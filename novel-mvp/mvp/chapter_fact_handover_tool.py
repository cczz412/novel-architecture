"""把作者明确的章事实稿交棒请求冻结为非正式动作 prototype。

本工具只绑定既有章事实稿 SHA、作者标题与规划水位。它不复制事实句，不写
AuthorWorkspace、C11、章节账、事实账或规划账，也不分配章节或 revision。
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
    from . import chapter_fact_draft_tool
else:  # 允许直接运行 python novel-mvp/mvp/chapter_fact_handover_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import chapter_fact_draft_tool


PROTOTYPE_IDENTITY = "CHAPTER_FACT_DRAFT_HANDOVER_ACTION_PROTOTYPE_R01"
STATUS = "REQUEST_RECORDED_NOT_APPLIED"
INTENT = "explicit_handover"
REQUEST_KEYS = {
    "chapter_fact_draft",
    "actor",
    "operation_id",
    "intent",
    "author_confirmed_title",
    "expected_prototype_sha256",
}
RESULT_KEYS = {
    "identity",
    "prototype",
    "status",
    "operation_id",
    "actor",
    "intent",
    "author_confirmed_title",
    "source_prototype",
    "slot",
    "planning_source",
    "effects",
    "action_sha256",
}
SOURCE_PROTOTYPE_KEYS = {"identity", "operation_id", "prototype_sha256"}
SLOT_KEYS = {"slot_ref", "slot_rev", "source_outline_ref"}
PLANNING_SOURCE_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "chapter_slot_snapshot_sha256",
    "generation_watermark",
    "source_commit_seq",
}
WATERMARK_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "slot_rev",
    "outline_source_commit_seq",
}
EFFECTS = {
    "c11": "none",
    "chapter_ledger": "none",
    "facts": "none",
    "plan": "none",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
OPERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class ChapterFactHandoverToolError(ValueError):
    """交棒动作 prototype 输入、结果或本地文件适配不合法。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise ChapterFactHandoverToolError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ChapterFactHandoverToolError("VALUE_NOT_JSON_SERIALIZABLE") from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _operation_id(value: object, code: str) -> str:
    if not isinstance(value, str) or OPERATION_ID_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _sha256_text(value: object, code: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(code)
    return value


def _non_negative_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code)
    return value


def _validated_title(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(code)
    return value


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """记录作者交棒请求；不应用动作，也不复制章事实句。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    try:
        draft = chapter_fact_draft_tool.validate_result(
            request["chapter_fact_draft"]
        )
    except chapter_fact_draft_tool.ChapterFactDraftToolError as exc:
        raise ChapterFactHandoverToolError(
            f"CHAPTER_FACT_DRAFT_INVALID:{exc.code}"
        ) from exc
    if request["actor"] != "author":
        _fail("AUTHOR_ACTOR_REQUIRED")
    operation_id = _operation_id(request["operation_id"], "OPERATION_ID_INVALID")
    if operation_id == draft["operation_id"]:
        _fail("NEW_OPERATION_ID_REQUIRED")
    if request["intent"] != INTENT:
        _fail("EXPLICIT_HANDOVER_INTENT_REQUIRED")
    title = _validated_title(request["author_confirmed_title"], "TITLE_INVALID")
    expected_sha = _sha256_text(
        request["expected_prototype_sha256"],
        "EXPECTED_PROTOTYPE_SHA_INVALID",
    )
    if expected_sha != draft["prototype_sha256"]:
        _fail("EXPECTED_PROTOTYPE_SHA_MISMATCH")

    action_core = {
        "identity": PROTOTYPE_IDENTITY,
        "prototype": True,
        "status": STATUS,
        "operation_id": operation_id,
        "actor": "author",
        "intent": INTENT,
        "author_confirmed_title": title,
        "source_prototype": {
            "identity": draft["identity"],
            "operation_id": draft["operation_id"],
            "prototype_sha256": draft["prototype_sha256"],
        },
        "slot": copy.deepcopy(draft["slot"]),
        "planning_source": copy.deepcopy(draft["planning_source"]),
        "effects": copy.deepcopy(EFFECTS),
    }
    return {
        **action_core,
        "action_sha256": _sha256(action_core),
    }


def _validated_slot_and_planning(
    slot: object,
    planning: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(slot, dict) or set(slot) != SLOT_KEYS:
        _fail("RESULT_SLOT_INVALID")
    slot_ref = slot["slot_ref"]
    if not isinstance(slot_ref, str) or not slot_ref:
        _fail("RESULT_SLOT_INVALID")
    slot_rev = _positive_int(slot["slot_rev"], "RESULT_SLOT_INVALID")
    source_outline_ref = slot["source_outline_ref"]
    prefix = f"{slot_ref}@outline-r"
    if (
        not isinstance(source_outline_ref, str)
        or not source_outline_ref.startswith(prefix)
        or not source_outline_ref.removeprefix(prefix).isdigit()
        or int(source_outline_ref.removeprefix(prefix)) < 1
    ):
        _fail("RESULT_OUTLINE_REF_INVALID")

    if not isinstance(planning, dict) or set(planning) != PLANNING_SOURCE_KEYS:
        _fail("RESULT_PLANNING_SOURCE_INVALID")
    source_plan_version = _positive_int(
        planning["source_plan_version"], "RESULT_PLANNING_SOURCE_INVALID"
    )
    source_plan_sha = _sha256_text(
        planning["source_plan_sha256"], "RESULT_PLANNING_SOURCE_INVALID"
    )
    _sha256_text(
        planning["chapter_slot_snapshot_sha256"],
        "RESULT_PLANNING_SOURCE_INVALID",
    )
    source_commit_seq = _non_negative_int(
        planning["source_commit_seq"], "RESULT_PLANNING_SOURCE_INVALID"
    )
    watermark = planning["generation_watermark"]
    if not isinstance(watermark, dict) or set(watermark) != WATERMARK_KEYS:
        _fail("RESULT_WATERMARK_INVALID")
    if (
        watermark["source_plan_version"] != source_plan_version
        or watermark["source_plan_sha256"] != source_plan_sha
        or watermark["slot_rev"] != slot_rev
        or watermark["outline_source_commit_seq"] != source_commit_seq
    ):
        _fail("RESULT_WATERMARK_MISMATCH")
    return copy.deepcopy(slot), copy.deepcopy(planning)


def validate_result(result: object) -> dict[str, Any]:
    """严格校验动作 prototype 全形状、水位、effects 与 action SHA。"""
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        _fail("RESULT_FIELDS_INVALID")
    if result["identity"] != PROTOTYPE_IDENTITY or result["prototype"] is not True:
        _fail("RESULT_IDENTITY_INVALID")
    if result["status"] != STATUS:
        _fail("RESULT_STATUS_INVALID")
    operation_id = _operation_id(
        result["operation_id"], "RESULT_OPERATION_ID_INVALID"
    )
    if result["actor"] != "author" or result["intent"] != INTENT:
        _fail("RESULT_AUTHORITY_INVALID")
    _validated_title(result["author_confirmed_title"], "RESULT_TITLE_INVALID")

    source = result["source_prototype"]
    if not isinstance(source, dict) or set(source) != SOURCE_PROTOTYPE_KEYS:
        _fail("RESULT_SOURCE_PROTOTYPE_INVALID")
    if source["identity"] != chapter_fact_draft_tool.PROTOTYPE_IDENTITY:
        _fail("RESULT_SOURCE_PROTOTYPE_INVALID")
    source_operation_id = _operation_id(
        source["operation_id"], "RESULT_SOURCE_PROTOTYPE_INVALID"
    )
    if source_operation_id == operation_id:
        _fail("RESULT_OPERATION_ID_REUSED")
    _sha256_text(
        source["prototype_sha256"], "RESULT_SOURCE_PROTOTYPE_INVALID"
    )
    _validated_slot_and_planning(result["slot"], result["planning_source"])
    if result["effects"] != EFFECTS:
        _fail("RESULT_EFFECTS_INVALID")
    action_sha = _sha256_text(result["action_sha256"], "RESULT_SHA_INVALID")
    core = copy.deepcopy(result)
    core.pop("action_sha256")
    if _sha256(core) != action_sha:
        _fail("ACTION_SHA_MISMATCH")
    return copy.deepcopy(result)


def _indented_block(value: str) -> str:
    return "\n".join(f"    {line}" for line in value.split("\n"))


def render_result(result: object) -> str:
    """渲染作者可读交棒请求，不把标题确认扩大成事实确认。"""
    validated = validate_result(result)
    slot = validated["slot"]
    planning = validated["planning_source"]
    source = validated["source_prototype"]
    lines = [
        "# 章事实稿交棒请求原型",
        "",
        "> 已记录交棒请求，但尚未写入章节账／事实账。",
        "> 标题确认只说明交棒时采用这个标题，不等于确认任何事实句。",
        "",
        "## 作者确认标题",
        "",
        _indented_block(validated["author_confirmed_title"]),
        "",
        "## 来源",
        "",
        f"- 章事实稿原型 SHA256：`{source['prototype_sha256']}`",
        f"- 章槽：`{slot['slot_ref']}`",
        f"- 章槽修订：`r{slot['slot_rev']}`",
        f"- 章纲来源：`{slot['source_outline_ref']}`",
        f"- 规划版本：`{planning['source_plan_version']}`",
        f"- 规划 SHA256：`{planning['source_plan_sha256']}`",
        f"- 规划提交水位：`{planning['source_commit_seq']}`",
        f"- 交棒请求操作号：`{validated['operation_id']}`",
        f"- 动作原型 SHA256：`{validated['action_sha256']}`",
        "",
        "## 写入结果",
        "",
        "- C11 写入：0",
        "- 章节账写入：0",
        "- 事实账写入：0",
        "- 规划账写入：0",
        "",
    ]
    return "\n".join(lines)


def _load_object(input_path: str | None) -> dict[str, Any]:
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
        raise ChapterFactHandoverToolError("INPUT_JSON_INVALID") from exc
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
        raise ChapterFactHandoverToolError("FILE_IDENTITY_UNAVAILABLE") from exc
    return False


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_atomic(output_path: str | None, payload: bytes) -> None:
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
    parser = argparse.ArgumentParser(description="冻结章事实稿显式交棒请求 prototype")
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    parser.add_argument(
        "--render",
        action="store_true",
        help="把已经生成的动作 prototype 渲染成作者可读 Markdown",
    )
    args = parser.parse_args(argv)
    try:
        if _same_file_identity(args.input, args.output):
            _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")
        value = _load_object(args.input)
        if args.render:
            payload = render_result(value).encode("utf-8")
        else:
            payload = _canonical_bytes(execute(value))
        _write_bytes_atomic(args.output, payload)
    except (OSError, ChapterFactHandoverToolError) as exc:
        print(f"CHAPTER_FACT_HANDOVER_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "ChapterFactHandoverToolError",
    "execute",
    "render_result",
    "validate_result",
]


if __name__ == "__main__":
    raise SystemExit(main())
