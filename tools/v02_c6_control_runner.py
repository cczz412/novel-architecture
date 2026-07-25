#!/usr/bin/env python3
"""V02/C6：C1 对照臂三章一次性正式执行器。

这个工具只做一件事：把 C1 已锁定的三份 ``control`` 请求发给
SenseNova ``deepseek-v4-flash``。相对 C1 请求，唯一允许的改动是把
``max_tokens`` 从 16000 抬到 65536；模型可见消息、其余请求外壳、
供料与采样参数必须保持不变。

每章最多一次请求，不重试、不换章、不挑结果。任一运输或机械闸失败，
整轮立即硬停。机械闸只检查 z-event-v1 结构、章号、连续事件 ID 与
目录内锚，不做语义判分。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import v02_anchor_first_experiment as prep
import v02_anchor_first_live_runner as live
from pipeline_common import model_benchmark
from zbatch_modules import neutral_extract
from zbatch_modules import z83_retry_transport
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
C1_SUPPLY_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C_anchor_first_experiment"
)
C6_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C6对照臂_r05_20260725"
EXPECTED_RUN_NAME = "V02_实验A锚先行倒装_C6对照臂_r05_20260725"

CASE_ORDER = live.CASE_ORDER
PHASE = live.MAIN_PHASE
CONTRACT_VERSION = "v02-c6-control-runner.v1"
SOURCE_MAX_TOKENS = 16000
C6_MAX_TOKENS = 65536


class C6ControlHardStop(ZBatchError):
    """C6 对照臂触发预写止损线。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return prep.canonical_sha(value)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise C6ControlHardStop(
            "required_artifact_missing",
            f"缺冻结件：{path}",
        )
    return model_benchmark.sha256_file(path)


def display_path(path: Path) -> str:
    return prep.display_path(path)


def _assert_exact_run_dir(run_dir: Path) -> None:
    if run_dir.resolve() != C6_RUN_DIR.resolve():
        raise C6ControlHardStop(
            "run_dir_not_exact",
            f"C6 对照臂运行目录必须是 {C6_RUN_DIR}",
        )


def _source_request_path(case_id: str) -> Path:
    return C1_SUPPLY_DIR / f"requests/control/{case_id}.json"


def _source_catalog_path(case_id: str) -> Path:
    return C1_SUPPLY_DIR / f"catalogs/{case_id}.json"


def _control_lock_rows() -> list[dict[str, Any]]:
    lock = read_json(C1_SUPPLY_DIR / "request_lock.json")
    if lock.get("schema_version") != "v02-anchor-first-request-lock.v1":
        raise C6ControlHardStop("c1_request_lock_drift", "C1 请求锁版本漂移")
    rows = lock.get("control_requests")
    if (
        not isinstance(rows, list)
        or [row.get("case_id") for row in rows] != list(CASE_ORDER)
    ):
        raise C6ControlHardStop(
            "c1_control_order_drift",
            "C1 对照请求顺序不再是冻结三章",
        )
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise C6ControlHardStop(
                "c1_control_lock_row_invalid",
                "C1 对照请求锁含非对象行",
            )
        result.append(dict(row))
    return result


def _assert_control_source(
    case_id: str,
    request: Mapping[str, Any],
    *,
    lock_sha256: str,
) -> None:
    expected_top = {
        "schema_version",
        "case_id",
        "provider",
        "api_base_url",
        "api_endpoint",
        "model",
        "source_body_sha256",
        "catalog_sha256",
        "_security",
        "arm",
        "body",
    }
    if set(request) != expected_top:
        raise C6ControlHardStop(
            "c1_control_shell_drift",
            f"{case_id} C1 对照请求外壳字段漂移",
        )
    expected_identity = {
        "schema_version": "v02-prepared-request.v1",
        "case_id": case_id,
        "provider": live.PINNED_PROVIDER,
        "api_base_url": "https://token.sensenova.cn/v1",
        "api_endpoint": "/chat/completions",
        "model": live.PINNED_MODEL,
        "_security": "no_api_key_no_authorization",
        "arm": "control",
    }
    for field, expected in expected_identity.items():
        if request.get(field) != expected:
            raise C6ControlHardStop(
                "c1_control_identity_drift",
                f"{case_id} C1 对照请求 {field} 漂移",
            )
    if canonical_sha(request) != lock_sha256:
        raise C6ControlHardStop(
            "c1_control_lock_sha_mismatch",
            f"{case_id} C1 对照请求不能由请求锁重建",
        )
    body = request.get("body")
    if not isinstance(body, Mapping):
        raise C6ControlHardStop(
            "c1_control_body_missing",
            f"{case_id} C1 对照请求缺 body",
        )
    expected_sampling = {
        "model": live.PINNED_MODEL,
        "temperature": 0.2,
        "max_tokens": SOURCE_MAX_TOKENS,
        "n": 1,
        "reasoning_effort": "medium",
        "response_format": {"type": "json_object"},
    }
    if set(body) != {"messages", *expected_sampling}:
        raise C6ControlHardStop(
            "c1_control_body_fields_drift",
            f"{case_id} C1 对照请求 body 字段漂移",
        )
    for field, expected in expected_sampling.items():
        if body.get(field) != expected:
            raise C6ControlHardStop(
                "c1_control_sampling_drift",
                f"{case_id} C1 对照请求参数 {field} 漂移",
            )
    messages = body.get("messages")
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or [row.get("role") for row in messages if isinstance(row, Mapping)]
        != ["system", "user"]
    ):
        raise C6ControlHardStop(
            "c1_control_messages_drift",
            f"{case_id} C1 对照请求消息结构漂移",
        )
    catalog = read_json(_source_catalog_path(case_id))
    if request.get("catalog_sha256") != canonical_sha(catalog):
        raise C6ControlHardStop(
            "c1_control_catalog_sha_mismatch",
            f"{case_id} C1 对照请求目录 SHA 漂移",
        )
    source = prep.load_case_source(live._case(case_id))
    if request.get("source_body_sha256") != source["body_sha256"]:
        raise C6ControlHardStop(
            "c1_control_source_sha_mismatch",
            f"{case_id} C1 对照请求正文 SHA 漂移",
        )


def _transport_only_request(
    case_id: str,
    *,
    lock_sha256: str,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    source_path = _source_request_path(case_id)
    source_raw = source_path.read_bytes()
    source = json.loads(source_raw)
    if not isinstance(source, Mapping):
        raise C6ControlHardStop(
            "c1_control_non_object",
            f"{case_id} C1 对照请求不是对象",
        )
    _assert_control_source(case_id, source, lock_sha256=lock_sha256)

    needle = b'"max_tokens": 16000'
    replacement = b'"max_tokens": 65536'
    if source_raw.count(needle) != 1 or replacement in source_raw:
        raise C6ControlHardStop(
            "c1_control_max_tokens_text_drift",
            f"{case_id} C1 请求不能做唯一运输字段替换",
        )
    prepared_raw = source_raw.replace(needle, replacement, 1)
    prepared = json.loads(prepared_raw)
    source_body = source["body"]
    prepared_body = prepared["body"]
    messages_equal = json.dumps(
        source_body["messages"],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8") == json.dumps(
        prepared_body["messages"],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    shell_equal = {
        key: value for key, value in source.items() if key != "body"
    } == {
        key: value for key, value in prepared.items() if key != "body"
    }
    body_except_max_equal = {
        key: value for key, value in source_body.items() if key != "max_tokens"
    } == {
        key: value
        for key, value in prepared_body.items()
        if key != "max_tokens"
    }
    if (
        not messages_equal
        or not shell_equal
        or not body_except_max_equal
        or source_body.get("max_tokens") != SOURCE_MAX_TOKENS
        or prepared_body.get("max_tokens") != C6_MAX_TOKENS
        or source_raw.replace(needle, replacement, 1) != prepared_raw
    ):
        raise C6ControlHardStop(
            "c6_delta_not_transport_only",
            f"{case_id} C6 请求相对 C1 不只 max_tokens 一处差异",
        )
    delta = {
        "schema_version": "v02-c6-control-request-delta.v1",
        "status": "PASS_ONLY_MAX_TOKENS_CHANGED",
        "case_id": case_id,
        "source_path": display_path(source_path),
        "source_file_sha256": sha256_file(source_path),
        "source_request_identity_sha256": canonical_sha(source),
        "prepared_file_sha256": model_benchmark.sha256_bytes(prepared_raw),
        "prepared_request_identity_sha256": canonical_sha(prepared),
        "messages_byte_equivalent": messages_equal,
        "request_shell_equal": shell_equal,
        "body_except_max_tokens_equal": body_except_max_equal,
        "from_max_tokens": SOURCE_MAX_TOKENS,
        "to_max_tokens": C6_MAX_TOKENS,
        "changed_request_fields": ["body.max_tokens"],
        "model_visible_messages_changed": False,
    }
    return prepared_raw, prepared, delta


def _prepared_artifacts(run_dir: Path) -> dict[str, bytes]:
    _assert_exact_run_dir(run_dir)
    live._load_provider()
    rows = _control_lock_rows()
    artifacts: dict[str, bytes] = {}
    lock_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["case_id"])
        raw, request, delta = _transport_only_request(
            case_id,
            lock_sha256=str(row["sha256"]),
        )
        catalog_path = _source_catalog_path(case_id)
        body_raw = json_bytes(request["body"])
        artifacts[f"prepared/main/{case_id}/request_artifact.json"] = raw
        artifacts[f"prepared/main/{case_id}/request_body.json"] = body_raw
        artifacts[f"prepared/catalogs/{case_id}.json"] = catalog_path.read_bytes()
        artifacts[f"prepared/deltas/{case_id}.json"] = json_bytes(delta)
        delta_rows.append(delta)
        lock_rows.append(
            {
                "case_id": case_id,
                "chapter": live._case(case_id).unit,
                "source_request_identity_sha256": row["sha256"],
                "prepared_request_file_sha256": model_benchmark.sha256_bytes(raw),
                "prepared_request_identity_sha256": canonical_sha(request),
                "wire_body_sha256": model_benchmark.sha256_bytes(
                    json.dumps(request["body"], ensure_ascii=False).encode("utf-8")
                ),
                "max_attempts": 1,
                "retry_allowed": False,
            }
        )

    artifacts["prepared/C6_request_lock.json"] = json_bytes(
        {
            "schema_version": "v02-c6-control-request-lock.v1",
            "status": "FROZEN_NOT_SENT",
            "run_id": run_dir.name,
            "provider": live.PINNED_PROVIDER,
            "model": live.PINNED_MODEL,
            "api_key_env": live.PINNED_KEY_ENV,
            "case_order": list(CASE_ORDER),
            "requests": lock_rows,
            "single_variable": "body.max_tokens",
            "from_max_tokens": SOURCE_MAX_TOKENS,
            "to_max_tokens": C6_MAX_TOKENS,
            "calls_per_case": 1,
            "retry_allowed": False,
            "chapter_swap_allowed": False,
            "result_selection_allowed": False,
            "candidate_only": True,
            "deepseek_official_api_used": False,
        }
    )
    artifacts["prepared/C6_request_delta_ledger.json"] = json_bytes(
        {
            "schema_version": "v02-c6-control-request-delta-ledger.v1",
            "status": "PASS_ONLY_MAX_TOKENS_CHANGED",
            "rows": delta_rows,
            "messages_changed": False,
            "other_shell_fields_changed": False,
            "changed_request_fields": ["body.max_tokens"],
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    artifacts["prepared/C6_ownership_ticket.json"] = json_bytes(
        {
            "schema_version": "v02-c6-control-ownership-ticket.v1",
            "ownership": "V02_NEW_ZONE",
            "read_surfaces": [
                "C1_LOCKED_CONTROL_REQUESTS_READ_ONLY",
                "C1_FROZEN_CATALOGS_READ_ONLY",
            ],
            "write_surfaces": ["C6_R05_NEW_RUN_ONLY"],
            "legacy_write_required": False,
            "current_chain_write": False,
            "formal_gold_or_pointer_write": False,
        }
    )
    vector = {
        relative: model_benchmark.sha256_bytes(raw)
        for relative, raw in sorted(artifacts.items())
    }
    artifacts["prepared/C6_mechanical_verification.json"] = json_bytes(
        {
            "schema_version": "v02-c6-control-prepared-verification.v1",
            "status": "PASS_TWICE_IDENTICAL",
            "first_vector": vector,
            "second_vector": vector,
            "vectors_equal": True,
            "vector_sha256": canonical_sha(vector),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return artifacts


def prepare_run(run_dir: Path = C6_RUN_DIR) -> dict[str, Any]:
    _assert_exact_run_dir(run_dir)
    if run_dir.exists() and any(path.is_file() for path in run_dir.rglob("*")):
        raise C6ControlHardStop(
            "run_dir_not_empty",
            f"C6 对照臂目录已存在，拒绝覆盖：{run_dir}",
        )
    first = _prepared_artifacts(run_dir)
    second = _prepared_artifacts(run_dir)
    if first != second:
        raise C6ControlHardStop(
            "prepared_double_run_drift",
            "C6 零调用准备连续两次不一致",
        )
    for relative, raw in sorted(first.items()):
        live.write_bytes_exclusive(run_dir / relative, raw)
    return verify_prepared(run_dir)


def verify_prepared(run_dir: Path = C6_RUN_DIR) -> dict[str, Any]:
    expected = _prepared_artifacts(run_dir)
    for relative, raw in expected.items():
        path = run_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise C6ControlHardStop(
                "prepared_artifact_drift",
                f"C6 准备件漂移：{relative}",
            )
    scan = live.secret_scan(run_dir)
    if scan["authorization_header_hit_count"]:
        raise C6ControlHardStop(
            "authorization_trace_in_prepared",
            "C6 准备件出现鉴权字段",
        )
    return {
        "status": "PASS_C6_CONTROL_PREPARED",
        "run_id": run_dir.name,
        "case_order": list(CASE_ORDER),
        "request_count": 3,
        "single_variable": "body.max_tokens",
        "from_max_tokens": SOURCE_MAX_TOKENS,
        "to_max_tokens": C6_MAX_TOKENS,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _validate_usage(usage: Mapping[str, Any]) -> None:
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise C6ControlHardStop(
                "usage_contract",
                f"响应缺合法 {field}",
            )
    if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
        raise C6ControlHardStop(
            "usage_contract",
            "总 token 不能由输入与输出相加重建",
        )


def validate_z_event_payload(
    *,
    case_id: str,
    payload: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    case = live._case(case_id)
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        raise C6ControlHardStop(
            "catalog_entries_missing",
            f"{case_id} 冻结目录缺 entries",
        )
    reasons, audit = neutral_extract.audit_event_envelope(
        payload,
        case.unit,
        entries,
    )
    if reasons:
        missing_ids = audit.get("missing_catalog_anchor_ids") or []
        if missing_ids:
            raise C6ControlHardStop(
                "z_event_anchor_outside_catalog",
                f"{case_id} 含目录外锚 {missing_ids}",
            )
        raise C6ControlHardStop(
            "z_event_contract",
            f"{case_id} 未通过现役 z-event-v1 机械合同：{reasons}",
        )
    return {
        **audit,
        "status": "PASS_Z_EVENT_V1_MECHANICAL",
        "case_id": case_id,
        "anchor_count": audit["anchor_reference_count"],
        "outside_catalog_anchor_count": len(
            audit["missing_catalog_anchor_ids"]
        ),
        "events_without_anchor_count": audit["events_without_anchors"],
        "semantic_anchor_support_verified": False,
    }


def _response_and_mechanical(
    *,
    case_id: str,
    response: Mapping[str, Any],
    raw_path: Path,
    run_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        payload, content, reasoning, finish = model_benchmark.response_envelope(
            response,
            live.PINNED_MODEL,
            require_nonempty_reasoning=False,
        )
    except model_benchmark.BenchmarkHardStop as exc:
        raise C6ControlHardStop(exc.reason_code, str(exc)) from exc
    if response.get("model") != live.PINNED_MODEL:
        raise C6ControlHardStop(
            "response_model_mismatch",
            f"响应型号 {response.get('model')!r} 不是冻结型号 {live.PINNED_MODEL}",
        )
    catalog = read_json(run_dir / f"prepared/catalogs/{case_id}.json")
    validation = validate_z_event_payload(
        case_id=case_id,
        payload=payload,
        catalog=catalog,
    )
    mechanical = {
        "schema_version": "v02-c6-control-mechanical.v1",
        "status": "PASS",
        "case_id": case_id,
        "json_object_gate": True,
        "finish_reason": finish,
        "response_model": response.get("model"),
        "z_event_validation": validation,
        "semantic_score": "PENDING_OFFLINE_REVIEW",
        "content_sha256": model_benchmark.sha256_bytes(content.encode("utf-8")),
        "reasoning_sha256": model_benchmark.sha256_bytes(reasoning.encode("utf-8")),
        "raw_response_sha256": sha256_file(raw_path),
    }
    return payload, mechanical


def _attempt_rows(path: Path) -> list[dict[str, Any]]:
    return live._attempt_rows(path)


def _audit_attempt_reservations(
    sample_root: Path,
    *,
    attempts: Sequence[Mapping[str, Any]],
    request_sha: str,
    wire_sha: str,
) -> list[dict[str, Any]]:
    reservations = model_benchmark.load_attempt_rows(
        sample_root / "transport/attempt_reservations.jsonl"
    )
    if len(reservations) != len(attempts):
        raise C6ControlHardStop(
            "attempt_reservation_count_mismatch",
            "请求占位票与实发尝试数不一致",
        )
    for reservation, attempt in zip(reservations, attempts, strict=True):
        preimage = {
            key: value
            for key, value in reservation.items()
            if key != "row_sha256"
        }
        if (
            reservation.get("schema_version")
            != "model-benchmark-attempt-reservation-v1"
            or reservation.get("logical_request_id")
            != attempt.get("logical_request_id")
            or reservation.get("attempt") != attempt.get("attempt")
            or reservation.get("request_artifact_sha256") != request_sha
            or reservation.get("wire_body_sha256") != wire_sha
            or attempt.get("request_artifact_sha256") != request_sha
            or attempt.get("wire_body_sha256") != wire_sha
            or reservation.get("row_sha256") != canonical_sha(preimage)
        ):
            raise C6ControlHardStop(
                "attempt_reservation_rebuild_mismatch",
                "请求占位票不能与实发尝试逐行重建",
            )
    return reservations


def _write_checkpoint(
    sample_root: Path,
    *,
    request_artifact: Mapping[str, Any],
    response: Mapping[str, Any],
    mechanical: Mapping[str, Any],
    usage: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    reservations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    checkpoint_dir = sample_root / "checkpoint"
    if checkpoint_dir.exists() and any(checkpoint_dir.iterdir()):
        raise C6ControlHardStop(
            "checkpoint_not_empty",
            "C6 不可变检查点已有内容",
        )
    values = {
        "01_request.json": dict(request_artifact),
        "02_response.json": dict(response),
        "03_mechanical.json": dict(mechanical),
        "04_usage_attempts.json": {
            "schema_version": "v02-c6-control-usage-attempts.v1",
            "usage": dict(usage),
            "attempt_rows": [dict(row) for row in attempts],
            "attempt_reservations": [dict(row) for row in reservations],
        },
    }
    refs: dict[str, str] = {}
    for filename, value in values.items():
        raw = json_bytes(value)
        live.write_bytes_exclusive(checkpoint_dir / filename, raw)
        refs[filename] = model_benchmark.sha256_bytes(raw)
    preimage = {
        "schema_version": "v02-c6-control-checkpoint-seal.v1",
        "contract_version": CONTRACT_VERSION,
        "artifacts": refs,
        "sealed": True,
    }
    seal = {**preimage, "checkpoint_id": canonical_sha(preimage)}
    live.write_json_exclusive(checkpoint_dir / "05_seal.json", seal)
    return seal


def _execute_sample(
    run_dir: Path,
    *,
    case_id: str,
    key: str,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    case = live._case(case_id)
    sample_root = run_dir / f"samples/{PHASE}/{case_id}"
    completion_path = sample_root / "completion.json"
    if completion_path.is_file():
        return audit_sample(run_dir, case_id=case_id)
    if any(sample_root.rglob("call_attempts.jsonl")) or (
        sample_root.exists()
        and any(path.is_file() for path in sample_root.rglob("*"))
    ):
        raise C6ControlHardStop(
            "attempt_or_partial_sample_exists",
            f"{case_id} 已有尝试或不完整工件，禁止再次发网",
        )

    artifact_path = run_dir / f"prepared/main/{case_id}/request_artifact.json"
    body_path = run_dir / f"prepared/main/{case_id}/request_body.json"
    artifact = read_json(artifact_path)
    body = read_json(body_path)
    if artifact.get("arm") != "control" or body.get("max_tokens") != C6_MAX_TOKENS:
        raise C6ControlHardStop(
            "prepared_request_identity_drift",
            f"{case_id} 实发件不是 C6 对照请求",
        )
    request_copy = sample_root / "transport/request.json"
    live.write_bytes_exclusive(request_copy, artifact_path.read_bytes())
    request_sha = sha256_file(request_copy)
    wire = json.dumps(body, ensure_ascii=False).encode("utf-8")
    wire_sha = model_benchmark.sha256_bytes(wire)
    if key.encode("utf-8") in request_copy.read_bytes():
        raise C6ControlHardStop(
            "secret_in_request",
            "请求工件意外含 API Key",
        )

    logical_id = f"V02-C6-CONTROL-{case_id}"
    ledger = sample_root / "transport/call_attempts.jsonl"
    try:
        logical = z83_retry_transport.run_logical_request(
            logical_request_id=logical_id,
            chapter=case.unit,
            send_once=sender_factory(
                root=sample_root,
                provider=live._load_provider(),
                key=key,
                logical_request_id=logical_id,
                request_sha=request_sha,
                wire_body=wire,
                wire_sha=wire_sha,
                opener=opener,
            ),
            attempt_ledger_path=ledger,
            contract_version=CONTRACT_VERSION,
            state=z83_retry_transport.RetryRunState(),
            policy=live.no_retry_policy(),
            sleeper=lambda _seconds: None,
            jitter=lambda: 0.0,
        )
    except z83_retry_transport.RetryTransportHardStop as exc:
        raise C6ControlHardStop(exc.reason_code, str(exc)) from exc

    outcome = logical.outcome
    transport_payload = outcome.payload
    response = (
        transport_payload.get("response_json")
        if isinstance(transport_payload, Mapping)
        else None
    )
    raw_path = (
        transport_payload.get("raw_path")
        if isinstance(transport_payload, Mapping)
        else None
    )
    if (
        not isinstance(response, Mapping)
        or not isinstance(raw_path, Path)
        or transport_payload.get("envelope_error")
    ):
        raise C6ControlHardStop(
            "response_envelope",
            "HTTP 200 响应外壳不能解析",
        )
    usage = dict(outcome.usage or {})
    _validate_usage(usage)
    payload, mechanical = _response_and_mechanical(
        case_id=case_id,
        response=response,
        raw_path=raw_path,
        run_dir=run_dir,
    )
    live.write_json_exclusive(sample_root / "candidate/model_json.json", payload)
    live.write_json_exclusive(sample_root / "mechanical.json", mechanical)
    usage_record = {
        "schema_version": "v02-c6-control-usage.v1",
        "case_id": case_id,
        "logical_request_id": logical_id,
        "request_artifact_sha256": request_sha,
        "wire_body_sha256": wire_sha,
        "raw_response_sha256": sha256_file(raw_path),
        "usage": usage,
    }
    live.write_json_exclusive(sample_root / "transport/usage.json", usage_record)
    reservations = _audit_attempt_reservations(
        sample_root,
        attempts=logical.attempt_rows,
        request_sha=request_sha,
        wire_sha=wire_sha,
    )
    seal = _write_checkpoint(
        sample_root,
        request_artifact=artifact,
        response=response,
        mechanical=mechanical,
        usage=usage_record,
        attempts=logical.attempt_rows,
        reservations=reservations,
    )
    completion = {
        "schema_version": "v02-c6-control-sample-completion.v1",
        "status": "MECHANICAL_PASS_CANDIDATE_ONLY",
        "case_id": case_id,
        "chapter": case.unit,
        "provider": live.PINNED_PROVIDER,
        "model": live.PINNED_MODEL,
        "logical_samples": 1,
        "network_attempts": len(logical.attempt_rows),
        "usage": usage,
        "event_count": mechanical["z_event_validation"]["event_count"],
        "anchor_count": mechanical["z_event_validation"]["anchor_count"],
        "checkpoint_id": seal["checkpoint_id"],
        "semantic_score": "PENDING_OFFLINE_REVIEW",
        "candidate_only": True,
        "deepseek_official_api_used": False,
    }
    live.write_json_exclusive(completion_path, completion)
    return completion


def audit_sample(
    run_dir: Path = C6_RUN_DIR,
    *,
    case_id: str,
) -> dict[str, Any]:
    sample_root = run_dir / f"samples/{PHASE}/{case_id}"
    artifact_path = run_dir / f"prepared/main/{case_id}/request_artifact.json"
    request_copy = sample_root / "transport/request.json"
    if request_copy.read_bytes() != artifact_path.read_bytes():
        raise C6ControlHardStop(
            "sent_request_drift",
            f"{case_id} 实发请求与冻结件不一致",
        )
    artifact = read_json(artifact_path)
    if artifact.get("arm") != "control":
        raise C6ControlHardStop(
            "sent_arm_drift",
            f"{case_id} 实发件不是 control",
        )
    attempts = _attempt_rows(sample_root / "transport/call_attempts.jsonl")
    z83_retry_transport.validate_attempt_rows(attempts)
    if len(attempts) != 1 or attempts[0].get("http_status") != 200:
        raise C6ControlHardStop(
            "attempt_count_or_status",
            f"{case_id} 不是唯一一次 HTTP 200",
        )
    body = read_json(run_dir / f"prepared/main/{case_id}/request_body.json")
    wire_sha = model_benchmark.sha256_bytes(
        json.dumps(body, ensure_ascii=False).encode("utf-8")
    )
    reservations = _audit_attempt_reservations(
        sample_root,
        attempts=attempts,
        request_sha=sha256_file(request_copy),
        wire_sha=wire_sha,
    )
    raw_path = sample_root / "transport/raw_responses/attempt01.json"
    response = read_json(raw_path)
    payload, mechanical = _response_and_mechanical(
        case_id=case_id,
        response=response,
        raw_path=raw_path,
        run_dir=run_dir,
    )
    if read_json(sample_root / "candidate/model_json.json") != payload:
        raise C6ControlHardStop(
            "candidate_rebuild_mismatch",
            f"{case_id} 候选件不能从原始响应重建",
        )
    if read_json(sample_root / "mechanical.json") != mechanical:
        raise C6ControlHardStop(
            "mechanical_rebuild_mismatch",
            f"{case_id} 机械票不能从原始响应重建",
        )
    checkpoint_dir = sample_root / "checkpoint"
    seal = read_json(checkpoint_dir / "05_seal.json")
    refs = seal.get("artifacts")
    if (
        seal.get("schema_version") != "v02-c6-control-checkpoint-seal.v1"
        or seal.get("contract_version") != CONTRACT_VERSION
        or not isinstance(refs, Mapping)
        or set(refs)
        != {
            "01_request.json",
            "02_response.json",
            "03_mechanical.json",
            "04_usage_attempts.json",
        }
    ):
        raise C6ControlHardStop(
            "checkpoint_contract",
            f"{case_id} 检查点封签字段不合同",
        )
    for filename, expected_sha in refs.items():
        if sha256_file(checkpoint_dir / filename) != expected_sha:
            raise C6ControlHardStop(
                "checkpoint_sha_mismatch",
                f"{case_id} 检查点 {filename} 漂移",
            )
    preimage = {
        key: value for key, value in seal.items() if key != "checkpoint_id"
    }
    if seal.get("checkpoint_id") != canonical_sha(preimage):
        raise C6ControlHardStop(
            "checkpoint_id_mismatch",
            f"{case_id} 检查点 ID 不能重建",
        )
    if read_json(checkpoint_dir / "01_request.json") != artifact:
        raise C6ControlHardStop(
            "checkpoint_request_mismatch",
            f"{case_id} 检查点请求与冻结件不一致",
        )
    if read_json(checkpoint_dir / "02_response.json") != response:
        raise C6ControlHardStop(
            "checkpoint_response_mismatch",
            f"{case_id} 检查点响应与原始响应不一致",
        )
    if read_json(checkpoint_dir / "03_mechanical.json") != mechanical:
        raise C6ControlHardStop(
            "checkpoint_mechanical_mismatch",
            f"{case_id} 检查点机械票不一致",
        )
    usage_attempts = read_json(checkpoint_dir / "04_usage_attempts.json")
    usage_record = read_json(sample_root / "transport/usage.json")
    response_usage = response.get("usage")
    if (
        usage_attempts.get("attempt_rows") != attempts
        or usage_attempts.get("attempt_reservations") != reservations
        or usage_attempts.get("usage") != usage_record
        or usage_record.get("usage") != response_usage
        or attempts[0].get("usage") != response_usage
        or attempts[0].get("request_artifact_sha256")
        != sha256_file(request_copy)
        or attempts[0].get("wire_body_sha256")
        != wire_sha
    ):
        raise C6ControlHardStop(
            "checkpoint_usage_attempts_mismatch",
            f"{case_id} 检查点 usage／尝试账不能从原始工件重建",
        )
    completion = read_json(sample_root / "completion.json")
    if completion.get("checkpoint_id") != seal.get("checkpoint_id"):
        raise C6ControlHardStop(
            "completion_checkpoint_mismatch",
            f"{case_id} 完成票没有绑定检查点",
        )
    return completion


def _attempt_count(run_dir: Path) -> int:
    return sum(
        len(_attempt_rows(path))
        for path in run_dir.glob("samples/main/*/transport/call_attempts.jsonl")
    )


def _hard_stop(
    run_dir: Path,
    *,
    case_id: str | None,
    error: BaseException,
    key: str,
) -> dict[str, Any]:
    path = run_dir / "hard_stop.json"
    if path.is_file():
        return read_json(path)
    attempts = [
        row
        for ledger in run_dir.glob(
            "samples/main/*/transport/call_attempts.jsonl"
        )
        for row in _attempt_rows(ledger)
    ]
    attempted_case_ids = [
        case_id
        for case_id in CASE_ORDER
        if any(
            row.get("logical_request_id") == f"V02-C6-CONTROL-{case_id}"
            for row in attempts
        )
    ]
    ticket = {
        "schema_version": "v02-c6-control-hard-stop.v1",
        "status": "HARD_STOP_NO_PATCH_NO_RERUN",
        "case_id": case_id,
        "reason_code": getattr(error, "reason_code", "run_failure"),
        "error_type": type(error).__name__,
        "message": str(error),
        "logical_requests_started": len(
            {row.get("logical_request_id") for row in attempts}
        ),
        "network_attempts": len(attempts),
        "429_count": sum(row.get("http_status") == 429 for row in attempts),
        "attempted_case_ids": attempted_case_ids,
        "remaining_case_ids_not_sent": [
            case_id for case_id in CASE_ORDER if case_id not in attempted_case_ids
        ],
        "post_failure_requests_sent": False,
        "rerun_allowed": False,
        "chapter_swap_allowed": False,
        "deepseek_official_api_used": False,
        "automatic_fallback_used": False,
        "secret_scan": live.secret_scan(run_dir, (key,)),
        "stopped_at": live.now_iso(),
    }
    live.write_json_exclusive(path, ticket)
    return ticket


def run_control(
    run_dir: Path = C6_RUN_DIR,
    *,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    verify_prepared(run_dir)
    if (run_dir / "hard_stop.json").is_file():
        raise C6ControlHardStop(
            "run_already_hard_stopped",
            "C6 对照臂已硬停，禁止补发",
        )
    completion_path = run_dir / "completion/main.json"
    if completion_path.is_file():
        return audit_run(run_dir)
    if _attempt_count(run_dir):
        raise C6ControlHardStop(
            "attempt_without_run_completion",
            "C6 对照臂已有尝试但未收口，禁止再次发网",
        )
    claim_path = run_dir / "transport/C6_control_claim.json"
    if claim_path.is_file():
        raise C6ControlHardStop(
            "claim_without_completion",
            "C6 对照臂已有占用票但未收口，禁止再次发网",
        )
    key = os.environ.get(live.PINNED_KEY_ENV, "")
    if not key:
        raise C6ControlHardStop(
            "api_key_not_loaded",
            "缺 SENSENOVA_API_KEY，尚未发网",
        )
    pre_send_scan = live.secret_scan(run_dir, (key,))
    if (
        pre_send_scan["exact_key_hit_count"]
        or pre_send_scan["authorization_header_hit_count"]
    ):
        raise C6ControlHardStop(
            "secret_trace_detected_before_send",
            "C6 准备目录在发网前检出密钥或鉴权头",
        )
    live.write_json_exclusive(
        claim_path,
        {
            "schema_version": "v02-c6-control-run-claim.v1",
            "status": "THREE_CONTROL_SAMPLES_CLAIMED_NO_RERUN",
            "case_order": list(CASE_ORDER),
            "logical_request_ids": [
                f"V02-C6-CONTROL-{case_id}" for case_id in CASE_ORDER
            ],
            "max_attempts_per_case": 1,
            "retry_allowed": False,
            "chapter_swap_allowed": False,
            "claimed_at": live.now_iso(),
        },
    )

    current_case: str | None = None
    completions: list[dict[str, Any]] = []
    try:
        for current_case in CASE_ORDER:
            completions.append(
                _execute_sample(
                    run_dir,
                    case_id=current_case,
                    key=key,
                    opener=opener,
                    sender_factory=sender_factory,
                )
            )
        rebuilt = [
            audit_sample(run_dir, case_id=case_id) for case_id in CASE_ORDER
        ]
        if [row.get("case_id") for row in rebuilt] != list(CASE_ORDER):
            raise C6ControlHardStop(
                "audit_order_mismatch",
                "C6 三章样张不能按冻结顺序重建",
            )
        scan = live.secret_scan(run_dir, (key,))
        if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
            raise C6ControlHardStop(
                "secret_trace_detected",
                "C6 运行目录检出密钥或鉴权头",
            )
        usage_by_case = {
            row["case_id"]: row["usage"] for row in completions
        }
        result = {
            "schema_version": "v02-c6-control-run-completion.v1",
            "status": "CONTROL_THREE_CHAPTERS_MECHANICAL_PASS_PENDING_C6_MAPPING",
            "case_ids": list(CASE_ORDER),
            "logical_samples": 3,
            "network_attempts": _attempt_count(run_dir),
            "usage_by_case": usage_by_case,
            "total_tokens": sum(
                int(row["total_tokens"]) for row in usage_by_case.values()
            ),
            "event_count_by_case": {
                row["case_id"]: row["event_count"] for row in completions
            },
            "candidate_only": True,
            "quality_result_registered": False,
            "secret_scan": scan,
            "deepseek_official_api_used": False,
            "automatic_fallback_used": False,
            "completed_at": live.now_iso(),
        }
        live.write_json_exclusive(completion_path, result)
        return result
    except (
        C6ControlHardStop,
        model_benchmark.BenchmarkHardStop,
        ZBatchError,
    ) as exc:
        error = (
            exc
            if isinstance(exc, C6ControlHardStop)
            else C6ControlHardStop(
                getattr(exc, "reason_code", "run_failure"),
                str(exc),
            )
        )
        _hard_stop(
            run_dir,
            case_id=current_case,
            error=error,
            key=key,
        )
        raise C6ControlHardStop(error.reason_code, str(error)) from exc


def audit_run(run_dir: Path = C6_RUN_DIR) -> dict[str, Any]:
    verify_prepared(run_dir)
    completion_path = run_dir / "completion/main.json"
    completion = read_json(completion_path)
    rebuilt = [
        audit_sample(run_dir, case_id=case_id) for case_id in CASE_ORDER
    ]
    if (
        completion.get("case_ids") != list(CASE_ORDER)
        or completion.get("logical_samples") != 3
        or completion.get("network_attempts") != 3
        or [row.get("case_id") for row in rebuilt] != list(CASE_ORDER)
    ):
        raise C6ControlHardStop(
            "run_completion_drift",
            "C6 完成票不能由三章检查点重建",
        )
    return completion


def status(run_dir: Path = C6_RUN_DIR) -> dict[str, Any]:
    return {
        "run_id": run_dir.name,
        "prepared": (run_dir / "prepared/C6_request_lock.json").is_file(),
        "attempts": _attempt_count(run_dir),
        "completed": (run_dir / "completion/main.json").is_file(),
        "hard_stopped": (run_dir / "hard_stop.json").is_file(),
        "attempts_by_case": {
            case_id: len(
                _attempt_rows(
                    run_dir
                    / f"samples/main/{case_id}/transport/call_attempts.jsonl"
                )
            )
            for case_id in CASE_ORDER
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "verify", "run", "audit", "status"):
        item = sub.add_parser(command)
        item.add_argument("--run-dir", type=Path, default=C6_RUN_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = args.run_dir.resolve()
    if args.command == "prepare":
        result = prepare_run(run_dir)
    elif args.command == "verify":
        result = verify_prepared(run_dir)
    elif args.command == "run":
        result = run_control(run_dir)
    elif args.command == "audit":
        result = audit_run(run_dir)
    else:
        result = status(run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
