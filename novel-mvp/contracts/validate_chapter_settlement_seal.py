"""Validate CHAPTER_SETTLEMENT_SEAL v1 structural boundaries."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "CHAPTER_SETTLEMENT_SEAL.schema.json"
FIXTURE_PATH = DIR / "CHAPTER_SETTLEMENT_SEAL.fixtures.jsonl"
TPS_VALIDATOR_PATH = DIR / "validate_traceable_provenance_seal.py"

STRUCTURAL_VALID = "STRUCTURAL_VALID"
STRUCTURAL_VALID_OWNER_UNRESOLVED = "STRUCTURAL_VALID_OWNER_UNRESOLVED"
STRUCTURAL_INVALID = "STRUCTURAL_INVALID"

LEDGER_NAMES = (
    "chapter",
    "fact",
    "character",
    "location",
    "item",
    "faction",
    "system",
    "world_rule",
    "longline",
    "planning",
)
FORBIDDEN_CONTENT_KEYS = {
    "body",
    "chapter_text",
    "database_table",
    "file_path",
    "path",
    "physical_path",
    "quote",
    "sql",
    "table_name",
    "text",
}
RECIPE_KEYS = {"base", "case_id", "expected_result", "mutation"}


class ContractError(ValueError):
    """A chapter settlement structural invariant failed."""


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODULE_LOAD_FAILED:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tps = _load_module(TPS_VALIDATOR_PATH, "chapter_settlement_tps")


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


def settlement_sha256(document: dict[str, Any]) -> str:
    payload = copy.deepcopy(document)
    payload.pop("settlement_sha256", None)
    return sha256_json(payload)


def seal_document(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result["settlement_sha256"] = settlement_sha256(result)
    return result


def closeout_action_sha256(action: dict[str, Any]) -> str:
    payload = copy.deepcopy(action)
    payload.pop("action_sha256", None)
    return sha256_json(payload)


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


def _validate_closeout(document: dict[str, Any]) -> None:
    action = document["closeout_input"]
    if action["slot_ref"] != document["slot_ref"]:
        raise ContractError("CLOSEOUT_SLOT_MISMATCH")
    if action["action_sha256"] != closeout_action_sha256(action):
        raise ContractError("CLOSEOUT_ACTION_SHA256_MISMATCH")
    route = action["route"]
    if route == "full_check":
        if (
            action["work_ref"] is None
            or action["work_rev"] is None
            or action["check_result_ref"] is None
        ):
            raise ContractError("FULL_CHECK_INPUT_INCOMPLETE")
    elif route == "skip_check":
        if (
            action["work_ref"] is None
            or action["work_rev"] is None
            or action["check_result_ref"] is not None
        ):
            raise ContractError("SKIP_CHECK_INPUT_INVALID")
    elif any(
        action[key] is not None
        for key in ("work_ref", "work_rev", "check_result_ref")
    ):
        raise ContractError("NO_PROSE_INPUT_MUST_BE_EMPTY")


def _validate_provenance(
    document: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], bool]:
    scope = document["truth_scope_ref"]
    seals: dict[str, dict[str, Any]] = {}
    owner_unresolved = False
    for raw in document["provenance_seals"]:
        try:
            result = tps.validate_seal(raw)
        except tps.ContractError as exc:
            raise ContractError(f"PROVENANCE_SEAL_INVALID:{exc}") from exc
        seal_sha = raw["seal_sha256"]
        if seal_sha in seals:
            raise ContractError("PROVENANCE_SEAL_DUPLICATE")
        if raw["truth_scope_ref"] != scope:
            raise ContractError("TRUTH_SCOPE_MISMATCH")
        seals[seal_sha] = raw
        owner_unresolved |= (
            result == tps.STRUCTURAL_VALID_OWNER_UNRESOLVED
        )
    return seals, owner_unresolved


def _add_refs(
    used: set[str],
    refs: list[str],
    seals: dict[str, dict[str, Any]],
    *,
    label: str,
) -> None:
    for ref in refs:
        if ref not in seals:
            raise ContractError(f"PROVENANCE_REF_NOT_FOUND:{label}:{ref}")
        used.add(ref)


def _statement_refs(document: dict[str, Any]) -> list[tuple[str, list[str]]]:
    values: list[tuple[str, list[str]]] = [
        (
            "planning.original_target",
            document["planning"]["original_target"]["provenance_seal_refs"],
        )
    ]
    for key in (
        "actual_completion",
        "key_plot_skeleton",
        "important_state_changes",
    ):
        values.extend(
            (f"outcome.{key}.{row['statement_id']}", row["provenance_seal_refs"])
            for row in document["outcome"][key]
        )
    values.extend(
        (
            f"unresolved_story_items.{row['item_id']}",
            row["provenance_seal_refs"],
        )
        for row in document["unresolved_story_items"]
    )
    values.append(
        (
            "next_chapter_handoff",
            document["next_chapter_handoff"]["provenance_seal_refs"],
        )
    )
    return values


def _validate_all_refs(
    document: dict[str, Any], seals: dict[str, dict[str, Any]]
) -> None:
    used: set[str] = set()
    _add_refs(
        used,
        document["manuscript"]["provenance_seal_refs"],
        seals,
        label="manuscript",
    )
    for index, row in enumerate(document["planning"]["adopted_path_refs"]):
        _add_refs(
            used,
            row["provenance_seal_refs"],
            seals,
            label=f"planning.adopted_path_refs.{index}",
        )
    for label, refs in _statement_refs(document):
        _add_refs(used, refs, seals, label=label)
    for row in document["ledger_coverage"]:
        _add_refs(
            used,
            row["provenance_seal_refs"],
            seals,
            label=f"ledger_coverage.{row['ledger_name']}",
        )
    if used != set(seals):
        raise ContractError("PROVENANCE_SEAL_UNUSED")


def _validate_manuscript(document: dict[str, Any]) -> None:
    route = document["closeout_input"]["route"]
    manuscript = document["manuscript"]
    disposition = manuscript["disposition"]
    if route == "no_prose":
        if (
            disposition != "NO_PROSE"
            or manuscript["chapter_revision_ref"] is not None
            or manuscript["handover_receipt_ref"] is not None
            or manuscript["written_progress_delta"] != 0
            or manuscript["provenance_seal_refs"]
        ):
            raise ContractError("NO_PROSE_MANUSCRIPT_EFFECT_FORBIDDEN")
        if document["outcome"]["target_disposition"] != "PLANNING_ONLY":
            raise ContractError("NO_PROSE_TARGET_MUST_BE_PLANNING_ONLY")
        return
    if disposition == "NO_PROSE":
        raise ContractError("WORK_ROUTE_CANNOT_USE_NO_PROSE_DISPOSITION")
    if disposition == "ADOPTED_C11":
        if (
            manuscript["chapter_revision_ref"] is None
            or manuscript["handover_receipt_ref"] is None
            or manuscript["written_progress_delta"] != 1
            or not manuscript["provenance_seal_refs"]
        ):
            raise ContractError("ADOPTED_C11_EVIDENCE_INCOMPLETE")
    elif (
        manuscript["chapter_revision_ref"] is not None
        or manuscript["handover_receipt_ref"] is not None
        or manuscript["written_progress_delta"] != 0
        or manuscript["provenance_seal_refs"]
    ):
        raise ContractError("NOT_ADOPTED_MUST_HAVE_ZERO_MANUSCRIPT_EFFECT")


def _validate_outcome(document: dict[str, Any]) -> None:
    outcome = document["outcome"]
    if outcome["target_disposition"] == "REMAPPED":
        if outcome["target_destination_ref"] is None:
            raise ContractError("REMAPPED_TARGET_DESTINATION_REQUIRED")
    elif outcome["target_destination_ref"] is not None:
        raise ContractError("TARGET_DESTINATION_ONLY_FOR_REMAPPED")

    statement_ids = [document["planning"]["original_target"]["statement_id"]]
    for key in (
        "actual_completion",
        "key_plot_skeleton",
        "important_state_changes",
    ):
        statement_ids.extend(row["statement_id"] for row in outcome[key])
    if len(statement_ids) != len(set(statement_ids)):
        raise ContractError("STATEMENT_ID_DUPLICATE")


def _validate_ledger_coverage(
    document: dict[str, Any], seals: dict[str, dict[str, Any]]
) -> bool:
    rows = document["ledger_coverage"]
    if tuple(row["ledger_name"] for row in rows) != LEDGER_NAMES:
        raise ContractError("TEN_LEDGER_COVERAGE_ORDER_OR_MEMBERSHIP_INVALID")
    owner_unresolved = False
    for row in rows:
        result = row["result"]
        before_sha = row["before_snapshot_sha256"]
        after_sha = row["after_snapshot_sha256"]
        unresolved_ref = row["unresolved_owner_ref"]
        referenced = [seals[ref] for ref in row["provenance_seal_refs"]]
        if result == "COMMITTED_CHANGE":
            if after_sha is None or before_sha == after_sha or unresolved_ref is not None:
                raise ContractError(
                    f"COMMITTED_CHANGE_EVIDENCE_INVALID:{row['ledger_name']}"
                )
            if not any(
                seal["claim_kind"] == "OWNER_COMMIT_CLAIM"
                for seal in referenced
            ):
                raise ContractError(
                    f"COMMITTED_CHANGE_OWNER_RECEIPT_REQUIRED:{row['ledger_name']}"
                )
        elif result == "CONFIRMED_NO_CHANGE":
            if (
                before_sha is None
                or before_sha != after_sha
                or unresolved_ref is not None
            ):
                raise ContractError(
                    f"NO_CHANGE_WATERMARK_INVALID:{row['ledger_name']}"
                )
        else:
            owner_unresolved = True
            if before_sha is not None or after_sha is not None or unresolved_ref is None:
                raise ContractError(
                    f"OWNER_UNRESOLVED_LEDGER_SHAPE_INVALID:{row['ledger_name']}"
                )
            if not any(
                seal["claim_kind"] == "OWNER_UNRESOLVED_CLAIM"
                for seal in referenced
            ):
                raise ContractError(
                    f"OWNER_UNRESOLVED_SEAL_REQUIRED:{row['ledger_name']}"
                )
    return owner_unresolved


def validate_settlement(document: Any) -> str:
    """Validate one settlement document without owner, network, or model access."""

    _validate_schema(document)
    _walk_forbidden_content(document)
    _validate_closeout(document)
    seals, provenance_unresolved = _validate_provenance(document)
    _validate_all_refs(document, seals)
    _validate_manuscript(document)
    _validate_outcome(document)
    ledger_unresolved = _validate_ledger_coverage(document, seals)
    owner_unresolved = provenance_unresolved or ledger_unresolved
    if owner_unresolved:
        if document["claim_kind"] != "OWNER_UNRESOLVED_CANDIDATE":
            raise ContractError("OWNER_UNRESOLVED_CANNOT_CLAIM_SEALED")
        result = STRUCTURAL_VALID_OWNER_UNRESOLVED
    else:
        if document["claim_kind"] != "OWNER_RESOLVED_SEALED":
            raise ContractError("OWNER_RESOLVED_CLAIM_KIND_MISMATCH")
        result = STRUCTURAL_VALID
    if document["settlement_sha256"] != settlement_sha256(document):
        raise ContractError("SETTLEMENT_SHA256_MISMATCH")
    return result


def _tps_fixture(case_id: str) -> dict[str, Any]:
    return copy.deepcopy(
        next(
            row["document"]
            for row in tps.load_fixtures()
            if row["case_id"] == case_id
        )
    )


def _statement(
    statement_id: str, summary: str, seal_refs: list[str]
) -> dict[str, Any]:
    return {
        "statement_id": statement_id,
        "summary": summary,
        "provenance_seal_refs": seal_refs,
    }


def _closeout(route: str) -> dict[str, Any]:
    action: dict[str, Any] = {
        "contract": "WRITING_DESK_CLOSEOUT_ACTION",
        "version": "v1",
        "operation_id": f"op-closeout-{route.replace('_', '-')}",
        "actor": "author",
        "slot_ref": "S-0001",
        "route": route,
        "work_ref": None if route == "no_prose" else "S-0001@work",
        "work_rev": None if route == "no_prose" else 2,
        "check_result_ref": "check-current-r2" if route == "full_check" else None,
    }
    action["action_sha256"] = closeout_action_sha256(action)
    return action


def _ledger_rows(valid_seal_sha: str) -> list[dict[str, Any]]:
    rows = []
    for ledger_name in LEDGER_NAMES:
        watermark = sha256_json(
            {"ledger_name": ledger_name, "synthetic_state": "unchanged"}
        )
        rows.append(
            {
                "ledger_name": ledger_name,
                "result": "CONFIRMED_NO_CHANGE",
                "before_snapshot_sha256": watermark,
                "after_snapshot_sha256": watermark,
                "provenance_seal_refs": [valid_seal_sha],
                "unresolved_owner_ref": None,
            }
        )
    return rows


def _resolved_document(route: str) -> dict[str, Any]:
    valid_seal = _tps_fixture("TPS-VALID-01")
    valid_sha = valid_seal["seal_sha256"]
    scope = copy.deepcopy(valid_seal["truth_scope_ref"])
    chapter_ref = copy.deepcopy(valid_seal["subject_ref"]["owner_ref"])
    chapter_ref.pop("kind")
    if route == "full_check":
        manuscript = {
            "disposition": "ADOPTED_C11",
            "chapter_revision_ref": chapter_ref,
            "handover_receipt_ref": {
                "operation_id": "op-handover-current",
                "receipt_sha256": sha256_json({"handover": "current"}),
            },
            "written_progress_delta": 1,
            "provenance_seal_refs": [valid_sha],
        }
        target_disposition = "COMPLETED"
        state_changes = [
            _statement("ST-0004", "合成人物状态已经改变。", [valid_sha])
        ]
        handoff_mode = "CONTINUE_SCOPE"
        handoff_scopes = ["storyline:L-0001", "sandbox:SB-0001"]
    elif route == "skip_check":
        manuscript = {
            "disposition": "NOT_ADOPTED",
            "chapter_revision_ref": None,
            "handover_receipt_ref": None,
            "written_progress_delta": 0,
            "provenance_seal_refs": [],
        }
        target_disposition = "PARTIAL"
        state_changes = []
        handoff_mode = "UNDECIDED"
        handoff_scopes = []
    else:
        manuscript = {
            "disposition": "NO_PROSE",
            "chapter_revision_ref": None,
            "handover_receipt_ref": None,
            "written_progress_delta": 0,
            "provenance_seal_refs": [],
        }
        target_disposition = "PLANNING_ONLY"
        state_changes = []
        handoff_mode = "UNDECIDED"
        handoff_scopes = []
    document = {
        "contract": "CHAPTER_SETTLEMENT_SEAL",
        "version": "v1",
        "truth_scope_ref": scope,
        "claim_kind": "OWNER_RESOLVED_SEALED",
        "slot_ref": "S-0001",
        "settled_at": "2026-09-03T03:00:00+08:00",
        "closeout_input": _closeout(route),
        "manuscript": manuscript,
        "planning": {
            "chapter_slot_snapshot_sha256": sha256_json(
                {"slot": "S-0001", "rev": 3}
            ),
            "source_plan_version": 7,
            "source_plan_sha256": sha256_json({"plan": 7}),
            "adopted_path_refs": [
                {
                    "object_ref": "work-card:WC-0001",
                    "revision": 2,
                    "object_sha256": sha256_json({"work_card": 2}),
                    "provenance_seal_refs": [valid_sha],
                }
            ],
            "original_target": _statement(
                "ST-0001", "完成合成章节目标。", [valid_sha]
            ),
        },
        "outcome": {
            "target_disposition": target_disposition,
            "target_destination_ref": None,
            "actual_completion": [
                _statement("ST-0002", "完成合成章节的当前处理。", [valid_sha])
            ],
            "key_plot_skeleton": [
                _statement("ST-0003", "合成剧情骨架保持可追溯。", [valid_sha])
            ],
            "important_state_changes": state_changes,
        },
        "ledger_coverage": _ledger_rows(valid_sha),
        "unresolved_story_items": [
            {
                "item_id": "USI-0001",
                "kind": "HOOK",
                "status": "OPEN",
                "summary": "合成悬念仍留给下一章。",
                "provenance_seal_refs": [valid_sha],
            }
        ],
        "next_chapter_handoff": {
            "mode": handoff_mode,
            "scope_refs": handoff_scopes,
            "summary": "下一章只读取已固定的合成范围。",
            "provenance_seal_refs": [valid_sha],
        },
        "provenance_seals": [valid_seal],
    }
    return seal_document(document)


def _unresolved_document() -> dict[str, Any]:
    document = _resolved_document("full_check")
    unresolved_seal = _tps_fixture("TPS-UNRESOLVED-01")
    unresolved_sha = unresolved_seal["seal_sha256"]
    document["provenance_seals"].append(unresolved_seal)
    row = next(
        item for item in document["ledger_coverage"]
        if item["ledger_name"] == "fact"
    )
    row.update(
        {
            "result": "OWNER_UNRESOLVED",
            "before_snapshot_sha256": None,
            "after_snapshot_sha256": None,
            "provenance_seal_refs": [unresolved_sha],
            "unresolved_owner_ref": {
                "expected_owner_contract": "CCZ82_FORMAL_FACT_OWNER",
                "missing_identity_semantics": [
                    "stable_fact_revision",
                    "same_generation_receipt",
                ],
                "tracking_ref": "CCZ-82",
                "reason_code": "OWNER_UNRESOLVED",
            },
        }
    )
    document["claim_kind"] = "OWNER_UNRESOLVED_CANDIDATE"
    return seal_document(document)


def build_base_document(base: str) -> dict[str, Any]:
    if base == "resolved_full":
        return _resolved_document("full_check")
    if base == "resolved_skip":
        return _resolved_document("skip_check")
    if base == "resolved_no_prose":
        return _resolved_document("no_prose")
    if base == "unresolved_fact":
        return _unresolved_document()
    raise ContractError(f"FIXTURE_BASE_UNKNOWN:{base}")


def _move_unresolved(document: dict[str, Any], target: str) -> None:
    valid_sha = document["provenance_seals"][0]["seal_sha256"]
    unresolved_sha = document["provenance_seals"][1]["seal_sha256"]
    for row in document["ledger_coverage"]:
        watermark = sha256_json(
            {"ledger_name": row["ledger_name"], "synthetic_state": "unchanged"}
        )
        row.update(
            {
                "result": "CONFIRMED_NO_CHANGE",
                "before_snapshot_sha256": watermark,
                "after_snapshot_sha256": watermark,
                "provenance_seal_refs": [valid_sha],
                "unresolved_owner_ref": None,
            }
        )
    target_row = next(
        row for row in document["ledger_coverage"]
        if row["ledger_name"] == target
    )
    target_row.update(
        {
            "result": "OWNER_UNRESOLVED",
            "before_snapshot_sha256": None,
            "after_snapshot_sha256": None,
            "provenance_seal_refs": [unresolved_sha],
            "unresolved_owner_ref": {
                "expected_owner_contract": f"{target.upper()}_OWNER",
                "missing_identity_semantics": ["owner_receipt"],
                "tracking_ref": "CCZ-41" if target == "planning" else "CCZ-82",
                "reason_code": "OWNER_UNRESOLVED",
            },
        }
    )


def _apply_mutation(
    document: dict[str, Any], mutation: str
) -> dict[str, Any]:
    value = copy.deepcopy(document)
    if mutation == "none":
        return value
    if mutation == "action_as_root":
        return copy.deepcopy(value["closeout_input"])
    if mutation == "target_remapped":
        value["outcome"]["target_disposition"] = "REMAPPED"
        value["outcome"]["target_destination_ref"] = "slot:S-0003"
    elif mutation == "move_unresolved_to_planning":
        _move_unresolved(value, "planning")
    elif mutation == "move_unresolved_to_character":
        _move_unresolved(value, "character")
    elif mutation == "unresolved_seal_only":
        _move_unresolved(value, "fact")
        valid_sha = value["provenance_seals"][0]["seal_sha256"]
        unresolved_sha = value["provenance_seals"][1]["seal_sha256"]
        row = next(
            item for item in value["ledger_coverage"]
            if item["ledger_name"] == "fact"
        )
        watermark = sha256_json(
            {"ledger_name": "fact", "synthetic_state": "unchanged"}
        )
        row.update(
            {
                "result": "CONFIRMED_NO_CHANGE",
                "before_snapshot_sha256": watermark,
                "after_snapshot_sha256": watermark,
                "provenance_seal_refs": [valid_sha],
                "unresolved_owner_ref": None,
            }
        )
        value["next_chapter_handoff"]["provenance_seal_refs"] = [
            valid_sha,
            unresolved_sha,
        ]
    elif mutation == "no_prose_with_c11":
        value["manuscript"] = _resolved_document("full_check")["manuscript"]
    elif mutation == "skip_with_check_result":
        value["closeout_input"]["check_result_ref"] = "fake-pass"
        value["closeout_input"]["action_sha256"] = closeout_action_sha256(
            value["closeout_input"]
        )
    elif mutation == "scope_mismatch":
        value["truth_scope_ref"]["project_id"] = "PROJECT-OTHER"
    elif mutation == "missing_ledger":
        value["ledger_coverage"].pop()
    elif mutation == "duplicate_ledger":
        value["ledger_coverage"][-1] = copy.deepcopy(
            value["ledger_coverage"][0]
        )
    elif mutation == "unresolved_claims_resolved":
        value["claim_kind"] = "OWNER_RESOLVED_SEALED"
    elif mutation == "statement_without_basis":
        value["outcome"]["actual_completion"][0][
            "provenance_seal_refs"
        ] = []
    elif mutation == "provenance_sha_mismatch":
        value["provenance_seals"][0]["seal_sha256"] = "0" * 64
    elif mutation == "stale_settlement_sha":
        value["outcome"]["actual_completion"][0]["summary"] += " 已变化。"
        return value
    else:
        raise ContractError(f"FIXTURE_MUTATION_UNKNOWN:{mutation}")
    return seal_document(value)


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows = []
    for line_no, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != RECIPE_KEYS:
            raise ContractError(f"FIXTURE_RECIPE_INVALID:{line_no}")
        rows.append(value)
    return rows


def materialize_fixture_case(case: dict[str, Any]) -> dict[str, Any]:
    document = build_base_document(case["base"])
    return {
        **copy.deepcopy(case),
        "document": _apply_mutation(document, case["mutation"]),
    }


def validate_fixture_case(case: dict[str, Any]) -> str:
    materialized = materialize_fixture_case(case)
    try:
        return validate_settlement(materialized["document"])
    except (ContractError, KeyError, TypeError, ValueError):
        return STRUCTURAL_INVALID


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    counts = {
        STRUCTURAL_VALID: 0,
        STRUCTURAL_VALID_OWNER_UNRESOLVED: 0,
        STRUCTURAL_INVALID: 0,
    }
    for case in load_fixtures(path):
        actual = validate_fixture_case(case)
        if actual != case["expected_result"]:
            raise ContractError(
                f"FIXTURE_EXPECTATION_MISMATCH:{case['case_id']}:"
                f"{case['expected_result']}:{actual}"
            )
        counts[actual] += 1
    return counts


def main() -> int:
    counts = validate_all_fixtures()
    print(
        json.dumps(
            {
                "contract": "CHAPTER_SETTLEMENT_SEAL",
                "version": "v1",
                "status": "PASS",
                "counts": counts,
                "owner_resolution_performed": False,
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
