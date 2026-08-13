#!/usr/bin/env python3
"""Ticket-bound local Base inference for the single EX contrastive-pair arm."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

from jsonschema import Draft202012Validator


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parent
SPEC = EXP / "SPEC.json"
PAIR = EXP / "FIXED_CONTRASTIVE_PAIR.json"
SCORER = EXP / "score_ex_prompt_screen.py"
PREP_RECEIPT = EXP / "PREPARE_RECEIPT.json"
RULE_EXP = REPO / "finetuning/experiments/T5_R04_BASE_H180_OUT2_FULL_TARGET_RULE_SCREEN_20260810_R01"
RULE_RUNNER_PATH = RULE_EXP / "run_rule_prompt_screen.py"
RULE_SCORER_PATH = RULE_EXP / "score_rule_prompt_screen.py"
RULE_RUNNER_SPEC = importlib.util.spec_from_file_location("stable_rule_runner", RULE_RUNNER_PATH)
if RULE_RUNNER_SPEC is None or RULE_RUNNER_SPEC.loader is None:
    raise RuntimeError("STABLE_RULE_RUNNER_IMPORT_FAILED")
stable = importlib.util.module_from_spec(RULE_RUNNER_SPEC)
RULE_RUNNER_SPEC.loader.exec_module(stable)

RUN_ID = "T5_R04_BASE_H180_OUT2_FULL_TARGET_EX_CONTRASTIVE_SCREEN_R01"
RUN_ROOT = REPO / f"runs/{RUN_ID}"
VARIANT = "EX-1-CONTRASTIVE-PAIR"
REQUEST_SHA = "298854c2567e6842f2de774ffdc0e8a7d3cc0b6bcc1a6e187675c05648b77238"
RULE_RUN = REPO / "runs/T5_R04_BASE_H180_OUT2_FULL_TARGET_RULE_SCREEN_R01"
RULE_FINAL_METRICS = RULE_RUN / "scoring/final/METRICS.json"
RULE_FINAL_RECEIPT = RULE_RUN / "scoring/final/FINAL_RECEIPT.json"
RULE_FINAL_QUEUE = RULE_RUN / "scoring/final/BLIND_QUEUE.jsonl"
RULE_R02_ADJUDICATIONS = (
    REPO / "TEMP/rule_prompt_adjudication_20260810/SEMANTIC_ADJUDICATIONS_478_R02.jsonl"
)
RULE_R02_RECEIPT = REPO / "TEMP/rule_prompt_adjudication_20260810/ADJUDICATION_R02_RECEIPT.json"
R10 = REPO / "finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R10"
FORBIDDEN_COPY_TERMS = (
    "周棠",
    "俞安",
    "防水布",
    "备用电池",
    "码头货架",
    "签收单",
)
EXPECTED = {
    "r10_readme_sha256": "039c67d025da3aecd4cea69b87fdf7c64dc32ced6b6325b3e539af83a7b8464e",
    "r10_registry_sha256": "410c2489d6d031a2c82f05842b28f53fe5bc414a686cdefdbc0cdbe274de122a",
    "r10_result_ticket_sha256": "187a53f863bccb2456c4f42e507b1749faf14350187075bbdc8d6b0bd356744e",
    "fixed_pair_sha256": "aec37c720b2791fa8902fe4bcb31f6389e7a94d5327fac524337b52dd3d8f0c1",
    "stable_rule_runner_sha256": "e4bee2a100a4962a28bcadd6b3efde5c24ae2b87f8c980c2057caafd28292867",
    "stable_rule_scorer_sha256": "8f9bf1fff5718875316886f13937073753daab4532610602e34b69a96e84df84",
    "base_request_sha256": "126b0f0843fdd244f007a46361397f24f97ce8d71c73d760ae9ad5a6bf5b3088",
    "parent_raw_sha256": "f9bd1fc02f93cfb7c51193f1dc319753472949bc2bbde4360a6779c415cdb28e",
    "base_projection_sha256": "c7f738181148acc4c06644e47058606b35f07b9a0603521ffdb98502267b1b97",
    "rule_final_metrics_sha256": "699b06cb21b85b61304b35a226cb0169895d0e145f7ee71e0dd3ffa98bb1835b",
    "rule_final_receipt_sha256": "ed39dcdca3eeb08ca2925fe89dd1372bb356a1c181bf1d64155e7b93fd25fbd9",
    "rule_final_empty_queue_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "rule_r02_adjudications_sha256": "3a094afabe1bceb2cafa11e9de8565bdba8b73e646fb50c343a7c9b7895968e1",
    "rule_r02_receipt_sha256": "2cd863699e47f4a25959f2f0cfb2560e8d95df890382dc618e1a736ac2884cae",
    "base_context_decisions_sha256": stable.EXPECTED["base_context_decisions_sha256"],
    "read2_r02_sha256": stable.EXPECTED["read2_r02_sha256"],
    "gold_sha256": stable.EXPECTED["gold_sha256"],
    "txx_sha256": stable.EXPECTED["txx_sha256"],
    "schema_sha256": stable.EXPECTED["schema_sha256"],
    "semantic_policy_sha256": stable.EXPECTED["semantic_policy_sha256"],
    "wo_scorer_sha256": stable.EXPECTED["wo_scorer_sha256"],
    "ex1_request_sha256": REQUEST_SHA,
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
    return stable.sha256(path)


def text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return stable.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return stable.read_jsonl(path)


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return stable.jsonl_bytes(rows)


def write_json(path: Path, value: Any) -> None:
    stable.write_json(path, value)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    stable.write_jsonl(path, rows)


def pair_payload_sha(members: list[dict[str, Any]]) -> str:
    parts: list[bytes] = []
    for member in members:
        parts.extend(
            [
                member["member_id"].encode("utf-8"),
                member["user"].encode("utf-8"),
                member["assistant"].encode("utf-8"),
            ]
        )
    return hashlib.sha256(b"EXPAIR-V1\0" + b"\0".join(parts)).hexdigest()


def responsibility_units(user: str) -> dict[str, str]:
    units = {}
    for line in user.splitlines():
        match = re.fullmatch(r"\[(T\d+)\](.+)", line.strip())
        if match:
            units[match.group(1)] = match.group(2)
    return units


def validate_pair() -> dict[str, Any]:
    pair = read_json(PAIR)
    members = pair.get("members")
    if (
        pair.get("status") != "PROJECT_ORIGINAL_SYNTHETIC_EXAMPLE_CANDIDATE"
        or pair.get("forbidden_from_training") is not True
        or pair.get("member_order") != ["A", "B"]
        or not isinstance(members, list)
        or [item.get("member_id") for item in members] != ["A", "B"]
    ):
        raise RuntimeError("FIXED_PAIR_IDENTITY_OR_ORDER_DRIFT")
    schema = json.loads(stable.SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    field_hashes = {}
    responsibility_lengths = {}
    fact_density_per_100_unicode = {}
    neutral_carriers = {}
    for member in members:
        for field in ("user", "assistant"):
            value = member.get(field)
            if (
                not isinstance(value, str)
                or not value
                or value.startswith("\n")
                or value.endswith("\n")
                or "\r" in value
            ):
                raise RuntimeError(f"PAIR_FIELD_ENCODING_OR_BLANK_DRIFT:{member['member_id']}:{field}")
            digest = text_sha(value)
            if digest != member.get(f"{field}_sha256"):
                raise RuntimeError(f"PAIR_FIELD_SHA_DRIFT:{member['member_id']}:{field}")
            field_hashes[f"{member['member_id']}_{field}_sha256"] = digest
        answer = json.loads(member["assistant"])
        if list(validator.iter_errors(answer)) or len(answer.get("facts", [])) != 5:
            raise RuntimeError(f"PAIR_ASSISTANT_SCHEMA_OR_FACT_COUNT_DRIFT:{member['member_id']}")
        facts = answer["facts"]
        if sum(item["evidence_ids"] == ["T01"] for item in facts) != 2:
            raise RuntimeError(f"PAIR_T01_FACT_COUNT_DRIFT:{member['member_id']}")
        if any(
            evidence_id in {"T05", "T06", "T07", "T08"}
            for item in facts
            for evidence_id in item["evidence_ids"]
        ):
            raise RuntimeError(f"PAIR_T05_T08_MUST_HAVE_ZERO_FACTS:{member['member_id']}")
        units = responsibility_units(member["user"])
        if list(units) != [f"T{index:02d}" for index in range(1, 9)]:
            raise RuntimeError(f"PAIR_RESPONSIBILITY_UNIT_ORDER_DRIFT:{member['member_id']}")
        responsibility_length = len("".join(units.values()))
        expected_length = {"A": 311, "B": 321}[member["member_id"]]
        if responsibility_length != expected_length:
            raise RuntimeError(f"PAIR_RESPONSIBILITY_LENGTH_DRIFT:{member['member_id']}")
        responsibility_lengths[member["member_id"]] = responsibility_length
        fact_density_per_100_unicode[member["member_id"]] = round(
            len(facts) * 100 / responsibility_length, 6
        )
        neutral_carriers[member["member_id"]] = "".join(
            units[f"T{index:02d}"] for index in range(6, 9)
        )
    if neutral_carriers["A"] != neutral_carriers["B"] or len(neutral_carriers["A"]) != 165:
        raise RuntimeError("PAIR_T06_T08_SHARED_NEUTRAL_CARRIER_DRIFT")
    payload_sha = pair_payload_sha(members)
    if payload_sha != pair.get("pair_payload_sha256"):
        raise RuntimeError("PAIR_PAYLOAD_SHA_DRIFT")
    return {
        "members": 2,
        "member_order": ["A", "B"],
        "assistant_schema_valid": 2,
        "facts_per_member": {"A": 5, "B": 5},
        "t01_facts_per_member": {"A": 2, "B": 2},
        "t05_t08_facts_per_member": {"A": 0, "B": 0},
        "responsibility_unicode_lengths": responsibility_lengths,
        "facts_per_100_responsibility_unicode": fact_density_per_100_unicode,
        "shared_t06_t08_neutral_carrier_unicode": 165,
        "pair_payload_sha256": payload_sha,
        **field_hashes,
    }


def strip_contract_boilerplate(text: str) -> str:
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("【") and stripped.endswith("】"):
            continue
        if re.fullmatch(r"T\d+(?:、T\d+)+", stripped):
            continue
        kept.append(re.sub(r"^\[T\d+\]", "", stripped))
    return re.sub(r"\s+", "", "".join(kept))


def anti_copy_check() -> dict[str, Any]:
    pair = read_json(PAIR)
    base_requests = read_jsonl(stable.BASE_REQUEST)
    gold_rows = read_jsonl(stable.GOLD)
    real_user_and_gold = "\n".join(
        [row["messages"][1]["content"] for row in base_requests]
        + [fact["fact_sentence"] for row in gold_rows for fact in row["facts"]]
    )
    term_counts = {term: real_user_and_gold.count(term) for term in FORBIDDEN_COPY_TERMS}
    if any(term_counts.values()):
        raise RuntimeError(f"PAIR_FORBIDDEN_TERM_FOUND_IN_REAL24:{term_counts}")
    example_facts = [
        fact["fact"]
        for member in pair["members"]
        for fact in json.loads(member["assistant"])["facts"]
    ]
    gold_facts = [fact["fact_sentence"] for row in gold_rows for fact in row["facts"]]
    fact_sha_overlap = sorted({text_sha(text) for text in example_facts} & {text_sha(text) for text in gold_facts})
    if fact_sha_overlap:
        raise RuntimeError("PAIR_COMPLETE_FACT_SHA_OVERLAP_WITH_REAL24")
    example_texts = [
        strip_contract_boilerplate(member[field])
        for member in pair["members"]
        for field in ("user", "assistant")
    ]
    real_texts = [strip_contract_boilerplate(row["messages"][1]["content"]) for row in base_requests]
    real_texts.extend(strip_contract_boilerplate(text) for text in gold_facts)
    real_windows = {
        text[index : index + 12]
        for text in real_texts
        for index in range(max(0, len(text) - 11))
    }
    overlaps = sorted(
        {
            text[index : index + 12]
            for text in example_texts
            for index in range(max(0, len(text) - 11))
            if text[index : index + 12] in real_windows
        }
    )
    if overlaps:
        raise RuntimeError(f"PAIR_12_UNICODE_CONTIGUOUS_COPY_OVERLAP:{overlaps[:3]}")
    return {
        "forbidden_term_counts_in_real24_user_plus_gold": term_counts,
        "complete_fact_sha_overlap_count": 0,
        "twelve_unicode_contiguous_copy_overlap_count_after_contract_strip": 0,
    }


def build_requests() -> list[dict[str, Any]]:
    pair = read_json(PAIR)
    a, b = pair["members"]
    base = read_jsonl(stable.BASE_REQUEST)
    cases = [f"C{index:02d}" for index in range(1, 25)]
    if [row.get("case_id") for row in base] != cases:
        raise RuntimeError("BASE_REQUEST_CASE_ORDER_DRIFT")
    result = []
    for row in base:
        messages = row.get("messages")
        if not isinstance(messages, list) or [item.get("role") for item in messages] != [
            "system",
            "user",
        ]:
            raise RuntimeError(f"BASE_REQUEST_MESSAGE_SHAPE_DRIFT:{row.get('case_id')}")
        result.append(
            {
                "case_id": row["case_id"],
                "messages": [
                    {"role": "system", "content": messages[0]["content"]},
                    {"role": "user", "content": a["user"]},
                    {"role": "assistant", "content": a["assistant"]},
                    {"role": "user", "content": b["user"]},
                    {"role": "assistant", "content": b["assistant"]},
                    {"role": "user", "content": messages[1]["content"]},
                ],
            }
        )
    return result


def verify_request_derivation() -> dict[str, Any]:
    base = read_jsonl(stable.BASE_REQUEST)
    derived = build_requests()
    digest = hashlib.sha256(jsonl_bytes(derived)).hexdigest()
    if digest != REQUEST_SHA:
        raise RuntimeError(f"EX1_REQUEST_SHA_DRIFT:{digest}")
    roles = ["system", "user", "assistant", "user", "assistant", "user"]
    for source, request in zip(base, derived, strict=True):
        messages = request["messages"]
        if [message["role"] for message in messages] != roles:
            raise RuntimeError(f"EX1_MESSAGE_ROLE_ORDER_DRIFT:{source['case_id']}")
        if messages[0] != source["messages"][0] or messages[-1] != source["messages"][1]:
            raise RuntimeError(f"EX1_ORIGINAL_SYSTEM_OR_ACTUAL_USER_DRIFT:{source['case_id']}")
    return {
        "rows": 24,
        "case_order": "C01_TO_C24",
        "message_roles": roles,
        "original_system_bytes_unchanged": True,
        "actual_user_bytes_unchanged": True,
        "request_sha256": digest,
    }


def verify_static_inputs() -> dict[str, Any]:
    stable.verify_static_inputs()
    projection, projection_sha, _ = stable.exact_base_projection()
    if len(projection) != 24 or projection_sha != EXPECTED["base_projection_sha256"]:
        raise RuntimeError("EX0_BASE_PROJECTION_DRIFT")
    actual = {
        "r10_readme_sha256": sha256(R10 / "00_READ_ME_FIRST.md"),
        "r10_registry_sha256": sha256(R10 / "DECISION_REGISTRY.json"),
        "r10_result_ticket_sha256": sha256(R10 / "RULE_RESULT_TICKET.json"),
        "fixed_pair_sha256": sha256(PAIR),
        "stable_rule_runner_sha256": sha256(RULE_RUNNER_PATH),
        "stable_rule_scorer_sha256": sha256(RULE_SCORER_PATH),
        "base_request_sha256": sha256(stable.BASE_REQUEST),
        "parent_raw_sha256": sha256(stable.PARENT_RAW),
        "base_projection_sha256": projection_sha,
        "rule_final_metrics_sha256": sha256(RULE_FINAL_METRICS),
        "rule_final_receipt_sha256": sha256(RULE_FINAL_RECEIPT),
        "rule_final_empty_queue_sha256": sha256(RULE_FINAL_QUEUE),
        "rule_r02_adjudications_sha256": sha256(RULE_R02_ADJUDICATIONS),
        "rule_r02_receipt_sha256": sha256(RULE_R02_RECEIPT),
        "base_context_decisions_sha256": sha256(stable.BASE_CONTEXT_DECISIONS),
        "read2_r02_sha256": sha256(stable.READ2_R02),
        "gold_sha256": sha256(stable.GOLD),
        "txx_sha256": sha256(stable.TXX),
        "schema_sha256": sha256(stable.SCHEMA),
        "semantic_policy_sha256": sha256(stable.POLICY),
        "wo_scorer_sha256": sha256(stable.WO_SCORER),
        "ex1_request_sha256": hashlib.sha256(jsonl_bytes(build_requests())).hexdigest(),
    }
    if actual != EXPECTED:
        raise RuntimeError(f"STATIC_INPUT_SHA_DRIFT:{actual}")
    return {
        **actual,
        "pair_validation": validate_pair(),
        "anti_copy": anti_copy_check(),
        "request_derivation": verify_request_derivation(),
    }


def validate_ticket(path: Path, *, require_run_root_absent: bool = True) -> dict[str, Any]:
    ticket = read_json(path)
    if set(ticket) != TICKET_KEYS:
        raise RuntimeError("TICKET_KEYS_DRIFT")
    fixed = {
        "schema_version": "base-h180-out2-full-target-ex-contrastive-ticket/1.0",
        "approved": True,
        "scope": "BASE_H180_OUT2_FULL_TARGET_EX_CONTRASTIVE_SINGLE_24_INFERENCE",
        "run_id": RUN_ID,
        "run_root": str(RUN_ROOT),
        "authorized_commands": ["infer-ex1"],
        "spec_sha256": sha256(SPEC),
        "runner_sha256": sha256(Path(__file__)),
        "scorer_sha256": sha256(SCORER),
        "prepare_receipt_sha256": sha256(PREP_RECEIPT),
        "model_receipt_sha256": stable.MODEL_RECEIPT_SHA,
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


def generate(model: Any, tokenizer: Any, stream_generate: Any, sampler: Any, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, request in enumerate(requests, 1):
        free = stable.system_free_percent()
        if free >= 0 and free < 8:
            raise RuntimeError(f"MEMORY_HARD_STOP:{request['case_id']}:{free}")
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
            raise RuntimeError(f"EMPTY_GENERATION_NO_RETRY:{request['case_id']}")
        raw = "".join(pieces)
        rows.append(
            {
                "variant": VARIANT,
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
        print(f"EX1_PROGRESS case={index}/24", flush=True)
    return rows


def infer(ticket_path: Path, validate_only: bool) -> None:
    ticket = validate_ticket(ticket_path)
    if validate_only:
        print(json.dumps({"status": "PASS_TICKET_VALIDATION", "run_root_exists": False}))
        return
    if sys.executable != str(stable.PYTHON):
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    requests = build_requests()
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
            "model_receipt_sha256": stable.MODEL_RECEIPT_SHA,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    request_path = RUN_ROOT / "requests/EX_1_CONTRASTIVE_PAIR_REQUESTS_24.jsonl"
    write_jsonl(request_path, requests)
    if sha256(request_path) != REQUEST_SHA:
        raise RuntimeError("WRITTEN_EX1_REQUEST_SHA_DRIFT")
    sys.path.insert(0, str(stable.VENDOR))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler

    mx.set_wired_limit(20 * 1024**3)
    mx.set_memory_limit(22 * 1024**3)
    mx.set_cache_limit(1 * 1024**3)
    mx.clear_cache()
    model_gate = stable.verify_model_receipt_members()
    model, tokenizer = load(str(stable.MODEL))
    rows = generate(model, tokenizer, stream_generate, make_sampler(temp=0.0), requests)
    raw_path = RUN_ROOT / "inference/EX1_RAW_24.jsonl"
    write_jsonl(raw_path, rows)
    write_json(
        RUN_ROOT / "inference/EX1_RESULT.json",
        {
            "status": "PASS_EX1_24_INFERENCE",
            "run_id": RUN_ID,
            "rows": len(rows),
            "variant": VARIANT,
            "raw_sha256": sha256(raw_path),
            "request_sha256": sha256(request_path),
            "fixed_pair_sha256": sha256(PAIR),
            "ticket_sha256": ticket_sha,
            "ticket_copy_sha256": sha256(ticket_copy),
            "spec_sha256": sha256(SPEC),
            "runner_sha256": sha256(Path(__file__)),
            "scorer_sha256": sha256(SCORER),
            "prepare_receipt_sha256": sha256(PREP_RECEIPT),
            "model_receipt_sha256": stable.MODEL_RECEIPT_SHA,
            "model_member_gates_before_each_load": [
                {
                    "load_index": 1,
                    "load_scope": "UNFINETUNED_BASE_FOR_EX1_ONLY",
                    "gate": model_gate,
                }
            ],
            "model_load_count": 1,
            "adapter_loaded": False,
            "retry": 0,
            "api_calls": 0,
        },
    )
    print(json.dumps({"status": "PASS_EX1_INFERENCE", "raw_sha256": sha256(raw_path)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-check", "infer-ex1"))
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
                    "model_member_gate": stable.verify_model_receipt_members(),
                },
                ensure_ascii=False,
            )
        )
        return
    if args.ticket is None:
        raise RuntimeError("EXECUTION_TICKET_REQUIRED_BEFORE_RUN_ROOT_OR_MODEL_LOAD")
    infer(args.ticket, args.validate_only)


if __name__ == "__main__":
    main()
