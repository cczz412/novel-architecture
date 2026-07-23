from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REL = Path("reports/Z74A_正反例换皮候选_20260721/三联例候选.json")
OUT_REL = Path("reports/Z75_正反例全文回传与内测_20260721/item1")
FORBIDDEN_SOURCE = "reports/Z74A_正反例换皮候选_20260721/原料来源与病灶提炼.json"
EXPECTED_SOURCE_SHA256 = "16648bf988501c9b0968e41e4aef51b36d0b0c47ec9e1c47900c3dbfe3fcb945"

RAW_COPY_NAME = "三联例候选_逐字原件.json"
SCHEMA_NAME = "冻结Schema_v0.1_十层定义_只读依据.json"
LANDING_NAME = "28条刚好版_落点层候选旁表.json"
SUPPORT_AUDIT_NAME = "字段支撑词机械对账.json"
SPLIT_INDEX_JSON_NAME = "Notion拆页索引.json"
SPLIT_INDEX_MD_NAME = "Notion拆页索引.md"
RECEIPT_NAME = "机械验收.json"
MANIFEST_NAME = "report_manifest.json"
SHA_NAME = "SHA256SUMS"

SCHEMA_AUTHORITY = {
    "title": "外发Prompt定稿｜Schema v0.1 六窗实料归层一致性测试_20260721",
    "page_id": "4e3a7a30-0862-4fd0-9869-b5d9045be8a0",
    "url": "https://app.notion.com/p/4e3a7a3008624fd09869b5d9045be8a0",
    "frozen_status": "frozen",
    "frozen_at": "2026-07-21 04:15 Asia/Shanghai",
}

LAYER_DEFINITIONS = [
    {
        "layer": "L0",
        "name": "原文锚",
        "definition": "原文在哪；一切条目须能指回原文位置。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["原文位置"],
    },
    {
        "layer": "L1",
        "name": "事件层",
        "definition": "发生了什么；全库唯一事实记账层。",
        "is_unique_event_fact_ledger": True,
        "literal_receivers": ["主体", "前提或条件", "动作", "对象", "结果或变化"],
    },
    {
        "layer": "L2",
        "name": "情节线层",
        "definition": "欠读者什么；F 伏笔、M 悬念、X 冲突。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["F伏笔", "M悬念", "X冲突", "埋点", "提醒", "回收窗口"],
    },
    {
        "layer": "L3",
        "name": "人物层",
        "definition": "人物稳定档案与由事件推导的状态快照。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": [
            "稳定档案.欲望",
            "稳定档案.恐惧",
            "稳定档案.底线",
            "状态快照.位置",
            "状态快照.伤势",
            "状态快照.关系",
        ],
    },
    {
        "layer": "K",
        "name": "知识门禁层",
        "definition": "世界真相、角色以为、读者已见三层分开。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["世界真相", "角色以为", "读者已见"],
    },
    {
        "layer": "L4",
        "name": "章节功能层",
        "definition": "这一章要干什么活；目标、阻力、代价等施工单信息。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["目标", "阻力", "代价"],
    },
    {
        "layer": "L5",
        "name": "卷幕层",
        "definition": "这一段路要走到哪；滚动规划，近细远粗。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["卷幕滚动规划"],
    },
    {
        "layer": "L6",
        "name": "设定层",
        "definition": "地点、势力、物品与规则等稳定世界实体。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["地点", "势力", "物品", "规则"],
    },
    {
        "layer": "T",
        "name": "标签手册层",
        "definition": "这种戏通常怎么写、怎么写会崩；不另存新事实。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["标签手册"],
    },
    {
        "layer": "V",
        "name": "导出视图层",
        "definition": "按需投影同一批节点；导出禁回写，不另存新事实。",
        "is_unique_event_fact_ledger": False,
        "literal_receivers": ["导出视图"],
    },
]

FROZEN_RECEIVER_PATHS = {
    "L0.原文位置",
    "L1.主体",
    "L1.前提或条件",
    "L1.动作",
    "L1.对象",
    "L1.结果或变化",
    "L2.F伏笔",
    "L2.M悬念",
    "L2.X冲突",
    "L2.埋点",
    "L2.提醒",
    "L2.回收窗口",
    "L3.稳定档案.欲望",
    "L3.稳定档案.恐惧",
    "L3.稳定档案.底线",
    "L3.状态快照.位置",
    "L3.状态快照.伤势",
    "L3.状态快照.关系",
    "K.世界真相",
    "K.角色以为",
    "K.读者已见",
    "L4.目标",
    "L4.阻力",
    "L4.代价",
    "L5.卷幕滚动规划",
    "L6.地点",
    "L6.势力",
    "L6.物品",
    "L6.规则",
    "T.标签手册",
    "V.导出视图",
}

# 四页都是原文件的连续行切片。按顺序拼接后必须逐字节还原原件。
SPLIT_SPECS = [
    {
        "part": 1,
        "filename": "notion_pages/01_LARGE四组_含文件头.txt",
        "line_start": 1,
        "line_end": 662,
        "groups": ["LARGE-01", "LARGE-02", "LARGE-03", "LARGE-04"],
    },
    {
        "part": 2,
        "filename": "notion_pages/02_SMALL四组.txt",
        "line_start": 663,
        "line_end": 1323,
        "groups": ["SMALL-01", "SMALL-02", "SMALL-03", "SMALL-04"],
    },
    {
        "part": 3,
        "filename": "notion_pages/03_MISS四组.txt",
        "line_start": 1324,
        "line_end": 1689,
        "groups": ["MISS-01", "MISS-02", "MISS-03", "MISS-04"],
    },
    {
        "part": 4,
        "filename": "notion_pages/04_ANCHOR四组_含文件尾.txt",
        "line_start": 1690,
        "line_end": 2334,
        "groups": ["ANCHOR-01", "ANCHOR-02", "ANCHOR-03", "ANCHOR-04"],
    },
]


def _l1(
    qualifier_targets: list[str],
    downstream_use: str,
    reason: str,
    *,
    extra_primary_fields: list[str] | None = None,
    secondary_receivers: list[dict[str, Any]] | None = None,
    candidate_extension_note: str | None = None,
    confidence: str = "high",
) -> dict[str, Any]:
    field_mapping = {
        "subject": ["L1.主体"],
        "action": ["L1.动作"],
        "result": ["L1.结果或变化"],
        "necessary_qualifiers": qualifier_targets,
        "anchors": ["L0.原文位置"],
    }
    primary_fields = ["L1.主体", "L1.动作", "L1.结果或变化", *qualifier_targets]
    primary_fields.extend(extra_primary_fields or [])
    return {
        "primary_layer": "L1",
        "primary_layer_name": "事件层",
        "primary_field_paths": list(dict.fromkeys(primary_fields)),
        "field_mapping": field_mapping,
        "secondary_receivers": secondary_receivers or [],
        "downstream_use": downstream_use,
        "candidate_reason": reason,
        "candidate_extension_note": candidate_extension_note,
        "confidence": confidence,
    }


# 旁表只做候选落点，不写回 Z74A 原件，也不进入本轮提示词。
LANDING_SPECS: dict[str, dict[str, Any]] = {
    "LARGE-01/JR-01": _l1(
        ["L1.前提或条件"],
        "保留冷藏柜异常，同时阻止下游虚构它与门禁异常的因果边。",
        "发现异常是可判真的发生项；无因果声明只约束事件图，不把两件事合并。",
        candidate_extension_note="候选扩展：两条事件之间不得建立因果关系；冻结页未给因果边字段。",
    ),
    "LARGE-01/JR-02": _l1(
        ["L1.前提或条件"],
        "保留门禁异常，同时阻止下游虚构它与温度报警的因果边。",
        "门禁记录显示的状态是独立事实；无因果声明负责守住事件边界。",
        candidate_extension_note="候选扩展：两条事件之间不得建立因果关系；冻结页未给因果边字段。",
    ),
    "LARGE-02/JR-01": _l1(
        ["L1.对象"],
        "更新首班车时刻，供后续场景与时间安排读取。",
        "主体、调整对象和调整后的时间都明确，能形成单主体事件。",
        extra_primary_fields=["L1.对象"],
    ),
    "LARGE-02/JR-02": _l1(
        ["L1.前提或条件"],
        "更新发车出口，并保留收到新表这一触发前提。",
        "司机的动作和调度员动作分开记账，避免错挂主体。",
        extra_primary_fields=["L1.对象"],
    ),
    "LARGE-03/JR-01": _l1(
        ["L1.前提或条件"],
        "让下游知道采购员已作出暂缓下单的决定，而不把它吞进后续位移。",
        "看到报价上涨是明示前提，决定暂缓下单是已经发生的心理决定。",
        secondary_receivers=[
            {
                "layer": "K",
                "field_paths": ["K.角色以为"],
                "use": "若知识门禁需供数，可投影采购员当前意向；不重复记事实。",
            }
        ],
    ),
    "LARGE-03/JR-02": _l1(
        ["L1.前提或条件"],
        "保留采购员随后去会议室汇报的独立位移与沟通动作。",
        "该动作可与前一决定分别核验；“随后”负责叙述顺序。",
        candidate_extension_note="候选扩展：‘随后’涉及叙述顺序；冻结页未给顺序字段。",
    ),
    "LARGE-04/JR-01": _l1(
        ["L1.结果或变化"],
        "把样品封条当前被确认完整这一状态变化交给后续连续性检查。",
        "这里只确认封条状态，不替温度规则作风险结论。",
    ),
    "LARGE-04/JR-02": {
        "primary_layer": "L6",
        "primary_layer_name": "设定层",
        "primary_field_paths": ["L6.规则"],
        "field_mapping": {
            "subject": ["L6.规则"],
            "action": ["L6.规则"],
            "result": ["L6.规则"],
            "necessary_qualifiers": ["L6.规则"],
            "anchors": ["L0.原文位置"],
        },
        "secondary_receivers": [
            {
                "layer": "L1",
                "field_paths": ["L1.动作", "L1.结果或变化"],
                "use": "若需记录规程被写明这一发生项，可在 L1 留事件引用；规则正文仍归 L6。",
            }
        ],
        "downstream_use": "供样品处置、风险判断和场景约束读取温度触发条件与停用效果。",
        "candidate_reason": "语义中心是稳定规程的触发—效果，不是一次性的现场动作。",
        "candidate_extension_note": "候选扩展：规则内部可再拆触发条件与效果；冻结页只明示‘规则’受体。",
        "confidence": "high",
    },
    "LARGE-04/JR-03": {
        "primary_layer": "K",
        "primary_layer_name": "知识门禁层",
        "primary_field_paths": ["K.读者已见"],
        "field_mapping": {
            "subject": ["K.读者已见"],
            "action": ["K.读者已见"],
            "result": ["K.读者已见"],
            "necessary_qualifiers": ["K.读者已见"],
            "anchors": ["L0.原文位置"],
        },
        "secondary_receivers": [],
        "downstream_use": "守住‘本页未证明超温’的证据边界，防止下游把未见记录写成风险已排除。",
        "candidate_reason": "这条表达的是当前材料揭示到哪，而不是运输温度的世界真相。",
        "candidate_extension_note": "候选扩展：可细分材料范围、证据状态和未揭示命题；冻结页只明示‘读者已见’。",
        "confidence": "medium",
    },
    "SMALL-01/JR-01": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "把更换滤芯、启动设备与指示灯转绿保留为同一完成链。",
        "同主体同对象的连续步骤共同形成可核验完成态，继续碎切会丢失链路。",
    ),
    "SMALL-01/JR-02": _l1(
        ["L1.前提或条件"],
        "记录同一时段发生的独立保洁动作，不与设备操作混为一条。",
        "主体和对象不同，时间相邻不等于同一完成链。",
        candidate_extension_note="候选扩展：‘同一时段’的时间细目待字段级小版本定义。",
    ),
    "SMALL-02/JR-01": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "供服务切换、故障恢复和连续性状态读取完整条件—操作—结果。",
        "备份校验是明示前提，控制台确认是直接结果，三者共同构成一个完成链。",
    ),
    "SMALL-02/JR-02": _l1(
        ["L1.前提或条件"],
        "记录值班同事写工单编号这一同期独立动作。",
        "与服务切换主体、对象不同，只保留时间关系。",
        candidate_extension_note="候选扩展：‘同一时段’的时间细目待字段级小版本定义。",
    ),
    "SMALL-03/JR-01": _l1(
        ["L1.前提或条件"],
        "把班长对甲组的一项完整安排交给后续任务与场景动作链读取。",
        "清点、填表、交前台是同一指令内有序完成链，不能拆成无主碎片。",
        candidate_extension_note="候选扩展：明早与先后顺序的细目待字段级小版本定义。",
    ),
    "SMALL-03/JR-02": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "记录甲组长确认收到通知，供后续判断任务是否已传达。",
        "回复是独立主体动作；‘随后’只规定叙述顺序。",
        candidate_extension_note="候选扩展：‘随后’涉及叙述顺序；冻结页未给顺序字段。",
    ),
    "SMALL-04/JR-01": _l1(
        ["L1.前提或条件"],
        "保留闭店前的重复核对习惯及差额入簿结果，供流程连续性检查。",
        "时间限定决定这项习惯何时成立，不能单独切走。",
        secondary_receivers=[
            {
                "layer": "L6",
                "field_paths": ["L6.规则"],
                "use": "只有经语义审定为正式制度时，才可投影成 L6 流程规则。",
            }
        ],
        candidate_extension_note="候选扩展：重复周期与有效范围待字段级小版本定义。",
        confidence="medium",
    ),
    "SMALL-04/JR-02": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "更新后门在闭店后的锁闭状态。",
        "闭店后是明示时间条件，保安锁门是单一可核验动作。",
        candidate_extension_note="候选扩展：具体时间字段待字段级小版本定义。",
    ),
    "MISS-01/JR-01": {
        "primary_layer": "K",
        "primary_layer_name": "知识门禁层",
        "primary_field_paths": ["K.角色以为"],
        "field_mapping": {
            "subject": ["K.角色以为"],
            "action": ["K.角色以为"],
            "result": ["K.角色以为"],
            "necessary_qualifiers": ["K.角色以为"],
            "anchors": ["L0.原文位置"],
        },
        "secondary_receivers": [
            {
                "layer": "L1",
                "field_paths": ["L1.主体", "L1.动作", "L1.结果或变化"],
                "use": "若需记录‘产生怀疑’这一认知事件，可由 L1 引用同一锚。",
            }
        ],
        "downstream_use": "让下游区分角色怀疑与世界真相，避免把未确认判断写成事实。",
        "candidate_reason": "语义中心是不确定的角色认知，正对应 K 的‘角色以为’。",
        "candidate_extension_note": "候选扩展：角色、命题、置信程度与确认状态可再细分；冻结页只明示‘角色以为’。",
        "confidence": "high",
    },
    "MISS-02/JR-01": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "记录计划已经形成、执行尚未发生，供未来任务与状态检查读取。",
        "‘计划周五更换’是当前已发生的意向事件；周三和尚未更换守住完成态边界。",
        secondary_receivers=[
            {
                "layer": "K",
                "field_paths": ["K.角色以为"],
                "use": "向知识门禁投影管理员意向，不把计划冒充世界完成态。",
            }
        ],
    ),
    "MISS-03/JR-01": _l1(
        ["L1.对象", "L1.结果或变化"],
        "保留十箱的抽查范围与其中两箱的异常结果，供质量统计和后续处置使用。",
        "数量和异常强度均由原文明示；缩成‘部分标签有问题’会损失结构用途。",
        extra_primary_fields=["L1.对象"],
    ),
    "MISS-04/JR-01": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "记录培训改时及其场地开放限制，供排期和场景约束读取。",
        "会议室开放时段是动作成立的明示背景限制，不能从事件里漏掉。",
        secondary_receivers=[
            {
                "layer": "L6",
                "field_paths": ["L6.地点", "L6.规则"],
                "use": "若下午开放是稳定设定，可投影到会议室实体卡；单次例子本身不足以定为长期规则。",
            }
        ],
        candidate_extension_note="候选扩展：具体开放时段的字段形状待字段级小版本定义。",
        confidence="medium",
    ),
    "ANCHOR-01/JR-01": _l1(
        ["L1.对象", "L1.结果或变化"],
        "记录配送员把三箱样品送达接待台的独立动作。",
        "短引完整支撑主体、数量、动作与到达结果，不借邻句补签收。",
        extra_primary_fields=["L1.对象"],
    ),
    "ANCHOR-01/JR-02": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "记录接待员核封后完成签收，供交接状态读取。",
        "签收结果需要第二段原文支撑，不能挂在只写送达的短引上。",
    ),
    "ANCHOR-02/JR-01": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "保留复位操作与指示灯变绿的直接结果。",
        "完成结果来自第二个短引；两段锚合用才能托住整条事件。",
        candidate_extension_note="候选扩展：‘随后’涉及叙述顺序；冻结页未给顺序字段。",
    ),
    "ANCHOR-03/JR-01": _l1(
        ["L1.对象", "L1.结果或变化"],
        "记录文员把退货单存入蓝色文件夹。",
        "该短引只支持文员动作，不把邻近助理动作错挂给文员。",
        extra_primary_fields=["L1.对象"],
    ),
    "ANCHOR-03/JR-02": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "记录助理随后关窗及窗户状态变化。",
        "主体在第二个短引中明确，必须与文员动作分账。",
        candidate_extension_note="候选扩展：‘随后’涉及叙述顺序；冻结页未给顺序字段。",
    ),
    "ANCHOR-04/JR-01": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "保留主管安排的清点—核完—上报完整指令链。",
        "两段短引共同支撑任务对象、顺序与上报结果。",
        candidate_extension_note="候选扩展：下午与先后顺序的细目待字段级小版本定义。",
    ),
    "ANCHOR-04/JR-02": _l1(
        ["L1.前提或条件", "L1.结果或变化"],
        "保留差额超过三件时暂停发货并通知经理的条件分支。",
        "条件与后果必须同条保留，前半指令锚不能替代后半分支锚。",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(data))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_text(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in folded if character.isalnum())


def source_counts(candidate: dict[str, Any]) -> dict[str, Any]:
    groups = candidate["groups"]
    just_right_records = [record for group in groups for record in group["just_right"]["records"]]
    anchors = [anchor for record in just_right_records for anchor in record["anchors"]]
    support_term_total = 0
    qualifier_total = 0
    for record in just_right_records:
        support = record["anchor_support"]
        support_term_total += sum(len(support[field]["terms"]) for field in ("subject", "action", "result"))
        for qualifier in support["necessary_qualifiers"]:
            qualifier_total += 1
            support_term_total += len(qualifier["terms"])
    return {
        "triplet_group_total": len(groups),
        "variant_total": len(groups) * 3,
        "too_large_record_total": sum(len(group["too_large"]["records"]) for group in groups),
        "too_small_record_total": sum(len(group["too_small"]["records"]) for group in groups),
        "just_right_record_total": len(just_right_records),
        "anchor_total": len(anchors),
        "necessary_qualifier_total": qualifier_total,
        "support_term_total": support_term_total,
        "group_ids": [group["group_id"] for group in groups],
    }


def _audit_field(
    field_value: str,
    anchors: list[str],
    terms: list[str],
    anchor_indexes: list[int],
) -> dict[str, Any]:
    referenced_anchors = [anchors[index] for index in anchor_indexes]
    normalized_field = normalize_text(field_value)
    normalized_anchors = normalize_text("\n".join(referenced_anchors))
    term_checks = [
        {
            "term": term,
            "in_field": normalize_text(term) in normalized_field,
            "in_referenced_anchors": normalize_text(term) in normalized_anchors,
        }
        for term in terms
    ]
    return {
        "field_value": field_value,
        "anchor_indexes": anchor_indexes,
        "referenced_anchors": referenced_anchors,
        "terms": terms,
        "term_checks": term_checks,
        "status": "pass"
        if all(check["in_field"] and check["in_referenced_anchors"] for check in term_checks)
        else "fail",
    }


def build_support_audit(candidate: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for group_index, group in enumerate(candidate["groups"]):
        scenario = group["source_scenario"]
        for record_index, record in enumerate(group["just_right"]["records"]):
            record_key = f"{group['group_id']}/JR-{record_index + 1:02d}"
            anchors = record["anchors"]
            support = record["anchor_support"]
            anchor_checks = [
                {
                    "anchor_index": index,
                    "anchor": anchor,
                    "character_count": len(anchor),
                    "length_10_to_25": 10 <= len(anchor) <= 25,
                    "verbatim_in_source_scenario": any(anchor in sentence for sentence in scenario),
                }
                for index, anchor in enumerate(anchors)
            ]
            field_checks = {
                field: _audit_field(
                    record[field],
                    anchors,
                    support[field]["terms"],
                    support[field]["anchor_indexes"],
                )
                for field in ("subject", "action", "result")
            }
            qualifier_checks = []
            for qualifier_support in support["necessary_qualifiers"]:
                qualifier_index = qualifier_support["qualifier_index"]
                qualifier_checks.append(
                    {
                        "qualifier_index": qualifier_index,
                        **_audit_field(
                            record["necessary_qualifiers"][qualifier_index],
                            anchors,
                            qualifier_support["terms"],
                            qualifier_support["anchor_indexes"],
                        ),
                    }
                )
            status = "pass"
            if not all(check["length_10_to_25"] and check["verbatim_in_source_scenario"] for check in anchor_checks):
                status = "fail"
            if not all(check["status"] == "pass" for check in field_checks.values()):
                status = "fail"
            if not all(check["status"] == "pass" for check in qualifier_checks):
                status = "fail"
            rows.append(
                {
                    "record_key": record_key,
                    "source_locator": {
                        "group_index": group_index,
                        "group_id": group["group_id"],
                        "just_right_record_index": record_index,
                    },
                    "anchors": anchors,
                    "anchor_checks": anchor_checks,
                    "field_checks": field_checks,
                    "necessary_qualifier_checks": qualifier_checks,
                    "status": status,
                }
            )
    counts = source_counts(candidate)
    return {
        "schema_version": "z75-item1-field-support-audit-v1",
        "status": "pass" if len(rows) == 28 and all(row["status"] == "pass" for row in rows) else "fail",
        "source_path": str(SOURCE_REL),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "checks": {
            "record_total": len(rows),
            "anchor_total": counts["anchor_total"],
            "support_term_total": counts["support_term_total"],
            "necessary_qualifier_total": counts["necessary_qualifier_total"],
            "failed_record_total": sum(row["status"] != "pass" for row in rows),
        },
        "rows": rows,
    }


def build_landing_table(candidate: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    sequence = 0
    for group_index, group in enumerate(candidate["groups"]):
        for record_index, record in enumerate(group["just_right"]["records"]):
            sequence += 1
            record_key = f"{group['group_id']}/JR-{record_index + 1:02d}"
            if record_key not in LANDING_SPECS:
                raise ValueError(f"缺少落点候选：{record_key}")
            spec = LANDING_SPECS[record_key]
            rows.append(
                {
                    "candidate_id": f"Z75-LAND-{sequence:03d}",
                    "record_key": record_key,
                    "source_locator": {
                        "group_index": group_index,
                        "group_id": group["group_id"],
                        "just_right_record_index": record_index,
                    },
                    "source_record_sha256": sha256_bytes(canonical_json_bytes(record)),
                    "source_fields": {
                        "subject": record["subject"],
                        "action": record["action"],
                        "result": record["result"],
                        "necessary_qualifiers": record["necessary_qualifiers"],
                        "text": record["text"],
                        "anchors": record["anchors"],
                    },
                    "evidence_receiver": "L0.原文位置",
                    **spec,
                    "status": "candidate_pending_cloud_review",
                }
            )
    if set(LANDING_SPECS) != {row["record_key"] for row in rows}:
        unexpected = sorted(set(LANDING_SPECS) - {row["record_key"] for row in rows})
        raise ValueError(f"落点候选含原件外记录：{unexpected}")
    receiver_paths: list[str] = []
    for row in rows:
        receiver_paths.append(row["evidence_receiver"])
        receiver_paths.extend(row["primary_field_paths"])
        for targets in row["field_mapping"].values():
            receiver_paths.extend(targets)
        for receiver in row["secondary_receivers"]:
            receiver_paths.extend(receiver["field_paths"])
    unfrozen_receiver_paths = sorted(set(receiver_paths) - FROZEN_RECEIVER_PATHS)
    if unfrozen_receiver_paths:
        raise ValueError(f"字段标注混入冻结页未明示受体：{unfrozen_receiver_paths}")
    primary_counts = dict(sorted(Counter(row["primary_layer"] for row in rows).items()))
    return {
        "schema_version": "z75-item1-landing-candidate-side-table-v1",
        "status": "candidate_pending_cloud_review",
        "status_label": "落点层候选旁表／未并入原件／未固化",
        "source_path": str(SOURCE_REL),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "schema_authority": SCHEMA_AUTHORITY,
        "boundary": {
            "side_table_only": True,
            "source_json_modified": False,
            "future_prompt_visibility": False,
            "formal_semantic_verdict": False,
            "field_path_status": "frozen_page_literal_receiver_terms_only",
            "rule": "每条候选必须有主受体和字段；L0 随行；T/V 不作新事实主落点。",
        },
        "summary": {
            "row_total": len(rows),
            "row_with_primary_receiver_total": sum(bool(row["primary_field_paths"]) for row in rows),
            "primary_layer_counts": primary_counts,
            "l0_anchor_receiver_total": sum(row["evidence_receiver"] == "L0.原文位置" for row in rows),
            "t_or_v_primary_total": sum(row["primary_layer"] in {"T", "V"} for row in rows),
            "unfrozen_receiver_path_total": len(unfrozen_receiver_paths),
        },
        "rows": rows,
    }


def build_schema_reference() -> dict[str, Any]:
    return {
        "schema_version": "z75-item1-schema-authority-reference-v1",
        "status": "read_only_authority_reference",
        "authority": SCHEMA_AUTHORITY,
        "scope": "只摘录冻结十层定义与本旁表所需边界，不复制整页。",
        "layer_total": len(LAYER_DEFINITIONS),
        "layers": LAYER_DEFINITIONS,
        "adjudication_notes": [
            "L0 是所有条目的原文锚随行层。",
            "L1 是全库唯一事实记账层；L3、K、L6等层承接对应结构用途，不重复制造事实。",
            "T 是写法手册，V 是投影视图；二者不作本批原子的新事实主落点。",
            "本文件只记录冻结定义依据，不代表28条候选已完成正式语义审定。",
        ],
    }


def build_split_files(
    out_dir: Path,
    source_bytes: bytes,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    lines = source_bytes.splitlines(keepends=True)
    if len(lines) != 2334:
        raise ValueError(f"原件行数漂移：期望2334，实际{len(lines)}")
    group_map = {group["group_id"]: group for group in candidate["groups"]}
    parts: list[dict[str, Any]] = []
    reconstructed = bytearray()
    byte_cursor = 0
    for spec in SPLIT_SPECS:
        part_bytes = b"".join(lines[spec["line_start"] - 1 : spec["line_end"]])
        part_path = out_dir / spec["filename"]
        part_path.parent.mkdir(parents=True, exist_ok=True)
        part_path.write_bytes(part_bytes)
        group_ids = spec["groups"]
        just_right_total = sum(len(group_map[group_id]["just_right"]["records"]) for group_id in group_ids)
        anchor_total = sum(
            len(record["anchors"])
            for group_id in group_ids
            for record in group_map[group_id]["just_right"]["records"]
        )
        byte_start = byte_cursor
        byte_cursor += len(part_bytes)
        parts.append(
            {
                "part": spec["part"],
                "suggested_notion_page_title": f"三联例逐字原文｜{spec['part']:02d}｜{'至'.join((group_ids[0], group_ids[-1]))}",
                "path": spec["filename"],
                "source_line_start": spec["line_start"],
                "source_line_end": spec["line_end"],
                "source_byte_start_zero_based": byte_start,
                "source_byte_end_exclusive": byte_cursor,
                "bytes": len(part_bytes),
                "sha256": sha256_bytes(part_bytes),
                "group_ids": group_ids,
                "triplet_group_total": len(group_ids),
                "just_right_record_total": just_right_total,
                "anchor_total": anchor_total,
                "contains_file_prefix": spec["part"] == 1,
                "contains_file_suffix": spec["part"] == len(SPLIT_SPECS),
            }
        )
        reconstructed.extend(part_bytes)
    if bytes(reconstructed) != source_bytes:
        raise ValueError("Notion拆页片段不能逐字节还原原件")
    counts = source_counts(candidate)
    return {
        "schema_version": "z75-item1-notion-split-index-v1",
        "status": "pass",
        "source_path": str(SOURCE_REL),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "source_bytes": len(source_bytes),
        "split_rule": "四个文件是原件连续字节片段；页标题不进正文；按 part 顺序拼接后须与原件逐字节相同。",
        "readback_verification": {
            "method": "按 part 顺序导出各页纯文本并直接拼接，再核对总字节数与 SHA256。",
            "expected_bytes": len(source_bytes),
            "expected_sha256": EXPECTED_SOURCE_SHA256,
        },
        "counts": {
            "page_total": len(parts),
            "triplet_group_total": counts["triplet_group_total"],
            "just_right_record_total": counts["just_right_record_total"],
            "anchor_total": counts["anchor_total"],
        },
        "parts": parts,
        "forbidden_sources": [FORBIDDEN_SOURCE],
    }


def split_index_markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Notion 拆页索引｜第75道件①",
        "",
        "✅ 四个正文片段都是 Z74A 原件的连续字节切片。按编号拼接后，必须还原同一个原始 JSON。",
        "",
        f"- 原件：`{SOURCE_REL}`",
        f"- 预期字节数：`{index['source_bytes']}`",
        f"- 预期 SHA256：`{index['source_sha256']}`",
        "- 页面标题只放在 Notion 标题栏，不能混进正文片段。正文不要补说明、来源行或代码围栏。",
        "",
        "| 顺序 | 本地正文片段 | 原件行号 | 三联组 | 刚好版 | 短引 | 片段 SHA256 |",
        "|---:|---|---:|---|---:|---:|---|",
    ]
    for part in index["parts"]:
        lines.append(
            "| {part} | `{path}` | {start}～{end} | {groups} | {records} | {anchors} | `{sha}` |".format(
                part=part["part"],
                path=part["path"],
                start=part["source_line_start"],
                end=part["source_line_end"],
                groups="、".join(part["group_ids"]),
                records=part["just_right_record_total"],
                anchors=part["anchor_total"],
                sha=part["sha256"],
            )
        )
    lines.extend(
        [
            "",
            "⚠️ 禁止源只登记路径，不读取、不粘贴、不上传：",
            "",
            f"- `{FORBIDDEN_SOURCE}`",
            "",
            "回读验收：四页按 01→04 导出纯文本，直接拼接；总字节数与总 SHA 同时命中才算逐字回传。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def artifact_row(path: Path, out_dir: Path, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(out_dir).as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def _primary_output_paths(out_dir: Path) -> list[tuple[Path, str]]:
    paths: list[tuple[Path, str]] = [
        (out_dir / RAW_COPY_NAME, "Z74A原件字节级副本"),
        (out_dir / SCHEMA_NAME, "冻结Schema十层只读依据"),
        (out_dir / LANDING_NAME, "28条落点层候选旁表"),
        (out_dir / SUPPORT_AUDIT_NAME, "字段支撑词机械对账"),
        (out_dir / SPLIT_INDEX_JSON_NAME, "Notion拆页机器索引"),
        (out_dir / SPLIT_INDEX_MD_NAME, "Notion拆页人读索引"),
    ]
    paths.extend((out_dir / spec["filename"], "Notion逐字正文片段") for spec in SPLIT_SPECS)
    return paths


def build_receipt(
    source_bytes: bytes,
    candidate: dict[str, Any],
    support_audit: dict[str, Any],
    landing_table: dict[str, Any],
    split_index: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    counts = source_counts(candidate)
    fragments = [out_dir / spec["filename"] for spec in SPLIT_SPECS]
    reconstructed = b"".join(path.read_bytes() for path in fragments)
    checks = {
        "source_sha256_pinned": sha256_bytes(source_bytes) == EXPECTED_SOURCE_SHA256,
        "raw_copy_byte_identical": (out_dir / RAW_COPY_NAME).read_bytes() == source_bytes,
        "triplet_group_total_is_16": counts["triplet_group_total"] == 16,
        "variant_total_is_48": counts["variant_total"] == 48,
        "just_right_record_total_is_28": counts["just_right_record_total"] == 28,
        "anchor_total_is_42": counts["anchor_total"] == 42,
        "field_support_audit_pass": support_audit["status"] == "pass",
        "landing_candidate_row_total_is_28": landing_table["summary"]["row_total"] == 28,
        "all_landing_candidates_have_receivers": landing_table["summary"]["row_with_primary_receiver_total"] == 28,
        "t_or_v_primary_total_is_zero": landing_table["summary"]["t_or_v_primary_total"] == 0,
        "unfrozen_receiver_path_total_is_zero": landing_table["summary"]["unfrozen_receiver_path_total"] == 0,
        "schema_layer_total_is_10": len(LAYER_DEFINITIONS) == 10,
        "notion_split_reconstructs_source": reconstructed == source_bytes,
        "notion_split_counts_match": split_index["counts"]
        == {
            "page_total": 4,
            "triplet_group_total": 16,
            "just_right_record_total": 28,
            "anchor_total": 42,
        },
    }
    return {
        "schema_version": "z75-item1-mechanical-receipt-v1",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "counts": counts,
        "landing_primary_layer_counts": landing_table["summary"]["primary_layer_counts"],
        "source_integrity": {
            "path": str(SOURCE_REL),
            "sha256_before": EXPECTED_SOURCE_SHA256,
            "sha256_after": sha256_path(ROOT / SOURCE_REL),
            "source_json_modified": False,
        },
        "forbidden_sources": [FORBIDDEN_SOURCE],
        "forbidden_source_boundary": "仅登记路径；生成器不打开、不读取、不复制该文件。",
        "semantic_boundary": "机械PASS只证明数量、逐字、锚与支撑词合同；28条落点仍是待云端语义审的候选旁表。",
        "model_api_calls": 0,
        "network_calls": 0,
        "tokens": 0,
    }


def build_manifest(
    out_dir: Path,
    source_bytes: bytes,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    outputs = [artifact_row(path, out_dir, role) for path, role in _primary_output_paths(out_dir)]
    outputs.append(artifact_row(out_dir / RECEIPT_NAME, out_dir, "机械验收回执"))
    return {
        "schema_version": "z75-item1-report-manifest-v1",
        "task": "第75道件①正反例全文回传本地准备",
        "status": "prepared_candidate_pending_cloud_review",
        "status_label": "逐字回传本地件已备／落点旁表待云端语义审",
        "source_attachment": {
            "path": str(SOURCE_REL),
            "bytes": len(source_bytes),
            "sha256": sha256_bytes(source_bytes),
            "local_copy": RAW_COPY_NAME,
            "byte_identical": (out_dir / RAW_COPY_NAME).read_bytes() == source_bytes,
        },
        "source_counts": source_counts(candidate),
        "schema_authority": SCHEMA_AUTHORITY,
        "forbidden_sources": [FORBIDDEN_SOURCE],
        "forbidden_source_boundary": "只列路径，不含内容、大小、摘要或哈希。",
        "outputs": outputs,
        "builder": {
            "path": "tools/z75_item1_prepare.py",
            "sha256": sha256_path(ROOT / "tools/z75_item1_prepare.py"),
        },
        "test_file": {
            "path": "tests/test_z75_item1_prepare.py",
            "sha256": sha256_path(ROOT / "tests/test_z75_item1_prepare.py")
            if (ROOT / "tests/test_z75_item1_prepare.py").exists()
            else None,
        },
        "write_boundary": f"只写 {OUT_REL}/ 与 z75_item1 命名工具/测试；不改Z74A原件，不写Notion。",
        "zero_call_boundary": {"model_api_calls": 0, "network_calls": 0, "tokens": 0},
    }


def write_checksums(out_dir: Path) -> None:
    files = sorted(
        path
        for path in out_dir.rglob("*")
        if path.is_file() and path.name != SHA_NAME
    )
    lines = [f"{sha256_path(path)}  {path.relative_to(out_dir).as_posix()}" for path in files]
    (out_dir / SHA_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_bundle(out_dir: Path | None = None) -> dict[str, Any]:
    source_path = ROOT / SOURCE_REL
    out_dir = out_dir or ROOT / OUT_REL
    source_bytes = source_path.read_bytes()
    source_sha = sha256_bytes(source_bytes)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"Z74A原件SHA漂移：期望{EXPECTED_SOURCE_SHA256}，实际{source_sha}")
    candidate = json.loads(source_bytes.decode("utf-8"))
    counts = source_counts(candidate)
    expected_counts = {
        "triplet_group_total": 16,
        "just_right_record_total": 28,
        "anchor_total": 42,
    }
    for key, expected in expected_counts.items():
        if counts[key] != expected:
            raise ValueError(f"{key}漂移：期望{expected}，实际{counts[key]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / RAW_COPY_NAME).write_bytes(source_bytes)
    write_json(out_dir / SCHEMA_NAME, build_schema_reference())
    support_audit = build_support_audit(candidate)
    if support_audit["status"] != "pass":
        raise ValueError("字段支撑词机械对账失败")
    write_json(out_dir / SUPPORT_AUDIT_NAME, support_audit)
    landing_table = build_landing_table(candidate)
    write_json(out_dir / LANDING_NAME, landing_table)
    split_index = build_split_files(out_dir, source_bytes, candidate)
    write_json(out_dir / SPLIT_INDEX_JSON_NAME, split_index)
    (out_dir / SPLIT_INDEX_MD_NAME).write_text(split_index_markdown(split_index), encoding="utf-8")
    receipt = build_receipt(source_bytes, candidate, support_audit, landing_table, split_index, out_dir)
    if receipt["status"] != "pass":
        raise ValueError("件①机械验收失败")
    write_json(out_dir / RECEIPT_NAME, receipt)
    manifest = build_manifest(out_dir, source_bytes, candidate)
    write_json(out_dir / MANIFEST_NAME, manifest)
    write_checksums(out_dir)
    return verify_bundle(out_dir)


def _parse_checksums(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        checksum, relative = line.split("  ", 1)
        rows[relative] = checksum
    return rows


def verify_bundle(out_dir: Path | None = None) -> dict[str, Any]:
    out_dir = out_dir or ROOT / OUT_REL
    source_bytes = (ROOT / SOURCE_REL).read_bytes()
    candidate = json.loads(source_bytes.decode("utf-8"))
    manifest = read_json(out_dir / MANIFEST_NAME)
    receipt = read_json(out_dir / RECEIPT_NAME)
    support_audit = read_json(out_dir / SUPPORT_AUDIT_NAME)
    landing_table = read_json(out_dir / LANDING_NAME)
    split_index = read_json(out_dir / SPLIT_INDEX_JSON_NAME)
    mismatches: list[dict[str, Any]] = []

    if sha256_bytes(source_bytes) != EXPECTED_SOURCE_SHA256:
        mismatches.append({"scope": "source", "reason": "sha256_mismatch"})
    if (out_dir / RAW_COPY_NAME).read_bytes() != source_bytes:
        mismatches.append({"scope": "raw_copy", "reason": "not_byte_identical"})
    if source_counts(candidate)["triplet_group_total"] != 16:
        mismatches.append({"scope": "counts", "reason": "triplet_group_total"})
    if source_counts(candidate)["just_right_record_total"] != 28:
        mismatches.append({"scope": "counts", "reason": "just_right_record_total"})
    if source_counts(candidate)["anchor_total"] != 42:
        mismatches.append({"scope": "counts", "reason": "anchor_total"})
    if support_audit["status"] != "pass":
        mismatches.append({"scope": "support_audit", "reason": "status_not_pass"})
    if landing_table["summary"]["row_total"] != 28:
        mismatches.append({"scope": "landing_table", "reason": "row_total"})
    if landing_table["summary"]["t_or_v_primary_total"] != 0:
        mismatches.append({"scope": "landing_table", "reason": "t_or_v_primary"})
    fragments = [(out_dir / part["path"]).read_bytes() for part in split_index["parts"]]
    if b"".join(fragments) != source_bytes:
        mismatches.append({"scope": "notion_split", "reason": "reconstruction_mismatch"})
    for output in manifest["outputs"]:
        path = out_dir / output["path"]
        if not path.exists():
            mismatches.append({"scope": "manifest_output", "path": output["path"], "reason": "missing"})
            continue
        if path.stat().st_size != output["bytes"] or sha256_path(path) != output["sha256"]:
            mismatches.append({"scope": "manifest_output", "path": output["path"], "reason": "digest"})
    checksum_rows = _parse_checksums(out_dir / SHA_NAME)
    for relative, expected_sha in checksum_rows.items():
        path = out_dir / relative
        if not path.exists() or sha256_path(path) != expected_sha:
            mismatches.append({"scope": "sha256sums", "path": relative, "reason": "digest"})
    if receipt["status"] != "pass":
        mismatches.append({"scope": "receipt", "reason": "status_not_pass"})

    return {
        "status": "pass" if not mismatches else "fail",
        "mismatches": mismatches,
        "checked": {
            "manifest_output_total": len(manifest["outputs"]),
            "checksum_total": len(checksum_rows),
            "triplet_group_total": source_counts(candidate)["triplet_group_total"],
            "just_right_record_total": source_counts(candidate)["just_right_record_total"],
            "anchor_total": source_counts(candidate)["anchor_total"],
            "landing_candidate_row_total": landing_table["summary"]["row_total"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="准备并验收第75道件①本地逐字回传包")
    parser.add_argument("--verify-only", action="store_true", help="只验现有包，不重写")
    parser.add_argument("--out-dir", type=Path, default=None, help="测试时可指定输出目录")
    args = parser.parse_args()
    result = verify_bundle(args.out_dir) if args.verify_only else prepare_bundle(args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
