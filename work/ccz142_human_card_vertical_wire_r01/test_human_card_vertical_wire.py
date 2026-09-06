from __future__ import annotations

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    AUTHORITY_ROOT,
    PREVIEW_ROOT,
    PROOF_ROOT,
    DISPLAY_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

sys.path.insert(0, str(MODULE_ROOT))
from self_check import run_self_check  # noqa: E402
from vertical_wire import (  # noqa: E402
    DATABASE_FILENAME,
    GAP_CHAPTER_MISMATCH,
    GAP_NO_STORE_ROOT,
    STATUS_CLOSED,
    STATUS_WIRED,
    SYNTHETIC_CHAPTER,
    extract_handoff_items,
    load_synthetic_chapter,
    wire_synthetic_chapter_to_card,
)
from wire import main as wire_main  # noqa: E402

PROJECT = "fixture-project-001"


def test_frozen_chapter_matches_b01_revision_text() -> None:
    assert load_synthetic_chapter() == SYNTHETIC_CHAPTER
    items = extract_handoff_items(SYNTHETIC_CHAPTER)
    assert items is not None
    statuses = {item["status"] for item in items}
    assert {"已发生", "推测", "误信", "计划"} <= statuses


def test_wrong_chapter_does_not_write(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = wire_synthetic_chapter_to_card(
        chapter_text="这不是那条合成章。",
        store_root=store_root,
        project_scope_id=PROJECT,
    )
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_CHAPTER_MISMATCH]
    assert result["product_adopted"] is False
    assert not store_root.exists()
    assert "抽出了什么（人话结果卡）" in result["html"]
    assert "写法指导" not in result["html"]


def test_no_store_root_is_gap_page() -> None:
    result = wire_synthetic_chapter_to_card(chapter_text=SYNTHETIC_CHAPTER)
    assert result["status"] == STATUS_CLOSED
    assert result["wrote"] is False
    assert result["gaps"] == [GAP_NO_STORE_ROOT]
    assert result["proof"]["gaps"] == ["GAP_NO_LIVE_STORE"]
    assert "还读不到一张可展示的 current 卡" in result["html"]


def test_matching_chapter_opens_existing_card(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    result = wire_synthetic_chapter_to_card(
        chapter_text=SYNTHETIC_CHAPTER,
        store_root=store_root,
        project_scope_id=PROJECT,
    )
    page = result["html"]
    assert result["status"] == STATUS_WIRED
    assert result["wrote"] is True
    assert (store_root / DATABASE_FILENAME).is_file()
    assert result["proof"]["status"] == "READ_OK"
    assert result["proof"]["identity"]["pointer_namespace"] == "FIXTURE_ONLY"
    assert result["proof"]["identity"]["product_adopted"] is False
    assert "甲进入北塔。" in page
    assert "传闻／怀疑" in page
    assert "误信" in page
    assert "未证实" in page
    assert "FIXTURE_ONLY" in page
    assert "覆盖／漏抽尚未提供" in page
    assert "尚未提供" in page
    assert "synthetic-chapter-001" in page
    assert "写法指导" not in page
    assert "修补建议" not in page.replace("没有修补建议", "")

    import json
    import sqlite3

    connection = sqlite3.connect(store_root / DATABASE_FILENAME)
    rows = connection.execute("SELECT record_json FROM candidate_versions").fetchall()
    connection.close()
    statuses: list[str] = []
    for (blob,) in rows:
        payload = json.loads(blob)["payload"]
        statuses.extend(item["status"] for item in payload["items"])
    assert statuses.count("已发生") == 2
    assert "推测" in statuses
    assert "误信" in statuses
    assert "计划" in statuses
    assert len(statuses) == 5


def test_cli_writes_html(tmp_path: Path) -> None:
    store_root = tmp_path / "authority"
    out = tmp_path / "card.html"
    code = wire_main(
        [
            "--chapter-text",
            SYNTHETIC_CHAPTER,
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
    assert "误信" in html


def test_cli_wrong_chapter_exits_closed(tmp_path: Path) -> None:
    code = wire_main(
        [
            "--chapter-text",
            "错章",
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
    assert report["github_issue"] == 295
    assert report["identity_never_product_adopted"] is True
