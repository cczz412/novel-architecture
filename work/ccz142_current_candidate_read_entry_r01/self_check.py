"""Check this offline entry and its pinned HTML copies; never open a store.

This is a developer check, not an application entry point or a candidate reader.
It reads only the landing page, its manifest and the three named HTML samples.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTRY_NAME = "打开人话结果卡.html"
SOURCE_COMMIT = "9c2fb95881caf795aae46f1838a93eb674a63a5e"
SOURCE_DIR = Path("work/ccz142_current_candidate_read_preview_r01/samples")
EXPECTED = {
    "fixture_layout.html": (
        "4c529c174e907c32d10f6298397cc09cd10a9e203c38574d0a397ae06c7fb16d",
        "fc9b146ed6524823e10edc1aa90a5df60ec09522",
    ),
    "no_live_store.html": (
        "be5060218726514b6302a21ad3eb4b872b968e8fd1ad2df8b6f43a826a597aec",
        "f79dfddc75d1c2bbc920c60dece819e35b179308",
    ),
    "types_layout.html": (
        "29c752644fe9e2b939e8e89bd89961ade2ca2495e4e169a46b1cc3ee2194acf1",
        "d0c6ff40b6b3da755bdb6107437fb7f19749373f",
    ),
}
LINKS = {
    "open-gap": "samples/no_live_store.html",
    "open-types": "samples/types_layout.html",
    "open-fixture": "samples/fixture_layout.html",
}


class CheckError(ValueError):
    """A required file, identity or offline-only condition was not satisfied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def read_local(root: Path, relative: str) -> bytes:
    path = root / relative
    require(not path.is_symlink(), f"不能用符号链接代替样张：{relative}")
    require(path.resolve().is_relative_to(root.resolve()), f"文件越界：{relative}")
    require(path.is_file(), f"缺文件：{relative}")
    return path.read_bytes()


class StaticHTML(HTMLParser):
    """A deliberately small audit for these four static, asset-free pages."""

    BLOCKED_TAGS = {
        "script", "iframe", "frame", "frameset", "object", "embed", "link",
        "form", "input", "button", "textarea", "base", "audio", "video",
        "source", "track", "img", "svg", "math", "canvas",
    }
    BLOCKED_ATTRS = {
        "src", "srcset", "action", "formaction", "ping", "manifest",
        "background", "data", "codebase", "archive", "srcdoc", "style",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str | None]] = []
        self.text: list[str] = []
        self.style_text: list[str] = []
        self.in_style = False
        self.language: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        require(tag not in self.BLOCKED_TAGS, f"不应有可执行或外接元素：{tag}")
        require(len(attrs) == len(dict(attrs)), f"不应有重复属性：{tag}")
        attributes = dict(attrs)
        for name in attributes:
            require(not name.startswith("on"), f"不应有事件脚本：{name}")
            require(name not in self.BLOCKED_ATTRS, f"不应有外接资源属性：{name}")
            require(name != "href" or tag == "a", "只有普通链接可以使用 href")
        if tag == "meta":
            require("http-equiv" not in attributes, "不应自动跳转或改写加载规则")
        if tag == "a":
            self.links.append(attributes)
        if tag == "html":
            self.language = attributes.get("lang")
        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        (self.style_text if self.in_style else self.text).append(data)


def audit_html(content: bytes) -> StaticHTML:
    document = content.decode("utf-8")
    require(document.lstrip().lower().startswith("<!doctype html>"), "缺 HTML 声明")
    page = StaticHTML()
    page.feed(document)
    page.close()
    require(page.language == "zh-Hans", "页面没有保留中文语言标记")
    css = "".join(page.style_text)
    require("\\" not in css and "/*" not in css, "样式不应有转义或隐藏片段")
    require(not re.search(r"url\s*\(|@import|expression\s*\(", css, re.I),
            "样式不应加载外部资源或执行内容")
    return page


def check_entry(entry_dir: Path = HERE, source_root: Path | None = None) -> dict:
    """Validate shipped copies; optionally compare the three upstream files."""
    try:
        manifest = json.loads(read_local(entry_dir, "SOURCE_SAMPLES.json"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise CheckError("来源清单不是有效的 UTF-8 JSON") from exc
    require(isinstance(manifest, dict), "来源清单应是对象")
    require(manifest.get("source_commit") == SOURCE_COMMIT, "样张版本与钉住的 main 不符")
    require(manifest.get("status") == "CONSTRUCTION_DRAFT__NOT_MERGED", "草稿身份不符")
    require(manifest.get("reuse") == "BYTE_IDENTICAL_OFFLINE_COPIES", "复用方式不符")
    require(manifest.get("product_adopted") is False, "不能标成产品采纳")
    require(manifest.get("live_store_checked") is False, "入口没有检查活库")
    rows = manifest.get("samples")
    require(isinstance(rows, list) and len(rows) == 3, "来源清单必须恰好含三张样张")
    require(all(isinstance(row, dict) for row in rows), "来源清单条目格式不对")
    by_path = {row.get("local_path"): row for row in rows}
    require(set(by_path) == {f"samples/{name}" for name in EXPECTED}, "样张名单不符")

    landing = audit_html(read_local(entry_dir, ENTRY_NAME))
    require(len(landing.links) == 3, "入口必须恰好提供三张卡")
    found = {link.get("id"): link.get("href") for link in landing.links}
    require(found == LINKS, "入口链接被改动、缺失或指向了别处")
    require(all(link.get("target") in (None, "_self") for link in landing.links),
            "链接应在原标签页打开，方便返回")
    text = "".join(landing.text)
    for token in ("FIXTURE_ONLY", "不检查活库", "GAP_NO_LIVE_STORE", "main@9c2fb958"):
        require(token in text, f"入口缺身份说明：{token}")

    for name, (sha256, blob_sha1) in EXPECTED.items():
        relative = f"samples/{name}"
        content = read_local(entry_dir, relative)
        row = by_path[relative]
        require(hashlib.sha256(content).hexdigest() == sha256, f"样张不是原样副本：{name}")
        require(row.get("sha256") == sha256, f"清单 SHA256 不符：{name}")
        require(row.get("source_git_blob_sha1") == blob_sha1, f"清单 Git blob 不符：{name}")
        require(row.get("size_bytes") == len(content), f"清单文件长度不符：{name}")
        source_path = (SOURCE_DIR / name).as_posix()
        require(row.get("source_path") == source_path, f"清单来源路径不符：{name}")
        source_url = (
            "https://github.com/cczz412/novel-architecture/blob/"
            f"{SOURCE_COMMIT}/{source_path}"
        )
        require(row.get("source_url") == source_url, f"清单来源链接不符：{name}")
        page = audit_html(content)
        require(not page.links, f"原样张不应新添跳转：{name}")
        sample_text = "".join(page.text)
        require("这层还没接到 B02，不编数字" in sample_text, f"覆盖边界缺失：{name}")
        if name == "no_live_store.html":
            require("GAP_NO_LIVE_STORE" in sample_text, "缺口标记缺失")
            require("没有可展示的事实条目" in sample_text, "缺口页不能伪造条目")
        else:
            require("FIXTURE_ONLY" in sample_text, f"夹具标记缺失：{name}")
            require("不是产品权威" in sample_text, f"夹具边界缺失：{name}")
        if source_root is not None:
            source = read_local(source_root, source_path)
            require(source == content, f"仓库样张与钉住的离线副本不同：{name}")
    return {
        "status": "PASS",
        "source_commit": SOURCE_COMMIT,
        "entry": ENTRY_NAME,
        "samples_verified": 3,
        "source_comparison": "MATCHED_THREE_SOURCE_FILES" if source_root else "PINNED_COPIES_ONLY",
        "live_store_checked": False,
        "check_scope": "STATIC_FILES_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="只核对入口与 HTML 样张，不读取候选库。")
    parser.add_argument("--source-root", type=Path, help="可选：含原预览样张的仓库根目录")
    args = parser.parse_args()
    try:
        result = check_entry(source_root=args.source_root)
    except (CheckError, OSError, UnicodeError, TypeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
