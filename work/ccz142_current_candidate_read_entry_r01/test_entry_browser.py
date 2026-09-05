"""Optional real-browser smoke checks; never download a browser or run a server.

A missing local browser/Playwright is reported as SKIP, not a completed check.
Only a temporary copy of this entry is opened. No corpus or database is read.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="未安装 Playwright；浏览器验收未完成")
HERE = Path(__file__).resolve().parent
ENTRY_NAME = "打开人话结果卡.html"


def snapshot(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
        for p in root.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("javascript_enabled", [False, True], ids=["no-js", "js"])
@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 1000},
    {"width": 390, "height": 844},
], ids=["desktop", "mobile"])
def test_offline_file_links_without_repo_or_store(
    tmp_path: Path, javascript_enabled: bool, viewport: dict,
) -> None:
    entry = tmp_path / "只有入口 没有仓库与活库"
    entry.mkdir()
    shutil.copyfile(HERE / ENTRY_NAME, entry / ENTRY_NAME)
    shutil.copytree(HERE / "samples", entry / "samples")
    before = snapshot(entry)
    network_attempts: list[str] = []
    page_errors: list[str] = []
    with sync_api.sync_playwright() as playwright:
        browser_path = shutil.which("chromium") or shutil.which("chromium-browser")
        browser_path = browser_path or playwright.chromium.executable_path
        if not Path(browser_path).is_file():
            pytest.skip("本机没有 Chromium；浏览器验收未完成，不自动下载")
        browser = playwright.chromium.launch(
            executable_path=browser_path,
            headless=True,
            args=["--no-sandbox", "--disable-background-networking"],
        )
        context = browser.new_context(
            viewport=viewport, java_script_enabled=javascript_enabled,
            offline=True, service_workers="block",
        )
        # Browser-level offline mode blocks traffic; also record any attempted
        # non-file requests rather than silently treating blocked traffic as zero.
        context.on("request", lambda request: (
            network_attempts.append(request.url)
            if not request.url.startswith("file:") else None
        ))
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto((entry / ENTRY_NAME).as_uri())
        sync_api.expect(page.get_by_role("heading", name="打开人话结果卡")).to_be_visible()
        assert page.locator("nav a").count() == 3
        # Layout evaluation is test instrumentation, not JavaScript shipped in the entry.
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        cases = [
            ("open-gap", "no_live_store.html", ["GAP_NO_LIVE_STORE", "没有可展示的事实条目"]),
            ("open-types", "types_layout.html", ["FIXTURE_ONLY", "传闻／怀疑", "误信", "未证实"]),
            ("open-fixture", "fixture_layout.html", ["FIXTURE_ONLY", "甲进入北塔", "甲拿起铜钥匙"]),
        ]
        for link_id, filename, tokens in cases:
            page.locator(f"#{link_id}").click()
            page.wait_for_url((entry / "samples" / filename).as_uri())
            body = page.locator("body").inner_text()
            for token in tokens:
                assert token in body
            assert "这层还没接到 B02，不编数字" in body
            assert page.locator("script,form,input,button,iframe").count() == 0
            page.go_back()
            sync_api.expect(page.get_by_role("heading", name="打开人话结果卡")).to_be_visible()
        context.close()
        browser.close()
    assert network_attempts == []
    assert page_errors == []
    assert snapshot(entry) == before
    assert not list(entry.rglob("*.db"))


@pytest.mark.parametrize("javascript_enabled", [False, True], ids=["no-js", "js"])
@pytest.mark.parametrize("viewport", [
    {"width": 1440, "height": 1000},
    {"width": 390, "height": 844},
], ids=["desktop", "mobile"])
def test_memory_render_only(javascript_enabled: bool, viewport: dict) -> None:
    """Rendering evidence only: deliberately does NOT stand in for file navigation."""
    attempts: list[str] = []
    errors: list[str] = []
    with sync_api.sync_playwright() as playwright:
        executable = shutil.which("chromium") or shutil.which("chromium-browser")
        executable = executable or playwright.chromium.executable_path
        if not Path(executable).is_file():
            pytest.skip("本机没有 Chromium；内存渲染检查未完成")
        browser = playwright.chromium.launch(
            executable_path=executable, headless=True,
            args=["--no-sandbox", "--disable-background-networking"],
        )
        context = browser.new_context(
            viewport=viewport, java_script_enabled=javascript_enabled,
            offline=True, service_workers="block",
        )
        context.on("request", lambda request: attempts.append(request.url))
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        pages = [
            (ENTRY_NAME, ["FIXTURE_ONLY", "GAP_NO_LIVE_STORE", "不检查活库"]),
            ("samples/no_live_store.html", ["GAP_NO_LIVE_STORE", "没有可展示的事实条目"]),
            ("samples/types_layout.html", ["FIXTURE_ONLY", "传闻／怀疑", "误信", "未证实"]),
            ("samples/fixture_layout.html", ["FIXTURE_ONLY", "甲进入北塔", "甲拿起铜钥匙"]),
        ]
        for name, tokens in pages:
            page.set_content((HERE / name).read_text(encoding="utf-8"), wait_until="load")
            body = page.locator("body").inner_text()
            for token in tokens:
                assert token in body
            if name == ENTRY_NAME:
                assert page.locator("nav a").count() == 3
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            else:
                assert "这层还没接到 B02，不编数字" in body
        context.close()
        browser.close()
    assert attempts == []
    assert errors == []
