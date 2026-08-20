"""WRITING_CHECK_INPUT_PACKAGE_PROTOTYPE_R01 的人读清单。

本工具只严格复验并排版已有检测输入包。它不运行检测、不生成 judgment，
也不把输入包冒充 WRITING_DESK_CHECK_RESULT。
"""

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
    from . import writing_check_package_tool
    from .workspace import OPERATION_ID_RE, SHA256_RE
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import writing_check_package_tool
    from mvp.workspace import OPERATION_ID_RE, SHA256_RE


PACKAGE_KEYS = {
    "identity",
    "prototype",
    "check_operation_id",
    "work",
    "planning_source",
    "requirements",
    "scope",
    "input_package_sha256",
}
WORK_KEYS = {
    "slot_ref",
    "work_ref",
    "work_rev",
    "source_outline_ref",
    "text",
    "text_sha256",
}
PLANNING_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "generation_watermark",
    "source_commit_seq",
}
WATERMARK_KEYS = {
    "source_plan_version",
    "source_plan_sha256",
    "slot_rev",
    "outline_source_commit_seq",
}
REQUIREMENT_KEYS = {"requirement_ref", "source_kind", "source_text"}
SCOPE_KEYS = {"mode", "target_ref", "requirement_refs"}
OUTLINE_REF_RE = re.compile(r"^(.+)@outline-r([1-9][0-9]*)$")
WARNING = (
    "尚未运行检测；这不是WRITING_DESK_CHECK_RESULT，"
    "也不代表通过/全绿/可收工。"
)


class WritingCheckPackageReaderError(ValueError):
    """输入包无法在不猜测的前提下渲染。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise WritingCheckPackageReaderError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise WritingCheckPackageReaderError(
            "PACKAGE_NOT_JSON_SERIALIZABLE"
        ) from exc
    return (text + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _reference(value: object, *, code: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        _fail(code)
    return value


def _integer(value: object, *, code: str, minimum: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
    ):
        _fail(code)
    return value


def _valid_sha(value: object, *, code: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(code)
    return value


def validate_package(value: dict[str, Any]) -> dict[str, Any]:
    """复验完整 package、来源闭合与整包 SHA，不信任单独 scope 摘要。"""

    if not isinstance(value, dict) or set(value) != PACKAGE_KEYS:
        _fail("PACKAGE_FIELDS_INVALID")
    package = copy.deepcopy(value)
    if (
        package["identity"] != writing_check_package_tool.PROTOTYPE_IDENTITY
        or package["prototype"] is not True
    ):
        _fail("PACKAGE_PROTOTYPE_IDENTITY_INVALID")
    operation_id = package["check_operation_id"]
    if (
        not isinstance(operation_id, str)
        or OPERATION_ID_RE.fullmatch(operation_id) is None
    ):
        _fail("CHECK_OPERATION_ID_INVALID")

    work = package["work"]
    if not isinstance(work, dict) or set(work) != WORK_KEYS:
        _fail("PACKAGE_WORK_INVALID")
    slot_ref = _reference(work["slot_ref"], code="WORK_SLOT_REF_INVALID")
    work_ref = _reference(work["work_ref"], code="WORK_REF_INVALID")
    source_outline_ref = _reference(
        work["source_outline_ref"],
        code="SOURCE_OUTLINE_REF_INVALID",
    )
    if work_ref != f"{slot_ref}@work":
        _fail("WORK_REF_SLOT_MISMATCH")
    outline_match = OUTLINE_REF_RE.fullmatch(source_outline_ref)
    if outline_match is None or outline_match.group(1) != slot_ref:
        _fail("SOURCE_OUTLINE_REF_SLOT_MISMATCH")
    _integer(work["work_rev"], code="WORK_REV_INVALID", minimum=1)
    if not isinstance(work["text"], str):
        _fail("WORK_TEXT_INVALID")
    try:
        text_bytes = work["text"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WritingCheckPackageReaderError("WORK_TEXT_NOT_UTF8") from exc
    text_sha = _valid_sha(work["text_sha256"], code="WORK_TEXT_SHA_INVALID")
    if _sha256(text_bytes) != text_sha:
        _fail("WORK_TEXT_SHA_MISMATCH")

    planning = package["planning_source"]
    if not isinstance(planning, dict) or set(planning) != PLANNING_KEYS:
        _fail("PLANNING_SOURCE_INVALID")
    plan_version = _integer(
        planning["source_plan_version"],
        code="SOURCE_PLAN_VERSION_INVALID",
        minimum=1,
    )
    plan_sha = _valid_sha(
        planning["source_plan_sha256"],
        code="SOURCE_PLAN_SHA_INVALID",
    )
    source_commit_seq = _integer(
        planning["source_commit_seq"],
        code="SOURCE_COMMIT_SEQ_INVALID",
        minimum=0,
    )
    watermark = planning["generation_watermark"]
    if not isinstance(watermark, dict) or set(watermark) != WATERMARK_KEYS:
        _fail("GENERATION_WATERMARK_INVALID")
    if (
        watermark["source_plan_version"] != plan_version
        or watermark["source_plan_sha256"] != plan_sha
        or watermark["outline_source_commit_seq"] != source_commit_seq
    ):
        _fail("PLANNING_WATERMARK_MISMATCH")
    _integer(watermark["slot_rev"], code="SLOT_REV_INVALID", minimum=1)

    requirements = package["requirements"]
    if not isinstance(requirements, list):
        _fail("REQUIREMENTS_INVALID")
    refs: list[str] = []
    for index, row in enumerate(requirements):
        if not isinstance(row, dict) or set(row) != REQUIREMENT_KEYS:
            _fail(f"REQUIREMENT_FIELDS_INVALID:{index}")
        ref = _reference(
            row["requirement_ref"],
            code=f"REQUIREMENT_REF_INVALID:{index}",
        )
        if row["source_kind"] not in {"planned_event", "must_not"}:
            _fail(f"REQUIREMENT_SOURCE_KIND_INVALID:{index}")
        if not isinstance(row["source_text"], str):
            _fail(f"REQUIREMENT_SOURCE_TEXT_INVALID:{index}")
        if row["source_kind"] == "must_not":
            expected_ref = writing_check_package_tool._must_not_ref(
                source_outline_ref,
                row["source_text"],
            )
            if ref != expected_ref:
                _fail(f"MUST_NOT_REF_MISMATCH:{index}")
        elif "#must_not:" in ref:
            _fail(f"PLANNED_EVENT_REF_INVALID:{index}")
        refs.append(ref)
    if len(refs) != len(set(refs)):
        _fail("DUPLICATE_REQUIREMENT_REF")

    scope = package["scope"]
    if not isinstance(scope, dict) or set(scope) != SCOPE_KEYS:
        _fail("SCOPE_INVALID")
    if scope["mode"] != "chapter" or scope["target_ref"] != slot_ref:
        _fail("CHAPTER_SCOPE_NOT_CLOSED")
    if scope["requirement_refs"] != refs:
        _fail("SCOPE_REQUIREMENTS_NOT_CLOSED")

    package_sha = _valid_sha(
        package["input_package_sha256"],
        code="INPUT_PACKAGE_SHA_INVALID",
    )
    core = copy.deepcopy(package)
    core.pop("input_package_sha256")
    if _sha256(_canonical_bytes(core)) != package_sha:
        _fail("INPUT_PACKAGE_SHA_MISMATCH")
    return package


def _markdown_fence(text: str) -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return fence


def render_package(value: dict[str, Any]) -> str:
    """把已冻结输入包排版成人读检查清单，不运行检测。"""

    package = validate_package(value)
    work = package["work"]
    planning = package["planning_source"]
    watermark = planning["generation_watermark"]
    lines = [
        "# 写作检测输入清单",
        "",
        f"> ⚠️ {WARNING}",
        "",
        f"- Prototype 身份：`{package['identity']}`",
        f"- Check operation：`{package['check_operation_id']}`",
        f"- 输入包 SHA：`{package['input_package_sha256']}`",
        f"- 检查范围：全章（`{package['scope']['mode']}`）",
        f"- 目标章槽：`{work['slot_ref']}`",
        f"- 来源大纲：`{work['source_outline_ref']}`",
        f"- 工作稿：`{work['work_ref']}` / revision `{work['work_rev']}`",
        f"- 工作稿正文 SHA：`{work['text_sha256']}`",
        f"- Plan 水位：version `{planning['source_plan_version']}`",
        f"- Plan SHA：`{planning['source_plan_sha256']}`",
        f"- Slot revision：`{watermark['slot_rev']}`",
        f"- Outline source commit：`{planning['source_commit_seq']}`",
        "",
        "## 本次检查 requirements（按冻结顺序）",
        "",
    ]
    if not package["requirements"]:
        lines.append("本包没有列出 PE 或 must_not requirement。")
    for index, requirement in enumerate(package["requirements"], 1):
        lines.extend(
            [
                f"### {index}. {requirement['requirement_ref']}",
                "",
                f"- 来源类型：`{requirement['source_kind']}`",
                f"- 原文：{requirement['source_text']}",
                "",
            ]
        )
    fence = _markdown_fence(work["text"])
    lines.extend(
        [
            "## 本地作者原文，仅供本次检查输入",
            "",
            f"{fence}\n{work['text']}\n{fence}",
            "",
            f"> ⚠️ {WARNING}",
            "",
        ]
    )
    return "\n".join(lines)


def _load_package(input_path: str | None) -> dict[str, Any]:
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
        raise WritingCheckPackageReaderError("INPUT_JSON_INVALID") from exc
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


def _write_atomic(output_path: str | None, text: str) -> None:
    payload = text.encode("utf-8")
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
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="人读写作检测输入包")
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        if _same_input_output(args.input, args.output):
            _fail("OUTPUT_MUST_NOT_OVERWRITE_INPUT")
        _write_atomic(args.output, render_package(_load_package(args.input)))
    except (OSError, WritingCheckPackageReaderError) as exc:
        print(f"WRITING_CHECK_PACKAGE_READER_ERROR:{exc}", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "WritingCheckPackageReaderError",
    "render_package",
    "validate_package",
]


if __name__ == "__main__":
    raise SystemExit(main())
