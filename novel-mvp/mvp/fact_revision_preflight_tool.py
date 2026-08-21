"""预计算外来道同章修订对完整 C4 事实快照的证据影响。

本工具只产出非正式 prototype。它不写 C11、C1、事实账或规划账，也不把
预演结果冒充已经提交。输入输出路径只存在于 LOCAL_FILESYSTEM_ONLY CLI。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


if __package__:
    from . import external_chapter_route_tool, factstore
else:  # 允许直接运行 python novel-mvp/mvp/fact_revision_preflight_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import external_chapter_route_tool, factstore


PROTOTYPE_IDENTITY = "FACT_REVISION_MIGRATION_PREFLIGHT_PROTOTYPE_R01"
REQUEST_KEYS = {
    "old_chapter",
    "new_chapter",
    "facts",
    "operation_id",
    "flagged_at",
    "external_route_request",
}
RESULT_KEYS = {
    "identity",
    "prototype",
    "operation_id",
    "flagged_at",
    "source",
    "effects",
    "proposed_facts",
    "summary",
    "writes",
    "prototype_sha256",
}
SOURCE_KEYS = {
    "old_chapter",
    "new_chapter",
    "source_facts",
    "old_chapter_revision_ref",
    "new_chapter_revision_ref",
    "facts_snapshot_sha256",
    "external_route_request",
    "external_route_receipt",
}
WRITES = {"c11": "none", "c1": "none", "facts": "none", "plan": "none"}
COORDINATE_BASIS = factstore.ANCHOR_COORDINATE_BASIS
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
class FactRevisionPreflightError(ValueError):
    """输入不足以做确定性证据迁移，或本地文件适配不安全。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise FactRevisionPreflightError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise FactRevisionPreflightError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validated_chapter(value: object, label: str) -> dict[str, Any]:
    try:
        chapter = copy.deepcopy(
            factstore._validate_c11_object(value, "C1_CHAPTER_DOC")
        )
    except factstore.FactstoreError as exc:
        raise FactRevisionPreflightError(f"{label}_INVALID:{exc}") from exc
    revision_ref = chapter["chapter_revision_ref"]
    if revision_ref["chapter_id"] != chapter["id"]:
        _fail(f"{label}_REVISION_CHAPTER_MISMATCH")
    if revision_ref["revision_text_sha256"] != _text_sha256(chapter["text"]):
        _fail(f"{label}_REVISION_SHA_MISMATCH")
    return chapter


def _validated_request(
    request: object,
) -> tuple[
    str,
    str,
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    operation_id = request["operation_id"]
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("OPERATION_ID_INVALID")
    flagged_at = request["flagged_at"]
    if not isinstance(flagged_at, str) or not flagged_at:
        _fail("FLAGGED_AT_INVALID")

    old_chapter = _validated_chapter(request["old_chapter"], "OLD_CHAPTER")
    new_chapter = _validated_chapter(request["new_chapter"], "NEW_CHAPTER")
    old_ref = old_chapter["chapter_revision_ref"]
    new_ref = new_chapter["chapter_revision_ref"]
    if old_chapter["id"] != new_chapter["id"]:
        _fail("CHAPTER_ID_CHANGED")
    if new_ref["revision_no"] != old_ref["revision_no"] + 1:
        _fail("REVISION_MUST_INCREMENT_BY_ONE")

    route_request = request["external_route_request"]
    if not isinstance(route_request, dict):
        _fail("EXTERNAL_ROUTE_REQUEST_REQUIRED")
    try:
        route_receipt = external_chapter_route_tool.execute(route_request)
    except external_chapter_route_tool.ExternalChapterRouteError as exc:
        raise FactRevisionPreflightError(f"EXTERNAL_ROUTE_INVALID:{exc}") from exc
    if route_request.get("chapter_doc") != old_chapter:
        _fail("EXTERNAL_ROUTE_OLD_CHAPTER_MISMATCH")
    if (
        route_receipt
        != {
            "identity": external_chapter_route_tool.RECEIPT_IDENTITY,
            "accepted": True,
            "source_kind": external_chapter_route_tool.SOURCE_KIND,
            "chapter_id": old_chapter["id"],
            "chapter_revision_ref": copy.deepcopy(old_ref),
            "next_station": external_chapter_route_tool.NEXT_STATION,
            "writes": [],
        }
    ):
        _fail("EXTERNAL_ROUTE_RECEIPT_INVALID")
    try:
        facts = factstore.validate_c4_v1_snapshot(request["facts"])
    except factstore.FactstoreError as exc:
        raise FactRevisionPreflightError(f"C4_SNAPSHOT_INVALID:{exc}") from exc

    ledger = route_request["chapter_revision_ledger"]
    historical_refs = {
        row["revision_no"]: {
            "chapter_id": ledger["chapter_id"],
            "revision_no": row["revision_no"],
            "revision_text_sha256": row["text_sha256"],
        }
        for row in ledger["revisions"]
    }

    for fact in facts:
        if fact["chapter_id"] != old_chapter["id"]:
            continue
        fact_ref = fact["chapter_revision_ref"]
        if fact["status"] != "needs_recheck":
            if fact_ref != old_ref:
                _fail(f"TARGET_FACT_REVISION_MISMATCH:{fact['id']}")
        else:
            recheck = fact["recheck"]
            historical_ref = historical_refs.get(fact_ref["revision_no"])
            if (
                fact_ref["chapter_id"] != old_chapter["id"]
                or fact_ref["revision_no"] > old_ref["revision_no"]
                or historical_ref is None
                or fact_ref != historical_ref
                or recheck["from_revision_no"] != fact_ref["revision_no"]
                or recheck["from_revision_no"] >= recheck["target_revision_no"]
                or recheck["target_revision_no"] > old_ref["revision_no"]
            ):
                _fail(f"TARGET_NEEDS_RECHECK_LINEAGE_INVALID:{fact['id']}")
        if (
            fact["anchor_state"] == "VERIFIED"
            and fact_ref["revision_no"] == old_ref["revision_no"]
        ):
            anchor = fact["anchor_ref"]
            start, end = anchor["start"], anchor["end"]
            if old_chapter["text"][start:end] != fact["quote"]:
                _fail(f"TARGET_FACT_OLD_ANCHOR_SLICE_MISMATCH:{fact['id']}")
            if anchor["revision_text_sha256"] != old_ref["revision_text_sha256"]:
                _fail(f"TARGET_FACT_OLD_ANCHOR_SHA_MISMATCH:{fact['id']}")
    return (
        operation_id,
        flagged_at,
        old_chapter,
        new_chapter,
        facts,
        copy.deepcopy(route_request),
        copy.deepcopy(route_receipt),
    )


def _match_positions(text: str, quote: str) -> list[int]:
    """返回所有逐字起点，包含彼此重叠的命中。"""
    if not quote:
        return []
    positions: list[int] = []
    cursor = 0
    while cursor <= len(text) - len(quote):
        start = text.find(quote, cursor)
        if start < 0:
            break
        positions.append(start)
        cursor = start + 1
    return positions


def _anchor_for(
    revision_ref: dict[str, Any],
    quote: str,
    start: int,
) -> dict[str, Any]:
    return {
        **copy.deepcopy(revision_ref),
        "coordinate_basis": COORDINATE_BASIS,
        "start": start,
        "end": start + len(quote),
        "slice_sha256": _text_sha256(quote),
    }


def _effect(
    before: dict[str, Any],
    after: dict[str, Any],
    effect: str,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "fact_id": before["id"],
        "chapter_id": before["chapter_id"],
        "effect": effect,
        "status_before": before["status"],
        "status_after": after["status"],
        "anchor_state_before": before["anchor_state"],
        "anchor_state_after": after["anchor_state"],
        "reason": reason,
    }


def _migrate_target_fact(
    fact: dict[str, Any],
    old_chapter: dict[str, Any],
    new_chapter: dict[str, Any],
    flagged_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(fact)
    if fact["status"] == "needs_recheck":
        return result, _effect(
            fact,
            result,
            "unchanged_already_needs_recheck",
            fact["recheck"]["reason"],
        )

    old_text = old_chapter["text"]
    new_text = new_chapter["text"]
    new_ref = new_chapter["chapter_revision_ref"]
    quote = fact["quote"]
    if fact["anchor_state"] == "VERIFIED":
        anchor = fact["anchor_ref"]
        quote = old_text[anchor["start"] : anchor["end"]]
        new_positions = _match_positions(new_text, quote)
        reason = (
            "evidence_gone" if not new_positions else "anchor_ambiguous"
        )
    else:
        old_positions = _match_positions(old_text, quote)
        new_positions = _match_positions(new_text, quote)
        reason = "legacy_anchor_unverified"
        if len(old_positions) != 1:
            new_positions = []

    if len(new_positions) == 1:
        result["chapter_revision_ref"] = copy.deepcopy(new_ref)
        result["anchor_ref"] = _anchor_for(new_ref, quote, new_positions[0])
        result["anchor_state"] = "VERIFIED"
        result["recheck"] = None
        return result, _effect(fact, result, "revision_advanced", None)

    result["status"] = "needs_recheck"
    result["recheck"] = {
        "previous_status": fact["status"],
        "reason": reason,
        "from_revision_no": fact["chapter_revision_ref"]["revision_no"],
        "target_revision_no": new_ref["revision_no"],
        "flagged_at": flagged_at,
    }
    return result, _effect(fact, result, "needs_recheck", reason)


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """纯对象预演；任何一条输入坏掉就整批拒绝，不返回半份结果。"""
    (
        operation_id,
        flagged_at,
        old_chapter,
        new_chapter,
        facts,
        route_request,
        route_receipt,
    ) = _validated_request(request)
    chapter_id = old_chapter["id"]
    proposed_facts: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []
    for fact in facts:
        if fact["chapter_id"] != chapter_id:
            proposed = copy.deepcopy(fact)
            effect = _effect(
                fact,
                proposed,
                "unchanged_other_chapter",
                None,
            )
        else:
            proposed, effect = _migrate_target_fact(
                fact,
                old_chapter,
                new_chapter,
                flagged_at,
            )
        proposed_facts.append(proposed)
        effects.append(effect)

    try:
        proposed_facts = factstore.validate_c4_v1_snapshot(proposed_facts)
    except factstore.FactstoreError as exc:
        raise FactRevisionPreflightError(
            f"PROPOSED_C4_SNAPSHOT_INVALID:{exc}"
        ) from exc
    if [fact["id"] for fact in proposed_facts] != [fact["id"] for fact in facts]:
        _fail("PROPOSED_FACT_ORDER_OR_ID_CHANGED")

    summary = {
        "input_fact_count": len(facts),
        "target_chapter_fact_count": sum(
            fact["chapter_id"] == chapter_id for fact in facts
        ),
        "revision_advanced_count": sum(
            row["effect"] == "revision_advanced" for row in effects
        ),
        "needs_recheck_count": sum(
            row["effect"] == "needs_recheck" for row in effects
        ),
        "unchanged_other_chapter_count": sum(
            row["effect"] == "unchanged_other_chapter" for row in effects
        ),
        "unchanged_already_needs_recheck_count": sum(
            row["effect"] == "unchanged_already_needs_recheck"
            for row in effects
        ),
    }
    core = {
        "identity": PROTOTYPE_IDENTITY,
        "prototype": True,
        "operation_id": operation_id,
        "flagged_at": flagged_at,
        "source": {
            "old_chapter": copy.deepcopy(old_chapter),
            "new_chapter": copy.deepcopy(new_chapter),
            "source_facts": copy.deepcopy(facts),
            "old_chapter_revision_ref": copy.deepcopy(
                old_chapter["chapter_revision_ref"]
            ),
            "new_chapter_revision_ref": copy.deepcopy(
                new_chapter["chapter_revision_ref"]
            ),
            "facts_snapshot_sha256": _sha256(facts),
            "external_route_request": copy.deepcopy(route_request),
            "external_route_receipt": copy.deepcopy(route_receipt),
        },
        "effects": effects,
        "proposed_facts": proposed_facts,
        "summary": summary,
        "writes": copy.deepcopy(WRITES),
    }
    return {**core, "prototype_sha256": _sha256(core)}


def validate_result(value: object) -> dict[str, Any]:
    """从结果自带的完整来源重跑预演；逐字段一致才接受。"""
    if not isinstance(value, dict) or set(value) != RESULT_KEYS:
        _fail("RESULT_FIELDS_INVALID")
    result = copy.deepcopy(value)
    if result["identity"] != PROTOTYPE_IDENTITY or result["prototype"] is not True:
        _fail("RESULT_IDENTITY_INVALID")
    if (
        not isinstance(result["operation_id"], str)
        or OPERATION_ID_RE.fullmatch(result["operation_id"]) is None
        or not isinstance(result["flagged_at"], str)
        or not result["flagged_at"]
    ):
        _fail("RESULT_OPERATION_OR_TIME_INVALID")
    source = result["source"]
    if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
        _fail("RESULT_SOURCE_INVALID")
    prototype_sha = result["prototype_sha256"]
    if (
        not isinstance(prototype_sha, str)
        or SHA256_RE.fullmatch(prototype_sha) is None
    ):
        _fail("RESULT_SHA_INVALID")
    core = copy.deepcopy(result)
    core.pop("prototype_sha256")
    if _sha256(core) != prototype_sha:
        _fail("RESULT_SHA_MISMATCH")
    replay_request = {
        "old_chapter": copy.deepcopy(source["old_chapter"]),
        "new_chapter": copy.deepcopy(source["new_chapter"]),
        "facts": copy.deepcopy(source["source_facts"]),
        "operation_id": result["operation_id"],
        "flagged_at": result["flagged_at"],
        "external_route_request": copy.deepcopy(
            source["external_route_request"]
        ),
    }
    expected = execute(replay_request)
    if expected != result:
        _fail("RESULT_SEMANTIC_REPLAY_MISMATCH")
    return result


# LOCAL_FILESYSTEM_ONLY：纯对象 execute 不接路径。
def _load_request(input_path: str | None) -> dict[str, Any]:
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
        raise FactRevisionPreflightError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("INPUT_OBJECT_REQUIRED")
    return value


def _same_file_identity(input_path: str | None, output_path: str | None) -> bool:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return False
    source = Path(input_path)
    target = Path(output_path)
    try:
        if source.resolve() == target.resolve():
            return True
        if source.exists() and target.exists() and os.path.samefile(source, target):
            return True
    except OSError as exc:
        raise FactRevisionPreflightError("FILE_IDENTITY_UNAVAILABLE") from exc
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
    parser = argparse.ArgumentParser(description="预演 C1 修订对 C4 证据的影响")
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        if _same_file_identity(args.input, args.output):
            _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")
        _write_atomic(args.output, execute(_load_request(args.input)))
    except (OSError, FactRevisionPreflightError) as exc:
        print(f"FACT_REVISION_PREFLIGHT_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "FactRevisionPreflightError",
    "execute",
    "validate_result",
]


if __name__ == "__main__":
    raise SystemExit(main())
