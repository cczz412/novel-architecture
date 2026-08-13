#!/usr/bin/env python3
"""Ticket-bound READ1/2/4 low-dose B-contract relative screen."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
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
SPEC = EXP / "SPEC.json"
SCORER = EXP / "score_relative_screen.py"
RUN_ROOT = REPO / "runs/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
RUN_ID = "T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
MODEL = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/models/"
    "Qwen3-4B-Instruct-2507_cdbee75f"
)
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
MODEL_RECEIPT_SHA = "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
MODEL_FILE_COUNT = 13
MODEL_TOTAL_BYTES = 8_060_917_568
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = (
    REPO
    / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
)
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
TRAINER_SHA = "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909"
TRAIN_ROOT = (
    REPO
    / "finetuning/experiments/T5_R04_READ_CONTEXT_TRAIN36_RENDER_20260809_R01"
)
EVAL_ROOT = (
    REPO
    / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
)
TRAIN_PATHS = {
    "READ1": TRAIN_ROOT / "READ_1_TARGET_TRAIN36.jsonl",
    "READ2": TRAIN_ROOT / "READ_2_HALO180_TRAIN36.jsonl",
    "READ4": TRAIN_ROOT / "READ_4_FULL_CHAPTER_TRAIN36.jsonl",
}
TRAIN_SHA = {
    "READ1": "84ad6f7886b372334b008d49cc2f3343afdd6b98d83a24a00d604ae49b8f09e0",
    "READ2": "09fdbc52f7131f1a2a60552740ce28430e418ed84c858f0f997abda16e4a7c5e",
    "READ4": "93b3ab7e9beed9a6f54df751400ba2ac65cfd5a18f1865da01c7c0c81540ed4a",
}
EVAL_PATHS = {
    "READ1": EVAL_ROOT / "READ_1_TARGET_EVAL24.jsonl",
    "READ2": EVAL_ROOT / "READ_2_HALO180_EVAL24.jsonl",
    "READ4": EVAL_ROOT / "READ_4_FULL_CHAPTER_EVAL24.jsonl",
}
EVAL_SHA = {
    "READ1": "73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0",
    "READ2": "a12f1f5cb1adfed4958418bfa8373af52b6305fdef64122c9bf02e3338c77e85",
    "READ4": "350799084dbc15791bc3b46a669552aec2da7920bfa39c8a3a110e1cbe431d4f",
}
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
TXX = EVAL_ROOT / "REAL24_TXX_MAP.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/"
    "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
READ1_VIEW = (
    REPO
    / "runs/T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/adapter_views/iter24"
)
READ1_ADAPTER = READ1_VIEW / "adapters.safetensors"
READ1_CONFIG = READ1_VIEW / "adapter_config.json"
AB8_RUN = REPO / "runs/T5_R04_READ1_FORMAT_CONTRACT_AB8_R01"
AB8_REQUESTS = AB8_RUN / "FORMAT_B_REQUESTS_8.jsonl"
AB8_RAW = AB8_RUN / "FORMAT_B_RAW_8.jsonl"
AB8_ADJUDICATIONS = AB8_RUN / "FORMAT_B_ADJUDICATIONS.jsonl"
AB8_FINAL = AB8_RUN / "FORMAT_AB8_FINAL_METRICS.json"
AB8_TICKET = (
    REPO
    / "finetuning/experiments/T5_R04_READ1_FORMAT_CONTRACT_AB8_20260809_R01/"
    "RESULT_TICKET.md"
)
CASES8 = ("C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24")
ARMS = ("READ1", "READ2", "READ4")
NEW_ARMS = ("READ2", "READ4")
CONTRACT = (
    "【输出合同】输出必须是且只能是一个顶层键为 facts 的 JSON 对象；facts 为数组且允许为空，"
    "每个元素只能且必须包含 fact、status、speaker、evidence_ids，fact 为非空字符串，"
    "speaker 为字符串或 null，evidence_ids 为字符串数组，status 只能取“已发生”“正在发生”"
    "“计划”“承诺”“条件”“推测”“误信”“否定”之一；不得输出其他字段、Markdown 或解释。"
)
EXPECTED = {
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "read1_adapter_sha256": "7b01e203e45beb9562e55dff902bc0ecfd56c312f5a0a679c69813014ed14b1f",
    "read1_config_sha256": "f18f85d70333202c43294bc057e4565773e3b360fd880f710031ebcce27c23b8",
    "ab8_requests_sha256": "10969ace5317a7edd05a0ed89a79bac2e32cb9bb55a4a02a09c69a08ba45a663",
    "ab8_raw_sha256": "d79e768c1163085016472591e47e92a203421d73266f78daf51e952b71690351",
    "ab8_adjudications_sha256": "810fa1a4427b743854fc70def399a5635efe06c71daaf9feb0babd514aa1150f",
    "ab8_final_sha256": "58087ff31edbf80315fe05b76341c2437e5722634970fffed7a8a6f3235bea43",
    "ab8_result_ticket_sha256": "8ac276c9648657d4c488d3973092858e645afb2c600c78c6a0f7de18a0e72e61",
}
AUTHORIZED_COMMANDS = ["train-new-arms", "infer-stage1", "infer-full24"]
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
    "runner_sha256",
    "scorer_sha256",
    "model_receipt_sha256",
    "trainer_sha256",
    "train_read1_sha256",
    "train_read2_sha256",
    "train_read4_sha256",
    "eval_read1_sha256",
    "eval_read2_sha256",
    "eval_read4_sha256",
    "gold_sha256",
    "txx_sha256",
    "schema_sha256",
    "read1_adapter_sha256",
    "read1_adapter_config_sha256",
    "ab8_requests_sha256",
    "ab8_raw_sha256",
    "ab8_adjudications_sha256",
    "ab8_final_metrics_sha256",
    "ab8_result_ticket_sha256",
}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(path: Path) -> dict[str, Any]:
    def reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError(f"DUPLICATE_JSON_KEY:{path}:{key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject
    )
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def system_free_percent() -> int:
    result = subprocess.run(
        ["memory_pressure", "-Q"], text=True, capture_output=True, check=False
    )
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else -1


def active_lora_processes() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", r"[m]lx_lm.*lora"],
        text=True,
        capture_output=True,
        check=False,
    )
    return [int(item) for item in result.stdout.split() if item.isdigit()]


def verify_model_receipt_members() -> dict[str, Any]:
    if sha256(MODEL_RECEIPT) != MODEL_RECEIPT_SHA:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    receipt = strict_json(MODEL_RECEIPT)
    if receipt.get("revision") != MODEL_REVISION:
        raise RuntimeError("MODEL_REVISION_DRIFT")
    files = receipt.get("files")
    if not isinstance(files, list) or len(files) != MODEL_FILE_COUNT:
        raise RuntimeError("MODEL_RECEIPT_FILE_COUNT_DRIFT")
    total = 0
    for row in files:
        member = MODEL / row["path"]
        if not member.is_file() or member.stat().st_size != row["bytes"]:
            raise RuntimeError(f"MODEL_MEMBER_MISSING_OR_SIZE_DRIFT:{row['path']}")
        if sha256(member) != row["sha256"]:
            raise RuntimeError(f"MODEL_MEMBER_SHA_DRIFT:{row['path']}")
        total += row["bytes"]
    if total != MODEL_TOTAL_BYTES:
        raise RuntimeError("MODEL_TOTAL_BYTES_DRIFT")
    return {"member_count": len(files), "total_bytes": total}


def verify_static_inputs() -> dict[str, Any]:
    checks = {
        "trainer_sha256": sha256(TRAINER),
        "model_receipt_sha256": sha256(MODEL_RECEIPT),
        "gold_sha256": sha256(GOLD),
        "txx_sha256": sha256(TXX),
        "schema_sha256": sha256(SCHEMA),
        "read1_adapter_sha256": sha256(READ1_ADAPTER),
        "read1_config_sha256": sha256(READ1_CONFIG),
        "ab8_requests_sha256": sha256(AB8_REQUESTS),
        "ab8_raw_sha256": sha256(AB8_RAW),
        "ab8_adjudications_sha256": sha256(AB8_ADJUDICATIONS),
        "ab8_final_sha256": sha256(AB8_FINAL),
        "ab8_result_ticket_sha256": sha256(AB8_TICKET),
    }
    expected_checks = {
        "trainer_sha256": TRAINER_SHA,
        "model_receipt_sha256": MODEL_RECEIPT_SHA,
        **EXPECTED,
    }
    if checks != expected_checks:
        raise RuntimeError(f"STATIC_INPUT_SHA_DRIFT:{checks}")
    for arm in ARMS:
        if sha256(TRAIN_PATHS[arm]) != TRAIN_SHA[arm]:
            raise RuntimeError(f"TRAIN_SHA_DRIFT:{arm}")
        if sha256(EVAL_PATHS[arm]) != EVAL_SHA[arm]:
            raise RuntimeError(f"EVAL_SHA_DRIFT:{arm}")
    train_rows = {arm: read_jsonl(TRAIN_PATHS[arm]) for arm in ARMS}
    case_orders = {
        arm: [row.get("metadata", {}).get("case_id") for row in rows]
        for arm, rows in train_rows.items()
    }
    if any(len(rows) != 36 for rows in train_rows.values()):
        raise RuntimeError("TRAIN_ROW_COUNT_DRIFT")
    if len({tuple(value) for value in case_orders.values()}) != 1:
        raise RuntimeError("TRAIN_CASE_ORDER_CROSS_ARM_DRIFT")
    facts: dict[str, int] = {}
    for arm, rows in train_rows.items():
        facts[arm] = sum(
            len(json.loads(row["messages"][2]["content"])["facts"])
            for row in rows
        )
        if facts[arm] != 714:
            raise RuntimeError(f"TRAIN_FACT_COUNT_DRIFT:{arm}:{facts[arm]}")
    for index in range(36):
        messages = [train_rows[arm][index]["messages"] for arm in ARMS]
        if any([item["role"] for item in value] != ["system", "user", "assistant"] for value in messages):
            raise RuntimeError(f"TRAIN_MESSAGE_SHAPE_DRIFT:{index}")
        if not (messages[0][0] == messages[1][0] == messages[2][0]):
            raise RuntimeError(f"TRAIN_SYSTEM_CROSS_ARM_DRIFT:{index}")
        if not (messages[0][2] == messages[1][2] == messages[2][2]):
            raise RuntimeError(f"TRAIN_ASSISTANT_CROSS_ARM_DRIFT:{index}")
        if len({value[1]["content"] for value in messages}) != 3:
            raise RuntimeError(f"TRAIN_USER_READ_SCOPE_NOT_DISTINCT:{index}")
        if any(CONTRACT in value[0]["content"] for value in messages):
            raise RuntimeError(f"B_CONTRACT_LEAKED_INTO_TRAIN_SYSTEM:{index}")
    return {
        "train_rows": 36,
        "facts_per_arm": facts,
        "case_order_equal": True,
        "system_equal": True,
        "assistant_equal": True,
        "only_user_read_scope_differs": True,
        "sha_checks": checks,
    }


def validate_ticket(ticket_path: Path, command: str) -> dict[str, Any]:
    ticket = strict_json(ticket_path)
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError(
            f"TICKET_KEYS_DRIFT:missing={sorted(TICKET_KEYS-set(ticket))}:"
            f"extra={sorted(set(ticket)-TICKET_KEYS)}"
        )
    fixed = {
        "schema_version": "read-context-low-dose-b-relative-screen-ticket/1.0",
        "approved": True,
        "scope": "READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_SINGLE_RUN",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": AUTHORIZED_COMMANDS,
        "spec_sha256": sha256(SPEC),
        "runner_sha256": sha256(Path(__file__)),
        "scorer_sha256": sha256(SCORER),
        "model_receipt_sha256": MODEL_RECEIPT_SHA,
        "trainer_sha256": TRAINER_SHA,
        "train_read1_sha256": TRAIN_SHA["READ1"],
        "train_read2_sha256": TRAIN_SHA["READ2"],
        "train_read4_sha256": TRAIN_SHA["READ4"],
        "eval_read1_sha256": EVAL_SHA["READ1"],
        "eval_read2_sha256": EVAL_SHA["READ2"],
        "eval_read4_sha256": EVAL_SHA["READ4"],
        "gold_sha256": EXPECTED["gold_sha256"],
        "txx_sha256": EXPECTED["txx_sha256"],
        "schema_sha256": EXPECTED["schema_sha256"],
        "read1_adapter_sha256": EXPECTED["read1_adapter_sha256"],
        "read1_adapter_config_sha256": EXPECTED["read1_config_sha256"],
        "ab8_requests_sha256": EXPECTED["ab8_requests_sha256"],
        "ab8_raw_sha256": EXPECTED["ab8_raw_sha256"],
        "ab8_adjudications_sha256": EXPECTED["ab8_adjudications_sha256"],
        "ab8_final_metrics_sha256": EXPECTED["ab8_final_sha256"],
        "ab8_result_ticket_sha256": EXPECTED["ab8_result_ticket_sha256"],
    }
    for key, expected in fixed.items():
        if ticket.get(key) != expected:
            raise RuntimeError(f"TICKET_FIELD_DRIFT:{key}")
    if not all(
        isinstance(ticket.get(key), str) and ticket[key]
        for key in (
            "authorized_by",
            "decision_id",
            "decision_text_sha256",
            "source_thread_id",
            "issued_at",
        )
    ):
        raise RuntimeError("TICKET_AUTHORITY_IDENTITY_INCOMPLETE")
    if command not in ticket["authorized_commands"]:
        raise RuntimeError(f"COMMAND_NOT_AUTHORIZED:{command}")
    verify_static_inputs()
    if command == "train-new-arms" and RUN_ROOT.exists():
        raise RuntimeError(f"RUN_ROOT_EXISTS_NO_RETRY:{RUN_ROOT}")
    if command != "train-new-arms" and not RUN_ROOT.is_dir():
        raise RuntimeError(f"RUN_ROOT_MISSING:{RUN_ROOT}")
    return ticket


def train_config(arm: str) -> dict[str, Any]:
    return {
        "model": str(MODEL),
        "train": True,
        "data": str(RUN_ROOT / "data" / arm.lower()),
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
        "adapter_path": str(RUN_ROOT / "adapters" / arm.lower()),
        "save_every": 24,
        "max_seq_length": 4608,
        "grad_checkpoint": True,
        "seed": 20260802,
        "lora_parameters": {"rank": 32, "dropout": 0.0, "scale": 0.125},
    }


def train_one(arm: str) -> dict[str, Any]:
    import yaml

    if active_lora_processes():
        raise RuntimeError(f"OTHER_LORA_PROCESS_ACTIVE:{active_lora_processes()}")
    free = system_free_percent()
    if free >= 0 and free < 8:
        raise RuntimeError(f"MEMORY_HARD_STOP_BEFORE_TRAIN:{arm}:{free}")
    model_gate = verify_model_receipt_members()
    data_dir = RUN_ROOT / "data" / arm.lower()
    adapter_dir = RUN_ROOT / "adapters" / arm.lower()
    config_path = RUN_ROOT / "config" / f"{arm.lower()}.yaml"
    log_path = RUN_ROOT / "logs" / f"{arm.lower()}.log"
    data_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(TRAIN_PATHS[arm], data_dir / "train.jsonl")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(train_config(arm), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(VENDOR)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [str(PYTHON), "-m", "mlx_lm.lora", "--config", str(config_path)]
    began = time.monotonic()
    with log_path.open("x", encoding="utf-8") as log:
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
                print(
                    f"RELATIVE_TRAIN_PROGRESS arm={arm} iter={match.group(1)}/24 "
                    f"memory_free={system_free_percent()}%",
                    flush=True,
                )
        return_code = child.wait()
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    final = adapter_dir / "adapters.safetensors"
    numbered = adapter_dir / "0000024_adapters.safetensors"
    config = adapter_dir / "adapter_config.json"
    if return_code != 0 or "Saved final weights" not in log_text:
        raise RuntimeError(f"TRAIN_FAILED_NO_RETRY:{arm}:{return_code}")
    if not final.is_file() or not config.is_file():
        raise RuntimeError(f"FINAL_ADAPTER_MISSING:{arm}")
    if numbered.is_file():
        if sha256(numbered) != sha256(final):
            raise RuntimeError(f"STEP24_FINAL_ADAPTER_MISMATCH:{arm}")
        numbered.unlink()
    return {
        "arm": arm,
        "status": "PASS_TRAINING_24_MICROSTEPS_6_UPDATES",
        "completed_at": now(),
        "elapsed_seconds": round(time.monotonic() - began, 3),
        "source_train_sha256": sha256(data_dir / "train.jsonl"),
        "adapter_sha256": sha256(final),
        "adapter_config_sha256": sha256(config),
        "model_member_gate_before_child_process": model_gate,
        "return_code": return_code,
        "retry": 0,
        "remaining_numbered_checkpoints": 0,
    }


def train_new_arms(ticket_path: Path) -> None:
    ticket = validate_ticket(ticket_path, "train-new-arms")
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    model_gate = verify_model_receipt_members()
    RUN_ROOT.mkdir(parents=False)
    write_json(
        RUN_ROOT / "RUN_IDENTITY.json",
        {
            "status": "AUTHORIZED_TRAINING_STARTED",
            "run_id": RUN_ID,
            "created_at": now(),
            "ticket_sha256": sha256(ticket_path),
            "spec_sha256": sha256(SPEC),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "authorized_commands": ticket["authorized_commands"],
            "model_member_gate": model_gate,
            "api_calls": 0,
        },
    )
    receipts = []
    for arm in NEW_ARMS:
        receipt = train_one(arm)
        receipts.append(receipt)
        write_json(RUN_ROOT / "receipts" / f"TRAIN_{arm}.json", receipt)
    write_json(
        RUN_ROOT / "TRAINING_RESULT.json",
        {
            "status": "PASS_TWO_NEW_ARMS_TRAINED",
            "completed_at": now(),
            "arm_order": list(NEW_ARMS),
            "receipts": receipts,
            "read1_retrained": False,
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "PASS_TRAIN_NEW_ARMS", "arms": receipts}, ensure_ascii=False))


def derived_requests(arm: str, cases: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    rows = read_jsonl(EVAL_PATHS[arm])
    if len(rows) != 24:
        raise RuntimeError(f"EVAL_ROW_COUNT_DRIFT:{arm}")
    by_case = dict(zip((f"C{index:02d}" for index in range(1, 25)), rows, strict=True))
    selected = cases or tuple(by_case)
    result = []
    for case_id in selected:
        source = by_case[case_id]
        if [message.get("role") for message in source.get("messages", [])] != ["system", "user"]:
            raise RuntimeError(f"EVAL_MESSAGE_SHAPE_DRIFT:{arm}:{case_id}")
        messages = [dict(message) for message in source["messages"]]
        messages[0]["content"] += "\n" + CONTRACT
        if messages[1] != source["messages"][1]:
            raise RuntimeError(f"EVAL_USER_CHANGED:{arm}:{case_id}")
        result.append({"case_id": case_id, "messages": messages})
    return result


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


def verified_model_load(
    load: Any, *, adapter: Path | None = None
) -> tuple[Any, Any, dict[str, Any]]:
    """Recheck all model members immediately before one actual model load."""
    gate = verify_model_receipt_members()
    if adapter is None:
        model, tokenizer = load(str(MODEL))
    else:
        model, tokenizer = load(str(MODEL), adapter_path=str(adapter))
    return model, tokenizer, gate


def generate(
    model: Any,
    tokenizer: Any,
    stream_generate: Any,
    sampler: Any,
    variant: str,
    arm: str,
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for index, request in enumerate(requests, 1):
        free = system_free_percent()
        if free >= 0 and free < 8:
            raise RuntimeError(
                f"MEMORY_HARD_STOP_BEFORE_CASE:{variant}:{request['case_id']}:{free}"
            )
        prompt = tokenizer.apply_chat_template(
            request["messages"], tokenize=False, add_generation_prompt=True
        )
        pieces: list[str] = []
        final = None
        began = time.monotonic()
        for response in stream_generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=2048,
            sampler=sampler,
        ):
            pieces.append(response.text)
            final = response
        if final is None:
            raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{variant}:{request['case_id']}")
        raw = "".join(pieces)
        rows.append(
            {
                "variant": variant,
                "arm": arm,
                "case_id": request["case_id"],
                "raw_output": raw,
                "finish_reason": final.finish_reason,
                "stop_token": int(final.token),
                "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids,
                "generation_tokens_including_stop": int(final.generation_tokens),
                "output_tokens_excluding_stop": len(
                    tokenizer.encode(raw, add_special_tokens=False)
                ),
                "input_tokens": int(final.prompt_tokens),
                "elapsed_seconds": round(time.monotonic() - began, 3),
            }
        )
        print(
            f"RELATIVE_INFER_PROGRESS variant={variant} case={index}/{len(requests)}",
            flush=True,
        )
    return rows


def adapter_path(arm: str) -> Path:
    return READ1_VIEW if arm == "READ1" else RUN_ROOT / "adapters" / arm.lower()


def verify_training_receipts() -> None:
    result = strict_json(RUN_ROOT / "TRAINING_RESULT.json")
    if result.get("status") != "PASS_TWO_NEW_ARMS_TRAINED":
        raise RuntimeError("TRAINING_RESULT_NOT_PASS")
    for arm in NEW_ARMS:
        receipt = strict_json(RUN_ROOT / "receipts" / f"TRAIN_{arm}.json")
        current = adapter_path(arm) / "adapters.safetensors"
        if sha256(current) != receipt.get("adapter_sha256"):
            raise RuntimeError(f"TRAINED_ADAPTER_SHA_DRIFT:{arm}")


def infer_stage1(ticket_path: Path) -> None:
    validate_ticket(ticket_path, "infer-stage1")
    verify_training_receipts()
    output = RUN_ROOT / "inference/STAGE1_LORA_RAW_24.jsonl"
    if output.exists():
        raise RuntimeError("STAGE1_OUTPUT_EXISTS_NO_RETRY")
    request_root = RUN_ROOT / "requests/stage1"
    request_root.mkdir(parents=True, exist_ok=False)
    requests = {arm: derived_requests(arm, CASES8) for arm in ARMS}
    for arm in ARMS:
        write_jsonl(request_root / f"{arm}.jsonl", requests[arm])
    if (request_root / "READ1.jsonl").read_bytes() != AB8_REQUESTS.read_bytes():
        raise RuntimeError("READ1_STAGE1_REQUEST_NOT_EXACT_OLD_B")
    read1_rows = []
    for row in read_jsonl(AB8_RAW):
        copied = dict(row)
        copied["variant"] = "LORA_READ1"
        copied["arm"] = "READ1"
        copied["reused_from_raw_sha256"] = EXPECTED["ab8_raw_sha256"]
        read1_rows.append(copied)
    mx, load, stream_generate, make_sampler = configure_mlx()
    sampler = make_sampler(temp=0.0)
    generated = list(read1_rows)
    model_load_gates = []
    for arm in NEW_ARMS:
        model, tokenizer, gate = verified_model_load(
            load, adapter=adapter_path(arm)
        )
        model_load_gates.append(
            {"variant": f"LORA_{arm}", "arm": arm, "gate": gate}
        )
        generated.extend(
            generate(
                model,
                tokenizer,
                stream_generate,
                sampler,
                f"LORA_{arm}",
                arm,
                requests[arm],
            )
        )
        del model
        mx.clear_cache()
    write_jsonl(output, generated)
    write_json(
        RUN_ROOT / "inference/STAGE1_RESULT.json",
        {
            "status": "PASS_STAGE1_INFERENCE_24_ROWS",
            "rows": len(generated),
            "raw_sha256": sha256(output),
            "read1_reused_original_raw_sha256": EXPECTED["ab8_raw_sha256"],
            "model_member_gates_before_each_load": model_load_gates,
            "api_calls": 0,
            "retry": 0,
        },
    )
    print(json.dumps({"status": "PASS_INFER_STAGE1", "raw_sha256": sha256(output)}))


def infer_full24(ticket_path: Path) -> None:
    validate_ticket(ticket_path, "infer-full24")
    verify_training_receipts()
    gate_path = RUN_ROOT / "scoring/STAGE1_MECHANICAL_GATE.json"
    gate = strict_json(gate_path)
    stage1_raw = RUN_ROOT / "inference/STAGE1_LORA_RAW_24.jsonl"
    if gate.get("stage1_raw_sha256") != sha256(stage1_raw):
        raise RuntimeError("STAGE1_GATE_RAW_SHA_DRIFT")
    passing = gate.get("passing_arms")
    if not isinstance(passing, list) or len(passing) < 2:
        raise RuntimeError("FULL24_FORBIDDEN_FEWER_THAN_TWO_PASSING_ARMS")
    if any(arm not in ARMS for arm in passing):
        raise RuntimeError("STAGE1_GATE_UNKNOWN_ARM")
    output = RUN_ROOT / "inference/FULL24_MATCHED_RAW.jsonl"
    if output.exists():
        raise RuntimeError("FULL24_OUTPUT_EXISTS_NO_RETRY")
    request_root = RUN_ROOT / "requests/full24"
    request_root.mkdir(parents=True, exist_ok=False)
    requests = {arm: derived_requests(arm) for arm in passing}
    for arm in passing:
        write_jsonl(request_root / f"{arm}.jsonl", requests[arm])
    mx, load, stream_generate, make_sampler = configure_mlx()
    sampler = make_sampler(temp=0.0)
    generated: list[dict[str, Any]] = []
    model_load_gates = []
    base_model, base_tokenizer, base_gate = verified_model_load(load)
    model_load_gates.append(
        {
            "variants": [f"BASE_{arm}" for arm in passing],
            "arm": "SHARED_BASE",
            "gate": base_gate,
        }
    )
    for arm in passing:
        generated.extend(
            generate(
                base_model,
                base_tokenizer,
                stream_generate,
                sampler,
                f"BASE_{arm}",
                arm,
                requests[arm],
            )
        )
    del base_model
    mx.clear_cache()
    stage1_index = {
        (row["variant"], row["case_id"]): row for row in read_jsonl(stage1_raw)
    }
    for arm in passing:
        model, tokenizer, lora_gate = verified_model_load(
            load, adapter=adapter_path(arm)
        )
        model_load_gates.append(
            {"variant": f"LORA_{arm}", "arm": arm, "gate": lora_gate}
        )
        old_rows = [stage1_index[(f"LORA_{arm}", case_id)] for case_id in CASES8]
        missing_requests = [row for row in requests[arm] if row["case_id"] not in CASES8]
        new_rows = generate(
            model,
            tokenizer,
            stream_generate,
            sampler,
            f"LORA_{arm}",
            arm,
            missing_requests,
        )
        by_case = {row["case_id"]: row for row in old_rows + new_rows}
        generated.extend(by_case[f"C{index:02d}"] for index in range(1, 25))
        del model
        mx.clear_cache()
    write_jsonl(output, generated)
    expected_rows = len(passing) * 48
    if len(generated) != expected_rows:
        raise RuntimeError(f"FULL24_ROW_COUNT_DRIFT:{len(generated)}:{expected_rows}")
    write_json(
        RUN_ROOT / "inference/FULL24_RESULT.json",
        {
            "status": "PASS_FULL24_MATCHED_INFERENCE",
            "passing_arms": passing,
            "rows": len(generated),
            "raw_sha256": sha256(output),
            "model_member_gates_before_each_load": model_load_gates,
            "api_calls": 0,
            "retry": 0,
        },
    )
    print(json.dumps({"status": "PASS_INFER_FULL24", "raw_sha256": sha256(output)}))


def static_check() -> None:
    identity = verify_static_inputs()
    result = {
        "status": "PASS_STATIC_PREP_ONLY",
        "run_root_exists": RUN_ROOT.exists(),
        "inputs": identity,
        "ticket_present": False,
        "model_loaded": False,
        "training_started": False,
        "inference_started": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "static-check",
            "validate",
            "train-new-arms",
            "infer-stage1",
            "infer-full24",
        ),
    )
    parser.add_argument("--ticket", type=Path)
    parser.add_argument("--action", choices=AUTHORIZED_COMMANDS)
    args = parser.parse_args()
    if args.command == "static-check":
        static_check()
        return
    if args.ticket is None:
        raise RuntimeError("EXECUTION_TICKET_REQUIRED_BEFORE_RUN_ROOT_OR_MODEL_LOAD")
    if args.command == "validate":
        if args.action is None:
            raise RuntimeError("VALIDATE_REQUIRES_ACTION")
        validate_ticket(args.ticket, args.action)
        print(json.dumps({"status": "PASS_TICKET_VALIDATION", "action": args.action}))
    elif args.command == "train-new-arms":
        train_new_arms(args.ticket)
    elif args.command == "infer-stage1":
        infer_stage1(args.ticket)
    else:
        infer_full24(args.ticket)


if __name__ == "__main__":
    main()
