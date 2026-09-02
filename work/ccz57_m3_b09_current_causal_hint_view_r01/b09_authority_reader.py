"""Read B-04 through B-08 authority without creating B-09 state."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
B08_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, B05_ROOT, B08_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION as B01_CONTRACT_VERSION,
    FIXTURE_ACCESS as B01_FIXTURE_ACCESS,
    FIXTURE_POINTER_NAMESPACE,
    SOURCE_GENERATION_RECORD_TYPE,
    SOURCE_MODULE as B01_SOURCE_MODULE,
    WRITING_MATERIAL_RECORD_TYPE,
    LIVE_POINTER_KEYS,
    pointer_logical_key,
    record_ref as b01_record_ref,
    validate_candidate_version,
    validate_chapter_revision_ref,
    validate_record as b01_validate_record,
    validate_record_ref as b01_validate_record_ref,
    validate_segment_index_snapshot,
)
from b05_contracts import (  # noqa: E402
    B05ContractError,
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_immutable_record,
    validate_record_ref,
)
from patch_route_projection import PatchAggregateProjector  # noqa: E402
from work.ccz57_m3_b06_commit_core_r01.b06_contracts import (  # noqa: E402
    B06ContractError,
    validate_merge_receipt,
    validate_mutable_pointer,
)
from work.ccz57_m3_b04_patch_atomic_group_r03_5.b04_contracts import (  # noqa: E402
    B04ContractError,
    validate_causal_record,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.b07_contracts import (  # noqa: E402
    validate_current_run_state,
)
from b08_contracts import (  # noqa: E402
    B08ContractError,
    terminal_component_observation,
    terminal_record_ref,
    validate_authority_snapshot,
    validate_terminal_record,
)
from work.ccz57_m3_b08_segment_terminal_r01.b08_store import (  # noqa: E402
    B08TerminalReadService,
)

if __package__:
    from .b09_contracts import (  # noqa: E402
        B09AuthorityError,
        B09ContractError,
        validate_request,
    )
else:
    from b09_contracts import (  # noqa: E402
        B09AuthorityError,
        B09ContractError,
        validate_request,
    )

FreshnessReader = Callable[[], dict[str, str]]
ImmutableReader = Callable[[dict[str, Any]], dict[str, Any]]
FRESHNESS_KEYS = {
    "b02_scope_snapshot_hash",
    "active_policy_selection_hash",
    "non_content_gate_snapshot_hash",
}
SNAPSHOT_KEYS = {
    "request",
    "b05_records",
    "active_route",
    "lifecycle_head_ref",
    "validation_receipt",
    "causal_hint_proposals",
    "run_state",
    "current_pointer",
    "base_candidate",
    "current_candidate",
    "current_segment_index",
    "merge_receipt_or_null",
    "exact_current_terminal_ref_or_null",
    "freshness",
    "authority_fingerprint",
}


def _decode(raw: Any, *, reason: str, detail: str) -> dict[str, Any]:
    try:
        value = json.loads(bytes(raw).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise B09AuthorityError(reason, f"{detail}: {error}") from error
    if not isinstance(value, dict):
        raise B09AuthorityError(reason, detail)
    return value


def _ref_equal(left: Any, right: Any) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _record_for_ref(
    records: list[dict[str, Any]],
    ref: dict[str, Any],
    *,
    expected_type: str,
) -> dict[str, Any]:
    try:
        validate_record_ref(ref, expected_type=expected_type)
    except ValueError as error:
        raise B09AuthorityError("AUTHORITY_REFERENCE_CONFLICT", str(error)) from error
    matches = [
        record
        for record in records
        if record.get("record_type") == expected_type
        and _ref_equal(record_ref(record), ref)
    ]
    if len(matches) != 1:
        raise B09AuthorityError(
            "AUTHORITY_REFERENCE_CONFLICT",
            f"expected one {expected_type}, found {len(matches)}",
        )
    return deepcopy(matches[0])


def _validate_freshness(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != FRESHNESS_KEYS:
        raise B09AuthorityError("AUTHORITY_READER_UNAVAILABLE", "freshness shape")
    if any(
        not isinstance(item, str)
        or len(item) != 64
        or any(character not in "0123456789abcdef" for character in item)
        for item in value.values()
    ):
        raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", "freshness hash")
    return deepcopy(value)


class CurrentCausalHintAuthorityReader:
    """Own the fixed read order and return one verified, disposable snapshot."""

    __slots__ = (
        "_b05_store",
        "_shared_database_path",
        "_freshness_reader",
        "_immutable_reader",
        "_b08_authority_reader",
    )

    def __init__(
        self,
        *,
        b05_store: Any,
        shared_database_path: Path,
        freshness_reader: FreshnessReader,
        immutable_reader: ImmutableReader,
        b08_authority_reader: Any,
    ) -> None:
        self._b05_store = b05_store
        self._shared_database_path = Path(shared_database_path)
        self._freshness_reader = freshness_reader
        self._immutable_reader = immutable_reader
        self._b08_authority_reader = b08_authority_reader

    @staticmethod
    def _b05_projection(records: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            return PatchAggregateProjector.project(records)
        except B05ContractError as error:
            reason = (
                "AUTHORITY_HASH_MISMATCH"
                if "HASH" in error.code or "INVALID" in error.code
                else "AUTHORITY_REFERENCE_CONFLICT"
            )
            raise B09AuthorityError(reason, error.code) from error

    @staticmethod
    def _select_route(
        *,
        records: list[dict[str, Any]],
        projection: dict[str, Any],
        state: dict[str, Any],
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
    ]:
        state_authority = state["authority_snapshot"]
        route_ref = state_authority["route_decision_ref"]
        route_hash = state_authority["route_decision_hash"]
        if route_ref is None:
            if route_hash is not None:
                raise B09AuthorityError(
                    "AUTHORITY_STATE_INCOHERENT", "route ref/hash nullability"
                )
            return None, None, None
        route = _record_for_ref(
            records, route_ref, expected_type="M3_PATCH_ROUTE_RECEIPT"
        )
        if route_hash != route["record_hash"]:
            raise B09AuthorityError(
                "AUTHORITY_HASH_MISMATCH", "B07 route_decision_hash"
            )
        series = [
            item
            for item in projection["series"]
            if item["route_series_id"] == route["payload"]["route_series_id"]
        ]
        if len(series) != 1:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "B07 route series is not unique"
            )
        active_route_ref = deepcopy(series[0]["active_route_receipt_ref"])
        active_route = _record_for_ref(
            records,
            active_route_ref,
            expected_type="M3_PATCH_ROUTE_RECEIPT",
        )
        if (
            active_route["payload"]["route_series_id"]
            != route["payload"]["route_series_id"]
        ):
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "active route series mismatch"
            )
        lifecycle_head_ref = deepcopy(series[0]["lifecycle_head_ref"])
        _record_for_ref(
            records,
            lifecycle_head_ref,
            expected_type="M3_PATCH_LIFECYCLE_RECEIPT",
        )
        if not _ref_equal(active_route_ref, route_ref):
            return None, None, None
        validation = _record_for_ref(
            records,
            route["payload"]["validation_receipt_ref"],
            expected_type="M3_PATCH_VALIDATION_RECEIPT",
        )
        return route, lifecycle_head_ref, validation

    @staticmethod
    def _candidate_row(
        connection: sqlite3.Connection, ref: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            validate_record_ref(ref, expected_type="M3_CANDIDATE_VERSION")
        except ValueError as error:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", str(error)
            ) from error
        if (
            ref["contract_version"] != B01_CONTRACT_VERSION
            or ref["record_contract_version"] != B01_CONTRACT_VERSION
            or ref["source_module"] != B01_SOURCE_MODULE
            or ref["access"] != B01_FIXTURE_ACCESS
            or not isinstance(ref["record_version"], int)
            or isinstance(ref["record_version"], bool)
        ):
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "candidate ref policy"
            )
        row = connection.execute(
            "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
            (sha256_value(ref),),
        ).fetchone()
        if row is None:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "candidate not found"
            )
        candidate = _decode(
            row[0],
            reason="AUTHORITY_HASH_MISMATCH",
            detail="candidate bytes",
        )
        try:
            validate_immutable_record(candidate, expected_type="M3_CANDIDATE_VERSION")
        except ValueError as error:
            raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        if (
            candidate["contract_version"] != B01_CONTRACT_VERSION
            or candidate["record_contract_version"] != B01_CONTRACT_VERSION
            or candidate["source_module"] != B01_SOURCE_MODULE
            or candidate["access"] != B01_FIXTURE_ACCESS
            or not isinstance(candidate["record_version"], int)
            or isinstance(candidate["record_version"], bool)
        ):
            raise B09AuthorityError(
                "AUTHORITY_HASH_MISMATCH", "candidate record policy"
            )
        if not _ref_equal(record_ref(candidate), ref):
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "candidate ref mismatch"
            )
        payload = candidate.get("payload")
        if not isinstance(payload, dict) or payload.get(
            "version_payload_hash"
        ) != sha256_value(
            {
                key: value
                for key, value in payload.items()
                if key != "version_payload_hash"
            }
        ):
            raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", "candidate payload hash")
        return candidate

    @staticmethod
    def _pointer(
        connection: sqlite3.Connection,
        *,
        logical_pointer_key: str,
        project_scope_id: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT project_scope_id, pointer_json FROM current_pointers "
            "WHERE logical_pointer_key = ?",
            (logical_pointer_key,),
        ).fetchone()
        if row is None or row[0] != project_scope_id:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "current pointer not found"
            )
        pointer = _decode(
            row[1],
            reason="AUTHORITY_HASH_MISMATCH",
            detail="pointer bytes",
        )
        if set(pointer) != LIVE_POINTER_KEYS:
            raise B09AuthorityError("AUTHORITY_STATE_INCOHERENT", "pointer shape")
        if (
            pointer["logical_pointer_key"] != logical_pointer_key
            or not isinstance(pointer["generation"], int)
            or isinstance(pointer["generation"], bool)
            or pointer["generation"] < 1
        ):
            raise B09AuthorityError("AUTHORITY_STATE_INCOHERENT", "pointer identity")
        return pointer

    @staticmethod
    def _validate_pointer_candidate_binding(
        pointer: dict[str, Any],
        candidate: dict[str, Any],
    ) -> None:
        try:
            validate_chapter_revision_ref(pointer["chapter_revision_ref"])
            validate_record_ref(
                pointer["current_candidate_version_ref"],
                expected_type="M3_CANDIDATE_VERSION",
            )
            candidate_ref = record_ref(candidate)
            payload = candidate["payload"]
            input_binding = payload["extraction_input_binding"]
            expected_pointer_key = pointer_logical_key(
                pointer["chapter_revision_ref"],
                pointer["seg"],
                pointer["input_binding_hash"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise B09AuthorityError(
                "AUTHORITY_STATE_INCOHERENT", f"pointer contract: {error}"
            ) from error
        if (
            pointer["pointer_namespace"] != FIXTURE_POINTER_NAMESPACE
            or pointer["candidate_schema_id"] != CANDIDATE_SCHEMA_ID
            or payload["candidate_schema_id"] != CANDIDATE_SCHEMA_ID
            or not isinstance(pointer["project_scope_id"], str)
            or not pointer["project_scope_id"]
            or not isinstance(pointer["author_workspace_logical_key"], str)
            or not pointer["author_workspace_logical_key"]
            or not isinstance(pointer["logical_pointer_key"], str)
            or not pointer["logical_pointer_key"]
            or pointer["logical_pointer_key"] != expected_pointer_key
            or not isinstance(pointer["seg"], int)
            or isinstance(pointer["seg"], bool)
            or pointer["seg"] < 1
            or not isinstance(pointer["input_binding_hash"], str)
            or re.fullmatch(r"[0-9a-f]{64}", pointer["input_binding_hash"])
            is None
            or not _ref_equal(
                pointer["current_candidate_version_ref"], candidate_ref
            )
            or pointer["chapter_revision_ref"] != payload["chapter_revision_ref"]
            or pointer["seg"] != payload["seg"]
            or pointer["input_binding_hash"] != input_binding["input_binding_hash"]
        ):
            raise B09AuthorityError(
                "AUTHORITY_STATE_INCOHERENT", "pointer/candidate contract"
            )

    @staticmethod
    def _merge_receipt(
        connection: sqlite3.Connection,
        *,
        project_scope_id: str,
        current_candidate: dict[str, Any],
    ) -> dict[str, Any] | None:
        if current_candidate["payload"]["parent_candidate_version_ref"] is None:
            return None
        rows = connection.execute(
            "SELECT receipt_json FROM merge_receipts WHERE project_scope_id = ?",
            (project_scope_id,),
        ).fetchall()
        matches: list[dict[str, Any]] = []
        current_ref = record_ref(current_candidate)
        for row in rows:
            receipt = _decode(
                row[0],
                reason="AUTHORITY_HASH_MISMATCH",
                detail="merge receipt bytes",
            )
            try:
                validate_merge_receipt(receipt)
            except ValueError as error:
                raise B09AuthorityError(
                    "AUTHORITY_HASH_MISMATCH", str(error)
                ) from error
            if _ref_equal(
                receipt["payload"]["child_candidate_version_ref"], current_ref
            ):
                matches.append(receipt)
        if len(matches) != 1:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT",
                f"exact child merge receipt count {len(matches)}",
            )
        return matches[0]

    @staticmethod
    def _terminal_binding_matches(
        terminal: dict[str, Any],
        *,
        state: dict[str, Any],
        pointer: dict[str, Any],
    ) -> bool:
        payload = terminal["payload"]
        run = payload["run_binding"]
        segment = payload["segment_binding"]
        terminal_pointer = payload["pointer_binding"]
        state_authority = state["authority_snapshot"]
        return (
            run["project_scope_id"] == state["project_scope_id"]
            and run["logical_run_key"] == state["logical_run_key"]
            and run["run_id"] == state["run_id"]
            and run["logical_run_generation"] == state["logical_run_generation"]
            and run["run_epoch"] == state["run_epoch"]
            and segment["chapter_revision_ref"]
            == state_authority["chapter_revision_ref"]
            and segment["seg"] == pointer["seg"]
            and segment["segment_scope_hash"] == state_authority["segment_scope_hash"]
            and terminal_pointer["logical_pointer_key"]
            == pointer["logical_pointer_key"]
            and terminal_pointer["generation"] == pointer["generation"]
            and _ref_equal(
                terminal_pointer["current_candidate_version_ref"],
                pointer["current_candidate_version_ref"],
            )
        )

    def _b08_currentness(
        self,
        connection: sqlite3.Connection,
        terminal: dict[str, Any],
    ) -> tuple[str, str]:
        run = terminal["payload"]["run_binding"]
        try:
            snapshot = self._b08_authority_reader.read_current(
                connection,
                project_scope_id=run["project_scope_id"],
                logical_run_key=run["logical_run_key"],
            )
            validate_authority_snapshot(snapshot, for_publish=False)
            return B08TerminalReadService._currentness(terminal, snapshot)
        except B08ContractError as error:
            raise B09AuthorityError("AUTHORITY_STATE_INCOHERENT", error.code) from error
        except B09AuthorityError:
            raise
        except Exception as error:
            raise B09AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", f"B08 currentness: {error}"
            ) from error

    def _exact_terminal(
        self,
        connection: sqlite3.Connection,
        *,
        state: dict[str, Any],
        pointer: dict[str, Any],
    ) -> dict[str, Any] | None:
        rows = connection.execute(
            "SELECT record_json FROM b08_segment_terminal_receipts "
            "WHERE project_scope_id = ? AND logical_run_key = ?",
            (state["project_scope_id"], state["logical_run_key"]),
        ).fetchall()
        exact: list[dict[str, Any]] = []
        for row in rows:
            terminal = _decode(
                row[0],
                reason="AUTHORITY_HASH_MISMATCH",
                detail="terminal bytes",
            )
            try:
                validate_terminal_record(terminal)
            except ValueError as error:
                raise B09AuthorityError(
                    "AUTHORITY_HASH_MISMATCH", str(error)
                ) from error
            if self._terminal_binding_matches(terminal, state=state, pointer=pointer):
                exact.append(terminal)
        bound = [
            terminal
            for terminal in exact
            if _ref_equal(
                terminal_component_observation(terminal),
                state["last_component_observation"],
            )
        ]
        if len(bound) == 1:
            currentness, reason = self._b08_currentness(connection, bound[0])
            if currentness != "CURRENT":
                raise B09AuthorityError(
                    "AUTHORITY_STATE_INCOHERENT",
                    f"B08 terminal is {currentness}: {reason}",
                )
        if state["status"] == "SUCCEEDED":
            if len(exact) != 1 or len(bound) != 1:
                raise B09AuthorityError(
                    "AUTHORITY_STATE_INCOHERENT",
                    "terminal B07/B08 binding conflict",
                )
            return terminal_record_ref(bound[0])
        if state["status"] == "STOPPED":
            if not exact and not bound:
                return None
            if len(exact) == 1 and len(bound) == 1:
                return terminal_record_ref(bound[0])
            raise B09AuthorityError(
                "AUTHORITY_STATE_INCOHERENT",
                "stopped run terminal binding conflict",
            )
        if bound:
            raise B09AuthorityError(
                "AUTHORITY_STATE_INCOHERENT",
                "nonterminal run binds an exact terminal",
            )
        return None

    @staticmethod
    def _read_state(
        connection: sqlite3.Connection, request: dict[str, Any]
    ) -> dict[str, Any]:
        requested = connection.execute(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND run_id = ?",
            (request["project_scope_id"], request["run_id"]),
        ).fetchone()
        if requested is None:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "requested run not found"
            )
        requested_state = _decode(
            requested[0],
            reason="AUTHORITY_HASH_MISMATCH",
            detail="requested run state bytes",
        )
        try:
            validate_current_run_state(requested_state)
        except ValueError as error:
            raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        current = connection.execute(
            "SELECT state_json FROM b07_current_run_states "
            "WHERE project_scope_id = ? AND logical_run_key = ? "
            "ORDER BY logical_run_generation DESC LIMIT 1",
            (request["project_scope_id"], requested_state["logical_run_key"]),
        ).fetchone()
        if current is None:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "current logical run not found"
            )
        state = _decode(
            current[0],
            reason="AUTHORITY_HASH_MISMATCH",
            detail="current run state bytes",
        )
        try:
            validate_current_run_state(state)
        except ValueError as error:
            raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        return state

    def _collect_shared(
        self,
        *,
        request: dict[str, Any],
        records: list[dict[str, Any]],
        projection: dict[str, Any],
        freshness: dict[str, str],
    ) -> dict[str, Any]:
        if not self._shared_database_path.is_file():
            raise B09AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", "shared SQLite missing"
            )
        uri = f"file:{self._shared_database_path.resolve().as_posix()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True) as connection:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("BEGIN")
                state = self._read_state(connection, request)
                route, lifecycle_head_ref, validation = self._select_route(
                    records=records, projection=projection, state=state
                )
                pointer = self._pointer(
                    connection,
                    logical_pointer_key=state["authority_snapshot"][
                        "candidate_pointer_key"
                    ],
                    project_scope_id=state["project_scope_id"],
                )
                current_candidate = self._candidate_row(
                    connection, pointer["current_candidate_version_ref"]
                )
                self._validate_pointer_candidate_binding(pointer, current_candidate)
                if route is None:
                    base_candidate = current_candidate
                else:
                    base_candidate = self._candidate_row(
                        connection,
                        validation["payload"]["input_binding"][
                            "base_candidate_version_ref"
                        ],
                    )
                merge_receipt = self._merge_receipt(
                    connection,
                    project_scope_id=state["project_scope_id"],
                    current_candidate=current_candidate,
                )
                terminal_ref = self._exact_terminal(
                    connection, state=state, pointer=pointer
                )
                connection.rollback()
        except B09AuthorityError:
            raise
        except sqlite3.Error as error:
            raise B09AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", str(error)
            ) from error

        state_authority = state["authority_snapshot"]
        payload = current_candidate["payload"]
        if (
            state["project_scope_id"] != request["project_scope_id"]
            or pointer["project_scope_id"] != state["project_scope_id"]
            or state_authority["candidate_pointer_key"]
            != pointer["logical_pointer_key"]
            or state_authority["observed_pointer_generation"] != pointer["generation"]
            or not _ref_equal(
                state_authority["observed_candidate_version_ref"],
                pointer["current_candidate_version_ref"],
            )
            or not _ref_equal(
                record_ref(current_candidate),
                pointer["current_candidate_version_ref"],
            )
            or payload["chapter_revision_ref"] != pointer["chapter_revision_ref"]
            or payload["chapter_revision_ref"]
            != state_authority["chapter_revision_ref"]
            or payload["seg"] != pointer["seg"]
        ):
            raise B09AuthorityError(
                "AUTHORITY_STATE_INCOHERENT", "run/pointer/candidate binding"
            )
        if route is not None:
            binding = route["payload"]["binding_header"]
            if (
                binding["chapter_revision_ref"]
                != base_candidate["payload"]["chapter_revision_ref"]
                or binding["seg"] != base_candidate["payload"]["seg"]
                or validation["payload"]["active_policy_selection_hash"]
                != route["payload"]["active_policy_selection_hash"]
            ):
                raise B09AuthorityError(
                    "AUTHORITY_REFERENCE_CONFLICT", "route/base/PVR binding"
                )

        fingerprint = {
            "active_route_receipt_ref_or_null": (
                None if route is None else record_ref(route)
            ),
            "lifecycle_head_ref_or_null": deepcopy(lifecycle_head_ref),
            "b02_scope_snapshot_hash": freshness["b02_scope_snapshot_hash"],
            "active_policy_selection_hash": freshness["active_policy_selection_hash"],
            "non_content_gate_snapshot_hash": freshness[
                "non_content_gate_snapshot_hash"
            ],
            "pointer_generation": pointer["generation"],
            "pointer_binding_hash": sha256_value(pointer),
            "run_epoch": state["run_epoch"],
            "state_revision": state["state_revision"],
            "state_hash": state["state_hash"],
            "exact_current_terminal_ref_or_absent": (
                "ABSENT" if terminal_ref is None else terminal_ref
            ),
        }
        return {
            "active_route": route,
            "lifecycle_head_ref": lifecycle_head_ref,
            "validation_receipt": validation,
            "run_state": state,
            "current_pointer": pointer,
            "base_candidate": base_candidate,
            "current_candidate": current_candidate,
            "merge_receipt_or_null": merge_receipt,
            "exact_current_terminal_ref_or_null": terminal_ref,
            "freshness": freshness,
            "authority_fingerprint": fingerprint,
        }

    def _read_exact(self, ref: dict[str, Any], *, expected_type: str) -> dict[str, Any]:
        try:
            record = self._immutable_reader(deepcopy(ref))
        except B09AuthorityError:
            raise
        except Exception as error:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT",
                f"{expected_type} read failed: {error}",
            ) from error
        try:
            validate_immutable_record(record, expected_type=expected_type)
        except ValueError as error:
            reason = (
                "AUTHORITY_HASH_MISMATCH"
                if "HASH" in str(error)
                else "AUTHORITY_REFERENCE_CONFLICT"
            )
            raise B09AuthorityError(reason, str(error)) from error
        if not _ref_equal(record_ref(record), ref):
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", f"{expected_type} ref mismatch"
            )
        return deepcopy(record)

    def _candidate_reference_records(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            specs: list[tuple[dict[str, Any], str]] = []
            for candidate in candidates:
                payload = candidate["payload"]
                binding = payload["extraction_input_binding"]
                specs.extend(
                    [
                        (
                            binding["accepted_source_generation_ref"],
                            SOURCE_GENERATION_RECORD_TYPE,
                        ),
                        (payload["segment_index_ref"], "M3_SEGMENT_INDEX_SNAPSHOT"),
                    ]
                )
                specs.extend(
                    (item["material_ref"], WRITING_MATERIAL_RECORD_TYPE)
                    for item in binding["writing_material_refs"]
                )
                specs.extend(
                    (ref, "A_RAW_ATTEMPT_RECEIPT")
                    for ref in payload["origin_attempt_refs"]
                )
            resolved: dict[bytes, tuple[str, dict[str, Any]]] = {}
            for ref, expected_type in specs:
                key = canonical_bytes(ref)
                prior = resolved.get(key)
                if prior is not None:
                    if prior[0] != expected_type:
                        raise B09AuthorityError(
                            "AUTHORITY_REFERENCE_CONFLICT",
                            "candidate reference type conflict",
                        )
                    continue
                resolved[key] = (
                    expected_type,
                    self._read_candidate_reference(
                        ref,
                        expected_type=expected_type,
                    ),
                )
            return [resolved[key][1] for key in sorted(resolved)]
        except B09AuthorityError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise B09AuthorityError(
                "AUTHORITY_HASH_MISMATCH",
                f"candidate reference closure: {error}",
            ) from error

    def _read_candidate_reference(
        self,
        ref: dict[str, Any],
        *,
        expected_type: str,
    ) -> dict[str, Any]:
        try:
            b01_validate_record_ref(ref, expected_type=expected_type)
            record = self._immutable_reader(deepcopy(ref))
            b01_validate_record(record)
        except B09AuthorityError:
            raise
        except B01ContractError as error:
            raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        except Exception as error:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT",
                f"{expected_type} read failed: {error}",
            ) from error
        if record["record_type"] != expected_type:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", f"{expected_type} type mismatch"
            )
        if not _ref_equal(b01_record_ref(record), ref):
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", f"{expected_type} ref mismatch"
            )
        return deepcopy(record)

    def _attach_immutables(self, collected: dict[str, Any]) -> dict[str, Any]:
        route = collected["active_route"]
        proposals: list[dict[str, Any]] = []
        patch_proposal: dict[str, Any] | None = None
        if route is not None:
            proposal_refs = [
                entry["causal_hint_proposal_ref"]
                for entry in route["payload"]["causal_hint_routes"]
                if entry["route"] == "ROUTE_TO_B09"
            ]
            seen: set[bytes] = set()
            for ref in sorted(proposal_refs, key=canonical_bytes):
                key = canonical_bytes(ref)
                if key in seen:
                    raise B09AuthorityError(
                        "AUTHORITY_REFERENCE_CONFLICT", "duplicate proposal route"
                    )
                seen.add(key)
                proposals.append(
                    self._read_exact(ref, expected_type="M3_CAUSAL_HINT_PROPOSAL")
                )
            patch_proposal = self._read_exact(
                collected["validation_receipt"]["payload"]["input_binding"][
                    "patch_proposal_ref"
                ],
                expected_type="M3_PATCH_PROPOSAL",
            )
        reference_records = self._candidate_reference_records(
            [collected["base_candidate"], collected["current_candidate"]]
        )
        current_segment_indexes = [
            record
            for record in reference_records
            if _ref_equal(
                b01_record_ref(record),
                collected["current_candidate"]["payload"]["segment_index_ref"],
            )
        ]
        if len(current_segment_indexes) != 1:
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "current segment index closure"
            )
        current_segment_index = current_segment_indexes[0]
        try:
            for candidate in (
                collected["base_candidate"],
                collected["current_candidate"],
            ):
                validate_candidate_version(
                    candidate,
                    allow_child=candidate["payload"]["parent_candidate_version_ref"]
                    is not None,
                    reference_records=reference_records,
                )
            validate_mutable_pointer(
                collected["current_pointer"],
                candidate=collected["current_candidate"],
                reference_records=reference_records,
            )
            validate_segment_index_snapshot(current_segment_index)
            if route is not None and patch_proposal is not None:
                base_segment_indexes = [
                    record
                    for record in reference_records
                    if _ref_equal(
                        b01_record_ref(record),
                        collected["base_candidate"]["payload"]["segment_index_ref"],
                    )
                ]
                if len(base_segment_indexes) != 1:
                    raise B09AuthorityError(
                        "AUTHORITY_REFERENCE_CONFLICT", "base segment index closure"
                    )
                input_binding = collected["validation_receipt"]["payload"][
                    "input_binding"
                ]
                b02_binding = input_binding["b02_scope_binding"]
                context = {
                    "reference_records": [
                        record
                        for record in reference_records
                        if record["record_type"] != "M3_SEGMENT_INDEX_SNAPSHOT"
                    ],
                    "segment_index": base_segment_indexes[0],
                    "candidate_version": collected["base_candidate"],
                    "lineage_locators": [],
                    "evidence_locators": [],
                    "segment_inputs": [],
                }
                diagnostic_refs = [
                    binding["diagnostic_ref"]
                    for binding in b02_binding["diagnostic_state_bindings"]
                ]
                coverage_refs = b02_binding["coverage_observation_refs"]
                source_slice_refs = patch_proposal["payload"].get(
                    "authorized_source_slice_refs", []
                )
                for proposal in proposals:
                    validate_causal_record(
                        proposal,
                        context=context,
                        diagnostic_refs=diagnostic_refs,
                        coverage_refs=coverage_refs,
                        source_slice_refs=source_slice_refs,
                    )
        except (
            B01ContractError,
            B04ContractError,
            B06ContractError,
            KeyError,
            TypeError,
        ) as error:
            raise B09AuthorityError("AUTHORITY_HASH_MISMATCH", str(error)) from error
        if (
            current_segment_index["payload"]["chapter_revision_ref"]
            != collected["current_candidate"]["payload"]["chapter_revision_ref"]
        ):
            raise B09AuthorityError(
                "AUTHORITY_REFERENCE_CONFLICT", "candidate/segment index scope"
            )
        result = deepcopy(collected)
        result["causal_hint_proposals"] = proposals
        result["current_segment_index"] = current_segment_index
        return result

    def read(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_request(request)
        try:
            with self._b05_store.serialization():
                first_records = self._b05_store.read_records()
                first_projection = self._b05_projection(first_records)
                first_freshness = _validate_freshness(self._freshness_reader())
                first = self._collect_shared(
                    request=request,
                    records=first_records,
                    projection=first_projection,
                    freshness=first_freshness,
                )
                first = self._attach_immutables(first)
                second_records = self._b05_store.read_records()
                second_projection = self._b05_projection(second_records)
                second_freshness = _validate_freshness(self._freshness_reader())
                try:
                    second = self._collect_shared(
                        request=request,
                        records=second_records,
                        projection=second_projection,
                        freshness=second_freshness,
                    )
                except B09AuthorityError as error:
                    raise B09AuthorityError(
                        "AUTHORITY_DRIFT", error.detail or error.reason_code
                    ) from error
            if canonical_bytes(first["authority_fingerprint"]) != canonical_bytes(
                second["authority_fingerprint"]
            ):
                raise B09AuthorityError(
                    "AUTHORITY_DRIFT", "authority fingerprint changed"
                )
            snapshot = {
                "request": deepcopy(request),
                "b05_records": deepcopy(first_records),
                **first,
            }
            if set(snapshot) != SNAPSHOT_KEYS:
                raise B09AuthorityError(
                    "AUTHORITY_STATE_INCOHERENT", "snapshot closure"
                )
            return deepcopy(snapshot)
        except (B09AuthorityError, B09ContractError):
            raise
        except B05ContractError as error:
            reason = (
                "AUTHORITY_HASH_MISMATCH"
                if "HASH" in error.code or "INVALID" in error.code
                else "AUTHORITY_READER_UNAVAILABLE"
            )
            raise B09AuthorityError(reason, error.code) from error
        except Exception as error:
            raise B09AuthorityError(
                "AUTHORITY_READER_UNAVAILABLE", str(error)
            ) from error
