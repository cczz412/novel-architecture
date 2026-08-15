"""M1 导入器：用户文件 → 章节文档（C1）＋导入损失报告。

产出合同：contracts/C1_CHAPTER_DOC.md（v0）。落盘走 M4（store）。
损失报告 v0 是最小版：只报本次导入的章数、总字数和空章警告，不落盘。
"""

from __future__ import annotations

from pathlib import Path

from mvp import store


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"文件不存在或不是文件：{path}")
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"读不了这个文件的编码（请另存为 UTF-8）：{path}")


def ingest_text(project: str, title: str, text: str, kind: str = "draft") -> dict:
    """单份文本入库，返回 C1 章节文档。"""
    return store.add_chapter(project, title, text, kind)


def ingest_files(project: str, files: list[str], kind: str = "draft",
                 title: str | None = None, on_imported=None) -> dict:
    """批量导入文件。

    on_imported(chapter, text_len)：每导入一章回调一次（CLI 用来逐行打印）。
    返回导入损失报告最小版：
        {"count": 章数, "total_chars": 总字数, "warnings": [空章警告…], "chapters": [C1…]}
    """
    chapters: list[dict] = []
    warnings: list[str] = []
    total_chars = 0
    for f in files:
        p = Path(f)
        text = _read_text(p)
        ch = ingest_text(project, title or p.stem, text, kind)
        chapters.append(ch)
        total_chars += len(text)
        if not text.strip():
            warnings.append(f"{ch['id']}《{ch['title']}》正文为空（来源 {p.name}）")
        if on_imported:
            on_imported(ch, len(text))
    return {"count": len(chapters), "total_chars": total_chars,
            "warnings": warnings, "chapters": chapters}
