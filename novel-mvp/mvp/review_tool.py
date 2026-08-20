"""M5 独立文件工具：C4 v1 快照＋作者审查动作 → 新快照＋回执。

核心 execute 只接对象。文件入口仅为 LOCAL_FILESYSTEM_ONLY 运输适配；
不接 AuthorWorkspace、project_dir、reconcile 或作者身份推断。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    from . import factstore
except ImportError:  # pragma: no cover - 直接运行脚本时使用
    import factstore  # type: ignore[no-redef]


REQUEST_KEYS = {
    "snapshot_version",
    "expected_snapshot_version",
    "expected_snapshot_sha256",
    "facts",
    "chapter_revision_ref",
    "action",
    "decided_at",
}
BATCH_REQUEST_KEYS = {
    "snapshot_version",
    "snapshot_sha256",
    "facts",
    "items",
}
BATCH_ITEM_KEYS = {
    "chapter_revision_ref",
    "action",
    "decided_at",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def validate_review_action(action: dict[str, Any]) -> dict[str, Any]:
    """公开的纯对象动作门，供 workspace 适配器复用同一 M5 校验。"""
    factstore._validate_review_action(action)
    return copy.deepcopy(action)


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """纯对象执行；任何绑定失败都不返回半批结果。"""
    if not isinstance(request, dict):
        raise factstore.FactstoreError("REVIEW_TOOL_REQUEST_NOT_OBJECT")
    if set(request) != REQUEST_KEYS:
        missing = REQUEST_KEYS - set(request)
        extra = set(request) - REQUEST_KEYS
        if missing:
            raise factstore.FactstoreError(
                f"REVIEW_TOOL_REQUEST_MISSING:{','.join(sorted(missing))}"
            )
        raise factstore.FactstoreError(
            f"REVIEW_TOOL_REQUEST_EXTRA:{','.join(sorted(extra))}"
        )
    snapshot_version = request["snapshot_version"]
    if (
        not isinstance(snapshot_version, int)
        or isinstance(snapshot_version, bool)
        or snapshot_version <= 0
    ):
        raise factstore.FactstoreError("REVIEW_SNAPSHOT_VERSION_INVALID")
    expected_version = request["expected_snapshot_version"]
    if (
        not isinstance(expected_version, int)
        or isinstance(expected_version, bool)
        or expected_version <= 0
    ):
        raise factstore.FactstoreError("REVIEW_EXPECTED_SNAPSHOT_VERSION_INVALID")
    if expected_version != snapshot_version:
        raise factstore.FactstoreError("STALE_SNAPSHOT_VERSION")
    expected_sha = request["expected_snapshot_sha256"]
    if not isinstance(expected_sha, str) or SHA256_RE.fullmatch(expected_sha) is None:
        raise factstore.FactstoreError("REVIEW_SNAPSHOT_SHA_INVALID")
    facts_before = factstore.validate_c4_v1_snapshot(request["facts"])
    action = validate_review_action(request["action"])
    before_sha = factstore.c4_snapshot_sha256(facts_before)
    if before_sha != expected_sha:
        raise factstore.FactstoreError("STALE_SNAPSHOT_SHA")

    facts_after, action_result = factstore.apply_review_action_to_c4_snapshot(
        snapshot=facts_before,
        action=action,
        chapter_revision_ref=request["chapter_revision_ref"],
        decided_at=request["decided_at"],
    )
    after_sha = factstore.c4_snapshot_sha256(facts_after)
    action_sha = hashlib.sha256(_json_bytes(action)).hexdigest()
    receipt = {
        **action_result,
        "status": "APPLIED",
        "actor": "author",
        "before_snapshot_version": snapshot_version,
        "after_snapshot_version": snapshot_version + 1,
        "before_snapshot_sha256": before_sha,
        "after_snapshot_sha256": after_sha,
        "action_sha256": action_sha,
    }
    return {
        "snapshot_version": snapshot_version + 1,
        "snapshot_sha256": after_sha,
        "facts": facts_after,
        "receipt": receipt,
    }


def _validated_batch_preflight(
    request: dict[str, Any],
) -> tuple[int, str, list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(request, dict):
        raise factstore.FactstoreError("REVIEW_TOOL_BATCH_REQUEST_NOT_OBJECT")
    if set(request) != BATCH_REQUEST_KEYS:
        missing = BATCH_REQUEST_KEYS - set(request)
        extra = set(request) - BATCH_REQUEST_KEYS
        if missing:
            raise factstore.FactstoreError(
                f"REVIEW_TOOL_BATCH_REQUEST_MISSING:{','.join(sorted(missing))}"
            )
        raise factstore.FactstoreError(
            f"REVIEW_TOOL_BATCH_REQUEST_EXTRA:{','.join(sorted(extra))}"
        )
    snapshot_version = request["snapshot_version"]
    if (
        not isinstance(snapshot_version, int)
        or isinstance(snapshot_version, bool)
        or snapshot_version <= 0
    ):
        raise factstore.FactstoreError("REVIEW_BATCH_SNAPSHOT_VERSION_INVALID")
    snapshot_sha = request["snapshot_sha256"]
    if not isinstance(snapshot_sha, str) or SHA256_RE.fullmatch(snapshot_sha) is None:
        raise factstore.FactstoreError("REVIEW_BATCH_SNAPSHOT_SHA_INVALID")
    facts = factstore.validate_c4_v1_snapshot(request["facts"])
    if factstore.c4_snapshot_sha256(facts) != snapshot_sha:
        raise factstore.FactstoreError("STALE_SNAPSHOT_SHA")
    items = request["items"]
    if not isinstance(items, list) or not items:
        raise factstore.FactstoreError("REVIEW_TOOL_BATCH_ITEMS_REQUIRED")

    facts_by_ref = {fact["id"]: fact for fact in facts}
    seen_fact_refs: set[str] = set()
    seen_operation_ids: set[str] = set()
    batch_revision_ref: dict[str, Any] | None = None
    validated_items: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != BATCH_ITEM_KEYS:
            raise factstore.FactstoreError(
                f"REVIEW_TOOL_BATCH_ITEM_SHAPE_INVALID:{index}"
            )
        action = validate_review_action(item["action"])
        decided_at = item["decided_at"]
        if not isinstance(decided_at, str) or not decided_at.strip():
            raise factstore.FactstoreError("FACT_REVIEW_DECIDED_AT_INVALID")
        fact_ref = action["fact_ref"]
        operation_id = action["operation_id"]
        if fact_ref in seen_fact_refs:
            raise factstore.FactstoreError("REVIEW_BATCH_FACT_REF_DUPLICATE")
        if operation_id in seen_operation_ids:
            raise factstore.FactstoreError(
                "REVIEW_BATCH_OPERATION_ID_DUPLICATE"
            )
        target = facts_by_ref.get(fact_ref)
        if target is None:
            raise factstore.FactstoreError("FACT_REVIEW_TARGET_NOT_FOUND")
        revision_ref = item["chapter_revision_ref"]
        if not isinstance(revision_ref, dict) or revision_ref != target[
            "chapter_revision_ref"
        ]:
            raise factstore.FactstoreError(
                f"REVIEW_BATCH_ACTION_REVISION_FACT_MISMATCH:{fact_ref}"
            )
        if batch_revision_ref is None:
            batch_revision_ref = copy.deepcopy(revision_ref)
        elif revision_ref != batch_revision_ref:
            raise factstore.FactstoreError("REVIEW_BATCH_CROSS_REVISION_SCOPE")
        seen_fact_refs.add(fact_ref)
        seen_operation_ids.add(operation_id)
        validated_items.append(
            {
                "chapter_revision_ref": copy.deepcopy(revision_ref),
                "action": action,
                "decided_at": decided_at,
            }
        )
    return snapshot_version, snapshot_sha, facts, validated_items


def execute_batch(request: dict[str, Any]) -> dict[str, Any]:
    """按显式作者动作顺序复用单条 execute，整批只返回最终快照。"""
    snapshot_version, snapshot_sha, facts, items = _validated_batch_preflight(
        request
    )
    receipts: list[dict[str, Any]] = []
    current_version = snapshot_version
    current_sha = snapshot_sha
    current_facts = facts
    for item in items:
        result = execute(
            {
                "snapshot_version": current_version,
                "expected_snapshot_version": current_version,
                "expected_snapshot_sha256": current_sha,
                "facts": current_facts,
                **item,
            }
        )
        current_version = result["snapshot_version"]
        current_sha = result["snapshot_sha256"]
        current_facts = result["facts"]
        receipts.append(result["receipt"])
    return {
        "snapshot_version": current_version,
        "snapshot_sha256": current_sha,
        "facts": current_facts,
        "receipts": receipts,
        "input_count": len(items),
        "applied_count": len(receipts),
    }


def execute_request(request: dict[str, Any]) -> dict[str, Any]:
    """CLI 显式区分原单条动作与同章动作批次。"""
    has_single = "action" in request
    has_batch = "items" in request
    if has_single and has_batch:
        raise factstore.FactstoreError("REVIEW_TOOL_REQUEST_SHAPE_AMBIGUOUS")
    if has_batch:
        return execute_batch(request)
    return execute(request)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _read_request(path: str | None) -> dict[str, Any]:
    if path is None or path == "-":
        value = json.load(sys.stdin)
    else:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise factstore.FactstoreError("REVIEW_TOOL_REQUEST_NOT_OBJECT")
    return value


def _write_json_atomic(path: Path, value: Any) -> None:
    if not path.parent.is_dir():
        raise factstore.FactstoreError("REVIEW_TOOL_OUTPUT_PARENT_NOT_FOUND")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LOCAL_FILESYSTEM_ONLY：执行作者提交的 C4 v1 审查动作"
    )
    parser.add_argument("--input", help="本地 JSON 文件；省略或 - 表示 stdin")
    parser.add_argument("--output", help="本地 JSON 文件；省略或 - 表示 stdout")
    args = parser.parse_args()
    try:
        result = execute_request(_read_request(args.input))
        if args.output is None or args.output == "-":
            sys.stdout.buffer.write(_json_bytes(result))
        else:
            _write_json_atomic(Path(args.output), result)
    except (factstore.FactstoreError, json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(
            json.dumps(
                {"status": "REJECTED", "reason": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
