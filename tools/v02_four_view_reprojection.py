#!/usr/bin/env python3
"""Offline v0.2 reprojection of the two locked X01 four-view samples.

The tool is deliberately narrow:

* it reads two byte-locked local samples;
* it performs no model/API/network call;
* it keeps one fact library and projects four consumer indexes from it;
* it never mutates formal gold, defaults, governance, or source inputs.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_RELATIVE_PATH = Path(
    "experiments/extraction_redesign_v02_overnight_20260725/"
    "B1_four_view_reprojection"
)

Z99_SAMPLE_RELATIVE_PATH = Path(
    "experiments/Z99_external_finalization_supply_20260724/"
    "four_views/four_views_candidate_sample.json"
)
Z99_SIDECAR_RELATIVE_PATH = Path(
    "experiments/Z99_external_finalization_supply_20260724/"
    "four_views/four_views_audit_sidecar.json"
)
Z99_MANIFEST_RELATIVE_PATH = Path(
    "experiments/Z99_external_finalization_supply_20260724/"
    "four_views/manifest.json"
)
D_SAMPLE_RELATIVE_PATH = Path(
    "TEMP/extract_chain_consult_3win_20260724/"
    "00_shared/D_x01_four_view_projection_sample.json"
)
D_W1_MIRROR_RELATIVE_PATH = Path(
    "TEMP/extract_chain_consult_3win_20260724/"
    "W1_Q1_Q6_granularity/attachments/"
    "D_x01_four_view_projection_sample.json"
)

EXPECTED_INPUT_SHA256 = {
    "z99_sample": "6c00808f4d522791b0c4324ebe0a62d2a91de355e56412047119d887510c08c0",
    "z99_sidecar": "4dc8cf030a88ef775a5b96d4610216c00ba12d01d0bff99d75d42f4367db6f1a",
    "z99_manifest": "b2f490deb72f62cbdd427c87741c4dddba751d6443626846e92672b1c65eea80",
    "d_sample": "381fa7ce0655b72efdfad2408d517450e02afef9f387139fa80fedaadd277635",
    "d_w1_mirror": "381fa7ce0655b72efdfad2408d517450e02afef9f387139fa80fedaadd277635",
}

EXPECTED_FACT_IDS = (
    "GOLD-C0003-01-N01",
    "GOLD-C0003-02-N01",
    "GOLD-C0003-03-N01",
    "GOLD-C0003-04-N01",
    "GOLD-C0003-05-N01",
    "GOLD-C0003-06-N01",
    "GOLD-C0003-07-N01",
    "GOLD-C0003-08-N01",
    "GOLD-C0003-09-N01",
    "GOLD-C0003-09-N02",
    "GOLD-C0003-09-N03",
    "GOLD-C0003-09-N04",
    "GOLD-C0003-09-N05",
    "GOLD-C0003-10-N01",
    "GOLD-C0003-10-N02",
    "GOLD-C0003-11-N01",
    "GOLD-C0003-11-N02",
    "GOLD-C0003-11-N03",
    "GOLD-C0003-12-N01",
    "GOLD-C0003-12-N02",
    "GOLD-C0003-12-N03",
    "GOLD-C0003-13-N01",
    "GOLD-C0003-14-N01",
)

Z99_OUTPUT_FILENAME = "z99_four_views_reprojected_v02.json"
Z99_SIDECAR_OUTPUT_FILENAME = "z99_four_views_reprojected_v02_sidecar.json"
D_OUTPUT_FILENAME = "sample_d_four_views_reprojected_v02.json"
D_SIDECAR_OUTPUT_FILENAME = "sample_d_four_views_reprojected_v02_sidecar.json"
COMPARISON_FILENAME = "before_after_comparison.json"
MANIFEST_FILENAME = "manifest.json"

STATE_SLOTS = frozenset(
    {
        "knowledge",
        "belief",
        "goal",
        "plan",
        "physical",
        "emotion_attention",
        "role_relation",
        "resource",
        "location",
        "constraint",
        "habit_skill",
    }
)
CAUSAL_RELATIONS = frozenset(
    {"cause", "trigger", "condition", "motive", "enable", "prevent"}
)
ISSUE_TYPES = frozenset({"question", "task", "promise", "risk"})
ISSUE_STATUSES = frozenset({"open", "updated", "resolved", "invalidated"})

RATIO_RANGES_PERCENT = {
    "timeline": (40.0, 55.0),
    "causal": (20.0, 30.0),
    "character_state": (25.0, 40.0),
    "unresolved": (5.0, 20.0),
}
TOTAL_PROJECTION_MULTIPLE_RANGE = (1.1, 1.5)

TIMELINE_PLAN = (
    {
        "fact_id": "GOLD-C0003-01-N01",
        "scene_id": "S01",
        "beat_type": "revelation",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-02-N01",
        "scene_id": "S01",
        "beat_type": "trigger",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-03-N01",
        "scene_id": "S01",
        "beat_type": "action_result",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-04-N01",
        "scene_id": "S01",
        "beat_type": "state_change",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-05-N01",
        "scene_id": "S01",
        "beat_type": "action_result",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-06-N01",
        "scene_id": "S01",
        "beat_type": "decision_plan",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-07-N01",
        "scene_id": "S01",
        "beat_type": "action_result",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-08-N01",
        "scene_id": "S01",
        "beat_type": "state_change",
        "time_ref_fact_id": "GOLD-C0003-07-N01",
    },
    {
        "fact_id": "GOLD-C0003-09-N01",
        "scene_id": "S02",
        "beat_type": "revelation",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-10-N01",
        "scene_id": "S02",
        "beat_type": "revelation",
        "time_ref_fact_id": None,
    },
    {
        "fact_id": "GOLD-C0003-10-N02",
        "scene_id": "S02",
        "beat_type": "state_change",
        "time_ref_fact_id": None,
    },
)

CAUSAL_PLAN = (
    {
        "edge_id": "CE-C0003-001",
        "from_fact_ids": ["GOLD-C0003-02-N01"],
        "to_fact_id": "GOLD-C0003-03-N01",
        "relation": "trigger",
        "basis": "explicit",
        "modal": "asserted",
    },
    {
        "edge_id": "CE-C0003-002",
        "from_fact_ids": [
            "GOLD-C0003-09-N01",
            "GOLD-C0003-10-N01",
        ],
        "to_fact_id": "GOLD-C0003-10-N02",
        "relation": "condition",
        "basis": "explicit",
        "modal": "恐怕",
    },
)

ZHOU_KNOWS_INTERVIEW = "知道两天后要参加廷根大学历史系面试"
ZHOU_KNOWS_MEMORY_GAPS = (
    "知道两天后要参加廷根大学历史系面试；"
    "知道克莱恩的记忆失去连贯且多处缺失"
)
ZHOU_KNOWS_MEMORY_AND_KNOWLEDGE_GAPS = (
    "知道两天后要参加廷根大学历史系面试；"
    "知道克莱恩的记忆与知识均碎片化并残缺"
)

STATE_PLAN = (
    {
        "entry_id": "CS-C0003-001",
        "fact_id": "GOLD-C0003-01-N01",
        "character_id": "周明瑞",
        "state_slot": "knowledge",
        "before": "unknown",
        "delta": "set",
        "after": ZHOU_KNOWS_INTERVIEW,
        "persistence": "open",
        "previous_entry_id": None,
    },
    {
        "entry_id": "CS-C0003-002",
        "fact_id": "GOLD-C0003-04-N01",
        "character_id": "周明瑞",
        "state_slot": "physical",
        "before": "unknown",
        "delta": "set",
        "after": "太阳穴位置的伤口已经愈合",
        "persistence": "open",
        "previous_entry_id": None,
    },
    {
        "entry_id": "CS-C0003-003",
        "fact_id": "GOLD-C0003-08-N01",
        "character_id": "周明瑞",
        "state_slot": "emotion_attention",
        "before": "unknown",
        "delta": "shift",
        "after": "把注意力转到转运仪式",
        "persistence": "scene",
        "previous_entry_id": None,
    },
    {
        "entry_id": "CS-C0003-004",
        "fact_id": "GOLD-C0003-09-N01",
        "character_id": "周明瑞",
        "state_slot": "knowledge",
        "before": ZHOU_KNOWS_INTERVIEW,
        "delta": "add",
        "after": ZHOU_KNOWS_MEMORY_GAPS,
        "persistence": "open",
        "previous_entry_id": "CS-C0003-001",
    },
    {
        "entry_id": "CS-C0003-005",
        "fact_id": "GOLD-C0003-10-N01",
        "character_id": "周明瑞",
        "state_slot": "knowledge",
        "before": ZHOU_KNOWS_MEMORY_GAPS,
        "delta": "expand",
        "after": ZHOU_KNOWS_MEMORY_AND_KNOWLEDGE_GAPS,
        "persistence": "open",
        "previous_entry_id": "CS-C0003-004",
    },
    {
        "entry_id": "CS-C0003-006",
        "fact_id": "GOLD-C0003-10-N02",
        "character_id": "周明瑞",
        "state_slot": "belief",
        "before": "unknown",
        "delta": "set",
        "after": "相信以当前状态回到大学恐怕无法毕业",
        "persistence": "open",
        "previous_entry_id": None,
    },
    {
        "entry_id": "CS-C0003-007",
        "fact_id": "GOLD-C0003-11-N01",
        "character_id": "梅丽莎",
        "state_slot": "goal",
        "before": "unknown",
        "delta": "set",
        "after": "立志成为蒸汽机械师",
        "persistence": "open",
        "previous_entry_id": None,
    },
    {
        "entry_id": "CS-C0003-008",
        "fact_id": "GOLD-C0003-12-N01",
        "character_id": "班森",
        "state_slot": "constraint",
        "before": "unknown",
        "delta": "set",
        "after": "为保住工作和维持生活，必须接受繁重任务并经常加班或出差",
        "persistence": "open",
        "previous_entry_id": None,
    },
    {
        "entry_id": "CS-C0003-009",
        "fact_id": "GOLD-C0003-14-N01",
        "character_id": "梅丽莎",
        "state_slot": "habit_skill",
        "before": "unknown",
        "delta": "set",
        "after": "为省车费，平时提前出门并步行约五十分钟上学",
        "persistence": "open",
        "previous_entry_id": None,
    },
)

UNRESOLVED_PLAN = (
    {
        "fact_id": "GOLD-C0003-09-N02",
        "issue_id": "IS-C0003-09-N02",
        "issue_type": "question",
        "status": "open",
        "closure_condition": "形成可核验的转轮手枪来源结论",
    },
    {
        "fact_id": "GOLD-C0003-09-N03",
        "issue_id": "IS-C0003-09-N03",
        "issue_type": "question",
        "status": "open",
        "closure_condition": "确认克莱恩的死亡属于自杀、他杀或其他可核验结论",
    },
    {
        "fact_id": "GOLD-C0003-09-N04",
        "issue_id": "IS-C0003-09-N04",
        "issue_type": "question",
        "status": "open",
        "closure_condition": "形成可核验的笔记本句子含义解释",
    },
    {
        "fact_id": "GOLD-C0003-09-N05",
        "issue_id": "IS-C0003-09-N05",
        "issue_type": "question",
        "status": "open",
        "closure_condition": "确认克莱恩事发前两天是否参与过奇怪事情",
    },
)

SINGLE_ENDPOINT_CAUSAL_BACKLOG = (
    {
        "fact_id": "GOLD-C0003-02-N01",
        "qualifier": "里面房间的门吱呀打开后",
        "reason": "门打开没有独立计分事实端点，保留为原事实条件。",
    },
    {
        "fact_id": "GOLD-C0003-08-N01",
        "qualifier": "真的想回家",
        "reason": "动机没有独立计分事实端点，保留为原事实限定。",
    },
    {
        "fact_id": "GOLD-C0003-11-N02",
        "qualifier": "掌握理论知识后",
        "reason": "掌握理论知识没有独立计分事实端点，保留为原事实条件。",
    },
    {
        "fact_id": "GOLD-C0003-12-N01",
        "qualifier": "保住工作、维持生活",
        "reason": "目的没有独立计分事实端点，保留为原事实限定。",
    },
    {
        "fact_id": "GOLD-C0003-14-N01",
        "qualifier": "为了省车费/省钱",
        "reason": "目的没有独立计分事实端点，保留为原事实限定。",
    },
)

TIMELINE_EXCLUSION_BACKLOG = (
    {
        "fact_ids": [
            "GOLD-C0003-11-N01",
            "GOLD-C0003-11-N02",
            "GOLD-C0003-11-N03",
            "GOLD-C0003-12-N02",
            "GOLD-C0003-12-N03",
        ],
        "reason": (
            "这些条目是章内回顾的背景事实，输入没有给出足够的章内场景排序关系；"
            "不靠相邻顺序补成时间线节点。"
        ),
    },
)

FORBIDDEN_CONSUMER_KEYS = frozenset(
    {
        "anchor_id",
        "identity_key",
        "minimal_support_sets",
        "quote",
        "source_evidence",
        "source_short_quote",
    }
)


class ReprojectionError(ValueError):
    """Raised when a locked input or the v0.2 projection contract is violated."""


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


def _load_locked_json(
    relative_path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], bytes]:
    path = REPO_ROOT / relative_path
    raw = path.read_bytes()
    actual_sha256 = sha256_bytes(raw)
    if actual_sha256 != expected_sha256:
        raise ReprojectionError(
            "锁定输入 SHA 不匹配："
            f"expected={expected_sha256} actual={actual_sha256} path={path}"
        )
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReprojectionError(f"锁定输入不是合法 JSON：{path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ReprojectionError(f"锁定输入顶层必须是对象：{path}")
    return document, raw


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReprojectionError(f"{label} 必须是对象。")
    return value


def _require_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReprojectionError(f"{label} 必须是数组。")
    return value


def _normalise_qualifiers(
    qualifiers: object,
    *,
    type_key: str,
    label: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, value in enumerate(_require_list(qualifiers, label)):
        row = _require_mapping(value, f"{label}[{index}]")
        qualifier_type = row.get(type_key)
        qualifier_value = row.get("value")
        if not isinstance(qualifier_type, str) or not qualifier_type:
            raise ReprojectionError(f"{label}[{index}].{type_key} 必须是非空字符串。")
        if not isinstance(qualifier_value, str) or not qualifier_value:
            raise ReprojectionError(f"{label}[{index}].value 必须是非空字符串。")
        rows.append({"type": qualifier_type, "value": qualifier_value})
    return rows


def _source_part_map(sidecar: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    source_document = _require_mapping(
        sidecar.get("source_document"),
        "Z99 sidecar.source_document",
    )
    parts: dict[str, Mapping[str, Any]] = {}
    for item_index, item_value in enumerate(
        _require_list(source_document.get("layered_items"), "layered_items")
    ):
        item = _require_mapping(item_value, f"layered_items[{item_index}]")
        for part_index, part_value in enumerate(
            _require_list(item.get("parts"), f"layered_items[{item_index}].parts")
        ):
            part = _require_mapping(
                part_value,
                f"layered_items[{item_index}].parts[{part_index}]",
            )
            if part.get("rfu") is None:
                continue
            part_id = part.get("part_id")
            if not isinstance(part_id, str) or not part_id:
                raise ReprojectionError("Z99 sidecar 出现无效 part_id。")
            if part_id in parts:
                raise ReprojectionError(f"Z99 sidecar 的 part_id 重复：{part_id}")
            parts[part_id] = part
    return parts


def _z99_state_candidate_map(
    candidate: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    views = _require_mapping(candidate.get("views"), "Z99 candidate.views")
    state_view = _require_mapping(
        views.get("character_state_candidates"),
        "Z99 character_state_candidates",
    )
    rows: dict[str, Mapping[str, Any]] = {}
    for group_index, group_value in enumerate(
        _require_list(state_view.get("subject_groups"), "subject_groups")
    ):
        group = _require_mapping(group_value, f"subject_groups[{group_index}]")
        for row_index, row_value in enumerate(
            _require_list(
                group.get("fact_candidates"),
                f"subject_groups[{group_index}].fact_candidates",
            )
        ):
            row = _require_mapping(
                row_value,
                f"subject_groups[{group_index}].fact_candidates[{row_index}]",
            )
            part_id = row.get("part_id")
            if not isinstance(part_id, str) or not part_id:
                raise ReprojectionError("Z99 状态候选出现无效 part_id。")
            if part_id in rows:
                raise ReprojectionError(f"Z99 状态候选 part_id 重复：{part_id}")
            rows[part_id] = row
    return rows


def _extract_z99_facts(
    candidate: Mapping[str, Any],
    sidecar: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if candidate.get("schema_version") != "z99-four-views-candidate-sample-v0.1":
        raise ReprojectionError("Z99 输入 schema_version 发生漂移。")
    if candidate.get("status") != "candidate_projection_not_active":
        raise ReprojectionError("Z99 输入候选状态发生漂移。")

    views = _require_mapping(candidate.get("views"), "Z99 candidate.views")
    timeline = _require_mapping(views.get("timeline"), "Z99 timeline")
    timeline_entries = _require_list(timeline.get("entries"), "Z99 timeline.entries")
    timeline_ids = [row.get("part_id") for row in timeline_entries if isinstance(row, dict)]
    if len(timeline_ids) != len(timeline_entries):
        raise ReprojectionError("Z99 timeline 出现非对象条目。")
    if tuple(timeline_ids) != EXPECTED_FACT_IDS:
        raise ReprojectionError("Z99 timeline 的 23 个事实顺序或身份发生漂移。")

    source_parts = _source_part_map(sidecar)
    candidate_rows = _z99_state_candidate_map(candidate)
    if set(source_parts) != set(EXPECTED_FACT_IDS):
        raise ReprojectionError("Z99 sidecar 的 RFU 事实集合发生漂移。")
    if set(candidate_rows) != set(EXPECTED_FACT_IDS):
        raise ReprojectionError("Z99 状态候选事实集合发生漂移。")

    facts: list[dict[str, Any]] = []
    anchors_by_fact_id: dict[str, dict[str, Any]] = {}
    for source_order, fact_id in enumerate(EXPECTED_FACT_IDS, start=1):
        source_part = source_parts[fact_id]
        source_rfu = _require_mapping(source_part.get("rfu"), f"{fact_id}.rfu")
        candidate_row = candidate_rows[fact_id]
        source_fact_head = _require_mapping(
            source_rfu.get("fact_head"),
            f"{fact_id}.rfu.fact_head",
        )
        candidate_fact_head = _require_mapping(
            candidate_row.get("fact_head"),
            f"{fact_id}.candidate.fact_head",
        )
        if source_fact_head != candidate_fact_head:
            raise ReprojectionError(f"{fact_id} 的 Z99 事实头与 sidecar 不一致。")

        source_qualifiers = _normalise_qualifiers(
            source_rfu.get("required_qualifiers"),
            type_key="type",
            label=f"{fact_id}.rfu.required_qualifiers",
        )
        candidate_qualifiers = _normalise_qualifiers(
            candidate_row.get("required_qualifiers"),
            type_key="type_original",
            label=f"{fact_id}.candidate.required_qualifiers",
        )
        if source_qualifiers != candidate_qualifiers:
            raise ReprojectionError(f"{fact_id} 的 Z99 限定与 sidecar 不一致。")

        claim = source_part.get("claim")
        if not isinstance(claim, str) or not claim:
            raise ReprojectionError(f"{fact_id}.claim 必须是非空字符串。")
        facts.append(
            {
                "fact_id": fact_id,
                "source_order": source_order,
                "claim": claim,
                "fact_head": copy.deepcopy(dict(source_fact_head)),
                "qualifiers": source_qualifiers,
            }
        )
        anchors_by_fact_id[fact_id] = {
            "fact_id": fact_id,
            "minimal_support_sets": copy.deepcopy(
                source_rfu.get("minimal_support_sets", [])
            ),
            "source_evidence": copy.deepcopy(source_part.get("source_evidence", [])),
        }
    return facts, anchors_by_fact_id


def _extract_d_facts(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    if candidate.get("schema") != "chapter-fact-graph-four-view-sample-v0.1":
        raise ReprojectionError("样张 D 的 schema 发生漂移。")
    views = _require_mapping(candidate.get("views"), "样张 D.views")
    rows = _require_list(
        views.get("character_status_ledger"),
        "样张 D.character_status_ledger",
    )
    if len(rows) != len(EXPECTED_FACT_IDS):
        raise ReprojectionError("样张 D 的人物状态旧账不再是 23 条。")

    facts: list[dict[str, Any]] = []
    ids: list[str] = []
    for source_order, value in enumerate(rows, start=1):
        row = _require_mapping(value, f"character_status_ledger[{source_order - 1}]")
        fact_id = row.get("fact_id")
        claim = row.get("claim")
        if not isinstance(fact_id, str) or not fact_id:
            raise ReprojectionError("样张 D 出现无效 fact_id。")
        if not isinstance(claim, str) or not claim:
            raise ReprojectionError(f"{fact_id}.claim 必须是非空字符串。")
        ids.append(fact_id)
        facts.append(
            {
                "fact_id": fact_id,
                "source_order": source_order,
                "claim": claim,
                "fact_head": copy.deepcopy(
                    dict(_require_mapping(row.get("fact_head"), f"{fact_id}.fact_head"))
                ),
                "qualifiers": _normalise_qualifiers(
                    row.get("qualifiers_consumer"),
                    type_key="type",
                    label=f"{fact_id}.qualifiers_consumer",
                ),
            }
        )
    if tuple(ids) != EXPECTED_FACT_IDS:
        raise ReprojectionError("样张 D 的 23 个事实顺序或身份发生漂移。")
    return facts


def _fact_semantic_copy(facts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "fact_id": fact["fact_id"],
            "claim": copy.deepcopy(fact["claim"]),
            "fact_head": copy.deepcopy(fact["fact_head"]),
            "qualifiers": copy.deepcopy(fact["qualifiers"]),
        }
        for fact in facts
    ]


def load_locked_inputs() -> dict[str, Any]:
    z99_candidate, z99_candidate_raw = _load_locked_json(
        Z99_SAMPLE_RELATIVE_PATH,
        EXPECTED_INPUT_SHA256["z99_sample"],
    )
    z99_sidecar, z99_sidecar_raw = _load_locked_json(
        Z99_SIDECAR_RELATIVE_PATH,
        EXPECTED_INPUT_SHA256["z99_sidecar"],
    )
    z99_manifest, z99_manifest_raw = _load_locked_json(
        Z99_MANIFEST_RELATIVE_PATH,
        EXPECTED_INPUT_SHA256["z99_manifest"],
    )
    d_candidate, d_candidate_raw = _load_locked_json(
        D_SAMPLE_RELATIVE_PATH,
        EXPECTED_INPUT_SHA256["d_sample"],
    )

    d_w1_path = REPO_ROOT / D_W1_MIRROR_RELATIVE_PATH
    d_w1_raw = d_w1_path.read_bytes()
    d_w1_sha256 = sha256_bytes(d_w1_raw)
    if d_w1_sha256 != EXPECTED_INPUT_SHA256["d_w1_mirror"]:
        raise ReprojectionError(
            "样张 D 的 W1 附件镜像 SHA 不匹配："
            f"expected={EXPECTED_INPUT_SHA256['d_w1_mirror']} "
            f"actual={d_w1_sha256}"
        )
    if d_candidate_raw != d_w1_raw:
        raise ReprojectionError("样张 D 共享件与 W1 附件不是逐字相同镜像。")

    manifest_artifacts = {
        row.get("path"): row
        for row in _require_list(z99_manifest.get("artifacts"), "Z99 manifest.artifacts")
        if isinstance(row, dict)
    }
    expected_manifest_hashes = {
        "four_views_candidate_sample.json": EXPECTED_INPUT_SHA256["z99_sample"],
        "four_views_audit_sidecar.json": EXPECTED_INPUT_SHA256["z99_sidecar"],
    }
    for filename, expected_sha256 in expected_manifest_hashes.items():
        row = manifest_artifacts.get(filename)
        if row is None or row.get("sha256") != expected_sha256:
            raise ReprojectionError(f"Z99 manifest 没有正确锁定 {filename}。")

    z99_facts, z99_anchors = _extract_z99_facts(z99_candidate, z99_sidecar)
    d_facts = _extract_d_facts(d_candidate)
    if _fact_semantic_copy(z99_facts) != _fact_semantic_copy(d_facts):
        raise ReprojectionError("两份输入不再指向同一组 23 个计分原子。")

    return {
        "z99_candidate": z99_candidate,
        "z99_sidecar": z99_sidecar,
        "z99_manifest": z99_manifest,
        "d_candidate": d_candidate,
        "z99_facts": z99_facts,
        "d_facts": d_facts,
        "z99_anchors": z99_anchors,
        "raw": {
            "z99_sample": z99_candidate_raw,
            "z99_sidecar": z99_sidecar_raw,
            "z99_manifest": z99_manifest_raw,
            "d_sample": d_candidate_raw,
            "d_w1_mirror": d_w1_raw,
        },
    }


def _fact_map(facts: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    mapping = {str(fact["fact_id"]): fact for fact in facts}
    if len(mapping) != len(facts):
        raise ReprojectionError("事实库出现重复 fact_id。")
    return mapping


def _time_field(
    fact: Mapping[str, Any],
    *,
    ref_fact_id: str | None,
) -> dict[str, Any] | None:
    time_qualifiers = [
        qualifier
        for qualifier in _require_list(fact.get("qualifiers"), "fact.qualifiers")
        if isinstance(qualifier, dict) and "时间" in str(qualifier.get("type"))
    ]
    if not time_qualifiers:
        return None
    if len(time_qualifiers) > 1:
        raise ReprojectionError(
            f"{fact['fact_id']} 有多个时间限定，当前窄样本规则不能静默合并。"
        )
    qualifier = time_qualifiers[0]
    return {
        "kind": "relative",
        "value": qualifier["value"],
        "ref_fact_id": ref_fact_id,
        "precision": "source_exact",
    }


def _build_timeline(
    facts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = _fact_map(facts)
    rows: list[dict[str, Any]] = []
    for seq, plan in enumerate(TIMELINE_PLAN, start=1):
        fact_id = str(plan["fact_id"])
        fact = by_id[fact_id]
        rows.append(
            {
                "fact_id": fact_id,
                "seq": seq,
                "scene_id": plan["scene_id"],
                "storyline_id": None,
                "beat_type": plan["beat_type"],
                "time": _time_field(
                    fact,
                    ref_fact_id=plan["time_ref_fact_id"],
                ),
            }
        )
    return rows


def _build_character_states(
    facts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = _fact_map(facts)
    rows: list[dict[str, Any]] = []
    for plan in STATE_PLAN:
        fact_id = str(plan["fact_id"])
        actuality = _require_mapping(
            by_id[fact_id].get("fact_head"),
            f"{fact_id}.fact_head",
        ).get("actuality")
        if not isinstance(actuality, str) or not actuality:
            raise ReprojectionError(f"{fact_id}.fact_head.actuality 无效。")
        row = copy.deepcopy(dict(plan))
        row["actuality"] = actuality
        rows.append(row)
    return rows


def _build_unresolved(
    facts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = _fact_map(facts)
    rows: list[dict[str, Any]] = []
    for plan in UNRESOLVED_PLAN:
        fact_id = str(plan["fact_id"])
        fact = by_id[fact_id]
        fact_head = _require_mapping(fact.get("fact_head"), f"{fact_id}.fact_head")
        if fact_head.get("actuality") != "unresolved":
            raise ReprojectionError(f"{fact_id} 不再是 unresolved，拒绝旧规则套用。")
        row = copy.deepcopy(dict(plan))
        row.update(
            {
                "statement": fact["claim"],
                "storyline_id": None,
                "opened_by_fact_id": fact_id,
                "last_update_fact_id": fact_id,
                "resolved_by_fact_id": None,
                "actuality": "unresolved",
            }
        )
        rows.append(row)
    return rows


def _ratio_status(value: float, lower: float, upper: float) -> str:
    if value < lower:
        return "OUT_OF_RANGE_LOW"
    if value > upper:
        return "OUT_OF_RANGE_HIGH"
    return "PASS"


def _build_ratio_audit(counts: Mapping[str, int]) -> dict[str, Any]:
    denominator = counts["unique_facts"]
    ratios = {
        "timeline": round(counts["timeline_nodes"] * 100 / denominator, 4),
        "causal": round(counts["causal_edges"] * 100 / denominator, 4),
        "character_state": round(
            counts["character_state_updates"] * 100 / denominator,
            4,
        ),
        "unresolved": round(counts["unresolved_items"] * 100 / denominator, 4),
    }
    statuses = {
        key: _ratio_status(value, *RATIO_RANGES_PERCENT[key])
        for key, value in ratios.items()
    }
    projection_multiple = round(
        counts["total_projection_rows"] / denominator,
        4,
    )
    multiple_status = _ratio_status(
        projection_multiple,
        *TOTAL_PROJECTION_MULTIPLE_RANGE,
    )
    backlog: list[dict[str, Any]] = []
    if statuses["causal"] != "PASS":
        backlog.append(
            {
                "view": "causal",
                "status": statuses["causal"],
                "actual_percent": ratios["causal"],
                "reason": (
                    "锁定事实库中只找到两组“独立事实端点＋显式关系”；"
                    "其余五个单端条件或目的继续留在 qualifier，不补推边。"
                ),
            }
        )
    return {
        "denominator": {
            "name": "unique_scoring_atoms",
            "value": denominator,
        },
        "expected_percent_ranges": {
            key: {"min": bounds[0], "max": bounds[1]}
            for key, bounds in RATIO_RANGES_PERCENT.items()
        },
        "actual_percent": ratios,
        "status": statuses,
        "total_projection_multiple": projection_multiple,
        "expected_total_projection_multiple": {
            "min": TOTAL_PROJECTION_MULTIPLE_RANGE[0],
            "max": TOTAL_PROJECTION_MULTIPLE_RANGE[1],
        },
        "total_projection_multiple_status": multiple_status,
        "backlog": backlog,
    }


def build_outline(
    *,
    source_sample_id: str,
    facts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    timeline = _build_timeline(facts)
    causal_edges = copy.deepcopy(list(CAUSAL_PLAN))
    character_states = _build_character_states(facts)
    unresolved_items = _build_unresolved(facts)
    counts = {
        "unique_facts": len(facts),
        "timeline_nodes": len(timeline),
        "causal_edges": len(causal_edges),
        "character_state_updates": len(character_states),
        "unresolved_items": len(unresolved_items),
        "total_projection_rows": (
            len(timeline)
            + len(causal_edges)
            + len(character_states)
            + len(unresolved_items)
        ),
    }
    outline = {
        "schema": "chapter-fact-graph-outline-v1",
        "status": "candidate_reprojection_not_active",
        "chapter_id": "C0003",
        "density_class": "not_assessed",
        "source_sample_id": source_sample_id,
        "projection_policy": "extraction-redesign-v0.2-section-2",
        "quality_boundary": (
            "离线机械重投影候选；不是正式金标，不启用默认路由，"
            "不把推断边混入显式因果边。"
        ),
        "facts": copy.deepcopy(list(facts)),
        "views": {
            "timeline": timeline,
            "causal_edges": causal_edges,
            "character_states": character_states,
            "unresolved_items": unresolved_items,
            "inference_edges": {
                "non_gold": True,
                "default_visible": False,
                "items": [],
            },
        },
        "counts": counts,
        "ratio_audit": _build_ratio_audit(counts),
    }
    validate_outline(outline)
    return outline


def _nested_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(key)
            keys.extend(_nested_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_nested_keys(child))
    return keys


def validate_outline(outline: Mapping[str, Any]) -> None:
    if outline.get("schema") != "chapter-fact-graph-outline-v1":
        raise ReprojectionError("消费包 schema 不正确。")
    facts = _require_list(outline.get("facts"), "outline.facts")
    fact_ids = {
        fact.get("fact_id")
        for fact in facts
        if isinstance(fact, Mapping)
    }
    if len(fact_ids) != len(facts) or tuple(
        fact.get("fact_id") for fact in facts if isinstance(fact, Mapping)
    ) != EXPECTED_FACT_IDS:
        raise ReprojectionError("消费包事实库不是锁定的 23 个唯一计分原子。")

    views = _require_mapping(outline.get("views"), "outline.views")
    consumer_view_names = (
        "timeline",
        "causal_edges",
        "character_states",
        "unresolved_items",
    )
    for view_name in consumer_view_names:
        for row in _require_list(views.get(view_name), f"views.{view_name}"):
            mapping = _require_mapping(row, f"views.{view_name}[]")
            row_refs: list[object]
            if view_name == "causal_edges":
                row_refs = [
                    *_require_list(
                        mapping.get("from_fact_ids"),
                        "causal_edge.from_fact_ids",
                    ),
                    mapping.get("to_fact_id"),
                ]
            else:
                row_refs = [mapping.get("fact_id")]
            if any(reference not in fact_ids for reference in row_refs):
                raise ReprojectionError(f"{view_name} 出现悬空 fact_id。")
            forbidden = FORBIDDEN_CONSUMER_KEYS.intersection(_nested_keys(mapping))
            if forbidden:
                raise ReprojectionError(
                    f"{view_name} 泄漏锚或审计字段：{sorted(forbidden)}"
                )
            if {"claim", "fact_head", "qualifiers"}.intersection(mapping):
                raise ReprojectionError(f"{view_name} 重复携带事实正文。")

    causal_edges = _require_list(views.get("causal_edges"), "views.causal_edges")
    edge_ids: set[object] = set()
    for edge in causal_edges:
        mapping = _require_mapping(edge, "causal_edge")
        edge_id = mapping.get("edge_id")
        if edge_id in edge_ids:
            raise ReprojectionError(f"因果 edge_id 重复：{edge_id}")
        edge_ids.add(edge_id)
        from_ids = _require_list(mapping.get("from_fact_ids"), "from_fact_ids")
        if not from_ids or not mapping.get("to_fact_id"):
            raise ReprojectionError("因果边必须同时有 from 与 to。")
        if mapping.get("relation") not in CAUSAL_RELATIONS:
            raise ReprojectionError("因果边 relation 不在 v0.2 枚举中。")
        if mapping.get("basis") != "explicit":
            raise ReprojectionError("默认因果边只允许 basis=explicit。")

    state_rows = _require_list(
        views.get("character_states"),
        "views.character_states",
    )
    by_entry_id = {
        row.get("entry_id"): row
        for row in state_rows
        if isinstance(row, Mapping)
    }
    if len(by_entry_id) != len(state_rows):
        raise ReprojectionError("人物状态 entry_id 重复。")
    for row_value in state_rows:
        row = _require_mapping(row_value, "character_state")
        if row.get("state_slot") not in STATE_SLOTS:
            raise ReprojectionError("人物状态槽不在 v0.2 枚举中。")
        for required in (
            "character_id",
            "before",
            "delta",
            "after",
            "actuality",
        ):
            if not isinstance(row.get(required), str) or not row.get(required):
                raise ReprojectionError(f"人物状态缺少有效 {required}。")
        previous_entry_id = row.get("previous_entry_id")
        if previous_entry_id is None:
            continue
        previous = by_entry_id.get(previous_entry_id)
        if previous is None:
            raise ReprojectionError("人物状态 previous_entry_id 悬空。")
        if (
            previous.get("character_id") != row.get("character_id")
            or previous.get("state_slot") != row.get("state_slot")
            or previous.get("after") != row.get("before")
        ):
            raise ReprojectionError("人物状态前值连续性断裂。")

    unresolved_rows = _require_list(
        views.get("unresolved_items"),
        "views.unresolved_items",
    )
    issue_ids: set[object] = set()
    for row_value in unresolved_rows:
        row = _require_mapping(row_value, "unresolved_item")
        if row.get("issue_id") in issue_ids:
            raise ReprojectionError("未决 issue_id 重复。")
        issue_ids.add(row.get("issue_id"))
        if row.get("issue_type") not in ISSUE_TYPES:
            raise ReprojectionError("未决 issue_type 不在 v0.2 枚举中。")
        if row.get("status") not in ISSUE_STATUSES:
            raise ReprojectionError("未决 status 不在 v0.2 枚举中。")
        if not isinstance(row.get("closure_condition"), str):
            raise ReprojectionError("未决事项必须写明回收条件。")

    inference = _require_mapping(
        views.get("inference_edges"),
        "views.inference_edges",
    )
    if (
        inference.get("non_gold") is not True
        or inference.get("default_visible") is not False
        or inference.get("items") != []
    ):
        raise ReprojectionError("inference_edges 没有按 non_gold 隔离。")

    counts = _require_mapping(outline.get("counts"), "outline.counts")
    expected_counts = {
        "unique_facts": 23,
        "timeline_nodes": 11,
        "causal_edges": 2,
        "character_state_updates": 9,
        "unresolved_items": 4,
        "total_projection_rows": 26,
    }
    if counts != expected_counts:
        raise ReprojectionError(
            f"v0.2 重投影读数发生漂移：expected={expected_counts} actual={counts}"
        )


def _old_counts_for_z99(candidate: Mapping[str, Any]) -> dict[str, int]:
    views = _require_mapping(candidate.get("views"), "Z99 views")
    return {
        "unique_facts": 23,
        "timeline_nodes": int(
            _require_mapping(views.get("timeline"), "Z99 timeline")
            .get("counts", {})
            .get("entry_count")
        ),
        "causal_rows_not_edges": int(
            _require_mapping(
                views.get("causal_candidates"),
                "Z99 causal_candidates",
            )
            .get("counts", {})
            .get("candidate_count")
        ),
        "character_state_rows": int(
            _require_mapping(
                views.get("character_state_candidates"),
                "Z99 character_state_candidates",
            )
            .get("counts", {})
            .get("fact_candidate_count")
        ),
        "unresolved_items": int(
            _require_mapping(views.get("unresolved"), "Z99 unresolved")
            .get("counts", {})
            .get("entry_count")
        ),
    }


def _old_counts_for_d(candidate: Mapping[str, Any]) -> dict[str, int]:
    counts = _require_mapping(candidate.get("counts"), "样张 D.counts")
    return {
        "unique_facts": 23,
        "timeline_nodes": int(counts["timeline"]),
        "causal_rows_not_edges": int(counts["causal_chain"]),
        "character_state_rows": int(counts["character_status_ledger"]),
        "unresolved_items": int(counts["unresolved_ledger"]),
    }


def _old_ratio_audit(old_counts: Mapping[str, int]) -> dict[str, float]:
    denominator = old_counts["unique_facts"]
    return {
        "timeline": round(old_counts["timeline_nodes"] * 100 / denominator, 4),
        "causal_rows_not_edges": round(
            old_counts["causal_rows_not_edges"] * 100 / denominator,
            4,
        ),
        "character_state": round(
            old_counts["character_state_rows"] * 100 / denominator,
            4,
        ),
        "unresolved": round(
            old_counts["unresolved_items"] * 100 / denominator,
            4,
        ),
    }


def _projection_membership(outline: Mapping[str, Any]) -> dict[str, set[str]]:
    views = _require_mapping(outline.get("views"), "outline.views")
    causal_refs: set[str] = set()
    for value in _require_list(views.get("causal_edges"), "causal_edges"):
        edge = _require_mapping(value, "causal_edge")
        causal_refs.update(str(item) for item in edge["from_fact_ids"])
        causal_refs.add(str(edge["to_fact_id"]))
    return {
        "timeline": {
            str(row["fact_id"])
            for row in _require_list(views.get("timeline"), "timeline")
        },
        "causal_endpoint": causal_refs,
        "character_state": {
            str(row["fact_id"])
            for row in _require_list(
                views.get("character_states"),
                "character_states",
            )
        },
        "unresolved": {
            str(row["fact_id"])
            for row in _require_list(
                views.get("unresolved_items"),
                "unresolved_items",
            )
        },
    }


def build_sidecar(
    *,
    source_sample_id: str,
    outline: Mapping[str, Any],
    source_locks: Sequence[Mapping[str, Any]],
    anchors_by_fact_id: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    membership = _projection_membership(outline)
    facts = _require_list(outline.get("facts"), "outline.facts")
    trace = []
    for fact in facts:
        mapping = _require_mapping(fact, "fact")
        fact_id = str(mapping["fact_id"])
        trace.append(
            {
                "fact_id": fact_id,
                "source_order": mapping["source_order"],
                "admission": {
                    "timeline": fact_id in membership["timeline"],
                    "causal_endpoint": fact_id in membership["causal_endpoint"],
                    "character_state": fact_id in membership["character_state"],
                    "unresolved": fact_id in membership["unresolved"],
                },
            }
        )

    if anchors_by_fact_id is None:
        anchor_inventory = {
            "availability": "not_supplied_in_consumer_sample",
            "fact_count": 0,
            "items": [],
        }
    else:
        anchor_items = [
            copy.deepcopy(dict(anchors_by_fact_id[fact_id]))
            for fact_id in EXPECTED_FACT_IDS
        ]
        anchor_inventory = {
            "availability": "carried_from_locked_z99_audit_sidecar",
            "fact_count": len(anchor_items),
            "items": anchor_items,
        }

    return {
        "schema": "chapter-fact-graph-outline-v1-audit-sidecar",
        "status": "candidate_sidecar_not_active",
        "source_sample_id": source_sample_id,
        "source_locks": copy.deepcopy(list(source_locks)),
        "anchor_policy": (
            "quote、anchor_id、minimal_support_sets 只留在本 sidecar；"
            "不得进入 chapter-fact-graph-outline-v1 消费包。"
        ),
        "anchor_inventory": anchor_inventory,
        "projection_trace": trace,
        "backlog": {
            "causal_single_endpoint_qualifiers": copy.deepcopy(
                list(SINGLE_ENDPOINT_CAUSAL_BACKLOG)
            ),
            "timeline_ambiguous_background": copy.deepcopy(
                list(TIMELINE_EXCLUSION_BACKLOG)
            ),
            "ratio_exceptions": copy.deepcopy(
                outline["ratio_audit"]["backlog"]
            ),
        },
        "quality_boundary": (
            "sidecar 只提供来源锁、锚与准入轨迹；不把候选重投影升级为正式金标。"
        ),
    }


def build_comparison(
    *,
    inputs: Mapping[str, Any],
    z99_outline: Mapping[str, Any],
    d_outline: Mapping[str, Any],
) -> dict[str, Any]:
    z99_before = _old_counts_for_z99(inputs["z99_candidate"])
    d_before = _old_counts_for_d(inputs["d_candidate"])
    z99_after = copy.deepcopy(dict(z99_outline["counts"]))
    d_after = copy.deepcopy(dict(d_outline["counts"]))
    if z99_after != d_after:
        raise ReprojectionError("同一组事实的两份重投影读数不一致。")
    semantic_digest = sha256_bytes(
        stable_json_bytes(_fact_semantic_copy(inputs["z99_facts"]))
    )
    return {
        "schema": "four-view-reprojection-before-after-v0.2",
        "status": "candidate_comparison_not_active",
        "denominator": {
            "name": "unique_scoring_atoms",
            "value": 23,
            "rule": "每个 fact_id 只计一次；四视图允许重复投影。",
        },
        "underlying_fact_semantic_sha256": semantic_digest,
        "samples": {
            "z99_four_views_candidate_sample": {
                "before_counts": z99_before,
                "before_percent": _old_ratio_audit(z99_before),
                "before_boundary": (
                    "causal 是单端限定候选，不是可沿链回读的因果边；"
                    "人物状态旧账收了全部 23 个事实。"
                ),
                "after_counts": z99_after,
                "after_ratio_audit": copy.deepcopy(z99_outline["ratio_audit"]),
            },
            "sample_d_shared": {
                "before_counts": d_before,
                "before_percent": _old_ratio_audit(d_before),
                "before_boundary": (
                    "causal_chain 仍是事实列表；人物状态旧账收了全部 23 个事实；"
                    "believed 风险被当成未决项。"
                ),
                "after_counts": d_after,
                "after_ratio_audit": copy.deepcopy(d_outline["ratio_audit"]),
            },
        },
        "state_variable_result": {
            "rule": "只有人物状态槽可持续更新时才准入人物状态账。",
            "before_rows": 23,
            "after_updates": 9,
            "main_character_continuity": {
                "character_id": "周明瑞",
                "state_slot": "knowledge",
                "entry_path": [
                    "CS-C0003-001",
                    "CS-C0003-004",
                    "CS-C0003-005",
                ],
            },
        },
        "fixed_v0.2_projection_result": {
            "timeline_nodes": 11,
            "causal_edges": 2,
            "unresolved_items": 4,
            "inference_edges": 0,
        },
        "exceptions": copy.deepcopy(z99_outline["ratio_audit"]["backlog"]),
        "quality_boundary": (
            "前后只比较结构和机械读数，不把旧 causal 行与新 causal edge "
            "当作同质质量分数。"
        ),
    }


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


def _source_lock_row(
    *,
    role: str,
    relative_path: Path,
    raw: bytes,
    projection_count: int,
) -> dict[str, Any]:
    return {
        "role": role,
        "path": relative_path.as_posix(),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "projection_count": projection_count,
    }


def build_bundle(output_dir: Path | None = None) -> dict[str, Any]:
    output = output_dir or (REPO_ROOT / DEFAULT_OUTPUT_RELATIVE_PATH)
    inputs = load_locked_inputs()

    z99_outline = build_outline(
        source_sample_id="z99_four_views_candidate_sample",
        facts=inputs["z99_facts"],
    )
    d_outline = build_outline(
        source_sample_id="sample_d_shared",
        facts=inputs["d_facts"],
    )

    z99_source_locks = [
        _source_lock_row(
            role="primary_consumer_sample",
            relative_path=Z99_SAMPLE_RELATIVE_PATH,
            raw=inputs["raw"]["z99_sample"],
            projection_count=1,
        ),
        _source_lock_row(
            role="audit_sidecar",
            relative_path=Z99_SIDECAR_RELATIVE_PATH,
            raw=inputs["raw"]["z99_sidecar"],
            projection_count=0,
        ),
        _source_lock_row(
            role="source_manifest",
            relative_path=Z99_MANIFEST_RELATIVE_PATH,
            raw=inputs["raw"]["z99_manifest"],
            projection_count=0,
        ),
    ]
    d_source_locks = [
        _source_lock_row(
            role="primary_shared_sample",
            relative_path=D_SAMPLE_RELATIVE_PATH,
            raw=inputs["raw"]["d_sample"],
            projection_count=1,
        ),
        _source_lock_row(
            role="w1_hash_only_mirror",
            relative_path=D_W1_MIRROR_RELATIVE_PATH,
            raw=inputs["raw"]["d_w1_mirror"],
            projection_count=0,
        ),
    ]

    z99_sidecar = build_sidecar(
        source_sample_id="z99_four_views_candidate_sample",
        outline=z99_outline,
        source_locks=z99_source_locks,
        anchors_by_fact_id=inputs["z99_anchors"],
    )
    d_sidecar = build_sidecar(
        source_sample_id="sample_d_shared",
        outline=d_outline,
        source_locks=d_source_locks,
        anchors_by_fact_id=None,
    )
    comparison = build_comparison(
        inputs=inputs,
        z99_outline=z99_outline,
        d_outline=d_outline,
    )

    _write_json(output / Z99_OUTPUT_FILENAME, z99_outline)
    _write_json(output / Z99_SIDECAR_OUTPUT_FILENAME, z99_sidecar)
    _write_json(output / D_OUTPUT_FILENAME, d_outline)
    _write_json(output / D_SIDECAR_OUTPUT_FILENAME, d_sidecar)
    _write_json(output / COMPARISON_FILENAME, comparison)

    artifact_names = (
        Z99_OUTPUT_FILENAME,
        Z99_SIDECAR_OUTPUT_FILENAME,
        D_OUTPUT_FILENAME,
        D_SIDECAR_OUTPUT_FILENAME,
        COMPARISON_FILENAME,
    )
    manifest = {
        "schema": "four-view-reprojection-artifact-manifest-v0.2",
        "status": "candidate_bundle_not_active",
        "task": "B1_four_view_reprojection",
        "generator": {
            "path": "tools/v02_four_view_reprojection.py",
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "inputs": [*z99_source_locks, *d_source_locks],
        "mirror_check": {
            "shared_d_equals_w1_attachment": True,
            "sha256": EXPECTED_INPUT_SHA256["d_sample"],
            "w1_attachment_projection_count": 0,
        },
        "underlying_fact_semantic_sha256": comparison[
            "underlying_fact_semantic_sha256"
        ],
        "experiment": {
            "only_variable": "character_state_admission",
            "rule": "state_slot_sustainably_updatable_only",
            "fixed_rules": {
                "timeline": "sortable_plot_event_or_state_turn",
                "causal": "two_independent_fact_endpoints_plus_explicit_relation",
                "unresolved": "question_task_promise_or_risk_lifecycle_change",
            },
        },
        "counts_per_sample": copy.deepcopy(dict(z99_outline["counts"])),
        "ratio_audit_per_sample": copy.deepcopy(dict(z99_outline["ratio_audit"])),
        "execution": {
            "model_api_calls": 0,
            "network_requests": 0,
            "formal_gold_mutations": 0,
            "default_route_mutations": 0,
            "governance_mutations": 0,
            "notion_writes": 0,
        },
        "artifact_hash_scope": (
            "下列五个产物；manifest 自身不进入清单，避免递归自哈希。"
        ),
        "artifacts": [
            _artifact_row(output, filename) for filename in artifact_names
        ],
        "quality_boundary": (
            "本包是 v0.2 B1 离线候选停点，不是正式金标、默认配置或生产启用。"
        ),
    }
    _write_json(output / MANIFEST_FILENAME, manifest)
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="离线生成 v0.2 B1 两份四视图重投影候选包。"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / DEFAULT_OUTPUT_RELATIVE_PATH,
        help="输出目录；五份输入始终按路径与 SHA 锁死。",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    manifest = build_bundle(args.output_dir)
    result = {
        "status": "PASS",
        "output_dir": str(args.output_dir),
        "manifest_sha256": sha256_file(args.output_dir / MANIFEST_FILENAME),
        "counts_per_sample": manifest["counts_per_sample"],
        "ratio_audit_per_sample": manifest["ratio_audit_per_sample"],
        "model_api_calls": 0,
        "network_requests": 0,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
