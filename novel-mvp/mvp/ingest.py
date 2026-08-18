"""M1 导入器：用户文件 → 章节文档（C1）＋导入损失报告。

产出合同：contracts/C1_CHAPTER_DOC.md（v0）。落盘走 M4（store）。
损失报告 v0 是最小版：只报本次导入的章数、总字数和空章警告，不落盘。
"""

from __future__ import annotations

from pathlib import Path

from typing import Any

from mvp import input_router, intake_identity, store


MATERIAL_ROLES = {"INTRO", "CHAPTER", "SETTING", "TITLE", "TAGS"}


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


def _whole_source_declaration(length: int, material_role: str | None) -> dict[str, Any]:
    role = material_role.upper() if isinstance(material_role, str) else None
    if role == "UNKNOWN":
        role = None
    if role is not None and role not in MATERIAL_ROLES:
        raise ValueError(f"不支持的 material role：{material_role}")
    if role is None:
        return {
            "start": 0,
            "end": length,
            "role": None,
            "state": "UNKNOWN",
            "basis": {"type": "NO_ASSERTION", "reference": None},
            "actor": {"type": "SYSTEM", "reference": "C10-FIRST-DEFAULT-UNKNOWN"},
            "reason": None,
        }
    return {
        "start": 0,
        "end": length,
        "role": role,
        "state": "CONFIRMED",
        "basis": {"type": "USER_DECLARATION", "reference": "CLI-MATERIAL-ROLE"},
        "actor": {"type": "USER", "reference": "CLI-USER"},
        "reason": f"用户在导入入口明确声明为 {role}",
    }


def ingest_text(
    project: str,
    title: str,
    text: str,
    kind: str = "draft",
    *,
    material_role: str | None = None,
) -> dict:
    """纯粘贴入口；draft 默认 Unknown，只有显式 Chapter 才能生成 C1。"""
    if kind == "outline":
        chapter = store.add_chapter(project, title, text, kind)
        return {
            "count": 1,
            "total_chars": len(text),
            "warnings": [],
            "chapters": [chapter],
            "api_calls": 0,
            "automatic_retries": 0,
        }
    if kind != "draft":
        raise ValueError(f"不支持的导入 kind：{kind}")
    if not text:
        raise ValueError("纯粘贴输入不能为空")
    declarations = [_whole_source_declaration(len(text), material_role)]
    report = intake_identity.ingest_explicit_materials(
        project,
        source_name=title,
        raw_bytes=text.encode("utf-8"),
        encoding="utf-8",
        declarations=declarations,
    )
    return {
        "count": len(report["chapters"]),
        "total_chars": len(text),
        **report,
    }


def ingest_explicit_materials(
    project: str,
    *,
    source_name: str,
    raw_bytes: bytes,
    encoding: str,
    declarations: list[dict],
) -> dict:
    """C10-first 明确材料入口；身份由调用方声明，不从内容猜。"""
    return intake_identity.ingest_explicit_materials(
        project,
        source_name=source_name,
        raw_bytes=raw_bytes,
        encoding=encoding,
        declarations=declarations,
    )


def _resolve_declarations(
    items: list[dict[str, Any]],
    material_role: str | None,
    declaration_manifest: list[dict[str, Any]] | dict[str, list[dict[str, Any]]] | None,
) -> dict[str, list[dict[str, Any]]]:
    names = [item["source_name"] for item in items]
    if declaration_manifest is None:
        return {
            item["source_name"]: [
                _whole_source_declaration(
                    len(item["raw_bytes"].decode(item["encoding"], errors="strict")),
                    material_role,
                )
            ]
            for item in items
        }
    if isinstance(declaration_manifest, list):
        if len(items) != 1:
            raise ValueError("数组 declarations 只允许对应一个终端 source")
        return {items[0]["source_name"]: declaration_manifest}
    if not isinstance(declaration_manifest, dict):
        raise ValueError("declaration manifest 必须是数组或 source_name→数组对象")
    if set(declaration_manifest) != set(names):
        missing = sorted(set(names) - set(declaration_manifest))
        extra = sorted(set(declaration_manifest) - set(names))
        raise ValueError(f"declaration manifest source 不闭合：missing={missing} extra={extra}")
    if not all(isinstance(value, list) for value in declaration_manifest.values()):
        raise ValueError("declaration manifest 每个 source 必须对应 declarations 数组")
    return declaration_manifest


def _ingest_outline_files(
    project: str,
    files: list[str],
    title: str | None,
    on_imported,
) -> dict:
    pending = []
    lengths = []
    total_chars = 0
    for value in files:
        path = Path(value)
        text = _read_text(path)
        total_chars += len(text)
        pending.append({"title": title or path.stem, "text": text, "kind": "outline"})
        lengths.append(len(text))
    chapters = store.add_chapters(project, pending) if pending else []
    if on_imported:
        for chapter, text_len in zip(chapters, lengths):
            on_imported(chapter, text_len)
    return {
        "count": len(chapters),
        "total_chars": total_chars,
        "warnings": [],
        "chapters": chapters,
        "api_calls": 0,
        "automatic_retries": 0,
    }


def ingest_files(
    project: str,
    files: list[str],
    kind: str = "draft",
    title: str | None = None,
    on_imported=None,
    *,
    material_role: str | None = None,
    declaration_manifest: list[dict[str, Any]]
    | dict[str, list[dict[str, Any]]]
    | None = None,
) -> dict:
    """批量导入文件。

    on_imported(chapter, text_len)：每导入一章回调一次（CLI 用来逐行打印）。
    返回导入损失报告最小版：
        {"count": 章数, "total_chars": 总字数, "warnings": [空章警告…], "chapters": [C1…]}
    """
    if kind == "outline":
        if material_role is not None or declaration_manifest is not None:
            raise ValueError("outline 兼容入口不能同时携带 C10 material role／declarations")
        return _ingest_outline_files(project, files, title, on_imported)
    if kind != "draft":
        raise ValueError(f"不支持的导入 kind：{kind}")

    items, format_receipt = input_router.collect_paths(files)
    if format_receipt["status"] != "READY":
        raise input_router.InputRoutingBlocked(format_receipt)
    declarations = _resolve_declarations(items, material_role, declaration_manifest)
    batch_items = []
    for item in items:
        source_name = item["source_name"]
        source_declarations = declarations[source_name]
        has_confirmed_chapter = any(
            declaration.get("state") == "CONFIRMED"
            and declaration.get("role") == "CHAPTER"
            for declaration in source_declarations
            if isinstance(declaration, dict)
        )
        batch_items.append(
            {
                "source_name": source_name,
                "raw_bytes": item["raw_bytes"],
                "encoding": item["encoding"],
                "declarations": source_declarations,
                "default_title": title or Path(source_name.split("#", 1)[0]).stem,
                "chapter_no_hint": item["chapter_no_hint"] if has_confirmed_chapter else None,
            }
        )
    report = intake_identity.ingest_explicit_material_batch(
        project,
        batch_items,
        enforce_global_chapter_sequence=True,
    )
    total_chars = sum(len(source["decoded_text"]) for source in report["sources"])
    warnings = [*format_receipt["warnings"], *report["warnings"]]
    if on_imported:
        for chapter in report["chapters"]:
            on_imported(chapter, len(chapter["text"]))
    return {
        "count": len(report["chapters"]),
        "total_chars": total_chars,
        "warnings": warnings,
        "chapters": report["chapters"],
        "sources": report["sources"],
        "material_units": report["material_units"],
        "projection_receipts": report["projection_receipts"],
        "format_receipt": format_receipt,
        "api_calls": 0,
        "automatic_retries": 0,
    }
