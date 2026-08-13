#!/usr/bin/env python3
"""Ticket-bound local BASE+READ2 inference for OUT3/OUT4 Demo formats."""

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
SCORER = EXP / "score_base_read2_out_format_screen.py"
PREP_RECEIPT = EXP / "PREPARE_RECEIPT.json"
RUN_ID = "T5_R04_BASE_READ2_OUT_FORMAT_SCREEN_R01"
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
READ2_REQUEST = PARENT_RUN / "requests/full24/READ2.jsonl"
BASE_CONTEXT_RUN = REPO / "runs/T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_R01"
BASE_CONTEXT_FINAL = BASE_CONTEXT_RUN / "scoring/final/METRICS.json"
BASE_CONTEXT_DECISIONS = (
    BASE_CONTEXT_RUN / "scoring/adjudications/SEMANTIC_ADJUDICATIONS_223.jsonl"
)
BASE_CONTEXT_ADJ_RECEIPT = BASE_CONTEXT_RUN / "scoring/adjudications/ADJUDICATION_RECEIPT.json"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
TXX = EVAL_ROOT / "REAL24_TXX_MAP.jsonl"
POLICY = (
    REPO
    / "finetuning/experiments/T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_20260810_R01/"
    "SEMANTIC_ADJUDICATION_POLICY.md"
)
WO_SCORER = (
    REPO
    / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/"
    "tools/score_demo.py"
)
R06 = REPO / "finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R06"

COMMON_PREFIX = (
    "你是中文小说事实抽取器。B/T 编号只表示原文位置。"
    "只抽取【编号负责区】明确表达、会影响后续情节的事实。"
)
STATUS_VALUES = "已发生、正在发生、计划、承诺、条件、推测、误信、否定"
OUT3_SYSTEM = (
    COMMON_PREFIX
    + "每条事实的证据只能来自【允许证据 ID】，并使用最小充分的连续 T 编号范围。"
    "【输出合同】输出必须是且只能是一个顶层键为 facts 的 JSON 对象；"
    "facts 为数组且允许为空，每个元素只能且必须包含 fact、status、speaker、evidence_ranges。"
    "fact 为非空字符串；speaker 为字符串或 null；status 只能取："
    + STATUS_VALUES
    + "。evidence_ranges 必须是且只能是恰好包含 1 个字符串的数组；"
    "单个证据写成 [\"T01\"]，连续证据写成 [\"T01-T03\"]。"
    "不得把一条事实写成多个范围字符串，也不得倒序、越出允许范围或使用其他格式。"
    "没有事实时输出 {\"facts\":[]}。不得输出其他字段、Markdown 或解释。"
)
OUT4_SYSTEM = (
    COMMON_PREFIX
    + "每条事实的证据只能来自【允许证据 ID】，并选择最小充分的连续 T 编号集合。"
    "【输出合同】输出必须是且只能是一个顶层键为 facts 的 JSON 对象；"
    "facts 为数组且允许为空，每个元素只能且必须包含 fact、status、speaker、unit_ids、quote。"
    "fact 和 quote 为非空字符串；speaker 为字符串或 null；status 只能取："
    + STATUS_VALUES
    + "。unit_ids 必须是字符串数组，只选最小充分的连续 T 编号；"
    "quote 必须是所选 unit_ids 对应目标单元文本内的逐字连续原文，不得改写或引入目标外文字。"
    "没有事实时输出 {\"facts\":[]}。不得输出其他字段、Markdown 或解释。"
)
VARIANTS = {
    "OUT3-IDRANGE": "BASE_READ2_OUT3_IDRANGE",
    "OUT4-IDQUOTE": "BASE_READ2_OUT4_IDQUOTE",
}
OUT3_REQUEST_SHA = "664726e8847a0513de36d9eb3852eaa5c98a2cda2e8f7a82e27ff5570a2e08ed"
OUT4_REQUEST_SHA = "aba03bca27429245795c1c274436d3b44a57c047ab0038e7c08167c091ddab26"
EXPECTED = {
    "parent_spec_sha256": "ff4ae3e702a318d3d47a0476d1cbbc18078884735e14176d1f9171b07232cd06",
    "parent_raw_sha256": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "read2_projection_sha256": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "read2_request_sha256": "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "base_context_final_sha256": "f625c10ecf0e1d4be8eade2032dc2fdbe6d398ac55a6ad89f47abffa117825c7",
    "base_context_decisions_sha256": "ddc75e55cb441c6dd90f354f2a7ee7ffb28dd32f08e82a91df2052d1ae5ccf4d",
    "base_context_adjudication_receipt_sha256": "9170e59a8219efc5fff4e13291842f8a114fcdee00c95e9ffe85c063c345b6f3",
    "semantic_policy_sha256": "73083a1d91edcc8fadabd2342fc59b89e10ef770aeaa6ffe926867f4f4c39a93",
    "wo_scorer_sha256": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
    "r06_registry_sha256": "bf997a9e6e614a1d115716a55d3eddd55c9d47662e5367350862db4dbf250c0d",
    "r06_result_ticket_sha256": "02089af291d96757ffea114d0ea3f527f22f499614ba1b93bfb40b3efb3555f6",
    "out3_request_sha256": OUT3_REQUEST_SHA,
    "out4_request_sha256": OUT4_REQUEST_SHA,
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


def exact_read2_projection() -> tuple[list[dict[str, Any]], str]:
    selected: list[bytes] = []
    rows: list[dict[str, Any]] = []
    for line in PARENT_RAW.read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        if row.get("variant") == "BASE_READ2":
            selected.append(line)
            rows.append(row)
    return rows, hashlib.sha256(b"".join(selected)).hexdigest()


def build_requests(out_format: str) -> list[dict[str, Any]]:
    if out_format not in {"OUT3-IDRANGE", "OUT4-IDQUOTE"}:
        raise RuntimeError(f"UNKNOWN_OUT_FORMAT:{out_format}")
    system = OUT3_SYSTEM if out_format == "OUT3-IDRANGE" else OUT4_SYSTEM
    source = read_jsonl(READ2_REQUEST)
    expected_cases = [f"C{index:02d}" for index in range(1, 25)]
    if len(source) != 24 or [row.get("case_id") for row in source] != expected_cases:
        raise RuntimeError("READ2_SOURCE_CASE_ORDER_DRIFT")
    result = []
    for row in source:
        messages = row.get("messages")
        if not isinstance(messages, list) or [item.get("role") for item in messages] != ["system", "user"]:
            raise RuntimeError(f"READ2_MESSAGE_SHAPE_DRIFT:{row.get('case_id')}")
        original_user = dict(messages[1])
        if not messages[0].get("content", "").startswith(COMMON_PREFIX):
            raise RuntimeError(f"READ2_FACT_DEFINITION_DRIFT:{row['case_id']}")
        new_messages = [{"role": "system", "content": system}, dict(messages[1])]
        if new_messages[1] != original_user:
            raise RuntimeError(f"READ2_USER_CHANGED:{row['case_id']}")
        if "evidence_ids" in new_messages[0]["content"]:
            raise RuntimeError(f"OLD_OUTPUT_CONTRACT_LEAK:{row['case_id']}")
        result.append({"case_id": row["case_id"], "messages": new_messages})
    return result


def verify_request_derivation() -> dict[str, Any]:
    source = read_jsonl(READ2_REQUEST)
    out3 = build_requests("OUT3-IDRANGE")
    out4 = build_requests("OUT4-IDQUOTE")
    for index in range(24):
        if not (source[index]["messages"][1] == out3[index]["messages"][1] == out4[index]["messages"][1]):
            raise RuntimeError(f"USER_NOT_IDENTICAL:C{index + 1:02d}")
        if not (out3[index]["messages"][0]["content"].startswith(COMMON_PREFIX) and out4[index]["messages"][0]["content"].startswith(COMMON_PREFIX)):
            raise RuntimeError(f"FACT_DEFINITION_NOT_SHARED:C{index + 1:02d}")
        if out3[index]["messages"][0] == out4[index]["messages"][0]:
            raise RuntimeError(f"OUTPUT_CONTRACT_NOT_DISTINCT:C{index + 1:02d}")
    hashes = {
        "out3_request_sha256": hashlib.sha256(jsonl_bytes(out3)).hexdigest(),
        "out4_request_sha256": hashlib.sha256(jsonl_bytes(out4)).hexdigest(),
    }
    if hashes != {
        "out3_request_sha256": OUT3_REQUEST_SHA,
        "out4_request_sha256": OUT4_REQUEST_SHA,
    }:
        raise RuntimeError(f"DERIVED_REQUEST_SHA_DRIFT:{hashes}")
    return {
        "rows_per_new_format": 24,
        "total_new_requests": 48,
        "case_order": "C01_TO_C24",
        "read2_user_messages_identical": True,
        "fact_definition_identical": True,
        "only_system_output_contract_differs": True,
        **hashes,
    }


def verify_static_inputs() -> dict[str, Any]:
    projection, projection_sha = exact_read2_projection()
    if len(projection) != 24 or [row.get("case_id") for row in projection] != [f"C{i:02d}" for i in range(1, 25)]:
        raise RuntimeError("OUT2_PROJECTION_CASE_ORDER_DRIFT")
    actual = {
        "parent_spec_sha256": sha256(PARENT_SPEC),
        "parent_raw_sha256": sha256(PARENT_RAW),
        "read2_projection_sha256": projection_sha,
        "read2_request_sha256": sha256(READ2_REQUEST),
        "gold_sha256": sha256(GOLD),
        "txx_sha256": sha256(TXX),
        "base_context_final_sha256": sha256(BASE_CONTEXT_FINAL),
        "base_context_decisions_sha256": sha256(BASE_CONTEXT_DECISIONS),
        "base_context_adjudication_receipt_sha256": sha256(BASE_CONTEXT_ADJ_RECEIPT),
        "semantic_policy_sha256": sha256(POLICY),
        "wo_scorer_sha256": sha256(WO_SCORER),
        "r06_registry_sha256": sha256(R06 / "DECISION_REGISTRY.json"),
        "r06_result_ticket_sha256": sha256(R06 / "BASE_CONTEXT_DEMO_RESULT_TICKET.json"),
        **{key: value for key, value in verify_request_derivation().items() if key.endswith("sha256")},
    }
    if actual != EXPECTED:
        raise RuntimeError(f"STATIC_INPUT_SHA_DRIFT:{actual}")
    if sha256(MODEL_RECEIPT) != MODEL_RECEIPT_SHA:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    return actual


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


def validate_ticket(path: Path) -> dict[str, Any]:
    ticket = read_json(path)
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("TICKET_KEYS_DRIFT")
    fixed = {
        "schema_version": "base-read2-out-format-screen-ticket/1.0",
        "approved": True,
        "scope": "BASE_READ2_OUT_FORMAT_SCREEN_SINGLE_48_INFERENCE",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-new-formats"],
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


def generate(
    model: Any,
    tokenizer: Any,
    stream_generate: Any,
    sampler: Any,
    requests_by_format: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for out_format in ("OUT3-IDRANGE", "OUT4-IDQUOTE"):
        for index, request in enumerate(requests_by_format[out_format], 1):
            free = system_free_percent()
            if free >= 0 and free < 8:
                raise RuntimeError(f"MEMORY_HARD_STOP:{out_format}:{request['case_id']}:{free}")
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
                raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{out_format}:{request['case_id']}")
            raw = "".join(pieces)
            rows.append(
                {
                    "variant": VARIANTS[out_format],
                    "arm": out_format,
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
            print(f"{out_format}_PROGRESS case={index}/24", flush=True)
    return rows


def infer(ticket_path: Path, validate_only: bool) -> None:
    ticket = validate_ticket(ticket_path)
    if validate_only:
        print(json.dumps({"status": "PASS_TICKET_VALIDATION", "run_root_exists": False}))
        return
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests_by_format = {
        "OUT3-IDRANGE": build_requests("OUT3-IDRANGE"),
        "OUT4-IDQUOTE": build_requests("OUT4-IDQUOTE"),
    }
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
        "OUT3-IDRANGE": RUN_ROOT / "requests/OUT3_IDRANGE_READ2_24.jsonl",
        "OUT4-IDQUOTE": RUN_ROOT / "requests/OUT4_IDQUOTE_READ2_24.jsonl",
    }
    for out_format, request_path in request_paths.items():
        write_jsonl(request_path, requests_by_format[out_format])
    if sha256(request_paths["OUT3-IDRANGE"]) != OUT3_REQUEST_SHA:
        raise RuntimeError("WRITTEN_OUT3_REQUEST_SHA_DRIFT")
    if sha256(request_paths["OUT4-IDQUOTE"]) != OUT4_REQUEST_SHA:
        raise RuntimeError("WRITTEN_OUT4_REQUEST_SHA_DRIFT")
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
    rows = generate(
        model,
        tokenizer,
        stream_generate,
        make_sampler(temp=0.0),
        requests_by_format,
    )
    raw_path = RUN_ROOT / "inference/NEW_FORMATS_RAW_48.jsonl"
    write_jsonl(raw_path, rows)
    write_json(
        RUN_ROOT / "inference/NEW_FORMATS_RESULT.json",
        {
            "status": "PASS_NEW_OUT_FORMATS_48_INFERENCE",
            "run_id": RUN_ID,
            "rows": len(rows),
            "rows_by_variant": {variant: 24 for variant in VARIANTS.values()},
            "raw_sha256": sha256(raw_path),
            "request_sha256_by_format": {
                out_format: sha256(path) for out_format, path in request_paths.items()
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
                    "load_scope": "SHARED_UNFINETUNED_BASE_FOR_OUT3_OUT4",
                    "gate": model_gate,
                }
            ],
            "model_load_count": 1,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    print(
        json.dumps(
            {"status": "PASS_NEW_OUT_FORMATS_INFERENCE", "raw_sha256": sha256(raw_path)}
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "infer-new-formats"))
    parser.add_argument("--ticket", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.command == "static-check":
        if args.ticket is not None or args.validate_only:
            raise RuntimeError("STATIC_CHECK_TAKES_NO_TICKET")
        print(json.dumps({"status": "PASS_STATIC_INPUTS", **verify_static_inputs()}))
        return
    if args.ticket is None:
        raise RuntimeError("EXECUTION_TICKET_REQUIRED_BEFORE_RUN_ROOT_OR_MODEL_LOAD")
    infer(args.ticket, args.validate_only)


if __name__ == "__main__":
    main()
