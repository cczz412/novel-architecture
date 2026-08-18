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
RECORDED_AT = "2026-08-18T12:00:00+08:00"


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
        "actor": {"type": "USER", "reference": "USER-TITLE-TEST"},
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
        "actor": {"type": "SYSTEM", "reference": "STRUCTURED-TITLE-ENTRY"},
        "recorded_at": RECORDED_AT,
        "reason": f"受控结构化入口明确声明为 {role}",
    }


def _candidate_title(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": "TITLE",
        "state": "CANDIDATE",
        "basis": {
            "type": "CONTENT_CLASSIFICATION_CANDIDATE",
            "reference": "LOCAL-PARSER-TITLE-CANDIDATE",
        },
        "actor": {"type": "PARSER", "reference": "PARSER-TITLE-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": "只有候选依据，没有 Title 确认权",
    }


def _unknown(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": None,
        "state": "UNKNOWN",
        "basis": {"type": "NO_ASSERTION", "reference": None},
        "actor": {"type": "SYSTEM", "reference": "INTAKE-TITLE-TEST"},
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
        validate_record(record, f"product_title_records[{index}]")
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


def test_pt_01_confirmed_title_only_stays_in_c10_v3(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pt-01")
    text = "《雾城来信》\n"
    report = _ingest("pt-01", text, [_confirmed(0, len(text), "TITLE", "PT-01")])

    _assert_product_records(report, "v3")
    _assert_exact_source(report, text)
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "CONFIRMED" and identity["role"] == "TITLE"
    assert report["chapters"] == store.chapters("pt-01") == []
    assert report["projection_receipts"] == []
    assert report["api_calls"] == report["automatic_retries"] == 0


def test_pt_02_candidate_title_has_no_c1_or_m3_authority(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pt-02")
    text = "《可能的书名》\n"
    report = _ingest("pt-02", text, [_candidate_title(0, len(text))])

    _assert_product_records(report, "v3")
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "CANDIDATE" and identity["role"] == "TITLE"
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is False
    assert report["chapters"] == report["projection_receipts"] == []


def test_pt_03_title_plus_chapter_only_projects_chapter(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pt-03")
    title = "《雾城来信》\n"
    chapter = "第一章 雨夜\n沈砚推门走进内库。\n"
    text = title + chapter
    report = _ingest(
        "pt-03",
        text,
        [
            _structured(0, len(title), "TITLE", "PT-03-T"),
            _confirmed(len(title), len(text), "CHAPTER", "PT-03-C"),
        ],
    )

    _assert_product_records(report, "v3")
    _assert_exact_source(report, text)
    assert len(report["chapters"]) == 1
    assert title not in report["chapters"][0]["text"]
    segments, admission = product_cli.prepare_m3_segments(report["chapters"][0], CFG)
    sent = "".join(item["text"] for item in segments)
    assert admission["status"] == "READY"
    assert title not in sent and "沈砚推门走进内库" in sent


def test_pt_04_title_intro_setting_chapter_coexist_in_v3(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pt-04")
    title = "《雾城来信》\n"
    intro = "作品简介：她在旧城寻找失踪的兄长。\n"
    setting = "设定集：王朝共有九州。\n"
    chapter = "第一章 灰烬\n沈砚从灰里捡起半枚铜扣。\n"
    text = title + intro + setting + chapter
    title_end = len(title)
    intro_end = title_end + len(intro)
    setting_end = intro_end + len(setting)
    report = _ingest(
        "pt-04",
        text,
        [
            _confirmed(0, title_end, "TITLE", "PT-04-T"),
            _confirmed(title_end, intro_end, "INTRO", "PT-04-I"),
            _structured(intro_end, setting_end, "SETTING", "PT-04-S"),
            _confirmed(setting_end, len(text), "CHAPTER", "PT-04-C"),
        ],
    )

    _assert_product_records(report, "v3")
    _assert_exact_source(report, text)
    roles = [item["identity_revisions"][-1]["role"] for item in report["material_units"]]
    assert roles == ["TITLE", "INTRO", "SETTING", "CHAPTER"]
    assert len(report["chapters"]) == 1
    c1_text = report["chapters"][0]["text"]
    assert title not in c1_text and intro not in c1_text and setting not in c1_text
    assert "沈砚从灰里捡起半枚铜扣" in c1_text


def test_pt_05_story_hint_title_does_not_become_story_evidence(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pt-05")
    text = "《重生后我成为九州第一剑仙》\n"
    report = _ingest("pt-05", text, [_confirmed(0, len(text), "TITLE", "PT-05")])

    _assert_product_records(report, "v3")
    _assert_exact_source(report, text)
    assert report["chapters"] == report["projection_receipts"] == []
    assert set(report["material_units"][0]) == {
        "contract",
        "version",
        "material_unit_id",
        "source_ref",
        "identity_revisions",
    }


def test_pt_06_structured_title_entry_is_valid_but_still_not_c1(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pt-06")
    text = "雾城来信"
    report = _ingest("pt-06", text, [_structured(0, len(text), "TITLE", "PT-06")])

    _assert_product_records(report, "v3")
    _assert_exact_source(report, text)
    assert report["chapters"] == report["projection_receipts"] == []


def test_pt_07_title_like_text_and_filename_are_not_identity_authority(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pt-07")
    text = "《雾城来信》\n"
    report = _ingest(
        "pt-07",
        text,
        [_unknown(0, len(text))],
        source_name="book-title.txt",
    )

    _assert_product_records(report, "v1")
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "UNKNOWN" and identity["role"] is None
    assert report["chapters"] == report["projection_receipts"] == []


def test_pt_08_confirmed_chapter_behavior_stays_on_legacy_v1(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pt-08")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    report = _ingest("pt-08", text, [_confirmed(0, len(text), "CHAPTER", "PT-08")])

    _assert_product_records(report, "v1")
    assert len(report["chapters"]) == 1
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is True


def test_pt_09_title_to_chapter_revision_can_project_without_overwriting_history(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pt-09")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    initial = _ingest("pt-09", text, [_confirmed(0, len(text), "TITLE", "PT-09-R1")])
    unit_id = initial["material_units"][0]["material_unit_id"]
    assert initial["chapters"] == []

    revised = intake_identity.append_identity_revision(
        "pt-09",
        unit_id,
        role="CHAPTER",
        state="CONFIRMED",
        basis={"type": "USER_DECLARATION", "reference": "UI-PT-09-R2"},
        actor={"type": "USER", "reference": "USER-TITLE-TEST"},
        recorded_at="2026-08-18T12:01:00+08:00",
        reason="用户明确改判为章节书稿",
    )
    validate_record(revised)
    assert revised["version"] == "v3"
    assert [item["role"] for item in revised["identity_revisions"]] == ["TITLE", "CHAPTER"]
    assert intake_identity.current_c1_eligibility(revised) is True

    projection = intake_identity.project_material_units_to_c1("pt-09", [unit_id])
    assert len(projection["chapters"]) == 1
    assert len(store.intake_material_units("pt-09")[0]["identity_revisions"]) == 2


def test_pt_10_real_path_sends_only_chapter_to_fake_m3(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pt-10")
    title = "《重生后我成为九州第一剑仙》\n"
    chapter = "第一章 雨夜\n沈砚推门走进内库。\n"
    text = title + chapter
    report = _ingest(
        "pt-10",
        text,
        [
            _confirmed(0, len(title), "TITLE", "PT-10-T"),
            _confirmed(len(title), len(text), "CHAPTER", "PT-10-C"),
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
    product_cli.cmd_extract(SimpleNamespace(project="pt-10", chapter=None, redo=False))

    assert fake_m3_calls
    sent = "".join(fake_m3_calls)
    assert title not in sent
    assert "沈砚推门走进内库" in sent
