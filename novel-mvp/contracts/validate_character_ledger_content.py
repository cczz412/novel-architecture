"Validate CHARACTER_LEDGER_CONTENT v1 records and as-of query semantics."

from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


CONTRACTS_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = CONTRACTS_DIR / "CHARACTER_LEDGER_CONTENT.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "CHARACTER_LEDGER_CONTENT.fixtures.jsonl"
ENVELOPE_VALIDATOR_PATH = CONTRACTS_DIR / "validate_ledger_entry_envelope.py"

CONTRACT_NAME = "CHARACTER_LEDGER_CONTENT"
CONTRACT_VERSION = "character-ledger-content-v1"
ENVELOPE_KEYS = (
    "id",
    "source_identity",
    "confirm_status",
    "evidence_refs",
    "story_time",
    "created_at",
    "updated_at",
    "rev",
    "note",
)
ALIVE_VALUES = frozenset({"alive", "dead"})
DESTINY_REF_PATTERN = "DESTINY-"


class ContractError(ValueError):
    "A CHARACTER_LEDGER_CONTENT invariant failed."


def _load_schema() -> dict[str, Any]:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


SCHEMA = _load_schema()
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def _load_envelope_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_ledger_entry_envelope_for_character",
        ENVELOPE_VALIDATOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise ContractError("ENVELOPE_VALIDATOR_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENVELOPE_VALIDATOR = _load_envelope_validator()


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
        raise ContractError(f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}")


def _parse_datetime(value: str, *, label: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError(f"{label}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


def _envelope(document: dict[str, Any]) -> dict[str, Any]:
    return {key: document[key] for key in ENVELOPE_KEYS}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _anchor_story_order(anchor: dict[str, Any]) -> int | None:
    value = anchor.get("story_order")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _chapter_revision_ref(anchor: dict[str, Any]) -> dict[str, Any]:
    value = anchor.get("chapter_revision_ref")
    if not isinstance(value, dict):
        raise ContractError("CHAPTER_REVISION_REF_REQUIRED")
    return value


def _validate_interval(value: dict[str, Any], *, label: str) -> None:
    start = value["start"]
    end = value["end"]
    if end is None:
        return
    start_order = _anchor_story_order(start)
    end_order = _anchor_story_order(end)
    if start_order is not None and end_order is not None:
        if end_order <= start_order:
            raise ContractError(f"STORY_INTERVAL_END_NOT_AFTER_START:{label}")
        return
    if _chapter_revision_ref(start) == _chapter_revision_ref(end):
        raise ContractError(f"STORY_INTERVAL_END_EQUALS_START:{label}")


def _nested_attestation_requires_author(record: dict[str, Any], evidence_refs: list[str]) -> None:
    if "AUTHOR_ATTESTATION" not in evidence_refs:
        return
    if (
        record["source_identity"] != "author_declared"
        or record["confirm_status"] != "confirmed"
    ):
        raise ContractError(
            "NESTED_AUTHOR_ATTESTATION_REQUIRES_AUTHOR_DECLARED_CONFIRMED"
        )


def validate_record(
    document: Any,
    *,
    destiny_ids: frozenset[str] | set[str] | None = None,
) -> dict[str, Any]:
    "Validate one complete character-ledger record."

    _validate_schema(document)
    assert isinstance(document, dict)

    try:
        ENVELOPE_VALIDATOR.validate_entry(_envelope(document), entry_kind="DEFINITION")
    except ENVELOPE_VALIDATOR.ContractError as exc:
        raise ContractError(f"ENVELOPE_INVALID:{exc}") from exc

    created = _parse_datetime(document["created_at"], label="CREATED_AT")
    updated = _parse_datetime(document["updated_at"], label="UPDATED_AT")
    if updated < created:
        raise ContractError("UPDATED_AT_BEFORE_CREATED_AT")

    alias_names: set[str] = set()
    for index, alias in enumerate(document["aliases"]):
        name = alias["name"]
        if name in alias_names:
            raise ContractError(f"ALIAS_NAME_DUPLICATE:{name}")
        alias_names.add(name)
        _validate_interval(alias["story_time"], label=f"aliases[{index}]")
        _nested_attestation_requires_author(document, alias["evidence_refs"])

    state_starts: set[tuple[str, str]] = set()
    alive_start_keys: set[str] = set()
    for index, item in enumerate(document["state_timeline"]):
        if item["ch_ref"] != document["id"]:
            raise ContractError(f"STATE_CH_REF_MUST_MATCH_CHARACTER:{index}")
        _validate_interval(item["story_time"], label=f"state_timeline[{index}]")
        _nested_attestation_requires_author(document, item["evidence_refs"])

        start_key = _canonical(item["story_time"]["start"])
        identity = (item["state_key"], start_key)
        if identity in state_starts:
            raise ContractError(
                f"STATE_START_DUPLICATE:{item['state_key']}:{index}"
            )
        state_starts.add(identity)

        if item["state_key"] == "alive":
            if item["value"] not in ALIVE_VALUES:
                raise ContractError(f"ALIVE_VALUE_INVALID:{item['value']}")
            if "AUTHOR_ATTESTATION" not in item["evidence_refs"]:
                raise ContractError(
                    f"ALIVE_TRANSITION_REQUIRES_AUTHOR_ATTESTATION:{index}"
                )
            if start_key in alive_start_keys:
                raise ContractError(f"ALIVE_TRANSITION_START_DUPLICATE:{index}")
            alive_start_keys.add(start_key)

    relation_starts: set[tuple[str, str, str]] = set()
    for index, item in enumerate(document["relationships"]):
        if item["target_ref"] == document["id"]:
            raise ContractError(f"RELATIONSHIP_SELF_FORBIDDEN:{index}")
        _validate_interval(item["story_time"], label=f"relationships[{index}]")
        _nested_attestation_requires_author(document, item["evidence_refs"])
        identity = (
            item["target_ref"],
            item["kind"],
            _canonical(item["story_time"]["start"]),
        )
        if identity in relation_starts:
            raise ContractError(
                f"RELATIONSHIP_START_DUPLICATE:{item['target_ref']}:{item['kind']}"
            )
        relation_starts.add(identity)

    # Review note 3 closed in L5: destiny_ref now has an official prefix
    # (PLAN_DESTINY_CONTENT) and, when a destiny directory is supplied,
    # a mandatory existence check.
    destiny_ref = document["destiny_ref"]
    if destiny_ref is not None:
        if not isinstance(destiny_ref, str):
            raise ContractError("DESTINY_REF_SHAPE_INVALID")
        if not (
            destiny_ref.startswith(DESTINY_REF_PATTERN)
            and destiny_ref[len(DESTINY_REF_PATTERN):].isdigit()
        ):
            raise ContractError(f"DESTINY_REF_PREFIX_INVALID:{destiny_ref}")
        if destiny_ids is not None and destiny_ref not in destiny_ids:
            raise ContractError(f"DESTINY_REF_NOT_FOUND:{destiny_ref}")

    return document


def _exact_ref_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _chapter_revision_ref(left) == _chapter_revision_ref(right)


def query_state_as_of(
    document: Any,
    *,
    state_key: str,
    as_of: dict[str, Any],
) -> dict[str, Any]:
    "Return an explicitly bounded as-of result; never substitute the latest value."

    record = validate_record(document)
    if not isinstance(state_key, str) or not state_key:
        raise ContractError("QUERY_STATE_KEY_INVALID")
    if not isinstance(as_of, dict) or "chapter_revision_ref" not in as_of:
        raise ContractError("QUERY_AS_OF_INVALID")

    candidates = [
        item for item in record["state_timeline"] if item["state_key"] == state_key
    ]
    if not candidates:
        return {"status": "NOT_RECORDED", "state_key": state_key, "value": None}

    target_order = _anchor_story_order(as_of)
    if target_order is not None:
        comparable: list[tuple[int, dict[str, Any]]] = []
        for item in candidates:
            interval = item["story_time"]
            start_order = _anchor_story_order(interval["start"])
            end_order = (
                _anchor_story_order(interval["end"])
                if interval["end"] is not None
                else None
            )
            if start_order is None:
                continue
            if start_order <= target_order and (
                end_order is None or target_order < end_order
            ):
                comparable.append((start_order, item))
        if not comparable:
            if any(
                _anchor_story_order(item["story_time"]["start"]) is None
                for item in candidates
            ):
                return {
                    "status": "STORY_TIME_NOT_COMPARABLE",
                    "state_key": state_key,
                    "value": None,
                }
            return {"status": "NOT_RECORDED", "state_key": state_key, "value": None}
        latest_start = max(start for start, _ in comparable)
        matches = [item for start, item in comparable if start == latest_start]
    else:
        matches = [
            item
            for item in candidates
            if _exact_ref_match(item["story_time"]["start"], as_of)
        ]
        if not matches:
            return {
                "status": "STORY_TIME_NOT_COMPARABLE",
                "state_key": state_key,
                "value": None,
            }

    if len(matches) != 1:
        raise ContractError(f"STATE_QUERY_AMBIGUOUS:{state_key}:{len(matches)}")
    item = matches[0]
    return {
        "status": "RECORDED",
        "state_key": state_key,
        "value": item["value"],
        "evidence_refs": list(item["evidence_refs"]),
        "story_time": item["story_time"],
    }


def load_fixtures(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractError(f"FIXTURE_JSON_INVALID:{line_no}") from exc
        if not isinstance(row, dict):
            raise ContractError(f"FIXTURE_NOT_OBJECT:{line_no}")
        rows.append(row)
    case_ids = [row.get("case_id") for row in rows]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        raise ContractError("FIXTURE_CASE_ID_INVALID")
    if len(case_ids) != len(set(case_ids)):
        raise ContractError("FIXTURE_CASE_ID_DUPLICATE")
    return rows


def validate_fixture_case(case: dict[str, Any]) -> str | None:
    destiny_ids = (
        frozenset(case["known_destiny_ids"])
        if "known_destiny_ids" in case
        else None
    )
    try:
        validate_record(case.get("document"), destiny_ids=destiny_ids)
    except ContractError as exc:
        return str(exc)
    return None


def run_fixtures(path: Path = FIXTURE_PATH) -> tuple[int, int]:
    rows = load_fixtures(path)
    valid_count = 0
    invalid_count = 0
    for case in rows:
        actual_error = validate_fixture_case(case)
        if case.get("valid") is True:
            valid_count += 1
            if actual_error is not None:
                raise ContractError(
                    f"FIXTURE_EXPECTED_VALID:{case['case_id']}:{actual_error}"
                )
        elif case.get("valid") is False:
            invalid_count += 1
            expected = case.get("expected_error")
            if not isinstance(expected, str) or not expected:
                raise ContractError(
                    f"FIXTURE_EXPECTED_ERROR_MISSING:{case['case_id']}"
                )
            if actual_error is None or not actual_error.startswith(expected):
                raise ContractError(
                    f"FIXTURE_ERROR_MISMATCH:{case['case_id']}:"
                    f"expected={expected}:actual={actual_error}"
                )
        else:
            raise ContractError(f"FIXTURE_VALID_FLAG_INVALID:{case['case_id']}")
    return valid_count, invalid_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", action="store_true")
    parser.add_argument("--fixture-path", type=Path, default=FIXTURE_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.fixtures:
        print("Use --fixtures to validate the frozen fixture pack.")
        return 0
    valid_count, invalid_count = run_fixtures(args.fixture_path)
    total = valid_count + invalid_count
    print(
        "PASS_CHARACTER_LEDGER_CONTENT "
        f"cases={total} valid={valid_count} invalid={invalid_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
