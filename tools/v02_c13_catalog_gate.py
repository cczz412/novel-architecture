#!/usr/bin/env python3
"""C13 r06 型号验票的离线解析器。

本工具只读取已保存的响应原件并做确定性核验：不发网络请求，不读取环境变量，
也不读取钥匙串。真正的目录请求或最小握手必须由获准的独立运输入口完成。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/providers/c13_provider_catalog_gate_v1.json"
EXPECTED_PROVIDER_MODELS = {
    "qianwen_platform": "qwen3.7-max-2026-05-20",
    "volcengine_ark": "doubao-seed-2-1-pro-260628",
    "tencent_tokenhub": "minimax-m3",
}
HARD_STOP = "HARD_STOP_PROVIDER_DO_NOT_SEND_C13_90_PROMPTS"


class C13CatalogGateError(ValueError):
    """合同或入参不满足 C13 型号验票要求。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_contract(path: Path | None = None) -> dict[str, Any]:
    path = CONTRACT_PATH if path is None else path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C13CatalogGateError(f"型号验票合同无法读取：{path}") from exc
    if not isinstance(value, dict):
        raise C13CatalogGateError("型号验票合同顶层必须是对象")
    if value.get("schema_version") != "c13-provider-catalog-gate-v1":
        raise C13CatalogGateError("型号验票合同版本不匹配")
    providers = value.get("providers")
    if not isinstance(providers, list) or len(providers) != 3:
        raise C13CatalogGateError("型号验票合同必须恰有三家供应商")
    actual = {
        row.get("provider_id"): row.get("exact_model_id")
        for row in providers
        if isinstance(row, Mapping)
    }
    if actual != EXPECTED_PROVIDER_MODELS:
        raise C13CatalogGateError("型号验票合同的三家精确型号漂移")
    return value


def provider_contract(provider_id: str) -> dict[str, Any]:
    contract = load_contract()
    matches = [
        row
        for row in contract["providers"]
        if isinstance(row, Mapping) and row.get("provider_id") == provider_id
    ]
    if len(matches) != 1:
        raise C13CatalogGateError(f"不认识或重复的供应商：{provider_id}")
    return dict(matches[0])


def frozen_minimal_handshake_body(provider_id: str) -> dict[str, Any]:
    """回读并复验获批的最小握手请求；本函数不发送请求。"""

    profile = provider_contract(provider_id)
    if profile.get("verification_mode") != "NOTION_AUTHORIZED_SINGLE_MINIMAL_HANDSHAKE":
        raise C13CatalogGateError("该供应商没有最小握手请求体")
    request_contract = profile.get("request_contract")
    if not isinstance(request_contract, Mapping):
        raise C13CatalogGateError("最小握手缺请求合同")
    body = request_contract.get("frozen_request_body")
    expected_sha256 = request_contract.get("frozen_request_body_sha256")
    if not isinstance(body, Mapping) or not isinstance(expected_sha256, str):
        raise C13CatalogGateError("最小握手请求体或 SHA 缺失")
    if body.get("model") != profile["exact_model_id"]:
        raise C13CatalogGateError("最小握手请求型号漂移")
    if sha256_bytes(canonical_bytes(body)) != expected_sha256:
        raise C13CatalogGateError("最小握手请求体 SHA 漂移")
    return dict(body)


def _hard_stop(
    profile: Mapping[str, Any], reason_code: str, *, raw_response: bytes
) -> dict[str, Any]:
    return {
        "provider_id": profile["provider_id"],
        "exact_model_id": profile["exact_model_id"],
        "verification_mode": profile["verification_mode"],
        "status": HARD_STOP,
        "reason_code": reason_code,
        "raw_response_sha256": sha256_bytes(raw_response),
        "counts_toward_c13_90_prompt_cap": False,
        "automatic_fallback_allowed": False,
    }


def _decode_json_object(raw_response: bytes) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _require_one_attempt(profile: Mapping[str, Any], attempt_no: int) -> None:
    if type(attempt_no) is not int or attempt_no != 1:
        raise C13CatalogGateError(
            f"{profile['provider_id']} 型号验票只允许第 1 次；不得重试或挑选"
        )
    if profile.get("network_attempt_cap") != 1:
        raise C13CatalogGateError("型号验票合同的单次上限漂移")
    if profile.get("counts_toward_c13_90_prompt_cap") is not False:
        raise C13CatalogGateError("型号验票不得计入 C13 的 90 条题面额度")


def _request_id(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("id") or payload.get("request_id")
    return value if isinstance(value, str) and value.strip() else None


def verify_single_minimal_handshake(
    provider_id: str, raw_response: bytes, *, attempt_no: int
) -> dict[str, Any]:
    """核一份 Notion 已放行的单次最小握手回包；不替代 Notion 授权本身。"""

    profile = provider_contract(provider_id)
    if profile.get("verification_mode") != "NOTION_AUTHORIZED_SINGLE_MINIMAL_HANDSHAKE":
        raise C13CatalogGateError("该供应商不适用最小握手验票")
    frozen_minimal_handshake_body(provider_id)
    _require_one_attempt(profile, attempt_no)
    payload = _decode_json_object(raw_response)
    if payload is None:
        return _hard_stop(profile, "HANDSHAKE_RESPONSE_NOT_UTF8_JSON_OBJECT", raw_response=raw_response)
    if payload.get("model") != profile["exact_model_id"]:
        return _hard_stop(profile, "HANDSHAKE_RESPONSE_MODEL_ID_MISMATCH", raw_response=raw_response)
    if _request_id(payload) is None:
        return _hard_stop(profile, "HANDSHAKE_RESPONSE_REQUEST_ID_MISSING", raw_response=raw_response)
    if not isinstance(payload.get("usage"), Mapping) or not payload["usage"]:
        return _hard_stop(profile, "HANDSHAKE_RESPONSE_USAGE_MISSING", raw_response=raw_response)
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return _hard_stop(profile, "HANDSHAKE_RESPONSE_CHOICE_TOTAL_NOT_ONE", raw_response=raw_response)
    return {
        "provider_id": profile["provider_id"],
        "exact_model_id": profile["exact_model_id"],
        "verification_mode": profile["verification_mode"],
        "status": "PASS_EXACT_MODEL_SINGLE_MINIMAL_HANDSHAKE",
        "attempt_no": attempt_no,
        "notion_authorization_required": True,
        "raw_response_sha256": sha256_bytes(raw_response),
        "response_model_id": payload["model"],
        "response_request_id": _request_id(payload),
        "counts_toward_c13_90_prompt_cap": False,
        "automatic_fallback_allowed": False,
    }


def verify_live_model_catalog(
    provider_id: str, raw_response: bytes, *, attempt_no: int
) -> dict[str, Any]:
    """核一份已保存的实时模型目录原件；不执行 GET /models。"""

    profile = provider_contract(provider_id)
    if profile.get("verification_mode") != "LIVE_MODEL_CATALOG":
        raise C13CatalogGateError("该供应商不适用实时模型目录验票")
    _require_one_attempt(profile, attempt_no)
    payload = _decode_json_object(raw_response)
    if payload is None:
        return _hard_stop(profile, "CATALOG_RESPONSE_NOT_UTF8_JSON_OBJECT", raw_response=raw_response)
    catalog = profile.get("catalog_contract")
    if not isinstance(catalog, Mapping):
        raise C13CatalogGateError("目录验票合同缺 catalog_contract")
    rows = payload.get(catalog.get("data_path"))
    if not isinstance(rows, list):
        return _hard_stop(profile, "CATALOG_DATA_NOT_ARRAY", raw_response=raw_response)
    exact = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get(catalog.get("exact_model_id_field")) == profile["exact_model_id"]
    ]
    if len(exact) != catalog.get("exact_match_total"):
        return _hard_stop(profile, "CATALOG_EXACT_MODEL_ID_NOT_UNIQUE", raw_response=raw_response)
    if exact[0].get(catalog.get("status_field")) != catalog.get("required_status"):
        return _hard_stop(profile, "CATALOG_EXACT_MODEL_NOT_ONLINE", raw_response=raw_response)
    return {
        "provider_id": profile["provider_id"],
        "exact_model_id": profile["exact_model_id"],
        "verification_mode": profile["verification_mode"],
        "status": "PASS_EXACT_MODEL_LIVE_CATALOG",
        "attempt_no": attempt_no,
        "raw_response_sha256": sha256_bytes(raw_response),
        "selected_model": dict(exact[0]),
        "counts_toward_c13_90_prompt_cap": False,
        "automatic_fallback_allowed": False,
    }


def verify_saved_ticket(
    provider_id: str, raw_response: bytes, *, attempt_no: int = 1
) -> dict[str, Any]:
    """按合同分派到目录或最小握手离线验票。"""

    profile = provider_contract(provider_id)
    if profile["verification_mode"] == "LIVE_MODEL_CATALOG":
        return verify_live_model_catalog(provider_id, raw_response, attempt_no=attempt_no)
    return verify_single_minimal_handshake(provider_id, raw_response, attempt_no=attempt_no)


def verify_ticket_set(tickets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """验三家各一张原始票；少票、重票或第 2 次尝试均禁止继续。"""

    if isinstance(tickets, (str, bytes)) or not isinstance(tickets, Sequence):
        raise C13CatalogGateError("验票集合必须是三家原始响应描述")
    if len(tickets) != 3:
        raise C13CatalogGateError("C13 型号验票必须恰有三家各一张票")
    expected_ids = set(EXPECTED_PROVIDER_MODELS)
    seen: set[str] = set()
    receipts: list[dict[str, Any]] = []
    for ticket in tickets:
        if not isinstance(ticket, Mapping) or set(ticket) != {
            "provider_id", "attempt_no", "raw_response"
        }:
            raise C13CatalogGateError("每张票只能含 provider_id、attempt_no、raw_response")
        provider_id = ticket["provider_id"]
        raw_response = ticket["raw_response"]
        if not isinstance(provider_id, str) or provider_id in seen:
            raise C13CatalogGateError("型号验票供应商重复或身份无效")
        if not isinstance(raw_response, bytes):
            raise C13CatalogGateError("型号验票原始响应必须是 bytes")
        seen.add(provider_id)
        receipts.append(
            verify_saved_ticket(
                provider_id, raw_response, attempt_no=ticket["attempt_no"]
            )
        )
    if seen != expected_ids:
        raise C13CatalogGateError("型号验票供应商缺失或越界")
    return receipts


def main() -> int:
    parser = argparse.ArgumentParser(description="C13 r06 型号验票离线解析器")
    parser.add_argument("provider_id", choices=sorted(EXPECTED_PROVIDER_MODELS))
    parser.add_argument("raw_response_path", type=Path)
    parser.add_argument("--attempt-no", type=int, default=1)
    args = parser.parse_args()
    receipt = verify_saved_ticket(
        args.provider_id,
        args.raw_response_path.read_bytes(),
        attempt_no=args.attempt_no,
    )
    print(canonical_bytes(receipt).decode("utf-8"), end="")
    return 0 if receipt["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
