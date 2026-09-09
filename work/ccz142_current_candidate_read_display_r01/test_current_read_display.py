from __future__ import annotations

import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, PROOF_ROOT, AUTHORITY_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from candidate_authority import (  # noqa: E402
    CandidateAuthorityStore,
    CandidateRootInitializer,
)
from card_render import (  # noqa: E402
    CARD_TITLE,
    COVERAGE_NOT_WIRED,
    DENSITY_NOT_WIRED,
    EMPTY_READ_GAPS,
    render_markdown,
    show_current_card,
)
from shadow_fixtures import (  # noqa: E402
    MutableRootAuthorityReader,
    authority_snapshot,
    root_request,
)
from show import main as show_main  # noqa: E402

sys.path.insert(0, str(MODULE_ROOT))
from self_check import run_self_check  # noqa: E402

PROJECT = "fixture-project-001"


def new_store(root: Path) -> CandidateAuthorityStore:
    store = CandidateAuthorityStore(root, project_scope_id=PROJECT)
    store.initialize_authority_schema()
    return store


def publish_root(store: CandidateAuthorityStore) -> dict:
    request = root_request()
    return CandidateRootInitializer(
        store=store,
        authority_reader=MutableRootAuthorityReader(authority_snapshot(request)),
    ).initialize_root(request)


def test_no_live_store_page_shows_gap_and_read_path() -> None:
    shown = show_current_card()
    page = shown["markdown"]
    assert shown["proof"]["gaps"] == ["GAP_NO_LIVE_STORE"]
    assert "`GAP_NO_LIVE_STORE`" in page
    assert "CandidateAuthorityStore" in page
    assert "还读不到一张可展示的 current 卡" in page
    assert COVERAGE_NOT_WIRED in page
    assert DENSITY_NOT_WIRED in page
    assert "抽取结算" not in page
    assert "整章完整性" in page
    assert "## 写法指导" not in page
    assert shown["proof"]["identity"]["product_adopted"] is False


def test_fixture_store_page_shows_human_items(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    publish_root(store)
    shown = show_current_card(store_root=store.root, project_scope_id=PROJECT)
    page = shown["markdown"]
    assert shown["proof"]["status"] == "READ_OK"
    assert "甲进入北塔。" in page
    assert "甲拿起铜钥匙。" in page
    assert "甲走进北塔。" in page
    assert "FIXTURE_ONLY" in page
    assert "不是产品权威" in page
    assert "抽取结算" in page
    assert "自评：3／5（合格）" in page
    assert "这不是认可" in page
    assert "责任段 1 有 2 条" not in page
    assert COVERAGE_NOT_WIRED not in page
    assert "synthetic-chapter-001" in page
    assert "整章完整性：未确认" in page
    assert "不是已确认的整章汇总" in page
    assert "书名：未提供" in page
    assert "### 1. 甲进入北塔。" in page
    assert "状态：已发生" in page
    assert "证据：甲走进北塔。" in page
    assert "稳定条目：lin_" in page
    assert "原文位置：责任段 1，字节 0–18；责任段 1，字节 39–57" in page
    assert "说话人：旁白" in page
    assert EMPTY_READ_GAPS in page.split("## 缺口", 1)[1]


def test_cli_writes_gap_page_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = show_main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "`GAP_NO_LIVE_STORE`" in captured.out
    assert captured.out.startswith(f"# {CARD_TITLE}")


def test_cli_out_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "card.md"
    exit_code = show_main(["--out", str(target)])
    assert exit_code == 2
    text = target.read_text(encoding="utf-8")
    assert "`GAP_NO_LIVE_STORE`" in text


def test_layout_sample_is_not_a_live_product_card() -> None:
    sample = (MODULE_ROOT / "samples" / "fixture_layout.md").read_text(encoding="utf-8")
    assert "样张" in sample
    assert "不是活库读出" in sample
    assert "甲进入北塔。" in sample
    assert "稳定条目：未提供" in sample
    assert "原文位置：未提供" in sample
    assert "产品权威" in sample
    assert "## 写法指导" not in sample


def test_self_check_passes() -> None:
    receipt = run_self_check()
    assert receipt["result"] == "PASS"


def test_renderer_does_not_invent_items_on_gap() -> None:
    page = render_markdown(
        {
            "status": "GAP",
            "identity": {"product_adopted": False},
            "read_path": {"store_class": "CandidateAuthorityStore"},
            "human_card": None,
            "gaps": ["GAP_STORE_MISSING"],
            "limitations": [],
            "standing_boundaries": ["GAP_REAL_NOVEL_NOT_IN_SCOPE"],
        }
    )
    assert "没有可展示的事实条目" in page
    assert "`GAP_STORE_MISSING`" in page
