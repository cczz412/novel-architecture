from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

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
import self_check as preview_check  # noqa: E402
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
    assert "覆盖／漏抽尚未提供" in page
    assert "抽取结算" not in page
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
    assert "抽取结算" in page
    assert "自评：3／5（合格）" in page
    assert "这不是认可" in page
    assert "覆盖／漏抽尚未提供" not in page
    assert "<h3>" in page
    assert "状态：已发生" in page
    assert "synthetic-chapter-001" in page
    assert "不是已确认的整章汇总" in page
    assert "稳定条目：lin_" in page
    assert "原文位置：责任段 1，字节 0–18；责任段 1，字节 39–57" in page


def test_types_sample_shows_rumor_misbelief_unverified() -> None:
    page = types_preview_html()
    assert "传闻／怀疑" in page
    assert "误信" in page
    assert "未证实" in page
    assert "稳定条目：未提供" in page
    assert "原文位置：未提供" in page
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


@pytest.mark.parametrize("name", sorted(preview_check.FROZEN_SAMPLE_SHA256))
def test_self_check_rejects_changed_frozen_sample(tmp_path: Path, monkeypatch, name: str) -> None:
    copied = tmp_path / "preview"
    shutil.copytree(MODULE_ROOT, copied)
    sample = copied / "samples" / name
    original = sample.read_bytes()
    sample.write_bytes(b"!" + original[1:])
    monkeypatch.setattr(preview_check, "ROOT", copied)
    with pytest.raises(RuntimeError, match=f"READ_PREVIEW_FROZEN_SAMPLE_DRIFT: {name}"):
        run_self_check()


def test_self_check_accepts_current_page_independent_of_frozen_html(monkeypatch) -> None:
    original = preview_check.show_current_html

    def with_extra_newline():
        shown = original()
        return {**shown, "html": shown["html"] + "\n"}

    monkeypatch.setattr(preview_check, "show_current_html", with_extra_newline)
    assert run_self_check()["result"] == "PASS"


def test_self_check_rejects_current_gap_page_without_gap_label(monkeypatch) -> None:
    original = preview_check.show_current_html

    def without_label():
        shown = original()
        return {**shown, "html": shown["html"].replace("GAP_NO_LIVE_STORE", "")}

    monkeypatch.setattr(preview_check, "show_current_html", without_label)
    with pytest.raises(RuntimeError, match="READ_PREVIEW_GAP_PAGE_UNLABELLED"):
        run_self_check()
