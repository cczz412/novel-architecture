"""六本设定账的唯一落盘方。

内容形状由 L1～L5 合同校验；本模块只负责发号、跨文件原子提交和禁止旁路直写。
事务协调器仍是 planstore，不另起 journal。
"""

from __future__ import annotations

import copy
import importlib.util
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from . import planstore
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import planstore  # type: ignore[no-redef]


ACTION_NAME = "setting_ledger_write"
CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"
ID_NUMBER_RE = re.compile(r"^(\d+)$")
SETTING_FAULT_POINTS = {
    "after_prepare",
    "after_characters",
    "after_locations",
    "after_items",
    "after_factions",
    "after_systems",
    "after_world_rules",
    "after_plan",
    "after_blob",
    "during_history",
    "after_history",
    "before_commit",
    "after_commit",
}
FORBIDDEN_LEDGERS = {
    "plan",
    "fact",
    "chapter",
    "longline",
    "storyline",
    "hook",
    "planning",
    "facts",
    "chapters",
}


class SettingstoreError(planstore.PlanstoreError):
    """设定账动作在写前或恢复时被拒绝。"""


@dataclass(frozen=True)
class LedgerSpec:
    name: str
    prefix: str
    counter_key: str
    filename: str
    contract: str
    version: str
    validator_file: str


LEDGERS: dict[str, LedgerSpec] = {
    "character": LedgerSpec(
        "character",
        "CH-",
        "CH",
        "characters.json",
        "CHARACTER_LEDGER_CONTENT",
        "character-ledger-content-v1.1",
        "validate_character_ledger_content.py",
    ),
    "location": LedgerSpec(
        "location",
        "LOC-",
        "LOC",
        "locations.json",
        "LOCATION_LEDGER_CONTENT",
        "location-ledger-content-v1",
        "validate_location_ledger_content.py",
    ),
    "item": LedgerSpec(
        "item",
        "IT-",
        "IT",
        "items.json",
        "ITEM_LEDGER_CONTENT",
        "item-ledger-content-v1",
        "validate_item_ledger_content.py",
    ),
    "faction": LedgerSpec(
        "faction",
        "FA-",
        "FA",
        "factions.json",
        "FACTION_LEDGER_CONTENT",
        "faction-ledger-content-v1",
        "validate_faction_ledger_content.py",
    ),
    "system": LedgerSpec(
        "system",
        "SY-",
        "SY",
        "systems.json",
        "SYSTEM_LEDGER_CONTENT",
        "system-ledger-content-v1",
        "validate_system_ledger_content.py",
    ),
    "world_rule": LedgerSpec(
        "world_rule",
        "RU-",
        "RU",
        "world_rules.json",
        "WORLD_RULE_LEDGER_CONTENT",
        "world-rule-ledger-content-v1",
        "validate_world_rule_ledger_content.py",
    ),
}


def _spec(ledger: Any) -> LedgerSpec:
    if ledger in FORBIDDEN_LEDGERS:
        raise SettingstoreError(f"LEDGER_NOT_A_SETTING_LEDGER:{ledger}")
    if not isinstance(ledger, str) or ledger not in LEDGERS:
        raise SettingstoreError(f"UNKNOWN_SETTING_LEDGER:{ledger}")
    return LEDGERS[ledger]


@lru_cache(maxsize=None)
def _validator_module(filename: str) -> Any:
    path = CONTRACTS_DIR / filename
    spec = importlib.util.spec_from_file_location(
        f"settingstore_{path.stem}",
        path,
    )
    if spec is None or spec.loader is None:
        raise SettingstoreError(f"SETTING_VALIDATOR_IMPORT_FAILED:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_records(root: Path, filename: str) -> list[dict[str, Any]]:
    path = root / filename
    if not path.exists() or path.stat().st_size == 0:
        return []
    value = planstore._read_json(path)
    if not isinstance(value, list):
        raise SettingstoreError(f"SETTING_FILE_NOT_LIST:{filename}")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise SettingstoreError(f"SETTING_RECORD_SHAPE_INVALID:{filename}")
        if item["id"] in seen:
            raise SettingstoreError(f"SETTING_ID_DUPLICATE:{item['id']}")
        seen.add(item["id"])
        records.append(item)
    return records


def _counter_value(plan: dict[str, Any], key: str) -> int:
    value = plan["id_counters"].get(key, 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SettingstoreError(f"{key}_COUNTER_INVALID")
    return value


def _id_number(entry_id: str, prefix: str) -> int | None:
    if not entry_id.startswith(prefix):
        return None
    match = ID_NUMBER_RE.fullmatch(entry_id[len(prefix) :])
    if match is None:
        return None
    return int(match.group(1))


def _assert_counter_aligned(records: list[dict[str, Any]], spec: LedgerSpec, plan: dict[str, Any]) -> None:
    numbers = [
        number
        for item in records
        for number in [_id_number(str(item.get("id")), spec.prefix)]
        if number is not None
    ]
    counter = _counter_value(plan, spec.counter_key)
    if counter != max(numbers, default=0):
        raise SettingstoreError(f"{spec.counter_key}_COUNTER_DRIFT")


def _allocate_id(plan: dict[str, Any], records: list[dict[str, Any]], spec: LedgerSpec) -> tuple[str, int]:
    used = {item["id"] for item in records}
    next_number = _counter_value(plan, spec.counter_key) + 1
    while True:
        entry_id = f"{spec.prefix}{next_number:04d}"
        if entry_id not in used:
            return entry_id, next_number
        next_number += 1


def _validate_payload(
    spec: LedgerSpec,
    record: dict[str, Any],
    *,
    before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    module = _validator_module(spec.validator_file)
    try:
        module.validate_record(record)
        if (
            spec.name == "system"
            and before is not None
            and before.get("source_identity") == "pack_prefilled"
            and hasattr(module, "validate_pack_prefilled_transition")
        ):
            module.validate_pack_prefilled_transition(before, record)
    except module.ContractError as exc:
        raise SettingstoreError(f"SETTING_CONTRACT_INVALID:{exc}") from exc
    return record


def _fill_record(
    spec: LedgerSpec,
    incoming: dict[str, Any],
    *,
    entry_id: str,
    created_at: str,
    updated_at: str,
    rev: int,
) -> dict[str, Any]:
    record = copy.deepcopy(incoming)
    record["contract"] = spec.contract
    record["version"] = spec.version
    record["id"] = entry_id
    if spec.name == "character":
        for key in ("desire_seq", "ordeal_seq", "intent_seq", "choice_seq"):
            record.setdefault(key, [])
    record["created_at"] = created_at
    record["updated_at"] = updated_at
    record["rev"] = rev
    record.setdefault("note", "")
    record.setdefault("story_time", None)
    return record


def _history_and_blob(
    *,
    operation_id: str,
    actor: str,
    spec: LedgerSpec,
    before: dict[str, Any],
    after: dict[str, Any],
    timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content_hash, blob = planstore._blob_record(before)
    row = {
        "ts": timestamp,
        "op": operation_id,
        "actor": actor,
        "action": ACTION_NAME,
        "object_id": after["id"],
        "rev": after["rev"],
        "changes": {"ledger": [spec.name, spec.name], "state": [copy.deepcopy(before), copy.deepcopy(after)]},
        "content_hash": content_hash,
        "note": f"{spec.name} setting-ledger write",
    }
    return row, blob


def _replayed_receipt(root: Path, operation_id: str) -> dict[str, Any]:
    prepare = next(
        (
            row
            for row in planstore._operation_rows(root, operation_id)
            if row.get("phase") == "prepare"
        ),
        None,
    )
    if prepare is None or not isinstance(prepare.get("receipt"), dict):
        raise SettingstoreError("COMMITTED_SETTING_RECEIPT_UNRESOLVABLE")
    return {
        **copy.deepcopy(prepare["receipt"]),
        "story_commit_seq": prepare["story_commit_seq"],
        "replayed": True,
    }


def read_setting_records(project_dir: str | Path, ledger: str) -> list[dict[str, Any]]:
    spec = _spec(ledger)
    return copy.deepcopy(_load_records(Path(project_dir), spec.filename))


def write_setting_record(
    project_dir: str | Path,
    *,
    ledger: str,
    operation_id: str,
    record: dict[str, Any],
    timestamp: str,
    actor: str = "author",
    expected_rev: int | None = None,
    fault_at: str | None = None,
) -> dict[str, Any]:
    """创建或更新一条设定账记录；ID 只由本函数发放。"""
    spec = _spec(ledger)
    if not isinstance(record, dict):
        raise SettingstoreError("SETTING_RECORD_NOT_OBJECT")
    if not isinstance(timestamp, str) or not timestamp:
        raise SettingstoreError("SETTING_TIMESTAMP_INVALID")
    if not isinstance(actor, str) or not actor:
        raise SettingstoreError("SETTING_ACTOR_INVALID")
    if expected_rev is not None and (
        not isinstance(expected_rev, int) or isinstance(expected_rev, bool) or expected_rev < 1
    ):
        raise SettingstoreError("SETTING_EXPECTED_REV_INVALID")
    if fault_at is not None and fault_at not in SETTING_FAULT_POINTS:
        raise SettingstoreError("UNKNOWN_SETTING_FAULT_POINT")
    operation_id = planstore._validate_operation_id(operation_id)
    incoming_id = record.get("id")
    if incoming_id is not None and incoming_id != "" and not isinstance(incoming_id, str):
        raise SettingstoreError("SETTING_ID_SHAPE_INVALID")

    request_sha = planstore._sha256_json(
        {
            "operation_id": operation_id,
            "ledger": ledger,
            "record": record,
            "actor": actor,
            "expected_rev": expected_rev,
        }
    )
    root = Path(project_dir)
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        status = planstore._operation_status_unlocked(root, operation_id)
        if status["state"] == "COMMITTED":
            if status["request_sha256"] != request_sha:
                raise SettingstoreError("OPERATION_ID_PAYLOAD_CONFLICT")
            return _replayed_receipt(root, operation_id)
        if status["terminal_phase"] == "rolled_back":
            raise SettingstoreError("OPERATION_ROLLED_BACK_REQUIRES_NEW_ID")
        if status["state"] == "NEEDS_MANUAL_RECOVERY":
            raise SettingstoreError("OPERATION_NEEDS_MANUAL_RECOVERY")

        plan_before = planstore._read_json(root / "plan.json")
        planstore._validate_plan(plan_before)
        records = _load_records(root, spec.filename)
        _assert_counter_aligned(records, spec, plan_before)

        existing = None
        if isinstance(incoming_id, str) and incoming_id:
            matches = [item for item in records if item["id"] == incoming_id]
            if not matches:
                raise SettingstoreError(f"SETTING_RECORD_NOT_FOUND:{incoming_id}")
            existing = copy.deepcopy(matches[0])
            if expected_rev is not None and existing["rev"] != expected_rev:
                raise SettingstoreError("STALE_SETTING_REVISION")
            if not existing["id"].startswith(spec.prefix):
                raise SettingstoreError(f"SETTING_ID_PREFIX_INVALID:{existing['id']}")
            unchanged = _fill_record(
                spec,
                record,
                entry_id=existing["id"],
                created_at=existing["created_at"],
                updated_at=existing["updated_at"],
                rev=existing["rev"],
            )
            _validate_payload(spec, unchanged, before=existing)
            if planstore._sha256_json(unchanged) == planstore._sha256_json(existing):
                return {
                    "operation_id": operation_id,
                    "status": "NO_CHANGE",
                    "ledger": spec.name,
                    "record_ref": existing["id"],
                    "rev": existing["rev"],
                    "created": False,
                    "story_commit_seq": planstore._latest_committed_story_seq(root),
                    "replayed": False,
                }
            after = _fill_record(
                spec,
                record,
                entry_id=existing["id"],
                created_at=existing["created_at"],
                updated_at=timestamp,
                rev=existing["rev"] + 1,
            )
            counter_after = _counter_value(plan_before, spec.counter_key)
            created = False
        else:
            if expected_rev is not None:
                raise SettingstoreError("SETTING_EXPECTED_REV_ON_CREATE_FORBIDDEN")
            entry_id, counter_after = _allocate_id(plan_before, records, spec)
            after = _fill_record(
                spec,
                record,
                entry_id=entry_id,
                created_at=timestamp,
                updated_at=timestamp,
                rev=1,
            )
            created = True

        _validate_payload(spec, after, before=existing)

        if created:
            records_after = [*records, after]
        else:
            records_after = [
                after if item["id"] == after["id"] else item for item in records
            ]
        plan_after = copy.deepcopy(plan_before)
        plan_after["id_counters"][spec.counter_key] = counter_after
        planstore._validate_plan(plan_after)
        _assert_counter_aligned(records_after, spec, plan_after)

        before_snapshot = existing or {
            "id": after["id"],
            "rev": 0,
            "state": "absent",
        }
        history_row, blob = _history_and_blob(
            operation_id=operation_id,
            actor=actor,
            spec=spec,
            before=before_snapshot,
            after=after,
            timestamp=timestamp,
        )
        return planstore._commit_generic_transaction_locked(
            root,
            operation_id=operation_id,
            action_name=ACTION_NAME,
            request_sha256=request_sha,
            replacements={
                spec.filename: planstore._canonical_bytes(records_after),
                "plan.json": planstore._canonical_bytes(plan_after),
            },
            appends={"plan_history.jsonl": planstore._canonical_bytes(history_row)},
            blobs=[blob],
            receipt={
                "operation_id": operation_id,
                "status": "COMMITTED",
                "ledger": spec.name,
                "record_ref": after["id"],
                "rev": after["rev"],
                "created": created,
            },
            timestamp=timestamp,
            fault_at=fault_at,
        )
