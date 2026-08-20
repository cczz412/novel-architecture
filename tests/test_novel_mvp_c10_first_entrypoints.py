from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    import cli as product_cli
    from mvp import ingest, input_router, store
finally:
    sys.path.pop(0)


RECORDED_AT = "2026-08-18T18:00:00+08:00"


def _init(tmp_path: Path, monkeypatch, project: str) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "data")
    store.init_project(project)


def _write(tmp_path: Path, name: str, payload: str | bytes) -> Path:
    path = tmp_path / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_bytes(payload)
    return path


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in members.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 8, 18, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return buffer.getvalue()


def _docx(paragraphs: list[str], *, header: str | None = None) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    ).encode("utf-8")
    members = {
        "word/document.xml": document,
        "[Content_Types].xml": b"<Types/>",
    }
    if header is not None:
        members["word/header1.xml"] = header.encode("utf-8")
    return _zip(members)


def _confirmed(start: int, end: int, role: str, suffix: str) -> dict:
    return {
        "start": start,
        "end": end,
        "role": role,
        "state": "CONFIRMED",
        "basis": {"type": "USER_DECLARATION", "reference": f"UI-{suffix}"},
        "actor": {"type": "USER", "reference": "USER-ENTRYPOINT-TEST"},
        "recorded_at": RECORDED_AT,
        "reason": f"用户明确声明为 {role}",
    }


@pytest.mark.parametrize(
    "name,text",
    [
        ("intro.txt", "作品简介：她在旧城寻找兄长。\n"),
        ("setting.txt", "设定集：王朝共有九州。\n"),
        ("title.txt", "《雾城来信》\n"),
        ("tags.txt", "标签：重生、权谋、女强\n"),
        ("unknown.txt", "身份未确认的材料。\n"),
    ],
)
def test_entry_01_default_file_identity_is_unknown_and_never_c1(
    tmp_path, monkeypatch, name: str, text: str
) -> None:
    project = f"default-{Path(name).stem}"
    _init(tmp_path, monkeypatch, project)
    report = ingest.ingest_files(project, [str(_write(tmp_path, name, text))])

    assert report["chapters"] == store.chapters(project) == []
    assert len(report["material_units"]) == 1
    identity = report["material_units"][0]["identity_revisions"][-1]
    assert identity["state"] == "UNKNOWN" and identity["role"] is None
    assert report["api_calls"] == report["automatic_retries"] == 0


@pytest.mark.parametrize(
    "role,expected_version",
    [("INTRO", "v1"), ("SETTING", "v2"), ("TITLE", "v3"), ("TAGS", "v4")],
)
def test_entry_02_explicit_nonchapter_roles_use_c10_and_never_c1(
    tmp_path, monkeypatch, role: str, expected_version: str
) -> None:
    project = f"role-{role.lower()}"
    _init(tmp_path, monkeypatch, project)
    text = f"明确 {role} 材料。\n"
    path = _write(tmp_path, f"{role.lower()}.txt", text)
    report = ingest.ingest_files(project, [str(path)], material_role=role)

    assert report["chapters"] == []
    assert len(report["material_units"]) == 1
    assert report["material_units"][0]["version"] == expected_version
    assert report["material_units"][0]["identity_revisions"][-1]["role"] == role


def test_entry_03_cli_default_is_unknown_but_explicit_chapter_reaches_m3(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "cli-default")
    tags_path = _write(tmp_path, "tags.txt", "标签：重生、权谋、女强\n")
    product_cli.cmd_ingest(
        SimpleNamespace(
            project="cli-default",
            files=[str(tags_path)],
            outline=False,
            title=None,
            material_role=None,
            declarations=None,
        )
    )
    assert store.chapters("cli-default") == []

    _init(tmp_path, monkeypatch, "cli-chapter")
    chapter_path = _write(
        tmp_path,
        "chapter.txt",
        "第一章 雨夜\n沈砚推门。\n第二章 清晨\n他带着印册离开。\n",
    )
    product_cli.cmd_ingest(
        SimpleNamespace(
            project="cli-chapter",
            files=[str(chapter_path)],
            outline=False,
            title=None,
            material_role="chapter",
            declarations=None,
        )
    )
    chapters = store.chapters("cli-chapter")
    assert len(chapters) == 2
    cfg = {"seg_min_chars": 620, "seg_max_chars": 923, "halo_chars": 180}
    assert all(product_cli.prepare_m3_segments(chapter, cfg)[1]["status"] == "READY" for chapter in chapters)


def test_entry_04_paste_defaults_unknown_and_explicit_chapter_is_the_only_c1(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "paste-unknown")
    unknown = ingest.ingest_text("paste-unknown", "粘贴", "标签：重生、权谋\n")
    assert unknown["chapters"] == []
    assert unknown["material_units"][0]["identity_revisions"][-1]["role"] is None

    _init(tmp_path, monkeypatch, "paste-chapter")
    chapter = ingest.ingest_text(
        "paste-chapter",
        "粘贴章节",
        "第一章 雨夜\n沈砚推门。\n",
        material_role="CHAPTER",
    )
    assert len(chapter["chapters"]) == 1


def test_entry_05_cli_mixed_manifest_only_projects_chapter(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "mixed-cli")
    title = "《雾城来信》\n"
    intro = "作品简介：她在旧城寻找兄长。\n"
    setting = "设定集：王朝共有九州。\n"
    tags = "标签：重生、权谋、女强\n"
    chapter = "第一章 雨夜\n沈砚推门。\n"
    text = title + intro + setting + tags + chapter
    p1 = len(title)
    p2 = p1 + len(intro)
    p3 = p2 + len(setting)
    p4 = p3 + len(tags)
    declarations = [
        _confirmed(0, p1, "TITLE", "MIX-TIT"),
        _confirmed(p1, p2, "INTRO", "MIX-I"),
        _confirmed(p2, p3, "SETTING", "MIX-S"),
        _confirmed(p3, p4, "TAGS", "MIX-TAGS"),
        _confirmed(p4, len(text), "CHAPTER", "MIX-C"),
    ]
    source_path = _write(tmp_path, "mixed.txt", text)
    declaration_path = _write(
        tmp_path,
        "mixed.declarations.json",
        json.dumps(declarations, ensure_ascii=False),
    )
    product_cli.cmd_ingest(
        SimpleNamespace(
            project="mixed-cli",
            files=[str(source_path)],
            outline=False,
            title=None,
            material_role=None,
            declarations=str(declaration_path),
        )
    )

    units = store.intake_material_units("mixed-cli")
    assert [item["identity_revisions"][-1]["role"] for item in units] == [
        "TITLE",
        "INTRO",
        "SETTING",
        "TAGS",
        "CHAPTER",
    ]
    assert all(item["version"] == "v4" for item in units)
    chapters = store.chapters("mixed-cli")
    assert len(chapters) == 1
    assert all(value not in chapters[0]["text"] for value in (title, intro, setting, tags))


def test_entry_06_markdown_headings_ignore_fenced_fake_heading(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "markdown")
    text = (
        "# 第一章 雨夜\n正文一。\n"
        "```text\n# 第二章 假标题\n假正文。\n```\n"
        "# 第二章 旧印\n正文二。\n"
    )
    report = ingest.ingest_files(
        "markdown",
        [str(_write(tmp_path, "book.md", text))],
        material_role="CHAPTER",
    )

    assert len(report["chapters"]) == 2
    assert [item["title"] for item in report["chapters"]] == ["第一章 雨夜", "第二章 旧印"]
    assert "第二章 假标题" in report["chapters"][0]["text"]
    source = report["sources"][0]
    assert source["decoded_text"] == text
    assert source["source_sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_entry_07_docx_main_flow_becomes_derived_c10_source(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "docx")
    payload = _docx(["正文第一段", "正文第二段"])
    report = ingest.ingest_files(
        "docx",
        [str(_write(tmp_path, "c01.docx", payload))],
        material_role="CHAPTER",
    )

    assert len(report["chapters"]) == 1
    assert report["chapters"][0]["text"] == "正文第一段\n正文第二段"
    assert report["sources"][0]["decoded_text"] == "正文第一段\n正文第二段"
    root = report["format_receipt"]["sources"][0]
    assert root["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert root["derived_source_sha256"] == report["sources"][0]["source_sha256"]


def test_entry_08_docx_unparsed_area_blocks_without_partial_write(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "docx-block")
    payload = _docx(["正文"], header="<w:hdr xmlns:w='x'><w:p/></w:hdr>")
    with pytest.raises(input_router.InputRoutingBlocked) as caught:
        ingest.ingest_files(
            "docx-block",
            [str(_write(tmp_path, "c01.docx", payload))],
            material_role="CHAPTER",
        )
    assert caught.value.receipt["blocks"][0]["type"] == "unparsed_docx_area"
    assert store.intake_sources("docx-block") == []
    assert store.intake_material_units("docx-block") == []
    assert store.chapters("docx-block") == []


def test_entry_09_zip_txt_md_docx_chapters_are_atomic_and_ordered(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "zip-clean")
    payload = _zip(
        {
            "c01.txt": "正文一。".encode(),
            "c02.md": "正文二。".encode(),
            "c03.docx": _docx(["正文三。"]),
        }
    )
    report = ingest.ingest_files(
        "zip-clean",
        [str(_write(tmp_path, "book.zip", payload))],
        material_role="CHAPTER",
    )

    assert report["format_receipt"]["terminal_source_count"] == 3
    assert len(report["sources"]) == len(report["material_units"]) == 3
    assert [item["text"] for item in report["chapters"]] == ["正文一。", "正文二。", "正文三。"]
    assert [item["identity_revisions"][-1]["role"] for item in report["material_units"]] == [
        "CHAPTER",
        "CHAPTER",
        "CHAPTER",
    ]


def test_entry_10_zip_member_failure_and_missing_number_leave_zero_partial_state(
    tmp_path, monkeypatch
) -> None:
    _init(tmp_path, monkeypatch, "zip-block")
    payload = _zip(
        {
            "c01.txt": "正文一。".encode(),
            "c02.txt": "正文二。".encode(),
            "c03.docx": b"not-a-docx",
            "c04.txt": "正文四。".encode(),
        }
    )
    with pytest.raises(input_router.InputRoutingBlocked):
        ingest.ingest_files(
            "zip-block",
            [str(_write(tmp_path, "book.zip", payload))],
            material_role="CHAPTER",
        )
    assert store.intake_sources("zip-block") == []
    assert store.intake_material_units("zip-block") == []
    assert store.chapters("zip-block") == []


def test_entry_11_zip_path_traversal_blocks_before_any_write(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "zip-path")
    payload = _zip({"../evil.txt": b"evil", "c01.txt": "正文。".encode()})
    with pytest.raises(input_router.InputRoutingBlocked) as caught:
        ingest.ingest_files(
            "zip-path",
            [str(_write(tmp_path, "unsafe.zip", payload))],
            material_role="CHAPTER",
        )
    assert any(item["type"] == "unsafe_archive_path" for item in caught.value.receipt["blocks"])
    assert store.intake_sources("zip-path") == []
    assert store.chapters("zip-path") == []


def test_entry_12_multi_source_manifest_can_mix_roles_inside_zip(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "zip-mixed")
    members = {
        "title.txt": "《雾城来信》\n",
        "intro.txt": "作品简介：她在旧城寻找兄长。\n",
        "setting.txt": "设定集：王朝共有九州。\n",
        "tags.txt": "标签：重生、权谋、女强\n",
        "chapter.txt": "第一章 雨夜\n沈砚推门。\n",
    }
    payload = _zip({name: text.encode() for name, text in members.items()})
    path = _write(tmp_path, "materials.zip", payload)
    role_by_name = {
        "materials.zip/title.txt": "TITLE",
        "materials.zip/intro.txt": "INTRO",
        "materials.zip/setting.txt": "SETTING",
        "materials.zip/tags.txt": "TAGS",
        "materials.zip/chapter.txt": "CHAPTER",
    }
    manifest = {
        name: [_confirmed(0, len(members[name.split("/", 1)[1]]), role, name)]
        for name, role in role_by_name.items()
    }
    report = ingest.ingest_files(
        "zip-mixed",
        [str(path)],
        declaration_manifest=manifest,
    )

    assert len(report["material_units"]) == 5
    assert len(report["chapters"]) == 1
    assert [item["identity_revisions"][-1]["role"] for item in report["material_units"]] == [
        "TITLE",
        "INTRO",
        "SETTING",
        "TAGS",
        "CHAPTER",
    ]


def test_entry_13_cross_file_chapter_gap_blocks_before_c10_or_c1(tmp_path, monkeypatch) -> None:
    _init(tmp_path, monkeypatch, "sequence-gap")
    paths = [
        str(_write(tmp_path, "c01.txt", "正文一。")),
        str(_write(tmp_path, "c03.txt", "正文三。")),
    ]
    with pytest.raises(ValueError, match="跨文件章序"):
        ingest.ingest_files("sequence-gap", paths, material_role="CHAPTER")
    assert store.intake_sources("sequence-gap") == []
    assert store.intake_material_units("sequence-gap") == []
    assert store.chapters("sequence-gap") == []


def test_entry_13a_filename_and_content_chapter_number_conflict_blocks_all_writes(
    tmp_path,
    monkeypatch,
) -> None:
    _init(tmp_path, monkeypatch, "filename-content-conflict")
    path = _write(
        tmp_path,
        "c01.txt",
        "第六十七章 风暴\n沈砚推门。\n",
    )

    with pytest.raises(
        ValueError,
        match="文件名章号与正文标题章号冲突",
    ):
        ingest.ingest_files(
            "filename-content-conflict",
            [str(path)],
            material_role="CHAPTER",
        )

    assert store.intake_sources("filename-content-conflict") == []
    assert store.intake_material_units("filename-content-conflict") == []
    assert store.intake_c1_projections("filename-content-conflict") == []
    assert store.chapters("filename-content-conflict") == []


def test_entry_13b_zip_member_filename_and_content_conflict_is_atomic(
    tmp_path,
    monkeypatch,
) -> None:
    _init(tmp_path, monkeypatch, "zip-filename-content-conflict")
    payload = _zip(
        {
            "c01.txt": "第六十七章 风暴\n沈砚推门。\n".encode(),
            "c02.txt": "第二章 清晨\n他离开旧宅。\n".encode(),
        }
    )

    with pytest.raises(
        ValueError,
        match="文件名章号与正文标题章号冲突",
    ):
        ingest.ingest_files(
            "zip-filename-content-conflict",
            [str(_write(tmp_path, "book.zip", payload))],
            material_role="CHAPTER",
        )

    assert store.intake_sources("zip-filename-content-conflict") == []
    assert store.intake_material_units("zip-filename-content-conflict") == []
    assert store.intake_c1_projections("zip-filename-content-conflict") == []
    assert store.chapters("zip-filename-content-conflict") == []


def test_entry_13c_matching_filename_and_content_chapter_number_still_passes(
    tmp_path,
    monkeypatch,
) -> None:
    _init(tmp_path, monkeypatch, "filename-content-match")
    report = ingest.ingest_files(
        "filename-content-match",
        [
            str(
                _write(
                    tmp_path,
                    "c01.txt",
                    "第一章 雨夜\n沈砚推门。\n",
                )
            )
        ],
        material_role="CHAPTER",
    )

    assert len(report["chapters"]) == 1
    assert report["chapters"][0]["title"] == "第一章 雨夜"
    assert report["chapters"] == store.chapters("filename-content-match")


@pytest.mark.parametrize(
    "members",
    [
        {},
        {"__MACOSX/._book.txt": b"metadata", ".DS_Store": b"metadata"},
    ],
)
def test_entry_14_zip_without_terminal_material_blocks_instead_of_succeeding(
    tmp_path, monkeypatch, members: dict[str, bytes]
) -> None:
    _init(tmp_path, monkeypatch, "zip-empty")
    path = _write(tmp_path, "empty.zip", _zip(members))

    with pytest.raises(input_router.InputRoutingBlocked) as caught:
        ingest.ingest_files("zip-empty", [str(path)], material_role="CHAPTER")

    assert caught.value.receipt["blocks"][0]["type"] == "no_terminal_source"
    assert store.intake_sources("zip-empty") == []
    assert store.intake_material_units("zip-empty") == []
    assert store.chapters("zip-empty") == []
