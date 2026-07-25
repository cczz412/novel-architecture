#!/usr/bin/env python3
"""V02/C4：SenseNova 64K 运输面唯一探针与过闸续跑。

本工具只服务 C4：

- 步一从封存的 C2/C3 usage 与本地平台文档核账，0 API；
- 步二只允许 B02-U0039 发一次 64K 探针；
- 探针满足 ``finish_reason=stop``、完整 JSON 和闭集锚机械闸后，
  才允许继续 B03/B01；
- 旧 C2/C3 目录只读，任何失败都在新的 C4 r03 目录硬停。
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import v02_anchor_first_experiment as prep
import v02_anchor_first_live_runner as live
from pipeline_common import model_benchmark
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
C2_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C2_r01_20260725"
C3_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C3_r02_20260725"
C3_SUPPLY_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C3_claim_span_prompt_explicit_examples"
)
C4_SUPPLY_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C4_transport_probe"
)
C4_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C4_r03_20260725"

ATTACHMENTS_ROOT = Path(
    os.environ.get("CODEX_ATTACHMENTS_DIR", Path.home() / ".codex/attachments")
).expanduser()
DOC_A = (
    ATTACHMENTS_ROOT
    / "a7b4b227-d503-47e9-9237-baeadedd2c65/pasted-text.txt"
)
DOC_B = (
    ATTACHMENTS_ROOT
    / "d0c05625-d597-4b3d-8531-0310e7ca9ee8/pasted-text.txt"
)

C4_SCHEMA = "v02-anchor-first-c4-transport-probe.v1"
C4_MAX_TOKENS = 65536
PROBE_CASE_ID = "B02-U0039"
REMAINING_CASE_IDS = ("B03-U0041", "B01-U0033")
EXPECTED_RUN_NAME = "V02_实验A锚先行倒装_C4_r03_20260725"
AUTHORITY_TIME = "2026-07-25T08:14:00+08:00"


class C4HardStop(ZBatchError):
    """C4 触发预写保险丝。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return prep.canonical_sha(value)


def display_path(path: Path) -> str:
    return prep.display_path(path)


def _raw_response(run_dir: Path) -> Path:
    return (
        run_dir
        / "samples/main/B02-U0039/transport/raw_responses/attempt01.json"
    )


def _attempt_ledger(run_dir: Path) -> Path:
    return run_dir / "samples/main/B02-U0039/transport/call_attempts.jsonl"


def _only_attempt(path: Path) -> dict[str, Any]:
    rows = live._attempt_rows(path)
    if len(rows) != 1:
        raise C4HardStop(
            "historical_usage_ledger_not_singleton",
            f"封存账不是唯一一次尝试：{display_path(path)}",
        )
    return rows[0]


def _document_lines(path: Path, line_numbers: Sequence[int]) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    selected: list[dict[str, Any]] = []
    for number in line_numbers:
        if number <= 0 or number > len(lines):
            raise C4HardStop(
                "platform_document_line_missing",
                f"平台文档缺第 {number} 行：{path}",
            )
        selected.append({"line": number, "text": lines[number - 1]})
    return {
        "path": path.as_posix(),
        "sha256": prep.sha256_file(path),
        "lines": selected,
    }


def _round_usage(label: str, run_dir: Path) -> dict[str, Any]:
    raw_path = _raw_response(run_dir)
    response = read_json(raw_path)
    choices = response.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], Mapping)
    ):
        raise C4HardStop("historical_response_contract", f"{label} choices 非唯一对象")
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        raise C4HardStop("historical_usage_missing", f"{label} 缺 usage")
    live._validate_usage(usage)
    details = usage.get("completion_tokens_details")
    reasoning = details.get("reasoning_tokens") if isinstance(details, Mapping) else None
    if isinstance(reasoning, bool) or not isinstance(reasoning, int):
        raise C4HardStop("historical_reasoning_usage_missing", f"{label} 缺 reasoning_tokens")
    completion = int(usage["completion_tokens"])
    if reasoning > completion:
        raise C4HardStop("historical_reasoning_usage_invalid", f"{label} reasoning 超 completion")
    finish = choices[0].get("finish_reason")
    content = choices[0].get("message", {}).get("content")
    complete_json = False
    if finish == "stop" and isinstance(content, str):
        try:
            complete_json = isinstance(json.loads(content), dict)
        except json.JSONDecodeError:
            complete_json = False
    attempt = _only_attempt(_attempt_ledger(run_dir))
    if attempt.get("usage") != usage:
        raise C4HardStop("historical_usage_mismatch", f"{label} 原始响应与尝试账 usage 不同")
    return {
        "round": label,
        "run_dir": display_path(run_dir),
        "raw_response_sha256": prep.sha256_file(raw_path),
        "attempt_ledger_sha256": prep.sha256_file(_attempt_ledger(run_dir)),
        "finish_reason": finish,
        "complete_json_observed": complete_json,
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "non_reasoning_completion_residual": completion - reasoning,
        "reasoning_share_of_completion": reasoning / completion if completion else 0.0,
        "total_tokens": usage["total_tokens"],
        "usage_raw": dict(usage),
    }


def build_token_accounting() -> dict[str, Any]:
    """只读封存 usage 与平台文档；不读取正式金标正文。"""

    rounds = [
        _round_usage("C2_first_round", C2_RUN_DIR),
        _round_usage("C3_prompt_explicit_round", C3_RUN_DIR),
    ]
    reasoning_values = [row["reasoning_tokens"] for row in rounds]
    residual_values = [row["non_reasoning_completion_residual"] for row in rounds]
    completion_values = [row["completion_tokens"] for row in rounds]
    c2, c3 = rounds
    if c2["finish_reason"] != "stop" or c2["complete_json_observed"] is not True:
        raise C4HardStop("c2_complete_json_evidence_missing", "C2 不能证明完整 JSON 曾自然结束")
    if c3["finish_reason"] != "length":
        raise C4HardStop("c3_length_evidence_missing", "C3 不是 length 触顶")

    docs = [
        _document_lines(DOC_A, (2, 87, 224)),
        _document_lines(DOC_B, (262, 440, 577)),
    ]
    doc_text = "\n".join(
        row["text"] for document in docs for row in document["lines"]
    )
    if "65536" not in doc_text or "64K" not in doc_text:
        raise C4HardStop("platform_cap_evidence_missing", "本地平台文档没有 64K/65536 双证")

    return {
        "schema_version": "v02-c4-token-accounting.v1",
        "status": "pass_zero_call_accounted",
        "authority_time": AUTHORITY_TIME,
        "provider": live.PINNED_PROVIDER,
        "model": live.PINNED_MODEL,
        "rounds": rounds,
        "distribution_n": 2,
        "distributions": {
            "reasoning_tokens": {
                "values": reasoning_values,
                "min": min(reasoning_values),
                "max": max(reasoning_values),
                "mean": statistics.mean(reasoning_values),
                "median": statistics.median(reasoning_values),
            },
            "non_reasoning_completion_residual": {
                "values": residual_values,
                "min": min(residual_values),
                "max": max(residual_values),
                "mean": statistics.mean(residual_values),
                "median": statistics.median(residual_values),
            },
            "completion_tokens": {
                "values": completion_values,
                "min": min(completion_values),
                "max": max(completion_values),
                "mean": statistics.mean(completion_values),
                "median": statistics.median(completion_values),
            },
        },
        "complete_json_estimate": {
            "observed_complete_c2_completion_tokens": c2["completion_tokens"],
            "c3_truncated_at_completion_tokens": c3["completion_tokens"],
            "strict_arithmetic_lower_bound_for_c3_path": c3["completion_tokens"] + 1,
            "exact_required_tokens_known": False,
            "wording": (
                "C2 的 13894 只证明旧题面曾在该输出量完整结束；"
                "C3 在 16001 仍截断，因此 C3 这条生成路径只可确定需要大于 16001，"
                "不能从字符数反推精确需求，也不能保证 65536 必过。"
            ),
        },
        "platform_cap": {
            "max_tokens": C4_MAX_TOKENS,
            "documents": docs,
            "default_65535_is_not_cap": True,
            "reasoning_counted_inside_completion_observed": all(
                row["reasoning_tokens"] <= row["completion_tokens"] for row in rounds
            ),
            "accounting_boundary": (
                "供应商把 reasoning_tokens 放在 completion_tokens_details 下；"
                "completion-reasoning 只记服务端残差，不冒充可见正文精确 token。"
            ),
        },
        "formal_gold_body_read_count": 0,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _actual_c3_delta(
    c4_artifacts: Mapping[str, bytes],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case_id in live.CASE_ORDER:
        relative = f"requests/anchor_first/{case_id}.json"
        c3_path = C3_SUPPLY_DIR / relative
        c3 = read_json(c3_path)
        c4 = json.loads(c4_artifacts[relative])
        c3_body = c3["body"]
        c4_body = c4["body"]
        row = {
            "case_id": case_id,
            "c3_file_sha256": prep.sha256_file(c3_path),
            "c3_request_identity_sha256": canonical_sha(c3),
            "c4_request_identity_sha256": canonical_sha(c4),
            "messages_byte_equivalent": json_bytes(c3_body["messages"])
            == json_bytes(c4_body["messages"]),
            "request_shell_equal": {
                key: value for key, value in c3.items() if key != "body"
            }
            == {key: value for key, value in c4.items() if key != "body"},
            "body_except_max_tokens_equal": {
                key: value for key, value in c3_body.items() if key != "max_tokens"
            }
            == {
                key: value for key, value in c4_body.items() if key != "max_tokens"
            },
            "top_p_omitted_before": "top_p" not in c3_body,
            "top_p_omitted_after": "top_p" not in c4_body,
            "from_max_tokens": c3_body.get("max_tokens"),
            "to_max_tokens": c4_body.get("max_tokens"),
        }
        rows.append(row)
    if any(
        not row["messages_byte_equivalent"]
        or not row["request_shell_equal"]
        or not row["body_except_max_tokens_equal"]
        or not row["top_p_omitted_before"]
        or not row["top_p_omitted_after"]
        or row["from_max_tokens"] != 16000
        or row["to_max_tokens"] != C4_MAX_TOKENS
        for row in rows
    ):
        raise C4HardStop("c4_delta_not_transport_only", "C4 相对封存 C3 不只 max_tokens 一处差异")
    return {
        "schema_version": "v02-c4-vs-sealed-c3-delta.v1",
        "status": "pass_only_max_tokens_changed",
        "sealed_c3_supply_dir": display_path(C3_SUPPLY_DIR),
        "sealed_c3_manifest_sha256": prep.sha256_file(
            C3_SUPPLY_DIR / "artifact_manifest.json"
        ),
        "rows": rows,
        "model_visible_messages_changed": False,
        "changed_request_fields": ["body.max_tokens"],
        "model_api_calls": 0,
        "network_requests": 0,
    }


def build_c4_supply() -> dict[str, bytes]:
    base = prep.build_artifacts(
        selection_k=prep.K_MISSING,
        environ={},
        prompt_variant=prep.PROMPT_VARIANT_C3,
        max_tokens_override=C4_MAX_TOKENS,
    )
    accounting = build_token_accounting()
    delta = _actual_c3_delta(base)
    extras: dict[str, bytes] = {
        "V02_C4_token_accounting.json": prep.canonical_bytes(accounting),
        "V02_C4_vs_sealed_C3_delta.json": prep.canonical_bytes(delta),
        "V02_C4_ownership_ticket.json": prep.canonical_bytes(
            {
                "schema_version": "v02-c4-ownership-ticket.v1",
                "ownership": "V02_new_zone",
                "read_surfaces": [
                    "V02_C3_sealed_supply_read_only",
                    "V02_C2_C3_usage_ledgers_read_only",
                    "local_provider_documents_read_only",
                ],
                "write_surfaces": ["V02_C4_supply", "V02_C4_run_r03"],
                "legacy_write_required": False,
                "stage": "P0_to_P1_transport",
                "formal_gold_or_pointer_write": False,
                "current_chain_write": False,
            }
        ),
    }
    artifacts = {**base, **extras}
    manifest_preimage = {
        relative: prep.sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["V02_C4_bundle_manifest.json"] = prep.canonical_bytes(
        {
            "schema_version": "v02-c4-bundle-manifest.v1",
            "file_total_excluding_self": len(manifest_preimage),
            "files": [
                {"path": relative, "sha256": digest}
                for relative, digest in manifest_preimage.items()
            ],
            "artifact_set_sha256": canonical_sha(manifest_preimage),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def write_or_verify_supply(supply_dir: Path = C4_SUPPLY_DIR) -> dict[str, Any]:
    artifacts = build_c4_supply()
    prep.write_artifacts(supply_dir, artifacts)
    result = prep.verify_artifacts(supply_dir, artifacts)
    if result["status"] != "pass":
        raise C4HardStop("c4_supply_verify_failed", "C4 供料不能机械重建")
    delta = read_json(supply_dir / "V02_C4_vs_sealed_C3_delta.json")
    if delta.get("status") != "pass_only_max_tokens_changed":
        raise C4HardStop("c4_delta_receipt_failed", "C4 差异票未过")
    return {
        **result,
        "supply_dir": display_path(supply_dir),
        "bundle_manifest_sha256": prep.sha256_file(
            supply_dir / "V02_C4_bundle_manifest.json"
        ),
    }


def _c4_prepared_additions(run_dir: Path, supply_dir: Path) -> dict[str, bytes]:
    delta_path = supply_dir / "V02_C4_vs_sealed_C3_delta.json"
    accounting_path = supply_dir / "V02_C4_token_accounting.json"
    lock = {
        "schema_version": "v02-c4-request-lock.v1",
        "status": "frozen_not_sent",
        "run_id": run_dir.name,
        "probe_case_id": PROBE_CASE_ID,
        "remaining_cases": [
            {"case_id": case_id, "status": "FROZEN_NOT_SENT"}
            for case_id in REMAINING_CASE_IDS
        ],
        "probe_max_attempts": 1,
        "probe_may_unlock_remaining": (
            "finish_reason=stop + complete_json + closed_anchor_mechanical_pass"
        ),
        "max_tokens": C4_MAX_TOKENS,
        "reasoning_effort": "medium",
        "messages_changed_from_c3": False,
        "c3_hard_stop_sha256": prep.sha256_file(C3_RUN_DIR / "hard_stop.json"),
        "c3_raw_response_sha256": prep.sha256_file(_raw_response(C3_RUN_DIR)),
        "c4_supply_manifest_sha256": prep.sha256_file(
            supply_dir / "V02_C4_bundle_manifest.json"
        ),
        "c4_delta_sha256": prep.sha256_file(delta_path),
        "c4_accounting_sha256": prep.sha256_file(accounting_path),
        "rerun_or_chapter_switch_allowed": False,
    }
    return {
        "prepared/V02_C4_request_lock.json": json_bytes(lock),
        "prepared/V02_C4_token_accounting.json": accounting_path.read_bytes(),
        "prepared/V02_C4_delta.json": delta_path.read_bytes(),
    }


def prepare_run(
    run_dir: Path = C4_RUN_DIR,
    supply_dir: Path = C4_SUPPLY_DIR,
) -> dict[str, Any]:
    if run_dir.name != EXPECTED_RUN_NAME:
        raise C4HardStop("c4_run_name_not_exact", f"C4 运行名必须是 {EXPECTED_RUN_NAME}")
    write_or_verify_supply(supply_dir)
    live.prepare_run(run_dir, supply_dir)
    for relative, raw in _c4_prepared_additions(run_dir, supply_dir).items():
        live.write_bytes_exclusive(run_dir / relative, raw)
    verify_prepared(run_dir, supply_dir)
    return read_json(run_dir / "prepared/V02_C4_request_lock.json")


def verify_prepared(
    run_dir: Path = C4_RUN_DIR,
    supply_dir: Path = C4_SUPPLY_DIR,
) -> dict[str, Any]:
    if run_dir.name != EXPECTED_RUN_NAME:
        raise C4HardStop("c4_run_name_not_exact", f"C4 运行名必须是 {EXPECTED_RUN_NAME}")
    write_or_verify_supply(supply_dir)
    live.verify_prepared(run_dir, supply_dir)
    for relative, raw in _c4_prepared_additions(run_dir, supply_dir).items():
        path = run_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise C4HardStop("c4_prepared_addition_drift", f"C4 准备件漂移：{relative}")
    for case_id in live.CASE_ORDER:
        c3 = read_json(C3_SUPPLY_DIR / f"requests/anchor_first/{case_id}.json")
        c4 = read_json(run_dir / f"prepared/main/{case_id}/request_artifact.json")
        if c3["body"]["messages"] != c4["body"]["messages"]:
            raise C4HardStop("c4_messages_drift", f"{case_id} messages 漂移")
    return {
        "status": "pass_c4_prepared",
        "run_id": run_dir.name,
        "probe_case_id": PROBE_CASE_ID,
        "remaining_status": "FROZEN_NOT_SENT",
        "max_tokens": C4_MAX_TOKENS,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _c4_hard_stop(
    run_dir: Path,
    *,
    case_id: str | None,
    error: BaseException,
    key: str = "",
) -> dict[str, Any]:
    path = run_dir / "hard_stop.json"
    if path.is_file():
        return read_json(path)
    attempt_rows = [
        row
        for ledger in run_dir.glob("samples/*/*/transport/call_attempts.jsonl")
        for row in live._attempt_rows(ledger)
    ]
    ticket = {
        "schema_version": "v02-c4-hard-stop.v1",
        "status": "hard_stop_no_patch_no_rerun",
        "case_id": case_id,
        "reason_code": getattr(error, "reason_code", "run_failure"),
        "error_type": type(error).__name__,
        "message": str(error),
        "logical_requests_started": len(
            {row.get("logical_request_id") for row in attempt_rows}
        ),
        "network_attempts": len(attempt_rows),
        "probe_max_attempts": 1,
        "probe_rerun_allowed": False,
        "chapter_switch_allowed": False,
        "truncated_response_salvage_allowed": False,
        "later_chapters_sent": any(
            case_id in str(row.get("logical_request_id"))
            for row in attempt_rows
            for case_id in REMAINING_CASE_IDS
        ),
        "secret_scan": live.secret_scan(run_dir, (key,) if key else ()),
        "stopped_at": now_iso(),
    }
    live.write_json_exclusive(path, ticket)
    return ticket


def _probe_attempts(run_dir: Path) -> list[dict[str, Any]]:
    return live._attempt_rows(
        run_dir / f"samples/main/{PROBE_CASE_ID}/transport/call_attempts.jsonl"
    )


def _assert_no_remaining_attempts(run_dir: Path) -> None:
    for case_id in REMAINING_CASE_IDS:
        ledgers = list(
            (run_dir / f"samples/main/{case_id}").glob(
                "transport/call_attempts.jsonl"
            )
        )
        if any(live._attempt_rows(path) for path in ledgers):
            raise C4HardStop(
                "remaining_chapter_sent_before_probe_gate",
                f"{case_id} 在探针过闸前已有调用",
            )


def run_probe(
    run_dir: Path = C4_RUN_DIR,
    supply_dir: Path = C4_SUPPLY_DIR,
    *,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    verify_prepared(run_dir, supply_dir)
    if (run_dir / "hard_stop.json").is_file():
        raise C4HardStop("run_already_hard_stopped", "C4 已硬停，禁止再发")
    if (run_dir / "completion/probe.json").is_file():
        return read_json(run_dir / "completion/probe.json")
    if _probe_attempts(run_dir):
        raise C4HardStop("probe_attempt_already_exists", "唯一探针已有尝试，禁止重发")
    _assert_no_remaining_attempts(run_dir)
    key = os.environ.get(live.PINNED_KEY_ENV, "")
    if not key:
        raise C4HardStop("api_key_not_loaded", "缺 SENSENOVA_API_KEY，未占用探针")
    live.write_json_exclusive(
        run_dir / "transport/V02_C4_probe_claim.json",
        {
            "schema_version": "v02-c4-probe-claim.v1",
            "status": "one_probe_claimed",
            "logical_request_id": f"V02-C4-PROBE-MAIN-{PROBE_CASE_ID}",
            "case_id": PROBE_CASE_ID,
            "max_network_attempts": 1,
            "max_tokens": C4_MAX_TOKENS,
            "claimed_at": now_iso(),
        },
    )
    try:
        completion = live._execute_sample(
            run_dir,
            phase=live.MAIN_PHASE,
            case_id=PROBE_CASE_ID,
            key=key,
            supply_dir=supply_dir,
            opener=opener,
            sender_factory=sender_factory,
            logical_prefix="V02-C4-PROBE",
        )
        rebuilt = live.audit_sample(
            run_dir,
            phase=live.MAIN_PHASE,
            case_id=PROBE_CASE_ID,
            supply_dir=supply_dir,
        )
        if rebuilt != completion:
            raise C4HardStop("probe_audit_mismatch", "探针完成票不能从原始响应重建")
        _assert_no_remaining_attempts(run_dir)
        scan = live.secret_scan(run_dir, (key,))
        if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
            raise C4HardStop("secret_trace_detected", "C4 运行目录检出密钥或鉴权头")
        ticket = {
            "schema_version": "v02-c4-probe-completion.v1",
            "status": "transport_probe_pass_unlock_remaining",
            "case_id": PROBE_CASE_ID,
            "finish_reason": "stop",
            "complete_json": True,
            "closed_anchor_mechanical_gate": "pass",
            "claim_span_gate": "pass",
            "network_attempts": len(_probe_attempts(run_dir)),
            "usage": completion["usage"],
            "counts_as_quality_result": False,
            "counts_against_main_budget": False,
            "reused_as_main_first_chapter": True,
            "remaining_cases_unlocked": list(REMAINING_CASE_IDS),
            "secret_scan": scan,
            "completed_at": now_iso(),
        }
        live.write_json_exclusive(run_dir / "completion/probe.json", ticket)
        return ticket
    except (
        C4HardStop,
        live.V02LiveHardStop,
        model_benchmark.BenchmarkHardStop,
        ZBatchError,
    ) as exc:
        error = (
            exc
            if isinstance(exc, C4HardStop)
            else C4HardStop(getattr(exc, "reason_code", "run_failure"), str(exc))
        )
        _c4_hard_stop(run_dir, case_id=PROBE_CASE_ID, error=error, key=key)
        raise error from exc


def continue_main(
    run_dir: Path = C4_RUN_DIR,
    supply_dir: Path = C4_SUPPLY_DIR,
    *,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    verify_prepared(run_dir, supply_dir)
    if (run_dir / "hard_stop.json").is_file():
        raise C4HardStop("run_already_hard_stopped", "C4 已硬停，禁止续发")
    probe_path = run_dir / "completion/probe.json"
    if not probe_path.is_file():
        raise C4HardStop("probe_gate_not_passed", "唯一探针未过闸")
    probe = read_json(probe_path)
    if probe.get("status") != "transport_probe_pass_unlock_remaining":
        raise C4HardStop("probe_gate_not_passed", "唯一探针未过闸")
    live.audit_sample(
        run_dir,
        phase=live.MAIN_PHASE,
        case_id=PROBE_CASE_ID,
        supply_dir=supply_dir,
    )
    if len(_probe_attempts(run_dir)) != 1:
        raise C4HardStop("probe_attempt_count_drift", "探针不是唯一一次尝试")
    if (run_dir / "completion/main.json").is_file():
        return read_json(run_dir / "completion/main.json")
    _assert_no_remaining_attempts(run_dir)
    key = os.environ.get(live.PINNED_KEY_ENV, "")
    if not key:
        raise C4HardStop("api_key_not_loaded", "缺 SENSENOVA_API_KEY，后两章未发")
    live.write_json_exclusive(
        run_dir / "transport/V02_C4_main_continuation_claim.json",
        {
            "schema_version": "v02-c4-main-continuation-claim.v1",
            "status": "two_remaining_samples_claimed",
            "probe_case_reused_without_resend": PROBE_CASE_ID,
            "remaining_order": list(REMAINING_CASE_IDS),
            "logical_request_ids": [
                f"V02-C4-MAIN-MAIN-{case_id}" for case_id in REMAINING_CASE_IDS
            ],
            "claimed_at": now_iso(),
        },
    )
    current_case: str | None = None
    try:
        for current_case in REMAINING_CASE_IDS:
            live._execute_sample(
                run_dir,
                phase=live.MAIN_PHASE,
                case_id=current_case,
                key=key,
                supply_dir=supply_dir,
                opener=opener,
                sender_factory=sender_factory,
                logical_prefix="V02-C4-MAIN",
            )
        completions = [
            live.audit_sample(
                run_dir,
                phase=live.MAIN_PHASE,
                case_id=case_id,
                supply_dir=supply_dir,
            )
            for case_id in live.CASE_ORDER
        ]
        scan = live.secret_scan(run_dir, (key,))
        if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
            raise C4HardStop("secret_trace_detected", "C4 运行目录检出密钥或鉴权头")
        usage_by_case = {
            row["case_id"]: row["usage"] for row in completions
        }
        result = {
            "schema_version": "v02-c4-main-completion.v1",
            "status": "main_mechanical_pass_pending_offline_score",
            "case_ids": list(live.CASE_ORDER),
            "probe_case_reused_without_resend": PROBE_CASE_ID,
            "logical_samples": 3,
            "network_attempts": sum(
                len(
                    live._attempt_rows(
                        run_dir
                        / f"samples/main/{case_id}/transport/call_attempts.jsonl"
                    )
                )
                for case_id in live.CASE_ORDER
            ),
            "usage_by_case": usage_by_case,
            "total_tokens": sum(
                int(row["total_tokens"]) for row in usage_by_case.values()
            ),
            "quality_result_registered": False,
            "candidate_only": True,
            "stability_not_run": True,
            "secret_scan": scan,
            "completed_at": now_iso(),
        }
        live.write_json_exclusive(run_dir / "completion/main.json", result)
        return result
    except (
        C4HardStop,
        live.V02LiveHardStop,
        model_benchmark.BenchmarkHardStop,
        ZBatchError,
    ) as exc:
        error = (
            exc
            if isinstance(exc, C4HardStop)
            else C4HardStop(getattr(exc, "reason_code", "run_failure"), str(exc))
        )
        _c4_hard_stop(run_dir, case_id=current_case, error=error, key=key)
        raise error from exc


def status(run_dir: Path = C4_RUN_DIR) -> dict[str, Any]:
    return {
        "run_dir": display_path(run_dir),
        "prepared": (run_dir / "prepared/V02_C4_request_lock.json").is_file(),
        "probe_attempts": len(_probe_attempts(run_dir)),
        "probe_completed": (run_dir / "completion/probe.json").is_file(),
        "main_completed": (run_dir / "completion/main.json").is_file(),
        "hard_stopped": (run_dir / "hard_stop.json").is_file(),
        "remaining_attempts": {
            case_id: len(
                live._attempt_rows(
                    run_dir
                    / f"samples/main/{case_id}/transport/call_attempts.jsonl"
                )
            )
            for case_id in REMAINING_CASE_IDS
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("account", "0 API 核算 C2/C3 token 与平台上限"),
        ("prepare", "生成 C4 供料与 r03 冻结运行件"),
        ("verify", "机械重建并核对 C4 冻结件"),
        ("run-probe", "只发 B02-U0039 唯一 64K 探针"),
        ("continue-main", "探针过闸后只发 B03/B01"),
        ("status", "读取 C4 状态"),
    ):
        item = sub.add_parser(command, help=help_text)
        item.add_argument("--run-dir", type=Path, default=C4_RUN_DIR)
        item.add_argument("--supply-dir", type=Path, default=C4_SUPPLY_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = args.run_dir.resolve()
    supply_dir = args.supply_dir.resolve()
    if args.command == "account":
        result = build_token_accounting()
    elif args.command == "prepare":
        result = prepare_run(run_dir, supply_dir)
    elif args.command == "verify":
        result = verify_prepared(run_dir, supply_dir)
    elif args.command == "run-probe":
        result = run_probe(run_dir, supply_dir)
    elif args.command == "continue-main":
        result = continue_main(run_dir, supply_dir)
    elif args.command == "status":
        result = status(run_dir)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
