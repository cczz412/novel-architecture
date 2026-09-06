"""Persist named book/chapter beside the store, then reopen the existing card."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_card_identity_r01"
NAMED_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_txt_card_r01"
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    IDENTITY_ROOT,
    NAMED_ROOT,
    DISPLAY_ROOT,
    PREVIEW_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from card_render import render_markdown  # noqa: E402
from html_render import page_html, show_current_html  # noqa: E402
from identity_card import (  # noqa: E402
    drop_named_chapter_with_card_identity,
    stamp_scope_identity,
)
from named_chapter import (  # noqa: E402
    DEFAULT_PROJECT_SCOPE_ID,
    STATUS_CLOSED,
    STATUS_DROPPED,
    compose_drop_page,
    dumps_result as dumps_named_result,
)

DOCUMENT_IDENTITY = "CCZ142-NAMED-IDENTITY-STORE-R01"
GITHUB_ISSUE = 301
BASE_MAIN_SHA = "4856209bdb2817c875474e3ae5baecae66f43f96"
IDENTITY_FILENAME = "named-card-identity.json"


def identity_path(store_root: Path) -> Path:
    return Path(store_root) / IDENTITY_FILENAME


def load_stored_identity(store_root: Path) -> dict[str, Any] | None:
    target = identity_path(store_root)
    if not target.is_file():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    title = payload.get("book_title")
    chapter_no = payload.get("chapter_no")
    if not isinstance(title, str) or not title:
        return None
    if not isinstance(chapter_no, int) or isinstance(chapter_no, bool):
        return None
    return payload


def write_stored_identity(
    store_root: Path,
    *,
    drop_result: dict[str, Any],
) -> Path:
    drop = drop_result.get("drop") if isinstance(drop_result.get("drop"), dict) else {}
    payload = {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "book_title": drop.get("book_title"),
        "book_id": drop.get("book_id"),
        "chapter_no": drop.get("chapter_no"),
        "rights": drop.get("rights"),
        "pointer_key": drop_result.get("pointer_key"),
        "pointer_namespace": "FIXTURE_ONLY",
        "product_adopted": False,
    }
    target = identity_path(store_root)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _render_with_identity(
    proof: dict[str, Any],
    *,
    book_title: str,
    chapter_no: int,
    released: bool,
    banner_title: str | None = None,
    banner_chapter_no: int | None = None,
) -> tuple[str, str, dict[str, Any]]:
    stamped = stamp_scope_identity(
        proof,
        book_title=book_title,
        chapter_no=chapter_no,
    )
    markdown = render_markdown(stamped)
    html = page_html(markdown)
    html, markdown = compose_drop_page(
        book_title=banner_title or book_title,
        chapter_no=banner_chapter_no if banner_chapter_no is not None else chapter_no,
        released=released,
        inner_html=html,
        inner_markdown=markdown,
    )
    return html, markdown, stamped


def open_store_card(
    *,
    store_root: Path | None,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
) -> dict[str, Any]:
    """Open the existing card from a store. Sidecar fills 书名／章节 if present."""

    if store_root is None:
        shown = show_current_html()
        return {
            "document_identity": DOCUMENT_IDENTITY,
            "github_issue": GITHUB_ISSUE,
            "base_main_sha": BASE_MAIN_SHA,
            "status": STATUS_CLOSED,
            "wrote": False,
            "sidecar_present": False,
            "identity_stamped": False,
            "product_adopted": False,
            "pointer_namespace": "FIXTURE_ONLY",
            "html": shown["html"],
            "markdown": shown["markdown"],
            "proof": shown["proof"],
        }

    store_root = Path(store_root)
    sidecar = load_stored_identity(store_root)
    shown = show_current_html(
        store_root=store_root,
        project_scope_id=project_scope_id,
        pointer_key=(sidecar or {}).get("pointer_key"),
    )
    if sidecar is None:
        return {
            "document_identity": DOCUMENT_IDENTITY,
            "github_issue": GITHUB_ISSUE,
            "base_main_sha": BASE_MAIN_SHA,
            "status": shown["proof"].get("status"),
            "wrote": False,
            "sidecar_present": False,
            "identity_stamped": False,
            "product_adopted": False,
            "pointer_namespace": "FIXTURE_ONLY",
            "html": shown["html"],
            "markdown": shown["markdown"],
            "proof": shown["proof"],
        }

    html, markdown, stamped = _render_with_identity(
        shown["proof"],
        book_title=str(sidecar["book_title"]),
        chapter_no=int(sidecar["chapter_no"]),
        released=True,
    )
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": shown["proof"].get("status"),
        "wrote": False,
        "sidecar_present": True,
        "identity_stamped": True,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "pointer_key": sidecar.get("pointer_key"),
        "stored_identity": sidecar,
        "html": html,
        "markdown": markdown,
        "proof": stamped,
    }


def drop_named_chapter_to_store(
    *,
    book: str,
    chapter_no: int,
    txt_path: Path | None = None,
    store_root: Path | None = None,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
) -> dict[str, Any]:
    """Drop via #300, then persist identity beside the sqlite file."""

    dropped = drop_named_chapter_with_card_identity(
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
    result["sidecar_wrote"] = False

    if dropped["status"] == STATUS_DROPPED and store_root is not None:
        write_stored_identity(Path(store_root), drop_result=dropped)
        result["sidecar_wrote"] = True
        result["sidecar_path"] = str(identity_path(Path(store_root)))
        return result

    sidecar = (
        load_stored_identity(Path(store_root)) if store_root is not None else None
    )
    if sidecar is not None:
        shown = show_current_html(
            store_root=Path(store_root),
            project_scope_id=project_scope_id,
            pointer_key=sidecar.get("pointer_key"),
        )
        attempted = str(dropped.get("drop", {}).get("book_title") or book)
        html, markdown, stamped = _render_with_identity(
            shown["proof"],
            book_title=str(sidecar["book_title"]),
            chapter_no=int(sidecar["chapter_no"]),
            released=False,
            banner_title=attempted,
            banner_chapter_no=chapter_no,
        )
        result["html"] = html
        result["markdown"] = markdown
        result["proof"] = stamped
        result["identity_stamped"] = True
        result["sidecar_present"] = True
    return result


def dumps_result(result: dict[str, Any]) -> str:
    return dumps_named_result(result)
