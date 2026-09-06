from __future__ import annotations

import importlib.util
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

from current_read_proof import prove_current_read  # noqa: E402
from html_render import show_current_html  # noqa: E402
from named_chapter import DATABASE_FILENAME  # noqa: E402
from store_identity import (  # noqa: E402
    STATUS_DROPPED,
    drop_named_chapter_to_store,
)

from coverage_wire import open_coverage_card  # noqa: E402

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
    assert (store_root / DATABASE_FILENAME).is_file()
    return dropped


def test_named_drop_shows_count_distribution(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    _drop(store_root)
    shown = show_current_html(store_root=store_root)
    page = shown["markdown"]
    view = shown["proof"]["coverage_view"]
    assert view["wired"] is True
    assert view["b02_originals"] is False
    assert shown["proof"]["settlement_view"]["score"] == 3
    assert "自评：3／5（合格）" in page
    assert "这不是认可" in page
    assert "责任段 1 有 5 条" not in page
    assert "满覆盖" not in page
    assert "覆盖／漏抽尚未提供" not in page
    opened = open_coverage_card(store_root=store_root)
    assert opened["coverage_wired"] is True


def test_no_live_store_keeps_unprovided() -> None:
    proof = prove_current_read()
    assert proof["coverage_view"]["wired"] is False
    shown = show_current_html()
    assert shown["proof"]["settlement_view"]["wired"] is False
    assert "覆盖／漏抽尚未提供" in shown["markdown"]
    assert "责任段 1 有" not in shown["markdown"]
    assert "抽取结算" not in shown["markdown"]


def test_unreleased_book_does_not_write(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    dropped = drop_named_chapter_to_store(
        book="全职高手",
        chapter_no=1,
        store_root=store_root,
    )
    assert dropped["status"] != STATUS_DROPPED
    assert not (store_root / DATABASE_FILENAME).is_file()


def test_cli_original_open(tmp_path: Path) -> None:
    import importlib.util

    store_root = tmp_path / "authority"
    out = tmp_path / "open.html"
    _drop(store_root)
    spec = importlib.util.spec_from_file_location(
        "coverage_wire_drop",
        MODULE_ROOT / "drop.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(
        ["--store", str(store_root), "--out", str(out), "--json-only"]
    ) == 0
    html = out.read_text(encoding="utf-8")
    assert "自评：3／5（合格）" in html
    assert "这不是认可" in html


def _load_self_check():
    spec = importlib.util.spec_from_file_location(
        "coverage_wire_self_check",
        MODULE_ROOT / "self_check.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_self_check_pass() -> None:
    report = _load_self_check().run_self_check()
    assert report["result"] == "PASS"
    assert report["github_issue"] == 305
