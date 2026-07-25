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
import v02_c6_control_runner as c6  # noqa: E402


pytestmark = pytest.mark.v02


def _isolated_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    run_dir = tmp_path / c6.EXPECTED_RUN_NAME
    monkeypatch.setattr(c6, "C6_RUN_DIR", run_dir)
    return run_dir


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


class ControlOpener:
    def __init__(
        self,
        *,
        invalid_case: str | None = None,
        response_model: str = live.PINNED_MODEL,
    ) -> None:
        self.invalid_case = invalid_case
        self.response_model = response_model
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, timeout: int) -> FakeResponse:
        body = json.loads(request.data.decode("utf-8"))
        self.calls.append(body)
        rendered = json.dumps(body, ensure_ascii=False)
        case_id = next(
            case_id
            for case_id in c6.CASE_ORDER
            if f"EV-C{prep.CASE_BY_ID[case_id].unit:04d}-" in rendered
        )
        chapter = prep.CASE_BY_ID[case_id].unit
        catalog = c6.read_json(c6._source_catalog_path(case_id))
        anchor_id = catalog["entries"][0]["anchor_id"]
        if case_id == self.invalid_case:
            anchor_id = "E9999"
        payload = {
            "schema_version": "z-event-v1",
            "chapter": chapter,
            "events": [
                {
                    "event_id": f"EV-C{chapter:04d}-01",
                    "event": "人物明确完成了一项安排",
                    "anchors": [{"anchor_id": anchor_id}],
                }
            ],
        }
        response = {
            "model": self.response_model,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(payload, ensure_ascii=False),
                        "reasoning_content": "完成中性事件清点",
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
        return FakeResponse(
            json.dumps(response, ensure_ascii=False).encode("utf-8")
        )


def test_prepare_changes_only_max_tokens_and_is_double_run_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)

    result = c6.prepare_run(run_dir)

    assert result["status"] == "PASS_C6_CONTROL_PREPARED"
    assert result["from_max_tokens"] == 16000
    assert result["to_max_tokens"] == 65536
    ledger = c6.read_json(run_dir / "prepared/C6_request_delta_ledger.json")
    assert ledger["changed_request_fields"] == ["body.max_tokens"]
    for row in ledger["rows"]:
        assert row["messages_byte_equivalent"] is True
        assert row["request_shell_equal"] is True
        assert row["body_except_max_tokens_equal"] is True
        case_id = row["case_id"]
        source = c6.read_json(c6._source_request_path(case_id))
        prepared = c6.read_json(
            run_dir / f"prepared/main/{case_id}/request_artifact.json"
        )
        assert source["body"]["messages"] == prepared["body"]["messages"]
        assert source["body"]["max_tokens"] == 16000
        assert prepared["body"]["max_tokens"] == 65536
        assert {
            key: value for key, value in source.items() if key != "body"
        } == {
            key: value for key, value in prepared.items() if key != "body"
        }
    verification = c6.read_json(
        run_dir / "prepared/C6_mechanical_verification.json"
    )
    assert verification["vectors_equal"] is True
    assert verification["first_vector"] == verification["second_vector"]


def test_run_sends_each_control_once_and_seals_five_piece_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    c6.prepare_run(run_dir)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = ControlOpener()

    result = c6.run_control(run_dir, opener=opener)

    assert result["status"] == (
        "CONTROL_THREE_CHAPTERS_MECHANICAL_PASS_PENDING_C6_MAPPING"
    )
    assert result["logical_samples"] == 3
    assert result["network_attempts"] == 3
    assert len(opener.calls) == 3
    assert all(body["max_tokens"] == 65536 for body in opener.calls)
    assert all(body["temperature"] == 0.2 for body in opener.calls)
    for case_id in c6.CASE_ORDER:
        completion = c6.audit_sample(run_dir, case_id=case_id)
        assert completion["status"] == "MECHANICAL_PASS_CANDIDATE_ONLY"
        checkpoint = (
            run_dir / f"samples/main/{case_id}/checkpoint"
        )
        assert sorted(path.name for path in checkpoint.iterdir()) == [
            "01_request.json",
            "02_response.json",
            "03_mechanical.json",
            "04_usage_attempts.json",
            "05_seal.json",
        ]
        usage_attempts = c6.read_json(checkpoint / "04_usage_attempts.json")
        assert len(usage_attempts["attempt_reservations"]) == 1
        assert usage_attempts["attempt_reservations"][0][
            "logical_request_id"
        ] == f"V02-C6-CONTROL-{case_id}"
        mechanical = c6.read_json(
            run_dir / f"samples/main/{case_id}/mechanical.json"
        )
        assert mechanical["z_event_validation"][
            "outside_catalog_anchor_count"
        ] == 0
        assert mechanical["z_event_validation"]["event_ids_contiguous"] is True
    assert c6.run_control(run_dir, opener=opener) == result
    assert len(opener.calls) == 3


def test_directory_outside_exact_run_path_is_rejected(tmp_path: Path) -> None:
    alternate = tmp_path / c6.EXPECTED_RUN_NAME

    with pytest.raises(c6.C6ControlHardStop, match="运行目录必须是"):
        c6.prepare_run(alternate)


def test_outside_catalog_anchor_hard_stops_after_first_case_and_cannot_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    c6.prepare_run(run_dir)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = ControlOpener(invalid_case=c6.CASE_ORDER[0])

    with pytest.raises(c6.C6ControlHardStop, match="目录外锚"):
        c6.run_control(run_dir, opener=opener)

    assert len(opener.calls) == 1
    hard_stop = c6.read_json(run_dir / "hard_stop.json")
    assert hard_stop["reason_code"] == "z_event_anchor_outside_catalog"
    assert hard_stop["network_attempts"] == 1
    assert hard_stop["rerun_allowed"] is False
    assert c6.status(run_dir)["attempts_by_case"] == {
        c6.CASE_ORDER[0]: 1,
        c6.CASE_ORDER[1]: 0,
        c6.CASE_ORDER[2]: 0,
    }
    with pytest.raises(c6.C6ControlHardStop, match="已硬停"):
        c6.run_control(run_dir, opener=opener)
    assert len(opener.calls) == 1


def test_short_event_summary_is_rejected_by_active_event_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    c6.prepare_run(run_dir)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")

    class ShortSummaryOpener(ControlOpener):
        def __call__(self, request: Any, timeout: int) -> FakeResponse:
            response = super().__call__(request, timeout)
            envelope = json.loads(response._raw.decode("utf-8"))
            payload = json.loads(envelope["choices"][0]["message"]["content"])
            payload["events"][0]["event"] = "过关"
            envelope["choices"][0]["message"]["content"] = json.dumps(
                payload,
                ensure_ascii=False,
            )
            return FakeResponse(
                json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            )

    opener = ShortSummaryOpener()
    with pytest.raises(c6.C6ControlHardStop, match="事件摘要长度非法"):
        c6.run_control(run_dir, opener=opener)
    assert len(opener.calls) == 1


def test_response_model_must_equal_frozen_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    c6.prepare_run(run_dir)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = ControlOpener(response_model="deepseek-v4-flash-build")

    with pytest.raises(c6.C6ControlHardStop, match="不是冻结型号"):
        c6.run_control(run_dir, opener=opener)
    assert len(opener.calls) == 1
    assert c6.read_json(run_dir / "hard_stop.json")["reason_code"] == (
        "response_model_mismatch"
    )


def test_payload_rejects_empty_events_discontinuous_ids_and_missing_anchors() -> None:
    case_id = c6.CASE_ORDER[0]
    chapter = prep.CASE_BY_ID[case_id].unit
    catalog = c6.read_json(c6._source_catalog_path(case_id))
    valid = {
        "schema_version": "z-event-v1",
        "chapter": chapter,
        "events": [
            {
                "event_id": f"EV-C{chapter:04d}-01",
                "event": "人物完成一项安排",
                "anchors": [{"anchor_id": catalog["entries"][0]["anchor_id"]}],
            }
        ],
    }
    assert c6.validate_z_event_payload(
        case_id=case_id,
        payload=valid,
        catalog=catalog,
    )["status"] == "PASS_Z_EVENT_V1_MECHANICAL"

    empty = {**valid, "events": []}
    with pytest.raises(c6.C6ControlHardStop, match="events为空"):
        c6.validate_z_event_payload(
            case_id=case_id,
            payload=empty,
            catalog=catalog,
        )

    discontinuous = json.loads(json.dumps(valid, ensure_ascii=False))
    discontinuous["events"][0]["event_id"] = f"EV-C{chapter:04d}-02"
    with pytest.raises(c6.C6ControlHardStop, match="事件ID不连续"):
        c6.validate_z_event_payload(
            case_id=case_id,
            payload=discontinuous,
            catalog=catalog,
        )

    missing_anchor = json.loads(json.dumps(valid, ensure_ascii=False))
    missing_anchor["events"][0]["anchors"] = []
    with pytest.raises(c6.C6ControlHardStop, match="无冻结证据ID"):
        c6.validate_z_event_payload(
            case_id=case_id,
            payload=missing_anchor,
            catalog=catalog,
        )


def test_loaded_key_is_scanned_before_send(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    c6.prepare_run(run_dir)
    key = "test-secret-not-real"
    monkeypatch.setenv(live.PINNED_KEY_ENV, key)
    (run_dir / "prepared/key_leak.txt").write_text(key, encoding="utf-8")
    opener = ControlOpener()

    with pytest.raises(c6.C6ControlHardStop, match="检出密钥"):
        c6.run_control(run_dir, opener=opener)
    assert opener.calls == []
