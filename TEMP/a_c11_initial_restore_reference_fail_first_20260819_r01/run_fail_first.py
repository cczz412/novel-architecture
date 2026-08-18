"""TEMP-only fail-first probes for C11 INITIAL and RESTORE reference gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CONTRACTS_DIR = REPO_ROOT / "novel-mvp" / "contracts"

sys.path.insert(0, str(CONTRACTS_DIR))
import validate_c11_chapter_revision_ledger as c11  # noqa: E402


OLD = "甲拿起钥匙。乙离开。"
CHANGED = "甲放下钥匙。乙回家。"


def capture(call: Callable[[], Any]) -> str:
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001 - the probe records current formal behavior verbatim.
        return str(exc)
    return "PASS" if result is None else str(result)


def schema_result(document: dict[str, Any]) -> str:
    validator = c11.schema_validator()
    return capture(lambda: c11.validate_schema_document(validator, document))


def ledger_result(ledger: dict[str, Any]) -> str:
    return capture(lambda: c11.validate_ledger(ledger))


def initial_helper_result(
    ledger: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    row = ledger["revisions"][0]
    return c11.validate_current_c10_eligibility(
        row["content_ref"],
        row["origin_material_ref"],
        records,
        require_referenced_revision_is_current=True,
    )


def initial_case(
    case_id: str,
    *,
    role: str | None = "CHAPTER",
    state: str = "CONFIRMED",
    current_identity_revision_no: int = 1,
    referenced_identity_revision_no: int = 1,
) -> dict[str, Any]:
    ledger = c11.ledger_one(OLD)
    ledger["revisions"][0]["origin_material_ref"][
        "identity_revision_no"
    ] = referenced_identity_revision_no
    records = [
        c11.c10_material_record(
            OLD,
            "R1",
            role=role,
            state=state,
            identity_revision_no=current_identity_revision_no,
        )
    ]
    schema = schema_result(ledger)
    ledger_check = ledger_result(ledger)
    helper = initial_helper_result(ledger, records)
    wrong_success = schema == "PASS" and ledger_check == "PASS" and helper != "C10_CONFIRMED_CHAPTER_ELIGIBLE"
    return {
        "case_id": case_id,
        "schema_result": schema,
        "validate_ledger_result": ledger_check,
        "eligibility_helper_result": helper,
        "formal_action_shape": "INITIAL_NOT_REPRESENTABLE_IN_CHAPTER_REVISION_COMMIT_ACTION",
        "current_machine_reachability": "DIRECT_LEDGER_SCHEMA_AND_VALIDATE_LEDGER_PATH_ACCEPTS",
        "wrong_success": wrong_success,
    }


def revision_kind_case(case_id: str, *, revision_no: int) -> dict[str, Any]:
    ledger = c11.ledger_one(OLD)
    if revision_no == 1:
        ledger["revisions"][0]["change_kind"] = "REPLACE"
        row = ledger["revisions"][0]
        material = c11.c10_material_record(OLD, "R1")
    else:
        ledger = c11.append_replace(ledger, CHANGED)
        ledger["revisions"][1]["change_kind"] = "INITIAL"
        row = ledger["revisions"][1]
        material = c11.c10_material_record(CHANGED, "R2")
    schema = schema_result(ledger)
    ledger_check = ledger_result(ledger)
    helper = c11.validate_current_c10_eligibility(
        row["content_ref"],
        row["origin_material_ref"],
        [material],
        require_referenced_revision_is_current=True,
    )
    return {
        "case_id": case_id,
        "schema_result": schema,
        "validate_ledger_result": ledger_check,
        "eligibility_helper_result": helper,
        "formal_action_shape": "INITIAL_KIND_ONLY_EXISTS_IN_LEDGER_REVISION_SCHEMA",
        "current_machine_reachability": "DIRECT_LEDGER_SCHEMA_AND_VALIDATE_LEDGER_PATH_ACCEPTS",
        "wrong_success": schema == "PASS" and ledger_check == "PASS",
    }


def restore_missing_identity_revision_case() -> dict[str, Any]:
    ledger = c11.ledger_one(OLD)
    ledger["revisions"][0]["origin_material_ref"]["identity_revision_no"] = 999
    ledger = c11.append_replace(ledger, CHANGED)
    action = c11.restore_action(ledger, 1)
    material = c11.c10_material_record(OLD, "R1", identity_revision_no=2)
    schema = schema_result(action)
    ledger_check = ledger_result(ledger)
    historical_revision_exists = any(
        revision["revision_no"] == 999 for revision in material["identity_revisions"]
    )
    helper = c11.validate_current_c10_eligibility(
        ledger["revisions"][0]["content_ref"],
        ledger["revisions"][0]["origin_material_ref"],
        [material],
        require_referenced_revision_is_current=False,
    )
    action_result = c11.validate_action(action, ledger, [material])
    return {
        "case_id": "FF-06",
        "schema_result": schema,
        "validate_ledger_result": ledger_check,
        "eligibility_helper_result": helper,
        "historical_identity_revision_exists": historical_revision_exists,
        "formal_action_result": action_result,
        "current_machine_reachability": "VALIDATE_ACTION_PRECHECK_ALLOWED",
        "wrong_success": (
            schema == "PASS"
            and ledger_check == "PASS"
            and not historical_revision_exists
            and action_result == "PRECHECK_ALLOWED"
        ),
    }


def run() -> dict[str, Any]:
    results = [
        initial_case("FF-01", role="SETTING"),
        initial_case("FF-02", role="INTRO", state="CANDIDATE"),
        initial_case(
            "FF-03",
            current_identity_revision_no=2,
            referenced_identity_revision_no=1,
        ),
        revision_kind_case("FF-04", revision_no=1),
        revision_kind_case("FF-05", revision_no=2),
        restore_missing_identity_revision_case(),
    ]
    return {
        "identity": "A_C11_INITIAL_RESTORE_REFERENCE_FAIL_FIRST_R01",
        "verdict": (
            "CONTRACT_MACHINE_GAP_FOUND"
            if any(row["wrong_success"] for row in results)
            else "NO_NEW_GAP"
        ),
        "wrong_success_count": sum(row["wrong_success"] for row in results),
        "case_count": len(results),
        "formal_writes": 0,
        "api_calls": 0,
        "automatic_retries": 0,
        "results": results,
    }


def main() -> int:
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
