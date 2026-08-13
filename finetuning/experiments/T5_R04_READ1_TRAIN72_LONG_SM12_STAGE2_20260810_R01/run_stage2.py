#!/usr/bin/env python3
"""Run one ticket-bound READ1 long-S/M Stage 2 continuation and L6 probe."""

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
SPEC_PATH = EXP / "STAGE2_SPEC.json"
TRAIN = EXP / "LONG_SM12_TRAIN.jsonl"
SCORER = EXP / "score_stage2_l6.py"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN72_LONG_SM12_STAGE2_R01"
PARENT_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01"
PARENT_ADAPTER = PARENT_RUN / "adapters/adapters.safetensors"
PARENT_ADAPTER_CONFIG = PARENT_RUN / "adapters/adapter_config.json"
PARENT_TRAINING_RESULT = PARENT_RUN / "TRAINING_RESULT.json"
PARENT_FAIL_TICKET = PARENT_RUN / "L6_MECHANICAL_FAIL_TICKET.json"
PARENT_L6_RAW = PARENT_RUN / "inference/L6_RAW_12.jsonl"
PARENT_L6_REQUEST = PARENT_RUN / "data/L6_V2_REQUESTS.jsonl"
SOURCE_TRAIN72 = (
    REPO
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN72_RENDER_CONTRACT_V2_20260809_R01"
    / "READ_1_TARGET_TRAIN72.jsonl"
)
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
RUNTIME_RUNNER = (
    REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/run_read1_low_dose.py"
)

TRAIN_SHA = "13c16c838c763ad716afbdf5d6dcb952486c7a477ebd73d35d857518a5ade7bc"
SOURCE_TRAIN72_SHA = "21213ae287d002351136b92c9caeb7388d2e71432574f9c8dcdf5ec1c3797f76"
PARENT_ADAPTER_SHA = "eeabed51700244b55b2953e08882fc45e253ab0dc850d4a6cae96a5088ec5d70"
PARENT_ADAPTER_CONFIG_SHA = "d5249eefbaf344a71fcd5b3a1c678db517ed8434ba33d225559e18687efc3005"
PARENT_TRAINING_RESULT_SHA = "64c1ae162db7d7bfb54336204aeee315f7f13de98f9e8d15263755a61ffcb387"
PARENT_FAIL_TICKET_SHA = "d4bde13591bff46613f43a50d948b990bba20e5162889ae4e5deb0bb0c587b53"
PARENT_L6_RAW_SHA = "e3c662cb87aaf8ba6862ce37c562de3752f554e2877079833da49e97dcf7646d"
PARENT_L6_REQUEST_SHA = "1aa942e9910fd3525f7c2fb7f3f23f9d706a2564870f3526319104dcfa42b3ec"
MODEL_RECEIPT_SHA = "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
TRAINER_SHA = "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909"
RUNTIME_RUNNER_SHA = "db9ae2a2c33dbbe3539f86fa9e45645e8dda6267ac42b5484b6b042290d80245"
MAX_OUTPUT_TOKENS = 2048
CASE_ORDER = [
    "LC-S01",
    "LC-M06",
    "LC-S02",
    "LC-M05",
    "LC-S03",
    "LC-M04",
    "LC-S04",
    "LC-M03",
    "LC-S05",
    "LC-M02",
    "LC-S06",
    "LC-M01",
]
FACT_COUNTS = [0, 10, 0, 8, 1, 7, 2, 6, 2, 5, 3, 4]
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
    "stage2_spec_sha256",
    "train_input_sha256",
    "parent_adapter_sha256",
    "parent_training_result_sha256",
    "parent_l6_fail_ticket_sha256",
    "parent_l6_raw_sha256",
    "l6_request_sha256",
    "runner_sha256",
    "scorer_sha256",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError(f"DUPLICATE_JSON_KEY:{label}:{key}")
            result[key] = value
        return result

    value = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{label}")
    return value


def read_json(path: Path) -> dict[str, Any]:
    return strict_json_bytes(path.read_bytes(), str(path))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(path.read_bytes().splitlines(), 1):
        if line.strip():
            rows.append(strict_json_bytes(line, f"{path}:{index}"))
    return rows


def compact_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_spec() -> dict[str, Any]:
    return read_json(SPEC_PATH)


def project_base_l6() -> bytes:
    rows = [row for row in read_jsonl(PARENT_L6_RAW) if row.get("variant") == "BASE_L6"]
    if len(rows) != 6 or [row.get("case_id") for row in rows] != [f"LC-L{i:02d}" for i in range(1, 7)]:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_DRIFT")
    return compact_jsonl(rows)


def static_check() -> dict[str, Any]:
    spec = load_spec()
    fixed = {
        TRAIN: TRAIN_SHA,
        SOURCE_TRAIN72: SOURCE_TRAIN72_SHA,
        PARENT_ADAPTER: PARENT_ADAPTER_SHA,
        PARENT_ADAPTER_CONFIG: PARENT_ADAPTER_CONFIG_SHA,
        PARENT_TRAINING_RESULT: PARENT_TRAINING_RESULT_SHA,
        PARENT_FAIL_TICKET: PARENT_FAIL_TICKET_SHA,
        PARENT_L6_RAW: PARENT_L6_RAW_SHA,
        PARENT_L6_REQUEST: PARENT_L6_REQUEST_SHA,
        MODEL_RECEIPT: MODEL_RECEIPT_SHA,
        TRAINER: TRAINER_SHA,
        RUNTIME_RUNNER: RUNTIME_RUNNER_SHA,
    }
    for path, expected in fixed.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"STATIC_SHA_DRIFT:{path}")
    if sha256(Path(__file__)) != spec["components"]["runner_sha256"]:
        raise RuntimeError("RUNNER_SHA_DRIFT")
    if sha256(SCORER) != spec["components"]["scorer_sha256"]:
        raise RuntimeError("SCORER_SHA_DRIFT")

    source_lines = SOURCE_TRAIN72.read_bytes().splitlines()
    if TRAIN.read_bytes().splitlines() != source_lines[36:48]:
        raise RuntimeError("LONG_SM12_NOT_EXACT_SOURCE_PROJECTION")
    rows = read_jsonl(TRAIN)
    if len(rows) != 12 or [row["metadata"]["case_id"] for row in rows] != CASE_ORDER:
        raise RuntimeError("LONG_SM12_CASE_ORDER_DRIFT")
    observed_facts = []
    for row in rows:
        if [message.get("role") for message in row.get("messages", [])] != ["system", "user", "assistant"]:
            raise RuntimeError("LONG_SM12_MESSAGE_SHAPE_DRIFT")
        answer = strict_json_bytes(row["messages"][2]["content"].encode("utf-8"), "assistant")
        if set(answer) != {"facts"} or not isinstance(answer["facts"], list):
            raise RuntimeError("LONG_SM12_ASSISTANT_SHAPE_DRIFT")
        observed_facts.append(len(answer["facts"]))
    if observed_facts != FACT_COUNTS or sum(observed_facts) != 48:
        raise RuntimeError("LONG_SM12_FACT_COUNT_DRIFT")
    parent_config = read_json(PARENT_ADAPTER_CONFIG)
    required_parent = {
        "fine_tune_type": "lora",
        "optimizer": "adam",
        "mask_prompt": True,
        "num_layers": 16,
        "batch_size": 2,
        "grad_accumulation_steps": 4,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
    }
    if any(parent_config.get(key) != value for key, value in required_parent.items()):
        raise RuntimeError("PARENT_RECIPE_IDENTITY_DRIFT")
    if parent_config.get("lora_parameters") != {"rank": 32, "dropout": 0.0, "scale": 0.125}:
        raise RuntimeError("PARENT_LORA_PARAMETERS_DRIFT")
    base_projection = project_base_l6()
    return {
        "status": "PASS_STATIC_PREPARED_NOT_RUN",
        "train_rows": 12,
        "train_facts": 48,
        "fact_counts": observed_facts,
        "base_l6_rows_reusable": 6,
        "base_l6_projection_sha256": hashlib.sha256(base_projection).hexdigest(),
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
    if ticket["schema_version"] != "read1-train72-long-sm12-stage2-execution-ticket/1.0":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_SCHEMA_INVALID")
    if ticket["scope"] != "READ1_TRAIN72_LONG_SM12_STAGE2_SINGLE_RUN":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_SCOPE_INVALID")
    if ticket["run_id"] != "T5_R04_READ1_TRAIN72_LONG_SM12_STAGE2_R01":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_RUN_ID_INVALID")
    if ticket["run_root"] != str(RUN_ROOT) or ticket["authorized_commands"] != AUTHORIZED_COMMANDS:
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_RUN_BOUNDARY_INVALID")
    if command not in ticket["authorized_commands"]:
        raise RuntimeError(f"CZ_CONTROL_WINDOW_TICKET_COMMAND_NOT_ALLOWED:{command}")
    for field in ("decision_id", "source_thread_id", "issued_at"):
        if not isinstance(ticket[field], str) or not ticket[field].strip():
            raise RuntimeError(f"CZ_CONTROL_WINDOW_TICKET_DECISION_FIELD_INVALID:{field}")
    if not re.fullmatch(r"[0-9a-f]{64}", ticket["decision_text_sha256"]):
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_DECISION_SHA_INVALID")
    spec = load_spec()
    expected = {
        "stage2_spec_sha256": sha256(SPEC_PATH),
        "train_input_sha256": TRAIN_SHA,
        "parent_adapter_sha256": PARENT_ADAPTER_SHA,
        "parent_training_result_sha256": PARENT_TRAINING_RESULT_SHA,
        "parent_l6_fail_ticket_sha256": PARENT_FAIL_TICKET_SHA,
        "parent_l6_raw_sha256": PARENT_L6_RAW_SHA,
        "l6_request_sha256": PARENT_L6_REQUEST_SHA,
        "runner_sha256": spec["components"]["runner_sha256"],
        "scorer_sha256": spec["components"]["scorer_sha256"],
    }
    for field, value in expected.items():
        if ticket[field] != value:
            raise RuntimeError(f"CZ_CONTROL_WINDOW_TICKET_IDENTITY_MISMATCH:{field}")
    return ticket, raw


def frozen_ticket_matches(raw: bytes) -> None:
    frozen = RUN_ROOT / "AUTHORIZATION_TICKET.json"
    if not frozen.is_file() or frozen.read_bytes() != raw:
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_FROZEN_COPY_MISMATCH")


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
        "iters": 12,
        "val_batches": 0,
        "learning_rate": 0.00001,
        "steps_per_report": 2,
        "steps_per_eval": 12,
        "grad_accumulation_steps": 4,
        "adapter_path": str(RUN_ROOT / "adapters"),
        "save_every": 12,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
        "resume_adapter_file": str(PARENT_ADAPTER),
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def load_runtime() -> Any:
    module_spec = importlib.util.spec_from_file_location("read1_long_sm12_stage2_runtime", RUNTIME_RUNNER)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("RUNTIME_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def no_other_training_process() -> None:
    result = subprocess.run(["pgrep", "-fl", "mlx_lm.lora"], capture_output=True, text=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        raise RuntimeError(f"OTHER_MLX_LORA_PROCESS:{result.stdout.strip()}")


def require_runtime_python() -> None:
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError(f"WRONG_RUNTIME_PYTHON:{sys.executable}")


def prepare_run_files(ticket: dict[str, Any], ticket_raw: bytes) -> None:
    import yaml

    if RUN_ROOT.exists():
        raise RuntimeError("RUN_ROOT_EXISTS_NO_RETRY")
    (RUN_ROOT / "data").mkdir(parents=True)
    shutil.copyfile(TRAIN, RUN_ROOT / "data/train.jsonl")
    shutil.copyfile(PARENT_L6_REQUEST, RUN_ROOT / "data/L6_V2_REQUESTS.jsonl")
    (RUN_ROOT / "data/BASE_L6_REUSED.jsonl").write_bytes(project_base_l6())
    (RUN_ROOT / "config").mkdir()
    (RUN_ROOT / "config/stage2.yaml").write_text(
        yaml.safe_dump(runtime_config(), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (RUN_ROOT / "AUTHORIZATION_TICKET.json").write_bytes(ticket_raw)
    write_json(
        RUN_ROOT / "RUN_IDENTITY.json",
        {
            "run_id": ticket["run_id"],
            "authorization_ticket_sha256": hashlib.sha256(ticket_raw).hexdigest(),
            "stage2_spec_sha256": sha256(SPEC_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "train_input_sha256": sha256(TRAIN),
            "parent_adapter_sha256": sha256(PARENT_ADAPTER),
            "parent_training_result_sha256": sha256(PARENT_TRAINING_RESULT),
            "parent_l6_fail_ticket_sha256": sha256(PARENT_FAIL_TICKET),
            "parent_l6_raw_sha256": sha256(PARENT_L6_RAW),
            "base_l6_projection_sha256": sha256(RUN_ROOT / "data/BASE_L6_REUSED.jsonl"),
            "l6_request_sha256": sha256(RUN_ROOT / "data/L6_V2_REQUESTS.jsonl"),
            "retry": 0,
            "api_calls": 0,
        },
    )


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
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(RUN_ROOT / "config/stage2.yaml")]
    began = time.monotonic()
    with (RUN_ROOT / "training.log").open("x", encoding="utf-8") as log:
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
                print(f"STAGE2_PROGRESS iteration={match.group(1)}/12 memory_free={free}%", flush=True)
                if free < 8:
                    child.terminate()
                    child.wait()
                    raise RuntimeError("MEMORY_HARD_STOP_DURING_TRAINING")
        code = child.wait()
    elapsed = round(time.monotonic() - began, 3)
    log_text = (RUN_ROOT / "training.log").read_text(encoding="utf-8", errors="replace")
    final_adapter = RUN_ROOT / "adapters/adapters.safetensors"
    numbered = RUN_ROOT / "adapters/0000012_adapters.safetensors"
    if code != 0 or "Saved final weights" not in log_text or not final_adapter.is_file() or not numbered.is_file():
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{code}")
    if final_adapter.read_bytes() != numbered.read_bytes():
        raise RuntimeError("FINAL_AND_NUMBERED_CHECKPOINT_DIFFER")
    numbered.unlink()
    if sha256(PARENT_ADAPTER) != PARENT_ADAPTER_SHA:
        raise RuntimeError("PARENT_ADAPTER_CHANGED_DURING_STAGE2")
    write_json(
        RUN_ROOT / "TRAINING_RESULT.json",
        {
            "status": "STAGE2_TRAINED_FINAL_ONLY",
            "iterations": 12,
            "optimizer_updates": 3,
            "elapsed_seconds": elapsed,
            "resume_adapter_file": str(PARENT_ADAPTER),
            "parent_adapter_sha256": PARENT_ADAPTER_SHA,
            "final_adapter_sha256": sha256(final_adapter),
            "numbered_checkpoint_removed_after_byte_identity_check": True,
            "retry": 0,
            "api_calls": 0,
        },
    )


def verify_trained_state(ticket_raw: bytes) -> None:
    frozen_ticket_matches(ticket_raw)
    result_path = RUN_ROOT / "TRAINING_RESULT.json"
    final_adapter = RUN_ROOT / "adapters/adapters.safetensors"
    if not result_path.is_file() or not final_adapter.is_file():
        raise RuntimeError("STAGE2_TRAINING_NOT_COMPLETE")
    result = read_json(result_path)
    if result.get("status") != "STAGE2_TRAINED_FINAL_ONLY":
        raise RuntimeError("STAGE2_TRAINING_RESULT_STATUS_DRIFT")
    if result.get("parent_adapter_sha256") != PARENT_ADAPTER_SHA:
        raise RuntimeError("STAGE2_PARENT_ADAPTER_IDENTITY_DRIFT")
    if result.get("final_adapter_sha256") != sha256(final_adapter):
        raise RuntimeError("STAGE2_FINAL_ADAPTER_IDENTITY_DRIFT")


def infer_l6(ticket_path: Path) -> None:
    _, ticket_raw = validate_ticket(ticket_path, "infer-l6")
    static_check()
    require_runtime_python()
    verify_trained_state(ticket_raw)
    request_path = RUN_ROOT / "data/L6_V2_REQUESTS.jsonl"
    rows = read_jsonl(request_path)
    if len(rows) != 6 or [row["metadata"]["case_id"] for row in rows] != [f"LC-L{i:02d}" for i in range(1, 7)]:
        raise RuntimeError("L6_REQUEST_DENOMINATOR_OR_ORDER_DRIFT")
    output = RUN_ROOT / "inference/L6_STAGE2_LORA_RAW_6.jsonl"
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
            "STAGE2_LORA_L6",
            case_id,
            row["messages"],
            output,
        )
        print(
            f"STAGE2_L6_INFER case={case_id} observed={index}/6 "
            f"repetition={result['repetition_detected']} token_limit={result['token_limit_hit']}",
            flush=True,
        )
    del model
    mx.clear_cache()
    raw_rows = read_jsonl(output)
    if len(raw_rows) != 6 or [row.get("case_id") for row in raw_rows] != [f"LC-L{i:02d}" for i in range(1, 7)]:
        raise RuntimeError("L6_INFERENCE_ROW_COUNT_OR_ORDER_DRIFT")
    write_json(
        RUN_ROOT / "inference/L6_RESULT.json",
        {
            "rows": 6,
            "raw_sha256": sha256(output),
            "base_rows_reused": 6,
            "parent_l6_raw_sha256": PARENT_L6_RAW_SHA,
            "repetition_rows": sum(row.get("repetition_detected") is True for row in raw_rows),
            "token_limit_rows": sum(row.get("token_limit_hit") is True for row in raw_rows),
            "duplicate_facts": sum(int(row.get("duplicate_facts", 0)) for row in raw_rows),
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "retry": 0,
            "api_calls": 0,
        },
    )


def status() -> None:
    result = {"run_root": str(RUN_ROOT), "run_exists": RUN_ROOT.exists(), "files": {}}
    for name in (
        "RUN_IDENTITY.json",
        "TRAINING_RESULT.json",
        "inference/L6_STAGE2_LORA_RAW_6.jsonl",
        "scoring/l6_pre/L6_MECHANICAL_GATE.json",
        "scoring/l6_final/L6_GATE.json",
    ):
        path = RUN_ROOT / name
        result["files"][name] = {"exists": path.is_file(), "sha256": sha256(path) if path.is_file() else None}
    print(json.dumps(result, ensure_ascii=False, indent=2))


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
