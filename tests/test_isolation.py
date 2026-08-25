from __future__ import annotations

import os
import socket
import threading
from pathlib import Path

import pytest
from isolation import (
    VENDOR_API_KEY_ENVS,
    GitNotAvailableError,
    NetworkBlockedError,
    frozen_zip_bytes,
    run_git,
)


def test_vendor_api_keys_are_cleared_for_the_session() -> None:
    for name in VENDOR_API_KEY_ENVS:
        assert name not in os.environ, name


def test_outbound_tcp_is_blocked_by_default() -> None:
    with pytest.raises(NetworkBlockedError, match="pytest default network is blocked"):
        socket.create_connection(("1.1.1.1", 443), timeout=1)


def test_localhost_tcp_is_not_blocked() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = int(server.getsockname()[1])
    accepted = threading.Event()

    def _accept_once() -> None:
        connection, _peer = server.accept()
        connection.close()
        accepted.set()

    worker = threading.Thread(target=_accept_once, daemon=True)
    worker.start()
    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    client.close()
    assert accepted.wait(2)
    server.close()
    worker.join(timeout=2)


@pytest.mark.allow_network
def test_allow_network_marker_skips_default_network_guard(
    _block_outbound_network: bool,
) -> None:
    assert _block_outbound_network is False


def test_git_init_stays_sha1_when_global_config_wants_sha256_and_gpgsign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile = tmp_path / "hostile.gitconfig"
    hostile.write_text(
        "[commit]\n"
        "\tgpgsign = true\n"
        "[init]\n"
        "\tdefaultObjectFormat = sha256\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile))
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git("init", "-q", cwd=repo)
    run_git("config", "user.email", "iso@example.invalid", cwd=repo)
    run_git("config", "user.name", "isolation", cwd=repo)
    (repo / "seed.txt").write_text("ok\n", encoding="utf-8")
    run_git("add", "seed.txt", cwd=repo)
    run_git("commit", "-qm", "seed", cwd=repo)
    sha = run_git("rev-parse", "HEAD", cwd=repo, text=True).stdout.strip()
    fmt = run_git(
        "rev-parse",
        "--show-object-format",
        cwd=repo,
        text=True,
    ).stdout.strip()
    assert len(sha) == 40
    assert fmt == "sha1"


def test_missing_git_raises_stable_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    with pytest.raises(GitNotAvailableError, match="git executable is not available"):
        run_git("status", cwd=tmp_path)


def test_frozen_zip_bytes_are_stable() -> None:
    first = frozen_zip_bytes({"chapter.txt": "第一章\n".encode()})
    second = frozen_zip_bytes({"chapter.txt": "第一章\n".encode()})
    assert first == second
    assert first[:2] == b"PK"
