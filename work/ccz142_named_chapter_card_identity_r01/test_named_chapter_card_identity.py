from __future__ import annotations

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NAMED_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_txt_card_r01"
WIRE_ROOT = REPOSITORY_ROOT / "work" / "ccz142_human_card_vertical_wire_r01"
for candidate in (REPOSITORY_ROOT, NAMED_ROOT, WIRE_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
sys.path.insert(0, str(MODULE_ROOT))

from self_check import run_self_check  # noqa: E402
from drop import main as drop_main  # noqa: E402
from identity_card import (  # noqa: E402
    DATABASE_FILENAME,
    STATUS_DROPPED,
    drop_named_chapter_with_card_identity,
)
from named_chapter import GAP_NOT_RELEASED, STATUS_CLOSED  # noqa: E402

BOOK = "北塔夹具"
FIXTURE_TXT = WIRE_ROOT / "synthetic_chapter.txt"


def test_released_drop_stamps_book_and_chapter_on_card(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = drop_named_chapter_with_card_identity(
        book=BOOK,
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    page = result["html"]
    markdown = result["markdown"]
    assert result["status"] == STATUS_DROPPED
    assert result["identity_stamped"] is True
    assert result["proof"]["result_scope"]["book_title"] == BOOK
    assert result["proof"]["result_scope"]["chapter_id"] == "1"
    assert "- 书名：北塔夹具" in markdown
    assert "- 章节：1" in markdown
    assert "书名：北塔夹具" in page
    assert "章节：1" in page
    assert "甲进入北塔。" in page
    assert "传闻／怀疑" in page
    assert "误信" in page
    assert "未证实" in page
    assert "写法指导" not in page
    assert (store_root / DATABASE_FILENAME).is_file()


def test_unreleased_book_does_not_stamp_title(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = drop_named_chapter_with_card_identity(
        book="全职高手",
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_NOT_RELEASED]
    assert result["identity_stamped"] is False
    assert result["proof"]["result_scope"]["book_title"] in {"未提供", "尚未提供"}
    assert "书名：全职高手" not in result["html"]
    assert "书名：全职高手" not in result["markdown"]
    assert not store_root.exists()


def test_failed_drop_keeps_existing_card(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    first = drop_named_chapter_with_card_identity(
        book=BOOK,
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert first["status"] == STATUS_DROPPED
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("这不是那条合成章。\n", encoding="utf-8")
    second = drop_named_chapter_with_card_identity(
        book=BOOK,
        chapter_no=1,
        txt_path=wrong,
        store_root=store_root,
    )
    assert second["status"] == STATUS_CLOSED
    assert second["wrote"] is False
    assert second["identity_stamped"] is False
    assert (store_root / DATABASE_FILENAME).is_file()
    assert "甲进入北塔。" in second["html"]
    assert "未放行／未写入" in second["html"]


def test_cli_writes_stamped_html(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    out = tmp_path / "card.html"
    code = drop_main(
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
            str(out),
            "--json-only",
        ]
    )
    assert code == 0
    html = out.read_text(encoding="utf-8")
    assert "书名：北塔夹具" in html
    assert "章节：1" in html


def test_self_check_pass() -> None:
    report = run_self_check()
    assert report["result"] == "PASS"
    assert report["github_issue"] == 299
