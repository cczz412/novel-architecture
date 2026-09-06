from __future__ import annotations

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WIRE_ROOT = REPOSITORY_ROOT / "work" / "ccz142_human_card_vertical_wire_r01"
STORE_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_identity_store_r01"
NAMED_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_txt_card_r01"
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
for candidate in (
    REPOSITORY_ROOT,
    WIRE_ROOT,
    STORE_ROOT,
    NAMED_ROOT,
    PROOF_ROOT,
    DISPLAY_ROOT,
    PREVIEW_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
sys.path.insert(0, str(MODULE_ROOT))

from self_check import run_self_check  # noqa: E402
from current_read_proof import prove_current_read  # noqa: E402
from html_render import show_current_html  # noqa: E402
from named_chapter import DATABASE_FILENAME  # noqa: E402
from store_identity import (  # noqa: E402
    IDENTITY_FILENAME,
    STATUS_DROPPED,
    drop_named_chapter_to_store,
)

sys.path.insert(0, str(MODULE_ROOT))
from drop import main as drop_main  # noqa: E402
from identity_read import open_original_store_card  # noqa: E402

BOOK = "北塔夹具"
FIXTURE_TXT = WIRE_ROOT / "synthetic_chapter.txt"


def _drop(store_root: Path) -> dict:
    dropped = drop_named_chapter_to_store(
        book=BOOK,
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert dropped["status"] == STATUS_DROPPED
    assert (store_root / IDENTITY_FILENAME).is_file()
    assert (store_root / DATABASE_FILENAME).is_file()
    return dropped


def test_original_prove_and_show_keep_book(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    _drop(store_root)
    proof = prove_current_read(store_root=store_root)
    assert proof["result_scope"]["book_title"] == BOOK
    assert proof["result_scope"]["chapter_id"] == "1"
    shown = show_current_html(store_root=store_root)
    assert shown["proof"]["result_scope"]["book_title"] == BOOK
    assert "- 书名：北塔夹具" in shown["markdown"]
    assert "- 章节：1" in shown["markdown"]
    assert "书名：北塔夹具" in shown["html"]
    opened = open_original_store_card(store_root=store_root)
    assert opened["identity_from_sidecar"] is True
    assert opened["prove"]["result_scope"]["book_title"] == BOOK


def test_missing_sidecar_stays_unprovided(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    _drop(store_root)
    (store_root / IDENTITY_FILENAME).unlink()
    proof = prove_current_read(store_root=store_root)
    assert proof["result_scope"]["book_title"] == "未提供"
    shown = show_current_html(store_root=store_root)
    assert "书名：未提供" in shown["markdown"]


def test_broken_sidecar_is_ignored(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    _drop(store_root)
    (store_root / IDENTITY_FILENAME).write_text("{not-json", encoding="utf-8")
    proof = prove_current_read(store_root=store_root)
    assert proof["result_scope"]["book_title"] == "未提供"
    assert proof["result_scope"]["chapter_id"] == "synthetic-chapter-001"


def test_cli_original_open(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    out = tmp_path / "open.html"
    _drop(store_root)
    assert (
        drop_main(["--store", str(store_root), "--out", str(out), "--json-only"]) == 0
    )
    html = out.read_text(encoding="utf-8")
    assert "书名：北塔夹具" in html
    assert "章节：1" in html


def test_self_check_pass() -> None:
    report = run_self_check()
    assert report["result"] == "PASS"
    assert report["github_issue"] == 303
