from __future__ import annotations

import errno
import io
import os
import socket
import stat
import subprocess
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


VENDOR_API_KEY_ENVS: tuple[str, ...] = (
    "DASHSCOPE_API_KEY",
    "DASHSCOPE_API_KEY_FILE",
    "SENSENOVA_API_KEY",
    "TENCENT_TOKENHUB_API_KEY",
    "SILICONFLOW_API_KEY",
    "ANT_LING_API_KEY",
    "ARK_API_KEY",
    "LONGCAT_API_KEY",
    "DEEPSEEK_API_KEY",
    "VOLCENGINE_AGENT_PLAN_API_KEY",
)

LOCAL_NETWORK_HOSTS = frozenset(
    {
        "127.0.0.1",
        "::1",
        "0:0:0:0:0:0:0:1",
        "localhost",
    }
)

FROZEN_ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)

_GIT_CONFIG_PAIRS: tuple[tuple[str, str], ...] = (
    ("commit.gpgsign", "false"),
    ("core.hooksPath", os.devnull),
    ("init.defaultObjectFormat", "sha1"),
)


class NetworkBlockedError(OSError):
    """pytest 默认断网时，外联 socket 被拦住。"""


class GitNotAvailableError(RuntimeError):
    """测试要跑 Git 时 PATH 里没有 git，给出稳定错误而不是 FileNotFoundError。"""


def host_is_localhost(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized.startswith("::ffff:"):
        normalized = normalized.removeprefix("::ffff:")
    return normalized in LOCAL_NETWORK_HOSTS


def clear_vendor_api_keys(monkeypatch: Any) -> None:
    for name in VENDOR_API_KEY_ENVS:
        monkeypatch.delenv(name, raising=False)


def isolated_git_environ(base: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_COUNT"] = str(len(_GIT_CONFIG_PAIRS))
    for index, (key, value) in enumerate(_GIT_CONFIG_PAIRS):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value
    return env


def apply_isolated_git_environ(monkeypatch: Any) -> None:
    env = isolated_git_environ()
    for key in (
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_COUNT",
        *(f"GIT_CONFIG_KEY_{index}" for index in range(len(_GIT_CONFIG_PAIRS))),
        *(f"GIT_CONFIG_VALUE_{index}" for index in range(len(_GIT_CONFIG_PAIRS))),
    ):
        monkeypatch.setenv(key, env[key])


def git_isolation_argv() -> list[str]:
    argv: list[str] = []
    for key, value in _GIT_CONFIG_PAIRS:
        argv.extend(["-c", f"{key}={value}"])
    return argv


def _with_sha1_init(args: tuple[str, ...]) -> tuple[str, ...]:
    if not args or args[0] != "init":
        return args
    if any(item == "--object-format=sha1" or item.startswith("--object-format=") for item in args):
        return args
    return ("init", "--object-format=sha1", *args[1:])


def run_git(
    *args: str,
    cwd: Path | str | None = None,
    check: bool = True,
    text: bool = False,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[Any]:
    argv = ["git", *git_isolation_argv(), *_with_sha1_init(args)]
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=text,
            env=isolated_git_environ(env),
        )
    except FileNotFoundError as exc:
        raise GitNotAvailableError(
            "git executable is not available; test Git operations need git on PATH"
        ) from exc
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            argv,
            completed.stdout,
            completed.stderr,
        )
    return completed


def _blocked_tcp_host(sock: socket.socket, address: Any) -> str | None:
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return None
    host = address[0] if isinstance(address, tuple) and address else None
    if host is None or host_is_localhost(str(host)):
        return None
    return str(host)


def install_network_guard(monkeypatch: Any) -> None:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def guarded_connect(self: socket.socket, address: Any) -> None:
        host = _blocked_tcp_host(self, address)
        if host is not None:
            raise NetworkBlockedError(
                f"pytest default network is blocked: {host!r}"
            )
        return original_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any) -> int:
        host = _blocked_tcp_host(self, address)
        if host is not None:
            return errno.EHOSTUNREACH
        return original_connect_ex(self, address)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        host = address[0] if isinstance(address, tuple) and address else address
        if not host_is_localhost(str(host) if host is not None else None):
            raise NetworkBlockedError(
                f"pytest default network is blocked: {host!r}"
            )
        return original_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)


def frozen_zip_info(name: str) -> zipfile.ZipInfo:
    return zipfile.ZipInfo(filename=name, date_time=FROZEN_ZIP_DATE_TIME)


def frozen_zip_bytes(
    members: dict[str, bytes],
    *,
    symlink: str | None = None,
    symlink_target: bytes = b"target.txt",
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in members.items():
            archive.writestr(frozen_zip_info(name), payload)
        if symlink is not None:
            info = frozen_zip_info(symlink)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, symlink_target)
    return buffer.getvalue()
