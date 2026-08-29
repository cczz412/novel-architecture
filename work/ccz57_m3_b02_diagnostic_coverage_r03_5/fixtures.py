"""Exact synthetic B-01 r03.5 inputs and deterministic B-02 arguments."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from b02_contracts import CONTRACT_VERSION, record_ref, sha256_value
from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (
    CandidateVersionStore,
)

MODULE_ROOT = Path(__file__).resolve().parent
B01_ROOT = MODULE_ROOT.parent / "ccz57_m3_b01_candidate_version_r03_5"
B01_OBJECT_SHAPES_PATH = B01_ROOT / "OBJECT_SHAPES.json"
B01_MANIFEST_PATH = B01_ROOT / "MANIFEST.sha256"
LEGACY_B02_ROOT = MODULE_ROOT.parent / "ccz57_m3_b02_diagnostic_coverage_r03_4"

RESPONSIBILITY_TEXT_1 = "甲走进北塔。甲拿起铜钥匙。甲走进北塔。"
RESPONSIBILITY_TEXT_2 = "乙停在门外。"
SOURCE_MATCHED = "甲走进北塔。"
SOURCE_PARTIAL = "甲走进北塔。甲拿起铜钥匙。"
SOURCE_MISSING = "甲拿起铜钥匙。甲走进北塔。"

NORMAL_FIXTURES = {
    "N-01": "writer identity original",
    "N-02": "entry-level Diagnostic with LineageLocator + EvidenceLocator",
    "N-03": "append-only lifecycle and immutable Diagnostic original",
    "N-04": "MATCHED Coverage with one exact locator pair",
    "N-05": "PARTIAL Coverage with source evidence and matched locator pair",
    "N-06": "MISSING Coverage with source evidence and zero matched refs",
    "N-07": "open issue projection with locator summaries and no prose",
    "N-08": "idempotent atomic restart readback",
    "N-09": "decomposed Unicode source evidence canonical round trip",
}

FAILURE_FIXTURES = {
    "F-01": "r03.3 CandidateVersion rejected by r03.5 admission",
    "F-02": "Diagnostic EvidenceLocator missing gives zero writes",
    "F-03": "Diagnostic locator pair from different lineages rejected",
    "F-04": "MISSING rejects any matched locator",
    "F-05": "PARTIAL and MATCHED require a matched locator pair",
    "F-06": "source evidence outside exact chapter rejected",
    "F-07": "source evidence hash or byte location drift rejected",
    "F-08": "CandidateVersion ref/revision/contract drift rejected",
    "F-09": "immutable overwrite and hash collision rejected",
    "F-10": "lifecycle order, time, duplicate, and terminal errors rejected",
    "F-11": "transaction failure leaves zero pending bytes",
    "F-12": "write-set, model, network, subprocess, real novel, Patch blocked",
}


def deterministic_sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def segment_inputs() -> list[dict[str, Any]]:
    first_end = len(RESPONSIBILITY_TEXT_1.encode("utf-8"))
    second_end = first_end + len(RESPONSIBILITY_TEXT_2.encode("utf-8"))
    return [
        {
            "seg": 1,
            "start_byte": 0,
            "end_byte": first_end,
            "responsibility_text": RESPONSIBILITY_TEXT_1,
        },
        {
            "seg": 2,
            "start_byte": first_end,
            "end_byte": second_end,
            "responsibility_text": RESPONSIBILITY_TEXT_2,
        },
    ]


def exact_b01_objects() -> dict[str, Any]:
    """Read exact merged B-01 objects; never manufacture a CandidateVersion."""

    catalog = json.loads(B01_OBJECT_SHAPES_PATH.read_text(encoding="utf-8"))
    if (
        catalog["catalog_version"] != CONTRACT_VERSION
        or catalog["candidate_schema_id"] != "novel-fact-extraction-v2.1"
    ):
        raise AssertionError("B-01 r03.5 catalog identity drift")
    records = catalog["immutable_records"]
    candidate = next(
        item for item in records if item["record_type"] == "M3_CANDIDATE_VERSION"
    )
    segment = next(
        item
        for item in records
        if item["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT"
    )
    references = deepcopy(catalog["reference_records"])
    locator_references = [*references, deepcopy(segment)]
    lineage_locators: list[dict[str, Any]] = []
    evidence_locators: list[dict[str, Any]] = []
    for item in candidate["payload"]["items"]:
        lineage_locators.append(
            CandidateVersionStore.lineage_locator(
                candidate,
                item["lineage_id"],
                reference_records=locator_references,
            )
        )
        evidence_locators.append(
            CandidateVersionStore.evidence_locator(
                candidate,
                item["lineage_id"],
                reference_records=locator_references,
            )
        )
    if lineage_locators[0] != catalog["lineage_locator_example"]:
        raise AssertionError("B-01 LineageLocator example drift")
    if evidence_locators[0] != catalog["evidence_locator_example"]:
        raise AssertionError("B-01 EvidenceLocator example drift")
    return {
        "reference_records": references,
        "segment_index": deepcopy(segment),
        "candidate_version": deepcopy(candidate),
        "lineage_locators": lineage_locators,
        "evidence_locators": evidence_locators,
        "segment_inputs": segment_inputs(),
    }


def exact_upstream_fixture() -> dict[str, Any]:
    return exact_b01_objects()


def matched_pair(context: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return {
        "lineage_locator": deepcopy(context["lineage_locators"][index]),
        "evidence_locator": deepcopy(context["evidence_locators"][index]),
    }


def diagnostic_kwargs(
    fixture_id: str,
    context: dict[str, Any],
    writer_identity_ref: dict[str, Any],
    *,
    locator_index: int = 0,
    axis: str = "FACT_COMPLETENESS",
    severity: str = "WARNING",
    created_at: str = "2026-08-29T04:10:00Z",
) -> dict[str, Any]:
    return {
        "axis": axis,
        "severity": severity,
        "lineage_locator": deepcopy(context["lineage_locators"][locator_index]),
        "evidence_locator": deepcopy(context["evidence_locators"][locator_index]),
        "fingerprint": deterministic_sha(f"{fixture_id}:diagnostic"),
        "writer_identity_ref": deepcopy(writer_identity_ref),
        "created_at": created_at,
    }


def coverage_kwargs(
    fixture_id: str,
    context: dict[str, Any],
    writer_identity_ref: dict[str, Any],
    candidate_match: str,
    *,
    source_evidence: str | None = None,
    matched_indices: tuple[int, ...] | None = None,
    created_at: str = "2026-08-29T04:20:00Z",
) -> dict[str, Any]:
    if source_evidence is None:
        source_evidence = {
            "MATCHED": SOURCE_MATCHED,
            "PARTIAL": SOURCE_PARTIAL,
            "MISSING": SOURCE_MISSING,
        }[candidate_match]
    if matched_indices is None:
        matched_indices = () if candidate_match == "MISSING" else (0,)
    return {
        "source_observation_id": f"{fixture_id.lower()}-observation",
        "source_evidence": source_evidence,
        "axis": "FACT_COMPLETENESS",
        "candidate_match": candidate_match,
        "matched_candidate_bindings": [
            matched_pair(context, index) for index in matched_indices
        ],
        "observer_ref": deepcopy(writer_identity_ref),
        "created_at": created_at,
    }


def reseal_record(record: dict[str, Any]) -> dict[str, Any]:
    mutated = deepcopy(record)
    mutated["record_hash"] = sha256_value(
        {key: value for key, value in mutated.items() if key != "record_hash"}
    )
    return mutated


def upstream_identity_summary() -> dict[str, Any]:
    upstream = exact_upstream_fixture()
    candidate = upstream["candidate_version"]
    return {
        "candidate_version_ref": record_ref(candidate),
        "chapter_revision_ref": deepcopy(candidate["payload"]["chapter_revision_ref"]),
        "candidate_schema_id": candidate["payload"]["candidate_schema_id"],
        "lineage_locator_hashes": [
            locator["locator_hash"] for locator in upstream["lineage_locators"]
        ],
        "evidence_locator_hashes": [
            locator["locator_hash"] for locator in upstream["evidence_locators"]
        ],
    }
