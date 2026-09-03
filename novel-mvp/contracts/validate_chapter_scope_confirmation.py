"""Validate CHAPTER_SCOPE_CONFIRMATION v1 structural boundaries."""

from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "CHAPTER_SCOPE_CONFIRMATION.schema.json"
FIXTURE_PATH = DIR / "CHAPTER_SCOPE_CONFIRMATION.fixtures.jsonl"

STRUCTURAL_VALID = "STRUCTURAL_VALID"
STRUCTURAL_INVALID = "STRUCTURAL_INVALID"

TRANSITION_INTENTS = (
    "CONTINUE_CURRENT",
    "SWITCH_HARD_CUT",
    "SWITCH_SUSTAINED_BRANCH",
    "SWITCH_MAINLINE_BRIDGE",
)
STOP_REASONS = {
    "NO_CANDIDATE",
    "CANDIDATE_CONFLICT",
    "AUTHORIZATION_INVALID",
    "FOCUS_MISMATCH",
    "SOURCE_ADVANCED",
    "SCOPE_MISMATCH",
    "SOURCE_DAMAGED",
    "UNAUTHORIZED",
}
FORBIDDEN_CONTENT_KEYS = {
    "body",
    "chapter_text",
    "database_table",
    "file_path",
    "name",
    "path",
    "quote",
    "sql",
    "summary",
    "table_name",
    "text",
}
RECIPE_KEYS = {"base", "case_id", "expected_result", "mutation"}


class ContractError(ValueError):
    """A chapter scope confirmation structural invariant failed."""


def _load_schema() -> dict[str, Any]:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


SCHEMA = _load_schema()
VALIDATOR = Draft202012Validator(SCHEMA)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def scope_basis_sha256(document: dict[str, Any]) -> str:
    payload = copy.deepcopy(document)
    payload.pop("scope_basis_sha256", None)
    payload.pop("ccz139_handoff", None)
    return sha256_json(payload)


def _handoff_for(document: dict[str, Any]) -> dict[str, Any]:
    selection = document["selection"]
    confirmation = document["confirmation"]
    basis = document["chapter_slot_basis"]
    assert selection is not None and confirmation is not None
    permission = confirmation["permission_snapshot_ref"]
    focus = confirmation["effective_focus_ref"]
    return {
        "target": "CCZ-139",
        "scope_id": document["scope_id"],
        "selected_storyline_ref": selection["selected_storyline_ref"],
        "transition_intent": selection["transition_intent"],
        "viewpoint_character_ref": selection["viewpoint_character_ref"],
        "appearance_character_refs": selection["appearance_character_refs"],
        "permission_snapshot_sha256": permission["snapshot_sha256"],
        "effective_focus_sha256": focus["focus_sha256"],
        "source_plan_version": basis["source_plan_version"],
        "source_plan_sha256": basis["source_plan_sha256"],
        "slot_ref": basis["slot_ref"],
        "slot_rev": basis["slot_rev"],
        "scope_basis_sha256": document["scope_basis_sha256"],
    }


def seal_document(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result["scope_basis_sha256"] = scope_basis_sha256(result)
    result["ccz139_handoff"] = (
        _handoff_for(result) if result["status"] == "CONFIRMED" else None
    )
    return result


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _validate_schema(document: Any) -> None:
    errors = sorted(
        VALIDATOR.iter_errors(document),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        raise ContractError(
            f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}"
        )


def _walk_forbidden_content(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_CONTENT_KEYS:
                raise ContractError(
                    f"PROTECTED_CONTENT_KEY_FORBIDDEN:{path}.{key}"
                )
            _walk_forbidden_content(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_forbidden_content(item, f"{path}[{index}]")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_scope_and_watermarks(document: dict[str, Any]) -> None:
    scope = document["truth_scope_ref"]
    basis = document["chapter_slot_basis"]
    task = document["task_ref"]
    if basis["project_id"] != scope["project_id"]:
        raise ContractError("CHAPTER_BASIS_PROJECT_SCOPE_MISMATCH")
    if task["project_id"] != scope["project_id"]:
        raise ContractError("TASK_PROJECT_SCOPE_MISMATCH")
    if task["slot_ref"] != basis["slot_ref"]:
        raise ContractError("TASK_SLOT_SCOPE_MISMATCH")
    if task["expected_source_plan_version"] != basis["source_plan_version"]:
        raise ContractError("TASK_SOURCE_PLAN_VERSION_MISMATCH")
    if task["expected_source_plan_sha256"] != basis["source_plan_sha256"]:
        raise ContractError("TASK_SOURCE_PLAN_SHA256_MISMATCH")
    if task["expected_slot_rev"] != basis["slot_rev"]:
        raise ContractError("TASK_SLOT_REV_MISMATCH")


def _candidate_maps(
    document: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    basis = document["chapter_slot_basis"]
    candidates = document["candidate_basis"]
    all_rows = (
        candidates["storyline_candidates"]
        + candidates["character_candidates"]
    )
    basis_refs = [row["basis_ref"] for row in all_rows]
    if len(basis_refs) != len(set(basis_refs)):
        raise ContractError("CANDIDATE_BASIS_REF_DUPLICATE")
    for row in all_rows:
        if row["source_plan_version"] != basis["source_plan_version"]:
            raise ContractError("CANDIDATE_SOURCE_PLAN_VERSION_MISMATCH")
        if row["source_plan_sha256"] != basis["source_plan_sha256"]:
            raise ContractError("CANDIDATE_SOURCE_PLAN_SHA256_MISMATCH")

    storylines = {
        row["object_ref"]: row for row in candidates["storyline_candidates"]
    }
    characters = {
        row["object_ref"]: row for row in candidates["character_candidates"]
    }
    if len(storylines) != len(candidates["storyline_candidates"]):
        raise ContractError("STORYLINE_CANDIDATE_DUPLICATE")
    if len(characters) != len(candidates["character_candidates"]):
        raise ContractError("CHARACTER_CANDIDATE_DUPLICATE")
    return storylines, characters


def _selected_refs(selection: dict[str, Any]) -> list[str]:
    return [
        selection["selected_storyline_ref"],
        selection["viewpoint_character_ref"],
        *selection["appearance_character_refs"],
    ]


def _validate_selection(
    selection: dict[str, Any],
    storylines: dict[str, dict[str, Any]],
    characters: dict[str, dict[str, Any]],
) -> None:
    storyline_ref = selection["selected_storyline_ref"]
    viewpoint_ref = selection["viewpoint_character_ref"]
    appearance_refs = selection["appearance_character_refs"]
    if storyline_ref not in storylines:
        raise ContractError("SELECTED_STORYLINE_NOT_IN_CURRENT_CANDIDATES")
    if viewpoint_ref not in characters:
        raise ContractError("VIEWPOINT_CHARACTER_NOT_IN_CURRENT_CANDIDATES")
    if viewpoint_ref not in appearance_refs:
        raise ContractError("VIEWPOINT_CHARACTER_MUST_APPEAR")
    missing = [ref for ref in appearance_refs if ref not in characters]
    if missing:
        raise ContractError("APPEARANCE_CHARACTER_NOT_IN_CURRENT_CANDIDATES")

    expected_basis_refs = [
        storylines[storyline_ref]["basis_ref"],
        characters[viewpoint_ref]["basis_ref"],
    ]
    expected_basis_refs.extend(
        characters[ref]["basis_ref"]
        for ref in appearance_refs
        if ref != viewpoint_ref
    )
    if selection["selected_basis_refs"] != expected_basis_refs:
        raise ContractError("SELECTED_BASIS_REFS_MISMATCH")


def _validate_confirmation(
    document: dict[str, Any], selection: dict[str, Any]
) -> None:
    confirmation = document["confirmation"]
    assert confirmation is not None
    scope = document["truth_scope_ref"]
    basis = document["chapter_slot_basis"]
    permission = confirmation["permission_snapshot_ref"]
    focus = confirmation["effective_focus_ref"]

    if permission["principal_author_id"] != scope["principal_author_id"]:
        raise ContractError("PERMISSION_AUTHOR_SCOPE_MISMATCH")
    if permission["project_id"] != scope["project_id"]:
        raise ContractError("PERMISSION_PROJECT_SCOPE_MISMATCH")
    if permission["slot_ref"] != basis["slot_ref"]:
        raise ContractError("PERMISSION_SLOT_SCOPE_MISMATCH")
    if focus["project_id"] != scope["project_id"]:
        raise ContractError("FOCUS_PROJECT_SCOPE_MISMATCH")
    if focus["slot_ref"] != basis["slot_ref"]:
        raise ContractError("FOCUS_SLOT_SCOPE_MISMATCH")
    if (
        confirmation["permission_revocation_version"]
        != permission["revocation_version"]
    ):
        raise ContractError("PERMISSION_REVOCATION_VERSION_MISMATCH")

    actor_id = confirmation["actor_id"]
    if confirmation["mode"] == "AUTHOR_CONFIRMED":
        if actor_id != scope["principal_author_id"]:
            raise ContractError("AUTHOR_CONFIRMATION_ACTOR_MISMATCH")
        if permission["delegate_actor_id"] is not None:
            raise ContractError("AUTHOR_CONFIRMATION_CANNOT_USE_DELEGATE")
    else:
        delegate_id = permission["delegate_actor_id"]
        if delegate_id is None or actor_id != delegate_id:
            raise ContractError("DELEGATED_CONFIRMATION_ACTOR_MISMATCH")
        if actor_id == scope["principal_author_id"]:
            raise ContractError("DELEGATED_CONFIRMATION_MUST_USE_DELEGATE")

    required_scope_refs = set(_selected_refs(selection))
    if not required_scope_refs.issubset(permission["allowed_scope_refs"]):
        raise ContractError("PERMISSION_SELECTION_SCOPE_NOT_COVERED")

    confirmed_at = _parse_time(confirmation["confirmed_at"])
    if confirmed_at > _parse_time(permission["valid_until"]):
        raise ContractError("PERMISSION_EXPIRED_AT_CONFIRMATION")
    if confirmed_at > _parse_time(focus["valid_until"]):
        raise ContractError("FOCUS_EXPIRED_AT_CONFIRMATION")
    if permission["revoked_at"] is not None:
        revoked_at = _parse_time(permission["revoked_at"])
        if revoked_at <= confirmed_at:
            raise ContractError("PERMISSION_REVOKED_AT_CONFIRMATION")


def _validate_status_shape(document: dict[str, Any]) -> None:
    status = document["status"]
    reason = document["reason_code"]
    selection = document["selection"]
    confirmation = document["confirmation"]
    handoff = document["ccz139_handoff"]
    superseded_by = document["superseded_by_scope_id"]
    revoked_at = document["revoked_at"]

    if status == "CONFIRMED":
        if reason is not None or selection is None or confirmation is None:
            raise ContractError("CONFIRMED_SHAPE_INVALID")
        if handoff is None or superseded_by is not None or revoked_at is not None:
            raise ContractError("CONFIRMED_CONSUMER_STATE_INVALID")
        if confirmation["permission_snapshot_ref"]["revoked_at"] is not None:
            raise ContractError("CONFIRMED_PERMISSION_ALREADY_REVOKED")
    elif status == "AWAITING_AUTHOR":
        if (
            reason != "AUTHORIZATION_REQUIRED"
            or selection is not None
            or confirmation is not None
            or handoff is not None
            or document["supersedes_scope_id"] is not None
            or superseded_by is not None
            or revoked_at is not None
        ):
            raise ContractError("AWAITING_AUTHOR_SHAPE_INVALID")
    elif status == "STOPPED":
        if (
            reason not in STOP_REASONS
            or selection is not None
            or confirmation is not None
            or handoff is not None
            or document["supersedes_scope_id"] is not None
            or superseded_by is not None
            or revoked_at is not None
        ):
            raise ContractError("STOPPED_SHAPE_INVALID")
        candidates = document["candidate_basis"]
        if reason == "UNAUTHORIZED" and (
            candidates["storyline_candidates"]
            or candidates["character_candidates"]
        ):
            raise ContractError("UNAUTHORIZED_STOP_LEAKS_CANDIDATES")
    elif status == "SUPERSEDED":
        if (
            reason != "SUPERSEDED_BY_NEW_SCOPE"
            or selection is None
            or confirmation is None
            or handoff is not None
            or superseded_by is None
            or revoked_at is not None
        ):
            raise ContractError("SUPERSEDED_SHAPE_INVALID")
    else:
        if (
            reason not in {"AUTHOR_REVOKED", "PERMISSION_REVOKED"}
            or selection is None
            or confirmation is None
            or handoff is not None
            or superseded_by is not None
            or revoked_at is None
        ):
            raise ContractError("REVOKED_SHAPE_INVALID")
        confirmed_at = _parse_time(confirmation["confirmed_at"])
        if _parse_time(revoked_at) <= confirmed_at:
            raise ContractError("REVOCATION_TIME_INVALID")
        permission_revoked = confirmation["permission_snapshot_ref"]["revoked_at"]
        if reason == "PERMISSION_REVOKED" and permission_revoked != revoked_at:
            raise ContractError("PERMISSION_REVOCATION_RECEIPT_MISMATCH")
        if reason == "AUTHOR_REVOKED" and permission_revoked is not None:
            raise ContractError("AUTHOR_REVOCATION_CANNOT_REWRITE_PERMISSION")


def _validate_lineage(document: dict[str, Any]) -> None:
    scope_id = document["scope_id"]
    for key in ("supersedes_scope_id", "superseded_by_scope_id"):
        if document[key] == scope_id:
            raise ContractError(f"SELF_REFERENCE_FORBIDDEN:{key}")


def validate_scope_confirmation(document: Any) -> str:
    """Validate one confirmation without owner, current, network or model access."""

    _validate_schema(document)
    _walk_forbidden_content(document)
    _validate_scope_and_watermarks(document)
    storylines, characters = _candidate_maps(document)
    if document["selection"] is not None:
        _validate_selection(document["selection"], storylines, characters)
    if document["confirmation"] is not None:
        if document["selection"] is None:
            raise ContractError("CONFIRMATION_WITHOUT_SELECTION")
        _validate_confirmation(document, document["selection"])
    _validate_status_shape(document)
    _validate_lineage(document)
    if document["scope_basis_sha256"] != scope_basis_sha256(document):
        raise ContractError("SCOPE_BASIS_SHA256_MISMATCH")
    if document["status"] == "CONFIRMED":
        if document["ccz139_handoff"] != _handoff_for(document):
            raise ContractError("CCZ139_HANDOFF_PROJECTION_MISMATCH")
    elif document["ccz139_handoff"] is not None:
        raise ContractError("NON_CONFIRMED_HANDOFF_FORBIDDEN")
    return STRUCTURAL_VALID


def _candidate(
    basis_ref: str,
    object_ref: str,
    source_kind: str,
    source_plan_sha256: str,
) -> dict[str, Any]:
    return {
        "basis_ref": basis_ref,
        "object_ref": object_ref,
        "source_kind": source_kind,
        "source_plan_version": 7,
        "source_plan_sha256": source_plan_sha256,
        "source_object_revision": 2,
        "source_object_sha256": sha256_json(
            {"object_ref": object_ref, "revision": 2}
        ),
    }


def _confirmed_document(
    transition_intent: str = "CONTINUE_CURRENT",
    *,
    delegated: bool = False,
    second_storyline: bool = False,
    supersedes_scope_id: str | None = None,
) -> dict[str, Any]:
    plan_sha = sha256_json({"plan": "synthetic-current", "version": 7})
    storyline_ref = "LINE-0002" if second_storyline else "LINE-0001"
    viewpoint_ref = "CHAR-0002" if second_storyline else "CHAR-0001"
    appearances = (
        ["CHAR-0002", "CHAR-0003"]
        if second_storyline
        else ["CHAR-0001", "CHAR-0002"]
    )
    storylines = [
        _candidate(
            "BASIS-LINE-0001",
            "LINE-0001",
            "CHAPTER_SLOT_SNAPSHOT",
            plan_sha,
        ),
        _candidate(
            "BASIS-LINE-0002",
            "LINE-0002",
            "CURRENT_PLANNING_LONGLINE",
            plan_sha,
        ),
    ]
    characters = [
        _candidate(
            f"BASIS-CHAR-000{index}",
            f"CHAR-000{index}",
            "CHAPTER_SLOT_SNAPSHOT",
            plan_sha,
        )
        for index in range(1, 4)
    ]
    story_map = {row["object_ref"]: row for row in storylines}
    character_map = {row["object_ref"]: row for row in characters}
    selected_basis_refs = [
        story_map[storyline_ref]["basis_ref"],
        character_map[viewpoint_ref]["basis_ref"],
        *[
            character_map[ref]["basis_ref"]
            for ref in appearances
            if ref != viewpoint_ref
        ],
    ]
    author_id = "AUTHOR-0001"
    actor_id = "AGENT-0001" if delegated else author_id
    selection = {
        "selected_storyline_ref": storyline_ref,
        "transition_intent": transition_intent,
        "viewpoint_character_ref": viewpoint_ref,
        "appearance_character_refs": appearances,
        "selected_basis_refs": selected_basis_refs,
    }
    document = {
        "contract": "CHAPTER_SCOPE_CONFIRMATION",
        "version": "v1",
        "scope_id": "SCOPE-0002" if supersedes_scope_id else "SCOPE-0001",
        "truth_scope_ref": {
            "principal_author_id": author_id,
            "project_id": "PROJECT-0001",
        },
        "status": "CONFIRMED",
        "reason_code": None,
        "chapter_slot_basis": {
            "contract": "CHAPTER_SLOT_SNAPSHOT",
            "version": "v1",
            "project_id": "PROJECT-0001",
            "slot_ref": "SLOT-0001",
            "source_plan_version": 7,
            "source_plan_sha256": plan_sha,
            "slot_rev": 3,
            "snapshot_sha256": sha256_json({"slot": "SLOT-0001", "rev": 3}),
        },
        "task_ref": {
            "object_ref": "TASK-0001",
            "object_revision": 4,
            "object_sha256": sha256_json({"task": "TASK-0001", "rev": 4}),
            "project_id": "PROJECT-0001",
            "slot_ref": "SLOT-0001",
            "expected_source_plan_version": 7,
            "expected_source_plan_sha256": plan_sha,
            "expected_slot_rev": 3,
        },
        "candidate_basis": {
            "storyline_candidates": storylines,
            "character_candidates": characters,
        },
        "selection": selection,
        "confirmation": {
            "mode": (
                "DELEGATED_CONFIRMED" if delegated else "AUTHOR_CONFIRMED"
            ),
            "actor_id": actor_id,
            "confirmed_at": "2026-09-03T10:00:00+08:00",
            "permission_revocation_version": 0,
            "permission_snapshot_ref": {
                "contract": "PERMISSION_SNAPSHOT",
                "version": "v1",
                "snapshot_id": "PERMISSION-0001",
                "snapshot_revision": 5,
                "snapshot_sha256": sha256_json(
                    {"permission": "PERMISSION-0001", "revision": 5}
                ),
                "principal_author_id": author_id,
                "delegate_actor_id": "AGENT-0001" if delegated else None,
                "project_id": "PROJECT-0001",
                "slot_ref": "SLOT-0001",
                "allowed_action": "CONFIRM_CHAPTER_SCOPE",
                "allowed_phase": "CHAPTER_PREP",
                "allowed_scope_refs": list(
                    dict.fromkeys(_selected_refs(selection))
                ),
                "valid_until": "2099-12-31T23:59:59+08:00",
                "revoked_at": None,
                "revocation_version": 0,
            },
            "effective_focus_ref": {
                "focus_id": "FOCUS-0001",
                "focus_revision": 6,
                "focus_sha256": sha256_json(
                    {"focus": "FOCUS-0001", "revision": 6}
                ),
                "project_id": "PROJECT-0001",
                "slot_ref": "SLOT-0001",
                "phase": "CHAPTER_PREP",
                "valid_until": "2099-12-31T23:59:59+08:00",
            },
        },
        "supersedes_scope_id": supersedes_scope_id,
        "superseded_by_scope_id": None,
        "revoked_at": None,
        "ccz139_handoff": None,
        "scope_basis_sha256": "0" * 64,
    }
    return seal_document(document)


def _awaiting_document() -> dict[str, Any]:
    document = _confirmed_document()
    document.update(
        {
            "scope_id": "SCOPE-AWAITING-0001",
            "status": "AWAITING_AUTHOR",
            "reason_code": "AUTHORIZATION_REQUIRED",
            "selection": None,
            "confirmation": None,
            "supersedes_scope_id": None,
        }
    )
    return seal_document(document)


def _superseded_document() -> dict[str, Any]:
    document = _confirmed_document()
    document.update(
        {
            "status": "SUPERSEDED",
            "reason_code": "SUPERSEDED_BY_NEW_SCOPE",
            "superseded_by_scope_id": "SCOPE-0002",
        }
    )
    return seal_document(document)


def _revoked_document(*, permission: bool = False) -> dict[str, Any]:
    document = _confirmed_document()
    revoked_at = "2026-09-03T11:00:00+08:00"
    document.update(
        {
            "status": "REVOKED",
            "reason_code": "PERMISSION_REVOKED" if permission else "AUTHOR_REVOKED",
            "revoked_at": revoked_at,
        }
    )
    if permission:
        document["confirmation"]["permission_snapshot_ref"]["revoked_at"] = (
            revoked_at
        )
    return seal_document(document)


def _unauthorized_document() -> dict[str, Any]:
    document = _confirmed_document()
    document.update(
        {
            "scope_id": "SCOPE-STOPPED-0001",
            "status": "STOPPED",
            "reason_code": "UNAUTHORIZED",
            "candidate_basis": {
                "storyline_candidates": [],
                "character_candidates": [],
            },
            "selection": None,
            "confirmation": None,
            "supersedes_scope_id": None,
        }
    )
    return seal_document(document)


def build_base_document(base: str) -> dict[str, Any]:
    if base == "confirmed_continue":
        return _confirmed_document()
    if base == "confirmed_hard_cut":
        return _confirmed_document("SWITCH_HARD_CUT", second_storyline=True)
    if base == "confirmed_sustained_branch":
        return _confirmed_document(
            "SWITCH_SUSTAINED_BRANCH", second_storyline=True
        )
    if base == "confirmed_mainline_bridge":
        return _confirmed_document(
            "SWITCH_MAINLINE_BRIDGE", second_storyline=True
        )
    if base == "confirmed_delegated":
        return _confirmed_document(delegated=True)
    if base == "confirmed_supersedes":
        return _confirmed_document(
            "SWITCH_HARD_CUT",
            second_storyline=True,
            supersedes_scope_id="SCOPE-0001",
        )
    if base == "awaiting_author":
        return _awaiting_document()
    if base == "superseded":
        return _superseded_document()
    if base == "revoked_author":
        return _revoked_document()
    if base == "revoked_permission":
        return _revoked_document(permission=True)
    if base == "stopped_unauthorized":
        return _unauthorized_document()
    raise ContractError(f"FIXTURE_BASE_UNKNOWN:{base}")


def _reseal_after_mutation(document: dict[str, Any]) -> dict[str, Any]:
    return seal_document(document)


def apply_mutation(document: dict[str, Any], mutation: str) -> dict[str, Any]:
    if mutation == "none":
        return document
    if mutation == "storyline_not_candidate":
        document["selection"]["selected_storyline_ref"] = "LINE-9999"
    elif mutation == "natural_language_storyline":
        document["selection"]["selected_storyline_ref"] = "临时支线"
    elif mutation == "viewpoint_not_candidate":
        document["selection"]["viewpoint_character_ref"] = "CHAR-9999"
    elif mutation == "appearance_not_candidate":
        document["selection"]["appearance_character_refs"].append("CHAR-9999")
    elif mutation == "duplicate_appearance":
        document["selection"]["appearance_character_refs"].append("CHAR-0002")
    elif mutation == "task_project_mismatch":
        document["task_ref"]["project_id"] = "PROJECT-0002"
    elif mutation == "task_slot_mismatch":
        document["task_ref"]["slot_ref"] = "SLOT-0002"
    elif mutation == "task_plan_version_mismatch":
        document["task_ref"]["expected_source_plan_version"] = 8
    elif mutation == "task_plan_sha_mismatch":
        document["task_ref"]["expected_source_plan_sha256"] = "f" * 64
    elif mutation == "task_slot_rev_mismatch":
        document["task_ref"]["expected_slot_rev"] = 4
    elif mutation == "candidate_plan_sha_mismatch":
        document["candidate_basis"]["storyline_candidates"][0][
            "source_plan_sha256"
        ] = "f" * 64
    elif mutation == "delegated_actor_mismatch":
        document["confirmation"]["actor_id"] = "AGENT-9999"
    elif mutation == "permission_scope_missing":
        document["confirmation"]["permission_snapshot_ref"][
            "allowed_scope_refs"
        ] = [document["selection"]["selected_storyline_ref"]]
    elif mutation == "permission_revoked_before_confirm":
        document["confirmation"]["permission_snapshot_ref"]["revoked_at"] = (
            "2026-09-03T09:00:00+08:00"
        )
    elif mutation == "focus_wrong_slot":
        document["confirmation"]["effective_focus_ref"]["slot_ref"] = (
            "SLOT-0002"
        )
    elif mutation == "focus_expired":
        document["confirmation"]["effective_focus_ref"]["valid_until"] = (
            "2026-09-03T09:00:00+08:00"
        )
    elif mutation == "selected_basis_mismatch":
        document["selection"]["selected_basis_refs"] = ["BASIS-LINE-0001"]
    elif mutation == "superseded_without_successor":
        document["superseded_by_scope_id"] = None
    elif mutation == "unauthorized_candidate_leak":
        leaked = _confirmed_document()["candidate_basis"]
        document["candidate_basis"] = leaked
    elif mutation == "self_supersedes":
        document["supersedes_scope_id"] = document["scope_id"]
    elif mutation == "extra_field":
        document["runtime_effect"] = "write"
    elif mutation == "stale_scope_hash":
        document["task_ref"]["object_revision"] += 1
        return document
    elif mutation == "non_confirmed_handoff":
        document = _reseal_after_mutation(document)
        document["ccz139_handoff"] = _confirmed_document()["ccz139_handoff"]
        return document
    elif mutation == "handoff_projection_mismatch":
        document = _reseal_after_mutation(document)
        document["ccz139_handoff"]["selected_storyline_ref"] = "LINE-9999"
        return document
    elif mutation == "forbidden_natural_language_field":
        document["candidate_basis"]["storyline_candidates"][0]["name"] = (
            "synthetic storyline"
        )
    else:
        raise ContractError(f"FIXTURE_MUTATION_UNKNOWN:{mutation}")
    return _reseal_after_mutation(document)


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        if set(row) != RECIPE_KEYS:
            raise ContractError("FIXTURE_RECIPE_KEYS_INVALID")
    return rows


def materialize_fixture_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        **case,
        "document": apply_mutation(
            build_base_document(case["base"]), case["mutation"]
        ),
    }


def validate_fixture_case(case: dict[str, Any]) -> str:
    document = materialize_fixture_case(case)["document"]
    try:
        return validate_scope_confirmation(document)
    except ContractError:
        return STRUCTURAL_INVALID


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {STRUCTURAL_VALID: 0, STRUCTURAL_INVALID: 0}
    seen: set[str] = set()
    for case in load_fixtures(path):
        case_id = case["case_id"]
        if case_id in seen:
            raise ContractError(f"FIXTURE_CASE_ID_DUPLICATE:{case_id}")
        seen.add(case_id)
        actual = validate_fixture_case(case)
        if actual != case["expected_result"]:
            raise ContractError(
                f"FIXTURE_EXPECTATION_MISMATCH:{case_id}:{actual}"
            )
        counts[actual] += 1
    return counts


def main() -> int:
    counts = validate_all_fixtures()
    print(
        json.dumps(
            {
                "contract": "CHAPTER_SCOPE_CONFIRMATION",
                "version": "v1",
                "status": "PASS",
                "counts": counts,
                "current_owner_resolution_performed": False,
                "permission_evaluation_performed": False,
                "network_calls": 0,
                "model_calls": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
