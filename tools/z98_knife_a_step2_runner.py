#!/usr/bin/env python3
"""第98道刀A实验步二：68节点正式执行器与零调用全链预演。

这个工具把 r05 已冻结的 34 组 ``repair -> independent_judge`` 图真正
变成可审计状态机。它不会替 r05 发明缺失的修复请求外壳，也不会把离线
fixture 冒充千问在线目录结果：

* ``prepare`` 只生成 r07 零调用预演工件；
* ``verify`` 连续重建并核对全部预演工件；
* ``live-preflight`` 只有在另行批准的修复外壳权威票和千问官方目录票
  都齐时才返回可发网；当前缺任一票都会在读取密钥和网络之前拒绝。

正式发网仍按 r05 的 68 节点顺序逐节点落不可变五件套；任何已有尝试但
没有完整检查点的节点都视为占用不明，禁止重发。
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_DIR = _TOOLS_DIR.parent
for _import_root in (_REPO_DIR, _TOOLS_DIR):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from experiments.Z98_independent_verifier_freeze_20260724 import (  # noqa: E402
    pipeline as freeze_pipeline,
)
from experiments.Z98_independent_verifier_freeze_20260724.core import (  # noqa: E402
    API_KEY_ENV as QWEN_KEY_ENV,
    INPUT_PRICE_CNY_PER_MILLION_TOKENS,
    MODEL_ID as QWEN_MODEL_ID,
    OUTPUT_PRICE_CNY_PER_MILLION_TOKENS,
    PROVIDER_ID as QWEN_PROVIDER_ID,
    TOTAL_COST_CAP_MICRO_CNY,
    TOTAL_TOKEN_CAP,
    make_synthetic_repair_transport_tickets,
    parse_verifier_content,
    render_dynamic_verifier_request,
    sha256_bytes,
    stable_json_bytes,
)
from experiments.Z98_knife_a_patch_step1_20260724.core import (  # noqa: E402
    Z98ContractError,
    validate_atom_batch,
    validate_patch,
)

try:  # 直接执行 tools/ 脚本时
    from pipeline_common import model_benchmark
    from zbatch_modules import z83_retry_transport
    from zbatch_modules.errors import ZBatchError
except ModuleNotFoundError:  # 作为 tools.z98_... 导入时
    from tools.pipeline_common import model_benchmark
    from tools.zbatch_modules import z83_retry_transport
    from tools.zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
STEP1_ROOT = ROOT / "runs/Z98_刀A小额补丁实验_步一备料_v1.0_20260724"
R05_ROOT = ROOT / "runs/Z98_刀A小额补丁实验_独立核验冻结_r05_v1.0_20260724"
R06_ROOT = ROOT / "runs/Z98_刀A小额补丁实验_步二发网前运行器缺口硬停_r06_v1.0_20260724"
DEFAULT_RUN_DIR = ROOT / "runs/Z98_刀A小额补丁实验_步二正式执行器预演_r07_v1.3_20260724"

R05_MANIFEST_SHA256 = "7389dba3abc5b3ce78b98fa08b9b078d015c1496b95a5d4613d15cabfdb47c40"
R06_HARD_STOP_SHA256 = "f81e8adc4dbed046df9d152d955bbc234a044db3a665c4f8f0fc83a2c9bea076"
REPAIR_REQUEST_SET_SHA256 = "d10179c500d98e79adb90c98fe4b7c571c18c191ab4da322cf610d04db90bb70"
CONTRACT_VERSION = "z98-knife-a-step2-executor-v1"
REPAIR_AUTHORITY_SCHEMA = "z98-repair-envelope-authority-v1"
CATALOG_RECEIPT_SCHEMA = "z98-qwen-official-catalog-receipt-v2"
CATALOG_APPROVAL_SCHEMA = "z98-qwen-catalog-independent-approval-v1"
CATALOG_APPROVAL_ALGORITHM = "rsa-pkcs1v15-sha256"

# 这三张信任表故意默认留空。正式发网前，必须由独立审收把 Notion
# 回读权威票、官方 qianwen CLI 内容身份和独立目录签名公钥钉进受审代码。
# 目录票本身不再回写进 runner，避免“票绑定 runner、runner 又钉票”的循环。
TRUSTED_REPAIR_AUTHORITY_RECEIPT_SHA256S: frozenset[str] = frozenset()
TRUSTED_QWEN_CLI_IDENTITIES: dict[str, dict[str, str]] = {}
TRUSTED_QWEN_CATALOG_APPROVER_KEYS: dict[str, dict[str, Any]] = {}
QWEN_CATALOG_TTL_SECONDS = 30 * 60

NOTION_QUEUE_PAGE_ID = "3d80c8bc0efe458ebb487a7297e654dc"
NOTION_LEDGER_PAGE_ID = "4a46597cd80242f385f15209ebe9170c"
NOTION_QUEUE_URL = f"https://app.notion.com/p/{NOTION_QUEUE_PAGE_ID}"
NOTION_LEDGER_URL = f"https://app.notion.com/p/{NOTION_LEDGER_PAGE_ID}"

SENSENOVA_CONFIG = ROOT / "config/providers/sensenova.json"
TENCENT_CONFIG = ROOT / "config/providers/tencent_tokenhub_multi_model.json"
QWEN_CONFIG = ROOT / "config/providers/qianwen_platform_multi_model.json"

RUNTIME_DEPENDENCIES = (
    Path(__file__).resolve(),
    Path(freeze_pipeline.__file__).resolve(),
    ROOT / "experiments/Z98_independent_verifier_freeze_20260724/core.py",
    ROOT / "experiments/Z98_knife_a_patch_step1_20260724/core.py",
    Path(model_benchmark.__file__).resolve(),
    Path(z83_retry_transport.__file__).resolve(),
)

LANE_CONTRACTS: dict[str, dict[str, str]] = {
    "flash": {
        "provider": "sensenova",
        "model": "deepseek-v4-flash",
        "api_key_env": "SENSENOVA_API_KEY",
    },
    "pro": {
        "provider": "tencent_tokenhub",
        "model": "deepseek-v4-pro-202606",
        "api_key_env": "TENCENT_TOKENHUB_API_KEY",
    },
}


class Z98Step2HardStop(ZBatchError):
    """正式发网前或执行中出现预写失败面。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class LiveAuthority:
    """通过两张外部权威票后得到的发网前最小上下文。"""

    repair_envelope: Mapping[str, Any]
    qwen_catalog: Mapping[str, Any]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _parse_iso_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise Z98Step2HardStop(
            "timestamp_invalid",
            f"{label}缺时间",
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Z98Step2HardStop(
            "timestamp_invalid",
            f"{label}不是 ISO 时间",
        ) from exc
    if parsed.tzinfo is None:
        raise Z98Step2HardStop(
            "timestamp_invalid",
            f"{label}缺时区",
        )
    return parsed


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return model_benchmark.sha256_file(path)


def _display_path(path: Path) -> str:
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


def _catalog_approval_message(
    receipt: Mapping[str, Any],
    approval: Mapping[str, Any],
) -> bytes:
    """构造独立审收方签名的稳定消息；签名字段本身不参与签名。"""

    receipt_payload = {
        key: value
        for key, value in receipt.items()
        if key != "independent_approval"
    }
    approval_context = {
        key: approval.get(key)
        for key in (
            "schema_version",
            "status",
            "algorithm",
            "key_id",
            "approved_at",
        )
    }
    return (
        json.dumps(
            {
                "purpose": (
                    "Z98_QWEN_EXACT_CATALOG_RECEIPT_INDEPENDENT_APPROVAL"
                ),
                "catalog_receipt": receipt_payload,
                "approval_context": approval_context,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _verify_rsa_pkcs1v15_sha256(
    message: bytes,
    signature: bytes,
    *,
    modulus_hex: str,
    exponent: int,
) -> bool:
    """只做 RSA PKCS#1 v1.5 + SHA-256 验签；不持有私钥。"""

    try:
        modulus = int(modulus_hex, 16)
    except (TypeError, ValueError):
        return False
    if modulus.bit_length() < 2048 or exponent < 3 or exponent % 2 == 0:
        return False
    size = (modulus.bit_length() + 7) // 8
    if len(signature) != size:
        return False
    encoded_signature = int.from_bytes(signature, "big")
    if encoded_signature >= modulus:
        return False
    decoded = pow(encoded_signature, exponent, modulus).to_bytes(size, "big")
    digest_info = (
        bytes.fromhex("3031300d060960864801650304020105000420")
        + hashlib.sha256(message).digest()
    )
    padding_size = size - len(digest_info) - 3
    if padding_size < 8:
        return False
    expected = (
        b"\x00\x01"
        + (b"\xff" * padding_size)
        + b"\x00"
        + digest_info
    )
    return hmac.compare_digest(decoded, expected)


def _validate_catalog_independent_approval(
    receipt: Mapping[str, Any],
) -> Mapping[str, Any]:
    approval = receipt.get("independent_approval")
    required = {
        "schema_version",
        "status",
        "algorithm",
        "key_id",
        "approved_at",
        "signed_payload_sha256",
        "signature_base64",
    }
    if not isinstance(approval, Mapping) or set(approval) != required:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_untrusted",
            "千问目录票缺独立签名审收层",
        )
    expected = {
        "schema_version": CATALOG_APPROVAL_SCHEMA,
        "status": "APPROVED_BY_INDEPENDENT_REVIEW",
        "algorithm": CATALOG_APPROVAL_ALGORITHM,
    }
    if any(approval.get(key) != value for key, value in expected.items()):
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_untrusted",
            "千问目录票独立签名合同漂移",
        )
    key_id = approval.get("key_id")
    trusted_key = TRUSTED_QWEN_CATALOG_APPROVER_KEYS.get(str(key_id))
    if (
        not isinstance(key_id, str)
        or not key_id
        or not isinstance(trusted_key, Mapping)
        or set(trusted_key) != {"algorithm", "modulus_hex", "exponent"}
        or trusted_key.get("algorithm") != CATALOG_APPROVAL_ALGORITHM
        or not isinstance(trusted_key.get("modulus_hex"), str)
        or not isinstance(trusted_key.get("exponent"), int)
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_approver_untrusted",
            "独立目录审收公钥尚未钉入受审信任根",
        )
    approved_at = _parse_iso_time(
        approval.get("approved_at"),
        "千问目录独立审收票",
    )
    checked_at = _parse_iso_time(receipt.get("checked_at"), "千问目录票")
    if approved_at < checked_at:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_untrusted",
            "独立审收时间早于目录核验时间",
        )
    message = _catalog_approval_message(receipt, approval)
    if (
        approval.get("signed_payload_sha256")
        != sha256_bytes(message)
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_untrusted",
            "独立签名没有绑定整张目录证据与运行身份",
        )
    try:
        signature = base64.b64decode(
            str(approval.get("signature_base64")),
            validate=True,
        )
    except (ValueError, TypeError) as exc:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_untrusted",
            "独立签名不是合法 Base64",
        ) from exc
    if not _verify_rsa_pkcs1v15_sha256(
        message,
        signature,
        modulus_hex=trusted_key["modulus_hex"],
        exponent=trusted_key["exponent"],
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_untrusted",
            "千问目录票独立签名验签失败",
        )
    return approval


def _assert_sha(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise Z98Step2HardStop(
            "frozen_source_drift",
            f"{label}缺失或 SHA 漂移：{_display_path(path)}",
        )


def _read_r05() -> tuple[dict[str, Any], dict[str, Any]]:
    _assert_sha(
        R05_ROOT / "bundle_manifest.json",
        R05_MANIFEST_SHA256,
        "r05 bundle manifest",
    )
    _assert_sha(
        R06_ROOT / "hard_stop.json",
        R06_HARD_STOP_SHA256,
        "r06 hard stop",
    )
    sequence = read_json(R05_ROOT / "execution/sequence_68.json")
    mappings = read_json(R05_ROOT / "mappings/verifier_mapping.json")
    if (
        sequence.get("total_nodes") != 68
        or len(sequence.get("nodes", [])) != 68
        or mappings.get("mapping_count") != 17
        or len(mappings.get("mappings", [])) != 17
    ):
        raise Z98Step2HardStop("r05_graph_drift", "r05 不是 17模板/68节点冻结图")
    immutability = read_json(
        R05_ROOT / "receipts/repair_source_immutability.json"
    )
    replay = immutability.get("authority_listing_replay", {})
    if (
        immutability.get("status") != "PASS_UNCHANGED"
        or replay.get("recomputed_aggregate_listing_sha256")
        != REPAIR_REQUEST_SET_SHA256
    ):
        raise Z98Step2HardStop(
            "repair_request_set_drift",
            "17份修复请求集合不等于 d101 权威集合",
        )
    return sequence, mappings


def _provider_configs() -> dict[str, dict[str, Any]]:
    configs = {
        "sensenova": read_json(SENSENOVA_CONFIG),
        "tencent_tokenhub": read_json(TENCENT_CONFIG),
        "qianwen_platform": read_json(QWEN_CONFIG),
    }
    expected = {
        "sensenova": ("SENSENOVA_API_KEY", "/chat/completions"),
        "tencent_tokenhub": ("TENCENT_TOKENHUB_API_KEY", "/chat/completions"),
        "qianwen_platform": (QWEN_KEY_ENV, "/chat/completions"),
    }
    for provider_id, (key_env, endpoint) in expected.items():
        row = configs[provider_id]
        if (
            row.get("provider", provider_id) != provider_id
            or row.get("api_key_env") != key_env
            or row.get("endpoint") != endpoint
        ):
            raise Z98Step2HardStop(
                "provider_config_drift",
                f"{provider_id} 本地通道身份漂移",
            )
    qwen_rows = [
        row
        for row in configs["qianwen_platform"].get("models", [])
        if isinstance(row, Mapping) and row.get("model_id") == QWEN_MODEL_ID
    ]
    if (
        len(qwen_rows) != 1
        or qwen_rows[0].get("fixed_snapshot") is not True
        or qwen_rows[0].get("live_catalog_check_required_before_run")
        is not True
    ):
        raise Z98Step2HardStop(
            "qwen_fixed_model_config_missing",
            "千问固定型号本地登记缺失或未要求发网前目录核验",
        )
    return configs


def _runtime_dependency_rows() -> list[dict[str, str]]:
    return [
        {
            "path": _display_path(path),
            "sha256": sha256_file(path),
        }
        for path in RUNTIME_DEPENDENCIES
    ]


def _repair_authority_schema() -> dict[str, Any]:
    """返回未来权威票的机器合同，不生成任何授权值。"""

    return {
        "schema_version": REPAIR_AUTHORITY_SCHEMA,
        "status_required": "APPROVED_FOR_Z98_STEP2",
        "authority_required": {
            "notion_queue_url": NOTION_QUEUE_URL,
            "notion_queue_page_id": NOTION_QUEUE_PAGE_ID,
            "notion_ledger_url": NOTION_LEDGER_URL,
            "notion_ledger_page_id": NOTION_LEDGER_PAGE_ID,
            "approval_block_id": "nonempty string",
            "approval_block_last_edited_time": "nonempty string",
            "approval_text": "nonempty verbatim text",
            "approval_text_sha256": "sha256(approval_text UTF-8)",
            "lane_profiles_sha256": "sha256(canonical lane_profiles)",
            "readback_receipt_id": "nonempty independent Notion readback id",
        },
        "required_lane_profiles": {
            lane: {
                "provider": contract["provider"],
                "model": contract["model"],
                "api_key_env": contract["api_key_env"],
                "body_fields": (
                    "exact JSON object; model/messages forbidden because runner inserts "
                    "the already frozen identities"
                ),
            }
            for lane, contract in LANE_CONTRACTS.items()
        },
        "forbidden": [
            "fixture_only_non_sendable",
            "automatic_provider_fallback",
            "implicit provider defaults",
            "unapproved aliases",
        ],
        "trusted_whole_receipt_sha256_required": True,
        "current_status": "MISSING_NOT_SELF_AUTHORIZED",
    }


def _catalog_adapter_contract() -> dict[str, Any]:
    return {
        "schema_version": "z98-qwen-catalog-adapter-contract-v1",
        "provider": QWEN_PROVIDER_ID,
        "exact_model_id": QWEN_MODEL_ID,
        "required_receipt_schema": CATALOG_RECEIPT_SCHEMA,
        "required_status": "PASS_EXACT_MODEL_ONLINE",
        "required_source_kind": (
            "APPROVED_OFFICIAL_CATALOG_COMMAND_OR_APPROVED_OFFICIAL_API"
        ),
        "required_bindings": [
            "adapter_identity",
            "adapter_sha256",
            "raw_catalog_path",
            "raw_catalog_sha256",
            "selected_model_id",
            "selected_model_status",
            "package_name",
            "package_version",
            "npm_integrity",
            "package_manifest_path",
            "package_manifest_sha256",
            "status_evidence_kind",
            "status_evidence_policy",
            "checked_at",
            "target_run_id",
            "target_run_root_sha256",
            "prepared_manifest_sha256",
            "catalog_attempt_reservation_sha256",
            "independent_approval.signature_base64",
            "independent_approval.signed_payload_sha256",
        ],
        "forbidden": [
            "fixture accepted as online",
            "chat completion used as model catalog",
            "unapproved /models assumption",
            "alias substitution",
            "cross-platform failover",
        ],
        "current_local_state": (
            "千问 OpenAI兼容通道未配置已证实的官方模型目录适配器；"
            "独立目录审收公钥也未钉入；live-preflight fail closed"
        ),
    }


def _fixture_lane_fields(lane: str) -> dict[str, Any]:
    """只用于离线状态机演算，明确不可发网。"""

    if lane == "flash":
        return {
            "temperature": 0.2,
            "max_tokens": 8000,
            "n": 1,
            "reasoning_effort": "medium",
            "response_format": {"type": "json_object"},
        }
    if lane == "pro":
        return {
            "temperature": 0.2,
            "max_tokens": 8000,
            "n": 1,
            "thinking": {"type": "enabled", "reasoning_effort": "medium"},
        }
    raise Z98Step2HardStop("unknown_lane", f"不认识的修复臂：{lane}")


def _validate_repair_authority(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Z98Step2HardStop(
            "repair_envelope_authority_missing",
            "修复请求外壳权威票缺失；未读取密钥、未请求目录、未发模型",
        )
    if (
        value.get("schema_version") != REPAIR_AUTHORITY_SCHEMA
        or value.get("status") != "APPROVED_FOR_Z98_STEP2"
        or value.get("fixture_only_non_sendable") is not False
        or value.get("automatic_provider_fallback") is not False
    ):
        raise Z98Step2HardStop(
            "repair_envelope_authority_invalid",
            "修复请求外壳权威票身份、批准状态或禁回退字段不成立",
        )
    authority = value.get("authority")
    required_authority = {
        "notion_queue_url",
        "notion_queue_page_id",
        "notion_ledger_url",
        "notion_ledger_page_id",
        "approval_block_id",
        "approval_block_last_edited_time",
        "approval_text",
        "approval_text_sha256",
        "lane_profiles_sha256",
        "readback_receipt_id",
    }
    if (
        not isinstance(authority, Mapping)
        or set(authority) != required_authority
    ):
        raise Z98Step2HardStop(
            "repair_envelope_authority_invalid",
            "修复请求外壳权威票 authority 字段集合漂移",
        )
    expected_identity = {
        "notion_queue_url": NOTION_QUEUE_URL,
        "notion_queue_page_id": NOTION_QUEUE_PAGE_ID,
        "notion_ledger_url": NOTION_LEDGER_URL,
        "notion_ledger_page_id": NOTION_LEDGER_PAGE_ID,
    }
    if any(
        authority.get(field) != expected
        for field, expected in expected_identity.items()
    ):
        raise Z98Step2HardStop(
            "repair_envelope_authority_invalid",
            "修复外壳权威票没有绑定指定 Notion 队列页和账序页",
        )
    for field in (
        "approval_block_id",
        "approval_block_last_edited_time",
        "approval_text",
        "readback_receipt_id",
    ):
        if not isinstance(authority.get(field), str) or not authority[field]:
            raise Z98Step2HardStop(
                "repair_envelope_authority_invalid",
                f"修复外壳权威票缺 {field}",
            )
    if (
        not _is_sha256(authority.get("approval_text_sha256"))
        or sha256_bytes(authority["approval_text"].encode("utf-8"))
        != authority["approval_text_sha256"]
    ):
        raise Z98Step2HardStop(
            "repair_envelope_authority_invalid",
            "修复外壳权威票批准正文与 SHA 不一致",
        )
    profiles = value.get("lane_profiles")
    if not isinstance(profiles, Mapping) or set(profiles) != set(LANE_CONTRACTS):
        raise Z98Step2HardStop(
            "repair_envelope_authority_invalid",
            "修复外壳权威票必须且只能含 flash/pro 两臂",
        )
    for lane, expected in LANE_CONTRACTS.items():
        row = profiles.get(lane)
        if not isinstance(row, Mapping):
            raise Z98Step2HardStop(
                "repair_envelope_authority_invalid",
                f"{lane} 外壳权威行非法",
            )
        if any(row.get(field) != value for field, value in expected.items()):
            raise Z98Step2HardStop(
                "repair_envelope_authority_invalid",
                f"{lane} provider/model/key_env 与冻结图不一致",
            )
        fields = row.get("body_fields")
        if not isinstance(fields, Mapping) or not fields:
            raise Z98Step2HardStop(
                "repair_envelope_authority_invalid",
                f"{lane} 缺逐字段 body_fields",
            )
        forbidden = {"model", "messages", "provider", "api_key", "authorization"}
        if forbidden & {str(key).casefold() for key in fields}:
            raise Z98Step2HardStop(
                "repair_envelope_authority_invalid",
                f"{lane} body_fields 夹带 runner 专属或密钥字段",
            )
    if (
        not _is_sha256(authority.get("lane_profiles_sha256"))
        or canonical_sha(profiles) != authority["lane_profiles_sha256"]
    ):
        raise Z98Step2HardStop(
            "repair_envelope_authority_invalid",
            "修复外壳两臂字段没有绑定批准正文中的规范化 SHA",
        )
    return value


def _validate_repair_authority_path(path: Path) -> Mapping[str, Any]:
    """消费独立 Notion 回读票；runner 不能给任意本地 JSON 自签。"""

    receipt_sha = sha256_file(path)
    if receipt_sha not in TRUSTED_REPAIR_AUTHORITY_RECEIPT_SHA256S:
        raise Z98Step2HardStop(
            "repair_envelope_authority_untrusted",
            "修复外壳票未由独立 Notion 回读审收钉入受审信任表",
        )
    return _validate_repair_authority(read_json(path))


def _validate_catalog_receipt(
    value: Any,
    *,
    run_dir: Path | None = None,
    require_fresh: bool = False,
    require_approval: bool = True,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_missing",
            "千问官方精确型号目录票缺失；fixture 不得冒充 online",
        )
    required = {
        "schema_version",
        "status",
        "provider",
        "exact_model_id",
        "source_kind",
        "adapter_identity",
        "adapter_sha256",
        "raw_catalog_path",
        "raw_catalog_sha256",
        "selected_model_id",
        "selected_model_status",
        "status_evidence_kind",
        "status_evidence_policy",
        "checked_at",
        "command_path",
        "command_version",
        "catalog_command",
        "target_run_id",
        "target_run_root_sha256",
        "prepared_manifest_sha256",
        "catalog_attempt_reservation_path",
        "catalog_attempt_reservation_sha256",
        "package_name",
        "package_version",
        "npm_integrity",
        "package_manifest_path",
        "package_manifest_sha256",
        "independent_approval",
        "fixture_only_non_sendable",
        "automatic_fallback",
    }
    if set(value) != required:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_invalid",
            "千问目录票字段集合漂移",
        )
    expected = {
        "schema_version": CATALOG_RECEIPT_SCHEMA,
        "status": "PASS_EXACT_MODEL_ONLINE",
        "provider": QWEN_PROVIDER_ID,
        "exact_model_id": QWEN_MODEL_ID,
        "selected_model_id": QWEN_MODEL_ID,
        "selected_model_status": "online",
        "status_evidence_kind": "authenticated_catalog_membership",
        "status_evidence_policy": (
            "官方qianwen认证目录不返回online字段；精确ID在认证后的"
            "ListModelSeries目录中唯一出现，按本轮目录闸政策记online。"
        ),
        "fixture_only_non_sendable": False,
        "automatic_fallback": False,
    }
    if any(value.get(field) != expected_value for field, expected_value in expected.items()):
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_invalid",
            "千问目录票不是固定型号 online 的正式结果",
        )
    if value.get("source_kind") not in {
        "approved_official_catalog_command",
        "approved_official_catalog_api",
    }:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_invalid",
            "千问目录票来源不是已批准官方目录适配器",
        )
    for field in (
        "adapter_sha256",
        "raw_catalog_sha256",
        "package_manifest_sha256",
    ):
        if not _is_sha256(value.get(field)):
            raise Z98Step2HardStop(
                "qwen_catalog_receipt_invalid",
                f"千问目录票 {field} 非 SHA-256",
            )
    for field in (
        "adapter_identity",
        "raw_catalog_path",
        "checked_at",
        "command_path",
        "command_version",
        "package_name",
        "package_version",
        "npm_integrity",
        "package_manifest_path",
        "target_run_id",
        "catalog_attempt_reservation_path",
    ):
        if not isinstance(value.get(field), str) or not value[field]:
            raise Z98Step2HardStop(
                "qwen_catalog_receipt_invalid",
                f"千问目录票缺 {field}",
            )
    if value.get("catalog_command") != [
        value["command_path"],
        "models",
        "list",
        "--all",
        "--format",
        "json",
    ]:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_invalid",
            "千问目录票没有绑定唯一允许的官方 models list 命令",
        )
    if not _is_sha256(value.get("prepared_manifest_sha256")) or not _is_sha256(
        value.get("catalog_attempt_reservation_sha256")
    ) or not _is_sha256(value.get("target_run_root_sha256")):
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_invalid",
            "千问目录票未绑定运行根、prepared manifest 或目录占用票 SHA",
        )
    if run_dir is not None:
        if (
            value.get("target_run_id") != run_dir.name
            or value.get("target_run_root_sha256")
            != sha256_bytes(str(run_dir.resolve()).encode("utf-8"))
            or value.get("prepared_manifest_sha256")
            != sha256_file(run_dir / "prepared/artifact_manifest.json")
        ):
            raise Z98Step2HardStop(
                "qwen_catalog_receipt_cross_run",
                "千问目录票不属于本运行或 prepared manifest",
            )
    reservation_path = Path(
        str(value["catalog_attempt_reservation_path"])
    ).resolve()
    if (
        not reservation_path.is_file()
        or str(reservation_path)
        != value["catalog_attempt_reservation_path"]
        or sha256_file(reservation_path)
        != value["catalog_attempt_reservation_sha256"]
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_reservation_missing",
            "千问目录票没有绑定发网前占用票原件",
        )
    reservation = read_json(reservation_path)
    expected_reservation = {
        "schema_version": "z98-qwen-catalog-attempt-reservation-v1",
        "target_run_id": value["target_run_id"],
        "target_run_root_sha256": value["target_run_root_sha256"],
        "prepared_manifest_sha256": value["prepared_manifest_sha256"],
        "adapter_sha256": value["adapter_sha256"],
        "package_manifest_sha256": value["package_manifest_sha256"],
        "catalog_command": value["catalog_command"],
        "reserved_before_catalog_command": True,
    }
    if (
        not isinstance(reservation, Mapping)
        or set(reservation) != {*expected_reservation, "reserved_at"}
        or any(
            reservation.get(field) != expected
            for field, expected in expected_reservation.items()
        )
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_reservation_invalid",
            "千问目录占用票不能由本运行和固定命令重建",
        )
    reserved_at = _parse_iso_time(
        reservation.get("reserved_at"),
        "千问目录占用票",
    )
    checked_at = _parse_iso_time(value.get("checked_at"), "千问目录票")
    if checked_at < reserved_at:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_invalid",
            "千问目录核验时间早于目录占用票",
        )
    if require_fresh:
        age = (
            datetime.now(timezone.utc) - checked_at.astimezone(timezone.utc)
        ).total_seconds()
        if age < -300 or age > QWEN_CATALOG_TTL_SECONDS:
            raise Z98Step2HardStop(
                "qwen_catalog_receipt_expired",
                "千问目录票已过30分钟有效期或时间在未来",
            )
    if require_approval:
        _validate_catalog_independent_approval(value)
    elif value.get("independent_approval") is not None:
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_invalid",
            "目录构造阶段不得自行写入独立审收签名",
        )
    command_path = Path(value["command_path"]).expanduser().resolve()
    trusted_identity = TRUSTED_QWEN_CLI_IDENTITIES.get(
        str(value["adapter_sha256"])
    )
    if not isinstance(trusted_identity, Mapping):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_untrusted",
            "qianwen CLI 实物 SHA 未钉入受审官方身份信任表",
        )
    required_identity = {
        "package_name",
        "package_version",
        "npm_integrity",
        "package_manifest_path",
        "package_manifest_sha256",
        "command_version",
    }
    if set(trusted_identity) != required_identity or any(
        value.get(field) != trusted_identity[field]
        for field in required_identity
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_untrusted",
            "目录票的包名、版本、完整性或入口身份未命中受审信任表",
        )
    if (
        not command_path.is_file()
        or str(command_path) != value["command_path"]
        or sha256_file(command_path) != value["adapter_sha256"]
        or value["adapter_identity"] != f"qianwen-cli:{command_path}"
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_drift",
            "千问目录票绑定的官方CLI实物缺失或SHA漂移",
        )
    manifest_path = Path(str(value["package_manifest_path"])).resolve()
    if (
        not manifest_path.is_file()
        or str(manifest_path) != value["package_manifest_path"]
        or sha256_file(manifest_path) != value["package_manifest_sha256"]
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_drift",
            "qianwen 官方包清单实物缺失或 SHA 漂移",
        )
    package_manifest = read_json(manifest_path)
    integrity = package_manifest.get("_integrity")
    if integrity is None and isinstance(package_manifest.get("dist"), Mapping):
        integrity = package_manifest["dist"].get("integrity")
    if (
        package_manifest.get("name") != value["package_name"]
        or package_manifest.get("version") != value["package_version"]
        or integrity != value["npm_integrity"]
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_drift",
            "qianwen 包名、版本或 npm integrity 不能从包清单重建",
        )
    raw_path = Path(value["raw_catalog_path"])
    if not raw_path.is_absolute():
        raw_path = ROOT / raw_path
    raw_path = raw_path.resolve()
    if (
        not raw_path.is_file()
        or sha256_file(raw_path) != value["raw_catalog_sha256"]
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_raw_drift",
            "千问目录票绑定的原始目录响应缺失或SHA漂移",
        )
    try:
        raw_catalog = json.loads(raw_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Z98Step2HardStop(
            "qwen_catalog_raw_invalid",
            "千问目录票绑定的原始目录响应不是合法JSON",
        ) from exc
    exact = [
        row
        for row in _catalog_rows(raw_catalog)
        if _catalog_model_identity(row) == QWEN_MODEL_ID
    ]
    if len(exact) != 1:
        raise Z98Step2HardStop(
            "qwen_catalog_raw_exact_model_drift",
            "原始目录响应中的精确型号不是唯一一行",
        )
    return value


def _validate_catalog_receipt_path(
    path: Path,
    *,
    run_dir: Path,
    require_fresh: bool,
) -> Mapping[str, Any]:
    if not path.is_file():
        raise Z98Step2HardStop(
            "qwen_catalog_receipt_untrusted",
            "千问目录票原件缺失",
        )
    return _validate_catalog_receipt(
        read_json(path),
        run_dir=run_dir,
        require_fresh=require_fresh,
        require_approval=True,
    )


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _catalog_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, Mapping):
        candidates = [
            value[key]
            for key in ("models", "data")
            if key in value and isinstance(value[key], list)
        ]
        if len(candidates) != 1:
            raise Z98Step2HardStop(
                "qwen_catalog_format_unknown",
                "千问 models list JSON 顶层结构未知",
            )
        rows = candidates[0]
    else:
        raise Z98Step2HardStop(
            "qwen_catalog_format_unknown",
            "千问 models list 没有返回 JSON 数组或模型集合",
        )
    if not rows or not all(isinstance(row, Mapping) for row in rows):
        raise Z98Step2HardStop(
            "qwen_catalog_format_unknown",
            "千问 models list 模型行结构未知或为空",
        )
    return list(rows)


def _catalog_model_identity(row: Mapping[str, Any]) -> str | None:
    observed = {
        str(row[key])
        for key in ("id", "model_id", "name")
        if isinstance(row.get(key), str) and row[key]
    }
    if len(observed) > 1:
        raise Z98Step2HardStop(
            "qwen_catalog_format_unknown",
            "千问目录同一模型行出现冲突身份字段",
        )
    return next(iter(observed), None)


def catalog_check(
    output_dir: Path,
    *,
    run_dir: Path,
    command_runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """只接受官方 qianwen CLI 的精确目录命令并生成可复验票。"""

    verify_prepared(run_dir)
    prepared_manifest_sha = sha256_file(
        run_dir / "prepared/artifact_manifest.json"
    )
    command_path = shutil.which("qianwen")
    if not command_path:
        raise Z98Step2HardStop(
            "qwen_cli_missing",
            "未找到 qianwen CLI；不安装、不登录、不切别名",
        )
    resolved = Path(command_path).expanduser().resolve()
    if not resolved.is_file():
        raise Z98Step2HardStop(
            "qwen_cli_missing",
            f"qianwen 命令不存在：{resolved}",
        )
    adapter_sha = sha256_file(resolved)
    trusted_identity = TRUSTED_QWEN_CLI_IDENTITIES.get(adapter_sha)
    if not isinstance(trusted_identity, Mapping):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_untrusted",
            "发现 qianwen 命令，但其内容身份未获独立审收",
        )
    package_manifest_path = Path(
        str(trusted_identity["package_manifest_path"])
    ).resolve()
    if (
        not package_manifest_path.is_file()
        or sha256_file(package_manifest_path)
        != trusted_identity["package_manifest_sha256"]
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_untrusted",
            "受审 qianwen 包清单缺失或漂移",
        )
    package_manifest = read_json(package_manifest_path)
    integrity = package_manifest.get("_integrity")
    if integrity is None and isinstance(package_manifest.get("dist"), Mapping):
        integrity = package_manifest["dist"].get("integrity")
    if (
        package_manifest.get("name") != trusted_identity["package_name"]
        or package_manifest.get("version")
        != trusted_identity["package_version"]
        or integrity != trusted_identity["npm_integrity"]
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_untrusted",
            "qianwen 包清单身份不能从受审真源重建",
        )
    version_result = command_runner(
        [str(resolved), "version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if version_result.returncode != 0 or not version_result.stdout.strip():
        raise Z98Step2HardStop(
            "qwen_cli_version_failed",
            "qianwen CLI 版本读取失败，拒绝生成目录票",
        )
    if version_result.stdout.strip() != trusted_identity["command_version"]:
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_untrusted",
            "qianwen CLI version 与受审固定版本不一致",
        )
    command = [
        str(resolved),
        "models",
        "list",
        "--all",
        "--format",
        "json",
    ]
    if output_dir.exists() and any(output_dir.iterdir()):
        raise Z98Step2HardStop(
            "catalog_output_exists",
            "目录核验输出目录已有内容，拒绝覆盖或重发目录请求",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    reservation_path = output_dir / "catalog_attempt_reservation.json"
    model_benchmark.write_json_exclusive(
        reservation_path,
        {
            "schema_version": "z98-qwen-catalog-attempt-reservation-v1",
            "target_run_id": run_dir.name,
            "target_run_root_sha256": sha256_bytes(
                str(run_dir.resolve()).encode("utf-8")
            ),
            "prepared_manifest_sha256": prepared_manifest_sha,
            "adapter_sha256": adapter_sha,
            "package_manifest_sha256": trusted_identity[
                "package_manifest_sha256"
            ],
            "catalog_command": command,
            "reserved_before_catalog_command": True,
            "reserved_at": now_iso(),
        },
    )
    result = command_runner(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise Z98Step2HardStop(
            "qwen_catalog_command_failed",
            "qianwen models list 失败或未登录，拒绝切换入口",
        )
    raw = result.stdout.encode("utf-8")
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Z98Step2HardStop(
            "qwen_catalog_format_unknown",
            "qianwen models list stdout 不是 JSON",
        ) from exc
    exact = [
        row
        for row in _catalog_rows(parsed)
        if _catalog_model_identity(row) == QWEN_MODEL_ID
    ]
    if len(exact) != 1:
        raise Z98Step2HardStop(
            "qwen_exact_model_not_unique",
            f"目录中精确型号 {QWEN_MODEL_ID} 不是唯一一行",
        )
    raw_path = output_dir / "raw_catalog_stdout.json"
    model_benchmark.write_bytes_exclusive(raw_path, raw)
    receipt = {
        "schema_version": CATALOG_RECEIPT_SCHEMA,
        "status": "PASS_EXACT_MODEL_ONLINE",
        "provider": QWEN_PROVIDER_ID,
        "exact_model_id": QWEN_MODEL_ID,
        "source_kind": "approved_official_catalog_command",
        "adapter_identity": f"qianwen-cli:{resolved}",
        "adapter_sha256": adapter_sha,
        "raw_catalog_path": _display_path(raw_path),
        "raw_catalog_sha256": sha256_bytes(raw),
        "selected_model_id": QWEN_MODEL_ID,
        "selected_model_status": "online",
        "status_evidence_kind": "authenticated_catalog_membership",
        "status_evidence_policy": (
            "官方qianwen认证目录不返回online字段；精确ID在认证后的"
            "ListModelSeries目录中唯一出现，按本轮目录闸政策记online。"
        ),
        "checked_at": now_iso(),
        "command_path": str(resolved),
        "command_version": version_result.stdout.strip(),
        "catalog_command": command,
        "target_run_id": run_dir.name,
        "target_run_root_sha256": sha256_bytes(
            str(run_dir.resolve()).encode("utf-8")
        ),
        "prepared_manifest_sha256": prepared_manifest_sha,
        "catalog_attempt_reservation_path": str(
            reservation_path.resolve()
        ),
        "catalog_attempt_reservation_sha256": sha256_file(
            reservation_path
        ),
        "package_name": trusted_identity["package_name"],
        "package_version": trusted_identity["package_version"],
        "npm_integrity": trusted_identity["npm_integrity"],
        "package_manifest_path": str(package_manifest_path),
        "package_manifest_sha256": trusted_identity[
            "package_manifest_sha256"
        ],
        "independent_approval": None,
        "fixture_only_non_sendable": False,
        "automatic_fallback": False,
    }
    _validate_catalog_receipt(
        receipt,
        run_dir=run_dir,
        require_approval=False,
    )
    receipt_path = output_dir / "qwen_catalog_receipt.json"
    model_benchmark.write_json_exclusive(receipt_path, receipt)
    return {
        "status": "STRUCTURALLY_VALID_AWAITING_INDEPENDENT_SIGNATURE",
        "receipt_path": _display_path(receipt_path),
        "receipt_sha256": sha256_file(receipt_path),
        "raw_catalog_sha256": receipt["raw_catalog_sha256"],
        "exact_model_id": QWEN_MODEL_ID,
    }


def _repair_body(
    repair_request: Mapping[str, Any],
    *,
    lane: str,
    body_fields: Mapping[str, Any],
) -> dict[str, Any]:
    contract = LANE_CONTRACTS[lane]
    model_visible = repair_request.get("model_visible")
    if not isinstance(model_visible, Mapping):
        raise Z98Step2HardStop("repair_blueprint_invalid", "修复请求缺 model_visible")
    messages = model_visible.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise Z98Step2HardStop("repair_blueprint_invalid", "修复 messages 漂移")
    forbidden = {"model", "messages", "provider", "api_key", "authorization"}
    if forbidden & {str(key).casefold() for key in body_fields}:
        raise Z98Step2HardStop(
            "repair_envelope_authority_invalid",
            "修复 body_fields 夹带 runner 或密钥字段",
        )
    return {
        "model": contract["model"],
        "messages": copy.deepcopy(messages),
        **copy.deepcopy(dict(body_fields)),
    }


def _chapter_number(chapter_id: str) -> int:
    if not chapter_id.startswith("ch") or not chapter_id[2:].isdigit():
        raise Z98Step2HardStop("chapter_id_invalid", f"章号非法：{chapter_id}")
    return int(chapter_id[2:])


def _synthetic_p2_response(repair_request_bytes: bytes) -> bytes:
    """复用冻结包的机械 fixture 生成逻辑，不进入正式结果。"""

    return freeze_pipeline._synthetic_p2_response(repair_request_bytes)


def _synthetic_verdict(template: Mapping[str, Any]) -> bytes:
    binding = template.get("private_binding")
    if not isinstance(binding, Mapping):
        raise Z98Step2HardStop("template_invalid", "裁判模板缺 private_binding")
    item_ids = binding.get("item_ids")
    if not isinstance(item_ids, list) or not item_ids:
        raise Z98Step2HardStop("template_invalid", "裁判模板 item_ids 非法")
    value = {
        "schema": "z98-independent-verdict-v1",
        "case_id": binding["case_id"],
        "items": [
            {
                "item_id": item_id,
                "verdict": "PASS",
                "fact_support": "SUPPORTED",
                "qualifier_support": "NOT_APPLICABLE",
                "anchor_support": "FULL",
                "atomicity": "ATOMIC",
                "reason_codes": ["NONE"],
            }
            for item_id in item_ids
        ],
        "receipt": {"returned_item_ids": item_ids},
    }
    return stable_json_bytes(value)


def _checkpoint_payloads(
    *,
    node: Mapping[str, Any],
    request: Mapping[str, Any],
    response: Any,
    usage: Mapping[str, Any],
    attempts: Mapping[str, Any],
    rehearsal: bool,
) -> dict[str, bytes]:
    prefix = f"rehearsal/checkpoints/{node['node_id']}"
    four = {
        "01_request.json": {
            "schema_version": "z98-node-request-checkpoint-v1",
            "node_id": node["node_id"],
            "node_kind": node["node_kind"],
            "fixture_only_non_sendable": rehearsal,
            "request": copy.deepcopy(dict(request)),
        },
        "02_response.json": {
            "schema_version": "z98-node-response-checkpoint-v1",
            "node_id": node["node_id"],
            "fixture_only_non_sendable": rehearsal,
            "response": copy.deepcopy(response),
        },
        "03_usage.json": {
            "schema_version": "z98-node-usage-checkpoint-v1",
            "node_id": node["node_id"],
            "fixture_only_non_sendable": rehearsal,
            "usage": copy.deepcopy(dict(usage)),
        },
        "04_attempts.json": {
            "schema_version": "z98-node-attempt-checkpoint-v1",
            "node_id": node["node_id"],
            "fixture_only_non_sendable": rehearsal,
            "attempts": [copy.deepcopy(dict(attempts))],
        },
    }
    payloads = {
        f"{prefix}/{filename}": stable_json_bytes(value)
        for filename, value in four.items()
    }
    refs = {
        filename: sha256_bytes(payloads[f"{prefix}/{filename}"])
        for filename in sorted(four)
    }
    seal_preimage = {
        "schema_version": "z98-node-checkpoint-seal-v1",
        "contract_version": CONTRACT_VERSION,
        "node_id": node["node_id"],
        "node_sequence": node["sequence"],
        "node_kind": node["node_kind"],
        "status": "PASS_FIXTURE_ONLY" if rehearsal else "PASS_FORMAL",
        "fixture_only_non_sendable": rehearsal,
        "artifacts": refs,
        "sealed": True,
    }
    seal = {**seal_preimage, "checkpoint_id": canonical_sha(seal_preimage)}
    payloads[f"{prefix}/05_seal.json"] = stable_json_bytes(seal)
    return payloads


def _build_rehearsal(
    sequence: Mapping[str, Any],
    mappings: Mapping[str, Any],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """用明确标记的 fixture 演算 68 节点，不授权任何真实发送。"""

    mapping_by_path = {
        row["repair_request_path"]: row for row in mappings["mappings"]
    }
    nodes = sequence["nodes"]
    by_id = {node["node_id"]: node for node in nodes}
    payloads: dict[str, bytes] = {}
    repair_runtime: dict[str, dict[str, Any]] = {}
    completed: list[str] = []
    qwen_actual_tokens = 0
    qwen_actual_micro_cny = 0
    dynamic_request_rows: list[dict[str, Any]] = []

    for node in nodes:
        depends = node.get("depends_on", [])
        if any(dependency not in completed for dependency in depends):
            raise Z98Step2HardStop(
                "rehearsal_dependency_gap",
                f"{node['node_id']} 前置节点未完成",
            )
        if node["node_kind"] == "repair":
            request_path = ROOT / node["repair_request_path"]
            request_bytes = request_path.read_bytes()
            if sha256_bytes(request_bytes) != node["repair_request_sha256"]:
                raise Z98Step2HardStop(
                    "repair_request_drift",
                    f"{node['node_id']} 冻结请求 SHA 漂移",
                )
            request_blueprint = json.loads(request_bytes)
            lane = str(node["tested_lane"])
            body = _repair_body(
                request_blueprint,
                lane=lane,
                body_fields=_fixture_lane_fields(lane),
            )
            candidate_bytes = _synthetic_p2_response(request_bytes)
            candidate = json.loads(candidate_bytes)
            candidate_path = (
                f"rehearsal/runtime/{node['node_id']}/raw_response.json"
            )
            call_bytes, usage_bytes = make_synthetic_repair_transport_tickets(
                repair_node=node,
                p2_response_path=candidate_path,
                p2_response_bytes=candidate_bytes,
            )
            call_attempt = json.loads(call_bytes)
            usage = json.loads(usage_bytes)
            repair_runtime[str(node["node_id"])] = {
                "request_bytes": request_bytes,
                "candidate_path": candidate_path,
                "candidate_bytes": candidate_bytes,
                "call_attempt_path": (
                    f"rehearsal/runtime/{node['node_id']}/call_attempt.json"
                ),
                "call_attempt_bytes": call_bytes,
                "usage_path": (
                    f"rehearsal/runtime/{node['node_id']}/usage.json"
                ),
                "usage_bytes": usage_bytes,
            }
            payloads[candidate_path] = candidate_bytes
            payloads[
                f"rehearsal/runtime/{node['node_id']}/call_attempt.json"
            ] = call_bytes
            payloads[
                f"rehearsal/runtime/{node['node_id']}/usage.json"
            ] = usage_bytes
            payloads.update(
                _checkpoint_payloads(
                    node=node,
                    request={
                        "fixture_only_non_sendable": True,
                        "repair_request_path": node["repair_request_path"],
                        "repair_request_sha256": node[
                            "repair_request_sha256"
                        ],
                        "body": body,
                    },
                    response=candidate,
                    usage=usage,
                    attempts=call_attempt,
                    rehearsal=True,
                )
            )
        elif node["node_kind"] == "independent_judge":
            repair_node = by_id[node["depends_on"][0]]
            runtime = repair_runtime[str(repair_node["node_id"])]
            mapping = mapping_by_path[repair_node["repair_request_path"]]
            template_path = R05_ROOT / mapping["verifier_template_path"]
            template = read_json(template_path)
            dynamic = render_dynamic_verifier_request(
                template,
                expected_template_sha256=mapping[
                    "verifier_template_sha256"
                ],
                repair_request_bytes=runtime["request_bytes"],
                p2_response_path=runtime["candidate_path"],
                p2_response_bytes=runtime["candidate_bytes"],
                repair_node=repair_node,
                judge_node=node,
                call_attempt_path=runtime["call_attempt_path"],
                call_attempt_bytes=runtime["call_attempt_bytes"],
                usage_path=runtime["usage_path"],
                usage_bytes=runtime["usage_bytes"],
                actual_accumulated_tokens=qwen_actual_tokens,
                actual_accumulated_micro_cny=qwen_actual_micro_cny,
            )
            verdict_bytes = _synthetic_verdict(template)
            verdict = parse_verifier_content(
                verdict_bytes,
                expected_case_id=template["private_binding"]["case_id"],
                expected_item_ids=template["private_binding"]["item_ids"],
            )
            usage = {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
                "fixture_only_non_sendable": True,
            }
            attempt = {
                "attempt": 1,
                "http_status": 200,
                "finish_reason": "stop",
                "fixture_only_non_sendable": True,
            }
            payloads.update(
                _checkpoint_payloads(
                    node=node,
                    request={
                        **dynamic,
                        "fixture_only_non_sendable": True,
                        "catalog_status": "FIXTURE_NOT_ONLINE_PROOF",
                    },
                    response=verdict,
                    usage=usage,
                    attempts=attempt,
                    rehearsal=True,
                )
            )
            qwen_actual_tokens += 2
            qwen_actual_micro_cny += (
                INPUT_PRICE_CNY_PER_MILLION_TOKENS
                + OUTPUT_PRICE_CNY_PER_MILLION_TOKENS
            )
            dynamic_request_rows.append(
                {
                    "node_id": node["node_id"],
                    "dynamic_request_body_sha256": dynamic["source_binding"][
                        "dynamic_request_body_sha256"
                    ],
                    "token_gate_status": dynamic["budget_preflight"][
                        "token_gate"
                    ]["allowed"],
                    "cost_gate_status": dynamic["budget_preflight"][
                        "cost_gate"
                    ]["allowed"],
                }
            )
        else:
            raise Z98Step2HardStop(
                "unknown_node_kind",
                f"不认识的节点类型：{node['node_kind']}",
            )
        completed.append(str(node["node_id"]))

    if len(completed) != 68 or len(dynamic_request_rows) != 34:
        raise Z98Step2HardStop("rehearsal_incomplete", "68节点预演未完整走通")
    receipt = {
        "schema_version": "z98-step2-full-rehearsal-v1",
        "status": "PASS_FIXTURE_ONLY_NON_SENDABLE",
        "fixture_only_non_sendable": True,
        "completed_nodes": len(completed),
        "repair_nodes": 34,
        "judge_nodes": len(dynamic_request_rows),
        "checkpoint_file_count": 68 * 5,
        "dependency_order_pass": True,
        "dynamic_request_rows": dynamic_request_rows,
        "qwen_fixture_actual_tokens": qwen_actual_tokens,
        "qwen_fixture_actual_micro_cny": qwen_actual_micro_cny,
        "qwen_round_token_cap": TOTAL_TOKEN_CAP,
        "qwen_round_cost_cap_micro_cny": TOTAL_COST_CAP_MICRO_CNY,
        "quality_result": "NOT_RUN_FIXTURE_ONLY",
        "model_api_calls": 0,
        "provider_catalog_requests": 0,
        "network_attempts": 0,
        "secret_values_read": False,
    }
    payloads["rehearsal/full_chain_receipt.json"] = stable_json_bytes(receipt)
    return payloads, receipt


def _build_prepared_base(run_dir: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    sequence, mappings = _read_r05()
    configs = _provider_configs()
    payloads: dict[str, bytes] = {
        "inputs/r05/bundle_manifest.json": (
            R05_ROOT / "bundle_manifest.json"
        ).read_bytes(),
        "inputs/r05/execution/sequence_68.json": (
            R05_ROOT / "execution/sequence_68.json"
        ).read_bytes(),
        "inputs/r05/mappings/verifier_mapping.json": (
            R05_ROOT / "mappings/verifier_mapping.json"
        ).read_bytes(),
        "inputs/r05/receipts/repair_source_immutability.json": (
            R05_ROOT / "receipts/repair_source_immutability.json"
        ).read_bytes(),
        "inputs/r06/hard_stop.json": (R06_ROOT / "hard_stop.json").read_bytes(),
        "inputs/step1/design/comparison_design.json": (
            STEP1_ROOT / "design/comparison_design.json"
        ).read_bytes(),
        "inputs/providers/sensenova.json": SENSENOVA_CONFIG.read_bytes(),
        "inputs/providers/tencent_tokenhub_multi_model.json": (
            TENCENT_CONFIG.read_bytes()
        ),
        "inputs/providers/qianwen_platform_multi_model.json": (
            QWEN_CONFIG.read_bytes()
        ),
    }
    for path in RUNTIME_DEPENDENCIES:
        payloads[
            f"inputs/runtime_dependencies/{path.relative_to(ROOT).as_posix()}"
        ] = path.read_bytes()

    run_nodes: list[dict[str, Any]] = []
    for node in sequence["nodes"]:
        runtime_root = f"runtime/{node['node_id']}"
        row = {
            **copy.deepcopy(node),
            "formal_runtime_paths": {
                "request_artifact": f"{runtime_root}/request_artifact.json",
                "raw_provider_response": (
                    f"{runtime_root}/raw_provider_response.json"
                ),
                "model_content": f"{runtime_root}/model_content.json",
                "call_attempts": f"{runtime_root}/call_attempts.jsonl",
                "usage": f"{runtime_root}/usage.json",
                "checkpoint_root": f"{runtime_root}/checkpoint",
            },
            "resume_rule": (
                "complete checkpoint may be reused as computation only; "
                "attempt reservation without complete checkpoint hard-stops"
            ),
        }
        if node["node_kind"] == "repair":
            row["live_request_body_status"] = (
                "BLOCKED_REPAIR_ENVELOPE_AUTHORITY_MISSING"
            )
            row["fixture_rehearsal_body_status"] = (
                "FIXTURE_ONLY_NON_SENDABLE"
            )
        else:
            row["live_request_body_status"] = (
                "DYNAMIC_AFTER_REPAIR_AND_CATALOG_GATE"
            )
        run_nodes.append(row)
    run_plan = {
        "schema_version": "z98-step2-formal-run-plan-v1",
        "status": "PREPARED_ZERO_CALL_LIVE_BLOCKED",
        "contract_version": CONTRACT_VERSION,
        "run_id": run_dir.name,
        "node_count": 68,
        "repair_count": 34,
        "judge_count": 34,
        "sampling_order": [row["node_id"] for row in run_nodes],
        "nodes": run_nodes,
        "automatic_fallback": False,
        "deepseek_official_api_used": False,
        "rerun_after_attempt_reservation_allowed": False,
    }
    rehearsal_payloads, rehearsal = _build_rehearsal(sequence, mappings)
    payloads.update(rehearsal_payloads)
    payloads["prepared/run_plan.json"] = stable_json_bytes(run_plan)
    payloads["prepared/repair_envelope_authority.schema.json"] = (
        stable_json_bytes(_repair_authority_schema())
    )
    payloads["prepared/qwen_catalog_adapter_contract.json"] = (
        stable_json_bytes(_catalog_adapter_contract())
    )
    payloads["prepared/state_machine_contract.json"] = stable_json_bytes(
        {
            "schema_version": "z98-step2-state-machine-v1",
            "states": [
                "PREPARED",
                "CATALOG_VERIFIED",
                "CLAIMED",
                "NODE_RESERVED",
                "NODE_CHECKPOINTED",
                "HARD_STOPPED",
                "COMPLETED_AWAITING_SCORING",
            ],
            "resume": {
                "allowed_only_for_complete_checkpoint_prefix": True,
                "reservation_without_checkpoint": "HARD_STOP_NO_RESEND",
                "hard_stop_run_resumable": False,
                "manual_sample_selection": False,
            },
            "checkpoint_files": [
                "01_request.json",
                "02_response.json",
                "03_usage.json",
                "04_attempts.json",
                "05_seal.json",
            ],
            "finalize_source": "only 68 immutable checkpoints",
        }
    )
    payloads["prepared/finalize_contract.json"] = stable_json_bytes(
        {
            "schema_version": "z98-step2-finalize-contract-v1",
            "requires_checkpoint_count": 68,
            "requires_repair_judge_pairs": 34,
            "rebuild_usage_from_raw": True,
            "outputs": [
                "usage ledger by provider/lane/chapter/contract",
                "strict legacy scale read-only column",
                "UCR five-layer diagnostic column",
                "three-way comparison input",
                "single versus batch comparison input",
            ],
            "quality_winner_may_be_self_registered": False,
            "partial_completion_may_be_scored": False,
        }
    )
    preflight = {
        "schema_version": "z98-step2-runner-preflight-v1",
        "status": "PASS_ZERO_CALL_EXECUTOR_REHEARSAL_LIVE_BLOCKED",
        "run_id": run_dir.name,
        "r05_manifest_sha256": R05_MANIFEST_SHA256,
        "r06_hard_stop_sha256": R06_HARD_STOP_SHA256,
        "repair_request_set_sha256": REPAIR_REQUEST_SET_SHA256,
        "executor_contract_version": CONTRACT_VERSION,
        "runtime_dependencies": _runtime_dependency_rows(),
        "nodes_rehearsed": rehearsal["completed_nodes"],
        "checkpoint_files_rehearsed": rehearsal["checkpoint_file_count"],
        "repair_envelope_authority": (
            "BLOCKED_REPAIR_ENVELOPE_AUTHORITY_MISSING"
        ),
        "qwen_catalog_gate": (
            "BLOCKED_APPROVED_OFFICIAL_CATALOG_ADAPTER_MISSING"
        ),
        "live_release_allowed": False,
        "fixture_only_non_sendable": True,
        "keys_loaded": False,
        "model_api_calls": 0,
        "provider_catalog_requests": 0,
        "network_attempts": 0,
        "usage_tokens": 0,
        "quality_result": "NOT_REACHED",
        "protected_sources_rewritten": False,
        "provider_config_sha256": {
            provider: canonical_sha(config)
            for provider, config in configs.items()
        },
    }
    payloads["prepared/preflight.json"] = stable_json_bytes(preflight)
    payloads["run_manifest.json"] = stable_json_bytes(
        {
            "schema_version": "z98-step2-runner-manifest-v1",
            "run_id": run_dir.name,
            "status": "PREPARED_ZERO_CALL_LIVE_BLOCKED",
            "r05_mode": "sealed_read_only",
            "r06_mode": "sealed_read_only",
            "fixture_only_non_sendable": True,
            "live_release_allowed": False,
            "rerun_allowed_after_claim": False,
            "quality_result": "NOT_REACHED",
        }
    )
    return payloads, preflight


def _build_prepared_payloads(
    run_dir: Path,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    first, preflight = _build_prepared_base(run_dir)
    second, _ = _build_prepared_base(run_dir)
    if first != second:
        raise Z98Step2HardStop(
            "rehearsal_nondeterministic",
            "r07 零调用全链预演连续两次字节不一致",
        )
    vector = {
        path: sha256_bytes(raw) for path, raw in sorted(first.items())
    }
    verification = {
        "schema_version": "z98-step2-mechanical-double-run-v1",
        "status": "PASS_TWICE_BYTE_IDENTICAL",
        "first_vector": vector,
        "second_vector": vector,
        "vectors_equal": True,
        "vector_sha256": canonical_sha(vector),
        "file_count": len(vector),
        "model_api_calls": 0,
        "provider_catalog_requests": 0,
        "network_attempts": 0,
    }
    payloads = dict(first)
    payloads["prepared/mechanical_double_run.json"] = stable_json_bytes(
        verification
    )
    manifest_rows = [
        {
            "path": path,
            "sha256": sha256_bytes(raw),
            "byte_count": len(raw),
        }
        for path, raw in sorted(payloads.items())
    ]
    payloads["prepared/artifact_manifest.json"] = stable_json_bytes(
        {
            "schema_version": "z98-step2-prepared-artifact-manifest-v1",
            "file_count_excluding_manifest": len(manifest_rows),
            "files": manifest_rows,
        }
    )
    return payloads, preflight


def _guard_prepare_target(run_dir: Path) -> None:
    protected = {STEP1_ROOT.resolve(), R05_ROOT.resolve(), R06_ROOT.resolve()}
    resolved = run_dir.resolve()
    if resolved in protected or any(root in resolved.parents for root in protected):
        raise Z98Step2HardStop(
            "sealed_run_target",
            "r07 不能建在 step1/r05/r06 封存目录内",
        )
    if run_dir.exists() and any(path.is_file() for path in run_dir.rglob("*")):
        raise Z98Step2HardStop(
            "run_directory_exists",
            f"运行目录已存在，拒绝覆盖：{_display_path(run_dir)}",
        )


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    _guard_prepare_target(run_dir)
    payloads, preflight = _build_prepared_payloads(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    for relative, raw in sorted(payloads.items()):
        model_benchmark.write_bytes_exclusive(run_dir / relative, raw)
    verify_prepared(run_dir)
    return preflight


def verify_prepared(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    allow_runtime: bool = False,
) -> dict[str, Any]:
    expected, preflight = _build_prepared_payloads(run_dir)
    for relative, raw in expected.items():
        path = run_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise Z98Step2HardStop(
                "prepared_artifact_drift",
                f"r07 预演工件漂移：{relative}",
            )
    manifest = read_json(run_dir / "prepared/artifact_manifest.json")
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise Z98Step2HardStop("prepared_manifest_invalid", "r07 manifest 非法")
    for row in rows:
        path = run_dir / row["path"]
        if (
            not path.is_file()
            or sha256_file(path) != row["sha256"]
            or path.stat().st_size != row["byte_count"]
        ):
            raise Z98Step2HardStop(
                "prepared_manifest_drift",
                f"r07 manifest 不能重建：{row['path']}",
            )
    if not allow_runtime and (
        (run_dir / "runtime/run_claim.json").is_file()
        or (run_dir / "runtime/hard_stop.json").is_file()
    ):
        raise Z98Step2HardStop(
            "preflight_claim_pollution",
            "零调用预演不得夹入正式 claim 或 hard stop",
        )
    return {
        "status": preflight["status"],
        "run_id": run_dir.name,
        "manifest_sha256": sha256_file(
            run_dir / "prepared/artifact_manifest.json"
        ),
        "mechanical_double_run_sha256": sha256_file(
            run_dir / "prepared/mechanical_double_run.json"
        ),
        "full_chain_receipt_sha256": sha256_file(
            run_dir / "rehearsal/full_chain_receipt.json"
        ),
        "node_count": 68,
        "live_release_allowed": False,
        "model_api_calls": 0,
        "provider_catalog_requests": 0,
        "network_attempts": 0,
    }


def live_preflight(
    run_dir: Path,
    *,
    repair_authority_path: Path | None,
    qwen_catalog_receipt_path: Path | None,
) -> LiveAuthority:
    """验证两张外部权威票；缺票时在密钥与网络之前 fail closed。"""

    _reject_pre_network_hard_stopped_run(run_dir)
    verify_prepared(run_dir)
    if (run_dir / "runtime/run_claim.json").exists():
        raise Z98Step2HardStop(
            "run_already_claimed",
            "本运行编号已有正式占用票，拒绝再次发网",
        )
    if repair_authority_path is None or not repair_authority_path.is_file():
        raise Z98Step2HardStop(
            "repair_envelope_authority_missing",
            "修复请求外壳数值未由真源批准；未读取密钥、未请求目录、未发模型",
        )
    repair_authority = _validate_repair_authority_path(
        repair_authority_path
    )
    if (
        qwen_catalog_receipt_path is None
        or not qwen_catalog_receipt_path.is_file()
    ):
        raise Z98Step2HardStop(
            "qwen_catalog_adapter_missing",
            "千问官方精确型号目录适配票缺失；未读取密钥、未发模型",
        )
    catalog = _validate_catalog_receipt_path(
        qwen_catalog_receipt_path,
        run_dir=run_dir,
        require_fresh=True,
    )
    return LiveAuthority(
        repair_envelope=repair_authority,
        qwen_catalog=catalog,
    )


def _reject_pre_network_hard_stopped_run(
    run_dir: Path,
    *,
    reject_claim_slot: bool = True,
) -> None:
    """硬停票存在即封目录；票体损坏也不构成绕过理由。"""

    if (run_dir / "pre_network_hard_stop.json").exists():
        raise Z98Step2HardStop(
            "pre_network_hard_stopped_run_not_resumable",
            "本运行已有发网前硬停票，禁止同目录重新预检或发网",
        )
    slot = run_dir / "runtime/run_slot.json"
    if reject_claim_slot and slot.exists():
        raise Z98Step2HardStop(
            "run_slot_already_reserved",
            "本运行编号已被另一正式运行或硬停占用",
        )


def _claim_run_slot(run_dir: Path) -> dict[str, Any]:
    payload = {
        "schema_version": "z98-step2-run-slot-v1",
        "status": "CLAIM_RESERVED",
        "run_id": run_dir.name,
        "prepared_manifest_sha256": sha256_file(
            run_dir / "prepared/artifact_manifest.json"
        ),
        "reserved_at": now_iso(),
    }
    try:
        model_benchmark.write_json_exclusive(
            run_dir / "runtime/run_slot.json",
            payload,
        )
    except FileExistsError as exc:
        raise Z98Step2HardStop(
            "run_slot_already_reserved",
            "本运行编号已被另一进程原子占用",
        ) from exc
    return payload


def _write_pre_network_hard_stop(
    run_dir: Path,
    error: BaseException,
    *,
    owned_run_slot_sha256: str | None = None,
) -> None:
    path = run_dir / "pre_network_hard_stop.json"
    slot_path = run_dir / "runtime/run_slot.json"
    if path.exists() or (run_dir / "runtime/run_claim.json").exists():
        return
    if slot_path.exists():
        if (
            owned_run_slot_sha256 is None
            or sha256_file(slot_path) != owned_run_slot_sha256
        ):
            # 另一正式进程已经赢得同一个原子占用槽；不能反向污染它。
            return
    else:
        try:
            model_benchmark.write_json_exclusive(
                slot_path,
                {
                    "schema_version": "z98-step2-run-slot-v1",
                    "status": "HARD_STOP_RESERVED",
                    "run_id": run_dir.name,
                    "prepared_manifest_sha256": sha256_file(
                        run_dir / "prepared/artifact_manifest.json"
                    ),
                    "reserved_at": now_iso(),
                },
            )
        except FileExistsError:
            # 另一正式进程已经赢得同一个原子占用槽；不能反向污染它。
            return
    run_slot_sha256 = sha256_file(slot_path)
    model_benchmark.write_json_exclusive(
        path,
        {
            "schema_version": "z98-step2-pre-network-hard-stop-v1",
            "status": "HARD_STOP_NO_NETWORK_NO_SECRET_READ",
            "reason_code": getattr(error, "reason_code", "preflight_error"),
            "error_type": type(error).__name__,
            "message": str(error),
            "run_slot_sha256": run_slot_sha256,
            "repair_request_set_sha256": REPAIR_REQUEST_SET_SHA256,
            "model_api_calls": 0,
            "provider_catalog_requests": 0,
            "network_attempts": 0,
            "usage_tokens": 0,
            "secret_values_read": False,
            "rerun_in_same_directory_allowed": False,
            "stopped_at": now_iso(),
        },
    )


def command_live_preflight(
    run_dir: Path,
    *,
    repair_authority_path: Path | None,
    qwen_catalog_receipt_path: Path | None,
) -> dict[str, Any]:
    try:
        authority = live_preflight(
            run_dir,
            repair_authority_path=repair_authority_path,
            qwen_catalog_receipt_path=qwen_catalog_receipt_path,
        )
    except BaseException as exc:
        _write_pre_network_hard_stop(run_dir, exc)
        raise
    return {
        "status": "PASS_AUTHORITY_AND_QWEN_CATALOG_RECEIPT",
        "repair_authority_sha256": sha256_file(repair_authority_path),
        "qwen_catalog_receipt_sha256": sha256_file(
            qwen_catalog_receipt_path
        ),
        "qwen_exact_model_id": authority.qwen_catalog["exact_model_id"],
        "keys_loaded": False,
        "network_attempts": 0,
    }


def _usage_triplet(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise Z98Step2HardStop("usage_contract", f"{label} usage 不是对象")
    result: dict[str, int] = {}
    aliases = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    }
    for target, candidates in aliases.items():
        observed = next(
            (value[key] for key in candidates if key in value),
            None,
        )
        if (
            not isinstance(observed, int)
            or isinstance(observed, bool)
            or observed < 0
        ):
            raise Z98Step2HardStop(
                "usage_contract",
                f"{label} 缺合法 {target}",
            )
        result[target] = observed
    if result["prompt_tokens"] + result["completion_tokens"] != result[
        "total_tokens"
    ]:
        raise Z98Step2HardStop(
            "usage_contract",
            f"{label} usage 总数不能由输入与输出相加重建",
        )
    return result


def _checkpoint_root(run_dir: Path, node_id: str) -> Path:
    return run_dir / f"runtime/{node_id}/checkpoint"


def _formal_checkpoint_paths(
    run_dir: Path,
    node_id: str,
) -> dict[str, Path]:
    root = _checkpoint_root(run_dir, node_id)
    return {
        "01_request.json": root / "01_request.json",
        "02_response.json": root / "02_response.json",
        "03_usage.json": root / "03_usage.json",
        "04_attempts.json": root / "04_attempts.json",
        "05_seal.json": root / "05_seal.json",
    }


def _checkpoint_is_complete(run_dir: Path, node_id: str) -> bool:
    root = _checkpoint_root(run_dir, node_id)
    if not root.exists():
        return False
    paths = _formal_checkpoint_paths(run_dir, node_id)
    existing = {path.name for path in root.iterdir()}
    expected = {path.name for path in paths.values()}
    if existing != expected:
        raise Z98Step2HardStop(
            "incomplete_checkpoint",
            f"{node_id} 五件套目录不完整或夹入未知文件，禁止重发",
        )
    return True


def validate_formal_checkpoint(
    run_dir: Path,
    node: Mapping[str, Any],
) -> dict[str, Any]:
    paths = _formal_checkpoint_paths(run_dir, str(node["node_id"]))
    root = _checkpoint_root(run_dir, str(node["node_id"]))
    existing = {name for name, path in paths.items() if path.is_file()}
    if existing and existing != set(paths):
        raise Z98Step2HardStop(
            "incomplete_checkpoint",
            f"{node['node_id']} 五件套不完整，禁止重发",
        )
    if not existing:
        raise Z98Step2HardStop(
            "checkpoint_missing",
            f"{node['node_id']} 检查点不存在",
        )
    if {path.name for path in root.iterdir()} != set(paths):
        raise Z98Step2HardStop(
            "checkpoint_extra_artifact",
            f"{node['node_id']} 五件套目录夹入第六件或未知文件",
        )
    request_doc = read_json(paths["01_request.json"])
    response_doc = read_json(paths["02_response.json"])
    usage_doc = read_json(paths["03_usage.json"])
    attempts_doc = read_json(paths["04_attempts.json"])
    seal = read_json(paths["05_seal.json"])
    preimage = {key: value for key, value in seal.items() if key != "checkpoint_id"}
    authority_chain = _validate_runtime_authority_chain(run_dir)
    expected_seal_keys = {
        "schema_version",
        "contract_version",
        "run_claim_sha256",
        "network_release_sha256",
        "node_id",
        "node_sequence",
        "node_kind",
        "status",
        "fixture_only_non_sendable",
        "artifacts",
        "sealed",
        "checkpoint_id",
    }
    if (
        set(seal) != expected_seal_keys
        or seal.get("schema_version") != "z98-node-checkpoint-seal-v1"
        or seal.get("contract_version") != CONTRACT_VERSION
        or seal.get("run_claim_sha256")
        != authority_chain["run_claim_sha256"]
        or seal.get("network_release_sha256")
        != authority_chain["network_release_sha256"]
        or seal.get("node_id") != node["node_id"]
        or seal.get("node_sequence") != node["sequence"]
        or seal.get("node_kind") != node["node_kind"]
        or seal.get("status") != "PASS_FORMAL"
        or seal.get("fixture_only_non_sendable") is not False
        or seal.get("sealed") is not True
        or seal.get("checkpoint_id") != canonical_sha(preimage)
    ):
        raise Z98Step2HardStop(
            "checkpoint_seal_invalid",
            f"{node['node_id']} 封签身份或 SHA 不能重建",
        )
    refs = seal.get("artifacts")
    expected_names = set(paths) - {"05_seal.json"}
    if not isinstance(refs, Mapping) or set(refs) != expected_names:
        raise Z98Step2HardStop(
            "checkpoint_seal_invalid",
            f"{node['node_id']} 封签没有完整引用四件",
        )
    for name, expected in refs.items():
        if not _is_sha256(expected) or sha256_file(paths[name]) != expected:
            raise Z98Step2HardStop(
                "checkpoint_artifact_drift",
                f"{node['node_id']} 检查点漂移：{name}",
            )
    _validate_formal_checkpoint_records(
        run_dir=run_dir,
        node=node,
        request_doc=request_doc,
        response_doc=response_doc,
        usage_doc=usage_doc,
        attempts_doc=attempts_doc,
    )
    return seal


def _bound_runtime_file(
    run_dir: Path,
    relative: Any,
    *,
    label: str,
) -> Path:
    if not isinstance(relative, str) or not relative:
        raise Z98Step2HardStop(
            "checkpoint_record_invalid",
            f"{label}路径为空",
        )
    path = (run_dir / relative).resolve()
    if not path.is_relative_to(run_dir.resolve()) or not path.is_file():
        raise Z98Step2HardStop(
            "checkpoint_record_invalid",
            f"{label}路径越界或文件不存在",
        )
    return path


def _validate_formal_checkpoint_records(
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    request_doc: Any,
    response_doc: Any,
    usage_doc: Any,
    attempts_doc: Any,
) -> None:
    expected_outer = {
        "01": {
            "schema_version",
            "node_id",
            "node_kind",
            "fixture_only_non_sendable",
            "request",
        },
        "02": {
            "schema_version",
            "node_id",
            "fixture_only_non_sendable",
            "response",
        },
        "03": {
            "schema_version",
            "node_id",
            "fixture_only_non_sendable",
            "usage",
        },
        "04": {
            "schema_version",
            "node_id",
            "fixture_only_non_sendable",
            "attempts",
        },
    }
    docs = {
        "01": request_doc,
        "02": response_doc,
        "03": usage_doc,
        "04": attempts_doc,
    }
    expected_schemas = {
        "01": "z98-node-request-checkpoint-v1",
        "02": "z98-node-response-checkpoint-v1",
        "03": "z98-node-usage-checkpoint-v1",
        "04": "z98-node-attempt-checkpoint-v1",
    }
    node_id = str(node["node_id"])
    for label, document in docs.items():
        if (
            not isinstance(document, Mapping)
            or set(document) != expected_outer[label]
            or document.get("schema_version") != expected_schemas[label]
            or document.get("node_id") != node_id
            or document.get("fixture_only_non_sendable") is not False
        ):
            raise Z98Step2HardStop(
                "checkpoint_record_invalid",
                f"{node_id} 检查点 {label} 外层字段或身份不合同",
            )
    if request_doc.get("node_kind") != node["node_kind"]:
        raise Z98Step2HardStop(
            "checkpoint_record_invalid",
            f"{node_id} 请求件节点类型漂移",
        )
    request_record = request_doc["request"]
    authority_chain = _validate_runtime_authority_chain(run_dir)
    request_keys = {
        "schema_version",
        "run_id",
        "run_claim_sha256",
        "network_release_sha256",
        "node_id",
        "node_sequence",
        "node_kind",
        "provider",
        "model",
        "contract_version",
        "body",
        "_security",
    }
    if (
        not isinstance(request_record, Mapping)
        or set(request_record) != request_keys
        or request_record.get("schema_version")
        != "z98-live-request-artifact-v1"
        or request_record.get("run_id") != run_dir.name
        or request_record.get("run_claim_sha256")
        != authority_chain["run_claim_sha256"]
        or request_record.get("network_release_sha256")
        != authority_chain["network_release_sha256"]
        or request_record.get("node_id") != node_id
        or request_record.get("node_sequence") != node["sequence"]
        or request_record.get("node_kind") != node["node_kind"]
        or request_record.get("provider") != _provider_id_for_node(node)
        or request_record.get("model") != _model_id_for_node(node)
        or request_record.get("contract_version") != CONTRACT_VERSION
        or request_record.get("_security") != "no_api_key_no_authorization"
        or not isinstance(request_record.get("body"), Mapping)
    ):
        raise Z98Step2HardStop(
            "checkpoint_request_binding_invalid",
            f"{node_id} 请求件不能绑定正式节点与供应商",
        )
    body = request_record["body"]
    if body.get("model") != _model_id_for_node(node):
        raise Z98Step2HardStop(
            "checkpoint_request_binding_invalid",
            f"{node_id} 请求 body 模型漂移",
        )
    request_artifact = run_dir / f"runtime/{node_id}/request_artifact.json"
    request_artifact_record = (
        read_json(request_artifact) if request_artifact.is_file() else None
    )
    if (
        not request_artifact.is_file()
        or request_artifact_record != request_record
    ):
        raise Z98Step2HardStop(
            "checkpoint_request_binding_invalid",
            f"{node_id} 检查点请求件不等于实发请求工件",
        )
    request_sha = sha256_file(request_artifact)
    wire_sha = sha256_bytes(
        json.dumps(
            request_artifact_record["body"],
            ensure_ascii=False,
        ).encode("utf-8")
    )

    attempts = attempts_doc["attempts"]
    if not isinstance(attempts, list) or not attempts:
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 检查点没有网络尝试",
        )
    try:
        z83_retry_transport.validate_attempt_rows(attempts)
    except ZBatchError as exc:
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 尝试账字段或SHA不合同：{exc}",
        ) from exc
    if any(
        row.get("logical_request_id") != node_id
        or row.get("request_artifact_sha256") != request_sha
        or row.get("wire_body_sha256") != wire_sha
        for row in attempts
    ):
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 尝试账没有绑定请求工件与线上字节",
        )
    global_ledger = run_dir / f"runtime/{node_id}/transport/call_attempts.jsonl"
    if _attempt_rows(global_ledger) != attempts:
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 五件套尝试账与运输原账不一致",
        )
    reservations = _attempt_rows(
        run_dir / f"runtime/{node_id}/transport/attempt_reservations.jsonl"
    )
    if len(reservations) != len(attempts):
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 占用票数量与真实尝试数不一致",
        )
    for reservation, attempt in zip(
        reservations,
        attempts,
        strict=True,
    ):
        reservation_preimage = {
            key: value
            for key, value in reservation.items()
            if key != "row_sha256"
        }
        if (
            reservation.get("schema_version")
            != "model-benchmark-attempt-reservation-v1"
            or reservation.get("logical_request_id") != node_id
            or reservation.get("attempt") != attempt.get("attempt")
            or reservation.get("request_artifact_sha256") != request_sha
            or reservation.get("wire_body_sha256") != wire_sha
            or reservation.get("row_sha256")
            != canonical_sha(reservation_preimage)
        ):
            raise Z98Step2HardStop(
                "checkpoint_attempt_binding_invalid",
                f"{node_id} 占用票不能逐行绑定真实尝试",
            )
    try:
        z83_retry_transport.validate_retry_wait_sequence(
            global_ledger,
            attempts,
            require_all_429_completed=True,
        )
    except ZBatchError as exc:
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 429等待票不能与运输账重建：{exc}",
        ) from exc
    if (
        attempts[-1].get("http_status") != 200
        or attempts[-1].get("outcome") != "success"
        or attempts[-1].get("usage_status") != "returned"
    ):
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 正式PASS封签最后一次尝试不是HTTP 200成功",
        )
    if (
        len(attempts) > 3
        or [row.get("attempt") for row in attempts]
        != list(range(1, len(attempts) + 1))
        or any(row.get("http_status") != 429 for row in attempts[:-1])
    ):
        raise Z98Step2HardStop(
            "checkpoint_attempt_binding_invalid",
            f"{node_id} 尝试序列不是至多两次429后唯一成功",
        )

    usage = _usage_triplet(usage_doc["usage"], node_id)
    if _usage_triplet(attempts[-1].get("usage"), node_id) != usage:
        raise Z98Step2HardStop(
            "checkpoint_usage_binding_invalid",
            f"{node_id} usage件不等于成功运输原账",
        )
    response_record = response_doc["response"]
    common_response_keys = {
        "provider_response_path",
        "provider_response_sha256",
        "model_content_path",
        "model_content_sha256",
        "response_model",
        "finish_reason",
        "reasoning_content_sha256",
    }
    if node["node_kind"] == "repair":
        expected_response_keys = common_response_keys | {
            "candidate",
            "normalized_call_attempt_path",
            "normalized_call_attempt_sha256",
            "normalized_usage_path",
            "normalized_usage_sha256",
        }
    else:
        expected_response_keys = common_response_keys | {
            "verdict",
            "dynamic_source_binding",
            "budget_preflight",
            "budget_reservation_path",
            "budget_reservation_sha256",
            "budget_settlement_path",
            "budget_settlement_sha256",
        }
    if (
        not isinstance(response_record, Mapping)
        or set(response_record) != expected_response_keys
        or response_record.get("finish_reason") != "stop"
        or not _is_sha256(response_record.get("reasoning_content_sha256"))
    ):
        raise Z98Step2HardStop(
            "checkpoint_response_binding_invalid",
            f"{node_id} 响应件字段或finish_reason不合同",
        )
    raw_path = _bound_runtime_file(
        run_dir,
        response_record["provider_response_path"],
        label=f"{node_id}原始响应",
    )
    content_path = _bound_runtime_file(
        run_dir,
        response_record["model_content_path"],
        label=f"{node_id}模型正文",
    )
    if (
        sha256_file(raw_path) != response_record["provider_response_sha256"]
        or sha256_file(content_path) != response_record["model_content_sha256"]
        or attempts[-1].get("raw_response_sha256")
        != response_record["provider_response_sha256"]
    ):
        raise Z98Step2HardStop(
            "checkpoint_response_binding_invalid",
            f"{node_id} 响应原字节或正文SHA漂移",
        )
    transport_raw = (
        run_dir
        / f"runtime/{node_id}/transport/raw_responses/"
        f"attempt{int(attempts[-1]['attempt']):02d}.json"
    )
    if (
        not transport_raw.is_file()
        or transport_raw.read_bytes() != raw_path.read_bytes()
    ):
        raise Z98Step2HardStop(
            "checkpoint_response_binding_invalid",
            f"{node_id} 响应副本不能追溯到成功运输的原始响应",
        )
    raw_response = read_json(raw_path)
    parsed, content, reasoning, finish = model_benchmark.response_envelope(
        raw_response,
        _model_id_for_node(node),
        require_nonempty_reasoning=False,
    )
    if (
        finish != "stop"
        or content_path.read_bytes() != content.encode("utf-8")
        or raw_response.get("model") != response_record["response_model"]
        or sha256_bytes(reasoning.encode("utf-8"))
        != response_record["reasoning_content_sha256"]
        or _usage_triplet(raw_response.get("usage"), node_id) != usage
    ):
        raise Z98Step2HardStop(
            "checkpoint_response_binding_invalid",
            f"{node_id} 响应件不能从供应商原始响应重建",
        )
    if node["node_kind"] == "repair":
        repair_request = read_json(ROOT / str(node["repair_request_path"]))
        rebuilt_candidate = _validate_repair_candidate(
            node,
            parsed,
            repair_request,
        )
        if rebuilt_candidate != response_record["candidate"]:
            raise Z98Step2HardStop(
                "checkpoint_response_binding_invalid",
                f"{node_id} 修复候选不能从原始模型正文按冻结合同重建",
            )
        for path_field, sha_field in (
            (
                "normalized_call_attempt_path",
                "normalized_call_attempt_sha256",
            ),
            ("normalized_usage_path", "normalized_usage_sha256"),
        ):
            normalized = _bound_runtime_file(
                run_dir,
                response_record[path_field],
                label=f"{node_id}{path_field}",
            )
            if sha256_file(normalized) != response_record[sha_field]:
                raise Z98Step2HardStop(
                    "checkpoint_response_binding_invalid",
                    f"{node_id} 归一运输票SHA漂移",
                )
    else:
        reservation_path, settlement_path = _qwen_budget_paths(
            run_dir,
            node_id,
        )
        if (
            response_record["budget_reservation_path"]
            != reservation_path.relative_to(run_dir).as_posix()
            or response_record["budget_settlement_path"]
            != settlement_path.relative_to(run_dir).as_posix()
            or sha256_file(reservation_path)
            != response_record["budget_reservation_sha256"]
            or sha256_file(settlement_path)
            != response_record["budget_settlement_sha256"]
        ):
            raise Z98Step2HardStop(
                "qwen_budget_receipt_invalid",
                f"{node_id} 响应件没有绑定预算预占与结算票",
            )
        _validate_qwen_budget_receipts(run_dir, node)
        nodes = read_json(run_dir / "prepared/run_plan.json")["nodes"]
        nodes_by_id = {str(row["node_id"]): row for row in nodes}
        repair_node = nodes_by_id[str(node["depends_on"][0])]
        mappings = read_json(
            run_dir / "inputs/r05/mappings/verifier_mapping.json"
        )["mappings"]
        mapping = next(
            row
            for row in mappings
            if row["repair_request_path"] == repair_node["repair_request_path"]
        )
        template = read_json(
            R05_ROOT / str(mapping["verifier_template_path"])
        )
        rebuilt_verdict = parse_verifier_content(
            content,
            expected_case_id=template["private_binding"]["case_id"],
            expected_item_ids=template["private_binding"]["item_ids"],
        )
        if rebuilt_verdict != response_record["verdict"]:
            raise Z98Step2HardStop(
                "checkpoint_response_binding_invalid",
                f"{node_id} 裁判判词不能从原始模型正文按冻结合同重建",
            )
        qwen_tokens, qwen_cost = _qwen_actual_totals_before_node(
            run_dir,
            nodes,
            node_id=node_id,
        )
        repair_root = run_dir / f"runtime/{repair_node['node_id']}"
        rebuilt_dynamic = render_dynamic_verifier_request(
            template,
            expected_template_sha256=str(
                mapping["verifier_template_sha256"]
            ),
            repair_request_bytes=(
                ROOT / str(repair_node["repair_request_path"])
            ).read_bytes(),
            p2_response_path=(
                repair_root / "model_content.json"
            ).relative_to(run_dir).as_posix(),
            p2_response_bytes=(
                repair_root / "model_content.json"
            ).read_bytes(),
            repair_node=repair_node,
            judge_node=node,
            call_attempt_path=(
                repair_root / "call_attempt.json"
            ).relative_to(run_dir).as_posix(),
            call_attempt_bytes=(repair_root / "call_attempt.json").read_bytes(),
            usage_path=(
                repair_root / "usage.json"
            ).relative_to(run_dir).as_posix(),
            usage_bytes=(repair_root / "usage.json").read_bytes(),
            actual_accumulated_tokens=qwen_tokens,
            actual_accumulated_micro_cny=qwen_cost,
        )
        if (
            rebuilt_dynamic["request_body"] != body
            or rebuilt_dynamic["source_binding"]
            != response_record["dynamic_source_binding"]
            or rebuilt_dynamic["budget_preflight"]
            != response_record["budget_preflight"]
        ):
            raise Z98Step2HardStop(
                "checkpoint_dynamic_binding_invalid",
                f"{node_id} 动态裁判请求不能由前置修复工件与累计预算重建",
            )
        _validate_qwen_budget_receipts(
            run_dir,
            node,
            expected_budget_preflight=rebuilt_dynamic["budget_preflight"],
            expected_accumulated_tokens=qwen_tokens,
            expected_accumulated_micro_cny=qwen_cost,
        )


def _attempt_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Z98Step2HardStop(
                    "attempt_ledger_invalid",
                    f"{_display_path(path)} 含非对象行",
                )
            rows.append(value)
    return rows


def _node_has_attempt_evidence(run_dir: Path, node_id: str) -> bool:
    node_root = run_dir / f"runtime/{node_id}"
    root = node_root / "transport"
    candidates = (
        root / "attempt_reservations.jsonl",
        root / "call_attempts.jsonl",
        root / "raw_responses",
        node_root / "request_artifact.json",
        node_root / "raw_provider_response.json",
        node_root / "model_content.json",
        node_root / "call_attempt.json",
        node_root / "usage.json",
        node_root / "qwen_budget_reservation.json",
        node_root / "qwen_budget_settlement.json",
        node_root / "checkpoint",
    )
    return any(
        (path.is_file() and path.stat().st_size > 0)
        or (path.is_dir() and any(child.is_file() for child in path.rglob("*")))
        for path in candidates
    )


def audit_resume_position(run_dir: Path) -> dict[str, Any]:
    """只认完整前缀；占用票后缺封签时永不重发该节点。"""

    plan = read_json(run_dir / "prepared/run_plan.json")
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 68:
        raise Z98Step2HardStop("run_plan_invalid", "正式 run plan 不是 68 节点")
    completed: list[str] = []
    first_open: str | None = None
    for node in nodes:
        node_id = str(node["node_id"])
        if _checkpoint_is_complete(run_dir, node_id):
            if first_open is not None:
                raise Z98Step2HardStop(
                    "checkpoint_noncontiguous",
                    "完整检查点不是连续前缀，疑似人工挑样",
                )
            validate_formal_checkpoint(run_dir, node)
            completed.append(node_id)
            continue
        if _node_has_attempt_evidence(run_dir, node_id):
            raise Z98Step2HardStop(
                "attempt_without_checkpoint",
                f"{node_id} 已有占用或响应但无完整五件套，禁止同目录重发",
            )
        if first_open is None:
            first_open = node_id
    return {
        "status": (
            "COMPLETE_68"
            if len(completed) == 68
            else "RESUMABLE_AT_NEXT_UNATTEMPTED_NODE"
        ),
        "completed_prefix_count": len(completed),
        "completed_node_ids": completed,
        "next_node_id": first_open,
        "attempted_node_may_be_resent": False,
        "quality_result": "UNJUDGED",
    }


def _write_formal_checkpoint(
    run_dir: Path,
    *,
    node: Mapping[str, Any],
    request_record: Mapping[str, Any],
    response_record: Mapping[str, Any],
    usage: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    authority_chain = _validate_runtime_authority_chain(run_dir)
    paths = _formal_checkpoint_paths(run_dir, str(node["node_id"]))
    root = _checkpoint_root(run_dir, str(node["node_id"]))
    if root.exists() and any(root.iterdir()):
        raise Z98Step2HardStop(
            "checkpoint_already_exists",
            f"{node['node_id']} 五件套已有内容，拒绝覆盖",
        )
    payload_values = {
        "01_request.json": {
            "schema_version": "z98-node-request-checkpoint-v1",
            "node_id": node["node_id"],
            "node_kind": node["node_kind"],
            "fixture_only_non_sendable": False,
            "request": copy.deepcopy(dict(request_record)),
        },
        "02_response.json": {
            "schema_version": "z98-node-response-checkpoint-v1",
            "node_id": node["node_id"],
            "fixture_only_non_sendable": False,
            "response": copy.deepcopy(dict(response_record)),
        },
        "03_usage.json": {
            "schema_version": "z98-node-usage-checkpoint-v1",
            "node_id": node["node_id"],
            "fixture_only_non_sendable": False,
            "usage": copy.deepcopy(dict(usage)),
        },
        "04_attempts.json": {
            "schema_version": "z98-node-attempt-checkpoint-v1",
            "node_id": node["node_id"],
            "fixture_only_non_sendable": False,
            "attempts": [copy.deepcopy(dict(row)) for row in attempts],
        },
    }
    for name, value in payload_values.items():
        model_benchmark.write_bytes_exclusive(paths[name], stable_json_bytes(value))
    refs = {
        name: sha256_file(paths[name])
        for name in sorted(payload_values)
    }
    seal_preimage = {
        "schema_version": "z98-node-checkpoint-seal-v1",
        "contract_version": CONTRACT_VERSION,
        "run_claim_sha256": authority_chain["run_claim_sha256"],
        "network_release_sha256": authority_chain[
            "network_release_sha256"
        ],
        "node_id": node["node_id"],
        "node_sequence": node["sequence"],
        "node_kind": node["node_kind"],
        "status": "PASS_FORMAL",
        "fixture_only_non_sendable": False,
        "artifacts": refs,
        "sealed": True,
    }
    seal = {**seal_preimage, "checkpoint_id": canonical_sha(seal_preimage)}
    model_benchmark.write_json_exclusive(paths["05_seal.json"], seal)
    validate_formal_checkpoint(run_dir, node)
    return seal


def _key_env_for_node(node: Mapping[str, Any]) -> str:
    if node["node_kind"] == "independent_judge":
        return QWEN_KEY_ENV
    return LANE_CONTRACTS[str(node["tested_lane"])]["api_key_env"]


def _provider_id_for_node(node: Mapping[str, Any]) -> str:
    if node["node_kind"] == "independent_judge":
        return QWEN_PROVIDER_ID
    return str(node["tested_provider"])


def _model_id_for_node(node: Mapping[str, Any]) -> str:
    if node["node_kind"] == "independent_judge":
        return QWEN_MODEL_ID
    return str(node["tested_model"])


def _provider_timeout(provider_id: str) -> int:
    return 120 if provider_id == QWEN_PROVIDER_ID else 600


def _default_send_node(
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    provider: Mapping[str, Any],
    key: str,
    body: Mapping[str, Any],
    state: z83_retry_transport.RetryRunState,
    policy: z83_retry_transport.RetryPolicy,
    opener: Any = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    jitter: Callable[[], float] | None = None,
) -> z83_retry_transport.LogicalRequestResult:
    node_id = str(node["node_id"])
    node_root = run_dir / f"runtime/{node_id}"
    request_record = {
        "schema_version": "z98-live-request-artifact-v1",
        "run_id": run_dir.name,
        **_validate_runtime_authority_chain(run_dir),
        "node_id": node_id,
        "node_sequence": node["sequence"],
        "node_kind": node["node_kind"],
        "provider": _provider_id_for_node(node),
        "model": _model_id_for_node(node),
        "contract_version": CONTRACT_VERSION,
        "body": copy.deepcopy(dict(body)),
        "_security": "no_api_key_no_authorization",
    }
    request_path = node_root / "request_artifact.json"
    model_benchmark.write_json_exclusive(request_path, request_record)
    request_sha = sha256_file(request_path)
    wire = json.dumps(body, ensure_ascii=False).encode("utf-8")
    wire_sha = sha256_bytes(wire)
    if key.encode("utf-8") in request_path.read_bytes():
        raise Z98Step2HardStop(
            "secret_in_request",
            f"{node_id} 请求工件意外包含 API Key",
        )

    actual_open = opener
    if actual_open is None:
        import urllib.request

        actual_open = urllib.request.build_opener(
            model_benchmark._NoRedirectHandler()
        ).open
    timeout_seconds = _provider_timeout(_provider_id_for_node(node))

    def timeout_adapter(request: Any, timeout: int = 0) -> Any:
        del timeout
        return actual_open(request, timeout=timeout_seconds)

    logical = z83_retry_transport.run_logical_request(
        logical_request_id=node_id,
        chapter=_chapter_number(str(node["chapter_id"])),
        send_once=model_benchmark.send_once_factory(
            root=node_root,
            provider=provider,
            key=key,
            logical_request_id=node_id,
            request_sha=request_sha,
            wire_body=wire,
            wire_sha=wire_sha,
            opener=timeout_adapter,
        ),
        attempt_ledger_path=node_root / "transport/call_attempts.jsonl",
        contract_version=CONTRACT_VERSION,
        state=state,
        policy=policy,
        sleeper=sleeper,
        monotonic=monotonic,
        jitter=jitter,
    )
    return logical


NodeSender = Callable[..., z83_retry_transport.LogicalRequestResult]


def _response_parts(
    result: z83_retry_transport.LogicalRequestResult,
    *,
    requested_model: str,
    require_reasoning: bool,
) -> tuple[dict[str, Any], str, str, str, Path]:
    payload = result.outcome.payload
    if not isinstance(payload, Mapping):
        raise Z98Step2HardStop(
            "response_envelope",
            "成功运输结果没有响应对象",
        )
    response = payload.get("response_json")
    raw_path = payload.get("raw_path")
    if not isinstance(response, Mapping) or not isinstance(raw_path, Path):
        raise Z98Step2HardStop(
            "response_envelope",
            "HTTP 200 响应外壳不是合法对象",
        )
    try:
        model_data, content, reasoning, finish = model_benchmark.response_envelope(
            response,
            requested_model,
            require_nonempty_reasoning=require_reasoning,
        )
    except BaseException as exc:
        raise Z98Step2HardStop(
            getattr(exc, "reason_code", "response_envelope"),
            str(exc),
        ) from exc
    return model_data, content, reasoning, finish, raw_path


def _repair_normalized_tickets(
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    model_content_path: Path,
    model_content_bytes: bytes,
    result: z83_retry_transport.LogicalRequestResult,
    usage: Mapping[str, int],
) -> tuple[str, bytes, str, bytes]:
    response_path = model_content_path.relative_to(run_dir).as_posix()
    response_sha = sha256_bytes(model_content_bytes)
    common = {
        "node_id": node["node_id"],
        "tested_lane": node["tested_lane"],
        "provider": node["tested_provider"],
        "model": node["tested_model"],
        "request_path": node["repair_request_path"],
        "request_sha256": node["repair_request_sha256"],
        "response_path": response_path,
        "response_sha256": response_sha,
    }
    success_rows = [
        row
        for row in result.attempt_rows
        if row.get("outcome") == "success"
    ]
    if len(success_rows) != 1:
        raise Z98Step2HardStop(
            "attempt_ledger_invalid",
            f"{node['node_id']} 必须恰好一条成功尝试",
        )
    success = success_rows[0]
    call_attempt = {
        "schema_version": "z98-repair-call-attempt-v1",
        **common,
        "attempt_number": int(success["attempt"]),
        "http_status": int(success["http_status"]),
        "finish_reason": "stop",
    }
    usage_record = {
        "schema_version": "z98-repair-usage-v1",
        **common,
        **dict(usage),
    }
    node_root = run_dir / f"runtime/{node['node_id']}"
    call_path = node_root / "call_attempt.json"
    usage_path = node_root / "usage.json"
    call_bytes = stable_json_bytes(call_attempt)
    usage_bytes = stable_json_bytes(usage_record)
    model_benchmark.write_bytes_exclusive(call_path, call_bytes)
    model_benchmark.write_bytes_exclusive(usage_path, usage_bytes)
    return (
        call_path.relative_to(run_dir).as_posix(),
        call_bytes,
        usage_path.relative_to(run_dir).as_posix(),
        usage_bytes,
    )


def _validate_repair_candidate(
    node: Mapping[str, Any],
    model_data: Mapping[str, Any],
    repair_request: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        if node["contract_mode"] == "single_patch":
            return {
                "contract_mode": "single_patch",
                "payload": validate_patch(model_data),
            }
        slot_ids = repair_request.get("slot_ids")
        if not isinstance(slot_ids, list):
            raise Z98ContractError("batch blueprint 缺 slot_ids")
        return {
            "contract_mode": "atom_batch_v2",
            "payload": validate_atom_batch(
                model_data,
                expected_slot_ids=slot_ids,
            ),
        }
    except Z98ContractError as exc:
        raise Z98Step2HardStop(
            "repair_structure_rejected",
            f"{node['node_id']} 修复响应合同拒收：{exc}",
        ) from exc


def _qwen_actual_totals(
    run_dir: Path,
    nodes: Sequence[Mapping[str, Any]],
) -> tuple[int, int]:
    """返回硬帽占用；含成功 usage 与已发生 429 的保守负债。"""

    tokens = 0
    cost = 0
    for node in nodes:
        if node["node_kind"] != "independent_judge":
            continue
        if not _checkpoint_is_complete(run_dir, str(node["node_id"])):
            continue
        settlement = _validate_qwen_budget_receipts(
            run_dir,
            node,
            _skip_dynamic_binding=True,
        )
        tokens += int(settlement["hard_cap_accounted_tokens"])
        cost += int(settlement["hard_cap_accounted_micro_cny"])
    return tokens, cost


def _qwen_actual_totals_before_node(
    run_dir: Path,
    nodes: Sequence[Mapping[str, Any]],
    *,
    node_id: str,
) -> tuple[int, int]:
    """按冻结顺序重建某裁判节点发送前已经发生的千问正式 usage。"""

    tokens = 0
    cost = 0
    found = False
    for row in nodes:
        if str(row["node_id"]) == node_id:
            found = True
            break
        if row["node_kind"] != "independent_judge":
            continue
        if not _checkpoint_is_complete(run_dir, str(row["node_id"])):
            raise Z98Step2HardStop(
                "checkpoint_dynamic_binding_invalid",
                f"{node_id} 前置裁判节点缺正式封签，不能重建累计预算",
            )
        settlement = _validate_qwen_budget_receipts(
            run_dir,
            row,
            _skip_dynamic_binding=True,
        )
        tokens += int(settlement["hard_cap_accounted_tokens"])
        cost += int(settlement["hard_cap_accounted_micro_cny"])
    if not found:
        raise Z98Step2HardStop(
            "checkpoint_dynamic_binding_invalid",
            f"run plan 找不到裁判节点 {node_id}",
        )
    return tokens, cost


def _qwen_budget_paths(
    run_dir: Path,
    node_id: str,
) -> tuple[Path, Path]:
    root = run_dir / f"runtime/{node_id}"
    return (
        root / "qwen_budget_reservation.json",
        root / "qwen_budget_settlement.json",
    )


def _write_qwen_budget_reservation(
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    budget_preflight: Mapping[str, Any],
    accumulated_tokens: int,
    accumulated_micro_cny: int,
    max_attempts: int,
) -> dict[str, Any]:
    projection = int(
        budget_preflight["conservative_total_token_projection"]
    )
    projection_cost = int(
        budget_preflight["conservative_cost_projection_micro_cny"]
    )
    reserved_tokens = projection * max_attempts
    reserved_cost = projection_cost * max_attempts
    if accumulated_tokens + reserved_tokens > TOTAL_TOKEN_CAP:
        raise Z98Step2HardStop(
            "qwen_retry_reservation_token_cap_exceeded",
            "裁判最多三次尝试的保守 token 预占将超过 50 万帽",
        )
    if accumulated_micro_cny + reserved_cost > TOTAL_COST_CAP_MICRO_CNY:
        raise Z98Step2HardStop(
            "qwen_retry_reservation_cost_cap_exceeded",
            "裁判最多三次尝试的保守金额预占将超过 10 元帽",
        )
    payload = {
        "schema_version": "z98-qwen-retry-budget-reservation-v1",
        "node_id": node["node_id"],
        "budget_preflight_sha256": canonical_sha(budget_preflight),
        "max_attempts": max_attempts,
        "per_attempt_conservative_token_upper_bound": projection,
        "per_attempt_conservative_cost_upper_bound_micro_cny": projection_cost,
        "accumulated_hard_cap_tokens_before": accumulated_tokens,
        "accumulated_hard_cap_micro_cny_before": accumulated_micro_cny,
        "reserved_hard_cap_tokens": reserved_tokens,
        "reserved_hard_cap_micro_cny": reserved_cost,
        "round_token_cap": TOTAL_TOKEN_CAP,
        "round_cost_cap_micro_cny": TOTAL_COST_CAP_MICRO_CNY,
        "written_before_attempt_reservation": True,
    }
    path, _ = _qwen_budget_paths(run_dir, str(node["node_id"]))
    model_benchmark.write_json_exclusive(path, payload)
    return payload


def _write_qwen_budget_settlement(
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    reservation: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    usage: Mapping[str, int],
) -> dict[str, Any]:
    unknown_count = sum(
        1
        for row in attempts
        if row.get("http_status") == 429
        and row.get("usage") == z83_retry_transport.UNKNOWN_USAGE
    )
    actual_cost = (
        int(usage["prompt_tokens"])
        * INPUT_PRICE_CNY_PER_MILLION_TOKENS
        + int(usage["completion_tokens"])
        * OUTPUT_PRICE_CNY_PER_MILLION_TOKENS
    )
    unknown_tokens = (
        unknown_count
        * int(reservation["per_attempt_conservative_token_upper_bound"])
    )
    unknown_cost = (
        unknown_count
        * int(
            reservation[
                "per_attempt_conservative_cost_upper_bound_micro_cny"
            ]
        )
    )
    payload = {
        "schema_version": "z98-qwen-retry-budget-settlement-v1",
        "node_id": node["node_id"],
        "reservation_sha256": canonical_sha(reservation),
        "network_attempt_count": len(attempts),
        "unknown_429_count": unknown_count,
        "actual_success_usage": dict(usage),
        "actual_success_micro_cny": actual_cost,
        "unknown_token_conservative_upper_bound": unknown_tokens,
        "unknown_cost_conservative_upper_bound_micro_cny": unknown_cost,
        "hard_cap_accounted_tokens": int(usage["total_tokens"])
        + unknown_tokens,
        "hard_cap_accounted_micro_cny": actual_cost + unknown_cost,
        "unused_attempt_reservation_released": (
            int(reservation["max_attempts"]) - len(attempts)
        ),
        "unknown_usage_not_recorded_as_zero": True,
    }
    _, path = _qwen_budget_paths(run_dir, str(node["node_id"]))
    model_benchmark.write_json_exclusive(path, payload)
    return payload


def _validate_qwen_budget_receipts(
    run_dir: Path,
    node: Mapping[str, Any],
    *,
    expected_budget_preflight: Mapping[str, Any] | None = None,
    expected_accumulated_tokens: int | None = None,
    expected_accumulated_micro_cny: int | None = None,
    _skip_dynamic_binding: bool = False,
) -> dict[str, Any]:
    node_id = str(node["node_id"])
    if expected_budget_preflight is None and not _skip_dynamic_binding:
        response_checkpoint = _formal_checkpoint_paths(
            run_dir,
            node_id,
        )["02_response.json"]
        if response_checkpoint.is_file():
            response_value = read_json(response_checkpoint).get("response")
            if isinstance(response_value, Mapping) and isinstance(
                response_value.get("budget_preflight"),
                Mapping,
            ):
                expected_budget_preflight = response_value[
                    "budget_preflight"
                ]
                plan_nodes = read_json(
                    run_dir / "prepared/run_plan.json"
                )["nodes"]
                (
                    expected_accumulated_tokens,
                    expected_accumulated_micro_cny,
                ) = _qwen_actual_totals_before_node(
                    run_dir,
                    plan_nodes,
                    node_id=node_id,
                )
    reservation_path, settlement_path = _qwen_budget_paths(run_dir, node_id)
    if not reservation_path.is_file() or not settlement_path.is_file():
        raise Z98Step2HardStop(
            "qwen_budget_receipt_missing",
            f"{node_id} 缺预算预占或结算票",
        )
    reservation = read_json(reservation_path)
    settlement = read_json(settlement_path)
    expected_reservation_keys = {
        "schema_version",
        "node_id",
        "budget_preflight_sha256",
        "max_attempts",
        "per_attempt_conservative_token_upper_bound",
        "per_attempt_conservative_cost_upper_bound_micro_cny",
        "accumulated_hard_cap_tokens_before",
        "accumulated_hard_cap_micro_cny_before",
        "reserved_hard_cap_tokens",
        "reserved_hard_cap_micro_cny",
        "round_token_cap",
        "round_cost_cap_micro_cny",
        "written_before_attempt_reservation",
    }
    expected_settlement_keys = {
        "schema_version",
        "node_id",
        "reservation_sha256",
        "network_attempt_count",
        "unknown_429_count",
        "actual_success_usage",
        "actual_success_micro_cny",
        "unknown_token_conservative_upper_bound",
        "unknown_cost_conservative_upper_bound_micro_cny",
        "hard_cap_accounted_tokens",
        "hard_cap_accounted_micro_cny",
        "unused_attempt_reservation_released",
        "unknown_usage_not_recorded_as_zero",
    }
    if (
        set(reservation) != expected_reservation_keys
        or reservation.get("schema_version")
        != "z98-qwen-retry-budget-reservation-v1"
        or reservation.get("node_id") != node_id
        or reservation.get("max_attempts") != 3
        or reservation.get("round_token_cap") != TOTAL_TOKEN_CAP
        or reservation.get("round_cost_cap_micro_cny")
        != TOTAL_COST_CAP_MICRO_CNY
        or reservation.get("written_before_attempt_reservation") is not True
        or set(settlement) != expected_settlement_keys
        or settlement.get("schema_version")
        != "z98-qwen-retry-budget-settlement-v1"
        or settlement.get("node_id") != node_id
        or settlement.get("reservation_sha256")
        != canonical_sha(reservation)
        or settlement.get("unknown_usage_not_recorded_as_zero") is not True
    ):
        raise Z98Step2HardStop(
            "qwen_budget_receipt_invalid",
            f"{node_id} 预算预占或结算票字段不合同",
        )
    token_upper = reservation.get(
        "per_attempt_conservative_token_upper_bound"
    )
    cost_upper = reservation.get(
        "per_attempt_conservative_cost_upper_bound_micro_cny"
    )
    accumulated_tokens = reservation.get(
        "accumulated_hard_cap_tokens_before"
    )
    accumulated_cost = reservation.get(
        "accumulated_hard_cap_micro_cny_before"
    )
    if (
        not all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in (
                token_upper,
                cost_upper,
                accumulated_tokens,
                accumulated_cost,
            )
        )
        or reservation.get("reserved_hard_cap_tokens") != token_upper * 3
        or reservation.get("reserved_hard_cap_micro_cny") != cost_upper * 3
        or accumulated_tokens + token_upper * 3 > TOTAL_TOKEN_CAP
        or accumulated_cost + cost_upper * 3 > TOTAL_COST_CAP_MICRO_CNY
    ):
        raise Z98Step2HardStop(
            "qwen_budget_receipt_invalid",
            f"{node_id} 预算预占数字不能由单次上界与整轮帽重建",
        )
    if expected_budget_preflight is not None:
        expected_token_upper = int(
            expected_budget_preflight[
                "conservative_total_token_projection"
            ]
        )
        expected_cost_upper = int(
            expected_budget_preflight[
                "conservative_cost_projection_micro_cny"
            ]
        )
        if (
            reservation.get("budget_preflight_sha256")
            != canonical_sha(expected_budget_preflight)
            or token_upper != expected_token_upper
            or cost_upper != expected_cost_upper
            or accumulated_tokens != expected_accumulated_tokens
            or accumulated_cost != expected_accumulated_micro_cny
        ):
            raise Z98Step2HardStop(
                "qwen_budget_receipt_invalid",
                f"{node_id} 预算预占未绑定动态请求与此前正式结算",
            )
    attempts = read_json(
        _formal_checkpoint_paths(run_dir, node_id)["04_attempts.json"]
    )["attempts"]
    usage = _usage_triplet(
        read_json(
            _formal_checkpoint_paths(run_dir, node_id)["03_usage.json"]
        )["usage"],
        node_id,
    )
    unknown_count = sum(
        1
        for row in attempts
        if row.get("http_status") == 429
        and row.get("usage") == z83_retry_transport.UNKNOWN_USAGE
    )
    expected = {
        "network_attempt_count": len(attempts),
        "unknown_429_count": unknown_count,
        "actual_success_usage": usage,
        "actual_success_micro_cny": (
            usage["prompt_tokens"] * INPUT_PRICE_CNY_PER_MILLION_TOKENS
            + usage["completion_tokens"]
            * OUTPUT_PRICE_CNY_PER_MILLION_TOKENS
        ),
        "unknown_token_conservative_upper_bound": (
            unknown_count
            * int(
                reservation[
                    "per_attempt_conservative_token_upper_bound"
                ]
            )
        ),
        "unknown_cost_conservative_upper_bound_micro_cny": (
            unknown_count
            * int(
                reservation[
                    "per_attempt_conservative_cost_upper_bound_micro_cny"
                ]
            )
        ),
        "unused_attempt_reservation_released": (
            3 - len(attempts)
        ),
    }
    expected["hard_cap_accounted_tokens"] = (
        usage["total_tokens"]
        + expected["unknown_token_conservative_upper_bound"]
    )
    expected["hard_cap_accounted_micro_cny"] = (
        expected["actual_success_micro_cny"]
        + expected["unknown_cost_conservative_upper_bound_micro_cny"]
    )
    if any(settlement.get(key) != value for key, value in expected.items()):
        raise Z98Step2HardStop(
            "qwen_budget_receipt_invalid",
            f"{node_id} 预算结算不能从 usage 与 429 原账重建",
        )
    return settlement


def _repair_usage_grid(
    run_dir: Path,
    nodes: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], int]:
    totals: dict[tuple[str, str, str], int] = {}
    for node in nodes:
        if node["node_kind"] != "repair" or not _checkpoint_is_complete(
            run_dir, str(node["node_id"])
        ):
            continue
        usage_row = read_json(
            _formal_checkpoint_paths(run_dir, str(node["node_id"]))[
                "03_usage.json"
            ]
        )["usage"]
        usage = _usage_triplet(usage_row, str(node["node_id"]))
        key = (
            str(node["tested_lane"]),
            str(node["chapter_id"]),
            str(node["contract_mode"]),
        )
        totals[key] = totals.get(key, 0) + usage["total_tokens"]
    return totals


def _execute_repair_node(
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    authority: LiveAuthority,
    provider: Mapping[str, Any],
    key: str,
    state: z83_retry_transport.RetryRunState,
    policy: z83_retry_transport.RetryPolicy,
    sender: NodeSender,
    opener: Any,
    sleeper: Callable[[float], None] | None,
    monotonic: Callable[[], float] | None,
    jitter: Callable[[], float] | None,
) -> dict[str, Any]:
    repair_path = ROOT / str(node["repair_request_path"])
    repair_bytes = repair_path.read_bytes()
    if sha256_bytes(repair_bytes) != node["repair_request_sha256"]:
        raise Z98Step2HardStop(
            "repair_request_drift",
            f"{node['node_id']} 冻结修复请求 SHA 漂移",
        )
    repair_request = json.loads(repair_bytes)
    lane = str(node["tested_lane"])
    profile = authority.repair_envelope["lane_profiles"][lane]
    body = _repair_body(
        repair_request,
        lane=lane,
        body_fields=profile["body_fields"],
    )
    result = sender(
        run_dir=run_dir,
        node=node,
        provider=provider,
        key=key,
        body=body,
        state=state,
        policy=policy,
        opener=opener,
        sleeper=sleeper,
        monotonic=monotonic,
        jitter=jitter,
    )
    model_data, content, reasoning, finish, raw_path = _response_parts(
        result,
        requested_model=str(node["tested_model"]),
        require_reasoning=False,
    )
    candidate = _validate_repair_candidate(node, model_data, repair_request)
    usage = _usage_triplet(result.outcome.usage, str(node["node_id"]))
    if usage["total_tokens"] > int(node["token_cap"]):
        raise Z98Step2HardStop(
            "repair_budget_over_cap",
            f"{node['node_id']} usage={usage['total_tokens']} 超预注册 {node['token_cap']}",
        )
    node_root = run_dir / f"runtime/{node['node_id']}"
    raw_copy = node_root / "raw_provider_response.json"
    model_copy = node_root / "model_content.json"
    model_benchmark.write_bytes_exclusive(raw_copy, raw_path.read_bytes())
    model_benchmark.write_bytes_exclusive(model_copy, content.encode("utf-8"))
    call_path, call_bytes, usage_path, usage_bytes = _repair_normalized_tickets(
        run_dir=run_dir,
        node=node,
        model_content_path=model_copy,
        model_content_bytes=content.encode("utf-8"),
        result=result,
        usage=usage,
    )
    request_record = read_json(node_root / "request_artifact.json")
    response_record = {
        "provider_response_path": raw_copy.relative_to(run_dir).as_posix(),
        "provider_response_sha256": sha256_file(raw_copy),
        "model_content_path": model_copy.relative_to(run_dir).as_posix(),
        "model_content_sha256": sha256_file(model_copy),
        "response_model": result.outcome.payload["response_json"]["model"],
        "finish_reason": finish,
        "reasoning_content_sha256": sha256_bytes(reasoning.encode("utf-8")),
        "candidate": candidate,
        "normalized_call_attempt_path": call_path,
        "normalized_call_attempt_sha256": sha256_bytes(call_bytes),
        "normalized_usage_path": usage_path,
        "normalized_usage_sha256": sha256_bytes(usage_bytes),
    }
    seal = _write_formal_checkpoint(
        run_dir,
        node=node,
        request_record=request_record,
        response_record=response_record,
        usage=usage,
        attempts=result.attempt_rows,
    )
    return {"node_id": node["node_id"], "checkpoint_id": seal["checkpoint_id"]}


def _execute_judge_node(
    *,
    run_dir: Path,
    node: Mapping[str, Any],
    nodes_by_id: Mapping[str, Mapping[str, Any]],
    mapping_by_path: Mapping[str, Mapping[str, Any]],
    provider: Mapping[str, Any],
    key: str,
    state: z83_retry_transport.RetryRunState,
    policy: z83_retry_transport.RetryPolicy,
    sender: NodeSender,
    opener: Any,
    sleeper: Callable[[float], None] | None,
    monotonic: Callable[[], float] | None,
    jitter: Callable[[], float] | None,
    all_nodes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    repair_node = nodes_by_id[str(node["depends_on"][0])]
    repair_root = run_dir / f"runtime/{repair_node['node_id']}"
    mapping = mapping_by_path[str(repair_node["repair_request_path"])]
    template_path = R05_ROOT / str(mapping["verifier_template_path"])
    template = read_json(template_path)
    qwen_tokens, qwen_cost = _qwen_actual_totals(run_dir, all_nodes)
    dynamic = render_dynamic_verifier_request(
        template,
        expected_template_sha256=str(mapping["verifier_template_sha256"]),
        repair_request_bytes=(ROOT / str(repair_node["repair_request_path"])).read_bytes(),
        p2_response_path=(
            repair_root / "model_content.json"
        ).relative_to(run_dir).as_posix(),
        p2_response_bytes=(repair_root / "model_content.json").read_bytes(),
        repair_node=repair_node,
        judge_node=node,
        call_attempt_path=(
            repair_root / "call_attempt.json"
        ).relative_to(run_dir).as_posix(),
        call_attempt_bytes=(repair_root / "call_attempt.json").read_bytes(),
        usage_path=(
            repair_root / "usage.json"
        ).relative_to(run_dir).as_posix(),
        usage_bytes=(repair_root / "usage.json").read_bytes(),
        actual_accumulated_tokens=qwen_tokens,
        actual_accumulated_micro_cny=qwen_cost,
    )
    body = dynamic["request_body"]
    reservation = _write_qwen_budget_reservation(
        run_dir=run_dir,
        node=node,
        budget_preflight=dynamic["budget_preflight"],
        accumulated_tokens=qwen_tokens,
        accumulated_micro_cny=qwen_cost,
        max_attempts=1 + policy.max_429_retries_per_request,
    )
    result = sender(
        run_dir=run_dir,
        node=node,
        provider=provider,
        key=key,
        body=body,
        state=state,
        policy=policy,
        opener=opener,
        sleeper=sleeper,
        monotonic=monotonic,
        jitter=jitter,
    )
    model_data, content, reasoning, finish, raw_path = _response_parts(
        result,
        requested_model=QWEN_MODEL_ID,
        require_reasoning=False,
    )
    verdict = parse_verifier_content(
        content,
        expected_case_id=template["private_binding"]["case_id"],
        expected_item_ids=template["private_binding"]["item_ids"],
    )
    usage = _usage_triplet(result.outcome.usage, str(node["node_id"]))
    settlement = _write_qwen_budget_settlement(
        run_dir=run_dir,
        node=node,
        reservation=reservation,
        attempts=result.attempt_rows,
        usage=usage,
    )
    prospective_tokens = (
        qwen_tokens + settlement["hard_cap_accounted_tokens"]
    )
    prospective_cost = (
        qwen_cost + settlement["hard_cap_accounted_micro_cny"]
    )
    if prospective_tokens > TOTAL_TOKEN_CAP:
        raise Z98Step2HardStop(
            "qwen_round_token_cap_exceeded",
            "裁判正式 usage 超过整轮 50 万 token 帽",
        )
    if prospective_cost > TOTAL_COST_CAP_MICRO_CNY:
        raise Z98Step2HardStop(
            "qwen_round_cost_cap_exceeded",
            "裁判正式 usage 按冻结价超过整轮 10 元帽",
        )
    node_root = run_dir / f"runtime/{node['node_id']}"
    raw_copy = node_root / "raw_provider_response.json"
    model_copy = node_root / "model_content.json"
    model_benchmark.write_bytes_exclusive(raw_copy, raw_path.read_bytes())
    model_benchmark.write_bytes_exclusive(model_copy, content.encode("utf-8"))
    request_record = read_json(node_root / "request_artifact.json")
    reservation_path, settlement_path = _qwen_budget_paths(
        run_dir,
        str(node["node_id"]),
    )
    response_record = {
        "provider_response_path": raw_copy.relative_to(run_dir).as_posix(),
        "provider_response_sha256": sha256_file(raw_copy),
        "model_content_path": model_copy.relative_to(run_dir).as_posix(),
        "model_content_sha256": sha256_file(model_copy),
        "response_model": result.outcome.payload["response_json"]["model"],
        "finish_reason": finish,
        "reasoning_content_sha256": sha256_bytes(reasoning.encode("utf-8")),
        "verdict": verdict,
        "dynamic_source_binding": dynamic["source_binding"],
        "budget_preflight": dynamic["budget_preflight"],
        "budget_reservation_path": (
            reservation_path.relative_to(run_dir).as_posix()
        ),
        "budget_reservation_sha256": sha256_file(reservation_path),
        "budget_settlement_path": (
            settlement_path.relative_to(run_dir).as_posix()
        ),
        "budget_settlement_sha256": sha256_file(settlement_path),
    }
    seal = _write_formal_checkpoint(
        run_dir,
        node=node,
        request_record=request_record,
        response_record=response_record,
        usage=usage,
        attempts=result.attempt_rows,
    )
    return {"node_id": node["node_id"], "checkpoint_id": seal["checkpoint_id"]}


def _write_runtime_hard_stop(
    run_dir: Path,
    error: BaseException,
    *,
    node_id: str | None,
) -> None:
    path = run_dir / "runtime/hard_stop.json"
    if path.exists():
        return
    model_benchmark.write_json_exclusive(
        path,
        {
            "schema_version": "z98-step2-runtime-hard-stop-v1",
            "status": "HARD_STOP_NO_PATCH_NO_RESEND",
            "node_id": node_id,
            "reason_code": getattr(error, "reason_code", "runtime_error"),
            "error_type": type(error).__name__,
            "message": str(error),
            "rerun_in_same_directory_allowed": False,
            "partial_results_may_be_scored": False,
            "stopped_at": now_iso(),
        },
    )


def _copy_live_authority_receipts(
    run_dir: Path,
    repair_authority_path: Path,
    qwen_catalog_receipt_path: Path,
) -> None:
    destination = run_dir / "runtime/authority"
    for source, name in (
        (repair_authority_path, "repair_envelope_authority.json"),
        (qwen_catalog_receipt_path, "qwen_catalog_receipt.json"),
    ):
        model_benchmark.write_bytes_exclusive(
            destination / name,
            source.read_bytes(),
        )
    catalog = _validate_catalog_receipt_path(
        qwen_catalog_receipt_path,
        run_dir=run_dir,
        require_fresh=True,
    )
    raw_source = Path(str(catalog["raw_catalog_path"]))
    if not raw_source.is_absolute():
        raw_source = ROOT / raw_source
    raw_source = raw_source.resolve()
    model_benchmark.write_bytes_exclusive(
        destination / "qwen_raw_catalog.json",
        raw_source.read_bytes(),
    )
    model_benchmark.write_json_exclusive(
        destination / "qwen_adapter_binding.json",
        {
            "schema_version": "z98-qwen-adapter-runtime-binding-v1",
            "adapter_identity": catalog["adapter_identity"],
            "adapter_path": catalog["command_path"],
            "adapter_sha256": catalog["adapter_sha256"],
            "raw_catalog_source_path": catalog["raw_catalog_path"],
            "raw_catalog_sha256": catalog["raw_catalog_sha256"],
            "status_evidence_kind": catalog["status_evidence_kind"],
            "status_evidence_policy": catalog["status_evidence_policy"],
        },
    )


def _verify_frozen_provider_configs(
    run_dir: Path,
) -> dict[str, dict[str, Any]]:
    configs = _provider_configs()
    pairs = {
        "sensenova": (
            run_dir / "inputs/providers/sensenova.json",
            SENSENOVA_CONFIG,
        ),
        "tencent_tokenhub": (
            run_dir / "inputs/providers/tencent_tokenhub_multi_model.json",
            TENCENT_CONFIG,
        ),
        "qianwen_platform": (
            run_dir / "inputs/providers/qianwen_platform_multi_model.json",
            QWEN_CONFIG,
        ),
    }
    for provider_id, (frozen, live) in pairs.items():
        if not frozen.is_file() or frozen.read_bytes() != live.read_bytes():
            raise Z98Step2HardStop(
                "provider_config_drift",
                f"{provider_id} 配置在 prepare 后漂移",
            )
    return configs


def _load_live_keys() -> dict[str, str]:
    key_envs = {
        "sensenova": "SENSENOVA_API_KEY",
        "tencent_tokenhub": "TENCENT_TOKENHUB_API_KEY",
        "qianwen_platform": QWEN_KEY_ENV,
    }
    keys = {
        provider: os.environ.get(env) or ""
        for provider, env in key_envs.items()
    }
    missing = [
        key_envs[provider] for provider, value in keys.items() if not value
    ]
    if missing:
        raise Z98Step2HardStop(
            "api_key_missing",
            f"缺少环境变量：{', '.join(sorted(missing))}；未创建新节点占用票",
        )
    return keys


def _run_claim_payload(
    run_dir: Path,
    repair_authority_path: Path,
    qwen_catalog_receipt_path: Path,
) -> dict[str, Any]:
    catalog = _validate_catalog_receipt_path(
        qwen_catalog_receipt_path,
        run_dir=run_dir,
        require_fresh=False,
    )
    return {
        "schema_version": "z98-step2-run-claim-v1",
        "run_id": run_dir.name,
        "contract_version": CONTRACT_VERSION,
        "r05_manifest_sha256": R05_MANIFEST_SHA256,
        "repair_request_set_sha256": REPAIR_REQUEST_SET_SHA256,
        "run_slot_sha256": sha256_file(
            run_dir / "runtime/run_slot.json"
        ),
        "prepared_manifest_sha256": sha256_file(
            run_dir / "prepared/artifact_manifest.json"
        ),
        "runtime_dependency_vector_sha256": canonical_sha(
            _runtime_dependency_rows()
        ),
        "provider_config_vector_sha256": canonical_sha(
            {
                provider: canonical_sha(config)
                for provider, config in _provider_configs().items()
            }
        ),
        "repair_authority_sha256": sha256_file(repair_authority_path),
        "qwen_catalog_receipt_sha256": sha256_file(
            qwen_catalog_receipt_path
        ),
        "qwen_catalog_raw_sha256": catalog["raw_catalog_sha256"],
        "qwen_catalog_adapter_sha256": catalog["adapter_sha256"],
        "qwen_catalog_status_evidence_kind": catalog[
            "status_evidence_kind"
        ],
        "rerun_in_same_directory_allowed": False,
        "resume_next_unattempted_node_allowed": True,
    }


def _write_network_release(
    run_dir: Path,
    configs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    claim_path = run_dir / "runtime/run_claim.json"
    catalog_root = run_dir / "runtime/catalog/tencent"
    catalog_audit = model_benchmark.audit_provider_model_catalog(
        catalog_root,
        configs["tencent_tokenhub"],
        LANE_CONTRACTS["pro"]["model"],
    )
    if not isinstance(catalog_audit, Mapping):
        raise Z98Step2HardStop(
            "tencent_catalog_receipt_missing",
            "腾讯固定版目录闸没有生成可重建票据",
        )
    payload = {
        "schema_version": "z98-step2-network-release-v1",
        "run_claim_sha256": sha256_file(claim_path),
        "tencent_catalog_receipt_sha256": catalog_audit[
            "receipt_sha256"
        ],
        "tencent_catalog_raw_sha256": catalog_audit[
            "raw_response_sha256"
        ],
        "released_after_catalog_audit": True,
        "released_at": now_iso(),
    }
    model_benchmark.write_json_exclusive(
        run_dir / "runtime/network_release.json",
        payload,
    )
    return payload


def _validate_runtime_authority_chain(run_dir: Path) -> dict[str, Any]:
    """重建正式发网占用链；本地五件套不能跳过外部权威票。"""

    if (run_dir / "pre_network_hard_stop.json").exists():
        raise Z98Step2HardStop(
            "pre_network_hard_stopped_run_cannot_finalize",
            "发网前硬停目录不能进入正式链",
        )
    if (run_dir / "runtime/hard_stop.json").exists():
        raise Z98Step2HardStop(
            "hard_stopped_run_cannot_finalize",
            "运行硬停目录不能进入正式链",
        )
    claim_path = run_dir / "runtime/run_claim.json"
    release_path = run_dir / "runtime/network_release.json"
    if not claim_path.is_file() or not release_path.is_file():
        raise Z98Step2HardStop(
            "run_claim_missing",
            "正式收口缺 run claim 或目录闸放行票",
        )
    repair_copy = (
        run_dir / "runtime/authority/repair_envelope_authority.json"
    )
    qwen_copy = run_dir / "runtime/authority/qwen_catalog_receipt.json"
    qwen_raw_copy = run_dir / "runtime/authority/qwen_raw_catalog.json"
    slot_path = run_dir / "runtime/run_slot.json"
    if not slot_path.is_file():
        raise Z98Step2HardStop(
            "run_claim_missing",
            "正式收口缺原子运行占用槽",
        )
    slot = read_json(slot_path)
    if (
        not isinstance(slot, Mapping)
        or set(slot)
        != {
            "schema_version",
            "status",
            "run_id",
            "prepared_manifest_sha256",
            "reserved_at",
        }
        or slot.get("schema_version") != "z98-step2-run-slot-v1"
        or slot.get("status") != "CLAIM_RESERVED"
        or slot.get("run_id") != run_dir.name
        or slot.get("prepared_manifest_sha256")
        != sha256_file(run_dir / "prepared/artifact_manifest.json")
    ):
        raise Z98Step2HardStop(
            "run_claim_drift",
            "原子运行占用槽身份漂移",
        )
    _parse_iso_time(slot.get("reserved_at"), "原子运行占用槽")
    _validate_repair_authority_path(repair_copy)
    catalog = _validate_catalog_receipt_path(
        qwen_copy,
        run_dir=run_dir,
        require_fresh=False,
    )
    claim = read_json(claim_path)
    expected_claim = _run_claim_payload(run_dir, repair_copy, qwen_copy)
    if (
        not isinstance(claim, Mapping)
        or set(claim) != {*expected_claim, "claimed_at"}
        or any(claim.get(field) != value for field, value in expected_claim.items())
        or not isinstance(claim.get("claimed_at"), str)
        or not claim["claimed_at"]
    ):
        raise Z98Step2HardStop(
            "run_claim_drift",
            "正式 run claim 不能由受审权威票和冻结依赖重建",
        )
    if (
        not qwen_raw_copy.is_file()
        or sha256_file(qwen_raw_copy) != catalog["raw_catalog_sha256"]
    ):
        raise Z98Step2HardStop(
            "resume_authority_copy_drift",
            "千问目录原始响应副本漂移",
        )
    configs = _verify_frozen_provider_configs(run_dir)
    catalog_audit = model_benchmark.audit_provider_model_catalog(
        run_dir / "runtime/catalog/tencent",
        configs["tencent_tokenhub"],
        LANE_CONTRACTS["pro"]["model"],
    )
    if not isinstance(catalog_audit, Mapping):
        raise Z98Step2HardStop(
            "tencent_catalog_receipt_missing",
            "腾讯目录票缺失",
        )
    release = read_json(release_path)
    expected_release = {
        "schema_version": "z98-step2-network-release-v1",
        "run_claim_sha256": sha256_file(claim_path),
        "tencent_catalog_receipt_sha256": catalog_audit[
            "receipt_sha256"
        ],
        "tencent_catalog_raw_sha256": catalog_audit[
            "raw_response_sha256"
        ],
        "released_after_catalog_audit": True,
    }
    if (
        not isinstance(release, Mapping)
        or set(release) != {*expected_release, "released_at"}
        or any(
            release.get(field) != value
            for field, value in expected_release.items()
        )
        or not isinstance(release.get("released_at"), str)
        or not release["released_at"]
    ):
        raise Z98Step2HardStop(
            "network_release_drift",
            "网络放行票不能由 run claim 与腾讯目录原账重建",
        )
    return {
        "run_claim_sha256": expected_release["run_claim_sha256"],
        "network_release_sha256": sha256_file(release_path),
    }


def _verify_resume_claim(
    run_dir: Path,
    *,
    repair_authority_path: Path,
    qwen_catalog_receipt_path: Path,
) -> LiveAuthority:
    verify_prepared(run_dir, allow_runtime=True)
    claim_path = run_dir / "runtime/run_claim.json"
    if not claim_path.is_file():
        raise Z98Step2HardStop(
            "run_claim_missing",
            "没有正式 run claim，不能把预演目录当成可续跑目录",
        )
    repair = _validate_repair_authority_path(repair_authority_path)
    catalog = _validate_catalog_receipt_path(
        qwen_catalog_receipt_path,
        run_dir=run_dir,
        require_fresh=True,
    )
    claim = read_json(claim_path)
    expected = _run_claim_payload(
        run_dir,
        repair_authority_path,
        qwen_catalog_receipt_path,
    )
    if (
        not isinstance(claim, Mapping)
        or set(claim) != {*expected, "claimed_at"}
        or any(claim.get(field) != value for field, value in expected.items())
        or not isinstance(claim.get("claimed_at"), str)
        or not claim["claimed_at"]
    ):
        raise Z98Step2HardStop(
            "resume_claim_drift",
            "续跑占用票字段或冻结依赖漂移",
        )
    copied = {
        "repair_authority_sha256": (
            run_dir / "runtime/authority/repair_envelope_authority.json"
        ),
        "qwen_catalog_receipt_sha256": (
            run_dir / "runtime/authority/qwen_catalog_receipt.json"
        ),
        "qwen_catalog_raw_sha256": (
            run_dir / "runtime/authority/qwen_raw_catalog.json"
        ),
    }
    for field, path in copied.items():
        if not path.is_file() or sha256_file(path) != claim[field]:
            raise Z98Step2HardStop(
                "resume_authority_copy_drift",
                f"续跑权威票副本漂移：{path.name}",
            )
    adapter_binding = read_json(
        run_dir / "runtime/authority/qwen_adapter_binding.json"
    )
    if (
        adapter_binding.get("adapter_sha256")
        != claim["qwen_catalog_adapter_sha256"]
        or adapter_binding.get("raw_catalog_sha256")
        != claim["qwen_catalog_raw_sha256"]
        or adapter_binding.get("status_evidence_kind")
        != claim["qwen_catalog_status_evidence_kind"]
    ):
        raise Z98Step2HardStop(
            "resume_catalog_binding_drift",
            "续跑目录适配器绑定票与run claim不一致",
        )
    _verify_frozen_provider_configs(run_dir)
    _validate_runtime_authority_chain(run_dir)
    return LiveAuthority(repair_envelope=repair, qwen_catalog=catalog)


def _retry_state_from_run(
    run_dir: Path,
    nodes: Sequence[Mapping[str, Any]],
    completed_node_ids: Sequence[str],
    *,
    resume_now_monotonic: float,
) -> z83_retry_transport.RetryRunState:
    """只从已封签前缀恢复；跨进程后保守重等完整 10/30 秒。"""

    rows: list[dict[str, Any]] = []
    by_id = {str(node["node_id"]): node for node in nodes}
    for node_id in completed_node_ids:
        attempts_path = _formal_checkpoint_paths(
            run_dir,
            node_id,
        )["04_attempts.json"]
        attempts = read_json(attempts_path)["attempts"]
        z83_retry_transport.validate_attempt_rows(attempts)
        rows.extend(attempts)
    state = z83_retry_transport.RetryRunState.from_attempt_rows(rows)
    if completed_node_ids:
        last_node = by_id[str(completed_node_ids[-1])]
        state.last_chapter = _chapter_number(str(last_node["chapter_id"]))
        state.last_logical_completed_monotonic = resume_now_monotonic
    return state


def _execute_live_nodes(
    run_dir: Path,
    *,
    authority: LiveAuthority,
    configs: Mapping[str, Mapping[str, Any]],
    keys: Mapping[str, str],
    sender: NodeSender,
    provider_openers: Mapping[str, Any] | None,
    sleeper: Callable[[float], None] | None,
    monotonic: Callable[[], float] | None,
    jitter: Callable[[], float] | None,
) -> dict[str, Any]:
    plan = read_json(run_dir / "prepared/run_plan.json")
    nodes = plan["nodes"]
    by_id = {str(node["node_id"]): node for node in nodes}
    mappings = read_json(
        run_dir / "inputs/r05/mappings/verifier_mapping.json"
    )["mappings"]
    mapping_by_path = {
        str(row["repair_request_path"]): row for row in mappings
    }
    openers = dict(provider_openers or {})
    policy = z83_retry_transport.RetryPolicy()
    policy.validate()
    position = audit_resume_position(run_dir)
    completed = set(position["completed_node_ids"])
    clock = monotonic or time.monotonic
    state = _retry_state_from_run(
        run_dir,
        nodes,
        position["completed_node_ids"],
        resume_now_monotonic=clock(),
    )
    current_node_id: str | None = None
    try:
        for node in nodes:
            current_node_id = str(node["node_id"])
            if current_node_id in completed:
                continue
            if any(
                str(dependency) not in completed
                for dependency in node.get("depends_on", [])
            ):
                raise Z98Step2HardStop(
                    "dependency_not_checkpointed",
                    f"{current_node_id} 前置节点没有正式封签",
                )
            provider_id = _provider_id_for_node(node)
            if node["node_kind"] == "repair":
                result = _execute_repair_node(
                    run_dir=run_dir,
                    node=node,
                    authority=authority,
                    provider=configs[provider_id],
                    key=keys[provider_id],
                    state=state,
                    policy=policy,
                    sender=sender,
                    opener=openers.get(provider_id),
                    sleeper=sleeper,
                    monotonic=monotonic,
                    jitter=jitter,
                )
            else:
                result = _execute_judge_node(
                    run_dir=run_dir,
                    node=node,
                    nodes_by_id=by_id,
                    mapping_by_path=mapping_by_path,
                    provider=configs[provider_id],
                    key=keys[provider_id],
                    state=state,
                    policy=policy,
                    sender=sender,
                    opener=openers.get(provider_id),
                    sleeper=sleeper,
                    monotonic=monotonic,
                    jitter=jitter,
                    all_nodes=nodes,
                )
            completed.add(str(result["node_id"]))
    except BaseException as exc:
        _write_runtime_hard_stop(
            run_dir,
            exc,
            node_id=current_node_id,
        )
        raise
    # KeyboardInterrupt、进程被杀和未分类程序异常不冒充质量硬停；
    # 下次只允许从完整前缀后的未尝试节点恢复。
    return finalize(run_dir)


def run_live(
    run_dir: Path,
    *,
    repair_authority_path: Path,
    qwen_catalog_receipt_path: Path,
    sender: NodeSender = _default_send_node,
    provider_openers: Mapping[str, Any] | None = None,
    tencent_catalog_opener: Any = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    jitter: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """按冻结顺序执行；只有完整前缀后面的未尝试节点可继续。"""

    owned_run_slot_sha256: str | None = None
    try:
        authority = live_preflight(
            run_dir,
            repair_authority_path=repair_authority_path,
            qwen_catalog_receipt_path=qwen_catalog_receipt_path,
        )
        _claim_run_slot(run_dir)
        owned_run_slot_sha256 = sha256_file(
            run_dir / "runtime/run_slot.json"
        )
        configs = _verify_frozen_provider_configs(run_dir)
        _copy_live_authority_receipts(
            run_dir,
            repair_authority_path,
            qwen_catalog_receipt_path,
        )
        claim = {
            **_run_claim_payload(
                run_dir,
                repair_authority_path,
                qwen_catalog_receipt_path,
            ),
            "claimed_at": now_iso(),
        }
        model_benchmark.write_json_exclusive(
            run_dir / "runtime/run_claim.json",
            claim,
        )
    except BaseException as exc:
        _write_pre_network_hard_stop(
            run_dir,
            exc,
            owned_run_slot_sha256=owned_run_slot_sha256,
        )
        raise
    try:
        # run claim 已先占住本运行编号；到这里才读密钥和发目录请求。
        keys = _load_live_keys()
        catalog_root = run_dir / "runtime/catalog/tencent"
        model_benchmark.write_json_exclusive(
            catalog_root / "catalog_attempt_reservation.json",
            {
                "schema_version": (
                    "z98-tencent-catalog-attempt-reservation-v1"
                ),
                "run_claim_sha256": sha256_file(
                    run_dir / "runtime/run_claim.json"
                ),
                "provider": "tencent_tokenhub",
                "exact_model_id": LANE_CONTRACTS["pro"]["model"],
                "reserved_before_catalog_request": True,
                "reserved_at": now_iso(),
            },
        )
        model_benchmark.verify_provider_model_catalog(
            catalog_root,
            configs["tencent_tokenhub"],
            LANE_CONTRACTS["pro"]["model"],
            keys["tencent_tokenhub"],
            opener=tencent_catalog_opener,
        )
        _write_network_release(run_dir, configs)
        _validate_runtime_authority_chain(run_dir)
    except BaseException as exc:
        _write_runtime_hard_stop(run_dir, exc, node_id=None)
        raise
    return _execute_live_nodes(
        run_dir,
        authority=authority,
        configs=configs,
        keys=keys,
        sender=sender,
        provider_openers=provider_openers,
        sleeper=sleeper,
        monotonic=monotonic,
        jitter=jitter,
    )


def _checkpoint_documents(
    run_dir: Path,
    node: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    validate_formal_checkpoint(run_dir, node)
    paths = _formal_checkpoint_paths(run_dir, str(node["node_id"]))
    return (
        read_json(paths["01_request.json"]),
        read_json(paths["02_response.json"]),
        read_json(paths["03_usage.json"]),
        read_json(paths["04_attempts.json"]),
    )


def _build_finalize_payloads(run_dir: Path) -> dict[str, bytes]:
    authority_chain = _validate_runtime_authority_chain(run_dir)
    plan = read_json(run_dir / "prepared/run_plan.json")
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 68:
        raise Z98Step2HardStop("run_plan_invalid", "finalize 找不到 68 节点")
    position = audit_resume_position(run_dir)
    if position["completed_prefix_count"] != 68:
        raise Z98Step2HardStop(
            "finalize_before_68",
            f"只有 {position['completed_prefix_count']}/68 个封签，拒绝 finalize",
        )
    usage_rows: list[dict[str, Any]] = []
    repair_candidates: list[dict[str, Any]] = []
    judge_verdicts: list[dict[str, Any]] = []
    seal_rows: list[dict[str, Any]] = []
    nodes_by_id = {str(node["node_id"]): node for node in nodes}
    mapping_by_request = {
        str(row["repair_request_path"]): row
        for row in read_json(
            run_dir / "inputs/r05/mappings/verifier_mapping.json"
        )["mappings"]
    }
    for node in nodes:
        request_doc, response_doc, usage_doc, attempts_doc = (
            _checkpoint_documents(run_dir, node)
        )
        usage = _usage_triplet(usage_doc["usage"], str(node["node_id"]))
        seal = read_json(
            _formal_checkpoint_paths(run_dir, str(node["node_id"]))[
                "05_seal.json"
            ]
        )
        seal_rows.append(
            {
                "node_id": node["node_id"],
                "checkpoint_id": seal["checkpoint_id"],
                "seal_sha256": sha256_file(
                    _formal_checkpoint_paths(run_dir, str(node["node_id"]))[
                        "05_seal.json"
                    ]
                ),
            }
        )
        usage_rows.append(
            {
                "node_id": node["node_id"],
                "node_kind": node["node_kind"],
                "tested_lane": (
                    node.get("tested_lane")
                    if node["node_kind"] == "repair"
                    else node.get("tested_lane_private")
                ),
                "provider": _provider_id_for_node(node),
                "model": _model_id_for_node(node),
                "chapter_id": node["chapter_id"],
                "contract_mode": (
                    node.get("contract_mode")
                    if node["node_kind"] == "repair"
                    else node.get("contract_mode_private")
                ),
                **usage,
                "network_attempts": len(attempts_doc["attempts"]),
                "checkpoint_id": seal["checkpoint_id"],
            }
        )
        if node["node_kind"] == "repair":
            repair_candidates.append(
                {
                    "node_id": node["node_id"],
                    "tested_lane": node["tested_lane"],
                    "chapter_id": node["chapter_id"],
                    "contract_mode": node["contract_mode"],
                    "candidate": response_doc["response"]["candidate"],
                    "checkpoint_id": seal["checkpoint_id"],
                }
            )
        else:
            repair_node = nodes_by_id[str(node["depends_on"][0])]
            mapping = mapping_by_request[
                str(repair_node["repair_request_path"])
            ]
            judge_verdicts.append(
                {
                    "node_id": node["node_id"],
                    "tested_lane_private": node["tested_lane_private"],
                    "chapter_id": node["chapter_id"],
                    "contract_mode_private": node["contract_mode_private"],
                    "source_slot_ids": mapping["source_slot_ids"],
                    "verdict": response_doc["response"]["verdict"],
                    "checkpoint_id": seal["checkpoint_id"],
                }
            )
    if len(repair_candidates) != 34 or len(judge_verdicts) != 34:
        raise Z98Step2HardStop("finalize_pair_count", "repair/judge 不是 34 对")

    by_provider: dict[str, dict[str, int]] = {}
    by_lane: dict[str, dict[str, int]] = {}
    for row in usage_rows:
        for bucket, key in (
            (by_provider, str(row["provider"])),
            (by_lane, str(row["tested_lane"])),
        ):
            target = bucket.setdefault(
                key,
                {
                    "logical_requests": 0,
                    "network_attempts": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            )
            target["logical_requests"] += 1
            target["network_attempts"] += int(row["network_attempts"])
            for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
                target[field] += int(row[field])
    qwen_hard_cap_tokens, qwen_hard_cap_cost = _qwen_actual_totals(
        run_dir,
        nodes,
    )
    qwen_unknown_429 = sum(
        int(
            _validate_qwen_budget_receipts(run_dir, node)[
                "unknown_429_count"
            ]
        )
        for node in nodes
        if node["node_kind"] == "independent_judge"
    )
    usage_ledger = {
        "schema_version": "z98-step2-formal-usage-ledger-v1",
        "status": "REBUILT_FROM_68_CHECKPOINTS",
        "rows": usage_rows,
        "by_provider": by_provider,
        "by_tested_lane": by_lane,
        "qwen_actual_tokens": by_provider[QWEN_PROVIDER_ID]["total_tokens"],
        "qwen_actual_micro_cny": (
            by_provider[QWEN_PROVIDER_ID]["prompt_tokens"]
            * INPUT_PRICE_CNY_PER_MILLION_TOKENS
            + by_provider[QWEN_PROVIDER_ID]["completion_tokens"]
            * OUTPUT_PRICE_CNY_PER_MILLION_TOKENS
        ),
        "qwen_unknown_429_attempts": qwen_unknown_429,
        "qwen_hard_cap_accounted_tokens": qwen_hard_cap_tokens,
        "qwen_hard_cap_accounted_micro_cny": qwen_hard_cap_cost,
        "formal_usage_uses_provider_success_usage": True,
        "hard_cap_account_includes_unknown_429_conservative_debt": True,
    }
    score_inputs = {
        "schema_version": "z98-step2-score-inputs-v1",
        "status": "INPUTS_ONLY_NO_SELF_JUDGMENT",
        "strict_legacy_scale": {
            "mode": "READ_ONLY_COLUMN",
            "score": None,
            "historical_scores_rewritten": False,
            "computability": "NOT_COMPUTABLE_WITHOUT_COMPLETE_GOLD_VERDICTS",
            "null_is_not_zero": True,
        },
        "ucr_five_layer": {
            "mode": "CANDIDATE_DIAGNOSTIC_COLUMN",
            "score": None,
            "layers": ["FCR", "QCR_full", "ASR_full", "UCR", "SOP"],
            "may_replace_strict_scale": False,
            "computability": (
                "NOT_COMPUTABLE_WITHOUT_FROZEN_RFU_WEIGHTS_AND_Z98_ADAPTER"
            ),
            "null_is_not_zero": True,
        },
        "repair_candidates": repair_candidates,
        "independent_judge_verdicts": judge_verdicts,
    }
    component_rows: list[dict[str, Any]] = []
    for judge in judge_verdicts:
        items = judge["verdict"]["items"]
        slots = judge["source_slot_ids"]
        if len(items) != len(slots):
            raise Z98Step2HardStop(
                "finalize_slot_mapping_invalid",
                f"{judge['node_id']} 裁判 item 与冻结 slot 数量不一致",
            )
        for slot_id, item in zip(slots, items, strict=True):
            component_rows.append(
                {
                    "tested_lane": judge["tested_lane_private"],
                    "chapter_id": judge["chapter_id"],
                    "contract_mode": judge["contract_mode_private"],
                    "slot_id": slot_id,
                    "verdict": item["verdict"],
                    "fact_support": item["fact_support"],
                    "qualifier_support": item["qualifier_support"],
                    "anchor_support": item["anchor_support"],
                    "atomicity": item["atomicity"],
                    "reason_codes": item["reason_codes"],
                }
            )
    component_pairs: list[dict[str, Any]] = []
    for lane in sorted({str(row["tested_lane"]) for row in component_rows}):
        single = {
            str(row["slot_id"]): row
            for row in component_rows
            if row["tested_lane"] == lane
            and row["contract_mode"] == "single_patch"
        }
        batch = {
            str(row["slot_id"]): row
            for row in component_rows
            if row["tested_lane"] == lane
            and row["contract_mode"] == "atom_batch_v2"
        }
        if set(single) != set(batch):
            raise Z98Step2HardStop(
                "finalize_same_slot_contract_failed",
                f"{lane} 单条与批式不是同一组冻结 slot",
            )
        for slot_id in sorted(single):
            single_row = single[slot_id]
            batch_row = batch[slot_id]
            compared_fields = (
                "verdict",
                "fact_support",
                "qualifier_support",
                "anchor_support",
                "atomicity",
                "reason_codes",
            )
            component_pairs.append(
                {
                    "tested_lane": lane,
                    "slot_id": slot_id,
                    "single": single_row,
                    "batch": batch_row,
                    "all_component_fields_equal": all(
                        single_row[field] == batch_row[field]
                        for field in compared_fields
                    ),
                }
            )
    comparison_design = read_json(
        run_dir / "inputs/step1/design/comparison_design.json"
    )
    comparisons = {
        "schema_version": "z98-step2-comparison-inputs-v1",
        "status": "INPUTS_ONLY_AWAITING_UNIFIED_REVIEW",
        "three_way": {
            "arms": [
                "knife_a_patch_current_run",
                "z96_knife_b_a_plus_anchor_candidate_replay",
                "retry03_baseline",
            ],
            "current_run_inputs": repair_candidates,
            "external_arms": {
                "status": "NOT_COMPUTABLE_WITHOUT_FROZEN_SLOT_MAPPING",
                "design_source_sha256": canonical_sha(comparison_design),
                "z96_design_reference_sha256": (
                    comparison_design["dispute_2_three_way"][1][
                        "source_sha256"
                    ]
                ),
                "retry03_quality_verdict_count": 0,
                "null_is_not_zero": True,
            },
            "winner": None,
        },
        "single_vs_batch": {
            "same_selected_slots_required": True,
            "same_selected_slots_verified": True,
            "comparison_level": "INDEPENDENT_JUDGE_COMPONENTS_ONLY",
            "pair_count": len(component_pairs),
            "rows": component_pairs,
            "winner": None,
        },
    }
    finalize_receipt = {
        "schema_version": "z98-step2-finalize-receipt-v1",
        "status": "COMPLETED_68_AWAITING_UNIFIED_QUALITY_REVIEW",
        "checkpoint_count": len(seal_rows),
        "repair_judge_pair_count": 34,
        "checkpoint_vector_sha256": canonical_sha(seal_rows),
        **authority_chain,
        "quality_result": "UNJUDGED",
        "quality_winner_registered": False,
        "strict_score_registered": False,
        "ucr_score_registered": False,
        "partial_results_scored": False,
        "seal_rows": seal_rows,
    }
    return {
        "final/usage_ledger.json": stable_json_bytes(usage_ledger),
        "final/score_inputs.json": stable_json_bytes(score_inputs),
        "final/comparison_inputs.json": stable_json_bytes(comparisons),
        "final/finalize_receipt.json": stable_json_bytes(finalize_receipt),
    }


def finalize(run_dir: Path) -> dict[str, Any]:
    payloads = _build_finalize_payloads(run_dir)
    if any((run_dir / relative).exists() for relative in payloads):
        raise Z98Step2HardStop(
            "finalize_already_exists",
            "finalize 工件已存在，拒绝覆盖或重算挑结果",
        )
    for relative, raw in sorted(payloads.items()):
        model_benchmark.write_bytes_exclusive(run_dir / relative, raw)
    audit = audit_completed(run_dir)
    return {
        "status": "COMPLETED_68_AWAITING_UNIFIED_QUALITY_REVIEW",
        "finalize_receipt_sha256": sha256_file(
            run_dir / "final/finalize_receipt.json"
        ),
        "usage_ledger_sha256": sha256_file(
            run_dir / "final/usage_ledger.json"
        ),
        "score_inputs_sha256": sha256_file(
            run_dir / "final/score_inputs.json"
        ),
        "comparison_inputs_sha256": sha256_file(
            run_dir / "final/comparison_inputs.json"
        ),
        "audit_vector_sha256": audit["vector_sha256"],
        "quality_result": "UNJUDGED",
    }


def audit_completed(run_dir: Path) -> dict[str, Any]:
    expected = _build_finalize_payloads(run_dir)
    vector: dict[str, str] = {}
    for relative, raw in expected.items():
        path = run_dir / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise Z98Step2HardStop(
                "finalize_drift",
                f"finalize 不能由68封签重建：{relative}",
            )
        vector[relative] = sha256_bytes(raw)
    return {
        "status": "PASS_REBUILT_FROM_68_SEALS",
        "vector": vector,
        "vector_sha256": canonical_sha(vector),
        "quality_result": "UNJUDGED",
    }


def resume_or_audit(
    run_dir: Path,
    *,
    repair_authority_path: Path | None = None,
    qwen_catalog_receipt_path: Path | None = None,
    sender: NodeSender = _default_send_node,
    provider_openers: Mapping[str, Any] | None = None,
    tencent_catalog_opener: Any = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    jitter: Callable[[], float] | None = None,
) -> dict[str, Any]:
    _reject_pre_network_hard_stopped_run(
        run_dir,
        reject_claim_slot=False,
    )
    if (run_dir / "runtime/hard_stop.json").exists():
        raise Z98Step2HardStop(
            "hard_stopped_run_not_resumable",
            "本运行已有硬停票，禁止同目录续跑",
        )
    if (run_dir / "final/finalize_receipt.json").exists():
        return audit_completed(run_dir)
    position = audit_resume_position(run_dir)
    if position["completed_prefix_count"] == 68:
        return finalize(run_dir)
    if not (run_dir / "runtime/run_claim.json").is_file():
        raise Z98Step2HardStop(
            "run_claim_missing",
            "没有正式 run claim，不能把预演目录当成可续跑目录",
        )
    if repair_authority_path is None or qwen_catalog_receipt_path is None:
        raise Z98Step2HardStop(
            "resume_authority_missing",
            "续跑仍须逐字复验原修复外壳权威票与千问目录票",
        )
    authority = _verify_resume_claim(
        run_dir,
        repair_authority_path=repair_authority_path,
        qwen_catalog_receipt_path=qwen_catalog_receipt_path,
    )
    # 票、配置与下一节点无尝试证据全部复验后，才读取密钥。
    keys = _load_live_keys()
    configs = _verify_frozen_provider_configs(run_dir)
    return _execute_live_nodes(
        run_dir,
        authority=authority,
        configs=configs,
        keys=keys,
        sender=sender,
        provider_openers=provider_openers,
        sleeper=sleeper,
        monotonic=monotonic,
        jitter=jitter,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare",
            "verify",
            "catalog-check",
            "live-preflight",
            "run",
            "resume-or-audit",
            "finalize",
            "audit",
        ),
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
    )
    parser.add_argument("--repair-authority", type=Path)
    parser.add_argument("--qwen-catalog-receipt", type=Path)
    parser.add_argument("--catalog-output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.run_dir)
    elif args.command == "verify":
        result = verify_prepared(args.run_dir)
    elif args.command == "catalog-check":
        if args.catalog_output_dir is None:
            parser.error("catalog-check 必须提供 --catalog-output-dir")
        result = catalog_check(
            args.catalog_output_dir,
            run_dir=args.run_dir,
        )
    elif args.command == "live-preflight":
        result = command_live_preflight(
            args.run_dir,
            repair_authority_path=args.repair_authority,
            qwen_catalog_receipt_path=args.qwen_catalog_receipt,
        )
    elif args.command == "run":
        if args.repair_authority is None or args.qwen_catalog_receipt is None:
            parser.error("run 必须提供两张权威票")
        result = run_live(
            args.run_dir,
            repair_authority_path=args.repair_authority,
            qwen_catalog_receipt_path=args.qwen_catalog_receipt,
        )
    elif args.command == "resume-or-audit":
        result = resume_or_audit(
            args.run_dir,
            repair_authority_path=args.repair_authority,
            qwen_catalog_receipt_path=args.qwen_catalog_receipt,
        )
    elif args.command == "finalize":
        result = finalize(args.run_dir)
    else:
        result = audit_completed(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
