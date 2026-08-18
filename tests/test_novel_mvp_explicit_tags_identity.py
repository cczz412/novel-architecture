from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    import cli as product_cli
    from contracts.validate_c10_intake_material_identity import validate_record
    from mvp import ingest, intake_identity, store
finally:
    sys.path.pop(0)


CFG = {
    "model_id": "NO_API_TEST_DOUBLE",
    "seg_min_chars": 620,
    "seg_max_chars": 923,
    "halo_chars": 180,
}
RECORDED_AT = "2026-08-18T16:00:00+08:00"


def _init(tmp_path: Path, monkeypatch, project: str) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "data")
    store.init_project(project)


def _confirmed(start: int, end: int, role: str, suffix: str) -> dict:
    return {
        "start": start,
        "end": end,
        "role": role,
        "state": "CONFIRMED",
        "basis": {"type": "USER_DECLARATION", "reference": f"UI-{suffix}"},
        "actor": {"type": "USER", "reference": "USER-TAGS-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": f"用户明确声明为 {role}",
    }


def _structured(start: int, end: int, role: str, suffix: str) -> dict:
    return {
        "start": start,
        "end": end,
        "role": role,
        "state": "CONFIRMED",
        "basis": {"type": "STRUCTURED_ENTRY", "reference": f"SLOT-{suffix}"},
        "actor": {"type": "SYSTEM", "reference": "STRUCTURED-TAGS-ENTRY"},
        "recorded_at": RECORDED_AT,
        "reason": f"受控结构化入口明确声明为 {role}",
    }


def _candidate_tags(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": "TAGS",
        "state": "CANDIDATE",
        "basis": {
            "type": "CONTENT_CLASSIFICATION_CANDIDATE",
            "reference": "LOCAL-PARSER-TAGS-CANDIDATE",
        },
        "actor": {"type": "PARSER", "reference": "PARSER-TAGS-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": "只有候选依据，没有 Tags 确认权",
    }


def _unknown(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": None,
        "state": "UNKNOWN",
        "basis": {"type": "NO_ASSERTION", "reference": None},
        "actor": {"type": "SYSTEM", "reference": "INTAKE-TAGS-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": None,
    }


def _ingest(
    project: str,
    text: str,
    declarations: list[dict],
    *,
    source_name: str = "explicit-material.txt",
) -> dict:
    return ingest.ingest_explicit_materials(
        project,
        source_name=source_name,
        raw_bytes=text.encode("utf-8"),
        encoding="utf-8",
        declarations=declarations,
    )


def _assert_product_records(report: dict, expected_version: str) -> None:
    assert report["material_units"]
    for index, record in enumerate(report["material_units"]):
        validate_record(record, f"product_tags_records[{index}]")
        assert record["version"] == expected_version


def _assert_exact_source(report: dict, text: str) -> None:
    source = report["source"]
    raw = base64.b64decode(source["original_bytes_base64"], validate=True)
    assert raw == text.encode("utf-8")
    assert source["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert raw.decode(source["encoding"]) == source["decoded_text"] == text

    ordered = sorted(
        report["material_units"],
        key=lambda record: record["source_ref"]["start"],
    )
    spans = [
        (record["source_ref"]["start"], record["source_ref"]["end"])
        for record in ordered
    ]
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    assert all(left[1] == right[0] for left, right in zip(spans, spans[1:]))
    assert "".join(text[start:end] for start, end in spans) == text
    for record in ordered:
        ref = record["source_ref"]
        assert ref["source_sha256"] == source["source_sha256"]
        value = text[ref["start"] : ref["end"]]
        assert hashlib.sha256(value.encode()).hexdigest() == ref["slice_sha256"]


def test_ptg_01_multi_tag_block_stays_one_c10_v4_unit_without_dedup(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "ptg-01")
    text = "标签：重生、权谋、重生\n"
    report = _ingest("ptg-01", text, [_confirmed(0, len(text), "TAGS", "PTG-01")])

    _assert_product_records(report, "v4")
    _assert_exact_source(report, text)
    assert len(report["material_units"]) == 1
    assert report["source"]["decoded_text"] == text
    assert report["chapters"] == store.chapters("ptg-01") == []
    assert report["projection_receipts"] == []
    assert report["api_calls"] == report["automatic_retries"] == 0


def test_ptg_02_candidate_tags_has_no_c1_or_m3_authority(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ptg-02")
    text = "标签：重生、权谋、女强\n"
    report = _ingest("ptg-02", text, [_candidate_tags(0, len(text))])

    _assert_product_records(report, "v4")
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "CANDIDATE" and identity["role"] == "TAGS"
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is False
    assert report["chapters"] == report["projection_receipts"] == []


def test_ptg_03_tags_plus_chapter_only_projects_chapter(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ptg-03")
    tags = "标签：重生、权谋、女强\n"
    chapter = "第一章 雨夜\n沈砚推门走进内库。\n"
    text = tags + chapter
    report = _ingest(
        "ptg-03",
        text,
        [
            _structured(0, len(tags), "TAGS", "PTG-03-T"),
            _confirmed(len(tags), len(text), "CHAPTER", "PTG-03-C"),
        ],
    )

    _assert_product_records(report, "v4")
    _assert_exact_source(report, text)
    assert len(report["chapters"]) == 1
    assert tags not in report["chapters"][0]["text"]
    segments, admission = product_cli.prepare_m3_segments(report["chapters"][0], CFG)
    sent = "".join(item["text"] for item in segments)
    assert admission["status"] == "READY"
    assert tags not in sent and "沈砚推门走进内库" in sent


def test_ptg_04_title_intro_setting_tags_chapter_coexist_in_v4(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "ptg-04")
    title = "《雾城来信》\n"
    intro = "作品简介：她在旧城寻找兄长。\n"
    setting = "设定集：王朝共有九州。\n"
    tags = "标签：重生、权谋、女强\n"
    chapter = "第一章 灰烬\n沈砚从灰里捡起半枚铜扣。\n"
    text = title + intro + setting + tags + chapter
    title_end = len(title)
    intro_end = title_end + len(intro)
    setting_end = intro_end + len(setting)
    tags_end = setting_end + len(tags)
    report = _ingest(
        "ptg-04",
        text,
        [
            _confirmed(0, title_end, "TITLE", "PTG-04-TIT"),
            _confirmed(title_end, intro_end, "INTRO", "PTG-04-I"),
            _structured(intro_end, setting_end, "SETTING", "PTG-04-S"),
            _confirmed(setting_end, tags_end, "TAGS", "PTG-04-TAGS"),
            _confirmed(tags_end, len(text), "CHAPTER", "PTG-04-C"),
        ],
    )

    _assert_product_records(report, "v4")
    _assert_exact_source(report, text)
    roles = [item["identity_revisions"][-1]["role"] for item in report["material_units"]]
    assert roles == ["TITLE", "INTRO", "SETTING", "TAGS", "CHAPTER"]
    assert len(report["chapters"]) == 1
    c1_text = report["chapters"][0]["text"]
    assert all(value not in c1_text for value in (title, intro, setting, tags))
    assert "沈砚从灰里捡起半枚铜扣" in c1_text


def test_ptg_05_story_hint_tags_do_not_become_story_evidence(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ptg-05")
    text = "重生、权谋、女强\n"
    report = _ingest("ptg-05", text, [_confirmed(0, len(text), "TAGS", "PTG-05")])

    _assert_product_records(report, "v4")
    _assert_exact_source(report, text)
    assert report["chapters"] == report["projection_receipts"] == []
    assert set(report["material_units"][0]) == {
        "contract",
        "version",
        "material_unit_id",
        "source_ref",
        "identity_revisions",
    }


def test_ptg_06_structured_tags_entry_is_valid_but_still_not_c1(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "ptg-06")
    text = "重生、权谋、女强"
    report = _ingest("ptg-06", text, [_structured(0, len(text), "TAGS", "PTG-06")])

    _assert_product_records(report, "v4")
    _assert_exact_source(report, text)
    assert report["chapters"] == report["projection_receipts"] == []


def test_ptg_07_tag_like_text_filename_and_hashes_are_not_identity_authority(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "ptg-07")
    text = "标签：#重生 #权谋 #女强\n"
    report = _ingest(
        "ptg-07",
        text,
        [_unknown(0, len(text))],
        source_name="tags.txt",
    )

    _assert_product_records(report, "v1")
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "UNKNOWN" and identity["role"] is None
    assert report["chapters"] == report["projection_receipts"] == []


def test_ptg_08_confirmed_chapter_behavior_stays_on_legacy_v1(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ptg-08")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    report = _ingest("ptg-08", text, [_confirmed(0, len(text), "CHAPTER", "PTG-08")])

    _assert_product_records(report, "v1")
    assert len(report["chapters"]) == 1
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is True


def test_ptg_09_tags_to_chapter_revision_can_project_without_overwriting_history(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "ptg-09")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    initial = _ingest("ptg-09", text, [_confirmed(0, len(text), "TAGS", "PTG-09-R1")])
    unit_id = initial["material_units"][0]["material_unit_id"]
    assert initial["chapters"] == []

    revised = intake_identity.append_identity_revision(
        "ptg-09",
        unit_id,
        role="CHAPTER",
        state="CONFIRMED",
        basis={"type": "USER_DECLARATION", "reference": "UI-PTG-09-R2"},
        actor={"type": "USER", "reference": "USER-TAGS-TEST"},
        recorded_at="2026-08-18T16:01:00+08:00",
        reason="用户明确改判为章节书稿",
    )
    validate_record(revised)
    assert revised["version"] == "v4"
    assert [item["role"] for item in revised["identity_revisions"]] == ["TAGS", "CHAPTER"]
    assert intake_identity.current_c1_eligibility(revised) is True

    projection = intake_identity.project_material_units_to_c1("ptg-09", [unit_id])
    assert len(projection["chapters"]) == 1
    assert len(store.intake_material_units("ptg-09")[0]["identity_revisions"]) == 2


def test_ptg_10_real_path_sends_only_chapter_to_fake_m3(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ptg-10")
    tags = "标签：重生、权谋、女强\n"
    chapter = "第一章 雨夜\n沈砚推门走进内库。\n"
    text = tags + chapter
    report = _ingest(
        "ptg-10",
        text,
        [
            _confirmed(0, len(tags), "TAGS", "PTG-10-T"),
            _confirmed(len(tags), len(text), "CHAPTER", "PTG-10-C"),
        ],
    )
    assert len(report["chapters"]) == 1

    fake_m3_calls: list[str] = []
    monkeypatch.setattr(product_cli.ex, "load_config", lambda: CFG)
    monkeypatch.setattr(
        product_cli.ex,
        "extract_segment",
        lambda segment, cfg: fake_m3_calls.append(segment["text"]) or [],
    )
    monkeypatch.setattr(
        product_cli.store,
        "add_fact_candidates",
        lambda project, chapter_id, items, source: 0,
    )
    product_cli.cmd_extract(SimpleNamespace(project="ptg-10", chapter=None, redo=False))

    assert fake_m3_calls
    sent = "".join(fake_m3_calls)
    assert tags not in sent
    assert "沈砚推门走进内库" in sent
