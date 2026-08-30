"""Non-persistent current-route projection and downstream read guards."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from b05_contracts import (
    canonical_bytes,
    fail,
    record_ref,
    sha256_value,
    stable_sorted,
    validate_immutable_record,
    validate_output_record,
    validate_record_ref,
)


class PatchAggregateProjector:
    """Recompute active routes; never guesses through a broken lifecycle chain."""

    @staticmethod
    def project(records: list[dict[str, Any]]) -> dict[str, Any]:
        for record in records:
            validate_output_record(record)
        routes = [
            item for item in records if item["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
        ]
        lifecycles = [
            item
            for item in records
            if item["record_type"] == "M3_PATCH_LIFECYCLE_RECEIPT"
        ]
        series_ids = sorted(
            {route["payload"]["route_series_id"] for route in routes},
            key=canonical_bytes,
        )
        result = []
        for series_id in series_ids:
            series_routes = [
                item
                for item in routes
                if item["payload"]["route_series_id"] == series_id
            ]
            series_lifecycle = [
                item
                for item in lifecycles
                if item["payload"]["route_series_id"] == series_id
            ]
            sequences = sorted(
                item["payload"]["lifecycle_sequence"] for item in series_lifecycle
            )
            if sequences != list(range(1, len(sequences) + 1)):
                fail("B05_PROJECTION_LIFECYCLE_SEQUENCE_INVALID")
            if not series_lifecycle:
                fail("B05_PROJECTION_LIFECYCLE_MISSING")
            ordered_lifecycle = sorted(
                series_lifecycle,
                key=lambda item: item["payload"]["lifecycle_sequence"],
            )
            route_refs = {canonical_bytes(record_ref(item)) for item in series_routes}
            for lifecycle in series_lifecycle:
                payload = lifecycle["payload"]
                subject = canonical_bytes(payload["subject_route_receipt_ref"])
                if subject not in route_refs:
                    fail("B05_PROJECTION_SUBJECT_ROUTE_MISSING")
                replacement = payload["replacement_route_receipt_ref_or_null"]
                prior = payload["prior_route_receipt_ref_or_null"]
                if (
                    replacement is not None
                    and canonical_bytes(replacement) not in route_refs
                ):
                    fail("B05_PROJECTION_REPLACEMENT_ROUTE_MISSING")
                if prior is not None and canonical_bytes(prior) not in route_refs:
                    fail("B05_PROJECTION_PRIOR_ROUTE_MISSING")
            first = ordered_lifecycle[0]["payload"]
            if first["event"] != "ROUTES_FROZEN":
                fail("B05_PROJECTION_INITIAL_EVENT_INVALID")
            current_ref = first["subject_route_receipt_ref"]
            current_route = next(
                item
                for item in series_routes
                if canonical_bytes(record_ref(item)) == canonical_bytes(current_ref)
            )
            if current_route["payload"]["route_generation"] != 1:
                fail("B05_PROJECTION_INITIAL_GENERATION_INVALID")
            tail = ordered_lifecycle[1:]
            if len(tail) % 2 != 0:
                fail("B05_PROJECTION_REOPEN_EVENT_PAIR_INCOMPLETE")
            for index in range(0, len(tail), 2):
                superseded = tail[index]["payload"]
                reopened = tail[index + 1]["payload"]
                if (
                    superseded["event"] != "SUPERSEDED"
                    or reopened["event"] != "REOPENED_WITH_NEW_MATERIAL"
                    or canonical_bytes(superseded["subject_route_receipt_ref"])
                    != canonical_bytes(current_ref)
                    or canonical_bytes(
                        superseded["replacement_route_receipt_ref_or_null"]
                    )
                    != canonical_bytes(reopened["subject_route_receipt_ref"])
                    or canonical_bytes(reopened["prior_route_receipt_ref_or_null"])
                    != canonical_bytes(current_ref)
                    or superseded["evaluation_key"] != reopened["evaluation_key"]
                    or superseded["effective_at"] != reopened["effective_at"]
                ):
                    fail("B05_PROJECTION_REOPEN_CHAIN_INVALID")
                next_route = next(
                    item
                    for item in series_routes
                    if canonical_bytes(record_ref(item))
                    == canonical_bytes(reopened["subject_route_receipt_ref"])
                )
                if next_route["payload"]["route_generation"] != (
                    current_route["payload"]["route_generation"] + 1
                ):
                    fail("B05_PROJECTION_ROUTE_GENERATION_INVALID")
                current_ref = reopened["subject_route_receipt_ref"]
                current_route = next_route
            superseded = {
                canonical_bytes(item["payload"]["subject_route_receipt_ref"])
                for item in series_lifecycle
                if item["payload"]["event"] == "SUPERSEDED"
            }
            active = [
                route
                for route in series_routes
                if canonical_bytes(record_ref(route)) not in superseded
            ]
            if len(active) != 1:
                fail("B05_PROJECTION_ACTIVE_ROUTE_AMBIGUOUS")
            head = max(
                series_lifecycle,
                key=lambda item: item["payload"]["lifecycle_sequence"],
            )
            result.append(
                {
                    "route_series_id": series_id,
                    "active_route_receipt_ref": record_ref(active[0]),
                    "active_route_generation": active[0]["payload"]["route_generation"],
                    "lifecycle_head_ref": record_ref(head),
                    "route_units": deepcopy(active[0]["payload"]["route_units"]),
                    "causal_hint_routes": deepcopy(
                        active[0]["payload"]["causal_hint_routes"]
                    ),
                }
            )
        return {
            "projection_type": "PatchRouteAggregateProjection",
            "series": stable_sorted(result),
            "persists_output": False,
        }

    @staticmethod
    def persist(_: dict[str, Any]) -> None:
        fail("B05_PROJECTION_PERSISTENCE_FORBIDDEN")


def _active_route(
    records: list[dict[str, Any]], route_receipt_ref: dict[str, Any]
) -> dict[str, Any]:
    validate_record_ref(route_receipt_ref, expected_type="M3_PATCH_ROUTE_RECEIPT")
    projection = PatchAggregateProjector.project(records)
    if not any(
        canonical_bytes(item["active_route_receipt_ref"])
        == canonical_bytes(route_receipt_ref)
        for item in projection["series"]
    ):
        fail("B05_DOWNSTREAM_ROUTE_NOT_ACTIVE")
    matches = [
        item
        for item in records
        if item["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
        and canonical_bytes(record_ref(item)) == canonical_bytes(route_receipt_ref)
    ]
    if len(matches) != 1:
        fail("B05_DOWNSTREAM_ROUTE_UNRESOLVABLE")
    return matches[0]


def _require_freshness(
    route: dict[str, Any],
    *,
    live_pointer_binding_hash: str,
    b02_scope_snapshot_hash: str,
    active_policy_selection_hash: str,
    non_content_gate_snapshot_hash: str,
) -> None:
    payload = route["payload"]
    binding = payload["binding_header"]
    if binding["live_pointer_binding_hash"] != live_pointer_binding_hash:
        fail("B05_DOWNSTREAM_POINTER_STALE")
    if binding["b02_scope_snapshot_hash"] != b02_scope_snapshot_hash:
        fail("B05_DOWNSTREAM_B02_SCOPE_STALE")
    if payload["active_policy_selection_hash"] != active_policy_selection_hash:
        fail("B05_DOWNSTREAM_POLICY_STALE")
    if binding["non_content_gate_snapshot_hash"] != non_content_gate_snapshot_hash:
        fail("B05_DOWNSTREAM_GATE_STALE")


def _validation_receipt_for_route(
    records: list[dict[str, Any]], route: dict[str, Any]
) -> dict[str, Any]:
    validation_ref = route["payload"]["validation_receipt_ref"]
    matches = [
        item
        for item in records
        if item["record_type"] == "M3_PATCH_VALIDATION_RECEIPT"
        and canonical_bytes(record_ref(item)) == canonical_bytes(validation_ref)
    ]
    if len(matches) != 1:
        fail("B05_DOWNSTREAM_PVR_UNRESOLVABLE")
    return matches[0]


def _require_effective_protection(
    pvr: dict[str, Any],
    proof: dict[str, Any],
    base_candidate_version_record: dict[str, Any],
) -> None:
    validate_immutable_record(
        base_candidate_version_record, expected_type="M3_CANDIDATE_VERSION"
    )
    binding = pvr["payload"]["input_binding"]
    if (
        canonical_bytes(record_ref(base_candidate_version_record))
        != canonical_bytes(binding["base_candidate_version_ref"])
        or sha256_value(base_candidate_version_record["payload"])
        != binding["base_version_payload_hash"]
    ):
        fail("B05_B06_BASE_BINDING_MISMATCH")
    written_lineages = {
        item.get("lineage_id")
        for item in proof["logical_write_set"]
        if item.get("kind") == "LINEAGE_TARGET"
    }
    expected = []
    for index, item in enumerate(
        base_candidate_version_record["payload"].get("items", [])
    ):
        if item.get("lineage_id") in written_lineages:
            continue
        locator = {
            "contract": "M3_LINEAGE_LOCATOR",
            "contract_version": base_candidate_version_record["contract_version"],
            "candidate_version_ref": record_ref(base_candidate_version_record),
            "lineage_id": item.get("lineage_id"),
            "json_pointer": f"/items/{index}",
            "item_hash": item.get("item_hash")
            or sha256_value(
                {key: value for key, value in item.items() if key != "item_hash"}
            ),
            "locator_hash": "",
        }
        locator["locator_hash"] = sha256_value(
            {key: value for key, value in locator.items() if key != "locator_hash"}
        )
        expected.append(
            {
                "lineage_locator": locator,
                "json_pointer": f"/items/{index}",
                "protected_item_hash": locator["item_hash"],
                "protected_item_canonical_bytes_hash": sha256_value(item),
                "protection_reason": "NOT_WRITTEN_BY_THIS_ROUTE_UNIT",
            }
        )
    protection_checks = [
        item
        for item in proof["check_results"]
        if item["check_code"] == "B05_CHECK_EFFECTIVE_PROTECTION_COMPLETE"
    ]
    if (
        canonical_bytes(stable_sorted(proof["effective_protection_proof"]))
        != canonical_bytes(stable_sorted(expected))
        or len(protection_checks) != 1
        or protection_checks[0]["status"] != "PASS"
    ):
        fail("B05_B06_EFFECTIVE_PROTECTION_INVALID")


class B06AdmissionGuard:
    @staticmethod
    def require_allow(
        records: list[dict[str, Any]],
        *,
        route_receipt_ref: dict[str, Any],
        route_unit_id: str,
        base_candidate_version_record: dict[str, Any],
        live_pointer_binding_hash: str,
        b02_scope_snapshot_hash: str,
        active_policy_selection_hash: str,
        non_content_gate_snapshot_hash: str,
    ) -> dict[str, Any]:
        route = _active_route(records, route_receipt_ref)
        _require_freshness(
            route,
            live_pointer_binding_hash=live_pointer_binding_hash,
            b02_scope_snapshot_hash=b02_scope_snapshot_hash,
            active_policy_selection_hash=active_policy_selection_hash,
            non_content_gate_snapshot_hash=non_content_gate_snapshot_hash,
        )
        entries = [
            item
            for item in route["payload"]["route_units"]
            if item["route_unit_id"] == route_unit_id
        ]
        if len(entries) != 1 or entries[0]["route"] != "ALLOW_FOR_B06":
            fail("B05_B06_ROUTE_DENIED")
        pvr = _validation_receipt_for_route(records, route)
        proofs = [
            item
            for item in pvr["payload"]["route_unit_proofs"]
            if item["route_unit_id"] == route_unit_id
        ]
        if (
            len(proofs) != 1
            or entries[0]["unit_proof_hash"] != proofs[0]["unit_proof_hash"]
        ):
            fail("B05_B06_UNIT_PROOF_MISMATCH")
        _require_effective_protection(pvr, proofs[0], base_candidate_version_record)
        return deepcopy(entries[0])


class B09AdmissionGuard:
    @staticmethod
    def require_route(
        records: list[dict[str, Any]],
        *,
        route_receipt_ref: dict[str, Any],
        causal_hint_proposal_ref: dict[str, Any],
        mapping_proof_hash: str,
        live_pointer_binding_hash: str,
        b02_scope_snapshot_hash: str,
        active_policy_selection_hash: str,
        non_content_gate_snapshot_hash: str,
    ) -> dict[str, Any]:
        route = _active_route(records, route_receipt_ref)
        _require_freshness(
            route,
            live_pointer_binding_hash=live_pointer_binding_hash,
            b02_scope_snapshot_hash=b02_scope_snapshot_hash,
            active_policy_selection_hash=active_policy_selection_hash,
            non_content_gate_snapshot_hash=non_content_gate_snapshot_hash,
        )
        entries = [
            item
            for item in route["payload"]["causal_hint_routes"]
            if canonical_bytes(item["causal_hint_proposal_ref"])
            == canonical_bytes(causal_hint_proposal_ref)
        ]
        if (
            len(entries) != 1
            or entries[0]["route"] != "ROUTE_TO_B09"
            or entries[0]["mapping_proof_hash"] != mapping_proof_hash
        ):
            fail("B05_B09_ROUTE_DENIED")
        pvr = _validation_receipt_for_route(records, route)
        mappings = [
            item
            for item in pvr["payload"]["causal_support_mappings"]
            if canonical_bytes(item["causal_hint_proposal_ref"])
            == canonical_bytes(causal_hint_proposal_ref)
        ]
        if (
            len(mappings) != 1
            or mappings[0]["mapping_status"] != "COMPLETE"
            or entries[0]["mapping_proof_hash"] != mappings[0]["mapping_proof_hash"]
        ):
            fail("B05_B09_MAPPING_PROOF_MISMATCH")
        supporting_units = mappings[0]["supporting_route_unit_ids"]
        routes_by_unit = {
            item["route_unit_id"]: item["route"]
            for item in route["payload"]["route_units"]
        }
        if (
            entries[0]["supporting_route_unit_ids"] != supporting_units
            or not supporting_units
            or any(
                routes_by_unit.get(unit_id) != "ALLOW_FOR_B06"
                for unit_id in supporting_units
            )
        ):
            fail("B05_B09_SUPPORTING_ROUTE_MISMATCH")
        return deepcopy(entries[0])
