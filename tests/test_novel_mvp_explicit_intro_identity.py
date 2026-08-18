from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


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
RECORDED_AT = "2026-08-17T12:00:00+08:00"


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
        "actor": {"type": "USER", "reference": "USER-PRODUCT-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": f"用户明确声明为 {role}",
    }


def _candidate_intro(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": "INTRO",
        "state": "CANDIDATE",
        "basis": {
            "type": "CONTENT_CLASSIFICATION_CANDIDATE",
            "reference": "LOCAL-PARSER-PROBE",
        },
        "actor": {"type": "PARSER", "reference": "PARSER-PRODUCT-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": "只有候选依据，没有确认权威",
    }


def _unknown(start: int, end: int) -> dict:
    return {
        "start": start,
        "end": end,
        "role": None,
        "state": "UNKNOWN",
        "basis": {"type": "NO_ASSERTION", "reference": None},
        "actor": {"type": "SYSTEM", "reference": "INTAKE-PRODUCT-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": None,
    }


def _ingest(project: str, text: str, declarations: list[dict], name: str = "source.txt") -> dict:
    return ingest.ingest_explicit_materials(
        project,
        source_name=name,
        raw_bytes=text.encode("utf-8"),
        encoding="utf-8",
        declarations=declarations,
    )


def _validate_product_records(report: dict) -> None:
    for index, record in enumerate(report["material_units"]):
        validate_record(record, f"product_records[{index}]")


def _assert_source_integrity(report: dict, text: str) -> None:
    source = report["source"]
    raw = base64.b64decode(source["original_bytes_base64"], validate=True)
    assert raw == text.encode("utf-8")
    assert source["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert raw.decode(source["encoding"]) == source["decoded_text"] == text
    spans = sorted(
        (record["source_ref"]["start"], record["source_ref"]["end"])
        for record in report["material_units"]
    )
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    assert all(left[1] == right[0] for left, right in zip(spans, spans[1:]))
    for record in report["material_units"]:
        ref = record["source_ref"]
        value = text[ref["start"] : ref["end"]]
        assert hashlib.sha256(value.encode("utf-8")).hexdigest() == ref["slice_sha256"]


def test_pi_01_explicit_intro_only_stays_in_c10_and_never_reaches_c1_or_m3(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pi-01")
    text = "作品简介：她重生后守住了家族旧宅。\n"
    report = _ingest("pi-01", text, [_confirmed(0, len(text), "INTRO", "PI-01")])

    _validate_product_records(report)
    _assert_source_integrity(report, text)
    assert len(store.intake_material_units("pi-01")) == 1
    assert report["chapters"] == store.chapters("pi-01") == []
    assert store.intake_c1_projections("pi-01") == []
    assert report["api_calls"] == report["automatic_retries"] == 0


def test_pi_02_mixed_intro_and_chapter_share_source_but_only_chapter_reaches_m3(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pi-02")
    intro = "作品简介：她重生后守住了家族旧宅。\n\n"
    chapter = "第一章 雨夜\n沈砚推门走进内库。\n"
    text = intro + chapter
    report = _ingest(
        "pi-02",
        text,
        [
            _confirmed(0, len(intro), "INTRO", "PI-02-I"),
            _confirmed(len(intro), len(text), "CHAPTER", "PI-02-C"),
        ],
    )

    _validate_product_records(report)
    _assert_source_integrity(report, text)
    assert len(report["material_units"]) == 2
    assert len({item["source_ref"]["source_sha256"] for item in report["material_units"]}) == 1
    assert len(report["chapters"]) == 1
    assert intro not in report["chapters"][0]["text"]
    segments, admission = product_cli.prepare_m3_segments(report["chapters"][0], CFG)
    assert admission["status"] == "READY"
    assert segments
    assert intro not in "".join(item["text"] for item in segments)
    assert "沈砚推门走进内库" in "".join(item["text"] for item in segments)


def test_pi_03_intro_plus_multi_chapter_keeps_prod_02_split_and_admission(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pi-03")
    intro = "作品简介：两个人在旧城追查失踪案。\n\n"
    manuscript = "第一章 雨夜\n沈砚推门。\n第二章 清晨\n他带着印册离开。\n"
    text = intro + manuscript
    report = _ingest(
        "pi-03",
        text,
        [
            _confirmed(0, len(intro), "INTRO", "PI-03-I"),
            _confirmed(len(intro), len(text), "CHAPTER", "PI-03-C"),
        ],
    )

    _assert_source_integrity(report, text)
    assert len(report["chapters"]) == 2
    assert [item["title"] for item in report["chapters"]] == ["第一章 雨夜", "第二章 清晨"]
    for chapter in report["chapters"]:
        segments, admission = product_cli.prepare_m3_segments(chapter, CFG)
        assert admission["status"] == "READY"
        assert segments
        assert intro not in "".join(item["text"] for item in segments)


def test_pi_04_candidate_intro_does_not_impersonate_confirmed_or_emit_c1(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pi-04")
    text = "她站在门前，回头看了一眼。\n"
    report = _ingest("pi-04", text, [_candidate_intro(0, len(text))])
    current = report["material_units"][0]["identity_revisions"][-1]

    _validate_product_records(report)
    assert current["state"] == "CANDIDATE"
    assert current["role"] == "INTRO"
    assert report["chapters"] == []
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is False


def test_pi_05_unknown_never_defaults_to_chapter(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "pi-05")
    text = "未标身份的材料。\n"
    report = _ingest("pi-05", text, [_unknown(0, len(text))])
    current = report["material_units"][0]["identity_revisions"][-1]

    _validate_product_records(report)
    assert current["state"] == "UNKNOWN"
    assert current["role"] is None
    assert report["chapters"] == []
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is False


def test_pi_06_confirmed_chapter_positive_control_reaches_c1_and_admission(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pi-06")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    report = _ingest("pi-06", text, [_confirmed(0, len(text), "CHAPTER", "PI-06")])

    assert len(report["chapters"]) == 1
    assert intake_identity.current_c1_eligibility(report["material_units"][0]) is True
    segments, admission = product_cli.prepare_m3_segments(report["chapters"][0], CFG)
    assert admission["status"] == "READY"
    assert segments


def test_pi_07_revision_appends_history_and_recomputes_current_eligibility(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pi-07")
    text = "第一章 雨夜\n沈砚推门走进内库。\n"
    initial = _ingest(
        "pi-07", text, [_confirmed(0, len(text), "INTRO", "PI-07-R1")]
    )
    unit_id = initial["material_units"][0]["material_unit_id"]
    assert store.chapters("pi-07") == []
    assert intake_identity.current_c1_eligibility(initial["material_units"][0]) is False

    revised = intake_identity.append_identity_revision(
        "pi-07",
        unit_id,
        role="CHAPTER",
        state="CONFIRMED",
        basis={"type": "USER_DECLARATION", "reference": "UI-PI-07-R2"},
        actor={"type": "USER", "reference": "USER-PRODUCT-TEST"},
        recorded_at="2026-08-17T12:01:00+08:00",
        reason="用户改判为章节书稿",
    )
    validate_record(revised)
    assert [item["revision_no"] for item in revised["identity_revisions"]] == [1, 2]
    assert revised["identity_revisions"][0]["role"] == "INTRO"
    assert intake_identity.current_c1_eligibility(revised) is True

    projection = intake_identity.project_material_units_to_c1("pi-07", [unit_id])
    assert len(projection["chapters"]) == 1
    duplicate = intake_identity.project_material_units_to_c1("pi-07", [unit_id])
    assert duplicate["chapters"] == []
    assert len(store.chapters("pi-07")) == 1


def test_pi_08_real_product_path_sends_only_confirmed_chapter_to_fake_m3(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "pi-08")
    intro = "作品简介：旧城里没人敢提那场火。\n\n"
    chapter = "第一章 灰烬\n沈砚从灰里捡起半枚铜扣。\n"
    text = intro + chapter
    report = _ingest(
        "pi-08",
        text,
        [
            _confirmed(0, len(intro), "INTRO", "PI-08-I"),
            _confirmed(len(intro), len(text), "CHAPTER", "PI-08-C"),
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
    product_cli.cmd_extract(SimpleNamespace(project="pi-08", chapter=None, redo=False))

    assert fake_m3_calls
    assert intro not in "".join(fake_m3_calls)
    assert "沈砚从灰里捡起半枚铜扣" in "".join(fake_m3_calls)


def test_negative_gap_is_not_silently_defaulted_to_chapter(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "negative-gap")
    text = "简介区。未声明区。"
    with pytest.raises(ValueError, match="缺口|未覆盖"):
        _ingest(
            "negative-gap",
            text,
            [_confirmed(0, 4, "INTRO", "NEGATIVE-GAP")],
        )
    assert store.intake_sources("negative-gap") == []
    assert store.intake_material_units("negative-gap") == []
    assert store.chapters("negative-gap") == []


def test_negative_model_cannot_write_confirmed_intro(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "negative-model")
    text = "疑似简介。"
    declaration = _confirmed(0, len(text), "INTRO", "NEGATIVE-MODEL")
    declaration["actor"] = {"type": "MODEL", "reference": "MODEL-NOT-AUTHORITY"}
    with pytest.raises(ValueError, match="actor.type"):
        _ingest("negative-model", text, [declaration])
    assert store.intake_material_units("negative-model") == []


def test_legacy_c1_is_not_backfilled_with_c10_identity(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "legacy")
    store.add_chapter("legacy", "旧章节", "旧项目正文。", "draft")
    assert len(store.chapters("legacy")) == 1
    assert store.intake_sources("legacy") == []
    assert store.intake_material_units("legacy") == []
    assert store.intake_c1_projections("legacy") == []
