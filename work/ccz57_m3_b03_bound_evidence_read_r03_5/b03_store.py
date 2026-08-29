"""Crash-recoverable B-03 fixture store with physically split plaintext."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterator

from b03_contracts import (
    REPOSITORY_ROOT,
    TOMBSTONE_FIELDS,
    canonical_bytes,
    fail,
    guard_write_path,
    record_ref,
    validate_record,
    validate_retention_record,
    validate_tombstone,
)

_SLICE_TYPE = "M3_AUTHORIZED_SOURCE_SLICE"
_RETENTION_TYPE = "M3_SOURCE_SLICE_RETENTION_RECEIPT"
_DIRECT_APPEND_FORBIDDEN = {_SLICE_TYPE, _RETENTION_TYPE}


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _json_blob(value: Any) -> bytes:
    return canonical_bytes(value)


def _from_blob(value: bytes | str) -> Any:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return json.loads(value)


class B03FixtureStore:
    """SQLite state with immutable metadata and plaintext in separate files."""

    def __init__(
        self,
        root: Path,
        *,
        commit_capability: object,
        read_capability: object,
        record_validators: dict[
            str, Callable[[dict[str, Any], list[dict[str, Any]]], None]
        ],
        slice_validator: Callable[
            [dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]], None
        ],
        retention_planner: Callable[
            [
                dict[str, Any],
                list[dict[str, Any]],
                list[dict[str, Any]],
                str,
            ],
            dict[str, Any],
        ],
    ) -> None:
        self.root = self._admit_root(root)
        self.state_path = self.root / "immutable-state.sqlite3"
        self._content_path = self.root / "expiring-content.sqlite3"
        self.events: list[str] = []
        self.before_publish_hook: Any = None
        self.before_retention_commit_hook: Any = None
        self.before_transaction_commit_hook: Any = None
        self.__commit_capability = commit_capability
        self.__read_capability = read_capability
        self.__record_validators = dict(record_validators)
        self.__slice_validator = slice_validator
        self.__retention_planner = retention_planner
        self._reject_external_aliases(self.state_path)
        self._reject_external_aliases(self._content_path)
        self._connection = sqlite3.connect(
            self.state_path,
            isolation_level=None,
            timeout=30,
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA main.journal_mode=DELETE")
        self._connection.execute("PRAGMA main.synchronous=FULL")
        self._connection.execute("PRAGMA main.secure_delete=ON")
        self._connection.execute(
            "ATTACH DATABASE ? AS content", (str(self._content_path),)
        )
        self._connection.execute("PRAGMA content.journal_mode=DELETE")
        self._connection.execute("PRAGMA content.synchronous=FULL")
        self._connection.execute("PRAGMA content.secure_delete=ON")
        self._initialize_schema()

    @staticmethod
    def _reject_external_aliases(path: Path) -> None:
        for candidate in (
            path,
            Path(f"{path}-journal"),
            Path(f"{path}-wal"),
            Path(f"{path}-shm"),
        ):
            if candidate.is_symlink():
                fail("B03_WRITE_SET_VIOLATION", f"symlink:{candidate}")
            if candidate.exists() and (
                not candidate.is_file() or candidate.stat().st_nlink != 1
            ):
                fail("B03_WRITE_SET_VIOLATION", f"external-alias:{candidate}")

    @classmethod
    def _admit_root(cls, root: Path) -> Path:
        requested = Path(root).expanduser().absolute()
        for component in (requested, *requested.parents):
            if component.exists() and component.is_symlink():
                fail("B03_WRITE_SET_VIOLATION", f"symlink:{component}")
        resolved = requested.resolve(strict=False)
        module_root = Path(__file__).resolve().parent
        if not _inside(resolved, module_root) or resolved == module_root:
            fail("B03_WRITE_SET_VIOLATION", str(resolved))
        relative = resolved.relative_to(REPOSITORY_ROOT).as_posix() + "/"
        guard_write_path(relative)
        resolved.mkdir(parents=True, exist_ok=True)
        if resolved.is_symlink() or resolved.resolve() != resolved:
            fail("B03_WRITE_SET_VIOLATION", f"symlink:{resolved}")
        return resolved

    def _initialize_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS records (
                record_key TEXT PRIMARY KEY,
                record_json BLOB NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS slice_cores (
                record_hash TEXT PRIMARY KEY,
                record_ref_json BLOB NOT NULL,
                core_json BLOB NOT NULL,
                content_sha256 TEXT NOT NULL,
                content_utf8_bytes INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tombstones (
                record_hash TEXT PRIMARY KEY,
                tombstone_json BLOB NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS trusted_times (
                monotonic_sequence INTEGER PRIMARY KEY,
                record_json BLOB NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS content.slice_content (
                record_hash TEXT PRIMARY KEY,
                content BLOB NOT NULL
            )
            """,
        )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in statements:
                self._connection.execute(statement)
            self._connection.execute("COMMIT")
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise

    def _transaction(self) -> Iterator[sqlite3.Connection]:
        class Transaction:
            def __init__(self, store: B03FixtureStore) -> None:
                self.store = store

            def __enter__(self) -> sqlite3.Connection:
                self.store._connection.execute("BEGIN IMMEDIATE")
                return self.store._connection

            def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
                if exc_type is not None:
                    self.store._connection.execute("ROLLBACK")
                    return False
                try:
                    hook = self.store.before_transaction_commit_hook
                    if hook is not None:
                        hook()
                    self.store._connection.execute("COMMIT")
                except BaseException:
                    self.store._connection.execute("ROLLBACK")
                    raise
                return False

        return Transaction(self)

    @staticmethod
    def _key(record: dict[str, Any]) -> str:
        return ":".join(
            (record["record_type"], record["record_id"], str(record["record_version"]))
        )

    @staticmethod
    def _record_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT record_json FROM records ORDER BY record_key"
        ).fetchall()
        return [_from_blob(row[0]) for row in rows]

    @staticmethod
    def _trusted_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT record_json FROM trusted_times ORDER BY monotonic_sequence"
        ).fetchall()
        return [_from_blob(row[0]) for row in rows]

    @staticmethod
    def _slice_core_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT record_ref_json, core_json, content_sha256, content_utf8_bytes
            FROM slice_cores ORDER BY record_hash
            """
        ).fetchall()
        return [
            {
                "record_ref": _from_blob(row[0]),
                "core": _from_blob(row[1]),
                "content_sha256": row[2],
                "content_utf8_bytes": row[3],
            }
            for row in rows
        ]

    def records(self) -> list[dict[str, Any]]:
        return deepcopy(self._record_rows(self._connection))

    def trusted_times(self) -> list[dict[str, Any]]:
        return deepcopy(self._trusted_rows(self._connection))

    def slice_cores(self) -> list[dict[str, Any]]:
        return deepcopy(self._slice_core_rows(self._connection))

    def admit_trusted_times(
        self,
        records: list[dict[str, Any]],
        *,
        chain_validator: Callable[[list[dict[str, Any]]], Any],
        inactive_selector: Callable[
            [dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]], bool
        ]
        | None = None,
    ) -> None:
        chain_validator(records)
        supplied = {item["payload"]["monotonic_sequence"]: item for item in records}
        purged = 0
        with self._transaction() as connection:
            existing = {
                item["payload"]["monotonic_sequence"]: item
                for item in self._trusted_rows(connection)
            }
            for sequence, item in existing.items():
                if sequence not in supplied:
                    fail("B03_TRUSTED_TIME_STALE")
                if canonical_bytes(item) != canonical_bytes(supplied[sequence]):
                    fail("B03_TRUSTED_TIME_HEAD_AMBIGUOUS")
            if existing and max(supplied) < max(existing):
                fail("B03_TRUSTED_TIME_STALE")
            for sequence, item in supplied.items():
                if sequence in existing:
                    continue
                connection.execute(
                    "INSERT INTO trusted_times(monotonic_sequence, record_json) VALUES (?, ?)",
                    (sequence, _json_blob(item)),
                )
            chain_validator(self._trusted_rows(connection))
            if inactive_selector is not None:
                for core in list(self._slice_core_rows(connection)):
                    current_records = self._record_rows(connection)
                    current_times = self._trusted_rows(connection)
                    if not inactive_selector(
                        core["core"], current_records, current_times
                    ):
                        continue
                    slice_record = self._materialize(connection, core["record_ref"])
                    entry = self.__retention_planner(
                        slice_record,
                        current_records,
                        current_times,
                        "UNREADABLE",
                    )
                    self._apply_retention(connection, entry)
                    purged += 1
        if purged:
            self.events.extend(
                ["source_slice_content_purged", "content_residue_scan_passed"]
            )

    @staticmethod
    def _insert_record(
        connection: sqlite3.Connection,
        record: dict[str, Any],
        *,
        require_new: bool = False,
    ) -> bool:
        key = B03FixtureStore._key(record)
        row = connection.execute(
            "SELECT record_json FROM records WHERE record_key = ?", (key,)
        ).fetchone()
        if row is not None:
            if canonical_bytes(_from_blob(row[0])) != canonical_bytes(record):
                fail("B03_IMMUTABLE_ALREADY_EXISTS", key)
            if require_new:
                fail("B03_IMMUTABLE_ALREADY_EXISTS", key)
            return False
        connection.execute(
            "INSERT INTO records(record_key, record_json) VALUES (?, ?)",
            (key, _json_blob(record)),
        )
        return True

    def append_record(
        self,
        record: dict[str, Any],
        *,
        expected_type: str,
        commit_capability: object | None = None,
    ) -> dict[str, Any]:
        if commit_capability is not self.__commit_capability:
            fail("B03_COMMIT_CAPABILITY_REQUIRED")
        validate_record(record)
        if (
            record["record_type"] != expected_type
            or expected_type in _DIRECT_APPEND_FORBIDDEN
        ):
            fail("B03_WRITER_SCOPE_ESCAPE", record["record_type"])
        with self._transaction() as connection:
            validator = self.__record_validators.get(expected_type)
            if validator is None:
                fail("B03_WRITER_SCOPE_ESCAPE", expected_type)
            validator(record, self._record_rows(connection))
            inserted = self._insert_record(connection, record)
        if inserted:
            self.events.append("immutable_record_atomic_write")
        return record_ref(record)

    @staticmethod
    def _tombstone_row(
        connection: sqlite3.Connection, record_hash: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT tombstone_json FROM tombstones WHERE record_hash = ?",
            (record_hash,),
        ).fetchone()
        return None if row is None else _from_blob(row[0])

    def is_tombstoned(self, slice_ref: dict[str, Any]) -> bool:
        return (
            self._tombstone_row(self._connection, slice_ref["record_hash"]) is not None
        )

    @staticmethod
    def _materialize(
        connection: sqlite3.Connection, slice_ref: dict[str, Any]
    ) -> dict[str, Any]:
        record_hash = slice_ref["record_hash"]
        if B03FixtureStore._tombstone_row(connection, record_hash) is not None:
            fail("TOMBSTONED_CONTENT_UNAVAILABLE")
        core_row = connection.execute(
            """
            SELECT record_ref_json, core_json, content_sha256, content_utf8_bytes
            FROM slice_cores WHERE record_hash = ?
            """,
            (record_hash,),
        ).fetchone()
        content_row = connection.execute(
            "SELECT content FROM content.slice_content WHERE record_hash = ?",
            (record_hash,),
        ).fetchone()
        if core_row is None or content_row is None:
            fail("B03_REFERENCE_INTEGRITY_FAILED", "source slice")
        stored_ref = _from_blob(core_row[0])
        if stored_ref != slice_ref:
            fail("B03_REFERENCE_INTEGRITY_FAILED", "source slice ref")
        content = bytes(content_row[0])
        if (
            hashlib.sha256(content).hexdigest() != core_row[2]
            or len(content) != core_row[3]
        ):
            fail("B03_SLICE_INTEGRITY_MISMATCH")
        record = _from_blob(core_row[1])
        record["payload"]["content"] = content.decode("utf-8")
        validate_record(record)
        if record_ref(record) != slice_ref:
            fail("B03_SLICE_INTEGRITY_MISMATCH", "record ref")
        return record

    def existing_slice_core(self, slice_ref: dict[str, Any]) -> dict[str, Any] | None:
        row = self._connection.execute(
            """
            SELECT record_ref_json, core_json, content_sha256, content_utf8_bytes
            FROM slice_cores WHERE record_hash = ?
            """,
            (slice_ref["record_hash"],),
        ).fetchone()
        if row is None:
            return None
        return {
            "record_ref": _from_blob(row[0]),
            "core": _from_blob(row[1]),
            "content_sha256": row[2],
            "content_utf8_bytes": row[3],
        }

    def publish_slice(
        self,
        record: dict[str, Any],
        *,
        commit_capability: object | None = None,
    ) -> dict[str, Any]:
        if commit_capability is not self.__commit_capability:
            fail("B03_COMMIT_CAPABILITY_REQUIRED")
        validate_record(record)
        if record["record_type"] != _SLICE_TYPE:
            fail("B03_WRITER_SCOPE_ESCAPE", record["record_type"])
        ref = record_ref(record)
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT 1 FROM slice_cores WHERE record_hash = ?",
                (ref["record_hash"],),
            ).fetchone()
            if existing is not None:
                reopened = self._materialize(connection, ref)
                if canonical_bytes(reopened) != canonical_bytes(record):
                    fail("B03_IMMUTABLE_ALREADY_EXISTS", ref["record_hash"])
                return ref
            if self._tombstone_row(connection, ref["record_hash"]) is not None:
                fail("B03_RETENTION_ALREADY_FINAL")
            self.__slice_validator(
                record, self._record_rows(connection), self._trusted_rows(connection)
            )
            content = record["payload"]["content"].encode("utf-8")
            if (
                hashlib.sha256(content).hexdigest()
                != record["payload"]["content_sha256"]
                or len(content) != record["payload"]["content_utf8_bytes"]
            ):
                fail("B03_SLICE_INTEGRITY_MISMATCH")
            core = deepcopy(record)
            del core["payload"]["content"]
            connection.execute(
                """
                INSERT INTO slice_cores(
                    record_hash, record_ref_json, core_json,
                    content_sha256, content_utf8_bytes
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ref["record_hash"],
                    _json_blob(ref),
                    _json_blob(core),
                    record["payload"]["content_sha256"],
                    record["payload"]["content_utf8_bytes"],
                ),
            )
            connection.execute(
                "INSERT INTO content.slice_content(record_hash, content) VALUES (?, ?)",
                (ref["record_hash"], content),
            )
            reopened = self._materialize(connection, ref)
            if canonical_bytes(reopened) != canonical_bytes(record):
                fail("B03_TRANSACTION_READBACK_INVALID", "source slice")
        self.events.extend(
            ["immutable_record_atomic_write", "source_slice_content_published"]
        )
        return ref

    def read_slice_content(
        self,
        slice_ref: dict[str, Any],
        *,
        read_capability: object | None = None,
    ) -> str:
        if read_capability is not self.__read_capability:
            return "B03_SOURCE_CONTENT_ACCESS_DENIED"
        with self._transaction() as connection:
            record = self._materialize(connection, slice_ref)
            self.__slice_validator(
                record,
                self._record_rows(connection),
                self._trusted_rows(connection),
            )
            content = record["payload"]["content"]
        self.events.append("synthetic_bound_evidence_read")
        return content

    @staticmethod
    def tombstone_for_slice(slice_record: dict[str, Any]) -> dict[str, Any]:
        payload = slice_record["payload"]
        tombstone = {
            "authorized_source_slice_ref": record_ref(slice_record),
            "evidence_binding_hash": payload["evidence_binding"]["binding_hash"],
            "evidence_sha256": payload["evidence_binding"]["evidence_sha256"],
            "content_bytes_retained": False,
            "storage_state": "TOMBSTONED_CONTENT_UNAVAILABLE",
        }
        if sorted(tombstone, key=lambda item: item.encode("utf-8")) != TOMBSTONE_FIELDS:
            fail("B03_TOMBSTONE_FIELD_VIOLATION")
        validate_tombstone(tombstone)
        return tombstone

    @staticmethod
    def _apply_retention(connection: sqlite3.Connection, entry: dict[str, Any]) -> None:
        slice_ref = entry["slice_ref"]
        tombstone = entry["tombstone"]
        receipt = entry["receipt"]
        slice_record = B03FixtureStore._materialize(connection, slice_ref)
        expected = B03FixtureStore.tombstone_for_slice(slice_record)
        if canonical_bytes(expected) != canonical_bytes(tombstone):
            fail("B03_RETENTION_INVALID", "tombstone drift")
        validate_retention_record(receipt, tombstone=tombstone)
        if receipt["payload"]["authorized_source_slice_ref"] != slice_ref:
            fail("B03_RETENTION_INVALID", "slice ref")
        B03FixtureStore._insert_record(connection, receipt, require_new=True)
        connection.execute(
            "INSERT INTO tombstones(record_hash, tombstone_json) VALUES (?, ?)",
            (slice_ref["record_hash"], _json_blob(tombstone)),
        )
        deleted_core = connection.execute(
            "DELETE FROM slice_cores WHERE record_hash = ?",
            (slice_ref["record_hash"],),
        ).rowcount
        deleted_content = connection.execute(
            "DELETE FROM content.slice_content WHERE record_hash = ?",
            (slice_ref["record_hash"],),
        ).rowcount
        if deleted_core != 1 or deleted_content != 1:
            fail("B03_RETENTION_PROOF_FAILED", "missing content or core")
        if (
            connection.execute(
                "SELECT 1 FROM slice_cores WHERE record_hash = ?",
                (slice_ref["record_hash"],),
            ).fetchone()
            is not None
        ):
            fail("B03_RETENTION_PROOF_FAILED", "core residue")
        if (
            connection.execute(
                "SELECT 1 FROM content.slice_content WHERE record_hash = ?",
                (slice_ref["record_hash"],),
            ).fetchone()
            is not None
        ):
            fail("B03_RETENTION_PROOF_FAILED", "content residue")

    def commit_retention(
        self,
        slice_ref: dict[str, Any],
        *,
        event: str,
        commit_capability: object | None = None,
    ) -> dict[str, Any]:
        if commit_capability is not self.__commit_capability:
            fail("B03_COMMIT_CAPABILITY_REQUIRED")
        with self._transaction() as connection:
            if self.before_retention_commit_hook is not None:
                self.before_retention_commit_hook()
            slice_record = self._materialize(connection, slice_ref)
            entry = self.__retention_planner(
                slice_record,
                self._record_rows(connection),
                self._trusted_rows(connection),
                event,
            )
            self._apply_retention(connection, entry)
        self.events.extend(
            [
                "immutable_record_atomic_write",
                "source_slice_content_purged",
                "content_residue_scan_passed",
            ]
        )
        return record_ref(entry["receipt"])

    def append_record_with_retentions(
        self,
        record: dict[str, Any],
        *,
        event: str,
        expected_type: str,
        commit_capability: object | None = None,
        retention_selector: Callable[
            [dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]], bool
        ],
    ) -> dict[str, Any]:
        if commit_capability is not self.__commit_capability:
            fail("B03_COMMIT_CAPABILITY_REQUIRED")
        validate_record(record)
        if (
            record["record_type"] != expected_type
            or expected_type in _DIRECT_APPEND_FORBIDDEN
        ):
            fail("B03_WRITER_SCOPE_ESCAPE", record["record_type"])
        with self._transaction() as connection:
            validator = self.__record_validators.get(expected_type)
            if validator is None:
                fail("B03_WRITER_SCOPE_ESCAPE", expected_type)
            validator(record, self._record_rows(connection))
            inserted = self._insert_record(connection, record)
            purged = 0
            current_records = self._record_rows(connection)
            current_times = self._trusted_rows(connection)
            for core in list(self._slice_core_rows(connection)):
                slice_record = self._materialize(connection, core["record_ref"])
                if not retention_selector(slice_record, current_records, current_times):
                    continue
                entry = self.__retention_planner(
                    slice_record,
                    current_records,
                    current_times,
                    event,
                )
                self._apply_retention(connection, entry)
                purged += 1
        if inserted:
            self.events.append("immutable_record_atomic_write")
        if purged:
            self.events.extend(
                ["source_slice_content_purged", "content_residue_scan_passed"]
            )
        return record_ref(record)

    def snapshot(self) -> dict[str, str]:
        state = {
            "records": self._record_rows(self._connection),
            "slice_cores": self._slice_core_rows(self._connection),
            "tombstones": [
                _from_blob(row[0])
                for row in self._connection.execute(
                    "SELECT tombstone_json FROM tombstones ORDER BY record_hash"
                ).fetchall()
            ],
            "content_hashes": [
                {
                    "record_hash": row[0],
                    "content_sha256": hashlib.sha256(bytes(row[1])).hexdigest(),
                }
                for row in self._connection.execute(
                    "SELECT record_hash, content FROM content.slice_content ORDER BY record_hash"
                ).fetchall()
            ],
        }
        if not any(state.values()):
            return {}
        return {"logical_state": hashlib.sha256(canonical_bytes(state)).hexdigest()}

    def state_counts(self) -> dict[str, int]:
        return {
            "records": self._connection.execute(
                "SELECT COUNT(*) FROM records"
            ).fetchone()[0],
            "source_slices": self._connection.execute(
                "SELECT COUNT(*) FROM slice_cores"
            ).fetchone()[0],
            "tombstones": self._connection.execute(
                "SELECT COUNT(*) FROM tombstones"
            ).fetchone()[0],
        }

    def plaintext_present(self, slice_ref: dict[str, Any]) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM content.slice_content WHERE record_hash = ?",
                (slice_ref["record_hash"],),
            ).fetchone()
            is not None
        )

    def _state_contains_for_test(self, text: str) -> bool:
        return text.encode("utf-8") in self.state_path.read_bytes()

    def _content_file_contains_for_test(self, text: str) -> bool:
        return text.encode("utf-8") in self._content_path.read_bytes()

    def tombstone(self, slice_ref: dict[str, Any]) -> dict[str, Any] | None:
        value = self._tombstone_row(self._connection, slice_ref["record_hash"])
        return None if value is None else deepcopy(value)

    def storage_residue(self) -> list[str]:
        allowed = {self.state_path.name, self._content_path.name}
        return sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_file() and path.name not in allowed
        )

    def close(self) -> None:
        self._connection.close()
