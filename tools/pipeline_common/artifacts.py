"""公共工件壳：稳定 JSON、SHA-256 与清单核验。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping


class ArtifactError(RuntimeError):
    """工件路径、内容或清单不符合机械合同时抛出。"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ArtifactError(f"不是可读文件：{path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(root: Path, relative_path: str | Path) -> Path:
    """把 POSIX 相对路径锁在根目录内，拒绝绝对路径与越界。"""

    value = PurePosixPath(str(relative_path).replace("\\", "/"))
    if value.is_absolute() or not value.parts or ".." in value.parts:
        raise ArtifactError(f"路径必须是仓内相对路径：{relative_path}")
    resolved_root = root.resolve()
    candidate = (resolved_root / Path(*value.parts)).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ArtifactError(f"路径越出仓库：{relative_path}") from exc
    return candidate


def repo_relative_identity(root: Path, path: str | Path) -> str:
    """把根目录内路径统一写成稳定的 POSIX 相对身份，拒绝越界。"""

    resolved_root = root.resolve()
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = resolve_repo_path(resolved_root, path)
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ArtifactError(f"路径越出仓库：{path}") from exc
    if not relative.parts:
        raise ArtifactError("工件身份不能指向仓库根目录")
    return PurePosixPath(*relative.parts).as_posix()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArtifactError(f"JSON 不存在：{path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"JSON 无法读取：{path}：{exc}") from exc


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_text_atomic(path: Path, text: str) -> None:
    _atomic_write(path, text.encode("utf-8"))


def write_json_atomic(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_text_atomic(path, payload)


def build_manifest(root: Path, paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """为一组仓内文件生成排序稳定的字节清单。"""

    normalized = [PurePosixPath(str(value).replace("\\", "/")).as_posix() for value in paths]
    if len(normalized) != len(set(normalized)):
        raise ArtifactError("清单路径重复")
    entries: list[dict[str, Any]] = []
    for relative in sorted(normalized):
        path = resolve_repo_path(root, relative)
        if not path.is_file():
            raise ArtifactError(f"清单文件不存在：{relative}")
        entries.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def verify_manifest(root: Path, entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """逐条核对路径、字节数和 SHA，不自动修复。"""

    rows = list(entries)
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        relative = str(row.get("path", ""))
        if relative in seen:
            errors.append({"index": index, "path": relative, "reason": "duplicate_path"})
            continue
        seen.add(relative)
        try:
            path = resolve_repo_path(root, relative)
        except ArtifactError as exc:
            errors.append({"index": index, "path": relative, "reason": str(exc)})
            continue
        if not path.is_file():
            errors.append({"index": index, "path": relative, "reason": "missing"})
            continue
        actual_bytes = path.stat().st_size
        actual_sha256 = sha256_file(path)
        if row.get("bytes") != actual_bytes:
            errors.append(
                {
                    "index": index,
                    "path": relative,
                    "reason": "bytes_mismatch",
                    "expected": row.get("bytes"),
                    "actual": actual_bytes,
                }
            )
        if row.get("sha256") != actual_sha256:
            errors.append(
                {
                    "index": index,
                    "path": relative,
                    "reason": "sha256_mismatch",
                    "expected": row.get("sha256"),
                    "actual": actual_sha256,
                }
            )
    return {
        "passed": not errors,
        "checked": len(rows),
        "errors": errors,
    }


ZIP_MANIFEST_NAME = "MANIFEST.json"
ZIP_SHA256SUMS_NAME = "SHA256SUMS"
ZIP_MANIFEST_SCHEMA = "portable-zip-manifest-v1"


def _zip_member_name(value: str) -> str:
    """把 ZIP 成员名锁成相对 POSIX 路径，拒绝越界和平台绝对路径。"""

    if "\\" in value:
        raise ArtifactError(f"ZIP 成员必须使用 POSIX 路径：{value}")
    member = PurePosixPath(value)
    windows_member = PureWindowsPath(value)
    if (
        not value
        or member.is_absolute()
        or bool(windows_member.drive)
        or ".." in member.parts
        or "." in member.parts
        or value.endswith("/")
        or member.as_posix() != value
    ):
        raise ArtifactError(f"ZIP 成员必须是文件相对路径：{value}")
    return member.as_posix()


def _zip_manifest(
    payloads: Mapping[str, bytes],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> bytes:
    rows = [
        {
            "path": path,
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }
        for path, data in sorted(payloads.items())
    ]
    value = {
        "schema_version": ZIP_MANIFEST_SCHEMA,
        "file_count": len(rows),
        "files": rows,
        "metadata": dict(metadata or {}),
    }
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256sums(payloads: Mapping[str, bytes]) -> bytes:
    lines = [
        f"{sha256_bytes(data)}  {path}"
        for path, data in sorted(payloads.items())
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_verified_zip_members(
    payloads: Mapping[str, bytes],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, bytes]:
    """为 payload 加包内清单与 SHA；清单不自哈希，SHA 文件不自哈希。"""

    normalized: dict[str, bytes] = {}
    for raw_path, data in payloads.items():
        path = _zip_member_name(raw_path)
        if path in (ZIP_MANIFEST_NAME, ZIP_SHA256SUMS_NAME):
            raise ArtifactError(f"payload 占用了保留成员名：{path}")
        if path in normalized:
            raise ArtifactError(f"ZIP 成员重名：{path}")
        if not isinstance(data, bytes):
            raise ArtifactError(f"ZIP payload 必须是 bytes：{path}")
        normalized[path] = data

    manifest = _zip_manifest(normalized, metadata=metadata)
    members = dict(normalized)
    members[ZIP_MANIFEST_NAME] = manifest
    members[ZIP_SHA256SUMS_NAME] = _sha256sums(
        {**normalized, ZIP_MANIFEST_NAME: manifest}
    )
    return dict(sorted(members.items()))


def verify_zip_archive(path: Path) -> dict[str, Any]:
    """CRC、成员集合、字节数与逐文件 SHA 四项一起核对。"""

    if not path.is_file():
        raise ArtifactError(f"ZIP 不存在：{path}")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            duplicate_names = sorted(
                {name for name in names if names.count(name) > 1}
            )
            crc_failure = archive.testzip()
            members = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ArtifactError(f"ZIP 无法回读：{path}：{exc}") from exc

    errors: list[dict[str, Any]] = []
    if duplicate_names:
        errors.append(
            {"reason": "duplicate_members", "members": duplicate_names}
        )
    for name in names:
        try:
            _zip_member_name(name)
        except ArtifactError as exc:
            errors.append(
                {
                    "reason": "unsafe_archive_member_path",
                    "path": name,
                    "detail": str(exc),
                }
            )
    if crc_failure is not None:
        errors.append({"reason": "crc_failure", "member": crc_failure})

    manifest_bytes = members.get(ZIP_MANIFEST_NAME)
    sums_bytes = members.get(ZIP_SHA256SUMS_NAME)
    if manifest_bytes is None:
        errors.append({"reason": "manifest_missing"})
    if sums_bytes is None:
        errors.append({"reason": "sha256sums_missing"})

    manifest: dict[str, Any] = {}
    if manifest_bytes is not None:
        try:
            parsed = json.loads(manifest_bytes.decode("utf-8"))
            if isinstance(parsed, dict):
                manifest = parsed
            else:
                errors.append({"reason": "manifest_not_object"})
        except (UnicodeError, json.JSONDecodeError) as exc:
            errors.append({"reason": "manifest_invalid", "detail": str(exc)})

    expected_payloads: set[str] = set()
    rows = manifest.get("files")
    if manifest and not isinstance(rows, list):
        errors.append({"reason": "manifest_files_not_list"})
        rows = []
    if manifest and manifest.get("schema_version") != ZIP_MANIFEST_SCHEMA:
        errors.append(
            {
                "reason": "manifest_schema_version_mismatch",
                "expected": ZIP_MANIFEST_SCHEMA,
                "actual": manifest.get("schema_version"),
            }
        )
    if manifest and (
        type(manifest.get("file_count")) is not int
        or manifest.get("file_count") != len(rows or [])
    ):
        errors.append(
            {
                "reason": "manifest_file_count_mismatch",
                "expected": len(rows or []),
                "actual": manifest.get("file_count"),
            }
        )
    for row in rows or []:
        if not isinstance(row, dict):
            errors.append({"reason": "manifest_row_not_object"})
            continue
        member = str(row.get("path", ""))
        try:
            member = _zip_member_name(member)
        except ArtifactError as exc:
            errors.append(
                {
                    "reason": "unsafe_manifest_member_path",
                    "path": str(row.get("path", "")),
                    "detail": str(exc),
                }
            )
            continue
        if member in expected_payloads:
            errors.append({"reason": "manifest_duplicate_path", "path": member})
            continue
        expected_payloads.add(member)
        data = members.get(member)
        if data is None:
            errors.append({"reason": "manifest_member_missing", "path": member})
            continue
        if row.get("bytes") != len(data):
            errors.append(
                {
                    "reason": "manifest_bytes_mismatch",
                    "path": member,
                    "expected": row.get("bytes"),
                    "actual": len(data),
                }
            )
        actual_sha = sha256_bytes(data)
        if row.get("sha256") != actual_sha:
            errors.append(
                {
                    "reason": "manifest_sha256_mismatch",
                    "path": member,
                    "expected": row.get("sha256"),
                    "actual": actual_sha,
                }
            )

    expected_members = expected_payloads | {
        ZIP_MANIFEST_NAME,
        ZIP_SHA256SUMS_NAME,
    }
    if manifest and set(members) != expected_members:
        errors.append(
            {
                "reason": "member_set_mismatch",
                "missing": sorted(expected_members - set(members)),
                "extra": sorted(set(members) - expected_members),
            }
        )

    sums: dict[str, str] = {}
    if sums_bytes is not None:
        try:
            for line in sums_bytes.decode("utf-8").splitlines():
                digest, separator, member = line.partition("  ")
                if (
                    not separator
                    or len(digest) != 64
                    or member in sums
                ):
                    raise ValueError(f"无效 SHA 行：{line}")
                try:
                    member = _zip_member_name(member)
                except ArtifactError as exc:
                    errors.append(
                        {
                            "reason": "unsafe_sha256sums_member_path",
                            "path": member,
                            "detail": str(exc),
                        }
                    )
                    continue
                sums[member] = digest
        except (UnicodeError, ValueError) as exc:
            errors.append({"reason": "sha256sums_invalid", "detail": str(exc)})

    expected_sums = expected_payloads | {ZIP_MANIFEST_NAME}
    if sums_bytes is not None and set(sums) != expected_sums:
        errors.append(
            {
                "reason": "sha256sums_member_set_mismatch",
                "missing": sorted(expected_sums - set(sums)),
                "extra": sorted(set(sums) - expected_sums),
            }
        )
    for member, expected_sha in sums.items():
        data = members.get(member)
        if data is None:
            continue
        actual_sha = sha256_bytes(data)
        if expected_sha != actual_sha:
            errors.append(
                {
                    "reason": "sha256sums_mismatch",
                    "path": member,
                    "expected": expected_sha,
                    "actual": actual_sha,
                }
            )

    return {
        "passed": not errors,
        "zip_sha256": sha256_file(path),
        "zip_bytes": path.stat().st_size,
        "member_count": len(members),
        "payload_count": len(expected_payloads),
        "crc_passed": crc_failure is None,
        "errors": errors,
    }


def write_verified_zip(
    path: Path,
    payloads: Mapping[str, bytes],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """先写临时 ZIP，完整回读通过后才原子替换目标。"""

    members = build_verified_zip_members(payloads, metadata=metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for member, data in members.items():
                archive.writestr(member, data)
        receipt = verify_zip_archive(temporary)
        if not receipt["passed"]:
            raise ArtifactError(
                "ZIP 回读验收失败："
                + json.dumps(receipt["errors"], ensure_ascii=False)
            )
        os.replace(temporary, path)
        return verify_zip_archive(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
