#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tarfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Sequence

if __package__:
    from tools import repo_slim_inventory as inventory
else:
    import repo_slim_inventory as inventory


ROOT = Path(__file__).resolve().parents[1]
POLICY_RELATIVE = Path("governance/external_payload_validation_policy.json")
POLICY_SCHEMA_RELATIVE = Path(
    "governance/contracts/external_payload_validation_policy_v1.schema.json"
)
REPORT_SCHEMA_RELATIVE = Path(
    "governance/contracts/external_payload_verification_report_v1.schema.json"
)
INVENTORY_HELPER_RELATIVE = Path("tools/repo_slim_inventory.py")
READ_CHUNK_BYTES = 1024 * 1024
MAX_DIRECTORY_DEPTH = 64

Identity = tuple[int, int, int, int, int, int, int]


class PayloadValidationError(RuntimeError):
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


def _identity(value: os.stat_result) -> Identity:
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
    try:
        return inventory._safe_relative_path(value, code=code)
    except inventory.InventoryError as exc:
        raise PayloadValidationError(code, exc.detail) from exc


def _directory_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _file_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _require_platform_capabilities() -> None:
    required = {
        "O_NOFOLLOW": hasattr(os, "O_NOFOLLOW"),
        "O_DIRECTORY": hasattr(os, "O_DIRECTORY"),
        "open_dir_fd": os.open in getattr(os, "supports_dir_fd", set()),
        "stat_dir_fd": os.stat in getattr(os, "supports_dir_fd", set()),
        "stat_no_follow": os.stat in getattr(os, "supports_follow_symlinks", set()),
        "listdir_fd": os.listdir in getattr(os, "supports_fd", set()),
    }
    missing = sorted(name for name, available in required.items() if not available)
    if missing:
        raise PayloadValidationError(
            "PAYLOAD_PLATFORM_CAPABILITY_MISSING",
            "缺少安全逐层读取能力：" + ", ".join(missing),
        )


def _assert_plain_directory(
    info: os.stat_result,
    *,
    root_device: int,
    code: str,
) -> None:
    if not stat.S_ISDIR(info.st_mode):
        raise PayloadValidationError(code, "路径不是普通目录")
    if info.st_dev != root_device:
        raise PayloadValidationError(code, "路径跨越了登记存储设备")


def _assert_plain_file(
    info: os.stat_result,
    *,
    root_device: int,
    code: str,
) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise PayloadValidationError(code, "payload 含非普通文件")
    if info.st_nlink != 1:
        raise PayloadValidationError(code, "payload 含硬链接文件")
    if info.st_dev != root_device:
        raise PayloadValidationError(code, "payload 文件跨越了登记存储设备")


@contextmanager
def _open_directory_chain(
    root: Path,
    relative: PurePosixPath,
) -> Iterator[tuple[int, int, tuple[Identity, ...]]]:
    descriptors: list[int] = []
    try:
        try:
            root_descriptor = os.open(root, _directory_flags())
        except OSError as exc:
            raise PayloadValidationError(
                "PAYLOAD_ROOT_INVALID",
                "无法安全打开登记存储根",
            ) from exc
        descriptors.append(root_descriptor)
        root_info = os.fstat(root_descriptor)
        if not stat.S_ISDIR(root_info.st_mode):
            raise PayloadValidationError(
                "PAYLOAD_ROOT_INVALID",
                "登记存储根不是普通目录",
            )
        root_device = root_info.st_dev
        identities = [_identity(root_info)]

        for part in relative.parts:
            try:
                descriptor = os.open(
                    part,
                    _directory_flags(),
                    dir_fd=descriptors[-1],
                )
            except OSError as exc:
                raise PayloadValidationError(
                    "PAYLOAD_ROOT_INVALID",
                    "对象或 payload 根无法逐层安全打开",
                ) from exc
            info = os.fstat(descriptor)
            _assert_plain_directory(
                info,
                root_device=root_device,
                code="PAYLOAD_ROOT_INVALID",
            )
            descriptors.append(descriptor)
            identities.append(_identity(info))

        yield descriptors[-1], root_device, tuple(identities)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _verify_directory_chain(
    root: Path,
    relative: PurePosixPath,
    expected_identities: tuple[Identity, ...],
) -> None:
    with _open_directory_chain(root, relative) as (
        _payload_descriptor,
        _root_device,
        actual_identities,
    ):
        if actual_identities != expected_identities:
            raise PayloadValidationError(
                "PAYLOAD_SNAPSHOT_DRIFT",
                "登记根、对象目录或 payload 根在核验中被替换",
            )


def _snapshot_payload_tree(
    payload_descriptor: int,
    *,
    root_device: int,
) -> dict[str, Identity]:
    files: dict[str, Identity] = {}
    folded_paths: set[str] = set()

    def walk(
        directory_descriptor: int,
        parent: PurePosixPath | None,
        depth: int,
    ) -> None:
        if depth > MAX_DIRECTORY_DEPTH:
            raise PayloadValidationError(
                "PAYLOAD_TREE_INVALID",
                "payload 目录层级超过 64 层",
            )
        try:
            names = sorted(os.listdir(directory_descriptor))
        except OSError as exc:
            raise PayloadValidationError(
                "PAYLOAD_TREE_INVALID",
                "无法读取 payload 目录",
            ) from exc
        for name in names:
            relative = PurePosixPath(name) if parent is None else parent / name
            safe_relative = _safe_relative_path(
                relative.as_posix(),
                code="PAYLOAD_ENTRY_PATH_INVALID",
            )
            try:
                info = os.stat(
                    name,
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise PayloadValidationError(
                    "PAYLOAD_SNAPSHOT_DRIFT",
                    "payload 条目在枚举中消失",
                ) from exc
            if stat.S_ISLNK(info.st_mode):
                raise PayloadValidationError(
                    "PAYLOAD_TREE_INVALID",
                    "payload 含符号链接",
                )
            if stat.S_ISDIR(info.st_mode):
                if info.st_dev != root_device:
                    raise PayloadValidationError(
                        "PAYLOAD_TREE_INVALID",
                        "payload 子目录跨越了登记存储设备",
                    )
                try:
                    child_descriptor = os.open(
                        name,
                        _directory_flags(),
                        dir_fd=directory_descriptor,
                    )
                except OSError as exc:
                    raise PayloadValidationError(
                        "PAYLOAD_SNAPSHOT_DRIFT",
                        "payload 子目录无法安全打开",
                    ) from exc
                try:
                    opened = os.fstat(child_descriptor)
                    _assert_plain_directory(
                        opened,
                        root_device=root_device,
                        code="PAYLOAD_TREE_INVALID",
                    )
                    if _identity(opened) != _identity(info):
                        raise PayloadValidationError(
                            "PAYLOAD_SNAPSHOT_DRIFT",
                            "payload 子目录在枚举后被替换",
                        )
                    walk(child_descriptor, safe_relative, depth + 1)
                finally:
                    os.close(child_descriptor)
                continue

            _assert_plain_file(
                info,
                root_device=root_device,
                code="PAYLOAD_TREE_INVALID",
            )
            normalized = safe_relative.as_posix()
            folded = normalized.casefold()
            if folded in folded_paths:
                raise PayloadValidationError(
                    "PAYLOAD_PATH_CONFLICT",
                    "payload 含大小写折叠后重复的文件路径",
                )
            folded_paths.add(folded)
            files[normalized] = _identity(info)

    walk(payload_descriptor, None, 1)
    return files


def _hash_registered_payload_file(
    payload_descriptor: int,
    relative: PurePosixPath,
    *,
    expected_identity: Identity,
    expected_size: int,
    root_device: int,
) -> str:
    directory_descriptors: list[int] = []
    file_descriptor: int | None = None
    try:
        directory_descriptors.append(os.dup(payload_descriptor))
        for part in relative.parts[:-1]:
            try:
                descriptor = os.open(
                    part,
                    _directory_flags(),
                    dir_fd=directory_descriptors[-1],
                )
            except OSError as exc:
                raise PayloadValidationError(
                    "PAYLOAD_SNAPSHOT_DRIFT",
                    "payload 文件父目录无法安全打开",
                ) from exc
            info = os.fstat(descriptor)
            _assert_plain_directory(
                info,
                root_device=root_device,
                code="PAYLOAD_TREE_INVALID",
            )
            directory_descriptors.append(descriptor)

        try:
            file_descriptor = os.open(
                relative.name,
                _file_flags(),
                dir_fd=directory_descriptors[-1],
            )
        except OSError as exc:
            raise PayloadValidationError(
                "PAYLOAD_FILE_MISSING",
                "清单文件不存在或无法安全打开",
            ) from exc
        opened = os.fstat(file_descriptor)
        _assert_plain_file(
            opened,
            root_device=root_device,
            code="PAYLOAD_TREE_INVALID",
        )
        opened_identity = _identity(opened)
        if opened_identity != expected_identity:
            raise PayloadValidationError(
                "PAYLOAD_SNAPSHOT_DRIFT",
                "payload 文件在枚举后被替换",
            )
        if opened.st_size != expected_size:
            raise PayloadValidationError(
                "PAYLOAD_SIZE_MISMATCH",
                "payload 文件大小与清单不一致",
            )

        digest = hashlib.sha256()
        while True:
            chunk = os.read(file_descriptor, READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
        if _identity(os.fstat(file_descriptor)) != opened_identity:
            raise PayloadValidationError(
                "PAYLOAD_SNAPSHOT_DRIFT",
                "payload 文件在读取时发生变化",
            )

        verification_directories: list[int] = [os.dup(payload_descriptor)]
        verification_file: int | None = None
        try:
            if _identity(os.fstat(verification_directories[0])) != _identity(
                os.fstat(directory_descriptors[0])
            ):
                raise PayloadValidationError(
                    "PAYLOAD_SNAPSHOT_DRIFT",
                    "payload 根在读取时被替换",
                )
            for index, part in enumerate(relative.parts[:-1], start=1):
                descriptor = os.open(
                    part,
                    _directory_flags(),
                    dir_fd=verification_directories[-1],
                )
                verification_directories.append(descriptor)
                if _identity(os.fstat(descriptor)) != _identity(
                    os.fstat(directory_descriptors[index])
                ):
                    raise PayloadValidationError(
                        "PAYLOAD_SNAPSHOT_DRIFT",
                        "payload 文件父目录在读取时被替换",
                    )
            verification_file = os.open(
                relative.name,
                _file_flags(),
                dir_fd=verification_directories[-1],
            )
            if _identity(os.fstat(verification_file)) != opened_identity:
                raise PayloadValidationError(
                    "PAYLOAD_SNAPSHOT_DRIFT",
                    "payload 文件在读取后被替换",
                )
        except OSError as exc:
            raise PayloadValidationError(
                "PAYLOAD_SNAPSHOT_DRIFT",
                "payload 路径在读取后无法安全复核",
            ) from exc
        finally:
            if verification_file is not None:
                os.close(verification_file)
            for descriptor in reversed(verification_directories):
                os.close(descriptor)
        return digest.hexdigest()
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(directory_descriptors):
            os.close(descriptor)


def _read_json_bytes(raw: bytes, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadValidationError(code, "JSON 无法读取或解析") from exc
    if not isinstance(value, dict):
        raise PayloadValidationError(code, "JSON 顶层必须是对象")
    return value


def _load_policy(
    repo_root: Path,
) -> tuple[dict[str, Any], bytes]:
    relative = PurePosixPath(POLICY_RELATIVE.as_posix())
    raw = inventory._read_registered_file(
        repo_root,
        relative,
        code="PAYLOAD_POLICY_INVALID",
    )
    policy = _read_json_bytes(raw, code="PAYLOAD_POLICY_INVALID")
    schema = inventory._read_registered_json(
        repo_root,
        PurePosixPath(POLICY_SCHEMA_RELATIVE.as_posix()),
        code="PAYLOAD_POLICY_SCHEMA_INVALID",
    )
    inventory._validate_schema(
        policy,
        schema,
        code="PAYLOAD_POLICY_CONTRACT_INVALID",
    )
    return policy, raw


def _validate_policy_relations(
    policy: dict[str, Any],
    registry: dict[str, Any],
) -> None:
    if policy["registry_id"] != registry["registry_id"]:
        raise PayloadValidationError(
            "PAYLOAD_POLICY_REGISTRY_MISMATCH",
            "验证政策绑定了另一份外置登记册",
        )
    target_ids = [row["artifact_id"] for row in policy["targets"]]
    exclusion_ids = [row["artifact_id"] for row in policy["exclusions"]]
    if target_ids != sorted(target_ids) or exclusion_ids != sorted(exclusion_ids):
        raise PayloadValidationError(
            "PAYLOAD_POLICY_ORDER_INVALID",
            "targets 与 exclusions 必须分别按 artifact_id 排序",
        )
    folded_ids = [value.casefold() for value in target_ids + exclusion_ids]
    if len(folded_ids) != len(set(folded_ids)):
        raise PayloadValidationError(
            "PAYLOAD_POLICY_ID_CONFLICT",
            "验证目标与排除对象含重复编号",
        )

    roots = {row["root_id"]: row for row in registry["storage_roots"]}
    objects = {row["artifact_id"]: row for row in registry["objects"]}
    external_ids = {
        artifact_id
        for artifact_id, row in objects.items()
        if roots[row["root_id"]]["role"] == "external_archive"
    }
    covered_ids = set(target_ids) | set(exclusion_ids)
    if covered_ids != external_ids:
        raise PayloadValidationError(
            "PAYLOAD_POLICY_COVERAGE_INVALID",
            "验证政策没有逐件覆盖外置登记对象",
        )

    for target in policy["targets"]:
        row = objects[target["artifact_id"]]
        manifest = row["manifest"]
        if (
            row["externalization"] != "already_external"
            or row["verification_level"] != "cryptographically_sealed"
            or manifest is None
            or manifest["entry_sha256_field"] is None
            or manifest["sha256"] != target["manifest_sha256"]
        ):
            raise PayloadValidationError(
                "PAYLOAD_POLICY_TARGET_INVALID",
                f"{target['artifact_id']} 不具备逐文件 SHA 验证条件",
            )


def _resolve_target_root(
    repo_root: Path,
    registry: dict[str, Any],
    root_id: str,
) -> Path:
    roots = {row["root_id"]: row for row in registry["storage_roots"]}
    try:
        path = inventory.resolve_storage_root(repo_root, roots[root_id])
    except inventory.InventoryError as exc:
        raise PayloadValidationError(
            "PAYLOAD_TARGET_ROOT_INVALID",
            exc.detail,
        ) from exc
    return path


def _hash_plain_file(path: Path, *, expected_size: int, code: str) -> str:
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise PayloadValidationError(code, "容器不存在") from exc
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise PayloadValidationError(code, "容器必须是单链接普通文件")
    if before.st_size != expected_size:
        raise PayloadValidationError(code, "容器大小与登记不一致")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if _identity(path.lstat()) != _identity(before):
        raise PayloadValidationError(code, "容器在读取中发生漂移")
    return digest.hexdigest()


def _tar_member_name(value: str) -> str:
    while value.startswith("./"):
        value = value[2:]
    return _safe_relative_path(value, code="TAR_MEMBER_PATH_INVALID").as_posix()


def _verify_tar_representation(
    root: Path,
    object_row: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    representation = object_row.get("representation")
    if not isinstance(representation, dict) or representation.get("kind") != (
        "tar_posix_tree_v1"
    ):
        raise PayloadValidationError("ARCHIVE_REPRESENTATION_INVALID")
    if representation.get("original_aggregate_sha256") != manifest.get(
        "aggregate_sha256"
    ):
        raise PayloadValidationError("ARCHIVE_AGGREGATE_IDENTITY_MISMATCH")
    object_relative = _safe_relative_path(
        object_row["relative_path"], code="PAYLOAD_OBJECT_PATH_INVALID"
    )
    container_relative = _safe_relative_path(
        representation["container_relative_path"],
        code="ARCHIVE_CONTAINER_PATH_INVALID",
    )
    container = root.joinpath(*object_relative.parts, *container_relative.parts)
    actual_container_sha = _hash_plain_file(
        container,
        expected_size=representation["container_bytes"],
        code="ARCHIVE_CONTAINER_INVALID",
    )
    if actual_container_sha != representation["container_sha256"]:
        raise PayloadValidationError("ARCHIVE_CONTAINER_DIGEST_MISMATCH")

    expected_files = {row["path"]: row for row in manifest.get("files", [])}
    expected_links = {row["path"]: row for row in manifest.get("symlinks", [])}
    actual_files: dict[str, tarfile.TarInfo] = {}
    actual_links: dict[str, tarfile.TarInfo] = {}
    try:
        archive = tarfile.open(container, mode="r:")
    except (OSError, tarfile.TarError) as exc:
        raise PayloadValidationError("ARCHIVE_CONTAINER_TAR_INVALID") from exc
    with archive:
        seen_folded: set[str] = set()
        for member in archive:
            name = _tar_member_name(member.name)
            if member.isdir():
                continue
            if name.casefold() in seen_folded:
                raise PayloadValidationError("TAR_MEMBER_PATH_COLLISION", name)
            seen_folded.add(name.casefold())
            if member.isfile():
                actual_files[name] = member
            elif member.issym():
                actual_links[name] = member
            else:
                raise PayloadValidationError("TAR_MEMBER_TYPE_INVALID", name)
        if set(actual_files) != set(expected_files) or set(actual_links) != set(
            expected_links
        ):
            raise PayloadValidationError("TAR_MEMBER_SET_MISMATCH")
        for name, expected in expected_files.items():
            member = actual_files[name]
            if member.size != expected["bytes"]:
                raise PayloadValidationError("TAR_MEMBER_SIZE_MISMATCH", name)
            extracted = archive.extractfile(member)
            if extracted is None:
                raise PayloadValidationError("TAR_MEMBER_READ_FAILED", name)
            digest = hashlib.sha256()
            for block in iter(lambda: extracted.read(8 * 1024 * 1024), b""):
                digest.update(block)
            if digest.hexdigest() != expected["sha256"]:
                raise PayloadValidationError("TAR_MEMBER_DIGEST_MISMATCH", name)
        for name, expected in expected_links.items():
            if actual_links[name].linkname != expected.get("archive_link_target"):
                raise PayloadValidationError("TAR_SYMLINK_TARGET_MISMATCH", name)
    return {
        "symlink_count": len(expected_links),
        "total_bytes": manifest.get("source_total_bytes"),
    }


def _load_manifest_expectations(
    root: Path,
    object_row: dict[str, Any],
    target: dict[str, Any],
) -> tuple[bytes, dict[str, tuple[int, str]], str, int]:
    manifest_contract = object_row["manifest"]
    object_relative = _safe_relative_path(
        object_row["relative_path"],
        code="PAYLOAD_OBJECT_PATH_INVALID",
    )
    manifest_relative = _safe_relative_path(
        manifest_contract["relative_path"],
        code="PAYLOAD_MANIFEST_PATH_INVALID",
    )
    combined = PurePosixPath(*(object_relative.parts + manifest_relative.parts))
    raw = inventory._read_registered_file(
        root,
        combined,
        code="PAYLOAD_MANIFEST_INVALID",
    )
    manifest_sha256 = _sha256_bytes(raw)
    if (
        manifest_sha256 != manifest_contract["sha256"]
        or manifest_sha256 != target["manifest_sha256"]
    ):
        raise PayloadValidationError(
            "PAYLOAD_MANIFEST_BINDING_INVALID",
            "payload 清单 SHA 与登记或验证政策不一致",
        )
    manifest = _read_json_bytes(raw, code="PAYLOAD_MANIFEST_INVALID")
    entries = manifest.get(manifest_contract["entries_field"])
    if (
        not isinstance(entries, list)
        or len(entries) != manifest_contract["expected_entry_count"]
    ):
        raise PayloadValidationError(
            "PAYLOAD_MANIFEST_ENTRY_SET_INVALID",
            "payload 清单条目集合或条目数不合法",
        )

    path_field = manifest_contract["entry_path_field"]
    sha_field = manifest_contract["entry_sha256_field"]
    size_field = target["entry_size_field"]
    expected: dict[str, tuple[int, str]] = {}
    folded_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise PayloadValidationError(
                "PAYLOAD_MANIFEST_ENTRY_INVALID",
                "payload 清单条目不是对象",
            )
        relative = _safe_relative_path(
            entry.get(path_field),
            code="PAYLOAD_MANIFEST_ENTRY_PATH_INVALID",
        ).as_posix()
        folded = relative.casefold()
        if folded in folded_paths:
            raise PayloadValidationError(
                "PAYLOAD_MANIFEST_PATH_CONFLICT",
                "payload 清单含大小写折叠后重复路径",
            )
        folded_paths.add(folded)
        digest = entry.get(sha_field)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise PayloadValidationError(
                "PAYLOAD_MANIFEST_DIGEST_INVALID",
                "payload 清单含不合法 SHA-256",
            )
        size = entry.get(size_field)
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise PayloadValidationError(
                "PAYLOAD_MANIFEST_SIZE_INVALID",
                "payload 清单含不合法文件大小",
            )
        expected[relative] = (size, digest)

    total_bytes = sum(size for size, _digest in expected.values())
    total_files_field = target["manifest_total_files_field"]
    total_bytes_field = target["manifest_total_bytes_field"]
    if (
        manifest.get(total_files_field) != len(expected)
        or manifest.get(total_bytes_field) != total_bytes
    ):
        raise PayloadValidationError(
            "PAYLOAD_MANIFEST_TOTAL_MISMATCH",
            "payload 清单顶层合计与逐项合计不一致",
        )
    canonical_entries = [
        {
            "bytes": expected[path][0],
            "path": path,
            "sha256": expected[path][1],
        }
        for path in sorted(expected)
    ]
    entry_set_sha256 = _sha256_bytes(_json_bytes(canonical_entries))
    return raw, expected, entry_set_sha256, total_bytes


def _validate_report(
    repo_root: Path,
    report: dict[str, Any],
) -> None:
    expected_checks = [
        "policy_contract_valid",
        "artifact_allowlisted",
        "manifest_binding_valid",
        "payload_path_set_exact",
        "payload_sizes_exact",
        "payload_sha256_exact",
        "payload_snapshot_stable",
        "readonly_capability_respected",
    ]
    if report["checks"] != expected_checks:
        raise PayloadValidationError(
            "PAYLOAD_REPORT_RELATION_INVALID",
            "报告检查项与固定顺序不一致",
        )
    schema = inventory._read_registered_json(
        repo_root,
        PurePosixPath(REPORT_SCHEMA_RELATIVE.as_posix()),
        code="PAYLOAD_REPORT_SCHEMA_INVALID",
    )
    inventory._validate_schema(
        report,
        schema,
        code="PAYLOAD_REPORT_CONTRACT_INVALID",
    )
    serialized = _json_bytes(report)
    if str(repo_root).encode("utf-8") in serialized:
        raise PayloadValidationError(
            "PAYLOAD_REPORT_LEAK",
            "报告含主仓绝对路径",
        )


def validate_payload(
    artifact_id: str,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    _require_platform_capabilities()
    validator_relative = PurePosixPath("tools/external_payload_validator.py")
    validator_raw = inventory._read_registered_file(
        repo_root,
        validator_relative,
        code="PAYLOAD_VALIDATOR_SNAPSHOT_INVALID",
    )
    inventory_helper_relative = PurePosixPath(INVENTORY_HELPER_RELATIVE.as_posix())
    inventory_helper_raw = inventory._read_registered_file(
        repo_root,
        inventory_helper_relative,
        code="PAYLOAD_INVENTORY_HELPER_SNAPSHOT_INVALID",
    )
    registry_relative = PurePosixPath(inventory.REGISTRY_RELATIVE.as_posix())
    registry_raw = inventory._read_registered_file(
        repo_root,
        registry_relative,
        code="PAYLOAD_REGISTRY_INVALID",
    )
    registry = inventory.load_registry(repo_root)
    policy, policy_raw = _load_policy(repo_root)
    _validate_policy_relations(policy, registry)

    target_by_id = {row["artifact_id"]: row for row in policy["targets"]}
    exclusion_by_id = {row["artifact_id"]: row for row in policy["exclusions"]}
    if artifact_id in exclusion_by_id:
        raise PayloadValidationError(
            "PAYLOAD_ARTIFACT_EXCLUDED",
            exclusion_by_id[artifact_id]["reason"],
        )
    target = target_by_id.get(artifact_id)
    if target is None:
        raise PayloadValidationError(
            "PAYLOAD_ARTIFACT_NOT_APPROVED",
            "对象没有进入逐文件验证白名单",
        )

    objects = {row["artifact_id"]: row for row in registry["objects"]}
    object_row = objects[artifact_id]
    root = _resolve_target_root(
        repo_root,
        registry,
        object_row["root_id"],
    )
    manifest_raw, expected, entry_set_sha256, total_bytes = _load_manifest_expectations(
        root,
        object_row,
        target,
    )
    try:
        manifest_document = json.loads(manifest_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadValidationError("PAYLOAD_MANIFEST_INVALID") from exc

    representation = object_row.get("representation")
    tar_summary: dict[str, Any] | None = None
    if representation is not None:
        tar_summary = _verify_tar_representation(
            root,
            object_row,
            manifest_document,
        )

    object_relative = _safe_relative_path(
        object_row["relative_path"],
        code="PAYLOAD_OBJECT_PATH_INVALID",
    )
    payload_relative = _safe_relative_path(
        target["payload_root_relative_path"],
        code="PAYLOAD_ROOT_PATH_INVALID",
    )
    combined_payload = PurePosixPath(*(object_relative.parts + payload_relative.parts))

    if representation is None:
        with _open_directory_chain(root, combined_payload) as (
            payload_descriptor,
            root_device,
            chain_identities,
        ):
            before = _snapshot_payload_tree(
                payload_descriptor,
                root_device=root_device,
            )
            if set(before) != set(expected):
                raise PayloadValidationError(
                    "PAYLOAD_FILE_SET_MISMATCH",
                    "payload 实际文件集合与清单不一致",
                )

            for path in sorted(expected):
                expected_size, expected_digest = expected[path]
                if before[path][4] != expected_size:
                    raise PayloadValidationError(
                        "PAYLOAD_SIZE_MISMATCH",
                        "payload 文件大小与清单不一致",
                    )
                actual_digest = _hash_registered_payload_file(
                    payload_descriptor,
                    _safe_relative_path(
                        path,
                        code="PAYLOAD_MANIFEST_ENTRY_PATH_INVALID",
                    ),
                    expected_identity=before[path],
                    expected_size=expected_size,
                    root_device=root_device,
                )
                if actual_digest != expected_digest:
                    raise PayloadValidationError(
                        "PAYLOAD_DIGEST_MISMATCH",
                        "payload 文件 SHA-256 与清单不一致",
                    )

            after = _snapshot_payload_tree(
                payload_descriptor,
                root_device=root_device,
            )
            if after != before:
                raise PayloadValidationError(
                    "PAYLOAD_SNAPSHOT_DRIFT",
                    "payload 文件集合或身份在核验中发生变化",
                )
            _verify_directory_chain(root, combined_payload, chain_identities)

    current_registry_raw = inventory._read_registered_file(
        repo_root,
        registry_relative,
        code="PAYLOAD_REGISTRY_INVALID",
    )
    current_policy_raw = inventory._read_registered_file(
        repo_root,
        PurePosixPath(POLICY_RELATIVE.as_posix()),
        code="PAYLOAD_POLICY_INVALID",
    )
    current_validator_raw = inventory._read_registered_file(
        repo_root,
        validator_relative,
        code="PAYLOAD_VALIDATOR_SNAPSHOT_INVALID",
    )
    current_inventory_helper_raw = inventory._read_registered_file(
        repo_root,
        inventory_helper_relative,
        code="PAYLOAD_INVENTORY_HELPER_SNAPSHOT_INVALID",
    )
    current_manifest_raw, _expected, _set_sha, _total = _load_manifest_expectations(
        root,
        object_row,
        target,
    )
    if (
        current_registry_raw != registry_raw
        or current_policy_raw != policy_raw
        or current_manifest_raw != manifest_raw
        or current_validator_raw != validator_raw
        or current_inventory_helper_raw != inventory_helper_raw
    ):
        raise PayloadValidationError(
            "PAYLOAD_INPUT_SNAPSHOT_DRIFT",
            "验证器、安全读取助手、登记册、验证政策或清单在核验中发生变化",
        )

    verification: dict[str, Any] = {
        "file_count": len(expected),
        "total_bytes": total_bytes,
        "entry_set_sha256": entry_set_sha256,
        "exact_file_set": True,
        "content_sha256_verified": True,
        "snapshot_stable": True,
    }
    if tar_summary is not None:
        verification.update(
            {
                "total_bytes": tar_summary["total_bytes"],
                "archive_representation": "tar_posix_tree_v1",
                "symlink_count": tar_summary["symlink_count"],
                "container_sha256_verified": True,
            }
        )

    report: dict[str, Any] = {
        "contract_version": "external-payload-verification-report-v1",
        "status": "PASS",
        "policy_id": policy["policy_id"],
        "registry_id": registry["registry_id"],
        "artifact_id": artifact_id,
        "root_id": object_row["root_id"],
        "bindings": {
            "registry_sha256": _sha256_bytes(registry_raw),
            "policy_sha256": _sha256_bytes(policy_raw),
            "manifest_sha256": _sha256_bytes(manifest_raw),
            "validator_sha256": _sha256_bytes(validator_raw),
            "inventory_helper_sha256": _sha256_bytes(inventory_helper_raw),
        },
        "verification": verification,
        "claims": {
            "payload_bytes_match_manifest": True,
            "package_metadata_verified": False,
            "consumer_closure_verified": False,
            "pointer_resolution_verified": False,
            "recoverability_proven": False,
            "independent_backup_proven": False,
            "migration_performed": False,
            "hard_limit_activation_authorized": False,
            "deletion_authorized": False,
        },
        "checks": [
            "policy_contract_valid",
            "artifact_allowlisted",
            "manifest_binding_valid",
            "payload_path_set_exact",
            "payload_sizes_exact",
            "payload_sha256_exact",
            "payload_snapshot_stable",
            "readonly_capability_respected",
        ],
    }
    _validate_report(repo_root, report)
    return report


def command_check(args: argparse.Namespace) -> int:
    report = validate_payload(args.artifact_id, ROOT)
    verification = report["verification"]
    print(
        f"PASS: {report['artifact_id']} 的 payload 已逐文件核对；"
        f"{verification['file_count']} 个文件，"
        f"{verification['total_bytes']} 字节；"
        "未授权移动、删除或启用 10MB 硬门。"
    )
    return 0


def command_report(args: argparse.Namespace) -> int:
    report = validate_payload(args.artifact_id, ROOT)
    sys.stdout.buffer.write(_json_bytes(report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="一次只核一个已登记外置对象的 payload 文件集合、大小与 SHA-256。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text, handler in (
        ("check", "输出一行人看结论", command_check),
        ("report", "输出不含逐文件清单的轻量 JSON 报告", command_report),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--artifact-id",
            required=True,
            help="外置登记册和验证政策共同允许的对象编号",
        )
        command_parser.set_defaults(handler=handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (PayloadValidationError, inventory.InventoryError) as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
