import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("p4_splitter", ROOT / "tools" / "p4_splitter.py")
p4 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(p4)
SOURCE_PATH = ROOT / "tests" / "fixtures" / "toy_chapter.txt"
GOLD_PATH = ROOT / "tests" / "fixtures" / "toy_gold.json"


def source_bytes():
    return SOURCE_PATH.read_bytes()


def source_text():
    return source_bytes().decode("utf-8")


def source_sha():
    return p4.sha256_bytes(source_bytes())


def split(granularity="P4-GRAN-10"):
    return p4.split_chapter(source_bytes(), "TOY-CHAPTER-001", granularity, source_sha())


def test_atoms_and_zones_preserve_original_bytes_and_dialogue_turn():
    text = source_text()
    atoms = p4.atomize(text)
    assert "".join(item["text"] for item in atoms) == text
    assert any(item["text"] == "“我们今晚出发。”林舟说。\n" for item in atoms)
    for granularity in p4.GRANULARITIES:
        result = split(granularity)
        assert "".join(zone["text"] for zone in result["zones"]) == text
        assert result["source_sha256"] == source_sha()
        for zone in result["zones"]:
            assert text[zone["start_char"] : zone["end_char_exclusive"]] == zone["text"]
            encoded = source_bytes()
            assert (
                encoded[zone["start_byte"] : zone["end_byte_exclusive"]].decode("utf-8")
                == zone["text"]
            )


def test_crlf_multibyte_bytes_offsets_and_sha_are_preserved():
    raw = "甲说：“走。”\r\n乙点头。\r\n".encode("utf-8")
    expected = p4.sha256_bytes(raw)
    result = p4.split_chapter(raw, "TOY-CRLF", "P4-GRAN-10", expected)
    assert result["source_sha256"] == expected
    assert result["source_byte_count"] == len(raw)
    assert "".join(atom["text"] for atom in result["atoms"]).encode("utf-8") == raw
    for atom in result["atoms"]:
        assert raw[atom["start_byte"] : atom["end_byte_exclusive"]].decode("utf-8") == atom["text"]
    assert "\r\n" in result["atoms"][0]["text"]


def test_non_utf8_and_sha_drift_fail_closed():
    with pytest.raises(p4.SplitterError, match="strict UTF-8"):
        p4.split_chapter(b"\xff", "BAD", "P4-GRAN-10", p4.sha256_bytes(b"\xff"))
    with pytest.raises(p4.SplitterError, match="source SHA drift"):
        p4.split_chapter("正文。".encode(), "DRIFT", "P4-GRAN-10", "0" * 64)


def test_two_builds_are_byte_identical():
    first = p4.canonical_json_bytes(p4.build_toy(SOURCE_PATH, GOLD_PATH, source_sha()))
    second = p4.canonical_json_bytes(p4.build_toy(SOURCE_PATH, GOLD_PATH, source_sha()))
    assert first == second
    assert p4.sha256_bytes(first) == p4.sha256_bytes(second)


def test_gold_classifies_single_span_and_multi_span_cross_zone_after_split():
    before = split()
    snapshot = p4.canonical_json_bytes(before)
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["facts"]
    audit = p4.classify_frozen_gold(source_bytes(), before, gold)
    assert p4.canonical_json_bytes(before) == snapshot
    by_id = {fact["fact_id"]: fact for fact in audit["facts"]}
    assert all(
        span["exact_source_match"]
        for fact in audit["facts"]
        for span in fact["evidence_spans"]
    )
    assert by_id["TOY-F02"]["classification"] == "CROSS_RESPONSIBILITY_ZONES"
    assert len(by_id["TOY-F02"]["evidence_spans"]) == 2
    assert by_id["TOY-F04"]["classification"] == "CROSS_RESPONSIBILITY_ZONES"
    assert len(by_id["TOY-F04"]["evidence_spans"]) == 1
    assert len(by_id["TOY-F04"]["evidence_spans"][0]["intersecting_zone_ids"]) > 1


def test_fixed_denominators_prevent_narrow_zone_denominator_gain():
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["facts"]
    audits = {
        granularity: p4.classify_frozen_gold(source_bytes(), split(granularity), gold)
        for granularity in p4.GRANULARITIES
    }
    registry = p4.build_denominator_registry(gold, audits)
    assert registry["all_gold_denominator"] == 4
    expected_intersection = set(registry["per_granularity_contained_diagnostic_only"]["P4-GRAN-10"])
    expected_intersection &= set(registry["per_granularity_contained_diagnostic_only"]["P4-GRAN-20"])
    expected_intersection &= set(registry["per_granularity_contained_diagnostic_only"]["P4-GRAN-30"])
    assert set(registry["common_contained_fact_ids"]) == expected_intersection
    assert "TOY-F02" not in registry["common_contained_fact_ids"]
    assert "TOY-F04" not in registry["common_contained_fact_ids"]


def test_model_payload_has_no_position_or_treatment_metadata():
    pair = p4.render_pair(
        split(),
        4,
        p4.TOY_ONLY_SYSTEM_PROMPT,
        p4.TOY_ONLY_OUTPUT_CONTRACT,
    )
    visible = json.dumps(pair["model_payloads"], ensure_ascii=False, sort_keys=True)
    forbidden = (
        "P4-GRAN",
        "-Z",
        "U000",
        "start_char",
        "end_char",
        "start_byte",
        "end_byte",
        "LOCAL_READ",
        "FULL_CHAPTER_READ",
    )
    assert not any(token in visible for token in forbidden)
    for payload in pair["model_payloads"].values():
        for row in payload["responsibility_excerpt"]["rows"]:
            assert set(row) == {"evidence_id", "text"}
    for row in pair["run_sidecar"]["responsibility_mapping"]["rows"]:
        assert {
            "evidence_id",
            "stable_atom_id",
            "start_char",
            "end_char_exclusive",
            "start_byte",
            "end_byte_exclusive",
            "text",
        } == set(row)


def test_local_and_full_model_payload_only_change_read_context_text():
    pair = p4.render_pair(
        split(),
        4,
        p4.TOY_ONLY_SYSTEM_PROMPT,
        p4.TOY_ONLY_OUTPUT_CONTRACT,
    )
    local = pair["model_payloads"]["local"]
    full = pair["model_payloads"]["full"]
    assert local["read_context"]["text"] != full["read_context"]["text"]
    normalized_local = json.loads(json.dumps(local, ensure_ascii=False))
    normalized_local["read_context"]["text"] = full["read_context"]["text"]
    assert p4.canonical_json_bytes(normalized_local) == p4.canonical_json_bytes(full)
    target_text = "".join(row["text"] for row in local["responsibility_excerpt"]["rows"])
    assert local["read_context"]["text"].count(target_text) == 1
    assert full["read_context"]["text"].count(target_text) == 1
    assert pair["run_sidecar"]["arms"]["local"]["arm"] == "LOCAL_READ"
    assert pair["run_sidecar"]["arms"]["full"]["arm"] == "FULL_CHAPTER_READ"


def test_oversized_sentence_is_never_broken_for_zone_target():
    raw = ("甲" * 500 + "。").encode("utf-8")
    result = p4.split_chapter(raw, "TOY-LONG", "P4-GRAN-30", p4.sha256_bytes(raw))
    assert result["atomic_unit_count"] == 1
    assert result["actual_zone_count"] == 1
    assert result["zones"][0]["text"] == raw.decode("utf-8")


def test_all_granularities_reach_requested_zone_counts_on_72_complete_atoms():
    text = "".join(
        f"第{index:03d}个完整原子单元包含汉字与符号🙂。"
        for index in range(1, 73)
    )
    raw = text.encode("utf-8")
    expected_sha = p4.sha256_bytes(raw)
    results = {}

    for granularity, expected_zone_count in p4.GRANULARITIES.items():
        first = p4.split_chapter(
            raw,
            "TOY-72-COMPLETE-ATOMS",
            granularity,
            expected_sha,
        )
        second = p4.split_chapter(
            raw,
            "TOY-72-COMPLETE-ATOMS",
            granularity,
            expected_sha,
        )
        assert p4.canonical_json_bytes(first) == p4.canonical_json_bytes(second)
        assert first["source_sha256"] == expected_sha
        assert first["atomic_unit_count"] == 72
        assert first["actual_zone_count"] == expected_zone_count
        assert [zone["zone_id"] for zone in first["zones"]] == [
            f"{granularity}-Z{index:03d}"
            for index in range(1, expected_zone_count + 1)
        ]

        assert "".join(atom["text"] for atom in first["atoms"]).encode("utf-8") == raw
        assert "".join(zone["text"] for zone in first["zones"]).encode("utf-8") == raw
        for rows in (first["atoms"], first["zones"]):
            assert rows[0]["start_char"] == 0
            assert rows[0]["start_byte"] == 0
            assert rows[-1]["end_char_exclusive"] == len(text)
            assert rows[-1]["end_byte_exclusive"] == len(raw)
            for previous, current in zip(rows, rows[1:]):
                assert previous["end_char_exclusive"] == current["start_char"]
                assert previous["end_byte_exclusive"] == current["start_byte"]
            for row in rows:
                assert text[row["start_char"] : row["end_char_exclusive"]] == row["text"]
                assert (
                    raw[row["start_byte"] : row["end_byte_exclusive"]].decode("utf-8")
                    == row["text"]
                )

        atom_lookup = {atom["atom_id"]: atom for atom in first["atoms"]}
        for zone in first["zones"]:
            assert "".join(atom_lookup[atom_id]["text"] for atom_id in zone["atom_ids"]) == zone["text"]
        results[granularity] = first

    boundary_signatures = {
        granularity: tuple(
            (
                zone["start_char"],
                zone["end_char_exclusive"],
                zone["start_byte"],
                zone["end_byte_exclusive"],
            )
            for zone in result["zones"]
        )
        for granularity, result in results.items()
    }
    assert len(set(boundary_signatures.values())) == 3

    zone_id_sets = [
        {zone["zone_id"] for zone in results[granularity]["zones"]}
        for granularity in p4.GRANULARITIES
    ]
    assert all(
        left.isdisjoint(right)
        for index, left in enumerate(zone_id_sets)
        for right in zone_id_sets[index + 1 :]
    )
