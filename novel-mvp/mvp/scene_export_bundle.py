"""M10 C8 场景卡原型的确定性无帧文本 ZIP 工具。

纯对象核心只接收现役 C8 prototype 和显式计划来源水位。
它复用现役严格校验与全卡 Markdown 渲染，不生成新场景内容。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, NoReturn
import zipfile

if __package__:
    from . import scene_export, scene_export_tool
else:  # 允许直接运行本地文件工具。
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import scene_export, scene_export_tool


BUNDLE_IDENTITY = "M10_C8_TEXT_BUNDLE_PROTOTYPE"
BUNDLE_VERSION = "v1"
MEMBER_ORDER = ("scene_cards.json", "scene_cards.md", "manifest.json")
SOURCE_IDENTITY_FIELDS = {"source_plan_version", "source_plan_sha256"}
REQUEST_FIELDS = {"c8_prototype", "source_identity"}
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = 0o100644


class SceneExportBundleError(ValueError):
    """场景卡文本包在写入前未通过闭合校验。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise SceneExportBundleError(code, detail)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _validated_source_identity(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SOURCE_IDENTITY_FIELDS:
        _fail("SOURCE_IDENTITY_INVALID")
    version = value["source_plan_version"]
    source_sha = value["source_plan_sha256"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        _fail("SOURCE_PLAN_VERSION_INVALID")
    if not _valid_sha256(source_sha):
        _fail("SOURCE_PLAN_SHA256_INVALID")
    return copy.deepcopy(value)


def _validate_embedded_source(
    prototype: dict[str, Any],
    source_identity: dict[str, Any],
) -> None:
    for field in ("workspace_basis", "workspace_binding"):
        embedded = prototype.get(field)
        if embedded is None:
            continue
        if not isinstance(embedded, dict):
            _fail("EMBEDDED_SOURCE_IDENTITY_INVALID", field)
        if (
            embedded.get("source_plan_version")
            != source_identity["source_plan_version"]
            or embedded.get("source_plan_sha256")
            != source_identity["source_plan_sha256"]
        ):
            _fail("EMBEDDED_SOURCE_IDENTITY_MISMATCH", field)


def _validated_ai_label(prototype: dict[str, Any]) -> dict[str, Any]:
    value = prototype.get("ai_label")
    if (
        not isinstance(value, dict)
        or set(value) != {"contains_ai_generated_content", "note"}
        or not isinstance(value["contains_ai_generated_content"], bool)
        or not isinstance(value["note"], str)
        or not value["note"].strip()
    ):
        _fail("C8_AI_LABEL_INVALID")
    return copy.deepcopy(value)


def _validate_no_frames(prototype: dict[str, Any]) -> None:
    cards = prototype.get("cards")
    if not isinstance(cards, list):
        _fail("C8_CARDS_INVALID")
    for index, card in enumerate(cards):
        if not isinstance(card, dict) or card.get("frame_refs") != []:
            _fail("FRAME_REFERENCES_NOT_ALLOWED", str(index))


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = FIXED_FILE_MODE << 16
    info.internal_attr = 0
    info.extra = b""
    info.comment = b""
    return info


def build_bundle(c8_prototype: dict[str, Any], source_identity: dict[str, Any]) -> bytes:
    """用现有 C8 JSON 和显式计划水位生成固定三成员 ZIP。"""

    if not isinstance(c8_prototype, dict):
        _fail("C8_PROTOTYPE_OBJECT_REQUIRED")
    prototype = copy.deepcopy(c8_prototype)
    source = _validated_source_identity(source_identity)
    try:
        card_ids = scene_export_tool._validated_prototype_card_ids(prototype)
        markdown = scene_export_tool.render_all(prototype)
    except (scene_export.SceneExportError, scene_export_tool.SceneExportToolError) as exc:
        raise SceneExportBundleError("C8_PROTOTYPE_INVALID", str(exc)) from exc
    _validate_embedded_source(prototype, source)
    ai_label = _validated_ai_label(prototype)
    _validate_no_frames(prototype)
    if not _valid_sha256(prototype.get("source_sha256")):
        _fail("C8_SOURCE_SHA256_INVALID")

    try:
        json_payload = scene_export_tool._output_bytes(prototype)
    except (TypeError, ValueError) as exc:
        raise SceneExportBundleError("C8_PROTOTYPE_NOT_JSON_SERIALIZABLE") from exc
    markdown_payload = markdown.encode("utf-8")
    manifest = {
        "bundle_identity": {
            "contract": BUNDLE_IDENTITY,
            "version": BUNDLE_VERSION,
            "format": "ZIP_STORED_TEXT_ONLY",
        },
        "c8_identity": {
            "contract": prototype["contract"],
            "version": prototype["version"],
            "export_id": prototype["export_id"],
            "source_sha256": prototype["source_sha256"],
        },
        "source_plan": {
            "version": source["source_plan_version"],
            "sha256": source["source_plan_sha256"],
        },
        "card_ids": card_ids,
        "ai_label": ai_label,
        "member_order": list(MEMBER_ORDER),
        "members": {
            "scene_cards.json": {
                "bytes": len(json_payload),
                "sha256": _sha256(json_payload),
            },
            "scene_cards.md": {
                "bytes": len(markdown_payload),
                "sha256": _sha256(markdown_payload),
            },
        },
    }
    manifest_payload = _canonical_json_bytes(manifest)
    payloads = {
        "scene_cards.json": json_payload,
        "scene_cards.md": markdown_payload,
        "manifest.json": manifest_payload,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
    ) as archive:
        archive.comment = b""
        for name in MEMBER_ORDER:
            archive.writestr(_zip_info(name), payloads[name])
    return buffer.getvalue()


def _load_request(path_text: str | None) -> dict[str, Any]:
    if path_text in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(path_text)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE")
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SceneExportBundleError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        _fail("REQUEST_FIELDS_INVALID")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bundle_atomic(path: Path, payload: bytes) -> None:
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY")
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _validate_paths(input_path: str | None, output_path: str) -> None:
    if input_path in {None, "-"}:
        return
    if Path(input_path).resolve() == Path(output_path).resolve():
        _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出 M10 C8 无帧文本 ZIP")
    parser.add_argument("--input", help="输入 JSON；省略或 - 表示 stdin")
    parser.add_argument("--output", required=True, help="输出本地 ZIP 文件")
    args = parser.parse_args(argv)
    try:
        _validate_paths(args.input, args.output)
        request = _load_request(args.input)
        payload = build_bundle(
            request["c8_prototype"],
            request["source_identity"],
        )
        _write_bundle_atomic(Path(args.output), payload)
    except (OSError, SceneExportBundleError) as exc:
        print(f"SCENE_EXPORT_BUNDLE_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = ["SceneExportBundleError", "build_bundle"]


if __name__ == "__main__":
    raise SystemExit(main())
