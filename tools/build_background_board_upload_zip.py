#!/usr/bin/env python3
"""把当前共同背景板编译成可上传的单层 ZIP。"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import posixpath
import re
import sys
import tempfile
import unicodedata
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("config/background_board_upload/sources.json")
CONFIG_SCHEMA = "background-board-flat-package-config-v1"
MANIFEST_SCHEMA = "background-board-flat-package-manifest-v1"
TOOL_VERSION = "1.1"
ROUTER_NAME = "00_CHATGPT_MASTER_ROUTER.md"
MANIFEST_NAME = "01_PACKAGE_MANIFEST.json"
SHA256SUMS_NAME = "02_SHA256SUMS.txt"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
VERSION_RE = re.compile(r"(?:^|_)R(?P<number>[0-9]+(?:[._-][0-9]+)*)$")
PREFIX_RE = re.compile(r"[A-Z][A-Z0-9_-]*")
MARKDOWN_LINK_RE = re.compile(
    r"(?P<open>!?\[[^\]\n]*\]\()(?P<destination><[^>\n]+>|[^)\n]*)(?P<close>\))"
)
JUNK_COMPONENTS = {
    ".ds_store",
    "__macosx",
    "thumbs.db",
    "desktop.ini",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".spotlight-v100",
    ".trashes",
}
JUNK_SUFFIXES = {".pyc", ".pyo", ".swp", ".swo"}


class BackgroundPackageError(RuntimeError):
    """配置、源材料或成品不符合运输合同。"""


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    label: str
    role: str
    version: str
    prefix: str
    root: Path
    root_relative: str
    entry_relative: str
    manifest_relative: str
    manifest_sha256: str
    daily_directory: str | None
    flatten_aliases: dict[str, str]
    additional_included_files: tuple[str, ...]
    pointer_relative: str | None


@dataclass(frozen=True)
class SourceFile:
    source: SourceSpec
    source_relative: str
    source_path: Path
    flat_name: str


@dataclass(frozen=True)
class CompiledPackage:
    package_id: str
    zip_name: str
    zip_bytes: bytes
    zip_sha256: str
    source_count: int
    source_file_count: int
    zip_member_count: int
    skipped_count: int
    sources: tuple[SourceSpec, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise BackgroundPackageError(f"文件无法读取：{path}：{exc}") from exc
    return digest.hexdigest()


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BackgroundPackageError(f"JSON 不存在：{path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BackgroundPackageError(f"JSON 无法读取：{path}：{exc}") from exc
    if not isinstance(value, dict):
        raise BackgroundPackageError(f"JSON 顶层必须是对象：{path}")
    return value


def repo_path(repo_root: Path, raw: str, *, field: str) -> Path:
    value = PurePosixPath(str(raw).replace("\\", "/"))
    if value.is_absolute() or not value.parts or ".." in value.parts:
        raise BackgroundPackageError(f"{field} 必须是仓库内相对路径：{raw}")
    resolved_root = repo_root.resolve()
    resolved = (resolved_root / Path(*value.parts)).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise BackgroundPackageError(f"{field} 越出仓库：{raw}") from exc
    return resolved


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise BackgroundPackageError(f"路径越出仓库：{path}") from exc


def require_keys(value: dict[str, Any], keys: set[str], *, where: str) -> None:
    missing = sorted(keys - value.keys())
    if missing:
        raise BackgroundPackageError(f"{where} 缺字段：{missing}")


def reject_unknown_keys(
    value: dict[str, Any], allowed: set[str], *, where: str
) -> None:
    unknown = sorted(value.keys() - allowed)
    if unknown:
        raise BackgroundPackageError(f"{where} 有未知字段：{unknown}")


def normalize_version(value: Any, *, where: str) -> str:
    version = str(value)
    if not re.fullmatch(r"R[0-9]+(?:[._-][0-9]+)*", version):
        raise BackgroundPackageError(f"{where} 不是可用版本号：{version}")
    return version


def infer_version_from_root(root: Path) -> str:
    match = VERSION_RE.search(root.name)
    if not match:
        raise BackgroundPackageError(f"背景板目录名没有 R 版本：{root.name}")
    return f"R{match.group('number')}"


def version_sort_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"[0-9]+", version))


def ensure_plain_tree(root: Path) -> None:
    if not root.is_dir():
        raise BackgroundPackageError(f"背景板目录不存在：{root}")
    if root.is_symlink():
        raise BackgroundPackageError(f"背景板根目录不能是符号链接：{root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise BackgroundPackageError(f"背景板内出现符号链接，拒绝打包：{path}")


def is_junk(relative: PurePosixPath) -> bool:
    for part in relative.parts:
        folded = part.casefold()
        if folded in JUNK_COMPONENTS or part.startswith("._"):
            return True
    name = relative.name.casefold()
    return name.endswith("~") or any(name.endswith(suffix) for suffix in JUNK_SUFFIXES)


def validate_manifest(source: SourceSpec) -> frozenset[str]:
    manifest_path = source.root / PurePosixPath(source.manifest_relative)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise BackgroundPackageError(
            f"{source.label} 的清单不存在或不是普通文件：{manifest_path}"
        )
    actual_manifest_sha = sha256_file(manifest_path)
    if actual_manifest_sha != source.manifest_sha256:
        raise BackgroundPackageError(
            f"{source.label} 清单 SHA 漂移："
            f"配置/指针={source.manifest_sha256}，现物={actual_manifest_sha}"
        )

    manifest = read_json(manifest_path)
    rows = manifest.get("members")
    if rows is None:
        rows = manifest.get("files")
    if not isinstance(rows, list):
        raise BackgroundPackageError(
            f"{source.label} 清单缺少 members 或 files 数组"
        )
    listed: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise BackgroundPackageError(
                f"{source.label} 清单第 {index + 1} 项没有合法 path"
            )
        expected_sha = row.get("sha256")
        expected_bytes = row.get("bytes")
        relative = PurePosixPath(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise BackgroundPackageError(
                f"{source.label} 清单成员路径不安全：{row['path']}"
            )
        normalized = relative.as_posix()
        if normalized in listed:
            raise BackgroundPackageError(
                f"{source.label} 清单成员重复：{normalized}"
            )
        listed.add(normalized)
        if expected_sha is None and expected_bytes is None:
            if normalized != source.manifest_relative:
                raise BackgroundPackageError(
                    f"{source.label} 只有清单自身可省略 bytes 和 sha256：{normalized}"
                )
            continue
        path = source.root / Path(*relative.parts)
        if not path.is_file() or path.is_symlink():
            raise BackgroundPackageError(
                f"{source.label} 清单成员不存在或不是普通文件：{row['path']}"
            )
        if expected_bytes is not None and path.stat().st_size != expected_bytes:
            raise BackgroundPackageError(
                f"{source.label} 清单成员字节数漂移：{row['path']}"
            )
        if expected_sha is not None and sha256_file(path) != expected_sha:
            raise BackgroundPackageError(
                f"{source.label} 清单成员 SHA 漂移：{row['path']}"
            )
    listed.add(source.manifest_relative)
    overlap = sorted(listed.intersection(source.additional_included_files))
    if overlap:
        raise BackgroundPackageError(
            f"{source.label} 的 additional_included_files 与清单重复：{overlap}"
        )
    for relative_raw in source.additional_included_files:
        relative = PurePosixPath(relative_raw)
        path = source.root / Path(*relative.parts)
        if not path.is_file() or path.is_symlink():
            raise BackgroundPackageError(
                f"{source.label} 明确追加文件不存在或不是普通文件：{relative_raw}"
            )
        listed.add(relative_raw)
    return frozenset(listed)


def resolve_direct_source(
    repo_root: Path, row: dict[str, Any], common: dict[str, Any]
) -> SourceSpec:
    allowed = set(common) | {
        "resolver",
        "entry_path",
        "manifest_path",
        "manifest_sha256",
        "authority_file",
        "version",
    }
    reject_unknown_keys(row, allowed, where=f"source {row.get('source_id')}")
    require_keys(
        row,
        {"entry_path", "manifest_path", "authority_file", "version"},
        where=f"source {row.get('source_id')}",
    )
    entry = repo_path(repo_root, row["entry_path"], field="entry_path")
    root = entry.parent
    if not entry.is_file() or entry.is_symlink():
        raise BackgroundPackageError(f"产品背景板入口不存在：{entry}")
    version = normalize_version(row["version"], where="direct source version")
    inferred = infer_version_from_root(root)
    if inferred != version:
        raise BackgroundPackageError(
            f"配置版本 {version} 与目录版本 {inferred} 不一致：{root.name}"
        )
    manifest = repo_path(repo_root, row["manifest_path"], field="manifest_path")
    try:
        manifest_relative = manifest.relative_to(root).as_posix()
    except ValueError as exc:
        raise BackgroundPackageError("产品清单必须放在产品背景板目录内") from exc
    authority = repo_path(repo_root, row["authority_file"], field="authority_file")
    try:
        authority_text = authority.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BackgroundPackageError(f"当前入口依据无法读取：{authority}") from exc
    expected_link = f"({repo_relative(repo_root, entry)})"
    if expected_link not in authority_text:
        raise BackgroundPackageError(
            f"配置里的产品背景板不是 {row['authority_file']} 当前链接：{row['entry_path']}"
        )
    configured_manifest_sha = row.get("manifest_sha256")
    manifest_sha = sha256_file(manifest)
    if configured_manifest_sha is not None and configured_manifest_sha != manifest_sha:
        raise BackgroundPackageError("产品背景板配置中的 manifest_sha256 已漂移")
    return SourceSpec(
        **common,
        version=version,
        root=root,
        root_relative=repo_relative(repo_root, root),
        entry_relative=entry.relative_to(root).as_posix(),
        manifest_relative=manifest_relative,
        manifest_sha256=manifest_sha,
        pointer_relative=None,
    )


def resolve_pointer_source(
    repo_root: Path, row: dict[str, Any], common: dict[str, Any]
) -> SourceSpec:
    allowed = set(common) | {
        "resolver",
        "pointer_path",
        "entry_field",
        "manifest_field",
        "version_field",
    }
    reject_unknown_keys(row, allowed, where=f"source {row.get('source_id')}")
    require_keys(
        row,
        {"pointer_path", "entry_field", "manifest_field", "version_field"},
        where=f"source {row.get('source_id')}",
    )
    pointer = repo_path(repo_root, row["pointer_path"], field="pointer_path")
    pointer_data = read_json(pointer)
    for key in (row["entry_field"], row["manifest_field"], row["version_field"]):
        if key not in pointer_data:
            raise BackgroundPackageError(f"当前指针缺字段：{key}")
    base = pointer.parent
    entry_raw = pointer_data[row["entry_field"]]
    manifest_raw = pointer_data[row["manifest_field"]]
    if not isinstance(entry_raw, str) or not isinstance(manifest_raw, str):
        raise BackgroundPackageError("当前指针的入口和清单路径必须是字符串")
    entry_relative = PurePosixPath(entry_raw.replace("\\", "/"))
    manifest_relative_path = PurePosixPath(manifest_raw.replace("\\", "/"))
    for value, field in (
        (entry_relative, "entry_field"),
        (manifest_relative_path, "manifest_field"),
    ):
        if value.is_absolute() or not value.parts or ".." in value.parts:
            raise BackgroundPackageError(f"当前指针 {field} 必须是安全相对路径")
    entry = (base / Path(*entry_relative.parts)).resolve()
    manifest = (base / Path(*manifest_relative_path.parts)).resolve()
    resolved_repo = repo_root.resolve()
    for path, field in ((entry, "entry_field"), (manifest, "manifest_field")):
        try:
            path.relative_to(resolved_repo)
        except ValueError as exc:
            raise BackgroundPackageError(f"当前指针 {field} 越出仓库") from exc
    root = entry.parent
    try:
        manifest_relative = manifest.relative_to(root).as_posix()
    except ValueError as exc:
        raise BackgroundPackageError("报告清单必须放在当前报告背景板目录内") from exc
    if not entry.is_file() or entry.is_symlink():
        raise BackgroundPackageError(f"报告背景板入口不存在：{entry}")
    version = normalize_version(
        pointer_data[row["version_field"]], where="current pointer version"
    )
    inferred = infer_version_from_root(root)
    if inferred != version:
        raise BackgroundPackageError(
            f"当前指针版本 {version} 与目录版本 {inferred} 不一致"
        )
    package_id = pointer_data.get("current_package_id")
    if package_id is not None and package_id != root.name:
        raise BackgroundPackageError("当前指针的 package id 与入口目录不一致")
    expected_manifest_sha = pointer_data.get("manifest_sha256")
    if not isinstance(expected_manifest_sha, str):
        raise BackgroundPackageError("当前指针缺合法 manifest_sha256")
    return SourceSpec(
        **common,
        version=version,
        root=root,
        root_relative=repo_relative(repo_root, root),
        entry_relative=entry.relative_to(root).as_posix(),
        manifest_relative=manifest_relative,
        manifest_sha256=expected_manifest_sha,
        pointer_relative=repo_relative(repo_root, pointer),
    )


def resolve_highest_version_source(
    repo_root: Path, row: dict[str, Any], common: dict[str, Any]
) -> SourceSpec:
    allowed = set(common) | {
        "resolver",
        "base_directory",
        "directory_prefix",
        "entry_name",
        "manifest_name",
    }
    reject_unknown_keys(row, allowed, where=f"source {row.get('source_id')}")
    require_keys(
        row,
        {"base_directory", "directory_prefix", "entry_name", "manifest_name"},
        where=f"source {row.get('source_id')}",
    )
    base = repo_path(repo_root, row["base_directory"], field="base_directory")
    if not base.is_dir() or base.is_symlink():
        raise BackgroundPackageError(f"版本存放目录不存在或不是普通目录：{base}")
    directory_prefix = str(row["directory_prefix"])
    if not directory_prefix or "/" in directory_prefix or "\\" in directory_prefix:
        raise BackgroundPackageError("directory_prefix 不合法")
    entry_name = PurePosixPath(str(row["entry_name"]))
    manifest_name = PurePosixPath(str(row["manifest_name"]))
    for value, field in ((entry_name, "entry_name"), (manifest_name, "manifest_name")):
        if value.is_absolute() or len(value.parts) != 1 or value.name in {".", ".."}:
            raise BackgroundPackageError(f"{field} 必须是单个安全文件名")

    candidates: list[tuple[tuple[int, ...], str, Path]] = []
    for child in sorted(base.iterdir()):
        if child.is_symlink() or not child.is_dir():
            continue
        if not child.name.startswith(directory_prefix):
            continue
        match = VERSION_RE.search(child.name)
        if not match:
            continue
        version = normalize_version(
            f"R{match.group('number')}", where=f"目录 {child.name}"
        )
        entry = child / entry_name.name
        manifest = child / manifest_name.name
        if not entry.is_file() or entry.is_symlink():
            continue
        if not manifest.is_file() or manifest.is_symlink():
            continue
        manifest_data = read_json(manifest)
        package_id = manifest_data.get("package_id")
        if package_id is not None and package_id != child.name:
            continue
        candidates.append((version_sort_key(version), version, child))
    if not candidates:
        raise BackgroundPackageError(
            f"{base} 下没有入口和清单都完整的版本目录：{directory_prefix}*_R数字"
        )
    highest_key = max(item[0] for item in candidates)
    highest = [item for item in candidates if item[0] == highest_key]
    if len(highest) != 1:
        names = [item[2].name for item in highest]
        raise BackgroundPackageError(f"最高版本出现多个目录，无法自动拍板：{names}")
    _, version, root = highest[0]
    manifest = root / manifest_name.name
    return SourceSpec(
        **common,
        version=version,
        root=root,
        root_relative=repo_relative(repo_root, root),
        entry_relative=entry_name.name,
        manifest_relative=manifest_name.name,
        manifest_sha256=sha256_file(manifest),
        pointer_relative=None,
    )


def resolve_sources(repo_root: Path, config: dict[str, Any]) -> tuple[SourceSpec, ...]:
    reject_unknown_keys(
        config,
        {"schema_version", "output_directory", "sources"},
        where="config",
    )
    require_keys(
        config,
        {"schema_version", "output_directory", "sources"},
        where="config",
    )
    if config["schema_version"] != CONFIG_SCHEMA:
        raise BackgroundPackageError(
            f"配置版本不支持：{config['schema_version']}"
        )
    rows = config["sources"]
    if not isinstance(rows, list) or len(rows) < 2:
        raise BackgroundPackageError("sources 至少要登记产品背景板和报告背景板")
    resolved: list[SourceSpec] = []
    seen_ids: set[str] = set()
    seen_prefixes: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise BackgroundPackageError("sources 每一项都必须是对象")
        require_keys(
            row,
            {"source_id", "label", "role", "prefix", "resolver"},
            where="source",
        )
        source_id = str(row["source_id"])
        prefix = str(row["prefix"])
        if source_id in seen_ids:
            raise BackgroundPackageError(f"source_id 重复：{source_id}")
        if prefix in seen_prefixes:
            raise BackgroundPackageError(f"prefix 重复：{prefix}")
        if not PREFIX_RE.fullmatch(prefix) or "__" in prefix:
            raise BackgroundPackageError(f"prefix 不合法：{prefix}")
        aliases = row.get("flatten_aliases", {})
        if not isinstance(aliases, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in aliases.items()
        ):
            raise BackgroundPackageError(f"flatten_aliases 不合法：{source_id}")
        additional_raw = row.get("additional_included_files", [])
        if not isinstance(additional_raw, list) or not all(
            isinstance(value, str) for value in additional_raw
        ):
            raise BackgroundPackageError(
                f"additional_included_files 不合法：{source_id}"
            )
        additional: list[str] = []
        for value in additional_raw:
            relative = PurePosixPath(value.replace("\\", "/"))
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                raise BackgroundPackageError(
                    f"additional_included_files 必须是安全相对路径：{value}"
                )
            normalized = relative.as_posix()
            if normalized in additional:
                raise BackgroundPackageError(
                    f"additional_included_files 重复：{normalized}"
                )
            additional.append(normalized)
        common = {
            "source_id": source_id,
            "label": str(row["label"]),
            "role": str(row["role"]),
            "prefix": prefix,
            "daily_directory": (
                str(row["daily_directory"])
                if row.get("daily_directory") is not None
                else None
            ),
            "flatten_aliases": dict(aliases),
            "additional_included_files": tuple(additional),
        }
        resolver = row["resolver"]
        if resolver == "direct_entry":
            source = resolve_direct_source(repo_root, row, common)
        elif resolver == "highest_version_directory":
            source = resolve_highest_version_source(repo_root, row, common)
        elif resolver == "current_pointer":
            source = resolve_pointer_source(repo_root, row, common)
        else:
            raise BackgroundPackageError(f"未知 resolver：{resolver}")
        ensure_plain_tree(source.root)
        validate_manifest(source)
        resolved.append(source)
        seen_ids.add(source_id)
        seen_prefixes.add(prefix)
    return tuple(resolved)


def flat_name(source: SourceSpec, relative: PurePosixPath) -> str:
    parts = list(relative.parts)
    if not parts:
        raise BackgroundPackageError("不能打包空相对路径")
    for index in range(len(parts) - 1):
        parts[index] = source.flatten_aliases.get(parts[index], parts[index])
    name = unicodedata.normalize(
        "NFC", f"{source.prefix}_{source.version}__{'__'.join(parts)}"
    )
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise BackgroundPackageError(f"平铺文件名不安全：{name}")
    if len(name.encode("utf-8")) > 240:
        raise BackgroundPackageError(f"平铺文件名超过 240 字节：{name}")
    return name


def enumerate_source_files(
    sources: tuple[SourceSpec, ...],
) -> tuple[list[SourceFile], list[dict[str, str]]]:
    files: list[SourceFile] = []
    skipped: list[dict[str, str]] = []
    folded_names: dict[str, str] = {}
    for source in sources:
        allowed_files = validate_manifest(source)
        for path in sorted(source.root.rglob("*")):
            if not path.is_file():
                continue
            relative = PurePosixPath(path.relative_to(source.root).as_posix())
            if is_junk(relative):
                skipped.append(
                    {
                        "source_id": source.source_id,
                        "source_relative_path": relative.as_posix(),
                        "reason": "os_or_tool_cache_junk",
                    }
                )
                continue
            if relative.as_posix() not in allowed_files:
                raise BackgroundPackageError(
                    f"{source.label} 出现清单外普通文件，拒绝打包：{relative.as_posix()}"
                )
            name = flat_name(source, relative)
            folded = unicodedata.normalize("NFC", name).casefold()
            if folded in folded_names:
                raise BackgroundPackageError(
                    f"平铺后文件名冲突：{folded_names[folded]} / {name}"
                )
            folded_names[folded] = name
            files.append(
                SourceFile(
                    source=source,
                    source_relative=relative.as_posix(),
                    source_path=path,
                    flat_name=name,
                )
            )
    return sorted(files, key=lambda item: item.flat_name), skipped


def _split_destination(value: str) -> tuple[str, str, str]:
    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    body = value.strip()
    if body.startswith("<") and ">" in body:
        end = body.index(">")
        return leading + body[1:end], body[end + 1 :], trailing
    match = re.match(r"(?P<url>\S+)(?P<title>.*)", body)
    if not match:
        return value, "", ""
    return leading + match.group("url"), match.group("title"), trailing


def rewrite_markdown_links(
    text: str,
    *,
    source_relative: str,
    mapping: dict[str, str],
) -> tuple[str, int]:
    count = 0
    parent = PurePosixPath(source_relative).parent

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        raw_url, title, trailing = _split_destination(match.group("destination"))
        leading = raw_url[: len(raw_url) - len(raw_url.lstrip())]
        url = raw_url.strip()
        split = urllib.parse.urlsplit(url)
        if split.scheme or split.netloc or not split.path or split.path.startswith("/"):
            return match.group(0)
        decoded = urllib.parse.unquote(split.path)
        normalized = posixpath.normpath((parent / decoded).as_posix())
        if normalized == ".." or normalized.startswith("../"):
            return match.group(0)
        replacement = mapping.get(normalized)
        if replacement is None:
            return match.group(0)
        destination = urllib.parse.urlunsplit(
            ("", "", replacement, split.query, split.fragment)
        )
        if any(char.isspace() for char in destination) or any(
            char in destination for char in "()"
        ):
            destination = f"<{destination}>"
        count += 1
        return (
            match.group("open")
            + leading
            + destination
            + title
            + trailing
            + match.group("close")
        )

    return MARKDOWN_LINK_RE.sub(replace, text), count


def compile_source_payloads(
    files: list[SourceFile],
) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    mapping_by_source: dict[str, dict[str, str]] = {}
    for item in files:
        mapping_by_source.setdefault(item.source.source_id, {})[
            item.source_relative
        ] = item.flat_name

    payloads: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for item in files:
        raw = item.source_path.read_bytes()
        packaged = raw
        rewrites = 0
        transform = "filename_prefix_and_flatten_only"
        if item.source_path.suffix.casefold() == ".md":
            try:
                text = raw.decode("utf-8")
            except UnicodeError as exc:
                raise BackgroundPackageError(
                    f"Markdown 不是 UTF-8：{item.source_path}"
                ) from exc
            text, rewrites = rewrite_markdown_links(
                text,
                source_relative=item.source_relative,
                mapping=mapping_by_source[item.source.source_id],
            )
            packaged = text.encode("utf-8")
            if rewrites:
                transform = "filename_prefix_flatten_and_internal_link_rewrite"
        payloads[item.flat_name] = packaged
        rows.append(
            {
                "source_id": item.source.source_id,
                "source_relative_path": item.source_relative,
                "flat_name": item.flat_name,
                "source_bytes": len(raw),
                "source_sha256": sha256_bytes(raw),
                "packaged_bytes": len(packaged),
                "packaged_sha256": sha256_bytes(packaged),
                "transform": transform,
                "internal_links_rewritten": rewrites,
            }
        )
    return payloads, rows


def render_router(
    package_id: str,
    sources: tuple[SourceSpec, ...],
    files: list[SourceFile],
) -> bytes:
    flat_by_source_relative = {
        (item.source.source_id, item.source_relative): item.flat_name for item in files
    }
    lines = [
        "# ChatGPT 背景板总导航",
        "",
        f"- 运输包：`{package_id}`",
        "- 形态：所有材料平铺在同一层；源文件用“背景板身份＋版本”前缀消除重名。",
        "- 边界：本包只是手工上传／解压用的运输副本，不替代本地正式背景板，不产生施工、训练、API、Git、Notion 或生产权限。",
        "",
        "## 怎么读",
        "",
    ]
    for index, source in enumerate(sources, start=1):
        if source.role == "product_authority":
            meaning = "回答我们准备做什么产品、哪些原则和边界已经拍下"
        elif source.role == "external_evidence":
            meaning = "回答外面有什么证据、经验、反例和未知，不能替产品拍板"
        elif source.role == "requirements_acceptance_baseline":
            meaning = "回答每项局部能力应让用户得到什么、怎样验收，不能证明代码已经做到"
        else:
            meaning = "按入口声明的身份和权限边界使用"
        lines.append(f"{index}. {source.label}{meaning}。")
    lines.extend(
        [
            f"{len(sources) + 1}. 平时只读与任务直接相关的入口和主题，不把所有材料一次塞进上下文。",
            f"{len(sources) + 2}. 当前代码、正式合同和运行结果不在本包里；判断‘已经做到什么’必须回本地现物核对。",
            f"{len(sources) + 3}. 包外的本地相对链接不会被塞进本包；只有同一背景板内、且本包确实包含目标文件的链接会改成平铺文件名。",
            "",
            "## 冲突时怎么判断",
            "",
            "- CZ 最新明确指令和正式合同／结果票高于背景板文字。",
            "- 产品共同背景板负责产品原则；原子需求板负责拆解目标和验收，不能反过来改产品原则。",
            "- 外部报告只提供证据、反例和候选，不产生产品、施工、训练或上传权限。",
            "- 涉及作者数据时，优先读取产品板里的数据权利与安全政策；换平台不能降低作者隔离和最小授权边界。",
            "",
            "## 当前背景板",
            "",
            "| 身份 | 版本 | 入口 | 日常读法 |",
            "|---|---|---|---|",
        ]
    )
    for source in sources:
        entry_flat = flat_by_source_relative[(source.source_id, source.entry_relative)]
        if source.role == "product_authority":
            daily = "先读入口，再按产品问题选 01～08 或政策／债务页"
        elif source.role == "requirements_acceptance_baseline":
            daily = "先读入口；人按模块查预期，Agent 精确读取机器 JSON"
        elif source.daily_directory:
            daily = f"先读 `{source.prefix}_{source.version}__{source.flatten_aliases.get(source.daily_directory, source.daily_directory)}__*` 主题页"
        else:
            daily = "先读入口，再按任务选相关文件"
        lines.append(
            f"| {source.label} | `{source.version}` | [{entry_flat}]({entry_flat}) | {daily} |"
        )

    for source in sources:
        daily_items = [
            item
            for item in files
            if item.source.source_id == source.source_id
            and source.daily_directory
            and PurePosixPath(item.source_relative).parts[0]
            == source.daily_directory
        ]
        if daily_items:
            lines.extend(["", f"## {source.label}的日常主题页", ""])
            lines.extend(
                f"- [{item.flat_name}]({item.flat_name})" for item in daily_items
            )

    lines.extend(["", "## 原路径与平铺文件名对照", ""])
    for source in sources:
        lines.extend([f"### {source.label} {source.version}", ""])
        lines.extend(
            [
                "| 原相对路径 | ZIP 内文件名 |",
                "|---|---|",
            ]
        )
        for item in files:
            if item.source.source_id != source.source_id:
                continue
            lines.append(
                f"| `{item.source_relative}` | [{item.flat_name}]({item.flat_name}) |"
            )
        lines.append("")
    lines.extend(
        [
            "## 校验文件",
            "",
            f"- `{MANIFEST_NAME}`：记录每份原件和运输副本的字节数、SHA、改名及链接改写数。",
            f"- `{SHA256SUMS_NAME}`：核对 ZIP 内除它自身外的每个成员。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def build_zip_bytes(payloads: dict[str, bytes], *, package_id: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        archive.comment = package_id.encode("ascii")
        for name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo(filename=name, date_time=FIXED_ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def verify_zip_bytes(
    zip_bytes: bytes, expected: dict[str, bytes], *, package_id: str
) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
            names = archive.namelist()
            if archive.comment != package_id.encode("ascii"):
                raise BackgroundPackageError("ZIP 包身份注释不一致")
            if archive.testzip() is not None:
                raise BackgroundPackageError("ZIP CRC 回读失败")
            if len(names) != len(set(names)):
                raise BackgroundPackageError("ZIP 出现重名成员")
            folded = [unicodedata.normalize("NFC", name).casefold() for name in names]
            if len(folded) != len(set(folded)):
                raise BackgroundPackageError("ZIP 出现大小写或 Unicode 等价重名")
            if any("/" in name or "\\" in name for name in names):
                raise BackgroundPackageError("ZIP 不是单层平铺结构")
            if any(is_junk(PurePosixPath(name)) for name in names):
                raise BackgroundPackageError("ZIP 混入缓存垃圾")
            if sorted(names) != sorted(expected):
                raise BackgroundPackageError("ZIP 成员集合与清单不一致")
            for info in archive.infolist():
                if info.date_time != FIXED_ZIP_TIME:
                    raise BackgroundPackageError(f"ZIP 时间戳不固定：{info.filename}")
                if archive.read(info.filename) != expected[info.filename]:
                    raise BackgroundPackageError(
                        f"ZIP 成员字节与预期不一致：{info.filename}"
                    )
    except zipfile.BadZipFile as exc:
        raise BackgroundPackageError(f"ZIP 无法回读：{exc}") from exc


def compile_package(repo_root: Path, config_path: Path) -> CompiledPackage:
    config = read_json(config_path)
    sources = resolve_sources(repo_root, config)
    files, skipped = enumerate_source_files(sources)
    if not files:
        raise BackgroundPackageError("没有可打包的背景板文件")
    payloads, file_rows = compile_source_payloads(files)
    package_id = "CHATGPT_FLAT_BACKGROUND_BOARDS_" + "_".join(
        f"{source.prefix}_{source.version}" for source in sources
    )
    router = render_router(package_id, sources, files)
    payloads[ROUTER_NAME] = router
    source_rows = []
    flat_by_source_relative = {
        (item.source.source_id, item.source_relative): item.flat_name for item in files
    }
    for source in sources:
        source_rows.append(
            {
                "source_id": source.source_id,
                "label": source.label,
                "role": source.role,
                "version": source.version,
                "root": source.root_relative,
                "entry_source_relative_path": source.entry_relative,
                "entry_flat_name": flat_by_source_relative[
                    (source.source_id, source.entry_relative)
                ],
                "manifest_source_relative_path": source.manifest_relative,
                "manifest_sha256": source.manifest_sha256,
                "current_pointer": source.pointer_relative,
                "additional_included_files": list(source.additional_included_files),
            }
        )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "package_id": package_id,
        "tool": {
            "path": "tools/build_background_board_upload_zip.py",
            "version": TOOL_VERSION,
            "config": repo_relative(repo_root, config_path),
        },
        "identity": "manual_extract_or_upload_transport_copy",
        "authority": "NO_PRODUCT_EXECUTION_TRAINING_API_GIT_NOTION_OR_PRODUCTION_AUTHORITY",
        "layout": "single_flat_directory",
        "source_count": len(sources),
        "source_file_count": len(file_rows),
        "generated_member_count": 3,
        "zip_member_count": len(file_rows) + 3,
        "junk_excluded_count": len(skipped),
        "junk_policy": {
            "action": "exclude_from_transport_only_do_not_modify_sources",
            "components": sorted(JUNK_COMPONENTS),
            "suffixes": sorted(JUNK_SUFFIXES),
            "apple_double_prefix": "._",
            "editor_backup_suffix": "~",
        },
        "transform_policy": {
            "all_source_files": "add source identity and version prefix, then flatten",
            "markdown": "rewrite only links whose targets are included in the same source board",
            "images_and_other_files": "rename only; bytes unchanged",
            "external_or_out_of_package_links": "leave unchanged",
        },
        "sources": source_rows,
        "files": file_rows,
        "skipped_junk": skipped,
        "generated_members": [ROUTER_NAME, MANIFEST_NAME, SHA256SUMS_NAME],
    }
    manifest_bytes = stable_json_bytes(manifest)
    payloads[MANIFEST_NAME] = manifest_bytes
    sums = "".join(
        f"{sha256_bytes(data)}  {name}\n"
        for name, data in sorted(payloads.items())
    ).encode("utf-8")
    payloads[SHA256SUMS_NAME] = sums
    zip_bytes = build_zip_bytes(payloads, package_id=package_id)
    verify_zip_bytes(zip_bytes, payloads, package_id=package_id)
    return CompiledPackage(
        package_id=package_id,
        zip_name=f"{package_id}.zip",
        zip_bytes=zip_bytes,
        zip_sha256=sha256_bytes(zip_bytes),
        source_count=len(sources),
        source_file_count=len(file_rows),
        zip_member_count=len(payloads),
        skipped_count=len(skipped),
        sources=sources,
    )


def resolve_output_directory(repo_root: Path, config: dict[str, Any]) -> Path:
    raw = config.get("output_directory")
    if not isinstance(raw, str):
        raise BackgroundPackageError("output_directory 必须是字符串")
    relative = PurePosixPath(raw.replace("\\", "/"))
    if relative.is_absolute() or not relative.parts or relative.parts[0] != "TEMP":
        raise BackgroundPackageError("output_directory 必须放在仓库 TEMP 下")
    output = repo_path(repo_root, raw, field="output_directory")
    temp_root = (repo_root / "TEMP").resolve()
    try:
        output.relative_to(temp_root)
    except ValueError as exc:
        raise BackgroundPackageError("output_directory 必须放在仓库 TEMP 下") from exc
    return output


def write_new_file_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise BackgroundPackageError(f"目标 ZIP 已存在，拒绝覆盖：{path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def run(repo_root: Path, config_path: Path, *, check: bool) -> dict[str, Any]:
    config = read_json(config_path)
    output_directory = resolve_output_directory(repo_root, config)
    compiled = compile_package(repo_root, config_path)
    zip_path = output_directory / compiled.zip_name
    if check:
        if not zip_path.is_file():
            raise BackgroundPackageError(f"待核 ZIP 不存在：{zip_path}")
        actual = zip_path.read_bytes()
        if actual != compiled.zip_bytes:
            raise BackgroundPackageError(
                "现有 ZIP 与当前背景板的确定性编译结果不一致；"
                "不要覆盖旧版，请先核对背景板是否已经升版"
            )
        status = "PASS_BYTE_IDENTICAL"
    elif zip_path.exists():
        if not zip_path.is_file() or zip_path.read_bytes() != compiled.zip_bytes:
            raise BackgroundPackageError(
                f"同名目标已存在但内容不同，拒绝覆盖：{zip_path}"
            )
        status = "REUSED_BYTE_IDENTICAL"
    else:
        write_new_file_atomic(zip_path, compiled.zip_bytes)
        status = "CREATED"
    return {
        "status": status,
        "zip_path": str(zip_path),
        "zip_sha256": compiled.zip_sha256,
        "package_id": compiled.package_id,
        "source_versions": {
            source.source_id: source.version for source in compiled.sources
        },
        "source_files": compiled.source_file_count,
        "zip_members": compiled.zip_member_count,
        "junk_excluded": compiled.skipped_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="一键生成当前共同背景板的 ChatGPT 单层 ZIP。"
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=("build", "check"),
        default="build",
        help="build 创建或复用字节一致的 ZIP；check 只核对现有 ZIP。",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG.as_posix(),
        help="仓库内配置路径。",
    )
    args = parser.parse_args(argv)
    try:
        config_path = repo_path(ROOT, args.config, field="--config")
        result = run(ROOT, config_path, check=args.action == "check")
    except BackgroundPackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
