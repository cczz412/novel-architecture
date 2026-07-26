from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c13_catalog_gate as gate  # noqa: E402


pytestmark = pytest.mark.v02


def _raw(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _handshake(model_id: str) -> bytes:
    return _raw(
        {
            "id": "hs-c13-r06",
            "model": model_id,
            "usage": {"total_tokens": 1},
            "choices": [{"message": {"content": "ok"}}],
        }
    )


def _catalog(rows: list[object]) -> bytes:
    return _raw({"data": rows})


def test_contract_freezes_exact_three_provider_models_and_no_fallback() -> None:
    contract = gate.load_contract()

    assert {
        row["provider_id"]: row["exact_model_id"]
        for row in contract["providers"]
    } == gate.EXPECTED_PROVIDER_MODELS
    assert contract["global_rules"]["automatic_fallback_allowed"] is False
    assert contract["global_rules"]["near_match_model_id_allowed"] is False
    assert contract["global_rules"]["model_api_calls_by_this_verifier"] == 0
    assert contract["global_rules"]["key_value_read_by_this_verifier"] is False


@pytest.mark.parametrize(
    ("provider_id", "model_id"),
    [
        ("qianwen_platform", "qwen3.7-max-2026-05-20"),
        ("volcengine_ark", "doubao-seed-2-1-pro-260628"),
    ],
)
def test_notion_authorized_handshake_requires_exact_response_model(
    provider_id: str, model_id: str
) -> None:
    body = gate.frozen_minimal_handshake_body(provider_id)
    receipt = gate.verify_single_minimal_handshake(
        provider_id, _handshake(model_id), attempt_no=1
    )

    assert body["model"] == model_id
    assert body["messages"] == [
        {
            "role": "user",
            "content": '只回复一个 JSON 对象：{"ok":true}',
        }
    ]
    assert receipt["status"] == "PASS_EXACT_MODEL_SINGLE_MINIMAL_HANDSHAKE"
    assert receipt["response_model_id"] == model_id
    assert receipt["notion_authorization_required"] is True
    assert receipt["counts_toward_c13_90_prompt_cap"] is False


def test_handshake_rejects_near_model_and_second_attempt() -> None:
    receipt = gate.verify_single_minimal_handshake(
        "qianwen_platform", _handshake("qwen3.7-max"), attempt_no=1
    )
    assert receipt["status"] == gate.HARD_STOP
    assert receipt["reason_code"] == "HANDSHAKE_RESPONSE_MODEL_ID_MISMATCH"

    with pytest.raises(gate.C13CatalogGateError, match="只允许第 1 次"):
        gate.verify_single_minimal_handshake(
            "qianwen_platform",
            _handshake("qwen3.7-max-2026-05-20"),
            attempt_no=2,
        )


def test_handshake_body_sha_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = gate.load_contract()
    contract["providers"][0]["request_contract"]["frozen_request_body"][
        "temperature"
    ] = 0.2
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(gate, "CONTRACT_PATH", path)

    with pytest.raises(gate.C13CatalogGateError, match="请求体 SHA 漂移"):
        gate.frozen_minimal_handshake_body("qianwen_platform")


def test_tencent_catalog_requires_one_exact_online_model() -> None:
    receipt = gate.verify_live_model_catalog(
        "tencent_tokenhub",
        _catalog([{"id": "minimax-m3", "status": "online"}]),
        attempt_no=1,
    )
    assert receipt["status"] == "PASS_EXACT_MODEL_LIVE_CATALOG"
    assert receipt["selected_model"] == {"id": "minimax-m3", "status": "online"}

    near = gate.verify_live_model_catalog(
        "tencent_tokenhub",
        _catalog([{"id": "minimax-m3-preview", "status": "online"}]),
        attempt_no=1,
    )
    assert near["status"] == gate.HARD_STOP
    assert near["reason_code"] == "CATALOG_EXACT_MODEL_ID_NOT_UNIQUE"

    offline = gate.verify_live_model_catalog(
        "tencent_tokenhub",
        _catalog([{"id": "minimax-m3", "status": "offline"}]),
        attempt_no=1,
    )
    assert offline["status"] == gate.HARD_STOP
    assert offline["reason_code"] == "CATALOG_EXACT_MODEL_NOT_ONLINE"


def test_ticket_set_requires_exactly_one_raw_ticket_per_provider() -> None:
    tickets = [
        {
            "provider_id": "qianwen_platform",
            "attempt_no": 1,
            "raw_response": _handshake("qwen3.7-max-2026-05-20"),
        },
        {
            "provider_id": "volcengine_ark",
            "attempt_no": 1,
            "raw_response": _handshake("doubao-seed-2-1-pro-260628"),
        },
        {
            "provider_id": "tencent_tokenhub",
            "attempt_no": 1,
            "raw_response": _catalog([{"id": "minimax-m3", "status": "online"}]),
        },
    ]

    receipts = gate.verify_ticket_set(tickets)
    assert [row["status"] for row in receipts] == [
        "PASS_EXACT_MODEL_SINGLE_MINIMAL_HANDSHAKE",
        "PASS_EXACT_MODEL_SINGLE_MINIMAL_HANDSHAKE",
        "PASS_EXACT_MODEL_LIVE_CATALOG",
    ]

    with pytest.raises(gate.C13CatalogGateError, match="恰有三家"):
        gate.verify_ticket_set(tickets[:2])


def test_verifier_has_no_network_or_environment_key_reads() -> None:
    source = Path(gate.__file__).read_text(encoding="utf-8")
    forbidden = (
        "import urllib",
        "import requests",
        "import httpx",
        "import socket",
        "import os",
        "getenv(",
        "environ",
        "security find-generic-password",
    )
    assert not any(marker in source for marker in forbidden)
