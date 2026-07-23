#!/usr/bin/env python3
"""第91道步二：三章双臂的运输与机械验收薄壳。

本工具只负责六份冻结请求的单次采样、运输留痕和机械三闸。来源事实只在
发网前验 seal，不进入模型请求；语义盲审仍由后续人工步骤完成。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import z91_crossbook_exam_prep as step1
from pipeline_common import model_benchmark
from zbatch_modules import neutral_extract, z83_retry_transport
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
STEP1_DIR = ROOT / "runs/Z91_双臂跨书基线_步一试卷_v1.2_20260723"
DEFAULT_RUN_DIR = ROOT / "runs/Z91_双臂跨书基线_步二双臂_v1.0_20260723"
SENSENOVA_PROVIDER_PATH = ROOT / "config/providers/sensenova.json"
TENCENT_PROVIDER_PATH = ROOT / "config/providers/tencent_tokenhub_multi_model.json"
ACCESS_POLICY_PATH = ROOT / "config/providers/provider_access_policy.json"
CONTRACT_VERSION = "z91-crossbook-six-sample-transport-v1"
FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro-202606"

CASES: tuple[dict[str, Any], ...] = (
    {
        "case_key": "X02-C0031",
        "chapter": 31,
        "messages_sha256": "680e752b1f2f826f45d75e8370739263a19b5b89d7010841edcd13c4f8cab796",
    },
    {
        "case_key": "X03-C0019",
        "chapter": 19,
        "messages_sha256": "ae3eeb0fcfa10383133e946ae0cb3ef35c0139dfe136f815351d7106ae89b35b",
    },
    {
        "case_key": "X04-C0046",
        "chapter": 46,
        "messages_sha256": "67b0e416af4cccdc9265dd77abe91b958f419b5df162009358ab92ad854c3a99",
    },
)

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm_id": "flash_sensenova",
        "provider": "sensenova",
        "model": FLASH_MODEL,
        "request_filename": "flash_sensenova.json",
        "key_env": "SENSENOVA_API_KEY",
        "require_reasoning": False,
    },
    {
        "arm_id": "pro_primary_tencent",
        "provider": "tencent_tokenhub",
        "model": PRO_MODEL,
        "request_filename": "pro_primary_tencent.json",
        "key_env": "TENCENT_TOKENHUB_API_KEY",
        "require_reasoning": True,
    },
)

RUNTIME_DEPENDENCIES = (
    Path(__file__).resolve(),
    Path(step1.__file__).resolve(),
    Path(model_benchmark.__file__).resolve(),
    Path(neutral_extract.__file__).resolve(),
    Path(z83_retry_transport.__file__).resolve(),
)

FORBIDDEN_RESOLVED_KEYS = {
    "arm",
    "arm_id",
    "candidate_events",
    "choices",
    "flash_output",
    "model",
    "model_id",
    "model_output",
    "model_outputs",
    "pro_output",
    "response",
    "response_model",
    "usage",
}


class Z91RunHardStop(ZBatchError):
    """正式样本出现预写失败面；当前运行目录不得再采样。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return model_benchmark.sha256_bytes(canonical_bytes(value))


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return model_benchmark.sha256_file(path)


def write_bytes_exclusive(path: Path, raw: bytes) -> None:
    model_benchmark.write_bytes_exclusive(path, raw)


def write_json_exclusive(path: Path, value: Any) -> None:
    model_benchmark.write_json_exclusive(path, value)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _stored_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _assert_sha(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise ZBatchError(f"{label}缺失或 SHA 漂移：{path}")


def _resolve_reference_path(seal_path: Path, stored: str) -> Path:
    raw = Path(stored)
    if raw.is_absolute():
        return raw.resolve()
    run_root = seal_path.parent.parent.parent
    candidates = (
        seal_path.parent / raw,
        run_root / raw,
        ROOT / raw,
    )
    existing = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved not in existing:
            existing.append(resolved)
    if len(existing) != 1:
        raise ZBatchError(f"来源事实引用路径不存在或有歧义：{stored}")
    return existing[0]


def _artifact_reference(
    seal: Mapping[str, Any], field: str, seal_path: Path
) -> dict[str, str]:
    value = seal.get(field)
    stored_path: Any = None
    expected_sha: Any = None
    if isinstance(value, Mapping):
        stored_path = value.get("path")
        expected_sha = value.get("sha256")
    elif isinstance(value, str):
        stored_path = value
        for sha_field in (f"{field}_sha256", f"{field.removesuffix('_file')}_sha256"):
            if sha_field in seal:
                expected_sha = seal.get(sha_field)
                break
    if not isinstance(stored_path, str) or not _is_sha256(expected_sha):
        raise ZBatchError(f"source fact seal 的 {field} 路径或 SHA 不合同")
    path = _resolve_reference_path(seal_path, stored_path)
    _assert_sha(path, str(expected_sha), field)
    return {
        "path": _display_path(path),
        "sha256": str(expected_sha),
    }


def _reviewer_references(
    seal: Mapping[str, Any], seal_path: Path
) -> list[dict[str, str]]:
    values = seal.get("reviewer_files")
    if isinstance(values, Mapping):
        ordered_values = [values[key] for key in sorted(values)]
    elif isinstance(values, list):
        ordered_values = values
    else:
        ordered_values = []
    if len(ordered_values) != 2:
        raise ZBatchError("source fact seal 必须恰好引用两份独立复核原件")
    result: list[dict[str, str]] = []
    companion = seal.get("reviewer_files_sha256")
    for index, value in enumerate(ordered_values):
        if isinstance(value, Mapping):
            stored = value.get("path")
            expected = value.get("sha256")
        else:
            stored = value
            if isinstance(companion, list) and index < len(companion):
                expected = companion[index]
            elif isinstance(companion, Mapping):
                expected = companion.get(str(value))
            else:
                expected = None
        if not isinstance(stored, str) or not _is_sha256(expected):
            raise ZBatchError("source fact seal 的 reviewer_files 路径或 SHA 不合同")
        path = _resolve_reference_path(seal_path, stored)
        _assert_sha(path, str(expected), f"第{index + 1}份复核原件")
        result.append({"path": _display_path(path), "sha256": str(expected)})
    if len({row["path"] for row in result}) != 2:
        raise ZBatchError("两位复核者不能引用同一份原件")
    return result


def _forbidden_keys(value: Any, prefix: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            if name.lower() in FORBIDDEN_RESOLVED_KEYS:
                hits.append(f"{prefix}.{name}")
            hits.extend(_forbidden_keys(child, f"{prefix}.{name}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_forbidden_keys(child, f"{prefix}[{index}]"))
    return hits


def validate_source_fact_seal(seal_path: Path) -> dict[str, Any]:
    """核来源事实先于模型输出封存，且没有夹入任何双臂答案字段。"""

    if not seal_path.is_file():
        raise ZBatchError(f"发网前缺 source fact seal：{seal_path}")
    seal = read_json(seal_path)
    if not isinstance(seal, Mapping):
        raise ZBatchError("source fact seal 顶层不是对象")
    expected_header = {
        "schema_version": "z91-source-fact-seal-v1",
        "status": "sealed_before_model_calls",
        "probe_count": 18,
        "reviewers": 2,
    }
    for field, expected in expected_header.items():
        if seal.get(field) != expected:
            raise ZBatchError(f"source fact seal 的 {field} 漂移")
    if not isinstance(seal.get("sealed_at"), str) or not seal["sealed_at"]:
        raise ZBatchError("source fact seal 缺 sealed_at")

    expected_rubric = sha256_file(STEP1_DIR / "rubric_candidate.json")
    expected_probes = sha256_file(STEP1_DIR / "probe_slots.json")
    if seal.get("rubric_sha256") != expected_rubric:
        raise ZBatchError("source fact seal 没有钉死步一判分尺")
    if seal.get("probe_slots_sha256") != expected_probes:
        raise ZBatchError("source fact seal 没有钉死步一探针槽")
    expected_chapters = {
        str(case["case_key"]): sha256_file(
            STEP1_DIR / f"cases/{case['case_key']}/chapter_body.txt"
        )
        for case in CASES
    }
    if seal.get("chapter_body_sha256_by_case") != expected_chapters:
        raise ZBatchError("source fact seal 的三章正文 SHA 与步一不一致")

    reviewers = _reviewer_references(seal, seal_path)
    adjudication = _artifact_reference(seal, "adjudication_file", seal_path)
    resolved = _artifact_reference(seal, "resolved_file", seal_path)
    resolved_doc = read_json(_stored_path(resolved["path"]))
    hits = _forbidden_keys(resolved_doc)
    if hits:
        raise ZBatchError(f"resolved 来源事实夹入模型输出字段：{hits}")

    preimage_sha = seal.get("seal_preimage_sha256")
    preimage = {key: value for key, value in seal.items() if key != "seal_preimage_sha256"}
    if not _is_sha256(preimage_sha) or preimage_sha != canonical_sha(preimage):
        raise ZBatchError("source fact seal 的前像 SHA 不能由本体重建")

    return {
        "schema_version": "z91-source-fact-seal-audit-v1",
        "status": "pass_sealed_before_model_calls",
        "seal_path": _display_path(seal_path),
        "seal_sha256": sha256_file(seal_path),
        "seal_preimage_sha256": preimage_sha,
        "rubric_sha256": expected_rubric,
        "probe_slots_sha256": expected_probes,
        "chapter_body_sha256_by_case": expected_chapters,
        "reviewer_files": reviewers,
        "adjudication_file": adjudication,
        "resolved_file": resolved,
        "probe_count": 18,
        "reviewers": 2,
        "resolved_model_output_field_hits": [],
    }


def _load_providers() -> dict[str, dict[str, Any]]:
    sensenova = read_json(SENSENOVA_PROVIDER_PATH)
    tencent = read_json(TENCENT_PROVIDER_PATH)
    expected_sensenova = {
        "provider": "sensenova",
        "base_url": "https://token.sensenova.cn/v1",
        "endpoint": "/chat/completions",
        "api_key_env": "SENSENOVA_API_KEY",
        "model": FLASH_MODEL,
    }
    for field, expected in expected_sensenova.items():
        if sensenova.get(field) != expected:
            raise ZBatchError(f"现役 SenseNova 配置 {field} 漂移")
    if FLASH_MODEL not in sensenova.get("allowed_models", []):
        raise ZBatchError("现役 SenseNova 未准入冻结 Flash 型号")

    expected_tencent = {
        "provider": "tencent_tokenhub",
        "base_url": "https://tokenhub.tencentmaas.com/v1",
        "endpoint": "/chat/completions",
        "model_catalog_endpoint": "/models",
        "model_catalog_check_required_before_run": True,
        "api_key_env": "TENCENT_TOKENHUB_API_KEY",
    }
    for field, expected in expected_tencent.items():
        if tencent.get(field) != expected:
            raise ZBatchError(f"腾讯唯一通道配置 {field} 漂移")
    exact = [
        row
        for row in tencent.get("models", [])
        if isinstance(row, Mapping) and row.get("model_id") == PRO_MODEL
    ]
    if len(exact) != 1 or exact[0].get("call_ready") is not True:
        raise ZBatchError("腾讯固定 Pro 型号未按精确 ID 唯一准入")

    policy = read_json(ACCESS_POLICY_PATH)
    official = policy.get("providers", {}).get("deepseek_official", {})
    if official.get("default_action") != "deny" or "permanently_disabled" not in str(
        official.get("status")
    ):
        raise ZBatchError("DeepSeek 官方 API 永久禁用策略漂移")
    return {"sensenova": sensenova, "tencent_tokenhub": tencent}


def _request_source(case_key: str, arm: Mapping[str, Any]) -> Path:
    return STEP1_DIR / f"cases/{case_key}/requests/{arm['request_filename']}"


def _assert_request(
    body: Mapping[str, Any], case: Mapping[str, Any], arm: Mapping[str, Any]
) -> None:
    messages = body.get("messages")
    if canonical_sha(messages) != case["messages_sha256"]:
        raise ZBatchError(f"{case['case_key']} 的 messages SHA 漂移")
    common = {
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 32000,
        "n": 1,
    }
    if arm["arm_id"] == "flash_sensenova":
        expected = {
            **common,
            "model": FLASH_MODEL,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "medium",
        }
    else:
        expected = {
            **common,
            "model": PRO_MODEL,
            "thinking": {"type": "enabled", "reasoning_effort": "medium"},
        }
    if dict(body) != expected:
        raise ZBatchError(
            f"{case['case_key']}／{arm['arm_id']} 冻结请求参数或字段集合漂移"
        )


def sample_specs() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for case in CASES:
        for arm in ARMS:
            sample_id = f"{case['case_key']}__{arm['arm_id']}"
            result.append(
                {
                    **case,
                    **arm,
                    "sample_id": sample_id,
                    "logical_request_id": f"Z91-{sample_id}",
                }
            )
    return result


def _request_artifact(
    run_dir: Path,
    sample: Mapping[str, Any],
    body: Mapping[str, Any],
    provider: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "z91-frozen-request-artifact-v1",
        "run_id": run_dir.name,
        "sample_id": sample["sample_id"],
        "logical_request_id": sample["logical_request_id"],
        "case_key": sample["case_key"],
        "chapter": sample["chapter"],
        "arm_id": sample["arm_id"],
        "provider": sample["provider"],
        "api_base_url": provider["base_url"],
        "api_endpoint": provider["endpoint"],
        "model": sample["model"],
        "contract_version": CONTRACT_VERSION,
        "body": copy.deepcopy(dict(body)),
        "_security": "no_api_key_no_authorization_no_fallback",
    }


def _runtime_dependency_rows() -> list[dict[str, str]]:
    return [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in RUNTIME_DEPENDENCIES
    ]


def _build_prepared_base(
    run_dir: Path, source_fact_seal: Path
) -> tuple[dict[str, bytes], dict[str, Any]]:
    step1_audit = step1.audit_run(STEP1_DIR)
    seal_audit = validate_source_fact_seal(source_fact_seal)
    providers = _load_providers()
    payloads: dict[str, bytes] = {}
    sample_rows: list[dict[str, Any]] = []

    fixed_inputs = (
        "selection.json",
        "probe_slots.json",
        "rubric_candidate.json",
        "request_matrix.json",
        "artifact_manifest.json",
        "SHA256SUMS",
        "mechanical_verification.json",
    )
    for name in fixed_inputs:
        payloads[f"inputs/step1/{name}"] = (STEP1_DIR / name).read_bytes()
    payloads["inputs/providers/sensenova.json"] = SENSENOVA_PROVIDER_PATH.read_bytes()
    payloads[
        "inputs/providers/tencent_tokenhub_multi_model.json"
    ] = TENCENT_PROVIDER_PATH.read_bytes()
    payloads["inputs/provider_access_policy.json"] = ACCESS_POLICY_PATH.read_bytes()
    for dependency in RUNTIME_DEPENDENCIES:
        relative = dependency.relative_to(ROOT).as_posix()
        payloads[f"inputs/runtime_dependencies/{relative}"] = dependency.read_bytes()

    for case in CASES:
        case_key = str(case["case_key"])
        payloads[f"inputs/cases/{case_key}/chapter_body.txt"] = (
            STEP1_DIR / f"cases/{case_key}/chapter_body.txt"
        ).read_bytes()
        payloads[f"inputs/cases/{case_key}/evidence_catalog.json"] = (
            STEP1_DIR / f"cases/{case_key}/evidence_catalog.json"
        ).read_bytes()
        for arm in ARMS:
            sample = next(
                row
                for row in sample_specs()
                if row["case_key"] == case_key and row["arm_id"] == arm["arm_id"]
            )
            source = _request_source(case_key, arm)
            body = read_json(source)
            if not isinstance(body, Mapping):
                raise ZBatchError(f"冻结请求不是对象：{source}")
            _assert_request(body, case, arm)
            provider = providers[str(arm["provider"])]
            artifact = _request_artifact(run_dir, sample, body, provider)
            prefix = f"prepared/samples/{sample['sample_id']}"
            payloads[f"{prefix}/request_body.json"] = json_bytes(body)
            payloads[f"{prefix}/request_artifact.json"] = json_bytes(artifact)
            sample_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "logical_request_id": sample["logical_request_id"],
                    "case_key": case_key,
                    "chapter": case["chapter"],
                    "arm_id": arm["arm_id"],
                    "provider": arm["provider"],
                    "model": arm["model"],
                    "messages_sha256": case["messages_sha256"],
                    "request_body_sha256": sha256_file(source),
                    "request_artifact_sha256": model_benchmark.sha256_bytes(
                        payloads[f"{prefix}/request_artifact.json"]
                    ),
                }
            )

    seal_pin = {
        "schema_version": "z91-source-fact-seal-pin-v1",
        "source_fact_seal_path": _display_path(source_fact_seal),
        "source_fact_seal_sha256": seal_audit["seal_sha256"],
        "audit": seal_audit,
        "model_visible": False,
    }
    payloads["provenance/source_fact_seal_pin.json"] = json_bytes(seal_pin)
    run_plan = {
        "schema_version": "z91-six-sample-run-plan-v1",
        "status": "prepared_zero_call",
        "contract_version": CONTRACT_VERSION,
        "sample_count": 6,
        "samples_per_case": 2,
        "samples": sample_rows,
        "sampling_order": [row["sample_id"] for row in sample_rows],
        "tencent_catalog_gate_before_run_claim": True,
        "tencent_exact_model": PRO_MODEL,
        "automatic_fallback": False,
        "deepseek_official_api_used": False,
        "source_fact_seal_sha256": seal_audit["seal_sha256"],
    }
    payloads["prepared/run_plan.json"] = json_bytes(run_plan)
    preflight = {
        "schema_version": "z91-step2-preflight-v1",
        "status": "pass_zero_call_prepared",
        "run_id": run_dir.name,
        "step1_dir": STEP1_DIR.relative_to(ROOT).as_posix(),
        "step1_manifest_vector_sha256": step1_audit["manifest_vector_sha256"],
        "source_fact_seal_sha256": seal_audit["seal_sha256"],
        "sample_count": 6,
        "model_api_calls": 0,
        "network_attempts": 0,
        "keys_loaded": False,
        "providers": {
            "flash": {
                "provider": "sensenova",
                "model": FLASH_MODEL,
                "provider_config_sha256": sha256_file(SENSENOVA_PROVIDER_PATH),
            },
            "pro": {
                "provider": "tencent_tokenhub",
                "model": PRO_MODEL,
                "provider_config_sha256": sha256_file(TENCENT_PROVIDER_PATH),
                "catalog_gate": "GET /v1/models exact id online before six-sample claim",
            },
        },
        "runtime_dependencies": _runtime_dependency_rows(),
        "deepseek_official_api_used": False,
        "automatic_fallback": False,
    }
    payloads["prepared/preflight.json"] = json_bytes(preflight)
    payloads["run_manifest.json"] = json_bytes(
        {
            "schema_version": "z91-step2-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared_zero_call",
            "sample_count": 6,
            "source_fact_seal_sha256": seal_audit["seal_sha256"],
            "deepseek_official_api_used": False,
            "rerun_allowed_after_claim": False,
        }
    )
    return payloads, preflight


def _build_prepared_payloads(
    run_dir: Path, source_fact_seal: Path
) -> tuple[dict[str, bytes], dict[str, Any]]:
    first, preflight = _build_prepared_base(run_dir, source_fact_seal)
    second, _ = _build_prepared_base(run_dir, source_fact_seal)
    if first != second:
        raise ZBatchError("步二零调用准备连续两次构造不一致")
    vector = {path: model_benchmark.sha256_bytes(raw) for path, raw in sorted(first.items())}
    verification = {
        "schema_version": "z91-step2-prepared-mechanical-verification-v1",
        "status": "pass_twice_identical",
        "first_vector": vector,
        "second_vector": vector,
        "vectors_equal": True,
        "vector_sha256": canonical_sha(vector),
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    result = dict(first)
    result["prepared/mechanical_verification.json"] = json_bytes(verification)
    return result, preflight


def _guard_prepare_target(run_dir: Path, source_fact_seal: Path) -> None:
    if run_dir.resolve() == STEP1_DIR.resolve() or STEP1_DIR.resolve() in run_dir.resolve().parents:
        raise ZBatchError("步二运行目录不能等于或位于步一封存目录内")
    if not run_dir.exists():
        return
    existing = [path for path in run_dir.rglob("*") if path.is_file()]
    if not existing:
        return
    try:
        source_fact_seal.resolve().relative_to(run_dir.resolve())
    except ValueError as exc:
        raise ZBatchError(f"运行目录已存在，拒绝覆盖正式 run：{run_dir}") from exc
    if any(
        not path.resolve().relative_to(run_dir.resolve()).as_posix().startswith(
            "review/source_facts/"
        )
        for path in existing
    ):
        raise ZBatchError(f"运行目录已有正式工件，拒绝覆盖或复跑：{run_dir}")


def prepare(run_dir: Path, source_fact_seal: Path) -> dict[str, Any]:
    _guard_prepare_target(run_dir, source_fact_seal)
    payloads, preflight = _build_prepared_payloads(run_dir, source_fact_seal)
    run_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(payloads.items()):
        write_bytes_exclusive(run_dir / relative, raw)
    verify_prepared(run_dir)
    return preflight


def verify_prepared(run_dir: Path) -> dict[str, Any]:
    pin_path = run_dir / "provenance/source_fact_seal_pin.json"
    if not pin_path.is_file():
        raise ZBatchError("步二缺 source fact seal 引用票")
    pin = read_json(pin_path)
    seal_path = _stored_path(str(pin.get("source_fact_seal_path") or ""))
    payloads, preflight = _build_prepared_payloads(run_dir, seal_path)
    for relative, raw in payloads.items():
        path = run_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise ZBatchError(f"步二准备工件漂移：{relative}")
    scan = secret_scan(run_dir)
    if scan["authorization_header_hit_count"]:
        raise ZBatchError("步二准备目录出现 Authorization 字段")
    return preflight


def secret_scan(run_dir: Path, keys: Sequence[str] = ()) -> dict[str, Any]:
    key_bytes = {key.encode("utf-8") for key in keys if key}
    exact_hits: set[str] = set()
    authorization_hits: set[str] = set()

    def has_authorization(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(
                str(name).lower() == "authorization" or has_authorization(child)
                for name, child in value.items()
            )
        if isinstance(value, list):
            return any(has_authorization(child) for child in value)
        return False

    for path in sorted(value for value in run_dir.rglob("*") if value.is_file()):
        raw = path.read_bytes()
        relative = path.relative_to(run_dir).as_posix()
        if any(key in raw for key in key_bytes):
            exact_hits.add(relative)
        if path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        try:
            if path.suffix.lower() == ".jsonl":
                values = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
            else:
                values = [json.loads(raw.decode())]
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if any(has_authorization(value) for value in values):
            authorization_hits.add(relative)
    return {
        "exact_key_hits": sorted(exact_hits),
        "exact_key_hit_count": len(exact_hits),
        "authorization_header_hits": sorted(authorization_hits),
        "authorization_header_hit_count": len(authorization_hits),
    }


def _load_frozen_providers(run_dir: Path) -> dict[str, dict[str, Any]]:
    providers = {
        "sensenova": read_json(run_dir / "inputs/providers/sensenova.json"),
        "tencent_tokenhub": read_json(
            run_dir / "inputs/providers/tencent_tokenhub_multi_model.json"
        ),
    }
    live = _load_providers()
    if providers != live:
        raise ZBatchError("prepare 后供应商配置漂移；禁止按旧准备件发网")
    return providers


def _attempt_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_checkpoint(
    sample_root: Path,
    *,
    request_artifact: Mapping[str, Any],
    response: Mapping[str, Any],
    usage_record: Mapping[str, Any],
    attempt_rows: Sequence[Mapping[str, Any]],
    mechanical: Mapping[str, Any],
    verdict: str,
) -> dict[str, Any]:
    if verdict not in {"pass", "fail"}:
        raise ZBatchError("Z91 检查点判词只能是 pass/fail")
    root = sample_root / "checkpoint"
    if root.exists() and any(root.iterdir()):
        raise ZBatchError(f"检查点已有内容，拒绝覆盖：{root}")
    payloads = {
        "01_request.json": dict(request_artifact),
        "02_response.json": dict(response),
        "03_usage.json": dict(usage_record),
        "04_attempts.json": {
            "schema_version": "z91-immutable-attempt-set-v1",
            "rows": [dict(row) for row in attempt_rows],
        },
    }
    references: dict[str, Any] = {}
    for filename, value in payloads.items():
        raw = json_bytes(value)
        write_bytes_exclusive(root / filename, raw)
        references[filename] = model_benchmark.sha256_bytes(raw)
    raw_path = Path(str(mechanical["raw_response_path"]))
    seal_preimage = {
        "schema_version": "z91-immutable-checkpoint-seal-v1",
        "contract_version": CONTRACT_VERSION,
        "sample_id": request_artifact["sample_id"],
        "logical_request_id": request_artifact["logical_request_id"],
        "mechanical_verdict": verdict,
        "artifacts": references,
        "mechanical_path": "mechanical.json",
        "mechanical_sha256": sha256_file(sample_root / "mechanical.json"),
        "raw_response_path": raw_path.as_posix(),
        "raw_response_sha256": mechanical["raw_response_sha256"],
        "sealed": True,
    }
    seal = {**seal_preimage, "checkpoint_id": canonical_sha(seal_preimage)}
    write_json_exclusive(root / "05_seal.json", seal)
    validate_checkpoint(sample_root)
    return seal


def validate_checkpoint(sample_root: Path) -> dict[str, Any]:
    root = sample_root / "checkpoint"
    names = {
        "01_request.json",
        "02_response.json",
        "03_usage.json",
        "04_attempts.json",
        "05_seal.json",
    }
    if not root.is_dir() or {path.name for path in root.iterdir()} != names:
        raise ZBatchError("Z91 不可变检查点五件不齐或夹入第六件")
    seal = read_json(root / "05_seal.json")
    checkpoint_id = seal.get("checkpoint_id")
    preimage = {key: value for key, value in seal.items() if key != "checkpoint_id"}
    if not _is_sha256(checkpoint_id) or checkpoint_id != canonical_sha(preimage):
        raise ZBatchError("Z91 检查点 ID 不能由本体重建")
    if (
        seal.get("schema_version") != "z91-immutable-checkpoint-seal-v1"
        or seal.get("contract_version") != CONTRACT_VERSION
        or seal.get("mechanical_verdict") not in {"pass", "fail"}
        or seal.get("sealed") is not True
    ):
        raise ZBatchError("Z91 检查点身份或判词漂移")
    refs = seal.get("artifacts")
    if not isinstance(refs, Mapping) or set(refs) != names - {"05_seal.json"}:
        raise ZBatchError("Z91 检查点四件引用不完整")
    for filename, expected in refs.items():
        if not _is_sha256(expected) or sha256_file(root / filename) != expected:
            raise ZBatchError(f"Z91 检查点引用漂移：{filename}")
    mechanical = sample_root / str(seal.get("mechanical_path") or "")
    raw = sample_root / str(seal.get("raw_response_path") or "")
    if (
        not mechanical.is_file()
        or sha256_file(mechanical) != seal.get("mechanical_sha256")
        or not raw.is_file()
        or sha256_file(raw) != seal.get("raw_response_sha256")
    ):
        raise ZBatchError("Z91 检查点没有绑定机械票或原始响应")
    return seal


def _usage_record(
    sample: Mapping[str, Any],
    request_sha: str,
    raw_sha: str,
    usage: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "z91-sample-usage-v1",
        "sample_id": sample["sample_id"],
        "logical_request_id": sample["logical_request_id"],
        "request_artifact_sha256": request_sha,
        "raw_response_sha256": raw_sha,
        "usage": dict(usage),
    }


def _validate_usage(usage: Mapping[str, Any]) -> None:
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise Z91RunHardStop("usage_contract", f"成功响应缺合法 {field}")
    if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
        raise Z91RunHardStop("usage_contract", "usage 总 token 不能由输入与输出相加重建")


def _mechanical_pass(
    sample_root: Path,
    sample: Mapping[str, Any],
    response: Mapping[str, Any],
    raw_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    model_data, content, reasoning, finish = model_benchmark.response_envelope(
        response,
        str(sample["model"]),
        require_nonempty_reasoning=bool(sample["require_reasoning"]),
    )
    if response.get("model") != sample["model"]:
        raise Z91RunHardStop(
            "response_model_mismatch",
            f"响应型号 {response.get('model')!r} 不是冻结精确型号 {sample['model']}",
        )
    catalog_doc = read_json(
        sample_root.parents[1]
        / f"inputs/cases/{sample['case_key']}/evidence_catalog.json"
    )
    catalog = catalog_doc.get("entries") if isinstance(catalog_doc, Mapping) else None
    if not isinstance(catalog, list):
        raise Z91RunHardStop("catalog_contract", "冻结证据目录缺 entries")
    reasons, program_audit = neutral_extract.audit_event_envelope(
        model_data, int(sample["chapter"]), catalog
    )
    if reasons:
        reason_code = (
            "structure_overreach"
            if any("字段" in reason or "外壳" in reason for reason in reasons)
            else "mechanical_contract"
        )
        raise Z91RunHardStop(
            reason_code,
            f"{sample['sample_id']} 机械合同失败：{reasons}；不做补跑或修补",
        )
    materialized = neutral_extract.materialize_events(
        model_data, catalog, int(sample["chapter"])
    )
    mechanical = {
        "schema_version": "z91-mechanical-three-gates-v1",
        "status": "pass",
        "sample_id": sample["sample_id"],
        "json_and_schema_gate": True,
        "catalog_anchor_gate": len(program_audit["missing_catalog_anchor_ids"]) == 0,
        "length_and_contiguous_id_gate": (
            finish == "stop"
            and program_audit["event_ids_contiguous"]
            and program_audit["invalid_event_id_count"] == 0
        ),
        "event_count": program_audit["event_count"],
        "anchor_reference_count": program_audit["anchor_reference_count"],
        "outside_catalog_anchor_count": len(program_audit["missing_catalog_anchor_ids"]),
        "invalid_event_id_count": program_audit["invalid_event_id_count"],
        "events_without_anchors": program_audit["events_without_anchors"],
        "finish_reason": finish,
        "response_model": response.get("model"),
        "content_sha256": model_benchmark.sha256_bytes(content.encode("utf-8")),
        "reasoning_content_sha256": model_benchmark.sha256_bytes(
            reasoning.encode("utf-8")
        ),
        "raw_response_path": raw_path.relative_to(sample_root).as_posix(),
        "raw_response_sha256": sha256_file(raw_path),
    }
    if not all(
        mechanical[field]
        for field in (
            "json_and_schema_gate",
            "catalog_anchor_gate",
            "length_and_contiguous_id_gate",
        )
    ):
        raise Z91RunHardStop("mechanical_gate", "机械三闸没有全过")
    return model_data, materialized, program_audit, mechanical


def _mechanical_fail(
    sample_root: Path,
    sample: Mapping[str, Any],
    response: Mapping[str, Any],
    raw_path: Path,
    error: BaseException,
) -> dict[str, Any]:
    finish: Any = None
    choices = response.get("choices")
    if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], Mapping):
        finish = choices[0].get("finish_reason")
    return {
        "schema_version": "z91-mechanical-three-gates-v1",
        "status": "fail_hard_stop_no_rerun",
        "sample_id": sample["sample_id"],
        "json_and_schema_gate": False,
        "catalog_anchor_gate": False,
        "length_and_contiguous_id_gate": False,
        "finish_reason": finish,
        "response_model": response.get("model"),
        "reason_code": getattr(error, "reason_code", "mechanical_contract"),
        "error_type": type(error).__name__,
        "message": str(error),
        "raw_response_path": raw_path.relative_to(sample_root).as_posix(),
        "raw_response_sha256": sha256_file(raw_path),
    }


def _sample_completion(
    sample: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    usage: Mapping[str, Any],
    mechanical: Mapping[str, Any],
    seal: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "z91-sample-completion-v1",
        "status": "sample_completed_mechanical_pass_awaiting_blind_review",
        "sample_id": sample["sample_id"],
        "logical_request_id": sample["logical_request_id"],
        "case_key": sample["case_key"],
        "chapter": sample["chapter"],
        "arm_id": sample["arm_id"],
        "provider": sample["provider"],
        "model": sample["model"],
        "logical_samples": 1,
        "network_attempts": len(attempts),
        "429_count": sum(1 for row in attempts if row.get("http_status") == 429),
        "usage": dict(usage),
        "event_count": mechanical["event_count"],
        "mechanical_three_gates": "pass",
        "checkpoint_id": seal["checkpoint_id"],
        "deepseek_official_api_used": False,
    }


def _write_sample_hard_stop(
    sample_root: Path, sample: Mapping[str, Any], error: BaseException
) -> None:
    path = sample_root / "hard_stop.json"
    if path.exists():
        return
    write_json_exclusive(
        path,
        {
            "schema_version": "z91-sample-hard-stop-v1",
            "status": "hard_stop_no_rerun_no_patch",
            "sample_id": sample["sample_id"],
            "logical_request_id": sample["logical_request_id"],
            "reason_code": getattr(error, "reason_code", "sample_failure"),
            "error_type": type(error).__name__,
            "message": str(error),
            "rerun_allowed": False,
            "stopped_at": now_iso(),
        },
    )


def _execute_sample(
    run_dir: Path,
    sample: Mapping[str, Any],
    provider: Mapping[str, Any],
    key: str,
    *,
    state: z83_retry_transport.RetryRunState,
    policy: z83_retry_transport.RetryPolicy,
    opener: Any,
    sleeper: Callable[[float], None] | None,
    monotonic: Callable[[], float] | None,
    jitter: Callable[[], float] | None,
) -> dict[str, Any]:
    sample_root = run_dir / f"samples/{sample['sample_id']}"
    prepared_root = run_dir / f"prepared/samples/{sample['sample_id']}"
    artifact_path = prepared_root / "request_artifact.json"
    body_path = prepared_root / "request_body.json"
    artifact = read_json(artifact_path)
    body = read_json(body_path)
    request_path = sample_root / "transport/request.json"
    write_bytes_exclusive(request_path, artifact_path.read_bytes())
    request_sha = sha256_file(request_path)
    wire = json.dumps(body, ensure_ascii=False).encode("utf-8")
    wire_sha = model_benchmark.sha256_bytes(wire)
    if key.encode("utf-8") in request_path.read_bytes():
        raise Z91RunHardStop("secret_in_request_artifact", "请求工件意外含 API Key")
    ledger = sample_root / "transport/call_attempts.jsonl"
    try:
        logical = z83_retry_transport.run_logical_request(
            logical_request_id=str(sample["logical_request_id"]),
            chapter=int(sample["chapter"]),
            send_once=model_benchmark.send_once_factory(
                root=sample_root,
                provider=provider,
                key=key,
                logical_request_id=str(sample["logical_request_id"]),
                request_sha=request_sha,
                wire_body=wire,
                wire_sha=wire_sha,
                opener=opener,
            ),
            attempt_ledger_path=ledger,
            contract_version=CONTRACT_VERSION,
            state=state,
            policy=policy,
            sleeper=sleeper,
            monotonic=monotonic,
            jitter=jitter,
        )
    except z83_retry_transport.RetryTransportHardStop as exc:
        error = Z91RunHardStop(exc.reason_code, str(exc))
        _write_sample_hard_stop(sample_root, sample, error)
        raise error from exc

    payload = logical.outcome.payload
    response = payload.get("response_json") if isinstance(payload, Mapping) else None
    raw_path = payload.get("raw_path") if isinstance(payload, Mapping) else None
    if (
        not isinstance(payload, Mapping)
        or payload.get("envelope_error")
        or not isinstance(response, Mapping)
        or not isinstance(raw_path, Path)
    ):
        error = Z91RunHardStop("response_envelope", "HTTP 200 响应外壳不能解析")
        _write_sample_hard_stop(sample_root, sample, error)
        raise error
    attempts = list(logical.attempt_rows)
    usage = dict(logical.outcome.usage or {})
    try:
        _validate_usage(usage)
        model_data, materialized, program_audit, mechanical = _mechanical_pass(
            sample_root, sample, response, raw_path
        )
    except (model_benchmark.BenchmarkHardStop, Z91RunHardStop, ZBatchError) as exc:
        reason = getattr(exc, "reason_code", "mechanical_contract")
        error = exc if isinstance(exc, Z91RunHardStop) else Z91RunHardStop(reason, str(exc))
        mechanical = _mechanical_fail(sample_root, sample, response, raw_path, error)
        write_json_exclusive(sample_root / "mechanical.json", mechanical)
        usage_record = _usage_record(
            sample, request_sha, sha256_file(raw_path), usage
        )
        write_json_exclusive(sample_root / "transport/usage.json", usage_record)
        _write_checkpoint(
            sample_root,
            request_artifact=artifact,
            response=response,
            usage_record=usage_record,
            attempt_rows=attempts,
            mechanical=mechanical,
            verdict="fail",
        )
        _write_sample_hard_stop(sample_root, sample, error)
        raise error from exc

    write_json_exclusive(sample_root / "candidate/model_json.json", model_data)
    write_json_exclusive(sample_root / "candidate/neutral_events.json", materialized)
    write_json_exclusive(sample_root / "candidate/program_audit.json", program_audit)
    write_json_exclusive(sample_root / "mechanical.json", mechanical)
    usage_record = _usage_record(sample, request_sha, sha256_file(raw_path), usage)
    write_json_exclusive(sample_root / "transport/usage.json", usage_record)
    seal = _write_checkpoint(
        sample_root,
        request_artifact=artifact,
        response=response,
        usage_record=usage_record,
        attempt_rows=attempts,
        mechanical=mechanical,
        verdict="pass",
    )
    completion = _sample_completion(sample, attempts, usage, mechanical, seal)
    write_json_exclusive(sample_root / "completion.json", completion)
    return completion


def _network_summary(run_dir: Path) -> tuple[int, int, int]:
    rows = [
        row
        for sample in sample_specs()
        for row in _attempt_rows(
            run_dir
            / f"samples/{sample['sample_id']}/transport/call_attempts.jsonl"
        )
    ]
    logical = {str(row.get("logical_request_id")) for row in rows}
    return len(rows), len(logical), sum(1 for row in rows if row.get("http_status") == 429)


def _write_global_hard_stop(
    run_dir: Path,
    error: BaseException,
    *,
    catalog_network_attempts: int,
) -> dict[str, Any]:
    path = run_dir / "hard_stop.json"
    if path.exists():
        return read_json(path)
    attempts, logical, count_429 = _network_summary(run_dir)
    receipt = {
        "schema_version": "z91-step2-hard-stop-v1",
        "status": "hard_stop_no_rerun_no_patch",
        "reason_code": getattr(error, "reason_code", "run_failure"),
        "error_type": type(error).__name__,
        "message": str(error),
        "model_api_logical_samples_started": logical,
        "model_api_network_attempts": attempts,
        "catalog_network_attempts": catalog_network_attempts,
        "429_count": count_429,
        "deepseek_official_api_used": False,
        "automatic_fallback_used": False,
        "rerun_allowed": False,
        "stopped_at": now_iso(),
    }
    write_json_exclusive(path, receipt)
    return receipt


def _run_claim(
    run_dir: Path, source_fact_seal_sha256: str
) -> dict[str, Any]:
    return {
        "schema_version": "z91-six-sample-run-claim-v1",
        "status": "six_samples_claimed_no_rerun",
        "run_id": run_dir.name,
        "sample_ids": [sample["sample_id"] for sample in sample_specs()],
        "logical_request_ids": [
            sample["logical_request_id"] for sample in sample_specs()
        ],
        "sample_count": 6,
        "single_sample_per_arm_per_case": True,
        "source_fact_seal_sha256": source_fact_seal_sha256,
        "tencent_provider": "config/providers/tencent_tokenhub_multi_model.json",
        "tencent_exact_model": PRO_MODEL,
        "tencent_catalog_gate": "pass_exact_model_online",
        "automatic_fallback": False,
        "deepseek_official_api_used": False,
        "claimed_at": now_iso(),
    }


def _completion_document(
    run_dir: Path,
    completions: Sequence[Mapping[str, Any]],
    source_fact_seal_sha256: str,
    scan: Mapping[str, Any],
) -> dict[str, Any]:
    attempts = sum(int(row["network_attempts"]) for row in completions)
    count_429 = sum(int(row["429_count"]) for row in completions)
    total_tokens = sum(int(row["usage"]["total_tokens"]) for row in completions)
    checkpoints = {str(row["sample_id"]): row["checkpoint_id"] for row in completions}
    usage = {str(row["sample_id"]): row["usage"] for row in completions}
    return {
        "schema_version": "z91-step2-completion-v1",
        "status": "six_samples_mechanical_pass_awaiting_blind_semantic_review",
        "run_id": run_dir.name,
        "logical_samples": 6,
        "model_api_network_attempts": attempts,
        "catalog_network_attempts": 1,
        "429_count": count_429,
        "mechanical_three_gates": "pass_6_of_6",
        "sample_ids": [row["sample_id"] for row in completions],
        "usage_by_sample": usage,
        "total_tokens": total_tokens,
        "checkpoint_ids": checkpoints,
        "source_fact_seal_sha256": source_fact_seal_sha256,
        "secret_scan": dict(scan),
        "automatic_fallback_used": False,
        "deepseek_official_api_used": False,
        "semantic_result": "not_scored",
        "completed_at": now_iso(),
    }


def run(
    run_dir: Path,
    *,
    opener: Any = None,
    catalog_opener: Any = None,
    policy: z83_retry_transport.RetryPolicy | None = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    jitter: Callable[[], float] | None = None,
) -> dict[str, Any]:
    verify_prepared(run_dir)
    if (run_dir / "hard_stop.json").exists():
        raise ZBatchError("第91道步二已经硬停，禁止复跑或捞回旧响应")
    if (run_dir / "transport/run_claim.json").exists():
        raise ZBatchError("六份正式调用票已经占用，禁止再次采样")
    if (run_dir / "transport").exists() and any((run_dir / "transport").iterdir()):
        raise ZBatchError("运行目录已有运输工件，拒绝重复目录闸或采样")

    providers = _load_frozen_providers(run_dir)
    keys: dict[str, str] = {}
    for arm in ARMS:
        key = os.environ.get(str(arm["key_env"]), "")
        if not key:
            raise ZBatchError(f"缺少 {arm['key_env']}；尚未查询目录或占用六样本")
        keys[str(arm["provider"])] = key
    tencent = providers["tencent_tokenhub"]
    try:
        model_benchmark.verify_provider_model_catalog(
            run_dir,
            tencent,
            PRO_MODEL,
            keys["tencent_tokenhub"],
            opener=catalog_opener,
        )
        model_benchmark.audit_provider_model_catalog(run_dir, tencent, PRO_MODEL)
    except (model_benchmark.BenchmarkHardStop, ZBatchError) as exc:
        reason = getattr(exc, "reason_code", "model_catalog_audit")
        error = Z91RunHardStop(reason, str(exc))
        _write_global_hard_stop(run_dir, error, catalog_network_attempts=1)
        raise error from exc

    pin = read_json(run_dir / "provenance/source_fact_seal_pin.json")
    seal_sha = str(pin["source_fact_seal_sha256"])
    write_json_exclusive(run_dir / "transport/run_claim.json", _run_claim(run_dir, seal_sha))
    state = z83_retry_transport.RetryRunState()
    active_policy = policy or z83_retry_transport.RetryPolicy()
    completions: list[dict[str, Any]] = []
    try:
        for sample in sample_specs():
            completions.append(
                _execute_sample(
                    run_dir,
                    sample,
                    providers[str(sample["provider"])],
                    keys[str(sample["provider"])],
                    state=state,
                    policy=active_policy,
                    opener=opener,
                    sleeper=sleeper,
                    monotonic=monotonic,
                    jitter=jitter,
                )
            )
    except (Z91RunHardStop, ZBatchError) as exc:
        error = exc if isinstance(exc, Z91RunHardStop) else Z91RunHardStop(
            "sample_failure", str(exc)
        )
        _write_global_hard_stop(run_dir, error, catalog_network_attempts=1)
        raise error from exc

    scan = secret_scan(run_dir, tuple(keys.values()))
    if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
        error = Z91RunHardStop("secret_trace_detected", "步二目录检出密钥或鉴权头")
        _write_global_hard_stop(run_dir, error, catalog_network_attempts=1)
        raise error
    completion = _completion_document(run_dir, completions, seal_sha, scan)
    write_json_exclusive(run_dir / "completion.json", completion)
    audit_completed(run_dir)
    return completion


def _validate_reservations(
    reservations: Sequence[Mapping[str, Any]], attempts: Sequence[Mapping[str, Any]]
) -> None:
    if len(reservations) != len(attempts):
        raise ZBatchError("尝试占用票与真实尝试数不一致")
    for reservation, attempt in zip(reservations, attempts, strict=True):
        preimage = {
            key: value for key, value in reservation.items() if key != "row_sha256"
        }
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


def _audit_sample(run_dir: Path, sample: Mapping[str, Any]) -> dict[str, Any]:
    sample_root = run_dir / f"samples/{sample['sample_id']}"
    if (sample_root / "hard_stop.json").exists():
        raise ZBatchError(f"{sample['sample_id']} 已硬停，不能审计成完成态")
    artifact_path = run_dir / f"prepared/samples/{sample['sample_id']}/request_artifact.json"
    body_path = run_dir / f"prepared/samples/{sample['sample_id']}/request_body.json"
    request_path = sample_root / "transport/request.json"
    if request_path.read_bytes() != artifact_path.read_bytes():
        raise ZBatchError(f"{sample['sample_id']} 实发请求工件与冻结件不一致")
    request_sha = sha256_file(request_path)
    body = read_json(body_path)
    wire_sha = model_benchmark.sha256_bytes(
        json.dumps(body, ensure_ascii=False).encode("utf-8")
    )
    attempts = _attempt_rows(sample_root / "transport/call_attempts.jsonl")
    z83_retry_transport.validate_attempt_rows(attempts)
    z83_retry_transport.validate_retry_wait_sequence(
        sample_root / "transport/call_attempts.jsonl",
        attempts,
        require_all_429_completed=True,
    )
    reservations = _attempt_rows(sample_root / "transport/attempt_reservations.jsonl")
    _validate_reservations(reservations, attempts)
    successes = [row for row in attempts if row.get("outcome") == "success"]
    if len(successes) != 1 or successes[0].get("http_status") != 200:
        raise ZBatchError(f"{sample['sample_id']} 完成态没有唯一 HTTP 200")
    success = successes[0]
    if (
        success.get("request_artifact_sha256") != request_sha
        or success.get("wire_body_sha256") != wire_sha
    ):
        raise ZBatchError(f"{sample['sample_id']} 尝试账请求 SHA 漂移")
    raw_path = sample_root / f"transport/raw_responses/attempt{int(success['attempt']):02d}.json"
    if not raw_path.is_file() or sha256_file(raw_path) != success.get("raw_response_sha256"):
        raise ZBatchError(f"{sample['sample_id']} 原始响应缺失或 SHA 漂移")
    response = read_json(raw_path)
    model_data, materialized, program_audit, mechanical = _mechanical_pass(
        sample_root, sample, response, raw_path
    )
    usage = success.get("usage")
    if not isinstance(usage, Mapping):
        raise ZBatchError(f"{sample['sample_id']} 成功尝试缺 usage")
    _validate_usage(usage)
    expected_usage = _usage_record(sample, request_sha, sha256_file(raw_path), usage)
    comparisons = {
        "candidate/model_json.json": model_data,
        "candidate/neutral_events.json": materialized,
        "candidate/program_audit.json": program_audit,
        "mechanical.json": mechanical,
        "transport/usage.json": expected_usage,
    }
    for relative, expected in comparisons.items():
        if read_json(sample_root / relative) != expected:
            raise ZBatchError(f"{sample['sample_id']} 不能从原始响应重建：{relative}")
    checkpoint = validate_checkpoint(sample_root)
    checkpoint_request = read_json(sample_root / "checkpoint/01_request.json")
    checkpoint_response = read_json(sample_root / "checkpoint/02_response.json")
    checkpoint_usage = read_json(sample_root / "checkpoint/03_usage.json")
    checkpoint_attempts = read_json(sample_root / "checkpoint/04_attempts.json")
    if (
        checkpoint_request != read_json(artifact_path)
        or checkpoint_response != response
        or checkpoint_usage != expected_usage
        or checkpoint_attempts
        != {"schema_version": "z91-immutable-attempt-set-v1", "rows": attempts}
        or checkpoint.get("mechanical_verdict") != "pass"
    ):
        raise ZBatchError(f"{sample['sample_id']} 五件套不能由原始证据重建")
    expected_completion = _sample_completion(
        sample, attempts, usage, mechanical, checkpoint
    )
    if read_json(sample_root / "completion.json") != expected_completion:
        raise ZBatchError(f"{sample['sample_id']} 完成票不能由原始证据重建")
    return expected_completion


def audit_completed(run_dir: Path) -> dict[str, Any]:
    """从六份原始响应、usage 与尝试账重建完成态，不复用旧判词。"""

    verify_prepared(run_dir)
    if (run_dir / "hard_stop.json").exists():
        raise ZBatchError("步二已硬停，禁止审计成六样本完成态")
    completion_path = run_dir / "completion.json"
    claim_path = run_dir / "transport/run_claim.json"
    if not completion_path.is_file() or not claim_path.is_file():
        raise ZBatchError("六样本尚未完成或尚未占用")
    providers = _load_frozen_providers(run_dir)
    model_benchmark.audit_provider_model_catalog(
        run_dir, providers["tencent_tokenhub"], PRO_MODEL
    )
    pin = read_json(run_dir / "provenance/source_fact_seal_pin.json")
    seal_path = _stored_path(str(pin["source_fact_seal_path"]))
    seal_audit = validate_source_fact_seal(seal_path)
    if seal_audit["seal_sha256"] != pin.get("source_fact_seal_sha256"):
        raise ZBatchError("source fact seal 在 prepare 后漂移")
    claim = read_json(claim_path)
    expected_claim = _run_claim(run_dir, seal_audit["seal_sha256"])
    for field, expected in expected_claim.items():
        if field != "claimed_at" and claim.get(field) != expected:
            raise ZBatchError(f"六样本占用票字段漂移：{field}")
    if set(claim) != set(expected_claim) or not isinstance(claim.get("claimed_at"), str):
        raise ZBatchError("六样本占用票字段集合或时间漂移")

    completions = [_audit_sample(run_dir, sample) for sample in sample_specs()]
    stored_completion = read_json(completion_path)
    stored_scan = stored_completion.get("secret_scan")
    if stored_scan != {
        "exact_key_hits": [],
        "exact_key_hit_count": 0,
        "authorization_header_hits": [],
        "authorization_header_hit_count": 0,
    }:
        raise ZBatchError("完成票没有证明两把密钥零痕迹")
    expected_completion = _completion_document(
        run_dir,
        completions,
        seal_audit["seal_sha256"],
        stored_scan,
    )
    for field, expected in expected_completion.items():
        if field != "completed_at" and stored_completion.get(field) != expected:
            raise ZBatchError(f"六样本完成票不能重建：{field}")
    if set(stored_completion) != set(expected_completion) or not isinstance(
        stored_completion.get("completed_at"), str
    ):
        raise ZBatchError("六样本完成票字段集合或时间漂移")
    scan = secret_scan(run_dir)
    if scan["authorization_header_hit_count"]:
        raise ZBatchError("完成目录出现 Authorization 字段")
    receipt = {
        "schema_version": "z91-step2-completion-audit-v1",
        "status": "pass_rebuilt_from_raw_response_usage_attempts",
        "run_id": run_dir.name,
        "logical_samples": 6,
        "model_api_network_attempts": expected_completion[
            "model_api_network_attempts"
        ],
        "catalog_network_attempts": 1,
        "mechanical_three_gates": "pass_6_of_6",
        "checkpoint_ids": expected_completion["checkpoint_ids"],
        "source_fact_seal_sha256": seal_audit["seal_sha256"],
        "secret_authorization_hits": 0,
        "deepseek_official_api_used": False,
    }
    path = run_dir / "audit/completion_audit.json"
    if path.exists():
        if read_json(path) != receipt:
            raise ZBatchError("既有步二审计票与原始证据重建结果不一致")
    else:
        write_json_exclusive(path, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="零调用冻结六样本运行件")
    prepare_parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    prepare_parser.add_argument("--source-fact-seal", type=Path, required=True)
    run_parser = subparsers.add_parser("run", help="目录闸通过后占用并发送六样本")
    run_parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    audit_parser = subparsers.add_parser("audit", help="从原始响应和 usage 重建验收")
    audit_parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.run_dir.resolve(), args.source_fact_seal.resolve())
    elif args.command == "run":
        result = run(args.run_dir.resolve())
    else:
        result = audit_completed(args.run_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
