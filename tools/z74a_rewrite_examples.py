#!/usr/bin/env python3
"""第74道 A线：确定性生成通用正反例，并对六本正文做机械解耦核验。

这个工具不调用模型、不联网、不运行抽取，也不修改任何金标或现役配置。
原始 Z71 例只进入 provenance 文件；未来可喂给模型的文本只在三联例文件中。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_Z71_DIR = ROOT / "reports/Z71_z70语义补全旁路_20260721"
DEFAULT_Z73_DIR = ROOT / "reports/Z73_第3章金标v1.2定稿转正_20260721"
DEFAULT_OUT_DIR = ROOT / "reports/Z74A_正反例换皮候选_20260721"

DEFAULT_CORPORA = {
    "X01_诡秘之主": ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters",
    "知否": ROOT
    / "corpus-downloads/05_感情关系/庶女明兰传（知否？知否？应是绿肥红瘦）/庶女明兰传（知否？知否？应是绿肥红瘦）(关心则乱).txt",
    "大王饶命": ROOT
    / "corpus-downloads/01_单主角升级线/大王饶命/大王饶命(会说话的肘子).txt",
    "神秘复苏": ROOT
    / "corpus-downloads/01_单主角升级线/神秘复苏/神秘复苏(佛前献花).txt",
    "无限恐怖": ROOT
    / "corpus-downloads/01_单主角升级线/无限恐怖/无限恐怖(zhttty).txt",
    "凡人修仙传": ROOT
    / "corpus-downloads/07_历史世界规则/凡人修仙传/凡人修仙传(忘语).txt",
}

CORPUS_WINDOWS = {
    "X01_诡秘之主": {"source_kind": "frozen_chapter_directory", "start_chapter": 1, "end_chapter": 200},
    "知否": {"source_kind": "original_txt_heading_window", "start_chapter": 1, "end_chapter": 50},
    "大王饶命": {"source_kind": "original_txt_heading_window", "start_chapter": 1, "end_chapter": 50},
    "神秘复苏": {"source_kind": "original_txt_heading_window", "start_chapter": 1, "end_chapter": 50},
    "无限恐怖": {"source_kind": "original_txt_heading_window", "start_chapter": 1, "end_chapter": 50},
    "凡人修仙传": {"source_kind": "original_txt_heading_window", "start_chapter": 1, "end_chapter": 50},
}

PROTECTED_TERMS = {
    "X01_诡秘之主": {
        "titles": ["诡秘之主"],
        "characters": ["克莱恩", "周明瑞", "梅丽莎", "班森", "邓恩"],
        "places": ["廷根", "贝克兰德"],
        "concepts": ["塔罗会", "灰雾", "非凡者", "值夜者", "愚者"],
    },
    "知否": {
        "titles": ["庶女明兰传", "知否", "绿肥红瘦"],
        "characters": ["明兰", "顾廷烨", "盛老太太", "王若弗", "墨兰", "如兰", "长柏"],
        "places": ["宁远侯府", "宥阳", "汴京"],
        "concepts": ["嫡庶", "内宅"],
    },
    "大王饶命": {
        "titles": ["大王饶命"],
        "characters": ["吕树", "吕小鱼", "李弦一", "聂廷", "石学晋"],
        "places": ["洛城"],
        "concepts": ["道元班", "天罗地网", "负面情绪值", "洗髓果实", "尸狗", "山河印"],
    },
    "神秘复苏": {
        "titles": ["神秘复苏"],
        "characters": ["杨间", "王小明", "赵开明"],
        "places": ["大昌市", "鬼邮局"],
        "concepts": ["鬼眼", "鬼域", "驭鬼者", "灵异公交", "棺材钉"],
    },
    "无限恐怖": {
        "titles": ["无限恐怖"],
        "characters": ["郑吒", "楚轩", "詹岚", "张杰"],
        "places": ["主神空间"],
        "concepts": ["中洲队", "奖励点", "支线剧情", "基因锁", "轮回小队"],
    },
    "凡人修仙传": {
        "titles": ["凡人修仙传"],
        "characters": ["韩立", "南宫婉", "厉飞雨", "墨大夫"],
        "places": ["黄枫谷", "七玄门", "乱星海"],
        "concepts": ["掌天瓶", "噬金虫", "青竹蜂云剑", "灵根", "筑基", "结丹", "元婴"],
    },
}

# 这是六本最容易留下题材指纹的词，不等于自然语言中的永久禁词。
# 只对本批新三联例生效；不对原料证据倒查，也不外推成通用分类器。
PLOT_SIGNATURE_TERMS = [
    "穿越",
    "转生",
    "修仙",
    "修炼",
    "灵气",
    "功法",
    "宗门",
    "飞升",
    "仙人",
    "鬼",
    "灵异",
    "复活",
    "轮回",
    "主神",
    "基因锁",
    "超凡",
    "非凡",
    "异能",
    "超能力",
    "占卜",
    "仪式",
    "神灵",
    "序列",
    "侯府",
    "嫡庶",
    "内宅",
    "宅斗",
    "修士",
    "法宝",
    "丹药",
    "境界",
]

LONG_FRAGMENT_LENGTH = 18
FOUR_ROUND_FILE = "四轮v1.1旧尺与v1.2新尺双列基线参照.json"
CANDIDATE_STATUS = "silver_candidate_unreviewed_not_promoted"
CANDIDATE_STATUS_CN = "候选银标／未语义审定／不固化不升默认"
MODEL_FILE = "三联例候选.json"
SOURCE_FILE = "原料来源与病灶提炼.json"
DECOUPLING_FILE = "机械解耦验收.json"
STRUCTURE_REVIEW_FILE = "情节结构指纹复核.json"
STOP_REPORT_FILE = "第74道A线停点回包｜正反例换皮候选_20260721.md"
DOUBLE_RUN_FILE = "双跑一致回执.json"
MANIFEST_FILE = "report_manifest.json"
SHA_FILE = "SHA256SUMS"
CORE_FILES = [
    MODEL_FILE,
    SOURCE_FILE,
    DECOUPLING_FILE,
    STRUCTURE_REVIEW_FILE,
    STOP_REPORT_FILE,
]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, data: Any) -> None:
    path.write_bytes(canonical_json_bytes(data))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


_NON_WORD_RE = re.compile(r"[\W_]+", flags=re.UNICODE)


def normalize_text(text: str) -> str:
    """NFKC、忽略大小写，并移除标点、空白与下划线。"""

    folded = unicodedata.normalize("NFKC", text).casefold()
    return _NON_WORD_RE.sub("", folded)


def record(
    subject: str,
    action: str,
    result: str,
    necessary_qualifiers: list[str],
    text: str,
    anchor: str,
) -> dict[str, Any]:
    return {
        "subject": subject,
        "action": action,
        "result": result,
        "necessary_qualifiers": necessary_qualifiers,
        "text": text,
        "anchor": anchor,
    }


def wrong_variant(records: list[str], why_wrong: str) -> dict[str, Any]:
    return {
        "output_count": len(records),
        "records": [{"text": text} for text in records],
        "why_wrong": why_wrong,
    }


def triplet(
    group_id: str,
    pathology_type: str,
    subpattern: str,
    neutral_domain: str,
    source_scenario: list[str],
    too_large: dict[str, Any],
    too_small: dict[str, Any],
    just_right_records: list[dict[str, Any]],
    teaching_point: str,
) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "pathology_type": pathology_type,
        "subpattern": subpattern,
        "neutral_domain": neutral_domain,
        "source_scenario": source_scenario,
        "too_large": too_large,
        "too_small": too_small,
        "just_right": {
            "expected_record_count": len(just_right_records),
            "records": just_right_records,
            "teaching_point": teaching_point,
        },
    }


def _support(terms: list[str], anchor_indexes: list[int]) -> dict[str, Any]:
    return {"terms": terms, "anchor_indexes": anchor_indexes}


def _anchor_spec(
    anchors: list[str],
    subject: dict[str, Any],
    action: dict[str, Any],
    result: dict[str, Any],
    qualifiers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "anchors": anchors,
        "anchor_support": {
            "subject": subject,
            "action": action,
            "result": result,
            "necessary_qualifiers": [
                {"qualifier_index": index, **item} for index, item in enumerate(qualifiers)
            ],
        },
    }


# 每条刚好版都显式列出短引与字段支撑词。短引必须是 source_scenario 的逐字子串；
# 支撑词既要出现在对应字段里，也要出现在所指短引里，避免“有锚但锚不托结论”。
ANCHOR_SPECS: dict[str, list[dict[str, Any]]] = {
    "LARGE-01": [
        _anchor_spec(
            ["维护员发现冷藏柜温度报警。", "现有记录没有说明两件事互为因果。"],
            _support(["维护员"], [0]),
            _support(["冷藏柜", "温度报警"], [0]),
            _support(["冷藏柜", "温度报警"], [0]),
            [_support(["没有说明", "互为因果"], [1])],
        ),
        _anchor_spec(
            ["工具间的门禁记录显示门未关严。", "现有记录没有说明两件事互为因果。"],
            _support(["门禁记录"], [0]),
            _support(["工具间", "门未关严"], [0]),
            _support(["工具间", "门未关严"], [0]),
            [_support(["没有说明", "互为因果"], [1])],
        ),
    ],
    "LARGE-02": [
        _anchor_spec(
            ["调度员把首班车时间改为七点四十分。"],
            _support(["调度员"], [0]),
            _support(["首班车", "改为七点四十分"], [0]),
            _support(["首班车", "七点四十分"], [0]),
            [_support(["首班车"], [0])],
        ),
        _anchor_spec(
            ["司机收到新表后改从北侧出口发车。"],
            _support(["司机"], [0]),
            _support(["北侧出口", "发车"], [0]),
            _support(["北侧出口", "发车"], [0]),
            [_support(["收到新表后"], [0])],
        ),
    ],
    "LARGE-03": [
        _anchor_spec(
            ["采购员看到报价上涨，决定暂缓下单。"],
            _support(["采购员"], [0]),
            _support(["报价上涨", "决定暂缓下单"], [0]),
            _support(["决定暂缓下单"], [0]),
            [_support(["看到报价上涨"], [0])],
        ),
        _anchor_spec(
            ["随后，采购员去会议室汇报价格变化。"],
            _support(["采购员"], [0]),
            _support(["去会议室", "汇报价格变化"], [0]),
            _support(["采购员", "去会议室"], [0]),
            [_support(["随后"], [0])],
        ),
    ],
    "LARGE-04": [
        _anchor_spec(
            ["检验员确认样品封条完整。"],
            _support(["检验员"], [0]),
            _support(["确认", "样品封条"], [0]),
            _support(["封条完整"], [0]),
            [_support(["确认", "封条完整"], [0])],
        ),
        _anchor_spec(
            ["规程写明：运输温度超过八度时", "运输温度超过八度时，样品应停用"],
            _support(["规程"], [0]),
            _support(["温度超过八度", "样品应停用"], [1]),
            _support(["样品", "停用"], [1]),
            [_support(["运输温度超过八度时"], [0, 1])],
        ),
        _anchor_spec(
            ["本页没有运输温度超过八度的记录。"],
            _support(["本页"], [0]),
            _support(["运输温度", "记录"], [0]),
            _support(["没有", "超过八度", "记录"], [0]),
            [_support(["本页", "没有", "记录"], [0])],
        ),
    ],
    "SMALL-01": [
        _anchor_spec(
            ["技师取下旧滤芯，装入新滤芯并启动设备。", "设备指示灯转为绿色。"],
            _support(["技师"], [0]),
            _support(["取下旧滤芯", "装入新滤芯", "启动设备"], [0]),
            _support(["指示灯", "转为绿色"], [1]),
            [_support(["取下旧滤芯", "装入新滤芯"], [0])],
        ),
        _anchor_spec(
            ["同一时段，保洁员擦拭隔壁工位。"],
            _support(["保洁员"], [0]),
            _support(["擦拭", "隔壁工位"], [0]),
            _support(["隔壁工位", "擦拭"], [0]),
            [_support(["同一时段"], [0])],
        ),
    ],
    "SMALL-02": [
        _anchor_spec(
            ["备份校验通过后，管理员把服务切到备用节点", "并在控制台确认切换成功。"],
            _support(["管理员"], [0]),
            _support(["服务", "切到备用节点", "控制台"], [0, 1]),
            _support(["确认切换成功"], [1]),
            [_support(["备份校验通过后"], [0])],
        ),
        _anchor_spec(
            ["同一时段，值班同事把工单编号写到白板上。"],
            _support(["值班同事"], [0]),
            _support(["工单编号", "写到白板上"], [0]),
            _support(["白板上", "工单编号"], [0]),
            [_support(["同一时段"], [0])],
        ),
    ],
    "SMALL-03": [
        _anchor_spec(
            ["班长通知甲组：明早先清点器材", "再把差额填表交到前台。"],
            _support(["班长"], [0]),
            _support(["清点器材", "差额填表"], [0, 1]),
            _support(["差额", "交到前台"], [1]),
            [
                _support(["明早"], [0]),
                _support(["先清点器材", "再把差额填表交到前台"], [0, 1]),
            ],
        ),
        _anchor_spec(
            ["甲组长随后回复已收到通知。"],
            _support(["甲组长"], [0]),
            _support(["回复", "收到通知"], [0]),
            _support(["通知", "收到"], [0]),
            [_support(["随后"], [0])],
        ),
    ],
    "SMALL-04": [
        _anchor_spec(
            ["每逢闭店前，值班员都会核对收银箱", "并把差额写入交接簿。"],
            _support(["值班员"], [0]),
            _support(["核对收银箱", "差额", "写入交接簿"], [0, 1]),
            _support(["差额", "写入交接簿"], [1]),
            [_support(["每逢闭店前"], [0]), _support(["都会"], [0])],
        ),
        _anchor_spec(
            ["闭店后，保安锁上后门。"],
            _support(["保安"], [0]),
            _support(["锁上后门"], [0]),
            _support(["后门", "锁上"], [0]),
            [_support(["闭店后"], [0])],
        ),
    ],
    "MISS-01": [
        _anchor_spec(
            ["分析员发现两份计数不一致。", "她怀疑第二份记录漏了一页，但尚未确认。"],
            _support(["分析员"], [0]),
            _support(["怀疑", "漏了一页"], [1]),
            _support(["漏了一页", "尚未确认"], [1]),
            [_support(["怀疑"], [1]), _support(["尚未确认"], [1])],
        ),
    ],
    "MISS-02": [
        _anchor_spec(
            ["管理员计划周五更换全部旧标签。", "当前仍是周三，全部标签尚未更换。"],
            _support(["管理员"], [0]),
            _support(["计划", "更换全部旧标签"], [0]),
            _support(["全部标签", "尚未更换"], [1]),
            [_support(["周五"], [0]), _support(["当前仍是周三"], [1])],
        ),
    ],
    "MISS-03": [
        _anchor_spec(
            ["质检员抽查十箱货物。", "其中两箱的标签字迹模糊。"],
            _support(["质检员"], [0]),
            _support(["抽查十箱货物"], [0]),
            _support(["两箱", "标签字迹模糊"], [1]),
            [_support(["十箱"], [0]), _support(["其中两箱"], [1])],
        ),
    ],
    "MISS-04": [
        _anchor_spec(
            ["会议室只在下午开放。", "组织者因此把培训改到十五点。"],
            _support(["组织者"], [1]),
            _support(["培训", "改到十五点"], [1]),
            _support(["培训", "十五点"], [1]),
            [_support(["会议室", "只在下午开放"], [0])],
        ),
    ],
    "ANCHOR-01": [
        _anchor_spec(
            ["配送员把三箱样品送到接待台。"],
            _support(["配送员"], [0]),
            _support(["三箱样品", "送到接待台"], [0]),
            _support(["样品", "送到接待台"], [0]),
            [_support(["三箱"], [0])],
        ),
        _anchor_spec(
            ["接待员核对封条后完成签收。"],
            _support(["接待员"], [0]),
            _support(["核对封条"], [0]),
            _support(["完成签收"], [0]),
            [_support(["核对封条后"], [0])],
        ),
    ],
    "ANCHOR-02": [
        _anchor_spec(
            ["操作员在控制台按下复位键。", "指示灯随后由红色转为绿色。"],
            _support(["操作员"], [0]),
            _support(["按下复位键"], [0]),
            _support(["指示灯", "由红色转为绿色"], [1]),
            [_support(["随后"], [1])],
        ),
    ],
    "ANCHOR-03": [
        _anchor_spec(
            ["文员把退货单夹进蓝色文件夹。"],
            _support(["文员"], [0]),
            _support(["退货单", "夹进", "文件夹"], [0]),
            _support(["退货单", "蓝色文件夹"], [0]),
            [_support(["蓝色"], [0])],
        ),
        _anchor_spec(
            ["旁边的助理随后关上窗户。"],
            _support(["助理"], [0]),
            _support(["关上窗户"], [0]),
            _support(["窗户", "关上"], [0]),
            [_support(["随后"], [0])],
        ),
    ],
    "ANCHOR-04": [
        _anchor_spec(
            ["主管说：下午先清点三号货架", "核完后把缺件数发给我。"],
            _support(["主管"], [0]),
            _support(["清点三号货架", "缺件数"], [0, 1]),
            _support(["缺件数", "发给"], [1]),
            [_support(["下午"], [0]), _support(["核完后"], [1])],
        ),
        _anchor_spec(
            ["主管接着说：如果差额超过三件", "暂停发货并通知值班经理。"],
            _support(["主管"], [0]),
            _support(["暂停发货", "通知值班经理"], [1]),
            _support(["暂停发货", "通知值班经理"], [1]),
            [_support(["如果差额超过三件"], [0])],
        ),
    ],
}


# 锚不托病的错误版不仅说明“错”，还带着故意不足的短引；校验器会证明：
# 短引能托住一部分词，却托不住同一主张里的其余词。
WRONG_ANCHOR_SPECS = {
    "ANCHOR-01": {
        "variant": "too_large",
        "record_index": 0,
        "anchors": ["配送员把三箱样品送到接待台。"],
        "claim_components": {
            "subject": "配送员与接待员",
            "action": "把三箱样品送到接待台并核对封条",
            "result": "样品送到接待台并完成签收",
        },
        "supported_claim_terms": {
            "subject": ["配送员"],
            "action": ["三箱样品", "送到接待台"],
            "result": ["送到接待台"],
        },
        "unsupported_claim_terms": {
            "subject": ["接待员"],
            "action": ["核对封条"],
            "result": ["完成签收"],
        },
    },
    "ANCHOR-02": {
        "variant": "too_small",
        "record_index": 0,
        "anchors": ["操作员在控制台按下复位键。"],
        "claim_components": {
            "subject": "操作员",
            "action": "按下复位键",
            "result": "指示灯由红色转为绿色",
        },
        "supported_claim_terms": {"subject": ["操作员"], "action": ["按下复位键"]},
        "unsupported_claim_terms": {"result": ["指示灯", "由红色转为绿色"]},
    },
    "ANCHOR-03": {
        "variant": "too_large",
        "record_index": 0,
        "anchors": ["文员把退货单夹进蓝色文件夹。"],
        "claim_components": {
            "subject": "文员与助理",
            "action": "把退货单夹进蓝色文件夹并关上窗户",
            "result": "退货单夹进文件夹且助理关上窗户",
        },
        "supported_claim_terms": {
            "subject": ["文员"],
            "action": ["退货单", "夹进", "蓝色文件夹"],
            "result": ["退货单", "夹进", "文件夹"],
        },
        "unsupported_claim_terms": {
            "subject": ["助理"],
            "action": ["关上窗户"],
            "result": ["助理", "关上窗户"],
        },
    },
    "ANCHOR-04": {
        "variant": "too_small",
        "record_index": 0,
        "anchors": ["主管说：下午先清点三号货架"],
        "claim_components": {
            "subject": "主管",
            "action": "清点三号货架并在差额超过三件时暂停发货",
            "result": "把缺件数发给我并通知值班经理",
        },
        "supported_claim_terms": {"subject": ["主管"], "action": ["清点三号货架"]},
        "unsupported_claim_terms": {
            "action": ["差额超过三件", "暂停发货"],
            "result": ["把缺件数发给我", "通知值班经理"],
        },
    },
}


SMALL_GRANULARITY_ACTION_TERMS = {
    "SMALL-01": ["取下旧滤芯", "装入新滤芯", "启动设备", "指示灯转为绿色", "擦拭隔壁工位"],
    "SMALL-02": ["备份校验通过", "把服务切到备用节点", "在控制台确认切换成功", "把工单编号写到白板上"],
    "SMALL-03": ["通知甲组", "清点器材", "把差额填表交到前台", "回复已收到通知"],
    "SMALL-04": ["核对收银箱", "把差额写入交接簿", "锁上后门"],
}


def _attach_anchor_specs(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for group in groups:
        group_id = group["group_id"]
        records = group["just_right"]["records"]
        specs = ANCHOR_SPECS.get(group_id, [])
        if len(specs) != len(records):
            raise ValueError(f"{group_id} 的短引规格应有{len(records)}条，实际{len(specs)}条")
        for item, spec in zip(records, specs, strict=True):
            item.pop("anchor", None)
            item.update(spec)

        wrong_spec = WRONG_ANCHOR_SPECS.get(group_id)
        if wrong_spec:
            variant = group[wrong_spec["variant"]]
            record_item = variant["records"][wrong_spec["record_index"]]
            record_item["wrong_anchor_case"] = {
                key: value
                for key, value in wrong_spec.items()
                if key not in {"variant", "record_index"}
            }
        if group_id in SMALL_GRANULARITY_ACTION_TERMS:
            terms = SMALL_GRANULARITY_ACTION_TERMS[group_id]
            group["too_large"]["granularity_only_check"] = {
                "source_action_terms": terms,
                "source_action_term_total": len(terms),
                "invented_action_count": 0,
            }
    return groups


def build_triplets() -> list[dict[str, Any]]:
    """固定的16组三联例；不含随机分支。"""

    groups = [
        triplet(
            "LARGE-01",
            "太大病",
            "无证据关联的两个异常被并成一个原因链",
            "公共设施维护",
            [
                "维护员发现冷藏柜温度报警。",
                "同一时段，工具间的门禁记录显示门未关严。",
                "现有记录没有说明两件事互为因果。",
            ],
            wrong_variant(
                ["维护员发现门未关严导致冷藏柜温度报警。"],
                "把两个可分别判真的异常写成一个未经支持的因果链。",
            ),
            wrong_variant(
                ["维护员发现冷藏柜。", "冷藏柜报警。", "工具间有门。", "门没有关严。"],
                "把两个完整异常又切成物件和状态碎片。",
            ),
            [
                record(
                    "维护员",
                    "发现冷藏柜温度报警",
                    "冷藏柜温度报警",
                    ["现有记录没有说明两件事互为因果"],
                    "维护员发现冷藏柜温度报警。",
                    "维护员发现冷藏柜温度报警",
                ),
                record(
                    "门禁记录",
                    "显示工具间的门未关严",
                    "工具间的门未关严",
                    ["现有记录没有说明两件事互为因果"],
                    "门禁记录显示工具间的门未关严。",
                    "工具间的门禁记录显示门未关严",
                ),
            ],
            "没有原文关系词时，两个异常分成两条，不能自行补因果。",
        ),
        triplet(
            "LARGE-02",
            "太大病",
            "跨主体动作被塞进同一条",
            "车辆调度",
            [
                "调度员把首班车时间改为七点四十分。",
                "司机收到新表后改从北侧出口发车。",
            ],
            wrong_variant(
                ["调度员修改首班车时间并从北侧出口发车。"],
                "把司机的动作错挂给调度员。",
            ),
            wrong_variant(
                ["调度员修改时间。", "时间变成七点四十分。", "司机收到表。", "司机更换出口。"],
                "主体虽分开了，但每个完整动作又被拆成没有独立价值的碎片。",
            ),
            [
                record(
                    "调度员",
                    "把首班车时间改为七点四十分",
                    "首班车时间变为七点四十分",
                    ["调整对象是首班车"],
                    "调度员把首班车时间改为七点四十分。",
                    "调度员把首班车时间改为七点四十分",
                ),
                record(
                    "司机",
                    "收到新表后改从北侧出口发车",
                    "车辆改从北侧出口发车",
                    ["收到新表后"],
                    "司机收到新表后改从北侧出口发车。",
                    "司机收到新表后改从北侧出口发车",
                ),
            ],
            "主体变化就是强拆分信号；条件可以保留在对应主体那一条。",
        ),
        triplet(
            "LARGE-03",
            "太大病",
            "相邻心理决定被吞进后续位移动作",
            "采购管理",
            [
                "采购员看到报价上涨，决定暂缓下单。",
                "随后，采购员去会议室汇报价格变化。",
            ],
            wrong_variant(
                ["采购员看到报价上涨后决定暂缓下单，随后去会议室汇报价格变化。"],
                "把两个可独立判真的动作压成一条；虽不虚构完成态，仍无法分别核验决定和位移。",
            ),
            wrong_variant(
                ["采购员看到报价。", "报价上涨。", "采购员作出决定。", "采购员前往会议室。"],
                "把心理决定和位移动作拆成更小的残句，反而丢掉各自动作结果。",
            ),
            [
                record(
                    "采购员",
                    "看到报价上涨后决定暂缓下单",
                    "决定暂缓下单",
                    ["看到报价上涨"],
                    "采购员看到报价上涨，决定暂缓下单。",
                    "看到报价上涨，决定暂缓下单",
                ),
                record(
                    "采购员",
                    "去会议室汇报价格变化",
                    "采购员去会议室",
                    ["随后"],
                    "采购员随后去会议室汇报价格变化。",
                    "随后去会议室汇报价格变化",
                ),
            ],
            "同一主体也可能连续做两个可独立判真的动作，心理动作不能挂成位移修饰语。",
        ),
        triplet(
            "LARGE-04",
            "太大病",
            "当前状态与条件风险混写",
            "样品管理",
            [
                "检验员确认样品封条完整。",
                "规程写明：运输温度超过八度时，样品应停用。",
                "本页没有运输温度超过八度的记录。",
            ],
            wrong_variant(
                ["检验员确认样品封条完整，因此样品不存在停用风险。"],
                "用封条状态替代温度条件，还把未触发的风险写成已排除。",
            ),
            wrong_variant(
                ["检验员查看样品。", "封条完整。", "规程提到温度。", "规程提到停用。"],
                "状态和规则都被拆成不能独立说明结论的词组。",
            ),
            [
                record(
                    "检验员",
                    "确认样品封条",
                    "确认封条完整",
                    ["只确认封条完整"],
                    "检验员确认样品封条完整。",
                    "确认样品封条完整",
                ),
                record(
                    "规程",
                    "写明运输温度超过八度时样品应停用",
                    "样品应停用",
                    ["运输温度超过八度时"],
                    "运输规程写明，温度超过八度时样品应停用。",
                    "运输温度超过八度时，样品应停用",
                ),
                record(
                    "本页",
                    "没有记录运输温度超过八度",
                    "没有发现超过八度的记录",
                    ["本页没有超过八度的记录"],
                    "本页没有运输温度超过八度的记录。",
                    "本页没有运输温度超过八度的记录",
                ),
            ],
            "已发生状态和未触发规则分别记录，不能互相代替。",
        ),
        triplet(
            "SMALL-01",
            "太小病",
            "同主体同对象的连续步骤共同形成完成态",
            "设备保养",
            [
                "技师取下旧滤芯，装入新滤芯并启动设备。",
                "设备指示灯转为绿色。",
                "同一时段，保洁员擦拭隔壁工位。",
            ],
            wrong_variant(
                ["技师取下旧滤芯、装入新滤芯并启动设备，设备指示灯转为绿色；同一时段，保洁员擦拭隔壁工位。"],
                "把两个主体的独立工作并成一条，内容没有新增，只改变了粒度。",
            ),
            wrong_variant(
                [
                    "技师取下旧滤芯。",
                    "技师装入新滤芯。",
                    "技师启动设备。",
                    "指示灯变绿。",
                    "保洁员擦拭隔壁工位。",
                ],
                "前四个连续步骤共同证明一次更换完成，不应拆成四条；保洁动作本来就独立。",
            ),
            [
                record(
                    "技师",
                    "取下旧滤芯、装入新滤芯并启动设备",
                    "设备指示灯转为绿色",
                    ["取下旧滤芯后装入新滤芯"],
                    "技师更换滤芯并启动设备，指示灯转绿。",
                    "装入新滤芯并启动设备，指示灯转为绿色",
                ),
                record(
                    "保洁员",
                    "擦拭隔壁工位",
                    "隔壁工位被擦拭",
                    ["发生在同一时段"],
                    "同一时段，保洁员擦拭隔壁工位。",
                    "同一时段，保洁员擦拭隔壁工位",
                ),
            ],
            "同主体、同对象、连续步骤只通向一个完成态时保留为一条。",
        ),
        triplet(
            "SMALL-02",
            "太小病",
            "条件、操作与直接结果属于同一完成链",
            "系统运维",
            [
                "备份校验通过后，管理员把服务切到备用节点，并在控制台确认切换成功。",
                "同一时段，值班同事把工单编号写到白板上。",
            ],
            wrong_variant(
                ["备份校验通过后，管理员把服务切到备用节点并在控制台确认切换成功；同一时段，值班同事把工单编号写到白板上。"],
                "把不同主体、不同对象的两件事并成一条，内容没有新增。",
            ),
            wrong_variant(
                [
                    "备份校验通过。",
                    "管理员切换服务。",
                    "管理员查看控制台。",
                    "控制台确认切换成功。",
                    "值班同事把工单编号写到白板上。",
                ],
                "前四条把同一主体、同一服务的条件、操作与确认结果过拆；白板记录保持独立。",
            ),
            [
                record(
                    "管理员",
                    "把服务切到备用节点并在控制台确认",
                    "确认切换成功",
                    ["备份校验通过后"],
                    "备份校验通过后，管理员把服务切到备用节点，并在控制台确认切换成功。",
                    "备份校验通过后，管理员切换到备用服务",
                ),
                record(
                    "值班同事",
                    "把工单编号写到白板上",
                    "白板上出现工单编号",
                    ["发生在同一时段"],
                    "同一时段，值班同事把工单编号写到白板上。",
                    "同一时段，值班同事把工单编号写到白板上",
                ),
            ],
            "必要前提和紧随操作出现的直接结果要留在同一条。",
        ),
        triplet(
            "SMALL-03",
            "太小病",
            "同一言语中的一项完整安排被碎切",
            "器材盘点",
            [
                "班长通知甲组：明早先清点器材，再把差额填表交到前台。",
                "甲组长随后回复已收到通知。",
            ],
            wrong_variant(
                ["班长通知甲组明早先清点器材、再把差额填表交到前台；甲组长随后回复已收到通知。"],
                "把发话者的任务安排和受领者的回复并成一条，内容没有新增。",
            ),
            wrong_variant(
                [
                    "班长说话。",
                    "甲组明早盘点。",
                    "差额要填表。",
                    "表交到前台。",
                    "甲组长回复已收到通知。",
                ],
                "前四条把同一说话主体的一项任务安排切碎；回复本来就独立。",
            ),
            [
                record(
                    "班长",
                    "安排甲组清点器材并把差额填表",
                    "差额填表后交到前台",
                    ["明早", "先清点器材，再把差额填表交到前台"],
                    "班长安排甲组明早清点器材，再把差额填表交到前台。",
                    "明早先清点器材，再把差额填表交到前台",
                ),
                record(
                    "甲组长",
                    "回复已收到通知",
                    "通知被确认收到",
                    ["随后回复"],
                    "甲组长随后回复已收到通知。",
                    "甲组长随后回复已收到通知",
                ),
            ],
            "同一发话者、同一受领者和同一任务结果可以构成一条完整安排。",
        ),
        triplet(
            "SMALL-04",
            "太小病",
            "习惯行动的时间限定被单独切走",
            "门店交接",
            [
                "每逢闭店前，值班员都会核对收银箱，并把差额写入交接簿。",
                "闭店后，保安锁上后门。",
            ],
            wrong_variant(
                ["每逢闭店前值班员核对收银箱并把差额写入交接簿；闭店后保安锁上后门。"],
                "把两个主体的交接动作并成一条，内容没有新增。",
            ),
            wrong_variant(
                [
                    "门店将要闭店。",
                    "值班员核对收银箱。",
                    "值班员写交接簿。",
                    "保安锁上后门。",
                ],
                "前三条把重复时间条件与同一交接动作拆散；保安动作本来就独立。",
            ),
            [
                record(
                    "值班员",
                    "核对收银箱并把差额写入交接簿",
                    "差额写入交接簿",
                    ["每逢闭店前", "都会执行"],
                    "每逢闭店前，值班员都会核对收银箱，并把差额写入交接簿。",
                    "每逢闭店前，值班员都会核对收银箱",
                ),
                record(
                    "保安",
                    "锁上后门",
                    "后门被锁上",
                    ["闭店后"],
                    "闭店后，保安锁上后门。",
                    "闭店后，保安锁上后门",
                ),
            ],
            "习惯频率和时间限定是动作成立范围，不应另立空洞事件。",
        ),
        triplet(
            "MISS-01",
            "漏抽病",
            "不确定认知被当成无事实而漏掉",
            "数据核对",
            [
                "分析员发现两份计数不一致。",
                "她怀疑第二份记录漏了一页，但尚未确认。",
            ],
            wrong_variant(
                ["分析员确认第二份记录漏了一页，导致两份计数不一致。"],
                "把怀疑升级成已确认事实，还补出了确定因果。",
            ),
            wrong_variant([], "因为结论不确定而整条漏掉。"),
            [
                record(
                    "分析员",
                    "怀疑第二份记录漏了一页",
                    "漏了一页的判断尚未确认",
                    ["只是怀疑", "尚未确认"],
                    "分析员怀疑第二份记录漏了一页，但尚未确认。",
                    "怀疑第二份记录漏了一页，但尚未确认",
                )
            ],
            "不确定认知也是已发生的心理事实，但必须保留不确定强度。",
        ),
        triplet(
            "MISS-02",
            "漏抽病",
            "意愿或计划因尚未执行而漏掉",
            "档案整理",
            [
                "管理员计划周五更换全部旧标签。",
                "当前仍是周三，全部标签尚未更换。",
            ],
            wrong_variant(
                ["管理员周五更换了全部旧标签，整理工作已经完成。"],
                "把计划写成已执行，并虚构完成结果。",
            ),
            wrong_variant([], "因为动作尚未执行而忽略明确计划。"),
            [
                record(
                    "管理员",
                    "计划更换全部旧标签",
                    "全部标签尚未更换",
                    ["周五", "当前仍是周三"],
                    "管理员计划周五更换全部旧标签，目前尚未执行。",
                    "计划周五更换全部旧标签",
                )
            ],
            "计划可以记录，但结果必须写成待执行，不能冒充完成。",
        ),
        triplet(
            "MISS-03",
            "漏抽病",
            "事实强度被缩成模糊概括",
            "包装抽查",
            [
                "质检员抽查十箱货物。",
                "其中两箱的标签字迹模糊。",
            ],
            wrong_variant(
                ["质检员确认整批货物的标签都不合格。"],
                "把十箱中的两箱扩大成整批全部。",
            ),
            wrong_variant(
                ["质检员发现标签有点问题。"],
                "虽然没有完全漏掉，但样本数和问题数量都丢了，事实强度无法复核。",
            ),
            [
                record(
                    "质检员",
                    "抽查十箱货物",
                    "发现两箱标签字迹模糊",
                    ["十箱", "其中两箱"],
                    "质检员抽查十箱货物，发现其中两箱标签字迹模糊。",
                    "抽查十箱货物，其中两箱的标签字迹模糊",
                )
            ],
            "数量和抽查范围决定事实强度，不能为了短而抹掉。",
        ),
        triplet(
            "MISS-04",
            "漏抽病",
            "背景限制没有留在动作里",
            "场地排期",
            [
                "会议室只在下午开放。",
                "组织者因此把培训改到十五点。",
            ],
            wrong_variant(
                ["组织者因为所有场地上午都关闭，把整周培训统一改到十五点。"],
                "把单个会议室和单次培训扩大成全部场地与整周安排。",
            ),
            wrong_variant(
                ["组织者把培训改到十五点。"],
                "漏掉了改期成立的必要场地限制。",
            ),
            [
                record(
                    "组织者",
                    "把培训改到十五点",
                    "培训改到十五点",
                    ["会议室只在下午开放"],
                    "因会议室只在下午开放，组织者把培训改到十五点。",
                    "会议室只在下午开放，因此把培训改到十五点",
                )
            ],
            "直接约束动作选择的背景限制要保留，其他背景才可省略。",
        ),
        triplet(
            "ANCHOR-01",
            "锚不托病",
            "同一短引只支持复合句的前半",
            "样品配送",
            [
                "配送员把三箱样品送到接待台。",
                "接待员核对封条后完成签收。",
            ],
            wrong_variant(
                ["配送员把三箱样品送到接待台，接待员核对封条后完成签收。"],
                "复合主张里的两件事都来自场景，但所附短引只有送达句，不能托住接待员核对和签收。",
            ),
            wrong_variant(
                ["配送员送样品。", "接待员看封条。", "接待员签字。"],
                "把接待员同一核对签收过程切碎。",
            ),
            [
                record(
                    "配送员",
                    "把三箱样品送到接待台",
                    "样品送到接待台",
                    ["数量为三箱"],
                    "配送员把三箱样品送到接待台。",
                    "把三箱样品送到接待台",
                ),
                record(
                    "接待员",
                    "核对封条",
                    "完成签收",
                    ["核对封条后"],
                    "接待员核对封条后签收。",
                    "核对封条后签收",
                ),
            ],
            "每条的短引必须覆盖该条主体、动作和结果，不能借邻句补齐。",
        ),
        triplet(
            "ANCHOR-02",
            "锚不托病",
            "短引缺少完成结果",
            "控制台复位",
            [
                "操作员在控制台按下复位键。",
                "指示灯随后由红色转为绿色。",
            ],
            wrong_variant(
                ["操作员复位全部设备并消除了所有告警。"],
                "把单个操作结果扩大到全部设备和全部告警。",
            ),
            wrong_variant(
                ["操作员按下复位键，指示灯由红色转为绿色。"],
                "主张写了操作与结果，但所附短引只到操作，不能托住指示灯变化。",
            ),
            [
                record(
                    "操作员",
                    "按下复位键",
                    "指示灯由红色转为绿色",
                    ["随后"],
                    "操作员按下复位键，指示灯随后由红色转为绿色。",
                    "按下复位键，指示灯随后由红色转为绿色",
                )
            ],
            "若结果是完成态的一部分，短引必须同时托住操作和结果。",
        ),
        triplet(
            "ANCHOR-03",
            "锚不托病",
            "邻近动作被错挂到当前主体",
            "退货登记",
            [
                "文员把退货单夹进蓝色文件夹。",
                "旁边的助理随后关上窗户。",
            ],
            wrong_variant(
                ["文员把退货单夹进蓝色文件夹，旁边的助理随后关上窗户。"],
                "复合主张保持了两个原主体，但所附短引只有归档句，不能托住助理关窗。",
            ),
            wrong_variant(
                ["文员拿退货单。", "文件夹是蓝色。", "助理碰了窗户。"],
                "把两个独立动作拆成对象和颜色碎片。",
            ),
            [
                record(
                    "文员",
                    "把退货单夹进文件夹",
                    "退货单存入蓝色文件夹",
                    ["文件夹为蓝色"],
                    "文员把退货单夹进蓝色文件夹。",
                    "把退货单夹进蓝色文件夹",
                ),
                record(
                    "助理",
                    "关上窗户",
                    "窗户被关上",
                    ["随后"],
                    "助理随后关上窗户。",
                    "助理随后关上窗户",
                ),
            ],
            "相邻不等于同属；先核主体，再决定短引能托哪一条。",
        ),
        triplet(
            "ANCHOR-04",
            "锚不托病",
            "长指令只取前半，漏掉后半条件分支",
            "仓储发货",
            [
                "主管说：下午先清点三号货架，核完后把缺件数发给我。",
                "主管接着说：如果差额超过三件，暂停发货并通知值班经理。",
            ],
            wrong_variant(
                ["主管确认差额已经超过三件，并下令永久停止发货。"],
                "把条件分支写成已触发，还把暂停扩大成永久停止。",
            ),
            wrong_variant(
                ["主管说：下午先清点三号货架，核完后把缺件数发给我；如果差额超过三件，暂停发货并通知值班经理。"],
                "主张忠实合并两段原指令，但所附短引只到清点开头，不能托住上报和条件处置。",
            ),
            [
                record(
                    "主管",
                    "安排清点三号货架并发送缺件数",
                    "缺件数发给主管",
                    ["下午", "核完后"],
                    "主管安排下午清点三号货架，核完后上报缺件数。",
                    "下午先清点三号货架，核完后把缺件数发给我",
                ),
                record(
                    "主管",
                    "要求暂停发货并通知值班经理",
                    "暂停发货并通知值班经理",
                    ["如果差额超过三件"],
                    "若差额超过三件，主管要求暂停发货并通知值班经理。",
                    "如果差额超过三件，暂停发货并通知值班经理",
                ),
            ],
            "长句后半含独立条件处置时要另立一条，并让短引完整覆盖该分支。",
        ),
    ]
    return _attach_anchor_specs(groups)


def build_model_candidate() -> dict[str, Any]:
    groups = build_triplets()
    return {
        "schema_version": "z74a-rewrite-triplets-v1",
        "status": CANDIDATE_STATUS,
        "status_label": CANDIDATE_STATUS_CN,
        "identity": "第74道A线独立正反例换皮候选",
        "future_prompt_visibility": True,
        "provenance_is_excluded": True,
        "scope_note": "这里只含通用三联例；真实原料与六本文本路径不进入未来提示词。",
        "construction_contract": {
            "pathology_type_total": 4,
            "subpattern_per_type": 4,
            "triplet_group_total": 16,
            "variant_per_group": ["太大", "太小", "刚好"],
            "just_right_required_fields": ["主体", "动作", "结果", "必要限定", "短引"],
        },
        "groups": groups,
    }


def _index_by_event(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["event_id"]: row for row in rows if row.get("event_id")}


EXPECTED_Z71_LEDGER_COUNTS = {"fill_rows": 32, "gold_rows": 14, "current_rows": 34}
EXPECTED_FOUR_ROUND_IDS = ["B0_Z57", "Z68C", "Z70", "Z71"]
EXPECTED_FORMAL_PARTS_PER_ROUND = 23

FORMAL_PART_CATEGORY_IDS = {
    "uncertain_cognition": {
        "GOLD-C0003-09-N02",
        "GOLD-C0003-09-N03",
        "GOLD-C0003-09-N04",
        "GOLD-C0003-09-N05",
    },
    "intention_or_plan": {
        "GOLD-C0003-08-N01",
        "GOLD-C0003-11-N01",
        "GOLD-C0003-12-N02",
    },
    "background_or_limitation": {
        "GOLD-C0003-01-N01",
        "GOLD-C0003-03-N01",
        "GOLD-C0003-05-N01",
        "GOLD-C0003-06-N01",
        "GOLD-C0003-10-N02",
        "GOLD-C0003-12-N01",
        "GOLD-C0003-12-N03",
        "GOLD-C0003-13-N01",
        "GOLD-C0003-14-N01",
    },
}

# 每个子模式都落到可直接回读的源行，不用“某类问题”这种无法定位的概括。
GROUP_EVIDENCE_BLUEPRINT: dict[str, list[tuple[str, str]]] = {
    "LARGE-01": [
        ("z71_fill", "EV-C0003-11"),
        ("z71_fill", "EV-C0005-02"),
        ("z71_fill", "EV-C0005-18"),
    ],
    "LARGE-02": [("z71_fill", "EV-C0005-02"), ("z71_fill", "EV-C0013-08")],
    "LARGE-03": [("z71_fill", "EV-C0005-08"), ("z71_fill", "EV-C0013-08")],
    "LARGE-04": [("z71_current", "C-C0013-01"), ("z71_current", "D-C0013-02")],
    "SMALL-01": [("z71_fill", "EV-C0003-07"), ("z73_formal", "GOLD-C0003-05-N01")],
    "SMALL-02": [("z71_fill", "EV-C0004-08"), ("z73_formal", "GOLD-C0003-03-N01")],
    "SMALL-03": [("z71_fill", "EV-C0003-11"), ("z73_formal", "GOLD-C0003-06-N01")],
    "SMALL-04": [("z71_current", "B-C0019-02"), ("z73_formal", "GOLD-C0003-14-N01")],
    "MISS-01": [("z71_gold", "GOLD-C0003-09"), ("z73_formal", "GOLD-C0003-09-N02")],
    "MISS-02": [("z71_gold", "GOLD-C0003-08"), ("z73_formal", "GOLD-C0003-12-N02")],
    "MISS-03": [("z71_gold", "GOLD-C0003-01"), ("z73_formal", "GOLD-C0003-05-N01")],
    "MISS-04": [("z71_gold", "GOLD-C0003-13"), ("z73_formal", "GOLD-C0003-14-N01")],
    "ANCHOR-01": [("z73_formal", "GOLD-C0003-01-N01"), ("z73_formal", "GOLD-C0003-07-N01")],
    "ANCHOR-02": [("z73_formal", "GOLD-C0003-03-N01"), ("z73_formal", "GOLD-C0003-05-N01")],
    "ANCHOR-03": [("z71_fill", "EV-C0003-01"), ("z71_fill", "EV-C0004-14")],
    "ANCHOR-04": [("z73_formal", "GOLD-C0003-06-N01"), ("z73_formal", "GOLD-C0003-14-N01")],
}


def _ledger_rows(rows: list[dict[str, Any]], section: str) -> list[dict[str, Any]]:
    return [{"json_pointer": f"/{section}/{index}", **row} for index, row in enumerate(rows)]


def _formal_issue_tags(part_id: str, verdict: str) -> list[str]:
    tags = []
    if verdict == "coverage_only_invalid_support":
        tags.append("invalid_anchor")
    if verdict != "strict_hit":
        tags.append("not_strict_hit")
    for category, part_ids in FORMAL_PART_CATEGORY_IDS.items():
        if part_id in part_ids:
            tags.append(category)
    return tags


def _build_group_evidence(
    review: dict[str, Any],
    four_rounds: dict[str, Any],
    review_path: Path,
    four_round_path: Path,
) -> list[dict[str, Any]]:
    section_specs = {
        "z71_fill": ("fill_rows", "event_id"),
        "z71_gold": ("gold_rows", "gold_item_id"),
        "z71_current": ("current_rows", "record_id"),
    }
    z71_indexes: dict[str, dict[str, tuple[int, dict[str, Any]]]] = {}
    for source_kind, (section, id_field) in section_specs.items():
        z71_indexes[source_kind] = {
            row[id_field]: (index, row)
            for index, row in enumerate(review[section])
            if row.get(id_field)
        }

    formal_index: dict[str, list[tuple[int, int, str, dict[str, Any]]]] = {}
    for round_index, round_row in enumerate(four_rounds["rounds"]):
        for row_index, row in enumerate(round_row["formal_part_rows"]):
            formal_index.setdefault(row["formal_gold_part_id"], []).append(
                (round_index, row_index, round_row["round_id"], row)
            )

    subpatterns = {group["group_id"]: group["subpattern"] for group in build_triplets()}
    evidence_rows = []
    for group_id, requests in GROUP_EVIDENCE_BLUEPRINT.items():
        refs = []
        for source_kind, locator in requests:
            if source_kind == "z73_formal":
                matches = formal_index.get(locator, [])
                if len(matches) != len(EXPECTED_FOUR_ROUND_IDS):
                    raise ValueError(f"{group_id} 的四轮证据 {locator} 未完整定位")
                for round_index, row_index, round_id, row in matches:
                    refs.append(
                        {
                            "source": _relative_source(four_round_path),
                            "json_pointer": f"/rounds/{round_index}/formal_part_rows/{row_index}",
                            "locator": {"round_id": round_id, "formal_gold_part_id": locator},
                            "verdict": row.get("verdict"),
                            "review_note": row.get("semantic_review_note"),
                        }
                    )
                continue

            section, id_field = section_specs[source_kind]
            match = z71_indexes[source_kind].get(locator)
            if match is None:
                raise ValueError(f"{group_id} 的 Z71 证据 {locator} 未定位")
            row_index, row = match
            refs.append(
                {
                    "source": _relative_source(review_path),
                    "json_pointer": f"/{section}/{row_index}",
                    "locator": {id_field: locator},
                    "verdict": row.get("verdict"),
                    "review_note": row.get("note"),
                }
            )
        evidence_rows.append(
            {
                "group_id": group_id,
                "subpattern": subpatterns[group_id],
                "evidence_ref_total": len(refs),
                "evidence_refs": refs,
            }
        )
    if len(evidence_rows) != 16 or set(subpatterns) != set(GROUP_EVIDENCE_BLUEPRINT):
        raise ValueError("16个子模式的证据映射不完整")
    return evidence_rows


def build_source_material(z71_dir: Path, z73_dir: Path) -> dict[str, Any]:
    review_path = z71_dir / "语义人工复核源.json"
    diff_path = z71_dir / "补全逐条diff与provenance.json"
    gold_path = z73_dir / "第3章结构层金标v1.2.json"
    four_round_path = z73_dir / FOUR_ROUND_FILE

    review = read_json(review_path)
    diff = read_json(diff_path)
    gold = read_json(gold_path)
    four_rounds = read_json(four_round_path)

    for section, expected in EXPECTED_Z71_LEDGER_COUNTS.items():
        actual = len(review.get(section, []))
        if actual != expected:
            raise ValueError(f"Z71 {section} 应为{expected}行，实际{actual}行")
    rounds = four_rounds.get("rounds", [])
    round_ids = [row.get("round_id") for row in rounds]
    if round_ids != EXPECTED_FOUR_ROUND_IDS:
        raise ValueError(f"四轮顺序或标识不符：{round_ids}")
    for row in rounds:
        actual = len(row.get("formal_part_rows", []))
        if actual != EXPECTED_FORMAL_PARTS_PER_ROUND:
            raise ValueError(f"{row.get('round_id')} formal_part_rows 应为23行，实际{actual}行")
    expected_part_ids = {
        row["formal_gold_part_id"] for row in rounds[0]["formal_part_rows"]
    }
    if len(expected_part_ids) != EXPECTED_FORMAL_PARTS_PER_ROUND:
        raise ValueError("首轮 formal_gold_part_id 不是23个唯一项")
    for row in rounds[1:]:
        actual_ids = {item["formal_gold_part_id"] for item in row["formal_part_rows"]}
        if actual_ids != expected_part_ids:
            raise ValueError(f"{row['round_id']} 的23个正式部件与首轮不一致")

    review_rows = _index_by_event(review.get("fill_rows", []))
    raw_candidates = []
    for row in diff.get("rows", []):
        event_id = row.get("event_id")
        review_row = review_rows.get(event_id, {})
        verdict = review_row.get("verdict") or row.get("semantic_review") or "unknown"
        raw_candidates.append(
            {
                "chapter": row.get("chapter"),
                "event_id": event_id,
                "candidate_polarity": "positive_candidate" if verdict == "pass" else "negative_candidate",
                "verdict": verdict,
                "before": row.get("before"),
                "after": row.get("after"),
                "review_note": review_row.get("note") or row.get("semantic_review_note"),
            }
        )

    verdict_counts = Counter(row["verdict"] for row in raw_candidates)
    decisions = [
        item.get("granularity_decision")
        for item in gold.get("layered_items", [])
        if item.get("granularity_decision")
    ]
    formal_rows = []
    for round_index, round_row in enumerate(rounds):
        for row_index, row in enumerate(round_row["formal_part_rows"]):
            part_id = row["formal_gold_part_id"]
            formal_rows.append(
                {
                    "round_id": round_row["round_id"],
                    "round_index": round_index,
                    "row_index": row_index,
                    "json_pointer": f"/rounds/{round_index}/formal_part_rows/{row_index}",
                    **row,
                    "issue_tags": _formal_issue_tags(part_id, row.get("verdict", "unknown")),
                }
            )
    invalid_anchor_rows = [row for row in formal_rows if "invalid_anchor" in row["issue_tags"]]
    categorized_issues = {
        category: [
            row
            for row in formal_rows
            if category in row["issue_tags"] and row.get("verdict") != "strict_hit"
        ]
        for category in FORMAL_PART_CATEGORY_IDS
    }
    group_evidence = _build_group_evidence(review, four_rounds, review_path, four_round_path)
    return {
        "schema_version": "z74a-source-material-v1",
        "status": "source_only_not_prompt_visible",
        "candidate_status": CANDIDATE_STATUS,
        "candidate_status_label": CANDIDATE_STATUS_CN,
        "future_prompt_visibility": False,
        "hard_boundary": "本文件只用于审计来源，永不拼入未来模型提示词；其中真实专名不参加新三联例的零重叠计数。",
        "sources": {
            "z71_review": {"path": _relative_source(review_path), "sha256": sha256_path(review_path)},
            "z71_diff": {"path": _relative_source(diff_path), "sha256": sha256_path(diff_path)},
            "z73_formal_gold": {"path": _relative_source(gold_path), "sha256": sha256_path(gold_path)},
            "z73_four_round_baseline": {
                "path": _relative_source(four_round_path),
                "sha256": sha256_path(four_round_path),
            },
        },
        "z71_full_ledgers": {
            "fill_rows": {
                "row_total": len(review["fill_rows"]),
                "rows": _ledger_rows(review["fill_rows"], "fill_rows"),
            },
            "gold_rows": {
                "row_total": len(review["gold_rows"]),
                "rows": _ledger_rows(review["gold_rows"], "gold_rows"),
            },
            "current_rows": {
                "row_total": len(review["current_rows"]),
                "rows": _ledger_rows(review["current_rows"], "current_rows"),
            },
        },
        "z71_original_positive_and_negative_candidates": {
            "row_total": len(raw_candidates),
            "verdict_counts": dict(sorted(verdict_counts.items())),
            "rows": raw_candidates,
        },
        "z73_scale_contract": {
            "formal_status": gold.get("status"),
            "gold_scope": gold.get("gold_scope"),
            "atomicity_policy": gold.get("atomicity_policy"),
            "granularity_decision_counts": dict(sorted(Counter(decisions).items())),
        },
        "z73_four_round_formal_parts": {
            "round_total": len(rounds),
            "round_ids": round_ids,
            "part_rows_per_round": EXPECTED_FORMAL_PARTS_PER_ROUND,
            "row_total": len(formal_rows),
            "verdict_counts": dict(sorted(Counter(row.get("verdict") for row in formal_rows).items())),
            "rows": formal_rows,
            "invalid_anchor_rows": {
                "row_total": len(invalid_anchor_rows),
                "rows": invalid_anchor_rows,
            },
            "categorized_non_strict_rows": {
                category: {"row_total": len(rows), "rows": rows}
                for category, rows in categorized_issues.items()
            },
        },
        "subpattern_evidence_map": {
            "group_total": len(group_evidence),
            "all_refs_are_json_pointer_locatable": True,
            "rows": group_evidence,
        },
    }


def iter_string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_string_values(child)


def validate_model_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    groups = candidate.get("groups", [])
    type_counts = Counter(group.get("pathology_type") for group in groups)
    if len(groups) != 16:
        errors.append(f"三联组应为16，实际{len(groups)}")
    if set(type_counts.values()) != {4} or len(type_counts) != 4:
        errors.append(f"应为四类且每类四组，实际{dict(type_counts)}")

    just_right_record_total = 0
    anchor_total = 0
    wrong_anchor_case_total = 0
    for group in groups:
        group_id = group.get("group_id", "unknown")
        source_scenarios = group.get("source_scenario", [])
        for variant_name in ("too_large", "too_small"):
            variant = group.get(variant_name, {})
            if variant.get("output_count") != len(variant.get("records", [])):
                errors.append(f"{group_id}.{variant_name} 条数声明不一致")
            for record_index, bad_record in enumerate(variant.get("records", []), start=1):
                wrong_case = bad_record.get("wrong_anchor_case")
                if not wrong_case:
                    continue
                wrong_anchor_case_total += 1
                anchors = wrong_case.get("anchors", [])
                components = wrong_case.get("claim_components", {})
                supported = wrong_case.get("supported_claim_terms", {})
                unsupported = wrong_case.get("unsupported_claim_terms", {})
                if not anchors or not supported or not unsupported:
                    errors.append(f"{group_id}.{variant_name}[{record_index}] 错锚结构不完整")
                    continue
                for anchor in anchors:
                    if not 10 <= len(anchor) <= 25:
                        errors.append(
                            f"{group_id}.{variant_name}[{record_index}] 错锚长度不是10至25字：{anchor}"
                        )
                    if not any(anchor in scenario for scenario in source_scenarios):
                        errors.append(
                            f"{group_id}.{variant_name}[{record_index}] 错锚不在原始场景：{anchor}"
                        )
                normalized_anchors = [normalize_text(anchor) for anchor in anchors]
                normalized_claim = normalize_text(bad_record.get("text", ""))
                for support_kind, should_be_in_anchor in ((supported, True), (unsupported, False)):
                    for component, terms in support_kind.items():
                        field_value = normalize_text(str(components.get(component, "")))
                        if not field_value:
                            errors.append(
                                f"{group_id}.{variant_name}[{record_index}] 错锚缺主张字段{component}"
                            )
                        for term in terms:
                            normalized_term = normalize_text(term)
                            if normalized_term not in field_value or normalized_term not in normalized_claim:
                                errors.append(
                                    f"{group_id}.{variant_name}[{record_index}] 主张字段未包含支撑词{term}"
                                )
                            appears = any(normalized_term in anchor for anchor in normalized_anchors)
                            if appears != should_be_in_anchor:
                                relation = "应出现却未出现" if should_be_in_anchor else "应缺失却出现"
                                errors.append(
                                    f"{group_id}.{variant_name}[{record_index}] 错锚中的{term}{relation}"
                                )
        if group_id in SMALL_GRANULARITY_ACTION_TERMS:
            granularity_check = group.get("too_large", {}).get("granularity_only_check", {})
            expected_terms = SMALL_GRANULARITY_ACTION_TERMS[group_id]
            if granularity_check.get("source_action_terms") != expected_terms:
                errors.append(f"{group_id}.too_large 动作清单与固定规格不一致")
            if granularity_check.get("source_action_term_total") != len(expected_terms):
                errors.append(f"{group_id}.too_large 动作清单条数不一致")
            if granularity_check.get("invented_action_count") != 0:
                errors.append(f"{group_id}.too_large 声明含新增动作")
            normalized_source = normalize_text("\n".join(source_scenarios))
            normalized_too_large = normalize_text(
                "\n".join(
                    record_row.get("text", "")
                    for record_row in group.get("too_large", {}).get("records", [])
                )
            )
            for term in expected_terms:
                normalized_term = normalize_text(term)
                if normalized_term not in normalized_source:
                    errors.append(f"{group_id}.too_large 动作词不在原场景：{term}")
                if normalized_term not in normalized_too_large:
                    errors.append(f"{group_id}.too_large 合并版漏动作词：{term}")
        just_right = group.get("just_right", {})
        records = just_right.get("records", [])
        just_right_record_total += len(records)
        if just_right.get("expected_record_count") != len(records):
            errors.append(f"{group_id}.just_right 条数声明不一致")
        if not records:
            errors.append(f"{group_id}.just_right 不得为空")
        for index, item in enumerate(records, start=1):
            for key in (
                "subject",
                "action",
                "result",
                "necessary_qualifiers",
                "text",
                "anchors",
                "anchor_support",
            ):
                if key not in item or item[key] in (None, "", []):
                    errors.append(f"{group_id}.just_right[{index}] 缺{key}")
            anchors = item.get("anchors", [])
            anchor_total += len(anchors)
            for anchor in anchors:
                if not 10 <= len(anchor) <= 25:
                    errors.append(f"{group_id}.just_right[{index}] 短引长度不是10至25字：{anchor}")
                if not any(anchor in scenario for scenario in source_scenarios):
                    errors.append(f"{group_id}.just_right[{index}] 短引不在原始场景：{anchor}")

            support = item.get("anchor_support", {})
            normalized_anchors = [normalize_text(anchor) for anchor in anchors]

            def check_support(component: str, component_value: str, support_row: dict[str, Any]) -> None:
                terms = support_row.get("terms", [])
                anchor_indexes = support_row.get("anchor_indexes", [])
                if not terms or not anchor_indexes:
                    errors.append(f"{group_id}.just_right[{index}] {component}支撑项为空")
                    return
                if any(not isinstance(anchor_index, int) or not 0 <= anchor_index < len(anchors) for anchor_index in anchor_indexes):
                    errors.append(f"{group_id}.just_right[{index}] {component}短引序号越界")
                    return
                normalized_component = normalize_text(component_value)
                selected_anchors = [normalized_anchors[anchor_index] for anchor_index in anchor_indexes]
                for term in terms:
                    normalized_term = normalize_text(term)
                    if len(normalized_term) < 2:
                        errors.append(f"{group_id}.just_right[{index}] {component}支撑词过短：{term}")
                    if normalized_term not in normalized_component:
                        errors.append(
                            f"{group_id}.just_right[{index}] {component}字段不含支撑词：{term}"
                        )
                    if not any(normalized_term in anchor for anchor in selected_anchors):
                        errors.append(
                            f"{group_id}.just_right[{index}] {component}短引不托支撑词：{term}"
                        )

            for component in ("subject", "action", "result"):
                check_support(component, str(item.get(component, "")), support.get(component, {}))
            qualifier_support = support.get("necessary_qualifiers", [])
            qualifiers = item.get("necessary_qualifiers", [])
            if len(qualifier_support) != len(qualifiers):
                errors.append(f"{group_id}.just_right[{index}] 必要限定与支撑项条数不一致")
            for expected_index, support_row in enumerate(qualifier_support):
                qualifier_index = support_row.get("qualifier_index")
                if qualifier_index != expected_index or qualifier_index >= len(qualifiers):
                    errors.append(f"{group_id}.just_right[{index}] 必要限定支撑序号错误")
                    continue
                check_support(
                    f"necessary_qualifiers[{qualifier_index}]",
                    str(qualifiers[qualifier_index]),
                    support_row,
                )

    if wrong_anchor_case_total != 4:
        errors.append(f"锚不托病应有4个显式错锚，实际{wrong_anchor_case_total}")

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "pathology_type_total": len(type_counts),
        "type_counts": dict(sorted(type_counts.items())),
        "triplet_group_total": len(groups),
        "variant_total": len(groups) * 3,
        "just_right_record_total": just_right_record_total,
        "anchor_total": anchor_total,
        "wrong_anchor_case_total": wrong_anchor_case_total,
    }


class LiteralMatcher:
    """小型 Aho-Corasick；一次线性扫描查候选长片段。"""

    def __init__(self, patterns: Iterable[str]) -> None:
        self.goto: list[dict[str, int]] = [{}]
        self.fail: list[int] = [0]
        self.outputs: list[list[str]] = [[]]
        for pattern in sorted(set(patterns)):
            state = 0
            for char in pattern:
                if char not in self.goto[state]:
                    self.goto[state][char] = self._new_state()
                state = self.goto[state][char]
            self.outputs[state].append(pattern)
        queue: deque[int] = deque()
        for state in self.goto[0].values():
            queue.append(state)
        while queue:
            current = queue.popleft()
            for char, nxt in self.goto[current].items():
                queue.append(nxt)
                fallback = self.fail[current]
                while fallback and char not in self.goto[fallback]:
                    fallback = self.fail[fallback]
                self.fail[nxt] = self.goto[fallback].get(char, 0)
                self.outputs[nxt].extend(self.outputs[self.fail[nxt]])

    def _new_state(self) -> int:
        self.goto.append({})
        self.fail.append(0)
        self.outputs.append([])
        return len(self.goto) - 1

    def find(self, text: str, limit: int = 200) -> set[str]:
        found: set[str] = set()
        state = 0
        for char in text:
            while state and char not in self.goto[state]:
                state = self.fail[state]
            state = self.goto[state].get(char, 0)
            found.update(self.outputs[state])
            if len(found) >= limit:
                break
        return found


def _long_fragments(strings: Iterable[str], length: int) -> set[str]:
    fragments: set[str] = set()
    for text in strings:
        normalized = normalize_text(text)
        if len(normalized) < length:
            continue
        fragments.update(normalized[index : index + length] for index in range(len(normalized) - length + 1))
    return fragments


def parse_corpus_args(values: list[str] | None) -> dict[str, Path]:
    if not values:
        return dict(DEFAULT_CORPORA)
    parsed: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"语料参数必须是 标签=路径：{value}")
        label, raw_path = value.split("=", 1)
        if label in parsed:
            raise ValueError(f"语料标签重复：{label}")
        parsed[label] = Path(raw_path).expanduser().resolve()
    missing = sorted(set(PROTECTED_TERMS) - set(parsed))
    extra = sorted(set(parsed) - set(PROTECTED_TERMS))
    if missing or extra:
        raise ValueError(f"六本标签必须固定；缺少={missing}，多出={extra}")
    return parsed


_CHAPTER_HEADING_RE = re.compile(
    r"(?m)^(?:卷[^\n]*?\s+)?第\s*[0-9一二三四五六七八九十百千零〇两]+\s*(?:章|回)[^\n]*$"
)
_FROZEN_CHAPTER_NAME_RE = re.compile(r"^(\d{4})_")


def _tree_hash(rows: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for name, raw in rows:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")
    return digest.hexdigest()


def load_corpus_window(label: str, path: Path) -> tuple[str, dict[str, Any]]:
    """只返回本批获准章窗；原书txt在第51个章标题处截断。"""

    spec = CORPUS_WINDOWS[label]
    start = spec["start_chapter"]
    end = spec["end_chapter"]
    if spec["source_kind"] == "frozen_chapter_directory":
        if not path.is_dir():
            raise FileNotFoundError(f"冻结章目录不存在：{path}")
        selected: list[tuple[str, bytes]] = []
        seen: list[int] = []
        for chapter_path in sorted(path.glob("*.txt")):
            match = _FROZEN_CHAPTER_NAME_RE.match(chapter_path.name)
            if not match:
                continue
            chapter = int(match.group(1))
            if start <= chapter <= end:
                raw = chapter_path.read_bytes()
                selected.append((chapter_path.name, raw))
                seen.append(chapter)
        expected = list(range(start, end + 1))
        if seen != expected:
            raise ValueError(f"{label}冻结章不连续：期望{start}-{end}，实际首尾={seen[:1]}..{seen[-1:]}")
        window_bytes = b"\n".join(raw for _, raw in selected)
        text = window_bytes.decode("utf-8")
        receipt = {
            "label": label,
            "source_kind": spec["source_kind"],
            "path": str(path),
            "source_file_count": len(selected),
            "source_bytes": sum(len(raw) for _, raw in selected),
            "source_tree_sha256": _tree_hash(selected),
            "window_start_chapter": start,
            "window_end_chapter": end,
            "window_chapter_count": len(selected),
            "window_bytes": len(window_bytes),
            "window_sha256": hashlib.sha256(window_bytes).hexdigest(),
        }
        return text, receipt

    if not path.is_file():
        raise FileNotFoundError(f"原书正文不存在：{path}")
    window_lines: list[str] = []
    headings: list[str] = []
    next_heading: str | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            stripped = line.rstrip("\r\n")
            if _CHAPTER_HEADING_RE.fullmatch(stripped):
                if len(headings) == end:
                    next_heading = stripped
                    break
                headings.append(stripped)
            if headings:
                window_lines.append(line)
    if len(headings) != end or next_heading is None:
        raise ValueError(f"{label}章标题不足以截取前{end}章：边界前只识别到{len(headings)}个")
    window_text = "".join(window_lines)
    window_bytes = window_text.encode("utf-8")
    receipt = {
        "label": label,
        "source_kind": spec["source_kind"],
        "path": str(path),
        "source_file_count": 1,
        "source_bytes": path.stat().st_size,
        "source_file_sha256": sha256_path(path),
        "window_start_chapter": start,
        "window_end_chapter": end,
        "window_chapter_count": end - start + 1,
        "heading_count_read_through_boundary": end + 1,
        "window_first_heading": headings[start - 1],
        "window_next_heading": next_heading,
        "window_bytes": len(window_bytes),
        "window_sha256": hashlib.sha256(window_bytes).hexdigest(),
    }
    return window_text, receipt


def audit_decoupling(candidate: dict[str, Any], corpora: dict[str, Path]) -> dict[str, Any]:
    strings = list(iter_string_values(candidate))
    normalized_model_text = normalize_text("\n".join(strings))

    protected_hits: list[dict[str, str]] = []
    for label, categories in PROTECTED_TERMS.items():
        for category, terms in categories.items():
            for term in terms:
                if normalize_text(term) in normalized_model_text:
                    protected_hits.append({"corpus": label, "category": category, "term": term})

    signature_hits = sorted(
        term for term in PLOT_SIGNATURE_TERMS if normalize_text(term) in normalized_model_text
    )

    fragments = _long_fragments(strings, LONG_FRAGMENT_LENGTH)
    matcher = LiteralMatcher(fragments)
    long_matches: list[dict[str, str]] = []
    corpus_rows: list[dict[str, Any]] = []
    registry_absent_from_window: list[dict[str, str]] = []
    registry_observed_in_window: set[tuple[str, str, str]] = set()
    for label in sorted(corpora):
        path = corpora[label]
        text, corpus_row = load_corpus_window(label, path)
        normalized_corpus = normalize_text(text)
        registry_evidence_space = normalized_corpus + normalize_text(label + path.name)
        for category, terms in PROTECTED_TERMS[label].items():
            for term in terms:
                if normalize_text(term) not in registry_evidence_space:
                    registry_absent_from_window.append(
                        {"corpus": label, "category": category, "term": term}
                    )
                else:
                    registry_observed_in_window.add((label, category, term))
        for fragment in sorted(matcher.find(normalized_corpus)):
            long_matches.append({"corpus": label, "normalized_fragment": fragment})
        corpus_row["window_normalized_characters"] = len(normalized_corpus)
        corpus_rows.append(corpus_row)

    title_character_place_hits = [
        hit for hit in protected_hits if hit["category"] in {"titles", "characters", "places"}
    ]
    concept_hits = [hit for hit in protected_hits if hit["category"] == "concepts"]
    window_verified_proper_hits = [
        hit
        for hit in protected_hits
        if (hit["corpus"], hit["category"], hit["term"]) in registry_observed_in_window
    ]
    gates = {
        "six_corpus_exact_proper_name_overlap": {
            "count": len(window_verified_proper_hits),
            "status": "pass" if not window_verified_proper_hits else "fail",
            "window_verified_term_total": len(registry_observed_in_window),
            "hits": window_verified_proper_hits,
        },
        "protected_title_character_place_overlap": {
            "count": len(title_character_place_hits),
            "status": "pass" if not title_character_place_hits else "fail",
            "hits": title_character_place_hits,
        },
        "protected_ability_or_concept_overlap": {
            "count": len(concept_hits),
            "status": "pass" if not concept_hits else "fail",
            "hits": concept_hits,
        },
        "normalized_long_fragment_overlap": {
            "count": len(long_matches),
            "status": "pass" if not long_matches else "fail",
            "threshold_normalized_characters": LONG_FRAGMENT_LENGTH,
            "hits": long_matches,
        },
        "plot_signature_forbidden_term_overlap": {
            "count": len(signature_hits),
            "status": "pass" if not signature_hits else "fail",
            "hits": signature_hits,
        },
    }
    passed = all(gate["status"] == "pass" for gate in gates.values())
    return {
        "schema_version": "z74a-mechanical-decoupling-v1",
        "status": "pass" if passed else "fail",
        "audited_file": MODEL_FILE,
        "audited_scope": "三联例候选中全部字符串值，即未来模型可见文本",
        "excluded_scope": f"{SOURCE_FILE} 及其他 provenance；它们永不进入未来提示词",
        "corpora": corpus_rows,
        "protected_registry_term_total": sum(
            len(terms)
            for categories in PROTECTED_TERMS.values()
            for terms in categories.values()
        ),
        "protected_registry_terms_not_observed_in_current_window": {
            "count": len(registry_absent_from_window),
            "terms": registry_absent_from_window,
            "gate_effect": "none；保护表可以覆盖章窗外已知专名，不因本窗未出现而移除。",
        },
        "candidate_long_fragment_total": len(fragments),
        "gates": gates,
        "mechanical_boundary": {
            "exact_name_rule": "只对本工具明列且已在对应正文中核到的小说名、角色、地名、能力或专有概念做归一化精确子串检查。",
            "extra_protection_rule": "另用完整显式保护表检查小说名、角色、地名、能力和专有概念；章窗内未出现的词仍保留为额外保护项，但不冒充本窗抽取得到。",
            "long_fragment_rule": "对模型可见的每个字符串分别做NFKC、忽略大小写并去标点空白，再以18个归一化字符为滑窗，与X01冻结1至200章及其余五本原书前50章线性查重。",
            "plot_signature_rule": "检查固定题材禁词；另由逐组人工结构复核判断是否只是改名复述。",
            "false_positive_policy": "没有逐词白名单豁免。少于18字的常用短语不进入长片段闸，这是统一阈值，不是按命中临时放行。",
            "known_limit": "专名表和情节禁词表是显式保护表，不是自动命名实体识别；零命中不能证明抽象情节绝对无相似，只能证明本批四道机械闸为零。",
        },
    }


def build_structure_review(candidate: dict[str, Any]) -> dict[str, Any]:
    manual_notes = {
        "LARGE-01": "两个无关设施异常只训练‘无关系词就分开’，没有沿用秘密线索汇聚或超常原因揭露结构。",
        "LARGE-02": "普通发车排班中的两名工作人员只承载主体切换，不含队伍、阵营或身份揭露结构。",
        "LARGE-03": "采购暂缓与去开会是日常决策加位移，没有沿用冒险目标、追查或能力发动结构。",
        "LARGE-04": "封条状态与温度规程是质量管理中的事实和条件规则，没有沿用危险物品或超常代价设定。",
        "SMALL-01": "更换滤芯是单设备维护完成态，不对应成长、升级或获得特殊物品。",
        "SMALL-02": "备份后切换服务是普通运维链，不对应传送、复原或特殊空间机制。",
        "SMALL-03": "器材清点安排只训练同一言语任务，不复述家族命令、组织任务或队伍分工。",
        "SMALL-04": "闭店交接是重复性门店流程，不对应每日训练、规则修习或资源积累。",
        "MISS-01": "计数差异只承载未确认判断，不复述失踪、阴谋或身份猜测。",
        "MISS-02": "更换标签计划是未执行行政安排，不对应远期成长目标或行动伏笔。",
        "MISS-03": "十箱抽查只训练数量强度，不对应战力等级、资质或群体胜负。",
        "MISS-04": "会议室开放时间只是场地限制，不对应世界规则、门派规矩或身份门槛。",
        "ANCHOR-01": "样品配送与接待签收是常规交接，不对应护送、交易或关键物品转移情节。",
        "ANCHOR-02": "复位键和指示灯只证明设备操作完成，不对应复苏、觉醒或状态晋升。",
        "ANCHOR-03": "文件归档与关窗只训练邻句主体识别，没有追逐、监视或关系冲突。",
        "ANCHOR-04": "货架盘点和差额处置是条件化仓储指令，不对应生存任务、惩罚或团队关卡。",
    }
    rows = []
    for group in candidate["groups"]:
        group_id = group["group_id"]
        rows.append(
            {
                "group_id": group_id,
                "neutral_domain": group["neutral_domain"],
                "rule_review": "pass",
                "manual_structure_review": "pass",
                "reviewer": "Codex",
                "reason": manual_notes[group_id],
            }
        )
    return {
        "schema_version": "z74a-plot-structure-review-v1",
        "status": "pass",
        "review_scope": "16组source_scenario、太大、太小、刚好四部分",
        "rule_basis": "专名保护表＋情节签名禁词表＋中性工作场景域",
        "manual_boundary": "这是Codex单审的结构同源性复核，不冒充独立双审或语义金标验收。",
        "rows": rows,
    }


def make_stop_report(
    structure: dict[str, Any], decoupling: dict[str, Any], source_material: dict[str, Any]
) -> str:
    gates = decoupling["gates"]
    corpus_lines = "\n".join(
        f"- {row['label']}：扫描第{row['window_start_chapter']}–{row['window_end_chapter']}章，窗口 {row['window_bytes']} 字节，窗口 SHA-256 `{row['window_sha256']}`"
        for row in decoupling["corpora"]
    )
    return f"""# 第74道 A线停点回包｜正反例换皮候选

✅ 结论：A线机械候选已生成。明确状态是：**{CANDIDATE_STATUS_CN}**。

- 固定病灶 4 类，每类 4 个子模式，共 {structure['triplet_group_total']} 组三联例、{structure['variant_total']} 个太大／太小／刚好版本。
- 刚好版共 {structure['just_right_record_total']} 条、{structure['anchor_total']} 个短引；每条都列出主体、动作、结果、必要限定的字段支撑词和对应短引。
- 4 个锚不托病错误版都显式带错误短引；程序只证明“部分支撑词能在短引中找到、另一部分找不到”。
- Z71 三组原料已全量入账：补全 32 行、金标 14 行、现役 34 行。
- Z73 四轮基线已全量入账：4 轮 × 23 行＝{source_material['z73_four_round_formal_parts']['row_total']} 行；判词、无效锚、不确定认知、意愿计划和背景限制问题均逐行可定位。
- 16 个子模式各自都有具体文件路径和 JSON 定位，不再使用无法回读的概括引用。
- 0 模型调用、0 网络、0 抽取；没有改金标、指针、抽取合同或默认链。

🔥 解耦四闸

- 六本专名精确重叠：{gates['six_corpus_exact_proper_name_overlap']['count']}
- 保护小说名／角色／地名重叠：{gates['protected_title_character_place_overlap']['count']}
- 保护能力／专有概念重叠：{gates['protected_ability_or_concept_overlap']['count']}
- 18字归一化长片段重叠：{gates['normalized_long_fragment_overlap']['count']}
- 情节签名禁词重叠：{gates['plot_signature_forbidden_term_overlap']['count']}
- 16组情节结构人工／规则复核：通过；这是 Codex 单审，不冒充独立双审。

六本实际正文：

{corpus_lines}

⚠️ 机械边界

原料证据和新三联例严格分栏。`{SOURCE_FILE}` 保留真实事件、判词和专名，只供追溯，永不拼进未来提示词；零重叠只核 `{MODEL_FILE}` 的全部模型可见字符串。长片段闸统一按 NFKC、忽略大小写、去标点空白后的 18 字滑窗查 X01 intake 冻结第1–200章与其余五本原书第1–50章。正文只扫描、不拷贝入仓。专名表与情节禁词表是显式保护表，不是自动识别人名地名；没有逐词白名单豁免，少于18字的常用短语只因统一阈值不进入长片段闸。

短引校验只核字段支撑词能否逐字回到对应短引，不等于程序已经证明整句语义正确。整句是否成立仍要靠后续人工语义审定。

👉 停点

这批只证明“候选例已换皮且机械解耦”。它还是候选银标，尚未做语义审定；不得固化，也不得升为默认提示词。若要继续，必须另开人工语义审定，本道不替后续拍板。

来源：Codex
"""


def _relative_source(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def generate_core(
    target: Path,
    z71_dir: Path,
    z73_dir: Path,
    corpora: dict[str, Path],
) -> dict[str, str]:
    target.mkdir(parents=True, exist_ok=True)
    candidate = build_model_candidate()
    structure = validate_model_candidate(candidate)
    source_material = build_source_material(z71_dir, z73_dir)
    decoupling = audit_decoupling(candidate, corpora)
    structure_review = build_structure_review(candidate)

    if structure["status"] != "pass":
        raise RuntimeError(f"三联例结构验收失败：{structure['errors']}")
    if decoupling["status"] != "pass":
        raise RuntimeError(f"机械解耦失败：{decoupling['gates']}")

    write_json(target / MODEL_FILE, candidate)
    write_json(target / SOURCE_FILE, source_material)
    write_json(target / DECOUPLING_FILE, decoupling)
    write_json(target / STRUCTURE_REVIEW_FILE, structure_review)
    (target / STOP_REPORT_FILE).write_text(
        make_stop_report(structure, decoupling, source_material), encoding="utf-8"
    )
    return {name: sha256_path(target / name) for name in CORE_FILES}


def finalize_bundle(
    target: Path,
    core_hashes: dict[str, str],
    z71_dir: Path,
    z73_dir: Path,
    corpora: dict[str, Path],
) -> None:
    double_receipt = {
        "schema_version": "z74a-double-run-consistency-v1",
        "status": "pass",
        "run_count": 2,
        "comparison_scope": CORE_FILES,
        "byte_identical": True,
        "core_hashes": core_hashes,
        "note": "两个独立临时目录各自完整生成核心文件，再逐文件比较SHA-256。",
    }
    write_json(target / DOUBLE_RUN_FILE, double_receipt)

    source_paths = [
        z71_dir / "语义人工复核源.json",
        z71_dir / "补全逐条diff与provenance.json",
        z73_dir / "第3章结构层金标v1.2.json",
        z73_dir / FOUR_ROUND_FILE,
    ]
    outputs = CORE_FILES + [DOUBLE_RUN_FILE]
    decoupling = read_json(target / DECOUPLING_FILE)
    manifest = {
        "schema_version": "z74a-report-manifest-v1",
        "status": CANDIDATE_STATUS,
        "status_label": CANDIDATE_STATUS_CN,
        "task": "第74道A线正反例换皮候选",
        "created_at": None,
        "zero_call_boundary": {
            "model_api_calls": 0,
            "network_calls": 0,
            "extraction_runs": 0,
        },
        "write_boundary": "只写A线脚本、测试与独立报告目录；不改金标、指针、抽取合同、默认链、decisions或Notion。",
        "inputs": [
            {"path": _relative_source(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)}
            for path in source_paths
        ],
        "corpora": decoupling["corpora"],
        "builder": {
            "path": "tools/z74a_rewrite_examples.py",
            "sha256": sha256_path(Path(__file__)),
        },
        "test_file": {
            "path": "tests/test_z74a_rewrite_examples.py",
            "sha256": sha256_path(ROOT / "tests/test_z74a_rewrite_examples.py")
            if (ROOT / "tests/test_z74a_rewrite_examples.py").is_file()
            else None,
        },
        "outputs": [
            {"path": name, "bytes": (target / name).stat().st_size, "sha256": sha256_path(target / name)}
            for name in outputs
        ],
        "candidate_boundary": CANDIDATE_STATUS_CN,
    }
    write_json(target / MANIFEST_FILE, manifest)
    checksum_names = outputs + [MANIFEST_FILE]
    checksum_text = "".join(f"{sha256_path(target / name)}  {name}\n" for name in checksum_names)
    (target / SHA_FILE).write_text(checksum_text, encoding="utf-8")


def _directory_hashes(path: Path) -> dict[str, str]:
    return {
        str(file.relative_to(path)): sha256_path(file)
        for file in sorted(path.iterdir())
        if file.is_file()
    }


def build_bundle(
    out_dir: Path,
    z71_dir: Path = DEFAULT_Z71_DIR,
    z73_dir: Path = DEFAULT_Z73_DIR,
    corpora: dict[str, Path] | None = None,
) -> dict[str, Any]:
    corpora = corpora or dict(DEFAULT_CORPORA)
    with tempfile.TemporaryDirectory(prefix="z74a-pass1-") as first_raw, tempfile.TemporaryDirectory(
        prefix="z74a-pass2-"
    ) as second_raw:
        first = Path(first_raw)
        second = Path(second_raw)
        first_core = generate_core(first, z71_dir, z73_dir, corpora)
        second_core = generate_core(second, z71_dir, z73_dir, corpora)
        if first_core != second_core:
            raise RuntimeError("双跑核心文件SHA不一致")
        finalize_bundle(first, first_core, z71_dir, z73_dir, corpora)
        finalize_bundle(second, second_core, z71_dir, z73_dir, corpora)
        first_all = _directory_hashes(first)
        second_all = _directory_hashes(second)
        if first_all != second_all:
            raise RuntimeError("双跑最终工件SHA不一致")

        out_dir.mkdir(parents=True, exist_ok=True)
        for file in sorted(first.iterdir()):
            if file.is_file():
                shutil.copy2(file, out_dir / file.name)
    return {
        "status": "pass",
        "out_dir": str(out_dir),
        "file_hashes": _directory_hashes(out_dir),
    }


def verify_bundle(out_dir: Path) -> dict[str, Any]:
    manifest_path = out_dir / MANIFEST_FILE
    manifest = read_json(manifest_path)
    mismatches: list[dict[str, Any]] = []
    checked = {"outputs": 0, "inputs": 0, "builder": 0, "test_file": 0, "corpora": 0, "checksums": 0}

    def resolve_external(raw_path: str) -> Path:
        path = Path(raw_path)
        return path if path.is_absolute() else ROOT / path

    def check_file(scope: str, path: Path, expected_hash: str | None, expected_bytes: int | None = None) -> None:
        actual_hash = sha256_path(path) if path.is_file() else None
        actual_bytes = path.stat().st_size if path.is_file() else None
        if actual_hash != expected_hash or (
            expected_bytes is not None and actual_bytes != expected_bytes
        ):
            mismatches.append(
                {
                    "scope": scope,
                    "path": str(path),
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                    "expected_bytes": expected_bytes,
                    "actual_bytes": actual_bytes,
                }
            )

    for row in manifest["outputs"]:
        path = out_dir / row["path"]
        check_file("outputs", path, row.get("sha256"), row.get("bytes"))
        checked["outputs"] += 1

    for row in manifest.get("inputs", []):
        check_file(
            "inputs",
            resolve_external(row["path"]),
            row.get("sha256"),
            row.get("bytes"),
        )
        checked["inputs"] += 1

    for scope, key in (("builder", "builder"), ("test_file", "test_file")):
        row = manifest.get(key)
        if not row:
            mismatches.append({"scope": scope, "error": "manifest_missing_entry"})
            continue
        check_file(scope, resolve_external(row["path"]), row.get("sha256"), row.get("bytes"))
        checked[scope] += 1

    corpus_fields = {
        "source_kind",
        "source_file_count",
        "source_bytes",
        "source_tree_sha256",
        "source_file_sha256",
        "window_start_chapter",
        "window_end_chapter",
        "window_chapter_count",
        "heading_count_read_through_boundary",
        "window_first_heading",
        "window_next_heading",
        "window_bytes",
        "window_sha256",
        "window_normalized_characters",
    }
    for expected in manifest.get("corpora", []):
        label = expected.get("label")
        try:
            text, actual = load_corpus_window(label, Path(expected["path"]))
            actual["window_normalized_characters"] = len(normalize_text(text))
            differences = {
                field: {"expected": expected.get(field), "actual": actual.get(field)}
                for field in corpus_fields
                if field in expected and expected.get(field) != actual.get(field)
            }
            if differences:
                mismatches.append(
                    {"scope": "corpora", "path": expected.get("path"), "differences": differences}
                )
        except (FileNotFoundError, KeyError, UnicodeDecodeError, ValueError) as exc:
            mismatches.append(
                {"scope": "corpora", "path": expected.get("path"), "error": str(exc)}
            )
        checked["corpora"] += 1

    checksum_path = out_dir / SHA_FILE
    if not checksum_path.is_file():
        mismatches.append({"scope": "checksums", "path": str(checksum_path), "error": "missing"})
    else:
        for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), start=1):
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            if not match:
                mismatches.append(
                    {"scope": "checksums", "line": line_number, "error": "malformed"}
                )
                continue
            expected_hash, name = match.groups()
            check_file("checksums", out_dir / name, expected_hash)
            checked["checksums"] += 1

    return {
        "status": "pass" if not mismatches else "fail",
        "checked": checked,
        "mismatches": mismatches,
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--z71-dir", type=Path, default=DEFAULT_Z71_DIR)
    parser.add_argument("--z73-dir", type=Path, default=DEFAULT_Z73_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--corpus",
        action="append",
        help="可重复六次，格式为固定标签=完整正文路径；不传则用已定位的六本正文。",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="回读输出、输入、构建脚本、测试、六本章窗和SHA清单；不重建工件。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if args.verify_only:
        result = verify_bundle(args.out_dir.resolve())
    else:
        corpora = parse_corpus_args(args.corpus)
        result = build_bundle(
            args.out_dir.resolve(),
            args.z71_dir.resolve(),
            args.z73_dir.resolve(),
            corpora,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
