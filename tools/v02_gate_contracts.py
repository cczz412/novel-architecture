#!/usr/bin/env python3
"""Build and validate the v0.2 extraction-pipeline gate contracts.

The builder is deliberately offline and deterministic.  It owns only the B2
candidate bundle.  It does not read provider configuration, import an HTTP
client, issue a judge ticket, or change any active pipeline pointer.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B2_gate_contract_v0.1"
)

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
HEX64_PATTERN = "^[0-9a-f]{64}$"
MISSING_PATTERN = "^[A-Z0-9_]+_MISSING$"

SCHEMA_NAMES = (
    "preflight",
    "block_receipt",
    "failure_code_map",
    "snapshot_receipt",
    "program_green_receipt",
    "judge_green_ticket",
    "budget_ledger",
)

ROUTE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    (
        "STRUCTURE",
        "机器结构、身份、枚举、必填、唯一性、分母结构和终态互斥。",
    ),
    (
        "BOUNDARY",
        "软分块与事实原子的边界，包括无缺口、无重叠和端点范围。",
    ),
    (
        "FACT",
        "主语、谓语、宾语、结果、极性、事实性及其证据一致。",
    ),
    (
        "QUALIFIER",
        "不得强化、必要限定、限定精度、归因与情态作用域。",
    ),
    (
        "ANCHOR",
        "支持集、逐字定位、物理坐标、最小承托和快照数量。",
    ),
    (
        "PROVENANCE_BUDGET",
        "来源散列、合同锁、隔离、独立裁判、预算和发布闸。",
    ),
)

CONTENT_HARD_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("H01", "原子边界", "BOUNDARY"),
    ("H02", "subject", "FACT"),
    ("H03", "predicate", "FACT"),
    ("H04", "object", "FACT"),
    ("H05", "result", "FACT"),
    ("H06", "polarity", "FACT"),
    ("H07", "actuality 与证据一致", "FACT"),
    ("H08", "不得强化", "QUALIFIER"),
    ("H09", "必要限定类型", "QUALIFIER"),
    ("H10", "限定值精度", "QUALIFIER"),
    ("H11", "归因与情态作用域", "QUALIFIER"),
    ("H12", "最小承托组", "ANCHOR"),
)

# v0.2 没有预先给出细码命名表。B2 v0.1 按每一道已拍板程序闸
# 首次冻结完整登记集；之后出现新细码必须先升级合同，不能落 UNKNOWN 放行。
FINE_CODE_ROWS: tuple[tuple[str, str, str, str], ...] = (
    (
        "PF_ZIP_UNPARSEABLE",
        "P-1",
        "STRUCTURE",
        "输入 zip 不能完整解析。",
    ),
    (
        "PF_WHITELIST_INCOMPLETE",
        "P-1",
        "STRUCTURE",
        "白名单材料不齐。",
    ),
    ("PF_BODY_EMPTY", "P-1", "STRUCTURE", "正文为空。"),
    (
        "PF_CONTRACT_HASH_UNLOCKED",
        "P-1",
        "PROVENANCE_BUDGET",
        "合同散列未冻结。",
    ),
    (
        "PF_FORMAL_GOLD_PLAINTEXT_PRESENT",
        "P-1",
        "PROVENANCE_BUDGET",
        "供料中出现正式金标原文答案。",
    ),
    (
        "PF_SECRET_PRESENT",
        "P-1",
        "PROVENANCE_BUDGET",
        "供料中出现密钥或秘密值。",
    ),
    ("S0_CORE_BELOW_400", "S0", "BOUNDARY", "核心块少于 400 字。"),
    ("S0_CORE_ABOVE_800", "S0", "BOUNDARY", "核心块多于 800 字。"),
    ("S0_CORE_GAP", "S0", "BOUNDARY", "相邻核心块之间存在缺口。"),
    ("S0_CORE_OVERLAP", "S0", "BOUNDARY", "相邻核心块发生重叠。"),
    (
        "S0_PHYSICAL_LINE_COORD_MISSING",
        "S0",
        "ANCHOR",
        "核心块缺少物理行号坐标。",
    ),
    (
        "S0_SOURCE_HASH_MISSING",
        "S0",
        "PROVENANCE_BUDGET",
        "核心块缺少来源散列。",
    ),
    (
        "S0_BLOCK_SIZE_POLICY_MISSING",
        "S0",
        "BOUNDARY",
        "小中大三类块尺寸边界尚未拍板。",
    ),
    (
        "S1_LEDGER_ID_DUPLICATE",
        "S1",
        "STRUCTURE",
        "章节账目身份不唯一。",
    ),
    (
        "S1_ENTITY_ID_DUPLICATE",
        "S1",
        "STRUCTURE",
        "实体身份不唯一。",
    ),
    (
        "S1_COORDINATE_UNPARSEABLE",
        "S1",
        "ANCHOR",
        "账目坐标不能被程序解析。",
    ),
    (
        "S1_S0_REFERENCE_UNRESOLVABLE",
        "S1",
        "ANCHOR",
        "账目或实体不能回引 S0 块。",
    ),
    (
        "M03_RULE_HASH_UNLOCKED",
        "M03",
        "PROVENANCE_BUDGET",
        "规则散列未纳入合同锁。",
    ),
    (
        "M03_SCHEMA_HASH_UNLOCKED",
        "M03",
        "PROVENANCE_BUDGET",
        "Schema 散列未纳入合同锁。",
    ),
    (
        "M03_PROMPT_HASH_UNLOCKED",
        "M03",
        "PROVENANCE_BUDGET",
        "Prompt 散列未纳入合同锁。",
    ),
    (
        "M03_CANARY_HASH_UNLOCKED",
        "M03",
        "PROVENANCE_BUDGET",
        "哨兵散列未纳入合同锁。",
    ),
    ("S3_ID_INVALID", "S3", "STRUCTURE", "身份字段非法。"),
    ("S3_ENUM_INVALID", "S3", "STRUCTURE", "枚举值非法。"),
    (
        "S3_REQUIRED_FIELD_MISSING",
        "S3",
        "STRUCTURE",
        "必填字段缺失。",
    ),
    (
        "S3_SUPPORT_SET_INVALID",
        "S3",
        "ANCHOR",
        "支持集为空、重复或不可解析。",
    ),
    (
        "S3_VERBATIM_LOCATOR_INVALID",
        "S3",
        "ANCHOR",
        "逐字短引不能按坐标定位。",
    ),
    (
        "S3_DENOMINATOR_MISMATCH",
        "S3",
        "PROVENANCE_BUDGET",
        "风险路由分母不一致。",
    ),
    (
        "S3_UPGRADE_RATE_OVER_0_40",
        "S3",
        "PROVENANCE_BUDGET",
        "事实包升级率超过 0.40。",
    ),
    (
        "H01_ATOMIC_BOUNDARY",
        "S3_CONTENT",
        "BOUNDARY",
        "内容硬项 H01：原子边界失败。",
    ),
    (
        "H02_SUBJECT_MISSING_OR_WRONG",
        "S3_CONTENT",
        "FACT",
        "内容硬项 H02：subject 缺失或错误。",
    ),
    (
        "H03_PREDICATE_MISSING_OR_WRONG",
        "S3_CONTENT",
        "FACT",
        "内容硬项 H03：predicate 缺失或错误。",
    ),
    (
        "H04_OBJECT_MISSING_OR_WRONG",
        "S3_CONTENT",
        "FACT",
        "内容硬项 H04：object 缺失或错误。",
    ),
    (
        "H05_RESULT_MISSING_OR_WRONG",
        "S3_CONTENT",
        "FACT",
        "内容硬项 H05：result 缺失或错误。",
    ),
    (
        "H06_POLARITY_MISMATCH",
        "S3_CONTENT",
        "FACT",
        "内容硬项 H06：polarity 不一致。",
    ),
    (
        "H07_ACTUALITY_EVIDENCE_MISMATCH",
        "S3_CONTENT",
        "FACT",
        "内容硬项 H07：actuality 与证据不一致。",
    ),
    (
        "H08_UNSUPPORTED_STRENGTHENING",
        "S3_CONTENT",
        "QUALIFIER",
        "内容硬项 H08：出现无证强化。",
    ),
    (
        "H09_REQUIRED_QUALIFIER_TYPE_MISSING",
        "S3_CONTENT",
        "QUALIFIER",
        "内容硬项 H09：必要限定类型缺失。",
    ),
    (
        "H10_QUALIFIER_VALUE_IMPRECISE",
        "S3_CONTENT",
        "QUALIFIER",
        "内容硬项 H10：限定值不精确。",
    ),
    (
        "H11_ATTRIBUTION_MODALITY_SCOPE_ERROR",
        "S3_CONTENT",
        "QUALIFIER",
        "内容硬项 H11：归因或情态作用域错误。",
    ),
    (
        "H12_MINIMAL_SUPPORT_SET_INVALID",
        "S3_CONTENT",
        "ANCHOR",
        "内容硬项 H12：最小承托组失败。",
    ),
    (
        "S6_FIVE_LAYER_RECOMPUTE_FAILED",
        "S6",
        "STRUCTURE",
        "五层指标不能独立重算。",
    ),
    (
        "S6_H_CODE_NOT_ZERO",
        "S6",
        "STRUCTURE",
        "进入终审时仍有 H 类失败。",
    ),
    (
        "S6_SNAPSHOT_COUNT_MISMATCH",
        "S6",
        "ANCHOR",
        "快照数量不一致。",
    ),
    (
        "S6_SNAPSHOT_HASH_MISMATCH",
        "S6",
        "PROVENANCE_BUDGET",
        "快照散列不一致。",
    ),
    ("S6_SOP_BELOW_0_98", "S6", "ANCHOR", "SOP 低于 0.98。"),
    (
        "S6_MULTIPLE_TERMINAL_STATES",
        "S6",
        "STRUCTURE",
        "同一快照同时声明多个终态。",
    ),
    (
        "J_CANDIDATE_SHA_UNLOCKED",
        "J",
        "PROVENANCE_BUDGET",
        "裁判输入候选 SHA 未锁。",
    ),
    (
        "J_NOT_BLIND",
        "J",
        "PROVENANCE_BUDGET",
        "裁判未按盲判要求执行。",
    ),
    (
        "J_SAME_PRODUCER_FAMILY",
        "J",
        "PROVENANCE_BUDGET",
        "裁判与生产者属于同一家族。",
    ),
    (
        "J_OUTPUT_SCOPE_VIOLATION",
        "J",
        "STRUCTURE",
        "裁判输出超出 verdict、H 码和 fact_id。",
    ),
    (
        "J_TRUST_ROOT_MISSING",
        "J",
        "PROVENANCE_BUDGET",
        "裁判信任根缺失。",
    ),
    (
        "J_TICKET_UNSIGNED",
        "J",
        "PROVENANCE_BUDGET",
        "裁判绿票未签发。",
    ),
    (
        "BUDGET_T1_DEFINITION_MISSING",
        "M07",
        "PROVENANCE_BUDGET",
        "T1 定义尚未拍板。",
    ),
    (
        "BUDGET_T1_VALUE_MISSING",
        "M07",
        "PROVENANCE_BUDGET",
        "T1 数值缺失。",
    ),
    (
        "BUDGET_UNIT_PRICE_MISSING",
        "M07",
        "PROVENANCE_BUDGET",
        "单价缺失。",
    ),
    (
        "BUDGET_K_MISSING",
        "M07",
        "PROVENANCE_BUDGET",
        "K 缺失。",
    ),
    (
        "BUDGET_B_PLUS_3_EXCEEDED",
        "M07",
        "PROVENANCE_BUDGET",
        "普通章调用数超过 B+3。",
    ),
    (
        "BUDGET_B_PLUS_5_EXCEEDED",
        "M07",
        "PROVENANCE_BUDGET",
        "关键章调用数超过 B+5。",
    ),
    (
        "BUDGET_U_DENOMINATOR_INVALID",
        "M07",
        "PROVENANCE_BUDGET",
        "u 未使用事实包数量作分母。",
    ),
    (
        "BUDGET_U_OVER_0_40",
        "M07",
        "PROVENANCE_BUDGET",
        "u 超过 0.40。",
    ),
    (
        "BUDGET_R_OVER_1_35_T1",
        "M07",
        "PROVENANCE_BUDGET",
        "整链成本超过 1.35×T1。",
    ),
    (
        "R_PROGRAM_GREEN_MISSING",
        "R",
        "PROVENANCE_BUDGET",
        "缺程序绿票。",
    ),
    (
        "R_JUDGE_GREEN_MISSING",
        "R",
        "PROVENANCE_BUDGET",
        "缺裁判绿票。",
    ),
    (
        "R_ENGINEERING_GREEN_MISSING",
        "R",
        "PROVENANCE_BUDGET",
        "缺工程绿票。",
    ),
    (
        "R_HASH_UNLOCKED",
        "R",
        "PROVENANCE_BUDGET",
        "候选或合同散列未锁。",
    ),
    (
        "R_BUDGET_NOT_OK",
        "R",
        "PROVENANCE_BUDGET",
        "预算闸未通过。",
    ),
    (
        "R_CANDIDATE_STATUS_INVALID",
        "R",
        "STRUCTURE",
        "发布对象不是 candidate_silver_not_active。",
    ),
    (
        "R_ACTIVE_POINTER_MUTATION",
        "R",
        "PROVENANCE_BUDGET",
        "候选施工改动了现役指针。",
    ),
    (
        "R_PRODUCER_SELF_CHECK_AS_PROGRAM_GREEN",
        "R",
        "PROVENANCE_BUDGET",
        "生产者自检被冒充程序绿票。",
    ),
)

ROUTE_IDS = tuple(row[0] for row in ROUTE_DEFINITIONS)
FINE_CODES = tuple(row[0] for row in FINE_CODE_ROWS)
PREFLIGHT_CODES = tuple(code for code, stage, _, _ in FINE_CODE_ROWS if stage == "P-1")


class ContractValidationError(ValueError):
    """Raised when a schema, example, or bundle violates the frozen contract."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _object_schema(
    properties: Mapping[str, Any],
    required: Sequence[str] | None = None,
    **keywords: Any,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": dict(properties),
        "required": list(required if required is not None else properties),
        "additionalProperties": False,
    }
    schema.update(keywords)
    return schema


def _root_schema(
    name: str,
    title: str,
    properties: Mapping[str, Any],
    required: Sequence[str] | None = None,
    **keywords: Any,
) -> dict[str, Any]:
    schema = _object_schema(properties, required, **keywords)
    schema.update(
        {
            "$schema": DRAFT_2020_12,
            "$id": f"https://local.invalid/contracts/v02/{name}.schema.json",
            "title": title,
        }
    )
    return schema


def _preflight_schema() -> dict[str, Any]:
    check_fields = {
        "zip_parseable": {"type": "boolean"},
        "whitelist_complete": {"type": "boolean"},
        "body_nonempty": {"type": "boolean"},
        "contract_hash_locked": {"type": "boolean"},
        "formal_gold_plaintext_absent": {"type": "boolean"},
        "secrets_absent": {"type": "boolean"},
    }
    schema = _root_schema(
        "preflight",
        "P-1 preflight receipt v0.1",
        {
            "schema_version": {"const": "v02-preflight-receipt-v0.1"},
            "receipt_id": {"type": "string", "minLength": 1},
            "module_id": {"const": "M01"},
            "run_id": {"type": "string", "minLength": 1},
            "contract_hash": {
                "oneOf": [
                    {"type": "string", "pattern": HEX64_PATTERN},
                    {"const": "FULL_CHAIN_CONTRACT_HASH_MISSING"},
                ]
            },
            "contract_hash_scope": {
                "enum": ["FULL_CHAIN_CONTRACT", "B2_SCHEMA_BUNDLE_ONLY"]
            },
            "contract_components": _object_schema(
                {
                    "rules_sha256": {
                        "oneOf": [
                            {"type": "string", "pattern": HEX64_PATTERN},
                            {"const": "RULES_HASH_MISSING"},
                        ]
                    },
                    "schemas_sha256": {
                        "type": "string",
                        "pattern": HEX64_PATTERN,
                    },
                    "prompt_sha256": {
                        "oneOf": [
                            {"type": "string", "pattern": HEX64_PATTERN},
                            {"const": "PROMPT_HASH_MISSING"},
                        ]
                    },
                    "canary_sha256": {
                        "oneOf": [
                            {"type": "string", "pattern": HEX64_PATTERN},
                            {"const": "CANARY_HASH_MISSING"},
                        ]
                    },
                }
            ),
            "checks": _object_schema(check_fields),
            "gate_status": {"enum": ["PASS", "HARD_STOP"]},
            "failure_codes": {
                "type": "array",
                "items": {"enum": list(PREFLIGHT_CODES)},
                "uniqueItems": True,
            },
            "model_api_calls": {"const": 0},
            "network_requests": {"const": 0},
        },
    )
    schema["oneOf"] = [
        {
            "properties": {
                "checks": {
                    "properties": {key: {"const": True} for key in check_fields}
                },
                "gate_status": {"const": "PASS"},
                "failure_codes": {"maxItems": 0},
            }
        },
        {
            "properties": {
                "gate_status": {"const": "HARD_STOP"},
                "failure_codes": {"minItems": 1},
            }
        },
    ]
    return schema


def _block_receipt_schema() -> dict[str, Any]:
    return _root_schema(
        "block_receipt",
        "S0 block receipt v0.1",
        {
            "schema_version": {"const": "v02-block-receipt-v0.1"},
            "receipt_id": {"type": "string", "minLength": 1},
            "module_id": {"const": "M02"},
            "chapter_id": {"type": "string", "minLength": 1},
            "block_id": {"type": "string", "minLength": 1},
            "source_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "contract_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "core_start_char": {"type": "integer", "minimum": 0},
            "core_end_char_exclusive": {"type": "integer", "minimum": 1},
            "core_char_count": {
                "type": "integer",
                "minimum": 400,
                "maximum": 800,
            },
            "physical_line_start": {"type": "integer", "minimum": 1},
            "physical_line_end": {"type": "integer", "minimum": 1},
            "previous_core_end_char_exclusive": {
                "type": "integer",
                "minimum": 0,
            },
            "next_core_start_char": {"type": "integer", "minimum": 1},
            "sequence_gap_chars": {"const": 0},
            "sequence_overlap_chars": {"const": 0},
            "coordinate_unique": {"const": True},
            "s0_reference_resolvable": {"const": True},
            "block_size_policy": _object_schema(
                {
                    "small": {"const": "SMALL_BLOCK_SIZE_MISSING"},
                    "medium": {"const": "MEDIUM_BLOCK_SIZE_MISSING"},
                    "large": {"const": "LARGE_BLOCK_SIZE_MISSING"},
                }
            ),
            "receipt_status": {"const": "BLOCKED_POLICY_MISSING"},
            "failure_codes": {
                "type": "array",
                "items": {"enum": list(FINE_CODES)},
                "minItems": 1,
                "uniqueItems": True,
            },
        },
    )


def _failure_code_map_schema() -> dict[str, Any]:
    route_row = _object_schema(
        {
            "route_id": {"enum": list(ROUTE_IDS)},
            "definition": {"type": "string", "minLength": 1},
        }
    )
    content_row = _object_schema(
        {
            "hard_item_id": {"enum": [row[0] for row in CONTENT_HARD_ITEMS]},
            "meaning": {"type": "string", "minLength": 1},
            "normalized_route": {"enum": list(ROUTE_IDS)},
        }
    )
    fine_row = _object_schema(
        {
            "fine_code": {"enum": list(FINE_CODES)},
            "source_stage": {
                "enum": [
                    "P-1",
                    "S0",
                    "S1",
                    "M03",
                    "S3",
                    "S3_CONTENT",
                    "S6",
                    "J",
                    "M07",
                    "R",
                ]
            },
            "normalized_route": {"enum": list(ROUTE_IDS)},
            "meaning": {"type": "string", "minLength": 1},
        }
    )
    coverage = _object_schema(
        {
            "registered_fine_code_count": {"const": len(FINE_CODE_ROWS)},
            "mapped_fine_code_count": {"const": len(FINE_CODE_ROWS)},
            "route_count": {"const": len(ROUTE_DEFINITIONS)},
            "covered_routes": {
                "type": "array",
                "items": {"enum": list(ROUTE_IDS)},
                "minItems": len(ROUTE_IDS),
                "maxItems": len(ROUTE_IDS),
                "uniqueItems": True,
            },
            "unmapped_codes": {"type": "array", "maxItems": 0},
            "duplicate_codes": {"type": "array", "maxItems": 0},
        }
    )
    return _root_schema(
        "failure_code_map",
        "Fine-code to six-route map v0.1",
        {
            "schema_version": {"const": "v02-failure-code-map-v0.1"},
            "module_id": {"const": "M04"},
            "registry_status": {"const": "FIRST_COMPLETE_FREEZE"},
            "contract_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "unknown_code_policy": {"const": "REJECT"},
            "six_routes_are_not_content_h01_h12": {"const": True},
            "routing_categories": {
                "type": "array",
                "items": route_row,
                "minItems": len(ROUTE_IDS),
                "maxItems": len(ROUTE_IDS),
                "uniqueItems": True,
            },
            "content_hard_items": {
                "type": "array",
                "items": content_row,
                "minItems": len(CONTENT_HARD_ITEMS),
                "maxItems": len(CONTENT_HARD_ITEMS),
                "uniqueItems": True,
            },
            "fine_codes": {
                "type": "array",
                "items": fine_row,
                "minItems": len(FINE_CODE_ROWS),
                "maxItems": len(FINE_CODE_ROWS),
                "uniqueItems": True,
            },
            "coverage": coverage,
        },
    )


def _metrics_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "fcr": {"type": "number", "minimum": 0, "maximum": 1},
            "qcr_full": {"type": "number", "minimum": 0, "maximum": 1},
            "asr_full": {"type": "number", "minimum": 0, "maximum": 1},
            "ucr": {"type": "number", "minimum": 0, "maximum": 1},
            "sop": {"type": "number", "minimum": 0.98, "maximum": 1},
        }
    )


def _terminal_flags_schema() -> dict[str, Any]:
    schema = _object_schema(
        {
            "accepted": {"type": "boolean"},
            "rejected": {"type": "boolean"},
            "hard_stopped": {"type": "boolean"},
        }
    )
    schema["oneOf"] = [
        {
            "properties": {
                "accepted": {"const": True},
                "rejected": {"const": False},
                "hard_stopped": {"const": False},
            }
        },
        {
            "properties": {
                "accepted": {"const": False},
                "rejected": {"const": True},
                "hard_stopped": {"const": False},
            }
        },
        {
            "properties": {
                "accepted": {"const": False},
                "rejected": {"const": False},
                "hard_stopped": {"const": True},
            }
        },
    ]
    return schema


def _snapshot_receipt_schema() -> dict[str, Any]:
    return _root_schema(
        "snapshot_receipt",
        "S6 independent snapshot receipt v0.1",
        {
            "schema_version": {"const": "v02-snapshot-receipt-v0.1"},
            "receipt_id": {"type": "string", "minLength": 1},
            "module_id": {"const": "M05"},
            "candidate_id": {"type": "string", "minLength": 1},
            "candidate_sha256": {
                "type": "string",
                "pattern": HEX64_PATTERN,
            },
            "contract_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "independent_recompute": {"const": True},
            "expected_snapshot_count": {"type": "integer", "minimum": 1},
            "actual_snapshot_count": {"type": "integer", "minimum": 1},
            "expected_snapshot_sha256": {
                "type": "string",
                "pattern": HEX64_PATTERN,
            },
            "actual_snapshot_sha256": {
                "type": "string",
                "pattern": HEX64_PATTERN,
            },
            "remaining_h_code_count": {"const": 0},
            "metrics": _metrics_schema(),
            "terminal_flags": _terminal_flags_schema(),
            "failure_codes": {
                "type": "array",
                "items": {"enum": list(FINE_CODES)},
                "maxItems": 0,
            },
        },
    )


def _program_green_receipt_schema() -> dict[str, Any]:
    return _root_schema(
        "program_green_receipt",
        "Independent program-green format example v0.1",
        {
            "schema_version": {"const": "v02-program-green-receipt-v0.1"},
            "receipt_id": {"type": "string", "minLength": 1},
            "module_id": {"const": "M05"},
            "example_only": {"const": True},
            "receipt_status": {"const": "EXAMPLE_PROGRAM_GREEN_FORMAT_VALID"},
            "candidate_id": {"type": "string", "minLength": 1},
            "candidate_sha256": {
                "type": "string",
                "pattern": HEX64_PATTERN,
            },
            "contract_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "snapshot_receipt_sha256": {
                "type": "string",
                "pattern": HEX64_PATTERN,
            },
            "failure_code_map_sha256": {
                "type": "string",
                "pattern": HEX64_PATTERN,
            },
            "producer_id": {"type": "string", "minLength": 1},
            "issuer_id": {"type": "string", "minLength": 1},
            "issuer_role": {"const": "INDEPENDENT_PROGRAM_VALIDATOR"},
            "producer_selfcheck_present": {"type": "boolean"},
            "producer_selfcheck_evidence_role": {
                "const": "DIAGNOSTIC_ONLY_NOT_GREEN_TICKET"
            },
            "producer_selfcheck_used_as_program_green": {"const": False},
            "remaining_h_code_count": {"const": 0},
            "snapshot_count_and_hash_match": {"const": True},
            "five_layers_independently_recomputed": {"const": True},
            "metrics": _metrics_schema(),
            "hash_locked": {"const": True},
        },
    )


def _judge_green_ticket_schema() -> dict[str, Any]:
    return _root_schema(
        "judge_green_ticket",
        "Judge-green ticket format-only placeholder v0.1",
        {
            "schema_version": {"const": "v02-judge-green-ticket-v0.1"},
            "ticket_id": {"type": "string", "minLength": 1},
            "module_id": {"const": "M06"},
            "format_mode": {"const": "FORMAT_ONLY_UNISSUED"},
            "candidate_id": {"type": "string", "minLength": 1},
            "candidate_sha256": {
                "type": "string",
                "pattern": HEX64_PATTERN,
            },
            "candidate_lock_status": {"const": "HASH_LOCKED"},
            "blind_judging_required": {"const": True},
            "judge_family_must_differ_from_producer": {"const": True},
            "allowed_judge_output_fields": {"const": ["verdict", "h_codes", "fact_id"]},
            "issuance_status": {"const": "UNISSUED"},
            "trust_root_status": {"const": "TRUST_ROOT_MISSING"},
            "trust_root_id": {"const": "TRUST_ROOT_ID_MISSING"},
            "signature": {"type": "null"},
            "verdict": {"type": "null"},
            "h_codes": {"type": "null"},
            "fact_id": {"type": "null"},
            "engineering_gate": {"const": "RED"},
            "activation_allowed": {"const": False},
            "failure_codes": {"const": ["J_TRUST_ROOT_MISSING", "J_TICKET_UNSIGNED"]},
        },
    )


def _budget_ledger_schema() -> dict[str, Any]:
    return _root_schema(
        "budget_ledger",
        "Budget ledger with explicit missing inputs v0.1",
        {
            "schema_version": {"const": "v02-budget-ledger-v0.1"},
            "ledger_id": {"type": "string", "minLength": 1},
            "module_id": {"const": "M07"},
            "candidate_id": {"type": "string", "minLength": 1},
            "contract_hash": {"type": "string", "pattern": HEX64_PATTERN},
            "t1_definition": {"const": "T1_DEFINITION_MISSING"},
            "t1_value": {"const": "T1_VALUE_MISSING"},
            "unit_price": {"const": "UNIT_PRICE_MISSING"},
            "k_value": {"const": "K_VALUE_MISSING"},
            "block_size_policy": _object_schema(
                {
                    "small": {"const": "SMALL_BLOCK_SIZE_MISSING"},
                    "medium": {"const": "MEDIUM_BLOCK_SIZE_MISSING"},
                    "large": {"const": "LARGE_BLOCK_SIZE_MISSING"},
                }
            ),
            "call_caps": _object_schema(
                {
                    "baseline_b": {"const": "B_MISSING"},
                    "normal_chapter_cap": {"const": "B_PLUS_3"},
                    "key_chapter_cap": {"const": "B_PLUS_5"},
                }
            ),
            "upgrade_routing": _object_schema(
                {
                    "numerator": {"const": "UPGRADED_FACT_PACKAGE_COUNT_MISSING"},
                    "denominator": {"const": "FACT_PACKAGE_COUNT_MISSING"},
                    "observed_u": {"const": "U_OBSERVED_MISSING"},
                    "u_cap": {"const": 0.4},
                }
            ),
            "repair_ratio": _object_schema(
                {
                    "observed_r": {"const": "R_OBSERVED_MISSING"},
                    "formula": {"const": "R <= 1.35 * T1"},
                    "cap_multiplier": {"const": 1.35},
                }
            ),
            "budget_status": {"const": "BLOCKED_MISSING_INPUTS"},
            "budget_ok": {"const": False},
            "failure_codes": {
                "const": [
                    "BUDGET_T1_DEFINITION_MISSING",
                    "BUDGET_T1_VALUE_MISSING",
                    "BUDGET_UNIT_PRICE_MISSING",
                    "BUDGET_K_MISSING",
                ]
            },
        },
    )


def build_schemas() -> dict[str, dict[str, Any]]:
    """Return the seven deterministic Draft 2020-12 schemas."""

    return {
        "preflight": _preflight_schema(),
        "block_receipt": _block_receipt_schema(),
        "failure_code_map": _failure_code_map_schema(),
        "snapshot_receipt": _snapshot_receipt_schema(),
        "program_green_receipt": _program_green_receipt_schema(),
        "judge_green_ticket": _judge_green_ticket_schema(),
        "budget_ledger": _budget_ledger_schema(),
    }


def contract_hash_for_schemas(
    schemas: Mapping[str, Mapping[str, Any]],
) -> str:
    rows = [
        {
            "name": name,
            "sha256": _sha256(_json_bytes(schemas[name])),
        }
        for name in SCHEMA_NAMES
    ]
    return _sha256(_canonical_bytes({"schema_hashes": rows}))


def _valid_failure_code_map(contract_hash: str) -> dict[str, Any]:
    fine_rows = [
        {
            "fine_code": code,
            "source_stage": stage,
            "normalized_route": route,
            "meaning": meaning,
        }
        for code, stage, route, meaning in FINE_CODE_ROWS
    ]
    return {
        "schema_version": "v02-failure-code-map-v0.1",
        "module_id": "M04",
        "registry_status": "FIRST_COMPLETE_FREEZE",
        "contract_hash": contract_hash,
        "unknown_code_policy": "REJECT",
        "six_routes_are_not_content_h01_h12": True,
        "routing_categories": [
            {"route_id": route_id, "definition": definition}
            for route_id, definition in ROUTE_DEFINITIONS
        ],
        "content_hard_items": [
            {
                "hard_item_id": hard_id,
                "meaning": meaning,
                "normalized_route": route,
            }
            for hard_id, meaning, route in CONTENT_HARD_ITEMS
        ],
        "fine_codes": fine_rows,
        "coverage": {
            "registered_fine_code_count": len(fine_rows),
            "mapped_fine_code_count": len(fine_rows),
            "route_count": len(ROUTE_IDS),
            "covered_routes": list(ROUTE_IDS),
            "unmapped_codes": [],
            "duplicate_codes": [],
        },
    }


def build_valid_examples(
    schemas: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    contract_hash = contract_hash_for_schemas(schemas)
    failure_map = _valid_failure_code_map(contract_hash)
    failure_map_sha = _sha256(_json_bytes(failure_map))
    snapshot = {
        "schema_version": "v02-snapshot-receipt-v0.1",
        "receipt_id": "EXAMPLE-SNAPSHOT-001",
        "module_id": "M05",
        "candidate_id": "EXAMPLE-CANDIDATE-001",
        "candidate_sha256": "a" * 64,
        "contract_hash": contract_hash,
        "independent_recompute": True,
        "expected_snapshot_count": 3,
        "actual_snapshot_count": 3,
        "expected_snapshot_sha256": "b" * 64,
        "actual_snapshot_sha256": "b" * 64,
        "remaining_h_code_count": 0,
        "metrics": {
            "fcr": 1.0,
            "qcr_full": 1.0,
            "asr_full": 1.0,
            "ucr": 1.0,
            "sop": 0.99,
        },
        "terminal_flags": {
            "accepted": True,
            "rejected": False,
            "hard_stopped": False,
        },
        "failure_codes": [],
    }
    snapshot_sha = _sha256(_json_bytes(snapshot))
    return {
        "preflight": {
            "schema_version": "v02-preflight-receipt-v0.1",
            "receipt_id": "EXAMPLE-PREFLIGHT-001",
            "module_id": "M01",
            "run_id": "EXAMPLE-RUN-001",
            "contract_hash": "FULL_CHAIN_CONTRACT_HASH_MISSING",
            "contract_hash_scope": "B2_SCHEMA_BUNDLE_ONLY",
            "contract_components": {
                "rules_sha256": "RULES_HASH_MISSING",
                "schemas_sha256": contract_hash,
                "prompt_sha256": "PROMPT_HASH_MISSING",
                "canary_sha256": "CANARY_HASH_MISSING",
            },
            "checks": {
                "zip_parseable": True,
                "whitelist_complete": True,
                "body_nonempty": True,
                "contract_hash_locked": False,
                "formal_gold_plaintext_absent": True,
                "secrets_absent": True,
            },
            "gate_status": "HARD_STOP",
            "failure_codes": ["PF_CONTRACT_HASH_UNLOCKED"],
            "model_api_calls": 0,
            "network_requests": 0,
        },
        "block_receipt": {
            "schema_version": "v02-block-receipt-v0.1",
            "receipt_id": "EXAMPLE-BLOCK-001",
            "module_id": "M02",
            "chapter_id": "EXAMPLE-CHAPTER-001",
            "block_id": "EXAMPLE-BLOCK-001",
            "source_hash": "c" * 64,
            "contract_hash": contract_hash,
            "core_start_char": 400,
            "core_end_char_exclusive": 1040,
            "core_char_count": 640,
            "physical_line_start": 21,
            "physical_line_end": 52,
            "previous_core_end_char_exclusive": 400,
            "next_core_start_char": 1040,
            "sequence_gap_chars": 0,
            "sequence_overlap_chars": 0,
            "coordinate_unique": True,
            "s0_reference_resolvable": True,
            "block_size_policy": {
                "small": "SMALL_BLOCK_SIZE_MISSING",
                "medium": "MEDIUM_BLOCK_SIZE_MISSING",
                "large": "LARGE_BLOCK_SIZE_MISSING",
            },
            "receipt_status": "BLOCKED_POLICY_MISSING",
            "failure_codes": ["S0_BLOCK_SIZE_POLICY_MISSING"],
        },
        "failure_code_map": failure_map,
        "snapshot_receipt": snapshot,
        "program_green_receipt": {
            "schema_version": "v02-program-green-receipt-v0.1",
            "receipt_id": "EXAMPLE-PROGRAM-GREEN-001",
            "module_id": "M05",
            "example_only": True,
            "receipt_status": "EXAMPLE_PROGRAM_GREEN_FORMAT_VALID",
            "candidate_id": "EXAMPLE-CANDIDATE-001",
            "candidate_sha256": "a" * 64,
            "contract_hash": contract_hash,
            "snapshot_receipt_sha256": snapshot_sha,
            "failure_code_map_sha256": failure_map_sha,
            "producer_id": "EXAMPLE-PRODUCER-001",
            "issuer_id": "EXAMPLE-INDEPENDENT-VALIDATOR-001",
            "issuer_role": "INDEPENDENT_PROGRAM_VALIDATOR",
            "producer_selfcheck_present": True,
            "producer_selfcheck_evidence_role": ("DIAGNOSTIC_ONLY_NOT_GREEN_TICKET"),
            "producer_selfcheck_used_as_program_green": False,
            "remaining_h_code_count": 0,
            "snapshot_count_and_hash_match": True,
            "five_layers_independently_recomputed": True,
            "metrics": {
                "fcr": 1.0,
                "qcr_full": 1.0,
                "asr_full": 1.0,
                "ucr": 1.0,
                "sop": 0.99,
            },
            "hash_locked": True,
        },
        "judge_green_ticket": {
            "schema_version": "v02-judge-green-ticket-v0.1",
            "ticket_id": "FORMAT-ONLY-JUDGE-TICKET-001",
            "module_id": "M06",
            "format_mode": "FORMAT_ONLY_UNISSUED",
            "candidate_id": "EXAMPLE-CANDIDATE-001",
            "candidate_sha256": "a" * 64,
            "candidate_lock_status": "HASH_LOCKED",
            "blind_judging_required": True,
            "judge_family_must_differ_from_producer": True,
            "allowed_judge_output_fields": [
                "verdict",
                "h_codes",
                "fact_id",
            ],
            "issuance_status": "UNISSUED",
            "trust_root_status": "TRUST_ROOT_MISSING",
            "trust_root_id": "TRUST_ROOT_ID_MISSING",
            "signature": None,
            "verdict": None,
            "h_codes": None,
            "fact_id": None,
            "engineering_gate": "RED",
            "activation_allowed": False,
            "failure_codes": [
                "J_TRUST_ROOT_MISSING",
                "J_TICKET_UNSIGNED",
            ],
        },
        "budget_ledger": {
            "schema_version": "v02-budget-ledger-v0.1",
            "ledger_id": "EXAMPLE-BUDGET-001",
            "module_id": "M07",
            "candidate_id": "EXAMPLE-CANDIDATE-001",
            "contract_hash": contract_hash,
            "t1_definition": "T1_DEFINITION_MISSING",
            "t1_value": "T1_VALUE_MISSING",
            "unit_price": "UNIT_PRICE_MISSING",
            "k_value": "K_VALUE_MISSING",
            "block_size_policy": {
                "small": "SMALL_BLOCK_SIZE_MISSING",
                "medium": "MEDIUM_BLOCK_SIZE_MISSING",
                "large": "LARGE_BLOCK_SIZE_MISSING",
            },
            "call_caps": {
                "baseline_b": "B_MISSING",
                "normal_chapter_cap": "B_PLUS_3",
                "key_chapter_cap": "B_PLUS_5",
            },
            "upgrade_routing": {
                "numerator": "UPGRADED_FACT_PACKAGE_COUNT_MISSING",
                "denominator": "FACT_PACKAGE_COUNT_MISSING",
                "observed_u": "U_OBSERVED_MISSING",
                "u_cap": 0.4,
            },
            "repair_ratio": {
                "observed_r": "R_OBSERVED_MISSING",
                "formula": "R <= 1.35 * T1",
                "cap_multiplier": 1.35,
            },
            "budget_status": "BLOCKED_MISSING_INPUTS",
            "budget_ok": False,
            "failure_codes": [
                "BUDGET_T1_DEFINITION_MISSING",
                "BUDGET_T1_VALUE_MISSING",
                "BUDGET_UNIT_PRICE_MISSING",
                "BUDGET_K_MISSING",
            ],
        },
    }


def build_invalid_examples(
    valid_examples: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    invalid = {name: copy.deepcopy(value) for name, value in valid_examples.items()}
    invalid["preflight"]["unexpected_field"] = "must be rejected"
    invalid["block_receipt"]["core_char_count"] = 801

    invalid["failure_code_map"]["fine_codes"].append(
        {
            "fine_code": "UNKNOWN_FINE_CODE",
            "source_stage": "S3",
            "normalized_route": "STRUCTURE",
            "meaning": "未知码不得进入 UNKNOWN 路由后放行。",
        }
    )
    invalid["failure_code_map"]["coverage"]["registered_fine_code_count"] += 1
    invalid["failure_code_map"]["coverage"]["mapped_fine_code_count"] += 1

    invalid["snapshot_receipt"]["terminal_flags"] = {
        "accepted": True,
        "rejected": True,
        "hard_stopped": True,
    }

    invalid["program_green_receipt"]["issuer_id"] = invalid["program_green_receipt"][
        "producer_id"
    ]
    invalid["program_green_receipt"]["producer_selfcheck_used_as_program_green"] = True

    invalid["judge_green_ticket"].update(
        {
            "format_mode": "ISSUED",
            "issuance_status": "ISSUED",
            "trust_root_status": "TRUSTED",
            "trust_root_id": "FABRICATED-TRUST-ROOT",
            "signature": "FABRICATED-SIGNATURE",
            "verdict": "PASS",
            "h_codes": [],
            "fact_id": "EXAMPLE-FACT-001",
            "engineering_gate": "GREEN",
            "activation_allowed": True,
            "failure_codes": [],
        }
    )

    invalid["budget_ledger"]["budget_status"] = "PASS"
    invalid["budget_ledger"]["budget_ok"] = True
    invalid["budget_ledger"]["failure_codes"] = []
    return invalid


def _type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise ContractValidationError(f"unsupported JSON Schema type: {expected}")


def validate_against_schema(
    instance: Any,
    schema: Mapping[str, Any],
    path: str = "$",
) -> None:
    """Validate the Draft 2020-12 subset used by the seven frozen schemas."""

    if "type" in schema and not _type_matches(instance, str(schema["type"])):
        raise ContractValidationError(
            f"{path}: expected {schema['type']}, got {type(instance).__name__}"
        )
    if "const" in schema and instance != schema["const"]:
        raise ContractValidationError(
            f"{path}: expected const {schema['const']!r}, got {instance!r}"
        )
    if "enum" in schema and instance not in schema["enum"]:
        raise ContractValidationError(f"{path}: value {instance!r} is outside the enum")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            raise ContractValidationError(f"{path}: missing required fields {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(instance) - set(properties))
            if unknown:
                raise ContractValidationError(
                    f"{path}: unknown fields are forbidden: {unknown}"
                )
        for key, child_schema in properties.items():
            if key in instance:
                validate_against_schema(
                    instance[key],
                    child_schema,
                    f"{path}.{key}",
                )
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            raise ContractValidationError(f"{path}: too few properties")
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            raise ContractValidationError(f"{path}: too many properties")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ContractValidationError(f"{path}: too few items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ContractValidationError(f"{path}: too many items")
        if schema.get("uniqueItems") is True:
            encoded = [_canonical_bytes(item) for item in instance]
            if len(encoded) != len(set(encoded)):
                raise ContractValidationError(f"{path}: duplicate items")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(instance):
                validate_against_schema(
                    item,
                    item_schema,
                    f"{path}[{index}]",
                )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise ContractValidationError(f"{path}: string is too short")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise ContractValidationError(f"{path}: string is too long")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise ContractValidationError(
                f"{path}: string does not match {schema['pattern']}"
            )

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ContractValidationError(f"{path}: value is below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ContractValidationError(f"{path}: value is above maximum")

    for child_schema in schema.get("allOf", []):
        validate_against_schema(instance, child_schema, path)
    if "anyOf" in schema:
        matches = 0
        for child_schema in schema["anyOf"]:
            try:
                validate_against_schema(instance, child_schema, path)
            except ContractValidationError:
                continue
            matches += 1
        if matches == 0:
            raise ContractValidationError(f"{path}: no anyOf branch matched")
    if "oneOf" in schema:
        matches = 0
        for child_schema in schema["oneOf"]:
            try:
                validate_against_schema(instance, child_schema, path)
            except ContractValidationError:
                continue
            matches += 1
        if matches != 1:
            raise ContractValidationError(
                f"{path}: expected one oneOf branch, got {matches}"
            )


def _schema_strict_object_count(schema: Mapping[str, Any]) -> int:
    count = 0

    def walk(value: Any, path: str) -> None:
        nonlocal count
        if isinstance(value, dict):
            if value.get("type") == "object":
                count += 1
                if value.get("additionalProperties") is not False:
                    raise ContractValidationError(
                        f"{path}: object schema must reject unknown fields"
                    )
            for key, child in value.items():
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(schema, "$")
    return count


def validate_schema_document(name: str, schema: Mapping[str, Any]) -> int:
    if schema.get("$schema") != DRAFT_2020_12:
        raise ContractValidationError(f"{name}: schema dialect is not Draft 2020-12")
    if schema.get("$id") != (f"https://local.invalid/contracts/v02/{name}.schema.json"):
        raise ContractValidationError(f"{name}: unexpected schema id")
    if not isinstance(schema.get("title"), str) or not schema["title"]:
        raise ContractValidationError(f"{name}: title missing")
    return _schema_strict_object_count(schema)


def _validate_failure_map_semantics(instance: Mapping[str, Any]) -> None:
    expected_routes = dict(ROUTE_DEFINITIONS)
    actual_routes = {
        row["route_id"]: row["definition"] for row in instance["routing_categories"]
    }
    if actual_routes != expected_routes:
        raise ContractValidationError("failure_code_map: six route definitions drifted")

    expected_hard = {
        hard_id: (meaning, route) for hard_id, meaning, route in CONTENT_HARD_ITEMS
    }
    actual_hard = {
        row["hard_item_id"]: (
            row["meaning"],
            row["normalized_route"],
        )
        for row in instance["content_hard_items"]
    }
    if actual_hard != expected_hard:
        raise ContractValidationError("failure_code_map: H01-H12 drifted")

    expected_fine = {
        code: (stage, route, meaning) for code, stage, route, meaning in FINE_CODE_ROWS
    }
    rows = instance["fine_codes"]
    actual_fine: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        code = row["fine_code"]
        if code in actual_fine:
            raise ContractValidationError(
                f"failure_code_map: duplicate fine code {code}"
            )
        actual_fine[code] = (
            row["source_stage"],
            row["normalized_route"],
            row["meaning"],
        )
    if actual_fine != expected_fine:
        missing = sorted(set(expected_fine) - set(actual_fine))
        unknown = sorted(set(actual_fine) - set(expected_fine))
        drifted = sorted(
            code
            for code in set(expected_fine) & set(actual_fine)
            if expected_fine[code] != actual_fine[code]
        )
        raise ContractValidationError(
            "failure_code_map: incomplete or changed mapping; "
            f"missing={missing}, unknown={unknown}, drifted={drifted}"
        )
    coverage = instance["coverage"]
    if coverage["covered_routes"] != list(ROUTE_IDS):
        raise ContractValidationError(
            "failure_code_map: covered route order or membership drifted"
        )
    if coverage["unmapped_codes"] or coverage["duplicate_codes"]:
        raise ContractValidationError(
            "failure_code_map: zero-leak coverage proof failed"
        )


def validate_semantics(name: str, instance: Mapping[str, Any]) -> None:
    if name == "preflight":
        checks = instance["checks"]
        if (
            instance["contract_hash_scope"] == "B2_SCHEMA_BUNDLE_ONLY"
            and checks["contract_hash_locked"]
        ):
            raise ContractValidationError(
                "preflight: B2 schema hash is not a full-chain contract lock"
            )
        if instance["gate_status"] == "PASS":
            if not all(checks.values()) or instance["failure_codes"]:
                raise ContractValidationError(
                    "preflight: PASS requires all checks and zero failures"
                )
        else:
            if all(checks.values()) or not instance["failure_codes"]:
                raise ContractValidationError(
                    "preflight: HARD_STOP needs a failed check and a code"
                )
    elif name == "block_receipt":
        observed = instance["core_end_char_exclusive"] - instance["core_start_char"]
        if observed != instance["core_char_count"]:
            raise ContractValidationError("block_receipt: char count mismatch")
        if (
            instance["previous_core_end_char_exclusive"] != instance["core_start_char"]
            or instance["next_core_start_char"] != instance["core_end_char_exclusive"]
        ):
            raise ContractValidationError("block_receipt: core sequence is not gapless")
        expected_missing = {
            "small": "SMALL_BLOCK_SIZE_MISSING",
            "medium": "MEDIUM_BLOCK_SIZE_MISSING",
            "large": "LARGE_BLOCK_SIZE_MISSING",
        }
        if instance["block_size_policy"] != expected_missing:
            raise ContractValidationError(
                "block_receipt: unknown block sizes must stay explicit"
            )
    elif name == "failure_code_map":
        _validate_failure_map_semantics(instance)
    elif name == "snapshot_receipt":
        flags = instance["terminal_flags"]
        if sum(bool(value) for value in flags.values()) != 1:
            raise ContractValidationError(
                "snapshot_receipt: exactly one terminal state is required"
            )
        if (
            instance["expected_snapshot_count"] != instance["actual_snapshot_count"]
            or instance["expected_snapshot_sha256"]
            != instance["actual_snapshot_sha256"]
        ):
            raise ContractValidationError("snapshot_receipt: count/hash mismatch")
        if flags["accepted"] and (
            instance["remaining_h_code_count"] != 0
            or instance["failure_codes"]
            or instance["metrics"]["sop"] < 0.98
        ):
            raise ContractValidationError(
                "snapshot_receipt: accepted state has a red S6 condition"
            )
    elif name == "program_green_receipt":
        if instance["issuer_id"] == instance["producer_id"]:
            raise ContractValidationError(
                "program_green_receipt: producer cannot validate itself"
            )
        if instance["producer_selfcheck_used_as_program_green"]:
            raise ContractValidationError(
                "program_green_receipt: selfcheck is diagnostic only"
            )
        if not instance["example_only"]:
            raise ContractValidationError(
                "program_green_receipt: B2 may build examples only"
            )
    elif name == "judge_green_ticket":
        if (
            instance["issuance_status"] != "UNISSUED"
            or instance["trust_root_status"] != "TRUST_ROOT_MISSING"
            or instance["signature"] is not None
            or instance["engineering_gate"] != "RED"
            or instance["activation_allowed"]
        ):
            raise ContractValidationError(
                "judge_green_ticket: missing trust root is an engineering red"
            )
    elif name == "budget_ledger":
        missing_values = [
            instance["t1_definition"],
            instance["t1_value"],
            instance["unit_price"],
            instance["k_value"],
            *instance["block_size_policy"].values(),
        ]
        if not all(re.fullmatch(MISSING_PATTERN, value) for value in missing_values):
            raise ContractValidationError(
                "budget_ledger: unknown inputs need *_MISSING values"
            )
        if instance["budget_ok"]:
            raise ContractValidationError(
                "budget_ledger: missing inputs cannot pass the budget gate"
            )
    else:
        raise ContractValidationError(f"unknown schema name: {name}")


def validate_instance(
    name: str,
    instance: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> None:
    validate_against_schema(instance, schema)
    validate_semantics(name, instance)


def validate_examples(
    schemas: Mapping[str, Mapping[str, Any]],
    valid_examples: Mapping[str, Mapping[str, Any]],
    invalid_examples: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if tuple(schemas) != SCHEMA_NAMES:
        raise ContractValidationError("schema set or order drifted")
    if set(valid_examples) != set(SCHEMA_NAMES):
        raise ContractValidationError("valid example set is incomplete")
    if set(invalid_examples) != set(SCHEMA_NAMES):
        raise ContractValidationError("invalid example set is incomplete")

    strict_object_count = 0
    for name in SCHEMA_NAMES:
        strict_object_count += validate_schema_document(name, schemas[name])
        validate_instance(name, valid_examples[name], schemas[name])

    invalid_rejections: dict[str, str] = {}
    for name in SCHEMA_NAMES:
        try:
            validate_instance(name, invalid_examples[name], schemas[name])
        except ContractValidationError as exc:
            invalid_rejections[name] = str(exc)
        else:
            raise ContractValidationError(
                f"{name}: invalid example unexpectedly passed"
            )

    unknown_rejections: dict[str, str] = {}
    for name in SCHEMA_NAMES:
        injected = copy.deepcopy(valid_examples[name])
        injected["__unknown_field__"] = "must reject"
        try:
            validate_instance(name, injected, schemas[name])
        except ContractValidationError as exc:
            unknown_rejections[name] = str(exc)
        else:
            raise ContractValidationError(f"{name}: unknown field unexpectedly passed")

    return {
        "schema_count": len(SCHEMA_NAMES),
        "valid_example_count": len(valid_examples),
        "invalid_example_count": len(invalid_examples),
        "valid_examples_passed": len(valid_examples),
        "invalid_examples_rejected": len(invalid_rejections),
        "unknown_field_injections_rejected": len(unknown_rejections),
        "strict_object_schema_nodes": strict_object_count,
        "invalid_rejections": invalid_rejections,
        "unknown_field_rejections": unknown_rejections,
    }


def _manifest(
    contract_files: Mapping[str, bytes],
    contract_hash: str,
) -> dict[str, Any]:
    inventory = [
        {
            "path": path,
            "bytes": len(data),
            "sha256": _sha256(data),
        }
        for path, data in sorted(contract_files.items())
    ]
    bundle_content_hash = _sha256(_canonical_bytes(inventory))
    return {
        "schema_version": "v02-b2-gate-contract-manifest-v0.1",
        "candidate_id": "B2_gate_contract_v0.1",
        "candidate_status": "candidate_silver_not_active",
        "authority_boundary": {
            "design": "统一设计稿｜抽取工序重设计 v0.2",
            "sections": ["一", "四", "五", "九", "十", "十一", "十二"],
            "work_order": "连夜施工令 B2",
            "local_b2_freeze": (
                "v0.2 未给既定细码命名表；本候选按逐闸要求首次冻结完整细码集。"
            ),
        },
        "scope": {
            "pipeline": ["P-1", "S0", "S1", "S2", "S3", "S4", "S5", "S6", "J", "R"],
            "model_api_calls": 0,
            "network_requests": 0,
            "active_pointer_changed": False,
            "formal_gold_changed": False,
            "default_chain_changed": False,
        },
        "contract_hash": contract_hash,
        "contract_hash_scope": "B2_SCHEMA_BUNDLE_ONLY",
        "full_chain_contract_lock": {
            "required_components": ["rules", "schemas", "prompt", "canary"],
            "rules_sha256": "RULES_HASH_MISSING",
            "schemas_sha256": contract_hash,
            "prompt_sha256": "PROMPT_HASH_MISSING",
            "canary_sha256": "CANARY_HASH_MISSING",
            "full_chain_contract_hash": "FULL_CHAIN_CONTRACT_HASH_MISSING",
            "full_chain_hash_locked": False,
            "engineering_gate": "RED",
        },
        "bundle_content_hash": bundle_content_hash,
        "artifact_count": len(inventory),
        "artifacts": inventory,
        "schema_inventory": [
            {
                "name": name,
                "schema_path": f"schemas/{name}.schema.json",
                "valid_example_path": f"examples/valid/{name}.json",
                "invalid_example_path": f"examples/invalid/{name}.json",
                "draft": "2020-12",
            }
            for name in SCHEMA_NAMES
        ],
        "module_ownership": [
            {
                "module_id": "M01",
                "responsibility": "P-1 预检与硬停回执",
                "artifacts": ["preflight"],
            },
            {
                "module_id": "M02",
                "responsibility": "S0 坐标与 block_receipt",
                "artifacts": ["block_receipt"],
            },
            {
                "module_id": "M03",
                "responsibility": "规则、Schema、Prompt、哨兵的 contract_hash 锁",
                "artifacts": [
                    "manifest.contract_hash",
                    "manifest.full_chain_contract_lock",
                    "schema_inventory",
                ],
            },
            {
                "module_id": "M04",
                "responsibility": "全部细失败码唯一归一到六类路由",
                "artifacts": ["failure_code_map"],
            },
            {
                "module_id": "M05",
                "responsibility": "S6 快照独立重算与程序绿票格式",
                "artifacts": ["snapshot_receipt", "program_green_receipt"],
            },
            {
                "module_id": "M06",
                "responsibility": "裁判票格式与信任根缺失红灯",
                "artifacts": ["judge_green_ticket"],
            },
            {
                "module_id": "M07",
                "responsibility": "B+3、B+5、u、R 的预算总账",
                "artifacts": ["budget_ledger"],
            },
            {
                "module_id": "M09",
                "responsibility": "candidate_silver_not_active 发布隔离",
                "artifacts": ["manifest.release_isolation"],
            },
        ],
        "failure_code_coverage": {
            "fine_code_count": len(FINE_CODES),
            "route_count": len(ROUTE_IDS),
            "covered_routes": list(ROUTE_IDS),
            "content_hard_item_count": len(CONTENT_HARD_ITEMS),
            "unmapped_code_count": 0,
            "duplicate_code_count": 0,
            "unknown_code_policy": "REJECT",
        },
        "explicit_missing_values": [
            "T1_DEFINITION_MISSING",
            "T1_VALUE_MISSING",
            "UNIT_PRICE_MISSING",
            "K_VALUE_MISSING",
            "SMALL_BLOCK_SIZE_MISSING",
            "MEDIUM_BLOCK_SIZE_MISSING",
            "LARGE_BLOCK_SIZE_MISSING",
            "RULES_HASH_MISSING",
            "PROMPT_HASH_MISSING",
            "CANARY_HASH_MISSING",
            "FULL_CHAIN_CONTRACT_HASH_MISSING",
        ],
        "release_isolation": {
            "required_candidate_status": "candidate_silver_not_active",
            "program_green_issued": False,
            "judge_green_issued": False,
            "engineering_green": False,
            "b2_schema_bundle_hash_locked": True,
            "full_chain_hash_locked": False,
            "budget_ok": False,
            "activation_allowed": False,
        },
        "activation_formula": (
            "PROGRAM_GREEN && JUDGE_GREEN && ENGINEERING_GREEN && "
            "HASH_LOCKED && BUDGET_OK && candidate_silver_not_active"
        ),
        "producer_selfcheck_authority": "DIAGNOSTIC_ONLY_NOT_GREEN_TICKET",
    }


def build_artifacts() -> dict[str, bytes]:
    schemas = build_schemas()
    valid = build_valid_examples(schemas)
    invalid = build_invalid_examples(valid)
    stats = validate_examples(schemas, valid, invalid)
    contract_hash = contract_hash_for_schemas(schemas)

    contract_files: dict[str, bytes] = {}
    for name in SCHEMA_NAMES:
        contract_files[f"schemas/{name}.schema.json"] = _json_bytes(schemas[name])
        contract_files[f"examples/valid/{name}.json"] = _json_bytes(valid[name])
        contract_files[f"examples/invalid/{name}.json"] = _json_bytes(invalid[name])

    manifest = _manifest(contract_files, contract_hash)
    manifest_bytes = _json_bytes(manifest)
    acceptance = {
        "schema_version": "v02-b2-gate-contract-acceptance-v0.1",
        "candidate_id": "B2_gate_contract_v0.1",
        "candidate_status": "candidate_silver_not_active",
        "contract_hash": contract_hash,
        "manifest_sha256": _sha256(manifest_bytes),
        "model_api_calls": 0,
        "network_requests": 0,
        "checks": {
            "draft_2020_12_schema_count": stats["schema_count"],
            "valid_examples_passed": stats["valid_examples_passed"],
            "invalid_examples_rejected": stats["invalid_examples_rejected"],
            "unknown_field_injections_rejected": stats[
                "unknown_field_injections_rejected"
            ],
            "strict_object_schema_nodes": stats["strict_object_schema_nodes"],
            "fine_codes_mapped": len(FINE_CODES),
            "six_routes_covered": len(ROUTE_IDS),
            "unmapped_codes": 0,
            "duplicate_codes": 0,
            "producer_selfcheck_as_green_rejected": True,
            "snapshot_three_terminal_states_rejected": True,
            "fabricated_judge_trust_root_rejected": True,
            "unknown_fine_code_rejected": True,
            "judge_ticket_issued": False,
            "b2_schema_bundle_hash_locked": True,
            "full_chain_hash_locked": False,
            "engineering_gate": "RED",
            "activation_allowed": False,
        },
        "result": "PASS_CONTRACT_FORMAT_ONLY_NOT_ACTIVATED",
    }
    return {
        **contract_files,
        "manifest.json": manifest_bytes,
        "acceptance_receipt.json": _json_bytes(acceptance),
    }


def _artifact_tree_hash(artifacts: Mapping[str, bytes]) -> str:
    rows = [
        {"path": path, "sha256": _sha256(data), "bytes": len(data)}
        for path, data in sorted(artifacts.items())
    ]
    return _sha256(_canonical_bytes(rows))


def write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, data in artifacts.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def check_bundle(bundle_dir: Path) -> dict[str, Any]:
    schemas: dict[str, dict[str, Any]] = {}
    valid: dict[str, dict[str, Any]] = {}
    invalid: dict[str, dict[str, Any]] = {}
    for name in SCHEMA_NAMES:
        schema_path = bundle_dir / f"schemas/{name}.schema.json"
        valid_path = bundle_dir / f"examples/valid/{name}.json"
        invalid_path = bundle_dir / f"examples/invalid/{name}.json"
        for path in (schema_path, valid_path, invalid_path):
            if not path.is_file():
                raise ContractValidationError(f"missing bundle file: {path}")
        schemas[name] = json.loads(schema_path.read_text(encoding="utf-8"))
        valid[name] = json.loads(valid_path.read_text(encoding="utf-8"))
        invalid[name] = json.loads(invalid_path.read_text(encoding="utf-8"))

    stats = validate_examples(schemas, valid, invalid)
    manifest_path = bundle_dir / "manifest.json"
    acceptance_path = bundle_dir / "acceptance_receipt.json"
    if not manifest_path.is_file() or not acceptance_path.is_file():
        raise ContractValidationError("manifest or acceptance receipt is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))

    if manifest["candidate_status"] != "candidate_silver_not_active":
        raise ContractValidationError("manifest: candidate isolation drifted")
    if manifest["contract_hash"] != contract_hash_for_schemas(schemas):
        raise ContractValidationError("manifest: contract hash mismatch")
    inventory_paths = {row["path"] for row in manifest["artifacts"]}
    expected_paths = {
        f"{kind}/{state}/{name}.json"
        if kind == "examples"
        else f"schemas/{name}.schema.json"
        for name in SCHEMA_NAMES
        for kind, state in (
            ("schemas", ""),
            ("examples", "valid"),
            ("examples", "invalid"),
        )
    }
    if inventory_paths != expected_paths:
        raise ContractValidationError("manifest: artifact inventory incomplete")
    for row in manifest["artifacts"]:
        path = bundle_dir / row["path"]
        data = path.read_bytes()
        if row["bytes"] != len(data) or row["sha256"] != _sha256(data):
            raise ContractValidationError(f"manifest: artifact changed: {row['path']}")
    if acceptance["manifest_sha256"] != _sha256(manifest_path.read_bytes()):
        raise ContractValidationError("acceptance: manifest SHA mismatch")
    if acceptance["checks"]["fine_codes_mapped"] != len(FINE_CODES):
        raise ContractValidationError("acceptance: fine-code count mismatch")
    return {
        "result": "PASS",
        "schema_count": stats["schema_count"],
        "valid_examples_passed": stats["valid_examples_passed"],
        "invalid_examples_rejected": stats["invalid_examples_rejected"],
        "unknown_field_injections_rejected": stats["unknown_field_injections_rejected"],
        "fine_codes_mapped": len(FINE_CODES),
        "routes_covered": len(ROUTE_IDS),
        "contract_hash": manifest["contract_hash"],
        "manifest_sha256": _sha256(manifest_path.read_bytes()),
    }


def write_double_run_receipt(bundle_dir: Path) -> dict[str, Any]:
    first = build_artifacts()
    second = build_artifacts()
    if first != second:
        raise ContractValidationError("two in-memory builds differ")

    with tempfile.TemporaryDirectory(prefix="v02-b2-pass1-") as first_tmp:
        with tempfile.TemporaryDirectory(prefix="v02-b2-pass2-") as second_tmp:
            first_dir = Path(first_tmp)
            second_dir = Path(second_tmp)
            write_artifacts(first_dir, first)
            write_artifacts(second_dir, second)
            first_readback = {path: (first_dir / path).read_bytes() for path in first}
            second_readback = {
                path: (second_dir / path).read_bytes() for path in second
            }
            if first_readback != second_readback:
                raise ContractValidationError(
                    "two directory readbacks are not byte-identical"
                )
            check_bundle(first_dir)
            check_bundle(second_dir)

    target = {
        path: (bundle_dir / path).read_bytes()
        for path in first
        if (bundle_dir / path).is_file()
    }
    if target != first:
        missing = sorted(set(first) - set(target))
        changed = sorted(
            path for path in set(first) & set(target) if first[path] != target[path]
        )
        raise ContractValidationError(
            f"target differs from deterministic build; missing={missing}, "
            f"changed={changed}"
        )
    tree_hash = _artifact_tree_hash(first)
    receipt = {
        "schema_version": "v02-b2-double-run-receipt-v0.1",
        "candidate_id": "B2_gate_contract_v0.1",
        "pass1_tree_sha256": tree_hash,
        "pass2_tree_sha256": _artifact_tree_hash(second),
        "target_tree_sha256": _artifact_tree_hash(target),
        "compared_file_count": len(first),
        "byte_identical": True,
        "pass1_validation": "PASS",
        "pass2_validation": "PASS",
        "target_validation": "PASS",
        "model_api_calls": 0,
        "network_requests": 0,
    }
    (bundle_dir / "double_run_receipt.json").write_bytes(_json_bytes(receipt))
    return receipt


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or validate the offline B2 gate-contract bundle."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_BUNDLE_DIR,
    )

    validate = subparsers.add_parser("validate-bundle")
    validate.add_argument(
        "--bundle-dir",
        type=Path,
        default=DEFAULT_BUNDLE_DIR,
    )

    double_run = subparsers.add_parser("double-run")
    double_run.add_argument(
        "--bundle-dir",
        type=Path,
        default=DEFAULT_BUNDLE_DIR,
    )

    validate_instance_parser = subparsers.add_parser("validate-instance")
    validate_instance_parser.add_argument(
        "--name",
        choices=SCHEMA_NAMES,
        required=True,
    )
    validate_instance_parser.add_argument("--schema", type=Path, required=True)
    validate_instance_parser.add_argument("--instance", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "build":
        artifacts = build_artifacts()
        write_artifacts(args.output_dir, artifacts)
        result = {
            "result": "BUILT",
            "output_dir": str(args.output_dir),
            "file_count": len(artifacts),
            "tree_sha256": _artifact_tree_hash(artifacts),
        }
    elif args.command == "validate-bundle":
        result = check_bundle(args.bundle_dir)
    elif args.command == "double-run":
        result = write_double_run_receipt(args.bundle_dir)
    else:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        instance = json.loads(args.instance.read_text(encoding="utf-8"))
        validate_schema_document(args.name, schema)
        validate_instance(args.name, instance, schema)
        result = {
            "result": "PASS",
            "schema_name": args.name,
            "instance": str(args.instance),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
