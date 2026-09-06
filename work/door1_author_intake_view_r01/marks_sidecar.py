"""只读、追加门 1 的本地标记；不认识候选库，也不修改候选库。"""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SIDECAR_NAME = "door1.marks.json"
SCHEMA_VERSION = 1
MAX_BYTES = 1_048_576
MAX_MARKS = 4096
MARK_KEYS = {"mark_id", "mark_type", "target_type", "target_id", "created_at"}
ENVELOPE_KEYS = {"schema_version", "view_id", "marks"}
TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
ID_RE = re.compile(r"m_[0-9a-f]{32}\Z")
VIEW_RE = re.compile(r"[0-9a-f]{64}\Z")


class MarksError(ValueError):
    """异常只带稳定编号；不给页面带入机器路径或文件原文。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def empty_document(view_id: str) -> dict[str, Any]:
    if not isinstance(view_id, str) or not VIEW_RE.fullmatch(view_id):
        raise MarksError("GAP_MARKS_SCOPE")
    return {"schema_version": SCHEMA_VERSION, "view_id": view_id, "marks": []}


def placeholder_id(mark_id: str) -> str:
    return "new_" + mark_id


def new_mark(mark_type: str, target_id: str) -> dict[str, str]:
    """时间用 UTC；界面怎么显示时间不改变这份记录。"""
    if mark_type not in {"漏抽", "重新抽"}:
        raise MarksError("GAP_MARKS_SHAPE")
    return {
        "mark_id": "m_" + uuid.uuid4().hex,
        "mark_type": mark_type,
        "target_type": "sentence" if mark_type == "漏抽" else "candidate",
        "target_id": target_id,
        "created_at": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }


def validate_document(
    value: Any,
    view_id: str,
    sentence_ids: set[str],
    candidate_ids: set[str],
) -> dict[str, Any]:
    """整份检查，不悄悄跳过坏行；后加的空候选只能来自此前的补漏标记。"""
    empty_document(view_id)
    if not isinstance(value, dict) or set(value) != ENVELOPE_KEYS:
        raise MarksError("GAP_MARKS_SHAPE")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != SCHEMA_VERSION
    ):
        raise MarksError("GAP_MARKS_SHAPE")
    if value["view_id"] != view_id:
        raise MarksError("GAP_MARKS_SCOPE")
    marks = value["marks"]
    if not isinstance(marks, list) or len(marks) > MAX_MARKS:
        raise MarksError("GAP_MARKS_SHAPE")
    seen: set[str] = set()
    known_candidates = set(candidate_ids)
    for mark in marks:
        if not isinstance(mark, dict) or set(mark) != MARK_KEYS:
            raise MarksError("GAP_MARKS_SHAPE")
        if not all(isinstance(v, str) for v in mark.values()):
            raise MarksError("GAP_MARKS_SHAPE")
        if not ID_RE.fullmatch(mark["mark_id"]) or mark["mark_id"] in seen:
            raise MarksError("GAP_MARKS_SHAPE")
        seen.add(mark["mark_id"])
        stamp = mark["created_at"]
        if not TIME_RE.fullmatch(stamp):
            raise MarksError("GAP_MARKS_SHAPE")
        try:
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise MarksError("GAP_MARKS_SHAPE") from exc
        if mark["mark_type"] == "漏抽" and mark["target_type"] == "sentence":
            if mark["target_id"] not in sentence_ids:
                raise MarksError("GAP_MARKS_TARGET")
            known_candidates.add(placeholder_id(mark["mark_id"]))
        elif mark["mark_type"] == "重新抽" and mark["target_type"] == "candidate":
            if mark["target_id"] not in known_candidates:
                raise MarksError("GAP_MARKS_TARGET")
        else:
            raise MarksError("GAP_MARKS_SHAPE")
    # 返回副本，调用方不通过引用修改已经核对过的数据。
    return json.loads(json.dumps(value, ensure_ascii=False))


def encode_document(value: dict[str, Any]) -> bytes:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise MarksError("GAP_MARKS_TOO_LARGE")
    return payload


def _safe_target(path: Path) -> None:
    if path.name != SIDECAR_NAME or path.is_symlink():
        raise MarksError("GAP_MARKS_PATH")
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise MarksError("GAP_MARKS_PATH")


def read_marks(
    path: Path,
    view_id: str,
    sentence_ids: set[str],
    candidate_ids: set[str],
) -> dict[str, Any]:
    """缺文件和坏文件分开；坏文件原样留着，页面仍然能打开。"""
    path = Path(path)
    result = {
        "status": "MISSING",
        "message": "还没有标记",
        "gap": None,
        "document": empty_document(view_id),
    }
    try:
        _safe_target(path)
        if not path.exists():
            return result
        if path.stat().st_size > MAX_BYTES:
            raise MarksError("GAP_MARKS_TOO_LARGE")
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise MarksError("GAP_MARKS_TOO_LARGE")
        value = json.loads(raw.decode("utf-8"))
        result["document"] = validate_document(
            value, view_id, sentence_ids, candidate_ids
        )
        result.update(status="OK", message="已读到标记")
    except (OSError, ValueError, UnicodeError) as exc:
        result.update(
            status="ERROR",
            message="标记没读到",
            gap=getattr(exc, "code", "GAP_MARKS_READ"),
        )
    return result


def create_if_missing(path: Path, document: dict[str, Any]) -> bool:
    """只建空边车；已经存在的边车，无论好坏都不覆盖。"""
    path = Path(path)
    _safe_target(path)
    payload = encode_document(document)
    if document.get("marks") != []:
        raise MarksError("GAP_MARKS_SHAPE")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        # 本函数新建、且尚未交付的空文件可以清理；已有文件从不碰。
        path.unlink(missing_ok=True)
        raise
    return True


@contextmanager
def _append_lock(path: Path) -> Iterator[None]:
    """只供 Python 追加使用；撞上其他进程就停，不覆盖对方刚写的记录。"""
    lock = path.with_name(".door1.marks.lock")
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise MarksError("GAP_MARKS_BUSY") from exc
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


def append_mark(
    path: Path,
    mark: dict[str, str],
    view_id: str,
    sentence_ids: set[str],
    candidate_ids: set[str],
) -> dict[str, Any]:
    """追加后原子替换 JSON；这里没有服务端接口，浏览器走自己的文件授权。"""
    path = Path(path)
    _safe_target(path)
    with _append_lock(path):
        current = read_marks(path, view_id, sentence_ids, candidate_ids)
        if current["status"] == "ERROR":
            raise MarksError(current["gap"])
        document = current["document"]
        for old in document["marks"]:
            if old["mark_id"] == mark.get("mark_id"):
                if old != mark:
                    raise MarksError("GAP_MARKS_CONFLICT")
                return document
        document["marks"].append(mark)
        document = validate_document(document, view_id, sentence_ids, candidate_ids)
        payload = encode_document(document)
        temporary = path.with_name(".door1.marks." + uuid.uuid4().hex + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            _safe_target(path)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return document
