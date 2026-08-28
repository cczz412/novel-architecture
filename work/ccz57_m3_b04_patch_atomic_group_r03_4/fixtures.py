"""Pure synthetic fixtures for the CCZ-57 M3 B-04 contract."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from b04_contracts import (
    CONTRACT_VERSION,
    FIXTURE_ACCESS,
    IMMUTABLE_CONTRACT,
    RETENTION_CLASS,
    SOURCE_MODULE,
    sha256_value,
)

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
FIXED = CATALOG["fixed_vectors"]
B03_CATALOG = CATALOG["b03_record_ref_catalog"]
NEGATIVE_SOURCE_SLICE = CATALOG["negative_source_slice_fixtures"]

CREATED_AT = "2026-08-28T07:30:00Z"
REVISION = {
    "chapter_id": "fixture-c01",
    "revision_no": 2,
    "revision_text_sha256": "1" * 64,
}
ATTEMPT_REF = {
    "contract": "M3_RECORD_REF",
    "contract_version": CONTRACT_VERSION,
    "record_type": "A_RAW_ATTEMPT_RECEIPT",
    "record_id": "attempt_fixture_001",
    "record_version": 1,
    "record_contract_version": CONTRACT_VERSION,
    "record_hash": "cd541e3c19f34ba05c60682ec9f7c752afa1b8577c6402f56bc260abd21e6f25",
    "access": FIXTURE_ACCESS,
    "source_module": "A_STAGE_FIXTURE",
}


def _immutable(
    *,
    record_type: str,
    record_id: str,
    record_version: int,
    source_module: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": record_version,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": source_module,
        "access": FIXTURE_ACCESS,
        "retention_class": RETENTION_CLASS,
        "created_at": CREATED_AT,
        "payload": payload,
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    return record


BASE = _immutable(
    record_type="M3_CANDIDATE_VERSION",
    record_id="cv_fixture_parent",
    record_version=3,
    source_module=SOURCE_MODULE,
    payload={
        "chapter_revision_ref": deepcopy(REVISION),
        "seg": 1,
        "parent_candidate_version_ref": None,
        "origin_attempt_refs": [deepcopy(ATTEMPT_REF)],
        "origin_commit_intent_ref": None,
        "items": [
            {
                "lineage_id": "lin_fact_001",
                "text": "角色甲进入北塔。",
                "quote": "角色甲走进北塔。",
                "item_hash": "4e3b0c357533bf3384927e89eef01268ec99cef732643bd4d854636c9dac8ea6",
            },
            {
                "lineage_id": "lin_fact_002",
                "text": "角色甲持有一把铜钥匙。",
                "quote": "铜钥匙在角色甲手中。",
                "item_hash": "5fab26a641f3e8788268ff01ebfcf5f584e113b95d13cf0521b346a916580547",
            },
        ],
        "lineage_index": [
            {
                "lineage_id": "lin_fact_001",
                "json_pointer": "/items/0",
                "item_hash": "4e3b0c357533bf3384927e89eef01268ec99cef732643bd4d854636c9dac8ea6",
            },
            {
                "lineage_id": "lin_fact_002",
                "json_pointer": "/items/1",
                "item_hash": "5fab26a641f3e8788268ff01ebfcf5f584e113b95d13cf0521b346a916580547",
            },
        ],
        "version_payload_hash": "27495dc404c3448063651be0672487332700c1624c14338a1e1712b995a0da7f",
    },
)
assert (
    BASE["record_hash"]
    == "64405e245bd4e1d758f3848984e318acfd7912c48558f81e3aee1318eeb88f26"
)

BASE_REF = {
    "contract": "M3_RECORD_REF",
    "contract_version": CONTRACT_VERSION,
    "record_type": "M3_CANDIDATE_VERSION",
    "record_id": "cv_fixture_parent",
    "record_version": 3,
    "record_contract_version": CONTRACT_VERSION,
    "record_hash": BASE["record_hash"],
    "access": FIXTURE_ACCESS,
    "source_module": SOURCE_MODULE,
}
LOCATOR_1 = {
    "contract": "M3_LINEAGE_LOCATOR",
    "contract_version": CONTRACT_VERSION,
    "candidate_version_ref": deepcopy(BASE_REF),
    "lineage_id": "lin_fact_001",
    "json_pointer": "/items/0",
    "item_hash": BASE["payload"]["items"][0]["item_hash"],
    "locator_hash": "f43f65f5435f6b7cedb4ddcc3078e9437fbf58d17a8885e3b2427e2793a0180d",
}
LOCATOR_2 = {
    "contract": "M3_LINEAGE_LOCATOR",
    "contract_version": CONTRACT_VERSION,
    "candidate_version_ref": deepcopy(BASE_REF),
    "lineage_id": "lin_fact_002",
    "json_pointer": "/items/1",
    "item_hash": BASE["payload"]["items"][1]["item_hash"],
    "locator_hash": "febc1b3b6e2b01b137548526ecac80f39471334b27c74c211a7d918799d06451",
}

IDENTITY_REF = {
    "contract": "M3_RECORD_REF",
    "contract_version": CONTRACT_VERSION,
    "record_type": "M3_DIAGNOSTIC_RECORDER_IDENTITY",
    "record_id": "diagnostic_recorder_fixture_001",
    "record_version": 1,
    "record_contract_version": CONTRACT_VERSION,
    "record_hash": "3a65907eb71a54223ecc1e3a4ba314daaeabdd900cf186ecd93e7aa46ed51afc",
    "access": FIXTURE_ACCESS,
    "source_module": SOURCE_MODULE,
}
DIAGNOSTIC = _immutable(
    record_type="M3_DIAGNOSTIC",
    record_id="diag_fixture_001",
    record_version=1,
    source_module=SOURCE_MODULE,
    payload={
        "base_candidate_version_ref": deepcopy(BASE_REF),
        "chapter_revision_ref": deepcopy(REVISION),
        "seg": 1,
        "axis": "TEMPORAL_STATE",
        "severity": "BLOCKING",
        "target": {"kind": "LINEAGE", "lineage_locator": deepcopy(LOCATOR_1)},
        "evidence_refs": [deepcopy(ATTEMPT_REF)],
        "fingerprint": "fd7620218596b314a9d65d58c7c2a53333b41aabb78347bd4bf7ddeb7a2bcae3",
        "writer_identity_ref": deepcopy(IDENTITY_REF),
    },
)
assert (
    DIAGNOSTIC["record_hash"]
    == "04d20c2cb2bf866a96e4bd35ef06b1629e60a3a39c05d32ab0a87254690ca0bc"
)

COVERAGE = _immutable(
    record_type="M3_COVERAGE_OBSERVATION",
    record_id="coverage_fixture_001",
    record_version=1,
    source_module=SOURCE_MODULE,
    payload={
        "base_candidate_version_ref": deepcopy(BASE_REF),
        "chapter_revision_ref": deepcopy(REVISION),
        "seg": 1,
        "source_observation_id": "obs-fixture-seg1-001",
        "source_span_hash": "9" * 64,
        "axis": "EXPLICIT_FACT_RECALL",
        "candidate_match": "PARTIAL",
        "observer_ref": deepcopy(IDENTITY_REF),
    },
)
assert (
    COVERAGE["record_hash"]
    == "5726950bb7991803d5aaa4d71c6ad558297bffaba25c3354f3cc5e51c9aae0f2"
)

POLICY = _immutable(
    record_type="M3_PROTECTION_POLICY",
    record_id="protection_policy_fixture_001",
    record_version=1,
    source_module="POLICY_FIXTURE_REGISTRY",
    payload={
        "policy_revision": 1,
        "protect_untouched_fields": True,
        "protect_accepted_lineage": True,
    },
)
assert (
    POLICY["record_hash"]
    == "4921b413800d148200aefd9ad6cebbe80dfd9dacea539655bd843f361e8d3346"
)


NORMAL_FIXTURE_DEFINITIONS = [
    {"id": "N-01", "purpose": "no SourceSlice exact fixed vector"},
    {"id": "N-02", "purpose": "single REPLACE_FIELD"},
    {"id": "N-03", "purpose": "single ADD_CANDIDATE_ITEM"},
    {"id": "N-04", "purpose": "independent replace and add groups"},
    {"id": "N-05", "purpose": "exact ProtectionSet complement"},
    {"id": "N-06", "purpose": "empty SourceSlice route"},
    {"id": "N-07", "purpose": "B-03 R02 exact SourceSlice ref route"},
    {"id": "N-08", "purpose": "noncommittable causal sidecar"},
    {"id": "N-09", "purpose": "idempotent route replay"},
    {"id": "N-10", "purpose": "100 deterministic projections"},
]

FAILURE_FIXTURE_DEFINITIONS = [
    {"id": "F-01", "error": "B04_ADMISSION_FAILED", "purpose": "A or B-01 drift"},
    {
        "id": "F-02",
        "error": "B04_B02_NOT_MERGED",
        "purpose": "Draft head used as merge",
    },
    {
        "id": "F-03",
        "error": "B04_B02_READBACK_FAILED",
        "purpose": "tree or receipt drift",
    },
    {
        "id": "F-04",
        "error": "B04_UPSTREAM_OBJECT_INVALID",
        "purpose": "Diagnostic or Coverage drift",
    },
    {
        "id": "F-05",
        "error": "B04_IMMUTABLE_SHAPE_INVALID",
        "purpose": "canonical or envelope drift",
    },
    {
        "id": "F-06",
        "error": "B04_LINEAGE_LOCATOR_INVALID",
        "purpose": "RecordRef or locator drift",
    },
    {
        "id": "F-07",
        "error": "B04_PROTECTION_POLICY_INVALID",
        "purpose": "policy disabled or drifted",
    },
    {
        "id": "F-08",
        "error": "B04_PROTECTION_COMPLEMENT_MISMATCH",
        "purpose": "ProtectionSet mismatch",
    },
    {
        "id": "F-09",
        "error": "B04_PROTECTED_TARGET_OVERLAP",
        "purpose": "write hits protected value",
    },
    {
        "id": "F-10",
        "error": "B04_PATCH_PAYLOAD_INVALID",
        "purpose": "Patch shape drift",
    },
    {
        "id": "F-11",
        "error": "SOURCE_SLICE_RECORD_REF_MISMATCH",
        "purpose": "unapproved SourceSlice",
    },
    {
        "id": "F-12",
        "error": "B04_REPLACE_TARGET_INVALID",
        "purpose": "replace grammar drift",
    },
    {
        "id": "F-13",
        "error": "B04_ADD_COVERAGE_REQUIRED",
        "purpose": "add without missing coverage",
    },
    {
        "id": "F-14",
        "error": "FORBIDDEN_COMMITTABLE_OPERATION",
        "purpose": "causal operation",
    },
    {
        "id": "F-15",
        "error": "B04_OPERATION_DUPLICATE",
        "purpose": "operation copied between groups",
    },
    {
        "id": "F-16",
        "error": "B04_ATOMIC_GROUP_HASH_MISMATCH",
        "purpose": "group identity drift",
    },
    {
        "id": "F-17",
        "error": "B04_CROSS_GROUP_TARGET_OVERLAP",
        "purpose": "cross-group overlap",
    },
    {
        "id": "F-18",
        "error": "B04_CROSS_GROUP_DEPENDENCY",
        "purpose": "cross-group dependency",
    },
    {
        "id": "F-19",
        "error": "B04_CAUSAL_MUST_BE_NONCOMMITTABLE",
        "purpose": "committable causal sidecar",
    },
    {
        "id": "F-20",
        "error": "B04_PREVIEW_B05_REFERENCE_FORBIDDEN",
        "purpose": "B-05 output in Preview",
    },
    {
        "id": "F-21",
        "error": "B04_PREVIEW_PERSISTENCE_FORBIDDEN",
        "purpose": "persisted Preview",
    },
    {
        "id": "F-22",
        "error": "B04_IMMUTABLE_IDENTITY_COLLISION",
        "purpose": "identity conflict or crash",
    },
    {
        "id": "F-23",
        "error": "B04_SELF_CHECK_FAILED",
        "purpose": "write set or writer drift",
    },
    {
        "id": "F-24",
        "error": "B04_RUNTIME_EVENT_FORBIDDEN",
        "purpose": "network, process, or novel event",
    },
    {
        "id": "F-25",
        "error": "STALE_SOURCE_SLICE_REF",
        "purpose": "R03.4 stale SourceSlice ref",
    },
    {
        "id": "F-26",
        "error": "SOURCE_SLICE_RECORD_REF_MISMATCH",
        "purpose": "hash-only SourceSlice splice",
    },
    {
        "id": "F-27",
        "error": "SOURCE_SLICE_RECORD_REF_MISMATCH",
        "purpose": "nine one-field SourceSlice drifts",
    },
    {
        "id": "F-28",
        "error": "SOURCE_SLICE_REVISION_MISMATCH",
        "purpose": "SourceSlice revision drift",
    },
    {
        "id": "F-29",
        "error": "B03_ACCESS_FORBIDDEN",
        "purpose": "B-03 writer or content read",
    },
]

F27_FIELDS = [
    "contract",
    "contract_version",
    "record_type",
    "record_id",
    "record_version",
    "record_contract_version",
    "record_hash",
    "access",
    "source_module",
]
FAILURE_EXECUTION_IDS = [
    *[
        item["id"]
        for item in FAILURE_FIXTURE_DEFINITIONS
        if item["id"] not in {"F-27", "F-29"}
    ],
    *[f"F-27.{field}" for field in F27_FIELDS],
    "F-29.writer_call",
    "F-29.content_read",
]
assert len(NORMAL_FIXTURE_DEFINITIONS) == 10
assert len(FAILURE_FIXTURE_DEFINITIONS) == 29
assert len(FAILURE_EXECUTION_IDS) == 38


def route_inputs(route_name: str) -> dict[str, Any]:
    route = FIXED["routes"][route_name]
    source_refs = route["patch_proposal_record"]["payload"][
        "authorized_source_slice_refs"
    ]
    return {
        "base": deepcopy(BASE),
        "policy": deepcopy(POLICY),
        "diagnostics": [deepcopy(DIAGNOSTIC)],
        "coverages": [deepcopy(COVERAGE)],
        "source_slice_refs": deepcopy(source_refs),
        "source_slice_revision": deepcopy(REVISION) if source_refs else None,
        "groups": deepcopy(FIXED["shared_unaffected"]["atomic_groups"]),
        "causal_payloads": [deepcopy(route["causal_hint_proposal_record"]["payload"])],
        "created_at": CREATED_AT,
        "access": FIXTURE_ACCESS,
    }


def fixed_route(route_name: str) -> dict[str, Any]:
    return deepcopy(FIXED["routes"][route_name])
