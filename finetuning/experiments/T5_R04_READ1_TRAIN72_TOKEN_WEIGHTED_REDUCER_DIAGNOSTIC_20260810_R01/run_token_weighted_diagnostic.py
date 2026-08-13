#!/usr/bin/env python3
"""Run one ticket-bound READ1 TRAIN72 token-weighted-reducer-diagnostic qualification."""

from __future__ import annotations

import argparse
from collections import Counter
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
DENSITY_PACKAGE = (
    REPO / "finetuning/experiments/T5_R04_READ1_TRAIN72_DENSITY_PAIRED_20260810_R01"
)
TRAIN = DENSITY_PACKAGE / "READ_1_TARGET_TRAIN72_DENSITY_PAIRED.jsonl"
PAIR_MAP = DENSITY_PACKAGE / "DENSITY_PAIR_MAP.json"
OLD_DENSITY_SPEC = DENSITY_PACKAGE / "DENSITY_PAIRED_SPEC.json"
SCORER = EXP / "score_token_weighted_diagnostic.py"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN72_TOKEN_WEIGHTED_REDUCER_DIAGNOSTIC_R01"
SOURCE_TRAIN = (
    REPO
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN72_RENDER_CONTRACT_V2_20260809_R01"
    / "READ_1_TARGET_TRAIN72.jsonl"
)
PARENT_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01"
PARENT_FAIL_TICKET = PARENT_RUN / "L6_MECHANICAL_FAIL_TICKET.json"
STAGE2_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_LONG_SM12_STAGE2_R01"
STAGE2_FAIL_TICKET = STAGE2_RUN / "L6_MECHANICAL_FAIL_TICKET.json"
OLD_DENSITY_RUN = REPO / "runs/T5_R04_READ1_TRAIN72_DENSITY_PAIRED_R01"
OLD_DENSITY_FAIL_TICKET = OLD_DENSITY_RUN / "L6_MECHANICAL_FAIL_TICKET.json"
PARENT_L6_RAW = PARENT_RUN / "inference/L6_RAW_12.jsonl"
PARENT_L6_REQUEST = PARENT_RUN / "data/L6_V2_REQUESTS.jsonl"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
PREFLIGHT = REPO / "finetuning/experiments/T5_R04_TOKEN_WEIGHTED_GRAD_ACCUM_PREFLIGHT_20260810_R01"
PREFLIGHT_RECEIPT = PREFLIGHT / "PREPARE_RECEIPT.json"
VENDOR = PREFLIGHT / "vendor_token_weighted"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
RUNTIME_RUNNER = (
    REPO / "finetuning/experiments/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/run_read1_low_dose.py"
)

TRAIN_SHA = "9c1a2202380f5c589d590a34354309643b1bb8fc0a12732184e11a282c924797"
PAIR_MAP_SHA = "5150d835085a92af6df6e9fe140fe82f0afab2e649d6b986a5ed3f146953bcdc"
SOURCE_TRAIN_SHA = "21213ae287d002351136b92c9caeb7388d2e71432574f9c8dcdf5ec1c3797f76"
PAYLOAD_MULTISET_SHA = "682b2cea7050f54a4b86667565993fa3aca736d37aea3eeaebef0fde9c989f74"
PARENT_FAIL_TICKET_SHA = "d4bde13591bff46613f43a50d948b990bba20e5162889ae4e5deb0bb0c587b53"
STAGE2_FAIL_TICKET_SHA = "c2ccee02959307e291f3b38a3ba7882dfd6434d54c9539625e4d983aeb9d1c1a"
OLD_DENSITY_FAIL_TICKET_SHA = "b0674dcf87a355798659f893f650f397c6c329c60d34898c58778ce5f6ca7146"
PARENT_L6_RAW_SHA = "e3c662cb87aaf8ba6862ce37c562de3752f554e2877079833da49e97dcf7646d"
PARENT_L6_REQUEST_SHA = "1aa942e9910fd3525f7c2fb7f3f23f9d706a2564870f3526319104dcfa42b3ec"
BASE_L6_PROJECTION_SHA = "db5d40432a0849b78f3d5a09824251af4574002205b5221892bc9b32b3649476"
MODEL_RECEIPT_SHA = "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
PREFLIGHT_RECEIPT_SHA = "4e46a23ca6da1741c1027884a2a4e9c35cd3fb21576c1f8e58fc97166a08d31c"
TRAINER_SHA = "2ff621480fb043220f8dff29d01f85f6e8f8ffe9b04fb2eebc415a837b0be1c6"
VENDOR_TREE_SHA = "2e77413bec6141f2a71b1fac032f5967bdfb9e2b65ba43a1b484d78d4e1f8059"
RUNTIME_RUNNER_SHA = "db9ae2a2c33dbbe3539f86fa9e45645e8dda6267ac42b5484b6b042290d80245"
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
    "pair_map_sha256",
    "source_train_sha256",
    "parent_fail_ticket_sha256",
    "stage2_fail_ticket_sha256",
    "old_density_fail_ticket_sha256",
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


def multiset_sha(lines: list[bytes]) -> str:
    return hashlib.sha256(b"\n".join(sorted(lines)) + b"\n").hexdigest()


def vendor_tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
        digest.update(b"\0")
    return digest.hexdigest()


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
    return [strict_json_bytes(line, f"{path}:{i}") for i, line in enumerate(path.read_bytes().splitlines(), 1) if line.strip()]


def compact_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_spec() -> dict[str, Any]:
    return read_json(SPEC_PATH)


def project_base_l6() -> bytes:
    rows = [row for row in read_jsonl(PARENT_L6_RAW) if row.get("variant") == "BASE_L6"]
    expected = [f"LC-L{i:02d}" for i in range(1, 7)]
    if len(rows) != 6 or [row.get("case_id") for row in rows] != expected:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_DRIFT")
    projected = compact_jsonl(rows)
    if hashlib.sha256(projected).hexdigest() != BASE_L6_PROJECTION_SHA:
        raise RuntimeError("PARENT_BASE_L6_PROJECTION_SHA_DRIFT")
    return projected


def static_check() -> dict[str, Any]:
    spec = load_spec()
    fixed = {
        TRAIN: TRAIN_SHA,
        PAIR_MAP: PAIR_MAP_SHA,
        SOURCE_TRAIN: SOURCE_TRAIN_SHA,
        PARENT_FAIL_TICKET: PARENT_FAIL_TICKET_SHA,
        STAGE2_FAIL_TICKET: STAGE2_FAIL_TICKET_SHA,
        OLD_DENSITY_FAIL_TICKET: OLD_DENSITY_FAIL_TICKET_SHA,
        PARENT_L6_RAW: PARENT_L6_RAW_SHA,
        PARENT_L6_REQUEST: PARENT_L6_REQUEST_SHA,
        MODEL_RECEIPT: MODEL_RECEIPT_SHA,
        PREFLIGHT_RECEIPT: PREFLIGHT_RECEIPT_SHA,
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
    if vendor_tree_sha(VENDOR) != VENDOR_TREE_SHA:
        raise RuntimeError("DERIVED_VENDOR_TREE_SHA_DRIFT")
    source_lines = SOURCE_TRAIN.read_bytes().splitlines()
    train_lines = TRAIN.read_bytes().splitlines()
    if Counter(source_lines) != Counter(train_lines):
        raise RuntimeError("TRAIN72_PAYLOAD_MULTISET_DRIFT")
    if multiset_sha(source_lines) != PAYLOAD_MULTISET_SHA or multiset_sha(train_lines) != PAYLOAD_MULTISET_SHA:
        raise RuntimeError("TRAIN72_PAYLOAD_MULTISET_SHA_DRIFT")
    source_rows = read_jsonl(SOURCE_TRAIN)
    rows = read_jsonl(TRAIN)
    if len(rows) != 72 or rows[:36] != source_rows[:36]:
        raise RuntimeError("TRAIN72_ROW_COUNT_OR_DENSE_PREFIX_DRIFT")
    facts = []
    cases = []
    for row in rows:
        cases.append(row["metadata"]["case_id"])
        answer = strict_json_bytes(row["messages"][2]["content"].encode(), "assistant")
        facts.append(len(answer["facts"]))
    if len(set(cases)) != 72 or sum(facts) != 830 or facts.count(0) != 7:
        raise RuntimeError("TRAIN72_CASE_FACT_OR_EMPTY_DRIFT")
    pair_map = read_json(PAIR_MAP)
    if pair_map.get("line_payload_multiset_equal") is not True:
        raise RuntimeError("PAIR_MAP_MULTISET_NOT_EQUAL")
    if pair_map.get("empty_answer_paired_with_4_to_10_fact_answer") != 0:
        raise RuntimeError("PAIR_MAP_EMPTY_HIGH_DENSITY_PAIR_REMAINS")
    if len(pair_map.get("batches", [])) != 36:
        raise RuntimeError("PAIR_MAP_BATCH_COUNT_DRIFT")
    for index, batch in enumerate(pair_map["batches"]):
        expected_cases = cases[index * 2 : index * 2 + 2]
        expected_facts = facts[index * 2 : index * 2 + 2]
        if [case["case_id"] for case in batch["cases"]] != expected_cases:
            raise RuntimeError("PAIR_MAP_CASE_ORDER_DRIFT")
        if batch["fact_count_pair"] != expected_facts:
            raise RuntimeError("PAIR_MAP_FACT_COUNT_DRIFT")
    return {
        "status": "PASS_STATIC_PREPARED_NOT_RUN",
        "rows": 72,
        "facts": 830,
        "empty_answers": 7,
        "payload_multiset_sha256": PAYLOAD_MULTISET_SHA,
        "empty_paired_with_4_to_10": 0,
        "base_l6_rows_reusable": 6,
        "base_l6_projection_sha256": hashlib.sha256(project_base_l6()).hexdigest(),
        "derived_trainer_sha256": TRAINER_SHA,
        "derived_vendor_tree_sha256": VENDOR_TREE_SHA,
        "only_experimental_variable": "optimizer_window_gradient_reducer_normalization",
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
    if ticket["schema_version"] != "read1-train72-token-weighted-reducer-diagnostic-execution-ticket/1.0":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_SCHEMA_INVALID")
    if ticket["scope"] != "READ1_TRAIN72_TOKEN_WEIGHTED_DIAGNOSTIC_SINGLE_RUN":
        raise RuntimeError("CZ_CONTROL_WINDOW_TICKET_SCOPE_INVALID")
    if ticket["run_id"] != "T5_R04_READ1_TRAIN72_TOKEN_WEIGHTED_REDUCER_DIAGNOSTIC_R01":
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
        "spec_sha256": sha256(SPEC_PATH),
        "train_input_sha256": TRAIN_SHA,
        "pair_map_sha256": PAIR_MAP_SHA,
        "source_train_sha256": SOURCE_TRAIN_SHA,
        "parent_fail_ticket_sha256": PARENT_FAIL_TICKET_SHA,
        "stage2_fail_ticket_sha256": STAGE2_FAIL_TICKET_SHA,
        "old_density_fail_ticket_sha256": OLD_DENSITY_FAIL_TICKET_SHA,
        "parent_l6_raw_sha256": PARENT_L6_RAW_SHA,
        "l6_request_sha256": PARENT_L6_REQUEST_SHA,
        "base_l6_projection_sha256": BASE_L6_PROJECTION_SHA,
        "reducer_preflight_receipt_sha256": PREFLIGHT_RECEIPT_SHA,
        "derived_trainer_sha256": TRAINER_SHA,
        "derived_vendor_tree_sha256": VENDOR_TREE_SHA,
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
    module_spec = importlib.util.spec_from_file_location("read1_token_weighted_diagnostic_runtime", RUNTIME_RUNNER)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("RUNTIME_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.VENDOR = VENDOR
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
    (RUN_ROOT / "config/token_weighted_diagnostic.yaml").write_text(
        yaml.safe_dump(runtime_config(), sort_keys=False, allow_unicode=True), encoding="utf-8"
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
            "pair_map_sha256": sha256(PAIR_MAP),
            "source_train_sha256": sha256(SOURCE_TRAIN),
            "parent_fail_ticket_sha256": sha256(PARENT_FAIL_TICKET),
            "stage2_fail_ticket_sha256": sha256(STAGE2_FAIL_TICKET),
            "old_density_fail_ticket_sha256": sha256(OLD_DENSITY_FAIL_TICKET),
            "base_l6_projection_sha256": sha256(RUN_ROOT / "data/BASE_L6_REUSED.jsonl"),
            "l6_request_sha256": sha256(RUN_ROOT / "data/L6_V2_REQUESTS.jsonl"),
            "reducer_preflight_receipt_sha256": sha256(PREFLIGHT_RECEIPT),
            "derived_trainer_sha256": sha256(TRAINER),
            "derived_vendor_tree_sha256": vendor_tree_sha(VENDOR),
            "only_experimental_variable": "optimizer_window_gradient_reducer_normalization",
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
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(RUN_ROOT / "config/token_weighted_diagnostic.yaml")]
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
                print(f"TOKEN_WEIGHTED_DIAGNOSTIC_PROGRESS iteration={match.group(1)}/36 memory_free={free}%", flush=True)
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
            "status": "TOKEN_WEIGHTED_DIAGNOSTIC_TRAINED_FINAL_ONLY",
            "iterations": 36,
            "optimizer_updates": 9,
            "elapsed_seconds": elapsed,
            "final_adapter_sha256": sha256(final_adapter),
            "numbered_checkpoint_removed_after_byte_identity_check": True,
            "retry": 0,
            "api_calls": 0,
            "derived_trainer_sha256": TRAINER_SHA,
            "derived_vendor_tree_sha256": VENDOR_TREE_SHA,
        },
    )


def verify_trained_state(ticket_raw: bytes) -> None:
    frozen_ticket_matches(ticket_raw)
    result_path = RUN_ROOT / "TRAINING_RESULT.json"
    final_adapter = RUN_ROOT / "adapters/adapters.safetensors"
    if not result_path.is_file() or not final_adapter.is_file():
        raise RuntimeError("TRAINING_NOT_COMPLETE")
    result = read_json(result_path)
    if result.get("status") != "TOKEN_WEIGHTED_DIAGNOSTIC_TRAINED_FINAL_ONLY":
        raise RuntimeError("TRAINING_RESULT_STATUS_DRIFT")
    if result.get("final_adapter_sha256") != sha256(final_adapter):
        raise RuntimeError("FINAL_ADAPTER_IDENTITY_DRIFT")


def infer_l6(ticket_path: Path) -> None:
    _, ticket_raw = validate_ticket(ticket_path, "infer-l6")
    static_check()
    require_runtime_python()
    verify_trained_state(ticket_raw)
    request_path = RUN_ROOT / "data/L6_V2_REQUESTS.jsonl"
    rows = read_jsonl(request_path)
    expected = [f"LC-L{i:02d}" for i in range(1, 7)]
    if len(rows) != 6 or [row["metadata"]["case_id"] for row in rows] != expected:
        raise RuntimeError("L6_REQUEST_DENOMINATOR_OR_ORDER_DRIFT")
    output = RUN_ROOT / "inference/L6_TOKEN_WEIGHTED_DIAGNOSTIC_LORA_RAW_6.jsonl"
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
            "TOKEN_WEIGHTED_DIAGNOSTIC_LORA_L6",
            case_id,
            row["messages"],
            output,
        )
        print(
            f"TOKEN_WEIGHTED_DIAGNOSTIC_L6_INFER case={case_id} observed={index}/6 "
            f"repetition={result['repetition_detected']} token_limit={result['token_limit_hit']}",
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
        "inference/L6_TOKEN_WEIGHTED_DIAGNOSTIC_LORA_RAW_6.jsonl",
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
