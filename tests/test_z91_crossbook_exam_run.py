from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import z91_crossbook_exam_run as z91
from zbatch_modules.errors import ZBatchError
from zbatch_modules.z83_retry_transport import RetryPolicy


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.status = status
        self.headers = {
            "Content-Type": "application/json",
            "x-request-id": "unit-test",
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.raw


ZERO_WAIT_POLICY = RetryPolicy(
    same_chapter_gap_seconds=0.0,
    cross_chapter_gap_seconds=0.0,
    retry_delays_seconds=(0.0, 0.0),
    max_429_retries_per_request=2,
    max_429_per_run=5,
    max_retry_after_seconds=300.0,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def make_source_fact_seal(run_dir: Path) -> Path:
    root = run_dir / "review/source_facts"
    reviewer_a = root / "reviewer_A.json"
    reviewer_b = root / "reviewer_B.json"
    adjudication = root / "field_adjudication.json"
    resolved = root / "resolved.json"
    _write_json(reviewer_a, {"reviewer": "A", "facts": ["仅看原文"]})
    _write_json(reviewer_b, {"reviewer": "B", "facts": ["仅看原文"]})
    _write_json(adjudication, {"status": "all_fields_resolved_before_calls"})
    _write_json(
        resolved,
        {
            "schema_version": "z91-source-facts-resolved-v1",
            "status": "sealed",
            "probe_count": 18,
            "items": [
                {"probe_id": f"P{index:02d}", "source_fact": f"来源事实{index}"}
                for index in range(1, 19)
            ],
        },
    )
    seal = {
        "schema_version": "z91-source-fact-seal-v1",
        "status": "sealed_before_model_calls",
        "rubric_sha256": z91.sha256_file(z91.STEP1_DIR / "rubric_candidate.json"),
        "probe_slots_sha256": z91.sha256_file(z91.STEP1_DIR / "probe_slots.json"),
        "chapter_body_sha256_by_case": {
            case["case_key"]: z91.sha256_file(
                z91.STEP1_DIR / f"cases/{case['case_key']}/chapter_body.txt"
            )
            for case in z91.CASES
        },
        "reviewer_files": {
            "A": {"path": reviewer_a.name, "sha256": z91.sha256_file(reviewer_a)},
            "B": {"path": reviewer_b.name, "sha256": z91.sha256_file(reviewer_b)},
        },
        "adjudication_file": {
            "path": adjudication.name,
            "sha256": z91.sha256_file(adjudication),
        },
        "resolved_file": {
            "path": resolved.name,
            "sha256": z91.sha256_file(resolved),
        },
        "probe_count": 18,
        "reviewers": 2,
        "sealed_at": "2026-07-23T00:00:00+00:00",
    }
    seal["seal_preimage_sha256"] = z91.canonical_sha(seal)
    seal_path = root / "source_fact_seal.json"
    _write_json(seal_path, seal)
    return seal_path


def prepare_run(tmp_path: Path, name: str = "z91_run") -> Path:
    run_dir = tmp_path / name
    seal_path = make_source_fact_seal(run_dir)
    z91.prepare(run_dir, seal_path)
    return run_dir


def authorize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSENOVA_API_KEY", "flash-unit-key")
    monkeypatch.setenv("TENCENT_TOKENHUB_API_KEY", "pro-unit-key")


def catalog_online(request, timeout):
    assert request.get_method() == "GET"
    assert request.full_url == "https://tokenhub.tencentmaas.com/v1/models"
    assert timeout == 60
    return FakeResponse({"data": [{"id": z91.PRO_MODEL, "status": "online"}]})


def response_payload(sample: dict, *, finish_reason: str = "stop", extra=False) -> dict:
    chapter = int(sample["chapter"])
    event = {
        "event_id": f"EV-C{chapter:04d}-01",
        "event": "这是一条满足最小长度的事件摘要。",
        "anchors": [{"anchor_id": "E0001"}],
    }
    if extra:
        event["classification"] = "结构越权"
    content = {
        "schema_version": "z-event-v1",
        "chapter": chapter,
        "events": [event],
    }
    return {
        "id": f"unit-{sample['sample_id']}",
        "model": sample["model"],
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "reasoning_content": "单元测试思考内容",
                    "content": json.dumps(content, ensure_ascii=False),
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


def run_fake_success(run_dir: Path, monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch)
    samples = z91.sample_specs()
    calls: list[tuple[str, bytes]] = []

    def opener(request, timeout):
        sample = samples[len(calls)]
        calls.append((request.full_url, request.data))
        assert timeout == 600
        body = json.loads(request.data)
        assert body["model"] == sample["model"]
        return FakeResponse(response_payload(sample))

    result = z91.run(
        run_dir,
        opener=opener,
        catalog_opener=catalog_online,
        policy=ZERO_WAIT_POLICY,
        sleeper=lambda _: None,
        jitter=lambda: 0.0,
    )
    return result, calls


def test_prepare_accepts_only_presealed_source_fact_subtree_and_is_zero_call(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "z91_prepared"
    seal_path = make_source_fact_seal(run_dir)

    receipt = z91.prepare(run_dir, seal_path)
    verification = z91.read_json(run_dir / "prepared/mechanical_verification.json")
    plan = z91.read_json(run_dir / "prepared/run_plan.json")

    assert receipt["status"] == "pass_zero_call_prepared"
    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert verification["status"] == "pass_twice_identical"
    assert verification["first_vector"] == verification["second_vector"]
    assert plan["sample_count"] == 6
    assert plan["tencent_exact_model"] == "deepseek-v4-pro-202606"
    assert plan["automatic_fallback"] is False
    assert (run_dir / "review/source_facts/reviewer_A.json").is_file()

    with pytest.raises(ZBatchError, match="已有正式工件"):
        z91.prepare(run_dir, seal_path)


def test_prepare_rejects_any_other_preexisting_file(tmp_path: Path) -> None:
    source_run = tmp_path / "source"
    seal_path = make_source_fact_seal(source_run)
    run_dir = tmp_path / "occupied"
    run_dir.mkdir()
    (run_dir / "old.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ZBatchError, match="拒绝覆盖正式 run"):
        z91.prepare(run_dir, seal_path)


def test_six_fake_samples_use_exact_routes_frozen_requests_and_raw_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = prepare_run(tmp_path)

    result, calls = run_fake_success(run_dir, monkeypatch)

    assert result["logical_samples"] == 6
    assert result["model_api_network_attempts"] == 6
    assert result["mechanical_three_gates"] == "pass_6_of_6"
    assert result["deepseek_official_api_used"] is False
    assert len(calls) == 6
    for index, (url, wire) in enumerate(calls):
        sample = z91.sample_specs()[index]
        expected_url = (
            "https://token.sensenova.cn/v1/chat/completions"
            if sample["provider"] == "sensenova"
            else "https://tokenhub.tencentmaas.com/v1/chat/completions"
        )
        assert url == expected_url
        body = json.loads(wire)
        assert z91.canonical_sha(body["messages"]) == sample["messages_sha256"]
        assert body["temperature"] == 0.0
        assert body["n"] == 1
        assert body["max_tokens"] == 32000
        if sample["provider"] == "sensenova":
            assert body["response_format"] == {"type": "json_object"}
            assert body["reasoning_effort"] == "medium"
        else:
            assert body["model"] == "deepseek-v4-pro-202606"
            assert body["thinking"] == {
                "type": "enabled",
                "reasoning_effort": "medium",
            }
            assert "response_format" not in body
    for sample in z91.sample_specs():
        root = run_dir / f"samples/{sample['sample_id']}"
        assert len(list((root / "checkpoint").iterdir())) == 5
        assert z91.read_json(root / "mechanical.json")["status"] == "pass"
    audit = z91.audit_completed(run_dir)
    assert audit["status"] == "pass_rebuilt_from_raw_response_usage_attempts"
    assert audit["logical_samples"] == 6

    post_calls = 0

    def must_not_call(request, timeout):
        nonlocal post_calls
        post_calls += 1
        raise AssertionError("复跑不应触发目录或模型请求")

    with pytest.raises(ZBatchError, match="已经占用"):
        z91.run(run_dir, opener=must_not_call, catalog_opener=must_not_call)
    assert post_calls == 0


def test_tencent_catalog_alias_or_offline_cannot_claim_or_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = prepare_run(tmp_path)
    authorize(monkeypatch)
    post_calls = 0

    def catalog_alias(request, timeout):
        return FakeResponse(
            {"data": [{"id": "deepseek-v4-pro", "status": "online"}]}
        )

    def post(request, timeout):
        nonlocal post_calls
        post_calls += 1
        raise AssertionError("目录闸失败后不能发样本")

    with pytest.raises(z91.Z91RunHardStop) as captured:
        z91.run(run_dir, opener=post, catalog_opener=catalog_alias)

    assert captured.value.reason_code == "model_catalog_exact_id_missing"
    assert post_calls == 0
    assert not (run_dir / "transport/run_claim.json").exists()
    hard_stop = z91.read_json(run_dir / "hard_stop.json")
    assert hard_stop["deepseek_official_api_used"] is False
    assert hard_stop["automatic_fallback_used"] is False


@pytest.mark.parametrize(
    ("finish_reason", "extra", "expected_reason"),
    [
        ("length", False, "finish_reason_length"),
        ("stop", True, "structure_overreach"),
    ],
)
def test_length_or_structure_overreach_hard_stops_without_second_sample(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    finish_reason: str,
    extra: bool,
    expected_reason: str,
) -> None:
    run_dir = prepare_run(tmp_path)
    authorize(monkeypatch)
    calls = 0
    first = z91.sample_specs()[0]

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(
            response_payload(first, finish_reason=finish_reason, extra=extra)
        )

    with pytest.raises(z91.Z91RunHardStop) as captured:
        z91.run(
            run_dir,
            opener=opener,
            catalog_opener=catalog_online,
            policy=ZERO_WAIT_POLICY,
            sleeper=lambda _: None,
            jitter=lambda: 0.0,
        )

    assert captured.value.reason_code == expected_reason
    assert calls == 1
    root = run_dir / f"samples/{first['sample_id']}"
    assert z91.read_json(root / "mechanical.json")["status"] == (
        "fail_hard_stop_no_rerun"
    )
    assert z91.read_json(root / "checkpoint/05_seal.json")[
        "mechanical_verdict"
    ] == "fail"
    assert not (run_dir / f"samples/{z91.sample_specs()[1]['sample_id']}").exists()


def test_429_retries_only_identical_frozen_request_and_audit_counts_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = prepare_run(tmp_path)
    authorize(monkeypatch)
    samples = z91.sample_specs()
    wires: list[bytes] = []
    successful_samples = 0

    def opener(request, timeout):
        nonlocal successful_samples
        wires.append(request.data)
        if len(wires) == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                {"Retry-After": "0", "Content-Type": "application/json"},
                io.BytesIO(b'{"error":"rate limited"}'),
            )
        sample = samples[successful_samples]
        successful_samples += 1
        return FakeResponse(response_payload(sample))

    result = z91.run(
        run_dir,
        opener=opener,
        catalog_opener=catalog_online,
        policy=ZERO_WAIT_POLICY,
        sleeper=lambda _: None,
        jitter=lambda: 0.0,
    )

    assert result["model_api_network_attempts"] == 7
    assert result["429_count"] == 1
    assert wires[0] == wires[1]
    first_ledger = z91._attempt_rows(
        run_dir
        / f"samples/{samples[0]['sample_id']}/transport/call_attempts.jsonl"
    )
    assert [row["http_status"] for row in first_ledger] == [429, 200]
    assert first_ledger[0]["usage"] == "unknown"
    assert z91.audit_completed(run_dir)["model_api_network_attempts"] == 7
