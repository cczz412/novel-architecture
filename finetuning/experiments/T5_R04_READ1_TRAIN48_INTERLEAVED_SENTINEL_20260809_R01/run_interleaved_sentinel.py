#!/usr/bin/env python3
"""Train the single SM-interleaved iter24 candidate and run its fixed gate."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
RUN = REPO / "runs/T5_R04_READ1_TRAIN48_INTERLEAVED_SENTINEL_R01"
SOURCE_TRAIN = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/READ_1_TARGET_TRAIN48.jsonl"
DERIVED_TRAIN = EXP / "READ_1_TARGET_TRAIN48_INTERLEAVED.jsonl"
BASE_RUNNER = REPO / "finetuning/experiments/T5_R04_READ1_TRAIN48_MIXED_SENTINEL_20260809_R01/run_mixed_sentinel.py"
OLD_RUN = REPO / "runs/T5_R04_READ1_TRAIN48_MIXED_SENTINEL_R01"
SOURCE_SHA = "87d241eee1d37569682b82d858b8fb7848c2e45b91092c7fc2bc99dec9297a98"
TAIL_ORDER = (
    "LC-S01",
    "LC-M06",
    "LC-S02",
    "LC-M05",
    "LC-S03",
    "LC-M04",
    "LC-S04",
    "LC-M03",
    "LC-S05",
    "LC-M02",
    "LC-S06",
    "LC-M01",
)
STEPS = (24,)
REAL8_CASES = ("C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_base_runner() -> Any:
    spec = importlib.util.spec_from_file_location("mixed_sentinel_base_runtime", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("BASE_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_derived() -> dict[str, Any]:
    if sha256(SOURCE_TRAIN) != SOURCE_SHA:
        raise RuntimeError("SOURCE_TRAIN_SHA_DRIFT")
    source_lines = SOURCE_TRAIN.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(source_lines) != 48 or any(not line.endswith("\n") for line in source_lines):
        raise RuntimeError("SOURCE_TRAIN_LINE_DRIFT")
    tail_by_case = {json.loads(line)["metadata"]["case_id"]: line for line in source_lines[36:]}
    if set(tail_by_case) != set(TAIL_ORDER):
        raise RuntimeError("SOURCE_TAIL_CASE_DRIFT")
    derived_text = "".join(source_lines[:36] + [tail_by_case[case_id] for case_id in TAIL_ORDER])
    if DERIVED_TRAIN.exists():
        if DERIVED_TRAIN.read_text(encoding="utf-8") != derived_text:
            raise RuntimeError("DERIVED_TRAIN_DRIFT")
    else:
        DERIVED_TRAIN.write_text(derived_text, encoding="utf-8")
    derived_lines = DERIVED_TRAIN.read_text(encoding="utf-8").splitlines(keepends=True)
    if derived_lines[:36] != source_lines[:36]:
        raise RuntimeError("FIRST36_BYTES_CHANGED")
    if Counter(source_lines) != Counter(derived_lines):
        raise RuntimeError("CONTENT_MULTISET_CHANGED")
    rows = read_jsonl(DERIVED_TRAIN)
    if [row["metadata"]["case_id"] for row in rows[36:]] != list(TAIL_ORDER):
        raise RuntimeError("DERIVED_TAIL_ORDER_DRIFT")
    source_gold = {row["metadata"]["case_id"]: row["messages"][-1]["content"] for row in read_jsonl(SOURCE_TRAIN)}
    derived_gold = {row["metadata"]["case_id"]: row["messages"][-1]["content"] for row in rows}
    if source_gold != derived_gold:
        raise RuntimeError("GOLD_CHANGED")
    return {
        "source_sha256": sha256(SOURCE_TRAIN),
        "derived_sha256": sha256(DERIVED_TRAIN),
        "rows": len(rows),
        "facts": sum(len(json.loads(row["messages"][-1]["content"])["facts"]) for row in rows),
        "first36_byte_identical": True,
        "content_multiset_identical": True,
        "gold_identical_by_case": True,
        "tail_order": list(TAIL_ORDER),
    }


def configured_base() -> Any:
    evidence = build_derived()
    base = load_base_runner()
    base.RUN = RUN
    base.TRAIN = DERIVED_TRAIN
    base.EXPECTED_SHA.pop(SOURCE_TRAIN, None)
    base.EXPECTED_SHA[DERIVED_TRAIN] = evidence["derived_sha256"]
    base.SENTINEL_CASES = REAL8_CASES
    original_config = base.config

    def iter24_config() -> dict[str, Any]:
        value = original_config()
        value["iters"] = 24
        value["save_every"] = 24
        return value

    base.config = iter24_config
    return base


def prepare() -> None:
    evidence = build_derived()
    evidence["runner_sha256"] = sha256(Path(__file__))
    evidence["scorer_sha256"] = sha256(EXP / "score_interleaved_sentinel.py")
    base = configured_base()
    base.prepare()
    write_json(EXP / "ORDER_CHECK.json", evidence)


def train() -> None:
    base = configured_base()
    base.static_check()
    if not (RUN / "PREPARE.json").is_file() or (RUN / "training.log").exists():
        raise RuntimeError("TRAIN_STATE_INVALID_NO_RETRY")
    runtime = base.load_old_runner()
    if runtime.system_free_percent() < 8:
        raise RuntimeError("MEMORY_HARD_STOP_BEFORE_TRAINING")
    base.no_other_training_process()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(base.VENDOR)
    env["PYTHONUNBUFFERED"] = "1"
    command = [str(base.PYTHON), "-m", "mlx_lm.lora", "--config", str(RUN / "config/read1_train48_mixed.yaml")]
    began = time.monotonic()
    with (RUN / "training.log").open("x", encoding="utf-8") as log:
        child = subprocess.Popen(
            command,
            cwd=RUN,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        assert child.stdout is not None
        for line in child.stdout:
            log.write(line)
            log.flush()
            match = re.search(r"Iter (\d+):", line)
            if match:
                free = runtime.system_free_percent()
                print(f"INTERLEAVED_TRAIN iteration={match.group(1)}/24 memory_free={free}%", flush=True)
                if free < 8:
                    child.terminate()
                    child.wait()
                    raise RuntimeError("MEMORY_HARD_STOP_DURING_TRAINING")
        code = child.wait()
    elapsed = round(time.monotonic() - began, 3)
    log_text = (RUN / "training.log").read_text(encoding="utf-8", errors="replace")
    if code != 0 or "Saved final weights" not in log_text:
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{code}")
    checkpoint = RUN / "adapters/0000024_adapters.safetensors"
    if not checkpoint.is_file():
        raise RuntimeError("CHECKPOINT_24_MISSING")
    write_json(
        RUN / "TRAINING_RESULT.json",
        {
            "elapsed_seconds": elapsed,
            "checkpoint_sha256": {"24": sha256(checkpoint)},
            "only_iteration_24_trained": True,
            "retry": 0,
            "api_calls": 0,
        },
    )
    print(
        json.dumps(
            {"status": "TRAINED_ITER24_ONLY", "elapsed_seconds": elapsed, "checkpoint_sha256": sha256(checkpoint)},
            ensure_ascii=False,
        )
    )


def output_for_step(step: int) -> Path:
    if step != 24:
        raise RuntimeError("ONLY_ITER24_AUTHORIZED")
    return RUN / "PROBE24_RAW.jsonl"


def eval_gate() -> None:
    base = configured_base()
    if not (RUN / "TRAINING_RESULT.json").is_file():
        raise RuntimeError("TRAINING_NOT_COMPLETE")
    output = output_for_step(24)
    inherited_output = RUN / "INITIAL_RAW.jsonl"
    real8_output = RUN / "REAL8_MIXED24_RAW.jsonl"
    if any(path.exists() for path in (output, inherited_output, real8_output)):
        raise RuntimeError("EVAL_OUTPUT_EXISTS_NO_RETRY")
    runtime = base.load_old_runner()
    _, load, stream_generate, make_sampler = runtime.configure_mlx()
    sampler = make_sampler(temp=0.0)
    inherited = [
        row
        for row in base.read_jsonl(OLD_RUN / "INITIAL_RAW.jsonl")
        if row["variant"] in {"BASE_L6", "DENSE24_L6"}
    ]
    if len(inherited) != 12:
        raise RuntimeError("BASE_DENSE_L6_REUSE_DRIFT")
    base.write_jsonl(inherited_output, inherited)
    base.generate_group(
        runtime,
        load,
        stream_generate,
        sampler,
        "MIXED24_L6",
        base.read_jsonl(base.L6_EVAL),
        output,
        base.adapter_view(24),
    )
    base.generate_group(
        runtime,
        load,
        stream_generate,
        sampler,
        "MIXED24_REAL_SENTINEL",
        base.real_rows_for_cases(REAL8_CASES),
        output,
        base.adapter_view(24),
    )
    rows = base.read_jsonl(output)
    if len(rows) != 14:
        raise RuntimeError("EVAL14_ROW_COUNT_DRIFT")
    real8 = [row for row in rows if row["variant"] == "MIXED24_REAL_SENTINEL"]
    if [row["case_id"] for row in real8] != list(REAL8_CASES):
        raise RuntimeError("REAL8_ORDER_DRIFT")
    base.write_jsonl(real8_output, real8)
    write_json(
        RUN / "EVAL14_24_RESULT.json",
        {
            "step": 24,
            "mixed_rows": len(rows),
            "raw_sha256": sha256(output),
            "real8_raw_sha256": sha256(real8_output),
            "repetition_rows": sum(row["repetition_detected"] for row in rows),
            "token_limit_rows": sum(row["token_limit_hit"] for row in rows),
            "duplicate_facts": sum(row["duplicate_facts"] for row in rows),
            "retry": 0,
            "api_calls": 0,
        },
    )


def eval_full(step: int) -> None:
    if step != 24:
        raise RuntimeError("FULL_STEP_INVALID")
    configured_base().eval_full(step)


def status() -> None:
    result = {"derived_train": build_derived(), "run_exists": RUN.exists(), "steps": {}}
    for step in STEPS:
        raw = output_for_step(step)
        result["steps"][str(step)] = {"raw_exists": raw.exists(), "raw_sha256": sha256(raw) if raw.is_file() else None}
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "train", "eval-gate", "eval-full", "status"))
    parser.add_argument("--step", type=int, choices=STEPS)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "train":
        train()
    elif args.command == "eval-gate":
        eval_gate()
    elif args.command == "eval-full":
        if args.step is None:
            parser.error("eval-full requires --step")
        eval_full(args.step)
    else:
        status()


if __name__ == "__main__":
    main()
