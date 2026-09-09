from __future__ import annotations

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WIRE_ROOT = REPOSITORY_ROOT / "work" / "ccz142_human_card_vertical_wire_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
for candidate in (REPOSITORY_ROOT, WIRE_ROOT, PREVIEW_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
sys.path.insert(0, str(MODULE_ROOT))

from self_check import run_self_check  # noqa: E402
from drop import main as drop_main  # noqa: E402
from named_chapter import (  # noqa: E402
    DATABASE_FILENAME,
    GAP_CHAPTER_MISMATCH,
    GAP_NOT_RELEASED,
    GAP_NO_STORE_ROOT,
    GAP_PATH_NOT_RELEASED,
    STATUS_CLOSED,
    STATUS_DROPPED,
    drop_named_chapter,
)

BOOK = "北塔夹具"
FIXTURE_TXT = WIRE_ROOT / "synthetic_chapter.txt"


def test_named_released_chapter_opens_existing_card(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = drop_named_chapter(
        book=BOOK,
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    page = result["html"]
    assert result["status"] == STATUS_DROPPED
    assert result["wrote"] is True
    assert result["drop"]["txt_bytes_read"] is True
    assert result["drop"]["book_title"] == BOOK
    assert result["drop"]["chapter_no"] == 1
    assert (store_root / DATABASE_FILENAME).is_file()
    assert result["proof"]["status"] == "READ_OK"
    assert result["proof"]["identity"]["pointer_namespace"] == "FIXTURE_ONLY"
    assert result["proof"]["identity"]["product_adopted"] is False
    assert "这次丢进：" in page and "北塔夹具" in page
    assert "第 1 章" in page
    assert "甲进入北塔。" in page
    assert "传闻／怀疑" in page
    assert "误信" in page
    assert "未证实" in page
    assert "FIXTURE_ONLY" in page
    assert "覆盖／漏抽尚未提供" not in page
    assert "抽取结算" in page
    assert "自评：3／5（合格）" in page
    assert "这不是认可" in page
    assert "写法指导" not in page
    assert "修补建议" not in page.replace("没有修补建议", "")


def test_unreleased_book_does_not_read_or_write(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = drop_named_chapter(
        book="全职高手",
        chapter_no=1,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_NOT_RELEASED]
    assert result["drop"]["txt_bytes_read"] is False
    assert result["product_adopted"] is False
    assert not store_root.exists()
    assert "这次丢进：" in result["html"] and "全职高手" in result["html"]
    assert "未放行／未写入" in result["html"]
    assert "写法指导" not in result["html"]


def test_wrong_chapter_number_does_not_read(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = drop_named_chapter(
        book=BOOK,
        chapter_no=2,
        txt_path=FIXTURE_TXT,
        store_root=store_root,
    )
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_NOT_RELEASED]
    assert result["drop"]["txt_bytes_read"] is False
    assert not store_root.exists()


def test_blocked_path_does_not_read(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    blocked = Path("corpus-downloads/gold-not-released/ch01.txt")
    result = drop_named_chapter(
        book=BOOK,
        chapter_no=1,
        txt_path=blocked,
        store_root=store_root,
    )
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_PATH_NOT_RELEASED]
    assert result["drop"]["txt_bytes_read"] is False
    assert not store_root.exists()
    assert not blocked.exists()


def test_wrong_txt_hash_does_not_write(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("这不是那条合成章。\n", encoding="utf-8")
    result = drop_named_chapter(
        book=BOOK,
        chapter_no=1,
        txt_path=wrong,
        store_root=store_root,
    )
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_CHAPTER_MISMATCH]
    assert result["drop"]["txt_bytes_read"] is True
    assert not store_root.exists()


def test_no_store_root_is_gap_page() -> None:
    result = drop_named_chapter(book=BOOK, chapter_no=1)
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_NO_STORE_ROOT]
    assert result["drop"]["txt_bytes_read"] is False
    assert result["proof"]["gaps"] == ["GAP_NO_LIVE_STORE"]
    assert "还读不到一张可展示的 current 卡" in result["html"]
    assert "这次丢进：" in result["html"] and "北塔夹具" in result["html"]


def test_cli_writes_html(tmp_path: Path) -> None:
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
    assert "抽出了什么（人话结果卡）" in html
    assert "这次丢进：" in html and "北塔夹具" in html
    assert "误信" in html


def test_cli_unreleased_exits_closed(tmp_path: Path) -> None:
    code = drop_main(
        [
            "--book",
            "全职高手",
            "--chapter",
            "1",
            "--txt",
            str(FIXTURE_TXT),
            "--store",
            str(tmp_path / "authority"),
            "--json-only",
        ]
    )
    assert code == 2
    assert not (tmp_path / "authority").exists()


def test_self_check_pass() -> None:
    report = run_self_check()
    assert report["result"] == "PASS"
    assert report["github_issue"] == 297
    assert report["identity_never_product_adopted"] is True
    assert report["allowlist_entry_count"] == 1
