from __future__ import annotations

import inspect
import io
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp/upload_inspect_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import upload_inspect_tool
    from mvp.upload_source import UploadSource
finally:
    sys.path.pop(0)


TEXT = "第一章\n甲推开门。\n"


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _docx(text: str) -> bytes:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
        "</w:document>"
    ).encode()
    return _zip(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": document,
        }
    )


def _symlink_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("link.txt")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b"target.txt")
    return buffer.getvalue()


def _crc_broken_zip() -> bytes:
    marker = b"SYNTHETIC-ZIP-CONTENT"
    payload = bytearray(_zip({"chapter.txt": marker}))
    offset = payload.index(marker)
    payload[offset] ^= 0x01
    return bytes(payload)


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _assert_safe_result(result: dict, raw_text: str = TEXT) -> None:
    serialized = _json_text(result)
    assert raw_text not in serialized

    forbidden_keys = {
        "raw_bytes",
        "raw_bytes_hex",
        "original_bytes_base64",
        "decoded_text",
        "declarations",
    }

    def walk(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result)


@pytest.mark.parametrize(
    ("name", "payload", "root_format", "terminal_format"),
    [
        ("chapter.txt", TEXT.encode(), "txt", "txt"),
        ("chapter.md", TEXT.encode("gb18030"), "md", "md"),
        ("chapter.docx", _docx(TEXT), "docx", "docx_main_flow_text"),
        ("book.zip", _zip({"chapter-01.txt": TEXT.encode()}), "zip", "txt"),
    ],
)
def test_four_supported_formats_return_safe_inspection_without_truth_writes(
    name: str,
    payload: bytes,
    root_format: str,
    terminal_format: str,
) -> None:
    result = upload_inspect_tool.execute([UploadSource(name, payload)])

    assert result["status"] == "READY"
    assert result["uploads"][0]["source_name"] == name
    assert result["uploads"][0]["format"] == root_format
    assert result["terminal_materials"][0]["format"] == terminal_format
    assert result["terminal_materials"][0]["source_chain"][0] == name
    assert result["terminal_source_count"] == 1
    assert result["blocks"] == []
    assert result["api_calls"] == 0
    assert result["model_calls"] == 0
    assert result["automatic_retries"] == 0
    _assert_safe_result(result)


@pytest.mark.parametrize(
    ("name", "payload", "root_format", "terminal_name", "terminal_format"),
    [
        ("chapter.txt", TEXT.encode(), "txt", "chapter.txt", "txt"),
        ("chapter.md", TEXT.encode("gb18030"), "md", "chapter.md", "md"),
        (
            "chapter.docx",
            _docx(TEXT),
            "docx",
            "chapter.docx#word/document.xml",
            "docx_main_flow_text",
        ),
        (
            "book.zip",
            _zip({"chapter-01.txt": TEXT.encode()}),
            "zip",
            "book.zip/chapter-01.txt",
            "txt",
        ),
    ],
)
def test_render_shows_safe_author_readable_summary_for_all_supported_formats(
    name: str,
    payload: bytes,
    root_format: str,
    terminal_name: str,
    terminal_format: str,
) -> None:
    upload = UploadSource(
        name,
        payload,
        declarations=[{"author_note": f"DO-NOT-RENDER:{TEXT}"}],
    )

    rendered = upload_inspect_tool.render_inspection([upload])

    assert "检查状态：✅ READY" in rendered
    assert "原上传数：1" in rendered
    assert "终端材料数：1" in rendered
    assert "可以继续导入：是" in rendered
    assert name in rendered
    assert terminal_name in rendered
    assert f"格式：{root_format}" in rendered
    assert f"格式：{terminal_format}" in rendered
    assert f"大小：{len(payload)} bytes" in rendered
    assert upload.sha256 in rendered
    assert "编码：" in rendered
    assert "来源链：" in rendered
    assert "这只是导入前检查，尚未创建项目/C10/C1/工作区状态" in rendered
    assert TEXT not in rendered
    assert "DO-NOT-RENDER" not in rendered
    assert "raw_bytes" not in rendered
    assert "base64" not in rendered
    assert "decoded_text" not in rendered
    assert "declarations" not in rendered


def test_zip_known_junk_is_visible_but_does_not_hide_valid_terminal() -> None:
    payload = _zip(
        {
            "__MACOSX/.DS_Store": b"junk",
            "chapter-02.txt": TEXT.encode(),
        }
    )

    result = upload_inspect_tool.execute([UploadSource("book.zip", payload)])

    assert result["status"] == "READY"
    assert result["terminal_source_count"] == 1
    assert result["discarded"] == [
        {
            "source_name": "book.zip/__MACOSX/.DS_Store",
            "reason": "known_archive_junk",
        }
    ]
    _assert_safe_result(result)

    rendered = upload_inspect_tool.render_inspection(
        [UploadSource("book.zip", payload)]
    )
    assert "检查状态：✅ READY" in rendered
    assert "book.zip/__MACOSX/.DS_Store：known_archive_junk" in rendered
    assert "book.zip → chapter-02.txt" in rendered
    assert "第 2 章（只来自文件名提示）" in rendered


def test_batch_lists_every_original_upload_and_terminal_in_input_order() -> None:
    uploads = [
        UploadSource("第3章.txt", TEXT.encode()),
        UploadSource(
            "bundle.zip",
            _zip({"chapter-04.md": TEXT.encode()}),
        ),
    ]

    result = upload_inspect_tool.execute(uploads)

    assert [item["source_name"] for item in result["uploads"]] == [
        "第3章.txt",
        "bundle.zip",
    ]
    assert [item["position"] for item in result["uploads"]] == [1, 2]
    assert [item["chapter_no_hint"] for item in result["terminal_materials"]] == [
        3,
        4,
    ]
    assert result["terminal_source_count"] == 2
    _assert_safe_result(result)


@pytest.mark.parametrize(
    ("name", "payload", "block_type"),
    [
        ("traversal.zip", _zip({"../escape.txt": TEXT.encode()}), "unsafe_archive_path"),
        ("symlink.zip", _symlink_zip(), "archive_symlink"),
        ("corrupted.zip", _crc_broken_zip(), "zip_crc_error"),
        ("broken.zip", b"not-a-zip", "invalid_container"),
        ("unknown.bin", b"opaque", "unsupported_format"),
    ],
)
def test_zip_and_unknown_format_failures_use_current_router_blocks(
    name: str,
    payload: bytes,
    block_type: str,
) -> None:
    result = upload_inspect_tool.execute([UploadSource(name, payload)])

    assert result["status"] == "BLOCKED"
    assert any(block["type"] == block_type for block in result["blocks"])
    assert result["terminal_source_count"] == 0
    _assert_safe_result(result)

    rendered = upload_inspect_tool.render_inspection([UploadSource(name, payload)])
    assert "检查状态：❌ BLOCKED" in rendered
    assert "可以继续导入：否" in rendered
    assert "没有可继续导入的终端材料" in rendered
    assert f"[{block_type}]" in rendered
    assert "检查状态：✅ READY" not in rendered


def test_unknown_filename_hint_stays_unknown_instead_of_guessing_identity() -> None:
    rendered = upload_inspect_tool.render_inspection(
        [UploadSource("notes.txt", TEXT.encode())]
    )

    assert "文件名章号提示：未识别（工具不会猜材料身份）" in rendered
    assert "设定" not in rendered


def test_stdin_transport_matches_object_core_and_stdout_is_stable() -> None:
    upload = UploadSource("chapter.txt", TEXT.encode())
    request = {
        "uploads": [
            {
                "source_name": upload.source_name,
                "raw_bytes_hex": upload.raw_bytes.hex(),
                "declarations": None,
                "encoding_hint": None,
            }
        ]
    }
    stdout = io.StringIO()

    code = upload_inspect_tool.main(
        ["--output", "-"],
        stdin=io.StringIO(json.dumps(request)),
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    expected = upload_inspect_tool.execute([upload])
    assert stdout.getvalue().encode("utf-8") == upload_inspect_tool._output_bytes(
        expected
    )
    assert json.loads(stdout.getvalue()) == expected
    _assert_safe_result(json.loads(stdout.getvalue()))


def test_render_stdin_stdout_must_start_from_original_upload_request() -> None:
    upload = UploadSource("chapter.txt", TEXT.encode())
    request = {
        "uploads": [
            {
                "source_name": upload.source_name,
                "raw_bytes_hex": upload.raw_bytes.hex(),
            }
        ]
    }
    stdout = io.StringIO()

    code = upload_inspect_tool.main(
        ["--render", "--output", "-"],
        stdin=io.StringIO(json.dumps(request)),
        stdout=stdout,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == upload_inspect_tool.render_inspection([upload])
    assert TEXT not in stdout.getvalue()


def test_local_file_cli_never_exposes_absolute_path_or_source_text(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "chapter.txt"
    output_path = tmp_path / "inspection.json"
    input_path.write_text(TEXT, encoding="utf-8")

    code = upload_inspect_tool.main(
        ["--file", str(input_path), "--output", str(output_path)],
        stderr=io.StringIO(),
    )
    result = json.loads(output_path.read_text(encoding="utf-8"))

    assert code == 0
    assert str(tmp_path) not in _json_text(result)
    assert result["uploads"][0]["source_name"] == "chapter.txt"
    assert {path.name for path in tmp_path.iterdir()} == {
        "chapter.txt",
        "inspection.json",
    }
    _assert_safe_result(result)


@pytest.mark.parametrize("alias_kind", ["exact", "symlink", "hardlink"])
def test_output_cannot_replace_any_local_input_alias(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    input_path = tmp_path / "chapter.txt"
    input_path.write_text(TEXT, encoding="utf-8")
    if alias_kind == "exact":
        output_path = input_path
    else:
        output_path = tmp_path / f"chapter-{alias_kind}.txt"
        if alias_kind == "symlink":
            output_path.symlink_to(input_path)
        else:
            output_path.hardlink_to(input_path)
    before = input_path.read_bytes()
    stderr = io.StringIO()

    code = upload_inspect_tool.main(
        ["--file", str(input_path), "--output", str(output_path)],
        stderr=stderr,
    )

    assert code == 2
    assert "OUTPUT_PATH_MUST_DIFFER_FROM_INPUTS" in stderr.getvalue()
    assert input_path.read_bytes() == before
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".*.tmp"))


def test_relative_input_and_absolute_output_alias_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "chapter.txt"
    input_path.write_text(TEXT, encoding="utf-8")
    before = input_path.read_bytes()
    monkeypatch.chdir(tmp_path)
    stderr = io.StringIO()

    code = upload_inspect_tool.main(
        ["--file", "chapter.txt", "--output", str(input_path)],
        stderr=stderr,
    )

    assert code == 2
    assert "OUTPUT_PATH_MUST_DIFFER_FROM_INPUTS" in stderr.getvalue()
    assert input_path.read_bytes() == before
    assert not list(tmp_path.glob(".*.tmp"))


def test_invalid_stdin_does_not_replace_existing_output(tmp_path: Path) -> None:
    output_path = tmp_path / "inspection.json"
    output_path.write_bytes(b"old-inspection\n")

    code = upload_inspect_tool.main(
        ["--output", str(output_path)],
        stdin=io.StringIO("{bad-json"),
        stderr=io.StringIO(),
    )

    assert code == 2
    assert output_path.read_bytes() == b"old-inspection\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_same_local_input_is_byte_stable_across_processes(tmp_path: Path) -> None:
    input_path = tmp_path / "chapter.txt"
    first_output = tmp_path / "inspection-1.json"
    second_output = tmp_path / "inspection-2.json"
    input_path.write_text(TEXT, encoding="utf-8")
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    for output_path in (first_output, second_output):
        completed = subprocess.run(
            [
                sys.executable,
                str(TOOL_PATH),
                "--file",
                str(input_path),
                "--output",
                str(output_path),
            ],
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    assert first_output.read_bytes() == second_output.read_bytes()
    assert json.loads(first_output.read_text(encoding="utf-8"))["status"] == "READY"


def test_render_local_file_is_safe_and_byte_stable_across_processes(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "chapter-08.txt"
    first_output = tmp_path / "inspection-1.md"
    second_output = tmp_path / "inspection-2.md"
    input_path.write_text(TEXT, encoding="utf-8")
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    for output_path in (first_output, second_output):
        completed = subprocess.run(
            [
                sys.executable,
                str(TOOL_PATH),
                "--render",
                "--file",
                str(input_path),
                "--output",
                str(output_path),
            ],
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    assert first_output.read_bytes() == second_output.read_bytes()
    rendered = first_output.read_text(encoding="utf-8")
    assert str(tmp_path) not in rendered
    assert TEXT not in rendered
    assert "第 8 章（只来自文件名提示）" in rendered


def test_render_failure_preserves_existing_output_and_removes_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "inspection.md"
    output_path.write_bytes(b"old-render\n")

    def fail_replace(source: str, destination: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(upload_inspect_tool.os, "replace", fail_replace)

    with pytest.raises(OSError, match="synthetic replace failure"):
        upload_inspect_tool._write_text_atomic(output_path, "new-render\n")

    assert output_path.read_bytes() == b"old-render\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_render_output_cannot_replace_local_input(tmp_path: Path) -> None:
    input_path = tmp_path / "chapter.txt"
    input_path.write_text(TEXT, encoding="utf-8")
    before = input_path.read_bytes()
    stderr = io.StringIO()

    code = upload_inspect_tool.main(
        ["--render", "--file", str(input_path), "--output", str(input_path)],
        stderr=stderr,
    )

    assert code == 2
    assert "OUTPUT_PATH_MUST_DIFFER_FROM_INPUTS" in stderr.getvalue()
    assert input_path.read_bytes() == before
    assert not list(tmp_path.glob(".*.tmp"))


def test_object_core_accepts_only_upload_sources_and_has_no_path_or_project() -> None:
    assert list(inspect.signature(upload_inspect_tool.execute).parameters) == [
        "uploads"
    ]
    with pytest.raises(
        upload_inspect_tool.UploadInspectToolError,
        match="UPLOAD_SOURCE_BATCH_INVALID",
    ):
        upload_inspect_tool.execute([Path("chapter.txt")])  # type: ignore[list-item]
    assert not hasattr(upload_inspect_tool, "create_project")
    assert not hasattr(upload_inspect_tool, "persist")
