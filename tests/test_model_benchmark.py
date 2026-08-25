from __future__ import annotations

import json
import io
import urllib.error
from pathlib import Path

import pytest

from isolation import clear_vendor_api_keys
from tools.pipeline_common import model_benchmark as benchmark


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


def response_payload(
    *, finish_reason: str = "stop", include_reasoning: bool = True
) -> dict:
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
    message = {
        "role": "assistant",
        "content": json.dumps(content, ensure_ascii=False),
    }
    if include_reasoning:
        message["reasoning_content"] = "我逐条核对了正文和锚目录。"
    return {
        "id": "test-model-benchmark",
        "model": "qwen3.7-plus",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": message,
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


def prepare_qwen(root: Path) -> dict:
    return benchmark.prepare(
        root,
        benchmark_id=root.name,
        stage_id="neutral_extract_x01_ch0003_v3_t02",
        provider_id="qianwen_platform",
        model_id="qwen3.7-plus",
        profile_id="thinking_32k_prompt_json",
    )


def test_qwen_adapter_keeps_messages_and_records_every_compatibility_delta() -> None:
    stage = benchmark.load_stage("neutral_extract_x01_ch0003_v3_t02")
    provider, adapter, _ = benchmark.load_provider("qianwen_platform")
    profile = benchmark.resolve_profile(
        adapter,
        "thinking_32k_prompt_json",
        "qwen3.7-plus",
        provider=provider,
    )
    body, diff = benchmark.build_body(stage, provider, "qwen3.7-plus", profile)
    baseline = benchmark.read_json(
        benchmark.ROOT / stage["source_artifacts"]["baseline_request"]["path"]
    )

    assert body["messages"] == baseline["messages"]
    assert body["model"] == "qwen3.7-plus"
    assert body["temperature"] == 0.2
    assert body["n"] == 1
    assert body["enable_thinking"] is True
    assert body["thinking_budget"] == 32768
    assert "response_format" not in body
    assert "reasoning_effort" not in body
    assert "max_tokens" not in body
    assert diff["messages_byte_equal"] is True
    assert diff["gold_or_answer_hits"] == []
    assert diff["changed_paths"] == [
        "$.enable_thinking",
        "$.max_tokens",
        "$.model",
        "$.reasoning_effort",
        "$.response_format",
        "$.thinking_budget",
    ]


def test_qianwen_deepseek_v4_pro_uses_its_own_thinking_contract() -> None:
    stage = benchmark.load_stage("neutral_extract_x01_ch0003_v3_t02")
    provider, adapter, _ = benchmark.load_provider("qianwen_platform")
    profile = benchmark.resolve_profile(
        adapter,
        "deepseek_v4_pro_medium_prompt_json",
        "deepseek-v4-pro",
        provider=provider,
    )

    body, diff = benchmark.build_body(stage, provider, "deepseek-v4-pro", profile)

    assert body["model"] == "deepseek-v4-pro"
    assert body["temperature"] == 0.2
    assert body["enable_thinking"] is True
    assert body["reasoning_effort"] == "medium"
    assert body["max_completion_tokens"] == 32000
    assert "max_tokens" not in body
    assert "response_format" not in body
    assert "n" not in body
    assert "thinking_budget" not in body
    assert profile["single_sample_via_response_gate"] is True
    assert diff["messages_byte_equal"] is True


def test_volcengine_deepseek_v4_pro_uses_local_json_gate() -> None:
    stage = benchmark.load_stage("neutral_extract_x01_ch0003_v3_t02")
    provider, adapter, _ = benchmark.load_provider("volcengine_ark")
    profile = benchmark.resolve_profile(
        adapter,
        "deepseek_v4_pro_medium_prompt_json",
        "deepseek-v4-pro-260425",
        provider=provider,
    )

    body, diff = benchmark.build_body(
        stage, provider, "deepseek-v4-pro-260425", profile
    )

    assert body["model"] == "deepseek-v4-pro-260425"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 32000
    assert body["thinking"] == {"type": "enabled"}
    assert body["reasoning_effort"] == "medium"
    assert "response_format" not in body
    assert "n" not in body
    assert profile["single_sample_via_response_gate"] is True
    assert diff["messages_byte_equal"] is True


@pytest.mark.parametrize(
    ("model_id", "profile_id", "expected_effort"),
    [
        ("hy3", "thinking_high_structured_json", "high"),
        ("glm-5.2", "thinking_structured_json", None),
    ],
)
def test_tencent_thinking_profiles_use_local_json_gate(
    model_id: str, profile_id: str, expected_effort: str | None
) -> None:
    stage = benchmark.load_stage("neutral_extract_x01_ch0003_v3_t02")
    provider, adapter, _ = benchmark.load_provider("tencent_tokenhub")
    profile = benchmark.resolve_profile(
        adapter, profile_id, model_id, provider=provider
    )

    body, _ = benchmark.build_body(stage, provider, model_id, profile)

    assert body["temperature"] == 0.2
    assert body["thinking"] == {"type": "enabled"}
    assert body.get("reasoning_effort") == expected_effort
    assert "response_format" not in body
    assert profile["require_nonempty_reasoning_content"] is True


def test_tencent_deepseek_v4_pro_uses_nested_medium_contract() -> None:
    stage = benchmark.load_stage("neutral_extract_x01_ch0003_v3_t02")
    provider, adapter, _ = benchmark.load_provider("tencent_tokenhub")
    profile = benchmark.resolve_profile(
        adapter,
        "deepseek_v4_pro_medium_prompt_json",
        "deepseek-v4-pro-202606",
        provider=provider,
    )

    body, diff = benchmark.build_body(
        stage, provider, "deepseek-v4-pro-202606", profile
    )

    assert body["model"] == "deepseek-v4-pro-202606"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 32000
    assert body["n"] == 1
    assert body["thinking"] == {
        "type": "enabled",
        "reasoning_effort": "medium",
    }
    assert "reasoning_effort" not in body
    assert "response_format" not in body
    assert diff["messages_byte_equal"] is True


def test_ant_ling_profile_uses_official_thinking_and_json_contract() -> None:
    stage = benchmark.load_stage("neutral_extract_x01_ch0003_v3_t02")
    provider, adapter, _ = benchmark.load_provider("ant_ling")
    profile = benchmark.resolve_profile(
        adapter,
        "ling_flash_thinking_json",
        "Ling-3.0-flash",
        provider=provider,
    )

    body, diff = benchmark.build_body(
        stage, provider, "Ling-3.0-flash", profile
    )

    assert body["model"] == "Ling-3.0-flash"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 32000
    assert body["thinking"] == {"type": "enable"}
    assert body["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in body
    assert "n" not in body
    assert profile["single_sample_via_response_gate"] is True
    assert diff["messages_byte_equal"] is True
    assert diff["gold_or_answer_hits"] == []


@pytest.mark.parametrize(
    "model_id",
    [
        "qwen3.7-max",
        "qwen3.7-max-2026-05-20",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "glm-5.2",
        "kimi-k2.7-code",
    ],
)
def test_unverified_model_profile_pairs_fail_before_directory_creation(
    tmp_path: Path, model_id: str
) -> None:
    root = tmp_path / model_id

    with pytest.raises(benchmark.ZBatchError, match="尚未做过配对验证"):
        benchmark.prepare(
            root,
            benchmark_id=model_id,
            stage_id="neutral_extract_x01_ch0003_v3_t02",
            provider_id="qianwen_platform",
            model_id=model_id,
            profile_id="thinking_32k_prompt_json",
        )

    assert not root.exists()


def test_profile_model_allowlist_is_fail_closed_and_exact() -> None:
    provider, adapter, _ = benchmark.load_provider("qianwen_platform")
    broken = json.loads(json.dumps(adapter))
    del broken["profiles"]["thinking_32k_prompt_json"]["validated_model_ids"]
    with pytest.raises(benchmark.ZBatchError, match="缺精确模型白名单"):
        benchmark.resolve_profile(
            broken,
            "thinking_32k_prompt_json",
            "qwen3.7-plus",
            provider=provider,
        )

    duplicated = json.loads(json.dumps(adapter))
    duplicated["profiles"]["thinking_32k_prompt_json"]["validated_model_ids"] = [
        "qwen3.7-plus",
        "qwen3.7-plus",
    ]
    with pytest.raises(benchmark.ZBatchError, match="重复精确 ID"):
        benchmark.resolve_profile(
            duplicated,
            "thinking_32k_prompt_json",
            "qwen3.7-plus",
            provider=provider,
        )

    unknown = json.loads(json.dumps(adapter))
    unknown["profiles"]["thinking_32k_prompt_json"]["validated_model_ids"] = [
        "qwen3.7-plus-snapshot",
    ]
    with pytest.raises(benchmark.ZBatchError, match="未登记模型"):
        benchmark.resolve_profile(
            unknown,
            "thinking_32k_prompt_json",
            "qwen3.7-plus-snapshot",
            provider=provider,
        )


def test_list_only_exposes_verified_runnable_pairs() -> None:
    options = benchmark.list_options()
    assert options["defaults"]["default_stage_id"] == (
        "neutral_extract_x01_ch0003_v3_t02"
    )
    assert options["defaults"]["default_temperature"] == 0.2
    qwen = options["providers"]["qianwen_platform"]

    assert qwen["runnable_pairs"] == [
        {
            "model": "deepseek-v4-pro",
            "profile": "deepseek_v4_pro_medium_prompt_json",
        },
        {"model": "qwen3.7-plus", "profile": "thinking_32k_prompt_json"},
    ]
    assert qwen["registered_models_without_validated_profile"] == [
        "qwen3.7-flash",
        "qwen3.7-max",
        "qwen3.7-max-2026-05-20",
        "deepseek-v4-flash",
        "glm-5.2",
        "kimi-k2.7-code",
    ]

    volcengine = options["providers"]["volcengine_ark"]
    assert volcengine["runnable_pairs"] == [
        {
            "model": "deepseek-v4-pro-260425",
            "profile": "deepseek_v4_pro_medium_prompt_json",
        }
    ]
    assert volcengine["registered_models_without_validated_profile"] == [
        "glm-5-2-260617",
        "doubao-seed-evolving",
        "doubao-seed-2-1-turbo-260628",
        "doubao-seed-2-1-pro-260628",
        "deepseek-v4-flash-260425",
    ]

    tencent = options["providers"]["tencent_tokenhub"]
    assert tencent["runnable_pairs"] == [
        {
            "model": "deepseek-v4-pro-202606",
            "profile": "deepseek_v4_pro_medium_prompt_json",
        },
        {
            "model": "deepseek-v4-pro",
            "profile": "deepseek_v4_pro_medium_prompt_json",
        },
        {"model": "hy3", "profile": "thinking_high_structured_json"},
        {
            "model": "deepseek-v4-flash",
            "profile": "thinking_high_structured_json",
        },
        {
            "model": "deepseek-v4-pro",
            "profile": "thinking_high_structured_json",
        },
        {
            "model": "deepseek-v4-flash-202605",
            "profile": "thinking_structured_json",
        },
        {
            "model": "deepseek-v4-pro-202606",
            "profile": "thinking_structured_json",
        },
        {"model": "glm-5.2", "profile": "thinking_structured_json"},
        {"model": "glm-5.1", "profile": "thinking_structured_json"},
        {
            "model": "kimi-k2.7-code-highspeed",
            "profile": "thinking_structured_json",
        },
        {"model": "kimi-k3", "profile": "thinking_structured_json"},
        {
            "model": "kimi-k2.7-code",
            "profile": "thinking_structured_json",
        },
        {"model": "kimi-k2.6", "profile": "thinking_structured_json"},
    ]
    assert tencent["registered_models_without_validated_profile"] == [
        "hy-role",
        "minimax-m3",
        "minimax-m2.7",
    ]

    ant_ling = options["providers"]["ant_ling"]
    assert ant_ling["runnable_pairs"] == [
        {"model": "Ling-3.0-flash", "profile": "ling_flash_thinking_json"}
    ]
    assert ant_ling["registered_models_without_validated_profile"] == []


def test_tencent_model_catalog_requires_exact_online_model(tmp_path: Path) -> None:
    provider, _, _ = benchmark.load_provider("tencent_tokenhub")
    requests = []

    def opener(request, timeout):
        requests.append(request)
        assert timeout == 60
        assert request.full_url == "https://tokenhub.tencentmaas.com/v1/models"
        assert request.get_method() == "GET"
        return FakeResponse(
            {
                "object": "list",
                "data": [
                    {"id": "hy3", "status": "online"},
                    {"id": "glm-5.2", "status": "offline"},
                ],
            }
        )

    receipt = benchmark.verify_provider_model_catalog(
        tmp_path,
        provider,
        "hy3",
        "catalog-test-key",
        opener=opener,
    )

    assert len(requests) == 1
    assert receipt is not None
    assert receipt["status"] == "pass_exact_model_online"
    assert receipt["model_api_calls"] == 0
    assert receipt["selected_model"] == {"id": "hy3", "status": "online"}
    saved = benchmark.read_json(tmp_path / "transport/provider_model_catalog.json")
    assert saved == receipt
    audit = benchmark.audit_provider_model_catalog(tmp_path, provider, "hy3")
    assert audit is not None
    assert audit["receipt_sha256"] == benchmark.sha256_file(
        tmp_path / "transport/provider_model_catalog.json"
    )
    assert "catalog-test-key" not in (
        tmp_path / "transport/provider_model_catalog.json"
    ).read_text(encoding="utf-8")


def test_tencent_model_catalog_rejects_offline_model(tmp_path: Path) -> None:
    provider, _, _ = benchmark.load_provider("tencent_tokenhub")

    with pytest.raises(benchmark.BenchmarkHardStop, match="不是 online"):
        benchmark.verify_provider_model_catalog(
            tmp_path,
            provider,
            "glm-5.2",
            "catalog-test-key",
            opener=lambda request, timeout: FakeResponse(
                {"data": [{"id": "glm-5.2", "status": "offline"}]}
            ),
        )

    assert not (tmp_path / "transport/provider_model_catalog.json").exists()
    assert (tmp_path / "transport/provider_model_catalog_raw.json").is_file()


def test_tencent_model_catalog_audit_rejects_receipt_tampering(
    tmp_path: Path,
) -> None:
    provider, _, _ = benchmark.load_provider("tencent_tokenhub")
    benchmark.verify_provider_model_catalog(
        tmp_path,
        provider,
        "hy3",
        "catalog-test-key",
        opener=lambda request, timeout: FakeResponse(
            {"data": [{"id": "hy3", "status": "online"}]}
        ),
    )
    receipt_path = tmp_path / "transport/provider_model_catalog.json"
    receipt = benchmark.read_json(receipt_path)
    receipt["model_id"] = "glm-5.2"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(benchmark.ZBatchError, match="不能由原始响应重建"):
        benchmark.audit_provider_model_catalog(tmp_path, provider, "hy3")


def test_prepare_is_zero_call_repeatable_and_uses_fixed_layout(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    preflight = prepare_qwen(first)
    prepare_qwen(second)

    one = benchmark.verify_prepared(first)
    two = benchmark.verify_prepared(second)
    assert one["body_sha256"] == two["body_sha256"]
    assert one["messages_sha256"] == two["messages_sha256"]
    assert one["source_pins_sha256"] == two["source_pins_sha256"]
    assert one["artifact_sha256"] != two["artifact_sha256"]
    assert (first / "benchmark.json").is_file()
    assert (first / "inputs/chapter.txt").is_file()
    assert (first / "inputs/benchmark_defaults.json").is_file()
    assert (first / "prepared/request_body.json").is_file()
    assert not (first / "transport/run_claim.json").exists()
    copied_targets = [row["target"] for row in preflight["copied_inputs"]]
    assert copied_targets
    assert all(not Path(target).is_absolute() for target in copied_targets)
    assert all(target.startswith("inputs/") for target in copied_targets)
    state = benchmark.read_json(first / "state.json")
    assert state["status"] == "prepared_zero_call"


def test_copy_file_records_repository_relative_target_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    run_root = repo_root / "experiments/model_benchmarks/path_identity"
    source = repo_root / "config/source.json"
    target = run_root / "inputs/source.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"ok": true}\n', encoding="utf-8")
    monkeypatch.setattr(benchmark, "ROOT", repo_root)

    receipt = benchmark.copy_file(source, target, artifact_root=run_root)

    assert receipt["source"] == "config/source.json"
    assert (
        receipt["target"]
        == "experiments/model_benchmarks/path_identity/inputs/source.json"
    )
    assert not Path(receipt["target"]).is_absolute()


def test_copy_file_records_run_relative_source_for_external_replay(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "replay"
    source = run_root / "incoming/adjudication.json"
    target = run_root / "scorecard/adjudication.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"ok": true}\n', encoding="utf-8")

    receipt = benchmark.copy_file(source, target, artifact_root=run_root)

    assert receipt["source"] == "incoming/adjudication.json"
    assert receipt["target"] == "scorecard/adjudication.json"
    assert all(not Path(receipt[key]).is_absolute() for key in ("source", "target"))


def test_nondefault_temperature_requires_explicit_diagnostic_reason(
    tmp_path: Path,
) -> None:
    root = tmp_path / "temperature_zero"
    with pytest.raises(benchmark.ZBatchError, match="必须显式授权"):
        benchmark.prepare(
            root,
            benchmark_id=root.name,
            stage_id="neutral_extract_x01_ch0003_v3",
            provider_id="qianwen_platform",
            model_id="qwen3.7-plus",
            profile_id="thinking_32k_prompt_json",
        )
    assert not root.exists()


def test_official_deepseek_is_not_available_through_generic_slot() -> None:
    with pytest.raises(benchmark.ZBatchError, match="尚未进入模型试验通道"):
        benchmark.load_provider("deepseek_official")


def test_run_requires_key_before_claiming_single_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_vendor_api_keys(monkeypatch)
    root = tmp_path / "missing_key"
    prepare_qwen(root)

    with pytest.raises(benchmark.ZBatchError, match="缺少 DASHSCOPE_API_KEY"):
        benchmark.run(root)

    assert not (root / "transport/run_claim.json").exists()


def test_verify_rejects_frozen_provider_copy_drift(tmp_path: Path) -> None:
    root = tmp_path / "provider_drift"
    prepare_qwen(root)
    frozen = benchmark.read_json(root / "inputs/provider_config.json")
    frozen["base_url"] = "https://drift.invalid"
    (root / "inputs/provider_config.json").write_text(
        json.dumps(frozen, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(benchmark.ZBatchError, match="供应商配置.*漂移"):
        benchmark.verify_prepared(root)


def test_mocked_run_writes_fixed_candidate_and_score_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sample"
    prepare_qwen(root)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key-not-in-artifacts")
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        assert timeout == 600
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "qwen3.7-plus"
        assert body["temperature"] == 0.2
        assert body["enable_thinking"] is True
        assert body["thinking_budget"] == 32768
        assert "response_format" not in body
        assert "reasoning_effort" not in body
        assert "max_tokens" not in body
        return FakeResponse(response_payload())

    result = benchmark.run(root, opener=opener)

    assert calls == ["https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"]
    assert result["logical_samples"] == 1
    assert result["mechanical_gates"] == "pass"
    assert (root / "transport/raw_responses/attempt01.json").is_file()
    assert (root / "candidate/model_json.json").is_file()
    assert (root / "candidate/neutral_events.json").is_file()
    assert (root / "scorecard/mechanical.json").is_file()
    assert (root / "scorecard/adjudication_template.json").is_file()
    assert result["completion_audit"]["status"] == "pass_rebuilt_from_raw"
    assert (root / "transport/completion_audit.json").is_file()
    assert result["secret_scan"]["exact_key_hit_count"] == 0


def test_thinking_profile_rejects_response_without_observed_reasoning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "thinking_missing"
    prepare_qwen(root)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")

    with pytest.raises(benchmark.BenchmarkHardStop, match="没有可观察的非空"):
        benchmark.run(
            root,
            opener=lambda request, timeout: FakeResponse(
                response_payload(include_reasoning=False)
            ),
        )

    ticket = benchmark.read_json(root / "transport/hard_stop.json")
    assert ticket["reason_code"] == "thinking_not_observed"


def test_completion_audit_rebuilds_and_detects_candidate_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "audit"
    prepare_qwen(root)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    benchmark.run(root, opener=lambda request, timeout: FakeResponse(response_payload()))
    assert benchmark.audit_completed(root)["status"] == "pass_rebuilt_from_raw"

    candidate = benchmark.read_json(root / "candidate/model_json.json")
    candidate["events"][0]["event"] = "被篡改。"
    (root / "candidate/model_json.json").write_text(
        json.dumps(candidate, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(benchmark.ZBatchError, match="不能由原始响应重建"):
        benchmark.audit_completed(root)


def test_completion_audit_rejects_summary_and_checkpoint_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "audit_tamper"
    prepare_qwen(root)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    benchmark.run(root, opener=lambda request, timeout: FakeResponse(response_payload()))

    completion_path = root / "transport/sample_completion.json"
    original_completion = benchmark.read_json(completion_path)
    completion = dict(original_completion)
    completion["usage"] = {"total_tokens": 1}
    completion_path.write_text(
        json.dumps(completion, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(benchmark.ZBatchError, match="样张完成票字段不能"):
        benchmark.audit_completed(root)

    completion_path.write_text(
        json.dumps(original_completion, ensure_ascii=False),
        encoding="utf-8",
    )
    checkpoint_path = root / "transport/checkpoint.json"
    checkpoint = benchmark.read_json(checkpoint_path)
    checkpoint["checkpoint_id"] = "0" * 64
    checkpoint_path.write_text(
        json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(benchmark.ZBatchError, match="检查点 ID"):
        benchmark.audit_completed(root)


def test_key_echo_writes_authoritative_hard_stop_ticket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "key_echo"
    prepare_qwen(root)
    key = "test-secret-key"
    monkeypatch.setenv("DASHSCOPE_API_KEY", key)

    def opener(request, timeout):
        return FakeResponse({"error": key})

    with pytest.raises(benchmark.BenchmarkHardStop, match="回显 API Key"):
        benchmark.run(root, opener=opener)

    ticket = benchmark.read_json(root / "transport/hard_stop.json")
    assert ticket["reason_code"] == "api_key_echoed"
    assert ticket["logical_sample_count"] == 1
    assert ticket["network_attempts"] == 1
    assert ticket["usage_tokens"] == "unknown"
    attempts = benchmark.load_attempt_rows(root / "transport/call_attempts.jsonl")
    assert len(attempts) == 1
    assert attempts[0]["error_code"] == "api_key_echoed"
    assert benchmark.read_json(root / "state.json")["status"] == "hard_stopped"


def test_429_key_echo_stops_after_first_network_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "key_echo_429"
    prepare_qwen(root)
    key = "test-secret-key"
    monkeypatch.setenv("DASHSCOPE_API_KEY", key)

    def opener(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {"Content-Type": "application/json", "Retry-After": "1"},
            io.BytesIO(json.dumps({"error": key}).encode("utf-8")),
        )

    with pytest.raises(benchmark.BenchmarkHardStop, match="回显 API Key"):
        benchmark.run(root, opener=opener)

    ticket = benchmark.read_json(root / "transport/hard_stop.json")
    assert ticket["reason_code"] == "api_key_echoed"
    assert ticket["network_attempts"] == 1
    attempts = benchmark.load_attempt_rows(root / "transport/call_attempts.jsonl")
    assert len(attempts) == 1
    assert attempts[0]["http_status"] == 429
    assert attempts[0]["error_code"] == "api_key_echoed"
    assert not (root / "transport/call_attempts_retry_waits.jsonl").exists()


def test_normal_429_then_success_is_fully_rebuilt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "normal_429_success"
    prepare_qwen(root)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    clock = [100.0]

    def monotonic() -> float:
        return clock[0]

    def sleeper(seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.setattr(benchmark.z83_retry_transport.time, "monotonic", monotonic)
    monkeypatch.setattr(benchmark.z83_retry_transport.time, "sleep", sleeper)
    monkeypatch.setattr(benchmark.z83_retry_transport.random, "random", lambda: 0.0)
    calls = [0]

    def opener(request, timeout):
        calls[0] += 1
        if calls[0] == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Content-Type": "application/json", "Retry-After": "0"},
                io.BytesIO(b'{"error":"rate_limited"}'),
            )
        return FakeResponse(response_payload())

    result = benchmark.run(root, opener=opener)

    assert result["network_attempts"] == 2
    assert result["429_count"] == 1
    assert benchmark.audit_completed(root)["attempt_count"] == 2
    attempts = benchmark.load_attempt_rows(root / "transport/call_attempts.jsonl")
    assert [row["http_status"] for row in attempts] == [429, 200]
    waits = benchmark.z83_retry_transport.read_retry_wait_rows(
        root / "transport/call_attempts.jsonl"
    )
    assert len(waits) == 1
    assert waits[0]["status"] == "completed"


def test_score_writes_summary_receipt_and_keeps_candidate_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "scored"
    prepare_qwen(root)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    benchmark.run(root, opener=lambda request, timeout: FakeResponse(response_payload()))
    template = benchmark.read_json(root / "scorecard/adjudication_template.json")
    adjudication = {
        "schema_version": "model-benchmark-adjudication-v1",
        "gold_sha256": template["gold_sha256"],
        "formal_denominator": 23,
        "gold_rows": [
            {
                "part_id": row["part_id"],
                "verdict": "miss",
                "candidate_event_ids": [],
                "reason": "测试判词：当前唯一候选不覆盖此金标原子。",
            }
            for row in template["gold_rows"]
        ],
    }
    adjudication_path = root / "review.json"
    benchmark.write_json_exclusive(adjudication_path, adjudication)

    result = benchmark.score(root, adjudication_path)

    assert result["candidate_tier"] == "silver_only"
    assert result["promoted_or_default_changed"] is False
    assert result["gold_chapter_3"]["strict_hit"] == 0
    assert (root / "scorecard/final.json").is_file()
    assert "qwen3.7-plus" in (root / "summary.md").read_text(encoding="utf-8")
    assert "来源：Codex" in (root / "receipt.md").read_text(encoding="utf-8")


def test_index_reads_only_benchmark_specs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_root = tmp_path / "model_benchmarks"
    index_root.mkdir()
    run = index_root / "one"
    run.mkdir()
    benchmark.write_json_exclusive(
        run / "benchmark.json",
        {
            "benchmark_id": "one",
            "stage_id": "stage",
            "provider": "qianwen_platform",
            "model": "qwen3.7-plus",
            "profile": "thinking_32k_prompt_json",
        },
    )
    benchmark.write_state(run, status="prepared_zero_call")
    monkeypatch.setattr(benchmark, "BENCHMARK_ROOT", index_root)
    monkeypatch.setattr(benchmark, "INDEX_PATH", index_root / "INDEX.md")

    result = benchmark.rebuild_index()

    assert result["indexed"] == 1
    assert "qwen3.7-plus" in (index_root / "INDEX.md").read_text(encoding="utf-8")
