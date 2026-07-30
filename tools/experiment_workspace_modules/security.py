from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .contracts import sha256_bytes


SENSITIVE_FILENAME_PATTERN = re.compile(
    r"(^|/)(\.env($|\.)|id_(rsa|dsa|ecdsa|ed25519)$|"
    r"[^/]+\.(pem|key|p12|pfx|jks|keystore))",
    re.IGNORECASE,
)
SENSITIVE_CONTENT_RULES = (
    (
        "AUTHORIZATION_HEADER",
        re.compile(
            rb"""(?imx)
            (?:^|[{\s,])
            ["']?authorization["']?
            \s*[:=]\s*
            ["']?(?:bearer|basic)\s+[A-Za-z0-9._~+/-]{8,}
            """
        ),
    ),
    (
        "BEARER_TOKEN",
        re.compile(
            rb"""(?ix)
            \bbearer\s+
            (?!<|\$\{|your[-_]|example[-_]|placeholder)
            [A-Za-z0-9._~+/-]{12,}
            """
        ),
    ),
    (
        "API_KEY_HEADER",
        re.compile(rb"(?im)^\s*x-api-key\s*:\s*\S+"),
    ),
    (
        "PRIVATE_KEY_BLOCK",
        re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    ),
    (
        "JWT_TOKEN",
        re.compile(rb"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    (
        "ASSIGNED_SECRET",
        re.compile(
            rb"""(?ix)
            ["']?(?:api[_-]?key|access[_-]?token|secret|password)["']?
            \s*[:=]\s*
            ["']?[A-Za-z0-9_./+=-]{12,}
            """
        ),
    ),
    (
        "PRIVATE_ABSOLUTE_PATH",
        re.compile(rb"(?:^|[\s\"'])/Users/[^/\s\"']+/"),
    ),
)
SENSITIVE_RULE_IDS = (
    "SENSITIVE_FILENAME",
    *(rule_id for rule_id, _ in SENSITIVE_CONTENT_RULES),
)


class SecurityError(ValueError):
    def __init__(self, code: str, path: str | None = None):
        super().__init__(code)
        self.code = code
        self.path = path


@dataclass(frozen=True)
class FileSnapshot:
    data: bytes
    size: int
    sha256: str
    device: int
    inode: int
    mtime_ns: int
    links: int


def _directory_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def open_directory(path: Path) -> int:
    try:
        return os.open(path, _directory_flags())
    except OSError as exc:
        raise SecurityError("DIRECTORY_OPEN_REJECTED") from exc


def open_directory_at(
    parent_fd: int,
    name: str,
    *,
    create: bool,
    mode: int = 0o700,
) -> int:
    if not name or name in {".", ".."} or "/" in name:
        raise SecurityError("DIRECTORY_COMPONENT_INVALID")
    if create:
        try:
            os.mkdir(name, mode=mode, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as exc:
            raise SecurityError("DIRECTORY_CREATE_REJECTED", name) from exc
    try:
        return os.open(name, _directory_flags(), dir_fd=parent_fd)
    except OSError as exc:
        try:
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError:
            info = None
        if info is not None and stat.S_ISLNK(info.st_mode):
            raise SecurityError("SYMLINK_REJECTED", name) from exc
        raise SecurityError("DIRECTORY_COMPONENT_REJECTED", name) from exc


def open_directory_chain(
    root_fd: int,
    parts: tuple[str, ...],
    *,
    create: bool,
) -> int:
    current = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = open_directory_at(current, part, create=create)
            os.close(current)
            current = next_fd
        return current
    except Exception:
        os.close(current)
        raise


def read_regular_file_at(root_fd: int, relative: str) -> FileSnapshot:
    parts = tuple(relative.split("/"))
    if not parts or any(not part or part in {".", ".."} for part in parts):
        raise SecurityError("SOURCE_PATH_INVALID", relative)
    parent_fd = open_directory_chain(root_fd, parts[:-1], create=False)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        try:
            descriptor = os.open(parts[-1], flags, dir_fd=parent_fd)
        except OSError as exc:
            raise SecurityError("SOURCE_OPEN_REJECTED", relative) from exc
    finally:
        os.close(parent_fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SecurityError("SOURCE_NOT_REGULAR_FILE", relative)
        if before.st_nlink != 1:
            raise SecurityError("HARDLINK_REJECTED", relative)
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read()
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_nlink,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_nlink,
    )
    if identity_before != identity_after or len(data) != after.st_size:
        raise SecurityError("SOURCE_CHANGED_DURING_READ", relative)
    return FileSnapshot(
        data=data,
        size=len(data),
        sha256=sha256_bytes(data),
        device=after.st_dev,
        inode=after.st_ino,
        mtime_ns=after.st_mtime_ns,
        links=after.st_nlink,
    )


def read_regular_file(root: Path, relative: str) -> FileSnapshot:
    root_fd = open_directory(root)
    try:
        return read_regular_file_at(root_fd, relative)
    finally:
        os.close(root_fd)


def write_new_file_at(
    root_fd: int,
    relative: str,
    data: bytes,
    *,
    mode: int = 0o600,
) -> FileSnapshot:
    parts = tuple(relative.split("/"))
    if not parts or any(not part or part in {".", ".."} for part in parts):
        raise SecurityError("TARGET_PATH_INVALID", relative)
    parent_fd = open_directory_chain(root_fd, parts[:-1], create=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        try:
            descriptor = os.open(
                parts[-1],
                flags,
                mode,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise SecurityError("TARGET_CREATE_REJECTED", relative) from exc
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return read_regular_file_at(root_fd, relative)


def sensitive_rule_for(relative: str, data: bytes) -> str | None:
    if SENSITIVE_FILENAME_PATTERN.search(relative):
        return "SENSITIVE_FILENAME"
    for rule_id, pattern in SENSITIVE_CONTENT_RULES:
        if pattern.search(data):
            return rule_id
    return None
