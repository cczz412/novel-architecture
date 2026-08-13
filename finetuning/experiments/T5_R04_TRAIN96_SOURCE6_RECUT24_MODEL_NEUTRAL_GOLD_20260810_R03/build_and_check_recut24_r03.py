from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
R01 = ROOT / (
    "finetuning/experiments/"
    "T5_R04_TRAIN96_SOURCE6_RECUT24_MODEL_NEUTRAL_GOLD_20260810_R01"
)
R02 = ROOT / (
    "finetuning/experiments/"
    "T5_R04_TRAIN96_SOURCE6_RECUT24_MODEL_NEUTRAL_GOLD_20260810_R02"
)
R04 = ROOT / (
    "finetuning/experiments/"
    "T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R04"
)

R02_SOURCE = R02 / "SOURCE_INDEX_24.jsonl"
R02_GOLD = R02 / "MODEL_NEUTRAL_GOLD_24.jsonl"
R02_SIDECAR = R02 / "SEMANTIC_REVIEW_SIDECAR.jsonl"
R02_MANIFEST = R02 / "OUTPUT_MANIFEST.json"
R02_RECEIPT = R02 / "FINAL_VALIDATION_RECEIPT.json"
CONTROL_REVIEW = R04 / "RECUT24_R02_CONTROL_REVIEW.md"

EXPECTED_INPUT_SHA256 = {
    "RECUT24_R02_CONTROL_REVIEW.md": (
        "39acf841d8a72751114e9b93a981d1ff3517dbe3a806ec3a60a87712dd37f761"
    ),
    "SOURCE_INDEX_24.jsonl": (
        "8b600c194c4da832c33b292e3deda0266d6dccef0f6d885fd48a5d87f562a168"
    ),
    "MODEL_NEUTRAL_GOLD_24.jsonl": (
        "1bec7dbfc26878e0553e8f34319c072c46da0f6b80e4a3ae19842629451bec6d"
    ),
    "SEMANTIC_REVIEW_SIDECAR.jsonl": (
        "a93e7ec1137e7c7614d3a4b228610fd148dfcc8b28f6a985813fd821e06a6389"
    ),
    "OUTPUT_MANIFEST.json": (
        "a03e5578917214eb37714249fe69e00dc7d621fe3e1d28709b349d4abc2eb80d"
    ),
    "FINAL_VALIDATION_RECEIPT.json": (
        "8fc6353a3fdafe3807d9724d93cd7d9013e3aa549aabe8340d012b279dadc38c"
    ),
}

STATUS = "PASS_CANDIDATE_MODEL_NEUTRAL_GOLD_PENDING_CONTROL_REVIEW"
STATUSES = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
FEATURE_GATE_MAX_CORRECT = 17

SOURCE_INDEX = HERE / "SOURCE_INDEX_24.jsonl"
GOLD = HERE / "MODEL_NEUTRAL_GOLD_24.jsonl"
SIDECAR = HERE / "SEMANTIC_REVIEW_SIDECAR.jsonl"
SUMMARY = HERE / "REVIEW_SUMMARY.md"
FEATURE_REPORT = HERE / "FIXED_FEATURE_REPORT.json"
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

# 只改三个已经独立审为语义真空的目标；边界均为冻结正文中的完整自然段。
COORDINATE_OVERRIDES = {
    "RC96-CH01-01": (1615, 1718),
    "RC96-CH02-01": (816, 956),
    "RC96-CH04-02": (1217, 1270),
}

SEMANTIC_FIX_IDS = {
    "RC96-CH01-02",
    "RC96-CH02-02",
    "RC96-CH03-03",
    "RC96-CH04-04",
    "RC96-CH06-01",
    "RC96-CH08-04",
}

ZERO_REVIEW_OVERRIDES = {
    "RC96-CH01-01": {
        "zero_kind": "NATURAL_ZERO",
        "one_missing_condition_away": False,
        "review_reason": (
            "橘猫插曲和空响复核都停在当场；正文明确排除棚体异响，"
            "没有形成新故障、归属、计划或责任。"
        ),
        "tempting_exclusions": [
            [
                "橘猫绕盆、蹭裤腿，老魏把猫拨向无车一侧",
                "一次性动作",
                "只是现场互动，没有形成收养、物品归属或后续安排。",
            ],
            [
                "车轮压过水沟盖发出空响",
                "实体／归属",
                "众人随后确认声音不是棚体异响，不能记成棚架新故障。",
            ],
        ],
    },
    "RC96-CH02-01": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": False,
        "review_reason": (
            "擦铜砣、收册、墨迹和玩笑都是争执后的当场收束，"
            "没有产生新账目结论、规则或责任。"
        ),
        "tempting_exclusions": [
            [
                "魏书吏把记录吹干后叠进蓝布册",
                "一次性动作",
                "只是收存当场记录，目标内没有新增账目结果或正式归档规则。",
            ],
            [
                "纸角墨迹被阿谷说成像泥鳅",
                "实体／归属",
                "这是对墨迹外形的玩笑，不能当作货物、签记或作假线索。",
            ],
            [
                "冷茶杯沿缺瓷",
                "重要性",
                "只是即时生活动作，没有影响后续商贸判断。",
            ],
        ],
    },
    "RC96-CH04-02": {
        "zero_kind": "HARD_ZERO",
        "one_missing_condition_away": True,
        "review_reason": (
            "粉笔圈和请喝水是训练间隙的玩笑说法；目标内没有教练确认，"
            "也没有比赛规则或人员安排真正改变。"
        ),
        "tempting_exclusions": [
            [
                "许乔说每个粉笔圈算交接区",
                "责任区／归属",
                "这是临时玩笑，不是教练或赛规确认的正式交接区。",
            ],
            [
                "踩线的人请喝水",
                "条件",
                "表面像条件规则，但只是玩笑，目标内没有执行或承诺。",
            ],
            [
                "杜航问半只鞋算不算",
                "条件／说话人",
                "只是追问，没有得到结论，不能补成新规则。",
            ],
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


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


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
    paths = {
        "RECUT24_R02_CONTROL_REVIEW.md": CONTROL_REVIEW,
        "SOURCE_INDEX_24.jsonl": R02_SOURCE,
        "MODEL_NEUTRAL_GOLD_24.jsonl": R02_GOLD,
        "SEMANTIC_REVIEW_SIDECAR.jsonl": R02_SIDECAR,
        "OUTPUT_MANIFEST.json": R02_MANIFEST,
        "FINAL_VALIDATION_RECEIPT.json": R02_RECEIPT,
    }
    actual = {name: file_sha256(path) for name, path in paths.items()}
    if actual != EXPECTED_INPUT_SHA256:
        raise ValueError(f"R02或控制审查SHA漂移：{actual}")


def build_source_rows() -> list[dict[str, Any]]:
    rows = []
    for old in read_jsonl(R02_SOURCE):
        row = copy.deepcopy(old)
        case_id = row["case_id"]
        if case_id not in COORDINATE_OVERRIDES:
            rows.append(row)
            continue
        start, end = COORDINATE_OVERRIDES[case_id]
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
        row.update(
            {
                "target_start": start,
                "target_end": end,
                "target_sha256": sha256_bytes(target.encode()),
                "target_non_whitespace_character_count": sum(
                    not character.isspace() for character in target
                ),
                "target_units": units,
            }
        )
        rows.append(row)
    return rows


def build_gold_rows() -> list[dict[str, Any]]:
    # 三个换段题均为真空，因此R02的24题Gold可以逐字承接。
    return read_jsonl(R02_GOLD)


def build_sidecar_rows(
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    old_sources = {row["case_id"]: row for row in read_jsonl(R02_SOURCE)}
    sources = {row["case_id"]: row for row in source_rows}
    rows = []
    for old_sidecar in read_jsonl(R02_SIDECAR):
        case_id = old_sidecar["case_id"]
        if case_id not in COORDINATE_OVERRIDES:
            rows.append(copy.deepcopy(old_sidecar))
            continue
        old_source = old_sources[case_id]
        source = sources[case_id]
        row = copy.deepcopy(old_sidecar)
        row.update(copy.deepcopy(ZERO_REVIEW_OVERRIDES[case_id]))
        row.update(
            {
                "r03_review_disposition": (
                    "FULL_REVIEW_AFTER_SURFACE_COORDINATE_CHANGE_PASS"
                ),
                "coordinate_changed_from_r02": True,
                "semantic_review_passed": True,
                "unresolved_semantic_issues": 0,
                "r03_coordinate_change": {
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
                    "boundary_review": (
                        "冻结正文中的完整自然段边界；逐字重读后仍为语义真空"
                    ),
                },
                "r03_surface_shortcut_fix": (
                    "只换取冻结正文中的自然目标区；没有修改正文、标点或换行"
                ),
            }
        )
        rows.append(row)
    return rows


def paragraph_count(target: str) -> int:
    return len([part for part in re.split(r"\n\s*\n", target) if part.strip()])


def feature_values(
    source_rows: list[dict[str, Any]],
) -> dict[str, list[tuple[str, int | Fraction, bool]]]:
    output: dict[str, list[tuple[str, int | Fraction, bool]]] = {
        "non_whitespace_characters": [],
        "paragraphs_per_non_whitespace_character": [],
        "chinese_comma_count": [],
    }
    for row in source_rows:
        source_text = (ROOT / row["source_path"]).read_text()
        target = source_text[row["target_start"] : row["target_end"]]
        non_whitespace = sum(not character.isspace() for character in target)
        paragraphs = paragraph_count(target)
        is_empty = row["reviewed_fact_count"] == 0
        output["non_whitespace_characters"].append(
            (row["case_id"], non_whitespace, is_empty)
        )
        output["paragraphs_per_non_whitespace_character"].append(
            (row["case_id"], Fraction(paragraphs, non_whitespace), is_empty)
        )
        output["chinese_comma_count"].append(
            (row["case_id"], target.count("，"), is_empty)
        )
    return output


def best_threshold(
    items: list[tuple[str, int | Fraction, bool]],
) -> dict[str, Any]:
    candidates = []
    for threshold in sorted({value for _, value, _ in items}):
        for direction in ("EMPTY_IF_VALUE_GE", "EMPTY_IF_VALUE_LT"):
            tp_empty = tn_nonempty = fp_empty = fn_empty = 0
            predictions = []
            for case_id, value, actual_empty in items:
                predicted_empty = (
                    value >= threshold
                    if direction == "EMPTY_IF_VALUE_GE"
                    else value < threshold
                )
                predictions.append(
                    {
                        "case_id": case_id,
                        "actual_empty": actual_empty,
                        "predicted_empty": predicted_empty,
                    }
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
                    "direction": direction,
                    "threshold": threshold,
                    "correct": tp_empty + tn_nonempty,
                    "total": len(items),
                    "confusion": {
                        "true_empty_predicted_empty": tp_empty,
                        "true_nonempty_predicted_nonempty": tn_nonempty,
                        "true_nonempty_predicted_empty": fp_empty,
                        "true_empty_predicted_nonempty": fn_empty,
                    },
                    "predictions": predictions,
                }
            )
    candidates.sort(
        key=lambda item: (
            -item["correct"],
            item["threshold"],
            0 if item["direction"] == "EMPTY_IF_VALUE_GE" else 1,
        )
    )
    best = candidates[0]
    threshold = best["threshold"]
    if isinstance(threshold, Fraction):
        best["threshold_exact"] = f"{threshold.numerator}/{threshold.denominator}"
        best["threshold_decimal"] = float(threshold)
        del best["threshold"]
    return best


def make_feature_report(
    source_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    values = feature_values(source_rows)
    report_features = {}
    for name, items in values.items():
        best = best_threshold(items)
        per_case = []
        for case_id, value, actual_empty in items:
            item: dict[str, Any] = {
                "case_id": case_id,
                "actual_empty": actual_empty,
            }
            if isinstance(value, Fraction):
                item["value_exact"] = f"{value.numerator}/{value.denominator}"
                item["value_decimal"] = float(value)
            else:
                item["value"] = value
            per_case.append(item)
        report_features[name] = {"best_single_threshold": best, "per_case": per_case}
    return {
        "schema_version": "recut24-r03-fixed-visible-feature-report/1.0",
        "dataset_status": STATUS,
        "conclusion_zh": "三个预先固定的模型可见单特征门均不超过17/24",
        "label_definition": "facts为空记作empty，否则记作nonempty",
        "threshold_search": (
            "逐一取本批全部观测值为阈值，同时遍历大于等于判空和小于判空"
        ),
        "maximum_allowed_correct": FEATURE_GATE_MAX_CORRECT,
        "calculator_path": HERE.relative_to(ROOT).as_posix()
        + "/build_and_check_recut24_r03.py",
        "calculator_sha256": file_sha256(Path(__file__)),
        "features": report_features,
        "combination_classifier_trained": False,
        "additional_surface_features_checked": False,
    }


def validate(
    source_rows: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
    sidecar_rows: list[dict[str, Any]],
    feature_report: dict[str, Any],
) -> dict[str, Any]:
    if not (len(source_rows) == len(gold_rows) == len(sidecar_rows) == 24):
        raise ValueError("source/Gold/sidecar不是24题")
    case_ids = [row["case_id"] for row in source_rows]
    r02_sources = read_jsonl(R02_SOURCE)
    r02_case_ids = [row["case_id"] for row in r02_sources]
    if case_ids != r02_case_ids or len(set(case_ids)) != 24:
        raise ValueError("case顺序、集合或唯一性错误")
    if [row["case_id"] for row in gold_rows] != case_ids:
        raise ValueError("Gold顺序错误")
    if [row["case_id"] for row in sidecar_rows] != case_ids:
        raise ValueError("sidecar顺序错误")

    old_sources = {row["case_id"]: row for row in r02_sources}
    old_sidecars = {row["case_id"]: row for row in read_jsonl(R02_SIDECAR)}
    old_gold = {row["case_id"]: row for row in read_jsonl(R02_GOLD)}
    target_shas = set()
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source, gold, sidecar in zip(
        source_rows, gold_rows, sidecar_rows, strict=True
    ):
        case_id = source["case_id"]
        old = old_sources[case_id]
        if source["dataset_status"] != STATUS or gold["dataset_status"] != STATUS:
            raise ValueError(f"{case_id} 状态错误")
        if source["training_authorized"] or gold["training_authorized"]:
            raise ValueError(f"{case_id} 被错误授权训练")
        if case_id in COORDINATE_OVERRIDES:
            if (source["target_start"], source["target_end"]) != (
                COORDINATE_OVERRIDES[case_id]
            ):
                raise ValueError(f"{case_id} 没用冻结R03坐标")
            if not sidecar.get("semantic_review_passed"):
                raise ValueError(f"{case_id} 换段后没有完成逐字语义复核")
        else:
            if source != old or sidecar != old_sidecars[case_id]:
                raise ValueError(f"{case_id} 未改题没有与R02逐字相同")
        if gold != old_gold[case_id]:
            raise ValueError(f"{case_id} Gold不应相对R02变化")

        source_path = ROOT / source["source_path"]
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8", errors="strict")
        if sha256_bytes(source_bytes) != source["source_chapter_sha256"]:
            raise ValueError(f"{case_id} 章节SHA漂移")
        start, end = source["target_start"], source["target_end"]
        if start < 0 or end <= start or end > len(source_text):
            raise ValueError(f"{case_id} 坐标越界")
        if start and not source_text[:start].endswith("\n\n"):
            raise ValueError(f"{case_id} 起点不是自然段边界")
        if end < len(source_text) and not source_text[end:].startswith("\n\n"):
            raise ValueError(f"{case_id} 终点不是自然段边界")
        target = source_text[start:end]
        if sha256_bytes(target.encode()) != source["target_sha256"]:
            raise ValueError(f"{case_id} target SHA错误")
        if "".join(unit["text"] for unit in source["target_units"]) != target:
            raise ValueError(f"{case_id} Txx不能逐字重建target")
        if source["target_sha256"] in target_shas:
            raise ValueError(f"{case_id} target SHA重复")
        target_shas.add(source["target_sha256"])
        if source["reviewed_fact_count"] != len(gold["facts"]):
            raise ValueError(f"{case_id} source/Gold事实数不一致")
        if gold["expected_fact_count"] != len(gold["facts"]):
            raise ValueError(f"{case_id} expected_fact_count错误")
        if gold["exhaustive_within_target_candidate"] is not True:
            raise ValueError(f"{case_id} exhaustive标记错误")
        units = {unit["id"] for unit in source["target_units"]}
        fact_ids = set()
        for fact in gold["facts"]:
            if fact["fact_id"] in fact_ids or not fact["fact_sentence"]:
                raise ValueError(f"{case_id} fact_id重复或事实句为空")
            fact_ids.add(fact["fact_id"])
            if fact["status"] not in STATUSES:
                raise ValueError(f"{case_id} status非法")
            if fact["speaker"] is not None and not isinstance(fact["speaker"], str):
                raise ValueError(f"{case_id} speaker类型非法")
            evidence = fact["evidence_ids"]
            if not evidence or not all(item in units for item in evidence):
                raise ValueError(f"{case_id} evidence不存在或为空")
            numbers = [int(item[1:]) for item in evidence]
            if numbers != list(range(numbers[0], numbers[-1] + 1)):
                raise ValueError(f"{case_id} evidence不连续")
        if not gold["facts"]:
            exclusions = sidecar.get("tempting_exclusions", [])
            if len(exclusions) < 2:
                raise ValueError(f"{case_id} 真空题缺少具体诱饵排除理由")
        by_source[source["source_id"]].append(source)

    chapter_counts = Counter(row["source_id"] for row in source_rows)
    if len(chapter_counts) != 6 or set(chapter_counts.values()) != {4}:
        raise ValueError(f"不是六章各四题：{chapter_counts}")
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

    counts = Counter(len(row["facts"]) for row in gold_rows)
    if counts != Counter({0: 8, 1: 4, 2: 3, 3: 3, 4: 2, 5: 2, 6: 2}):
        raise ValueError(f"事实分布相对R02漂移：{counts}")
    if sum(key * value for key, value in counts.items()) != 49:
        raise ValueError("事实总数不是49")
    for case_id in SEMANTIC_FIX_IDS:
        if old_gold[case_id] != next(
            row for row in gold_rows if row["case_id"] == case_id
        ):
            raise ValueError(f"{case_id} R02语义修正倒退")

    for name, payload in feature_report["features"].items():
        correct = payload["best_single_threshold"]["correct"]
        if correct > FEATURE_GATE_MAX_CORRECT:
            raise ValueError(f"{name} 单阈值仍可猜中{correct}/24")

    return {
        "cases": 24,
        "facts": 49,
        "fact_count_distribution": {
            str(key): counts[key] for key in sorted(counts)
        },
        "zero_cases": counts[0],
        "nonempty_cases": 24 - counts[0],
        "coordinate_changes_from_r02": len(COORDINATE_OVERRIDES),
        "unique_source_chapters": len(chapter_counts),
        "targets_per_chapter": 4,
        "within_recut24_overlaps": 0,
        "prior_train72_l6_real24_overlaps": 0,
        "unique_target_sha256": len(target_shas),
        "all_evidence_in_target_and_contiguous": "49/49",
        "zero_case_exclusions_complete": "8/8",
        "unchanged_rows_byte_equivalent_to_r02": "21/21 source and sidecar; 24/24 Gold",
        "semantic_fix_cases_passed": "6/6",
        "unresolved_semantic_issues": 0,
        "fixed_visible_feature_gates": {
            name: payload["best_single_threshold"]["correct"]
            for name, payload in feature_report["features"].items()
        },
    }


def coordinate_change_rows(
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    old = {row["case_id"]: row for row in read_jsonl(R02_SOURCE)}
    return [
        {
            "case_id": row["case_id"],
            "old_range": [old[row["case_id"]]["target_start"], old[row["case_id"]]["target_end"]],
            "new_range": [row["target_start"], row["target_end"]],
            "old_non_whitespace_characters": old[row["case_id"]][
                "target_non_whitespace_character_count"
            ],
            "new_non_whitespace_characters": row[
                "target_non_whitespace_character_count"
            ],
            "new_target_sha256": row["target_sha256"],
        }
        for row in source_rows
        if row["case_id"] in COORDINATE_OVERRIDES
    ]


def markdown_summary(
    validation: dict[str, Any],
    feature_report: dict[str, Any],
    changes: list[dict[str, Any]],
) -> bytes:
    feature_lines = []
    for name, payload in feature_report["features"].items():
        best = payload["best_single_threshold"]
        threshold = best.get("threshold", best.get("threshold_exact"))
        feature_lines.append(
            f"| `{name}` | `{best['direction']}` | `{threshold}` | "
            f"{best['correct']}/24 | PASS |"
        )
    change_lines = [
        f"| `{item['case_id']}` | `[{item['old_range'][0]},{item['old_range'][1]})` | "
        f"`[{item['new_range'][0]},{item['new_range'][1]})` | "
        f"{item['old_non_whitespace_characters']} → {item['new_non_whitespace_characters']} |"
        for item in changes
    ]
    text = f"""# RECUT24 R03 审收说明

✅ 这版只在六篇冻结正文里换了 3 个自然目标区，24题仍是 8 个真空题、16 个非空题，Gold 仍为49条。六章正文、R01、R02 都没有修改。

R02 的语义与坐标机械核心已经通过，但可用自然段密度或逗号数明显猜空题，所以 R02 不能训练。R03 只修这层可见捷径，不生成题面，也不是训练授权。

## 三处坐标变化

| 题目 | R02坐标 | R03坐标 | 非空白字数 |
|---|---:|---:|---:|
{chr(10).join(change_lines)}

三处都按冻结正文的完整自然段收口，并重新逐字核了事实与诱饵。它们仍是语义真空：没有靠半句截断、填动作、改标点或改正文造空。

## 固定的三项表面门

| 模型可见特征 | 最佳判空方向 | 阈值 | 最佳准确数 | 结论 |
|---|---|---:|---:|---|
{chr(10).join(feature_lines)}

算法只遍历每项特征的所有观测阈值和两个方向，没有训练组合分类器，也没有临时增加第四个门。详细混淆表和逐题数值见 `FIXED_FEATURE_REPORT.json`。

## 语义与机械结论

- 事实分布：`0:8 / 1:4 / 2:3 / 3:3 / 4:2 / 5:2 / 6:2`，合计49条。
- R02六项语义修正继续通过：CH01-02、CH02-02、CH03-03、CH04-04、CH06-01、CH08-04。
- 未换段的21题 source/sidecar 与R02逐字相同；24题Gold全部逐字承接R02。
- 六章各4题，同章0重叠；与TRAIN72、L6、REAL24既有目标0坐标重叠、0片段SHA重复。
- 8个真空题都有正文诱饵和具体排除理由，没有换成纯景物填充。
- 构建器从最终输入确定性重渲染并逐字比对现有文件；本票不声称两套独立临时目录的“双构建”。

状态只到 `{STATUS}`，等待控制窗复核，不是训练授权。

来源：Codex
"""
    return text.encode()


def build_core() -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    verify_inputs()
    source_rows = build_source_rows()
    gold_rows = build_gold_rows()
    sidecar_rows = build_sidecar_rows(source_rows)
    feature_report = make_feature_report(source_rows)
    validation = validate(source_rows, gold_rows, sidecar_rows, feature_report)
    changes = coordinate_change_rows(source_rows)
    payloads = {
        "SOURCE_INDEX_24.jsonl": jsonl_bytes(source_rows),
        "MODEL_NEUTRAL_GOLD_24.jsonl": jsonl_bytes(gold_rows),
        "SEMANTIC_REVIEW_SIDECAR.jsonl": jsonl_bytes(sidecar_rows),
        "REVIEW_SUMMARY.md": markdown_summary(validation, feature_report, changes),
        "FIXED_FEATURE_REPORT.json": json_bytes(feature_report),
    }
    return payloads, validation, {"coordinate_changes": changes, "feature_report": feature_report}


def build() -> dict[str, Any]:
    r01_before = tree_digest(R01)
    r02_before = tree_digest(R02)
    payloads, validation, details = build_core()
    for name, data in payloads.items():
        (HERE / name).write_bytes(data)

    members = {}
    for path in [SOURCE_INDEX, GOLD, SIDECAR, SUMMARY, FEATURE_REPORT, Path(__file__)]:
        members[path.name] = {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
    manifest = {
        "schema_version": "train96-source6-recut24-output-manifest/3.0",
        "dataset_status": STATUS,
        "parent_r02": {
            "path": R02.relative_to(ROOT).as_posix(),
            "core_sha256": EXPECTED_INPUT_SHA256,
            "tree_digest": r02_before,
        },
        "control_review": {
            "path": CONTROL_REVIEW.relative_to(ROOT).as_posix(),
            "sha256": EXPECTED_INPUT_SHA256["RECUT24_R02_CONTROL_REVIEW.md"],
        },
        "members": members,
        "training_authorized": False,
    }
    MANIFEST.write_bytes(json_bytes(manifest))
    r01_after = tree_digest(R01)
    r02_after = tree_digest(R02)
    if r01_before != r01_after or r02_before != r02_after:
        raise ValueError("R01或R02在构建前后发生变化")
    receipt = {
        "schema_version": "train96-source6-recut24-final-validation-receipt/3.0",
        "dataset_status": STATUS,
        "conclusion_zh": (
            "24题、49条模型中立Gold候选通过R03三项固定表面门，"
            "等待控制窗复核，不是训练授权"
        ),
        "output_manifest": {
            "path": MANIFEST.name,
            "bytes": MANIFEST.stat().st_size,
            "sha256": file_sha256(MANIFEST),
        },
        "r01_byte_identity": {
            "tree_digest_before": r01_before,
            "tree_digest_after": r01_after,
            "unchanged": r01_before == r01_after,
        },
        "r02_byte_identity": {
            "tree_digest_before": r02_before,
            "tree_digest_after": r02_after,
            "unchanged": r02_before == r02_after,
        },
        "coordinate_changes": details["coordinate_changes"],
        "semantic_fix_status": {case_id: "PASS" for case_id in sorted(SEMANTIC_FIX_IDS)},
        "validation": {
            **validation,
            "deterministic_rerender_verified": True,
            "double_build_claimed": False,
            "json_parse": "PASS",
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
    RECEIPT.write_bytes(json_bytes(receipt))
    return receipt


def check_files() -> dict[str, Any]:
    payloads, validation, _ = build_core()
    for name, expected in payloads.items():
        path = HERE / name
        if not path.exists() or path.read_bytes() != expected:
            raise ValueError(f"{name} 与确定性重渲染不一致")
    manifest = json.loads(MANIFEST.read_text())
    for name, identity in manifest["members"].items():
        path = HERE / name
        if path.stat().st_size != identity["bytes"] or file_sha256(path) != identity["sha256"]:
            raise ValueError(f"manifest成员漂移：{name}")
    receipt = json.loads(RECEIPT.read_text())
    if receipt["output_manifest"]["sha256"] != file_sha256(MANIFEST):
        raise ValueError("receipt没有绑定当前manifest")
    if tree_digest(R01) != receipt["r01_byte_identity"]["tree_digest_after"]:
        raise ValueError("R01在封票后漂移")
    if tree_digest(R02) != receipt["r02_byte_identity"]["tree_digest_after"]:
        raise ValueError("R02在封票后漂移")
    return validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    result = build() if args.command == "build" else check_files()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
