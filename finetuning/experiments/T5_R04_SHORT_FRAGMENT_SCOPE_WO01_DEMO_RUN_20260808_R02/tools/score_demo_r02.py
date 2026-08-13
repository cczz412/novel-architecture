#!/usr/bin/env python3
"""Minimal R02 scorer with recoverable and structured semantic layers."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[4]
R01_SCORER = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/tools/score_demo.py"


def load_r01():
    spec = importlib.util.spec_from_file_location("wo01_demo_r01_scorer", R01_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("R01_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recoverable_parse(module, raw: str) -> tuple[bool, list[dict]]:
    """Keep fact objects when the JSON root and facts array are readable."""
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        return False, []
    schema_valid = not list(Draft202012Validator(module.read_json(module.SCHEMA)).iter_errors(value))
    if not isinstance(value, dict) or not isinstance(value.get("facts"), list):
        return schema_valid, []
    recovered = [item for item in value["facts"] if isinstance(item, dict) and isinstance(item.get("fact"), str)]
    return schema_valid, recovered


def root_facts_readable(raw: str) -> bool:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        return False
    return isinstance(value, dict) and isinstance(value.get("facts"), list)


def adjudication_set_index(module, base_index, path: Path | None, raw_sha: str, canonical: dict) -> dict:
    if path is None or path.suffix == ".jsonl":
        return base_index(path, raw_sha, canonical)
    manifest = module.read_json(path)
    if set(manifest) != {"files", "status"} or manifest["status"] != "FROZEN_R02_ADJUDICATION_SET":
        raise RuntimeError("ADJUDICATION_SET_INVALID")
    merged = {}
    for relative in manifest["files"]:
        current = base_index(REPO / relative, raw_sha, canonical)
        overlap = set(merged) & set(current)
        if overlap:
            raise RuntimeError(f"ADJUDICATION_SET_OVERLAP:{sorted(overlap)}")
        merged.update(current)
    return merged


def score(raw_path: Path, adjudications: Path | None) -> dict:
    module = load_r01()
    original_parse = module.parse
    original_adjudication_index = module.adjudication_index
    module.adjudication_index = lambda path, raw_sha, canonical: adjudication_set_index(
        module, original_adjudication_index, path, raw_sha, canonical
    )
    structured = module.score(raw_path, adjudications)
    module.parse = lambda raw: recoverable_parse(module, raw)
    try:
        recoverable = module.score(raw_path, adjudications)
    finally:
        module.parse = original_parse
        module.adjudication_index = original_adjudication_index

    raw_rows = module.read_jsonl(raw_path)
    by_arm = {}
    for arm in module.ARMS:
        recoverable_arm = recoverable["arms"][arm]
        structured_arm = structured["arms"][arm]
        by_arm[arm] = {
            "semantic_recoverable": recoverable_arm["semantic"],
            "semantic_structured": structured_arm["semantic"],
            "strict_structured": structured_arm["strict"],
            "recoverable_prediction_count": recoverable_arm["semantic"]["tp"] + recoverable_arm["semantic"]["fp"],
            "structured_prediction_count": structured_arm["semantic"]["tp"] + structured_arm["semantic"]["fp"],
            "json_root_and_facts_readable": sum(
                root_facts_readable(row["raw_output"]) for row in raw_rows if row["arm"] == arm
            ),
            "schema_valid": recoverable_arm["schema_valid"],
            "status_correct": recoverable_arm["status_correct"],
            "speaker_correct": recoverable_arm["speaker_correct"],
            "evidence_correct": recoverable_arm["evidence_correct"],
            "semantic_matches": recoverable_arm["semantic_matches"],
            "empty_false_positive_cases": recoverable_arm["empty_false_positive_cases"],
            "duplicate_facts": recoverable_arm["duplicate_facts"],
            "token_limit_cases": recoverable_arm["token_limit_cases"],
            "clean_stop_cases": recoverable_arm["clean_stop_cases"],
            "output_tokens": recoverable_arm["output_tokens"],
        }

    structured_cases = {(row["arm"], row["case_id"]): row for row in structured["case_metrics"]}
    case_metrics = []
    for row in recoverable["case_metrics"]:
        old = structured_cases[(row["arm"], row["case_id"])]
        common = {key: value for key, value in row.items() if key not in {"predictions", "semantic_tp", "strict_tp"}}
        case_metrics.append(
            {
                **common,
                "recoverable_predictions": row["predictions"],
                "semantic_recoverable_tp": row["semantic_tp"],
                "structured_predictions": old["predictions"],
                "semantic_structured_tp": old["semantic_tp"],
                "strict_structured_tp": old["strict_tp"],
            }
        )

    return {
        "status": recoverable["status"],
        "scoring_contract": "SEMANTIC_RECOVERABLE_MAIN_SCHEMA_SEPARATE",
        "raw_sha256": recoverable["raw_sha256"],
        "semantic_pending": recoverable["semantic_pending"],
        "arms": by_arm,
        "case_metrics": case_metrics,
        "blind_queue": recoverable["blind_queue"],
        "model_called_by_scorer": False,
    }


def main() -> None:
    module = load_r01()
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.raw, args.adjudications)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    queue = result.pop("blind_queue")
    module.write_json(args.output_dir / "METRICS.json", result)
    module.write_jsonl(args.output_dir / "BLIND_QUEUE.jsonl", queue)
    canonical = module.canonical_map()
    casebook = [
        {"case_id": case_id, "source": canonical[case_id]["source"], "gold": module.gold(canonical[case_id])}
        for case_id in sorted({row["case_id"] for row in queue})
    ]
    module.write_jsonl(args.output_dir / "BLIND_CASEBOOK.jsonl", casebook)
    module.write_json(
        args.output_dir / "SCORING_RECEIPT.json",
        {
            "status": result["status"],
            "scoring_contract": result["scoring_contract"],
            "raw_sha256": result["raw_sha256"],
            "semantic_pending": result["semantic_pending"],
            "metrics_sha256": module.sha256(args.output_dir / "METRICS.json"),
            "blind_queue_sha256": module.sha256(args.output_dir / "BLIND_QUEUE.jsonl"),
            "api_calls": 0,
            "training_started": False,
        },
    )
    print(json.dumps({"status": result["status"], "semantic_pending": result["semantic_pending"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
