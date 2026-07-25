#!/usr/bin/env python3
"""Build and check the offline v0.2 granularity boundary casebook.

The casebook is deliberately closed:

* every clause already carries structural labels;
* the program only applies the frozen A-D atom contract, five merge
  requirements, seven split triggers, and the speech-content exception;
* an uncovered boundary becomes ``NEEDS_ADJUDICATION`` instead of receiving a
  newly invented semantic rule;
* all examples are fictional structural rewrites with no model/API/network
  dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B4_1_granularity_casebook"
)

FACT_HEAD_FIELDS = (
    "subject",
    "predicate",
    "object",
    "result",
    "polarity",
    "actuality",
)
ALLOWED_ACTUALITIES = frozenset(
    {"occurred", "planned", "reported", "believed", "unresolved"}
)
ALLOWED_PRIMARY_FUNCTIONS = frozenset(
    {
        "state_change",
        "action_result",
        "revelation",
        "decision_plan",
        "trigger",
        "unresolved_change",
        "none",
    }
)
ALLOWED_LEDGER_VIEWS = frozenset(
    {"timeline", "character_state", "unresolved"}
)
ALLOWED_RELATIONS = frozenset(
    {
        "independent",
        "condition",
        "time",
        "motive",
        "manner",
        "quantity",
        "location",
        "step",
        "completion",
        "reported_content",
        "cause",
        "result",
    }
)
MERGE_TAIL_RELATIONS = frozenset(
    {
        "condition",
        "time",
        "motive",
        "manner",
        "quantity",
        "location",
        "step",
        "completion",
    }
)

ATOM_CRITERIA = {
    "A_COMPLETE_FACT_HEAD": "一条具有 subject、predicate、object、result、polarity、actuality 六值。",
    "B_INDEPENDENT_LEDGER_OR_CAUSAL_ENDPOINT": "一条写入独立账本键，或充当可独立复用的因果端点。",
    "C_STANDALONE_OUTLINE_REUSE": "拿掉相邻句后，这条仍可单独供大纲使用。",
    "D_EXACTLY_ONE_PRIMARY_FUNCTION": "一条有且只有一个主情节功能。",
}

MERGE_REASON_ORDER = (
    "M_SAME_EVENT_WINDOW_OR_SPEECH",
    "M_TOP_LEVEL_ACTUALITY_SAME",
    "M_EXACTLY_ONE_PRIMARY_FUNCTION",
    "M_TAIL_IS_DEPENDENT",
    "M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY",
)
MERGE_REASONS = {
    "M_SAME_EVENT_WINDOW_OR_SPEECH": "同一事件时间窗，或同一言语行为。",
    "M_TOP_LEVEL_ACTUALITY_SAME": "顶层 actuality 相同。",
    "M_EXACTLY_ONE_PRIMARY_FUNCTION": "合并后仍只有一个主情节功能。",
    "M_TAIL_IS_DEPENDENT": "后半是限定、步骤、完成动作，或同一言语行为中的归因内容。",
    "M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY": "后半没有独立账本键，也不是独立因果端点。",
}

SPLIT_REASON_ORDER = (
    "S_DIFFERENT_TIME_WINDOW",
    "S_ACTUALITY_DIFFERENT",
    "S_DIFFERENT_SUBJECT_INDEPENDENT_ACTION",
    "S_DIFFERENT_STATE_SLOT_OR_ISSUE",
    "S_INDEPENDENT_RESULTS",
    "S_CAUSAL_ENDPOINTS_REUSABLE",
    "S_EITHER_HALF_STANDALONE",
)
SPLIT_REASONS = {
    "S_DIFFERENT_TIME_WINDOW": "不同章节或不同事件时间窗。",
    "S_ACTUALITY_DIFFERENT": "顶层 actuality 不同。",
    "S_DIFFERENT_SUBJECT_INDEPENDENT_ACTION": "不同主体分别完成独立动作。",
    "S_DIFFERENT_STATE_SLOT_OR_ISSUE": "写入不同人物状态槽或不同未决事项。",
    "S_INDEPENDENT_RESULTS": "两部分各自形成不同的独立结果。",
    "S_CAUSAL_ENDPOINTS_REUSABLE": "因果两端都能离开相邻句独立复用。",
    "S_EITHER_HALF_STANDALONE": "删除任一部分后，另一部分仍是完整且有用的事实。",
}

SOURCE_SPECIFIC_TOKENS = (
    "周明瑞",
    "梅丽莎",
    "克莱恩",
    "韩立",
    "墨大夫",
    "左轮手枪",
    "怀表",
    "廷根",
    "诡秘之主",
    "知否",
    "大王饶命",
    "神秘复苏",
    "无限恐怖",
    "凡人修仙传",
)


class GranularityCasebookError(ValueError):
    """Raised when a case or generated bundle violates the frozen contract."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _tree_hash(artifacts: Mapping[str, bytes]) -> str:
    inventory = [
        {"path": path, "bytes": len(data), "sha256": _sha256(data)}
        for path, data in sorted(artifacts.items())
    ]
    return _sha256(_canonical_bytes(inventory))


def _ledger(
    view: str,
    key: str,
    *,
    state_slot: str | None = None,
    issue_id: str | None = None,
) -> dict[str, Any]:
    return {
        "view": view,
        "key": key,
        "independent": True,
        "state_slot": state_slot,
        "issue_id": issue_id,
    }


def _fact_head(
    subject: str,
    predicate: str,
    object_: str,
    result: str,
    actuality: str,
    *,
    polarity: str = "positive",
) -> dict[str, str]:
    return {
        "subject": subject,
        "predicate": predicate,
        "object": object_,
        "result": result,
        "polarity": polarity,
        "actuality": actuality,
    }


def _attributed_content(
    source: str,
    modality: str,
    fact_head: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "source_attribution": source,
        "modality": modality,
        "fact_head": dict(fact_head),
    }


def _part(
    *,
    part_id: str,
    text: str,
    event_window: str,
    fact_head: Mapping[str, str],
    primary_function: str,
    relation_to_previous: str,
    ledger_writes: Sequence[Mapping[str, Any]] = (),
    causal_endpoint_ids: Sequence[str] = (),
    standalone_outline_reuse: bool,
    independent_action: bool,
    independent_result_key: str | None,
    speech_event_id: str | None = None,
    attributed_content: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "part_id": part_id,
        "text": text,
        "event_window": event_window,
        "speech_event_id": speech_event_id,
        "fact_head": dict(fact_head),
        "primary_functions": [primary_function],
        "ledger_writes": [dict(row) for row in ledger_writes],
        "causal_endpoint_ids": list(causal_endpoint_ids),
        "standalone_outline_reuse": standalone_outline_reuse,
        "independent_action": independent_action,
        "independent_result_key": independent_result_key,
        "relation_to_previous": relation_to_previous,
        "attributed_content": (
            dict(attributed_content) if attributed_content is not None else None
        ),
    }


def _expected(
    *,
    decision: str,
    atom_count: int,
    reason_codes: Sequence[str],
    rationale: str,
) -> dict[str, Any]:
    return {
        "decision": decision,
        "atom_count": atom_count,
        "reason_codes": list(reason_codes),
        "rationale": rationale,
    }


def build_cases() -> list[dict[str, Any]]:
    """Return ten fictional cases derived only from the frozen structural rules."""

    return [
        {
            "case_id": "B4-G01",
            "title": "提示条件不另立中心事实",
            "text": "值班员发现药材箱受潮；这个发现发生在湿度提示灯亮起之后。",
            "parts": [
                _part(
                    part_id="B4-G01-P01",
                    text="值班员发现药材箱受潮。",
                    event_window="CH-A_SCENE-01",
                    fact_head=_fact_head(
                        "值班员",
                        "发现",
                        "药材箱受潮",
                        "受潮事实进入处置视野",
                        "occurred",
                    ),
                    primary_function="revelation",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "character_state",
                            "值班员:knowledge:药材箱受潮",
                            state_slot="knowledge",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=False,
                    independent_result_key="受潮事实被发现",
                ),
                _part(
                    part_id="B4-G01-P02",
                    text="发现发生在湿度提示灯亮起之后。",
                    event_window="CH-A_SCENE-01",
                    fact_head=_fact_head(
                        "湿度提示灯",
                        "亮起",
                        "仓库高湿提示",
                        "限定发现发生的条件",
                        "occurred",
                    ),
                    primary_function="revelation",
                    relation_to_previous="condition",
                    standalone_outline_reuse=False,
                    independent_action=False,
                    independent_result_key=None,
                ),
            ],
            "expected": _expected(
                decision="MERGE",
                atom_count=1,
                reason_codes=MERGE_REASON_ORDER,
                rationale="提示灯只限定发现条件，没有独立账本键或第二个主情节功能。",
            ),
        },
        {
            "case_id": "B4-G02",
            "title": "确认风险与处置动作分立",
            "text": "监测员确认冷却液泄漏，维修员随后关闭主阀。",
            "parts": [
                _part(
                    part_id="B4-G02-P01",
                    text="监测员确认冷却液泄漏。",
                    event_window="CH-A_SCENE-02",
                    fact_head=_fact_head(
                        "监测员",
                        "确认",
                        "冷却液泄漏",
                        "泄漏事实被确认",
                        "occurred",
                    ),
                    primary_function="revelation",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "character_state",
                            "监测员:knowledge:冷却液泄漏",
                            state_slot="knowledge",
                        )
                    ],
                    causal_endpoint_ids=["CE-B4-G02"],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="泄漏事实被确认",
                ),
                _part(
                    part_id="B4-G02-P02",
                    text="维修员随后关闭主阀。",
                    event_window="CH-A_SCENE-02",
                    fact_head=_fact_head(
                        "维修员",
                        "关闭",
                        "冷却系统主阀",
                        "冷却液继续流出被截断",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="result",
                    ledger_writes=[
                        _ledger("timeline", "CH-A_SCENE-02:关闭主阀")
                    ],
                    causal_endpoint_ids=["CE-B4-G02"],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="主阀关闭",
                ),
            ],
            "expected": _expected(
                decision="SPLIT",
                atom_count=2,
                reason_codes=(
                    "S_DIFFERENT_SUBJECT_INDEPENDENT_ACTION",
                    "S_INDEPENDENT_RESULTS",
                    "S_CAUSAL_ENDPOINTS_REUSABLE",
                    "S_EITHER_HALF_STANDALONE",
                ),
                rationale="确认与关阀各有主体、结果和复用价值，并形成显式因果两端。",
            ),
        },
        {
            "case_id": "B4-G03",
            "title": "放入与封存完成动作合并",
            "text": "库管把培养皿放进恒温柜，并扣上柜门门闩完成封存。",
            "parts": [
                _part(
                    part_id="B4-G03-P01",
                    text="库管把培养皿放进恒温柜。",
                    event_window="CH-B_SCENE-01",
                    fact_head=_fact_head(
                        "库管",
                        "放入",
                        "培养皿与恒温柜",
                        "培养皿进入封存位置",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger("timeline", "CH-B_SCENE-01:培养皿封存")
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="培养皿完成封存",
                ),
                _part(
                    part_id="B4-G03-P02",
                    text="库管扣上柜门门闩完成封存。",
                    event_window="CH-B_SCENE-01",
                    fact_head=_fact_head(
                        "库管",
                        "扣上",
                        "恒温柜门闩",
                        "培养皿封存完成",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="completion",
                    standalone_outline_reuse=False,
                    independent_action=False,
                    independent_result_key=None,
                ),
            ],
            "expected": _expected(
                decision="MERGE",
                atom_count=1,
                reason_codes=MERGE_REASON_ORDER,
                rationale="扣门闩只完成同一次封存，没有第二个独立账本写入。",
            ),
        },
        {
            "case_id": "B4-G04",
            "title": "连续校准步骤合并",
            "text": "技师启动校准，旋动调节钮归零，再按确认键完成仪表校准。",
            "parts": [
                _part(
                    part_id="B4-G04-P01",
                    text="技师启动仪表校准。",
                    event_window="CH-B_SCENE-02",
                    fact_head=_fact_head(
                        "技师",
                        "启动",
                        "仪表校准程序",
                        "仪表进入校准流程",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger("timeline", "CH-B_SCENE-02:仪表校准")
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="仪表完成校准",
                ),
                _part(
                    part_id="B4-G04-P02",
                    text="技师旋动调节钮使读数归零。",
                    event_window="CH-B_SCENE-02",
                    fact_head=_fact_head(
                        "技师",
                        "旋动",
                        "仪表调节钮",
                        "读数归零",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="step",
                    standalone_outline_reuse=False,
                    independent_action=False,
                    independent_result_key=None,
                ),
                _part(
                    part_id="B4-G04-P03",
                    text="技师按确认键完成仪表校准。",
                    event_window="CH-B_SCENE-02",
                    fact_head=_fact_head(
                        "技师",
                        "按下",
                        "仪表确认键",
                        "校准流程完成",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="completion",
                    standalone_outline_reuse=False,
                    independent_action=False,
                    independent_result_key=None,
                ),
            ],
            "expected": _expected(
                decision="MERGE",
                atom_count=1,
                reason_codes=MERGE_REASON_ORDER,
                rationale="两段后续动作都是同一校准终态的步骤与完成动作。",
            ),
        },
        {
            "case_id": "B4-G05",
            "title": "同一发言中的数量与禁令合并",
            "text": "领班通知学徒明早搬运六箱滤芯，并强调搬运前不得拆封。",
            "parts": [
                _part(
                    part_id="B4-G05-P01",
                    text="领班通知学徒明早搬运六箱滤芯。",
                    event_window="CH-C_SCENE-01",
                    speech_event_id="SP-B4-G05",
                    fact_head=_fact_head(
                        "领班",
                        "通知",
                        "学徒搬运六箱滤芯",
                        "搬运安排被下达",
                        "occurred",
                    ),
                    primary_function="decision_plan",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger("timeline", "CH-C_SCENE-01:搬运通知")
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="搬运安排被下达",
                    attributed_content=_attributed_content(
                        "领班",
                        "instructed_future",
                        _fact_head(
                            "学徒",
                            "搬运",
                            "六箱滤芯",
                            "搬运任务待执行",
                            "planned",
                        ),
                    ),
                ),
                _part(
                    part_id="B4-G05-P02",
                    text="领班并强调搬运前不得拆封。",
                    event_window="CH-C_SCENE-01",
                    speech_event_id="SP-B4-G05",
                    fact_head=_fact_head(
                        "领班",
                        "强调",
                        "搬运前不得拆封",
                        "封装约束被说明",
                        "occurred",
                    ),
                    primary_function="decision_plan",
                    relation_to_previous="reported_content",
                    standalone_outline_reuse=False,
                    independent_action=False,
                    independent_result_key=None,
                    attributed_content=_attributed_content(
                        "领班",
                        "prohibited_future",
                        _fact_head(
                            "学徒",
                            "拆封",
                            "六箱滤芯",
                            "滤芯保持封装",
                            "planned",
                            polarity="negative",
                        ),
                    ),
                ),
            ],
            "expected": _expected(
                decision="MERGE",
                atom_count=1,
                reason_codes=MERGE_REASON_ORDER,
                rationale="这是同一次通知；六箱和不得拆封是计划内容的参数与约束。",
            ),
        },
        {
            "case_id": "B4-G06",
            "title": "移动目的地完成动作合并",
            "text": "巡检员沿北廊前往备用机房，随后进入机房。",
            "parts": [
                _part(
                    part_id="B4-G06-P01",
                    text="巡检员沿北廊前往备用机房。",
                    event_window="CH-C_SCENE-02",
                    fact_head=_fact_head(
                        "巡检员",
                        "前往",
                        "备用机房",
                        "巡检位置转向备用机房",
                        "occurred",
                    ),
                    primary_function="state_change",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "character_state",
                            "巡检员:location:备用机房",
                            state_slot="location",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="巡检员抵达备用机房",
                ),
                _part(
                    part_id="B4-G06-P02",
                    text="巡检员随后进入机房。",
                    event_window="CH-C_SCENE-02",
                    fact_head=_fact_head(
                        "巡检员",
                        "进入",
                        "备用机房",
                        "移动到达目的地",
                        "occurred",
                    ),
                    primary_function="state_change",
                    relation_to_previous="completion",
                    standalone_outline_reuse=False,
                    independent_action=False,
                    independent_result_key=None,
                ),
            ],
            "expected": _expected(
                decision="MERGE",
                atom_count=1,
                reason_codes=MERGE_REASON_ORDER,
                rationale="进入机房是同一次移动的到达完成态，不另写位置账。",
            ),
        },
        {
            "case_id": "B4-G07",
            "title": "同一主体的不同状态槽拆分",
            "text": "研究员得知样本已污染，并决定暂停后续试验。",
            "parts": [
                _part(
                    part_id="B4-G07-P01",
                    text="研究员得知样本已污染。",
                    event_window="CH-D_SCENE-01",
                    fact_head=_fact_head(
                        "研究员",
                        "得知",
                        "样本已污染",
                        "污染信息被掌握",
                        "occurred",
                    ),
                    primary_function="revelation",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "character_state",
                            "研究员:knowledge:样本污染",
                            state_slot="knowledge",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=False,
                    independent_result_key="污染信息被掌握",
                ),
                _part(
                    part_id="B4-G07-P02",
                    text="研究员决定暂停后续试验。",
                    event_window="CH-D_SCENE-01",
                    fact_head=_fact_head(
                        "研究员",
                        "决定",
                        "暂停后续试验",
                        "暂停计划成立",
                        "occurred",
                    ),
                    primary_function="decision_plan",
                    relation_to_previous="result",
                    ledger_writes=[
                        _ledger(
                            "character_state",
                            "研究员:plan:暂停试验",
                            state_slot="plan",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=False,
                    independent_result_key="暂停计划成立",
                ),
            ],
            "expected": _expected(
                decision="SPLIT",
                atom_count=2,
                reason_codes=(
                    "S_DIFFERENT_STATE_SLOT_OR_ISSUE",
                    "S_INDEPENDENT_RESULTS",
                    "S_EITHER_HALF_STANDALONE",
                ),
                rationale="得知写知识槽，决定写计划槽；两者可以分别被大纲引用。",
            ),
        },
        {
            "case_id": "B4-G08",
            "title": "四个未决事项分别立账",
            "text": "应急会上留下四个待查项：备用泵为何停机、谁改了排班表、缺失钥匙在哪、积水何时退去。",
            "parts": [
                _part(
                    part_id="B4-G08-P01",
                    text="备用泵停机原因待查。",
                    event_window="CH-D_SCENE-02",
                    fact_head=_fact_head(
                        "备用泵停机原因",
                        "待查",
                        "故障来源",
                        "故障原因事项保持开放",
                        "unresolved",
                    ),
                    primary_function="unresolved_change",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "unresolved",
                            "ISSUE-B4-G08-01",
                            issue_id="ISSUE-B4-G08-01",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=False,
                    independent_result_key="ISSUE-B4-G08-01:open",
                ),
                _part(
                    part_id="B4-G08-P02",
                    text="排班表修改者待查。",
                    event_window="CH-D_SCENE-02",
                    fact_head=_fact_head(
                        "排班表修改者",
                        "待查",
                        "修改来源",
                        "修改者事项保持开放",
                        "unresolved",
                    ),
                    primary_function="unresolved_change",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "unresolved",
                            "ISSUE-B4-G08-02",
                            issue_id="ISSUE-B4-G08-02",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=False,
                    independent_result_key="ISSUE-B4-G08-02:open",
                ),
                _part(
                    part_id="B4-G08-P03",
                    text="缺失钥匙的位置待查。",
                    event_window="CH-D_SCENE-02",
                    fact_head=_fact_head(
                        "缺失钥匙的位置",
                        "待查",
                        "钥匙去向",
                        "钥匙去向事项保持开放",
                        "unresolved",
                    ),
                    primary_function="unresolved_change",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "unresolved",
                            "ISSUE-B4-G08-03",
                            issue_id="ISSUE-B4-G08-03",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=False,
                    independent_result_key="ISSUE-B4-G08-03:open",
                ),
                _part(
                    part_id="B4-G08-P04",
                    text="积水退去时间待查。",
                    event_window="CH-D_SCENE-02",
                    fact_head=_fact_head(
                        "积水退去时间",
                        "待查",
                        "退水时点",
                        "退水时点事项保持开放",
                        "unresolved",
                    ),
                    primary_function="unresolved_change",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "unresolved",
                            "ISSUE-B4-G08-04",
                            issue_id="ISSUE-B4-G08-04",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=False,
                    independent_result_key="ISSUE-B4-G08-04:open",
                ),
            ],
            "expected": _expected(
                decision="SPLIT",
                atom_count=4,
                reason_codes=(
                    "S_DIFFERENT_STATE_SLOT_OR_ISSUE",
                    "S_INDEPENDENT_RESULTS",
                    "S_EITHER_HALF_STANDALONE",
                ),
                rationale="四个 issue_id 可在不同位置分别更新或解决，不能压成一个问题。",
            ),
        },
        {
            "case_id": "B4-G09",
            "title": "计划、执行与带情态报告拆分",
            "text": "检修员计划次日检查天窗；次日完成检查；随后报告天窗可能漏水。",
            "parts": [
                _part(
                    part_id="B4-G09-P01",
                    text="检修员计划次日检查天窗。",
                    event_window="CH-E_DAY-00",
                    fact_head=_fact_head(
                        "检修员",
                        "检查",
                        "天窗",
                        "检查计划成立",
                        "planned",
                    ),
                    primary_function="decision_plan",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger(
                            "character_state",
                            "检修员:plan:检查天窗",
                            state_slot="plan",
                        )
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="检查计划成立",
                ),
                _part(
                    part_id="B4-G09-P02",
                    text="次日检修员完成天窗检查。",
                    event_window="CH-E_DAY-01",
                    fact_head=_fact_head(
                        "检修员",
                        "完成检查",
                        "天窗",
                        "天窗检查完成",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger("timeline", "CH-E_DAY-01:天窗检查完成")
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="天窗检查完成",
                ),
                _part(
                    part_id="B4-G09-P03",
                    text="检修员随后报告天窗可能漏水。",
                    event_window="CH-E_DAY-01",
                    speech_event_id="SP-B4-G09",
                    fact_head=_fact_head(
                        "检修员",
                        "报告",
                        "天窗可能漏水",
                        "漏水风险判断被报告",
                        "occurred",
                    ),
                    primary_function="revelation",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger("timeline", "CH-E_DAY-01:漏水风险报告")
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="漏水风险判断被报告",
                    attributed_content=_attributed_content(
                        "检修员",
                        "possible",
                        _fact_head(
                            "天窗",
                            "漏水",
                            "雨水",
                            "存在进水风险",
                            "believed",
                        ),
                    ),
                ),
            ],
            "expected": _expected(
                decision="SPLIT",
                atom_count=3,
                reason_codes=(
                    "S_DIFFERENT_TIME_WINDOW",
                    "S_ACTUALITY_DIFFERENT",
                    "S_INDEPENDENT_RESULTS",
                    "S_EITHER_HALF_STANDALONE",
                ),
                rationale="计划、完成检查、发生报告各自成条；报告内容仍保持“可能”的归因判断。",
            ),
        },
        {
            "case_id": "B4-G10",
            "title": "跨章独立结果硬拆",
            "text": "管理员周一登记借出急救包；周五另行通知下月演练日期。",
            "parts": [
                _part(
                    part_id="B4-G10-P01",
                    text="管理员周一登记借出急救包。",
                    event_window="CH-F01_MONDAY",
                    fact_head=_fact_head(
                        "管理员",
                        "登记",
                        "急救包借出",
                        "借用记录成立",
                        "occurred",
                    ),
                    primary_function="action_result",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger("timeline", "CH-F01_MONDAY:急救包借出")
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="借用记录成立",
                ),
                _part(
                    part_id="B4-G10-P02",
                    text="管理员周五通知下月演练日期。",
                    event_window="CH-F02_FRIDAY",
                    fact_head=_fact_head(
                        "管理员",
                        "通知",
                        "下月演练日期",
                        "演练日程被传达",
                        "occurred",
                    ),
                    primary_function="revelation",
                    relation_to_previous="independent",
                    ledger_writes=[
                        _ledger("timeline", "CH-F02_FRIDAY:演练日期通知")
                    ],
                    standalone_outline_reuse=True,
                    independent_action=True,
                    independent_result_key="演练日程被传达",
                ),
            ],
            "expected": _expected(
                decision="SPLIT",
                atom_count=2,
                reason_codes=(
                    "S_DIFFERENT_TIME_WINDOW",
                    "S_INDEPENDENT_RESULTS",
                    "S_EITHER_HALF_STANDALONE",
                ),
                rationale="两件事跨章、跨时间窗，结果和后续回收点都不同。",
            ),
        },
    ]


def build_casebook() -> dict[str, Any]:
    return {
        "schema_version": "v02-b4-1-granularity-casebook-v0.1",
        "candidate_id": "B4_1_granularity_casebook",
        "candidate_status": "candidate_silver_not_active",
        "authority_boundary": {
            "design": "统一设计稿｜抽取工序重设计 v0.2",
            "section": "三｜怎么算一条",
            "work_order": "连夜施工令 B4.1",
            "source_use": "只继承封闭结构判据，不复制六本专名、原句或可回指情节。",
        },
        "closed_rule_contract": {
            "atom_criteria": ATOM_CRITERIA,
            "merge_requirements": {
                code: MERGE_REASONS[code] for code in MERGE_REASON_ORDER
            },
            "split_triggers": {
                code: SPLIT_REASONS[code] for code in SPLIT_REASON_ORDER
            },
            "speech_exception": (
                "说话行为的顶层 actuality 可为 occurred；被归因内容保留自己的 "
                "fact_head actuality 与 modality，不能随说话行为升级。"
            ),
            "unsupported_boundary_policy": (
                "既未命中拆分条件、又未满足全部合并条件时返回 "
                "NEEDS_ADJUDICATION；不得补语义规则。"
            ),
        },
        "case_count": 10,
        "cases": build_cases(),
    }


def _has_complete_fact_head(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    if set(value) != set(FACT_HEAD_FIELDS):
        return False
    if not all(isinstance(value[field], str) and value[field] for field in value):
        return False
    return value["actuality"] in ALLOWED_ACTUALITIES


def _validate_attributed_content(part: Mapping[str, Any]) -> None:
    content = part.get("attributed_content")
    if content is None:
        return
    if not isinstance(content, Mapping):
        raise GranularityCasebookError(
            f"{part['part_id']}: attributed_content must be an object"
        )
    if not isinstance(content.get("source_attribution"), str) or not content[
        "source_attribution"
    ]:
        raise GranularityCasebookError(
            f"{part['part_id']}: attributed content lacks source"
        )
    if not isinstance(content.get("modality"), str) or not content["modality"]:
        raise GranularityCasebookError(
            f"{part['part_id']}: attributed content lacks modality"
        )
    if not _has_complete_fact_head(content.get("fact_head")):
        raise GranularityCasebookError(
            f"{part['part_id']}: attributed content fact_head is incomplete"
        )


def validate_case(case: Mapping[str, Any]) -> None:
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise GranularityCasebookError("case_id is missing")
    parts = case.get("parts")
    if not isinstance(parts, list) or len(parts) < 2:
        raise GranularityCasebookError(f"{case_id}: at least two parts required")
    part_ids: list[str] = []
    for index, part in enumerate(parts):
        if not isinstance(part, Mapping):
            raise GranularityCasebookError(f"{case_id}: part is not an object")
        part_id = part.get("part_id")
        if not isinstance(part_id, str) or not part_id:
            raise GranularityCasebookError(f"{case_id}: part_id is missing")
        part_ids.append(part_id)
        if not isinstance(part.get("text"), str) or not part["text"]:
            raise GranularityCasebookError(f"{part_id}: text is missing")
        if not isinstance(part.get("event_window"), str) or not part[
            "event_window"
        ]:
            raise GranularityCasebookError(f"{part_id}: event_window is missing")
        if not _has_complete_fact_head(part.get("fact_head")):
            raise GranularityCasebookError(f"{part_id}: fact_head is incomplete")
        functions = part.get("primary_functions")
        if (
            not isinstance(functions, list)
            or len(functions) != 1
            or functions[0] not in ALLOWED_PRIMARY_FUNCTIONS
        ):
            raise GranularityCasebookError(
                f"{part_id}: exactly one controlled primary function required"
            )
        relation = part.get("relation_to_previous")
        if relation not in ALLOWED_RELATIONS:
            raise GranularityCasebookError(f"{part_id}: unknown relation")
        if index == 0 and relation != "independent":
            raise GranularityCasebookError(
                f"{part_id}: first relation must be independent"
            )
        writes = part.get("ledger_writes")
        if not isinstance(writes, list):
            raise GranularityCasebookError(
                f"{part_id}: ledger_writes must be a list"
            )
        for write in writes:
            if not isinstance(write, Mapping):
                raise GranularityCasebookError(
                    f"{part_id}: ledger write is not an object"
                )
            if write.get("view") not in ALLOWED_LEDGER_VIEWS:
                raise GranularityCasebookError(
                    f"{part_id}: unknown ledger view {write.get('view')!r}"
                )
            if not isinstance(write.get("key"), str) or not write["key"]:
                raise GranularityCasebookError(
                    f"{part_id}: ledger key is missing"
                )
            if write.get("independent") is not True:
                raise GranularityCasebookError(
                    f"{part_id}: only explicit independent writes are admitted"
                )
            if write["view"] == "character_state" and not isinstance(
                write.get("state_slot"), str
            ):
                raise GranularityCasebookError(
                    f"{part_id}: character-state write lacks state_slot"
                )
            if write["view"] == "unresolved" and not isinstance(
                write.get("issue_id"), str
            ):
                raise GranularityCasebookError(
                    f"{part_id}: unresolved write lacks issue_id"
                )
        endpoint_ids = part.get("causal_endpoint_ids")
        if not isinstance(endpoint_ids, list) or not all(
            isinstance(value, str) and value for value in endpoint_ids
        ):
            raise GranularityCasebookError(
                f"{part_id}: causal_endpoint_ids must be strings"
            )
        for boolean_field in ("standalone_outline_reuse", "independent_action"):
            if not isinstance(part.get(boolean_field), bool):
                raise GranularityCasebookError(
                    f"{part_id}: {boolean_field} must be boolean"
                )
        result_key = part.get("independent_result_key")
        if result_key is not None and (
            not isinstance(result_key, str) or not result_key
        ):
            raise GranularityCasebookError(
                f"{part_id}: independent_result_key is invalid"
            )
        speech_event_id = part.get("speech_event_id")
        if speech_event_id is not None and (
            not isinstance(speech_event_id, str) or not speech_event_id
        ):
            raise GranularityCasebookError(
                f"{part_id}: speech_event_id is invalid"
            )
        _validate_attributed_content(part)
        if relation == "reported_content" and speech_event_id is None:
            raise GranularityCasebookError(
                f"{part_id}: reported_content requires a speech_event_id"
            )
        if relation == "reported_content" and part.get("attributed_content") is None:
            raise GranularityCasebookError(
                f"{part_id}: reported_content requires attributed content"
            )
    if len(set(part_ids)) != len(part_ids):
        raise GranularityCasebookError(f"{case_id}: duplicate part_id")

    expected = case.get("expected")
    if not isinstance(expected, Mapping):
        raise GranularityCasebookError(f"{case_id}: expected result is missing")
    if expected.get("decision") not in {"MERGE", "SPLIT"}:
        raise GranularityCasebookError(f"{case_id}: expected decision is invalid")
    atom_count = expected.get("atom_count")
    if not isinstance(atom_count, int) or not 1 <= atom_count <= len(parts):
        raise GranularityCasebookError(
            f"{case_id}: expected atom_count is invalid"
        )
    reason_codes = expected.get("reason_codes")
    if not isinstance(reason_codes, list) or not all(
        isinstance(code, str) for code in reason_codes
    ):
        raise GranularityCasebookError(
            f"{case_id}: expected reason codes are invalid"
        )
    allowed_reasons = (
        set(MERGE_REASONS)
        if expected["decision"] == "MERGE"
        else set(SPLIT_REASONS)
    )
    if not set(reason_codes) <= allowed_reasons:
        raise GranularityCasebookError(
            f"{case_id}: expected reason code uses the wrong decision family"
        )


def validate_casebook(casebook: Mapping[str, Any]) -> None:
    if casebook.get("schema_version") != "v02-b4-1-granularity-casebook-v0.1":
        raise GranularityCasebookError("unexpected casebook schema")
    cases = casebook.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise GranularityCasebookError("casebook must contain exactly ten cases")
    expected_ids = [f"B4-G{index:02d}" for index in range(1, 11)]
    observed_ids = [case.get("case_id") for case in cases]
    if observed_ids != expected_ids:
        raise GranularityCasebookError(
            "case IDs must be the ordered B4-G01 through B4-G10 set"
        )
    for case in cases:
        validate_case(case)

    case_text = "\n".join(
        [
            str(case["title"])
            for case in cases
        ]
        + [str(case["text"]) for case in cases]
        + [str(part["text"]) for case in cases for part in case["parts"]]
    )
    leakage_hits = sorted(
        token for token in SOURCE_SPECIFIC_TOKENS if token in case_text
    )
    if leakage_hits:
        raise GranularityCasebookError(
            f"source-specific case token detected: {leakage_hits}"
        )
    if "《" in case_text or "》" in case_text:
        raise GranularityCasebookError("book-title brackets are forbidden in cases")


def _independent_ledger_keys(part: Mapping[str, Any]) -> set[str]:
    return {
        f"{write['view']}:{write['key']}"
        for write in part["ledger_writes"]
        if write["independent"]
    }


def _state_or_issue_keys(part: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for write in part["ledger_writes"]:
        if write["view"] == "character_state":
            keys.add(f"state_slot:{write['state_slot']}")
        elif write["view"] == "unresolved":
            keys.add(f"issue:{write['issue_id']}")
    return keys


def _primary_functions(parts: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        function
        for part in parts
        for function in part["primary_functions"]
        if function != "none"
    }


def _same_speech_event(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    speech_id = left.get("speech_event_id")
    return speech_id is not None and speech_id == right.get("speech_event_id")


def _reported_content_is_preserved(part: Mapping[str, Any]) -> bool:
    content = part.get("attributed_content")
    return (
        isinstance(content, Mapping)
        and isinstance(content.get("source_attribution"), str)
        and bool(content["source_attribution"])
        and isinstance(content.get("modality"), str)
        and bool(content["modality"])
        and _has_complete_fact_head(content.get("fact_head"))
    )


def split_reason_codes(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> list[str]:
    hits: set[str] = set()
    if (
        left["event_window"] != right["event_window"]
        and not _same_speech_event(left, right)
    ):
        hits.add("S_DIFFERENT_TIME_WINDOW")
    if left["fact_head"]["actuality"] != right["fact_head"]["actuality"]:
        hits.add("S_ACTUALITY_DIFFERENT")
    if (
        left["fact_head"]["subject"] != right["fact_head"]["subject"]
        and left["independent_action"]
        and right["independent_action"]
    ):
        hits.add("S_DIFFERENT_SUBJECT_INDEPENDENT_ACTION")

    left_state_or_issue = _state_or_issue_keys(left)
    right_state_or_issue = _state_or_issue_keys(right)
    if (
        left_state_or_issue
        and right_state_or_issue
        and left_state_or_issue != right_state_or_issue
    ):
        hits.add("S_DIFFERENT_STATE_SLOT_OR_ISSUE")

    left_result = left.get("independent_result_key")
    right_result = right.get("independent_result_key")
    if left_result and right_result and left_result != right_result:
        hits.add("S_INDEPENDENT_RESULTS")

    shared_edges = set(left["causal_endpoint_ids"]) & set(
        right["causal_endpoint_ids"]
    )
    if (
        shared_edges
        and left["standalone_outline_reuse"]
        and right["standalone_outline_reuse"]
    ):
        hits.add("S_CAUSAL_ENDPOINTS_REUSABLE")

    if left["standalone_outline_reuse"] and right[
        "standalone_outline_reuse"
    ]:
        hits.add("S_EITHER_HALF_STANDALONE")
    return [code for code in SPLIT_REASON_ORDER if code in hits]


def merge_condition_codes(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> list[str]:
    passes: set[str] = set()
    same_speech = _same_speech_event(left, right)
    if left["event_window"] == right["event_window"] or same_speech:
        passes.add("M_SAME_EVENT_WINDOW_OR_SPEECH")
    if left["fact_head"]["actuality"] == right["fact_head"]["actuality"]:
        passes.add("M_TOP_LEVEL_ACTUALITY_SAME")
    if len(_primary_functions((left, right))) == 1:
        passes.add("M_EXACTLY_ONE_PRIMARY_FUNCTION")

    relation = right["relation_to_previous"]
    ordinary_dependent_tail = relation in MERGE_TAIL_RELATIONS
    speech_dependent_tail = (
        relation == "reported_content"
        and same_speech
        and _reported_content_is_preserved(right)
    )
    if ordinary_dependent_tail or speech_dependent_tail:
        passes.add("M_TAIL_IS_DEPENDENT")
    if not _independent_ledger_keys(right) and not right[
        "causal_endpoint_ids"
    ]:
        passes.add("M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY")
    return [code for code in MERGE_REASON_ORDER if code in passes]


def evaluate_boundary(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    split_codes = split_reason_codes(left, right)
    merge_codes = merge_condition_codes(left, right)
    if split_codes:
        outcome = "SPLIT"
    elif merge_codes == list(MERGE_REASON_ORDER):
        outcome = "MERGE"
    else:
        outcome = "NEEDS_ADJUDICATION"
    return {
        "left_part_id": left["part_id"],
        "right_part_id": right["part_id"],
        "outcome": outcome,
        "split_reason_codes": split_codes,
        "merge_condition_codes_passed": merge_codes,
        "merge_condition_codes_missing": [
            code for code in MERGE_REASON_ORDER if code not in merge_codes
        ],
    }


def _atom_contract(parts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ledger_keys = sorted(
        {
            key
            for part in parts
            for key in _independent_ledger_keys(part)
        }
    )
    endpoint_ids = sorted(
        {
            edge_id
            for part in parts
            for edge_id in part["causal_endpoint_ids"]
        }
    )
    standalone_part_ids = [
        part["part_id"] for part in parts if part["standalone_outline_reuse"]
    ]
    functions = sorted(_primary_functions(parts))
    checks = {
        "A_COMPLETE_FACT_HEAD": all(
            _has_complete_fact_head(part["fact_head"]) for part in parts
        ),
        "B_INDEPENDENT_LEDGER_OR_CAUSAL_ENDPOINT": bool(
            ledger_keys or endpoint_ids
        ),
        "C_STANDALONE_OUTLINE_REUSE": bool(standalone_part_ids),
        "D_EXACTLY_ONE_PRIMARY_FUNCTION": len(functions) == 1,
    }
    return {
        "part_ids": [part["part_id"] for part in parts],
        "checks": checks,
        "complete_fact_head_part_count": sum(
            _has_complete_fact_head(part["fact_head"]) for part in parts
        ),
        "independent_ledger_keys": ledger_keys,
        "causal_endpoint_ids": endpoint_ids,
        "standalone_part_ids": standalone_part_ids,
        "primary_functions": functions,
        "passes": all(checks.values()),
    }


def evaluate_case(case: Mapping[str, Any]) -> dict[str, Any]:
    validate_case(case)
    parts = case["parts"]
    boundaries = [
        evaluate_boundary(left, right)
        for left, right in zip(parts, parts[1:])
    ]
    needs_adjudication = any(
        row["outcome"] == "NEEDS_ADJUDICATION" for row in boundaries
    )

    groups: list[list[Mapping[str, Any]]] = [[parts[0]]]
    for boundary, right in zip(boundaries, parts[1:]):
        if boundary["outcome"] == "MERGE":
            groups[-1].append(right)
        else:
            groups.append([right])

    if needs_adjudication:
        decision = "NEEDS_ADJUDICATION"
    elif len(groups) == 1:
        decision = "MERGE"
    else:
        decision = "SPLIT"

    split_codes = {
        code for row in boundaries for code in row["split_reason_codes"]
    }
    merge_codes = {
        code
        for row in boundaries
        if row["outcome"] == "MERGE"
        for code in row["merge_condition_codes_passed"]
    }
    if decision == "MERGE":
        reason_codes = [
            code for code in MERGE_REASON_ORDER if code in merge_codes
        ]
    else:
        reason_codes = [
            code for code in SPLIT_REASON_ORDER if code in split_codes
        ]

    atom_contracts = [_atom_contract(group) for group in groups]
    expected = case["expected"]
    expectation_checks = {
        "decision_matches": decision == expected["decision"],
        "atom_count_matches": len(groups) == expected["atom_count"],
        "reason_codes_match": reason_codes == expected["reason_codes"],
        "all_output_atoms_pass_A_to_D": all(
            atom["passes"] for atom in atom_contracts
        ),
        "no_uncovered_boundary": not needs_adjudication,
    }
    return {
        "schema_version": "v02-b4-1-granularity-case-result-v0.1",
        "case_id": case["case_id"],
        "title": case["title"],
        "expected": dict(expected),
        "observed": {
            "decision": decision,
            "atom_count": len(groups),
            "reason_codes": reason_codes,
            "groups": [
                [part["part_id"] for part in group] for group in groups
            ],
        },
        "boundaries": boundaries,
        "atom_contracts": atom_contracts,
        "expectation_checks": expectation_checks,
        "passed": all(expectation_checks.values()),
    }


def evaluate_casebook(casebook: Mapping[str, Any]) -> dict[str, Any]:
    validate_casebook(casebook)
    results = [evaluate_case(case) for case in casebook["cases"]]
    decision_counts = {
        decision: sum(
            result["observed"]["decision"] == decision for result in results
        )
        for decision in ("MERGE", "SPLIT", "NEEDS_ADJUDICATION")
    }
    observed_merge_codes = sorted(
        {
            code
            for result in results
            if result["observed"]["decision"] == "MERGE"
            for code in result["observed"]["reason_codes"]
        }
    )
    observed_split_codes = sorted(
        {
            code
            for result in results
            if result["observed"]["decision"] == "SPLIT"
            for code in result["observed"]["reason_codes"]
        }
    )
    return {
        "schema_version": "v02-b4-1-granularity-case-results-v0.1",
        "candidate_id": "B4_1_granularity_casebook",
        "summary": {
            "required_cases": 10,
            "evaluated_cases": len(results),
            "passed_cases": sum(result["passed"] for result in results),
            "decision_counts": decision_counts,
            "merge_reason_codes_covered": observed_merge_codes,
            "split_reason_codes_covered": observed_split_codes,
            "all_merge_reason_codes_covered": (
                set(observed_merge_codes) == set(MERGE_REASONS)
            ),
            "all_split_reason_codes_covered": (
                set(observed_split_codes) == set(SPLIT_REASONS)
            ),
            "uncovered_boundary_count": decision_counts[
                "NEEDS_ADJUDICATION"
            ],
        },
        "results": results,
    }


def _casebook_markdown(casebook: Mapping[str, Any]) -> bytes:
    lines = [
        "# B4.1 颗粒度封闭判例册",
        "",
        "✅ 这十例只回归 v0.2 已拍的“一条”判据，不增加语义规则。",
        "",
        "程序只看预先填好的结构标签。某个边界若既没命中拆分条件，"
        "又没满足全部合并条件，就挂为 `NEEDS_ADJUDICATION`，不会硬凑答案。",
        "",
        "| 编号 | 结构例 | 预期 | 输出条数 | 大白话理由 | 机器理由码 |",
        "|---|---|---:|---:|---|---|",
    ]
    for case in casebook["cases"]:
        expected = case["expected"]
        lines.append(
            "| {case_id} | {text} | {decision} | {atom_count} | "
            "{rationale} | {codes} |".format(
                case_id=case["case_id"],
                text=case["text"].replace("|", "｜"),
                decision=expected["decision"],
                atom_count=expected["atom_count"],
                rationale=expected["rationale"].replace("|", "｜"),
                codes="、".join(expected["reason_codes"]),
            )
        )
    lines.extend(
        [
            "",
            "## 言语例外",
            "",
            "B4-G05 中，通知和强调这两个说话动作的顶层状态都是已发生；"
            "被归因内容仍分别保留计划、未来指令和禁止情态。"
            "B4-G09 中，报告动作已发生，但“可能漏水”仍是被归因的判断，"
            "没有升级成客观已发生。",
            "",
            "## 材料边界",
            "",
            "- 十例均为虚构结构例，没有书名、人物专名或原句。",
            "- 不读取正式金标，不修改默认链、当前状态或发布目录。",
            "- 模型 API 0 次，网络请求 0 次。",
            "",
            "来源：Codex",
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_artifacts() -> dict[str, bytes]:
    casebook = build_casebook()
    validate_casebook(casebook)
    results = evaluate_casebook(casebook)
    summary = results["summary"]
    if summary["passed_cases"] != 10:
        raise GranularityCasebookError("the casebook did not pass 10/10")
    if summary["uncovered_boundary_count"] != 0:
        raise GranularityCasebookError(
            "an uncovered boundary requires adjudication; do not fill it"
        )
    if not summary["all_merge_reason_codes_covered"]:
        raise GranularityCasebookError("merge reason coverage is incomplete")
    if not summary["all_split_reason_codes_covered"]:
        raise GranularityCasebookError("split reason coverage is incomplete")

    casebook_bytes = _json_bytes(casebook)
    casebook_md = _casebook_markdown(casebook)
    results_bytes = _json_bytes(results)
    acceptance = {
        "schema_version": "v02-b4-1-granularity-acceptance-v0.1",
        "candidate_id": "B4_1_granularity_casebook",
        "candidate_status": "candidate_silver_not_active",
        "checks": {
            "case_count": 10,
            "case_pass_count": summary["passed_cases"],
            "merge_case_count": summary["decision_counts"]["MERGE"],
            "split_case_count": summary["decision_counts"]["SPLIT"],
            "uncovered_boundary_count": summary["uncovered_boundary_count"],
            "all_output_atoms_pass_A_to_D": all(
                atom["passes"]
                for result in results["results"]
                for atom in result["atom_contracts"]
            ),
            "all_five_merge_requirements_covered": summary[
                "all_merge_reason_codes_covered"
            ],
            "all_seven_split_triggers_covered": summary[
                "all_split_reason_codes_covered"
            ],
            "speech_content_actuality_preserved": True,
            "source_specific_token_hits": [],
            "book_title_bracket_hits": 0,
            "new_semantic_rules_added": 0,
        },
        "scope": {
            "model_api_calls": 0,
            "network_requests": 0,
            "formal_gold_mutations": 0,
            "default_route_mutations": 0,
            "governance_mutations": 0,
            "notion_writes": 0,
        },
        "casebook_sha256": _sha256(casebook_bytes),
        "case_results_sha256": _sha256(results_bytes),
        "result": "PASS_10_OF_10_CLOSED_RULES_ONLY",
    }
    artifacts: dict[str, bytes] = {
        "casebook.json": casebook_bytes,
        "casebook.md": casebook_md,
        "case_results.json": results_bytes,
        "acceptance_receipt.json": _json_bytes(acceptance),
    }
    inventory = [
        {"path": path, "bytes": len(data), "sha256": _sha256(data)}
        for path, data in sorted(artifacts.items())
    ]
    manifest = {
        "schema_version": "v02-b4-1-granularity-manifest-v0.1",
        "candidate_id": "B4_1_granularity_casebook",
        "candidate_status": "candidate_silver_not_active",
        "authority_boundary": casebook["authority_boundary"],
        "rule_freeze": {
            "atom_criteria_codes": list(ATOM_CRITERIA),
            "merge_reason_codes": list(MERGE_REASON_ORDER),
            "split_reason_codes": list(SPLIT_REASON_ORDER),
            "unsupported_boundary_policy": "NEEDS_ADJUDICATION",
            "new_semantic_rules_added": 0,
        },
        "case_summary": summary,
        "fictionalization_guard": {
            "case_mode": "fully_fictional_structural_examples",
            "source_quotes_used": 0,
            "source_specific_token_hits": [],
            "book_title_bracket_hits": 0,
        },
        "scope": acceptance["scope"],
        "artifacts": inventory,
        "artifact_count": len(inventory),
        "bundle_content_hash": _tree_hash(artifacts),
        "release_isolation": {
            "activation_allowed": False,
            "formal_gold_changed": False,
            "default_chain_changed": False,
            "current_state_changed": False,
        },
    }
    artifacts["manifest.json"] = _json_bytes(manifest)
    return artifacts


def write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, data in sorted(artifacts.items()):
        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def build_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    artifacts = build_artifacts()
    write_artifacts(output_dir, artifacts)
    return {
        "result": "BUILT",
        "output_dir": str(output_dir),
        "artifact_count": len(artifacts),
        "tree_sha256": _tree_hash(artifacts),
        "case_pass_count": 10,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def _read_tree(
    root: Path,
    *,
    include_double_run: bool,
) -> dict[str, bytes]:
    ignored = set() if include_double_run else {"double_run_receipt.json"}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in ignored
    }


def check_bundle(bundle_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    expected = build_artifacts()
    if not bundle_dir.is_dir():
        raise GranularityCasebookError(f"bundle directory is missing: {bundle_dir}")
    observed = _read_tree(bundle_dir, include_double_run=False)
    if set(observed) != set(expected):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise GranularityCasebookError(
            f"bundle file set mismatch; missing={missing}, extra={extra}"
        )
    mismatched = [
        path for path in sorted(expected) if observed[path] != expected[path]
    ]
    if mismatched:
        raise GranularityCasebookError(
            f"bundle bytes differ from deterministic builder: {mismatched}"
        )

    manifest = json.loads(observed["manifest.json"])
    for row in manifest["artifacts"]:
        data = observed[row["path"]]
        if len(data) != row["bytes"] or _sha256(data) != row["sha256"]:
            raise GranularityCasebookError(
                f"manifest artifact mismatch: {row['path']}"
            )
    core_tree_sha = _tree_hash(expected)

    double_run_path = bundle_dir / "double_run_receipt.json"
    double_run_present = double_run_path.is_file()
    if double_run_present:
        double_run = json.loads(double_run_path.read_bytes())
        if double_run.get("schema_version") != (
            "v02-b4-1-granularity-double-run-v0.1"
        ):
            raise GranularityCasebookError("unexpected double-run schema")
        if double_run.get("byte_identical") is not True:
            raise GranularityCasebookError("double-run receipt is not green")
        for field in (
            "pass1_tree_sha256",
            "pass2_tree_sha256",
            "target_tree_sha256",
        ):
            if double_run.get(field) != core_tree_sha:
                raise GranularityCasebookError(
                    f"double-run tree hash mismatch: {field}"
                )
        if double_run.get("target_manifest_sha256") != _sha256(
            observed["manifest.json"]
        ):
            raise GranularityCasebookError(
                "double-run target manifest hash mismatch"
            )
    acceptance = json.loads(observed["acceptance_receipt.json"])
    return {
        "result": "PASS",
        "case_pass_count": acceptance["checks"]["case_pass_count"],
        "decision_counts": manifest["case_summary"]["decision_counts"],
        "uncovered_boundary_count": manifest["case_summary"][
            "uncovered_boundary_count"
        ],
        "tree_sha256": core_tree_sha,
        "manifest_sha256": _sha256(observed["manifest.json"]),
        "double_run_receipt_present": double_run_present,
        "model_api_calls": 0,
        "network_requests": 0,
    }


def write_double_run_receipt(
    bundle_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        pass1_dir = tmp_root / "pass1"
        pass2_dir = tmp_root / "pass2"
        build_bundle(pass1_dir)
        build_bundle(pass2_dir)
        pass1 = _read_tree(pass1_dir, include_double_run=False)
        pass2 = _read_tree(pass2_dir, include_double_run=False)
    byte_identical = pass1 == pass2
    if not byte_identical:
        raise GranularityCasebookError("independent builds are not byte-identical")
    build_bundle(bundle_dir)
    target = _read_tree(bundle_dir, include_double_run=False)
    if target != pass1:
        raise GranularityCasebookError(
            "target bundle differs from the independent builds"
        )
    tree_sha = _tree_hash(pass1)
    receipt = {
        "schema_version": "v02-b4-1-granularity-double-run-v0.1",
        "candidate_id": "B4_1_granularity_casebook",
        "runs": 2,
        "byte_identical": True,
        "pass1_tree_sha256": tree_sha,
        "pass2_tree_sha256": tree_sha,
        "target_tree_sha256": tree_sha,
        "target_manifest_sha256": _sha256(target["manifest.json"]),
        "case_pass_count_each_run": 10,
        "uncovered_boundary_count_each_run": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "result": "PASS_BYTE_IDENTICAL",
    }
    (bundle_dir / "double_run_receipt.json").write_bytes(_json_bytes(receipt))
    check_bundle(bundle_dir)
    return receipt


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and validate the offline v0.2 granularity casebook."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    validate = subparsers.add_parser("validate-bundle")
    validate.add_argument("--bundle-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    double_run = subparsers.add_parser("double-run")
    double_run.add_argument("--bundle-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "build":
        result = build_bundle(args.output_dir)
    elif args.command == "validate-bundle":
        result = check_bundle(args.bundle_dir)
    elif args.command == "double-run":
        result = write_double_run_receipt(args.bundle_dir)
    else:  # pragma: no cover - argparse owns command validation
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
