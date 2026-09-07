"""Shared mechanics for L2/L3 setting-ledger content contracts."""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS_DIR = Path(__file__).resolve().parent
ENVELOPE_PATH = CONTRACTS_DIR / "validate_ledger_entry_envelope.py"
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
TAG_TARGETS_BY_CONTRACT = {
    "CHARACTER_LEDGER_CONTENT": frozenset(
        {
            "/id", "/created_at", "/updated_at", "/rev", "/note",
            "/source_identity", "/confirm_status", "/evidence_refs", "/story_time",
            "/canonical_name", "/aliases", "/role_tag", "/profile", "/visibility",
            "/destiny_ref", "/state_timeline", "/relationships", "/desire_seq",
            "/ordeal_seq", "/intent_seq", "/choice_seq",
        }
    ),
    "LOCATION_LEDGER_CONTENT": frozenset(
        {
            "/id", "/created_at", "/updated_at", "/rev", "/note",
            "/source_identity", "/confirm_status", "/evidence_refs", "/story_time",
            "/name", "/aliases", "/loc_type", "/parent_ref", "/profile",
            "/state_timeline",
        }
    ),
    "ITEM_LEDGER_CONTENT": frozenset(
        {
            "/id", "/created_at", "/updated_at", "/rev", "/note",
            "/source_identity", "/confirm_status", "/evidence_refs", "/story_time",
            "/name", "/item_type", "/first_seen", "/ownership", "/item_status",
        }
    ),
    "FACTION_LEDGER_CONTENT": frozenset(
        {
            "/id", "/created_at", "/updated_at", "/rev", "/note",
            "/source_identity", "/confirm_status", "/evidence_refs", "/story_time",
            "/name", "/aliases", "/fac_type", "/members", "/relations", "/profile",
        }
    ),
    "SYSTEM_LEDGER_CONTENT": frozenset(
        {
            "/id", "/created_at", "/updated_at", "/rev", "/note",
            "/source_identity", "/confirm_status", "/evidence_refs", "/story_time",
            "/name", "/category", "/rank_order", "/relations", "/scope", "/pack_ref",
        }
    ),
    "WORLD_RULE_LEDGER_CONTENT": frozenset(
        {
            "/id", "/created_at", "/updated_at", "/rev", "/note",
            "/source_identity", "/confirm_status", "/evidence_refs", "/story_time",
            "/rule_text", "/scope", "/hardness", "/exceptions",
        }
    ),
}
LEGACY_KEYS = {"story" + "_sequence", "text" + "_sha256"}


class ContractError(ValueError):
    """A shared setting-ledger contract invariant failed."""


def _load_envelope() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_ledger_entry_envelope_for_setting_ledgers",
        ENVELOPE_PATH,
    )
    if spec is None or spec.loader is None:
        raise ContractError("ENVELOPE_VALIDATOR_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENVELOPE = _load_envelope()


def load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def _schema_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "$"


def _walk_keys(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            result.append(str(key))
            result.extend(_walk_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            result.extend(_walk_keys(nested))
    return result


def validate_schema(document: Any, schema: dict[str, Any]) -> None:
    legacy = sorted(set(_walk_keys(document)) & LEGACY_KEYS)
    if legacy:
        raise ContractError("LEGACY_STORY_ANCHOR_KEY_FORBIDDEN:" + ",".join(legacy))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        first = errors[0]
        raise ContractError(f"SCHEMA_INVALID:{_schema_path(first)}:{first.validator}")


def _parse_datetime(value: str, label: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError(f"{label}_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{label}_TIMEZONE_REQUIRED")
    return parsed


def envelope(document: dict[str, Any]) -> dict[str, Any]:
    keys = list(ENVELOPE_KEYS)
    if document.get("version", "").endswith("-v2"):
        keys.extend(("tags", "tag_groups"))
    return {key: document[key] for key in keys}


def validate_root(
    document: Any,
    *,
    schema: dict[str, Any],
    contract: str,
    version: str | tuple[str, ...] | list[str] | set[str],
    prefix: str,
) -> dict[str, Any]:
    validate_schema(document, schema)
    assert isinstance(document, dict)
    accepted_versions = {version} if isinstance(version, str) else set(version)
    if document["contract"] != contract or document["version"] not in accepted_versions:
        raise ContractError("CONTRACT_IDENTITY_INVALID")
    if not document["id"].startswith(prefix):
        raise ContractError("LEDGER_ID_PREFIX_INVALID")
    try:
        ENVELOPE.validate_entry(
            envelope(document),
            entry_kind="DEFINITION",
            contract_version=(
                ENVELOPE.CONTRACT_VERSION_V2
                if document["version"].endswith("-v2")
                else ENVELOPE.CONTRACT_VERSION_V1
            ),
            allowed_targets=TAG_TARGETS_BY_CONTRACT.get(contract),
        )
    except ENVELOPE.ContractError as exc:
        raise ContractError(f"ENVELOPE_INVALID:{exc}") from exc
    created = _parse_datetime(document["created_at"], "CREATED_AT")
    updated = _parse_datetime(document["updated_at"], "UPDATED_AT")
    if updated < created:
        raise ContractError("UPDATED_AT_BEFORE_CREATED_AT")
    return document


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def chapter_ref(anchor: dict[str, Any]) -> dict[str, Any]:
    value = anchor.get("chapter_revision_ref")
    if not isinstance(value, dict):
        raise ContractError("CHAPTER_REVISION_REF_REQUIRED")
    return value


def story_order(anchor: dict[str, Any]) -> int | None:
    value = anchor.get("story_order")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def validate_interval(interval: dict[str, Any], label: str) -> None:
    start = interval["start"]
    end = interval["end"]
    if end is None:
        return
    start_order = story_order(start)
    end_order = story_order(end)
    if start_order is not None and end_order is not None:
        if end_order <= start_order:
            raise ContractError(f"STORY_INTERVAL_END_NOT_AFTER_START:{label}")
        return
    if chapter_ref(start) == chapter_ref(end):
        raise ContractError(f"STORY_INTERVAL_END_EQUALS_START:{label}")


def validate_evidence(record: dict[str, Any], refs: list[str], label: str) -> None:
    if not refs:
        raise ContractError(f"EVIDENCE_REQUIRED:{label}")
    if "AUTHOR_ATTESTATION" in refs and (
        record["source_identity"] != "author_declared"
        or record["confirm_status"] != "confirmed"
    ):
        raise ContractError(
            f"NESTED_AUTHOR_ATTESTATION_REQUIRES_AUTHOR_DECLARED_CONFIRMED:{label}"
        )


def validate_aliases(record: dict[str, Any], aliases: list[dict[str, Any]]) -> None:
    names: set[str] = set()
    for index, alias in enumerate(aliases):
        if alias["name"] in names:
            raise ContractError(f"ALIAS_NAME_DUPLICATE:{alias['name']}")
        names.add(alias["name"])
        validate_interval(alias["story_time"], f"aliases[{index}]")
        validate_evidence(record, alias["evidence_refs"], f"aliases[{index}]")


def validate_timeline(
    record: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    identity: Callable[[dict[str, Any]], tuple[Any, ...]],
    label: str,
) -> None:
    seen: set[tuple[Any, ...]] = set()
    for index, entry in enumerate(entries):
        validate_interval(entry["story_time"], f"{label}[{index}]")
        validate_evidence(record, entry["evidence_refs"], f"{label}[{index}]")
        key = (*identity(entry), canonical(entry["story_time"]["start"]))
        if key in seen:
            raise ContractError(f"TIMELINE_START_DUPLICATE:{label}:{index}")
        seen.add(key)


def _exact_anchor(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return chapter_ref(left) == chapter_ref(right)


def _active(interval: dict[str, Any], as_of: dict[str, Any]) -> str:
    start = interval["start"]
    end = interval["end"]
    target_order = story_order(as_of)
    start_order = story_order(start)
    if target_order is not None and start_order is not None:
        if target_order < start_order:
            return "OUTSIDE"
        if end is None:
            return "ACTIVE"
        end_order = story_order(end)
        if end_order is None:
            return "NOT_COMPARABLE"
        return "ACTIVE" if target_order < end_order else "OUTSIDE"
    if _exact_anchor(start, as_of):
        return "ACTIVE"
    return "NOT_COMPARABLE"


def query_timeline_as_of(
    entries: list[dict[str, Any]],
    *,
    as_of: dict[str, Any],
    predicate: Callable[[dict[str, Any]], bool],
    project: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    candidates = [entry for entry in entries if predicate(entry)]
    if not candidates:
        return {"status": "NOT_RECORDED"}
    active: list[dict[str, Any]] = []
    incomparable = False
    for entry in candidates:
        state = _active(entry["story_time"], as_of)
        if state == "ACTIVE":
            active.append(entry)
        elif state == "NOT_COMPARABLE":
            incomparable = True
    if not active:
        return {
            "status": (
                "STORY_TIME_NOT_COMPARABLE" if incomparable else "NOT_RECORDED"
            )
        }
    ordered = [
        (story_order(entry["story_time"]["start"]), entry) for entry in active
    ]
    with_order = [(order, entry) for order, entry in ordered if order is not None]
    if with_order:
        highest = max(order for order, _ in with_order)
        chosen = [entry for order, entry in with_order if order == highest]
    else:
        chosen = active
    if len(chosen) != 1:
        raise ContractError(f"AS_OF_QUERY_AMBIGUOUS:{len(chosen)}")
    return {"status": "RECORDED", **project(chosen[0])}


def load_fixtures(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [row.get("case_id") for row in rows]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise ContractError("FIXTURE_CASE_ID_INVALID")
    if len(ids) != len(set(ids)):
        raise ContractError("FIXTURE_CASE_ID_DUPLICATE")
    return rows
