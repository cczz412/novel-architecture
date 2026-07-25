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


def _valid_payload(case_id: str) -> dict[str, Any]:
    case = prep.CASE_BY_ID[case_id]
    catalog = live.read_json(live._source_catalog(case_id))
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


class DynamicOpener:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, timeout: int) -> FakeResponse:
        body = json.loads(request.data.decode("utf-8"))
        text = json.dumps(body, ensure_ascii=False)
        case_id = next(
            case_id
            for case_id in live.CASE_ORDER
            if f"EV-C{prep.CASE_BY_ID[case_id].unit:04d}-" in text
        )
        self.calls.append(body)
        payload = _valid_payload(case_id)
        content = json.dumps(payload, ensure_ascii=False)
        prompt_tokens = 100
        completion_tokens = 50
        response = {
            "model": live.PINNED_MODEL,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": content,
                        "reasoning_content": "完成闭集锚核对",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
        return FakeResponse(json.dumps(response, ensure_ascii=False).encode("utf-8"))


class FirstCaseMechanicalFailureOpener(DynamicOpener):
    def __call__(self, request: Any, timeout: int) -> FakeResponse:
        response = super().__call__(request, timeout)
        envelope = json.loads(response.read().decode("utf-8"))
        payload = json.loads(envelope["choices"][0]["message"]["content"])
        payload["events"][0]["support_obligations"][0][
            "claim_span"
        ] = "这一段不在事件句里"
        envelope["choices"][0]["message"]["content"] = json.dumps(
            payload, ensure_ascii=False
        )
        return FakeResponse(json.dumps(envelope, ensure_ascii=False).encode("utf-8"))


def test_prepare_sends_only_treatment_and_pins_sensenova(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    result = live.prepare_run(run_dir)

    assert result["status"] == "pass_zero_call_prepared"
    plan = live.read_json(run_dir / "prepared/run_plan.json")
    assert plan["main_calls"] == 3
    assert plan["control_requests"] == "FROZEN_NOT_SENT"
    control = live.read_json(run_dir / "prepared/control_not_sent.json")
    assert control["control_request_count"] == 3
    assert all(row["execution_status"] == "FROZEN_NOT_SENT" for row in control["requests"])
    route = live.read_json(run_dir / "prepared/provider_route.json")
    assert route["provider"] == "sensenova"
    assert route["model"] == "deepseek-v4-flash"
    assert route["tencent_v4_pro_used"] is False
    assert route["deepseek_official_api_used"] is False


def test_c3_supply_is_explicitly_pinned_without_touching_c1(
    tmp_path: Path,
) -> None:
    supply_dir = tmp_path / "c3_supply"
    artifacts = prep.build_artifacts(
        environ={},
        prompt_variant=prep.PROMPT_VARIANT_C3,
    )
    prep.write_artifacts(supply_dir, artifacts)
    run_dir = tmp_path / "run"

    result = live.prepare_run(run_dir, supply_dir)

    assert result["supply_dir"] == supply_dir.resolve().as_posix()
    assert result["supply_prompt_variant"] == prep.PROMPT_VARIANT_C3
    plan = live.read_json(run_dir / "prepared/run_plan.json")
    assert plan["supply_dir"] == supply_dir.resolve().as_posix()
    assert plan["supply_prompt_variant"] == prep.PROMPT_VARIANT_C3
    for case_id in live.CASE_ORDER:
        assert (
            run_dir / f"prepared/main/{case_id}/request_artifact.json"
        ).read_bytes() == (
            supply_dir / f"requests/anchor_first/{case_id}.json"
        ).read_bytes()

    with pytest.raises(Exception, match="准备件漂移"):
        live.verify_prepared(run_dir, live.SUPPLY_DIR)


def test_legacy_prepared_ticket_rebuild_omits_new_supply_metadata(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "legacy_run"
    live.write_json_exclusive(
        run_dir / "prepared/preflight.json",
        {
            "schema_version": "v02-anchor-first-c2-preflight.v1",
            "status": "pass_zero_call_prepared",
        },
    )

    payloads = live._prepared_payloads(run_dir)
    plan = json.loads(payloads["prepared/run_plan.json"])
    preflight = json.loads(payloads["prepared/preflight.json"])

    assert "supply_dir" not in plan
    assert "supply_prompt_variant" not in plan
    assert "supply_artifact_manifest_sha256" not in plan
    assert "supply_request_lock_sha256" not in plan
    assert "supply_dir" not in preflight
    assert "supply_prompt_variant" not in preflight


def test_main_and_stability_each_send_exactly_three_without_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    live.prepare_run(run_dir)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")

    main_opener = DynamicOpener()
    main = live.run_main(run_dir, opener=main_opener)
    assert main["logical_samples"] == 3
    assert len(main_opener.calls) == 3
    main_hashes = {
        case_id: live.sha256_file(
            run_dir / f"samples/main/{case_id}/candidate/model_json.json"
        )
        for case_id in live.CASE_ORDER
    }

    repeat_opener = DynamicOpener()
    stability = live.run_stability(run_dir, opener=repeat_opener)
    assert stability["logical_samples"] == 3
    assert len(repeat_opener.calls) == 3
    assert main_hashes == {
        case_id: live.sha256_file(
            run_dir / f"samples/main/{case_id}/candidate/model_json.json"
        )
        for case_id in live.CASE_ORDER
    }
    diagnostic = live.read_json(
        run_dir / "diagnostics/stability_disagreement.json"
    )
    assert diagnostic["main_result_selection"] == "main_only"
    assert diagnostic["stability_result_can_replace_main"] is False
    assert not (run_dir / "samples/control").exists()


def test_no_retry_policy_is_literal_zero_retry() -> None:
    policy = live.no_retry_policy()

    assert policy.retry_delays_seconds == ()
    assert policy.max_429_retries_per_request == 0
    assert policy.max_429_per_run == 1
    policy.validate()


def test_stability_is_blocked_before_main_completion(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    live.prepare_run(run_dir)

    with pytest.raises(Exception, match="主测没有完整收口"):
        live.run_stability(run_dir)


def test_forged_main_ticket_cannot_unlock_stability(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    live.prepare_run(run_dir)
    live.write_json_exclusive(
        run_dir / "completion/main.json",
        {
            "phase": "main",
            "logical_samples": 3,
            "case_ids": list(live.CASE_ORDER),
            "control_requests_sent": 0,
        },
    )

    with pytest.raises(Exception, match="主测没有完整收口"):
        live.run_stability(run_dir)


def test_first_case_mechanical_failure_stops_all_later_calls_and_seals_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    live.prepare_run(run_dir)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = FirstCaseMechanicalFailureOpener()

    with pytest.raises(live.V02LiveHardStop, match="闭集锚机械闸失败"):
        live.run_main(run_dir, opener=opener)

    assert len(opener.calls) == 1
    ticket = live.read_json(run_dir / "hard_stop.json")
    assert ticket["status"] == "hard_stop_no_patch_no_rerun"
    assert ticket["logical_requests_started"] == 1
    assert ticket["secret_scan"]["exact_key_hit_count"] == 0
    assert ticket["secret_scan"]["authorization_header_hit_count"] == 0
    assert not (run_dir / "samples/main/B03").exists()
    assert not (run_dir / "samples/main/B01").exists()
    assert not (run_dir / "samples/stability").exists()

    second_opener = DynamicOpener()
    with pytest.raises(Exception, match="本轮已硬停"):
        live.run_main(run_dir, opener=second_opener)
    assert second_opener.calls == []
