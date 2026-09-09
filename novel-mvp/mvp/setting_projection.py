"""已确认事实经显式绑定写入六本设定账；不猜主体，不替作者签字。

SETTING_PROJECTION_BINDING / SETTING_PROJECTION_RECEIPT 都是候选形状。
设定正文只由 settingstore 写；续跑底稿和回执复用 planstore 的事务日志。
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from . import factstore, planstore, settingstore
from .workspace import AuthorWorkspace, _author_workspace_binding


SHAPE_STATUS = "CANDIDATE_SHAPE_NOT_FROZEN"
SETTING_PROJECTION_BINDING = "SETTING_PROJECTION_BINDING"
SETTING_PROJECTION_RECEIPT = "SETTING_PROJECTION_RECEIPT"
BINDINGS_FILENAME = "setting_projection_bindings.json"
ACTION_INPUT = "setting_projection_input"
ACTION_MEMO = "setting_projection_memo"
ACTION_RECEIPT = "setting_projection_receipt"
BINDING_KEYS = {
    "fact_id",
    "ledger",
    "target",
    "kind",
    "state_key",
    "value",
    "proposer",
    "note",
}
NAME_FIELDS = {
    "character": "canonical_name",
    "location": "name",
    "item": "name",
    "faction": "name",
    "system": "name",
    "world_rule": "rule_text",
}
# 只认绑定点名的字段；这里不是从事实句猜账的规则表。
DEFINITION_FIELDS = {
    "character": {"profile", "role_tag"},
    "location": {"profile", "loc_type", "parent_ref"},
    "item": {"item_type"},
    "faction": {"profile", "fac_type"},
    "system": {"category", "rank_order", "scope", "relations"},
    "world_rule": {"scope", "hardness", "exceptions"},
}
TIMELINES = {
    "character": ("state_timeline", "ch_ref"),
    "location": ("state_timeline", "loc_ref"),
    "item": ("item_status", "it_ref"),
}
FACT_ID_RE = re.compile(r"f[0-9]{3,}\Z")


class SettingProjectionError(ValueError):
    """code 是稳定错误码；消息不带机器路径或小说正文。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> None:
    raise SettingProjectionError(code)


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SettingProjectionError("PROJECTION_VALUE_NOT_JSON") from exc


def _sha(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _bound_project_dir(workspace: AuthorWorkspace) -> Path:
    """只从已认证句柄取本地项目根；不接受调用方提供作者、项目或替代路径。"""
    binding = _author_workspace_binding(workspace)
    return binding.backend._require_project(binding.author_id, binding.project_id)


def initialize_setting_allocator(
    workspace: AuthorWorkspace, *, book_id: str
) -> dict[str, Any]:
    """Explicitly prepare the physical setting allocator for a bound workspace.

    A logical plan without a physical allocator needs reconciliation, not an
    inferred copy or a fresh set of counters.
    """
    root = _bound_project_dir(workspace)
    binding = _author_workspace_binding(workspace)
    # Workspace commits take this lock too. Acquire workspace before planstore;
    # projection and reader paths release either lock before taking the other.
    with binding.backend._exclusive_lock(root):
        if workspace.read("plan") is not None:
            _fail("PROJECTION_LOGICAL_PLAN_REQUIRES_RECONCILIATION")
        return settingstore.initialize_setting_allocator(root, book_id=book_id)


def _regular_bytes(path: Path) -> bytes | None:
    """缺文件留空；不跟随符号链接，也不阻塞在管道等非普通文件上。"""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SettingProjectionError("PROJECTION_SOURCE_UNSAFE") from exc
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            _fail("PROJECTION_SOURCE_UNSAFE")
        return handle.read()


def _read_json_file(path: Path, default: Any) -> Any:
    raw = _regular_bytes(path)
    if raw is None:
        return copy.deepcopy(default)
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise SettingProjectionError("PROJECTION_SOURCE_INVALID_JSON") from exc


def validate_setting_projection_binding(value: Any) -> dict[str, Any]:
    """校验一条绑定。definition 可没有补充值；state 必须给出键和值。"""
    if not isinstance(value, dict) or set(value) != BINDING_KEYS:
        _fail("BINDING_FIELDS_INVALID")
    fact_id, ledger = value["fact_id"], value["ledger"]
    if not isinstance(fact_id, str) or FACT_ID_RE.fullmatch(fact_id) is None:
        _fail("BINDING_FACT_ID_INVALID")
    if not isinstance(ledger, str) or ledger not in settingstore.LEDGERS:
        _fail("BINDING_LEDGER_INVALID")
    target = value["target"]
    if not isinstance(target, dict) or set(target) != {"entry_id", "canonical_name"}:
        _fail("BINDING_TARGET_INVALID")
    if not _nonempty(target["canonical_name"]):
        _fail("BINDING_NAME_INVALID")
    entry_id = target["entry_id"]
    prefix = re.escape(settingstore.LEDGERS[ledger].prefix)
    if entry_id is not None and (
        not isinstance(entry_id, str)
        or re.fullmatch(prefix + r"[0-9]+", entry_id) is None
    ):
        _fail("BINDING_ENTRY_ID_INVALID")
    if value["proposer"] not in ("author", "model", "rule"):
        _fail("BINDING_PROPOSER_INVALID")
    if not isinstance(value["note"], str):
        _fail("BINDING_NOTE_INVALID")
    if value["kind"] == "definition":
        if value["state_key"] is not None:
            _fail("BINDING_DEFINITION_STATE_KEY_FORBIDDEN")
        patch = value["value"]
        if patch is not None and (
            not isinstance(patch, dict) or not set(patch) <= DEFINITION_FIELDS[ledger]
        ):
            _fail("BINDING_DEFINITION_VALUE_INVALID")
    elif value["kind"] == "state":
        if not _nonempty(value["state_key"]) or value["value"] is None:
            _fail("BINDING_STATE_VALUE_REQUIRED")
        if ledger in {"system", "world_rule"}:
            _fail("BINDING_STATE_NOT_SUPPORTED")
        if ledger == "character" and value["state_key"] == "alive":
            _fail("BINDING_ALIVE_REQUIRES_AUTHOR_ACTION")
    else:
        _fail("BINDING_KIND_INVALID")
    _json_bytes(value)
    return copy.deepcopy(value)


def validate_setting_projection_bindings(value: Any) -> list[dict[str, Any]]:
    """文件是记录数组；一条事实只能有一条绑定，包括完全相同的重复行。"""
    if not isinstance(value, list):
        _fail("BINDINGS_NOT_LIST")
    rows = [validate_setting_projection_binding(row) for row in value]
    if len({row["fact_id"] for row in rows}) != len(rows):
        _fail("BINDING_FACT_DUPLICATE")
    return rows


def read_setting_projection_bindings(project_dir: str | Path) -> list[dict[str, Any]]:
    """读手写绑定文件；没有文件就没有绑定，不顺手补建。"""
    return validate_setting_projection_bindings(
        _read_json_file(Path(project_dir) / BINDINGS_FILENAME, [])
    )


def _inputs(source: str | Path | AuthorWorkspace, root: Path) -> dict[str, Any]:
    bindings = read_setting_projection_bindings(root)
    if isinstance(source, AuthorWorkspace):
        snapshot = source.read_current_snapshot(["facts"])
        facts_state = snapshot.read("facts")
        facts = [] if facts_state is None else facts_state["payload"]
        if not source.is_current_snapshot(snapshot):
            _fail("PROJECTION_INPUT_CHANGED")
        identity = {"author_id": source.author_id, "project_id": source.project_id}
    else:
        facts = _read_json_file(root / "facts.json", [])
        identity = None
    if not isinstance(facts, list) or not all(isinstance(row, dict) for row in facts):
        _fail("PROJECTION_FACTS_INVALID")
    try:
        modern = [row for row in facts if row.get("version") == "v1"]
        legacy = [row for row in facts if row.get("version") != "v1"]
        factstore.validate_c4_v1_snapshot(modern)
        factstore._validate_facts(legacy)
        for row in legacy:
            if row.get("version") not in (None, "v0-r02"):
                _fail("PROJECTION_FACT_VERSION_UNSUPPORTED")
            if row.get("contract") not in (None, "C4_FACT_QUERY"):
                _fail("PROJECTION_FACT_VERSION_UNSUPPORTED")
            if (
                any(
                    not isinstance(row.get(key), str)
                    for key in (
                        "id",
                        "chapter_id",
                        "text",
                        "quote",
                        "status",
                        "source",
                        "note",
                        "added_at",
                    )
                )
                or not row["text"].strip()
            ):
                _fail("PROJECTION_FACTS_INVALID")
    except factstore.FactstoreError as exc:
        raise SettingProjectionError("PROJECTION_FACTS_INVALID") from exc
    if len({row["id"] for row in facts}) != len(facts):
        _fail("PROJECTION_FACT_ID_DUPLICATE")
    fact_ids = {row["id"] for row in facts}
    if any(row["fact_id"] not in fact_ids for row in bindings):
        _fail("BINDING_FACT_NOT_FOUND")
    return {"facts": facts, "bindings": bindings, "identity": identity}


def _eligible_reason(fact: dict[str, Any]) -> str | None:
    # 是否确认只认 C4；本票不重新抽取，也不把引文待核偷换成作者未确认。
    return (
        None if fact["status"] == factstore.STATUS_CONFIRMED else "FACT_NOT_CONFIRMED"
    )


def _target(
    records: list[dict[str, Any]],
    binding: dict[str, Any],
) -> dict[str, Any] | None:
    target = binding["target"]
    name_key = NAME_FIELDS[binding["ledger"]]
    if target["entry_id"] is not None:
        matches = [row for row in records if row["id"] == target["entry_id"]]
        if not matches:
            _fail("PROJECTION_TARGET_NOT_FOUND")
        if matches[0][name_key] != target["canonical_name"]:
            _fail("PROJECTION_TARGET_NAME_MISMATCH")
    else:
        matches = [row for row in records if row[name_key] == target["canonical_name"]]
    if len(matches) > 1:
        _fail("PROJECTION_TARGET_AMBIGUOUS")
    return copy.deepcopy(matches[0]) if matches else None


def _blank(binding: dict[str, Any], fact: dict[str, Any]) -> dict[str, Any]:
    name, ledger = binding["target"]["canonical_name"], binding["ledger"]
    defaults = {
        "character": {
            "canonical_name": name,
            "aliases": [],
            "role_tag": None,
            "profile": fact["text"],
            "visibility": "AUTHOR",
            "destiny_ref": None,
            "state_timeline": [],
            "relationships": [],
            "desire_seq": [],
            "ordeal_seq": [],
            "intent_seq": [],
            "choice_seq": [],
        },
        "location": {
            "name": name,
            "aliases": [],
            "loc_type": "未分类",
            "parent_ref": None,
            "profile": fact["text"],
            "state_timeline": [],
        },
        "item": {
            "name": name,
            "item_type": "未分类",
            "first_seen": None,
            "ownership": [],
            "item_status": [],
        },
        "faction": {
            "name": name,
            "aliases": [],
            "fac_type": "未分类",
            "members": [],
            "relations": [],
            "profile": fact["text"],
        },
        "system": {
            "name": name,
            "category": "未分类",
            "rank_order": None,
            "relations": [],
            "scope": None,
            "pack_ref": None,
        },
        "world_rule": {
            "rule_text": name,
            "scope": None,
            "hardness": "advisory",
            "exceptions": [],
        },
    }
    return copy.deepcopy(defaults[ledger])


def _assert_editable(record: dict[str, Any]) -> None:
    if (
        record.get("confirm_status") != "candidate"
        or record.get("source_identity") != "draft_inferred"
    ):
        _fail("PROJECTION_TARGET_PROTECTED")


def _append_state(
    record: dict[str, Any],
    binding: dict[str, Any],
    fact: dict[str, Any],
) -> None:
    ledger, key, value = binding["ledger"], binding["state_key"], binding["value"]
    ref = fact.get("chapter_revision_ref")
    if not isinstance(ref, dict):
        _fail("PROJECTION_STORY_ANCHOR_REQUIRED")
    interval = {"start": {"chapter_revision_ref": copy.deepcopy(ref)}, "end": None}
    row: dict[str, Any] = {"story_time": interval, "evidence_refs": [fact["id"]]}
    if key == "alias" and ledger in {"character", "location", "faction"}:
        destination = "aliases"
        row["name"] = value
    elif ledger == "character" and key == "relationship":
        destination = "relationships"
        if not isinstance(value, dict) or set(value) != {"target_ref", "kind"}:
            _fail("BINDING_STATE_VALUE_INVALID")
        row.update(copy.deepcopy(value))
    elif ledger == "item" and key == "ownership":
        destination = "ownership"
        row["owner_ref"] = value
    elif ledger == "faction" and key in {"member", "relation"}:
        destination = "members" if key == "member" else "relations"
        expected = {"ch_ref", "role"} if key == "member" else {"target_ref", "kind"}
        if not isinstance(value, dict) or set(value) != expected:
            _fail("BINDING_STATE_VALUE_INVALID")
        row.update(copy.deepcopy(value))
    elif ledger in TIMELINES:
        destination, self_key = TIMELINES[ledger]
        row.update({self_key: record["id"], "state_key": key, "value": value})
    else:
        _fail("BINDING_STATE_NOT_SUPPORTED")
    record[destination].append(row)


def _record(
    existing: dict[str, Any] | None,
    binding: dict[str, Any],
    fact: dict[str, Any],
    *,
    include_state: bool = True,
) -> dict[str, Any]:
    if existing is not None:
        _assert_editable(existing)
    record = copy.deepcopy(existing) if existing is not None else _blank(binding, fact)
    if binding["kind"] == "definition":
        for key, value in (binding["value"] or {}).items():
            old = record.get(key)
            if existing is None or old == value or old is None or old == "未分类":
                record[key] = copy.deepcopy(value)
            elif key == "profile" and isinstance(value, str):
                record[key] = old if value in old.splitlines() else f"{old}\n{value}"
            elif key in {"relations", "exceptions"} and isinstance(value, list):
                record[key] = [
                    *old,
                    *[copy.deepcopy(item) for item in value if item not in old],
                ]
            else:
                _fail("PROJECTION_DEFINITION_CONFLICT")
        if existing is not None and binding["value"] is None and "profile" in record:
            if fact["text"] not in record["profile"].splitlines():
                record["profile"] += "\n" + fact["text"]
    elif include_state:
        _append_state(record, binding, fact)
    line = (
        f"[{fact['id']}] 事实：{fact['text']}；"
        f"说明：{binding['note'] or '显式绑定投影，待作者确认。'}"
    )
    old_note = record.get("note", "")
    record["note"] = (
        old_note
        if line in old_note.splitlines()
        else "\n".join(filter(None, [old_note, line]))
    )
    record.update(
        source_identity="draft_inferred",
        confirm_status="candidate",
        evidence_refs=[fact["id"]],
        story_time=None,
    )
    return record


def _validate_record(ledger: str, record: dict[str, Any]) -> None:
    spec = settingstore.LEDGERS[ledger]
    # 0 号只供内存校验自引用形状，从不交给 writer，不占号、不落盘。
    probe = settingstore._fill_record(
        spec,
        record,
        entry_id=record.get("id", spec.prefix + "0"),
        created_at=record.get("created_at", "1970-01-01T00:00:00Z"),
        updated_at=record.get("updated_at", "1970-01-01T00:00:00Z"),
        rev=record.get("rev", 1),
    )
    try:
        settingstore._validate_payload(spec, probe)
    except settingstore.SettingstoreError as exc:
        raise SettingProjectionError("PROJECTION_CONTENT_INVALID") from exc


def _read_ledgers(root: Path) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for ledger, spec in settingstore.LEDGERS.items():
        _regular_bytes(root / spec.filename)
        try:
            rows = settingstore.read_setting_records(root, ledger)
            for row in rows:
                settingstore._validate_payload(spec, row)
        except (settingstore.SettingstoreError, ValueError, OSError) as exc:
            raise SettingProjectionError("PROJECTION_SETTING_SOURCE_INVALID") from exc
        result[ledger] = rows
    return result


def _preflight(
    inputs: dict[str, Any],
    records: dict[str, list[dict[str, Any]]],
    done: dict[str, Any],
) -> None:
    facts = {row["id"]: row for row in inputs["facts"]}
    simulated = copy.deepcopy(records)
    for binding in inputs["bindings"]:
        fact = facts[binding["fact_id"]]
        if _eligible_reason(fact) is not None:
            continue
        if fact["id"] in done:
            if done[fact["id"]]["binding_sha256"] != _sha(binding) or done[fact["id"]][
                "fact_sha256"
            ] != _sha(fact):
                _fail("PROJECTION_PREVIOUS_BINDING_CONFLICT")
            continue
        ledger = binding["ledger"]
        existing = _target(simulated[ledger], binding)
        if existing is None:
            probe = _record(None, binding, fact, include_state=False)
            probe["id"] = settingstore.LEDGERS[ledger].prefix + "0"
            if binding["kind"] == "state":
                _append_state(probe, binding, fact)
        else:
            probe = _record(existing, binding, fact)
        _validate_record(ledger, probe)
        if existing is None:
            simulated[ledger].append(probe)
        else:
            simulated[ledger] = [
                probe
                if row[NAME_FIELDS[ledger]] == existing[NAME_FIELDS[ledger]]
                else row
                for row in simulated[ledger]
            ]


def _key(operation_id: str, stage: str, fact_id: str = "") -> str:
    return "sp-" + stage + ":" + _sha([operation_id, fact_id, stage])


def _saved(root: Path, operation_id: str, action: str) -> dict[str, Any] | None:
    status = planstore._operation_status_unlocked(root, operation_id)
    if status["state"] == "COMMITTED":
        row = next(
            row
            for row in planstore._operation_rows(root, operation_id)
            if row.get("phase") == "prepare"
        )
        if row.get("action") != action or not isinstance(
            row.get("receipt", {}).get("payload"), dict
        ):
            _fail("PROJECTION_OPERATION_CONFLICT")
        return copy.deepcopy(row["receipt"]["payload"])
    if status["state"] != "NOT_HAPPENED" or planstore._operation_rows(
        root, operation_id
    ):
        _fail("PROJECTION_OPERATION_NEEDS_RECOVERY")
    return None


def _memo(
    root: Path,
    operation_id: str,
    action: str,
    payload: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    with planstore._exclusive_lock(root):
        planstore._recover_pending_locked(root, timestamp=timestamp)
        previous = _saved(root, operation_id, action)
        if previous is not None:
            if previous != payload:
                _fail("PROJECTION_OPERATION_CONFLICT")
            return previous
        planstore._commit_generic_transaction_locked(
            root,
            operation_id=operation_id,
            action_name=action,
            request_sha256=_sha(payload),
            replacements={},
            appends={},
            blobs=[],
            receipt={"payload": payload},
            timestamp=timestamp,
        )
    return copy.deepcopy(payload)


@contextmanager
def _projection_lock(root: Path) -> Iterator[None]:
    # 只串行排队投影调用。单条设定提交仍由 writer 自己拿 .planstore.lock。
    path = root / ".setting_projection.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _previous_results(root: Path, operation_id: str) -> dict[str, Any]:
    rows = planstore._commit_rows(root)
    committed = {row["op"] for row in rows if row.get("phase") == "commit"}
    receipts = [
        row["receipt"]["payload"]
        for row in rows
        if row.get("phase") == "prepare"
        and row["op"] in committed
        and row.get("action") == ACTION_RECEIPT
    ]
    completed = {row["operation_id"] for row in receipts}
    for row in rows:
        if (
            row.get("phase") == "prepare"
            and row["op"] in committed
            and row.get("action") == ACTION_INPUT
        ):
            original = row["receipt"]["payload"]["operation_id"]
            if original != operation_id and original not in completed:
                _fail("PROJECTION_PREVIOUS_RUN_INCOMPLETE")
    return {
        item["fact_id"]: item
        for receipt in receipts
        for item in receipt["items"]
        if item["entry_id"] is not None and item["action"] in {"created", "appended"}
    }


def _write_step(
    root: Path,
    key: str,
    build: Callable[[], dict[str, Any]],
    timestamp: str,
) -> dict[str, Any]:
    with planstore._exclusive_lock(root):
        request = _saved(root, key, ACTION_MEMO)
    if request is None:
        request = _memo(root, key, ACTION_MEMO, build(), timestamp)
    # 重跑使用写前底稿；已回滚的子事务不能复用旧号，但父操作号不变。
    attempt = 0
    with planstore._exclusive_lock(root):
        while True:
            write_id = _key(key, "write", str(attempt))
            status = planstore._operation_status_unlocked(root, write_id)
            if status["terminal_phase"] != "rolled_back":
                break
            attempt += 1
    return settingstore.write_setting_record(
        root,
        ledger=request["ledger"],
        operation_id=write_id,
        record=request["record"],
        expected_rev=request["expected_rev"],
        timestamp=timestamp,
        actor="setting_projection",
    )


def _project_one(
    root: Path,
    operation_id: str,
    binding: dict[str, Any],
    fact: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    fact_id, ledger = fact["id"], binding["ledger"]
    route_key = _key(operation_id, "route", fact_id)
    result_key = _key(operation_id, "result", fact_id)
    with planstore._exclusive_lock(root):
        finished = _saved(root, result_key, ACTION_MEMO)
        route = _saved(root, route_key, ACTION_MEMO)
    if finished is not None:
        return finished
    if route is None:
        existing = _target(_read_ledgers(root)[ledger], binding)
        route = _memo(
            root,
            route_key,
            ACTION_MEMO,
            {"entry_id": None if existing is None else existing["id"]},
            timestamp,
        )

    def build_create() -> dict[str, Any]:
        # 再看一次名字，防止规划底稿写好后出现同名条目。
        if _target(_read_ledgers(root)[ledger], binding) is not None:
            _fail("PROJECTION_TARGET_CHANGED")
        return {
            "ledger": ledger,
            "record": _record(None, binding, fact, include_state=False),
            "expected_rev": None,
        }

    def build_append(entry_id: str) -> dict[str, Any]:
        rows = _read_ledgers(root)[ledger]
        existing = next((row for row in rows if row["id"] == entry_id), None)
        if existing is None:
            _fail("PROJECTION_TARGET_NOT_FOUND")
        return {
            "ledger": ledger,
            "record": _record(existing, binding, fact),
            "expected_rev": existing["rev"],
        }

    created = route["entry_id"] is None
    if created:
        write = _write_step(
            root, _key(operation_id, "create", fact_id), build_create, timestamp
        )
        entry_id = write["record_ref"]
        if binding["kind"] == "state":
            _write_step(
                root,
                _key(operation_id, "append", fact_id),
                lambda: build_append(entry_id),
                timestamp,
            )
    else:
        entry_id = route["entry_id"]
        _write_step(
            root,
            _key(operation_id, "append", fact_id),
            lambda: build_append(entry_id),
            timestamp,
        )
    return _memo(
        root,
        result_key,
        ACTION_MEMO,
        {
            "fact_id": fact_id,
            "ledger": ledger,
            "entry_id": entry_id,
            "action": "created" if created else "appended",
            "reason_code": None,
            "binding_sha256": _sha(binding),
            "fact_sha256": _sha(fact),
        },
        timestamp,
    )


def project_confirmed_facts(
    project_dir: str | Path | AuthorWorkspace,
    *,
    operation_id: str,
) -> dict[str, Any]:
    """把 confirmed 事实投成候选卡；也接受已认证工作区句柄，不复制其事实账。

    多条记录逐条提交，不宣称整批回滚。中断后必须用同一操作号续跑；输入变了就停。
    已完成的操作原样返回历史回执，不将这份历史回执当作当前仍有效的证明。
    """
    try:
        planstore._validate_operation_id(operation_id)
    except planstore.PlanstoreError as exc:
        raise SettingProjectionError("PROJECTION_OPERATION_ID_INVALID") from exc
    root = (
        _bound_project_dir(project_dir)
        if isinstance(project_dir, AuthorWorkspace)
        else Path(project_dir)
    )
    if not root.is_dir() or root.is_symlink():
        _fail("PROJECTION_PROJECT_NOT_FOUND")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _projection_lock(root):
        with planstore._exclusive_lock(root):
            planstore._recover_pending_locked(root, timestamp=timestamp)
            finished = _saved(root, operation_id, ACTION_RECEIPT)
            if finished is not None:
                return finished
            seed = _saved(root, _key(operation_id, "input"), ACTION_INPUT)
            done = _previous_results(root, operation_id)
        inputs = _inputs(project_dir, root)
        input_sha = _sha(inputs)
        if seed is None:
            records = _read_ledgers(root)
            binding_ids = {row["fact_id"] for row in inputs["bindings"]}
            if any(
                row["status"] == factstore.STATUS_CONFIRMED
                and row["id"] in binding_ids
                and row["id"] not in done
                for row in inputs["facts"]
            ):
                # writer 共用规划账发号。本票不另造规划账或第二套计数器。
                plan = _read_json_file(root / "plan.json", None)
                if plan is None:
                    _fail("PROJECTION_PLAN_REQUIRED")
                try:
                    planstore._validate_plan(plan)
                    for ledger, rows in records.items():
                        settingstore._assert_counter_aligned(
                            rows, settingstore.LEDGERS[ledger], plan
                        )
                except (
                    planstore.PlanstoreError,
                    settingstore.SettingstoreError,
                ) as exc:
                    raise SettingProjectionError("PROJECTION_PLAN_INVALID") from exc
            _preflight(inputs, records, done)
            seed = _memo(
                root,
                _key(operation_id, "input"),
                ACTION_INPUT,
                {
                    "operation_id": operation_id,
                    "input_sha256": input_sha,
                    "timestamp": timestamp,
                },
                timestamp,
            )
        elif seed["input_sha256"] != input_sha:
            _fail("PROJECTION_INPUT_CHANGED")
        timestamp = seed["timestamp"]
        bindings = {row["fact_id"]: row for row in inputs["bindings"]}
        items, unbound = [], []
        confirmed = [
            row
            for row in inputs["facts"]
            if row["status"] == factstore.STATUS_CONFIRMED
        ]
        for fact in inputs["facts"]:
            binding = bindings.get(fact["id"])
            if binding is None and fact["status"] != factstore.STATUS_CONFIRMED:
                continue
            reason = _eligible_reason(fact)
            if binding is None:
                unbound.append(fact["id"])
                reason = "NO_BINDING"
            if reason is not None:
                items.append(
                    {
                        "fact_id": fact["id"],
                        "ledger": None if binding is None else binding["ledger"],
                        "entry_id": None,
                        "action": "skipped",
                        "reason_code": reason,
                        "binding_sha256": None if binding is None else _sha(binding),
                        "fact_sha256": _sha(fact),
                    }
                )
            elif fact["id"] in done:
                items.append(
                    {
                        **done[fact["id"]],
                        "action": "skipped",
                        "reason_code": "ALREADY_PROJECTED",
                    }
                )
            else:
                if _sha(_inputs(project_dir, root)) != input_sha:
                    _fail("PROJECTION_INPUT_CHANGED")
                items.append(_project_one(root, operation_id, binding, fact, timestamp))
        if _sha(_inputs(project_dir, root)) != input_sha:
            _fail("PROJECTION_INPUT_CHANGED")
        written = [row for row in items if row["action"] in {"created", "appended"}]
        receipt = {
            "contract": SETTING_PROJECTION_RECEIPT,
            "shape_status": SHAPE_STATUS,
            "operation_id": operation_id,
            "status": "COMPLETED",
            "input_sha256": input_sha,
            "confirmed_fact_count": len(confirmed),
            "written_ledger_count": len({row["ledger"] for row in written}),
            "written_entry_count": len(
                {(row["ledger"], row["entry_id"]) for row in written}
            ),
            "projected_fact_count": len(written),
            "created_count": sum(row["action"] == "created" for row in items),
            "appended_count": sum(row["action"] == "appended" for row in items),
            "skipped_count": sum(row["action"] == "skipped" for row in items),
            "unbound_confirmed_count": len(unbound),
            "unbound_confirmed_fact_ids": unbound,
            "items": items,
        }
        return _memo(root, operation_id, ACTION_RECEIPT, receipt, timestamp)


__all__ = [
    "SETTING_PROJECTION_BINDING",
    "SETTING_PROJECTION_RECEIPT",
    "SHAPE_STATUS",
    "SettingProjectionError",
    "validate_setting_projection_binding",
    "validate_setting_projection_bindings",
    "read_setting_projection_bindings",
    "project_confirmed_facts",
]
