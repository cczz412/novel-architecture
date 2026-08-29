"""Pure, non-persistent projection of open B-02 Diagnostics."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from b02_contracts import (
    TERMINAL_EVENTS,
    canonical_bytes,
    fail,
    parse_utc,
    record_ref,
    validate_diagnostic_record,
    validate_identity_record,
    validate_lifecycle_record,
    validate_record,
)


def project_open_diagnostics(
    *, context: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Recompute one scope's open Diagnostics without writing any state."""
    normalized_records = [deepcopy(record) for record in records]
    for record in normalized_records:
        validate_record(record)
    identities = [
        record
        for record in normalized_records
        if record["record_type"] == "M3_DIAGNOSTIC_RECORDER_IDENTITY"
    ]
    diagnostics = [
        record
        for record in normalized_records
        if record["record_type"] == "M3_DIAGNOSTIC"
    ]
    lifecycles = [
        record
        for record in normalized_records
        if record["record_type"] == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT"
    ]
    for identity in identities:
        validate_identity_record(identity)
    validation_records = [*identities, *diagnostics, *lifecycles]
    for diagnostic in diagnostics:
        validate_diagnostic_record(
            diagnostic, context=context, records=validation_records
        )
    diagnostic_by_ref = {
        canonical_bytes(record_ref(item)): item for item in diagnostics
    }
    diagnostic_refs = set(diagnostic_by_ref)
    if len(diagnostic_refs) != len(diagnostics):
        fail("B02_PROJECTION_INVALID", "duplicate Diagnostic input")
    grouped: dict[bytes, list[dict[str, Any]]] = defaultdict(list)
    for lifecycle in lifecycles:
        validate_lifecycle_record(lifecycle, records=validation_records)
        key = canonical_bytes(lifecycle["payload"]["diagnostic_ref"])
        if key not in diagnostic_refs:
            fail("B02_PROJECTION_INVALID", "lifecycle outside input Diagnostics")
        grouped[key].append(lifecycle)

    open_items: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        key = canonical_bytes(record_ref(diagnostic))
        diagnostic_created_at = parse_utc(
            diagnostic_by_ref[key]["created_at"], "B02_PROJECTION_INVALID"
        )
        stream = sorted(
            grouped.get(key, []),
            key=lambda record: (
                record["payload"]["lifecycle_sequence"],
                record["record_id"],
                record["record_hash"],
            ),
        )
        prior_sequence = 0
        prior_time = None
        prior_event = None
        terminal_seen = False
        for lifecycle in stream:
            payload = lifecycle["payload"]
            sequence = payload["lifecycle_sequence"]
            effective = parse_utc(payload["effective_at"], "B02_PROJECTION_INVALID")
            if effective < diagnostic_created_at:
                fail("B02_PROJECTION_INVALID", "lifecycle before Diagnostic")
            if sequence <= prior_sequence:
                fail("B02_PROJECTION_INVALID", "lifecycle sequence")
            if prior_time is not None and effective < prior_time:
                fail("B02_PROJECTION_INVALID", "lifecycle time")
            if (
                prior_time is not None
                and effective == prior_time
                and payload["event"] != prior_event
            ):
                fail("B02_PROJECTION_INVALID", "same-time event conflict")
            if terminal_seen:
                fail("B02_PROJECTION_INVALID", "event after terminal")
            terminal_seen = payload["event"] in TERMINAL_EVENTS
            prior_sequence = sequence
            prior_time = effective
            prior_event = payload["event"]
        if not stream or stream[-1]["payload"]["event"] not in TERMINAL_EVENTS:
            target = diagnostic["payload"]["target"]
            lineage = target["lineage_locator"]
            evidence = target["evidence_locator"]
            open_items.append(
                {
                    "diagnostic_ref": record_ref(diagnostic),
                    "lineage_id": lineage["lineage_id"],
                    "item_json_pointer": lineage["json_pointer"],
                    "lineage_locator_hash": lineage["locator_hash"],
                    "evidence_json_pointer": evidence["evidence_json_pointer"],
                    "evidence_sha256": evidence["evidence_sha256"],
                    "evidence_locator_hash": evidence["locator_hash"],
                }
            )

    open_items.sort(
        key=lambda item: (
            item["diagnostic_ref"]["record_id"],
            item["diagnostic_ref"]["record_version"],
            item["diagnostic_ref"]["record_hash"],
        )
    )
    open_refs = [item["diagnostic_ref"] for item in open_items]
    candidate = context["candidate_version"]
    result = {
        "view_type": "DERIVED_RECOMPUTABLE",
        "base_candidate_version_ref": record_ref(candidate),
        "chapter_revision_ref": deepcopy(
            candidate["payload"]["chapter_revision_ref"]
        ),
        "seg": candidate["payload"]["seg"],
        "open_diagnostic_refs": open_refs,
        "open_diagnostics": open_items,
        "open_count": len(open_refs),
    }
    return result
