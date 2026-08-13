#!/usr/bin/env python3
"""Run the authorized WO-01 local Demo; no API, no training, zero retry."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
INPUT = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
ADAPTER = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/eval_adapters/c2_full/update_72"
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
ARMS = ("TARGET_ONLY", "SMALL_HALO", "CURRENT_WINDOW")
REQUESTS = {arm: INPUT / f"sealed_inputs_candidate/{arm}_REQUESTS_24.jsonl" for arm in ARMS}
SIDECAR = INPUT / "sealed_inputs_candidate/HIDDEN_REQUEST_SIDECAR_72.jsonl"
EXPECTED = {
    "input_manifest": "e4efced726b066002cb91630b77d21ef7a22cf2eb05ef7e4aca59a2482ae694f",
    "adapter": "321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9",
    "adapter_config": "72df68a7d01b8feae8f92cc0e4f69c832d9ad71886b4f8ea2896a7436d73031e",
    "model_receipt": "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6",
}
MAX_OUTPUT_TOKENS = 1024


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_bytes())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def stable_row_sha(row: dict) -> str:
    payload = (json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_bytes(b"".join((json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode() for row in rows))


def verify_sources() -> None:
    checks = {
        INPUT / "OUTPUT_MANIFEST.json": EXPECTED["input_manifest"],
        ADAPTER / "adapters.safetensors": EXPECTED["adapter"],
        ADAPTER / "adapter_config.json": EXPECTED["adapter_config"],
        MODEL / "MODEL_RECEIPT.json": EXPECTED["model_receipt"],
    }
    for path, expected in checks.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"SOURCE_IDENTITY_DRIFT:{path}")
    receipt = read_json(MODEL / "MODEL_RECEIPT.json")
    if receipt.get("status") != "COMPLETE_VERIFIED" or receipt.get("revision") != "cdbee75f17c01a7cc42f958dc650907174af0554":
        raise RuntimeError("BASE_MODEL_RECEIPT_INVALID")


def load_plan() -> list[dict]:
    verify_sources()
    hidden = {(row["arm"], row["row_index"]): row for row in read_jsonl(SIDECAR)}
    if len(hidden) != 72:
        raise RuntimeError("HIDDEN_SIDECAR_NOT_72")
    plan = []
    for arm in ARMS:
        rows = read_jsonl(REQUESTS[arm])
        if len(rows) != 24:
            raise RuntimeError(f"REQUEST_COUNT_NOT_24:{arm}")
        for row_index, request in enumerate(rows):
            messages = request.get("messages")
            if len(messages or []) != 2 or [row.get("role") for row in messages] != ["system", "user"]:
                raise RuntimeError(f"REQUEST_NOT_SYSTEM_USER:{arm}:{row_index}")
            sidecar = hidden[(arm, row_index)]
            if stable_row_sha(request) != sidecar["model_visible_request_sha256"]:
                raise RuntimeError(f"REQUEST_SIDECAR_DRIFT:{arm}:{row_index}")
            visible = json.dumps(request, ensure_ascii=False)
            if any(token in visible for token in (sidecar["case_id"], '"arm"', '"gold"')):
                raise RuntimeError(f"MODEL_VISIBLE_HIDDEN_FIELD_LEAK:{arm}:{row_index}")
            plan.append({"arm": arm, "row_index": row_index, "case_id": sidecar["case_id"], "request_sha256": sidecar["model_visible_request_sha256"], "gold_binding_sha256": sidecar["gold_binding_sha256"], "messages": messages})
    return plan


def memory_free_percent() -> int:
    output = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, check=False).stdout
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", output)
    return int(match.group(1)) if match else -1


def require_memory() -> None:
    free = memory_free_percent()
    if free < 8:
        raise RuntimeError(f"MEMORY_HARD_STOP:{free}")


def selected_plan(mode: str) -> list[dict]:
    plan = load_plan()
    if mode == "smoke":
        return [plan[0], plan[48]]
    return plan


def run(mode: str, output_dir: Path) -> None:
    if output_dir.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{output_dir}")
    output_dir.mkdir(parents=True)
    plan = selected_plan(mode)
    started = time.monotonic()
    try:
        require_memory()
        sys.path.insert(0, str(VENDOR))
        import mlx.core as mx
        from mlx_lm import load
        from mlx_lm.generate import stream_generate
        from mlx_lm.sample_utils import make_sampler

        mx.set_wired_limit(20 * 1024**3)
        mx.set_memory_limit(22 * 1024**3)
        mx.set_cache_limit(1 * 1024**3)
        mx.clear_cache()
        model, tokenizer = load(str(MODEL), adapter_path=str(ADAPTER))
        sampler = make_sampler(temp=0.0)
        outputs = []
        for sequence_index, item in enumerate(plan, start=1):
            require_memory()
            prompt = tokenizer.apply_chat_template(item["messages"], tokenize=False, add_generation_prompt=True)
            if item["messages"][0]["content"] not in prompt or item["messages"][1]["content"] not in prompt:
                raise RuntimeError("SYSTEM_OR_USER_DROPPED_FROM_PROMPT")
            pieces, final = [], None
            for response in stream_generate(model, tokenizer, prompt=prompt, max_tokens=MAX_OUTPUT_TOKENS, sampler=sampler):
                pieces.append(response.text)
                final = response
            if final is None:
                raise RuntimeError("EMPTY_GENERATION")
            outputs.append({"sequence_index": sequence_index, "arm": item["arm"], "row_index": item["row_index"], "case_id": item["case_id"], "request_sha256": item["request_sha256"], "gold_binding_sha256": item["gold_binding_sha256"], "raw_output": "".join(pieces), "finish_reason": final.finish_reason, "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids, "output_tokens": int(final.generation_tokens)})
            mx.clear_cache()
        raw = output_dir / "RAW_OUTPUTS.jsonl"
        write_jsonl(raw, outputs)
        write_json(output_dir / "RUN_RECEIPT.json", {"status": "PASS_DEMO_INFERENCE_COMPLETE", "mode": mode, "rows": len(outputs), "arms": {arm: sum(row["arm"] == arm for row in outputs) for arm in ARMS}, "raw_sha256": sha256(raw), "checkpoint_sha256": EXPECTED["adapter"], "decode": {"greedy": True, "temperature": 0.0, "max_output_tokens": 1024, "retry": 0}, "elapsed_seconds": round(time.monotonic() - started, 3), "model_loaded": True, "api_calls": 0, "training_started": False})
    except BaseException as error:
        write_json(output_dir / "ABORT_RECEIPT.json", {"status": "HARD_STOP_NO_RETRY", "mode": mode, "error_type": type(error).__name__, "error": str(error), "retry": 0, "api_calls": 0, "training_started": False})
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("validate", "smoke", "full"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.mode == "validate":
        print(json.dumps({"status": "PASS_DEMO_INPUTS", "rows": len(load_plan()), "model_loaded": False}, ensure_ascii=False))
        return
    if args.output_dir is None:
        parser.error("smoke/full 需要 --output-dir")
    run(args.mode, args.output_dir)


if __name__ == "__main__":
    main()
