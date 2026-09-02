"""Read B-01/B-06/B-07/B-08 authority without creating B-10 state."""

from __future__ import annotations

import json
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B08_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, B08_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    SOURCE_GENERATION_RECORD_TYPE,
    WRITING_MATERIAL_RECORD_TYPE,
    record_ref as b01_record_ref,
    validate_candidate_version,
    validate_record as b01_validate_record,
    validate_record_ref as b01_validate_record_ref,
    validate_segment_index_snapshot,
)
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    sha256_value,
)
from work.ccz57_m3_b06_commit_core_r01.b06_contracts import (  # noqa: E402
    B06ContractError,
    validate_mutable_pointer,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.b07_contracts import (  # noqa: E402
    project_author_status,
    validate_current_run_state,
)
from b08_contracts import (  # noqa: E402
    B08ContractError,
    terminal_record_ref,
    validate_authority_snapshot,
    validate_terminal_record,
)
from b08_store import B08TerminalReadService  # noqa: E402

if __package__:
    from .b10_contracts import (  # noqa: E402
        B10AuthorityError,
        B10ContractError,
        exact_segment_key,
        validate_request,
        validate_segment_result,
        validate_segment_set_closure,
    )
else:
    from b10_contracts import (  # noqa: E402
        B10AuthorityError,
        B10ContractError,
        exact_segment_key,
        validate_request,
        validate_segment_result,
        validate_segment_set_closure,
    )

CurrentSegmentIndexReader = Callable[[dict[str, Any]], dict[str, Any]]
ImmutableReader = Callable[[dict[str, Any]], dict[str, Any]]

_REQUIRED_TABLES = {
    "candidate_versions",
    "current_pointers",
    "merge_receipts",
    "b07_current_run_states",
    "b08_segment_terminal_receipts",
}


def _ref_equal(left: Any, right: Any) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _decode(raw: Any, *, detail: str) -> dict[str, Any]:
    try:
        value = json.loads(bytes(raw).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise B10AuthorityError("AUTHORITY_HASH_MISMATCH", f"{detail}: {error}") from error
    if not isinstance(value, dict):
        raise B10AuthorityError("AUTHORITY_HASH_MISMATCH", detail)
    return value


def _decode_state_row(row: tuple[Any, ...]) -> dict[str, Any]:
    state = _decode(row[8], detail="B-07 state bytes")
    try:
        validate_current_run_state(state)
    except ValueError as error:
        raise B10AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
    expected = (
        state["project_scope_id"],
        state["run_id"],
        state["logical_run_key"],
        state["logical_run_generation"],
        state["run_epoch"],
        state["state_revision"],
        state["status"],
        (
            None
            if state["stop_receipt_ref"] is None
            else state["stop_receipt_ref"]["record_id"]
        ),
    )
    if tuple(row[:8]) != expected:
        raise B10AuthorityError(
            "AUTHORITY_STATE_INCOHERENT", "B-07 mirrored columns"
        )
    return state


def _decode_terminal_row(row: tuple[Any, ...]) -> dict[str, Any]:
    terminal = _decode(row[10], detail="B-08 terminal bytes")
    try:
        validate_terminal_record(terminal)
    except ValueError as error:
        raise B10AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
    payload = terminal["payload"]
    run = payload["run_binding"]
    expected = (
        payload["terminalization_key"],
        run["project_scope_id"],
        run["logical_run_key"],
        run["run_id"],
        run["logical_run_generation"],
        run["run_epoch"],
        payload["operation_id"],
        row[7],
        terminal["record_id"],
        terminal["record_hash"],
    )
    operation_request_hash = sha256_value(
        {
            "call_request_hash": row[7],
            "authority_snapshot_hash": payload["authority_snapshot_hash"],
        }
    )
    if (
        tuple(row[:10]) != expected
        or payload["operation_request_hash"] != operation_request_hash
    ):
        raise B10AuthorityError(
            "AUTHORITY_STATE_INCOHERENT", "B-08 mirrored columns"
        )
    return terminal


class ChapterProgressAuthorityReader:
    """Own the fixed current-authority read order and its double-read fence."""

    __slots__ = (
        "_shared_database_path",
        "_current_segment_index_reader",
        "_immutable_reader",
        "_b08_authority_reader",
    )

    def __init__(
        self,
        *,
        shared_database_path: Path,
        current_segment_index_reader: CurrentSegmentIndexReader,
        immutable_reader: ImmutableReader,
        b08_authority_reader: Any,
    ) -> None:
        self._shared_database_path = Path(shared_database_path)
        self._current_segment_index_reader = current_segment_index_reader
        self._immutable_reader = immutable_reader
        self._b08_authority_reader = b08_authority_reader

    def _read_current_segment_index(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            record = self._current_segment_index_reader(deepcopy(request))
            validate_segment_index_snapshot(record)
        except B10AuthorityError:
            raise
        except B01ContractError as error:
            raise B10AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        except Exception as error:
            raise B10AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", f"B-01 current reader: {error}"
            ) from error
        payload = record["payload"]
        if (
            b01_record_ref(record) != request["segment_index_ref"]
            or payload["project_scope_id"] != request["project_scope_id"]
            or payload["chapter_revision_ref"] != request["chapter_revision_ref"]
        ):
            raise B10AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "requested SegmentIndex is not current"
            )
        return deepcopy(record)

    def _read_candidate_reference(
        self,
        ref: dict[str, Any],
        *,
        expected_type: str,
        current_segment_index: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            b01_validate_record_ref(ref, expected_type=expected_type)
            if _ref_equal(ref, b01_record_ref(current_segment_index)):
                record = current_segment_index
            else:
                record = self._immutable_reader(deepcopy(ref))
            b01_validate_record(record)
        except B10AuthorityError:
            raise
        except B01ContractError as error:
            raise B10AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        except Exception as error:
            raise B10AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT",
                f"{expected_type} read failed: {error}",
            ) from error
        if record["record_type"] != expected_type or not _ref_equal(
            b01_record_ref(record), ref
        ):
            raise B10AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", f"{expected_type} ref mismatch"
            )
        return deepcopy(record)

    def _candidate_reference_records(
        self,
        candidate: dict[str, Any],
        *,
        current_segment_index: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            payload = candidate["payload"]
            binding = payload["extraction_input_binding"]
            specs: list[tuple[dict[str, Any], str]] = [
                (binding["accepted_source_generation_ref"], SOURCE_GENERATION_RECORD_TYPE),
                (payload["segment_index_ref"], "M3_SEGMENT_INDEX_SNAPSHOT"),
            ]
            specs.extend(
                (item["material_ref"], WRITING_MATERIAL_RECORD_TYPE)
                for item in binding["writing_material_refs"]
            )
            specs.extend(
                (ref, "A_RAW_ATTEMPT_RECEIPT")
                for ref in payload["origin_attempt_refs"]
            )
            records: dict[bytes, dict[str, Any]] = {}
            for ref, expected_type in specs:
                key = canonical_bytes(ref)
                if key not in records:
                    records[key] = self._read_candidate_reference(
                        ref,
                        expected_type=expected_type,
                        current_segment_index=current_segment_index,
                    )
            return [records[key] for key in sorted(records)]
        except B10AuthorityError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise B10AuthorityError(
                "AUTHORITY_HASH_MISMATCH", f"candidate closure: {error}"
            ) from error

    @staticmethod
    def _candidate_row(
        connection: sqlite3.Connection, ref: dict[str, Any]
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
            (sha256_value(ref),),
        ).fetchone()
        if row is None:
            raise B10AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "current candidate not found"
            )
        candidate = _decode(row[0], detail="B-06 candidate bytes")
        if not _ref_equal(b01_record_ref(candidate), ref):
            raise B10AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "candidate ref mismatch"
            )
        return candidate

    def _pointer_and_candidate(
        self,
        connection: sqlite3.Connection,
        *,
        state: dict[str, Any],
        current_segment_index: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        pointer_key = state["authority_snapshot"]["candidate_pointer_key"]
        row = connection.execute(
            "SELECT project_scope_id, pointer_json FROM current_pointers "
            "WHERE logical_pointer_key = ?",
            (pointer_key,),
        ).fetchone()
        if row is None or row[0] != state["project_scope_id"]:
            raise B10AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "B-07 pointer not found"
            )
        pointer = _decode(row[1], detail="B-06 pointer bytes")
        candidate = self._candidate_row(
            connection, pointer["current_candidate_version_ref"]
        )
        references = self._candidate_reference_records(
            candidate, current_segment_index=current_segment_index
        )
        try:
            validate_candidate_version(
                candidate,
                allow_child=candidate["payload"]["parent_candidate_version_ref"]
                is not None,
                reference_records=references,
            )
            validate_mutable_pointer(
                pointer, candidate=candidate, reference_records=references
            )
        except (B01ContractError, B06ContractError, KeyError, TypeError) as error:
            raise B10AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        if (
            pointer["project_scope_id"] != state["project_scope_id"]
            or pointer["logical_pointer_key"]
            != state["authority_snapshot"]["candidate_pointer_key"]
        ):
            raise B10AuthorityError(
                "AUTHORITY_STATE_INCOHERENT", "B-07/B-06 pointer scope"
            )
        return pointer, candidate

    @staticmethod
    def _current_states(
        connection: sqlite3.Connection, *, project_scope_id: str
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT project_scope_id, run_id, logical_run_key, "
            "logical_run_generation, run_epoch, state_revision, status, "
            "stop_receipt_id, state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? ORDER BY logical_run_key, "
            "logical_run_generation DESC",
            (project_scope_id,),
        ).fetchall()
        current: dict[str, dict[str, Any]] = {}
        for row in rows:
            state = _decode_state_row(row)
            current.setdefault(state["logical_run_key"], state)
        return list(current.values())

    @staticmethod
    def _run_summary(state: dict[str, Any]) -> dict[str, Any]:
        author = project_author_status(state)
        return {
            "logical_run_key": state["logical_run_key"],
            "run_id": state["run_id"],
            "logical_run_generation": state["logical_run_generation"],
            "run_epoch": state["run_epoch"],
            "state_revision": state["state_revision"],
            "state_hash": state["state_hash"],
            "status": state["status"],
            "phase": state["phase"],
            "wait_kind": state["wait_kind"],
            "author_action_required": author["author_action_required"],
            "author_action_kind": author["author_action_kind"],
        }

    def _terminal_for_state(
        self,
        connection: sqlite3.Connection,
        *,
        state: dict[str, Any],
        pointer: dict[str, Any],
        segment_key: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        rows = connection.execute(
            "SELECT terminalization_key, project_scope_id, logical_run_key, run_id, "
            "logical_run_generation, run_epoch, operation_id, call_request_hash, "
            "record_id, record_hash, record_json "
            "FROM b08_segment_terminal_receipts WHERE project_scope_id = ? "
            "AND logical_run_key = ?",
            (state["project_scope_id"], state["logical_run_key"]),
        ).fetchall()
        matches: list[dict[str, Any]] = []
        for row in rows:
            terminal = _decode_terminal_row(row)
            payload = terminal["payload"]
            run = payload["run_binding"]
            segment = payload["segment_binding"]
            terminal_pointer = payload["pointer_binding"]
            same_current_run = (
                run["run_id"] == state["run_id"]
                and run["logical_run_generation"]
                == state["logical_run_generation"]
                and run["run_epoch"] == state["run_epoch"]
            )
            if not same_current_run:
                continue
            if (
                segment["chapter_revision_ref"] != segment_key["chapter_revision_ref"]
                or not _ref_equal(
                    segment["segment_index_ref"], segment_key["segment_index_ref"]
                )
                or segment["seg"] != segment_key["seg"]
                or terminal_pointer["logical_pointer_key"]
                != pointer["logical_pointer_key"]
            ):
                raise B10AuthorityError(
                    "AUTHORITY_STATE_INCOHERENT", "B-08 exact segment mismatch"
                )
            matches.append(terminal)
        if len(matches) > 1:
            raise B10AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "multiple exact B-08 terminals"
            )
        if not matches:
            return None, None, None
        terminal = matches[0]
        try:
            snapshot = self._b08_authority_reader.read_current(
                connection,
                project_scope_id=state["project_scope_id"],
                logical_run_key=state["logical_run_key"],
            )
            validate_authority_snapshot(snapshot, for_publish=False)
            currentness, reason = B08TerminalReadService._currentness(
                terminal, snapshot
            )
        except B08ContractError as error:
            raise B10AuthorityError("AUTHORITY_STATE_INCOHERENT", error.code) from error
        except Exception as error:
            raise B10AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", f"B-08 currentness: {error}"
            ) from error
        return terminal, currentness, reason

    def _resolve_segment(
        self,
        connection: sqlite3.Connection,
        *,
        segment_key: dict[str, Any],
        binding: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if binding is None:
            result = {
                "exact_segment_key": deepcopy(segment_key),
                "segment_status": "NOT_TRACKED_YET",
                "run_state_or_null": None,
                "terminal_record_ref_or_null": None,
                "terminal_currentness_or_null": None,
                "product_result_or_null": None,
                "terminal_delivery_or_null": None,
                "authority_witness": {
                    "kind": "AUTHORITATIVE_NO_CURRENT_RUN",
                    "exact_segment_key": deepcopy(segment_key),
                },
            }
            validate_segment_result(result)
            return result
        state, pointer, _candidate = binding
        run_summary = self._run_summary(state)
        state_authority = state["authority_snapshot"]
        run_pointer_current = (
            state_authority["observed_pointer_generation"] == pointer["generation"]
            and _ref_equal(
                state_authority["observed_candidate_version_ref"],
                pointer["current_candidate_version_ref"],
            )
        )
        terminal, currentness, currentness_reason = self._terminal_for_state(
            connection,
            state=state,
            pointer=pointer,
            segment_key=segment_key,
        )
        if terminal is None:
            terminal_ref = None
            product_result = None
            delivery = None
            if state["status"] in {"SUCCEEDED", "STOPPED"}:
                status = "TERMINALIZING" if run_pointer_current else "STALE"
                witness = {
                    "kind": "TERMINAL_PENDING",
                    "run_id": state["run_id"],
                    "logical_run_generation": state["logical_run_generation"],
                    "run_epoch": state["run_epoch"],
                    "state_hash": state["state_hash"],
                    "run_pointer_current": run_pointer_current,
                }
            else:
                status = (
                    {
                        "NEW": "RUNNING",
                        "ACTIVE": "RUNNING",
                        "WAITING_LOCAL": "WAITING",
                        "B06_OUTCOME_PENDING": "RUNNING",
                    }[state["status"]]
                    if run_pointer_current
                    else "STALE"
                )
                witness = {
                    "kind": "B07_CURRENT_RUN",
                    "state_hash": state["state_hash"],
                    "pointer_hash": sha256_value(pointer),
                    "run_pointer_current": run_pointer_current,
                }
        else:
            terminal_ref = terminal_record_ref(terminal)
            classification = terminal["payload"]["classification_binding"]
            product_result = classification["product_result"]
            delivery = classification["terminal_delivery"]
            if currentness == "CURRENT":
                status = delivery
            elif (
                currentness == "RUN_NOT_PUBLISHED"
                and run_pointer_current
                and state["status"]
                in {"NEW", "ACTIVE", "WAITING_LOCAL", "B06_OUTCOME_PENDING"}
            ):
                status = "WAITING" if state["status"] == "WAITING_LOCAL" else "RUNNING"
            else:
                status = "STALE"
            witness = {
                "kind": "B08_TERMINAL",
                "terminal_record_ref": deepcopy(terminal_ref),
                "currentness": currentness,
                "currentness_reason": currentness_reason,
                "state_hash": state["state_hash"],
                "pointer_hash": sha256_value(pointer),
            }
        result = {
            "exact_segment_key": deepcopy(segment_key),
            "segment_status": status,
            "run_state_or_null": run_summary,
            "terminal_record_ref_or_null": terminal_ref,
            "terminal_currentness_or_null": currentness,
            "product_result_or_null": product_result,
            "terminal_delivery_or_null": delivery,
            "authority_witness": witness,
        }
        validate_segment_result(result)
        return result

    def _collect(self, request: dict[str, Any]) -> dict[str, Any]:
        segment_index = self._read_current_segment_index(request)
        payload = segment_index["payload"]
        expected = [
            exact_segment_key(
                project_scope_id=payload["project_scope_id"],
                author_workspace_logical_key=payload[
                    "author_workspace_logical_key"
                ],
                chapter_revision_ref=payload["chapter_revision_ref"],
                segment_index_ref=b01_record_ref(segment_index),
                seg=segment["seg"],
            )
            for segment in payload["segments"]
        ]
        if len(expected) != len({canonical_bytes(key) for key in expected}):
            raise B10AuthorityError(
                "AUTHORITY_STATE_INCOHERENT", "duplicate B-01 segment"
            )
        if not self._shared_database_path.is_file():
            raise B10AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", "shared SQLite missing"
            )
        uri = f"file:{self._shared_database_path.resolve().as_posix()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True) as connection:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("BEGIN")
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                if not _REQUIRED_TABLES <= tables:
                    raise B10AuthorityError(
                        "AUTHORITY_READER_UNAVAILABLE", "authority tables missing"
                    )
                by_segment: dict[bytes, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
                expected_by_bytes = {canonical_bytes(key): key for key in expected}
                expected_by_seg = {key["seg"]: key for key in expected}
                for state in self._current_states(
                    connection, project_scope_id=request["project_scope_id"]
                ):
                    if (
                        state["authority_snapshot"]["chapter_revision_ref"]
                        != request["chapter_revision_ref"]
                    ):
                        continue
                    pointer, candidate = self._pointer_and_candidate(
                        connection,
                        state=state,
                        current_segment_index=segment_index,
                    )
                    candidate_payload = candidate["payload"]
                    seg = candidate_payload["seg"]
                    key = expected_by_seg.get(seg)
                    if key is None:
                        raise B10AuthorityError(
                            "AUTHORITY_STATE_INCOHERENT", "out-of-range segment"
                        )
                    if (
                        pointer["author_workspace_logical_key"]
                        != payload["author_workspace_logical_key"]
                        or not _ref_equal(
                            candidate_payload["segment_index_ref"],
                            request["segment_index_ref"],
                        )
                        or not _ref_equal(
                            candidate_payload["extraction_input_binding"][
                                "accepted_source_generation_ref"
                            ],
                            payload["accepted_source_generation_ref"],
                        )
                    ):
                        raise B10AuthorityError(
                            "AUTHORITY_REFERENCE_CONFLICT",
                            "mixed workspace, SegmentIndex, or source generation",
                        )
                    key_bytes = canonical_bytes(key)
                    if key_bytes not in expected_by_bytes or key_bytes in by_segment:
                        raise B10AuthorityError(
                            "AUTHORITY_REFERENCE_CONFLICT",
                            "multiple current runs for one segment",
                        )
                    by_segment[key_bytes] = (state, pointer, candidate)
                results = [
                    self._resolve_segment(
                        connection,
                        segment_key=key,
                        binding=by_segment.get(canonical_bytes(key)),
                    )
                    for key in expected
                ]
                connection.rollback()
        except B10AuthorityError:
            raise
        except sqlite3.Error as error:
            raise B10AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", str(error)
            ) from error
        resolved = [item["exact_segment_key"] for item in results]
        try:
            validate_segment_set_closure(expected, resolved)
        except B10ContractError as error:
            raise B10AuthorityError(
                "AUTHORITY_STATE_INCOHERENT", error.code
            ) from error
        fingerprint = {
            "segment_index_ref": deepcopy(request["segment_index_ref"]),
            "segment_index_record_hash": segment_index["record_hash"],
            "expected_segment_keys": deepcopy(expected),
            "segment_witnesses": [
                {
                    "exact_segment_key": deepcopy(item["exact_segment_key"]),
                    "authority_witness": deepcopy(item["authority_witness"]),
                }
                for item in results
            ],
        }
        return {
            "expected_segment_keys": expected,
            "segment_results": results,
            "authority_fingerprint": fingerprint,
        }

    def _between_reads(self) -> None:
        """No-op seam used only by deterministic drift regression tests."""

    def read(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_request(request)
        try:
            first = self._collect(request)
            self._between_reads()
            second = self._collect(request)
            if canonical_bytes(first["authority_fingerprint"]) != canonical_bytes(
                second["authority_fingerprint"]
            ):
                raise B10AuthorityError(
                    "AUTHORITY_DRIFT", "authority fingerprint changed"
                )
            return deepcopy(first)
        except (B10AuthorityError, B10ContractError):
            raise
        except Exception as error:
            raise B10AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", str(error)
            ) from error
