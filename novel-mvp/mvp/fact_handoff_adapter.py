"""事实分支的薄交接适配器：M4 输出 -> 顺序 M5 -> M6/M7/M9 请求。

核心 ``execute`` 只处理对象。它不执行 M6 查询、M7 体检或 M9 概览，
也不读取项目、作者或工作区；文件读写只存在于本文件的 CLI 适配层。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, TextIO

try:
    from . import check_tool, factstore, overview, review_tool
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import check_tool  # type: ignore[no-redef]
    import factstore  # type: ignore[no-redef]
    import overview  # type: ignore[no-redef]
    import review_tool  # type: ignore[no-redef]


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"
REQUEST_KEYS = frozenset(
    {
        "m4_output",
        "author_actions",
        "current_revision_refs",
        "m6_query",
        "m7_check",
        "m9_config",
    }
)
M4_OUTPUT_KEYS = frozenset({"facts", "added_fact_refs", "added_count"})
ACTION_ITEM_KEYS = frozenset({"action", "chapter_revision_ref", "decided_at"})
M7_CHECK_KEYS = frozenset(
    {"project_display_name", "generated_at", "check_config"}
)
M7_CONFIG_KEYS = frozenset({"scope_name", "scope_kind", "kinds"})
M9_CONFIG_KEYS = frozenset({"generated_at", "provider_bindings_by_chapter"})
REVISION_REF_KEYS = frozenset(
    {"chapter_id", "revision_no", "revision_text_sha256"}
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FactHandoffAdapterError(ValueError):
    """交接输入不能安全组成一套完整的下游请求。"""


def _clean_string(value: object, *, reason: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FactHandoffAdapterError(reason)
    return value


def _valid_revision_ref(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == REVISION_REF_KEYS
        and isinstance(value.get("chapter_id"), str)
        and bool(value["chapter_id"])
        and isinstance(value.get("revision_no"), int)
        and not isinstance(value["revision_no"], bool)
        and value["revision_no"] >= 1
        and isinstance(value.get("revision_text_sha256"), str)
        and SHA256_RE.fullmatch(value["revision_text_sha256"]) is not None
    )


def _current_revision_index(raw_refs: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_refs, list) or not raw_refs:
        raise FactHandoffAdapterError("CURRENT_REVISION_REFS_MUST_BE_NONEMPTY_LIST")
    result: dict[str, dict[str, Any]] = {}
    for index, raw_ref in enumerate(raw_refs, start=1):
        if not _valid_revision_ref(raw_ref):
            raise FactHandoffAdapterError(f"CURRENT_REVISION_REF_INVALID:{index}")
        chapter_id = raw_ref["chapter_id"]
        if chapter_id in result:
            raise FactHandoffAdapterError(f"CURRENT_REVISION_REF_DUPLICATE:{chapter_id}")
        result[chapter_id] = copy.deepcopy(raw_ref)
    return result


def _validate_m4_output(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, dict) or set(raw) != M4_OUTPUT_KEYS:
        raise FactHandoffAdapterError("M4_OUTPUT_SHAPE_INVALID")
    facts = factstore.validate_c4_v1_snapshot(raw["facts"])
    if not facts:
        raise FactHandoffAdapterError("M4_OUTPUT_FACTS_EMPTY")
    added_refs = raw["added_fact_refs"]
    added_count = raw["added_count"]
    if (
        not isinstance(added_refs, list)
        or any(not isinstance(ref, str) for ref in added_refs)
        or len(added_refs) != len(set(added_refs))
        or not isinstance(added_count, int)
        or isinstance(added_count, bool)
        or added_count != len(added_refs)
    ):
        raise FactHandoffAdapterError("M4_OUTPUT_ADDED_METADATA_INVALID")
    by_id = {fact["id"]: fact for fact in facts}
    unknown = sorted(set(added_refs) - by_id.keys())
    if unknown:
        raise FactHandoffAdapterError(f"M4_OUTPUT_ADDED_FACT_UNKNOWN:{','.join(unknown)}")
    not_extracted = sorted(
        ref for ref in added_refs if by_id[ref]["status"] != "extracted"
    )
    if not_extracted:
        raise FactHandoffAdapterError(
            f"M4_OUTPUT_ADDED_FACT_NOT_EXTRACTED:{','.join(not_extracted)}"
        )
    return facts


def _validate_facts_are_current(
    facts: list[dict[str, Any]],
    current_by_chapter: dict[str, dict[str, Any]],
) -> None:
    fact_chapters = {fact["chapter_id"] for fact in facts}
    current_chapters = set(current_by_chapter)
    missing = sorted(fact_chapters - current_chapters)
    extra = sorted(current_chapters - fact_chapters)
    if missing:
        raise FactHandoffAdapterError(
            f"CURRENT_REVISION_REF_MISSING_FOR_CHAPTER:{','.join(missing)}"
        )
    if extra:
        raise FactHandoffAdapterError(
            f"CURRENT_REVISION_REF_WITHOUT_FACTS:{','.join(extra)}"
        )
    for fact in facts:
        expected = current_by_chapter[fact["chapter_id"]]
        if fact["chapter_revision_ref"] != expected:
            raise FactHandoffAdapterError(f"FACT_NOT_AT_CURRENT_REVISION:{fact['id']}")
        anchor = fact.get("anchor_ref")
        if (
            fact.get("anchor_state") != "VERIFIED"
            or fact.get("recheck") is not None
            or not isinstance(anchor, dict)
            or any(anchor.get(key) != expected[key] for key in REVISION_REF_KEYS)
        ):
            raise FactHandoffAdapterError(f"FACT_NOT_CURRENT_VERIFIED:{fact['id']}")


def _validate_author_actions(
    raw_actions: object,
    *,
    facts_by_id: dict[str, dict[str, Any]],
    current_by_chapter: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(raw_actions, list) or not raw_actions:
        raise FactHandoffAdapterError("AUTHOR_ACTIONS_MUST_BE_NONEMPTY_LIST")
    actions: list[dict[str, Any]] = []
    seen_operations: set[str] = set()
    for index, raw_item in enumerate(raw_actions, start=1):
        if not isinstance(raw_item, dict) or set(raw_item) != ACTION_ITEM_KEYS:
            raise FactHandoffAdapterError(f"AUTHOR_ACTION_ITEM_SHAPE_INVALID:{index}")
        action = review_tool.validate_review_action(raw_item["action"])
        operation_id = action["operation_id"]
        if operation_id in seen_operations:
            raise FactHandoffAdapterError(f"DUPLICATE_OPERATION_ID:{operation_id}")
        seen_operations.add(operation_id)
        if action["fact_ref"] not in facts_by_id:
            raise FactHandoffAdapterError(f"UNKNOWN_ACTION_FACT:{action['fact_ref']}")
        revision_ref = raw_item["chapter_revision_ref"]
        if not _valid_revision_ref(revision_ref):
            raise FactHandoffAdapterError(f"ACTION_REVISION_REF_INVALID:{index}")
        current_ref = current_by_chapter.get(revision_ref["chapter_id"])
        if current_ref is None or revision_ref != current_ref:
            raise FactHandoffAdapterError(
                f"ACTION_REVISION_NOT_CURRENT:{action['fact_ref']}"
            )
        target_fact = facts_by_id[action["fact_ref"]]
        if revision_ref != target_fact["chapter_revision_ref"]:
            raise FactHandoffAdapterError(
                f"ACTION_REVISION_FACT_MISMATCH:{action['fact_ref']}"
            )
        decided_at = _clean_string(
            raw_item["decided_at"], reason=f"ACTION_DECIDED_AT_INVALID:{index}"
        )
        actions.append(
            {
                "action": action,
                "chapter_revision_ref": copy.deepcopy(revision_ref),
                "decided_at": decided_at,
            }
        )
    return actions


def _validate_m7_check(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != M7_CHECK_KEYS:
        raise FactHandoffAdapterError("M7_CHECK_SHAPE_INVALID")
    project = _clean_string(
        raw["project_display_name"], reason="M7_PROJECT_DISPLAY_NAME_INVALID"
    )
    generated_at = _clean_string(
        raw["generated_at"], reason="M7_GENERATED_AT_INVALID"
    )
    config = raw["check_config"]
    if not isinstance(config, dict) or set(config) != M7_CONFIG_KEYS:
        raise FactHandoffAdapterError("M7_CHECK_CONFIG_SHAPE_INVALID")
    if not isinstance(config["scope_name"], str) or not config["scope_name"].strip():
        raise FactHandoffAdapterError("M7_SCOPE_NAME_INVALID")
    if config["scope_kind"] not in check_tool.SCOPE_KINDS:
        raise FactHandoffAdapterError("M7_SCOPE_KIND_INVALID")
    kinds = config["kinds"]
    if (
        not isinstance(kinds, list)
        or not kinds
        or any(kind not in check_tool.KINDS for kind in kinds)
        or any(not isinstance(kind, str) for kind in kinds)
        or len(kinds) != len(set(kinds))
    ):
        raise FactHandoffAdapterError("M7_KINDS_INVALID")
    return {
        "project": project,
        "generated_at": generated_at,
        "check_config": copy.deepcopy(config),
    }


def _validate_m9_config(raw: object) -> tuple[str, dict[str, object]]:
    if not isinstance(raw, dict) or set(raw) != M9_CONFIG_KEYS:
        raise FactHandoffAdapterError("M9_CONFIG_SHAPE_INVALID")
    generated_at = _clean_string(
        raw["generated_at"], reason="M9_GENERATED_AT_INVALID"
    )
    bindings = raw["provider_bindings_by_chapter"]
    if not isinstance(bindings, dict):
        raise FactHandoffAdapterError("M9_PROVIDER_BINDINGS_NOT_OBJECT")
    for chapter_id, binding in bindings.items():
        if not isinstance(chapter_id, str) or not chapter_id:
            raise FactHandoffAdapterError("M9_PROVIDER_BINDING_CHAPTER_INVALID")
        if not isinstance(binding, (str, dict)):
            raise FactHandoffAdapterError(
                f"M9_PROVIDER_BINDING_INVALID:{chapter_id}"
            )
    return generated_at, copy.deepcopy(bindings)


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """顺序执行明确 M5 动作，再组装三条只读事实消费请求。"""
    if not isinstance(request, dict):
        raise FactHandoffAdapterError("REQUEST_NOT_OBJECT")
    missing = sorted(REQUEST_KEYS - request.keys())
    extra = sorted(request.keys() - REQUEST_KEYS)
    if missing:
        raise FactHandoffAdapterError(f"REQUEST_MISSING_FIELDS:{','.join(missing)}")
    if extra:
        raise FactHandoffAdapterError(f"REQUEST_EXTRA_FIELDS:{','.join(extra)}")

    facts = _validate_m4_output(request["m4_output"])
    current_by_chapter = _current_revision_index(request["current_revision_refs"])
    _validate_facts_are_current(facts, current_by_chapter)
    actions = _validate_author_actions(
        request["author_actions"],
        facts_by_id={fact["id"]: fact for fact in facts},
        current_by_chapter=current_by_chapter,
    )
    query = _clean_string(request["m6_query"], reason="M6_QUERY_INVALID")
    m7_parts = _validate_m7_check(request["m7_check"])
    m9_generated_at, provider_bindings = _validate_m9_config(request["m9_config"])

    state: dict[str, Any] = {
        "snapshot_version": 1,
        "snapshot_sha256": factstore.c4_snapshot_sha256(facts),
        "facts": copy.deepcopy(facts),
    }
    for item in actions:
        current_sha = factstore.c4_snapshot_sha256(state["facts"])
        review_request = {
            "snapshot_version": state["snapshot_version"],
            "expected_snapshot_version": state["snapshot_version"],
            "expected_snapshot_sha256": current_sha,
            "facts": copy.deepcopy(state["facts"]),
            "chapter_revision_ref": copy.deepcopy(item["chapter_revision_ref"]),
            "action": copy.deepcopy(item["action"]),
            "decided_at": item["decided_at"],
        }
        state = review_tool.execute(review_request)
        if state["snapshot_sha256"] != factstore.c4_snapshot_sha256(state["facts"]):
            raise FactHandoffAdapterError("M5_RESULT_SNAPSHOT_SHA_MISMATCH")

    reviewed_facts = factstore.validate_c4_v1_snapshot(state["facts"])
    _validate_facts_are_current(reviewed_facts, current_by_chapter)
    current_refs = [
        copy.deepcopy(current_by_chapter[chapter_id])
        for chapter_id in sorted(current_by_chapter)
    ]
    m6_request = {
        "query": query,
        "facts": copy.deepcopy(reviewed_facts),
        "current_revision_refs": copy.deepcopy(current_refs),
    }
    m7_request = {
        **m7_parts,
        "facts": copy.deepcopy(reviewed_facts),
        "current_revision_refs": copy.deepcopy(current_refs),
    }

    facts_by_chapter: dict[str, list[dict[str, Any]]] = {}
    for fact in reviewed_facts:
        facts_by_chapter.setdefault(fact["chapter_id"], []).append(fact)
    if set(provider_bindings) != set(facts_by_chapter):
        missing_bindings = sorted(set(facts_by_chapter) - set(provider_bindings))
        extra_bindings = sorted(set(provider_bindings) - set(facts_by_chapter))
        details = [
            *(f"missing={chapter}" for chapter in missing_bindings),
            *(f"extra={chapter}" for chapter in extra_bindings),
        ]
        raise FactHandoffAdapterError(
            f"M9_PROVIDER_BINDINGS_CHAPTER_MISMATCH:{','.join(details)}"
        )

    source_revision = f"m5:v{state['snapshot_version']}:{state['snapshot_sha256']}"
    m9_requests_by_chapter: dict[str, dict[str, Any]] = {}
    for chapter_id in sorted(facts_by_chapter):
        m9_request = {
            "facts": copy.deepcopy(facts_by_chapter[chapter_id]),
            "current_revision_ref": copy.deepcopy(current_by_chapter[chapter_id]),
            "source_revision": source_revision,
            "generated_at": m9_generated_at,
        }
        stable_key = overview.provider_key_for_request(m9_request)
        binding = provider_bindings[chapter_id]
        if isinstance(binding, str):
            if binding != stable_key:
                raise FactHandoffAdapterError(
                    f"M9_PROVIDER_STABLE_KEY_MISMATCH:{chapter_id}"
                )
        elif set(binding) != overview.PROVIDER_RESULT_KEYS:
            raise FactHandoffAdapterError(
                f"M9_PROVIDER_RESPONSE_SHAPE_INVALID:{chapter_id}"
            )
        m9_requests_by_chapter[chapter_id] = m9_request

    return {
        "reviewed_snapshot": copy.deepcopy(state),
        "m6_request": m6_request,
        "m7_request": m7_request,
        "m9_requests_by_chapter": m9_requests_by_chapter,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise FactHandoffAdapterError(f"FILE_NOT_UTF8:{path}") from exc
    except json.JSONDecodeError as exc:
        raise FactHandoffAdapterError(f"FILE_NOT_JSON:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise FactHandoffAdapterError("REQUEST_NOT_OBJECT")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    if not path.parent.is_dir():
        raise FactHandoffAdapterError(f"OUTPUT_PARENT_NOT_FOUND:{path.parent}")
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def _local_file(raw: str, *, label: str) -> Path:
    if raw == "-":
        raise FactHandoffAdapterError(f"{label}_MUST_BE_LOCAL_FILE")
    return Path(raw)


def main(
    argv: list[str] | None = None,
    *,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="事实分支 LOCAL_FILESYSTEM_ONLY 薄交接适配器"
    )
    parser.add_argument("--input", required=True, help="本地单文件输入 JSON")
    parser.add_argument("--output", required=True, help="本地单文件输出 JSON")
    args = parser.parse_args(argv)
    stderr = stderr or sys.stderr
    try:
        input_path = _local_file(args.input, label="INPUT")
        output_path = _local_file(args.output, label="OUTPUT")
        result = execute(_read_json(input_path))
        _write_json_atomic(output_path, result)
    except (
        FactHandoffAdapterError,
        factstore.FactstoreError,
        overview.OverviewError,
        OSError,
    ) as exc:
        stderr.write(f"FACT_HANDOFF_ADAPTER_REJECTED:{exc}\n")
        stderr.flush()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
