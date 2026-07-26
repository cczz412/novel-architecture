from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c13_execution_runner as runner  # noqa: E402


pytestmark = pytest.mark.v02


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_run_plan_resigns_exact_90_nodes_and_freezes_conservative_stops() -> None:
    plan = runner.build_run_plan()

    assert len(plan["nodes"]) == 90
    assert Counter(row["provider_id"] for row in plan["nodes"]) == {
        "qianwen_platform": 30,
        "volcengine_ark": 30,
        "tencent_tokenhub": 30,
    }
    assert [row["sequence"] for row in plan["nodes"]] == list(range(1, 91))
    assert len({row["node_id"] for row in plan["nodes"]}) == 90
    assert len({row["dispatch_id"] for row in plan["nodes"]}) == 90
    assert plan["run_policy"] == {
        "total_node_hard_cap": 90,
        "per_provider_node_hard_cap": 30,
        "max_transport_attempts_per_node": 1,
        "max_transport_retries_per_node": 0,
        "consecutive_transport_failure_hard_stop": 1,
        "quality_retry_allowed": False,
        "change_question_on_retry_allowed": False,
        "automatic_provider_fallback_allowed": False,
    }


def test_prepare_keeps_execute_closed_and_binds_every_external_proof(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "V02_C13_r06_prepare"
    receipt = runner.prepare(run_dir)
    template = _read_json(
        run_dir / "prepared/execute_ticket_TEMPLATE.json"
    )

    assert receipt["status"] == "PREPARED_ZERO_CALL_EXECUTE_TICKET_REQUIRED"
    assert receipt["model_api_requests"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["key_values_read"] == 0
    assert template["execute_allowed"] is False
    assert template["status"] == "NOT_APPROVED_TEMPLATE_ONLY"
    assert template["narrow_git_freeze"]["pushed"] is False
    assert set(template["zero_call_rehearsal_receipt"]) == {
        "path",
        "sha256",
        "run_id",
        "runner_sha256",
        "run_plan_sha256",
        "node_order_sha256",
    }
    assert len(template["provider_gate_receipts"]) == 3
    for row in template["provider_gate_receipts"]:
        assert row["attempt_no"] == 1
        assert "attempt_ledger_path" in row
        assert "raw_response_path" in row
        assert "receipt_path" in row


def test_full_rehearsal_is_zero_call_and_covers_all_required_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("零调用预演不得进入真运输或密钥读取")

    monkeypatch.setattr(runner, "_load_live_keys_after_ticket", forbidden)
    monkeypatch.setattr(runner, "_live_http_transport", forbidden)

    run_dir = tmp_path / "V02_C13_r06_rehearsal"
    receipt = runner.rehearse(run_dir)

    assert receipt["status"] == "PASS_ZERO_CALL_FULL_CHAIN_REHEARSAL"
    assert receipt["node_total"] == 90
    assert receipt["per_provider_node_total"] == {
        "qianwen_platform": 30,
        "volcengine_ark": 30,
        "tencent_tokenhub": 30,
    }
    assert receipt["model_api_requests"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["key_values_read"] == 0
    assert receipt["paused_after_complete_checkpoint_total"] == 45
    assert receipt["resumed_from_node"] == "C13-R06-046"
    assert all(receipt["scenarios"].values())
    assert runner.audit_resume_position(run_dir)["status"] == "COMPLETE_90"


def test_live_entry_rejects_missing_execute_ticket_before_key_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "V02_C13_r06_unsigned"
    runner.prepare(run_dir)
    key_read_reached = False

    def forbidden_key_read(_plan: object) -> object:
        nonlocal key_read_reached
        key_read_reached = True
        raise AssertionError("执行票之前不得读取密钥")

    monkeypatch.setattr(
        runner,
        "_load_live_keys_after_ticket",
        forbidden_key_read,
    )

    with pytest.raises(
        runner.C13ExecutionError,
        match="必须先提供全局 execute 票",
    ) as caught:
        runner.run_live(run_dir, execute_ticket_path=None)

    assert caught.value.reason_code == (
        "execute_ticket_required_before_live_transport"
    )
    assert key_read_reached is False


def test_internal_executor_cannot_claim_live_without_execute_ticket(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "V02_C13_r06_direct_live_bypass"
    runner.prepare(run_dir)
    transport_reached = False

    def forbidden_transport(
        _node: object,
        _request_raw: bytes,
        _attempt_no: int,
    ) -> runner.TransportOutcome:
        nonlocal transport_reached
        transport_reached = True
        raise AssertionError("总执行票之前不得触发任何真运输注入点")

    with pytest.raises(
        runner.C13ExecutionError,
        match="必须先提供全局 execute 票",
    ) as caught:
        runner.execute_with_transport(
            run_dir,
            transport=forbidden_transport,
            execution_kind="LIVE_AUTHORIZED",
        )

    assert caught.value.reason_code == (
        "execute_ticket_required_before_live_transport"
    )
    assert transport_reached is False


def test_checkpoint_seal_rejects_attempt_reservation_drift(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "V02_C13_r06_attempt_seal"
    runner.prepare(run_dir)
    runner.execute_with_transport(
        run_dir,
        transport=runner.RehearsalTransport("full"),
        execution_kind="REHEARSAL_FAKE_TRANSPORT",
        stop_after_completed=1,
    )
    first_node = runner.build_run_plan()["nodes"][0]
    reservation_path = runner._checkpoint_paths(
        run_dir,
        first_node,
    )["attempt_reservation"]
    reservation = _read_json(reservation_path)
    reservation["request_sha256"] = "0" * 64
    reservation_path.write_text(
        json.dumps(reservation, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(
        runner.C13ExecutionError,
        match="工件漂移：attempt_reservation",
    ):
        runner.audit_resume_position(run_dir)


def test_checkpoint_seal_rejects_task_b_dual_ledger_drift(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "V02_C13_r06_task_b_seal"
    runner.prepare(run_dir)
    runner.execute_with_transport(
        run_dir,
        transport=runner.RehearsalTransport("full"),
        execution_kind="REHEARSAL_FAKE_TRANSPORT",
        stop_after_completed=2,
    )
    second_node = runner.build_run_plan()["nodes"][1]
    claim_path = runner._task_b_evidence_paths(
        run_dir,
        second_node,
    )["task_b_claim_ledger"]
    claim = _read_json(claim_path)
    claim["observation"]["claim_count"] = 999
    claim_path.write_text(
        json.dumps(claim, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(
        runner.C13ExecutionError,
        match="工件漂移：task_b_claim_ledger",
    ):
        runner.audit_resume_position(run_dir)


def test_unexpected_transport_exception_writes_authoritative_hard_stop(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "V02_C13_r06_transport_exception"
    runner.prepare(run_dir)

    def broken_transport(
        _node: object,
        _request_raw: bytes,
        _attempt_no: int,
    ) -> runner.TransportOutcome:
        raise RuntimeError("synthetic transport crash")

    with pytest.raises(runner.C13TransportHardStop) as caught:
        runner.execute_with_transport(
            run_dir,
            transport=broken_transport,
            execution_kind="REHEARSAL_FAKE_TRANSPORT",
        )

    hard_stop = _read_json(run_dir / "runtime/hard_stop.json")
    assert caught.value.reason_code == "UNEXPECTED_TRANSPORT_EXCEPTION"
    assert hard_stop["reason_code"] == "UNEXPECTED_TRANSPORT_EXCEPTION"
    assert hard_stop["attempted_node_may_be_resent"] is False
    assert runner.audit_resume_position(run_dir)["status"] == (
        "HARD_STOP_NOT_RESUMABLE"
    )


def test_unexpected_judgment_exception_keeps_raw_response_and_hard_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "V02_C13_r06_judgment_exception"
    runner.prepare(run_dir)
    transport = runner.RehearsalTransport("full")

    def broken_judgment(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic parser crash")

    monkeypatch.setattr(runner, "_evaluate_response", broken_judgment)
    with pytest.raises(runner.C13TransportHardStop) as caught:
        runner.execute_with_transport(
            run_dir,
            transport=transport,
            execution_kind="REHEARSAL_FAKE_TRANSPORT",
        )

    first_node = runner.build_run_plan()["nodes"][0]
    node_root = (
        run_dir
        / "runtime/nodes"
        / runner._safe_node_dir(first_node)
        / "attempts/attempt_01"
    )
    hard_stop = _read_json(run_dir / "runtime/hard_stop.json")
    assert caught.value.reason_code == "UNEXPECTED_JUDGMENT_EXCEPTION"
    assert (node_root / "01_raw_response.raw").is_file()
    assert hard_stop["reason_code"] == "UNEXPECTED_JUDGMENT_EXCEPTION"
    assert hard_stop["attempted_node_may_be_resent"] is False


def test_runner_source_keeps_live_network_behind_ticket_gate() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")

    assert source.index("_validate_execute_ticket(") < source.index(
        "_load_live_keys_after_ticket("
    )
    assert source.index("_load_live_keys_after_ticket(") < source.index(
        "_live_http_transport("
    )
    assert "git\", \"diff-tree\"" not in source
    assert '"diff-tree"' in source
    assert "verify_saved_ticket(" in source


def test_provider_gate_time_must_follow_git_freeze_and_precede_execute() -> None:
    committed = datetime(2026, 7, 26, 8, 0, tzinfo=timezone.utc)
    started = committed + timedelta(seconds=1)
    finished = started + timedelta(seconds=1)
    approved = finished + timedelta(seconds=1)

    runner._require_provider_gate_time_order(
        provider_id="qianwen_platform",
        git_committed_at=committed,
        started_at=started,
        finished_at=finished,
        execute_approved_at=approved,
    )
    with pytest.raises(
        runner.C13ExecutionError,
        match="Git冻结<发起<=结束<=execute批准",
    ):
        runner._require_provider_gate_time_order(
            provider_id="qianwen_platform",
            git_committed_at=started,
            started_at=committed,
            finished_at=finished,
            execute_approved_at=approved,
        )
