"""M11 语义检查员：规则先验，DeepSeek 只负责分流，不裁真值。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from pipeline_common.artifacts import (  # noqa: E402
    read_json,
    resolve_repo_path,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from zbatch_modules.api_transport import ApiTransport  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402
from zbatch_modules.stage_sampling import load_contract_bundle  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "governance/contracts/semantic_inspector_v1.json"
DEFAULT_RULE_REGISTRY = ROOT / "governance/rule_check_registry.json"
DEFAULT_PROFILE = "z76_phase2_reviewer"
STAGE = "semantic_route"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

INPUT_CONTRACT = "semantic-inspection-batch-v1"
MODEL_INPUT_CONTRACT = "semantic-router-input-v1"
MODEL_OUTPUT_CONTRACT = "semantic-router-output-v1"
RESULT_CONTRACT = "semantic-inspection-result-v1"
FEEDBACK_CONTRACT = "semantic-inspector-feedback-v1"
QUOTE_FILL_AUDIT_CONTRACT = "semantic-inspector-quote-fill-audit-v1"
QUOTE_PUNCTUATION_EQUIVALENCE_CONTRACT = (
    "semantic-inspector-quote-punctuation-equivalence-v1"
)
QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_CONTRACT = (
    "semantic-inspector-quote-punctuation-unit-equivalence-v1"
)

EVIDENCE_QUOTE_POLICY_EXACT = "exact"
EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING = (
    "anchor_id_authoritative_substring_fill"
)
EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING = (
    "anchor_id_authoritative_punctuation_normalized_substring_fill"
)
EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING = (
    "anchor_id_authoritative_punctuation_unit_substring_fill"
)
EVIDENCE_QUOTE_POLICIES = {
    EVIDENCE_QUOTE_POLICY_EXACT,
    EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING,
    EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING,
    EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING,
}

# 只允许施工令点名的标点等价；不折叠空白、不碰文字、数字或其他符号。
# 多字符项必须在单字符项之前匹配，避免把省略号／破折号拆开处理。
QUOTE_PUNCTUATION_EQUIVALENCE_GROUPS = (
    {"canonical": "...", "variants": ("……",)},
    {"canonical": "--", "variants": ("——",)},
    {"canonical": '"', "variants": ("“", "”", "＂")},
    {"canonical": "'", "variants": ("‘", "’", "＇")},
    {"canonical": ".", "variants": ("。", "．")},
    {"canonical": ",", "variants": ("，",)},
    {"canonical": ":", "variants": ("：",)},
    {"canonical": ";", "variants": ("；",)},
    {"canonical": "?", "variants": ("？",)},
    {"canonical": "!", "variants": ("！",)},
    {"canonical": "(", "variants": ("（",)},
    {"canonical": ")", "variants": ("）",)},
)

# retry08 独立合同：每个等价组映射到唯一的带类型单元，绝不再压成普通字符串。
# canonical 也显式列入 variants；多字符单元按最长优先整体吞入。
QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_GROUPS = (
    {"unit_id": "PUNCT_ELLIPSIS", "variants": ("……", "...")},
    {"unit_id": "PUNCT_DASH_PAIR", "variants": ("——", "--")},
    {
        "unit_id": "PUNCT_DOUBLE_QUOTE",
        "variants": ("“", "”", "＂", '"'),
    },
    {"unit_id": "PUNCT_SINGLE_QUOTE", "variants": ("‘", "’", "＇", "'")},
    {"unit_id": "PUNCT_PERIOD", "variants": ("。", "．", ".")},
    {"unit_id": "PUNCT_COMMA", "variants": ("，", ",")},
    {"unit_id": "PUNCT_COLON", "variants": ("：", ":")},
    {"unit_id": "PUNCT_SEMICOLON", "variants": ("；", ";")},
    {"unit_id": "PUNCT_QUESTION", "variants": ("？", "?")},
    {"unit_id": "PUNCT_EXCLAMATION", "variants": ("！", "!")},
    {"unit_id": "PUNCT_LEFT_PAREN", "variants": ("（", "(")},
    {"unit_id": "PUNCT_RIGHT_PAREN", "variants": ("）", ")")},
)

CHECK_TYPES = {
    "semantic_support",
    "granularity",
    "schema_landing",
    "classification_suggestion",
    "duplicate_candidate",
    "cross_chapter_causality",
}
MODEL_DECISIONS = {"pass_candidate", "review_candidate", "uncertain"}
SUPPORT_VALUES = {"direct_support", "partial_support", "not_support", "uncertain"}
DECLARED_RISKS = {
    "ambiguity",
    "negation",
    "cross_chapter_causality",
    "cross_subject",
    "multi_fact",
}
AUTO_STRONG_REVIEW_RISKS = {"ambiguity", "negation", "cross_chapter_causality"}

AMBIGUITY_RE = re.compile(
    r"可能|也许|或许|似乎|疑似|大概|未必|不确定|是否|为何|为什么|[?？]"
)
NEGATION_RE = re.compile(
    r"并非|不是|没有|尚未|未曾|未能|不能|无法|拒绝|否认|不再|不愿|不会|未"
)

SYSTEM_PROMPT = """你是小说流水线里的低成本语义检查分流员，不是真值裁判。
你只能判断输入陈述与所给原文锚之间的语义支撑关系，并把条目分到候选桶；不得改写输入、补写事实、修改金标、修改分类规则或宣布正式结论。
只有陈述中的全部事实头都被锚直接支撑时，才能给 pass_candidate。部分支撑、证据不托、粒度或类型存在疑问时给 review_candidate；拿不准时给 uncertain。
输出必须是单个 JSON 对象，严格服从用户消息里的输出合同，不要输出代码围栏或额外说明。"""


class InspectorError(RuntimeError):
    """输入、模型输出或分流账违反检查员合同。"""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InspectorError(f"{label} 必须是对象")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise InspectorError(f"{label} 必须是数组")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InspectorError(f"{label} 必须是非空字符串")
    return value.strip()


def _safe_id(value: Any, label: str) -> str:
    result = _text(value, label)
    if not SAFE_ID.fullmatch(result):
        raise InspectorError(f"{label} 只能含字母、数字、点、横线与下划线：{result}")
    return result


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def quote_punctuation_equivalence_contract() -> dict[str, Any]:
    """返回固定映射表；只供比对，绝不改写原响应或正式回填短引。"""

    return {
        "schema_version": QUOTE_PUNCTUATION_EQUIVALENCE_CONTRACT,
        "scope": "comparison_only_no_artifact_mutation",
        "matching_order": "longest_source_first_then_declared_order",
        "whitespace_normalized": False,
        "content_characters_normalized": False,
        "accepted_boundaries": [
            "双引号组不区分左引号、右引号与直引号方向",
            "单引号组不区分左引号、右引号与英文撇号形态",
            "仅整对省略号与三个英文句点等价；单个省略号不归一",
            "仅整对破折号与两个英文连字符等价；单个破折号不归一",
        ],
        "groups": [
            {
                "canonical": group["canonical"],
                "variants": list(group["variants"]),
            }
            for group in QUOTE_PUNCTUATION_EQUIVALENCE_GROUPS
        ],
    }


QUOTE_PUNCTUATION_EQUIVALENCE_SHA256 = sha256_bytes(
    stable_json_bytes(quote_punctuation_equivalence_contract())
)


def normalize_quote_punctuation(value: str) -> tuple[str, list[dict[str, Any]]]:
    """按固定表做确定性归一化，并保留每次替换的原始位置账。"""

    replacements = [
        (variant, str(group["canonical"]), group_index, variant_index)
        for group_index, group in enumerate(QUOTE_PUNCTUATION_EQUIVALENCE_GROUPS)
        for variant_index, variant in enumerate(group["variants"])
    ]
    replacements.sort(key=lambda row: (-len(row[0]), row[2], row[3]))
    parts: list[str] = []
    hits: list[dict[str, Any]] = []
    index = 0
    while index < len(value):
        matched = False
        for source, canonical, group_index, _ in replacements:
            if not value.startswith(source, index):
                continue
            normalized_start = sum(len(part) for part in parts)
            parts.append(canonical)
            hits.append(
                {
                    "source_start": index,
                    "source_end": index + len(source),
                    "normalized_start": normalized_start,
                    "normalized_end": normalized_start + len(canonical),
                    "source": source,
                    "canonical": canonical,
                    "source_codepoints": [f"U+{ord(char):04X}" for char in source],
                    "canonical_codepoints": [
                        f"U+{ord(char):04X}" for char in canonical
                    ],
                    "group_index": group_index,
                }
            )
            index += len(source)
            matched = True
            break
        if matched:
            continue
        parts.append(value[index])
        index += 1
    return "".join(parts), hits


def quote_punctuation_unit_equivalence_contract() -> dict[str, Any]:
    """返回 retry08 无碰撞标点单元合同；只用于比较，不改任何原件。"""

    unit_ids = [str(group["unit_id"]) for group in QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_GROUPS]
    variants = [
        str(variant)
        for group in QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_GROUPS
        for variant in group["variants"]
    ]
    if len(unit_ids) != len(set(unit_ids)):
        raise RuntimeError("标点单元合同存在重复 unit_id")
    if len(variants) != len(set(variants)):
        raise RuntimeError("标点单元合同存在跨组重复 variant")
    return {
        "schema_version": QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_CONTRACT,
        "scope": "comparison_only_no_artifact_mutation",
        "token_shape": ["kind", "value"],
        "matching_order": "longest_variant_first_then_declared_order",
        "comparison": "typed_token_contiguous_subsequence",
        "unit_ids_unique": True,
        "variants_cross_group_unique": True,
        "whitespace_normalized": False,
        "content_characters_normalized": False,
        "unmapped_characters": "RAW_BY_CODEPOINT",
        "accepted_boundaries": [
            "双引号组不区分左引号、右引号与直引号方向",
            "单引号组不区分左引号、右引号与英文撇号形态",
            "仅完整的两个中文省略号与三个英文句点构成一个省略号单元",
            "仅完整的两个中文破折号与两个英文连字符构成一个破折号单元",
            "混拼句点逐字符进入句号单元，绝不折算为省略号单元",
        ],
        "groups": [
            {
                "unit_id": str(group["unit_id"]),
                "variants": [str(value) for value in group["variants"]],
            }
            for group in QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_GROUPS
        ],
    }


QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256 = sha256_bytes(
    stable_json_bytes(quote_punctuation_unit_equivalence_contract())
)


def tokenize_quote_punctuation_units(value: str) -> list[dict[str, Any]]:
    """把字符串切成带类型的文字／标点单元，保留原始字节位置。"""

    variants = [
        (str(variant), str(group["unit_id"]), group_index, variant_index)
        for group_index, group in enumerate(QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_GROUPS)
        for variant_index, variant in enumerate(group["variants"])
    ]
    variants.sort(key=lambda row: (-len(row[0]), row[2], row[3]))
    tokens: list[dict[str, Any]] = []
    index = 0
    while index < len(value):
        matched = next(
            (
                (variant, unit_id)
                for variant, unit_id, _, _ in variants
                if value.startswith(variant, index)
            ),
            None,
        )
        if matched is not None:
            source, unit_id = matched
            tokens.append(
                {
                    "kind": "punctuation_unit",
                    "value": unit_id,
                    "source": source,
                    "source_start": index,
                    "source_end": index + len(source),
                    "source_codepoints": [f"U+{ord(char):04X}" for char in source],
                }
            )
            index += len(source)
            continue
        source = value[index]
        tokens.append(
            {
                "kind": "raw_character",
                "value": source,
                "source": source,
                "source_start": index,
                "source_end": index + 1,
                "source_codepoints": [f"U+{ord(source):04X}"],
            }
        )
        index += 1
    return tokens


def compare_quote_punctuation_units(
    model_quote: str,
    formal_quote: str,
) -> dict[str, Any]:
    """在带类型 token 上做连续子序列比较，返回唯一审计事实。"""

    model_tokens = tokenize_quote_punctuation_units(model_quote)
    formal_tokens = tokenize_quote_punctuation_units(formal_quote)
    model_keys = [(str(row["kind"]), str(row["value"])) for row in model_tokens]
    formal_keys = [(str(row["kind"]), str(row["value"])) for row in formal_tokens]
    starts = [
        start
        for start in range(len(formal_keys) - len(model_keys) + 1)
        if formal_keys[start : start + len(model_keys)] == model_keys
    ]
    matched = bool(starts)
    token_start = starts[0] if matched else None
    token_end = token_start + len(model_keys) if token_start is not None else None
    formal_source_start = (
        int(formal_tokens[token_start]["source_start"])
        if token_start is not None
        else None
    )
    formal_source_end = (
        int(formal_tokens[token_end - 1]["source_end"])
        if token_end is not None and token_end > token_start
        else None
    )
    raw_start = formal_quote.find(model_quote)
    raw_matched = raw_start >= 0
    return {
        "matched": matched,
        "raw_substring_matched": raw_matched,
        "raw_substring_start": raw_start if raw_matched else None,
        "raw_substring_end": raw_start + len(model_quote) if raw_matched else None,
        "unit_substring_match_count": len(starts),
        "unit_substring_start": token_start,
        "unit_substring_end": token_end,
        "formal_source_start": formal_source_start,
        "formal_source_end": formal_source_end,
        "formal_source_slice": (
            formal_quote[formal_source_start:formal_source_end]
            if formal_source_start is not None and formal_source_end is not None
            else None
        ),
        "unit_equivalence_required_for_match": matched and not raw_matched,
        "model_tokens": model_tokens,
        "formal_tokens": formal_tokens,
        "punctuation_unit_equivalence_sha256": (
            QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
        ),
    }


def validate_review_batch(raw: Any) -> dict[str, Any]:
    batch = _mapping(raw, "检查批")
    if batch.get("contract_version") != INPUT_CONTRACT:
        raise InspectorError(f"检查批合同必须是 {INPUT_CONTRACT}")
    batch_id = _safe_id(batch.get("batch_id"), "batch_id")
    if batch.get("decision_scope") != "routing_only":
        raise InspectorError("decision_scope 必须是 routing_only")
    items = _list(batch.get("items"), "items")
    if not items:
        raise InspectorError("items 不能为空")
    if len(items) > 100:
        raise InspectorError("单批最多 100 条，防止检查员吞入整库")

    normalized_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(items):
        item = _mapping(value, f"items[{index}]")
        item_id = _safe_id(item.get("item_id"), f"items[{index}].item_id")
        if item_id in seen_ids:
            raise InspectorError(f"item_id 重复：{item_id}")
        seen_ids.add(item_id)
        check_type = _text(item.get("check_type"), f"{item_id}.check_type")
        if check_type not in CHECK_TYPES:
            raise InspectorError(f"{item_id} 的 check_type 不受支持：{check_type}")
        source_kind = _text(item.get("source_kind"), f"{item_id}.source_kind")
        claim = _text(item.get("claim"), f"{item_id}.claim")
        anchors = _list(item.get("anchors"), f"{item_id}.anchors")
        if not anchors:
            raise InspectorError(f"{item_id} 至少要有一个锚")
        anchor_rows: list[dict[str, Any]] = []
        seen_anchor_ids: set[str] = set()
        for anchor_index, anchor_value in enumerate(anchors):
            anchor = _mapping(anchor_value, f"{item_id}.anchors[{anchor_index}]")
            anchor_id = _safe_id(anchor.get("anchor_id"), f"{item_id}.anchor_id")
            if anchor_id in seen_anchor_ids:
                raise InspectorError(f"{item_id} 的 anchor_id 重复：{anchor_id}")
            seen_anchor_ids.add(anchor_id)
            chapter = anchor.get("chapter")
            if (
                isinstance(chapter, bool)
                or not isinstance(chapter, int)
                or chapter <= 0
            ):
                raise InspectorError(f"{item_id}/{anchor_id} 的 chapter 必须是正整数")
            quote = _text(anchor.get("quote"), f"{item_id}/{anchor_id}.quote")
            if len(quote) > 300:
                raise InspectorError(f"{item_id}/{anchor_id} 的 quote 超过 300 字")
            anchor_rows.append(
                {"anchor_id": anchor_id, "chapter": chapter, "quote": quote}
            )

        risks = _list(item.get("declared_risks", []), f"{item_id}.declared_risks")
        normalized_risks: list[str] = []
        for risk in risks:
            risk_text = _text(risk, f"{item_id}.declared_risks")
            if risk_text not in DECLARED_RISKS:
                raise InspectorError(f"{item_id} 的风险枚举不受支持：{risk_text}")
            if risk_text not in normalized_risks:
                normalized_risks.append(risk_text)
        normalized_items.append(
            {
                "item_id": item_id,
                "check_type": check_type,
                "source_kind": source_kind,
                "claim": claim,
                "anchors": anchor_rows,
                "declared_risks": normalized_risks,
                "metadata": _mapping(item.get("metadata", {}), f"{item_id}.metadata"),
            }
        )

    return {
        "contract_version": INPUT_CONTRACT,
        "batch_id": batch_id,
        "decision_scope": "routing_only",
        "sampling_seed": _text(batch.get("sampling_seed"), "sampling_seed"),
        "items": normalized_items,
    }


def detected_risks(item: Mapping[str, Any]) -> list[str]:
    risks = set(str(value) for value in item.get("declared_risks", []))
    claim = str(item.get("claim", ""))
    if AMBIGUITY_RE.search(claim):
        risks.add("ambiguity")
    if NEGATION_RE.search(claim):
        risks.add("negation")
    chapters = {anchor.get("chapter") for anchor in item.get("anchors", [])}
    if item.get("check_type") == "cross_chapter_causality" or len(chapters) > 1:
        risks.add("cross_chapter_causality")
    return sorted(risks)


def split_by_rule_gate(
    batch: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    api_items: list[dict[str, Any]] = []
    escalated: list[dict[str, Any]] = []
    for item_value in batch["items"]:
        item = dict(item_value)
        risks = detected_risks(item)
        strong = sorted(AUTO_STRONG_REVIEW_RISKS.intersection(risks))
        if strong:
            escalated.append(
                {
                    "item_id": item["item_id"],
                    "route": "strong_review",
                    "source": "rule_gate",
                    "risk_reasons": strong,
                    "all_detected_risks": risks,
                    "final_truth": False,
                }
            )
        else:
            item["detected_risks"] = risks
            api_items.append(item)
    return api_items, escalated


def _system_prompt_with_suffix(system_prompt_suffix: str | None) -> str:
    if system_prompt_suffix is None:
        return SYSTEM_PROMPT
    if (
        not isinstance(system_prompt_suffix, str)
        or not system_prompt_suffix
        or system_prompt_suffix != system_prompt_suffix.strip()
        or "\n" in system_prompt_suffix
        or "\r" in system_prompt_suffix
    ):
        raise InspectorError("检查员系统消息增量必须是一条非空单行且无首尾空白")
    return f"{SYSTEM_PROMPT}\n{system_prompt_suffix}"


def build_messages(
    batch: Mapping[str, Any],
    api_items: Iterable[Mapping[str, Any]],
    *,
    system_prompt_suffix: str | None = None,
) -> list[dict[str, str]]:
    items = list(api_items)
    payload = {
        "contract_version": MODEL_INPUT_CONTRACT,
        "batch_id": batch["batch_id"],
        "decision_scope": "routing_only",
        "rules": {
            "pass_candidate": "陈述的全部事实头都被所给锚直接支撑；仍不是正式真值。",
            "review_candidate": "存在部分支撑、不支撑、粒度／类型疑义，转强审。",
            "uncertain": "无法可靠判断，转强审。",
            "no_rewrite": "不得改写 claim，不得添加输入没有的事实。",
        },
        "output_contract": {
            "contract_version": MODEL_OUTPUT_CONTRACT,
            "results": [
                {
                    "item_id": "原 item_id",
                    "decision": "pass_candidate|review_candidate|uncertain",
                    "support": "direct_support|partial_support|not_support|uncertain",
                    "rule_ids": ["SEM-01"],
                    "evidence": [
                        {
                            "anchor_id": "输入锚ID",
                            "quote": "输入原文短引",
                            "reason": "支撑或不支撑理由",
                        }
                    ],
                    "confidence": "0到1数字",
                    "needs_strong_review": "布尔值",
                    "reason": "简短判词",
                }
            ],
        },
        "items": items,
    }
    return [
        {
            "role": "system",
            "content": _system_prompt_with_suffix(system_prompt_suffix),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def _validate_evidence_quote_policy(
    evidence_quote_policy: str,
    minimum_quote_nonspace_chars: int,
) -> None:
    if evidence_quote_policy not in EVIDENCE_QUOTE_POLICIES:
        raise InspectorError(f"短引校验策略不受支持：{evidence_quote_policy}")
    if (
        isinstance(minimum_quote_nonspace_chars, bool)
        or not isinstance(minimum_quote_nonspace_chars, int)
        or minimum_quote_nonspace_chars <= 0
    ):
        raise InspectorError("短引最短非空白字符门槛必须是正整数")


def _model_quote_verbatim(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InspectorError(f"{label} 必须是非空字符串")
    return value


def _quote_fill_audit_record(
    *,
    item_id: str,
    evidence_index: int,
    anchor_id: str,
    model_quote: str,
    formal_quote: str,
    minimum_quote_nonspace_chars: int,
    evidence_quote_policy: str = EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING,
    punctuation_unit_match: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    substring_start = formal_quote.find(model_quote)
    record = {
        "item_id": item_id,
        "evidence_index": evidence_index,
        "anchor_id": anchor_id,
        "model_quote": model_quote,
        "formal_quote": formal_quote,
        "program_filled_from_anchor_id": True,
        "has_fill_difference": model_quote != formal_quote,
        "model_quote_chars": len(model_quote),
        "model_quote_nonspace_chars": sum(not char.isspace() for char in model_quote),
        "formal_quote_chars": len(formal_quote),
        "formal_quote_nonspace_chars": sum(not char.isspace() for char in formal_quote),
        "substring_start": substring_start,
        "substring_end": substring_start + len(model_quote),
        "minimum_quote_nonspace_chars": minimum_quote_nonspace_chars,
    }
    if (
        evidence_quote_policy
        == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
    ):
        normalized_model_quote, model_hits = normalize_quote_punctuation(model_quote)
        normalized_formal_quote, formal_hits = normalize_quote_punctuation(formal_quote)
        normalized_start = normalized_formal_quote.find(normalized_model_quote)
        if normalized_start < 0:
            raise InspectorError("标点归一化短引通过后无法重建审计坐标")
        record.update(
            {
                "substring_start": substring_start if substring_start >= 0 else None,
                "substring_end": (
                    substring_start + len(model_quote) if substring_start >= 0 else None
                ),
                "raw_substring_matched": substring_start >= 0,
                "raw_substring_start": substring_start
                if substring_start >= 0
                else None,
                "raw_substring_end": (
                    substring_start + len(model_quote) if substring_start >= 0 else None
                ),
                "normalized_model_quote": normalized_model_quote,
                "normalized_formal_quote": normalized_formal_quote,
                "normalized_substring_start": normalized_start,
                "normalized_substring_end": normalized_start
                + len(normalized_model_quote),
                "normalization_required_for_match": substring_start < 0,
                "match_mode": (
                    "raw_contiguous_substring"
                    if substring_start >= 0
                    else "punctuation_equivalent_contiguous_substring"
                ),
                "model_normalization_hits": model_hits,
                "formal_normalization_hits": formal_hits,
                "punctuation_equivalence_sha256": (
                    QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                ),
            }
        )
    elif (
        evidence_quote_policy
        == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
    ):
        unit_match = dict(
            punctuation_unit_match
            if punctuation_unit_match is not None
            else compare_quote_punctuation_units(model_quote, formal_quote)
        )
        if unit_match.get("matched") is not True:
            raise InspectorError("标点单元短引通过后无法重建审计坐标")
        record.update(
            {
                "substring_start": unit_match["raw_substring_start"],
                "substring_end": unit_match["raw_substring_end"],
                "raw_substring_matched": unit_match["raw_substring_matched"],
                "raw_substring_start": unit_match["raw_substring_start"],
                "raw_substring_end": unit_match["raw_substring_end"],
                "unit_substring_matched": True,
                "unit_substring_match_count": unit_match[
                    "unit_substring_match_count"
                ],
                "unit_substring_start": unit_match["unit_substring_start"],
                "unit_substring_end": unit_match["unit_substring_end"],
                "formal_source_start": unit_match["formal_source_start"],
                "formal_source_end": unit_match["formal_source_end"],
                "formal_source_slice": unit_match["formal_source_slice"],
                "unit_equivalence_required_for_match": unit_match[
                    "unit_equivalence_required_for_match"
                ],
                "match_mode": (
                    "raw_contiguous_substring"
                    if unit_match["raw_substring_matched"]
                    else "punctuation_unit_equivalent_contiguous_subsequence"
                ),
                "model_unit_tokens": unit_match["model_tokens"],
                "formal_unit_tokens": unit_match["formal_tokens"],
                "punctuation_unit_equivalence_sha256": (
                    QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                ),
                "formal_fill_is_frozen_quote": formal_quote == record["formal_quote"],
            }
        )
    return record


def build_quote_fill_audit(
    *,
    batch_id: str,
    rows: Iterable[Mapping[str, Any]],
    minimum_quote_nonspace_chars: int,
    evidence_quote_policy: str = EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING,
) -> dict[str, Any]:
    normalized_rows = [dict(row) for row in rows]
    audit = {
        "schema_version": QUOTE_FILL_AUDIT_CONTRACT,
        "batch_id": batch_id,
        "evidence_quote_policy": evidence_quote_policy,
        "minimum_quote_nonspace_chars": minimum_quote_nonspace_chars,
        "evidence_rows": len(normalized_rows),
        "program_filled_rows": len(normalized_rows),
        "differing_rows": sum(
            bool(row["has_fill_difference"]) for row in normalized_rows
        ),
        "rows": normalized_rows,
    }
    if (
        evidence_quote_policy
        == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
    ):
        audit.update(
            {
                "punctuation_equivalence_contract": (
                    quote_punctuation_equivalence_contract()
                ),
                "punctuation_equivalence_sha256": (
                    QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                ),
                "raw_substring_rows": sum(
                    bool(row.get("raw_substring_matched")) for row in normalized_rows
                ),
                "normalization_rescued_rows": sum(
                    bool(row.get("normalization_required_for_match"))
                    for row in normalized_rows
                ),
                "normalization_hit_rows": sum(
                    bool(row.get("model_normalization_hits"))
                    or bool(row.get("formal_normalization_hits"))
                    for row in normalized_rows
                ),
            }
        )
    elif (
        evidence_quote_policy
        == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
    ):
        audit.update(
            {
                "punctuation_unit_equivalence_contract": (
                    quote_punctuation_unit_equivalence_contract()
                ),
                "punctuation_unit_equivalence_sha256": (
                    QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                ),
                "raw_substring_rows": sum(
                    bool(row.get("raw_substring_matched"))
                    for row in normalized_rows
                ),
                "unit_equivalence_rescued_rows": sum(
                    bool(row.get("unit_equivalence_required_for_match"))
                    for row in normalized_rows
                ),
                "unit_mapping_hit_rows": sum(
                    any(
                        token.get("kind") == "punctuation_unit"
                        for token in row.get("model_unit_tokens", [])
                    )
                    or any(
                        token.get("kind") == "punctuation_unit"
                        for token in row.get("formal_unit_tokens", [])
                    )
                    for row in normalized_rows
                ),
            }
        )
    return audit


def parse_model_output(
    content: str,
    api_items: Iterable[Mapping[str, Any]],
    *,
    evidence_quote_policy: str = EVIDENCE_QUOTE_POLICY_EXACT,
    minimum_quote_nonspace_chars: int = 1,
    quote_fill_audit_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    _validate_evidence_quote_policy(evidence_quote_policy, minimum_quote_nonspace_chars)
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InspectorError(
            "DeepSeek 分流回包不是合法 JSON；硬停，不自动修补"
        ) from exc
    root = _mapping(raw, "DeepSeek 分流回包")
    if root.get("contract_version") != MODEL_OUTPUT_CONTRACT:
        raise InspectorError(f"DeepSeek 回包合同必须是 {MODEL_OUTPUT_CONTRACT}")
    results = _list(root.get("results"), "DeepSeek.results")
    expected = {str(item["item_id"]): item for item in api_items}
    if len(results) != len(expected):
        raise InspectorError(
            f"DeepSeek 返回条数不等于输入：{len(results)}/{len(expected)}"
        )
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(results):
        row = _mapping(value, f"DeepSeek.results[{index}]")
        item_id = _safe_id(row.get("item_id"), "DeepSeek.item_id")
        if item_id not in expected or item_id in seen:
            raise InspectorError(f"DeepSeek 返回未知或重复 item_id：{item_id}")
        seen.add(item_id)
        decision = _text(row.get("decision"), f"{item_id}.decision")
        support = _text(row.get("support"), f"{item_id}.support")
        if decision not in MODEL_DECISIONS:
            raise InspectorError(f"{item_id} 的 decision 非法：{decision}")
        if support not in SUPPORT_VALUES:
            raise InspectorError(f"{item_id} 的 support 非法：{support}")
        if decision == "pass_candidate" and support != "direct_support":
            raise InspectorError(f"{item_id} 只有 direct_support 才能进入通过候选")
        confidence = row.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise InspectorError(f"{item_id}.confidence 必须是 0～1 数字")
        confidence_value = float(confidence)
        if not 0.0 <= confidence_value <= 1.0:
            raise InspectorError(f"{item_id}.confidence 超出 0～1")
        needs_review = row.get("needs_strong_review")
        if not isinstance(needs_review, bool):
            raise InspectorError(f"{item_id}.needs_strong_review 必须是布尔值")
        rules = [
            _text(rule, f"{item_id}.rule_ids")
            for rule in _list(row.get("rule_ids"), f"{item_id}.rule_ids")
        ]
        if not rules:
            raise InspectorError(f"{item_id}.rule_ids 不能为空")
        allowed_anchors = {
            str(anchor["anchor_id"]): str(anchor["quote"])
            for anchor in expected[item_id]["anchors"]
        }
        evidence: list[dict[str, str]] = []
        for ev_index, ev_value in enumerate(
            _list(row.get("evidence"), f"{item_id}.evidence")
        ):
            ev = _mapping(ev_value, f"{item_id}.evidence[{ev_index}]")
            anchor_id = _safe_id(ev.get("anchor_id"), f"{item_id}.evidence.anchor_id")
            if evidence_quote_policy == EVIDENCE_QUOTE_POLICY_EXACT:
                quote = _text(ev.get("quote"), f"{item_id}.evidence.quote")
                if (
                    anchor_id not in allowed_anchors
                    or quote != allowed_anchors[anchor_id]
                ):
                    raise InspectorError(
                        f"{item_id} 回包引用了输入外锚或改写了短引：{anchor_id}"
                    )
                formal_quote = quote
            else:
                if anchor_id not in allowed_anchors:
                    raise InspectorError(f"{item_id} 回包引用了输入外锚：{anchor_id}")
                quote = _model_quote_verbatim(
                    ev.get("quote"), f"{item_id}.evidence.quote"
                )
                nonspace_chars = sum(not char.isspace() for char in quote)
                if nonspace_chars < minimum_quote_nonspace_chars:
                    raise InspectorError(
                        f"{item_id}/{anchor_id} 模型短引低于最短非空白字符门槛："
                        f"{nonspace_chars}/{minimum_quote_nonspace_chars}"
                    )
                formal_quote = allowed_anchors[anchor_id]
                if (
                    evidence_quote_policy
                    == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING
                ):
                    if quote not in formal_quote:
                        raise InspectorError(
                            f"{item_id}/{anchor_id} "
                            "模型短引不是冻结输入短引的逐字连续子串"
                        )
                    punctuation_unit_match = None
                elif (
                    evidence_quote_policy
                    == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
                ):
                    normalized_quote, _ = normalize_quote_punctuation(quote)
                    normalized_formal_quote, _ = normalize_quote_punctuation(
                        formal_quote
                    )
                    if normalized_quote not in normalized_formal_quote:
                        raise InspectorError(
                            f"{item_id}/{anchor_id} 标点归一化后仍不是冻结输入短引的"
                            "逐字连续子串（映射表外内容差异）"
                        )
                    punctuation_unit_match = None
                elif (
                    evidence_quote_policy
                    == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
                ):
                    punctuation_unit_match = compare_quote_punctuation_units(
                        quote, formal_quote
                    )
                    if punctuation_unit_match["matched"] is not True:
                        raise InspectorError(
                            f"{item_id}/{anchor_id} 标点单元比较后仍不是冻结输入短引的"
                            "连续子序列（映射表外内容差异）"
                        )
                else:  # pragma: no cover - 策略已在函数入口被拒绝
                    raise InspectorError(f"短引校验策略不受支持：{evidence_quote_policy}")
                if quote_fill_audit_rows is not None:
                    quote_fill_audit_rows.append(
                        _quote_fill_audit_record(
                            item_id=item_id,
                            evidence_index=ev_index,
                            anchor_id=anchor_id,
                            model_quote=quote,
                            formal_quote=formal_quote,
                            minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
                            evidence_quote_policy=evidence_quote_policy,
                            punctuation_unit_match=punctuation_unit_match,
                        )
                    )
            evidence.append(
                {
                    "anchor_id": anchor_id,
                    "quote": formal_quote,
                    "reason": _text(ev.get("reason"), f"{item_id}.evidence.reason"),
                }
            )
        if not evidence:
            raise InspectorError(f"{item_id}.evidence 不能为空")
        normalized.append(
            {
                "item_id": item_id,
                "decision": decision,
                "support": support,
                "rule_ids": sorted(set(rules)),
                "evidence": evidence,
                "confidence": confidence_value,
                "needs_strong_review": needs_review,
                "reason": _text(row.get("reason"), f"{item_id}.reason"),
                "final_truth": False,
            }
        )
    if seen != set(expected):
        raise InspectorError(f"DeepSeek 回包漏 item_id：{sorted(set(expected) - seen)}")
    return sorted(normalized, key=lambda row: row["item_id"])


def deterministic_sample(ids: Iterable[str], *, ratio: float, seed: str) -> list[str]:
    values = sorted(set(ids))
    if not values:
        return []
    if not 0.0 < ratio <= 1.0:
        raise InspectorError("抽样比例必须在 0～1 之间")
    count = max(1, math.ceil(len(values) * ratio))
    ranked = sorted(
        values,
        key=lambda value: hashlib.sha256(
            f"{seed}\0{value}".encode("utf-8")
        ).hexdigest(),
    )
    return sorted(ranked[:count])


def build_routing_result(
    *,
    batch: Mapping[str, Any],
    model_rows: Iterable[Mapping[str, Any]],
    rule_escalated: Iterable[Mapping[str, Any]],
    sample_ratio: float = 0.10,
) -> dict[str, Any]:
    model = [dict(row) for row in model_rows]
    pass_ids = [
        row["item_id"]
        for row in model
        if row["decision"] == "pass_candidate" and not row["needs_strong_review"]
    ]
    sample_ids = set(
        deterministic_sample(
            pass_ids, ratio=sample_ratio, seed=str(batch["sampling_seed"])
        )
    )
    routes = [dict(row) for row in rule_escalated]
    for row in model:
        if row["item_id"] in sample_ids:
            route = "strong_review_sample"
        elif row["decision"] == "pass_candidate" and not row["needs_strong_review"]:
            route = "provisional_pass_unreviewed"
        else:
            route = "strong_review"
        routes.append(
            {
                "item_id": row["item_id"],
                "route": route,
                "source": "deepseek_router",
                "model_decision": row["decision"],
                "model_support": row["support"],
                "confidence": row["confidence"],
                "reason": row["reason"],
                "final_truth": False,
            }
        )
    counts = {
        name: sum(1 for row in routes if row["route"] == name)
        for name in (
            "provisional_pass_unreviewed",
            "strong_review_sample",
            "strong_review",
        )
    }
    return {
        "contract_version": RESULT_CONTRACT,
        "batch_id": batch["batch_id"],
        "decision_scope": "routing_only",
        "sample_policy": {
            "base_ratio": sample_ratio,
            "seed": batch["sampling_seed"],
            "pass_bucket_size": len(pass_ids),
            "sample_ids": sorted(sample_ids),
        },
        "routes": sorted(routes, key=lambda row: row["item_id"]),
        "counts": counts,
        "deepseek_results": model,
        "final_truth": False,
        "authority_boundary": "所有非机械结论只是分流候选；正式判词由强审或 CZ 权限节点给出。",
    }


def audit_rule_registry(
    path: Path = DEFAULT_RULE_REGISTRY, *, root: Path = ROOT
) -> dict[str, Any]:
    raw = _mapping(read_json(path), "纯规则登记")
    if raw.get("schema_version") != "pipeline-rule-check-registry-v1":
        raise InspectorError("纯规则登记合同版本不符")
    checks = _list(raw.get("checks"), "checks")
    expected = {f"A{number:02d}" for number in range(1, 19)}
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for value in checks:
        row = _mapping(value, "rule_check")
        check_id = _safe_id(row.get("check_id"), "check_id")
        if check_id in seen:
            raise InspectorError(f"纯规则登记 ID 重复：{check_id}")
        seen.add(check_id)
        if row.get("execution") != "program":
            raise InspectorError(f"{check_id} 尚未转程序")
        source = _text(row.get("source_path"), f"{check_id}.source_path")
        source_path = resolve_repo_path(root, source)
        if not source_path.is_file():
            raise InspectorError(f"{check_id} 程序来源不存在：{source}")
        rows.append(
            {
                "check_id": check_id,
                "name": _text(row.get("name"), f"{check_id}.name"),
                "source_path": source,
                "source_sha256": sha256_file(source_path),
                "entrypoint": _text(row.get("entrypoint"), f"{check_id}.entrypoint"),
                "passed": True,
            }
        )
    if seen != expected:
        raise InspectorError(
            f"纯规则登记必须覆盖 A01～A18；缺={sorted(expected - seen)} 多={sorted(seen - expected)}"
        )
    return {
        "schema_version": "pipeline-rule-check-audit-v1",
        "registry_path": path.relative_to(root).as_posix()
        if path.is_relative_to(root)
        else str(path),
        "checked": len(rows),
        "passed": len(rows),
        "errors": 0,
        "rows": sorted(rows, key=lambda row: row["check_id"]),
    }


def _attempt_count(run_dir: Path) -> int:
    path = run_dir / "call_attempts.jsonl"
    if not path.is_file():
        return 0
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def _secret_scan(run_dir: Path, secret: str) -> dict[str, Any]:
    secret_bytes = secret.encode("utf-8") if secret else b""
    hits: list[str] = []
    bearer_hits: list[str] = []
    for path in sorted(value for value in run_dir.rglob("*") if value.is_file()):
        data = path.read_bytes()
        relative = path.relative_to(run_dir).as_posix()
        if secret_bytes and secret_bytes in data:
            hits.append(relative)
        if b"authorization: bearer " in data.lower():
            bearer_hits.append(relative)
    return {
        "files_scanned": sum(1 for value in run_dir.rglob("*") if value.is_file()),
        "exact_secret_hits": hits,
        "authorization_header_hits": bearer_hits,
        "passed": not hits and not bearer_hits,
    }


def run_preflight(
    batch_path: Path,
    run_dir: Path,
    *,
    system_prompt_suffix: str | None = None,
) -> dict[str, Any]:
    batch = validate_review_batch(read_json(batch_path))
    api_items, escalated = split_by_rule_gate(batch)
    messages = build_messages(
        batch,
        api_items,
        system_prompt_suffix=system_prompt_suffix,
    )
    receipt = {
        "schema_version": "semantic-inspector-preflight-v1",
        "batch_id": batch["batch_id"],
        "input_path": str(batch_path),
        "input_sha256": sha256_file(batch_path),
        "items": len(batch["items"]),
        "api_items": len(api_items),
        "rule_escalated": len(escalated),
        "rule_escalated_rows": escalated,
        "messages_sha256": sha256_bytes(stable_json_bytes(messages)),
        "model_api_calls": 0,
        "passed": True,
    }
    write_json_atomic(run_dir / "preflight.json", receipt)
    return receipt


def run_inspector(
    *,
    batch_path: Path,
    run_dir: Path,
    contract_path: Path = DEFAULT_CONTRACT,
    profile: str = DEFAULT_PROFILE,
    max_calls: int = 3,
    system_prompt_suffix: str | None = None,
    evidence_quote_policy: str = EVIDENCE_QUOTE_POLICY_EXACT,
    minimum_quote_nonspace_chars: int = 1,
    call_adapter: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    _validate_evidence_quote_policy(evidence_quote_policy, minimum_quote_nonspace_chars)
    result_path = run_dir / "routing_result.json"
    if result_path.exists() or (run_dir / "call_attempts.jsonl").exists():
        raise InspectorError("运行目录已有正式调用或结果，拒绝复跑挑结果")
    batch = validate_review_batch(read_json(batch_path))
    api_items, escalated = split_by_rule_gate(batch)
    rule_audit = audit_rule_registry()
    write_json_atomic(run_dir / "rule_check_audit.json", rule_audit)
    preflight = run_preflight(
        batch_path,
        run_dir,
        system_prompt_suffix=system_prompt_suffix,
    )
    write_json_atomic(run_dir / "input" / "review_batch.json", batch)

    model_rows: list[dict[str, Any]] = []
    quote_fill_audit_rows: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    transport_metadata: dict[str, Any] = {}
    if api_items:
        bundle = load_contract_bundle(contract_path, profile=profile)
        transport = (
            None
            if call_adapter is not None
            else ApiTransport.from_bundle(bundle, run_dir=run_dir, max_calls=max_calls)
        )
        messages = build_messages(
            batch,
            api_items,
            system_prompt_suffix=system_prompt_suffix,
        )
        try:
            response = (
                call_adapter(
                    bundle=bundle,
                    run_dir=run_dir,
                    stage=STAGE,
                    case_id=batch["batch_id"],
                    messages=messages,
                    api_items=api_items,
                    evidence_quote_policy=evidence_quote_policy,
                    minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
                )
                if call_adapter is not None
                else transport.call(  # type: ignore[union-attr]
                    stage=STAGE, case_id=batch["batch_id"], messages=messages
                )
            )
            model_rows = parse_model_output(
                response.content,
                api_items,
                evidence_quote_policy=evidence_quote_policy,
                minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
                quote_fill_audit_rows=quote_fill_audit_rows,
            )
            usage = dict(response.usage)
            transport_metadata = dict(response.metadata)
        except (InspectorError, ZBatchError) as exc:
            hard_stop = {
                "schema_version": "semantic-inspector-hard-stop-v1",
                "batch_id": batch["batch_id"],
                "reason": str(exc),
                "network_attempts": _attempt_count(run_dir),
                "repaired": False,
            }
            if (
                evidence_quote_policy
                in {
                    EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING,
                    EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING,
                }
            ):
                hard_stop.update(
                    {
                        "evidence_quote_policy": evidence_quote_policy,
                        "minimum_quote_nonspace_chars": (minimum_quote_nonspace_chars),
                        "punctuation_equivalence_sha256": (
                            QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256
                            if evidence_quote_policy
                            == EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
                            else QUOTE_PUNCTUATION_EQUIVALENCE_SHA256
                        ),
                    }
                )
            write_json_atomic(run_dir / "hard_stop.json", hard_stop)
            raise

    quote_fill_audit_path: Path | None = None
    if evidence_quote_policy in {
        EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING,
        EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING,
        EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING,
    }:
        quote_fill_audit_path = run_dir / "quote_fill_audit.json"
        write_json_atomic(
            quote_fill_audit_path,
            build_quote_fill_audit(
                batch_id=batch["batch_id"],
                rows=quote_fill_audit_rows,
                minimum_quote_nonspace_chars=minimum_quote_nonspace_chars,
                evidence_quote_policy=evidence_quote_policy,
            ),
        )

    routing = build_routing_result(
        batch=batch, model_rows=model_rows, rule_escalated=escalated
    )
    strong_queue_ids = [
        row["item_id"]
        for row in routing["routes"]
        if row["route"] in {"strong_review", "strong_review_sample"}
    ]
    write_json_atomic(result_path, routing)
    write_json_atomic(
        run_dir / "strong_review_queue.json",
        {
            "contract_version": "strong-review-queue-v1",
            "batch_id": batch["batch_id"],
            "item_ids": strong_queue_ids,
            "items": [
                item for item in batch["items"] if item["item_id"] in strong_queue_ids
            ],
            "authority": "强审给正式判词；本队列不改变任何正式件。",
        },
    )
    write_json_atomic(
        run_dir / "provisional_pass_bucket.json",
        {
            "contract_version": "provisional-pass-bucket-v1",
            "batch_id": batch["batch_id"],
            "item_ids": [
                row["item_id"]
                for row in routing["routes"]
                if row["route"]
                in {"provisional_pass_unreviewed", "strong_review_sample"}
            ],
            "sample_ids": routing["sample_policy"]["sample_ids"],
            "final_truth": False,
        },
    )
    secret_scan = _secret_scan(run_dir, os.environ.get("SENSENOVA_API_KEY", ""))
    if not secret_scan["passed"]:
        write_json_atomic(run_dir / "secret_scan.json", secret_scan)
        raise InspectorError("运行工件发现密钥或 Authorization 头痕迹；硬停")
    write_json_atomic(run_dir / "secret_scan.json", secret_scan)
    receipt = {
        "schema_version": "semantic-inspector-run-receipt-v1",
        "batch_id": batch["batch_id"],
        "status": "complete",
        "decision_scope": "routing_only",
        "items": len(batch["items"]),
        "api_items": preflight["api_items"],
        "rule_escalated": preflight["rule_escalated"],
        "logical_model_calls": 1 if api_items else 0,
        "network_attempts": _attempt_count(run_dir),
        "usage": usage,
        "transport": transport_metadata,
        "rule_checks": {
            "checked": rule_audit["checked"],
            "passed": rule_audit["passed"],
        },
        "secret_scan": secret_scan,
        "outputs": {
            "routing_result": "routing_result.json",
            "strong_review_queue": "strong_review_queue.json",
            "provisional_pass_bucket": "provisional_pass_bucket.json",
        },
        "mutated_formal_artifacts": 0,
    }
    if quote_fill_audit_path is not None:
        receipt["outputs"]["quote_fill_audit"] = quote_fill_audit_path.name
    write_json_atomic(run_dir / "run_receipt.json", receipt)
    experiment = {
        "schema_version": "pipeline-experiment-v1",
        "experiment_id": run_dir.name,
        "status": "complete",
        "module_id": "M11",
        "module_version": "semantic-review-router-v1",
        "summary": "规则先验＋DeepSeek 只分流＋通过桶固定抽样；不产正式真值。",
        "input_sha256": sha256_file(batch_path),
        "result_sha256": sha256_file(result_path),
        "rollback": "停用 inspect 命令并保留本目录；现役链未接入。",
    }
    write_json_atomic(run_dir / "experiment.json", experiment)
    return receipt


def apply_feedback(
    *, result_path: Path, feedback_path: Path, output_path: Path
) -> dict[str, Any]:
    routing = _mapping(read_json(result_path), "routing_result")
    if routing.get("contract_version") != RESULT_CONTRACT:
        raise InspectorError("routing_result 合同不符")
    feedback = _mapping(read_json(feedback_path), "feedback")
    if feedback.get("contract_version") != FEEDBACK_CONTRACT:
        raise InspectorError(f"feedback 合同必须是 {FEEDBACK_CONTRACT}")
    if feedback.get("batch_id") != routing.get("batch_id"):
        raise InspectorError("feedback 的 batch_id 与分流结果不一致")
    sampled = set(routing["sample_policy"]["sample_ids"])
    reviews = _list(feedback.get("reviews"), "feedback.reviews")
    seen: set[str] = set()
    errors = 0
    for value in reviews:
        row = _mapping(value, "feedback.review")
        item_id = _safe_id(row.get("item_id"), "feedback.item_id")
        if item_id not in sampled or item_id in seen:
            raise InspectorError(
                f"feedback 只能覆盖已抽样通过候选且不能重复：{item_id}"
            )
        seen.add(item_id)
        verdict = _text(row.get("verdict"), f"{item_id}.verdict")
        if verdict not in {"confirmed_pass", "misjudged"}:
            raise InspectorError(f"{item_id}.verdict 非法：{verdict}")
        if verdict == "misjudged":
            errors += 1
    if seen != sampled:
        raise InspectorError(f"feedback 未覆盖全部抽样项：{sorted(sampled - seen)}")
    error_rate = errors / len(reviews) if reviews else 0.0
    ratio = 0.30 if error_rate > 0.02 else 0.10
    pass_ids = [
        row["item_id"]
        for row in routing["routes"]
        if row["route"] in {"provisional_pass_unreviewed", "strong_review_sample"}
    ]
    expanded = deterministic_sample(
        pass_ids, ratio=ratio, seed=routing["sample_policy"]["seed"]
    )
    receipt = {
        "contract_version": "semantic-inspector-feedback-receipt-v1",
        "batch_id": routing["batch_id"],
        "reviewed": len(reviews),
        "misjudged": errors,
        "misjudgment_rate": error_rate,
        "threshold": 0.02,
        "sample_ratio": ratio,
        "expanded_to_30_percent": ratio == 0.30,
        "sample_ids": expanded,
        "new_review_ids": sorted(set(expanded) - sampled),
        "final_truth": False,
    }
    write_json_atomic(output_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M11 低成本语义检查分流器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser(
        "audit-rules", help="核对 A01～A18 纯规则项均有程序来源"
    )
    audit.add_argument("--registry", type=Path, default=DEFAULT_RULE_REGISTRY)
    audit.add_argument("--output", type=Path)

    preflight = subparsers.add_parser("preflight", help="0 调用检查输入与自动升级风险")
    preflight.add_argument("--input", type=Path, required=True)
    preflight.add_argument("--run-dir", type=Path, required=True)

    run = subparsers.add_parser("run", help="发一次 DeepSeek 分流请求")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--run-dir", type=Path, required=True)
    run.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    run.add_argument("--profile", default=DEFAULT_PROFILE)
    run.add_argument("--max-calls", type=int, default=3)

    feedback = subparsers.add_parser("feedback", help="录入强审抽查，必要时扩到 30%%")
    feedback.add_argument("--result", type=Path, required=True)
    feedback.add_argument("--feedback", type=Path, required=True)
    feedback.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit-rules":
        result = audit_rule_registry(args.registry)
        if args.output:
            write_json_atomic(args.output, result)
    elif args.command == "preflight":
        result = run_preflight(args.input, args.run_dir)
    elif args.command == "run":
        result = run_inspector(
            batch_path=args.input,
            run_dir=args.run_dir,
            contract_path=args.contract,
            profile=args.profile,
            max_calls=args.max_calls,
        )
    else:
        result = apply_feedback(
            result_path=args.result,
            feedback_path=args.feedback,
            output_path=args.output,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
