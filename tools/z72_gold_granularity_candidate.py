#!/usr/bin/env python3
"""第72道：机械生成第3章金标 v1.2 候选及四轮零调用重判账。

语义判断全部显式写在本文件的候选定义和人工判词表中；程序只负责：
1. 钉住真源 SHA；
2. 回读冻结锚和正文；
3. 检查旧语义点编号没有孤儿，并把仍待 CZ 审定的语义等价单列；
4. 汇总人工严格／影子判词，不做自动语义匹配；
5. 输出可重复的候选工件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
DEFAULT_OUTPUT_DIR = ROOT / "reports/Z72_第3章金标粒度候选_20260721"

GOLD_V1_1 = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
CHAPTER_TEXT = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt"
EVIDENCE_CATALOG = ROOT / "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/01_extract/evidence_catalogs/ch0003.json"

SAMPLE_PATHS = {
    "B0_Z57": ROOT / "runs/Z57_X01_稳定语义身份解耦与全链后半_20章_v1.0_20260719/01_extract/events/ch0003.json",
    "Z68C": ROOT / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720/01_extract/events/ch0003.json",
    "Z70": ROOT / "runs/Z70_X01_事件句压缩合同_五靶章_v1.0_20260721/01_extract/events/ch0003.json",
    "Z71": ROOT / "runs/Z71_X01_z70语义补全旁路_五靶章_v1.0_20260721/outputs/events/ch0003.json",
}

OLD_SCORE_PATHS = {
    "B0_Z57": ROOT / "reports/Z57_稳定语义身份解耦与全链后半_20260719/第3章当章层诚实成绩单.json",
    "Z68C": ROOT / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720/第3章金标v1.1语义成绩单.json",
    "Z70": ROOT / "reports/Z70_压缩病灶合同条款单变量_20260721/第3章金标v1.1语义成绩单.json",
    "Z71": ROOT / "reports/Z71_z70语义补全旁路_20260721/第3章金标v1.1语义成绩单.json",
}

RUN_GATE_PATHS = {
    "Z70": ROOT / "reports/Z70_压缩病灶合同条款单变量_20260721/report_manifest.json",
    "Z71": ROOT / "reports/Z71_z70语义补全旁路_20260721/report_manifest.json",
}

PROTECTED_PATHS = {
    "default_registry": ROOT / "config/defaults/zbatch_v1.2_full_chain.json",
    "runner": ROOT / "tools/zbatch.py",
    "classification_rules": ROOT / "config/contracts/classify_rules_v1.2.json",
    "current_122": ROOT / "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json",
}

EXPECTED_SHA256 = {
    "gold_v1_1": "8cca04f06ba21048e15420f178163c646d2effeead0970697fafbf5f45174b7c",
    "chapter_text": "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    "evidence_catalog": "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    "sample:B0_Z57": "b616bb8d5c7084c20e6b3baba228643d79b9d619c0dc6c229529499036ab9ad8",
    "sample:Z68C": "23e31e0d3844dd4708d973babf3c3f466860e4cb423552f95b150dc42a2382f9",
    "sample:Z70": "a4daa00d938c293c37a1b4407ebe060a7d4dea19b8ae7b21052390d79a8688a0",
    "sample:Z71": "8e94d2adac89f04119514aa7c52a008666e8af0e2869eaec2fb5079114e5021c",
    "old_score:B0_Z57": "069c28237624e0cfe5236805c11bec28ad4e599990f77cab737b6596a9af5f69",
    "old_score:Z68C": "d2bcf3d2e5dcfe61963fb34ae1b693a1b7d33d3e7c6182642f9d2b3bdbce698e",
    "old_score:Z70": "d18969b4c04f2472d3b36f3d99d3f3b920706bfb688749aeb5f19785427dccd8",
    "old_score:Z71": "8a1aaa78192f750a0df1e81110f69c97190468012964a42c5e5acd8453414ce3",
    "run_gate:Z70": "30408e009f6038c7d6f1dc0273e3f6aa24268d0ee227593bd0fe327714fde3ab",
    "run_gate:Z71": "91a962883e4e87c80f4bdc541c879c01241d0166107a3f7b5a9288359d4a1800",
    "protected:default_registry": "b23b5cce26b9cfe584dd97dbff6422efa2b22ccd5cba38c6ed6a44c4543bc0a1",
    "protected:runner": "160c28b3ef0210fd05c392f713534cf1ffdf041fa596ec790545b64955280850",
    "protected:classification_rules": "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de",
    "protected:current_122": "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
}

EXPECTED_OUTBOX = {
    "files": 18,
    "bytes": 942264,
    "sha256": "d67a3be7df95bc34089237213049b201d6f8e22c2b971d7f6b76f48e125cc38d",
}

TEST_VALIDATION = {
    "before_change": {"passed": 360, "status": "pass"},
    "after_change": {"passed": 370, "subtests_passed": 19, "status": "pass"},
    "command": "PYTHONPATH=. pytest -q tests",
    "scope_note": "按 CZ 的 TEMP 全忽略口径，只收仓库 tests/ 正式测试集；TEMP/弃用路线归档不纳入。",
}


def part(
    part_id: str,
    claim: str,
    anchors: list[str],
    points: list[str],
    reason: str,
    *,
    layer: str = "当章可知",
    scoreable: bool = True,
) -> dict[str, Any]:
    return {
        "part_id": part_id,
        "layer": layer,
        "score_in_single_chapter": scoreable,
        "claim": claim,
        "anchor_ids": anchors,
        "semantic_point_ids": points,
        "reason": reason,
    }


ITEMS: list[dict[str, Any]] = [
    {
        "item_id": "GOLD-C0003-01",
        "decision": "保留原粒度并补足锚",
        "original_semantic_points": {
            "G01-SP01": "信息来自克莱恩残留的记忆碎片",
            "G01-SP02": "两天后参加廷根大学历史系面试",
        },
        "parts": [
            part(
                "GOLD-C0003-01-N01",
                "周明瑞从克莱恩残留的记忆碎片中得知，两天后要参加廷根大学历史系面试。",
                ["E0005", "E0022", "E0023"],
                ["G01-SP01", "G01-SP02"],
                "同一认知动作及其时间、信息来源限定，不拆。",
            )
        ],
    },
    {
        "item_id": "GOLD-C0003-02",
        "decision": "措辞对齐",
        "original_semantic_points": {"G02-SP01": "里间房门打开，梅丽莎随即将出来"},
        "parts": [
            part(
                "GOLD-C0003-02-N01",
                "里面房间的门吱呀打开，梅丽莎随即将从里间出来。",
                ["E0073", "E0074", "E0077", "E0078"],
                ["G02-SP01"],
                "原文没有直接写梅丽莎已走出，也没有明说开门者；改成正文能自证的场景变化。",
            )
        ],
    },
    {
        "item_id": "GOLD-C0003-03",
        "decision": "措辞对齐",
        "original_semantic_points": {"G03-SP01": "左轮手枪被放进并藏在书桌抽屉"},
        "parts": [
            part(
                "GOLD-C0003-03-N01",
                "眼见梅丽莎即将出来，周明瑞把左轮手枪丢进书桌抽屉，并关上抽屉遮住它。",
                ["E0077", "E0078", "E0079", "E0085", "E0086", "E0087"],
                ["G03-SP01"],
                "放枪与关抽屉是同一主体围绕同一物件形成隐藏完成态的连续步骤，按现行原子合同合写。",
            )
        ],
    },
    {
        "item_id": "GOLD-C0003-04",
        "decision": "措辞对齐",
        "original_semantic_points": {"G04-SP01": "周明瑞确认太阳穴伤口愈合"},
        "parts": [
            part(
                "GOLD-C0003-04-N01",
                "周明瑞通过触摸太阳穴位置，确定伤口已经愈合。",
                ["E0087", "E0088"],
                ["G04-SP01"],
                "把‘发现’对齐为原文明确写出的触摸确认。",
            )
        ],
    },
    {
        "item_id": "GOLD-C0003-05",
        "decision": "保留同一调表过程并措辞对齐",
        "original_semantic_points": {
            "G05-SP01": "梅丽莎操作怀表并使秒针恢复走动",
            "G05-SP02": "梅丽莎校准怀表时间",
        },
        "parts": [
            part(
                "GOLD-C0003-05-N01",
                "梅丽莎操作怀表，使秒针恢复走动，并在听完大教堂敲响六下后校准时间。",
                ["E0105", "E0106", "E0107", "E0110", "E0111", "E0112", "E0113"],
                ["G05-SP01", "G05-SP02"],
                "同一主体围绕同一怀表连续调节，恢复走动与校时共同形成一次完整调表结果，合写避免双计。",
            ),
        ],
    },
    {
        "item_id": "GOLD-C0003-06",
        "decision": "保留原粒度并补足锚",
        "original_semantic_points": {
            "G06-SP01": "梅丽莎嘱咐周明瑞购买面包、羔羊肉和豌豆",
            "G06-SP02": "这些食材用于做豌豆炖羔羊肉",
        },
        "parts": [
            part(
                "GOLD-C0003-06-N01",
                "梅丽莎提到周明瑞快参加面试，嘱咐他购买新面包、羔羊肉和豌豆，并表示会做豌豆炖羔羊肉。",
                ["E0131", "E0132", "E0133", "E0144", "E0145", "E0146"],
                ["G06-SP01", "G06-SP02", "G13-SP02"],
                "同一说话者的一次采购与做菜安排；只写并列事实，不把相邻语句改成确定因果。G13-SP02 在此别名映射，不重复计分。",
            )
        ],
    },
    {
        "item_id": "GOLD-C0003-07",
        "decision": "措辞对齐并补足锚",
        "original_semantic_points": {"G07-SP01": "梅丽莎关门离开公寓并前往技术学校上课"},
        "parts": [
            part(
                "GOLD-C0003-07-N01",
                "梅丽莎关门离开公寓，前往廷根技术学校上全天课。",
                ["E0154", "E0155", "E0172"],
                ["G07-SP01"],
                "同一离家移动及其明确目的；旧锚 E0173 在动作之后，改接 E0172。",
            )
        ],
    },
    {
        "item_id": "GOLD-C0003-08",
        "decision": "保留原粒度并补足锚",
        "original_semantic_points": {
            "G08-SP01": "周明瑞把注意力转向转运仪式",
            "G08-SP02": "周明瑞想回家",
        },
        "parts": [
            part(
                "GOLD-C0003-08-N01",
                "目送梅丽莎离开后，周明瑞把心思转向转运仪式，并表达了想回家的愿望。",
                ["E0172", "E0173", "E0174"],
                ["G08-SP01", "G08-SP02"],
                "转向仪式与回家愿望构成同一心理行动和目的；补 E0174 覆盖后半句。",
            )
        ],
    },
    {
        "item_id": "GOLD-C0003-09",
        "decision": "复合条拆原子并校正身份",
        "original_semantic_points": {
            "G09-SP01": "克莱恩记忆失去连贯并多处缺失",
            "G09-SP02": "转轮手枪来历未明",
            "G09-SP03": "克莱恩自杀还是他杀未明",
            "G09-SP04": "笔记句子的含义未明",
            "G09-SP05": "事发前两天是否参与怪事未明",
        },
        "parts": [
            part("GOLD-C0003-09-N01", "周明瑞发现克莱恩的记忆失去连贯性，且多处内容缺失。", ["E0011", "E0012", "E0013"], ["G09-SP01"], "把记忆状态单列。"),
            part("GOLD-C0003-09-N02", "周明瑞无法确认那把转轮手枪的来历。", ["E0013", "E0014"], ["G09-SP02"], "手枪来历是独立未解问题。"),
            part("GOLD-C0003-09-N03", "周明瑞无法确认克莱恩是自杀还是他杀。", ["E0014", "E0015"], ["G09-SP03"], "死亡性质是独立未解问题。"),
            part("GOLD-C0003-09-N04", "周明瑞无法解释笔记本上‘所有人都会死，包括我’的含义。", ["E0015", "E0016"], ["G09-SP04"], "笔记含义是独立未解问题。"),
            part("GOLD-C0003-09-N05", "周明瑞无法确认克莱恩事发前两天是否参与过奇怪的事情。", ["E0016", "E0017"], ["G09-SP05"], "事发前经历是独立未解问题。"),
        ],
    },
    {
        "item_id": "GOLD-C0003-10",
        "decision": "复合条拆原子；一处证据不足待拍",
        "original_semantic_points": {
            "G10-SP01": "克莱恩掌握的知识也已碎片化",
            "G10-SP02": "以当前状态回大学恐怕无法毕业",
            "G10-SP03": "大学面试结果关系全家收入改善",
        },
        "parts": [
            part("GOLD-C0003-10-N01", "周明瑞发现克莱恩掌握的知识也已碎片化并有所残缺。", ["E0017", "E0018", "E0019"], ["G10-SP01"], "知识状态与具体未解记忆分开。"),
            part("GOLD-C0003-10-N02", "周明瑞判断，克莱恩以当前状态回到大学也恐怕无法毕业。", ["E0019", "E0020", "E0021"], ["G10-SP02"], "把旧称‘面试风险’对齐为正文直接写出的毕业风险。"),
            part(
                "GOLD-C0003-10-N03",
                "克莱恩参加大学面试的结果关系全家收入改善。",
                ["E0022", "E0023", "E0024", "E0025"],
                ["G10-SP03"],
                "第3章没有直接写出家庭收入因果；为守禁放水闸保留为证据不足候选，但不进入成绩分母。",
                layer="证据不足候选",
                scoreable=False,
            ),
        ],
    },
    {
        "item_id": "GOLD-C0003-11",
        "decision": "复合条拆原子并去除能力概括",
        "original_semantic_points": {
            "G11-SP01": "梅丽莎立志成为蒸汽机械师",
            "G11-SP02": "梅丽莎借学校工具捣鼓怀表",
            "G11-SP03": "梅丽莎宣称已经修好怀表",
        },
        "parts": [
            part("GOLD-C0003-11-N01", "梅丽莎立志成为一名蒸汽机械师。", ["E0048", "E0049"], ["G11-SP01"], "志向单列。"),
            part("GOLD-C0003-11-N02", "梅丽莎掌握理论知识后，开始借助技术学校的工具捣鼓怀表。", ["E0096", "E0097", "E0098"], ["G11-SP02"], "把泛化的‘制作、修理显能力’还原成正文动作。"),
            part("GOLD-C0003-11-N03", "梅丽莎最近宣称已经修好了怀表。", ["E0098", "E0099"], ["G11-SP03"], "保留‘宣称’这一事实强度，不能升级为无条件修好。"),
        ],
    },
    {
        "item_id": "GOLD-C0003-12",
        "decision": "跨主体复合条拆原子并对齐措辞",
        "original_semantic_points": {
            "G12-SP01": "班森为保工作和生活接受更繁重任务",
            "G12-SP02": "克莱恩想帮助哥哥分担负担",
            "G12-SP03": "克莱恩受出身和教育背景限制而感到不足",
        },
        "parts": [
            part("GOLD-C0003-12-N01", "班森为保住工作并维持生活，接受了更加繁重的任务，必须经常加班或去恶劣环境出差。", ["E0057", "E0058", "E0059", "E0060", "E0061", "E0062", "E0063"], ["G12-SP01"], "同一主体的一次工作负担变化及其直接表现。"),
            part("GOLD-C0003-12-N02", "克莱恩想帮助哥哥分担家庭负担。", ["E0063", "E0064"], ["G12-SP02"], "把克莱恩的意愿从班森的工作变化中拆开。"),
            part("GOLD-C0003-12-N03", "克莱恩进入大学后，因平民出身和普通文法学校背景而强烈感到自身不足。", ["E0064", "E0065", "E0066", "E0067", "E0068", "E0069"], ["G12-SP03"], "旧句‘眼下尚无能力’强于正文，改成正文直接写出的限制。"),
        ],
    },
    {
        "item_id": "GOLD-C0003-13",
        "decision": "复合条拆原子；一处等价性待拍",
        "original_semantic_points": {
            "G13-SP01": "家庭食物拮据，旧句概括为平日肉食稀少",
            "G13-SP02": "因克莱恩快参加面试，梅丽莎安排豌豆炖羔羊肉",
        },
        "parts": [
            part("GOLD-C0003-13-N01", "梅丽莎和周明瑞喝劣等茶水，并分享两条黑麦面包。", ["E0136", "E0137", "E0138", "E0139", "E0140", "E0141", "E0142"], ["G13-SP01"], "第3章不能自证长期肉食频率；先改为正文直接出现的食物拮据实例，并列等价性待拍。"),
        ],
    },
    {
        "item_id": "GOLD-C0003-14",
        "decision": "保留原粒度并补足锚",
        "original_semantic_points": {
            "G14-SP01": "梅丽莎为省车费",
            "G14-SP02": "梅丽莎平时提前出门并步行去学校",
            "G14-SP03": "步行约五十分钟",
        },
        "parts": [
            part(
                "GOLD-C0003-14-N01",
                "为了省车费，梅丽莎平时都会提前出门，步行约五十分钟去廷根技术学校。",
                ["E0155", "E0156", "E0157", "E0158", "E0159"],
                ["G14-SP01", "G14-SP02", "G14-SP03"],
                "同一主体的一项习惯通勤，省钱和时长是必要限定；当前合同不再排除普通动作，因此不删。",
            )
        ],
    },
]


REVIEW_FLAGS = [
    {
        "flag_id": "Z72-DEL-CAND-01",
        "kind": "剔除候选",
        "target_part_ids": ["GOLD-C0003-10-N03"],
        "reason": "冻结第3章只有面试与推荐信，没有‘面试结果关系全家收入改善’的直接因果句。",
        "candidate_still_present": True,
        "preservation_note": "证据不足候选仍在候选台账，但不进入23条成绩分母。",
        "decision_owner": "CZ",
    },
    {
        "flag_id": "Z72-EQUIV-CAND-01",
        "kind": "措辞等价性候选",
        "target_part_ids": ["GOLD-C0003-13-N01"],
        "reason": "该次劣茶与黑麦面包的食用情境能自证食物拮据实例，但不能直接证明‘平日肉食稀少’这一长期频率。",
        "candidate_still_present": True,
        "preservation_note": "旧语义点和正文中劣茶与黑麦面包的食用实例均保留，二者是否等价等 CZ 拍。",
        "decision_owner": "CZ",
    },
    {
        "flag_id": "Z72-DUP-CAND-01",
        "kind": "别名与因果等价待拍",
        "target_part_ids": [],
        "target_semantic_point_ids": ["G13-SP02"],
        "related_part_ids": ["GOLD-C0003-06-N01"],
        "reason": "G13-SP02 与 GOLD-C0003-06-N01 来自同一句采购／做菜安排；不另建计分原子。但旧点含‘因面试’因果，新句只保留中性并列，二者是否等价仍待 CZ 拍。",
        "candidate_still_present": True,
        "preservation_note": "旧语义点编号仍声明指向 GOLD-C0003-06-N01，只取消重复计分；因果语义是否等价没有确认。",
        "decision_owner": "CZ",
    },
]

PENDING_SEMANTIC_POINT_IDS = {"G10-SP03", "G13-SP01", "G13-SP02"}
ALIAS_NON_SCORING_POINT_IDS = {"G13-SP02"}


def judge(status: str, event_ids: list[str], note: str) -> tuple[str, list[str], str]:
    return status, event_ids, note


# 人工语义判词。程序只校验事件 ID 存在并汇总，不推断严格／影子。
ADJUDICATIONS: dict[str, dict[str, tuple[str, list[str], str]]] = {
    "B0_Z57": {
        "GOLD-C0003-01-N01": judge("coverage_only_invalid_support", ["EV-C0003-03"], "事件句写出记忆来源、两天后和历史系面试，但只挂 E0022，锚没有托住记忆来源和完整院系信息，不计有效召回。"),
        "GOLD-C0003-02-N01": judge("miss", [], "没有抽到里间房门打开与梅丽莎将出来。"),
        "GOLD-C0003-03-N01": judge("semantic_shadow", ["EV-C0003-04"], "抽到手枪进入抽屉，但缺梅丽莎将出来的条件和关抽屉遮住的完成态。"),
        "GOLD-C0003-04-N01": judge("strict_hit", ["EV-C0003-05"], "完整写出周明瑞确认太阳穴伤口愈合。"),
        "GOLD-C0003-05-N01": judge("semantic_shadow", ["EV-C0003-06"], "只概括怀表修好并归还，未写按钮操作、秒针恢复与校准时间。"),
        "GOLD-C0003-06-N01": judge("semantic_shadow", ["EV-C0003-07"], "抽到采购清单，但漏快参加面试和做豌豆炖羔羊肉的安排。"),
        "GOLD-C0003-07-N01": judge("coverage_only_invalid_support", ["EV-C0003-09"], "事件句声称离家上学，但所挂锚停在开门和转身嘱咐，未覆盖关门离开完成态，不计有效召回。"),
        "GOLD-C0003-08-N01": judge("semantic_shadow", ["EV-C0003-10"], "抽到转向转运仪式，漏想回家的愿望。"),
        "GOLD-C0003-09-N01": judge("semantic_shadow", ["EV-C0003-02"], "只写审视记忆碎片，未明说失去连贯与多处缺失。"),
        "GOLD-C0003-09-N02": judge("miss", [], "没有抽到手枪来历未明。"),
        "GOLD-C0003-09-N03": judge("miss", [], "没有抽到自杀或他杀未明。"),
        "GOLD-C0003-09-N04": judge("miss", [], "没有抽到笔记句子含义未明。"),
        "GOLD-C0003-09-N05": judge("miss", [], "没有抽到事发前两天是否参与怪事。"),
        "GOLD-C0003-10-N01": judge("miss", [], "审视记忆碎片不等于抽到知识也碎片化。"),
        "GOLD-C0003-10-N02": judge("miss", [], "没有抽到回大学恐怕无法毕业。"),
        "GOLD-C0003-11-N01": judge("miss", [], "没有抽到蒸汽机械师志向。"),
        "GOLD-C0003-11-N02": judge("miss", [], "‘已经修好怀表’不是此前借学校工具捣鼓怀表这一动作。"),
        "GOLD-C0003-11-N03": judge("miss", [], "‘已经修好怀表’没有抽出梅丽莎最近‘宣称修好’这一言语行为。"),
        "GOLD-C0003-12-N01": judge("miss", [], "没有抽到班森承担繁重任务。"),
        "GOLD-C0003-12-N02": judge("miss", [], "没有抽到克莱恩想帮哥哥。"),
        "GOLD-C0003-12-N03": judge("miss", [], "没有抽到克莱恩的教育背景不足。"),
        "GOLD-C0003-13-N01": judge("miss", [], "没有抽到劣茶与黑麦面包的食用情境。"),
        "GOLD-C0003-14-N01": judge("semantic_shadow", ["EV-C0003-09"], "只写离家上学，漏省车费、提前出门和约五十分钟。"),
    },
    "Z68C": {
        "GOLD-C0003-01-N01": judge("semantic_shadow", ["EV-C0003-03"], "抽到面试和推荐信，但漏‘两天后’。"),
        "GOLD-C0003-02-N01": judge("miss", [], "没有抽到里间房门打开与梅丽莎将出来。"),
        "GOLD-C0003-03-N01": judge("coverage_only_invalid_support", ["EV-C0003-04"], "事件句写到藏枪，但锚停在拉开抽屉，未托住放入、关抽屉和遮枪完成态，不计有效召回。"),
        "GOLD-C0003-04-N01": judge("coverage_only_invalid_support", ["EV-C0003-05"], "事件句写出伤口愈合，但锚 E0087 未覆盖 E0088 的愈合结果，不计有效召回。"),
        "GOLD-C0003-05-N01": judge("semantic_shadow", ["EV-C0003-07"], "写出按钮操作、秒针走动与对好时间，但漏听完大教堂六下钟声这一明示校时限定。"),
        "GOLD-C0003-06-N01": judge("semantic_shadow", ["EV-C0003-11"], "采购与做菜安排完整，但漏快参加面试这一并列信息。"),
        "GOLD-C0003-07-N01": judge("coverage_only_invalid_support", ["EV-C0003-20"], "事件句写出离开并前往学校，但所挂 E0173 是周明瑞转向仪式，未托住梅丽莎离家，不计有效召回。"),
        "GOLD-C0003-08-N01": judge("semantic_shadow", ["EV-C0003-21"], "写出转向仪式和想回家，但漏目送梅丽莎离开后的明示条件。"),
        "GOLD-C0003-09-N01": judge("semantic_shadow", ["EV-C0003-02"], "只写审视记忆碎片，未明说连贯性与缺失。"),
        "GOLD-C0003-09-N02": judge("miss", [], "没有抽到手枪来历未明。"),
        "GOLD-C0003-09-N03": judge("semantic_shadow", ["EV-C0003-09"], "抽到自杀经过诡异，但没有保留自杀或他杀两种可能。"),
        "GOLD-C0003-09-N04": judge("miss", [], "没有抽到笔记句子含义未明。"),
        "GOLD-C0003-09-N05": judge("miss", [], "没有抽到事发前两天是否参与怪事。"),
        "GOLD-C0003-10-N01": judge("miss", [], "记忆碎片事件没有覆盖知识碎片。"),
        "GOLD-C0003-10-N02": judge("miss", [], "面试与推荐信事件没有覆盖回大学恐怕无法毕业。"),
        "GOLD-C0003-11-N01": judge("miss", [], "没有蒸汽机械师志向。"),
        "GOLD-C0003-11-N02": judge("miss", [], "当场操作怀表不是此前借学校工具捣鼓怀表。"),
        "GOLD-C0003-11-N03": judge("miss", [], "当场实际调表没有抽出梅丽莎此前‘宣称修好’这一言语行为。"),
        "GOLD-C0003-12-N01": judge("miss", [], "没有班森工作负担。"),
        "GOLD-C0003-12-N02": judge("miss", [], "没有克莱恩帮哥哥的意愿。"),
        "GOLD-C0003-12-N03": judge("miss", [], "没有教育背景不足。"),
        "GOLD-C0003-13-N01": judge("strict_hit", ["EV-C0003-12", "EV-C0003-13"], "两条事件合起来完整覆盖喝劣茶与分享黑麦面包。"),
        "GOLD-C0003-14-N01": judge("semantic_shadow", ["EV-C0003-16", "EV-C0003-20"], "只覆盖出门和去学校，漏省车费、提前与五十分钟。"),
    },
    "Z70": {
        "GOLD-C0003-01-N01": judge("coverage_only_invalid_support", ["EV-C0003-03"], "事件句完整，但只挂 E0022，未托住记忆来源与完整院系信息，不计有效召回。"),
        "GOLD-C0003-02-N01": judge("strict_hit", ["EV-C0003-08"], "明确写出打开隔离门并从里间走出。"),
        "GOLD-C0003-03-N01": judge("strict_hit", ["EV-C0003-09"], "触发条件、放入抽屉和关抽屉掩盖完整。"),
        "GOLD-C0003-04-N01": judge("strict_hit", ["EV-C0003-10"], "完整写出触摸确认伤口愈合。"),
        "GOLD-C0003-05-N01": judge("strict_hit", ["EV-C0003-12"], "明确写出按钮操作使秒针走动，并依据钟声对好时间。"),
        "GOLD-C0003-06-N01": judge("semantic_shadow", ["EV-C0003-16"], "采购与做菜安排完整，但漏快参加面试这一并列信息。"),
        "GOLD-C0003-07-N01": judge("semantic_shadow", ["EV-C0003-20", "EV-C0003-24"], "只写准备出门及后来已离开，没有直接抽出关门去技术学校。"),
        "GOLD-C0003-08-N01": judge("semantic_shadow", ["EV-C0003-24"], "抽到转向仪式，但漏想回家。"),
        "GOLD-C0003-09-N01": judge("coverage_only_invalid_support", ["EV-C0003-02"], "事件句写出记忆失去连贯且多处缺失，但所挂锚没有完整覆盖‘多处内容缺失’结果，不计有效召回。"),
        "GOLD-C0003-09-N02": judge("miss", [], "没有手枪来历未明。"),
        "GOLD-C0003-09-N03": judge("semantic_shadow", ["EV-C0003-14"], "抽到自杀经过诡异，但没有保留自杀或他杀的两种可能。"),
        "GOLD-C0003-09-N04": judge("miss", [], "没有笔记含义未明。"),
        "GOLD-C0003-09-N05": judge("miss", [], "没有事发前两天是否参与怪事。"),
        "GOLD-C0003-10-N01": judge("miss", [], "记忆缺失事件没有覆盖知识也碎片化。"),
        "GOLD-C0003-10-N02": judge("miss", [], "过去靠努力毕业不等于当前状态回大学恐怕无法毕业。"),
        "GOLD-C0003-11-N01": judge("miss", [], "没有机械师志向。"),
        "GOLD-C0003-11-N02": judge("miss", [], "当场操作怀表不是此前借学校工具捣鼓。"),
        "GOLD-C0003-11-N03": judge("miss", [], "当场实际调表没有抽出梅丽莎此前‘宣称修好’这一言语行为。"),
        "GOLD-C0003-12-N01": judge("semantic_shadow", ["EV-C0003-05"], "抽到公司业务缩水和更繁重工作，但漏班森为保工作、维持生活的必要目的。"),
        "GOLD-C0003-12-N02": judge("miss", [], "没有克莱恩想帮哥哥。"),
        "GOLD-C0003-12-N03": judge("semantic_shadow", ["EV-C0003-07"], "覆盖平民出身与课程落后，但没有明确写出进入大学后强烈感到自身不足。"),
        "GOLD-C0003-13-N01": judge("semantic_shadow", ["EV-C0003-17"], "覆盖泡茶与食用黑麦面包，但事件句漏‘劣等茶’限定。"),
        "GOLD-C0003-14-N01": judge("semantic_shadow", ["EV-C0003-20", "EV-C0003-24"], "只覆盖准备出门及后来离开，漏省钱、提前与五十分钟。"),
    },
    "Z71": {
        "GOLD-C0003-01-N01": judge("semantic_shadow", ["EV-C0003-03"], "抽到面试和推荐信，但漏‘两天后’。"),
        "GOLD-C0003-02-N01": judge("miss", [], "没有抽到里间房门打开与梅丽莎将出来。"),
        "GOLD-C0003-03-N01": judge("coverage_only_invalid_support", ["EV-C0003-04"], "事件句写到藏枪，但锚停在拉开抽屉，未托住放入、关抽屉和遮枪完成态，不计有效召回。"),
        "GOLD-C0003-04-N01": judge("coverage_only_invalid_support", ["EV-C0003-05"], "事件句写出伤口愈合，但锚 E0087 未覆盖 E0088 的愈合结果，不计有效召回。"),
        "GOLD-C0003-05-N01": judge("coverage_only_invalid_support", ["EV-C0003-07"], "事件句补入钟声限定，但正式事件锚未覆盖钟声信息；旁路 provenance 未进入本评分输入，不计有效召回。"),
        "GOLD-C0003-06-N01": judge("coverage_only_invalid_support", ["EV-C0003-11"], "事件句把相邻并列写成面试导致采购做菜，且所挂锚未支撑该因果连接；沿用 Z71 支撑失败，不计有效召回。"),
        "GOLD-C0003-07-N01": judge("coverage_only_invalid_support", ["EV-C0003-20"], "事件句写出离开并前往学校，但所挂 E0173 是周明瑞转向仪式，未托住梅丽莎离家，不计有效召回。"),
        "GOLD-C0003-08-N01": judge("semantic_shadow", ["EV-C0003-21"], "写出转向仪式和想回家，但漏目送梅丽莎离开后的明示条件。"),
        "GOLD-C0003-09-N01": judge("semantic_shadow", ["EV-C0003-02"], "只写审视记忆碎片，未明说连贯性与缺失。"),
        "GOLD-C0003-09-N02": judge("miss", [], "没有手枪来历未明。"),
        "GOLD-C0003-09-N03": judge("semantic_shadow", ["EV-C0003-09"], "抽到自杀经过诡异，但没有保留自杀或他杀两种可能。"),
        "GOLD-C0003-09-N04": judge("miss", [], "没有笔记含义未明。"),
        "GOLD-C0003-09-N05": judge("miss", [], "没有事发前两天是否参与怪事。"),
        "GOLD-C0003-10-N01": judge("miss", [], "记忆碎片事件没有覆盖知识碎片。"),
        "GOLD-C0003-10-N02": judge("miss", [], "面试与推荐信事件没有覆盖回大学恐怕无法毕业。"),
        "GOLD-C0003-11-N01": judge("miss", [], "没有蒸汽机械师志向。"),
        "GOLD-C0003-11-N02": judge("miss", [], "当场操作怀表不是此前借学校工具捣鼓。"),
        "GOLD-C0003-11-N03": judge("miss", [], "当场实际调表没有抽出梅丽莎此前‘宣称修好’这一言语行为。"),
        "GOLD-C0003-12-N01": judge("miss", [], "没有班森工作负担。"),
        "GOLD-C0003-12-N02": judge("miss", [], "没有克莱恩帮哥哥的意愿。"),
        "GOLD-C0003-12-N03": judge("miss", [], "没有教育背景不足。"),
        "GOLD-C0003-13-N01": judge("strict_hit", ["EV-C0003-12", "EV-C0003-13"], "两条事件合起来完整覆盖喝劣茶与分享黑麦面包。"),
        "GOLD-C0003-14-N01": judge("semantic_shadow", ["EV-C0003-16", "EV-C0003-20"], "只覆盖出门和去学校，漏省车费、提前与五十分钟。"),
    },
}


OLD_SCORES = {
    "B0_Z57": {"strict_hit": 2, "semantic_recalled": 12, "total": 14},
    "Z68C": {"strict_hit": 6, "semantic_recalled": 13, "total": 14},
    "Z70": {"strict_hit": 6, "semantic_recalled": 14, "total": 14},
    "Z71": {"strict_hit": 6, "semantic_recalled": 13, "total": 14},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON 顶层不是对象：{path}")
    return value


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tree_fingerprint(path: Path) -> dict[str, Any]:
    rows: list[tuple[str, str, int]] = []
    for file in sorted(p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        rows.append((str(file.relative_to(path)), sha256(file), file.stat().st_size))
    payload = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def check_sha_inputs() -> dict[str, str]:
    actual = {
        "gold_v1_1": sha256(GOLD_V1_1),
        "chapter_text": sha256(CHAPTER_TEXT),
        "evidence_catalog": sha256(EVIDENCE_CATALOG),
    }
    actual.update({f"sample:{name}": sha256(path) for name, path in SAMPLE_PATHS.items()})
    actual.update({f"old_score:{name}": sha256(path) for name, path in OLD_SCORE_PATHS.items()})
    actual.update({f"run_gate:{name}": sha256(path) for name, path in RUN_GATE_PATHS.items()})
    actual.update({f"protected:{name}": sha256(path) for name, path in PROTECTED_PATHS.items()})
    if actual != EXPECTED_SHA256:
        mismatches = {key: {"expected": EXPECTED_SHA256.get(key), "actual": value} for key, value in actual.items() if EXPECTED_SHA256.get(key) != value}
        raise AssertionError(f"冻结输入或保护件 SHA 漂移：{mismatches}")
    if tree_fingerprint(ROOT / "outbox") != EXPECTED_OUTBOX:
        raise AssertionError("outbox 指纹漂移")
    for run_id, path in RUN_GATE_PATHS.items():
        gate = load_json(path)
        if gate.get("status") != "fail" or gate.get("disposition") != "hard_stop_no_repair":
            raise AssertionError(f"{run_id} 失败／硬停闸漂移")
    return actual


def catalog_rows() -> dict[str, dict[str, Any]]:
    catalog = load_json(EVIDENCE_CATALOG)
    rows = catalog.get("anchors") or catalog.get("evidence_catalog") or catalog.get("items") or catalog.get("entries")
    if not isinstance(rows, list):
        raise AssertionError("冻结证据目录未找到 anchors 列表")
    result = {str(row["anchor_id"]): row for row in rows}
    if len(result) != 175:
        raise AssertionError(f"冻结目录锚数不是175：{len(result)}")
    return result


def build_candidate(anchor_map: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    old_gold = load_json(GOLD_V1_1)
    old_ids = [item["item_id"] for item in old_gold["layered_items"]]
    if old_ids != [item["item_id"] for item in ITEMS]:
        raise AssertionError("14条旧金标映射顺序不完整")

    chapter_text = CHAPTER_TEXT.read_text(encoding="utf-8")
    candidate_items: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    old_point_ids: list[str] = []
    mapped_point_ids: list[str] = []
    anchor_checks: list[dict[str, Any]] = []
    old_by_id = {item["item_id"]: item for item in old_gold["layered_items"]}

    for definition in ITEMS:
        item_id = definition["item_id"]
        point_map = definition["original_semantic_points"]
        old_point_ids.extend(point_map)
        parts: list[dict[str, Any]] = []
        for raw_part in definition["parts"]:
            resolved_anchors: list[dict[str, Any]] = []
            for anchor_id in raw_part["anchor_ids"]:
                if anchor_id not in anchor_map:
                    raise AssertionError(f"候选锚不存在：{raw_part['part_id']} {anchor_id}")
                anchor = anchor_map[anchor_id]
                quote = anchor["quote"]
                if quote not in chapter_text:
                    raise AssertionError(f"候选锚不能回读冻结正文：{raw_part['part_id']} {anchor_id}")
                resolved_anchors.append(
                    {
                        "chapter": 3,
                        "anchor_id": anchor_id,
                        "identity_key": f"ch0003:{anchor_id}",
                        "quote": quote,
                    }
                )
                anchor_checks.append({"part_id": raw_part["part_id"], "anchor_id": anchor_id, "status": "pass"})
            mapped_point_ids.extend(raw_part["semantic_point_ids"])
            parts.append(
                {
                    "part_id": raw_part["part_id"],
                    "layer": raw_part["layer"],
                    "score_in_single_chapter": raw_part["score_in_single_chapter"],
                    "claim": raw_part["claim"],
                    "source_evidence": resolved_anchors,
                    "semantic_point_ids": raw_part["semantic_point_ids"],
                    "verdict": raw_part["reason"],
                    "review_flag_ids": [
                        flag["flag_id"]
                        for flag in REVIEW_FLAGS
                        if raw_part["part_id"] in flag.get("target_part_ids", [])
                        or raw_part["part_id"] in flag.get("related_part_ids", [])
                    ],
                }
            )
        hindsight = [part for part in old_by_id[item_id]["parts"] if part["layer"] == "回看件"]
        candidate_items.append(
            {
                "item_id": item_id,
                "source_kind": old_by_id[item_id]["source_kind"],
                "source_id": old_by_id[item_id]["source_id"],
                "decision": definition["decision"],
                "original_semantic_points": [{"semantic_point_id": key, "meaning": value} for key, value in point_map.items()],
                "parts": parts,
                "hindsight_parts_inherited_unchanged": hindsight,
            }
        )
        mapping_rows.append(
            {
                "old_item_id": item_id,
                "old_on_chapter_claim": next(part["claim"] for part in old_by_id[item_id]["parts"] if part["layer"] == "当章可知"),
                "decision": definition["decision"],
                "new_part_ids": [part["part_id"] for part in parts],
                "semantic_point_ids": list(point_map),
                "hindsight_part_ids_unchanged": [part["part_id"] for part in hindsight],
            }
        )

    if sorted(old_point_ids) != sorted(mapped_point_ids):
        raise AssertionError("旧语义点编号与候选声明编号不相等，存在编号孤儿、重复或新增")
    if len(old_point_ids) != len(set(old_point_ids)):
        raise AssertionError("旧语义点 ID 不唯一")

    point_destinations: dict[str, list[dict[str, Any]]] = {point_id: [] for point_id in old_point_ids}
    for candidate_item in candidate_items:
        for candidate_part in candidate_item["parts"]:
            for point_id in candidate_part["semantic_point_ids"]:
                point_destinations[point_id].append(
                    {
                        "part_id": candidate_part["part_id"],
                        "score_in_single_chapter": candidate_part["score_in_single_chapter"],
                        "layer": candidate_part["layer"],
                    }
                )
    for row in mapping_rows:
        row["semantic_point_mappings"] = [
            {
                "semantic_point_id": point_id,
                "destinations": point_destinations[point_id],
                "local_text_review_status": (
                    "pending_cz_equivalence_or_deletion_review"
                    if point_id in PENDING_SEMANTIC_POINT_IDS
                    else "pass_frozen_chapter_evidence_review"
                ),
                "alias_non_scoring": point_id in ALIAS_NON_SCORING_POINT_IDS,
            }
            for point_id in row["semantic_point_ids"]
        ]

    scoreable_parts = [part for item in candidate_items for part in item["parts"] if part["score_in_single_chapter"]]
    unscoreable_candidates = [part for item in candidate_items for part in item["parts"] if not part["score_in_single_chapter"]]

    candidate = {
        "schema_version": "structure-gold-v1.2-candidate",
        "gold_id": "X01-ch0003-structure-v1.2-candidate",
        "task": "第72道",
        "status": "candidate_pending_cz_review",
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "formal_gold_until_approval": {
            "path": str(GOLD_V1_1.relative_to(ROOT)),
            "sha256": EXPECTED_SHA256["gold_v1_1"],
            "status": "active_gold_unchanged",
        },
        "source": old_gold["source"],
        "evaluation_policy": old_gold["evaluation_policy"],
        "atomicity_policy": {
            "one_central_fact_head": True,
            "different_subjects_must_split": True,
            "independently_truth_testable_results_must_split": True,
            "same_subject_same_object_continuous_steps_may_merge_when_they_form_one_completion_state": True,
            "necessary_explicit_time_condition_result_must_remain_in_claim": True,
            "unsupported_details_must_not_be_invented": True,
        },
        "layer_summary": {
            "base_item_total": len(candidate_items),
            "candidate_part_total": sum(len(item["parts"]) for item in candidate_items),
            "on_chapter_atomic_part_total": len(scoreable_parts),
            "evidence_insufficient_candidate_total": len(unscoreable_candidates),
            "review_state_unit_total": len(scoreable_parts) + len(REVIEW_FLAGS),
            "hindsight_part_total": sum(len(item["hindsight_parts_inherited_unchanged"]) for item in candidate_items),
            "declared_old_semantic_point_total": len(old_point_ids),
            "declared_destination_point_total": len(mapped_point_ids),
            "declared_point_id_orphan_total": 0,
            "local_text_semantic_review_pass_total": len(old_point_ids) - len(PENDING_SEMANTIC_POINT_IDS),
            "cz_semantic_review_pending_total": len(PENDING_SEMANTIC_POINT_IDS),
            "semantic_deletion_count": 0,
            "semantic_equivalence_status": "28_local_text_reviewed_3_pending_cz_not_fully_proven",
        },
        "layered_items": candidate_items,
        "review_flags": REVIEW_FLAGS,
        "protected_state": {
            "gold_v1_rewritten": False,
            "gold_v1_1_rewritten": False,
            "current_122_records_rewritten": False,
            "default_runner_rewritten": False,
            "default_registry_rewritten": False,
            "classification_rules_rewritten": False,
            "outbox_rewritten": False,
            "four_round_samples_rerun": False,
            "model_api_calls": 0,
            "network_requests": 0,
            "token_usage": 0,
        },
    }
    mapping = {
        "schema_version": "z72-v1.1-to-v1.2-candidate-mapping-v1",
        "status": "pass_declared_point_ids_no_orphans_semantic_equivalence_pending",
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "old_base_item_total": len(old_ids),
        "mapped_old_base_item_total": len(mapping_rows),
        "candidate_part_total": sum(len(item["parts"]) for item in candidate_items),
        "new_scoreable_atomic_part_total": len(scoreable_parts),
        "evidence_insufficient_candidate_total": len(unscoreable_candidates),
        "review_state_unit_total": len(scoreable_parts) + len(REVIEW_FLAGS),
        "declared_old_semantic_point_total": len(old_point_ids),
        "declared_destination_point_total": len(mapped_point_ids),
        "declared_point_id_orphan_total": 0,
        "local_text_semantic_review_pass_total": len(old_point_ids) - len(PENDING_SEMANTIC_POINT_IDS),
        "cz_semantic_review_pending_ids": sorted(PENDING_SEMANTIC_POINT_IDS),
        "semantic_deletion_count": 0,
        "semantic_equivalence_status": "pending_cz_not_mechanically_proven",
        "orphan_old_item_ids": [],
        "orphan_semantic_point_ids": [],
        "rows": mapping_rows,
        "anchor_validation": {
            "status": "pass",
            "anchor_occurrence_total": len(anchor_checks),
            "checks": anchor_checks,
        },
        "review_flags": REVIEW_FLAGS,
    }
    return candidate, mapping


def build_scores(candidate: dict[str, Any]) -> dict[str, Any]:
    all_parts = [part for item in candidate["layered_items"] for part in item["parts"]]
    parts = [part for part in all_parts if part["score_in_single_chapter"]]
    part_ids = [part["part_id"] for part in parts]
    part_by_id = {part["part_id"]: part for part in parts}
    all_part_by_id = {part["part_id"]: part for part in all_parts}
    point_destinations: dict[str, list[str]] = {}
    for part_row in all_parts:
        for point_id in part_row["semantic_point_ids"]:
            point_destinations.setdefault(point_id, []).append(part_row["part_id"])
    item_parts: dict[str, list[str]] = {}
    item_pending_point_ids: dict[str, list[str]] = {}
    item_alias_point_ids: dict[str, list[str]] = {}
    for item in candidate["layered_items"]:
        point_ids = [point["semantic_point_id"] for point in item["original_semantic_points"]]
        item_parts[item["item_id"]] = [part["part_id"] for part in item["parts"]]
        item_pending_point_ids[item["item_id"]] = sorted(set(point_ids) & PENDING_SEMANTIC_POINT_IDS)
        item_alias_point_ids[item["item_id"]] = sorted(set(point_ids) & ALIAS_NON_SCORING_POINT_IDS)
    rounds: list[dict[str, Any]] = []

    for round_id, sample_path in SAMPLE_PATHS.items():
        sample_events = {event["event_id"]: event for event in load_json(sample_path)["events"]}
        round_judges = ADJUDICATIONS[round_id]
        if sorted(round_judges) != sorted(part_ids):
            raise AssertionError(f"{round_id} 人工判词没有覆盖全部候选原子")
        rows: list[dict[str, Any]] = []
        for part_id in part_ids:
            status, event_ids, note = round_judges[part_id]
            if status not in {"strict_hit", "semantic_shadow", "coverage_only_invalid_support", "miss"}:
                raise AssertionError(f"非法人工判词：{round_id} {part_id} {status}")
            missing_ids = [event_id for event_id in event_ids if event_id not in sample_events]
            if missing_ids:
                raise AssertionError(f"人工判词引用不存在的事件：{round_id} {part_id} {missing_ids}")
            if status == "miss" and event_ids:
                raise AssertionError(f"miss 不得挂事件：{round_id} {part_id}")
            if status != "miss" and not event_ids:
                raise AssertionError(f"命中、影子或无效支撑观察必须挂事件：{round_id} {part_id}")
            counts_toward_recall = status in {"strict_hit", "semantic_shadow"}
            rows.append(
                {
                    "part_id": part_id,
                    "claim": part_by_id[part_id]["claim"],
                    "verdict": status,
                    "candidate_event_ids": event_ids,
                    "candidate_events": [sample_events[event_id]["event"] for event_id in event_ids],
                    "semantic_review_note": note,
                    "review_flag_ids": part_by_id[part_id]["review_flag_ids"],
                    "counts_toward_effective_semantic_recall": counts_toward_recall,
                }
            )

        strict = sum(row["verdict"] == "strict_hit" for row in rows)
        shadow = sum(row["verdict"] == "semantic_shadow" for row in rows)
        invalid_support = sum(row["verdict"] == "coverage_only_invalid_support" for row in rows)
        recalled = sum(row["counts_toward_effective_semantic_recall"] for row in rows)
        actual_miss = sum(row["verdict"] == "miss" for row in rows)
        base_rows: list[dict[str, Any]] = []
        for item_id, ids in item_parts.items():
            scoreable_ids = [part_id for part_id in ids if all_part_by_id[part_id]["score_in_single_chapter"]]
            pending_ids = [part_id for part_id in ids if not all_part_by_id[part_id]["score_in_single_chapter"]]
            statuses = [round_judges[part_id][0] for part_id in scoreable_ids]
            pending_point_ids = item_pending_point_ids[item_id]
            alias_point_ids = item_alias_point_ids[item_id]
            alias_part_ids = list(
                dict.fromkeys(
                    part_id
                    for point_id in alias_point_ids
                    for part_id in point_destinations.get(point_id, [])
                    if part_id not in ids
                )
            )
            alias_statuses = [round_judges[part_id][0] for part_id in alias_part_ids if part_id in round_judges]
            if any(status in {"strict_hit", "semantic_shadow"} for status in alias_statuses):
                alias_observation = "aliased_observed_not_counted"
            elif any(status == "coverage_only_invalid_support" for status in alias_statuses):
                alias_observation = "aliased_coverage_invalid_not_counted"
            else:
                alias_observation = "aliased_not_observed"
            if pending_ids or pending_point_ids:
                verdict = "pending_evidence_review"
            elif statuses and all(status == "strict_hit" for status in statuses):
                verdict = "complete"
            elif any(status in {"strict_hit", "semantic_shadow"} for status in statuses):
                verdict = "observed_incomplete"
            else:
                verdict = "miss"
            base_rows.append(
                {
                    "old_item_id": item_id,
                    "candidate_part_ids": ids,
                    "scoreable_part_ids": scoreable_ids,
                    "pending_evidence_part_ids": pending_ids,
                    "pending_semantic_point_ids": pending_point_ids,
                    "part_verdicts": statuses,
                    "alias_non_scoring_point_ids": alias_point_ids,
                    "alias_destination_part_ids": alias_part_ids,
                    "alias_observation": alias_observation,
                    "diagnostic_rollup": verdict,
                }
            )
        base_complete = sum(row["diagnostic_rollup"] == "complete" for row in base_rows)
        base_observed = sum(row["diagnostic_rollup"] in {"complete", "observed_incomplete"} for row in base_rows)
        base_pending = sum(row["diagnostic_rollup"] == "pending_evidence_review" for row in base_rows)
        rounds.append(
            {
                "round_id": round_id,
                "sample": {"path": str(sample_path.relative_to(ROOT)), "sha256": sha256(sample_path), "rerun": False},
                "old_v1_1": OLD_SCORES[round_id],
                "v1_2_candidate_atomic": {
                    "strict_hit": strict,
                    "semantic_shadow": shadow,
                    "semantic_recalled": recalled,
                    "coverage_only_invalid_support": invalid_support,
                    "miss": actual_miss,
                    "not_effectively_recalled": len(rows) - recalled,
                    "total": len(rows),
                    "strict_hit_rate": strict / len(rows),
                    "semantic_recall_rate": recalled / len(rows),
                },
                "v1_2_candidate_old_item_diagnostic": {
                    "complete": base_complete,
                    "observed": base_observed,
                    "miss": len(base_rows) - base_observed - base_pending,
                    "pending_evidence_review": base_pending,
                    "total": len(base_rows),
                    "rule": "只作完整性观察：只看该旧底件自己的候选原子；全部严格才记完整；有效严格或影子才记已观察；无效支撑观察不计；含证据不足或语义等价待拍点则单列待审；别名观察单列且不抬分。不是新正式分数。",
                },
                "rows": rows,
                "base_item_rollup_rows": base_rows,
            }
        )

    return {
        "schema_version": "z72-four-round-zero-call-rejudge-v1",
        "task": "第72道",
        "status": "candidate_display_only_old_scores_not_rewritten",
        "model_api_calls": 0,
        "sample_reruns": 0,
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "score_policy": {
            "strict_hit": "人工确认同一原子的主体、中心谓词、直接结果和必要限定均被事件句与所挂锚覆盖。",
            "semantic_shadow": "人工确认同一核心谓词已出现，但缺必要限定或事实强度不一致。",
            "coverage_only_invalid_support": "事件句表面覆盖候选，但其正式所挂锚没有托住该主张，或已触发原文支撑失败；仅留诊断观察，不计有效语义召回。",
            "miss": "没有同一核心谓词；只有同场景、同主题或相邻事实不算影子。",
            "automation": "none_manual_verdicts_only",
            "denominator_guard": "23个可计分原子是唯一候选分母；另列14底件完整性观察和26状态台账，不把23、24、26混成一个成绩。",
        },
        "state_ledger": {
            "scoreable_atoms": 23,
            "insufficient_evidence_candidates": 1,
            "wording_equivalence_pending_points": 1,
            "alias_causal_equivalence_pending_points": 1,
            "total_units": 26,
            "hindsight_parts_outside_ledger": 2,
        },
        "run_level_gates_preserved": {
            "B0_Z57": {"status": "baseline_completed_unchanged"},
            "Z68C": {"status": "candidate_result_unchanged"},
            "Z70": {
                "status": load_json(RUN_GATE_PATHS["Z70"])["status"],
                "disposition": load_json(RUN_GATE_PATHS["Z70"])["disposition"],
                "source_path": str(RUN_GATE_PATHS["Z70"].relative_to(ROOT)),
                "source_sha256": sha256(RUN_GATE_PATHS["Z70"]),
                "preserved": True,
            },
            "Z71": {
                "status": load_json(RUN_GATE_PATHS["Z71"])["status"],
                "disposition": load_json(RUN_GATE_PATHS["Z71"])["disposition"],
                "source_path": str(RUN_GATE_PATHS["Z71"].relative_to(ROOT)),
                "source_sha256": sha256(RUN_GATE_PATHS["Z71"]),
                "preserved": True,
            },
        },
        "review_flags_apply_to_all_rounds": REVIEW_FLAGS,
        "rounds": rounds,
    }


def build_markdown(candidate: dict[str, Any], scores: dict[str, Any], mapping: dict[str, Any]) -> str:
    def md_cell(value: Any) -> str:
        return str(value).replace("|", "｜").replace("\r", "").replace("\n", "<br>")

    summary = candidate["layer_summary"]
    rows = [
        "# 第72道停点回包｜第3章金标粒度 v1.2 候选",
        "",
        "## 结论",
        "",
        "第3章金标 v1.2 候选草案已生成，但**没有转正**。v1.1 原件仍是正式判分尺。草案保留全部旧语义点编号，没有自行删除；其中 3 个语义点仍停在 CZ 审定，不能把‘编号有去处’说成‘语义已经完全等价’。",
        "",
        f"- 旧底件：{summary['base_item_total']} 条；可计分当章原子：{summary['on_chapter_atomic_part_total']} 条；证据不足候选：{summary['evidence_insufficient_candidate_total']} 条；回看件仍为 {summary['hindsight_part_total']} 条。",
        f"- 口径台账：23 个可计分原子＋1 个证据不足＋1 个措辞等价待拍＋1 个别名因果等价待拍＝{summary['review_state_unit_total']} 个状态单元；两条回看件另列。",
        f"- 声明编号：旧 {summary['declared_old_semantic_point_total']} 个，候选去向 {summary['declared_destination_point_total']} 个，编号孤儿 {summary['declared_point_id_orphan_total']}；冻结正文复核通过 {summary['local_text_semantic_review_pass_total']} 个，待 CZ {summary['cz_semantic_review_pending_total']} 个。",
        "- 模型 API 调用 0，四轮样张重跑 0；B0、Z68C、Z70、Z71 只读重判。",
        "- 严格分和有效影子分只收‘事件句与它正式所挂锚共同托住’的项目；文字表面命中但锚不支撑者单列为‘看见了但证据无效’，不计有效召回。",
        "",
        "## 14 条逐条处置",
        "",
        "| 旧金标件 | 处置 | 新部件数 | 逐条判词 |",
        "|---|---|---:|---|",
    ]
    for item in candidate["layered_items"]:
        notes = "；".join(f"{part['part_id']}：{part['verdict']}" for part in item["parts"])
        rows.append(f"| {item['item_id']} | {md_cell(item['decision'])} | {len(item['parts'])} | {md_cell(notes)} |")

    rows.extend(["", "## v1.2 候选草案全文", "", "| 候选部件 | 层／计分 | 候选事件句 | 冻结锚与原文短引 | 旧语义点 |", "|---|---|---|---|---|"])
    for item in candidate["layered_items"]:
        for part_row in item["parts"]:
            evidence = "；".join(
                f"{anchor['anchor_id']}={anchor['quote']}" for anchor in part_row["source_evidence"]
            )
            score_label = "计分" if part_row["score_in_single_chapter"] else "不计分待拍"
            rows.append(
                f"| {part_row['part_id']} | {part_row['layer']}／{score_label} | {md_cell(part_row['claim'])} | "
                f"{md_cell(evidence)} | {md_cell('、'.join(part_row['semantic_point_ids']))} |"
            )
        for hindsight in item["hindsight_parts_inherited_unchanged"]:
            rows.append(
                f"| {hindsight['part_id']} | 回看件／单章不计分 | {md_cell(hindsight['claim'])} | "
                f"沿用 v1.1，未改写 | — |"
            )

    rows.extend(["", "## v1.1 → v1.2 逐条映射", "", "| 旧金标件 | 旧当章句 | 处置 | 语义点 → 候选去向／状态 |", "|---|---|---|---|"])
    for mapping_row in mapping["rows"]:
        point_texts = []
        for point_row in mapping_row["semantic_point_mappings"]:
            destinations = "、".join(destination["part_id"] for destination in point_row["destinations"])
            point_texts.append(
                f"{point_row['semantic_point_id']}→{destinations}（{point_row['local_text_review_status']}"
                f"{'；别名不重复计分' if point_row['alias_non_scoring'] else ''}）"
            )
        rows.append(
            f"| {mapping_row['old_item_id']} | {md_cell(mapping_row['old_on_chapter_claim'])} | "
            f"{md_cell(mapping_row['decision'])} | {md_cell('；'.join(point_texts))} |"
        )

    rows.extend(["", "## 待 CZ 处置的三处", ""])
    for flag in REVIEW_FLAGS:
        rows.append(f"- **{flag['kind']} {flag['flag_id']}**：{flag['reason']} {flag['preservation_note']}")

    rows.extend(
        [
            "",
            "## 新旧尺四轮并排",
            "",
            "| 轮次 | 旧 v1.1 严格 | 旧 v1.1 语义召回 | v1.2候选原子严格 | v1.2有效语义召回 | 看见但锚无效 | 旧14底件：完整／已观察／待审 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for round_row in scores["rounds"]:
        old = round_row["old_v1_1"]
        atomic = round_row["v1_2_candidate_atomic"]
        rollup = round_row["v1_2_candidate_old_item_diagnostic"]
        rows.append(
            f"| {round_row['round_id']} | {old['strict_hit']}/{old['total']} | {old['semantic_recalled']}/{old['total']} | "
            f"{atomic['strict_hit']}/{atomic['total']} | {atomic['semantic_recalled']}/{atomic['total']} | "
            f"{atomic['coverage_only_invalid_support']} | {rollup['complete']}/{rollup['total']}／"
            f"{rollup['observed']}/{rollup['total']}／{rollup['pending_evidence_review']} |"
        )
    rows.extend(
        [
            "",
            "读法：候选成绩分母是23，不是24或26，不能和旧14条百分比直接翻案；旧成绩不追改。新尺把复合条拆开，还把正式锚不支撑的表面命中剔出有效召回，所以分数下降不等于模型输出再次变差。",
            "",
            "Z70 的五靶章 FAIL 与 Z71 的补全层硬停均从原 report_manifest.json 回读并原样保留；第3章换尺观察不能替它们翻案。",
        ]
    )

    for round_row in scores["rounds"]:
        rows.extend(
            [
                "",
                f"### {round_row['round_id']} 的 23 条人工重判",
                "",
                "| 候选部件 | 判词 | 计入有效召回 | 对应事件 | 理由 |",
                "|---|---|---:|---|---|",
            ]
        )
        for score_row in round_row["rows"]:
            rows.append(
                f"| {score_row['part_id']} | {score_row['verdict']} | "
                f"{'是' if score_row['counts_toward_effective_semantic_recall'] else '否'} | "
                f"{md_cell('、'.join(score_row['candidate_event_ids']) or '—')} | {md_cell(score_row['semantic_review_note'])} |"
            )

    rows.extend(
        [
            "",
            "## 机械验收与边界",
            "",
            f"- 映射：旧14条已映射 {mapping['mapped_old_base_item_total']}/14；孤儿旧条 0；声明语义点编号孤儿 0。三点仍待拍，所以没有宣称语义等价全部验证通过。",
            f"- 候选锚回读：{mapping['anchor_validation']['anchor_occurrence_total']} 个锚次全部能在冻结目录与第3章正文命中；‘锚存在’不等于证据充分，GOLD-C0003-10-N03 已另列证据不足。",
            "- 机械生成在两个隔离临时目录连续两次字节一致；全套测试结果见机械回执。",
            f"- 正式测试集改前 {TEST_VALIDATION['before_change']['passed']} 条全绿；改后 {TEST_VALIDATION['after_change']['passed']} 条＋{TEST_VALIDATION['after_change']['subtests_passed']} 个子测试全绿。命令：`{TEST_VALIDATION['command']}`。TEMP 按 CZ 已拍口径全忽略。",
            "- 金标 v1／v1.1、现役122条、默认链、分类规则、outbox 均未改；G101 未领取。",
            "- 本件只产候选与拍板底料，不改语义匹配自动化，不修 EV-C0005-15，不推进多本金标。",
            "",
            "来源：Codex",
        ]
    )
    return "\n".join(rows) + "\n"


def write_outputs(output_dir: Path) -> dict[str, Any]:
    input_shas = check_sha_inputs()
    anchor_map = catalog_rows()
    candidate, mapping = build_candidate(anchor_map)
    scores = build_scores(candidate)

    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = output_dir / "第3章结构层金标v1.2候选草案.json"
    mapping_path = output_dir / "v1.1到v1.2逐条映射与语义点账.json"
    scores_path = output_dir / "四轮新旧尺零调用重判.json"
    flags_path = output_dir / "剔除候选与证据风险.json"
    report_path = output_dir / "第72道停点回包｜第3章金标粒度v1.2候选_20260721.md"

    dump_json(candidate_path, candidate)
    dump_json(mapping_path, mapping)
    dump_json(scores_path, scores)
    dump_json(
        flags_path,
        {
            "schema_version": "z72-review-flags-v1",
            "status": "pending_cz_no_candidate_deleted",
            "model_api_calls": 0,
            "flags": REVIEW_FLAGS,
        },
    )
    report_path.write_text(build_markdown(candidate, scores, mapping), encoding="utf-8")

    generated = [candidate_path, mapping_path, scores_path, flags_path, report_path]
    receipt = {
        "schema_version": "z72-mechanical-validation-v1",
        "status": "pass_candidate_pending_cz",
        "model_api_calls": 0,
        "network_requests": 0,
        "token_usage": 0,
        "checks": [
            {"name": "frozen_input_sha", "status": "pass", "count": len(input_shas)},
            {"name": "old_14_items_mapped", "status": "pass", "count": mapping["mapped_old_base_item_total"]},
            {"name": "declared_point_ids_no_orphans", "status": "pass", "count": mapping["declared_destination_point_total"]},
            {"name": "semantic_equivalence_pending_cz", "status": "pending", "count": len(PENDING_SEMANTIC_POINT_IDS)},
            {"name": "candidate_anchor_readback", "status": "pass", "count": mapping["anchor_validation"]["anchor_occurrence_total"]},
            {"name": "four_round_samples_not_rerun", "status": "pass", "count": 4},
            {"name": "manual_semantic_verdicts_complete", "status": "pass", "count": sum(len(round_row["rows"]) for round_row in scores["rounds"])},
            {"name": "z70_z71_fail_hard_stop_gates_readback", "status": "pass", "count": len(RUN_GATE_PATHS)},
            {"name": "repository_test_suite_before_change", "status": "pass", "count": TEST_VALIDATION["before_change"]["passed"]},
            {"name": "repository_test_suite_after_change", "status": "pass", "count": TEST_VALIDATION["after_change"]["passed"]},
            {"name": "protected_files_unchanged", "status": "pass", "count": len(PROTECTED_PATHS)},
            {"name": "outbox_unchanged", "status": "pass", "count": EXPECTED_OUTBOX["files"]},
        ],
        "input_sha256": input_shas,
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "test_validation": TEST_VALIDATION,
        "outbox_fingerprint": EXPECTED_OUTBOX,
        "artifact_sha256": {str(path.relative_to(output_dir)): sha256(path) for path in generated},
    }
    dump_json(output_dir / "机械验收.json", receipt)
    generated.append(output_dir / "机械验收.json")
    manifest = {
        "schema_version": "z72-report-manifest-v1",
        "task": "第72道",
        "status": "candidate_stop_point",
        "producer": {"path": str(THIS_FILE.relative_to(ROOT)), "sha256": sha256(THIS_FILE)},
        "files": {str(path.relative_to(output_dir)): sha256(path) for path in generated},
        "candidate_boundary": "CZ 审过才可转正；v1.1 仍是正式判分尺。",
    }
    dump_json(output_dir / "report_manifest.json", manifest)
    return {
        "status": "pass_candidate_pending_cz",
        "output_dir": str(output_dir),
        "candidate_sha256": sha256(candidate_path),
        "mapping_sha256": sha256(mapping_path),
        "scores_sha256": sha256(scores_path),
        "receipt_sha256": sha256(output_dir / "机械验收.json"),
        "manifest_sha256": sha256(output_dir / "report_manifest.json"),
        "fingerprint": tree_fingerprint(output_dir),
    }


def repeat_validate_and_write(output_dir: Path) -> dict[str, Any]:
    """在两个隔离临时目录机械生成两次，再写正式目录并留一致性回执。"""

    with tempfile.TemporaryDirectory(prefix="z72-repeat-") as temp_name:
        temp_root = Path(temp_name)
        pass1 = write_outputs(temp_root / "pass1")
        pass2 = write_outputs(temp_root / "pass2")
        if pass1["fingerprint"] != pass2["fingerprint"]:
            raise AssertionError("第72道机械验收连续两次输出不一致")
        for relative_path in sorted(path.relative_to(temp_root / "pass1") for path in (temp_root / "pass1").rglob("*") if path.is_file()):
            if (temp_root / "pass1" / relative_path).read_bytes() != (temp_root / "pass2" / relative_path).read_bytes():
                raise AssertionError(f"第72道连续两次字节不一致：{relative_path}")

    final = write_outputs(output_dir)
    core_receipt = load_json(output_dir / "机械验收.json")
    core_receipt_sha = sha256(output_dir / "机械验收.json")
    for number in (1, 2):
        dump_json(
            output_dir / f"机械验收_pass{number}.json",
            {
                "schema_version": "z72-mechanical-validation-pass-v1",
                "pass": number,
                "status": core_receipt["status"],
                "core_receipt_sha256": core_receipt_sha,
                "isolated_artifact_fingerprint": pass1["fingerprint"],
            },
        )
    consistency_path = output_dir / "机械验收连续两次一致回执.json"
    dump_json(
        consistency_path,
        {
            "schema_version": "z72-repeat-validation-v1",
            "status": "pass_byte_identical",
            "pass1_fingerprint": pass1["fingerprint"],
            "pass2_fingerprint": pass2["fingerprint"],
            "same": True,
        },
    )

    manifest_path = output_dir / "report_manifest.json"
    manifest = load_json(manifest_path)
    manifest["files"]["机械验收_pass1.json"] = sha256(output_dir / "机械验收_pass1.json")
    manifest["files"]["机械验收_pass2.json"] = sha256(output_dir / "机械验收_pass2.json")
    manifest["files"]["机械验收连续两次一致回执.json"] = sha256(consistency_path)
    dump_json(manifest_path, manifest)
    final.update(
        {
            "repeat_validation": "pass_byte_identical",
            "repeat_fingerprint": pass1["fingerprint"],
            "consistency_receipt_sha256": sha256(consistency_path),
            "manifest_sha256": sha256(manifest_path),
            "fingerprint": tree_fingerprint(output_dir),
        }
    )
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = repeat_validate_and_write(args.output_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
