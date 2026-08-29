"""Pure, non-persisted full-item PatchPreview projection for B-04 r03.5."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from b04_contracts import (
    FORBIDDEN_B05_TYPES,
    PROJECTOR_MAP,
    canonical_bytes,
    exact_keys,
    expected_protected_entries,
    fail,
    record_ref,
    validate_evidence_locator,
    validate_lineage_locator,
    validate_output_record,
)

PREVIEW_KEYS = {
    "view_type",
    "projector",
    "base_candidate_version_ref",
    "protection_set_ref",
    "patch_ref",
    "diagnostic_refs",
    "coverage_observation_refs",
    "authorized_source_slice_refs",
    "causal_hint_proposal_refs",
    "atomic_group_previews",
    "noncommittable_sidecar_proposals",
    "forbidden_b05_record_types_present",
}
GROUP_PREVIEW_KEYS = {
    "atomic_group_id",
    "purpose",
    "proposed_changes",
    "supporting_diagnostic_refs",
    "supporting_coverage_refs",
    "authorized_source_slice_refs",
    "protected_item_summaries",
}
CHANGE_KEYS = {
    "operation_kind",
    "target_json_pointer",
    "old_item_hash",
    "old_item_summary",
    "new_item_summary",
}
ITEM_SUMMARY_KEYS = {
    "lineage_id",
    "fact",
    "status",
    "evidence",
    "speaker_if_present",
    "evidence_binding_hash",
}
PROTECTED_SUMMARY_KEYS = {"json_pointer", "protected_item_hash", "reason"}
SIDECAR_KEYS = {"proposal_ref", "display_summary", "committable"}
FORBIDDEN_DECISION_KEYS = {
    "eligibility",
    "mechanical_validation_result",
    "semantic_opinion",
    "supports_result",
    "contradicts_result",
    "route",
    "manual_review_result",
    "author_decision",
    "accepted_group_ids",
    "rejected_group_ids",
    "patch_lifecycle_state",
    "child_candidate_version_ref",
    "commit_intent_ref",
    "formal_fact_confirmation",
    "formal_fact_ref",
}


def _item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "lineage_id": item["lineage_id"],
        "fact": item["fact"],
        "status": item["status"],
        "evidence": item["evidence"],
        "speaker_if_present": item.get("speaker"),
        "evidence_binding_hash": item["evidence_binding"]["binding_hash"],
    }


def _item_at(context: dict[str, Any], pointer: str) -> dict[str, Any]:
    try:
        index = int(pointer.split("/")[2])
        return context["candidate_version"]["payload"]["items"][index]
    except (ValueError, IndexError, KeyError, TypeError):
        fail("B04_PREVIEW_BASE_POINTER_INVALID", pointer)


def _causal_display(*, context: dict[str, Any], proposal: dict[str, Any]) -> str:
    payload = proposal["payload"]
    from_item = validate_lineage_locator(
        payload["from_lineage_locator"], context=context
    )
    to_item = validate_lineage_locator(payload["to_lineage_locator"], context=context)
    return f"{from_item['fact']}，可能与{to_item['fact']}有关。"


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
        context: dict[str, Any],
        protection: dict[str, Any],
        patch: dict[str, Any],
        causal_records: list[dict[str, Any]],
        selected_group_ids: set[str] | None = None,
        attempt_b03_writer: bool = False,
        attempt_source_content_read: bool = False,
        attempt_b05_call: bool = False,
    ) -> dict[str, Any]:
        if attempt_b03_writer:
            fail("B03_WRITER_CALL_FORBIDDEN")
        if attempt_source_content_read:
            fail("SOURCE_SLICE_CONTENT_READ_FORBIDDEN")
        if attempt_b05_call:
            fail("B05_CALL_FORBIDDEN")
        validate_output_record(protection)
        validate_output_record(patch)
        if protection["record_type"] != "M3_CANDIDATE_PROTECTION_SET":
            fail("B04_PREVIEW_PROTECTION_INVALID")
        if patch["record_type"] != "M3_PATCH_PROPOSAL":
            fail("B04_PREVIEW_PATCH_INVALID")
        patch_payload = patch["payload"]
        all_group_ids = {
            group["atomic_group_id"] for group in patch_payload["atomic_groups"]
        }
        selected = all_group_ids if selected_group_ids is None else selected_group_ids
        if (
            not isinstance(selected, set)
            or not selected
            or not selected <= all_group_ids
        ):
            fail("B04_PREVIEW_GROUP_SELECTION_INVALID")
        expected_global_protection = expected_protected_entries(
            context=context, groups=patch_payload["atomic_groups"]
        )
        if protection["payload"]["protected_entries"] != expected_global_protection:
            fail("B04_PREVIEW_PROTECTION_INVALID", "global complement")
        group_previews: list[dict[str, Any]] = []
        for group in patch_payload["atomic_groups"]:
            if group["atomic_group_id"] not in selected:
                continue
            group_protected_summaries = [
                {
                    "json_pointer": entry["json_pointer"],
                    "protected_item_hash": entry["protected_item_hash"],
                    "reason": entry["reason"],
                }
                for entry in expected_protected_entries(context=context, groups=[group])
            ]
            changes: list[dict[str, Any]] = []
            diagnostic_refs: list[dict[str, Any]] = []
            coverage_refs: list[dict[str, Any]] = []
            for operation in group["operations"]:
                kind = operation["operation_kind"]
                if kind == "REPLACE_CANDIDATE_ITEM":
                    pointer = operation["target"]["json_pointer"]
                    old_item = _item_at(context, pointer)
                    changes.append(
                        {
                            "operation_kind": kind,
                            "target_json_pointer": pointer,
                            "old_item_hash": operation["expected_old_item_hash"],
                            "old_item_summary": _item_summary(old_item),
                            "new_item_summary": _item_summary(operation["new_item"]),
                        }
                    )
                    diagnostic_refs.extend(operation["supporting_diagnostic_refs"])
                    coverage_refs.extend(operation["supporting_coverage_refs"])
                elif kind == "ADD_CANDIDATE_ITEM":
                    changes.append(
                        {
                            "operation_kind": kind,
                            "target_json_pointer": "/items/-",
                            "old_item_hash": None,
                            "old_item_summary": None,
                            "new_item_summary": _item_summary(operation["new_item"]),
                        }
                    )
                    coverage_refs.extend(operation["supporting_coverage_refs"])
                else:
                    fail("B04_PREVIEW_OPERATION_INVALID", str(kind))
            stable_diagnostics = sorted(
                {
                    canonical_bytes(ref): deepcopy(ref) for ref in diagnostic_refs
                }.values(),
                key=canonical_bytes,
            )
            stable_coverages = sorted(
                {canonical_bytes(ref): deepcopy(ref) for ref in coverage_refs}.values(),
                key=canonical_bytes,
            )
            group_previews.append(
                {
                    "atomic_group_id": group["atomic_group_id"],
                    "purpose": group["purpose"],
                    "proposed_changes": changes,
                    "supporting_diagnostic_refs": stable_diagnostics,
                    "supporting_coverage_refs": stable_coverages,
                    "authorized_source_slice_refs": deepcopy(
                        patch_payload["authorized_source_slice_refs"]
                    ),
                    "protected_item_summaries": group_protected_summaries,
                }
            )
        causal_by_ref = {
            canonical_bytes(record_ref(item)): item for item in causal_records
        }
        ordered_causal: list[dict[str, Any]] = []
        sidecars: list[dict[str, Any]] = []
        for ref in patch_payload["sidecar_proposal_refs"]:
            proposal = causal_by_ref.get(canonical_bytes(ref))
            if proposal is None:
                fail("B04_PREVIEW_SIDECAR_MISSING")
            for locator in proposal["payload"]["evidence_locators"]:
                validate_evidence_locator(locator, context=context)
            ordered_causal.append(deepcopy(ref))
            sidecars.append(
                {
                    "proposal_ref": deepcopy(ref),
                    "display_summary": _causal_display(
                        context=context, proposal=proposal
                    ),
                    "committable": False,
                }
            )
        preview = {
            "view_type": "DERIVED_RECOMPUTABLE",
            "projector": PROJECTOR_MAP["PatchPreview"],
            "base_candidate_version_ref": record_ref(context["candidate_version"]),
            "protection_set_ref": record_ref(protection),
            "patch_ref": record_ref(patch),
            "diagnostic_refs": deepcopy(patch_payload["diagnostic_refs"]),
            "coverage_observation_refs": deepcopy(
                patch_payload["coverage_observation_refs"]
            ),
            "authorized_source_slice_refs": deepcopy(
                patch_payload["authorized_source_slice_refs"]
            ),
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
    if not preview["atomic_group_previews"]:
        fail("B04_PREVIEW_GROUP_SELECTION_INVALID")
    for group in preview["atomic_group_previews"]:
        exact_keys(group, GROUP_PREVIEW_KEYS, "B04_PREVIEW_GROUP_INVALID")
        for change in group["proposed_changes"]:
            exact_keys(change, CHANGE_KEYS, "B04_PREVIEW_CHANGE_INVALID")
            if change["old_item_summary"] is not None:
                exact_keys(
                    change["old_item_summary"],
                    ITEM_SUMMARY_KEYS,
                    "B04_PREVIEW_ITEM_SUMMARY_INVALID",
                )
            exact_keys(
                change["new_item_summary"],
                ITEM_SUMMARY_KEYS,
                "B04_PREVIEW_ITEM_SUMMARY_INVALID",
            )
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
