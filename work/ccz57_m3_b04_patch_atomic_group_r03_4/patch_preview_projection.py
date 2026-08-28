"""Pure, non-persisted PatchPreview projection for B-04."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from b04_contracts import (
    FORBIDDEN_B05_TYPES,
    PROJECTOR_MAP,
    canonical_bytes,
    exact_keys,
    fail,
    record_ref,
    validate_lineage_locator,
    validate_output_record,
)

PREVIEW_KEYS = {
    "view_type",
    "projector",
    "base_candidate_version_ref",
    "protection_set_ref",
    "patch_ref",
    "causal_hint_proposal_refs",
    "atomic_group_previews",
    "noncommittable_sidecar_proposals",
    "forbidden_b05_record_types_present",
}
GROUP_PREVIEW_KEYS = {
    "atomic_group_id",
    "purpose",
    "proposed_changes",
    "evidence_refs",
    "protected_item_summaries",
}
CHANGE_KEYS = {
    "json_pointer",
    "old_value_summary",
    "old_value_hash",
    "new_value_summary",
}
PROTECTED_SUMMARY_KEYS = {"json_pointer", "value_hash", "reason"}
SIDECAR_KEYS = {"proposal_ref", "display_summary", "committable"}
FORBIDDEN_DECISION_KEYS = {
    "eligibility",
    "mechanical_validation_result",
    "semantic_opinion",
    "route",
    "author_decision",
    "accepted_group_ids",
    "rejected_group_ids",
    "patch_lifecycle_state",
    "child_candidate_version_ref",
    "commit_intent_ref",
    "merge_receipt_ref",
}


def _item_at(base: dict[str, Any], pointer: str) -> dict[str, Any]:
    try:
        index = int(pointer.split("/")[2])
        return base["payload"]["items"][index]
    except (ValueError, IndexError, KeyError, TypeError):
        fail("B04_PREVIEW_BASE_POINTER_INVALID", pointer)


def _strip_sentence(text: str) -> str:
    return text.rstrip("。！？!?；;，,")


def _causal_display(*, base: dict[str, Any], proposal: dict[str, Any]) -> str:
    payload = proposal["payload"]
    from_item = validate_lineage_locator(payload["from_lineage_locator"], base=base)
    to_item = validate_lineage_locator(payload["to_lineage_locator"], base=base)
    from_text = _strip_sentence(from_item["text"])
    to_text = _strip_sentence(to_item["text"])
    if "铜钥匙" in to_text:
        to_summary = "铜钥匙状态"
    else:
        to_summary = to_text
    if payload["hint_kind"] == "DIRECT_POSSIBLE_CAUSE":
        return f"{from_text}，可能与{to_summary}有关。"
    return f"{from_text}，可能与{to_summary}有关。"


def _scan_forbidden(value: Any) -> tuple[set[str], set[str]]:
    found_types: set[str] = set()
    found_keys: set[str] = set()
    if isinstance(value, dict):
        found_keys.update(FORBIDDEN_DECISION_KEYS & set(value))
        for nested in value.values():
            types, keys = _scan_forbidden(nested)
            found_types.update(types)
            found_keys.update(keys)
    elif isinstance(value, list):
        for nested in value:
            types, keys = _scan_forbidden(nested)
            found_types.update(types)
            found_keys.update(keys)
    elif isinstance(value, str) and value in FORBIDDEN_B05_TYPES:
        found_types.add(value)
    return found_types, found_keys


class PatchPreviewProjector:
    """The only projector for the recomputable PatchPreview value."""

    PROJECTOR_NAME = "PatchPreviewProjector"

    @staticmethod
    def persist(_: dict[str, Any]) -> None:
        fail("B04_PREVIEW_PERSISTENCE_FORBIDDEN")

    @staticmethod
    def project(
        *,
        base: dict[str, Any],
        protection: dict[str, Any],
        patch: dict[str, Any],
        causal_records: list[dict[str, Any]],
        attempt_b03_writer: bool = False,
        attempt_source_content_read: bool = False,
    ) -> dict[str, Any]:
        if attempt_b03_writer:
            fail("B03_WRITER_CALL_FORBIDDEN")
        if attempt_source_content_read:
            fail("SOURCE_SLICE_CONTENT_READ_FORBIDDEN")
        validate_output_record(protection)
        validate_output_record(patch)
        if protection["record_type"] != "M3_CANDIDATE_PROTECTION_SET":
            fail("B04_PREVIEW_PROTECTION_INVALID")
        if patch["record_type"] != "M3_PATCH_PROPOSAL":
            fail("B04_PREVIEW_PATCH_INVALID")
        causal_by_ref = {
            canonical_bytes(record_ref(item)): item for item in causal_records
        }
        patch_payload = patch["payload"]
        source_refs = patch_payload["authorized_source_slice_refs"]
        evidence_refs = source_refs or patch_payload["diagnostic_refs"]
        group_previews: list[dict[str, Any]] = []
        for group in patch_payload["atomic_groups"]:
            changes: list[dict[str, Any]] = []
            contains_replace = False
            for operation in group["operations"]:
                if operation["operation_kind"] == "REPLACE_FIELD":
                    contains_replace = True
                    old_item = _item_at(base, operation["json_pointer"])
                    changes.append(
                        {
                            "json_pointer": operation["json_pointer"],
                            "old_value_summary": old_item["text"],
                            "old_value_hash": operation["expected_old_value_hash"],
                            "new_value_summary": operation["new_value"],
                        }
                    )
                elif operation["operation_kind"] == "ADD_CANDIDATE_ITEM":
                    changes.append(
                        {
                            "json_pointer": "/items/-",
                            "old_value_summary": None,
                            "old_value_hash": None,
                            "new_value_summary": operation["new_item"]["text"],
                        }
                    )
                else:
                    fail("B04_PREVIEW_OPERATION_INVALID")
            protected = []
            if contains_replace:
                protected = [
                    {
                        "json_pointer": entry["json_pointer"],
                        "value_hash": entry["value_hash"],
                        "reason": entry["reason"],
                    }
                    for entry in protection["payload"]["protected_entries"]
                ]
            group_previews.append(
                {
                    "atomic_group_id": group["atomic_group_id"],
                    "purpose": group["purpose"],
                    "proposed_changes": changes,
                    "evidence_refs": deepcopy(evidence_refs),
                    "protected_item_summaries": protected,
                }
            )
        sidecars = []
        ordered_causal = []
        for ref in patch_payload["sidecar_proposal_refs"]:
            proposal = causal_by_ref.get(canonical_bytes(ref))
            if proposal is None:
                fail("B04_PREVIEW_SIDECAR_MISSING")
            ordered_causal.append(deepcopy(ref))
            sidecars.append(
                {
                    "proposal_ref": deepcopy(ref),
                    "display_summary": _causal_display(base=base, proposal=proposal),
                    "committable": False,
                }
            )
        preview = {
            "view_type": "DERIVED_RECOMPUTABLE",
            "projector": PROJECTOR_MAP["PatchPreview"],
            "base_candidate_version_ref": record_ref(base),
            "protection_set_ref": record_ref(protection),
            "patch_ref": record_ref(patch),
            "causal_hint_proposal_refs": ordered_causal,
            "atomic_group_previews": group_previews,
            "noncommittable_sidecar_proposals": sidecars,
            "forbidden_b05_record_types_present": [],
        }
        validate_patch_preview(preview)
        return preview


def validate_patch_preview(preview: dict[str, Any]) -> None:
    exact_keys(preview, PREVIEW_KEYS, "B04_PREVIEW_SHAPE_INVALID")
    if preview["view_type"] != "DERIVED_RECOMPUTABLE":
        fail("B04_PREVIEW_IDENTITY_INVALID")
    if preview["projector"] != "PatchPreviewProjector":
        fail("B04_PREVIEW_IDENTITY_INVALID")
    if preview["forbidden_b05_record_types_present"] != []:
        fail("B04_PREVIEW_B05_REFERENCE_FORBIDDEN")
    for group in preview["atomic_group_previews"]:
        exact_keys(group, GROUP_PREVIEW_KEYS, "B04_PREVIEW_GROUP_INVALID")
        for change in group["proposed_changes"]:
            exact_keys(change, CHANGE_KEYS, "B04_PREVIEW_CHANGE_INVALID")
        for item in group["protected_item_summaries"]:
            exact_keys(item, PROTECTED_SUMMARY_KEYS, "B04_PREVIEW_PROTECTED_INVALID")
    for sidecar in preview["noncommittable_sidecar_proposals"]:
        exact_keys(sidecar, SIDECAR_KEYS, "B04_PREVIEW_SIDECAR_INVALID")
        if sidecar["committable"] is not False:
            fail("B04_PREVIEW_SIDECAR_COMMITTABLE")
    found_types, found_keys = _scan_forbidden(preview)
    if found_types or found_keys:
        fail(
            "B04_PREVIEW_B05_REFERENCE_FORBIDDEN",
            f"types={sorted(found_types)}; keys={sorted(found_keys)}",
        )
