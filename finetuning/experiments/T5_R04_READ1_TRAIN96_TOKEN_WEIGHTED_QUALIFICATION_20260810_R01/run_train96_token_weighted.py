#!/usr/bin/env python3
"""Run one ticket-bound READ1 TRAIN96 token-weighted qualification."""

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


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC_PATH = EXP / "SPEC.json"
TRAIN = EXP / "READ_1_TARGET_TRAIN96.jsonl"
TOKEN_STATS = EXP / "TRAIN96_TOKEN_STATS.json"
SCORER = EXP / "score_train96_l6.py"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN96_TOKEN_WEIGHTED_QUALIFICATION_R01"
OLD72 = (
    REPO
    / "finetuning/experiments/T5_R04_READ1_TRAIN72_DENSITY_PAIRED_20260810_R01"
    / "READ_1_TARGET_TRAIN72_DENSITY_PAIRED.jsonl"
)
R03 = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_TRAIN96_SOURCE6_RECUT24_MODEL_NEUTRAL_GOLD_20260810_R03"
)
R03_SOURCE = R03 / "SOURCE_INDEX_24.jsonl"
R03_GOLD = R03 / "MODEL_NEUTRAL_GOLD_24.jsonl"
R03_SIDECAR = R03 / "SEMANTIC_REVIEW_SIDECAR.jsonl"
R03_MANIFEST = R03 / "OUTPUT_MANIFEST.json"
R03_RECEIPT = R03 / "FINAL_VALIDATION_RECEIPT.json"
DIAGNOSTIC_FAIL = (
    REPO
    / "runs/T5_R04_READ1_TRAIN72_TOKEN_WEIGHTED_REDUCER_DIAGNOSTIC_R01/"
    "L6_MECHANICAL_FAIL_TICKET.json"
)
PARENT_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01"
PARENT_L6_RAW = PARENT_RUN / "inference/L6_RAW_12.jsonl"
PARENT_L6_REQUEST = PARENT_RUN / "data/L6_V2_REQUESTS.jsonl"
MODEL = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f"
)
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
PREFLIGHT = (
    REPO
    / "finetuning/experiments/T5_R04_TOKEN_WEIGHTED_GRAD_ACCUM_PREFLIGHT_20260810_R01"
)
PREFLIGHT_RECEIPT = PREFLIGHT / "PREPARE_RECEIPT.json"
VENDOR = PREFLIGHT / "vendor_token_weighted"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
RUNTIME_RUNNER = (
    REPO
    / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/"
    "run_read1_low_dose.py"
)

EXPECTED = {
    "old_train72_sha256": "9c1a2202380f5c589d590a34354309643b1bb8fc0a12732184e11a282c924797",
    "r03_source_sha256": "1067ec9ac4808523f543412cd419f133f3c352811467c032641ec1ba0ece350a",
    "r03_gold_sha256": "1bec7dbfc26878e0553e8f34319c072c46da0f6b80e4a3ae19842629451bec6d",
    "r03_sidecar_sha256": "239427e1780304be28eff3301132a5cf9304682798d37adc60fe6d5fed40d9df",
    "r03_manifest_sha256": "7eff5f3f591e6b79a69e005c1d654e9b68cf0e4597c8cdd061fb17fb39703ee4",
    "r03_receipt_sha256": "f79306c8d7eeaafdba7b465437bf455ea64ee8f6dfb479fd3c378d3f5096338c",
    "diagnostic_fail_sha256": "399c7eab1bf4f99cdf5012bf9ee027e15c798567d99a4082d5f15efdae57f62c",
    "parent_l6_raw_sha256": "e3c662cb87aaf8ba6862ce37c562de3752f554e2877079833da49e97dcf7646d",
    "l6_request_sha256": "1aa942e9910fd3525f7c2fb7f3f23f9d706a2564870f3526319104dcfa42b3ec",
    "base_l6_projection_sha256": "db5d40432a0849b78f3d5a09824251af4574002205b5221892bc9b32b3649476",
    "model_receipt_sha256": "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6",
    "preflight_receipt_sha256": "4e46a23ca6da1741c1027884a2a4e9c35cd3fb21576c1f8e58fc97166a08d31c",
    "trainer_sha256": "2ff621480fb043220f8dff29d01f85f6e8f8ffe9b04fb2eebc415a837b0be1c6",
    "vendor_tree_sha256": "2e77413bec6141f2a71b1fac032f5967bdfb9e2b65ba43a1b484d78d4e1f8059",
    "runtime_runner_sha256": "db9ae2a2c33dbbe3539f86fa9e45645e8dda6267ac42b5484b6b042290d80245",
}

MAX_OUTPUT_TOKENS = 2048
AUTHORIZED_COMMANDS = ["train", "infer-l6"]
TICKET_KEYS = {
    "schema_version",
    "approved",
    "authorized_by",
    "decision_id",
    "decision_text_sha256",
    "source_thread_id",
    "issued_at",
    "scope",
    "run_id",
    "run_root",
    "authorized_commands",
    "spec_sha256",
    "train_input_sha256",
    "token_stats_sha256",
    "old_train72_sha256",
    "r03_source_sha256",
    "r03_gold_sha256",
    "r03_sidecar_sha256",
    "r03_manifest_sha256",
    "r03_receipt_sha256",
    "diagnostic_fail_sha256",
    "parent_l6_raw_sha256",
    "l6_request_sha256",
    "base_l6_projection_sha256",
    "reducer_preflight_receipt_sha256",
    "derived_trainer_sha256",
    "derived_vendor_tree_sha256",
    "runner_sha256",
    "scorer_sha256",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise RuntimeError(f"DUPLICATE_JSON_KEY:{label}:{key}")
            value[key] = item
        return value

    result = json.loads(
        data.decode("utf-8", errors="strict"), object_pairs_hook=reject_duplicates
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{label}")
    return result


def read_json(path: Path) -> dict[str, Any]:
    return strict_json_bytes(path.read_bytes(), str(path))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        strict_json_bytes(line, f"{path}:{index}")
        for index, line in enumerate(path.read_bytes().splitlines(), 1)
        if line.strip()
    ]


def compact_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def vendor_tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
        digest.update(b"\0")
    return digest.hexdigest()


def load_spec() -> dict[str, Any]:
    return read_json(SPEC_PATH)


def project_base_l6() -> bytes:
    rows = [row for row in read_jsonl(PARENT_L6_RAW) if row.get("variant") == "BASE_L6"]
    expected = [f"LC-L{i:02d}" for i in range(1, 7)]
    if len(rows) != 6 or [row.get("case_id") for row in rows] != expected:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_DRIFT")
    projected = compact_jsonl(rows)
    if hashlib.sha256(projected).hexdigest() != EXPECTED["base_l6_projection_sha256"]:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_SHA_DRIFT")
    return projected


def static_check() -> dict[str, Any]:
    spec = load_spec()
    fixed = {
        OLD72: EXPECTED["old_train72_sha256"],
        R03_SOURCE: EXPECTED["r03_source_sha256"],
        R03_GOLD: EXPECTED["r03_gold_sha256"],
        R03_SIDECAR: EXPECTED["r03_sidecar_sha256"],
        R03_MANIFEST: EXPECTED["r03_manifest_sha256"],
        R03_RECEIPT: EXPECTED["r03_receipt_sha256"],
        DIAGNOSTIC_FAIL: EXPECTED["diagnostic_fail_sha256"],
        PARENT_L6_RAW: EXPECTED["parent_l6_raw_sha256"],
        PARENT_L6_REQUEST: EXPECTED["l6_request_sha256"],
        MODEL_RECEIPT: EXPECTED["model_receipt_sha256"],
        PREFLIGHT_RECEIPT: EXPECTED["preflight_receipt_sha256"],
        TRAINER: EXPECTED["trainer_sha256"],
        RUNTIME_RUNNER: EXPECTED["runtime_runner_sha256"],
        TRAIN: spec["training_input"]["sha256"],
        TOKEN_STATS: spec["token_accounting"]["sha256"],
    }
    for path, expected in fixed.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"STATIC_SHA_DRIFT:{path}")
    if sha256(Path(__file__)) != spec["components"]["runner_sha256"]:
        raise RuntimeError("RUNNER_SHA_DRIFT")
    if sha256(SCORER) != spec["components"]["scorer_sha256"]:
        raise RuntimeError("SCORER_SHA_DRIFT")
    if vendor_tree_sha(VENDOR) != EXPECTED["vendor_tree_sha256"]:
        raise RuntimeError("DERIVED_VENDOR_TREE_SHA_DRIFT")
    old_lines = OLD72.read_bytes().splitlines(keepends=True)
    train_lines = TRAIN.read_bytes().splitlines(keepends=True)
    if train_lines[:72] != old_lines or len(train_lines) != 96:
        raise RuntimeError("TRAIN96_OLD72_PREFIX_OR_ROW_COUNT_DRIFT")
    rows = read_jsonl(TRAIN)
    cases = [row["metadata"]["case_id"] for row in rows]
    counts = [len(strict_json_bytes(row["messages"][2]["content"].encode(), "assistant")["facts"]) for row in rows]
    if len(set(cases)) != 96 or sum(counts) != 879 or counts.count(0) != 15:
        raise RuntimeError("TRAIN96_CASE_FACT_OR_EMPTY_DRIFT")
    stats = read_json(TOKEN_STATS)
    if stats["combined"]["rows"] != 96 or stats["combined"]["assistant_loss_tokens"] <= 0:
        raise RuntimeError("TOKEN_STATS_DRIFT")
    if stats["combined"]["max_sequence_tokens"] > 4608 or stats["truncated_samples"] != 0:
        raise RuntimeError("TOKEN_LENGTH_GATE_FAILED")
    return {
        "status": "PASS_STATIC_PREPARED_NOT_RUN",
        "rows": 96,
        "facts": 879,
        "empty_answers": 15,
        "old72_prefix_byte_identical": True,
        "max_sequence_tokens": stats["combined"]["max_sequence_tokens"],
        "truncated_samples": 0,
        "base_l6_rows_reusable": 6,
        "base_l6_projection_sha256": hashlib.sha256(project_base_l6()).hexdigest(),
        "derived_trainer_sha256": EXPECTED["trainer_sha256"],
        "derived_vendor_tree_sha256": EXPECTED["vendor_tree_sha256"],
        "run_root_exists": RUN_ROOT.exists(),
        "model_loaded": False,
        "api_calls": 0,
    }


def validate_ticket(ticket_path: Path, command: str) -> tuple[dict[str, Any], bytes]:
    if not ticket_path.is_file():
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_MISSING")
    raw = ticket_path.read_bytes()
    ticket = strict_json_bytes(raw, str(ticket_path))
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_FIELDS_INVALID")
    if ticket["approved"] is not True or ticket["authorized_by"] != "CZ_CONTROL_WINDOW":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_NOT_APPROVED")
    if ticket["schema_version"] != "read1-train96-token-weighted-qualification-ticket/1.0":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_SCHEMA_INVALID")
    if ticket["scope"] != "READ1_TRAIN96_TOKEN_WEIGHTED_QUALIFICATION_SINGLE_RUN":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_SCOPE_INVALID")
    if ticket["run_id"] != RUN_ROOT.name or ticket["run_root"] != str(RUN_ROOT):
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_RUN_IDENTITY_INVALID")
    if ticket["authorized_commands"] != AUTHORIZED_COMMANDS or command not in AUTHORIZED_COMMANDS:
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_COMMAND_BOUNDARY_INVALID")
    for field in ("decision_id", "decision_text_sha256", "source_thread_id", "issued_at"):
        if not isinstance(ticket[field], str) or not ticket[field].strip():
            raise RuntimeError(f"CZ_CONTROL_WINDOW_TICKET_DECISION_FIELD_INVALID:{field}")
    spec = load_spec()
    expected = {
        "spec_sha256": sha256(SPEC_PATH),
        "train_input_sha256": sha256(TRAIN),
        "token_stats_sha256": sha256(TOKEN_STATS),
        "old_train72_sha256": EXPECTED["old_train72_sha256"],
        "r03_source_sha256": EXPECTED["r03_source_sha256"],
        "r03_gold_sha256": EXPECTED["r03_gold_sha256"],
        "r03_sidecar_sha256": EXPECTED["r03_sidecar_sha256"],
        "r03_manifest_sha256": EXPECTED["r03_manifest_sha256"],
        "r03_receipt_sha256": EXPECTED["r03_receipt_sha256"],
        "diagnostic_fail_sha256": EXPECTED["diagnostic_fail_sha256"],
        "parent_l6_raw_sha256": EXPECTED["parent_l6_raw_sha256"],
        "l6_request_sha256": EXPECTED["l6_request_sha256"],
        "base_l6_projection_sha256": EXPECTED["base_l6_projection_sha256"],
        "reducer_preflight_receipt_sha256": EXPECTED["preflight_receipt_sha256"],
        "derived_trainer_sha256": EXPECTED["trainer_sha256"],
        "derived_vendor_tree_sha256": EXPECTED["vendor_tree_sha256"],
        "runner_sha256": spec["components"]["runner_sha256"],
        "scorer_sha256": spec["components"]["scorer_sha256"],
    }
    for field, value in expected.items():
        if ticket[field] != value:
            raise RuntimeError(f"CZ_CONTROL_WINDOW_TICKET_IDENTITY_MISMATCH:{field}")
    return ticket, raw


def runtime_config() -> dict[str, Any]:
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
        "save_every": 48,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def load_runtime() -> Any:
    module_spec = importlib.util.spec_from_file_location("train96_runtime", RUNTIME_RUNNER)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("RUNTIME_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.VENDOR = VENDOR
    return module


def require_runtime_python() -> None:
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"WRONG_RUNTIME_PYTHON:{sys.executable}")


def no_other_training_process() -> None:
    result = subprocess.run(
        ["pgrep", "-fl", "mlx_lm.lora"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0 and result.stdout.strip():
        raise RuntimeError(f"OTHER_MLX_LORA_PROCESS:{result.stdout.strip()}")


def prepare_run_files(ticket: dict[str, Any], ticket_raw: bytes) -> None:
    import yaml

    if RUN_ROOT.exists():
        raise RuntimeError("RUN_ROOT_EXISTS_NO_RETRY")
    (RUN_ROOT / "data").mkdir(parents=True)
    shutil.copyfile(TRAIN, RUN_ROOT / "data/train.jsonl")
    shutil.copyfile(PARENT_L6_REQUEST, RUN_ROOT / "data/L6_V2_REQUESTS.jsonl")
    (RUN_ROOT / "data/BASE_L6_REUSED.jsonl").write_bytes(project_base_l6())
    (RUN_ROOT / "config").mkdir()
    (RUN_ROOT / "config/train96_token_weighted.yaml").write_text(
        yaml.safe_dump(runtime_config(), sort_keys=False, allow_unicode=True)
    )
    (RUN_ROOT / "AUTHORIZATION_TICKET.json").write_bytes(ticket_raw)
    write_json(
        RUN_ROOT / "RUN_IDENTITY.json",
        {
            "run_id": ticket["run_id"],
            "authorization_ticket_sha256": hashlib.sha256(ticket_raw).hexdigest(),
            "spec_sha256": sha256(SPEC_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "train_input_sha256": sha256(TRAIN),
            "token_stats_sha256": sha256(TOKEN_STATS),
            "r03_receipt_sha256": sha256(R03_RECEIPT),
            "diagnostic_fail_sha256": sha256(DIAGNOSTIC_FAIL),
            "base_l6_projection_sha256": sha256(RUN_ROOT / "data/BASE_L6_REUSED.jsonl"),
            "l6_request_sha256": sha256(RUN_ROOT / "data/L6_V2_REQUESTS.jsonl"),
            "derived_trainer_sha256": sha256(TRAINER),
            "derived_vendor_tree_sha256": vendor_tree_sha(VENDOR),
            "retry": 0,
            "api_calls": 0,
        },
    )


def frozen_ticket_matches(raw: bytes) -> None:
    frozen = RUN_ROOT / "AUTHORIZATION_TICKET.json"
    if not frozen.is_file() or frozen.read_bytes() != raw:
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_FROZEN_COPY_MISMATCH")


def train(ticket_path: Path) -> None:
    ticket, ticket_raw = validate_ticket(ticket_path, "train")
    static_check()
    require_runtime_python()
    runtime = load_runtime()
    if runtime.system_free_percent() < 8:
        raise RuntimeError("MEMORY_HARD_STOP_BEFORE_TRAINING")
    no_other_training_process()
    prepare_run_files(ticket, ticket_raw)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VENDOR)
    env["PYTHONUNBUFFERED"] = "1"
    command = [
        str(PYTHON),
        "-m",
        "mlx_lm.lora",
        "--config",
        str(RUN_ROOT / "config/train96_token_weighted.yaml"),
    ]
    began = time.monotonic()
    with (RUN_ROOT / "training.log").open("x") as log:
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
                free = runtime.system_free_percent()
                print(
                    f"TRAIN96_TOKEN_WEIGHTED_PROGRESS iteration={match.group(1)}/48 "
                    f"memory_free={free}%",
                    flush=True,
                )
                if free < 8:
                    child.terminate()
                    child.wait()
                    raise RuntimeError("MEMORY_HARD_STOP_DURING_TRAINING")
        code = child.wait()
    elapsed = round(time.monotonic() - began, 3)
    log_text = (RUN_ROOT / "training.log").read_text(errors="replace")
    final_adapter = RUN_ROOT / "adapters/adapters.safetensors"
    numbered = RUN_ROOT / "adapters/0000048_adapters.safetensors"
    if code != 0 or "Saved final weights" not in log_text or not final_adapter.is_file() or not numbered.is_file():
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{code}")
    if final_adapter.read_bytes() != numbered.read_bytes():
        raise RuntimeError("FINAL_AND_NUMBERED_CHECKPOINT_DIFFER")
    numbered.unlink()
    write_json(
        RUN_ROOT / "TRAINING_RESULT.json",
        {
            "status": "TRAIN96_TOKEN_WEIGHTED_TRAINED_FINAL_ONLY",
            "iterations": 48,
            "optimizer_updates": 12,
            "elapsed_seconds": elapsed,
            "final_adapter_sha256": sha256(final_adapter),
            "numbered_checkpoint_removed_after_byte_identity_check": True,
            "retry": 0,
            "api_calls": 0,
        },
    )


def verify_trained_state(ticket_raw: bytes) -> None:
    frozen_ticket_matches(ticket_raw)
    result_path = RUN_ROOT / "TRAINING_RESULT.json"
    adapter = RUN_ROOT / "adapters/adapters.safetensors"
    if not result_path.is_file() or not adapter.is_file():
        raise RuntimeError("TRAINING_NOT_COMPLETE")
    result = read_json(result_path)
    if result.get("status") != "TRAIN96_TOKEN_WEIGHTED_TRAINED_FINAL_ONLY":
        raise RuntimeError("TRAINING_RESULT_STATUS_DRIFT")
    if result.get("final_adapter_sha256") != sha256(adapter):
        raise RuntimeError("FINAL_ADAPTER_IDENTITY_DRIFT")


def infer_l6(ticket_path: Path) -> None:
    _, ticket_raw = validate_ticket(ticket_path, "infer-l6")
    static_check()
    require_runtime_python()
    verify_trained_state(ticket_raw)
    rows = read_jsonl(RUN_ROOT / "data/L6_V2_REQUESTS.jsonl")
    expected = [f"LC-L{i:02d}" for i in range(1, 7)]
    if len(rows) != 6 or [row["metadata"]["case_id"] for row in rows] != expected:
        raise RuntimeError("L6_REQUEST_DENOMINATOR_OR_ORDER_DRIFT")
    output = RUN_ROOT / "inference/L6_TRAIN96_TOKEN_WEIGHTED_LORA_RAW_6.jsonl"
    if output.exists():
        raise RuntimeError("L6_INFERENCE_OUTPUT_EXISTS_NO_RETRY")
    runtime = load_runtime()
    mx, load, stream_generate, make_sampler = runtime.configure_mlx()
    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(str(MODEL), adapter_path=str(RUN_ROOT / "adapters"))
    for index, row in enumerate(rows, 1):
        case_id = row["metadata"]["case_id"]
        result = runtime.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            "TRAIN96_TOKEN_WEIGHTED_LORA_L6",
            case_id,
            row["messages"],
            output,
        )
        print(
            f"TRAIN96_L6_INFER case={case_id} observed={index}/6 "
            f"repetition={result['repetition_detected']} "
            f"token_limit={result['token_limit_hit']}",
            flush=True,
        )
    del model
    mx.clear_cache()
    raw_rows = read_jsonl(output)
    if len(raw_rows) != 6 or [row.get("case_id") for row in raw_rows] != expected:
        raise RuntimeError("L6_INFERENCE_ROW_COUNT_OR_ORDER_DRIFT")
    write_json(
        RUN_ROOT / "inference/L6_RESULT.json",
        {
            "rows": 6,
            "raw_sha256": sha256(output),
            "base_rows_reused": 6,
            "repetition_rows": sum(row.get("repetition_detected") is True for row in raw_rows),
            "token_limit_rows": sum(row.get("token_limit_hit") is True for row in raw_rows),
            "duplicate_facts": sum(int(row.get("duplicate_facts", 0)) for row in raw_rows),
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "retry": 0,
            "api_calls": 0,
        },
    )


def status() -> None:
    print(
        json.dumps(
            {
                "run_root": str(RUN_ROOT),
                "run_exists": RUN_ROOT.exists(),
                "training_result": (RUN_ROOT / "TRAINING_RESULT.json").is_file(),
                "l6_raw": (RUN_ROOT / "inference/L6_TRAIN96_TOKEN_WEIGHTED_LORA_RAW_6.jsonl").is_file(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "train", "infer-l6", "status"))
    parser.add_argument("--ticket", type=Path)
    args = parser.parse_args()
    if args.command in AUTHORIZED_COMMANDS and args.ticket is None:
        parser.error(f"{args.command} requires --ticket from the CZ control window")
    if args.command == "static-check":
        print(json.dumps(static_check(), ensure_ascii=False, indent=2))
    elif args.command == "train":
        train(args.ticket)
    elif args.command == "infer-l6":
        infer_l6(args.ticket)
    else:
        status()


if __name__ == "__main__":
    main()
