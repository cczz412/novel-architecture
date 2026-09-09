"""Drop a named, rights-released chapter TXT into the existing human card."""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import sys
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WIRE_ROOT = REPOSITORY_ROOT / "work" / "ccz142_human_card_vertical_wire_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, WIRE_ROOT, PREVIEW_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from html_render import show_current_html  # noqa: E402
from vertical_wire import (  # noqa: E402
    DATABASE_FILENAME,
    DEFAULT_PROJECT_SCOPE_ID,
    wire_synthetic_chapter_to_card,
)

DOCUMENT_IDENTITY = "CCZ142-NAMED-CHAPTER-TXT-CARD-R01"
GITHUB_ISSUE = 297
BASE_MAIN_SHA = "80b9485fbe47ff2e71d5066b7ff640eb51c48c9c"
ALLOWLIST_PATH = MODULE_ROOT / "ALLOWLIST.json"
STATUS_DROPPED = "DROPPED"
STATUS_CLOSED = "CLOSED"
GAP_NOT_RELEASED = "GAP_NOT_RELEASED"
GAP_PATH_NOT_RELEASED = "GAP_PATH_NOT_RELEASED"
GAP_CHAPTER_MISMATCH = "GAP_CHAPTER_MISMATCH"
GAP_NO_STORE_ROOT = "GAP_NO_STORE_ROOT"
GAP_NO_TXT = "GAP_NO_TXT"
GAP_REAL_NOVEL_NOT_IN_SCOPE = "GAP_REAL_NOVEL_NOT_IN_SCOPE"
SHA_UNPROVIDED = "尚未提供"
FORBIDDEN_PATH_PARTS = {
    "corpus-downloads",
    "trial_seven_books",
    "earlier_extract_ch01-50",
    "newbook_unseen_by_models",
    "_newbook_rank_20260804",
    "golden-three-chapters",
}


def load_allowlist() -> dict[str, Any]:
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def find_allowlist_entry(book: str, chapter_no: int) -> dict[str, Any] | None:
    needle = book.strip()
    for entry in load_allowlist()["entries"]:
        if entry["chapter_no"] != chapter_no:
            continue
        if needle in {entry["book_id"], entry["book_title"]}:
            return entry
    return None


def chapter_text_sha256(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def path_is_blocked(path: Path) -> bool:
    candidates = [path]
    try:
        candidates.append(path.expanduser().resolve(strict=False))
    except OSError:
        pass
    for candidate in candidates:
        if any(part in FORBIDDEN_PATH_PARTS for part in candidate.parts):
            return True
    return False


def compose_drop_page(
    *,
    book_title: str,
    chapter_no: int,
    released: bool,
    inner_html: str,
    inner_markdown: str,
) -> tuple[str, str]:
    rights = "夹具放行" if released else "未放行／未写入"
    header_md = (
        f"这次丢进：**{book_title}** 第 {chapter_no} 章（{rights}）。"
        "身份 `FIXTURE_ONLY`。覆盖／密度尚未提供。\n\n"
    )
    banner = (
        '<section class="drop-identity" style="margin:0 0 1.25rem;'
        "padding:0.75rem 1rem;background:#eef4ff;"
        'border-left:4px solid #3d6ee2;">'
        f"<p>这次丢进：<strong>{html_lib.escape(book_title)}</strong>"
        f" 第 {chapter_no} 章（{html_lib.escape(rights)}）。"
        "身份 <code>FIXTURE_ONLY</code>。覆盖／密度尚未提供。</p>"
        "</section>\n"
    )
    if "<body>" in inner_html:
        html_out = inner_html.replace("<body>", "<body>\n" + banner, 1)
    else:
        html_out = banner + inner_html
    return html_out, header_md + inner_markdown


def _closed(
    *,
    gaps: list[str],
    book: str,
    chapter_no: int,
    entry: dict[str, Any] | None,
    txt_bytes_read: bool,
    sha256: str = SHA_UNPROVIDED,
) -> dict[str, Any]:
    shown = show_current_html()
    title = entry["book_title"] if entry else book
    html_out, markdown = compose_drop_page(
        book_title=title,
        chapter_no=chapter_no,
        released=False,
        inner_html=shown["html"],
        inner_markdown=shown["markdown"],
    )
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": STATUS_CLOSED,
        "gaps": gaps,
        "wrote": False,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "standing_boundaries": [GAP_REAL_NOVEL_NOT_IN_SCOPE],
        "drop": {
            "book": book,
            "book_title": title,
            "book_id": entry["book_id"] if entry else SHA_UNPROVIDED,
            "chapter_no": chapter_no,
            "rights": entry["rights"] if entry else "NOT_RELEASED",
            "txt_bytes_read": txt_bytes_read,
            "chapter_text_sha256": sha256,
        },
        "shown": shown,
        "html": html_out,
        "markdown": markdown,
        "proof": shown["proof"],
    }


def drop_named_chapter(
    *,
    book: str,
    chapter_no: int,
    txt_path: Path | None = None,
    store_root: Path | None = None,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
) -> dict[str, Any]:
    """Named book+chapter drop. Unreleased or wrong chapter never writes."""

    entry = find_allowlist_entry(book, chapter_no)
    if entry is None:
        return _closed(
            gaps=[GAP_NOT_RELEASED],
            book=book,
            chapter_no=chapter_no,
            entry=None,
            txt_bytes_read=False,
        )

    target = txt_path
    if target is None:
        target = REPOSITORY_ROOT / entry["source_txt_repo_path"]
    target = Path(target)
    if path_is_blocked(target):
        return _closed(
            gaps=[GAP_PATH_NOT_RELEASED],
            book=book,
            chapter_no=chapter_no,
            entry=entry,
            txt_bytes_read=False,
        )
    if store_root is None:
        return _closed(
            gaps=[GAP_NO_STORE_ROOT],
            book=book,
            chapter_no=chapter_no,
            entry=entry,
            txt_bytes_read=False,
        )
    if not target.is_file():
        return _closed(
            gaps=[GAP_NO_TXT],
            book=book,
            chapter_no=chapter_no,
            entry=entry,
            txt_bytes_read=False,
        )

    stripped = target.read_text(encoding="utf-8").strip()
    digest = chapter_text_sha256(stripped)
    if digest != entry["chapter_text_sha256"]:
        return _closed(
            gaps=[GAP_CHAPTER_MISMATCH],
            book=book,
            chapter_no=chapter_no,
            entry=entry,
            txt_bytes_read=True,
            sha256=digest,
        )

    wired = wire_synthetic_chapter_to_card(
        chapter_text=stripped,
        store_root=store_root,
        project_scope_id=project_scope_id,
    )
    html_out, markdown = compose_drop_page(
        book_title=entry["book_title"],
        chapter_no=chapter_no,
        released=True,
        inner_html=wired["html"],
        inner_markdown=wired["markdown"],
    )
    if wired.get("wrote") is not True:
        return _closed(
            gaps=list(wired.get("gaps") or [GAP_CHAPTER_MISMATCH]),
            book=book,
            chapter_no=chapter_no,
            entry=entry,
            txt_bytes_read=True,
            sha256=digest,
        )
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": STATUS_DROPPED,
        "gaps": [],
        "wrote": True,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "pointer_key": wired["pointer_key"],
        "extraction_item_count": wired["extraction_item_count"],
        "standing_boundaries": [GAP_REAL_NOVEL_NOT_IN_SCOPE],
        "drop": {
            "book": book,
            "book_title": entry["book_title"],
            "book_id": entry["book_id"],
            "chapter_no": chapter_no,
            "rights": entry["rights"],
            "txt_bytes_read": True,
            "chapter_text_sha256": digest,
        },
        "shown": wired["shown"],
        "html": html_out,
        "markdown": markdown,
        "proof": wired["proof"],
        "database_filename": DATABASE_FILENAME,
    }


def dumps_result(result: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in result.items()
        if key not in {"shown", "html", "markdown"}
    }
    payload["proof"] = result["proof"]
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
