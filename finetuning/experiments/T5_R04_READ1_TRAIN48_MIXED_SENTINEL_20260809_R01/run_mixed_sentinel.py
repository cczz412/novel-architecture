#!/usr/bin/env python3
"""Train one READ1 TRAIN48 LoRA and run the fixed mixed-data sentinels."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

import yaml


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
RUN = REPO / "runs/T5_R04_READ1_TRAIN48_MIXED_SENTINEL_R01"
TRAIN = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/READ_1_TARGET_TRAIN48.jsonl"
L6_EVAL = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/READ_1_TARGET_L6_EVAL.jsonl"
L6_GOLD = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01/L6_GOLD_6.jsonl"
REAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
REAL_EVAL = REAL_ROOT / "READ_1_TARGET_EVAL24.jsonl"
REAL_GOLD = REAL_ROOT / "REAL24_GOLD_24.jsonl"
REAL_SOURCE = REAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
OLD_RUNNER = REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/run_read1_low_dose.py"
DENSE_ADAPTER = REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/adapters/0000024_adapters.safetensors"
DENSE_VIEW = REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/adapter_views/iter24"
MAX_OUTPUT_TOKENS = 2048
SENTINEL_CASES = ("C02", "C03", "C05", "C08", "C09", "C11", "C01", "C04")
EXPECTED_SHA = {
    TRAIN: "87d241eee1d37569682b82d858b8fb7848c2e45b91092c7fc2bc99dec9297a98",
    L6_EVAL: "e96b8b5abb565f63e9bd3c2354c3a2a7366a4a646fb262379844c3fc32fb2503",
    L6_GOLD: "79ab2bf95aef439d3183d6cb1df3a59f6a3f706275714974fd4ed256469ba579",
    REAL_EVAL: "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0",
    REAL_GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    REAL_SOURCE: "0fe7ecb1649b93e4faab3d253d8904bee7f1a7a3e6f7f0fbb8b8e722c405de97",
    DENSE_ADAPTER: "7b01e203e45beb9562e55dff902bc0ecfd56c312f5a0a679c69813014ed14b1f",
    TRAINER: "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909",
    OLD_RUNNER: "db9ae2a2c33dbbe3539f86fa9e45645e8dda6267ac42b5484b6b042290d80245",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_old_runner() -> Any:
    spec = importlib.util.spec_from_file_location("read1_low_dose_runtime", OLD_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("OLD_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def static_check() -> None:
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    for path, expected in EXPECTED_SHA.items():
        if sha256(path) != expected:
            raise RuntimeError(f"STATIC_SHA_DRIFT:{path}")
    train = read_jsonl(TRAIN)
    if len(train) != 48 or sum(len(json.loads(row["messages"][-1]["content"])["facts"]) for row in train) != 762:
        raise RuntimeError("TRAIN48_DENOMINATOR_DRIFT")
    l6 = read_jsonl(L6_EVAL)
    if len(l6) != 6 or any(len(row["messages"]) != 2 for row in l6):
        raise RuntimeError("L6_INPUT_DRIFT")
    if any(row["metadata"].get("forbidden_from_training") is not True for row in l6):
        raise RuntimeError("L6_TRAINING_FIREWALL_DRIFT")
    if len(read_jsonl(REAL_EVAL)) != 24 or len(read_jsonl(REAL_GOLD)) != 24:
        raise RuntimeError("REAL24_DENOMINATOR_DRIFT")


def config() -> dict[str, Any]:
    return {
        "model": str(MODEL),
        "train": True,
        "data": str(RUN / "data"),
        "fine_tune_type": "lora",
        "optimizer": "adam",
        "mask_prompt": True,
        "num_layers": 16,
        "batch_size": 2,
        "iters": 96,
        "val_batches": 0,
        "learning_rate": 0.00003,
        "steps_per_report": 4,
        "steps_per_eval": 48,
        "grad_accumulation_steps": 4,
        "adapter_path": str(RUN / "adapters"),
        "save_every": 24,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def prepare() -> None:
    static_check()
    if RUN.exists():
        raise RuntimeError("RUN_ROOT_EXISTS_NO_RETRY")
    (RUN / "data").mkdir(parents=True)
    shutil.copyfile(TRAIN, RUN / "data/train.jsonl")
    (RUN / "config").mkdir()
    (RUN / "config/read1_train48_mixed.yaml").write_text(
        yaml.safe_dump(config(), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    write_json(
        RUN / "PREPARE.json",
        {
            "train_sha256": sha256(TRAIN),
            "train_rows": 48,
            "train_facts": 762,
            "l6_sha256": sha256(L6_EVAL),
            "l6_gold_sha256": sha256(L6_GOLD),
            "real24_sha256": sha256(REAL_EVAL),
            "real24_gold_sha256": sha256(REAL_GOLD),
            "dense_iter24_adapter_sha256": sha256(DENSE_ADAPTER),
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "PREPARED", "train_rows": 48, "train_facts": 762}, ensure_ascii=False))


def no_other_training_process() -> None:
    check = subprocess.run(["pgrep", "-fl", "mlx_lm.lora"], text=True, capture_output=True, check=False)
    if check.returncode == 0 and check.stdout.strip():
        raise RuntimeError(f"OTHER_MLX_LORA_PROCESS:{check.stdout.strip()}")


def train() -> None:
    static_check()
    if not (RUN / "PREPARE.json").is_file() or (RUN / "training.log").exists():
        raise RuntimeError("TRAIN_STATE_INVALID_NO_RETRY")
    runtime = load_old_runner()
    if runtime.system_free_percent() < 8:
        raise RuntimeError("MEMORY_HARD_STOP_BEFORE_TRAINING")
    no_other_training_process()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VENDOR)
    env["PYTHONUNBUFFERED"] = "1"
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(RUN / "config/read1_train48_mixed.yaml")]
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
                print(f"MIXED_TRAIN_PROGRESS iteration={match.group(1)}/96 memory_free={free}%", flush=True)
                if free < 8:
                    child.terminate()
                    child.wait()
                    raise RuntimeError("MEMORY_HARD_STOP_DURING_TRAINING")
        code = child.wait()
    elapsed = round(time.monotonic() - began, 3)
    log_text = (RUN / "training.log").read_text(encoding="utf-8", errors="replace")
    if code != 0 or "Saved final weights" not in log_text:
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{code}")
    checkpoint_sha = {}
    for step in (24, 48, 72, 96):
        checkpoint = RUN / f"adapters/{step:07d}_adapters.safetensors"
        if not checkpoint.is_file():
            raise RuntimeError(f"CHECKPOINT_MISSING:{step}")
        checkpoint_sha[str(step)] = sha256(checkpoint)
    write_json(
        RUN / "TRAINING_RESULT.json",
        {"elapsed_seconds": elapsed, "checkpoint_sha256": checkpoint_sha, "retry": 0, "api_calls": 0},
    )
    print(json.dumps({"status": "TRAINED", "elapsed_seconds": elapsed, "checkpoint_sha256": checkpoint_sha}))


def adapter_view(step: int) -> Path:
    view = RUN / f"adapter_views/mixed{step}"
    if view.exists():
        return view
    view.mkdir(parents=True)
    shutil.copyfile(RUN / "adapters/adapter_config.json", view / "adapter_config.json")
    checkpoint = (RUN / f"adapters/{step:07d}_adapters.safetensors").resolve()
    (view / "adapters.safetensors").symlink_to(checkpoint)
    return view


def generate_group(
    runtime: Any,
    load: Any,
    stream_generate: Any,
    sampler: Any,
    variant: str,
    rows: list[dict[str, Any]],
    output: Path,
    adapter: Path | None,
) -> None:
    args = {"adapter_path": str(adapter)} if adapter is not None else {}
    model, tokenizer = load(str(MODEL), **args)
    for index, row in enumerate(rows, 1):
        case_id = row["metadata"]["case_id"]
        result = runtime.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            variant,
            case_id,
            row["messages"],
            output,
        )
        print(
            f"MIXED_INFER variant={variant} case={case_id} observed={index}/{len(rows)} "
            f"repetition={result['repetition_detected']} token_limit={result['token_limit_hit']}",
            flush=True,
        )
    del model
    runtime.configure_mlx()[0].clear_cache()


def real_rows_for_cases(case_ids: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
    requests = read_jsonl(REAL_EVAL)
    cases = [row["case_id"] for row in read_jsonl(REAL_SOURCE)]
    by_case = dict(zip(cases, requests, strict=True))
    return [{"metadata": {"case_id": case_id}, "messages": by_case[case_id]["messages"]} for case_id in case_ids]


def eval_initial() -> None:
    static_check()
    if not (RUN / "TRAINING_RESULT.json").is_file():
        raise RuntimeError("TRAINING_NOT_COMPLETE")
    output = RUN / "INITIAL_RAW.jsonl"
    if output.exists():
        raise RuntimeError("INITIAL_RAW_EXISTS_NO_RETRY")
    runtime = load_old_runner()
    _, load, stream_generate, make_sampler = runtime.configure_mlx()
    sampler = make_sampler(temp=0.0)
    l6 = read_jsonl(L6_EVAL)
    generate_group(runtime, load, stream_generate, sampler, "BASE_L6", l6, output, None)
    generate_group(runtime, load, stream_generate, sampler, "DENSE24_L6", l6, output, DENSE_VIEW)
    generate_group(runtime, load, stream_generate, sampler, "MIXED96_L6", l6, output, adapter_view(96))
    generate_group(
        runtime,
        load,
        stream_generate,
        sampler,
        "MIXED96_REAL_SENTINEL",
        real_rows_for_cases(SENTINEL_CASES),
        output,
        adapter_view(96),
    )
    rows = read_jsonl(output)
    if len(rows) != 26:
        raise RuntimeError("INITIAL_RAW_COUNT_DRIFT")
    write_json(
        RUN / "INITIAL_RESULT.json",
        {
            "rows": 26,
            "raw_sha256": sha256(output),
            "repetition_rows": sum(row["repetition_detected"] for row in rows),
            "token_limit_rows": sum(row["token_limit_hit"] for row in rows),
            "retry": 0,
            "api_calls": 0,
        },
    )


def eval_fallback72() -> None:
    static_check()
    output = RUN / "FALLBACK72_RAW.jsonl"
    if output.exists():
        raise RuntimeError("FALLBACK72_RAW_EXISTS_NO_RETRY")
    runtime = load_old_runner()
    _, load, stream_generate, make_sampler = runtime.configure_mlx()
    sampler = make_sampler(temp=0.0)
    generate_group(runtime, load, stream_generate, sampler, "MIXED72_L6", read_jsonl(L6_EVAL), output, adapter_view(72))
    generate_group(
        runtime,
        load,
        stream_generate,
        sampler,
        "MIXED72_REAL_SENTINEL",
        real_rows_for_cases(SENTINEL_CASES),
        output,
        adapter_view(72),
    )
    rows = read_jsonl(output)
    if len(rows) != 14:
        raise RuntimeError("FALLBACK72_RAW_COUNT_DRIFT")
    write_json(
        RUN / "FALLBACK72_RESULT.json",
        {
            "rows": 14,
            "raw_sha256": sha256(output),
            "repetition_rows": sum(row["repetition_detected"] for row in rows),
            "token_limit_rows": sum(row["token_limit_hit"] for row in rows),
            "retry": 0,
            "api_calls": 0,
        },
    )


def eval_probe(step: int) -> None:
    if step not in {24, 48}:
        raise RuntimeError("PROBE_STEP_INVALID")
    static_check()
    output = RUN / f"PROBE{step}_RAW.jsonl"
    if output.exists():
        raise RuntimeError("PROBE_RAW_EXISTS_NO_RETRY")
    runtime = load_old_runner()
    _, load, stream_generate, make_sampler = runtime.configure_mlx()
    sampler = make_sampler(temp=0.0)
    generate_group(
        runtime,
        load,
        stream_generate,
        sampler,
        f"MIXED{step}_L6",
        read_jsonl(L6_EVAL),
        output,
        adapter_view(step),
    )
    generate_group(
        runtime,
        load,
        stream_generate,
        sampler,
        f"MIXED{step}_REAL_SENTINEL",
        real_rows_for_cases(SENTINEL_CASES),
        output,
        adapter_view(step),
    )
    rows = read_jsonl(output)
    if len(rows) != 14:
        raise RuntimeError("PROBE_RAW_COUNT_DRIFT")
    write_json(
        RUN / f"PROBE{step}_RESULT.json",
        {
            "step": step,
            "rows": 14,
            "raw_sha256": sha256(output),
            "repetition_rows": sum(row["repetition_detected"] for row in rows),
            "token_limit_rows": sum(row["token_limit_hit"] for row in rows),
            "duplicate_facts": sum(row["duplicate_facts"] for row in rows),
            "retry": 0,
            "api_calls": 0,
        },
    )


def probe_raw_path(step: int) -> Path:
    if step == 96:
        return RUN / "INITIAL_RAW.jsonl"
    if step == 72:
        return RUN / "FALLBACK72_RAW.jsonl"
    if step in {24, 48}:
        return RUN / f"PROBE{step}_RAW.jsonl"
    raise RuntimeError("PROBE_STEP_INVALID")


def eval_full(step: int) -> None:
    if step not in {24, 48, 72, 96}:
        raise RuntimeError("FULL_STEP_INVALID")
    source_path = probe_raw_path(step)
    source_variant = f"MIXED{step}_REAL_SENTINEL"
    observed = [row for row in read_jsonl(source_path) if row["variant"] == source_variant]
    if len(observed) != 8:
        raise RuntimeError("SENTINEL_ROWS_NOT_AVAILABLE")
    generated_path = RUN / f"REAL24_MIXED{step}_NEW16.jsonl"
    final_path = RUN / f"REAL24_MIXED{step}.jsonl"
    if generated_path.exists() or final_path.exists():
        raise RuntimeError("FULL_OUTPUT_EXISTS_NO_RETRY")
    remaining = [f"C{index:02d}" for index in range(1, 25) if f"C{index:02d}" not in SENTINEL_CASES]
    runtime = load_old_runner()
    _, load, stream_generate, make_sampler = runtime.configure_mlx()
    sampler = make_sampler(temp=0.0)
    generate_group(
        runtime,
        load,
        stream_generate,
        sampler,
        f"MIXED{step}_REAL",
        real_rows_for_cases(remaining),
        generated_path,
        adapter_view(step),
    )
    all_rows = [{**row, "variant": f"MIXED{step}_REAL"} for row in observed] + read_jsonl(generated_path)
    by_case = {row["case_id"]: row for row in all_rows}
    if len(by_case) != 24:
        raise RuntimeError("FULL_CASE_COVERAGE_DRIFT")
    canonical = [by_case[f"C{index:02d}"] for index in range(1, 25)]
    write_jsonl(final_path, canonical)
    write_json(
        RUN / f"REAL24_MIXED{step}_RESULT.json",
        {
            "rows": 24,
            "reused_sentinel_rows": 8,
            "new_inference_rows": 16,
            "raw_sha256": sha256(final_path),
            "repetition_rows": sum(row["repetition_detected"] for row in canonical),
            "token_limit_rows": sum(row["token_limit_hit"] for row in canonical),
            "duplicate_facts": sum(row["duplicate_facts"] for row in canonical),
            "retry": 0,
            "api_calls": 0,
        },
    )


def status() -> None:
    result = {"run_exists": RUN.exists(), "files": {}}
    for name in (
        "PREPARE.json",
        "TRAINING_RESULT.json",
        "INITIAL_RAW.jsonl",
        "FALLBACK72_RAW.jsonl",
        "PROBE24_RAW.jsonl",
        "PROBE48_RAW.jsonl",
        "REAL24_MIXED96.jsonl",
        "REAL24_MIXED72.jsonl",
        "REAL24_MIXED48.jsonl",
        "REAL24_MIXED24.jsonl",
    ):
        path = RUN / name
        result["files"][name] = {"exists": path.exists(), "sha256": sha256(path) if path.is_file() else None}
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("prepare", "train", "eval-initial", "eval-fallback72", "eval-probe", "eval-full", "status"),
    )
    parser.add_argument("--step", type=int, choices=(24, 48, 72, 96))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "train":
        train()
    elif args.command == "eval-initial":
        eval_initial()
    elif args.command == "eval-fallback72":
        eval_fallback72()
    elif args.command == "eval-probe":
        if args.step not in {24, 48}:
            parser.error("eval-probe requires --step 24 or 48")
        eval_probe(args.step)
    elif args.command == "eval-full":
        if args.step is None:
            parser.error("eval-full requires --step")
        eval_full(args.step)
    else:
        status()


if __name__ == "__main__":
    main()
