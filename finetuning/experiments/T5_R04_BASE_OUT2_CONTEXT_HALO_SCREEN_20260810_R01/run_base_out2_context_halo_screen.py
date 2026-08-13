#!/usr/bin/env python3
"""Ticket-bound local Base inference for the OUT2 H120/H60 halo screen."""

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
import unicodedata


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC = EXP / "SPEC.json"
SCORER = EXP / "score_base_out2_context_halo_screen.py"
PREP_RECEIPT = EXP / "PREPARE_RECEIPT.json"
RUN_ID = "T5_R04_BASE_OUT2_CONTEXT_HALO_SCREEN_R01"
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
PARENT_RAW = PARENT_RUN / "inference/FULL24_MATCHED_RAW.jsonl"
H180_REQUEST = PARENT_RUN / "requests/full24/READ2.jsonl"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
SOURCE_INDEX = EVAL_ROOT / "REAL24_SOURCE_INDEX.jsonl"
TXX = EVAL_ROOT / "REAL24_TXX_MAP.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
H180_EVAL = EVAL_ROOT / "READ_2_HALO180_EVAL24.jsonl"
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
R07 = REPO / "finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R07"

READ_HEADER = "【只读范围：只帮助理解，不得作为新增事实或证据】\n"
FOCUS_MARKER = "\n\n【编号负责区：只抽这里】"
VARIANTS = {
    120: "BASE_OUT2_HALO120",
    60: "BASE_OUT2_HALO60",
}
REQUEST_SHA = {
    120: "d31e907a4e897a59ce9503da70f746c8db42f010a8169a5bd001d6841abed655",
    60: "4b9e7aa3ec19e4f594a2ebc3ce1ed2e4ec7892067aff5a9ba99482434476fe6e",
}
EXPECTED = {
    "source_index_sha256": "0fe7ecb1649b93e4faab3d253d8904bee7f1a7a3e6f7f0fbb8b8e722c405de97",
    "txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "h180_eval_sha256": "a12f1f5cb1adfed4958418bfa8373af52b6305fdef64122c9bf02e3338c77e85",
    "h180_request_sha256": "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    "h180_projection_sha256": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "parent_raw_sha256": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "r07_readme_sha256": "46dc1bbc99076517fa813d26d5d0f3967785e18457a3fe5ba9bc979813b59247",
    "r07_registry_sha256": "96431fbb1c90a64cbd06b6117b4aada564b38b6e3256f81327312486cf904782",
    "r07_result_ticket_sha256": "c38121cece96ac7dd5dda49e2976bab4c38bb17c30de38bdbaccb10e4ad1f376",
    "base_context_final_sha256": "f625c10ecf0e1d4be8eade2032dc2fdbe6d398ac55a6ad89f47abffa117825c7",
    "base_context_decisions_sha256": "ddc75e55cb441c6dd90f354f2a7ee7ffb28dd32f08e82a91df2052d1ae5ccf4d",
    "base_context_adjudication_receipt_sha256": (
        "9170e59a8219efc5fff4e13291842f8a114fcdee00c95e9ffe85c063c345b6f3"
    ),
    "read2_r02_sha256": "03eb97a774ac41599d6f897e64486cec37d0a237b073f0ab621039733d599636",
    "read2_r02_receipt_sha256": "89922af0093da4f34da59e5f661703502fc7b4b3507f46a387831e155ee354b3",
    "read2_final_sha256": "524f8bcceb37aea95a6cf1ac7445580353360fdfd6de525982a216efa49ec96f",
    "semantic_policy_sha256": "73083a1d91edcc8fadabd2342fc59b89e10ef770aeaa6ffe926867f4f4c39a93",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "wo_scorer_sha256": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
    "h120_request_sha256": REQUEST_SHA[120],
    "h60_request_sha256": REQUEST_SHA[60],
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


def exact_h180_projection() -> tuple[list[dict[str, Any]], str]:
    selected: list[bytes] = []
    rows: list[dict[str, Any]] = []
    for line in PARENT_RAW.read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        if row.get("variant") == "BASE_READ2":
            selected.append(line)
            rows.append(row)
    return rows, hashlib.sha256(b"".join(selected)).hexdigest()


def is_variation_or_joiner(character: str) -> bool:
    codepoint = ord(character)
    return (
        character == "\u200d"
        or 0xFE00 <= codepoint <= 0xFE0F
        or 0xE0100 <= codepoint <= 0xE01EF
        or 0x1F3FB <= codepoint <= 0x1F3FF
    )


def verify_safe_boundary(text: str, index: int, label: str) -> None:
    if index <= 0 or index >= len(text):
        return
    before = text[index - 1]
    after = text[index]
    if before == "\r" and after == "\n":
        raise RuntimeError(f"HALO_BOUNDARY_SPLITS_CRLF:{label}")
    if (
        unicodedata.combining(before)
        or unicodedata.combining(after)
        or is_variation_or_joiner(before)
        or is_variation_or_joiner(after)
    ):
        raise RuntimeError(f"HALO_BOUNDARY_SPLITS_GRAPHEME_RISK:{label}")


def target_texts() -> dict[str, str]:
    source_rows = read_jsonl(SOURCE_INDEX)
    txx_rows = read_jsonl(TXX)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if [row.get("case_id") for row in source_rows] != cases:
        raise RuntimeError("SOURCE_INDEX_CASE_ORDER_DRIFT")
    if [row.get("case_id") for row in txx_rows] != cases:
        raise RuntimeError("TXX_CASE_ORDER_DRIFT")
    result = {}
    for source, txx in zip(source_rows, txx_rows, strict=True):
        units = txx.get("target_units")
        if not isinstance(units, list) or [unit.get("id") for unit in units] != [
            f"T{index:02d}" for index in range(1, len(units) + 1)
        ]:
            raise RuntimeError(f"TXX_UNIT_ORDER_DRIFT:{source['case_id']}")
        target = "".join(unit["text"] for unit in units)
        source_path = Path(source["source_path"])
        raw = source_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["source_sha256"]:
            raise RuntimeError(f"SOURCE_FILE_SHA_DRIFT:{source['case_id']}")
        text = raw.decode("utf-8", errors="strict")
        sliced = text[source["target_start"] : source["target_end"]]
        if sliced != target:
            raise RuntimeError(f"SOURCE_TARGET_REBUILD_DRIFT:{source['case_id']}")
        if hashlib.sha256(target.encode("utf-8")).hexdigest() != source["target_sha256"]:
            raise RuntimeError(f"SOURCE_TARGET_SHA_DRIFT:{source['case_id']}")
        if txx.get("target_sha256") != source["target_sha256"]:
            raise RuntimeError(f"TXX_TARGET_SHA_DRIFT:{source['case_id']}")
        result[source["case_id"]] = target
    return result


def split_h180_request(
    row: dict[str, Any], target: str
) -> tuple[str, str, str, str, list[dict[str, Any]]]:
    messages = row.get("messages")
    if not isinstance(messages, list) or [message.get("role") for message in messages] != [
        "system",
        "user",
    ]:
        raise RuntimeError(f"H180_MESSAGE_SHAPE_DRIFT:{row.get('case_id')}")
    user = messages[1].get("content")
    if not isinstance(user, str) or not user.startswith(READ_HEADER):
        raise RuntimeError(f"H180_READ_HEADER_DRIFT:{row['case_id']}")
    if user.count(FOCUS_MARKER) != 1:
        raise RuntimeError(f"H180_FOCUS_MARKER_DRIFT:{row['case_id']}")
    front, tail = user.split(FOCUS_MARKER, 1)
    read_text = front[len(READ_HEADER) :]
    if read_text.count(target) != 1:
        raise RuntimeError(f"H180_TARGET_OCCURRENCE_NOT_ONE:{row['case_id']}")
    start = read_text.index(target)
    left = read_text[:start]
    right = read_text[start + len(target) :]
    if len(left) > 180 or len(right) > 180:
        raise RuntimeError(f"H180_SIDE_EXCEEDS_180:{row['case_id']}")
    return left, target, right, FOCUS_MARKER + tail, messages


def build_requests(halo: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if halo not in VARIANTS:
        raise RuntimeError(f"UNKNOWN_HALO:{halo}")
    targets = target_texts()
    source = read_jsonl(H180_REQUEST)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if [row.get("case_id") for row in source] != cases:
        raise RuntimeError("H180_REQUEST_CASE_ORDER_DRIFT")
    result = []
    lengths = []
    for row in source:
        case_id = row["case_id"]
        left, target, right, tail, messages = split_h180_request(row, targets[case_id])
        left_start = max(0, len(left) - halo)
        right_end = min(len(right), halo)
        verify_safe_boundary(left, left_start, f"{case_id}:LEFT:{halo}")
        verify_safe_boundary(right, right_end, f"{case_id}:RIGHT:{halo}")
        new_read = left[left_start:] + target + right[:right_end]
        result.append(
            {
                "case_id": case_id,
                "messages": [
                    dict(messages[0]),
                    {"role": "user", "content": READ_HEADER + new_read + tail},
                ],
            }
        )
        lengths.append(
            {
                "case_id": case_id,
                "left_chars": len(left) - left_start,
                "right_chars": right_end,
            }
        )
    return result, lengths


def verify_request_derivation() -> dict[str, Any]:
    h180 = read_jsonl(H180_REQUEST)
    h120, lengths120 = build_requests(120)
    h60, lengths60 = build_requests(60)
    hashes = {
        "h120_request_sha256": hashlib.sha256(jsonl_bytes(h120)).hexdigest(),
        "h60_request_sha256": hashlib.sha256(jsonl_bytes(h60)).hexdigest(),
    }
    if hashes != {
        "h120_request_sha256": REQUEST_SHA[120],
        "h60_request_sha256": REQUEST_SHA[60],
    }:
        raise RuntimeError(f"DERIVED_HALO_REQUEST_SHA_DRIFT:{hashes}")
    targets = target_texts()
    for index, case_id in enumerate(f"C{i:02d}" for i in range(1, 25)):
        split180 = split_h180_request(h180[index], targets[case_id])
        split120 = split_h180_request(h120[index], targets[case_id])
        split60 = split_h180_request(h60[index], targets[case_id])
        if not (
            h180[index]["messages"][0]
            == h120[index]["messages"][0]
            == h60[index]["messages"][0]
        ):
            raise RuntimeError(f"HALO_SYSTEM_DRIFT:{case_id}")
        if not split180[3] == split120[3] == split60[3]:
            raise RuntimeError(f"HALO_FOCUS_TAIL_DRIFT:{case_id}")
        if not (split180[1] == split120[1] == split60[1] == targets[case_id]):
            raise RuntimeError(f"HALO_TARGET_DRIFT:{case_id}")
        if not (split180[0].endswith(split120[0]) and split120[0].endswith(split60[0])):
            raise RuntimeError(f"HALO_LEFT_NESTING_DRIFT:{case_id}")
        if not (split180[2].startswith(split120[2]) and split120[2].startswith(split60[2])):
            raise RuntimeError(f"HALO_RIGHT_NESTING_DRIFT:{case_id}")
    return {
        "rows_per_new_halo": 24,
        "total_new_requests": 48,
        "case_order": "C01_TO_C24",
        "system_focus_allowlist_target_unchanged": True,
        "h60_nested_in_h120_nested_in_h180": True,
        "exact_unicode_codepoint_slice_without_snapping_or_padding": True,
        "lengths_by_halo": {"120": lengths120, "60": lengths60},
        **hashes,
    }


def verify_h180_eval_identity() -> None:
    eval_rows = read_jsonl(H180_EVAL)
    actual_rows = read_jsonl(H180_REQUEST)
    if len(eval_rows) != 24 or len(actual_rows) != 24:
        raise RuntimeError("H180_EVAL_OR_REQUEST_ROWS_DRIFT")
    for eval_row, actual_row in zip(eval_rows, actual_rows, strict=True):
        if eval_row.get("messages", [None, None])[1] != actual_row.get("messages", [None, None])[1]:
            raise RuntimeError(f"H180_EVAL_USER_DRIFT:{actual_row.get('case_id')}")
        eval_system = eval_row["messages"][0]["content"]
        actual_system = actual_row["messages"][0]["content"]
        if not actual_system.startswith(eval_system + "\n"):
            raise RuntimeError(f"H180_ACTUAL_SYSTEM_NOT_DERIVED:{actual_row.get('case_id')}")


def verify_static_inputs() -> dict[str, Any]:
    projection, projection_sha = exact_h180_projection()
    if len(projection) != 24 or [row.get("case_id") for row in projection] != [
        f"C{index:02d}" for index in range(1, 25)
    ]:
        raise RuntimeError("H180_PROJECTION_CASE_ORDER_DRIFT")
    request_proof = verify_request_derivation()
    actual = {
        "source_index_sha256": sha256(SOURCE_INDEX),
        "txx_sha256": sha256(TXX),
        "gold_sha256": sha256(GOLD),
        "h180_eval_sha256": sha256(H180_EVAL),
        "h180_request_sha256": sha256(H180_REQUEST),
        "h180_projection_sha256": projection_sha,
        "parent_raw_sha256": sha256(PARENT_RAW),
        "r07_readme_sha256": sha256(R07 / "00_READ_ME_FIRST.md"),
        "r07_registry_sha256": sha256(R07 / "DECISION_REGISTRY.json"),
        "r07_result_ticket_sha256": sha256(R07 / "BASE_READ2_OUT_FORMAT_RESULT_TICKET.json"),
        "base_context_final_sha256": sha256(BASE_CONTEXT_FINAL),
        "base_context_decisions_sha256": sha256(BASE_CONTEXT_DECISIONS),
        "base_context_adjudication_receipt_sha256": sha256(BASE_CONTEXT_ADJ_RECEIPT),
        "read2_r02_sha256": sha256(READ2_R02),
        "read2_r02_receipt_sha256": sha256(READ2_R02_RECEIPT),
        "read2_final_sha256": sha256(READ2_FINAL),
        "semantic_policy_sha256": sha256(POLICY),
        "schema_sha256": sha256(SCHEMA),
        "wo_scorer_sha256": sha256(WO_SCORER),
        "h120_request_sha256": request_proof["h120_request_sha256"],
        "h60_request_sha256": request_proof["h60_request_sha256"],
    }
    if actual != EXPECTED:
        raise RuntimeError(f"STATIC_INPUT_SHA_DRIFT:{actual}")
    verify_h180_eval_identity()
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


def validate_ticket(path: Path) -> dict[str, Any]:
    ticket = read_json(path)
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("TICKET_KEYS_DRIFT")
    fixed = {
        "schema_version": "base-out2-context-halo-screen-ticket/1.0",
        "approved": True,
        "scope": "BASE_OUT2_CONTEXT_HALO_SCREEN_SINGLE_48_INFERENCE",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-new-halos"],
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
    requests_by_halo: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for halo in (120, 60):
        for index, request in enumerate(requests_by_halo[halo], 1):
            free = system_free_percent()
            if free >= 0 and free < 8:
                raise RuntimeError(f"MEMORY_HARD_STOP:HALO{halo}:{request['case_id']}:{free}")
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
                raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:HALO{halo}:{request['case_id']}")
            raw = "".join(pieces)
            rows.append(
                {
                    "variant": VARIANTS[halo],
                    "arm": f"HALO{halo}",
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
            print(f"HALO{halo}_PROGRESS case={index}/24", flush=True)
    return rows


def infer(ticket_path: Path, validate_only: bool) -> None:
    ticket = validate_ticket(ticket_path)
    if validate_only:
        print(json.dumps({"status": "PASS_TICKET_VALIDATION", "run_root_exists": False}))
        return
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests_by_halo = {halo: build_requests(halo)[0] for halo in (120, 60)}
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
        120: RUN_ROOT / "requests/HALO120_OUT2_READ2_24.jsonl",
        60: RUN_ROOT / "requests/HALO60_OUT2_READ2_24.jsonl",
    }
    for halo, path in request_paths.items():
        write_jsonl(path, requests_by_halo[halo])
        if sha256(path) != REQUEST_SHA[halo]:
            raise RuntimeError(f"WRITTEN_HALO_REQUEST_SHA_DRIFT:{halo}")
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
        requests_by_halo,
    )
    raw_path = RUN_ROOT / "inference/NEW_HALOS_RAW_48.jsonl"
    write_jsonl(raw_path, rows)
    write_json(
        RUN_ROOT / "inference/NEW_HALOS_RESULT.json",
        {
            "status": "PASS_NEW_HALOS_48_INFERENCE",
            "run_id": RUN_ID,
            "rows": len(rows),
            "rows_by_variant": {variant: 24 for variant in VARIANTS.values()},
            "raw_sha256": sha256(raw_path),
            "request_sha256_by_halo": {
                str(halo): sha256(path) for halo, path in request_paths.items()
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
                    "load_scope": "SHARED_UNFINETUNED_BASE_FOR_HALO120_HALO60",
                    "gate": model_gate,
                }
            ],
            "model_load_count": 1,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "PASS_NEW_HALOS_INFERENCE", "raw_sha256": sha256(raw_path)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "infer-new-halos"))
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
