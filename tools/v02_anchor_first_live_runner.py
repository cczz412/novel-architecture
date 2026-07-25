#!/usr/bin/env python3
"""抽取工序重设计 v0.2：实验 A 锚先行倒装正式执行器。

本工具只发送 C1 已冻结的三份 ``anchor_first`` 请求：

- V4 Flash 固定走 SenseNova；
- 三份 control 请求只登记 ``FROZEN_NOT_SENT``，绝不进入发送队列；
- 主测每章一次，主测收口后才允许同输入再做一次稳定性复测；
- 任一运输、响应、结构或闭集锚机械失败都硬停，不自动重试、不补跑。

正式金标与离线判分材料不进入任何模型请求。本工具也不会签发裁判绿票。
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import v02_anchor_first_experiment as prep
from pipeline_common import model_benchmark
from zbatch_modules import z83_retry_transport
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
SUPPLY_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "C_anchor_first_experiment"
)
DEFAULT_RUN_DIR = ROOT / "runs/V02_实验A锚先行倒装_C2_r01_20260725"
PROVIDER_PATH = ROOT / "config/providers/sensenova_modular_v1.json"
ACCESS_POLICY_PATH = ROOT / "config/providers/provider_access_policy.json"

CONTRACT_VERSION = "v02-anchor-first-c2-live.v1"
PINNED_PROVIDER = "sensenova"
PINNED_MODEL = "deepseek-v4-flash"
PINNED_KEY_ENV = "SENSENOVA_API_KEY"
MAIN_PHASE = "main"
STABILITY_PHASE = "stability"
PHASES = (MAIN_PHASE, STABILITY_PHASE)
CASE_ORDER = tuple(case.case_id for case in prep.CASES)


class V02LiveHardStop(ZBatchError):
    """正式执行触发预写止损线。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return model_benchmark.sha256_bytes(canonical_bytes(value))


def sha256_file(path: Path) -> str:
    return model_benchmark.sha256_file(path)


def write_json_exclusive(path: Path, value: Any) -> None:
    model_benchmark.write_json_exclusive(path, value)


def write_bytes_exclusive(path: Path, raw: bytes) -> None:
    model_benchmark.write_bytes_exclusive(path, raw)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _case(case_id: str) -> prep.CaseSpec:
    case = prep.CASE_BY_ID.get(case_id)
    if case is None:
        raise ZBatchError(f"未知实验章：{case_id}")
    return case


def _load_provider() -> dict[str, Any]:
    provider = read_json(PROVIDER_PATH)
    expected = {
        "provider": PINNED_PROVIDER,
        "base_url": "https://token.sensenova.cn/v1",
        "endpoint": "/chat/completions",
        "model": PINNED_MODEL,
        "api_key_env": PINNED_KEY_ENV,
    }
    for field, value in expected.items():
        if provider.get(field) != value:
            raise ZBatchError(f"SenseNova 配置 {field} 漂移")
    if provider.get("allowed_models") != [PINNED_MODEL]:
        raise ZBatchError("SenseNova 本轮准入型号不是唯一 V4 Flash")

    policy = read_json(ACCESS_POLICY_PATH)
    official = policy.get("providers", {}).get("deepseek_official", {})
    if official.get("default_action") != "deny" or "permanently_disabled" not in str(
        official.get("status")
    ):
        raise ZBatchError("DeepSeek 官方 API 永久禁用策略漂移")
    return provider


def _source_request(case_id: str, supply_dir: Path = SUPPLY_DIR) -> Path:
    return supply_dir / f"requests/anchor_first/{case_id}.json"


def _source_catalog(case_id: str, supply_dir: Path = SUPPLY_DIR) -> Path:
    return supply_dir / f"catalogs/{case_id}.json"


def _supply_prompt_variant(supply_dir: Path) -> str:
    config = read_json(supply_dir / "config.json")
    variant = config.get("prompt_variant", prep.PROMPT_VARIANT_C1)
    if variant not in prep.PROMPT_VARIANTS:
        raise ZBatchError(f"供料题面版本未知：{variant}")
    return str(variant)


def _supply_max_tokens_override(supply_dir: Path) -> int | None:
    config = read_json(supply_dir / "config.json")
    value = config.get("max_tokens_override")
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value != prep.SENSENOVA_DOCUMENTED_MAX_TOKENS
    ):
        raise ZBatchError("供料运输上限不是获批的 65536")
    return value


def _load_request_lock(supply_dir: Path = SUPPLY_DIR) -> dict[str, Any]:
    lock = read_json(supply_dir / "request_lock.json")
    if lock.get("schema_version") != "v02-anchor-first-request-lock.v1":
        raise ZBatchError("C1 请求锁版本漂移")
    treatment_rows = lock.get("anchor_first_requests")
    control_rows = lock.get("control_requests")
    if not isinstance(treatment_rows, list) or not isinstance(control_rows, list):
        raise ZBatchError("C1 请求锁缺两臂清单")
    if [row.get("case_id") for row in treatment_rows] != list(CASE_ORDER):
        raise ZBatchError("C1 锚先行请求顺序漂移")
    if [row.get("case_id") for row in control_rows] != list(CASE_ORDER):
        raise ZBatchError("C1 对照请求顺序漂移")

    for arm, rows in (("anchor_first", treatment_rows), ("control", control_rows)):
        for row in rows:
            case_id = str(row["case_id"])
            path = supply_dir / str(row["path"])
            request = read_json(path)
            if not path.is_file() or prep.canonical_sha(request) != row.get("sha256"):
                raise ZBatchError(f"供料 {arm} 请求缺失或 SHA 漂移：{case_id}")
    return lock


def _assert_treatment_request(
    case_id: str,
    request: Mapping[str, Any],
    *,
    expected_max_tokens: int = 16000,
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
        raise ZBatchError(f"{case_id} 请求外壳字段漂移")
    expected_identity = {
        "schema_version": "v02-prepared-request.v1",
        "case_id": case_id,
        "provider": PINNED_PROVIDER,
        "api_base_url": "https://token.sensenova.cn/v1",
        "api_endpoint": "/chat/completions",
        "model": PINNED_MODEL,
        "_security": "no_api_key_no_authorization",
        "arm": "anchor_first",
    }
    for field, expected in expected_identity.items():
        if request.get(field) != expected:
            raise ZBatchError(f"{case_id} 请求 {field} 漂移")
    body = request.get("body")
    if not isinstance(body, Mapping):
        raise ZBatchError(f"{case_id} 请求缺 body")
    expected_sampling = {
        "model": PINNED_MODEL,
        "temperature": 0.2,
        "max_tokens": expected_max_tokens,
        "n": 1,
        "reasoning_effort": "medium",
        "response_format": {"type": "json_object"},
    }
    for field, expected in expected_sampling.items():
        if body.get(field) != expected:
            raise ZBatchError(f"{case_id} 请求参数 {field} 漂移")
    if set(body) != {"model", "messages", *expected_sampling.keys() - {"model"}}:
        raise ZBatchError(f"{case_id} 请求 body 字段集合漂移")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ZBatchError(f"{case_id} 请求消息为空")


def _prepared_payloads(
    run_dir: Path,
    supply_dir: Path = SUPPLY_DIR,
) -> dict[str, bytes]:
    supply_dir = supply_dir.resolve()
    prompt_variant = _supply_prompt_variant(supply_dir)
    max_tokens_override = _supply_max_tokens_override(supply_dir)
    existing_preflight_path = run_dir / "prepared/preflight.json"
    legacy_prepared_metadata = False
    if existing_preflight_path.is_file():
        existing_preflight = read_json(existing_preflight_path)
        legacy_prepared_metadata = "supply_dir" not in existing_preflight
    stored_c0 = read_json(supply_dir / "c0_check.json")
    key_was_present = (
        stored_c0.get("checks", {}).get("api_key_environment_name_present") is True
    )
    rebuild_environment = (
        {PINNED_KEY_ENV: "PRESENCE_ONLY_REBUILD_SENTINEL"}
        if key_was_present
        else {}
    )
    verification = prep.verify_artifacts(
        supply_dir,
        prep.build_artifacts(
            selection_k=prep.K_MISSING,
            environ=rebuild_environment,
            prompt_variant=prompt_variant,
            max_tokens_override=max_tokens_override,
        ),
    )
    if verification.get("status") != "pass":
        raise ZBatchError("供料零调用工件不能从真源重建")
    provider = _load_provider()
    lock = _load_request_lock(supply_dir)
    payloads: dict[str, bytes] = {}
    sample_rows: list[dict[str, Any]] = []

    for case_id in CASE_ORDER:
        request_path = _source_request(case_id, supply_dir)
        request = read_json(request_path)
        if not isinstance(request, Mapping):
            raise ZBatchError(f"{case_id} 请求不是对象")
        _assert_treatment_request(
            case_id,
            request,
            expected_max_tokens=max_tokens_override or 16000,
        )
        catalog_path = _source_catalog(case_id, supply_dir)
        catalog = read_json(catalog_path)
        case_source = prep.load_case_source(_case(case_id))
        if request.get("source_body_sha256") != case_source["body_sha256"]:
            raise ZBatchError(f"{case_id} 正文 SHA 与冻结请求不一致")
        if request.get("catalog_sha256") != prep.canonical_sha(catalog):
            raise ZBatchError(f"{case_id} 目录 SHA 与冻结请求不一致")

        payloads[f"prepared/main/{case_id}/request_artifact.json"] = (
            request_path.read_bytes()
        )
        payloads[f"prepared/main/{case_id}/request_body.json"] = json_bytes(
            request["body"]
        )
        payloads[f"prepared/catalogs/{case_id}.json"] = catalog_path.read_bytes()
        sample_rows.append(
            {
                "case_id": case_id,
                "chapter": _case(case_id).unit,
                "provider": PINNED_PROVIDER,
                "model": PINNED_MODEL,
                "request_artifact_sha256": sha256_file(request_path),
                "request_identity_sha256": prep.canonical_sha(request),
                "wire_body_sha256": model_benchmark.sha256_bytes(
                    json.dumps(request["body"], ensure_ascii=False).encode("utf-8")
                ),
            }
        )

    control_rows = [
        {
            "case_id": row["case_id"],
            "source_path": display_path(supply_dir / str(row["path"])),
            "request_identity_sha256": row["sha256"],
            "execution_status": "FROZEN_NOT_SENT",
            "reason": "C2 authority sends only three anchor_first requests",
        }
        for row in lock["control_requests"]
    ]
    payloads["prepared/control_not_sent.json"] = json_bytes(
        {
            "schema_version": "v02-anchor-first-control-not-sent.v1",
            "status": "FROZEN_NOT_SENT",
            "control_request_count": 3,
            "model_api_calls": 0,
            "requests": control_rows,
        }
    )
    payloads["prepared/provider_route.json"] = json_bytes(
        {
            "schema_version": "v02-anchor-first-provider-route.v1",
            "current_experiment_model": "V4 Flash",
            "provider": PINNED_PROVIDER,
            "model": PINNED_MODEL,
            "api_key_env": PINNED_KEY_ENV,
            "provider_config_path": display_path(PROVIDER_PATH),
            "provider_config_sha256": sha256_file(PROVIDER_PATH),
            "deepseek_official_api_used": False,
            "tencent_v4_pro_used": False,
            "future_v4_pro_route_if_explicitly_required": "tencent_tokenhub",
            "automatic_fallback": False,
        }
    )
    run_plan = {
        "schema_version": "v02-anchor-first-c2-run-plan.v1",
        "run_id": run_dir.name,
        "status": "prepared_zero_call",
        "main_calls": 3,
        "stability_calls_after_main_closure": 3,
        "other_calls": 0,
        "main_order": list(CASE_ORDER),
        "stability_order": list(CASE_ORDER),
        "samples": sample_rows,
        "control_requests": "FROZEN_NOT_SENT",
        "single_variable": (
            "transport_max_tokens_only"
            if max_tokens_override is not None
            else "closed_anchor_alignment_contract"
        ),
        **(
            {}
            if legacy_prepared_metadata
            else {
                "supply_dir": display_path(supply_dir),
                "supply_prompt_variant": prompt_variant,
                **(
                    {"supply_max_tokens_override": max_tokens_override}
                    if max_tokens_override is not None
                    else {}
                ),
                "supply_artifact_manifest_sha256": sha256_file(
                    supply_dir / "artifact_manifest.json"
                ),
                "supply_request_lock_sha256": sha256_file(
                    supply_dir / "request_lock.json"
                ),
            }
        ),
        "single_sample_no_rerun": True,
        "stability_never_overwrites_main": True,
        "candidate_only": True,
        "judge_green_ticket_issued": False,
    }
    preflight = {
        "schema_version": "v02-anchor-first-c2-preflight.v1",
        "status": "pass_zero_call_prepared",
        "run_id": run_dir.name,
        "provider": provider["provider"],
        "model": provider["model"],
        "api_key_env": provider["api_key_env"],
        **(
            {}
            if legacy_prepared_metadata
            else {
                "supply_dir": display_path(supply_dir),
                "supply_prompt_variant": prompt_variant,
                **(
                    {"supply_max_tokens_override": max_tokens_override}
                    if max_tokens_override is not None
                    else {}
                ),
            }
        ),
        "request_count_main": 3,
        "request_count_stability": 3,
        "control_request_count_sent": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "deepseek_official_api_used": False,
        "automatic_fallback": False,
    }
    payloads["prepared/run_plan.json"] = json_bytes(run_plan)
    payloads["prepared/preflight.json"] = json_bytes(preflight)
    return payloads


def _prepared_twice(
    run_dir: Path,
    supply_dir: Path = SUPPLY_DIR,
) -> dict[str, bytes]:
    first = _prepared_payloads(run_dir, supply_dir)
    second = _prepared_payloads(run_dir, supply_dir)
    if first != second:
        raise ZBatchError("C2 零调用准备连续两次构造不一致")
    vector = {
        relative: model_benchmark.sha256_bytes(raw)
        for relative, raw in sorted(first.items())
    }
    result = dict(first)
    result["prepared/mechanical_verification.json"] = json_bytes(
        {
            "schema_version": "v02-anchor-first-c2-prepared-verification.v1",
            "status": "pass_twice_identical",
            "first_vector": vector,
            "second_vector": vector,
            "vectors_equal": True,
            "vector_sha256": canonical_sha(vector),
            "model_api_calls": 0,
            "network_requests": 0,
        }
    )
    return result


def prepare_run(
    run_dir: Path,
    supply_dir: Path = SUPPLY_DIR,
) -> dict[str, Any]:
    if run_dir.exists() and any(path.is_file() for path in run_dir.rglob("*")):
        raise ZBatchError(f"C2 运行目录已存在，拒绝覆盖：{run_dir}")
    payloads = _prepared_twice(run_dir, supply_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(payloads.items()):
        write_bytes_exclusive(run_dir / relative, raw)
    verify_prepared(run_dir, supply_dir)
    return read_json(run_dir / "prepared/preflight.json")


def verify_prepared(
    run_dir: Path,
    supply_dir: Path = SUPPLY_DIR,
) -> dict[str, Any]:
    expected = _prepared_twice(run_dir, supply_dir)
    for relative, raw in expected.items():
        path = run_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise ZBatchError(f"C2 准备件漂移：{relative}")
    scan = secret_scan(run_dir)
    if scan["authorization_header_hit_count"]:
        raise ZBatchError("C2 准备件出现 Authorization 字段")
    return read_json(run_dir / "prepared/preflight.json")


def secret_scan(run_dir: Path, keys: Sequence[str] = ()) -> dict[str, Any]:
    key_bytes = {key.encode("utf-8") for key in keys if key}
    exact_hits: list[str] = []
    authorization_hits: list[str] = []

    def contains_authorization(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(
                str(name).lower() == "authorization" or contains_authorization(child)
                for name, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_authorization(child) for child in value)
        return False

    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        relative = path.relative_to(run_dir).as_posix()
        if any(key in raw for key in key_bytes):
            exact_hits.append(relative)
        if path.suffix not in {".json", ".jsonl"}:
            continue
        try:
            values = (
                [
                    json.loads(line)
                    for line in raw.decode("utf-8").splitlines()
                    if line.strip()
                ]
                if path.suffix == ".jsonl"
                else [json.loads(raw.decode("utf-8"))]
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if any(contains_authorization(value) for value in values):
            authorization_hits.append(relative)
    return {
        "exact_key_hits": exact_hits,
        "exact_key_hit_count": len(exact_hits),
        "authorization_header_hits": authorization_hits,
        "authorization_header_hit_count": len(authorization_hits),
    }


def no_retry_policy() -> z83_retry_transport.RetryPolicy:
    return z83_retry_transport.RetryPolicy(
        same_chapter_gap_seconds=0.0,
        cross_chapter_gap_seconds=0.0,
        retry_delays_seconds=(),
        max_429_retries_per_request=0,
        max_429_per_run=1,
    )


def _attempt_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _validate_usage(usage: Mapping[str, Any]) -> None:
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise V02LiveHardStop("usage_contract", f"响应缺合法 {field}")
    if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
        raise V02LiveHardStop("usage_contract", "总 token 不能由输入与输出相加重建")


def _checkpoint(
    sample_root: Path,
    *,
    request_artifact: Mapping[str, Any],
    response: Mapping[str, Any],
    usage: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    mechanical: Mapping[str, Any],
) -> dict[str, Any]:
    root = sample_root / "checkpoint"
    if root.exists() and any(root.iterdir()):
        raise ZBatchError("不可变检查点已有内容，拒绝覆盖")
    values = {
        "01_request.json": dict(request_artifact),
        "02_response.json": dict(response),
        "03_usage.json": dict(usage),
        "04_attempts.json": {
            "schema_version": "v02-anchor-first-attempt-set.v1",
            "rows": [dict(row) for row in attempts],
        },
    }
    refs: dict[str, str] = {}
    for filename, value in values.items():
        raw = json_bytes(value)
        write_bytes_exclusive(root / filename, raw)
        refs[filename] = model_benchmark.sha256_bytes(raw)
    preimage = {
        "schema_version": "v02-anchor-first-checkpoint-seal.v1",
        "contract_version": CONTRACT_VERSION,
        "artifacts": refs,
        "mechanical_path": "../mechanical.json",
        "mechanical_sha256": sha256_file(sample_root / "mechanical.json"),
        "sealed": True,
    }
    seal = {**preimage, "checkpoint_id": canonical_sha(preimage)}
    write_json_exclusive(root / "05_seal.json", seal)
    return seal


def _hard_stop_path(run_dir: Path) -> Path:
    return run_dir / "hard_stop.json"


def _write_hard_stop(
    run_dir: Path,
    *,
    phase: str,
    case_id: str | None,
    error: BaseException,
    scan: Mapping[str, Any],
) -> dict[str, Any]:
    path = _hard_stop_path(run_dir)
    if path.is_file():
        return read_json(path)
    attempts = [
        row
        for ledger in run_dir.glob("samples/*/*/transport/call_attempts.jsonl")
        for row in _attempt_rows(ledger)
    ]
    ticket = {
        "schema_version": "v02-anchor-first-c2-hard-stop.v1",
        "status": "hard_stop_no_patch_no_rerun",
        "phase": phase,
        "case_id": case_id,
        "reason_code": getattr(error, "reason_code", "run_failure"),
        "error_type": type(error).__name__,
        "message": str(error),
        "logical_requests_started": len(
            {row.get("logical_request_id") for row in attempts}
        ),
        "network_attempts": len(attempts),
        "429_count": sum(row.get("http_status") == 429 for row in attempts),
        "rerun_allowed": False,
        "deepseek_official_api_used": False,
        "automatic_fallback_used": False,
        "secret_scan": dict(scan),
        "stopped_at": now_iso(),
    }
    write_json_exclusive(path, ticket)
    return ticket


def _response_and_mechanical(
    *,
    case_id: str,
    response: Mapping[str, Any],
    raw_path: Path,
    supply_dir: Path = SUPPLY_DIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, content, reasoning, finish = model_benchmark.response_envelope(
        response,
        PINNED_MODEL,
        require_nonempty_reasoning=False,
    )
    if response.get("model") != PINNED_MODEL:
        raise V02LiveHardStop(
            "response_model_mismatch",
            f"响应型号 {response.get('model')!r} 不是冻结型号 {PINNED_MODEL}",
        )
    catalog = read_json(_source_catalog(case_id, supply_dir))
    source = prep.load_case_source(_case(case_id))
    validation = prep.validate_closed_anchor_alignment(
        payload,
        catalog=catalog,
        source_text=str(source["body"]),
    )
    if validation.get("status") != "pass":
        raise V02LiveHardStop(
            "closed_anchor_mechanical_contract",
            f"{case_id} 闭集锚机械闸失败：{validation.get('errors')}",
        )
    mechanical = {
        "schema_version": "v02-anchor-first-c2-mechanical.v1",
        "status": "pass",
        "case_id": case_id,
        "json_object_gate": True,
        "finish_reason": finish,
        "response_model": response.get("model"),
        "event_count": len(payload.get("events", [])),
        "closed_anchor_validation": validation,
        "semantic_support_verified": False,
        "content_sha256": model_benchmark.sha256_bytes(content.encode("utf-8")),
        "reasoning_sha256": model_benchmark.sha256_bytes(reasoning.encode("utf-8")),
        "raw_response_sha256": sha256_file(raw_path),
    }
    return payload, mechanical


def _execute_sample(
    run_dir: Path,
    *,
    phase: str,
    case_id: str,
    key: str,
    supply_dir: Path = SUPPLY_DIR,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
    logical_prefix: str = "V02-C2",
) -> dict[str, Any]:
    case = _case(case_id)
    sample_root = run_dir / f"samples/{phase}/{case_id}"
    completion_path = sample_root / "completion.json"
    if completion_path.is_file():
        return audit_sample(
            run_dir,
            phase=phase,
            case_id=case_id,
            supply_dir=supply_dir,
        )
    if any(sample_root.rglob("call_attempts.jsonl")):
        raise V02LiveHardStop(
            "attempt_without_completion",
            f"{phase}/{case_id} 已有尝试但没有完成票，禁止再次发网",
        )
    if sample_root.exists() and any(path.is_file() for path in sample_root.rglob("*")):
        raise V02LiveHardStop(
            "partial_sample_artifacts",
            f"{phase}/{case_id} 已有不完整工件，禁止覆盖",
        )

    artifact_path = run_dir / f"prepared/main/{case_id}/request_artifact.json"
    body_path = run_dir / f"prepared/main/{case_id}/request_body.json"
    artifact = read_json(artifact_path)
    body = read_json(body_path)
    request_copy = sample_root / "transport/request.json"
    write_bytes_exclusive(request_copy, artifact_path.read_bytes())
    request_sha = sha256_file(request_copy)
    wire = json.dumps(body, ensure_ascii=False).encode("utf-8")
    wire_sha = model_benchmark.sha256_bytes(wire)
    if key.encode("utf-8") in request_copy.read_bytes():
        raise V02LiveHardStop("secret_in_request", "请求工件意外含 API Key")
    logical_id = f"{logical_prefix}-{phase.upper()}-{case_id}"
    provider = _load_provider()
    state = z83_retry_transport.RetryRunState()
    ledger = sample_root / "transport/call_attempts.jsonl"
    try:
        logical = z83_retry_transport.run_logical_request(
            logical_request_id=logical_id,
            chapter=case.unit,
            send_once=sender_factory(
                root=sample_root,
                provider=provider,
                key=key,
                logical_request_id=logical_id,
                request_sha=request_sha,
                wire_body=wire,
                wire_sha=wire_sha,
                opener=opener,
            ),
            attempt_ledger_path=ledger,
            contract_version=CONTRACT_VERSION,
            state=state,
            policy=no_retry_policy(),
            sleeper=lambda _seconds: None,
            jitter=lambda: 0.0,
        )
    except z83_retry_transport.RetryTransportHardStop as exc:
        raise V02LiveHardStop(exc.reason_code, str(exc)) from exc

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
        raise V02LiveHardStop("response_envelope", "HTTP 200 响应外壳不能解析")
    usage = dict(outcome.usage or {})
    _validate_usage(usage)
    payload, mechanical = _response_and_mechanical(
        case_id=case_id,
        response=response,
        raw_path=raw_path,
        supply_dir=supply_dir,
    )
    write_json_exclusive(sample_root / "candidate/model_json.json", payload)
    write_json_exclusive(sample_root / "mechanical.json", mechanical)
    usage_record = {
        "schema_version": "v02-anchor-first-c2-usage.v1",
        "phase": phase,
        "case_id": case_id,
        "logical_request_id": logical_id,
        "request_artifact_sha256": request_sha,
        "raw_response_sha256": sha256_file(raw_path),
        "usage": usage,
    }
    write_json_exclusive(sample_root / "transport/usage.json", usage_record)
    seal = _checkpoint(
        sample_root,
        request_artifact=artifact,
        response=response,
        usage=usage_record,
        attempts=logical.attempt_rows,
        mechanical=mechanical,
    )
    completion = {
        "schema_version": "v02-anchor-first-c2-sample-completion.v1",
        "status": "mechanical_pass_candidate_only",
        "phase": phase,
        "case_id": case_id,
        "chapter": case.unit,
        "provider": PINNED_PROVIDER,
        "model": PINNED_MODEL,
        "logical_samples": 1,
        "network_attempts": len(logical.attempt_rows),
        "usage": usage,
        "event_count": mechanical["event_count"],
        "checkpoint_id": seal["checkpoint_id"],
        "semantic_score": "pending_offline_review",
        "deepseek_official_api_used": False,
    }
    write_json_exclusive(completion_path, completion)
    return completion


def audit_sample(
    run_dir: Path,
    *,
    phase: str,
    case_id: str,
    supply_dir: Path = SUPPLY_DIR,
) -> dict[str, Any]:
    sample_root = run_dir / f"samples/{phase}/{case_id}"
    completion = read_json(sample_root / "completion.json")
    artifact = read_json(run_dir / f"prepared/main/{case_id}/request_artifact.json")
    request_copy = sample_root / "transport/request.json"
    if request_copy.read_bytes() != (
        run_dir / f"prepared/main/{case_id}/request_artifact.json"
    ).read_bytes():
        raise ZBatchError(f"{phase}/{case_id} 实发请求与冻结件不一致")
    attempts = _attempt_rows(sample_root / "transport/call_attempts.jsonl")
    z83_retry_transport.validate_attempt_rows(attempts)
    if len(attempts) != 1 or attempts[0].get("http_status") != 200:
        raise ZBatchError(f"{phase}/{case_id} 不是唯一一次 HTTP 200")
    raw_path = sample_root / "transport/raw_responses/attempt01.json"
    response = read_json(raw_path)
    payload, mechanical = _response_and_mechanical(
        case_id=case_id,
        response=response,
        raw_path=raw_path,
        supply_dir=supply_dir,
    )
    if read_json(sample_root / "candidate/model_json.json") != payload:
        raise ZBatchError(f"{phase}/{case_id} 候选件不能从原始响应重建")
    if read_json(sample_root / "mechanical.json") != mechanical:
        raise ZBatchError(f"{phase}/{case_id} 机械票不能从原始响应重建")
    if completion.get("checkpoint_id") != read_json(
        sample_root / "checkpoint/05_seal.json"
    ).get("checkpoint_id"):
        raise ZBatchError(f"{phase}/{case_id} 完成票没有绑定检查点")
    if artifact.get("arm") != "anchor_first":
        raise ZBatchError(f"{phase}/{case_id} 意外使用 control 请求")
    return completion


def _claim(run_dir: Path, phase: str) -> dict[str, Any]:
    return {
        "schema_version": "v02-anchor-first-c2-phase-claim.v1",
        "phase": phase,
        "status": "three_samples_claimed_no_rerun",
        "run_id": run_dir.name,
        "case_order": list(CASE_ORDER),
        "logical_request_ids": [
            f"V02-C2-{phase.upper()}-{case_id}" for case_id in CASE_ORDER
        ],
        "sample_count": 3,
        "control_requests_sent": 0,
        "provider": PINNED_PROVIDER,
        "model": PINNED_MODEL,
        "claimed_at": now_iso(),
    }


def _phase_completion(
    run_dir: Path,
    phase: str,
    completions: Sequence[Mapping[str, Any]],
    scan: Mapping[str, Any],
) -> dict[str, Any]:
    usage = {
        row["case_id"]: row["usage"]
        for row in completions
        if isinstance(row.get("usage"), Mapping)
    }
    return {
        "schema_version": "v02-anchor-first-c2-phase-completion.v1",
        "status": "main_mechanical_pass_pending_offline_score"
        if phase == MAIN_PHASE
        else "stability_mechanical_pass_diagnostic_only",
        "phase": phase,
        "run_id": run_dir.name,
        "logical_samples": 3,
        "network_attempts": sum(int(row["network_attempts"]) for row in completions),
        "usage_by_case": usage,
        "total_tokens": sum(int(value["total_tokens"]) for value in usage.values()),
        "case_ids": list(CASE_ORDER),
        "control_requests_sent": 0,
        "secret_scan": dict(scan),
        "candidate_only": True,
        "deepseek_official_api_used": False,
        "automatic_fallback_used": False,
        "completed_at": now_iso(),
    }


def _verify_main_closure(
    run_dir: Path,
    supply_dir: Path = SUPPLY_DIR,
) -> dict[str, Any]:
    path = run_dir / "completion/main.json"
    if not path.is_file():
        raise ZBatchError("主测没有完整收口，禁止稳定性复测")
    try:
        ticket = read_json(path)
        if (
            ticket.get("phase") != MAIN_PHASE
            or ticket.get("logical_samples") != len(CASE_ORDER)
            or ticket.get("case_ids") != list(CASE_ORDER)
            or ticket.get("control_requests_sent") != 0
        ):
            raise ZBatchError("主测完成票字段不完整")
        rebuilt = [
            audit_sample(
                run_dir,
                phase=MAIN_PHASE,
                case_id=case_id,
                supply_dir=supply_dir,
            )
            for case_id in CASE_ORDER
        ]
        if [row.get("case_id") for row in rebuilt] != list(CASE_ORDER):
            raise ZBatchError("主测三章样张不能完整重建")
    except (OSError, KeyError, TypeError, ValueError, ZBatchError) as exc:
        raise ZBatchError(
            "主测没有完整收口，禁止稳定性复测"
        ) from exc
    return ticket


def _run_phase(
    run_dir: Path,
    phase: str,
    *,
    supply_dir: Path = SUPPLY_DIR,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    if phase not in PHASES:
        raise ZBatchError(f"未知阶段：{phase}")
    if _supply_max_tokens_override(supply_dir) is not None:
        raise ZBatchError(
            "C4 运输探针供料禁止走通用 run-main/run-stability；"
            "必须使用 v02_c4_transport_probe.py 的逐步闸"
        )
    verify_prepared(run_dir, supply_dir)
    if _hard_stop_path(run_dir).is_file():
        raise ZBatchError("本轮已硬停，禁止补发或捞回")
    if phase == STABILITY_PHASE:
        _verify_main_closure(run_dir, supply_dir)
    completion_path = run_dir / f"completion/{phase}.json"
    if completion_path.is_file():
        return read_json(completion_path)

    key = os.environ.get(PINNED_KEY_ENV, "")
    if not key:
        raise ZBatchError(f"缺少 {PINNED_KEY_ENV}；尚未占用任何模型请求")
    claim_path = run_dir / f"transport/{phase}_claim.json"
    if not claim_path.is_file():
        write_json_exclusive(claim_path, _claim(run_dir, phase))
    completions: list[dict[str, Any]] = []
    current_case: str | None = None
    try:
        for current_case in CASE_ORDER:
            completions.append(
                _execute_sample(
                    run_dir,
                    phase=phase,
                    case_id=current_case,
                    key=key,
                    supply_dir=supply_dir,
                    opener=opener,
                    sender_factory=sender_factory,
                )
            )
        scan = secret_scan(run_dir, (key,))
        if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
            raise V02LiveHardStop("secret_trace_detected", "运行目录检出密钥或鉴权头")
        result = _phase_completion(run_dir, phase, completions, scan)
        write_json_exclusive(completion_path, result)
        if phase == STABILITY_PHASE:
            write_json_exclusive(
                run_dir / "diagnostics/stability_disagreement.json",
                stability_disagreement(run_dir),
            )
        return result
    except (V02LiveHardStop, ZBatchError, model_benchmark.BenchmarkHardStop) as exc:
        error = (
            exc
            if isinstance(exc, V02LiveHardStop)
            else V02LiveHardStop(
                getattr(exc, "reason_code", "run_failure"),
                str(exc),
            )
        )
        scan = secret_scan(run_dir, (key,))
        _write_hard_stop(
            run_dir,
            phase=phase,
            case_id=current_case,
            error=error,
            scan=scan,
        )
        raise error from exc


def run_main(
    run_dir: Path,
    *,
    supply_dir: Path = SUPPLY_DIR,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    return _run_phase(
        run_dir,
        MAIN_PHASE,
        supply_dir=supply_dir,
        opener=opener,
        sender_factory=sender_factory,
    )


def run_stability(
    run_dir: Path,
    *,
    supply_dir: Path = SUPPLY_DIR,
    opener: Any = None,
    sender_factory: Callable[..., Any] = model_benchmark.send_once_factory,
) -> dict[str, Any]:
    return _run_phase(
        run_dir,
        STABILITY_PHASE,
        supply_dir=supply_dir,
        opener=opener,
        sender_factory=sender_factory,
    )


def _event_signature(event: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        event.get("event_id"),
        event.get("event"),
        tuple(event.get("minimal_anchor_ids") or []),
        tuple(
            (
                row.get("claim_span"),
                tuple(row.get("anchor_ids") or []),
                row.get("combination"),
            )
            for row in event.get("support_obligations") or []
            if isinstance(row, Mapping)
        ),
    )


def stability_disagreement(run_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_slots = 0
    changed_slots = 0
    for case_id in CASE_ORDER:
        main_doc = read_json(
            run_dir / f"samples/main/{case_id}/candidate/model_json.json"
        )
        repeat_doc = read_json(
            run_dir / f"samples/stability/{case_id}/candidate/model_json.json"
        )
        main_events = [
            _event_signature(row)
            for row in main_doc.get("events", [])
            if isinstance(row, Mapping)
        ]
        repeat_events = [
            _event_signature(row)
            for row in repeat_doc.get("events", [])
            if isinstance(row, Mapping)
        ]
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
                "exact_payload_equal": main_doc == repeat_doc,
            }
        )
    return {
        "schema_version": "v02-anchor-first-stability-disagreement.v1",
        "status": "diagnostic_only_never_overwrites_main",
        "chapters": rows,
        "compared_slots": total_slots,
        "changed_slots": changed_slots,
        "overall_disagreement_rate": (
            changed_slots / total_slots if total_slots else 0.0
        ),
        "main_result_selection": "main_only",
        "stability_result_can_replace_main": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("prepare", "零调用冻结正式三章执行件"),
        ("verify", "从 C1 真源重建并核对准备件"),
        ("run-main", "SenseNova V4 Flash 三章主测"),
        ("run-stability", "主测收口后的同输入稳定性复测"),
        ("status", "读取运行状态"),
    ):
        item = sub.add_parser(command, help=help_text)
        item.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
        item.add_argument(
            "--supply-dir",
            type=Path,
            default=SUPPLY_DIR,
            help="明确指定本轮冻结供料目录；默认仍是旧 C1 供料。",
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = args.run_dir.resolve()
    supply_dir = args.supply_dir.resolve()
    if args.command == "prepare":
        result = prepare_run(run_dir, supply_dir)
    elif args.command == "verify":
        result = verify_prepared(run_dir, supply_dir)
    elif args.command == "run-main":
        result = run_main(run_dir, supply_dir=supply_dir)
    elif args.command == "run-stability":
        result = run_stability(run_dir, supply_dir=supply_dir)
    else:
        result = {
            "run_dir": display_path(run_dir),
            "supply_dir": display_path(supply_dir),
            "prepared": (run_dir / "prepared/preflight.json").is_file(),
            "main_completed": (run_dir / "completion/main.json").is_file(),
            "stability_completed": (
                run_dir / "completion/stability.json"
            ).is_file(),
            "hard_stopped": _hard_stop_path(run_dir).is_file(),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
