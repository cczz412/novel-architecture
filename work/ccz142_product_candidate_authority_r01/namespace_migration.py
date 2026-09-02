"""Persisted cutover gates without becoming a second candidate-object writer."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import stat
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    FIXTURE_ACCESS,
    FIXTURE_POINTER_NAMESPACE,
    PRODUCT_AUTHORITY_PROFILE,
    PRODUCT_READ_ONLY_ACCESS,
    canonical_bytes,
    record_ref,
    sha256_value,
)
from work.ccz142_candidate_authority_r01.candidate_authority import (  # noqa: E402
    CandidateAuthorityStore,
)

CONTROL_SCHEMA_VERSION = "ccz142-product-namespace-migration-r01"
SOURCE_KEYS = {
    "source_namespace",
    "candidate_access",
    "upstream_access",
    "project_scope_id",
    "source_head_sha256",
    "synthetic_fixture",
}
PRE_CUTOVER_STATES = {
    "DISCOVERED",
    "SOURCE_VERIFIED",
    "TARGET_STAGED",
    "SHADOW_VERIFIED",
}
PRODUCT_ACTIVE_STATES = {"CUTOVER_COMMITTED", "POST_CUTOVER_ACTIVE"}


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
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("PRAGMA journal_mode=TRUNCATE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS migration_state ("
                "migration_id TEXT PRIMARY KEY, project_scope_id TEXT NOT NULL, "
                "source_json BLOB NOT NULL, source_hash TEXT NOT NULL, "
                "state TEXT NOT NULL, target_root_result_json BLOB, "
                "target_pointer_key TEXT, target_pointer_generation INTEGER, "
                "shadow_semantic_hash TEXT, event_sequence INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS migration_events ("
                "migration_id TEXT NOT NULL, event_sequence INTEGER NOT NULL, "
                "event TEXT NOT NULL, payload_json BLOB NOT NULL, "
                "PRIMARY KEY(migration_id, event_sequence))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata ("
                "key TEXT PRIMARY KEY, value BLOB NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)",
                ("schema_version", sqlite3.Binary(CONTROL_SCHEMA_VERSION.encode())),
            )
            connection.commit()

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
            "target_pointer_generation, shadow_semantic_hash, event_sequence "
            "FROM migration_state WHERE migration_id = ?",
            (migration_id,),
        ).fetchone()
        if row is None:
            fail("MIGRATION_NOT_FOUND")
        return row

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

    def discover(self, migration_id: str, source: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(migration_id, str) or not migration_id:
            fail("MIGRATION_ID_INVALID")
        if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
            fail("MIGRATION_SOURCE_SHAPE_INVALID")
        if (
            source["source_namespace"] != FIXTURE_POINTER_NAMESPACE
            or source["candidate_access"] != FIXTURE_ACCESS
            or not isinstance(source["project_scope_id"], str)
            or not source["project_scope_id"]
            or not isinstance(source["source_head_sha256"], str)
            or len(source["source_head_sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in source["source_head_sha256"]
            )
            or not isinstance(source["synthetic_fixture"], bool)
        ):
            fail("MIGRATION_SOURCE_IDENTITY_INVALID")
        source_hash = sha256_value(source)
        rejected = (
            source["synthetic_fixture"]
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
    ) -> dict[str, Any]:
        descriptor, connection = self._open_locked()
        try:
            row = self._row(connection, migration_id)
            if row[3] != expected_state:
                fail("MIGRATION_STATE_CONFLICT", f"{row[3]} != {expected_state}")
            sequence = row[8] + 1
            assignments = ["state = ?", "event_sequence = ?"]
            values: list[Any] = [next_state, sequence]
            for key, value in (updates or {}).items():
                if key not in {
                    "target_root_result_json",
                    "target_pointer_key",
                    "target_pointer_generation",
                    "shadow_semantic_hash",
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
                event=next_state,
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

    def verify_source(self, migration_id: str, *, observed_source_hash: str) -> dict[str, Any]:
        state = self.read_state(migration_id)
        if observed_source_hash != state["source_hash"]:
            fail("MIGRATION_SOURCE_HASH_MISMATCH")
        return self._transition(
            migration_id,
            expected_state="DISCOVERED",
            next_state="SOURCE_VERIFIED",
            event_payload={"source_hash": observed_source_hash},
        )

    def stage_target(
        self,
        migration_id: str,
        *,
        store: CandidateAuthorityStore,
        root_result: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.read_state(migration_id)
        if (
            store.authority_profile.identity != PRODUCT_AUTHORITY_PROFILE.identity
            or store.project_scope_id != state["project_scope_id"]
        ):
            fail("MIGRATION_TARGET_PROFILE_MISMATCH")
        pointer = store.read_pointer(root_result["logical_pointer_key"])
        candidate = store.read_candidate(root_result["candidate_version_ref"])
        if (
            pointer["pointer_namespace"]
            != PRODUCT_AUTHORITY_PROFILE.pointer_namespace
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
            },
        )

    def shadow_verify(
        self,
        migration_id: str,
        *,
        source_semantic_hash: str,
        target_semantic_hash: str,
    ) -> dict[str, Any]:
        if source_semantic_hash != target_semantic_hash:
            fail("MIGRATION_SHADOW_DIVERGENCE")
        return self._transition(
            migration_id,
            expected_state="TARGET_STAGED",
            next_state="SHADOW_VERIFIED",
            event_payload={"semantic_hash": source_semantic_hash},
            updates={"shadow_semantic_hash": source_semantic_hash},
        )

    def cutover(
        self,
        migration_id: str,
        *,
        store: CandidateAuthorityStore,
    ) -> dict[str, Any]:
        state = self.read_state(migration_id)
        pointer = store.read_pointer(state["target_pointer_key"])
        if (
            pointer["pointer_namespace"]
            != PRODUCT_AUTHORITY_PROFILE.pointer_namespace
            or pointer["generation"] != state["target_pointer_generation"]
        ):
            fail("MIGRATION_CUTOVER_CAS_MISMATCH")
        return self._transition(
            migration_id,
            expected_state="SHADOW_VERIFIED",
            next_state="CUTOVER_COMMITTED",
            event_payload={
                "target_pointer_key": pointer["logical_pointer_key"],
                "target_pointer_generation": pointer["generation"],
            },
        )

    def activate_product_run(self, migration_id: str) -> dict[str, Any]:
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
        state = self.read_state(migration_id)
        if state["state"] != "POST_CUTOVER_ACTIVE":
            fail("MIGRATION_RECOVERY_NOT_ACTIVE")
        if (
            pointer_before["pointer_namespace"]
            != PRODUCT_AUTHORITY_PROFILE.pointer_namespace
            or pointer_after["pointer_namespace"]
            != PRODUCT_AUTHORITY_PROFILE.pointer_namespace
            or pointer_before["logical_pointer_key"]
            != pointer_after["logical_pointer_key"]
            or pointer_after["generation"] <= pointer_before["generation"]
        ):
            fail("MIGRATION_FORWARD_RECOVERY_INVALID")
        persisted = store.read_pointer(pointer_after["logical_pointer_key"])
        if canonical_bytes(persisted) != canonical_bytes(pointer_after):
            fail("MIGRATION_FORWARD_RECOVERY_NOT_PERSISTED")
        return self._transition(
            migration_id,
            expected_state="POST_CUTOVER_ACTIVE",
            next_state="POST_CUTOVER_ACTIVE",
            event_payload={
                "pointer_generation_before": pointer_before["generation"],
                "pointer_generation_after": pointer_after["generation"],
                "legacy_writer_reactivated": False,
            },
            updates={"target_pointer_generation": pointer_after["generation"]},
        )

    def read_state(self, migration_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.database_path) as connection:
            row = self._row(connection, migration_id)
        return {
            "migration_id": migration_id,
            "project_scope_id": row[0],
            "source": _decode(row[1]),
            "source_hash": row[2],
            "state": row[3],
            "target_root_result": (
                None if row[4] is None else _decode(row[4])
            ),
            "target_pointer_key": row[5],
            "target_pointer_generation": row[6],
            "shadow_semantic_hash": row[7],
            "event_sequence": row[8],
        }

    def events(self, migration_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.database_path) as connection:
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
        if store.authority_profile.identity != PRODUCT_AUTHORITY_PROFILE.identity:
            fail("MIGRATION_TARGET_PROFILE_MISMATCH")
        self.__controller = controller
        self.__store = store
        self.__migration_id = migration_id

    def _require_active(self) -> None:
        state = self.__controller.read_state(self.__migration_id)
        if state["state"] != "POST_CUTOVER_ACTIVE":
            fail("PRODUCT_NAMESPACE_NOT_ACTIVE")

    def read_pointer(self, logical_pointer_key: str) -> dict[str, Any]:
        self._require_active()
        pointer = self.__store.read_pointer(logical_pointer_key)
        if pointer["pointer_namespace"] != PRODUCT_AUTHORITY_PROFILE.pointer_namespace:
            fail("MIGRATION_MIXED_NAMESPACE_REF")
        return deepcopy(pointer)

    def read_candidate(self, ref: dict[str, Any]) -> dict[str, Any]:
        self._require_active()
        if (
            ref.get("contract_version")
            != PRODUCT_AUTHORITY_PROFILE.contract_version
            or ref.get("access") != PRODUCT_AUTHORITY_PROFILE.candidate_access
        ):
            fail("MIGRATION_MIXED_NAMESPACE_REF")
        return self.__store.read_candidate(ref)
