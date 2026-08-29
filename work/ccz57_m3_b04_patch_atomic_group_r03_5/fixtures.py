"""Synthetic B-01/B-02 r03.5 inputs for B-04 full-item Patch tests."""

from __future__ import annotations

import hashlib
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = MODULE_ROOT.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from b04_contracts import (  # noqa: E402
    CONTRACT_VERSION,
    FIXTURE_ACCESS,
    IMMUTABLE_CONTRACT,
    RETENTION_CLASS,
    SOURCE_MODULE,
    _binding_from_coverage,
    canonical_bytes,
    proposed_add_lineage_id,
    record_ref,
    sha256_value,
)
from work.ccz57_m3_b02_diagnostic_coverage_r03_5 import (  # noqa: E402
    b02_contracts as _b02_contracts_module,
)

sys.modules.setdefault("b02_contracts", _b02_contracts_module)

from work.ccz57_m3_b02_diagnostic_coverage_r03_5.b02_store import (  # noqa: E402
    B02Service,
    CoverageRecorder,
    DiagnosticLifecycleWriter,
    DiagnosticRecorder,
    DiagnosticRecorderIdentityRegistry,
    FixtureStore as B02FixtureStore,
)
from work.ccz57_m3_b02_diagnostic_coverage_r03_5.fixtures import (  # noqa: E402
    SOURCE_MISSING,
    SOURCE_PARTIAL,
    coverage_kwargs,
    diagnostic_kwargs,
    exact_upstream_fixture,
)
from work.ccz57_m3_b03_bound_evidence_read_r03_5 import (  # noqa: E402
    b03_contracts as _b03_contracts_module,
)

sys.modules.setdefault("b03_contracts", _b03_contracts_module)

B03_MODULE_ROOT = MODULE_ROOT.parent / "ccz57_m3_b03_bound_evidence_read_r03_5"
if str(B03_MODULE_ROOT) not in sys.path:
    sys.path.append(str(B03_MODULE_ROOT))

from work.ccz57_m3_b03_bound_evidence_read_r03_5.b03_contracts import (  # noqa: E402
    make_input_record as b03_make_input_record,
    record_ref as b03_record_ref,
)
from work.ccz57_m3_b03_bound_evidence_read_r03_5.service import (  # noqa: E402
    B03Service,
)

CREATED_AT = "2026-08-30T02:10:00Z"
IDENTITY_CREATED_AT = "2026-08-30T02:00:00Z"

NORMAL_FIXTURES = {
    "N-01": "Diagnostic-only replacement keeps exact bound evidence",
    "N-02": "MISSING Coverage authorizes a complete added item",
    "N-03": "PARTIAL Coverage authorizes replacement evidence change",
    "N-04": "replacement and add groups preview independently",
    "N-05": "ProtectionSet equals untouched complete-item set",
    "N-06": "B-03 absence does not block Coverage Patch",
    "N-07": "Coverage provenance persists in Patch original",
    "N-08": "noncommittable causal sidecar remains separate",
    "N-09": "idempotent replay returns identical RecordRefs",
    "N-10": "Preview contains complete item summaries and no B-05 result",
}

FAILURE_FIXTURES = {
    "F-01": "legacy contract or operation rejected",
    "F-02": "replacement old item hash drift rejected",
    "F-03": "replacement Diagnostic missing or wrong target rejected",
    "F-04": "terminal Diagnostic rejected",
    "F-05": "replacement evidence change without Coverage rejected",
    "F-06": "replacement Coverage evidence drift rejected",
    "F-07": "add without Coverage rejected",
    "F-08": "MATCHED Coverage cannot authorize add",
    "F-09": "add evidence or binding drift rejected",
    "F-10": "caller-chosen add lineage rejected",
    "F-11": "incomplete item and item_hash injection rejected",
    "F-12": "group hash, duplicate or overlap drift rejected",
    "F-13": "ProtectionSet complement drift rejected",
    "F-14": "unused top-level Diagnostic or Coverage rejected",
    "F-15": "mixed base or candidate schema rejected",
    "F-16": "causal sidecar must remain noncommittable",
    "F-17": "Preview persistence and B-05 calls rejected",
    "F-18": "transaction failures leave visible store unchanged",
    "F-19": "write-set escape and forbidden runtime events rejected",
    "F-20": "SourceSlice cannot replace Coverage for new evidence",
    "F-21": "revoked B-03 SourceSlice fails before B-04 publish",
    "F-22": "B-02 state change fails at the publish linearization guard",
}


def _immutable(
    *, record_type: str, record_id: str, payload: dict[str, Any], created_at: str
) -> dict[str, Any]:
    record = {
        "contract": IMMUTABLE_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": "",
        "source_module": SOURCE_MODULE,
        "access": FIXTURE_ACCESS,
        "retention_class": RETENTION_CLASS,
        "created_at": created_at,
        "payload": deepcopy(payload),
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    return record


def policy_record() -> dict[str, Any]:
    return _immutable(
        record_type="M3_PROTECTION_POLICY",
        record_id="m3-protection-policy-r03.5",
        created_at=IDENTITY_CREATED_AT,
        payload={
            "policy_revision": "r03.5-full-item",
            "protect_untouched_items": True,
            "protect_accepted_lineage": True,
        },
    )


def bound_recheck_stack(root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Build one authoritative live B-03 recheck; no free range exists."""

    runtime_root = (
        B03_MODULE_ROOT
        / ".pytest-runtime-b04"
        / hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]
    )
    context = data["context"]
    candidate = context["candidate_version"]
    item = candidate["payload"]["items"][0]
    subject = {
        "kind": "CANDIDATE_FACT",
        "candidate_version_ref": record_ref(candidate),
        "lineage_locator": deepcopy(context["lineage_locators"][0]),
        "evidence_locator": deepcopy(context["evidence_locators"][0]),
        "item_hash": item["item_hash"],
        "source_revision_ref": deepcopy(candidate["payload"]["chapter_revision_ref"]),
        "source_generation_ref": deepcopy(
            candidate["payload"]["extraction_input_binding"][
                "accepted_source_generation_ref"
            ]
        ),
    }
    policy = b03_make_input_record(
        record_type="M3_BOUND_EVIDENCE_READ_POLICY",
        record_id="policy:b04-r03.5-recheck",
        created_at="2026-08-29T06:00:00Z",
        payload={
            "allowed_subject_types": ["CANDIDATE_FACT", "FORMAL_LEDGER_ITEM"],
            "authorization_modes": ["POLICY_FIXTURE_ONLY"],
            "adjacent_prose_access": "DENY",
            "plaintext_retention": "SHORT_TERM_EXPIRING",
            "revocation_effect": "IMMEDIATE_DENY_AND_PURGE",
            "expiry_effect": "DENY_AND_PURGE_AT_OR_AFTER_EXPIRY",
        },
    )
    trusted_times = [
        b03_make_input_record(
            record_type="M3_TRUSTED_TIME_RECEIPT",
            record_id=f"time:b04-r03.5-recheck:{sequence}",
            created_at="2026-08-29T06:00:00Z",
            payload={
                "time_source_id": "fixture-clock-b04-recheck",
                "trusted_evaluation_time": timestamp,
                "monotonic_sequence": sequence,
                "clock_mode": "DETERMINISTIC_FIXTURE",
            },
        )
        for sequence, timestamp in (
            (1, "2026-08-29T06:01:00Z"),
            (2, "2026-08-29T06:02:00Z"),
        )
    ]
    service = B03Service(
        runtime_root,
        upstream=deepcopy(context),
        policy=deepcopy(policy),
        trusted_times=deepcopy(trusted_times),
    )
    request_ref = service.request(
        {
            "subject": deepcopy(subject),
            "evidence_binding": deepcopy(item["evidence_binding"]),
            "purpose": "BOUND_EVIDENCE_REVIEW",
        },
        created_at="2026-08-29T06:01:00Z",
    )
    consent_ref = service.consent(
        request_ref,
        actor="fixture-author",
        created_at="2026-08-29T06:01:01Z",
    )
    authorization_ref = service.authorize(
        request_ref,
        consent_ref,
        created_at="2026-08-29T06:01:02Z",
    )
    source_slice_ref = service.read(request_ref, consent_ref, authorization_ref)
    stored = service.slice_core(source_slice_ref)
    if stored is None:
        raise AssertionError("B-03 SourceSlice fixture missing")
    source_slice = deepcopy(stored["core"])
    source_slice["payload"]["content"] = service.read_slice_content(source_slice_ref)
    if b03_record_ref(source_slice) != source_slice_ref:
        raise AssertionError("B-03 SourceSlice fixture drift")
    return {
        "records": [source_slice],
        "service": service,
        "consent_ref": consent_ref,
        "authorization_ref": authorization_ref,
        "runtime_root": runtime_root,
    }


def _group(
    group_id: str, purpose: str, operations: list[dict[str, Any]]
) -> dict[str, Any]:
    group = {
        "atomic_group_id": group_id,
        "purpose": purpose,
        "operations": deepcopy(operations),
        "group_payload_hash": "",
    }
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )
    return group


def _upstream_records() -> dict[str, Any]:
    context = exact_upstream_fixture()
    identity = DiagnosticRecorderIdentityRegistry.build(
        writer_version="b02-r03.5-b04-fixture",
        created_at=IDENTITY_CREATED_AT,
    )
    identity_ref = record_ref(identity)
    diagnostic = DiagnosticRecorder.build(
        context=context,
        **diagnostic_kwargs("B04-R03.5", context, identity_ref, created_at=CREATED_AT),
    )
    missing = CoverageRecorder.build(
        context=context,
        **coverage_kwargs(
            "B04-MISSING",
            context,
            identity_ref,
            "MISSING",
            source_evidence=SOURCE_MISSING,
            created_at=CREATED_AT,
        ),
    )
    partial = CoverageRecorder.build(
        context=context,
        **coverage_kwargs(
            "B04-PARTIAL",
            context,
            identity_ref,
            "PARTIAL",
            source_evidence=SOURCE_PARTIAL,
            created_at=CREATED_AT,
        ),
    )
    matched = CoverageRecorder.build(
        context=context,
        **coverage_kwargs(
            "B04-MATCHED",
            context,
            identity_ref,
            "MATCHED",
            created_at=CREATED_AT,
        ),
    )
    terminal = DiagnosticLifecycleWriter.build(
        diagnostic_ref=record_ref(diagnostic),
        lifecycle_sequence=1,
        event="CLOSED",
        effective_at="2026-08-30T02:20:00Z",
        reason_code="FIXTURE_CLOSED",
        created_at="2026-08-30T02:20:00Z",
    )
    return {
        "context": context,
        "identity": identity,
        "diagnostic": diagnostic,
        "missing_coverage": missing,
        "partial_coverage": partial,
        "matched_coverage": matched,
        "terminal_lifecycle": terminal,
    }


def build_authoritative_b02_store(
    root: Path, data: dict[str, Any]
) -> tuple[B02FixtureStore, B02Service]:
    """Populate the exact B-02 store that B-04 must read as current state."""

    context = deepcopy(data["context"])
    store = B02FixtureStore(root)
    service = B02Service(store, **context)
    identity = data["identity"]
    identity_ref = service.register_identity(
        writer_version=identity["payload"]["writer_version"],
        created_at=identity["created_at"],
    )
    if identity_ref != record_ref(identity):
        raise AssertionError("B-02 identity fixture drift")
    diagnostic = data["diagnostic"]
    diagnostic_payload = diagnostic["payload"]
    diagnostic_ref = service.add_diagnostic(
        axis=diagnostic_payload["axis"],
        severity=diagnostic_payload["severity"],
        lineage_locator=deepcopy(diagnostic_payload["target"]["lineage_locator"]),
        evidence_locator=deepcopy(diagnostic_payload["target"]["evidence_locator"]),
        fingerprint=diagnostic_payload["fingerprint"],
        writer_identity_ref=deepcopy(diagnostic_payload["writer_identity_ref"]),
        created_at=diagnostic["created_at"],
    )
    if diagnostic_ref != record_ref(diagnostic):
        raise AssertionError("B-02 Diagnostic fixture drift")
    for key in ("missing_coverage", "partial_coverage", "matched_coverage"):
        coverage = data[key]
        payload = coverage["payload"]
        coverage_ref = service.add_coverage(
            source_observation_id=payload["source_observation_id"],
            source_evidence=payload["source_evidence_binding"]["evidence"],
            axis=payload["axis"],
            candidate_match=payload["candidate_match"],
            matched_candidate_bindings=deepcopy(payload["matched_candidate_bindings"]),
            observer_ref=deepcopy(payload["observer_ref"]),
            created_at=coverage["created_at"],
        )
        if coverage_ref != record_ref(coverage):
            raise AssertionError(f"B-02 {key} fixture drift")
    return store, service


def _replacement(
    data: dict[str, Any], *, change_evidence: bool = False
) -> dict[str, Any]:
    context = data["context"]
    old = context["candidate_version"]["payload"]["items"][0]
    new_item = {
        key: deepcopy(value) for key, value in old.items() if key != "item_hash"
    }
    new_item["fact"] = "甲已经进入北塔。"
    new_item["status"] = "正在发生"
    coverage_refs: list[dict[str, Any]] = []
    if change_evidence:
        coverage = data["partial_coverage"]
        source = coverage["payload"]["source_evidence_binding"]
        new_item["evidence"] = source["evidence"]
        new_item["evidence_binding"] = _binding_from_coverage(coverage)
        coverage_refs = [record_ref(coverage)]
    return {
        "operation_kind": "REPLACE_CANDIDATE_ITEM",
        "target": deepcopy(context["lineage_locators"][0]),
        "expected_old_item_hash": old["item_hash"],
        "new_item": new_item,
        "supporting_diagnostic_refs": [record_ref(data["diagnostic"])],
        "supporting_coverage_refs": coverage_refs,
    }


def _addition(
    data: dict[str, Any], *, atomic_group_id: str, group_operation_ordinal: int
) -> dict[str, Any]:
    coverage = data["missing_coverage"]
    source = coverage["payload"]["source_evidence_binding"]
    coverage_refs = [record_ref(coverage)]
    new_item = {
        "lineage_id": "lin_pending",
        "fact": "甲拿起铜钥匙后进入北塔。",
        "status": "已发生",
        "evidence": source["evidence"],
        "speaker": "旁白",
        "evidence_binding": _binding_from_coverage(coverage),
    }
    new_item["lineage_id"] = proposed_add_lineage_id(
        base_candidate_version_ref=record_ref(data["context"]["candidate_version"]),
        supporting_coverage_refs=coverage_refs,
        atomic_group_id=atomic_group_id,
        group_operation_ordinal=group_operation_ordinal,
        item=new_item,
    )
    return {
        "operation_kind": "ADD_CANDIDATE_ITEM",
        "target_collection_pointer": "/items",
        "new_item": new_item,
        "supporting_coverage_refs": coverage_refs,
    }


def _causal_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "from_lineage_locator": deepcopy(data["context"]["lineage_locators"][0]),
        "to_lineage_locator": deepcopy(data["context"]["lineage_locators"][1]),
        "evidence_locators": sorted(
            deepcopy(data["context"]["evidence_locators"]), key=canonical_bytes
        ),
        "coverage_observation_refs": [],
        "authorized_source_slice_refs": [],
        "diagnostic_refs": [record_ref(data["diagnostic"])],
        "hint_kind": "DIRECT_POSSIBLE_CAUSE",
        "expiry_request_seconds": 3600,
        "noncommittable": True,
        "chapter_revision_ref": deepcopy(
            data["context"]["candidate_version"]["payload"]["chapter_revision_ref"]
        ),
    }


def route_inputs(route: str) -> dict[str, Any]:
    data = _upstream_records()
    diagnostics: list[dict[str, Any]] = []
    coverages: list[dict[str, Any]] = []
    causal_payloads: list[dict[str, Any]] = []
    if route == "replace_only":
        diagnostics = [data["diagnostic"]]
        groups = [_group("replace-existing", "修正完整候选", [_replacement(data)])]
    elif route == "add_only":
        coverages = [data["missing_coverage"]]
        groups = [
            _group(
                "add-missing",
                "补充漏抽候选",
                [
                    _addition(
                        data,
                        atomic_group_id="add-missing",
                        group_operation_ordinal=0,
                    )
                ],
            )
        ]
    elif route == "replace_with_evidence":
        diagnostics = [data["diagnostic"]]
        coverages = [data["partial_coverage"]]
        groups = [
            _group(
                "replace-evidence",
                "整条候选连同逐字依据一起修正",
                [_replacement(data, change_evidence=True)],
            )
        ]
    elif route == "replace_and_add":
        diagnostics = [data["diagnostic"]]
        coverages = [data["missing_coverage"]]
        groups = [
            _group("replace-existing", "修正完整候选", [_replacement(data)]),
            _group(
                "add-missing",
                "补充漏抽候选",
                [
                    _addition(
                        data,
                        atomic_group_id="add-missing",
                        group_operation_ordinal=0,
                    )
                ],
            ),
        ]
    elif route == "causal_sidecar":
        diagnostics = [data["diagnostic"]]
        groups = [_group("replace-existing", "修正完整候选", [_replacement(data)])]
        causal_payloads = [_causal_payload(data)]
    else:
        raise KeyError(route)
    return {
        "context": deepcopy(data["context"]),
        "policy": policy_record(),
        "diagnostics": sorted(
            deepcopy(diagnostics), key=lambda item: canonical_bytes(record_ref(item))
        ),
        "coverages": sorted(
            deepcopy(coverages), key=lambda item: canonical_bytes(record_ref(item))
        ),
        "source_slice_records": [],
        "groups": groups,
        "causal_payloads": causal_payloads,
        "created_at": CREATED_AT,
        "access": FIXTURE_ACCESS,
        "catalog": data,
    }
