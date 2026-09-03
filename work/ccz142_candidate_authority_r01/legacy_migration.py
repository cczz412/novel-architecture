"""Read and validate legacy B-01/B-06 fixtures before authority-store import."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from b01_contract import record_ref, validate_candidate_version, verify_state
from b05_contracts import canonical_bytes, sha256_value
from b06_contracts import validate_merge_receipt, validate_mutable_pointer

from candidate_authority import (
    _LEGACY_MIGRATION_TOKEN,
    CandidateAuthorityStore,
    fail,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _decode(raw: Any, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(bytes(raw).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        fail(code, str(error))
    if not isinstance(value, dict):
        fail(code)
    return value


class LegacyCandidateMigration:
    """The migration service never writes the destination database directly."""

    def __init__(self, store: CandidateAuthorityStore) -> None:
        self.store = store

    @staticmethod
    @contextmanager
    def _b06_source_serialization(
        source_database_path: Path,
    ) -> Iterator[None]:
        lock_path = source_database_path.parent / ".b06-commit.lock"
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(lock_path, flags)
        except OSError as error:
            fail("B06_MIGRATION_SOURCE_LOCK_UNAVAILABLE", str(error))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                fail("B06_MIGRATION_SOURCE_LOCK_INVALID")
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def migrate_b01_json(
        self,
        *,
        source_state_path: Path,
        authority_snapshot: dict[str, Any],
        reference_records: list[dict[str, Any]],
        migration_id: str,
    ) -> dict[str, Any]:
        source_bytes = source_state_path.read_bytes()
        before_hash = hashlib.sha256(source_bytes).hexdigest()
        prior = self.store.read_migration(
            migration_id=migration_id,
            source_kind="B01_STATE_JSON",
            source_sha256=before_hash,
        )
        if prior is not None:
            return prior
        state = json.loads(source_bytes.decode("utf-8"))
        try:
            verify_state(state, reference_records=reference_records)
        except ValueError as error:
            fail("B01_MIGRATION_SOURCE_INVALID", str(error))

        def source_stability_check() -> None:
            if file_sha256(source_state_path) != before_hash:
                fail("MIGRATION_SOURCE_MUTATED_BEFORE_COMMIT")

        return self.store.import_legacy_b01_snapshot(
            migration_id=migration_id,
            source_sha256=before_hash,
            staged_state=state,
            authority_snapshot=authority_snapshot,
            source_stability_check=source_stability_check,
            migration_token=_LEGACY_MIGRATION_TOKEN,
        )

    def migrate_b06_sqlite(
        self,
        *,
        source_database_path: Path,
        reference_records: list[dict[str, Any]],
        migration_id: str,
    ) -> dict[str, Any]:
        resolved_source = source_database_path.resolve()
        if resolved_source == self.store.database_path.resolve():
            fail("MIGRATION_SOURCE_EQUALS_DESTINATION")
        with self._b06_source_serialization(resolved_source):
            return self._migrate_b06_sqlite_locked(
                source_database_path=resolved_source,
                reference_records=reference_records,
                migration_id=migration_id,
            )

    def _migrate_b06_sqlite_locked(
        self,
        *,
        source_database_path: Path,
        reference_records: list[dict[str, Any]],
        migration_id: str,
    ) -> dict[str, Any]:
        before_hash = file_sha256(source_database_path)
        source_uri = f"{source_database_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as source:
            source.execute("PRAGMA query_only=ON")
            source.execute("BEGIN")
            journal_mode = source.execute("PRAGMA journal_mode").fetchone()[0]
            if journal_mode.lower() not in {"delete", "truncate"}:
                fail("B06_MIGRATION_SOURCE_JOURNAL_MODE_UNSUPPORTED", journal_mode)
            tables = {
                row[0]
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            required = {"candidate_versions", "current_pointers", "merge_receipts"}
            if not required <= tables:
                fail("B06_MIGRATION_SOURCE_SCHEMA_INVALID")
            raw_candidate_rows = source.execute(
                "SELECT ref_hash, record_json FROM candidate_versions ORDER BY ref_hash"
            ).fetchall()
            raw_pointer_rows = source.execute(
                "SELECT logical_pointer_key, project_scope_id, pointer_json "
                "FROM current_pointers ORDER BY logical_pointer_key"
            ).fetchall()
            raw_receipt_rows = source.execute(
                "SELECT project_scope_id, operation_id, request_hash, receipt_json "
                "FROM merge_receipts ORDER BY project_scope_id, operation_id"
            ).fetchall()
            if file_sha256(source_database_path) != before_hash:
                fail("MIGRATION_SOURCE_MUTATED_BEFORE_IMPORT")
        candidate_rows = [
            (row[0], bytes(row[1])) for row in raw_candidate_rows
        ]
        candidates = {
            ref_hash: _decode(raw, code="MIGRATION_CANDIDATE_INVALID")
            for ref_hash, raw in candidate_rows
        }
        for ref_hash, candidate in candidates.items():
            if sha256_value(record_ref(candidate)) != ref_hash:
                fail("MIGRATION_CANDIDATE_REF_HASH_MISMATCH")
            try:
                validate_candidate_version(
                    candidate,
                    allow_child=candidate["payload"]["parent_candidate_version_ref"]
                    is not None,
                    reference_records=reference_records,
                )
            except (KeyError, ValueError) as error:
                fail("MIGRATION_CANDIDATE_INVALID", str(error))
        receipt_rows = [
            (row[0], row[1], row[2], bytes(row[3])) for row in raw_receipt_rows
        ]
        receipts = [
            _decode(row[3], code="MIGRATION_RECEIPT_INVALID")
            for row in receipt_rows
        ]
        for row, receipt in zip(receipt_rows, receipts, strict=True):
            try:
                validate_merge_receipt(receipt)
            except ValueError as error:
                fail("MIGRATION_RECEIPT_INVALID", str(error))
            payload = receipt["payload"]
            if (
                row[0] != self.store.project_scope_id
                or row[1] != payload["operation_id"]
                or row[2] != payload["request_hash"]
            ):
                fail("MIGRATION_RECEIPT_ROW_MISMATCH")
        pointer_rows = [
            (row[0], row[1], bytes(row[2])) for row in raw_pointer_rows
        ]
        for _pointer_key, project_scope_id, raw in pointer_rows:
            if project_scope_id != self.store.project_scope_id:
                fail("MIGRATION_PROJECT_SCOPE_MISMATCH")
            pointer = _decode(raw, code="MIGRATION_POINTER_INVALID")
            if (
                pointer.get("logical_pointer_key") != _pointer_key
                or pointer.get("project_scope_id") != project_scope_id
            ):
                fail("MIGRATION_POINTER_ROW_MISMATCH")
            candidate = candidates.get(
                sha256_value(pointer["current_candidate_version_ref"])
            )
            if candidate is None:
                fail("MIGRATION_POINTER_CANDIDATE_MISSING")
            try:
                validate_mutable_pointer(
                    pointer,
                    candidate=candidate,
                    reference_records=reference_records,
                )
            except (KeyError, ValueError) as error:
                fail("MIGRATION_POINTER_INVALID", str(error))
        result = self.store.import_legacy_b06_snapshot(
            migration_id=migration_id,
            source_sha256=before_hash,
            candidate_rows=candidate_rows,
            pointer_rows=pointer_rows,
            receipt_rows=receipt_rows,
            receipts=receipts,
            source_stability_check=lambda: self._verify_source_hash(
                source_database_path, before_hash
            ),
            migration_token=_LEGACY_MIGRATION_TOKEN,
        )
        return result

    @staticmethod
    def _verify_source_hash(source_path: Path, expected_sha256: str) -> None:
        if file_sha256(source_path) != expected_sha256:
            fail("MIGRATION_SOURCE_MUTATED_BEFORE_COMMIT")


def same_record_ref(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return canonical_bytes(record_ref(left)) == canonical_bytes(record_ref(right))
