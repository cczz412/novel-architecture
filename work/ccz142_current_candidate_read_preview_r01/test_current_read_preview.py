from __future__ import annotations

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    DISPLAY_ROOT,
    PROOF_ROOT,
    AUTHORITY_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from candidate_authority import (  # noqa: E402
    CandidateAuthorityStore,
    CandidateRootInitializer,
)
from html_render import (  # noqa: E402
    fixture_layout_html,
    page_html,
    render_html,
    show_current_html,
    types_preview_html,
)
from shadow_fixtures import (  # noqa: E402
    MutableRootAuthorityReader,
    authority_snapshot,
    root_request,
)

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


def test_no_live_store_html_shows_gap() -> None:
    shown = show_current_html()
    page = shown["html"]
    assert shown["proof"]["gaps"] == ["GAP_NO_LIVE_STORE"]
    assert "GAP_NO_LIVE_STORE" in page
    assert "<!DOCTYPE html>" in page
    assert "抽出了什么（人话结果卡）" in page
    assert "整章完整性" in page
    assert "密度" in page
    assert "还读不到一张可展示的 current 卡" in page
    assert "写法指导" not in page
    assert shown["proof"]["identity"]["product_adopted"] is False


def test_fixture_store_html_shows_human_items(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    publish_root(store)
    shown = show_current_html(store_root=store.root, project_scope_id=PROJECT)
    page = shown["html"]
    assert shown["proof"]["status"] == "READ_OK"
    assert "甲进入北塔。" in page
    assert "甲拿起铜钥匙。" in page
    assert "FIXTURE_ONLY" in page
    assert "不是产品权威" in page
    assert "<h3>" in page
    assert "状态：已发生" in page
    assert "synthetic-chapter-001" in page
    assert "不是已确认的整章汇总" in page


def test_types_sample_shows_rumor_misbelief_unverified() -> None:
    page = types_preview_html()
    assert "传闻／怀疑" in page
    assert "误信" in page
    assert "未证实" in page
    assert "不是活库读出" in page
    assert "写法指导" not in page


def test_layout_html_matches_display_markdown_sample() -> None:
    page = fixture_layout_html()
    source = (
        DISPLAY_ROOT / "samples" / "fixture_layout.md"
    ).read_text(encoding="utf-8")
    assert "甲进入北塔。" in page
    assert "样张" in page
    assert source.splitlines()[0] in (
        "> 这是夹具样张，用来看卡长什么样。不是活库读出，也不是产品权威。"
    )


def test_renderer_does_not_invent_items_on_gap() -> None:
    page = render_html(
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
    assert "GAP_STORE_MISSING" in page


def test_page_html_escapes_angle_brackets() -> None:
    page = page_html("# 抽出了什么\n\n<script>alert(1)</script>\n")
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_self_check_passes() -> None:
    receipt = run_self_check()
    assert receipt["result"] == "PASS"
