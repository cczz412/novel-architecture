"""Exact synthetic inputs for the CCZ-57 M3 B-02 fixture suite.

B-01 records are read from its merged ``OBJECT_SHAPES.json``.  This module
never manufactures a SegmentIndex, CandidateVersion, or LineageLocator.
The A admission and B-01 merge receipt are byte-identical fixture copies of
the repository-external receipts and are hashed before JSON parsing.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from b02_contracts import (
    CONTRACT_VERSION,
    EXPECTED_A_REVIEWED_HEAD,
    RUN_ACCESS,
    record_ref,
    sha256_value,
)

MODULE_ROOT = Path(__file__).resolve().parent
B01_OBJECT_SHAPES_PATH = (
    MODULE_ROOT.parent / "ccz57_m3_b01_candidate_version_r03_4" / "OBJECT_SHAPES.json"
)
A_ADMISSION_RECEIPT_PATH = MODULE_ROOT / "A_INTERFACE_ADMISSION_RECEIPT.fixture.json"
B01_MERGE_RECEIPT_PATH = MODULE_ROOT / "B01_MERGE_READBACK_RECEIPT.fixture.json"

NORMAL_FIXTURES = {
    "N-01": "writer identity original",
    "N-02": "open Diagnostic",
    "N-03": "SUPERSEDED lifecycle append",
    "N-04": "CLOSED lifecycle append",
    "N-05": "MATCHED Coverage",
    "N-06": "MISSING Coverage",
    "N-07": "PARTIAL Coverage",
    "N-08": "mixed open-Diagnostic projection",
    "N-09": "order-independent restart projection",
}

FAILURE_FIXTURES = {
    "F-01": "GLOBAL-A admission missing",
    "F-02": "GLOBAL-A admission drift",
    "F-03": "B-01 merge receipt missing",
    "F-04": "B-01 merge not reachable from current main",
    "F-05": "B-01 RecordRef drift",
    "F-06": "LineageLocator does not resolve",
    "F-07": "Diagnostic evidence outside CandidateVersion origin refs",
    "F-08": "Diagnostic immutable original overwrite",
    "F-09": "same immutable identity with different bytes",
    "F-10": "lifecycle duplicate-sequence conflict",
    "F-11": "lifecycle sequence or effective-time reversal",
    "F-12": "same lifecycle time with different event",
    "F-13": "lifecycle append after terminal event",
    "F-14": "revision or segment drift",
    "F-15": "invalid Coverage enum",
    "F-16": "Coverage attempts CandidateVersion or pointer write",
    "F-17": "write-set escape",
    "F-18": "network, model, subprocess, or dynamic runtime path",
}


def _seal_external_record(
    *,
    record_type: str,
    record_id: str,
    source_module: str,
    created_at: str,
    payload: dict[str, Any],
    expected_hash: str,
) -> dict[str, Any]:
    """Build one exact upstream immutable fixture without a B-02 writer."""
    record = {
        "contract": "M3_IMMUTABLE_RECORD",
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": source_module,
        "access": RUN_ACCESS,
        "retention_class": "CORE_IMMUTABLE_AUDIT",
        "created_at": created_at,
        "payload": deepcopy(payload),
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    if record["record_hash"] != expected_hash:
        raise AssertionError(
            f"exact upstream fixture hash drift: {record_type}:"
            f"{record['record_hash']}"
        )
    return record


def exact_a_reference_records() -> list[dict[str, Any]]:
    """Construct the exact A review and interface-manifest records."""
    review = _seal_external_record(
        record_type="A_EXACT_HEAD_REVIEW_RECEIPT",
        record_id="a_exact_review_9eafdac_20260828",
        source_module="A_REVIEW_IMPORT",
        created_at="2026-08-28T03:26:14Z",
        payload={
            "repository": "cczz412/novel-architecture",
            "pr_number": 186,
            "base_sha": "d4f0398cf9c7a0a1cb7c281adafdb91a40ff2000",
            "head_sha": EXPECTED_A_REVIEWED_HEAD,
            "review_result": "PASS",
            "source_file_sha256": (
                "267ce10e7612dc32df8d64b7a23cee3f30223195d01e1ec9f5ae32a72c21aa3f"
            ),
            "scope": "A_STAGE_EXACT_HEAD_MECHANICAL_REVIEW_ONLY",
        },
        expected_hash=(
            "7878b111cbc71b2f67710254015ecc327946190294f0a82e9ffb7dd9b0b6d75c"
        ),
    )
    manifest = _seal_external_record(
        record_type="A_INTERFACE_MANIFEST",
        record_id="a_interface_manifest_main_019df751_20260828",
        source_module="A_INTERFACE_MANIFEST_READER",
        created_at="2026-08-28T03:26:14Z",
        payload={
            "repository": "cczz412/novel-architecture",
            "issue_number": 176,
            "interface_names": [
                "RawAttempt",
                "ProviderTurn",
                "MechanicalGate",
                "C3Preview",
            ],
            "manifest_mode": "MERGED_CURRENT_MAIN_READBACK",
        },
        expected_hash=(
            "80751b702a335e1b733e975ac3905512ac54ec9f8f47922e2f975564542aeaa7"
        ),
    )
    return [review, manifest]


def exact_b01_objects() -> dict[str, Any]:
    """Read, select, and return B-01 exact objects from the merged catalog."""
    catalog = json.loads(B01_OBJECT_SHAPES_PATH.read_text(encoding="utf-8"))
    records = catalog["immutable_records"]
    candidate = next(
        item for item in records if item["record_type"] == "M3_CANDIDATE_VERSION"
    )
    segment = next(
        item
        for item in records
        if item["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT"
    )
    locator = catalog["lineage_locator_example"]
    if locator["candidate_version_ref"] != record_ref(candidate):
        raise AssertionError("B-01 locator does not reference the exact CandidateVersion")
    return {
        "catalog_path": B01_OBJECT_SHAPES_PATH,
        "segment_index": deepcopy(segment),
        "candidate_version": deepcopy(candidate),
        "lineage_locators": [deepcopy(locator)],
    }


def exact_upstream_fixture() -> dict[str, Any]:
    """Return every exact upstream input needed to open B-02 writers."""
    b01 = exact_b01_objects()
    a_records = exact_a_reference_records()
    return {
        "admission_bytes": A_ADMISSION_RECEIPT_PATH.read_bytes(),
        "merge_receipt_bytes": B01_MERGE_RECEIPT_PATH.read_bytes(),
        "reference_records": [
            *deepcopy(a_records),
            deepcopy(b01["segment_index"]),
            deepcopy(b01["candidate_version"]),
        ],
        "lineage_locators": deepcopy(b01["lineage_locators"]),
    }


def deterministic_sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def diagnostic_kwargs(
    fixture_id: str,
    upstream_context: dict[str, Any],
    writer_identity_ref: dict[str, Any],
    *,
    axis: str = "FACT_COMPLETENESS",
    severity: str = "WARNING",
    created_at: str = "2026-08-28T12:10:00Z",
) -> dict[str, Any]:
    """Build deterministic current-API arguments for one Diagnostic fixture."""
    return {
        "axis": axis,
        "severity": severity,
        "lineage_locator": deepcopy(upstream_context["lineage_locators"][0]),
        "evidence_refs": deepcopy(upstream_context["origin_attempt_refs"]),
        "fingerprint": deterministic_sha(f"{fixture_id}:diagnostic"),
        "writer_identity_ref": deepcopy(writer_identity_ref),
        "created_at": created_at,
    }


def coverage_kwargs(
    fixture_id: str,
    writer_identity_ref: dict[str, Any],
    candidate_match: str,
    *,
    created_at: str = "2026-08-28T12:20:00Z",
) -> dict[str, Any]:
    """Build deterministic current-API arguments for one Coverage fixture."""
    return {
        "source_observation_id": f"{fixture_id.lower()}-observation",
        "source_span_hash": deterministic_sha(f"{fixture_id}:source-span"),
        "axis": "FACT_COMPLETENESS",
        "candidate_match": candidate_match,
        "observer_ref": deepcopy(writer_identity_ref),
        "created_at": created_at,
    }


def reseal_record(record: dict[str, Any]) -> dict[str, Any]:
    """Re-hash a deliberately mutated record so tests reach the intended gate."""
    mutated = deepcopy(record)
    mutated["record_hash"] = sha256_value(
        {key: value for key, value in mutated.items() if key != "record_hash"}
    )
    return mutated
