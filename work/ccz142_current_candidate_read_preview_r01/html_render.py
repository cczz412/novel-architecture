"""Turn the Markdown human card into a double-clickable HTML page.

This package does not read the store itself. It reuses prove_current_read
and render_markdown, then wraps the same page as HTML a person can open.
"""

from __future__ import annotations

import html as html_lib
import sys
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, DISPLAY_ROOT, PROOF_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from card_render import render_markdown, show_current_card  # noqa: E402

DOCUMENT_IDENTITY = "CCZ142-CURRENT-CANDIDATE-READ-PREVIEW-R01"
GITHUB_ISSUE = 268
BASE_MAIN_SHA = "9364598dad5fd51e2acf1bbafd34e7e19b7554ba"
PAGE_TITLE = "抽出了什么（人话结果卡）"
TYPES_DISCLAIMER = (
    "> 这是夹具样张，用来看「传闻／误信／未证实」长什么样。"
    "不是活库读出，也不是产品权威。\n\n"
)
FIXTURE_LAYOUT_MD = (
    DISPLAY_ROOT / "samples" / "fixture_layout.md"
)


def types_proof() -> dict[str, Any]:
    """Synthetic card so the types row is visible. Not a live store read."""

    return {
        "status": "READ_OK",
        "identity": {
            "pointer_namespace": "FIXTURE_ONLY",
            "candidate_access": "POLICY_FIXTURE_READ_ONLY",
            "product_adopted": False,
        },
        "read_path": {
            "store_class": (
                "work/ccz142_candidate_authority_r01/"
                "candidate_authority.py::CandidateAuthorityStore"
            ),
            "read_pointer": "B06CommitStore.read_pointer",
            "read_candidate": "B06CommitStore.read_candidate",
        },
        "pointer_key": "fixture-types-sample",
        "result_scope": {
            "book_title": "未提供",
            "project_scope_id": "未提供",
            "chapter_id": "未提供",
            "revision_no": "未提供",
            "revision_text_sha256": "未提供",
            "responsibility_segment": "未提供",
            "display_range": "当前指针指向的这一份候选。不是已确认的整章汇总。",
            "chapter_completeness": "未确认",
            "density": "尚未提供，不编数字",
        },
        "human_card": {
            "items": [
                {
                    "fact": "甲进入北塔。",
                    "status": "已发生",
                    "kind": "已发生",
                    "evidence": "甲走进北塔。",
                },
                {
                    "fact": "有人说北塔夜里有人影。",
                    "status": "推测",
                    "kind": "传闻／怀疑",
                    "evidence": "守夜的人说看见人影。",
                },
                {
                    "fact": "甲以为铜钥匙能开南门。",
                    "status": "误信",
                    "kind": "误信",
                    "evidence": "甲把铜钥匙往南门孔里塞。",
                    "speaker": "旁白",
                },
                {
                    "fact": "乙答应明天来接应。",
                    "status": "承诺",
                    "kind": "未证实",
                    "evidence": "乙说明天来接应。",
                },
            ]
        },
        "gaps": [],
        "limitations": ["GAP_NOT_PRODUCT_IDENTITY"],
        "standing_boundaries": ["GAP_REAL_NOVEL_NOT_IN_SCOPE"],
    }


def _inline(text: str) -> str:
    pieces = text.split("`")
    out: list[str] = []
    for index, piece in enumerate(pieces):
        escaped = html_lib.escape(piece)
        if index % 2 == 0:
            out.append(escaped)
        else:
            out.append(f"<code>{escaped}</code>")
    return "".join(out)


def markdown_to_html_body(markdown: str) -> str:
    """Tiny converter for this card's headings, quotes, lists, and code."""

    lines = markdown.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("> ") or line == ">":
            quotes: list[str] = []
            while index < len(lines) and (
                lines[index].startswith("> ") or lines[index] == ">"
            ):
                quotes.append("" if lines[index] == ">" else lines[index][2:])
                index += 1
            index -= 1
            inner = "<br />\n".join(
                _inline(quote) if quote else "&nbsp;" for quote in quotes
            )
            out.append(f'<blockquote>{inner}</blockquote>')
        elif line.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(f"<li>{_inline(lines[index][2:])}</li>")
                index += 1
            index -= 1
            out.append("<ul>\n" + "\n".join(items) + "\n</ul>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
        index += 1
    return "\n".join(out)


def page_html(markdown: str) -> str:
    body = markdown_to_html_body(markdown)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-Hans">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        f"<title>{html_lib.escape(PAGE_TITLE)}</title>\n"
        "<style>\n"
        "body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
        "'Noto Sans SC',sans-serif;max-width:42rem;margin:2rem auto;"
        "padding:0 1.25rem 3rem;line-height:1.65;color:#1f1f1f;"
        "background:#faf8f4;}\n"
        "h1{font-size:1.6rem;margin:0 0 1rem;}\n"
        "h2{font-size:1.15rem;margin:1.6rem 0 0.6rem;border-bottom:"
        "1px solid #e6e0d4;padding-bottom:0.25rem;}\n"
        "h3{font-size:1.05rem;margin:1.1rem 0 0.35rem;}\n"
        "blockquote{margin:0 0 1rem;padding:0.75rem 1rem;background:#fff6d6;"
        "border-left:4px solid #e2b93d;}\n"
        "ul{padding-left:1.2rem;}\n"
        "code{font-family:ui-monospace,Menlo,monospace;font-size:0.88em;"
        "background:#eee8dc;padding:0.1em 0.35em;border-radius:4px;}\n"
        "p.foot{color:#666;margin-top:2rem;}\n"
        "</style>\n"
        "</head>\n"
        f"<body>\n{body}\n</body>\n</html>\n"
    )


def render_html(proof: dict[str, Any]) -> str:
    return page_html(render_markdown(proof))


def types_preview_html() -> str:
    return page_html(TYPES_DISCLAIMER + render_markdown(types_proof()))


def fixture_layout_html() -> str:
    return page_html(FIXTURE_LAYOUT_MD.read_text(encoding="utf-8"))


def show_current_html(
    *,
    store_root: Path | None = None,
    project_scope_id: str = "fixture-project-001",
    pointer_key: str | None = None,
) -> dict[str, Any]:
    shown = show_current_card(
        store_root=store_root,
        project_scope_id=project_scope_id,
        pointer_key=pointer_key,
    )
    return {
        "proof": shown["proof"],
        "markdown": shown["markdown"],
        "html": page_html(shown["markdown"]),
    }
