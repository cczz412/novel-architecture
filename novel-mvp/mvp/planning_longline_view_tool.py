"""当前规划账中故事线与伏笔的只读长线视图。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, NoReturn


if __package__:
    from . import planstore
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import planstore


IDENTITY = "M8_CURRENT_PLANNING_LONGLINE_VIEW"
VERSION = "v1"
SCOPE = "PLANNING_NOT_FACT"
NOTICE = (
    "这些内容是规划安排，不表示故事已经发生、伏笔已经实际兑现或读者已经知道。"
)
UNAVAILABLE = ("卷纲", "人物命运", "灵感与预计使用时机")
TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"

ENTRY_KEYS = frozenset({"version", "sha256", "plan"})
COMMON_KEYS = frozenset(
    {"id", "source_identity", "created_at", "updated_at", "rev", "note"}
)
STORYLINE_KEYS = COMMON_KEYS | {
    "name",
    "alias",
    "priority",
    "members",
    "line_status",
    "last_scene_ref",
}
HOOK_KEYS = COMMON_KEYS | {
    "content",
    "plant_refs",
    "payoff_slot_ref",
    "hook_status",
    "paid_by_ref",
    "defer_count",
    "revealed",
    "revealed_at",
    "safety_summary",
    "truth_bearing",
}
PLANT_REF_KEYS = frozenset({"ref", "note"})
HOOK_LINK_KEYS = frozenset({"hook_ref", "role"})

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
STORYLINE_ID_RE = re.compile(r"L-[0-9]{4,}\Z")
HOOK_ID_RE = re.compile(r"H-[0-9]{4,}\Z")
SCENE_ID_RE = re.compile(r"SCN-[0-9]{4,}\Z")
EVENT_ID_RE = re.compile(r"PE-[0-9]{4,}\Z")
SLOT_ID_RE = re.compile(r"S-[0-9]{4,}\Z")
# 正式存储合同只冻结 ``CH-`` 身份前缀，没有冻结编号位数。
# 现役章槽快照同时存在 CH-001 与 CH-0001，不能由这个只读消费者
# 私自收窄成四位数字。
CHARACTER_ID_RE = re.compile(r"CH-\S+\Z")


class PlanningLonglineViewError(ValueError):
    """当前规划不能安全投影成故事线／伏笔视图。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise PlanningLonglineViewError(f"{code}:{detail}" if detail else code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise PlanningLonglineViewError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _exact_keys(value: dict[str, Any], expected: frozenset[str], label: str) -> None:
    missing = sorted(expected - value.keys())
    extra = sorted(value.keys() - expected)
    if missing:
        _fail("OBJECT_FIELDS_MISSING", f"{label}:{','.join(missing)}")
    if extra:
        _fail("OBJECT_FIELDS_EXTRA", f"{label}:{','.join(extra)}")


def _string(value: Any, field: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        _fail("STRING_INVALID", field)
    return value


def _nullable_string(value: Any, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        _fail("NULLABLE_STRING_INVALID", field)
    return value


def _integer(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("INTEGER_INVALID", field)
    if minimum is not None and value < minimum:
        _fail("INTEGER_INVALID", field)
    return value


def _unique_refs(
    value: Any,
    field: str,
    pattern: re.Pattern[str],
) -> list[str]:
    if not isinstance(value, list):
        _fail("REFERENCE_LIST_INVALID", field)
    refs: list[str] = []
    for ref in value:
        if not isinstance(ref, str) or pattern.fullmatch(ref) is None:
            _fail("REFERENCE_INVALID", field)
        refs.append(ref)
    if len(refs) != len(set(refs)):
        _fail("REFERENCE_DUPLICATE", field)
    return refs


def _validate_common(
    value: dict[str, Any],
    *,
    label: str,
    id_pattern: re.Pattern[str],
) -> str:
    object_id = value.get("id")
    if not isinstance(object_id, str) or id_pattern.fullmatch(object_id) is None:
        _fail("OBJECT_ID_INVALID", label)
    if value.get("source_identity") not in {
        "author_declared",
        "draft_inferred",
        "model_suggested",
    }:
        _fail("SOURCE_IDENTITY_INVALID", object_id)
    _string(value.get("created_at"), f"{object_id}.created_at", nonempty=True)
    _string(value.get("updated_at"), f"{object_id}.updated_at", nonempty=True)
    _integer(value.get("rev"), f"{object_id}.rev", minimum=1)
    _string(value.get("note"), f"{object_id}.note")
    return object_id


def _index_ids(value: Any, label: str, pattern: re.Pattern[str]) -> set[str]:
    if not isinstance(value, list):
        _fail("PLAN_COLLECTION_INVALID", label)
    ids: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            _fail("PLAN_OBJECT_INVALID", f"{label}[{index}]")
        object_id = item.get("id")
        if not isinstance(object_id, str) or pattern.fullmatch(object_id) is None:
            _fail("PLAN_OBJECT_ID_INVALID", f"{label}[{index}]")
        ids.append(object_id)
    if len(ids) != len(set(ids)):
        _fail("PLAN_OBJECT_ID_DUPLICATE", label)
    return set(ids)


def _validate_storylines(
    value: Any,
    *,
    scene_ids: set[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(value, list):
        _fail("PLAN_COLLECTION_INVALID", "storylines")
    rows: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            _fail("PLAN_OBJECT_INVALID", f"storylines[{index}]")
        _exact_keys(raw, STORYLINE_KEYS, f"storylines[{index}]")
        storyline_id = _validate_common(
            raw,
            label=f"storylines[{index}]",
            id_pattern=STORYLINE_ID_RE,
        )
        ids.append(storyline_id)
        _string(raw.get("name"), f"{storyline_id}.name", nonempty=True)
        _nullable_string(raw.get("alias"), f"{storyline_id}.alias")
        _integer(raw.get("priority"), f"{storyline_id}.priority")
        _unique_refs(raw.get("members"), f"{storyline_id}.members", CHARACTER_ID_RE)
        if raw.get("line_status") not in {
            "active",
            "paused",
            "converged",
            "merged",
        }:
            _fail("STORYLINE_STATUS_INVALID", storyline_id)
        last_scene_ref = raw.get("last_scene_ref")
        if last_scene_ref is not None and (
            not isinstance(last_scene_ref, str)
            or SCENE_ID_RE.fullmatch(last_scene_ref) is None
            or last_scene_ref not in scene_ids
        ):
            _fail("STORYLINE_LAST_SCENE_REF_INVALID", storyline_id)
        rows.append(copy.deepcopy(raw))
    if len(ids) != len(set(ids)):
        _fail("STORYLINE_ID_DUPLICATE")
    return rows, set(ids)


def _validate_storyline_refs(plan: dict[str, Any], storyline_ids: set[str]) -> None:
    for slot in plan.get("slots", []):
        if not isinstance(slot, dict):
            _fail("PLAN_OBJECT_INVALID", "slots")
        slot_ref = slot.get("id")
        refs = _unique_refs(
            slot.get("storyline_refs"),
            f"slot[{slot_ref}].storyline_refs",
            STORYLINE_ID_RE,
        )
        if any(ref not in storyline_ids for ref in refs):
            _fail("SLOT_STORYLINE_REF_NOT_FOUND", str(slot_ref))
    for event in plan.get("events", []):
        if not isinstance(event, dict):
            _fail("PLAN_OBJECT_INVALID", "events")
        event_ref = event.get("id")
        if "storyline_ref" not in event:
            _fail("EVENT_STORYLINE_REF_MISSING", str(event_ref))
        storyline_ref = event.get("storyline_ref")
        if storyline_ref is not None and (
            not isinstance(storyline_ref, str)
            or STORYLINE_ID_RE.fullmatch(storyline_ref) is None
            or storyline_ref not in storyline_ids
        ):
            _fail("EVENT_STORYLINE_REF_NOT_FOUND", str(event_ref))


def _hook_links_by_event(
    events: Any,
    hook_ids: set[str],
) -> dict[str, list[dict[str, str]]]:
    if not isinstance(events, list):
        _fail("PLAN_COLLECTION_INVALID", "events")
    result: dict[str, list[dict[str, str]]] = {}
    for event in events:
        if not isinstance(event, dict):
            _fail("PLAN_OBJECT_INVALID", "events")
        event_ref = str(event.get("id"))
        links = event.get("hook_links")
        if links is None:
            # 旧的无伏笔事件不会阻止只读投影；一旦给出引用则严格闭合。
            result[event_ref] = []
            continue
        if not isinstance(links, list):
            _fail("EVENT_HOOK_LINKS_INVALID", event_ref)
        validated: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for index, link in enumerate(links):
            if not isinstance(link, dict):
                _fail("EVENT_HOOK_LINK_INVALID", f"{event_ref}:{index}")
            _exact_keys(link, HOOK_LINK_KEYS, f"event[{event_ref}].hook_links[{index}]")
            hook_ref = link.get("hook_ref")
            role = link.get("role")
            if (
                not isinstance(hook_ref, str)
                or HOOK_ID_RE.fullmatch(hook_ref) is None
                or hook_ref not in hook_ids
            ):
                _fail("EVENT_HOOK_REF_NOT_FOUND", event_ref)
            if role not in {"plant", "payoff"}:
                _fail("EVENT_HOOK_ROLE_INVALID", event_ref)
            identity = (hook_ref, role)
            if identity in seen:
                _fail("EVENT_HOOK_LINK_DUPLICATE", event_ref)
            seen.add(identity)
            validated.append({"hook_ref": hook_ref, "role": role})
        result[event_ref] = validated
    return result


def _validate_hooks(
    value: Any,
    *,
    slot_ids: set[str],
    scene_ids: set[str],
    event_ids: set[str],
    events: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("PLAN_COLLECTION_INVALID", "hooks")
    raw_ids: list[str] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            _fail("PLAN_OBJECT_INVALID", f"hooks[{index}]")
        hook_id = raw.get("id")
        if not isinstance(hook_id, str) or HOOK_ID_RE.fullmatch(hook_id) is None:
            _fail("OBJECT_ID_INVALID", f"hooks[{index}]")
        raw_ids.append(hook_id)
    if len(raw_ids) != len(set(raw_ids)):
        _fail("HOOK_ID_DUPLICATE")
    hook_ids = set(raw_ids)
    links_by_event = _hook_links_by_event(events, hook_ids)

    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        _exact_keys(raw, HOOK_KEYS, f"hooks[{index}]")
        hook_id = _validate_common(
            raw,
            label=f"hooks[{index}]",
            id_pattern=HOOK_ID_RE,
        )
        _string(raw.get("content"), f"{hook_id}.content", nonempty=True)
        plants = raw.get("plant_refs")
        if not isinstance(plants, list):
            _fail("HOOK_PLANT_REFS_INVALID", hook_id)
        plant_identities: list[str] = []
        for plant_index, plant in enumerate(plants):
            if not isinstance(plant, dict):
                _fail("HOOK_PLANT_REF_INVALID", f"{hook_id}:{plant_index}")
            _exact_keys(
                plant,
                PLANT_REF_KEYS,
                f"hook[{hook_id}].plant_refs[{plant_index}]",
            )
            ref = plant.get("ref")
            if not isinstance(ref, str) or (
                ref not in event_ids and ref not in scene_ids
            ):
                _fail("HOOK_PLANT_TARGET_NOT_FOUND", hook_id)
            _string(plant.get("note"), f"{hook_id}.plant_refs.note")
            plant_identities.append(ref)
        if len(plant_identities) != len(set(plant_identities)):
            _fail("HOOK_PLANT_REF_DUPLICATE", hook_id)

        payoff_slot_ref = raw.get("payoff_slot_ref")
        if payoff_slot_ref is not None and (
            not isinstance(payoff_slot_ref, str)
            or SLOT_ID_RE.fullmatch(payoff_slot_ref) is None
            or payoff_slot_ref not in slot_ids
        ):
            _fail("HOOK_PAYOFF_SLOT_REF_NOT_FOUND", hook_id)
        hook_status = raw.get("hook_status")
        if hook_status not in {"open", "paid", "voided"}:
            _fail("HOOK_STATUS_INVALID", hook_id)
        paid_by_ref = raw.get("paid_by_ref")
        if paid_by_ref is not None and (
            not isinstance(paid_by_ref, str)
            or EVENT_ID_RE.fullmatch(paid_by_ref) is None
            or paid_by_ref not in event_ids
        ):
            _fail("HOOK_PAID_BY_REF_NOT_FOUND", hook_id)
        if hook_status == "paid" and paid_by_ref is None:
            _fail("HOOK_PAID_EVENT_REQUIRED", hook_id)
        if hook_status == "paid" and not any(
            link == {"hook_ref": hook_id, "role": "payoff"}
            for link in links_by_event.get(str(paid_by_ref), [])
        ):
            _fail("HOOK_PAID_EVENT_LINK_MISSING", hook_id)

        _integer(raw.get("defer_count"), f"{hook_id}.defer_count", minimum=0)
        if not isinstance(raw.get("revealed"), bool):
            _fail("HOOK_REVEALED_INVALID", hook_id)
        revealed_at = raw.get("revealed_at")
        if revealed_at is not None and (
            not isinstance(revealed_at, str)
            or (revealed_at not in slot_ids and revealed_at not in scene_ids)
        ):
            _fail("HOOK_REVEALED_AT_NOT_FOUND", hook_id)
        if raw.get("revealed") is True and revealed_at is None:
            _fail("HOOK_REVEALED_AT_REQUIRED", hook_id)
        _string(
            raw.get("safety_summary"),
            f"{hook_id}.safety_summary",
            nonempty=True,
        )
        if raw.get("truth_bearing") not in {"primary", "shadow", "handed_over"}:
            _fail("HOOK_TRUTH_BEARING_INVALID", hook_id)
        rows.append(copy.deepcopy(raw))
    return rows


def execute(plan_entry: dict[str, Any]) -> dict[str, Any]:
    """从一份带水位的 current plan 生成只读规划视图。"""
    if not isinstance(plan_entry, dict):
        _fail("PLAN_ENTRY_NOT_OBJECT")
    _exact_keys(plan_entry, ENTRY_KEYS, "plan_entry")
    source_version = _integer(
        plan_entry.get("version"), "source_plan_version", minimum=1
    )
    source_sha = plan_entry.get("sha256")
    if not isinstance(source_sha, str) or SHA256_RE.fullmatch(source_sha) is None:
        _fail("SOURCE_PLAN_SHA_INVALID")
    plan = copy.deepcopy(plan_entry.get("plan"))
    if not isinstance(plan, dict):
        _fail("PLAN_OBJECT_REQUIRED")
    if hashlib.sha256(_canonical_bytes(plan)).hexdigest() != source_sha:
        _fail("SOURCE_PLAN_SHA_MISMATCH")
    try:
        planstore._validate_plan(plan)
    except planstore.PlanstoreError as exc:
        _fail("PLAN_INVALID", str(exc))

    volumes = plan.get("volumes")
    if not isinstance(volumes, list):
        _fail("PLAN_COLLECTION_INVALID", "volumes")
    if volumes:
        _fail("VOLUMES_NOT_SUPPORTED")

    slot_ids = _index_ids(plan.get("slots"), "slots", SLOT_ID_RE)
    scene_ids = _index_ids(plan.get("scenes"), "scenes", SCENE_ID_RE)
    event_ids = _index_ids(plan.get("events"), "events", EVENT_ID_RE)
    storylines, storyline_ids = _validate_storylines(
        plan.get("storylines"), scene_ids=scene_ids
    )
    _validate_storyline_refs(plan, storyline_ids)
    hooks = _validate_hooks(
        plan.get("hooks"),
        slot_ids=slot_ids,
        scene_ids=scene_ids,
        event_ids=event_ids,
        events=plan.get("events"),
    )

    return {
        "identity": IDENTITY,
        "version": VERSION,
        "scope": SCOPE,
        "notice": NOTICE,
        "source_plan_version": source_version,
        "source_plan_sha256": source_sha,
        "status_semantics": {
            "storyline_status": "只表示规划中的故事线状态。",
            "hook_status_paid": "只表示已经安排回收，不表示实际兑现。",
            "hook_revealed": "只表示规划中安排揭示，不表示读者实际已知。",
        },
        "storylines": storylines,
        "hooks": hooks,
        "unavailable": list(UNAVAILABLE),
    }


def _load_input(input_path: str | None) -> dict[str, Any]:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE")
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanningLonglineViewError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("INPUT_OBJECT_REQUIRED")
    return value


def _same_input_output(input_path: str | None, output_path: str | None) -> bool:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return False
    source = Path(input_path)
    target = Path(output_path)
    if source.resolve() == target.resolve():
        return True
    if source.exists() and target.exists():
        return os.path.samefile(source, target)
    return False


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(output_path: str | None, value: dict[str, Any]) -> None:
    payload = _canonical_bytes(value)
    if output_path in {None, "-"}:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        return
    path = Path(output_path)
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY")
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="当前规划的故事线／伏笔只读视图")
    parser.add_argument("--input", default="-", help="输入 plan 快照 JSON")
    parser.add_argument("--output", default="-", help="输出视图 JSON")
    args = parser.parse_args(argv)
    try:
        if _same_input_output(args.input, args.output):
            _fail("OUTPUT_MUST_NOT_OVERWRITE_INPUT")
        result = execute(_load_input(args.input))
        _write_atomic(args.output, result)
    except (OSError, PlanningLonglineViewError) as exc:
        print(f"PLANNING_LONGLINE_VIEW_ERROR:{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
