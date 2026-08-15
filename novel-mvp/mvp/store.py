"""M4 事实账：项目/章节/事实的存取与状态管理，全线唯一真源。

schema v0 是临时件：只为跑通「导入→确认→入账→取证」这个环。
小说架构仓的 N16 语义合同（表述/命题拆分）定案后，本文件整体重建。

目录结构：
    data/<项目名>/project.json    项目元信息
    data/<项目名>/chapters.json   章节列表（含正文全文，字段见 contracts/C1_CHAPTER_DOC.md）
    data/<项目名>/facts.json      事实账（候选 + 已确认 + 已拒绝）

事实条目 v0 字段（详见 contracts/C4_FACT_QUERY.md）：
    id / chapter_id / text（事实句） / quote（原文依据） /
    status: extracted（候选）| confirmed（已确认）| rejected（已拒绝）/
    source（候选来自哪：manual | 文件名 | 将来的模型名） / note
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

STATUS_EXTRACTED = "extracted"
STATUS_CONFIRMED = "confirmed"
STATUS_REJECTED = "rejected"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _safe_project_name(project: str) -> str:
    """项目名只能是 data/ 下一层目录，不能带斜杠、不能是 . / ..。"""
    name = (project or "").strip()
    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or Path(name).is_absolute()
    ):
        raise SystemExit(f"项目名不合法：{project!r}（只能是 data/ 下的一层名字，不能带斜杠）")
    return name


def project_dir(project: str) -> Path:
    name = _safe_project_name(project)
    d = (DATA_ROOT / name).resolve()
    root = DATA_ROOT.resolve()
    if d != root / name and root not in d.parents:
        raise SystemExit(f"项目名不合法：{project!r}（会落到 data/ 外面）")
    return DATA_ROOT / name


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"账本坏了，读不了 {path.name}：{e}") from e


def _save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def init_project(project: str) -> Path:
    d = project_dir(project)
    meta_path = d / "project.json"
    if meta_path.exists():
        raise SystemExit(f"项目已存在：{d}")
    _save(meta_path, {"name": project, "created_at": _now(), "schema": "v0"})
    _save(d / "chapters.json", [])
    _save(d / "facts.json", [])
    return d


def _require(project: str) -> Path:
    d = project_dir(project)
    if not (d / "project.json").exists():
        raise SystemExit(f"项目不存在：{project}（先 init）")
    return d


def chapters(project: str) -> list[dict]:
    data = _load(_require(project) / "chapters.json", [])
    if not isinstance(data, list):
        raise SystemExit("chapters.json 不是数组，账本坏了")
    return data


def facts(project: str) -> list[dict]:
    data = _load(_require(project) / "facts.json", [])
    if not isinstance(data, list):
        raise SystemExit("facts.json 不是数组，账本坏了")
    return data


def add_chapter(project: str, title: str, text: str, kind: str = "draft") -> dict:
    """kind: draft=已有正文, outline=大纲/规划条目"""
    d = _require(project)
    chs = chapters(project)
    ch = {
        "id": f"c{len(chs) + 1:02d}",
        "title": title,
        "kind": kind,
        "text": text,
        "added_at": _now(),
    }
    chs.append(ch)
    _save(d / "chapters.json", chs)
    return ch


def _alloc_fact_ids(fs: list[dict], n: int) -> list[str]:
    """发 n 个保证不撞号的新事实号：从现有最大号顺延，逐个对全账查重。

    I-014 教训：老发号「条数+1」在账本有缺号/历史错号时会撞上已有号
    （《三国》f274–f323 各挂两条就是这么来的）。号唯一是 C4 合同底线。
    """
    used = {f.get("id") for f in fs if isinstance(f, dict) and f.get("id")}
    nums = [
        int(m.group(1))
        for f in fs if isinstance(f, dict)
        for m in [re.fullmatch(r"f(\d+)", str(f.get("id") or ""))]
        if m
    ]
    nxt = max(nums, default=0) + 1
    out: list[str] = []
    while len(out) < n:
        fid = f"f{nxt:03d}"
        if fid not in used:
            out.append(fid)
            used.add(fid)
        nxt += 1
    return out


def add_fact_candidates(project: str, chapter_id: str, items: list[dict], source: str) -> int:
    d = _require(project)
    if chapter_id not in {c.get("id") for c in chapters(project) if isinstance(c, dict)}:
        raise SystemExit(f"章节不存在：{chapter_id}")
    fs = facts(project)
    n0 = len(fs)
    valid = [
        it for it in items
        if isinstance(it, dict) and (it.get("text") or "").strip()
    ]
    new_ids = _alloc_fact_ids(fs, len(valid))
    for it, fid in zip(valid, new_ids):
        text = it["text"].strip()
        rec = {
            "id": fid,
            "chapter_id": chapter_id,
            "text": text,
            "quote": (it.get("quote") or "").strip(),
            "status": STATUS_EXTRACTED,
            "source": source,
            "note": "",
            "added_at": _now(),
        }
        if it.get("seg"):
            rec["seg"] = it["seg"]
        fs.append(rec)
    _save(d / "facts.json", fs)
    return len(fs) - n0


def repair_ids(project: str) -> dict:
    """修账工具（I-014）：扫描全账，重复事实号的后到者迁移到新号。

    每个号只认账面首次出现的那条（与 M7 完整性预检同口径）；
    后到者拿 _alloc_fact_ids 发的新号，原号记进 id_remapped_from 字段留痕。
    返回修账报告：{"total": 总条数, "remap": [{"old","new","chapter_id","seg","text"}…]}。
    无重复时不写盘。
    """
    d = _require(project)
    fs = facts(project)
    seen: set[str] = set()
    latecomers = []
    for f in fs:
        if f["id"] in seen:
            latecomers.append(f)
        else:
            seen.add(f["id"])
    if not latecomers:
        return {"total": len(fs), "remap": []}
    new_ids = _alloc_fact_ids(fs, len(latecomers))
    remap = []
    for f, new_id in zip(latecomers, new_ids):
        remap.append({
            "old": f["id"], "new": new_id, "chapter_id": f["chapter_id"],
            "seg": f.get("seg"), "text": f["text"][:40],
        })
        f["id_remapped_from"] = f["id"]
        f["id"] = new_id
    _save(d / "facts.json", fs)
    report = {"repaired_at": _now(), "total": len(fs), "remap": remap}
    _save(d / "repair_ids_report.json", report)
    return report


def set_status(project: str, fact_id: str, status: str, note: str = "") -> dict:
    d = _require(project)
    fs = facts(project)
    for f in fs:
        if f["id"] == fact_id:
            f["status"] = status
            f["decided_at"] = _now()
            if note:
                f["note"] = note
            _save(d / "facts.json", fs)
            return f
    raise SystemExit(f"事实不存在：{fact_id}")


def edit_fact_text(project: str, fact_id: str, new_text: str) -> dict:
    """确认时改写事实句：原候选文本备档进 note，再换上新句。"""
    d = _require(project)
    fs = facts(project)
    for f in fs:
        if f["id"] == fact_id:
            f["note"] = f"原文候选：{f['text']}"
            f["text"] = new_text
            _save(d / "facts.json", fs)
            return f
    raise SystemExit(f"事实不存在：{fact_id}")
