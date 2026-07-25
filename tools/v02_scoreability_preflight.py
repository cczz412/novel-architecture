#!/usr/bin/env python3
"""V02/C10.1：实验发网前可计分性预检。

本工具只做六项机械检查，不计算实验分数，也不改变既有分母或判据：

1. 双臂都有实发计划；
2. 双臂输出合同相容；
3. 正式分母 SHA 已锁；
4. crosswalk 输入材料能生成；
5. 计分器能用空壳样张完整走通；
6. 每个指标要么能产数，要么缺件已在实验前列入阻断项。

历史 C1 回放直接读取冻结件；缺口不会补成零。未通过预检的材料可以保留
``exploratory_only`` 观察，但禁止登记实验胜负。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
C1_DIR = V02_ROOT / "C_anchor_first_experiment"
DEFAULT_OUTPUT_DIR = V02_ROOT / "V02_C10_scoreability_and_reporting_20260725"

CASE_ORDER = ("B02-U0039", "B03-U0041", "B01-U0033")
CASE_DENOMINATORS = {
    "B02-U0039": 8,
    "B03-U0041": 16,
    "B01-U0033": 25,
}
METRIC_IDS = (
    "ANCHOR_PARTIAL",
    "FCR",
    "QCR_full",
    "ASR_full",
    "UCR",
    "SOP",
)
CHECK_IDS = (
    "BOTH_ARMS_HAVE_DISPATCH_PLANS",
    "OUTPUT_CONTRACTS_ARE_COMPATIBLE",
    "FORMAL_DENOMINATOR_SHA_IS_LOCKED",
    "CROSSWALK_INPUTS_CAN_BE_GENERATED",
    "SCORER_EMPTY_SHELL_COMPLETES_END_TO_END",
    "EVERY_METRIC_NUMERIC_OR_PREDECLARED_BLOCKED",
)
CHECK_RULES_ZH = (
    "双臂都有实发计划",
    "双臂输出合同相容",
    "正式分母 SHA 已锁",
    "crosswalk 输入材料能生成",
    "计分器能用空壳样张完整走通",
    "每个指标要么能产数，要么其缺件已在实验前列入阻断项",
)

SCOREABLE = "SCOREABLE"
NOT_SCOREABLE = "NOT_SCOREABLE"


class ScoreabilityPreflightError(RuntimeError):
    """预检材料不符合合同，不能生成可计分性票。"""


def stable_json_bytes(value: Any) -> bytes:
    """把 JSON 编码为稳定字节。"""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    """计算与键序无关的内容 SHA。"""

    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    """读取文件并计算 SHA-256。"""

    if not path.is_file():
        raise ScoreabilityPreflightError(f"证据文件不存在：{path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    """读取 JSON；格式错误即拒收。"""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreabilityPreflightError(f"不能读取 JSON：{path}") from exc


def _read_ref(
    value: Any,
    evidence_root: Path,
    label: str,
) -> tuple[Mapping[str, Any], dict[str, str]]:
    """回读一份实际文件并核对清单里预锁的 SHA。"""

    if not isinstance(value, Mapping):
        raise ScoreabilityPreflightError(f"{label} 不是文件引用")
    relative = value.get("path")
    expected_sha = value.get("sha256")
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
    ):
        raise ScoreabilityPreflightError(f"{label} 路径不合法")
    if (
        not isinstance(expected_sha, str)
        or len(expected_sha) != 64
        or any(ch not in "0123456789abcdef" for ch in expected_sha)
    ):
        raise ScoreabilityPreflightError(f"{label} 缺合法 SHA-256")
    path = evidence_root / relative
    observed_sha = sha256_file(path)
    if observed_sha != expected_sha:
        raise ScoreabilityPreflightError(f"{label} 实文件 SHA 不匹配")
    document = read_json(path)
    if not isinstance(document, Mapping):
        raise ScoreabilityPreflightError(f"{label} 实文件不是 JSON 对象")
    return document, {
        "path": relative,
        "sha256": observed_sha,
    }


def _required_identity(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScoreabilityPreflightError(f"{label} 缺身份")
    return value.strip()


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ScoreabilityPreflightError(f"{label} 缺时间")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ScoreabilityPreflightError(f"{label} 时间格式不合法") from exc
    if parsed.tzinfo is None:
        raise ScoreabilityPreflightError(f"{label} 必须带时区")
    return parsed


def _normalize_events(
    output: Mapping[str, Any],
    contract: Mapping[str, Any],
    arm_id: str,
) -> list[dict[str, str]]:
    events_key = _required_identity(contract.get("events_key"), "events_key")
    event_id_key = _required_identity(
        contract.get("event_id_key"), "event_id_key"
    )
    atom_id_key = _required_identity(
        contract.get("atom_id_key"), "atom_id_key"
    )
    events = output.get(events_key)
    if not isinstance(events, list) or not events:
        raise ScoreabilityPreflightError(f"{arm_id} 空壳输出没有事件")
    normalized: list[dict[str, str]] = []
    seen_event_ids: set[str] = set()
    for row in events:
        if not isinstance(row, Mapping):
            raise ScoreabilityPreflightError(f"{arm_id} 事件不是对象")
        event_id = _required_identity(row.get(event_id_key), "event_id")
        atom_id = _required_identity(row.get(atom_id_key), "atom_id")
        if event_id in seen_event_ids:
            raise ScoreabilityPreflightError(f"{arm_id} 事件身份重复")
        seen_event_ids.add(event_id)
        normalized.append({"event_id": event_id, "atom_id": atom_id})
    return normalized


def _run_empty_shell_scorer(
    fixture: Mapping[str, Any],
    blockers: Mapping[str, Any],
    earliest_dispatch_at: datetime,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """实际执行一遍最小计数器，并机械验证前置阻断的时序。"""

    raw_inputs = fixture.get("metric_inputs")
    if not isinstance(raw_inputs, Mapping):
        raise ScoreabilityPreflightError("空壳计分输入缺 metric_inputs")
    raw_blockers = blockers.get("blockers")
    if not isinstance(raw_blockers, list):
        raise ScoreabilityPreflightError("前置阻断文件缺 blockers")
    blocker_by_metric: dict[str, Mapping[str, Any]] = {}
    for row in raw_blockers:
        if not isinstance(row, Mapping):
            raise ScoreabilityPreflightError("前置阻断行不是对象")
        metric_id = _required_identity(row.get("metric_id"), "blocker metric_id")
        blocker_id = _required_identity(row.get("blocker_id"), "blocker_id")
        declared_at = _parse_time(row.get("declared_at"), "blocker declared_at")
        if declared_at >= earliest_dispatch_at:
            raise ScoreabilityPreflightError(f"{metric_id} 阻断项不是发网前登记")
        if metric_id in blocker_by_metric:
            raise ScoreabilityPreflightError(f"{metric_id} 阻断项重复")
        blocker_by_metric[metric_id] = {
            **row,
            "blocker_id": blocker_id,
        }

    results: dict[str, dict[str, Any]] = {}
    states: dict[str, str] = {}
    for metric_id in METRIC_IDS:
        values = raw_inputs.get(metric_id)
        if isinstance(values, list) and values and all(
            isinstance(value, bool) for value in values
        ):
            results[metric_id] = {
                "metric_id": metric_id,
                "status": "NUMERIC_READY",
                "numerator": sum(values),
                "denominator": len(values),
            }
            states[metric_id] = "NUMERIC_READY"
        elif metric_id in blocker_by_metric:
            results[metric_id] = {
                "metric_id": metric_id,
                "status": "BLOCKED_PREDECLARED",
                "blocker_id": blocker_by_metric[metric_id]["blocker_id"],
            }
            states[metric_id] = "BLOCKED_PREDECLARED"
        else:
            results[metric_id] = {
                "metric_id": metric_id,
                "status": "MISSING_UNDECLARED",
            }
            states[metric_id] = "MISSING_UNDECLARED"
    return results, states


def _check_row(
    check_id: str,
    passed: bool,
    evidence: Mapping[str, Any],
    failure_reason: str | None = None,
) -> dict[str, Any]:
    rule_text = CHECK_RULES_ZH[CHECK_IDS.index(check_id)]
    row: dict[str, Any] = {
        "check_id": check_id,
        "rule_text_exact": rule_text,
        "passed": passed,
        "evidence": dict(evidence),
    }
    if not passed:
        row["failure_reason"] = failure_reason or "UNSPECIFIED"
    return row


def evaluate_manifest(
    document: Mapping[str, Any],
    evidence_root: Path,
) -> dict[str, Any]:
    """回读真实文件并按六项固定合同机械检查。"""

    if document.get("schema_version") != "v02-scoreability-preflight-input.v1":
        raise ScoreabilityPreflightError("预检清单 schema_version 不受支持")

    experiment_id = _required_identity(
        document.get("experiment_id"), "experiment_id"
    )
    arms = document.get("arms")
    if not isinstance(arms, list) or len(arms) != 2:
        raise ScoreabilityPreflightError("预检必须恰好登记两臂")
    if not all(isinstance(row, Mapping) for row in arms):
        raise ScoreabilityPreflightError("arm 不是对象")
    arm_ids = [
        _required_identity(row.get("arm_id"), "arm_id") for row in arms
    ]
    if len(set(arm_ids)) != 2:
        raise ScoreabilityPreflightError("两臂身份必须唯一")

    plan_payloads: list[Mapping[str, Any]] = []
    contract_payloads: list[Mapping[str, Any]] = []
    output_payloads: list[Mapping[str, Any]] = []
    plan_refs: list[dict[str, str]] = []
    contract_refs: list[dict[str, str]] = []
    output_refs: list[dict[str, str]] = []
    for arm in arms:
        arm_id = _required_identity(arm.get("arm_id"), "arm_id")
        plan, plan_ref = _read_ref(
            arm.get("dispatch_plan_ref"),
            evidence_root,
            f"{arm_id} dispatch_plan",
        )
        contract, contract_ref = _read_ref(
            arm.get("output_contract_ref"),
            evidence_root,
            f"{arm_id} output_contract",
        )
        output, output_ref = _read_ref(
            arm.get("output_fixture_ref"),
            evidence_root,
            f"{arm_id} output_fixture",
        )
        if (
            plan.get("arm_id") != arm_id
            or contract.get("arm_id") != arm_id
            or output.get("arm_id") != arm_id
        ):
            raise ScoreabilityPreflightError(f"{arm_id} 外层与实文件身份不一致")
        plan_payloads.append(plan)
        contract_payloads.append(contract)
        output_payloads.append(output)
        plan_refs.append(plan_ref)
        contract_refs.append(contract_ref)
        output_refs.append(output_ref)

    dispatch_times: list[datetime] = []
    plans_ready = True
    planned_request_counts: list[int] = []
    for arm_id, payload in zip(arm_ids, plan_payloads, strict=True):
        dispatch_times.append(
            _parse_time(payload.get("frozen_at"), f"{arm_id} frozen_at")
        )
        requests = payload.get("requests")
        if not isinstance(requests, list) or not requests:
            plans_ready = False
            planned_request_counts.append(0)
            continue
        request_ids: list[str] = []
        for row in requests:
            if not isinstance(row, Mapping):
                plans_ready = False
                continue
            request_ids.append(
                _required_identity(row.get("request_id"), "request_id")
            )
            body_sha = row.get("body_sha256")
            if (
                not isinstance(body_sha, str)
                or len(body_sha) != 64
                or any(ch not in "0123456789abcdef" for ch in body_sha)
            ):
                plans_ready = False
        if len(request_ids) != len(set(request_ids)):
            plans_ready = False
        if payload.get("arm_id") != arm_id:
            plans_ready = False
        planned_request_counts.append(len(requests))
    check_plans = _check_row(
        CHECK_IDS[0],
        plans_ready,
        {
            "arm_ids": arm_ids,
            "planned_request_counts": planned_request_counts,
            "plan_files": plan_refs,
        },
        "至少一臂没有冻结且非空的实发计划",
    )

    normalized_shapes = [
        payload.get("normalized_score_shape")
        for payload in contract_payloads
    ]
    adapter_ids = {
        _required_identity(payload.get("scorer_adapter_id"), "scorer_adapter_id")
        for payload in contract_payloads
    }
    contracts_compatible = (
        len(normalized_shapes) == 2
        and isinstance(normalized_shapes[0], list)
        and normalized_shapes[0] == normalized_shapes[1]
        and normalized_shapes[0] == ["atom_id", "event_id"]
        and len(adapter_ids) == 1
    )
    check_contracts = _check_row(
        CHECK_IDS[1],
        contracts_compatible,
        {
            "normalized_score_shapes": normalized_shapes,
            "scorer_adapter_ids": sorted(adapter_ids),
            "contract_files": contract_refs,
        },
        "两臂没有冻结到同一计分形状与同一适配器",
    )

    denominator, denominator_ref = _read_ref(
        document.get("formal_denominator_ref"),
        evidence_root,
        "formal_denominator",
    )
    chapters = denominator.get("chapters")
    denominator_case_ids: list[str] = []
    atom_ids: list[str] = []
    denominator_rows_valid = isinstance(chapters, list) and bool(chapters)
    if isinstance(chapters, list):
        for row in chapters:
            if not isinstance(row, Mapping):
                denominator_rows_valid = False
                continue
            denominator_case_ids.append(
                _required_identity(row.get("case_id"), "denominator case_id")
            )
            raw_atom_ids = row.get("atom_ids")
            if not isinstance(raw_atom_ids, list) or not raw_atom_ids:
                denominator_rows_valid = False
                continue
            atom_ids.extend(
                _required_identity(atom_id, "atom_id")
                for atom_id in raw_atom_ids
            )
    denominator_ready = (
        denominator_rows_valid
        and len(denominator_case_ids) == len(set(denominator_case_ids))
        and len(atom_ids) == len(set(atom_ids))
        and len(atom_ids) == denominator.get("total")
    )
    check_denominator = _check_row(
        CHECK_IDS[2],
        denominator_ready,
        {
            "denominator_file": denominator_ref,
            "chapter_total": len(denominator_case_ids),
            "formal_denominator_total": denominator.get("total"),
            "recomputed_atom_total": len(atom_ids),
        },
        "正式分母没有以可复验 SHA 锁定，或章级分母与总分母不一致",
    )

    generator_identity, generator_ref = _read_ref(
        document.get("crosswalk_generator_identity_ref"),
        evidence_root,
        "crosswalk_generator_identity",
    )
    expected_tool_sha = sha256_file(Path(__file__))
    generator_code_matches = (
        generator_identity.get("module_path")
        == "tools/v02_scoreability_preflight.py"
        and generator_identity.get("module_sha256") == expected_tool_sha
    )
    normalized_outputs: dict[str, list[dict[str, str]]] = {}
    crosswalk_ready = denominator_ready and contracts_compatible
    for arm_id, output, contract in zip(
        arm_ids, output_payloads, contract_payloads, strict=True
    ):
        try:
            normalized = _normalize_events(output, contract, arm_id)
        except ScoreabilityPreflightError:
            normalized = []
            crosswalk_ready = False
        if any(row["atom_id"] not in set(atom_ids) for row in normalized):
            crosswalk_ready = False
        normalized_outputs[arm_id] = normalized
    crosswalk_ready = (
        crosswalk_ready
        and generator_code_matches
        and all(normalized_outputs.values())
    )
    check_crosswalk = _check_row(
        CHECK_IDS[3],
        crosswalk_ready,
        {
            "generator_identity_file": generator_ref,
            "generator_code_matches": generator_code_matches,
            "output_files": output_refs,
            "normalized_row_counts": {
                arm_id: len(rows)
                for arm_id, rows in normalized_outputs.items()
            },
            "scoring_atom_total": len(atom_ids),
        },
        "crosswalk 缺任一双臂输出或计分原子输入，或实际归一失败",
    )

    scorer_fixture, scorer_fixture_ref = _read_ref(
        document.get("scorer_empty_shell_ref"),
        evidence_root,
        "scorer_empty_shell",
    )
    blockers, blocker_ref = _read_ref(
        document.get("predeclared_blockers_ref"),
        evidence_root,
        "predeclared_blockers",
    )
    earliest_dispatch_at = min(dispatch_times)
    scorer_results, metric_states = _run_empty_shell_scorer(
        scorer_fixture,
        blockers,
        earliest_dispatch_at,
    )
    scorer_ready = set(scorer_results) == set(METRIC_IDS)
    check_scorer = _check_row(
        CHECK_IDS[4],
        scorer_ready,
        {
            "scorer_fixture_file": scorer_fixture_ref,
            "generator_code_sha256": expected_tool_sha,
            "complete_path_reached": scorer_ready,
            "metrics_produced": sorted(scorer_results),
        },
        "空壳样张没有走完整计分路径并产出六项指标槽位",
    )

    metric_coverage_ready = set(metric_states) == set(METRIC_IDS) and all(
        status in {"NUMERIC_READY", "BLOCKED_PREDECLARED"}
        for status in metric_states.values()
    )
    check_metrics = _check_row(
        CHECK_IDS[5],
        metric_coverage_ready,
        {
            "metric_states": metric_states,
            "predeclared_blocker_file": blocker_ref,
            "scorer_results": scorer_results,
        },
        "至少一项指标既不能产数，也未在实验前登记为阻断项",
    )

    checks = [
        check_plans,
        check_contracts,
        check_denominator,
        check_crosswalk,
        check_scorer,
        check_metrics,
    ]
    all_checks_pass = all(row["passed"] for row in checks)
    all_metrics_numeric = (
        set(metric_states) == set(METRIC_IDS)
        and set(metric_states.values()) == {"NUMERIC_READY"}
    )
    exploratory_only = bool(document.get("exploratory_only"))
    scoreable = all_checks_pass and all_metrics_numeric and not exploratory_only
    return {
        "schema_version": "v02-scoreability-preflight-receipt.v1",
        "experiment_id": experiment_id,
        "status": SCOREABLE if scoreable else NOT_SCOREABLE,
        "checks": checks,
        "all_six_mechanical_checks_pass": all_checks_pass,
        "all_metrics_numeric_ready": all_metrics_numeric,
        "exploratory_only": exploratory_only or not scoreable,
        "quality_verdict_allowed": False,
        "winner_or_gate_result_allowed": False,
        "separate_quality_authority_required": True,
        "missing_values_zero_filled": False,
    }


def _canonical_request_sha(request: Mapping[str, Any]) -> str:
    return canonical_sha(request)


def _verify_c1_request_rows(
    lock: Mapping[str, Any],
    key: str,
) -> tuple[bool, list[dict[str, Any]]]:
    rows = lock.get(key)
    evidence: list[dict[str, Any]] = []
    if not isinstance(rows, list) or len(rows) != len(CASE_ORDER):
        return False, evidence
    for row in rows:
        if not isinstance(row, Mapping):
            return False, evidence
        case_id = str(row.get("case_id"))
        relpath = row.get("path")
        if case_id not in CASE_ORDER or not isinstance(relpath, str):
            return False, evidence
        path = C1_DIR / relpath
        request = read_json(path)
        observed = _canonical_request_sha(request)
        evidence.append(
            {
                "case_id": case_id,
                "path": path.relative_to(ROOT).as_posix(),
                "locked_identity_sha256": row.get("sha256"),
                "observed_identity_sha256": observed,
                "matches": observed == row.get("sha256"),
            }
        )
    return (
        [row["case_id"] for row in evidence] == list(CASE_ORDER)
        and all(row["matches"] for row in evidence),
        evidence,
    )


def _extract_output_contract_ids(request: Mapping[str, Any]) -> set[str]:
    body = request.get("body")
    if not isinstance(body, Mapping):
        return set()
    messages = body.get("messages")
    if not isinstance(messages, list):
        return set()
    text = "\n".join(
        str(row.get("content", ""))
        for row in messages
        if isinstance(row, Mapping)
    )
    identities = {
        identity
        for identity in ("z-event-v1", "closed_anchor_alignment.v1")
        if identity in text
    }
    return identities


def replay_c1() -> dict[str, Any]:
    """对 C1 历史冻结件执行六项回放，必须停在 NOT_SCOREABLE。"""

    request_lock_path = C1_DIR / "request_lock.json"
    source_manifest_path = C1_DIR / "source_manifest.json"
    score_template_path = C1_DIR / "gate/offline_score_template.json"
    preflight_path = C1_DIR / "c1_preflight.json"

    lock = read_json(request_lock_path)
    control_ok, control_rows = _verify_c1_request_rows(
        lock, "control_requests"
    )
    treatment_ok, treatment_rows = _verify_c1_request_rows(
        lock, "anchor_first_requests"
    )
    planned = lock.get("planned_calls")
    plans_ready = (
        control_ok
        and treatment_ok
        and isinstance(planned, Mapping)
        and planned.get("control") == 3
        and planned.get("anchor_first") == 3
    )
    check_plans = _check_row(
        CHECK_IDS[0],
        plans_ready,
        {
            "request_lock_sha256": sha256_file(request_lock_path),
            "control_requests": control_rows,
            "treatment_requests": treatment_rows,
            "planned_calls": planned,
        },
        "C1 双臂实发计划或请求锁不完整",
    )

    control_contracts: set[str] = set()
    treatment_contracts: set[str] = set()
    for row in control_rows:
        control_contracts.update(
            _extract_output_contract_ids(read_json(ROOT / row["path"]))
        )
    for row in treatment_rows:
        treatment_contracts.update(
            _extract_output_contract_ids(read_json(ROOT / row["path"]))
        )
    compatibility_bridge = C1_DIR / "contracts/output_score_compatibility.json"
    contracts_compatible = (
        control_contracts == treatment_contracts
        and len(control_contracts) == 1
    ) or compatibility_bridge.is_file()
    check_contracts = _check_row(
        CHECK_IDS[1],
        contracts_compatible,
        {
            "control_contract_ids": sorted(control_contracts),
            "treatment_contract_ids": sorted(treatment_contracts),
            "compatibility_bridge_path": (
                compatibility_bridge.relative_to(ROOT).as_posix()
            ),
            "compatibility_bridge_exists": compatibility_bridge.is_file(),
        },
        "C1 两臂输出合同不同，且没有冻结的共同计分适配桥",
    )

    manifest = read_json(source_manifest_path)
    manifest_rows = manifest.get("chapters")
    denominator_ready = (
        manifest.get("offline_denominator") == 49
        and isinstance(manifest_rows, list)
        and [row.get("case_id") for row in manifest_rows] == list(CASE_ORDER)
        and sum(int(row.get("formal_denominator", 0)) for row in manifest_rows)
        == 49
    )
    gold_bindings: list[dict[str, Any]] = []
    if isinstance(manifest_rows, list):
        for row in manifest_rows:
            gold = row.get("formal_gold")
            pointer = row.get("gold_pointer")
            if not isinstance(gold, Mapping) or not isinstance(pointer, Mapping):
                denominator_ready = False
                continue
            gold_path = ROOT / str(gold.get("path"))
            pointer_path = ROOT / str(pointer.get("path"))
            gold_match = sha256_file(gold_path) == gold.get("sha256")
            pointer_match = sha256_file(pointer_path) == pointer.get("sha256")
            denominator_ready = denominator_ready and gold_match and pointer_match
            gold_bindings.append(
                {
                    "case_id": row.get("case_id"),
                    "formal_denominator": row.get("formal_denominator"),
                    "formal_gold_sha_matches": gold_match,
                    "gold_pointer_sha_matches": pointer_match,
                }
            )
    check_denominator = _check_row(
        CHECK_IDS[2],
        denominator_ready,
        {
            "source_manifest_sha256": sha256_file(source_manifest_path),
            "offline_score_template_sha256": sha256_file(score_template_path),
            "formal_denominator_total": manifest.get("offline_denominator"),
            "bindings": gold_bindings,
        },
        "C1 正式分母或金标身份锁漂移",
    )

    outputs_absent = lock.get("c2_output_lock_state") == (
        "not_created_zero_call_c1"
    )
    check_crosswalk = _check_row(
        CHECK_IDS[3],
        False,
        {
            "c2_output_lock_state": lock.get("c2_output_lock_state"),
            "control_output_available": not outputs_absent,
            "treatment_output_available": not outputs_absent,
            "crosswalk_generator_input_complete": False,
        },
        "C1 只有双臂请求，没有双臂输出，crosswalk 输入不能生成",
    )

    template = read_json(score_template_path)
    null_slots: list[str] = []
    chapters = template.get("chapters")
    if isinstance(chapters, Mapping):
        for case_id in CASE_ORDER:
            chapter = chapters.get(case_id)
            if not isinstance(chapter, Mapping):
                null_slots.append(f"{case_id}:chapter")
                continue
            if chapter.get("failure_counts", {}).get("ANCHOR_PARTIAL") is None:
                null_slots.append(f"{case_id}:ANCHOR_PARTIAL")
            layers = chapter.get("layers")
            if isinstance(layers, Mapping):
                for metric in METRIC_IDS[1:]:
                    row = layers.get(metric)
                    if not isinstance(row, Mapping) or row.get("passed") is None:
                        null_slots.append(f"{case_id}:{metric}")
            if chapter.get("model_api_calls") is None:
                null_slots.append(f"{case_id}:model_api_calls")
    check_scorer = _check_row(
        CHECK_IDS[4],
        False,
        {
            "offline_score_template_sha256": sha256_file(score_template_path),
            "null_slot_total": len(null_slots),
            "null_slots": null_slots,
            "complete_path_reached": False,
        },
        "C1 空壳模板保留空值，不能完整走到计分收口",
    )

    c1_preflight = read_json(preflight_path)
    known_blockers = c1_preflight.get("c2_known_local_hold_reasons")
    per_metric_states = {
        metric: "MISSING_NOT_PREDECLARED_AS_METRIC_BLOCKER"
        for metric in METRIC_IDS
    }
    check_metrics = _check_row(
        CHECK_IDS[5],
        False,
        {
            "c1_preflight_sha256": sha256_file(preflight_path),
            "known_preflight_holds": known_blockers,
            "metric_states": per_metric_states,
            "metric_blockers_declared_before_dispatch": [],
        },
        "C1 没有在实验前逐指标登记缺件阻断项",
    )

    checks = [
        check_plans,
        check_contracts,
        check_denominator,
        check_crosswalk,
        check_scorer,
        check_metrics,
    ]
    if all(row["passed"] for row in checks):
        raise ScoreabilityPreflightError("C1 历史回放意外变为可计分")
    return {
        "schema_version": "v02-scoreability-preflight-receipt.v1",
        "experiment_id": "C1_HISTORICAL_REPLAY",
        "status": NOT_SCOREABLE,
        "checks": checks,
        "passed_check_total": sum(1 for row in checks if row["passed"]),
        "failed_check_total": sum(1 for row in checks if not row["passed"]),
        "all_six_mechanical_checks_pass": False,
        "all_metrics_numeric_ready": False,
        "exploratory_only": True,
        "exploratory_observations_may_be_retained": True,
        "quality_verdict_allowed": False,
        "winner_or_gate_result_allowed": False,
        "missing_values_zero_filled": False,
        "historical_scores_rewritten": False,
    }


def scoreability_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-scoreability-preflight-contract.v1",
        "check_order": [
            {
                "check_id": CHECK_IDS[0],
                "rule_text_exact": CHECK_RULES_ZH[0],
            },
            {
                "check_id": CHECK_IDS[1],
                "rule_text_exact": CHECK_RULES_ZH[1],
            },
            {
                "check_id": CHECK_IDS[2],
                "rule_text_exact": CHECK_RULES_ZH[2],
            },
            {
                "check_id": CHECK_IDS[3],
                "rule_text_exact": CHECK_RULES_ZH[3],
            },
            {
                "check_id": CHECK_IDS[4],
                "rule_text_exact": CHECK_RULES_ZH[4],
            },
            {
                "check_id": CHECK_IDS[5],
                "rule_text_exact": CHECK_RULES_ZH[5],
            },
        ],
        "metric_ids": list(METRIC_IDS),
        "status_enum": [SCOREABLE, NOT_SCOREABLE],
        "scoreable_rule": (
            "六项全过、六项指标全为 NUMERIC_READY，且不是 exploratory_only；"
            "本票仍不授予质量胜负权限。"
        ),
        "not_scoreable_rule": (
            "任一检查失败、任一指标仍受阻，或明确 exploratory_only，"
            "均禁止胜负与过闸结论。"
        ),
        "missing_value_policy": "缺失不得补零。",
    }


def _example_evidence_documents() -> dict[str, Mapping[str, Any]]:
    documents: dict[str, Mapping[str, Any]] = {}
    for arm_id, prefix in (("control", "C"), ("treatment", "T")):
        documents[f"example_evidence/dispatch_{arm_id}.json"] = {
            "schema_version": "v02-dispatch-plan-fixture.v1",
            "arm_id": arm_id,
            "frozen_at": "2026-07-25T00:00:00+08:00",
            "requests": [
                {
                    "request_id": f"{prefix}-REQ-001",
                    "body_sha256": hashlib.sha256(
                        f"{arm_id}-request".encode("utf-8")
                    ).hexdigest(),
                }
            ],
        }
        documents[f"example_evidence/contract_{arm_id}.json"] = {
            "schema_version": "v02-output-adapter-fixture.v1",
            "arm_id": arm_id,
            "events_key": "events",
            "event_id_key": "event_id",
            "atom_id_key": "atom_id",
            "normalized_score_shape": ["atom_id", "event_id"],
            "scorer_adapter_id": "c10-empty-shell-adapter.v1",
        }
        documents[f"example_evidence/output_{arm_id}.json"] = {
            "schema_version": "v02-output-fixture.v1",
            "arm_id": arm_id,
            "events": [
                {"event_id": f"{prefix}-EV-001", "atom_id": "SYN-A01"},
                {"event_id": f"{prefix}-EV-002", "atom_id": "SYN-A02"},
                {"event_id": f"{prefix}-EV-003", "atom_id": "SYN-A03"},
            ],
        }
    documents["example_evidence/formal_denominator.json"] = {
        "schema_version": "v02-denominator-fixture.v1",
        "chapters": [
            {"case_id": "SYN-01", "atom_ids": ["SYN-A01"]},
            {"case_id": "SYN-02", "atom_ids": ["SYN-A02"]},
            {"case_id": "SYN-03", "atom_ids": ["SYN-A03"]},
        ],
        "total": 3,
    }
    documents["example_evidence/generator_identity.json"] = {
        "schema_version": "v02-generator-identity.v1",
        "module_path": "tools/v02_scoreability_preflight.py",
        "module_sha256": sha256_file(Path(__file__)),
    }
    documents["example_evidence/scorer_empty_shell.json"] = {
        "schema_version": "v02-scorer-empty-shell-fixture.v1",
        "metric_inputs": {
            metric_id: [True, True, False] for metric_id in METRIC_IDS
        },
    }
    documents["example_evidence/predeclared_blockers.json"] = {
        "schema_version": "v02-predeclared-blockers.v1",
        "blockers": [],
    }
    return documents


def _reference_for(
    name: str,
    raw_documents: Mapping[str, bytes],
) -> dict[str, str]:
    return {
        "path": name,
        "sha256": hashlib.sha256(raw_documents[name]).hexdigest(),
    }


def scoreable_example_input(
    raw_documents: Mapping[str, bytes],
) -> dict[str, Any]:
    arms = [
        {
            "arm_id": arm_id,
            "dispatch_plan_ref": _reference_for(
                f"example_evidence/dispatch_{arm_id}.json",
                raw_documents,
            ),
            "output_contract_ref": _reference_for(
                f"example_evidence/contract_{arm_id}.json",
                raw_documents,
            ),
            "output_fixture_ref": _reference_for(
                f"example_evidence/output_{arm_id}.json",
                raw_documents,
            ),
        }
        for arm_id in ("control", "treatment")
    ]
    return {
        "schema_version": "v02-scoreability-preflight-input.v1",
        "experiment_id": "SYNTHETIC_SCOREABLE_EXAMPLE",
        "arms": arms,
        "formal_denominator_ref": _reference_for(
            "example_evidence/formal_denominator.json",
            raw_documents,
        ),
        "crosswalk_generator_identity_ref": _reference_for(
            "example_evidence/generator_identity.json",
            raw_documents,
        ),
        "scorer_empty_shell_ref": _reference_for(
            "example_evidence/scorer_empty_shell.json",
            raw_documents,
        ),
        "predeclared_blockers_ref": _reference_for(
            "example_evidence/predeclared_blockers.json",
            raw_documents,
        ),
        "exploratory_only": False,
        "synthetic_fixture_only": True,
    }


def _static_artifacts() -> dict[str, bytes]:
    raw = {
        name: stable_json_bytes(document)
        for name, document in _example_evidence_documents().items()
    }
    example = scoreable_example_input(raw)
    raw.update(
        {
            "scoreability_preflight_contract.json": stable_json_bytes(
                scoreability_contract()
            ),
            "scoreable_example_input.json": stable_json_bytes(example),
            "c1_historical_replay_receipt.json": stable_json_bytes(replay_c1()),
        }
    )
    return raw


def write_or_verify(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    """写出合同与回放票；重复执行必须逐字一致。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    shas: dict[str, str] = {}
    artifacts = _static_artifacts()
    for name, raw in artifacts.items():
        path = output_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ScoreabilityPreflightError(f"既有产物字节不一致：{path}")
        path.write_bytes(raw)
        shas[name] = hashlib.sha256(raw).hexdigest()
    example = read_json(output_dir / "scoreable_example_input.json")
    receipt = evaluate_manifest(example, output_dir)
    receipt["synthetic_fixture_only"] = True
    receipt["quality_verdict_allowed"] = False
    receipt["winner_or_gate_result_allowed"] = False
    receipt_raw = stable_json_bytes(receipt)
    receipt_path = output_dir / "scoreable_example_receipt.json"
    if receipt_path.exists() and receipt_path.read_bytes() != receipt_raw:
        raise ScoreabilityPreflightError(
            f"既有产物字节不一致：{receipt_path}"
        )
    receipt_path.write_bytes(receipt_raw)
    shas["scoreable_example_receipt.json"] = hashlib.sha256(
        receipt_raw
    ).hexdigest()
    return shas


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="合同与回放票输出目录",
    )
    parser.add_argument(
        "--check-manifest",
        type=Path,
        help="另行检查一份 v02-scoreability-preflight-input.v1 清单",
    )
    args = parser.parse_args(argv)
    if args.check_manifest:
        receipt = evaluate_manifest(
            read_json(args.check_manifest),
            args.check_manifest.parent,
        )
        print(stable_json_bytes(receipt).decode("utf-8"), end="")
        return 0 if receipt["status"] == SCOREABLE else 2
    print(
        json.dumps(
            write_or_verify(args.output_dir),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
