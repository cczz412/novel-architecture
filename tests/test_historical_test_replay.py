from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import historical_test_replay as replay


ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _registry(source_manifest_sha: str) -> dict:
    nodeids = [
        f"tests/test_fake.py::FakeTests::test_case_{index:02d}" for index in range(40)
    ]
    return {
        "schema_version": "historical-test-replay-registry-v1",
        "registry_id": "S05B-SYNTHETIC-01",
        "decision": {
            "authority": "CZ",
            "choice": "S-05-B",
            "source_text": "S-05-B",
            "source_text_sha256": hashlib.sha256(b"S-05-B").hexdigest(),
        },
        "default_collection": {
            "mode": "deselect_exact",
            "marker": "historical_replay",
            "node_count": 40,
        },
        "program_snapshot": {
            "source": "git_archive_resolved_commit",
            "dirty_worktree_included": False,
            "internal_symlink_mode": ("copy_tracked_target_bytes_as_regular_file"),
            "allowed_omitted_symlinks": ["corpus-downloads"],
        },
        "source_package": {
            "package_id": "historical_test_replay_synthetic_v1",
            "status": "unsealed",
            "external_root_id": "repository_sibling_external_archive_v1",
            "relative_path": "historical_test_replay_synthetic_v1",
            "manifest_sha256": None,
        },
        "source_roots": [
            {
                "root_id": "archive_batch_20260723",
                "kind": "fixed_sibling_archive_batch",
                "relative_path": "archive_batch_20260723",
                "manifest_sha256": source_manifest_sha,
            },
            {
                "root_id": "repository_local_ignored",
                "kind": "repository_local_ignored",
            },
        ],
        "source_units": [
            {
                "unit_id": "external_run",
                "root_id": "archive_batch_20260723",
                "repo_relative_path": "runs/external",
                "kind": "directory",
            },
            {
                "unit_id": "local_run",
                "root_id": "repository_local_ignored",
                "repo_relative_path": "runs/local",
                "kind": "directory",
            },
        ],
        "groups": [
            {
                "group_id": "synthetic_history",
                "reason": "合成历史材料只用于复制器机械测试。",
                "nodeids": nodeids,
                "source_unit_ids": ["external_run", "local_run"],
            }
        ],
    }


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    external_root = tmp_path / "repo_外置仓"
    archive = external_root / "archive_batch_20260723"
    archive.mkdir(parents=True)
    _write_json(archive / "MANIFEST.json", {"fixture": "source-root"})
    (archive / "runs/external").mkdir(parents=True)
    (archive / "runs/external/b.txt").write_text(
        "external\n",
        encoding="utf-8",
    )

    (repo / "config/test_replay").mkdir(parents=True)
    shutil.copy2(
        ROOT / "config/test_replay/historical_replays_v1.schema.json",
        repo / "config/test_replay/historical_replays_v1.schema.json",
    )
    value = _registry(_sha256(archive / "MANIFEST.json"))
    _write_json(
        repo / "config/test_replay/historical_replays.json",
        value,
    )
    (repo / "runs/local").mkdir(parents=True)
    (repo / "runs/local/a.txt").write_text("local\n", encoding="utf-8")
    (repo / "tools").mkdir()
    shutil.copy2(
        ROOT / "tools/historical_test_replay.py",
        repo / "tools/historical_test_replay.py",
    )
    (repo / "tools/target.py").write_text(
        "VALUE = 'tracked target'\n",
        encoding="utf-8",
    )
    (repo / "tools/alias.py").symlink_to("target.py")
    (repo / "corpus-downloads").symlink_to(".local/corpus-downloads")
    (repo / "tests").mkdir()
    methods = "\n".join(
        f"    def test_case_{index:02d}(self):\n        pass\n" for index in range(40)
    )
    (repo / "tests/test_fake.py").write_text(
        f"class FakeTests:\n{methods}",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text("runs/\n", encoding="utf-8")

    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Codex Test")
    _git(repo, "config", "user.email", "codex-test@example.invalid")
    return repo, external_root


def _seal_registry(repo: Path) -> tuple[dict, Path]:
    package_path, manifest_sha = replay.seal_package(repo)
    registry_path = repo / replay.REGISTRY_RELATIVE
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["source_package"]["status"] = "sealed"
    registry["source_package"]["manifest_sha256"] = manifest_sha
    _write_json(registry_path, registry)
    return registry, package_path


def _commit(repo: Path) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "synthetic replay fixture")
    return _git(repo, "rev-parse", "HEAD")


def test_seal_and_materialize_copy_commit_and_fixture_bytes(
    tmp_path: Path,
) -> None:
    repo, _external = _make_repo(tmp_path)
    registry, _package = _seal_registry(repo)
    commit = _commit(repo)

    workspace = replay.materialize_workspace(
        repo,
        commit=commit,
        run_id="s05b-test-001",
    )

    assert not (workspace / ".git").exists()
    assert not (workspace / "corpus-downloads").exists()
    alias = workspace / "tools/alias.py"
    assert alias.is_file()
    assert not alias.is_symlink()
    assert alias.read_bytes() == (workspace / "tools/target.py").read_bytes()
    assert (workspace / "runs/local/a.txt").read_text() == "local\n"
    assert (workspace / "runs/external/b.txt").read_text() == "external\n"
    receipt = replay.verify_materialization_receipt(workspace)
    assert receipt["program_commit"] == commit
    assert receipt["nodeids"] == replay.historical_nodeids(registry)
    assert receipt["program_snapshot"]["omitted_symlinks"] == ["corpus-downloads"]
    assert receipt["program_snapshot"]["converted_symlinks"] == [
        {"path": "tools/alias.py", "target": "tools/target.py"}
    ]


def test_unsealed_registry_blocks_materialization(tmp_path: Path) -> None:
    repo, _external = _make_repo(tmp_path)
    with pytest.raises(replay.ReplayError, match="PACKAGE_NOT_SEALED"):
        replay.materialize_workspace(
            repo,
            commit="HEAD",
            run_id="s05b-unsealed",
        )


def test_package_payload_drift_is_rejected(tmp_path: Path) -> None:
    repo, _external = _make_repo(tmp_path)
    registry, package = _seal_registry(repo)
    payload = package / "payload/runs/local/a.txt"
    payload.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(replay.ReplayError, match="PACKAGE_PAYLOAD_DRIFT"):
        replay.validate_package(repo, registry)


def test_source_symlink_is_rejected_before_package_publish(
    tmp_path: Path,
) -> None:
    repo, _external = _make_repo(tmp_path)
    (repo / "runs/local/link.txt").symlink_to("a.txt")
    with pytest.raises(replay.ReplayError, match="SOURCE_SYMLINK_REJECTED"):
        replay.seal_package(repo)
    assert not (tmp_path / "repo_外置仓/historical_test_replay_synthetic_v1").exists()


def test_source_hardlink_is_rejected_before_package_publish(
    tmp_path: Path,
) -> None:
    repo, _external = _make_repo(tmp_path)
    os.link(
        repo / "runs/local/a.txt",
        repo / "runs/local/second.txt",
    )
    with pytest.raises(replay.ReplayError, match="SOURCE_HARDLINK_REJECTED"):
        replay.seal_package(repo)
    assert not (tmp_path / "repo_外置仓/historical_test_replay_synthetic_v1").exists()


def test_existing_workspace_is_never_overwritten(tmp_path: Path) -> None:
    repo, _external = _make_repo(tmp_path)
    _registry_value, _package = _seal_registry(repo)
    commit = _commit(repo)
    replay.materialize_workspace(
        repo,
        commit=commit,
        run_id="s05b-no-overwrite",
    )
    with pytest.raises(replay.ReplayError, match="WORKSPACE_ALREADY_EXISTS"):
        replay.materialize_workspace(
            repo,
            commit=commit,
            run_id="s05b-no-overwrite",
        )


def test_corpus_pointer_must_stay_an_omitted_symlink(
    tmp_path: Path,
) -> None:
    repo, _external = _make_repo(tmp_path)
    _registry_value, _package = _seal_registry(repo)
    (repo / "corpus-downloads").unlink()
    (repo / "corpus-downloads").write_text(
        "must not become tracked content\n",
        encoding="utf-8",
    )
    commit = _commit(repo)

    with pytest.raises(
        replay.ReplayError,
        match="GIT_ARCHIVE_OMITTED_PATH_NOT_SYMLINK",
    ):
        replay.materialize_workspace(
            repo,
            commit=commit,
            run_id="s05b-corpus-guard",
        )


def test_paths_and_commit_argument_cannot_be_injected(
    tmp_path: Path,
) -> None:
    repo, _external = _make_repo(tmp_path)
    with pytest.raises(replay.ReplayError, match="RUN_ID_INVALID"):
        replay.materialize_workspace(
            repo,
            commit="HEAD",
            run_id="../escape",
        )
    with pytest.raises(replay.ReplayError, match="COMMIT_ARGUMENT_INVALID"):
        replay.resolve_commit(repo, "--help")
    with pytest.raises(replay.ReplayError, match="COMMIT_ARGUMENT_INVALID"):
        replay.resolve_commit(repo, "HEAD")

    registry_path = repo / replay.REGISTRY_RELATIVE
    value = json.loads(registry_path.read_text(encoding="utf-8"))
    value["source_units"][0]["repo_relative_path"] = "../outside"
    _write_json(registry_path, value)
    with pytest.raises(replay.ReplayError, match="SOURCE_UNIT_PATH_INVALID"):
        replay.load_registry(repo)


def test_test_environment_drops_credentials_and_uses_workspace_tmp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("SENSENOVA_API_KEY", "must-not-leak")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-leak")

    environment = replay._sanitized_test_environment(workspace)

    assert "SENSENOVA_API_KEY" not in environment
    assert "UNRELATED_SECRET" not in environment
    assert environment["TMPDIR"] == str(workspace / "TEMP/historical_replay_runtime")
    assert Path(environment["TMPDIR"]).is_dir()


@pytest.mark.parametrize(
    ("event", "message"),
    [
        ("socket.connect", "HISTORICAL_REPLAY_NETWORK_BLOCKED"),
        ("subprocess.Popen", "HISTORICAL_REPLAY_SUBPROCESS_BLOCKED"),
        ("os.symlink", "HISTORICAL_REPLAY_LINK_CREATION_BLOCKED"),
        ("os.link", "HISTORICAL_REPLAY_LINK_CREATION_BLOCKED"),
    ],
)
def test_runtime_audit_hook_blocks_network_and_subprocess(
    event: str,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(replay, "_AUDIT_ACTIVE", True)
    with pytest.raises(RuntimeError, match=message):
        replay._historical_replay_audit_hook(event, ())


def test_runtime_audit_resolves_workspace_symlink_before_allowing_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside\n", encoding="utf-8")
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(replay, "_AUDIT_ACTIVE", True)
    monkeypatch.setattr(replay, "_AUDIT_WORKSPACE", workspace)
    monkeypatch.setattr(replay, "_AUDIT_RUNTIME_ROOTS", ())

    label, allowed = replay._audit_path_label(workspace / "escape/secret.txt")

    assert label == "<outside-approved-roots>"
    assert allowed is False
    with pytest.raises(
        RuntimeError,
        match="HISTORICAL_REPLAY_EXTERNAL_FILE_BLOCKED",
    ):
        replay._historical_replay_audit_hook(
            "open",
            (workspace / "escape/secret.txt", "r", 0),
        )


@pytest.mark.parametrize(
    ("event", "args"),
    [
        ("os.remove", ("outside.txt", -1)),
        ("os.rename", ("outside.txt", "inside.txt", -1, -1)),
    ],
)
def test_runtime_audit_blocks_mutation_outside_workspace(
    event: str,
    args: tuple[object, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(replay, "_AUDIT_ACTIVE", True)
    monkeypatch.setattr(replay, "_AUDIT_WORKSPACE", workspace)
    monkeypatch.setattr(replay, "_AUDIT_RUNTIME_ROOTS", ())

    with pytest.raises(
        RuntimeError,
        match="HISTORICAL_REPLAY_EXTERNAL_MUTATION_BLOCKED",
    ):
        replay._historical_replay_audit_hook(event, args)
