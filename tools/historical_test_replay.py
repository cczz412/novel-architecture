#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_RELATIVE = Path("config/test_replay/historical_replays.json")
SCHEMA_RELATIVE = Path("config/test_replay/historical_replays_v1.schema.json")
MATERIALIZATION_RECEIPT = Path("HISTORICAL_REPLAY_MATERIALIZATION.json")
RUN_RECEIPT = Path("HISTORICAL_REPLAY_RUN_RECEIPT.json")
ACCESS_RECEIPT = Path("HISTORICAL_REPLAY_FILE_ACCESS.json")
PACKAGE_MANIFEST_COPY = Path(".historical_replay/PACKAGE_MANIFEST.json")
PACKAGE_MANIFEST_NAME = "MANIFEST.json"
PACKAGE_PAYLOAD_ROOT = "payload"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
HEX_40_PATTERN = re.compile(r"^[0-9a-f]{40}$")
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")
NETWORK_AUDIT_EVENTS = {
    "socket.bind",
    "socket.connect",
    "socket.connect_ex",
    "socket.getaddrinfo",
    "socket.gethostbyaddr",
    "socket.gethostbyname",
    "socket.getnameinfo",
    "socket.sendto",
}
SUBPROCESS_AUDIT_PREFIXES = (
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
)
SUBPROCESS_AUDIT_EVENTS = {
    "os.system",
    "pty.spawn",
    "subprocess.Popen",
}
LINK_AUDIT_EVENTS = {
    "os.link",
    "os.symlink",
}
SINGLE_PATH_MUTATION_AUDIT_EVENTS = {
    "os.chmod",
    "os.chown",
    "os.mkdir",
    "os.remove",
    "os.rmdir",
    "os.truncate",
    "os.utime",
}
DOUBLE_PATH_MUTATION_AUDIT_EVENTS = {
    "os.rename",
}


class ReplayError(RuntimeError):
    def __init__(
        self,
        code: str,
        detail: str = "",
        *,
        path: str | None = None,
    ) -> None:
        message = code
        if detail:
            message = f"{message}: {detail}"
        if path is not None:
            message = f"{message}: {path}"
        super().__init__(message)
        self.code = code
        self.detail = detail
        self.path = path


@dataclass(frozen=True)
class SourceFile:
    source: Path
    destination: str
    root_id: str
    unit_id: str
    identity: tuple[int, int, int, int, int, int]


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
    )


def _safe_relative_path(value: object, *, code: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ReplayError(code, "路径必须是非空字符串")
    if "\x00" in value or "\\" in value:
        raise ReplayError(code, "路径含不允许的字符", path=value)
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReplayError(code, "路径必须是规范的仓库相对路径", path=value)
    if ".git" in path.parts:
        raise ReplayError(code, "路径不能进入 .git", path=value)
    return path


def _path_from_posix(root: Path, relative: PurePosixPath) -> Path:
    return root.joinpath(*relative.parts)


def _read_regular_bytes(path: Path, *, code: str) -> bytes:
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise ReplayError(code, "文件不存在") from exc
    if stat.S_ISLNK(before.st_mode):
        raise ReplayError(code, "拒绝符号链接")
    if not stat.S_ISREG(before.st_mode):
        raise ReplayError(code, "不是普通文件")
    if before.st_nlink != 1:
        raise ReplayError(code, "拒绝硬链接")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ReplayError(code, "无法安全打开普通文件") from exc
    try:
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(before):
            raise ReplayError(code, "文件在打开前发生漂移")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _identity(after) != _identity(before):
            raise ReplayError(code, "文件在读取时发生漂移")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_bytes_exclusive(path: Path, data: bytes, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(path, mode)


def _read_json_regular(path: Path, *, code: str) -> dict[str, Any]:
    raw = _read_regular_bytes(path, code=code)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayError(code, "JSON 无法解析") from exc
    if not isinstance(value, dict):
        raise ReplayError(code, "JSON 顶层必须是对象")
    return value


def _write_json_exclusive(path: Path, value: Any) -> None:
    _write_bytes_exclusive(path, _json_bytes(value))


def registry_contract_projection(registry: dict[str, Any]) -> dict[str, Any]:
    return {
        key: registry[key]
        for key in (
            "schema_version",
            "registry_id",
            "decision",
            "default_collection",
            "program_snapshot",
            "source_roots",
            "source_units",
            "groups",
        )
    }


def registry_contract_sha256(registry: dict[str, Any]) -> str:
    return _canonical_json_sha256(registry_contract_projection(registry))


def registry_file_sha256(repo_root: Path) -> str:
    return _sha256_bytes(
        _read_regular_bytes(
            repo_root / REGISTRY_RELATIVE,
            code="REGISTRY_FILE_INVALID",
        )
    )


def historical_nodeids(registry: dict[str, Any]) -> list[str]:
    return [nodeid for group in registry["groups"] for nodeid in group["nodeids"]]


def _validate_registry_semantics(
    repo_root: Path,
    registry: dict[str, Any],
) -> None:
    source_text = registry["decision"]["source_text"]
    if (
        _sha256_bytes(source_text.encode("utf-8"))
        != registry["decision"]["source_text_sha256"]
    ):
        raise ReplayError("DECISION_SHA_MISMATCH")

    package = registry["source_package"]
    package_relative = _safe_relative_path(
        package["relative_path"],
        code="PACKAGE_PATH_INVALID",
    )
    if len(package_relative.parts) != 1:
        raise ReplayError(
            "PACKAGE_PATH_INVALID",
            "回放包只能使用外置仓根下的固定单层目录",
        )
    if package["relative_path"] != package["package_id"]:
        raise ReplayError(
            "PACKAGE_ID_PATH_MISMATCH",
            "回放包编号必须等于固定目录名",
        )
    if package["status"] == "unsealed" and package["manifest_sha256"] is not None:
        raise ReplayError("UNSEALED_PACKAGE_HAS_MANIFEST_SHA")
    if package["status"] == "sealed" and not HEX_64_PATTERN.fullmatch(
        str(package["manifest_sha256"])
    ):
        raise ReplayError("SEALED_PACKAGE_MISSING_MANIFEST_SHA")

    root_ids: set[str] = set()
    root_kinds: set[str] = set()
    for source_root in registry["source_roots"]:
        root_id = source_root["root_id"]
        if root_id in root_ids:
            raise ReplayError("SOURCE_ROOT_ID_DUPLICATE", path=root_id)
        root_ids.add(root_id)
        root_kinds.add(source_root["kind"])
        if source_root["kind"] == "fixed_sibling_archive_batch":
            _safe_relative_path(
                source_root.get("relative_path"),
                code="SOURCE_ROOT_PATH_INVALID",
            )
            if not HEX_64_PATTERN.fullmatch(str(source_root.get("manifest_sha256"))):
                raise ReplayError("SOURCE_ROOT_MANIFEST_SHA_INVALID")
        elif set(source_root) != {"root_id", "kind"}:
            raise ReplayError(
                "LOCAL_SOURCE_ROOT_HAS_EXTRA_FIELDS",
                path=root_id,
            )
    if root_kinds != {
        "fixed_sibling_archive_batch",
        "repository_local_ignored",
    }:
        raise ReplayError("SOURCE_ROOT_KINDS_INCOMPLETE")

    unit_ids: set[str] = set()
    unit_paths: list[tuple[str, PurePosixPath, str]] = []
    for unit in registry["source_units"]:
        unit_id = unit["unit_id"]
        if unit_id in unit_ids:
            raise ReplayError("SOURCE_UNIT_ID_DUPLICATE", path=unit_id)
        unit_ids.add(unit_id)
        if unit["root_id"] not in root_ids:
            raise ReplayError(
                "SOURCE_UNIT_ROOT_UNKNOWN",
                path=unit["root_id"],
            )
        relative = _safe_relative_path(
            unit["repo_relative_path"],
            code="SOURCE_UNIT_PATH_INVALID",
        )
        unit_paths.append((unit["root_id"], relative, unit_id))
    for index, (root_id, path, unit_id) in enumerate(unit_paths):
        for other_root, other_path, other_id in unit_paths[index + 1 :]:
            if root_id != other_root:
                continue
            if path == other_path:
                raise ReplayError(
                    "SOURCE_UNIT_PATH_DUPLICATE",
                    f"{unit_id} 与 {other_id}",
                )
            if path in other_path.parents or other_path in path.parents:
                raise ReplayError(
                    "SOURCE_UNIT_PATH_OVERLAP",
                    f"{unit_id} 与 {other_id}",
                )

    group_ids: set[str] = set()
    seen_nodeids: set[str] = set()
    used_units: set[str] = set()
    for group in registry["groups"]:
        group_id = group["group_id"]
        if group_id in group_ids:
            raise ReplayError("GROUP_ID_DUPLICATE", path=group_id)
        group_ids.add(group_id)
        for unit_id in group["source_unit_ids"]:
            if unit_id not in unit_ids:
                raise ReplayError(
                    "GROUP_SOURCE_UNIT_UNKNOWN",
                    path=unit_id,
                )
            used_units.add(unit_id)
        if len(group["source_unit_ids"]) != len(set(group["source_unit_ids"])):
            raise ReplayError(
                "GROUP_SOURCE_UNIT_DUPLICATE",
                path=group_id,
            )
        for nodeid in group["nodeids"]:
            if nodeid in seen_nodeids:
                raise ReplayError("NODEID_DUPLICATE", path=nodeid)
            if any(token in nodeid for token in ("*", "?", "[")):
                raise ReplayError("NODEID_WILDCARD_REJECTED", path=nodeid)
            parts = nodeid.split("::")
            if len(parts) not in {2, 3}:
                raise ReplayError("NODEID_SHAPE_INVALID", path=nodeid)
            test_relative = _safe_relative_path(
                parts[0],
                code="NODEID_TEST_PATH_INVALID",
            )
            if (
                test_relative.parts[0] != "tests"
                or not test_relative.name.startswith("test_")
                or test_relative.suffix != ".py"
            ):
                raise ReplayError("NODEID_TEST_PATH_INVALID", path=nodeid)
            if not _path_from_posix(repo_root, test_relative).is_file():
                raise ReplayError("NODEID_TEST_FILE_MISSING", path=nodeid)
            seen_nodeids.add(nodeid)
    if used_units != unit_ids:
        missing = sorted(unit_ids - used_units)
        raise ReplayError(
            "SOURCE_UNIT_WITHOUT_CONSUMER",
            ",".join(missing),
        )
    expected_count = registry["default_collection"]["node_count"]
    if len(seen_nodeids) != expected_count:
        raise ReplayError(
            "NODE_COUNT_MISMATCH",
            f"登记={expected_count}，实际={len(seen_nodeids)}",
        )


def load_registry(repo_root: Path = ROOT) -> dict[str, Any]:
    schema = _read_json_regular(
        repo_root / SCHEMA_RELATIVE,
        code="REGISTRY_SCHEMA_FILE_INVALID",
    )
    registry = _read_json_regular(
        repo_root / REGISTRY_RELATIVE,
        code="REGISTRY_FILE_INVALID",
    )
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(registry)
    except (SchemaError, ValidationError) as exc:
        raise ReplayError(
            "REGISTRY_SCHEMA_INVALID",
            getattr(exc, "json_path", str(exc)),
        ) from exc
    _validate_registry_semantics(repo_root, registry)
    return registry


def external_archive_root(repo_root: Path) -> Path:
    return repo_root.parent / f"{repo_root.name}_外置仓"


def replay_workspace_root(repo_root: Path) -> Path:
    return repo_root.parent / f"{repo_root.name}_测试工作区"


def _assert_directory_without_symlink(path: Path, *, code: str) -> None:
    try:
        value = path.lstat()
    except FileNotFoundError as exc:
        raise ReplayError(code, "目录不存在") from exc
    if stat.S_ISLNK(value.st_mode):
        raise ReplayError(code, "拒绝符号链接目录")
    if not stat.S_ISDIR(value.st_mode):
        raise ReplayError(code, "不是目录")


def _resolved_source_roots(
    repo_root: Path,
    registry: dict[str, Any],
) -> dict[str, Path]:
    result: dict[str, Path] = {}
    sibling_root = external_archive_root(repo_root)
    _assert_directory_without_symlink(
        sibling_root,
        code="EXTERNAL_ARCHIVE_ROOT_INVALID",
    )
    for source_root in registry["source_roots"]:
        if source_root["kind"] == "repository_local_ignored":
            path = repo_root
        else:
            relative = _safe_relative_path(
                source_root["relative_path"],
                code="SOURCE_ROOT_PATH_INVALID",
            )
            path = _path_from_posix(sibling_root, relative)
            manifest_path = path / PACKAGE_MANIFEST_NAME
            actual_manifest_sha = _sha256_bytes(
                _read_regular_bytes(
                    manifest_path,
                    code="SOURCE_ROOT_MANIFEST_INVALID",
                )
            )
            if actual_manifest_sha != source_root["manifest_sha256"]:
                raise ReplayError(
                    "SOURCE_ROOT_MANIFEST_SHA_MISMATCH",
                    path=source_root["root_id"],
                )
        _assert_directory_without_symlink(
            path,
            code="SOURCE_ROOT_DIRECTORY_INVALID",
        )
        result[source_root["root_id"]] = path
    return result


def _source_file_from_stat(
    source: Path,
    destination: PurePosixPath,
    *,
    root_id: str,
    unit_id: str,
) -> SourceFile:
    value = source.lstat()
    if stat.S_ISLNK(value.st_mode):
        raise ReplayError(
            "SOURCE_SYMLINK_REJECTED",
            path=destination.as_posix(),
        )
    if not stat.S_ISREG(value.st_mode):
        raise ReplayError(
            "SOURCE_SPECIAL_FILE_REJECTED",
            path=destination.as_posix(),
        )
    if value.st_nlink != 1:
        raise ReplayError(
            "SOURCE_HARDLINK_REJECTED",
            path=destination.as_posix(),
        )
    return SourceFile(
        source=source,
        destination=destination.as_posix(),
        root_id=root_id,
        unit_id=unit_id,
        identity=_identity(value),
    )


def _walk_directory(
    source_root: Path,
    destination_root: PurePosixPath,
    *,
    root_id: str,
    unit_id: str,
) -> list[SourceFile]:
    result: list[SourceFile] = []

    def visit(current: Path, relative: PurePosixPath) -> None:
        try:
            entries = sorted(os.scandir(current), key=lambda item: item.name)
        except OSError as exc:
            raise ReplayError(
                "SOURCE_DIRECTORY_READ_FAILED",
                path=(destination_root / relative).as_posix(),
            ) from exc
        for entry in entries:
            child_relative = relative / entry.name
            destination = destination_root / child_relative
            value = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(value.st_mode):
                raise ReplayError(
                    "SOURCE_SYMLINK_REJECTED",
                    path=destination.as_posix(),
                )
            if stat.S_ISDIR(value.st_mode):
                visit(Path(entry.path), child_relative)
                continue
            result.append(
                _source_file_from_stat(
                    Path(entry.path),
                    destination,
                    root_id=root_id,
                    unit_id=unit_id,
                )
            )

    visit(source_root, PurePosixPath())
    return result


def collect_source_files(
    repo_root: Path,
    registry: dict[str, Any],
) -> list[SourceFile]:
    roots = _resolved_source_roots(repo_root, registry)
    files: list[SourceFile] = []
    destinations: set[str] = set()
    for unit in registry["source_units"]:
        relative = _safe_relative_path(
            unit["repo_relative_path"],
            code="SOURCE_UNIT_PATH_INVALID",
        )
        source = _path_from_posix(roots[unit["root_id"]], relative)
        if unit["kind"] == "file":
            unit_files = [
                _source_file_from_stat(
                    source,
                    relative,
                    root_id=unit["root_id"],
                    unit_id=unit["unit_id"],
                )
            ]
        else:
            _assert_directory_without_symlink(
                source,
                code="SOURCE_UNIT_DIRECTORY_INVALID",
            )
            unit_files = _walk_directory(
                source,
                relative,
                root_id=unit["root_id"],
                unit_id=unit["unit_id"],
            )
            if not unit_files:
                raise ReplayError(
                    "SOURCE_UNIT_DIRECTORY_EMPTY",
                    path=unit["unit_id"],
                )
        for source_file in unit_files:
            if source_file.destination in destinations:
                raise ReplayError(
                    "SOURCE_DESTINATION_DUPLICATE",
                    path=source_file.destination,
                )
            destinations.add(source_file.destination)
            files.append(source_file)
    return sorted(files, key=lambda item: item.destination)


def _source_snapshot(files: list[SourceFile]) -> list[tuple[str, tuple[int, ...]]]:
    return [(item.destination, item.identity) for item in files]


def _read_source_file(item: SourceFile) -> bytes:
    before = item.source.lstat()
    if _identity(before) != item.identity:
        raise ReplayError(
            "SOURCE_CHANGED_BEFORE_COPY",
            path=item.destination,
        )
    data = _read_regular_bytes(
        item.source,
        code="SOURCE_FILE_READ_FAILED",
    )
    after = item.source.lstat()
    if _identity(after) != item.identity:
        raise ReplayError(
            "SOURCE_CHANGED_DURING_COPY",
            path=item.destination,
        )
    return data


def _package_readme(registry: dict[str, Any]) -> bytes:
    text = f"""# 历史测试回放包

包编号：`{registry["source_package"]["package_id"]}`

这个包只保存 S-05-B 登记的历史测试材料副本。它不能单独当测试通过，也不能直接
回写主仓。使用时必须由 `tools/historical_test_replay.py` 把固定 Git 提交和本包
复制到新的同级测试工作区，再运行登记的 40 个精确节点。

包内 `payload/` 保留仓库相对落点；`MANIFEST.json` 与 `SHA256SUMS` 负责逐文件验 SHA。

来源：Codex
"""
    return text.encode("utf-8")


def _expected_result(registry: dict[str, Any]) -> bytes:
    return _json_bytes(
        {
            "expected_node_count": len(historical_nodeids(registry)),
            "expected_pytest_exit_code": 0,
            "result_status": "not_run_by_seal",
            "schema_version": "historical-test-replay-expected-v1",
        }
    )


def _metadata_rows(
    values: dict[str, bytes],
) -> list[dict[str, Any]]:
    return [
        {
            "bytes": len(data),
            "path": path,
            "sha256": _sha256_bytes(data),
        }
        for path, data in sorted(values.items())
    ]


def _build_package_in_directory(
    repo_root: Path,
    registry: dict[str, Any],
    staging: Path,
) -> dict[str, Any]:
    before_files = collect_source_files(repo_root, registry)
    file_rows: list[dict[str, Any]] = []
    unit_counts: dict[str, dict[str, int]] = {
        unit["unit_id"]: {"file_count": 0, "total_bytes": 0}
        for unit in registry["source_units"]
    }
    checksum_lines: list[str] = []
    for item in before_files:
        data = _read_source_file(item)
        destination = staging / PACKAGE_PAYLOAD_ROOT / item.destination
        _write_bytes_exclusive(
            destination,
            data,
            mode=stat.S_IMODE(item.identity[2]),
        )
        digest = _sha256_bytes(data)
        file_rows.append(
            {
                "bytes": len(data),
                "path": item.destination,
                "sha256": digest,
                "source_root_id": item.root_id,
                "source_unit_id": item.unit_id,
            }
        )
        unit_counts[item.unit_id]["file_count"] += 1
        unit_counts[item.unit_id]["total_bytes"] += len(data)
        checksum_lines.append(f"{digest}  {PACKAGE_PAYLOAD_ROOT}/{item.destination}\n")

    after_files = collect_source_files(repo_root, registry)
    if _source_snapshot(after_files) != _source_snapshot(before_files):
        raise ReplayError("SOURCE_TREE_CHANGED_DURING_SEAL")

    metadata_values = {
        "EXPECTED_RESULT.json": _expected_result(registry),
        "REPLAY_README.md": _package_readme(registry),
        "SHA256SUMS": "".join(checksum_lines).encode("utf-8"),
    }
    for relative, data in metadata_values.items():
        _write_bytes_exclusive(staging / relative, data)

    manifest = {
        "decision": registry["decision"],
        "files": file_rows,
        "metadata_files": _metadata_rows(metadata_values),
        "nodeids_sha256": _canonical_json_sha256(historical_nodeids(registry)),
        "package_id": registry["source_package"]["package_id"],
        "registry_contract_sha256": registry_contract_sha256(registry),
        "registry_id": registry["registry_id"],
        "schema_version": "historical-test-replay-package-v1",
        "source_root_manifests": [
            {
                "root_id": source_root["root_id"],
                "sha256": source_root["manifest_sha256"],
            }
            for source_root in registry["source_roots"]
            if source_root["kind"] == "fixed_sibling_archive_batch"
        ],
        "source_units": [
            {
                "file_count": unit_counts[unit["unit_id"]]["file_count"],
                "total_bytes": unit_counts[unit["unit_id"]]["total_bytes"],
                "unit_id": unit["unit_id"],
            }
            for unit in registry["source_units"]
        ],
        "total_bytes": sum(row["bytes"] for row in file_rows),
        "total_files": len(file_rows),
    }
    _write_json_exclusive(staging / PACKAGE_MANIFEST_NAME, manifest)
    return manifest


def _actual_regular_files(root: Path) -> list[str]:
    result: list[str] = []
    for current, directories, files in os.walk(root, followlinks=False):
        directories.sort()
        files.sort()
        current_path = Path(current)
        for directory in directories:
            value = (current_path / directory).lstat()
            if stat.S_ISLNK(value.st_mode):
                raise ReplayError(
                    "PACKAGE_SYMLINK_REJECTED",
                    path=(current_path / directory).relative_to(root).as_posix(),
                )
            if not stat.S_ISDIR(value.st_mode):
                raise ReplayError("PACKAGE_SPECIAL_DIRECTORY_REJECTED")
        for filename in files:
            path = current_path / filename
            value = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(value.st_mode):
                raise ReplayError(
                    "PACKAGE_SYMLINK_REJECTED",
                    path=relative,
                )
            if not stat.S_ISREG(value.st_mode):
                raise ReplayError(
                    "PACKAGE_SPECIAL_FILE_REJECTED",
                    path=relative,
                )
            if value.st_nlink != 1:
                raise ReplayError(
                    "PACKAGE_HARDLINK_REJECTED",
                    path=relative,
                )
            result.append(relative)
    return sorted(result)


def _validate_package_path(
    package_path: Path,
    registry: dict[str, Any],
    *,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    _assert_directory_without_symlink(
        package_path,
        code="PACKAGE_DIRECTORY_INVALID",
    )
    manifest_path = package_path / PACKAGE_MANIFEST_NAME
    manifest_raw = _read_regular_bytes(
        manifest_path,
        code="PACKAGE_MANIFEST_INVALID",
    )
    if _sha256_bytes(manifest_raw) != expected_manifest_sha256:
        raise ReplayError("PACKAGE_MANIFEST_SHA_MISMATCH")
    try:
        manifest = json.loads(manifest_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayError("PACKAGE_MANIFEST_INVALID") from exc
    if not isinstance(manifest, dict):
        raise ReplayError("PACKAGE_MANIFEST_INVALID")
    expected_scalars = {
        "schema_version": "historical-test-replay-package-v1",
        "package_id": registry["source_package"]["package_id"],
        "registry_id": registry["registry_id"],
        "registry_contract_sha256": registry_contract_sha256(registry),
        "nodeids_sha256": _canonical_json_sha256(historical_nodeids(registry)),
    }
    for key, expected in expected_scalars.items():
        if manifest.get(key) != expected:
            raise ReplayError(
                "PACKAGE_MANIFEST_BINDING_MISMATCH",
                path=key,
            )
    if manifest.get("decision") != registry["decision"]:
        raise ReplayError("PACKAGE_DECISION_MISMATCH")

    file_rows = manifest.get("files")
    if not isinstance(file_rows, list) or not file_rows:
        raise ReplayError("PACKAGE_FILE_ROWS_INVALID")
    expected_files = {
        PACKAGE_MANIFEST_NAME,
        "EXPECTED_RESULT.json",
        "REPLAY_README.md",
        "SHA256SUMS",
    }
    checksum_lines: list[str] = []
    total_bytes = 0
    destinations: list[str] = []
    valid_root_ids = {
        source_root["root_id"] for source_root in registry["source_roots"]
    }
    valid_unit_ids = {unit["unit_id"] for unit in registry["source_units"]}
    unit_by_id = {unit["unit_id"]: unit for unit in registry["source_units"]}
    unit_counts = {
        unit_id: {"file_count": 0, "total_bytes": 0} for unit_id in valid_unit_ids
    }
    for row in file_rows:
        if set(row) != {
            "bytes",
            "path",
            "sha256",
            "source_root_id",
            "source_unit_id",
        }:
            raise ReplayError("PACKAGE_FILE_ROW_FIELDS_INVALID")
        relative = _safe_relative_path(
            row["path"],
            code="PACKAGE_FILE_PATH_INVALID",
        )
        if row["source_root_id"] not in valid_root_ids:
            raise ReplayError("PACKAGE_FILE_ROOT_UNKNOWN")
        if row["source_unit_id"] not in valid_unit_ids:
            raise ReplayError("PACKAGE_FILE_UNIT_UNKNOWN")
        unit = unit_by_id[row["source_unit_id"]]
        if row["source_root_id"] != unit["root_id"]:
            raise ReplayError("PACKAGE_FILE_UNIT_ROOT_MISMATCH")
        if not isinstance(row["bytes"], int) or row["bytes"] < 0:
            raise ReplayError("PACKAGE_FILE_SIZE_INVALID")
        if not HEX_64_PATTERN.fullmatch(str(row["sha256"])):
            raise ReplayError("PACKAGE_FILE_SHA_INVALID")
        relative_text = relative.as_posix()
        unit_relative = _safe_relative_path(
            unit["repo_relative_path"],
            code="SOURCE_UNIT_PATH_INVALID",
        )
        if unit["kind"] == "file":
            belongs_to_unit = relative == unit_relative
        else:
            belongs_to_unit = unit_relative in relative.parents
        if not belongs_to_unit:
            raise ReplayError(
                "PACKAGE_FILE_OUTSIDE_SOURCE_UNIT",
                path=relative_text,
            )
        destinations.append(relative_text)
        payload_relative = f"{PACKAGE_PAYLOAD_ROOT}/{relative_text}"
        expected_files.add(payload_relative)
        data = _read_regular_bytes(
            package_path / payload_relative,
            code="PACKAGE_PAYLOAD_FILE_INVALID",
        )
        if len(data) != row["bytes"] or _sha256_bytes(data) != row["sha256"]:
            raise ReplayError(
                "PACKAGE_PAYLOAD_DRIFT",
                path=relative_text,
            )
        total_bytes += len(data)
        unit_counts[row["source_unit_id"]]["file_count"] += 1
        unit_counts[row["source_unit_id"]]["total_bytes"] += len(data)
        checksum_lines.append(
            f"{row['sha256']}  {PACKAGE_PAYLOAD_ROOT}/{relative_text}\n"
        )
    if destinations != sorted(destinations) or len(destinations) != len(
        set(destinations)
    ):
        raise ReplayError("PACKAGE_FILE_ORDER_OR_DUPLICATE_INVALID")
    if manifest.get("total_files") != len(file_rows):
        raise ReplayError("PACKAGE_TOTAL_FILES_MISMATCH")
    if manifest.get("total_bytes") != total_bytes:
        raise ReplayError("PACKAGE_TOTAL_BYTES_MISMATCH")

    expected_unit_rows = [
        {
            "file_count": unit_counts[unit["unit_id"]]["file_count"],
            "total_bytes": unit_counts[unit["unit_id"]]["total_bytes"],
            "unit_id": unit["unit_id"],
        }
        for unit in registry["source_units"]
    ]
    if any(row["file_count"] < 1 for row in expected_unit_rows):
        raise ReplayError("PACKAGE_SOURCE_UNIT_EMPTY")
    if manifest.get("source_units") != expected_unit_rows:
        raise ReplayError("PACKAGE_SOURCE_UNITS_MISMATCH")

    expected_source_manifests = [
        {
            "root_id": source_root["root_id"],
            "sha256": source_root["manifest_sha256"],
        }
        for source_root in registry["source_roots"]
        if source_root["kind"] == "fixed_sibling_archive_batch"
    ]
    if manifest.get("source_root_manifests") != expected_source_manifests:
        raise ReplayError("PACKAGE_SOURCE_ROOT_MANIFEST_MISMATCH")

    metadata_rows = manifest.get("metadata_files")
    if not isinstance(metadata_rows, list):
        raise ReplayError("PACKAGE_METADATA_ROWS_INVALID")
    metadata_by_path = {
        row.get("path"): row for row in metadata_rows if isinstance(row, dict)
    }
    if set(metadata_by_path) != {
        "EXPECTED_RESULT.json",
        "REPLAY_README.md",
        "SHA256SUMS",
    }:
        raise ReplayError("PACKAGE_METADATA_PATHS_INVALID")
    for relative, row in metadata_by_path.items():
        if set(row) != {"bytes", "path", "sha256"}:
            raise ReplayError("PACKAGE_METADATA_ROW_FIELDS_INVALID")
        data = _read_regular_bytes(
            package_path / relative,
            code="PACKAGE_METADATA_FILE_INVALID",
        )
        if len(data) != row["bytes"] or _sha256_bytes(data) != row["sha256"]:
            raise ReplayError(
                "PACKAGE_METADATA_DRIFT",
                path=relative,
            )
    expected_checksums = "".join(checksum_lines).encode("utf-8")
    if (
        _read_regular_bytes(
            package_path / "SHA256SUMS",
            code="PACKAGE_CHECKSUMS_INVALID",
        )
        != expected_checksums
    ):
        raise ReplayError("PACKAGE_CHECKSUMS_MISMATCH")
    if set(_actual_regular_files(package_path)) != expected_files:
        raise ReplayError("PACKAGE_FILE_SET_MISMATCH")
    return manifest


def package_path_for(
    repo_root: Path,
    registry: dict[str, Any],
) -> Path:
    relative = _safe_relative_path(
        registry["source_package"]["relative_path"],
        code="PACKAGE_PATH_INVALID",
    )
    return _path_from_posix(external_archive_root(repo_root), relative)


def validate_package(
    repo_root: Path,
    registry: dict[str, Any],
) -> dict[str, Any]:
    package = registry["source_package"]
    if package["status"] != "sealed":
        raise ReplayError("PACKAGE_NOT_SEALED")
    return _validate_package_path(
        package_path_for(repo_root, registry),
        registry,
        expected_manifest_sha256=package["manifest_sha256"],
    )


def seal_package(repo_root: Path = ROOT) -> tuple[Path, str]:
    registry = load_registry(repo_root)
    if registry["source_package"]["status"] != "unsealed":
        raise ReplayError("PACKAGE_ALREADY_MARKED_SEALED")
    external_root = external_archive_root(repo_root)
    _assert_directory_without_symlink(
        external_root,
        code="EXTERNAL_ARCHIVE_ROOT_INVALID",
    )
    final_path = package_path_for(repo_root, registry)
    if final_path.exists() or final_path.is_symlink():
        raise ReplayError("PACKAGE_ALREADY_EXISTS")
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{registry['source_package']['package_id']}.staging-",
            dir=external_root,
        )
    )
    published = False
    try:
        _build_package_in_directory(repo_root, registry, staging)
        manifest_sha = _sha256_bytes(
            _read_regular_bytes(
                staging / PACKAGE_MANIFEST_NAME,
                code="PACKAGE_MANIFEST_INVALID",
            )
        )
        _validate_package_path(
            staging,
            registry,
            expected_manifest_sha256=manifest_sha,
        )
        staging.rename(final_path)
        published = True
        _validate_package_path(
            final_path,
            registry,
            expected_manifest_sha256=manifest_sha,
        )
        return final_path, manifest_sha
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)


def validate_configuration(
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    registry = load_registry(repo_root)
    source_files = collect_source_files(repo_root, registry)
    result: dict[str, Any] = {
        "node_count": len(historical_nodeids(registry)),
        "package_status": registry["source_package"]["status"],
        "registry_contract_sha256": registry_contract_sha256(registry),
        "source_file_count": len(source_files),
        "status": "READY_TO_SEAL",
    }
    if registry["source_package"]["status"] == "sealed":
        manifest = validate_package(repo_root, registry)
        result.update(
            {
                "package_manifest_sha256": registry["source_package"][
                    "manifest_sha256"
                ],
                "package_total_bytes": manifest["total_bytes"],
                "package_total_files": manifest["total_files"],
                "status": "VALID",
            }
        )
    return result


def _safe_git_environment() -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("LANG", "LC_ALL", "LC_CTYPE", "PATH"):
        value = os.environ.get(key)
        if value:
            result[key] = value
    return result


def _git(
    repo_root: Path,
    args: Sequence[str],
    *,
    binary: bool = False,
) -> bytes | str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        env=_safe_git_environment(),
    )
    if completed.returncode != 0:
        raise ReplayError("GIT_COMMAND_FAILED", " ".join(args[:2]))
    if binary:
        return completed.stdout
    try:
        return completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ReplayError("GIT_OUTPUT_INVALID") from exc


def resolve_commit(repo_root: Path, commit: str) -> str:
    if not HEX_40_PATTERN.fullmatch(commit):
        raise ReplayError(
            "COMMIT_ARGUMENT_INVALID",
            "只接受完整 40 位提交号",
        )
    resolved = _git(
        repo_root,
        ["rev-parse", "--verify", f"{commit}^{{commit}}"],
    )
    if not isinstance(resolved, str) or not HEX_40_PATTERN.fullmatch(resolved):
        raise ReplayError("RESOLVED_COMMIT_INVALID")
    return resolved


def _git_file_bytes(repo_root: Path, commit: str, relative: str) -> bytes:
    value = _git(
        repo_root,
        ["show", f"{commit}:{relative}"],
        binary=True,
    )
    if not isinstance(value, bytes):
        raise AssertionError("binary git output must be bytes")
    return value


def _normalized_link_target(name: str, linkname: str) -> str:
    if not linkname or "\\" in linkname:
        raise ReplayError("GIT_ARCHIVE_SYMLINK_TARGET_INVALID", path=name)
    link_path = PurePosixPath(linkname)
    if link_path.is_absolute():
        raise ReplayError("GIT_ARCHIVE_SYMLINK_TARGET_ESCAPE", path=name)
    parts: list[str] = []
    for part in (PurePosixPath(name).parent / link_path).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ReplayError(
                    "GIT_ARCHIVE_SYMLINK_TARGET_ESCAPE",
                    path=name,
                )
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise ReplayError("GIT_ARCHIVE_SYMLINK_TARGET_INVALID", path=name)
    return PurePosixPath(*parts).as_posix()


def _extract_git_archive(
    archive_bytes: bytes,
    destination: Path,
    *,
    allowed_omitted_symlinks: set[str],
) -> dict[str, Any]:
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        members = archive.getmembers()
        by_name: dict[str, tarfile.TarInfo] = {}
        for member in members:
            relative = _safe_relative_path(
                member.name.rstrip("/"),
                code="GIT_ARCHIVE_PATH_INVALID",
            )
            name = relative.as_posix()
            if name in by_name:
                raise ReplayError(
                    "GIT_ARCHIVE_MEMBER_DUPLICATE",
                    path=name,
                )
            by_name[name] = member
        for omitted in sorted(allowed_omitted_symlinks):
            member = by_name.get(omitted)
            if member is None:
                raise ReplayError(
                    "GIT_ARCHIVE_OMITTED_SYMLINK_MISSING",
                    path=omitted,
                )
            if not member.issym():
                raise ReplayError(
                    "GIT_ARCHIVE_OMITTED_PATH_NOT_SYMLINK",
                    path=omitted,
                )
            prefix = f"{omitted}/"
            if any(name.startswith(prefix) for name in by_name):
                raise ReplayError(
                    "GIT_ARCHIVE_OMITTED_PATH_HAS_CONTENT",
                    path=omitted,
                )

        def target_member(name: str) -> tarfile.TarInfo:
            seen: set[str] = set()
            current = name
            while True:
                if current in seen:
                    raise ReplayError(
                        "GIT_ARCHIVE_SYMLINK_CYCLE",
                        path=name,
                    )
                seen.add(current)
                member = by_name.get(current)
                if member is None:
                    raise ReplayError(
                        "GIT_ARCHIVE_SYMLINK_TARGET_MISSING",
                        path=name,
                    )
                if member.issym():
                    current = _normalized_link_target(
                        current,
                        member.linkname,
                    )
                    continue
                if not member.isfile():
                    raise ReplayError(
                        "GIT_ARCHIVE_SYMLINK_TARGET_NOT_FILE",
                        path=name,
                    )
                return member

        converted_symlinks: list[dict[str, str]] = []
        omitted_symlinks: list[str] = []
        tree_rows: list[dict[str, Any]] = []
        for name, member in sorted(by_name.items()):
            if member.isdir():
                (destination / name).mkdir(parents=True, exist_ok=True)
                continue
            if member.islnk():
                raise ReplayError(
                    "GIT_ARCHIVE_HARDLINK_REJECTED",
                    path=name,
                )
            if member.issym():
                if name in allowed_omitted_symlinks:
                    omitted_symlinks.append(name)
                    continue
                resolved = _normalized_link_target(name, member.linkname)
                real_member = target_member(resolved)
                stream = archive.extractfile(real_member)
                mode = real_member.mode
                converted_symlinks.append({"path": name, "target": resolved})
            elif member.isfile():
                stream = archive.extractfile(member)
                mode = member.mode
            else:
                raise ReplayError(
                    "GIT_ARCHIVE_SPECIAL_MEMBER_REJECTED",
                    path=name,
                )
            if stream is None:
                raise ReplayError(
                    "GIT_ARCHIVE_MEMBER_READ_FAILED",
                    path=name,
                )
            data = stream.read()
            _write_bytes_exclusive(
                destination / name,
                data,
                mode=mode & 0o777,
            )
            tree_rows.append(
                {
                    "bytes": len(data),
                    "path": name,
                    "sha256": _sha256_bytes(data),
                }
            )
    if omitted_symlinks != sorted(allowed_omitted_symlinks):
        raise ReplayError("GIT_ARCHIVE_OMITTED_SYMLINK_SET_MISMATCH")
    return {
        "converted_symlinks": converted_symlinks,
        "file_count": len(tree_rows),
        "omitted_symlinks": omitted_symlinks,
        "tree_sha256": _canonical_json_sha256(tree_rows),
    }


def _copy_package_payload(
    package_path: Path,
    manifest: dict[str, Any],
    workspace: Path,
) -> None:
    for row in manifest["files"]:
        relative = _safe_relative_path(
            row["path"],
            code="PACKAGE_FILE_PATH_INVALID",
        )
        destination = _path_from_posix(workspace, relative)
        if destination.exists() or destination.is_symlink():
            raise ReplayError(
                "PACKAGE_DESTINATION_COLLIDES_WITH_PROGRAM",
                path=relative.as_posix(),
            )
        data = _read_regular_bytes(
            package_path / PACKAGE_PAYLOAD_ROOT / relative.as_posix(),
            code="PACKAGE_PAYLOAD_FILE_INVALID",
        )
        if len(data) != row["bytes"] or _sha256_bytes(data) != row["sha256"]:
            raise ReplayError(
                "PACKAGE_PAYLOAD_DRIFT",
                path=relative.as_posix(),
            )
        _write_bytes_exclusive(destination, data)


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ReplayError(
            "RUN_ID_INVALID",
            "只接受字母、数字、点、下划线和短横线",
        )


def materialize_workspace(
    repo_root: Path = ROOT,
    *,
    commit: str,
    run_id: str,
) -> Path:
    _validate_run_id(run_id)
    registry = load_registry(repo_root)
    manifest = validate_package(repo_root, registry)
    resolved_commit = resolve_commit(repo_root, commit)
    current_registry_sha = registry_file_sha256(repo_root)
    commit_registry = _git_file_bytes(
        repo_root,
        resolved_commit,
        REGISTRY_RELATIVE.as_posix(),
    )
    if _sha256_bytes(commit_registry) != current_registry_sha:
        raise ReplayError("COMMIT_REGISTRY_MISMATCH")
    current_tool = _read_regular_bytes(
        repo_root / "tools/historical_test_replay.py",
        code="REPLAY_TOOL_FILE_INVALID",
    )
    commit_tool = _git_file_bytes(
        repo_root,
        resolved_commit,
        "tools/historical_test_replay.py",
    )
    if commit_tool != current_tool:
        raise ReplayError("COMMIT_REPLAY_TOOL_MISMATCH")

    workspace_root = replay_workspace_root(repo_root)
    if workspace_root.exists():
        _assert_directory_without_symlink(
            workspace_root,
            code="WORKSPACE_ROOT_INVALID",
        )
    else:
        workspace_root.mkdir()
    final_path = workspace_root / run_id
    if final_path.exists() or final_path.is_symlink():
        raise ReplayError("WORKSPACE_ALREADY_EXISTS")
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{run_id}.staging-",
            dir=workspace_root,
        )
    )
    published = False
    try:
        archive_bytes = _git(
            repo_root,
            ["archive", "--format=tar", resolved_commit],
            binary=True,
        )
        if not isinstance(archive_bytes, bytes):
            raise AssertionError("binary git output must be bytes")
        program = _extract_git_archive(
            archive_bytes,
            staging,
            allowed_omitted_symlinks=set(
                registry["program_snapshot"]["allowed_omitted_symlinks"]
            ),
        )
        if (
            _sha256_bytes(
                _read_regular_bytes(
                    staging / REGISTRY_RELATIVE,
                    code="WORKSPACE_REGISTRY_INVALID",
                )
            )
            != current_registry_sha
        ):
            raise ReplayError("WORKSPACE_REGISTRY_MISMATCH")
        if (
            _read_regular_bytes(
                staging / "tools/historical_test_replay.py",
                code="WORKSPACE_TOOL_INVALID",
            )
            != current_tool
        ):
            raise ReplayError("WORKSPACE_TOOL_MISMATCH")
        if (staging / ".git").exists():
            raise ReplayError("WORKSPACE_GIT_METADATA_PRESENT")

        package_path = package_path_for(repo_root, registry)
        _copy_package_payload(package_path, manifest, staging)
        _write_bytes_exclusive(
            staging / PACKAGE_MANIFEST_COPY,
            _read_regular_bytes(
                package_path / PACKAGE_MANIFEST_NAME,
                code="PACKAGE_MANIFEST_INVALID",
            ),
        )
        receipt = {
            "capability_limits": {
                "delete_source": False,
                "model_api": False,
                "network": False,
                "notion_write": False,
                "source_worktree_included": False,
            },
            "fixture_total_bytes": manifest["total_bytes"],
            "fixture_total_files": manifest["total_files"],
            "nodeids": historical_nodeids(registry),
            "package_manifest_sha256": registry["source_package"]["manifest_sha256"],
            "program_commit": resolved_commit,
            "program_snapshot": {
                **program,
                "git_metadata_included": False,
            },
            "registry_contract_sha256": registry_contract_sha256(registry),
            "registry_id": registry["registry_id"],
            "registry_sha256": current_registry_sha,
            "run_id": run_id,
            "schema_version": "historical-test-replay-materialization-v1",
            "status": "ready",
            "tool_sha256": _sha256_bytes(current_tool),
        }
        _write_json_exclusive(staging / MATERIALIZATION_RECEIPT, receipt)
        verify_materialization_receipt(staging)
        staging.rename(final_path)
        published = True
        verify_materialization_receipt(final_path)
        return final_path
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)


def verify_materialization_receipt(
    workspace_root: Path,
) -> dict[str, Any]:
    registry = load_registry(workspace_root)
    receipt = _read_json_regular(
        workspace_root / MATERIALIZATION_RECEIPT,
        code="MATERIALIZATION_RECEIPT_INVALID",
    )
    expected_keys = {
        "capability_limits",
        "fixture_total_bytes",
        "fixture_total_files",
        "nodeids",
        "package_manifest_sha256",
        "program_commit",
        "program_snapshot",
        "registry_contract_sha256",
        "registry_id",
        "registry_sha256",
        "run_id",
        "schema_version",
        "status",
        "tool_sha256",
    }
    if set(receipt) != expected_keys:
        raise ReplayError("MATERIALIZATION_RECEIPT_FIELDS_INVALID")
    expected_scalars = {
        "schema_version": "historical-test-replay-materialization-v1",
        "status": "ready",
        "registry_id": registry["registry_id"],
        "registry_sha256": registry_file_sha256(workspace_root),
        "registry_contract_sha256": registry_contract_sha256(registry),
        "package_manifest_sha256": registry["source_package"]["manifest_sha256"],
        "nodeids": historical_nodeids(registry),
    }
    for key, expected in expected_scalars.items():
        if receipt.get(key) != expected:
            raise ReplayError(
                "MATERIALIZATION_RECEIPT_BINDING_MISMATCH",
                path=key,
            )
    if not HEX_40_PATTERN.fullmatch(str(receipt["program_commit"])):
        raise ReplayError("MATERIALIZATION_COMMIT_INVALID")
    _validate_run_id(str(receipt["run_id"]))
    expected_capabilities = {
        "delete_source": False,
        "model_api": False,
        "network": False,
        "notion_write": False,
        "source_worktree_included": False,
    }
    if receipt["capability_limits"] != expected_capabilities:
        raise ReplayError("MATERIALIZATION_CAPABILITIES_INVALID")
    if (workspace_root / ".git").exists():
        raise ReplayError("WORKSPACE_GIT_METADATA_PRESENT")
    tool_data = _read_regular_bytes(
        workspace_root / "tools/historical_test_replay.py",
        code="WORKSPACE_TOOL_INVALID",
    )
    if _sha256_bytes(tool_data) != receipt["tool_sha256"]:
        raise ReplayError("WORKSPACE_TOOL_DRIFT")

    manifest_raw = _read_regular_bytes(
        workspace_root / PACKAGE_MANIFEST_COPY,
        code="WORKSPACE_PACKAGE_MANIFEST_INVALID",
    )
    if _sha256_bytes(manifest_raw) != receipt["package_manifest_sha256"]:
        raise ReplayError("WORKSPACE_PACKAGE_MANIFEST_SHA_MISMATCH")
    try:
        manifest = json.loads(manifest_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayError("WORKSPACE_PACKAGE_MANIFEST_INVALID") from exc
    if manifest.get("registry_contract_sha256") != registry_contract_sha256(registry):
        raise ReplayError("WORKSPACE_PACKAGE_REGISTRY_MISMATCH")
    if manifest.get("total_files") != receipt["fixture_total_files"]:
        raise ReplayError("WORKSPACE_FIXTURE_COUNT_MISMATCH")
    if manifest.get("total_bytes") != receipt["fixture_total_bytes"]:
        raise ReplayError("WORKSPACE_FIXTURE_BYTES_MISMATCH")
    for row in manifest["files"]:
        relative = _safe_relative_path(
            row["path"],
            code="WORKSPACE_FIXTURE_PATH_INVALID",
        )
        data = _read_regular_bytes(
            _path_from_posix(workspace_root, relative),
            code="WORKSPACE_FIXTURE_INVALID",
        )
        if len(data) != row["bytes"] or _sha256_bytes(data) != row["sha256"]:
            raise ReplayError(
                "WORKSPACE_FIXTURE_DRIFT",
                path=relative.as_posix(),
            )
    return receipt


def _sanitized_test_environment(workspace: Path) -> dict[str, str]:
    result: dict[str, str] = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONPATH": os.pathsep.join([str(workspace), str(workspace / "tools")]),
    }
    for key in ("LANG", "LC_ALL", "LC_CTYPE", "PATH"):
        value = os.environ.get(key)
        if value:
            result[key] = value
    runtime_tmp = workspace / "TEMP/historical_replay_runtime"
    runtime_tmp.mkdir(parents=True, exist_ok=False)
    result["TMPDIR"] = str(runtime_tmp)
    return result


def run_historical_replay(
    repo_root: Path = ROOT,
    *,
    commit: str,
    run_id: str,
) -> tuple[Path, int]:
    workspace = materialize_workspace(
        repo_root,
        commit=commit,
        run_id=run_id,
    )
    registry = load_registry(workspace)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "tools.historical_test_replay",
        "--historical-replay",
        *historical_nodeids(registry),
    ]
    completed = subprocess.run(
        command,
        cwd=workspace,
        env=_sanitized_test_environment(workspace),
        check=False,
    )
    run_receipt = {
        "network_or_model_calls_authorized": False,
        "node_count": len(historical_nodeids(registry)),
        "pytest_exit_code": completed.returncode,
        "run_id": run_id,
        "schema_version": "historical-test-replay-run-v1",
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }
    _write_json_exclusive(workspace / RUN_RECEIPT, run_receipt)
    return workspace, completed.returncode


_AUDIT_ACTIVE = False
_AUDIT_WRITING = False
_AUDIT_WORKSPACE: Path | None = None
_AUDIT_RUNTIME_ROOTS: tuple[Path, ...] = ()
_AUDIT_ACCESSES: set[tuple[str, str]] = set()
_AUDIT_BLOCKED: set[str] = set()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _audit_path_label(raw: object) -> tuple[str, bool]:
    if isinstance(raw, int):
        return "<file-descriptor>", True
    if raw is None:
        raw = "."
    try:
        value = os.fspath(raw)
    except TypeError:
        return "<unknown>", False
    if isinstance(value, bytes):
        value = os.fsdecode(value)
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    normalized = Path(os.path.realpath(path))
    if _AUDIT_WORKSPACE is not None and _is_within(
        normalized,
        _AUDIT_WORKSPACE,
    ):
        return normalized.relative_to(_AUDIT_WORKSPACE).as_posix(), True
    for runtime_root in _AUDIT_RUNTIME_ROOTS:
        if _is_within(normalized, runtime_root):
            relative = normalized.relative_to(runtime_root).as_posix()
            return f"<python-runtime>/{relative}", True
    if normalized == Path("/dev/null"):
        return "<device>/null", True
    return "<outside-approved-roots>", False


def _historical_replay_audit_hook(event: str, args: tuple[Any, ...]) -> None:
    if not _AUDIT_ACTIVE or _AUDIT_WRITING:
        return
    if event in NETWORK_AUDIT_EVENTS:
        _AUDIT_BLOCKED.add("network")
        raise RuntimeError("HISTORICAL_REPLAY_NETWORK_BLOCKED")
    if event in SUBPROCESS_AUDIT_EVENTS or event.startswith(SUBPROCESS_AUDIT_PREFIXES):
        _AUDIT_BLOCKED.add("subprocess")
        raise RuntimeError("HISTORICAL_REPLAY_SUBPROCESS_BLOCKED")
    if event in LINK_AUDIT_EVENTS:
        _AUDIT_BLOCKED.add("link_creation")
        raise RuntimeError("HISTORICAL_REPLAY_LINK_CREATION_BLOCKED")
    if event in (SINGLE_PATH_MUTATION_AUDIT_EVENTS | DOUBLE_PATH_MUTATION_AUDIT_EVENTS):
        path_count = 2 if event in DOUBLE_PATH_MUTATION_AUDIT_EVENTS else 1
        labels = [_audit_path_label(raw) for raw in args[:path_count]]
        within_workspace = all(
            allowed and not label.startswith("<") and _AUDIT_WORKSPACE is not None
            for label, allowed in labels
        )
        if not within_workspace:
            _AUDIT_BLOCKED.add("filesystem_mutation_outside_workspace")
            raise RuntimeError("HISTORICAL_REPLAY_EXTERNAL_MUTATION_BLOCKED")
    if event not in {"open", "os.listdir", "os.scandir"} or not args:
        return
    label, allowed = _audit_path_label(args[0])
    _AUDIT_ACCESSES.add((event, label))
    if not allowed:
        _AUDIT_BLOCKED.add("file_outside_approved_roots")
        raise RuntimeError("HISTORICAL_REPLAY_EXTERNAL_FILE_BLOCKED")


def _runtime_roots() -> tuple[Path, ...]:
    candidates = {
        Path(sys.prefix),
        Path(sys.base_prefix),
        Path(sys.executable).parent,
    }
    for value in sysconfig.get_paths().values():
        if value:
            candidates.add(Path(value))
    return tuple(
        sorted(
            {Path(os.path.realpath(path)) for path in candidates if path.exists()},
            key=lambda path: path.as_posix(),
        )
    )


def pytest_configure(config: Any) -> None:
    global _AUDIT_ACTIVE
    global _AUDIT_RUNTIME_ROOTS
    global _AUDIT_WORKSPACE
    if not config.getoption("--historical-replay", default=False):
        return
    _AUDIT_WORKSPACE = Path(os.path.realpath(Path.cwd()))
    _AUDIT_RUNTIME_ROOTS = _runtime_roots()
    _AUDIT_ACTIVE = True
    sys.addaudithook(_historical_replay_audit_hook)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    del session, exitstatus
    global _AUDIT_WRITING
    if not _AUDIT_ACTIVE or _AUDIT_WORKSPACE is None:
        return
    _AUDIT_WRITING = True
    try:
        payload = {
            "accesses": [
                {"event": event, "path": path}
                for event, path in sorted(_AUDIT_ACCESSES)
            ],
            "blocked_capabilities": sorted(_AUDIT_BLOCKED),
            "network_guard": "python_audit_hook",
            "os_level_sandbox_claimed": False,
            "schema_version": "historical-test-replay-file-access-v1",
        }
        path = _AUDIT_WORKSPACE / ACCESS_RECEIPT
        if path.exists():
            raise ReplayError("ACCESS_RECEIPT_ALREADY_EXISTS")
        _write_json_exclusive(path, payload)
    finally:
        _AUDIT_WRITING = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="封存并在隔离副本中回放 S-05-B 历史测试。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="只校验登记册、来源和已封包。")
    subparsers.add_parser("seal", help="复制历史材料到固定外置回放包。")
    for command in ("materialize", "run"):
        command_parser = subparsers.add_parser(
            command,
            help="复制固定提交和已封包材料。"
            if command == "materialize"
            else "复制后运行 40 个登记节点。",
        )
        command_parser.add_argument(
            "--commit",
            required=True,
            help="完整 40 位 Git 提交号。",
        )
        command_parser.add_argument(
            "--run-id",
            required=True,
            help="新的隔离回放运行号。",
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            payload = validate_configuration(ROOT)
        elif args.command == "seal":
            _path, manifest_sha = seal_package(ROOT)
            payload = {
                "manifest_sha256": manifest_sha,
                "package_id": load_registry(ROOT)["source_package"]["package_id"],
                "registry_update_required": True,
                "status": "SEALED_COPY_CREATED",
            }
        elif args.command == "materialize":
            workspace = materialize_workspace(
                ROOT,
                commit=args.commit,
                run_id=args.run_id,
            )
            payload = {
                "run_id": workspace.name,
                "status": "MATERIALIZED",
                "workspace_root_id": "repository_sibling_test_workspace_v1",
            }
        elif args.command == "run":
            workspace, returncode = run_historical_replay(
                ROOT,
                commit=args.commit,
                run_id=args.run_id,
            )
            payload = {
                "pytest_exit_code": returncode,
                "run_id": workspace.name,
                "status": "PASS" if returncode == 0 else "FAIL",
                "workspace_root_id": "repository_sibling_test_workspace_v1",
            }
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return returncode
        else:
            raise AssertionError("argparse accepted an unknown command")
    except ReplayError as exc:
        payload = {
            "error_code": exc.code,
            "status": "REJECTED",
        }
        if exc.path is not None:
            payload["path"] = exc.path
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
