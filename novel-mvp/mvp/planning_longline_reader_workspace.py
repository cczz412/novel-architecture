"""AuthorWorkspace 当前规划中故事线与伏笔的作者只读页。

这里仅排版现役 ``planning_longline_view_workspace.execute`` 结果。它不新增长线
字段、不保存页面、不改规划，也不把规划状态写成已经发生的故事事实。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import planning_longline_view_tool, planning_longline_view_workspace
from .workspace import SHA256_RE, AuthorWorkspace


VIEW_IDENTITY = {
    "name": "AUTHOR_WORKSPACE_CURRENT_PLANNING_LONGLINE_READER_VIEW",
    "version": "v1",
    "projection_only": True,
}
RESULT_KEYS = {
    "identity",
    "version",
    "scope",
    "notice",
    "source_plan_version",
    "source_plan_sha256",
    "status_semantics",
    "storylines",
    "hooks",
    "unavailable",
}
STATUS_SEMANTICS = {
    "storyline_status": "只表示规划中的故事线状态。",
    "hook_status_paid": "只表示已经安排回收，不表示实际兑现。",
    "hook_revealed": "只表示规划中安排揭示，不表示读者实际已知。",
}
SOURCE_IDENTITY_LABELS = {
    "author_declared": "作者明确提供",
    "draft_inferred": "从草稿推得",
    "model_suggested": "模型建议",
}
STORYLINE_STATUS_LABELS = {
    "active": "规划中进行",
    "paused": "规划中暂停",
    "converged": "规划中汇合",
    "merged": "规划中合并",
}
HOOK_STATUS_LABELS = {
    "open": "规划中仍待回收",
    "paid": "规划中已安排回收；不代表故事里已经兑现",
    "voided": "规划中作废",
}


class PlanningLonglineReaderWorkspaceError(RuntimeError):
    """当前规划长线视图不能安全排成作者页面。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise PlanningLonglineReaderWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _string(value: object, *, label: str, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        _fail(f"{label}_INVALID")
    return value


def _integer(value: object, *, label: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{label}_INVALID")
    if minimum is not None and value < minimum:
        _fail(f"{label}_INVALID")
    return value


def _validated_storyline(value: object, index: int) -> dict[str, Any]:
    label = f"STORYLINE_{index}"
    if not isinstance(value, dict) or set(value) != planning_longline_view_tool.STORYLINE_KEYS:
        _fail(f"{label}_INVALID")
    storyline = copy.deepcopy(value)
    storyline_id = _string(storyline["id"], label=f"{label}_ID")
    if (
        storyline_id is None
        or planning_longline_view_tool.STORYLINE_ID_RE.fullmatch(storyline_id)
        is None
    ):
        _fail(f"{label}_ID_INVALID")
    _string(storyline["name"], label=f"{label}_NAME")
    _string(storyline["alias"], label=f"{label}_ALIAS", allow_none=True)
    _integer(storyline["priority"], label=f"{label}_PRIORITY")
    if (
        not isinstance(storyline["members"], list)
        or any(not isinstance(item, str) for item in storyline["members"])
        or any(
            planning_longline_view_tool.CHARACTER_ID_RE.fullmatch(item) is None
            for item in storyline["members"]
        )
        or len(storyline["members"]) != len(set(storyline["members"]))
        or storyline["line_status"] not in STORYLINE_STATUS_LABELS
        or storyline["source_identity"] not in SOURCE_IDENTITY_LABELS
    ):
        _fail(f"{label}_INVALID")
    last_scene_ref = _string(
        storyline["last_scene_ref"],
        label=f"{label}_LAST_SCENE_REF",
        allow_none=True,
    )
    if (
        last_scene_ref is not None
        and planning_longline_view_tool.SCENE_ID_RE.fullmatch(last_scene_ref)
        is None
    ):
        _fail(f"{label}_LAST_SCENE_REF_INVALID")
    _string(storyline["created_at"], label=f"{label}_CREATED_AT")
    _string(storyline["updated_at"], label=f"{label}_UPDATED_AT")
    _integer(storyline["rev"], label=f"{label}_REV", minimum=1)
    _string(storyline["note"], label=f"{label}_NOTE")
    return storyline


def _validated_hook(value: object, index: int) -> dict[str, Any]:
    label = f"HOOK_{index}"
    if not isinstance(value, dict) or set(value) != planning_longline_view_tool.HOOK_KEYS:
        _fail(f"{label}_INVALID")
    hook = copy.deepcopy(value)
    for key in ("id", "content", "created_at", "updated_at", "note", "safety_summary"):
        _string(hook[key], label=f"{label}_{key.upper()}")
    if planning_longline_view_tool.HOOK_ID_RE.fullmatch(hook["id"]) is None:
        _fail(f"{label}_ID_INVALID")
    if (
        hook["source_identity"] not in SOURCE_IDENTITY_LABELS
        or hook["hook_status"] not in HOOK_STATUS_LABELS
        or not isinstance(hook["revealed"], bool)
        or hook["truth_bearing"] not in {"primary", "shadow", "handed_over"}
    ):
        _fail(f"{label}_INVALID")
    for key in ("payoff_slot_ref", "paid_by_ref", "revealed_at"):
        _string(hook[key], label=f"{label}_{key.upper()}", allow_none=True)
    if (
        hook["payoff_slot_ref"] is not None
        and planning_longline_view_tool.SLOT_ID_RE.fullmatch(
            hook["payoff_slot_ref"]
        )
        is None
    ):
        _fail(f"{label}_PAYOFF_SLOT_REF_INVALID")
    if (
        hook["paid_by_ref"] is not None
        and planning_longline_view_tool.EVENT_ID_RE.fullmatch(hook["paid_by_ref"])
        is None
    ):
        _fail(f"{label}_PAID_BY_REF_INVALID")
    if hook["hook_status"] == "paid" and hook["paid_by_ref"] is None:
        _fail(f"{label}_PAID_BY_REF_REQUIRED")
    if hook["revealed"] is True and hook["revealed_at"] is None:
        _fail(f"{label}_REVEALED_AT_REQUIRED")
    _integer(hook["defer_count"], label=f"{label}_DEFER_COUNT", minimum=0)
    _integer(hook["rev"], label=f"{label}_REV", minimum=1)
    if not isinstance(hook["plant_refs"], list):
        _fail(f"{label}_PLANT_REFS_INVALID")
    plants: list[dict[str, str]] = []
    for plant_index, plant in enumerate(hook["plant_refs"]):
        if not isinstance(plant, dict) or set(plant) != planning_longline_view_tool.PLANT_REF_KEYS:
            _fail(f"{label}_PLANT_{plant_index}_INVALID")
        ref = _string(plant["ref"], label=f"{label}_PLANT_{plant_index}_REF")
        note = _string(plant["note"], label=f"{label}_PLANT_{plant_index}_NOTE")
        assert ref is not None and note is not None
        if (
            planning_longline_view_tool.EVENT_ID_RE.fullmatch(ref) is None
            and planning_longline_view_tool.SCENE_ID_RE.fullmatch(ref) is None
        ):
            _fail(f"{label}_PLANT_{plant_index}_REF_INVALID")
        plants.append({"ref": ref, "note": note})
    if len({plant["ref"] for plant in plants}) != len(plants):
        _fail(f"{label}_PLANT_REF_DUPLICATE")
    hook["plant_refs"] = plants
    return hook


def _validated_result(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != RESULT_KEYS
        or value.get("identity") != planning_longline_view_tool.IDENTITY
        or value.get("version") != planning_longline_view_tool.VERSION
        or value.get("scope") != planning_longline_view_tool.SCOPE
        or value.get("notice") != planning_longline_view_tool.NOTICE
        or value.get("status_semantics") != STATUS_SEMANTICS
        or value.get("unavailable") != list(planning_longline_view_tool.UNAVAILABLE)
    ):
        _fail("PLANNING_LONGLINE_VIEW_INVALID")
    source_version = _integer(
        value["source_plan_version"],
        label="SOURCE_PLAN_VERSION",
        minimum=1,
    )
    source_sha = value["source_plan_sha256"]
    if not isinstance(source_sha, str) or SHA256_RE.fullmatch(source_sha) is None:
        _fail("SOURCE_PLAN_SHA_INVALID")
    if not isinstance(value["storylines"], list) or not isinstance(value["hooks"], list):
        _fail("PLANNING_LONGLINE_COLLECTION_INVALID")
    storylines = [
        _validated_storyline(row, index)
        for index, row in enumerate(value["storylines"])
    ]
    hooks = [_validated_hook(row, index) for index, row in enumerate(value["hooks"])]
    if len({row["id"] for row in storylines}) != len(storylines):
        _fail("STORYLINE_ID_DUPLICATE")
    if len({row["id"] for row in hooks}) != len(hooks):
        _fail("HOOK_ID_DUPLICATE")
    return {
        **copy.deepcopy(value),
        "source_plan_version": source_version,
        "source_plan_sha256": source_sha,
        "storylines": storylines,
        "hooks": hooks,
    }


def _indented_block(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(f"    {line}" for line in normalized.split("\n"))


def _labeled_text(lines: list[str], label: str, value: str | None) -> None:
    lines.extend([f"- {label}：", "", _indented_block(value if value is not None else "（无）")])


def _render_storylines(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["## 故事线（只表示当前规划）"]
    if not rows:
        return [*lines, "", "当前规划里还没有故事线。"]
    for index, row in enumerate(rows, start=1):
        lines.extend(["", f"### {index}. 故事线", ""])
        _labeled_text(lines, "编号", row["id"])
        _labeled_text(lines, "名称", row["name"])
        _labeled_text(lines, "别名", row["alias"])
        lines.extend(
            [
                "",
                f"- 优先级：`{row['priority']}`",
                f"- 规划状态：{STORYLINE_STATUS_LABELS[row['line_status']]}",
                f"- 来源身份：{SOURCE_IDENTITY_LABELS[row['source_identity']]}",
                f"- 当前修订：`{row['rev']}`",
            ]
        )
        _labeled_text(lines, "最近场景", row["last_scene_ref"])
        if row["members"]:
            lines.extend(["- 关联人物：", ""])
            for member in row["members"]:
                lines.append(_indented_block(member))
        else:
            _labeled_text(lines, "关联人物", None)
        _labeled_text(lines, "备注", row["note"] or None)
    return lines


def _render_hooks(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["## 伏笔（只表示当前规划）"]
    if not rows:
        return [*lines, "", "当前规划里还没有伏笔。"]
    for index, row in enumerate(rows, start=1):
        lines.extend(["", f"### {index}. 伏笔", ""])
        _labeled_text(lines, "编号", row["id"])
        _labeled_text(lines, "内容", row["content"])
        lines.extend(
            [
                "",
                f"- 规划状态：{HOOK_STATUS_LABELS[row['hook_status']]}",
                f"- 规划中安排揭示：{'是；不代表读者已经知道' if row['revealed'] else '否'}",
                f"- 推迟次数：`{row['defer_count']}`",
                f"- 来源身份：{SOURCE_IDENTITY_LABELS[row['source_identity']]}",
                f"- 当前修订：`{row['rev']}`",
            ]
        )
        _labeled_text(lines, "计划回收章槽", row["payoff_slot_ref"])
        _labeled_text(lines, "计划回收事件", row["paid_by_ref"])
        _labeled_text(lines, "计划揭示位置", row["revealed_at"])
        _labeled_text(lines, "安全说明", row["safety_summary"])
        if row["plant_refs"]:
            lines.extend(["- 埋点：", ""])
            for plant_index, plant in enumerate(row["plant_refs"], start=1):
                lines.append(f"    {plant_index}. 位置")
                lines.append(_indented_block(plant["ref"]))
                lines.append("    说明")
                lines.append(_indented_block(plant["note"] or "（无）"))
        else:
            _labeled_text(lines, "埋点", None)
        _labeled_text(lines, "备注", row["note"] or None)
    return lines


def _render_markdown(view: dict[str, Any]) -> str:
    lines = [
        "# 当前规划里的故事线与伏笔｜只读",
        "",
        "> 这些内容是未来规划，不表示故事已经发生。",
        "> “已安排回收”不代表正文已经兑现；“安排揭示”不代表读者已经知道。",
        "",
        f"- 当前规划版本：`{view['source_plan_version']}`",
        f"- 当前规划 SHA256：`{view['source_plan_sha256']}`",
        f"- 故事线数量：`{len(view['storylines'])}`",
        f"- 伏笔数量：`{len(view['hooks'])}`",
        "",
        *_render_storylines(view["storylines"]),
        "",
        *_render_hooks(view["hooks"]),
        "",
        "## 当前还没有固定存储的长线内容",
        "",
    ]
    for item in view["unavailable"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本页读取的是当前规划账中的故事线和伏笔。",
            "- 本页没有生成或修改规划。",
            "- 本页没有写入事实账、长线账或其他账本。",
            "- 本页不是独立长线账已经建成的证明。",
            "",
        ]
    )
    return "\n".join(lines)


def read_current_planning_longline_view(
    workspace: AuthorWorkspace,
) -> dict[str, Any]:
    """读出 current plan 的故事线和伏笔，并排成作者可读 Markdown。"""
    handle = _require_workspace(workspace)
    try:
        raw = planning_longline_view_workspace.execute(handle)
    except planning_longline_view_workspace.PlanningLonglineViewWorkspaceError as exc:
        raise PlanningLonglineReaderWorkspaceError(
            f"CURRENT_PLANNING_LONGLINE_READ_REJECTED:{exc}"
        ) from exc
    view = _validated_result(raw)
    status = "EMPTY" if not view["storylines"] and not view["hooks"] else "READY"
    return {
        "status": status,
        "encoding": "UTF-8",
        "view_identity": copy.deepcopy(VIEW_IDENTITY),
        "source_plan_snapshot": {
            "version": view["source_plan_version"],
            "sha256": view["source_plan_sha256"],
        },
        "storyline_count": len(view["storylines"]),
        "hook_count": len(view["hooks"]),
        "unavailable": copy.deepcopy(view["unavailable"]),
        "markdown": _render_markdown(view),
    }


__all__ = [
    "PlanningLonglineReaderWorkspaceError",
    "read_current_planning_longline_view",
]
