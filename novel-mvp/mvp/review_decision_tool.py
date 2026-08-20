"""把作者对一页 M5 候选的明确决定转换为现役 review_actions。"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


if __package__:
    from . import factstore, review_page_tool
else:  # 允许直接运行 python novel-mvp/mvp/review_decision_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import factstore, review_page_tool


REQUEST_KEYS = {"review_page", "decisions"}
DECISION_BASE_KEYS = {
    "fact_ref",
    "decision",
    "note",
    "operation_id",
    "decided_at",
}
DECISION_EDIT_KEYS = DECISION_BASE_KEYS | {"replacement_text"}
ALLOWED_DECISIONS = {"confirm", "reject", "edit", "edit_and_confirm"}
EDIT_DECISIONS = {"edit", "edit_and_confirm"}
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class ReviewDecisionToolError(ValueError):
    """作者决定对象或本地 JSON 文件适配不合法。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ReviewDecisionToolError(code, detail)


def execute(request: object) -> dict[str, Any]:
    """只为作者逐条点名的本页事实构造动作，不执行或默认补决定。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    try:
        page = review_page_tool.validate_page(request.get("review_page"))
    except review_page_tool.ReviewPageToolError as exc:
        raise ReviewDecisionToolError("REVIEW_PAGE_INVALID", str(exc)) from exc

    decisions = request.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        _fail("DECISIONS_MUST_BE_NONEMPTY_ARRAY")
    facts_by_ref = {fact["id"]: fact for fact in page["items"]}
    seen_fact_refs: set[str] = set()
    seen_operation_ids: set[str] = set()
    review_actions: list[dict[str, Any]] = []
    for index, raw_decision in enumerate(decisions):
        if not isinstance(raw_decision, dict):
            _fail("DECISION_FIELDS_INVALID", str(index))
        decision = raw_decision.get("decision")
        if decision not in ALLOWED_DECISIONS:
            _fail("DECISION_NOT_ALLOWED", str(decision))
        decision_keys = set(raw_decision)
        if decision in EDIT_DECISIONS:
            if decision_keys == DECISION_BASE_KEYS:
                _fail("DECISION_REPLACEMENT_REQUIRED", str(index))
            if decision_keys != DECISION_EDIT_KEYS:
                _fail("DECISION_FIELDS_INVALID", str(index))
            replacement_text = raw_decision.get("replacement_text")
            if (
                not isinstance(replacement_text, str)
                or not replacement_text.strip()
            ):
                _fail("DECISION_REPLACEMENT_REQUIRED", str(index))
        else:
            if "replacement_text" in decision_keys:
                _fail("DECISION_REPLACEMENT_FORBIDDEN", str(index))
            if decision_keys != DECISION_BASE_KEYS:
                _fail("DECISION_FIELDS_INVALID", str(index))
            replacement_text = None
        fact_ref = raw_decision.get("fact_ref")
        if not isinstance(fact_ref, str) or fact_ref not in facts_by_ref:
            _fail("DECISION_FACT_NOT_ON_PAGE", str(fact_ref))
        if fact_ref in seen_fact_refs:
            _fail("DECISION_FACT_REF_DUPLICATE", fact_ref)
        operation_id = raw_decision.get("operation_id")
        if (
            not isinstance(operation_id, str)
            or OPERATION_ID_RE.fullmatch(operation_id) is None
        ):
            _fail("DECISION_OPERATION_ID_INVALID", str(index))
        if operation_id in seen_operation_ids:
            _fail("DECISION_OPERATION_ID_DUPLICATE", operation_id)
        note = raw_decision.get("note")
        if not isinstance(note, str):
            _fail("DECISION_NOTE_INVALID", str(index))
        decided_at = raw_decision.get("decided_at")
        if not isinstance(decided_at, str) or not decided_at.strip():
            _fail("DECISION_DECIDED_AT_INVALID", str(index))

        try:
            action = factstore.build_review_action(
                facts_by_ref[fact_ref],
                decision=decision,
                note=note,
                replacement_text=replacement_text,
                operation_id=operation_id,
            )
        except factstore.FactstoreError as exc:
            raise ReviewDecisionToolError(
                "DECISION_ACTION_INVALID",
                f"{index}:{exc}",
            ) from exc
        review_actions.append(
            {
                "action": action,
                "chapter_revision_ref": copy.deepcopy(
                    page["chapter_revision_ref"]
                ),
                "decided_at": decided_at,
            }
        )
        seen_fact_refs.add(fact_ref)
        seen_operation_ids.add(operation_id)

    return {
        "review_actions": review_actions,
        "expected_facts_version": page["facts_snapshot"]["version"],
        "expected_facts_sha256": page["facts_snapshot"]["sha256"],
    }


# LOCAL_FILESYSTEM_ONLY: 仅把本地 JSON 请求适配到纯对象 execute。
def _load_request(input_path: str | None) -> dict[str, Any]:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE", str(path))
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewDecisionToolError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("REQUEST_OBJECT_REQUIRED")
    return value


def _output_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY", str(path.parent))
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE", str(path))
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
            handle.write(_output_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _validate_paths(input_path: str | None, output_path: str | None) -> None:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return
    if Path(input_path).resolve() == Path(output_path).resolve():
        _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 M5 本页作者决定转换为 review_actions")
    parser.add_argument("--input", help="输入 JSON；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 JSON；省略或 - 表示 stdout")
    args = parser.parse_args(argv)
    try:
        _validate_paths(args.input, args.output)
        result = execute(_load_request(args.input))
        if args.output in {None, "-"}:
            sys.stdout.buffer.write(_output_bytes(result))
            sys.stdout.buffer.flush()
        else:
            _write_json_atomic(Path(args.output), result)
    except (OSError, ReviewDecisionToolError) as exc:
        print(f"REVIEW_DECISION_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = ["ReviewDecisionToolError", "execute"]


if __name__ == "__main__":
    raise SystemExit(main())
