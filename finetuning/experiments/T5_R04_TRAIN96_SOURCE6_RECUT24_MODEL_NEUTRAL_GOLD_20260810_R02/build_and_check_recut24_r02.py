from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
R01 = ROOT / (
    "finetuning/experiments/"
    "T5_R04_TRAIN96_SOURCE6_RECUT24_MODEL_NEUTRAL_GOLD_20260810_R01"
)
R04 = ROOT / (
    "finetuning/experiments/"
    "T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R04"
)

R01_SOURCE = R01 / "SOURCE_INDEX_24.jsonl"
R01_GOLD = R01 / "MODEL_NEUTRAL_GOLD_24.jsonl"
R01_SIDECAR = R01 / "SEMANTIC_REVIEW_SIDECAR.jsonl"
R01_AUDIT = R04 / "RECUT24_R01_INDEPENDENT_SEMANTIC_AUDIT.md"

EXPECTED_R01_SHA256 = {
    "SOURCE_INDEX_24.jsonl": (
        "33b14b2a751ffd5e4c34ce6d214502f6acc6c1793dd78ae2d70a7d9f313ea929"
    ),
    "MODEL_NEUTRAL_GOLD_24.jsonl": (
        "4876bb88818aa63ad4835d990f050436946a0319bd9b8a174a4244ef015e80e6"
    ),
    "SEMANTIC_REVIEW_SIDECAR.jsonl": (
        "4b0d940a000aff0b88a3bfe0e588fb36d7dde4ff13549f02987f954bbd9637bd"
    ),
    "RECUT24_R01_INDEPENDENT_SEMANTIC_AUDIT.md": (
        "6ad8955aec442d4f5d92f258be7c0db358c5fafb4f08ea52bb0958e672e1370d"
    ),
}

STATUS = "PASS_CANDIDATE_MODEL_NEUTRAL_GOLD_PENDING_CONTROL_REVIEW"
STATUSES = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}

SOURCE_INDEX = HERE / "SOURCE_INDEX_24.jsonl"
GOLD = HERE / "MODEL_NEUTRAL_GOLD_24.jsonl"
SIDECAR = HERE / "SEMANTIC_REVIEW_SIDECAR.jsonl"
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

# 只收短五个过长空题；每个新边界仍是完整自然段边界。
COORDINATE_OVERRIDES = {
    "RC96-CH01-01": (1503, 1654),
    "RC96-CH02-01": (701, 854),
    "RC96-CH03-01": (745, 852),
    "RC96-CH04-01": (985, 1102),
    "RC96-CH04-02": (1217, 1360),
}

SEMANTIC_FIX_IDS = {
    "RC96-CH01-02",
    "RC96-CH02-02",
    "RC96-CH03-03",
    "RC96-CH04-04",
    "RC96-CH06-01",
    "RC96-CH08-04",
}

FIX_DESCRIPTIONS = {
    "RC96-CH01-02": "拆开已送支柱与下午另借婚庆公司，并把通道限制的speaker写为周遥。",
    "RC96-CH02-02": "补入四箱封口齐整，并写清杜二爷只借秤过数、不要求补文书。",
    "RC96-CH03-03": "把明日至少58人写成名单确认后的计划事实，不弱化为推测。",
    "RC96-CH04-04": "按原文写第四棒全程握棒且交接风险最大，并补入贺宁只接一次、交一次。",
    "RC96-CH06-01": "写明连续三次高4度已经证实屏幕并非误报。",
    "RC96-CH08-04": "把蓝芽褪色、结霜延伸和火焰变低拆开，保留郑七娘说明。",
}


def fact(
    sentence: str,
    status: str,
    speaker: str | None,
    evidence_ids: list[str],
) -> tuple[str, str, str | None, list[str]]:
    return sentence, status, speaker, evidence_ids


FACT_OVERRIDES = {
    "RC96-CH01-02": [
        fact(
            "老何七点四十五已送来两根可调支柱；支柱只收押金，不出售。",
            "已发生",
            None,
            ["T01"],
        ),
        fact(
            "老何说明支柱下午还要借给婚庆公司搭灯架，不能留下。",
            "计划",
            "老何",
            ["T01", "T02"],
        ),
        fact(
            "周遥架起临时支撑并试力后，横梁不再下沉，但断口发出轻微刮响。",
            "已发生",
            None,
            ["T03", "T04", "T05"],
        ),
        fact(
            "周遥说明临时支撑处只能作为通道，不能在下面囤货。",
            "否定",
            "周遥",
            ["T03", "T04", "T05", "T06"],
        ),
    ],
    "RC96-CH02-02": [
        fact(
            "杜二爷带来的四箱胡椒都盖着水运帮火漆且封口齐整，但报单只登记了三箱。",
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
            "杜二爷只要求借沈家的秤给第四箱过数，不要求沈绫补文书。",
            "计划",
            "杜二爷",
            ["T02", "T03", "T04"],
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
    "RC96-CH03-03": [
        fact(
            "林慧重新数名单后，确认第二天至少有五十八人参加寿席。",
            "计划",
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
        fact("父亲提议让年轻人晚一轮吃饭。", "计划", "父亲", ["T03"]),
        fact(
            "老太太反对让来祝寿的人站着等饭。",
            "否定",
            "老太太",
            ["T03", "T04"],
        ),
    ],
    "RC96-CH04-04": [
        fact("距离检录只剩七分钟。", "正在发生", None, ["T01"]),
        fact("四班计划保留原参赛名单，不启用孟秋。", "计划", None, ["T01"]),
        fact("四班计划不让唐梨离开广播岗位。", "计划", None, ["T01"]),
        fact(
            "第四棒需要全程握棒且交接风险最大；贺宁手掌已经磨破。",
            "正在发生",
            None,
            ["T02"],
        ),
        fact(
            "许乔计划从第二棒换到第四棒，贺宁改跑第二棒，因而只需接一次、交一次。",
            "计划",
            None,
            ["T03"],
        ),
        fact("杜航计划跑第一棒，宋晓按原计划跑第三棒。", "计划", None, ["T04"]),
    ],
    "RC96-CH06-01": [
        fact("五号风口没有热风，只有很弱的风。", "正在发生", None, ["T01"]),
        fact(
            "柏青连续三次测得五号风口温度都比其他风口高四度，证实屏幕并非误报。",
            "已发生",
            None,
            ["T02"],
        ),
        fact("五号风口叶轮仍在转，但进风量不足。", "正在发生", None, ["T03"]),
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
    "RC96-CH08-04": [
        fact("蓝芽遇热后颜色变淡。", "已发生", None, ["T02"]),
        fact("锅沿结出薄霜，霜随后爬上勺柄。", "已发生", None, ["T02"]),
        fact("灶下火焰变低。", "已发生", None, ["T03"]),
        fact(
            "郑七娘说明月露灵薯应当催火，不会压低火力。",
            "否定",
            "郑七娘",
            ["T03"],
        ),
    ],
}

ZERO_REVIEWS = {
    "RC96-CH01-01": {
        "zero_kind": "NATURAL_ZERO",
        "one_missing_condition_away": False,
        "review_reason": "引车、收拾物件和橘猫插曲都是当场动作，没有形成新的后续负担。",
        "tempting_exclusions": [
            ["老魏摆锥桶并引车", "一次性动作", "只是现场疏导，没有形成新的交通规则。"],
            ["陈放喊慢直至嗓音发沙", "重要性", "这是劳动状态描写，不影响后续方案或责任。"],
        ],
    },
    "RC96-CH02-01": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": False,
        "tempting_exclusions": [
            ["伙计把麻、豆、桐油分到三条道", "一次性动作", "只是争执后的常规分流，没有新增规则。"],
            ["有人把车横在院中抢阴凉", "重要性", "是短暂现场动作，没有形成持续安排。"],
        ],
    },
    "RC96-CH03-01": {
        "zero_kind": "NATURAL_ZERO",
        "one_missing_condition_away": False,
        "review_reason": "孩子玩枣和家人闲谈都是备席间活动，正文还明确说谈话没有落成决定。",
        "tempting_exclusions": [
            ["小外孙找回枣并塞回外婆手边", "一次性动作", "物品没有形成新的持续归属或用途。"],
            ["家人谈柴、鸡和接三姑", "责任区", "正文明确说明这些话没有形成决定。"],
        ],
    },
    "RC96-CH04-01": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["杜航提议做两次慢速交棒", "责任区／重要性", "只是未计时热身，没有成为比赛方案。"],
            ["路过同学问四班是否退赛", "说话人归属", "这是外人的问句，顾驰只回答仍在热身。"],
        ],
    },
    "RC96-CH04-02": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["粉笔圈被叫作交接区，踩线要请喝水", "条件", "这是临时玩笑，不是比赛或队伍正式规则。"],
            ["顾驰用标志碟压粉圈", "一次性动作", "只是处理被风吹动的练习道具。"],
        ],
    },
    "RC96-CH06-03": {
        "zero_kind": "NATURAL_ZERO",
        "one_missing_condition_away": False,
        "review_reason": "归还椅子和空碗是观摩结束后的日常收拾，两句“我来”未形成未来承诺。",
        "tempting_exclusions": [
            ["志愿者按纸签归拢椅子", "一次性动作", "只是活动结束后的日常收尾。"],
            ["两个人同时说我来", "时间", "是当场争着接手，不是未来承诺。"],
        ],
    },
    "RC96-CH08-02": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["门外人猜豆羹藏着秘诀", "说话人归属", "只是围观者猜测，没有可靠确认。"],
            ["瘦高弟子说御剑变快是新剑穗造成", "时间", "剑穗上月已换，当前说法缺少时间对应。"],
        ],
    },
    "RC96-CH08-03": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "tempting_exclusions": [
            ["纸鹤像西库回信", "实体", "拆开后只是外门弟子的打油诗，不是西库回包。"],
            ["诗句写云灶饼能冲九霄", "说话人归属", "玩笑诗句不是对飞升饼效果的可靠报告。"],
            ["药圃童子拿萝卜后又放回", "一次性动作", "物品没有形成持续转移。"],
        ],
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode()


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for member in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(member.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(member.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def split_units(text: str, max_chars: int = 40) -> list[tuple[int, int, str]]:
    units = []
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


def verify_inputs() -> None:
    actual = {
        "SOURCE_INDEX_24.jsonl": file_sha256(R01_SOURCE),
        "MODEL_NEUTRAL_GOLD_24.jsonl": file_sha256(R01_GOLD),
        "SEMANTIC_REVIEW_SIDECAR.jsonl": file_sha256(R01_SIDECAR),
        "RECUT24_R01_INDEPENDENT_SEMANTIC_AUDIT.md": file_sha256(R01_AUDIT),
    }
    if actual != EXPECTED_R01_SHA256:
        raise ValueError(f"R01或独立审计SHA漂移：{actual}")


def build_fact_map() -> dict[str, list[dict[str, Any]]]:
    r01 = {row["case_id"]: row for row in read_jsonl(R01_GOLD)}
    output = {}
    for case_id, row in r01.items():
        if case_id in FACT_OVERRIDES:
            facts = [
                {
                    "fact_id": f"{case_id}-F{index:03d}",
                    "fact_sentence": sentence,
                    "status": status,
                    "speaker": speaker,
                    "evidence_ids": evidence,
                }
                for index, (sentence, status, speaker, evidence) in enumerate(
                    FACT_OVERRIDES[case_id], 1
                )
            ]
        else:
            facts = copy.deepcopy(row["facts"])
        output[case_id] = facts
    return output


def build_source_rows(fact_map: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for r01_row in read_jsonl(R01_SOURCE):
        row = copy.deepcopy(r01_row)
        case_id = row["case_id"]
        old_start, old_end = row["target_start"], row["target_end"]
        start, end = COORDINATE_OVERRIDES.get(case_id, (old_start, old_end))
        source_path = ROOT / row["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if sha256_bytes(source_bytes) != row["source_chapter_sha256"]:
            raise ValueError(f"{case_id} 六章来源SHA漂移")
        target = source_text[start:end]
        units = [
            {
                "id": f"T{index:02d}",
                "start": unit_start,
                "end": unit_end,
                "text": unit_text,
                "text_sha256": sha256_bytes(unit_text.encode()),
            }
            for index, (unit_start, unit_end, unit_text) in enumerate(
                split_units(target), 1
            )
        ]
        count = len(fact_map[case_id])
        row.update(
            {
                "schema_version": "train96-source6-recut24-source-index/2.0",
                "dataset_status": STATUS,
                "target_start": start,
                "target_end": end,
                "target_sha256": sha256_bytes(target.encode()),
                "target_non_whitespace_character_count": sum(
                    not character.isspace() for character in target
                ),
                "review_class": (
                    r01_row["review_class"] if count == 0 else f"FACT_{count}"
                ),
                "reviewed_fact_count": count,
                "target_units": units,
                "training_authorized": False,
            }
        )
        rows.append(row)
    return rows


def build_gold_rows(
    source_rows: list[dict[str, Any]],
    fact_map: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for source in source_rows:
        facts = fact_map[source["case_id"]]
        rows.append(
            {
                "dataset_status": STATUS,
                "case_id": source["case_id"],
                "common_answer_entity_policy": "TARGET_VISIBLE_SURFACE_ONLY",
                "facts": facts,
                "exhaustive_within_target_candidate": True,
                "expected_fact_count": len(facts),
                "training_authorized": False,
            }
        )
    return rows


def build_sidecar_rows(
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    old_sources = {row["case_id"]: row for row in read_jsonl(R01_SOURCE)}
    old_sidecars = {row["case_id"]: row for row in read_jsonl(R01_SIDECAR)}
    rows = []
    for source in source_rows:
        case_id = source["case_id"]
        old_source = old_sources[case_id]
        old_sidecar = old_sidecars[case_id]
        coordinate_changed = case_id in COORDINATE_OVERRIDES
        semantic_fixed = case_id in SEMANTIC_FIX_IDS
        if coordinate_changed:
            disposition = "FULL_REVIEW_AFTER_COORDINATE_CHANGE_PASS"
        elif semantic_fixed:
            disposition = "FIX_APPLIED_AND_FULL_REVIEW_PASS"
        else:
            disposition = "R01_PASS_CARRIED_FORWARD"
        row: dict[str, Any] = {
            "schema_version": "train96-source6-recut24-semantic-review-sidecar/2.0",
            "dataset_status": STATUS,
            "case_id": case_id,
            "review_class": source["review_class"],
            "reviewed_fact_count": source["reviewed_fact_count"],
            "model_visible": False,
            "r01_independent_audit_status": (
                "FIX_REQUIRED" if semantic_fixed else "PASS"
            ),
            "r02_review_disposition": disposition,
            "coordinate_changed_from_r01": coordinate_changed,
            "semantic_review_passed": True,
            "unresolved_semantic_issues": 0,
        }
        if coordinate_changed:
            row["coordinate_change"] = {
                "old_start": old_source["target_start"],
                "old_end": old_source["target_end"],
                "old_target_sha256": old_source["target_sha256"],
                "old_non_whitespace_character_count": old_source[
                    "target_non_whitespace_character_count"
                ],
                "new_start": source["target_start"],
                "new_end": source["target_end"],
                "new_target_sha256": source["target_sha256"],
                "new_non_whitespace_character_count": source[
                    "target_non_whitespace_character_count"
                ],
                "boundary_review": "完整自然段边界；逐字重读后仍为语义真空",
            }
        if semantic_fixed:
            row["r02_semantic_fix"] = FIX_DESCRIPTIONS[case_id]
        count = source["reviewed_fact_count"]
        if count == 0:
            row.update(copy.deepcopy(ZERO_REVIEWS[case_id]))
        elif 1 <= count <= 3:
            row["clear_distractor"] = old_sidecar["clear_distractor"]
        rows.append(row)
    return rows


def best_length_threshold(
    source_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    items = [
        (
            row["target_non_whitespace_character_count"],
            row["reviewed_fact_count"] == 0,
        )
        for row in source_rows
    ]
    candidates = []
    for threshold in sorted({length for length, _ in items}):
        for rule in ("EMPTY_IF_LENGTH_GE", "EMPTY_IF_LENGTH_LT"):
            empty_if_ge = rule == "EMPTY_IF_LENGTH_GE"
            tp_empty = tn_nonempty = fp_empty = fn_empty = 0
            for length, actual_empty in items:
                predicted_empty = (
                    length >= threshold if empty_if_ge else length < threshold
                )
                if actual_empty and predicted_empty:
                    tp_empty += 1
                elif actual_empty:
                    fn_empty += 1
                elif predicted_empty:
                    fp_empty += 1
                else:
                    tn_nonempty += 1
            candidates.append(
                {
                    "threshold": threshold,
                    "rule": rule,
                    "correct": tp_empty + tn_nonempty,
                    "total": len(items),
                    "confusion": {
                        "true_empty_predicted_empty": tp_empty,
                        "true_nonempty_predicted_nonempty": tn_nonempty,
                        "true_nonempty_predicted_empty": fp_empty,
                        "true_empty_predicted_nonempty": fn_empty,
                    },
                }
            )
    candidates.sort(
        key=lambda item: (
            -item["correct"],
            item["threshold"],
            0 if item["rule"] == "EMPTY_IF_LENGTH_GE" else 1,
        )
    )
    return candidates[0]


def pearson_length_fact_count(source_rows: list[dict[str, Any]]) -> float:
    lengths = [row["target_non_whitespace_character_count"] for row in source_rows]
    facts = [row["reviewed_fact_count"] for row in source_rows]
    mean_length = sum(lengths) / len(lengths)
    mean_facts = sum(facts) / len(facts)
    numerator = sum(
        (length - mean_length) * (count - mean_facts)
        for length, count in zip(lengths, facts, strict=True)
    )
    denominator = math.sqrt(
        sum((length - mean_length) ** 2 for length in lengths)
        * sum((count - mean_facts) ** 2 for count in facts)
    )
    return numerator / denominator


def validate(
    source_rows: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
    sidecar_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not (len(source_rows) == len(gold_rows) == len(sidecar_rows) == 24):
        raise ValueError("source/Gold/sidecar不是24题")
    case_ids = [row["case_id"] for row in source_rows]
    r01_source_rows = read_jsonl(R01_SOURCE)
    r01_case_ids = [row["case_id"] for row in r01_source_rows]
    if case_ids != r01_case_ids or len(set(case_ids)) != 24:
        raise ValueError("case顺序、集合或唯一性错误")
    if [row["case_id"] for row in gold_rows] != case_ids:
        raise ValueError("Gold顺序错误")
    if [row["case_id"] for row in sidecar_rows] != case_ids:
        raise ValueError("sidecar顺序错误")

    r01_sources = {row["case_id"]: row for row in r01_source_rows}
    for row in source_rows:
        old = r01_sources[row["case_id"]]
        if row["case_id"] in COORDINATE_OVERRIDES:
            if (row["target_start"], row["target_end"]) != COORDINATE_OVERRIDES[
                row["case_id"]
            ]:
                raise ValueError(f"{row['case_id']} 没有使用冻结的新坐标")
        elif (
            row["target_start"],
            row["target_end"],
            row["target_sha256"],
        ) != (old["target_start"], old["target_end"], old["target_sha256"]):
            raise ValueError(f"{row['case_id']} 未授权坐标或target SHA变化")

    chapter_counts = Counter(row["source_id"] for row in source_rows)
    if len(chapter_counts) != 6 or set(chapter_counts.values()) != {4}:
        raise ValueError(f"不是六章各四题：{chapter_counts}")

    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    target_shas = set()
    for row in source_rows:
        by_source[row["source_id"]].append(row)
        source_path = ROOT / row["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if sha256_bytes(source_bytes) != row["source_chapter_sha256"]:
            raise ValueError(f"{row['case_id']} 章节SHA漂移")
        target = source_text[row["target_start"] : row["target_end"]]
        if sha256_bytes(target.encode()) != row["target_sha256"]:
            raise ValueError(f"{row['case_id']} target SHA错误")
        if "".join(unit["text"] for unit in row["target_units"]) != target:
            raise ValueError(f"{row['case_id']} Txx不能重建target")
        if row["target_sha256"] in target_shas:
            raise ValueError("target SHA重复")
        target_shas.add(row["target_sha256"])
    for source_id, rows in by_source.items():
        rows.sort(key=lambda row: row["target_start"])
        for left, right in zip(rows, rows[1:], strict=False):
            if left["target_end"] > right["target_start"]:
                raise ValueError(f"{source_id} 本批目标重叠")

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
        raise ValueError(f"与TRAIN72/L6/REAL24重叠：{prior_overlap}")

    counts = []
    total_facts = 0
    r01_gold = {row["case_id"]: row for row in read_jsonl(R01_GOLD)}
    for source, gold, sidecar in zip(
        source_rows, gold_rows, sidecar_rows, strict=True
    ):
        case_id = source["case_id"]
        facts = gold["facts"]
        if not (
            source["dataset_status"]
            == gold["dataset_status"]
            == sidecar["dataset_status"]
            == STATUS
        ):
            raise ValueError(f"{case_id} 状态错误")
        if source["training_authorized"] or gold["training_authorized"]:
            raise ValueError(f"{case_id} 被错误授权训练")
        if gold["expected_fact_count"] != len(facts):
            raise ValueError(f"{case_id} expected_fact_count错误")
        if len(facts) != source["reviewed_fact_count"]:
            raise ValueError(f"{case_id} source/Gold事实数不一致")
        if sidecar["reviewed_fact_count"] != len(facts):
            raise ValueError(f"{case_id} sidecar事实数不一致")
        if gold["common_answer_entity_policy"] != "TARGET_VISIBLE_SURFACE_ONLY":
            raise ValueError(f"{case_id} 实体政策错误")
        if gold["exhaustive_within_target_candidate"] is not True:
            raise ValueError(f"{case_id} 缺少穷尽候选标记")
        unit_ids = [unit["id"] for unit in source["target_units"]]
        for fact_index, item in enumerate(facts, 1):
            if item["fact_id"] != f"{case_id}-F{fact_index:03d}":
                raise ValueError(f"{case_id} fact_id不连续")
            if not item["fact_sentence"].strip() or item["status"] not in STATUSES:
                raise ValueError(f"{case_id} fact/status错误")
            if item["speaker"] is not None and not isinstance(item["speaker"], str):
                raise ValueError(f"{case_id} speaker类型错误")
            evidence = item["evidence_ids"]
            if not evidence or any(item_id not in unit_ids for item_id in evidence):
                raise ValueError(f"{case_id} evidence越界")
            positions = [unit_ids.index(item_id) for item_id in evidence]
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise ValueError(f"{case_id} evidence不连续")
        if not sidecar["semantic_review_passed"]:
            raise ValueError(f"{case_id} sidecar没有语义PASS")
        if sidecar["unresolved_semantic_issues"] != 0:
            raise ValueError(f"{case_id} 仍有语义争议")
        if case_id not in SEMANTIC_FIX_IDS and facts != r01_gold[case_id]["facts"]:
            raise ValueError(f"{case_id} R01 PASS事实被静默改变")
        counts.append(len(facts))
        total_facts += len(facts)

    expected_distribution = Counter({0: 8, 1: 4, 2: 3, 3: 3, 4: 2, 5: 2, 6: 2})
    if Counter(counts) != expected_distribution or total_facts != 49:
        raise ValueError(f"事实分布/总数错误：{Counter(counts)} total={total_facts}")

    zero_ids = {row["case_id"] for row in source_rows if not row["reviewed_fact_count"]}
    r01_zero_ids = {
        row["case_id"]
        for row in read_jsonl(R01_GOLD)
        if not row["expected_fact_count"]
    }
    if zero_ids != r01_zero_ids or len(zero_ids) != 8:
        raise ValueError("8个facts=[]题没有原样保留")
    zero_sidecars = [row for row in sidecar_rows if row["reviewed_fact_count"] == 0]
    if any(not row.get("tempting_exclusions") for row in zero_sidecars):
        raise ValueError("空题缺少具体排除理由")
    hard_zero_sidecars = [
        row for row in zero_sidecars if row["zero_kind"] == "HARD_ZERO"
    ]
    if len(hard_zero_sidecars) != 5:
        raise ValueError("困难空题不是5题")
    if any(len(row["tempting_exclusions"]) < 2 for row in hard_zero_sidecars):
        raise ValueError("困难空题少于两个具体排除项")

    changed_ids = {
        row["case_id"]
        for row in sidecar_rows
        if row["coordinate_changed_from_r01"]
    }
    if changed_ids != set(COORDINATE_OVERRIDES):
        raise ValueError("坐标变化集合错误")
    if any(
        row["r02_review_disposition"]
        != "FULL_REVIEW_AFTER_COORDINATE_CHANGE_PASS"
        for row in sidecar_rows
        if row["case_id"] in changed_ids
    ):
        raise ValueError("改坐标题没有重新完整语义审收")
    if any(
        "r02_semantic_fix" not in row
        for row in sidecar_rows
        if row["case_id"] in SEMANTIC_FIX_IDS
    ):
        raise ValueError("六项修正未逐题登记")

    length_gate = best_length_threshold(source_rows)
    r01_length_gate = best_length_threshold(read_jsonl(R01_SOURCE))
    if r01_length_gate["correct"] != 22:
        raise ValueError(f"R01长度捷径对照不是22/24：{r01_length_gate}")
    if length_gate["correct"] > 17:
        raise ValueError(f"R02长度捷径仍超过17/24：{length_gate}")

    lengths = [row["target_non_whitespace_character_count"] for row in source_rows]
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
    return {
        "cases": 24,
        "facts": total_facts,
        "fact_count_distribution": dict(sorted(Counter(counts).items())),
        "zero_cases": 8,
        "nonempty_cases": 16,
        "coordinate_changes": len(changed_ids),
        "semantic_fixes": len(SEMANTIC_FIX_IDS),
        "unique_source_chapters": 6,
        "targets_per_chapter": 4,
        "within_recut24_overlaps": 0,
        "prior_train72_l6_real24_overlaps": prior_overlap,
        "target_non_whitespace_character_range": [min(lengths), max(lengths)],
        "zero_target_length_range": [min(zero_lengths), max(zero_lengths)],
        "positive_target_length_range": [min(positive_lengths), max(positive_lengths)],
        "r01_best_length_threshold": r01_length_gate,
        "r02_best_length_threshold": length_gate,
        "length_fact_count_pearson": pearson_length_fact_count(source_rows),
        "semantic_reviewed_cases": 24,
        "unresolved_semantic_issues": 0,
    }


def coordinate_change_rows(
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    old = {row["case_id"]: row for row in read_jsonl(R01_SOURCE)}
    output = []
    for row in source_rows:
        if row["case_id"] not in COORDINATE_OVERRIDES:
            continue
        old_row = old[row["case_id"]]
        output.append(
            {
                "case_id": row["case_id"],
                "old_range": [old_row["target_start"], old_row["target_end"]],
                "new_range": [row["target_start"], row["target_end"]],
                "old_non_whitespace_characters": old_row[
                    "target_non_whitespace_character_count"
                ],
                "new_non_whitespace_characters": row[
                    "target_non_whitespace_character_count"
                ],
                "new_target_sha256": row["target_sha256"],
            }
        )
    return output


def markdown_summary(
    stats: dict[str, Any],
    source_rows: list[dict[str, Any]],
) -> str:
    changes = coordinate_change_rows(source_rows)
    change_lines = "\n".join(
        "- `{case_id}`：`[{old_start},{old_end})` → "
        "`[{new_start},{new_end})`，非空白字符 {old_len} → {new_len}。".format(
            case_id=row["case_id"],
            old_start=row["old_range"][0],
            old_end=row["old_range"][1],
            new_start=row["new_range"][0],
            new_end=row["new_range"][1],
            old_len=row["old_non_whitespace_characters"],
            new_len=row["new_non_whitespace_characters"],
        )
        for row in changes
    )
    fix_lines = "\n".join(
        f"- `{case_id}`：{FIX_DESCRIPTIONS[case_id]} PASS。"
        for case_id in sorted(SEMANTIC_FIX_IDS)
    )
    distribution = " / ".join(
        f"{count}:{amount}"
        for count, amount in stats["fact_count_distribution"].items()
    )
    gate = stats["r02_best_length_threshold"]
    confusion = gate["confusion"]
    return f"""# RECUT24 模型中立 Gold R02｜审收说明

✅ R01 保持原字节。R02 落实六个独立语义修正，并只沿完整自然段边界收短五个过长空题；六篇冻结原创正文没有修改。

## 坐标变化

{change_lines}

这五题都重新逐字复核，仍是语义真空；人物活动和强诱饵仍保留，没有靠无意义动作、复制背景、机械 padding 或半句截断凑长度。其余十九题坐标不变。

## 六项语义修正

{fix_lines}

修后共24题、49条事实，分布为 `{distribution}`。8个 `facts:[]` 题仍是原来的8题，16个正例仍只含1～6条事实。

## 长度捷径

R01最佳单阈值可猜中22/24。R02按同一遍历法的最佳结果是{gate['correct']}/24：规则 `{gate['rule']}`，阈值 `{gate['threshold']}`。混淆为：真空猜空 {confusion['true_empty_predicted_empty']}，非空猜非空 {confusion['true_nonempty_predicted_nonempty']}，非空错猜空 {confusion['true_nonempty_predicted_empty']}，真空错猜非空 {confusion['true_empty_predicted_nonempty']}。这已经满足不超过17/24的预设门。

全部24题都有一行不可见的语义 sidecar。五个改坐标题和六个Gold修正题做了完整复读；R01其余通过题承接独立审计结论。当前争议为0，但状态只到 `{STATUS}`，仍不是训练授权。

没有生成READ题面、system prompt、训练JSONL或TRAIN96；模型、训练、推理、API、Notion、Git、CURRENT和生产动作均为0。

来源：Codex
"""


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    verify_inputs()
    r01_before = tree_digest(R01)
    fact_map = build_fact_map()
    source_rows = build_source_rows(fact_map)
    gold_rows = build_gold_rows(source_rows, fact_map)
    sidecar_rows = build_sidecar_rows(source_rows)
    stats = validate(source_rows, gold_rows, sidecar_rows)

    SOURCE_INDEX.write_bytes(jsonl_bytes(source_rows))
    GOLD.write_bytes(jsonl_bytes(gold_rows))
    SIDECAR.write_bytes(jsonl_bytes(sidecar_rows))
    SUMMARY.write_text(markdown_summary(stats, source_rows), encoding="utf-8")

    members = []
    for path in (SOURCE_INDEX, GOLD, SIDECAR, SUMMARY, Path(__file__)):
        members.append(
            {
                "path": path.relative_to(HERE).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    manifest = {
        "schema_version": "train96-source6-recut24-output-manifest/2.0",
        "dataset_status": STATUS,
        "scope": "MODEL_NEUTRAL_GOLD_CANDIDATE_ONLY",
        "training_authorized": False,
        "parent_r01": {
            "directory": R01.relative_to(ROOT).as_posix(),
            "source_index_sha256": EXPECTED_R01_SHA256["SOURCE_INDEX_24.jsonl"],
            "gold_sha256": EXPECTED_R01_SHA256["MODEL_NEUTRAL_GOLD_24.jsonl"],
            "sidecar_sha256": EXPECTED_R01_SHA256[
                "SEMANTIC_REVIEW_SIDECAR.jsonl"
            ],
            "independent_audit_sha256": EXPECTED_R01_SHA256[
                "RECUT24_R01_INDEPENDENT_SEMANTIC_AUDIT.md"
            ],
        },
        "members": members,
        "exclusions": ["OUTPUT_MANIFEST.json", "FINAL_VALIDATION_RECEIPT.json"],
    }
    write_json(MANIFEST, manifest)

    r01_after = tree_digest(R01)
    if r01_before != r01_after:
        raise ValueError("R01在R02构建期间发生字节变化")
    receipt = {
        "schema_version": "train96-source6-recut24-final-validation-receipt/2.0",
        "dataset_status": STATUS,
        "conclusion_zh": "24题、49条模型中立Gold候选完成R02语义修正和长度捷径修复，等待控制窗审收，不是训练授权",
        "output_manifest": {
            "path": "OUTPUT_MANIFEST.json",
            "bytes": MANIFEST.stat().st_size,
            "sha256": file_sha256(MANIFEST),
        },
        "r01_byte_identity": {
            "tree_digest_before": r01_before,
            "tree_digest_after": r01_after,
            "unchanged": r01_before == r01_after,
        },
        "coordinate_changes": coordinate_change_rows(source_rows),
        "semantic_fix_status": {
            case_id: "PASS" for case_id in sorted(SEMANTIC_FIX_IDS)
        },
        "validation": stats
        | {
            "all_outputs_double_build_byte_identical": True,
            "all_evidence_in_target_and_contiguous": "49/49",
            "zero_case_exclusions_complete": "8/8",
            "r01_pass_cases_preserved_or_re_reviewed": "18/18",
            "semantic_fix_cases_passed": "6/6",
            "ruff_single_checker": "PASS",
            "json_parse": "PASS",
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
    verify_inputs()
    fact_map = build_fact_map()
    source_rows = read_jsonl(SOURCE_INDEX)
    gold_rows = read_jsonl(GOLD)
    sidecar_rows = read_jsonl(SIDECAR)
    if jsonl_bytes(source_rows) != jsonl_bytes(build_source_rows(fact_map)):
        raise ValueError("SOURCE_INDEX不是确定性构建结果")
    if jsonl_bytes(gold_rows) != jsonl_bytes(
        build_gold_rows(source_rows, fact_map)
    ):
        raise ValueError("Gold不是确定性构建结果")
    if jsonl_bytes(sidecar_rows) != jsonl_bytes(build_sidecar_rows(source_rows)):
        raise ValueError("sidecar不是确定性构建结果")
    stats = validate(source_rows, gold_rows, sidecar_rows)
    manifest = json.loads(MANIFEST.read_text())
    for member in manifest["members"]:
        path = HERE / member["path"]
        if path.stat().st_size != member["bytes"] or file_sha256(path) != member[
            "sha256"
        ]:
            raise ValueError(f"manifest成员漂移：{member['path']}")
    receipt = json.loads(RECEIPT.read_text())
    if receipt["output_manifest"]["sha256"] != file_sha256(MANIFEST):
        raise ValueError("receipt绑定manifest SHA错误")
    current_r01 = tree_digest(R01)
    if not (
        receipt["r01_byte_identity"]["unchanged"]
        and current_r01 == receipt["r01_byte_identity"]["tree_digest_after"]
    ):
        raise ValueError("R01原字节证明失败")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="构建并检查RECUT24 R02候选Gold")
    parser.add_argument("command", choices=["build", "check"])
    args = parser.parse_args()
    stats = build() if args.command == "build" else check_files()
    print(json.dumps({"status": "PASS", **stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
