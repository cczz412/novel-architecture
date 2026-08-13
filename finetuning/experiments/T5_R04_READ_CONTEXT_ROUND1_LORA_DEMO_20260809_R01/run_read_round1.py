#!/usr/bin/env python3
"""READ Round1: three independent LoRA trainings plus matched base/LoRA inference."""

from __future__ import annotations

import argparse
from datetime import datetime
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
EXP = Path(__file__).resolve().parent
RUN_ROOT = REPO / "runs/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_R01"
TRAIN_ROOT = REPO / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
EXPECTED_TRAINER_SHA = "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
MAX_SEQUENCE_LENGTH = 4608
MAX_OUTPUT_TOKENS = 2048
ARMS = ("read1", "read2", "read4")
ARM_LABELS = {
    "read1": "READ-1-TARGET",
    "read2": "READ-2-HALO180",
    "read4": "READ-4-FULL-CHAPTER",
}
VARIANT_SUFFIX = {"read1": "READ1", "read2": "READ2", "read4": "READ4"}
TRAIN_PATHS = {
    "read1": TRAIN_ROOT / "READ_1_TARGET_TRAIN36.jsonl",
    "read2": TRAIN_ROOT / "READ_2_HALO180_TRAIN36.jsonl",
    "read4": TRAIN_ROOT / "READ_4_FULL_CHAPTER_TRAIN36.jsonl",
}
TRAIN_SHA = {
    "read1": "84ad6f7886b372334b008d49cc2f3343afdd6b98d83a24a00d604ae49b8f09e0",
    "read2": "09fdbc52f7131f1a2a60552740ce28430e418ed84c858f0f997abda16e4a7c5e",
    "read4": "93b3ab7e9beed9a6f54df751400ba2ac65cfd5a18f1865da01c7c0c81540ed4a",
}
EVAL_PATHS = {
    "read1": EVAL_ROOT / "READ_1_TARGET_EVAL24.jsonl",
    "read2": EVAL_ROOT / "READ_2_HALO180_EVAL24.jsonl",
    "read4": EVAL_ROOT / "READ_4_FULL_CHAPTER_EVAL24.jsonl",
}
EVAL_SHA = {
    "read1": "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0",
    "read2": "a12f1f5cb1adfed4958418bfa8373af52b6305fdef64122c9bf02e3338c77e85",
    "read4": "350799084dbc15791bc3b46a669552aec2da7920bfa39c8a3a110e1cbe431d4f",
}
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise RuntimeError(f"OUTPUT_EXISTS:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()


def system_free_percent() -> int:
    result = subprocess.run(["memory_pressure", "-Q"], text=True, capture_output=True, check=False)
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else -1


def memory_snapshot() -> dict[str, Any]:
    swap = subprocess.run(["sysctl", "-n", "vm.swapusage"], text=True, capture_output=True, check=False)
    return {"free_percent": system_free_percent(), "swap": swap.stdout.strip()}


def active_lora_processes() -> list[int]:
    result = subprocess.run(["pgrep", "-f", r"[m]lx_lm.*lora"], text=True, capture_output=True, check=False)
    return [int(item) for item in result.stdout.split() if item.isdigit()]


def train_identity(arm: str) -> dict[str, Any]:
    path = TRAIN_PATHS[arm]
    rows = read_jsonl(path)
    cases = [row.get("metadata", {}).get("case_id") for row in rows]
    facts = 0
    for row in rows:
        if [message.get("role") for message in row.get("messages", [])] != ["system", "user", "assistant"]:
            raise RuntimeError(f"TRAIN_MESSAGE_SHAPE_DRIFT:{arm}")
        facts += len(json.loads(row["messages"][-1]["content"])["facts"])
    if len(rows) != 36 or len(set(cases)) != 36 or facts != 714:
        raise RuntimeError(f"TRAIN_DENOMINATOR_DRIFT:{arm}:{len(rows)}:{len(set(cases))}:{facts}")
    return {"path": str(path), "sha256": sha256(path), "rows": len(rows), "facts": facts, "case_order": cases}


def eval_identity(arm: str) -> dict[str, Any]:
    path = EVAL_PATHS[arm]
    rows = read_jsonl(path)
    cases = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    if len(rows) != 24 or cases != [f"C{i:02d}" for i in range(1, 25)]:
        raise RuntimeError(f"EVAL_DENOMINATOR_DRIFT:{arm}")
    if any([message.get("role") for message in row.get("messages", [])] != ["system", "user"] for row in rows):
        raise RuntimeError(f"EVAL_MESSAGE_SHAPE_DRIFT:{arm}")
    return {"path": str(path), "sha256": sha256(path), "rows": 24, "case_order": cases}


def runtime_train_path(arm: str) -> Path:
    return RUN_ROOT / "data" / arm / "train.jsonl"


def adapter_dir(arm: str) -> Path:
    return RUN_ROOT / "adapters" / arm


def config_path(arm: str) -> Path:
    return RUN_ROOT / "config" / f"{arm}.yaml"


def training_log(arm: str) -> Path:
    return RUN_ROOT / "logs" / f"{arm}.log"


def config_values(arm: str) -> dict[str, Any]:
    return {
        "model": str(MODEL),
        "train": True,
        "data": str(runtime_train_path(arm).parent),
        "fine_tune_type": "lora",
        "optimizer": "adam",
        "mask_prompt": True,
        "num_layers": 16,
        "batch_size": 2,
        "iters": 288,
        "val_batches": 0,
        "learning_rate": 0.00003,
        "steps_per_report": 4,
        "steps_per_eval": 48,
        "grad_accumulation_steps": 4,
        "adapter_path": str(adapter_dir(arm)),
        "save_every": 96,
        "max_seq_length": MAX_SEQUENCE_LENGTH,
        "grad_checkpoint": True,
        "seed": 20260802,
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def verify_static_inputs() -> dict[str, Any]:
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    if sha256(TRAINER) != EXPECTED_TRAINER_SHA:
        raise RuntimeError("M1_TRAINER_SHA_DRIFT")
    receipt = json.loads((MODEL / "MODEL_RECEIPT.json").read_text(encoding="utf-8"))
    if receipt.get("status") != "COMPLETE_VERIFIED":
        raise RuntimeError("BASE_MODEL_NOT_VERIFIED")
    train = {}
    evaluation = {}
    for arm in ARMS:
        if sha256(TRAIN_PATHS[arm]) != TRAIN_SHA[arm]:
            raise RuntimeError(f"TRAIN_SHA_DRIFT:{arm}")
        if sha256(EVAL_PATHS[arm]) != EVAL_SHA[arm]:
            raise RuntimeError(f"EVAL_SHA_DRIFT:{arm}")
        train[arm] = train_identity(arm)
        evaluation[arm] = eval_identity(arm)
    if len({tuple(value["case_order"]) for value in train.values()}) != 1:
        raise RuntimeError("TRAIN_CASE_ORDER_CROSS_ARM_DRIFT")
    return {"train": train, "evaluation": evaluation}


def full_sequence_lengths() -> dict[str, Any]:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True, trust_remote_code=True)
    by_arm: dict[str, list[int]] = {}
    for arm in ARMS:
        counts = []
        for row in read_jsonl(TRAIN_PATHS[arm]):
            rendered = tokenizer.apply_chat_template(
                row["messages"], tokenize=False, add_generation_prompt=False
            )
            counts.append(len(tokenizer.encode(rendered, add_special_tokens=False)))
        if max(counts) > MAX_SEQUENCE_LENGTH:
            raise RuntimeError(f"TRAIN_SEQUENCE_TRUNCATION_RISK:{arm}:{max(counts)}")
        by_arm[arm] = counts
    return {
        arm: {"min": min(values), "max": max(values), "mean": round(sum(values) / len(values), 3)}
        for arm, values in by_arm.items()
    }


def prepare() -> None:
    if RUN_ROOT.exists():
        raise RuntimeError(f"RUN_ROOT_EXISTS_NO_OVERWRITE:{RUN_ROOT}")
    identities = verify_static_inputs()
    lengths = full_sequence_lengths()
    RUN_ROOT.mkdir(parents=True)
    for arm in ARMS:
        target = runtime_train_path(arm)
        target.parent.mkdir(parents=True)
        shutil.copyfile(TRAIN_PATHS[arm], target)
        if sha256(target) != TRAIN_SHA[arm]:
            raise RuntimeError(f"RUNTIME_TRAIN_COPY_DRIFT:{arm}")
        config_path(arm).parent.mkdir(parents=True, exist_ok=True)
        config_path(arm).write_text(
            yaml.safe_dump(config_values(arm), allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    write_json(
        RUN_ROOT / "PREPARE_RECEIPT.json",
        {
            "status": "READY_FOR_SERIAL_READ_ROUND1",
            "created_at": now(),
            "arm_order": list(ARMS),
            "same_original_base": {"path": str(MODEL), "revision": MODEL_REVISION},
            "identities": identities,
            "full_training_sequence_tokens": lengths,
            "recipe": config_values("read1") | {"data": "PER_ARM", "adapter_path": "PER_ARM"},
            "api_calls": 0,
            "training_authorized": True,
        },
    )
    write_json(
        RUN_ROOT / "RUN_STATE.json",
        {"status": "READY_FOR_TRAINING", "completed_training_arms": [], "completed_inference_variants": []},
    )
    print(json.dumps({"status": "PASS_PREPARE", "lengths": lengths}, ensure_ascii=False))


def update_state(**values: Any) -> None:
    path = RUN_ROOT / "RUN_STATE.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state.update(values, updated_at=now())
    write_json(path, state, replace=True)


def train_one(arm: str) -> None:
    if active_lora_processes():
        raise RuntimeError(f"OTHER_LORA_PROCESS_ACTIVE:{active_lora_processes()}")
    if system_free_percent() < 8:
        raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_ARM:{arm}")
    if adapter_dir(arm).exists() or training_log(arm).exists():
        raise RuntimeError(f"TRAIN_OUTPUT_EXISTS_NO_RETRY:{arm}")
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(config_path(arm))]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VENDOR)
    env["PYTHONUNBUFFERED"] = "1"
    training_log(arm).parent.mkdir(parents=True, exist_ok=True)
    update_state(status="TRAINING", active_arm=arm, completed_iterations=0)
    print(f"READ_TRAIN_START arm={arm} memory_free={system_free_percent()}%", flush=True)
    began = time.monotonic()
    with training_log(arm).open("x", encoding="utf-8") as log:
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
                iteration = int(match.group(1))
                update_state(status="TRAINING", active_arm=arm, completed_iterations=iteration)
                print(f"READ_TRAIN_PROGRESS arm={arm} iteration={iteration}/288 memory_free={system_free_percent()}%", flush=True)
                if system_free_percent() < 8:
                    child.terminate()
                    child.wait()
                    update_state(status="HARD_STOP_MEMORY", active_arm=arm, completed_iterations=iteration)
                    raise RuntimeError(f"MEMORY_HARD_STOP_DURING_ARM:{arm}:{iteration}")
        code = child.wait()
    log_text = training_log(arm).read_text(encoding="utf-8", errors="replace")
    if code != 0 or "Saved final weights" not in log_text:
        update_state(status="HARD_STOP_TRAINING_FAILURE", active_arm=arm, return_code=code)
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{arm}:{code}")
    required = [adapter_dir(arm) / f"{iteration:07d}_adapters.safetensors" for iteration in (96, 192, 288)]
    required += [adapter_dir(arm) / "adapters.safetensors", adapter_dir(arm) / "adapter_config.json"]
    if not all(path.is_file() and path.stat().st_size > 0 for path in required):
        raise RuntimeError(f"TRAINING_ARTIFACT_MISSING:{arm}")
    receipt = {
        "status": "PASS_TRAINING_COMPLETE",
        "arm": arm,
        "label": ARM_LABELS[arm],
        "completed_at": now(),
        "elapsed_seconds": round(time.monotonic() - began, 3),
        "source_train_sha256": TRAIN_SHA[arm],
        "final_adapter_sha256": sha256(adapter_dir(arm) / "adapters.safetensors"),
        "checkpoint_sha256": {
            str(iteration): sha256(adapter_dir(arm) / f"{iteration:07d}_adapters.safetensors")
            for iteration in (96, 192, 288)
        },
        "memory_after": memory_snapshot(),
        "api_calls": 0,
        "retry": 0,
    }
    write_json(RUN_ROOT / "receipts" / f"{arm}_TRAINING.json", receipt)
    state = json.loads((RUN_ROOT / "RUN_STATE.json").read_text(encoding="utf-8"))
    completed = state.get("completed_training_arms", [])
    completed.append(arm)
    update_state(status="BETWEEN_TRAINING_ARMS", active_arm=None, completed_iterations=288, completed_training_arms=completed)
    print(f"READ_TRAIN_COMPLETE arm={arm} elapsed={receipt['elapsed_seconds']}s", flush=True)


def train_all() -> None:
    verify_static_inputs()
    state = json.loads((RUN_ROOT / "RUN_STATE.json").read_text(encoding="utf-8"))
    if state.get("status") != "READY_FOR_TRAINING":
        raise RuntimeError(f"TRAIN_ALL_BAD_STATE:{state.get('status')}")
    for arm in ARMS:
        train_one(arm)
    update_state(status="TRAINING_COMPLETE_PENDING_INFERENCE", active_arm=None)
    print("READ_ALL_TRAINING_COMPLETE", flush=True)


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


def generate_rows(model: Any, tokenizer: Any, stream_generate: Any, sampler: Any, arm: str, prefix: str, partial: Path) -> None:
    cases = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    rows = read_jsonl(EVAL_PATHS[arm])
    for index, (case_id, row) in enumerate(zip(cases, rows, strict=True), 1):
        if system_free_percent() < 8:
            raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_CASE:{prefix}:{arm}:{case_id}")
        prompt = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=True)
        began = time.monotonic()
        pieces: list[str] = []
        final = None
        for response in stream_generate(
            model, tokenizer, prompt=prompt, max_tokens=MAX_OUTPUT_TOKENS, sampler=sampler
        ):
            pieces.append(response.text)
            final = response
        if final is None:
            raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{prefix}:{arm}:{case_id}")
        raw = "".join(pieces)
        append_jsonl(
            partial,
            {
                "variant": f"{prefix}_{VARIANT_SUFFIX[arm]}",
                "arm": ARM_LABELS[arm],
                "case_id": case_id,
                "raw_output": raw,
                "finish_reason": final.finish_reason,
                "stop_token": int(final.token),
                "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids,
                "generation_tokens_including_stop": int(final.generation_tokens),
                "output_tokens_excluding_stop": len(tokenizer.encode(raw, add_special_tokens=False)),
                "input_tokens": int(final.prompt_tokens),
                "elapsed_seconds": round(time.monotonic() - began, 3),
            },
        )
        print(f"READ_INFER_PROGRESS variant={prefix}_{VARIANT_SUFFIX[arm]} case={index}/24", flush=True)


def finalize_partial(partial: Path, final: Path, expected_rows: int) -> None:
    if final.exists() or not partial.is_file():
        raise RuntimeError(f"INFERENCE_OUTPUT_STATE_INVALID:{final}")
    rows = read_jsonl(partial)
    if len(rows) != expected_rows:
        raise RuntimeError(f"INFERENCE_ROW_COUNT_DRIFT:{partial}:{len(rows)}")
    partial.rename(final)


def infer_base_all() -> None:
    verify_static_inputs()
    output = RUN_ROOT / "inference/BASE_RAW_OUTPUTS.jsonl"
    partial = output.with_suffix(".partial.jsonl")
    if output.exists() or partial.exists():
        raise RuntimeError("BASE_INFERENCE_EXISTS_NO_RETRY")
    mx, load, stream_generate, make_sampler = configure_mlx()
    update_state(status="INFER_BASE", active_arm="base")
    model, tokenizer = load(str(MODEL))
    sampler = make_sampler(temp=0.0)
    for arm in ARMS:
        generate_rows(model, tokenizer, stream_generate, sampler, arm, "BASE", partial)
        mx.clear_cache()
    finalize_partial(partial, output, 72)
    del model
    mx.clear_cache()
    update_state(status="BASE_INFERENCE_COMPLETE_PENDING_LORA", active_arm=None, completed_inference_variants=[f"BASE_{VARIANT_SUFFIX[arm]}" for arm in ARMS])
    print(f"READ_BASE_INFERENCE_COMPLETE sha256={sha256(output)}", flush=True)


def infer_lora_all() -> None:
    verify_static_inputs()
    base_output = RUN_ROOT / "inference/BASE_RAW_OUTPUTS.jsonl"
    output = RUN_ROOT / "inference/LORA_RAW_OUTPUTS.jsonl"
    partial = output.with_suffix(".partial.jsonl")
    combined = RUN_ROOT / "inference/RAW_OUTPUTS_144.jsonl"
    if not base_output.is_file() or output.exists() or partial.exists() or combined.exists():
        raise RuntimeError("LORA_INFERENCE_OUTPUT_STATE_INVALID")
    mx, load, stream_generate, make_sampler = configure_mlx()
    sampler = make_sampler(temp=0.0)
    update_state(status="INFER_LORA", active_arm=ARMS[0])
    for arm in ARMS:
        receipt = RUN_ROOT / "receipts" / f"{arm}_TRAINING.json"
        if not receipt.is_file():
            raise RuntimeError(f"TRAINING_RECEIPT_MISSING:{arm}")
        update_state(status="INFER_LORA", active_arm=arm)
        model, tokenizer = load(str(MODEL), adapter_path=str(adapter_dir(arm)))
        generate_rows(model, tokenizer, stream_generate, sampler, arm, "LORA", partial)
        del model
        mx.clear_cache()
    finalize_partial(partial, output, 72)
    combined.write_bytes(base_output.read_bytes() + output.read_bytes())
    if len(read_jsonl(combined)) != 144:
        raise RuntimeError("COMBINED_144_ROW_DRIFT")
    update_state(status="INFERENCE_COMPLETE_PENDING_SCORING", active_arm=None, completed_inference_variants=[f"{prefix}_{VARIANT_SUFFIX[arm]}" for prefix in ("BASE", "LORA") for arm in ARMS])
    print(f"READ_LORA_INFERENCE_COMPLETE combined_sha256={sha256(combined)}", flush=True)


def status() -> None:
    state_path = RUN_ROOT / "RUN_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"status": "NOT_PREPARED"}
    active = state.get("active_arm")
    tail: list[str] = []
    if active in ARMS and training_log(active).is_file():
        tail = training_log(active).read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
    payload = {
        "state": state,
        "memory": memory_snapshot(),
        "active_lora_processes": active_lora_processes(),
        "training_log_tail": tail,
        "raw_rows": {
            path.name: len(read_jsonl(path))
            for path in (RUN_ROOT / "inference").glob("*.jsonl")
            if path.is_file()
        } if (RUN_ROOT / "inference").is_dir() else {},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "train-all", "infer-base-all", "infer-lora-all", "status"))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "train-all":
        train_all()
    elif args.command == "infer-base-all":
        infer_base_all()
    elif args.command == "infer-lora-all":
        infer_lora_all()
    else:
        status()


if __name__ == "__main__":
    main()
