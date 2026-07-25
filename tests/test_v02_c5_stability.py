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
import v02_c5_stability as stability  # noqa: E402


pytestmark = pytest.mark.v02


def _isolated_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    run_dir = tmp_path / stability.EXPECTED_RUN_NAME
    monkeypatch.setattr(stability, "C5_STABILITY_RUN_DIR", run_dir)
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


class StopOpener:
    def __init__(self, supply_dir: Path) -> None:
        self.supply_dir = supply_dir
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, timeout: int) -> FakeResponse:
        body = json.loads(request.data.decode("utf-8"))
        rendered = json.dumps(body, ensure_ascii=False)
        case_id = next(
            case_id
            for case_id in live.CASE_ORDER
            if f"EV-C{prep.CASE_BY_ID[case_id].unit:04d}-" in rendered
        )
        catalog = json.loads(
            (
                self.supply_dir / f"catalogs/{case_id}.json"
            ).read_text(encoding="utf-8")
        )
        anchor = catalog["entries"][0]["anchor_id"]
        payload = {
            "schema_version": prep.CONTRACT_VERSION,
            "chapter": prep.CASE_BY_ID[case_id].unit,
            "events": [
                {
                    "event_id": (
                        f"EV-C{prep.CASE_BY_ID[case_id].unit:04d}-01"
                    ),
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
        self.calls.append(body)
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
        return FakeResponse(
            json.dumps(response, ensure_ascii=False).encode("utf-8")
        )


def test_c5_stability_prepare_copies_c4_requests_byte_for_byte(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    result = stability.prepare_run(run_dir)

    assert result["status"] == "PASS_C5_STABILITY_PREPARED"
    for case_id in live.CASE_ORDER:
        assert (
            run_dir / f"prepared/main/{case_id}/request_artifact.json"
        ).read_bytes() == (
            stability.C4_RUN_DIR
            / f"prepared/main/{case_id}/request_artifact.json"
        ).read_bytes()
        body = json.loads(
            (
                run_dir / f"prepared/main/{case_id}/request_body.json"
            ).read_text(encoding="utf-8")
        )
        assert body["max_tokens"] == 65536
        assert body["temperature"] == 0.2
        assert body["reasoning_effort"] == "medium"


def test_c5_stability_requires_sealed_main_conclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    empty_score_dir = tmp_path / "empty_score"

    with pytest.raises(stability.C5StabilityHardStop, match="缺冻结件"):
        stability.prepare_run(run_dir, score_dir=empty_score_dir)


def test_c5_stability_sends_each_chapter_once_and_never_changes_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    stability.prepare_run(run_dir)
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = StopOpener(stability.C4_SUPPLY_DIR)

    result = stability.run_stability(run_dir, opener=opener)

    assert result["logical_samples"] == 3
    assert result["network_attempts"] == 3
    assert result["main_conclusion_changed"] is False
    assert result["quality_result_registered"] is False
    assert len(opener.calls) == 3
    assert all(body["max_tokens"] == 65536 for body in opener.calls)
    diagnostic = json.loads(
        (
            run_dir / "diagnostics/stability_disagreement.json"
        ).read_text(encoding="utf-8")
    )
    assert diagnostic["main_result_selection"] == "C4_MAIN_ONLY"
    assert diagnostic["stability_result_can_replace_main"] is False
    assert diagnostic["stability_result_can_change_c5_conclusion"] is False
    assert not (run_dir / "samples/main").exists()


def test_c5_stability_rejects_prepared_request_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    stability.prepare_run(run_dir)
    path = run_dir / "prepared/main/B02-U0039/request_body.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["temperature"] = 0.0
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(stability.C5StabilityHardStop, match="漂移"):
        stability.verify_prepared(run_dir)


def test_c5_stability_rejects_orphan_claim_before_send(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    stability.prepare_run(run_dir)
    live.write_json_exclusive(
        run_dir / "transport/C5_stability_claim.json",
        {"status": "orphan_test_claim"},
    )
    monkeypatch.setenv(live.PINNED_KEY_ENV, "test-secret-not-real")
    opener = StopOpener(stability.C4_SUPPLY_DIR)

    with pytest.raises(stability.C5StabilityHardStop, match="占用票"):
        stability.run_stability(run_dir, opener=opener)
    assert opener.calls == []


def test_c5_stability_scans_loaded_key_before_send(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _isolated_run(tmp_path, monkeypatch)
    stability.prepare_run(run_dir)
    key = "test-secret-not-real"
    monkeypatch.setenv(live.PINNED_KEY_ENV, key)
    leak = run_dir / "prepared/test_key_leak.txt"
    leak.write_text(key, encoding="utf-8")
    opener = StopOpener(stability.C4_SUPPLY_DIR)

    with pytest.raises(stability.C5StabilityHardStop, match="密钥"):
        stability.run_stability(run_dir, opener=opener)
    assert opener.calls == []


def test_c5_stability_rejects_same_name_under_another_parent(
    tmp_path: Path,
) -> None:
    alternate = tmp_path / stability.EXPECTED_RUN_NAME

    with pytest.raises(
        stability.C5StabilityHardStop,
        match="运行目录必须是",
    ):
        stability.prepare_run(alternate)
