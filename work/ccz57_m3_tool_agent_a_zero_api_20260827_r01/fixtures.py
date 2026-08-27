"""Synthetic fixtures only. No novel corpus text."""

from __future__ import annotations

import hashlib
import json

from zero_api_shell import pack_tool_bundle

CHAPTER_TEXT = "林澈关上窗。雨声变小。"
REVISION = {
    "chapter_id": "c01",
    "revision_no": 2,
    "revision_text_sha256": hashlib.sha256(CHAPTER_TEXT.encode("utf-8")).hexdigest(),
}
C1 = {
    "contract": "C1_CHAPTER_DOC",
    "version": "v1",
    "id": "c01",
    "title": "合成章节",
    "kind": "draft",
    "text": CHAPTER_TEXT,
    "added_at": "2026-08-27 00:00:00",
    "chapter_revision_ref": REVISION,
}
C2 = {
    "contract": "C2_SEGMENT",
    "version": "v1",
    "chapter_revision_ref": REVISION,
    "seg": 1,
    "text": CHAPTER_TEXT,
    "start": 0,
    "end": len(CHAPTER_TEXT),
    "halo_before": "",
    "halo_after": "",
}
OPENROUTER_IDENTITY = {"model": "synthetic/model", "provider": "synthetic-provider"}
ARK_IDENTITY = {"model": "synthetic-model", "endpoint": "ep-synthetic"}
OPENROUTER_BUNDLE = pack_tool_bundle(
    protocol="openrouter_chat_completions",
    exact_model_identity=OPENROUTER_IDENTITY,
)
ARK_BUNDLE = pack_tool_bundle(
    protocol="ark_responses",
    exact_model_identity=ARK_IDENTITY,
)
OPENROUTER_RUN_IDENTITY = {
    "run_id": "synthetic-run",
    "provider_protocol": "openrouter_chat_completions",
    "model": OPENROUTER_IDENTITY["model"],
    "upstream_identity": {"provider": OPENROUTER_IDENTITY["provider"]},
    "reasoning": {"mode": "disabled"},
    "config": {
        "temperature": 0,
        "max_tokens": 256,
        "tool_bundle_id": "baseline-r01.1",
        "tool_provider_payload_sha256": OPENROUTER_BUNDLE[
            "provider_payload_sha256"
        ],
        "tool_internal_schema_sha256": OPENROUTER_BUNDLE[
            "canonical_internal_schema_sha256"
        ],
    },
}
ARK_RUN_IDENTITY = {
    "run_id": "synthetic-ark-run",
    "provider_protocol": "ark_responses",
    "model": ARK_IDENTITY["model"],
    "upstream_identity": {"endpoint": ARK_IDENTITY["endpoint"]},
    "reasoning": {"mode": "disabled"},
    "config": {
        "temperature": 0,
        "max_output_tokens": 256,
        "tool_bundle_id": "baseline-r01.1",
        "tool_provider_payload_sha256": ARK_BUNDLE["provider_payload_sha256"],
        "tool_internal_schema_sha256": ARK_BUNDLE[
            "canonical_internal_schema_sha256"
        ],
    },
}


def _raw(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


OPENROUTER_REQUEST = _raw(
    {
        "model": OPENROUTER_IDENTITY["model"],
        "provider": {
            "order": [OPENROUTER_IDENTITY["provider"]],
            "allow_fallbacks": False,
        },
        "reasoning": OPENROUTER_RUN_IDENTITY["reasoning"],
        "temperature": 0,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "synthetic input"}],
        "tools": OPENROUTER_BUNDLE["provider_payload"],
    }
)

ARK_REQUEST = _raw(
    {
        "model": ARK_IDENTITY["model"],
        "endpoint": ARK_IDENTITY["endpoint"],
        "reasoning": ARK_RUN_IDENTITY["reasoning"],
        "temperature": 0,
        "max_output_tokens": 256,
        "input": [{"role": "user", "content": "synthetic input"}],
        "tools": ARK_BUNDLE["provider_payload"],
    }
)


OPENROUTER_TOOL = _raw(
    {
        "id": "resp-or-1",
        "model": OPENROUTER_IDENTITY["model"],
        "provider": OPENROUTER_IDENTITY["provider"],
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-or-1",
                            "type": "function",
                            "function": {
                                "name": "submit_baseline_candidate",
                                "arguments": json.dumps(
                                    {
                                        "expected_revision_ref": REVISION,
                                        "facts": [
                                            {"text": "林澈关上窗。", "quote": "林澈关上窗。"}
                                        ],
                                    },
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ),
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 12},
    }
)

ARK_TOOL = _raw(
    {
        "id": "resp-ark-1",
        "model": ARK_IDENTITY["model"],
        "endpoint": ARK_IDENTITY["endpoint"],
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "id": "fc-1",
                "call_id": "call-ark-1",
                "name": "read_current_c2_segment",
                "arguments": json.dumps(
                    {"expected_revision_ref": REVISION}, separators=(",", ":")
                ),
            }
        ],
        "usage": {"input_tokens": 9, "output_tokens": 5},
    }
)

OPENROUTER_LEGACY = _raw(
    {
        "id": "resp-old-1",
        "model": OPENROUTER_IDENTITY["model"],
        "provider": OPENROUTER_IDENTITY["provider"],
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {"facts": [{"text": "林澈关上窗。", "quote": "林澈关上窗。"}]},
                        ensure_ascii=False,
                    )
                },
            }
        ],
    }
)

OPENROUTER_BAD_OUTER = b'{"id":"broken"'

OPENROUTER_BAD_CONTENT = _raw(
    {
        "id": "resp-old-bad-content",
        "model": OPENROUTER_IDENTITY["model"],
        "provider": OPENROUTER_IDENTITY["provider"],
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": '{"facts":['},
            }
        ],
    }
)

OPENROUTER_BAD_SCHEMA = _raw(
    {
        "id": "resp-old-bad-schema",
        "model": OPENROUTER_IDENTITY["model"],
        "provider": OPENROUTER_IDENTITY["provider"],
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {"facts": [{"text": "合成事实。", "speaker": "林澈"}]},
                        ensure_ascii=False,
                    )
                },
            }
        ],
    }
)
