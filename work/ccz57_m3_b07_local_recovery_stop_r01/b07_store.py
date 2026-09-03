"""SQLite-backed B-07 RunController sharing B-06's transaction domain."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
for candidate in (REPOSITORY_ROOT, B06_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    record_ref,
    sha256_value,
)
from work.ccz57_m3_b08_segment_terminal_r01.b08_contracts import (  # noqa: E402
    B08ContractError,
    terminal_component_observation,
    validate_terminal_record,
)
from b06_contracts import validate_merge_receipt  # noqa: E402

from b07_contracts import (  # noqa: E402
    NONTERMINAL_STATUSES,
    STOP_RECEIPT_TYPE,
    B07ContractError,
    build_current_run_state,
    build_debug_record,
    build_resume_plan,
    build_stop_receipt,
    fail,
    rehash_state,
    stop_receipt_ref,
    validate_authority_snapshot,
    validate_current_run_state,
    validate_debug_record,
    validate_pending_local_action,
    validate_stop_receipt,
    validate_stop_receipt_for_state,
    TERMINAL_COMPONENT_KIND,
    validate_terminal_transition_source,
)

AuthorityReader = Callable[[], dict[str, Any]]
Clock = Callable[[], str]

_REQUIRED_B06_TABLES = {"candidate_versions", "current_pointers", "merge_receipts"}
_B07_TABLES = {
    "b07_current_run_states",
    "b07_stop_receipts",
    "b07_internal_debug_records",
    "b07_run_command_dedupe",
}


def _decode(raw: Any, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(bytes(raw).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        fail(code, str(error))
    if not isinstance(value, dict):
        fail(code)
    return value


class B07RunStore:
    """The only writer for CurrentRunState and StopReceipt."""

    __slots__ = ("root", "failure_point", "events", "_database_path", "_clock")

    def __init__(
        self,
        root: Path,
        *,
        clock: Clock,
        failure_point: str | None = None,
    ) -> None:
        self.root = self._guard_storage_path(root)
        self.failure_point = failure_point
        self.events: list[dict[str, str]] = []
        self._database_path = self.root / "b06-commit-core.sqlite3"
        self._clock = clock

    @staticmethod
    def _guard_storage_path(path: Path) -> Path:
        resolved = path.resolve(strict=False)
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
            fail("B07_WRITE_SET_ESCAPE", str(path))
        return resolved

    def initialize_schema(self) -> None:
        if not self._database_path.is_file():
            fail("B07_B06_TRANSACTION_DOMAIN_MISSING")
        with sqlite3.connect(self._database_path) as connection:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if not _REQUIRED_B06_TABLES <= existing:
                fail("B07_B06_TRANSACTION_DOMAIN_MISSING")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS b07_stop_receipts ("
                "project_scope_id TEXT NOT NULL, stop_receipt_id TEXT NOT NULL, "
                "run_id TEXT NOT NULL, stop_operation_id TEXT NOT NULL, "
                "request_hash TEXT NOT NULL, receipt_json BLOB NOT NULL, "
                "PRIMARY KEY(project_scope_id, stop_receipt_id), "
                "UNIQUE(project_scope_id, run_id), "
                "UNIQUE(project_scope_id, stop_operation_id))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS b07_current_run_states ("
                "project_scope_id TEXT NOT NULL, run_id TEXT NOT NULL, "
                "logical_run_key TEXT NOT NULL, logical_run_generation INTEGER NOT NULL, "
                "run_epoch INTEGER NOT NULL, state_revision INTEGER NOT NULL, "
                "status TEXT NOT NULL, stop_receipt_id TEXT, state_json BLOB NOT NULL, "
                "PRIMARY KEY(project_scope_id, run_id), "
                "UNIQUE(project_scope_id, logical_run_key, logical_run_generation), "
                "FOREIGN KEY(project_scope_id, stop_receipt_id) "
                "REFERENCES b07_stop_receipts(project_scope_id, stop_receipt_id), "
                "CHECK((status = 'STOPPED' AND stop_receipt_id IS NOT NULL) "
                "OR (status != 'STOPPED' AND stop_receipt_id IS NULL)))"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS b07_one_nonterminal_run "
                "ON b07_current_run_states(project_scope_id, logical_run_key) "
                "WHERE status NOT IN ('SUCCEEDED', 'STOPPED')"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS b07_internal_debug_records ("
                "project_scope_id TEXT NOT NULL, debug_record_id TEXT NOT NULL, "
                "run_id TEXT NOT NULL, record_json BLOB NOT NULL, "
                "PRIMARY KEY(project_scope_id, debug_record_id))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS b07_run_command_dedupe ("
                "project_scope_id TEXT NOT NULL, source_run_id TEXT NOT NULL, "
                "command_kind TEXT NOT NULL, operation_id TEXT NOT NULL, "
                "request_hash TEXT NOT NULL, result_run_id TEXT NOT NULL, "
                "result_epoch INTEGER NOT NULL, result_revision INTEGER NOT NULL, "
                "result_ref_json BLOB, "
                "PRIMARY KEY(project_scope_id, source_run_id, command_kind, operation_id))"
            )
            connection.commit()

    def _inject(self, point: str) -> None:
        if self.failure_point == point:
            fail("B07_SIMULATED_TRANSACTION_FAILURE", point)

    def _authority(self, reader: AuthorityReader) -> dict[str, Any]:
        try:
            snapshot = reader()
        except Exception as error:
            fail("B07_AUTHORITY_READER_UNAVAILABLE", str(error))
        validate_authority_snapshot(snapshot)
        return deepcopy(snapshot)

    @staticmethod
    def _exact_b08_terminal(
        connection: sqlite3.Connection,
        *,
        state: dict[str, Any],
        observation: Any,
        source_state_revision: int,
        source_state_hash: str | None,
        target_status: str | None,
    ) -> dict[str, Any]:
        validate_terminal_transition_source(state, observation)
        locator = observation["component_artifact_ref"][
            "workspace_relative_locator"
        ]
        record_hash = locator.rsplit("/", 1)[-1][:-5]
        try:
            row = connection.execute(
                "SELECT terminalization_key, project_scope_id, logical_run_key, "
                "run_id, logical_run_generation, run_epoch, operation_id, "
                "call_request_hash, record_id, record_hash, record_json "
                "FROM b08_segment_terminal_receipts "
                "WHERE project_scope_id = ? AND record_hash = ?",
                (state["project_scope_id"], record_hash),
            ).fetchone()
        except sqlite3.OperationalError as error:
            fail("B07_TERMINAL_OBSERVATION_NOT_FOUND", str(error))
        if row is None:
            fail("B07_TERMINAL_OBSERVATION_NOT_FOUND")
        record = _decode(row[10], code="B07_TERMINAL_RECORD_INVALID")
        try:
            validate_terminal_record(record)
            exact_observation = terminal_component_observation(record)
        except B08ContractError as error:
            fail("B07_TERMINAL_RECORD_INVALID", str(error))
        if canonical_bytes(exact_observation) != canonical_bytes(observation):
            fail("B07_TERMINAL_OBSERVATION_MISMATCH")
        payload = record["payload"]
        run = payload["run_binding"]
        expected_row = (
            payload["terminalization_key"],
            run["project_scope_id"],
            run["logical_run_key"],
            run["run_id"],
            run["logical_run_generation"],
            run["run_epoch"],
            payload["operation_id"],
            row[7],
            record["record_id"],
            record["record_hash"],
        )
        expected_operation_request_hash = sha256_value(
            {
                "call_request_hash": row[7],
                "authority_snapshot_hash": payload["authority_snapshot_hash"],
            }
        )
        if (
            tuple(row[:10]) != expected_row
            or payload["operation_request_hash"]
            != expected_operation_request_hash
        ):
            fail("B07_TERMINAL_RECORD_INVALID")
        if (
            run["project_scope_id"] != state["project_scope_id"]
            or run["logical_run_key"] != state["logical_run_key"]
            or run["run_id"] != state["run_id"]
            or run["logical_run_generation"]
            != state["logical_run_generation"]
            or run["run_epoch"] != state["run_epoch"]
            or run["finalized_from_state_revision"] != source_state_revision
            or (
                source_state_hash is not None
                and run["finalized_from_state_hash"] != source_state_hash
            )
        ):
            fail("B07_TERMINAL_OBSERVATION_SCOPE_MISMATCH")
        delivery = payload["classification_binding"]["terminal_delivery"]
        if (
            target_status == "SUCCEEDED"
            and delivery not in {"COMPLETE", "EMPTY_VALID"}
        ) or (
            target_status == "STOPPED" and delivery not in {"PARTIAL", "BLOCKED"}
        ):
            fail("B07_TERMINAL_DELIVERY_MISMATCH")
        return record

    @staticmethod
    def _request_hash(value: dict[str, Any]) -> str:
        return sha256_value(value)

    @staticmethod
    def _state_row(
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        run_id: str,
    ) -> tuple[dict[str, Any], bytes]:
        row = connection.execute(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND run_id = ?",
            (project_scope_id, run_id),
        ).fetchone()
        if row is None:
            fail("B07_RUN_NOT_FOUND")
        raw = bytes(row[0])
        state = _decode(raw, code="B07_STORED_RUN_STATE_INVALID")
        validate_current_run_state(state)
        return state, raw

    @staticmethod
    def _assert_fence(
        state: dict[str, Any],
        *,
        expected_run_epoch: int,
        expected_state_revision: int,
    ) -> None:
        if (
            state["run_epoch"] != expected_run_epoch
            or state["state_revision"] != expected_state_revision
        ):
            fail("B07_STALE_RUN_FENCE")

    @staticmethod
    def _dedupe_lookup(
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        source_run_id: str,
        command_kind: str,
        operation_id: str,
        request_hash: str,
    ) -> tuple[str, int, int, dict[str, Any] | None] | None:
        row = connection.execute(
            "SELECT request_hash, result_run_id, result_epoch, result_revision, "
            "result_ref_json FROM b07_run_command_dedupe "
            "WHERE project_scope_id = ? AND source_run_id = ? "
            "AND command_kind = ? AND operation_id = ?",
            (project_scope_id, source_run_id, command_kind, operation_id),
        ).fetchone()
        if row is None:
            return None
        if row[0] != request_hash:
            fail("B07_IDEMPOTENCY_CONFLICT")
        result_ref = (
            None
            if row[4] is None
            else _decode(row[4], code="B07_STORED_DEDUPE_RESULT_INVALID")
        )
        return row[1], row[2], row[3], result_ref

    @staticmethod
    def _dedupe_insert(
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        source_run_id: str,
        command_kind: str,
        operation_id: str,
        request_hash: str,
        result_state: dict[str, Any],
        result_ref: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO b07_run_command_dedupe("
            "project_scope_id, source_run_id, command_kind, operation_id, "
            "request_hash, result_run_id, result_epoch, result_revision, result_ref_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_scope_id,
                source_run_id,
                command_kind,
                operation_id,
                request_hash,
                result_state["run_id"],
                result_state["run_epoch"],
                result_state["state_revision"],
                None
                if result_ref is None
                else sqlite3.Binary(canonical_bytes(result_ref)),
            ),
        )

    @staticmethod
    def _insert_state(connection: sqlite3.Connection, state: dict[str, Any]) -> None:
        validate_current_run_state(state)
        connection.execute(
            "INSERT INTO b07_current_run_states("
            "project_scope_id, run_id, logical_run_key, logical_run_generation, "
            "run_epoch, state_revision, status, stop_receipt_id, state_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                state["project_scope_id"],
                state["run_id"],
                state["logical_run_key"],
                state["logical_run_generation"],
                state["run_epoch"],
                state["state_revision"],
                state["status"],
                None,
                sqlite3.Binary(canonical_bytes(state)),
            ),
        )

    @staticmethod
    def _update_state(
        connection: sqlite3.Connection,
        *,
        before: dict[str, Any],
        after: dict[str, Any],
        stop_receipt_id: str | None = None,
    ) -> None:
        validate_current_run_state(after)
        cursor = connection.execute(
            "UPDATE b07_current_run_states SET run_epoch = ?, state_revision = ?, "
            "status = ?, stop_receipt_id = ?, state_json = ? "
            "WHERE project_scope_id = ? AND run_id = ? "
            "AND run_epoch = ? AND state_revision = ? AND state_json = ?",
            (
                after["run_epoch"],
                after["state_revision"],
                after["status"],
                stop_receipt_id,
                sqlite3.Binary(canonical_bytes(after)),
                before["project_scope_id"],
                before["run_id"],
                before["run_epoch"],
                before["state_revision"],
                sqlite3.Binary(canonical_bytes(before)),
            ),
        )
        if cursor.rowcount != 1:
            fail("B07_STATE_CAS_CONFLICT")

    def read_state(self, project_scope_id: str, run_id: str) -> dict[str, Any]:
        with sqlite3.connect(self._database_path) as connection:
            state, _ = self._state_row(
                connection, project_scope_id=project_scope_id, run_id=run_id
            )
        return state

    def read_stop_receipt(self, project_scope_id: str, run_id: str) -> dict[str, Any]:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT receipt_json FROM b07_stop_receipts "
                "WHERE project_scope_id = ? AND run_id = ?",
                (project_scope_id, run_id),
            ).fetchone()
        if row is None:
            fail("B07_STOP_RECEIPT_NOT_FOUND")
        receipt = _decode(row[0], code="B07_STORED_STOP_RECEIPT_INVALID")
        validate_stop_receipt(receipt)
        return receipt

    def read_debug_records(
        self, project_scope_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT record_json FROM b07_internal_debug_records "
                "WHERE project_scope_id = ? AND run_id = ? ORDER BY debug_record_id",
                (project_scope_id, run_id),
            ).fetchall()
        records = [
            _decode(row[0], code="B07_STORED_DEBUG_RECORD_INVALID") for row in rows
        ]
        for record in records:
            validate_debug_record(record)
        return records

    def visible_counts(self) -> dict[str, int]:
        with sqlite3.connect(self._database_path) as connection:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in sorted(_B07_TABLES - {"b07_run_command_dedupe"})
            }

    def schema_objects(self) -> list[str]:
        with sqlite3.connect(self._database_path) as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            ]

    def open_run(
        self,
        *,
        project_scope_id: str,
        logical_run_key: str,
        run_id: str,
        run_kind: str,
        operation_id: str,
        authority_reader: AuthorityReader,
    ) -> dict[str, Any]:
        request_hash = self._request_hash(
            {
                "kind": "B07_OPEN_V1",
                "project_scope_id": project_scope_id,
                "logical_run_key": logical_run_key,
                "run_id": run_id,
                "run_kind": run_kind,
                "operation_id": operation_id,
            }
        )
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                replay = self._dedupe_lookup(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="OPEN",
                    operation_id=operation_id,
                    request_hash=request_hash,
                )
                if replay is not None:
                    state, _ = self._state_row(
                        connection,
                        project_scope_id=project_scope_id,
                        run_id=replay[0],
                    )
                    connection.rollback()
                    return state
                prior = connection.execute(
                    "SELECT COUNT(*) FROM b07_current_run_states "
                    "WHERE project_scope_id = ? AND logical_run_key = ?",
                    (project_scope_id, logical_run_key),
                ).fetchone()[0]
                if prior:
                    fail("B07_REOPEN_REQUIRED")
                authority = self._authority(authority_reader)
                if not authority["budget_allows_continue"]:
                    fail("B07_OPEN_BUDGET_DENIED")
                if not authority["permission_active"]:
                    fail("B07_OPEN_PERMISSION_DENIED")
                created_at = self._clock()
                state = build_current_run_state(
                    project_scope_id=project_scope_id,
                    logical_run_key=logical_run_key,
                    run_id=run_id,
                    logical_run_generation=1,
                    run_kind=run_kind,
                    authority_snapshot=authority,
                    created_at=created_at,
                )
                self._insert_state(connection, state)
                self._dedupe_insert(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="OPEN",
                    operation_id=operation_id,
                    request_hash=request_hash,
                    result_state=state,
                )
                connection.commit()
                self.events.append({"event": "run_opened", "run_id": run_id})
                return state
            except Exception:
                connection.rollback()
                raise

    def advance(
        self,
        *,
        project_scope_id: str,
        run_id: str,
        operation_id: str,
        expected_run_epoch: int,
        expected_state_revision: int,
        target_status: str,
        target_phase: str,
        wait_kind: str | None,
        authority_reader: AuthorityReader,
        component_observation: dict[str, Any] | None = None,
        pending_local_action: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if pending_local_action is not None:
            validate_pending_local_action(pending_local_action)
        request_hash = self._request_hash(
            {
                "kind": "B07_ADVANCE_V1",
                "project_scope_id": project_scope_id,
                "run_id": run_id,
                "operation_id": operation_id,
                "expected_run_epoch": expected_run_epoch,
                "expected_state_revision": expected_state_revision,
                "target_status": target_status,
                "target_phase": target_phase,
                "wait_kind": wait_kind,
                "component_observation": component_observation,
                "pending_local_action": pending_local_action,
            }
        )
        allowed = {
            "ACTIVE": {"ACTIVE", "WAITING_LOCAL", "B06_OUTCOME_PENDING", "SUCCEEDED"},
            "WAITING_LOCAL": {"ACTIVE", "B06_OUTCOME_PENDING"},
        }
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                replay = self._dedupe_lookup(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="ADVANCE",
                    operation_id=operation_id,
                    request_hash=request_hash,
                )
                if replay is not None:
                    state, _ = self._state_row(
                        connection,
                        project_scope_id=project_scope_id,
                        run_id=replay[0],
                    )
                    connection.rollback()
                    return state
                state, _ = self._state_row(
                    connection, project_scope_id=project_scope_id, run_id=run_id
                )
                self._assert_fence(
                    state,
                    expected_run_epoch=expected_run_epoch,
                    expected_state_revision=expected_state_revision,
                )
                if target_status not in allowed.get(state["status"], set()):
                    fail("B07_TRANSITION_INVALID")
                authority = self._authority(authority_reader)
                if canonical_bytes(authority) != canonical_bytes(
                    state["authority_snapshot"]
                ):
                    fail("B07_AUTHORITY_DRIFT")
                if target_status == "SUCCEEDED":
                    self._exact_b08_terminal(
                        connection,
                        state=state,
                        observation=component_observation,
                        source_state_revision=state["state_revision"],
                        source_state_hash=state["state_hash"],
                        target_status="SUCCEEDED",
                    )
                elif (
                    isinstance(component_observation, dict)
                    and component_observation.get("component_kind")
                    == TERMINAL_COMPONENT_KIND
                ):
                    self._exact_b08_terminal(
                        connection,
                        state=state,
                        observation=component_observation,
                        source_state_revision=state["state_revision"],
                        source_state_hash=state["state_hash"],
                        target_status=None,
                    )
                updated = deepcopy(state)
                updated["state_revision"] += 1
                updated["status"] = target_status
                updated["phase"] = (
                    "DONE" if target_status == "SUCCEEDED" else target_phase
                )
                updated["wait_kind"] = wait_kind
                updated["last_component_observation"] = deepcopy(component_observation)
                updated["pending_local_action"] = deepcopy(pending_local_action)
                updated["updated_at"] = self._clock()
                updated = rehash_state(updated)
                self._update_state(connection, before=state, after=updated)
                self._dedupe_insert(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="ADVANCE",
                    operation_id=operation_id,
                    request_hash=request_hash,
                    result_state=updated,
                )
                connection.commit()
                self.events.append({"event": "run_advanced", "run_id": run_id})
                return updated
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _resume_disposition(stop_reason_code: str) -> str:
        if stop_reason_code in {
            "LOCAL_STORAGE_INTEGRITY_FAILURE",
            "UNRECOVERABLE_COMPONENT_FAILURE",
            "LOCAL_AUTHORITY_MISSING",
        }:
            return "MAINTENANCE_REQUIRED"
        if stop_reason_code == "ROUTE_STOP":
            return "DO_NOT_RESUME"
        return "REOPEN_NEW_RUN"

    def _stop_in_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        state: dict[str, Any],
        operation_id: str,
        request_hash: str,
        stop_reason_code: str,
        stop_class: str,
        stop_source: str,
        authority: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self._exact_b08_terminal(
            connection,
            state=state,
            observation=state["last_component_observation"],
            source_state_revision=state["state_revision"] - 1,
            source_state_hash=None,
            target_status="STOPPED",
        )
        created_at = self._clock()
        payload = {
            "project_scope_id": state["project_scope_id"],
            "logical_run_key": state["logical_run_key"],
            "run_id": state["run_id"],
            "logical_run_generation": state["logical_run_generation"],
            "run_epoch": state["run_epoch"],
            "stopped_from_state_revision": state["state_revision"],
            "stop_operation_id": operation_id,
            "stop_request_hash": request_hash,
            "stop_reason_code": stop_reason_code,
            "stop_class": stop_class,
            "stop_source": stop_source,
            "authority_snapshot": deepcopy(authority),
            "last_durable_phase": state["phase"],
            "last_component_observation": deepcopy(state["last_component_observation"]),
            "pending_local_action": deepcopy(state["pending_local_action"]),
            "retainable_candidate_version_ref": deepcopy(
                authority["observed_candidate_version_ref"]
            ),
            "resume_disposition": self._resume_disposition(stop_reason_code),
            "terminalization_required": True,
            "created_at": created_at,
        }
        receipt = build_stop_receipt(payload=payload, created_at=created_at)
        receipt_ref = stop_receipt_ref(receipt)
        connection.execute(
            "INSERT INTO b07_stop_receipts("
            "project_scope_id, stop_receipt_id, run_id, stop_operation_id, "
            "request_hash, receipt_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                state["project_scope_id"],
                receipt["record_id"],
                state["run_id"],
                operation_id,
                request_hash,
                sqlite3.Binary(canonical_bytes(receipt)),
            ),
        )
        self._inject("after_stop_receipt_insert")
        stopped = deepcopy(state)
        stopped["state_revision"] += 1
        stopped["status"] = "STOPPED"
        stopped["phase"] = "DONE"
        stopped["wait_kind"] = None
        stopped["authority_snapshot"] = deepcopy(authority)
        stopped["pending_local_action"] = None
        stopped["stop_receipt_ref"] = receipt_ref
        stopped["updated_at"] = created_at
        stopped = rehash_state(stopped)
        self._update_state(
            connection,
            before=state,
            after=stopped,
            stop_receipt_id=receipt["record_id"],
        )
        self._inject("after_stopped_state_update")
        return stopped, receipt

    def stop(
        self,
        *,
        project_scope_id: str,
        run_id: str,
        operation_id: str,
        expected_run_epoch: int,
        expected_state_revision: int,
        stop_reason_code: str,
        stop_class: str,
        stop_source: str,
        authority_reader: AuthorityReader,
    ) -> dict[str, Any]:
        request_hash = self._request_hash(
            {
                "kind": "B07_STOP_V1",
                "project_scope_id": project_scope_id,
                "run_id": run_id,
                "operation_id": operation_id,
                "expected_run_epoch": expected_run_epoch,
                "expected_state_revision": expected_state_revision,
                "stop_reason_code": stop_reason_code,
                "stop_class": stop_class,
                "stop_source": stop_source,
            }
        )
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                replay = self._dedupe_lookup(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="STOP",
                    operation_id=operation_id,
                    request_hash=request_hash,
                )
                if replay is not None:
                    receipt = self._stop_receipt_from_ref(connection, replay[3])
                    connection.rollback()
                    return receipt
                state, _ = self._state_row(
                    connection, project_scope_id=project_scope_id, run_id=run_id
                )
                self._assert_fence(
                    state,
                    expected_run_epoch=expected_run_epoch,
                    expected_state_revision=expected_state_revision,
                )
                if state["status"] not in NONTERMINAL_STATUSES:
                    fail("B07_STOP_ALREADY_FINALIZED")
                authority = self._authority(authority_reader)
                if canonical_bytes(authority) != canonical_bytes(
                    state["authority_snapshot"]
                ):
                    fail("B07_AUTHORITY_DRIFT")
                stopped, receipt = self._stop_in_transaction(
                    connection,
                    state=state,
                    operation_id=operation_id,
                    request_hash=request_hash,
                    stop_reason_code=stop_reason_code,
                    stop_class=stop_class,
                    stop_source=stop_source,
                    authority=authority,
                )
                self._dedupe_insert(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="STOP",
                    operation_id=operation_id,
                    request_hash=request_hash,
                    result_state=stopped,
                    result_ref=stop_receipt_ref(receipt),
                )
                self._inject("before_stop_commit")
                connection.commit()
                self.events.append({"event": "run_stopped", "run_id": run_id})
                return receipt
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _stop_receipt_from_ref(
        connection: sqlite3.Connection, ref: dict[str, Any] | None
    ) -> dict[str, Any]:
        if ref is None or ref.get("record_type") != STOP_RECEIPT_TYPE:
            fail("B07_STORED_DEDUPE_RESULT_INVALID")
        row = connection.execute(
            "SELECT receipt_json FROM b07_stop_receipts "
            "WHERE project_scope_id = ? AND stop_receipt_id = ?",
            (None, ref["record_id"]),
        ).fetchone()
        if row is None:
            row = connection.execute(
                "SELECT receipt_json FROM b07_stop_receipts WHERE stop_receipt_id = ?",
                (ref["record_id"],),
            ).fetchone()
        if row is None:
            fail("B07_STORED_DEDUPE_RESULT_INVALID")
        receipt = _decode(row[0], code="B07_STORED_STOP_RECEIPT_INVALID")
        validate_stop_receipt(receipt)
        if canonical_bytes(record_ref(receipt)) != canonical_bytes(ref):
            fail("B07_STORED_DEDUPE_RESULT_INVALID")
        return receipt

    def append_debug(
        self,
        *,
        project_scope_id: str,
        run_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                state, _ = self._state_row(
                    connection, project_scope_id=project_scope_id, run_id=run_id
                )
                complete_payload = deepcopy(payload)
                complete_payload.update(
                    {
                        "project_scope_id": project_scope_id,
                        "run_id": run_id,
                        "run_epoch": state["run_epoch"],
                        "state_revision": state["state_revision"],
                        "created_at": self._clock(),
                    }
                )
                complete_payload["debug_payload_bytes"] = len(
                    canonical_bytes(
                        {
                            key: value
                            for key, value in complete_payload.items()
                            if key != "debug_payload_bytes"
                        }
                    )
                )
                record = build_debug_record(
                    payload=complete_payload,
                    created_at=complete_payload["created_at"],
                )
                existing = connection.execute(
                    "SELECT record_json FROM b07_internal_debug_records "
                    "WHERE project_scope_id = ? AND run_id = ?",
                    (project_scope_id, run_id),
                ).fetchall()
                total_bytes = sum(len(bytes(row[0])) for row in existing)
                if (
                    len(existing) >= 32
                    or total_bytes + len(canonical_bytes(record)) > 65536
                ):
                    fail("B07_DEBUG_QUOTA_EXCEEDED")
                connection.execute(
                    "INSERT INTO b07_internal_debug_records("
                    "project_scope_id, debug_record_id, run_id, record_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        project_scope_id,
                        record["record_id"],
                        run_id,
                        sqlite3.Binary(canonical_bytes(record)),
                    ),
                )
                self._inject("debug_before_commit")
                connection.commit()
                self.events.append({"event": "debug_written", "run_id": run_id})
                return record
            except Exception:
                connection.rollback()
                raise

    def derive_resume_plan(
        self,
        *,
        project_scope_id: str,
        run_id: str,
        authority_reader: AuthorityReader,
        b06_outcome: str = "NOT_APPLICABLE",
    ) -> dict[str, Any]:
        state = self.read_state(project_scope_id, run_id)
        authority = self._authority(authority_reader)
        preconditions: list[str] = []
        if state["status"] == "STOPPED":
            receipt = self.read_stop_receipt(project_scope_id, run_id)
            validate_stop_receipt_for_state(state, receipt)
            disposition = receipt["payload"]["resume_disposition"]
        elif state["status"] == "SUCCEEDED":
            disposition = "DO_NOT_RESUME"
        elif state["status"] == "B06_OUTCOME_PENDING":
            disposition = "RECONCILE_B06_THEN_CONTINUE"
        elif canonical_bytes(authority) != canonical_bytes(state["authority_snapshot"]):
            disposition = "DO_NOT_RESUME"
            preconditions.append("AUTHORITY_DRIFT_REQUIRES_STOP_OR_NEW_RUN")
        else:
            disposition = "CONTINUE_SAME_RUN"
        return build_resume_plan(
            state=state,
            authority_snapshot=authority,
            b06_outcome=b06_outcome,
            disposition=disposition,
            next_phase=state["phase"],
            preconditions=preconditions,
        )

    def resume(
        self,
        *,
        project_scope_id: str,
        run_id: str,
        operation_id: str,
        expected_run_epoch: int,
        expected_state_revision: int,
        authority_reader: AuthorityReader,
    ) -> dict[str, Any]:
        request_hash = self._request_hash(
            {
                "kind": "B07_RESUME_V1",
                "project_scope_id": project_scope_id,
                "run_id": run_id,
                "operation_id": operation_id,
                "expected_run_epoch": expected_run_epoch,
                "expected_state_revision": expected_state_revision,
            }
        )
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                replay = self._dedupe_lookup(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="RESUME",
                    operation_id=operation_id,
                    request_hash=request_hash,
                )
                if replay is not None:
                    state, _ = self._state_row(
                        connection,
                        project_scope_id=project_scope_id,
                        run_id=replay[0],
                    )
                    connection.rollback()
                    return state
                state, _ = self._state_row(
                    connection, project_scope_id=project_scope_id, run_id=run_id
                )
                self._assert_fence(
                    state,
                    expected_run_epoch=expected_run_epoch,
                    expected_state_revision=expected_state_revision,
                )
                if state["status"] not in {"ACTIVE", "WAITING_LOCAL"}:
                    fail("B07_RESUME_NOT_ALLOWED")
                authority = self._authority(authority_reader)
                if canonical_bytes(authority) != canonical_bytes(
                    state["authority_snapshot"]
                ):
                    fail("B07_AUTHORITY_DRIFT")
                resumed = deepcopy(state)
                resumed["run_epoch"] += 1
                resumed["state_revision"] += 1
                resumed["status"] = "ACTIVE"
                resumed["wait_kind"] = None
                resumed["updated_at"] = self._clock()
                resumed = rehash_state(resumed)
                self._update_state(connection, before=state, after=resumed)
                self._dedupe_insert(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="RESUME",
                    operation_id=operation_id,
                    request_hash=request_hash,
                    result_state=resumed,
                )
                connection.commit()
                self.events.append({"event": "run_resumed", "run_id": run_id})
                return resumed
            except Exception:
                connection.rollback()
                raise

    def reopen(
        self,
        *,
        project_scope_id: str,
        source_run_id: str,
        new_run_id: str,
        operation_id: str,
        authority_reader: AuthorityReader,
    ) -> dict[str, Any]:
        request_hash = self._request_hash(
            {
                "kind": "B07_REOPEN_V1",
                "project_scope_id": project_scope_id,
                "source_run_id": source_run_id,
                "new_run_id": new_run_id,
                "operation_id": operation_id,
            }
        )
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                replay = self._dedupe_lookup(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=source_run_id,
                    command_kind="REOPEN",
                    operation_id=operation_id,
                    request_hash=request_hash,
                )
                if replay is not None:
                    state, _ = self._state_row(
                        connection,
                        project_scope_id=project_scope_id,
                        run_id=replay[0],
                    )
                    connection.rollback()
                    return state
                source, _ = self._state_row(
                    connection,
                    project_scope_id=project_scope_id,
                    run_id=source_run_id,
                )
                if source["status"] != "STOPPED":
                    fail("B07_REOPEN_SOURCE_NOT_STOPPED")
                receipt = self._stop_receipt_from_ref(
                    connection, source["stop_receipt_ref"]
                )
                validate_stop_receipt_for_state(source, receipt)
                if receipt["payload"]["resume_disposition"] != "REOPEN_NEW_RUN":
                    fail("B07_REOPEN_REQUIRES_MAINTENANCE_OR_NEW_ROUTE")
                authority = self._authority(authority_reader)
                if not authority["budget_allows_continue"]:
                    fail("B07_REOPEN_BUDGET_DENIED")
                if not authority["permission_active"]:
                    fail("B07_REOPEN_PERMISSION_DENIED")
                created_at = self._clock()
                reopened = build_current_run_state(
                    project_scope_id=project_scope_id,
                    logical_run_key=source["logical_run_key"],
                    run_id=new_run_id,
                    logical_run_generation=source["logical_run_generation"] + 1,
                    run_kind=source["run_kind"],
                    authority_snapshot=authority,
                    created_at=created_at,
                    reopened_from_stop_receipt_ref=source["stop_receipt_ref"],
                )
                self._insert_state(connection, reopened)
                self._dedupe_insert(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=source_run_id,
                    command_kind="REOPEN",
                    operation_id=operation_id,
                    request_hash=request_hash,
                    result_state=reopened,
                    result_ref=source["stop_receipt_ref"],
                )
                connection.commit()
                self.events.append({"event": "run_reopened", "run_id": new_run_id})
                return reopened
            except Exception:
                connection.rollback()
                raise

    def classify_b06_outcome(
        self, connection: sqlite3.Connection, state: dict[str, Any]
    ) -> str:
        pending = state["pending_local_action"]
        if state["status"] != "B06_OUTCOME_PENDING" or pending is None:
            return "NOT_APPLICABLE"
        receipt_row = connection.execute(
            "SELECT request_hash, receipt_json FROM merge_receipts "
            "WHERE project_scope_id = ? AND operation_id = ?",
            (state["project_scope_id"], pending["operation_id"]),
        ).fetchone()
        pointer_row = connection.execute(
            "SELECT project_scope_id, pointer_json FROM current_pointers "
            "WHERE logical_pointer_key = ?",
            (pending["expected_pointer_key"],),
        ).fetchone()
        if pointer_row is None or pointer_row[0] != state["project_scope_id"]:
            return "INTEGRITY_FAILURE"
        pointer = _decode(pointer_row[1], code="B07_B06_POINTER_INVALID")
        if receipt_row is None:
            if pointer.get("generation") == pending[
                "expected_pointer_generation"
            ] and canonical_bytes(
                pointer.get("current_candidate_version_ref")
            ) == canonical_bytes(pending["expected_candidate_version_ref"]):
                return "NOT_PUBLISHED"
            return "CONFLICT"
        if receipt_row[0] != pending["request_hash"]:
            return "CONFLICT"
        try:
            receipt = _decode(receipt_row[1], code="B07_B06_RECEIPT_INVALID")
            validate_merge_receipt(receipt)
            child_ref = receipt["payload"]["child_candidate_version_ref"]
            child_row = connection.execute(
                "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
                (sha256_value(child_ref),),
            ).fetchone()
            if child_row is None:
                return "INTEGRITY_FAILURE"
            child = _decode(child_row[0], code="B07_B06_CHILD_INVALID")
            if (
                canonical_bytes(record_ref(child)) != canonical_bytes(child_ref)
                or canonical_bytes(pointer.get("current_candidate_version_ref"))
                != canonical_bytes(child_ref)
                or pointer.get("generation")
                != receipt["payload"]["pointer_generation_after"]
            ):
                return "INTEGRITY_FAILURE"
        except (B07ContractError, ValueError):
            return "INTEGRITY_FAILURE"
        return "COMMITTED"

    def reconcile_b06(
        self,
        *,
        project_scope_id: str,
        run_id: str,
        operation_id: str,
        expected_run_epoch: int,
        expected_state_revision: int,
        authority_reader: AuthorityReader,
        committed_status: str = "ACTIVE",
        committed_phase: str = "FINALIZING",
    ) -> dict[str, Any]:
        request_hash = self._request_hash(
            {
                "kind": "B07_RECONCILE_B06_V1",
                "project_scope_id": project_scope_id,
                "run_id": run_id,
                "operation_id": operation_id,
                "expected_run_epoch": expected_run_epoch,
                "expected_state_revision": expected_state_revision,
                "committed_status": committed_status,
                "committed_phase": committed_phase,
            }
        )
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                replay = self._dedupe_lookup(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="RECONCILE_B06",
                    operation_id=operation_id,
                    request_hash=request_hash,
                )
                if replay is not None:
                    state, _ = self._state_row(
                        connection,
                        project_scope_id=project_scope_id,
                        run_id=replay[0],
                    )
                    connection.rollback()
                    return state
                state, _ = self._state_row(
                    connection, project_scope_id=project_scope_id, run_id=run_id
                )
                self._assert_fence(
                    state,
                    expected_run_epoch=expected_run_epoch,
                    expected_state_revision=expected_state_revision,
                )
                outcome = self.classify_b06_outcome(connection, state)
                authority = self._authority(authority_reader)
                if outcome == "COMMITTED":
                    updated = deepcopy(state)
                    updated["state_revision"] += 1
                    updated["status"] = committed_status
                    updated["phase"] = (
                        "DONE" if committed_status == "SUCCEEDED" else committed_phase
                    )
                    updated["wait_kind"] = None
                    updated["authority_snapshot"] = authority
                    updated["pending_local_action"] = None
                    updated["updated_at"] = self._clock()
                    updated = rehash_state(updated)
                    self._update_state(connection, before=state, after=updated)
                    result_ref = None
                else:
                    reason = {
                        "NOT_PUBLISHED": "B06_NOT_PUBLISHED",
                        "CONFLICT": "B06_POINTER_CONFLICT",
                        "INTEGRITY_FAILURE": "LOCAL_STORAGE_INTEGRITY_FAILURE",
                    }.get(outcome)
                    if reason is None:
                        fail("B07_B06_OUTCOME_INVALID", outcome)
                    updated, receipt = self._stop_in_transaction(
                        connection,
                        state=state,
                        operation_id=f"{operation_id}:stop",
                        request_hash=request_hash,
                        stop_reason_code=reason,
                        stop_class="B06_LOCAL_OUTCOME",
                        stop_source="B07_RECONCILER",
                        authority=authority,
                    )
                    result_ref = stop_receipt_ref(receipt)
                self._dedupe_insert(
                    connection,
                    project_scope_id=project_scope_id,
                    source_run_id=run_id,
                    command_kind="RECONCILE_B06",
                    operation_id=operation_id,
                    request_hash=request_hash,
                    result_state=updated,
                    result_ref=result_ref,
                )
                connection.commit()
                self.events.append(
                    {"event": f"b06_{outcome.lower()}", "run_id": run_id}
                )
                return updated
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def run_fence_reader(view: Any, context: dict[str, Any]) -> None:
        fence = context.get("run_fence")
        if not isinstance(fence, dict):
            fail("B07_B06_FENCE_CONTEXT_INVALID")
        row = view.fetchone(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND run_id = ?",
            (fence.get("project_scope_id"), fence.get("run_id")),
        )
        if row is None:
            fail("B07_B06_FENCE_STALE")
        state = _decode(row[0], code="B07_STORED_RUN_STATE_INVALID")
        validate_current_run_state(state)
        pending = state["pending_local_action"]
        if (
            state["run_epoch"] != fence.get("expected_run_epoch")
            or state["state_revision"] != fence.get("expected_state_revision")
            or state["status"] != "B06_OUTCOME_PENDING"
            or pending is None
            or pending["operation_id"] != context.get("operation_id")
            or pending["request_hash"] != context.get("request_hash")
            or pending["expected_pointer_key"]
            != state["authority_snapshot"]["candidate_pointer_key"]
        ):
            fail("B07_B06_FENCE_STALE")
