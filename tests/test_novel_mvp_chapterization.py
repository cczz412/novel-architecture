from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
T03_ROOT = ROOT / "TEMP/t03_parallel_r13_m1_m2_20260815_r01"
RECEIPT_ROOT = T03_ROOT / "t03_prod_02_safe_chapterization_20260817_r01"
LOCK_PATH = RECEIPT_ROOT / "CHAPTERIZATION_FIXTURE_LOCK.json"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    import cli as product_cli
    from mvp import chapterize, ingest, segment
finally:
    sys.path.pop(0)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def _case(case_id: str) -> dict:
    return next(item for item in _lock()["cases"] if item["case_id"] == case_id)


def _materialize(case_id: str) -> str:
    case = _case(case_id)
    if case["kind"] == "literal_text":
        text = case["text"]
    elif case["kind"] == "generated_text":
        text = case["pattern"] * case["repeat"]
    elif case["kind"] == "ordered_concatenation_of_frozen_inputs":
        directory = Path(case["directory"])
        payloads = [(directory / name).read_bytes() for name in case["filenames"]]
        assert [_sha256_bytes(value) for value in payloads] == case["source_file_sha256"]
        text = b"".join(payloads).decode("utf-8")
    else:
        raise AssertionError(f"没有文本的夹具：{case_id}")
    assert len(text) == case.get("chars", case.get("combined_chars"))
    expected_sha = case.get("sha256", case.get("combined_sha256"))
    assert _sha256_bytes(text.encode("utf-8")) == expected_sha
    return text


def _write_case(tmp_path: Path, case_id: str) -> Path:
    path = tmp_path / f"{case_id}.txt"
    path.write_text(_materialize(case_id), encoding="utf-8")
    return path


def _install_fake_batch_store(monkeypatch) -> tuple[list[dict], list[list[dict]]]:
    saved: list[dict] = []
    writes: list[list[dict]] = []
    sources: list[dict] = []
    units: list[dict] = []
    projections: list[dict] = []

    def fake_add_chapters(project: str, items: list[dict]) -> list[dict]:
        writes.append(copy.deepcopy(items))
        built = []
        for item in items:
            chapter = {
                "id": f"c{len(saved) + 1:02d}",
                "title": item["title"],
                "kind": item.get("kind", "draft"),
                "text": item["text"],
                "added_at": "product-test",
            }
            saved.append(chapter)
            built.append(chapter)
        return built

    monkeypatch.setattr(ingest.store, "add_chapters", fake_add_chapters)
    monkeypatch.setattr(ingest.store, "chapters", lambda project: saved)
    monkeypatch.setattr(ingest.store, "intake_sources", lambda project: sources)
    monkeypatch.setattr(ingest.store, "intake_material_units", lambda project: units)
    monkeypatch.setattr(ingest.store, "intake_c1_projections", lambda project: projections)
    monkeypatch.setattr(
        ingest.store,
        "add_intake_source",
        lambda project, source: sources.append(copy.deepcopy(source)) or source,
    )
    monkeypatch.setattr(
        ingest.store,
        "add_intake_material_units",
        lambda project, records: units.extend(copy.deepcopy(records)) or records,
    )
    monkeypatch.setattr(
        ingest.store,
        "add_intake_c1_projections",
        lambda project, receipts: projections.extend(copy.deepcopy(receipts)) or receipts,
    )
    return saved, writes


def _assert_exact_coverage(text: str, result: dict) -> None:
    spans = result["coverage_segments"]
    assert result["source_sha256"] == _sha256_bytes(text.encode("utf-8"))
    assert result["coverage"] == {
        "source_chars": len(text),
        "covered_chars": len(text),
        "lost_chars": 0,
        "duplicated_chars": 0,
        "reordered_chars": 0,
        "illegal_overlap": 0,
    }
    assert "".join(text[item["start"] : item["end"]] for item in spans) == text
    assert all(left["end"] == right["start"] for left, right in zip(spans, spans[1:]))
    for candidate in result["candidates"]:
        source = candidate["source_ref"]
        assert text[source["body_start"] : source["body_end"]] == candidate["text"]
        assert _sha256_bytes(candidate["text"].encode("utf-8")) == candidate["text_sha256"]


def test_p_ch_01_clean_three_chapters_enter_three_c1(tmp_path, monkeypatch) -> None:
    text = _materialize("P-CH-01")
    result = chapterize.chapterize_text(text, default_title="clean-three")
    _assert_exact_coverage(text, result)
    assert result["status"] == "READY"
    assert [item["chapter_no"] for item in result["candidates"]] == [1, 2, 3]

    saved, writes = _install_fake_batch_store(monkeypatch)
    report = ingest.ingest_files(
        "no-write",
        [str(_write_case(tmp_path, "P-CH-01"))],
        material_role="CHAPTER",
    )
    assert report["count"] == 3
    assert len(writes) == 1
    assert saved == report["chapters"]
    assert [item["text"] for item in saved] == [
        item["text"] for item in result["candidates"]
    ]


def test_p_ch_02_frozen_clean_ten_chapters_enter_ten_c1(tmp_path, monkeypatch) -> None:
    text = _materialize("P-CH-02")
    result = chapterize.chapterize_text(text, default_title="clean-ten")
    _assert_exact_coverage(text, result)
    assert result["status"] == "READY"
    assert [item["chapter_no"] for item in result["candidates"]] == list(range(1, 11))

    saved, writes = _install_fake_batch_store(monkeypatch)
    report = ingest.ingest_files(
        "no-write",
        [str(_write_case(tmp_path, "P-CH-02"))],
        material_role="CHAPTER",
    )
    assert report["count"] == 10
    assert len(writes) == 1
    assert [item["text"] for item in saved] == [
        item["text"] for item in result["candidates"]
    ]


def test_p_ch_03_duplicate_display_titles_do_not_overwrite(tmp_path, monkeypatch) -> None:
    text = _materialize("P-CH-03")
    result = chapterize.chapterize_text(text, default_title="duplicate-title")
    assert [item["display_title"] for item in result["candidates"]] == ["同名", "同名"]

    saved, writes = _install_fake_batch_store(monkeypatch)
    report = ingest.ingest_files(
        "no-write",
        [str(_write_case(tmp_path, "P-CH-03"))],
        material_role="CHAPTER",
    )
    assert report["count"] == 2
    assert len(writes) == 1
    assert [item["id"] for item in saved] == ["c01", "c02"]
    assert saved[0]["text"] != saved[1]["text"]


def test_p_ch_04_empty_and_short_chapters_keep_boundaries(tmp_path, monkeypatch) -> None:
    text = _materialize("P-CH-04")
    result = chapterize.chapterize_text(text, default_title="empty-short")
    assert [item["text"] for item in result["candidates"]] == ["", "短。\n", "正文。"]
    assert any("正文为空" in warning for warning in result["warnings"])

    saved, writes = _install_fake_batch_store(monkeypatch)
    report = ingest.ingest_files(
        "no-write",
        [str(_write_case(tmp_path, "P-CH-04"))],
        material_role="CHAPTER",
    )
    assert len(writes) == 1
    assert report["count"] == 3
    assert [item["text"] for item in saved] == ["", "短。\n", "正文。"]


def test_p_ch_05_untitled_long_text_stays_one_c1_not_many_responsibility_units(
    tmp_path, monkeypatch
) -> None:
    text = _materialize("P-CH-05")
    result = chapterize.chapterize_text(text, default_title="untitled-long")
    assert result["status"] == "SINGLE_UNTITLED"
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["text"] == text
    _assert_exact_coverage(text, result)

    saved, writes = _install_fake_batch_store(monkeypatch)
    report = ingest.ingest_files(
        "no-write",
        [str(_write_case(tmp_path, "P-CH-05"))],
        material_role="CHAPTER",
    )
    assert report["count"] == 1
    assert len(saved) == 1
    assert len(writes) == 1

    responsibility_text = "\n\n".join(["段" * 800] * 4)
    responsibility_chapters = chapterize.chapterize_text(
        responsibility_text, default_title="responsibility-control"
    )
    responsibility_units = segment.segment_chapter(responsibility_text, 620, 923, 180)
    assert len(responsibility_chapters["candidates"]) == 1
    assert len(responsibility_units) > 1


def test_p_ch_06_sequence_contradiction_blocks_before_any_batch_write(
    tmp_path, monkeypatch
) -> None:
    clean_path = _write_case(tmp_path, "P-CH-01")
    bad_path = _write_case(tmp_path, "P-CH-06")
    result = chapterize.chapterize_text(_materialize("P-CH-06"), default_title="bad")
    assert result["status"] == "BLOCKED"
    assert result["candidates"] == []
    assert any(item["type"] == "chapter_sequence_contradiction" for item in result["blocks"])

    monkeypatch.setattr(product_cli.store, "DATA_ROOT", tmp_path / "product-data")
    product_cli.store.init_project("atomic-stop")
    with pytest.raises(chapterize.ChapterizationBlocked) as caught:
        ingest.ingest_files(
            "atomic-stop",
            [str(clean_path), str(bad_path)],
            material_role="CHAPTER",
        )
    assert caught.value.receipt["status"] == "BLOCKED"
    assert product_cli.store.chapters("atomic-stop") == []


def test_p_ch_07_all_success_cases_have_exact_source_coverage() -> None:
    for case_id in _case("P-CH-07")["cases"]:
        text = _materialize(case_id)
        result = chapterize.chapterize_text(text, default_title=case_id)
        assert result["status"] != "BLOCKED"
        _assert_exact_coverage(text, result)


def test_p_ch_08_real_cli_path_reaches_admission_then_fake_m3_without_api(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(product_cli.store, "DATA_ROOT", tmp_path / "product-data")
    product_cli.store.init_project("product-path")
    source_path = _write_case(tmp_path, "P-CH-01")
    product_cli.cmd_ingest(
        SimpleNamespace(
            project="product-path",
            files=[str(source_path)],
            outline=False,
            title=None,
            material_role="chapter",
            declarations=None,
        )
    )
    saved = product_cli.store.chapters("product-path")
    assert len(saved) == 3

    admission_receipts = []
    cfg = {"model_id": "NO_API_TEST_DOUBLE", "seg_min_chars": 620, "seg_max_chars": 923, "halo_chars": 180}
    for chapter in saved:
        segments, receipt = product_cli.prepare_m3_segments(chapter, cfg)
        admission_receipts.append(receipt)
        assert segments
    assert [item["status"] for item in admission_receipts] == ["READY", "READY", "READY"]

    fake_m3_calls: list[dict] = []
    monkeypatch.setattr(product_cli.ex, "load_config", lambda: cfg)
    monkeypatch.setattr(
        product_cli.ex,
        "extract_segment",
        lambda item, config: fake_m3_calls.append(copy.deepcopy(item)) or [],
    )
    monkeypatch.setattr(
        product_cli.store,
        "add_fact_candidates",
        lambda project, chapter_id, items, source: 0,
    )
    product_cli.cmd_extract(SimpleNamespace(project="product-path", chapter=None, redo=False))
    assert len(fake_m3_calls) == 3


def test_known_r01_r03_and_dht05_never_publish_known_wrong_splits() -> None:
    s1a_lock = json.loads(
        (T03_ROOT / "t03_s1a_fix_20260817_r01/S1A_BEFORE_LOCK.json").read_text(
            encoding="utf-8"
        )
    )
    r01 = next(item for item in s1a_lock["cases"] if item["case_id"] == "S1A-R01")
    r01_text = Path(r01["inputs"][0]["path"]).read_text(encoding="utf-8")
    r01_result = chapterize.chapterize_text(r01_text, default_title="R01")
    assert r01_result["status"] == "BLOCKED" or [
        item["chapter_no"] for item in r01_result["candidates"]
    ] == list(range(1, 11))

    r03_baseline = json.loads(
        (
            T03_ROOT
            / "t03_r03_double_heading_fix_20260817_r01/R03_DOUBLE_HEADING_BASELINE.json"
        ).read_text(encoding="utf-8")
    )
    r03_text = Path(r03_baseline["source"]["path"]).read_text(encoding="utf-8")
    r03_result = chapterize.chapterize_text(r03_text, default_title="R03")
    assert r03_result["status"] == "BLOCKED"
    assert r03_result["candidates"] == []

    dht05_path = (
        T03_ROOT
        / "t03_r03_double_heading_fix_20260817_r01/fixtures/DHT-05_body_between_candidates.txt"
    )
    dht05_result = chapterize.chapterize_text(
        dht05_path.read_text(encoding="utf-8"), default_title="DHT-05"
    )
    assert dht05_result["status"] == "BLOCKED"
    assert dht05_result["candidates"] == []


def test_s1a_f09_ambiguous_compact_section_fails_closed_without_overreach() -> None:
    fixture_root = T03_ROOT / "t03_s1a_fix_20260817_r01/fixtures"
    f09_text = (fixture_root / "F09_ambiguous_compact_section_sentence.txt").read_text(
        encoding="utf-8"
    )
    f09_result = chapterize.chapterize_text(f09_text, default_title="F09")
    assert f09_result["status"] == "BLOCKED"
    assert f09_result["candidates"] == []
    assert f09_result["blocks"] == [
        {
            "type": "ambiguous_unrecognized_heading",
            "detail": "无明确章标题，但出现不能安全当作无标题正文的结构行：第七节雨夜将至？",
        }
    ]
    _assert_exact_coverage(f09_text, f09_result)

    general_result = chapterize.chapterize_text(
        "第九节风声停了！\n她没有回头。\n", default_title="general-control"
    )
    assert general_result["status"] == "BLOCKED"

    for case_id in ("F03_valid_bare_section_title", "F04_valid_section_title_with_name"):
        text = (fixture_root / f"{case_id}.txt").read_text(encoding="utf-8")
        result = chapterize.chapterize_text(text, default_title=case_id)
        assert result["status"] == "READY"
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["chapter_no"] == 7
        assert result["candidates"][0]["text"] == "雨点敲在窗纸上。\n"
        _assert_exact_coverage(text, result)


def test_stable_double_heading_groups_collapse_without_relaxing_negative_controls() -> None:
    fixture_root = T03_ROOT / "t03_r03_double_heading_fix_20260817_r01/fixtures"
    stable_text = (fixture_root / "DHT-02_stable_double_heading.txt").read_text(
        encoding="utf-8"
    )
    stable = chapterize.chapterize_text(stable_text, default_title="DHT-02")
    assert stable["status"] == "READY"
    assert [item["chapter_no"] for item in stable["candidates"]] == [1, 2]
    assert [item["text"] for item in stable["candidates"]] == [
        "雨点敲在窗纸上。\n",
        "天光从山后升起。\n",
    ]
    _assert_exact_coverage(stable_text, stable)

    for name in ("DHT-05_body_between_candidates.txt", "DHT-10_isolated_ambiguous_pair.txt"):
        text = (fixture_root / name).read_text(encoding="utf-8")
        result = chapterize.chapterize_text(text, default_title=name)
        assert result["status"] == "BLOCKED"
        assert result["candidates"] == []


def test_real_r03_unknown_preamble_plus_chapter_span_reaches_three_c1(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(product_cli.store, "DATA_ROOT", tmp_path / "data")
    product_cli.store.init_project("r03-explicit")
    baseline = json.loads(
        (
            T03_ROOT
            / "t03_r03_double_heading_fix_20260817_r01/R03_DOUBLE_HEADING_BASELINE.json"
        ).read_text(encoding="utf-8")
    )
    source_path = Path(baseline["source"]["path"])
    text = source_path.read_text(encoding="utf-8")
    chapter_start = text.find("第1章")
    assert chapter_start == 80
    declarations = [
        {
            "start": 0,
            "end": chapter_start,
            "role": None,
            "state": "UNKNOWN",
            "basis": {"type": "NO_ASSERTION", "reference": None},
            "actor": {"type": "SYSTEM", "reference": "R03-PREAMBLE"},
            "recorded_at": "2026-08-18T19:00:00+08:00",
            "reason": None,
        },
        {
            "start": chapter_start,
            "end": len(text),
            "role": "CHAPTER",
            "state": "CONFIRMED",
            "basis": {"type": "USER_DECLARATION", "reference": "R03-CHAPTERS"},
            "actor": {"type": "USER", "reference": "USER-R03-TEST"},
            "recorded_at": "2026-08-18T19:00:00+08:00",
            "reason": "用户明确声明正文区间",
        },
    ]
    report = ingest.ingest_files(
        "r03-explicit",
        [str(source_path)],
        declaration_manifest=declarations,
    )

    assert len(report["material_units"]) == 2
    assert len(report["chapters"]) == 3
    assert [item["title"] for item in report["chapters"]] == [
        "第1章绯红",
        "第2章情况",
        "第3章梅丽莎（第一更求推荐票）",
    ]
    assert all(text[:chapter_start] not in item["text"] for item in report["chapters"])
    assert report["projection_receipts"][0]["chapter_ids"] == ["c01", "c02", "c03"]


def test_explicit_outline_keeps_previous_one_input_one_c1_behavior(tmp_path, monkeypatch) -> None:
    path = tmp_path / "outline.txt"
    text = "第一章 计划\n主角将在雨夜潜入内库。\n第二章 计划\n之后再决定是否告发。"
    path.write_text(text, encoding="utf-8")
    saved, writes = _install_fake_batch_store(monkeypatch)

    report = ingest.ingest_files("no-write", [str(path)], kind="outline")

    assert len(writes) == 1
    assert report["count"] == 1
    assert saved[0]["kind"] == "outline"
    assert saved[0]["text"] == text
