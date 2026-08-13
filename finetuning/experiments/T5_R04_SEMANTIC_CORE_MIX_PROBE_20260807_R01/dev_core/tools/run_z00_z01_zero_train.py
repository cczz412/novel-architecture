#!/usr/bin/env python3
"""Run the frozen DEV_CORE Z00/Z01 base-model diagnostic serially."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any


EXPERIMENT = Path(__file__).resolve().parents[2]
DEV = Path(__file__).resolve().parents[1]
SEALED = DEV / "sealed_r01"
OUT = DEV / "zero_training_r01"
STATE = OUT / "RUN_STATE.json"
LOCK = OUT / "RUN_LOCK.json"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
MAX_OUTPUT_TOKENS = 2048
EXPECTED = {
    "Z00": {
        "questions": SEALED / "Z00_BASE_A_CORE_QUESTIONS.jsonl",
        "sha256": "8414eda33f94a84bfa1f8ecffc3d878dd2816a2fa7754705606b49332cb173d2",
    },
    "Z01": {
        "questions": SEALED / "Z01_BASE_C2_CORE_QUESTIONS.jsonl",
        "sha256": "3c94ccdc6d41efe5305e5105e062793fd3b3bb142938bd82183790da9f2ec665",
    },
}
GOLD = SEALED / "CORE_GOLD.jsonl"
GOLD_SHA256 = "90f68035708aa8dbfba609799a49f655a45c0cfb56e9af4e4c3085257a0e8494"


def now() -> str:
    return datetime.now().astimezone().isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def system_free_percent() -> int:
    output = subprocess.check_output(["vm_stat"], text=True)
    match = re.search(r"page size of (\d+) bytes", output)
    page_size = int(match.group(1)) if match else 16384
    values: dict[str, int] = {}
    for line in output.splitlines():
        found = re.match(r"([^:]+):\s+(\d+)\.", line)
        if found:
            values[found.group(1)] = int(found.group(2))
    free_pages = sum(
        values.get(key, 0)
        for key in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable")
    )
    total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
    return round(100 * free_pages * page_size / total)


def validate_format(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"json_valid": False, "schema_valid": False, "parsed": None, "errors": [f"invalid_json:{exc.msg}"]}
    errors: list[str] = []
    if not isinstance(value, dict) or set(value) != {"fact_sentences"}:
        errors.append("top_level_schema")
    facts = value.get("fact_sentences") if isinstance(value, dict) else None
    if not isinstance(facts, list) or not all(isinstance(item, str) and item.strip() for item in facts):
        errors.append("fact_sentences_schema")
    return {
        "json_valid": True,
        "schema_valid": not errors,
        "parsed": value if not errors else None,
        "errors": errors,
    }


def check_frozen_inputs() -> dict[str, Any]:
    model_receipt = json.loads(MODEL_RECEIPT.read_text(encoding="utf-8"))
    if model_receipt.get("status") != "COMPLETE_VERIFIED":
        raise RuntimeError("MODEL_RECEIPT_NOT_VERIFIED")
    if model_receipt.get("repo_id") != "Qwen/Qwen3-4B-Instruct-2507":
        raise RuntimeError("MODEL_REPO_ID_DRIFT")
    if model_receipt.get("revision") != MODEL_REVISION:
        raise RuntimeError("MODEL_REVISION_DRIFT")
    if sha256(GOLD) != GOLD_SHA256:
        raise RuntimeError("CORE_GOLD_SHA_DRIFT")
    gold_rows = read_jsonl(GOLD)
    if len(gold_rows) != 48 or len({row["case_id"] for row in gold_rows}) != 48:
        raise RuntimeError("CORE_GOLD_DENOMINATOR_DRIFT")
    order = [row["case_id"] for row in gold_rows]
    question_receipts = {}
    for arm, spec in EXPECTED.items():
        if sha256(spec["questions"]) != spec["sha256"]:
            raise RuntimeError(f"{arm}_QUESTION_SHA_DRIFT")
        rows = read_jsonl(spec["questions"])
        if [row["case_id"] for row in rows] != order:
            raise RuntimeError(f"{arm}_CASE_ORDER_DRIFT")
        if len(rows) != 48:
            raise RuntimeError(f"{arm}_DENOMINATOR_DRIFT")
        question_receipts[arm] = {
            "path": str(spec["questions"]),
            "sha256": spec["sha256"],
            "rows": len(rows),
        }
    return {
        "model_receipt_sha256": sha256(MODEL_RECEIPT),
        "model_repo_id": model_receipt["repo_id"],
        "model_revision": model_receipt["revision"],
        "core_gold_sha256": GOLD_SHA256,
        "core_gold_rows": len(gold_rows),
        "core_gold_fact_count": sum(len(row["fact_sentences"]) for row in gold_rows),
        "questions": question_receipts,
    }


def preflight() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError("ZERO_TRAINING_OUTPUT_ALREADY_EXISTS")
    frozen = check_frozen_inputs()
    lock = {
        "schema_version": "t5-r04-dev-core-zero-training-run-lock-v1",
        "status": "PREFLIGHT_PASS_READY_TO_RUN",
        "created_at": now(),
        **frozen,
        "decode": {
            "temperature": 0.0,
            "sampler": "greedy",
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "automatic_retries": 0,
        },
        "run_order": ["Z00", "Z01"],
        "adapter": None,
        "training": False,
        "external_api": False,
        "sealed_inputs_mutable": False,
    }
    write_json(LOCK, lock)
    write_json(
        STATE,
        {
            "status": "PREFLIGHT_PASS_READY_TO_RUN",
            "pid": None,
            "completed": {"Z00": 0, "Z01": 0},
            "updated_at": now(),
        },
    )
    print(json.dumps(lock, ensure_ascii=False, indent=2))


def run() -> None:
    import mlx.core as mx
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    frozen = check_frozen_inputs()
    if lock.get("status") != "PREFLIGHT_PASS_READY_TO_RUN":
        raise RuntimeError("RUN_LOCK_NOT_READY")
    if lock.get("core_gold_sha256") != frozen["core_gold_sha256"]:
        raise RuntimeError("RUN_LOCK_GOLD_DRIFT")
    for arm in EXPECTED:
        if (OUT / f"arm_{arm.lower()}" / "RAW_OUTPUTS.jsonl").exists():
            raise RuntimeError(f"{arm}_OUTPUT_ALREADY_EXISTS")

    state = {
        "status": "RUNNING",
        "pid": os.getpid(),
        "current_arm": "MODEL_LOADING",
        "completed": {"Z00": 0, "Z01": 0},
        "started_at": now(),
        "updated_at": now(),
    }
    write_json(STATE, state)
    peak = 0
    try:
        mx.set_wired_limit(20 * 1024**3)
        mx.set_memory_limit(22 * 1024**3)
        mx.set_cache_limit(1 * 1024**3)
        mx.clear_cache()
        model, tokenizer = load(str(MODEL))
        sampler = make_sampler(temp=0.0)
        for arm in ("Z00", "Z01"):
            questions = read_jsonl(EXPECTED[arm]["questions"])
            arm_dir = OUT / f"arm_{arm.lower()}"
            arm_dir.mkdir(parents=True, exist_ok=True)
            raw_path = arm_dir / "RAW_OUTPUTS.jsonl"
            state["current_arm"] = arm
            state["updated_at"] = now()
            write_json(STATE, state)
            arm_peak = 0
            with raw_path.open("x", encoding="utf-8", newline="\n") as handle:
                for index, question in enumerate(questions, 1):
                    free_before = system_free_percent()
                    if free_before < 10:
                        raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_CASE:{arm}:{question['case_id']}:{free_before}")
                    mx.reset_peak_memory()
                    prompt = tokenizer.apply_chat_template(
                        question["messages"], tokenize=False, add_generation_prompt=True
                    )
                    input_tokens = len(tokenizer.encode(prompt))
                    began = time.monotonic()
                    output = generate(
                        model,
                        tokenizer,
                        prompt=prompt,
                        max_tokens=MAX_OUTPUT_TOKENS,
                        sampler=sampler,
                        verbose=False,
                    )
                    elapsed = time.monotonic() - began
                    output_tokens = len(tokenizer.encode(output))
                    format_result = validate_format(output)
                    case_peak = int(mx.get_peak_memory())
                    peak = max(peak, case_peak)
                    arm_peak = max(arm_peak, case_peak)
                    mx.clear_cache()
                    free_after = system_free_percent()
                    record = {
                        "index": index,
                        "arm": arm,
                        "case_id": question["case_id"],
                        "raw_output": output,
                        "parsed_output": format_result["parsed"],
                        "json_valid": format_result["json_valid"],
                        "schema_valid": format_result["schema_valid"],
                        "format_errors": format_result["errors"],
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "reached_max_output_tokens": output_tokens >= MAX_OUTPUT_TOKENS,
                        "elapsed_seconds": round(elapsed, 3),
                        "system_free_percent_before": free_before,
                        "system_free_percent_after": free_after,
                        "mlx_peak_memory_bytes": case_peak,
                    }
                    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    state["completed"][arm] = index
                    state["last_case"] = question["case_id"]
                    state["last_schema_valid"] = format_result["schema_valid"]
                    state["last_output_tokens"] = output_tokens
                    state["last_free_percent"] = free_after
                    state["peak_memory_bytes"] = peak
                    state["updated_at"] = now()
                    write_json(STATE, state)
                    print(
                        json.dumps(
                            {
                                "arm": arm,
                                "progress": f"{index}/48",
                                "case_id": question["case_id"],
                                "schema_valid": format_result["schema_valid"],
                                "output_tokens": output_tokens,
                                "free_after": free_after,
                                "peak_gib": round(case_peak / 1024**3, 3),
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    if free_after < 10:
                        raise RuntimeError(f"MEMORY_HARD_STOP_AFTER_CASE:{arm}:{question['case_id']}:{free_after}")
            write_json(
                arm_dir / "ARM_RUN_RECEIPT.json",
                {
                    "status": "COMPLETE",
                    "arm": arm,
                    "rows": 48,
                    "questions_sha256": EXPECTED[arm]["sha256"],
                    "raw_outputs_sha256": sha256(raw_path),
                    "mlx_peak_memory_bytes": arm_peak,
                    "decode": lock["decode"],
                    "completed_at": now(),
                },
            )
        state.update(
            {
                "status": "INFERENCE_COMPLETE",
                "current_arm": None,
                "completed_at": now(),
                "updated_at": now(),
                "peak_memory_bytes": peak,
            }
        )
    except BaseException as exc:
        state.update(
            {
                "status": "HARD_STOP",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "stopped_at": now(),
                "updated_at": now(),
            }
        )
        raise
    finally:
        write_json(STATE, state)
        mx.clear_cache()


def status() -> None:
    value = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"status": "NOT_STARTED"}
    pid = value.get("pid")
    alive = False
    if isinstance(pid, int):
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            pass
    value["process_alive"] = alive
    value["system_free_percent_now"] = system_free_percent()
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["preflight", "run", "status"])
    args = parser.parse_args()
    if args.action == "preflight":
        preflight()
    elif args.action == "run":
        run()
    else:
        status()


if __name__ == "__main__":
    main()
