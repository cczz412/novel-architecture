#!/usr/bin/env python3
"""Mechanical gates and blind-review semantic ranking for the relative screen."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
RUN_ROOT = REPO / "runs/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
STAGE1_RAW = RUN_ROOT / "inference/STAGE1_LORA_RAW_24.jsonl"
FULL_RAW = RUN_ROOT / "inference/FULL24_MATCHED_RAW.jsonl"
GOLD = (
    REPO
    / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/"
    "REAL24_GOLD_24.jsonl"
)
TXX = GOLD.parent / "REAL24_TXX_MAP.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/"
    "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
WO_SCORER = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/tools/score_demo.py"
)
OLD_AB8_RAW = (
    REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01/FORMAT_B_RAW_8.jsonl"
)
OLD_AB8_ADJUDICATIONS = (
    REPO
    / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01/FORMAT_B_ADJUDICATIONS.jsonl"
)
EXPECTED = {
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "wo_scorer_sha256": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
    "old_ab8_raw_sha256": "d79e768c1163085016472591e47e92a203421d73266f78daf51e952b71690351",
    "old_ab8_adjudications_sha256": "810fa1a4427b743854fc70def399a5635efe06c71daaf9feb0babd514aa1150f",
}
ARMS = ("READ1", "READ2", "READ4")
CASES8 = ("C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24")
MAX_OUTPUT_TOKENS = 2048


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def load_wo() -> Any:
    spec = importlib.util.spec_from_file_location("relative_wo_scorer", WO_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("WO_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_sources() -> None:
    actual = {
        "gold_sha256": sha256(GOLD),
        "txx_sha256": sha256(TXX),
        "schema_sha256": sha256(SCHEMA),
        "wo_scorer_sha256": sha256(WO_SCORER),
        "old_ab8_raw_sha256": sha256(OLD_AB8_RAW),
        "old_ab8_adjudications_sha256": sha256(OLD_AB8_ADJUDICATIONS),
    }
    if actual != EXPECTED:
        raise RuntimeError(f"SCORER_SOURCE_SHA_DRIFT:{actual}")


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    chunks = Counter(
        compact[index : index + 80] for index in range(0, len(compact) - 79, 8)
    )
    return any(count >= 3 for count in chunks.values())


def strict_and_recoverable_parse(
    raw: str, validator: Draft202012Validator
) -> tuple[bool, bool, list[dict[str, Any]]]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        value = None
    json_valid = isinstance(value, dict)
    schema_valid = json_valid and not list(validator.iter_errors(value))
    if json_valid and isinstance(value.get("facts"), list):
        facts = [
            item
            for item in value["facts"]
            if isinstance(item, dict)
            and isinstance(item.get("fact"), str)
            and item["fact"]
        ]
        return True, schema_valid, facts
    decoder = json.JSONDecoder()
    recovered = []
    for start, character in enumerate(raw):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(candidate, dict)
            and isinstance(candidate.get("fact"), str)
            and candidate["fact"]
        ):
            recovered.append(candidate)
    return json_valid, schema_valid, recovered


def target_ids() -> dict[str, set[str]]:
    return {
        row["case_id"]: {unit["id"] for unit in row["target_units"]}
        for row in read_jsonl(TXX)
    }


def gold_map() -> dict[str, list[dict[str, Any]]]:
    rows = read_jsonl(GOLD)
    if [row["case_id"] for row in rows] != [f"C{index:02d}" for index in range(1, 25)]:
        raise RuntimeError("GOLD_CASE_ORDER_DRIFT")
    return {
        row["case_id"]: [
            {
                "fact_id": f"{row['case_id']}-F{index:03d}",
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence_ids"],
            }
            for index, fact in enumerate(row["facts"], 1)
        ]
        for row in rows
    }


def mechanical_case(
    row: dict[str, Any],
    validator: Draft202012Validator,
    valid_ids: dict[str, set[str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    json_valid, schema_valid, facts = strict_and_recoverable_parse(
        row["raw_output"], validator
    )
    duplicates = sum(
        count - 1
        for count in Counter(item.get("fact") for item in facts).values()
        if count > 1
    )
    illegal = sum(
        not isinstance(item.get("evidence_ids"), list)
        or any(item_id not in valid_ids[row["case_id"]] for item_id in item.get("evidence_ids", []))
        for item in facts
    )
    return (
        {
            "variant": row["variant"],
            "arm": row["arm"],
            "case_id": row["case_id"],
            "predictions": len(facts),
            "json_valid": json_valid,
            "schema_valid": schema_valid,
            "illegal_evidence_predictions": illegal,
            "duplicate_predictions": duplicates,
            "repetition_detected": duplicates > 0 or repeated_chunk(row["raw_output"]),
            "token_limit_hit": row.get("finish_reason") == "length"
            or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
        },
        facts,
    )


def mechanical_summary(rows: list[dict[str, Any]], cases: int) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "strict_json_cases": sum(row["json_valid"] for row in rows),
        "schema_cases": sum(row["schema_valid"] for row in rows),
        "illegal_evidence_predictions": sum(
            row["illegal_evidence_predictions"] for row in rows
        ),
        "repetition_cases": sum(row["repetition_detected"] for row in rows),
        "token_limit_cases": sum(row["token_limit_hit"] for row in rows),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in rows),
        "pass": len(rows) == cases
        and sum(row["json_valid"] for row in rows) == cases
        and sum(row["schema_valid"] for row in rows) == cases
        and sum(row["illegal_evidence_predictions"] for row in rows) == 0
        and sum(row["repetition_detected"] for row in rows) == 0
        and sum(row["token_limit_hit"] for row in rows) == 0
        and sum(row["duplicate_predictions"] for row in rows) == 0,
    }


def stage1_pre() -> None:
    verify_sources()
    if not STAGE1_RAW.is_file():
        raise RuntimeError("STAGE1_RAW_MISSING")
    rows = read_jsonl(STAGE1_RAW)
    if len(rows) != 24:
        raise RuntimeError(f"STAGE1_ROW_COUNT_DRIFT:{len(rows)}")
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    valid_ids = target_ids()
    case_metrics = []
    summaries = {}
    for arm in ARMS:
        group = [row for row in rows if row.get("variant") == f"LORA_{arm}"]
        if [row.get("case_id") for row in group] != list(CASES8):
            raise RuntimeError(f"STAGE1_CASE_ORDER_DRIFT:{arm}")
        mechanical = [mechanical_case(row, validator, valid_ids)[0] for row in group]
        case_metrics.extend(mechanical)
        summaries[arm] = mechanical_summary(mechanical, 8)
    passing = [arm for arm in ARMS if summaries[arm]["pass"]]
    output = RUN_ROOT / "scoring/STAGE1_MECHANICAL_GATE.json"
    write_json(
        output,
        {
            "status": (
                "PASS_STAGE1_MINIMUM_TWO_ARMS"
                if len(passing) >= 2
                else "FAIL_STAGE1_FEWER_THAN_TWO_ARMS"
            ),
            "stage1_raw_sha256": sha256(STAGE1_RAW),
            "passing_arms": passing,
            "eliminated_arms": [arm for arm in ARMS if arm not in passing],
            "minimum_passing_arms_for_full24": 2,
            "full24_authorized_by_mechanical_gate": len(passing) >= 2,
            "semantic_threshold_used": False,
            "old_ab8_semantic_fail_preserved": True,
            "arms": summaries,
            "case_metrics": case_metrics,
            "api_calls": 0,
        },
    )
    print(
        json.dumps(
            {"status": read_json(output)["status"], "passing_arms": passing},
            ensure_ascii=False,
        )
    )


def old_decisions() -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for row in read_jsonl(OLD_AB8_ADJUDICATIONS):
        if row.get("raw_sha256") != EXPECTED["old_ab8_raw_sha256"]:
            raise RuntimeError("OLD_AB8_ADJUDICATION_RAW_SHA_DRIFT")
        if row.get("gold_sha256") != EXPECTED["gold_sha256"]:
            raise RuntimeError("OLD_AB8_ADJUDICATION_GOLD_SHA_DRIFT")
        key = (row["case_id"], row["prediction_fact_sha256"])
        if key in result or fact_sha(row["prediction_fact"]) != key[1]:
            raise RuntimeError("OLD_AB8_ADJUDICATION_FACT_DRIFT")
        result[key] = row
    return result


def new_decisions(path: Path | None, raw_sha: str) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    result = {}
    for row in read_jsonl(path):
        if row.get("raw_sha256") != raw_sha or row.get("gold_sha256") != EXPECTED["gold_sha256"]:
            raise RuntimeError("ADJUDICATION_IDENTITY_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or fact_sha(row.get("prediction_fact", "")) != key[1]:
            raise RuntimeError("ADJUDICATION_DUPLICATE_OR_FACT_DRIFT")
        if row.get("category") not in {
            "SEMANTIC_EQUIVALENT",
            "NOT_MATCH",
            "OUT_OF_SCOPE",
        }:
            raise RuntimeError("ADJUDICATION_CATEGORY_INVALID")
        result[key] = row
    return result


def semantic_score(
    raw_rows: list[dict[str, Any]],
    parsed: dict[tuple[str, str], list[dict[str, Any]]],
    adjudications: Path | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    wo = load_wo()
    gold = gold_map()
    raw_sha = sha256(FULL_RAW)
    old_index = old_decisions()
    new_index = new_decisions(adjudications, raw_sha)
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    case_metrics = []
    for row in raw_rows:
        case_id = row["case_id"]
        variant = row["variant"]
        predicted = parsed[(variant, case_id)]
        expected = gold[case_id]
        pairs, unmatched = wo.match(expected, predicted, normalized=True)
        used_gold = {gold_index for _, gold_index in pairs}
        for prediction_index in unmatched:
            text = predicted[prediction_index].get("fact", "")
            key = (case_id, fact_sha(text))
            decision = None
            if variant == "LORA_READ1" and case_id in CASES8:
                decision = old_index.get(key)
            if decision is None:
                decision = new_index.get(key)
            if decision is None:
                queue_row = pending.setdefault(
                    key,
                    {
                        "case_id": case_id,
                        "prediction_fact": text,
                        "prediction_fact_sha256": key[1],
                        "raw_sha256": raw_sha,
                        "gold_sha256": EXPECTED["gold_sha256"],
                        "variant_occurrences": [],
                        "candidate_gold_facts": [
                            {"fact_id": item["fact_id"], "fact": item["fact"]}
                            for item in expected
                        ],
                    },
                )
                queue_row["variant_occurrences"].append(variant)
            elif decision["category"] == "SEMANTIC_EQUIVALENT":
                matched_id = decision.get("matched_gold_fact_id")
                gold_index = next(
                    (
                        index
                        for index, item in enumerate(expected)
                        if item["fact_id"] == matched_id
                    ),
                    None,
                )
                if gold_index is None:
                    raise RuntimeError("ADJUDICATION_MATCHED_GOLD_ID_INVALID")
                if gold_index not in used_gold:
                    pairs.append((prediction_index, gold_index))
                    used_gold.add(gold_index)
        status_ok = speaker_ok = evidence_ok = 0
        for prediction_index, gold_index in pairs:
            prediction = predicted[prediction_index]
            target = expected[gold_index]
            status_ok += prediction.get("status") == target["status"]
            speaker_ok += prediction.get("speaker") == target["speaker"]
            evidence_ok += prediction.get("evidence_ids") == target["evidence_ids"]
        case_metrics.append(
            {
                "variant": variant,
                "arm": row["arm"],
                "case_id": case_id,
                "gold": len(expected),
                "predictions": len(predicted),
                "semantic_tp": len(pairs),
                "status_correct": status_ok,
                "speaker_correct": speaker_ok,
                "evidence_correct": evidence_ok,
            }
        )
    variants = [value for value in dict.fromkeys(row["variant"] for row in raw_rows)]
    by_variant = {}
    for variant in variants:
        group = [row for row in case_metrics if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        by_variant[variant] = {
            "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
            "status_correct": sum(row["status_correct"] for row in group),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
        }
    return {"variants": by_variant, "case_metrics": case_metrics}, list(pending.values())


def full_score(adjudications: Path | None, final: bool) -> None:
    verify_sources()
    gate = read_json(RUN_ROOT / "scoring/STAGE1_MECHANICAL_GATE.json")
    passing = gate.get("passing_arms")
    if not isinstance(passing, list) or len(passing) < 2:
        raise RuntimeError("FULL_SCORING_FORBIDDEN_FEWER_THAN_TWO_PASSING_ARMS")
    if not FULL_RAW.is_file():
        raise RuntimeError("FULL24_RAW_MISSING")
    raw_rows = read_jsonl(FULL_RAW)
    expected_variants = [f"BASE_{arm}" for arm in passing] + [
        f"LORA_{arm}" for arm in passing
    ]
    if Counter(row.get("variant") for row in raw_rows) != Counter(
        {variant: 24 for variant in expected_variants}
    ):
        raise RuntimeError("FULL24_VARIANT_ROW_COUNT_DRIFT")
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    valid_ids = target_ids()
    parsed = {}
    mechanical_cases = []
    mechanical_variants = {}
    for variant in expected_variants:
        group = [row for row in raw_rows if row["variant"] == variant]
        expected_cases = [f"C{index:02d}" for index in range(1, 25)]
        if [row["case_id"] for row in group] != expected_cases:
            raise RuntimeError(f"FULL24_CASE_ORDER_DRIFT:{variant}")
        current = []
        for row in group:
            metrics, facts = mechanical_case(row, validator, valid_ids)
            current.append(metrics)
            parsed[(variant, row["case_id"])] = facts
        mechanical_cases.extend(current)
        mechanical_variants[variant] = mechanical_summary(current, 24)
    lora_format_pass = all(
        mechanical_variants[f"LORA_{arm}"]["pass"] for arm in passing
    )
    base_format_all_pass = all(
        mechanical_variants[f"BASE_{arm}"]["pass"] for arm in passing
    )
    if not lora_format_pass:
        if final:
            raise RuntimeError("FULL_FINAL_FORBIDDEN_LORA_FORMAT_GATE_FAILED")
        semantic: dict[str, Any] = {"variants": {}, "case_metrics": []}
        pending: list[dict[str, Any]] = []
    else:
        semantic, pending = semantic_score(raw_rows, parsed, adjudications)
        if final and pending:
            raise RuntimeError(f"SEMANTIC_ADJUDICATIONS_INCOMPLETE:{len(pending)}")
    result: dict[str, Any] = {
        "status": (
            "FAIL_FULL24_LORA_FORMAT_GATE"
            if not lora_format_pass
            else (
                "PASS_FINAL_RELATIVE_RANKING"
                if final
                else "PENDING_BLIND_SEMANTIC_REVIEW"
            )
        ),
        "raw_sha256": sha256(FULL_RAW),
        "gold_sha256": EXPECTED["gold_sha256"],
        "passing_arms_from_stage1": passing,
        "lora_format_gate_pass": lora_format_pass,
        "base_format_report_all_pass": base_format_all_pass,
        "base_format_is_diagnostic_not_gate": True,
        "mechanical_variants": mechanical_variants,
        "mechanical_case_metrics": mechanical_cases,
        "semantic_pending": len(pending),
        "semantic_metric_is_final": final and not pending,
        **semantic,
        "conclusion_scope_zh": (
            "仅限当前本机 REAL24、单 seed、低剂量 24 步和 B 合同的条件式 Demo 排名；"
            "不是合格配方、生产候选或通用赢家。"
        ),
        "api_calls": 0,
    }
    if final and lora_format_pass:
        lora_scores = {
            arm: result["variants"][f"LORA_{arm}"]["semantic_recoverable"]["f1"]
            for arm in passing
        }
        ordered = sorted(lora_scores, key=lambda arm: (-lora_scores[arm], len(arm)))
        best, second = ordered[:2]
        gap = lora_scores[best] - lora_scores[second]
        base_delta = {
            arm: lora_scores[arm]
            - result["variants"][f"BASE_{arm}"]["semantic_recoverable"]["f1"]
            for arm in passing
        }
        if gap < 0.02:
            winner = min((best, second), key=lambda arm: {"READ1": 1, "READ2": 2, "READ4": 4}[arm])
            verdict = "APPROXIMATE_TIE_RECOMMEND_SHORTER_READ"
        else:
            winner = best
            verdict = "CONDITIONAL_DEMO_RELATIVE_WINNER"
        result["relative_ranking"] = {
            "verdict": verdict,
            "recommended_arm": winner,
            "lora_f1": lora_scores,
            "top_two_f1_gap": gap,
            "approximate_tie_threshold_strictly_below": 0.02,
            "matched_base_f1_delta_diagnostic_only": base_delta,
        }
    output_dir = RUN_ROOT / ("scoring/full_final" if final else "scoring/full_pre")
    if output_dir.exists():
        raise RuntimeError(f"SCORING_OUTPUT_EXISTS_NO_OVERWRITE:{output_dir}")
    output_dir.mkdir(parents=True)
    write_json(output_dir / "METRICS.json", result)
    write_jsonl(output_dir / "BLIND_QUEUE.jsonl", pending)
    print(
        json.dumps(
            {
                "status": result["status"],
                "semantic_pending": result["semantic_pending"],
                "lora_format_pass": lora_format_pass,
                "base_format_all_pass": base_format_all_pass,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("stage1-pre", "full-pre", "full-final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    if args.command == "stage1-pre":
        stage1_pre()
    elif args.command == "full-pre":
        full_score(None, False)
    else:
        if args.adjudications is None:
            raise RuntimeError("FULL_FINAL_REQUIRES_ADJUDICATIONS")
        full_score(args.adjudications, True)


if __name__ == "__main__":
    main()
