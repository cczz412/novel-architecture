"""Explicit v2 provenance, immutable storage, and strict downstream handshake."""
import copy
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "novel-mvp"))
try:
    from mvp import (chapter_workspace, segment_workspace, extract_workspace,
                     extract_tool, extract, text_mapping, quote_recovery,
                     fact_workspace, factstore, check_tool, overview, review_workspace)
    from mvp.workspace import WorkspaceRouter
finally:
    sys.path.pop(0)

RAW = "甲推开门。\n乙点亮灯。"
QUOTE = "甲推开门。乙点亮灯。"


def setup(tmp_path, raw=RAW, quote=QUOTE, alias=False):
    c = {"contract": "C1_CHAPTER_DOC", "version": "v1", "id": "c01",
         "title": "合成章", "kind": "draft", "text": raw, "added_at": "now",
         "chapter_revision_ref": {"chapter_id": "c01", "revision_no": 1,
                                  "revision_text_sha256": hashlib.sha256(raw.encode()).hexdigest()}}
    ws = WorkspaceRouter(tmp_path / "ws").create_project("auth:v2", "合成")
    chapter_workspace.persist_c1_current_views(
        ws, "chapters", [c], [c["chapter_revision_ref"]], {"chapters": 0, "chapter_index": 0})
    segment_workspace.persist_current_mapped_segments(ws, "segments", 20, 100, 10, 0)
    segs = segment_workspace.read_current_segments(ws)["items"]
    responses = {extract_tool.item_key(seg): {"data": {"facts": [
        {"text：" if alias else "text": "甲开门，乙点灯。", "quote": quote}]},
        "usage": {}, "model": "synthetic-offline"} for seg in segs}
    return ws, c, segs, responses


def inventory(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


def persist(ws, responses):
    extract_workspace.persist_current_recovered_fact_candidates(ws, "extract", responses, 0)
    fact_workspace.materialize_current_extracted_snapshot(
        ws, operation_id="facts", source="offline", added_at="now")
    return ws.read("facts")["payload"]


@pytest.mark.parametrize("quote", [QUOTE, "甲推开门。 乙点亮灯。", RAW])
@pytest.mark.parametrize("alias", [False, True])
def test_v2_roundtrip_preserves_raw_items_and_old_default(tmp_path, quote, alias):
    ws, c, segs, responses = setup(tmp_path, quote=quote, alias=alias)
    before = inventory(tmp_path)
    raw_responses = copy.deepcopy(responses)
    if alias or quote != RAW:
        with pytest.raises(extract_workspace.ExtractWorkspaceError):
            extract_workspace.persist_current_fact_candidates(ws, "old", responses, 0)
        assert inventory(tmp_path) == before
    facts = persist(ws, responses)
    c3 = extract_workspace.read_current_fact_candidates(ws)["items"][0]
    f = facts[0]
    assert c3["quote"] == quote and f["quote"] == RAW
    assert f["text_map_evidence"] == c3["text_map_evidence"]
    evidence = f["text_map_evidence"]
    assert evidence["version"] == "v2" and evidence["quote_original"] == quote
    assert (evidence["recovery"] is None) == (quote == RAW)
    if alias:
        assert evidence["provider_adaptation"]["original_item"] == raw_responses[
            extract_tool.item_key(segs[0])]["data"]["facts"][0]
    assert responses == raw_responses and f["status"] == "extracted"
    anchor = f["anchor_ref"]
    assert c["text"][anchor["start"]:anchor["end"]] == f["quote"]
    assert hashlib.sha256(f["quote"].encode()).hexdigest() == anchor["slice_sha256"]
    fact_workspace.read_current_snapshot(ws)
    before = inventory(tmp_path)
    assert extract_workspace.persist_current_recovered_fact_candidates(
        ws, "extract", responses, 0)["replayed"]
    assert fact_workspace.materialize_current_extracted_snapshot(
        ws, operation_id="facts", source="offline", added_at="now")["replayed"]
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("quote", ["甲推开门，乙点亮灯。", "甲推门。乙点亮灯。", "甲推开门。丙点亮灯。",
                                   "甲 推开门。乙点亮灯。", "甲推开门。\t乙点亮灯。",
                                   "甲推开门。  乙点亮灯。", "甲推开门。　乙点亮灯。"])
def test_mixed_good_bad_batch_never_writes(tmp_path, quote):
    ws, _c, _segs, responses = setup(tmp_path, quote=quote)
    response = next(iter(responses.values()))
    response["data"]["facts"].insert(0, {"text": "甲开门。", "quote": "甲推开门。"})
    before = inventory(tmp_path)
    with pytest.raises(extract_workspace.ExtractWorkspaceError):
        extract_workspace.persist_current_recovered_fact_candidates(ws, "bad", responses, 0)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("raw,quote", [("甲。\n乙。\n甲。\n乙。", "甲。乙。"),
                                      ("甲。乙。\n甲。\n乙。", "甲。乙。"),
                                      ("甲 A。\n乙。", "甲A。乙。"),
                                      ("甲。\r\n乙。", "甲。乙。"),
                                      ("e\u0301。\n乙。", "é。乙。")])
def test_recovery_rejects_ambiguity_and_other_character_normalization(raw, quote):
    with pytest.raises(ValueError):
        quote_recovery.locate_source_lf(quote, raw)


def test_halo_wrong_revision_and_missing_opt_in_inputs(tmp_path):
    _ws, c, segs, responses = setup(tmp_path)
    s = copy.deepcopy(segs[0])
    s["end"] = len("甲推开门。")
    s["text"] = "甲推开门。"
    with pytest.raises(ValueError, match="OUTSIDE_RESPONSIBILITY"):
        text_mapping.build_evidence_v2(s, QUOTE, {"text": "事实", "quote": QUOTE})
    called = []
    bad_ref = {**c["chapter_revision_ref"], "revision_no": 2}
    with pytest.raises(RuntimeError):
        extract.extract_segment(segs[0], {}, current_chapter_revision_ref=bad_ref,
                                response_provider=lambda *a: called.append(a), text_map_version="v2")
    assert not called
    s = copy.deepcopy(segs[0])
    s.pop("text_map")
    with pytest.raises(extract_tool.ExtractToolError, match="REQUIRES_MAPPED"):
        extract_tool.execute({"items": [s], "current_chapter_revision_refs": [c["chapter_revision_ref"]],
                              "text_map_version": "v2"}, extract_tool.offline_response_provider(responses))


@pytest.mark.parametrize("mode", ["both", "unknown", "ascii_alias", "empty", "wrong_type"])
def test_field_adapter_is_exact_and_atomic(tmp_path, mode):
    ws, _c, _segs, responses = setup(tmp_path, alias=True)
    item = next(iter(responses.values()))["data"]["facts"][0]
    if mode == "both":
        item["text"] = "冲突"
    elif mode == "unknown":
        item["unknown"] = 1
    elif mode == "ascii_alias":
        item["text:"] = item.pop("text：")
    elif mode == "empty":
        item["text："] = ""
    else:
        item["text："] = 1
    before = inventory(tmp_path)
    with pytest.raises(extract_workspace.ExtractWorkspaceError):
        extract_workspace.persist_current_recovered_fact_candidates(ws, "bad", responses, 0)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("mode", ["original_quote", "recovered", "offset", "reason", "rule", "missing",
                                   "adapter_text", "adapter_quote", "source_missing", "source_type", "source_quote", "source_unknown", "source_keys", "extra"])
def test_forged_v2_evidence_rejected_before_save(tmp_path, mode):
    ws, _c, _segs, responses = setup(tmp_path, alias=True)
    facts = persist(ws, responses)
    e = facts[0]["text_map_evidence"]
    if mode == "original_quote":
        e["quote_original"] += "假"
    elif mode == "recovered":
        e["recovery"]["quote_recovered"] += "假"
    elif mode == "offset":
        e["recovery"]["changes"][0]["original_offset"] += 1
    elif mode == "reason":
        e["recovery"]["changes"][0]["reason"] = "SPACE_TO_SOURCE_LF"
    elif mode == "rule":
        e["recovery"]["rule"] = "ANY_WHITESPACE"
    elif mode == "missing":
        del e["recovery"]
    elif mode == "adapter_text":
        e["provider_adaptation"]["original_item"]["text："] += "假"
    elif mode == "adapter_quote":
        e["provider_adaptation"]["original_item"]["quote"] += "假"
    elif mode == "source_missing":
        del e["provider_item"]
    elif mode == "source_type":
        e["provider_item"]["text："] = 1
    elif mode == "source_quote":
        e["provider_item"]["quote"] += "假"
    elif mode == "source_unknown":
        e["provider_item"]["unknown"] = 1
    elif mode == "source_keys":
        e["provider_item"]["text"] = e["provider_item"]["text："]
    else:
        e["extra"] = 1
    before = inventory(tmp_path)
    with pytest.raises(factstore.FactstoreError):
        fact_workspace.save_snapshot(ws, operation_id="forged", snapshot=facts, expected_version=1)
    assert inventory(tmp_path) == before


def test_immutable_v2_cannot_be_downgraded_and_old_save_replays(tmp_path):
    ws, _c, segs, responses = setup(tmp_path)
    facts = persist(ws, responses)
    downgraded = copy.deepcopy(facts)
    downgraded[0]["text_map_evidence"] = text_mapping.build_evidence(segs[0], RAW)
    factstore.validate_c4_v1_snapshot(downgraded)
    before = inventory(tmp_path)
    with pytest.raises(fact_workspace.FactWorkspaceError, match="ORIGIN_IMMUTABLE"):
        fact_workspace.save_snapshot(ws, operation_id="downgrade", snapshot=downgraded, expected_version=1)
    assert inventory(tmp_path) == before
    args = dict(operation_id="save", snapshot=facts, expected_version=1)
    fact_workspace.save_snapshot(ws, **args)
    added = copy.deepcopy(facts)
    added.append({**copy.deepcopy(facts[0]), "id": "f9999"})
    fact_workspace.save_snapshot(ws, operation_id="added", snapshot=added, expected_version=2)
    before = inventory(tmp_path)
    assert fact_workspace.save_snapshot(ws, **args)["replayed"]
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("forged", [False, True])
def test_m7_m9_validate_v2_without_auto_confirmation(tmp_path, forged):
    ws, c, _segs, responses = setup(tmp_path)
    facts = persist(ws, responses)
    if forged:
        facts[0]["text_map_evidence"]["recovery"]["quote_recovered"] += "假"
    provider = check_tool.FrozenFindingProvider({
        "provider_id": "offline", "model_calls": 0, "response": {"findings": []}})
    report = check_tool.execute({"project": "synthetic", "generated_at": "now", "facts": facts,
                                "current_revision_refs": [c["chapter_revision_ref"]],
                                "check_config": {"scope_name": "test", "scope_kind": "leftover", "kinds": ["event"]}}, provider)
    assert report["scan"]["excluded_counts"]["invalid_evidence"] == int(forged)
    called = []
    with pytest.raises(overview.OverviewError, match="C4_TEXT_MAP_INVALID" if forged else "NO_CONFIRMED_FACTS"):
        overview.execute({"facts": facts, "current_revision_ref": c["chapter_revision_ref"],
                          "source_revision": "synthetic", "generated_at": "now"}, lambda r: called.append(r))
    assert not called and ws.read("facts")["payload"][0]["status"] == "extracted"


@pytest.mark.parametrize("alias", [False, True])
def test_adaptation_cannot_be_added_or_stripped_in_c3_c4_m7_m9(tmp_path, alias):
    ws, c, segs, responses = setup(tmp_path, alias=alias)
    facts = persist(ws, responses)
    c3 = extract_workspace.read_current_fact_candidates(ws)["items"][0]
    e = facts[0]["text_map_evidence"]
    original = copy.deepcopy(e["provider_item"])
    e["provider_adaptation"] = (None if alias else quote_recovery.adapt_provider_item(
        {"text：": facts[0]["text"], "quote": QUOTE})[1])
    assert e["provider_item"] == original
    c3["text_map_evidence"] = copy.deepcopy(e)
    with pytest.raises(ValueError, match="REPLAY_MISMATCH"):
        text_mapping.validate_candidate(c3, segs[0])
    with pytest.raises(factstore.FactstoreError, match="REPLAY_MISMATCH"):
        factstore.validate_c4_v1_snapshot(facts)
    before = inventory(tmp_path)
    with pytest.raises(factstore.FactstoreError):
        fact_workspace.save_snapshot(ws, operation_id="bad", snapshot=facts, expected_version=1)
    assert inventory(tmp_path) == before
    report = check_tool.execute({"project": "synthetic", "generated_at": "now", "facts": facts,
        "current_revision_refs": [c["chapter_revision_ref"]],
        "check_config": {"scope_name": "test", "scope_kind": "leftover", "kinds": ["event"]}},
        check_tool.FrozenFindingProvider({"provider_id": "offline", "model_calls": 0,
                                         "response": {"findings": []}}))
    assert report["scan"]["excluded_counts"]["invalid_evidence"] == 1
    called = []
    with pytest.raises(overview.OverviewError, match="C4_TEXT_MAP_INVALID"):
        overview.execute({"facts": facts, "current_revision_ref": c["chapter_revision_ref"],
                          "source_revision": "synthetic", "generated_at": "now"},
                         lambda r: called.append(r))
    assert not called


@pytest.mark.parametrize("alias", [False, True])
def test_source_item_binding_at_admission_and_immutability_after_storage(tmp_path, alias):
    ws, _c, segs, responses = setup(tmp_path, alias=alias)
    facts = persist(ws, responses)
    c3 = extract_workspace.read_current_fact_candidates(ws)["items"][0]
    assert c3["text_map_evidence"]["provider_item"] == next(iter(responses.values()))["data"]["facts"][0]
    c3["text"] = "篡改入账文字"
    with pytest.raises(ValueError, match="VALUE_MISMATCH"):
        text_mapping.validate_candidate(c3, segs[0])
    # Even coherently replacing both source and derived adaptation cannot change
    # an admitted origin. Stateless proof validation is not origin authority.
    e = facts[0]["text_map_evidence"]
    e["provider_item"] = {"text" if alias else "text：": facts[0]["text"], "quote": QUOTE}
    e["provider_adaptation"] = quote_recovery.adapt_provider_item(e["provider_item"])[1]
    factstore.validate_c4_v1_snapshot(facts)
    before = inventory(tmp_path)
    with pytest.raises(fact_workspace.FactWorkspaceError, match="ORIGIN_IMMUTABLE"):
        fact_workspace.save_snapshot(ws, operation_id="replace", snapshot=facts, expected_version=1)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("decision", ["edit", "edit_and_confirm"])
@pytest.mark.parametrize("alias", [False, True])
def test_m5_author_edit_preserves_source_and_reopens(tmp_path, decision, alias):
    ws, c, _segs, responses = setup(tmp_path, alias=alias)
    original = persist(ws, responses)[0]
    evidence = copy.deepcopy(original["text_map_evidence"])
    args = {"operation_id": "author-edit", "expected_facts_version": 1, "review_action": {
        "action": factstore.build_review_action(original, decision=decision,
            replacement_text="作者修正后的事实。", operation_id="author-edit"),
        "chapter_revision_ref": c["chapter_revision_ref"], "decided_at": "now"}}
    result = review_workspace.apply_review(ws, **args)
    updated = result["facts"][0]
    assert updated["text"] == "作者修正后的事实。"
    assert updated["status"] == ("confirmed" if decision == "edit_and_confirm" else "extracted")
    assert updated["text_map_evidence"] == evidence
    reopened = WorkspaceRouter(tmp_path / "ws").open_project("auth:v2", ws.project_id)
    fact_workspace.read_current_snapshot(reopened)
    assert reopened.read("facts")["payload"] == result["facts"]
    before = inventory(tmp_path)
    assert review_workspace.apply_review(reopened, **args)["replayed"]
    assert inventory(tmp_path) == before
    report = check_tool.execute({"project": "synthetic", "generated_at": "now", "facts": result["facts"],
        "current_revision_refs": [c["chapter_revision_ref"]],
        "check_config": {"scope_name": "test", "scope_kind": "leftover", "kinds": ["event"]}},
        check_tool.FrozenFindingProvider({"provider_id": "offline", "model_calls": 0,
                                         "response": {"findings": []}}))
    assert report["scan"]["excluded_counts"]["invalid_evidence"] == 0

    class ProviderReached(Exception):
        pass

    def probe_provider(request):
        raise ProviderReached()

    with pytest.raises(ProviderReached if decision == "edit_and_confirm" else overview.OverviewError,
                       match=None if decision == "edit_and_confirm" else "NO_CONFIRMED_FACTS"):
        overview.execute({"facts": result["facts"], "current_revision_ref": c["chapter_revision_ref"],
                          "source_revision": "synthetic", "generated_at": "now"}, probe_provider)
