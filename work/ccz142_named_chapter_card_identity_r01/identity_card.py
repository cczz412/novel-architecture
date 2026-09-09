"""Stamp named book/chapter onto the existing human card scope fields."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NAMED_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_txt_card_r01"
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    NAMED_ROOT,
    DISPLAY_ROOT,
    PREVIEW_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from card_render import render_markdown  # noqa: E402
from html_render import page_html, show_current_html  # noqa: E402
from named_chapter import (  # noqa: E402
    DATABASE_FILENAME,
    DEFAULT_PROJECT_SCOPE_ID,
    STATUS_DROPPED,
    compose_drop_page,
    drop_named_chapter,
    dumps_result as dumps_named_result,
)

DOCUMENT_IDENTITY = "CCZ142-NAMED-CHAPTER-CARD-IDENTITY-R01"
GITHUB_ISSUE = 299
BASE_MAIN_SHA = "427e5c891285978e419f63f27984648e6e98e3c4"


def stamp_scope_identity(
    proof: dict[str, Any],
    *,
    book_title: str,
    chapter_no: int,
) -> dict[str, Any]:
    stamped = deepcopy(proof)
    scope = stamped.get("result_scope")
    if not isinstance(scope, dict):
        scope = {}
        stamped["result_scope"] = scope
    scope["book_title"] = book_title
    scope["chapter_id"] = str(chapter_no)
    return stamped


def _render_existing_card(
    proof: dict[str, Any],
    *,
    book_title: str,
    chapter_no: int,
    released: bool,
) -> tuple[str, str]:
    markdown = render_markdown(proof)
    html = page_html(markdown)
    return compose_drop_page(
        book_title=book_title,
        chapter_no=chapter_no,
        released=released,
        inner_html=html,
        inner_markdown=markdown,
    )


def drop_named_chapter_with_card_identity(
    *,
    book: str,
    chapter_no: int,
    txt_path: Path | None = None,
    store_root: Path | None = None,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
) -> dict[str, Any]:
    """Drop via #298, then put book/chapter on the existing card scope lines."""

    dropped = drop_named_chapter(
        book=book,
        chapter_no=chapter_no,
        txt_path=txt_path,
        store_root=store_root,
        project_scope_id=project_scope_id,
    )
    result = dict(dropped)
    result["document_identity"] = DOCUMENT_IDENTITY
    result["github_issue"] = GITHUB_ISSUE
    result["base_main_sha"] = BASE_MAIN_SHA

    if dropped["status"] == STATUS_DROPPED:
        title = str(dropped["drop"]["book_title"])
        stamped = stamp_scope_identity(
            dropped["proof"],
            book_title=title,
            chapter_no=chapter_no,
        )
        html, markdown = _render_existing_card(
            stamped,
            book_title=title,
            chapter_no=chapter_no,
            released=True,
        )
        result["proof"] = stamped
        result["html"] = html
        result["markdown"] = markdown
        result["identity_stamped"] = True
        return result

    store_file = None
    if store_root is not None:
        store_file = Path(store_root) / DATABASE_FILENAME
    if store_file is not None and store_file.is_file():
        shown = show_current_html(
            store_root=Path(store_root),
            project_scope_id=project_scope_id,
        )
        attempted = str(dropped["drop"].get("book_title") or book)
        html, markdown = compose_drop_page(
            book_title=attempted,
            chapter_no=chapter_no,
            released=False,
            inner_html=shown["html"],
            inner_markdown=shown["markdown"],
        )
        result["html"] = html
        result["markdown"] = markdown
        result["proof"] = shown["proof"]
        result["identity_stamped"] = False
        return result

    result["identity_stamped"] = False
    return result


def dumps_result(result: dict[str, Any]) -> str:
    return dumps_named_result(result)
