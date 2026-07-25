from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_anchor_first_experiment as prep  # noqa: E402
import v02_anchor_first_live_runner as live  # noqa: E402
import v02_c4_transport_probe as c4  # noqa: E402


pytestmark = pytest.mark.v02


class FakeResponse:
    def __init__(self, raw: bytes, status: int = 200):
        self._raw = raw
        self.status = status
        self.headers: dict[str, str] = {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _valid_payload(case_id: str, supply_dir: Path) -> dict[str, Any]:
    case = prep.CASE_BY_ID[case_id]
    catalog = json.loads(
        (supply_dir / f"catalogs/{case_id}.json").read_text(encoding="utf-8")
    )
    anchor = catalog["entries"][0]["anchor_id"]
    return {
        "schema_version": prep.CONTRACT_VERSION,
        "chapter": case.unit,
        "events": [
            {
                "event_id": f"EV-C{case.unit:04d}-01",
                "event": "人物明确做出一项安排",
                "minimal_anchor_ids": [anchor],
                "support_obligations": [
                    {
                        "claim_span": "做出一项安排",
                        "anchor_ids": [anchor],
                        "combination": "all_required",
                    }
                ],
            }
        ],
    }


class StopOpener:
    def __init__(self, supply_dir: Path) -> None:
        self.supply_dir = supply_dir
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, timeout: int) -> FakeResponse:
        body = json.loads(request.data.decode("utf-8"))
        self.calls.append(body)
        rendered = json.dumps(body, ensure_ascii=False)
        case_id = next(
            case_id
            for case_id in live.CASE_ORDER
            if f"EV-C{prep.CASE_BY_ID[case_id].unit:04d}-" in rendered
        )
        payload = _valid_payload(case_id, self.supply_dir)
        response = {
            "model": live.PINNED_MODEL,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(payload, ensure_ascii=False),
                        "reasoning_content": "完成闭集锚核对",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "completion_tokens_details": {"reasoning_tokens": 20},
            },
        }
        return FakeResponse(json.dumps(response, ensure_ascii=False).encode("utf-8"))


class LengthOpener:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, timeout: int) -> FakeResponse:
        body = json.loads(request.data.decode("utf-8"))
        self.calls.append(body)
        response = {
            "model": live.PINNED_MODEL,
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": "{\"schema_version\":",
                        "reasoning_content": "推理触顶",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": c4.C4_MAX_TOKENS,
                "total_tokens": 100 + c4.C4_MAX_TOKENS,
                "completion_tokens_details": {"reasoning_tokens": 64000},
            },
        }
        return FakeResponse(json.dumps(response, ensure_ascii=False).encode("utf-8"))


def _prepare(tmp_path: Path) -> tuple[Path, Path]:
    supply_dir = tmp_path / "V02_C4_transport_probe"
    run_dir = tmp_path / c4.EXPECTED_RUN_NAME
    c4.prepare_run(run_dir, supply_dir)
    return run_dir, supply_dir


def test_v02_c4_accounting_uses_archived_usage_and_65536_cap() -> None:
    result = c4.build_token_accounting()

    assert result["status"] == "pass_zero_call_accounted"
    assert [row["reasoning_tokens"] for row in result["rounds"]] == [12501, 14199]
    assert [
        row["non_reasoning_completion_residual"] for row in result["rounds"]
    ] == [1393, 1802]
    assert result["complete_json_estimate"][
        "strict_arithmetic_lower_bound_for_c3_path"
    ] == 16002
    assert result["complete_json_estimate"]["exact_required_tokens_known"] is False
    assert result["platform_cap"]["max_tokens"] == 65536
    assert result["formal_gold_body_read_count"] == 0
    assert result["model_api_calls"] == 0


def test_v02_c4_supply_changes_only_max_tokens_from_sealed_c3(
    tmp_path: Path,
) -> None:
    supply_dir = tmp_path / "V02_C4_transport_probe"
    result = c4.write_or_verify_supply(supply_dir)

    assert result["status"] == "pass"
    delta = c4.read_json(supply_dir / "V02_C4_vs_sealed_C3_delta.json")
    assert delta["status"] == "pass_only_max_tokens_changed"
    assert delta["changed_request_fields"] == ["body.max_tokens"]
    for row in delta["rows"]:
        assert row["messages_byte_equivalent"] is True
        assert row["request_shell_equal"] is True
        assert row["body_except_max_tokens_equal"] is True
        assert row["from_max_tokens"] == 16000
        assert row["to_max_tokens"] == 65536


def test_v02_c4_prepare_freezes_probe_and_remaining_cases(
    tmp_path: Path,
) -> None:
    run_dir, supply_dir = _prepare(tmp_path)

    verified = c4.verify_prepared(run_dir, supply_dir)
    assert verified["status"] == "pass_c4_prepared"
    lock = c4.read_json(run_dir / "prepared/V02_C4_request_lock.json")
    assert lock["probe_case_id"] == "B02-U0039"
    assert lock["probe_max_attempts"] == 1
    assert [row["status"] for row in lock["remaining_cases"]] == [
        "FROZEN_NOT_SENT",
        "FROZEN_NOT_SENT",
    ]
    c3 = c4.read_json(
        c4.C3_SUPPLY_DIR / "requests/anchor_first/B02-U0039.json"
    )
    prepared = c4.read_json(
        run_dir / "prepared/main/B02-U0039/request_artifact.json"
    )
    assert c3["body"]["messages"] == prepared["body"]["messages"]
    assert c3["body"]["max_tokens"] == 16000
    assert prepared["body"]["max_tokens"] == 65536


def test_v02_c4_length_probe_hard_stops_once_without_later_chapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, supply_dir = _prepare(tmp_path)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = LengthOpener()

    with pytest.raises(c4.C4HardStop, match="触顶"):
        c4.run_probe(run_dir, supply_dir, opener=opener)

    assert len(opener.calls) == 1
    assert opener.calls[0]["max_tokens"] == 65536
    hard_stop = c4.read_json(run_dir / "hard_stop.json")
    assert hard_stop["reason_code"] == "finish_reason_length"
    assert hard_stop["network_attempts"] == 1
    assert hard_stop["probe_rerun_allowed"] is False
    assert hard_stop["later_chapters_sent"] is False
    assert c4.status(run_dir)["remaining_attempts"] == {
        "B03-U0041": 0,
        "B01-U0033": 0,
    }


def test_v02_c4_passed_probe_is_reused_and_only_then_sends_remaining(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, supply_dir = _prepare(tmp_path)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = StopOpener(supply_dir)

    probe = c4.run_probe(run_dir, supply_dir, opener=opener)
    assert probe["status"] == "transport_probe_pass_unlock_remaining"
    assert len(opener.calls) == 1
    assert c4.status(run_dir)["remaining_attempts"] == {
        "B03-U0041": 0,
        "B01-U0033": 0,
    }

    main = c4.continue_main(run_dir, supply_dir, opener=opener)
    assert main["status"] == "main_mechanical_pass_pending_offline_score"
    assert main["probe_case_reused_without_resend"] == "B02-U0039"
    assert len(opener.calls) == 3
    assert all(body["max_tokens"] == 65536 for body in opener.calls)
    assert len(c4._probe_attempts(run_dir)) == 1
    assert c4.status(run_dir)["remaining_attempts"] == {
        "B03-U0041": 1,
        "B01-U0033": 1,
    }


def test_v02_c4_continue_is_blocked_before_probe_gate(tmp_path: Path) -> None:
    run_dir, supply_dir = _prepare(tmp_path)

    with pytest.raises(c4.C4HardStop, match="唯一探针未过闸"):
        c4.continue_main(run_dir, supply_dir)


def test_v02_c4_supply_is_rejected_by_generic_live_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, supply_dir = _prepare(tmp_path)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = StopOpener(supply_dir)

    with pytest.raises(Exception, match="禁止走通用"):
        live.run_main(run_dir, supply_dir=supply_dir, opener=opener)

    assert opener.calls == []
    assert c4.status(run_dir)["probe_attempts"] == 0
    assert c4.status(run_dir)["remaining_attempts"] == {
        "B03-U0041": 0,
        "B01-U0033": 0,
    }
