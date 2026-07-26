from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C13_downstream_consumer_program_20260725"
)
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import v02_c13_provider_wire as wire  # noqa: E402


pytestmark = pytest.mark.v02


def _decoded() -> dict[str, Any]:
    return {
        name: (
            json.loads(raw.decode("utf-8"))
            if name.endswith(".json")
            else raw.decode("utf-8")
        )
        for name, raw in wire.build_artifacts().items()
    }


def test_wire_bundle_is_exactly_three_by_thirty_and_still_not_executable() -> None:
    built = _decoded()
    plan = built["plans/wire_dispatch_plan.json"]
    receipt = built["preflight/wire_adapter_receipt.json"]

    assert plan["prompt_slot_total"] == 30
    assert plan["dispatch_total"] == 90
    assert Counter(row["provider_id"] for row in plan["rows"]) == {
        "qianwen_platform": 30,
        "volcengine_ark": 30,
        "tencent_tokenhub": 30,
    }
    assert receipt["provider_pass_total"] == 3
    assert receipt["rendered_request_total"] == 90
    assert receipt["model_api_calls"] == 0
    assert receipt["network_requests"] == 0
    assert receipt["key_value_read"] is False
    assert receipt["execute_allowed"] is False
    assert receipt["remaining_pre_send_blockers"] == [
        "NOTION_EXACT_PROMPT_APPROVED_TO_SEND_PENDING",
        "FLOOR_PASS_NUMERIC_CRITERION_PENDING",
        "THREE_PROVIDER_KEY_PRESENCE_RECHECK_PENDING",
        "REQUIRED_LIVE_CATALOG_GATE_PENDING",
    ]
    assert receipt["first_authorized_response_acceptance_gates"] == [
        "RESPONSE_MODEL_IDENTITY_MUST_MATCH_REQUEST",
        "STRICT_JSON_AND_REASONING_CONTRACT_MUST_PASS",
    ]


def test_same_slot_messages_are_byte_identical_for_all_three_providers() -> None:
    built = _decoded()
    rows = built["plans/wire_dispatch_plan.json"]["rows"]
    by_slot: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_slot.setdefault(row["base_call_id"], []).append(row)

    assert len(by_slot) == 30
    for slot_rows in by_slot.values():
        assert len(slot_rows) == 3
        assert len({row["messages_sha256"] for row in slot_rows}) == 1
        bodies = [built[row["body_path"]] for row in slot_rows]
        assert bodies[0]["messages"] == bodies[1]["messages"] == bodies[2]["messages"]


def test_qwen_max_wire_uses_exact_thinking_fields_without_json_mode() -> None:
    built = _decoded()
    body = built["wire/qianwen_platform/C13-N01.json"]
    profile = built["profiles/qianwen_platform.json"]

    assert body == {
        "model": "qwen3.7-max-2026-05-20",
        "messages": body["messages"],
        "temperature": 0.2,
        "stream": False,
        "enable_thinking": True,
        "thinking_budget": 32768,
    }
    for field in (
        "n",
        "max_tokens",
        "max_completion_tokens",
        "response_format",
        "reasoning_effort",
        "preserve_thinking",
        "tools",
    ):
        assert field not in body
    assert profile["wire_adapter_zero_call_render_passed"] is True
    assert profile["field_evidence_coverage_passed"] is True
    assert profile["field_evidence_snapshot_frozen"] is False
    assert profile["field_evidence_status"] == (
        "STATIC_DOCUMENT_POINTERS_ONLY_NOT_LIVE_COMPATIBILITY"
    )
    assert profile["live_catalog_or_identity_gate_passed"] is False


def test_doubao_wire_does_not_inherit_deepseek_reasoning_effort() -> None:
    built = _decoded()
    body = built["wire/volcengine_ark/C13-N01.json"]

    assert body["model"] == "doubao-seed-2-1-pro-260628"
    assert body["temperature"] == 0.2
    assert body["stream"] is False
    assert body["max_tokens"] == 32768
    assert body["thinking"] == {"type": "enabled"}
    assert "reasoning_effort" not in body
    assert "response_format" not in body
    assert "n" not in body
    assert "tools" not in body


def test_minimax_wire_splits_reasoning_and_uses_default_adaptive_thinking() -> None:
    built = _decoded()
    body = built["wire/tencent_tokenhub/C13-N01.json"]
    profile = built["profiles/tencent_tokenhub.json"]

    assert body["model"] == "minimax-m3"
    assert body["temperature"] == 0.2
    assert body["stream"] is False
    assert body["max_tokens"] == 32768
    assert body["reasoning_split"] is True
    assert "thinking" not in body
    assert "response_format" not in body
    assert "n" not in body
    assert profile["thinking_contract"] == (
        "MODEL_DEFAULT_ADAPTIVE_THINKING_WITH_SEPARATE_REASONING_FIELD"
    )


def test_wire_bundle_contains_no_secret_or_authorization_surface() -> None:
    raw = b"\n".join(wire.build_artifacts().values()).lower()
    for marker in (
        b"authorization: bearer",
        b"sk-",
        b"api_key_value",
        b"secret_value",
    ):
        assert marker not in raw


def test_write_and_check_are_deterministic_without_touching_source_r02(
    tmp_path: Path,
) -> None:
    before = wire.sha256_file(wire.SOURCE_R02 / "artifact_manifest.json")
    output = tmp_path / "wire"
    report = tmp_path / "report"

    first = wire.write_or_verify(output, report, write=True)
    second = wire.write_or_verify(output, report, write=False)

    assert first == second
    assert first["rendered_request_total"] == 90
    assert wire.sha256_file(wire.SOURCE_R02 / "artifact_manifest.json") == before
    assert before == wire.EXPECTED_SOURCE_MANIFEST_SHA256


def test_source_manifest_rejects_changed_real_file_even_if_manifest_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copied = tmp_path / "r02"
    shutil.copytree(wire.SOURCE_R02, copied)
    source = copied / "prompt_review/exact_visible_messages.json"
    source.write_bytes(source.read_bytes() + b"\n")
    monkeypatch.setattr(wire, "SOURCE_R02", copied)

    with pytest.raises(wire.WireFreezeError, match="实物 SHA 漂移"):
        wire.build_artifacts()


def test_check_mode_does_not_create_missing_directories(tmp_path: Path) -> None:
    output = tmp_path / "missing-output"
    report = tmp_path / "missing-report"

    with pytest.raises(wire.WireFreezeError):
        wire.write_or_verify(output, report, write=False)

    assert not output.exists()
    assert not report.exists()


def test_generator_has_no_network_or_provider_sdk_imports() -> None:
    source = Path(wire.__file__).read_text(encoding="utf-8")
    forbidden_imports = (
        "import requests",
        "import httpx",
        "import urllib",
        "import socket",
        "import openai",
        "import anthropic",
    )
    assert not any(marker in source for marker in forbidden_imports)
