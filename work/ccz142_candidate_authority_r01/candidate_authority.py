"""One candidate-authority store for B-01 roots and B-06 child commits."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
for candidate in (REPOSITORY_ROOT, B01_ROOT, B05_ROOT, B06_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b01_contract import (  # noqa: E402
    CCZ142_EXTRACTION_HANDOFF_CONTRACT,
    CCZ142_EXTRACTION_SOURCE_LANE,
    CCZ142_EXTRACTION_SOURCE_MODULE,
    FIXTURE_POINTER_NAMESPACE,
    _compose_ccz142_b01_runtime,
    canonical_bytes,
    record_ref,
    sha256_value,
)
from b06_store import B06CommitStore  # noqa: E402

ROOT_REQUEST_KEYS = {
    "admission",
    "reference_records",
    "project_scope_id",
    "author_workspace_logical_key",
    "chapter_revision_ref",
    "accepted_source_generation_ref",
    "writing_material_refs",
    "source_module_identity",
    "segment_inputs",
    "seg",
    "origin_attempt_refs",
    "raw_items",
    "operation_id",
    "created_at",
    "input_generation_id",
}
ROOT_AUTHORITY_KEYS = {
    "project_scope_id",
    "chapter_revision_ref",
    "input_generation_id",
    "input_generation_hash",
    "segment_scope_hash",
}
ROOT_RECORD_TYPES = {
    "M3_SEGMENT_INDEX_SNAPSHOT",
    "M3_CANDIDATE_VERSION",
    "M3_CANDIDATE_POINTER_SNAPSHOT",
}
_ROOT_PUBLISH_TOKEN = object()
_LEGACY_MIGRATION_TOKEN = object()


class CandidateAuthorityError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise CandidateAuthorityError(code, detail)


def _decode(raw: Any, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(bytes(raw).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        fail(code, str(error))
    if not isinstance(value, dict):
        fail(code)
    return value


def _storage_key(record: dict[str, Any]) -> str:
    return f"{record['record_type']}:{record['record_id']}:{record['record_version']}"


class _B01RootCaptureStore:
    """Capture one already-validated B-01 transaction without persistent writes."""

    def __init__(self) -> None:
        self._state: dict[str, Any] | None = None

    def read(self) -> dict[str, Any]:
        if self._state is None:
            return {"records": {}, "pointers": {}, "operations": {}}
        return deepcopy(self._state)

    def commit(self, state: dict[str, Any]) -> None:
        if self._state is not None:
            fail("B01_CAPTURE_ALREADY_COMMITTED")
        self._state = deepcopy(state)

    def take(self) -> dict[str, Any]:
        if self._state is None:
            fail("B01_CAPTURE_MISSING")
        return deepcopy(self._state)


class CandidateAuthorityStore(B06CommitStore):
    """The sole physical writer for one project's candidate authority."""

    def __init__(
        self,
        root: Path,
        *,
        project_scope_id: str,
        root_failure_point: str | None = None,
    ) -> None:
        if not isinstance(project_scope_id, str) or not project_scope_id:
            fail("PROJECT_SCOPE_INVALID")
        super().__init__(root)
        self.project_scope_id = project_scope_id
        self.root_failure_point = root_failure_point
        self.root_commit_count = 0
        self.bootstrap_copy_attempt_count = 0

    def _inject_root_failure(self, point: str) -> None:
        if self.root_failure_point == point:
            fail("ROOT_SIMULATED_TRANSACTION_FAILURE", point)

    def initialize_authority_schema(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA journal_mode=TRUNCATE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata "
                "(key TEXT PRIMARY KEY, value BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS candidate_versions "
                "(ref_hash TEXT PRIMARY KEY, record_json BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS current_pointers "
                "(logical_pointer_key TEXT PRIMARY KEY, "
                "project_scope_id TEXT NOT NULL, pointer_json BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS merge_receipts "
                "(project_scope_id TEXT NOT NULL, operation_id TEXT NOT NULL, "
                "request_hash TEXT NOT NULL UNIQUE, receipt_json BLOB NOT NULL, "
                "PRIMARY KEY(project_scope_id, operation_id))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS candidate_aux_records "
                "(storage_key TEXT PRIMARY KEY, record_json BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS candidate_root_operations "
                "(operation_id TEXT PRIMARY KEY, pointer_logical_key TEXT NOT NULL UNIQUE, "
                "request_hash TEXT NOT NULL UNIQUE, scope_hash TEXT NOT NULL, "
                "authority_snapshot_json BLOB NOT NULL, result_json BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS candidate_migrations "
                "(migration_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL, "
                "source_sha256 TEXT NOT NULL, request_hash TEXT NOT NULL UNIQUE, "
                "result_json BLOB NOT NULL)"
            )
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'project_scope_id'"
            ).fetchone()
            encoded_scope = self.project_scope_id.encode("utf-8")
            if row is None:
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    ("project_scope_id", sqlite3.Binary(encoded_scope)),
                )
            elif bytes(row[0]) != encoded_scope:
                fail("PROJECT_SCOPE_STORE_MISMATCH")
            connection.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)",
                ("authority_schema", sqlite3.Binary(b"r01-candidate")),
            )
            connection.commit()

    def initialize(self, *_args: Any, **_kwargs: Any) -> None:
        """Reject the legacy B-06 root-copy path on the product composition."""

        self.bootstrap_copy_attempt_count += 1
        fail("B06_BOOTSTRAP_COPY_FORBIDDEN")

    @staticmethod
    def _root_parts(state: dict[str, Any]) -> dict[str, Any]:
        if set(state) != {"records", "pointers", "operations"}:
            fail("ROOT_STATE_SHAPE_INVALID")
        if len(state["pointers"]) != 1 or len(state["operations"]) != 1:
            fail("ROOT_ATOMIC_WRITE_SET_INVALID")
        records = list(state["records"].values())
        if len(records) != 3 or {item["record_type"] for item in records} != (
            ROOT_RECORD_TYPES
        ):
            fail("ROOT_ATOMIC_WRITE_SET_INVALID")
        candidate = next(
            item for item in records if item["record_type"] == "M3_CANDIDATE_VERSION"
        )
        segment = next(
            item
            for item in records
            if item["record_type"] == "M3_SEGMENT_INDEX_SNAPSHOT"
        )
        snapshot = next(
            item
            for item in records
            if item["record_type"] == "M3_CANDIDATE_POINTER_SNAPSHOT"
        )
        pointer_key, pointer = next(iter(state["pointers"].items()))
        operation_id, operation = next(iter(state["operations"].items()))
        result = operation["result"]
        candidate_ref = record_ref(candidate)
        if (
            candidate["record_version"] != 1
            or candidate["payload"]["parent_candidate_version_ref"] is not None
            or pointer["logical_pointer_key"] != pointer_key
            or pointer["pointer_namespace"] != FIXTURE_POINTER_NAMESPACE
            or pointer["generation"] != 1
            or canonical_bytes(pointer["current_candidate_version_ref"])
            != canonical_bytes(candidate_ref)
            or canonical_bytes(result["candidate_version_ref"])
            != canonical_bytes(candidate_ref)
            or result["logical_pointer_key"] != pointer_key
            or snapshot["payload"]["snapshot_operation_id"] != operation_id
            or canonical_bytes(snapshot["payload"]["current_candidate_version_ref"])
            != canonical_bytes(candidate_ref)
        ):
            fail("ROOT_INTERNAL_BINDING_INVALID")
        return {
            "candidate": candidate,
            "segment": segment,
            "snapshot": snapshot,
            "pointer_key": pointer_key,
            "pointer": pointer,
            "operation_id": operation_id,
            "operation": operation,
            "result": result,
        }

    def _validate_root_scope(
        self, parts: dict[str, Any], authority_snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        if set(authority_snapshot) != ROOT_AUTHORITY_KEYS:
            fail("ROOT_AUTHORITY_SHAPE_INVALID")
        pointer = parts["pointer"]
        candidate = parts["candidate"]
        segment = parts["segment"]
        if (
            authority_snapshot["project_scope_id"] != self.project_scope_id
            or pointer["project_scope_id"] != self.project_scope_id
            or pointer["chapter_revision_ref"]
            != authority_snapshot["chapter_revision_ref"]
            or candidate["payload"]["chapter_revision_ref"]
            != authority_snapshot["chapter_revision_ref"]
            or segment["payload"]["chapter_revision_ref"]
            != authority_snapshot["chapter_revision_ref"]
        ):
            fail("ROOT_AUTHORITY_SCOPE_MISMATCH")
        scope = {
            "project_scope_id": self.project_scope_id,
            "chapter_revision_ref": deepcopy(pointer["chapter_revision_ref"]),
            "seg": pointer["seg"],
            "input_generation_id": authority_snapshot["input_generation_id"],
            "input_generation_hash": authority_snapshot["input_generation_hash"],
            "input_binding_hash": pointer["input_binding_hash"],
            "segment_scope_hash": authority_snapshot["segment_scope_hash"],
        }
        return scope

    @staticmethod
    def _insert_exact(
        connection: sqlite3.Connection,
        *,
        table: str,
        key_column: str,
        key: str,
        value_column: str,
        value: bytes,
    ) -> bool:
        row = connection.execute(
            f'SELECT "{value_column}" FROM "{table}" WHERE "{key_column}" = ?',
            (key,),
        ).fetchone()
        if row is None:
            connection.execute(
                f'INSERT INTO "{table}"("{key_column}", "{value_column}") '
                "VALUES (?, ?)",
                (key, sqlite3.Binary(value)),
            )
            return True
        if bytes(row[0]) != value:
            fail("ROOT_RECORD_IDENTITY_COLLISION", f"{table}:{key}")
        return False

    def _publish_root(
        self,
        *,
        staged_state: dict[str, Any],
        authority_snapshot: dict[str, Any],
        publisher_token: object | None = None,
    ) -> dict[str, Any]:
        if publisher_token not in {_ROOT_PUBLISH_TOKEN, _LEGACY_MIGRATION_TOKEN}:
            fail("ROOT_PUBLISHER_SCOPE_ESCAPE")
        parts = self._root_parts(staged_state)
        scope = self._validate_root_scope(parts, authority_snapshot)
        request_hash = parts["operation"]["request_hash"]
        scope_hash = sha256_value(scope)
        result_bytes = canonical_bytes(parts["result"])
        authority_bytes = canonical_bytes(authority_snapshot)
        with self.serialization():
            connection = sqlite3.connect(self._database_path)
            try:
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT request_hash, scope_hash, result_json "
                    "FROM candidate_root_operations WHERE operation_id = ?",
                    (parts["operation_id"],),
                ).fetchone()
                if prior is not None:
                    if (
                        prior[0] != request_hash
                        or prior[1] != scope_hash
                        or bytes(prior[2]) != result_bytes
                    ):
                        fail("ROOT_OPERATION_INPUT_CONFLICT")
                    connection.rollback()
                    return {
                        **_decode(prior[2], code="ROOT_RESULT_INVALID"),
                        "authority_scope_hash": scope_hash,
                        "reused_existing_initialization": True,
                    }
                pointer_row = connection.execute(
                    "SELECT pointer_json FROM current_pointers "
                    "WHERE logical_pointer_key = ?",
                    (parts["pointer_key"],),
                ).fetchone()
                if pointer_row is not None:
                    fail("ROOT_POINTER_ALREADY_INITIALIZED")
                records_inserted = 0
                candidate = parts["candidate"]
                if self._insert_exact(
                    connection,
                    table="candidate_versions",
                    key_column="ref_hash",
                    key=sha256_value(record_ref(candidate)),
                    value_column="record_json",
                    value=canonical_bytes(candidate),
                ):
                    records_inserted += 1
                for record in (parts["segment"], parts["snapshot"]):
                    if self._insert_exact(
                        connection,
                        table="candidate_aux_records",
                        key_column="storage_key",
                        key=_storage_key(record),
                        value_column="record_json",
                        value=canonical_bytes(record),
                    ):
                        records_inserted += 1
                self._inject_root_failure("after_records_insert")
                pointer = parts["pointer"]
                connection.execute(
                    "INSERT INTO current_pointers("
                    "logical_pointer_key, project_scope_id, pointer_json"
                    ") VALUES (?, ?, ?)",
                    (
                        parts["pointer_key"],
                        self.project_scope_id,
                        sqlite3.Binary(canonical_bytes(pointer)),
                    ),
                )
                self._inject_root_failure("after_pointer_insert")
                connection.execute(
                    "INSERT INTO candidate_root_operations("
                    "operation_id, pointer_logical_key, request_hash, scope_hash, "
                    "authority_snapshot_json, result_json"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        parts["operation_id"],
                        parts["pointer_key"],
                        request_hash,
                        scope_hash,
                        sqlite3.Binary(authority_bytes),
                        sqlite3.Binary(result_bytes),
                    ),
                )
                self._inject_root_failure("before_commit")
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                fail("ROOT_IDENTITY_CONFLICT", str(error))
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        self.root_commit_count += 1
        self.physical_write_attempts.append(
            {
                "event": "sqlite_root_atomic_commit",
                "transaction_id": parts["operation_id"],
            }
        )
        self.events.append(
            {
                "event": "root_pointer_snapshot_committed",
                "transaction_id": parts["operation_id"],
                "records_inserted": str(records_inserted),
            }
        )
        return {
            **deepcopy(parts["result"]),
            "authority_scope_hash": scope_hash,
            "reused_existing_initialization": False,
        }

    def read_root_operation(self, operation_id: str) -> dict[str, Any]:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT request_hash, scope_hash, authority_snapshot_json, result_json "
                "FROM candidate_root_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if row is None:
            fail("ROOT_OPERATION_NOT_FOUND")
        return {
            "request_hash": row[0],
            "scope_hash": row[1],
            "authority_snapshot": _decode(
                row[2], code="ROOT_AUTHORITY_SNAPSHOT_INVALID"
            ),
            "result": _decode(row[3], code="ROOT_RESULT_INVALID"),
        }

    def table_counts(self) -> dict[str, int]:
        with sqlite3.connect(self._database_path) as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' ORDER BY name"
                ).fetchall()
            ]
            return {
                table: connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
                for table in tables
            }

    @property
    def database_path(self) -> Path:
        return self._database_path

    @staticmethod
    def _migration_request_hash(
        *, migration_id: str, source_kind: str, source_sha256: str
    ) -> str:
        return sha256_value(
            {
                "migration_id": migration_id,
                "source_kind": source_kind,
                "source_sha256": source_sha256,
            }
        )

    def read_migration(
        self,
        *,
        migration_id: str,
        source_kind: str,
        source_sha256: str,
    ) -> dict[str, Any] | None:
        request_hash = self._migration_request_hash(
            migration_id=migration_id,
            source_kind=source_kind,
            source_sha256=source_sha256,
        )
        with sqlite3.connect(self._database_path) as connection:
            prior = connection.execute(
                "SELECT source_kind, source_sha256, request_hash, result_json "
                "FROM candidate_migrations WHERE migration_id = ?",
                (migration_id,),
            ).fetchone()
        if prior is None:
            return None
        if (
            prior[0] != source_kind
            or prior[1] != source_sha256
            or prior[2] != request_hash
        ):
            fail("MIGRATION_ID_INPUT_CONFLICT")
        return {
            **_decode(prior[3], code="MIGRATION_RESULT_INVALID"),
            "reused": True,
        }

    def record_migration(
        self,
        *,
        migration_id: str,
        source_kind: str,
        source_sha256: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        prior = self.read_migration(
            migration_id=migration_id,
            source_kind=source_kind,
            source_sha256=source_sha256,
        )
        if prior is not None:
            return prior
        request_hash = self._migration_request_hash(
            migration_id=migration_id,
            source_kind=source_kind,
            source_sha256=source_sha256,
        )
        result_bytes = canonical_bytes(result)
        with self.serialization():
            connection = sqlite3.connect(self._database_path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT source_kind, source_sha256, request_hash, result_json "
                    "FROM candidate_migrations WHERE migration_id = ?",
                    (migration_id,),
                ).fetchone()
                if prior is not None:
                    if (
                        prior[0] != source_kind
                        or prior[1] != source_sha256
                        or prior[2] != request_hash
                        or bytes(prior[3]) != result_bytes
                    ):
                        fail("MIGRATION_ID_INPUT_CONFLICT")
                    connection.rollback()
                    return {
                        **_decode(prior[3], code="MIGRATION_RESULT_INVALID"),
                        "reused": True,
                    }
                connection.execute(
                    "INSERT INTO candidate_migrations("
                    "migration_id, source_kind, source_sha256, request_hash, result_json"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        migration_id,
                        source_kind,
                        source_sha256,
                        request_hash,
                        sqlite3.Binary(result_bytes),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        return {**deepcopy(result), "reused": False}

    @staticmethod
    def _legacy_chain_reaches(
        current: dict[str, Any],
        incoming: dict[str, Any],
        receipts: list[dict[str, Any]],
    ) -> bool:
        generation = current["generation"]
        candidate_ref = current["current_candidate_version_ref"]
        while generation < incoming["generation"]:
            matches = [
                receipt
                for receipt in receipts
                if receipt["payload"]["pointer_generation_before"] == generation
                and receipt["payload"]["pointer_logical_key"]
                == current["logical_pointer_key"]
                and canonical_bytes(
                    receipt["payload"]["base_candidate_version_ref"]
                )
                == canonical_bytes(candidate_ref)
            ]
            if len(matches) != 1:
                return False
            payload = matches[0]["payload"]
            generation = payload["pointer_generation_after"]
            candidate_ref = payload["child_candidate_version_ref"]
        return generation == incoming["generation"] and canonical_bytes(
            candidate_ref
        ) == canonical_bytes(incoming["current_candidate_version_ref"])

    @staticmethod
    def _legacy_insert_or_match(
        connection: sqlite3.Connection,
        *,
        table: str,
        key_where: str,
        key_values: tuple[Any, ...],
        value_column: str,
        value: bytes,
        insert_sql: str,
        insert_values: tuple[Any, ...],
    ) -> bool:
        row = connection.execute(
            f'SELECT "{value_column}" FROM "{table}" WHERE {key_where}',
            key_values,
        ).fetchone()
        if row is None:
            connection.execute(insert_sql, insert_values)
            return True
        if bytes(row[0]) != value:
            fail("MIGRATION_RECORD_CONFLICT", table)
        return False

    def import_legacy_b06_snapshot(
        self,
        *,
        migration_id: str,
        source_sha256: str,
        candidate_rows: list[tuple[str, bytes]],
        pointer_rows: list[tuple[str, str, bytes]],
        receipt_rows: list[tuple[str, str, str, bytes]],
        receipts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        source_kind = "B06_SQLITE"
        request_hash = self._migration_request_hash(
            migration_id=migration_id,
            source_kind=source_kind,
            source_sha256=source_sha256,
        )
        with self.serialization():
            connection = sqlite3.connect(self._database_path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT source_kind, source_sha256, request_hash, result_json "
                    "FROM candidate_migrations WHERE migration_id = ?",
                    (migration_id,),
                ).fetchone()
                if prior is not None:
                    if (
                        prior[0] != source_kind
                        or prior[1] != source_sha256
                        or prior[2] != request_hash
                    ):
                        fail("MIGRATION_ID_INPUT_CONFLICT")
                    connection.rollback()
                    return {
                        **_decode(prior[3], code="MIGRATION_RESULT_INVALID"),
                        "reused": True,
                    }
                candidate_inserts = 0
                for ref_hash, raw in candidate_rows:
                    if self._legacy_insert_or_match(
                        connection,
                        table="candidate_versions",
                        key_where="ref_hash = ?",
                        key_values=(ref_hash,),
                        value_column="record_json",
                        value=raw,
                        insert_sql=(
                            "INSERT INTO candidate_versions(ref_hash, record_json) "
                            "VALUES (?, ?)"
                        ),
                        insert_values=(ref_hash, sqlite3.Binary(raw)),
                    ):
                        candidate_inserts += 1
                receipt_inserts = 0
                for project_scope_id, operation_id, receipt_hash, raw in receipt_rows:
                    if project_scope_id != self.project_scope_id:
                        fail("MIGRATION_PROJECT_SCOPE_MISMATCH")
                    if self._legacy_insert_or_match(
                        connection,
                        table="merge_receipts",
                        key_where="project_scope_id = ? AND operation_id = ?",
                        key_values=(project_scope_id, operation_id),
                        value_column="receipt_json",
                        value=raw,
                        insert_sql=(
                            "INSERT INTO merge_receipts("
                            "project_scope_id, operation_id, request_hash, receipt_json"
                            ") VALUES (?, ?, ?, ?)"
                        ),
                        insert_values=(
                            project_scope_id,
                            operation_id,
                            receipt_hash,
                            sqlite3.Binary(raw),
                        ),
                    ):
                        receipt_inserts += 1
                pointer_updates = 0
                for pointer_key, project_scope_id, raw in pointer_rows:
                    if project_scope_id != self.project_scope_id:
                        fail("MIGRATION_PROJECT_SCOPE_MISMATCH")
                    incoming = _decode(raw, code="MIGRATION_POINTER_INVALID")
                    existing_row = connection.execute(
                        "SELECT pointer_json FROM current_pointers "
                        "WHERE logical_pointer_key = ?",
                        (pointer_key,),
                    ).fetchone()
                    if existing_row is None:
                        connection.execute(
                            "INSERT INTO current_pointers("
                            "logical_pointer_key, project_scope_id, pointer_json"
                            ") VALUES (?, ?, ?)",
                            (
                                pointer_key,
                                project_scope_id,
                                sqlite3.Binary(raw),
                            ),
                        )
                        pointer_updates += 1
                        continue
                    existing = _decode(
                        existing_row[0], code="MIGRATION_POINTER_INVALID"
                    )
                    if canonical_bytes(existing) == canonical_bytes(incoming):
                        continue
                    if (
                        incoming["generation"] <= existing["generation"]
                        or not self._legacy_chain_reaches(
                            existing, incoming, receipts
                        )
                    ):
                        fail("MIGRATION_POINTER_CONFLICT")
                    cursor = connection.execute(
                        "UPDATE current_pointers SET pointer_json = ? "
                        "WHERE logical_pointer_key = ? AND pointer_json = ?",
                        (
                            sqlite3.Binary(raw),
                            pointer_key,
                            sqlite3.Binary(canonical_bytes(existing)),
                        ),
                    )
                    if cursor.rowcount != 1:
                        fail("MIGRATION_POINTER_CONFLICT")
                    pointer_updates += 1
                result = {
                    "source_sha256": source_sha256,
                    "candidate_rows_inserted": candidate_inserts,
                    "receipt_rows_inserted": receipt_inserts,
                    "pointer_rows_inserted_or_advanced": pointer_updates,
                    "source_unchanged": True,
                }
                connection.execute(
                    "INSERT INTO candidate_migrations("
                    "migration_id, source_kind, source_sha256, request_hash, result_json"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        migration_id,
                        source_kind,
                        source_sha256,
                        request_hash,
                        sqlite3.Binary(canonical_bytes(result)),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        return {**result, "reused": False}


class CandidateRootInitializer:
    """Narrow B-01 product-facing capability; it exposes no generic store commit."""

    __slots__ = ("__store", "__authority_reader")

    def __init__(
        self,
        *,
        store: CandidateAuthorityStore,
        authority_reader: Callable[[], dict[str, Any]],
    ) -> None:
        self.__store = store
        self.__authority_reader = authority_reader

    @staticmethod
    def _generation_record(request: dict[str, Any]) -> dict[str, Any]:
        target_ref = request["accepted_source_generation_ref"]
        matches = [
            record
            for record in request["reference_records"]
            if canonical_bytes(record_ref(record)) == canonical_bytes(target_ref)
        ]
        if len(matches) != 1:
            fail("ROOT_INPUT_GENERATION_UNRESOLVABLE")
        return matches[0]

    @staticmethod
    def _selected_segment(request: dict[str, Any]) -> dict[str, Any]:
        matches = [
            item for item in request["segment_inputs"] if item.get("seg") == request["seg"]
        ]
        if len(matches) != 1:
            fail("ROOT_SEGMENT_SCOPE_UNRESOLVABLE")
        return matches[0]

    def _authority(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            value = self.__authority_reader()
        except Exception as error:
            fail("ROOT_AUTHORITY_READER_UNAVAILABLE", str(error))
        if not isinstance(value, dict) or set(value) != ROOT_AUTHORITY_KEYS:
            fail("ROOT_AUTHORITY_SHAPE_INVALID")
        generation = self._generation_record(request)
        payload = generation.get("payload", {})
        segment_scope_hash = sha256_value(self._selected_segment(request))
        if (
            value["project_scope_id"] != request["project_scope_id"]
            or value["project_scope_id"] != self.__store.project_scope_id
            or value["chapter_revision_ref"] != request["chapter_revision_ref"]
            or value["input_generation_id"] != request["input_generation_id"]
            or value["input_generation_id"] != payload.get("workspace_generation_id")
            or value["input_generation_hash"] != payload.get("manifest_sha256")
            or value["segment_scope_hash"] != segment_scope_hash
        ):
            fail("ROOT_AUTHORITY_SCOPE_MISMATCH")
        return deepcopy(value)

    def initialize_root(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict) or set(request) != ROOT_REQUEST_KEYS:
            fail("ROOT_REQUEST_SHAPE_INVALID")
        prepared = deepcopy(request)
        input_generation_id = prepared.pop("input_generation_id")
        raw_items = prepared.pop("raw_items")
        authority_before = self._authority(request)
        capture = _B01RootCaptureStore()
        service, admit_extraction = _compose_ccz142_b01_runtime(capture)
        extraction_admission = admit_extraction(
            source_lane=CCZ142_EXTRACTION_SOURCE_LANE,
            source_module=CCZ142_EXTRACTION_SOURCE_MODULE,
            source_contract_version=CCZ142_EXTRACTION_HANDOFF_CONTRACT,
            project_scope_id=prepared["project_scope_id"],
            author_workspace_logical_key=prepared["author_workspace_logical_key"],
            chapter_revision_ref=prepared["chapter_revision_ref"],
            accepted_source_generation_ref=prepared[
                "accepted_source_generation_ref"
            ],
            writing_material_refs=prepared["writing_material_refs"],
            source_module_identity=prepared["source_module_identity"],
            segment_inputs=prepared["segment_inputs"],
            seg=prepared["seg"],
            origin_attempt_refs=prepared["origin_attempt_refs"],
            raw_items=raw_items,
        )
        result = service.initialize_root_baseline(
            **prepared,
            extraction_admission=extraction_admission,
        )
        authority_after = self._authority(
            {**request, "input_generation_id": input_generation_id}
        )
        if canonical_bytes(authority_after) != canonical_bytes(authority_before):
            fail("ROOT_AUTHORITY_DRIFT")
        published = self.__store._publish_root(
            staged_state=capture.take(),
            authority_snapshot=authority_before,
            publisher_token=_ROOT_PUBLISH_TOKEN,
        )
        if any(
            canonical_bytes(published[key]) != canonical_bytes(result[key])
            for key in result
        ):
            fail("ROOT_PUBLISH_READBACK_MISMATCH")
        return published
