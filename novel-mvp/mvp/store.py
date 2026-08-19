"""M4 事实账：项目/章节/事实的存取与状态管理，全线唯一真源。

schema v0 是临时件：只为跑通「导入→确认→入账→取证」这个环。
小说架构仓的 N16 语义合同（表述/命题拆分）定案后，本文件整体重建。

C1 v1 current view 只接受上游已经提交的 C11 revision ref；本模块不创建、
不猜测 chapter revision，也不把 legacy C1 v0 静默升级。

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

import copy
import hashlib
import json
import time
from pathlib import Path

from jsonschema import Draft202012Validator

from . import factstore

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
C11_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "C11_CHAPTER_REVISION_LEDGER.schema.json"
)

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


def intake_sources(project: str) -> list[dict]:
    """读取 C10 parent source；旧项目没有该文件时按空列表兼容。"""
    data = _load(_require(project) / "intake_sources.json", [])
    if not isinstance(data, list):
        raise SystemExit("intake_sources.json 不是数组，材料账坏了")
    return data


def intake_material_units(project: str) -> list[dict]:
    """读取 C10 材料单元；身份真值只存在这里，不复制进 C1。"""
    data = _load(_require(project) / "intake_material_units.json", [])
    if not isinstance(data, list):
        raise SystemExit("intake_material_units.json 不是数组，材料账坏了")
    return data


def intake_c1_projections(project: str) -> list[dict]:
    """读取 C10→C1 派生回执；它只防重复投影，不拥有材料身份。"""
    data = _load(_require(project) / "intake_c1_projections.json", [])
    if not isinstance(data, list):
        raise SystemExit("intake_c1_projections.json 不是数组，投影回执坏了")
    return data


def add_intake_source(project: str, source: dict) -> dict:
    """保存冻结 source；相同 id 只接受逐字段完全一致的重复写。"""
    d = _require(project)
    sources = intake_sources(project)
    for existing in sources:
        if existing.get("source_id") != source.get("source_id"):
            continue
        if existing != source:
            raise ValueError(f"source_id 已存在但内容不同：{source.get('source_id')}")
        return existing
    sources.append(source)
    _save(d / "intake_sources.json", sources)
    return source


def add_intake_material_units(project: str, records: list[dict]) -> list[dict]:
    """批量追加新 C10 单元；稳定 id 撞号时失败关闭，不覆盖旧身份链。"""
    d = _require(project)
    current = intake_material_units(project)
    used = {item.get("material_unit_id") for item in current if isinstance(item, dict)}
    incoming = [item.get("material_unit_id") for item in records]
    if len(incoming) != len(set(incoming)):
        raise ValueError("同批 C10 material_unit_id 重复")
    collisions = sorted(item for item in incoming if item in used)
    if collisions:
        raise ValueError(f"C10 material_unit_id 已存在：{collisions}")
    if not records:
        return []
    current.extend(records)
    _save(d / "intake_material_units.json", current)
    return records


def append_intake_identity_revision(project: str, record: dict) -> dict:
    """用已含完整历史的新 C10 record 替换旧 record，只允许追加一条 revision。"""
    d = _require(project)
    records = intake_material_units(project)
    unit_id = record.get("material_unit_id")
    for index, existing in enumerate(records):
        if existing.get("material_unit_id") != unit_id:
            continue
        if record.get("source_ref") != existing.get("source_ref"):
            raise ValueError("身份修订不能改变 C10 source span")
        old_revisions = existing.get("identity_revisions")
        new_revisions = record.get("identity_revisions")
        if (
            not isinstance(old_revisions, list)
            or not isinstance(new_revisions, list)
            or len(new_revisions) != len(old_revisions) + 1
            or new_revisions[:-1] != old_revisions
        ):
            raise ValueError("身份修订必须在完整旧 revision 链后只追加一条")
        records[index] = record
        _save(d / "intake_material_units.json", records)
        return record
    raise ValueError(f"C10 material unit 不存在：{unit_id}")


def add_intake_c1_projections(project: str, receipts: list[dict]) -> list[dict]:
    """追加 C10→C1 派生回执；同一 material revision 只允许投影一次。"""
    d = _require(project)
    current = intake_c1_projections(project)
    used = {
        (item.get("material_unit_id"), item.get("identity_revision_no"))
        for item in current
        if isinstance(item, dict)
    }
    incoming = [
        (item.get("material_unit_id"), item.get("identity_revision_no"))
        for item in receipts
    ]
    if len(incoming) != len(set(incoming)) or any(key in used for key in incoming):
        raise ValueError("同一 C10 material revision 不能重复投影到 C1")
    if not receipts:
        return []
    current.extend(receipts)
    _save(d / "intake_c1_projections.json", current)
    return receipts


def add_chapter(project: str, title: str, text: str, kind: str = "draft") -> dict:
    """kind: draft=已有正文, outline=大纲/规划条目"""
    return add_chapters(project, [{"title": title, "text": text, "kind": kind}])[0]


def _validate_c1_v1_current_view(chapter: dict) -> None:
    schema = json.loads(C11_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    if next(validator.iter_errors(chapter), None) is not None:
        raise ValueError("C1_V1_CURRENT_VIEW_INVALID")
    revision_ref = chapter["chapter_revision_ref"]
    if revision_ref["chapter_id"] != chapter["id"]:
        raise ValueError("C1_V1_REVISION_CHAPTER_MISMATCH")
    text_sha256 = hashlib.sha256(chapter["text"].encode("utf-8")).hexdigest()
    if revision_ref["revision_text_sha256"] != text_sha256:
        raise ValueError("C1_V1_REVISION_SHA_MISMATCH")


def add_c1_v1_current_view(
    project: str,
    *,
    title: str,
    text: str,
    chapter_revision_ref: dict,
) -> dict:
    """写入一条 C1 v1 current view；C11 真源与事务提交由上游协调器负责。"""
    d = _require(project)
    chs = chapters(project)
    chapter = {
        "contract": "C1_CHAPTER_DOC",
        "version": "v1",
        "id": f"c{len(chs) + 1:02d}",
        "title": title,
        "kind": "draft",
        "text": text,
        "added_at": _now(),
        "chapter_revision_ref": copy.deepcopy(chapter_revision_ref),
    }
    _validate_c1_v1_current_view(chapter)
    chs.append(chapter)
    _save(d / "chapters.json", chs)
    return chapter


def add_chapters(project: str, items: list[dict]) -> list[dict]:
    """一次写入一批 C1；整批校验完成后才替换 chapters.json。"""
    d = _require(project)
    chs = chapters(project)
    added_at = _now()
    built: list[dict] = []
    for offset, item in enumerate(items, 1):
        if not isinstance(item.get("title"), str) or not isinstance(item.get("text"), str):
            raise ValueError("批量章节需要字符串 title 和 text")
        kind = item.get("kind", "draft")
        if kind not in {"draft", "outline"}:
            raise ValueError(f"不支持的章节 kind：{kind}")
        built.append(
            {
                "id": f"c{len(chs) + offset:02d}",
                "title": item["title"],
                "kind": kind,
                "text": item["text"],
                "added_at": added_at,
            }
        )
    if not built:
        return []
    chs.extend(built)
    _save(d / "chapters.json", chs)
    return built


def _alloc_fact_ids(fs: list[dict], n: int) -> list[str]:
    """发 n 个保证不撞号的新事实号：从现有最大号顺延，逐个对全账查重。

    I-014 教训：老发号「条数+1」在账本有缺号/历史错号时会撞上已有号
    （《三国》f274–f323 各挂两条就是这么来的）。号唯一是 C4 合同底线。
    """
    return factstore.allocate_fact_ids(fs, n)


def add_fact_candidates(project: str, chapter_id: str, items: list[dict], source: str) -> int:
    d = _require(project)
    try:
        receipt = factstore.add_fact_candidates(
            d,
            chapter_id=chapter_id,
            items=items,
            source=source,
            timestamp=_now(),
        )
    except factstore.FactstoreError as exc:
        raise SystemExit(str(exc)) from exc
    return receipt["candidate_count"]


def repair_ids(project: str) -> dict:
    """修账工具（I-014）：扫描全账，重复事实号的后到者迁移到新号。

    每个号只认账面首次出现的那条（与 M7 完整性预检同口径）；
    后到者拿 _alloc_fact_ids 发的新号，原号记进 id_remapped_from 字段留痕。
    返回修账报告：{"total": 总条数, "remap": [{"old","new","chapter_id","seg","text"}…]}。
    无重复时不写盘。
    """
    d = _require(project)
    try:
        return factstore.repair_duplicate_fact_ids(d, timestamp=_now())
    except factstore.FactstoreError as exc:
        raise SystemExit(str(exc)) from exc


def review_fact(
    project: str,
    fact_id: str,
    *,
    decision: str,
    note: str = "",
    replacement_text: str | None = None,
    operation_id: str | None = None,
) -> dict:
    """旧 CLI／调用面的兼容入口；底层只走 FACT_REVIEW_ACTION 事务。"""
    d = _require(project)
    matches = [item for item in facts(project) if item.get("id") == fact_id]
    if len(matches) != 1:
        raise SystemExit(f"事实不存在或编号重复：{fact_id}")
    try:
        action = factstore.build_review_action(
            matches[0],
            decision=decision,
            note=note,
            replacement_text=replacement_text,
            operation_id=operation_id,
        )
        factstore.review_fact(d, action=action, timestamp=_now())
    except factstore.FactstoreError as exc:
        raise SystemExit(str(exc)) from exc
    current = [item for item in facts(project) if item.get("id") == fact_id]
    if len(current) != 1:
        raise SystemExit(f"事务提交后事实无法唯一回读：{fact_id}")
    return current[0]


def set_status(project: str, fact_id: str, status: str, note: str = "") -> dict:
    if status not in {STATUS_CONFIRMED, STATUS_REJECTED}:
        raise SystemExit(f"不支持的事实处置状态：{status}")
    return review_fact(
        project,
        fact_id,
        decision="confirm" if status == STATUS_CONFIRMED else "reject",
        note=note,
    )


def edit_fact_text(project: str, fact_id: str, new_text: str) -> dict:
    """确认时改写事实句：原候选文本备档进 note，再换上新句。"""
    return review_fact(project, fact_id, decision="edit", replacement_text=new_text)
