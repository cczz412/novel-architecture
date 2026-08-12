#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_RELATIVE = Path("governance/external_archive_registry.json")
REGISTRY_SCHEMA_RELATIVE = Path(
    "governance/contracts/external_archive_registry_v1.schema.json"
)
REPORT_SCHEMA_RELATIVE = Path(
    "governance/contracts/repo_slim_inventory_report_v1.schema.json"
)
MIGRATION_RECEIPT_SCHEMA_RELATIVE = Path(
    "governance/contracts/repository_size_migration_receipt_v1.schema.json"
)
MAX_REGISTERED_FILE_BYTES = 5 * 1024 * 1024
DISKUTIL = Path("/usr/sbin/diskutil")


class InventoryError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        message = code if not detail else f"{code}: {detail}"
        super().__init__(message)
        self.code = code
        self.detail = detail


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _identity(
    value: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _safe_relative_path(value: object, *, code: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise InventoryError(code, "路径必须是非空字符串")
    if "\x00" in value or "\\" in value or "//" in value:
        raise InventoryError(code, "路径含不允许的字符")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise InventoryError(code, "路径必须是规范的相对路径")
    if ".git" in relative.parts:
        raise InventoryError(code, "路径不能进入 .git")
    return relative


def _path_from_posix(root: Path, relative: PurePosixPath) -> Path:
    return root.joinpath(*relative.parts)


def _require_plain_directory(path: Path, *, code: str) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise InventoryError(code, "目录不存在") from exc
    if stat.S_ISLNK(info.st_mode):
        raise InventoryError(code, "拒绝符号链接目录")
    if not stat.S_ISDIR(info.st_mode):
        raise InventoryError(code, "不是目录")


def _require_plain_path_chain(
    root: Path,
    relative: PurePosixPath,
    *,
    final_kind: str,
    code: str,
) -> Path:
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as exc:
            raise InventoryError(code, "登记路径不存在") from exc
        if stat.S_ISLNK(info.st_mode):
            raise InventoryError(code, "登记路径经过符号链接")
        is_final = index == len(relative.parts) - 1
        if not is_final and not stat.S_ISDIR(info.st_mode):
            raise InventoryError(code, "登记路径的父级不是目录")
        if is_final and final_kind == "directory" and not stat.S_ISDIR(info.st_mode):
            raise InventoryError(code, "登记对象不是目录")
        if is_final and final_kind == "file" and not stat.S_ISREG(info.st_mode):
            raise InventoryError(code, "登记锚不是普通文件")
    return current


def _external_volume_records() -> list[dict[str, Any]]:
    try:
        completed = subprocess.run(
            [str(DISKUTIL), "list", "-plist", "external", "physical"],
            check=True,
            capture_output=True,
        )
        value = plistlib.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, plistlib.InvalidFileException) as exc:
        raise InventoryError(
            "EXTERNAL_VOLUME_DISCOVERY_FAILED",
            "无法读取已挂载外置物理卷身份",
        ) from exc
    rows: list[dict[str, Any]] = []
    for disk in value.get("AllDisksAndPartitions", []):
        if not isinstance(disk, dict):
            continue
        for partition in disk.get("Partitions", []):
            if not isinstance(partition, dict):
                continue
            rows.append(
                {
                    **partition,
                    "ParentWholeDisk": disk.get("DeviceIdentifier"),
                }
            )
    return rows


def _repository_parent_whole_disk(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["/bin/df", "-kP", str(repo_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        device = lines[-1].split()[0]
        info = subprocess.run(
            [str(DISKUTIL), "info", "-plist", device],
            check=True,
            capture_output=True,
        )
        value = plistlib.loads(info.stdout)
    except (
        IndexError,
        OSError,
        subprocess.CalledProcessError,
        plistlib.InvalidFileException,
    ) as exc:
        raise InventoryError(
            "REPOSITORY_DEVICE_IDENTITY_FAILED",
            "无法确认 repository 所在物理设备",
        ) from exc
    parent = value.get("ParentWholeDisk")
    if not isinstance(parent, str) or not parent:
        raise InventoryError(
            "REPOSITORY_DEVICE_IDENTITY_FAILED",
            "repository 缺少物理设备身份",
        )
    return parent


def _resolve_external_volume_uuid(
    repo_root: Path,
    locator: dict[str, Any],
) -> Path:
    volume_uuid = locator.get("volume_uuid")
    matches = [
        row
        for row in _external_volume_records()
        if row.get("VolumeUUID") == volume_uuid
        and isinstance(row.get("MountPoint"), str)
    ]
    if len(matches) != 1:
        raise InventoryError(
            "EXTERNAL_VOLUME_UUID_NOT_UNIQUE",
            "指定 UUID 必须唯一对应一个已挂载外置物理卷",
        )
    mount = Path(matches[0]["MountPoint"])
    if not mount.is_absolute():
        raise InventoryError(
            "EXTERNAL_VOLUME_MOUNT_INVALID",
            "外置卷挂载点不是绝对路径",
        )
    _require_plain_directory(mount, code="EXTERNAL_VOLUME_MOUNT_INVALID")
    parent_disk = matches[0].get("ParentWholeDisk")
    if (
        not isinstance(parent_disk, str)
        or parent_disk == _repository_parent_whole_disk(repo_root)
    ):
        raise InventoryError(
            "EXTERNAL_VOLUME_FAILURE_DOMAIN_INVALID",
            "外置卷与 repository 仍处于同一物理设备",
        )
    relative_root = _safe_relative_path(
        locator.get("relative_root"),
        code="EXTERNAL_VOLUME_RELATIVE_ROOT_INVALID",
    )
    return _require_plain_path_chain(
        mount,
        relative_root,
        final_kind="directory",
        code="EXTERNAL_VOLUME_ROOT_INVALID",
    )


def resolve_storage_root(
    repo_root: Path,
    row: dict[str, Any],
) -> Path:
    locator = row["locator"]
    kind = locator["kind"]
    if kind == "repository":
        path = repo_root
    elif kind == "repository_sibling_suffix":
        suffix = locator["suffix"]
        if (
            not isinstance(suffix, str)
            or not suffix.startswith("_")
            or "/" in suffix
            or "\\" in suffix
        ):
            raise InventoryError("ROOT_LOCATOR_UNSAFE", row["root_id"])
        path = repo_root.parent / f"{repo_root.name}{suffix}"
    elif kind == "external_volume_uuid":
        path = _resolve_external_volume_uuid(repo_root, locator)
    else:
        raise InventoryError("ROOT_LOCATOR_UNSUPPORTED", str(kind))
    if row["required"]:
        _require_plain_directory(path, code="STORAGE_ROOT_INVALID")
    return path


def _read_registered_file(
    root: Path,
    relative: PurePosixPath,
    *,
    code: str,
) -> bytes:
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    file_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        file_flags |= os.O_NOFOLLOW

    directory_descriptors: list[int] = []
    file_descriptor: int | None = None
    try:
        root_descriptor = os.open(root, directory_flags)
        directory_descriptors.append(root_descriptor)
        for part in relative.parts[:-1]:
            descriptor = os.open(
                part,
                directory_flags,
                dir_fd=directory_descriptors[-1],
            )
            directory_descriptors.append(descriptor)
        file_descriptor = os.open(
            relative.name,
            file_flags,
            dir_fd=directory_descriptors[-1],
        )
    except OSError as exc:
        for descriptor in reversed(directory_descriptors):
            os.close(descriptor)
        raise InventoryError(code, "无法逐层安全打开登记文件") from exc

    try:
        opened = os.fstat(file_descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise InventoryError(code, "登记锚不是普通文件")
        if opened.st_nlink != 1:
            raise InventoryError(code, "拒绝硬链接文件")
        if opened.st_size > MAX_REGISTERED_FILE_BYTES:
            raise InventoryError(code, "登记文件超过 5 MiB 上限")
        opened_identity = _identity(opened)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_REGISTERED_FILE_BYTES:
                raise InventoryError(code, "登记文件超过 5 MiB 上限")
            chunks.append(chunk)
        if _identity(os.fstat(file_descriptor)) != opened_identity:
            raise InventoryError(code, "登记文件在读取时发生漂移")

        verification_descriptors: list[int] = []
        verification_file: int | None = None
        try:
            verification_root = os.open(root, directory_flags)
            verification_descriptors.append(verification_root)
            if _identity(os.fstat(verification_root)) != _identity(
                os.fstat(directory_descriptors[0])
            ):
                raise InventoryError(code, "登记根目录在读取时被替换")
            for index, part in enumerate(relative.parts[:-1], start=1):
                descriptor = os.open(
                    part,
                    directory_flags,
                    dir_fd=verification_descriptors[-1],
                )
                verification_descriptors.append(descriptor)
                if _identity(os.fstat(descriptor)) != _identity(
                    os.fstat(directory_descriptors[index])
                ):
                    raise InventoryError(code, "登记父目录在读取时被替换")
            verification_file = os.open(
                relative.name,
                file_flags,
                dir_fd=verification_descriptors[-1],
            )
            if _identity(os.fstat(verification_file)) != opened_identity:
                raise InventoryError(code, "登记文件在读取时被替换")
        except OSError as exc:
            raise InventoryError(code, "登记路径在读取后无法安全复核") from exc
        finally:
            if verification_file is not None:
                os.close(verification_file)
            for descriptor in reversed(verification_descriptors):
                os.close(descriptor)
        return b"".join(chunks)
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(directory_descriptors):
            os.close(descriptor)


def _read_registered_json(
    root: Path,
    relative: PurePosixPath,
    *,
    code: str,
) -> dict[str, Any]:
    try:
        raw = _read_registered_file(root, relative, code=code)
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InventoryError(code, "JSON 无法读取或解析") from exc
    if not isinstance(value, dict):
        raise InventoryError(code, "JSON 顶层必须是对象")
    return value


def _validate_schema(
    value: dict[str, Any],
    schema: dict[str, Any],
    *,
    code: str,
) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(value)
    except (SchemaError, ValidationError) as exc:
        raise InventoryError(code, exc.message) from exc


def load_registry(repo_root: Path) -> dict[str, Any]:
    registry = _read_registered_json(
        repo_root,
        PurePosixPath(REGISTRY_RELATIVE.as_posix()),
        code="REGISTRY_JSON_INVALID",
    )
    schema = _read_registered_json(
        repo_root,
        PurePosixPath(REGISTRY_SCHEMA_RELATIVE.as_posix()),
        code="REGISTRY_SCHEMA_INVALID",
    )
    _validate_schema(registry, schema, code="REGISTRY_CONTRACT_INVALID")
    _validate_registry_relations(registry)
    return registry


def _validate_registry_relations(registry: dict[str, Any]) -> None:
    roots = registry["storage_roots"]
    objects = registry["objects"]
    conflicts = registry["known_conflicts"]
    root_ids = [row["root_id"] for row in roots]
    artifact_ids = [row["artifact_id"] for row in objects]
    conflict_ids = [row["conflict_id"] for row in conflicts]

    if root_ids != sorted(root_ids):
        raise InventoryError(
            "REGISTRY_ORDER_INVALID", "storage_roots 必须按 root_id 排序"
        )
    if artifact_ids != sorted(artifact_ids):
        raise InventoryError(
            "REGISTRY_ORDER_INVALID", "objects 必须按 artifact_id 排序"
        )
    if conflict_ids != sorted(conflict_ids):
        raise InventoryError(
            "REGISTRY_ORDER_INVALID",
            "known_conflicts 必须按 conflict_id 排序",
        )
    for label, values in (
        ("root_id", root_ids),
        ("artifact_id", artifact_ids),
        ("conflict_id", conflict_ids),
    ):
        folded = [value.casefold() for value in values]
        if len(folded) != len(set(folded)):
            raise InventoryError("REGISTRY_ID_CONFLICT", f"{label} 重复")

    root_set = set(root_ids)
    roots_by_id = {row["root_id"]: row for row in roots}
    artifact_set = set(artifact_ids)
    seen_paths: set[tuple[str, str]] = set()
    seen_manifests: set[tuple[str, str]] = set()
    for row in objects:
        if row["root_id"] not in root_set:
            raise InventoryError(
                "REGISTRY_ROOT_UNKNOWN",
                f"{row['artifact_id']} 指向未知 root_id",
            )
        relative = _safe_relative_path(
            row["relative_path"],
            code="REGISTRY_OBJECT_PATH_UNSAFE",
        ).as_posix()
        key = (row["root_id"].casefold(), relative.casefold())
        if key in seen_paths:
            raise InventoryError(
                "REGISTRY_PATH_CONFLICT",
                f"{row['artifact_id']} 与其他对象路径冲突",
            )
        seen_paths.add(key)
        for anchor in row["identity_anchors"]:
            _safe_relative_path(
                anchor["relative_path"],
                code="REGISTRY_ANCHOR_PATH_UNSAFE",
            )
        manifest = row["manifest"]
        representation = row.get("representation")
        root_row = roots_by_id[row["root_id"]]
        if representation is not None:
            if (
                root_row["locator"]["kind"] != "external_volume_uuid"
                or root_row["failure_domain"] != "different_physical_device"
                or row["recoverability"]
                != "package_integrity_proven_different_physical_device"
            ):
                raise InventoryError(
                    "ARCHIVE_REPRESENTATION_ROOT_INVALID",
                    f"{row['artifact_id']} 的 tar 表示必须位于已登记的不同物理设备",
                )
        elif root_row["locator"]["kind"] == "external_volume_uuid":
            raise InventoryError(
                "ARCHIVE_REPRESENTATION_MISSING",
                f"{row['artifact_id']} 的外置卷对象缺少物理表示合同",
            )
        if manifest is not None:
            manifest_relative = _safe_relative_path(
                manifest["relative_path"],
                code="REGISTRY_MANIFEST_PATH_UNSAFE",
            ).as_posix()
            manifest_key = (
                row["root_id"].casefold(),
                f"{relative}/{manifest_relative}".casefold(),
            )
            if manifest_key in seen_manifests:
                raise InventoryError(
                    "REGISTRY_MANIFEST_CONFLICT",
                    "两个对象登记了同一份清单",
                )
            seen_manifests.add(manifest_key)
            if (
                row["verification_level"] == "cryptographically_sealed"
                and manifest["entry_sha256_field"] is None
            ):
                raise InventoryError(
                    "REGISTRY_VERIFICATION_OVERCLAIM",
                    f"{row['artifact_id']} 缺少逐文件 SHA 字段",
                )
        elif row["verification_level"] in {
            "manifest_only",
            "cryptographically_sealed",
        }:
            raise InventoryError(
                "REGISTRY_MANIFEST_MISSING",
                f"{row['artifact_id']} 的验证等级需要清单",
            )
    for row in conflicts:
        unknown = set(row["artifact_ids"]) - artifact_set
        if unknown:
            raise InventoryError(
                "REGISTRY_CONFLICT_REFERENCE_UNKNOWN",
                f"{row['conflict_id']} 引用了未知对象",
            )


def _resolve_roots(
    repo_root: Path,
    registry: dict[str, Any],
) -> dict[str, Path]:
    _require_plain_directory(repo_root, code="REPOSITORY_ROOT_INVALID")
    resolved: dict[str, Path] = {}
    for row in registry["storage_roots"]:
        resolved[row["root_id"]] = resolve_storage_root(repo_root, row)
    return resolved


def _verify_activation_receipt(
    repo_root: Path,
    registry: dict[str, Any],
) -> dict[str, Any] | None:
    size_policy = registry["size_policy"]
    if size_policy["mode"] != "hard_limit":
        return None
    if (
        size_policy["hard_limit_activation"]
        == "blocked_in_s06a_until_separate_payload_validator"
    ):
        raise InventoryError(
            "HARD_LIMIT_NOT_AVAILABLE_IN_S06A",
            "当前只读扫描器不遍历外置 payload，不能签发 10MB 硬上限",
        )
    receipt = size_policy["activation_receipt"]
    if not isinstance(receipt, dict):
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "缺少迁移完成票",
        )
    relative = _safe_relative_path(
        receipt["path"],
        code="HARD_LIMIT_ACTIVATION_INVALID",
    )
    raw = _read_registered_file(
        repo_root,
        relative,
        code="HARD_LIMIT_ACTIVATION_INVALID",
    )
    if _sha256_bytes(raw) != receipt["sha256"]:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "迁移完成票 SHA 漂移",
        )
    if _read_git_index_path_bytes(repo_root, relative) != raw:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "迁移完成票必须与 Git 索引中的字节一致",
        )
    registry_relative = PurePosixPath(REGISTRY_RELATIVE.as_posix())
    registry_raw = _read_registered_file(
        repo_root,
        registry_relative,
        code="HARD_LIMIT_ACTIVATION_INVALID",
    )
    if _read_git_index_path_bytes(repo_root, registry_relative) != registry_raw:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "硬上限登记册必须与 Git 索引中的字节一致",
        )
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "迁移完成票不是合法 JSON",
        ) from exc
    if not isinstance(value, dict):
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "迁移完成票顶层必须是对象",
        )
    schema = _read_registered_json(
        repo_root,
        PurePosixPath(MIGRATION_RECEIPT_SCHEMA_RELATIVE.as_posix()),
        code="HARD_LIMIT_ACTIVATION_SCHEMA_INVALID",
    )
    _validate_schema(
        value,
        schema,
        code="HARD_LIMIT_ACTIVATION_INVALID",
    )
    if value["registry_id"] != registry["registry_id"]:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "迁移完成票绑定了另一份登记册",
        )
    known_artifact_ids = {row["artifact_id"] for row in registry["objects"]}
    unknown = set(value["moved_artifact_ids"]) - known_artifact_ids
    if unknown:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "迁移完成票含未登记对象",
        )
    objects_by_id = {row["artifact_id"]: row for row in registry["objects"]}
    roots_by_id = {row["root_id"]: row for row in registry["storage_roots"]}
    for artifact_id in value["moved_artifact_ids"]:
        row = objects_by_id[artifact_id]
        root = roots_by_id[row["root_id"]]
        if (
            row["category"] != "repository_experiment"
            or root["role"] != "external_archive"
            or row["externalization"] != "already_external"
            or row["consumer_closure"] != "verified"
            or row["status"] not in {"frozen", "sealed"}
            or row["verification_level"] != "cryptographically_sealed"
            or row["manifest"] is None
            or row["manifest"]["entry_sha256_field"] is None
        ):
            raise InventoryError(
                "HARD_LIMIT_ACTIVATION_INVALID",
                f"{artifact_id} 还不是消费者收口后的外置封签对象",
            )
    pointer_rows = value["repository_pointers"]
    pointer_ids = [row["artifact_id"] for row in pointer_rows]
    if len(pointer_ids) != len(set(pointer_ids)) or set(pointer_ids) != set(
        value["moved_artifact_ids"]
    ):
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "主仓指针证据与迁移对象不一一对应",
        )
    for pointer in pointer_rows:
        pointer_relative = _safe_relative_path(
            pointer["path"],
            code="HARD_LIMIT_ACTIVATION_INVALID",
        )
        pointer_raw = _read_registered_file(
            repo_root,
            pointer_relative,
            code="HARD_LIMIT_ACTIVATION_INVALID",
        )
        if _sha256_bytes(pointer_raw) != pointer["sha256"]:
            raise InventoryError(
                "HARD_LIMIT_ACTIVATION_INVALID",
                f"{pointer['artifact_id']} 的主仓指针 SHA 漂移",
            )
        if _read_git_index_path_bytes(repo_root, pointer_relative) != pointer_raw:
            raise InventoryError(
                "HARD_LIMIT_ACTIVATION_INVALID",
                f"{pointer['artifact_id']} 的主仓指针未固定在 Git 索引",
            )
    return value


def _verify_objects(
    roots: dict[str, Path],
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for row in registry["objects"]:
        root = roots[row["root_id"]]
        object_relative = _safe_relative_path(
            row["relative_path"],
            code="OBJECT_PATH_UNSAFE",
        )
        _require_plain_path_chain(
            root,
            object_relative,
            final_kind="directory",
            code="OBJECT_PATH_INVALID",
        )

        representation = row.get("representation")
        if representation is not None:
            if representation["original_tree_manifest_sha256"] != row["manifest"][
                "sha256"
            ]:
                raise InventoryError(
                    "ARCHIVE_REPRESENTATION_MANIFEST_MISMATCH",
                    row["artifact_id"],
                )
            container_relative = _safe_relative_path(
                representation["container_relative_path"],
                code="ARCHIVE_CONTAINER_PATH_UNSAFE",
            )
            container = _require_plain_path_chain(
                root,
                PurePosixPath(*(object_relative.parts + container_relative.parts)),
                final_kind="file",
                code="ARCHIVE_CONTAINER_INVALID",
            )
            if container.stat().st_size != representation["container_bytes"]:
                raise InventoryError(
                    "ARCHIVE_CONTAINER_SIZE_MISMATCH",
                    row["artifact_id"],
                )

        for anchor in row["identity_anchors"]:
            anchor_relative = _safe_relative_path(
                anchor["relative_path"],
                code="ANCHOR_PATH_UNSAFE",
            )
            combined = PurePosixPath(*(object_relative.parts + anchor_relative.parts))
            raw = _read_registered_file(
                root,
                combined,
                code="ANCHOR_SNAPSHOT_INVALID",
            )
            if _sha256_bytes(raw) != anchor["sha256"]:
                raise InventoryError(
                    "ANCHOR_SNAPSHOT_INVALID",
                    f"{row['artifact_id']} 的身份锚 SHA 漂移",
                )

        manifest_checked = False
        manifest = row["manifest"]
        if manifest is not None:
            manifest_relative = _safe_relative_path(
                manifest["relative_path"],
                code="MANIFEST_PATH_UNSAFE",
            )
            combined = PurePosixPath(*(object_relative.parts + manifest_relative.parts))
            raw = _read_registered_file(
                root,
                combined,
                code="MANIFEST_SNAPSHOT_INVALID",
            )
            if _sha256_bytes(raw) != manifest["sha256"]:
                raise InventoryError(
                    "MANIFEST_SNAPSHOT_INVALID",
                    f"{row['artifact_id']} 的清单 SHA 漂移",
                )
            try:
                value = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise InventoryError(
                    "MANIFEST_JSON_INVALID",
                    row["artifact_id"],
                ) from exc
            if not isinstance(value, dict):
                raise InventoryError(
                    "MANIFEST_JSON_INVALID",
                    f"{row['artifact_id']} 顶层不是对象",
                )
            if representation is not None:
                if (
                    value.get("aggregate_sha256")
                    != representation["original_aggregate_sha256"]
                ):
                    raise InventoryError(
                        "ARCHIVE_REPRESENTATION_AGGREGATE_MISMATCH",
                        row["artifact_id"],
                    )
            entries = value.get(manifest["entries_field"])
            if not isinstance(entries, list):
                raise InventoryError(
                    "MANIFEST_ENTRY_SET_INVALID",
                    f"{row['artifact_id']} 缺少登记数组",
                )
            if len(entries) != manifest["expected_entry_count"]:
                raise InventoryError(
                    "MANIFEST_ENTRY_COUNT_DRIFT",
                    f"{row['artifact_id']} 条目数漂移",
                )
            entry_sha_field = manifest["entry_sha256_field"]
            if entry_sha_field is not None:
                entry_path_field = manifest["entry_path_field"]
                seen_entry_paths: set[str] = set()
                for entry in entries:
                    if (
                        not isinstance(entry, dict)
                        or not isinstance(entry.get(entry_sha_field), str)
                        or len(entry[entry_sha_field]) != 64
                        or any(
                            character not in "0123456789abcdef"
                            for character in entry[entry_sha_field]
                        )
                    ):
                        raise InventoryError(
                            "MANIFEST_ENTRY_DIGEST_INVALID",
                            f"{row['artifact_id']} 缺少合法逐项 SHA",
                        )
                    try:
                        entry_path = _safe_relative_path(
                            entry.get(entry_path_field),
                            code="MANIFEST_ENTRY_PATH_INVALID",
                        ).as_posix()
                    except InventoryError as exc:
                        raise InventoryError(
                            "MANIFEST_ENTRY_PATH_INVALID",
                            f"{row['artifact_id']} 含不合法逐项路径",
                        ) from exc
                    folded_path = entry_path.casefold()
                    if folded_path in seen_entry_paths:
                        raise InventoryError(
                            "MANIFEST_ENTRY_PATH_CONFLICT",
                            f"{row['artifact_id']} 含重复逐项路径",
                        )
                    seen_entry_paths.add(folded_path)
            manifest_checked = True

        summaries.append(
            {
                "artifact_id": row["artifact_id"],
                "root_id": row["root_id"],
                "status": row["status"],
                "verification_level": row["verification_level"],
                "recoverability": row["recoverability"],
                "manifest_checked": manifest_checked,
                "anchor_count": len(row["identity_anchors"]),
            }
        )
    return summaries


def measure_git_index_details(repo_root: Path) -> dict[str, Any]:
    """Measure tracked blobs once and retain the path-to-size mapping."""

    try:
        listed = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--stage", "-z"],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InventoryError(
            "GIT_INDEX_MEASUREMENT_INVALID",
            "无法读取 Git 索引",
        ) from exc

    indexed_rows: list[tuple[str, str]] = []
    for record in listed.split(b"\0"):
        if not record:
            continue
        try:
            header, path_bytes = record.split(b"\t", 1)
            mode, object_id, stage = header.decode("ascii").split(" ")
            path = path_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise InventoryError(
                "GIT_INDEX_MEASUREMENT_INVALID",
                "Git 索引记录无法解析",
            ) from exc
        if stage != "0" or mode == "160000":
            raise InventoryError(
                "GIT_INDEX_MEASUREMENT_INVALID",
                "索引含未合并条目或子模块",
            )
        indexed_rows.append((path, object_id))

    unique_ids = sorted({object_id for _path, object_id in indexed_rows})
    if not unique_ids:
        return {
            "tracked_path_count": 0,
            "tracked_bytes": 0,
            "entries": [],
        }
    query = ("\n".join(unique_ids) + "\n").encode("ascii")
    try:
        inspected = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "cat-file",
                "--batch-check=%(objectname) %(objecttype) %(objectsize)",
            ],
            input=query,
            check=True,
            capture_output=True,
        ).stdout.decode("ascii")
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        raise InventoryError(
            "GIT_INDEX_MEASUREMENT_INVALID",
            "无法读取索引对象大小",
        ) from exc

    sizes: dict[str, int] = {}
    for line in inspected.splitlines():
        try:
            object_id, object_type, size_text = line.split(" ")
            size = int(size_text)
        except ValueError as exc:
            raise InventoryError(
                "GIT_INDEX_MEASUREMENT_INVALID",
                "Git 对象大小无法解析",
            ) from exc
        if object_type != "blob":
            raise InventoryError(
                "GIT_INDEX_MEASUREMENT_INVALID",
                "跟踪路径不是普通 blob",
            )
        sizes[object_id] = size
    if set(sizes) != set(unique_ids):
        raise InventoryError(
            "GIT_INDEX_MEASUREMENT_INVALID",
            "Git 对象集合不完整",
        )
    entries = [
        {
            "path": path,
            "bytes": sizes[object_id],
        }
        for path, object_id in indexed_rows
    ]
    return {
        "tracked_path_count": len(entries),
        "tracked_bytes": sum(row["bytes"] for row in entries),
        "entries": entries,
    }


def measure_git_index(repo_root: Path) -> tuple[int, int]:
    details = measure_git_index_details(repo_root)
    return details["tracked_path_count"], details["tracked_bytes"]


def _read_git_index_path_bytes(
    repo_root: Path,
    relative: PurePosixPath,
) -> bytes:
    try:
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "ls-files",
                "--stage",
                "-z",
                "--",
                relative.as_posix(),
            ],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "无法读取 Git 索引证据",
        ) from exc
    records = [record for record in listed.split(b"\0") if record]
    if len(records) != 1:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            f"{relative.as_posix()} 没有唯一的 Git 索引身份",
        )
    try:
        header, indexed_path = records[0].split(b"\t", 1)
        _mode, object_id, stage = header.decode("ascii").split(" ")
        decoded_path = indexed_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "Git 索引证据无法解析",
        ) from exc
    if stage != "0" or decoded_path != relative.as_posix():
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "Git 索引证据不是唯一 stage 0 路径",
        )
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "blob", object_id],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "Git 索引对象无法读取",
        ) from exc


def _validate_report(repo_root: Path, report: dict[str, Any]) -> None:
    _validate_report_relations(report)
    schema = _read_registered_json(
        repo_root,
        PurePosixPath(REPORT_SCHEMA_RELATIVE.as_posix()),
        code="REPORT_SCHEMA_INVALID",
    )
    _validate_schema(report, schema, code="REPORT_CONTRACT_INVALID")


def _validate_report_relations(report: dict[str, Any]) -> None:
    inventory = report["git_inventory"]
    expected_target_met = inventory["tracked_bytes"] <= inventory["target_bytes"]
    if inventory["target_met"] is not expected_target_met:
        raise InventoryError(
            "REPORT_RELATION_INVALID",
            "target_met 与体积读数不一致",
        )
    expected_hard_limit = inventory["active_gate"] == "hard_limit"
    if inventory["hard_limit_active"] is not expected_hard_limit:
        raise InventoryError(
            "REPORT_RELATION_INVALID",
            "hard_limit_active 与当前闸不一致",
        )
    expected_gate_passed = inventory["tracked_bytes"] <= inventory["active_limit_bytes"]
    if inventory["active_gate_passed"] is not expected_gate_passed:
        raise InventoryError(
            "REPORT_RELATION_INVALID",
            "active_gate_passed 与当前上限不一致",
        )
    expected_status = "PASS" if inventory["active_gate_passed"] else "BLOCKED"
    if report["status"] != expected_status:
        raise InventoryError(
            "REPORT_RELATION_INVALID",
            "status 与当前体积闸不一致",
        )
    expected_blockers = (
        [] if inventory["active_gate_passed"] else ["active_size_gate_passed"]
    )
    if report["blockers"] != expected_blockers:
        raise InventoryError(
            "REPORT_RELATION_INVALID",
            "blockers 与当前体积闸不一致",
        )
    checks = report["checks"]
    check_ids = [row["check_id"] for row in checks]
    if len(check_ids) != len(set(check_ids)):
        raise InventoryError("REPORT_RELATION_INVALID", "检查编号重复")
    active_checks = [
        row for row in checks if row["check_id"] == "active_size_gate_passed"
    ]
    if (
        len(active_checks) != 1
        or active_checks[0]["passed"] is not inventory["active_gate_passed"]
    ):
        raise InventoryError(
            "REPORT_RELATION_INVALID",
            "体积检查项与汇总不一致",
        )


def scan_with_git_index_details(
    repo_root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_registry(repo_root)
    roots = _resolve_roots(repo_root, registry)
    activation_receipt = _verify_activation_receipt(repo_root, registry)
    object_summaries = _verify_objects(roots, registry)
    git_details = measure_git_index_details(repo_root)
    tracked_path_count = git_details["tracked_path_count"]
    tracked_bytes = git_details["tracked_bytes"]
    if (
        activation_receipt is not None
        and activation_receipt["tracked_bytes"] != tracked_bytes
    ):
        raise InventoryError(
            "HARD_LIMIT_ACTIVATION_INVALID",
            "迁移完成票体积与当前 Git 索引不一致",
        )

    size_policy = registry["size_policy"]
    active_limit = size_policy["active_limit_bytes"]
    target_bytes = size_policy["target_bytes"]
    gate_passed = tracked_bytes <= active_limit
    blockers = [] if gate_passed else ["active_size_gate_passed"]
    checks = [
        {"check_id": "registry_contract_valid", "passed": True},
        {"check_id": "root_locator_safe", "passed": True},
        {"check_id": "registered_object_set_exact", "passed": True},
        {"check_id": "registered_snapshot_stable", "passed": True},
        {"check_id": "git_index_measurement_stable", "passed": True},
        {"check_id": "active_size_gate_passed", "passed": gate_passed},
        {"check_id": "readonly_capability_respected", "passed": True},
    ]
    report: dict[str, Any] = {
        "contract_version": "repo-slim-inventory-report-v1",
        "status": "PASS" if not blockers else "BLOCKED",
        "registry_id": registry["registry_id"],
        "claim": {
            "inventory_complete_for_registered_objects": True,
            "external_payload_verified": False,
            "recoverability_proven": False,
            "migration_performed": False,
        },
        "roots": [
            {
                "root_id": row["root_id"],
                "role": row["role"],
                "resolved": True,
            }
            for row in registry["storage_roots"]
        ],
        "git_inventory": {
            "metric": size_policy["metric"],
            "tracked_path_count": tracked_path_count,
            "tracked_bytes": tracked_bytes,
            "pre_s06a_baseline_bytes": size_policy["pre_s06a_baseline_bytes"],
            "active_limit_bytes": active_limit,
            "target_bytes": target_bytes,
            "target_met": tracked_bytes <= target_bytes,
            "active_gate": size_policy["mode"],
            "active_gate_passed": gate_passed,
            "hard_limit_active": size_policy["mode"] == "hard_limit",
        },
        "objects": object_summaries,
        "conflicts": {
            "known_open_ids": [
                row["conflict_id"] for row in registry["known_conflicts"]
            ],
            "blocking_ids": [],
        },
        "blockers": blockers,
        "checks": checks,
    }
    _validate_report(repo_root, report)
    return report, git_details


def scan(repo_root: Path = ROOT) -> dict[str, Any]:
    report, _git_details = scan_with_git_index_details(repo_root)
    return report


def command_check(_args: argparse.Namespace) -> int:
    report = scan(ROOT)
    inventory = report["git_inventory"]
    print(
        f"{report['status']}: Git 跟踪体积 {inventory['tracked_bytes']} 字节；"
        f"当前上限 {inventory['active_limit_bytes']} 字节；"
        f"10MB 目标 {'已达到' if inventory['target_met'] else '尚未达到'}；"
        f"登记中的未决冲突 {len(report['conflicts']['known_open_ids'])} 项。"
    )
    return 0 if report["status"] == "PASS" else 1


def command_report(_args: argparse.Namespace) -> int:
    report = scan(ROOT)
    sys.stdout.buffer.write(_json_bytes(report))
    return 0 if report["status"] == "PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读核对仓库瘦身登记、固定清单与 Git 跟踪体积。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="输出一行人看结论")
    check_parser.set_defaults(handler=command_check)
    report_parser = subparsers.add_parser("report", help="输出确定性 JSON 报告")
    report_parser.set_defaults(handler=command_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except InventoryError as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
