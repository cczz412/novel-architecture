from __future__ import annotations

import hashlib
import io
import stat
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ingest, input_router, store
    from mvp.upload_source import CLOUD_SWAP_POINT, LOCAL_FILESYSTEM_ONLY, UploadSource
finally:
    sys.path.pop(0)


RECORDED_AT = "2026-08-19T02:30:00+08:00"


def _zip(members: dict[str, bytes], *, symlink: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "target.txt")
    return buffer.getvalue()


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    ).encode()
    return _zip({"word/document.xml": document, "[Content_Types].xml": b"<Types/>"})


def _confirmed_chapter(length: int) -> list[dict]:
    return [
        {
            "start": 0,
            "end": length,
            "role": "CHAPTER",
            "state": "CONFIRMED",
            "basis": {"type": "USER_DECLARATION", "reference": "UPLOAD-UI"},
            "actor": {"type": "USER", "reference": "AUTHOR"},
            "recorded_at": RECORDED_AT,
            "reason": "作者明确上传为章节",
        }
    ]


def _init(tmp_path: Path, monkeypatch, project: str) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "data")
    store.init_project(project)


def test_memory_txt_md_and_encoding_hint_keep_raw_upload_objects() -> None:
    txt = "第一章\n正文。".encode()
    md_text = "# 第二章\n正文二。"
    md = md_text.encode("gb18030")
    uploads = [
        UploadSource("c01.txt", txt),
        UploadSource("c02.md", md, encoding_hint="gb18030"),
    ]

    items, receipt = input_router.collect_uploads(uploads)

    assert receipt["status"] == "READY"
    assert [item["source_name"] for item in items] == ["c01.txt", "c02.md"]
    assert items[1]["raw_bytes"].decode(items[1]["encoding"]) == md_text
    assert receipt["upload_objects"] == [upload.caller_record() for upload in uploads]
    assert receipt["upload_objects"][0]["raw_bytes"] is txt
    assert receipt["upload_objects"][0]["source_sha256"] == hashlib.sha256(txt).hexdigest()
    assert all(item["cloud_swap_point"] == CLOUD_SWAP_POINT for item in receipt["upload_objects"])


@pytest.mark.parametrize(
    "declarations",
    [
        None,
        _confirmed_chapter(10),
        {"book.zip/c01.txt": _confirmed_chapter(10)},
    ],
)
def test_caller_record_preserves_declarations_as_a_deep_copy(declarations) -> None:
    upload = UploadSource("book.txt", b"content", declarations=declarations)

    first = upload.caller_record()
    second = upload.caller_record()

    assert first["declarations"] == declarations
    assert second["declarations"] == declarations
    if isinstance(first["declarations"], list):
        first["declarations"][0]["role"] = "REFERENCE"
    elif isinstance(first["declarations"], dict):
        first["declarations"]["book.zip/c01.txt"][0]["role"] = "REFERENCE"
    assert second["declarations"] == declarations
    assert upload.declarations == declarations


def test_memory_docx_and_zip_reuse_existing_terminal_shapes() -> None:
    docx = UploadSource("chapter.docx", _docx(["正文第一段", "正文第二段"]))
    docx_items, docx_receipt = input_router.collect_uploads([docx])
    assert docx_receipt["status"] == "READY"
    assert docx_items[0]["source_name"] == "chapter.docx#word/document.xml"
    assert docx_items[0]["raw_bytes"] == "正文第一段\n正文第二段".encode()

    payload = _zip({"c01.txt": "正文一。".encode(), "c02.md": "正文二。".encode()})
    items, receipt = input_router.collect_uploads([UploadSource("book.zip", payload)])
    assert receipt["status"] == "READY"
    assert [item["source_name"] for item in items] == [
        "book.zip/c01.txt",
        "book.zip/c02.md",
    ]
    assert receipt["upload_objects"][0]["raw_bytes"] == payload
    assert receipt["upload_objects"][0]["source_sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    "name",
    ["", "..", "../evil.txt", "/tmp/evil.txt", "dir/evil.txt", "dir\\evil.txt", "C:\\evil.txt", "book..txt"],
)
def test_upload_source_rejects_unsafe_logical_names(name: str) -> None:
    with pytest.raises(ValueError, match="UPLOAD_SOURCE_NAME"):
        UploadSource(name, b"content")


@pytest.mark.parametrize(
    ("payload", "block_type"),
    [
        (_zip({"../evil.txt": b"evil", "c01.txt": "正文。".encode()}), "unsafe_archive_path"),
        (_zip({"c01.txt": "正文。".encode()}, symlink="link.txt"), "archive_symlink"),
    ],
)
def test_memory_zip_keeps_path_and_symlink_guards(payload: bytes, block_type: str) -> None:
    _, receipt = input_router.collect_uploads([UploadSource("unsafe.zip", payload)])
    assert receipt["status"] == "BLOCKED"
    assert any(item["type"] == block_type for item in receipt["blocks"])


def test_ingest_uploads_uses_embedded_declarations_without_disk_path(
    tmp_path: Path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "memory-ingest")
    text = "第一章 雨夜\n沈砚推门。\n"
    raw = text.encode()
    upload = UploadSource(
        "chapter.txt",
        raw,
        declarations=_confirmed_chapter(len(text)),
    )

    report = ingest.ingest_uploads("memory-ingest", [upload])

    assert report["count"] == 1
    assert report["chapters"][0]["text"] == "沈砚推门。\n"
    assert report["material_units"][0]["identity_revisions"][-1]["role"] == "CHAPTER"
    assert report["upload_objects"][0]["raw_bytes"] == raw
    assert report["upload_objects"][0]["source_sha256"] == upload.sha256


def test_local_path_adapter_matches_memory_core(tmp_path: Path) -> None:
    raw = "第一章\n正文。".encode()
    path = tmp_path / "c01.txt"
    path.write_bytes(raw)

    path_items, path_receipt = input_router.collect_paths([str(path)])
    memory_items, memory_receipt = input_router.collect_uploads([UploadSource("c01.txt", raw)])

    assert LOCAL_FILESYSTEM_ONLY == "LOCAL_FILESYSTEM_ONLY"
    assert path_items == memory_items
    assert path_receipt["sources"] == memory_receipt["sources"]
    assert path_receipt["upload_objects"] == memory_receipt["upload_objects"]
