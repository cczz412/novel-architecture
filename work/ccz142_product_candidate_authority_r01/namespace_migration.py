"""Persisted cutover gates without becoming a second candidate-object writer."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
for candidate in (REPOSITORY_ROOT, AUTHORITY_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    FIXTURE_ACCESS,
    FIXTURE_AUTHORITY_PROFILE,
    FIXTURE_POINTER_NAMESPACE,
    PRODUCT_AUTHORITY_PROFILE,
    PRODUCT_READ_ONLY_ACCESS,
    canonical_bytes,
    record_ref,
    require_authority_profile,
    sha256_value,
    validate_candidate_version,
)
from work.ccz57_m3_b06_commit_core_r01.b06_contracts import (  # noqa: E402
    validate_mutable_pointer,
)
from candidate_authority import CandidateAuthorityStore  # noqa: E402

CONTROL_SCHEMA_VERSION = "ccz142-product-namespace-migration-r04"
SOURCE_EVIDENCE_KEYS = {
    "source_namespace",
    "candidate_access",
    "upstream_access",
    "project_scope_id",
    "source_authority_store_id",
    "source_storage_locator_hash",
    "source_pointer_key",
    "source_pointer_generation",
    "source_candidate_ref",
    "source_semantic_hash",
    "source_eligibility",
}
PRE_CUTOVER_STATES = {
    "DISCOVERED",
    "SOURCE_VERIFIED",
    "TARGET_STAGED",
    "SHADOW_VERIFIED",
}
CONTROL_TABLE_LAYOUTS = {
    "metadata": (
        ("key", "TEXT", 0, None, 1),
        ("value", "BLOB", 1, None, 0),
    ),
    "migration_state": (
        ("migration_id", "TEXT", 0, None, 1),
        ("project_scope_id", "TEXT", 1, None, 0),
        ("source_json", "BLOB", 1, None, 0),
        ("source_hash", "TEXT", 1, None, 0),
        ("state", "TEXT", 1, None, 0),
        ("target_root_result_json", "BLOB", 0, None, 0),
        ("target_pointer_key", "TEXT", 0, None, 0),
        ("target_pointer_generation", "INTEGER", 0, None, 0),
        ("target_authority_store_id", "TEXT", 0, None, 0),
        ("target_storage_locator_hash", "TEXT", 0, None, 0),
        ("shadow_semantic_hash", "TEXT", 0, None, 0),
        ("shadow_source_semantic_hash", "TEXT", 0, None, 0),
        ("shadow_target_semantic_hash", "TEXT", 0, None, 0),
        ("shadow_target_authority_store_id", "TEXT", 0, None, 0),
        ("shadow_target_storage_locator_hash", "TEXT", 0, None, 0),
        ("shadow_target_pointer_key", "TEXT", 0, None, 0),
        ("shadow_target_pointer_generation", "INTEGER", 0, None, 0),
        ("event_sequence", "INTEGER", 1, None, 0),
    ),
    "migration_events": (
        ("migration_id", "TEXT", 1, None, 1),
        ("event_sequence", "INTEGER", 1, None, 2),
        ("event", "TEXT", 1, None, 0),
        ("payload_json", "BLOB", 1, None, 0),
    ),
    "authority_project_bindings": (
        ("project_scope_id", "TEXT", 0, None, 1),
        ("authority_store_id", "TEXT", 1, None, 0),
        ("storage_locator_hash", "TEXT", 1, None, 0),
        ("bound_by_migration_id", "TEXT", 1, None, 0),
    ),
    "authority_pointer_bindings": (
        ("project_scope_id", "TEXT", 1, None, 1),
        ("target_pointer_key", "TEXT", 1, None, 2),
        ("authority_store_id", "TEXT", 1, None, 0),
        ("storage_locator_hash", "TEXT", 1, None, 0),
        ("migration_id", "TEXT", 1, None, 0),
        ("target_pointer_generation", "INTEGER", 1, None, 0),
    ),
}
CONTROL_UNIQUE_INDEXES = {
    "metadata": frozenset({("pk", 0, ("key",))}),
    "migration_state": frozenset({("pk", 0, ("migration_id",))}),
    "migration_events": frozenset(
        {("pk", 0, ("migration_id", "event_sequence"))}
    ),
    "authority_project_bindings": frozenset(
        {("pk", 0, ("project_scope_id",))}
    ),
    "authority_pointer_bindings": frozenset(
        {
            ("pk", 0, ("project_scope_id", "target_pointer_key")),
            ("u", 0, ("migration_id",)),
        }
    ),
}


class NamespaceMigrationError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def fail(code: str, detail: str = "") -> None:
    raise NamespaceMigrationError(code, detail)


def _decode(raw: Any) -> dict[str, Any]:
    value = json.loads(bytes(raw).decode("utf-8"))
    if not isinstance(value, dict):
        fail("MIGRATION_CONTROL_VALUE_INVALID")
    return value


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _candidate_semantic_projection(
    candidate: dict[str, Any],
    segment_index: dict[str, Any],
) -> dict[str, Any]:
    """Project fixture/product identities onto the same content semantics."""

    payload = candidate["payload"]
    seg = payload["seg"]
    selected_segment = segment_index["payload"]["segments"][seg - 1]
    items = []
    for item in payload["items"]:
        projected = {
            "fact": item["fact"],
            "status": item["status"],
            "evidence": item["evidence"],
            "evidence_binding": deepcopy(item["evidence_binding"]),
        }
        if "speaker" in item:
            projected["speaker"] = item["speaker"]
        items.append(projected)
    return {
        "candidate_schema_id": payload["candidate_schema_id"],
        "chapter_revision_ref": deepcopy(payload["chapter_revision_ref"]),
        "seg": seg,
        "extraction_input_binding": deepcopy(payload["extraction_input_binding"]),
        "segment_scope": {
            "coordinate_unit": segment_index["payload"]["coordinate_unit"],
            "chapter_length_bytes": segment_index["payload"]["chapter_length_bytes"],
            "coverage_denominator_bytes": segment_index["payload"][
                "coverage_denominator_bytes"
            ],
            "selected_segment": deepcopy(selected_segment),
        },
        "items": items,
    }


class ReadOnlyMigrationSource:
    """Reread one exact fixture authority pointer without exposing a writer."""

    __slots__ = ("__store", "__logical_pointer_key", "__reference_records")

    def __init__(
        self,
        *,
        store: CandidateAuthorityStore,
        logical_pointer_key: str,
        reference_records: list[dict[str, Any]],
    ) -> None:
        if not isinstance(store, CandidateAuthorityStore):
            fail("MIGRATION_SOURCE_READER_INVALID")
        if not isinstance(logical_pointer_key, str) or not logical_pointer_key:
            fail("MIGRATION_SOURCE_POINTER_INVALID")
        if not isinstance(reference_records, list):
            fail("MIGRATION_SOURCE_REFERENCE_SET_INVALID")
        self.__store = store
        self.__logical_pointer_key = logical_pointer_key
        self.__reference_records = deepcopy(reference_records)

    @contextmanager
    def locked_evidence(self) -> Iterator[dict[str, Any]]:
        with self.__store.serialization():
            yield self._read_locked()

    def read_evidence(self) -> dict[str, Any]:
        with self.locked_evidence() as evidence:
            return deepcopy(evidence)

    def _read_locked(self) -> dict[str, Any]:
        try:
            source_profile = require_authority_profile(
                self.__store.authority_profile
            )
        except ValueError:
            fail("MIGRATION_SOURCE_PROFILE_INVALID")
        if source_profile is not FIXTURE_AUTHORITY_PROFILE:
            fail("MIGRATION_SOURCE_PROFILE_INVALID")
        try:
            pointer = self.__store.read_pointer(self.__logical_pointer_key)
            candidate = self.__store.read_candidate(
                pointer["current_candidate_version_ref"]
            )
            segment_index = self.__store.read_aux_record(
                candidate["payload"]["segment_index_ref"]
            )
            validation_records = [
                *deepcopy(self.__reference_records),
                deepcopy(segment_index),
            ]
            validate_candidate_version(
                candidate,
                allow_child=(
                    candidate["payload"]["parent_candidate_version_ref"] is not None
                ),
                reference_records=validation_records,
                authority_profile=FIXTURE_AUTHORITY_PROFILE,
            )
            validate_mutable_pointer(
                pointer,
                candidate=candidate,
                reference_records=validation_records,
                authority_profile=FIXTURE_AUTHORITY_PROFILE,
            )
        except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
            fail("MIGRATION_SOURCE_EVIDENCE_INVALID", str(error))
        binding = candidate["payload"]["extraction_input_binding"]
        upstream_refs = [
            binding["accepted_source_generation_ref"],
            *(item["material_ref"] for item in binding["writing_material_refs"]),
        ]
        product_read_only = (
            upstream_refs
            and all(ref["access"] == PRODUCT_READ_ONLY_ACCESS for ref in upstream_refs)
            and segment_index["payload"]["source_module_identity"]
            == "CCZ142_READ_ONLY_ADAPTER"
        )
        projection = _candidate_semantic_projection(candidate, segment_index)
        return {
            "source_namespace": pointer["pointer_namespace"],
            "candidate_access": candidate["access"],
            "upstream_access": (
                PRODUCT_READ_ONLY_ACCESS if product_read_only else FIXTURE_ACCESS
            ),
            "project_scope_id": pointer["project_scope_id"],
            "source_authority_store_id": self.__store.authority_store_id,
            "source_storage_locator_hash": self.__store.storage_locator_hash,
            "source_pointer_key": pointer["logical_pointer_key"],
            "source_pointer_generation": pointer["generation"],
            "source_candidate_ref": record_ref(candidate),
            "source_semantic_hash": sha256_value(projection),
            "source_eligibility": (
                "PRODUCT_READ_ONLY_VERIFIED"
                if product_read_only
                else "SYNTHETIC_FIXTURE_REJECTED"
            ),
        }


class NamespaceMigrationController:
    """Write only migration state and cutover events, never candidate objects."""

    def __init__(self, root: Path) -> None:
        self.root = self._guard_root(root)
        self.database_path = self.root / "namespace-migration-control.sqlite3"
        self.lock_path = self.root / ".namespace-migration-control.lock"
        self._initialize()

    @staticmethod
    def _guard_root(root: Path) -> Path:
        resolved = root.resolve(strict=False)
        module_root = Path(__file__).resolve().parent
        repository_root = module_root.parents[1]
        temporary_root = Path(tempfile.gettempdir()).resolve()
        inside_repository = (
            resolved == repository_root or repository_root in resolved.parents
        )
        inside_module = resolved == module_root or module_root in resolved.parents
        inside_temp = resolved == temporary_root or temporary_root in resolved.parents
        if (inside_repository and not inside_module) or (
            not inside_repository and not inside_temp
        ):
            fail("MIGRATION_CONTROL_WRITE_SET_ESCAPE", str(root))
        return resolved

    def _initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.lock_path, flags, 0o600)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            os.close(descriptor)
            fail("MIGRATION_CONTROL_LOCK_INVALID")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.execute("PRAGMA journal_mode=TRUNCATE")
                connection.execute("PRAGMA synchronous=FULL")
                existing_tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                if existing_tables:
                    if existing_tables != set(CONTROL_TABLE_LAYOUTS):
                        fail("MIGRATION_CONTROL_SCHEMA_OBJECT_MISMATCH")
                    schema_row = connection.execute(
                        "SELECT value FROM metadata WHERE key = 'schema_version'"
                    ).fetchone()
                    if schema_row is None:
                        fail("MIGRATION_CONTROL_SCHEMA_IDENTITY_MISSING")
                    if bytes(schema_row[0]) != CONTROL_SCHEMA_VERSION.encode("utf-8"):
                        fail("MIGRATION_CONTROL_SCHEMA_IDENTITY_MISMATCH")
                else:
                    connection.execute(
                        "CREATE TABLE metadata ("
                        "key TEXT PRIMARY KEY, value BLOB NOT NULL)"
                    )
                    connection.execute(
                        "CREATE TABLE migration_state ("
                        "migration_id TEXT PRIMARY KEY, "
                        "project_scope_id TEXT NOT NULL, "
                        "source_json BLOB NOT NULL, source_hash TEXT NOT NULL, "
                        "state TEXT NOT NULL, target_root_result_json BLOB, "
                        "target_pointer_key TEXT, target_pointer_generation INTEGER, "
                        "target_authority_store_id TEXT, "
                        "target_storage_locator_hash TEXT, "
                        "shadow_semantic_hash TEXT, "
                        "shadow_source_semantic_hash TEXT, "
                        "shadow_target_semantic_hash TEXT, "
                        "shadow_target_authority_store_id TEXT, "
                        "shadow_target_storage_locator_hash TEXT, "
                        "shadow_target_pointer_key TEXT, "
                        "shadow_target_pointer_generation INTEGER, "
                        "event_sequence INTEGER NOT NULL)"
                    )
                    connection.execute(
                        "CREATE TABLE migration_events ("
                        "migration_id TEXT NOT NULL, "
                        "event_sequence INTEGER NOT NULL, "
                        "event TEXT NOT NULL, payload_json BLOB NOT NULL, "
                        "PRIMARY KEY(migration_id, event_sequence))"
                    )
                    connection.execute(
                        "CREATE TABLE authority_project_bindings ("
                        "project_scope_id TEXT PRIMARY KEY, "
                        "authority_store_id TEXT NOT NULL, "
                        "storage_locator_hash TEXT NOT NULL, "
                        "bound_by_migration_id TEXT NOT NULL)"
                    )
                    connection.execute(
                        "CREATE TABLE authority_pointer_bindings ("
                        "project_scope_id TEXT NOT NULL, "
                        "target_pointer_key TEXT NOT NULL, "
                        "authority_store_id TEXT NOT NULL, "
                        "storage_locator_hash TEXT NOT NULL, "
                        "migration_id TEXT NOT NULL UNIQUE, "
                        "target_pointer_generation INTEGER NOT NULL, "
                        "PRIMARY KEY(project_scope_id, target_pointer_key))"
                    )
                    connection.execute(
                        "INSERT INTO metadata(key, value) VALUES (?, ?)",
                        (
                            "schema_version",
                            sqlite3.Binary(CONTROL_SCHEMA_VERSION.encode("utf-8")),
                        ),
                    )
                self._verify_control_schema(connection)
                connection.commit()
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _verify_control_schema(connection: sqlite3.Connection) -> None:
        actual_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if actual_tables != set(CONTROL_TABLE_LAYOUTS):
            fail("MIGRATION_CONTROL_SCHEMA_OBJECT_MISMATCH")
        schema_row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        if schema_row is None:
            fail("MIGRATION_CONTROL_SCHEMA_IDENTITY_MISSING")
        if bytes(schema_row[0]) != CONTROL_SCHEMA_VERSION.encode("utf-8"):
            fail("MIGRATION_CONTROL_SCHEMA_IDENTITY_MISMATCH")
        for table, expected_layout in CONTROL_TABLE_LAYOUTS.items():
            actual_layout = tuple(
                (row[1], str(row[2]).upper(), row[3], row[4], row[5])
                for row in connection.execute(
                    f'PRAGMA table_info("{table}")'
                ).fetchall()
            )
            if actual_layout != expected_layout:
                fail("MIGRATION_CONTROL_SCHEMA_LAYOUT_MISMATCH", table)
            actual_unique_indexes = set()
            for index_row in connection.execute(
                f'PRAGMA index_list("{table}")'
            ).fetchall():
                if index_row[2] != 1:
                    continue
                escaped_index = str(index_row[1]).replace('"', '""')
                columns = tuple(
                    row[2]
                    for row in connection.execute(
                        f'PRAGMA index_info("{escaped_index}")'
                    ).fetchall()
                )
                actual_unique_indexes.add((index_row[3], index_row[4], columns))
            if actual_unique_indexes != CONTROL_UNIQUE_INDEXES[table]:
                fail("MIGRATION_CONTROL_SCHEMA_UNIQUE_INDEX_MISMATCH", table)

    def _open_locked(self) -> tuple[int, sqlite3.Connection]:
        flags = os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.lock_path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            os.close(descriptor)
            fail("MIGRATION_CONTROL_LOCK_INVALID")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        self._verify_control_schema(connection)
        return descriptor, connection

    @staticmethod
    def _close_locked(
        descriptor: int,
        connection: sqlite3.Connection,
        *,
        commit: bool,
    ) -> None:
        try:
            connection.commit() if commit else connection.rollback()
        finally:
            connection.close()
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _row(connection: sqlite3.Connection, migration_id: str) -> tuple[Any, ...]:
        row = connection.execute(
            "SELECT project_scope_id, source_json, source_hash, state, "
            "target_root_result_json, target_pointer_key, "
            "target_pointer_generation, target_authority_store_id, "
            "target_storage_locator_hash, shadow_semantic_hash, "
            "shadow_source_semantic_hash, shadow_target_semantic_hash, "
            "shadow_target_authority_store_id, "
            "shadow_target_storage_locator_hash, shadow_target_pointer_key, "
            "shadow_target_pointer_generation, event_sequence "
            "FROM migration_state WHERE migration_id = ?",
            (migration_id,),
        ).fetchone()
        if row is None:
            fail("MIGRATION_NOT_FOUND")
        return row

    @staticmethod
    def _state_from_row(migration_id: str, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "migration_id": migration_id,
            "project_scope_id": row[0],
            "source": _decode(row[1]),
            "source_hash": row[2],
            "state": row[3],
            "target_root_result": None if row[4] is None else _decode(row[4]),
            "target_pointer_key": row[5],
            "target_pointer_generation": row[6],
            "target_authority_store_id": row[7],
            "target_storage_locator_hash": row[8],
            "shadow_semantic_hash": row[9],
            "shadow_source_semantic_hash": row[10],
            "shadow_target_semantic_hash": row[11],
            "shadow_target_authority_store_id": row[12],
            "shadow_target_storage_locator_hash": row[13],
            "shadow_target_pointer_key": row[14],
            "shadow_target_pointer_generation": row[15],
            "event_sequence": row[16],
        }

    @staticmethod
    def _bind_cutover(
        connection: sqlite3.Connection,
        *,
        migration_id: str,
        state: dict[str, Any],
    ) -> None:
        project_binding = (
            state["target_authority_store_id"],
            state["target_storage_locator_hash"],
        )
        prior_project = connection.execute(
            "SELECT authority_store_id, storage_locator_hash "
            "FROM authority_project_bindings WHERE project_scope_id = ?",
            (state["project_scope_id"],),
        ).fetchone()
        if prior_project is None:
            connection.execute(
                "INSERT INTO authority_project_bindings("
                "project_scope_id, authority_store_id, storage_locator_hash, "
                "bound_by_migration_id) VALUES (?, ?, ?, ?)",
                (
                    state["project_scope_id"],
                    *project_binding,
                    migration_id,
                ),
            )
        elif tuple(prior_project) != project_binding:
            fail("MIGRATION_PROJECT_AUTHORITY_CONFLICT")

        pointer_binding = (
            state["target_authority_store_id"],
            state["target_storage_locator_hash"],
            migration_id,
            state["target_pointer_generation"],
        )
        prior_pointer = connection.execute(
            "SELECT authority_store_id, storage_locator_hash, migration_id, "
            "target_pointer_generation FROM authority_pointer_bindings "
            "WHERE project_scope_id = ? AND target_pointer_key = ?",
            (state["project_scope_id"], state["target_pointer_key"]),
        ).fetchone()
        if prior_pointer is None:
            connection.execute(
                "INSERT INTO authority_pointer_bindings("
                "project_scope_id, target_pointer_key, authority_store_id, "
                "storage_locator_hash, migration_id, target_pointer_generation"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    state["project_scope_id"],
                    state["target_pointer_key"],
                    *pointer_binding,
                ),
            )
        elif tuple(prior_pointer) != pointer_binding:
            fail("MIGRATION_POINTER_AUTHORITY_CONFLICT")

    @staticmethod
    def _advance_pointer_binding(
        connection: sqlite3.Connection,
        *,
        migration_id: str,
        state: dict[str, Any],
        generation_before: int,
        generation_after: int,
    ) -> None:
        cursor = connection.execute(
            "UPDATE authority_pointer_bindings "
            "SET target_pointer_generation = ? "
            "WHERE project_scope_id = ? AND target_pointer_key = ? "
            "AND authority_store_id = ? AND storage_locator_hash = ? "
            "AND migration_id = ? AND target_pointer_generation = ?",
            (
                generation_after,
                state["project_scope_id"],
                state["target_pointer_key"],
                state["target_authority_store_id"],
                state["target_storage_locator_hash"],
                migration_id,
                generation_before,
            ),
        )
        if cursor.rowcount != 1:
            fail("MIGRATION_POINTER_AUTHORITY_CONFLICT")

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        migration_id: str,
        sequence: int,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        connection.execute(
            "INSERT INTO migration_events("
            "migration_id, event_sequence, event, payload_json"
            ") VALUES (?, ?, ?, ?)",
            (
                migration_id,
                sequence,
                event,
                sqlite3.Binary(canonical_bytes(payload)),
            ),
        )

    @staticmethod
    def _validate_source_evidence(source: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(source, dict) or set(source) != SOURCE_EVIDENCE_KEYS:
            fail("MIGRATION_SOURCE_EVIDENCE_SHAPE_INVALID")
        candidate_ref = source["source_candidate_ref"]
        if (
            source["source_namespace"] != FIXTURE_POINTER_NAMESPACE
            or source["candidate_access"] != FIXTURE_ACCESS
            or not isinstance(source["project_scope_id"], str)
            or not source["project_scope_id"]
            or not _is_sha256(source["source_authority_store_id"])
            or not _is_sha256(source["source_storage_locator_hash"])
            or not isinstance(source["source_pointer_key"], str)
            or not source["source_pointer_key"]
            or not isinstance(source["source_pointer_generation"], int)
            or isinstance(source["source_pointer_generation"], bool)
            or source["source_pointer_generation"] < 1
            or not isinstance(candidate_ref, dict)
            or candidate_ref.get("access") != FIXTURE_ACCESS
            or candidate_ref.get("record_type") != "M3_CANDIDATE_VERSION"
            or not _is_sha256(candidate_ref.get("record_hash"))
            or not _is_sha256(source["source_semantic_hash"])
            or source["upstream_access"]
            not in {FIXTURE_ACCESS, PRODUCT_READ_ONLY_ACCESS}
            or source["source_eligibility"]
            not in {
                "PRODUCT_READ_ONLY_VERIFIED",
                "SYNTHETIC_FIXTURE_REJECTED",
            }
        ):
            fail("MIGRATION_SOURCE_EVIDENCE_INVALID")
        eligibility_matches = (
            source["source_eligibility"] == "PRODUCT_READ_ONLY_VERIFIED"
            and source["upstream_access"] == PRODUCT_READ_ONLY_ACCESS
        ) or (
            source["source_eligibility"] == "SYNTHETIC_FIXTURE_REJECTED"
            and source["upstream_access"] == FIXTURE_ACCESS
        )
        if not eligibility_matches:
            fail("MIGRATION_SOURCE_EVIDENCE_INVALID", "eligibility")
        return deepcopy(source)

    @classmethod
    @contextmanager
    def _locked_source_evidence(
        cls,
        source_reader: ReadOnlyMigrationSource,
    ) -> Iterator[dict[str, Any]]:
        if not isinstance(source_reader, ReadOnlyMigrationSource):
            fail("MIGRATION_SOURCE_READER_REQUIRED")
        with source_reader.locked_evidence() as source:
            yield cls._validate_source_evidence(source)

    @staticmethod
    def _require_source_evidence(
        state: dict[str, Any],
        source: dict[str, Any],
    ) -> None:
        if (
            canonical_bytes(source) != canonical_bytes(state["source"])
            or sha256_value(source) != state["source_hash"]
            or source["project_scope_id"] != state["project_scope_id"]
        ):
            fail("MIGRATION_SOURCE_EVIDENCE_DRIFT")

    @staticmethod
    def _target_semantic_hash(
        store: CandidateAuthorityStore,
        pointer: dict[str, Any],
    ) -> str:
        try:
            candidate = store.read_candidate(pointer["current_candidate_version_ref"])
            segment_index = store.read_aux_record(
                candidate["payload"]["segment_index_ref"]
            )
            projection = _candidate_semantic_projection(candidate, segment_index)
        except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
            fail("MIGRATION_TARGET_EVIDENCE_INVALID", str(error))
        return sha256_value(projection)

    def discover(
        self,
        migration_id: str,
        source_reader: ReadOnlyMigrationSource,
    ) -> dict[str, Any]:
        if not isinstance(migration_id, str) or not migration_id:
            fail("MIGRATION_ID_INVALID")
        with self._locked_source_evidence(source_reader) as source:
            source = deepcopy(source)
        source_hash = sha256_value(source)
        rejected = (
            source["source_eligibility"] != "PRODUCT_READ_ONLY_VERIFIED"
            or source["upstream_access"] != PRODUCT_READ_ONLY_ACCESS
        )
        state = "REJECTED_READ_ONLY" if rejected else "DISCOVERED"
        descriptor, connection = self._open_locked()
        try:
            prior = connection.execute(
                "SELECT source_hash, state FROM migration_state WHERE migration_id = ?",
                (migration_id,),
            ).fetchone()
            if prior is not None:
                if prior[0] != source_hash:
                    fail("MIGRATION_ID_INPUT_CONFLICT")
                self._close_locked(descriptor, connection, commit=False)
                if prior[1] == "REJECTED_READ_ONLY":
                    fail("MIGRATION_SYNTHETIC_FIXTURE_INELIGIBLE")
                return self.read_state(migration_id)
            connection.execute(
                "INSERT INTO migration_state("
                "migration_id, project_scope_id, source_json, source_hash, state, "
                "event_sequence) VALUES (?, ?, ?, ?, ?, 1)",
                (
                    migration_id,
                    source["project_scope_id"],
                    sqlite3.Binary(canonical_bytes(source)),
                    source_hash,
                    state,
                ),
            )
            self._append_event(
                connection,
                migration_id=migration_id,
                sequence=1,
                event=state,
                payload={"source_hash": source_hash},
            )
            self._close_locked(descriptor, connection, commit=True)
        except Exception:
            try:
                in_transaction = connection.in_transaction
            except sqlite3.ProgrammingError:
                in_transaction = False
            if in_transaction:
                self._close_locked(descriptor, connection, commit=False)
            raise
        if rejected:
            fail("MIGRATION_SYNTHETIC_FIXTURE_INELIGIBLE")
        return self.read_state(migration_id)

    def _transition(
        self,
        migration_id: str,
        *,
        expected_state: str,
        next_state: str,
        event_payload: dict[str, Any],
        updates: dict[str, Any] | None = None,
        event_name: str | None = None,
        bind_cutover: bool = False,
        advance_pointer_binding: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        descriptor, connection = self._open_locked()
        try:
            row = self._row(connection, migration_id)
            if row[3] != expected_state:
                fail("MIGRATION_STATE_CONFLICT", f"{row[3]} != {expected_state}")
            state = self._state_from_row(migration_id, row)
            if bind_cutover:
                self._bind_cutover(
                    connection,
                    migration_id=migration_id,
                    state=state,
                )
            if advance_pointer_binding is not None:
                self._advance_pointer_binding(
                    connection,
                    migration_id=migration_id,
                    state=state,
                    generation_before=advance_pointer_binding[0],
                    generation_after=advance_pointer_binding[1],
                )
            sequence = row[16] + 1
            assignments = ["state = ?", "event_sequence = ?"]
            values: list[Any] = [next_state, sequence]
            for key, value in (updates or {}).items():
                if key not in {
                    "target_root_result_json",
                    "target_pointer_key",
                    "target_pointer_generation",
                    "target_authority_store_id",
                    "target_storage_locator_hash",
                    "shadow_semantic_hash",
                    "shadow_source_semantic_hash",
                    "shadow_target_semantic_hash",
                    "shadow_target_authority_store_id",
                    "shadow_target_storage_locator_hash",
                    "shadow_target_pointer_key",
                    "shadow_target_pointer_generation",
                }:
                    fail("MIGRATION_CONTROL_FIELD_INVALID", key)
                assignments.append(f"{key} = ?")
                values.append(value)
            values.append(migration_id)
            connection.execute(
                f"UPDATE migration_state SET {', '.join(assignments)} "
                "WHERE migration_id = ?",
                tuple(values),
            )
            self._append_event(
                connection,
                migration_id=migration_id,
                sequence=sequence,
                event=next_state if event_name is None else event_name,
                payload=event_payload,
            )
            self._close_locked(descriptor, connection, commit=True)
        except Exception:
            try:
                in_transaction = connection.in_transaction
            except sqlite3.ProgrammingError:
                in_transaction = False
            if in_transaction:
                self._close_locked(descriptor, connection, commit=False)
            raise
        return self.read_state(migration_id)

    def verify_source(
        self,
        migration_id: str,
        *,
        source_reader: ReadOnlyMigrationSource,
    ) -> dict[str, Any]:
        with self._locked_source_evidence(source_reader) as source:
            state = self.read_state(migration_id)
            self._require_source_evidence(state, source)
            return self._transition(
                migration_id,
                expected_state="DISCOVERED",
                next_state="SOURCE_VERIFIED",
                event_payload={"source_evidence_hash": state["source_hash"]},
            )

    @staticmethod
    def _require_product_store(store: CandidateAuthorityStore) -> None:
        try:
            identity = store.authority_profile.identity
            project_scope_id = store.project_scope_id
            authority_store_id = store.authority_store_id
            storage_locator_hash = store.storage_locator_hash
        except (AttributeError, RuntimeError, sqlite3.Error, UnicodeDecodeError):
            fail("MIGRATION_TARGET_PROFILE_MISMATCH")
        if (
            identity != PRODUCT_AUTHORITY_PROFILE.identity
            or not isinstance(project_scope_id, str)
            or not project_scope_id
            or not isinstance(authority_store_id, str)
            or len(authority_store_id) != 64
            or not isinstance(storage_locator_hash, str)
            or len(storage_locator_hash) != 64
        ):
            fail("MIGRATION_TARGET_PROFILE_MISMATCH")

    @classmethod
    def _require_target_store(
        cls,
        state: dict[str, Any],
        store: CandidateAuthorityStore,
    ) -> None:
        cls._require_product_store(store)
        if (
            store.project_scope_id != state["project_scope_id"]
            or store.authority_store_id != state["target_authority_store_id"]
            or store.storage_locator_hash != state["target_storage_locator_hash"]
            or not isinstance(state["target_pointer_key"], str)
            or not state["target_pointer_key"]
        ):
            fail("MIGRATION_TARGET_STORE_MISMATCH")

    @staticmethod
    def _require_target_pointer(
        state: dict[str, Any],
        pointer: dict[str, Any],
    ) -> None:
        if (
            pointer.get("project_scope_id") != state["project_scope_id"]
            or pointer.get("logical_pointer_key") != state["target_pointer_key"]
            or pointer.get("pointer_namespace")
            != PRODUCT_AUTHORITY_PROFILE.pointer_namespace
        ):
            fail("MIGRATION_TARGET_POINTER_MISMATCH")

    def stage_target(
        self,
        migration_id: str,
        *,
        store: CandidateAuthorityStore,
        root_result: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_product_store(store)
        with store.serialization():
            state = self.read_state(migration_id)
            if store.project_scope_id != state["project_scope_id"]:
                fail("MIGRATION_TARGET_PROFILE_MISMATCH")
            pointer = store.read_pointer(root_result["logical_pointer_key"])
            candidate = store.read_candidate(root_result["candidate_version_ref"])
            if (
                pointer["pointer_namespace"]
                != PRODUCT_AUTHORITY_PROFILE.pointer_namespace
                or pointer["project_scope_id"] != state["project_scope_id"]
                or pointer["generation"] != 1
                or pointer["current_candidate_version_ref"] != record_ref(candidate)
            ):
                fail("MIGRATION_TARGET_BINDING_INVALID")
            return self._transition(
                migration_id,
                expected_state="SOURCE_VERIFIED",
                next_state="TARGET_STAGED",
                event_payload={
                    "target_pointer_key": pointer["logical_pointer_key"],
                    "target_candidate_ref": record_ref(candidate),
                },
                updates={
                    "target_root_result_json": sqlite3.Binary(
                        canonical_bytes(root_result)
                    ),
                    "target_pointer_key": pointer["logical_pointer_key"],
                    "target_pointer_generation": pointer["generation"],
                    "target_authority_store_id": store.authority_store_id,
                    "target_storage_locator_hash": store.storage_locator_hash,
                },
            )

    def shadow_verify(
        self,
        migration_id: str,
        *,
        source_reader: ReadOnlyMigrationSource,
        store: CandidateAuthorityStore,
    ) -> dict[str, Any]:
        self._require_product_store(store)
        with self._locked_source_evidence(source_reader) as source:
            with store.serialization():
                state = self.read_state(migration_id)
                self._require_source_evidence(state, source)
                self._require_target_store(state, store)
                pointer = store.read_pointer(state["target_pointer_key"])
                self._require_target_pointer(state, pointer)
                if pointer["generation"] != state["target_pointer_generation"]:
                    fail("MIGRATION_SHADOW_GENERATION_MISMATCH")
                source_semantic_hash = source["source_semantic_hash"]
                target_semantic_hash = self._target_semantic_hash(store, pointer)
                if source_semantic_hash != target_semantic_hash:
                    fail("MIGRATION_SHADOW_DIVERGENCE")
                return self._transition(
                    migration_id,
                    expected_state="TARGET_STAGED",
                    next_state="SHADOW_VERIFIED",
                    event_payload={
                        "source_evidence_hash": state["source_hash"],
                        "source_semantic_hash": source_semantic_hash,
                        "target_semantic_hash": target_semantic_hash,
                        "target_authority_store_id": store.authority_store_id,
                        "target_storage_locator_hash": store.storage_locator_hash,
                        "target_pointer_key": pointer["logical_pointer_key"],
                        "target_pointer_generation": pointer["generation"],
                    },
                    updates={
                        "shadow_semantic_hash": source_semantic_hash,
                        "shadow_source_semantic_hash": source_semantic_hash,
                        "shadow_target_semantic_hash": target_semantic_hash,
                        "shadow_target_authority_store_id": store.authority_store_id,
                        "shadow_target_storage_locator_hash": store.storage_locator_hash,
                        "shadow_target_pointer_key": pointer["logical_pointer_key"],
                        "shadow_target_pointer_generation": pointer["generation"],
                    },
                )

    @staticmethod
    def _require_shadow_binding(
        state: dict[str, Any],
        source: dict[str, Any],
        store: CandidateAuthorityStore,
        pointer: dict[str, Any],
        target_semantic_hash: str,
    ) -> None:
        if (
            not _is_sha256(state["shadow_source_semantic_hash"])
            or state["shadow_source_semantic_hash"] != source["source_semantic_hash"]
            or state["shadow_source_semantic_hash"]
            != state["shadow_target_semantic_hash"]
            or state["shadow_semantic_hash"]
            != state["shadow_source_semantic_hash"]
            or state["shadow_target_semantic_hash"] != target_semantic_hash
            or state["shadow_target_authority_store_id"] != store.authority_store_id
            or state["shadow_target_storage_locator_hash"]
            != store.storage_locator_hash
            or state["shadow_target_pointer_key"] != pointer["logical_pointer_key"]
            or state["shadow_target_pointer_generation"] != pointer["generation"]
        ):
            fail("MIGRATION_SHADOW_BINDING_MISMATCH")

    def _require_persisted_bindings(self, state: dict[str, Any]) -> None:
        with sqlite3.connect(self.database_path) as connection:
            self._verify_control_schema(connection)
            project = connection.execute(
                "SELECT authority_store_id, storage_locator_hash "
                "FROM authority_project_bindings WHERE project_scope_id = ?",
                (state["project_scope_id"],),
            ).fetchone()
            pointer = connection.execute(
                "SELECT authority_store_id, storage_locator_hash, migration_id, "
                "target_pointer_generation FROM authority_pointer_bindings "
                "WHERE project_scope_id = ? AND target_pointer_key = ?",
                (state["project_scope_id"], state["target_pointer_key"]),
            ).fetchone()
        if project != (
            state["target_authority_store_id"],
            state["target_storage_locator_hash"],
        ):
            fail("MIGRATION_PROJECT_AUTHORITY_CONFLICT")
        if pointer != (
            state["target_authority_store_id"],
            state["target_storage_locator_hash"],
            state["migration_id"],
            state["target_pointer_generation"],
        ):
            fail("MIGRATION_POINTER_AUTHORITY_CONFLICT")

    def cutover(
        self,
        migration_id: str,
        *,
        source_reader: ReadOnlyMigrationSource,
        store: CandidateAuthorityStore,
    ) -> dict[str, Any]:
        self._require_product_store(store)
        with self._locked_source_evidence(source_reader) as source:
            with store.serialization():
                state = self.read_state(migration_id)
                self._require_source_evidence(state, source)
                self._require_target_store(state, store)
                pointer = store.read_pointer(state["target_pointer_key"])
                self._require_target_pointer(state, pointer)
                if pointer["generation"] != state["target_pointer_generation"]:
                    fail("MIGRATION_CUTOVER_CAS_MISMATCH")
                target_semantic_hash = self._target_semantic_hash(store, pointer)
                self._require_shadow_binding(
                    state,
                    source,
                    store,
                    pointer,
                    target_semantic_hash,
                )
                return self._transition(
                    migration_id,
                    expected_state="SHADOW_VERIFIED",
                    next_state="CUTOVER_COMMITTED",
                    event_payload={
                        "source_evidence_hash": state["source_hash"],
                        "target_pointer_key": pointer["logical_pointer_key"],
                        "target_pointer_generation": pointer["generation"],
                    },
                    bind_cutover=True,
                )

    def activate_product_run(
        self,
        migration_id: str,
        *,
        store: CandidateAuthorityStore,
    ) -> dict[str, Any]:
        self._require_product_store(store)
        with store.serialization():
            state = self.read_state(migration_id)
            self._require_target_store(state, store)
            self._require_persisted_bindings(state)
            pointer = store.read_pointer(state["target_pointer_key"])
            self._require_target_pointer(state, pointer)
            if pointer["generation"] != state["target_pointer_generation"]:
                fail("MIGRATION_ACTIVATION_POINTER_DRIFT")
            return self._transition(
                migration_id,
                expected_state="CUTOVER_COMMITTED",
                next_state="POST_CUTOVER_ACTIVE",
                event_payload={"legacy_writer_reactivated": False},
            )

    def abort_before_cutover(self, migration_id: str) -> dict[str, Any]:
        state = self.read_state(migration_id)
        if state["state"] not in PRE_CUTOVER_STATES:
            fail("MIGRATION_ABORT_TOO_LATE")
        return self._transition(
            migration_id,
            expected_state=state["state"],
            next_state="ABORTED",
            event_payload={
                "target_visible": False,
                "legacy_writer_reactivated": False,
            },
        )

    def record_forward_recovery(
        self,
        migration_id: str,
        *,
        store: CandidateAuthorityStore,
        pointer_before: dict[str, Any],
        pointer_after: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_product_store(store)
        with store.serialization():
            state = self.read_state(migration_id)
            self._require_target_store(state, store)
            self._require_persisted_bindings(state)
            if state["state"] not in {
                "CUTOVER_COMMITTED",
                "POST_CUTOVER_ACTIVE",
            }:
                fail("MIGRATION_RECOVERY_NOT_ACTIVE")
            self._require_target_pointer(state, pointer_before)
            self._require_target_pointer(state, pointer_after)
            if (
                pointer_before["generation"]
                != state["target_pointer_generation"]
                or pointer_after["generation"] != pointer_before["generation"] + 1
            ):
                fail("MIGRATION_FORWARD_RECOVERY_INVALID")
            persisted = store.read_pointer(state["target_pointer_key"])
            if canonical_bytes(persisted) != canonical_bytes(pointer_after):
                fail("MIGRATION_FORWARD_RECOVERY_NOT_PERSISTED")
            return self._transition(
                migration_id,
                expected_state=state["state"],
                next_state=state["state"],
                event_payload={
                    "pointer_generation_before": pointer_before["generation"],
                    "pointer_generation_after": pointer_after["generation"],
                    "legacy_writer_reactivated": False,
                },
                updates={"target_pointer_generation": pointer_after["generation"]},
                event_name="FORWARD_RECOVERY_RECORDED",
                advance_pointer_binding=(
                    pointer_before["generation"],
                    pointer_after["generation"],
                ),
            )

    def read_state(self, migration_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.database_path) as connection:
            self._verify_control_schema(connection)
            row = self._row(connection, migration_id)
        return self._state_from_row(migration_id, row)

    def events(self, migration_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
            self._verify_control_schema(connection)
            rows = connection.execute(
                "SELECT event_sequence, event, payload_json "
                "FROM migration_events WHERE migration_id = ? "
                "ORDER BY event_sequence",
                (migration_id,),
            ).fetchall()
        return [
            {"sequence": row[0], "event": row[1], "payload": _decode(row[2])}
            for row in rows
        ]

    def schema_objects(self) -> list[str]:
        with sqlite3.connect(self.database_path) as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            ]

    def authority_binding_counts(self) -> dict[str, int]:
        with sqlite3.connect(self.database_path) as connection:
            self._verify_control_schema(connection)
            return {
                table: connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
                for table in (
                    "authority_project_bindings",
                    "authority_pointer_bindings",
                )
            }


class ProductCandidateAuthorityAccess:
    """Expose product reads only after one persisted cutover is active."""

    __slots__ = ("__controller", "__store", "__migration_id")

    def __init__(
        self,
        *,
        controller: NamespaceMigrationController,
        store: CandidateAuthorityStore,
        migration_id: str,
    ) -> None:
        state = controller.read_state(migration_id)
        controller._require_target_store(state, store)
        self.__controller = controller
        self.__store = store
        self.__migration_id = migration_id

    def _require_active(self) -> dict[str, Any]:
        state = self.__controller.read_state(self.__migration_id)
        self.__controller._require_target_store(state, self.__store)
        if state["state"] != "POST_CUTOVER_ACTIVE":
            fail("PRODUCT_NAMESPACE_NOT_ACTIVE")
        self.__controller._require_persisted_bindings(state)
        return state

    def _current_pointer(self, state: dict[str, Any]) -> dict[str, Any]:
        pointer = self.__store.read_pointer(state["target_pointer_key"])
        self.__controller._require_target_pointer(state, pointer)
        if pointer["generation"] != state["target_pointer_generation"]:
            fail("PRODUCT_NAMESPACE_POINTER_DRIFT")
        return pointer

    def read_pointer(self, logical_pointer_key: str) -> dict[str, Any]:
        with self.__store.serialization():
            state = self._require_active()
            if logical_pointer_key != state["target_pointer_key"]:
                fail("MIGRATION_TARGET_POINTER_MISMATCH")
            return deepcopy(self._current_pointer(state))

    def read_candidate(self, ref: dict[str, Any]) -> dict[str, Any]:
        if (
            ref.get("contract_version")
            != PRODUCT_AUTHORITY_PROFILE.contract_version
            or ref.get("access") != PRODUCT_AUTHORITY_PROFILE.candidate_access
        ):
            fail("MIGRATION_MIXED_NAMESPACE_REF")
        with self.__store.serialization():
            state = self._require_active()
            pointer = self._current_pointer(state)
            current_ref = pointer["current_candidate_version_ref"]
            seen: set[bytes] = set()
            while current_ref is not None:
                encoded = canonical_bytes(current_ref)
                if encoded in seen:
                    fail("MIGRATION_CANDIDATE_LINEAGE_CYCLE")
                seen.add(encoded)
                candidate = self.__store.read_candidate(current_ref)
                if canonical_bytes(ref) == encoded:
                    return candidate
                current_ref = candidate["payload"]["parent_candidate_version_ref"]
        fail("MIGRATION_CANDIDATE_OUTSIDE_TARGET_LINEAGE")
