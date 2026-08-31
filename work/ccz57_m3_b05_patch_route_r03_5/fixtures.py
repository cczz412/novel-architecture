"""Synthetic, text-free fixture families for B-05 r03.5."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    CandidateVersionStore,
    make_read_only_child_fixture,
)
from work.ccz57_m3_b02_diagnostic_coverage_r03_5.b02_contracts import (  # noqa: E402
    build_source_evidence_binding,
)
from work.ccz57_m3_b04_patch_atomic_group_r03_5.b04_contracts import (  # noqa: E402
    proposed_add_lineage_id,
)

from acceptance_spec import FAILURE_FIXTURES, NORMAL_FIXTURES  # noqa: E402
from authoritative_readers import (  # noqa: E402
    B01CurrentReaderAdapter,
    B02CurrentScopeReader,
    PolicyGateReader,
)
from b05_contracts import (  # noqa: E402
    CONTRACT_VERSION,
    FIXTURE_ACCESS,
    IMMUTABLE_CONTRACT,
    RETENTION_CLASS,
    SOURCE_MODULE,
    canonical_bytes,
    record_ref,
    sha256_value,
    stable_sorted,
)
from b05_store import B05RouteStore, B05Service, ValidatorIdentityRegistry  # noqa: E402

CREATED_AT = "2026-08-30T08:00:00Z"
REOPENED_AT = "2026-08-30T08:05:00Z"
B01_OBJECT_SHAPES = (
    Path(__file__).resolve().parent.parent
    / "ccz57_m3_b01_candidate_version_r03_5"
    / "OBJECT_SHAPES.json"
)
SEGMENT_INPUTS = [
    {
        "seg": 1,
        "start_byte": 0,
        "end_byte": len("甲走进北塔。甲拿起铜钥匙。甲走进北塔。".encode("utf-8")),
        "responsibility_text": "甲走进北塔。甲拿起铜钥匙。甲走进北塔。",
    },
    {
        "seg": 2,
        "start_byte": len("甲走进北塔。甲拿起铜钥匙。甲走进北塔。".encode("utf-8")),
        "end_byte": len(
            "甲走进北塔。甲拿起铜钥匙。甲走进北塔。乙停在门外。".encode("utf-8")
        ),
        "responsibility_text": "乙停在门外。",
    },
]


def external_record(
    record_type: str,
    payload: dict[str, Any],
    *,
    created_at: str = CREATED_AT,
    record_id: str | None = None,
) -> dict[str, Any]:
    payload = deepcopy(payload)
    prefixes = {
        "M3_CANDIDATE_PROTECTION_SET": "protection-set",
        "M3_PATCH_PROPOSAL": "patch-proposal",
        "M3_CAUSAL_HINT_PROPOSAL": "causal-hint-proposal",
    }
    prefix = prefixes.get(record_type, f"fixture-{record_type.lower()}")
    record_id = record_id or f"{prefix}:{sha256_value(payload)}"
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
        "payload": payload,
    }
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    return record


def _item(lineage_id: str, fact: str) -> dict[str, Any]:
    item = {
        "lineage_id": lineage_id,
        "fact": fact,
        "status": "候选",
        "evidence": f"synthetic-evidence-{lineage_id}",
        "speaker": "旁白",
        "evidence_binding": {
            "fixture": True,
            "evidence_sha256": sha256_value(f"synthetic-evidence-{lineage_id}"),
        },
    }
    item["item_hash"] = sha256_value(item)
    return item


def _lineage_locator(
    candidate: dict[str, Any], item: dict[str, Any], index: int
) -> dict[str, Any]:
    locator = {
        "contract": "M3_LINEAGE_LOCATOR",
        "contract_version": CONTRACT_VERSION,
        "candidate_version_ref": record_ref(candidate),
        "lineage_id": item["lineage_id"],
        "json_pointer": f"/items/{index}",
        "item_hash": item["item_hash"],
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    return locator


def _evidence_locator(
    candidate: dict[str, Any], item: dict[str, Any], index: int
) -> dict[str, Any]:
    binding = item["evidence_binding"]
    locator = {
        "contract": "M3_EVIDENCE_LOCATOR",
        "contract_version": CONTRACT_VERSION,
        "candidate_version_ref": record_ref(candidate),
        "lineage_id": item["lineage_id"],
        "evidence_json_pointer": f"/items/{index}/evidence",
        "evidence_sha256": binding["evidence_sha256"],
        "binding_hash": binding["binding_hash"],
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    return locator


def _group(group_id: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
    group = {
        "atomic_group_id": group_id,
        "purpose": f"fixture-purpose-{group_id}",
        "operations": deepcopy(operations),
        "group_payload_hash": "",
    }
    group["group_payload_hash"] = sha256_value(
        {key: value for key, value in group.items() if key != "group_payload_hash"}
    )
    return group


def _replace(
    item: dict[str, Any],
    target: dict[str, Any],
    diagnostic_ref: dict[str, Any],
    *,
    suffix: str,
) -> dict[str, Any]:
    replacement = {
        key: deepcopy(value) for key, value in item.items() if key != "item_hash"
    }
    replacement["fact"] = f"fixture-replaced-{suffix}"
    return {
        "operation_kind": "REPLACE_CANDIDATE_ITEM",
        "target": deepcopy(target),
        "expected_old_item_hash": item["item_hash"],
        "new_item": replacement,
        "supporting_diagnostic_refs": [deepcopy(diagnostic_ref)],
        "supporting_coverage_refs": [],
    }


def _add(
    candidate: dict[str, Any],
    coverage: dict[str, Any],
    *,
    atomic_group_id: str,
    group_operation_ordinal: int,
) -> dict[str, Any]:
    coverage_ref = record_ref(coverage)
    source = coverage["payload"]["source_evidence_binding"]
    evidence_binding = {
        "chapter_revision_ref": deepcopy(source["chapter_revision_ref"]),
        "evidence_sha256": source["evidence_sha256"],
        "sentence_count": source["sentence_count"],
        "match_locations": deepcopy(source["match_locations"]),
    }
    evidence_binding["binding_hash"] = sha256_value(evidence_binding)
    item = {
        "lineage_id": "lin_pending",
        "fact": "甲拿起铜钥匙后进入北塔。",
        "status": "已发生",
        "evidence": source["evidence"],
        "speaker": "旁白",
        "evidence_binding": evidence_binding,
    }
    item["lineage_id"] = proposed_add_lineage_id(
        base_candidate_version_ref=record_ref(candidate),
        supporting_coverage_refs=[coverage_ref],
        atomic_group_id=atomic_group_id,
        group_operation_ordinal=group_operation_ordinal,
        item=item,
    )
    return {
        "operation_kind": "ADD_CANDIDATE_ITEM",
        "target_collection_pointer": "/items",
        "new_item": item,
        "supporting_coverage_refs": [deepcopy(coverage_ref)],
    }


def validator_identity_payload() -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    implementation_members = [
        "authoritative_readers.py",
        "b05_contracts.py",
        "b05_store.py",
        "patch_route_projection.py",
    ]
    manifest_lines = [
        f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}"
        for name in implementation_members
    ]
    implementation_manifest = "\n".join(manifest_lines) + "\n"
    implementation_hash = hashlib.sha256(
        implementation_manifest.encode("utf-8")
    ).hexdigest()
    reader_sha = hashlib.sha256(
        (root / "authoritative_readers.py").read_bytes()
    ).hexdigest()
    return {
        "validator_name": "CCZ57-B05-Offline-Patch-Validator",
        "validator_version": "r03.5-fixture-1",
        "implementation_identity": {
            "repository": "cczz412/novel-architecture",
            "implementation_tree_or_artifact_hash": implementation_hash,
            "manifest_hash": hashlib.sha256(
                implementation_manifest.encode("utf-8")
            ).hexdigest(),
            "manifest_members": manifest_lines,
            "b01_current_reader_adapter": {
                "reader_identity": "B01CurrentReaderAdapter",
                "reader_version": "b05-r03.5-fixture-1",
                "implementation_sha256": reader_sha,
            },
            "b02_current_scope_reader": {
                "reader_identity": "B02CurrentScopeReader",
                "reader_version": "b05-r03.5-fixture-1",
                "implementation_sha256": reader_sha,
            },
            "policy_reader": {
                "reader_identity": "B05PolicyGateReader",
                "reader_version": "b05-r03.5-fixture-1",
                "implementation_sha256": reader_sha,
            },
            "gate_reader": {
                "reader_identity": "B05PolicyGateReader",
                "reader_version": "b05-r03.5-fixture-1",
                "implementation_sha256": reader_sha,
            },
        },
        "supported_contract_version": CONTRACT_VERSION,
        "supported_candidate_schema_ids": ["novel-fact-extraction-v2.1"],
        "supported_policy_contract": "M3_PATCH_VALIDATION_POLICY",
        "supported_policy_versions": ["b05-policy-fixture-1"],
        "runtime_capabilities": {
            "model_api": False,
            "network": False,
            "real_novel_read": False,
            "text_slice_read": False,
            "candidate_content_generation": False,
        },
    }


@dataclass
class FixtureEnvironment:
    store: B05RouteStore
    service: B05Service
    patch: dict[str, Any]
    protection: dict[str, Any]
    causals: list[dict[str, Any]]
    b01_reader: B01CurrentReaderAdapter
    b02_reader: B02CurrentScopeReader
    policy_reader: PolicyGateReader
    records: dict[str, dict[str, Any]]

    def evaluate(
        self, operation_id: str = "fixture-operation-1", **kwargs: Any
    ) -> dict[str, Any]:
        return self.service.evaluate(
            patch_proposal=self.patch,
            protection_set=self.protection,
            causal_hint_proposals=self.causals,
            operation_id=operation_id,
            created_at=kwargs.pop("created_at", CREATED_AT),
            **kwargs,
        )


def build_environment(
    root: Path,
    *,
    mode: str = "replace",
    candidate_child: bool = False,
    stale_pointer: bool = False,
    terminal_diagnostic: bool = False,
    closed_gate: bool = False,
    semantic_unknown_groups: list[str] | None = None,
    unknown_tokens: list[dict[str, Any]] | None = None,
    canonical_add_sort_frozen: bool = True,
    failure_point: str | None = None,
) -> FixtureEnvironment:
    catalog = json.loads(B01_OBJECT_SHAPES.read_text(encoding="utf-8"))
    segment_index = deepcopy(
        next(
            record
            for record in catalog["immutable_records"]
            if record["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT"
        )
    )
    root_candidate = deepcopy(
        next(
            record
            for record in catalog["immutable_records"]
            if record["record_type"] == "M3_CANDIDATE_VERSION"
        )
    )
    reference_records = deepcopy(catalog["reference_records"])
    candidate = root_candidate
    if candidate_child:
        raw_items = [
            {
                key: deepcopy(value)
                for key, value in item.items()
                if key in {"fact", "status", "evidence", "speaker"}
            }
            for item in root_candidate["payload"]["items"]
        ]
        raw_items[0]["fact"] = "甲已经走进北塔。"
        candidate = make_read_only_child_fixture(
            root_candidate,
            raw_items,
            reference_records=[*reference_records, deepcopy(segment_index)],
        )
    validation_records = [*reference_records, deepcopy(segment_index)]
    lineage_locators = [
        CandidateVersionStore.lineage_locator(
            candidate,
            item["lineage_id"],
            reference_records=validation_records,
        )
        for item in candidate["payload"]["items"]
    ]
    evidence_locators = [
        CandidateVersionStore.evidence_locator(
            candidate,
            item["lineage_id"],
            reference_records=validation_records,
        )
        for item in candidate["payload"]["items"]
    ]
    pointer_snapshot = None
    if not candidate_child:
        pointer_snapshot = deepcopy(
            next(
                record
                for record in catalog["immutable_records"]
                if record["record_type"] == "M3_CANDIDATE_POINTER_SNAPSHOT"
            )
        )
    live_pointer = deepcopy(catalog["live_pointer_example"])
    live_pointer["current_candidate_version_ref"] = record_ref(candidate)
    live_pointer["generation"] = 2 if candidate_child else 1
    if stale_pointer:
        stale_ref = deepcopy(record_ref(candidate))
        stale_ref["record_id"] = f"{stale_ref['record_id']}:stale"
        stale_ref["record_hash"] = sha256_value(stale_ref)
        live_pointer["current_candidate_version_ref"] = stale_ref

    upstream_context = {
        "reference_records": deepcopy(reference_records),
        "segment_index": deepcopy(segment_index),
        "candidate_version": deepcopy(candidate),
        "lineage_locators": deepcopy(lineage_locators),
        "evidence_locators": deepcopy(evidence_locators),
        "segment_inputs": deepcopy(SEGMENT_INPUTS),
    }
    candidate_payload = candidate["payload"]
    chapter_revision = candidate_payload["chapter_revision_ref"]
    item_a, item_b = candidate_payload["items"][:2]
    locator_a, locator_b = lineage_locators[:2]
    evidence_locator_a, evidence_locator_b = evidence_locators[:2]
    writer_identity = external_record(
        "M3_DIAGNOSTIC_RECORDER_IDENTITY",
        {"writer": "DiagnosticRecorder", "writer_version": "b05-r03.5-fixture-1"},
    )

    def diagnostic_for(
        label: str,
        lineage_locator: dict[str, Any],
        evidence_locator: dict[str, Any],
    ) -> dict[str, Any]:
        return external_record(
            "M3_DIAGNOSTIC",
            {
                "base_candidate_version_ref": record_ref(candidate),
                "candidate_schema_id": candidate_payload["candidate_schema_id"],
                "chapter_revision_ref": chapter_revision,
                "seg": candidate_payload["seg"],
                "axis": "FACT_COMPLETENESS",
                "severity": "WARN",
                "target": {
                    "kind": "CANDIDATE_ITEM_EVIDENCE",
                    "lineage_locator": deepcopy(lineage_locator),
                    "evidence_locator": deepcopy(evidence_locator),
                },
                "fingerprint": sha256_value({"fixture": label}),
                "writer_identity_ref": record_ref(writer_identity),
            },
            record_id=f"diagnostic:b05:{label}",
        )

    diagnostic = diagnostic_for("diagnostic-a", locator_a, evidence_locator_a)
    diagnostic_b = diagnostic_for("diagnostic-b", locator_b, evidence_locator_b)
    source_evidence_binding = build_source_evidence_binding(
        "甲拿起铜钥匙。", context=upstream_context
    )
    coverage = external_record(
        "M3_COVERAGE_OBSERVATION",
        {
            "base_candidate_version_ref": record_ref(candidate),
            "candidate_schema_id": candidate_payload["candidate_schema_id"],
            "chapter_revision_ref": chapter_revision,
            "seg": candidate_payload["seg"],
            "source_observation_id": "fixture-coverage-observation",
            "source_evidence_binding": source_evidence_binding,
            "axis": "FACT_COMPLETENESS",
            "candidate_match": "MISSING",
            "matched_candidate_bindings": [],
            "observer_ref": record_ref(writer_identity),
        },
    )
    b02_records = [writer_identity, diagnostic, diagnostic_b, coverage]
    if terminal_diagnostic:
        b02_records.append(
            external_record(
                "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
                {
                    "diagnostic_ref": record_ref(diagnostic),
                    "lifecycle_sequence": 1,
                    "event": "CLOSED",
                    "effective_at": CREATED_AT,
                    "reason_code": "FIXTURE_TERMINAL",
                    "resolution_ref": None,
                },
            )
        )
    groups: list[dict[str, Any]]
    if mode == "replace":
        groups = [
            _group(
                "replace-a",
                [_replace(item_a, locator_a, record_ref(diagnostic), suffix="a")],
            )
        ]
    elif mode == "add":
        groups = [
            _group(
                "add-c",
                [
                    _add(
                        candidate,
                        coverage,
                        atomic_group_id="add-c",
                        group_operation_ordinal=0,
                    )
                ],
            )
        ]
    elif mode == "mixed":
        groups = [
            _group(
                "replace-a",
                [_replace(item_a, locator_a, record_ref(diagnostic), suffix="a")],
            ),
            _group(
                "add-c",
                [
                    _add(
                        candidate,
                        coverage,
                        atomic_group_id="add-c",
                        group_operation_ordinal=0,
                    )
                ],
            ),
        ]
    elif mode in {"two-replace", "dependent"}:
        groups = [
            _group(
                "replace-a",
                [_replace(item_a, locator_a, record_ref(diagnostic), suffix="a")],
            ),
            _group(
                "replace-b",
                [_replace(item_b, locator_b, record_ref(diagnostic_b), suffix="b")],
            ),
        ]
    elif mode == "order-add":
        groups = [
            _group(
                "add-c",
                [
                    _add(
                        candidate,
                        coverage,
                        atomic_group_id="add-c",
                        group_operation_ordinal=0,
                    )
                ],
            ),
            _group(
                "add-d",
                [
                    _add(
                        candidate,
                        coverage,
                        atomic_group_id="add-d",
                        group_operation_ordinal=0,
                    )
                ],
            ),
        ]
    elif mode == "causal":
        groups = [
            _group(
                "replace-a",
                [_replace(item_a, locator_a, record_ref(diagnostic), suffix="a")],
            )
        ]
    else:
        raise KeyError(mode)
    protection_policy = external_record(
        "M3_PROTECTION_POLICY",
        {
            "policy_revision": "r03.5-full-item",
            "protect_untouched_items": True,
            "protect_accepted_lineage": True,
        },
    )
    replaced_lineages = {
        _find_target["lineage_id"]
        for group in groups
        for operation in group["operations"]
        if operation["operation_kind"] == "REPLACE_CANDIDATE_ITEM"
        for _find_target in [operation["target"]]
    }
    protected_entries = [
        {
            "lineage_locator": deepcopy(locator),
            "json_pointer": locator["json_pointer"],
            "protected_item_hash": item["item_hash"],
            "reason": "UNTOUCHED_BY_THIS_PATCH_PROTECTED",
        }
        for item, locator in ((item_a, locator_a), (item_b, locator_b))
        if item["lineage_id"] not in replaced_lineages
    ]
    protection = external_record(
        "M3_CANDIDATE_PROTECTION_SET",
        {
            "base_candidate_version_ref": record_ref(candidate),
            "protection_policy_ref": record_ref(protection_policy),
            "chapter_revision_ref": chapter_revision,
            "protected_entries": protected_entries,
        },
    )
    causal_records = []
    if mode == "causal":
        causal_records = [
            external_record(
                "M3_CAUSAL_HINT_PROPOSAL",
                {
                    "from_lineage_locator": deepcopy(locator_a),
                    "to_lineage_locator": deepcopy(locator_b),
                    "evidence_locators": sorted(
                        deepcopy(evidence_locators), key=canonical_bytes
                    ),
                    "coverage_observation_refs": [],
                    "authorized_source_slice_refs": [],
                    "diagnostic_refs": [record_ref(diagnostic)],
                    "hint_kind": "DIRECT_POSSIBLE_CAUSE",
                    "expiry_request_seconds": 3600,
                    "noncommittable": True,
                    "chapter_revision_ref": chapter_revision,
                },
            )
        ]
    selected_diagnostic_refs = stable_sorted(
        list(
            {
                canonical_bytes(ref): ref
                for group in groups
                for operation in group["operations"]
                for ref in operation.get("supporting_diagnostic_refs", [])
            }.values()
        )
    )
    selected_coverage_refs = stable_sorted(
        list(
            {
                canonical_bytes(ref): ref
                for group in groups
                for operation in group["operations"]
                for ref in operation.get("supporting_coverage_refs", [])
            }.values()
        )
    )
    patch = external_record(
        "M3_PATCH_PROPOSAL",
        {
            "base_candidate_version_ref": record_ref(candidate),
            "candidate_schema_id": "novel-fact-extraction-v2.1",
            "diagnostic_refs": stable_sorted(selected_diagnostic_refs),
            "coverage_observation_refs": stable_sorted(selected_coverage_refs),
            "authorized_source_slice_refs": [],
            "protection_set_ref": record_ref(protection),
            "chapter_revision_ref": chapter_revision,
            "atomic_groups": groups,
            "sidecar_proposal_refs": [record_ref(item) for item in causal_records],
        },
    )
    policy_payload: dict[str, Any] = {
        "policy_version": "b05-policy-fixture-1",
        "canonical_add_sort_frozen": canonical_add_sort_frozen,
        "semantic_unknown_group_ids": semantic_unknown_groups or [],
        "unknown_dependency_tokens": unknown_tokens or [],
        "declared_dependency_edges": [],
        "adjacent_check_group_ids": [],
    }
    if mode == "dependent":
        policy_payload["declared_dependency_edges"] = [
            {
                "left_atomic_group_id": "replace-a",
                "right_atomic_group_id": "replace-b",
                "edge_type": "OPERATION_RESULT_DEPENDENCY",
                "evidence_tokens": [
                    {
                        "type": "STABLE_CHECK_CODE",
                        "value": "B05_CHECK_FIXTURE_DEPENDENCY",
                    }
                ],
            }
        ]
    gate_bindings = []
    gate_records = []
    gate = external_record(
        "M3_NON_CONTENT_GATE",
        {"gate_kind": "CONTROLLED_COMMIT", "gate_scope": "PATCH_ROUTE_UNIT"},
    )
    gate_state = external_record(
        "M3_NON_CONTENT_GATE_STATE",
        {
            "gate_ref": record_ref(gate),
            "state_sequence": 1,
            "current_state": "CLOSED" if closed_gate else "OPEN",
        },
    )
    if closed_gate:
        policy_payload["declared_non_content_gates"] = [
            {"gate_ref": record_ref(gate), "gate_kind": "CONTROLLED_COMMIT"}
        ]
        gate_records = [gate, gate_state]
        gate_bindings = [
            {
                "gate_ref": record_ref(gate),
                "gate_state_ref": record_ref(gate_state),
                "current_state": "CLOSED",
                "applicable_patch_proposal_ref": record_ref(patch),
                "applicable_atomic_group_bindings_or_route_unit_ids": [
                    {
                        "atomic_group_id": groups[0]["atomic_group_id"],
                        "group_payload_hash": groups[0]["group_payload_hash"],
                    }
                ],
                "reader_identity": "B05PolicyGateReader",
                "reader_version": "b05-r03.5-fixture-1",
            }
        ]
    policy = external_record("M3_PATCH_VALIDATION_POLICY", policy_payload)
    selection = external_record(
        "M3_ACTIVE_POLICY_SELECTION",
        {"selected_validation_policy_ref": record_ref(policy)},
    )
    b01_reader = B01CurrentReaderAdapter(
        candidate_version=candidate,
        segment_index=segment_index,
        pointer_snapshot=pointer_snapshot,
        live_pointer_binding=live_pointer,
        reference_records=reference_records,
        lineage_locators=lineage_locators,
        evidence_locators=evidence_locators,
        segment_inputs=SEGMENT_INPUTS,
    )
    b02_reader = B02CurrentScopeReader(records=b02_records)
    policy_reader = PolicyGateReader(
        validation_policy=policy,
        active_selection=selection,
        gate_bindings=gate_bindings,
        gate_records=gate_records,
    )
    store = B05RouteStore(root, failure_point=failure_point)
    identity_ref = ValidatorIdentityRegistry.register(
        store, payload=validator_identity_payload(), created_at=CREATED_AT
    )
    service = B05Service(
        store,
        b01_reader=b01_reader,
        b02_reader=b02_reader,
        policy_gate_reader=policy_reader,
        protection_policy=protection_policy,
        source_slice_records=[],
        validator_identity_ref=identity_ref,
    )
    return FixtureEnvironment(
        store=store,
        service=service,
        patch=patch,
        protection=protection,
        causals=causal_records,
        b01_reader=b01_reader,
        b02_reader=b02_reader,
        policy_reader=policy_reader,
        records={
            "candidate": candidate,
            "segment_index": segment_index,
            "pointer_snapshot": pointer_snapshot,
            "diagnostic": diagnostic,
            "diagnostic_b": diagnostic_b,
            "coverage": coverage,
            "policy": policy,
            "selection": selection,
            "gate": gate,
            "gate_state": gate_state,
            "protection_policy": protection_policy,
        },
    )


def fixture_catalog() -> dict[str, Any]:
    return {
        "normal": deepcopy(NORMAL_FIXTURES),
        "failure": deepcopy(FAILURE_FIXTURES),
        "normal_count": len(NORMAL_FIXTURES),
        "failure_count": len(FAILURE_FIXTURES),
        "catalog_hash": sha256_value(
            {"normal": NORMAL_FIXTURES, "failure": FAILURE_FIXTURES}
        ),
    }
