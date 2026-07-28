#!/usr/bin/env python3
"""V02/C12.8：锚目录负载悬崖只读诊断。

本件只把 C2～C6 的历史调用按同一字段口径重建成机械账。
它不拟合曲线、不宣布阈值、不推翻 C6.4，也不登记质量胜负。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "tools").is_dir():
            return parent
    raise RuntimeError("无法定位小说架构仓库根目录")


ROOT = _find_repo_root()
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
TASK_ROOT = V02_ROOT / "V02_C12_8_anchor_catalog_load_diagnosis_20260725"
DEFAULT_OUTPUT_DIR = TASK_ROOT / "artifacts"
SELF_PATH = Path(__file__).resolve()

C2_RUN = ROOT / "runs/V02_实验A锚先行倒装_C2_r01_20260725"
C3_RUN = ROOT / "runs/V02_实验A锚先行倒装_C3_r02_20260725"
C4_RUN = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
C5_RUN = ROOT / "runs/V02_实验A锚先行倒装_C5稳定性_r04_20260725"
C6_RUN = ROOT / "runs/V02_实验A锚先行倒装_C6对照臂_r05_20260725"

CATALOG_SHA = {
    "B01-U0033": "136c903418c45fea56d5a0298a444f906d057488e9552b52d6acc50c930356fa",
    "B02-U0039": "c903e830197f13ea784d9542e3fb37580687bbc13ebb5f83bb3d41eab86c11a5",
    "B03-U0041": "c009880d31247cb356d2dd541e10609fc7956ec747ce44f89c337d6ac48f48fc",
}


def _sample_root(run: Path, phase: str, case_id: str) -> Path:
    return run / "samples" / phase / case_id


def _spec(
    *,
    call_id: str,
    run: Path,
    phase: str,
    case_id: str,
    contract_family: str,
    comparison_role: str,
    attempt_sha: str,
    result_path: Path,
    result_sha: str,
    result_mode: str,
    catalog_path: Path,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    root = _sample_root(run, phase, case_id)
    return {
        "call_id": call_id,
        "run_id": run.name,
        "phase": phase,
        "case_id": case_id,
        "contract_family": contract_family,
        "comparison_role": comparison_role,
        "attempt_path": root / "transport/call_attempts.jsonl",
        "attempt_sha256": attempt_sha,
        "request_path": root / "transport/request.json",
        "raw_response_path": root / "transport/raw_responses/attempt01.json",
        "result_path": result_path,
        "result_sha256": result_sha,
        "result_mode": result_mode,
        "catalog_path": catalog_path,
        "catalog_sha256": CATALOG_SHA[case_id],
        "expected": dict(expected),
    }


CALL_SPECS = (
    _spec(
        call_id="C2-B02",
        run=C2_RUN,
        phase="main",
        case_id="B02-U0039",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="transport_and_contract_history",
        attempt_sha="79c31e3fd65904d8bc6715bc5b1ff92223c08f6fe13415e8a3e4f503d5683c9e",
        result_path=C2_RUN / "hard_stop.json",
        result_sha="fef91c7a1f7b05dade2a3501bd76c2fe6efd2930fe80ec3ea8c22af71f47d3c9",
        result_mode="rejected_full_json",
        catalog_path=C2_RUN / "prepared/catalogs/B02-U0039.json",
        expected={
            "prompt_tokens": 6655,
            "completion_tokens": 13894,
            "reasoning_tokens": 12501,
            "finish_reason": "stop",
            "event_count": 9,
            "selected_anchor_reference_count": 18,
            "claim_span_violation_count": 5,
        },
    ),
    _spec(
        call_id="C3-B02",
        run=C3_RUN,
        phase="main",
        case_id="B02-U0039",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="transport_and_contract_history",
        attempt_sha="4baeb75887d7f3ec4b7cc46cb4e856445d5c02587ecb91964bd78d3b825475d7",
        result_path=C3_RUN / "hard_stop.json",
        result_sha="ce4fed0ac091ab6d7c53a8136c764091c6921dd6fc1f2d207c9d5c11b3691dbd",
        result_mode="truncated_no_salvage",
        catalog_path=C3_RUN / "prepared/catalogs/B02-U0039.json",
        expected={
            "prompt_tokens": 6833,
            "completion_tokens": 16001,
            "reasoning_tokens": 14199,
            "finish_reason": "length",
            "event_count": None,
            "selected_anchor_reference_count": None,
            "claim_span_violation_count": None,
        },
    ),
    _spec(
        call_id="C4-B01",
        run=C4_RUN,
        phase="main",
        case_id="B01-U0033",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="same_contract_core",
        attempt_sha="215b60969d9528945ef74abebaa2425fb01b2d13381aa1c65648fc48d46a5dd9",
        result_path=_sample_root(C4_RUN, "main", "B01-U0033")
        / "mechanical.json",
        result_sha="78875ce606cc47dde5c42cb77fc2aa04346930c93373c597b4ff78aebeb470ab",
        result_mode="accepted_mechanical",
        catalog_path=C4_RUN / "prepared/catalogs/B01-U0033.json",
        expected={
            "prompt_tokens": 23636,
            "completion_tokens": 14438,
            "reasoning_tokens": 12406,
            "finish_reason": "stop",
            "event_count": 14,
            "selected_anchor_reference_count": 52,
            "claim_span_violation_count": 0,
        },
    ),
    _spec(
        call_id="C4-B02",
        run=C4_RUN,
        phase="main",
        case_id="B02-U0039",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="same_contract_core",
        attempt_sha="a00e343008e81f0ebbec0ee135d08d8b3d178296b089e5e55798c1f693d35f3f",
        result_path=_sample_root(C4_RUN, "main", "B02-U0039")
        / "mechanical.json",
        result_sha="007705372365db542fd1334ce0b6dd3c37dce29fddfb2497face394bbcd4a6b4",
        result_mode="accepted_mechanical",
        catalog_path=C4_RUN / "prepared/catalogs/B02-U0039.json",
        expected={
            "prompt_tokens": 6833,
            "completion_tokens": 16472,
            "reasoning_tokens": 14696,
            "finish_reason": "stop",
            "event_count": 13,
            "selected_anchor_reference_count": 25,
            "claim_span_violation_count": 0,
        },
    ),
    _spec(
        call_id="C4-B03",
        run=C4_RUN,
        phase="main",
        case_id="B03-U0041",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="same_contract_core",
        attempt_sha="614c64cff929fe951815b5a1d30d469920354f6bba3c554887c3c9cac131a3b7",
        result_path=_sample_root(C4_RUN, "main", "B03-U0041")
        / "mechanical.json",
        result_sha="5a0fea9447498059d43d3d75d30c6c2c62fe231d97552f8a3445956440f8babb",
        result_mode="accepted_mechanical",
        catalog_path=C4_RUN / "prepared/catalogs/B03-U0041.json",
        expected={
            "prompt_tokens": 8218,
            "completion_tokens": 12558,
            "reasoning_tokens": 11520,
            "finish_reason": "stop",
            "event_count": 10,
            "selected_anchor_reference_count": 12,
            "claim_span_violation_count": 0,
        },
    ),
    _spec(
        call_id="C5-B01",
        run=C5_RUN,
        phase="stability",
        case_id="B01-U0033",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="same_contract_core",
        attempt_sha="3310132f117ce382d3381d2c960f988901f5b4b911657d533090df9beefb9e25",
        result_path=C5_RUN / "hard_stop.json",
        result_sha="a34ccba9d33a52ec0e458c65b9707e9240dd60072fbba3eec66121b0f2aaf297",
        result_mode="rejected_full_json",
        catalog_path=C4_RUN / "prepared/catalogs/B01-U0033.json",
        expected={
            "prompt_tokens": 23636,
            "completion_tokens": 16905,
            "reasoning_tokens": 13864,
            "finish_reason": "stop",
            "event_count": 17,
            "selected_anchor_reference_count": 37,
            "claim_span_violation_count": 10,
        },
    ),
    _spec(
        call_id="C5-B02",
        run=C5_RUN,
        phase="stability",
        case_id="B02-U0039",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="same_contract_core",
        attempt_sha="937280d6811a2458172ca9d73b80b67b0bcf596d8beb3b3928c2bfcd3807b70e",
        result_path=_sample_root(C5_RUN, "stability", "B02-U0039")
        / "mechanical.json",
        result_sha="391d2958a92c32fbdf2d3587150fb98457e6830f1c2c90d640a499d00b474151",
        result_mode="accepted_mechanical",
        catalog_path=C4_RUN / "prepared/catalogs/B02-U0039.json",
        expected={
            "prompt_tokens": 6833,
            "completion_tokens": 12743,
            "reasoning_tokens": 11549,
            "finish_reason": "stop",
            "event_count": 10,
            "selected_anchor_reference_count": 14,
            "claim_span_violation_count": 0,
        },
    ),
    _spec(
        call_id="C5-B03",
        run=C5_RUN,
        phase="stability",
        case_id="B03-U0041",
        contract_family="closed_anchor_alignment_v1",
        comparison_role="same_contract_core",
        attempt_sha="54080fb764b63809de2b27c141e9bb154dc843c34eb041db2bfdcf228b68e241",
        result_path=_sample_root(C5_RUN, "stability", "B03-U0041")
        / "mechanical.json",
        result_sha="54f5db533a23b682aa97b738e0640edf601cc556f4e18cd2ff3d99e1c18bbdb0",
        result_mode="accepted_mechanical",
        catalog_path=C4_RUN / "prepared/catalogs/B03-U0041.json",
        expected={
            "prompt_tokens": 8218,
            "completion_tokens": 10339,
            "reasoning_tokens": 9254,
            "finish_reason": "stop",
            "event_count": 10,
            "selected_anchor_reference_count": 17,
            "claim_span_violation_count": 0,
        },
    ),
    _spec(
        call_id="C6-B01",
        run=C6_RUN,
        phase="main",
        case_id="B01-U0033",
        contract_family="z_event_control_v1",
        comparison_role="different_contract_context_only",
        attempt_sha="0babe5ae0047dbbeab4de1342c18361ac42a692b40be62111f6418eca9269590",
        result_path=_sample_root(C6_RUN, "main", "B01-U0033")
        / "completion.json",
        result_sha="40fe9f476901128f959ecedf1b6dbff41ce5587025635f36c6a4fbbe5da5a633",
        result_mode="different_contract_completion",
        catalog_path=C6_RUN / "prepared/catalogs/B01-U0033.json",
        expected={
            "prompt_tokens": 23155,
            "completion_tokens": 9661,
            "reasoning_tokens": 2792,
            "finish_reason": "stop",
            "event_count": 75,
            "selected_anchor_reference_count": 358,
            "claim_span_violation_count": None,
        },
    ),
    _spec(
        call_id="C6-B02",
        run=C6_RUN,
        phase="main",
        case_id="B02-U0039",
        contract_family="z_event_control_v1",
        comparison_role="different_contract_context_only",
        attempt_sha="6e8b5e962fd015a8931db66fc54a28c417ff41fd5b158df2b4353a41c596441c",
        result_path=_sample_root(C6_RUN, "main", "B02-U0039")
        / "completion.json",
        result_sha="d086ac9d9e8b3ab3452aff3de4671143c0b7f2e9514fca03d3874515d056b347",
        result_mode="different_contract_completion",
        catalog_path=C6_RUN / "prepared/catalogs/B02-U0039.json",
        expected={
            "prompt_tokens": 6352,
            "completion_tokens": 13734,
            "reasoning_tokens": 11065,
            "finish_reason": "stop",
            "event_count": 44,
            "selected_anchor_reference_count": 75,
            "claim_span_violation_count": None,
        },
    ),
    _spec(
        call_id="C6-B03",
        run=C6_RUN,
        phase="main",
        case_id="B03-U0041",
        contract_family="z_event_control_v1",
        comparison_role="different_contract_context_only",
        attempt_sha="62241e0ef008bc41cdd77d01afedd748922d59c33a7fbe57d36e33b6b6729d83",
        result_path=_sample_root(C6_RUN, "main", "B03-U0041")
        / "completion.json",
        result_sha="3885003611e154f8a997e6465f90449d8282c9049a39cef6939c7e43defbf3b9",
        result_mode="different_contract_completion",
        catalog_path=C6_RUN / "prepared/catalogs/B03-U0041.json",
        expected={
            "prompt_tokens": 7737,
            "completion_tokens": 6157,
            "reasoning_tokens": 5579,
            "finish_reason": "stop",
            "event_count": 10,
            "selected_anchor_reference_count": 18,
            "claim_span_violation_count": None,
        },
    ),
)

PROTECTED_ROOTS = (
    C2_RUN,
    C3_RUN,
    C4_RUN,
    C5_RUN,
    C6_RUN,
    ROOT / "config/gold",
    V02_ROOT / "V02_C13_downstream_consumer_20260725",
)

CLAIM_SPAN_ERROR = re.compile(r"support_obligation_\d+_span_not_in_event")


class C128Error(RuntimeError):
    """C12.8 冻结证据或诊断合同不成立。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C128Error(f"冻结输入不存在：{display_path(path)}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C128Error(f"JSON 读取失败：{display_path(path)}") from exc


def read_single_jsonl(path: Path) -> Mapping[str, Any]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise C128Error(f"调用账必须恰好一行：{display_path(path)}")
    return rows[0]


def assert_safe_output(path: Path) -> None:
    resolved = path.resolve()
    for protected in PROTECTED_ROOTS:
        frozen = protected.resolve()
        if resolved == frozen or resolved.is_relative_to(frozen):
            raise C128Error(f"输出路径落入冻结根：{display_path(path)}")


def _verify_source(path: Path, expected_sha256: str) -> str:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise C128Error(
            f"冻结真源 SHA 漂移：{display_path(path)} "
            f"expected={expected_sha256} actual={actual}"
        )
    return actual


def _response(raw_path: Path) -> tuple[str, str]:
    response = read_json(raw_path)
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise C128Error(f"响应 choices 不闭合：{display_path(raw_path)}")
    choice = choices[0]
    content = choice.get("message", {}).get("content")
    finish_reason = choice.get("finish_reason")
    if not isinstance(content, str) or finish_reason not in {"stop", "length"}:
        raise C128Error(f"响应正文或结束原因非法：{display_path(raw_path)}")
    return finish_reason, content


def _closed_anchor_from_json(content: str) -> tuple[int, int]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise C128Error("完整响应不能解析为 JSON") from exc
    events = payload.get("events")
    if not isinstance(events, list):
        raise C128Error("完整响应缺 events")
    anchor_count = 0
    for event in events:
        anchors = event.get("minimal_anchor_ids")
        if not isinstance(anchors, list) or not all(
            isinstance(anchor, str) for anchor in anchors
        ):
            raise C128Error("完整响应含非法 minimal_anchor_ids")
        anchor_count += len(anchors)
    return len(events), anchor_count


def _metrics_from_result(
    *,
    mode: str,
    result_path: Path,
    response_content: str,
) -> tuple[int | None, int | None, int | None, str]:
    result = read_json(result_path)
    if mode == "accepted_mechanical":
        validation = result.get("closed_anchor_validation")
        events = validation.get("events") if isinstance(validation, Mapping) else None
        errors = validation.get("errors") if isinstance(validation, Mapping) else None
        if not isinstance(events, list) or not isinstance(errors, list):
            raise C128Error("机械票缺封闭锚明细")
        selected = sum(int(row["selected_anchor_count"]) for row in events)
        violations = sum(
            1 for error in errors if CLAIM_SPAN_ERROR.search(str(error))
        )
        return (
            int(result["event_count"]),
            selected,
            violations,
            "ACCEPTED_MECHANICAL_RESULT",
        )
    if mode == "rejected_full_json":
        event_count, selected = _closed_anchor_from_json(response_content)
        message = str(result.get("message") or "")
        violations = len(CLAIM_SPAN_ERROR.findall(message))
        if violations < 1:
            raise C128Error("拒收票没有 claim_span 违规")
        return (
            event_count,
            selected,
            violations,
            "DIAGNOSTIC_ONLY_FROM_REJECTED_FULL_JSON",
        )
    if mode == "truncated_no_salvage":
        if result.get("status") != "hard_stop_no_patch_no_rerun":
            raise C128Error("截断票状态非法")
        return (
            None,
            None,
            None,
            "MISSING_TRUNCATED_RESPONSE_NO_SALVAGE",
        )
    if mode == "different_contract_completion":
        return (
            int(result["event_count"]),
            int(result["anchor_count"]),
            None,
            "NOT_APPLICABLE_DIFFERENT_CONTRACT",
        )
    raise C128Error(f"未知结果模式：{mode}")


def build_call_row(spec: Mapping[str, Any]) -> dict[str, Any]:
    _verify_source(spec["attempt_path"], spec["attempt_sha256"])
    _verify_source(spec["result_path"], spec["result_sha256"])
    _verify_source(spec["catalog_path"], spec["catalog_sha256"])
    attempt = read_single_jsonl(spec["attempt_path"])
    request_sha = sha256_file(spec["request_path"])
    raw_response_sha = sha256_file(spec["raw_response_path"])
    if (
        attempt.get("request_artifact_sha256") != request_sha
        or attempt.get("raw_response_sha256") != raw_response_sha
        or attempt.get("http_status") != 200
    ):
        raise C128Error(f"{spec['call_id']} 调用账与请求／响应实物不一致")

    finish_reason, content = _response(spec["raw_response_path"])
    usage = attempt.get("usage")
    details = usage.get("completion_tokens_details") if isinstance(usage, Mapping) else None
    if not isinstance(usage, Mapping) or not isinstance(details, Mapping):
        raise C128Error(f"{spec['call_id']} usage 不完整")
    prompt_tokens = int(usage["prompt_tokens"])
    completion_tokens = int(usage["completion_tokens"])
    reasoning_tokens = int(details["reasoning_tokens"])
    if (
        prompt_tokens <= 0
        or completion_tokens <= 0
        or not 0 <= reasoning_tokens <= completion_tokens
    ):
        raise C128Error(f"{spec['call_id']} token 读数非法")

    catalog = read_json(spec["catalog_path"])
    entries = catalog.get("entries")
    if (
        not isinstance(entries, list)
        or catalog.get("entry_count") != len(entries)
        or catalog.get("selection_k") != "K_MISSING"
    ):
        raise C128Error(f"{spec['call_id']} 锚目录身份或 K 状态漂移")

    event_count, selected, violations, metric_status = _metrics_from_result(
        mode=str(spec["result_mode"]),
        result_path=spec["result_path"],
        response_content=content,
    )
    observed = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "finish_reason": finish_reason,
        "event_count": event_count,
        "selected_anchor_reference_count": selected,
        "claim_span_violation_count": violations,
    }
    if observed != spec["expected"]:
        raise C128Error(
            f"{spec['call_id']} 读数与冻结预期不一致："
            f"expected={spec['expected']} actual={observed}"
        )

    return {
        "call_id": spec["call_id"],
        "run_id": spec["run_id"],
        "phase": spec["phase"],
        "case_id": spec["case_id"],
        "contract_family": spec["contract_family"],
        "comparison_role": spec["comparison_role"],
        "request_sha256": request_sha,
        "raw_response_sha256": raw_response_sha,
        "attempt_ledger_sha256": spec["attempt_sha256"],
        "result_receipt_sha256": spec["result_sha256"],
        "catalog_sha256": spec["catalog_sha256"],
        "catalog_entry_count": len(entries),
        "catalog_file_byte_count": spec["catalog_path"].stat().st_size,
        "selection_k": "K_MISSING",
        "selection_k_is_approved_numeric_limit": False,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "reasoning_share_of_completion": reasoning_tokens / completion_tokens,
        "reasoning_share_percent_display": (
            f"{reasoning_tokens / completion_tokens:.4%}"
        ),
        "finish_reason": finish_reason,
        "event_count": event_count,
        "selected_anchor_reference_count": selected,
        "selected_anchor_is_output_metric_not_input_k": True,
        "claim_span_violation_count": violations,
        "claim_span_metric_status": metric_status,
        "rejected_response_used_as_quality_result": False,
        "source_paths": {
            "request": display_path(spec["request_path"]),
            "raw_response": display_path(spec["raw_response_path"]),
            "attempt_ledger": display_path(spec["attempt_path"]),
            "result_receipt": display_path(spec["result_path"]),
            "catalog": display_path(spec["catalog_path"]),
        },
    }


def build_historical_ledger() -> dict[str, Any]:
    calls = [build_call_row(spec) for spec in CALL_SPECS]
    return {
        "schema_version": "v02-c12-8-historical-call-ledger.v1",
        "status": "PASS_READONLY_HISTORICAL_REBUILD",
        "call_total": len(calls),
        "case_ids": ["B01-U0033", "B02-U0039", "B03-U0041"],
        "metric_contract": {
            "input_tokens": "supplier_usage.prompt_tokens",
            "reasoning_share": (
                "supplier_usage.reasoning_tokens / completion_tokens"
            ),
            "catalog_entry_count": "input_anchor_catalog.entries length",
            "selection_k": (
                "K_MISSING means no approved numeric limit and no truncation"
            ),
            "selected_anchor_reference_count": (
                "output references summed across events; not input load and not K"
            ),
            "claim_span_violation_count": (
                "closed_anchor_alignment only; z-event rows are NOT_APPLICABLE"
            ),
        },
        "calls": calls,
        "model_api_calls": 0,
        "network_requests": 0,
        "quality_result_registered": False,
    }


def _call_map(ledger: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {row["call_id"]: row for row in ledger["calls"]}


def build_notional_errata(ledger: Mapping[str, Any]) -> dict[str, Any]:
    calls = _call_map(ledger)
    return {
        "schema_version": "v02-c12-8-notion-shorthand-errata.v1",
        "status": "ADDITIVE_ERRATA_DO_NOT_REWRITE_OLD_LINE",
        "mixed_b01_shorthand": {
            "old_shorthand": {
                "prompt_tokens": 23636,
                "selected_anchor_reference_count": 52,
                "claim_span_violation_count": 10,
            },
            "why_invalid": (
                "52 anchors and 0 violations belong to C4-B01; "
                "10 violations and 37 anchors belong to C5-B01."
            ),
            "correct_rows": [
                {
                    key: calls["C4-B01"][key]
                    for key in (
                        "call_id",
                        "request_sha256",
                        "prompt_tokens",
                        "selected_anchor_reference_count",
                        "claim_span_violation_count",
                    )
                },
                {
                    key: calls["C5-B01"][key]
                    for key in (
                        "call_id",
                        "request_sha256",
                        "prompt_tokens",
                        "selected_anchor_reference_count",
                        "claim_span_violation_count",
                    )
                },
            ],
        },
        "c4_shorthand_rows": [
            {
                key: calls[call_id][key]
                for key in (
                    "call_id",
                    "prompt_tokens",
                    "selected_anchor_reference_count",
                    "claim_span_violation_count",
                )
            }
            for call_id in ("C4-B02", "C4-B03")
        ],
        "old_line_rewritten": False,
    }


def build_diagnosis(ledger: Mapping[str, Any]) -> dict[str, Any]:
    calls = _call_map(ledger)
    same_contract_replays = []
    for case_id in ("B01-U0033", "B02-U0039", "B03-U0041"):
        main = calls[f"C4-{case_id[:3]}"]
        repeat = calls[f"C5-{case_id[:3]}"]
        same_contract_replays.append(
            {
                "case_id": case_id,
                "same_request_sha256": (
                    main["request_sha256"] == repeat["request_sha256"]
                ),
                "catalog_entry_count": main["catalog_entry_count"],
                "prompt_tokens": main["prompt_tokens"],
                "main_result": {
                    "claim_span_violation_count": main[
                        "claim_span_violation_count"
                    ],
                    "selected_anchor_reference_count": main[
                        "selected_anchor_reference_count"
                    ],
                },
                "repeat_result": {
                    "claim_span_violation_count": repeat[
                        "claim_span_violation_count"
                    ],
                    "selected_anchor_reference_count": repeat[
                        "selected_anchor_reference_count"
                    ],
                },
            }
        )
    return {
        "schema_version": "v02-c12-8-dual-hypothesis-diagnosis.v1",
        "status": "PASS_DIAGNOSIS_NO_ADJUDICATION",
        "same_contract_replays": same_contract_replays,
        "hypotheses": [
            {
                "hypothesis_id": "H1_PROBABILISTIC_INSTABILITY",
                "status": "OPEN_NOT_ADJUDICATED",
                "supporting_observation": (
                    "B01 used the same request SHA twice and produced "
                    "0 then 10 claim_span violations."
                ),
                "why_not_proven": (
                    "Only two B01 observations exist; failure probability "
                    "cannot be estimated."
                ),
            },
            {
                "hypothesis_id": "H2_ANCHOR_CATALOG_LOAD_CLIFF",
                "status": "OPEN_NOT_ADJUDICATED",
                "supporting_observation": (
                    "B01 had 419 catalog entries and 23636 prompt tokens, "
                    "well above B02/B03, and is the only same-contract failure."
                ),
                "why_not_proven": (
                    "Chapter content, fact density, catalog size and output "
                    "behaviour changed together; three chapters cannot isolate load."
                ),
            },
        ],
        "required_conclusion": (
            "概率性不稳定与锚目录负载悬崖两种解释都仍然可能；"
            "现有三章少量调用不能裁定主因。"
        ),
        "c6_4_risk_statement_kept": True,
        "curve_fitted": False,
        "threshold_declared": False,
        "hypothesis_ranked": False,
        "quality_result_registered": False,
        "different_contract_c6_excluded_from_causal_comparison": True,
        "selected_anchor_count_used_as_input_load": False,
        "input_load_fields": ["catalog_entry_count", "prompt_tokens"],
    }


def build_future_experiment_shape() -> dict[str, Any]:
    return {
        "schema_version": "v02-c12-8-minimum-future-experiment-shape.v1",
        "status": "DESIGN_ONLY_NOT_AUTHORIZED_NOT_EXECUTED",
        "unit": "one frozen B01 fact package with targeted anchor selection",
        "held_constant": [
            "chapter body",
            "fact package",
            "prompt",
            "model and provider",
            "sampling parameters",
            "output contract",
            "correct required anchors",
        ],
        "only_changed_variable": "input candidate anchor count K",
        "candidate_levels_not_approved": [8, 16, 32, 64, 419],
        "candidate_sets_nested": True,
        "correct_required_anchors_present_at_every_level": True,
        "added_items_are_same_chapter_real_distractor_anchors": True,
        "levels_interleaved_to_reduce_time_and_provider_confounds": True,
        "repeated_calls_per_level": "CZ_APPROVAL_MISSING",
        "budget": "CZ_APPROVAL_MISSING",
        "preregister_before_network": True,
        "report_raw_results_without_curve_fit": True,
        "declare_safe_threshold": False,
        "execute_now": False,
        "minimum_readouts": [
            "mechanical acceptance",
            "claim_span violations with an explicit denominator",
            "required-anchor recall",
            "prompt/completion/reasoning tokens",
            "latency",
            "transport failures",
        ],
    }


def build_source_receipt(ledger: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for call in ledger["calls"]:
        rows.append(
            {
                "call_id": call["call_id"],
                "source_paths": call["source_paths"],
                "source_sha256": {
                    "request": call["request_sha256"],
                    "raw_response": call["raw_response_sha256"],
                    "attempt_ledger": call["attempt_ledger_sha256"],
                    "result_receipt": call["result_receipt_sha256"],
                    "catalog": call["catalog_sha256"],
                },
            }
        )
    return {
        "schema_version": "v02-c12-8-source-binding-receipt.v1",
        "status": "PASS_FROZEN_LOCAL_SOURCES",
        "rows": rows,
        "source_set_sha256": sha256_bytes(
            canonical_bytes(
                {
                    row["call_id"]: row["source_sha256"]
                    for row in rows
                }
            )
        ),
        "sealed_sources_rewritten": False,
        "rejected_response_salvaged_as_quality": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_artifacts() -> dict[str, bytes]:
    ledger = build_historical_ledger()
    documents: dict[str, Any] = {
        "historical_call_ledger.json": ledger,
        "notion_shorthand_errata.json": build_notional_errata(ledger),
        "dual_hypothesis_diagnosis.json": build_diagnosis(ledger),
        "minimum_future_experiment_shape.json": (
            build_future_experiment_shape()
        ),
        "source_binding_receipt.json": build_source_receipt(ledger),
    }
    artifacts = {
        name: canonical_bytes(document)
        for name, document in documents.items()
    }
    readme = (
        "# C12.8｜锚目录负载悬崖只读诊断\n\n"
        "这是一份 0 API 的历史调用机械重建。输入负载只看目录条目数与"
        "输入 token；模型输出的选锚引用数单列，绝不冒充输入 K。\n\n"
        "结论保持两种解释都未裁定，不拟合曲线，不宣布阈值，不推翻 C6.4。"
        "\n\n来源：Codex\n"
    ).encode("utf-8")
    artifacts["README.md"] = readme
    rows = [
        {"path": name, "sha256": sha256_bytes(raw), "byte_count": len(raw)}
        for name, raw in sorted(artifacts.items())
    ]
    manifest = {
        "schema_version": "v02-c12-8-artifact-manifest.v1",
        "status": "PASS_CANDIDATE_DIAGNOSIS_NO_ADJUDICATION",
        "program_path": display_path(SELF_PATH),
        "program_sha256": sha256_file(SELF_PATH),
        "files": rows,
        "artifact_set_sha256": sha256_bytes(
            canonical_bytes({row["path"]: row["sha256"] for row in rows})
        ),
        "model_api_calls": 0,
        "network_requests": 0,
        "quality_result_registered": False,
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(manifest)
    return artifacts


def write_or_verify(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    write: bool,
) -> dict[str, Any]:
    assert_safe_output(output_dir)
    artifacts = build_artifacts()
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, raw in artifacts.items():
            path = output_dir / name
            if path.exists() and path.read_bytes() != raw:
                raise C128Error(f"既有候选工件漂移：{display_path(path)}")
            path.write_bytes(raw)
    if not output_dir.is_dir():
        raise C128Error("候选工件目录不存在")
    actual_names = {path.name for path in output_dir.iterdir() if path.is_file()}
    if actual_names != set(artifacts):
        raise C128Error("候选工件目录文件集合不闭合")
    for name, raw in artifacts.items():
        if (output_dir / name).read_bytes() != raw:
            raise C128Error(f"候选工件不能重建：{name}")
    return json.loads(artifacts["artifact_manifest.json"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C12.8 锚目录负载悬崖诊断")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    manifest = write_or_verify(args.output_dir, write=not args.check)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "artifact_set_sha256": manifest["artifact_set_sha256"],
                "model_api_calls": 0,
                "network_requests": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
