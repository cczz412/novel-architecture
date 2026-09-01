"""Focused B-08 terminal, currentness, idempotency, and boundary tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest

from b08_contracts import (
    B08ContractError,
    guard_runtime_event,
    terminal_component_observation,
    validate_adapter_ready_view,
    validate_exact_current_view,
    validate_terminal_record,
)
from b08_store import B08SegmentTerminalStore, B08TerminalReadService
from fixtures import build_environment
from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import sha256_value

ROOT = Path(__file__).resolve().parent


def _ref(result: dict) -> dict:
    return result["terminal_record_ref"]


def test_schema_adds_one_b08_object_table_and_no_view_writer(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "schema")
    names = set(env.store.schema_objects())

    assert "b08_segment_terminal_receipts" in names
    assert not {
        "b08_exact_current_views",
        "b08_adapter_ready_views",
        "b08_stale_records",
        "b08_checkpoints",
        "b08_commit_intents",
    } & names
    assert env.store.visible_counts() == {"b08_segment_terminal_receipts": 0}
    with sqlite3.connect(env.store._database_path) as connection:
        schema_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'b08_segment_terminal_receipts'"
        ).fetchone()[0]
    assert "UNIQUE(project_scope_id, logical_run_key" not in schema_sql


def test_publish_uses_authority_reader_and_returns_one_terminal_object(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "publish")
    result = env.publish()
    record = result["terminal_record"]

    validate_terminal_record(record)
    assert env.authority.read_count == 1
    assert result["component_observation"] == terminal_component_observation(record)
    locator = result["component_observation"]["component_artifact_ref"][
        "workspace_relative_locator"
    ]
    raw = env.store.read_artifact_bytes(locator)
    assert hashlib.sha256(raw).hexdigest() == result["component_observation"][
        "component_artifact_ref"
    ]["artifact_sha256"]
    assert env.store.visible_counts() == {"b08_segment_terminal_receipts": 1}
    assert record["payload"]["b06_merge_receipt_ref_or_null"] is None
    assert record["payload"]["pointer_binding"]["candidate_origin"] == "ROOT"


def test_publish_signature_has_no_caller_owned_result_or_coverage_fields() -> None:
    parameters = set(inspect.signature(B08SegmentTerminalStore.publish).parameters)
    assert parameters == {
        "self",
        "project_scope_id",
        "run_id",
        "operation_id",
        "expected_run_epoch",
        "expected_state_revision",
    }
    assert set(inspect.signature(B08TerminalReadService.__init__).parameters) == {
        "self",
        "store",
    }


def test_terminalization_key_is_recomputed_from_run_and_segment_bindings(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "terminal-key")
    record = deepcopy(env.publish()["terminal_record"])
    record["payload"]["terminalization_key"] = "0" * 64
    record["record_id"] = f"segment-terminal:{'0' * 64}"
    record["record_hash"] = sha256_value(
        {key: value for key, value in record.items() if key != "record_hash"}
    )
    with pytest.raises(B08ContractError, match="B08_TERMINALIZATION_KEY_INVALID"):
        validate_terminal_record(record)


def test_unbound_terminal_is_historical_but_not_published(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "unbound")
    result = env.publish()
    exact = env.reader.exact_current_view(_ref(result))
    adapter = env.reader.adapter_ready_view(_ref(result))

    validate_exact_current_view(exact)
    validate_adapter_ready_view(adapter)
    assert exact["currentness"] == "RUN_NOT_PUBLISHED"
    assert exact["reason_code"] == "B07_OBSERVATION_NOT_BOUND"
    assert adapter["ready"] is False
    assert adapter["candidate_version_ref_or_null"] is None


def test_b07_binding_makes_complete_terminal_current_and_adapter_ready(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "bound")
    result = env.publish()
    state = env.bind_succeeded(result)
    exact = env.reader.exact_current_view(_ref(result))
    adapter = env.reader.adapter_ready_view(_ref(result))

    assert state["status"] == "SUCCEEDED"
    assert exact["currentness"] == "CURRENT"
    assert adapter["ready"] is True
    assert adapter["candidate_version_ref_or_null"] == result["terminal_record"][
        "payload"
    ]["pointer_binding"]["current_candidate_version_ref"]


@pytest.mark.parametrize(
    ("product_result", "delivery", "candidate_count"),
    [
        ("CANDIDATES_READY", "COMPLETE", 2),
        ("NO_CHANGE", "COMPLETE", 1),
        ("LEGAL_ZERO", "EMPTY_VALID", 0),
        ("NOT_APPLICABLE", "EMPTY_VALID", 0),
    ],
)
def test_complete_result_vocabulary_is_kept_separate_from_delivery_shape(
    tmp_path: Path,
    product_result: str,
    delivery: str,
    candidate_count: int,
) -> None:
    env = build_environment(tmp_path / product_result.lower())
    env.authority.classification.update(
        {
            "product_result": product_result,
            "terminal_delivery": delivery,
            "candidate_count": candidate_count,
            "reason_code": f"{product_result}_FIXTURE",
        }
    )
    result = env.publish()
    env.bind_succeeded(result)
    exact = env.reader.exact_current_view(_ref(result))

    assert exact["product_result"] == product_result
    assert exact["terminal_delivery"] == delivery
    assert exact["currentness"] == "CURRENT"


@pytest.mark.parametrize(
    ("product_result", "delivery", "candidate_count"),
    [
        ("CANDIDATES_READY", "EMPTY_VALID", 0),
        ("LEGAL_ZERO", "COMPLETE", 1),
        ("EXTRACTION_FAILED", "COMPLETE", 0),
        ("INSUFFICIENT_EVIDENCE", "EMPTY_VALID", 0),
    ],
)
def test_illegal_result_delivery_combinations_fail_before_write(
    tmp_path: Path,
    product_result: str,
    delivery: str,
    candidate_count: int,
) -> None:
    env = build_environment(tmp_path / f"bad-{product_result.lower()}")
    env.authority.classification.update(
        {
            "product_result": product_result,
            "terminal_delivery": delivery,
            "candidate_count": candidate_count,
        }
    )
    with pytest.raises(B08ContractError, match="B08_RESULT_DELIVERY_CONFLICT"):
        env.publish()
    assert env.store.visible_counts()["b08_segment_terminal_receipts"] == 0


def test_partial_terminal_is_current_for_b10_but_closed_to_adapter(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "partial")
    env.authority.classification.update(
        {
            "product_result": "INSUFFICIENT_EVIDENCE",
            "terminal_delivery": "PARTIAL",
            "reason_code": "EVIDENCE_GAP_REMAINS",
            "expected_unit_count": 2,
            "covered_unit_count": 1,
            "missing_unit_count": 1,
            "coverage_complete": False,
        }
    )
    result = env.publish()
    env.bind_then_stop(result)
    exact = env.reader.exact_current_view(_ref(result))
    adapter = env.reader.adapter_ready_view(_ref(result))

    assert exact["currentness"] == "CURRENT"
    assert exact["terminal_delivery"] == "PARTIAL"
    assert adapter["ready"] is False


def test_same_operation_replays_and_changed_call_conflicts(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "replay")
    state = env.state()
    first = env.publish()
    replay = env.store.publish(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="b08-terminal-1",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
    )
    assert replay == first
    assert env.authority.read_count == 1

    with pytest.raises(B08ContractError, match="B08_IDEMPOTENCY_CONFLICT"):
        env.store.publish(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="b08-terminal-1",
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"] + 1,
        )
    assert env.store.visible_counts()["b08_segment_terminal_receipts"] == 1


def test_different_operation_cannot_publish_same_terminalization_key(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "same-key")
    env.publish("operation-a")
    with pytest.raises(B08ContractError, match="B08_TERMINALIZATION_CONFLICT"):
        env.publish("operation-b")
    assert env.store.visible_counts()["b08_segment_terminal_receipts"] == 1


@pytest.mark.parametrize(
    "failure_point", ["after_terminal_insert", "before_terminal_commit"]
)
def test_failure_injection_rolls_back_terminal(
    tmp_path: Path, failure_point: str
) -> None:
    env = build_environment(tmp_path / failure_point, failure_point=failure_point)
    with pytest.raises(B08ContractError, match="B08_SIMULATED_TRANSACTION_FAILURE"):
        env.publish()
    assert env.store.visible_counts()["b08_segment_terminal_receipts"] == 0


def test_two_concurrent_operations_have_one_visible_winner(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "concurrent")

    def run(operation_id: str) -> str:
        try:
            env.publish(operation_id)
        except B08ContractError as error:
            return error.code
        return "WRITTEN"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ["operation-a", "operation-b"]))

    assert results.count("WRITTEN") == 1
    assert results.count("B08_TERMINALIZATION_CONFLICT") == 1
    assert env.store.visible_counts()["b08_segment_terminal_receipts"] == 1


def test_b06_child_requires_and_binds_exact_merge_receipt(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "b06-child")
    env.commit_b06_child()
    result = env.publish()
    payload = result["terminal_record"]["payload"]

    assert payload["pointer_binding"]["candidate_origin"] == "B06_CHILD"
    assert payload["b06_merge_receipt_ref_or_null"] is not None
    assert payload["b06_merge_receipt_ref_or_null"]["record_type"] == (
        "M3_CANDIDATE_MERGE_RECEIPT"
    )


def test_resume_epoch_supersedes_unbound_old_terminal(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "resume")
    result = env.publish()
    state = env.state()
    resumed = env.b07.b07.resume(
        project_scope_id=env.project_scope_id,
        run_id=env.run_id,
        operation_id="resume-after-unbound-terminal",
        expected_run_epoch=state["run_epoch"],
        expected_state_revision=state["state_revision"],
        authority_reader=env.b07.authority,
    )
    exact = env.reader.exact_current_view(_ref(result))

    assert resumed["run_epoch"] == state["run_epoch"] + 1
    assert exact["currentness"] == "SUPERSEDED_RUN_EPOCH"


def test_reopen_generation_supersedes_stopped_old_terminal(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "reopen")
    env.authority.classification.update(
        {
            "product_result": "EXTRACTION_FAILED",
            "terminal_delivery": "BLOCKED",
            "reason_code": "EXTRACTION_FAILED_AFTER_RETRY",
            "candidate_count": 0,
            "expected_unit_count": 1,
            "covered_unit_count": 0,
            "missing_unit_count": 1,
            "coverage_complete": False,
        }
    )
    result = env.publish()
    env.bind_then_stop(result)
    reopened = env.b07.b07.reopen(
        project_scope_id=env.project_scope_id,
        source_run_id=env.run_id,
        new_run_id="run-b08-reopened",
        operation_id="reopen-after-b08",
        authority_reader=env.b07.authority,
    )
    exact = env.reader.exact_current_view(_ref(result))

    assert reopened["logical_run_generation"] == 2
    assert reopened["run_epoch"] == 0
    assert exact["currentness"] == "SUPERSEDED_RUN_GENERATION"


def test_source_pointer_and_classification_drift_are_derived_not_persisted(
    tmp_path: Path,
) -> None:
    env = build_environment(tmp_path / "drift")
    result = env.publish()
    env.bind_succeeded(result)
    record = result["terminal_record"]

    env.authority.segment_override = deepcopy(record["payload"]["segment_binding"])
    env.authority.segment_override["chapter_revision_ref"]["revision_no"] += 1
    assert env.reader.exact_current_view(_ref(result))["currentness"] == (
        "SOURCE_REVISION_STALE"
    )

    env.authority.segment_override = None
    pointer = deepcopy(record["payload"]["pointer_binding"])
    pointer["generation"] += 1
    env.authority.pointer_override = {
        "logical_pointer_key": pointer["logical_pointer_key"],
        "generation": pointer["generation"],
        "current_candidate_version_ref": deepcopy(
            pointer["current_candidate_version_ref"]
        ),
    }
    assert env.reader.exact_current_view(_ref(result))["currentness"] == "POINTER_STALE"

    env.authority.pointer_override = None
    env.authority.classification["reason_code"] = "RECLASSIFIED_BY_AUTHORITY"
    assert env.reader.exact_current_view(_ref(result))["currentness"] == (
        "AUTHORITY_DRIFT"
    )
    assert env.store.visible_counts()["b08_segment_terminal_receipts"] == 1


def test_database_reopen_reads_same_record_without_view_tables(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "database-reopen")
    result = env.publish()
    reopened = B08SegmentTerminalStore(
        env.b07.b06.store.root,
        clock=env.clock,
        authority_reader=env.authority,
    )
    reopened.initialize_schema()

    assert reopened.read_record(_ref(result)) == result["terminal_record"]
    assert reopened.visible_counts() == {"b08_segment_terminal_receipts": 1}
    assert not {"b08_exact_current_views", "b08_adapter_ready_views"} & set(
        reopened.schema_objects()
    )


def test_write_path_and_runtime_boundaries_are_fail_closed(tmp_path: Path) -> None:
    env = build_environment(tmp_path / "boundaries")
    with pytest.raises(B08ContractError, match="B08_WRITE_SET_ESCAPE"):
        B08SegmentTerminalStore(
            ROOT.parent / "ccz57_m3_b07_local_recovery_stop_r01",
            clock=env.clock,
            authority_reader=env.authority,
        )
    for event in (
        "model_api",
        "network",
        "real_novel_read",
        "candidate_version_write",
        "pointer_write",
        "b07_state_write",
        "derived_view_write",
    ):
        with pytest.raises(B08ContractError, match="B08_FORBIDDEN_RUNTIME_EVENT"):
            guard_runtime_event(event)


def test_imports_have_no_model_network_or_subprocess_execution() -> None:
    forbidden_modules = {
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "socket",
        "subprocess",
    }
    for name in ("b08_contracts.py", "b08_store.py", "fixtures.py"):
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert not (imports & forbidden_modules)
