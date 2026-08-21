from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import extract
finally:
    sys.path.pop(0)


CFG = {
    "model_id": "NO_API_SYNTHETIC",
    "max_output_tokens": 100,
    "call_timeout_seconds": 5,
}


def _completed(*, stdout: str, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["arkcli"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_timeout_is_structured_and_single_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def timeout(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired("arkcli", 5)

    monkeypatch.setattr(extract.subprocess, "run", timeout)

    with pytest.raises(extract.ExtractCallFailure) as caught:
        extract.call_json("instructions", "content", CFG)

    assert calls == 1
    assert caught.value.completion_state == "FAILED_TIMEOUT"
    assert caught.value.code == "ARKCLI_TIMEOUT"
    assert caught.value.raw_response_sha256 is None
    assert caught.value.raw_response_bytes is None


def test_truncated_output_keeps_legacy_message_only_constructor() -> None:
    failure = extract.TruncatedOutput("truncated")

    assert isinstance(failure, RuntimeError)
    assert failure.completion_state == "INCOMPLETE_TRUNCATED"
    assert failure.code == "MODEL_OUTPUT_TRUNCATED"


def test_transport_error_records_raw_stdout_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = "gateway unavailable"
    monkeypatch.setattr(
        extract.subprocess,
        "run",
        lambda *args, **kwargs: _completed(stdout=raw, returncode=7),
    )

    with pytest.raises(extract.ExtractCallFailure) as caught:
        extract.call_json("instructions", "content", CFG)

    assert caught.value.completion_state == "FAILED_TRANSPORT"
    assert caught.value.code == "ARKCLI_EXIT_7"
    assert caught.value.raw_response_sha256 == _sha(raw)
    assert caught.value.raw_response_bytes == len(raw.encode("utf-8"))


def test_invalid_outer_response_is_structured_raw_response_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = "not-json"
    monkeypatch.setattr(
        extract.subprocess,
        "run",
        lambda *args, **kwargs: _completed(stdout=raw),
    )

    with pytest.raises(extract.ExtractCallFailure) as caught:
        extract.call_json("instructions", "content", CFG)

    assert caught.value.completion_state == "FAILED_RAW_RESPONSE"
    assert caught.value.code == "ARKCLI_ENVELOPE_JSON_INVALID"
    assert caught.value.raw_response_sha256 == _sha(raw)


@pytest.mark.parametrize("raw", ["[]", "null"])
def test_non_object_outer_response_is_structured_raw_response_failure(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    monkeypatch.setattr(
        extract.subprocess,
        "run",
        lambda *args, **kwargs: _completed(stdout=raw),
    )

    with pytest.raises(extract.ExtractCallFailure) as caught:
        extract.call_json("instructions", "content", CFG)

    assert caught.value.completion_state == "FAILED_RAW_RESPONSE"
    assert caught.value.code == "ARKCLI_ENVELOPE_NOT_OBJECT"
    assert caught.value.raw_response_sha256 == _sha(raw)


def test_truncated_content_is_structured_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = json.dumps(
        {
            "content": '{"facts":[',
            "usage": {"completion_tokens": 100},
            "model": "SYNTHETIC",
            "finish_reason": "length",
        },
        ensure_ascii=False,
    )
    calls = 0

    def one_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _completed(stdout=raw)

    monkeypatch.setattr(extract.subprocess, "run", one_call)

    with pytest.raises(extract.TruncatedOutput) as caught:
        extract.call_json("instructions", "content", CFG)

    assert calls == 1
    assert caught.value.completion_state == "INCOMPLETE_TRUNCATED"
    assert caught.value.code == "MODEL_OUTPUT_TRUNCATED"
    assert caught.value.finish_reason == "length"
    assert caught.value.raw_response_sha256 == _sha(raw)


def test_extract_segment_propagates_truncation_after_one_model_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def truncated(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise extract.TruncatedOutput(
            "truncated",
            finish_reason="length",
            raw_response_sha256="0" * 64,
            raw_response_bytes=10,
        )

    monkeypatch.setattr(extract, "call_model", truncated)

    with pytest.raises(extract.TruncatedOutput):
        extract.extract_segment(
            {
                "seg": 1,
                "text": "合成责任段",
                "halo_before": "",
                "halo_after": "",
            },
            CFG,
        )

    assert calls == 1
