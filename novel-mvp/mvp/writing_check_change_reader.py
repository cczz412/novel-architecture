"""把现有写作检测结果排版成作者只看变化的清单。

本工具只复验完整 input package 与正式 WRITING_DESK_CHECK_RESULT v1，
再筛出 mismatch、missing、unplanned、unknown。它不运行检测、不生成
judgment，也不写工作区、正文、规划、事实、C11 或 closeout。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, NoReturn

if __package__:
    from . import writing_check_result_tool
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import writing_check_result_tool


REQUEST_KEYS = {"input_package", "check_result"}
CHANGE_CATEGORIES = {"mismatch", "missing", "unplanned", "unknown"}
VIEW_IDENTITY = "WRITING_CHECK_CHANGE_VIEW_R01"
VIEW_KEYS = {
    "identity",
    "projection_only",
    "creates_judgments",
    "input_package_sha256",
    "check_result_ref",
    "operation_id",
    "work",
    "planning_source",
    "scope",
    "change_count",
    "omitted_covered_count",
    "changes",
}


class WritingCheckChangeReaderError(ValueError):
    """检测输入包与正式结果不能组成同一份稳定变化视图。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise WritingCheckChangeReaderError(code)


def _validated_request(value: object) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    package = copy.deepcopy(value["input_package"])
    result = copy.deepcopy(value["check_result"])
    if not isinstance(package, dict):
        _fail("INPUT_PACKAGE_OBJECT_REQUIRED")
    if not isinstance(result, dict) or not isinstance(result.get("judgments"), list):
        _fail("CHECK_RESULT_OBJECT_REQUIRED")
    try:
        rebuilt = writing_check_result_tool.execute(
            {
                "input_package": copy.deepcopy(package),
                "provider_response": {
                    "judgments": copy.deepcopy(result["judgments"]),
                },
            }
        )
    except writing_check_result_tool.WritingCheckResultError as exc:
        raise WritingCheckChangeReaderError(
            f"CURRENT_RESULT_VALIDATION_FAILED:{exc.code}"
        ) from exc
    if rebuilt != result:
        _fail("CHECK_RESULT_REBUILD_MISMATCH")
    return package, rebuilt


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """严格复验当前输入与结果，再返回不带 covered 的变化对象。"""

    package, result = _validated_request(request)
    changes = [
        copy.deepcopy(row)
        for row in result["judgments"]
        if row["category"] in CHANGE_CATEGORIES
    ]
    omitted_count = sum(
        1 for row in result["judgments"] if row["category"] == "covered"
    )
    work = package["work"]
    planning = package["planning_source"]
    watermark = planning["generation_watermark"]
    view = {
        "identity": VIEW_IDENTITY,
        "projection_only": True,
        "creates_judgments": False,
        "input_package_sha256": package["input_package_sha256"],
        "check_result_ref": result["check_result_ref"],
        "operation_id": result["operation_id"],
        "work": {
            "slot_ref": work["slot_ref"],
            "work_ref": work["work_ref"],
            "work_rev": work["work_rev"],
            "text_sha256": work["text_sha256"],
            "source_outline_ref": work["source_outline_ref"],
        },
        "planning_source": {
            "source_plan_version": planning["source_plan_version"],
            "source_plan_sha256": planning["source_plan_sha256"],
            "slot_rev": watermark["slot_rev"],
            "source_commit_seq": planning["source_commit_seq"],
        },
        "scope": copy.deepcopy(result["scope"]),
        "change_count": len(changes),
        "omitted_covered_count": omitted_count,
        "changes": changes,
    }
    if set(view) != VIEW_KEYS:
        _fail("VIEW_FIELDS_INVALID")
    return view


def _fence_for(value: str) -> str:
    fence = "```"
    while fence in value:
        fence += "`"
    return fence


def _quote_lines(value: str | None) -> list[str]:
    if value is None:
        return ["- 逐字引文：无"]
    fence = _fence_for(value)
    return ["- 逐字引文：", "", fence, value, fence]


def render(request: dict[str, Any]) -> str:
    """稳定输出 UTF-8 Markdown；只排版已有变化，不制造新判断。"""

    view = execute(request)
    work = view["work"]
    planning = view["planning_source"]
    lines = [
        "# 稿件检查变化清单",
        "",
        "⚠️ 这只是变化视图，只排版现有判断，不作整体结论。",
        "不会调用检测 provider，也不会修改正文、章事实稿、规划、事实或 C11；不会创建 closeout。",
        "",
        f"- 视图身份：`{view['identity']}`",
        f"- 检测结果：`{view['check_result_ref']}`",
        f"- 检测操作：`{view['operation_id']}`",
        f"- 输入包 SHA：`{view['input_package_sha256']}`",
        f"- 章槽：`{work['slot_ref']}`",
        f"- 工作稿：`{work['work_ref']}` / revision `{work['work_rev']}`",
        f"- 工作内容 SHA：`{work['text_sha256']}`",
        f"- 来源大纲：`{work['source_outline_ref']}`",
        f"- Plan 水位：version `{planning['source_plan_version']}`",
        f"- Plan SHA：`{planning['source_plan_sha256']}`",
        f"- Slot revision：`{planning['slot_rev']}`",
        f"- Outline source commit：`{planning['source_commit_seq']}`",
        "",
        "## 需要作者查看的变化",
        "",
    ]
    if not view["changes"]:
        lines.extend(["本次没有需要展示的变化。", ""])
        return "\n".join(lines)

    for index, change in enumerate(view["changes"], 1):
        requirement_ref = change["requirement_ref"]
        lines.extend(
            [
                f"### {index}. {change['category']}",
                "",
                f"- Requirement：`{requirement_ref}`" if requirement_ref else "- Requirement：无",
                f"- 原判断说明：{change['explanation']}",
                *_quote_lines(change["evidence_quote"]),
                "",
            ]
        )
    return "\n".join(lines)


def _load_request(path_text: str | None) -> dict[str, Any]:
    if path_text in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(path_text)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE")
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WritingCheckChangeReaderError("INPUT_JSON_INVALID") from exc
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


def _write_atomic(path_text: str | None, value: str) -> None:
    payload = value.encode("utf-8")
    if path_text in {None, "-"}:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        return
    path = Path(path_text)
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
    parser = argparse.ArgumentParser(description="把正式检测结果排版成作者变化清单")
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        if _same_input_output(args.input, args.output):
            _fail("OUTPUT_MUST_NOT_OVERWRITE_INPUT")
        _write_atomic(args.output, render(_load_request(args.input)))
    except (OSError, WritingCheckChangeReaderError) as exc:
        print(f"WRITING_CHECK_CHANGE_READER_ERROR:{exc}", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "WritingCheckChangeReaderError",
    "execute",
    "render",
]


if __name__ == "__main__":
    raise SystemExit(main())
