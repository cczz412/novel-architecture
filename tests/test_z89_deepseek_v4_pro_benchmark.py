from __future__ import annotations

import json
from pathlib import Path

import pytest

import z89_deepseek_v4_pro_benchmark as z89


def authorize_official_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(z89.OFFICIAL_APPROVAL_ENV, z89.OFFICIAL_APPROVAL_VALUE)


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": "application/json", "x-request-id": "test"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.raw


def response_payload(*, finish_reason: str = "stop") -> dict:
    content = {
        "schema_version": "z-event-v1",
        "chapter": 3,
        "events": [
            {
                "event_id": "EV-C0003-01",
                "event": "周明瑞确定了行动计划。",
                "anchors": [{"anchor_id": "E0002"}],
            }
        ],
    }
    return {
        "id": "test-z89",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "reasoning_content": "测试思考",
                    "content": json.dumps(content, ensure_ascii=False),
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "completion_tokens_details": {"reasoning_tokens": 10},
        },
    }


def test_build_body_keeps_messages_and_changes_only_declared_body_fields() -> None:
    body, diff = z89.build_body()
    baseline = z89.read_json(z89.SOURCE_BODY)

    assert body["messages"] == baseline["messages"]
    assert body["model"] == "deepseek-v4-pro"
    assert body["temperature"] == 0.0
    assert body["reasoning_effort"] == "medium"
    assert body["max_tokens"] == 32000
    assert body["n"] == 1
    assert body["response_format"] == {"type": "json_object"}
    assert "thinking" not in body
    assert diff["body_changed_paths"] == ["$.model", "$.temperature"]
    assert diff["messages_byte_equal"] is True
    assert diff["gold_or_answer_hits"] == []


def test_prepare_is_zero_call_repeatable_and_secret_free(tmp_path: Path) -> None:
    first = tmp_path / "z89_first"
    second = tmp_path / "z89_second"

    z89.prepare(first)
    z89.prepare(second)

    one = z89.verify_prepared(first)
    two = z89.verify_prepared(second)
    assert one["messages_sha256"] == two["messages_sha256"]
    assert one["messages_equal_retry03"] is True
    assert one["gold_or_answer_hits"] == []
    assert one["secret_scan"]["exact_key_hit_count"] == 0
    assert one["secret_scan"]["authorization_header_hit_count"] == 0
    assert z89.read_json(first / "run_manifest.json")["status"] == "prepared_zero_call"


def test_mocked_formal_sample_writes_single_checkpoint_and_score_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "z89_run"
    z89.prepare(run_dir)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-in-response")
    authorize_official_api(monkeypatch)
    calls: list[str] = []

    def opener(request, timeout):
        calls.append(request.full_url)
        assert timeout == 600
        assert request.full_url == "https://api.deepseek.com/chat/completions"
        return FakeResponse(response_payload())

    result = z89.run(run_dir, opener=opener)

    assert calls == ["https://api.deepseek.com/chat/completions"]
    assert result["logical_samples"] == 1
    assert result["network_attempts"] == 1
    assert result["mechanical_three_gates"] == "pass"
    assert result["event_count"] == 1
    assert (run_dir / "checkpoints/ch0003/05_seal.json").is_file()
    assert len(list((run_dir / "checkpoints/ch0003").iterdir())) == 5
    template = z89.read_json(run_dir / "review/adjudication_template.json")
    assert template["formal_denominator"] == 23
    assert len(template["gold_rows"]) == 23
    assert template["model_visible_request_contains_score_material"] is False
    assert result["secret_scan"]["exact_key_hit_count"] == 0


def test_length_response_hard_stops_without_second_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "z89_length"
    z89.prepare(run_dir)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    authorize_official_api(monkeypatch)
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(response_payload(finish_reason="length"))

    with pytest.raises(z89.Z89HardStop, match="32k 下仍触顶"):
        z89.run(run_dir, opener=opener)

    assert calls == 1
    hard_stop = z89.read_json(run_dir / "main/hard_stop.json")
    assert hard_stop["reason_code"] == "finish_reason_length"
    assert hard_stop["rerun_allowed"] is False
    assert z89.read_json(run_dir / "checkpoints/ch0003/05_seal.json")[
        "mechanical_verdict"
    ] == "fail"


def test_completed_run_cannot_be_sampled_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "z89_no_rerun"
    z89.prepare(run_dir)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    authorize_official_api(monkeypatch)

    def opener(request, timeout):
        return FakeResponse(response_payload())

    z89.run(run_dir, opener=opener)
    with pytest.raises(z89.ZBatchError, match="已占用正式调用票"):
        z89.run(run_dir, opener=opener)


def test_score_uses_23_part_double_track_and_prewritten_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "z89_score"
    z89.prepare(run_dir)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    authorize_official_api(monkeypatch)

    def opener(request, timeout):
        return FakeResponse(response_payload())

    z89.run(run_dir, opener=opener)
    template = z89.read_json(run_dir / "review/adjudication_template.json")
    adjudication = {
        "schema_version": "z89-gold-adjudication-v1",
        "gold_sha256": z89.GOLD_FILE_SHA256,
        "formal_denominator": 23,
        "gold_rows": [
            {
                "part_id": row["part_id"],
                "verdict": "miss",
                "candidate_event_ids": [],
                "reason": "测试判词：当前唯一事件不覆盖此金标原子。",
            }
            for row in template["gold_rows"]
        ],
    }
    adjudication_path = run_dir / "review/adjudication_completed.json"
    z89.write_json_exclusive(adjudication_path, adjudication)

    result = z89.score(run_dir, adjudication_path)

    assert result["gold_chapter_3"]["formal_denominator"] == 23
    assert result["gold_chapter_3"]["strict_hit"] == 0
    assert result["gold_chapter_3"]["effective_recall"] == 0
    assert result["prewritten_interpretation"] == "between_prewritten_thresholds_requires_cz_review"
    assert result["candidate_tier"] == "silver_only"
    assert result["promoted_or_default_changed"] is False


def test_official_api_stays_blocked_even_when_key_is_already_in_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "z89_default_denied"
    z89.prepare(run_dir)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(response_payload())

    with pytest.raises(z89.ZBatchError, match="默认永久禁用"):
        z89.run(run_dir, opener=opener)

    assert calls == 0
    assert not (run_dir / "main/run_claim.json").exists()
