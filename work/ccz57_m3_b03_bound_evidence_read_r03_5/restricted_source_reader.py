"""Bound-evidence reader; callers never provide a text range."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from b03_contracts import (
    ACTIVE_STATE,
    SLICE_RETENTION,
    build_output_record,
    fail,
    projected_state,
    record_ref,
    require_current_trusted_time,
    resolve_bound_candidate_input,
    validate_authorization_record,
    validate_consent_record,
    validate_lifecycle_streams,
    validate_policy_record,
    validate_request_record,
    validate_slice_record,
)


def _linked_lifecycle_refs(
    records: list[dict[str, Any]],
    parent_ref: dict[str, Any],
    record_type: str,
) -> list[dict[str, Any]]:
    return [
        record_ref(record)
        for record in records
        if record["record_type"] == record_type
        and record["payload"]["parent_ref"] == parent_ref
    ]


class SourceReadAuthorizationStateProjector:
    """Pure, non-persistent current-state projector."""

    @staticmethod
    def project(
        *,
        request: dict[str, Any],
        authorization: dict[str, Any],
        consent: dict[str, Any],
        policy: dict[str, Any],
        records: list[dict[str, Any]],
        trusted_time_records: list[dict[str, Any]],
        supplied_time_ref: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        validate_policy_record(policy)
        validate_request_record(request, context=context)
        all_records = [*records, policy]
        validate_consent_record(consent, records=all_records, context=context)
        validate_authorization_record(
            authorization, all_records=all_records, context=context
        )
        if (
            authorization["payload"]["request_ref"] != record_ref(request)
            or authorization["payload"]["source_read_consent_ref"]
            != record_ref(consent)
            or consent["payload"]["request_ref"] != record_ref(request)
            or consent["payload"]["policy_ref"]
            != authorization["payload"]["policy_ref"]
        ):
            fail("B03_AUTHORIZATION_BINDING_DRIFT")
        validate_lifecycle_streams(records)
        head = require_current_trusted_time(supplied_time_ref, trusted_time_records)
        auth_lifecycle = [
            record
            for record in records
            if record["record_type"] == "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT"
            and record["payload"]["parent_ref"] == record_ref(authorization)
        ]
        consent_lifecycle = [
            record
            for record in records
            if record["record_type"] == "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT"
            and record["payload"]["parent_ref"] == record_ref(consent)
        ]
        now = head["payload"]["trusted_evaluation_time"]
        return {
            "authorization_lifecycle_refs": _linked_lifecycle_refs(
                records,
                record_ref(authorization),
                "M3_SOURCE_READ_AUTHORIZATION_LIFECYCLE_RECEIPT",
            ),
            "consent_lifecycle_refs": _linked_lifecycle_refs(
                records,
                record_ref(consent),
                "M3_SOURCE_READ_CONSENT_LIFECYCLE_RECEIPT",
            ),
            "trusted_time_ref": record_ref(head),
            "trusted_evaluation_time": now,
            "projected_authorization_state": projected_state(
                authorization, auth_lifecycle, now
            ),
            "projected_consent_state": projected_state(consent, consent_lifecycle, now),
        }


class RestrictedSourceReader:
    """Build one exact-evidence SourceSlice after the first authorization check."""

    @staticmethod
    def build_slice(
        *,
        request: dict[str, Any],
        authorization: dict[str, Any],
        consent: dict[str, Any],
        policy: dict[str, Any],
        records: list[dict[str, Any]],
        trusted_time_records: list[dict[str, Any]],
        supplied_time_ref: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        state = SourceReadAuthorizationStateProjector.project(
            request=request,
            authorization=authorization,
            consent=consent,
            policy=policy,
            records=records,
            trusted_time_records=trusted_time_records,
            supplied_time_ref=supplied_time_ref,
            context=context,
        )
        if (
            state["projected_authorization_state"] != ACTIVE_STATE
            or state["projected_consent_state"] != ACTIVE_STATE
        ):
            fail("B03_SOURCE_READ_NOT_ACTIVE")
        resolved = resolve_bound_candidate_input(
            {
                "subject": request["payload"]["subject"],
                "evidence_binding": request["payload"]["evidence_binding"],
                "purpose": request["payload"]["purpose"],
            },
            context=context,
        )
        content = resolved["item"]["evidence"]
        payload = {
            "request_ref": record_ref(request),
            "authorization_ref": record_ref(authorization),
            "source_read_consent_ref": record_ref(consent),
            **state,
            "subject": deepcopy(request["payload"]["subject"]),
            "evidence_binding": deepcopy(request["payload"]["evidence_binding"]),
            "source_revision_ref": deepcopy(
                request["payload"]["subject"]["source_revision_ref"]
            ),
            "source_generation_ref": deepcopy(
                request["payload"]["subject"]["source_generation_ref"]
            ),
            "b02_context_hash": request["payload"]["b02_context_hash"],
            "content": content,
            "content_sha256": request["payload"]["evidence_binding"]["evidence_sha256"],
            "content_utf8_bytes": len(content.encode("utf-8")),
            "expires_at": authorization["payload"]["expires_at"],
            "content_access_state": "READABLE_UNTIL_EXPIRY",
        }
        slice_record = build_output_record(
            record_type="M3_AUTHORIZED_SOURCE_SLICE",
            payload=payload,
            created_at=state["trusted_evaluation_time"],
            retention_class=SLICE_RETENTION,
        )
        validate_slice_record(
            slice_record, all_records=[*records, policy], context=context
        )
        return slice_record
