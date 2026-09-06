from __future__ import annotations

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WIRE_ROOT = REPOSITORY_ROOT / "work" / "ccz142_human_card_vertical_wire_r01"
NAMED_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_txt_card_r01"
for candidate in (REPOSITORY_ROOT, WIRE_ROOT, NAMED_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
sys.path.insert(0, str(MODULE_ROOT))

from self_check import run_self_check  # noqa: E402
from named_chapter import DATABASE_FILENAME, GAP_NOT_RELEASED  # noqa: E402
from store_identity import (  # noqa: E402
    IDENTITY_FILENAME,
    STATUS_DROPPED,
    drop_named_chapter_to_store,
    identity_path,
    open_store_card,
)

sys.path.insert(0, str(MODULE_ROOT))
from drop import main as drop_main  # noqa: E402

BOOK = "北塔夹具"
FIXTURE_TXT = WIRE_ROOT / "synthetic_chapter.txt"


def test_drop_writes_sidecar_and_reopen_keeps_book(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    dropped = drop_named_chapter_to_store(
        book=BOOK,
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert dropped["status"] == STATUS_DROPPED
    assert dropped["sidecar_wrote"] is True
    assert identity_path(store_root).is_file()
    assert (store_root / DATABASE_FILENAME).is_file()

    reopened = open_store_card(store_root=store_root)
    assert reopened["sidecar_present"] is True
    assert reopened["identity_stamped"] is True
    assert reopened["proof"]["result_scope"]["book_title"] == BOOK
    assert reopened["proof"]["result_scope"]["chapter_id"] == "1"
    assert "- 书名：北塔夹具" in reopened["markdown"]
    assert "- 章节：1" in reopened["markdown"]
    assert "书名：北塔夹具" in reopened["html"]
    assert "甲进入北塔。" in reopened["html"]


def test_unreleased_does_not_write_sidecar(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = drop_named_chapter_to_store(
        book="全职高手",
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert result["gaps"] == [GAP_NOT_RELEASED]
    assert result["sidecar_wrote"] is False
    assert not identity_path(store_root).exists()
    assert not store_root.exists()


def test_failed_drop_does_not_overwrite_sidecar(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    first = drop_named_chapter_to_store(
        book=BOOK,
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert first["sidecar_wrote"] is True
    original = identity_path(store_root).read_text(encoding="utf-8")
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("这不是那条合成章。\n", encoding="utf-8")
    second = drop_named_chapter_to_store(
        book=BOOK,
        chapter_no=1,
        txt_path=wrong,
        store_root=store_root,
    )
    assert second["sidecar_wrote"] is False
    assert identity_path(store_root).read_text(encoding="utf-8") == original
    reopened = open_store_card(store_root=store_root)
    assert reopened["proof"]["result_scope"]["book_title"] == BOOK
    assert "书名：北塔夹具" in reopened["html"]


def test_cli_open_only(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    out_drop = tmp_path / "drop.html"
    out_open = tmp_path / "open.html"
    assert (
        drop_main(
            [
                "--book",
                BOOK,
                "--chapter",
                "1",
                "--txt",
                str(FIXTURE_TXT),
                "--store",
                str(store_root),
                "--out",
                str(out_drop),
                "--json-only",
            ]
        )
        == 0
    )
    assert (
        drop_main(
            [
                "--open-only",
                "--store",
                str(store_root),
                "--out",
                str(out_open),
                "--json-only",
            ]
        )
        == 0
    )
    html = out_open.read_text(encoding="utf-8")
    assert "书名：北塔夹具" in html
    assert "章节：1" in html
    assert (store_root / IDENTITY_FILENAME).is_file()


def test_self_check_pass() -> None:
    report = run_self_check()
    assert report["result"] == "PASS"
    assert report["github_issue"] == 301
