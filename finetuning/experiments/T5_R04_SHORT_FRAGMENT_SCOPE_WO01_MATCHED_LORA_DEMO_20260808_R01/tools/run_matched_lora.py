#!/usr/bin/env python3
"""Run the three matched WO-01 LoRA arms by reusing the frozen M1 recipe."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time


REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
WORK = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT"
M1_RUNNER = WORK / "m1_r01/tools/m1_runner.py"
RUN_ROOT = REPO / "runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_MATCHED_LORA_DEMO_R01"
DATA_ROOT = EXP / "data"
ARMS = ("target_only", "small_halo", "current_window")
LABELS = {"target_only": "TARGET_ONLY", "small_halo": "SMALL_HALO", "current_window": "CURRENT_WINDOW"}


def load_m1():
    spec = importlib.util.spec_from_file_location("m1_runner_matched", M1_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("M1_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = RUN_ROOT
    module.ARM_ORDER = ARMS
    module.ARMS = {
        arm: {
            "label": LABELS[arm],
            "format_arm": "C2_FULL_ID_LIST",
            "train": DATA_ROOT / "source_train" / f"{LABELS[arm]}.jsonl",
            "dev": DATA_ROOT / "dev" / f"{LABELS[arm]}.jsonl",
            "required": ("fact", "status", "speaker", "evidence_ids"),
        }
        for arm in ARMS
    }
    module.CANONICAL_TRAIN = WORK / "inspection/T5_R04_SYNTHETIC_MICRO24_R01/canonical/CANONICAL_MICRO24.jsonl"
    module.CANONICAL_DEV = WORK / "set_b_r03_work/sealed/T5_R04_SYNTHETIC_MICRO24_SET_B_R03_20260808/canonical/CANONICAL_MICRO24_SET_B_R03.jsonl"
    module.check_schema = check_c2_schema
    return module


def check_c2_schema(value, arm: str) -> tuple[bool, list[str]]:
    del arm
    if not isinstance(value, dict) or set(value) != {"facts"} or not isinstance(value.get("facts"), list):
        return False, ["top_level_facts_schema"]
    errors = []
    required = {"fact", "status", "speaker", "evidence_ids"}
    allowed = {"已发生", "正在发生", "计划", "承诺", "条件", "推测", "误信", "否定"}
    for index, item in enumerate(value["facts"]):
        if not isinstance(item, dict) or set(item) != required:
            errors.append(f"fact_{index}_keys")
            continue
        if not isinstance(item.get("fact"), str) or not item["fact"]:
            errors.append(f"fact_{index}_fact")
        if item.get("status") not in allowed:
            errors.append(f"fact_{index}_status")
        if item.get("speaker") is not None and not isinstance(item.get("speaker"), str):
            errors.append(f"fact_{index}_speaker")
        if not isinstance(item.get("evidence_ids"), list) or not all(isinstance(x, str) for x in item["evidence_ids"]):
            errors.append(f"fact_{index}_evidence_ids")
    return not errors, errors


def prepare() -> None:
    m1 = load_m1()
    if RUN_ROOT.exists():
        raise RuntimeError(f"RUN_ROOT_EXISTS:{RUN_ROOT}")
    if m1.sha256(m1.TRAINER) != m1.EXPECTED_TRAINER_SHA:
        raise RuntimeError("M1_TRAINER_SHA_DRIFT")
    model_receipt = json.loads((m1.MODEL / "MODEL_RECEIPT.json").read_text(encoding="utf-8"))
    if model_receipt.get("status") != "COMPLETE_VERIFIED":
        raise RuntimeError("BASE_MODEL_NOT_VERIFIED")
    materials = {}
    for arm in ARMS:
        source_id = m1.dataset_identity(m1.ARMS[arm]["train"])
        dev_id = m1.dataset_identity(m1.ARMS[arm]["dev"])
        if (source_id["rows"], source_id["unique_case_ids"], source_id["fact_count"], source_id["natural_empty_count"]) != (24, 24, 43, 2):
            raise RuntimeError(f"TRAIN_DENOMINATOR_DRIFT:{arm}")
        if (dev_id["rows"], dev_id["unique_case_ids"], dev_id["fact_count"], dev_id["natural_empty_count"]) != (24, 24, 48, 2):
            raise RuntimeError(f"DEV_DENOMINATOR_DRIFT:{arm}")
        if any(row.get("metadata", {}).get("set_role") != "DEV24_SET_B_R03_DO_NOT_TRAIN" for row in m1.read_jsonl(m1.ARMS[arm]["dev"])):
            raise RuntimeError(f"DEV_IDENTITY_DRIFT:{arm}")
        m1.runtime_train(arm).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(m1.ARMS[arm]["train"], m1.runtime_train(arm))
        m1.write_config(arm)
        material = m1.execution_material(arm)
        lock = {
            "status": "FROZEN_READY_FOR_M1_ARM_TRAINING",
            "cz_authorization": "WO01_MATCHED_THREE_LORA_DEMO_20260808",
            "material": material,
            "forbidden": {"cross_arm_checkpoint_reuse": True, "dev_training": True, "api": True, "parameter_tuning": True},
        }
        m1.write_json(m1.arm_lock_path(arm), lock)
        materials[arm] = {"execution_lock_sha256": m1.sha256(m1.arm_lock_path(arm)), "material": material}
    master = {
        "status": "FROZEN_READY_FOR_SERIAL_THREE_ARM_MATCHED_LORA_DEMO",
        "arm_order": list(ARMS),
        "same_original_base": {"path": str(m1.MODEL), "revision": m1.MODEL_REVISION, "receipt_sha256": m1.sha256(m1.MODEL / "MODEL_RECEIPT.json")},
        "canonical": {"train_sha256": m1.sha256(m1.CANONICAL_TRAIN), "dev_sha256": m1.sha256(m1.CANONICAL_DEV)},
        "dev_identity": "DEV24_SET_B_R03_DO_NOT_TRAIN",
        "materials": materials,
    }
    m1.write_json(RUN_ROOT / "MASTER_EXECUTION_LOCK.json", master)
    m1.write_json(RUN_ROOT / "M1_STATE.json", {"status": "READY_FOR_SERIAL_TRAINING", "completed_training_arms": [], "completed_inference_arms": [], "api_calls": 0})
    print(json.dumps({"status": master["status"], "arms": list(ARMS)}, ensure_ascii=False))


def train_one(arm: str) -> None:
    m1 = load_m1()
    m1.train_one(arm)


def train_all() -> None:
    m1 = load_m1()
    for arm in ARMS:
        m1.train_one(arm)
    state = json.loads((RUN_ROOT / "M1_STATE.json").read_text(encoding="utf-8"))
    state.update({"status": "TRAINING_COMPLETE_PENDING_DEV_INFERENCE", "completed_training_arms": list(ARMS)})
    m1.write_json(RUN_ROOT / "M1_STATE.json", state)


def infer_dev_one(arm: str) -> None:
    m1 = load_m1()
    sys.path.insert(0, str(m1.VENDOR))
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler

    m1.verify_arm_lock(arm)
    train_receipt = json.loads(m1.arm_receipt_path(arm).read_text(encoding="utf-8"))
    if train_receipt.get("status") != "PASS_M1_ARM_TRAINING_COMPLETE":
        raise RuntimeError(f"TRAINING_NOT_COMPLETE:{arm}")
    adapter = m1.build_eval_adapter(arm, 72)
    result_root = RUN_ROOT / "results" / arm / "update_72"
    if result_root.exists():
        raise RuntimeError(f"RESULT_EXISTS:{result_root}")
    result_root.mkdir(parents=True)
    mx.set_wired_limit(20 * 1024**3)
    mx.set_memory_limit(22 * 1024**3)
    mx.set_cache_limit(1 * 1024**3)
    mx.clear_cache()
    model, tokenizer = load(str(m1.MODEL), adapter_path=str(adapter))
    sampler = make_sampler(temp=0.0)
    records = []
    peak = 0
    began_arm = time.monotonic()
    for index, row in enumerate(m1.read_jsonl(m1.ARMS[arm]["dev"]), 1):
        if m1.system_free_percent() < 8:
            raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_CASE:{arm}:{row['case_id']}")
        prompt = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=False, add_generation_prompt=True)
        gold = json.loads(row["messages"][-1]["content"])
        source = m1.parse_prompt_source(row["messages"][1]["content"], arm)
        mx.reset_peak_memory()
        began = time.monotonic()
        pieces = []
        final = None
        for response in stream_generate(model, tokenizer, prompt=prompt, max_tokens=m1.MAX_OUTPUT_TOKENS, sampler=sampler):
            pieces.append(response.text)
            final = response
        if final is None:
            raise RuntimeError(f"EMPTY_GENERATION:{arm}:{row['case_id']}")
        raw = "".join(pieces)
        peak = max(peak, int(mx.get_peak_memory()))
        records.append(
            {
                "index": index,
                "arm": arm,
                "scope_arm": LABELS[arm],
                "format_arm": "C2_FULL_ID_LIST",
                "optimizer_update": 72,
                "split": "dev24",
                "case_id": row["case_id"],
                "raw_output": raw,
                "gold_output": gold,
                "source": source,
                "finish_reason": final.finish_reason,
                "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids,
                "output_tokens_excluding_stop": len(tokenizer.encode(raw, add_special_tokens=False)),
                "input_tokens": int(final.prompt_tokens),
                "elapsed_seconds": round(time.monotonic() - began, 3),
                **m1.analyze_output(raw, gold, arm, tokenizer),
            }
        )
        print(f"WO01_DEV arm={arm} case={index}/24 schema={records[-1]['schema_valid']}", flush=True)
        mx.clear_cache()
    raw_path = result_root / "DEV24_RAW_OUTPUTS.jsonl"
    m1.write_jsonl(raw_path, records)
    receipt = {
        "status": "PASS_WO01_MATCHED_LORA_DEV24_INFERENCE_COMPLETE",
        "arm": arm,
        "scope_arm": LABELS[arm],
        "optimizer_update": 72,
        "rows": 24,
        "gold_facts": 48,
        "adapter": m1.validate_safetensors(adapter / "adapters.safetensors"),
        "dev_raw_sha256": m1.sha256(raw_path),
        "elapsed_seconds": round(time.monotonic() - began_arm, 3),
        "peak_mlx_bytes": peak,
        "api_calls": 0,
        "dev_trained": False,
        "retry": 0,
    }
    m1.write_json(result_root / "INFERENCE_RECEIPT.json", receipt)
    del model
    mx.clear_cache()


def infer_all() -> None:
    m1 = load_m1()
    for arm in ARMS:
        infer_dev_one(arm)
    state = json.loads((RUN_ROOT / "M1_STATE.json").read_text(encoding="utf-8"))
    state.update({"status": "DEV_INFERENCE_COMPLETE_PENDING_SCORING", "completed_inference_arms": list(ARMS)})
    m1.write_json(RUN_ROOT / "M1_STATE.json", state)


def status() -> None:
    m1 = load_m1()
    state = json.loads((RUN_ROOT / "M1_STATE.json").read_text(encoding="utf-8")) if (RUN_ROOT / "M1_STATE.json").is_file() else {"status": "NOT_PREPARED"}
    print(json.dumps({"state": state, "memory": m1.memory_snapshot(), "active_lora_processes": m1.active_lora_processes()}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "train-one", "train-all", "infer-one", "infer-all", "status"))
    parser.add_argument("--arm", choices=ARMS)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "train-one":
        if not args.arm:
            parser.error("train-one requires --arm")
        train_one(args.arm)
    elif args.command == "train-all":
        train_all()
    elif args.command == "infer-one":
        if not args.arm:
            parser.error("infer-one requires --arm")
        infer_dev_one(args.arm)
    elif args.command == "infer-all":
        infer_all()
    else:
        status()


if __name__ == "__main__":
    main()
