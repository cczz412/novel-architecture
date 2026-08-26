from __future__ import annotations

import json
from typing import Any


class DuplicateKeyError(ValueError):
    pass


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(key)
        out[key] = value
    return out


def raw_decode_object(text: str) -> tuple[Any, str]:
    decoder = json.JSONDecoder(object_pairs_hook=reject_duplicate_keys)
    stripped = text.lstrip()
    value, end = decoder.raw_decode(stripped)
    trailing = stripped[end:]
    return value, trailing
