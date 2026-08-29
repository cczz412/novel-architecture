"""Build B-03 retention evidence from a verified SourceSlice."""

from __future__ import annotations

from typing import Any

from b03_contracts import (
    build_output_record,
    current_trusted_time_head,
    fail,
    record_ref,
    validate_retention_record,
    validate_slice_record,
)
from b03_store import B03FixtureStore
from restricted_source_reader import SourceReadAuthorizationStateProjector


def _record(
    records: list[dict[str, Any]], ref: dict[str, Any], expected_type: str
) -> dict[str, Any]:
    matches = [item for item in records if record_ref(item) == ref]
    if len(matches) != 1 or matches[0]["record_type"] != expected_type:
        fail("B03_REFERENCE_INTEGRITY_FAILED", expected_type)
    return matches[0]


class RestrictedSourceRetentionController:
    """Prepare the exact tombstone and receipt before one atomic store commit."""

    @staticmethod
    def prepare(
        *,
        slice_record: dict[str, Any],
        policy: dict[str, Any],
        records: list[dict[str, Any]],
        trusted_time_records: list[dict[str, Any]],
        context: dict[str, Any],
        event: str,
    ) -> dict[str, Any]:
        if event not in {"UNREADABLE", "DELETED"}:
            fail("B03_RETENTION_INVALID", "event")
        all_records = [*records, policy]
        validate_slice_record(slice_record, all_records=all_records, context=context)
        request = _record(
            records,
            slice_record["payload"]["request_ref"],
            "M3_SOURCE_READ_REQUEST",
        )
        consent = _record(
            records,
            slice_record["payload"]["source_read_consent_ref"],
            "M3_SOURCE_READ_CONSENT",
        )
        authorization = _record(
            records,
            slice_record["payload"]["authorization_ref"],
            "M3_SOURCE_READ_AUTHORIZATION",
        )
        head = current_trusted_time_head(trusted_time_records)
        SourceReadAuthorizationStateProjector.project(
            request=request,
            authorization=authorization,
            consent=consent,
            policy=policy,
            records=records,
            trusted_time_records=trusted_time_records,
            supplied_time_ref=record_ref(head),
            context=context,
        )
        tombstone = B03FixtureStore.tombstone_for_slice(slice_record)
        receipt = build_output_record(
            record_type="M3_SOURCE_SLICE_RETENTION_RECEIPT",
            created_at=head["payload"]["trusted_evaluation_time"],
            payload={
                "authorized_source_slice_ref": record_ref(slice_record),
                "lifecycle_sequence": 1,
                "event": event,
                "effective_at": head["payload"]["trusted_evaluation_time"],
                "trusted_time_ref": record_ref(head),
                "trusted_evaluation_time": head["payload"]["trusted_evaluation_time"],
                "content_bytes_retained": False,
                "retained_metadata_fields": sorted(
                    tombstone, key=lambda item: item.encode("utf-8")
                ),
            },
        )
        validate_retention_record(receipt, tombstone=tombstone)
        return {
            "slice_ref": record_ref(slice_record),
            "tombstone": tombstone,
            "receipt": receipt,
        }
