"""T03-A 本地格式入口：文件／ZIP → 可交给 C10-first 的严格文本 sources。

这里只做格式、容器、解码和来源链机械处理，不猜材料 role，不写 C1，不调模型。
"""

from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree


IDENTITY = "NOVEL_MVP_C10_FIRST_INPUT_ROUTER_R01"
LIMITS = {
    "max_archive_layers": 2,
    "max_files": 200,
    "max_total_uncompressed_bytes": 32 * 1024 * 1024,
    "max_single_file_bytes": 8 * 1024 * 1024,
}
_JUNK_NAMES = {".ds_store", "thumbs.db"}
_CHINESE_NUMBER = re.compile(r"第(?P<value>[零〇一二三四五六七八九十百千万两0-9]+)章")
_LATIN_NUMBER = re.compile(
    r"(?:chapter|chap|ch|c)[-_ ]*0*(?P<value>[0-9]+)|^0*(?P<plain>[0-9]+)(?:\D|$)",
    re.IGNORECASE,
)
_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}


class InputRoutingBlocked(SystemExit):
    """格式或容器不能无损转换为 C10 source；调用方必须整批停止。"""

    def __init__(self, receipt: dict[str, Any]):
        self.receipt = receipt
        detail = receipt["blocks"][0]["detail"] if receipt["blocks"] else "未知入口错误"
        super().__init__(f"导入强停：{detail}")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256(value.encode("utf-8"))


def _chapter_number(value: str) -> int:
    if value.isascii() and value.isdigit():
        return int(value)
    total = 0
    section = 0
    digit = 0
    for char in value:
        if char in _DIGITS:
            digit = _DIGITS[char]
        elif char in _SMALL_UNITS:
            section += (digit or 1) * _SMALL_UNITS[char]
            digit = 0
        elif char == "万":
            total += (section + digit or 1) * 10_000
            section = 0
            digit = 0
        else:
            raise ValueError(f"不支持的中文章号：{value}")
    return total + section + digit


def filename_chapter_no(name: str) -> int | None:
    """文件名只辅助已明确 Chapter 的跨文件章序，不授予材料身份。"""
    stem = Path(name.split("#", 1)[0]).stem
    match = _CHINESE_NUMBER.search(stem)
    if match:
        return _chapter_number(match.group("value"))
    match = _LATIN_NUMBER.search(stem)
    if match:
        return int(match.group("value") or match.group("plain"))
    return None


def _decode_text(payload: bytes) -> tuple[str, str]:
    attempts = ["utf-16"] if payload.startswith((b"\xff\xfe", b"\xfe\xff")) else []
    attempts.extend(["utf-8-sig", "gb18030"])
    errors: list[str] = []
    for encoding in attempts:
        try:
            text = payload.decode(encoding, errors="strict")
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
            continue
        controls = sum(1 for char in text if ord(char) < 32 and char not in "\r\n\t")
        if controls >= 3 or any(token in text for token in ("锟斤拷", "烫烫烫", "屯屯屯")):
            errors.append(f"{encoding}: 解码后仍有明显乱码或异常控制字符")
            continue
        return text, encoding
    raise ValueError("；".join(errors) or "严格解码失败")


def _safe_zip_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not path.is_absolute() and ".." not in path.parts and "\x00" not in normalized


def _format(name: str, payload: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if zipfile.is_zipfile(io.BytesIO(payload)):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                return "docx" if "word/document.xml" in archive.namelist() else "zip"
        except zipfile.BadZipFile:
            return "invalid_container"
    if suffix in {".zip", ".docx"}:
        return "invalid_container"
    return {".txt": "txt", ".md": "md", ".doc": "doc"}.get(suffix, "unsupported")


def _docx_main_flow(payload: bytes) -> tuple[str, list[str]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
        if "word/document.xml" not in names:
            raise ValueError("DOCX 缺少 word/document.xml")
        unparsed = [
            name
            for name in names
            if name.startswith(
                (
                    "word/header",
                    "word/footer",
                    "word/comments",
                    "word/footnotes",
                    "word/endnotes",
                )
            )
            and name.endswith(".xml")
        ]
        xml_payload = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_payload)
    unsupported_tags = ("}txbxContent", "}del", "}altChunk")
    unsupported = sorted(
        {tag for node in root.iter() for tag in unsupported_tags if node.tag.endswith(tag)}
    )
    unparsed.extend(unsupported)

    def inline_text(node: ElementTree.Element) -> str:
        if node.tag.endswith(("}txbxContent", "}del", "}altChunk")):
            return ""
        if node.tag.endswith("}t"):
            return node.text or ""
        if node.tag.endswith("}tab"):
            return "\t"
        if node.tag.endswith("}br"):
            return "\n"
        return "".join(inline_text(child) for child in node)

    paragraphs: list[str] = []

    def walk(node: ElementTree.Element) -> None:
        if node.tag.endswith(("}txbxContent", "}del", "}altChunk")):
            return
        if node.tag.endswith("}p"):
            paragraphs.append(inline_text(node))
            return
        for child in node:
            walk(child)

    walk(root)
    return "\n".join(paragraphs), unparsed


class _Collector:
    def __init__(self, limits: dict[str, int] | None):
        self.limits = {**LIMITS, **(limits or {})}
        self.items: list[dict[str, Any]] = []
        self.sources: list[dict[str, Any]] = []
        self.blocks: list[dict[str, str]] = []
        self.warnings: list[str] = []
        self.discarded: list[dict[str, str]] = []
        self._file_count = 0
        self._total_uncompressed = 0
        self._terminal_names: set[str] = set()

    def _block(self, block_type: str, source_name: str, detail: str) -> None:
        self.blocks.append({"type": block_type, "source_name": source_name, "detail": detail})

    def _source_receipt(
        self,
        name: str,
        payload: bytes,
        format_name: str,
        chain: list[str],
    ) -> dict[str, Any]:
        receipt = {
            "source_name": name,
            "format": format_name,
            "source_sha256": _sha256(payload),
            "bytes": len(payload),
            "source_chain": chain,
        }
        self.sources.append(receipt)
        return receipt

    def _terminal(
        self,
        source_name: str,
        raw_bytes: bytes,
        encoding: str,
        format_name: str,
        receipt: dict[str, Any],
    ) -> None:
        if source_name in self._terminal_names:
            self._block("duplicate_source_name", source_name, "同批解包后出现重复 source_name")
            return
        self._terminal_names.add(source_name)
        decoded = raw_bytes.decode(encoding, errors="strict")
        receipt.update(
            {
                "state": "decoded",
                "encoding": encoding,
                "decoded_chars": len(decoded),
                "decoded_text_sha256": _sha256_text(decoded),
            }
        )
        self.items.append(
            {
                "source_name": source_name,
                "raw_bytes": raw_bytes,
                "encoding": encoding,
                "format": format_name,
                "chapter_no_hint": filename_chapter_no(source_name),
            }
        )

    def _text(self, name: str, payload: bytes, format_name: str, chain: list[str]) -> None:
        receipt = self._source_receipt(name, payload, format_name, chain)
        try:
            text, encoding = _decode_text(payload)
        except ValueError as exc:
            receipt["state"] = "blocked"
            self._block("decode_error", name, str(exc))
            return
        if not text:
            receipt["state"] = "blocked"
            self._block("empty_document", name, "解码后为空，不能建立非空 C10 material span")
            return
        self._terminal(name, payload, encoding, format_name, receipt)

    def _docx(self, name: str, payload: bytes, chain: list[str]) -> None:
        receipt = self._source_receipt(name, payload, "docx", chain)
        try:
            text, unparsed = _docx_main_flow(payload)
        except (ElementTree.ParseError, KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
            receipt["state"] = "blocked"
            self._block("docx_decode_error", name, f"DOCX 主文档流读取失败：{exc}")
            return
        if unparsed:
            receipt["state"] = "blocked"
            receipt["unparsed_areas"] = unparsed
            self._block("unparsed_docx_area", name, f"DOCX 有未覆盖区域：{unparsed}")
            return
        if not text:
            receipt["state"] = "blocked"
            self._block("empty_document", name, "DOCX 主文档流为空")
            return
        derived = text.encode("utf-8")
        derived_name = f"{name}#word/document.xml"
        receipt.update(
            {
                "state": "decoded_to_derived_source",
                "derived_source_name": derived_name,
                "derived_source_sha256": _sha256(derived),
                "decoded_chars": len(text),
            }
        )
        derived_receipt = {
            "source_name": derived_name,
            "format": "docx_main_flow_text",
            "source_sha256": _sha256(derived),
            "bytes": len(derived),
            "source_chain": [*chain, "word/document.xml"],
            "derived_from_sha256": receipt["source_sha256"],
        }
        self.sources.append(derived_receipt)
        self._terminal(derived_name, derived, "utf-8", "docx_main_flow_text", derived_receipt)

    def _zip(self, name: str, payload: bytes, chain: list[str], layer: int) -> None:
        receipt = self._source_receipt(name, payload, "zip", chain)
        if layer > self.limits["max_archive_layers"]:
            receipt["state"] = "blocked"
            self._block("nested_archive_too_deep", name, "ZIP 嵌套超过两层保守上限")
            return
        receipt["state"] = "container"
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as exc:
            self._block("invalid_container", name, f"ZIP 中央目录不可读：{exc}")
            return
        terminal_count_before = len(self.items)
        block_count_before = len(self.blocks)
        seen_names: set[str] = set()
        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                normalized = info.filename.replace("\\", "/")
                if not _safe_zip_name(normalized):
                    self._block("unsafe_archive_path", name, f"拒绝成员路径：{info.filename}")
                    continue
                mode = info.external_attr >> 16
                if mode and stat.S_ISLNK(mode):
                    self._block("archive_symlink", name, f"拒绝符号链接成员：{info.filename}")
                    continue
                lower = normalized.lower()
                basename = PurePosixPath(normalized).name
                if lower.startswith("__macosx/") or basename.lower() in _JUNK_NAMES:
                    self.discarded.append(
                        {"source_name": f"{name}/{normalized}", "reason": "known_archive_junk"}
                    )
                    continue
                if normalized in seen_names:
                    self._block("duplicate_archive_member", name, f"重复成员名：{normalized}")
                    continue
                seen_names.add(normalized)
                self._file_count += 1
                self._total_uncompressed += info.file_size
                if self._file_count > self.limits["max_files"]:
                    self._block("archive_file_limit", name, "ZIP 文件数超过保守上限")
                    return
                if info.file_size > self.limits["max_single_file_bytes"]:
                    self._block("archive_member_too_large", name, f"成员过大：{normalized}")
                    continue
                if self._total_uncompressed > self.limits["max_total_uncompressed_bytes"]:
                    self._block("archive_total_size_limit", name, "ZIP 解压总量超过保守上限")
                    return
                try:
                    member_payload = archive.read(info)
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    self._block("zip_crc_error", name, f"成员读取失败：{normalized}；{exc}")
                    continue
                member_name = f"{name}/{normalized}"
                self.process(member_name, member_payload, [*chain, normalized], layer)
        if len(self.items) == terminal_count_before and len(self.blocks) == block_count_before:
            receipt["state"] = "blocked"
            self._block("no_terminal_source", name, "ZIP 中没有可导入的 TXT／MD／DOCX 材料")

    def process(self, name: str, payload: bytes, chain: list[str], archive_layer: int) -> None:
        format_name = _format(name, payload)
        if format_name in {"txt", "md"}:
            self._text(name, payload, format_name, chain)
        elif format_name == "docx":
            self._docx(name, payload, chain)
        elif format_name == "zip":
            self._zip(name, payload, chain, archive_layer + 1)
        elif format_name == "doc":
            self._source_receipt(name, payload, format_name, chain)["state"] = "blocked"
            self._block("unsupported_doc", name, "旧 DOC 暂不支持，请另存为 DOCX")
        elif format_name == "invalid_container":
            self._source_receipt(name, payload, format_name, chain)["state"] = "blocked"
            self._block("invalid_container", name, "ZIP／DOCX 文件头或中央目录不可读")
        else:
            self._source_receipt(name, payload, format_name, chain)["state"] = "blocked"
            self._block("unsupported_format", name, "只支持 TXT／MD／DOCX／ZIP")

    def receipt(self) -> dict[str, Any]:
        return {
            "identity": IDENTITY,
            "status": "BLOCKED" if self.blocks else "READY",
            "sources": self.sources,
            "terminal_source_count": len(self.items),
            "blocks": self.blocks,
            "warnings": self.warnings,
            "discarded": self.discarded,
            "api_calls": 0,
            "automatic_retries": 0,
        }


def collect_paths(
    paths: list[str],
    *,
    limits: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """读取所有输入；任一格式错误只返回 BLOCKED，调用方不得落半套账。"""
    if not isinstance(paths, list) or not paths:
        raise ValueError("导入至少需要一个文件")
    collector = _Collector(limits)
    root_names: set[str] = set()
    for value in paths:
        path = Path(value)
        if not path.is_file():
            collector._block("missing_input", str(path), "文件不存在或不是普通文件")
            continue
        name = path.name
        if name in root_names:
            collector._block("duplicate_root_name", name, "同批根文件名重复")
            continue
        root_names.add(name)
        try:
            input_bytes = path.stat().st_size
        except OSError as exc:
            collector._block("input_read_error", name, f"无法读取文件属性：{exc}")
            continue
        if input_bytes > collector.limits["max_single_file_bytes"]:
            collector._block("input_file_too_large", name, "根文件超过保守单文件大小上限")
            continue
        try:
            payload = path.read_bytes()
        except OSError as exc:
            collector._block("input_read_error", name, f"无法读取文件：{exc}")
            continue
        collector.process(name, payload, [name], 0)
    receipt = collector.receipt()
    return collector.items, receipt
