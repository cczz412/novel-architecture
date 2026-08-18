from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FROZEN_VALIDATOR = Path(
    "/Users/a1234/挣钱/小说架构/TEMP/"
    "v0_c3_output_contract_handshake_preflight_20260818_r01/normalize_and_validate.py"
)
FROZEN_VALIDATOR_SHA256 = "061cf0f98042258a2be4f8afe2e7a23306b914394707feb2de71f291b6c70428"
EXACT_FENCE = re.compile(r"\A```json\r?\n(?P<body>[\s\S]+)\r?\n```\Z")


class UnifiedContractError(ValueError):
    pass


@dataclass(frozen=True)
class UnwrappedContent:
    payload: dict[str, Any]
    payload_text: str
    transport_shape: str
    content_sha256: str
    payload_sha256: str
    rewrap_exact: bool


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_frozen_validator():
    if sha256_bytes(FROZEN_VALIDATOR.read_bytes()) != FROZEN_VALIDATOR_SHA256:
        raise UnifiedContractError("FROZEN_VALIDATOR_DRIFT")
    spec = importlib.util.spec_from_file_location(
        "frozen_handshake_validator_for_unified_replay", FROZEN_VALIDATOR
    )
    if spec is None or spec.loader is None:
        raise UnifiedContractError("FROZEN_VALIDATOR_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def unwrap_content(content: str) -> UnwrappedContent:
    if not isinstance(content, str) or not content:
        raise UnifiedContractError("EMPTY_OR_NON_STRING_CONTENT")
    if content != content.strip():
        raise UnifiedContractError("OUTSIDE_WHITESPACE_OR_TEXT")
    content_raw = content.encode("utf-8")

    if content.startswith("```"):
        match = EXACT_FENCE.fullmatch(content)
        if not match:
            raise UnifiedContractError("FENCE_SHAPE")
        payload_text = match.group("body")
        if "```" in payload_text:
            raise UnifiedContractError("NESTED_OR_MULTIPLE_FENCE")
        shape = "EXACT_SINGLE_JSON_FENCE"
        rewrap_exact = f"```json\n{payload_text}\n```" == content
        if not rewrap_exact and "\r\n" not in content:
            raise UnifiedContractError("FENCE_REWRAP_MISMATCH")
    else:
        if "```" in content:
            raise UnifiedContractError("FENCE_SHAPE")
        payload_text = content
        shape = "NAKED_JSON"
        rewrap_exact = True

    payload_raw = payload_text.encode("utf-8")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise UnifiedContractError("BAD_JSON") from exc
    if not isinstance(payload, dict):
        raise UnifiedContractError("TOP_LEVEL_NOT_OBJECT")
    return UnwrappedContent(
        payload=payload,
        payload_text=payload_text,
        transport_shape=shape,
        content_sha256=sha256_bytes(content_raw),
        payload_sha256=sha256_bytes(payload_raw),
        rewrap_exact=rewrap_exact,
    )


def normalize_and_validate(
    content: str, route: str, expected_input_sha256: str
) -> UnwrappedContent:
    unwrapped = unwrap_content(content)
    before = json.dumps(unwrapped.payload, ensure_ascii=False, sort_keys=True)
    validator = load_frozen_validator()
    validator.validate_candidate(unwrapped.payload, route, expected_input_sha256)
    after = json.dumps(unwrapped.payload, ensure_ascii=False, sort_keys=True)
    if before != after:
        raise UnifiedContractError("VALIDATOR_MUTATED_PAYLOAD")
    return unwrapped
