#!/usr/bin/env python3
"""Run exactly one authorized READ1 TRAIN72 V2 qualification flow."""

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
SPEC_PATH = EXP / "RUN_SPEC.json"
SCORER = EXP / "score_read1_train72_v2.py"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01"
TRAIN = (
    REPO
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN72_RENDER_CONTRACT_V2_20260809_R01"
    / "READ_1_TARGET_TRAIN72.jsonl"
)
L6_ROOT = REPO / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01"
L6_REQUEST = L6_ROOT / "READ_1_TARGET_L6_EVAL.jsonl"
L6_GOLD = L6_ROOT / "L6_GOLD_6.jsonl"
L6_INDEX = L6_ROOT / "L6_SOURCE_INDEX.jsonl"
REAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
REAL_REQUEST = REAL_ROOT / "READ_1_TARGET_EVAL24.jsonl"
REAL_GOLD = REAL_ROOT / "REAL24_GOLD_24.jsonl"
REAL_TXX = REAL_ROOT / "REAL24_TXX_MAP.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01"
    / "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
RUNTIME_RUNNER = (
    REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/run_read1_low_dose.py"
)

TRAIN_SHA = "21213ae287d002351136b92c9caeb7388d2e71432574f9c8dcdf5ec1c3797f76"
L6_REQUEST_SHA = "e96b8b5abb565f63e9bd3c2354c3a2a7366a4a646fb262379844c3fc32fb2503"
L6_V2_SHA = "1aa942e9910fd3525f7c2fb7f3f23f9d706a2564870f3526319104dcfa42b3ec"
L6_GOLD_SHA = "79ab2bf95aef439d3183d6cb1df3a59f6a3f706275714974fd4ed256469ba579"
L6_INDEX_SHA = "d09841d845b6bc080cadc354f26947995353e404a254e77f0e7eef9be6969687"
REAL_REQUEST_SHA = "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0"
REAL_V2_SHA = "dd8dcda9bf3e14fcb603043f2fc1c3e2505fbc65df5e6b9e94454d3b3492fe60"
REAL_GOLD_SHA = "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4"
REAL_TXX_SHA = "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a"
SCHEMA_SHA = "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14"
MODEL_RECEIPT_SHA = "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
TRAINER_SHA = "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909"
RUNTIME_RUNNER_SHA = "db9ae2a2c33dbbe3539f86fa9e45645e8dda6267ac42b5484b6b042290d80245"
MAX_OUTPUT_TOKENS = 2048
AUTHORIZED_COMMANDS = ["train", "infer-l6", "infer-real24"]
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
    "run_spec_sha256",
    "train_input_sha256",
    "l6_v2_request_sha256",
    "real24_v2_request_sha256",
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
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows).encode(
        "utf-8"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()


def load_spec() -> dict[str, Any]:
    return read_json(SPEC_PATH)


def system_contract() -> str:
    rows = read_jsonl(TRAIN)
    systems = {row["messages"][0]["content"] for row in rows}
    if len(systems) != 1:
        raise RuntimeError("TRAIN_SYSTEM_NOT_UNIQUE")
    return systems.pop()


def derive_v2_requests(source: Path, expected_rows: int) -> bytes:
    rows = read_jsonl(source)
    if len(rows) != expected_rows:
        raise RuntimeError(f"EVAL_REQUEST_DENOMINATOR_DRIFT:{source}")
    system = system_contract()
    derived = []
    for row in rows:
        item = json.loads(json.dumps(row, ensure_ascii=False))
        messages = item.get("messages")
        if not isinstance(messages, list) or [message.get("role") for message in messages] != ["system", "user"]:
            raise RuntimeError(f"EVAL_MESSAGE_SHAPE_DRIFT:{source}")
        messages[0]["content"] = system
        derived.append(item)
    return compact_jsonl(derived)


def static_check() -> dict[str, Any]:
    spec = load_spec()
    fixed = {
        TRAIN: TRAIN_SHA,
        L6_REQUEST: L6_REQUEST_SHA,
        L6_GOLD: L6_GOLD_SHA,
        L6_INDEX: L6_INDEX_SHA,
        REAL_REQUEST: REAL_REQUEST_SHA,
        REAL_GOLD: REAL_GOLD_SHA,
        REAL_TXX: REAL_TXX_SHA,
        SCHEMA: SCHEMA_SHA,
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

    train = read_jsonl(TRAIN)
    if len(train) != 72:
        raise RuntimeError("TRAIN72_ROW_DRIFT")
    fact_counts = []
    for row in train:
        if [message.get("role") for message in row.get("messages", [])] != ["system", "user", "assistant"]:
            raise RuntimeError("TRAIN72_MESSAGE_SHAPE_DRIFT")
        value = json.loads(row["messages"][2]["content"])
        if not isinstance(value, dict) or set(value) != {"facts"} or not isinstance(value["facts"], list):
            raise RuntimeError("TRAIN72_ASSISTANT_SHAPE_DRIFT")
        fact_counts.append(len(value["facts"]))
    if sum(fact_counts) != 830 or fact_counts.count(0) != 7:
        raise RuntimeError("TRAIN72_FACT_OR_EMPTY_DRIFT")

    l6_v2 = derive_v2_requests(L6_REQUEST, 6)
    real_v2 = derive_v2_requests(REAL_REQUEST, 24)
    if hashlib.sha256(l6_v2).hexdigest() != L6_V2_SHA:
        raise RuntimeError("L6_V2_DERIVATION_DRIFT")
    if hashlib.sha256(real_v2).hexdigest() != REAL_V2_SHA:
        raise RuntimeError("REAL24_V2_DERIVATION_DRIFT")
    if len(read_jsonl(L6_GOLD)) != 6 or len(read_jsonl(REAL_GOLD)) != 24:
        raise RuntimeError("EVAL_GOLD_DENOMINATOR_DRIFT")
    return {
        "train_rows": 72,
        "train_facts": 830,
        "train_empty_cases": 7,
        "l6_rows": 6,
        "real24_rows": 24,
        "l6_v2_sha256": L6_V2_SHA,
        "real24_v2_sha256": REAL_V2_SHA,
        "run_root_exists": RUN_ROOT.exists(),
    }


def validate_ticket(ticket_path: Path, command: str) -> tuple[dict[str, Any], bytes]:
    if not ticket_path.is_file():
        raise RuntimeError("CZ_AUTHORIZATION_TICKET_MISSING")
    raw = ticket_path.read_bytes()
    ticket = strict_json_bytes(raw, str(ticket_path))
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("CZ_AUTHORIZATION_TICKET_FIELDS_INVALID")
    if ticket["approved"] is not True or ticket["authorized_by"] != "CZ":
        raise RuntimeError("CZ_AUTHORIZATION_NOT_APPROVED")
    if ticket["schema_version"] != "read1-train72-v2-cz-execution-ticket/1.0":
        raise RuntimeError("CZ_AUTHORIZATION_SCHEMA_INVALID")
    if ticket["scope"] != "READ1_TRAIN72_V2_QUALIFICATION_SINGLE_RUN":
        raise RuntimeError("CZ_AUTHORIZATION_SCOPE_INVALID")
    if ticket["run_id"] != "T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01":
        raise RuntimeError("CZ_AUTHORIZATION_RUN_ID_INVALID")
    if ticket["run_root"] != str(RUN_ROOT) or ticket["authorized_commands"] != AUTHORIZED_COMMANDS:
        raise RuntimeError("CZ_AUTHORIZATION_RUN_BOUNDARY_INVALID")
    if command not in ticket["authorized_commands"]:
        raise RuntimeError(f"CZ_AUTHORIZATION_COMMAND_NOT_ALLOWED:{command}")
    for field in ("decision_id", "source_thread_id", "issued_at"):
        if not isinstance(ticket[field], str) or not ticket[field].strip():
            raise RuntimeError(f"CZ_AUTHORIZATION_DECISION_FIELD_INVALID:{field}")
    if not re.fullmatch(r"[0-9a-f]{64}", ticket["decision_text_sha256"]):
        raise RuntimeError("CZ_AUTHORIZATION_DECISION_SHA_INVALID")
    spec = load_spec()
    expected = {
        "run_spec_sha256": sha256(SPEC_PATH),
        "train_input_sha256": TRAIN_SHA,
        "l6_v2_request_sha256": L6_V2_SHA,
        "real24_v2_request_sha256": REAL_V2_SHA,
        "runner_sha256": spec["components"]["runner_sha256"],
        "scorer_sha256": spec["components"]["scorer_sha256"],
    }
    for field, value in expected.items():
        if ticket[field] != value:
            raise RuntimeError(f"CZ_AUTHORIZATION_IDENTITY_MISMATCH:{field}")
    return ticket, raw


def frozen_ticket_matches(raw: bytes) -> None:
    frozen = RUN_ROOT / "AUTHORIZATION_TICKET.json"
    if not frozen.is_file() or frozen.read_bytes() != raw:
        raise RuntimeError("CZ_AUTHORIZATION_FROZEN_COPY_MISMATCH")


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
        "iters": 36,
        "val_batches": 0,
        "learning_rate": 0.00003,
        "steps_per_report": 4,
        "steps_per_eval": 36,
        "grad_accumulation_steps": 4,
        "adapter_path": str(RUN_ROOT / "adapters"),
        "save_every": 36,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def load_runtime() -> Any:
    spec = importlib.util.spec_from_file_location("read1_train72_v2_runtime", RUNTIME_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("RUNTIME_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
    (RUN_ROOT / "data/L6_V2_REQUESTS.jsonl").write_bytes(derive_v2_requests(L6_REQUEST, 6))
    (RUN_ROOT / "data/REAL24_V2_REQUESTS.jsonl").write_bytes(derive_v2_requests(REAL_REQUEST, 24))
    (RUN_ROOT / "config").mkdir()
    (RUN_ROOT / "config/read1_train72_v2.yaml").write_text(
        yaml.safe_dump(runtime_config(), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (RUN_ROOT / "AUTHORIZATION_TICKET.json").write_bytes(ticket_raw)
    write_json(
        RUN_ROOT / "RUN_IDENTITY.json",
        {
            "run_id": ticket["run_id"],
            "authorization_ticket_sha256": hashlib.sha256(ticket_raw).hexdigest(),
            "run_spec_sha256": sha256(SPEC_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "train_input_sha256": sha256(TRAIN),
            "l6_v2_request_sha256": sha256(RUN_ROOT / "data/L6_V2_REQUESTS.jsonl"),
            "real24_v2_request_sha256": sha256(RUN_ROOT / "data/REAL24_V2_REQUESTS.jsonl"),
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
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(RUN_ROOT / "config/read1_train72_v2.yaml")]
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
                print(f"TRAIN72_V2_PROGRESS iteration={match.group(1)}/36 memory_free={free}%", flush=True)
                if free < 8:
                    child.terminate()
                    child.wait()
                    raise RuntimeError("MEMORY_HARD_STOP_DURING_TRAINING")
        code = child.wait()
    elapsed = round(time.monotonic() - began, 3)
    log_text = (RUN_ROOT / "training.log").read_text(encoding="utf-8", errors="replace")
    final_adapter = RUN_ROOT / "adapters/adapters.safetensors"
    numbered = RUN_ROOT / "adapters/0000036_adapters.safetensors"
    if code != 0 or "Saved final weights" not in log_text or not final_adapter.is_file() or not numbered.is_file():
        raise RuntimeError(f"TRAINING_FAILURE_NO_RETRY:{code}")
    if final_adapter.read_bytes() != numbered.read_bytes():
        raise RuntimeError("FINAL_AND_NUMBERED_CHECKPOINT_DIFFER")
    numbered.unlink()
    write_json(
        RUN_ROOT / "TRAINING_RESULT.json",
        {
            "status": "TRAINED_FINAL_ONLY",
            "iterations": 36,
            "optimizer_updates": 9,
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
    final_adapter = RUN_ROOT / "adapters/adapters.safetensors"
    if not result_path.is_file() or not final_adapter.is_file():
        raise RuntimeError("TRAINING_NOT_COMPLETE")
    result = read_json(result_path)
    if result.get("status") != "TRAINED_FINAL_ONLY" or result.get("final_adapter_sha256") != sha256(final_adapter):
        raise RuntimeError("TRAINING_RESULT_IDENTITY_DRIFT")


def generate_group(
    runtime: Any,
    load: Any,
    stream_generate: Any,
    sampler: Any,
    variant: str,
    rows: list[dict[str, Any]],
    output: Path,
    adapter_path: Path | None,
) -> None:
    kwargs = {"adapter_path": str(adapter_path)} if adapter_path is not None else {}
    model, tokenizer = load(str(MODEL), **kwargs)
    for index, row in enumerate(rows, 1):
        case_id = row["metadata"]["case_id"]
        result = runtime.generate_one(
            model,
            tokenizer,
            stream_generate,
            sampler,
            variant,
            case_id,
            row["messages"],
            output,
        )
        print(
            f"TRAIN72_V2_INFER variant={variant} case={case_id} observed={index}/{len(rows)} "
            f"repetition={result['repetition_detected']} token_limit={result['token_limit_hit']}",
            flush=True,
        )
    del model


def infer_group(ticket_path: Path, dataset: str) -> None:
    _, ticket_raw = validate_ticket(ticket_path, "infer-l6" if dataset == "l6" else "infer-real24")
    static_check()
    require_runtime_python()
    verify_trained_state(ticket_raw)
    if dataset == "real24":
        gate = RUN_ROOT / "scoring/l6_final/L6_GATE.json"
        if not gate.is_file() or read_json(gate).get("pass") is not True:
            raise RuntimeError("L6_GATE_NOT_PASSED_REAL24_FORBIDDEN")
    request_path = RUN_ROOT / ("data/L6_V2_REQUESTS.jsonl" if dataset == "l6" else "data/REAL24_V2_REQUESTS.jsonl")
    rows = read_jsonl(request_path)
    expected = 6 if dataset == "l6" else 24
    if len(rows) != expected:
        raise RuntimeError(f"RUNTIME_REQUEST_DENOMINATOR_DRIFT:{dataset}")
    output = RUN_ROOT / f"inference/{'L6_RAW_12' if dataset == 'l6' else 'REAL24_RAW_48'}.jsonl"
    if output.exists():
        raise RuntimeError(f"INFERENCE_OUTPUT_EXISTS_NO_RETRY:{dataset}")
    runtime = load_runtime()
    mx, load, stream_generate, make_sampler = runtime.configure_mlx()
    sampler = make_sampler(temp=0.0)
    generate_group(runtime, load, stream_generate, sampler, f"BASE_{dataset.upper()}", rows, output, None)
    mx.clear_cache()
    generate_group(runtime, load, stream_generate, sampler, f"LORA_{dataset.upper()}", rows, output, RUN_ROOT / "adapters")
    mx.clear_cache()
    raw_rows = read_jsonl(output)
    if len(raw_rows) != expected * 2:
        raise RuntimeError(f"INFERENCE_ROW_COUNT_DRIFT:{dataset}")
    write_json(
        RUN_ROOT / f"inference/{dataset.upper()}_RESULT.json",
        {
            "rows": len(raw_rows),
            "raw_sha256": sha256(output),
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
        "inference/L6_RAW_12.jsonl",
        "scoring/l6_final/L6_GATE.json",
        "inference/REAL24_RAW_48.jsonl",
        "scoring/real24_final/REAL24_GATE.json",
    ):
        path = RUN_ROOT / name
        result["files"][name] = {"exists": path.is_file(), "sha256": sha256(path) if path.is_file() else None}
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "train", "infer-l6", "infer-real24", "status"))
    parser.add_argument("--ticket", type=Path)
    args = parser.parse_args()
    if args.command in AUTHORIZED_COMMANDS and args.ticket is None:
        parser.error(f"{args.command} requires --ticket from the CZ control window")
    if args.command == "static-check":
        print(json.dumps(static_check(), ensure_ascii=False, indent=2))
    elif args.command == "train":
        train(args.ticket)
    elif args.command == "infer-l6":
        infer_group(args.ticket, "l6")
    elif args.command == "infer-real24":
        infer_group(args.ticket, "real24")
    else:
        status()


if __name__ == "__main__":
    main()
