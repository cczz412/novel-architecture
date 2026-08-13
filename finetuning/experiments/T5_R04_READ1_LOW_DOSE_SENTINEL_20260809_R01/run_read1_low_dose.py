#!/usr/bin/env python3
"""Train READ1 for 48 iterations, then run the update-24/update-48 sentinel."""

from __future__ import annotations

from collections import Counter
import hashlib
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
RUN_ROOT = REPO / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01"
TRAIN_SOURCE = REPO / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01/READ_1_TARGET_TRAIN36.jsonl"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
EVAL_SOURCE = EVAL_ROOT / "READ_1_TARGET_EVAL24.jsonl"
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
TRAIN_SHA = "84ad6f7886b372334b008d49cc2f3343afdd6b98d83a24a00d604ae49b8f09e0"
EVAL_SHA = "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0"
TRAINER_SHA = "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909"
MAX_OUTPUT_TOKENS = 2048
SENTINEL_CASES = ("C02", "C03", "C05", "C08", "C09", "C11", "C01", "C04")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def system_free_percent() -> int:
    output = subprocess.check_output(["memory_pressure"], text=True)
    for line in output.splitlines():
        if line.startswith("System-wide memory free percentage:"):
            return int(line.rsplit(" ", 1)[-1].rstrip("%"))
    raise RuntimeError("MEMORY_PERCENT_UNAVAILABLE")


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    chunks = Counter(compact[index : index + 80] for index in range(0, len(compact) - 79, 8))
    return any(count >= 3 for count in chunks.values())


def fact_texts(raw: str) -> list[str]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        value = None
    if isinstance(value, dict) and isinstance(value.get("facts"), list):
        return [item["fact"] for item in value["facts"] if isinstance(item, dict) and isinstance(item.get("fact"), str)]
    result = []
    for match in re.finditer(r'"fact"\s*:\s*("(?:\\.|[^"\\])*")', raw):
        try:
            result.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    return result


def repetition(raw: str) -> tuple[bool, int]:
    facts = fact_texts(raw)
    duplicates = sum(count - 1 for count in Counter(facts).values() if count > 1)
    return duplicates > 0 or repeated_chunk(raw), duplicates


def config() -> dict[str, Any]:
    return {
        "model": str(MODEL),
        "train": True,
        "data": str(RUN_ROOT / "data"),
        "fine_tune_type": "lora",
        "optimizer": "adam",
        "mask_prompt": True,
        "num_layers": 16,
        "batch_size": 2,
        "iters": 48,
        "val_batches": 0,
        "learning_rate": 0.00003,
        "steps_per_report": 4,
        "steps_per_eval": 48,
        "grad_accumulation_steps": 4,
        "adapter_path": str(RUN_ROOT / "adapters"),
        "save_every": 24,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def prepare() -> None:
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    if RUN_ROOT.exists():
        raise RuntimeError("RUN_ROOT_EXISTS_NO_RETRY")
    if sha256(TRAIN_SOURCE) != TRAIN_SHA or sha256(EVAL_SOURCE) != EVAL_SHA or sha256(TRAINER) != TRAINER_SHA:
        raise RuntimeError("STATIC_SHA_DRIFT")
    train = read_jsonl(TRAIN_SOURCE)
    if len(train) != 36 or sum(len(json.loads(row["messages"][-1]["content"])["facts"]) for row in train) != 714:
        raise RuntimeError("TRAIN36_DENOMINATOR_DRIFT")
    if len(read_jsonl(EVAL_SOURCE)) != 24:
        raise RuntimeError("REAL24_DENOMINATOR_DRIFT")
    (RUN_ROOT / "data").mkdir(parents=True)
    shutil.copyfile(TRAIN_SOURCE, RUN_ROOT / "data/train.jsonl")
    (RUN_ROOT / "config").mkdir()
    (RUN_ROOT / "config/read1_low_dose.yaml").write_text(
        yaml.safe_dump(config(), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def train() -> float:
    if system_free_percent() < 8:
        raise RuntimeError("MEMORY_HARD_STOP_BEFORE_TRAINING")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VENDOR)
    env["PYTHONUNBUFFERED"] = "1"
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(RUN_ROOT / "config/read1_low_dose.yaml")]
    log_path = RUN_ROOT / "training.log"
    began = time.monotonic()
    with log_path.open("x", encoding="utf-8") as log:
        child = subprocess.Popen(
            command,
            cwd=RUN_ROOT,
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
                print(
                    f"LOW_DOSE_TRAIN_PROGRESS iteration={match.group(1)}/48 memory_free={system_free_percent()}%",
                    flush=True,
                )
                if system_free_percent() < 8:
                    child.terminate()
                    child.wait()
                    raise RuntimeError("MEMORY_HARD_STOP_DURING_TRAINING")
        code = child.wait()
    elapsed = round(time.monotonic() - began, 3)
    if code != 0 or "Saved final weights" not in log_path.read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{code}")
    for step in (24, 48):
        checkpoint = RUN_ROOT / f"adapters/{step:07d}_adapters.safetensors"
        if not checkpoint.is_file():
            raise RuntimeError(f"CHECKPOINT_MISSING:{step}")
    return elapsed


def configure_mlx() -> tuple[Any, Any, Any, Any]:
    sys.path.insert(0, str(VENDOR))
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler

    mx.set_wired_limit(20 * 1024**3)
    mx.set_memory_limit(22 * 1024**3)
    mx.set_cache_limit(1 * 1024**3)
    mx.clear_cache()
    return mx, load, stream_generate, make_sampler


def adapter_view(step: int) -> Path:
    view = RUN_ROOT / f"adapter_views/iter{step}"
    view.mkdir(parents=True)
    shutil.copyfile(RUN_ROOT / "adapters/adapter_config.json", view / "adapter_config.json")
    (view / "adapters.safetensors").symlink_to((RUN_ROOT / f"adapters/{step:07d}_adapters.safetensors").resolve())
    return view


def generate_one(
    model: Any,
    tokenizer: Any,
    stream_generate: Any,
    sampler: Any,
    variant: str,
    case_id: str,
    messages: list[dict[str, str]],
    output: Path,
) -> dict[str, Any]:
    if system_free_percent() < 8:
        raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_CASE:{variant}:{case_id}")
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    began = time.monotonic()
    pieces = []
    final = None
    for response in stream_generate(model, tokenizer, prompt=prompt, max_tokens=MAX_OUTPUT_TOKENS, sampler=sampler):
        pieces.append(response.text)
        final = response
    if final is None:
        raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{variant}:{case_id}")
    raw = "".join(pieces)
    is_repetition, duplicates = repetition(raw)
    row = {
        "variant": variant,
        "arm": "READ-1-TARGET",
        "case_id": case_id,
        "raw_output": raw,
        "finish_reason": final.finish_reason,
        "stop_token": int(final.token),
        "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids,
        "generation_tokens_including_stop": int(final.generation_tokens),
        "output_tokens_excluding_stop": len(tokenizer.encode(raw, add_special_tokens=False)),
        "input_tokens": int(final.prompt_tokens),
        "elapsed_seconds": round(time.monotonic() - began, 3),
        "repetition_detected": is_repetition,
        "duplicate_facts": duplicates,
        "token_limit_hit": final.finish_reason == "length" or int(final.generation_tokens) >= MAX_OUTPUT_TOKENS,
    }
    append_jsonl(output, row)
    return row


def run_sentinel() -> dict[str, Any]:
    rows = read_jsonl(EVAL_SOURCE)
    cases = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    by_case = dict(zip(cases, rows, strict=True))
    raw_path = RUN_ROOT / "READ1_LOW_DOSE_RAW.partial.jsonl"
    mx, load, stream_generate, make_sampler = configure_mlx()
    sampler = make_sampler(temp=0.0)
    result: dict[str, Any] = {}
    for step in (24, 48):
        variant = f"READ1_ITER{step}"
        model, tokenizer = load(str(MODEL), adapter_path=str(adapter_view(step)))
        observed = []
        failed = False
        for case_id in SENTINEL_CASES:
            row = generate_one(
                model,
                tokenizer,
                stream_generate,
                sampler,
                variant,
                case_id,
                by_case[case_id]["messages"],
                raw_path,
            )
            observed.append(case_id)
            print(
                f"LOW_DOSE_SENTINEL variant={variant} case={case_id} repetition={row['repetition_detected']} token_limit={row['token_limit_hit']}",
                flush=True,
            )
            if row["repetition_detected"] or row["token_limit_hit"]:
                failed = True
                break
        if not failed:
            for case_id in cases:
                if case_id in observed:
                    continue
                generate_one(
                    model,
                    tokenizer,
                    stream_generate,
                    sampler,
                    variant,
                    case_id,
                    by_case[case_id]["messages"],
                    raw_path,
                )
                observed.append(case_id)
                print(f"LOW_DOSE_FULL_PROGRESS variant={variant} case={case_id} observed={len(observed)}/24", flush=True)
        result[variant] = {
            "status": "FAIL_SENTINEL" if failed else "PASS_SENTINEL_FULL24_COMPLETE",
            "observed_cases": observed,
        }
        del model
        mx.clear_cache()
    return result


def main() -> None:
    prepare()
    elapsed = train()
    sentinel = run_sentinel()
    raw_path = RUN_ROOT / "READ1_LOW_DOSE_RAW.partial.jsonl"
    write_json(
        RUN_ROOT / "RUN_RESULT.json",
        {
            "training_elapsed_seconds": elapsed,
            "checkpoint_sha256": {
                "24": sha256(RUN_ROOT / "adapters/0000024_adapters.safetensors"),
                "48": sha256(RUN_ROOT / "adapters/0000048_adapters.safetensors"),
            },
            "sentinel": sentinel,
            "raw_rows": len(read_jsonl(raw_path)),
            "raw_sha256": sha256(raw_path),
            "api_calls": 0,
            "retry": 0,
        },
    )
    print(json.dumps({"training_elapsed_seconds": elapsed, "sentinel": sentinel}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
