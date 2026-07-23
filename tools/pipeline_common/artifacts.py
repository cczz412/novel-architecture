"""公共工件壳：稳定 JSON、SHA-256 与清单核验。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
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
