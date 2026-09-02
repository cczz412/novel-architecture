"""Read and validate legacy B-01/B-06 fixtures before authority-store import."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from b01_contract import (  # noqa: E402
    PRODUCT_AUTHORITY_PROFILE,
    PRODUCT_READ_ONLY_ACCESS,
    record_ref,
    validate_candidate_version,
    verify_state,
)
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

    def _reject_unconverted_product_source(
        self,
        candidates: list[dict[str, Any]],
    ) -> None:
        if self.store.authority_profile.identity != PRODUCT_AUTHORITY_PROFILE.identity:
            return
        if any(
            candidate["payload"]["extraction_input_binding"][
                "accepted_source_generation_ref"
            ]["access"]
            != PRODUCT_READ_ONLY_ACCESS
            for candidate in candidates
        ):
            fail("MIGRATION_SYNTHETIC_FIXTURE_INELIGIBLE")
        fail("MIGRATION_PRODUCT_REBUILD_REQUIRED")

    def migrate_b01_json(
        self,
        *,
        source_state_path: Path,
        authority_snapshot: dict[str, Any],
        reference_records: list[dict[str, Any]],
        migration_id: str,
    ) -> dict[str, Any]:
        before_hash = file_sha256(source_state_path)
        prior = self.store.read_migration(
            migration_id=migration_id,
            source_kind="B01_STATE_JSON",
            source_sha256=before_hash,
        )
        if prior is not None:
            return prior
        state = json.loads(source_state_path.read_text(encoding="utf-8"))
        try:
            verify_state(state, reference_records=reference_records)
        except ValueError as error:
            fail("B01_MIGRATION_SOURCE_INVALID", str(error))
        self._reject_unconverted_product_source(
            [
                record
                for record in state["records"].values()
                if record["record_type"] == "M3_CANDIDATE_VERSION"
            ]
        )
        published = self.store._publish_root(
            staged_state=state,
            authority_snapshot=authority_snapshot,
            publisher_token=_LEGACY_MIGRATION_TOKEN,
        )
        after_hash = file_sha256(source_state_path)
        if after_hash != before_hash:
            fail("MIGRATION_SOURCE_MUTATED")
        result = {
            "source_sha256": before_hash,
            "root_candidate_ref": published["candidate_version_ref"],
            "pointer_logical_key": published["logical_pointer_key"],
            "source_unchanged": True,
        }
        return self.store.record_migration(
            migration_id=migration_id,
            source_kind="B01_STATE_JSON",
            source_sha256=before_hash,
            result=result,
        )

    def migrate_b06_sqlite(
        self,
        *,
        source_database_path: Path,
        reference_records: list[dict[str, Any]],
        migration_id: str,
    ) -> dict[str, Any]:
        if source_database_path.resolve() == self.store.database_path.resolve():
            fail("MIGRATION_SOURCE_EQUALS_DESTINATION")
        before_hash = file_sha256(source_database_path)
        with sqlite3.connect(source_database_path) as source:
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
        candidate_rows = [
            (row[0], bytes(row[1])) for row in raw_candidate_rows
        ]
        candidates = {
            ref_hash: _decode(raw, code="MIGRATION_CANDIDATE_INVALID")
            for ref_hash, raw in candidate_rows
        }
        self._reject_unconverted_product_source(list(candidates.values()))
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
        )
        if file_sha256(source_database_path) != before_hash:
            fail("MIGRATION_SOURCE_MUTATED")
        return result


def same_record_ref(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return canonical_bytes(record_ref(left)) == canonical_bytes(record_ref(right))
