"""模块 4：Prompt 渲染与 SHA 钉死。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .errors import ZBatchError

PromptContractError = ZBatchError


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_prompt(template: str, values: dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", value)
    leftovers = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", result)))
    if leftovers:
        raise PromptContractError(f"Prompt 仍有未填占位符：{leftovers}")
    return result


replace_prompt = render_prompt


def prompt_sha256(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def verify_pin(path: Path, expected_sha256: str) -> dict[str, object]:
    actual = sha256_file(path) if path.is_file() else None
    return {
        "path": str(path),
        "expected_sha256": expected_sha256,
        "actual_sha256": actual,
        "matches_pin": actual == expected_sha256,
    }


def load_pinned_text(path: Path, expected_sha256: str) -> str:
    result = verify_pin(path, expected_sha256)
    if not result["matches_pin"]:
        raise PromptContractError(
            f"Prompt SHA 漂移：expected={expected_sha256},actual={result['actual_sha256']}"
        )
    return path.read_text(encoding="utf-8")
