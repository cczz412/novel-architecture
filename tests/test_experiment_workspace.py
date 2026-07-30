from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
from pathlib import Path

import pytest

from tools.experiment_workspace import build_parser
from tools.experiment_workspace_modules.contracts import (
    ALLOWLIST_CONTRACT_ID,
    CAPABILITY_LIMITS,
    allowlist_contract_sha256,
    canonical_json_sha256,
    materializer_bundle_sha256,
)
from tools.experiment_workspace_modules.materialize import (
    MaterializeError,
    S0_ELIGIBLE_WRITE_PATHS,
    S0_REQUIRED_CHECK_IDS,
    materialize,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/experiment_workspace/source"
HEAD_SHA = "a" * 40
MATERIALIZE_MODULE = importlib.import_module(
    "tools.experiment_workspace_modules.materialize"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git/HEAD").write_text(f"{HEAD_SHA}\n", encoding="ascii")
    shutil.copytree(
        ROOT / "tools/experiment_workspace_modules",
        repo / "tools/experiment_workspace_modules",
    )
    shutil.copy2(
        ROOT / "tools/experiment_workspace.py",
        repo / "tools/experiment_workspace.py",
    )
    shutil.copytree(
        FIXTURE_ROOT,
        repo / "tests/fixtures/experiment_workspace/source",
    )
    wave_plan_relative = (
        "TEMP/restructure_wave_preflight/test/S0_MATERIALIZE_PLAN.json"
    )
    wave_plan = {
        "capability_limits": {
            **CAPABILITY_LIMITS,
            "register_only": False,
        },
        "contract_version": "repository-restructure-wave-plan-v1",
        "expected_head_sha": HEAD_SHA,
        "plan_id": "S0-TEST-WAVE-PLAN-001",
        "route": "S0",
        "wave_id": "S0_MATERIALIZE_ONLY",
    }
    _write_json(repo / wave_plan_relative, wave_plan)
    receipt = {
        "authorization_boundary": {
            "authorization_context_claim_is_cryptographic_proof": False,
            "authorizes_delete": False,
            "authorizes_external_removal": False,
            "authorizes_model_api": False,
            "authorizes_notion_write": False,
            "authorizes_physical_move": False,
            "authorizes_preflight": False,
            "authorizes_wave": False,
            "eligible_wave_id": "S0_MATERIALIZE_ONLY",
            "eligible_write_paths": S0_ELIGIBLE_WRITE_PATHS,
            "mechanical_preconditions_pass": True,
            "requires_same_task_human_readback": True,
        },
        "blockers": [],
        "checks": [
            {
                "check_id": check_id,
                "evidence": {},
                "passed": True,
            }
            for check_id in sorted(S0_REQUIRED_CHECK_IDS)
        ],
        "contract_version": "repository-restructure-wave-receipt-v1",
        "evaluated_at": "2026-07-30T08:00:00+00:00",
        "evidence_snapshot": [
            {
                "path": wave_plan_relative,
                "sha256": _sha256(repo / wave_plan_relative),
            }
        ],
        "head_sha": HEAD_SHA,
        "plan_content_sha256": canonical_json_sha256(wave_plan),
        "plan_id": "S0-TEST-WAVE-PLAN-001",
        "responsibility_window": {
            "wave_id": "S0_MATERIALIZE_ONLY",
        },
        "route": "S0",
        "runtime_effects": {
            "model_api_calls": 0,
            "network_attempts": 0,
            "receipt_writes": 1,
            "tracked_repository_writes": 0,
        },
        "status": "PASS",
        "wave_id": "S0_MATERIALIZE_ONLY",
    }
    _write_json(
        repo
        / "TEMP/restructure_wave_preflight/test/S0_MATERIALIZE_RECEIPT.json",
        receipt,
    )
    return repo


def _plan(
    repo: Path,
    *,
    run_id: str = "s0-test-001",
    source: str = (
        "tests/fixtures/experiment_workspace/source/program/hello.py"
    ),
    destination: str = "workspace/program/hello.py",
    role: str = "program",
) -> str:
    source_path = repo / source
    receipt_relative = (
        "TEMP/restructure_wave_preflight/test/"
        "S0_MATERIALIZE_RECEIPT.json"
    )
    wave_plan_relative = (
        "TEMP/restructure_wave_preflight/test/S0_MATERIALIZE_PLAN.json"
    )
    value = {
        "allowlist_contract_id": ALLOWLIST_CONTRACT_ID,
        "allowlist_contract_sha256": allowlist_contract_sha256(),
        "capability_limits": CAPABILITY_LIMITS,
        "contract_version": "experiment-materialize-plan-v1",
        "expected_head_sha": HEAD_SHA,
        "items": [
            {
                "bytes": source_path.stat().st_size,
                "destination": destination,
                "role": role,
                "sha256": _sha256(source_path),
                "source": source,
                "source_type": "file",
            }
        ],
        "materializer_bundle_sha256": materializer_bundle_sha256(repo),
        "plan_id": "S0-TEST-PLAN-001",
        "revision": 1,
        "run_id": run_id,
        "s0_receipt": {
            "path": receipt_relative,
            "sha256": _sha256(repo / receipt_relative),
            "wave_plan_path": wave_plan_relative,
            "wave_plan_sha256": _sha256(repo / wave_plan_relative),
        },
    }
    relative = "tests/fixtures/experiment_workspace/materialize_plan.json"
    _write_json(repo / relative, value)
    return relative


def test_cli_exposes_only_materialize_command() -> None:
    parser = build_parser()
    assert parser.parse_args(
        [
            "materialize",
            "--plan",
            "experiments/example/materialize_plan.json",
        ]
    ).command == "materialize"
    for forbidden in ("preflight", "run", "seal", "status"):
        with pytest.raises(SystemExit):
            parser.parse_args([forbidden])


def test_materialize_copies_registered_file_and_binds_receipts(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    source = (
        repo
        / "tests/fixtures/experiment_workspace/source/program/hello.py"
    )
    source_before = source.stat()
    source_bytes_before = source.read_bytes()

    output = materialize(repo_root=repo, plan_relative=plan_relative)

    copied = output / "workspace/program/hello.py"
    source_after = source.stat()
    assert copied.read_bytes() == source_bytes_before == source.read_bytes()
    assert (
        source_after.st_dev,
        source_after.st_ino,
        source_after.st_size,
        source_after.st_mtime_ns,
    ) == (
        source_before.st_dev,
        source_before.st_ino,
        source_before.st_size,
        source_before.st_mtime_ns,
    )
    identity = json.loads(
        (output / "RUN_IDENTITY.json").read_text(encoding="utf-8")
    )
    receipt = json.loads(
        (output / "receipts/COPY_RECEIPT.json").read_text(encoding="utf-8")
    )
    assert identity["state"] == "materialized"
    assert identity["previous_state"] == "reserved"
    assert receipt["scope"] == "copy_only"
    assert receipt["isolation_verified"] is False
    assert receipt["capability_limits"] == CAPABILITY_LIMITS
    assert receipt["sensitive_scan"]["result"] == "PASS"
    assert receipt["workspace_files"] == [
        {
            "bytes": copied.stat().st_size,
            "path": "workspace/program/hello.py",
            "role": "program",
            "sha256": _sha256(copied),
            "source": (
                "tests/fixtures/experiment_workspace/"
                "source/program/hello.py"
            ),
        }
    ]


def test_same_run_id_cannot_be_materialized_twice(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    materialize(repo_root=repo, plan_relative=plan_relative)

    with pytest.raises(MaterializeError, match="RUN_OUTPUT_ALREADY_EXISTS"):
        materialize(repo_root=repo, plan_relative=plan_relative)


def test_source_change_after_plan_is_rejected_without_copy(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    source = (
        repo
        / "tests/fixtures/experiment_workspace/source/program/hello.py"
    )
    source.write_text("changed\n", encoding="utf-8")

    with pytest.raises(MaterializeError, match="SOURCE_SIZE_MISMATCH"):
        materialize(repo_root=repo, plan_relative=plan_relative)

    assert not (repo / "runs/s0-test-001").exists()
    assert not (repo / "runs/.locks/s0-test-001.lock").exists()


def test_sensitive_source_is_rejected_before_lock_or_copy(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    source_relative = (
        "tests/fixtures/experiment_workspace/source/program/secret.py"
    )
    source = repo / source_relative
    source.write_text(
        'api_key = "not-a-real-secret-value"\n',
        encoding="utf-8",
    )
    plan_relative = _plan(repo, source=source_relative)

    with pytest.raises(MaterializeError, match="ASSIGNED_SECRET"):
        materialize(repo_root=repo, plan_relative=plan_relative)

    assert not (repo / "runs/s0-test-001").exists()
    assert not (repo / "runs/.locks/s0-test-001.lock").exists()
    assert not (repo / "runs/.staging").exists()


@pytest.mark.parametrize(
    "field",
    [
        "authorizes_delete",
        "authorizes_external_removal",
        "authorizes_model_api",
        "authorizes_notion_write",
        "authorizes_physical_move",
        "authorizes_preflight",
        "authorizes_wave",
        "authorizes_network",
    ],
)
def test_s0_receipt_with_broader_authority_is_rejected(
    tmp_path: Path,
    field: str,
) -> None:
    repo = _make_repo(tmp_path)
    receipt = (
        repo
        / "TEMP/restructure_wave_preflight/test/S0_MATERIALIZE_RECEIPT.json"
    )
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["authorization_boundary"][field] = True
    _write_json(receipt, value)
    plan_relative = _plan(repo)

    with pytest.raises(
        MaterializeError,
        match=r"S0_RECEIPT_(NOT_ELIGIBLE|BOUNDARY_INVALID)",
    ):
        materialize(repo_root=repo, plan_relative=plan_relative)

    assert not (repo / "runs").exists()


def test_s0_receipt_requires_complete_checks_and_wave_plan_binding(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    receipt = (
        repo
        / "TEMP/restructure_wave_preflight/test/S0_MATERIALIZE_RECEIPT.json"
    )
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["checks"] = value["checks"][:-1]
    _write_json(receipt, value)
    plan_relative = _plan(repo)
    with pytest.raises(MaterializeError, match="S0_RECEIPT_NOT_ELIGIBLE"):
        materialize(repo_root=repo, plan_relative=plan_relative)

    repo = _make_repo(tmp_path / "second")
    wave_plan = (
        repo
        / "TEMP/restructure_wave_preflight/test/S0_MATERIALIZE_PLAN.json"
    )
    value = json.loads(wave_plan.read_text(encoding="utf-8"))
    value["plan_id"] = "S0-CHANGED-AFTER-RECEIPT"
    _write_json(wave_plan, value)
    plan_relative = _plan(repo)
    with pytest.raises(MaterializeError, match="S0_RECEIPT_NOT_ELIGIBLE"):
        materialize(repo_root=repo, plan_relative=plan_relative)


def test_existing_lock_blocks_recovery_without_overwrite(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    lock = repo / "runs/.locks/s0-test-001.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("older reservation\n", encoding="utf-8")

    with pytest.raises(MaterializeError, match="RUN_ALREADY_RESERVED"):
        materialize(repo_root=repo, plan_relative=plan_relative)

    assert lock.read_text(encoding="utf-8") == "older reservation\n"
    assert not (repo / "runs/s0-test-001").exists()


def test_post_publish_verification_failure_leaves_one_non_success_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    real_entry_at = MATERIALIZE_MODULE._entry_at
    run_lookups = 0

    def fail_second_run_lookup(
        parent_fd: int,
        name: str,
    ) -> os.stat_result | None:
        nonlocal run_lookups
        if name == "s0-test-001":
            run_lookups += 1
            if run_lookups == 2:
                return None
        return real_entry_at(parent_fd, name)

    monkeypatch.setattr(
        MATERIALIZE_MODULE,
        "_entry_at",
        fail_second_run_lookup,
    )
    with pytest.raises(MaterializeError, match="PUBLISHED_IDENTITY_MISMATCH"):
        materialize(repo_root=repo, plan_relative=plan_relative)

    output = repo / "runs/s0-test-001"
    identity = json.loads(
        (output / "RUN_IDENTITY.json").read_text(encoding="utf-8")
    )
    assert identity["state"] == "reserved"
    assert not (repo / "runs/.rejected/s0-test-001.json").exists()


def test_publish_directory_sync_failure_keeps_reserved_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    real_sync = MATERIALIZE_MODULE._sync_directory

    def fail_publish_sync(descriptor: int, *, code: str) -> None:
        if code == "PUBLISH_DIRECTORY_SYNC_FAILED":
            raise MaterializeError(code)
        real_sync(descriptor, code=code)

    monkeypatch.setattr(
        MATERIALIZE_MODULE,
        "_sync_directory",
        fail_publish_sync,
    )
    with pytest.raises(
        MaterializeError,
        match="PUBLISH_DIRECTORY_SYNC_FAILED",
    ):
        materialize(repo_root=repo, plan_relative=plan_relative)

    identity = json.loads(
        (repo / "runs/s0-test-001/RUN_IDENTITY.json").read_text(
            encoding="utf-8"
        )
    )
    assert identity["state"] == "reserved"
    assert not (repo / "runs/.rejected/s0-test-001.json").exists()


def test_identity_sync_failure_rolls_back_to_reserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    real_sync = MATERIALIZE_MODULE._sync_directory
    failed_once = False

    def fail_identity_sync_once(descriptor: int, *, code: str) -> None:
        nonlocal failed_once
        if code == "IDENTITY_DIRECTORY_SYNC_FAILED" and not failed_once:
            failed_once = True
            raise MaterializeError(code)
        real_sync(descriptor, code=code)

    monkeypatch.setattr(
        MATERIALIZE_MODULE,
        "_sync_directory",
        fail_identity_sync_once,
    )
    with pytest.raises(
        MaterializeError,
        match="IDENTITY_DIRECTORY_SYNC_FAILED",
    ):
        materialize(repo_root=repo, plan_relative=plan_relative)

    identity = json.loads(
        (repo / "runs/s0-test-001/RUN_IDENTITY.json").read_text(
            encoding="utf-8"
        )
    )
    assert identity["state"] == "reserved"
    assert not (repo / "runs/.rejected/s0-test-001.json").exists()


def test_git_head_and_materializer_bundle_are_frozen(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    plan_relative = _plan(repo)
    (repo / ".git/HEAD").write_text(f"{'b' * 40}\n", encoding="ascii")

    with pytest.raises(MaterializeError, match="GIT_HEAD_MISMATCH"):
        materialize(repo_root=repo, plan_relative=plan_relative)

    (repo / ".git/HEAD").write_text(f"{HEAD_SHA}\n", encoding="ascii")
    module = repo / "tools/experiment_workspace_modules/security.py"
    module.write_text(module.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(
        MaterializeError,
        match="MATERIALIZER_BUNDLE_SHA256_MISMATCH",
    ):
        materialize(repo_root=repo, plan_relative=plan_relative)
