#!/usr/bin/env python3
"""Prepare and later score the blind READ2 semantic carryover gate."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
PARENT_EXP = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
)
RUN_ROOT = REPO / "runs/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
FULL_RAW = RUN_ROOT / "inference/FULL24_MATCHED_RAW.jsonl"
FULL_RESULT = RUN_ROOT / "inference/FULL24_RESULT.json"
FULL_METRICS = RUN_ROOT / "scoring/full_pre/METRICS.json"
PARENT_SCORER = PARENT_EXP / "score_relative_screen.py"
GOLD = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/"
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
    "T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/"
    "tools/score_demo.py"
)
QUEUE = EXP / "BLIND_QUEUE.jsonl"
VARIANTS = ("BASE_READ2", "LORA_READ2")
CASES = tuple(f"C{index:02d}" for index in range(1, 25))
EXPECTED_SHA = {
    "full_raw": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "full_result": "a8b3276179551aaa3b7e42c274c0a7c5327846171be58c02ff0d38de778340b9",
    "full_metrics": "583d89053ed5662b516206579782338994afeca3580a25e39cc98c1781692d57",
    "parent_scorer": "196304b03a9e0bf194bd929b5a00b9e436ace64bfa8a7bd530c12308e32b8b23",
    "schema": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "gold": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "txx": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "wo_scorer": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
}
EXPECTED_PROJECTION_SHA = {
    "BASE_READ2": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "LORA_READ2": "e1951be12acb7df0feda81bcf16f8d30be35f95b57e85d15013a08d55b404333",
    "combined": "c3f62fe5b596f1a66778c088bcb9081febbaae46bfbfde305c8f4d4ae77647a7",
}
QUEUE_FIELDS = {
    "case_id",
    "prediction_fact",
    "prediction_fact_sha256",
    "raw_sha256",
    "gold_sha256",
    "candidate_gold_facts",
    "category",
    "matched_gold_fact_id",
}
ALLOWED_CATEGORIES = {
    "SEMANTIC_EQUIVALENT",
    "NOT_MATCH",
    "OUT_OF_SCOPE",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def write_new(path: Path, value: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(value)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_IMPORT_FAILED:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_inputs() -> None:
    actual = {
        "full_raw": sha256(FULL_RAW),
        "full_result": sha256(FULL_RESULT),
        "full_metrics": sha256(FULL_METRICS),
        "parent_scorer": sha256(PARENT_SCORER),
        "schema": sha256(SCHEMA),
        "gold": sha256(GOLD),
        "txx": sha256(TXX),
        "wo_scorer": sha256(WO_SCORER),
    }
    if actual != EXPECTED_SHA:
        raise RuntimeError(f"FROZEN_INPUT_SHA_DRIFT:{actual}")

    result = read_json(FULL_RESULT)
    metrics = read_json(FULL_METRICS)
    if result.get("raw_sha256") != EXPECTED_SHA["full_raw"]:
        raise RuntimeError("FULL_RESULT_RAW_BINDING_DRIFT")
    if metrics.get("status") != "FAIL_FULL24_LORA_FORMAT_GATE":
        raise RuntimeError("OLD_GLOBAL_FAIL_STATUS_DRIFT")
    if metrics.get("raw_sha256") != EXPECTED_SHA["full_raw"]:
        raise RuntimeError("FULL_METRICS_RAW_BINDING_DRIFT")
    if metrics.get("gold_sha256") != EXPECTED_SHA["gold"]:
        raise RuntimeError("FULL_METRICS_GOLD_BINDING_DRIFT")
    mechanical = metrics.get("mechanical_variants", {})
    if mechanical.get("LORA_READ2", {}).get("pass") is not True:
        raise RuntimeError("LORA_READ2_NO_LONGER_MECHANICALLY_PASSING")
    if mechanical.get("LORA_READ1", {}).get("pass") is not False:
        raise RuntimeError("LORA_READ1_FAILURE_BOUNDARY_DRIFT")


def frozen_rows() -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    exact_lines = FULL_RAW.read_text(encoding="utf-8").splitlines(keepends=True)
    parsed_lines = [(line, json.loads(line)) for line in exact_lines if line.strip()]
    all_rows = [row for _, row in parsed_lines]
    expected_counts = Counter(
        {"BASE_READ1": 24, "BASE_READ2": 24, "LORA_READ1": 24, "LORA_READ2": 24}
    )
    if Counter(row.get("variant") for row in all_rows) != expected_counts:
        raise RuntimeError("FULL_RAW_VARIANT_SET_DRIFT")
    all_keys = [(row.get("variant"), row.get("case_id")) for row in all_rows]
    if len(all_keys) != len(set(all_keys)):
        raise RuntimeError("FULL_RAW_DUPLICATE_VARIANT_CASE_KEY")

    projection: dict[str, bytes] = {}
    selected: list[dict[str, Any]] = []
    for variant in VARIANTS:
        variant_pairs = [(line, row) for line, row in parsed_lines if row["variant"] == variant]
        rows = [row for _, row in variant_pairs]
        if [row.get("case_id") for row in rows] != list(CASES):
            raise RuntimeError(f"READ2_CASE_ORDER_DRIFT:{variant}")
        projection[variant] = "".join(line for line, _ in variant_pairs).encode("utf-8")
        selected.extend(rows)
    projection["combined"] = projection["BASE_READ2"] + projection["LORA_READ2"]
    actual_projection = {key: bytes_sha256(value) for key, value in projection.items()}
    if actual_projection != EXPECTED_PROJECTION_SHA:
        raise RuntimeError(f"READ2_EXACT_LINE_PROJECTION_DRIFT:{actual_projection}")
    return selected, projection


def build_state() -> dict[str, Any]:
    verify_inputs()
    selected, projection = frozen_rows()
    parent = load_module(PARENT_SCORER, "read2_carryover_parent_scorer")
    wo = parent.load_wo()
    gold = parent.gold_map()
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    parsed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    exact_pairs: dict[tuple[str, str], list[tuple[int, int]]] = {}
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    unmatched_occurrences = 0
    for row in selected:
        variant = row["variant"]
        case_id = row["case_id"]
        _, _, facts = parent.strict_and_recoverable_parse(row["raw_output"], validator)
        prediction_keys = [(case_id, fact_sha(item["fact"])) for item in facts]
        if len(prediction_keys) != len(set(prediction_keys)):
            raise RuntimeError(f"DUPLICATE_PREDICTION_KEY:{variant}:{case_id}")
        parsed[(variant, case_id)] = facts
        pairs, unmatched = wo.match(gold[case_id], facts, normalized=True)
        exact_pairs[(variant, case_id)] = list(pairs)
        unmatched_occurrences += len(unmatched)
        for prediction_index in unmatched:
            text = facts[prediction_index]["fact"]
            key = (case_id, fact_sha(text))
            queue_row = pending.setdefault(
                key,
                {
                    "case_id": case_id,
                    "prediction_fact": text,
                    "prediction_fact_sha256": key[1],
                    "raw_sha256": EXPECTED_SHA["full_raw"],
                    "gold_sha256": EXPECTED_SHA["gold"],
                    "candidate_gold_facts": [
                        {"fact_id": item["fact_id"], "fact": item["fact"]}
                        for item in gold[case_id]
                    ],
                    "category": None,
                    "matched_gold_fact_id": None,
                },
            )
            if queue_row["prediction_fact"] != text:
                raise RuntimeError("PREDICTION_FACT_SHA_COLLISION")

    queue = list(pending.values())
    for row in queue:
        if set(row) != QUEUE_FIELDS:
            raise RuntimeError("BLIND_QUEUE_FIELD_SET_DRIFT")
        serialized = json.dumps(row, ensure_ascii=False)
        if any(token in serialized for token in ("variant", "arm", "BASE_READ2", "LORA_READ2")):
            raise RuntimeError("BLIND_QUEUE_IDENTITY_LEAK")
    return {
        "selected": selected,
        "projection": projection,
        "parsed": parsed,
        "exact_pairs": exact_pairs,
        "gold": gold,
        "wo": wo,
        "queue": queue,
        "unmatched_occurrences": unmatched_occurrences,
    }


def prepare() -> None:
    state = build_state()
    queue_bytes = jsonl_bytes(state["queue"])
    write_new(QUEUE, queue_bytes)
    print(
        json.dumps(
            {
                "status": "PREPARED_BLIND_QUEUE_NOT_ADJUDICATED_NOT_FINAL",
                "selected_rows": len(state["selected"]),
                "queue_rows": len(state["queue"]),
                "unmatched_prediction_occurrences": state["unmatched_occurrences"],
                "queue_sha256": bytes_sha256(queue_bytes),
            },
            ensure_ascii=False,
        )
    )


def verify() -> None:
    state = build_state()
    if not QUEUE.is_file():
        raise RuntimeError("BLIND_QUEUE_MISSING")
    expected = jsonl_bytes(state["queue"])
    if QUEUE.read_bytes() != expected:
        raise RuntimeError("BLIND_QUEUE_REBUILD_DRIFT")
    rows = read_jsonl(QUEUE)
    keys = [(row["case_id"], row["prediction_fact_sha256"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError("BLIND_QUEUE_DUPLICATE_KEY")
    print(
        json.dumps(
            {
                "status": "PASS_PREPARE_MECHANICAL_VERIFICATION",
                "selected_variants": list(VARIANTS),
                "rows_per_variant": 24,
                "queue_rows": len(rows),
                "queue_sha256": sha256(QUEUE),
                "identity_leaks": 0,
            },
            ensure_ascii=False,
        )
    )


def load_adjudications(path: Path, queue: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    expected = {(row["case_id"], row["prediction_fact_sha256"]): row for row in queue}
    decisions: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_jsonl(path):
        if set(row) != QUEUE_FIELDS:
            raise RuntimeError("ADJUDICATION_FIELD_SET_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in decisions:
            raise RuntimeError("ADJUDICATION_DUPLICATE_KEY")
        template = expected.get(key)
        if template is None:
            raise RuntimeError("ADJUDICATION_UNKNOWN_FACT")
        for field in QUEUE_FIELDS - {"category", "matched_gold_fact_id"}:
            if row.get(field) != template.get(field):
                raise RuntimeError(f"ADJUDICATION_IDENTITY_DRIFT:{field}")
        if row.get("category") not in ALLOWED_CATEGORIES:
            raise RuntimeError("ADJUDICATION_CATEGORY_INVALID")
        if row["category"] == "SEMANTIC_EQUIVALENT":
            valid_ids = {item["fact_id"] for item in template["candidate_gold_facts"]}
            if row.get("matched_gold_fact_id") not in valid_ids:
                raise RuntimeError("ADJUDICATION_MATCHED_GOLD_ID_INVALID")
        elif row.get("matched_gold_fact_id") is not None:
            raise RuntimeError("NONMATCH_ADJUDICATION_MUST_NOT_BIND_GOLD")
        decisions[key] = row
    if set(decisions) != set(expected):
        missing = len(set(expected) - set(decisions))
        extra = len(set(decisions) - set(expected))
        raise RuntimeError(f"ADJUDICATION_COVERAGE_DRIFT:missing={missing}:extra={extra}")
    return decisions


def final(adjudications: Path, output: Path) -> None:
    state = build_state()
    if QUEUE.read_bytes() != jsonl_bytes(state["queue"]):
        raise RuntimeError("BLIND_QUEUE_REBUILD_DRIFT")
    decisions = load_adjudications(adjudications, state["queue"])
    case_metrics = []
    for row in state["selected"]:
        variant = row["variant"]
        case_id = row["case_id"]
        predicted = state["parsed"][(variant, case_id)]
        expected = state["gold"][case_id]
        pairs = list(state["exact_pairs"][(variant, case_id)])
        used_gold = {gold_index for _, gold_index in pairs}
        matched_predictions = {prediction_index for prediction_index, _ in pairs}
        for prediction_index, prediction in enumerate(predicted):
            if prediction_index in matched_predictions:
                continue
            key = (case_id, fact_sha(prediction["fact"]))
            decision = decisions[key]
            if decision["category"] != "SEMANTIC_EQUIVALENT":
                continue
            gold_index = next(
                index
                for index, item in enumerate(expected)
                if item["fact_id"] == decision["matched_gold_fact_id"]
            )
            if gold_index not in used_gold:
                pairs.append((prediction_index, gold_index))
                used_gold.add(gold_index)
        status_correct = speaker_correct = evidence_correct = 0
        for prediction_index, gold_index in pairs:
            prediction = predicted[prediction_index]
            target = expected[gold_index]
            status_correct += prediction.get("status") == target["status"]
            speaker_correct += prediction.get("speaker") == target["speaker"]
            evidence_correct += prediction.get("evidence_ids") == target["evidence_ids"]
        case_metrics.append(
            {
                "variant": variant,
                "case_id": case_id,
                "gold": len(expected),
                "predictions": len(predicted),
                "semantic_tp": len(pairs),
                "status_correct": status_correct,
                "speaker_correct": speaker_correct,
                "evidence_correct": evidence_correct,
            }
        )

    variants = {}
    for variant in VARIANTS:
        group = [row for row in case_metrics if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        variants[variant] = {
            "semantic_recoverable": state["wo"].prf(
                tp, predictions - tp, gold_count - tp
            ),
            "semantic_tp": tp,
            "predictions": predictions,
            "gold": gold_count,
            "status_correct": sum(row["status_correct"] for row in group),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
            "status_accuracy_on_semantic_tp": (
                sum(row["status_correct"] for row in group) / tp if tp else 0.0
            ),
            "speaker_accuracy_on_semantic_tp": (
                sum(row["speaker_correct"] for row in group) / tp if tp else 0.0
            ),
            "evidence_accuracy_on_semantic_tp": (
                sum(row["evidence_correct"] for row in group) / tp if tp else 0.0
            ),
        }
    lora_f1 = variants["LORA_READ2"]["semantic_recoverable"]["f1"]
    base_f1 = variants["BASE_READ2"]["semantic_recoverable"]["f1"]
    passed = lora_f1 >= base_f1
    result = {
        "status": (
            "PASS_READ2_CARRYOVER_TO_NEXT_OUT_COMPARISON"
            if passed
            else "FAIL_READ2_CARRYOVER_STOP"
        ),
        "old_global_status_remains": "FAIL_FULL24_LORA_FORMAT_GATE",
        "raw_sha256": EXPECTED_SHA["full_raw"],
        "gold_sha256": EXPECTED_SHA["gold"],
        "blind_queue_sha256": sha256(QUEUE),
        "adjudications_sha256": sha256(adjudications),
        "semantic_pending": 0,
        "variants": variants,
        "case_metrics": case_metrics,
        "preregistered_rule": "LORA_READ2_F1 >= BASE_READ2_F1",
        "rule_pass": passed,
        "meaning_zh": (
            "只允许 READ2 承接下一组 OUT 对照；不是 READ 赢家，也不自动授权 OUT 执行。"
            if passed
            else "READ2 承接线自动停止。"
        ),
        "api_calls": 0,
    }
    if output.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{output}")
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "base_f1": base_f1,
                "lora_f1": lora_f1,
                "semantic_pending": 0,
                "output_sha256": sha256(output),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify", "final"))
    parser.add_argument("--adjudications", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "verify":
        verify()
    else:
        if args.adjudications is None or args.output is None:
            raise RuntimeError("FINAL_REQUIRES_ADJUDICATIONS_AND_OUTPUT")
        final(args.adjudications, args.output)


if __name__ == "__main__":
    main()
