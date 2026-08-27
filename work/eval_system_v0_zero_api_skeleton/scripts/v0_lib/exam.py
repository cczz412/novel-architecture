from __future__ import annotations

import re
from typing import Any

PUBLIC_MANIFEST_ALLOWLIST = {
    "item_id",
    "item_version",
    "task_kind",
    "split",
    "leakage_group_uid",
    "reference_status",
    "rights_status",
    "unreviewed",
}

NAKED_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _leaky_public_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if NAKED_SHA256.fullmatch(text):
        return "NAKED_HASH"
    lowered = text.lower()
    if (
        text.startswith("/")
        or text.startswith("work/")
        or text.startswith("./")
        or "\\" in text
        or "/users/" in lowered
        or ":\\" in text
    ):
        return "PATH"
    if "合成句" in text or "chapter_text" in lowered:
        return "PROSE"
    return None


def exam_error(pack: dict[str, Any]) -> str | None:
    items = pack.get("items") or []
    exposures = pack.get("exposures") or []
    public_manifest = pack.get("public_manifest") or []

    for item in items:
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id.startswith("syn."):
            return f"ITEM_ID_NOT_SYNTHETIC:{item_id!r}"
        group = item.get("leakage_group_uid")
        if not isinstance(group, str) or not group.startswith("syn.lg."):
            return f"LEAKAGE_GROUP_NOT_SYNTHETIC:{group!r}"
        if item.get("reference_status") == "GOLD":
            return f"GOLD_FORBIDDEN:{item_id}"
        split_at = item.get("split_assigned_at")
        sampled_at = item.get("sampled_at")
        if sampled_at and split_at and sampled_at < split_at:
            return f"SAMPLE_BEFORE_SPLIT:{item_id}"

    exposed_short_groups: set[str] = set()
    for row in exposures:
        if row.get("exposure_kind") == "SHORT_DIAGNOSIS":
            exposed_short_groups.add(row["leakage_group_uid"])
        item = _item(items, row.get("item_id"))
        if item and row.get("exposed_at") and item.get("split_assigned_at"):
            if row["exposed_at"] < item["split_assigned_at"]:
                return f"EXPOSURE_BEFORE_SPLIT:{row.get('item_id')}"

    claimed_unseen = pack.get("claimed_unseen_groups") or []
    for group in claimed_unseen:
        if group in exposed_short_groups:
            return f"EXPOSED_GROUP_CANNOT_BE_UNSEEN:{group}"

    for item in items:
        if item.get("unreviewed") is True and item.get("auto_fail") is True:
            return f"UNREVIEWED_AUTO_FAIL:{item.get('item_id')}"

    for row in public_manifest:
        extra = set(row) - PUBLIC_MANIFEST_ALLOWLIST
        if extra:
            return f"PUBLIC_MANIFEST_EXTRA_KEYS:{sorted(extra)}"
        for key, value in row.items():
            leak = _leaky_public_value(value)
            if leak:
                return f"PUBLIC_MANIFEST_FORBIDDEN_VALUE:{leak}:{key}"

    return None


def _item(items: list[dict[str, Any]], item_id: Any) -> dict[str, Any] | None:
    for item in items:
        if item.get("item_id") == item_id:
            return item
    return None
