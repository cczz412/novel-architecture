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

import z68_revised_request_pilot as z68  # noqa: E402
import z83_program_side_repair_pilot as z83  # noqa: E402
import z94_local_semantic_live as live  # noqa: E402


@pytest.fixture(autouse=True)
def _freeze_z94_release_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "z94_release_authority.json"
    state_path.write_text(
        json.dumps(
            {
                "current_step": {
                    "task_id": live.TENCENT_RELEASE_TASK_ID,
                    "step2_release_allowed": True,
                    "authority_time": live.TENCENT_RELEASE_AUTHORITY_TIME,
                    "step2_release_authority": {
                        "authority_kind": "cz_direct_provider_override",
                        "provider": "tencent_tokenhub",
                        "model": live.TENCENT_MODEL,
                        "temperature": 0.2,
                        "max_tokens": 8000,
                        "full_rerun_required": True,
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live, "CURRENT_STATE", state_path)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.origin = datetime(2026, 7, 23, 18, 0, tzinfo=timezone(timedelta(hours=8)))

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += float(seconds)

    def iso(self) -> str:
        return (self.origin + timedelta(seconds=self.value)).isoformat(
            timespec="seconds"
        )


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.raw


def _prepared(tmp_path: Path) -> Path:
    run_dir = tmp_path / live.TENCENT_RUN_NAME
    live.prepare(run_dir, allow_test_run_dir=True)
    return run_dir


def test_prepare_refreezes_tencent_compatibility_profile_and_preserves_sources(
    tmp_path: Path,
) -> None:
    before = {
        "step1": z68.tree_fingerprint(live.STEP1_RUN),
        "retry13": z68.tree_fingerprint(live.SOURCE_RETRY13),
    }
    run_dir = _prepared(tmp_path)
    first = live.verify_preflight(run_dir, allow_test_run_dir=True)
    second = live.verify_preflight(run_dir, allow_test_run_dir=True)
    assert first == second
    assert first["logical_request_count"] == 32
    assert first["retry13_outer_difference_count"] == 4
    assert first["step1_messages_unchanged"] is True
    assert before == {
        "step1": z68.tree_fingerprint(live.STEP1_RUN),
        "retry13": z68.tree_fingerprint(live.SOURCE_RETRY13),
    }
    preflight = live.read_json(run_dir / "repair/atomic_preflight.json")
    root_preflight = live.read_json(run_dir / "preflight.json")
    assert root_preflight["protected_before"] == z83.protected_snapshot()
    assert preflight["z94_step2_supply_slice_only"] is False
    assert preflight["z94_tencent_provider_override"] is True
    for row in preflight["rows"]:
        body = live.read_json(run_dir / row["prepared_request_path"])
        assert body["model"] == live.TENCENT_MODEL
        assert body["temperature"] == 0.2
        assert body["max_tokens"] == 8000
        assert body["n"] == 1
        assert body["thinking"] == {"type": "enabled"}
        assert "response_format" not in body
        assert "reasoning_effort" not in body
    assert not (run_dir / "repair/call_attempts.jsonl").exists()


def test_fake_transport_runs_32_fresh_requests_and_materializes_175_events(
    tmp_path: Path,
) -> None:
    run_dir = _prepared(tmp_path)
    plan = live._validate_plan(run_dir)
    clock = FakeClock()
    sent: list[str] = []

    def opener(request: object, *, timeout: int) -> FakeResponse:
        del timeout
        if request.get_method() == "GET":  # type: ignore[attr-defined]
            return FakeResponse(
                json.dumps(
                    {
                        "object": "list",
                        "data": [{"id": live.TENCENT_MODEL, "status": "online"}],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
        task = plan["tasks"][len(sent)]
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        sent.append(str(task["task_id"]))
        content = json.dumps(
            {
                "event": f"测试人物完成第{len(sent)}项明确行动并取得结果。",
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
                            "message": {
                                "role": "assistant",
                                "reasoning_content": "逐条核对局部窗口与锚目录。",
                                "content": content,
                            },
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

    with mock.patch.dict(
        os.environ, {"TENCENT_TOKENHUB_API_KEY": "test-only"}, clear=True
    ):
        with mock.patch.object(live.retry13, "_now_iso", side_effect=clock.iso):
            metrics = live.run_repair(
                run_dir,
                opener=opener,
                sleeper=clock.sleep,
                monotonic=clock.monotonic,
                jitter=lambda: 0.0,
                allow_test_run_dir=True,
            )
    assert sent == [str(task["task_id"]) for task in plan["tasks"]]
    assert metrics["logical_request_count"] == 32
    assert metrics["final_event_count"] == 175
    assert metrics["rewritten_descendant_count"] == 32
    assert len(list((run_dir / "repair/checkpoints").iterdir())) == 32
    assert len(z68.read_jsonl(run_dir / "repair/usage.jsonl")) == 32
    assert len(list((run_dir / "repair/tencent_reasoning_audit").glob("*.json"))) == 32
    assert live.read_json(run_dir / "repair/tencent_reasoning_audit_summary.json")[
        "logical_request_count"
    ] == 32
    assert not (run_dir / "repair/hard_stop.json").exists()
    review = z83.build_review(run_dir, phase="final")
    assert review["phase"] == "final"
    assert len(list((run_dir / "final_review/inspector_batches").glob("ch*.json"))) == 3
    assert (
        z83._retry05_system_prompt_suffix(run_dir)
        == z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
    )
    inspector_bodies: list[dict] = []

    def inspector_opener(request: object, *, timeout: int) -> FakeResponse:
        assert timeout == 300
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        inspector_bodies.append(body)
        assert body["messages"][0]["content"].endswith(
            z83.RETRY05_VERBATIM_QUOTE_SYSTEM_LINE
        )
        payload = json.loads(body["messages"][1]["content"])
        results = []
        for item in payload["items"]:
            anchor = item["anchors"][0]
            results.append(
                {
                    "item_id": item["item_id"],
                    "decision": "pass_candidate",
                    "support": "direct_support",
                    "rule_ids": ["SEM-01"],
                    "evidence": [
                        {
                            "anchor_id": anchor["anchor_id"],
                            "quote": anchor["quote"],
                            "reason": "假网回归逐字引用冻结短引。",
                        }
                    ],
                    "confidence": 0.9,
                    "needs_strong_review": False,
                    "reason": "只作分流候选。",
                }
            )
        return FakeResponse(
            json.dumps(
                {
                    "model": z83.api_transport.PINNED_MODEL,
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "contract_version": (
                                            z83.pipeline_inspector.MODEL_OUTPUT_CONTRACT
                                        ),
                                        "results": results,
                                    },
                                    ensure_ascii=False,
                                ),
                            },
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
        with mock.patch.object(
            z83,
            "_retry13_no_redirect_open",
            side_effect=inspector_opener,
        ):
            inspector_receipt = z83.run_inspector(
                run_dir,
                phase="final",
                allow_test_run_dir=True,
            )
    assert inspector_receipt["logical_model_calls"] == 3
    assert len(inspector_bodies) == 3
    assert z83.require_inspector_complete(run_dir, phase="final") == inspector_receipt


def test_missing_key_stops_before_claim_or_network(tmp_path: Path) -> None:
    run_dir = _prepared(tmp_path)
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(z83.ZBatchError, match="缺少 TENCENT_TOKENHUB_API_KEY"):
            live.run_repair(run_dir, allow_test_run_dir=True)
    assert not (run_dir / "repair/retry13_run_claim.json").exists()
    assert not (run_dir / "repair/call_attempts.jsonl").exists()


def test_structure_overreach_hard_stops_and_does_not_send_later_tasks(
    tmp_path: Path,
) -> None:
    run_dir = _prepared(tmp_path)
    clock = FakeClock()
    attempts = 0

    def opener(request: object, *, timeout: int) -> FakeResponse:
        nonlocal attempts
        del timeout
        if request.get_method() == "GET":  # type: ignore[attr-defined]
            return FakeResponse(
                json.dumps(
                    {
                        "object": "list",
                        "data": [{"id": live.TENCENT_MODEL, "status": "online"}],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
        attempts += 1
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        content = json.dumps(
            [
                {"event": "越权返回了数组容器。", "anchor_ids": ["E0001"]}
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return FakeResponse(
            json.dumps(
                {
                    "model": body["model"],
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "reasoning_content": "结构检查。",
                                "content": content,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )

    with mock.patch.dict(
        os.environ, {"TENCENT_TOKENHUB_API_KEY": "test-only"}, clear=True
    ):
        with mock.patch.object(live.retry13, "_now_iso", side_effect=clock.iso):
            with pytest.raises(z83.ZBatchError, match="根字段必须且只能"):
                live.run_repair(
                    run_dir,
                    opener=opener,
                    sleeper=clock.sleep,
                    monotonic=clock.monotonic,
                    jitter=lambda: 0.0,
                    allow_test_run_dir=True,
                )
    assert attempts == 1
    assert (run_dir / "repair/hard_stop.json").is_file()
    assert not (run_dir / "repair/01_extract").exists()
    top = live.read_json(run_dir / "run_manifest.json")
    assert top["status"] == "repair_hard_stop"
    assert top["authoritative_ticket"] == "repair/hard_stop.json"


def test_test_directory_cannot_reach_real_network_without_injected_opener(
    tmp_path: Path,
) -> None:
    run_dir = _prepared(tmp_path)
    with mock.patch.dict(
        os.environ, {"TENCENT_TOKENHUB_API_KEY": "test-only"}, clear=True
    ):
        with pytest.raises(z83.ZBatchError, match="必须显式注入假网络"):
            live.run_repair(run_dir, allow_test_run_dir=True)
    assert not (run_dir / "repair/retry13_run_claim.json").exists()
