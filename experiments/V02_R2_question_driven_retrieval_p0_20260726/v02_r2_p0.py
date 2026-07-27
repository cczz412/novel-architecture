from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "v02-r2-question-driven-p0.v1"
SOURCE_CATALOG_SCHEMA_VERSION = "v02-r2-source-catalog.v2"
QUESTION_GOLD_SCHEMA_VERSION = "v02-r2-question-gold-dev.v2"
ANSWER_CONTRACT_SCHEMA_VERSION = "v02-r2-answer-with-sources.v1"
ADJUDICATION_SCHEMA_VERSION = "v02-r2-isolated-adjudication.v1"
ADJUDICATOR_REGISTRY_SCHEMA_VERSION = "v02-r2-adjudicator-registry.v1"
ADJUDICATOR_TICKET_SCHEMA_VERSION = "v02-r2-adjudicator-ticket.v1"

PUNCTUATION = "。！？!?；;…"
CLOSING_MARKS = "\"'”’』」》】）〕〉》"
HARD_ERROR_CODES = {
    "HALLUCINATION",
    "EVIDENCE_NOT_SUPPORT",
    "WRONG_SUBJECT",
    "WRONG_OBJECT",
    "WRONG_TIME_OR_CHAPTER",
    "POLARITY_REVERSAL",
    "REALIS_MODALITY_REVERSAL",
    "ATTRIBUTION_REVERSAL",
    "CAUSAL_DIRECTION_REVERSED",
    "FALSE_PREMISE_ACCEPTED",
    "SOURCE_ID_INVALID_OR_FORGED",
    "UNSUPPORTED_EXTRA_CLAIM",
}
QUESTION_RESULTS = {
    "FULL_SUPPORTED",
    "PARTIAL_SUPPORTED",
    "CORRECT_ABSTAIN",
    "WRONG_ABSTAIN",
    "FALSE_PREMISE_CORRECTED",
    "FALSE_PREMISE_ACCEPTED",
    "EVIDENCE_NOT_SUPPORT",
    "SOURCE_ID_INVALID_OR_FORGED",
    "UNSUPPORTED_EXTRA_CLAIM",
    "QUALIFIER_WRONG",
    "HALLUCINATION",
    "WRONG_ENTITY_TIME_OBJECT",
    "HEAD_COVERAGE_INCOMPLETE",
    "UNSCORABLE_GOLD_INCOMPLETE",
}
HARD_ERROR_PRIORITY = (
    "HALLUCINATION",
    "UNSUPPORTED_EXTRA_CLAIM",
    "SOURCE_ID_INVALID_OR_FORGED",
    "EVIDENCE_NOT_SUPPORT",
    "FALSE_PREMISE_ACCEPTED",
    "WRONG_SUBJECT",
    "WRONG_OBJECT",
    "WRONG_TIME_OR_CHAPTER",
    "POLARITY_REVERSAL",
    "REALIS_MODALITY_REVERSAL",
    "ATTRIBUTION_REVERSAL",
    "CAUSAL_DIRECTION_REVERSED",
)
HARD_ERROR_RESULT_MAP = {
    "HALLUCINATION": "HALLUCINATION",
    "UNSUPPORTED_EXTRA_CLAIM": "UNSUPPORTED_EXTRA_CLAIM",
    "SOURCE_ID_INVALID_OR_FORGED": "SOURCE_ID_INVALID_OR_FORGED",
    "EVIDENCE_NOT_SUPPORT": "EVIDENCE_NOT_SUPPORT",
    "FALSE_PREMISE_ACCEPTED": "FALSE_PREMISE_ACCEPTED",
    "WRONG_SUBJECT": "WRONG_ENTITY_TIME_OBJECT",
    "WRONG_OBJECT": "WRONG_ENTITY_TIME_OBJECT",
    "WRONG_TIME_OR_CHAPTER": "WRONG_ENTITY_TIME_OBJECT",
    "POLARITY_REVERSAL": "QUALIFIER_WRONG",
    "REALIS_MODALITY_REVERSAL": "QUALIFIER_WRONG",
    "ATTRIBUTION_REVERSAL": "QUALIFIER_WRONG",
    "CAUSAL_DIRECTION_REVERSED": "QUALIFIER_WRONG",
}

SPARSE_QUERY_POLICY = {
    "schema_version": "v02-r2-sparse-query-policy.v1",
    "method": "CHAR_2_3_GRAM_BM25_LIKE",
    "ngram_sizes": [2, 3],
    "query_source": "QUESTION_TEXT_ONLY_NO_GOLD_TERMS",
    "diagnostic_only": True,
}

FAILURE_CODE_CONTRACT = {
    "schema_version": "v02-r2-question-failure-codes.v1",
    "candidate_status": "candidate_silver_not_active",
    "inherits_c15_failure_codes": False,
    "c15_binding_unchanged": True,
    "unknown_code_policy": "REJECT",
    "routes": {
        "PLAN": [
            "PLAN_MISS",
            "FALSE_PREMISE_NOT_IDENTIFIED",
            "QUESTION_SCOPE_UNRESOLVED",
        ],
        "RETRIEVAL": [
            "ALIAS_MISS",
            "CANDIDATE_GENERATION_MISS",
            "RANKING_MISS",
            "WINDOW_EXPANSION_MISS",
            "MULTI_SPAN_JOIN_MISS",
            "SOURCE_SEGMENTATION_DEFECT",
        ],
        "ANSWER": [
            "MISSING_REQUIRED_HEAD",
            "QUALIFIER_MISSING",
            "COREFERENCE_UNRESOLVED",
            "MULTIPLE_ATOMS_COMPRESSED",
            "UNSUPPORTED_EXTRA_CLAIM",
        ],
        "SUPPORT": [
            "EVIDENCE_NOT_SUPPORT",
            "SOURCE_ID_INVALID_OR_FORGED",
            "SOURCE_WINDOW_OUT_OF_SCOPE",
        ],
        "TRANSPORT": [
            "HTTP_429",
            "NETWORK_INTERRUPTED",
            "OUTPUT_LENGTH",
            "NON_JSON_RESPONSE",
            "USAGE_UNKNOWN",
        ],
        "ISOLATION": [
            "GOLD_MOUNTED_DURING_RUN",
            "LOCKBOX_REFERENCE_LEAK",
            "OUTPUT_NOT_SEALED_BEFORE_SCORE",
        ],
    },
}

TERMINAL_ISOLATION_CONTRACT = {
    "schema_version": "v02-r2-terminal-isolation-contract.v1",
    "candidate_status": "candidate_silver_not_active",
    "current_stage": "EXECUTABLE_PREFLIGHT_READY_VALUES_FREEZE_BEFORE_TERMINAL_RUN",
    "freeze_required": {
        "question_set_sha256": None,
        "gold_lockbox_sha256": None,
        "scorer_sha256": None,
        "model_workspace_manifest_sha256": None,
        "adjudicator_ticket_registry_sha256": None,
        "retrieval_policy_sha256": None,
        "prompt_sha256": None,
        "model_identity_receipt_sha256": None,
        "retry_policy_sha256": None,
        "route_manifests": [],
    },
    "run_order": [
        "BUILD_ALLOWLISTED_MODEL_WORKSPACE_WITHOUT_GOLD",
        "RUN_EXECUTABLE_ISOLATION_PREFLIGHT",
        "VERIFY_GOLD_NOT_MOUNTED",
        "VERIFY_ALL_FROZEN_SHA",
        "RUN_EACH_QUALIFIED_ROUTE_ONCE",
        "SEAL_ALL_OUTPUTS",
        "WRITE_OUTPUT_COLLECTION_SHA",
        "UNLOCK_ISOLATED_SCORER",
        "SCORE_ONCE",
    ],
    "terminal_template_policy": "NOTION_R2_SAME_TEMPLATE_NEW_30",
    "terminal_route_policy": (
        "所有进入终验的路线须在任何终验结果可见前同时冻结；"
        "每条路线只跑一轮；全部输出封存后统一解锁评分。"
    ),
    "active_gate": {
        "full_supported_minimum": 15,
        "critical_error_maximum": 10,
    },
    "diagnostic_only_not_gate": {
        "hard_error_target": 0,
        "major_semantic_error_target_maximum": 3,
    },
}

LEDGER_SCHEMAS = {
    "retrieval": {
        "schema_version": "v02-r2-retrieval-ledger.v1",
        "required_fields": [
            "schema_version",
            "question_id",
            "plan_sha256",
            "index_payload_sha256",
            "ranked_windows",
            "candidate_chars",
            "elapsed_ms",
        ],
        "field_types": {
            "schema_version": "str",
            "question_id": "str",
            "plan_sha256": "str",
            "index_payload_sha256": "str",
            "ranked_windows": "list",
            "candidate_chars": "int",
            "elapsed_ms": "int",
        },
        "additional_fields_allowed": False,
    },
    "answer": {
        "schema_version": "v02-r2-answer-ledger.v1",
        "required_fields": [
            "schema_version",
            "question_id",
            "request_sha256",
            "raw_response_sha256",
            "answer_payload_sha256",
            "answer_status",
            "required_head_ids_claimed",
            "usage",
        ],
        "field_types": {
            "schema_version": "str",
            "question_id": "str",
            "request_sha256": "str",
            "raw_response_sha256": "str",
            "answer_payload_sha256": "str",
            "answer_status": "str",
            "required_head_ids_claimed": "list",
            "usage": "dict",
        },
        "additional_fields_allowed": False,
    },
    "support": {
        "schema_version": "v02-r2-support-ledger.v1",
        "required_fields": [
            "schema_version",
            "question_id",
            "claim_id",
            "source_ids",
            "program_backfill_pass",
            "adjudicator_ticket_id",
            "adjudicator_ticket_receipt_sha256",
            "adjudication_payload_sha256",
        ],
        "field_types": {
            "schema_version": "str",
            "question_id": "str",
            "claim_id": "str",
            "source_ids": "list",
            "program_backfill_pass": "bool",
            "adjudicator_ticket_id": "str",
            "adjudicator_ticket_receipt_sha256": "str",
            "adjudication_payload_sha256": "str",
        },
        "additional_fields_allowed": False,
    },
}


class R2P0Error(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


SPARSE_QUERY_POLICY["policy_payload_sha256"] = sha256_bytes(
    canonical_bytes(SPARSE_QUERY_POLICY)
)


def validate_ledger_record(
    *,
    ledger_name: str,
    record: Mapping[str, Any],
) -> None:
    if ledger_name not in LEDGER_SCHEMAS:
        raise R2P0Error(f"LEDGER_SCHEMA_UNKNOWN:{ledger_name}")
    schema = LEDGER_SCHEMAS[ledger_name]
    expected_fields = set(schema["required_fields"])
    if set(record) != expected_fields:
        raise R2P0Error(f"LEDGER_FIELDS_INVALID:{ledger_name}")
    expected_schema_version = schema["schema_version"]
    if record["schema_version"] != expected_schema_version:
        raise R2P0Error(f"LEDGER_SCHEMA_VERSION_INVALID:{ledger_name}")
    python_types = {
        "str": str,
        "int": int,
        "list": list,
        "dict": dict,
        "bool": bool,
    }
    for field, type_name in schema["field_types"].items():
        expected_type = python_types[type_name]
        if not isinstance(record[field], expected_type):
            raise R2P0Error(
                f"LEDGER_FIELD_TYPE_INVALID:{ledger_name}:{field}"
            )
        if expected_type is int and isinstance(record[field], bool):
            raise R2P0Error(
                f"LEDGER_FIELD_TYPE_INVALID:{ledger_name}:{field}"
            )


def ledger_examples() -> dict[str, Mapping[str, Any]]:
    examples: dict[str, Mapping[str, Any]] = {
        "retrieval": {
            "schema_version": LEDGER_SCHEMAS["retrieval"]["schema_version"],
            "question_id": "EXAMPLE-Q01",
            "plan_sha256": "0" * 64,
            "index_payload_sha256": "1" * 64,
            "ranked_windows": ["B00-U0000-P0001"],
            "candidate_chars": 100,
            "elapsed_ms": 1,
        },
        "answer": {
            "schema_version": LEDGER_SCHEMAS["answer"]["schema_version"],
            "question_id": "EXAMPLE-Q01",
            "request_sha256": "2" * 64,
            "raw_response_sha256": "3" * 64,
            "answer_payload_sha256": "4" * 64,
            "answer_status": "ANSWER",
            "required_head_ids_claimed": ["H1"],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        "support": {
            "schema_version": LEDGER_SCHEMAS["support"]["schema_version"],
            "question_id": "EXAMPLE-Q01",
            "claim_id": "C1",
            "source_ids": ["B00-U0000-S0001"],
            "program_backfill_pass": True,
            "adjudicator_ticket_id": "EXAMPLE-TICKET",
            "adjudicator_ticket_receipt_sha256": "6" * 64,
            "adjudication_payload_sha256": "5" * 64,
        },
    }
    for name, record in examples.items():
        validate_ledger_record(ledger_name=name, record=record)
    return examples


def _paragraph_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        end = cursor + len(line)
        spans.append((cursor, end, line))
        cursor = end
    if cursor < len(text):
        spans.append((cursor, len(text), text[cursor:]))
    return spans


def _sentence_spans_v2(
    paragraph_text: str,
    *,
    base_offset: int,
) -> list[tuple[int, int, str]]:
    if not paragraph_text:
        return []
    spans: list[tuple[int, int, str]] = []
    start = 0
    cursor = 0
    while cursor < len(paragraph_text):
        char = paragraph_text[cursor]
        cursor += 1
        if char not in PUNCTUATION:
            continue
        while cursor < len(paragraph_text) and paragraph_text[cursor] in PUNCTUATION:
            cursor += 1
        while cursor < len(paragraph_text) and paragraph_text[cursor] in CLOSING_MARKS:
            cursor += 1
        while cursor < len(paragraph_text) and paragraph_text[cursor].isspace():
            cursor += 1
        spans.append(
            (
                base_offset + start,
                base_offset + cursor,
                paragraph_text[start:cursor],
            )
        )
        start = cursor
    if start < len(paragraph_text):
        spans.append(
            (
                base_offset + start,
                base_offset + len(paragraph_text),
                paragraph_text[start:],
            )
        )
    return spans


def _content_without_closers(text: str) -> str:
    return "".join(
        char for char in text if not char.isspace() and char not in CLOSING_MARKS
    )


def build_source_catalog_v2(
    *,
    source_text: str,
    source_id: str,
    chapter: int,
    run_id: str,
    legacy_catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not source_text:
        raise R2P0Error("SOURCE_BODY_EMPTY")

    paragraphs: list[dict[str, Any]] = []
    sentences: list[dict[str, Any]] = []
    sentence_index = 1
    legacy_sentences = (
        list(legacy_catalog["sentences"]) if legacy_catalog is not None else []
    )
    for paragraph_index, (start, end, original) in enumerate(
        _paragraph_spans(source_text),
        start=1,
    ):
        paragraph_id = f"{source_id}-P{paragraph_index:04d}"
        paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "char_start": start,
                "char_end_exclusive": end,
                "original_text": original,
            }
        )
        for sentence_start, sentence_end, sentence_text in _sentence_spans_v2(
            original,
            base_offset=start,
        ):
            if not _content_without_closers(sentence_text):
                raise R2P0Error(
                    f"SOURCE_SEGMENTATION_DEFECT:{source_id}:{sentence_index}"
                )
            legacy_overlaps: list[tuple[int, str]] = []
            legacy_overlap_candidates: list[dict[str, Any]] = []
            for legacy_row in legacy_sentences:
                overlap_start = max(sentence_start, legacy_row["char_start"])
                overlap_end = min(
                    sentence_end,
                    legacy_row["char_end_exclusive"],
                )
                if overlap_start >= overlap_end:
                    continue
                overlap_text = source_text[overlap_start:overlap_end]
                content_overlap = len(_content_without_closers(overlap_text))
                legacy_overlap_candidates.append(
                    {
                        "legacy_source_id": legacy_row["sentence_id"],
                        "content_char_overlap": content_overlap,
                        "total_char_overlap": overlap_end - overlap_start,
                    }
                )
                if content_overlap:
                    legacy_overlaps.append(
                        (content_overlap, legacy_row["sentence_id"])
                    )
            if legacy_catalog is not None:
                if not legacy_overlaps:
                    raise R2P0Error(
                        f"LEGACY_SENTENCE_ROUTE_MISSING:{source_id}:{sentence_index}"
                    )
                legacy_overlaps.sort(key=lambda row: (-row[0], row[1]))
                if (
                    len(legacy_overlaps) > 1
                    and legacy_overlaps[0][0] == legacy_overlaps[1][0]
                ):
                    raise R2P0Error(
                        f"LEGACY_SENTENCE_ROUTE_TIE:{source_id}:{sentence_index}"
                    )
                sentence_id = legacy_overlaps[0][1]
            else:
                sentence_id = f"{source_id}-S{sentence_index:04d}"
            sentences.append(
                {
                    "sentence_id": sentence_id,
                    "paragraph_id": paragraph_id,
                    "char_start": sentence_start,
                    "char_end_exclusive": sentence_end,
                    "original_text": sentence_text,
                    "legacy_sentence_ids_with_content_overlap": [
                        row[1] for row in legacy_overlaps
                    ],
                    "_legacy_overlap_candidates": legacy_overlap_candidates,
                    "accepted_legacy_source_ids": [],
                }
            )
            sentence_index += 1

    alias_candidates: dict[str, list[tuple[int, int, int]]] = {}
    for row_index, row in enumerate(sentences):
        for candidate in row["_legacy_overlap_candidates"]:
            alias_candidates.setdefault(
                candidate["legacy_source_id"],
                [],
            ).append(
                (
                    candidate["content_char_overlap"],
                    candidate["total_char_overlap"],
                    row_index,
                )
            )
    for legacy_source_id, candidates in alias_candidates.items():
        candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))
        if (
            len(candidates) > 1
            and candidates[0][:2] == candidates[1][:2]
        ):
            raise R2P0Error(
                f"LEGACY_SOURCE_ID_ALIAS_TIE:{legacy_source_id}"
            )
        sentences[candidates[0][2]]["accepted_legacy_source_ids"].append(
            legacy_source_id
        )
    for row in sentences:
        row["accepted_legacy_source_ids"].sort()
        del row["_legacy_overlap_candidates"]

    payload: dict[str, Any] = {
        "schema_version": SOURCE_CATALOG_SCHEMA_VERSION,
        "candidate_status": "candidate_silver_not_active",
        "run_id": run_id,
        "source_id": source_id,
        "chapter": chapter,
        "coordinate_unit": "PYTHON_UNICODE_CODEPOINT",
        "source_id_namespace": (
            "C15_LEGACY_SENTENCE_ID_ACCEPTED_AND_RESOLVED_TO_V2_SENTENCE"
            if legacy_catalog is not None
            else "V02_R2_NEW_SENTENCE_ID"
        ),
        "answer_source_id_contract": "SENTENCE_ID_ONLY_PARAGRAPH_ID_FOR_RETRIEVAL_ONLY",
        "source_body_sha256": sha256_bytes(source_text.encode("utf-8")),
        "source_text": source_text,
        "paragraphs": paragraphs,
        "sentences": sentences,
        "semantic_truth_verified_by_program": False,
    }
    payload["catalog_payload_sha256"] = sha256_bytes(canonical_bytes(payload))
    verify_source_catalog_v2(payload)
    return payload


def verify_source_catalog_v2(catalog: Mapping[str, Any]) -> dict[str, Any]:
    source_text = catalog["source_text"]
    paragraphs = list(catalog["paragraphs"])
    sentences = list(catalog["sentences"])
    expected_body_sha256 = sha256_bytes(source_text.encode("utf-8"))
    if catalog.get("source_body_sha256") != expected_body_sha256:
        raise R2P0Error("SOURCE_BODY_SHA_MISMATCH")
    payload_without_hash = dict(catalog)
    actual_payload_sha256 = payload_without_hash.pop(
        "catalog_payload_sha256",
        None,
    )
    expected_payload_sha256 = sha256_bytes(
        canonical_bytes(payload_without_hash)
    )
    if actual_payload_sha256 != expected_payload_sha256:
        raise R2P0Error("CATALOG_PAYLOAD_SHA_MISMATCH")

    paragraph_rebuild = "".join(row["original_text"] for row in paragraphs)
    if paragraph_rebuild != source_text:
        raise R2P0Error("PARAGRAPH_REBUILD_MISMATCH")
    for row in [*paragraphs, *sentences]:
        start = row["char_start"]
        end = row["char_end_exclusive"]
        if not isinstance(start, int) or not isinstance(end, int) or start >= end:
            raise R2P0Error("SOURCE_RANGE_INVALID")
        if source_text[start:end] != row["original_text"]:
            raise R2P0Error("SOURCE_RANGE_TEXT_MISMATCH")
    isolated = [
        row["sentence_id"]
        for row in sentences
        if not _content_without_closers(row["original_text"])
    ]
    if isolated:
        raise R2P0Error(f"ISOLATED_CLOSER_SENTENCE:{isolated}")
    sentence_ids = [row["sentence_id"] for row in sentences]
    if len(sentence_ids) != len(set(sentence_ids)):
        raise R2P0Error("SOURCE_SENTENCE_ID_DUPLICATED")
    accepted_legacy_ids = [
        source_id
        for row in sentences
        for source_id in row["accepted_legacy_source_ids"]
    ]
    if len(accepted_legacy_ids) != len(set(accepted_legacy_ids)):
        raise R2P0Error("LEGACY_SOURCE_ID_ALIAS_DUPLICATED")
    return {
        "status": "PASS",
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "isolated_closer_sentence_count": 0,
        "source_body_sha256": expected_body_sha256,
        "catalog_payload_sha256": expected_payload_sha256,
    }


def verify_lockbox_source_id_compatibility(
    *,
    lockbox: Mapping[str, Any],
    catalogs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    required_source_ids = {
        source_id
        for cell in lockbox["cells"]
        for part in cell["required_parts"]
        for source_group in part["source_id_groups"]
        for source_id in source_group
    }
    rows_by_id = {
        accepted_source_id: row
        for catalog in catalogs
        for row in catalog["sentences"]
        for accepted_source_id in row["accepted_legacy_source_ids"]
    }
    missing = sorted(required_source_ids - rows_by_id.keys())
    if missing:
        raise R2P0Error(f"LOCKBOX_SOURCE_ID_MISSING:{missing}")
    wrong_primary = sorted(
        source_id
        for source_id in required_source_ids
        if source_id not in rows_by_id[source_id]["accepted_legacy_source_ids"]
    )
    if wrong_primary:
        raise R2P0Error(f"LOCKBOX_SOURCE_ID_NOT_OVERLAPPING:{wrong_primary}")
    return {
        "status": "PASS",
        "required_source_id_count": len(required_source_ids),
        "matched_source_id_count": len(required_source_ids),
        "missing_source_id_count": 0,
        "answer_source_id_namespace": (
            "C15_LEGACY_SENTENCE_ID_ACCEPTED_AND_RESOLVED_TO_V2_SENTENCE"
        ),
        "alias_resolution_count": len(rows_by_id),
    }


def resolve_legacy_source_row(
    *,
    catalogs: Sequence[Mapping[str, Any]],
    legacy_source_id: str,
) -> Mapping[str, Any]:
    matches = [
        row
        for catalog in catalogs
        for row in catalog["sentences"]
        if legacy_source_id in row["accepted_legacy_source_ids"]
    ]
    if not matches:
        raise R2P0Error(
            f"LEGACY_SOURCE_ID_NOT_FOUND:{legacy_source_id}"
        )
    if len(matches) != 1:
        raise R2P0Error(
            f"LEGACY_SOURCE_ID_RESOLUTION_AMBIGUOUS:{legacy_source_id}"
        )
    return matches[0]


def verify_all_legacy_source_id_resolution(
    *,
    legacy_catalogs: Sequence[Mapping[str, Any]],
    new_catalogs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    legacy_rows = [
        row
        for catalog in legacy_catalogs
        for row in catalog["sentences"]
    ]
    legacy_ids = [row["sentence_id"] for row in legacy_rows]
    if len(legacy_ids) != len(set(legacy_ids)):
        raise R2P0Error("LEGACY_SOURCE_ID_DUPLICATED_ACROSS_CATALOGS")
    pure_closer_ids = [
        row["sentence_id"]
        for row in legacy_rows
        if not _content_without_closers(row["original_text"])
    ]
    resolved_rows = {
        source_id: resolve_legacy_source_row(
            catalogs=new_catalogs,
            legacy_source_id=source_id,
        )
        for source_id in legacy_ids
    }
    unresolved_content = sorted(
        source_id
        for source_id, row in resolved_rows.items()
        if not _content_without_closers(row["original_text"])
    )
    if unresolved_content:
        raise R2P0Error(
            f"LEGACY_SOURCE_ID_RESOLVED_TO_EMPTY_CONTENT:{unresolved_content}"
        )
    return {
        "status": "PASS",
        "legacy_source_id_count": len(legacy_ids),
        "resolved_unique_count": len(resolved_rows),
        "pure_closer_legacy_source_id_count": len(pure_closer_ids),
        "pure_closer_resolved_to_content_count": len(pure_closer_ids),
        "missing_count": 0,
        "ambiguous_count": 0,
    }


def load_formal_gold_parts(
    *,
    repo: Path,
    case_ids: Sequence[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    parts: dict[str, dict[str, Any]] = {}
    receipts: list[dict[str, Any]] = []
    for case_id in sorted(set(case_ids)):
        if "-" not in case_id:
            raise R2P0Error(f"CASE_ID_INVALID:{case_id}")
        book_id, unit_id = case_id.split("-", maxsplit=1)
        pointer_path = (
            repo
            / "config/gold"
            / f"Z74B_{book_id}_{unit_id}_structure_gold_current.json"
        )
        if not pointer_path.is_file():
            raise R2P0Error(f"FORMAL_GOLD_POINTER_MISSING:{case_id}")
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer.get("status") != "active" or pointer.get("label_tier") != "gold":
            raise R2P0Error(f"FORMAL_GOLD_POINTER_NOT_ACTIVE:{case_id}")
        gold_path = repo / pointer["active_gold"]["path"]
        if not gold_path.is_file():
            raise R2P0Error(f"FORMAL_GOLD_FILE_MISSING:{case_id}")
        actual_sha256 = sha256_file(gold_path)
        if actual_sha256 != pointer["active_gold"]["sha256"]:
            raise R2P0Error(f"FORMAL_GOLD_SHA_MISMATCH:{case_id}")
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        part_count = 0
        for item in gold["layered_items"]:
            for part in item.get("parts", []):
                part_id = part["part_id"]
                if part_id in parts:
                    raise R2P0Error(f"FORMAL_GOLD_PART_DUPLICATED:{part_id}")
                parts[part_id] = {
                    "semantic_statement": part["claim"],
                    "claim_components": part.get("claim_components", {}),
                    "formal_gold_pointer_path": str(pointer_path.relative_to(repo)),
                    "formal_gold_path": str(gold_path.relative_to(repo)),
                    "formal_gold_sha256": actual_sha256,
                    "formal_gold_version": pointer["active_gold"]["version"],
                }
                part_count += 1
        receipts.append(
            {
                "case_id": case_id,
                "pointer_path": str(pointer_path.relative_to(repo)),
                "pointer_sha256": sha256_file(pointer_path),
                "formal_gold_path": str(gold_path.relative_to(repo)),
                "formal_gold_sha256": actual_sha256,
                "formal_gold_version": pointer["active_gold"]["version"],
                "part_count": part_count,
            }
        )
    return parts, receipts


def migrate_r1_lockbox_to_dev_gold_v2(
    lockbox: Mapping[str, Any],
    *,
    formal_gold_parts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    formal_gold_parts = formal_gold_parts or {}
    migrated_cells: list[dict[str, Any]] = []
    for cell in lockbox["cells"]:
        if cell["expected"] == "ANSWERED":
            answerability = "ANSWERABLE"
            missing_part_ids = [
                part["part_id"]
                for part in cell["required_parts"]
                if part["part_id"] not in formal_gold_parts
            ]
            semantic_status = (
                "FORMAL_GOLD_CURRENT_IMPORTED"
                if not missing_part_ids
                else "NEEDS_HUMAN_SEMANTIC_ANSWER"
            )
        elif cell["expected"] == "OPEN":
            answerability = "UNRESOLVED_NEEDS_HUMAN"
            semantic_status = "NOT_SCOREABLE"
            missing_part_ids = []
        else:
            raise R2P0Error(f"UNKNOWN_R1_EXPECTED:{cell['expected']}")

        required_heads = []
        for part in cell["required_parts"]:
            formal_part = formal_gold_parts.get(part["part_id"])
            required_heads.append(
                {
                    "head_id": part["part_id"],
                    "semantic_statement": (
                        formal_part["semantic_statement"] if formal_part else None
                    ),
                    "formal_gold_claim_components": (
                        formal_part["claim_components"] if formal_part else None
                    ),
                    "source_id_groups": part["source_id_groups"],
                    "required_qualifiers": {
                        "retain_negation": part["must_retain_negation"],
                        "retain_uncertainty": part["must_retain_uncertainty"],
                    },
                    "semantic_truth_status": semantic_status,
                    "gold_provenance": (
                        {
                            "pointer_path": formal_part[
                                "formal_gold_pointer_path"
                            ],
                            "formal_gold_path": formal_part["formal_gold_path"],
                            "formal_gold_sha256": formal_part[
                                "formal_gold_sha256"
                            ],
                            "formal_gold_version": formal_part[
                                "formal_gold_version"
                            ],
                        }
                        if formal_part
                        else None
                    ),
                }
            )
        migrated_cells.append(
            {
                "cell_id": cell["cell_id"],
                "case_id": cell["case_id"],
                "question_id": cell["question_id"],
                "question_text": cell["question_text"],
                "answerability": answerability,
                "required_heads": required_heads,
                "optional_heads": [],
                "acceptable_semantic_variants": [],
                "forbidden_inferences": [],
                "semantic_truth_status": semantic_status,
                "model_visible": False,
                "legacy_expected": cell["expected"],
                "missing_formal_gold_part_ids": missing_part_ids,
            }
        )

    unresolved = sum(
        row["semantic_truth_status"] == "NOT_SCOREABLE" for row in migrated_cells
    )
    needs_semantic = sum(
        row["semantic_truth_status"] == "NEEDS_HUMAN_SEMANTIC_ANSWER"
        for row in migrated_cells
    )
    scoreable = sum(
        row["semantic_truth_status"] == "FORMAL_GOLD_CURRENT_IMPORTED"
        for row in migrated_cells
    )
    result: dict[str, Any] = {
        "schema_version": QUESTION_GOLD_SCHEMA_VERSION,
        "candidate_status": "candidate_silver_not_active",
        "model_visible": False,
        "formal_gold_payload_exported": False,
        "formal_gold_claims_mounted_for_isolated_offline_scoring": bool(
            formal_gold_parts
        ),
        "legacy_reference_map_sha256": lockbox["reference_map_sha256"],
        "cell_total": len(migrated_cells),
        "cells": migrated_cells,
        "migration_summary": {
            "scoreable_semantic_cells": scoreable,
            "needs_human_semantic_answer": needs_semantic,
            "unresolved_needs_human_answerability": unresolved,
            "legacy_open_auto_score_allowed": False,
        },
    }
    result["migration_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def _unique_string_list(value: Any, *, error_prefix: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise R2P0Error(f"{error_prefix}_NOT_NONEMPTY_LIST")
    if any(not isinstance(row, str) or not row for row in value):
        raise R2P0Error(f"{error_prefix}_ITEM_INVALID")
    if len(value) != len(set(value)):
        raise R2P0Error(f"{error_prefix}_DUPLICATED")
    return value


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def validate_adjudicator_registry(
    registry: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if set(registry) != {
        "schema_version",
        "scoring_executor_id",
        "tickets",
    }:
        raise R2P0Error("ADJUDICATOR_REGISTRY_FIELDS_INVALID")
    if registry.get("schema_version") != ADJUDICATOR_REGISTRY_SCHEMA_VERSION:
        raise R2P0Error("ADJUDICATOR_REGISTRY_SCHEMA_VERSION_INVALID")
    if (
        not isinstance(registry["scoring_executor_id"], str)
        or not registry["scoring_executor_id"]
    ):
        raise R2P0Error("ADJUDICATOR_REGISTRY_SCORING_EXECUTOR_INVALID")
    tickets = registry.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        raise R2P0Error("ADJUDICATOR_REGISTRY_TICKETS_INVALID")
    indexed: dict[str, Mapping[str, Any]] = {}
    for ticket in tickets:
        if set(ticket) != {
            "ticket_id",
            "receipt_sha256",
            "issuer",
            "receipt_path",
            "independence_basis",
        }:
            raise R2P0Error("ADJUDICATOR_TICKET_FIELDS_INVALID")
        ticket_id = ticket["ticket_id"]
        if not isinstance(ticket_id, str) or not ticket_id:
            raise R2P0Error("ADJUDICATOR_TICKET_ID_INVALID")
        if ticket_id in indexed:
            raise R2P0Error(f"ADJUDICATOR_TICKET_ID_DUPLICATED:{ticket_id}")
        if not _valid_sha256(ticket["receipt_sha256"]):
            raise R2P0Error("ADJUDICATOR_TICKET_RECEIPT_SHA_INVALID")
        for field in ("issuer", "receipt_path", "independence_basis"):
            if not isinstance(ticket[field], str) or not ticket[field]:
                raise R2P0Error(
                    f"ADJUDICATOR_TICKET_{field.upper()}_INVALID"
                )
        indexed[ticket_id] = ticket
    return indexed


def load_verified_adjudicator_registry(
    *,
    registry_path: Path,
    expected_registry_sha256: str,
    isolation_root: Path,
    scoring_executor_id: str,
) -> dict[str, Mapping[str, Any]]:
    root_resolved = isolation_root.resolve()
    if registry_path.is_symlink():
        raise R2P0Error("ADJUDICATOR_REGISTRY_SYMLINK_FORBIDDEN")
    if not registry_path.is_file():
        raise R2P0Error("ADJUDICATOR_REGISTRY_FILE_MISSING")
    if not registry_path.resolve().is_relative_to(root_resolved):
        raise R2P0Error("ADJUDICATOR_REGISTRY_PATH_ESCAPE")
    if not _valid_sha256(expected_registry_sha256):
        raise R2P0Error("ADJUDICATOR_REGISTRY_EXPECTED_SHA_INVALID")
    if sha256_file(registry_path) != expected_registry_sha256:
        raise R2P0Error("ADJUDICATOR_REGISTRY_FILE_SHA_MISMATCH")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    indexed = validate_adjudicator_registry(registry)
    if registry["scoring_executor_id"] != scoring_executor_id:
        raise R2P0Error("ADJUDICATOR_REGISTRY_SCORING_EXECUTOR_MISMATCH")

    verified: dict[str, Mapping[str, Any]] = {}
    for ticket_id, ticket in indexed.items():
        relative_path = Path(ticket["receipt_path"])
        if relative_path.is_absolute():
            raise R2P0Error("ADJUDICATOR_TICKET_PATH_NOT_RELATIVE")
        receipt_path = isolation_root / relative_path
        if receipt_path.is_symlink():
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_SYMLINK_FORBIDDEN:{ticket_id}"
            )
        if not receipt_path.is_file():
            raise R2P0Error(f"ADJUDICATOR_TICKET_FILE_MISSING:{ticket_id}")
        if not receipt_path.resolve().is_relative_to(root_resolved):
            raise R2P0Error(f"ADJUDICATOR_TICKET_PATH_ESCAPE:{ticket_id}")
        if sha256_file(receipt_path) != ticket["receipt_sha256"]:
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_FILE_SHA_MISMATCH:{ticket_id}"
            )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if set(receipt) != {
            "schema_version",
            "ticket_id",
            "issuer",
            "adjudicator_executor_id",
            "scoring_executor_id",
            "independence_basis",
        }:
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_RECEIPT_FIELDS_INVALID:{ticket_id}"
            )
        if receipt["schema_version"] != ADJUDICATOR_TICKET_SCHEMA_VERSION:
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_SCHEMA_VERSION_INVALID:{ticket_id}"
            )
        if receipt["ticket_id"] != ticket_id:
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_RECEIPT_ID_MISMATCH:{ticket_id}"
            )
        if receipt["issuer"] != ticket["issuer"]:
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_RECEIPT_ISSUER_MISMATCH:{ticket_id}"
            )
        if receipt["independence_basis"] != ticket["independence_basis"]:
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_INDEPENDENCE_BASIS_MISMATCH:{ticket_id}"
            )
        if receipt["scoring_executor_id"] != scoring_executor_id:
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_SCORING_EXECUTOR_MISMATCH:{ticket_id}"
            )
        adjudicator_executor_id = receipt["adjudicator_executor_id"]
        if (
            not isinstance(adjudicator_executor_id, str)
            or not adjudicator_executor_id
            or adjudicator_executor_id == scoring_executor_id
        ):
            raise R2P0Error(
                f"ADJUDICATOR_TICKET_NOT_INDEPENDENT:{ticket_id}"
            )
        verified[ticket_id] = {
            **ticket,
            "adjudicator_executor_id": adjudicator_executor_id,
            "verified_receipt_path": str(receipt_path),
        }
    return verified


def validate_terminal_freeze_contract(
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    freeze = contract.get("freeze_required")
    if not isinstance(freeze, dict):
        raise R2P0Error("TERMINAL_FREEZE_REQUIRED_INVALID")
    required_sha_fields = {
        "question_set_sha256",
        "gold_lockbox_sha256",
        "scorer_sha256",
        "model_workspace_manifest_sha256",
        "adjudicator_ticket_registry_sha256",
        "retrieval_policy_sha256",
        "prompt_sha256",
        "model_identity_receipt_sha256",
        "retry_policy_sha256",
    }
    if not required_sha_fields.issubset(freeze):
        raise R2P0Error("TERMINAL_FREEZE_FIELDS_MISSING")
    missing_or_invalid = sorted(
        field for field in required_sha_fields if not _valid_sha256(freeze[field])
    )
    if missing_or_invalid:
        raise R2P0Error(
            f"TERMINAL_FREEZE_SHA_MISSING_OR_INVALID:{missing_or_invalid}"
        )
    route_manifests = freeze.get("route_manifests")
    if (
        not isinstance(route_manifests, list)
        or not route_manifests
        or any(not _valid_sha256(value) for value in route_manifests)
    ):
        raise R2P0Error("TERMINAL_ROUTE_MANIFESTS_NOT_FROZEN")
    return {
        "status": "PASS",
        "frozen_sha_field_count": len(required_sha_fields),
        "route_manifest_count": len(route_manifests),
    }


def _gold_head_sources(gold: Mapping[str, Any]) -> dict[str, set[str]]:
    return {
        head["head_id"]: {
            source_id
            for source_group in head["source_id_groups"]
            for source_id in source_group
        }
        for head in gold["required_heads"]
    }


def validate_answer_contract(
    answer: Mapping[str, Any],
    *,
    gold: Mapping[str, Any] | None = None,
) -> None:
    if set(answer) != {
        "schema_version",
        "question_id",
        "status",
        "claims",
        "abstention_reason",
    }:
        raise R2P0Error("ANSWER_TOP_LEVEL_FIELDS_INVALID")
    if answer.get("schema_version") != ANSWER_CONTRACT_SCHEMA_VERSION:
        raise R2P0Error("ANSWER_SCHEMA_VERSION_INVALID")
    if not isinstance(answer.get("question_id"), str) or not answer["question_id"]:
        raise R2P0Error("ANSWER_QUESTION_ID_INVALID")
    status = answer.get("status")
    if status not in {"ANSWER", "PARTIAL", "ABSTAIN"}:
        raise R2P0Error("ANSWER_STATUS_INVALID")
    claims = answer.get("claims")
    if not isinstance(claims, list):
        raise R2P0Error("ANSWER_CLAIMS_NOT_LIST")
    if status == "ABSTAIN" and claims:
        raise R2P0Error("ABSTAIN_WITH_CLAIMS")
    if status != "ABSTAIN" and not claims:
        raise R2P0Error("ANSWER_WITHOUT_CLAIMS")
    if status == "ABSTAIN":
        if not isinstance(answer.get("abstention_reason"), str):
            raise R2P0Error("ABSTENTION_REASON_REQUIRED")
    elif answer.get("abstention_reason") is not None:
        raise R2P0Error("ANSWER_WITH_ABSTENTION_REASON")
    allowed_head_sources = _gold_head_sources(gold) if gold is not None else {}
    if gold is not None and answer["question_id"] != gold["question_id"]:
        raise R2P0Error("ANSWER_GOLD_QUESTION_ID_MISMATCH")
    claim_ids: list[str] = []
    for claim in claims:
        if set(claim) != {"claim_id", "head_ids", "statement", "source_ids"}:
            raise R2P0Error("ANSWER_CLAIM_FIELDS_INVALID")
        if not isinstance(claim["claim_id"], str) or not claim["claim_id"]:
            raise R2P0Error("ANSWER_CLAIM_ID_INVALID")
        claim_ids.append(claim["claim_id"])
        if not isinstance(claim["statement"], str) or not claim["statement"]:
            raise R2P0Error("ANSWER_CLAIM_REQUIRED_VALUE_EMPTY")
        head_ids = _unique_string_list(
            claim["head_ids"],
            error_prefix="ANSWER_HEAD_IDS",
        )
        source_ids = _unique_string_list(
            claim["source_ids"],
            error_prefix="ANSWER_SOURCE_IDS",
        )
        if gold is None:
            continue
        unknown_heads = sorted(set(head_ids) - allowed_head_sources.keys())
        if unknown_heads:
            raise R2P0Error(f"ANSWER_HEAD_ID_UNAUTHORIZED:{unknown_heads}")
        allowed_sources = set().union(
            *(allowed_head_sources[head_id] for head_id in head_ids)
        )
        unauthorized_sources = sorted(set(source_ids) - allowed_sources)
        if unauthorized_sources:
            raise R2P0Error(
                f"ANSWER_SOURCE_ID_UNAUTHORIZED:{unauthorized_sources}"
            )
        missing_head_evidence = sorted(
            head_id
            for head_id in head_ids
            if not (set(source_ids) & allowed_head_sources[head_id])
        )
        if missing_head_evidence:
            raise R2P0Error(
                f"ANSWER_HEAD_WITHOUT_AUTHORIZED_SOURCE:{missing_head_evidence}"
            )
    if len(claim_ids) != len(set(claim_ids)):
        raise R2P0Error("ANSWER_CLAIM_ID_DUPLICATED")


def validate_adjudication_contract(
    *,
    gold: Mapping[str, Any],
    answer: Mapping[str, Any],
    adjudication: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if set(adjudication) != {
        "schema_version",
        "question_id",
        "gold_cell_payload_sha256",
        "answer_payload_sha256",
        "adjudicator_ticket_id",
        "adjudicator_ticket_receipt_sha256",
        "head_checks",
        "hard_error_codes",
        "false_premise_corrected",
    }:
        raise R2P0Error("ADJUDICATION_TOP_LEVEL_FIELDS_INVALID")
    if adjudication.get("schema_version") != ADJUDICATION_SCHEMA_VERSION:
        raise R2P0Error("ADJUDICATION_SCHEMA_VERSION_INVALID")
    if adjudication.get("question_id") != answer.get("question_id"):
        raise R2P0Error("ADJUDICATION_QUESTION_ID_MISMATCH")
    if adjudication["question_id"] != gold["question_id"]:
        raise R2P0Error("ADJUDICATION_GOLD_QUESTION_ID_MISMATCH")
    expected_gold_sha256 = sha256_bytes(canonical_bytes(gold))
    if adjudication["gold_cell_payload_sha256"] != expected_gold_sha256:
        raise R2P0Error("ADJUDICATION_GOLD_SHA_MISMATCH")
    expected_answer_sha256 = sha256_bytes(canonical_bytes(answer))
    if adjudication["answer_payload_sha256"] != expected_answer_sha256:
        raise R2P0Error("ADJUDICATION_ANSWER_SHA_MISMATCH")
    if (
        not isinstance(adjudication["adjudicator_ticket_id"], str)
        or not adjudication["adjudicator_ticket_id"]
    ):
        raise R2P0Error("ADJUDICATOR_TICKET_ID_INVALID")
    if not _valid_sha256(adjudication["adjudicator_ticket_receipt_sha256"]):
        raise R2P0Error("ADJUDICATOR_TICKET_RECEIPT_SHA_INVALID")
    if not isinstance(adjudication["false_premise_corrected"], bool):
        raise R2P0Error("FALSE_PREMISE_CORRECTED_NOT_BOOL")
    hard_errors = adjudication["hard_error_codes"]
    if not isinstance(hard_errors, list):
        raise R2P0Error("HARD_ERROR_CODES_NOT_LIST")
    if any(not isinstance(row, str) for row in hard_errors):
        raise R2P0Error("HARD_ERROR_CODE_ITEM_INVALID")
    if len(hard_errors) != len(set(hard_errors)):
        raise R2P0Error("HARD_ERROR_CODE_DUPLICATED")
    unknown_hard = sorted(set(hard_errors) - HARD_ERROR_CODES)
    if unknown_hard:
        raise R2P0Error(f"UNKNOWN_HARD_ERROR_CODE:{unknown_hard}")
    head_rows = adjudication["head_checks"]
    if not isinstance(head_rows, list):
        raise R2P0Error("ADJUDICATION_HEAD_CHECKS_NOT_LIST")
    required_heads = {row["head_id"] for row in gold["required_heads"]}
    head_checks: dict[str, Mapping[str, Any]] = {}
    for row in head_rows:
        if set(row) != {
            "head_id",
            "fact_correct",
            "evidence_supports",
            "qualifiers_correct",
        }:
            raise R2P0Error("ADJUDICATION_HEAD_CHECK_FIELDS_INVALID")
        head_id = row["head_id"]
        if not isinstance(head_id, str) or not head_id:
            raise R2P0Error("ADJUDICATION_HEAD_ID_INVALID")
        if head_id not in required_heads:
            raise R2P0Error(f"ADJUDICATION_HEAD_ID_UNAUTHORIZED:{head_id}")
        if head_id in head_checks:
            raise R2P0Error(f"ADJUDICATION_HEAD_ID_DUPLICATED:{head_id}")
        for field in ("fact_correct", "evidence_supports", "qualifiers_correct"):
            if not isinstance(row[field], bool):
                raise R2P0Error(f"ADJUDICATION_{field.upper()}_NOT_BOOL")
        head_checks[head_id] = row
    return head_checks


def score_question(
    *,
    gold: Mapping[str, Any],
    answer: Mapping[str, Any],
    adjudication: Mapping[str, Any],
    adjudicator_registry_path: Path | None = None,
    trusted_adjudicator_registry_sha256: str | None = None,
    adjudicator_isolation_root: Path | None = None,
    scoring_executor_id: str | None = None,
) -> dict[str, Any]:
    validate_answer_contract(answer)
    if answer["question_id"] != gold["question_id"]:
        raise R2P0Error("ANSWER_GOLD_QUESTION_ID_MISMATCH")
    if gold["semantic_truth_status"] in {
        "NOT_SCOREABLE",
        "NEEDS_HUMAN_SEMANTIC_ANSWER",
    }:
        return _score_result(
            result="UNSCORABLE_GOLD_INCOMPLETE",
            hard_errors=[],
            missing_heads=[],
        )
    validate_answer_contract(answer, gold=gold)
    if (
        adjudicator_registry_path is None
        or trusted_adjudicator_registry_sha256 is None
        or adjudicator_isolation_root is None
        or scoring_executor_id is None
    ):
        raise R2P0Error("TRUSTED_ADJUDICATOR_REGISTRY_REQUIRED")
    trusted_tickets = load_verified_adjudicator_registry(
        registry_path=adjudicator_registry_path,
        expected_registry_sha256=trusted_adjudicator_registry_sha256,
        isolation_root=adjudicator_isolation_root,
        scoring_executor_id=scoring_executor_id,
    )
    ticket_id = adjudication.get("adjudicator_ticket_id")
    if ticket_id not in trusted_tickets:
        raise R2P0Error(f"ADJUDICATOR_TICKET_NOT_TRUSTED:{ticket_id}")
    trusted_ticket = trusted_tickets[ticket_id]
    if (
        adjudication.get("adjudicator_ticket_receipt_sha256")
        != trusted_ticket["receipt_sha256"]
    ):
        raise R2P0Error("ADJUDICATOR_TICKET_RECEIPT_SHA_MISMATCH")
    head_checks = validate_adjudication_contract(
        gold=gold,
        answer=answer,
        adjudication=adjudication,
    )

    answerability = gold["answerability"]
    hard_errors = sorted(set(adjudication["hard_error_codes"]))
    required_head_ids = [row["head_id"] for row in gold["required_heads"]]
    missing_heads = [
        head_id
        for head_id in required_head_ids
        if head_id not in head_checks
        or not head_checks[head_id].get("fact_correct")
        or not head_checks[head_id].get("evidence_supports")
        or not head_checks[head_id].get("qualifiers_correct")
    ]
    any_supported = any(
        head_checks[head_id]["fact_correct"]
        and head_checks[head_id]["evidence_supports"]
        for head_id in required_head_ids
        if head_id in head_checks
    )
    qualifier_wrong_heads = [
        head_id
        for head_id in required_head_ids
        if head_id in head_checks
        and head_checks[head_id].get("fact_correct")
        and head_checks[head_id].get("evidence_supports")
        and not head_checks[head_id].get("qualifiers_correct")
    ]

    if answerability == "ANSWERABLE":
        if answer["status"] == "ABSTAIN":
            return _score_result(
                result="WRONG_ABSTAIN",
                hard_errors=hard_errors,
                missing_heads=required_head_ids,
            )
        if hard_errors:
            result = _hard_error_result(hard_errors)
            return _score_result(
                result=result,
                hard_errors=hard_errors,
                missing_heads=missing_heads,
            )
        if qualifier_wrong_heads:
            return _score_result(
                result="QUALIFIER_WRONG",
                hard_errors=[],
                missing_heads=qualifier_wrong_heads,
            )
        if not missing_heads:
            return _score_result(
                result="FULL_SUPPORTED",
                hard_errors=[],
                missing_heads=[],
            )
        if any_supported:
            return _score_result(
                result="PARTIAL_SUPPORTED",
                hard_errors=[],
                missing_heads=missing_heads,
            )
        return _score_result(
            result="HEAD_COVERAGE_INCOMPLETE",
            hard_errors=[],
            missing_heads=missing_heads,
        )

    if answerability == "UNANSWERABLE":
        if answer["status"] == "ABSTAIN" and not hard_errors:
            return _score_result(
                result="CORRECT_ABSTAIN",
                hard_errors=[],
                missing_heads=[],
            )
        return _score_result(
            result="HALLUCINATION",
            hard_errors=sorted(set(hard_errors) | {"HALLUCINATION"}),
            missing_heads=[],
        )

    if answerability == "FALSE_PREMISE":
        corrected = adjudication.get("false_premise_corrected") is True
        if (
            corrected
            and answer["status"] != "ABSTAIN"
            and not hard_errors
            and not missing_heads
        ):
            return _score_result(
                result="FALSE_PREMISE_CORRECTED",
                hard_errors=[],
                missing_heads=[],
            )
        return _score_result(
            result="FALSE_PREMISE_ACCEPTED",
            hard_errors=sorted(set(hard_errors) | {"FALSE_PREMISE_ACCEPTED"}),
            missing_heads=missing_heads,
        )

    raise R2P0Error(f"GOLD_ANSWERABILITY_INVALID:{answerability}")


def _hard_error_result(hard_errors: Sequence[str]) -> str:
    present = set(hard_errors)
    for code in HARD_ERROR_PRIORITY:
        if code in present:
            return HARD_ERROR_RESULT_MAP[code]
    raise R2P0Error("HARD_ERROR_RESULT_MAPPING_MISSING")


def _score_result(
    *,
    result: str,
    hard_errors: Sequence[str],
    missing_heads: Sequence[str],
) -> dict[str, Any]:
    if result not in QUESTION_RESULTS:
        raise R2P0Error(f"QUESTION_RESULT_INVALID:{result}")
    return {
        "result": result,
        "full_supported": result in {
            "FULL_SUPPORTED",
            "FALSE_PREMISE_CORRECTED",
        },
        "hard_critical": bool(hard_errors),
        "hard_error_codes": list(hard_errors),
        "missing_head_ids": list(missing_heads),
        "semantic_truth_verified_by_program": False,
        "score_source": "ISOLATED_ADJUDICATION_TICKET",
    }


def normalized_chars(text: str) -> str:
    return "".join(
        char.lower()
        for char in text
        if char.isalnum() or "\u4e00" <= char <= "\u9fff"
    )


def char_ngrams(text: str, sizes: Sequence[int] = (2, 3)) -> Counter[str]:
    normalized = normalized_chars(text)
    grams: Counter[str] = Counter()
    for size in sizes:
        for start in range(max(0, len(normalized) - size + 1)):
            grams[normalized[start : start + size]] += 1
    return grams


def build_sparse_index(catalogs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    document_frequency: Counter[str] = Counter()
    for catalog in catalogs:
        for paragraph in catalog["paragraphs"]:
            grams = char_ngrams(paragraph["original_text"])
            document_frequency.update(grams)
            documents.append(
                {
                    "case_id": catalog["source_id"],
                    "paragraph_id": paragraph["paragraph_id"],
                    "char_start": paragraph["char_start"],
                    "char_end_exclusive": paragraph["char_end_exclusive"],
                    "char_count": len(paragraph["original_text"]),
                    "grams": dict(grams),
                }
            )
    result: dict[str, Any] = {
        "schema_version": "v02-r2-sparse-index.v1",
        "candidate_status": "candidate_silver_not_active",
        "method": "CHAR_2_3_GRAM_BM25_LIKE",
        "query_policy_payload_sha256": SPARSE_QUERY_POLICY[
            "policy_payload_sha256"
        ],
        "source_catalog_bindings": [
            {
                "source_id": catalog["source_id"],
                "source_body_sha256": catalog["source_body_sha256"],
                "catalog_payload_sha256": catalog[
                    "catalog_payload_sha256"
                ],
                "source_id_namespace": catalog["source_id_namespace"],
            }
            for catalog in catalogs
        ],
        "document_count": len(documents),
        "document_frequency": dict(document_frequency),
        "documents": documents,
    }
    result["index_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def rank_paragraphs(
    *,
    question_text: str,
    case_id: str,
    index: Mapping[str, Any],
) -> list[dict[str, Any]]:
    query = char_ngrams(question_text)
    case_docs = [row for row in index["documents"] if row["case_id"] == case_id]
    if not case_docs:
        raise R2P0Error(f"INDEX_CASE_MISSING:{case_id}")
    average_length = sum(sum(row["grams"].values()) for row in case_docs) / len(
        case_docs
    )
    total_documents = index["document_count"]
    doc_frequency = index["document_frequency"]
    scored: list[dict[str, Any]] = []
    for row in case_docs:
        frequencies = row["grams"]
        document_length = sum(frequencies.values())
        score = 0.0
        matched: list[str] = []
        for gram, query_frequency in query.items():
            term_frequency = frequencies.get(gram, 0)
            if not term_frequency:
                continue
            matched.append(gram)
            frequency = doc_frequency.get(gram, 0)
            inverse = math.log(1 + (total_documents - frequency + 0.5) / (frequency + 0.5))
            denominator = term_frequency + 1.2 * (
                0.25 + 0.75 * document_length / max(average_length, 1)
            )
            score += (
                inverse
                * term_frequency
                * 2.2
                / denominator
                * (1 + math.log1p(query_frequency))
            )
        scored.append(
            {
                "paragraph_id": row["paragraph_id"],
                "score": round(score, 8),
                "matched_grams": sorted(matched),
                "char_count": row["char_count"],
            }
        )
    return sorted(
        scored,
        key=lambda row: (-row["score"], row["paragraph_id"]),
    )


def sentence_to_paragraph(
    catalogs: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    return {
        accepted_source_id: row["paragraph_id"]
        for catalog in catalogs
        for row in catalog["sentences"]
        for accepted_source_id in row["accepted_legacy_source_ids"]
    }


def build_recall_curve(
    *,
    gold_v2: Mapping[str, Any],
    index: Mapping[str, Any],
    catalogs: Sequence[Mapping[str, Any]],
    k_values: Sequence[int] = (1, 2, 3, 5, 8, 10, 15),
) -> dict[str, Any]:
    source_to_paragraph = sentence_to_paragraph(catalogs)
    answerable_cells = [
        cell for cell in gold_v2["cells"] if cell["answerability"] == "ANSWERABLE"
    ]
    rankings = {
        cell["cell_id"]: rank_paragraphs(
            question_text=cell["question_text"],
            case_id=cell["case_id"],
            index=index,
        )
        for cell in answerable_cells
    }
    points: list[dict[str, Any]] = []
    for k in k_values:
        full_question_hits = 0
        head_hits = 0
        head_total = 0
        material_chars = 0
        for cell in answerable_cells:
            ranking = rankings[cell["cell_id"]][:k]
            retrieved = {row["paragraph_id"] for row in ranking}
            material_chars += sum(row["char_count"] for row in ranking)
            cell_complete = True
            for head in cell["required_heads"]:
                head_total += 1
                group_hits = []
                for source_group in head["source_id_groups"]:
                    paragraphs = {
                        source_to_paragraph[source_id]
                        for source_id in source_group
                        if source_id in source_to_paragraph
                    }
                    group_hits.append(bool(paragraphs & retrieved))
                head_complete = bool(group_hits) and all(group_hits)
                if head_complete:
                    head_hits += 1
                else:
                    cell_complete = False
            if cell_complete:
                full_question_hits += 1
        points.append(
            {
                "k": k,
                "answerable_question_count": len(answerable_cells),
                "full_question_recall_count": full_question_hits,
                "full_question_recall": round(
                    full_question_hits / max(len(answerable_cells), 1),
                    6,
                ),
                "required_head_count": head_total,
                "required_head_recall_count": head_hits,
                "required_head_recall": round(head_hits / max(head_total, 1), 6),
                "candidate_material_chars_total": material_chars,
                "candidate_material_chars_per_question": round(
                    material_chars / max(len(answerable_cells), 1),
                    2,
                ),
            }
        )
    result: dict[str, Any] = {
        "schema_version": "v02-r2-recall-curve.v1",
        "candidate_status": "candidate_silver_not_active",
        "diagnostic_only": True,
        "query_source": SPARSE_QUERY_POLICY["query_source"],
        "query_policy_payload_sha256": SPARSE_QUERY_POLICY[
            "policy_payload_sha256"
        ],
        "index_payload_sha256": index["index_payload_sha256"],
        "source_catalog_bindings": index["source_catalog_bindings"],
        "points": points,
        "interpretation_boundary": (
            "只测机械召回是否把旧 lockbox 所需来源段落送进候选；"
            "不等于作者问题已回答，也不验证证据语义承托。"
        ),
    }
    result["curve_payload_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def contract_bundle() -> dict[str, Any]:
    return {
        "schema_version": "v02-r2-p0-contract-bundle.v1",
        "answer_contract": {
            "schema_version": ANSWER_CONTRACT_SCHEMA_VERSION,
            "model_quote_allowed": False,
            "source_id_namespace": (
                "C15_LEGACY_SENTENCE_ID_ACCEPTED_AND_RESOLVED_TO_V2_SENTENCE"
            ),
            "paragraph_ids_are_retrieval_only_not_answer_source_ids": True,
            "status_enum": ["ANSWER", "PARTIAL", "ABSTAIN"],
            "status_is_candidate_self_label_not_score_authority": True,
            "claim_fields_exact": [
                "claim_id",
                "head_ids",
                "statement",
                "source_ids",
            ],
        },
        "adjudication_contract": {
            "schema_version": ADJUDICATION_SCHEMA_VERSION,
            "isolated_from_model": True,
            "head_check_fields": [
                "head_id",
                "fact_correct",
                "evidence_supports",
                "qualifiers_correct",
            ],
            "hard_error_codes": sorted(HARD_ERROR_CODES),
            "hard_error_result_map": HARD_ERROR_RESULT_MAP,
            "required_hash_bindings": [
                "gold_cell_payload_sha256",
                "answer_payload_sha256",
                "adjudicator_ticket_id",
                "adjudicator_ticket_receipt_sha256",
                "trusted_adjudicator_registry_file_sha256",
                "adjudicator_ticket_receipt_file_sha256",
                "scoring_executor_id",
            ],
            "trusted_registry_schema_version": (
                ADJUDICATOR_REGISTRY_SCHEMA_VERSION
            ),
            "ticket_receipt_schema_version": (
                ADJUDICATOR_TICKET_SCHEMA_VERSION
            ),
            "self_declared_ticket_is_score_authority": False,
        },
        "three_ledgers": LEDGER_SCHEMAS,
        "per_question_cost": [
            "question_id",
            "retrieval_elapsed_ms",
            "candidate_chars",
            "flash_attempts",
            "flash_tokens_known",
            "pro_attempts",
            "pro_tokens_known",
            "unknown_usage_attempts",
            "transport_failures",
            "total_elapsed_ms",
        ],
        "failure_codes": FAILURE_CODE_CONTRACT,
        "terminal_isolation": TERMINAL_ISOLATION_CONTRACT,
    }


def artifact_manifest(
    *,
    root: Path,
    schema_version: str,
    excluded_relative_paths: set[str] | None = None,
) -> dict[str, Any]:
    excluded_relative_paths = excluded_relative_paths or {"manifest.json"}
    root_resolved = root.resolve()
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise R2P0Error(
                f"ARTIFACT_MANIFEST_SYMLINK_FORBIDDEN:"
                f"{path.relative_to(root).as_posix()}"
            )
        if not path.resolve().is_relative_to(root_resolved):
            raise R2P0Error(
                f"ARTIFACT_MANIFEST_PATH_ESCAPE:"
                f"{path.relative_to(root).as_posix()}"
            )
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative not in excluded_relative_paths:
            records.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "schema_version": schema_version,
        "candidate_status": "candidate_silver_not_active",
        "file_count": len(records),
        "files": records,
    }
    manifest["manifest_payload_sha256"] = sha256_bytes(
        canonical_bytes(manifest)
    )
    return manifest


def _json_forbidden_hits(value: Any, *, path: str = "$") -> list[str]:
    forbidden_keys = {
        "semantic_statement",
        "formal_gold_claim_components",
        "gold_provenance",
        "required_heads",
        "source_id_groups",
        "migration_summary",
    }
    forbidden_string_fragments = {
        "config/gold/",
        "/formal_gold/",
        "question_gold_dev",
        "scoring_lockbox",
    }
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in forbidden_keys:
                hits.append(child_path)
            hits.extend(_json_forbidden_hits(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(
                _json_forbidden_hits(child, path=f"{path}[{index}]")
            )
    elif isinstance(value, str):
        for fragment in forbidden_string_fragments:
            if fragment in value:
                hits.append(f"{path}:contains:{fragment}")
    return hits


def verify_model_workspace_isolation(
    model_workspace: Path,
    *,
    trusted_manifest_file_sha256: str | None = None,
) -> dict[str, Any]:
    manifest_path = model_workspace / "manifest.json"
    if not manifest_path.is_file():
        raise R2P0Error("MODEL_WORKSPACE_MANIFEST_MISSING")
    root_resolved = model_workspace.resolve()
    for path in model_workspace.rglob("*"):
        relative = path.relative_to(model_workspace).as_posix()
        if path.is_symlink():
            raise R2P0Error(
                f"MODEL_WORKSPACE_SYMLINK_FORBIDDEN:{relative}"
            )
        if not path.resolve().is_relative_to(root_resolved):
            raise R2P0Error(
                f"MODEL_WORKSPACE_PATH_ESCAPE:{relative}"
            )
    actual_manifest_file_sha256 = sha256_file(manifest_path)
    if (
        trusted_manifest_file_sha256 is not None
        and actual_manifest_file_sha256 != trusted_manifest_file_sha256
    ):
        raise R2P0Error("MODEL_WORKSPACE_TRUSTED_MANIFEST_SHA_MISMATCH")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_paths = {row["path"] for row in manifest["files"]}
    actual_paths = {
        path.relative_to(model_workspace).as_posix()
        for path in model_workspace.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_paths != expected_paths:
        raise R2P0Error("MODEL_WORKSPACE_FILE_SET_MISMATCH")
    forbidden_path_fragments = {"gold", "lockbox"}
    for relative in actual_paths:
        lowered_parts = {part.lower() for part in Path(relative).parts}
        if lowered_parts & forbidden_path_fragments:
            raise R2P0Error(f"MODEL_WORKSPACE_FORBIDDEN_PATH:{relative}")
    forbidden_hits: list[str] = []
    for record in manifest["files"]:
        path = model_workspace / record["path"]
        if sha256_file(path) != record["sha256"]:
            raise R2P0Error(
                f"MODEL_WORKSPACE_FILE_SHA_MISMATCH:{record['path']}"
            )
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            forbidden_hits.extend(
                f"{record['path']}:{hit}"
                for hit in _json_forbidden_hits(value)
            )
    if forbidden_hits:
        raise R2P0Error(
            f"MODEL_WORKSPACE_GOLD_LEAK:{sorted(forbidden_hits)}"
        )
    payload_without_hash = dict(manifest)
    actual_payload_sha256 = payload_without_hash.pop(
        "manifest_payload_sha256",
        None,
    )
    expected_payload_sha256 = sha256_bytes(
        canonical_bytes(payload_without_hash)
    )
    if actual_payload_sha256 != expected_payload_sha256:
        raise R2P0Error("MODEL_WORKSPACE_MANIFEST_PAYLOAD_SHA_MISMATCH")
    return {
        "status": "PASS",
        "model_workspace_path": model_workspace.name,
        "file_count": len(actual_paths),
        "forbidden_gold_hit_count": 0,
        "manifest_payload_sha256": expected_payload_sha256,
        "manifest_file_sha256": actual_manifest_file_sha256,
        "trusted_manifest_binding_checked": (
            trusted_manifest_file_sha256 is not None
        ),
    }


def build_model_workspace(
    *,
    model_workspace: Path,
    catalogs: Sequence[Mapping[str, Any]],
    index: Mapping[str, Any],
) -> dict[str, Any]:
    for catalog in catalogs:
        write_json(
            model_workspace
            / "source_catalog_v2"
            / f"{catalog['source_id']}.json",
            catalog,
        )
    write_json(model_workspace / "retrieval/sparse_index.json", index)
    write_json(
        model_workspace / "contracts/contract_bundle.json",
        contract_bundle(),
    )
    write_json(
        model_workspace / "contracts/ledger_schemas.json",
        LEDGER_SCHEMAS,
    )
    write_json(
        model_workspace / "contracts/ledger_examples.json",
        ledger_examples(),
    )
    write_json(
        model_workspace / "contracts/sparse_query_policy.json",
        SPARSE_QUERY_POLICY,
    )
    manifest = artifact_manifest(
        root=model_workspace,
        schema_version="v02-r2-model-workspace-manifest.v1",
    )
    write_json(model_workspace / "manifest.json", manifest)
    manifest_file_sha256 = sha256_file(model_workspace / "manifest.json")
    return verify_model_workspace_isolation(
        model_workspace,
        trusted_manifest_file_sha256=manifest_file_sha256,
    )


def build_p0(
    *,
    repo: Path,
    output_dir: Path,
) -> dict[str, Any]:
    c15_catalog_dir = repo / "runs/V02_C15_pipeline_v1_r01_20260726/s0/source_catalogs"
    lockbox_path = (
        repo
        / "runs/V02_R1_route_comparison_r04_20260726/frozen/"
        "question_reference_map.lockbox.json"
    )
    old_catalog_paths = sorted(c15_catalog_dir.glob("*.json"))
    if len(old_catalog_paths) != 3:
        raise R2P0Error(f"EXPECTED_THREE_CATALOGS:{len(old_catalog_paths)}")
    old_catalogs = [
        json.loads(path.read_text(encoding="utf-8")) for path in old_catalog_paths
    ]
    lockbox = json.loads(lockbox_path.read_text(encoding="utf-8"))
    formal_gold_parts, formal_gold_receipts = load_formal_gold_parts(
        repo=repo,
        case_ids=[cell["case_id"] for cell in lockbox["cells"]],
    )
    required_part_ids = {
        part["part_id"]
        for cell in lockbox["cells"]
        for part in cell["required_parts"]
    }
    missing_formal_part_ids = sorted(required_part_ids - formal_gold_parts.keys())
    if missing_formal_part_ids:
        raise R2P0Error(
            f"FORMAL_GOLD_REQUIRED_PART_MISSING:{missing_formal_part_ids}"
        )
    formal_gold_subset_receipt = {
        "status": "PASS",
        "required_unique_part_count": len(required_part_ids),
        "matched_required_part_count": len(required_part_ids),
        "formal_gold_total_part_count": len(formal_gold_parts),
        "formal_gold_extra_part_count": len(
            formal_gold_parts.keys() - required_part_ids
        ),
        "claim_scope": (
            "只声明 R1 lockbox 必需的 48 个原子全部匹配；"
            "不声明 58 个正式金标原子全部进入本开发题集。"
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    new_catalogs = []
    catalog_receipts = []
    for old_catalog, source_path in zip(old_catalogs, old_catalog_paths, strict=True):
        catalog = build_source_catalog_v2(
            source_text=old_catalog["source_text"],
            source_id=old_catalog["source_id"],
            chapter=old_catalog["chapter"],
            run_id=output_dir.name,
            legacy_catalog=old_catalog,
        )
        new_catalogs.append(catalog)
        catalog_receipts.append(
            {
                "source_id": old_catalog["source_id"],
                "input_path": str(source_path.relative_to(repo)),
                "input_sha256": sha256_file(source_path),
                "old_sentence_count": len(old_catalog["sentences"]),
                "new_sentence_count": len(catalog["sentences"]),
                "new_catalog_payload_sha256": catalog[
                    "catalog_payload_sha256"
                ],
                "verification": verify_source_catalog_v2(catalog),
            }
        )
        write_json(
            output_dir / "source_catalog_v2" / f"{old_catalog['source_id']}.json",
            catalog,
        )

    source_id_compatibility = verify_lockbox_source_id_compatibility(
        lockbox=lockbox,
        catalogs=new_catalogs,
    )
    all_legacy_source_id_resolution = verify_all_legacy_source_id_resolution(
        legacy_catalogs=old_catalogs,
        new_catalogs=new_catalogs,
    )
    gold_v2 = migrate_r1_lockbox_to_dev_gold_v2(
        lockbox,
        formal_gold_parts=formal_gold_parts,
    )
    write_json(
        output_dir / "scoring_lockbox/question_gold_dev_v2.json",
        gold_v2,
    )
    index = build_sparse_index(new_catalogs)
    write_json(output_dir / "retrieval/sparse_index.json", index)
    curve = build_recall_curve(
        gold_v2=gold_v2,
        index=index,
        catalogs=new_catalogs,
    )
    write_json(output_dir / "retrieval/recall_curve.json", curve)
    write_json(output_dir / "contracts/contract_bundle.json", contract_bundle())
    write_json(output_dir / "contracts/failure_code_contract.json", FAILURE_CODE_CONTRACT)
    write_json(output_dir / "contracts/ledger_schemas.json", LEDGER_SCHEMAS)
    write_json(output_dir / "contracts/ledger_examples.json", ledger_examples())
    write_json(
        output_dir / "contracts/sparse_query_policy.json",
        SPARSE_QUERY_POLICY,
    )
    write_json(
        output_dir / "contracts/terminal_isolation_contract.json",
        TERMINAL_ISOLATION_CONTRACT,
    )
    isolation_receipt = build_model_workspace(
        model_workspace=output_dir / "model_workspace",
        catalogs=new_catalogs,
        index=index,
    )
    write_json(
        output_dir / "isolation/model_workspace_preflight_receipt.json",
        isolation_receipt,
    )

    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_status": "candidate_silver_not_active",
        "model_api_calls": 0,
        "network_calls": 0,
        "source_inputs": {
            "r1_lockbox_path": str(lockbox_path.relative_to(repo)),
            "r1_lockbox_sha256": sha256_file(lockbox_path),
            "external_review_path": (
                "/Users/a1234/Downloads/"
                "R2_小说事实材料管线_病根评审与施工蓝图_20260726.md"
            ),
            "external_review_sha256": (
                "22421fcee21546658b8871d34a7ea536"
                "53011e0ac1d72958d19dabdcd4c87b79"
            ),
            "formal_gold_inputs": formal_gold_receipts,
            "formal_gold_required_subset": formal_gold_subset_receipt,
            "c15_catalogs": catalog_receipts,
            "source_id_compatibility": source_id_compatibility,
            "all_legacy_source_id_resolution": (
                all_legacy_source_id_resolution
            ),
        },
        "gold_migration": gold_v2["migration_summary"],
        "recall_curve_payload_sha256": curve["curve_payload_sha256"],
        "failure_code_policy": "R2_NEW_CONTRACT_C15_UNCHANGED",
        "trusted_adjudicator_registry_required": True,
        "file_backed_adjudicator_registry_verifier_implemented": True,
        "terminal_freeze_total_gate_implemented": True,
        "semantic_truth_verified_by_program": False,
        "model_workspace_isolation_preflight": isolation_receipt,
        "p0_status": (
            "ENGINEERING_P0_PASS_SCORER_AND_ISOLATION_PREFLIGHT_READY_"
            "28_SCOREABLE_2_OPEN_UNRESOLVED"
        ),
    }
    write_json(output_dir / "p0_receipt.json", receipt)

    manifest = artifact_manifest(
        root=output_dir,
        schema_version="v02-r2-p0-manifest.v1",
    )
    write_json(output_dir / "manifest.json", manifest)
    return receipt


def _validation_command(
    *,
    repo: Path,
    command_id: str,
    argv: Sequence[str],
) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        list(argv),
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed_seconds = round(time.perf_counter() - started, 3)
    return {
        "command_id": command_id,
        "argv": list(argv),
        "exit_code": completed.returncode,
        "elapsed_seconds": elapsed_seconds,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_validation_suite(
    *,
    repo: Path,
    output_dir: Path,
    include_full_suite: bool,
) -> dict[str, Any]:
    source_path = Path(__file__).resolve()
    test_path = repo / "tests/test_v02_r2_question_driven_p0.py"
    related_tests = [
        "tests/test_v02_r1_route_runner.py",
        "tests/test_v02_c15_pipeline_v1.py",
        "tests/test_v02_r2_question_driven_p0.py",
        "tests/test_tool_registry.py",
    ]
    command_specs: list[tuple[str, list[str]]] = [
        (
            "ruff",
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                str(source_path.relative_to(repo)),
                str(test_path.relative_to(repo)),
            ],
        ),
        (
            "py_compile",
            [
                sys.executable,
                "-m",
                "py_compile",
                str(source_path.relative_to(repo)),
                str(test_path.relative_to(repo)),
            ],
        ),
        (
            "related_tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *related_tests,
            ],
        ),
    ]
    if include_full_suite:
        command_specs.append(
            (
                "full_suite",
                [sys.executable, "-m", "pytest", "-q"],
            )
        )
    results = [
        _validation_command(
            repo=repo,
            command_id=command_id,
            argv=argv,
        )
        for command_id, argv in command_specs
    ]
    status = (
        "PASS"
        if all(row["exit_code"] == 0 for row in results)
        else "FAIL"
    )
    receipt = {
        "schema_version": "v02-r2-p0-validation-receipt.v1",
        "candidate_status": "candidate_silver_not_active",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "model_api_calls": 0,
        "network_calls": 0,
        "source_sha256": sha256_file(source_path),
        "test_sha256": sha256_file(test_path),
        "full_suite_included": include_full_suite,
        "commands": results,
    }
    write_json(output_dir / "validation/validation_receipt.json", receipt)
    manifest = artifact_manifest(
        root=output_dir,
        schema_version="v02-r2-p0-manifest.v1",
    )
    write_json(output_dir / "manifest.json", manifest)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/V02_R2_question_driven_retrieval_p0_r04_20260726"),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="构建后运行固定机械验收，并把命令与结果写入运行目录。",
    )
    parser.add_argument(
        "--full-suite",
        action="store_true",
        help="与 --validate 一起使用时，额外运行整仓 pytest。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = Path(__file__).resolve().parents[2]
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo / output_dir
    receipt = build_p0(repo=repo, output_dir=output_dir)
    output: dict[str, Any] = {"build_receipt": receipt}
    if args.validate:
        validation = run_validation_suite(
            repo=repo,
            output_dir=output_dir,
            include_full_suite=args.full_suite,
        )
        output["validation_receipt"] = validation
        if validation["status"] != "PASS":
            print(json.dumps(output, ensure_ascii=False, indent=2))
            raise R2P0Error("VALIDATION_SUITE_FAILED")
    elif args.full_suite:
        raise R2P0Error("FULL_SUITE_REQUIRES_VALIDATE")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
