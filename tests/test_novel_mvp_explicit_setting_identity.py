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
RECORDED_AT = "2026-08-17T15:00:00+08:00"


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
        "actor": {"type": "USER", "reference": "USER-SETTING-TEST"},
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
        "actor": {"type": "SYSTEM", "reference": "STRUCTURED-SETTING-ENTRY"},
        "recorded_at": RECORDED_AT,
        "reason": f"结构化入口明确声明为 {role}",
    }


def _candidate_setting(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": "SETTING",
        "state": "CANDIDATE",
        "basis": {
            "type": "CONTENT_CLASSIFICATION_CANDIDATE",
            "reference": "LOCAL-PARSER-SETTING-CANDIDATE",
        },
        "actor": {"type": "PARSER", "reference": "PARSER-SETTING-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": "只有候选依据，没有 Setting 确认权",
    }


def _unknown(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": None,
        "state": "UNKNOWN",
        "basis": {"type": "NO_ASSERTION", "reference": None},
        "actor": {"type": "SYSTEM", "reference": "INTAKE-SETTING-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": None,
    }


def _ingest(project: str, text: str, declarations: list[dict]) -> dict:
    return ingest.ingest_explicit_materials(
        project,
        source_name="explicit-material.txt",
        raw_bytes=text.encode("utf-8"),
        encoding="utf-8",
        declarations=declarations,
    )


def _assert_product_records(report: dict, expected_version: str) -> None:
    assert report["material_units"]
    for index, record in enumerate(report["material_units"]):
        validate_record(record, f"product_setting_records[{index}]")
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
        assert hashlib.sha256(text[ref["start"] : ref["end"]].encode()).hexdigest() == ref[
            "slice_sha256"
        ]


def test_ps_01_explicit_setting_only_stays_in_c10_v2(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-01")
    text = "设定集：王朝共有九州，修士境界共九层。\n"
    report = _ingest("ps-01", text, [_confirmed(0, len(text), "SETTING", "PS-01")])

    _assert_product_records(report, "v2")
    _assert_exact_source(report, text)
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "CONFIRMED" and identity["role"] == "SETTING"
    assert report["chapters"] == store.chapters("ps-01") == []
    assert report["projection_receipts"] == []
    assert report["api_calls"] == report["automatic_retries"] == 0


def test_ps_02_setting_plus_chapter_only_projects_chapter(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-02")
    setting = "设定集：王朝共有九州。\n\n"
    chapter = "第一章 雨夜\n沈砚推门走进内库。\n"
    text = setting + chapter
    report = _ingest(
        "ps-02",
        text,
        [
            _structured(0, len(setting), "SETTING", "PS-02-S"),
            _confirmed(len(setting), len(text), "CHAPTER", "PS-02-C"),
        ],
    )

    _assert_product_records(report, "v2")
    _assert_exact_source(report, text)
    assert len(report["chapters"]) == 1
    assert setting not in report["chapters"][0]["text"]
    segments, admission = product_cli.prepare_m3_segments(report["chapters"][0], CFG)
    assert admission["status"] == "READY"
    assert segments and setting not in "".join(item["text"] for item in segments)


def test_ps_03_intro_setting_chapter_coexist_in_v2(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-03")
    intro = "作品简介：她在旧城寻找失踪的兄长。\n\n"
    setting = "设定集：王朝共有九州。\n\n"
    chapter = "第一章 灰烬\n沈砚从灰里捡起半枚铜扣。\n"
    text = intro + setting + chapter
    report = _ingest(
        "ps-03",
        text,
        [
            _confirmed(0, len(intro), "INTRO", "PS-03-I"),
            _confirmed(len(intro), len(intro + setting), "SETTING", "PS-03-S"),
            _structured(len(intro + setting), len(text), "CHAPTER", "PS-03-C"),
        ],
    )

    _assert_product_records(report, "v2")
    _assert_exact_source(report, text)
    assert [unit["identity_revisions"][-1]["role"] for unit in report["material_units"]] == [
        "INTRO",
        "SETTING",
        "CHAPTER",
    ]
    assert len(report["chapters"]) == 1
    assert intro not in report["chapters"][0]["text"]
    assert setting not in report["chapters"][0]["text"]


def test_ps_04_setting_plus_multi_chapter_keeps_safe_split(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-04")
    setting = "设定集：王朝共有九州。\n\n"
    manuscript = "第一章 雨夜\n沈砚推门。\n第二章 清晨\n他带着印册离开。\n"
    text = setting + manuscript
    report = _ingest(
        "ps-04",
        text,
        [
            _confirmed(0, len(setting), "SETTING", "PS-04-S"),
            _confirmed(len(setting), len(text), "CHAPTER", "PS-04-C"),
        ],
    )

    _assert_product_records(report, "v2")
    _assert_exact_source(report, text)
    assert [chapter["title"] for chapter in report["chapters"]] == ["第一章 雨夜", "第二章 清晨"]
    assert all(setting not in chapter["text"] for chapter in report["chapters"])


def test_ps_05_candidate_setting_has_no_chapter_authority(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-05")
    text = "世界分为五洲，或许仍需作者确认。\n"
    report = _ingest("ps-05", text, [_candidate_setting(0, len(text))])

    _assert_product_records(report, "v2")
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "CANDIDATE" and identity["role"] == "SETTING"
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is False
    assert report["chapters"] == report["projection_receipts"] == []


def test_ps_06_unknown_with_setting_words_never_defaults_to_chapter(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "ps-06")
    text = "境界、规则、能力、每天三次、共九州，但身份未确认。\n"
    report = _ingest("ps-06", text, [_unknown(0, len(text))])

    _assert_product_records(report, "v1")
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "UNKNOWN" and identity["role"] is None
    assert report["chapters"] == report["projection_receipts"] == []


def test_ps_07_fact_dense_setting_never_reaches_c1_or_m3(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-07")
    text = "某境界最多活三百年。\n主角每天可使用三次能力。\n王朝共有九州。"
    report = _ingest("ps-07", text, [_structured(0, len(text), "SETTING", "PS-07")])

    _assert_product_records(report, "v2")
    _assert_exact_source(report, text)
    assert report["source"]["source_sha256"] == (
        "609187d81db717ad13dc248eff5fb1b6d6fd1e4d24cc6525d3cb8138abe749fa"
    )
    assert report["chapters"] == report["projection_receipts"] == []


def test_ps_08_confirmed_chapter_positive_control_still_works(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-08")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    report = _ingest("ps-08", text, [_confirmed(0, len(text), "CHAPTER", "PS-08")])

    _assert_product_records(report, "v1")
    assert len(report["chapters"]) == 1
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is True
    segments, admission = product_cli.prepare_m3_segments(report["chapters"][0], CFG)
    assert admission["status"] == "READY" and segments


def test_ps_09_v2_setting_to_chapter_revision_appends_and_recomputes(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "ps-09")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    initial = _ingest("ps-09", text, [_confirmed(0, len(text), "SETTING", "PS-09-R1")])
    unit_id = initial["material_units"][0]["material_unit_id"]
    assert initial["material_units"][0]["version"] == "v2"
    assert initial["chapters"] == []

    revised = intake_identity.append_identity_revision(
        "ps-09",
        unit_id,
        role="CHAPTER",
        state="CONFIRMED",
        basis={"type": "USER_DECLARATION", "reference": "UI-PS-09-R2"},
        actor={"type": "USER", "reference": "USER-SETTING-TEST"},
        recorded_at="2026-08-17T15:01:00+08:00",
        reason="用户明确改判为章节书稿",
    )
    validate_record(revised)
    assert revised["version"] == "v2"
    assert [item["role"] for item in revised["identity_revisions"]] == ["SETTING", "CHAPTER"]
    assert intake_identity.current_c1_eligibility(revised) is True

    projection = intake_identity.project_material_units_to_c1("ps-09", [unit_id])
    assert len(projection["chapters"]) == 1
    assert len(store.intake_material_units("ps-09")[0]["identity_revisions"]) == 2


def test_ps_10_real_path_sends_only_chapter_to_fake_m3(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "ps-10")
    setting = "设定集：某境界最多活三百年，能力每日只能用三次。\n\n"
    chapter = "第一章 雨夜\n沈砚推门走进内库。\n"
    text = setting + chapter
    report = _ingest(
        "ps-10",
        text,
        [
            _confirmed(0, len(setting), "SETTING", "PS-10-S"),
            _confirmed(len(setting), len(text), "CHAPTER", "PS-10-C"),
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
    product_cli.cmd_extract(SimpleNamespace(project="ps-10", chapter=None, redo=False))

    assert fake_m3_calls
    sent = "".join(fake_m3_calls)
    assert setting not in sent
    assert "沈砚推门走进内库" in sent
