from __future__ import annotations

import re
from typing import Any

from .refs import canonical_hash

SYNTHETIC_PREFIX = re.compile(r"^合成句[：:]")
LEAKY_NAME = re.compile(r"(pass|fail|gold|supported|rejected)", re.I)


def reason_pair_error(pair: dict[str, Any], *, filename: str) -> str | None:
    if LEAKY_NAME.search(filename):
        return f"FILENAME_LEAKS_DIRECTION:{filename}"
    if pair.get("candidate_status") != "CANDIDATE":
        return "REASON_CODE_NOT_CANDIDATE"
    if pair.get("calibrated") is True or pair.get("not_calibrated") is not True:
        return "MUST_NOT_CLAIM_CALIBRATED"
    if pair.get("single_primary_reason") is not True:
        return "ONE_PRIMARY_REASON_REQUIRED"
    for key in ("positive", "negative_minimal", "surface_rewrite"):
        blob = pair.get(key) or {}
        text = blob.get("text")
        if not isinstance(text, str) or not SYNTHETIC_PREFIX.search(text):
            return f"TEXT_NOT_SYNTHETIC:{key}"
    declared = pair.get("pair_hash")
    material = {
        "pair_id": pair.get("pair_id"),
        "candidate_code": pair.get("candidate_code"),
        "positive": pair.get("positive"),
        "negative_minimal": pair.get("negative_minimal"),
        "surface_rewrite": pair.get("surface_rewrite"),
    }
    actual = canonical_hash(material)
    if declared != actual:
        return f"PAIR_HASH_MISMATCH:{pair.get('pair_id')}"
    return None
