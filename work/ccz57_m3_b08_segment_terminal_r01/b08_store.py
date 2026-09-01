"""One SQLite writer plus two non-persistent B-08 read views."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Protocol

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    sha256_value,
)

from b08_contracts import (  # noqa: E402
    ADAPTER_READY_VIEW_TYPE,
    EXACT_CURRENT_VIEW_TYPE,
    TERMINAL_RECEIPT_TYPE,
    WRITE_SET_PREFIX,
    B08ContractError,
    build_terminal_record,
    fail,
    terminal_component_observation,
    terminal_record_ref,
    terminalization_key,
    validate_adapter_ready_view,
    validate_authority_snapshot,
    validate_exact_current_view,
    validate_terminal_record,
)

Clock = Callable[[], str]

_REQUIRED_SHARED_TABLES = {
    "candidate_versions",
    "current_pointers",
    "merge_receipts",
    "b07_current_run_states",
}
_B08_TABLE = "b08_segment_terminal_receipts"


class TerminalAuthorityReader(Protocol):
    """Product-owned reader; callers cannot replace it on publish or view calls."""

    def read_for_run(
        self,
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        run_id: str,
    ) -> dict[str, Any]: ...

    def read_current(
        self,
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        logical_run_key: str,
    ) -> dict[str, Any]: ...


def _decode(raw: Any, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(bytes(raw).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        fail(code, str(error))
    if not isinstance(value, dict):
        fail(code)
    return value


class B08SegmentTerminalStore:
    """The only B-08 writer; the constructor owns the authority reader."""

    __slots__ = (
        "root",
        "failure_point",
        "events",
        "_database_path",
        "_clock",
        "_authority_reader",
    )

    def __init__(
        self,
        root: Path,
        *,
        clock: Clock,
        authority_reader: TerminalAuthorityReader,
        failure_point: str | None = None,
    ) -> None:
        self.root = self._guard_storage_path(root)
        self.failure_point = failure_point
        self.events: list[dict[str, str]] = []
        self._database_path = self.root / "b06-commit-core.sqlite3"
        self._clock = clock
        self._authority_reader = authority_reader

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
            fail("B08_WRITE_SET_ESCAPE", str(path))
        return resolved

    def initialize_schema(self) -> None:
        if not self._database_path.is_file():
            fail("B08_SHARED_TRANSACTION_DOMAIN_MISSING")
        with sqlite3.connect(self._database_path) as connection:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if not _REQUIRED_SHARED_TABLES <= existing:
                fail("B08_SHARED_TRANSACTION_DOMAIN_MISSING")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS b08_segment_terminal_receipts ("
                "terminalization_key TEXT PRIMARY KEY, "
                "project_scope_id TEXT NOT NULL, logical_run_key TEXT NOT NULL, "
                "run_id TEXT NOT NULL, logical_run_generation INTEGER NOT NULL, "
                "run_epoch INTEGER NOT NULL, operation_id TEXT NOT NULL, "
                "call_request_hash TEXT NOT NULL, record_id TEXT NOT NULL UNIQUE, "
                "record_hash TEXT NOT NULL UNIQUE, record_json BLOB NOT NULL, "
                "UNIQUE(project_scope_id, operation_id))"
            )
            connection.commit()

    def _inject(self, point: str) -> None:
        if self.failure_point == point:
            fail("B08_SIMULATED_TRANSACTION_FAILURE", point)

    @staticmethod
    def _call_request_hash(
        *,
        project_scope_id: str,
        run_id: str,
        operation_id: str,
        expected_run_epoch: int,
        expected_state_revision: int,
    ) -> str:
        return sha256_value(
            {
                "kind": "B08_PUBLISH_V1",
                "project_scope_id": project_scope_id,
                "run_id": run_id,
                "operation_id": operation_id,
                "expected_run_epoch": expected_run_epoch,
                "expected_state_revision": expected_state_revision,
            }
        )

    @staticmethod
    def _row_record(row: tuple[Any, ...], *, code: str) -> dict[str, Any]:
        record = _decode(row[-1], code=code)
        validate_terminal_record(record)
        return record

    def publish(
        self,
        *,
        project_scope_id: str,
        run_id: str,
        operation_id: str,
        expected_run_epoch: int,
        expected_state_revision: int,
    ) -> dict[str, Any]:
        if (
            not isinstance(project_scope_id, str)
            or not project_scope_id
            or not isinstance(run_id, str)
            or not run_id
            or not isinstance(operation_id, str)
            or not operation_id
            or not isinstance(expected_run_epoch, int)
            or isinstance(expected_run_epoch, bool)
            or expected_run_epoch < 0
            or not isinstance(expected_state_revision, int)
            or isinstance(expected_state_revision, bool)
            or expected_state_revision < 1
        ):
            fail("B08_OPERATION_INVALID")
        call_request_hash = self._call_request_hash(
            project_scope_id=project_scope_id,
            run_id=run_id,
            operation_id=operation_id,
            expected_run_epoch=expected_run_epoch,
            expected_state_revision=expected_state_revision,
        )
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                prior = connection.execute(
                    "SELECT call_request_hash, record_json "
                    "FROM b08_segment_terminal_receipts "
                    "WHERE project_scope_id = ? AND operation_id = ?",
                    (project_scope_id, operation_id),
                ).fetchone()
                if prior is not None:
                    if prior[0] != call_request_hash:
                        fail("B08_IDEMPOTENCY_CONFLICT")
                    record = self._row_record(
                        (prior[1],), code="B08_STORED_TERMINAL_INVALID"
                    )
                    connection.rollback()
                    return self._publish_result(record)

                try:
                    snapshot = self._authority_reader.read_for_run(
                        connection,
                        project_scope_id=project_scope_id,
                        run_id=run_id,
                    )
                except B08ContractError:
                    raise
                except Exception as error:
                    fail("B08_AUTHORITY_READER_UNAVAILABLE", str(error))
                validate_authority_snapshot(snapshot, for_publish=True)
                state = snapshot["run_state"]
                if (
                    state["project_scope_id"] != project_scope_id
                    or state["run_id"] != run_id
                ):
                    fail("B08_RUN_SCOPE_MISMATCH")
                if (
                    state["run_epoch"] != expected_run_epoch
                    or state["state_revision"] != expected_state_revision
                ):
                    fail("B08_STALE_RUN_FENCE")

                key = terminalization_key(snapshot)
                existing = connection.execute(
                    "SELECT operation_id, record_json "
                    "FROM b08_segment_terminal_receipts "
                    "WHERE terminalization_key = ?",
                    (key,),
                ).fetchone()
                if existing is not None:
                    fail("B08_TERMINALIZATION_CONFLICT", str(existing[0]))

                operation_request_hash = sha256_value(
                    {
                        "call_request_hash": call_request_hash,
                        "authority_snapshot_hash": sha256_value(snapshot),
                    }
                )
                record = build_terminal_record(
                    snapshot=snapshot,
                    operation_id=operation_id,
                    operation_request_hash=operation_request_hash,
                    created_at=self._clock(),
                )
                payload = record["payload"]
                run = payload["run_binding"]
                connection.execute(
                    "INSERT INTO b08_segment_terminal_receipts("
                    "terminalization_key, project_scope_id, logical_run_key, run_id, "
                    "logical_run_generation, run_epoch, operation_id, call_request_hash, "
                    "record_id, record_hash, record_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        payload["terminalization_key"],
                        run["project_scope_id"],
                        run["logical_run_key"],
                        run["run_id"],
                        run["logical_run_generation"],
                        run["run_epoch"],
                        operation_id,
                        call_request_hash,
                        record["record_id"],
                        record["record_hash"],
                        sqlite3.Binary(canonical_bytes(record)),
                    ),
                )
                self._inject("after_terminal_insert")
                self._inject("before_terminal_commit")
                connection.commit()
                self.events.append(
                    {"event": "segment_terminal_written", "run_id": run_id}
                )
                return self._publish_result(record)
            except sqlite3.IntegrityError as error:
                connection.rollback()
                fail("B08_TERMINALIZATION_CONFLICT", str(error))
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _publish_result(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "terminal_record": deepcopy(record),
            "terminal_record_ref": terminal_record_ref(record),
            "component_observation": terminal_component_observation(record),
        }

    def read_record(self, ref: dict[str, Any]) -> dict[str, Any]:
        try:
            validate_record = ref["record_type"] == TERMINAL_RECEIPT_TYPE
            record_id = ref["record_id"]
            record_hash = ref["record_hash"]
        except (KeyError, TypeError):
            fail("B08_TERMINAL_REF_INVALID")
        if not validate_record:
            fail("B08_TERMINAL_REF_INVALID")
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT record_json FROM b08_segment_terminal_receipts "
                "WHERE record_id = ? AND record_hash = ?",
                (record_id, record_hash),
            ).fetchone()
        if row is None:
            fail("B08_TERMINAL_NOT_FOUND")
        record = self._row_record(row, code="B08_STORED_TERMINAL_INVALID")
        if canonical_bytes(terminal_record_ref(record)) != canonical_bytes(ref):
            fail("B08_TERMINAL_REF_INVALID")
        return record

    def read_artifact_bytes(self, workspace_relative_locator: str) -> bytes:
        prefix = f"{WRITE_SET_PREFIX}records/"
        if (
            not isinstance(workspace_relative_locator, str)
            or not workspace_relative_locator.startswith(prefix)
            or not workspace_relative_locator.endswith(".json")
        ):
            fail("B08_ARTIFACT_LOCATOR_INVALID")
        record_hash = workspace_relative_locator[len(prefix) : -5]
        if len(record_hash) != 64:
            fail("B08_ARTIFACT_LOCATOR_INVALID")
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT record_json FROM b08_segment_terminal_receipts "
                "WHERE record_hash = ?",
                (record_hash,),
            ).fetchone()
        if row is None:
            fail("B08_TERMINAL_NOT_FOUND")
        raw = bytes(row[0])
        record = _decode(raw, code="B08_STORED_TERMINAL_INVALID")
        validate_terminal_record(record)
        if record["record_hash"] != record_hash:
            fail("B08_STORED_TERMINAL_INVALID")
        return raw

    def visible_counts(self) -> dict[str, int]:
        with sqlite3.connect(self._database_path) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM b08_segment_terminal_receipts"
            ).fetchone()[0]
        return {"b08_segment_terminal_receipts": count}

    def schema_objects(self) -> list[str]:
        with sqlite3.connect(self._database_path) as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            ]


class B08TerminalReadService:
    """Derive currentness and adapter readiness without storing either view."""

    __slots__ = ("_store", "_authority_reader")

    def __init__(
        self,
        *,
        store: B08SegmentTerminalStore,
    ) -> None:
        self._store = store
        self._authority_reader = store._authority_reader

    def _current_snapshot(self, record: dict[str, Any]) -> dict[str, Any]:
        run = record["payload"]["run_binding"]
        with sqlite3.connect(self._store._database_path) as connection:
            try:
                snapshot = self._authority_reader.read_current(
                    connection,
                    project_scope_id=run["project_scope_id"],
                    logical_run_key=run["logical_run_key"],
                )
            except B08ContractError:
                raise
            except Exception as error:
                fail("B08_AUTHORITY_READER_UNAVAILABLE", str(error))
        validate_authority_snapshot(snapshot, for_publish=False)
        return snapshot

    @staticmethod
    def _currentness(
        record: dict[str, Any], snapshot: dict[str, Any]
    ) -> tuple[str, str]:
        payload = record["payload"]
        run = payload["run_binding"]
        state = snapshot["run_state"]
        if state["logical_run_generation"] != run["logical_run_generation"]:
            return "SUPERSEDED_RUN_GENERATION", "NEWER_LOGICAL_RUN_GENERATION"
        if state["run_epoch"] != run["run_epoch"]:
            return "SUPERSEDED_RUN_EPOCH", "NEWER_RUN_EPOCH"
        current_segment = snapshot["segment_binding"]
        old_segment = payload["segment_binding"]
        if current_segment["chapter_revision_ref"] != old_segment["chapter_revision_ref"]:
            return "SOURCE_REVISION_STALE", "CHAPTER_REVISION_CHANGED"
        if (
            current_segment["seg"] != old_segment["seg"]
            or current_segment["segment_scope_hash"]
            != old_segment["segment_scope_hash"]
            or current_segment["candidate_schema_id"]
            != old_segment["candidate_schema_id"]
            or canonical_bytes(current_segment["segment_index_ref"])
            != canonical_bytes(old_segment["segment_index_ref"])
            or canonical_bytes(current_segment["source_generation_ref"])
            != canonical_bytes(old_segment["source_generation_ref"])
        ):
            return "SEGMENT_SCOPE_STALE", "SEGMENT_SCOPE_CHANGED"
        current_pointer = snapshot["pointer_binding"]
        old_pointer = payload["pointer_binding"]
        if (
            current_pointer["logical_pointer_key"] != old_pointer["logical_pointer_key"]
            or current_pointer["generation"] != old_pointer["generation"]
        ):
            return "POINTER_STALE", "CURRENT_POINTER_CHANGED"
        if canonical_bytes(current_pointer["current_candidate_version_ref"]) != canonical_bytes(
            old_pointer["current_candidate_version_ref"]
        ):
            return "CANDIDATE_STALE", "CURRENT_CANDIDATE_CHANGED"
        current_merge = snapshot["b06_merge_receipt_or_null"]
        current_merge_ref = (
            None if current_merge is None else terminal_record_ref_for_any(current_merge)
        )
        if canonical_bytes(current_merge_ref) != canonical_bytes(
            payload["b06_merge_receipt_ref_or_null"]
        ):
            return "AUTHORITY_DRIFT", "B06_BINDING_CHANGED"
        if canonical_bytes(snapshot["classification_binding"]) != canonical_bytes(
            payload["classification_binding"]
        ):
            return "AUTHORITY_DRIFT", "CLASSIFICATION_OR_COVERAGE_CHANGED"

        observation = terminal_component_observation(record)
        if canonical_bytes(state["last_component_observation"]) != canonical_bytes(
            observation
        ):
            return "RUN_NOT_PUBLISHED", "B07_OBSERVATION_NOT_BOUND"
        delivery = payload["classification_binding"]["terminal_delivery"]
        if state["status"] == "SUCCEEDED" and delivery not in {
            "COMPLETE",
            "EMPTY_VALID",
        }:
            return "RUN_STATUS_INCOMPATIBLE", "SUCCEEDED_WITH_INCOMPLETE_TERMINAL"
        if state["status"] == "STOPPED" and delivery not in {"PARTIAL", "BLOCKED"}:
            return "RUN_STATUS_INCOMPATIBLE", "STOPPED_WITH_COMPLETE_TERMINAL"
        if state["status"] not in {"SUCCEEDED", "STOPPED"}:
            return "RUN_NOT_PUBLISHED", "B07_RUN_NOT_TERMINAL"
        return "CURRENT", "EXACT_CURRENT_TERMINAL"

    def exact_current_view(self, ref: dict[str, Any]) -> dict[str, Any]:
        record = self._store.read_record(ref)
        snapshot = self._current_snapshot(record)
        currentness, reason = self._currentness(record, snapshot)
        run = record["payload"]["run_binding"]
        classification = record["payload"]["classification_binding"]
        view = {
            "view_type": EXACT_CURRENT_VIEW_TYPE,
            "terminal_record_ref": terminal_record_ref(record),
            "currentness": currentness,
            "reason_code": reason,
            "product_result": classification["product_result"],
            "terminal_delivery": classification["terminal_delivery"],
            "run_id": run["run_id"],
            "logical_run_generation": run["logical_run_generation"],
            "run_epoch": run["run_epoch"],
            "current_state_hash": snapshot["run_state"]["state_hash"],
            "view_hash": "",
        }
        view["view_hash"] = sha256_value(
            {key: value for key, value in view.items() if key != "view_hash"}
        )
        validate_exact_current_view(view)
        return view

    def adapter_ready_view(self, ref: dict[str, Any]) -> dict[str, Any]:
        record = self._store.read_record(ref)
        exact = self.exact_current_view(ref)
        classification = record["payload"]["classification_binding"]
        ready = (
            exact["currentness"] == "CURRENT"
            and classification["terminal_delivery"] in {"COMPLETE", "EMPTY_VALID"}
            and classification["product_result"]
            not in {"INSUFFICIENT_EVIDENCE", "EXTRACTION_FAILED"}
        )
        view = {
            "view_type": ADAPTER_READY_VIEW_TYPE,
            "terminal_record_ref": terminal_record_ref(record),
            "ready": ready,
            "reason_code": "ADAPTER_READY" if ready else exact["reason_code"],
            "product_result": classification["product_result"],
            "terminal_delivery": classification["terminal_delivery"],
            "candidate_version_ref_or_null": (
                deepcopy(record["payload"]["pointer_binding"]["current_candidate_version_ref"])
                if ready
                else None
            ),
            "view_hash": "",
        }
        view["view_hash"] = sha256_value(
            {key: value for key, value in view.items() if key != "view_hash"}
        )
        validate_adapter_ready_view(view)
        return view


def terminal_record_ref_for_any(record: dict[str, Any]) -> dict[str, Any]:
    """Build a normal M3 record ref after the caller validated the original."""
    from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import record_ref

    return record_ref(record)
