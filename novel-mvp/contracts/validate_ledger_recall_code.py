"""Validate LEDGER_RECALL_CODE ledger-recall-code-v1 and its resolve receipts.

Shape B only: rev-pinned codes across the ten registered ledgers. The live
three-ledger rh_ handle registry (Shape A, STALE on source advance) is a
separate mechanism and is intentionally not touched here.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent
SCHEMA_PATH = DIR / "LEDGER_RECALL_CODE.schema.json"
FIXTURE_PATH = DIR / "LEDGER_RECALL_CODE.fixtures.jsonl"
COMMON_PATH = DIR / "plan_longline_contract_common.py"


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_ledger_recall_code_common",
        COMMON_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("COMMON_HELPER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = _load_common()
ContractError = COMMON.ContractError
SCHEMA = COMMON.load_schema(SCHEMA_PATH)
CONTRACT = "LEDGER_RECALL_CODE"
VERSION = "ledger-recall-code-v1"
LEDGER_NAMES = tuple(SCHEMA["properties"]["ledger_name"]["enum"])
RETIRED_NOTICE_TEXT = COMMON.RETIRED_NOTICE_TEXT
_ENTRY_KEYS = {"ledger_name", "entry_id", "confirm_status", "revisions"}
_REVISION_KEYS = {"rev", "sha"}


def validate_code(document: Any) -> dict[str, Any]:
    COMMON.validate_schema(document, SCHEMA)
    assert isinstance(document, dict)
    if document["contract"] != CONTRACT or document["version"] != VERSION:
        raise ContractError("CONTRACT_IDENTITY_INVALID")
    if document["expires_at"] is not None:
        COMMON.parse_datetime(document["expires_at"], "EXPIRES_AT")
    return document


def _validate_registry(registry: Any) -> list[dict[str, Any]]:
    if not isinstance(registry, list):
        raise ContractError("REGISTRY_INVALID")
    for entry in registry:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise ContractError("REGISTRY_ENTRY_INVALID")
        if entry["ledger_name"] not in LEDGER_NAMES:
            raise ContractError("REGISTRY_ENTRY_LEDGER_NAME_INVALID")
        if not isinstance(entry["entry_id"], str) or not entry["entry_id"]:
            raise ContractError("REGISTRY_ENTRY_ID_INVALID")
        if entry["confirm_status"] not in COMMON.CONFIRM_STATUSES:
            raise ContractError("REGISTRY_ENTRY_CONFIRM_STATUS_INVALID")
        revisions = entry["revisions"]
        if not isinstance(revisions, list) or not revisions:
            raise ContractError("REGISTRY_ENTRY_REVISIONS_INVALID")
        revs: set[int] = set()
        for revision in revisions:
            if not isinstance(revision, dict) or set(revision) != _REVISION_KEYS:
                raise ContractError("REGISTRY_ENTRY_REVISION_INVALID")
            rev = revision["rev"]
            if not isinstance(rev, int) or isinstance(rev, bool) or rev < 1:
                raise ContractError("REGISTRY_ENTRY_REVISION_INVALID")
            if rev in revs:
                raise ContractError("REGISTRY_ENTRY_REVISION_DUPLICATE")
            revs.add(rev)
    return registry


def _rejected(reason: str) -> dict[str, Any]:
    return {"status": "REJECTED", "reason": reason}


def resolve_code(
    code: Any,
    registry: Any,
    *,
    authorized: bool = True,
    now: str | None = None,
) -> dict[str, Any]:
    """Resolve one rev-pinned code against a mechanical ledger registry.

    A valid code returns exactly the pinned entry version. Retired entries
    still serve old codes, but the receipt must carry the retirement notice
    (decision 题 7, 2026-08-22).
    """

    record = validate_code(code)
    entries = _validate_registry(registry)
    if not isinstance(authorized, bool):
        raise ContractError("AUTHORIZED_FLAG_INVALID")
    if record["expires_at"] is not None:
        if now is None:
            raise ContractError("NOW_REQUIRED_FOR_EXPIRABLE_CODE")
        expires = COMMON.parse_datetime(record["expires_at"], "EXPIRES_AT")
        current = COMMON.parse_datetime(now, "NOW")
        if current > expires:
            return _rejected("CODE_EXPIRED")
    if not authorized:
        return _rejected("UNAUTHORIZED")
    entry = next(
        (
            item
            for item in entries
            if item["ledger_name"] == record["ledger_name"]
            and item["entry_id"] == record["entry_id"]
        ),
        None,
    )
    if entry is None:
        return _rejected("ENTRY_NOT_FOUND")
    revision = next(
        (item for item in entry["revisions"] if item["rev"] == record["rev"]),
        None,
    )
    if revision is None:
        return _rejected("REVISION_NOT_FOUND")
    if revision["sha"] != record["sha"]:
        return _rejected("SHA_MISMATCH")
    retired = entry["confirm_status"] == "retired"
    return {
        "status": "OK",
        "ledger_name": record["ledger_name"],
        "entry_id": record["entry_id"],
        "rev": record["rev"],
        "sha": record["sha"],
        "retired_notice": retired,
        "notice": RETIRED_NOTICE_TEXT if retired else None,
    }


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return COMMON.load_fixtures(path)


def _resolve_case(case: dict[str, Any]) -> dict[str, Any]:
    return resolve_code(
        case["code"],
        case["registry"],
        authorized=case.get("authorized", True),
        now=case.get("now"),
    )


_HANDLERS = {
    "code": lambda case: validate_code(case["document"]),
    "resolve": _resolve_case,
}


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    return COMMON.validate_fixture_case(case, _HANDLERS)


def validate_all_fixtures(path: Path = FIXTURE_PATH) -> dict[str, int]:
    return COMMON.validate_all_fixtures(path, _HANDLERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.fixtures:
        counts = validate_all_fixtures()
        print(
            "PASS_LEDGER_RECALL_CODE "
            f"cases={counts['cases']} valid={counts['valid']} "
            f"invalid={counts['invalid']}"
        )
        return 0
    if args.input is None:
        parser.error("--input or --fixtures is required")
    validate_code(json.loads(args.input.read_text(encoding="utf-8")))
    print("PASS_LEDGER_RECALL_CODE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
