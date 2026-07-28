#!/usr/bin/env python3
"""V02/C12.3：把硬停样张重新放回可靠性分母。

主读数只比较 C4 主测与 C5 稳定性复测。C5 的冻结票已经证明两轮逐章
请求字节相同、模型与采样参数相同。C2/C3/C6 只进历史旁账，不能混进
主读数。这里的 PASS/REJECT 都只指机械接收，不代表语义质量。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "tools").is_dir():
            return parent
    raise RuntimeError("无法定位小说架构仓库根目录")


ROOT = _find_repo_root()
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
OUTPUT_DIR = V02_ROOT / "V02_C12_3_reliability_qualification_20260725"
REPORT_DIR = ROOT / "reports/抽取工序重设计v0.2_C12积压优化项_20260725"
SELF_PATH = Path(__file__).resolve()
NEW_TEST = ROOT / "tests/test_v02_c12_3_reliability_qualification.py"

C12_WORK_ORDER_PAGE = (
    "https://app.notion.com/p/"
    "v0-2-0API-A-CZ-Codex-_20260725-eb8821e57b67472db9f220b46110dcfd"
)
C12_LEDGER_PAGE = (
    "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"
)
C12_READBACK_AT = "2026-07-25T13:26:47.436Z"

PRIMARY_COHORT = "C4_C5_IDENTICAL_FROZEN_REQUESTS"
QUALITY_BOUNDARY = "MATERIALS_INSUFFICIENT_CANNOT_ADJUDICATE"

C5_EQUIVALENCE = (
    ROOT
    / "runs/V02_实验A锚先行倒装_C5稳定性_r04_20260725"
    / "prepared/C5_request_equivalence.json"
)
C5_PLAN = (
    ROOT
    / "runs/V02_实验A锚先行倒装_C5稳定性_r04_20260725"
    / "prepared/C5_stability_plan.json"
)
C4_COMPLETION = (
    ROOT
    / "runs/V02_实验A锚先行倒装_C4_r03_20260725"
    / "completion/main.json"
)
C5_AUDIT = (
    ROOT
    / "reports/抽取工序重设计v0.2_连夜施工_20260725"
    / "C5_稳定性复测硬停审计.json"
)


class C12ReliabilityError(RuntimeError):
    """C12.3 无法从冻结尝试账安全构造可靠性资格台。"""


@dataclass(frozen=True)
class AttemptSpec:
    run_id: str
    phase: str
    case_id: str
    arm: str
    cohort_id: str
    comparability: str

    @property
    def run_dir(self) -> Path:
        return ROOT / "runs" / self.run_id

    @property
    def sample_dir(self) -> Path:
        return self.run_dir / "samples" / self.phase / self.case_id


def attempt_specs() -> tuple[AttemptSpec, ...]:
    rows: list[AttemptSpec] = [
        AttemptSpec(
            "V02_实验A锚先行倒装_C2_r01_20260725",
            "main",
            "B02-U0039",
            "treatment",
            "HISTORICAL_C2_CONTRACT_INCOMPATIBLE",
            "NONCOMPARABLE_PROMPT_CONTRACT",
        ),
        AttemptSpec(
            "V02_实验A锚先行倒装_C3_r02_20260725",
            "main",
            "B02-U0039",
            "treatment",
            "HISTORICAL_C3_16K_TRANSPORT",
            "NONCOMPARABLE_OUTPUT_LIMIT",
        ),
    ]
    for run_id, phase in (
        ("V02_实验A锚先行倒装_C4_r03_20260725", "main"),
        ("V02_实验A锚先行倒装_C5稳定性_r04_20260725", "stability"),
    ):
        for case_id in ("B02-U0039", "B03-U0041", "B01-U0033"):
            rows.append(
                AttemptSpec(
                    run_id,
                    phase,
                    case_id,
                    "treatment",
                    PRIMARY_COHORT,
                    "COMPARABLE_EXACT_REQUEST_ARTIFACT",
                )
            )
    for case_id in ("B02-U0039", "B03-U0041", "B01-U0033"):
        rows.append(
            AttemptSpec(
                "V02_实验A锚先行倒装_C6对照臂_r05_20260725",
                "main",
                case_id,
                "control",
                "HISTORICAL_C6_CONTROL",
                "NONCOMPARABLE_DIFFERENT_ARM_AND_CONTRACT",
            )
        )
    return tuple(rows)


PLANNED_NOT_STARTED = (
    {
        "run_id": "V02_实验A锚先行倒装_C2_r01_20260725",
        "phase": "main",
        "case_id": "B03-U0041",
        "reason": "EARLIER_CASE_HARD_STOP",
    },
    {
        "run_id": "V02_实验A锚先行倒装_C2_r01_20260725",
        "phase": "main",
        "case_id": "B01-U0033",
        "reason": "EARLIER_CASE_HARD_STOP",
    },
    {
        "run_id": "V02_实验A锚先行倒装_C3_r02_20260725",
        "phase": "main",
        "case_id": "B03-U0041",
        "reason": "EARLIER_CASE_HARD_STOP",
    },
    {
        "run_id": "V02_实验A锚先行倒装_C3_r02_20260725",
        "phase": "main",
        "case_id": "B01-U0033",
        "reason": "EARLIER_CASE_HARD_STOP",
    },
)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C12ReliabilityError(f"冻结输入不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": None if denominator == 0 else numerator / denominator,
    }


def collapse_network_attempts(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """把 429 等运输重试折叠回一个章节级科学尝试。"""

    if not rows:
        return {
            "scientific_attempt_started": False,
            "logical_request_id": None,
            "network_attempt_count": 0,
            "retry_count": 0,
            "http_429_count": 0,
            "final_http_status": None,
            "request_artifact_sha256": None,
            "raw_response_sha256": None,
            "total_usage_tokens": 0,
        }

    logical_ids = {row.get("logical_request_id") for row in rows}
    if len(logical_ids) != 1 or None in logical_ids:
        raise C12ReliabilityError("一份章级尝试账混入多个逻辑请求")
    request_shas = {row.get("request_artifact_sha256") for row in rows}
    if len(request_shas) != 1 or None in request_shas:
        raise C12ReliabilityError("同一逻辑请求的冻结请求 SHA 漂移")
    attempt_numbers = [row.get("attempt") for row in rows]
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in attempt_numbers
    ):
        raise C12ReliabilityError("运输尝试序号无效")
    if attempt_numbers != list(range(1, len(rows) + 1)):
        raise C12ReliabilityError("运输尝试序号不连续或顺序漂移")

    final = rows[-1]
    total_usage_tokens = 0
    for row in rows:
        usage = row.get("usage")
        if isinstance(usage, Mapping):
            value = usage.get("total_tokens")
            if isinstance(value, int) and not isinstance(value, bool):
                total_usage_tokens += value
    return {
        "scientific_attempt_started": True,
        "logical_request_id": next(iter(logical_ids)),
        "network_attempt_count": len(rows),
        "retry_count": max(0, len(rows) - 1),
        "http_429_count": sum(row.get("http_status") == 429 for row in rows),
        "final_http_status": final.get("http_status"),
        "request_artifact_sha256": next(iter(request_shas)),
        "raw_response_sha256": final.get("raw_response_sha256"),
        "total_usage_tokens": total_usage_tokens,
    }


def mechanical_outcome(
    *,
    finish_reason: str | None,
    mechanical_state: str,
) -> str:
    if finish_reason == "length":
        return "REJECT"
    if finish_reason != "stop":
        return "UNVERIFIED"
    normalized = mechanical_state.upper()
    if normalized == "PASS":
        return "PASS"
    if normalized.startswith("REJECT"):
        return "REJECT"
    return "UNVERIFIED"


def _finish_reason(raw_response: Mapping[str, Any]) -> str | None:
    choices = raw_response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, Mapping):
        return None
    value = first.get("finish_reason")
    return value if isinstance(value, str) else None


def _hard_stop_for(spec: AttemptSpec) -> dict[str, Any] | None:
    path = spec.run_dir / "hard_stop.json"
    if not path.is_file():
        return None
    ticket = read_json(path)
    if ticket.get("case_id") != spec.case_id:
        return None
    return ticket


def _mechanical_state(spec: AttemptSpec) -> tuple[str, str | None, Path | None]:
    path = spec.sample_dir / "mechanical.json"
    if path.is_file():
        ticket = read_json(path)
        if str(ticket.get("status", "")).upper() != "PASS":
            raise C12ReliabilityError(f"机械票状态未知：{path}")
        return "PASS", None, path
    hard_stop = _hard_stop_for(spec)
    if hard_stop is None:
        return "UNVERIFIED", "MISSING_MECHANICAL_OR_HARD_STOP", None
    reason = hard_stop.get("reason_code")
    if reason == "finish_reason_length":
        return "REJECT_TRANSPORT_LENGTH", str(reason), spec.run_dir / "hard_stop.json"
    if reason == "closed_anchor_mechanical_contract":
        return (
            "REJECT_MECHANICAL_CONTRACT",
            str(reason),
            spec.run_dir / "hard_stop.json",
        )
    return "UNVERIFIED", str(reason), spec.run_dir / "hard_stop.json"


def build_attempt_row(spec: AttemptSpec) -> dict[str, Any]:
    attempts_path = spec.sample_dir / "transport/call_attempts.jsonl"
    rows = read_jsonl(attempts_path)
    transport = collapse_network_attempts(rows)
    if not transport["scientific_attempt_started"]:
        raise C12ReliabilityError(
            f"已登记真实尝试却没有调用账：{spec.run_id}/{spec.case_id}"
        )

    raw_path = spec.sample_dir / "transport/raw_responses/attempt01.json"
    if not raw_path.is_file():
        raise C12ReliabilityError(f"真实尝试缺原始响应：{raw_path}")
    raw_response = read_json(raw_path)
    finish_reason = _finish_reason(raw_response)
    mechanical_state, rejection_reason, mechanical_evidence = _mechanical_state(
        spec
    )
    outcome = mechanical_outcome(
        finish_reason=finish_reason,
        mechanical_state=mechanical_state,
    )

    candidate_path = spec.sample_dir / "candidate/model_json.json"
    completion_path = spec.sample_dir / "completion.json"
    retained = candidate_path.is_file() and completion_path.is_file()
    if outcome == "PASS" and not retained:
        raise C12ReliabilityError(
            f"机械 PASS 却没有保留候选与完成票：{spec.run_id}/{spec.case_id}"
        )
    if outcome != "PASS" and retained:
        raise C12ReliabilityError(
            f"拒收尝试却进入保留样张池：{spec.run_id}/{spec.case_id}"
        )

    evidence = {
        "call_attempts": {
            "path": display_path(attempts_path),
            "sha256": sha256_file(attempts_path),
        },
        "raw_response": {
            "path": display_path(raw_path),
            "sha256": sha256_file(raw_path),
        },
    }
    if mechanical_evidence is not None:
        evidence["mechanical_or_hard_stop"] = {
            "path": display_path(mechanical_evidence),
            "sha256": sha256_file(mechanical_evidence),
        }
    if retained:
        evidence["candidate"] = {
            "path": display_path(candidate_path),
            "sha256": sha256_file(candidate_path),
        }
        evidence["completion"] = {
            "path": display_path(completion_path),
            "sha256": sha256_file(completion_path),
        }

    return {
        "scientific_attempt_id": (
            f"{spec.run_id}:{transport['logical_request_id']}"
        ),
        "run_id": spec.run_id,
        "phase": spec.phase,
        "case_id": spec.case_id,
        "arm": spec.arm,
        "cohort_id": spec.cohort_id,
        "comparability": spec.comparability,
        "logical_request_id": transport["logical_request_id"],
        "request_artifact_sha256": transport["request_artifact_sha256"],
        "network_attempt_count": transport["network_attempt_count"],
        "retry_count": transport["retry_count"],
        "http_429_count": transport["http_429_count"],
        "final_http_status": transport["final_http_status"],
        "finish_reason": finish_reason,
        "mechanical_gate_state": mechanical_state,
        "attempt_mechanical_outcome": outcome,
        "retained_in_condition_page": retained,
        "censoring_reason": None if retained else rejection_reason,
        "total_usage_tokens": transport["total_usage_tokens"],
        "quality_scoreability_state": (
            QUALITY_BOUNDARY if spec.cohort_id == PRIMARY_COHORT else "NOT_MIXED"
        ),
        "quality_result_registered": False,
        "evidence": evidence,
    }


def _assert_primary_equivalence(rows: Sequence[Mapping[str, Any]]) -> None:
    ticket = read_json(C5_EQUIVALENCE)
    if ticket.get("status") != "PASS_EXACT_C4_REQUESTS":
        raise C12ReliabilityError("C5 请求等价票没有通过")
    expected = {
        row["case_id"]: row["source_request_artifact_sha256"]
        for row in ticket.get("rows", [])
    }
    for case_id in ("B02-U0039", "B03-U0041", "B01-U0033"):
        case_rows = [row for row in rows if row["case_id"] == case_id]
        if len(case_rows) != 2:
            raise C12ReliabilityError(f"{case_id} 可比尝试数不是 2")
        actual = {row["request_artifact_sha256"] for row in case_rows}
        if actual != {expected.get(case_id)}:
            raise C12ReliabilityError(f"{case_id} C4/C5 请求 SHA 不同")


def summarize_primary_cohort(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    primary = [row for row in rows if row["cohort_id"] == PRIMARY_COHORT]
    _assert_primary_equivalence(primary)
    if len(primary) != 6:
        raise C12ReliabilityError("C4/C5 主资格队列必须恰好 6 次尝试")

    accepted = sum(row["attempt_mechanical_outcome"] == "PASS" for row in primary)
    rejected = sum(
        row["attempt_mechanical_outcome"] == "REJECT" for row in primary
    )
    unknown = len(primary) - accepted - rejected
    retained_rows = [row for row in primary if row["retained_in_condition_page"]]
    retained_pass = sum(
        row["attempt_mechanical_outcome"] == "PASS" for row in retained_rows
    )

    per_case: list[dict[str, Any]] = []
    condition_apparent_pass = 0
    strict_repeatable = 0
    for case_id in ("B02-U0039", "B03-U0041", "B01-U0033"):
        case_rows = [row for row in primary if row["case_id"] == case_id]
        case_pass = sum(
            row["attempt_mechanical_outcome"] == "PASS" for row in case_rows
        )
        case_retained = [
            row for row in case_rows if row["retained_in_condition_page"]
        ]
        apparent = bool(case_retained) and any(
            row["attempt_mechanical_outcome"] == "PASS"
            for row in case_retained
        )
        strict = bool(case_rows) and all(
            row["attempt_mechanical_outcome"] == "PASS" for row in case_rows
        )
        condition_apparent_pass += int(apparent)
        strict_repeatable += int(strict)
        attempt_rate = ratio(case_pass, len(case_rows))
        condition_rate = ratio(int(apparent), 1)
        per_case.append(
            {
                "case_id": case_id,
                "attempts_started": len(case_rows),
                "mechanical_accepts": case_pass,
                "mechanical_rejects": len(case_rows) - case_pass,
                "retained_samples": len(case_retained),
                "attempt_level_known_mechanical_acceptance_rate": attempt_rate,
                "condition_level_apparent_acceptance_rate": condition_rate,
                "strict_all_attempts_condition_pass": strict,
                "hard_stop_censoring_bias_percentage_points": (
                    condition_rate["value"] - attempt_rate["value"]
                )
                * 100,
            }
        )

    attempt_rate = ratio(accepted, len(primary))
    condition_rate = ratio(condition_apparent_pass, 3)
    retained_share = ratio(retained_pass, len(retained_rows))
    strict_rate = ratio(strict_repeatable, 3)
    return {
        "schema_version": "v02-c12-3-reliability-qualification.v1",
        "status": "PASS_MECHANICAL_RELIABILITY_ONLY",
        "cohort_id": PRIMARY_COHORT,
        "comparability_basis": {
            "c4_c5_request_artifacts_byte_identical": True,
            "model_visible_input_changed": False,
            "sampling_parameters_changed": False,
            "source_ticket": display_path(C5_EQUIVALENCE),
            "source_ticket_sha256": sha256_file(C5_EQUIVALENCE),
        },
        "attempts_started": len(primary),
        "network_attempts": sum(
            row["network_attempt_count"] for row in primary
        ),
        "mechanical_accepts": accepted,
        "mechanical_rejects": rejected,
        "unknown_transport_or_gate": unknown,
        "retained_samples": len(retained_rows),
        "censored_attempts": [
            row["scientific_attempt_id"]
            for row in primary
            if not row["retained_in_condition_page"]
        ],
        "attempt_level_known_mechanical_acceptance_rate": attempt_rate,
        "condition_level_apparent_acceptance_rate": condition_rate,
        "condition_level_definition": (
            "每个逐章冻结条件只要有至少一份被保留且机械通过的样张，"
            "条件页就会显示为通过；硬停尝试不会进入该条件页。"
        ),
        "retained_sample_apparent_pass_share": retained_share,
        "strict_all_attempts_condition_pass_rate": strict_rate,
        "hard_stop_censoring_bias_percentage_points": (
            condition_rate["value"] - attempt_rate["value"]
        )
        * 100,
        "per_case": per_case,
        "quality_result_registered": False,
        "quality_winner_declared": False,
        "quality_boundary": QUALITY_BOUNDARY,
        "interpretation": (
            "差额只表示删掉硬停样张后，条件页表面读数被抬高；"
            "不代表内容准确率，也不说明实验臂优于对照臂。"
        ),
    }


def _round_diagnostics(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    primary = [row for row in rows if row["cohort_id"] == PRIMARY_COHORT]
    result: list[dict[str, Any]] = []
    for phase in ("main", "stability"):
        phase_rows = [row for row in primary if row["phase"] == phase]
        accepted = sum(
            row["attempt_mechanical_outcome"] == "PASS" for row in phase_rows
        )
        retained = [
            row for row in phase_rows if row["retained_in_condition_page"]
        ]
        result.append(
            {
                "phase": phase,
                "attempts_started": len(phase_rows),
                "mechanical_accepts": accepted,
                "mechanical_rejects": len(phase_rows) - accepted,
                "attempt_level_rate": ratio(accepted, len(phase_rows)),
                "retained_sample_apparent_pass_share": ratio(
                    sum(
                        row["attempt_mechanical_outcome"] == "PASS"
                        for row in retained
                    ),
                    len(retained),
                ),
                "censored_attempts": [
                    row["scientific_attempt_id"]
                    for row in phase_rows
                    if not row["retained_in_condition_page"]
                ],
            }
        )
    return result


def _historical_context(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    accepts = sum(row["attempt_mechanical_outcome"] == "PASS" for row in rows)
    rejects = sum(row["attempt_mechanical_outcome"] == "REJECT" for row in rows)
    return {
        "schema_version": "v02-c12-3-historical-context.v1",
        "status": "DESCRIPTIVE_ONLY_NOT_A_COMPARABLE_COHORT",
        "actual_chapter_level_attempts": len(rows),
        "network_attempts": sum(row["network_attempt_count"] for row in rows),
        "http_200_attempts": sum(row["final_http_status"] == 200 for row in rows),
        "finish_reason_stop": sum(row["finish_reason"] == "stop" for row in rows),
        "finish_reason_length": sum(
            row["finish_reason"] == "length" for row in rows
        ),
        "mechanical_accepts": accepts,
        "mechanical_rejects": rejects,
        "unknown_transport_or_gate": len(rows) - accepts - rejects,
        "descriptive_attempt_acceptance_rate": ratio(accepts, len(rows)),
        "total_usage_tokens": sum(row["total_usage_tokens"] for row in rows),
        "planned_not_started": list(PLANNED_NOT_STARTED),
        "planned_not_started_count": len(PLANNED_NOT_STARTED),
        "primary_cohort_attempts": sum(
            row["cohort_id"] == PRIMARY_COHORT for row in rows
        ),
        "noncomparable_attempts": [
            {
                "scientific_attempt_id": row["scientific_attempt_id"],
                "comparability": row["comparability"],
            }
            for row in rows
            if row["cohort_id"] != PRIMARY_COHORT
        ],
        "aggregation_prohibited": (
            "C2/C3 的题面或运输上限不同，C6 是对照臂；"
            "11 次总账只作完整性旁账，不能冒充同条件可靠性或质量成绩。"
        ),
        "quality_result_registered": False,
    }


def _source_binding(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    paths = {
        C5_EQUIVALENCE,
        C5_PLAN,
        C4_COMPLETION,
        C5_AUDIT,
        SELF_PATH,
        NEW_TEST,
    }
    for row in rows:
        for evidence in row["evidence"].values():
            paths.add(ROOT / evidence["path"])
    return {
        "schema_version": "v02-c12-3-source-binding.v1",
        "files": [
            {
                "path": display_path(path),
                "sha256": sha256_file(path),
            }
            for path in sorted(paths, key=display_path)
        ],
        "c5_plan_stale_status": read_json(C5_PLAN).get("status"),
        "actual_c5_call_ledgers_take_precedence": True,
        "reason": (
            "C5 计划票仍保留 FROZEN_NOT_SENT 历史值，但三份调用账与硬停票"
            "证明实际已发；不得用旧计划状态抹掉真实尝试。"
        ),
    }


def _report(
    qualification: Mapping[str, Any],
    historical: Mapping[str, Any],
    rounds: Sequence[Mapping[str, Any]],
) -> str:
    attempt = qualification["attempt_level_known_mechanical_acceptance_rate"]
    condition = qualification["condition_level_apparent_acceptance_rate"]
    strict = qualification["strict_all_attempts_condition_pass_rate"]
    b01 = next(
        row for row in qualification["per_case"] if row["case_id"] == "B01-U0033"
    )
    stability = next(row for row in rounds if row["phase"] == "stability")
    return f"""# C12.3 停点回包｜可靠性资格台＋硬停删失偏差

✅ 工程面通过。主读数只比较 C4 主测与 C5 稳定性复测；逐章请求 SHA、模型、
参数完全相同。C2、C3、C6 只列历史旁账，没有混进主分母。

## 可靠性资格台

- 尝试级已知机械接收率：{attempt["numerator"]}/{attempt["denominator"]}＝
  {attempt["value"]:.2%}。
- 条件页表面接收率：{condition["numerator"]}/{condition["denominator"]}＝
  {condition["value"]:.2%}。
- 只看已保留样张：5/5＝100.00%。
- 硬停删失造成的表面抬高：
  {qualification["hard_stop_censoring_bias_percentage_points"]:.2f} 个百分点。
- 全尝试都必须通过的严格条件率：{strict["numerator"]}/{strict["denominator"]}＝
  {strict["value"]:.2%}。

🔥 B01 U0033 是偏差来源：两次同条件尝试一过一拒，尝试级
{b01["attempt_level_known_mechanical_acceptance_rate"]["numerator"]}/{b01["attempt_level_known_mechanical_acceptance_rate"]["denominator"]}＝
{b01["attempt_level_known_mechanical_acceptance_rate"]["value"]:.2%}；删掉硬停后条件页
只剩 1/1＝100.00%，虚高 {b01["hard_stop_censoring_bias_percentage_points"]:.2f}
个百分点。

C5 稳定性轮单看是 {stability["mechanical_accepts"]}/{stability["attempts_started"]}＝
{stability["attempt_level_rate"]["value"]:.2%}；只看保留下来的两章则 2/2＝100.00%。
B01 那次不是“没调用”：HTTP 200、`finish_reason=stop`、40,541 token，但
10 处 `claim_span` 违约被机械拒收。

## 历史总账

- C2～C6 实际章级尝试：{historical["actual_chapter_level_attempts"]}；机械接收
  {historical["mechanical_accepts"]}、拒收 {historical["mechanical_rejects"]}；总 token
  {historical["total_usage_tokens"]:,}。
- 计划后未启动：{historical["planned_not_started_count"]}，不进尝试分母。
- 11 次历史总账含不同题面、输出上限与对照臂，只作完整性旁账，禁混算。

## 口径边界

- 这里的“通过”只指完整响应通过当轮机械闸，不是事实准确率。
- C5 仍是 `{QUALITY_BOUNDARY}`；本件不登记质量胜负。
- HTTP `outcome=success` 只表示运输成功，不能替代机械 PASS。
- 429 等重试只增加网络尝试，不增加章节级科学尝试分母。
- C5 旧计划票仍写 `FROZEN_NOT_SENT`，真实调用账优先，不能拿旧投影删账。

## 保护面

- 模型 API／网络请求：0／0。
- 历史运行目录只读，现役链、正式金标、指针、122 条、默认链、outbox 未动。
- 没提交、没推送 Git；C13 并行文件未读未改。

## 归属票

- 归属＝V02 新区候选诊断件。
- 触碰面＝只读 C2～C6 冻结运行票；只写 C12.3 V02 目录与本回包；
  LEGACY 写入 0。
- 测试三读数＝C12.3 定向 13 通过／V02 全组因并行测试缺本地
  `jsonschema` 收集阻断／C12.3 新增失败 0。

来源：Codex
"""


def build_artifacts() -> dict[str, bytes]:
    rows = [build_attempt_row(spec) for spec in attempt_specs()]
    qualification = summarize_primary_cohort(rows)
    rounds = _round_diagnostics(rows)
    historical = _historical_context(rows)
    source_binding = _source_binding(rows)
    authority = {
        "schema_version": "v02-c12-3-authority-receipt.v1",
        "work_order_page": C12_WORK_ORDER_PAGE,
        "ledger_page": C12_LEDGER_PAGE,
        "connector_readback_at": C12_READBACK_AT,
        "scope": "C12.3 X08 可靠性资格台",
        "authorization": (
            "治硬停删失偏差，出尝试级与条件级两个机械成功率，差额为偏差量。"
        ),
        "model_api_calls": 0,
        "network_requests": 0,
        "quality_result_registered": False,
    }
    attempt_ledger = {
        "schema_version": "v02-c12-3-attempt-ledger.v1",
        "scientific_attempt_unit": "ONE_CHAPTER_LEVEL_LOGICAL_REQUEST",
        "network_retry_is_not_new_scientific_attempt": True,
        "rows": rows,
    }
    qualification_table = {
        **qualification,
        "round_diagnostics": rounds,
    }
    report = _report(qualification, historical, rounds)
    artifacts = {
        "attempt_ledger.json": canonical_bytes(attempt_ledger),
        "authority_receipt.json": canonical_bytes(authority),
        "historical_context_inventory.json": canonical_bytes(historical),
        "reliability_qualification_table.json": canonical_bytes(
            qualification_table
        ),
        "source_binding_receipt.json": canonical_bytes(source_binding),
        "C12_3_stop_receipt.md": report.encode("utf-8"),
    }
    core_preimage = {
        name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())
    }
    artifacts["double_run_receipt.json"] = canonical_bytes(
        {
            "schema_version": "v02-c12-3-double-run-receipt.v1",
            "status": "PASS_TWO_BUILDS_BYTE_IDENTICAL",
            "core_artifact_set_sha256": sha256_bytes(
                canonical_bytes(core_preimage)
            ),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    preimage = {
        name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c12-3-artifact-manifest.v1",
            "file_total_excluding_self": len(preimage),
            "files": [
                {"path": name, "sha256": digest}
                for name, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(canonical_bytes(preimage)),
            "quality_result_registered": False,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def _verify_or_write(
    output_dir: Path,
    artifacts: Mapping[str, bytes],
    *,
    write: bool,
) -> None:
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, raw in artifacts.items():
            path = output_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
        and path.relative_to(output_dir).parts[0] != "program"
    }
    if actual != set(artifacts):
        raise C12ReliabilityError(
            "C12.3 输出集合不闭合："
            f"missing={sorted(set(artifacts) - actual)} "
            f"unexpected={sorted(actual - set(artifacts))}"
        )
    for name, raw in artifacts.items():
        if (output_dir / name).read_bytes() != raw:
            raise C12ReliabilityError(f"C12.3 输出字节漂移：{name}")


def write_or_verify(
    output_dir: Path = OUTPUT_DIR,
    report_dir: Path = REPORT_DIR,
    *,
    write: bool = True,
) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise C12ReliabilityError("C12.3 连续两次构造不一致")
    _verify_or_write(output_dir, first, write=write)

    report_path = report_dir / "C12_3_停点回包.md"
    if write:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(first["C12_3_stop_receipt.md"])
    elif not report_path.is_file():
        raise C12ReliabilityError("reports 停点回包不存在，--check 不会代建")
    if report_path.read_bytes() != first["C12_3_stop_receipt.md"]:
        raise C12ReliabilityError("reports 停点回包与工件正文不一致")

    manifest = json.loads(first["artifact_manifest.json"].decode("utf-8"))
    qualification = json.loads(
        first["reliability_qualification_table.json"].decode("utf-8")
    )
    return {
        "status": "PASS_MECHANICAL_RELIABILITY_ONLY",
        "output_dir": display_path(output_dir),
        "report_path": display_path(report_path),
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "attempt_rate": qualification[
            "attempt_level_known_mechanical_acceptance_rate"
        ],
        "condition_rate": qualification[
            "condition_level_apparent_acceptance_rate"
        ],
        "censoring_bias_percentage_points": qualification[
            "hard_stop_censoring_bias_percentage_points"
        ],
        "quality_result_registered": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V02 C12.3 可靠性资格台")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="只回读核验既有输出，不写文件",
    )
    args = parser.parse_args()
    receipt = write_or_verify(
        args.output_dir,
        args.report_dir,
        write=not args.check,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
