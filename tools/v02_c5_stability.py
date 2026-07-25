#!/usr/bin/env python3
"""V02/C5：C4 主结论封存后的三章一次稳定性复测。

本工具只做诊断复测：

- C4 r03 主测与 C5 离线主结论都只读；
- 三章逐字复用 C4 已实发请求，每章最多一次；
- 固定 SenseNova V4 Flash、temperature=0.2、medium、65536；
- 不重试、不择优、不发第三轮；
- 分歧率永不改写 C5 主结论。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import v02_anchor_first_live_runner as live
import v02_c4_transport_probe as c4
import v02_c5_offline_score as c5
from pipeline_common import model_benchmark
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
C4_RUN_DIR = c4.C4_RUN_DIR
C4_SUPPLY_DIR = c4.C4_SUPPLY_DIR
C5_SCORE_DIR = c5.C5_OUTPUT_DIR
C5_STABILITY_RUN_DIR = (
    ROOT / "runs/V02_实验A锚先行倒装_C5稳定性_r04_20260725"
)
EXPECTED_RUN_NAME = "V02_实验A锚先行倒装_C5稳定性_r04_20260725"
CASE_ORDER = live.CASE_ORDER
STABILITY_PHASE = live.STABILITY_PHASE
EXPECTED_MAX_TOKENS = c4.C4_MAX_TOKENS


class C5StabilityHardStop(ZBatchError):
    """C5 稳定性轮触发止损。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C5StabilityHardStop(
            "required_artifact_missing", f"缺冻结件：{path}"
        )
    return model_benchmark.sha256_file(path)


def _assert_exact_run_dir(run_dir: Path) -> None:
    if run_dir.resolve() != C5_STABILITY_RUN_DIR.resolve():
        raise C5StabilityHardStop(
            "run_dir_not_exact",
            f"C5 稳定性运行目录必须是 {C5_STABILITY_RUN_DIR}",
        )


def _assert_main_conclusion_sealed(
    score_dir: Path = C5_SCORE_DIR,
) -> dict[str, Any]:
    path = score_dir / "sealed_main_conclusion.json"
    if not path.is_file():
        raise C5StabilityHardStop(
            "main_conclusion_missing",
            f"缺冻结件：{path}",
        )
    conclusion = read_json(path)
    if (
        conclusion.get("selected_conclusion") != c5.CONCLUSION_MISSING
        or conclusion.get("main_conclusion_locked_before_stability") is not True
        or conclusion.get("stability_diagnostic_may_not_change_conclusion")
        is not True
    ):
        raise C5StabilityHardStop(
            "main_conclusion_not_sealed",
            "C5 三选一主结论没有先封存，禁止稳定性复测",
        )
    score_path = score_dir / "offline_score_receipt.json"
    if (
        sha256_file(score_path)
        != conclusion.get("offline_score_receipt_sha256")
    ):
        raise C5StabilityHardStop(
            "main_conclusion_score_sha_mismatch",
            "C5 主结论绑定的离线程序票 SHA 漂移",
        )
    return {
        "selected_conclusion": conclusion["selected_conclusion"],
        "sealed_main_conclusion_sha256": sha256_file(path),
        "offline_score_receipt_sha256": sha256_file(score_path),
    }


def _assert_c4_main_closed(
    c4_run_dir: Path = C4_RUN_DIR,
    c4_supply_dir: Path = C4_SUPPLY_DIR,
) -> dict[str, Any]:
    c4.verify_prepared(c4_run_dir, c4_supply_dir)
    if (c4_run_dir / "hard_stop.json").is_file():
        raise C5StabilityHardStop(
            "c4_main_hard_stopped", "C4 主测目录存在硬停票"
        )
    completion_path = c4_run_dir / "completion/main.json"
    completion = read_json(completion_path)
    if (
        completion.get("status") != "main_mechanical_pass_pending_offline_score"
        or completion.get("case_ids") != list(CASE_ORDER)
        or completion.get("logical_samples") != 3
        or completion.get("network_attempts") != 3
    ):
        raise C5StabilityHardStop(
            "c4_main_not_closed", "C4 三章主测没有完整机械收口"
        )
    candidate_rows: list[dict[str, Any]] = []
    for case_id in CASE_ORDER:
        audited = live.audit_sample(
            c4_run_dir,
            phase=live.MAIN_PHASE,
            case_id=case_id,
            supply_dir=c4_supply_dir,
        )
        if audited.get("status") != "mechanical_pass_candidate_only":
            raise C5StabilityHardStop(
                "c4_main_sample_drift", f"{case_id} C4 主样张不能重建"
            )
        candidate_rows.append(
            {
                "case_id": case_id,
                "candidate_sha256": sha256_file(
                    c4_run_dir
                    / f"samples/main/{case_id}/candidate/model_json.json"
                ),
                "request_artifact_sha256": sha256_file(
                    c4_run_dir
                    / f"prepared/main/{case_id}/request_artifact.json"
                ),
                "request_body_sha256": sha256_file(
                    c4_run_dir
                    / f"prepared/main/{case_id}/request_body.json"
                ),
            }
        )
    return {
        "main_completion_sha256": sha256_file(completion_path),
        "main_candidates": candidate_rows,
    }


def _prepared_artifacts(
    run_dir: Path,
    *,
    c4_run_dir: Path = C4_RUN_DIR,
    c4_supply_dir: Path = C4_SUPPLY_DIR,
    score_dir: Path = C5_SCORE_DIR,
) -> dict[str, bytes]:
    _assert_exact_run_dir(run_dir)
    conclusion = _assert_main_conclusion_sealed(score_dir)
    main = _assert_c4_main_closed(c4_run_dir, c4_supply_dir)
    artifacts: dict[str, bytes] = {}
    equivalence_rows: list[dict[str, Any]] = []
    for case_id in CASE_ORDER:
        for suffix in ("request_artifact.json", "request_body.json"):
            source = c4_run_dir / f"prepared/main/{case_id}/{suffix}"
            artifacts[f"prepared/main/{case_id}/{suffix}"] = source.read_bytes()
        catalog = c4_run_dir / f"prepared/catalogs/{case_id}.json"
        artifacts[f"prepared/catalogs/{case_id}.json"] = catalog.read_bytes()
        artifact = read_json(
            c4_run_dir
            / f"prepared/main/{case_id}/request_artifact.json"
        )
        body = artifact.get("body")
        if not isinstance(body, Mapping):
            raise C5StabilityHardStop(
                "c4_request_body_missing", f"{case_id} C4 请求缺 body"
            )
        expected_sampling = {
            "model": live.PINNED_MODEL,
            "temperature": 0.2,
            "max_tokens": EXPECTED_MAX_TOKENS,
            "n": 1,
            "reasoning_effort": "medium",
            "response_format": {"type": "json_object"},
        }
        if any(body.get(key) != value for key, value in expected_sampling.items()):
            raise C5StabilityHardStop(
                "c4_sampling_parameter_drift",
                f"{case_id} C4 请求参数不再是获批复测参数",
            )
        equivalence_rows.append(
            {
                "case_id": case_id,
                "source_request_artifact_sha256": sha256_file(
                    c4_run_dir
                    / f"prepared/main/{case_id}/request_artifact.json"
                ),
                "source_request_body_sha256": sha256_file(
                    c4_run_dir
                    / f"prepared/main/{case_id}/request_body.json"
                ),
                "messages_sha256": model_benchmark.sha256_bytes(
                    json.dumps(
                        body["messages"], ensure_ascii=False
                    ).encode("utf-8")
                ),
                "sampling_parameters": expected_sampling,
                "byte_identical_copy_required": True,
            }
        )
    provider_route = c4_run_dir / "prepared/provider_route.json"
    artifacts["prepared/provider_route.json"] = provider_route.read_bytes()
    artifacts["prepared/C5_main_conclusion_lock.json"] = json_bytes(conclusion)
    artifacts["prepared/C5_request_equivalence.json"] = json_bytes(
        {
            "schema_version": "v02-c5-stability-request-equivalence.v1",
            "status": "PASS_EXACT_C4_REQUESTS",
            "rows": equivalence_rows,
            "model_visible_input_changed": False,
            "sampling_parameters_changed": False,
            "max_tokens": EXPECTED_MAX_TOKENS,
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    artifacts["prepared/C5_stability_plan.json"] = json_bytes(
        {
            "schema_version": "v02-c5-stability-plan.v1",
            "status": "FROZEN_NOT_SENT",
            "run_id": run_dir.name,
            "main_reference": main,
            "case_order": list(CASE_ORDER),
            "logical_request_ids": [
                f"V02-C5-STABILITY-STABILITY-{case_id}"
                for case_id in CASE_ORDER
            ],
            "stability_calls": 3,
            "max_attempts_per_case": 1,
            "retry_allowed": False,
            "third_round_allowed": False,
            "main_result_selection": "C4_MAIN_ONLY",
            "stability_may_change_main_conclusion": False,
            "candidate_only": True,
            "deepseek_official_api_used": False,
        }
    )
    vector = {
        relative: model_benchmark.sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["prepared/C5_mechanical_verification.json"] = json_bytes(
        {
            "schema_version": "v02-c5-stability-prepared-verification.v1",
            "status": "PASS_TWICE_IDENTICAL",
            "vector": vector,
            "vector_sha256": c5.canonical_sha(vector),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def prepare_run(
    run_dir: Path = C5_STABILITY_RUN_DIR,
    *,
    c4_run_dir: Path = C4_RUN_DIR,
    c4_supply_dir: Path = C4_SUPPLY_DIR,
    score_dir: Path = C5_SCORE_DIR,
) -> dict[str, Any]:
    if run_dir.exists() and any(path.is_file() for path in run_dir.rglob("*")):
        raise C5StabilityHardStop(
            "run_dir_not_empty", f"C5 稳定性目录已存在：{run_dir}"
        )
    first = _prepared_artifacts(
        run_dir,
        c4_run_dir=c4_run_dir,
        c4_supply_dir=c4_supply_dir,
        score_dir=score_dir,
    )
    second = _prepared_artifacts(
        run_dir,
        c4_run_dir=c4_run_dir,
        c4_supply_dir=c4_supply_dir,
        score_dir=score_dir,
    )
    if first != second:
        raise C5StabilityHardStop(
            "prepared_double_run_drift", "C5 稳定性准备连续两次不一致"
        )
    for relative, raw in sorted(first.items()):
        live.write_bytes_exclusive(run_dir / relative, raw)
    return verify_prepared(
        run_dir,
        c4_run_dir=c4_run_dir,
        c4_supply_dir=c4_supply_dir,
        score_dir=score_dir,
    )


def verify_prepared(
    run_dir: Path = C5_STABILITY_RUN_DIR,
    *,
    c4_run_dir: Path = C4_RUN_DIR,
    c4_supply_dir: Path = C4_SUPPLY_DIR,
    score_dir: Path = C5_SCORE_DIR,
) -> dict[str, Any]:
    expected = _prepared_artifacts(
        run_dir,
        c4_run_dir=c4_run_dir,
        c4_supply_dir=c4_supply_dir,
        score_dir=score_dir,
    )
    for relative, raw in expected.items():
        path = run_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise C5StabilityHardStop(
                "prepared_artifact_drift", f"C5 稳定性准备件漂移：{relative}"
            )
    scan = live.secret_scan(run_dir)
    if scan["authorization_header_hit_count"]:
        raise C5StabilityHardStop(
            "authorization_trace_in_prepared",
            "C5 稳定性准备件出现鉴权字段",
        )
    return {
        "status": "PASS_C5_STABILITY_PREPARED",
        "run_id": run_dir.name,
        "case_order": list(CASE_ORDER),
        "request_count": 3,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _event_signatures(path: Path) -> list[tuple[Any, ...]]:
    document = read_json(path)
    events = document.get("events")
    if not isinstance(events, list):
        raise C5StabilityHardStop(
            "candidate_events_missing", f"候选件缺 events：{path}"
        )
    return [
        live._event_signature(row)
        for row in events
        if isinstance(row, Mapping)
    ]


def cross_run_disagreement(
    c4_run_dir: Path,
    stability_run_dir: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_slots = 0
    changed_slots = 0
    for case_id in CASE_ORDER:
        main_path = (
            c4_run_dir
            / f"samples/main/{case_id}/candidate/model_json.json"
        )
        repeat_path = (
            stability_run_dir
            / f"samples/stability/{case_id}/candidate/model_json.json"
        )
        main_events = _event_signatures(main_path)
        repeat_events = _event_signatures(repeat_path)
        width = max(len(main_events), len(repeat_events))
        changed = sum(
            index >= len(main_events)
            or index >= len(repeat_events)
            or main_events[index] != repeat_events[index]
            for index in range(width)
        )
        total_slots += width
        changed_slots += changed
        rows.append(
            {
                "case_id": case_id,
                "main_event_count": len(main_events),
                "stability_event_count": len(repeat_events),
                "compared_slots": width,
                "changed_slots": changed,
                "disagreement_rate": changed / width if width else 0.0,
                "exact_payload_equal": main_path.read_bytes()
                == repeat_path.read_bytes(),
                "main_candidate_sha256": sha256_file(main_path),
                "stability_candidate_sha256": sha256_file(repeat_path),
            }
        )
    return {
        "schema_version": "v02-c5-cross-run-stability-disagreement.v1",
        "status": "DIAGNOSTIC_ONLY_NEVER_CHANGES_MAIN",
        "chapters": rows,
        "compared_slots": total_slots,
        "changed_slots": changed_slots,
        "overall_disagreement_rate": (
            changed_slots / total_slots if total_slots else 0.0
        ),
        "main_result_selection": "C4_MAIN_ONLY",
        "stability_result_can_replace_main": False,
        "stability_result_can_change_c5_conclusion": False,
    }


def _attempt_count(run_dir: Path) -> int:
    return sum(
        len(live._attempt_rows(path))
        for path in run_dir.glob(
            "samples/stability/*/transport/call_attempts.jsonl"
        )
    )


def run_stability(
    run_dir: Path = C5_STABILITY_RUN_DIR,
    *,
    c4_run_dir: Path = C4_RUN_DIR,
    c4_supply_dir: Path = C4_SUPPLY_DIR,
    score_dir: Path = C5_SCORE_DIR,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    verify_prepared(
        run_dir,
        c4_run_dir=c4_run_dir,
        c4_supply_dir=c4_supply_dir,
        score_dir=score_dir,
    )
    if (run_dir / "hard_stop.json").is_file():
        raise C5StabilityHardStop(
            "run_already_hard_stopped", "C5 稳定性轮已硬停，禁止补发"
        )
    completion_path = run_dir / "completion/stability.json"
    if completion_path.is_file():
        return read_json(completion_path)
    if _attempt_count(run_dir):
        raise C5StabilityHardStop(
            "attempt_without_completion",
            "C5 稳定性轮已有尝试但未收口，禁止再次发网",
        )
    claim_path = run_dir / "transport/C5_stability_claim.json"
    if claim_path.is_file():
        raise C5StabilityHardStop(
            "claim_without_completion",
            "C5 稳定性轮已有占用票但未收口，禁止再次发网",
        )
    key = os.environ.get(live.PINNED_KEY_ENV, "")
    if not key:
        raise C5StabilityHardStop(
            "api_key_not_loaded", "缺 SENSENOVA_API_KEY，尚未发网"
        )
    pre_send_scan = live.secret_scan(run_dir, (key,))
    if (
        pre_send_scan["exact_key_hit_count"]
        or pre_send_scan["authorization_header_hit_count"]
    ):
        raise C5StabilityHardStop(
            "secret_trace_detected_before_send",
            "C5 稳定性准备目录在发网前检出密钥或鉴权头",
        )
    live.write_json_exclusive(
        claim_path,
        {
            "schema_version": "v02-c5-stability-claim.v1",
            "status": "THREE_SAMPLES_CLAIMED_NO_RERUN",
            "case_order": list(CASE_ORDER),
            "logical_request_ids": [
                f"V02-C5-STABILITY-STABILITY-{case_id}"
                for case_id in CASE_ORDER
            ],
            "max_attempts_per_case": 1,
            "retry_allowed": False,
            "third_round_allowed": False,
            "claimed_at": live.now_iso(),
        },
    )
    current_case: str | None = None
    completions: list[dict[str, Any]] = []
    try:
        for current_case in CASE_ORDER:
            completions.append(
                live._execute_sample(
                    run_dir,
                    phase=STABILITY_PHASE,
                    case_id=current_case,
                    key=key,
                    supply_dir=c4_supply_dir,
                    opener=opener,
                    sender_factory=sender_factory,
                    logical_prefix="V02-C5-STABILITY",
                )
            )
        rebuilt = [
            live.audit_sample(
                run_dir,
                phase=STABILITY_PHASE,
                case_id=case_id,
                supply_dir=c4_supply_dir,
            )
            for case_id in CASE_ORDER
        ]
        if [row.get("case_id") for row in rebuilt] != list(CASE_ORDER):
            raise C5StabilityHardStop(
                "stability_audit_order_mismatch",
                "C5 稳定性样张不能按冻结顺序重建",
            )
        scan = live.secret_scan(run_dir, (key,))
        if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
            raise C5StabilityHardStop(
                "secret_trace_detected", "C5 稳定性目录检出密钥或鉴权头"
            )
        diagnostic = cross_run_disagreement(c4_run_dir, run_dir)
        live.write_json_exclusive(
            run_dir / "diagnostics/stability_disagreement.json",
            diagnostic,
        )
        usage_by_case = {
            row["case_id"]: row["usage"] for row in completions
        }
        result = {
            "schema_version": "v02-c5-stability-completion.v1",
            "status": "STABILITY_MECHANICAL_PASS_DIAGNOSTIC_ONLY",
            "case_ids": list(CASE_ORDER),
            "logical_samples": 3,
            "network_attempts": _attempt_count(run_dir),
            "usage_by_case": usage_by_case,
            "total_tokens": sum(
                int(row["total_tokens"]) for row in usage_by_case.values()
            ),
            "main_conclusion": c5.CONCLUSION_MISSING,
            "main_conclusion_changed": False,
            "quality_result_registered": False,
            "candidate_only": True,
            "third_round_allowed": False,
            "secret_scan": scan,
            "completed_at": live.now_iso(),
        }
        live.write_json_exclusive(completion_path, result)
        return result
    except (
        C5StabilityHardStop,
        live.V02LiveHardStop,
        model_benchmark.BenchmarkHardStop,
        ZBatchError,
    ) as exc:
        error = (
            exc
            if isinstance(exc, live.V02LiveHardStop)
            else live.V02LiveHardStop(
                getattr(exc, "reason_code", "run_failure"),
                str(exc),
            )
        )
        live._write_hard_stop(
            run_dir,
            phase=STABILITY_PHASE,
            case_id=current_case,
            error=error,
            scan=live.secret_scan(run_dir, (key,)),
        )
        raise C5StabilityHardStop(error.reason_code, str(error)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify", "run", "status"):
        item = sub.add_parser(command)
        item.add_argument("--run-dir", type=Path, default=C5_STABILITY_RUN_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = args.run_dir.resolve()
    if args.command == "prepare":
        result = prepare_run(run_dir)
    elif args.command == "verify":
        result = verify_prepared(run_dir)
    elif args.command == "run":
        result = run_stability(run_dir)
    else:
        result = {
            "run_id": run_dir.name,
            "prepared": (
                run_dir / "prepared/C5_stability_plan.json"
            ).is_file(),
            "attempts": _attempt_count(run_dir),
            "completed": (run_dir / "completion/stability.json").is_file(),
            "hard_stopped": (run_dir / "hard_stop.json").is_file(),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
