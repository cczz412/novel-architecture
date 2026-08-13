#!/usr/bin/env python3
"""Build matched Set A train and Set B dev rows for the three WO-01 arms."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
WORK = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT"
TRAIN_CANONICAL = WORK / "inspection/T5_R04_SYNTHETIC_MICRO24_R01/canonical/CANONICAL_MICRO24.jsonl"
DEV_CANONICAL = WORK / "set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808/canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
C2_TRAIN = WORK / "inspection/T5_R04_SYNTHETIC_MICRO24_R01/rendered/C2_FULL_ID_LIST_TRAIN_24.jsonl"
RENDERER_PATH = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01/tools/wo01_renderer.py"
ARMS = ("TARGET_ONLY", "SMALL_HALO", "CURRENT_WINDOW")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS:{path}")
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def load_renderer():
    spec = importlib.util.spec_from_file_location("wo01_renderer_matched", RENDERER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("WO01_RENDERER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CASE_ID_PATTERN = re.compile(r"^MICRO24(?:B)?-S\d{2}$")
    return module


def gold_value(sample: dict) -> dict:
    return {
        "facts": [
            {
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence"]["unit_ids"],
            }
            for fact in sample["facts"]
        ]
    }


def build_split(renderer, samples: list[dict], split: str, system_prompt: str) -> dict[str, list[dict]]:
    result = {arm: [] for arm in ARMS}
    for sample in samples:
        assistant = json.dumps(gold_value(sample), ensure_ascii=False, separators=(",", ":"))
        for arm in ARMS:
            visible = renderer.render_model_visible(sample, arm, system_prompt)
            if renderer.contains_forbidden_visible_metadata(visible):
                raise RuntimeError(f"VISIBLE_METADATA_LEAK:{split}:{sample['case_id']}:{arm}")
            result[arm].append(
                {
                    "case_id": sample["case_id"],
                    "messages": [*visible["messages"], {"role": "assistant", "content": assistant}],
                    "metadata": {
                        "format_arm": "C2_FULL_ID_LIST",
                        "scope_arm": arm,
                        "set_role": "TRAIN24_SET_A_ENGINEERING_ONLY" if split == "train" else "DEV24_SET_B_R03_DO_NOT_TRAIN",
                    },
                }
            )
    return result


def validate_matched(train: dict[str, list[dict]], dev: dict[str, list[dict]]) -> dict:
    for split, arms, expected_facts in (("train", train, 43), ("dev", dev, 48)):
        base = arms[ARMS[0]]
        if len(base) != 24 or len({row["case_id"] for row in base}) != 24:
            raise RuntimeError(f"{split.upper()}_CASE_DENOMINATOR")
        order = [row["case_id"] for row in base]
        gold = [row["messages"][-1]["content"] for row in base]
        if sum(len(json.loads(item)["facts"]) for item in gold) != expected_facts:
            raise RuntimeError(f"{split.upper()}_FACT_DENOMINATOR")
        for arm in ARMS[1:]:
            if [row["case_id"] for row in arms[arm]] != order:
                raise RuntimeError(f"{split.upper()}_ORDER_DRIFT:{arm}")
            if [row["messages"][-1]["content"] for row in arms[arm]] != gold:
                raise RuntimeError(f"{split.upper()}_GOLD_DRIFT:{arm}")
    train_ids = {row["case_id"] for row in train[ARMS[0]]}
    dev_ids = {row["case_id"] for row in dev[ARMS[0]]}
    if train_ids & dev_ids:
        raise RuntimeError("SET_B_MIXED_INTO_TRAIN")
    return {"train_rows_each": 24, "train_facts_each": 43, "dev_rows_each": 24, "dev_facts_each": 48, "train_dev_case_overlap": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=EXP / "data")
    args = parser.parse_args()
    if args.output_root.exists():
        raise RuntimeError(f"OUTPUT_ROOT_EXISTS:{args.output_root}")
    renderer = load_renderer()
    train_samples = read_jsonl(TRAIN_CANONICAL)
    dev_samples = read_jsonl(DEV_CANONICAL)
    system_prompt = read_jsonl(C2_TRAIN)[0]["messages"][0]["content"]
    train = build_split(renderer, train_samples, "train", system_prompt)
    dev = build_split(renderer, dev_samples, "dev", system_prompt)
    counts = validate_matched(train, dev)
    for arm in ARMS:
        write_jsonl(args.output_root / "source_train" / f"{arm}.jsonl", train[arm])
        write_jsonl(args.output_root / "dev" / f"{arm}.jsonl", dev[arm])
    receipt = {
        "status": "PASS_MATCHED_3X24_TRAIN_AND_DEV_RENDERED",
        "arms": list(ARMS),
        "counts": counts,
        "train_canonical_sha256": sha256(TRAIN_CANONICAL),
        "dev_canonical_sha256": sha256(DEV_CANONICAL),
        "renderer_sha256": sha256(RENDERER_PATH),
        "system_prompt_source_sha256": sha256(C2_TRAIN),
        "files": {
            split: {arm: {"path": str(args.output_root / folder / f"{arm}.jsonl"), "sha256": sha256(args.output_root / folder / f"{arm}.jsonl")} for arm in ARMS}
            for split, folder in (("train", "source_train"), ("dev", "dev"))
        },
    }
    write_json(EXP / "INPUT_BUILD_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
