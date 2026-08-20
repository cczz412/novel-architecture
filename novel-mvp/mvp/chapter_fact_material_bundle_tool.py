"""把现役 M11 章事实稿材料包排成作者可读的本地文件。

本工具只读取并严格校验已经生成的组合原型。它不会重新读取作者工作区，
不会回取被挡材料，也不会生成章事实稿、交棒动作或任何账本写入。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

if __package__:
    from . import chapter_fact_material_bundle_workspace, packer_tool
else:  # 允许直接运行这个 LOCAL_FILESYSTEM_ONLY 文件工具。
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from mvp import chapter_fact_material_bundle_workspace, packer_tool


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"


class ChapterFactMaterialBundleToolError(RuntimeError):
    """输入不是可信材料包，或作者可读文件不能安全写出。"""


def _fail(code: str, detail: str = "") -> NoReturn:
    raise ChapterFactMaterialBundleToolError(
        f"{code}:{detail}" if detail else code
    )


def validate_result(value: object) -> dict[str, Any]:
    """严格校验已有组合原型，不重新读取工作区或补写内容。"""

    try:
        return chapter_fact_material_bundle_workspace.validate_result(value)
    except (
        chapter_fact_material_bundle_workspace.ChapterFactMaterialBundleWorkspaceError
    ) as exc:
        raise ChapterFactMaterialBundleToolError(
            f"BUNDLE_RESULT_INVALID:{exc}"
        ) from exc


def _indented_block(value: str) -> list[str]:
    lines = value.splitlines()
    if not lines:
        lines = [""]
    return [f"    {line}" for line in lines]


def _append_untrusted_text(
    lines: list[str], label: str, value: str
) -> None:
    lines.extend(["", f"**{label}**", "", *_indented_block(value)])


def _append_untrusted_value(lines: list[str], label: str, value: Any) -> None:
    if isinstance(value, list):
        lines.extend(["", f"**{label}**"])
        if not value:
            lines.extend(["", "- 无"])
            return
        for index, item in enumerate(value, start=1):
            lines.extend(
                ["", f"第 {index} 项", "", *_indented_block(str(item))]
            )
        return
    _append_untrusted_text(lines, label, str(value))


def _snapshot_line(label: str, snapshot: dict[str, Any]) -> str:
    sha256 = snapshot["sha256"] if snapshot["sha256"] is not None else "无"
    return f"- {label}：版本 {snapshot['version']}；SHA256：{sha256}"


def _render_loaded_facts(result: dict[str, Any]) -> list[str]:
    rows = result["current_fact_pack"]["loaded_facts"]
    lines = ["## 已发生且已确认事实"]
    if not rows:
        return [*lines, "", "- 无"]
    for index, row in enumerate(rows, start=1):
        fact = row["fact"]
        revision = fact["chapter_revision_ref"]
        anchor = fact["anchor_ref"]
        lines.extend(
            [
                "",
                f"### {index}. 事实句",
                "",
                *_indented_block(fact["text"]),
                "",
                "**事实编号**",
                "",
                *_indented_block(fact["id"]),
                "",
                "**章节编号**",
                "",
                *_indented_block(revision["chapter_id"]),
                f"- 修订号：`r{revision['revision_no']}`",
                f"- 章节文字 SHA256：`{revision['revision_text_sha256']}`",
                "",
                "**装入原因**",
                "",
                *_indented_block(row["why_loaded"]),
                "",
                "**逐字引用证据**",
                "",
                *_indented_block(fact["quote"]),
                "",
                (
                    f"- 原文坐标：`[{anchor['start']}, {anchor['end']})`；"
                    f"口径：`{anchor['coordinate_basis']}`"
                ),
                f"- 引用 SHA256：`{anchor['slice_sha256']}`",
            ]
        )
    return lines


def _render_omission_counts(result: dict[str, Any]) -> list[str]:
    omitted = result["current_fact_pack"]["m11_result"]["omitted"]
    labels = packer_tool.AUTHOR_SAFE_OMISSION_REASON_LABELS
    counts = {reason: 0 for reason in labels}
    for row in omitted:
        reason = row["reason"]
        if reason not in counts:
            _fail("BLOCKED_MATERIAL_REASON_UNKNOWN")
        counts[reason] += 1
    lines = [
        "## 被挡材料（只显示原因和数量）",
        "",
        f"- 被挡总数：{len(omitted)} 条",
    ]
    lines.extend(f"- {label}：{counts[reason]} 条" for reason, label in labels.items())
    return lines


def _render_future_events(result: dict[str, Any]) -> list[str]:
    rows = result["planning_supply"]["future_event_materials"]
    lines = ["## 下一章未来计划（每项都尚未发生）"]
    if not rows:
        return [*lines, "", "- 无"]
    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                "",
                f"### {index}. 尚未发生",
                "",
                *_indented_block(row["text"]),
                "",
                "**计划事件编号**",
                "",
                *_indented_block(row["id"]),
                f"- 计划事件修订：`r{row['rev']}`",
                "",
                "**场景引用**",
                "",
                *_indented_block(row["scene_ref"]),
            ]
        )
        optional_labels = (
            ("storyline_ref", "故事线引用"),
            ("purpose", "计划用途"),
            ("story_time_hint", "故事时间提示"),
            ("origin_ref", "来源引用"),
            ("repair_ref", "修复引用"),
            ("deviation_note", "偏离说明"),
            ("defer_count", "已推迟次数"),
        )
        for field, label in optional_labels:
            if field in row:
                _append_untrusted_value(lines, label, row[field])
    return lines


def _render_writing_notes(result: dict[str, Any]) -> list[str]:
    notes = result["planning_supply"]["writing_note_sources"]
    chapter = notes["chapter"]
    scenes = notes["scenes"]
    lines = [
        "## 写法批注（不是事实）",
        "",
        "### 本章写法来源",
        "",
        "- 身份：写法批注，不是已经发生的故事事实",
        "",
        "**章槽编号**",
        "",
        *_indented_block(chapter["slot_ref"]),
        f"- 章槽修订：`r{chapter['slot_rev']}`",
    ]
    chapter_labels = (
        ("goal", "本章目标"),
        ("summary", "本章摘要"),
        ("entry_state", "进入状态"),
        ("exit_condition", "退出条件"),
        ("exit_hook", "章末钩子"),
        ("must_not", "不得发生"),
        ("risks", "写作风险"),
    )
    for field, label in chapter_labels:
        if field in chapter:
            _append_untrusted_value(lines, label, chapter[field])
    if not scenes:
        lines.extend(["", "### 场景写法来源", "", "- 无"])
        return lines
    lines.extend(["", "### 场景写法来源"])
    scene_labels = (
        ("goal", "场景目标"),
        ("summary", "场景摘要"),
        ("location", "地点提示"),
        ("characters", "人物提示"),
        ("pov", "视角提示"),
        ("mood_in", "进入情绪"),
        ("mood_out", "离开情绪"),
        ("visual_hint", "视觉提示"),
        ("dialogue_hints", "对白提示"),
        ("resistance", "阻力提示"),
        ("turn", "转折提示"),
        ("spoiler_notes", "剧透边界"),
        ("word_estimate", "字数提示"),
    )
    for index, scene in enumerate(scenes, start=1):
        lines.extend(
            [
                "",
                f"#### 场景写法来源 {index}",
                "",
                "- 身份：写法批注，不是已经发生的故事事实",
                "",
                "**场景编号**",
                "",
                *_indented_block(scene["id"]),
                f"- 场景修订：`r{scene['rev']}`",
            ]
        )
        for field, label in scene_labels:
            if field in scene:
                _append_untrusted_value(lines, label, scene[field])
    return lines


def _render_longline_context(result: dict[str, Any]) -> list[str]:
    rows = result["planning_supply"]["longline_context"]
    lines = ["## 长线背景（规划参考，不是已经发生的事实）"]
    if not rows:
        return [*lines, "", "- 无"]
    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                "",
                f"### 长线背景 {index}",
                "",
                "**故事线名称**",
                "",
                *_indented_block(row["name"]),
                "",
                "**故事线编号**",
                "",
                *_indented_block(row["id"]),
                f"- 修订：`r{row['rev']}`",
                f"- 优先级：{row['priority']}",
                f"- 状态：{row['line_status']}",
            ]
        )
        if row["alias"] is None:
            lines.append("- 别名：无")
        else:
            _append_untrusted_text(lines, "别名", row["alias"])
        _append_untrusted_value(lines, "涉及人物", row["members"])
    return lines


def render_result(value: object) -> str:
    """把可信组合原型排成稳定作者页，不增加或改变任何内容决策。"""

    result = validate_result(value)
    sources = result["source_snapshots"]
    lines = [
        "# M11 章事实稿材料包｜原型｜只读快照｜未生成章事实稿｜未交棒",
        "",
        f"- 材料包 SHA256：`{result['bundle_sha256']}`",
        f"- 工作区绑定摘要：`{result['workspace_binding_sha256']}`",
        _snapshot_line("规划账快照", sources["plan"]),
        _snapshot_line("事实账快照", sources["facts"]),
        _snapshot_line("章节目录快照", sources["chapter_index"]),
        "",
        *_render_loaded_facts(result),
        "",
        *_render_omission_counts(result),
        "",
        *_render_future_events(result),
        "",
        *_render_writing_notes(result),
        "",
        *_render_longline_context(result),
        "",
        "## 使用边界",
        "",
        "- 打开这个文件时没有重新核对作者工作区；它只代表生成时的一次只读快照。",
        "- 章事实稿：未生成",
        "- 交棒：未发生",
        "- 事实账写入：0",
        "- 规划账写入：0",
        "- C11 写入：0",
        "",
    ]
    return "\n".join(lines)


def _load_json(input_path: str | None) -> dict[str, Any]:
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
        raise ChapterFactMaterialBundleToolError("INPUT_JSON_INVALID") from exc
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
        raise ChapterFactMaterialBundleToolError(
            "FILE_IDENTITY_UNAVAILABLE"
        ) from exc
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
    parser = argparse.ArgumentParser(
        description="把 M11 章事实稿材料包原型排成作者可读 Markdown"
    )
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        if _same_file_identity(args.input, args.output):
            _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")
        value = _load_json(args.input)
        _write_bytes_atomic(args.output, render_result(value).encode("utf-8"))
    except (OSError, ChapterFactMaterialBundleToolError) as exc:
        print(f"CHAPTER_FACT_MATERIAL_BUNDLE_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "ChapterFactMaterialBundleToolError",
    "render_result",
    "validate_result",
]


if __name__ == "__main__":
    raise SystemExit(main())
