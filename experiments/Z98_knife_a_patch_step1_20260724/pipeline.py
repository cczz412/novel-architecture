"""第98道刀A步一零调用备料包生成器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import (
    CHAPTER_SPECS,
    RETRY03_ROOT,
    RETRY03_USAGE_SHA256,
    Z94_SINGLE_CONTRACT_PATH,
    Z96_SUMMARY_PATH,
    Z97_CLAIM_SCHEMA_PATH,
    Z97_RFU_SCHEMA_PATH,
    SourceReader,
    Z98ContractError,
    build_budget_plan,
    make_batch_groups,
    select_slots,
    sha256_bytes,
    stable_json_bytes,
    validate_patch,
    verify_sha,
)


PACKAGE_ROOT = Path(__file__).resolve().parent
AUTHORITY_CONTRACT_PATH = PACKAGE_ROOT / "design/authority_contract.json"
CONTRACT_PATHS = {
    "knife_a_patch_v1": PACKAGE_ROOT / "contracts/knife_a_patch_v1.schema.json",
    "atom_batch_v2": PACKAGE_ROOT / "contracts/atom_batch_v2.schema.json",
    "rfu_v1_hardened": PACKAGE_ROOT
    / "contracts/rfu_v1_hardened.schema.json",
    "candidate_claim_v1_hardened": PACKAGE_ROOT
    / "contracts/candidate_claim_v1_hardened.schema.json",
}
_MODEL_LEAK_KEYS = {
    "gold",
    "golden",
    "answer",
    "answers",
    "score",
    "scores",
    "adjudication",
    "verdict",
    "human_judgment",
}
_MODEL_LEAK_MARKERS = (
    "GOLD-C",
    "MatchVerdict",
    "scoring_answers",
    "score_only",
    "人工判词",
    "正式答案",
    "金标答案",
)


def _load_json_bytes(path: Path) -> tuple[Any, bytes]:
    data = path.read_bytes()
    return json.loads(data), data


def _read_usage(reader: SourceReader) -> dict[str, dict[str, Any]]:
    raw = reader.read_bytes(f"{RETRY03_ROOT}/main/usage.jsonl")
    verify_sha(
        sha256_bytes(raw),
        RETRY03_USAGE_SHA256,
        "retry03 usage.jsonl",
    )
    rows: dict[str, dict[str, Any]] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = str(row["case_id"])
        chapter_id = case_id.rsplit("_ch", maxsplit=1)[-1]
        rows[f"ch{chapter_id}"] = row
    return rows


def _load_inputs(
    reader: SourceReader,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    usage_rows = _read_usage(reader)
    chapter_inputs: dict[str, dict[str, Any]] = {}
    same_exam_rows: list[dict[str, Any]] = []
    for chapter_id, spec in CHAPTER_SPECS.items():
        event_path = (
            f"{RETRY03_ROOT}/main/01_extract/events/{chapter_id}.json"
        )
        evidence_path = (
            f"{RETRY03_ROOT}/inputs/evidence_catalogs/{chapter_id}.json"
        )
        event_bytes = reader.read_bytes(event_path)
        event_sha = sha256_bytes(event_bytes)
        verify_sha(event_sha, str(spec["event_sha256"]), f"{chapter_id} 事件")
        event_payload = json.loads(event_bytes)
        events = event_payload.get("events")
        if not isinstance(events, list) or len(events) != spec["event_count"]:
            raise Z98ContractError(f"{chapter_id} 事件数量漂移")
        evidence_bytes = reader.read_bytes(evidence_path)
        evidence_payload = json.loads(evidence_bytes)
        evidence_entries = evidence_payload.get("entries")
        if not isinstance(evidence_entries, list):
            raise Z98ContractError(f"{chapter_id} 冻结目录结构非法")
        usage = usage_rows.get(chapter_id)
        if usage is None:
            raise Z98ContractError(f"{chapter_id} 缺 usage")
        total_tokens = usage.get("usage", {}).get("total_tokens")
        if total_tokens != spec["t1_total_tokens"]:
            raise Z98ContractError(f"{chapter_id} T1 usage 漂移")
        request_path = f"{RETRY03_ROOT}/prepared_requests/{chapter_id}.json"
        request_bytes = reader.read_bytes(request_path)
        actual_request_path = (
            f"{RETRY03_ROOT}/main/requests/neutral_extract/"
            f"z83_main_{chapter_id}_request.json"
        )
        actual_request_bytes = reader.read_bytes(actual_request_path)
        actual_request_file_sha = sha256_bytes(actual_request_bytes)
        request_sha = usage.get("request_sha256")
        verify_sha(
            str(request_sha),
            str(spec["request_sha256"]),
            f"{chapter_id} 实发 request",
        )
        verify_sha(
            actual_request_file_sha,
            str(spec["request_sha256"]),
            f"{chapter_id} 实发 request 文件",
        )
        chapter_inputs[chapter_id] = {
            "events": events,
            "evidence_entries": evidence_entries,
            "event_path": event_path,
            "evidence_path": evidence_path,
            "event_sha256": event_sha,
            "evidence_sha256": sha256_bytes(evidence_bytes),
            "t1_total_tokens": total_tokens,
            "usage_request_sha256": usage["request_sha256"],
            "usage_response_sha256": usage["raw_response_sha256"],
            "prepared_request_path": request_path,
            "prepared_request_file_sha256": sha256_bytes(request_bytes),
            "actual_request_path": actual_request_path,
            "actual_request_file_sha256": actual_request_file_sha,
        }
        same_exam_rows.append(
            {
                "chapter_id": chapter_id,
                "event_path": event_path,
                "event_sha256": event_sha,
                "event_count": len(events),
                "evidence_path": evidence_path,
                "evidence_entry_count": len(evidence_entries),
                "t1_total_tokens": total_tokens,
                "usage_request_sha256": usage["request_sha256"],
                "usage_response_sha256": usage["raw_response_sha256"],
                "prepared_request_path": request_path,
                "prepared_request_file_sha256": sha256_bytes(request_bytes),
                "actual_request_path": actual_request_path,
                "actual_request_file_sha256": actual_request_file_sha,
            }
        )
    return chapter_inputs, {
        "schema_version": "z98-same-exam-receipt-v1",
        "status": "PASS",
        "sealed_source": "retry03",
        "chapters": same_exam_rows,
        "total_events": sum(row["event_count"] for row in same_exam_rows),
        "total_t1_tokens": sum(row["t1_total_tokens"] for row in same_exam_rows),
        "usage_path": f"{RETRY03_ROOT}/main/usage.jsonl",
        "usage_sha256": RETRY03_USAGE_SHA256,
        "historical_run_status_boundary": (
            "只复用三章唯一有效主样张；不把后续检查员硬停改写成完成态"
        ),
    }


def _contract_material() -> tuple[dict[str, Any], dict[str, bytes]]:
    parsed: dict[str, Any] = {}
    raw: dict[str, bytes] = {}
    for name, path in CONTRACT_PATHS.items():
        value, data = _load_json_bytes(path)
        parsed[name] = value
        raw[name] = data
    return parsed, raw


def _model_visible_slot(slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot_id": slot["slot_id"],
        "source_event_id": slot["source_event_id"],
        "source_event": slot["source_event"],
        "source_span_ids": slot["source_span_ids"],
        "anchor_candidates": slot["anchor_candidates"],
    }


def _single_requests(
    selected: dict[str, list[dict[str, Any]]],
    patch_schema: dict[str, Any],
    patch_schema_sha: str,
) -> dict[str, dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}
    for chapter_id, slots in selected.items():
        for slot in slots:
            request_id = f"Z98-P2-SINGLE-{slot['slot_id']}"
            model_visible = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你只处理程序点名的一条事件，返回一个刀A补丁对象。"
                            "不得重写整章，不得输出合同外字段。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": stable_json_bytes(
                            {
                                "request_id": request_id,
                                "input": _model_visible_slot(slot),
                                "response_contract": patch_schema,
                            }
                        ).decode("utf-8"),
                    },
                ],
                "response_contract_sha256": patch_schema_sha,
            }
            requests[
                f"requests/single/{chapter_id}/{slot['slot_id']}.json"
            ] = {
                "schema_version": "z98-single-request-blueprint-v1",
                "request_id": request_id,
                "chapter_id": chapter_id,
                "slot_ids": [slot["slot_id"]],
                "contract_mode": "single_patch",
                "candidate_silver_only": True,
                "model_visible": model_visible,
            }
    return requests


def _batch_requests(
    selected: dict[str, list[dict[str, Any]]],
    groups: dict[str, list[dict[str, Any]]],
    patch_schema: dict[str, Any],
    batch_schema: dict[str, Any],
    batch_schema_sha: str,
) -> dict[str, dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}
    for chapter_id, chapter_groups in groups.items():
        by_slot = {str(slot["slot_id"]): slot for slot in selected[chapter_id]}
        for group in chapter_groups:
            slots = [by_slot[slot_id] for slot_id in group["slot_ids"]]
            request_id = f"Z98-P2-{group['batch_id']}"
            model_visible = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你只处理程序预给的4到8个slot。每个slot只返回一个"
                            "互斥状态；返回slot顺序与全集必须原样一致。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": stable_json_bytes(
                            {
                                "request_id": request_id,
                                "slots": [
                                    _model_visible_slot(slot) for slot in slots
                                ],
                                "response_contract": batch_schema,
                                "patch_contract": patch_schema,
                            }
                        ).decode("utf-8"),
                    },
                ],
                "response_contract_sha256": batch_schema_sha,
            }
            requests[
                f"requests/atom_batch_v2/{chapter_id}/{group['batch_id']}.json"
            ] = {
                "schema_version": "z98-batch-request-blueprint-v1",
                "request_id": request_id,
                "chapter_id": chapter_id,
                "slot_ids": group["slot_ids"],
                "contract_mode": "atom_batch_v2",
                "candidate_silver_only": True,
                "model_visible": model_visible,
            }
    return requests


def _walk_for_leaks(value: Any, path: str = "$") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in _MODEL_LEAK_KEYS:
                hits.append({"path": f"{path}.{key}", "reason": "forbidden_key"})
            hits.extend(_walk_for_leaks(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_walk_for_leaks(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for marker in _MODEL_LEAK_MARKERS:
            if marker in value:
                hits.append(
                    {
                        "path": path,
                        "reason": f"forbidden_marker:{marker}",
                    }
                )
    return hits


def _p1_diff_ticket(
    source_before: dict[str, str],
    source_after: dict[str, str],
    hardened_contract_shas: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "z98-p1-hardening-diff-v1",
        "status": (
            "PASS"
            if source_before == source_after
            else "HARD_STOP_SOURCE_CHANGED"
        ),
        "z97_source_sha_before": source_before,
        "z97_source_sha_after": source_after,
        "z97_source_unchanged": source_before == source_after,
        "z98_hardened_schema_sha256": hardened_contract_shas,
        "only_tightening": True,
        "changes": [
            {
                "schema": "rfu",
                "json_pointer": "",
                "old": "additionalProperties=true",
                "new": "additionalProperties=false",
            },
            {
                "schema": "rfu",
                "json_pointer": "/properties/minimal_support_sets/items",
                "old": "additionalProperties=true",
                "new": "additionalProperties=false",
            },
            {
                "schema": "rfu",
                "json_pointer": "/properties/provenance",
                "old": "additionalProperties=true",
                "new": "additionalProperties=false",
            },
            {
                "schema": "rfu",
                "json_pointer": "/properties/optional_details/items",
                "old": "unconstrained",
                "new": "JSON primitives only; uncontracted objects rejected",
            },
            {
                "schema": "candidate_claim",
                "json_pointer": "",
                "old": "additionalProperties=true",
                "new": "additionalProperties=false",
            },
            {
                "schema": "candidate_claim",
                "json_pointer": "/properties/qualifiers/items",
                "old": "additionalProperties=true",
                "new": "additionalProperties=false",
            },
        ],
        "semantic_field_meanings_changed": False,
        "z97_demo_artifacts_rewritten": False,
    }


def _comparison_design(
    z96_summary_sha: str,
    z94_single_contract_sha: str,
) -> dict[str, Any]:
    return {
        "schema_version": "z98-comparison-design-v1",
        "dispute_2_three_way": [
            {
                "arm": "retry03_baseline",
                "source": "sealed_same_exam",
                "new_model_calls": 0,
            },
            {
                "arm": "z96_knife_b_a_plus_anchor_replay",
                "source_sha256": z96_summary_sha,
                "new_model_calls": 0,
                "quality_boundary": "只读候选重放，不复用旧质量结论",
            },
            {
                "arm": "z98_knife_a_p2_patch",
                "source": "new_candidate_requests",
                "new_model_calls": "step2_only",
            },
        ],
        "dispute_3_same_selected_slots": {
            "single_mode": "single_patch",
            "batch_mode": "atom-batch-v2",
            "selected_slot_identity_must_match": True,
            "current_single_object_contract_read_only_reference_sha256": (
                z94_single_contract_sha
            ),
            "current_single_object_contract_modified": False,
        },
        "metrics": {
            "legacy_strict": {
                "role": "read_only",
                "historical_results_rewritten": False,
            },
            "ucr_five_layers": {
                "role": "candidate_columns_only",
                "columns": [
                    "FCR",
                    "QCR_full",
                    "ASR_full",
                    "UCR",
                    "SOP",
                ],
                "formal_score": False,
                "metric_switch_evidence": False,
            },
        },
        "gold_or_answer_in_model_window": False,
    }


def _frozen_task_registry(
    chapter_inputs: dict[str, dict[str, Any]],
    selected: dict[str, list[dict[str, Any]]],
    groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    permitted_actions = [
        "KEEP",
        "ADD",
        "SPLIT",
        "NARROW",
        "RECLASSIFY",
        "ADD_ANCHOR_CANDIDATE",
    ]
    for chapter_id, slots in selected.items():
        batch_by_slot = {
            slot_id: group["batch_id"]
            for group in groups[chapter_id]
            for slot_id in group["slot_ids"]
        }
        events_by_id = {
            str(event["event_id"]): event
            for event in chapter_inputs[chapter_id]["events"]
        }
        for atom_index, slot in enumerate(slots, start=1):
            event_id = str(slot["source_event_id"])
            event = events_by_id[event_id]
            tasks.append(
                {
                    "task_id": f"Z98-TASK-{chapter_id}-{atom_index:02d}",
                    "slot_id": slot["slot_id"],
                    "batch_id": batch_by_slot[str(slot["slot_id"])],
                    "parent_event_id": event_id,
                    "chapter_id": chapter_id,
                    "atom_index": atom_index,
                    "source_event_path": chapter_inputs[chapter_id][
                        "event_path"
                    ],
                    "source_event_file_sha256": chapter_inputs[chapter_id][
                        "event_sha256"
                    ],
                    "source_event_identity_sha256": sha256_bytes(
                        stable_json_bytes(event)
                    ),
                    "source_actual_request_path": chapter_inputs[chapter_id][
                        "actual_request_path"
                    ],
                    "source_actual_request_sha256": chapter_inputs[chapter_id][
                        "actual_request_file_sha256"
                    ],
                    "contract_arms": [
                        "single_patch",
                        "atom_batch_v2",
                    ],
                    "permitted_actions": permitted_actions,
                    "must_not_add_new_facts": True,
                    "must_not_drop_source_supported_facts": True,
                    "status": "FROZEN_NOT_SENT",
                }
            )
    return {
        "schema_version": "z98-frozen-task-registry-v1",
        "task_count": len(tasks),
        "tasks": tasks,
        "selection_origin": "deterministic risk ranking; no manual answers",
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _run_canaries(
    *,
    selected: dict[str, list[dict[str, Any]]],
    groups: dict[str, list[dict[str, Any]]],
    budgets: list[dict[str, Any]],
    single_requests: dict[str, dict[str, Any]],
    batch_requests: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    budget_pass = all(
        row["whole_chain_formula_pass"]
        and row["actual_repair_usage_tokens"] is None
        and row["budget_compliance_status"] == "PRE_REGISTERED_NOT_MEASURED"
        for row in budgets
    )
    results.append({"canary": "budget_preregistered_not_measured", "pass": budget_pass})

    expected_limits = {
        chapter_id: min(
            6,
            int(CHAPTER_SPECS[chapter_id]["event_count"]) // 10,
        )
        for chapter_id in CHAPTER_SPECS
    }
    actual_limits = {
        chapter_id: len(slots) for chapter_id, slots in selected.items()
    }
    results.append(
        {
            "canary": "chapter_repair_limit",
            "pass": actual_limits == expected_limits,
            "expected": expected_limits,
            "actual": actual_limits,
        }
    )

    single_slots = sorted(
        slot_id
        for request in single_requests.values()
        for slot_id in request["slot_ids"]
    )
    batch_slots = sorted(
        slot_id
        for request in batch_requests.values()
        for slot_id in request["slot_ids"]
    )
    provider_markers = ("sensenova", "tencent_tokenhub", "deepseek-v4")
    model_visible_text = stable_json_bytes(
        [
            request["model_visible"]
            for request in [*single_requests.values(), *batch_requests.values()]
        ]
    ).decode("utf-8")
    arm_isolation = (
        single_slots == batch_slots
        and not any(marker in model_visible_text for marker in provider_markers)
        and all(
            not group["cross_chapter_merge"]
            for chapter_groups in groups.values()
            for group in chapter_groups
        )
    )
    results.append({"canary": "arm_and_chapter_isolation", "pass": arm_isolation})

    wrong_sha_rejected = False
    try:
        verify_sha(
            "0" * 64,
            str(CHAPTER_SPECS["ch0003"]["event_sha256"]),
            "CANARY wrong source",
        )
    except Z98ContractError:
        wrong_sha_rejected = True
    results.append({"canary": "wrong_source_sha_rejected", "pass": wrong_sha_rejected})

    unknown_field_rejected = False
    sample_patch = {
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
        "unknown": "reject",
    }
    try:
        validate_patch(sample_patch)
    except Z98ContractError:
        unknown_field_rejected = True
    results.append(
        {"canary": "unknown_field_rejected", "pass": unknown_field_rejected}
    )
    return {
        "schema_version": "z98-step1-canary-receipt-v1",
        "status": "PASS" if all(row["pass"] for row in results) else "FAIL",
        "cases": results,
    }


def _transport_envelope(budgets: list[dict[str, Any]]) -> dict[str, Any]:
    grids: list[dict[str, Any]] = []
    for provider_lane in ("flash", "pro"):
        for contract_mode in ("single_patch", "atom_batch_v2"):
            logical_requests = sum(
                int(row["contract_modes"][contract_mode][
                    "future_new_logical_requests"
                ])
                for row in budgets
            )
            token_cap = sum(
                int(
                    row["contract_modes"][contract_mode][
                        "future_new_token_cap"
                    ]
                )
                for row in budgets
            )
            grids.append(
                {
                    "provider_lane": provider_lane,
                    "contract_mode": contract_mode,
                    "future_new_logical_request_cap": logical_requests,
                    "future_new_token_cap": token_cap,
                    "actual_usage_tokens": None,
                    "status": "PRE_REGISTERED_NOT_MEASURED",
                }
            )
    return {
        "grid_count": len(grids),
        "grids": grids,
        "all_grid_future_new_logical_request_cap": sum(
            row["future_new_logical_request_cap"] for row in grids
        ),
        "all_grid_future_new_token_cap": sum(
            row["future_new_token_cap"] for row in grids
        ),
        "not_an_r_gate": True,
        "boundary": (
            "四格相加只作运输总包络；R闸始终在"
            "chapter×provider×contract_mode单元内独立判断"
        ),
    }


def build_bundle(
    bundle_root: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """生成确定性步一包；目标目录必须为空或不存在。"""

    repository = (
        repo_root.resolve()
        if repo_root is not None
        else PACKAGE_ROOT.parents[1].resolve()
    )
    target = bundle_root.resolve()
    if target.exists() and any(target.iterdir()):
        raise Z98ContractError(f"目标目录非空，拒绝覆盖：{target}")
    target.mkdir(parents=True, exist_ok=True)
    reader = SourceReader(repository)

    z97_before = {
        "rfu.schema.json": sha256_bytes(reader.read_bytes(Z97_RFU_SCHEMA_PATH)),
        "candidate_claim.schema.json": sha256_bytes(
            reader.read_bytes(Z97_CLAIM_SCHEMA_PATH)
        ),
    }
    chapter_inputs, same_exam_receipt = _load_inputs(reader)
    z96_bytes = reader.read_bytes(Z96_SUMMARY_PATH)
    z94_single_bytes = reader.read_bytes(Z94_SINGLE_CONTRACT_PATH)
    z96_summary = json.loads(z96_bytes)
    if z96_summary.get("status") != "PASS":
        raise Z98ContractError("Z96 刀B候选摘要不是 PASS")
    contracts, contract_bytes = _contract_material()
    authority_bytes = AUTHORITY_CONTRACT_PATH.read_bytes()
    authority_contract = json.loads(authority_bytes)
    contract_shas = {
        name: sha256_bytes(data) for name, data in contract_bytes.items()
    }

    selected: dict[str, list[dict[str, Any]]] = {}
    groups: dict[str, list[dict[str, Any]]] = {}
    budgets: list[dict[str, Any]] = []
    for chapter_id, inputs in chapter_inputs.items():
        chapter_slots = select_slots(
            chapter_id,
            inputs["events"],
            inputs["evidence_entries"],
        )
        selected[chapter_id] = chapter_slots
        groups[chapter_id] = make_batch_groups(chapter_id, chapter_slots)
        budgets.append(
            build_budget_plan(
                chapter_id,
                selected_count=len(chapter_slots),
                batch_count=len(groups[chapter_id]),
            )
        )

    single_requests = _single_requests(
        selected,
        contracts["knife_a_patch_v1"],
        contract_shas["knife_a_patch_v1"],
    )
    batch_requests = _batch_requests(
        selected,
        groups,
        contracts["knife_a_patch_v1"],
        contracts["atom_batch_v2"],
        contract_shas["atom_batch_v2"],
    )
    all_requests = {**single_requests, **batch_requests}
    leak_hits: list[dict[str, str]] = []
    for relative_path, request in sorted(all_requests.items()):
        for hit in _walk_for_leaks(request["model_visible"]):
            leak_hits.append({"request_path": relative_path, **hit})

    z97_after = {
        "rfu.schema.json": sha256_bytes(reader.read_bytes(Z97_RFU_SCHEMA_PATH)),
        "candidate_claim.schema.json": sha256_bytes(
            reader.read_bytes(Z97_CLAIM_SCHEMA_PATH)
        ),
    }
    p1_ticket = _p1_diff_ticket(
        z97_before,
        z97_after,
        {
            "rfu_v1_hardened": contract_shas["rfu_v1_hardened"],
            "candidate_claim_v1_hardened": contract_shas[
                "candidate_claim_v1_hardened"
            ],
        },
    )
    if p1_ticket["status"] != "PASS":
        raise Z98ContractError("Z97 源 schema 在施工中发生变化")

    selection_receipt = {
        "schema_version": "z98-selection-receipt-v1",
        "rule": {
            "inputs": "retry03 events + frozen evidence catalogs only",
            "risk_formula": (
                "50*anchor_count + 20*marker_hits + 10*punctuation_hits "
                "+ min(nonspace_length,100)"
            ),
            "sort": "risk_score desc, event_id asc",
            "chapter_limit": "min(6, floor(10% * event_count))",
            "anchor_neighborhood": "existing anchor index ±1",
            "manual_selection": False,
        },
        "chapters": {
            chapter_id: {
                "event_count": len(chapter_inputs[chapter_id]["events"]),
                "selected_count": len(slots),
                "selected_slots": slots,
                "batch_groups": groups[chapter_id],
            }
            for chapter_id, slots in selected.items()
        },
        "selected_count_total": sum(len(slots) for slots in selected.values()),
        "single_and_batch_slot_sets_equal": True,
    }
    frozen_task_registry = _frozen_task_registry(
        chapter_inputs,
        selected,
        groups,
    )
    budget_receipt = {
        "schema_version": "z98-budget-receipt-v1",
        "status": "PRE_REGISTERED_NOT_MEASURED",
        "formula_precheck": "PASS",
        "chapters": budgets,
        "transport_envelope": _transport_envelope(budgets),
        "step1_model_api_calls": 0,
        "step1_network_attempts": 0,
        "future_cost_accounting": (
            "Flash与Pro分臂；实际费用只认步二usage和供应商账单"
        ),
    }
    contract_receipt = {
        "schema_version": "z98-contract-sha-receipt-v1",
        "status": "PASS",
        "contracts": [
            {
                "name": name,
                "path": f"contracts/{CONTRACT_PATHS[name].name}",
                "sha256": contract_shas[name],
            }
            for name in sorted(contract_shas)
        ],
        "current_single_object_contract_reference": {
            "path": Z94_SINGLE_CONTRACT_PATH,
            "sha256": sha256_bytes(z94_single_bytes),
            "read_only": True,
            "modified": False,
        },
        "atom_batch_v2_runtime_rules": {
            "item_fields": [
                "slot_id",
                "status",
                "atom",
                "split_span_ids",
                "missing_context_codes",
            ],
            "returned_slot_ids_must_equal_preallocated_slots": True,
            "needs_context_max_expansions_per_slot": 1,
            "context_expansion_counter_is_program_owned": True,
        },
        "authority_contract": {
            "path": "design/authority_contract.json",
            "sha256": sha256_bytes(authority_bytes),
            "sha_boundary": authority_contract["sha_boundary"],
        },
    }
    authority_receipt = {
        "schema_version": "z98-authority-contract-sha-receipt-v1",
        "status": "PASS_LOCAL_FREEZE",
        "path": "design/authority_contract.json",
        "sha256": sha256_bytes(authority_bytes),
        "authority_time": authority_contract["authority"]["authority_time"],
        "unified_design_page_id": authority_contract["authority"][
            "unified_design_page_id"
        ],
        "sha_boundary": authority_contract["sha_boundary"],
    }
    comparison_design = _comparison_design(
        sha256_bytes(z96_bytes),
        sha256_bytes(z94_single_bytes),
    )
    canary_receipt = _run_canaries(
        selected=selected,
        groups=groups,
        budgets=budgets,
        single_requests=single_requests,
        batch_requests=batch_requests,
    )
    if canary_receipt["status"] != "PASS":
        raise Z98ContractError("步一 CANARY 未全过")
    leak_receipt = {
        "schema_version": "z98-model-window-leak-scan-v1",
        "status": "PASS" if not leak_hits else "FAIL",
        "request_count": len(all_requests),
        "forbidden_hit_count": len(leak_hits),
        "hits": leak_hits,
        "source_reader_exact_allowlist": sorted(reader.allowed_paths),
        "source_reader_read_ledger": sorted(
            reader.read_ledger,
            key=lambda row: (row["path"], row["sha256"]),
        ),
    }
    if leak_hits:
        raise Z98ContractError("模型可见请求命中答案面泄漏标记")
    preflight = {
        "schema_version": "z98-step1-preflight-v1",
        "status": "PASS_ZERO_CALL_PREPARED_AWAITING_REVIEW",
        "step2_release_allowed": False,
        "model_api_calls": 0,
        "network_attempts": 0,
        "selected_repairs_by_chapter": {
            chapter_id: len(slots) for chapter_id, slots in selected.items()
        },
        "selected_repairs_total": sum(len(slots) for slots in selected.values()),
        "single_request_count": len(single_requests),
        "batch_request_count": len(batch_requests),
        "same_exam_receipt_pass": same_exam_receipt["status"] == "PASS",
        "leak_scan_pass": leak_receipt["status"] == "PASS",
        "p1_hardening_pass": p1_ticket["status"] == "PASS",
        "canary_pass": canary_receipt["status"] == "PASS",
        "authority_contract_frozen": True,
        "frozen_task_count": frozen_task_registry["task_count"],
        "quality_status": "UNJUDGED",
        "next_action": "统一审收后另令放行步二；本包自身不得发网",
    }

    files: dict[str, bytes] = {}
    files["design/authority_contract.json"] = authority_bytes
    for name, data in contract_bytes.items():
        files[f"contracts/{CONTRACT_PATHS[name].name}"] = data
    json_artifacts = {
        "receipts/same_exam_receipt.json": same_exam_receipt,
        "receipts/selection_receipt.json": selection_receipt,
        "receipts/budget_receipt.json": budget_receipt,
        "receipts/contract_sha_receipt.json": contract_receipt,
        "receipts/authority_contract_sha_receipt.json": authority_receipt,
        "receipts/model_window_leak_scan.json": leak_receipt,
        "receipts/p1_hardening_diff.json": p1_ticket,
        "receipts/canary_receipt.json": canary_receipt,
        "design/comparison_design.json": comparison_design,
        "design/frozen_task_registry.json": frozen_task_registry,
        "preflight.json": preflight,
    }
    json_artifacts.update(all_requests)
    for relative_path, value in json_artifacts.items():
        files[relative_path] = stable_json_bytes(value)
    manifest_rows = [
        {
            "path": path,
            "sha256": sha256_bytes(data),
            "byte_count": len(data),
        }
        for path, data in sorted(files.items())
    ]
    manifest = {
        "schema_version": "z98-step1-bundle-manifest-v1",
        "file_count_excluding_manifest": len(manifest_rows),
        "files": manifest_rows,
    }
    files["bundle_manifest.json"] = stable_json_bytes(manifest)
    for relative_path, data in sorted(files.items()):
        output_path = target / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    return {
        "status": preflight["status"],
        "bundle_root": str(target),
        "file_count": len(files),
        "manifest_sha256": sha256_bytes(files["bundle_manifest.json"]),
        "selected_repairs_by_chapter": preflight[
            "selected_repairs_by_chapter"
        ],
        "single_request_count": len(single_requests),
        "batch_request_count": len(batch_requests),
        "step2_release_allowed": False,
    }
