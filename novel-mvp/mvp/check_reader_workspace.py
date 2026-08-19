"""已保存 M7 报告的一键只读视图。

这里只组合现役 ``check_workspace.read_saved`` 与
``check_tool.render_report``。它不接路径或身份文本，不生成报告、不调用
provider，也不把人读视图写回 AuthorWorkspace。
"""

from __future__ import annotations

import copy
from typing import Any, NoReturn

from . import check_tool, check_workspace
from .workspace import AuthorWorkspace


VIEW_KEYS = {
    "health_report_snapshot",
    "facts_snapshot",
    "chapter_index_snapshot",
    "current_facts_snapshot",
    "current_chapter_index_snapshot",
    "stale_reasons",
    "m7",
}
STALE_REASON_LABELS = {
    "FACTS_SNAPSHOT_ADVANCED": "事实账水位已前进",
    "CHAPTER_INDEX_SNAPSHOT_ADVANCED": "章节索引水位已前进",
}


class CheckReaderWorkspaceError(RuntimeError):
    """保存报告在连续读取中不稳定，或返回形状不符合现役接口。"""


def _fail(code: str) -> NoReturn:
    raise CheckReaderWorkspaceError(code)


def _require_workspace(value: object) -> AuthorWorkspace:
    if not isinstance(value, AuthorWorkspace):
        _fail("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    return value


def _snapshot(
    value: object,
    *,
    label: str,
    minimum_version: int = 0,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "sha256"}
        or not isinstance(value.get("version"), int)
        or isinstance(value["version"], bool)
        or value["version"] < minimum_version
    ):
        _fail(f"{label}_SNAPSHOT_INVALID")
    sha256 = value["sha256"]
    if value["version"] == 0:
        if sha256 is not None:
            _fail(f"{label}_SNAPSHOT_INVALID")
    elif (
        not isinstance(sha256, str)
        or check_tool.SHA256_RE.fullmatch(sha256) is None
    ):
        _fail(f"{label}_SNAPSHOT_INVALID")
    return {"version": value["version"], "sha256": sha256}


def _stable_identity(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != VIEW_KEYS
        or not isinstance(value.get("m7"), dict)
        or not isinstance(value.get("stale_reasons"), list)
        or any(
            not isinstance(reason, str) or not reason
            for reason in value["stale_reasons"]
        )
        or len(value["stale_reasons"]) != len(set(value["stale_reasons"]))
    ):
        _fail("SAVED_REPORT_VIEW_INVALID")
    state = value["m7"].get("source_revision_state")
    reasons = list(value["stale_reasons"])
    if state not in {"CURRENT", "STALE"}:
        _fail("SAVED_REPORT_STATE_INVALID")
    if (state == "CURRENT" and reasons) or (state == "STALE" and not reasons):
        _fail("SAVED_REPORT_STATE_REASON_MISMATCH")
    return {
        "health_report_snapshot": _snapshot(
            value["health_report_snapshot"],
            label="HEALTH_REPORT",
            minimum_version=1,
        ),
        "current_facts_snapshot": _snapshot(
            value["current_facts_snapshot"],
            label="CURRENT_FACTS",
        ),
        "current_chapter_index_snapshot": _snapshot(
            value["current_chapter_index_snapshot"],
            label="CURRENT_CHAPTER_INDEX",
        ),
        "state": state,
        "stale_reasons": reasons,
    }


def _empty_result() -> dict[str, Any]:
    return {
        "status": "EMPTY",
        "encoding": "UTF-8",
        "health_report_snapshot": None,
        "current_facts_snapshot": None,
        "current_chapter_index_snapshot": None,
        "stale_reasons": [],
        "text": (
            "【暂无已保存体检报告】\n"
            "状态：EMPTY\n"
            "没有可读取的已保存报告；本次未生成或重跑报告。\n"
        ),
    }


def _view_text(state: str, reasons: list[str], body: str) -> str:
    if state == "CURRENT":
        heading = "【当前体检报告】\n状态：CURRENT\n"
    else:
        reason_lines = "\n".join(
            f"- {STALE_REASON_LABELS.get(reason, '来源水位发生变化')}（{reason}）"
            for reason in reasons
        )
        heading = (
            "【历史体检报告｜已过期】\n"
            "状态：STALE\n"
            "警示：下面内容来自历史报告，不能当作当前报告。\n"
            f"过期原因：\n{reason_lines}\n"
        )
    return f"{heading}\n{body}"


def read_author_view(workspace: AuthorWorkspace) -> dict[str, Any]:
    """连续读取两次稳定副本，再返回作者可直接展示的人读结果。"""

    handle = _require_workspace(workspace)
    first = check_workspace.read_saved(handle)
    second = check_workspace.read_saved(handle)
    if first is None or second is None:
        if first is None and second is None:
            return _empty_result()
        _fail("SAVED_REPORT_CHANGED_DURING_READ")
    first_identity = _stable_identity(first)
    second_identity = _stable_identity(second)
    if first_identity != second_identity:
        _fail("SAVED_REPORT_CHANGED_DURING_READ")
    report = copy.deepcopy(second["m7"])
    body = check_tool.render_report(report)
    state = second_identity["state"]
    reasons = copy.deepcopy(second_identity["stale_reasons"])
    return {
        "status": state,
        "encoding": "UTF-8",
        "health_report_snapshot": copy.deepcopy(
            second_identity["health_report_snapshot"]
        ),
        "current_facts_snapshot": copy.deepcopy(
            second_identity["current_facts_snapshot"]
        ),
        "current_chapter_index_snapshot": copy.deepcopy(
            second_identity["current_chapter_index_snapshot"]
        ),
        "stale_reasons": reasons,
        "text": _view_text(state, reasons, body),
    }


__all__ = ["CheckReaderWorkspaceError", "read_author_view"]
