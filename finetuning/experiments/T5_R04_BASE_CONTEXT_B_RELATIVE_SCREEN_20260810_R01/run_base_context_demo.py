#!/usr/bin/env python3
"""Ticket-bound BASE_READ4 inference for the Base context Demo."""

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
SCORER = EXP / "score_base_context_demo.py"
RUN_ID = "T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_R01"
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
PARENT_EXP = REPO / "finetuning/experiments/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
PARENT_SPEC = PARENT_EXP / "SPEC.json"
PARENT_RUN = REPO / "runs/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
PARENT_RAW = PARENT_RUN / "inference/FULL24_MATCHED_RAW.jsonl"
PARENT_RESULT = PARENT_RUN / "inference/FULL24_RESULT.json"
PARENT_METRICS = PARENT_RUN / "scoring/full_pre/METRICS.json"
PARENT_REQUESTS = {
    "READ1": PARENT_RUN / "requests/full24/READ1.jsonl",
    "READ2": PARENT_RUN / "requests/full24/READ2.jsonl",
}
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
EVAL_READ4 = EVAL_ROOT / "READ_4_FULL_CHAPTER_EVAL24.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
TXX = EVAL_ROOT / "REAL24_TXX_MAP.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/"
    "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
POLICY = EXP / "SEMANTIC_ADJUDICATION_POLICY.md"
WO_SCORER = (
    REPO
    / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/"
    "tools/score_demo.py"
)
READ2_CARRYOVER = (
    REPO
    / "finetuning/experiments/T5_R04_READ2_LOW_DOSE_B_SEMANTIC_CARRYOVER_20260810_R01"
)
READ2_R02 = READ2_CARRYOVER / "SEMANTIC_ADJUDICATIONS_381_R02.jsonl"
READ2_FINAL = READ2_CARRYOVER / "FINAL_CARRYOVER_METRICS_R02.json"
CONTRACT = (
    "【输出合同】输出必须是且只能是一个顶层键为 facts 的 JSON 对象；facts 为数组且允许为空，"
    "每个元素只能且必须包含 fact、status、speaker、evidence_ids，fact 为非空字符串，"
    "speaker 为字符串或 null，evidence_ids 为字符串数组，status 只能取“已发生”“正在发生”"
    "“计划”“承诺”“条件”“推测”“误信”“否定”之一；不得输出其他字段、Markdown 或解释。"
)
EXPECTED = {
    "parent_spec_sha256": "ff4ae3e702a318d3d47a0476d1cbbc18078884735e14176d1f9171b07232cd06",
    "parent_raw_sha256": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "parent_result_sha256": "a8b3276179551aaa3b7e42c274c0a7c5327846171be58c02ff0d38de778340b9",
    "parent_metrics_sha256": "583d89053ed5662b516206579782338994afeca3580a25e39cc98c1781692d57",
    "read1_actual_request_sha256": "72622224236853a70b0ea1ddfcc85ead2e4319a9ec97ee54226be2113f28b022",
    "read2_actual_request_sha256": "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    "base_read1_projection_sha256": "21de7f972b892796fedc5fb8f6a4ad9c79223b7804a492a4f6dc9fa3ecdb564f",
    "base_read2_projection_sha256": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "eval_read4_sha256": "350799084dbc15791bc3b46a669552aec2da7920bfa39c8a3a110e1cbe431d4f",
    "read4_b_requests_sha256": "b917c8253c78671435e735c18afa0365717507736da4be28e5c2b81eb55387c2",
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "semantic_policy_sha256": "73083a1d91edcc8fadabd2342fc59b89e10ef770aeaa6ffe926867f4f4c39a93",
    "wo_scorer_sha256": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
    "read2_r02_sha256": "03eb97a774ac41599d6f897e64486cec37d0a237b073f0ab621039733d599636",
    "read2_final_sha256": "524f8bcceb37aea95a6cf1ac7445580353360fdfd6de525982a216efa49ec96f",
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_bytes(jsonl_bytes(rows))


def exact_line_projection(variant: str) -> tuple[list[dict[str, Any]], str]:
    selected: list[bytes] = []
    rows: list[dict[str, Any]] = []
    for line in PARENT_RAW.read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        if row.get("variant") == variant:
            selected.append(line)
            rows.append(row)
    return rows, hashlib.sha256(b"".join(selected)).hexdigest()


def derived_read4_requests() -> list[dict[str, Any]]:
    source_rows = read_jsonl(EVAL_READ4)
    if len(source_rows) != 24:
        raise RuntimeError("READ4_EVAL_ROWS_NOT_24")
    result = []
    for index, source in enumerate(source_rows, 1):
        if [item.get("role") for item in source.get("messages", [])] != ["system", "user"]:
            raise RuntimeError(f"READ4_MESSAGE_SHAPE_DRIFT:C{index:02d}")
        messages = [dict(item) for item in source["messages"]]
        original_user = dict(messages[1])
        messages[0]["content"] += "\n" + CONTRACT
        if messages[1] != original_user:
            raise RuntimeError(f"READ4_USER_CHANGED:C{index:02d}")
        result.append({"case_id": f"C{index:02d}", "messages": messages})
    return result


def verify_cross_arm_request_identity() -> dict[str, Any]:
    requests = {
        "READ1": read_jsonl(PARENT_REQUESTS["READ1"]),
        "READ2": read_jsonl(PARENT_REQUESTS["READ2"]),
        "READ4": derived_read4_requests(),
    }
    expected_cases = [f"C{index:02d}" for index in range(1, 25)]
    for arm, rows in requests.items():
        if len(rows) != 24 or [row.get("case_id") for row in rows] != expected_cases:
            raise RuntimeError(f"REQUEST_CASE_ORDER_DRIFT:{arm}")
    marker = "\n\n【编号负责区：只抽这里】"
    header = "【只读范围：只帮助理解，不得作为新增事实或证据】\n"
    for index in range(24):
        messages = [requests[arm][index].get("messages") for arm in ("READ1", "READ2", "READ4")]
        if any([item.get("role") for item in value] != ["system", "user"] for value in messages):
            raise RuntimeError(f"REQUEST_MESSAGE_SHAPE_DRIFT:{index}")
        systems = [value[0]["content"] for value in messages]
        if len(set(systems)) != 1 or not systems[0].endswith("\n" + CONTRACT):
            raise RuntimeError(f"REQUEST_SYSTEM_OR_B_CONTRACT_DRIFT:{index}")
        read_scopes = []
        tails = []
        for value in messages:
            user = value[1]["content"]
            if user.count(marker) != 1 or not user.startswith(header):
                raise RuntimeError(f"REQUEST_USER_SHAPE_DRIFT:{index}")
            front, tail = user.split(marker, 1)
            read_scopes.append(front[len(header) :])
            tails.append(marker + tail)
        if len(set(tails)) != 1:
            raise RuntimeError(f"REQUEST_FOCUS_OR_ALLOWLIST_DRIFT:{index}")
        if len(set(read_scopes)) != 3:
            raise RuntimeError(f"REQUEST_READ_SCOPE_NOT_DISTINCT:{index}")
    return {
        "rows_per_arm": 24,
        "case_order": "C01_TO_C24",
        "system_with_format_b_equal": True,
        "focus_and_allowlist_tail_equal": True,
        "only_read_scope_text_differs": True,
    }


def verify_static_inputs() -> dict[str, Any]:
    actual = {
        "parent_spec_sha256": sha256(PARENT_SPEC),
        "parent_raw_sha256": sha256(PARENT_RAW),
        "parent_result_sha256": sha256(PARENT_RESULT),
        "parent_metrics_sha256": sha256(PARENT_METRICS),
        "read1_actual_request_sha256": sha256(PARENT_REQUESTS["READ1"]),
        "read2_actual_request_sha256": sha256(PARENT_REQUESTS["READ2"]),
        "eval_read4_sha256": sha256(EVAL_READ4),
        "gold_sha256": sha256(GOLD),
        "txx_sha256": sha256(TXX),
        "schema_sha256": sha256(SCHEMA),
        "semantic_policy_sha256": sha256(POLICY),
        "wo_scorer_sha256": sha256(WO_SCORER),
        "read2_r02_sha256": sha256(READ2_R02),
        "read2_final_sha256": sha256(READ2_FINAL),
    }
    for variant, key in (
        ("BASE_READ1", "base_read1_projection_sha256"),
        ("BASE_READ2", "base_read2_projection_sha256"),
    ):
        rows, projection_sha = exact_line_projection(variant)
        if len(rows) != 24 or [row.get("case_id") for row in rows] != [f"C{i:02d}" for i in range(1, 25)]:
            raise RuntimeError(f"BASE_PROJECTION_CASE_DRIFT:{variant}")
        actual[key] = projection_sha
    actual["read4_b_requests_sha256"] = hashlib.sha256(jsonl_bytes(derived_read4_requests())).hexdigest()
    verify_cross_arm_request_identity()
    if actual != EXPECTED:
        raise RuntimeError(f"STATIC_INPUT_SHA_DRIFT:{actual}")
    if sha256(MODEL_RECEIPT) != MODEL_RECEIPT_SHA:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    return actual


def verify_model_receipt_members() -> dict[str, Any]:
    if sha256(MODEL_RECEIPT) != MODEL_RECEIPT_SHA:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    receipt = strict_json(MODEL_RECEIPT)
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


def validate_ticket(path: Path) -> dict[str, Any]:
    ticket = strict_json(path)
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("TICKET_KEYS_DRIFT")
    fixed = {
        "schema_version": "base-context-b-relative-screen-ticket/1.0",
        "approved": True,
        "scope": "BASE_CONTEXT_B_RELATIVE_SCREEN_SINGLE_READ4_INFERENCE",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-base-read4"],
        "spec_sha256": sha256(SPEC),
        "runner_sha256": sha256(Path(__file__)),
        "scorer_sha256": sha256(SCORER),
        "model_receipt_sha256": MODEL_RECEIPT_SHA,
        **EXPECTED,
    }
    for key, expected in fixed.items():
        if ticket.get(key) != expected:
            raise RuntimeError(f"TICKET_FIELD_DRIFT:{key}")
    for key in ("authorized_by", "decision_id", "decision_text_sha256", "source_thread_id", "issued_at"):
        if not isinstance(ticket.get(key), str) or not ticket[key]:
            raise RuntimeError(f"TICKET_AUTHORITY_MISSING:{key}")
    verify_static_inputs()
    if RUN_ROOT.exists():
        raise RuntimeError(f"RUN_ROOT_EXISTS_NO_RETRY:{RUN_ROOT}")
    return ticket


def system_free_percent() -> int:
    import subprocess

    result = subprocess.run(["memory_pressure", "-Q"], text=True, capture_output=True, check=False)
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else -1


def generate(model: Any, tokenizer: Any, stream_generate: Any, sampler: Any, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, request in enumerate(requests, 1):
        free = system_free_percent()
        if free >= 0 and free < 8:
            raise RuntimeError(f"MEMORY_HARD_STOP:{request['case_id']}:{free}")
        prompt = tokenizer.apply_chat_template(request["messages"], tokenize=False, add_generation_prompt=True)
        pieces: list[str] = []
        final = None
        began = time.monotonic()
        for response in stream_generate(model, tokenizer, prompt=prompt, max_tokens=2048, sampler=sampler):
            pieces.append(response.text)
            final = response
        if final is None:
            raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{request['case_id']}")
        raw = "".join(pieces)
        rows.append(
            {
                "variant": "BASE_READ4",
                "arm": "READ4",
                "case_id": request["case_id"],
                "raw_output": raw,
                "finish_reason": final.finish_reason,
                "stop_token": int(final.token),
                "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids,
                "generation_tokens_including_stop": int(final.generation_tokens),
                "output_tokens_excluding_stop": len(tokenizer.encode(raw, add_special_tokens=False)),
                "input_tokens": int(final.prompt_tokens),
                "elapsed_seconds": round(time.monotonic() - began, 3),
            }
        )
        print(f"BASE_READ4_PROGRESS case={index}/24", flush=True)
    return rows


def infer(ticket_path: Path, validate_only: bool) -> None:
    ticket = validate_ticket(ticket_path)
    if validate_only:
        print(json.dumps({"status": "PASS_TICKET_VALIDATION", "run_root_exists": False}))
        return
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = derived_read4_requests()
    RUN_ROOT.mkdir(parents=False)
    ticket_sha = sha256(ticket_path)
    ticket_copy = RUN_ROOT / "AUTHORIZATION_TICKET.json"
    if ticket_copy.exists():
        raise RuntimeError("AUTHORIZATION_TICKET_COPY_EXISTS_NO_OVERWRITE")
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
            "authorized_commands": ticket["authorized_commands"],
            "model_receipt_sha256": MODEL_RECEIPT_SHA,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    request_path = RUN_ROOT / "requests/BASE_READ4_B_24.jsonl"
    write_jsonl(request_path, requests)
    if sha256(request_path) != EXPECTED["read4_b_requests_sha256"]:
        raise RuntimeError("WRITTEN_READ4_REQUEST_SHA_DRIFT")
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
    raw_path = RUN_ROOT / "inference/BASE_READ4_RAW_24.jsonl"
    write_jsonl(raw_path, rows)
    write_json(
        RUN_ROOT / "inference/BASE_READ4_RESULT.json",
        {
            "status": "PASS_BASE_READ4_24_INFERENCE",
            "run_id": RUN_ID,
            "rows": len(rows),
            "raw_sha256": sha256(raw_path),
            "request_sha256": sha256(request_path),
            "ticket_sha256": ticket_sha,
            "ticket_copy_sha256": sha256(ticket_copy),
            "spec_sha256": sha256(SPEC),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "model_receipt_sha256": MODEL_RECEIPT_SHA,
            "model_member_gates_before_each_load": [
                {"variant": "BASE_READ4", "arm": "READ4", "gate": model_gate}
            ],
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "PASS_BASE_READ4_INFERENCE", "raw_sha256": sha256(raw_path)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("infer-base-read4",))
    parser.add_argument("--ticket", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.ticket is None:
        raise RuntimeError("EXECUTION_TICKET_REQUIRED_BEFORE_RUN_ROOT_OR_MODEL_LOAD")
    infer(args.ticket, args.validate_only)


if __name__ == "__main__":
    main()
