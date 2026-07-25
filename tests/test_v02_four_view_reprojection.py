from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from tools import v02_four_view_reprojection as reprojection


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _nested_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(key)
            keys.extend(_nested_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_nested_keys(child))
    return keys


def test_inputs_are_byte_locked_and_d_w1_attachment_is_hash_only_mirror() -> None:
    inputs = reprojection.load_locked_inputs()
    for role, expected in reprojection.EXPECTED_INPUT_SHA256.items():
        assert reprojection.sha256_bytes(inputs["raw"][role]) == expected
    assert inputs["raw"]["d_sample"] == inputs["raw"]["d_w1_mirror"]

    manifest = reprojection.build_bundle
    assert callable(manifest)


def test_sha_drift_is_a_hard_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = tmp_path / "changed.json"
    source = reprojection.REPO_ROOT / reprojection.D_SAMPLE_RELATIVE_PATH
    changed.write_bytes(source.read_bytes() + b"\n")
    monkeypatch.setattr(
        reprojection,
        "REPO_ROOT",
        tmp_path,
    )
    relative = Path("changed.json")
    with pytest.raises(reprojection.ReprojectionError, match="SHA"):
        reprojection._load_locked_json(
            relative,
            reprojection.EXPECTED_INPUT_SHA256["d_sample"],
        )


def test_two_inputs_resolve_to_same_23_unique_scoring_atoms() -> None:
    inputs = reprojection.load_locked_inputs()
    z99_facts = inputs["z99_facts"]
    d_facts = inputs["d_facts"]
    assert [row["fact_id"] for row in z99_facts] == list(
        reprojection.EXPECTED_FACT_IDS
    )
    assert [row["fact_id"] for row in d_facts] == list(
        reprojection.EXPECTED_FACT_IDS
    )
    assert reprojection._fact_semantic_copy(
        z99_facts
    ) == reprojection._fact_semantic_copy(d_facts)
    assert len({row["fact_id"] for row in z99_facts}) == 23


def test_outline_has_one_fact_library_and_views_only_reference_it() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="test",
        facts=inputs["z99_facts"],
    )
    assert outline["schema"] == "chapter-fact-graph-outline-v1"
    assert len(outline["facts"]) == 23
    fact_ids = {row["fact_id"] for row in outline["facts"]}
    for view_name in (
        "timeline",
        "character_states",
        "unresolved_items",
    ):
        for row in outline["views"][view_name]:
            assert row["fact_id"] in fact_ids
            assert {"claim", "fact_head", "qualifiers"}.isdisjoint(row)
    for edge in outline["views"]["causal_edges"]:
        assert set(edge["from_fact_ids"]) <= fact_ids
        assert edge["to_fact_id"] in fact_ids
        assert {"claim", "fact_head", "qualifiers"}.isdisjoint(edge)


def test_timeline_uses_function_not_presence_of_time_qualifier() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="test",
        facts=inputs["z99_facts"],
    )
    timeline = outline["views"]["timeline"]
    by_id = {row["fact_id"]: row for row in timeline}
    assert len(timeline) == 11
    assert "GOLD-C0003-02-N01" in by_id
    assert by_id["GOLD-C0003-02-N01"]["time"] is None
    assert "GOLD-C0003-09-N05" not in by_id
    assert by_id["GOLD-C0003-08-N01"]["time"]["ref_fact_id"] == (
        "GOLD-C0003-07-N01"
    )
    assert [row["seq"] for row in timeline] == list(range(1, 12))


def test_causal_view_has_two_explicit_edges_and_single_endpoints_stay_out() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="test",
        facts=inputs["z99_facts"],
    )
    edges = outline["views"]["causal_edges"]
    assert [row["edge_id"] for row in edges] == [
        "CE-C0003-001",
        "CE-C0003-002",
    ]
    assert all(row["basis"] == "explicit" for row in edges)
    assert edges[0]["from_fact_ids"] == ["GOLD-C0003-02-N01"]
    assert edges[0]["to_fact_id"] == "GOLD-C0003-03-N01"
    assert edges[1]["from_fact_ids"] == [
        "GOLD-C0003-09-N01",
        "GOLD-C0003-10-N01",
    ]
    assert edges[1]["modal"] == "恐怕"
    assert outline["views"]["inference_edges"] == {
        "non_gold": True,
        "default_visible": False,
        "items": [],
    }
    assert outline["ratio_audit"]["status"]["causal"] == "OUT_OF_RANGE_LOW"


def test_character_state_admission_is_nine_and_continuity_is_traceable() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="test",
        facts=inputs["z99_facts"],
    )
    states = outline["views"]["character_states"]
    assert len(states) == 9
    assert {row["state_slot"] for row in states} <= reprojection.STATE_SLOTS
    assert "GOLD-C0003-13-N01" not in {row["fact_id"] for row in states}
    assert "GOLD-C0003-12-N02" not in {row["fact_id"] for row in states}
    assert "GOLD-C0003-12-N03" not in {row["fact_id"] for row in states}

    by_entry = {row["entry_id"]: row for row in states}
    path = ["CS-C0003-001", "CS-C0003-004", "CS-C0003-005"]
    assert [by_entry[entry_id]["character_id"] for entry_id in path] == [
        "周明瑞",
        "周明瑞",
        "周明瑞",
    ]
    assert [by_entry[entry_id]["state_slot"] for entry_id in path] == [
        "knowledge",
        "knowledge",
        "knowledge",
    ]
    assert by_entry[path[1]]["before"] == by_entry[path[0]]["after"]
    assert by_entry[path[2]]["before"] == by_entry[path[1]]["after"]
    assert by_entry[path[1]]["previous_entry_id"] == path[0]
    assert by_entry[path[2]]["previous_entry_id"] == path[1]


def test_unresolved_is_four_lifecycle_questions_not_believed_risk() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="test",
        facts=inputs["z99_facts"],
    )
    issues = outline["views"]["unresolved_items"]
    assert len(issues) == 4
    assert {row["issue_type"] for row in issues} == {"question"}
    assert {row["status"] for row in issues} == {"open"}
    assert all(row["closure_condition"] for row in issues)
    assert "GOLD-C0003-10-N02" not in {row["fact_id"] for row in issues}


def test_ratio_denominator_is_unique_atoms_and_out_of_range_is_not_tuned() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="test",
        facts=inputs["z99_facts"],
    )
    assert outline["counts"] == {
        "unique_facts": 23,
        "timeline_nodes": 11,
        "causal_edges": 2,
        "character_state_updates": 9,
        "unresolved_items": 4,
        "total_projection_rows": 26,
    }
    audit = outline["ratio_audit"]
    assert audit["denominator"] == {
        "name": "unique_scoring_atoms",
        "value": 23,
    }
    assert audit["actual_percent"] == {
        "timeline": 47.8261,
        "causal": 8.6957,
        "character_state": 39.1304,
        "unresolved": 17.3913,
    }
    assert audit["status"] == {
        "timeline": "PASS",
        "causal": "OUT_OF_RANGE_LOW",
        "character_state": "PASS",
        "unresolved": "PASS",
    }
    assert audit["total_projection_multiple"] == 1.1304
    assert audit["total_projection_multiple_status"] == "PASS"
    assert len(audit["backlog"]) == 1


def test_anchors_exist_only_in_z99_sidecar_and_d_does_not_borrow_them() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="z99",
        facts=inputs["z99_facts"],
    )
    z99_sidecar = reprojection.build_sidecar(
        source_sample_id="z99",
        outline=outline,
        source_locks=[],
        anchors_by_fact_id=inputs["z99_anchors"],
    )
    d_sidecar = reprojection.build_sidecar(
        source_sample_id="d",
        outline=outline,
        source_locks=[],
        anchors_by_fact_id=None,
    )
    consumer_keys = set(_nested_keys(outline))
    assert consumer_keys.isdisjoint(reprojection.FORBIDDEN_CONSUMER_KEYS)
    assert "quote" in set(_nested_keys(z99_sidecar))
    assert z99_sidecar["anchor_inventory"]["fact_count"] == 23
    assert d_sidecar["anchor_inventory"] == {
        "availability": "not_supplied_in_consumer_sample",
        "fact_count": 0,
        "items": [],
    }


def test_before_after_keeps_old_row_semantics_separate_from_new_edges() -> None:
    inputs = reprojection.load_locked_inputs()
    z99 = reprojection.build_outline(
        source_sample_id="z99",
        facts=inputs["z99_facts"],
    )
    d_sample = reprojection.build_outline(
        source_sample_id="d",
        facts=inputs["d_facts"],
    )
    comparison = reprojection.build_comparison(
        inputs=inputs,
        z99_outline=z99,
        d_outline=d_sample,
    )
    assert comparison["samples"]["z99_four_views_candidate_sample"][
        "before_counts"
    ] == {
        "unique_facts": 23,
        "timeline_nodes": 23,
        "causal_rows_not_edges": 7,
        "character_state_rows": 23,
        "unresolved_items": 4,
    }
    assert comparison["samples"]["sample_d_shared"]["before_counts"] == {
        "unique_facts": 23,
        "timeline_nodes": 10,
        "causal_rows_not_edges": 7,
        "character_state_rows": 23,
        "unresolved_items": 5,
    }
    assert comparison["state_variable_result"]["after_updates"] == 9
    assert comparison["fixed_v0.2_projection_result"]["causal_edges"] == 2


def test_bundle_is_byte_identical_and_manifest_hashes_every_artifact(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    source_paths = (
        reprojection.Z99_SAMPLE_RELATIVE_PATH,
        reprojection.Z99_SIDECAR_RELATIVE_PATH,
        reprojection.Z99_MANIFEST_RELATIVE_PATH,
        reprojection.D_SAMPLE_RELATIVE_PATH,
        reprojection.D_W1_MIRROR_RELATIVE_PATH,
    )
    hashes_before = {
        path: reprojection.sha256_file(reprojection.REPO_ROOT / path)
        for path in source_paths
    }
    left_manifest = reprojection.build_bundle(left)
    right_manifest = reprojection.build_bundle(right)
    assert left_manifest == right_manifest
    assert _tree_bytes(left) == _tree_bytes(right)
    assert hashes_before == {
        path: reprojection.sha256_file(reprojection.REPO_ROOT / path)
        for path in source_paths
    }

    assert left_manifest["execution"] == {
        "model_api_calls": 0,
        "network_requests": 0,
        "formal_gold_mutations": 0,
        "default_route_mutations": 0,
        "governance_mutations": 0,
        "notion_writes": 0,
    }
    assert left_manifest["mirror_check"]["w1_attachment_projection_count"] == 0
    for row in left_manifest["artifacts"]:
        artifact = left / row["path"]
        assert artifact.stat().st_size == row["bytes"]
        assert reprojection.sha256_file(artifact) == row["sha256"]
    assert reprojection.MANIFEST_FILENAME not in {
        row["path"] for row in left_manifest["artifacts"]
    }


def test_validation_rejects_dangling_edge_and_network_imports_are_absent() -> None:
    inputs = reprojection.load_locked_inputs()
    outline = reprojection.build_outline(
        source_sample_id="test",
        facts=inputs["z99_facts"],
    )
    changed = copy.deepcopy(outline)
    changed["views"]["causal_edges"][0]["from_fact_ids"] = ["NOT-A-FACT"]
    with pytest.raises(reprojection.ReprojectionError, match="悬空"):
        reprojection.validate_outline(changed)

    source = Path(reprojection.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert imported_roots.isdisjoint(
        {"httpx", "requests", "socket", "urllib", "aiohttp", "openai"}
    )


def test_serialized_consumers_have_no_anchor_identity_or_quote_fields(
    tmp_path: Path,
) -> None:
    reprojection.build_bundle(tmp_path)
    for filename in (
        reprojection.Z99_OUTPUT_FILENAME,
        reprojection.D_OUTPUT_FILENAME,
    ):
        payload = json.loads((tmp_path / filename).read_text(encoding="utf-8"))
        keys = set(_nested_keys(payload))
        assert keys.isdisjoint(reprojection.FORBIDDEN_CONSUMER_KEYS)
