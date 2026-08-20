"""M1 上传对象：把不受信任的逻辑名和原始 bytes 交给格式路由核心。

本模块不落盘、不连接云服务。未来云端只需在 CLOUD_SWAP_POINT 构造同一个
UploadSource；受信任本地 CLI 则通过 LOCAL_FILESYSTEM_ONLY 适配器读取文件。
"""

from __future__ import annotations

import codecs
import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


CLOUD_SWAP_POINT = "UPLOAD_SOURCE_CONSTRUCTION"
LOCAL_FILESYSTEM_ONLY = "LOCAL_FILESYSTEM_ONLY"


def _validate_source_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or value in {".", ".."}:
        raise ValueError("UPLOAD_SOURCE_NAME_INVALID")
    if "\x00" in value or ".." in value or "/" in value or "\\" in value:
        raise ValueError("UPLOAD_SOURCE_NAME_UNSAFE")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or ".." in posix.parts:
        raise ValueError("UPLOAD_SOURCE_NAME_UNSAFE")
    return value


def _validate_declarations(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        if any(not isinstance(item, dict) for item in value):
            raise ValueError("UPLOAD_DECLARATIONS_INVALID")
        return copy.deepcopy(value)
    if isinstance(value, dict):
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(items, list)
            or any(not isinstance(item, dict) for item in items)
            for name, items in value.items()
        ):
            raise ValueError("UPLOAD_DECLARATIONS_INVALID")
        return copy.deepcopy(value)
    raise ValueError("UPLOAD_DECLARATIONS_INVALID")


@dataclass(frozen=True, slots=True)
class UploadSource:
    source_name: str
    raw_bytes: bytes
    declarations: list[dict[str, Any]] | dict[str, list[dict[str, Any]]] | None = None
    encoding_hint: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_name", _validate_source_name(self.source_name))
        if not isinstance(self.raw_bytes, bytes):
            raise ValueError("UPLOAD_RAW_BYTES_REQUIRED")
        object.__setattr__(self, "declarations", _validate_declarations(self.declarations))
        if self.encoding_hint is not None:
            if not isinstance(self.encoding_hint, str) or not self.encoding_hint:
                raise ValueError("UPLOAD_ENCODING_HINT_INVALID")
            try:
                codecs.lookup(self.encoding_hint)
            except LookupError as exc:
                raise ValueError("UPLOAD_ENCODING_HINT_INVALID") from exc

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()

    def caller_record(self) -> dict[str, Any]:
        """调用方可把这一对象交给未来 AuthorWorkspace 保存；本票只返回，不落盘。"""
        return {
            "source_name": self.source_name,
            "raw_bytes": self.raw_bytes,
            "source_sha256": self.sha256,
            "bytes": len(self.raw_bytes),
            "declarations": copy.deepcopy(self.declarations),
            "encoding_hint": self.encoding_hint,
            "cloud_swap_point": CLOUD_SWAP_POINT,
        }


def from_local_path(value: str) -> UploadSource:
    """LOCAL_FILESYSTEM_ONLY：受信任本地 CLI 读文件后立刻转换为 UploadSource。"""
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在或不是普通文件：{path}")
    return UploadSource(source_name=path.name, raw_bytes=path.read_bytes())
