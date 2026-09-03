"""Focused B-10 authority, aggregation, projection, and boundary tests."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
B07_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b07_local_recovery_stop_r01"
B08_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
for candidate in (
    REPOSITORY_ROOT,
    B01_ROOT,
    B05_ROOT,
    B06_ROOT,
    B07_ROOT,
    B08_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    record_ref as b01_record_ref,
)
from work.ccz57_m3_b01_candidate_version_r03_5.fixtures import (  # noqa: E402
    _initialize as initialize_b01_fixture,
    _load_state as load_b01_state,
)
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    canonical_bytes,
    record_ref,
    sha256_value,
)
from b07_contracts import (  # noqa: E402
    B07ContractError,
    state_hash_value,
)
from work.ccz57_m3_b08_segment_terminal_r01.fixtures import (  # noqa: E402
    build_environment,
)

from b10_authority_reader import ChapterProgressAuthorityReader  # noqa: E402
from b10_contracts import (  # noqa: E402
    AUTHOR_VIEW_KEYS,
    B10ContractError,
    PURPOSE,
    exact_segment_key,
    validate_author_view,
    validate_segment_set_closure,
)
from current_chapter_progress_view import (  # noqa: E402
    _author_action,
    _processing_state,
    project_author_progress,
    read_current_chapter_progress,
)


class CurrentSegmentIndexReader:
    def __init__(self, record: dict[str, Any]) -> None:
        self.record = deepcopy(record)
        self.read_count = 0

    def __call__(self, _request: dict[str, Any]) -> dict[str, Any]:
        self.read_count += 1
        return deepcopy(self.record)


class DriftReader(ChapterProgressAuthorityReader):
    __slots__ = ("_callback",)

    def __init__(self, *, callback: Callable[[], None], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._callback = callback

    def _between_reads(self) -> None:
        self._callback()


def _immutable_reader(records: list[dict[str, Any]]) -> Any:
    indexed = {
        canonical_bytes(b01_record_ref(record)): deepcopy(record)
        for record in records
    }

    def read(ref: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(indexed[canonical_bytes(ref)])

    read.indexed = indexed  # type: ignore[attr-defined]
    return read


def _world(root: Path) -> SimpleNamespace:
    env = build_environment(root / "upstream")
    b01 = env.b07.b06.b05.b01_reader.read_scope()
    segment_index = b01["segment_index_record"]
    current_index_reader = CurrentSegmentIndexReader(segment_index)
    immutable_reader = _immutable_reader(b01["candidate_reference_records"])
    kwargs = {
        "shared_database_path": env.store._database_path,
        "current_segment_index_reader": current_index_reader,
        "immutable_reader": immutable_reader,
        "b08_authority_reader": env.authority,
    }
    reader = ChapterProgressAuthorityReader(**kwargs)
    request = {
        "project_scope_id": env.project_scope_id,
        "chapter_revision_ref": deepcopy(
            segment_index["payload"]["chapter_revision_ref"]
        ),
        "segment_index_ref": b01_record_ref(segment_index),
        "purpose": PURPOSE,
    }
    return SimpleNamespace(
        env=env,
        segment_index=segment_index,
        current_index_reader=current_index_reader,
        immutable_reader=immutable_reader,
        reader_kwargs=kwargs,
        reader=reader,
        request=request,
    )


def _read(world: SimpleNamespace) -> dict[str, Any]:
    return read_current_chapter_progress(world.reader, world.request)


def _segment(view: dict[str, Any], seg: int = 1) -> dict[str, Any]:
    return next(
        item for item in view["segments"] if item["exact_segment_key"]["seg"] == seg
    )


def _advance(
    world: SimpleNamespace,
    *,
    status: str,
    phase: str = "FINALIZING",
    wait_kind: str | None = None,
) -> dict[str, Any]:
    state = world.env.state()
    return world.env.b07.b07.advance(
        project_scope_id=world.env.project_scope_id,
        run_id=world.env.run_id,
        operation_id=f"b10-{status.lower()}",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status=status,
        target_phase=phase,
        wait_kind=wait_kind,
        authority_reader=world.env.b07.authority,
    )


def _classification(
    product_result: str, delivery: str
) -> dict[str, Any]:
    candidate_count = 1 if product_result == "CANDIDATES_READY" else 0
    complete = delivery in {"COMPLETE", "EMPTY_VALID"}
    return {
        "classification_policy_ref": deepcopy(
            _world_classification_template["classification_policy_ref"]
        ),
        "classification_policy_hash": _world_classification_template[
            "classification_policy_hash"
        ],
        "product_result": product_result,
        "terminal_delivery": delivery,
        "reason_code": f"B10_{product_result}",
        "candidate_count": candidate_count,
        "expected_unit_count": 1,
        "covered_unit_count": 1 if complete else 0,
        "missing_unit_count": 0 if complete else 1,
        "coverage_complete": complete,
    }


_world_classification_template: dict[str, Any] = {}


def _terminalize(
    world: SimpleNamespace,
    *,
    product_result: str,
    delivery: str,
    stop_reason_code: str = "AUTHOR_ABORTED",
) -> dict[str, Any]:
    global _world_classification_template
    _world_classification_template = deepcopy(world.env.authority.classification)
    world.env.authority.classification = _classification(product_result, delivery)
    result = world.env.publish(f"b10-{product_result.lower()}")
    if delivery in {"COMPLETE", "EMPTY_VALID"}:
        world.env.bind_succeeded(result)
    else:
        world.env.bind_then_stop(result, stop_reason_code=stop_reason_code)
    return result


def _set_new_state(world: SimpleNamespace) -> None:
    state = deepcopy(world.env.state())
    state["status"] = "NEW"
    state["phase"] = "EXTRACTING"
    state["state_hash"] = state_hash_value(state)
    with sqlite3.connect(world.env.store._database_path) as connection:
        connection.execute(
            "UPDATE b07_current_run_states SET status = ?, state_json = ? "
            "WHERE project_scope_id = ? AND run_id = ?",
            (
                "NEW",
                canonical_bytes(state),
                world.env.project_scope_id,
                world.env.run_id,
            ),
        )
        connection.commit()


def _advance_pointer_generation(world: SimpleNamespace) -> None:
    with sqlite3.connect(world.env.store._database_path) as connection:
        raw = connection.execute(
            "SELECT pointer_json FROM current_pointers WHERE logical_pointer_key = ?",
            (world.env.b07.b06.live_pointer["logical_pointer_key"],),
        ).fetchone()[0]
        pointer = json.loads(bytes(raw).decode("utf-8"))
        pointer["generation"] += 1
        connection.execute(
            "UPDATE current_pointers SET pointer_json = ? "
            "WHERE logical_pointer_key = ?",
            (canonical_bytes(pointer), pointer["logical_pointer_key"]),
        )
        connection.commit()


def _install_seg2_run(
    world: SimpleNamespace, root: Path
) -> tuple[str, str, Callable[[], dict[str, Any]]]:
    fixture_root = root / "b01-seg2"
    initialize_b01_fixture(
        fixture_root,
        seg=2,
        operation_id="fixture-operation-seg2",
        raw_items=[],
    )
    state = load_b01_state(fixture_root)
    candidate = next(
        record
        for record in state["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    pointer = next(iter(state["pointers"].values()))
    assert candidate["payload"]["segment_index_ref"] == world.request[
        "segment_index_ref"
    ]
    with sqlite3.connect(world.env.store._database_path) as connection:
        connection.execute(
            "INSERT INTO candidate_versions(ref_hash, record_json) VALUES (?, ?)",
            (
                sha256_value(pointer["current_candidate_version_ref"]),
                canonical_bytes(candidate),
            ),
        )
        connection.execute(
            "INSERT INTO current_pointers(logical_pointer_key, project_scope_id, "
            "pointer_json) VALUES (?, ?, ?)",
            (
                pointer["logical_pointer_key"],
                pointer["project_scope_id"],
                canonical_bytes(pointer),
            ),
        )
        connection.commit()
    authority = deepcopy(world.env.b07.authority.snapshot)
    authority["candidate_pointer_key"] = pointer["logical_pointer_key"]
    authority["observed_pointer_generation"] = pointer["generation"]
    authority["observed_candidate_version_ref"] = deepcopy(
        pointer["current_candidate_version_ref"]
    )
    authority["segment_scope_hash"] = sha256_value({"seg": 2})
    logical_run_key = "logical-run:fixture-seg2"
    run_id = "run-b07-fixture-seg2"
    def authority_reader() -> dict[str, Any]:
        return deepcopy(authority)

    world.env.b07.b07.open_run(
        project_scope_id=world.env.project_scope_id,
        logical_run_key=logical_run_key,
        run_id=run_id,
        run_kind="FACT_EXTRACTION_REPAIR",
        operation_id="open-seg2",
        authority_reader=authority_reader,
    )
    return logical_run_key, run_id, authority_reader


def _complete_run(
    world: SimpleNamespace,
    run_id: str,
    operation: str,
    authority_reader: Callable[[], dict[str, Any]],
) -> None:
    state = world.env.b07.b07.read_state(world.env.project_scope_id, run_id)
    state = world.env.b07.b07.advance(
        project_scope_id=world.env.project_scope_id,
        run_id=run_id,
        operation_id=f"prepare-{operation}",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="ACTIVE",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=authority_reader,
    )
    result = world.env.store.publish(
        project_scope_id=world.env.project_scope_id,
        run_id=run_id,
        operation_id=operation,
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
    )
    world.env.b07.b07.advance(
        project_scope_id=world.env.project_scope_id,
        run_id=run_id,
        operation_id=f"bind-{operation}",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        target_status="SUCCEEDED",
        target_phase="FINALIZING",
        wait_kind=None,
        authority_reader=authority_reader,
        component_observation=result["component_observation"],
    )


def test_package_imports_share_b10_exception_identity() -> None:
    package = "work.ccz57_m3_b10_chapter_candidate_progress_view_r01"
    contracts = importlib.import_module(f"{package}.b10_contracts")
    authority = importlib.import_module(f"{package}.b10_authority_reader")
    view = importlib.import_module(f"{package}.current_chapter_progress_view")
    assert authority.B10AuthorityError is contracts.B10AuthorityError
    assert view.B10AuthorityError is contracts.B10AuthorityError


@pytest.mark.parametrize("status", ["NEW", "ACTIVE", "B06_OUTCOME_PENDING"])
def test_nonterminal_processing_states_are_running(tmp_path: Path, status: str) -> None:
    world = _world(tmp_path)
    if status == "NEW":
        _set_new_state(world)
    elif status == "B06_OUTCOME_PENDING":
        world.env.b07.prepare_b06(world.env.state())
    view = _read(world)
    assert view["availability"] == "READY"
    assert _segment(view)["segment_status"] == "RUNNING"
    assert _segment(view, 2)["authority_witness"]["kind"] == (
        "AUTHORITATIVE_NO_CURRENT_RUN"
    )


def test_waiting_local_preserves_author_action(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _advance(world, status="WAITING_LOCAL", wait_kind="AUTHOR_ACTION")
    view = _read(world)
    assert _segment(view)["segment_status"] == "WAITING"
    assert view["author_action_required"] is True
    assert view["author_action_kind"] == "REVIEW_INPUT"


@pytest.mark.parametrize(
    ("stop_reason", "expected_action", "action_required"),
    [
        ("AUTHOR_ABORTED", "RESTART", True),
        ("ROUTE_STOP", "WAIT", False),
        ("LOCAL_STORAGE_INTEGRITY_FAILURE", "WAIT", False),
    ],
)
def test_blocked_segment_preserves_stop_receipt_action(
    tmp_path: Path,
    stop_reason: str,
    expected_action: str,
    action_required: bool,
) -> None:
    world = _world(tmp_path)
    _terminalize(
        world,
        product_result="EXTRACTION_FAILED",
        delivery="BLOCKED",
        stop_reason_code=stop_reason,
    )
    view = _read(world)

    assert _segment(view)["segment_status"] == "BLOCKED"
    assert view["author_action_kind"] == expected_action
    assert view["author_action_required"] is action_required


@pytest.mark.parametrize(
    "stop_reason",
    ["ROUTE_STOP", "LOCAL_STORAGE_INTEGRITY_FAILURE"],
)
def test_safe_stop_action_wins_over_partial_review(
    tmp_path: Path, stop_reason: str
) -> None:
    world = _world(tmp_path)
    _terminalize(
        world,
        product_result="INSUFFICIENT_EVIDENCE",
        delivery="PARTIAL",
        stop_reason_code=stop_reason,
    )
    view = _read(world)

    assert _segment(view)["segment_status"] == "PARTIAL"
    assert view["author_action_kind"] == "WAIT"
    assert view["author_action_required"] is False


@pytest.mark.parametrize(
    ("actions", "expected"),
    [
        (["RESTART"], "RESTART"),
        (["RESTART", "REVIEW_INPUT"], "REVIEW_INPUT"),
        (["RESTART", "REFRESH"], "REFRESH"),
        (["RESTART", "REFRESH", "WAIT"], "WAIT"),
    ],
)
def test_multi_segment_author_action_priority_is_order_independent(
    actions: list[str], expected: str
) -> None:
    segments = [
        {
            "segment_status": "BLOCKED",
            "run_state_or_null": {"author_action_kind": action},
        }
        for action in actions
    ]
    required, action = _author_action(segments, "BLOCKED")
    reversed_required, reversed_action = _author_action(
        list(reversed(segments)), "BLOCKED"
    )

    assert (required, action) == (expected != "WAIT", expected)
    assert (reversed_required, reversed_action) == (required, action)


@pytest.mark.parametrize("terminal_status", ["SUCCEEDED", "STOPPED"])
def test_direct_terminal_without_b08_is_rejected_and_view_stays_running(
    tmp_path: Path, terminal_status: str
) -> None:
    world = _world(tmp_path)
    state = world.env.state()
    with pytest.raises(B07ContractError, match="B07_TERMINAL_OBSERVATION_REQUIRED"):
        if terminal_status == "SUCCEEDED":
            _advance(world, status="SUCCEEDED")
        else:
            world.env.b07.b07.stop(
                project_scope_id=world.env.project_scope_id,
                run_id=world.env.run_id,
                operation_id="b10-stop-without-terminal",
                expected_run_epoch=state["run_epoch"],
                expected_state_revision=state["state_revision"],
                stop_reason_code="AUTHOR_ABORTED",
                stop_class="LOCAL_CONTROL",
                stop_source="B10_FIXTURE",
                authority_reader=world.env.b07.authority,
            )
    view = _read(world)
    segment = _segment(view)
    assert segment["segment_status"] == "RUNNING"
    assert segment["authority_witness"]["kind"] == "B07_CURRENT_RUN"
    assert view["candidate_processing_state"] == "IN_PROGRESS"
    assert view["has_blockers"] is False
    assert world.env.state() == state


def test_resume_epoch_does_not_reuse_old_terminal(tmp_path: Path) -> None:
    world = _world(tmp_path)
    world.env.publish("old-epoch-terminal")
    state = world.env.state()
    world.env.b07.b07.resume(
        project_scope_id=world.env.project_scope_id,
        run_id=world.env.run_id,
        operation_id="resume-for-b10",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        authority_reader=world.env.b07.authority,
    )
    view = _read(world)
    segment = _segment(view)
    assert segment["segment_status"] == "RUNNING"
    assert segment["terminal_record_ref_or_null"] is None


def test_reopen_generation_does_not_reuse_old_terminal(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _terminalize(world, product_result="EXTRACTION_FAILED", delivery="BLOCKED")
    world.env.b07.b07.reopen(
        project_scope_id=world.env.project_scope_id,
        source_run_id=world.env.run_id,
        new_run_id="run-b10-reopened",
        operation_id="reopen-for-b10",
        authority_reader=world.env.b07.authority,
    )
    view = _read(world)
    segment = _segment(view)
    assert segment["run_state_or_null"]["logical_run_generation"] == 2
    assert segment["segment_status"] == "RUNNING"
    assert segment["terminal_record_ref_or_null"] is None


@pytest.mark.parametrize(
    ("product_result", "delivery", "expected"),
    [
        ("CANDIDATES_READY", "COMPLETE", "COMPLETE"),
        ("NO_CHANGE", "COMPLETE", "COMPLETE"),
        ("LEGAL_ZERO", "EMPTY_VALID", "EMPTY_VALID"),
        ("NOT_APPLICABLE", "EMPTY_VALID", "EMPTY_VALID"),
        ("INSUFFICIENT_EVIDENCE", "PARTIAL", "PARTIAL"),
        ("EXTRACTION_FAILED", "BLOCKED", "BLOCKED"),
    ],
)
def test_all_b08_product_results_map_without_reinterpretation(
    tmp_path: Path,
    product_result: str,
    delivery: str,
    expected: str,
) -> None:
    world = _world(tmp_path)
    _terminalize(world, product_result=product_result, delivery=delivery)
    view = _read(world)
    segment = _segment(view)
    assert segment["segment_status"] == expected
    assert segment["product_result_or_null"] == product_result
    assert segment["terminal_delivery_or_null"] == delivery
    assert segment["terminal_currentness_or_null"] == "CURRENT"
    if expected in {"COMPLETE", "EMPTY_VALID"}:
        assert view["counts"]["completed_segments"] == 1
    else:
        assert view["counts"]["completed_segments"] == 0


def test_complete_requires_every_expected_segment(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _terminalize(world, product_result="CANDIDATES_READY", delivery="COMPLETE")
    _, run_id, authority_reader = _install_seg2_run(world, tmp_path)
    _complete_run(world, run_id, "complete-seg2", authority_reader)
    view = _read(world)
    assert [item["segment_status"] for item in view["segments"]] == [
        "COMPLETE",
        "COMPLETE",
    ]
    assert view["candidate_processing_state"] == "COMPLETE"
    assert view["complete_claim_allowed"] is True
    assert view["counts"]["completed_segments"] == 2


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["NOT_TRACKED_YET", "NOT_TRACKED_YET"], "NOT_TRACKED"),
        (["COMPLETE", "NOT_TRACKED_YET"], "IN_PROGRESS"),
        (["WAITING", "WAITING"], "WAITING"),
        (["PARTIAL", "WAITING"], "PARTIAL"),
        (["BLOCKED", "WAITING"], "BLOCKED"),
        (["STALE", "PARTIAL"], "BLOCKED"),
        (["EMPTY_VALID", "COMPLETE"], "COMPLETE"),
    ],
)
def test_mixed_state_precedence_is_order_independent(
    statuses: list[str], expected: str
) -> None:
    assert _processing_state(statuses) == expected
    assert _processing_state(list(reversed(statuses))) == expected


def test_segment_set_closure_rejects_duplicate_missing_and_extra(
    tmp_path: Path,
) -> None:
    world = _world(tmp_path)
    payload = world.segment_index["payload"]
    keys = [
        exact_segment_key(
            project_scope_id=payload["project_scope_id"],
            author_workspace_logical_key=payload[
                "author_workspace_logical_key"
            ],
            chapter_revision_ref=payload["chapter_revision_ref"],
            segment_index_ref=world.request["segment_index_ref"],
            seg=seg,
        )
        for seg in (1, 2)
    ]
    validate_segment_set_closure(keys, list(reversed(keys)))
    with pytest.raises(B10ContractError, match="B10_SEGMENT_SET_MISMATCH"):
        validate_segment_set_closure(keys, [keys[0], keys[0]])
    with pytest.raises(B10ContractError, match="B10_SEGMENT_SET_MISMATCH"):
        validate_segment_set_closure(keys, [keys[0]])
    extra = deepcopy(keys[1])
    extra["seg"] = 3
    with pytest.raises(B10ContractError, match="B10_SEGMENT_SET_MISMATCH"):
        validate_segment_set_closure(keys, [keys[0], extra])


def test_request_for_noncurrent_segment_index_is_unavailable(tmp_path: Path) -> None:
    world = _world(tmp_path)
    world.request["chapter_revision_ref"] = deepcopy(
        world.request["chapter_revision_ref"]
    )
    world.request["chapter_revision_ref"]["revision_no"] += 1
    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["candidate_processing_state"] is None
    assert view["counts"] is None
    assert view["segments"] == []


def test_b07_mirrored_column_tamper_fails_closed(tmp_path: Path) -> None:
    world = _world(tmp_path)
    with sqlite3.connect(world.env.store._database_path) as connection:
        connection.execute(
            "UPDATE b07_current_run_states SET status = 'WAITING_LOCAL' "
            "WHERE run_id = ?",
            (world.env.run_id,),
        )
        connection.commit()
    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_STATE_INCOHERENT"


def test_b07_record_hash_tamper_fails_closed(tmp_path: Path) -> None:
    world = _world(tmp_path)
    with sqlite3.connect(world.env.store._database_path) as connection:
        raw = connection.execute(
            "SELECT state_json FROM b07_current_run_states WHERE run_id = ?",
            (world.env.run_id,),
        ).fetchone()[0]
        state = json.loads(bytes(raw).decode("utf-8"))
        state["phase"] = "CHECKING"
        connection.execute(
            "UPDATE b07_current_run_states SET state_json = ? WHERE run_id = ?",
            (canonical_bytes(state), world.env.run_id),
        )
        connection.commit()
    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_HASH_MISMATCH"


def test_missing_stop_receipt_hides_counts_and_actions(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _terminalize(world, product_result="EXTRACTION_FAILED", delivery="BLOCKED")
    with sqlite3.connect(world.env.store._database_path) as connection:
        connection.execute("DELETE FROM b07_stop_receipts")
        connection.commit()

    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_REFERENCE_CONFLICT"
    assert view["counts"] is None
    assert view["author_action_kind"] == "NONE"


def test_tampered_stop_receipt_hides_counts_and_actions(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _terminalize(world, product_result="EXTRACTION_FAILED", delivery="BLOCKED")
    with sqlite3.connect(world.env.store._database_path) as connection:
        raw = connection.execute(
            "SELECT receipt_json FROM b07_stop_receipts"
        ).fetchone()[0]
        receipt = json.loads(bytes(raw).decode("utf-8"))
        receipt["payload"]["resume_disposition"] = "DO_NOT_RESUME"
        connection.execute(
            "UPDATE b07_stop_receipts SET receipt_json = ?",
            (canonical_bytes(receipt),),
        )
        connection.commit()

    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_HASH_MISMATCH"
    assert view["counts"] is None


def test_stop_receipt_scope_mismatch_hides_counts_and_actions(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _terminalize(world, product_result="EXTRACTION_FAILED", delivery="BLOCKED")
    state = deepcopy(world.env.state())
    with sqlite3.connect(world.env.store._database_path) as connection:
        raw = connection.execute(
            "SELECT receipt_json FROM b07_stop_receipts"
        ).fetchone()[0]
        receipt = json.loads(bytes(raw).decode("utf-8"))
        receipt["payload"]["logical_run_key"] = "logical-run:wrong"
        receipt["record_id"] = f"run-stop:{sha256_value(receipt['payload'])}"
        receipt["record_hash"] = sha256_value(
            {key: value for key, value in receipt.items() if key != "record_hash"}
        )
        state["stop_receipt_ref"] = record_ref(receipt)
        state["state_hash"] = state_hash_value(state)
        connection.execute(
            "UPDATE b07_stop_receipts SET stop_receipt_id = ?, receipt_json = ?",
            (receipt["record_id"], canonical_bytes(receipt)),
        )
        connection.execute(
            "UPDATE b07_current_run_states SET stop_receipt_id = ?, state_json = ?",
            (receipt["record_id"], canonical_bytes(state)),
        )
        connection.commit()

    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_STATE_INCOHERENT"
    assert view["counts"] is None


def test_unbound_current_terminal_keeps_active_run_running(tmp_path: Path) -> None:
    world = _world(tmp_path)
    world.env.publish("unbound-current-terminal")
    view = _read(world)
    segment = _segment(view)
    assert segment["terminal_currentness_or_null"] == "RUN_NOT_PUBLISHED"
    assert segment["segment_status"] == "RUNNING"


def test_unbound_terminal_with_superseded_pointer_is_stale(tmp_path: Path) -> None:
    world = _world(tmp_path)
    world.env.publish("unbound-stale-terminal")
    _advance_pointer_generation(world)
    view = _read(world)
    segment = _segment(view)
    assert segment["terminal_currentness_or_null"] == "POINTER_STALE"
    assert segment["segment_status"] == "STALE"
    assert view["has_blockers"] is True
    assert view["author_action_kind"] == "REFRESH"


def test_nonterminal_run_with_superseded_pointer_is_stale(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _advance_pointer_generation(world)
    view = _read(world)
    assert _segment(view)["segment_status"] == "STALE"
    assert view["candidate_processing_state"] == "IN_PROGRESS"
    assert view["has_blockers"] is True
    assert view["author_action_kind"] == "REFRESH"


def test_two_current_runs_for_one_segment_fail_closed(tmp_path: Path) -> None:
    world = _world(tmp_path)
    world.env.b07.b07.open_run(
        project_scope_id=world.env.project_scope_id,
        logical_run_key="logical-run:duplicate-segment",
        run_id="run-duplicate-segment",
        run_kind="FACT_EXTRACTION_REPAIR",
        operation_id="open-duplicate-segment",
        authority_reader=world.env.b07.authority,
    )
    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_REFERENCE_CONFLICT"


def test_negative_no_run_witness_participates_in_double_read_fence(
    tmp_path: Path,
) -> None:
    world = _world(tmp_path)
    fired = False

    def create_run() -> None:
        nonlocal fired
        if fired:
            return
        fired = True
        _install_seg2_run(world, tmp_path)

    reader = DriftReader(callback=create_run, **world.reader_kwargs)
    view = read_current_chapter_progress(reader, world.request)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_DRIFT"
    assert view["counts"] is None
    assert view["segments"] == []


def test_terminal_state_with_missing_b08_record_fails_closed(tmp_path: Path) -> None:
    world = _world(tmp_path)
    global _world_classification_template
    _world_classification_template = deepcopy(world.env.authority.classification)
    world.env.authority.classification = _classification(
        "INSUFFICIENT_EVIDENCE", "PARTIAL"
    )
    result = world.env.publish("terminal-to-hide")
    world.env.bind_then_stop(result)
    with sqlite3.connect(world.env.store._database_path) as connection:
        connection.execute("DELETE FROM b08_segment_terminal_receipts")
        connection.commit()

    view = _read(world)
    assert view["availability"] == "UNAVAILABLE"
    assert view["reason_code"] == "AUTHORITY_REFERENCE_CONFLICT"
    assert view["counts"] is None


def test_author_projection_is_exact_whitelist_and_contains_no_internal_identity(
    tmp_path: Path,
) -> None:
    world = _world(tmp_path)
    projected = project_author_progress(_read(world))
    assert set(projected) == AUTHOR_VIEW_KEYS
    validate_author_view(projected)
    encoded = json.dumps(projected, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        "record_id",
        "record_hash",
        "run_id",
        "generation",
        "epoch",
        "revision",
        "pointer",
        "diagnostic",
        "route",
        "token",
        "cost",
        "model",
        "prompt",
        "debug",
        "sqlite",
    ):
        assert forbidden not in encoded


def test_unavailable_projection_does_not_leak_reason_or_counts(tmp_path: Path) -> None:
    world = _world(tmp_path)
    world.current_index_reader.record["record_hash"] = "0" * 64
    internal = _read(world)
    projected = project_author_progress(internal)
    assert projected["availability"] == "UNAVAILABLE"
    assert projected["candidate_processing_state"] is None
    assert projected["total_segments"] is None
    assert "reason_code" not in projected


def test_reader_performs_two_current_segment_index_reads(tmp_path: Path) -> None:
    world = _world(tmp_path)
    _read(world)
    assert world.current_index_reader.read_count == 2


def test_b10_has_no_writer_record_table_or_forbidden_runtime_dependency() -> None:
    source_files = [
        ROOT / "b10_contracts.py",
        ROOT / "b10_authority_reader.py",
        ROOT / "current_chapter_progress_view.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in source_files]
    class_names = {
        node.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }
    assert not any("Writer" in name or "Record" in name for name in class_names)
    assert "CREATE TABLE" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE " not in source
    assert "DELETE FROM" not in source
    for forbidden in (
        "ccz57_m3_b09",
        "ccz57_m3_b11",
        "ccz57_m3_b12",
        "requests",
        "urllib",
        "httpx",
        "openai",
        "anthropic",
    ):
        assert forbidden not in source.lower()


def test_public_read_has_no_caller_supplied_status_or_authority_fields() -> None:
    signature = inspect.signature(read_current_chapter_progress)
    assert list(signature.parameters) == ["authority_reader", "request"]
    reader_signature = inspect.signature(ChapterProgressAuthorityReader.read)
    assert list(reader_signature.parameters) == ["self", "request"]
