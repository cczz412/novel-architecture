#!/usr/bin/env python3
"""C15 管线化 v1 第一阶段候选件。

本工具只做离线、确定性的五件事：

1. 冻结正文来源目录（S0）；
2. 按来源 ID 程序回填逐字证据（S3）；
3. 构造并验证程序分块计划（S1）；
4. 验证问题单和修补白名单（S4）；
5. 生成 Q3 修补 A/B 实验预注册件。

它不导入 HTTP 客户端，不读取密钥，不发送模型请求，不修改现役链。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import v02_anchor_first_experiment as anchor_first  # noqa: E402
import v02_gate_contracts as gate_contracts  # noqa: E402


DEFAULT_CONTRACT_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C15_pipeline_v1_20260726"
)
DEFAULT_RUN_DIR = REPO_ROOT / "runs" / "V02_C15_pipeline_v1_r01_20260726"
DEFAULT_REPORT_DIR = REPO_ROOT / "reports" / "V02_C15_pipeline_v1_20260726"

C2_RAW_RESPONSE = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C2_r01_20260725"
    / "samples"
    / "main"
    / "B02-U0039"
    / "transport"
    / "raw_responses"
    / "attempt01.json"
)
C2_CATALOG = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C2_r01_20260725"
    / "prepared"
    / "catalogs"
    / "B02-U0039.json"
)
C2_REQUEST = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C2_r01_20260725"
    / "samples"
    / "main"
    / "B02-U0039"
    / "transport"
    / "request.json"
)
C2_HARD_STOP = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C2_r01_20260725"
    / "hard_stop.json"
)
C5_RAW_RESPONSE = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C5稳定性_r04_20260725"
    / "samples"
    / "stability"
    / "B01-U0033"
    / "transport"
    / "raw_responses"
    / "attempt01.json"
)
C5_CATALOG = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C5稳定性_r04_20260725"
    / "prepared"
    / "catalogs"
    / "B01-U0033.json"
)
C5_REQUEST = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C5稳定性_r04_20260725"
    / "samples"
    / "stability"
    / "B01-U0033"
    / "transport"
    / "request.json"
)
C5_HARD_STOP = (
    REPO_ROOT
    / "runs"
    / "V02_实验A锚先行倒装_C5稳定性_r04_20260725"
    / "hard_stop.json"
)
B4_CASEBOOK = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B4_1_granularity_casebook"
    / "casebook.json"
)
C13_PROMPT_CONTRACT = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C13_downstream_consumer_r02_20260726"
    / "contracts"
    / "prompt_contract.json"
)
C5_STABILITY_AUDIT = (
    REPO_ROOT
    / "reports"
    / "抽取工序重设计v0.2_连夜施工_20260725"
    / "C5_稳定性复测硬停审计.json"
)

SEALED_FILES = (
    C2_RAW_RESPONSE,
    C2_CATALOG,
    C2_REQUEST,
    C2_HARD_STOP,
    C5_RAW_RESPONSE,
    C5_CATALOG,
    C5_REQUEST,
    C5_HARD_STOP,
    B4_CASEBOOK,
    C13_PROMPT_CONTRACT,
    C5_STABILITY_AUDIT,
)
SEALED_DIRECTORIES = tuple(
    sorted(
        {
            REPO_ROOT
            / "runs"
            / "V02_C13_downstream_consumer_execution_r07_20260726",
            REPO_ROOT
            / "runs"
            / "V02_C13_downstream_consumer_rehearsal_r07_20260726",
            REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C2_r01_20260725",
            REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C3_r02_20260725",
            REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C4_r03_20260725",
            REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C5稳定性_r04_20260725",
            REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C6对照臂_r05_20260725",
            *(REPO_ROOT / "runs").glob("Z89_*"),
            *(REPO_ROOT / "runs").glob("Z91_*"),
        },
        key=lambda path: path.as_posix(),
    )
)

RUN_ID = "V02_C15_pipeline_v1_r01_20260726"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_CODE_RE = re.compile(r"^[A-Z0-9-]+-(?:P|S)\d{4}$")

C15_DIAGNOSTIC_BINDINGS: tuple[tuple[str, str, str], ...] = (
    (
        "PROVENANCE_SOURCE_EMPTY",
        "PF_BODY_EMPTY",
        "冻结正文为空，不能建立来源真源。",
    ),
    (
        "PROVENANCE_SOURCE_HASH_MISMATCH",
        "S6_SNAPSHOT_HASH_MISMATCH",
        "正文、目录或运行票登记的来源散列不一致。",
    ),
    (
        "BOUNDARY_SOURCE_RANGEREVERSED",
        "H01_ATOMIC_BOUNDARY",
        "来源单元字符区间端点逆序。",
    ),
    (
        "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
        "S3_ENUM_INVALID",
        "修补触碰问题单未授权的操作或字段。",
    ),
    (
        "MISSING_REQUIRES_CALIBRATION",
        "S0_BLOCK_SIZE_POLICY_MISSING",
        "运行所需阈值尚未通过校准冻结。",
    ),
)
DIAGNOSTIC_TO_FINE_CODE = {
    diagnostic_label: fine_code
    for diagnostic_label, fine_code, _ in C15_DIAGNOSTIC_BINDINGS
}
FROZEN_FINE_CODE_ROWS = {
    code: {
        "stage": stage,
        "normalized_route": route,
        "meaning": meaning,
    }
    for code, stage, route, meaning in gate_contracts.FINE_CODE_ROWS
}

C13_MISSING_BUCKETS: tuple[str, ...] = (
    "ATTRIBUTION_MISSING",
    "REALIS_MODALITY_POLARITY_MISSING",
    "COREFERENCE_UNRESOLVED",
    "SUBJECT_PREDICATE_OBJECT_MISSING",
    "STATE_SLOT_MISSING",
    "TIME_CHAPTER_ORDER_MISSING",
    "FACT_NOT_EXTRACTED",
    "SCENE_VISUAL_MISSING",
    "EMOTION_INTENSITY_MISSING",
)
Z89_ISSUE_TYPES: tuple[str, ...] = (
    "QUALIFIER_MISSING",
    "MULTIPLE_ATOMS_COMPRESSED",
)
PATCH_OPERATIONS: dict[str, tuple[str, ...]] = {
    "A_FLASH_SELF_REPAIR": (
        "add_fixed_metadata",
        "replace_field",
        "replace_source_ids",
    ),
    "B_V4_PRO_PATCH": (
        "add_fixed_metadata",
        "replace_field",
        "replace_source_ids",
        "add_fact",
        "split_fact",
        "replace_qualifier",
    ),
}
PATCH_ENVELOPE_FIELDS = {
    "issue_id",
    "operation",
    "target_field",
    "fact_scope_id",
    "full_chunk_rewrite",
    "object_id",
    "before_object",
    "after_object",
}


class C15ContractError(ValueError):
    """C15 候选合同的机械验收失败。"""

    def __init__(self, diagnostic_label: str, message: str) -> None:
        if diagnostic_label not in DIAGNOSTIC_TO_FINE_CODE:
            raise ValueError(
                f"C15 未登记诊断标签，拒绝进入运行时：{diagnostic_label}"
            )
        super().__init__(message)
        self.diagnostic_label = diagnostic_label
        self.failure_code = DIAGNOSTIC_TO_FINE_CODE[diagnostic_label]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _sha_without_field(value: Mapping[str, Any], field: str) -> str:
    clone = copy.deepcopy(dict(value))
    clone.pop(field, None)
    return canonical_sha(clone)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def failure_code_binding() -> dict[str, Any]:
    rows = [
        {
            "diagnostic_label": diagnostic_label,
            "existing_fine_code": fine_code,
            "normalized_route": FROZEN_FINE_CODE_ROWS[fine_code][
                "normalized_route"
            ],
            "meaning": meaning,
        }
        for diagnostic_label, fine_code, meaning in C15_DIAGNOSTIC_BINDINGS
    ]
    return {
        "schema_version": "v02-c15-frozen-failure-code-binding.v1",
        "base_contract": "B2_gate_contract_v0.1",
        "base_routes": list(gate_contracts.ROUTE_IDS),
        "frozen_spectrum_unchanged": True,
        "spectrum_extension_count": 0,
        "diagnostic_bindings": rows,
        "unknown_code_policy": "REJECT",
        "candidate_status": "candidate_silver_not_active",
    }


def validate_failure_code_binding(value: Mapping[str, Any]) -> None:
    if value.get("unknown_code_policy") != "REJECT":
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "C15 诊断标签绑定必须保持未知码拒收。",
        )
    if (
        value.get("frozen_spectrum_unchanged") is not True
        or value.get("spectrum_extension_count") != 0
    ):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "C15 不得扩展冻结失败码谱系。",
        )
    rows = value.get("diagnostic_bindings")
    if not isinstance(rows, list):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "C15 缺诊断标签到现有失败码的绑定表。",
        )
    actual = {
        (
            row.get("diagnostic_label"),
            row.get("existing_fine_code"),
            row.get("meaning"),
        )
        for row in rows
        if isinstance(row, Mapping)
    }
    expected = set(C15_DIAGNOSTIC_BINDINGS)
    if actual != expected:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "C15 诊断标签绑定有漏项、未知项或映射漂移。",
        )
    for row in rows:
        fine_code = row["existing_fine_code"]
        if fine_code not in gate_contracts.FINE_CODES:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "C15 诊断标签绑定到了冻结谱系之外。",
            )
        if (
            row["normalized_route"]
            != FROZEN_FINE_CODE_ROWS[fine_code]["normalized_route"]
        ):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "C15 诊断标签绑定的六类路由与冻结登记不一致。",
            )


def _paragraph_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        end = cursor + len(line)
        spans.append((cursor, end, line))
        cursor = end
    if cursor < len(text):
        spans.append((cursor, len(text), text[cursor:]))
    return spans


def _sentence_spans(
    paragraph_text: str,
    *,
    base_offset: int,
) -> list[tuple[int, int, str]]:
    if not paragraph_text:
        return []
    spans: list[tuple[int, int, str]] = []
    start = 0
    cursor = 0
    punctuation = "。！？!?；;…"
    while cursor < len(paragraph_text):
        char = paragraph_text[cursor]
        cursor += 1
        if char not in punctuation:
            continue
        while cursor < len(paragraph_text) and paragraph_text[cursor] in punctuation:
            cursor += 1
        while cursor < len(paragraph_text) and paragraph_text[cursor].isspace():
            cursor += 1
        spans.append(
            (
                base_offset + start,
                base_offset + cursor,
                paragraph_text[start:cursor],
            )
        )
        start = cursor
    if start < len(paragraph_text):
        spans.append(
            (
                base_offset + start,
                base_offset + len(paragraph_text),
                paragraph_text[start:],
            )
        )
    return spans


def build_source_catalog(
    *,
    run_id: str,
    source_id: str,
    chapter: int,
    source_text: str,
) -> dict[str, Any]:
    if not source_text:
        raise C15ContractError(
            "PROVENANCE_SOURCE_EMPTY",
            "正文为空，不能冻结来源目录。",
        )
    paragraphs = []
    sentences = []
    sentence_index = 1
    for paragraph_index, (start, end, original) in enumerate(
        _paragraph_spans(source_text),
        start=1,
    ):
        paragraph_id = f"{source_id}-P{paragraph_index:04d}"
        paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "char_start": start,
                "char_end_exclusive": end,
                "original_text": original,
            }
        )
        for sentence_start, sentence_end, sentence_text in _sentence_spans(
            original,
            base_offset=start,
        ):
            sentences.append(
                {
                    "sentence_id": f"{source_id}-S{sentence_index:04d}",
                    "paragraph_id": paragraph_id,
                    "char_start": sentence_start,
                    "char_end_exclusive": sentence_end,
                    "original_text": sentence_text,
                }
            )
            sentence_index += 1

    catalog: dict[str, Any] = {
        "schema_version": "v02-c15-source-catalog.v1",
        "run_id": run_id,
        "source_id": source_id,
        "chapter": chapter,
        "coordinate_unit": "PYTHON_UNICODE_CODEPOINT_INDEX",
        "source_text": source_text,
        "source_body_sha256": sha256_bytes(source_text.encode("utf-8")),
        "paragraphs": paragraphs,
        "sentences": sentences,
        "catalog_sha256": "",
        "candidate_status": "candidate_silver_not_active",
    }
    catalog["catalog_sha256"] = _sha_without_field(catalog, "catalog_sha256")
    return catalog


def build_source_run_ticket(catalog: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "v02-c15-source-run-ticket.v1",
        "run_id": catalog["run_id"],
        "source_id": catalog["source_id"],
        "source_body_sha256": catalog["source_body_sha256"],
        "catalog_sha256": catalog["catalog_sha256"],
        "model_api_calls": 0,
        "network_requests": 0,
        "candidate_status": "candidate_silver_not_active",
    }


def _validate_ordered_units(
    *,
    units: Any,
    id_field: str,
    source_text: str,
    require_contiguous: bool,
) -> None:
    if not isinstance(units, list) or not units:
        raise C15ContractError(
            "PROVENANCE_SOURCE_EMPTY",
            f"{id_field} 单元为空。",
        )
    observed_ids: set[str] = set()
    previous_end = 0
    rebuilt: list[str] = []
    for unit in units:
        if not isinstance(unit, Mapping):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                f"{id_field} 条目不是对象。",
            )
        unit_id = unit.get(id_field)
        if (
            not isinstance(unit_id, str)
            or unit_id in observed_ids
            or not SOURCE_CODE_RE.fullmatch(unit_id)
        ):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                f"{id_field} 缺失、重复或格式非法。",
            )
        observed_ids.add(unit_id)
        start = unit.get("char_start")
        end = unit.get("char_end_exclusive")
        if not isinstance(start, int) or not isinstance(end, int):
            raise C15ContractError(
                "BOUNDARY_SOURCE_RANGEREVERSED",
                f"{unit_id} 字符区间不是整数。",
            )
        if end <= start:
            raise C15ContractError(
                "BOUNDARY_SOURCE_RANGEREVERSED",
                f"{unit_id} 字符区间逆序或为空。",
            )
        if start < previous_end or (require_contiguous and start != previous_end):
            raise C15ContractError(
                "BOUNDARY_SOURCE_RANGEREVERSED",
                f"{unit_id} 字符区间乱序、重叠或有缺口。",
            )
        original = unit.get("original_text")
        if not isinstance(original, str) or source_text[start:end] != original:
            raise C15ContractError(
                "PROVENANCE_SOURCE_HASH_MISMATCH",
                f"{unit_id} 不能按字符区间逐字回贴正文。",
            )
        rebuilt.append(original)
        previous_end = end
    if require_contiguous and (
        previous_end != len(source_text) or "".join(rebuilt) != source_text
    ):
        raise C15ContractError(
            "PROVENANCE_SOURCE_HASH_MISMATCH",
            f"{id_field} 不能逐字重建全文。",
        )


def validate_source_catalog(
    catalog: Mapping[str, Any],
    *,
    run_ticket: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_text = catalog.get("source_text")
    if not isinstance(source_text, str) or not source_text:
        raise C15ContractError(
            "PROVENANCE_SOURCE_EMPTY",
            "source_text 为空。",
        )
    if catalog.get("source_body_sha256") != sha256_bytes(source_text.encode("utf-8")):
        raise C15ContractError(
            "PROVENANCE_SOURCE_HASH_MISMATCH",
            "source_body_sha256 与正文不一致。",
        )
    expected_catalog_sha = _sha_without_field(catalog, "catalog_sha256")
    if catalog.get("catalog_sha256") != expected_catalog_sha:
        raise C15ContractError(
            "PROVENANCE_SOURCE_HASH_MISMATCH",
            "catalog_sha256 与目录载荷不一致。",
        )
    _validate_ordered_units(
        units=catalog.get("paragraphs"),
        id_field="paragraph_id",
        source_text=source_text,
        require_contiguous=True,
    )
    _validate_ordered_units(
        units=catalog.get("sentences"),
        id_field="sentence_id",
        source_text=source_text,
        require_contiguous=True,
    )
    paragraph_ids = {
        row["paragraph_id"]
        for row in catalog["paragraphs"]
        if isinstance(row, Mapping)
    }
    if any(
        row.get("paragraph_id") not in paragraph_ids
        for row in catalog["sentences"]
        if isinstance(row, Mapping)
    ):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "sentence 引用了目录外 paragraph_id。",
        )
    if run_ticket is not None:
        expected = {
            "run_id": catalog.get("run_id"),
            "source_id": catalog.get("source_id"),
            "source_body_sha256": catalog.get("source_body_sha256"),
            "catalog_sha256": catalog.get("catalog_sha256"),
        }
        observed = {key: run_ticket.get(key) for key in expected}
        if observed != expected:
            raise C15ContractError(
                "PROVENANCE_SOURCE_HASH_MISMATCH",
                "来源运行票与目录身份或散列不一致。",
            )
    return {
        "status": "PASS",
        "paragraph_count": len(catalog["paragraphs"]),
        "sentence_count": len(catalog["sentences"]),
        "source_body_sha256": catalog["source_body_sha256"],
        "catalog_sha256": catalog["catalog_sha256"],
    }


def build_chunk_plan(
    catalog: Mapping[str, Any],
    *,
    primary_ranges: Sequence[tuple[int, int]] | None,
    context_chars: int = 0,
    diagnostic_risks: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if context_chars < 0:
        raise C15ContractError(
            "BOUNDARY_SOURCE_RANGEREVERSED",
            "context_chars 不得为负数。",
        )
    if primary_ranges is None:
        plan: dict[str, Any] = {
            "schema_version": "v02-c15-chunk-plan.v1",
            "run_id": catalog["run_id"],
            "source_id": catalog["source_id"],
            "source_catalog_sha256": catalog["catalog_sha256"],
            "status": "BLOCKED_MISSING_CALIBRATION",
            "failure_codes": ["S0_BLOCK_SIZE_POLICY_MISSING"],
            "diagnostic_labels": ["MISSING_REQUIRES_CALIBRATION"],
            "block_size_policy": "MISSING_REQUIRES_CALIBRATION",
            "load_ledger": {
                "source_char_count": len(catalog["source_text"]),
                "approved_target_tokens": "MISSING_REQUIRES_CALIBRATION",
                "approved_catalog_entry_limit": "MISSING_REQUIRES_CALIBRATION",
                "approved_context_overlap": "MISSING_REQUIRES_CALIBRATION",
            },
            "diagnostic_risks": [dict(row) for row in diagnostic_risks],
            "chunks": [],
            "plan_sha256": "",
            "candidate_status": "candidate_silver_not_active",
        }
        plan["plan_sha256"] = _sha_without_field(plan, "plan_sha256")
        return plan

    source_length = len(catalog["source_text"])
    sentences = catalog["sentences"]
    chunks = []
    for index, (start, end) in enumerate(primary_ranges, start=1):
        if end <= start:
            raise C15ContractError(
                "BOUNDARY_SOURCE_RANGEREVERSED",
                f"chunk {index} primary 区间逆序或为空。",
            )
        primary_ids = [
            row["sentence_id"]
            for row in sentences
            if start <= row["char_start"] < end
        ]
        context_start = max(0, start - context_chars)
        context_end = min(source_length, end + context_chars)
        visible_ids = [
            row["sentence_id"]
            for row in sentences
            if row["char_end_exclusive"] > context_start
            and row["char_start"] < context_end
        ]
        chunks.append(
            {
                "chunk_id": f"{catalog['source_id']}-C{index:02d}",
                "primary_range": {
                    "char_start": start,
                    "char_end_exclusive": end,
                },
                "context_only_ranges": [
                    {
                        "char_start": context_start,
                        "char_end_exclusive": start,
                    },
                    {
                        "char_start": end,
                        "char_end_exclusive": context_end,
                    },
                ],
                "primary_owned_source_ids": primary_ids,
                "visible_source_ids": visible_ids,
                "load_ledger": {
                    "primary_char_count": end - start,
                    "visible_source_id_count": len(visible_ids),
                    "primary_source_id_count": len(primary_ids),
                },
            }
        )
    plan = {
        "schema_version": "v02-c15-chunk-plan.v1",
        "run_id": catalog["run_id"],
        "source_id": catalog["source_id"],
        "source_catalog_sha256": catalog["catalog_sha256"],
        "status": "READY_OFFLINE_ONLY",
        "failure_codes": [],
        "diagnostic_labels": [],
        "block_size_policy": "EXPLICIT_PREAPPROVED_RANGES",
        "load_ledger": {
            "source_char_count": source_length,
            "approved_target_tokens": "EXPLICIT_PREAPPROVED_RANGES",
            "approved_catalog_entry_limit": "EXPLICIT_PREAPPROVED_RANGES",
            "approved_context_overlap": context_chars,
        },
        "diagnostic_risks": [dict(row) for row in diagnostic_risks],
        "chunks": chunks,
        "plan_sha256": "",
        "candidate_status": "candidate_silver_not_active",
    }
    plan["plan_sha256"] = _sha_without_field(plan, "plan_sha256")
    validate_chunk_plan(plan, catalog=catalog)
    return plan


def validate_chunk_plan(
    plan: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    if plan.get("source_catalog_sha256") != catalog.get("catalog_sha256"):
        raise C15ContractError(
            "PROVENANCE_SOURCE_HASH_MISMATCH",
            "chunk_plan 没有绑定当前 S0 目录。",
        )
    if plan.get("plan_sha256") != _sha_without_field(plan, "plan_sha256"):
        raise C15ContractError(
            "PROVENANCE_SOURCE_HASH_MISMATCH",
            "chunk_plan SHA 漂移。",
        )
    if plan.get("status") == "BLOCKED_MISSING_CALIBRATION":
        if plan.get("failure_codes") != ["S0_BLOCK_SIZE_POLICY_MISSING"]:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "缺校准状态必须带唯一冻结失败码。",
            )
        if plan.get("diagnostic_labels") != [
            "MISSING_REQUIRES_CALIBRATION"
        ]:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "缺校准状态必须带对应诊断标签。",
            )
        if plan.get("chunks") != []:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "缺校准时不得猜块边界。",
            )
        return {"status": "BLOCKED_MISSING_CALIBRATION", "chunk_count": 0}

    chunks = plan.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise C15ContractError(
            "PROVENANCE_SOURCE_EMPTY",
            "READY chunk_plan 没有块。",
        )
    ranges = [
        (
            row["primary_range"]["char_start"],
            row["primary_range"]["char_end_exclusive"],
        )
        for row in chunks
    ]
    if ranges[0][0] != 0 or ranges[-1][1] != len(catalog["source_text"]):
        raise C15ContractError(
            "BOUNDARY_SOURCE_RANGEREVERSED",
            "primary 区间未覆盖全文首尾。",
        )
    for previous, current in zip(ranges, ranges[1:]):
        if previous[1] != current[0]:
            raise C15ContractError(
                "BOUNDARY_SOURCE_RANGEREVERSED",
                "primary 区间有缺口或重叠。",
            )
    catalog_ids = {row["sentence_id"] for row in catalog["sentences"]}
    primary_ids = [
        source_id
        for chunk in chunks
        for source_id in chunk["primary_owned_source_ids"]
    ]
    visible_ids = [
        source_id
        for chunk in chunks
        for source_id in chunk["visible_source_ids"]
    ]
    if set(primary_ids) != catalog_ids or len(primary_ids) != len(set(primary_ids)):
        raise C15ContractError(
            "BOUNDARY_SOURCE_RANGEREVERSED",
            "sentence primary 归属未做到 100% 且不重复。",
        )
    if not set(visible_ids).issubset(catalog_ids):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "chunk_plan 引用了 S0 目录外 source ID。",
        )
    return {
        "status": "PASS",
        "chunk_count": len(chunks),
        "primary_coverage": 1.0,
        "duplicate_primary_owner_count": 0,
        "outside_source_id_count": 0,
    }


def _provider_content(raw_response: Mapping[str, Any]) -> Mapping[str, Any]:
    choices = raw_response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "历史响应 choices 不是唯一项。",
        )
    message = choices[0].get("message")
    if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "历史响应缺模型 JSON 文本。",
        )
    parsed = json.loads(message["content"])
    if not isinstance(parsed, Mapping):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "模型 JSON 根节点不是对象。",
        )
    return parsed


def _legacy_catalog_map(catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = catalog.get("entries")
    if not isinstance(rows, list):
        raise C15ContractError(
            "PROVENANCE_SOURCE_EMPTY",
            "旧目录 entries 缺失。",
        )
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "旧目录条目不是对象。",
            )
        anchor_id = row.get("anchor_id")
        if not isinstance(anchor_id, str) or anchor_id in result:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "旧目录 anchor_id 缺失或重复。",
            )
        result[anchor_id] = row
    return result


def backfill_source_quotes(
    model_output: Mapping[str, Any],
    *,
    legacy_catalog: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog_map = _legacy_catalog_map(legacy_catalog)
    events = model_output.get("events")
    if not isinstance(events, list):
        raise C15ContractError(
            "PROVENANCE_SOURCE_EMPTY",
            "模型输出 events 缺失。",
        )
    transformed_events: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for event_index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "模型事件不是对象。",
            )
        if "source_quotes" in event:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "模型不得写 source_quotes。",
            )
        event_text = event.get("event")
        event_id = event.get("event_id")
        obligations = event.get("support_obligations")
        source_ids = event.get("minimal_anchor_ids")
        if (
            not isinstance(event_text, str)
            or not isinstance(event_id, str)
            or not isinstance(obligations, list)
            or not isinstance(source_ids, list)
        ):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                f"{event_id or event_index} 旧事件字段不完整。",
            )
        if any(
            isinstance(obligation, Mapping) and "source_quotes" in obligation
            for obligation in obligations
        ):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "模型不得在支撑义务里写 source_quotes。",
            )
        for obligation_index, obligation in enumerate(obligations):
            if not isinstance(obligation, Mapping):
                raise C15ContractError(
                    "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                    f"{event_id} 支撑义务不是对象。",
                )
            claim_span = obligation.get("claim_span")
            if not isinstance(claim_span, str) or claim_span not in event_text:
                violations.append(
                    {
                        "event_id": event_id,
                        "obligation_index": obligation_index,
                        "legacy_claim_span": claim_span,
                        "source_ids": list(obligation.get("anchor_ids") or []),
                    }
                )
        obligation_source_ids = [
            str(source_id)
            for obligation in obligations
            if isinstance(obligation, Mapping)
            for source_id in (obligation.get("anchor_ids") or [])
        ]
        unique_source_ids = list(
            dict.fromkeys(
                [*(str(value) for value in source_ids), *obligation_source_ids]
            )
        )
        if any(source_id not in catalog_map for source_id in unique_source_ids):
            raise C15ContractError(
                "PROVENANCE_SOURCE_HASH_MISMATCH",
                f"{event_id} 引用了旧目录外 source ID。",
            )
        source_quotes = [
            {
                "source_id": source_id,
                "original_text": str(catalog_map[source_id]["quote"]),
                "char_start": int(catalog_map[source_id]["body_start_char"]),
                "char_end_exclusive": int(
                    catalog_map[source_id]["body_end_char_exclusive"]
                ),
                "quote_sha256": sha256_bytes(
                    str(catalog_map[source_id]["quote"]).encode("utf-8")
                ),
                "producer": "PROGRAM_BACKFILL_FROM_FROZEN_CATALOG",
            }
            for source_id in unique_source_ids
        ]
        transformed_events.append(
            {
                "event_id": event_id,
                "event": event_text,
                "source_ids": unique_source_ids,
                "source_quotes": source_quotes,
                "semantic_support_status": "ANCHOR_SUPPORT_SEMANTIC_OPEN",
            }
        )
    return (
        {
            "schema_version": "v02-c15-program-source-backfill.v1",
            "chapter": model_output.get("chapter"),
            "events": transformed_events,
            "model_source_quote_write_allowed": False,
            "string_generation_mismatch_count_after_backfill": 0,
            "semantic_support_verified": False,
            "semantic_support_status": "ANCHOR_SUPPORT_SEMANTIC_OPEN",
            "candidate_status": "candidate_silver_not_active",
        },
        violations,
    )


def replay_c2_c5() -> dict[str, Any]:
    cases = (
        ("C2_B02_U0039", C2_RAW_RESPONSE, C2_CATALOG, C2_REQUEST, 5),
        ("C5_B01_U0033", C5_RAW_RESPONSE, C5_CATALOG, C5_REQUEST, 10),
    )
    rows: list[dict[str, Any]] = []
    case_receipts = []
    for case_id, response_path, catalog_path, request_path, expected_count in cases:
        raw = read_json(response_path)
        catalog = read_json(catalog_path)
        request = read_json(request_path)
        observed_catalog_sha = anchor_first.canonical_sha(catalog)
        if request.get("catalog_sha256") != observed_catalog_sha:
            raise C15ContractError(
                "PROVENANCE_SOURCE_HASH_MISMATCH",
                f"{case_id} 历史请求与目录规范化 SHA 不一致。",
            )
        if request.get("source_body_sha256") != catalog.get("source_body_sha256"):
            raise C15ContractError(
                "PROVENANCE_SOURCE_HASH_MISMATCH",
                f"{case_id} 历史请求与目录正文 SHA 不一致。",
            )
        model_output = _provider_content(raw)
        transformed, violations = backfill_source_quotes(
            model_output,
            legacy_catalog=catalog,
        )
        if len(violations) != expected_count:
            raise C15ContractError(
                "PROVENANCE_SOURCE_HASH_MISMATCH",
                f"{case_id} 违约数漂移：{len(violations)} != {expected_count}",
            )
        event_map = {row["event_id"]: row for row in transformed["events"]}
        for violation_index, violation in enumerate(violations, start=1):
            source_ids = violation["source_ids"]
            transformed_event = event_map[violation["event_id"]]
            quote_map = {
                quote["source_id"]: quote["quote_sha256"]
                for quote in transformed_event["source_quotes"]
            }
            rows.append(
                {
                    "replay_id": f"{case_id}-R{violation_index:02d}",
                    "case_id": case_id,
                    "event_id": violation["event_id"],
                    "obligation_index": violation["obligation_index"],
                    "legacy_claim_span_sha256": (
                        sha256_bytes(violation["legacy_claim_span"].encode("utf-8"))
                        if isinstance(violation["legacy_claim_span"], str)
                        else None
                    ),
                    "source_ids": source_ids,
                    "program_backfill_quote_sha256_by_source_id": {
                        source_id: quote_map[source_id] for source_id in source_ids
                    },
                    "string_mismatch_before": True,
                    "string_mismatch_after_program_backfill": False,
                    "semantic_support_status": "ANCHOR_SUPPORT_SEMANTIC_OPEN",
                }
            )
        case_receipts.append(
            {
                "case_id": case_id,
                "raw_response_sha256": sha256_file(response_path),
                "catalog_file_sha256": sha256_file(catalog_path),
                "catalog_canonical_sha256": observed_catalog_sha,
                "legacy_violation_count": len(violations),
                "program_backfill_string_mismatch_count": 0,
                "semantic_support_verified": False,
            }
        )
    return {
        "schema_version": "v02-c15-s3-replay-receipt.v1",
        "status": "PASS_STRING_LAYER_ONLY",
        "model_api_calls": 0,
        "network_requests": 0,
        "same_model_outputs_reused_read_only": True,
        "legacy_violation_count": len(rows),
        "program_backfill_string_mismatch_count": 0,
        "semantic_support_status": "ANCHOR_SUPPORT_SEMANTIC_OPEN",
        "case_receipts": case_receipts,
        "replay_rows": rows,
        "candidate_status": "candidate_silver_not_active",
    }


def issue_and_patch_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-c15-issue-and-patch-contract.v1",
        "issue_types": {
            "c13_missing_buckets": list(C13_MISSING_BUCKETS),
            "b2_six_routes": list(gate_contracts.ROUTE_IDS),
            "z89_semantic_issues": list(Z89_ISSUE_TYPES),
        },
        "patch_operations_by_arm": {
            key: list(value) for key, value in PATCH_OPERATIONS.items()
        },
        "patch_scope_rule": (
            "每条 issue 必须显式冻结 allowed_operations 与 allowed_fields；"
            "补丁不得越出该条 issue 的授权面。"
        ),
        "mechanical_diff_guard": {
            "required_issue_fields": [
                "object_id",
                "before_object_sha256",
                "allowed_diff_paths",
            ],
            "required_patch_fields": [
                "object_id",
                "before_object",
                "after_object",
            ],
            "rule": (
                "程序必须核对前态 SHA，并计算 before_object→after_object 的真实"
                " JSON Pointer 差异；差异路径不得越出 allowed_diff_paths；"
                "add_fact 只能保留旧事实并新增冻结 ID，split_fact 只能把指定"
                "源事实替换为预登记子事实 ID，其他事实不得改动。"
            ),
        },
        "unauthorized_failure_code": "S3_ENUM_INVALID",
        "unauthorized_diagnostic_label": (
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE"
        ),
        "exact_duplicate_policy": {
            "hint_allowed": True,
            "automatic_merge_allowed": False,
            "semantic_merge_allowed": False,
            "authority": "D/B4.1",
        },
        "full_chunk_rewrite_allowed": False,
        "candidate_status": "candidate_silver_not_active",
    }


def _json_diff_paths(before: Any, after: Any, *, path: str = "") -> set[str]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        result: set[str] = set()
        keys = set(before) | set(after)
        for key in keys:
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            child_path = f"{path}/{escaped}"
            if key not in before or key not in after:
                result.add(child_path)
                continue
            result.update(
                _json_diff_paths(before[key], after[key], path=child_path)
            )
        return result
    if isinstance(before, list) and isinstance(after, list):
        return {path or "/"} if before != after else set()
    return {path or "/"} if before != after else set()


def _fact_rows_by_id(value: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = value.get("facts")
    if not isinstance(rows, list):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "事实操作对象缺 facts 数组。",
        )
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "facts 含非对象条目。",
            )
        fact_id = row.get("fact_id")
        if not isinstance(fact_id, str) or fact_id in result:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "facts 的 fact_id 缺失或重复。",
            )
        result[fact_id] = row
    return result


def _validate_fact_sequence_change(
    *,
    operation: str,
    issue: Mapping[str, Any],
    before_object: Mapping[str, Any],
    after_object: Mapping[str, Any],
) -> None:
    before_facts = _fact_rows_by_id(before_object)
    after_facts = _fact_rows_by_id(after_object)
    fact_scope_id = issue["fact_scope_id"]
    if operation == "add_fact":
        if fact_scope_id in before_facts or fact_scope_id not in after_facts:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "add_fact 没有新增问题单冻结的唯一事实 ID。",
            )
        if set(after_facts) - set(before_facts) != {fact_scope_id}:
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "add_fact 新增了问题单范围外的事实。",
            )
        if set(before_facts) - set(after_facts):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "add_fact 删除了已有事实。",
            )
        if any(after_facts[fact_id] != row for fact_id, row in before_facts.items()):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "add_fact 夹带改写了已有事实。",
            )
        return

    split_result_fact_ids = issue.get("split_result_fact_ids")
    if (
        fact_scope_id not in before_facts
        or not isinstance(split_result_fact_ids, list)
        or not split_result_fact_ids
        or len(split_result_fact_ids) != len(set(split_result_fact_ids))
        or not all(isinstance(value, str) for value in split_result_fact_ids)
    ):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "split_fact 缺冻结源事实或冻结子事实 ID 清单。",
        )
    expected_new_ids = set(split_result_fact_ids)
    if fact_scope_id in after_facts:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "split_fact 没有移除指定源事实。",
        )
    if set(after_facts) - set(before_facts) != expected_new_ids:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "split_fact 新增的子事实 ID 与冻结清单不一致。",
        )
    if set(before_facts) - set(after_facts) != {fact_scope_id}:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "split_fact 删除了指定源事实以外的事实。",
        )
    shared_ids = set(before_facts) & set(after_facts)
    if any(before_facts[fact_id] != after_facts[fact_id] for fact_id in shared_ids):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "split_fact 夹带改写了其他已有事实。",
        )
    if any(
        after_facts[fact_id].get("source_fact_id") != fact_scope_id
        for fact_id in expected_new_ids
    ):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "split_fact 子事实没有逐条绑定被冻结的源事实。",
        )


def validate_patch(
    patch: Mapping[str, Any],
    *,
    issue: Mapping[str, Any],
    arm: str,
) -> dict[str, Any]:
    unknown_patch_fields = set(patch) - PATCH_ENVELOPE_FIELDS
    if unknown_patch_fields:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "补丁外壳夹带未登记字段。",
        )
    allowed_for_arm = set(PATCH_OPERATIONS.get(arm, ()))
    operation = patch.get("operation")
    issue_allowed_ops = issue.get("allowed_operations")
    issue_allowed_fields = issue.get("allowed_fields")
    if not isinstance(issue_allowed_ops, list) or not isinstance(
        issue_allowed_fields, list
    ):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "问题单没有冻结许可动作或许可字段。",
        )
    if operation not in allowed_for_arm or operation not in issue_allowed_ops:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "补丁操作不在臂合同与问题单双重白名单中。",
        )
    if patch.get("issue_id") != issue.get("issue_id"):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "补丁没有绑定当前冻结问题单。",
        )
    object_id = issue.get("object_id")
    before_object_sha256 = issue.get("before_object_sha256")
    allowed_diff_paths = issue.get("allowed_diff_paths")
    before_object = patch.get("before_object")
    after_object = patch.get("after_object")
    if (
        not isinstance(object_id, str)
        or patch.get("object_id") != object_id
        or not isinstance(before_object_sha256, str)
        or not isinstance(allowed_diff_paths, list)
        or not isinstance(before_object, Mapping)
        or not isinstance(after_object, Mapping)
    ):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "问题单或补丁缺冻结对象、前态 SHA、前后对象或许可差异路径。",
        )
    if canonical_sha(before_object) != before_object_sha256:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "补丁前态与问题单冻结 SHA 不一致。",
        )
    actual_diff_paths = _json_diff_paths(before_object, after_object)
    if not actual_diff_paths:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "补丁没有真实差异。",
        )
    if not actual_diff_paths.issubset(set(allowed_diff_paths)):
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "实际前后差异越出问题单许可路径。",
        )
    target_field = patch.get("target_field")
    operations_without_field = {"add_fact", "split_fact"}
    if operation in operations_without_field:
        fact_scope_id = issue.get("fact_scope_id")
        if (
            not isinstance(fact_scope_id, str)
            or patch.get("fact_scope_id") != fact_scope_id
        ):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "新增或拆分事实没有绑定问题单冻结的事实范围。",
            )
        _validate_fact_sequence_change(
            operation=operation,
            issue=issue,
            before_object=before_object,
            after_object=after_object,
        )
    if operation not in operations_without_field:
        changed_fields = {
            path.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
            for path in actual_diff_paths
        }
        if (
            target_field not in issue_allowed_fields
            or target_field not in changed_fields
            or not changed_fields.issubset(set(issue_allowed_fields))
        ):
            raise C15ContractError(
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
                "补丁真实差异没有落在声明且获准的字段内。",
            )
    if patch.get("full_chunk_rewrite") is True:
        raise C15ContractError(
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE",
            "禁止整块重写。",
        )
    return {
        "status": "PASS",
        "issue_id": issue["issue_id"],
        "operation": operation,
        "target_field": target_field,
        "actual_diff_paths": sorted(actual_diff_paths),
        "semantic_truth_verified": False,
    }


def exact_duplicate_hints(facts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_claim: dict[str, list[str]] = {}
    for fact in facts:
        claim = fact.get("claim")
        fact_id = fact.get("fact_id")
        if isinstance(claim, str) and isinstance(fact_id, str):
            by_claim.setdefault(claim, []).append(fact_id)
    return [
        {
            "exact_claim_sha256": sha256_bytes(claim.encode("utf-8")),
            "fact_ids": sorted(fact_ids),
            "action": "HINT_ONLY_NO_AUTO_MERGE",
        }
        for claim, fact_ids in sorted(by_claim.items())
        if len(fact_ids) > 1
    ]


def q3_preregistration() -> dict[str, Any]:
    case_rows = []
    for case_id in ("B01-U0033", "B02-U0039", "B03-U0041"):
        case_rows.append(
            {
                "case_id": case_id,
                "chunk_slots": [
                    {
                        "chunk_slot": f"{case_id}-CHUNK-01",
                        "chunk_plan_sha256": "MISSING_REQUIRES_CALIBRATION",
                    },
                    {
                        "chunk_slot": f"{case_id}-CHUNK-02",
                        "chunk_plan_sha256": "MISSING_REQUIRES_CALIBRATION",
                    },
                ],
            }
        )
    value: dict[str, Any] = {
        "schema_version": "v02-c15-q3-repair-ab-preregistration.v1",
        "status": "FROZEN_NOT_SENT_BLOCKED_BY_CHUNK_CALIBRATION",
        "execution_priority": "AFTER_R1_SCOPE_EXPERIMENT",
        "superseding_correction": "C15_CORRECTION_20260726_1940",
        "question": (
            "同一 Flash 块内初稿与同一冻结问题单下，比较一次 Flash 自修"
            "与一次 V4 Pro 定点补丁的净语义修复。"
        ),
        "case_slots": case_rows,
        "call_budget": {
            "base_flash": 6,
            "arm_a_flash_self_repair": 6,
            "arm_b_v4_pro_patch": 6,
            "total": 18,
            "retry": 0,
        },
        "models": {
            "base_and_arm_a": {
                "provider": "sensenova",
                "model": "deepseek-v4-flash",
                "max_tokens": 65536,
            },
            "arm_b": {
                "provider": "tencent_tokenhub",
                "model": "deepseek-v4-pro-202606",
                "max_tokens": 32000,
                "exact_model_online_ticket_required": True,
                "fallback_allowed": False,
            },
        },
        "issue_list_freeze_sequence": [
            "六份 Flash 块内初稿全部落盘",
            "六份初稿机械闸全部通过",
            "评测隔离区读取 49 条金标摘录",
            "生成问题单但不向修补模型提供金标答案或短引",
            "问题单冻结 SHA",
            "A/B 两臂接收逐字相同的问题单与原始材料",
        ],
        "primary_criteria": {
            "net_strict_repair_formula": (
                "new_strict_hits - broken_prior_strict_hits"
            ),
            "unsupported_anchor_count_b_lte_a": True,
            "repair_regression_b_lte_a": True,
            "chapters_b_not_below_a_minimum": "2_OF_3",
            "missing_semantic_metrics_result": "MATERIALS_INSUFFICIENT",
            "self_score_allowed": False,
        },
        "network_authorization": {
            "separate_authorization_required": True,
            "sequence": [
                "API_KEY_EXISTENCE_ONLY",
                "EXACT_MODEL_IDENTITY_TICKET",
                "ALL_FROZEN_SHA_RECHECK",
            ],
            "execute_allowed": False,
        },
        "block_size_policy": "MISSING_REQUIRES_CALIBRATION",
        "model_api_calls": 0,
        "network_requests": 0,
        "candidate_status": "candidate_silver_not_active",
        "preregistration_sha256": "",
    }
    value["preregistration_sha256"] = _sha_without_field(
        value,
        "preregistration_sha256",
    )
    return value


def _strict_schema(
    *,
    schema_id: str,
    required: Sequence[str],
    properties: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": dict(properties),
    }


def build_contract_artifacts() -> dict[str, bytes]:
    binding = failure_code_binding()
    validate_failure_code_binding(binding)
    issue_contract = issue_and_patch_contract()
    prereg = q3_preregistration()
    source_schema = _strict_schema(
        schema_id="v02-c15-source-catalog.v1",
        required=(
            "schema_version",
            "run_id",
            "source_id",
            "chapter",
            "coordinate_unit",
            "source_text",
            "source_body_sha256",
            "paragraphs",
            "sentences",
            "catalog_sha256",
            "candidate_status",
        ),
        properties={
            "schema_version": {"const": "v02-c15-source-catalog.v1"},
            "run_id": {"type": "string", "minLength": 1},
            "source_id": {"type": "string", "minLength": 1},
            "chapter": {"type": "integer", "minimum": 1},
            "coordinate_unit": {
                "const": "PYTHON_UNICODE_CODEPOINT_INDEX"
            },
            "source_text": {"type": "string", "minLength": 1},
            "source_body_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "paragraphs": {"type": "array", "minItems": 1},
            "sentences": {"type": "array", "minItems": 1},
            "catalog_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "candidate_status": {
                "const": "candidate_silver_not_active"
            },
        },
    )
    chunk_schema = _strict_schema(
        schema_id="v02-c15-chunk-plan.v1",
        required=(
            "schema_version",
            "run_id",
            "source_id",
            "source_catalog_sha256",
            "status",
            "failure_codes",
            "diagnostic_labels",
            "block_size_policy",
            "load_ledger",
            "diagnostic_risks",
            "chunks",
            "plan_sha256",
            "candidate_status",
        ),
        properties={
            "schema_version": {"const": "v02-c15-chunk-plan.v1"},
            "run_id": {"type": "string"},
            "source_id": {"type": "string"},
            "source_catalog_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "status": {
                "enum": [
                    "BLOCKED_MISSING_CALIBRATION",
                    "READY_OFFLINE_ONLY",
                ]
            },
            "failure_codes": {"type": "array"},
            "diagnostic_labels": {"type": "array"},
            "block_size_policy": {"type": "string"},
            "load_ledger": {"type": "object"},
            "diagnostic_risks": {"type": "array"},
            "chunks": {"type": "array"},
            "plan_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "candidate_status": {
                "const": "candidate_silver_not_active"
            },
        },
    )
    artifacts = {
        "failure_code_binding.json": json_bytes(binding),
        "issue_and_patch_contract.json": json_bytes(issue_contract),
        "q3_repair_ab_preregistration.json": json_bytes(prereg),
        "schemas/source_catalog.schema.json": json_bytes(source_schema),
        "schemas/chunk_plan.schema.json": json_bytes(chunk_schema),
    }
    manifest = {
        "schema_version": "v02-c15-contract-manifest.v1",
        "candidate_id": "V02_C15_pipeline_v1_20260726",
        "candidate_status": "candidate_silver_not_active",
        "model_api_calls": 0,
        "network_requests": 0,
        "active_pipeline_changed": False,
        "artifacts": {
            path: sha256_bytes(raw) for path, raw in sorted(artifacts.items())
        },
    }
    manifest["artifact_tree_sha256"] = canonical_sha(manifest["artifacts"])
    artifacts["manifest.json"] = json_bytes(manifest)
    return artifacts


def write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    for relative, raw in artifacts.items():
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def _tree_sha(path: Path) -> str:
    rows = []
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        rows.append(
            {
                "path": file_path.relative_to(path).as_posix(),
                "sha256": sha256_file(file_path),
            }
        )
    return canonical_sha(rows)


def _sealed_receipt() -> dict[str, str]:
    receipt = {
        path.relative_to(REPO_ROOT).as_posix(): sha256_file(path)
        for path in SEALED_FILES
    }
    receipt.update(
        {
            f"{path.relative_to(REPO_ROOT).as_posix()}/": _tree_sha(path)
            for path in SEALED_DIRECTORIES
            if path.is_dir()
        }
    )
    return dict(sorted(receipt.items()))


def _replay_markdown(receipt: Mapping[str, Any]) -> str:
    lines = [
        "# C15 S3｜C2＋C5-B01 逐字证据程序回填回放",
        "",
        "| 序 | 来源 | 事件 | 义务序号 | source ID | 回填后字符串错位 | 语义承托 |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for index, row in enumerate(receipt["replay_rows"], start=1):
        lines.append(
            "| "
            + " | ".join(
                (
                    str(index),
                    str(row["case_id"]),
                    str(row["event_id"]),
                    str(row["obligation_index"]),
                    "、".join(row["source_ids"]),
                    "0",
                    "ANCHOR_SUPPORT_SEMANTIC_OPEN",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "这 15 行只证明模型不再负责誊抄逐字证据后，字符串错位可由程序消除；不证明所选证据在语义上托住主张。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def _stop_report(
    *,
    runtime_manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    source_receipts: Sequence[Mapping[str, Any]],
    chunk_receipts: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# C15｜管线化 v1 第一阶段停点回包",
        "",
        "✅ 0 模型 API／0 网络；写入面只包含 C15 新候选目录。",
        "",
        "## S0 来源冻结器",
        "",
        f"- 真实正文冻结：{len(source_receipts)} 章。",
        "- 每章都有段落 ID、句子 ID、字符偏移、逐字正文、正文 SHA、目录 SHA、运行 ID。",
        "- 正文只落本机 runs 候选区，不进入 Git 候选合同目录。",
        "",
        "## S3 程序逐字证据回填",
        "",
        f"- C2＋C5-B01 历史错位：{replay['legacy_violation_count']} 行。",
        "- 同一历史模型输出只读回放；程序按 source ID 回填后字符串错位：0。",
        "- 语义承托仍统一标记 ANCHOR_SUPPORT_SEMANTIC_OPEN，未冒充语义绿票。",
        "",
        "## S1 程序分块计划",
        "",
        f"- 三章计划票：{len(chunk_receipts)}。",
        "- 块大小、目录条目上限、上下文重叠均未校准；真实分块保持 MISSING_REQUIRES_CALIBRATION，未猜阈值。",
        (
            "- B01 23,636 token／419 条目录只登记风险，不转成阈值；"
            "来源票为 `reports/抽取工序重设计v0.2_连夜施工_20260725/"
            "C5_稳定性复测硬停审计.json`，其 SHA 已写入 B01 分块计划。"
        ),
        "",
        "## S4 问题单与修补白名单",
        "",
        "- A 臂只准固定元数据、字段替换、source ID 替换。",
        "- B 臂在 A 基础上可加事实、拆事实、换限定。",
        (
            "- 每条问题单再收窄许可字段；越权诊断标签为 "
            "REPAIR_UNAUTHORIZED_FIELD_CHANGE，正式失败码复用冻结谱系里的 "
            "S3_ENUM_INVALID；失败码谱系新增 0。"
        ),
        "- 精确重复只给提示，不自动语义合并。",
        "",
        "## Q3 修补 A/B 预注册",
        "",
        "- B01／B02／B03 各 2 个块槽位；基础 Flash 6＋A Flash 6＋B Pro 6＝18 次，0 重试。",
        "- B 臂固定腾讯 deepseek-v4-pro-202606；发网前必须验精确型号，失败不替换。",
        "- 因真实块边界尚未校准，状态为 FROZEN_NOT_SENT_BLOCKED_BY_CHUNK_CALIBRATION；本轮未发网。",
        "- 依 19:40 修正令，Q3 排在 R1 范围实验之后；当前只保留冻结预注册件。",
        "",
        "## SHA 与边界",
        "",
        f"- 运行工件树 SHA：`{runtime_manifest['artifact_tree_sha256']}`",
        f"- 封存输入前后相同：{runtime_manifest['sealed_inputs_unchanged']}",
        f"- 封存文件／目录指纹项：{runtime_manifest['sealed_input_fingerprint_count']}。",
        "- 指纹覆盖 C13 r07、C2–C6、Z89、Z91 与本轮直接读取证据。",
        "- C7 与现役链未纳入本票全树指纹；本回包只声明 C15 写入路径隔离，不用 Git 脏状态替代证据。",
        f"- 候选合同目录树 SHA：`{runtime_manifest['contract_tree_sha256']}`",
        "- 产物全部是候选银标；没有固化、没有升默认、没有写 outbox、没有提交或推送。",
        "",
        "来源：Codex",
        "",
    ]
    return "\n".join(lines)


def run_offline(
    *,
    contract_dir: Path,
    run_dir: Path,
    report_dir: Path,
) -> dict[str, Any]:
    before = _sealed_receipt()
    contract_artifacts = build_contract_artifacts()
    write_artifacts(contract_dir, contract_artifacts)
    contract_tree_sha = _tree_sha(contract_dir)

    source_receipts = []
    chunk_receipts = []
    runtime_files: list[Path] = []
    c5_stability_audit = read_json(C5_STABILITY_AUDIT)
    for case in anchor_first.CASES:
        source = anchor_first.load_case_source(case)
        catalog = build_source_catalog(
            run_id=RUN_ID,
            source_id=case.case_id,
            chapter=case.unit,
            source_text=source["body"],
        )
        ticket = build_source_run_ticket(catalog)
        source_receipt = validate_source_catalog(catalog, run_ticket=ticket)
        source_receipt["case_id"] = case.case_id
        source_receipt["cache_file_sha256"] = source["cache_sha256"]
        source_receipts.append(source_receipt)
        catalog_path = run_dir / "s0" / "source_catalogs" / f"{case.case_id}.json"
        ticket_path = run_dir / "s0" / "run_tickets" / f"{case.case_id}.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        ticket_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_bytes(json_bytes(catalog))
        ticket_path.write_bytes(json_bytes(ticket))
        runtime_files.extend((catalog_path, ticket_path))

        diagnostic_risks = []
        if case.case_id == "B01-U0033":
            diagnostic_risks.append(
                {
                    "risk_id": "B01_CATALOG_LOAD_CLIFF_UNCALIBRATED",
                    "prompt_tokens": c5_stability_audit["usage"]["B01-U0033"][
                        "prompt_tokens"
                    ],
                    "catalog_entry_count": len(read_json(C5_CATALOG)["entries"]),
                    "evidence_path": C5_STABILITY_AUDIT.relative_to(
                        REPO_ROOT
                    ).as_posix(),
                    "evidence_file_sha256": sha256_file(C5_STABILITY_AUDIT),
                    "policy": "RISK_ONLY_NOT_THRESHOLD",
                }
            )
        chunk_plan = build_chunk_plan(
            catalog,
            primary_ranges=None,
            diagnostic_risks=diagnostic_risks,
        )
        chunk_receipt = validate_chunk_plan(chunk_plan, catalog=catalog)
        chunk_receipt["case_id"] = case.case_id
        chunk_receipt["diagnostic_risks"] = chunk_plan["diagnostic_risks"]
        chunk_receipts.append(chunk_receipt)
        chunk_path = run_dir / "s1" / "chunk_plans" / f"{case.case_id}.json"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_bytes(json_bytes(chunk_plan))
        runtime_files.append(chunk_path)

    replay = replay_c2_c5()
    replay_path = run_dir / "s3" / "replay_receipt.json"
    replay_path.parent.mkdir(parents=True, exist_ok=True)
    replay_path.write_bytes(json_bytes(replay))
    runtime_files.append(replay_path)

    replay_report_path = report_dir / "C15_S3_15行回放表.md"
    replay_report_path.parent.mkdir(parents=True, exist_ok=True)
    replay_report_path.write_text(_replay_markdown(replay), encoding="utf-8")

    after = _sealed_receipt()
    sealed_unchanged = before == after
    if not sealed_unchanged:
        raise C15ContractError(
            "PROVENANCE_SOURCE_HASH_MISMATCH",
            "封存输入在离线运行前后发生变化。",
        )
    sealed_receipt = {
        "schema_version": "v02-c15-sealed-input-receipt.v1",
        "before_sha256_by_path": before,
        "after_sha256_by_path": after,
        "unchanged": sealed_unchanged,
        "model_api_calls": 0,
        "network_requests": 0,
    }
    sealed_path = run_dir / "sealed_input_receipt.json"
    sealed_path.write_bytes(json_bytes(sealed_receipt))
    runtime_files.append(sealed_path)

    artifacts = {
        path.relative_to(run_dir).as_posix(): sha256_file(path)
        for path in sorted(runtime_files)
    }
    runtime_manifest: dict[str, Any] = {
        "schema_version": "v02-c15-runtime-manifest.v1",
        "run_id": RUN_ID,
        "candidate_status": "candidate_silver_not_active",
        "model_api_calls": 0,
        "network_requests": 0,
        "sealed_inputs_unchanged": sealed_unchanged,
        "sealed_input_fingerprint_count": len(before),
        "contract_tree_sha256": contract_tree_sha,
        "artifacts": artifacts,
        "artifact_tree_sha256": canonical_sha(artifacts),
        "source_receipts": source_receipts,
        "chunk_receipts": chunk_receipts,
        "s3_replay_summary": {
            "legacy_violation_count": replay["legacy_violation_count"],
            "program_backfill_string_mismatch_count": replay[
                "program_backfill_string_mismatch_count"
            ],
            "semantic_support_status": replay["semantic_support_status"],
        },
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_bytes(json_bytes(runtime_manifest))

    report_path = report_dir / "C15_管线化v1第一阶段停点回包.md"
    report_path.write_text(
        _stop_report(
            runtime_manifest=runtime_manifest,
            replay=replay,
            source_receipts=source_receipts,
            chunk_receipts=chunk_receipts,
        ),
        encoding="utf-8",
    )
    return {
        "status": "PASS_ZERO_API_ZERO_NETWORK",
        "contract_dir": str(contract_dir),
        "run_dir": str(run_dir),
        "report_dir": str(report_dir),
        "runtime_manifest_sha256": sha256_file(manifest_path),
        "runtime_artifact_tree_sha256": runtime_manifest["artifact_tree_sha256"],
        "contract_tree_sha256": contract_tree_sha,
        "replay_row_count": replay["legacy_violation_count"],
        "sealed_inputs_unchanged": sealed_unchanged,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="生成 C15 候选合同")
    build.add_argument("--output-dir", type=Path, default=DEFAULT_CONTRACT_DIR)
    run = subparsers.add_parser("run-offline", help="执行 C15 0 API 离线工件")
    run.add_argument("--contract-dir", type=Path, default=DEFAULT_CONTRACT_DIR)
    run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    run.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "build":
        artifacts = build_contract_artifacts()
        write_artifacts(args.output_dir, artifacts)
        print(
            json.dumps(
                {
                    "status": "PASS_ZERO_API_ZERO_NETWORK",
                    "output_dir": str(args.output_dir),
                    "artifact_count": len(artifacts),
                    "artifact_tree_sha256": _tree_sha(args.output_dir),
                    "model_api_calls": 0,
                    "network_requests": 0,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "run-offline":
        print(
            json.dumps(
                run_offline(
                    contract_dir=args.contract_dir,
                    run_dir=args.run_dir,
                    report_dir=args.report_dir,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
