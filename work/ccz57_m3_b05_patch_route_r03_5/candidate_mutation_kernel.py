"""Pure CandidateVersion mutation shared by B-05 trial apply and B-06 commit."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from b05_contracts import canonical_bytes, record_ref, sha256_value


def find_lineage(value: Any) -> str | None:
    if isinstance(value, dict):
        lineage = value.get("lineage_id")
        if isinstance(lineage, str) and lineage:
            return lineage
        for child in value.values():
            found = find_lineage(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_lineage(child)
            if found is not None:
                return found
    return None


def item_hash(item: dict[str, Any]) -> str:
    return sha256_value(
        {key: value for key, value in item.items() if key != "item_hash"}
    )


def apply_groups(
    base_payload: dict[str, Any],
    groups: list[dict[str, Any]],
    *,
    canonical_add_sort: bool,
) -> tuple[dict[str, Any], list[str]]:
    """Apply validated B-04 groups without persistence or route decisions."""

    payload = deepcopy(base_payload)
    items = payload.get("items")
    if not isinstance(items, list):
        return payload, ["CANDIDATE_STRUCTURE_INVALID"]
    base_item_count = len(items)
    errors: list[str] = []
    for group in groups:
        for operation in group["operations"]:
            kind = operation.get("operation_kind")
            if kind == "REPLACE_CANDIDATE_ITEM":
                lineage = find_lineage(operation.get("target"))
                matches = [
                    index
                    for index, item in enumerate(items)
                    if item.get("lineage_id") == lineage
                ]
                if len(matches) != 1:
                    errors.append("EXPECTED_OLD_ITEM_HASH_MISMATCH")
                    continue
                index = matches[0]
                actual_hash = items[index].get("item_hash") or item_hash(items[index])
                if actual_hash != operation.get("expected_old_item_hash"):
                    errors.append("EXPECTED_OLD_ITEM_HASH_MISMATCH")
                    continue
                replacement = deepcopy(operation.get("new_item"))
                if not isinstance(replacement, dict):
                    errors.append("CANDIDATE_STRUCTURE_INVALID")
                    continue
                replacement["item_hash"] = item_hash(replacement)
                items[index] = replacement
            elif kind == "ADD_CANDIDATE_ITEM":
                addition = deepcopy(operation.get("new_item"))
                if not isinstance(addition, dict):
                    errors.append("CANDIDATE_STRUCTURE_INVALID")
                    continue
                addition["item_hash"] = item_hash(addition)
                items.append(addition)
            else:
                errors.append("FORBIDDEN_B05_RESPONSIBILITY_REQUESTED")
    if canonical_add_sort:
        items = [
            *items[:base_item_count],
            *sorted(
                items[base_item_count:],
                key=lambda item: canonical_bytes(item.get("lineage_id", "")),
            ),
        ]
    lineages = [item.get("lineage_id") for item in items]
    if any(not isinstance(item, str) or not item for item in lineages):
        errors.append("CANDIDATE_STRUCTURE_INVALID")
    if len(set(lineages)) != len(lineages):
        errors.append("CANDIDATE_STRUCTURE_INVALID")
    payload["items"] = items
    if "items_hash" in payload:
        payload["items_hash"] = sha256_value(items)
    if "lineage_index" in payload:
        payload["lineage_index"] = [
            {
                "lineage_id": item["lineage_id"],
                "json_pointer": f"/items/{index}",
                "item_hash": item["item_hash"],
            }
            for index, item in enumerate(items)
        ]
    if "version_payload_hash" in payload:
        payload["version_payload_hash"] = sha256_value(
            {
                key: value
                for key, value in payload.items()
                if key != "version_payload_hash"
            }
        )
    return payload, sorted(set(errors))


def build_child_payload(
    base_record: dict[str, Any], mutated_payload: dict[str, Any]
) -> dict[str, Any]:
    """Bind a mutation result to its exact parent and recompute child identity."""

    payload = deepcopy(mutated_payload)
    payload["parent_candidate_version_ref"] = record_ref(base_record)
    payload["origin_commit_intent_ref"] = None
    payload["version_payload_hash"] = sha256_value(
        {key: value for key, value in payload.items() if key != "version_payload_hash"}
    )
    return payload
