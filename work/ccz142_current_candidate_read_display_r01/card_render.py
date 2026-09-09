"""Render a current-candidate proof into a human Markdown card.

This package does not read the store itself. It displays what
`prove_current_read` already returned, or a typed gap page.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, PROOF_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from current_read_proof import STATUS_READ_OK, prove_current_read  # noqa: E402

DOCUMENT_IDENTITY = "CCZ142-CURRENT-CANDIDATE-READ-DISPLAY-R01"
GITHUB_ISSUE = 266
BASE_MAIN_SHA = "177c5832df9527cdcee3eaa513aafeda335550ea"
COVERAGE_NOT_WIRED = "覆盖／漏抽尚未提供：这张卡还没接到 B02，本卡目前不能判断是否抽全。"
DENSITY_NOT_WIRED = "密度（仅说明本次已返回的候选）：尚未提供。还没有可核对的候选信息分布说明。"
EMPTY_READ_GAPS = "读取缺口：无。这不等于没有漏抽。"
CARD_TITLE = "抽出了什么（人话结果卡）"
SCOPE_UNPROVIDED = "未提供"


def _scope_line(label: str, value: object) -> str:
    if value is None or value == "":
        shown = SCOPE_UNPROVIDED
    else:
        shown = str(value)
    return f"- {label}：{shown}"


def render_scope_section(proof: dict[str, Any]) -> list[str]:
    scope = proof.get("result_scope") if isinstance(proof.get("result_scope"), dict) else {}
    lines = [
        "## 这张卡对应哪一段",
        _scope_line("书名", scope.get("book_title") or SCOPE_UNPROVIDED),
        _scope_line("项目", scope.get("project_scope_id") or SCOPE_UNPROVIDED),
        _scope_line("章节", scope.get("chapter_id") or SCOPE_UNPROVIDED),
        _scope_line("修订", scope.get("revision_no") or SCOPE_UNPROVIDED),
        _scope_line("修订正文哈希", scope.get("revision_text_sha256") or SCOPE_UNPROVIDED),
        _scope_line("责任段", scope.get("responsibility_segment") or SCOPE_UNPROVIDED),
        _scope_line(
            "展示范围",
            scope.get("display_range") or "当前指针指向的这一份候选。不是已确认的整章汇总。",
        ),
        _scope_line("整章完整性", scope.get("chapter_completeness") or "未确认"),
        "",
    ]
    return lines


GAP_LABELS = {
    "GAP_NO_LIVE_STORE": "没人给出权威库路径。读路仍写在下面。",
    "GAP_STORE_MISSING": "路径上没有库，或打不开。",
    "GAP_POINTER_MISSING": "库在，current 指针不在。",
    "GAP_POINTER_AMBIGUOUS": "库里多于一个指针，又没指定是哪一条。",
    "GAP_CANDIDATE_MISSING": "指针在，候选版本不在或对不上。",
    "GAP_NO_HUMAN_ITEMS": "候选读到了，但没有可展示的事实条目。",
    "GAP_NOT_PRODUCT_IDENTITY": "读到了，但身份仍是夹具。这是限制，不是崩。",
    "GAP_REAL_NOVEL_NOT_IN_SCOPE": "真实小说 API 不在本票范围。",
}


def _gap_line(code: str) -> str:
    meaning = GAP_LABELS.get(code, "稳定缺口。")
    return f"- `{code}`：{meaning}"


def render_markdown(proof: dict[str, Any]) -> str:
    """Turn a proof dict into a page a person can open and read."""

    lines: list[str] = [f"# {CARD_TITLE}", ""]
    identity = proof.get("identity") if isinstance(proof.get("identity"), dict) else {}
    namespace = identity.get("pointer_namespace")
    access = identity.get("candidate_access")
    if proof.get("status") == STATUS_READ_OK:
        lines.append(
            f"> 身份：夹具 current（`{namespace}`／`{access}`）。"
            "不是产品权威，也不是正式事实。"
        )
    else:
        lines.append("> 还读不到一张可展示的 current 卡。下面是缺口，不是编出来的条目。")
        if namespace:
            lines.append(">")
            lines.append(f"> 已读到的身份：`{namespace}`。仍不是产品采用。")
    lines.append("")
    lines.extend(render_scope_section(proof))
    lines.append("## 读路")
    read_path = proof.get("read_path") if isinstance(proof.get("read_path"), dict) else {}
    store_class = read_path.get("store_class", "未知")
    lines.append(f"- 库：`{store_class}`")
    lines.append(f"- 指针：`{read_path.get('read_pointer', '未知')}`")
    lines.append(f"- 候选：`{read_path.get('read_candidate', '未知')}`")
    pointer_key = proof.get("pointer_key")
    if pointer_key:
        lines.append(f"- 当前指针：`{pointer_key}`")
    lines.append("")

    card = proof.get("human_card") if isinstance(proof.get("human_card"), dict) else None
    items = card.get("items") if card else None
    lines.append("## 条目")
    if isinstance(items, list) and items:
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            fact = str(item.get("fact") or "").strip()
            status = str(item.get("status") or "").strip()
            kind = str(item.get("kind") or "").strip()
            evidence = str(item.get("evidence") or "").strip()
            speaker = item.get("speaker")
            lines.append(f"### {index}. {fact}")
            if status:
                lines.append(f"- 状态：{status}")
            if kind:
                lines.append(f"- 类型：{kind}")
            if evidence:
                lines.append(f"- 证据：{evidence}")
            stable = str(item.get("stable_item_id") or "").strip() or SCOPE_UNPROVIDED
            source_location = str(item.get("source_location") or "").strip() or SCOPE_UNPROVIDED
            lines.append(f"- 稳定条目：{stable}")
            lines.append(f"- 原文位置：{source_location}")
            if isinstance(speaker, str) and speaker:
                lines.append(f"- 说话人：{speaker}")
            lines.append("")
    else:
        lines.append("没有可展示的事实条目。")
        lines.append("")

    settle = proof.get("settlement_view")
    if not isinstance(settle, dict):
        settle = {}
    if settle.get("wired") is True:
        lines.append("## 抽取结算")
        score_line = settle.get("score_line")
        if isinstance(score_line, str) and score_line:
            lines.append(f"- {score_line}")
        concern = settle.get("concern")
        if isinstance(concern, str) and concern:
            lines.append(f"- {concern}")
    else:
        lines.append("## 还没接到的层")
        lines.append(f"- {COVERAGE_NOT_WIRED}")
        lines.append(f"- {DENSITY_NOT_WIRED}")
    lines.append("")

    limitations = proof.get("limitations") if isinstance(proof.get("limitations"), list) else []
    lines.append("## 限制")
    if limitations:
        for code in limitations:
            lines.append(_gap_line(str(code)))
    else:
        lines.append("无。")
    lines.append("")

    gaps = proof.get("gaps") if isinstance(proof.get("gaps"), list) else []
    lines.append("## 缺口")
    if gaps:
        for code in gaps:
            lines.append(_gap_line(str(code)))
    else:
        lines.append(EMPTY_READ_GAPS)
    lines.append("")

    standing = proof.get("standing_boundaries") if isinstance(proof.get("standing_boundaries"), list) else []
    lines.append("## 常驻边界")
    if standing:
        for code in standing:
            lines.append(_gap_line(str(code)))
    else:
        lines.append(_gap_line("GAP_REAL_NOVEL_NOT_IN_SCOPE"))
    lines.append("")
    lines.append("本页没有修补条目，也不教你怎么写下一句。")
    lines.append("")
    return "\n".join(lines)


def show_current_card(
    *,
    store_root: Path | None = None,
    project_scope_id: str = "fixture-project-001",
    pointer_key: str | None = None,
) -> dict[str, Any]:
    proof = prove_current_read(
        store_root=store_root,
        project_scope_id=project_scope_id,
        pointer_key=pointer_key,
    )
    markdown = render_markdown(proof)
    return {"proof": proof, "markdown": markdown}
