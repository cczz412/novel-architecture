#!/usr/bin/env python3
"""V02/C12.5：状态不变量诊断候选。

这个检查器只认显式、冻结、可复验的状态编号、时间坐标、作用域和规则表。
它不从中文状态描述猜“死亡”“位置”“已解决”等语义，也不把叙述顺序冒充
故事时间。

首版只诊断三类问题：

* 离开显式登记的不可逆状态；
* 同一作用域、实体和时间区间内出现显式登记的互斥状态；
* 后继状态的起点不严格晚于它引用的前驱状态。

输出永远是候选诊断，不亮灯、不判质量、不修改任何状态。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "tools").is_dir():
            return parent
    raise RuntimeError("无法定位小说架构仓库根目录")


ROOT = _find_repo_root()
V02_ROOT = ROOT / "experiments/extraction_redesign_v02_overnight_20260725"
OUTPUT_DIR = V02_ROOT / "V02_C12_5_state_invariant_checker_20260725"
REPORT_PATH = (
    ROOT
    / "reports/抽取工序重设计v0.2_C12积压优化项_20260725"
    / "C12_5_停点回包.md"
)
SELF_PATH = Path(__file__).resolve()
TEST_PATH = ROOT / "tests/test_v02_c12_5_state_invariant_checker.py"

B1_DIR = V02_ROOT / "B1_four_view_reprojection"
B1_SOURCES = {
    "z99_reprojection": (
        B1_DIR / "z99_four_views_reprojected_v02.json",
        "724e830a223d4e0952e35a60e9ff6a39758b702a5c04624850f9f075e451cae4",
    ),
    "sample_d_reprojection": (
        B1_DIR / "sample_d_four_views_reprojected_v02.json",
        "d4b223823d8aeca81c71e44cd9ed105ed956c95cbac1aa3e6a6ab4c17d3abc44",
    ),
    "b1_manifest": (
        B1_DIR / "manifest.json",
        "3911b46333e081860e4cd4db0a92fe59bd69ef8c7eb2b42bc13496f1c0169755",
    ),
}

C12_WORK_ORDER_PAGE = (
    "https://app.notion.com/p/"
    "v0-2-0API-A-CZ-Codex-_20260725-eb8821e57b67472db9f220b46110dcfd"
)
C12_LEDGER_PAGE = "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"

TIME_WIDTH = 4
UNKNOWN_STATE_ID = "__UNKNOWN__"
DIAGNOSTIC_CODES = {
    "irreversible": "C125-D101_IRREVERSIBLE_REVERSE",
    "exclusive": "C125-D201_EXCLUSIVE_INTERVAL_OVERLAP",
    "monotonic": "C125-D301_PREDECESSOR_TIME_REGRESSION",
}
NOT_EVALUATED_CODES = (
    "C125-N001_NO_FROZEN_STATE_RULE",
    "C125-N002_NO_CANONICAL_STATE_ID",
    "C125-N003_NO_TOTAL_TIME_COORDINATE",
    "C125-N004_NO_WORLD_TIMELINE_BRANCH_SCOPE",
)


class StateInvariantError(RuntimeError):
    """C12.5 输入或冻结证据不满足机械检查条件。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise StateInvariantError(f"文件不存在：{path}")
    return sha256_bytes(path.read_bytes())


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise StateInvariantError(f"{label} 必须是非空字符串")
    return value


def _require_sha256(value: Any, label: str) -> str:
    digest = _require_string(value, label)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise StateInvariantError(f"{label} 必须是 64 位小写 SHA-256")
    return digest


def _time_key(value: Any, label: str) -> tuple[int, ...]:
    if (
        not isinstance(value, list)
        or len(value) != TIME_WIDTH
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
        or any(item < 0 for item in value)
    ):
        raise StateInvariantError(
            f"{label} 必须是 {TIME_WIDTH} 位非负整数数组；"
            "禁止字符串数字、中文时间、章号猜测和数组位置"
        )
    return tuple(value)


def _scope_key(assertion: Mapping[str, Any]) -> tuple[str, str, str, str]:
    scope = assertion.get("scope")
    if not isinstance(scope, Mapping):
        raise StateInvariantError("状态记录缺少 scope")
    return (
        _require_string(scope.get("world_id"), "scope.world_id"),
        _require_string(scope.get("timeline_id"), "scope.timeline_id"),
        _require_string(scope.get("branch_id"), "scope.branch_id"),
        _require_string(scope.get("policy_scope_id"), "scope.policy_scope_id"),
    )


def _same_scope(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return _scope_key(left) == _scope_key(right)


def _intervals_overlap(
    left_start: tuple[int, ...],
    left_end: tuple[int, ...] | None,
    right_start: tuple[int, ...],
    right_end: tuple[int, ...] | None,
) -> bool:
    """左闭右开区间是否有真实交集；None 表示正无穷。"""

    left_before_right_end = right_end is None or left_start < right_end
    right_before_left_end = left_end is None or right_start < left_end
    return left_before_right_end and right_before_left_end


def validate_rules(rules: Mapping[str, Any]) -> dict[str, Any]:
    if rules.get("schema_version") != "v02-c12.5-state-invariant-rules.v1":
        raise StateInvariantError("规则表 schema_version 不正确")
    policy_scope_id = _require_string(
        rules.get("policy_scope_id"), "rules.policy_scope_id"
    )
    domains = rules.get("state_domains")
    if not isinstance(domains, list) or not domains:
        raise StateInvariantError("规则表缺少 state_domains")

    states_by_slot: dict[str, set[str]] = {}
    for row in domains:
        if not isinstance(row, Mapping):
            raise StateInvariantError("state_domains 含非对象")
        slot_id = _require_string(row.get("slot_id"), "state_domain.slot_id")
        state_ids = row.get("state_ids")
        if (
            slot_id in states_by_slot
            or not isinstance(state_ids, list)
            or not state_ids
            or any(not isinstance(item, str) or not item for item in state_ids)
            or len(set(state_ids)) != len(state_ids)
            or UNKNOWN_STATE_ID in state_ids
        ):
            raise StateInvariantError("state_domains 重复、为空或含非法状态")
        states_by_slot[slot_id] = set(state_ids)

    irreversible = rules.get("irreversible_states")
    if not isinstance(irreversible, list):
        raise StateInvariantError("irreversible_states 必须是数组")
    irreversible_pairs: set[tuple[str, str]] = set()
    for row in irreversible:
        if not isinstance(row, Mapping):
            raise StateInvariantError("irreversible_states 含非对象")
        pair = (
            _require_string(row.get("slot_id"), "irreversible.slot_id"),
            _require_string(row.get("state_id"), "irreversible.state_id"),
        )
        if (
            pair[0] not in states_by_slot
            or pair[1] not in states_by_slot[pair[0]]
            or pair in irreversible_pairs
        ):
            raise StateInvariantError("不可逆状态引用未知状态或重复登记")
        irreversible_pairs.add(pair)

    exclusive_sets = rules.get("exclusive_sets")
    if not isinstance(exclusive_sets, list):
        raise StateInvariantError("exclusive_sets 必须是数组")
    exclusive: list[dict[str, Any]] = []
    seen_set_ids: set[str] = set()
    membership: set[tuple[str, str]] = set()
    for row in exclusive_sets:
        if not isinstance(row, Mapping):
            raise StateInvariantError("exclusive_sets 含非对象")
        set_id = _require_string(row.get("set_id"), "exclusive_set.set_id")
        members = row.get("members")
        if set_id in seen_set_ids or not isinstance(members, list) or len(members) < 2:
            raise StateInvariantError("互斥组重复或成员不足")
        seen_set_ids.add(set_id)
        normalized_members: list[tuple[str, str]] = []
        for member in members:
            if not isinstance(member, Mapping):
                raise StateInvariantError("互斥组成员不是对象")
            pair = (
                _require_string(member.get("slot_id"), "member.slot_id"),
                _require_string(member.get("state_id"), "member.state_id"),
            )
            if (
                pair[0] not in states_by_slot
                or pair[1] not in states_by_slot[pair[0]]
                or pair in membership
            ):
                raise StateInvariantError("互斥组引用未知状态或成员跨组重复")
            membership.add(pair)
            normalized_members.append(pair)
        if len({slot_id for slot_id, _state_id in normalized_members}) != 1:
            raise StateInvariantError("首版互斥组只允许同一状态槽")
        exclusive.append({"set_id": set_id, "members": tuple(normalized_members)})

    time_contract = rules.get("time_contract")
    expected_time_contract = {
        "coordinate_fields": [
            "chapter_index",
            "scene_index",
            "event_index",
            "phase_index",
        ],
        "interval_semantics": "HALF_OPEN",
        "null_end": "POSITIVE_INFINITY",
        "predecessor_order": "STRICTLY_INCREASING",
    }
    if time_contract != expected_time_contract:
        raise StateInvariantError("规则表 time_contract 与首版机械语义不一致")
    if rules.get("natural_language_state_inference") != "FORBIDDEN":
        raise StateInvariantError("规则表没有禁止自然语言状态推断")

    return {
        "policy_scope_id": policy_scope_id,
        "states_by_slot": states_by_slot,
        "irreversible_pairs": irreversible_pairs,
        "exclusive_sets": exclusive,
    }


def validate_stream(
    stream: Mapping[str, Any],
    *,
    normalized_rules: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if stream.get("schema_version") != "v02-c12.5-state-assertion-stream.v1":
        raise StateInvariantError("状态流 schema_version 不正确")
    rows = stream.get("assertions")
    if not isinstance(rows, list) or not rows:
        raise StateInvariantError("状态流没有 assertions")

    assertions: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    states_by_slot = normalized_rules["states_by_slot"]
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise StateInvariantError("assertions 含非对象")
        row = copy.deepcopy(dict(raw))
        assertion_id = _require_string(row.get("assertion_id"), "assertion_id")
        if assertion_id in by_id:
            raise StateInvariantError("assertion_id 重复")
        entity_id = _require_string(row.get("entity_id"), "entity_id")
        slot_id = _require_string(row.get("slot_id"), "slot_id")
        state_id = _require_string(row.get("state_id"), "state_id")
        identity_binding = _require_sha256(
            row.get("identity_binding_sha256"), "identity_binding_sha256"
        )
        if (
            slot_id not in states_by_slot
            or state_id != UNKNOWN_STATE_ID
            and state_id not in states_by_slot[slot_id]
        ):
            raise StateInvariantError("状态记录引用未知槽或状态 ID")
        scope = _scope_key(row)
        if scope[3] != normalized_rules["policy_scope_id"]:
            raise StateInvariantError("状态记录 policy_scope_id 与规则表不一致")
        valid_from = _time_key(row.get("valid_from"), "valid_from")
        valid_until_raw = row.get("valid_until")
        valid_until = (
            None
            if valid_until_raw is None
            else _time_key(valid_until_raw, "valid_until")
        )
        if valid_until is not None and valid_until <= valid_from:
            raise StateInvariantError("状态有效区间为空或反向")
        predecessor = row.get("predecessor_assertion_id")
        if predecessor is not None and (
            not isinstance(predecessor, str) or not predecessor
        ):
            raise StateInvariantError("predecessor_assertion_id 非法")
        source_fact_ids = row.get("source_fact_ids")
        evidence_refs = row.get("evidence_refs")
        if (
            not isinstance(source_fact_ids, list)
            or not source_fact_ids
            or any(not isinstance(item, str) or not item for item in source_fact_ids)
            or not isinstance(evidence_refs, list)
            or not evidence_refs
        ):
            raise StateInvariantError("状态记录缺事实或证据引用")
        for evidence_index, evidence in enumerate(evidence_refs, 1):
            if not isinstance(evidence, Mapping):
                raise StateInvariantError("evidence_refs 含非对象")
            _require_sha256(
                evidence.get("artifact_sha256"),
                f"evidence_refs[{evidence_index}].artifact_sha256",
            )
            _require_string(
                evidence.get("anchor_id"),
                f"evidence_refs[{evidence_index}].anchor_id",
            )
            _require_sha256(
                evidence.get("span_sha256"),
                f"evidence_refs[{evidence_index}].span_sha256",
            )
        normalized = {
            **row,
            "assertion_id": assertion_id,
            "entity_id": entity_id,
            "slot_id": slot_id,
            "state_id": state_id,
            "_identity_binding": identity_binding,
            "_scope_key": scope,
            "_valid_from": valid_from,
            "_valid_until": valid_until,
        }
        assertions.append(normalized)
        by_id[assertion_id] = normalized

    binding_by_entity_scope: dict[tuple[tuple[str, str, str, str], str], str] = {}
    for row in assertions:
        identity_key = (row["_scope_key"], row["entity_id"])
        previous_binding = binding_by_entity_scope.setdefault(
            identity_key,
            row["_identity_binding"],
        )
        if previous_binding != row["_identity_binding"]:
            raise StateInvariantError("同一作用域与实体 ID 出现身份绑定漂移")

    for row in assertions:
        predecessor_id = row.get("predecessor_assertion_id")
        if predecessor_id is None:
            continue
        predecessor = by_id.get(predecessor_id)
        if predecessor is None:
            raise StateInvariantError("前驱记录悬空")
        if (
            predecessor["entity_id"] != row["entity_id"]
            or predecessor["slot_id"] != row["slot_id"]
            or predecessor["_scope_key"] != row["_scope_key"]
            or predecessor["_identity_binding"] != row["_identity_binding"]
        ):
            raise StateInvariantError("前驱记录跨身份、实体、槽或作用域")

    for start in assertions:
        seen: set[str] = set()
        current = start
        while current.get("predecessor_assertion_id") is not None:
            current_id = current["assertion_id"]
            if current_id in seen:
                raise StateInvariantError("前驱链形成环")
            seen.add(current_id)
            current = by_id[current["predecessor_assertion_id"]]

    return sorted(
        assertions,
        key=lambda row: (
            row["_scope_key"],
            row["entity_id"],
            row["slot_id"],
            row["_valid_from"],
            row["assertion_id"],
        ),
    )


def diagnose(
    *,
    rules: Mapping[str, Any],
    stream: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_rules = validate_rules(rules)
    assertions = validate_stream(stream, normalized_rules=normalized_rules)
    by_id = {row["assertion_id"]: row for row in assertions}
    findings: list[dict[str, Any]] = []

    irreversible_checks = 0
    for terminal_slot, terminal_state in sorted(
        normalized_rules["irreversible_pairs"]
    ):
        terminal_groups: dict[
            tuple[tuple[str, str, str, str], str, str],
            list[dict[str, Any]],
        ] = {}
        for row in assertions:
            if row["slot_id"] == terminal_slot and row["state_id"] == terminal_state:
                terminal_groups.setdefault(
                    (
                        row["_scope_key"],
                        row["entity_id"],
                        row["_identity_binding"],
                    ),
                    [],
                ).append(row)
        for (scope, entity_id, binding), group in sorted(
            terminal_groups.items(),
            key=lambda item: item[0],
        ):
            terminal = min(
                group,
                key=lambda row: (row["_valid_from"], row["assertion_id"]),
            )
            conflicting = [
                row
                for row in assertions
                if row["entity_id"] == entity_id
                and row["_identity_binding"] == binding
                and row["slot_id"] == terminal_slot
                and row["_scope_key"] == scope
                and row["state_id"] not in {UNKNOWN_STATE_ID, terminal_state}
                and (
                    row["_valid_until"] is None
                    or row["_valid_until"] > terminal["_valid_from"]
                )
            ]
            for current in conflicting:
                irreversible_checks += 1
                findings.append(
                    {
                        "code": DIAGNOSTIC_CODES["irreversible"],
                        "rule_identity": {
                            "slot_id": terminal_slot,
                            "terminal_state_id": terminal_state,
                        },
                        "assertion_ids": [
                            terminal["assertion_id"],
                            current["assertion_id"],
                        ],
                        "source_fact_ids": sorted(
                            set(terminal["source_fact_ids"])
                            | set(current["source_fact_ids"])
                        ),
                        "scope": list(terminal["_scope_key"]),
                        "terminal_start": list(terminal["_valid_from"]),
                        "conflicting_interval": [
                            list(current["_valid_from"]),
                            (
                                None
                                if current["_valid_until"] is None
                                else list(current["_valid_until"])
                            ),
                        ],
                        "mechanical_basis": (
                            "non_terminal_state_active_at_or_after_registered_terminal"
                        ),
                    }
                )

    exclusive_checks = 0
    for group in normalized_rules["exclusive_sets"]:
        members = set(group["members"])
        eligible = [
            row
            for row in assertions
            if (row["slot_id"], row["state_id"]) in members
            and row["state_id"] != UNKNOWN_STATE_ID
        ]
        for left_index, left in enumerate(eligible):
            for right in eligible[left_index + 1 :]:
                if (
                    left["entity_id"] != right["entity_id"]
                    or left["_identity_binding"] != right["_identity_binding"]
                    or left["_scope_key"] != right["_scope_key"]
                    or left["state_id"] == right["state_id"]
                ):
                    continue
                exclusive_checks += 1
                if _intervals_overlap(
                    left["_valid_from"],
                    left["_valid_until"],
                    right["_valid_from"],
                    right["_valid_until"],
                ):
                    findings.append(
                        {
                            "code": DIAGNOSTIC_CODES["exclusive"],
                            "rule_identity": {"exclusive_set_id": group["set_id"]},
                            "assertion_ids": sorted(
                                [left["assertion_id"], right["assertion_id"]]
                            ),
                            "source_fact_ids": sorted(
                                set(left["source_fact_ids"])
                                | set(right["source_fact_ids"])
                            ),
                            "scope": list(left["_scope_key"]),
                            "time_intervals": sorted(
                                [
                                    [
                                        list(left["_valid_from"]),
                                        (
                                            None
                                            if left["_valid_until"] is None
                                            else list(left["_valid_until"])
                                        ),
                                    ],
                                    [
                                        list(right["_valid_from"]),
                                        (
                                            None
                                            if right["_valid_until"] is None
                                            else list(right["_valid_until"])
                                        ),
                                    ],
                                ],
                                key=lambda item: item[0],
                            ),
                            "mechanical_basis": (
                                "declared_exclusive_states_overlap_in_same_scope"
                            ),
                        }
                    )

    monotonic_checks = 0
    for row in assertions:
        predecessor_id = row.get("predecessor_assertion_id")
        if predecessor_id is None:
            continue
        monotonic_checks += 1
        predecessor = by_id[predecessor_id]
        if row["_valid_from"] <= predecessor["_valid_from"]:
            findings.append(
                {
                    "code": DIAGNOSTIC_CODES["monotonic"],
                    "rule_identity": {
                        "predecessor_order": "STRICTLY_INCREASING"
                    },
                    "assertion_ids": [
                        predecessor["assertion_id"],
                        row["assertion_id"],
                    ],
                    "source_fact_ids": sorted(
                        set(predecessor["source_fact_ids"])
                        | set(row["source_fact_ids"])
                    ),
                    "scope": list(row["_scope_key"]),
                    "time_keys": [
                        list(predecessor["_valid_from"]),
                        list(row["_valid_from"]),
                    ],
                    "mechanical_basis": (
                        "successor_start_not_strictly_after_predecessor_start"
                    ),
                }
            )

    findings = sorted(
        findings,
        key=lambda row: (
            row["code"],
            tuple(row["assertion_ids"]),
        ),
    )
    counts = Counter(row["code"] for row in findings)
    unknown_total = sum(
        row["state_id"] == UNKNOWN_STATE_ID for row in assertions
    )
    return {
        "schema_version": "v02-c12.5-state-invariant-diagnostic.v1",
        "status": "DIAGNOSTIC_ONLY",
        "quality_result_registered": False,
        "quality_score_eligible": False,
        "traffic_light_eligible": False,
        "blocks_execution": False,
        "winner": None,
        "changes_applied": False,
        "assertion_total": len(assertions),
        "unknown_state_total": unknown_total,
        "diagnostic_completeness": (
            "INCOMPLETE_UNKNOWN_STATE_PRESENT"
            if unknown_total
            else "COMPLETE_FOR_DECLARED_RULES_AND_FIELDS"
        ),
        "rule_summaries": [
            {
                "rule": "irreversible_state",
                "evaluated_pair_total": irreversible_checks,
                "finding_total": counts[DIAGNOSTIC_CODES["irreversible"]],
            },
            {
                "rule": "mutually_exclusive_interval",
                "evaluated_pair_total": exclusive_checks,
                "finding_total": counts[DIAGNOSTIC_CODES["exclusive"]],
            },
            {
                "rule": "predecessor_time_monotonicity",
                "evaluated_edge_total": monotonic_checks,
                "finding_total": counts[DIAGNOSTIC_CODES["monotonic"]],
            },
        ],
        "finding_total": len(findings),
        "findings": findings,
    }


def build_rules_fixture() -> dict[str, Any]:
    return {
        "schema_version": "v02-c12.5-state-invariant-rules.v1",
        "policy_scope_id": "POLICY-CANARY-01",
        "state_domains": [
            {"slot_id": "life", "state_ids": ["alive", "dead"]},
            {"slot_id": "location", "state_ids": ["city_a", "city_b"]},
            {"slot_id": "knowledge", "state_ids": ["low", "high"]},
        ],
        "irreversible_states": [{"slot_id": "life", "state_id": "dead"}],
        "exclusive_sets": [
            {
                "set_id": "EX-LOCATION-01",
                "members": [
                    {"slot_id": "location", "state_id": "city_a"},
                    {"slot_id": "location", "state_id": "city_b"},
                ],
            }
        ],
        "time_contract": {
            "coordinate_fields": [
                "chapter_index",
                "scene_index",
                "event_index",
                "phase_index",
            ],
            "interval_semantics": "HALF_OPEN",
            "null_end": "POSITIVE_INFINITY",
            "predecessor_order": "STRICTLY_INCREASING",
        },
        "natural_language_state_inference": "FORBIDDEN",
    }


def _assertion(
    assertion_id: str,
    *,
    slot_id: str,
    state_id: str,
    valid_from: Sequence[int],
    valid_until: Sequence[int] | None,
    predecessor: str | None,
) -> dict[str, Any]:
    return {
        "assertion_id": assertion_id,
        "scope": {
            "world_id": "W01",
            "timeline_id": "T01",
            "branch_id": "B01",
            "policy_scope_id": "POLICY-CANARY-01",
        },
        "entity_id": "ENTITY-01",
        "identity_binding_sha256": "1" * 64,
        "slot_id": slot_id,
        "state_id": state_id,
        "valid_from": list(valid_from),
        "valid_until": None if valid_until is None else list(valid_until),
        "predecessor_assertion_id": predecessor,
        "source_fact_ids": [f"FACT-{assertion_id}"],
        "evidence_refs": [
            {
                "artifact_sha256": "2" * 64,
                "anchor_id": f"ANCHOR-{assertion_id}",
                "span_sha256": "3" * 64,
            }
        ],
    }


def build_clean_stream() -> dict[str, Any]:
    return {
        "schema_version": "v02-c12.5-state-assertion-stream.v1",
        "assertions": [
            _assertion(
                "A-LIFE-1",
                slot_id="life",
                state_id="alive",
                valid_from=[1, 0, 1, 0],
                valid_until=[1, 0, 2, 0],
                predecessor=None,
            ),
            _assertion(
                "A-LIFE-2",
                slot_id="life",
                state_id="dead",
                valid_from=[1, 0, 2, 0],
                valid_until=None,
                predecessor="A-LIFE-1",
            ),
            _assertion(
                "A-LOC-1",
                slot_id="location",
                state_id="city_a",
                valid_from=[1, 0, 1, 0],
                valid_until=[1, 0, 2, 0],
                predecessor=None,
            ),
            _assertion(
                "A-LOC-2",
                slot_id="location",
                state_id="city_b",
                valid_from=[1, 0, 2, 0],
                valid_until=None,
                predecessor="A-LOC-1",
            ),
            _assertion(
                "A-KNOW-1",
                slot_id="knowledge",
                state_id="low",
                valid_from=[1, 0, 1, 0],
                valid_until=[1, 0, 2, 0],
                predecessor=None,
            ),
            _assertion(
                "A-KNOW-2",
                slot_id="knowledge",
                state_id="high",
                valid_from=[1, 0, 2, 0],
                valid_until=None,
                predecessor="A-KNOW-1",
            ),
        ],
    }


def build_mutants() -> dict[str, dict[str, Any]]:
    clean = build_clean_stream()

    irreversible = copy.deepcopy(clean)
    irreversible["assertions"].append(
        _assertion(
            "M-IRREVERSIBLE",
            slot_id="life",
            state_id="alive",
            valid_from=[1, 0, 3, 0],
            valid_until=None,
            predecessor="A-LIFE-2",
        )
    )

    exclusive = copy.deepcopy(clean)
    exclusive["assertions"].append(
        _assertion(
            "M-EXCLUSIVE",
            slot_id="location",
            state_id="city_a",
            valid_from=[1, 0, 2, 0],
            valid_until=[1, 0, 3, 0],
            predecessor=None,
        )
    )

    monotonic = copy.deepcopy(clean)
    for row in monotonic["assertions"]:
        if row["assertion_id"] == "A-KNOW-2":
            row["valid_from"] = [1, 0, 1, 0]
            row["valid_until"] = [1, 0, 3, 0]
            break

    return {
        "irreversible_reverse": irreversible,
        "exclusive_interval_overlap": exclusive,
        "predecessor_time_regression": monotonic,
    }


def build_canary_results() -> dict[str, Any]:
    rules = build_rules_fixture()
    clean_result = diagnose(rules=rules, stream=build_clean_stream())
    expected = {
        "irreversible_reverse": DIAGNOSTIC_CODES["irreversible"],
        "exclusive_interval_overlap": DIAGNOSTIC_CODES["exclusive"],
        "predecessor_time_regression": DIAGNOSTIC_CODES["monotonic"],
    }
    mutants: list[dict[str, Any]] = []
    for mutant_id, stream in build_mutants().items():
        result = diagnose(rules=rules, stream=stream)
        codes = [row["code"] for row in result["findings"]]
        mutants.append(
            {
                "mutant_id": mutant_id,
                "expected_code": expected[mutant_id],
                "observed_codes": codes,
                "detected_exactly_as_expected": codes == [expected[mutant_id]],
            }
        )
    return {
        "schema_version": "v02-c12.5-canary-results.v1",
        "fixture_only_not_real_novel_quality": True,
        "clean_fixture_finding_total": clean_result["finding_total"],
        "single_mutation_total": len(mutants),
        "single_mutation_detected_total": sum(
            row["detected_exactly_as_expected"] for row in mutants
        ),
        "mutants": mutants,
        "quality_result_registered": False,
    }


def _locked_source_receipt() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for role, (path, expected) in B1_SOURCES.items():
        actual = sha256_file(path)
        if actual != expected:
            raise StateInvariantError(
                f"B1 冻结源 SHA 漂移：{role} expected={expected} actual={actual}"
            )
        items.append(
            {
                "role": role,
                "path": display_path(path),
                "sha256": actual,
            }
        )
    return {
        "schema_version": "v02-c12.5-source-binding.v1",
        "sources": items,
        "source_sha_unchanged": True,
        "c13_read_or_write_total": 0,
    }


def scan_material_eligibility(
    *,
    source_role: str,
    source_path: Path,
    source_sha256: str,
    document: Mapping[str, Any],
) -> dict[str, Any]:
    state_rows_raw = document.get("views", {}).get("character_states", [])
    state_rows = (
        [row for row in state_rows_raw if isinstance(row, Mapping)]
        if isinstance(state_rows_raw, list)
        else []
    )
    state_total = len(state_rows)
    canonical_state_total = sum(
        isinstance(row.get("state_id"), str) and bool(row.get("state_id"))
        for row in state_rows
    )
    time_coordinate_total = sum(
        isinstance(row.get("valid_from"), list)
        and len(row["valid_from"]) == TIME_WIDTH
        and all(
            not isinstance(item, bool) and isinstance(item, int) and item >= 0
            for item in row["valid_from"]
        )
        for row in state_rows
    )
    scope_total = sum(
        isinstance(row.get("scope"), Mapping)
        and all(
            isinstance(row["scope"].get(key), str) and bool(row["scope"].get(key))
            for key in (
                "world_id",
                "timeline_id",
                "branch_id",
                "policy_scope_id",
            )
        )
        for row in state_rows
    )
    rule_registry = document.get("state_invariant_rules")
    frozen_rule_total = int(
        isinstance(rule_registry, Mapping)
        and rule_registry.get("schema_version")
        == "v02-c12.5-state-invariant-rules.v1"
    )
    codes: list[str] = []
    if frozen_rule_total == 0:
        codes.append("C125-N001_NO_FROZEN_STATE_RULE")
    if canonical_state_total != state_total:
        codes.append("C125-N002_NO_CANONICAL_STATE_ID")
    if time_coordinate_total != state_total:
        codes.append("C125-N003_NO_TOTAL_TIME_COORDINATE")
    if scope_total != state_total:
        codes.append("C125-N004_NO_WORLD_TIMELINE_BRANCH_SCOPE")
    return {
        "source_role": source_role,
        "source_path": display_path(source_path),
        "source_sha256": source_sha256,
        "state_row_total": state_total,
        "eligibility": (
            "NOT_EVALUATED"
            if codes
            else "STRUCTURALLY_ELIGIBLE_PENDING_SEPARATE_RULE_AND_STREAM_VALIDATION"
        ),
        "not_evaluated_codes": codes,
        "canonical_state_id_total": canonical_state_total,
        "total_time_coordinate_total": time_coordinate_total,
        "complete_scope_total": scope_total,
        "frozen_rule_total": frozen_rule_total,
        "natural_language_before_after_used_for_rules": False,
        "narrative_order_used_as_story_time": False,
        "finding_total": None,
    }


def _scan_b1_eligibility() -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for role in ("z99_reprojection", "sample_d_reprojection"):
        path, expected_sha = B1_SOURCES[role]
        document = json.loads(path.read_text(encoding="utf-8"))
        samples.append(
            scan_material_eligibility(
                source_role=role,
                source_path=path,
                source_sha256=expected_sha,
                document=document,
            )
        )
    return {
        "schema_version": "v02-c12.5-real-material-eligibility.v1",
        "status": "REAL_MATERIAL_NOT_ELIGIBLE_FOR_INVARIANT_SCAN",
        "samples": samples,
        "quality_result_registered": False,
        "false_zero_warning": (
            "缺规则、规范状态 ID、完整时间坐标和作用域时，不能把零告警写成通过。"
        ),
    }


def build_contract() -> dict[str, Any]:
    return {
        "schema_version": "v02-c12.5-state-invariant-contract.v1",
        "status": "candidate_diagnostic_not_active",
        "authority": {
            "work_order": C12_WORK_ORDER_PAGE,
            "ledger": C12_LEDGER_PAGE,
        },
        "scope": [
            "explicit_irreversible_state_reverse",
            "declared_exclusive_interval_overlap",
            "explicit_predecessor_time_regression",
        ],
        "required_inputs": [
            "frozen_rule_registry",
            "canonical_state_ids",
            "four_integer_story_time_coordinate",
            "world_timeline_branch_policy_scope",
            "identity_binding",
            "fact_and_evidence_references",
        ],
        "time_semantics": {
            "coordinate_width": TIME_WIDTH,
            "interval": "LEFT_CLOSED_RIGHT_OPEN",
            "null_end": "POSITIVE_INFINITY",
            "predecessor": "STRICTLY_INCREASING_START",
        },
        "unknown_state_id": UNKNOWN_STATE_ID,
        "unknown_policy": "excluded_from_irreversible_and_exclusive_diagnosis",
        "forbidden_inference": [
            "natural_language_state_keyword",
            "substring_or_synonym_state_match",
            "narrative_order_as_story_time",
            "chapter_id_or_array_position_as_hidden_clock",
            "alias_or_identity_merge",
            "cross_world_timeline_or_branch_comparison",
            "automatic_exception_or_revival_detection",
        ],
        "output_boundary": {
            "diagnostic_only": True,
            "quality_result_registered": False,
            "traffic_light_eligible": False,
            "blocks_execution": False,
            "changes_applied": False,
            "winner": None,
        },
    }


def _stop_receipt(
    *,
    source_receipt: Mapping[str, Any],
    canary: Mapping[str, Any],
    eligibility: Mapping[str, Any],
) -> str:
    samples = eligibility["samples"]
    return f"""# C12.5｜状态不变量检查器停点回包

✅ 结论：首版机械检查器工程可用，但现有真实 B1 状态账不具备巡检资格；
本道没有登记真实小说质量胜负，也没有输出假的“零告警通过”。

## 三条机械规则

- 不可逆状态：只认冻结规则表里的槽和值；离开已登记终态才记诊断。
- 同时互斥：只认同世界、时间线、分支、实体的互斥状态区间真实重叠；
  区间首尾相接不算重叠。
- 时序单调：后继记录的四段故事时间起点必须严格晚于前驱。

所有状态值都是不透明 ID。程序不从“已死、在某地、已解决”等中文里猜规则，
也不拿叙述顺序、章号或数组位置冒充故事时间。

## 金丝雀夹具

- 无矛盾夹具误报：{canary["clean_fixture_finding_total"]}。
- 三类单变量变异：{canary["single_mutation_detected_total"]}/
  {canary["single_mutation_total"]} 按预期被各自唯一规则检出。
- 这些只证明检查器有牙，不是网文质量成绩。

## 真实材料资格扫描

- B1 两份样张各有 {samples[0]["state_row_total"]} 条人物状态。
- 规范状态 ID、完整故事时间、世界／分支作用域、冻结规则表均缺失。
- 两份均记 `NOT_EVALUATED`；没有用自然语言补规则，没有把叙述顺序当故事时间。

## 保护面

- B1 冻结输入 {len(source_receipt["sources"])} 份 SHA 全同，回写 0。
- 模型 API／网络请求：0／0。
- 现役链、正式金标、默认项、C13 均未触碰。
- 输出固定为诊断候选：不亮灯、不阻断、不判赢家、不写质量分。

来源：Codex
"""


def _artifact_set_sha(files: Mapping[str, bytes]) -> str:
    rows = [
        {"path": name, "sha256": sha256_bytes(raw)}
        for name, raw in sorted(files.items())
    ]
    return sha256_bytes(canonical_bytes(rows))


def _build_payload_objects() -> dict[str, Any]:
    source_receipt = _locked_source_receipt()
    canary = build_canary_results()
    eligibility = _scan_b1_eligibility()
    contract = build_contract()
    implementation = {
        "schema_version": "v02-c12.5-implementation-binding.v1",
        "program": {
            "path": display_path(SELF_PATH),
            "sha256": sha256_file(SELF_PATH),
        },
        "test": {
            "path": display_path(TEST_PATH),
            "sha256": sha256_file(TEST_PATH),
        },
        "program_or_test_change_requires_artifact_regeneration": True,
    }
    return {
        "state_invariant_contract_v1.json": contract,
        "state_invariant_rules_canary_v1.json": build_rules_fixture(),
        "state_invariant_clean_stream_canary_v1.json": build_clean_stream(),
        "canary_diagnostic_results.json": canary,
        "b1_real_material_eligibility_scan.json": eligibility,
        "source_binding_receipt.json": source_receipt,
        "implementation_binding_receipt.json": implementation,
    }


def build_artifacts() -> tuple[dict[str, bytes], bytes]:
    first_objects = _build_payload_objects()
    second_objects = _build_payload_objects()
    first = {name: canonical_bytes(value) for name, value in first_objects.items()}
    second = {name: canonical_bytes(value) for name, value in second_objects.items()}
    first["C12_5_stop_receipt.md"] = _stop_receipt(
        source_receipt=first_objects["source_binding_receipt.json"],
        canary=first_objects["canary_diagnostic_results.json"],
        eligibility=first_objects["b1_real_material_eligibility_scan.json"],
    ).encode("utf-8")
    second["C12_5_stop_receipt.md"] = _stop_receipt(
        source_receipt=second_objects["source_binding_receipt.json"],
        canary=second_objects["canary_diagnostic_results.json"],
        eligibility=second_objects["b1_real_material_eligibility_scan.json"],
    ).encode("utf-8")
    if first != second:
        raise StateInvariantError("C12.5 两次独立重建不一致")
    double_run = {
        "schema_version": "v02-c12.5-double-run.v1",
        "byte_identical": True,
        "compared_file_total": len(first),
        "payload_set_sha256": _artifact_set_sha(first),
    }
    files = {
        **first,
        "double_run_receipt.json": canonical_bytes(double_run),
    }
    rows = [
        {"path": name, "sha256": sha256_bytes(raw)}
        for name, raw in sorted(files.items())
    ]
    manifest = {
        "schema_version": "v02-c12.5-artifact-manifest.v1",
        "artifact_set_sha256": sha256_bytes(canonical_bytes(rows)),
        "file_total_excluding_self": len(rows),
        "files": rows,
        "model_api_calls": 0,
        "network_requests": 0,
        "quality_result_registered": False,
        "active_route_mutations": 0,
        "c13_touched": False,
    }
    return files, canonical_bytes(manifest)


def _assert_output_path() -> None:
    resolved = OUTPUT_DIR.resolve()
    protected = [
        B1_DIR.resolve(),
        (V02_ROOT / "V02_C13_downstream_consumer_20260725").resolve(),
        (ROOT / "config/gold").resolve(),
        (ROOT / "runs").resolve(),
    ]
    if any(resolved == root or resolved.is_relative_to(root) for root in protected):
        raise StateInvariantError("C12.5 输出路径落入冻结或并行根")


def _is_ignorable_runtime_cache(relative_path: Path) -> bool:
    """Only Python's import cache is outside the controlled artifact set."""
    return (
        "__pycache__" in relative_path.parts
        and relative_path.suffix in {".pyc", ".pyo"}
    )


def _controlled_output_names() -> set[str]:
    return {
        relative.as_posix()
        for path in OUTPUT_DIR.rglob("*")
        if path.is_file()
        and not _is_ignorable_runtime_cache(
            relative := path.relative_to(OUTPUT_DIR)
        )
    }


def write_bundle() -> dict[str, Any]:
    _assert_output_path()
    files, manifest_raw = build_artifacts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    expected_names = set(files) | {
        "artifact_manifest.json",
        f"program/{SELF_PATH.name}",
    }
    stale = _controlled_output_names() - expected_names
    if stale:
        raise StateInvariantError(f"C12.5 输出目录含陈旧文件：{sorted(stale)}")
    for name, raw in files.items():
        (OUTPUT_DIR / name).write_bytes(raw)
    (OUTPUT_DIR / "artifact_manifest.json").write_bytes(manifest_raw)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_bytes(files["C12_5_stop_receipt.md"])
    return json.loads(manifest_raw)


def check_bundle() -> dict[str, Any]:
    files, manifest_raw = build_artifacts()
    expected = {**files, "artifact_manifest.json": manifest_raw}
    expected_names = set(expected) | {f"program/{SELF_PATH.name}"}
    actual_names = _controlled_output_names()
    if actual_names != expected_names:
        raise StateInvariantError(
            "C12.5 工件集合不闭合："
            f"missing={sorted(expected_names - actual_names)} "
            f"extra={sorted(actual_names - expected_names)}"
        )
    for name, raw in expected.items():
        if (OUTPUT_DIR / name).read_bytes() != raw:
            raise StateInvariantError(f"C12.5 工件漂移：{name}")
    if REPORT_PATH.read_bytes() != files["C12_5_stop_receipt.md"]:
        raise StateInvariantError("C12.5 本地回包与工件正文不一致")
    return json.loads(manifest_raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = check_bundle() if args.check else write_bundle()
    print(
        json.dumps(
            {
                "status": "CANDIDATE_DIAGNOSTIC_ENGINEERING_READY",
                "artifact_set_sha256": manifest["artifact_set_sha256"],
                "real_material_quality_result": "NOT_EVALUATED",
                "canary_mutations_detected": "3/3",
                "model_api_calls": 0,
                "network_requests": 0,
                "quality_result_registered": False,
                "output_dir": display_path(OUTPUT_DIR),
                "report_path": display_path(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
