"""Synthetic B-08 fixtures; no novel text, model call, or network access."""

from __future__ import annotations

import json
import sqlite3
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B07_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b07_local_recovery_stop_r01"
for candidate in (REPOSITORY_ROOT, B07_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    sha256_value,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.fixtures import (  # noqa: E402
    B07FixtureEnvironment,
    build_environment as build_b07_environment,
    generic_ref,
)

from b08_store import (  # noqa: E402
    B08SegmentTerminalStore,
    B08TerminalReadService,
)


def _decode(raw: Any) -> dict[str, Any]:
    value = json.loads(bytes(raw).decode("utf-8"))
    assert isinstance(value, dict)
    return value


class FixtureClock:
    def __init__(self) -> None:
        self.tick = 0

    def __call__(self) -> str:
        value = f"2026-09-01T06:10:{self.tick:02d}Z"
        self.tick += 1
        return value


class B08AuthorityFixture:
    """Reads B-01/B-06/B-07 originals from the shared SQLite connection."""

    def __init__(self) -> None:
        self.classification = {
            "classification_policy_ref": generic_ref(
                "M3_SEGMENT_TERMINAL_CLASSIFICATION_POLICY",
                "b08-policy:fixture",
            ),
            "classification_policy_hash": sha256_value(
                {"policy": "b08-fixture", "version": 1}
            ),
            "product_result": "CANDIDATES_READY",
            "terminal_delivery": "COMPLETE",
            "reason_code": "CANDIDATE_BATCH_COMPLETE",
            "candidate_count": 1,
            "expected_unit_count": 1,
            "covered_unit_count": 1,
            "missing_unit_count": 0,
            "coverage_complete": True,
        }
        self.segment_override: dict[str, Any] | None = None
        self.pointer_override: dict[str, Any] | None = None
        self.read_count = 0

    @staticmethod
    def _state_for_run(
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND run_id = ?",
            (project_scope_id, run_id),
        ).fetchone()
        if row is None:
            raise LookupError("run not found")
        return _decode(row[0])

    @staticmethod
    def _current_state(
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        logical_run_key: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND logical_run_key = ? "
            "ORDER BY logical_run_generation DESC LIMIT 1",
            (project_scope_id, logical_run_key),
        ).fetchone()
        if row is None:
            raise LookupError("logical run not found")
        return _decode(row[0])

    def _snapshot(
        self, connection: sqlite3.Connection, state: dict[str, Any]
    ) -> dict[str, Any]:
        self.read_count += 1
        pointer_row = connection.execute(
            "SELECT pointer_json FROM current_pointers WHERE logical_pointer_key = ?",
            (state["authority_snapshot"]["candidate_pointer_key"],),
        ).fetchone()
        if pointer_row is None:
            raise LookupError("pointer not found")
        pointer = _decode(pointer_row[0])
        if self.pointer_override is not None:
            pointer = deepcopy(self.pointer_override)
        candidate_row = connection.execute(
            "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
            (sha256_value(pointer["current_candidate_version_ref"]),),
        ).fetchone()
        if candidate_row is None:
            raise LookupError("candidate not found")
        candidate = _decode(candidate_row[0])
        payload = candidate["payload"]
        segment_binding = {
            "chapter_revision_ref": deepcopy(payload["chapter_revision_ref"]),
            "seg": payload["seg"],
            "segment_scope_hash": state["authority_snapshot"]["segment_scope_hash"],
            "segment_index_ref": deepcopy(payload["segment_index_ref"]),
            "source_generation_ref": deepcopy(
                payload["extraction_input_binding"]["accepted_source_generation_ref"]
            ),
            "candidate_schema_id": payload["candidate_schema_id"],
        }
        if self.segment_override is not None:
            segment_binding = deepcopy(self.segment_override)
        origin = (
            "B06_CHILD"
            if payload["parent_candidate_version_ref"] is not None
            else "ROOT"
        )
        pointer_binding = {
            "logical_pointer_key": pointer["logical_pointer_key"],
            "generation": pointer["generation"],
            "current_candidate_version_ref": deepcopy(
                pointer["current_candidate_version_ref"]
            ),
            "candidate_origin": origin,
        }
        merge_receipt = None
        if origin == "B06_CHILD":
            rows = connection.execute(
                "SELECT receipt_json FROM merge_receipts "
                "WHERE project_scope_id = ? ORDER BY operation_id",
                (state["project_scope_id"],),
            ).fetchall()
            matches = [
                _decode(row[0])
                for row in rows
                if canonical_bytes(_decode(row[0])["payload"]["child_candidate_version_ref"])
                == canonical_bytes(pointer["current_candidate_version_ref"])
            ]
            if len(matches) != 1:
                raise LookupError("exact merge receipt not found")
            merge_receipt = matches[0]
        return {
            "run_state": deepcopy(state),
            "segment_binding": segment_binding,
            "pointer_binding": pointer_binding,
            "classification_binding": deepcopy(self.classification),
            "b06_merge_receipt_or_null": deepcopy(merge_receipt),
        }

    def read_for_run(
        self,
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        state = self._state_for_run(
            connection, project_scope_id=project_scope_id, run_id=run_id
        )
        return self._snapshot(connection, state)

    def read_current(
        self,
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        logical_run_key: str,
    ) -> dict[str, Any]:
        state = self._current_state(
            connection,
            project_scope_id=project_scope_id,
            logical_run_key=logical_run_key,
        )
        return self._snapshot(connection, state)


@dataclass
class B08FixtureEnvironment:
    root: Path
    b07: B07FixtureEnvironment
    authority: B08AuthorityFixture
    store: B08SegmentTerminalStore
    reader: B08TerminalReadService
    clock: FixtureClock

    @property
    def project_scope_id(self) -> str:
        return self.b07.project_scope_id

    @property
    def run_id(self) -> str:
        return self.b07.run_id

    def state(self, run_id: str | None = None) -> dict[str, Any]:
        return self.b07.b07.read_state(
            self.project_scope_id, self.run_id if run_id is None else run_id
        )

    def publish(self, operation_id: str = "b08-terminal-1") -> dict[str, Any]:
        state = self.state()
        return self.store.publish(
            project_scope_id=self.project_scope_id,
            run_id=self.run_id,
            operation_id=operation_id,
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"],
        )

    def bind_succeeded(self, result: dict[str, Any]) -> dict[str, Any]:
        state = self.state()
        return self.b07.b07.advance(
            project_scope_id=self.project_scope_id,
            run_id=self.run_id,
            operation_id="bind-b08-success",
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"],
            target_status="SUCCEEDED",
            target_phase="FINALIZING",
            wait_kind=None,
            authority_reader=self.b07.authority,
            component_observation=result["component_observation"],
        )

    def bind_then_stop(
        self,
        result: dict[str, Any],
        *,
        stop_reason_code: str = "AUTHOR_ABORTED",
    ) -> dict[str, Any]:
        state = self.state()
        bound = self.b07.b07.advance(
            project_scope_id=self.project_scope_id,
            run_id=self.run_id,
            operation_id="bind-b08-stop",
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"],
            target_status="ACTIVE",
            target_phase="FINALIZING",
            wait_kind=None,
            authority_reader=self.b07.authority,
            component_observation=result["component_observation"],
        )
        return self.b07.b07.stop(
            project_scope_id=self.project_scope_id,
            run_id=self.run_id,
            operation_id="stop-after-b08",
            expected_run_epoch=bound["run_epoch"],
            expected_state_revision=bound["state_revision"],
            stop_reason_code=stop_reason_code,
            stop_class="LOCAL_CONTROL",
            stop_source="B08_FIXTURE",
            authority_reader=self.b07.authority,
        )

    def commit_b06_child(self) -> dict[str, Any]:
        state = self.state()
        pending, fence = self.b07.prepare_b06(state)
        self.b07.commit_b06(run_fence=fence)
        pointer = self.b07.b06.store.read_pointer(
            self.b07.b06.live_pointer["logical_pointer_key"]
        )
        self.b07.authority.sync_pointer(pointer)
        return self.b07.b07.reconcile_b06(
            project_scope_id=self.project_scope_id,
            run_id=self.run_id,
            operation_id="reconcile-b06-for-b08",
            expected_run_epoch=pending["run_epoch"],
            expected_state_revision=pending["state_revision"],
            authority_reader=self.b07.authority,
            committed_status="ACTIVE",
            committed_phase="FINALIZING",
        )


def build_environment(
    root: Path,
    *,
    failure_point: str | None = None,
) -> B08FixtureEnvironment:
    b07 = build_b07_environment(root / "shared")
    opened = b07.open()
    b07.b07.advance(
        project_scope_id=b07.project_scope_id,
        run_id=b07.run_id,
        operation_id="enter-finalizing",
        expected_run_epoch=opened["run_epoch"],
        expected_state_revision=opened["state_revision"],
        target_status="ACTIVE",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=b07.authority,
    )
    authority = B08AuthorityFixture()
    clock = FixtureClock()
    store = B08SegmentTerminalStore(
        b07.b06.store.root,
        clock=clock,
        authority_reader=authority,
        failure_point=failure_point,
    )
    store.initialize_schema()
    reader = B08TerminalReadService(store=store)
    return B08FixtureEnvironment(
        root=root,
        b07=b07,
        authority=authority,
        store=store,
        reader=reader,
        clock=clock,
    )
