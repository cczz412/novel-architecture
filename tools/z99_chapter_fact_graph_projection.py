#!/usr/bin/env python3
"""Build four candidate consumer views from the locked X01 chapter-3 UCR return.

This is an offline, deterministic projection.  It does not score, activate, or
rewrite formal gold material.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELATIVE_PATH = Path(
    "references/diagnostic-returns/"
    "六本金标UCR核准回包_20260724/"
    "原始回包/"
    "X01-ch0003-structure-v1.2_candidate_RFU_UCR_review.json"
)
EXPECTED_SOURCE_SHA256 = (
    "8056fe4a810ae255881b04028128e11e7c08a7abafe5baaf58cf8ba0b7ad3f1a"
)
DEFAULT_OUTPUT_RELATIVE_PATH = Path(
    "experiments/Z99_external_finalization_supply_20260724/four_views"
)
EXPECTED_GOLD_ID = "X01-ch0003-structure-v1.2-candidate-rfu-ucr-20260724"
EXPECTED_SOURCE_STATUS = "candidate_revision_not_active"
EXPECTED_PROJECTABLE_PART_COUNT = 23
EXPECTED_UNRESOLVED_COUNT = 4

CONTRACT_FILENAME = "four_views_contract_v0.1.json"
COMBINED_SAMPLE_FILENAME = "four_views_candidate_sample.json"
TIMELINE_FILENAME = "timeline_candidate_view.json"
CAUSAL_FILENAME = "causal_candidate_view.json"
CHARACTER_STATE_FILENAME = "character_state_candidate_view.json"
UNRESOLVED_FILENAME = "unresolved_candidate_view.json"
MARKDOWN_SAMPLE_FILENAME = "four_views_candidate_sample.md"
AUDIT_SIDECAR_FILENAME = "four_views_audit_sidecar.json"
ACCEPTANCE_RECEIPT_FILENAME = "four_views_acceptance_receipt.md"
MANIFEST_FILENAME = "manifest.json"

CONSUMER_VIEW_FILENAMES = (
    COMBINED_SAMPLE_FILENAME,
    TIMELINE_FILENAME,
    CAUSAL_FILENAME,
    CHARACTER_STATE_FILENAME,
    UNRESOLVED_FILENAME,
)

# The original Chinese or compound type is always kept in every projected
# qualifier.  These dimensions are an explicit parallel mapping, never a
# replacement for the source type.
QUALIFIER_TYPE_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "actuality": ("actuality",),
    "地点": ("location",),
    "对象": ("object_scope",),
    "归因": ("attribution",),
    "归因/actuality": ("attribution", "actuality"),
    "情态": ("modality",),
    "数量": ("quantity",),
    "方式": ("manner",),
    "时间": ("time",),
    "时间/情态": ("time", "modality"),
    "时间安排": ("time", "schedule"),
    "时间来源": ("time", "source"),
    "条件": ("condition",),
    "条件/时间": ("condition", "time"),
    "来源": ("source",),
    "来源/方法": ("source", "method"),
    "步骤": ("step",),
    "目的": ("purpose",),
    "目的/动机": ("purpose", "motivation"),
    "结果": ("result",),
    "背景": ("background",),
    "范围": ("scope",),
    "语境": ("context",),
    "频率": ("time", "frequency"),
}

CAUSAL_DIMENSIONS = frozenset({"condition", "purpose", "motivation"})

# These names and fragments are intentionally absent from all JSON consumer
# views.  They remain available in the separate full audit sidecar.
FORBIDDEN_CONSUMER_KEYS = frozenset(
    {
        "adjudication_history",
        "adjudication_ids",
        "audit",
        "change_summary",
        "evidence_status",
        "failure_codes",
        "minimal_support_sets",
        "original_semantic_points_audit_only",
        "part_review_table",
        "pathology_tags",
        "predecessor_claim_audit",
        "review",
        "review_provenance",
        "semantic_point_ids",
        "source_evidence",
        "source_short_quote",
        "verdict",
        "why_required",
        "window_evidence_refs_audit_only",
    }
)
FORBIDDEN_CONSUMER_KEY_FRAGMENTS = ("quote", "review", "pathology", "evidence")
ANCHOR_ID_PATTERN = re.compile(r"ch\d{4}:E\d{4}")


class ProjectionError(ValueError):
    """Raised when the locked input or projection contract is violated."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_locked_source(
    source_path: Path | None = None,
    *,
    expected_sha256: str = EXPECTED_SOURCE_SHA256,
) -> tuple[dict[str, Any], bytes]:
    """Load the one authorized UCR return and reject any byte drift."""

    path = source_path or (REPO_ROOT / SOURCE_RELATIVE_PATH)
    raw = path.read_bytes()
    actual_sha256 = sha256_bytes(raw)
    if actual_sha256 != expected_sha256:
        raise ProjectionError(
            "指定 UCR 回包 SHA 不匹配："
            f"expected={expected_sha256} actual={actual_sha256} path={path}"
        )
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProjectionError(f"指定 UCR 回包不是合法 JSON：{exc}") from exc
    if not isinstance(document, dict):
        raise ProjectionError("指定 UCR 回包顶层必须是对象。")
    return document, raw


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProjectionError(f"{label} 必须是对象。")
    return value


def _require_sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ProjectionError(f"{label} 必须是数组。")
    return value


def _validate_source_identity(document: Mapping[str, Any]) -> None:
    if document.get("gold_id") != EXPECTED_GOLD_ID:
        raise ProjectionError(
            "输入不是已锁定的 X01 第3章 UCR 候选回包：gold_id 不匹配。"
        )
    if document.get("status") != EXPECTED_SOURCE_STATUS:
        raise ProjectionError(
            "输入候选状态发生漂移，拒绝把它误当成可投影的同一份候选件。"
        )


def _project_fact_head(fact_head: object, part_id: str) -> dict[str, Any]:
    mapping = _require_mapping(fact_head, f"{part_id}.rfu.fact_head")
    required = ("subject", "predicate", "object", "result", "polarity", "actuality")
    missing = [key for key in required if key not in mapping]
    if missing:
        raise ProjectionError(f"{part_id} 的事实头缺字段：{missing}")
    projected: dict[str, Any] = {}
    for key in required:
        value = mapping[key]
        if not isinstance(value, str) or not value:
            raise ProjectionError(f"{part_id}.rfu.fact_head.{key} 必须是非空字符串。")
        projected[key] = value
    return projected


def _project_qualifier(qualifier: object, part_id: str) -> dict[str, Any]:
    mapping = _require_mapping(qualifier, f"{part_id}.rfu.required_qualifiers[]")
    original_type = mapping.get("type")
    value = mapping.get("value")
    if not isinstance(original_type, str) or not original_type:
        raise ProjectionError(f"{part_id} 出现无效限定类型。")
    if not isinstance(value, str) or not value:
        raise ProjectionError(f"{part_id} 的限定值必须是非空字符串。")
    dimensions = QUALIFIER_TYPE_DIMENSIONS.get(original_type)
    if dimensions is None:
        raise ProjectionError(
            f"{part_id} 出现未登记限定类型 {original_type!r}；"
            "为避免中文或复合类型被静默丢弃，先补显式映射再投影。"
        )
    return {
        "type_original": original_type,
        "value": value,
        "normalized_dimensions": list(dimensions),
    }


def _iter_projectable_parts(
    document: Mapping[str, Any],
) -> Iterable[dict[str, Any]]:
    """Yield RFU-bearing parts in source-array order.

    The proxy counts every source part, including non-RFU hindsight parts.  Gaps
    are therefore meaningful source-array gaps, not missing clock time.
    """

    source_position = 0
    seen_part_ids: set[str] = set()
    layered_items = _require_sequence(document.get("layered_items"), "layered_items")
    for item_index, item_value in enumerate(layered_items):
        item = _require_mapping(item_value, f"layered_items[{item_index}]")
        parts = _require_sequence(
            item.get("parts"), f"layered_items[{item_index}].parts"
        )
        for part_index, part_value in enumerate(parts):
            source_position += 1
            part = _require_mapping(
                part_value, f"layered_items[{item_index}].parts[{part_index}]"
            )
            rfu_value = part.get("rfu")
            if rfu_value is None:
                continue
            rfu = _require_mapping(rfu_value, f"source part #{source_position}.rfu")
            part_id = part.get("part_id")
            if not isinstance(part_id, str) or not part_id:
                raise ProjectionError(
                    f"source part #{source_position} 的 part_id 不是非空字符串。"
                )
            if part_id in seen_part_ids:
                raise ProjectionError(f"part_id 重复：{part_id}")
            seen_part_ids.add(part_id)
            qualifiers = [
                _project_qualifier(value, part_id)
                for value in _require_sequence(
                    rfu.get("required_qualifiers"),
                    f"{part_id}.rfu.required_qualifiers",
                )
            ]
            yield {
                "part_id": part_id,
                "narrative_order_proxy": source_position,
                "fact_head": _project_fact_head(rfu.get("fact_head"), part_id),
                "required_qualifiers": qualifiers,
            }


def collect_projectable_parts(
    document: Mapping[str, Any],
) -> list[dict[str, Any]]:
    _validate_source_identity(document)
    parts = list(_iter_projectable_parts(document))
    if len(parts) != EXPECTED_PROJECTABLE_PART_COUNT:
        raise ProjectionError(
            "锁定回包的可投影 RFU 数量发生漂移："
            f"expected={EXPECTED_PROJECTABLE_PART_COUNT} actual={len(parts)}"
        )
    unresolved_count = sum(
        row["fact_head"]["actuality"] == "unresolved" for row in parts
    )
    if unresolved_count != EXPECTED_UNRESOLVED_COUNT:
        raise ProjectionError(
            "锁定回包的 unresolved 数量发生漂移："
            f"expected={EXPECTED_UNRESOLVED_COUNT} actual={unresolved_count}"
        )
    return parts


def _view_envelope(
    *,
    view_schema: str,
    boundary: str,
    payload_key: str,
    payload: object,
) -> dict[str, Any]:
    return {
        "schema_version": view_schema,
        "status": "candidate_projection_not_active",
        "source_lock": {
            "sha256": EXPECTED_SOURCE_SHA256,
            "gold_id": EXPECTED_GOLD_ID,
            "source_status": EXPECTED_SOURCE_STATUS,
        },
        "boundary": boundary,
        payload_key: payload,
    }


def build_timeline_view(parts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    explicit_time_qualifier_count = 0
    for part in parts:
        time_qualifiers = [
            copy.deepcopy(qualifier)
            for qualifier in part["required_qualifiers"]
            if "time" in qualifier["normalized_dimensions"]
        ]
        explicit_time_qualifier_count += len(time_qualifiers)
        entries.append(
            {
                "part_id": part["part_id"],
                "narrative_order_proxy": part["narrative_order_proxy"],
                "fact_head": copy.deepcopy(part["fact_head"]),
                "explicit_time_qualifiers": time_qualifiers,
            }
        )
    view = _view_envelope(
        view_schema="z99-timeline-candidate-view-v0.1",
        boundary=(
            "只按源数组顺序给出 narrative_order_proxy，并原样携带显式时间类限定；"
            "不生成钟表时间、不把代理顺序当故事内先后，也不补推相邻事实关系。"
        ),
        payload_key="entries",
        payload=entries,
    )
    view["counts"] = {
        "entry_count": len(entries),
        "explicit_time_qualifier_count": explicit_time_qualifier_count,
    }
    return view


def build_causal_view(parts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for part in parts:
        for qualifier in part["required_qualifiers"]:
            relation_dimensions = [
                dimension
                for dimension in qualifier["normalized_dimensions"]
                if dimension in CAUSAL_DIMENSIONS
            ]
            if not relation_dimensions:
                continue
            candidates.append(
                {
                    "candidate_id": f"CC-{len(candidates) + 1:04d}",
                    "source_part_id": part["part_id"],
                    "narrative_order_proxy": part["narrative_order_proxy"],
                    "relation_dimensions": relation_dimensions,
                    "explicit_qualifier": copy.deepcopy(qualifier),
                    "scoped_fact_head": copy.deepcopy(part["fact_head"]),
                    "derivation": "same_part_explicit_required_qualifier_only",
                }
            )
    view = _view_envelope(
        view_schema="z99-causal-candidate-view-v0.1",
        boundary=(
            "这里只列同一 part 内明写的条件、目的或动机限定候选；"
            "没有把前后相邻条目连成因果，也没有把候选升级为确定因果链。"
        ),
        payload_key="candidates",
        payload=candidates,
    )
    view["counts"] = {"candidate_count": len(candidates)}
    view["adjacency_inference_used"] = False
    return view


def build_character_state_view(
    parts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for part in parts:
        subject = part["fact_head"]["subject"]
        grouped.setdefault(subject, []).append(
            {
                "part_id": part["part_id"],
                "narrative_order_proxy": part["narrative_order_proxy"],
                "fact_head": copy.deepcopy(part["fact_head"]),
                "required_qualifiers": copy.deepcopy(part["required_qualifiers"]),
            }
        )
    subject_groups = [
        {
            "subject_original": subject,
            "entry_count": len(entries),
            "fact_candidates": entries,
        }
        for subject, entries in grouped.items()
    ]
    view = _view_envelope(
        view_schema="z99-character-state-candidate-view-v0.1",
        boundary=(
            "只按事实头里的 subject 原字符串逐字分组；不拆联合主语、不合并别名。"
            "每条只是该 source part 的人物事实候选，不代表人物当前态或章末最终态。"
        ),
        payload_key="subject_groups",
        payload=subject_groups,
    )
    view["counts"] = {
        "subject_group_count": len(subject_groups),
        "fact_candidate_count": sum(
            group["entry_count"] for group in subject_groups
        ),
    }
    view["grouping_rule"] = "exact_subject_string_no_alias_merge"
    view["current_state_claimed"] = False
    return view


def build_unresolved_view(parts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    entries = [
        {
            "part_id": part["part_id"],
            "narrative_order_proxy": part["narrative_order_proxy"],
            "fact_head": copy.deepcopy(part["fact_head"]),
            "required_qualifiers": copy.deepcopy(part["required_qualifiers"]),
        }
        for part in parts
        if part["fact_head"]["actuality"] == "unresolved"
    ]
    view = _view_envelope(
        view_schema="z99-unresolved-candidate-view-v0.1",
        boundary=(
            "唯一入选条件是事实头 actuality 逐字等于 unresolved；"
            "不靠谓词、相邻位置或人工猜测扩充未决项。"
        ),
        payload_key="entries",
        payload=entries,
    )
    view["counts"] = {"entry_count": len(entries)}
    view["selection_rule"] = "fact_head.actuality == unresolved"
    return view


def _walk_keys_and_scalars(value: object) -> Iterable[tuple[str | None, object]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key), child
            yield from _walk_keys_and_scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield None, child
            yield from _walk_keys_and_scalars(child)


def assert_consumer_view_clean(view: Mapping[str, Any]) -> None:
    for key, value in _walk_keys_and_scalars(view):
        if key is not None:
            lowered = key.lower()
            if key in FORBIDDEN_CONSUMER_KEYS or any(
                fragment in lowered
                for fragment in FORBIDDEN_CONSUMER_KEY_FRAGMENTS
            ):
                raise ProjectionError(f"消费视图出现禁带字段：{key}")
        if isinstance(value, str) and ANCHOR_ID_PATTERN.search(value):
            raise ProjectionError("消费视图出现锚 identity_key，证据层发生泄漏。")


def build_views(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    parts = collect_projectable_parts(document)
    views = {
        "timeline": build_timeline_view(parts),
        "causal_candidates": build_causal_view(parts),
        "character_state_candidates": build_character_state_view(parts),
        "unresolved": build_unresolved_view(parts),
    }
    for view in views.values():
        assert_consumer_view_clean(view)
    return views


def build_contract() -> dict[str, Any]:
    return {
        "schema_version": "z99-four-views-projection-contract-v0.1",
        "status": "candidate_contract_not_active",
        "task": "Z99_external_finalization_supply_20260724",
        "source_lock": {
            "path": SOURCE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_SOURCE_SHA256,
            "gold_id": EXPECTED_GOLD_ID,
            "required_status": EXPECTED_SOURCE_STATUS,
            "excluded_substitutes": [
                "Z97 旧 RFU/UCR ledger",
                "正式 Z73 文件或指针",
            ],
        },
        "eligibility": {
            "rule": "只投影 layered_items[].parts[] 中存在 rfu 对象的 part",
            "expected_projectable_part_count": EXPECTED_PROJECTABLE_PART_COUNT,
            "expected_unresolved_count": EXPECTED_UNRESOLVED_COUNT,
        },
        "views": {
            "timeline": {
                "ordering_basis": "narrative_order_proxy_from_source_array_only",
                "time_basis": "required_qualifiers_with_explicit_time_mapping_only",
                "clock_time_inference": "forbidden",
            },
            "causal_candidates": {
                "allowed_dimensions": sorted(CAUSAL_DIMENSIONS),
                "basis": "same_part_explicit_required_qualifier_only",
                "adjacent_fact_inference": "forbidden",
                "candidate_is_confirmed_causality": False,
            },
            "character_state_candidates": {
                "grouping": "exact_fact_head_subject_string",
                "alias_merge": "forbidden",
                "joint_subject_split": "forbidden",
                "current_state_claim": "forbidden",
            },
            "unresolved": {
                "selection": "fact_head.actuality == unresolved",
                "lexical_or_position_guess": "forbidden",
                "expected_count": EXPECTED_UNRESOLVED_COUNT,
            },
        },
        "qualifier_type_normalization": {
            "rule": (
                "type_original 与 value 必须原样保留；normalized_dimensions "
                "只是并列显式映射，不能替换或删除中文、英文或复合类型。"
            ),
            "unknown_type_behavior": "reject_before_projection_no_silent_drop",
            "mapping": {
                key: list(value)
                for key, value in sorted(QUALIFIER_TYPE_DIMENSIONS.items())
            },
        },
        "consumer_separation": {
            "forbidden_keys": sorted(FORBIDDEN_CONSUMER_KEYS),
            "forbidden_key_fragments": list(
                FORBIDDEN_CONSUMER_KEY_FRAGMENTS
            ),
            "anchor_identity_pattern_forbidden": ANCHOR_ID_PATTERN.pattern,
            "full_audit_material_location": AUDIT_SIDECAR_FILENAME,
        },
        "audit_sidecar": {
            "preservation": "full_source_document_semantic_copy",
            "byte_identity_anchor": "source_lock.path + source_lock.sha256",
            "consumer_status": "not_a_consumer_view",
        },
        "quality_boundary": (
            "四视图只是对候选 UCR 回包的离线确定性供料，不是正式金标、"
            "不是当前事实图、不是质量评分，也不接生产 runner。"
        ),
        "execution_boundary": {
            "model_api_calls": 0,
            "network_requests": 0,
            "formal_gold_mutations": 0,
        },
    }


def build_combined_sample(
    views: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    combined = {
        "schema_version": "z99-four-views-candidate-sample-v0.1",
        "status": "candidate_projection_not_active",
        "source_lock": {
            "sha256": EXPECTED_SOURCE_SHA256,
            "gold_id": EXPECTED_GOLD_ID,
        },
        "quality_boundary": (
            "离线候选四视图；不代表正式金标、确定因果、人物当前态或生产启用。"
        ),
        "views": copy.deepcopy(dict(views)),
    }
    assert_consumer_view_clean(combined)
    return combined


def build_audit_sidecar(
    document: Mapping[str, Any],
    parts: Sequence[Mapping[str, Any]],
    views: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    causal_ids = {
        candidate["source_part_id"]
        for candidate in views["causal_candidates"]["candidates"]
    }
    unresolved_ids = {
        entry["part_id"] for entry in views["unresolved"]["entries"]
    }
    trace = []
    for part in parts:
        trace.append(
            {
                "part_id": part["part_id"],
                "narrative_order_proxy": part["narrative_order_proxy"],
                "included_in": {
                    "timeline": True,
                    "causal_candidates": part["part_id"] in causal_ids,
                    "character_state_candidates": True,
                    "unresolved": part["part_id"] in unresolved_ids,
                },
            }
        )
    return {
        "schema_version": "z99-four-views-audit-sidecar-v0.1",
        "status": "audit_only_not_consumer_view",
        "source_lock": {
            "path": SOURCE_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_SOURCE_SHA256,
        },
        "preservation": {
            "mode": "full_source_document_semantic_copy",
            "statement": (
                "源 JSON 的全部字段和值完整保留在 source_document；"
                "原文件逐字身份由锁定路径与 SHA256 证明。"
            ),
        },
        "projection_trace": trace,
        "source_document": copy.deepcopy(dict(document)),
    }


def _fact_head_text(fact_head: Mapping[str, Any]) -> str:
    return (
        f"{fact_head['subject']}｜{fact_head['predicate']}｜"
        f"{fact_head['object']}｜结果：{fact_head['result']}｜"
        f"实际性：{fact_head['actuality']}"
    )


def _escape_md(value: object) -> str:
    return str(value).replace("|", "｜").replace("\n", " ")


def _qualifier_text(qualifiers: Sequence[Mapping[str, Any]]) -> str:
    if not qualifiers:
        return "无（不补推）"
    return "；".join(
        f"{row['type_original']}={row['value']}"
        for row in qualifiers
    )


def build_markdown_sample(views: Mapping[str, Mapping[str, Any]]) -> str:
    timeline = views["timeline"]
    causal = views["causal_candidates"]
    character = views["character_state_candidates"]
    unresolved = views["unresolved"]
    lines = [
        "# 第99道·章级事实图四视图候选样张",
        "",
        "✅ 这只是指定 UCR 候选回包的离线投影，不是正式金标，"
        "也没有接入生产链。",
        "",
        "🔥 时间线只认源数组顺序代理和明写的时间类限定；"
        "因果栏只收同条事实内明写的条件、目的或动机。",
        "",
        "## 时间线候选",
        "",
        "| 叙述顺序代理 | 原子件 | 事实头 | 明写时间限定 |",
        "|---:|---|---|---|",
    ]
    for entry in timeline["entries"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(entry["narrative_order_proxy"]),
                    _escape_md(entry["part_id"]),
                    _escape_md(_fact_head_text(entry["fact_head"])),
                    _escape_md(
                        _qualifier_text(entry["explicit_time_qualifiers"])
                    ),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "⚠️ 上表的数字只是源数组位置，不是故事内钟表时间，"
            "有空档也不代表中间漏了事件。",
            "",
            "## 条件／目的／动机候选",
            "",
            "| 候选 | 原子件 | 明写关系 | 明写限定 | 所属事实 |",
            "|---|---|---|---|---|",
        ]
    )
    for candidate in causal["candidates"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    candidate["candidate_id"],
                    candidate["source_part_id"],
                    "／".join(candidate["relation_dimensions"]),
                    _escape_md(_qualifier_text([candidate["explicit_qualifier"]])),
                    _escape_md(
                        _fact_head_text(candidate["scoped_fact_head"])
                    ),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "⚠️ 这里没有把相邻原子件首尾相接，也没有把“候选”写成确定因果。",
            "",
            "## 人物事实候选",
            "",
            "分组只看事实头里的主语原字符串。联合主语不拆，别名不合并；"
            "这里也不声称这些是人物当前态。",
            "",
        ]
    )
    for group in character["subject_groups"]:
        lines.extend(
            [
                f"### {_escape_md(group['subject_original'])}",
                "",
                "| 叙述顺序代理 | 原子件 | 事实候选 |",
                "|---:|---|---|",
            ]
        )
        for entry in group["fact_candidates"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(entry["narrative_order_proxy"]),
                        entry["part_id"],
                        _escape_md(_fact_head_text(entry["fact_head"])),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(
        [
            "## 未决候选",
            "",
            "这里只收事实头实际性逐字等于 `unresolved` 的原子件。",
            "",
            "| 叙述顺序代理 | 原子件 | 未决事实 | 必要限定 |",
            "|---:|---|---|---|",
        ]
    )
    for entry in unresolved["entries"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(entry["narrative_order_proxy"]),
                    entry["part_id"],
                    _escape_md(_fact_head_text(entry["fact_head"])),
                    _escape_md(_qualifier_text(entry["required_qualifiers"])),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"✅ 本样张未决候选共 {unresolved['counts']['entry_count']} 条。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def build_acceptance_receipt(
    views: Mapping[str, Mapping[str, Any]],
) -> str:
    timeline_count = views["timeline"]["counts"]["entry_count"]
    time_count = views["timeline"]["counts"]["explicit_time_qualifier_count"]
    causal_count = views["causal_candidates"]["counts"]["candidate_count"]
    subject_count = views["character_state_candidates"]["counts"][
        "subject_group_count"
    ]
    unresolved_count = views["unresolved"]["counts"]["entry_count"]
    return "\n".join(
        [
            "# 第99道·四视图候选供料验收票",
            "",
            "✅ 结论：离线四视图候选供料可复现，仍是候选，不接正式金标或生产链。",
            "",
            f"- 锁定输入：`{SOURCE_RELATIVE_PATH.as_posix()}`",
            f"- 输入 SHA256：`{EXPECTED_SOURCE_SHA256}`",
            f"- 时间线候选：{timeline_count} 条；明写时间类限定：{time_count} 个",
            f"- 条件／目的／动机候选：{causal_count} 个",
            f"- 人物主语原字符串分组：{subject_count} 组",
            f"- 未决候选：{unresolved_count} 条",
            "- 模型 API 调用：0",
            "- 网络请求：0",
            "- 正式金标、当前指针、治理账、运行账改动：0",
            "",
            "⚠️ 时间线没有推钟表时间；因果栏没有从相邻事实补关系；"
            "人物栏没有合并别名，也没有冒充当前态。消费样张与完整审计 sidecar 分开。",
            "",
            "来源：Codex",
            "",
        ]
    )


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(path: Path, value: object) -> None:
    _write_bytes(path, stable_json_bytes(value))


def _artifact_row(output_dir: Path, filename: str) -> dict[str, Any]:
    path = output_dir / filename
    return {
        "path": filename,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_bundle(
    output_dir: Path | None = None,
    *,
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Build all Z99 four-view artifacts and return the manifest."""

    output = output_dir or (REPO_ROOT / DEFAULT_OUTPUT_RELATIVE_PATH)
    document, source_raw = load_locked_source(source_path)
    _validate_source_identity(document)
    parts = collect_projectable_parts(document)
    views = build_views(document)
    contract = build_contract()
    combined = build_combined_sample(views)
    sidecar = build_audit_sidecar(document, parts, views)
    markdown_sample = build_markdown_sample(views)
    receipt = build_acceptance_receipt(views)

    _write_json(output / CONTRACT_FILENAME, contract)
    _write_json(output / COMBINED_SAMPLE_FILENAME, combined)
    _write_json(output / TIMELINE_FILENAME, views["timeline"])
    _write_json(output / CAUSAL_FILENAME, views["causal_candidates"])
    _write_json(
        output / CHARACTER_STATE_FILENAME,
        views["character_state_candidates"],
    )
    _write_json(output / UNRESOLVED_FILENAME, views["unresolved"])
    _write_bytes(output / MARKDOWN_SAMPLE_FILENAME, markdown_sample.encode("utf-8"))
    _write_json(output / AUDIT_SIDECAR_FILENAME, sidecar)
    _write_bytes(
        output / ACCEPTANCE_RECEIPT_FILENAME,
        receipt.encode("utf-8"),
    )

    artifact_names = [
        CONTRACT_FILENAME,
        COMBINED_SAMPLE_FILENAME,
        TIMELINE_FILENAME,
        CAUSAL_FILENAME,
        CHARACTER_STATE_FILENAME,
        UNRESOLVED_FILENAME,
        MARKDOWN_SAMPLE_FILENAME,
        AUDIT_SIDECAR_FILENAME,
        ACCEPTANCE_RECEIPT_FILENAME,
    ]
    manifest = {
        "schema_version": "z99-four-views-artifact-manifest-v0.1",
        "status": "candidate_bundle_not_active",
        "task": "Z99_external_finalization_supply_20260724",
        "source_lock": {
            "path": SOURCE_RELATIVE_PATH.as_posix(),
            "sha256": sha256_bytes(source_raw),
            "bytes": len(source_raw),
            "gold_id": EXPECTED_GOLD_ID,
            "source_status": EXPECTED_SOURCE_STATUS,
        },
        "generator": {
            "path": "tools/z99_chapter_fact_graph_projection.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "counts": {
            "projectable_part_count": len(parts),
            "timeline_entry_count": views["timeline"]["counts"]["entry_count"],
            "explicit_time_qualifier_count": views["timeline"]["counts"][
                "explicit_time_qualifier_count"
            ],
            "causal_candidate_count": views["causal_candidates"]["counts"][
                "candidate_count"
            ],
            "subject_group_count": views["character_state_candidates"]["counts"][
                "subject_group_count"
            ],
            "unresolved_count": views["unresolved"]["counts"]["entry_count"],
        },
        "execution": {
            "model_api_calls": 0,
            "network_requests": 0,
            "formal_gold_mutations": 0,
            "current_or_governance_mutations": 0,
        },
        "quality_boundary": (
            "候选四视图离线供料；不代表正式金标、质量胜负、确定因果、"
            "人物当前态或生产启用。"
        ),
        "artifact_hash_scope": (
            "下列文件；manifest 自身不进入哈希清单，避免递归自哈希。"
        ),
        "artifacts": [
            _artifact_row(output, filename) for filename in artifact_names
        ],
    }
    _write_json(output / MANIFEST_FILENAME, manifest)
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="离线生成第99道章级事实图四视图候选供料。"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / DEFAULT_OUTPUT_RELATIVE_PATH,
        help="输出目录；输入始终锁死为指定 UCR 回包。",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    manifest = build_bundle(args.output_dir)
    result = {
        "status": "PASS",
        "output_dir": str(args.output_dir),
        "manifest_sha256": sha256_file(args.output_dir / MANIFEST_FILENAME),
        "source_sha256": manifest["source_lock"]["sha256"],
        "counts": manifest["counts"],
        "model_api_calls": 0,
        "network_requests": 0,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
