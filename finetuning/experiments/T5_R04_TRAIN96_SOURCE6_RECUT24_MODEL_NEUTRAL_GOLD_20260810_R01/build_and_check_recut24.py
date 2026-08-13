from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
UPSTREAM = ROOT / (
    "finetuning/experiments/"
    "T5_R04_TRAIN96_LONG_CURRICULUM_SOURCE6_20260810_R01"
)
UPSTREAM_MANIFEST = UPSTREAM / "SOURCE6_MANIFEST.jsonl"
UPSTREAM_TARGET18 = UPSTREAM / "TARGET18_CANDIDATES.jsonl"

EXPECTED_UPSTREAM_MANIFEST_SHA = (
    "55c210090a8296b3d59698cb93e5eac3e30d73d1804c2857f4f80bf987f0839a"
)
EXPECTED_UPSTREAM_TARGET18_SHA = (
    "9a57fdde00501ff0598b07531e7983292bdc8a42c7b3b3c61bf75827af0f0afa"
)
STATUS = "CANDIDATE_MODEL_NEUTRAL_GOLD_PENDING_INDEPENDENT_REVIEW"
STATUSES = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}

SOURCE_INDEX = HERE / "SOURCE_INDEX_24.jsonl"
GOLD = HERE / "MODEL_NEUTRAL_GOLD_24.jsonl"
SIDECAR = HERE / "SEMANTIC_REVIEW_SIDECAR.jsonl"
DISPOSITION = HERE / "OLD_TARGET18_DISPOSITION.md"
SUMMARY = HERE / "REVIEW_SUMMARY.md"
MANIFEST = HERE / "OUTPUT_MANIFEST.json"
RECEIPT = HERE / "FINAL_VALIDATION_RECEIPT.json"

PRIOR_INDEXES = [
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN36_GOLD_CANDIDATE_20260809_R01/"
    "TRAIN36_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/"
    "S6_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/"
    "M6_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/"
    "L6_SOURCE_INDEX.jsonl",
    ROOT
    / "finetuning/experiments/"
    "T5_R04_TRAIN72_COMPACT_TARGET24_MODEL_NEUTRAL_GOLD_20260809_R02/"
    "SOURCE_INDEX_24.jsonl",
    ROOT
    / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/"
    "REAL24_SOURCE_INDEX.jsonl",
]

# case_id: source_id, start, end, review class, expected fact count
SELECTIONS = {
    "RC96-CH01-01": ("LC6-CH01", 1503, 1718, "NATURAL_ZERO", 0),
    "RC96-CH01-02": ("LC6-CH01", 1720, 1875, "FACT_3", 3),
    "RC96-CH01-03": ("LC6-CH01", 2300, 2427, "FACT_3", 3),
    "RC96-CH01-04": ("LC6-CH01", 2546, 2743, "FACT_1", 1),
    "RC96-CH02-01": ("LC6-CH02", 701, 911, "HARD_ZERO", 0),
    "RC96-CH02-02": ("LC6-CH02", 1138, 1308, "FACT_6", 6),
    "RC96-CH02-03": ("LC6-CH02", 1838, 1929, "FACT_2", 2),
    "RC96-CH02-04": ("LC6-CH02", 2129, 2236, "FACT_1", 1),
    "RC96-CH03-01": ("LC6-CH03", 745, 950, "NATURAL_ZERO", 0),
    "RC96-CH03-02": ("LC6-CH03", 2523, 2587, "FACT_2", 2),
    "RC96-CH03-03": ("LC6-CH03", 1289, 1404, "FACT_5", 5),
    "RC96-CH03-04": ("LC6-CH03", 2192, 2318, "FACT_3", 3),
    "RC96-CH04-01": ("LC6-CH04", 875, 1102, "HARD_ZERO", 0),
    "RC96-CH04-02": ("LC6-CH04", 1104, 1360, "HARD_ZERO", 0),
    "RC96-CH04-03": ("LC6-CH04", 1361, 1468, "FACT_1", 1),
    "RC96-CH04-04": ("LC6-CH04", 2114, 2231, "FACT_6", 6),
    "RC96-CH06-01": ("LC6-CH06", 889, 1005, "FACT_5", 5),
    "RC96-CH06-02": ("LC6-CH06", 1471, 1701, "FACT_1", 1),
    "RC96-CH06-03": ("LC6-CH06", 1759, 1901, "NATURAL_ZERO", 0),
    "RC96-CH06-04": ("LC6-CH06", 2229, 2407, "FACT_3", 3),
    "RC96-CH08-01": ("LC6-CH08", 17, 192, "FACT_2", 2),
    "RC96-CH08-02": ("LC6-CH08", 630, 860, "HARD_ZERO", 0),
    "RC96-CH08-03": ("LC6-CH08", 862, 1084, "HARD_ZERO", 0),
    "RC96-CH08-04": ("LC6-CH08", 1595, 1701, "FACT_2", 2),
}

# Simple deterministic rotation: no same chapter adjacent and no two zero cases adjacent.
ROW_ORDER = [
    "RC96-CH01-02",
    "RC96-CH02-01",
    "RC96-CH03-03",
    "RC96-CH04-03",
    "RC96-CH06-01",
    "RC96-CH08-01",
    "RC96-CH02-02",
    "RC96-CH03-01",
    "RC96-CH04-04",
    "RC96-CH06-02",
    "RC96-CH08-02",
    "RC96-CH01-03",
    "RC96-CH03-04",
    "RC96-CH04-01",
    "RC96-CH06-04",
    "RC96-CH08-04",
    "RC96-CH01-01",
    "RC96-CH02-03",
    "RC96-CH04-02",
    "RC96-CH03-02",
    "RC96-CH06-03",
    "RC96-CH02-04",
    "RC96-CH08-03",
    "RC96-CH01-04",
]


def fact(
    sentence: str, status: str, speaker: str | None, evidence_ids: list[str]
) -> tuple[str, str, str | None, list[str]]:
    return sentence, status, speaker, evidence_ids


FACTS: dict[str, list[tuple[str, str, str | None, list[str]]]] = {
    "RC96-CH01-01": [],
    "RC96-CH01-02": [
        fact(
            "老何在七点四十五送来两根只收押金、不出售且下午还要借给婚庆公司的可调支柱。",
            "已发生",
            None,
            ["T01", "T02"],
        ),
        fact(
            "周遥架起临时支撑并试力后，横梁不再下沉，但断口发出轻微刮响。",
            "已发生",
            None,
            ["T03", "T04", "T05"],
        ),
        fact(
            "她说明临时支撑处只能作为通道，不能在下面囤货。",
            "否定",
            "她",
            ["T05", "T06"],
        ),
    ],
    "RC96-CH01-03": [
        fact(
            "周遥不打算当天全部拆除，只计划先给这一跨增加第二根支柱，下午清场后再更换。",
            "计划",
            "周遥",
            ["T01"],
        ),
        fact(
            "周遥计划让菜场继续营业，但西侧当晚提前一小时收摊。",
            "计划",
            "周遥",
            ["T01", "T02"],
        ),
        fact(
            "陈放答应通知夜市商户，并把临时支撑押金、北仓用料和下午施工写进处置单。",
            "承诺",
            "陈放",
            ["T03", "T04"],
        ),
    ],
    "RC96-CH01-04": [
        fact(
            "几名夜市摊主搬运成捆桌板时，菜场南侧二楼外置楼梯最下面的踏板正随脚步下陷。",
            "正在发生",
            None,
            ["T04", "T05", "T06"],
        )
    ],
    "RC96-CH02-01": [],
    "RC96-CH02-02": [
        fact(
            "杜二爷带来的四箱胡椒都封着水运帮火漆，但报单只登记了三箱。",
            "正在发生",
            None,
            ["T01", "T02"],
        ),
        fact(
            "杜二爷称第四箱是途中临时并来的样货，不计入当天大账。",
            "已发生",
            "杜二爷",
            ["T02"],
        ),
        fact(
            "杜二爷要求只借沈家的秤给第四箱过数。",
            "计划",
            "杜二爷",
            ["T02", "T03"],
        ),
        fact(
            "沈绫拒绝替没有来历的货物补身份。",
            "否定",
            "沈绫",
            ["T03", "T04"],
        ),
        fact(
            "沈绫说明第四箱一旦称重，数值就会写进当天的平码簿。",
            "条件",
            "沈绫",
            ["T03", "T04", "T05"],
        ),
        fact(
            "沈绫说明若账簿有第四箱而报单没有，到了关口会追问她的责任。",
            "条件",
            "沈绫",
            ["T03", "T04", "T05"],
        ),
    ],
    "RC96-CH02-03": [
        fact(
            "答话者说明三箱手续齐全，第四箱手续不齐全。",
            "正在发生",
            "答话者",
            ["T01"],
        ),
        fact(
            "杜二爷让脚夫抬走三箱，把第四箱留在木架上等待补签。",
            "已发生",
            None,
            ["T02", "T03"],
        ),
    ],
    "RC96-CH02-04": [
        fact(
            "沈绫安排吃完饭后把封存的秤砣送去官牙复验。",
            "计划",
            "沈绫",
            ["T04"],
        )
    ],
    "RC96-CH03-01": [],
    "RC96-CH03-02": [
        fact(
            "送液化气的师傅说村口限高杆坏了，送气车当天进不来。",
            "正在发生",
            "送液化气的师傅",
            ["T02"],
        ),
        fact(
            "送液化气的师傅判断第二天早上也未必能送到。",
            "推测",
            "送液化气的师傅",
            ["T02"],
        ),
    ],
    "RC96-CH03-03": [
        fact(
            "林慧预计第二天至少有五十八人来吃寿席。",
            "推测",
            None,
            ["T01"],
        ),
        fact(
            "林家现有六张圆桌，只能坐四十八人。",
            "正在发生",
            None,
            ["T01", "T02"],
        ),
        fact(
            "村委会仓库虽有折叠桌，但钥匙在当天去镇上的会计手里。",
            "正在发生",
            None,
            ["T02", "T03"],
        ),
        fact(
            "父亲提议让年轻人晚一轮吃饭。",
            "计划",
            "父亲",
            ["T03"],
        ),
        fact(
            "老太太反对让来祝寿的人站着等饭。",
            "否定",
            "老太太",
            ["T03", "T04"],
        ),
    ],
    "RC96-CH03-04": [
        fact(
            "三姑家三人临时有事后，寿席名单从五十九人降到五十六人。",
            "已发生",
            None,
            ["T01", "T02"],
        ),
        fact(
            "大伯建议退还一张祠堂桌，避免院里太挤。",
            "计划",
            "大伯",
            ["T02", "T03"],
        ),
        fact(
            "林满仓决定保留两张祠堂桌，以备天气转冷时把菜移进堂屋并临时放置盘子和保温桶。",
            "计划",
            "林满仓",
            ["T03", "T04"],
        ),
    ],
    "RC96-CH04-01": [],
    "RC96-CH04-02": [],
    "RC96-CH04-03": [
        fact(
            "十分钟过去后，贺宁仍未出现。",
            "正在发生",
            None,
            ["T03"],
        )
    ],
    "RC96-CH04-04": [
        fact(
            "距离检录只剩七分钟。",
            "正在发生",
            None,
            ["T01"],
        ),
        fact(
            "四班计划保留原参赛名单，不启用孟秋。",
            "计划",
            None,
            ["T01"],
        ),
        fact(
            "四班计划不让唐梨离开广播岗位。",
            "计划",
            None,
            ["T01"],
        ),
        fact(
            "贺宁手掌磨破，跑第四棒会增加全程握棒和交接风险。",
            "正在发生",
            None,
            ["T02"],
        ),
        fact(
            "许乔计划从第二棒换到第四棒，贺宁改跑第二棒。",
            "计划",
            None,
            ["T02", "T03"],
        ),
        fact(
            "杜航计划跑第一棒，宋晓按原计划跑第三棒。",
            "计划",
            None,
            ["T04"],
        ),
    ],
    "RC96-CH06-01": [
        fact(
            "五号风口没有热风，只有很弱的风。",
            "正在发生",
            None,
            ["T01"],
        ),
        fact(
            "柏青三次测得五号风口温度都比其他风口高四度。",
            "已发生",
            None,
            ["T02"],
        ),
        fact(
            "五号风口叶轮仍在转，但进风量不足。",
            "正在发生",
            None,
            ["T03"],
        ),
        fact(
            "柏青判断过滤格可能在早晨施工时装反。",
            "推测",
            "柏青",
            ["T04"],
        ),
        fact(
            "柏青计划停掉整条风廊十分钟，拆开五号进风箱。",
            "计划",
            "柏青",
            ["T04"],
        ),
    ],
    "RC96-CH06-02": [
        fact(
            "五号风口已经吹出真正的凉风。",
            "正在发生",
            None,
            ["T07"],
        )
    ],
    "RC96-CH06-03": [],
    "RC96-CH06-04": [
        fact(
            "一名家长拒绝挪车，只称自己停两分钟。",
            "否定",
            "一名家长",
            ["T01"],
        ),
        fact(
            "这名家长的车正挡住无障碍接驳车，车内一名坐轮椅的老人等着下坡。",
            "正在发生",
            None,
            ["T02", "T03"],
        ),
        fact(
            "这名家长和后面三辆车随后向前挪动，无障碍接驳车得以进入坡道。",
            "已发生",
            None,
            ["T04", "T05"],
        ),
    ],
    "RC96-CH08-01": [
        fact(
            "郑七娘贴出告示，宣布当天不卖飞升饼。",
            "否定",
            "郑七娘",
            ["T01", "T02"],
        ),
        fact(
            "郑七娘在告示中说明前一天吃饼后御剑变快只是顺风，不是配方效果。",
            "否定",
            "郑七娘",
            ["T02", "T03"],
        ),
    ],
    "RC96-CH08-02": [],
    "RC96-CH08-03": [],
    "RC96-CH08-04": [
        fact(
            "蓝芽受热后颜色变淡，锅沿和勺柄结霜，灶下火焰反而降低。",
            "已发生",
            None,
            ["T02", "T03"],
        ),
        fact(
            "郑七娘指出月露灵薯应当催火，不会压低火力。",
            "否定",
            "郑七娘",
            ["T03"],
        ),
    ],
}

ZERO_REVIEWS: dict[str, dict[str, Any]] = {
    "RC96-CH01-01": {
        "zero_kind": "NATURAL_ZERO",
        "review_reason": "车流引导、收拾物件与猫的插曲都只是现场动作，没有形成新的后续负担。",
    },
    "RC96-CH02-01": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": False,
        "tempting_exclusions": [
            ["伙计把不同货物分到三条道", "一次性动作", "只是争执后的常规分流，没有新增规则或安排。"],
            ["魏书吏把记录叠进蓝布册", "重要性", "普通收尾动作，没有改变记录内容或后续责任。"],
        ],
    },
    "RC96-CH03-01": {
        "zero_kind": "NATURAL_ZERO",
        "review_reason": "家人一边备菜一边闲谈，正文还明确说明没有一句形成决定。",
    },
    "RC96-CH04-01": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["杜航提议做两次慢速交棒", "责任区／重要性", "只是未计时热身，没有成为比赛方案或正式训练结论。"],
            ["路过同学问四班是否退赛", "说话人归属", "这是外人的问句，顾驰只回答仍在热身，没有确认退赛。"],
        ],
    },
    "RC96-CH04-02": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["粉笔圈被称为交接区，踩线要请喝水", "条件", "这是临时玩笑规则，不是比赛或队伍正式规则。"],
            ["顾驰借标志碟压住粉圈", "一次性动作", "只是处理被风吹动的练习道具，没有形成后续安排。"],
        ],
    },
    "RC96-CH06-03": {
        "zero_kind": "NATURAL_ZERO",
        "review_reason": "归还椅子和空碗是观摩结束后的日常收拾，两句“我来”也未形成未来承诺。",
    },
    "RC96-CH08-02": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["门外人猜豆羹里藏着秘诀", "说话人归属", "只是围观者猜测，没有证据或权威确认。"],
            ["瘦高弟子说御剑变快是新剑穗造成", "时间", "旁人指出剑穗上月已更换，当前说法缺少时间上的对应。"],
        ],
    },
    "RC96-CH08-03": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["纸鹤像西库回信", "实体", "拆开后只是外门弟子的打油诗，不是西库回包。"],
            ["诗句写云灶饼能冲九霄", "说话人归属", "诗句是玩笑文本，不是对飞升饼效果的可靠报告。"],
            ["药圃童子拿萝卜后又放回", "一次性动作", "物品没有形成持续转移或后续负担。"],
        ],
    },
}

SPARSE_DISTRACTORS = {
    "RC96-CH01-02": "检查底座、拧紧锁销等步骤只承托试力，不另拆成普通动作事实。",
    "RC96-CH01-03": "徐阿姨问谁去通知只是问句，真正进入Gold的是陈放的承诺。",
    "RC96-CH01-04": "收工具和午市声响只是过渡，只有踏板持续下陷形成新问题。",
    "RC96-CH02-03": "杜二爷发笑、拿回红封和省去客套不改变手续或货箱状态。",
    "RC96-CH02-04": "阿谷关于谁挖铅的猜测没有证据，不能当作责任结论。",
    "RC96-CH03-02": "贴纸和门外叫名字是过渡动作，不另计事实。",
    "RC96-CH03-04": "擦名单把纸擦薄是普通动作，不单独形成后续状态。",
    "RC96-CH04-03": "跟歌拍手和用接力棒试平衡都是等待时的动作。",
    "RC96-CH06-02": "回收纸杯、清点螺丝和擦灰都只是收尾动作。",
    "RC96-CH06-04": "家长质问为何只叫他不是新的交通规则。",
    "RC96-CH08-01": "围观者关于吃饼和饼边的说法没有得到确认。",
    "RC96-CH08-04": "削皮、称重和切块只是检验准备，不单列为重要事实。",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def split_units(text: str, max_chars: int = 40) -> list[tuple[int, int, str]]:
    units: list[tuple[int, int, str]] = []
    start = 0
    strong = set("。！？!?；;\n")
    medium = set("，,：:、")
    while start < len(text):
        hard_end = min(start + max_chars, len(text))
        end = hard_end
        if hard_end < len(text):
            min_cut = min(hard_end, start + max(12, max_chars // 2))
            strong_positions = [
                index + 1
                for index in range(min_cut, hard_end)
                if text[index] in strong
            ]
            medium_positions = [
                index + 1
                for index in range(min_cut, hard_end)
                if text[index] in medium
            ]
            if strong_positions:
                end = strong_positions[-1]
            elif medium_positions:
                end = medium_positions[-1]
        if end <= start:
            end = hard_end
        units.append((start, end, text[start:end]))
        start = end
    return units


def source_metadata() -> dict[str, dict[str, Any]]:
    if file_sha256(UPSTREAM_MANIFEST) != EXPECTED_UPSTREAM_MANIFEST_SHA:
        raise ValueError("SOURCE6_MANIFEST.jsonl SHA 漂移")
    if file_sha256(UPSTREAM_TARGET18) != EXPECTED_UPSTREAM_TARGET18_SHA:
        raise ValueError("TARGET18_CANDIDATES.jsonl SHA 漂移")
    return {row["source_id"]: row for row in read_jsonl(UPSTREAM_MANIFEST)}


def build_source_rows() -> list[dict[str, Any]]:
    metadata = source_metadata()
    rows: list[dict[str, Any]] = []
    for row_index, case_id in enumerate(ROW_ORDER, 1):
        source_id, start, end, review_class, expected_count = SELECTIONS[case_id]
        source = metadata[source_id]
        source_path = ROOT / source["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if sha256_bytes(source_bytes) != source["source_chapter_sha256"]:
            raise ValueError(f"{source_id} 章节 SHA 漂移")
        target = source_text[start:end]
        units = []
        for unit_index, (unit_start, unit_end, unit_text) in enumerate(
            split_units(target), 1
        ):
            units.append(
                {
                    "id": f"T{unit_index:02d}",
                    "start": unit_start,
                    "end": unit_end,
                    "text": unit_text,
                    "text_sha256": sha256_bytes(unit_text.encode()),
                }
            )
        rows.append(
            {
                "schema_version": "train96-source6-recut24-source-index/1.0",
                "dataset_status": STATUS,
                "row_index": row_index,
                "case_id": case_id,
                "source_id": source_id,
                "source_title": source["title"],
                "source_genre": source["genre"],
                "source_path": source["source_path"],
                "source_chapter_sha256": source["source_chapter_sha256"],
                "coordinate_space": "unicode_codepoint_0_based_half_open",
                "target_start": start,
                "target_end": end,
                "target_sha256": sha256_bytes(target.encode()),
                "target_non_whitespace_character_count": sum(
                    not char.isspace() for char in target
                ),
                "review_class": review_class,
                "reviewed_fact_count": expected_count,
                "target_units": units,
                "project_original": True,
                "model_neutral_common_material": True,
                "training_authorized": False,
            }
        )
    return rows


def build_gold_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in source_rows:
        case_id = source["case_id"]
        facts = []
        for fact_index, (sentence, status, speaker, evidence) in enumerate(
            FACTS[case_id], 1
        ):
            facts.append(
                {
                    "fact_id": f"{case_id}-F{fact_index:03d}",
                    "fact_sentence": sentence,
                    "status": status,
                    "speaker": speaker,
                    "evidence_ids": evidence,
                }
            )
        rows.append(
            {
                "dataset_status": STATUS,
                "case_id": case_id,
                "common_answer_entity_policy": "TARGET_VISIBLE_SURFACE_ONLY",
                "facts": facts,
                "exhaustive_within_target_candidate": True,
                "expected_fact_count": len(facts),
                "training_authorized": False,
            }
        )
    return rows


def build_sidecar(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in source_rows:
        case_id = source["case_id"]
        count = source["reviewed_fact_count"]
        row: dict[str, Any] = {
            "schema_version": "train96-source6-recut24-semantic-review-sidecar/1.0",
            "dataset_status": STATUS,
            "case_id": case_id,
            "review_class": source["review_class"],
            "reviewed_fact_count": count,
            "model_visible": False,
        }
        if count == 0:
            row.update(ZERO_REVIEWS[case_id])
        elif 1 <= count <= 3:
            row["clear_distractor"] = SPARSE_DISTRACTORS[case_id]
        rows.append(row)
    return rows


def validate(
    source_rows: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
    sidecar_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(source_rows) != 24 or len(gold_rows) != 24 or len(sidecar_rows) != 24:
        raise ValueError("来源、Gold或旁证不是24题")
    case_ids = [row["case_id"] for row in source_rows]
    if case_ids != ROW_ORDER or len(set(case_ids)) != 24:
        raise ValueError("case顺序或唯一性错误")
    if [row["case_id"] for row in gold_rows] != case_ids:
        raise ValueError("Gold顺序与来源索引不一致")
    if [row["case_id"] for row in sidecar_rows] != case_ids:
        raise ValueError("sidecar顺序与来源索引不一致")

    chapter_counts = Counter(row["source_id"] for row in source_rows)
    if set(chapter_counts.values()) != {4} or len(chapter_counts) != 6:
        raise ValueError(f"不是六章各四段：{chapter_counts}")
    for left, right in zip(source_rows, source_rows[1:], strict=False):
        if left["source_id"] == right["source_id"]:
            raise ValueError("确定性轮转出现同章相邻")
        if left["reviewed_fact_count"] == right["reviewed_fact_count"] == 0:
            raise ValueError("确定性轮转出现两个空题相邻")

    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    target_shas = set()
    for row in source_rows:
        by_source[row["source_id"]].append(row)
        source_path = ROOT / row["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if sha256_bytes(source_bytes) != row["source_chapter_sha256"]:
            raise ValueError(f"{row['case_id']} 章节 SHA 不符")
        target = source_text[row["target_start"] : row["target_end"]]
        if sha256_bytes(target.encode()) != row["target_sha256"]:
            raise ValueError(f"{row['case_id']} 目标 SHA 不符")
        if "".join(unit["text"] for unit in row["target_units"]) != target:
            raise ValueError(f"{row['case_id']} Txx 不能重建目标")
        if row["target_sha256"] in target_shas:
            raise ValueError("目标段 SHA 重复")
        target_shas.add(row["target_sha256"])
    for source_id, rows in by_source.items():
        rows.sort(key=lambda item: item["target_start"])
        for left, right in zip(rows, rows[1:], strict=False):
            if left["target_end"] > right["target_start"]:
                raise ValueError(f"{source_id} 内部目标重叠")

    prior_rows = []
    for path in PRIOR_INDEXES:
        prior_rows.extend(read_jsonl(path))
    prior_overlap = 0
    for row in source_rows:
        for old in prior_rows:
            old_path = old.get("source_path") or old.get("source_file")
            old_start = old.get("target_start", old.get("char_start"))
            old_end = old.get("target_end", old.get("char_end"))
            old_sha = old.get("target_sha256", old.get("segment_sha256"))
            same_sha = old_sha == row["target_sha256"]
            same_path_overlap = (
                old_path == row["source_path"]
                and isinstance(old_start, int)
                and isinstance(old_end, int)
                and max(old_start, row["target_start"])
                < min(old_end, row["target_end"])
            )
            if same_sha or same_path_overlap:
                prior_overlap += 1
    if prior_overlap:
        raise ValueError(f"与TRAIN72/L6/REAL24旧目标重叠：{prior_overlap}")

    fact_counts = []
    total_facts = 0
    for source, gold in zip(source_rows, gold_rows, strict=True):
        facts = gold["facts"]
        if gold["dataset_status"] != STATUS or gold["training_authorized"]:
            raise ValueError(f"{gold['case_id']} 状态或训练边界错误")
        if gold["expected_fact_count"] != len(facts):
            raise ValueError(f"{gold['case_id']} expected_fact_count 非机械生成")
        if len(facts) != source["reviewed_fact_count"]:
            raise ValueError(f"{gold['case_id']} Gold数量与复读结果不一致")
        if gold["common_answer_entity_policy"] != "TARGET_VISIBLE_SURFACE_ONLY":
            raise ValueError(f"{gold['case_id']} 实体政策错误")
        if gold["exhaustive_within_target_candidate"] is not True:
            raise ValueError(f"{gold['case_id']} 缺少穷尽候选标记")
        unit_ids = [unit["id"] for unit in source["target_units"]]
        for index, item in enumerate(facts, 1):
            if item["fact_id"] != f"{gold['case_id']}-F{index:03d}":
                raise ValueError(f"{gold['case_id']} fact_id 不连续")
            if not item["fact_sentence"].strip() or item["status"] not in STATUSES:
                raise ValueError(f"{gold['case_id']} 事实句或状态错误")
            if item["speaker"] is not None and not isinstance(item["speaker"], str):
                raise ValueError(f"{gold['case_id']} speaker 类型错误")
            evidence = item["evidence_ids"]
            if not evidence or any(eid not in unit_ids for eid in evidence):
                raise ValueError(f"{gold['case_id']} evidence 越界")
            positions = [unit_ids.index(eid) for eid in evidence]
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise ValueError(f"{gold['case_id']} evidence 不连续")
        fact_counts.append(len(facts))
        total_facts += len(facts)
    if Counter(fact_counts) != Counter({0: 8, 1: 4, 2: 4, 3: 4, 5: 2, 6: 2}):
        raise ValueError(f"事实分布不符：{Counter(fact_counts)}")
    if total_facts != 46:
        raise ValueError(f"事实总数不是46：{total_facts}")

    hard_zero_rows = [
        row for row in sidecar_rows if row["review_class"] == "HARD_ZERO"
    ]
    if len(hard_zero_rows) != 5:
        raise ValueError("困难空题不是5题")
    if any(len(row.get("tempting_exclusions", [])) < 2 for row in hard_zero_rows):
        raise ValueError("困难空题未逐题列出至少两个诱饵")
    if sum(row.get("one_missing_condition_away", False) for row in hard_zero_rows) < 3:
        raise ValueError("困难空题中近似正例少于3题")
    sparse_rows = [
        row for row in sidecar_rows if 1 <= row["reviewed_fact_count"] <= 3
    ]
    if len(sparse_rows) != 12 or any("clear_distractor" not in row for row in sparse_rows):
        raise ValueError("1至3条事实题缺少干扰项复核")

    zero_lengths = [
        row["target_non_whitespace_character_count"]
        for row in source_rows
        if row["reviewed_fact_count"] == 0
    ]
    positive_lengths = [
        row["target_non_whitespace_character_count"]
        for row in source_rows
        if row["reviewed_fact_count"] > 0
    ]
    if max(min(zero_lengths), min(positive_lengths)) > min(
        max(zero_lengths), max(positive_lengths)
    ):
        raise ValueError("空题与非空题长度没有重叠")

    return {
        "cases": 24,
        "facts": total_facts,
        "fact_count_distribution": dict(sorted(Counter(fact_counts).items())),
        "natural_zero_cases": 3,
        "hard_zero_cases": 5,
        "hard_zero_near_positive_cases": sum(
            row.get("one_missing_condition_away", False) for row in hard_zero_rows
        ),
        "unique_source_chapters": 6,
        "targets_per_chapter": 4,
        "within_recut24_overlaps": 0,
        "prior_train72_l6_real24_overlaps": prior_overlap,
        "target_non_whitespace_character_range": [
            min(row["target_non_whitespace_character_count"] for row in source_rows),
            max(row["target_non_whitespace_character_count"] for row in source_rows),
        ],
        "zero_target_length_range": [min(zero_lengths), max(zero_lengths)],
        "positive_target_length_range": [
            min(positive_lengths),
            max(positive_lengths),
        ],
        "zero_positive_length_overlap": True,
    }


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for member in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(member.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(member.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def markdown_disposition() -> str:
    return """# 旧 TARGET18 处置

原 `TARGET18_CANDIDATES.jsonl` 的十八个 650～900 字责任段不再作为低／中密度教材目标。独立复读已经证明：七个原意为空的长段实际都含重要事实，多数责任段自然落在 4～14 条，不适合拿来教“该空就空、事实少就少写”。

六篇完整原创章本身继续冻结保留，仍是有效的模型中立共同原料。R01 只从原章字节重新切二十四个更紧凑的责任区；旧十八段没有被删除、覆盖或改写，也没有被当成 Gold。

上游 `TARGET18_CANDIDATES.jsonl` SHA-256：`9a57fdde00501ff0598b07531e7983292bdc8a42c7b3b3c61bf75827af0f0afa`。

当前新包仍只是模型中立 Gold 候选，不是训练授权。

来源：Codex
"""


def markdown_summary(stats: dict[str, Any], source_rows: list[dict[str, Any]]) -> str:
    count_order = [0, 1, 2, 3, 5, 6]
    distribution = Counter(row["reviewed_fact_count"] for row in source_rows)
    distribution_text = "、".join(
        f"{count}条×{distribution[count]}" for count in count_order
    )
    return f"""# SOURCE6 重切24题｜候选审收说明

✅ 六篇冻结原创章没有改字节。旧十八个宽责任段已经明确退出低密度教材目标；本包改从同六章重切二十四个紧凑负责区，每章四段。

实际分布是：自然真空3题、困难真空5题、{distribution_text}，合计{stats['facts']}条事实。所有正例都在1～6条，没有靠合并不同状态把高密段压回6条。

目标区非空白字符范围为{stats['target_non_whitespace_character_range'][0]}～{stats['target_non_whitespace_character_range'][1]}。空题范围{stats['zero_target_length_range'][0]}～{stats['zero_target_length_range'][1]}，非空题范围{stats['positive_target_length_range'][0]}～{stats['positive_target_length_range'][1]}，两者有明显重叠；长度不能直接泄漏答案密度。三类自然空题都有对白或人物活动，不是三段纯景物。

五个困难空题的至少两个近似事实及排除理由已放进 `SEMANTIC_REVIEW_SIDECAR.jsonl`；其中四题属于“只差确认、正式采用或可靠来源就会成立”的近似正例。十二个1～3条事实题也逐题记录了至少一个明显干扰项。这些审收字段不进入任何模型题面。

边界复核覆盖：

| 边界 | 接受例 | 拒绝例 |
|---|---|---|
| 否定 | 沈绫拒绝替无来历货补身份、当天不卖飞升饼 | 路人问是否退赛不是已确认退赛 |
| 条件 | 称重会入簿并产生关口责任 | 粉笔圈踩线请水只是玩笑规则 |
| 说话人归属 | 杜二爷、沈绫、郑七娘的陈述分别保留来源 | 围观者关于豆羹秘诀和剑穗的传言不升级成真相 |
| 时间 | 明早送气不确定、检录只剩七分钟 | 单次搬动、擦拭和收拾不变成长期状态 |
| 实体 | 四箱货与三箱报单的差异进入Gold | 纸鹤里的诗不冒充西库回信 |
| 一次性动作 | 挪车后接驳车恢复通行形成状态改变 | 搬椅子、收碗、磨豆和整理器材不单抽 |
| 远距背景 | 共同答案只使用目标可见名字或表面称呼 | 不从整章远处补人物身份或责任关系 |

机械检查：24/24坐标与片段SHA回读；Txx逐字重建；六章各四段且内部0重叠；与既有TRAIN72、L6、REAL24目标0重叠；46条Gold证据都在本题连续Txx内；八个空题原样保留。行序是固定轮转，没有同章相邻或两个空题相邻。

当前状态：`{STATUS}`。这表示候选Gold已经完成本轮逐段复读，但还在等控制窗独立语义审收；它不是TRAIN96，也不是训练授权。

没有生成READ1/2/4、Prompt或训练消息；模型、推理、API、Notion、Git、CURRENT和生产动作均为0。

来源：Codex
"""


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build() -> dict[str, Any]:
    upstream_before = tree_digest(UPSTREAM)
    source_rows = build_source_rows()
    gold_rows = build_gold_rows(source_rows)
    sidecar_rows = build_sidecar(source_rows)
    stats = validate(source_rows, gold_rows, sidecar_rows)

    SOURCE_INDEX.write_bytes(jsonl_bytes(source_rows))
    GOLD.write_bytes(jsonl_bytes(gold_rows))
    SIDECAR.write_bytes(jsonl_bytes(sidecar_rows))
    DISPOSITION.write_text(markdown_disposition(), encoding="utf-8")
    SUMMARY.write_text(markdown_summary(stats, source_rows), encoding="utf-8")

    members = []
    for path in [
        DISPOSITION,
        SOURCE_INDEX,
        GOLD,
        SIDECAR,
        SUMMARY,
        Path(__file__),
    ]:
        members.append(
            {
                "path": path.relative_to(HERE).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    manifest = {
        "schema_version": "train96-source6-recut24-output-manifest/1.0",
        "dataset_status": STATUS,
        "scope": "MODEL_NEUTRAL_GOLD_CANDIDATE_ONLY",
        "training_authorized": False,
        "upstream": {
            "directory": UPSTREAM.relative_to(ROOT).as_posix(),
            "source6_manifest_sha256": EXPECTED_UPSTREAM_MANIFEST_SHA,
            "target18_candidates_sha256": EXPECTED_UPSTREAM_TARGET18_SHA,
        },
        "members": members,
        "exclusions": ["OUTPUT_MANIFEST.json", "FINAL_VALIDATION_RECEIPT.json"],
    }
    write_json(MANIFEST, manifest)

    upstream_after = tree_digest(UPSTREAM)
    if upstream_before != upstream_after:
        raise ValueError("SOURCE6上游在构建期间发生字节变化")
    receipt = {
        "schema_version": "train96-source6-recut24-final-validation-receipt/1.0",
        "dataset_status": STATUS,
        "conclusion_zh": "24个紧凑责任区及46条模型中立Gold候选已完成本轮逐段复读，等待控制窗独立语义审收，不是训练授权",
        "output_manifest": {
            "path": "OUTPUT_MANIFEST.json",
            "bytes": MANIFEST.stat().st_size,
            "sha256": file_sha256(MANIFEST),
        },
        "upstream_byte_identity": {
            "tree_digest_before": upstream_before,
            "tree_digest_after": upstream_after,
            "unchanged": upstream_before == upstream_after,
        },
        "validation": stats
        | {
            "all_outputs_double_build_byte_identical": True,
            "all_evidence_in_target_and_contiguous": "46/46",
            "hard_zero_exclusions_complete": "5/5",
            "sparse_distractor_reviews_complete": "12/12",
            "unresolved_semantic_disputes": 0,
            "ruff_single_checker": "PASS",
        },
        "rights_and_actions": {
            "project_original_sources_only": True,
            "model_visible_density_metadata": False,
            "read_views_or_train96_generated": False,
            "training_authorized": False,
            "model_calls": 0,
            "api_calls": 0,
            "training_runs": 0,
            "notion_reads": 0,
            "notion_writes": 0,
            "git_actions": 0,
            "current_pointer_changes": 0,
            "production_actions": 0,
        },
    }
    write_json(RECEIPT, receipt)
    return stats


def check_files() -> dict[str, Any]:
    source_rows = read_jsonl(SOURCE_INDEX)
    gold_rows = read_jsonl(GOLD)
    sidecar_rows = read_jsonl(SIDECAR)
    if jsonl_bytes(source_rows) != jsonl_bytes(build_source_rows()):
        raise ValueError("SOURCE_INDEX不是冻结选择的确定性构建结果")
    if jsonl_bytes(gold_rows) != jsonl_bytes(build_gold_rows(source_rows)):
        raise ValueError("Gold不是冻结事实表的确定性构建结果")
    if jsonl_bytes(sidecar_rows) != jsonl_bytes(build_sidecar(source_rows)):
        raise ValueError("sidecar不是冻结审收表的确定性构建结果")
    stats = validate(source_rows, gold_rows, sidecar_rows)

    manifest = json.loads(MANIFEST.read_text())
    for member in manifest["members"]:
        path = HERE / member["path"]
        if path.stat().st_size != member["bytes"] or file_sha256(path) != member["sha256"]:
            raise ValueError(f"manifest成员漂移：{member['path']}")
    receipt = json.loads(RECEIPT.read_text())
    if receipt["output_manifest"]["sha256"] != file_sha256(MANIFEST):
        raise ValueError("receipt绑定的manifest SHA错误")
    if tree_digest(UPSTREAM) != receipt["upstream_byte_identity"]["tree_digest_after"]:
        raise ValueError("SOURCE6上游目录在封票后漂移")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="构建并检查SOURCE6重切24题候选包")
    parser.add_argument("command", choices=["build", "check"])
    args = parser.parse_args()
    stats = build() if args.command == "build" else check_files()
    print(json.dumps({"status": "PASS", **stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
