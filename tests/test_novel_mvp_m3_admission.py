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
FIXTURE_ROOT = ROOT / "tests/fixtures/novel_mvp/intake_regressions"
MANIFEST_PATH = FIXTURE_ROOT / "m3_admission_manifest.json"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    import cli as product_cli
    from mvp import admission, ingest, store
finally:
    sys.path.pop(0)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lock() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _fixture_path(relative_path: str) -> Path:
    relative = Path(relative_path)
    assert not relative.is_absolute()
    assert ".." not in relative.parts
    path = (FIXTURE_ROOT / relative).resolve()
    assert path.is_relative_to(FIXTURE_ROOT.resolve())
    return path


def _fixture(entry: dict) -> Path:
    path = _fixture_path(entry["path"])
    assert _sha256(path) == entry["sha256"]
    return path


def _expected_ref(item: dict) -> tuple[int, int, str]:
    ref = item.get("source_ref", item)
    return ref["start"], ref["end"], item["text_sha256"]


def _contains_expected(segment: dict, expected: dict, source_text: str) -> bool:
    start, end, text_sha = _expected_ref(expected)
    ref = segment["source_ref"]
    return (
        ref["start"] <= start
        and ref["end"] >= end
        and hashlib.sha256(source_text[start:end].encode("utf-8")).hexdigest() == text_sha
    )


def _all_expected_in(expected: list[dict], segments: list[dict], source_text: str) -> bool:
    return all(
        any(_contains_expected(segment, item, source_text) for segment in segments)
        for item in expected
    )


def _overlap(left: dict, right: dict) -> bool:
    a = left["source_ref"]
    b = right["source_ref"]
    return a["start"] < b["end"] and b["start"] < a["end"]


@pytest.mark.parametrize("case", _lock()["cases"], ids=lambda item: item["case_id"])
def test_frozen_rm06_cases_match_product_admission(case: dict) -> None:
    source_path = _fixture_path(case["input_path"])
    assert _sha256(source_path) == case["input_sha256"]
    source_text = source_path.read_text(encoding="utf-8")
    chapter = {
        "id": "c01",
        "title": source_path.stem,
        "kind": "draft",
        "text": source_text,
        "added_at": "frozen-test",
    }
    before = copy.deepcopy(chapter)

    result = admission.apply_pre_m3_admission(chapter)

    assert chapter == before
    assert result["status"] == case["expected_status"]
    assert result["api_calls"] == 0
    assert result["automatic_retries"] == 0
    assert result["source"]["chapter_id"] == "c01"
    assert result["source"]["coordinate_basis"] == "c1_text"
    assert result["source"]["text_sha256"] == hashlib.sha256(source_text.encode()).hexdigest()

    coverage = result["coverage_segments"]
    assert "".join(segment["text"] for segment in coverage) == source_text
    assert coverage[0]["source_ref"]["start"] == 0
    assert coverage[-1]["source_ref"]["end"] == len(source_text)
    assert all(
        left["source_ref"]["end"] == right["source_ref"]["start"]
        for left, right in zip(coverage, coverage[1:])
    )
    assert all(
        source_text[segment["source_ref"]["start"] : segment["source_ref"]["end"]]
        == segment["text"]
        for segment in coverage
    )

    expected = case["expected_segments"]
    assert _all_expected_in(expected.get("story", []), result["candidate_story_segments"], source_text)
    assert _all_expected_in(
        expected.get("author_note", []), result["isolated_author_note_segments"], source_text
    )
    assert _all_expected_in(
        expected.get("uncertain", []), result["uncertain_segments"], source_text
    )

    if case["expected_status"] == "READY":
        assert _all_expected_in(expected.get("story", []), result["m3_eligible_targets"], source_text)
    else:
        assert result["m3_eligible_targets"] == []

    protected = [*result["isolated_author_note_segments"], *result["uncertain_segments"]]
    assert not any(
        _overlap(target, blocked)
        for target in result["m3_eligible_targets"]
        for blocked in protected
    )


def _run_cmd_extract_without_api(monkeypatch, chapter: dict) -> tuple[list[dict], list[dict]]:
    extracted_segments: list[dict] = []
    stored_candidates: list[dict] = []

    monkeypatch.setattr(product_cli.store, "chapters", lambda project: [chapter])
    monkeypatch.setattr(product_cli.store, "facts", lambda project: [])
    monkeypatch.setattr(
        product_cli.ex,
        "load_config",
        lambda: {
            "model_id": "NO_API_TEST_DOUBLE",
            "seg_min_chars": 620,
            "seg_max_chars": 923,
            "halo_chars": 180,
        },
    )

    def fake_extract(segment: dict, cfg: dict) -> list[dict]:
        extracted_segments.append(copy.deepcopy(segment))
        return []

    def fake_store(project: str, chapter_id: str, items: list[dict], source: str) -> int:
        stored_candidates.extend(copy.deepcopy(items))
        return len(items)

    monkeypatch.setattr(product_cli.ex, "extract_segment", fake_extract)
    monkeypatch.setattr(product_cli.store, "add_fact_candidates", fake_store)
    product_cli.cmd_extract(
        SimpleNamespace(project="readonly-product-test", chapter=None, redo=False)
    )
    return extracted_segments, stored_candidates


def test_cmd_extract_consumes_admitted_targets_without_api(monkeypatch) -> None:
    case = _lock()["cases"][0]
    source_path = _fixture_path(case["input_path"])
    source_text = source_path.read_text(encoding="utf-8")
    note = case["expected_segments"]["author_note"][0]
    note_start, note_end, _ = _expected_ref(note)
    author_note = source_text[note_start:note_end]
    chapter = {
        "id": "c01",
        "title": source_path.stem,
        "kind": "draft",
        "text": source_text,
        "added_at": "frozen-test",
    }

    extracted, stored = _run_cmd_extract_without_api(monkeypatch, chapter)

    assert extracted
    assert stored == []
    assert all(author_note not in segment["text"] for segment in extracted)
    admission_result = admission.apply_pre_m3_admission(chapter)
    expected_story = case["expected_segments"]["story"]
    assert _all_expected_in(expected_story, admission_result["m3_eligible_targets"], source_text)


def test_cmd_extract_holds_uncertain_case_without_api(monkeypatch) -> None:
    case = _lock()["cases"][-1]
    source_path = _fixture_path(case["input_path"])
    chapter = {
        "id": "c01",
        "title": source_path.stem,
        "kind": "draft",
        "text": source_path.read_text(encoding="utf-8"),
        "added_at": "frozen-test",
    }

    extracted, stored = _run_cmd_extract_without_api(monkeypatch, chapter)

    assert extracted == []
    assert stored == []


def test_admission_does_not_migrate_s1a_or_dht05() -> None:
    auxiliary = _lock()["auxiliary_texts"]
    s1a_fixture = _fixture(auxiliary["standalone_narrative_section"])
    s1a_text = s1a_fixture.read_text(encoding="utf-8")
    s1a_c1 = {"id": "c01", "title": s1a_fixture.stem, "kind": "draft", "text": s1a_text}
    s1a_result = admission.apply_pre_m3_admission(s1a_c1)
    assert any("第七节课终于结束了。" in item["text"] for item in s1a_result["m3_eligible_targets"])

    dht05 = _fixture(auxiliary["body_between_double_headings"])
    dht05_text = dht05.read_text(encoding="utf-8")
    dht05_c1 = {"id": "c01", "title": dht05.stem, "kind": "draft", "text": dht05_text}
    dht05_result = admission.apply_pre_m3_admission(dht05_c1)
    assert any(
        "第二章的正文已经开始。" in item["text"]
        for item in dht05_result["m3_eligible_targets"]
    )


def _c1(text: str, *, kind: str = "draft", chapter_id: str = "c01") -> dict:
    return {
        "id": chapter_id,
        "title": f"{chapter_id}-{kind}",
        "kind": kind,
        "text": text,
        "added_at": "frozen-test",
    }


def _assert_explicit_outline_excluded(chapter: dict) -> dict:
    before = copy.deepcopy(chapter)
    result = admission.apply_pre_m3_admission(chapter)

    assert chapter == before
    assert result["status"] == admission.EXPLICIT_OUTLINE_STATUS
    assert result["m3_eligible_targets"] == []
    assert result["candidate_story_segments"] == []
    assert result["api_calls"] == 0
    assert result["automatic_retries"] == 0
    assert result["blocks"] == [
        {
            "type": "explicit_outline_not_m3_eligible",
            "detail": "C1 kind=outline，由显式材料身份确定，不进入 M3",
        }
    ]
    assert "".join(item["text"] for item in result["coverage_segments"]) == chapter["text"]
    assert result["excluded_outline_segments"] == result["coverage_segments"]
    assert result["source"]["coordinate_basis"] == "c1_text"
    assert result["source"]["text_sha256"] == hashlib.sha256(
        chapter["text"].encode("utf-8")
    ).hexdigest()
    return result


def test_ol_01_explicit_outline_is_preserved_but_not_m3_eligible() -> None:
    source_path = _fixture(_lock()["auxiliary_texts"]["explicit_outline"])
    _assert_explicit_outline_excluded(_c1(source_path.read_text(encoding="utf-8"), kind="outline"))


def test_ol_02_outline_and_manuscript_have_independent_admission() -> None:
    outline = _c1("第三章计划：主角将在雨夜取走印册。", kind="outline", chapter_id="c01")
    manuscript = _c1("第三章 雨夜\n沈砚推门走进内库。", chapter_id="c02")

    _assert_explicit_outline_excluded(outline)
    manuscript_result = admission.apply_pre_m3_admission(manuscript)

    assert manuscript_result["status"] == "READY"
    assert "".join(item["text"] for item in manuscript_result["m3_eligible_targets"]) == manuscript["text"]


def test_ol_03_multi_chapter_manuscript_does_not_bypass_outline_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "data")
    store.init_project("ol-03")
    outline_path = tmp_path / "outline.txt"
    manuscript_path = tmp_path / "manuscript.txt"
    outline_text = "全书大纲\n第三章让主角进入内库。"
    manuscript_text = "第一章 雨夜\n沈砚推门。\n第二章 清晨\n他带着印册离开。"
    outline_path.write_text(outline_text, encoding="utf-8")
    manuscript_path.write_text(manuscript_text, encoding="utf-8")

    outline_report = ingest.ingest_files("ol-03", [str(outline_path)], kind="outline")
    manuscript_report = ingest.ingest_files(
        "ol-03",
        [str(manuscript_path)],
        kind="draft",
        material_role="CHAPTER",
    )
    chapters = store.chapters("ol-03")

    assert outline_report["count"] == 1
    assert manuscript_report["count"] == 2
    assert [chapter["kind"] for chapter in chapters] == ["outline", "draft", "draft"]
    assert chapters[0]["text"] == outline_text
    assert admission.apply_pre_m3_admission(chapters[0])["m3_eligible_targets"] == []
    assert all(
        admission.apply_pre_m3_admission(chapter)["status"] == "READY"
        for chapter in chapters[1:]
    )


def test_ol_04_manuscript_word_outline_is_not_a_classifier() -> None:
    chapter = _c1("他拿起桌上的大纲看了一眼，又把它压回书堆底下。")
    result = admission.apply_pre_m3_admission(chapter)

    assert result["status"] == "READY"
    assert "大纲" in result["m3_eligible_targets"][0]["text"]


def test_ol_05_outline_style_manuscript_is_not_false_killed() -> None:
    chapter = _c1("人物动作：抬头。\n地点：旧仓库。\n时间：凌晨。\n对话：‘你来了。’")
    result = admission.apply_pre_m3_admission(chapter)

    assert result["status"] == "READY"
    assert "".join(item["text"] for item in result["m3_eligible_targets"]) == chapter["text"]


def test_ol_06_ambiguous_outline_like_draft_keeps_existing_behavior() -> None:
    chapter = _c1("下一章主角要去码头，伏笔暂时不解释。")
    result = admission.apply_pre_m3_admission(chapter)

    assert result["status"] == "READY"
    assert result["excluded_outline_segments"] == []
    assert result["m3_eligible_targets"]


def test_ol_07_frozen_rm06_regression_is_still_seven_of_seven() -> None:
    cases = _lock()["cases"]
    assert len(cases) == 7
    for case in cases:
        source_path = _fixture_path(case["input_path"])
        chapter = _c1(source_path.read_text(encoding="utf-8"))
        result = admission.apply_pre_m3_admission(chapter)
        assert result["status"] == case["expected_status"]
        assert result["m3_eligible_targets"] == [] or _all_expected_in(
            case["expected_segments"].get("story", []),
            result["m3_eligible_targets"],
            chapter["text"],
        )


def test_ol_08_real_extract_path_excludes_outline_and_keeps_manuscript(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "data")
    store.init_project("ol-08")
    outline_path = tmp_path / "outline.txt"
    manuscript_path = tmp_path / "chapter.txt"
    outline_text = "大纲原稿\n第二章安排主角发现钥匙。"
    manuscript_text = "第一章 钥匙\n沈砚在门槛下摸到一把铜钥匙。"
    outline_path.write_text(outline_text, encoding="utf-8")
    manuscript_path.write_text(manuscript_text, encoding="utf-8")
    ingest.ingest_files("ol-08", [str(outline_path)], kind="outline")
    ingest.ingest_files(
        "ol-08",
        [str(manuscript_path)],
        kind="draft",
        material_role="CHAPTER",
    )
    chapters = store.chapters("ol-08")

    outline_segments, outline_receipt = product_cli.prepare_m3_segments(
        chapters[0],
        {"seg_min_chars": 620, "seg_max_chars": 923, "halo_chars": 180},
    )
    assert outline_segments == []
    assert outline_receipt["status"] == admission.EXPLICIT_OUTLINE_STATUS

    extracted: list[str] = []
    monkeypatch.setattr(
        product_cli.ex,
        "load_config",
        lambda: {
            "model_id": "NO_API_TEST_DOUBLE",
            "seg_min_chars": 620,
            "seg_max_chars": 923,
            "halo_chars": 180,
        },
    )
    monkeypatch.setattr(
        product_cli.ex,
        "extract_segment",
        lambda segment, cfg: extracted.append(segment["text"]) or [],
    )
    product_cli.cmd_extract(SimpleNamespace(project="ol-08", chapter=None, redo=False))

    assert extracted
    assert outline_text not in "\n".join(extracted)
    assert chapters[1]["text"] in "\n".join(extracted)

    calls_before_outline_refine = len(extracted)
    with pytest.raises(SystemExit, match="NOT_M3_ELIGIBLE__EXPLICIT_OUTLINE"):
        product_cli.cmd_refine(
            SimpleNamespace(
                project="ol-08",
                chapter=chapters[0]["id"],
                stages="anchor",
                fresh=True,
            )
        )
    assert len(extracted) == calls_before_outline_refine

    monkeypatch.setattr(product_cli.refine, "run_pipeline", lambda *args, **kwargs: {})
    monkeypatch.setattr(product_cli.refine, "format_receipt", lambda report: "NO_API_TEST")
    product_cli.cmd_refine(
        SimpleNamespace(
            project="ol-08",
            chapter=chapters[1]["id"],
            stages="anchor",
            fresh=True,
        )
    )
    assert len(extracted) > calls_before_outline_refine


def test_direct_candidate_import_reuses_admission_and_cannot_target_outline(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "data")
    store.init_project("direct-candidates")
    outline = store.add_chapter(
        "direct-candidates",
        "大纲",
        "第二章安排主角发现钥匙。",
        "outline",
    )
    chapter = store.add_chapter(
        "direct-candidates",
        "第一章",
        "沈砚在门槛下摸到一把铜钥匙。",
        "draft",
    )
    payload = tmp_path / "candidates.json"
    payload.write_text(
        json.dumps(
            [{"text": "沈砚找到铜钥匙。", "quote": "摸到一把铜钥匙"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Pre-M3 准入未放行"):
        product_cli.cmd_candidates(
            SimpleNamespace(
                project="direct-candidates",
                chapter=outline["id"],
                json_file=str(payload),
            )
        )
    assert store.facts("direct-candidates") == []

    product_cli.cmd_candidates(
        SimpleNamespace(
            project="direct-candidates",
            chapter=chapter["id"],
            json_file=str(payload),
        )
    )
    assert len(store.facts("direct-candidates")) == 1
