"""M1 上传安全体检工具。

对象核心只接 ``UploadSource`` 列表，复用现役 ``collect_uploads``
检查 TXT／MD／DOCX／ZIP。它不建项目、不写 C10／C1，也不判断材料身份。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, TextIO

if __package__:
    from . import input_router
    from .upload_source import UploadSource
else:  # 允许本地直接运行该文件。
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from mvp import input_router  # type: ignore[no-redef]
    from mvp.upload_source import UploadSource  # type: ignore[no-redef]


IDENTITY = "M1_UPLOAD_INSPECTION_R01"
LOCAL_FILESYSTEM_ONLY = "LOCAL_FILESYSTEM_ONLY"
REQUEST_KEYS = {"uploads"}
UPLOAD_REQUIRED_KEYS = {"source_name", "raw_bytes_hex"}
UPLOAD_OPTIONAL_KEYS = {"declarations", "encoding_hint"}
HEX_RE = re.compile(r"[0-9a-f]*\Z")


class UploadInspectToolError(ValueError):
    """上传体检还没得到完整、可安全展示的结果。"""


def _root_source_receipts(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    sources = receipt.get("sources")
    if not isinstance(sources, list):
        raise UploadInspectToolError("ROUTER_SOURCES_INVALID")
    for source in sources:
        if not isinstance(source, dict):
            raise UploadInspectToolError("ROUTER_SOURCE_INVALID")
        name = source.get("source_name")
        chain = source.get("source_chain")
        if isinstance(name, str) and chain == [name] and name not in indexed:
            indexed[name] = source
    return indexed


def _source_receipts(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    sources = receipt.get("sources")
    if not isinstance(sources, list):
        raise UploadInspectToolError("ROUTER_SOURCES_INVALID")
    for source in sources:
        if not isinstance(source, dict) or not isinstance(
            source.get("source_name"), str
        ):
            raise UploadInspectToolError("ROUTER_SOURCE_INVALID")
        name = source["source_name"]
        if name in indexed:
            raise UploadInspectToolError("ROUTER_SOURCE_NAME_DUPLICATE")
        indexed[name] = source
    return indexed


def _upload_summaries(
    uploads: list[UploadSource],
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    roots = _root_source_receipts(receipt)
    seen: set[str] = set()
    summaries: list[dict[str, Any]] = []
    for position, upload in enumerate(uploads, start=1):
        source = None if upload.source_name in seen else roots.get(upload.source_name)
        seen.add(upload.source_name)
        summaries.append(
            {
                "position": position,
                "source_name": upload.source_name,
                "format": source.get("format") if source is not None else None,
                "encoding": source.get("encoding") if source is not None else None,
                "state": source.get("state") if source is not None else "blocked",
                "bytes": len(upload.raw_bytes),
                "source_sha256": upload.sha256,
                "source_chain": (
                    copy.deepcopy(source.get("source_chain"))
                    if source is not None
                    else [upload.source_name]
                ),
                "chapter_no_hint": input_router.filename_chapter_no(
                    upload.source_name
                ),
            }
        )
    return summaries


def _terminal_summaries(
    items: list[dict[str, Any]],
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    sources = _source_receipts(receipt)
    summaries: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise UploadInspectToolError("ROUTER_TERMINAL_ITEM_INVALID")
        name = item.get("source_name")
        source = sources.get(name) if isinstance(name, str) else None
        if source is None:
            raise UploadInspectToolError("TERMINAL_SOURCE_RECEIPT_MISSING")
        summaries.append(
            {
                "source_name": name,
                "format": item.get("format"),
                "encoding": item.get("encoding"),
                "state": source.get("state"),
                "bytes": source.get("bytes"),
                "source_sha256": source.get("source_sha256"),
                "source_chain": copy.deepcopy(source.get("source_chain")),
                "chapter_no_hint": item.get("chapter_no_hint"),
                "decoded_chars": source.get("decoded_chars"),
                "decoded_text_sha256": source.get("decoded_text_sha256"),
                "derived_from_sha256": source.get("derived_from_sha256"),
            }
        )
    return summaries


def execute(uploads: list[UploadSource]) -> dict[str, Any]:
    """检查一批内存上传对象，只返回不含正文的安全摘要。"""
    if not isinstance(uploads, list) or not uploads:
        raise UploadInspectToolError("UPLOAD_SOURCE_BATCH_REQUIRED")
    if any(not isinstance(upload, UploadSource) for upload in uploads):
        raise UploadInspectToolError("UPLOAD_SOURCE_BATCH_INVALID")
    try:
        items, receipt = input_router.collect_uploads(uploads)
    except (TypeError, ValueError) as exc:
        raise UploadInspectToolError(f"UPLOAD_ROUTING_REJECTED:{exc}") from exc

    required_receipt_keys = {
        "status",
        "terminal_source_count",
        "blocks",
        "warnings",
        "discarded",
        "api_calls",
        "automatic_retries",
    }
    if not isinstance(receipt, dict) or not required_receipt_keys <= receipt.keys():
        raise UploadInspectToolError("ROUTER_RECEIPT_INVALID")
    return {
        "identity": IDENTITY,
        "status": receipt["status"],
        "uploads": _upload_summaries(uploads, receipt),
        "terminal_materials": _terminal_summaries(items, receipt),
        "terminal_source_count": receipt["terminal_source_count"],
        "warnings": copy.deepcopy(receipt["warnings"]),
        "blocks": copy.deepcopy(receipt["blocks"]),
        "discarded": copy.deepcopy(receipt["discarded"]),
        "api_calls": receipt["api_calls"],
        "model_calls": 0,
        "automatic_retries": receipt["automatic_retries"],
    }


def _render_value(value: object, *, unknown: str = "未识别") -> str:
    if value is None:
        return unknown
    if isinstance(value, str):
        return value.replace("\r", "\\r").replace("\n", "\\n")
    return str(value)


def _render_chapter_hint(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return f"第 {value} 章（只来自文件名提示）"
    return "未识别（工具不会猜材料身份）"


def _render_chain(value: object) -> str:
    if not isinstance(value, list) or not value:
        raise UploadInspectToolError("RENDER_SOURCE_CHAIN_INVALID")
    if any(not isinstance(item, str) or not item for item in value):
        raise UploadInspectToolError("RENDER_SOURCE_CHAIN_INVALID")
    return " → ".join(_render_value(item) for item in value)


def render_inspection(uploads: list[UploadSource]) -> str:
    """从原 UploadSource 重新执行检查，再生成不含正文的人读结果。"""
    result = execute(uploads)
    status = result.get("status")
    if status not in {"READY", "BLOCKED"}:
        raise UploadInspectToolError("RENDER_STATUS_INVALID")
    original_uploads = result.get("uploads")
    terminal_materials = result.get("terminal_materials")
    if not isinstance(original_uploads, list) or not isinstance(
        terminal_materials, list
    ):
        raise UploadInspectToolError("RENDER_MATERIALS_INVALID")
    if result.get("terminal_source_count") != len(terminal_materials):
        raise UploadInspectToolError("RENDER_TERMINAL_COUNT_MISMATCH")

    ready = status == "READY"
    lines = [
        "# M1 上传前检查",
        "",
        f"- 检查状态：{'✅ READY' if ready else '❌ BLOCKED'}",
        f"- 原上传数：{len(original_uploads)}",
        f"- 终端材料数：{len(terminal_materials)}",
        f"- 可以继续导入：{'是' if ready else '否'}",
        "",
        "> 这只是导入前检查，尚未创建项目/C10/C1/工作区状态。",
        "",
        "## 原上传",
    ]
    for position, upload in enumerate(original_uploads, start=1):
        if not isinstance(upload, dict):
            raise UploadInspectToolError("RENDER_UPLOAD_INVALID")
        reported_position = upload.get("position")
        if reported_position != position:
            raise UploadInspectToolError("RENDER_UPLOAD_ORDER_INVALID")
        lines.extend(
            [
                "",
                f"### {position}. {_render_value(upload.get('source_name'))}",
                f"- 格式：{_render_value(upload.get('format'), unknown='UNKNOWN（不猜）')}",
                f"- 大小：{_render_value(upload.get('bytes'))} bytes",
                f"- SHA256：{_render_value(upload.get('source_sha256'))}",
                f"- 编码：{_render_value(upload.get('encoding'))}",
                f"- 路由状态：{_render_value(upload.get('state'))}",
                f"- 文件名章号提示：{_render_chapter_hint(upload.get('chapter_no_hint'))}",
            ]
        )

    lines.extend(["", "## 拆分后的终端材料"])
    if not terminal_materials:
        lines.extend(["", "没有可继续导入的终端材料。"])
    for position, material in enumerate(terminal_materials, start=1):
        if not isinstance(material, dict):
            raise UploadInspectToolError("RENDER_TERMINAL_INVALID")
        lines.extend(
            [
                "",
                f"### {position}. {_render_value(material.get('source_name'))}",
                f"- 格式：{_render_value(material.get('format'), unknown='UNKNOWN（不猜）')}",
                f"- 大小：{_render_value(material.get('bytes'))} bytes",
                f"- SHA256：{_render_value(material.get('source_sha256'))}",
                f"- 编码：{_render_value(material.get('encoding'))}",
                f"- 路由状态：{_render_value(material.get('state'))}",
                f"- 来源链：{_render_chain(material.get('source_chain'))}",
                (
                    "- 文件名章号提示："
                    f"{_render_chapter_hint(material.get('chapter_no_hint'))}"
                ),
            ]
        )

    sections = [
        ("警告", result.get("warnings"), "没有警告。"),
        ("丢弃项", result.get("discarded"), "没有丢弃项。"),
        ("阻断原因", result.get("blocks"), "没有阻断原因。"),
    ]
    for title, entries, empty_text in sections:
        if not isinstance(entries, list):
            raise UploadInspectToolError(f"RENDER_{title}_INVALID")
        lines.extend(["", f"## {title}"])
        if not entries:
            lines.extend(["", empty_text])
            continue
        for entry in entries:
            if isinstance(entry, str):
                rendered = _render_value(entry)
            elif isinstance(entry, dict):
                if title == "丢弃项":
                    rendered = (
                        f"{_render_value(entry.get('source_name'))}："
                        f"{_render_value(entry.get('reason'))}"
                    )
                else:
                    rendered = (
                        f"[{_render_value(entry.get('type'))}] "
                        f"{_render_value(entry.get('source_name'))}："
                        f"{_render_value(entry.get('detail'))}"
                    )
            else:
                raise UploadInspectToolError(f"RENDER_{title}_INVALID")
            lines.append(f"- {rendered}")

    return "\n".join(lines) + "\n"


def _uploads_from_transport(value: object) -> list[UploadSource]:
    if not isinstance(value, dict) or set(value) != REQUEST_KEYS:
        raise UploadInspectToolError("TRANSPORT_REQUEST_INVALID")
    rows = value["uploads"]
    if not isinstance(rows, list) or not rows:
        raise UploadInspectToolError("TRANSPORT_UPLOADS_REQUIRED")
    uploads: list[UploadSource] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise UploadInspectToolError(f"TRANSPORT_UPLOAD_INVALID:{index}")
        missing = UPLOAD_REQUIRED_KEYS - row.keys()
        extra = row.keys() - UPLOAD_REQUIRED_KEYS - UPLOAD_OPTIONAL_KEYS
        if missing or extra:
            raise UploadInspectToolError(f"TRANSPORT_UPLOAD_INVALID:{index}")
        raw_hex = row["raw_bytes_hex"]
        if (
            not isinstance(raw_hex, str)
            or len(raw_hex) % 2 != 0
            or HEX_RE.fullmatch(raw_hex) is None
        ):
            raise UploadInspectToolError(f"TRANSPORT_RAW_BYTES_HEX_INVALID:{index}")
        try:
            uploads.append(
                UploadSource(
                    source_name=row["source_name"],
                    raw_bytes=bytes.fromhex(raw_hex),
                    declarations=copy.deepcopy(row.get("declarations")),
                    encoding_hint=row.get("encoding_hint"),
                )
            )
        except (TypeError, ValueError) as exc:
            raise UploadInspectToolError(
                f"TRANSPORT_UPLOAD_INVALID:{index}:{exc}"
            ) from exc
    return uploads


def _file_identity(
    path: Path,
    *,
    label: str,
) -> tuple[Path, os.stat_result | None]:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise UploadInspectToolError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        stat_result = None
    except OSError as exc:
        raise UploadInspectToolError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    return resolved, stat_result


def _same_file_identity(left: Path, right: Path) -> bool:
    left_resolved, left_stat = _file_identity(left, label="INPUT")
    right_resolved, right_stat = _file_identity(right, label="OUTPUT")
    return left_resolved == right_resolved or (
        left_stat is not None
        and right_stat is not None
        and os.path.samestat(left_stat, right_stat)
    )


def _validate_output_path(input_paths: list[str], output_path: str | None) -> None:
    if output_path in {None, "-"}:
        return
    output = Path(output_path)
    if any(_same_file_identity(Path(value), output) for value in input_paths):
        raise UploadInspectToolError("OUTPUT_PATH_MUST_DIFFER_FROM_INPUTS")


def _uploads_from_local_files(values: list[str]) -> list[UploadSource]:
    uploads: list[UploadSource] = []
    for value in values:
        path = Path(value)
        if not path.is_file():
            raise UploadInspectToolError(f"LOCAL_INPUT_NOT_FILE:{path.name}")
        try:
            uploads.append(UploadSource(path.name, path.read_bytes()))
        except (OSError, ValueError) as exc:
            raise UploadInspectToolError(f"LOCAL_INPUT_REJECTED:{path.name}") from exc
    return uploads


def _output_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    if not path.parent.is_dir():
        raise UploadInspectToolError("OUTPUT_PARENT_NOT_DIRECTORY")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        _fsync_directory(path.parent)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    _write_bytes_atomic(path, _output_bytes(value))


def _write_text_atomic(path: Path, value: str) -> None:
    _write_bytes_atomic(path, value.encode("utf-8"))


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="M1 上传安全体检")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="LOCAL_FILESYSTEM_ONLY：可重复指定本地上传文件",
    )
    parser.add_argument("--output", help="检查结果；省略或 - 写 stdout")
    parser.add_argument(
        "--render",
        action="store_true",
        help="从原上传执行检查后，输出作者可读 Markdown",
    )
    args = parser.parse_args(argv)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    try:
        _validate_output_path(args.file, args.output)
        if args.file:
            uploads = _uploads_from_local_files(args.file)
        else:
            try:
                request = json.load(stdin)
            except json.JSONDecodeError as exc:
                raise UploadInspectToolError(f"STDIN_JSON_INVALID:{exc}") from exc
            uploads = _uploads_from_transport(request)
        if args.render:
            rendered = render_inspection(uploads)
            if args.output in {None, "-"}:
                stdout.write(rendered)
                stdout.flush()
            else:
                _write_text_atomic(Path(args.output), rendered)
        else:
            result = execute(uploads)
            if args.output in {None, "-"}:
                stdout.write(_output_bytes(result).decode("utf-8"))
                stdout.flush()
            else:
                _write_atomic(Path(args.output), result)
    except (OSError, UploadInspectToolError) as exc:
        stderr.write(f"M1_UPLOAD_INSPECTION_REJECTED:{exc}\n")
        stderr.flush()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
