#!/usr/bin/env python3
"""公共模型横向试验薄壳：冻结阶段输入，只替换显式供应商与模型。"""

from __future__ import annotations

import argparse
import copy
import http.client
import json
import os
import re
import shutil
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import z75_multidirection_score as z75_score
import z79_fact_sheet_v3_pilot as z79
from pipeline_common.artifacts import (
    ArtifactError,
    read_json,
    repo_relative_identity,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from zbatch_modules import neutral_extract, z83_retry_transport
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "experiments/model_benchmarks"
STAGE_ROOT = ROOT / "config/model_benchmarks/stages"
ADAPTERS_PATH = ROOT / "config/model_benchmarks/provider_adapters.json"
DEFAULTS_PATH = ROOT / "config/model_benchmarks/defaults.json"
INDEX_PATH = BENCHMARK_ROOT / "INDEX.md"
ADAPTER_SCHEMA_VERSION = "model-benchmark-provider-adapters-v2"
LEGACY_ADAPTER_SCHEMA_VERSION = "model-benchmark-provider-adapters-v1"
BENCHMARK_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
FORBIDDEN_VISIBLE_TOKENS = (
    "GOLD-C0003-",
    "structure-gold-v1.2",
    "strict_hit",
    "semantic_shadow",
    "coverage_only_invalid_support",
    "第3章结构层金标v1.2",
)
RUNTIME_DEPENDENCIES = (
    Path(__file__),
    Path(z83_retry_transport.__file__),
    Path(neutral_extract.__file__),
    Path(z75_score.__file__),
    Path(z79.__file__),
)


class BenchmarkHardStop(ZBatchError):
    """试验出现预写失败面，必须封存当前目录。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def write_bytes_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def append_jsonl_fsync(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def copy_file(
    source: Path,
    target: Path,
    *,
    artifact_root: Path,
) -> dict[str, Any]:
    try:
        target_identity = repo_relative_identity(ROOT, target)
    except ArtifactError:
        # 单测或离线回放可把完整运行目录放在仓外；此时仍只记运行目录相对身份。
        target_identity = repo_relative_identity(artifact_root, target)
    try:
        source_identity = repo_relative_identity(ROOT, source)
    except ArtifactError:
        source_identity = repo_relative_identity(artifact_root, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {
        "source": source_identity,
        "source_sha256": sha256_file(source),
        "target": target_identity,
        "target_sha256": sha256_file(target),
    }


def benchmark_dir(benchmark_id: str) -> Path:
    if not BENCHMARK_ID_PATTERN.fullmatch(benchmark_id):
        raise ZBatchError("试验编号只允许英文字母、数字、点、下划线和短横线")
    return BENCHMARK_ROOT / benchmark_id


def stage_path(stage_id: str) -> Path:
    if not BENCHMARK_ID_PATTERN.fullmatch(stage_id):
        raise ZBatchError("阶段编号格式错误")
    return STAGE_ROOT / f"{stage_id}.json"


def load_stage(stage_id: str) -> dict[str, Any]:
    path = stage_path(stage_id)
    stage = read_json(path)
    if stage.get("schema_version") != "model-benchmark-stage-v1":
        raise ZBatchError(f"模型试验阶段合同版本错误：{path}")
    if stage.get("stage_id") != stage_id:
        raise ZBatchError("模型试验阶段编号与文件名不一致")
    return stage


def load_adapters() -> dict[str, Any]:
    adapters = read_json(ADAPTERS_PATH)
    if adapters.get("schema_version") != ADAPTER_SCHEMA_VERSION:
        raise ZBatchError("模型试验供应商适配合同版本错误")
    return adapters


def load_defaults() -> dict[str, Any]:
    defaults = read_json(DEFAULTS_PATH)
    if defaults.get("schema_version") != "model-benchmark-defaults-v1":
        raise ZBatchError("模型横评默认口径版本错误")
    temperature = defaults.get("default_temperature")
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
        raise ZBatchError("模型横评默认温度不是数字")
    default_stage_id = defaults.get("default_stage_id")
    if not isinstance(default_stage_id, str) or not stage_path(default_stage_id).is_file():
        raise ZBatchError("模型横评默认阶段不存在")
    return defaults


def load_provider(provider_id: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    adapters = load_adapters()
    provider_adapter = adapters.get("providers", {}).get(provider_id)
    if not isinstance(provider_adapter, Mapping):
        raise ZBatchError(f"供应商尚未进入模型试验通道：{provider_id}")
    config_path = ROOT / str(provider_adapter.get("provider_config", ""))
    provider = read_json(config_path)
    if provider.get("schema_version") != "provider-channel-v1":
        raise ZBatchError(f"供应商配置合同版本错误：{config_path}")
    if provider.get("provider") != provider_id:
        raise ZBatchError("供应商配置身份漂移")
    if provider.get("enabled_by_default") is not False:
        raise ZBatchError("横向试验供应商必须保持默认关闭")
    return provider, dict(provider_adapter), config_path


def resolve_model(provider: Mapping[str, Any], model_id: str) -> dict[str, Any]:
    rows = provider.get("models")
    if not isinstance(rows, list):
        raise ZBatchError("供应商配置缺模型清单")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("model_id") == model_id]
    if len(matches) != 1:
        raise ZBatchError(f"模型没有按精确 ID 唯一登记：{model_id}")
    model = dict(matches[0])
    if model.get("call_ready") is not True:
        raise ZBatchError(f"模型尚未准入调用：{model_id}")
    return model


def resolve_profile(
    adapter: Mapping[str, Any],
    profile_id: str,
    model_id: str,
    *,
    provider: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = adapter.get("profiles", {}).get(profile_id)
    if not isinstance(profile, Mapping):
        raise ZBatchError(f"供应商没有这个兼容档：{profile_id}")
    validated = profile.get("validated_model_ids")
    if not isinstance(validated, list) or not validated:
        raise ZBatchError(f"兼容档缺精确模型白名单：{profile_id}")
    if any(not isinstance(value, str) or not value for value in validated):
        raise ZBatchError(f"兼容档模型白名单含空值或非字符串：{profile_id}")
    if len(validated) != len(set(validated)):
        raise ZBatchError(f"兼容档模型白名单含重复精确 ID：{profile_id}")
    if provider is not None:
        registered = {
            row.get("model_id")
            for row in provider.get("models", [])
            if isinstance(row, Mapping)
        }
        unknown = [value for value in validated if value not in registered]
        if unknown:
            raise ZBatchError(f"兼容档白名单含未登记模型：{unknown}")
    if model_id not in validated:
        raise ZBatchError(
            f"模型与兼容档尚未做过配对验证：{model_id}／{profile_id}"
        )
    return dict(profile)


def resolve_legacy_frozen_profile(
    adapter: Mapping[str, Any], profile_id: str
) -> dict[str, Any]:
    """只供旧完成轮回读；旧合同不得再用于 prepare 或发网。"""

    profile = adapter.get("profiles", {}).get(profile_id)
    if not isinstance(profile, Mapping):
        raise ZBatchError(f"冻结旧适配合同缺兼容档：{profile_id}")
    return dict(profile)


def source_pins(stage: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = stage.get("source_artifacts")
    if not isinstance(artifacts, Mapping):
        raise ZBatchError("阶段配置缺 source_artifacts")
    rows: list[dict[str, Any]] = []
    for name, value in artifacts.items():
        if not isinstance(value, Mapping):
            raise ZBatchError(f"来源工件条目不是对象：{name}")
        path = ROOT / str(value.get("path", ""))
        expected = value.get("sha256")
        if not path.is_file() or sha256_file(path) != expected:
            raise ZBatchError(f"冻结来源缺失或 SHA 漂移：{name}")
        rows.append({"name": name, "path": value["path"], "sha256": expected})
    return {"status": "pass", "rows": rows}


def protected_snapshot(stage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_pins": source_pins(stage),
        "formal_and_default": z79.assert_protected()["formal_and_z75"],
    }


def build_body(
    stage: Mapping[str, Any],
    provider: Mapping[str, Any],
    model_id: str,
    profile: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifacts = stage["source_artifacts"]
    baseline_path = ROOT / artifacts["baseline_request"]["path"]
    baseline = read_json(baseline_path)
    body = copy.deepcopy(baseline)
    body["model"] = model_id
    body["temperature"] = stage["invariants"]["temperature"]
    for field in profile.get("drop_fields", []):
        body.pop(str(field), None)
    for field, value in profile.get("set_fields", {}).items():
        body[str(field)] = copy.deepcopy(value)

    keep_fields = profile.get("keep_fields", [])
    for field in keep_fields:
        if field not in body or body[field] != baseline.get(field):
            if field == "temperature" and body.get(field) == stage["invariants"]["temperature"]:
                continue
            raise ZBatchError(f"兼容档要求保持的请求字段发生漂移：{field}")
    if body.get("messages") != baseline.get("messages"):
        raise ZBatchError("模型可见消息发生漂移")
    if profile.get("single_sample_via_response_gate") is True:
        if "n" in body:
            raise ZBatchError("供应商不接收 n 时，请求仍夹带 n")
    elif body.get("n") != stage["invariants"]["n"]:
        raise ZBatchError("单次采样 n 漂移")
    visible = "\n".join(str(row.get("content", "")) for row in body["messages"])
    forbidden = [token for token in FORBIDDEN_VISIBLE_TOKENS if token in visible]
    if forbidden:
        raise ZBatchError(f"模型请求混入判分材料：{forbidden}")
    if body.get("response_format") == {"type": "json_object"} and "json" not in visible.lower():
        raise ZBatchError("结构化输出请求的提示词没有 JSON 字样")

    keys = sorted(set(baseline) | set(body))
    changed = [key for key in keys if baseline.get(key) != body.get(key)]
    changes = [
        {
            "path": f"$.{key}",
            "baseline": baseline.get(key, "__ABSENT__"),
            "candidate": body.get(key, "__ABSENT__"),
            "kind": (
                "model_selection"
                if key == "model"
                else "stage_invariant"
                if key == "temperature"
                else "provider_compatibility"
            ),
        }
        for key in changed
    ]
    diff = {
        "schema_version": "model-benchmark-compatibility-diff-v1",
        "baseline_request": {
            "path": artifacts["baseline_request"]["path"],
            "sha256": artifacts["baseline_request"]["sha256"],
            "model": baseline.get("model"),
        },
        "candidate": {
            "provider": provider["provider"],
            "model": model_id,
        },
        "changed_paths": [row["path"] for row in changes],
        "changes": changes,
        "compatibility_notes": list(profile.get("compatibility_notes", [])),
        "messages_byte_equal": canonical_bytes(body["messages"])
        == canonical_bytes(baseline["messages"]),
        "messages_sha256": canonical_sha(body["messages"]),
        "gold_or_answer_hits": forbidden,
        "comparison_label": (
            f"{provider['provider']}／{model_id}／"
            f"temperature={stage['invariants']['temperature']}／"
            "供应商兼容档条件成绩"
        ),
    }
    return body, diff


def secret_scan(root: Path, key: str | None = None) -> dict[str, Any]:
    key_bytes = key.encode("utf-8") if key else b""
    exact: list[str] = []
    authorization: list[str] = []

    def contains_authorization(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(
                str(name).lower() == "authorization" or contains_authorization(child)
                for name, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_authorization(child) for child in value)
        return False

    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        if key_bytes and key_bytes in raw:
            exact.append(relative)
        request_bearing = relative.startswith(("prepared/", "transport/", "candidate/"))
        if request_bearing and path.suffix in {".json", ".jsonl"}:
            try:
                if path.suffix == ".jsonl":
                    documents = [json.loads(line) for line in raw.decode().splitlines() if line]
                    hit = any(contains_authorization(value) for value in documents)
                else:
                    hit = contains_authorization(json.loads(raw.decode()))
            except (UnicodeDecodeError, json.JSONDecodeError):
                hit = False
            if hit:
                authorization.append(relative)
    return {
        "exact_key_hits": exact,
        "exact_key_hit_count": len(exact),
        "authorization_header_hits": authorization,
        "authorization_header_hit_count": len(authorization),
    }


def write_state(root: Path, *, status: str, details: Mapping[str, Any] | None = None) -> None:
    write_json_atomic(
        root / "state.json",
        {
            "schema_version": "model-benchmark-state-v1",
            "status": status,
            "details": dict(details or {}),
            "updated_at": now_iso(),
        },
    )


def prepare(
    root: Path,
    *,
    benchmark_id: str,
    stage_id: str,
    provider_id: str,
    model_id: str,
    profile_id: str,
    allow_temperature_diagnostic: bool = False,
    diagnostic_reason: str | None = None,
) -> dict[str, Any]:
    if root.exists():
        raise ZBatchError(f"试验目录已存在，拒绝覆盖或复跑：{root}")
    defaults = load_defaults()
    stage = load_stage(stage_id)
    stage_temperature = stage.get("invariants", {}).get("temperature")
    if (
        stage_id == defaults["default_stage_id"]
        and stage_temperature != defaults["default_temperature"]
    ):
        raise ZBatchError("默认阶段温度与横评默认口径不一致")
    diagnostic_reason = (diagnostic_reason or "").strip()
    if stage_temperature != defaults["default_temperature"] and (
        not allow_temperature_diagnostic or not diagnostic_reason
    ):
        raise ZBatchError(
            "非默认温度只允许另开的诊断轮；必须显式授权并填写诊断理由"
        )
    provider, adapter, provider_path = load_provider(provider_id)
    resolve_model(provider, model_id)
    profile = resolve_profile(adapter, profile_id, model_id, provider=provider)
    pins = source_pins(stage)
    protected = protected_snapshot(stage)
    body, diff = build_body(stage, provider, model_id, profile)

    root.mkdir(parents=True)
    spec = {
        "schema_version": "model-benchmark-v1",
        "benchmark_id": benchmark_id,
        "stage_id": stage_id,
        "provider": provider_id,
        "model": model_id,
        "profile": profile_id,
        "swap_module": stage["swap_module"],
        "write_root": root.relative_to(ROOT).as_posix() if root.is_relative_to(ROOT) else str(root),
        "single_sample_no_rerun": True,
        "candidate_only": True,
        "temperature_policy": {
            "default_temperature": defaults["default_temperature"],
            "actual_temperature": stage_temperature,
            "is_diagnostic_exception": stage_temperature
            != defaults["default_temperature"],
            "diagnostic_reason": diagnostic_reason or None,
        },
        "created_at": now_iso(),
    }
    write_json_exclusive(root / "benchmark.json", spec)
    copies = []
    copy_names = {
        "baseline_request": "baseline_request.json",
        "chapter_text": "chapter.txt",
        "evidence_catalog": "evidence_catalog.json",
        "prompt_package": "prompt_package.json",
    }
    for source_name, target_name in copy_names.items():
        source = ROOT / stage["source_artifacts"][source_name]["path"]
        copies.append(
            copy_file(source, root / "inputs" / target_name, artifact_root=root)
        )
    copies.extend(
        [
            copy_file(
                stage_path(stage_id),
                root / "inputs/stage_contract.json",
                artifact_root=root,
            ),
            copy_file(
                DEFAULTS_PATH,
                root / "inputs/benchmark_defaults.json",
                artifact_root=root,
            ),
            copy_file(
                provider_path,
                root / "inputs/provider_config.json",
                artifact_root=root,
            ),
            copy_file(
                ADAPTERS_PATH,
                root / "inputs/provider_adapters.json",
                artifact_root=root,
            ),
        ]
    )
    runtime_dependencies = []
    for path in RUNTIME_DEPENDENCIES:
        relative = path.relative_to(ROOT)
        frozen = root / "inputs/runtime_dependencies" / relative
        copies.append(copy_file(path, frozen, artifact_root=root))
        runtime_dependencies.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256_file(path),
                "frozen_path": frozen.relative_to(root).as_posix(),
                "frozen_sha256": sha256_file(frozen),
            }
        )
    write_json_exclusive(root / "inputs/source_pins.json", pins)
    write_json_exclusive(root / "prepared/request_body.json", body)
    artifact = {
        "schema_version": "model-benchmark-request-v1",
        "benchmark_id": benchmark_id,
        "stage_id": stage_id,
        "provider": provider_id,
        "model": model_id,
        "profile": profile_id,
        "url": provider["base_url"] + provider["endpoint"],
        "body": body,
        "_security": "no_api_key_no_authorization",
    }
    write_json_exclusive(root / "prepared/request_artifact.json", artifact)
    write_json_exclusive(root / "prepared/compatibility_diff.json", diff)
    preflight = {
        "schema_version": "model-benchmark-preflight-v1",
        "status": "pass_zero_call_prepared",
        "model_api_calls": 0,
        "network_attempts": 0,
        "benchmark": spec,
        "source_pins": pins,
        "copied_inputs": copies,
        "protected_before": protected,
        "request": {
            "body_sha256": sha256_file(root / "prepared/request_body.json"),
            "artifact_sha256": sha256_file(root / "prepared/request_artifact.json"),
            "messages_sha256": canonical_sha(body["messages"]),
            "messages_equal_baseline": diff["messages_byte_equal"],
            "changed_paths": diff["changed_paths"],
            "gold_or_answer_hits": diff["gold_or_answer_hits"],
        },
        "runtime_dependencies": runtime_dependencies,
        "created_at": now_iso(),
    }
    write_json_exclusive(root / "prepared/preflight.json", preflight)
    write_state(root, status="prepared_zero_call")
    first = verify_prepared(root)
    second = verify_prepared(root)
    if first != second:
        raise ZBatchError("零调用机械复验连续两次不一致")
    verification = {
        "schema_version": "model-benchmark-prepared-verification-v1",
        "status": "pass_twice_identical",
        "first": first,
        "second": second,
        "vector_sha256": canonical_sha(first),
    }
    write_json_exclusive(root / "prepared/mechanical_verification.json", verification)
    return preflight


def load_context(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = read_json(root / "benchmark.json")
    if spec.get("schema_version") != "model-benchmark-v1":
        raise ZBatchError("试验身份合同版本错误")
    stage = load_stage(str(spec["stage_id"]))
    provider, adapter, _ = load_provider(str(spec["provider"]))
    resolve_model(provider, str(spec["model"]))
    profile = resolve_profile(
        adapter,
        str(spec["profile"]),
        str(spec["model"]),
        provider=provider,
    )
    return spec, stage, provider, profile


def load_frozen_context(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """读取本轮随目录冻结的合同，供完工审计和历史重判使用。"""

    spec = read_json(root / "benchmark.json")
    if spec.get("schema_version") != "model-benchmark-v1":
        raise ZBatchError("试验身份合同版本错误")
    stage = read_json(root / "inputs/stage_contract.json")
    if (
        stage.get("schema_version") != "model-benchmark-stage-v1"
        or stage.get("stage_id") != spec.get("stage_id")
    ):
        raise ZBatchError("冻结阶段合同身份漂移")
    provider = read_json(root / "inputs/provider_config.json")
    if (
        provider.get("schema_version") != "provider-channel-v1"
        or provider.get("provider") != spec.get("provider")
        or provider.get("enabled_by_default") is not False
    ):
        raise ZBatchError("冻结供应商配置身份漂移")
    resolve_model(provider, str(spec["model"]))
    adapters = read_json(root / "inputs/provider_adapters.json")
    adapter_schema = adapters.get("schema_version")
    if adapter_schema not in {
        ADAPTER_SCHEMA_VERSION,
        LEGACY_ADAPTER_SCHEMA_VERSION,
    }:
        raise ZBatchError("冻结供应商适配合同版本错误")
    adapter = adapters.get("providers", {}).get(spec["provider"])
    if not isinstance(adapter, Mapping):
        raise ZBatchError("冻结适配合同缺本轮供应商")
    if adapter_schema == ADAPTER_SCHEMA_VERSION:
        profile = resolve_profile(
            adapter,
            str(spec["profile"]),
            str(spec["model"]),
            provider=provider,
        )
    else:
        profile = resolve_legacy_frozen_profile(adapter, str(spec["profile"]))
    artifact = read_json(root / "prepared/request_artifact.json")
    body = read_json(root / "prepared/request_body.json")
    if (
        artifact.get("benchmark_id") != spec.get("benchmark_id")
        or artifact.get("stage_id") != spec.get("stage_id")
        or artifact.get("provider") != spec.get("provider")
        or artifact.get("model") != spec.get("model")
        or artifact.get("profile") != spec.get("profile")
        or artifact.get("body") != body
        or body.get("model") != spec.get("model")
    ):
        raise ZBatchError("冻结试验身份与请求工件不一致")
    return spec, stage, provider, profile


def verify_prepared(root: Path) -> dict[str, Any]:
    spec, stage, provider, profile = load_context(root)
    preflight = read_json(root / "prepared/preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("零调用准备票状态错误")
    if (root / "transport/run_claim.json").exists():
        raise ZBatchError("正式单次采样票已占用")
    pins = source_pins(stage)
    body, diff = build_body(stage, provider, spec["model"], profile)
    if read_json(root / "prepared/request_body.json") != body:
        raise ZBatchError("冻结请求漂移")
    artifact = read_json(root / "prepared/request_artifact.json")
    if artifact.get("body") != body or artifact.get("model") != spec["model"]:
        raise ZBatchError("冻结请求工件不能机械回建")
    if read_json(root / "prepared/compatibility_diff.json") != diff:
        raise ZBatchError("供应商兼容差异账漂移")
    live_copy_pairs = (
        (stage_path(str(spec["stage_id"])), root / "inputs/stage_contract.json", "阶段合同"),
        (DEFAULTS_PATH, root / "inputs/benchmark_defaults.json", "横评默认口径"),
        (
            ROOT / str(load_adapters()["providers"][spec["provider"]]["provider_config"]),
            root / "inputs/provider_config.json",
            "供应商配置",
        ),
        (ADAPTERS_PATH, root / "inputs/provider_adapters.json", "供应商适配合同"),
    )
    for live, frozen, label in live_copy_pairs:
        if not live.is_file() or not frozen.is_file() or live.read_bytes() != frozen.read_bytes():
            raise ZBatchError(f"{label}在 prepare 后漂移；禁止按旧准备件发网")
    runtime_dependencies = preflight.get("runtime_dependencies")
    expected_dependencies = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(path),
            "frozen_path": (
                Path("inputs/runtime_dependencies") / path.relative_to(ROOT)
            ).as_posix(),
            "frozen_sha256": sha256_file(
                root / "inputs/runtime_dependencies" / path.relative_to(ROOT)
            ),
        }
        for path in RUNTIME_DEPENDENCIES
    ]
    if runtime_dependencies != expected_dependencies:
        raise ZBatchError("试验运行器或关键依赖在 prepare 后发生漂移")
    for path in RUNTIME_DEPENDENCIES:
        frozen = root / "inputs/runtime_dependencies" / path.relative_to(ROOT)
        if not frozen.is_file() or frozen.read_bytes() != path.read_bytes():
            raise ZBatchError("关键运行依赖源码副本漂移")
    current_protected = protected_snapshot(stage)
    if current_protected != preflight.get("protected_before"):
        raise ZBatchError("冻结输入或现役保护件在 prepare 后漂移；禁止发网")
    scan = secret_scan(root)
    if scan["authorization_header_hit_count"]:
        raise ZBatchError("零调用准备件出现 Authorization 字段")
    return {
        "source_pins_sha256": canonical_sha(pins),
        "body_sha256": sha256_file(root / "prepared/request_body.json"),
        "artifact_sha256": sha256_file(root / "prepared/request_artifact.json"),
        "messages_sha256": canonical_sha(body["messages"]),
        "messages_equal_baseline": diff["messages_byte_equal"],
        "changed_paths": diff["changed_paths"],
        "secret_scan": scan,
        "provider_config_sha256": sha256_file(root / "inputs/provider_config.json"),
        "benchmark_defaults_sha256": sha256_file(
            root / "inputs/benchmark_defaults.json"
        ),
        "protected_before_sha256": canonical_sha(current_protected),
    }


def catalog_status_policy(provider: Mapping[str, Any]) -> str:
    policy = provider.get("model_catalog_status_policy", "require_online")
    if policy not in {"require_online", "presence_only"}:
        raise BenchmarkHardStop(
            "model_catalog_contract", f"不认识的模型目录状态策略：{policy!r}"
        )
    return str(policy)


def select_online_catalog_model(
    raw: bytes, model_id: str, *, status_policy: str = "require_online"
) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkHardStop("model_catalog_invalid_json", "模型目录响应不是合法 JSON") from exc
    rows = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        raise BenchmarkHardStop("model_catalog_contract", "模型目录响应缺 data 数组")
    matches = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("id") == model_id
    ]
    if len(matches) != 1:
        raise BenchmarkHardStop(
            "model_catalog_exact_id_missing", f"模型目录没有唯一精确型号：{model_id}"
        )
    selected = matches[0]
    if status_policy == "require_online" and selected.get("status") != "online":
        raise BenchmarkHardStop(
            "model_catalog_not_online",
            f"精确型号当前不是 online：{model_id}／{selected.get('status')!r}",
        )
    if status_policy not in {"require_online", "presence_only"}:
        raise BenchmarkHardStop(
            "model_catalog_contract", f"不认识的模型目录状态策略：{status_policy!r}"
        )
    return selected


def catalog_receipt_status(status_policy: str) -> str:
    return (
        "pass_exact_model_online"
        if status_policy == "require_online"
        else "pass_exact_model_present"
    )


def audit_provider_model_catalog(
    root: Path, provider: Mapping[str, Any], model_id: str
) -> dict[str, str] | None:
    if provider.get("model_catalog_check_required_before_run") is not True:
        return None
    raw_path = root / "transport/provider_model_catalog_raw.json"
    receipt_path = root / "transport/provider_model_catalog.json"
    if not raw_path.is_file() or not receipt_path.is_file():
        raise ZBatchError("供应商模型目录原件或验收票缺失")
    raw = raw_path.read_bytes()
    status_policy = catalog_status_policy(provider)
    selected = select_online_catalog_model(
        raw, model_id, status_policy=status_policy
    )
    endpoint = provider.get("model_catalog_endpoint")
    expected = {
        "schema_version": "model-benchmark-provider-model-catalog-v1",
        "status": catalog_receipt_status(status_policy),
        "provider": provider["provider"],
        "model_id": model_id,
        "catalog_url": str(provider["base_url"]) + str(endpoint),
        "http_status": 200,
        "selected_model": selected,
        "raw_response_path": raw_path.relative_to(root).as_posix(),
        "raw_response_sha256": sha256_bytes(raw),
        "model_api_calls": 0,
        "catalog_network_attempts": 1,
    }
    receipt = read_json(receipt_path)
    if set(receipt) != {*expected, "checked_at"}:
        raise ZBatchError("供应商模型目录验收票字段集合漂移")
    if any(receipt.get(field) != value for field, value in expected.items()):
        raise ZBatchError("供应商模型目录验收票不能由原始响应重建")
    if not isinstance(receipt.get("checked_at"), str) or not receipt["checked_at"]:
        raise ZBatchError("供应商模型目录验收票缺检查时间")
    return {
        "receipt_sha256": sha256_file(receipt_path),
        "raw_response_sha256": sha256_file(raw_path),
    }


def verify_provider_model_catalog(
    root: Path,
    provider: Mapping[str, Any],
    model_id: str,
    key: str,
    *,
    opener: Any = None,
) -> dict[str, Any] | None:
    """腾讯等动态目录通道在正式采样前核精确型号；不产生模型 token。"""

    if provider.get("model_catalog_check_required_before_run") is not True:
        return None
    endpoint = provider.get("model_catalog_endpoint")
    if not isinstance(endpoint, str) or not endpoint.startswith("/"):
        raise BenchmarkHardStop("model_catalog_contract", "供应商要求目录闸但未配置目录端点")
    url = str(provider["base_url"]) + endpoint
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        method="GET",
    )
    open_fn = opener or urllib.request.build_opener(_NoRedirectHandler()).open
    try:
        with open_fn(request, timeout=60) as response:
            raw = response.read()
            http_status = int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        if key.encode() in raw:
            raise BenchmarkHardStop("api_key_echoed", "模型目录响应回显 API Key") from exc
        raise BenchmarkHardStop(
            "model_catalog_http_error",
            f"模型目录检查返回 HTTP {int(exc.code)}",
        ) from exc
    except (
        urllib.error.URLError,
        TimeoutError,
        http.client.IncompleteRead,
        ConnectionError,
        socket.timeout,
    ) as exc:
        raise BenchmarkHardStop(
            "model_catalog_transport_error", f"模型目录检查运输失败：{type(exc).__name__}"
        ) from exc
    if key.encode() in raw:
        raise BenchmarkHardStop("api_key_echoed", "模型目录响应回显 API Key")
    raw_path = root / "transport/provider_model_catalog_raw.json"
    write_bytes_exclusive(raw_path, raw)
    status_policy = catalog_status_policy(provider)
    selected = select_online_catalog_model(
        raw, model_id, status_policy=status_policy
    )
    if http_status != 200:
        raise BenchmarkHardStop(
            "model_catalog_http_status", f"模型目录检查返回 HTTP {http_status}"
        )
    receipt = {
        "schema_version": "model-benchmark-provider-model-catalog-v1",
        "status": catalog_receipt_status(status_policy),
        "provider": provider["provider"],
        "model_id": model_id,
        "catalog_url": url,
        "http_status": http_status,
        "selected_model": selected,
        "raw_response_path": raw_path.relative_to(root).as_posix(),
        "raw_response_sha256": sha256_bytes(raw),
        "model_api_calls": 0,
        "catalog_network_attempts": 1,
        "checked_at": now_iso(),
    }
    write_json_exclusive(root / "transport/provider_model_catalog.json", receipt)
    return receipt


def _safe_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    allowed = {"retry-after", "content-type", "x-request-id", "request-id"}
    return {
        str(key): str(value)
        for key, value in headers.items()
        if str(key).lower() in allowed
    }


def send_once_factory(
    *,
    root: Path,
    provider: Mapping[str, Any],
    key: str,
    logical_request_id: str,
    request_sha: str,
    wire_body: bytes,
    wire_sha: str,
    opener: Any = None,
):
    open_fn = opener or urllib.request.build_opener(_NoRedirectHandler()).open
    url = str(provider["base_url"]) + str(provider["endpoint"])

    def send_once(attempt: int) -> z83_retry_transport.AttemptOutcome:
        reservation = {
            "schema_version": "model-benchmark-attempt-reservation-v1",
            "logical_request_id": logical_request_id,
            "attempt": attempt,
            "request_artifact_sha256": request_sha,
            "wire_body_sha256": wire_sha,
            "reserved_at": now_iso(),
        }
        reservation["row_sha256"] = canonical_sha(reservation)
        append_jsonl_fsync(root / "transport/attempt_reservations.jsonl", reservation)
        started = now_iso()
        request = urllib.request.Request(
            url,
            data=wire_body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with open_fn(request, timeout=600) as response:
                raw = response.read()
                status = int(getattr(response, "status", 200) or 200)
                headers = _safe_headers(dict(response.headers.items()))
            if key.encode() in raw:
                return z83_retry_transport.AttemptOutcome(
                    http_status=status,
                    request_sha256=request_sha,
                    raw_response_sha256=sha256_bytes(raw),
                    usage={"status": "unknown_due_to_security_redaction"},
                    headers=headers,
                    payload={
                        "raw_path": None,
                        "response_json": None,
                        "envelope_error": "api_key_echoed",
                    },
                    error_code="api_key_echoed",
                    wire_body_sha256=wire_sha,
                    request_artifact_sha256=request_sha,
                    error_body_sha256=sha256_bytes(raw),
                    started_at=started,
                    finished_at=now_iso(),
                )
            raw_path = root / f"transport/raw_responses/attempt{attempt:02d}.json"
            write_bytes_exclusive(raw_path, raw)
            parsed: Mapping[str, Any] | None = None
            usage: Mapping[str, Any] = {}
            envelope_error: str | None = None
            try:
                value = json.loads(raw.decode("utf-8"))
                if isinstance(value, dict):
                    parsed = value
                    if isinstance(value.get("usage"), Mapping):
                        usage = dict(value["usage"])
                else:
                    envelope_error = "http_200_non_object"
            except (UnicodeDecodeError, json.JSONDecodeError):
                envelope_error = "http_200_invalid_json"
            return z83_retry_transport.AttemptOutcome(
                http_status=status,
                request_sha256=request_sha,
                raw_response_sha256=sha256_bytes(raw),
                usage=usage,
                headers=headers,
                payload={
                    "raw_path": raw_path,
                    "response_json": parsed,
                    "envelope_error": envelope_error,
                },
                wire_body_sha256=wire_sha,
                request_artifact_sha256=request_sha,
                started_at=started,
                finished_at=now_iso(),
            )
        except urllib.error.HTTPError as exc:
            error_body = exc.read() if hasattr(exc, "read") else b""
            if key.encode() in error_body:
                return z83_retry_transport.AttemptOutcome(
                    http_status=int(exc.code),
                    request_sha256=request_sha,
                    headers=_safe_headers(dict(exc.headers.items())) if exc.headers else {},
                    error_code="api_key_echoed",
                    wire_body_sha256=wire_sha,
                    request_artifact_sha256=request_sha,
                    error_body_sha256=sha256_bytes(error_body),
                    started_at=started,
                    finished_at=now_iso(),
                )
            write_bytes_exclusive(
                root / f"transport/errors/attempt{attempt:02d}.bin", error_body
            )
            return z83_retry_transport.AttemptOutcome(
                http_status=int(exc.code),
                request_sha256=request_sha,
                headers=_safe_headers(dict(exc.headers.items())) if exc.headers else {},
                error_code=f"http_{int(exc.code)}",
                wire_body_sha256=wire_sha,
                request_artifact_sha256=request_sha,
                error_body_sha256=sha256_bytes(error_body),
                started_at=started,
                finished_at=now_iso(),
            )
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.IncompleteRead,
            ConnectionError,
            socket.timeout,
        ) as exc:
            partial = exc.partial if isinstance(exc, http.client.IncompleteRead) else b""
            return z83_retry_transport.AttemptOutcome(
                http_status=598,
                request_sha256=request_sha,
                error_code=f"transport_{type(exc).__name__}",
                wire_body_sha256=wire_sha,
                request_artifact_sha256=request_sha,
                error_body_sha256=sha256_bytes(partial),
                started_at=started,
                finished_at=now_iso(),
            )

    return send_once


def load_attempt_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit_completed(root: Path) -> dict[str, Any]:
    """只从冻结输入、原始响应和运输账重建完成态，不复用旧判词。"""

    spec, stage, provider, profile = load_frozen_context(root)
    if (root / "transport/hard_stop.json").exists():
        raise ZBatchError("试验已硬停，禁止审计成完成态")
    if not (root / "transport/sample_completion.json").is_file():
        raise ZBatchError("正式样张尚未完成")
    catalog_audit = audit_provider_model_catalog(root, provider, str(spec["model"]))
    request_path = root / "transport/request.json"
    prepared_artifact = root / "prepared/request_artifact.json"
    if request_path.read_bytes() != prepared_artifact.read_bytes():
        raise ZBatchError("实发请求工件与冻结请求工件不一致")
    request_sha = sha256_file(request_path)
    body = read_json(root / "prepared/request_body.json")
    wire_sha = sha256_bytes(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    attempts = load_attempt_rows(root / "transport/call_attempts.jsonl")
    z83_retry_transport.validate_attempt_rows(attempts)
    z83_retry_transport.validate_retry_wait_sequence(
        root / "transport/call_attempts.jsonl",
        attempts,
        require_all_429_completed=True,
    )
    reservations = load_attempt_rows(root / "transport/attempt_reservations.jsonl")
    if len(reservations) != len(attempts):
        raise ZBatchError("尝试占用票与真实尝试数不一致")
    for reservation, attempt in zip(reservations, attempts, strict=True):
        preimage = {key: value for key, value in reservation.items() if key != "row_sha256"}
        if (
            reservation.get("schema_version")
            != "model-benchmark-attempt-reservation-v1"
            or reservation.get("logical_request_id") != attempt.get("logical_request_id")
            or reservation.get("attempt") != attempt.get("attempt")
            or reservation.get("request_artifact_sha256")
            != attempt.get("request_artifact_sha256")
            or reservation.get("wire_body_sha256") != attempt.get("wire_body_sha256")
            or reservation.get("row_sha256") != canonical_sha(preimage)
        ):
            raise ZBatchError("尝试占用票不能与真实尝试逐行重建")
    successful = [row for row in attempts if row.get("outcome") == "success"]
    if len(successful) != 1 or successful[0].get("http_status") != 200:
        raise ZBatchError("完成态必须恰好有一个成功响应")
    success = successful[0]
    if success.get("request_artifact_sha256") != request_sha:
        raise ZBatchError("尝试账请求 SHA 与实发工件不一致")
    if success.get("wire_body_sha256") != wire_sha:
        raise ZBatchError("尝试账 wire body SHA 不一致")
    attempt_number = int(success["attempt"])
    raw_path = root / f"transport/raw_responses/attempt{attempt_number:02d}.json"
    if not raw_path.is_file() or sha256_file(raw_path) != success.get("raw_response_sha256"):
        raise ZBatchError("成功响应原件缺失或 SHA 不一致")
    response = read_json(raw_path)
    model_data, content, reasoning, finish = response_envelope(
        response,
        str(spec["model"]),
        require_nonempty_reasoning=profile.get("require_nonempty_reasoning_content")
        is True,
    )

    catalog_doc = read_json(root / "inputs/evidence_catalog.json")
    catalog = catalog_doc.get("entries") if isinstance(catalog_doc, Mapping) else None
    if not isinstance(catalog, list):
        raise ZBatchError("冻结证据目录缺 entries")
    materialized, program_audit = neutral_extract.process_model_data(
        model_data, chapter=int(stage["chapter"]), catalog=catalog
    )
    if read_json(root / "candidate/model_json.json") != model_data:
        raise ZBatchError("候选模型 JSON 不能由原始响应重建")
    if read_json(root / "candidate/neutral_events.json") != materialized:
        raise ZBatchError("中性事件不能由原始响应重建")
    if read_json(root / "candidate/program_audit.json") != program_audit:
        raise ZBatchError("程序核对账不能由原始响应重建")

    events = model_data.get("events")
    if not isinstance(events, list):
        raise ZBatchError("模型 JSON 缺 events 数组")
    expected_mechanical = {
        "schema_version": "model-benchmark-mechanical-gates-v1",
        "status": "pass",
        "json_and_schema_gate": True,
        "catalog_anchor_gate": len(program_audit["missing_catalog_anchor_ids"]) == 0,
        "length_and_contiguous_id_gate": (
            program_audit["status"] == "pass"
            and program_audit["event_ids_contiguous"]
            and program_audit["invalid_event_id_count"] == 0
        ),
        "event_count": len(events),
        "anchor_reference_count": program_audit["anchor_reference_count"],
        "outside_catalog_anchor_count": len(program_audit["missing_catalog_anchor_ids"]),
        "invalid_event_id_count": program_audit["invalid_event_id_count"],
        "events_without_anchors": program_audit["events_without_anchors"],
        "finish_reason": finish,
        "response_model": response.get("model"),
        "content_sha256": sha256_bytes(content.encode()),
        "reasoning_content_sha256": sha256_bytes(reasoning.encode()),
    }
    if read_json(root / "scorecard/mechanical.json") != expected_mechanical:
        raise ZBatchError("机械闸不能由原始响应重建")

    usage_rows = load_attempt_rows(root / "transport/usage.jsonl")
    if len(usage_rows) != 1:
        raise ZBatchError("完成态必须恰好有一条 usage")
    usage = usage_rows[0]
    if (
        usage.get("request_artifact_sha256") != request_sha
        or usage.get("raw_response_sha256") != sha256_file(raw_path)
        or usage.get("usage") != success.get("usage")
    ):
        raise ZBatchError("usage 与请求／响应／尝试账不一致")
    checkpoint = read_json(root / "transport/checkpoint.json")
    expected_checkpoint_fields = {
        "request_sha256": request_sha,
        "wire_body_sha256": wire_sha,
        "raw_response_sha256": sha256_file(raw_path),
        "attempt_rows_sha256": canonical_sha(attempts),
        "usage_row_sha256": usage["row_sha256"],
        "mechanical_sha256": sha256_file(root / "scorecard/mechanical.json"),
        "adjudication_template_sha256": sha256_file(
            root / "scorecard/adjudication_template.json"
        ),
        "sealed": True,
    }
    if catalog_audit is not None:
        expected_checkpoint_fields.update(
            {
                "provider_model_catalog_receipt_sha256": catalog_audit[
                    "receipt_sha256"
                ],
                "provider_model_catalog_raw_sha256": catalog_audit[
                    "raw_response_sha256"
                ],
            }
        )
    for field, expected in expected_checkpoint_fields.items():
        if checkpoint.get(field) != expected:
            raise ZBatchError(f"不可变检查点字段漂移：{field}")
    checkpoint_preimage = {
        key: value for key, value in checkpoint.items() if key != "checkpoint_id"
    }
    if checkpoint.get("checkpoint_id") != canonical_sha(checkpoint_preimage):
        raise ZBatchError("不可变检查点 ID 不能由本体重建")
    prepared_verification = read_json(root / "prepared/mechanical_verification.json")
    first = prepared_verification.get("first")
    if (
        prepared_verification.get("status") != "pass_twice_identical"
        or not isinstance(first, Mapping)
        or prepared_verification.get("second") != first
        or prepared_verification.get("vector_sha256") != canonical_sha(first)
    ):
        raise ZBatchError("零调用双次复验票不能重建")
    scan = secret_scan(root)
    if scan["authorization_header_hit_count"]:
        raise ZBatchError("完成工件出现 Authorization 字段")
    completion = read_json(root / "transport/sample_completion.json")
    expected_completion = {
        "schema_version": "model-benchmark-sample-completion-v1",
        "status": "sample_completed_awaiting_semantic_score",
        "logical_samples": 1,
        "network_attempts": len(attempts),
        "429_count": sum(1 for row in attempts if row.get("http_status") == 429),
        "response_model": response.get("model"),
        "usage": usage["usage"],
        "event_count": len(events),
        "mechanical_gates": "pass",
        "checkpoint_id": checkpoint["checkpoint_id"],
        "secret_scan": {
            "exact_key_hits": [],
            "exact_key_hit_count": 0,
            "authorization_header_hits": [],
            "authorization_header_hit_count": 0,
        },
        "protected_unchanged": True,
        "prepared_verification_sha256": canonical_sha(first),
    }
    if set(completion) != {*expected_completion, "completed_at"}:
        raise ZBatchError("样张完成票字段集合漂移")
    for field, expected in expected_completion.items():
        if completion.get(field) != expected:
            raise ZBatchError(f"样张完成票字段不能由原始工件重建：{field}")
    if not isinstance(completion.get("completed_at"), str) or not completion["completed_at"]:
        raise ZBatchError("样张完成票缺完成时间")
    receipt = {
        "schema_version": "model-benchmark-completion-audit-v1",
        "status": "pass_rebuilt_from_raw",
        "benchmark_id": spec["benchmark_id"],
        "request_sha256": request_sha,
        "raw_response_sha256": sha256_file(raw_path),
        "attempt_count": len(attempts),
        "successful_response_count": 1,
        "usage_row_count": 1,
        "event_count": len(events),
        "checkpoint_id": checkpoint["checkpoint_id"],
        "secret_authorization_hits": 0,
    }
    path = root / "transport/completion_audit.json"
    if path.exists():
        if read_json(path) != receipt:
            raise ZBatchError("既有完工审计票与原始工件重建结果不一致")
    else:
        write_json_exclusive(path, receipt)
    return receipt


def write_hard_stop(root: Path, *, reason_code: str, error: BaseException) -> dict[str, Any]:
    path = root / "transport/hard_stop.json"
    if path.exists():
        return read_json(path)
    attempts = load_attempt_rows(root / "transport/call_attempts.jsonl")
    usage_unknown = any(
        row.get("usage") == z83_retry_transport.UNKNOWN_USAGE
        or row.get("error_code") == "api_key_echoed"
        or (
            isinstance(row.get("usage"), Mapping)
            and row["usage"].get("status") == "unknown_due_to_security_redaction"
        )
        for row in attempts
    )
    receipt = {
        "schema_version": "model-benchmark-hard-stop-v1",
        "status": "hard_stop_no_rerun_no_patch",
        "reason_code": reason_code,
        "error_type": type(error).__name__,
        "error": str(error),
        "logical_sample_count": 1 if attempts else 0,
        "network_attempts": len(attempts),
        "usage_tokens": (
            "unknown"
            if usage_unknown
            else sum(
                int(row.get("usage", {}).get("total_tokens", 0))
                for row in attempts
                if isinstance(row.get("usage"), Mapping)
            )
        ),
        "rerun_allowed": False,
        "created_at": now_iso(),
    }
    write_json_exclusive(path, receipt)
    write_state(root, status="hard_stopped", details=receipt)
    return receipt


def response_envelope(
    response: Mapping[str, Any],
    requested_model: str,
    *,
    require_nonempty_reasoning: bool = False,
) -> tuple[dict[str, Any], str, str, str]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise BenchmarkHardStop("choices_contract", "正式响应 choices 不是唯一对象")
    finish = choices[0].get("finish_reason")
    if finish == "length":
        raise BenchmarkHardStop("finish_reason_length", "正式响应触顶，拒绝重跑")
    if finish != "stop":
        raise BenchmarkHardStop("finish_reason_unexpected", f"finish_reason={finish!r}")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise BenchmarkHardStop("message_contract", "正式响应缺 message 对象")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise BenchmarkHardStop("empty_final_content", "正式响应正文为空")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise BenchmarkHardStop("content_invalid_json", f"正式响应正文不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkHardStop("content_non_object", "正式响应 JSON 不是对象")
    reasoning = message.get("reasoning_content") or ""
    if not isinstance(reasoning, str):
        raise BenchmarkHardStop("reasoning_content_contract", "reasoning_content 不是字符串")
    if require_nonempty_reasoning and not reasoning.strip():
        raise BenchmarkHardStop(
            "thinking_not_observed",
            "请求要求思考模式，但响应没有可观察的非空 reasoning_content",
        )
    response_model = response.get("model")
    if not isinstance(response_model, str) or not (
        response_model == requested_model or response_model.startswith(f"{requested_model}-")
    ):
        raise BenchmarkHardStop(
            "response_model_mismatch",
            f"响应模型为 {response_model!r}，不是请求模型 {requested_model}",
        )
    return payload, content, reasoning, str(finish)


def build_adjudication_template(
    root: Path, stage: Mapping[str, Any], event_ids: Sequence[str]
) -> dict[str, Any]:
    artifacts = stage["source_artifacts"]
    gold_pointer = ROOT / artifacts["gold_pointer"]["path"]
    gold_file = ROOT / artifacts["gold_file"]["path"]
    formal = z75_score.load_formal_gold(gold_pointer)
    denominator = int(stage["invariants"]["gold_denominator"])
    if formal["gold_sha256"] != artifacts["gold_file"]["sha256"]:
        raise ZBatchError("现役金标指针与阶段钉死金标不一致")
    if formal["denominator"] != denominator:
        raise ZBatchError("金标分母漂移")
    copies = [
        copy_file(
            gold_pointer,
            root / "scorecard/score_only/正式金标指针.json",
            artifact_root=root,
        ),
        copy_file(
            gold_file,
            root / "scorecard/score_only/第3章结构层金标v1.2.json",
            artifact_root=root,
        ),
    ]
    template = {
        "schema_version": "model-benchmark-adjudication-template-v1",
        "status": "awaiting_semantic_review",
        "gold_sha256": formal["gold_sha256"],
        "formal_denominator": denominator,
        "candidate_event_ids": list(event_ids),
        "gold_rows": [
            {
                "part_id": part_id,
                "claim": part["claim"],
                "verdict": "pending",
                "candidate_event_ids": [],
                "reason": "",
            }
            for part_id, part in formal["parts"].items()
        ],
        "score_only_copies": copies,
        "model_visible_request_contains_score_material": False,
    }
    write_json_exclusive(root / "scorecard/adjudication_template.json", template)
    return template


def run(
    root: Path, *, opener: Any = None, catalog_opener: Any = None
) -> dict[str, Any]:
    verification = verify_prepared(root)
    spec, stage, _, profile = load_frozen_context(root)
    provider = read_json(root / "inputs/provider_config.json")
    if provider.get("provider") != spec["provider"]:
        raise ZBatchError("冻结供应商配置身份漂移")
    resolve_model(provider, str(spec["model"]))
    key_env = str(provider["api_key_env"])
    key = os.environ.get(key_env)
    if not key:
        raise ZBatchError(f"缺少 {key_env}；未占用正式调用票")
    try:
        verify_provider_model_catalog(
            root,
            provider,
            str(spec["model"]),
            key,
            opener=catalog_opener,
        )
        catalog_audit = audit_provider_model_catalog(
            root, provider, str(spec["model"])
        )
    except (BenchmarkHardStop, ZBatchError) as exc:
        reason_code = (
            exc.reason_code
            if isinstance(exc, BenchmarkHardStop)
            else "model_catalog_audit"
        )
        write_hard_stop(root, reason_code=reason_code, error=exc)
        if isinstance(exc, BenchmarkHardStop):
            raise
        raise BenchmarkHardStop(reason_code, str(exc)) from exc
    logical_request_id = f"{spec['benchmark_id']}-C{int(stage['chapter']):04d}"
    write_json_exclusive(
        root / "transport/run_claim.json",
        {
            "schema_version": "model-benchmark-run-claim-v1",
            "benchmark_id": spec["benchmark_id"],
            "logical_request_id": logical_request_id,
            "single_sample_no_rerun": True,
            "claimed_at": now_iso(),
        },
    )
    write_state(root, status="running")
    body = read_json(root / "prepared/request_body.json")
    artifact = read_json(root / "prepared/request_artifact.json")
    request_path = root / "transport/request.json"
    write_json_exclusive(request_path, artifact)
    request_sha = sha256_file(request_path)
    wire = json.dumps(body, ensure_ascii=False).encode("utf-8")
    wire_sha = sha256_bytes(wire)
    if key in request_path.read_text():
        raise BenchmarkHardStop("secret_in_request_artifact", "请求工件意外含 API Key")
    policy = z83_retry_transport.RetryPolicy(
        retry_delays_seconds=(5.0, 10.0),
        max_429_retries_per_request=2,
        max_429_per_run=5,
        max_retry_after_seconds=300.0,
        same_chapter_gap_seconds=10.0,
        cross_chapter_gap_seconds=30.0,
    )
    try:
        logical = z83_retry_transport.run_logical_request(
            logical_request_id=logical_request_id,
            chapter=int(stage["chapter"]),
            send_once=send_once_factory(
                root=root,
                provider=provider,
                key=key,
                logical_request_id=logical_request_id,
                request_sha=request_sha,
                wire_body=wire,
                wire_sha=wire_sha,
                opener=opener,
            ),
            attempt_ledger_path=root / "transport/call_attempts.jsonl",
            contract_version="model-benchmark-transport-v1",
            state=z83_retry_transport.RetryRunState(),
            policy=policy,
        )
    except BenchmarkHardStop as exc:
        write_hard_stop(root, reason_code=exc.reason_code, error=exc)
        raise
    except z83_retry_transport.RetryTransportHardStop as exc:
        attempt_rows = load_attempt_rows(root / "transport/call_attempts.jsonl")
        reason_code = (
            "api_key_echoed"
            if attempt_rows and attempt_rows[-1].get("error_code") == "api_key_echoed"
            else exc.reason_code
        )
        message = "服务端响应回显 API Key" if reason_code == "api_key_echoed" else str(exc)
        wrapped = BenchmarkHardStop(reason_code, message)
        write_hard_stop(root, reason_code=reason_code, error=wrapped)
        raise wrapped from exc

    payload = logical.outcome.payload
    if not isinstance(payload, Mapping) or payload.get("envelope_error"):
        envelope_error = payload.get("envelope_error") if isinstance(payload, Mapping) else None
        reason_code = "api_key_echoed" if envelope_error == "api_key_echoed" else "response_envelope"
        message = "服务端响应回显 API Key" if reason_code == "api_key_echoed" else "HTTP 200 响应外壳不能解析"
        error = BenchmarkHardStop(reason_code, message)
        write_hard_stop(root, reason_code=error.reason_code, error=error)
        raise error
    response = payload.get("response_json")
    raw_path = payload.get("raw_path")
    if not isinstance(response, Mapping) or not isinstance(raw_path, Path):
        error = BenchmarkHardStop("response_artifact_missing", "正式响应工件缺失")
        write_hard_stop(root, reason_code=error.reason_code, error=error)
        raise error
    attempts = list(logical.attempt_rows)
    usage = dict(logical.outcome.usage or {})
    try:
        model_data, content, reasoning, finish = response_envelope(
            response,
            spec["model"],
            require_nonempty_reasoning=profile.get(
                "require_nonempty_reasoning_content"
            )
            is True,
        )
        catalog_doc = read_json(root / "inputs/evidence_catalog.json")
        catalog = catalog_doc.get("entries") if isinstance(catalog_doc, Mapping) else None
        if not isinstance(catalog, list):
            raise BenchmarkHardStop("catalog_contract", "冻结证据目录缺 entries")
        materialized, audit = neutral_extract.process_model_data(
            model_data, chapter=int(stage["chapter"]), catalog=catalog
        )
        if audit.get("missing_catalog_anchor_ids"):
            raise BenchmarkHardStop("outside_catalog_anchor", "目录外锚不为0")
        write_json_exclusive(root / "candidate/model_json.json", model_data)
        write_json_exclusive(root / "candidate/neutral_events.json", materialized)
        write_json_exclusive(root / "candidate/program_audit.json", audit)
        events = model_data.get("events")
        if not isinstance(events, list):
            raise BenchmarkHardStop("event_schema", "模型 JSON 缺 events 数组")
        mechanical = {
            "schema_version": "model-benchmark-mechanical-gates-v1",
            "status": "pass",
            "json_and_schema_gate": True,
            "catalog_anchor_gate": len(audit["missing_catalog_anchor_ids"]) == 0,
            "length_and_contiguous_id_gate": (
                audit["status"] == "pass"
                and audit["event_ids_contiguous"]
                and audit["invalid_event_id_count"] == 0
            ),
            "event_count": len(events),
            "anchor_reference_count": audit["anchor_reference_count"],
            "outside_catalog_anchor_count": len(audit["missing_catalog_anchor_ids"]),
            "invalid_event_id_count": audit["invalid_event_id_count"],
            "events_without_anchors": audit["events_without_anchors"],
            "finish_reason": finish,
            "response_model": response.get("model"),
            "content_sha256": sha256_bytes(content.encode()),
            "reasoning_content_sha256": sha256_bytes(reasoning.encode()),
        }
        if not all(
            mechanical[key]
            for key in (
                "json_and_schema_gate",
                "catalog_anchor_gate",
                "length_and_contiguous_id_gate",
            )
        ):
            raise BenchmarkHardStop("mechanical_gate", "机械三闸没有全过")
        write_json_exclusive(root / "scorecard/mechanical.json", mechanical)
        usage_row = {
            "schema_version": "model-benchmark-usage-v1",
            "logical_request_id": logical_request_id,
            "chapter": stage["chapter"],
            "request_artifact_sha256": request_sha,
            "raw_response_sha256": logical.outcome.raw_response_sha256,
            "usage": usage,
            "recorded_at": now_iso(),
        }
        usage_row["row_sha256"] = canonical_sha(usage_row)
        append_jsonl_fsync(root / "transport/usage.jsonl", usage_row)
        build_adjudication_template(
            root,
            stage,
            [str(row.get("event_id")) for row in events if isinstance(row, Mapping)],
        )
        checkpoint = {
            "schema_version": "model-benchmark-checkpoint-v1",
            "request_sha256": request_sha,
            "wire_body_sha256": wire_sha,
            "raw_response_sha256": logical.outcome.raw_response_sha256,
            "attempt_rows_sha256": canonical_sha(attempts),
            "usage_row_sha256": usage_row["row_sha256"],
            "mechanical_sha256": sha256_file(root / "scorecard/mechanical.json"),
            "adjudication_template_sha256": sha256_file(
                root / "scorecard/adjudication_template.json"
            ),
            "sealed": True,
        }
        if catalog_audit is not None:
            checkpoint.update(
                {
                    "provider_model_catalog_receipt_sha256": catalog_audit[
                        "receipt_sha256"
                    ],
                    "provider_model_catalog_raw_sha256": catalog_audit[
                        "raw_response_sha256"
                    ],
                }
            )
        checkpoint["checkpoint_id"] = canonical_sha(checkpoint)
        write_json_exclusive(root / "transport/checkpoint.json", checkpoint)
    except (BenchmarkHardStop, ZBatchError) as exc:
        reason = exc.reason_code if isinstance(exc, BenchmarkHardStop) else "mechanical_contract"
        write_hard_stop(root, reason_code=reason, error=exc)
        raise BenchmarkHardStop(reason, str(exc)) from exc

    scan = secret_scan(root, key)
    if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
        error = BenchmarkHardStop("secret_trace_detected", "试验目录检出密钥或鉴权头")
        write_hard_stop(root, reason_code=error.reason_code, error=error)
        raise error
    if protected_snapshot(stage) != read_json(root / "prepared/preflight.json")["protected_before"]:
        error = BenchmarkHardStop("protected_artifact_drift", "冻结输入或现役保护件漂移")
        write_hard_stop(root, reason_code=error.reason_code, error=error)
        raise error
    completion = {
        "schema_version": "model-benchmark-sample-completion-v1",
        "status": "sample_completed_awaiting_semantic_score",
        "logical_samples": 1,
        "network_attempts": len(attempts),
        "429_count": sum(1 for row in attempts if row.get("http_status") == 429),
        "response_model": response.get("model"),
        "usage": usage,
        "event_count": mechanical["event_count"],
        "mechanical_gates": "pass",
        "checkpoint_id": checkpoint["checkpoint_id"],
        "secret_scan": scan,
        "protected_unchanged": True,
        "prepared_verification_sha256": canonical_sha(verification),
        "completed_at": now_iso(),
    }
    write_json_exclusive(root / "transport/sample_completion.json", completion)
    try:
        audit = audit_completed(root)
    except (ZBatchError, BenchmarkHardStop) as exc:
        write_hard_stop(root, reason_code="completion_audit_failure", error=exc)
        raise BenchmarkHardStop("completion_audit_failure", str(exc)) from exc
    write_state(root, status="sample_completed_audited_awaiting_semantic_score")
    return {**completion, "completion_audit": audit}


def validate_adjudication(
    root: Path, stage: Mapping[str, Any], adjudication: Path
) -> list[dict[str, Any]]:
    doc = read_json(adjudication)
    if doc.get("schema_version") != "model-benchmark-adjudication-v1":
        raise ZBatchError("横向试验判词合同版本错误")
    denominator = int(stage["invariants"]["gold_denominator"])
    if doc.get("gold_sha256") != stage["source_artifacts"]["gold_file"]["sha256"]:
        raise ZBatchError("判词没有钉死本阶段金标")
    if doc.get("formal_denominator") != denominator:
        raise ZBatchError("判词分母错误")
    event_doc = read_json(root / "candidate/model_json.json")
    event_ids = {
        str(row.get("event_id"))
        for row in event_doc.get("events", [])
        if isinstance(row, Mapping)
    }
    formal = z75_score.load_formal_gold(
        ROOT / stage["source_artifacts"]["gold_pointer"]["path"]
    )
    rows = doc.get("gold_rows")
    if not isinstance(rows, list) or len(rows) != denominator:
        raise ZBatchError("判词没有逐条覆盖金标分母")
    allowed = {"strict_hit", "semantic_shadow", "coverage_only_invalid_support", "miss"}
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ZBatchError("判词含非对象")
        part_id = row.get("part_id")
        verdict = row.get("verdict")
        candidates = row.get("candidate_event_ids")
        reason = row.get("reason")
        if part_id not in formal["parts"] or part_id in seen:
            raise ZBatchError(f"金标编号重复或越界：{part_id}")
        if verdict not in allowed:
            raise ZBatchError(f"判词状态错误：{part_id}")
        if not isinstance(candidates, list) or any(value not in event_ids for value in candidates):
            raise ZBatchError(f"判词引用不存在的候选事件：{part_id}")
        if verdict == "miss" and candidates:
            raise ZBatchError(f"漏项不得夹带候选事件：{part_id}")
        if verdict != "miss" and not candidates:
            raise ZBatchError(f"命中或影子必须引用候选事件：{part_id}")
        if not isinstance(reason, str) or not reason.strip():
            raise ZBatchError(f"判词缺理由：{part_id}")
        seen.add(str(part_id))
        result.append(dict(row))
    if seen != set(formal["parts"]):
        raise ZBatchError("判词金标覆盖不完整")
    return result


def render_summary(
    spec: Mapping[str, Any], stage: Mapping[str, Any], scorecard: Mapping[str, Any]
) -> str:
    score = scorecard["gold_chapter_3"]
    usage = scorecard["usage"]
    return f"""# 模型横向试验总结｜{spec['benchmark_id']}

✅ 本轮只替换 M04 的供应商／模型插槽；模型可见消息、正文、证据目录、Prompt 与金标均未改。

| 项目 | 结果 |
|---|---|
| 阶段 | {stage['display_name']} |
| 供应商／模型 | {spec['provider']}／{spec['model']} |
| 兼容档 | {spec['profile']} |
| 单次采样 | 是，未重跑挑结果 |
| 机械三闸 | PASS |
| 严格命中 | {score['strict_hit']}/{score['formal_denominator']} |
| 有效召回 | {score['effective_recall']}/{score['formal_denominator']} |
| 表面覆盖 | {score['surface_coverage']}/{score['formal_denominator']} |
| 锚不托 | {score['invalid_anchor_observation']} |
| Token | {usage.get('total_tokens', 'unknown')} |

## 横向读法

本轮是“{spec['profile']}＋temperature={stage['invariants']['temperature']}”条件成绩。供应商兼容差异见 `prepared/compatibility_diff.json`，不能把它冒充成所有参数完全相同的纯模型单变量。

基线：retry03 DeepSeek V4 Flash 严格 6/23、有效 20/23；Z89 DeepSeek V4 Pro 严格 10/23、有效 20/23。

本轮仍是候选银标，不改默认链，不自动升模型。

来源：Codex
"""


def score(root: Path, adjudication: Path) -> dict[str, Any]:
    if (root / "transport/hard_stop.json").exists():
        raise ZBatchError("试验已硬停，禁止登记质量胜负")
    if not (root / "transport/sample_completion.json").is_file():
        raise ZBatchError("单次正式样张尚未完成")
    audit = audit_completed(root)
    if audit.get("status") != "pass_rebuilt_from_raw":
        raise ZBatchError("完工重建审计没有通过")
    spec, stage, _, _ = load_frozen_context(root)
    rows = validate_adjudication(root, stage, adjudication)
    denominator = int(stage["invariants"]["gold_denominator"])
    summary = z75_score.score_summary(rows, denominator)
    usage_rows = load_attempt_rows(root / "transport/usage.jsonl")
    if len(usage_rows) != 1:
        raise ZBatchError("完成态 usage 账不是唯一一行")
    scorecard = {
        "schema_version": "model-benchmark-scorecard-v1",
        "status": "candidate_silver_scored",
        "benchmark_id": spec["benchmark_id"],
        "provider": spec["provider"],
        "model": spec["model"],
        "profile": spec["profile"],
        "gold_chapter_3": summary,
        "baselines": stage["baseline_scores"],
        "mechanical_gates": read_json(root / "scorecard/mechanical.json"),
        "usage": usage_rows[0]["usage"],
        "single_sample_no_rerun": True,
        "candidate_tier": "silver_only",
        "promoted_or_default_changed": False,
        "compatibility_diff_sha256": sha256_file(
            root / "prepared/compatibility_diff.json"
        ),
        "created_at": now_iso(),
    }
    target = root / "scorecard/adjudication_completed.json"
    if adjudication.resolve() != target.resolve():
        copy_file(adjudication.resolve(), target, artifact_root=root)
    write_json_exclusive(root / "scorecard/final.json", scorecard)
    (root / "summary.md").write_text(render_summary(spec, stage, scorecard), encoding="utf-8")
    receipt = f"""# 模型横向试验回执｜{spec['benchmark_id']}

- 模型调用：1 次逻辑采样；网络尝试 {audit['attempt_count']} 次。
- 结果位置：`candidate/`；成绩位置：`scorecard/final.json`；人读总结：`summary.md`。
- 密钥：只由环境变量临时注入，运行目录检出 0。
- 现役件：未回写；本轮只进候选银标。
- 回退：整目录停用即可，现役链无需恢复动作。

来源：Codex
"""
    (root / "receipt.md").write_text(receipt, encoding="utf-8")
    write_state(root, status="completed_candidate_scored", details={"score": summary})
    return scorecard


def rebuild_index() -> dict[str, Any]:
    rows = []
    for root in sorted(path for path in BENCHMARK_ROOT.iterdir() if path.is_dir()):
        spec_path = root / "benchmark.json"
        if not spec_path.is_file():
            continue
        spec = read_json(spec_path)
        state = read_json(root / "state.json") if (root / "state.json").is_file() else {}
        score_path = root / "scorecard/final.json"
        score_text = "—"
        if score_path.is_file():
            result = read_json(score_path)["gold_chapter_3"]
            score_text = f"严格 {result['strict_hit']}/23；有效 {result['effective_recall']}/23"
        rows.append(
            {
                "benchmark_id": spec["benchmark_id"],
                "stage": spec["stage_id"],
                "provider_model": f"{spec['provider']}／{spec['model']}",
                "profile": spec["profile"],
                "status": state.get("status", "unknown"),
                "score": score_text,
                "path": (
                    root.relative_to(ROOT).as_posix()
                    if root.is_relative_to(ROOT)
                    else f"{BENCHMARK_ROOT.name}/{root.name}"
                ),
            }
        )
    lines = [
        "# 模型横向试验索引",
        "",
        "| 试验编号 | 阶段 | 供应商／模型 | 兼容档 | 状态 | 成绩 | 位置 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {benchmark_id} | {stage} | {provider_model} | {profile} | {status} | "
            "{score} | `{path}` |".format(**row)
        )
    lines.extend(["", "来源：Codex", ""])
    INDEX_PATH.write_text("\n".join(lines), encoding="utf-8")
    return {
        "indexed": len(rows),
        "path": (
            INDEX_PATH.relative_to(ROOT).as_posix()
            if INDEX_PATH.is_relative_to(ROOT)
            else str(INDEX_PATH)
        ),
    }


def list_options() -> dict[str, Any]:
    defaults = load_defaults()
    adapters = load_adapters()
    providers = {}
    for provider_id in sorted(adapters["providers"]):
        provider, adapter, _ = load_provider(provider_id)
        registered_models = [
            row["model_id"]
            for row in provider.get("models", [])
            if isinstance(row, Mapping) and row.get("call_ready") is True
        ]
        runnable_pairs = []
        paired_models: set[str] = set()
        for profile_id in sorted(adapter.get("profiles", {})):
            profile = adapter["profiles"][profile_id]
            validated = profile.get("validated_model_ids") if isinstance(profile, Mapping) else None
            if not isinstance(validated, list) or not validated:
                raise ZBatchError(f"兼容档缺精确模型白名单：{profile_id}")
            for model_id in validated:
                resolve_model(provider, model_id)
                resolve_profile(
                    adapter,
                    profile_id,
                    model_id,
                    provider=provider,
                )
                runnable_pairs.append({"model": model_id, "profile": profile_id})
                paired_models.add(model_id)
        providers[provider_id] = {
            "runnable_pairs": runnable_pairs,
            "registered_models_without_validated_profile": [
                model_id for model_id in registered_models if model_id not in paired_models
            ],
        }
    return {
        "defaults": defaults,
        "stages": sorted(path.stem for path in STAGE_ROOT.glob("*.json")),
        "providers": providers,
        "write_root": BENCHMARK_ROOT.relative_to(ROOT).as_posix(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list")
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--benchmark-id", required=True)
    prepare_parser.add_argument("--stage", required=True)
    prepare_parser.add_argument("--provider", required=True)
    prepare_parser.add_argument("--model", required=True)
    prepare_parser.add_argument("--profile", required=True)
    prepare_parser.add_argument("--allow-temperature-diagnostic", action="store_true")
    prepare_parser.add_argument("--diagnostic-reason")
    for action in ("verify", "run", "audit"):
        command = subparsers.add_parser(action)
        command.add_argument("--benchmark-id", required=True)
    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--benchmark-id", required=True)
    score_parser.add_argument("--adjudication", type=Path, required=True)
    subparsers.add_parser("index")
    args = parser.parse_args(argv)
    try:
        if args.action == "list":
            result = list_options()
        elif args.action == "index":
            result = rebuild_index()
        else:
            root = benchmark_dir(args.benchmark_id)
            if args.action == "prepare":
                result = prepare(
                    root,
                    benchmark_id=args.benchmark_id,
                    stage_id=args.stage,
                    provider_id=args.provider,
                    model_id=args.model,
                    profile_id=args.profile,
                    allow_temperature_diagnostic=args.allow_temperature_diagnostic,
                    diagnostic_reason=args.diagnostic_reason,
                )
            elif args.action == "verify":
                result = verify_prepared(root)
            elif args.action == "run":
                result = run(root)
            elif args.action == "audit":
                result = audit_completed(root)
            else:
                result = score(root, args.adjudication.resolve())
    except (ZBatchError, BenchmarkHardStop, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "error", "type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
