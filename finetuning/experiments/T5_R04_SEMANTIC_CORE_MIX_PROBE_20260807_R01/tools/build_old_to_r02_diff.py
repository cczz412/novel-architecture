#!/usr/bin/env python3
"""把冻结旧分与 EVALUATOR_R02 新分并排，不覆盖任一旧文件。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r02", type=Path, required=True)
    parser.add_argument("--old-final", type=Path, required=True)
    parser.add_argument("--old-stage1", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    r02 = json.loads(args.r02.read_text(encoding="utf-8"))
    old_final = json.loads(args.old_final.read_text(encoding="utf-8"))
    old_stage1 = json.loads(args.old_stage1.read_text(encoding="utf-8"))["stage_1a"]
    new = {row["group_id"]: row for row in r02["groups"]}
    old = {
        "H00_A_STAGE1_OLD41": {
            "format": old_stage1["a"]["stage1"]["raw_json_valid_cases"],
            "machine_repeat": None,
            "diagnostic_repeat": old_stage1["a"]["stage1"]["severe_repeat_cases"],
            "triple_f1": old_stage1["a"]["stage1"]["fact_normalized_raw"]["f1"],
        },
        "H01_A_FINAL_OLD41": {
            "format": old_final["arm_a"]["format_valid_segments"],
            "machine_repeat": old_final["arm_a"]["repeated_fact_loop_segments"],
            "diagnostic_repeat": old_stage1["a"]["final"]["severe_repeat_cases"],
            "triple_f1": old_final["arm_a"]["semantic_fact_status_speaker"]["f1"],
        },
        "H02_C_STAGE1_OLD41": {
            "format": old_stage1["c"]["stage1"]["raw_json_valid_cases"],
            "machine_repeat": None,
            "diagnostic_repeat": old_stage1["c"]["stage1"]["severe_repeat_cases"],
            "triple_f1": old_stage1["c"]["stage1"]["fact_normalized_raw"]["f1"],
        },
        "H03_C_FINAL_OLD41": {
            "format": old_final["arm_c"]["format_valid_segments"],
            "machine_repeat": old_final["arm_c"]["repeated_fact_loop_segments"],
            "diagnostic_repeat": old_stage1["c"]["final"]["severe_repeat_cases"],
            "triple_f1": old_final["arm_c"]["semantic_fact_status_speaker"]["f1"],
        },
    }
    rows = []
    for group_id in old:
        current = new[group_id]
        rows.append({
            "group_id": group_id,
            "old_format_valid": old[group_id]["format"],
            "r02_schema_valid": current["format"]["schema_valid"],
            "format_valid_delta": current["format"]["schema_valid"] - old[group_id]["format"],
            "old_machine_repeat_valid_json_only": old[group_id]["machine_repeat"],
            "old_recovered_diagnostic_repeat": old[group_id]["diagnostic_repeat"],
            "r02_recovered_object_repeat": current["format"]["recovered_object_repeat"],
            "r02_recovered_fact_repeat": current["format"]["recovered_fact_repeat"],
            "old_exact_triple_f1_misnamed_semantic": old[group_id]["triple_f1"],
            "r02_normalized_exact_triple_f1": current["scores"]["normalized_exact_triple"]["f1"],
            "r02_normalized_exact_fact_f1": current["scores"]["normalized_exact_fact"]["f1"],
        })
    output = {
        "schema_version": "t5-r04-evaluator-r02-old-diff-v1",
        "status": "PASS_OLD_PRESERVED_R02_SEPARATE",
        "source_bindings": {
            "r02_metrics_sha256": sha256(args.r02),
            "old_final_metrics_sha256": sha256(args.old_final),
            "old_stage1_metrics_sha256": sha256(args.old_stage1)
        },
        "rows": rows,
        "core_conclusion_impact": [
            {
                "conclusion": "STAGE2_FORMAT_POLLUTION_SUPPORTED",
                "result": "NOT_OVERTURNED_INTERPRETATION_REMAINS_NARROW",
                "reason": "A 的完整 Schema 仍为 4→14；R02 不把字符串近似当语义，也不支持特殊教材整体致害"
            },
            {
                "conclusion": "MIXED_STAGE_EFFECT",
                "result": "NOT_OVERTURNED",
                "reason": "C 的完整 Schema 37→35，恢复后事实复读 17→26"
            },
            {
                "conclusion": "OUTPUT_LIMIT_IS_TERMINATOR_SUPPORTED",
                "result": "NOT_REEVALUATED_NO_CONFLICT",
                "reason": "本轮评分器没有改 4096 实验的逐 token 证据"
            },
            {
                "conclusion": "NO_MATERIAL_HEADER_EFFECT",
                "result": "HISTORICAL_MACHINE_LABEL_UNCHANGED_WORDING_STILL_NEEDS_NARROWING",
                "reason": "本轮没有重跑 1C；外部复核已确认只测了 @start:end 的记法外观"
            }
        ],
        "new_diagnostic_findings": [
            {
                "finding": "A_FINAL_REPEAT_UNDERCOUNT_IN_ORIGINAL_MACHINE_SCORE",
                "old_valid_json_only_cases": old_final["arm_a"]["repeated_fact_loop_segments"],
                "r02_recovered_object_repeat_cases": new["H01_A_FINAL_OLD41"]["format"]["recovered_object_repeat"],
                "r02_recovered_fact_repeat_cases": new["H01_A_FINAL_OLD41"]["format"]["recovered_fact_repeat"],
                "impact": "原机器分漏掉非法 JSON 中的复读；阶段 1 后续诊断已捕获 23 案，因此不推翻阶段 1 总判"
            },
            {
                "finding": "ONE_A_FINAL_NORMALIZED_EXACT_FACT_WITH_TRIPLE_MISMATCH",
                "exact_fact_tp": new["H01_A_FINAL_OLD41"]["scores"]["normalized_exact_fact"]["tp"],
                "exact_triple_tp": new["H01_A_FINAL_OLD41"]["scores"]["normalized_exact_triple"]["tp"],
                "impact": "证明旧三元组地板分会掩盖极少量 fact 命中，但远不足以改判模型合格"
            }
        ],
        "historical_files_modified": False,
        "human_semantic_review_complete": False
    }
    write_json(args.output, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
