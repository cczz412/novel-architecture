"""Append-only fixture store and the four B-02 unique writers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from b02_contracts import (
    ALLOWED_ACCESS,
    B02ContractError,
    FIXTURE_ACCESS,
    TERMINAL_EVENTS,
    build_record,
    canonical_bytes,
    fail,
    parse_utc,
    record_ref,
    sha256_value,
    validate_coverage_record,
    validate_b02_output_record,
    validate_diagnostic_record,
    validate_identity_record,
    validate_lifecycle_record,
    validate_record,
    validate_record_ref,
    validate_upstream_context,
    _WRITER_TOKENS,
)

_TYPE_DIRECTORIES = {
    "M3_DIAGNOSTIC_RECORDER_IDENTITY": "M3_DIAGNOSTIC_RECORDER_IDENTITY",
    "M3_DIAGNOSTIC": "M3_DIAGNOSTIC",
    "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT": "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
    "M3_COVERAGE_OBSERVATION": "M3_COVERAGE_OBSERVATION",
}


def _record_identity(record: dict[str, Any]) -> str:
    return (
        f"{record['record_type']}:{record['record_id']}:"
        f"{record['record_version']}"
    )


class FixtureStore:
    """Atomic, one-file-per-record fixture store within B-02 or test temp."""

    __slots__ = ("root", "records_root", "events", "failure_point")

    def __init__(self, root: Path, *, failure_point: str | None = None) -> None:
        resolved = root.resolve(strict=False)
        module_root = Path(__file__).resolve().parent
        repository_root = module_root.parents[1]
        temporary_root = Path(tempfile.gettempdir()).resolve()
        inside_repository = (
            resolved == repository_root or repository_root in resolved.parents
        )
        inside_write_set = resolved == module_root or module_root in resolved.parents
        inside_test_temp = (
            resolved == temporary_root or temporary_root in resolved.parents
        )
        if (inside_repository and not inside_write_set) or (
            not inside_repository and not inside_test_temp
        ):
            fail("B02_WRITE_SET_ESCAPE", str(root))
        self.root = root
        self.records_root = root / "records"
        self.events: list[str] = []
        self.failure_point = failure_point

    def _assert_no_pending(self) -> None:
        if self.records_root.exists() and any(self.records_root.rglob("*.pending")):
            fail("B02_TRANSACTION_PENDING_FOUND")

    def _inject_failure(self, point: str) -> None:
        if self.failure_point == point:
            fail("B02_SIMULATED_TRANSACTION_FAILURE", point)

    def path_for(self, record: dict[str, Any]) -> Path:
        validate_b02_output_record(record)
        identity_hash = hashlib.sha256(
            _record_identity(record).encode("utf-8")
        ).hexdigest()
        directory = _TYPE_DIRECTORIES[record["record_type"]]
        path = self.records_root / directory / f"{identity_hash}.json"
        resolved = path.resolve(strict=False)
        records_root = self.records_root.resolve(strict=False)
        if records_root not in resolved.parents:
            fail("B02_WRITE_SET_ESCAPE", str(path))
        return path

    def read_records(self) -> list[dict[str, Any]]:
        self.events.append("fixture_storage_read")
        self._assert_no_pending()
        if not self.records_root.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(self.records_root.rglob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            validate_b02_output_record(record)
            records.append(record)
        return records

    def existing(self, record: dict[str, Any]) -> dict[str, Any] | None:
        self._assert_no_pending()
        path = self.path_for(record)
        if not path.exists():
            return None
        existing = json.loads(path.read_text(encoding="utf-8"))
        validate_b02_output_record(existing)
        return existing

    @staticmethod
    def _remove_created_empty_directories(created: list[Path]) -> None:
        for directory in reversed(created):
            try:
                directory.rmdir()
            except (FileNotFoundError, OSError):
                pass

class DiagnosticRecorderIdentityRegistry:
    """Unique writer for M3_DIAGNOSTIC_RECORDER_IDENTITY."""

    WRITER_NAME = "DiagnosticRecorderIdentityRegistry"

    @staticmethod
    def build(
        *, writer_version: str, created_at: str, access: str = FIXTURE_ACCESS
    ) -> dict[str, Any]:
        if not isinstance(writer_version, str) or not writer_version:
            fail("B02_WRITER_IDENTITY_INVALID", "writer version")
        record_id = f"diagnostic-recorder:{sha256_value(writer_version)[:24]}"
        record = build_record(
            record_type="M3_DIAGNOSTIC_RECORDER_IDENTITY",
            record_id=record_id,
            payload={"writer": "DiagnosticRecorder", "writer_version": writer_version},
            created_at=created_at,
            access=access,
            writer_token=_WRITER_TOKENS["M3_DIAGNOSTIC_RECORDER_IDENTITY"],
        )
        validate_identity_record(record)
        return record

    @staticmethod
    def register(
        record: dict[str, Any],
        *,
        commit_record: Callable[[dict[str, Any]], dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if not callable(commit_record):
            fail("B02_ADMISSION_CAPABILITY_REQUIRED")
        validate_identity_record(record)
        return commit_record(record)


class DiagnosticRecorder:
    """Unique writer for immutable Diagnostic originals."""

    WRITER_NAME = "DiagnosticRecorder"

    @staticmethod
    def build(
        *,
        context: dict[str, Any],
        axis: str,
        severity: str,
        lineage_locator: dict[str, Any],
        evidence_refs: list[dict[str, Any]],
        fingerprint: str,
        writer_identity_ref: dict[str, Any],
        created_at: str,
        access: str = FIXTURE_ACCESS,
    ) -> dict[str, Any]:
        candidate = context["candidate_version"]
        stable_evidence = sorted(
            deepcopy(evidence_refs),
            key=lambda ref: (
                ref.get("record_type", ""),
                ref.get("record_id", ""),
                ref.get("record_version", 0),
                ref.get("record_hash", ""),
            ),
        )
        payload = {
            "base_candidate_version_ref": record_ref(candidate),
            "chapter_revision_ref": deepcopy(
                candidate["payload"]["chapter_revision_ref"]
            ),
            "seg": candidate["payload"]["seg"],
            "axis": axis,
            "severity": severity,
            "target": {
                "kind": "LINEAGE",
                "lineage_locator": deepcopy(lineage_locator),
            },
            "evidence_refs": stable_evidence,
            "fingerprint": fingerprint,
            "writer_identity_ref": deepcopy(writer_identity_ref),
        }
        record_id = (
            f"diagnostic:{candidate['record_hash'][:16]}:{fingerprint[:32]}"
        )
        return build_record(
            record_type="M3_DIAGNOSTIC",
            record_id=record_id,
            payload=payload,
            created_at=created_at,
            access=access,
            writer_token=_WRITER_TOKENS["M3_DIAGNOSTIC"],
        )

    @staticmethod
    def record(
        store: FixtureStore,
        record: dict[str, Any],
        *,
        context: dict[str, Any],
        commit_record: Callable[[dict[str, Any]], dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if not callable(commit_record):
            fail("B02_ADMISSION_CAPABILITY_REQUIRED")
        records = store.read_records()
        validate_diagnostic_record(record, context=context, records=records)
        return commit_record(record)


def _validate_lifecycle_streams(records: list[dict[str, Any]]) -> None:
    diagnostics = {
        canonical_bytes(record_ref(record)): record
        for record in records
        if record["record_type"] == "M3_DIAGNOSTIC"
    }
    grouped: dict[bytes, list[dict[str, Any]]] = {}
    for record in records:
        if record["record_type"] != "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT":
            continue
        validate_lifecycle_record(record, records=records)
        key = canonical_bytes(record["payload"]["diagnostic_ref"])
        grouped.setdefault(key, []).append(record)
    for key, stream in grouped.items():
        diagnostic = diagnostics.get(key)
        if diagnostic is None:
            fail("B02_REFERENCE_INTEGRITY_FAILED", "lifecycle Diagnostic")
        ordered = sorted(
            stream,
            key=lambda item: (
                item["payload"]["lifecycle_sequence"],
                item["record_id"],
                item["record_hash"],
            ),
        )
        prior_sequence = 0
        prior_time = parse_utc(
            diagnostic["created_at"], "B02_REFERENCE_INTEGRITY_FAILED"
        )
        prior_event = None
        terminal_seen = False
        for item in ordered:
            payload = item["payload"]
            sequence = payload["lifecycle_sequence"]
            effective = parse_utc(
                payload["effective_at"], "B02_REFERENCE_INTEGRITY_FAILED"
            )
            if sequence <= prior_sequence or effective < prior_time:
                fail("B02_REFERENCE_INTEGRITY_FAILED", "lifecycle order")
            if effective == prior_time and prior_event not in {None, payload["event"]}:
                fail("B02_REFERENCE_INTEGRITY_FAILED", "lifecycle time conflict")
            if terminal_seen:
                fail("B02_REFERENCE_INTEGRITY_FAILED", "event after terminal")
            terminal_seen = payload["event"] in TERMINAL_EVENTS
            prior_sequence = sequence
            prior_time = effective
            prior_event = payload["event"]


class DiagnosticLifecycleWriter:
    """Unique append-only writer for Diagnostic lifecycle receipts."""

    WRITER_NAME = "DiagnosticLifecycleWriter"

    @staticmethod
    def build(
        *,
        diagnostic_ref: dict[str, Any],
        lifecycle_sequence: int,
        event: str,
        effective_at: str,
        reason_code: str,
        created_at: str,
        access: str = FIXTURE_ACCESS,
    ) -> dict[str, Any]:
        record_id = (
            f"diagnostic-lifecycle:{diagnostic_ref['record_hash'][:16]}:"
            f"{lifecycle_sequence}"
        )
        return build_record(
            record_type="M3_DIAGNOSTIC_LIFECYCLE_RECEIPT",
            record_id=record_id,
            payload={
                "diagnostic_ref": deepcopy(diagnostic_ref),
                "lifecycle_sequence": lifecycle_sequence,
                "event": event,
                "effective_at": effective_at,
                "reason_code": reason_code,
                "resolution_ref": None,
            },
            created_at=created_at,
            access=access,
            writer_token=_WRITER_TOKENS["M3_DIAGNOSTIC_LIFECYCLE_RECEIPT"],
        )

    @staticmethod
    def append(
        store: FixtureStore,
        record: dict[str, Any],
        *,
        commit_record: Callable[[dict[str, Any]], dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if not callable(commit_record):
            fail("B02_ADMISSION_CAPABILITY_REQUIRED")
        records = store.read_records()
        _validate_lifecycle_streams(records)
        validate_lifecycle_record(record, records=records)
        existing = store.existing(record)
        if existing is not None:
            if canonical_bytes(existing) != canonical_bytes(record):
                fail("B02_LIFECYCLE_SEQUENCE_CONFLICT")
            return record_ref(existing)
        diagnostic_ref = record["payload"]["diagnostic_ref"]
        diagnostic = next(
            item for item in records if record_ref(item) == diagnostic_ref
        )
        accepted = [
            item
            for item in records
            if item["record_type"] == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT"
            and item["payload"]["diagnostic_ref"] == diagnostic_ref
        ]
        for prior in accepted:
            validate_lifecycle_record(prior, records=records)
        new_payload = record["payload"]
        if accepted:
            max_sequence = max(
                item["payload"]["lifecycle_sequence"] for item in accepted
            )
            if any(
                item["payload"]["lifecycle_sequence"]
                == new_payload["lifecycle_sequence"]
                for item in accepted
            ):
                fail("B02_LIFECYCLE_SEQUENCE_CONFLICT")
            if new_payload["lifecycle_sequence"] < max_sequence:
                fail("B02_LIFECYCLE_ORDER_CONFLICT", "sequence")
            latest_time = max(
                parse_utc(item["payload"]["effective_at"], "B02_LIFECYCLE_INVALID")
                for item in accepted
            )
            new_time = parse_utc(
                new_payload["effective_at"], "B02_LIFECYCLE_INVALID"
            )
            if new_time < latest_time:
                fail("B02_LIFECYCLE_ORDER_CONFLICT", "effective_at")
            if any(
                item["payload"]["effective_at"] == new_payload["effective_at"]
                and item["payload"]["event"] != new_payload["event"]
                for item in accepted
            ):
                fail("B02_LIFECYCLE_TIME_CONFLICT")
            if any(
                item["payload"]["event"] in TERMINAL_EVENTS for item in accepted
            ):
                fail("B02_LIFECYCLE_TERMINAL")
        elif parse_utc(
            new_payload["effective_at"], "B02_LIFECYCLE_INVALID"
        ) < parse_utc(diagnostic["created_at"], "B02_LIFECYCLE_INVALID"):
            fail("B02_LIFECYCLE_ORDER_CONFLICT", "before Diagnostic")
        return commit_record(record)


class CoverageRecorder:
    """Unique writer for immutable Coverage observations."""

    WRITER_NAME = "CoverageRecorder"

    @staticmethod
    def build(
        *,
        context: dict[str, Any],
        source_observation_id: str,
        source_span_hash: str,
        axis: str,
        candidate_match: str,
        observer_ref: dict[str, Any],
        created_at: str,
        access: str = FIXTURE_ACCESS,
    ) -> dict[str, Any]:
        candidate = context["candidate_version"]
        identity = {
            "candidate_ref": record_ref(candidate),
            "source_observation_id": source_observation_id,
            "axis": axis,
        }
        record_id = f"coverage:{sha256_value(identity)[:40]}"
        return build_record(
            record_type="M3_COVERAGE_OBSERVATION",
            record_id=record_id,
            payload={
                "base_candidate_version_ref": record_ref(candidate),
                "chapter_revision_ref": deepcopy(
                    candidate["payload"]["chapter_revision_ref"]
                ),
                "seg": candidate["payload"]["seg"],
                "source_observation_id": source_observation_id,
                "source_span_hash": source_span_hash,
                "axis": axis,
                "candidate_match": candidate_match,
                "observer_ref": deepcopy(observer_ref),
            },
            created_at=created_at,
            access=access,
            writer_token=_WRITER_TOKENS["M3_COVERAGE_OBSERVATION"],
        )

    @staticmethod
    def record(
        store: FixtureStore,
        record: dict[str, Any],
        *,
        context: dict[str, Any],
        commit_record: Callable[[dict[str, Any]], dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if not callable(commit_record):
            fail("B02_ADMISSION_CAPABILITY_REQUIRED")
        records = store.read_records()
        validate_coverage_record(record, context=context, records=records)
        return commit_record(record)


def _validate_record_collection(
    records: list[dict[str, Any]], *, context: dict[str, Any]
) -> None:
    for record in records:
        validate_record(record)
        if record["record_type"] == "M3_DIAGNOSTIC_RECORDER_IDENTITY":
            validate_identity_record(record)
        elif record["record_type"] == "M3_DIAGNOSTIC":
            validate_diagnostic_record(record, context=context, records=records)
        elif record["record_type"] == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT":
            validate_lifecycle_record(record, records=records)
        elif record["record_type"] == "M3_COVERAGE_OBSERVATION":
            validate_coverage_record(record, context=context, records=records)
        else:
            fail("B02_REFERENCE_INTEGRITY_FAILED", "unexpected persisted type")
    _validate_lifecycle_streams(records)
    identities = [
        record
        for record in records
        if record["record_type"] == "M3_DIAGNOSTIC_RECORDER_IDENTITY"
    ]
    for record in records:
        if record["record_type"] == "M3_DIAGNOSTIC":
            validate_record_ref(
                record["payload"]["writer_identity_ref"],
                records=identities,
                allowed_access=ALLOWED_ACCESS,
            )
        if record["record_type"] == "M3_COVERAGE_OBSERVATION":
            validate_record_ref(
                record["payload"]["observer_ref"],
                records=identities,
                allowed_access=ALLOWED_ACCESS,
            )


def validate_store(store: FixtureStore, *, context: dict[str, Any]) -> None:
    _validate_record_collection(store.read_records(), context=context)


class B02Service:
    """Gate B-02 before exposing its four fixture writers."""

    __slots__ = ("store", "__load_context", "__commit_record")

    @staticmethod
    def __admit_runtime(
        store: FixtureStore,
        *,
        admission_bytes: bytes | None,
        merge_receipt_bytes: bytes | None,
        reference_records: list[dict[str, Any]],
        lineage_locators: list[dict[str, Any]],
    ) -> tuple[
        Callable[[], dict[str, Any]],
        Callable[[dict[str, Any]], dict[str, Any]],
    ]:
        context = validate_upstream_context(
            admission_bytes=admission_bytes,
            merge_receipt_bytes=merge_receipt_bytes,
            reference_records=reference_records,
            lineage_locators=lineage_locators,
        )
        sealed_context_bytes = canonical_bytes(context)
        sealed_context_hash = hashlib.sha256(sealed_context_bytes).hexdigest()

        def load_context() -> dict[str, Any]:
            reopened = json.loads(sealed_context_bytes)
            if hashlib.sha256(canonical_bytes(reopened)).hexdigest() != (
                sealed_context_hash
            ):
                fail("B02_ADMITTED_CONTEXT_DRIFT")
            return reopened

        def commit_record(record: dict[str, Any]) -> dict[str, Any]:
            validate_b02_output_record(record)
            existing = store.existing(record)
            if existing is not None:
                if canonical_bytes(existing) != canonical_bytes(record):
                    fail("B02_IMMUTABLE_ALREADY_EXISTS", _record_identity(record))
                _validate_record_collection(
                    store.read_records(), context=load_context()
                )
                return record_ref(existing)

            current_records = store.read_records()
            _validate_record_collection(
                [*current_records, record], context=load_context()
            )

            path = store.path_for(record)
            temporary = path.with_suffix(".json.pending")
            record_bytes = canonical_bytes(record)
            directory_candidates = [store.root, store.records_root, path.parent]
            created_directories = [
                directory
                for directory in directory_candidates
                if not directory.exists()
            ]
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                store._inject_failure("after_mkdir")
                temporary.write_bytes(record_bytes)
                store._inject_failure("after_pending_write")

                reopened = json.loads(temporary.read_text(encoding="utf-8"))
                _validate_record_collection(
                    [*current_records, reopened], context=load_context()
                )
                if canonical_bytes(reopened) != record_bytes:
                    fail(
                        "B02_TRANSACTION_READBACK_INVALID",
                        _record_identity(record),
                    )
                store.events.append("private_candidate_readback_validated")
                store._inject_failure("after_candidate_readback")

                os.replace(temporary, path)
            except B02ContractError:
                temporary.unlink(missing_ok=True)
                store._remove_created_empty_directories(created_directories)
                raise
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                temporary.unlink(missing_ok=True)
                store._remove_created_empty_directories(created_directories)
                fail("B02_TRANSACTION_WRITE_FAILED", str(error))

            store.events.append("immutable_record_atomic_write")
            return record_ref(reopened)

        return load_context, commit_record

    def __init__(
        self,
        store: FixtureStore,
        *,
        admission_bytes: bytes | None,
        merge_receipt_bytes: bytes | None,
        reference_records: list[dict[str, Any]],
        lineage_locators: list[dict[str, Any]],
    ) -> None:
        self.store = store
        self.__load_context, self.__commit_record = self.__admit_runtime(
            store,
            admission_bytes=admission_bytes,
            merge_receipt_bytes=merge_receipt_bytes,
            reference_records=reference_records,
            lineage_locators=lineage_locators,
        )

    @property
    def context(self) -> dict[str, Any]:
        """Return a detached copy; writers always use the sealed private bytes."""

        return self.__load_context()

    def register_identity(
        self, *, writer_version: str, created_at: str
    ) -> dict[str, Any]:
        record = DiagnosticRecorderIdentityRegistry.build(
            writer_version=writer_version, created_at=created_at
        )
        return DiagnosticRecorderIdentityRegistry.register(
            record,
            commit_record=self.__commit_record,
        )

    def add_diagnostic(self, **kwargs: Any) -> dict[str, Any]:
        context = self.__load_context()
        record = DiagnosticRecorder.build(context=context, **kwargs)
        return DiagnosticRecorder.record(
            self.store,
            record,
            context=context,
            commit_record=self.__commit_record,
        )

    def append_lifecycle(self, **kwargs: Any) -> dict[str, Any]:
        record = DiagnosticLifecycleWriter.build(**kwargs)
        return DiagnosticLifecycleWriter.append(
            self.store,
            record,
            commit_record=self.__commit_record,
        )

    def add_coverage(self, **kwargs: Any) -> dict[str, Any]:
        context = self.__load_context()
        record = CoverageRecorder.build(context=context, **kwargs)
        return CoverageRecorder.record(
            self.store,
            record,
            context=context,
            commit_record=self.__commit_record,
        )


def directory_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[f"dir:{relative}"] = ""
        elif path.is_file():
            snapshot[f"file:{relative}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def record_file_bytes(store: FixtureStore, ref: dict[str, Any]) -> bytes:
    records = store.read_records()
    matches = [record for record in records if record_ref(record) == ref]
    if len(matches) != 1:
        fail("B02_REFERENCE_INTEGRITY_FAILED", "record file")
    return store.path_for(matches[0]).read_bytes()
