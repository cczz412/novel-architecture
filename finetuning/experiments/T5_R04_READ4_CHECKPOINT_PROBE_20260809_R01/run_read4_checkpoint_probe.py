#!/usr/bin/env python3
"""Run the READ4 update-96/update-192 inference-only checkpoint probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
RUN_ROOT = REPO / "runs/T5_R04_READ4_CHECKPOINT_PROBE_20260809_R01"
ROUND1 = REPO / "runs/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_R01"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
INPUT = EVAL_ROOT / "READ_4_FULL_CHAPTER_EVAL24.jsonl"
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
ADAPTER_SOURCE = ROUND1 / "adapters/read4"
CONFIG_SOURCE = ADAPTER_SOURCE / "adapter_config.json"
INPUT_SHA = "350799084dbc15791bc3b46a669552aec2da7920bfa39c8a3a110e1cbe431d4f"
CONFIG_SHA = "4a3af7836caac3fd36de1ab8c43ce085f80ab59fe95bcc294148feaca5562c41"
CHECKPOINTS = {
    "READ4_96": (
        ADAPTER_SOURCE / "0000096_adapters.safetensors",
        "1f63ec8caddedaf5f5c0531453e37dee1eceae0f873c5cf93dfce1de2234f36d",
    ),
    "READ4_192": (
        ADAPTER_SOURCE / "0000192_adapters.safetensors",
        "d470086c4e821d975e56150add4e74668c1e96e8782f42929b70ca076cc5f40f",
    ),
}
MAX_OUTPUT_TOKENS = 2048


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()


def system_free_percent() -> int:
    output = subprocess.check_output(["memory_pressure"], text=True)
    for line in output.splitlines():
        if line.startswith("System-wide memory free percentage:"):
            return int(line.rsplit(" ", 1)[-1].rstrip("%"))
    raise RuntimeError("MEMORY_PERCENT_UNAVAILABLE")


def verify_inputs() -> tuple[list[dict[str, Any]], list[str]]:
    if sha256(INPUT) != INPUT_SHA or sha256(CONFIG_SOURCE) != CONFIG_SHA:
        raise RuntimeError("STATIC_INPUT_SHA_DRIFT")
    for path, expected in CHECKPOINTS.values():
        if sha256(path) != expected:
            raise RuntimeError(f"CHECKPOINT_SHA_DRIFT:{path}")
    rows = read_jsonl(INPUT)
    cases = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    if len(rows) != 24 or cases != [f"C{i:02d}" for i in range(1, 25)]:
        raise RuntimeError("REAL24_CASE_ORDER_DRIFT")
    if any(len(row.get("messages", [])) != 2 for row in rows):
        raise RuntimeError("EVAL_MESSAGES_NOT_TWO")
    return rows, cases


def build_views() -> dict[str, Path]:
    views: dict[str, Path] = {}
    for variant, (checkpoint, _) in CHECKPOINTS.items():
        view = RUN_ROOT / "adapter_views" / variant
        if view.exists():
            raise RuntimeError(f"VIEW_EXISTS_NO_OVERWRITE:{view}")
        view.mkdir(parents=True)
        shutil.copyfile(CONFIG_SOURCE, view / "adapter_config.json")
        (view / "adapters.safetensors").symlink_to(checkpoint.resolve())
        if sha256(view / "adapters.safetensors") != sha256(checkpoint):
            raise RuntimeError(f"VIEW_CHECKPOINT_DRIFT:{variant}")
        views[variant] = view
    return views


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-192", action="store_true")
    args = parser.parse_args()
    output = RUN_ROOT / "READ4_CHECKPOINT_RAW_48.jsonl"
    partial = RUN_ROOT / "READ4_CHECKPOINT_RAW_48.partial.jsonl"
    rows, cases = verify_inputs()
    if args.resume_192:
        view = RUN_ROOT / "adapter_views/READ4_192"
        if output.exists() or not partial.is_file() or not view.is_dir():
            raise RuntimeError("RESUME_192_STATE_INVALID")
        existing = read_jsonl(partial)
        if any(row.get("variant") == "READ4_192" for row in existing):
            raise RuntimeError("READ4_192_ALREADY_STARTED_NO_RETRY")
        if sha256(view / "adapter_config.json") != CONFIG_SHA:
            raise RuntimeError("READ4_192_VIEW_CONFIG_DRIFT")
        if sha256(view / "adapters.safetensors") != CHECKPOINTS["READ4_192"][1]:
            raise RuntimeError("READ4_192_VIEW_CHECKPOINT_DRIFT")
        views = {"READ4_192": view}
    else:
        if RUN_ROOT.exists() or output.exists() or partial.exists():
            raise RuntimeError("PROBE_RUN_ROOT_EXISTS_NO_RETRY")
        views = build_views()
    mx, load, stream_generate, make_sampler = configure_mlx()
    sampler = make_sampler(temp=0.0)
    for variant, view in views.items():
        if system_free_percent() < 8:
            raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_VARIANT:{variant}")
        model, tokenizer = load(str(MODEL), adapter_path=str(view))
        for index, (case_id, row) in enumerate(zip(cases, rows, strict=True), 1):
            if system_free_percent() < 8:
                raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_CASE:{variant}:{case_id}")
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
                raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{variant}:{case_id}")
            raw = "".join(pieces)
            append_jsonl(
                partial,
                {
                    "variant": variant,
                    "arm": "READ-4-FULL-CHAPTER",
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
            print(f"CHECKPOINT_INFER_PROGRESS variant={variant} case={index}/24", flush=True)
        del model
        mx.clear_cache()
    observed = read_jsonl(partial)
    if args.resume_192:
        if sum(row["variant"] == "READ4_192" for row in observed) != 24:
            raise RuntimeError("READ4_192_OUTPUT_NOT_24")
        print(f"READ4_192_INFERENCE_COMPLETE partial_sha256={sha256(partial)}", flush=True)
    else:
        if len(observed) != 48:
            raise RuntimeError("PROBE_OUTPUT_NOT_48")
        partial.rename(output)
        print(f"CHECKPOINT_PROBE_INFERENCE_COMPLETE sha256={sha256(output)}", flush=True)


if __name__ == "__main__":
    main()
