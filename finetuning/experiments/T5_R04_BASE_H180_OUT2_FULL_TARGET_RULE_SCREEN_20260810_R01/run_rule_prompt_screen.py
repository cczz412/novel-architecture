#!/usr/bin/env python3
"""Ticket-bound local Base inference for the RULE +1/+2 prompt screen."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC = EXP / "SPEC.json"
SCORER = EXP / "score_rule_prompt_screen.py"
PREP_RECEIPT = EXP / "PREPARE_RECEIPT.json"
RUN_ID = "T5_R04_BASE_H180_OUT2_FULL_TARGET_RULE_SCREEN_R01"
RUN_ROOT = REPO / f"runs/{RUN_ID}"
MODEL = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/models/"
    "Qwen3-4B-Instruct-2507_cdbee75f"
)
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
MODEL_RECEIPT_SHA = "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
MODEL_FILE_COUNT = 13
MODEL_TOTAL_BYTES = 8_060_917_568
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
PARENT_RUN = REPO / "runs/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
BASE_REQUEST = PARENT_RUN / "requests/full24/READ2.jsonl"
PARENT_RAW = PARENT_RUN / "inference/FULL24_MATCHED_RAW.jsonl"
BASE_CONTEXT_RUN = REPO / "runs/T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_R01"
BASE_CONTEXT_FINAL = BASE_CONTEXT_RUN / "scoring/final/METRICS.json"
BASE_CONTEXT_DECISIONS = (
    BASE_CONTEXT_RUN / "scoring/adjudications/SEMANTIC_ADJUDICATIONS_223.jsonl"
)
BASE_CONTEXT_ADJ_RECEIPT = (
    BASE_CONTEXT_RUN / "scoring/adjudications/ADJUDICATION_RECEIPT.json"
)
READ2_CARRYOVER = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_READ2_LOW_DOSE_B_SEMANTIC_CARRYOVER_20260810_R01"
)
READ2_R02 = READ2_CARRYOVER / "SEMANTIC_ADJUDICATIONS_381_R02.jsonl"
READ2_R02_RECEIPT = READ2_CARRYOVER / "ADJUDICATION_R02_RECEIPT.json"
READ2_FINAL = READ2_CARRYOVER / "FINAL_CARRYOVER_METRICS_R02.json"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
TXX = EVAL_ROOT / "REAL24_TXX_MAP.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
BASE_CONTEXT_EXP = (
    REPO / "finetuning/experiments/T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_20260810_R01"
)
POLICY = BASE_CONTEXT_EXP / "SEMANTIC_ADJUDICATION_POLICY.md"
SCHEMA = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/"
    "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
WO_SCORER = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/tools/score_demo.py"
)
R09 = REPO / "finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R09"

RULE_ONE_SUFFIX = (
    "\n【附加原子规则】\n"
    "1. 一条 fact 只写一个核心断言；不同主体、动作或状态分别写，不要合并。"
)
RULE_TWO_SUFFIX = (
    "\n2. 计划、承诺、推测、误信和否认必须保留对应状态，"
    "不得改写成“已发生”或客观确定事实。"
)
VARIANTS = (
    "RULE-1-PLUS-ONE",
    "RULE-2-PLUS-TWO",
)
REQUEST_SHA = {
    "RULE-1-PLUS-ONE": "9ea695da2c65a1862d7eaab20ab1569d25e96d6b690271111845a4d608e41cd8",
    "RULE-2-PLUS-TWO": "ef2e859b1200cad0308ddf3342598521b1dc2d6d5117e07cfe79073c8db4403a",
}
EXPECTED = {
    "r09_readme_sha256": "733848fb54e231e4ef7ce58ed3bcf72706098a201ce53c7516b4fccb889ab4b8",
    "r09_registry_sha256": "24cc1d970e728323a14549db9455f4d23e765706b4041f7b2bf9af45d60a683f",
    "r09_result_ticket_sha256": "c2b5fde501d4e14c36eaa70868823775520d41d60111c084dd6569565803bab4",
    "base_request_sha256": "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    "parent_raw_sha256": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "base_projection_sha256": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "base_context_final_sha256": "f625c10ecf0e1d4be8eade2032dc2fdbe6d398ac55a6ad89f47abffa117825c7",
    "base_context_decisions_sha256": "ddc75e55cb441c6dd90f354f2a7ee7ffb28dd32f08e82a91df2052d1ae5ccf4d",
    "base_context_adjudication_receipt_sha256": (
        "9170e59a8219efc5fff4e13291842f8a114fcdee00c95e9ffe85c063c345b6f3"
    ),
    "read2_r02_sha256": "03eb97a774ac41599d6f897e64486cec37d0a237b073f0ab621039733d599636",
    "read2_r02_receipt_sha256": "89922af0093da4f34da59e5f661703502fc7b4b3507f46a387831e155ee354b3",
    "read2_final_sha256": "524f8bcceb37aea95a6cf1ac7445580353360fdfd6de525982a216efa49ec96f",
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "semantic_policy_sha256": "73083a1d91edcc8fadabd2342fc59b89e10ef770aeaa6ffe926867f4f4c39a93",
    "wo_scorer_sha256": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
    "rule1_request_sha256": REQUEST_SHA["RULE-1-PLUS-ONE"],
    "rule2_request_sha256": REQUEST_SHA["RULE-2-PLUS-TWO"],
}
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
    "prepare_receipt_sha256",
    "model_receipt_sha256",
    *EXPECTED.keys(),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


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
    path.write_bytes(jsonl_bytes(rows))


def exact_base_projection() -> tuple[list[dict[str, Any]], str, bytes]:
    selected: list[bytes] = []
    rows: list[dict[str, Any]] = []
    for line in PARENT_RAW.read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        if row.get("variant") == "BASE_READ2":
            selected.append(line)
            rows.append(row)
    payload = b"".join(selected)
    return rows, hashlib.sha256(payload).hexdigest(), payload


def build_requests(variant: str) -> list[dict[str, Any]]:
    if variant not in VARIANTS:
        raise RuntimeError(f"UNKNOWN_RULE_VARIANT:{variant}")
    base = read_jsonl(BASE_REQUEST)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if [row.get("case_id") for row in base] != cases:
        raise RuntimeError("BASE_REQUEST_CASE_ORDER_DRIFT")
    suffix = RULE_ONE_SUFFIX
    if variant == "RULE-2-PLUS-TWO":
        suffix += RULE_TWO_SUFFIX
    result = []
    for row in base:
        messages = row.get("messages")
        if not isinstance(messages, list) or [message.get("role") for message in messages] != [
            "system",
            "user",
        ]:
            raise RuntimeError(f"BASE_REQUEST_MESSAGE_SHAPE_DRIFT:{row.get('case_id')}")
        result.append(
            {
                "case_id": row["case_id"],
                "messages": [
                    {"role": "system", "content": messages[0]["content"] + suffix},
                    {"role": "user", "content": messages[1]["content"]},
                ],
            }
        )
    return result


def verify_request_derivation() -> dict[str, Any]:
    base = read_jsonl(BASE_REQUEST)
    rule1 = build_requests("RULE-1-PLUS-ONE")
    rule2 = build_requests("RULE-2-PLUS-TWO")
    hashes = {
        "rule1_request_sha256": hashlib.sha256(jsonl_bytes(rule1)).hexdigest(),
        "rule2_request_sha256": hashlib.sha256(jsonl_bytes(rule2)).hexdigest(),
    }
    if hashes != {
        "rule1_request_sha256": REQUEST_SHA["RULE-1-PLUS-ONE"],
        "rule2_request_sha256": REQUEST_SHA["RULE-2-PLUS-TWO"],
    }:
        raise RuntimeError(f"RULE_REQUEST_SHA_DRIFT:{hashes}")
    for baseline, plus_one, plus_two in zip(base, rule1, rule2, strict=True):
        if not (
            baseline["case_id"] == plus_one["case_id"] == plus_two["case_id"]
            and baseline["messages"][1] == plus_one["messages"][1] == plus_two["messages"][1]
        ):
            raise RuntimeError(f"RULE_USER_OR_CASE_DRIFT:{baseline.get('case_id')}")
        base_system = baseline["messages"][0]["content"]
        one_system = plus_one["messages"][0]["content"]
        two_system = plus_two["messages"][0]["content"]
        if one_system != base_system + RULE_ONE_SUFFIX:
            raise RuntimeError(f"RULE1_SYSTEM_NOT_EXACT_SUFFIX:{baseline['case_id']}")
        if two_system != one_system + RULE_TWO_SUFFIX:
            raise RuntimeError(f"RULE2_SYSTEM_NOT_STRICT_EXTENSION:{baseline['case_id']}")
    return {
        "rows_per_new_variant": 24,
        "total_new_requests": 48,
        "case_order": "C01_TO_C24",
        "user_bytes_identical_across_three_variants": True,
        "rule2_system_strictly_extends_rule1_system": True,
        **hashes,
    }


def verify_static_inputs() -> dict[str, Any]:
    projection, projection_sha, _ = exact_base_projection()
    if len(projection) != 24 or [row.get("case_id") for row in projection] != [
        f"C{index:02d}" for index in range(1, 25)
    ]:
        raise RuntimeError("BASE_PROJECTION_CASE_ORDER_DRIFT")
    request_proof = verify_request_derivation()
    actual = {
        "r09_readme_sha256": sha256(R09 / "00_READ_ME_FIRST.md"),
        "r09_registry_sha256": sha256(R09 / "DECISION_REGISTRY.json"),
        "r09_result_ticket_sha256": sha256(R09 / "TARGET_BLOCK_RESULT_TICKET.json"),
        "base_request_sha256": sha256(BASE_REQUEST),
        "parent_raw_sha256": sha256(PARENT_RAW),
        "base_projection_sha256": projection_sha,
        "base_context_final_sha256": sha256(BASE_CONTEXT_FINAL),
        "base_context_decisions_sha256": sha256(BASE_CONTEXT_DECISIONS),
        "base_context_adjudication_receipt_sha256": sha256(BASE_CONTEXT_ADJ_RECEIPT),
        "read2_r02_sha256": sha256(READ2_R02),
        "read2_r02_receipt_sha256": sha256(READ2_R02_RECEIPT),
        "read2_final_sha256": sha256(READ2_FINAL),
        "gold_sha256": sha256(GOLD),
        "txx_sha256": sha256(TXX),
        "schema_sha256": sha256(SCHEMA),
        "semantic_policy_sha256": sha256(POLICY),
        "wo_scorer_sha256": sha256(WO_SCORER),
        "rule1_request_sha256": request_proof["rule1_request_sha256"],
        "rule2_request_sha256": request_proof["rule2_request_sha256"],
    }
    if actual != EXPECTED:
        raise RuntimeError(f"STATIC_INPUT_SHA_DRIFT:{actual}")
    if sha256(MODEL_RECEIPT) != MODEL_RECEIPT_SHA:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    return {**actual, "request_derivation": request_proof}


def verify_model_receipt_members() -> dict[str, Any]:
    if sha256(MODEL_RECEIPT) != MODEL_RECEIPT_SHA:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    receipt = read_json(MODEL_RECEIPT)
    if receipt.get("revision") != MODEL_REVISION:
        raise RuntimeError("MODEL_REVISION_DRIFT")
    files = receipt.get("files")
    if not isinstance(files, list) or len(files) != MODEL_FILE_COUNT:
        raise RuntimeError("MODEL_MEMBER_COUNT_DRIFT")
    total = 0
    for row in files:
        member = MODEL / row["path"]
        if not member.is_file() or member.stat().st_size != row["bytes"]:
            raise RuntimeError(f"MODEL_MEMBER_SIZE_DRIFT:{row['path']}")
        if sha256(member) != row["sha256"]:
            raise RuntimeError(f"MODEL_MEMBER_SHA_DRIFT:{row['path']}")
        total += row["bytes"]
    if total != MODEL_TOTAL_BYTES:
        raise RuntimeError("MODEL_TOTAL_BYTES_DRIFT")
    return {"member_count": len(files), "total_bytes": total, "revision": MODEL_REVISION}


def validate_ticket(
    path: Path, *, require_run_root_absent: bool = True
) -> dict[str, Any]:
    ticket = read_json(path)
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("TICKET_KEYS_DRIFT")
    fixed = {
        "schema_version": "base-h180-out2-full-target-rule-screen-ticket/1.0",
        "approved": True,
        "scope": "BASE_H180_OUT2_FULL_TARGET_RULE_SCREEN_SINGLE_48_INFERENCE",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-new-rules"],
        "spec_sha256": sha256(SPEC),
        "runner_sha256": sha256(Path(__file__)),
        "scorer_sha256": sha256(SCORER),
        "prepare_receipt_sha256": sha256(PREP_RECEIPT),
        "model_receipt_sha256": MODEL_RECEIPT_SHA,
        **EXPECTED,
    }
    for key, expected in fixed.items():
        if ticket.get(key) != expected:
            raise RuntimeError(f"TICKET_FIELD_DRIFT:{key}")
    for key in (
        "authorized_by",
        "decision_id",
        "decision_text_sha256",
        "source_thread_id",
        "issued_at",
    ):
        if not isinstance(ticket.get(key), str) or not ticket[key]:
            raise RuntimeError(f"TICKET_AUTHORITY_MISSING:{key}")
    verify_static_inputs()
    if require_run_root_absent and RUN_ROOT.exists():
        raise RuntimeError(f"RUN_ROOT_EXISTS_NO_RETRY:{RUN_ROOT}")
    return ticket


def system_free_percent() -> int:
    import subprocess

    result = subprocess.run(["memory_pressure", "-Q"], text=True, capture_output=True)
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else -1


def generate(
    model: Any,
    tokenizer: Any,
    stream_generate: Any,
    sampler: Any,
    requests: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for variant in VARIANTS:
        for index, request in enumerate(requests[variant], 1):
            free = system_free_percent()
            if free >= 0 and free < 8:
                raise RuntimeError(f"MEMORY_HARD_STOP:{variant}:{request['case_id']}:{free}")
            prompt = tokenizer.apply_chat_template(
                request["messages"], tokenize=False, add_generation_prompt=True
            )
            pieces: list[str] = []
            final = None
            began = time.monotonic()
            for response in stream_generate(
                model, tokenizer, prompt=prompt, max_tokens=2048, sampler=sampler
            ):
                pieces.append(response.text)
                final = response
            if final is None:
                raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{variant}:{request['case_id']}")
            raw = "".join(pieces)
            rows.append(
                {
                    "variant": variant,
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
            print(f"{variant}_PROGRESS case={index}/24", flush=True)
    return rows


def infer(ticket_path: Path, validate_only: bool) -> None:
    ticket = validate_ticket(ticket_path)
    if validate_only:
        print(json.dumps({"status": "PASS_TICKET_VALIDATION", "run_root_exists": False}))
        return
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = {variant: build_requests(variant) for variant in VARIANTS}
    RUN_ROOT.mkdir(parents=False)
    ticket_sha = sha256(ticket_path)
    ticket_copy = RUN_ROOT / "AUTHORIZATION_TICKET.json"
    ticket_copy.write_bytes(ticket_path.read_bytes())
    if sha256(ticket_copy) != ticket_sha:
        raise RuntimeError("AUTHORIZATION_TICKET_COPY_SHA_DRIFT")
    write_json(
        RUN_ROOT / "RUN_IDENTITY.json",
        {
            "status": "AUTHORIZED_INFERENCE_STARTED",
            "run_id": RUN_ID,
            "created_at": now(),
            "ticket_sha256": ticket_sha,
            "ticket_copy_sha256": sha256(ticket_copy),
            "spec_sha256": sha256(SPEC),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "prepare_receipt_sha256": sha256(PREP_RECEIPT),
            "authorized_commands": ticket["authorized_commands"],
            "model_receipt_sha256": MODEL_RECEIPT_SHA,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    request_paths = {
        "RULE-1-PLUS-ONE": RUN_ROOT / "requests/RULE_1_PLUS_ONE_REQUESTS_24.jsonl",
        "RULE-2-PLUS-TWO": RUN_ROOT / "requests/RULE_2_PLUS_TWO_REQUESTS_24.jsonl",
    }
    for variant, path in request_paths.items():
        write_jsonl(path, requests[variant])
        if sha256(path) != REQUEST_SHA[variant]:
            raise RuntimeError(f"WRITTEN_RULE_REQUEST_SHA_DRIFT:{variant}")
    sys.path.insert(0, str(VENDOR))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler

    mx.set_wired_limit(20 * 1024**3)
    mx.set_memory_limit(22 * 1024**3)
    mx.set_cache_limit(1 * 1024**3)
    mx.clear_cache()
    model_gate = verify_model_receipt_members()
    model, tokenizer = load(str(MODEL))
    rows = generate(model, tokenizer, stream_generate, make_sampler(temp=0.0), requests)
    raw_path = RUN_ROOT / "inference/NEW_RULES_RAW_48.jsonl"
    write_jsonl(raw_path, rows)
    write_json(
        RUN_ROOT / "inference/NEW_RULES_RESULT.json",
        {
            "status": "PASS_NEW_RULES_48_INFERENCE",
            "run_id": RUN_ID,
            "rows": len(rows),
            "rows_by_variant": {variant: 24 for variant in VARIANTS},
            "raw_sha256": sha256(raw_path),
            "request_sha256_by_variant": {
                variant: sha256(path) for variant, path in request_paths.items()
            },
            "ticket_sha256": ticket_sha,
            "ticket_copy_sha256": sha256(ticket_copy),
            "spec_sha256": sha256(SPEC),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "prepare_receipt_sha256": sha256(PREP_RECEIPT),
            "model_receipt_sha256": MODEL_RECEIPT_SHA,
            "model_member_gates_before_each_load": [
                {
                    "load_index": 1,
                    "load_scope": "SHARED_UNFINETUNED_BASE_FOR_RULE1_RULE2",
                    "gate": model_gate,
                }
            ],
            "model_load_count": 1,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "PASS_NEW_RULES_INFERENCE", "raw_sha256": sha256(raw_path)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "infer-new-rules"))
    parser.add_argument("--ticket", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.command == "static-check":
        if args.ticket is not None or args.validate_only:
            raise RuntimeError("STATIC_CHECK_TAKES_NO_TICKET")
        print(
            json.dumps(
                {
                    "status": "PASS_STATIC_INPUTS",
                    **verify_static_inputs(),
                    "model_member_gate": verify_model_receipt_members(),
                }
            )
        )
        return
    if args.ticket is None:
        raise RuntimeError("EXECUTION_TICKET_REQUIRED_BEFORE_RUN_ROOT_OR_MODEL_LOAD")
    infer(args.ticket, args.validate_only)


if __name__ == "__main__":
    main()
