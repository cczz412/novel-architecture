"""M6 取证问答：关键词 → 已确认事实＋原文依据。

只读 M4（store）的事实记录（contracts/C4_FACT_QUERY.md，v0）；
只查 status=confirmed 的真值，候选和已拒绝不参与回答。
"""

from __future__ import annotations

from mvp import store


def search_confirmed(project: str, keywords: list[str]) -> list[dict]:
    """全部关键词同时命中事实句文本才算命中。

    返回命中记录列表：C4 事实记录 ＋ chapter_title（内存态补充，不落盘）。
    """
    titles = {
        c.get("id"): c.get("title", "?")
        for c in store.chapters(project)
        if isinstance(c, dict) and c.get("id")
    }
    return [
        {**f, "chapter_title": titles.get(f.get("chapter_id"), "?")}
        for f in store.facts(project)
        if isinstance(f, dict)
        and f.get("status") == store.STATUS_CONFIRMED
        and all(k in (f.get("text") or "") for k in keywords)
    ]
