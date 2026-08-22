from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from isolation import run_git
from tools import repo_slim_inventory as inventory


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
    completed = run_git(*args, cwd=repo, check=True, text=True)
    return completed.stdout.strip()


def _base_registry(manifest_sha: str) -> dict:
    return {
        "schema_version": "artifact-storage-v1",
        "registry_id": "repo-slim-test",
        "updated_at": "2026-07-31",
        "authority": {
            "scope": "artifact_identity_location_and_inventory_only",
            "may_define_current_task": False,
            "may_authorize_migration": False,
            "may_authorize_deletion": False,
            "may_claim_independent_backup": False,
            "conflict_rule": (
                "registered_open_conflict_stays_visible_until_separate_adjudication"
            ),
        },
        "capability_limits": {
            "inventory_only": True,
            "registered_anchor_read": True,
            "registered_manifest_read": True,
            "external_payload_traversal": False,
            "external_object_content_read": False,
            "write": False,
            "move": False,
            "delete": False,
            "restore": False,
            "recoverability_claim": False,
            "network": False,
            "credential_read": False,
            "model_call": False,
            "notion_write": False,
        },
        "size_policy": {
            "metric": "git_index_per_tracked_path_blob_bytes",
            "mode": "s06a_bootstrap_no_growth",
            "pre_s06a_baseline_bytes": 0,
            "active_limit_bytes": 1_000_000_000,
            "target_bytes": 10_000_000,
            "hard_limit_bytes": None,
            "activation_receipt": None,
            "hard_limit_activation": (
                "blocked_in_s06a_until_separate_payload_validator"
            ),
            "boundary": "合成测试只核只读盘点和体积算法。",
        },
        "storage_roots": [
            {
                "root_id": "repository_main_v1",
                "locator": {
                    "kind": "repository",
                    "suffix": None,
                },
                "role": "authoritative_repository",
                "required": True,
                "failure_domain": "primary_volume",
                "boundary": "合成主仓。",
            },
            {
                "root_id": "repository_sibling_external_archive_v1",
                "locator": {
                    "kind": "repository_sibling_suffix",
                    "suffix": "_外置仓",
                },
                "role": "external_archive",
                "required": True,
                "failure_domain": "same_volume_as_repository",
                "boundary": "合成同级外置仓。",
            },
        ],
        "objects": [
            {
                "artifact_id": "fixture-archive",
                "root_id": "repository_sibling_external_archive_v1",
                "relative_path": "batch",
                "category": "external_archive_batch",
                "status": "frozen",
                "record_kind": "archive_batch",
                "lifecycle": "historical",
                "consumer_closure": "not_applicable",
                "verification_level": "manifest_only",
                "recoverability": "not_proven",
                "externalization": "already_external",
                "purpose_summary": "合成清单。",
                "identity_anchors": [],
                "manifest": {
                    "relative_path": "MANIFEST.json",
                    "sha256": manifest_sha,
                    "expected_entry_count": 1,
                    "entries_field": "entries",
                    "entry_path_field": "path",
                    "entry_sha256_field": None,
                },
                "keep_in_repository": ["清单身份"],
                "externalize_later": [],
                "consumers": ["tests/test_repo_slim_inventory.py"],
                "boundary": "只核清单，不读 payload。",
            }
        ],
        "known_conflicts": [],
    }


def _make_fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    repo = tmp_path / "repo"
    external = tmp_path / "repo_外置仓"
    manifest = external / "batch/MANIFEST.json"
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "path": "payload/result.json",
                }
            ]
        },
    )
    (external / "batch/payload").mkdir()
    (external / "batch/payload/result.json").write_text(
        '{"secret_payload": true}\n',
        encoding="utf-8",
    )

    contracts = repo / "governance/contracts"
    contracts.mkdir(parents=True)
    shutil.copy2(
        ROOT / inventory.REGISTRY_SCHEMA_RELATIVE,
        repo / inventory.REGISTRY_SCHEMA_RELATIVE,
    )
    shutil.copy2(
        ROOT / inventory.REPORT_SCHEMA_RELATIVE,
        repo / inventory.REPORT_SCHEMA_RELATIVE,
    )
    shutil.copy2(
        ROOT / inventory.MIGRATION_RECEIPT_SCHEMA_RELATIVE,
        repo / inventory.MIGRATION_RECEIPT_SCHEMA_RELATIVE,
    )
    registry = _base_registry(_sha256(manifest))
    _write_json(repo / inventory.REGISTRY_RELATIVE, registry)
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")

    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Codex Test")
    _git(repo, "config", "user.email", "codex-test@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    return repo, external, manifest, registry


def _save_registry(repo: Path, registry: dict) -> None:
    _write_json(repo / inventory.REGISTRY_RELATIVE, registry)


def _prepare_hard_limit_fixture(
    repo: Path,
    external: Path,
    manifest: Path,
    registry: dict,
    *,
    seal_object: bool,
) -> None:
    payload = external / "batch/payload/result.json"
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "path": "payload/result.json",
                    "sha256": _sha256(payload),
                }
            ]
        },
    )
    object_row = registry["objects"][0]
    object_row["manifest"]["sha256"] = _sha256(manifest)
    object_row["manifest"]["entry_sha256_field"] = "sha256"
    if seal_object:
        object_row.update(
            {
                "category": "repository_experiment",
                "status": "sealed",
                "lifecycle": "frozen",
                "consumer_closure": "verified",
                "verification_level": "cryptographically_sealed",
            }
        )

    pointer = repo / "experiments/fixture-archive/README.md"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("fixture external pointer\n", encoding="utf-8")
    receipt = repo / "governance/receipts/migration.json"
    receipt_value = {
        "contract_version": "repository-size-migration-receipt-v1",
        "receipt_id": "synthetic-migration",
        "registry_id": "repo-slim-test",
        "status": "PASS",
        "metric": "git_index_per_tracked_path_blob_bytes",
        "target_bytes": 10_000_000,
        "tracked_bytes": 0,
        "migration_performed": True,
        "consumer_closure_verified": True,
        "pointer_resolution_verified": True,
        "external_snapshot_verified": True,
        "moved_artifact_ids": ["fixture-archive"],
        "repository_pointers": [
            {
                "artifact_id": "fixture-archive",
                "path": "experiments/fixture-archive/README.md",
                "sha256": _sha256(pointer),
            }
        ],
        "boundary": "仅供合成测试。",
    }
    registry["size_policy"].update(
        {
            "mode": "hard_limit",
            "active_limit_bytes": 10_000_000,
            "hard_limit_bytes": 10_000_000,
            "activation_receipt": {
                "path": "governance/receipts/migration.json",
                "sha256": "0" * 64,
            },
        }
    )
    for _attempt in range(4):
        _write_json(receipt, receipt_value)
        registry["size_policy"]["activation_receipt"]["sha256"] = _sha256(receipt)
        _save_registry(repo, registry)
        _git(
            repo,
            "add",
            inventory.REGISTRY_RELATIVE.as_posix(),
            "experiments/fixture-archive/README.md",
            "governance/receipts/migration.json",
        )
        _count, tracked_bytes = inventory.measure_git_index(repo)
        if receipt_value["tracked_bytes"] == tracked_bytes:
            return
        receipt_value["tracked_bytes"] = tracked_bytes
    raise AssertionError("hard-limit fixture size did not stabilize")


def test_tool_is_registered_exactly_once_with_targeted_test() -> None:
    registry = json.loads(
        (ROOT / "governance/tool_registry.json").read_text(encoding="utf-8")
    )
    rows = [
        row
        for row in registry["tools"]
        if row["path"] == "tools/repo_slim_inventory.py"
    ]
    assert len(rows) == 1
    assert "tests/test_repo_slim_inventory.py" in rows[0]["test_references"]


def test_scan_passes_without_reading_registered_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _external, _manifest, _registry = _make_fixture(tmp_path)
    original = inventory._read_registered_file
    opened: list[str] = []

    def record_read(root: Path, relative: Path, *, code: str) -> bytes:
        opened.append(relative.as_posix())
        return original(root, relative, code=code)

    monkeypatch.setattr(inventory, "_read_registered_file", record_read)
    report = inventory.scan(repo)

    assert report["status"] == "PASS"
    assert report["claim"] == {
        "inventory_complete_for_registered_objects": True,
        "external_payload_verified": False,
        "recoverability_proven": False,
        "migration_performed": False,
    }
    assert opened == [
        "governance/external_archive_registry.json",
        "governance/contracts/external_archive_registry_v1.schema.json",
        "batch/MANIFEST.json",
        "governance/contracts/repo_slim_inventory_report_v1.schema.json",
    ]
    assert "payload/result.json" not in opened


def test_report_is_byte_reproducible_for_same_inputs(tmp_path: Path) -> None:
    repo, _external, _manifest, _registry = _make_fixture(tmp_path)
    first = inventory._json_bytes(inventory.scan(repo))
    second = inventory._json_bytes(inventory.scan(repo))
    assert first == second


def test_report_never_serializes_absolute_roots_or_username(
    tmp_path: Path,
) -> None:
    repo, external, _manifest, _registry = _make_fixture(tmp_path)
    raw = inventory._json_bytes(inventory.scan(repo)).decode("utf-8")
    assert str(repo) not in raw
    assert str(external) not in raw
    assert Path.home().name not in raw


def test_git_metric_counts_same_blob_once_per_tracked_path(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "metric"
    repo.mkdir()
    (repo / "a.txt").write_text("same\n", encoding="utf-8")
    (repo / "b.txt").write_text("same\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "a.txt", "b.txt")

    count, size = inventory.measure_git_index(repo)
    assert count == 2
    assert size == 2 * len(b"same\n")


def test_git_metric_details_keep_each_tracked_path_and_size(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "metric"
    repo.mkdir()
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "nested").mkdir()
    (repo / "nested/b.txt").write_text("bbb\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "a.txt", "nested/b.txt")

    details = inventory.measure_git_index_details(repo)

    assert details == {
        "tracked_path_count": 2,
        "tracked_bytes": len(b"a\n") + len(b"bbb\n"),
        "entries": [
            {"path": "a.txt", "bytes": len(b"a\n")},
            {"path": "nested/b.txt", "bytes": len(b"bbb\n")},
        ],
    }


def test_git_metric_ignores_untracked_and_worktree_only_changes(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "metric"
    repo.mkdir()
    (repo / "tracked.txt").write_text("index\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    before = inventory.measure_git_index(repo)

    (repo / "tracked.txt").write_text("worktree is much larger\n", encoding="utf-8")
    (repo / "untracked.bin").write_bytes(b"x" * 100_000)
    assert inventory.measure_git_index(repo) == before


def test_target_can_remain_false_while_active_gate_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _external, _manifest, registry = _make_fixture(tmp_path)
    registry["size_policy"]["active_limit_bytes"] = 20_000_000
    _save_registry(repo, registry)
    monkeypatch.setattr(
        inventory,
        "measure_git_index_details",
        lambda _root: {
            "tracked_path_count": 100,
            "tracked_bytes": 12_000_000,
            "entries": [],
        },
    )

    report = inventory.scan(repo)
    assert report["status"] == "PASS"
    assert report["git_inventory"]["target_met"] is False
    assert report["git_inventory"]["active_gate_passed"] is True


def test_active_size_gate_blocks_growth_past_limit(tmp_path: Path) -> None:
    repo, _external, _manifest, registry = _make_fixture(tmp_path)
    registry["size_policy"]["active_limit_bytes"] = 0
    _save_registry(repo, registry)

    report = inventory.scan(repo)
    assert report["status"] == "BLOCKED"
    assert report["blockers"] == ["active_size_gate_passed"]
    assert report["git_inventory"]["active_gate_passed"] is False


def test_missing_manifest_is_invalid(tmp_path: Path) -> None:
    repo, _external, manifest, _registry = _make_fixture(tmp_path)
    manifest.unlink()
    with pytest.raises(inventory.InventoryError, match="MANIFEST_SNAPSHOT_INVALID"):
        inventory.scan(repo)


def test_manifest_sha_drift_is_invalid(tmp_path: Path) -> None:
    repo, _external, manifest, _registry = _make_fixture(tmp_path)
    _write_json(manifest, {"entries": [{"path": "changed"}]})
    with pytest.raises(inventory.InventoryError, match="MANIFEST_SNAPSHOT_INVALID"):
        inventory.scan(repo)


def test_manifest_entry_count_drift_is_invalid(tmp_path: Path) -> None:
    repo, _external, manifest, registry = _make_fixture(tmp_path)
    _write_json(manifest, {"entries": []})
    registry["objects"][0]["manifest"]["sha256"] = _sha256(manifest)
    _save_registry(repo, registry)
    with pytest.raises(inventory.InventoryError, match="MANIFEST_ENTRY_COUNT_DRIFT"):
        inventory.scan(repo)


def test_registry_rejects_zero_entry_manifest_contract(tmp_path: Path) -> None:
    repo, _external, _manifest, registry = _make_fixture(tmp_path)
    registry["objects"][0]["manifest"]["expected_entry_count"] = 0
    _save_registry(repo, registry)

    with pytest.raises(inventory.InventoryError, match="REGISTRY_CONTRACT_INVALID"):
        inventory.scan(repo)


def test_cryptographic_manifest_rejects_unsafe_entry_path(
    tmp_path: Path,
) -> None:
    repo, _external, manifest, registry = _make_fixture(tmp_path)
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "path": "../escape",
                    "sha256": "0" * 64,
                }
            ]
        },
    )
    object_row = registry["objects"][0]
    object_row["verification_level"] = "cryptographically_sealed"
    object_row["manifest"]["sha256"] = _sha256(manifest)
    object_row["manifest"]["entry_sha256_field"] = "sha256"
    _save_registry(repo, registry)

    with pytest.raises(inventory.InventoryError, match="MANIFEST_ENTRY_PATH_INVALID"):
        inventory.scan(repo)


def test_cryptographic_manifest_rejects_duplicate_entry_paths(
    tmp_path: Path,
) -> None:
    repo, _external, manifest, registry = _make_fixture(tmp_path)
    _write_json(
        manifest,
        {
            "entries": [
                {
                    "path": "payload/result.json",
                    "sha256": "0" * 64,
                },
                {
                    "path": "PAYLOAD/RESULT.JSON",
                    "sha256": "1" * 64,
                },
            ]
        },
    )
    object_row = registry["objects"][0]
    object_row["verification_level"] = "cryptographically_sealed"
    object_row["manifest"]["sha256"] = _sha256(manifest)
    object_row["manifest"]["expected_entry_count"] = 2
    object_row["manifest"]["entry_sha256_field"] = "sha256"
    _save_registry(repo, registry)

    with pytest.raises(
        inventory.InventoryError,
        match="MANIFEST_ENTRY_PATH_CONFLICT",
    ):
        inventory.scan(repo)


def test_manifest_path_escape_is_rejected_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _external, _manifest, registry = _make_fixture(tmp_path)
    registry["objects"][0]["manifest"]["relative_path"] = "../MANIFEST.json"
    _save_registry(repo, registry)
    original = inventory._read_registered_file
    called_codes: list[str] = []

    def record_read(root: Path, relative: Path, *, code: str) -> bytes:
        called_codes.append(code)
        return original(root, relative, code=code)

    monkeypatch.setattr(inventory, "_read_registered_file", record_read)
    with pytest.raises(inventory.InventoryError, match="REGISTRY_CONTRACT_INVALID"):
        inventory.scan(repo)
    assert "MANIFEST_SNAPSHOT_INVALID" not in called_codes


def test_external_root_symlink_is_rejected(tmp_path: Path) -> None:
    repo, external, _manifest, _registry = _make_fixture(tmp_path)
    actual = tmp_path / "actual_external"
    external.rename(actual)
    external.symlink_to(actual.name, target_is_directory=True)
    with pytest.raises(inventory.InventoryError, match="STORAGE_ROOT_INVALID"):
        inventory.scan(repo)


def test_archive_batch_symlink_is_rejected(tmp_path: Path) -> None:
    repo, external, _manifest, _registry = _make_fixture(tmp_path)
    batch = external / "batch"
    actual = external / "actual_batch"
    batch.rename(actual)
    batch.symlink_to(actual.name, target_is_directory=True)
    with pytest.raises(inventory.InventoryError, match="OBJECT_PATH_INVALID"):
        inventory.scan(repo)


def test_manifest_symlink_is_rejected(tmp_path: Path) -> None:
    repo, _external, manifest, _registry = _make_fixture(tmp_path)
    target = manifest.with_name("actual.json")
    manifest.rename(target)
    manifest.symlink_to(target.name)
    with pytest.raises(inventory.InventoryError, match="MANIFEST_SNAPSHOT_INVALID"):
        inventory.scan(repo)


def test_manifest_hardlink_is_rejected(tmp_path: Path) -> None:
    repo, _external, manifest, _registry = _make_fixture(tmp_path)
    os.link(manifest, manifest.with_name("second.json"))
    with pytest.raises(inventory.InventoryError, match="MANIFEST_SNAPSHOT_INVALID"):
        inventory.scan(repo)


def test_parent_replacement_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, external, _manifest, _registry = _make_fixture(tmp_path)
    original_read = inventory.os.read
    manifest_inode = (external / "batch/MANIFEST.json").stat().st_ino
    replaced = False

    def replace_parent(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        data = original_read(descriptor, size)
        if not replaced and os.fstat(descriptor).st_ino == manifest_inode:
            batch = external / "batch"
            stable = external / "batch_before_replacement"
            batch.rename(stable)
            batch.symlink_to(stable.name, target_is_directory=True)
            replaced = True
        return data

    monkeypatch.setattr(inventory.os, "read", replace_parent)
    with pytest.raises(inventory.InventoryError, match="MANIFEST_SNAPSHOT_INVALID"):
        inventory.scan(repo)


def test_manifest_replacement_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _external, manifest, _registry = _make_fixture(tmp_path)
    original_read = inventory.os.read
    manifest_inode = manifest.stat().st_ino
    replaced = False

    def replace_manifest(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        data = original_read(descriptor, size)
        if not replaced and os.fstat(descriptor).st_ino == manifest_inode:
            old = manifest.with_name("MANIFEST.before.json")
            manifest.rename(old)
            _write_json(manifest, {"entries": [{"path": "replacement"}]})
            replaced = True
        return data

    monkeypatch.setattr(inventory.os, "read", replace_manifest)
    with pytest.raises(inventory.InventoryError, match="MANIFEST_SNAPSHOT_INVALID"):
        inventory.scan(repo)


def test_oversize_manifest_is_rejected_before_read(tmp_path: Path) -> None:
    repo, _external, manifest, _registry = _make_fixture(tmp_path)
    with manifest.open("r+b") as handle:
        handle.truncate(inventory.MAX_REGISTERED_FILE_BYTES + 1)
    with pytest.raises(inventory.InventoryError, match="MANIFEST_SNAPSHOT_INVALID"):
        inventory.scan(repo)


def test_duplicate_object_paths_are_rejected_case_insensitively(
    tmp_path: Path,
) -> None:
    repo, _external, _manifest, registry = _make_fixture(tmp_path)
    duplicate = json.loads(json.dumps(registry["objects"][0]))
    duplicate["artifact_id"] = "fixture-archive-two"
    duplicate["relative_path"] = "BATCH"
    registry["objects"].append(duplicate)
    _save_registry(repo, registry)
    with pytest.raises(inventory.InventoryError, match="REGISTRY_PATH_CONFLICT"):
        inventory.scan(repo)


def test_sealed_level_requires_per_file_sha_field(tmp_path: Path) -> None:
    repo, _external, _manifest, registry = _make_fixture(tmp_path)
    registry["objects"][0]["verification_level"] = "cryptographically_sealed"
    _save_registry(repo, registry)
    with pytest.raises(
        inventory.InventoryError,
        match="REGISTRY_VERIFICATION_OVERCLAIM",
    ):
        inventory.scan(repo)


def test_identity_anchor_cannot_be_arbitrary_payload_file(
    tmp_path: Path,
) -> None:
    repo, external, _manifest, registry = _make_fixture(tmp_path)
    payload = external / "batch/payload/README.md"
    payload.write_text("not an identity document\n", encoding="utf-8")
    registry["objects"][0]["identity_anchors"] = [
        {
            "kind": "root_identity_document",
            "relative_path": "payload/README.md",
            "sha256": _sha256(payload),
        }
    ]
    _save_registry(repo, registry)
    with pytest.raises(inventory.InventoryError, match="REGISTRY_CONTRACT_INVALID"):
        inventory.scan(repo)


def test_hard_limit_without_migration_receipt_is_invalid(tmp_path: Path) -> None:
    repo, _external, _manifest, registry = _make_fixture(tmp_path)
    registry["size_policy"].update(
        {
            "mode": "hard_limit",
            "active_limit_bytes": 10_000_000,
            "hard_limit_bytes": 10_000_000,
            "activation_receipt": None,
        }
    )
    _save_registry(repo, registry)
    with pytest.raises(inventory.InventoryError, match="REGISTRY_CONTRACT_INVALID"):
        inventory.scan(repo)


def test_s06a_rejects_hard_limit_even_with_exact_migration_receipt(
    tmp_path: Path,
) -> None:
    repo, external, manifest, registry = _make_fixture(tmp_path)
    _prepare_hard_limit_fixture(
        repo,
        external,
        manifest,
        registry,
        seal_object=True,
    )
    with pytest.raises(
        inventory.InventoryError,
        match="HARD_LIMIT_NOT_AVAILABLE_IN_S06A",
    ):
        inventory.scan(repo)


def test_migration_receipt_schema_rejects_semantically_empty_receipt() -> None:
    schema = json.loads(
        (ROOT / inventory.MIGRATION_RECEIPT_SCHEMA_RELATIVE).read_text(encoding="utf-8")
    )
    with pytest.raises(
        inventory.InventoryError,
        match="HARD_LIMIT_ACTIVATION_INVALID",
    ):
        inventory._validate_schema(
            {"status": "PASS", "scope": "synthetic"},
            schema,
            code="HARD_LIMIT_ACTIVATION_INVALID",
        )


def test_scan_does_not_mutate_registry_or_manifest(tmp_path: Path) -> None:
    repo, _external, manifest, _registry = _make_fixture(tmp_path)
    watched = [
        repo / inventory.REGISTRY_RELATIVE,
        repo / inventory.REGISTRY_SCHEMA_RELATIVE,
        repo / inventory.REPORT_SCHEMA_RELATIVE,
        manifest,
    ]
    before = {
        path: (path.stat().st_mtime_ns, path.stat().st_size, _sha256(path))
        for path in watched
    }
    inventory.scan(repo)
    after = {
        path: (path.stat().st_mtime_ns, path.stat().st_size, _sha256(path))
        for path in watched
    }
    assert after == before


def test_cli_surface_has_only_check_and_report() -> None:
    parser = inventory.build_parser()
    subparser_action = next(
        action for action in parser._actions if action.dest == "command"
    )
    assert set(subparser_action.choices) == {"check", "report"}


def test_report_relation_validator_rejects_false_target_flag(
    tmp_path: Path,
) -> None:
    repo, _external, _manifest, _registry = _make_fixture(tmp_path)
    report = inventory.scan(repo)
    report["git_inventory"]["target_met"] = not report["git_inventory"]["target_met"]
    with pytest.raises(inventory.InventoryError, match="REPORT_RELATION_INVALID"):
        inventory._validate_report_relations(report)


def test_report_relation_validator_rejects_false_active_gate(
    tmp_path: Path,
) -> None:
    repo, _external, _manifest, _registry = _make_fixture(tmp_path)
    report = inventory.scan(repo)
    report["git_inventory"]["tracked_bytes"] = (
        report["git_inventory"]["active_limit_bytes"] + 1
    )
    report["git_inventory"]["target_met"] = False
    with pytest.raises(inventory.InventoryError, match="REPORT_RELATION_INVALID"):
        inventory._validate_report_relations(report)


def test_external_volume_uuid_resolves_one_different_physical_device(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    mount = tmp_path / "external"
    target = mount / "archive/v1"
    repo.mkdir()
    target.mkdir(parents=True)
    monkeypatch.setattr(
        inventory,
        "_external_volume_records",
        lambda: [
            {
                "VolumeUUID": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
                "MountPoint": str(mount),
                "ParentWholeDisk": "disk9",
            }
        ],
    )
    monkeypatch.setattr(
        inventory,
        "_repository_parent_whole_disk",
        lambda _repo: "disk1",
    )
    row = {
        "root_id": "physical-archive-v1",
        "locator": {
            "kind": "external_volume_uuid",
            "volume_uuid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
            "expected_volume_name": "fixture",
            "relative_root": "archive/v1",
        },
        "required": True,
    }

    assert inventory.resolve_storage_root(repo, row) == target

    monkeypatch.setattr(
        inventory,
        "_repository_parent_whole_disk",
        lambda _repo: "disk9",
    )
    with pytest.raises(
        inventory.InventoryError,
        match="EXTERNAL_VOLUME_FAILURE_DOMAIN_INVALID",
    ):
        inventory.resolve_storage_root(repo, row)
