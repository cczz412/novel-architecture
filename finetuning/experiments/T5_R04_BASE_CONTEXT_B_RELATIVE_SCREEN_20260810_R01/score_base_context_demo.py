#!/usr/bin/env python3
"""Mechanical gate and blind semantic ranking for the Base context Demo."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC = EXP / "SPEC.json"
RUNNER = EXP / "run_base_context_demo.py"
POLICY = EXP / "SEMANTIC_ADJUDICATION_POLICY.md"
RUN_ID = "T5_R04_BASE_CONTEXT_B_RELATIVE_SCREEN_R01"
RUN_ROOT = REPO / f"runs/{RUN_ID}"
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
BASE4_RAW = RUN_ROOT / "inference/BASE_READ4_RAW_24.jsonl"
BASE4_RESULT = RUN_ROOT / "inference/BASE_READ4_RESULT.json"
BASE4_REQUEST = RUN_ROOT / "requests/BASE_READ4_B_24.jsonl"
RUN_IDENTITY = RUN_ROOT / "RUN_IDENTITY.json"
EXECUTION_TICKET = RUN_ROOT / "AUTHORIZATION_TICKET.json"
EVAL_ROOT = REPO / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01"
EVAL_READ4 = EVAL_ROOT / "READ_4_FULL_CHAPTER_EVAL24.jsonl"
GOLD = EVAL_ROOT / "REAL24_GOLD_24.jsonl"
TXX = EVAL_ROOT / "REAL24_TXX_MAP.jsonl"
SCHEMA = (
    REPO
    / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/"
    "P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
)
MODEL = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/models/"
    "Qwen3-4B-Instruct-2507_cdbee75f"
)
MODEL_RECEIPT = MODEL / "MODEL_RECEIPT.json"
MODEL_RECEIPT_SHA = "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
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
EXPECTED = {
    "parent_spec_sha256": "ff4ae3e702a318d3d47a0476d1cbbc18078884735e14176d1f9171b07232cd06",
    "parent_raw_sha256": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "parent_result_sha256": "a8b3276179551aaa3b7e42c274c0a7c5327846171be58c02ff0d38de778340b9",
    "parent_metrics_sha256": "583d89053ed5662b516206579782338994afeca3580a25e39cc98c1781692d57",
    "read1_actual_request_sha256": "72622224236853a70b0ea1ddfcc85ead2e4319a9ec97ee54226be2113f28b022",
    "read2_actual_request_sha256": "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    "eval_read4_sha256": "350799084dbc15791bc3b46a669552aec2da7920bfa39c8a3a110e1cbe431d4f",
    "read4_b_requests_sha256": "b917c8253c78671435e735c18afa0365717507736da4be28e5c2b81eb55387c2",
    "base_read1_projection_sha256": "21de7f972b892796fedc5fb8f6a4ad9c79223b7804a492a4f6dc9fa3ecdb564f",
    "base_read2_projection_sha256": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "gold_sha256": "234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4",
    "txx_sha256": "9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a",
    "schema_sha256": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "wo_scorer_sha256": "eed88ee3c02eb9963cc10f67c06f343415d3a3aed27dd6a71f79e420ccea9d1c",
    "read2_r02_sha256": "03eb97a774ac41599d6f897e64486cec37d0a237b073f0ab621039733d599636",
    "read2_final_sha256": "524f8bcceb37aea95a6cf1ac7445580353360fdfd6de525982a216efa49ec96f",
    "semantic_policy_sha256": "73083a1d91edcc8fadabd2342fc59b89e10ef770aeaa6ffe926867f4f4c39a93",
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
VARIANTS = ("BASE_READ1", "BASE_READ2", "BASE_READ4")
ARM_ORDER = {"READ1": 1, "READ2": 2, "READ4": 4}
MAX_OUTPUT_TOKENS = 2048
CONTRACT = (
    "【输出合同】输出必须是且只能是一个顶层键为 facts 的 JSON 对象；facts 为数组且允许为空，"
    "每个元素只能且必须包含 fact、status、speaker、evidence_ids，fact 为非空字符串，"
    "speaker 为字符串或 null，evidence_ids 为字符串数组，status 只能取“已发生”“正在发生”"
    "“计划”“承诺”“条件”“推测”“误信”“否定”之一；不得输出其他字段、Markdown 或解释。"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fact_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{path}")
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def exact_projection(variant: str) -> tuple[list[dict[str, Any]], bytes]:
    selected = []
    rows = []
    for line in PARENT_RAW.read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        if row.get("variant") == variant:
            selected.append(line)
            rows.append(row)
    return rows, b"".join(selected)


def verify_cross_arm_request_identity() -> dict[str, Any]:
    requests = {
        "READ1": read_jsonl(PARENT_REQUESTS["READ1"]),
        "READ2": read_jsonl(PARENT_REQUESTS["READ2"]),
        "READ4": read_jsonl(BASE4_REQUEST),
    }
    expected_cases = [f"C{index:02d}" for index in range(1, 25)]
    marker = "\n\n【编号负责区：只抽这里】"
    header = "【只读范围：只帮助理解，不得作为新增事实或证据】\n"
    for arm, rows in requests.items():
        if len(rows) != 24 or [row.get("case_id") for row in rows] != expected_cases:
            raise RuntimeError(f"REQUEST_CASE_ORDER_DRIFT:{arm}")
    for index in range(24):
        messages = [requests[arm][index].get("messages") for arm in ("READ1", "READ2", "READ4")]
        if any([item.get("role") for item in value] != ["system", "user"] for value in messages):
            raise RuntimeError(f"REQUEST_MESSAGE_SHAPE_DRIFT:{index}")
        systems = [value[0]["content"] for value in messages]
        if len(set(systems)) != 1 or not systems[0].endswith("\n" + CONTRACT):
            raise RuntimeError(f"REQUEST_SYSTEM_OR_B_CONTRACT_DRIFT:{index}")
        scopes = []
        tails = []
        for value in messages:
            user = value[1]["content"]
            if user.count(marker) != 1 or not user.startswith(header):
                raise RuntimeError(f"REQUEST_USER_SHAPE_DRIFT:{index}")
            front, tail = user.split(marker, 1)
            scopes.append(front[len(header) :])
            tails.append(marker + tail)
        if len(set(tails)) != 1:
            raise RuntimeError(f"REQUEST_FOCUS_OR_ALLOWLIST_DRIFT:{index}")
        if len(set(scopes)) != 3:
            raise RuntimeError(f"REQUEST_READ_SCOPE_NOT_DISTINCT:{index}")
    return {
        "rows_per_arm": 24,
        "system_with_format_b_equal": True,
        "focus_and_allowlist_tail_equal": True,
        "only_read_scope_text_differs": True,
    }


def verify_sources() -> dict[str, str]:
    actual = {
        "parent_spec_sha256": sha256(PARENT_SPEC),
        "parent_raw_sha256": sha256(PARENT_RAW),
        "parent_result_sha256": sha256(PARENT_RESULT),
        "parent_metrics_sha256": sha256(PARENT_METRICS),
        "read1_actual_request_sha256": sha256(PARENT_REQUESTS["READ1"]),
        "read2_actual_request_sha256": sha256(PARENT_REQUESTS["READ2"]),
        "eval_read4_sha256": sha256(EVAL_READ4),
        "read4_b_requests_sha256": sha256(BASE4_REQUEST),
        "gold_sha256": sha256(GOLD),
        "txx_sha256": sha256(TXX),
        "schema_sha256": sha256(SCHEMA),
        "wo_scorer_sha256": sha256(WO_SCORER),
        "read2_r02_sha256": sha256(READ2_R02),
        "read2_final_sha256": sha256(READ2_FINAL),
        "semantic_policy_sha256": sha256(POLICY),
    }
    for variant, key in (
        ("BASE_READ1", "base_read1_projection_sha256"),
        ("BASE_READ2", "base_read2_projection_sha256"),
    ):
        rows, data = exact_projection(variant)
        if len(rows) != 24:
            raise RuntimeError(f"PROJECTION_ROWS_DRIFT:{variant}")
        actual[key] = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED:
        raise RuntimeError(f"SCORER_INPUT_SHA_DRIFT:{actual}")
    verify_cross_arm_request_identity()
    parent_metrics = read_json(PARENT_METRICS)
    known = parent_metrics.get("mechanical_variants", {})
    if known.get("BASE_READ1", {}).get("schema_cases") != 23:
        raise RuntimeError("KNOWN_BASE_READ1_SCHEMA_DRIFT")
    if known.get("BASE_READ2", {}).get("schema_cases") != 22:
        raise RuntimeError("KNOWN_BASE_READ2_SCHEMA_DRIFT")
    return actual


def verify_execution_identity(base4_raw_sha: str) -> dict[str, Any]:
    for path in (EXECUTION_TICKET, RUN_IDENTITY, BASE4_RESULT, BASE4_REQUEST):
        if not path.is_file():
            raise RuntimeError(f"EXECUTION_IDENTITY_MEMBER_MISSING:{path}")
    ticket_sha = sha256(EXECUTION_TICKET)
    ticket = read_json(EXECUTION_TICKET)
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("EXECUTION_TICKET_KEYS_DRIFT")
    identity = read_json(RUN_IDENTITY)
    result = read_json(BASE4_RESULT)
    current = {
        "spec_sha256": sha256(SPEC),
        "runner_sha256": sha256(RUNNER),
        "scorer_sha256": sha256(Path(__file__)),
        "model_receipt_sha256": sha256(MODEL_RECEIPT),
    }
    if current["model_receipt_sha256"] != MODEL_RECEIPT_SHA:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    model_receipt = read_json(MODEL_RECEIPT)
    if model_receipt.get("revision") != MODEL_REVISION:
        raise RuntimeError("MODEL_RECEIPT_REVISION_DRIFT")
    ticket_fixed = {
        "schema_version": "base-context-b-relative-screen-ticket/1.0",
        "approved": True,
        "scope": "BASE_CONTEXT_B_RELATIVE_SCREEN_SINGLE_READ4_INFERENCE",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-base-read4"],
        **current,
        **EXPECTED,
    }
    for key, expected in ticket_fixed.items():
        if ticket.get(key) != expected:
            raise RuntimeError(f"EXECUTION_TICKET_FIELD_DRIFT:{key}")
    for key in ("authorized_by", "decision_id", "decision_text_sha256", "source_thread_id", "issued_at"):
        if not isinstance(ticket.get(key), str) or not ticket[key]:
            raise RuntimeError(f"EXECUTION_TICKET_AUTHORITY_MISSING:{key}")
    identity_fixed = {
        "status": "AUTHORIZED_INFERENCE_STARTED",
        "run_id": RUN_ID,
        "ticket_sha256": ticket_sha,
        "ticket_copy_sha256": ticket_sha,
        "spec_sha256": current["spec_sha256"],
        "runner_sha256": current["runner_sha256"],
        "scorer_sha256": current["scorer_sha256"],
        "authorized_commands": ["infer-base-read4"],
        "model_receipt_sha256": MODEL_RECEIPT_SHA,
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
    }
    for key, expected in identity_fixed.items():
        if identity.get(key) != expected:
            raise RuntimeError(f"RUN_IDENTITY_FIELD_DRIFT:{key}")
    result_fixed = {
        "status": "PASS_BASE_READ4_24_INFERENCE",
        "run_id": RUN_ID,
        "rows": 24,
        "raw_sha256": base4_raw_sha,
        "request_sha256": EXPECTED["read4_b_requests_sha256"],
        "ticket_sha256": ticket_sha,
        "ticket_copy_sha256": ticket_sha,
        "spec_sha256": current["spec_sha256"],
        "runner_sha256": current["runner_sha256"],
        "scorer_sha256": current["scorer_sha256"],
        "model_receipt_sha256": MODEL_RECEIPT_SHA,
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
    }
    for key, expected in result_fixed.items():
        if result.get(key) != expected:
            raise RuntimeError(f"BASE4_RESULT_FIELD_DRIFT:{key}")
    gates = result.get("model_member_gates_before_each_load")
    expected_gate = [
        {
            "variant": "BASE_READ4",
            "arm": "READ4",
            "gate": {
                "member_count": 13,
                "total_bytes": 8_060_917_568,
                "revision": MODEL_REVISION,
            },
        }
    ]
    if gates != expected_gate:
        raise RuntimeError("BASE4_MODEL_MEMBER_GATE_DRIFT")
    return {
        "ticket_sha256": ticket_sha,
        **current,
        "model_member_gate": expected_gate[0],
        "adapter_loaded": False,
        "retry": 0,
        "api_calls": 0,
        "cross_arm_request_identity": verify_cross_arm_request_identity(),
    }


def load_wo() -> Any:
    spec = importlib.util.spec_from_file_location("base_context_wo", WO_SCORER)
    if spec is None or spec.loader is None:
        raise RuntimeError("WO_SCORER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repeated_chunk(raw: str) -> bool:
    compact = re.sub(r"\s+", "", raw)
    if len(compact) < 240:
        return False
    chunks = Counter(compact[index : index + 80] for index in range(0, len(compact) - 79, 8))
    return any(count >= 3 for count in chunks.values())


def parse_facts(raw: str, validator: Draft202012Validator) -> tuple[bool, bool, list[dict[str, Any]]]:
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError:
        value = None
    json_valid = isinstance(value, dict)
    schema_valid = json_valid and not list(validator.iter_errors(value))
    if json_valid and isinstance(value.get("facts"), list):
        facts = [
            item
            for item in value["facts"]
            if isinstance(item, dict) and isinstance(item.get("fact"), str) and item["fact"]
        ]
        return True, schema_valid, facts
    decoder = json.JSONDecoder()
    recovered = []
    for start, character in enumerate(raw):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("fact"), str) and candidate["fact"]:
            recovered.append(candidate)
    return json_valid, schema_valid, recovered


def gold_map() -> dict[str, list[dict[str, Any]]]:
    result = {}
    rows = read_jsonl(GOLD)
    if [row.get("case_id") for row in rows] != [f"C{i:02d}" for i in range(1, 25)]:
        raise RuntimeError("GOLD_CASE_ORDER_DRIFT")
    for row in rows:
        result[row["case_id"]] = [
            {
                "fact_id": f"{row['case_id']}-F{index:03d}",
                "fact": fact["fact_sentence"],
                "status": fact["status"],
                "speaker": fact["speaker"],
                "evidence_ids": fact["evidence_ids"],
            }
            for index, fact in enumerate(row["facts"], 1)
        ]
    return result


def target_ids() -> dict[str, set[str]]:
    return {
        row["case_id"]: {unit["id"] for unit in row["target_units"]}
        for row in read_jsonl(TXX)
    }


def source_rows() -> tuple[list[dict[str, Any]], str, str, dict[str, Any]]:
    if not BASE4_RAW.is_file() or not BASE4_RESULT.is_file():
        raise RuntimeError("BASE_READ4_INFERENCE_OUTPUT_MISSING")
    verify_sources()
    base4_sha = sha256(BASE4_RAW)
    execution_identity = verify_execution_identity(base4_sha)
    base4_result = read_json(BASE4_RESULT)
    if base4_result.get("raw_sha256") != base4_sha:
        raise RuntimeError("BASE_READ4_RESULT_RAW_SHA_DRIFT")
    read1, read1_bytes = exact_projection("BASE_READ1")
    read2, read2_bytes = exact_projection("BASE_READ2")
    read4 = read_jsonl(BASE4_RAW)
    if Counter(row.get("variant") for row in read4) != Counter({"BASE_READ4": 24}):
        raise RuntimeError("BASE_READ4_VARIANT_ROWS_DRIFT")
    rows = read1 + read2 + read4
    for variant in VARIANTS:
        current = [row for row in rows if row.get("variant") == variant]
        if [row.get("case_id") for row in current] != [f"C{i:02d}" for i in range(1, 25)]:
            raise RuntimeError(f"CASE_ORDER_DRIFT:{variant}")
    bundle = read1_bytes + read2_bytes + BASE4_RAW.read_bytes()
    return rows, hashlib.sha256(bundle).hexdigest(), base4_sha, execution_identity


def mechanical_case(
    row: dict[str, Any], validator: Draft202012Validator, valid_ids: dict[str, set[str]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    json_valid, schema_valid, facts = parse_facts(row["raw_output"], validator)
    duplicates = sum(
        count - 1 for count in Counter(item.get("fact") for item in facts).values() if count > 1
    )
    illegal = sum(
        not isinstance(item.get("evidence_ids"), list)
        or any(value not in valid_ids[row["case_id"]] for value in item.get("evidence_ids", []))
        for item in facts
    )
    return (
        {
            "case_id": row["case_id"],
            "predictions": len(facts),
            "json_valid": json_valid,
            "schema_valid": schema_valid,
            "illegal_evidence_predictions": illegal,
            "duplicate_predictions": duplicates,
            "repetition_detected": duplicates > 0 or repeated_chunk(row["raw_output"]),
            "token_limit_hit": row.get("finish_reason") == "length"
            or row.get("generation_tokens_including_stop", 0) >= MAX_OUTPUT_TOKENS,
        },
        facts,
    )


def mechanical_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "cases": len(rows),
        "strict_json_cases": sum(row["json_valid"] for row in rows),
        "schema_cases": sum(row["schema_valid"] for row in rows),
        "illegal_evidence_predictions": sum(row["illegal_evidence_predictions"] for row in rows),
        "repetition_cases": sum(row["repetition_detected"] for row in rows),
        "token_limit_cases": sum(row["token_limit_hit"] for row in rows),
        "duplicate_predictions": sum(row["duplicate_predictions"] for row in rows),
    }
    result["mechanically_eligible"] = (
        result["cases"] == 24
        and result["strict_json_cases"] == 24
        and result["illegal_evidence_predictions"] == 0
        and result["repetition_cases"] == 0
        and result["token_limit_cases"] == 0
        and result["duplicate_predictions"] == 0
    )
    result["schema_is_reported_not_a_hard_gate"] = True
    return result


def frozen_read2_decisions() -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for row in read_jsonl(READ2_R02):
        if row.get("raw_sha256") != EXPECTED["parent_raw_sha256"]:
            raise RuntimeError("R02_ADJUDICATION_RAW_SHA_DRIFT")
        if row.get("gold_sha256") != EXPECTED["gold_sha256"]:
            raise RuntimeError("R02_ADJUDICATION_GOLD_SHA_DRIFT")
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or fact_sha(row.get("prediction_fact", "")) != key[1]:
            raise RuntimeError("R02_ADJUDICATION_KEY_DRIFT")
        if row.get("category") not in {"SEMANTIC_EQUIVALENT", "NOT_MATCH", "OUT_OF_SCOPE"}:
            raise RuntimeError("R02_ADJUDICATION_CATEGORY_DRIFT")
        result[key] = row
    if len(result) != 381:
        raise RuntimeError("R02_ADJUDICATION_ROWS_DRIFT")
    return result


def new_decisions(path: Path | None, queue: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    rows = read_jsonl(path)
    expected_by_key = {(row["case_id"], row["prediction_fact_sha256"]): row for row in queue}
    result = {}
    for row in rows:
        key = (row.get("case_id"), row.get("prediction_fact_sha256"))
        if key in result or key not in expected_by_key:
            raise RuntimeError("NEW_ADJUDICATION_DUPLICATE_OR_UNKNOWN_KEY")
        expected = expected_by_key[key]
        for field in (
            "case_id",
            "prediction_fact",
            "prediction_fact_sha256",
            "input_bundle_sha256",
            "base_read4_raw_sha256",
            "gold_sha256",
            "semantic_policy_sha256",
            "candidate_gold_facts",
        ):
            if row.get(field) != expected.get(field):
                raise RuntimeError(f"NEW_ADJUDICATION_IDENTITY_DRIFT:{field}")
        if row.get("category") not in {"SEMANTIC_EQUIVALENT", "NOT_MATCH", "OUT_OF_SCOPE"}:
            raise RuntimeError("NEW_ADJUDICATION_CATEGORY_INVALID")
        matched = row.get("matched_gold_fact_id")
        if row["category"] == "SEMANTIC_EQUIVALENT":
            valid = {item["fact_id"] for item in row["candidate_gold_facts"]}
            if matched not in valid:
                raise RuntimeError("NEW_ADJUDICATION_MATCHED_ID_INVALID")
        elif matched is not None:
            raise RuntimeError("NEW_ADJUDICATION_NONMATCH_MUST_HAVE_NULL")
        result[key] = row
    if set(result) != set(expected_by_key):
        raise RuntimeError("NEW_ADJUDICATION_COVERAGE_INCOMPLETE")
    return result


def semantic_pass(
    rows: list[dict[str, Any]],
    parsed: dict[tuple[str, str], list[dict[str, Any]]],
    eligible: list[str],
    input_bundle_sha: str,
    base4_raw_sha: str,
    added: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    wo = load_wo()
    gold = gold_map()
    frozen = frozen_read2_decisions()
    pending: dict[tuple[str, str], dict[str, Any]] = {}
    cases = []
    for variant in eligible:
        for row in (item for item in rows if item["variant"] == variant):
            case_id = row["case_id"]
            predictions = parsed[(variant, case_id)]
            expected = gold[case_id]
            pairs, unmatched = wo.match(expected, predictions, normalized=True)
            used_gold = {gold_index for _, gold_index in pairs}
            for prediction_index in unmatched:
                text = predictions[prediction_index].get("fact", "")
                key = (case_id, fact_sha(text))
                decision = frozen.get(key) or added.get(key)
                if decision is None:
                    pending.setdefault(
                        key,
                        {
                            "case_id": case_id,
                            "prediction_fact": text,
                            "prediction_fact_sha256": key[1],
                            "input_bundle_sha256": input_bundle_sha,
                            "base_read4_raw_sha256": base4_raw_sha,
                            "gold_sha256": EXPECTED["gold_sha256"],
                            "semantic_policy_sha256": EXPECTED["semantic_policy_sha256"],
                            "candidate_gold_facts": [
                                {"fact_id": item["fact_id"], "fact": item["fact"]} for item in expected
                            ],
                            "category": None,
                            "matched_gold_fact_id": None,
                        },
                    )
                    continue
                if decision["category"] != "SEMANTIC_EQUIVALENT":
                    continue
                matched_id = decision.get("matched_gold_fact_id")
                gold_index = next(
                    (index for index, item in enumerate(expected) if item["fact_id"] == matched_id), None
                )
                if gold_index is None:
                    raise RuntimeError("DECISION_MATCHED_GOLD_ID_INVALID")
                if gold_index not in used_gold:
                    pairs.append((prediction_index, gold_index))
                    used_gold.add(gold_index)
            status_ok = speaker_ok = evidence_ok = 0
            for prediction_index, gold_index in pairs:
                prediction = predictions[prediction_index]
                target = expected[gold_index]
                status_ok += prediction.get("status") == target["status"]
                speaker_ok += prediction.get("speaker") == target["speaker"]
                evidence_ok += prediction.get("evidence_ids") == target["evidence_ids"]
            cases.append(
                {
                    "variant": variant,
                    "case_id": case_id,
                    "gold": len(expected),
                    "predictions": len(predictions),
                    "semantic_tp": len(pairs),
                    "status_correct": status_ok,
                    "speaker_correct": speaker_ok,
                    "evidence_correct": evidence_ok,
                }
            )
    variants = {}
    for variant in eligible:
        group = [row for row in cases if row["variant"] == variant]
        tp = sum(row["semantic_tp"] for row in group)
        predictions = sum(row["predictions"] for row in group)
        gold_count = sum(row["gold"] for row in group)
        variants[variant] = {
            "semantic_recoverable": wo.prf(tp, predictions - tp, gold_count - tp),
            "semantic_tp": tp,
            "predictions": predictions,
            "gold": gold_count,
            "status_correct": sum(row["status_correct"] for row in group),
            "speaker_correct": sum(row["speaker_correct"] for row in group),
            "evidence_correct": sum(row["evidence_correct"] for row in group),
        }
    return {"variants": variants, "case_metrics": cases}, list(pending.values())


def score(adjudications: Path | None, final: bool) -> None:
    rows, bundle_sha, base4_sha, execution_identity = source_rows()
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    valid_ids = target_ids()
    parsed = {}
    summaries = {}
    case_metrics = []
    for variant in VARIANTS:
        current = []
        for row in (item for item in rows if item["variant"] == variant):
            metrics, facts = mechanical_case(row, validator, valid_ids)
            current.append(metrics)
            parsed[(variant, row["case_id"])] = facts
        summaries[variant] = mechanical_summary(current)
        case_metrics.extend({"variant": variant, **item} for item in current)
    eligible = [variant for variant in VARIANTS if summaries[variant]["mechanically_eligible"]]
    if not final:
        added = {}
    else:
        pre_metrics = read_json(RUN_ROOT / "scoring/pre/METRICS.json")
        if pre_metrics.get("input_bundle_sha256") != bundle_sha:
            raise RuntimeError("FINAL_INPUT_BUNDLE_SHA_DRIFT")
        if pre_metrics.get("base_read4_raw_sha256") != base4_sha:
            raise RuntimeError("FINAL_BASE_READ4_RAW_SHA_DRIFT")
        if pre_metrics.get("execution_identity", {}).get("ticket_sha256") != execution_identity[
            "ticket_sha256"
        ]:
            raise RuntimeError("FINAL_EXECUTION_TICKET_SHA_DRIFT")
        queue = read_jsonl(RUN_ROOT / "scoring/pre/BLIND_QUEUE.jsonl")
        if adjudications is None:
            raise RuntimeError("FINAL_REQUIRES_ADJUDICATIONS")
        added = new_decisions(adjudications, queue)
    semantic, pending = semantic_pass(rows, parsed, eligible, bundle_sha, base4_sha, added)
    if final and pending:
        raise RuntimeError(f"SEMANTIC_PENDING_NOT_ZERO:{len(pending)}")
    status = "PENDING_BLIND_SEMANTIC_REVIEW"
    selection = None
    if len(eligible) < 2:
        status = "FAIL_FEWER_THAN_TWO_MECHANICALLY_ELIGIBLE_ARMS"
        pending = []
    elif final:
        scores = {
            variant: semantic["variants"][variant]["semantic_recoverable"]["f1"] for variant in eligible
        }
        ranked = sorted(
            scores,
            key=lambda value: (-scores[value], ARM_ORDER[value.removeprefix("BASE_")]),
        )
        top = ranked[0]
        tie_group = [value for value in ranked if scores[top] - scores[value] < 0.02]
        if len(tie_group) > 1:
            max_schema = max(summaries[value]["schema_cases"] for value in tie_group)
            finalists = [
                value for value in tie_group if summaries[value]["schema_cases"] == max_schema
            ]
            chosen = min(finalists, key=lambda value: ARM_ORDER[value.removeprefix("BASE_")])
            verdict = "APPROXIMATE_TIE_SCHEMA_THEN_SHORTER_CONTEXT"
        else:
            chosen = top
            verdict = "HIGHEST_RECOVERABLE_SEMANTIC_F1"
        selection = {
            "verdict": verdict,
            "selected_arm": chosen.removeprefix("BASE_"),
            "f1_by_variant": scores,
            "approximate_tie_variants": tie_group,
            "tie_threshold_strictly_below": 0.02,
            "not_a_trained_read_winner": True,
            "does_not_authorize_out": True,
        }
        status = "PASS_BASE_CONTEXT_DEMO_SELECTION_COMPLETE"
    output_dir = RUN_ROOT / ("scoring/final" if final else "scoring/pre")
    if output_dir.exists():
        raise RuntimeError(f"OUTPUT_DIR_EXISTS_NO_OVERWRITE:{output_dir}")
    output_dir.mkdir(parents=True)
    result = {
        "status": status,
        "scope_name_zh": "未微调4B+B合同的本机 Base context Demo 选择",
        "input_bundle_sha256": bundle_sha,
        "base_read4_raw_sha256": base4_sha,
        "execution_identity": execution_identity,
        "gold_sha256": EXPECTED["gold_sha256"],
        "eligible_variants": eligible,
        "mechanical_variants": summaries,
        "mechanical_case_metrics": case_metrics,
        "semantic_pending": len(pending),
        "semantic": semantic,
        "selection": selection,
        "schema_is_reported_and_used_only_as_tiebreak": True,
        "read2_r02_identical_case_fact_decisions_reused": True,
        "old_trained_read_global_fail_unchanged": "FAIL_FULL24_LORA_FORMAT_GATE",
        "api_calls": 0,
    }
    write_json(output_dir / "METRICS.json", result)
    write_jsonl(output_dir / "BLIND_QUEUE.jsonl", pending)
    print(json.dumps({"status": status, "eligible": eligible, "semantic_pending": len(pending)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("pre", "final"))
    parser.add_argument("--adjudications", type=Path)
    args = parser.parse_args()
    score(args.adjudications, args.command == "final")


if __name__ == "__main__":
    main()
