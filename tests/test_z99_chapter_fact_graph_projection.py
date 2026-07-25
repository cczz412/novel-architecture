from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from tools import z99_chapter_fact_graph_projection as projection


def _load() -> tuple[dict[str, object], bytes]:
    return projection.load_locked_source()


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


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_locked_input_is_exact_ucr_return_not_old_ledger_or_formal_z73() -> None:
    document, raw = _load()
    assert projection.sha256_bytes(raw) == (
        "8056fe4a810ae255881b04028128e11e7c08a7abafe5baaf58cf8ba0b7ad3f1a"
    )
    assert projection.SOURCE_RELATIVE_PATH.as_posix() == (
        "references/diagnostic-returns/"
        "六本金标UCR核准回包_20260724/"
        "原始回包/"
        "X01-ch0003-structure-v1.2_candidate_RFU_UCR_review.json"
    )
    assert document["gold_id"] == projection.EXPECTED_GOLD_ID
    assert document["status"] == "candidate_revision_not_active"


def test_sha_drift_is_a_hard_failure(tmp_path: Path) -> None:
    _, raw = _load()
    changed = tmp_path / "changed.json"
    changed.write_bytes(raw + b"\n")
    with pytest.raises(projection.ProjectionError, match="SHA"):
        projection.load_locked_source(changed)


def test_four_view_counts_and_expected_unresolved_rows() -> None:
    document, _ = _load()
    views = projection.build_views(document)
    assert views["timeline"]["counts"] == {
        "entry_count": 23,
        "explicit_time_qualifier_count": 13,
    }
    assert views["causal_candidates"]["counts"] == {"candidate_count": 7}
    assert views["character_state_candidates"]["counts"] == {
        "subject_group_count": 5,
        "fact_candidate_count": 23,
    }
    unresolved = views["unresolved"]["entries"]
    assert [row["part_id"] for row in unresolved] == [
        "GOLD-C0003-09-N02",
        "GOLD-C0003-09-N03",
        "GOLD-C0003-09-N04",
        "GOLD-C0003-09-N05",
    ]
    assert all(row["fact_head"]["actuality"] == "unresolved" for row in unresolved)


def test_timeline_uses_source_order_proxy_and_explicit_time_types_only() -> None:
    document, _ = _load()
    timeline = projection.build_views(document)["timeline"]
    entries = timeline["entries"]
    assert [row["narrative_order_proxy"] for row in entries] == sorted(
        row["narrative_order_proxy"] for row in entries
    )
    # Five non-RFU hindsight parts remain visible as gaps in the source-order
    # proxy; the proxy is not rewritten into a fake clock-time sequence.
    assert entries[-1]["narrative_order_proxy"] == 26
    assert all(
        "time" in qualifier["normalized_dimensions"]
        for row in entries
        for qualifier in row["explicit_time_qualifiers"]
    )
    by_id = {row["part_id"]: row for row in entries}
    assert by_id["GOLD-C0003-02-N01"]["explicit_time_qualifiers"] == []
    assert by_id["GOLD-C0003-11-N02"]["explicit_time_qualifiers"] == [
        {
            "type_original": "条件/时间",
            "value": "掌握理论知识后",
            "normalized_dimensions": ["condition", "time"],
        }
    ]
    assert "clock" not in json.dumps(timeline, ensure_ascii=False).lower()


def test_causal_candidates_are_same_part_explicit_qualifiers_only() -> None:
    document, _ = _load()
    causal = projection.build_views(document)["causal_candidates"]
    assert causal["adjacency_inference_used"] is False
    assert [row["source_part_id"] for row in causal["candidates"]] == [
        "GOLD-C0003-02-N01",
        "GOLD-C0003-03-N01",
        "GOLD-C0003-08-N01",
        "GOLD-C0003-10-N02",
        "GOLD-C0003-11-N02",
        "GOLD-C0003-12-N01",
        "GOLD-C0003-14-N01",
    ]
    for row in causal["candidates"]:
        assert row["derivation"] == "same_part_explicit_required_qualifier_only"
        assert set(row["relation_dimensions"]) <= projection.CAUSAL_DIMENSIONS
        assert row["explicit_qualifier"]["type_original"] in {
            "条件",
            "条件/时间",
            "目的",
            "目的/动机",
        }


def test_character_groups_keep_exact_subject_strings_and_are_not_current_state() -> None:
    document, _ = _load()
    view = projection.build_views(document)["character_state_candidates"]
    groups = view["subject_groups"]
    assert view["grouping_rule"] == "exact_subject_string_no_alias_merge"
    assert view["current_state_claimed"] is False
    assert [row["subject_original"] for row in groups] == [
        "周明瑞",
        "梅丽莎",
        "班森",
        "克莱恩",
        "梅丽莎和周明瑞",
    ]
    assert [row["entry_count"] for row in groups] == [12, 7, 1, 2, 1]
    joint = groups[-1]
    assert [row["fact_head"]["subject"] for row in joint["fact_candidates"]] == [
        "梅丽莎和周明瑞"
    ]


def test_compound_and_chinese_qualifier_types_are_preserved_with_mapping() -> None:
    document, _ = _load()
    parts = projection.collect_projectable_parts(document)
    projected = {
        qualifier["type_original"]: tuple(qualifier["normalized_dimensions"])
        for part in parts
        for qualifier in part["required_qualifiers"]
    }
    source_types = {
        qualifier["type"]
        for item in document["layered_items"]
        for part in item["parts"]
        if part.get("rfu")
        for qualifier in part["rfu"]["required_qualifiers"]
    }
    assert set(projected) == source_types
    assert projected["条件/时间"] == ("condition", "time")
    assert projected["目的/动机"] == ("purpose", "motivation")
    assert projected["归因/actuality"] == ("attribution", "actuality")
    assert projected["来源/方法"] == ("source", "method")


def test_unknown_qualifier_type_is_rejected_instead_of_silently_dropped() -> None:
    document, _ = _load()
    changed = copy.deepcopy(document)
    changed["layered_items"][0]["parts"][0]["rfu"]["required_qualifiers"][0][
        "type"
    ] = "时间/未知复合维度"
    with pytest.raises(projection.ProjectionError, match="未登记限定类型"):
        projection.collect_projectable_parts(changed)


def test_consumer_views_have_no_audit_evidence_or_anchor_identity_fields() -> None:
    document, _ = _load()
    views = projection.build_views(document)
    combined = projection.build_combined_sample(views)
    payloads = [combined, *views.values()]
    for payload in payloads:
        projection.assert_consumer_view_clean(payload)
        keys = [key.lower() for key in _nested_keys(payload)]
        assert not (
            projection.FORBIDDEN_CONSUMER_KEYS.intersection(keys)
        )
        assert not any(
            fragment in key
            for key in keys
            for fragment in projection.FORBIDDEN_CONSUMER_KEY_FRAGMENTS
        )
        serialized = json.dumps(payload, ensure_ascii=False)
        assert not projection.ANCHOR_ID_PATTERN.search(serialized)
        assert "review" not in serialized.lower()


def test_sidecar_is_a_complete_semantic_copy_of_the_locked_input() -> None:
    document, _ = _load()
    parts = projection.collect_projectable_parts(document)
    views = projection.build_views(document)
    sidecar = projection.build_audit_sidecar(document, parts, views)
    assert sidecar["source_document"] == document
    source_keys = _nested_keys(sidecar["source_document"])
    assert "quote" in source_keys
    assert "minimal_support_sets" in source_keys
    assert "source_evidence" in source_keys
    assert "review" in source_keys
    assert "pathology_tags" in source_keys


def test_bundle_is_byte_identical_and_manifest_hashes_every_listed_artifact(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    source_path = projection.REPO_ROOT / projection.SOURCE_RELATIVE_PATH
    source_sha_before = projection.sha256_file(source_path)
    left_manifest = projection.build_bundle(left)
    right_manifest = projection.build_bundle(right)
    assert _tree_bytes(left) == _tree_bytes(right)
    assert left_manifest == right_manifest
    assert projection.sha256_file(source_path) == source_sha_before

    for row in left_manifest["artifacts"]:
        artifact = left / row["path"]
        assert artifact.stat().st_size == row["bytes"]
        assert projection.sha256_file(artifact) == row["sha256"]
    assert projection.MANIFEST_FILENAME not in {
        row["path"] for row in left_manifest["artifacts"]
    }


def test_markdown_artifacts_end_with_codex_source_and_keep_candidate_boundary(
    tmp_path: Path,
) -> None:
    projection.build_bundle(tmp_path)
    sample = (tmp_path / projection.MARKDOWN_SAMPLE_FILENAME).read_text(
        encoding="utf-8"
    )
    receipt = (tmp_path / projection.ACCEPTANCE_RECEIPT_FILENAME).read_text(
        encoding="utf-8"
    )
    assert sample.rstrip().endswith("来源：Codex")
    assert receipt.rstrip().endswith("来源：Codex")
    assert "不是正式金标" in sample
    assert "模型 API 调用：0" in receipt
    assert "网络请求：0" in receipt


def test_generator_imports_no_network_or_api_client_modules() -> None:
    source = Path(projection.__file__).read_text(encoding="utf-8")
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
