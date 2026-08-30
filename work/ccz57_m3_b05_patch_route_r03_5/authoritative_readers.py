"""Bounded, read-only interfaces consumed by the B-05 offline shell."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    validate_candidate_version as b01_validate_candidate_version,
    validate_evidence_locator as b01_validate_evidence_locator,
    validate_lineage_locator as b01_validate_lineage_locator,
    validate_pointer_snapshot as b01_validate_pointer_snapshot,
    validate_segment_index_snapshot as b01_validate_segment_index,
)
from work.ccz57_m3_b02_diagnostic_coverage_r03_5.b02_contracts import (  # noqa: E402
    B02ContractError,
    validate_coverage_record as b02_validate_coverage_record,
    validate_diagnostic_record as b02_validate_diagnostic_record,
    validate_identity_record as b02_validate_identity_record,
    validate_lifecycle_record as b02_validate_lifecycle_record,
    validate_upstream_context as b02_validate_upstream_context,
)
from work.ccz57_m3_b04_patch_atomic_group_r03_5.b04_contracts import (  # noqa: E402
    B04ContractError,
    validate_causal_record as b04_validate_causal_record,
    validate_atomic_groups as b04_validate_atomic_groups,
    validate_patch_record as b04_validate_patch_record,
    validate_protection_record as b04_validate_protection_record,
)

from b05_contracts import (  # noqa: E402
    B05ContractError,
    CANDIDATE_SCHEMA_ID,
    canonical_bytes,
    fail,
    record_ref,
    sha256_value,
    stable_sorted,
    validate_immutable_record,
    validate_record_ref,
)

ReadHook = Callable[[int], None]


class _ReadOnlyReader:
    __slots__ = ("reader_identity", "reader_version", "_read_count", "_hook")

    def __init__(self, identity: str, version: str) -> None:
        if not identity or not version:
            fail("B05_READER_IDENTITY_INVALID")
        self.reader_identity = identity
        self.reader_version = version
        self._read_count = 0
        self._hook: ReadHook | None = None

    def set_read_hook(self, hook: ReadHook | None) -> None:
        self._hook = hook

    def _before_read(self) -> None:
        self._read_count += 1
        if self._hook is not None:
            self._hook(self._read_count)

    @property
    def read_count(self) -> int:
        return self._read_count


class B01CurrentReaderAdapter(_ReadOnlyReader):
    """One atomic read of exact B-01 originals plus the mutable live binding."""

    __slots__ = (
        "candidate_version",
        "segment_index",
        "pointer_snapshot",
        "live_pointer_binding",
        "reference_records",
        "lineage_locators",
        "evidence_locators",
        "segment_inputs",
    )

    LIVE_POINTER_KEYS = {
        "project_scope_id",
        "author_workspace_logical_key",
        "logical_pointer_key",
        "pointer_namespace",
        "candidate_schema_id",
        "input_binding_hash",
        "chapter_revision_ref",
        "seg",
        "generation",
        "current_candidate_version_ref",
    }

    def __init__(
        self,
        *,
        candidate_version: dict[str, Any],
        segment_index: dict[str, Any],
        live_pointer_binding: dict[str, Any],
        pointer_snapshot: dict[str, Any] | None = None,
        reference_records: list[dict[str, Any]],
        lineage_locators: list[dict[str, Any]],
        evidence_locators: list[dict[str, Any]],
        segment_inputs: list[dict[str, Any]],
        reader_identity: str = "B01CurrentReaderAdapter",
        reader_version: str = "b05-r03.5-fixture-1",
    ) -> None:
        super().__init__(reader_identity, reader_version)
        self.candidate_version = deepcopy(candidate_version)
        self.segment_index = deepcopy(segment_index)
        self.pointer_snapshot = deepcopy(pointer_snapshot)
        self.live_pointer_binding = deepcopy(live_pointer_binding)
        self.reference_records = deepcopy(reference_records)
        self.lineage_locators = deepcopy(lineage_locators)
        self.evidence_locators = deepcopy(evidence_locators)
        self.segment_inputs = deepcopy(segment_inputs)

    def read_scope(self) -> dict[str, Any]:
        self._before_read()
        validation_records = [
            *deepcopy(self.reference_records),
            deepcopy(self.segment_index),
        ]
        try:
            b01_validate_segment_index(self.segment_index)
            b01_validate_candidate_version(
                self.candidate_version,
                allow_child=True,
                reference_records=validation_records,
            )
            if self.pointer_snapshot is not None:
                b01_validate_pointer_snapshot(
                    self.pointer_snapshot,
                    records=[*validation_records, deepcopy(self.candidate_version)],
                )
            for locator in self.lineage_locators:
                b01_validate_lineage_locator(
                    locator,
                    candidate_version=self.candidate_version,
                    reference_records=validation_records,
                )
            for locator in self.evidence_locators:
                b01_validate_evidence_locator(
                    locator,
                    candidate_version=self.candidate_version,
                    reference_records=validation_records,
                )
        except B01ContractError as error:
            fail("B05_B01_CURRENT_READER_INVALID", error.code)
        candidate_lineages = sorted(
            item["lineage_id"] for item in self.candidate_version["payload"]["items"]
        )
        lineage_ids = sorted(locator.get("lineage_id") for locator in self.lineage_locators)
        evidence_ids = sorted(locator.get("lineage_id") for locator in self.evidence_locators)
        if candidate_lineages != lineage_ids or candidate_lineages != evidence_ids:
            fail("B05_B01_LOCATOR_CLOSURE_INVALID")
        if set(self.live_pointer_binding) != self.LIVE_POINTER_KEYS:
            fail("B05_B01_LIVE_POINTER_SHAPE_INVALID")
        if self.live_pointer_binding["candidate_schema_id"] != CANDIDATE_SCHEMA_ID:
            fail("B05_B01_LIVE_POINTER_SCHEMA_INVALID")
        candidate_payload = self.candidate_version["payload"]
        if candidate_payload.get("candidate_schema_id") != CANDIDATE_SCHEMA_ID:
            fail("B05_B01_CANDIDATE_SCHEMA_INVALID")
        if (
            canonical_bytes(candidate_payload.get("chapter_revision_ref"))
            != canonical_bytes(self.live_pointer_binding["chapter_revision_ref"])
            or candidate_payload.get("seg") != self.live_pointer_binding["seg"]
        ):
            fail("B05_B01_POINTER_SCOPE_MISMATCH")
        if canonical_bytes(
            self.segment_index["payload"].get("chapter_revision_ref")
        ) != canonical_bytes(candidate_payload.get("chapter_revision_ref")):
            fail("B05_B01_SEGMENT_INDEX_SCOPE_MISMATCH")
        candidate_segment_ref = candidate_payload.get("segment_index_ref")
        if canonical_bytes(candidate_segment_ref) != canonical_bytes(
            record_ref(self.segment_index)
        ):
            fail("B05_B01_SEGMENT_INDEX_REF_MISMATCH")
        current_ref = self.live_pointer_binding["current_candidate_version_ref"]
        validate_record_ref(current_ref, expected_type="M3_CANDIDATE_VERSION")
        upstream_context = {
            "reference_records": deepcopy(self.reference_records),
            "segment_index": deepcopy(self.segment_index),
            "candidate_version": deepcopy(self.candidate_version),
            "lineage_locators": deepcopy(self.lineage_locators),
            "evidence_locators": deepcopy(self.evidence_locators),
            "segment_inputs": deepcopy(self.segment_inputs),
        }
        return {
            "reader_identity": self.reader_identity,
            "reader_version": self.reader_version,
            "candidate_version_record": deepcopy(self.candidate_version),
            "segment_index_record": deepcopy(self.segment_index),
            "candidate_pointer_snapshot_record_or_null": deepcopy(
                self.pointer_snapshot
            ),
            "live_pointer_binding": deepcopy(self.live_pointer_binding),
            "live_pointer_binding_hash": sha256_value(self.live_pointer_binding),
            "candidate_reference_records": deepcopy(validation_records),
            "upstream_context": upstream_context,
        }


class B02CurrentScopeReader(_ReadOnlyReader):
    """Read selected Diagnostic streams and Coverage originals as one scope."""

    __slots__ = ("records",)
    TERMINAL_EVENTS = {"SUPERSEDED_BY_PATCH_REVIEW", "CLOSED"}
    DIAGNOSTIC_PAYLOAD_KEYS = {
        "base_candidate_version_ref",
        "candidate_schema_id",
        "chapter_revision_ref",
        "seg",
        "axis",
        "severity",
        "target",
        "fingerprint",
        "writer_identity_ref",
    }
    COVERAGE_PAYLOAD_KEYS = {
        "base_candidate_version_ref",
        "candidate_schema_id",
        "chapter_revision_ref",
        "seg",
        "source_observation_id",
        "source_evidence_binding",
        "axis",
        "candidate_match",
        "matched_candidate_bindings",
        "observer_ref",
    }
    LIFECYCLE_PAYLOAD_KEYS = {
        "diagnostic_ref",
        "lifecycle_sequence",
        "event",
        "effective_at",
        "reason_code",
        "resolution_ref",
    }

    def __init__(
        self,
        *,
        records: list[dict[str, Any]],
        reader_identity: str = "B02CurrentScopeReader",
        reader_version: str = "b05-r03.5-fixture-1",
    ) -> None:
        super().__init__(reader_identity, reader_version)
        self.records = deepcopy(records)

    def read_scope(
        self,
        *,
        base_candidate_version_ref: dict[str, Any],
        upstream_context: dict[str, Any],
        selected_diagnostic_refs: list[dict[str, Any]],
        selected_coverage_observation_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._before_read()
        validate_record_ref(
            base_candidate_version_ref, expected_type="M3_CANDIDATE_VERSION"
        )
        diagnostics = stable_sorted(selected_diagnostic_refs)
        coverages = stable_sorted(selected_coverage_observation_refs)
        for ref in diagnostics:
            validate_record_ref(ref, expected_type="M3_DIAGNOSTIC")
        for ref in coverages:
            validate_record_ref(ref, expected_type="M3_COVERAGE_OBSERVATION")
        current_record_type = "UPSTREAM_CONTEXT"
        try:
            context = b02_validate_upstream_context(**deepcopy(upstream_context))
            all_records = deepcopy(self.records)
            for record in all_records:
                record_type = record.get("record_type")
                current_record_type = str(record_type)
                if record_type == "M3_DIAGNOSTIC_RECORDER_IDENTITY":
                    b02_validate_identity_record(record)
                elif record_type == "M3_DIAGNOSTIC":
                    b02_validate_diagnostic_record(
                        record, context=context, records=all_records
                    )
                elif record_type == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT":
                    b02_validate_lifecycle_record(record, records=all_records)
                elif record_type == "M3_COVERAGE_OBSERVATION":
                    b02_validate_coverage_record(
                        record, context=context, records=all_records
                    )
                else:
                    fail("B05_B02_SCOPE_RECORD_TYPE_INVALID", str(record_type))
        except B02ContractError as error:
            mapped = {
                "M3_DIAGNOSTIC": "B05_B02_DIAGNOSTIC_SCOPE_INVALID",
                "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT": (
                    "B05_B02_LIFECYCLE_INVALID"
                ),
                "M3_COVERAGE_OBSERVATION": "B05_B02_COVERAGE_SCOPE_INVALID",
            }.get(current_record_type, "B05_B02_SCOPE_READER_INVALID")
            fail(mapped, error.code)
        candidate_payload = context["candidate_version"]["payload"]
        expected_candidate_schema_id = candidate_payload["candidate_schema_id"]
        expected_chapter_revision_ref = candidate_payload["chapter_revision_ref"]
        expected_seg = candidate_payload["seg"]
        if canonical_bytes(record_ref(context["candidate_version"])) != canonical_bytes(
            base_candidate_version_ref
        ):
            fail("B05_B02_SCOPE_BASE_MISMATCH")
        by_ref: dict[bytes, dict[str, Any]] = {}
        for record in self.records:
            try:
                validate_immutable_record(record)
            except B05ContractError as error:
                fail("B05_B02_SCOPE_READER_INVALID", error.code)
            key = canonical_bytes(record_ref(record))
            if record["record_type"] == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT":
                if set(record["payload"]) != self.LIFECYCLE_PAYLOAD_KEYS:
                    fail("B05_B02_LIFECYCLE_SHAPE_INVALID")
                validate_record_ref(
                    record["payload"].get("diagnostic_ref"),
                    expected_type="M3_DIAGNOSTIC",
                )
            if key in by_ref and canonical_bytes(by_ref[key]) != canonical_bytes(
                record
            ):
                fail("B05_B02_SCOPE_AMBIGUOUS")
            by_ref[key] = record
        diagnostic_records = []
        lifecycle_streams = []
        diagnostic_state_bindings = []
        for diagnostic_ref in diagnostics:
            diagnostic = by_ref.get(canonical_bytes(diagnostic_ref))
            if diagnostic is None:
                fail("B05_B02_DIAGNOSTIC_UNRESOLVABLE")
            diagnostic_records.append(deepcopy(diagnostic))
            diagnostic_payload = diagnostic["payload"]
            if set(diagnostic_payload) != self.DIAGNOSTIC_PAYLOAD_KEYS:
                fail("B05_B02_DIAGNOSTIC_SHAPE_INVALID")
            if canonical_bytes(
                diagnostic_payload.get("base_candidate_version_ref")
            ) != canonical_bytes(base_candidate_version_ref):
                fail("B05_B02_DIAGNOSTIC_BASE_SCOPE_INVALID")
            if (
                diagnostic_payload.get("candidate_schema_id")
                != expected_candidate_schema_id
                or canonical_bytes(diagnostic_payload.get("chapter_revision_ref"))
                != canonical_bytes(expected_chapter_revision_ref)
                or diagnostic_payload.get("seg") != expected_seg
            ):
                fail("B05_B02_DIAGNOSTIC_SCOPE_INVALID")
            lifecycle = []
            for record in self.records:
                if record["record_type"] != "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT":
                    continue
                if canonical_bytes(
                    record["payload"].get("diagnostic_ref")
                ) == canonical_bytes(diagnostic_ref):
                    lifecycle.append(record)
            lifecycle.sort(
                key=lambda item: (
                    item["payload"].get("lifecycle_sequence", 0),
                    item["record_id"],
                    item["record_hash"],
                )
            )
            sequences = [
                item["payload"].get("lifecycle_sequence") for item in lifecycle
            ]
            if sequences != list(range(1, len(sequences) + 1)):
                fail("B05_B02_LIFECYCLE_INCOMPLETE")
            effective_times = []
            terminal_seen = False
            for lifecycle_index, lifecycle_record in enumerate(lifecycle):
                lifecycle_payload = lifecycle_record["payload"]
                if terminal_seen:
                    fail("B05_B02_LIFECYCLE_AFTER_TERMINAL")
                try:
                    effective_times.append(
                        datetime.strptime(
                            lifecycle_payload["effective_at"],
                            "%Y-%m-%dT%H:%M:%SZ",
                        ).replace(tzinfo=timezone.utc)
                    )
                except (KeyError, TypeError, ValueError) as error:
                    fail("B05_B02_LIFECYCLE_TIME_INVALID", type(error).__name__)
                if lifecycle_index and effective_times[-1] <= effective_times[-2]:
                    fail("B05_B02_LIFECYCLE_TIME_NOT_INCREASING")
                terminal_seen = lifecycle_payload.get("event") in self.TERMINAL_EVENTS
            current = "OPEN"
            if lifecycle:
                event = lifecycle[-1]["payload"].get("event")
                current = event if event in self.TERMINAL_EVENTS else "OPEN"
            lifecycle_refs = [record_ref(item) for item in lifecycle]
            stream_preimage = {
                "diagnostic_ref": diagnostic_ref,
                "ordered_lifecycle_receipt_refs": lifecycle_refs,
                "current_terminal_state": current,
            }
            lifecycle_streams.append(
                {
                    "diagnostic_ref": deepcopy(diagnostic_ref),
                    "records": deepcopy(lifecycle),
                    "lifecycle_stream_hash": sha256_value(stream_preimage),
                    "current_terminal_state": current,
                }
            )
            diagnostic_state_bindings.append(
                {
                    "diagnostic_ref": deepcopy(diagnostic_ref),
                    "lifecycle_receipt_refs": lifecycle_refs,
                    "lifecycle_stream_hash": sha256_value(stream_preimage),
                    "current_terminal_state": current,
                }
            )
        coverage_records = []
        for coverage_ref in coverages:
            coverage = by_ref.get(canonical_bytes(coverage_ref))
            if coverage is None:
                fail("B05_B02_COVERAGE_UNRESOLVABLE")
            coverage_payload = coverage["payload"]
            if set(coverage_payload) != self.COVERAGE_PAYLOAD_KEYS:
                fail("B05_B02_COVERAGE_SHAPE_INVALID")
            if canonical_bytes(
                coverage_payload.get("base_candidate_version_ref")
            ) != canonical_bytes(base_candidate_version_ref):
                fail("B05_B02_COVERAGE_BASE_SCOPE_INVALID")
            if (
                coverage_payload.get("candidate_schema_id")
                != expected_candidate_schema_id
                or canonical_bytes(coverage_payload.get("chapter_revision_ref"))
                != canonical_bytes(expected_chapter_revision_ref)
                or coverage_payload.get("seg") != expected_seg
            ):
                fail("B05_B02_COVERAGE_SCOPE_INVALID")
            coverage_records.append(deepcopy(coverage))
        diagnostic_state_bindings = stable_sorted(diagnostic_state_bindings)
        coverage_refs = [record_ref(item) for item in coverage_records]
        scope_preimage = {
            "reader_identity": self.reader_identity,
            "reader_version": self.reader_version,
            "base_candidate_version_ref": deepcopy(base_candidate_version_ref),
            "diagnostic_state_bindings": diagnostic_state_bindings,
            "coverage_observation_refs": coverage_refs,
        }
        scope_hash = sha256_value(scope_preimage)
        return {
            "reader_identity": self.reader_identity,
            "reader_version": self.reader_version,
            "base_candidate_version_ref": deepcopy(base_candidate_version_ref),
            "diagnostic_records": diagnostic_records,
            "lifecycle_streams": lifecycle_streams,
            "coverage_observation_records": coverage_records,
            "scope_record_refs": stable_sorted(
                [
                    *[record_ref(item) for item in diagnostic_records],
                    *[
                        record_ref(item)
                        for stream in lifecycle_streams
                        for item in stream["records"]
                    ],
                    *coverage_refs,
                ]
            ),
            "diagnostic_state_bindings": diagnostic_state_bindings,
            "coverage_observation_refs": coverage_refs,
            "scope_snapshot_hash": scope_hash,
        }


class B04PatchClosureReader:
    """Validate the exact B-04 closure while keeping SourceSlice bytes opaque."""

    @staticmethod
    def read(
        *,
        patch_proposal: dict[str, Any],
        protection_set: dict[str, Any],
        causal_hint_proposals: list[dict[str, Any]],
        protection_policy: dict[str, Any],
        source_slice_records: list[dict[str, Any]],
        upstream_context: dict[str, Any],
        b02_scope: dict[str, Any],
    ) -> dict[str, Any]:
        validate_immutable_record(patch_proposal, expected_type="M3_PATCH_PROPOSAL")
        validate_immutable_record(
            protection_set, expected_type="M3_CANDIDATE_PROTECTION_SET"
        )
        causal_hint_proposals = sorted(
            deepcopy(causal_hint_proposals),
            key=lambda item: canonical_bytes(record_ref(item)),
        )
        for record in causal_hint_proposals:
            validate_immutable_record(record, expected_type="M3_CAUSAL_HINT_PROPOSAL")
        diagnostics = deepcopy(b02_scope["diagnostic_records"])
        coverages = deepcopy(b02_scope["coverage_observation_records"])
        lifecycle_receipts = [
            deepcopy(record)
            for stream in b02_scope["lifecycle_streams"]
            for record in stream["records"]
        ]
        if source_slice_records:
            fail("B05_B03_DIRECT_RECORD_READ_FORBIDDEN")
        source_refs = deepcopy(
            patch_proposal["payload"].get("authorized_source_slice_refs", [])
        )
        try:
            b04_validate_protection_record(
                protection_set,
                context=upstream_context,
                policy=protection_policy,
                groups=patch_proposal["payload"]["atomic_groups"],
            )
            for causal in causal_hint_proposals:
                b04_validate_causal_record(
                    causal,
                    context=upstream_context,
                    diagnostic_refs=[record_ref(item) for item in diagnostics],
                    coverage_refs=[record_ref(item) for item in coverages],
                    source_slice_refs=source_refs,
                )
            if source_refs:
                if patch_proposal["payload"].get("candidate_schema_id") != (
                    CANDIDATE_SCHEMA_ID
                ):
                    raise B04ContractError("B04_CANDIDATE_SCHEMA_MISMATCH")
                used_diagnostics, used_coverages = b04_validate_atomic_groups(
                    patch_proposal["payload"]["atomic_groups"],
                    context=upstream_context,
                    diagnostics=diagnostics,
                    coverages=coverages,
                    lifecycle_receipts=lifecycle_receipts,
                )
                if used_diagnostics != {
                    canonical_bytes(ref)
                    for ref in patch_proposal["payload"]["diagnostic_refs"]
                } or used_coverages != {
                    canonical_bytes(ref)
                    for ref in patch_proposal["payload"][
                        "coverage_observation_refs"
                    ]
                }:
                    fail("B05_B04_SUPPORT_CLOSURE_INVALID")
                operations = [
                    operation
                    for group in patch_proposal["payload"]["atomic_groups"]
                    for operation in group["operations"]
                ]
                if (
                    len(source_refs) != 1
                    or len(operations) != 1
                    or operations[0].get("operation_kind")
                    != "REPLACE_CANDIDATE_ITEM"
                ):
                    fail("B05_B04_SOURCE_SLICE_SCOPE_INVALID")
                operation = operations[0]
                target = operation["target"]
                old_items = [
                    item
                    for item in upstream_context["candidate_version"]["payload"][
                        "items"
                    ]
                    if item["lineage_id"] == target["lineage_id"]
                ]
                if len(old_items) != 1 or (
                    operation["new_item"]["evidence"] != old_items[0]["evidence"]
                    or operation["new_item"]["evidence_binding"]
                    != old_items[0]["evidence_binding"]
                ):
                    fail("B05_B04_SOURCE_SLICE_SCOPE_INVALID")
            else:
                b04_validate_patch_record(
                    patch_proposal,
                    context=upstream_context,
                    diagnostics=diagnostics,
                    coverages=coverages,
                    lifecycle_receipts=lifecycle_receipts,
                    source_slice_records=[],
                    protection=protection_set,
                    causal_records=causal_hint_proposals,
                )
        except B04ContractError as error:
            fail("B05_B04_CLOSURE_INVALID", error.code)
        patch = patch_proposal["payload"]
        if set(patch) != {
            "base_candidate_version_ref",
            "candidate_schema_id",
            "diagnostic_refs",
            "coverage_observation_refs",
            "authorized_source_slice_refs",
            "protection_set_ref",
            "chapter_revision_ref",
            "atomic_groups",
            "sidecar_proposal_refs",
        }:
            fail("B05_B04_PATCH_PAYLOAD_SHAPE_INVALID")
        protection_payload = protection_set["payload"]
        if set(protection_payload) != {
            "base_candidate_version_ref",
            "protection_policy_ref",
            "chapter_revision_ref",
            "protected_entries",
        }:
            fail("B05_B04_PROTECTION_PAYLOAD_SHAPE_INVALID")
        if patch_proposal["record_id"] != f"patch-proposal:{sha256_value(patch)}":
            fail("B05_B04_PATCH_IDENTITY_INVALID")
        if protection_set["record_id"] != (
            f"protection-set:{sha256_value(protection_payload)}"
        ):
            fail("B05_B04_PROTECTION_IDENTITY_INVALID")
        validate_record_ref(
            patch["base_candidate_version_ref"], expected_type="M3_CANDIDATE_VERSION"
        )
        validate_record_ref(
            protection_payload["base_candidate_version_ref"],
            expected_type="M3_CANDIDATE_VERSION",
        )
        if canonical_bytes(patch["base_candidate_version_ref"]) != canonical_bytes(
            protection_payload["base_candidate_version_ref"]
        ) or canonical_bytes(patch["chapter_revision_ref"]) != canonical_bytes(
            protection_payload["chapter_revision_ref"]
        ):
            fail("B05_B04_PROTECTION_BASE_BINDING_MISMATCH")
        validate_record_ref(protection_payload["protection_policy_ref"])
        diagnostic_refs = stable_sorted(patch["diagnostic_refs"])
        coverage_refs = stable_sorted(patch["coverage_observation_refs"])
        if patch["diagnostic_refs"] != diagnostic_refs:
            fail("B05_B04_DIAGNOSTIC_REFS_INVALID")
        if patch["coverage_observation_refs"] != coverage_refs:
            fail("B05_B04_COVERAGE_REFS_INVALID")
        for ref in diagnostic_refs:
            validate_record_ref(ref, expected_type="M3_DIAGNOSTIC")
        for ref in coverage_refs:
            validate_record_ref(ref, expected_type="M3_COVERAGE_OBSERVATION")
        if canonical_bytes(patch.get("protection_set_ref")) != canonical_bytes(
            record_ref(protection_set)
        ):
            fail("B05_B04_PROTECTION_REF_MISMATCH")
        expected_causal = [record_ref(item) for item in causal_hint_proposals]
        if patch.get("sidecar_proposal_refs") != expected_causal:
            fail("B05_B04_CAUSAL_CLOSURE_MISMATCH")
        source_refs = patch.get("authorized_source_slice_refs", [])
        if source_refs != stable_sorted(source_refs):
            fail("B05_B04_SOURCE_SLICE_REFS_INVALID")
        for ref in source_refs:
            validate_record_ref(ref, expected_type="M3_AUTHORIZED_SOURCE_SLICE")
        for causal in causal_hint_proposals:
            causal_payload = causal["payload"]
            if set(causal_payload) != {
                "from_lineage_locator",
                "to_lineage_locator",
                "evidence_locators",
                "coverage_observation_refs",
                "authorized_source_slice_refs",
                "diagnostic_refs",
                "hint_kind",
                "expiry_request_seconds",
                "noncommittable",
                "chapter_revision_ref",
            }:
                fail("B05_B04_CAUSAL_PAYLOAD_SHAPE_INVALID")
            if causal["record_id"] != (
                f"causal-hint-proposal:{sha256_value(causal_payload)}"
            ):
                fail("B05_B04_CAUSAL_IDENTITY_INVALID")
            if causal_payload["noncommittable"] is not True:
                fail("B05_B04_CAUSAL_COMMITTABLE_FORBIDDEN")
            if canonical_bytes(
                causal_payload["chapter_revision_ref"]
            ) != canonical_bytes(patch["chapter_revision_ref"]):
                fail("B05_B04_CAUSAL_REVISION_MISMATCH")
            causal_diagnostics = stable_sorted(causal_payload["diagnostic_refs"])
            causal_coverages = stable_sorted(
                causal_payload["coverage_observation_refs"]
            )
            if any(ref not in diagnostic_refs for ref in causal_diagnostics):
                fail("B05_B04_CAUSAL_DIAGNOSTIC_SCOPE_INVALID")
            if any(ref not in coverage_refs for ref in causal_coverages):
                fail("B05_B04_CAUSAL_COVERAGE_SCOPE_INVALID")
            causal_refs = causal_payload.get("authorized_source_slice_refs", [])
            if causal_refs != stable_sorted(causal_refs):
                fail("B05_B04_CAUSAL_SOURCE_REFS_INVALID")
            if canonical_bytes(causal_refs) != canonical_bytes(source_refs):
                fail("B05_B04_CAUSAL_SOURCE_SCOPE_INVALID")
        groups = patch.get("atomic_groups")
        if not isinstance(groups, list) or not groups:
            fail("B05_B04_GROUP_CATALOG_INVALID")
        seen: set[str] = set()
        for group in groups:
            if set(group) != {
                "atomic_group_id",
                "purpose",
                "operations",
                "group_payload_hash",
            }:
                fail("B05_B04_GROUP_SHAPE_INVALID")
            group_id = group["atomic_group_id"]
            if not isinstance(group_id, str) or not group_id or group_id in seen:
                fail("B05_B04_GROUP_ID_INVALID")
            seen.add(group_id)
            expected_hash = sha256_value(
                {
                    key: value
                    for key, value in group.items()
                    if key != "group_payload_hash"
                }
            )
            if group["group_payload_hash"] != expected_hash:
                fail("B05_B04_GROUP_HASH_MISMATCH")
            if not isinstance(group["operations"], list) or not group["operations"]:
                fail("B05_B04_OPERATION_LIST_INVALID")
            for operation in group["operations"]:
                kind = operation.get("operation_kind")
                if kind == "REPLACE_CANDIDATE_ITEM":
                    expected_keys = {
                        "operation_kind",
                        "target",
                        "expected_old_item_hash",
                        "new_item",
                        "supporting_diagnostic_refs",
                        "supporting_coverage_refs",
                    }
                elif kind == "ADD_CANDIDATE_ITEM":
                    expected_keys = {
                        "operation_kind",
                        "target_collection_pointer",
                        "new_item",
                        "supporting_coverage_refs",
                    }
                else:
                    fail("B05_B04_OPERATION_KIND_INVALID", str(kind))
                if set(operation) != expected_keys:
                    fail("B05_B04_OPERATION_SHAPE_INVALID")
        return {
            "patch_proposal": deepcopy(patch_proposal),
            "protection_set": deepcopy(protection_set),
            "causal_hint_proposals": causal_hint_proposals,
            "protection_policy": deepcopy(protection_policy),
            "source_slice_records": deepcopy(source_slice_records),
            "closure_snapshot_hash": sha256_value(
                {
                    "patch_proposal_ref": record_ref(patch_proposal),
                    "protection_set_ref": record_ref(protection_set),
                    "causal_hint_proposal_refs": [
                        record_ref(item) for item in causal_hint_proposals
                    ],
                    "protection_policy_ref": record_ref(protection_policy),
                    "source_slice_refs": source_refs,
                }
            ),
        }


class PolicyGateReader(_ReadOnlyReader):
    """One exact policy selection plus zero or more declared non-content gates."""

    __slots__ = (
        "validation_policy",
        "active_selection",
        "gate_bindings",
        "gate_records",
    )

    def __init__(
        self,
        *,
        validation_policy: dict[str, Any],
        active_selection: dict[str, Any],
        gate_bindings: list[dict[str, Any]],
        gate_records: list[dict[str, Any]],
        reader_identity: str = "B05PolicyGateReader",
        reader_version: str = "b05-r03.5-fixture-1",
    ) -> None:
        super().__init__(reader_identity, reader_version)
        self.validation_policy = deepcopy(validation_policy)
        self.active_selection = deepcopy(active_selection)
        self.gate_bindings = deepcopy(gate_bindings)
        self.gate_records = deepcopy(gate_records)

    def read(
        self,
        *,
        patch_proposal_ref: dict[str, Any],
        atomic_group_bindings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._before_read()
        validate_record_ref(patch_proposal_ref, expected_type="M3_PATCH_PROPOSAL")
        if (
            not isinstance(atomic_group_bindings, list)
            or not atomic_group_bindings
            or atomic_group_bindings != stable_sorted(atomic_group_bindings)
        ):
            fail("B05_GATE_GROUP_CATALOG_INVALID")
        for group_binding in atomic_group_bindings:
            if set(group_binding) != {"atomic_group_id", "group_payload_hash"}:
                fail("B05_GATE_GROUP_CATALOG_INVALID")
        exact_group_binding_keys = {
            canonical_bytes(binding) for binding in atomic_group_bindings
        }
        validate_immutable_record(
            self.validation_policy, expected_type="M3_PATCH_VALIDATION_POLICY"
        )
        validate_immutable_record(
            self.active_selection, expected_type="M3_ACTIVE_POLICY_SELECTION"
        )
        policy_payload = self.validation_policy["payload"]
        allowed_policy_keys = {
            "policy_version",
            "canonical_add_sort_frozen",
            "semantic_unknown_group_ids",
            "unknown_dependency_tokens",
            "declared_dependency_edges",
            "adjacent_check_group_ids",
            "declared_non_content_gates",
        }
        if not set(policy_payload) <= allowed_policy_keys or not {
            "policy_version",
            "canonical_add_sort_frozen",
            "semantic_unknown_group_ids",
            "unknown_dependency_tokens",
            "declared_dependency_edges",
            "adjacent_check_group_ids",
        } <= set(policy_payload):
            fail("B05_VALIDATION_POLICY_SHAPE_INVALID")
        if set(self.active_selection["payload"]) != {
            "selected_validation_policy_ref"
        }:
            fail("B05_ACTIVE_POLICY_SELECTION_SHAPE_INVALID")
        policy_ref = record_ref(self.validation_policy)
        selected = self.active_selection["payload"].get(
            "selected_validation_policy_ref"
        )
        if canonical_bytes(selected) != canonical_bytes(policy_ref):
            fail("B05_ACTIVE_POLICY_SELECTION_INVALID")
        active_hash = sha256_value(
            {
                "reader_identity": self.reader_identity,
                "reader_version": self.reader_version,
                "active_policy_selection_ref": record_ref(self.active_selection),
                "selected_validation_policy_ref": policy_ref,
            }
        )
        bindings = stable_sorted(self.gate_bindings)
        declarations = policy_payload.get("declared_non_content_gates", [])
        if declarations != stable_sorted(declarations):
            fail("B05_GATE_DECLARATION_ORDER_INVALID")
        declared_by_ref: dict[bytes, dict[str, Any]] = {}
        for declaration in declarations:
            if set(declaration) != {"gate_ref", "gate_kind"}:
                fail("B05_GATE_DECLARATION_SHAPE_INVALID")
            validate_record_ref(declaration["gate_ref"], expected_type="M3_NON_CONTENT_GATE")
            if not isinstance(declaration["gate_kind"], str) or not declaration[
                "gate_kind"
            ]:
                fail("B05_GATE_DECLARATION_SHAPE_INVALID")
            key = canonical_bytes(declaration["gate_ref"])
            if key in declared_by_ref:
                fail("B05_GATE_DECLARATION_DUPLICATE")
            declared_by_ref[key] = declaration
        gate_records_by_ref: dict[bytes, dict[str, Any]] = {}
        state_records_by_gate: dict[bytes, list[dict[str, Any]]] = {}
        for record in self.gate_records:
            if record.get("record_type") not in {
                "M3_NON_CONTENT_GATE",
                "M3_NON_CONTENT_GATE_STATE",
            }:
                fail("B05_GATE_RECORD_TYPE_INVALID")
            validate_immutable_record(record, expected_type=record["record_type"])
            key = canonical_bytes(record_ref(record))
            if key in gate_records_by_ref:
                fail("B05_GATE_RECORD_AMBIGUOUS")
            gate_records_by_ref[key] = record
            if record["record_type"] == "M3_NON_CONTENT_GATE_STATE":
                payload = record["payload"]
                if set(payload) != {
                    "gate_ref",
                    "state_sequence",
                    "current_state",
                }:
                    fail("B05_GATE_STATE_SHAPE_INVALID")
                validate_record_ref(
                    payload["gate_ref"], expected_type="M3_NON_CONTENT_GATE"
                )
                if (
                    not isinstance(payload["state_sequence"], int)
                    or isinstance(payload["state_sequence"], bool)
                    or payload["state_sequence"] < 1
                    or payload["current_state"] not in {"OPEN", "CLOSED"}
                ):
                    fail("B05_GATE_STATE_MISMATCH")
                state_records_by_gate.setdefault(
                    canonical_bytes(payload["gate_ref"]), []
                ).append(record)
        current_state_ref_by_gate: dict[bytes, dict[str, Any]] = {}
        for gate_key, records in state_records_by_gate.items():
            if gate_key not in declared_by_ref:
                fail("B05_GATE_NOT_DECLARED")
            by_sequence: dict[int, dict[str, Any]] = {}
            for record in records:
                sequence = record["payload"]["state_sequence"]
                if sequence in by_sequence:
                    fail("B05_GATE_STATE_AMBIGUOUS")
                by_sequence[sequence] = record
            current_state_ref_by_gate[gate_key] = record_ref(
                by_sequence[max(by_sequence)]
            )
        for key, record in gate_records_by_ref.items():
            if record["record_type"] == "M3_NON_CONTENT_GATE" and key not in (
                declared_by_ref
            ):
                fail("B05_GATE_NOT_DECLARED")
        bound_gate_keys: set[bytes] = set()
        for binding in bindings:
            required = {
                "gate_ref",
                "gate_state_ref",
                "current_state",
                "applicable_patch_proposal_ref",
                "applicable_atomic_group_bindings_or_route_unit_ids",
                "reader_identity",
                "reader_version",
            }
            if set(binding) != required:
                fail("B05_GATE_BINDING_SHAPE_INVALID")
            validate_record_ref(
                binding["gate_ref"], expected_type="M3_NON_CONTENT_GATE"
            )
            validate_record_ref(
                binding["gate_state_ref"],
                expected_type="M3_NON_CONTENT_GATE_STATE",
            )
            gate_key = canonical_bytes(binding["gate_ref"])
            state_key = canonical_bytes(binding["gate_state_ref"])
            if gate_key in bound_gate_keys:
                fail("B05_GATE_BINDING_DUPLICATE")
            bound_gate_keys.add(gate_key)
            declaration = declared_by_ref.get(gate_key)
            gate_record = gate_records_by_ref.get(gate_key)
            state_record = gate_records_by_ref.get(state_key)
            if declaration is None:
                fail("B05_GATE_NOT_DECLARED")
            if gate_record is None or state_record is None:
                fail("B05_GATE_RECORD_UNRESOLVABLE")
            if set(gate_record["payload"]) != {"gate_kind", "gate_scope"}:
                fail("B05_GATE_RECORD_SHAPE_INVALID")
            if (
                gate_record["payload"]["gate_kind"] != declaration["gate_kind"]
                or gate_record["payload"]["gate_scope"] != "PATCH_ROUTE_UNIT"
            ):
                fail("B05_GATE_DECLARATION_MISMATCH")
            if set(state_record["payload"]) != {
                "gate_ref",
                "state_sequence",
                "current_state",
            }:
                fail("B05_GATE_STATE_SHAPE_INVALID")
            if (
                canonical_bytes(state_record["payload"]["gate_ref"])
                != canonical_bytes(binding["gate_ref"])
                or not isinstance(state_record["payload"]["state_sequence"], int)
                or isinstance(state_record["payload"]["state_sequence"], bool)
                or state_record["payload"]["state_sequence"] < 1
                or state_record["payload"]["current_state"] not in {"OPEN", "CLOSED"}
                or state_record["payload"]["current_state"]
                != binding["current_state"]
            ):
                fail("B05_GATE_STATE_MISMATCH")
            if canonical_bytes(current_state_ref_by_gate.get(gate_key)) != state_key:
                fail("B05_GATE_STATE_NOT_CURRENT")
            if (
                binding["reader_identity"] != self.reader_identity
                or binding["reader_version"] != self.reader_version
            ):
                fail("B05_GATE_READER_IDENTITY_MISMATCH")
            if canonical_bytes(
                binding["applicable_patch_proposal_ref"]
            ) != canonical_bytes(patch_proposal_ref):
                fail("B05_GATE_PATCH_SCOPE_INVALID")
            targets = binding["applicable_atomic_group_bindings_or_route_unit_ids"]
            if not isinstance(targets, list) or not targets:
                fail("B05_GATE_APPLICABILITY_INVALID")
            for target in targets:
                if isinstance(target, str):
                    if not target.startswith("route-unit:"):
                        fail("B05_GATE_APPLICABILITY_INVALID")
                elif not isinstance(target, dict) or set(target) != {
                    "atomic_group_id",
                    "group_payload_hash",
                }:
                    fail("B05_GATE_APPLICABILITY_INVALID")
                elif canonical_bytes(target) not in exact_group_binding_keys:
                    fail("B05_GATE_APPLICABILITY_INVALID")
        if (
            len(bindings) != len(declarations)
            or bound_gate_keys != set(declared_by_ref)
        ):
            fail("B05_GATE_DECLARATION_CLOSURE_INVALID")
        return {
            "reader_identity": self.reader_identity,
            "reader_version": self.reader_version,
            "validation_policy_record": deepcopy(self.validation_policy),
            "validation_policy_ref": policy_ref,
            "active_policy_selection_record": deepcopy(self.active_selection),
            "active_policy_selection_ref": record_ref(self.active_selection),
            "active_policy_selection_hash": active_hash,
            "non_content_gate_bindings": bindings,
            "non_content_gate_snapshot_hash": sha256_value(bindings),
        }


class UnavailableReader:
    """Explicit fixture for an authoritative reader outage."""

    def __getattr__(self, _: str) -> Any:
        fail("B05_AUTHORITATIVE_READER_UNAVAILABLE")
