#!/usr/bin/env python3
"""C13 三家接收端的零调用 wire 适配冻结件。

本文件只渲染 HTTP JSON body 与响应验收合同，不包含网络发送能力。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[3]
SOURCE_R02 = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C13_downstream_consumer_r02_20260726"
)
OUTPUT_DIR = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C13_downstream_consumer_wire_r03_20260726"
)
REPORT_DIR = ROOT / "reports/抽取工序重设计v0.2_C13三通道运输外壳_r03_20260726"

EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "aaf69c7c6f53a21b864580558de5398e0314154a0e96f5869af70556e42c9344"
)
EXPECTED_SOURCE_ARTIFACT_SET_SHA256 = (
    "d20c194fec453fc3c55a09b7088c59b7435d23118f0207ba6f8a8f8af6e19c9c"
)
EXPECTED_PROMPT_SET_SHA256 = (
    "1302b5fbda68f0b525d2e32267cd2084a1032be1d8a8335a92f869a451570b3f"
)

PROVIDER_CONFIGS = {
    "qianwen_platform": ROOT / "config/providers/qianwen_platform_multi_model.json",
    "volcengine_ark": ROOT / "config/providers/volcengine_ark_multi_model.json",
    "tencent_tokenhub": ROOT / "config/providers/tencent_tokenhub_multi_model.json",
}

WIRE_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "provider_id": "qianwen_platform",
        "model_id": "qwen3.7-max-2026-05-20",
        "role": "PRIMARY_READOUT",
        "timeout_seconds": 600,
        "body_fields": {
            "temperature": 0.2,
            "stream": False,
            "enable_thinking": True,
            "thinking_budget": 32768,
        },
        "allowed_body_fields": [
            "model",
            "messages",
            "temperature",
            "stream",
            "enable_thinking",
            "thinking_budget",
        ],
        "explicitly_omitted_fields": [
            "n",
            "max_tokens",
            "max_completion_tokens",
            "response_format",
            "reasoning_effort",
            "preserve_thinking",
            "tools",
            "tool_choice",
        ],
        "thinking_contract": (
            "EXPLICIT_ENABLE_THINKING_WITH_32768_REASONING_TOKEN_GUARD"
        ),
        "response_reasoning_path": "choices[0].message.reasoning_content",
        "field_evidence": [
            {
                "url": (
                    "https://platform.qianwenai.com/docs/"
                    "developer-guides/text-generation/thinking"
                ),
                "supports": [
                    "qwen3.7-max-2026-05-20",
                    "model",
                    "messages",
                    "temperature",
                    "stream",
                    "enable_thinking",
                    "thinking_budget",
                ],
            },
            {
                "path": (
                    "experiments/model_benchmarks/"
                    "MB_X01_C0003_qianwen_qwen3.7-plus_"
                    "thinking32k_t02_r06_20260723/transport/request.json"
                ),
                "scope": (
                    "只证明同平台 Qwen3.7 Plus 的非流式思考字段曾实跑；"
                    "不冒充 Max 固定版已完成兼容实调。"
                ),
            },
        ],
    },
    {
        "provider_id": "volcengine_ark",
        "model_id": "doubao-seed-2-1-pro-260628",
        "role": "REPLICATION",
        "timeout_seconds": 1800,
        "body_fields": {
            "temperature": 0.2,
            "stream": False,
            "max_tokens": 32768,
            "thinking": {"type": "enabled"},
        },
        "allowed_body_fields": [
            "model",
            "messages",
            "temperature",
            "stream",
            "max_tokens",
            "thinking",
        ],
        "explicitly_omitted_fields": [
            "n",
            "max_completion_tokens",
            "response_format",
            "reasoning_effort",
            "tools",
            "tool_choice",
        ],
        "thinking_contract": "EXPLICIT_THINKING_TYPE_ENABLED",
        "response_reasoning_path": "choices[0].message.reasoning_content",
        "field_evidence": [
            {
                "url": (
                    "https://api.volcengine.com/api-docs/view?"
                    "action=ChatCompletions&serviceCode=ark&version=2024-01-01"
                ),
                "supports": [
                    "model",
                    "messages",
                    "temperature",
                    "thinking",
                    "stream",
                    "max_tokens",
                ],
            },
            {
                "url": "https://www.volcengine.com/docs/82379/1449737",
                "supports": ["thinking.type=enabled"],
            },
            {
                "path": "config/providers/volcengine_ark_multi_model.json",
                "supports": ["doubao-seed-2-1-pro-260628"],
                "scope": (
                    "精确型号只作静态准入；首个真实响应仍须核 response.model，"
                    "不冒充已完成兼容实调。"
                ),
            },
        ],
    },
    {
        "provider_id": "tencent_tokenhub",
        "model_id": "minimax-m3",
        "role": "REPLICATION",
        "timeout_seconds": 600,
        "body_fields": {
            "temperature": 0.2,
            "stream": False,
            "max_tokens": 32768,
            "reasoning_split": True,
        },
        "allowed_body_fields": [
            "model",
            "messages",
            "temperature",
            "stream",
            "max_tokens",
            "reasoning_split",
        ],
        "explicitly_omitted_fields": [
            "n",
            "thinking",
            "response_format",
            "reasoning_effort",
            "tools",
            "tool_choice",
        ],
        "thinking_contract": (
            "MODEL_DEFAULT_ADAPTIVE_THINKING_WITH_SEPARATE_REASONING_FIELD"
        ),
        "response_reasoning_path": "choices[0].message.reasoning_content",
        "field_evidence": [
            {
                "url": "https://cloud.tencent.com/document/product/1823/132246",
                "supports": [
                    "minimax-m3",
                    "model",
                    "messages",
                    "temperature",
                    "stream",
                    "adaptive_thinking_by_default",
                    "max_tokens",
                    "reasoning_split",
                    "reasoning_content",
                ],
            },
            {
                "path": "config/providers/tencent_tokenhub_multi_model.json",
                "supports": ["minimax-m3"],
                "scope": (
                    "正式运行前仍须 fresh /v1/models 精确 online 票；"
                    "历史目录不能替代当前票。"
                ),
            },
        ],
    },
)


class WireFreezeError(RuntimeError):
    """C13 wire 冻结件不满足机械合同。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WireFreezeError(f"JSON 读取失败：{path}") from exc


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _verify_source_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise WireFreezeError("C13 r02 工件清单没有逐文件记录")
    expected: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise WireFreezeError("C13 r02 工件清单行格式错误")
        relative = row.get("path")
        digest = row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative == "artifact_manifest.json"
            or relative in expected
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise WireFreezeError("C13 r02 工件清单行不唯一或字段非法")
        expected[relative] = digest
    actual = {
        path.relative_to(SOURCE_R02).as_posix()
        for path in SOURCE_R02.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    }
    if actual != set(expected):
        raise WireFreezeError(
            "C13 r02 工件集合不闭合："
            f"missing={sorted(set(expected) - actual)} "
            f"unexpected={sorted(actual - set(expected))}"
        )
    for relative, digest in expected.items():
        if sha256_file(SOURCE_R02 / relative) != digest:
            raise WireFreezeError(f"C13 r02 实物 SHA 漂移：{relative}")
    rebuilt_set_sha256 = sha256_bytes(canonical_bytes(expected))
    if rebuilt_set_sha256 != EXPECTED_SOURCE_ARTIFACT_SET_SHA256:
        raise WireFreezeError("C13 r02 逐文件重建集合 SHA 漂移")
    return {
        "verified_file_total": len(expected),
        "rebuilt_artifact_set_sha256": rebuilt_set_sha256,
    }


def _load_source() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest_path = SOURCE_R02 / "artifact_manifest.json"
    if sha256_file(manifest_path) != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise WireFreezeError("C13 r02 工件清单 SHA 漂移")
    manifest = read_json(manifest_path)
    if (
        manifest.get("artifact_set_sha256")
        != EXPECTED_SOURCE_ARTIFACT_SET_SHA256
    ):
        raise WireFreezeError("C13 r02 工件集合 SHA 漂移")
    source_verification = _verify_source_manifest(manifest)
    prompt_bundle = read_json(
        SOURCE_R02 / "prompt_review/exact_visible_messages.json"
    )
    if prompt_bundle.get("prompt_set_sha256") != EXPECTED_PROMPT_SET_SHA256:
        raise WireFreezeError("C13 r02 题面集合 SHA 漂移")
    dispatch = read_json(SOURCE_R02 / "plans/provider_dispatch_plan.json")
    return prompt_bundle, dispatch, source_verification


def _validated_profiles() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in WIRE_PROFILES:
        provider_id = str(profile["provider_id"])
        config_path = PROVIDER_CONFIGS[provider_id]
        config = read_json(config_path)
        exact = [
            row
            for row in config.get("models", [])
            if isinstance(row, Mapping)
            and row.get("model_id") == profile["model_id"]
            and row.get("call_ready") is True
        ]
        if len(exact) != 1:
            raise WireFreezeError(
                f"{provider_id} 精确型号未唯一静态准入：{profile['model_id']}"
            )
        actual_fields = {
            "model",
            "messages",
            *profile["body_fields"].keys(),
        }
        allowed_fields = set(profile["allowed_body_fields"])
        if actual_fields != allowed_fields:
            raise WireFreezeError(
                f"{provider_id} 字段白名单与实际渲染字段不一致"
            )
        if allowed_fields & set(profile["explicitly_omitted_fields"]):
            raise WireFreezeError(f"{provider_id} 发送字段误入显式禁发清单")
        evidenced_fields = {
            str(field)
            for evidence in profile["field_evidence"]
            if isinstance(evidence, Mapping)
            for field in evidence.get("supports", [])
        }
        missing_evidence = allowed_fields - evidenced_fields
        if missing_evidence:
            raise WireFreezeError(
                f"{provider_id} 发送字段缺静态证据指针："
                f"{sorted(missing_evidence)}"
            )
        rows.append(
            {
                **profile,
                "provider_config_path": display_path(config_path),
                "provider_config_sha256": sha256_file(config_path),
                "base_url": config["base_url"],
                "endpoint": config["endpoint"],
                "api_key_env": config["api_key_env"],
                "enabled_by_default": config.get("enabled_by_default"),
                "automatic_fallback_allowed": False,
                "wire_adapter_zero_call_render_passed": True,
                "field_evidence_coverage_passed": True,
                "field_evidence_snapshot_frozen": False,
                "live_catalog_or_identity_gate_passed": False,
            }
        )
    return rows


def build_artifacts() -> dict[str, bytes]:
    prompt_bundle, dispatch, source_verification = _load_source()
    profiles = _validated_profiles()
    prompt_by_call = {
        row["call_id"]: row
        for row in prompt_bundle.get("rows", [])
        if isinstance(row, Mapping)
    }
    if len(prompt_by_call) != 30:
        raise WireFreezeError("C13 r02 精确题面不是 30 份")
    dispatch_nodes = dispatch.get("dispatch_nodes")
    if not isinstance(dispatch_nodes, list) or len(dispatch_nodes) != 90:
        raise WireFreezeError("C13 r02 私有调度位不是 90")
    profile_by_provider = {
        row["provider_id"]: row for row in profiles
    }

    artifacts: dict[str, bytes] = {}
    rendered_rows: list[dict[str, Any]] = []
    for node in dispatch_nodes:
        provider_id = str(node["provider_id"])
        profile = profile_by_provider.get(provider_id)
        if profile is None:
            raise WireFreezeError(f"调度位含未知供应商：{provider_id}")
        call_id = str(node["base_call_id"])
        prompt_row = prompt_by_call.get(call_id)
        if prompt_row is None:
            raise WireFreezeError(f"调度位缺精确题面：{call_id}")
        messages = prompt_row["messages"]
        messages_sha256 = sha256_bytes(canonical_bytes(messages))
        if messages_sha256 != node["messages_sha256"]:
            raise WireFreezeError(f"{node['dispatch_id']} 模型可见题面 SHA 漂移")
        body = {
            "model": profile["model_id"],
            "messages": messages,
            **profile["body_fields"],
        }
        if set(body) != set(profile["allowed_body_fields"]):
            raise WireFreezeError(f"{node['dispatch_id']} 实发字段越界")
        body_path = f"wire/{provider_id}/{call_id}.json"
        body_raw = canonical_bytes(body)
        artifacts[body_path] = body_raw
        rendered_rows.append(
            {
                "dispatch_id": node["dispatch_id"],
                "provider_id": provider_id,
                "model_id": profile["model_id"],
                "role": profile["role"],
                "base_call_id": call_id,
                "task": node["task"],
                "floor_kind": node["floor_kind"],
                "url": profile["base_url"] + profile["endpoint"],
                "timeout_seconds": profile["timeout_seconds"],
                "body_path": body_path,
                "body_sha256": sha256_bytes(body_raw),
                "body_fields": sorted(body),
                "messages_sha256": messages_sha256,
                "source_send_surface_sha256": node["send_surface_sha256"],
                "status": "FROZEN_NOT_SENT",
            }
        )

    counts = Counter(row["provider_id"] for row in rendered_rows)
    if counts != {
        "qianwen_platform": 30,
        "volcengine_ark": 30,
        "tencent_tokenhub": 30,
    }:
        raise WireFreezeError(f"三家 wire 数量错误：{dict(counts)}")
    for call_id in prompt_by_call:
        same_slot = [
            row
            for row in rendered_rows
            if row["base_call_id"] == call_id
        ]
        if len(same_slot) != 3 or len(
            {row["messages_sha256"] for row in same_slot}
        ) != 1:
            raise WireFreezeError(f"{call_id} 三家题面未保持逐字一致")

    profile_rows: list[dict[str, Any]] = []
    for profile in profiles:
        profile_payload = {
            "schema_version": "v02-c13-provider-wire-profile.v1",
            "provider_id": profile["provider_id"],
            "model_id": profile["model_id"],
            "role": profile["role"],
            "base_url": profile["base_url"],
            "endpoint": profile["endpoint"],
            "api_key_env": profile["api_key_env"],
            "provider_config_path": profile["provider_config_path"],
            "provider_config_sha256": profile["provider_config_sha256"],
            "enabled_by_default": profile["enabled_by_default"],
            "timeout_seconds": profile["timeout_seconds"],
            "allowed_body_fields": profile["allowed_body_fields"],
            "explicitly_omitted_fields": profile[
                "explicitly_omitted_fields"
            ],
            "thinking_contract": profile["thinking_contract"],
            "response_contract": {
                "unique_choice_required": True,
                "finish_reason_required": "stop",
                "content_path": "choices[0].message.content",
                "content_must_parse_as_json_object_without_repair": True,
                "reasoning_path": profile["response_reasoning_path"],
                "reasoning_or_reasoning_usage_must_be_observed": True,
                "response_model_identity_must_match_request": True,
                "usage_required": True,
                "request_id_required": True,
            },
            "field_evidence": profile["field_evidence"],
            "field_evidence_status": (
                "STATIC_DOCUMENT_POINTERS_ONLY_NOT_LIVE_COMPATIBILITY"
            ),
            "field_evidence_coverage_passed": profile[
                "field_evidence_coverage_passed"
            ],
            "field_evidence_snapshot_frozen": profile[
                "field_evidence_snapshot_frozen"
            ],
            "wire_adapter_zero_call_render_passed": True,
            "live_catalog_or_identity_gate_passed": False,
            "automatic_fallback_allowed": False,
            "model_api_calls": 0,
            "network_requests": 0,
            "key_value_read": False,
        }
        path = f"profiles/{profile['provider_id']}.json"
        artifacts[path] = canonical_bytes(profile_payload)
        profile_rows.append(
            {
                "provider_id": profile["provider_id"],
                "model_id": profile["model_id"],
                "profile_path": path,
                "profile_sha256": sha256_bytes(artifacts[path]),
                "rendered_request_total": counts[profile["provider_id"]],
                "status": (
                    "PASS_ZERO_CALL_CANDIDATE_RENDER_"
                    "STATIC_EVIDENCE_POINTERS_ONLY"
                ),
            }
        )

    plan = {
        "schema_version": "v02-c13-wire-dispatch-plan.v1",
        "status": (
            "PASS_ZERO_CALL_WIRE_RENDER_NOT_EXECUTABLE_"
            "PENDING_NOTION_FLOOR_CATALOG_AND_KEYS"
        ),
        "source_r02_path": display_path(SOURCE_R02),
        "source_r02_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
        "source_r02_artifact_set_sha256": (
            EXPECTED_SOURCE_ARTIFACT_SET_SHA256
        ),
        "source_r02_verified_file_total": source_verification[
            "verified_file_total"
        ],
        "source_r02_rebuilt_artifact_set_sha256": source_verification[
            "rebuilt_artifact_set_sha256"
        ],
        "source_prompt_set_sha256": EXPECTED_PROMPT_SET_SHA256,
        "prompt_slot_total": 30,
        "provider_total": 3,
        "dispatch_total": len(rendered_rows),
        "per_provider_hard_cap": 30,
        "total_hard_cap": 90,
        "primary_readout_provider": "qianwen_platform",
        "provider_scores_may_be_merged_averaged_or_weighted": False,
        "same_slot_messages_must_be_byte_identical": True,
        "private_c13_request_wrapper_may_be_sent": False,
        "rows": rendered_rows,
    }
    artifacts["plans/wire_dispatch_plan.json"] = canonical_bytes(plan)
    artifacts["preflight/wire_adapter_receipt.json"] = canonical_bytes(
        {
            "schema_version": "v02-c13-wire-adapter-receipt.v1",
            "status": (
                "PASS_ZERO_CALL_RENDER_ONLY_EXECUTION_REMAINS_BLOCKED"
            ),
            "providers": profile_rows,
            "provider_pass_total": 3,
            "rendered_request_total": 90,
            "messages_drift_total": 0,
            "forbidden_field_hit_total": 0,
            "secret_or_authorization_field_total": 0,
            "model_api_calls": 0,
            "network_requests": 0,
            "key_value_read": False,
            "execute_allowed": False,
            "remaining_pre_send_blockers": [
                "NOTION_EXACT_PROMPT_APPROVED_TO_SEND_PENDING",
                "FLOOR_PASS_NUMERIC_CRITERION_PENDING",
                "THREE_PROVIDER_KEY_PRESENCE_RECHECK_PENDING",
                "REQUIRED_LIVE_CATALOG_GATE_PENDING",
            ],
            "first_authorized_response_acceptance_gates": [
                "RESPONSE_MODEL_IDENTITY_MUST_MATCH_REQUEST",
                "STRICT_JSON_AND_REASONING_CONTRACT_MUST_PASS",
            ],
        }
    )
    readme = """# C13 r03｜三家运输外壳零调用冻结

✅ 已把 r02 封签的 30 份题面逐字复制到三家各自的 HTTP JSON body，
共 90 份。三家同题 `messages` SHA 完全相同；模型、温度、思考与输出
字段只存在于运输外壳，不进入题面。

✅ 千问固定版使用显式思考和 32768 思考预算；豆包 Pro 使用
`thinking.type=enabled` 与 32768 输出护栏；MiniMax M3 保持文档默认
adaptive thinking，并用 `reasoning_split=true` 把思考与最终 JSON 分开。
三家都不发送 `response_format`、工具或自动联网字段，最终正文由本地
严格 JSON 解析闸验收，禁止修补。

⚠️ 这张票只说明“候选字段能按静态文档指针确定性渲染”，不冒充三个
精确型号已经真实兼容，也不把文档链接当冻结快照。当前仍是 0 调用，
且 `execute_allowed=false`：Notion 逐字题面放行、地板数值判法、三把
密钥存在性与实时目录闸全部过之前，不会发第一条请求。响应身份闸不另
发探针；它验收获准的 90 份中第一条响应，失败即硬停、不接纳该响应。

来源：Codex
"""
    artifacts["README.md"] = readme.encode("utf-8")
    preimage = {
        path: sha256_bytes(raw)
        for path, raw in sorted(artifacts.items())
    }
    artifacts["artifact_manifest.json"] = canonical_bytes(
        {
            "schema_version": "v02-c13-wire-artifact-manifest.v1",
            "status": (
                "PASS_ZERO_CALL_WIRE_RENDER_NOT_EXECUTABLE_"
                "PENDING_NOTION_FLOOR_CATALOG_AND_KEYS"
            ),
            "files": [
                {"path": path, "sha256": digest}
                for path, digest in sorted(preimage.items())
            ],
            "artifact_set_sha256": sha256_bytes(
                canonical_bytes(preimage)
            ),
            "prompt_slot_total": 30,
            "rendered_request_total": 90,
            "model_api_calls": 0,
            "network_requests": 0,
            "key_value_read": False,
        }
    )
    return artifacts


def write_or_verify(
    output_dir: Path = OUTPUT_DIR,
    report_dir: Path = REPORT_DIR,
    *,
    write: bool = True,
) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise WireFreezeError("C13 wire 连续两次构造不一致")
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        for relative, raw in first.items():
            path = output_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    if actual != set(first):
        raise WireFreezeError(
            "C13 wire 输出集合不闭合："
            f"missing={sorted(set(first) - actual)} "
            f"unexpected={sorted(actual - set(first))}"
        )
    for relative, raw in first.items():
        if (output_dir / relative).read_bytes() != raw:
            raise WireFreezeError(f"C13 wire 工件字节漂移：{relative}")
    report_path = report_dir / "C13_三通道运输外壳停点回包.md"
    if write:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(first["README.md"])
    if report_path.read_bytes() != first["README.md"]:
        raise WireFreezeError("C13 wire reports 镜像与工件正文不一致")
    manifest = json.loads(first["artifact_manifest.json"])
    return {
        "status": manifest["status"],
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "prompt_slot_total": manifest["prompt_slot_total"],
        "rendered_request_total": manifest["rendered_request_total"],
        "model_api_calls": 0,
        "network_requests": 0,
        "key_value_read": False,
        "output_dir": display_path(output_dir),
        "report_path": display_path(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="V02 C13 三家运输外壳零调用冻结")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = write_or_verify(
        args.output_dir,
        args.report_dir,
        write=not args.check,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
