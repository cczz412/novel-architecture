from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import z83_program_side_repair_pilot as z83  # noqa: E402
import z83_retry13_atomic_repair as retry13  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.origin = datetime(2026, 7, 22, 18, 0, tzinfo=timezone(timedelta(hours=8)))

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += float(seconds)

    def iso(self) -> str:
        return (self.origin + timedelta(seconds=self.value)).isoformat(timespec="seconds")


class FakeResponse:
    status = 200
    headers: dict[str, str] = {"Content-Type": "application/json"}

    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.raw


def test_retry13_full_fake_network_path_builds_32_checkpoints_and_175_events(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / retry13.RUN_NAME
    z83.prepare(
        run_dir,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
        allow_test_run_dir=True,
    )
    z83.seed_main_samples(
        run_dir,
        ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_SOURCE_NAME,
        allow_test_run_dir=True,
    )

    class NoCallTransport:
        def call(self, **_: object) -> None:
            raise AssertionError("retry13主样张只准复用retry03，不得发网")

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.ApiTransport,
            "from_bundle",
            return_value=NoCallTransport(),
        ):
            z83.run_main(run_dir, allow_test_run_dir=True)
    z83.verify_main(run_dir, allow_test_run_dir=True)
    z83.build_review(run_dir, phase="main")
    with mock.patch.object(retry13.z83, "verify_main", return_value={}):
        plan = retry13.create_plan(run_dir)
    retry13.preflight(run_dir)
    first_verify = retry13.verify_preflight(run_dir)
    second_verify = retry13.verify_preflight(run_dir)
    assert first_verify == second_verify

    preflight = z83.read_json(run_dir / "repair/atomic_preflight.json")
    rows_by_task = {str(row["task_id"]): row for row in preflight["rows"]}
    clock = FakeClock()
    sent_task_ids: list[str] = []
    expected_timeout = z83.api_transport.TransportRoute.from_mapping(
        z83.load_bundle(run_dir).route
    ).timeout_seconds

    def opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == expected_timeout
        task = plan["tasks"][len(sent_task_ids)]
        task_id = str(task["task_id"])
        prepared_path = run_dir / str(rows_by_task[task_id]["prepared_request_path"])
        prepared_body = json.loads(prepared_path.read_text(encoding="utf-8"))
        assert request.data == json.dumps(  # type: ignore[attr-defined]
            prepared_body, ensure_ascii=False
        ).encode("utf-8")
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        clock.sleep(1.0)
        sent_task_ids.append(task_id)
        content = json.dumps(
            {
                "event": f"测试人物完成第{len(sent_task_ids)}项明确动作并得到结果。",
                "anchor_ids": list(task["required_anchor_ids"]),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return FakeResponse(
            json.dumps(
                {
                    "model": body["model"],
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "total_tokens": 120,
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(retry13, "_now_iso", side_effect=clock.iso):
            metrics = retry13.run_atomic_requests(
                run_dir,
                opener=opener,
                sleeper=clock.sleep,
                monotonic=clock.monotonic,
                jitter=lambda: 0.0,
            )
    assert sent_task_ids == [str(task["task_id"]) for task in plan["tasks"]]
    assert metrics["logical_request_count"] == 32
    assert metrics["network_attempts"] == 32
    assert metrics["main_event_count"] == 156
    assert metrics["final_event_count"] == 175
    assert metrics["rewritten_descendant_count"] == 32
    assert not (run_dir / "repair/hard_stop.json").exists()
    assert len(list((run_dir / "repair/checkpoints").iterdir())) == 32
    assert len(retry13._rebuild_all_task_results(run_dir=run_dir, plan=plan)) == 32
    lineage = z83.verify_call_lineage(run_dir, allow_test_run_dir=True)
    assert lineage["status"] == "pass"
    assert lineage["repair_parent_rewrite_count"] == 13
    assert lineage["repair_logical_request_count"] == 32
    assert lineage["repair_materialized_event_count"] == 175


def test_retry13_invalid_supplier_envelope_hard_stops_before_formal_materialization(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / retry13.RUN_NAME
    z83.prepare(
        run_dir,
        inspector_max_tokens=z83.INSPECTOR_COMPAT_MAX_TOKENS,
        allow_test_run_dir=True,
    )
    z83.seed_main_samples(
        run_dir,
        ROOT / "runs" / z83.APPROVED_COMPLETED_SEED_SOURCE_NAME,
        allow_test_run_dir=True,
    )

    class NoCallTransport:
        def call(self, **_: object) -> None:
            raise AssertionError("retry13主样张只准复用retry03，不得发网")

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(
            z83.api_transport.ApiTransport,
            "from_bundle",
            return_value=NoCallTransport(),
        ):
            z83.run_main(run_dir, allow_test_run_dir=True)
    z83.verify_main(run_dir, allow_test_run_dir=True)
    z83.build_review(run_dir, phase="main")
    with mock.patch.object(retry13.z83, "verify_main", return_value={}):
        retry13.create_plan(run_dir)
    retry13.preflight(run_dir)
    clock = FakeClock()

    def opener(request: object, *, timeout: int) -> FakeResponse:
        del timeout
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        clock.sleep(1.0)
        invalid_choices = [
            {
                "message": {"role": "assistant", "content": "{}"},
                "finish_reason": "stop",
            },
            {
                "message": {"role": "assistant", "content": "{}"},
                "finish_reason": "stop",
            },
        ]
        return FakeResponse(
            json.dumps(
                {
                    "model": body["model"],
                    "choices": invalid_choices,
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )

    with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "test-only"}, clear=True):
        with mock.patch.object(retry13, "_now_iso", side_effect=clock.iso):
            with pytest.raises(z83.ZBatchError, match="choices 必须且只能有1项"):
                retry13.run_atomic_requests(
                    run_dir,
                    opener=opener,
                    sleeper=clock.sleep,
                    monotonic=clock.monotonic,
                    jitter=lambda: 0.0,
                )
    hard_stop = z83.read_json(run_dir / "repair/hard_stop.json")
    assert hard_stop["completed_task_count"] == 0
    assert hard_stop["network_attempts"] == 1
    assert hard_stop["partial_formal_repair_written"] is False
    assert not (run_dir / "repair/01_extract").exists()
    assert not (run_dir / "final").exists()
