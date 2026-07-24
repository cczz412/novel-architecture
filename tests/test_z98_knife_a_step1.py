from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.Z97_rfu_ucr_ledger_20260724.core import (
    validate_candidate_claim as validate_z97_candidate_claim,
)
from experiments.Z97_rfu_ucr_ledger_20260724.core import (
    validate_rfu as validate_z97_rfu,
)
from experiments.Z97_rfu_ucr_ledger_20260724.fixtures import (
    build_canary_suite,
)
from experiments.Z98_knife_a_patch_step1_20260724 import pipeline
from experiments.Z98_knife_a_patch_step1_20260724.core import (
    CHAPTER_SPECS,
    SourceReader,
    Z98ContractError,
    allocate_integer_budget,
    authorize_context_expansion,
    build_budget_plan,
    sha256_bytes,
    validate_atom_batch,
    validate_hardened_candidate_claim,
    validate_hardened_rfu,
    validate_patch,
    verify_sha,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_patch() -> dict[str, object]:
    return {
        "op": "KEEP",
        "target_event_ids": ["EV-C0003-01"],
        "source_span_ids": ["ch0003:E0001"],
        "actor": "甲",
        "predicate": "执行",
        "object_or_result": "动作",
        "hard_qualifiers": [],
        "fact_class": "event",
        "speaker": None,
        "anchor_candidates": ["ch0003:E0001"],
    }


def _z97_case() -> dict[str, object]:
    return copy.deepcopy(build_canary_suite()["cases"][0])


def test_source_reader_is_exact_allowlist_and_rejects_answer_paths() -> None:
    reader = SourceReader(REPO_ROOT)
    event_path = (
        "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_"
        "20260722_transport_retry03/main/01_extract/events/ch0003.json"
    )
    assert sha256_bytes(reader.read_bytes(event_path)) == CHAPTER_SPECS["ch0003"][
        "event_sha256"
    ]
    with pytest.raises(Z98ContractError, match="未登记路径"):
        reader.read_bytes(
            "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_"
            "20260722_transport_retry03/provenance/score_only/"
            "第3章结构层金标v1.2.json"
        )


def test_wrong_source_sha_hard_stops() -> None:
    with pytest.raises(Z98ContractError, match="SHA 漂移"):
        verify_sha(
            "0" * 64,
            str(CHAPTER_SPECS["ch0003"]["event_sha256"]),
            "wrong-source-canary",
        )


def test_patch_contract_rejects_unknown_fields_and_wrong_op_shape() -> None:
    patch = _valid_patch()
    assert validate_patch(patch) == patch
    extra = copy.deepcopy(patch)
    extra["explanation"] = "不准进入"
    with pytest.raises(Z98ContractError, match="未知字段"):
        validate_patch(extra)
    add = copy.deepcopy(patch)
    add["op"] = "ADD"
    with pytest.raises(Z98ContractError, match="ADD 不得绑定"):
        validate_patch(add)


def test_atom_batch_requires_exact_slots_and_mutually_exclusive_fields() -> None:
    slots = [f"SLOT-ch0003-{index:02d}" for index in range(1, 5)]
    payload = {
        "schema": "atom-batch-v2",
        "request_id": "REQ-01",
        "items": [
            {
                "slot_id": slot_id,
                "status": "ok",
                "atom": {
                    **_valid_patch(),
                    "target_event_ids": [f"EV-C0003-{index:02d}"],
                },
                "split_span_ids": [],
                "missing_context_codes": [],
            }
            for index, slot_id in enumerate(slots, start=1)
        ],
        "receipt": {
            "returned_slot_ids": slots,
        },
    }
    assert validate_atom_batch(
        payload,
        expected_slot_ids=slots,
    ) == payload
    missing = copy.deepcopy(payload)
    missing["items"] = missing["items"][:-1]
    with pytest.raises(Z98ContractError):
        validate_atom_batch(
            missing,
            expected_slot_ids=slots,
        )
    mixed = copy.deepcopy(payload)
    mixed["items"][0]["split_span_ids"] = ["ch0003:E0001"]
    with pytest.raises(Z98ContractError, match="只能填写 atom"):
        validate_atom_batch(
            mixed,
            expected_slot_ids=slots,
        )


def test_needs_context_uses_fixed_codes_and_program_allows_one_expansion() -> None:
    slots = [f"SLOT-ch0013-{index:02d}" for index in range(1, 5)]
    payload = {
        "schema": "atom-batch-v2",
        "request_id": "REQ-CONTEXT",
        "items": [
            {
                "slot_id": slot_id,
                "status": "needs_context",
                "atom": None,
                "split_span_ids": [],
                "missing_context_codes": ["speaker"],
            }
            for slot_id in slots
        ],
        "receipt": {
            "returned_slot_ids": slots,
        },
    }
    validate_atom_batch(
        payload,
        expected_slot_ids=slots,
    )
    payload["items"][0]["missing_context_codes"] = ["unknown"]
    with pytest.raises(Z98ContractError, match="原因码非法"):
        validate_atom_batch(
            payload,
            expected_slot_ids=slots,
        )
    assert authorize_context_expansion(0) == 1
    with pytest.raises(Z98ContractError, match="最多扩窗一次"):
        authorize_context_expansion(1)


def test_z98_hardening_only_rejects_z97_unknown_field_acceptance() -> None:
    case = _z97_case()
    rfu = case["rfus"][0]
    claim = case["claims"][0]
    assert validate_hardened_rfu(rfu) == rfu
    assert validate_hardened_candidate_claim(claim) == claim

    rfu_top_extra = copy.deepcopy(rfu)
    rfu_top_extra["legacy_note"] = "Z97接受、Z98拒绝"
    assert validate_z97_rfu(rfu_top_extra)["legacy_note"]
    with pytest.raises(Z98ContractError, match="未知字段"):
        validate_hardened_rfu(rfu_top_extra)

    rfu_support_extra = copy.deepcopy(rfu)
    rfu_support_extra["minimal_support_sets"][0]["legacy_note"] = "旧旁注"
    assert validate_z97_rfu(rfu_support_extra)["minimal_support_sets"][0][
        "legacy_note"
    ]
    with pytest.raises(Z98ContractError, match="support_sets"):
        validate_hardened_rfu(rfu_support_extra)

    rfu_provenance_extra = copy.deepcopy(rfu)
    rfu_provenance_extra["provenance"]["legacy_note"] = "旧旁注"
    assert validate_z97_rfu(rfu_provenance_extra)["provenance"]["legacy_note"]
    with pytest.raises(Z98ContractError, match="provenance"):
        validate_hardened_rfu(rfu_provenance_extra)

    rfu_nested_optional = copy.deepcopy(rfu)
    rfu_nested_optional["optional_details"] = [[]]
    assert validate_z97_rfu(rfu_nested_optional)["optional_details"] == [[]]
    with pytest.raises(Z98ContractError, match="JSON 基础值"):
        validate_hardened_rfu(rfu_nested_optional)

    claim_top_extra = copy.deepcopy(claim)
    claim_top_extra["legacy_note"] = "旧旁注"
    assert validate_z97_candidate_claim(claim_top_extra)["legacy_note"]
    with pytest.raises(Z98ContractError, match="未知字段"):
        validate_hardened_candidate_claim(claim_top_extra)

    claim_qualifier_extra = copy.deepcopy(claim)
    claim_qualifier_extra["qualifiers"] = [
        {
            "qualifier_id": "Q1",
            "type": "time",
            "normalized_value": "当日",
            "legacy_note": "旧旁注",
        }
    ]
    assert validate_z97_candidate_claim(claim_qualifier_extra)["qualifiers"][0][
        "legacy_note"
    ]
    with pytest.raises(Z98ContractError, match="qualifier"):
        validate_hardened_candidate_claim(claim_qualifier_extra)


def test_every_declared_object_layer_rejects_additional_properties() -> None:
    contract_dir = (
        REPO_ROOT
        / "experiments/Z98_knife_a_patch_step1_20260724/contracts"
    )
    for path in sorted(contract_dir.glob("*.json")):
        payload = _load(path)
        stack: list[object] = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get("type") == "object":
                    assert node.get("additionalProperties") is False, (
                        path.name,
                        node,
                    )
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)


def test_budget_caps_are_preregistered_and_actual_usage_is_unmeasured() -> None:
    for chapter_id, expected_count in {
        "ch0003": 5,
        "ch0013": 4,
        "ch0019": 5,
    }.items():
        plan = build_budget_plan(
            chapter_id,
            selected_count=expected_count,
            batch_count=1,
        )
        t1 = int(CHAPTER_SPECS[chapter_id]["t1_total_tokens"])
        assert plan["p2_token_cap"] == int(t1 * 0.25)
        assert plan["independent_verification_token_cap"] == int(t1 * 0.10)
        assert plan["whole_chain_token_cap"] == int(t1 * 1.35)
        assert plan["actual_repair_usage_tokens"] is None
        assert plan["actual_independent_verification_usage_tokens"] is None
        assert plan["budget_compliance_status"] == "PRE_REGISTERED_NOT_MEASURED"
        assert plan["whole_chain_formula_pass"] is True
    assert allocate_integer_budget(10, 3) == [4, 3, 3]


def test_build_bundle_is_byte_deterministic_and_stays_zero_call(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left_summary = pipeline.build_bundle(left, repo_root=REPO_ROOT)
    right_summary = pipeline.build_bundle(right, repo_root=REPO_ROOT)
    assert left_summary["manifest_sha256"] == right_summary["manifest_sha256"]
    assert left_summary["selected_repairs_by_chapter"] == {
        "ch0003": 5,
        "ch0013": 4,
        "ch0019": 5,
    }
    assert left_summary["single_request_count"] == 14
    assert left_summary["batch_request_count"] == 3
    assert left_summary["step2_release_allowed"] is False
    left_files = {
        path.relative_to(left): path.read_bytes()
        for path in left.rglob("*")
        if path.is_file()
    }
    right_files = {
        path.relative_to(right): path.read_bytes()
        for path in right.rglob("*")
        if path.is_file()
    }
    assert left_files == right_files
    preflight = _load(left / "preflight.json")
    assert preflight["model_api_calls"] == 0
    assert preflight["network_attempts"] == 0
    assert preflight["step2_release_allowed"] is False
    assert preflight["quality_status"] == "UNJUDGED"


def test_bundle_pins_request_event_usage_and_same_slots(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    same_exam = _load(bundle / "receipts/same_exam_receipt.json")
    assert same_exam["usage_sha256"] == (
        "ffec6350aa88c1bdd1d25da4c3d639f96c4584c3ae45da63f34e4e06b33b29e1"
    )
    expected_request_shas = {
        "ch0003": "066c28910e612bb38e0db2bc28bde9f2f43b4349ef52774a275a68b347e28f80",
        "ch0013": "ef343a3c0f52e1727e0a00a3dcc301cff7d158671edbc30252532189eee90629",
        "ch0019": "ef76edc3f27fc615a976ae5d9c0e6da7e333610c8b7e6e4f77c5ed027ea8c583",
    }
    for row in same_exam["chapters"]:
        chapter_id = row["chapter_id"]
        assert row["event_sha256"] == CHAPTER_SPECS[chapter_id]["event_sha256"]
        assert row["usage_request_sha256"] == expected_request_shas[chapter_id]
        assert row["actual_request_file_sha256"] == expected_request_shas[
            chapter_id
        ]
        assert len(row["prepared_request_file_sha256"]) == 64

    selection = _load(bundle / "receipts/selection_receipt.json")
    single_slots = sorted(
        _load(path)["slot_ids"][0]
        for path in (bundle / "requests/single").rglob("*.json")
    )
    batch_slots = sorted(
        slot_id
        for path in (bundle / "requests/atom_batch_v2").rglob("*.json")
        for slot_id in _load(path)["slot_ids"]
    )
    assert single_slots == batch_slots
    assert selection["single_and_batch_slot_sets_equal"] is True
    for chapter in selection["chapters"].values():
        for group in chapter["batch_groups"]:
            assert 4 <= len(group["slot_ids"]) <= 8
            assert group["cross_chapter_merge"] is False
    budget = _load(bundle / "receipts/budget_receipt.json")
    assert budget["status"] == "PRE_REGISTERED_NOT_MEASURED"
    assert budget["formula_precheck"] == "PASS"
    envelope = budget["transport_envelope"]
    assert envelope["grid_count"] == 4
    assert envelope["not_an_r_gate"] is True
    assert envelope["all_grid_future_new_logical_request_cap"] == 68
    assert envelope["all_grid_future_new_token_cap"] == 116604
    assert all(row["actual_usage_tokens"] is None for row in envelope["grids"])
    contracts = _load(bundle / "receipts/contract_sha_receipt.json")
    assert contracts["atom_batch_v2_runtime_rules"][
        "needs_context_max_expansions_per_slot"
    ] == 1


def test_bundle_leak_scan_canaries_and_p1_source_immutability(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    leak = _load(bundle / "receipts/model_window_leak_scan.json")
    assert leak["status"] == "PASS"
    assert leak["forbidden_hit_count"] == 0
    canary = _load(bundle / "receipts/canary_receipt.json")
    assert canary["status"] == "PASS"
    assert {row["canary"] for row in canary["cases"]} == {
        "budget_preregistered_not_measured",
        "chapter_repair_limit",
        "arm_and_chapter_isolation",
        "wrong_source_sha_rejected",
        "unknown_field_rejected",
    }
    p1 = _load(bundle / "receipts/p1_hardening_diff.json")
    assert p1["status"] == "PASS"
    assert p1["z97_source_unchanged"] is True
    assert p1["only_tightening"] is True
    assert p1["z97_demo_artifacts_rewritten"] is False


def test_authority_contract_is_frozen_with_explicit_sha_boundary(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    authority_path = bundle / "design/authority_contract.json"
    authority = _load(authority_path)
    receipt = _load(bundle / "receipts/authority_contract_sha_receipt.json")
    assert authority["authority"] == {
        "notion_queue_url": (
            "https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc"
        ),
        "notion_ledger_url": (
            "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"
        ),
        "authority_time": "2026-07-24T15:55:00+08:00",
        "unified_design_page_id": "e3cfee94-c8d0-4df4-9b2f-454b9e01b1d7",
    }
    assert authority["verbatim_core_formulas"] == [
        "T1=I1+O1",
        "T2≤0.25T1",
        "q×T3≤0.10T1",
        "R=(T1+T2+q×T3)/T1≤1.35",
    ]
    assert authority["atom_batch_v2_fixed_item_fields"] == [
        "slot_id",
        "status",
        "atom",
        "split_span_ids",
        "missing_context_codes",
    ]
    assert receipt["sha256"] == sha256_bytes(authority_path.read_bytes())
    assert "不冒充Notion页面原始字节SHA" in receipt["sha_boundary"]


def test_frozen_task_registry_binds_all_14_slots_to_source_truth(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    pipeline.build_bundle(bundle, repo_root=REPO_ROOT)
    registry = _load(bundle / "design/frozen_task_registry.json")
    tasks = registry["tasks"]
    assert registry["task_count"] == 14
    assert len({task["task_id"] for task in tasks}) == 14
    assert len({task["slot_id"] for task in tasks}) == 14
    by_chapter = {
        chapter_id: [
            task for task in tasks if task["chapter_id"] == chapter_id
        ]
        for chapter_id in CHAPTER_SPECS
    }
    assert {chapter: len(rows) for chapter, rows in by_chapter.items()} == {
        "ch0003": 5,
        "ch0013": 4,
        "ch0019": 5,
    }
    for chapter_id, rows in by_chapter.items():
        event_path = REPO_ROOT / rows[0]["source_event_path"]
        payload = _load(event_path)
        events = {
            event["event_id"]: event for event in payload["events"]
        }
        assert [task["atom_index"] for task in rows] == list(
            range(1, len(rows) + 1)
        )
        for task in rows:
            assert task["status"] == "FROZEN_NOT_SENT"
            assert task["contract_arms"] == [
                "single_patch",
                "atom_batch_v2",
            ]
            assert task["must_not_add_new_facts"] is True
            assert task["must_not_drop_source_supported_facts"] is True
            assert task["source_event_file_sha256"] == CHAPTER_SPECS[
                chapter_id
            ]["event_sha256"]
            event = events[task["parent_event_id"]]
            assert task["source_event_identity_sha256"] == sha256_bytes(
                (
                    json.dumps(
                        event,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
            )
            request_path = REPO_ROOT / task["source_actual_request_path"]
            assert task["source_actual_request_sha256"] == sha256_bytes(
                request_path.read_bytes()
            )
            assert task["batch_id"].startswith(f"BATCH-{chapter_id}-")
    manifest = _load(bundle / "bundle_manifest.json")
    manifest_paths = {row["path"] for row in manifest["files"]}
    assert "design/authority_contract.json" in manifest_paths
    assert "design/frozen_task_registry.json" in manifest_paths
