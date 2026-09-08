"""Mapped extraction through the existing C1/M2/M3/M4 workspace transaction."""

import copy
import hashlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "novel-mvp"))
try:
    from mvp import (
        chapter_workspace, extract_tool, extract_workspace, fact_tool,
        fact_workspace, factstore, segment_tool, segment_workspace,
    )
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)


RAW = "\u3000\u3000甲推开门。\r\n\r\n\u3000\u3000乙点亮灯。\r\n"


def chapter(text=RAW, chapter_id="c01"):
    return {
        "contract": "C1_CHAPTER_DOC", "version": "v1", "id": chapter_id,
        "title": "第一章", "kind": "draft", "text": text,
        "added_at": "2026-09-08 12:00:00",
        "chapter_revision_ref": {"chapter_id": chapter_id, "revision_no": 1,
                                 "revision_text_sha256": hashlib.sha256(text.encode()).hexdigest()},
    }


def prepare(tmp_path, *, raw_quote=False):
    ws = WorkspaceRouter(tmp_path / "runtime").create_project("auth:map-test", "映射")
    c1 = chapter()
    chapter_workspace.persist_c1_current_views(
        ws, "op-chapters", [c1], [c1["chapter_revision_ref"]],
        {"chapters": 0, "chapter_index": 0},
    )
    segment_workspace.persist_current_mapped_segments(ws, "op-segments", 20, 100, 10, 0)
    c2 = segment_workspace.read_current_segments(ws)["items"]
    responses = {extract_tool.item_key(s): {
        "data": {"facts": [{"text": "甲开门，乙点灯。",
                            "quote": RAW.strip() if raw_quote else s["text"]}]},
        "usage": {}, "model": "offline-synthetic",
    } for s in c2}
    return ws, c1, c2, responses


def inventory(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("raw_quote", [False, True])
def test_cross_paragraph_to_persisted_extracted_and_exact_original(tmp_path, raw_quote):
    ws, c1, c2, responses = prepare(tmp_path, raw_quote=raw_quote)
    extract_workspace.persist_current_fact_candidates(ws, "op-extract", responses, 0)
    c3 = extract_workspace.read_current_fact_candidates(ws)["items"]
    assert c3[0]["quote"] == responses[extract_tool.item_key(c2[0])]["data"]["facts"][0]["quote"]
    receipt = fact_workspace.materialize_current_extracted_snapshot(
        ws, operation_id="op-facts", source="offline-synthetic", added_at="2026-09-08 12:01:00",
    )
    assert receipt["status"] == "COMMITTED"
    facts = ws.read("facts")["payload"]
    assert len(facts) == 1
    fact = facts[0]
    anchor = fact["anchor_ref"]
    assert fact["status"] == "extracted"
    assert fact["text_map_evidence"] == c3[0]["text_map_evidence"]
    assert fact["quote"] == c1["text"][anchor["start"]:anchor["end"]] == RAW.strip()
    assert hashlib.sha256(fact["quote"].encode()).hexdigest() == anchor["slice_sha256"]
    assert ws.read("chapters")["payload"] == [c1]
    assert factstore.validate_c4_v1_snapshot(facts) == facts
    fact_workspace.read_current_snapshot(ws)
    before = inventory(tmp_path / "runtime")
    assert fact_workspace.materialize_current_extracted_snapshot(
        ws, operation_id="op-facts", source="offline-synthetic", added_at="2026-09-08 12:01:00",
    )["replayed"] is True
    assert inventory(tmp_path / "runtime") == before


@pytest.mark.parametrize("bad_quote", ["甲推开门。乙点亮灯。", "甲 推开门。\n乙点亮灯。", "窗外下雨。", ""])
def test_bad_quote_never_writes_partial_c3(tmp_path, bad_quote):
    ws, _c1, c2, responses = prepare(tmp_path)
    responses[extract_tool.item_key(c2[0])]["data"]["facts"][0]["quote"] = bad_quote
    before = inventory(tmp_path / "runtime")
    with pytest.raises(extract_workspace.ExtractWorkspaceError):
        extract_workspace.persist_current_fact_candidates(ws, "op-extract", responses, 0)
    assert inventory(tmp_path / "runtime") == before
    assert ws.read("fact_candidates") is None


@pytest.mark.parametrize("field,value", [
    ("original_start", 0), ("original_slice_sha256", "0" * 64),
    ("quote_original", "假引文"), ("char_map", []),
])
def test_m4_rejects_forged_evidence_before_any_fact_write(tmp_path, field, value):
    ws, c1, c2, responses = prepare(tmp_path)
    c3 = extract_tool.execute(
        {"items": c2, "current_chapter_revision_refs": [c1["chapter_revision_ref"]]},
        extract_tool.offline_response_provider(responses),
    )["items"]
    c3[0]["text_map_evidence"][field] = value
    before = inventory(tmp_path / "runtime")
    with pytest.raises(factstore.FactstoreError):
        fact_tool.execute({"chapter": c1, "segments": c2, "candidates": c3,
                           "source": "synthetic", "added_at": "now"})
    assert inventory(tmp_path / "runtime") == before


def test_m4_source_change_before_commit_is_zero_write(tmp_path, monkeypatch):
    ws, _c1, _c2, responses = prepare(tmp_path)
    extract_workspace.persist_current_fact_candidates(ws, "op-extract", responses, 0)
    before = inventory(tmp_path / "runtime")
    real_read = fact_workspace._read_current_upstream
    calls = 0

    def changed(workspace):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise fact_workspace.FactWorkspaceError("SYNTHETIC_SOURCE_CHANGED")
        return real_read(workspace)

    monkeypatch.setattr(fact_workspace, "_read_current_upstream", changed)
    with pytest.raises(fact_workspace.FactWorkspaceSourceChangedError):
        fact_workspace.materialize_current_extracted_snapshot(
            ws, operation_id="op-facts", source="synthetic", added_at="now",
        )
    assert inventory(tmp_path / "runtime") == before


def test_render_validates_mapping_and_rejects_unknown_extension():
    request = {"items": [chapter()], "options": {
        "seg_min_chars": 20, "seg_max_chars": 100, "halo_chars": 10, "text_mapping": True,
    }}
    result = segment_tool.execute(request)
    segment_tool.validate_render_request({"source_request": request, "c2_result": result})
    bad = copy.deepcopy(result)
    bad["items"][0]["text_map"]["char_map"][0] = 0
    with pytest.raises(segment_tool.SegmentToolError):
        segment_tool.validate_render_request({"source_request": request, "c2_result": bad})


def test_mapped_runtime_rejects_halo_and_stale_revision():
    c1 = chapter('甲推开门。\n乙点亮灯。\n丙关上窗。')
    c2 = segment_tool.execute({'items': [c1], 'options': {
        'seg_min_chars': 4, 'seg_max_chars': 8, 'halo_chars': 20,
        'text_mapping': True,
    }})['items']
    assert len(c2) == 3 and '乙点亮灯。' in c2[0]['halo_after']
    response = {'data': {'facts': [{'text': '乙点灯。', 'quote': '乙点亮灯。'}]},
                'usage': {}, 'model': 'synthetic'}
    with pytest.raises(RuntimeError, match='QUOTE_OUTSIDE_RESPONSIBILITY'):
        extract_tool.execute(
            {'items': c2, 'current_chapter_revision_refs': [c1['chapter_revision_ref']]},
            extract_tool.offline_response_provider({extract_tool.item_key(s): response for s in c2}),
        )
    stale = copy.deepcopy(c1['chapter_revision_ref'])
    stale['revision_no'] += 1
    with pytest.raises(RuntimeError, match='REVISION'):
        extract_tool.execute(
            {'items': c2, 'current_chapter_revision_refs': [stale]},
            extract_tool.offline_response_provider({extract_tool.item_key(s): response for s in c2}),
        )


def test_c4_origin_proof_is_immutable_when_current_anchor_advances(tmp_path):
    ws, c1, _c2, responses = prepare(tmp_path)
    extract_workspace.persist_current_fact_candidates(ws, 'extract', responses, 0)
    fact_workspace.materialize_current_extracted_snapshot(
        ws, operation_id='facts', source='synthetic', added_at='now',
    )
    facts = ws.read('facts')['payload']
    origin = copy.deepcopy(facts[0]['text_map_evidence'])
    prefix = '前言。\n'
    current_text = prefix + c1['text']
    new_ref = {**c1['chapter_revision_ref'], 'revision_no': 2,
               'revision_text_sha256': hashlib.sha256(current_text.encode()).hexdigest()}
    facts[0]['chapter_revision_ref'] = new_ref
    facts[0]['anchor_ref'].update(new_ref)
    facts[0]['anchor_ref']['start'] += len(prefix)
    facts[0]['anchor_ref']['end'] += len(prefix)
    checked = factstore.validate_c4_v1_snapshot(facts)
    assert checked[0]['text_map_evidence'] == origin
    anchor = checked[0]['anchor_ref']
    assert current_text[anchor['start']:anchor['end']] == checked[0]['quote']
    checked[0]['text_map_evidence']['original_slice'] = '伪造来源'
    with pytest.raises(factstore.FactstoreError):
        factstore.validate_c4_v1_snapshot(checked)


@pytest.mark.parametrize("tamper", [
    "seg", "missing_seg", "origin_anchor", "same_revision_other_sha", "origin_newer",
])
def test_c4_reader_rejects_origin_provenance_tampering(tmp_path, tamper):
    ws, _c1, _c2, responses = prepare(tmp_path)
    extract_workspace.persist_current_fact_candidates(ws, 'extract', responses, 0)
    fact_workspace.materialize_current_extracted_snapshot(
        ws, operation_id='facts', source='synthetic', added_at='now',
    )
    facts = ws.read('facts')['payload']
    if tamper == 'seg':
        facts[0]['seg'] += 1
    elif tamper == 'missing_seg':
        facts[0].pop('seg')
    elif tamper == 'same_revision_other_sha':
        facts[0]['chapter_revision_ref']['revision_text_sha256'] = '0' * 64
        facts[0]['anchor_ref']['revision_text_sha256'] = '0' * 64
    elif tamper == 'origin_newer':
        facts[0]['text_map_evidence']['chapter_revision_ref']['revision_no'] += 1
    else:
        facts[0]['anchor_ref']['start'] += 1
        facts[0]['anchor_ref']['end'] += 1
    with pytest.raises(factstore.FactstoreError, match='C4_TEXT_MAP_ORIGIN'):
        factstore.validate_c4_v1_snapshot(facts)
