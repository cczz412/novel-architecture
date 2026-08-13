#!/usr/bin/env python3
"""Reuse Round1 scoring for the full READ1 iter-24 low-dose output."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
RUN = REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01"
ROUND1_RUN = REPO / "runs/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_R01"
ROUND1_SCORER = REPO / "finetuning/experiments/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_20260809_R01/score_read_round1.py"
OLD_RAW = ROUND1_RUN / "inference/RAW_OUTPUTS_144.jsonl"
OLD_ADJUDICATIONS = ROUND1_RUN / "semantic_review/SEMANTIC_ADJUDICATIONS_1536.jsonl"
LOW_RAW = RUN / "READ1_LOW_DOSE_RAW.partial.jsonl"
SHADOW_RAW = RUN / "scoring/SHADOW_RAW_144.jsonl"
INHERITED = RUN / "scoring/INHERITED_ADJUDICATIONS.jsonl"
INCREMENTAL = RUN / "semantic_review/INCREMENTAL_ADJUDICATIONS.jsonl"
COMBINED = RUN / "semantic_review/COMBINED_ADJUDICATIONS.jsonl"
OLD_RAW_SHA = "705f1e0df1088aa32ae6e26e9d38dcb86d92226a6fe3b5089033266c2ce2eec4"
OLD_ADJUDICATION_SHA = "5a3c3fe864d78711bc281de055f6405f13aaf142da3a4bd4c181cf7497d9b581"

# Blind decisions use only the queue's case, prediction text, and candidate gold.
# A null value means the prediction is not equivalent to one complete gold fact.
BLIND_DECISIONS: dict[str, str | None] = {
    "3a1ac7a3": "C01-F006", "e0418ca5": "C01-F005", "444c9387": None,
    "1d836473": None, "5fef830a": "C01-F008", "ab90b572": None,
    "d5b7c2cd": None, "d371433f": "C02-F009",
    "846d9d24": "C03-F004", "8a6178d9": "C03-F007", "c0527371": "C03-F008", "8c8f4cae": None,
    "343f7c1b": "C04-F002", "c2cc6f6c": "C04-F006", "83af9e7f": "C04-F007",
    "a22d0b1f": "C04-F008", "c56bf1c4": None, "e1a750d5": None,
    "4fa2606f": "C05-F005", "7e2c29f1": None, "2b8104ca": "C05-F012",
    "4571e961": "C06-F004", "3000508f": "C06-F009", "6bd5aab6": None,
    "999e2eb4": "C06-F015", "b1e67b52": None, "2e66d9df": "C06-F017", "e4095940": "C06-F018",
    "7f372b86": None, "84b5388a": None, "90866220": None, "758659ff": "C09-F009", "539117c1": None,
    "5caedfb9": None, "441892db": "C10-F004", "c8313f77": "C10-F008",
    "dde85a4b": "C10-F009", "c272459c": None, "9222aa70": "C10-F008",
    "49072ba2": "C11-F003", "a06d58bb": "C11-F003", "33826fab": None,
    "3fd09310": "C11-F005", "effd8bd3": "C11-F006", "ff108449": "C11-F007",
    "a9637714": None, "60fcc9b2": None, "24a66927": "C11-F008",
    "1ece9eb7": "C12-F003", "e030048d": None, "95e9687a": None,
    "9e414c39": "C12-F005", "d46edfb0": "C12-F006", "2a2ddfb5": "C12-F007",
    "7ed30a80": None, "9cdbac21": None, "7241dad5": "C12-F010", "0d05ef7b": "C12-F013",
    "2db2efae": None, "ca4b6a4a": None, "3f14e312": None, "fbe0bde9": "C13-F002",
    "0aa29ed4": None, "72c91a9f": "C13-F005", "2f8688e0": None,
    "bbcfadc3": "C14-F003", "c8d82b43": None, "a49649fa": None,
    "cba90189": None, "4984aed5": None, "e256d0f0": "C14-F011",
    "e6d4dd52": "C15-F001", "f864f89b": "C15-F005", "bd9028b9": "C15-F008",
    "03dcba5b": None, "fcd9a999": None, "640b471c": None,
    "52198c5c": None, "259d385b": None, "de48166d": None,
    "20ed386c": None, "85cb22d3": None, "903a4311": None,
    "69bbac0c": "C17-F003", "b3cdbc69": "C17-F010", "a6d737a6": None,
    "4c64b262": None, "799cafa9": None,
    "262e4fab": "C18-F002", "f9c3d9fc": "C18-F005", "4b3f6dce": None, "73e39f2b": "C18-F010",
    "835187ac": "C19-F015", "05d4b97e": None, "43f88021": "C19-F012",
    "79926466": None, "f78f3526": None, "f19fa49a": None, "dbc5ab3a": None,
    "775ad394": "C21-F001", "acb99f04": "C21-F002", "daa9eca3": None,
    "eae90d82": None, "66999f2c": None, "27948612": None, "283fbe08": "C21-F012",
    "2d742b60": "C22-F005", "0d3b357a": "C22-F006", "c7bc9e33": None,
    "eda0742b": "C23-F001", "179c5aa9": None, "a4934738": "C23-F004",
    "03addcc1": "C23-F005", "763914b6": None, "307484a7": None,
    "3a21dcdd": "C24-F001", "cb4dfffb": None, "dbaf3cb6": None,
    "bd2e08c9": "C24-F003", "b3355c92": "C24-F005", "d96041d9": None,
    "e77ed4ab": "C24-F007", "d08e76b2": "C24-F008", "bf2e88c5": None,
    "f92d2344": "C24-F009", "8ac181ef": None, "cba23c0a": "C24-F011",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_scorer() -> Any:
    spec = importlib.util.spec_from_file_location("round1_scorer_for_low_dose", ROUND1_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("ROUND1_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RAW = SHADOW_RAW
    return module


def prepare() -> None:
    if sha256(OLD_RAW) != OLD_RAW_SHA or sha256(OLD_ADJUDICATIONS) != OLD_ADJUDICATION_SHA:
        raise RuntimeError("ROUND1_SCORING_SOURCE_DRIFT")
    old_rows = read_jsonl(OLD_RAW)
    low_rows = [row for row in read_jsonl(LOW_RAW) if row.get("variant") == "READ1_ITER24"]
    if len(low_rows) != 24 or any(row.get("token_limit_hit") or row.get("repetition_detected") for row in low_rows):
        raise RuntimeError("ITER24_NOT_FULL_AND_STABLE")
    replacement = {row["case_id"]: {**row, "variant": "LORA_READ1"} for row in low_rows}
    if len(replacement) != 24:
        raise RuntimeError("ITER24_CASE_DUPLICATE")
    shadow = [replacement[row["case_id"]] if row.get("variant") == "LORA_READ1" else row for row in old_rows]
    write_jsonl(SHADOW_RAW, shadow)
    shadow_sha = sha256(SHADOW_RAW)
    inherited = []
    for row in read_jsonl(OLD_ADJUDICATIONS):
        copied = dict(row)
        copied["raw_sha256"] = shadow_sha
        inherited.append(copied)
    write_jsonl(INHERITED, inherited)
    scorer = load_scorer()
    result = scorer.score(INHERITED)
    queue = result.pop("blind_queue")
    write_json(RUN / "scoring/PRE_METRICS.json", result)
    write_jsonl(RUN / "scoring/BLIND_QUEUE_INCREMENTAL.jsonl", queue)
    print(json.dumps({"shadow_raw_sha256": shadow_sha, "semantic_pending": len(queue)}, ensure_ascii=False))


def adjudicate() -> None:
    queue = read_jsonl(RUN / "scoring/BLIND_QUEUE_INCREMENTAL.jsonl")
    if len(queue) != len(BLIND_DECISIONS):
        raise RuntimeError("BLIND_DECISION_COUNT_MISMATCH")
    rows = []
    seen = set()
    for item in queue:
        matches = [prefix for prefix in BLIND_DECISIONS if item["prediction_fact_sha256"].startswith(prefix)]
        if len(matches) != 1:
            raise RuntimeError(f"BLIND_DECISION_IDENTITY_MISMATCH:{item['prediction_fact_sha256']}")
        prefix = matches[0]
        seen.add(prefix)
        matched = BLIND_DECISIONS[prefix]
        rows.append(
            {
                "case_id": item["case_id"],
                "prediction_fact": item["prediction_fact"],
                "prediction_fact_sha256": item["prediction_fact_sha256"],
                "raw_sha256": item["raw_sha256"],
                "gold_sha256": item["gold_sha256"],
                "category": "SEMANTIC_EQUIVALENT" if matched else "NOT_MATCH",
                "matched_gold_fact_id": matched,
            }
        )
    if seen != set(BLIND_DECISIONS):
        raise RuntimeError("BLIND_DECISION_UNUSED_ENTRY")
    write_jsonl(INCREMENTAL, rows)
    print(json.dumps({"blind_decisions": len(rows)}, ensure_ascii=False))


def final() -> None:
    inherited = read_jsonl(INHERITED)
    incremental = read_jsonl(INCREMENTAL)
    expected = {(row["case_id"], row["prediction_fact_sha256"]) for row in read_jsonl(RUN / "scoring/BLIND_QUEUE_INCREMENTAL.jsonl")}
    actual = {(row.get("case_id"), row.get("prediction_fact_sha256")) for row in incremental}
    if actual != expected or len(incremental) != len(expected):
        raise RuntimeError("INCREMENTAL_ADJUDICATION_COVERAGE_MISMATCH")
    write_jsonl(COMBINED, inherited + incremental)
    scorer = load_scorer()
    result = scorer.score(COMBINED)
    queue = result.pop("blind_queue")
    if queue or result["semantic_pending"] != 0 or not result["semantic_metric_is_final"]:
        raise RuntimeError("FINAL_SCORING_STILL_PENDING")
    write_json(RUN / "scoring/FINAL_METRICS.json", result)
    print(json.dumps({"status": result["status"], "semantic_pending": 0}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "adjudicate", "final"))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "adjudicate":
        adjudicate()
    else:
        final()


if __name__ == "__main__":
    main()
