#!/usr/bin/env python3
"""Run isolated P3 context variants with the frozen M1 C2 update72 adapter."""

from __future__ import annotations

import argparse
from datetime import datetime
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

from safetensors import safe_open


REPO = Path("/Users/a1234/挣钱/小说架构")
EXP = REPO / "finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01"
BUILD = EXP / "sealed_inputs_r01"
RESULTS = EXP / "results_r01"
WORK = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT"
M1 = WORK / "m1_r01"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
ADAPTER = M1 / "eval_adapters/c2_full/update_72"
VENDOR = WORK / "pipeline_r02/vendor_r02"
OLD_RAW = M1 / "results/c2_full/update_72/DEV24_RAW_OUTPUTS.jsonl"
M1_RUNNER = M1 / "tools/m1_runner.py"
CURRENT = REPO / "finetuning/CURRENT.json"
MAX_OUTPUT_TOKENS = 1024
ARMS = ("c0_current_minimal", "c1_rulebook_8", "c2_purpose_short", "c4_previous_state_confirmed")
EXPECTED = {
    "current": "5abaa79b952532881dfc5e147e7da190471baba386aac263474b51edd414f8dd",
    "adapter": "321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9",
    "adapter_config": "72df68a7d01b8feae8f92cc0e4f69c832d9ad71886b4f8ea2896a7436d73031e",
    "old_raw": "b32460077523b054f772fa5a70d39e8f51bec902f81b04f0261040cfff1b13c6",
    "m1_runner": "f2199b8f911894d8347878a97244ca3b41e8e19fc5297408fd6e8d18a2f81be7",
}

spec = importlib.util.spec_from_file_location("m1_runner_frozen", M1_RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError("无法加载冻结 M1 runner")
m1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m1)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def free_percent() -> int:
    output = subprocess.run(["memory_pressure", "-Q"], text=True, capture_output=True, check=False).stdout
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", output)
    return int(match.group(1)) if match else -1


def verify_frozen() -> None:
    checks = {
        "current": CURRENT,
        "adapter": ADAPTER / "adapters.safetensors",
        "adapter_config": ADAPTER / "adapter_config.json",
        "old_raw": OLD_RAW,
        "m1_runner": M1_RUNNER,
    }
    for key, path in checks.items():
        actual = sha256(path)
        if actual != EXPECTED[key]:
            raise RuntimeError(f"冻结件漂移：{key} expected={EXPECTED[key]} actual={actual}")
    with safe_open(ADAPTER / "adapters.safetensors", framework="np") as handle:
        keys = list(handle.keys())
        if not keys:
            raise RuntimeError("C2 update72 adapter 为空")
        for key in keys:
            handle.get_slice(key).get_shape()
    if not (BUILD / "P3_SOURCE_AND_EXECUTION_LOCK.json").is_file():
        raise RuntimeError("缺少 sealed P3 输入锁")


def stable_projection(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "index", "arm", "format_arm", "optimizer_update", "split", "case_id", "raw_output",
        "gold_output", "source", "finish_reason", "stop_token_id", "stop_token_is_eos_eot",
        "generation_tokens_including_stop", "output_tokens_excluding_stop", "input_tokens",
        "json_valid", "schema_valid", "schema_errors", "parsed_output", "recovered_fact_objects",
        "complete_exact_fit", "repetition_detected", "exact_duplicate_fact_object_count",
        "earliest_exact_closure_token", "tail_waste_tokens",
    )
    return {key: row.get(key) for key in keys}


def projection_sha(rows: list[dict[str, Any]]) -> str:
    payload = "".join(json.dumps(stable_projection(row), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n" for row in rows)
    return text_sha(payload)


def run_arm(arm: str) -> None:
    if arm not in ARMS:
        raise RuntimeError(f"未知 arm：{arm}")
    if arm != "c0_current_minimal":
        baseline = RESULTS / "CONTEXT_BASELINE_REPRODUCTION_RECEIPT.json"
        if not baseline.is_file() or json.loads(baseline.read_text(encoding="utf-8")).get("status") != "PASS_C0_BASELINE_STABLE_PROJECTION_BYTE_IDENTICAL":
            raise RuntimeError("C0 基线尚未逐字复现，禁止继续 Prompt 对照")
    verify_frozen()
    question_path = BUILD / f"track_b/prompts/{arm}_QUESTIONS_24.jsonl"
    questions = read_jsonl(question_path)
    if len(questions) != 24 or len({row["case_id"] for row in questions}) != 24:
        raise RuntimeError(f"{arm} 不是 24 个唯一 case")
    out = RESULTS / "raw" / arm
    if out.exists():
        raise RuntimeError(f"结果目录已存在，禁止覆盖：{out}")
    out.mkdir(parents=True)
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
    records = []
    peak = 0
    began_all = time.monotonic()
    for index, row in enumerate(questions, 1):
        if free_percent() < 8:
            raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_CASE:{arm}/{row['case_id']}")
        prompt = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=False, add_generation_prompt=True)
        gold = json.loads(row["messages"][-1]["content"])
        source = m1.parse_prompt_source(row["messages"][1]["content"], "c2_full")
        mx.reset_peak_memory()
        began = time.monotonic()
        pieces = []
        final = None
        for response in stream_generate(model, tokenizer, prompt=prompt, max_tokens=MAX_OUTPUT_TOKENS, sampler=sampler):
            pieces.append(response.text)
            final = response
        if final is None:
            raise RuntimeError(f"EMPTY_GENERATION:{row['case_id']}")
        raw = "".join(pieces)
        peak = max(peak, int(mx.get_peak_memory()))
        records.append({
            "index": index,
            "arm": "c2_full",
            "context_arm": arm,
            "format_arm": "C2_FULL_ID_LIST",
            "optimizer_update": 72,
            "split": "dev24",
            "case_id": row["case_id"],
            "raw_output": raw,
            "gold_output": gold,
            "source": source,
            "finish_reason": final.finish_reason,
            "stop_token_id": int(final.token),
            "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids,
            "generation_tokens_including_stop": int(final.generation_tokens),
            "output_tokens_excluding_stop": len(tokenizer.encode(raw, add_special_tokens=False)),
            "input_tokens": int(final.prompt_tokens),
            "elapsed_seconds": round(time.monotonic() - began, 3),
            "full_prompt_sha256": text_sha(prompt),
            "input_block_sha256": row["input_block_sha256"],
            **m1.analyze_output(raw, gold, "c2_full", tokenizer),
        })
        print(json.dumps({"arm": arm, "case": row["case_id"], "done": index, "free_percent": free_percent(), "output_tokens": records[-1]["output_tokens_excluding_stop"], "schema": records[-1]["schema_valid"]}, ensure_ascii=False), flush=True)
        mx.clear_cache()
    raw_path = out / "RAW_OUTPUTS.jsonl"
    write_jsonl(raw_path, records)
    receipt = {
        "status": "PASS_CONTEXT_ARM_INFERENCE_COMPLETE",
        "arm": arm,
        "completed_at": now(),
        "cases": 24,
        "raw_sha256": sha256(raw_path),
        "stable_projection_sha256": projection_sha(records),
        "questions_sha256": sha256(question_path),
        "adapter_sha256": sha256(ADAPTER / "adapters.safetensors"),
        "decode": {"sampler": "greedy", "temperature": 0.0, "max_output_tokens": 1024, "retry": 0},
        "peak_mlx_bytes": peak,
        "elapsed_seconds": round(time.monotonic() - began_all, 3),
        "training": False,
        "api_called": False,
    }
    write_json(out / "INFERENCE_RECEIPT.json", receipt)
    if arm == "c0_current_minimal":
        old_rows = read_jsonl(OLD_RAW)
        old_projection = projection_sha(old_rows)
        new_projection = projection_sha(records)
        differences = []
        for old, new in zip(old_rows, records, strict=True):
            old_p = stable_projection(old)
            new_p = stable_projection(new)
            if old_p != new_p:
                differences.append({"case_id": old["case_id"], "different_fields": [key for key in old_p if old_p[key] != new_p[key]]})
        baseline = {
            "status": "PASS_C0_BASELINE_STABLE_PROJECTION_BYTE_IDENTICAL" if not differences and old_projection == new_projection else "HARD_STOP_C0_BASELINE_NOT_REPRODUCED",
            "old_raw_path": str(OLD_RAW),
            "old_raw_sha256": sha256(OLD_RAW),
            "new_raw_path": str(raw_path),
            "new_raw_sha256": sha256(raw_path),
            "stable_projection_definition": "原始逐案输出与所有稳定推理字段；排除 elapsed_seconds、context_arm、prompt SHA 等本次运行元数据。",
            "old_stable_projection_sha256": old_projection,
            "new_stable_projection_sha256": new_projection,
            "case_order_identical": [row["case_id"] for row in old_rows] == [row["case_id"] for row in records],
            "different_cases": differences,
            "raw_payload_byte_identity_not_expected": "原始 JSONL 含 elapsed_seconds，本票比较稳定投影而不是把运行耗时伪装成可复现业务字段。",
        }
        write_json(RESULTS / "CONTEXT_BASELINE_REPRODUCTION_RECEIPT.json", baseline)
        if baseline["status"].startswith("HARD_STOP"):
            raise RuntimeError("C0 基线稳定投影未逐字复现")


def status() -> None:
    payload = {"results_root": str(RESULTS), "free_percent": free_percent(), "arms": {}}
    for arm in ARMS:
        receipt = RESULTS / "raw" / arm / "INFERENCE_RECEIPT.json"
        payload["arms"][arm] = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {"status": "NOT_STARTED"}
    baseline = RESULTS / "CONTEXT_BASELINE_REPRODUCTION_RECEIPT.json"
    payload["baseline"] = json.loads(baseline.read_text(encoding="utf-8")) if baseline.is_file() else {"status": "NOT_STARTED"}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run-arm", "status"))
    parser.add_argument("--arm", choices=ARMS)
    args = parser.parse_args()
    if args.command == "status":
        status()
    else:
        if not args.arm:
            parser.error("run-arm 需要 --arm")
        run_arm(args.arm)


if __name__ == "__main__":
    main()
