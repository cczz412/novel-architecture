#!/usr/bin/env python3
"""Prepare and, only with a future exact ticket, run BLOCK300 Stage1."""

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
ROOT = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC = EXP / "SPEC.json"
SCORER = EXP / "score_block300_stage1.py"
PREP_RECEIPT = EXP / "PREPARE_RECEIPT.json"
SOURCE_MAP = EXP / "BLOCK300_STAGE1_SOURCE_INDEX.jsonl"
REQUESTS = EXP / "BLOCK300_STAGE1_REQUESTS.jsonl"
RUN_ID = "T5_R04_BASE_OUT2_BLOCK300_STAGE1_SCREEN_R01"
RUN_ROOT = ROOT / f"runs/{RUN_ID}"
MODEL = ROOT.parent / "小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f"
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
MODEL_RECEIPT_SHA = "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
MODEL_FILE_COUNT = 13
MODEL_TOTAL_BYTES = 8_060_917_568
PYTHON = Path("/opt/homebrew/opt/python@3.12/bin/python3.12")
VENDOR = ROOT / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
REAL24 = ROOT / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
SOURCE_INDEX = REAL24 / "REAL24_SOURCE_INDEX.jsonl"
OLD_TXX = REAL24 / "REAL24_TXX_MAP.jsonl"
GOLD = REAL24 / "REAL24_GOLD_24.jsonl"
PARENT_RUN = ROOT / "runs/T5_R04_READ_CONTEXT_LOW_DOSE_B_RELATIVE_SCREEN_R01"
PARENT_RAW = PARENT_RUN / "inference/FULL24_MATCHED_RAW.jsonl"
H180_REQUEST = PARENT_RUN / "requests/full24/READ2.jsonl"
BASE_CONTEXT_FINAL = ROOT / "runs/T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_R01/scoring/final/METRICS.json"
R02 = ROOT / "finetuning/experiments/T5_R04_BASE_OUT2_TARGET_BLOCK_COARSE_SCREEN_PREFLIGHT_20260810_R02"
R02_CANDIDATES = R02 / "TARGET_BLOCK_CANDIDATES_R02.jsonl"
R02_STATS = R02 / "BLOCK_STATS_R02.json"
R02_RECEIPT = R02 / "PREPARE_RECEIPT.json"
SCHEMA = ROOT / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
POLICY = ROOT / "finetuning/experiments/T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_20260810_R01/SEMANTIC_ADJUDICATION_POLICY.md"
WO_SCORER = ROOT / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/tools/score_demo.py"

STAGE_CASES = ["C01", "C02", "C05", "C09", "C10", "C14", "C23", "C24"]
READ_HEADER = "【只读范围：只帮助理解，不得作为新增事实或证据】\n"
FOCUS_HEADER = "\n\n【编号负责区：只抽这里】\n"
ALLOW_HEADER = "\n\n【允许证据 ID】\n"
VARIANT = "BASE_OUT2_BLOCK300_STAGE1"
MAX_OUTPUT_TOKENS = 2048
EXPECTED = {
    "source_index_sha256": "0fe7ecb1649b93e4faab3d253d8904bee7f1a7a3e6f7f0fbb8b8e722c405de97",
    "old_txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "parent_raw_sha256": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "h180_request_sha256": "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    "base_context_final_sha256": "f625c10ecf0e1d4be8eade2032dc2fdbe6d398ac55a6ad89f47abffa117825c7",
    "base_read2_projection_sha256": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "r02_candidates_sha256": "d4579d4c6dbcba7f85f92c6318f9461d574fc31daab493fa5fcd8457bd04e393",
    "r02_stats_sha256": "06708fbbc6bb3ffa35705263098e57aad6f3e5a277ac241e670dccbd61af2ff1",
    "r02_receipt_sha256": "dcf8bebc34bb1d481e4a8dfe60172dfabf085ffade800d1d9da30d691381ad9f",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "semantic_policy_sha256": "73083a1d91edcc8fadabd2342fc59b89e10ef770aeaa6ffe926867f4f4c39a93",
    "wo_scorer_sha256": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) for row in rows)
        + "\n"
    ).encode()


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


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def split_units(text: str, max_chars: int = 40) -> list[dict[str, Any]]:
    strong = set("。！？!?；;\n")
    medium = set("，,：:、")
    units = []
    start = 0
    while start < len(text):
        hard_end = min(start + max_chars, len(text))
        end = hard_end
        if hard_end < len(text):
            min_cut = start + max(12, max_chars // 2)
            strong_pos = [index + 1 for index in range(min_cut, hard_end) if text[index] in strong]
            medium_pos = [index + 1 for index in range(min_cut, hard_end) if text[index] in medium]
            if strong_pos:
                end = strong_pos[-1]
            elif medium_pos:
                end = medium_pos[-1]
        if end <= start:
            raise RuntimeError("UNIT_SPLITTER_NO_PROGRESS")
        units.append({"start": start, "end": end, "text": text[start:end]})
        start = end
    return units


def is_grapheme_risk(character: str) -> bool:
    codepoint = ord(character)
    return (
        character == "\u200d"
        or unicodedata.combining(character) != 0
        or 0xFE00 <= codepoint <= 0xFE0F
        or 0xE0100 <= codepoint <= 0xE01EF
        or 0x1F3FB <= codepoint <= 0x1F3FF
    )


def verify_safe_boundary(text: str, index: int, label: str) -> None:
    if index <= 0 or index >= len(text):
        return
    if text[index - 1] == "\r" and text[index] == "\n":
        raise RuntimeError(f"BOUNDARY_SPLITS_CRLF:{label}")
    if is_grapheme_risk(text[index - 1]) or is_grapheme_risk(text[index]):
        raise RuntimeError(f"BOUNDARY_SPLITS_GRAPHEME:{label}")


def boundary_input_rows() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], str]:
    pre_freeze_paths = {
        SOURCE_INDEX: EXPECTED["source_index_sha256"],
        OLD_TXX: EXPECTED["old_txx_sha256"],
        H180_REQUEST: EXPECTED["h180_request_sha256"],
        R02_CANDIDATES: EXPECTED["r02_candidates_sha256"],
    }
    if {path: sha256(path) for path in pre_freeze_paths} != pre_freeze_paths:
        raise RuntimeError("PRE_FREEZE_STATIC_INPUT_SHA_DRIFT")
    sources = {row["case_id"]: row for row in read_jsonl(SOURCE_INDEX)}
    candidates = [
        row
        for row in read_jsonl(R02_CANDIDATES)
        if row["band"] == "BLOCK300" and row["case_id"] in STAGE_CASES
    ]
    order = {case_id: index for index, case_id in enumerate(STAGE_CASES)}
    candidates.sort(key=lambda row: (order[row["case_id"]], row["block_index"]))
    h180 = read_jsonl(H180_REQUEST)
    systems = {row["messages"][0]["content"] for row in h180}
    if len(candidates) != 22 or len(systems) != 1:
        raise RuntimeError("STAGE1_CANDIDATE_OR_SYSTEM_SHAPE_DRIFT")
    return sources, candidates, systems.pop()


def build_static_bytes() -> tuple[bytes, bytes]:
    sources, candidates, system = boundary_input_rows()
    mapping_rows = []
    request_rows = []
    for candidate in candidates:
        case_id = candidate["case_id"]
        source = sources[case_id]
        source_path = Path(source["source_path"])
        raw = source_path.read_bytes()
        if sha256_bytes(raw) != source["source_sha256"]:
            raise RuntimeError(f"SOURCE_SHA_DRIFT:{case_id}")
        chapter = raw.decode("utf-8", errors="strict")
        block_start = candidate["source_absolute_start"]
        block_end = candidate["source_absolute_end"]
        block_text = chapter[block_start:block_end]
        if sha256_bytes(block_text.encode()) != candidate["block_sha256"]:
            raise RuntimeError(f"BLOCK_SHA_DRIFT:{candidate['block_id']}")
        units = []
        for index, unit in enumerate(split_units(block_text), 1):
            unit_text = unit["text"]
            units.append(
                {
                    "id": f"T{index:02d}",
                    "text": unit_text,
                    "text_sha256": sha256_bytes(unit_text.encode()),
                    "block_start": unit["start"],
                    "block_end": unit["end"],
                    "original_target_start": candidate["target_relative_start"] + unit["start"],
                    "original_target_end": candidate["target_relative_start"] + unit["end"],
                    "source_absolute_start": block_start + unit["start"],
                    "source_absolute_end": block_start + unit["end"],
                }
            )
        if "".join(unit["text"] for unit in units) != block_text:
            raise RuntimeError(f"NEW_TXX_REBUILD_DRIFT:{candidate['block_id']}")
        left_start = max(0, block_start - 180)
        right_end = min(len(chapter), block_end + 180)
        verify_safe_boundary(chapter, left_start, f"{candidate['block_id']}:HALO_LEFT")
        verify_safe_boundary(chapter, right_end, f"{candidate['block_id']}:HALO_RIGHT")
        read_text = chapter[left_start:right_end]
        numbered = "".join(f"[{unit['id']}]" + unit["text"] for unit in units)
        allowlist = "、".join(unit["id"] for unit in units)
        request_id = f"{case_id}-K{candidate['block_index']:02d}"
        user = READ_HEADER + read_text + FOCUS_HEADER + numbered + ALLOW_HEADER + allowlist
        request_rows.append({"case_id": request_id, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        mapping_rows.append(
            {
                "schema_version": "base-out2-block300-stage1-source-map/1.0",
                "status": "PREPARED_NOT_AUTHORIZED_NOT_RUN",
                "request_id": request_id,
                "parent_case_id": case_id,
                "block_index": candidate["block_index"],
                "block_count_in_case": candidate["block_count_in_case"],
                "source_path": source["source_path"],
                "source_sha256": source["source_sha256"],
                "parent_target_sha256": source["target_sha256"],
                "block_sha256": candidate["block_sha256"],
                "block_start": 0,
                "block_end": len(block_text),
                "original_target_start": candidate["target_relative_start"],
                "original_target_end": candidate["target_relative_end"],
                "source_absolute_start": block_start,
                "source_absolute_end": block_end,
                "halo_left_codepoints": block_start - left_start,
                "halo_right_codepoints": right_end - block_end,
                "target_units": units,
            }
        )
    request_bytes = jsonl_bytes(request_rows)
    forbidden = (b'"gold"', b'"fact_count"', b'"density"', b'"crossing"', b'BLOCK300')
    if any(token in request_bytes for token in forbidden):
        raise RuntimeError("MODEL_REQUEST_CONTAINS_FORBIDDEN_AUDIT_METADATA")
    return jsonl_bytes(mapping_rows), request_bytes


def exact_base_read2_projection() -> tuple[int, str]:
    selected = []
    count = 0
    for line in PARENT_RAW.read_bytes().splitlines(keepends=True):
        if json.loads(line).get("variant") == "BASE_READ2":
            selected.append(line)
            count += 1
    return count, sha256_bytes(b"".join(selected))


def post_freeze_gold_audit(mapping_bytes: bytes, request_bytes: bytes) -> dict[str, Any]:
    post_paths = {
        GOLD: EXPECTED["gold_sha256"],
        R02_STATS: EXPECTED["r02_stats_sha256"],
        R02_RECEIPT: EXPECTED["r02_receipt_sha256"],
        PARENT_RAW: EXPECTED["parent_raw_sha256"],
        BASE_CONTEXT_FINAL: EXPECTED["base_context_final_sha256"],
        SCHEMA: EXPECTED["schema_sha256"],
        POLICY: EXPECTED["semantic_policy_sha256"],
        WO_SCORER: EXPECTED["wo_scorer_sha256"],
    }
    if {path: sha256(path) for path in post_paths} != post_paths:
        raise RuntimeError("POST_FREEZE_STATIC_INPUT_SHA_DRIFT")
    count, projection_sha = exact_base_read2_projection()
    if count != 24 or projection_sha != EXPECTED["base_read2_projection_sha256"]:
        raise RuntimeError("FROZEN_FULL_TARGET_PROJECTION_DRIFT")
    mappings = [json.loads(line) for line in mapping_bytes.decode().splitlines()]
    old_txx = {row["case_id"]: row for row in read_jsonl(OLD_TXX)}
    gold = {row["case_id"]: row for row in read_jsonl(GOLD)}
    contained = crossing = 0
    for case_id in STAGE_CASES:
        case_blocks = [row for row in mappings if row["parent_case_id"] == case_id]
        old_units = {unit["id"]: (unit["start"], unit["end"]) for unit in old_txx[case_id]["target_units"]}
        for fact in gold[case_id]["facts"]:
            start = min(old_units[unit][0] for unit in fact["evidence_ids"])
            end = max(old_units[unit][1] for unit in fact["evidence_ids"])
            owners = [row for row in case_blocks if row["original_target_start"] <= start and end <= row["original_target_end"]]
            if len(owners) == 1:
                contained += 1
            else:
                crossing += 1
    if (contained, crossing) != (77, 8):
        raise RuntimeError(f"STAGE1_GOLD_CONTAINMENT_DRIFT:{contained}:{crossing}")
    return {
        "mapping_sha256_frozen_before_gold_and_gold_derived_stats_read": sha256_bytes(mapping_bytes),
        "requests_sha256_frozen_before_gold_and_gold_derived_stats_read": sha256_bytes(request_bytes),
        "gold_and_gold_derived_stats_read_only_after_static_outputs_frozen": True,
        "gold_facts": 85,
        "contained_gold_facts": contained,
        "crossing_gold_facts": crossing,
        "base_read2_projection_sha256": projection_sha,
    }


def verify_static_outputs() -> dict[str, Any]:
    mapping_bytes, request_bytes = build_static_bytes()
    if not SOURCE_MAP.is_file() or SOURCE_MAP.read_bytes() != mapping_bytes:
        raise RuntimeError("SOURCE_MAP_DRIFT_OR_MISSING")
    if not REQUESTS.is_file() or REQUESTS.read_bytes() != request_bytes:
        raise RuntimeError("REQUESTS_DRIFT_OR_MISSING")
    spec = read_json(SPEC)
    expected_outputs = spec["generated_static_outputs"]
    actual_outputs = {
        "source_index_sha256": sha256_bytes(mapping_bytes),
        "requests_sha256": sha256_bytes(request_bytes),
    }
    if actual_outputs != expected_outputs:
        raise RuntimeError(f"SPEC_STATIC_OUTPUT_SHA_DRIFT:{actual_outputs}")
    audit = post_freeze_gold_audit(mapping_bytes, request_bytes)
    return {**actual_outputs, **audit, "requests": 22, "parent_cases": 8}


def build_static_outputs() -> None:
    if SOURCE_MAP.exists() or REQUESTS.exists():
        raise RuntimeError("STATIC_OUTPUT_EXISTS_NO_OVERWRITE")
    mapping_bytes, request_bytes = build_static_bytes()
    SOURCE_MAP.write_bytes(mapping_bytes)
    REQUESTS.write_bytes(request_bytes)
    audit = post_freeze_gold_audit(mapping_bytes, request_bytes)
    print(json.dumps({"status": "BUILT_STATIC_OUTPUTS", **audit}, ensure_ascii=False))


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
        if not member.is_file() or member.stat().st_size != row["bytes"] or sha256(member) != row["sha256"]:
            raise RuntimeError(f"MODEL_MEMBER_DRIFT:{row['path']}")
        total += row["bytes"]
    if total != MODEL_TOTAL_BYTES:
        raise RuntimeError("MODEL_TOTAL_BYTES_DRIFT")
    return {"member_count": len(files), "total_bytes": total, "revision": MODEL_REVISION}


def ticket_keys() -> set[str]:
    return {
        "schema_version", "approved", "authorized_by", "decision_id", "decision_text_sha256",
        "source_thread_id", "issued_at", "scope", "run_id", "run_root", "authorized_commands",
        "spec_sha256", "runner_sha256", "scorer_sha256", "prepare_receipt_sha256",
        "model_receipt_sha256", "source_map_sha256", "requests_sha256", *EXPECTED.keys(),
    }


def validate_ticket(path: Path) -> dict[str, Any]:
    ticket = read_json(path)
    if set(ticket) != ticket_keys():
        raise RuntimeError("TICKET_KEYS_DRIFT")
    static = verify_static_outputs()
    fixed = {
        "schema_version": "base-out2-block300-stage1-ticket/1.0",
        "approved": True,
        "scope": "BASE_OUT2_BLOCK300_STAGE1_SINGLE_22_INFERENCE",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-block300-stage1"],
        "spec_sha256": sha256(SPEC),
        "runner_sha256": sha256(Path(__file__)),
        "scorer_sha256": sha256(SCORER),
        "prepare_receipt_sha256": sha256(PREP_RECEIPT),
        "model_receipt_sha256": MODEL_RECEIPT_SHA,
        "source_map_sha256": static["source_index_sha256"],
        "requests_sha256": static["requests_sha256"],
        **EXPECTED,
    }
    for key, expected in fixed.items():
        if ticket.get(key) != expected:
            raise RuntimeError(f"TICKET_FIELD_DRIFT:{key}")
    for key in ("authorized_by", "decision_id", "decision_text_sha256", "source_thread_id", "issued_at"):
        if not isinstance(ticket.get(key), str) or not ticket[key]:
            raise RuntimeError(f"TICKET_AUTHORITY_MISSING:{key}")
    if RUN_ROOT.exists():
        raise RuntimeError(f"RUN_ROOT_EXISTS_NO_RETRY:{RUN_ROOT}")
    return ticket


def system_free_percent() -> int:
    import subprocess

    result = subprocess.run(["memory_pressure", "-Q"], text=True, capture_output=True, check=False)
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else -1


def infer(ticket_path: Path, validate_only: bool) -> None:
    validate_ticket(ticket_path)
    if validate_only:
        print(json.dumps({"status": "PASS_TICKET_VALIDATION", "run_root_exists": False}))
        return
    if sys.executable != str(PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = read_jsonl(REQUESTS)
    mappings = {row["request_id"]: row for row in read_jsonl(SOURCE_MAP)}
    RUN_ROOT.mkdir(parents=False)
    ticket_copy = RUN_ROOT / "AUTHORIZATION_TICKET.json"
    ticket_copy.write_bytes(ticket_path.read_bytes())
    ticket_sha = sha256(ticket_copy)
    write_json(RUN_ROOT / "RUN_IDENTITY.json", {
        "status": "AUTHORIZED_INFERENCE_STARTED", "run_id": RUN_ID, "created_at": now(),
        "ticket_sha256": ticket_sha, "spec_sha256": sha256(SPEC), "runner_sha256": sha256(Path(__file__)),
        "scorer_sha256": sha256(SCORER), "prepare_receipt_sha256": sha256(PREP_RECEIPT),
        "source_map_sha256": sha256(SOURCE_MAP), "requests_sha256": sha256(REQUESTS),
        "adapter_loaded": False, "retry": 0, "api_calls": 0,
    })
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
    sampler = make_sampler(temp=0.0)
    rows = []
    for index, request in enumerate(requests, 1):
        free = system_free_percent()
        if free >= 0 and free < 8:
            raise RuntimeError(f"MEMORY_HARD_STOP:{request['case_id']}:{free}")
        prompt = tokenizer.apply_chat_template(request["messages"], tokenize=False, add_generation_prompt=True)
        pieces = []
        final = None
        began = time.monotonic()
        for response in stream_generate(model, tokenizer, prompt=prompt, max_tokens=MAX_OUTPUT_TOKENS, sampler=sampler):
            pieces.append(response.text)
            final = response
        if final is None:
            raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{request['case_id']}")
        raw = "".join(pieces)
        mapping = mappings[request["case_id"]]
        rows.append({
            "variant": VARIANT, "case_id": mapping["parent_case_id"], "request_id": request["case_id"],
            "block_index": mapping["block_index"], "raw_output": raw, "finish_reason": final.finish_reason,
            "stop_token": int(final.token), "stop_token_is_eos_eot": int(final.token) in tokenizer.eos_token_ids,
            "generation_tokens_including_stop": int(final.generation_tokens),
            "output_tokens_excluding_stop": len(tokenizer.encode(raw, add_special_tokens=False)),
            "input_tokens": int(final.prompt_tokens), "elapsed_seconds": round(time.monotonic() - began, 3),
        })
        print(f"BLOCK300_STAGE1_PROGRESS {index}/22", flush=True)
    raw_path = RUN_ROOT / "inference/BLOCK300_STAGE1_RAW_22.jsonl"
    write_jsonl(raw_path, rows)
    write_json(RUN_ROOT / "inference/BLOCK300_STAGE1_RESULT.json", {
        "status": "PASS_BLOCK300_STAGE1_22_INFERENCE", "rows": 22, "raw_sha256": sha256(raw_path),
        "ticket_sha256": ticket_sha, "requests_sha256": sha256(REQUESTS), "source_map_sha256": sha256(SOURCE_MAP),
        "model_member_gates_before_each_load": [{"load_index": 1, "gate": model_gate}],
        "model_load_count": 1, "adapter_loaded": False, "retry": 0, "api_calls": 0,
        "spec_sha256": sha256(SPEC), "runner_sha256": sha256(Path(__file__)),
        "scorer_sha256": sha256(SCORER), "prepare_receipt_sha256": sha256(PREP_RECEIPT),
    })
    print(json.dumps({"status": "PASS_INFERENCE", "raw_sha256": sha256(raw_path)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-build", "static-check", "infer-block300-stage1"))
    parser.add_argument("--ticket", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.command == "static-build":
        if args.ticket or args.validate_only:
            raise RuntimeError("STATIC_BUILD_TAKES_NO_TICKET")
        build_static_outputs()
    elif args.command == "static-check":
        if args.ticket or args.validate_only:
            raise RuntimeError("STATIC_CHECK_TAKES_NO_TICKET")
        print(json.dumps({"status": "PASS_STATIC_CHECK", **verify_static_outputs()}))
    else:
        if args.ticket is None:
            raise RuntimeError("EXECUTION_TICKET_REQUIRED_BEFORE_RUN_ROOT_OR_MODEL_LOAD")
        infer(args.ticket, args.validate_only)


if __name__ == "__main__":
    main()
