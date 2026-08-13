#!/usr/bin/env python3
"""Train one 24-iteration READ1 LoRA with the shared output contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import yaml


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
RUN = REPO / "runs/T5_R04_READ1_TRAIN36_CONTRACT_SENTINEL_R01"
TRAIN_SOURCE = REPO / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01/READ_1_TARGET_TRAIN36.jsonl"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
EVAL_SOURCE = EVAL_ROOT / "READ_1_TARGET_EVAL24.jsonl"
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
LOW_EXP = REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01"
LOW_RUNNER = LOW_EXP / "run_read1_low_dose.py"
AB_EXP = REPO / "finetuning/experiments/T5_R04_READ1_FORMAT_CONTRACT_AB8_20260809_R01"
AB_SCRIPT = AB_EXP / "run_format_contract_ab8.py"
AB_ADJUDICATIONS = REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01/FORMAT_B_ADJUDICATIONS.jsonl"
C_ADJUDICATIONS = REPO / "runs/T5_R04_READ1_FORMAT_SHORT_C8_R01/FORMAT_C_ADJUDICATIONS.jsonl"
TRAIN_DERIVED = RUN / "data/train.jsonl"
EVAL8_DERIVED = RUN / "data/eval8.jsonl"
CONFIG = RUN / "config/train36_contract_24.yaml"
RAW8 = RUN / "RAW_8.jsonl"
INHERITED = RUN / "scoring/INHERITED_ADJUDICATIONS.jsonl"
PRE_METRICS = RUN / "scoring/PRE_METRICS_8.json"
BLIND_QUEUE = RUN / "scoring/BLIND_QUEUE_8.jsonl"
ADJUDICATIONS = RUN / "semantic_review/ADJUDICATIONS_8.jsonl"
FINAL_METRICS = RUN / "scoring/FINAL_METRICS_8.json"
RESULT_TICKET = EXP / "RESULT_TICKET.md"
CASES = ("C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24")
EXPECTED = {
    TRAIN_SOURCE: "84ad6f7886b372334b008d49cc2f3343afdd6b98d83a24a00d604ae49b8f09e0",
    EVAL_SOURCE: "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0",
    GOLD: "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    TRAINER: "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909",
}

# Blind semantic decisions for predictions not covered by earlier identical
# fact text. A null value means no equivalence to one complete Gold fact.
BLIND_DECISIONS: dict[str, str | None] = {
    "d84b99a8f163": None,
    "296d61946a1b": "C02-F002",
    "d0478b5ee46f": None,
    "8d7428db9a31": "C02-F003",
    "6cf253cf25b8": "C02-F004",
    "e5b2fb93ca27": "C02-F005",
    "f7ef44f9175c": None,
    "7904b8e97e14": "C02-F009",
    "a02962fca9ea": None,
    "8c56efccd5eb": None,
    "c0038a0e1a2d": "C05-F006",
    "8c903348ba60": None,
    "e33544e4a68c": "C05-F009",
    "d47a96521080": None,
    "604056a24219": "C05-F011",
    "6e7d5cddb9ef": "C05-F012",
    "4ab0ec2d7db4": None,
    "0e2c88b3d90a": None,
    "7977a8fcc3a5": "C09-F009",
    "5456fa0f1203": "C09-F008",
    "adcafe39d61b": "C09-F009",
    "4622449d6eb4": "C23-F011",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bytes_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_IMPORT_FAILED:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_sources() -> None:
    for path, expected in EXPECTED.items():
        if sha256(path) != expected:
            raise RuntimeError(f"SOURCE_SHA_DRIFT:{path}")


def training_config() -> dict[str, Any]:
    return {
        "model": str(MODEL),
        "train": True,
        "data": str(RUN / "data"),
        "fine_tune_type": "lora",
        "optimizer": "adam",
        "mask_prompt": True,
        "num_layers": 16,
        "batch_size": 2,
        "iters": 24,
        "val_batches": 0,
        "learning_rate": 0.00003,
        "steps_per_report": 4,
        "steps_per_eval": 24,
        "grad_accumulation_steps": 4,
        "adapter_path": str(RUN / "adapters"),
        "save_every": 24,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def prepare() -> None:
    verify_sources()
    if RUN.exists():
        raise RuntimeError("RUN_ROOT_EXISTS_NO_RETRY")
    ab = load_module(AB_SCRIPT, "format_ab8_contract_source")
    train_source = read_jsonl(TRAIN_SOURCE)
    if len(train_source) != 36:
        raise RuntimeError("TRAIN36_COUNT_DRIFT")
    derived_train = []
    for source in train_source:
        row = json.loads(json.dumps(source, ensure_ascii=False))
        if [message.get("role") for message in row.get("messages", [])] != ["system", "user", "assistant"]:
            raise RuntimeError("TRAIN_MESSAGE_SHAPE_DRIFT")
        row["messages"][0]["content"] += "\n" + ab.CONTRACT
        derived_train.append(row)
    for source, derived in zip(train_source, derived_train, strict=True):
        if derived.get("metadata") != source.get("metadata"):
            raise RuntimeError("TRAIN_METADATA_DRIFT")
        if derived["messages"][1:] != source["messages"][1:]:
            raise RuntimeError("TRAIN_USER_OR_ASSISTANT_DRIFT")
        if derived["messages"][0]["content"] != source["messages"][0]["content"] + "\n" + ab.CONTRACT:
            raise RuntimeError("TRAIN_SYSTEM_NOT_EXACT_SUFFIX_ONLY")
    cases = [row["case_id"] for row in read_jsonl(SOURCE_INDEX)]
    eval_rows = read_jsonl(EVAL_SOURCE)
    by_case = dict(zip(cases, eval_rows, strict=True))
    derived_eval = []
    for case_id in CASES:
        source = by_case[case_id]
        row = json.loads(json.dumps(source, ensure_ascii=False))
        row["messages"][0]["content"] += "\n" + ab.CONTRACT
        if row["messages"][1] != source["messages"][1]:
            raise RuntimeError("EVAL_USER_DRIFT")
        derived_eval.append({"case_id": case_id, "messages": row["messages"]})
    write_jsonl(TRAIN_DERIVED, derived_train)
    write_jsonl(EVAL8_DERIVED, derived_eval)
    CONFIG.parent.mkdir(parents=True)
    CONFIG.write_text(yaml.safe_dump(training_config(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    summary = {
        "train_rows": 36,
        "eval_rows": 8,
        "case_order_unchanged": [row.get("metadata", {}).get("case_id") for row in train_source]
        == [row.get("metadata", {}).get("case_id") for row in derived_train],
        "assistant_payload_sha256_source": bytes_sha([row["messages"][2]["content"] for row in train_source]),
        "assistant_payload_sha256_derived": bytes_sha([row["messages"][2]["content"] for row in derived_train]),
        "user_payload_sha256_source": bytes_sha([row["messages"][1]["content"] for row in train_source]),
        "user_payload_sha256_derived": bytes_sha([row["messages"][1]["content"] for row in derived_train]),
        "train_source_sha256": sha256(TRAIN_SOURCE),
        "train_derived_sha256": sha256(TRAIN_DERIVED),
        "eval8_derived_sha256": sha256(EVAL8_DERIVED),
        "gold_sha256": sha256(GOLD),
        "contract": ab.CONTRACT,
    }
    if summary["assistant_payload_sha256_source"] != summary["assistant_payload_sha256_derived"]:
        raise RuntimeError("ASSISTANT_PAYLOAD_SHA_DRIFT")
    if summary["user_payload_sha256_source"] != summary["user_payload_sha256_derived"]:
        raise RuntimeError("USER_PAYLOAD_SHA_DRIFT")
    write_json(RUN / "PREPARE_SUMMARY.json", summary)
    print(json.dumps({"status": "PREPARED", **summary}, ensure_ascii=False))


def train() -> None:
    verify_sources()
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    runner = load_module(LOW_RUNNER, "low_dose_runtime_for_contract_training")
    if runner.system_free_percent() < 8:
        raise RuntimeError("MEMORY_HARD_STOP_BEFORE_TRAINING")
    active = subprocess.run(["pgrep", "-fl", "mlx_lm.*lora"], capture_output=True, text=True, check=False)
    if active.returncode == 0 and active.stdout.strip():
        raise RuntimeError(f"OTHER_LORA_PROCESS_ACTIVE:{active.stdout.strip()}")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VENDOR)
    env["PYTHONUNBUFFERED"] = "1"
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(CONFIG)]
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
            if line.startswith("Iter "):
                print(f"CONTRACT_TRAIN {line.strip()} memory_free={runner.system_free_percent()}%", flush=True)
                if runner.system_free_percent() < 8:
                    child.terminate()
                    child.wait()
                    raise RuntimeError("MEMORY_HARD_STOP_DURING_TRAINING")
        code = child.wait()
    log_text = (RUN / "training.log").read_text(encoding="utf-8", errors="replace")
    if code != 0 or "Saved final weights" not in log_text:
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{code}")
    adapter = RUN / "adapters/adapters.safetensors"
    checkpoint = RUN / "adapters/0000024_adapters.safetensors"
    if not adapter.is_file() or not checkpoint.is_file() or sha256(adapter) != sha256(checkpoint):
        raise RuntimeError("FINAL_ADAPTER_MISSING_OR_NOT_STEP24")
    elapsed = round(time.monotonic() - began, 3)
    write_json(
        RUN / "TRAINING_RESULT.json",
        {
            "status": "PASS_24_ITERATIONS",
            "elapsed_seconds": elapsed,
            "adapter_sha256": sha256(adapter),
            "checkpoint_sha256": sha256(checkpoint),
            "training_calls": 1,
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "TRAINING_COMPLETE", "elapsed_seconds": elapsed, "adapter_sha256": sha256(adapter)}, ensure_ascii=False))


def infer8() -> None:
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = read_jsonl(EVAL8_DERIVED)
    if [row["case_id"] for row in requests] != list(CASES):
        raise RuntimeError("EVAL8_ORDER_DRIFT")
    runner = load_module(LOW_RUNNER, "low_dose_runtime_for_contract_eval")
    mx, load, stream_generate, make_sampler = runner.configure_mlx()
    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(str(MODEL), adapter_path=str(RUN / "adapters"))
    for index, item in enumerate(requests, 1):
        row = runner.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            "TRAIN36_CONTRACT_ITER24",
            item["case_id"],
            item["messages"],
            RAW8,
        )
        print(
            f"CONTRACT_EVAL case={item['case_id']} done={index}/8 "
            f"limit={int(row['token_limit_hit'])} repetition={int(row['repetition_detected'])}",
            flush=True,
        )
        mx.clear_cache()
    print(json.dumps({"status": "INFERENCE8_COMPLETE", "raw_sha256": sha256(RAW8)}, ensure_ascii=False))


def configure_scorer() -> Any:
    ab = load_module(AB_SCRIPT, "format_ab8_scorer_for_contract_training")
    ab.EXP = EXP
    ab.RUN = RUN
    ab.RAW = RAW8
    ab.PRE_METRICS = PRE_METRICS
    ab.BLIND_QUEUE = BLIND_QUEUE
    ab.ADJUDICATIONS = ADJUDICATIONS
    ab.FINAL_METRICS = FINAL_METRICS
    ab.RESULT_TICKET = RESULT_TICKET
    ab.LOW_DECISIONS = INHERITED
    return ab


def prepare_inherited() -> None:
    if INHERITED.exists():
        return
    ab = load_module(AB_SCRIPT, "format_ab8_decision_sources")
    sources = (ab.LOW_DECISIONS, AB_ADJUDICATIONS, C_ADJUDICATIONS)
    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sources:
        for row in read_jsonl(path):
            key = (row["case_id"], row["prediction_fact_sha256"])
            value = {"category": row["category"], "matched_gold_fact_id": row.get("matched_gold_fact_id")}
            if key in combined and {
                "category": combined[key]["category"],
                "matched_gold_fact_id": combined[key].get("matched_gold_fact_id"),
            } != value:
                raise RuntimeError("INHERITED_DECISION_CONFLICT")
            combined[key] = row
    write_jsonl(INHERITED, list(combined.values()))


def score_pre() -> None:
    prepare_inherited()
    scorer = configure_scorer()
    result, queue = scorer.score()
    write_json(PRE_METRICS, result)
    write_jsonl(BLIND_QUEUE, queue)
    print(json.dumps({"status": result["status"], "semantic_pending": len(queue)}, ensure_ascii=False))


def adjudicate() -> None:
    queue = read_jsonl(BLIND_QUEUE)
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
    write_jsonl(ADJUDICATIONS, rows)
    print(json.dumps({"status": "BLIND_REVIEW_COMPLETE", "decisions": len(rows)}, ensure_ascii=False))


def score_final() -> None:
    if not ADJUDICATIONS.is_file():
        raise RuntimeError("ADJUDICATIONS_MISSING")
    scorer = configure_scorer()
    result, queue = scorer.score()
    if queue or result["semantic_pending"]:
        raise RuntimeError("SEMANTIC_REVIEW_INCOMPLETE")
    write_json(FINAL_METRICS, result)
    candidate = result["b_format_contract"]
    semantic = candidate["semantic_recoverable"]
    gate = result["gate"]
    decision = "PASS_EXPAND_TO_FULL24" if gate["all_pass"] else "FAIL_STOP_AT_8"
    training = json.loads((RUN / "TRAINING_RESULT.json").read_text(encoding="utf-8"))
    prepare_summary = json.loads((RUN / "PREPARE_SUMMARY.json").read_text(encoding="utf-8"))
    ticket = f"""# TRAIN36＋共同输出合同｜READ1 24步哨兵

结论：`{decision}`。

本轮从冻结 TRAIN36 READ1 派生36条训练行，user、assistant、metadata和顺序不变；训练与8道考试题都只在 system 末尾追加同一行完整输出合同。

- 派生训练数据 SHA：`{prepare_summary['train_derived_sha256']}`。
- 24步 adapter SHA：`{training['adapter_sha256']}`；训练耗时 {training['elapsed_seconds']} 秒。
- 8题事实：TP={semantic['tp']}，FP={semantic['fp']}，FN={semantic['fn']}，P={semantic['precision']:.6f}，R={semantic['recall']:.6f}，F1={semantic['f1']:.6f}。
- 8题格式：严格 JSON={candidate['json_valid_cases']}/8，完整 Schema={candidate['schema_valid_cases']}/8，非法证据={candidate['illegal_evidence_predictions']}，复读题={candidate['repetition_cases']}，触顶题={candidate['token_limit_cases']}，重复事实={candidate['duplicate_predictions']}。
- 命中字段：status={candidate['status_correct']}/{semantic['tp']}，speaker={candidate['speaker_correct']}/{semantic['tp']}，evidence={candidate['evidence_correct']}/{semantic['tp']}。
- 三道门：格式稳定={gate['format_stability_gate']}；事实保留={gate['semantic_retention_gate']}；status过半={gate['status_accuracy_gate']}。

若结论为 `FAIL_STOP_AT_8`，本轮不补完整24题、不增加训练步数，也不触碰 TRAIN48、READ2/4 或 OUT。

来源：Codex
"""
    if RESULT_TICKET.exists():
        raise RuntimeError("RESULT_TICKET_EXISTS_NO_OVERWRITE")
    RESULT_TICKET.write_text(ticket, encoding="utf-8")
    print(json.dumps({"status": decision, "metrics_sha256": sha256(FINAL_METRICS)}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "train", "infer8", "score-pre", "adjudicate", "score-final"))
    args = parser.parse_args()
    globals()[args.command.replace("-", "_")]()


if __name__ == "__main__":
    main()
