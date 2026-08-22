from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tools import external_payload_validator as validator
from tools import repo_slim_inventory as inventory


ROOT = Path(__file__).resolve().parents[1]
TARGET_ID = "fixture-archive"
EXCLUDED_ID = "archived-excluded"


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


@dataclass
class PayloadFixture:
    repo: Path
    external: Path
    object_root: Path
    payload_root: Path
    manifest_path: Path
    registry_path: Path
    policy_path: Path
    validator_path: Path
    inventory_helper_path: Path
    registry: dict
    policy: dict


def _base_registry(manifest_sha256: str, entry_count: int) -> dict:
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
            "boundary": "合成测试仍保持 S-06-A 硬门锁定。",
        },
        "storage_roots": [
            {
                "root_id": "repository_main_v1",
                "locator": {"kind": "repository", "suffix": None},
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
                "artifact_id": EXCLUDED_ID,
                "root_id": "repository_sibling_external_archive_v1",
                "relative_path": "legacy",
                "category": "legacy_external_container",
                "status": "frozen",
                "record_kind": "family_container",
                "lifecycle": "historical",
                "consumer_closure": "not_applicable",
                "verification_level": "directory_presence_only",
                "recoverability": "not_proven",
                "externalization": "already_external",
                "purpose_summary": "没有逐文件清单的合成旧对象。",
                "identity_anchors": [],
                "manifest": None,
                "keep_in_repository": ["排除原因"],
                "externalize_later": [],
                "consumers": ["tests/test_external_payload_validator.py"],
                "boundary": "验证器不得猜测此对象的 payload。",
            },
            {
                "artifact_id": TARGET_ID,
                "root_id": "repository_sibling_external_archive_v1",
                "relative_path": "batch",
                "category": "historical_test_replay_package",
                "status": "sealed",
                "record_kind": "replay_package",
                "lifecycle": "frozen",
                "consumer_closure": "verified",
                "verification_level": "cryptographically_sealed",
                "recoverability": "package_integrity_proven_same_failure_domain",
                "externalization": "already_external",
                "purpose_summary": "逐文件验证器的合成获准对象。",
                "identity_anchors": [],
                "manifest": {
                    "relative_path": "MANIFEST.json",
                    "sha256": manifest_sha256,
                    "expected_entry_count": entry_count,
                    "entries_field": "files",
                    "entry_path_field": "path",
                    "entry_sha256_field": "sha256",
                },
                "keep_in_repository": ["结论和指针"],
                "externalize_later": [],
                "consumers": ["tests/test_external_payload_validator.py"],
                "boundary": "PASS 只证明 payload 字节与清单一致。",
            },
        ],
        "known_conflicts": [],
    }


def _base_policy(manifest_sha256: str) -> dict:
    return {
        "contract_version": "external-payload-validation-policy-v1",
        "policy_id": "external-payload-validation-test",
        "registry_id": "repo-slim-test",
        "authority": {
            "scope": "registered_external_payload_bytes_only",
            "may_discover_targets": False,
            "may_move": False,
            "may_delete": False,
            "may_restore": False,
            "may_rewrite_registry": False,
            "may_issue_migration_receipt": False,
            "may_activate_hard_limit": False,
        },
        "capability_limits": {
            "one_artifact_per_command": True,
            "registered_payload_read": True,
            "exact_file_set_check": True,
            "streaming_sha256": True,
            "write": False,
            "network": False,
            "credential_read": False,
            "model_call": False,
            "notion_write": False,
        },
        "targets": [
            {
                "artifact_id": TARGET_ID,
                "manifest_sha256": manifest_sha256,
                "payload_root_relative_path": "payload",
                "entry_size_field": "bytes",
                "manifest_total_files_field": "total_files",
                "manifest_total_bytes_field": "total_bytes",
                "exact_file_set": True,
                "boundary": "只核合成 payload 的普通文件、大小和 SHA-256。",
            }
        ],
        "exclusions": [
            {
                "artifact_id": EXCLUDED_ID,
                "reason": "manifest_missing",
                "boundary": "没有清单就必须明确排除。",
            }
        ],
        "boundary": "只读测试政策；不授权移动、删除、出票或启用硬门。",
    }


def _manifest_for(files: dict[str, bytes]) -> dict:
    entries = [
        {
            "path": relative,
            "bytes": len(content),
            "sha256": _sha256_bytes(content),
        }
        for relative, content in sorted(files.items())
    ]
    return {
        "total_files": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "files": entries,
    }


def _make_fixture(
    tmp_path: Path,
    files: dict[str, bytes] | None = None,
) -> PayloadFixture:
    if files is None:
        files = {"result.bin": b"fixture payload\n"}
    repo = tmp_path / "repo"
    external = tmp_path / "repo_外置仓"
    object_root = external / "batch"
    payload_root = object_root / "payload"
    payload_root.mkdir(parents=True)
    for relative, content in files.items():
        path = payload_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    manifest_path = object_root / "MANIFEST.json"
    manifest = _manifest_for(files)
    _write_json(manifest_path, manifest)
    manifest_sha256 = _sha256(manifest_path)

    contract_relatives = (
        inventory.REGISTRY_SCHEMA_RELATIVE,
        inventory.MIGRATION_RECEIPT_SCHEMA_RELATIVE,
        inventory.BINDING_SCHEMA_RELATIVE,
        validator.POLICY_SCHEMA_RELATIVE,
        validator.REPORT_SCHEMA_RELATIVE,
    )
    for relative in contract_relatives:
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    validator_path = repo / "tools/external_payload_validator.py"
    validator_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tools/external_payload_validator.py", validator_path)
    inventory_helper_path = repo / validator.INVENTORY_HELPER_RELATIVE
    shutil.copy2(
        ROOT / validator.INVENTORY_HELPER_RELATIVE,
        inventory_helper_path,
    )

    registry = _base_registry(manifest_sha256, len(manifest["files"]))
    policy = _base_policy(manifest_sha256)
    registry_path = repo / inventory.REGISTRY_RELATIVE
    policy_path = repo / validator.POLICY_RELATIVE
    _write_json(registry_path, registry)
    _write_json(policy_path, policy)
    return PayloadFixture(
        repo=repo,
        external=external,
        object_root=object_root,
        payload_root=payload_root,
        manifest_path=manifest_path,
        registry_path=registry_path,
        policy_path=policy_path,
        validator_path=validator_path,
        inventory_helper_path=inventory_helper_path,
        registry=registry,
        policy=policy,
    )


def _rewrite_manifest(
    fixture: PayloadFixture,
    entries: list[dict],
) -> None:
    manifest = {
        "total_files": len(entries),
        "total_bytes": sum(entry.get("bytes", 0) for entry in entries),
        "files": entries,
    }
    _write_json(fixture.manifest_path, manifest)
    manifest_sha256 = _sha256(fixture.manifest_path)
    target = next(
        row for row in fixture.registry["objects"] if row["artifact_id"] == TARGET_ID
    )
    target["manifest"]["sha256"] = manifest_sha256
    target["manifest"]["expected_entry_count"] = len(entries)
    fixture.policy["targets"][0]["manifest_sha256"] = manifest_sha256
    _write_json(fixture.registry_path, fixture.registry)
    _write_json(fixture.policy_path, fixture.policy)


def _rebind_manifest(fixture: PayloadFixture) -> None:
    manifest_sha256 = _sha256(fixture.manifest_path)
    target = next(
        row for row in fixture.registry["objects"] if row["artifact_id"] == TARGET_ID
    )
    target["manifest"]["sha256"] = manifest_sha256
    fixture.policy["targets"][0]["manifest_sha256"] = manifest_sha256
    _write_json(fixture.registry_path, fixture.registry)
    _write_json(fixture.policy_path, fixture.policy)


def _expect_error(
    fixture: PayloadFixture,
    code: str,
    *,
    artifact_id: str = TARGET_ID,
) -> None:
    with pytest.raises(validator.PayloadValidationError) as caught:
        validator.validate_payload(artifact_id, fixture.repo)
    assert caught.value.code == code


@pytest.mark.parametrize(
    "files",
    [
        {"one.bin": b"one\n"},
        {
            "a.bin": b"alpha\n",
            "nested/b.bin": b"beta\n",
            "nested/c.bin": b"gamma\n",
        },
    ],
    ids=["single-file", "multiple-files"],
)
def test_pass_report_is_byte_reproducible(
    tmp_path: Path,
    files: dict[str, bytes],
) -> None:
    fixture = _make_fixture(tmp_path, files)

    first = validator.validate_payload(TARGET_ID, fixture.repo)
    second = validator.validate_payload(TARGET_ID, fixture.repo)
    first_bytes = validator._json_bytes(first)
    second_bytes = validator._json_bytes(second)

    assert first_bytes == second_bytes
    assert json.loads(first_bytes) == first
    assert first["status"] == "PASS"
    assert first["verification"]["file_count"] == len(files)
    assert first["verification"]["total_bytes"] == sum(map(len, files.values()))
    canonical_entries = [
        {
            "bytes": len(files[path]),
            "path": path,
            "sha256": _sha256_bytes(files[path]),
        }
        for path in sorted(files)
    ]
    assert first["verification"]["entry_set_sha256"] == _sha256_bytes(
        _json_bytes(canonical_entries)
    )


def test_payload_hashing_reads_in_one_mib_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"a" * (validator.READ_CHUNK_BYTES * 2 + 17)
    fixture = _make_fixture(tmp_path, {"large.bin": content})
    original_read = validator.os.read
    reads: list[tuple[int, int]] = []

    def recording_read(file_descriptor: int, size: int) -> bytes:
        value = original_read(file_descriptor, size)
        reads.append((size, len(value)))
        return value

    monkeypatch.setattr(validator.os, "read", recording_read)
    report = validator.validate_payload(TARGET_ID, fixture.repo)

    assert report["verification"]["total_bytes"] == len(content)
    expected_payload_reads = [
        (validator.READ_CHUNK_BYTES, validator.READ_CHUNK_BYTES),
        (validator.READ_CHUNK_BYTES, validator.READ_CHUNK_BYTES),
        (validator.READ_CHUNK_BYTES, 17),
        (validator.READ_CHUNK_BYTES, 0),
    ]
    assert all(requested == validator.READ_CHUNK_BYTES for requested, _ in reads)
    assert any(
        reads[index : index + len(expected_payload_reads)] == expected_payload_reads
        for index in range(len(reads) - len(expected_payload_reads) + 1)
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing", "PAYLOAD_FILE_SET_MISMATCH"),
        ("extra", "PAYLOAD_FILE_SET_MISMATCH"),
        ("size", "PAYLOAD_SIZE_MISMATCH"),
        ("digest", "PAYLOAD_DIGEST_MISMATCH"),
    ],
)
def test_payload_drift_is_rejected(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    fixture = _make_fixture(tmp_path, {"result.bin": b"same-size\n"})
    payload = fixture.payload_root / "result.bin"
    if mutation == "missing":
        payload.unlink()
    elif mutation == "extra":
        (fixture.payload_root / "extra.bin").write_bytes(b"extra\n")
    elif mutation == "size":
        payload.write_bytes(b"different-size\n")
    else:
        payload.write_bytes(b"diff-size\n")

    _expect_error(fixture, expected_code)


@pytest.mark.parametrize(
    ("entries", "expected_code"),
    [
        (
            [
                {
                    "path": "../escape.bin",
                    "bytes": 1,
                    "sha256": _sha256_bytes(b"x"),
                }
            ],
            "PAYLOAD_MANIFEST_ENTRY_PATH_INVALID",
        ),
        (
            [
                {
                    "path": "A.bin",
                    "bytes": 1,
                    "sha256": _sha256_bytes(b"a"),
                },
                {
                    "path": "a.bin",
                    "bytes": 1,
                    "sha256": _sha256_bytes(b"b"),
                },
            ],
            "PAYLOAD_MANIFEST_PATH_CONFLICT",
        ),
    ],
    ids=["unsafe-path", "casefold-duplicate"],
)
def test_manifest_path_rules_are_fail_closed(
    tmp_path: Path,
    entries: list[dict],
    expected_code: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    _rewrite_manifest(fixture, entries)

    _expect_error(fixture, expected_code)


def test_payload_file_symlink_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    payload = fixture.payload_root / "result.bin"
    outside = fixture.object_root / "outside.bin"
    outside.write_bytes(payload.read_bytes())
    payload.unlink()
    payload.symlink_to(outside)

    _expect_error(fixture, "PAYLOAD_TREE_INVALID")


def test_payload_parent_symlink_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path, {"nested/result.bin": b"payload\n"})
    nested = fixture.payload_root / "nested"
    outside = fixture.object_root / "outside-parent"
    nested.rename(outside)
    nested.symlink_to(outside, target_is_directory=True)

    _expect_error(fixture, "PAYLOAD_TREE_INVALID")


def test_payload_hardlink_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    source = fixture.payload_root / "result.bin"
    try:
        os.link(source, fixture.payload_root / "second-link.bin")
    except OSError as exc:
        pytest.skip(f"当前文件系统不支持硬链接测试：{exc}")

    _expect_error(fixture, "PAYLOAD_TREE_INVALID")


def test_payload_fifo_is_rejected_when_supported(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    fifo = fixture.payload_root / "pipe"
    try:
        os.mkfifo(fifo)
    except (AttributeError, OSError) as exc:
        pytest.skip(f"当前平台不支持 FIFO 测试：{exc}")

    _expect_error(fixture, "PAYLOAD_TREE_INVALID")


def test_second_snapshot_detects_file_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    payload = fixture.payload_root / "result.bin"
    original_hash = validator._hash_registered_payload_file
    replaced = False

    def hash_then_replace(*args: object, **kwargs: object) -> str:
        nonlocal replaced
        digest = original_hash(*args, **kwargs)
        if not replaced:
            replacement = fixture.payload_root / "replacement.tmp"
            replacement.write_bytes(payload.read_bytes())
            replacement.replace(payload)
            replaced = True
        return digest

    monkeypatch.setattr(
        validator,
        "_hash_registered_payload_file",
        hash_then_replace,
    )

    _expect_error(fixture, "PAYLOAD_SNAPSHOT_DRIFT")


def test_inventory_helper_drift_during_validation_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    original_hash = validator._hash_registered_payload_file
    changed = False

    def hash_then_change_helper(*args: object, **kwargs: object) -> str:
        nonlocal changed
        digest = original_hash(*args, **kwargs)
        if not changed:
            fixture.inventory_helper_path.write_bytes(
                fixture.inventory_helper_path.read_bytes() + b"\n# synthetic drift\n"
            )
            changed = True
        return digest

    monkeypatch.setattr(
        validator,
        "_hash_registered_payload_file",
        hash_then_change_helper,
    )

    _expect_error(fixture, "PAYLOAD_INPUT_SNAPSHOT_DRIFT")


def test_missing_no_follow_capability_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    monkeypatch.delattr(validator.os, "O_NOFOLLOW")

    _expect_error(fixture, "PAYLOAD_PLATFORM_CAPABILITY_MISSING")


def test_unregistered_and_policy_excluded_artifacts_are_rejected(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)

    _expect_error(
        fixture,
        "PAYLOAD_ARTIFACT_NOT_APPROVED",
        artifact_id="not-registered",
    )
    _expect_error(
        fixture,
        "PAYLOAD_ARTIFACT_EXCLUDED",
        artifact_id=EXCLUDED_ID,
    )


def test_missing_unrelated_required_root_does_not_block_target(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    fixture.registry["storage_roots"].append(
        {
            "root_id": "repository_sibling_isolated_experiments_v1",
            "locator": {
                "kind": "repository_sibling_suffix",
                "suffix": "_隔离实验",
            },
            "role": "isolated_experiment_workspace",
            "required": True,
            "failure_domain": "same_volume_as_repository",
            "boundary": "这个无关根故意不存在，不能挡单件外置验证。",
        }
    )
    _write_json(fixture.registry_path, fixture.registry)

    report = validator.validate_payload(TARGET_ID, fixture.repo)
    assert report["status"] == "PASS"


def test_policy_must_cover_every_registered_external_object(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    fixture.policy["exclusions"] = []
    _write_json(fixture.policy_path, fixture.policy)

    _expect_error(fixture, "PAYLOAD_POLICY_COVERAGE_INVALID")


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("total_files", 2),
        ("total_bytes", 999),
    ],
)
def test_manifest_top_level_totals_must_match_entries(
    tmp_path: Path,
    field: str,
    wrong_value: int,
) -> None:
    fixture = _make_fixture(tmp_path)
    manifest = json.loads(fixture.manifest_path.read_text(encoding="utf-8"))
    manifest[field] = wrong_value
    _write_json(fixture.manifest_path, manifest)
    _rebind_manifest(fixture)

    _expect_error(fixture, "PAYLOAD_MANIFEST_TOTAL_MISMATCH")


def test_cli_exposes_only_check_and_report_with_required_artifact_id() -> None:
    parser = validator.build_parser()
    command_action = next(
        action for action in parser._actions if action.dest == "command"
    )
    assert isinstance(command_action, argparse._SubParsersAction)
    assert set(command_action.choices) == {"check", "report"}

    for command_parser in command_action.choices.values():
        artifact_action = next(
            action for action in command_parser._actions if action.dest == "artifact_id"
        )
        assert artifact_action.required is True
        option_strings = {
            option
            for action in command_parser._actions
            for option in action.option_strings
        }
        assert option_strings == {"-h", "--help", "--artifact-id"}
        with pytest.raises(SystemExit):
            command_parser.parse_args([])

    for forbidden_command in ("move", "delete", "fix", "activate"):
        with pytest.raises(SystemExit):
            parser.parse_args([forbidden_command, "--artifact-id", TARGET_ID])
    with pytest.raises(SystemExit):
        parser.parse_args(["check", "--artifact-id", TARGET_ID, "--root", "/tmp"])


def test_report_is_lightweight_private_and_cannot_be_a_migration_receipt(
    tmp_path: Path,
) -> None:
    secret = b"TOP_SECRET_PAYLOAD_CONTENT_9f017\n"
    fixture = _make_fixture(tmp_path, {"private.bin": secret})
    report = validator.validate_payload(TARGET_ID, fixture.repo)
    serialized = validator._json_bytes(report)

    assert str(fixture.repo).encode() not in serialized
    assert str(fixture.external).encode() not in serialized
    home = Path.home()
    assert str(home).encode() not in serialized
    assert home.as_posix().encode() not in serialized
    assert secret.strip() not in serialized
    assert b'"files"' not in serialized
    assert report["claims"]["migration_performed"] is False
    assert report["claims"]["hard_limit_activation_authorized"] is False
    assert report["claims"]["deletion_authorized"] is False

    migration_schema = json.loads(
        (fixture.repo / inventory.MIGRATION_RECEIPT_SCHEMA_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(migration_schema)
    assert not Draft202012Validator(migration_schema).is_valid(report)


def test_validation_does_not_change_registry_policy_manifest_or_payload(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(
        tmp_path,
        {
            "one.bin": b"one\n",
            "nested/two.bin": b"two\n",
        },
    )
    input_paths = [
        fixture.registry_path,
        fixture.policy_path,
        fixture.manifest_path,
        fixture.validator_path,
        fixture.inventory_helper_path,
        fixture.payload_root / "one.bin",
        fixture.payload_root / "nested/two.bin",
    ]
    before = {
        path: (
            path.read_bytes(),
            path.stat().st_mode,
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in input_paths
    }

    validator.validate_payload(TARGET_ID, fixture.repo)

    after = {
        path: (
            path.read_bytes(),
            path.stat().st_mode,
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in input_paths
    }
    assert after == before


def test_s06a_hard_limit_activation_remains_locked(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    report = validator.validate_payload(TARGET_ID, fixture.repo)

    assert fixture.registry["size_policy"]["mode"] == "s06a_bootstrap_no_growth"
    assert (
        fixture.registry["size_policy"]["hard_limit_activation"]
        == "blocked_in_s06a_until_separate_payload_validator"
    )
    assert fixture.registry["size_policy"]["hard_limit_bytes"] is None
    assert fixture.registry["size_policy"]["activation_receipt"] is None
    assert fixture.policy["authority"]["may_issue_migration_receipt"] is False
    assert fixture.policy["authority"]["may_activate_hard_limit"] is False
    assert report["claims"]["hard_limit_activation_authorized"] is False


def test_tar_representation_verifies_files_and_symlink_target(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path, {"target.bin": b"payload\n"})
    link_target = "target.bin"
    manifest = {
        "aggregate_sha256": "a" * 64,
        "source_total_bytes": len(b"payload\n") + len(link_target.encode()),
        "files": [
            {
                "path": "target.bin",
                "bytes": len(b"payload\n"),
                "sha256": _sha256_bytes(b"payload\n"),
            }
        ],
        "symlinks": [
            {
                "path": "view.bin",
                "archive_link_target": link_target,
            }
        ],
    }
    container = fixture.object_root / "payload.tar"
    source_tree = tmp_path / "source-tree"
    source_tree.mkdir()
    (source_tree / "target.bin").write_bytes(b"payload\n")
    (source_tree / "view.bin").symlink_to(link_target)
    with tarfile.open(container, "w", format=tarfile.PAX_FORMAT) as archive:
        archive.add(source_tree / "target.bin", arcname="target.bin", recursive=False)
        archive.add(source_tree / "view.bin", arcname="view.bin", recursive=False)
    row = fixture.registry["objects"][1]
    row["representation"] = {
        "kind": "tar_posix_tree_v1",
        "original_tree_manifest_sha256": "b" * 64,
        "original_aggregate_sha256": "a" * 64,
        "container_relative_path": "payload.tar",
        "container_sha256": _sha256(container),
        "container_bytes": container.stat().st_size,
        "restore_contract": {
            "extract_to_posix_filesystem": True,
            "verify_regular_file_sha": True,
            "verify_symlink_target": True,
            "verify_member_set": True,
            "verify_total_logical_bytes": True,
        },
    }

    summary = validator._verify_tar_representation(
        fixture.external,
        row,
        manifest,
    )
    assert summary == {
        "symlink_count": 1,
        "total_bytes": manifest["source_total_bytes"],
    }

    row["representation"]["container_sha256"] = "0" * 64
    with pytest.raises(
        validator.PayloadValidationError,
        match="ARCHIVE_CONTAINER_DIGEST_MISMATCH",
    ):
        validator._verify_tar_representation(fixture.external, row, manifest)


def _write_aggregate_manifest(
    fixture: PayloadFixture,
    *,
    files: dict[str, bytes],
    member_count: int | None = None,
    aggregate_bytes: int | None = None,
    include_top_level: bool = False,
    top_level_files: int | None = None,
    top_level_bytes: int | None = None,
) -> None:
    entries = [
        {
            "path": relative,
            "bytes": len(content),
            "sha256": _sha256_bytes(content),
        }
        for relative, content in sorted(files.items())
    ]
    actual_files = len(entries)
    actual_bytes = sum(entry["bytes"] for entry in entries)
    manifest: dict = {
        "aggregate": {
            "member_count": actual_files if member_count is None else member_count,
            "total_bytes": actual_bytes if aggregate_bytes is None else aggregate_bytes,
        },
        "files": entries,
    }
    if include_top_level:
        manifest["total_files"] = (
            actual_files if top_level_files is None else top_level_files
        )
        manifest["total_bytes"] = (
            actual_bytes if top_level_bytes is None else top_level_bytes
        )
    _write_json(fixture.manifest_path, manifest)
    _rebind_manifest(fixture)


def _write_binding(fixture: PayloadFixture, absolute_directory: Path) -> Path:
    binding = {
        "contract_version": "external-root-binding-v1",
        "bindings": [
            {
                "root_id": "repository_sibling_external_archive_v1",
                "absolute_directory": str(absolute_directory),
            }
        ],
    }
    binding_path = fixture.repo / inventory.BINDING_RELATIVE
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(binding_path, binding)
    return binding_path


def test_nested_aggregate_totals_pass_without_top_level_fields(
    tmp_path: Path,
) -> None:
    files = {"a.bin": b"aa", "b.bin": b"bbb"}
    fixture = _make_fixture(tmp_path, files)
    _write_aggregate_manifest(fixture, files=files)

    report = validator.validate_payload(TARGET_ID, fixture.repo)
    assert report["status"] == "PASS"
    assert report["verification"]["file_count"] == 2
    assert report["verification"]["total_bytes"] == 5
    assert validator._resolve_manifest_total(
        json.loads(fixture.manifest_path.read_text(encoding="utf-8")),
        "aggregate.member_count",
    ) == 2


def test_nested_aggregate_totals_mismatch_entries(tmp_path: Path) -> None:
    files = {"result.bin": b"fixture payload\n"}
    fixture = _make_fixture(tmp_path, files)
    _write_aggregate_manifest(fixture, files=files, member_count=99)

    _expect_error(fixture, "PAYLOAD_MANIFEST_TOTAL_MISMATCH")


def test_top_level_and_nested_totals_disagree(tmp_path: Path) -> None:
    files = {"result.bin": b"fixture payload\n"}
    fixture = _make_fixture(tmp_path, files)
    _write_aggregate_manifest(
        fixture,
        files=files,
        include_top_level=True,
        member_count=99,
    )

    _expect_error(fixture, "PAYLOAD_MANIFEST_TOTAL_MISMATCH")


def test_private_binding_resolves_missing_sibling_without_leaking_path(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    bound = tmp_path / "bound-archive"
    fixture.external.rename(bound)
    assert not fixture.external.exists()
    binding_path = _write_binding(fixture, bound)

    report = validator.validate_payload(TARGET_ID, fixture.repo)
    serialized = validator._json_bytes(report)

    assert report["status"] == "PASS"
    assert str(bound).encode("utf-8") not in serialized
    assert bound.as_posix().encode("utf-8") not in serialized
    assert report["bindings"]["storage_root_binding_sha256"] == _sha256(binding_path)
    assert report["bindings"][
        "storage_root_device_fingerprint"
    ] == inventory.storage_root_device_fingerprint(bound)


def test_binding_symlink_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    real = tmp_path / "real-archive"
    fixture.external.rename(real)
    linked = tmp_path / "link-archive"
    linked.symlink_to(real, target_is_directory=True)
    _write_binding(fixture, linked)

    _expect_error(fixture, "PAYLOAD_TARGET_ROOT_INVALID")

    binding_path = fixture.repo / inventory.BINDING_RELATIVE
    linked_binding = fixture.repo / ".local/linked_bindings.json"
    binding_bytes = binding_path.read_bytes()
    linked_binding.write_bytes(binding_bytes)
    binding_path.unlink()
    binding_path.symlink_to(linked_binding)
    _expect_error(fixture, "PAYLOAD_TARGET_ROOT_INVALID")


def test_live_registry_policy_covers_every_external_archive_object() -> None:
    registry = json.loads(
        (ROOT / "governance/external_archive_registry.json").read_text(
            encoding="utf-8"
        )
    )
    policy = json.loads(
        (ROOT / "governance/external_payload_validation_policy.json").read_text(
            encoding="utf-8"
        )
    )
    validator._validate_policy_relations(policy, registry)
    assert len(policy["targets"]) == 41
    assert len(policy["exclusions"]) == 4
    targets = {row["artifact_id"]: row for row in policy["targets"]}
    for artifact_id in (
        "t5-r04-v2-correction-segment-scan-batch08-20260803-v1",
        "z76-phase2-semantic-inspector-pilot-runtime-20260721-v1",
    ):
        assert targets[artifact_id]["manifest_total_files_field"] == "file_count"
        assert targets[artifact_id]["manifest_total_bytes_field"] == "total_bytes"


@pytest.mark.parametrize(
    "inventory_code",
    [
        "EXTERNAL_VOLUME_UUID_NOT_UNIQUE",
        "EXTERNAL_VOLUME_DISCOVERY_FAILED",
        "EXTERNAL_VOLUME_MOUNT_INVALID",
    ],
)
def test_t7_unmounted_is_not_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    inventory_code: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    fixture.registry["storage_roots"].insert(
        0,
        {
            "root_id": "physical_external_archive_t7_v1",
            "locator": {
                "kind": "external_volume_uuid",
                "volume_uuid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
                "expected_volume_name": "T7 Shield",
                "relative_root": "archive/v1",
            },
            "role": "external_archive",
            "required": True,
            "failure_domain": "different_physical_device",
            "boundary": "合成 T7 外置卷；本测试不挂载。",
        },
    )
    target = next(
        row for row in fixture.registry["objects"] if row["artifact_id"] == TARGET_ID
    )
    target["root_id"] = "physical_external_archive_t7_v1"
    target["recoverability"] = "package_integrity_proven_different_physical_device"
    target["representation"] = {
        "kind": "tar_posix_tree_v1",
        "original_tree_manifest_sha256": target["manifest"]["sha256"],
        "original_aggregate_sha256": "a" * 64,
        "container_relative_path": "payload.tar",
        "container_sha256": "b" * 64,
        "container_bytes": 1,
        "restore_contract": {
            "extract_to_posix_filesystem": True,
            "verify_regular_file_sha": True,
            "verify_symlink_target": True,
            "verify_member_set": True,
            "verify_total_logical_bytes": True,
        },
    }
    _write_json(fixture.registry_path, fixture.registry)

    def missing_volume(*_args: object, **_kwargs: object) -> Path:
        raise inventory.InventoryError(inventory_code, "合成未挂载")

    monkeypatch.setattr(
        inventory,
        "_resolve_external_volume_uuid",
        missing_volume,
    )

    with pytest.raises(validator.PayloadValidationError) as caught:
        validator.validate_payload(TARGET_ID, fixture.repo)
    assert caught.value.code == validator.PAYLOAD_VOLUME_NOT_MOUNTED
    assert str(caught.value).startswith(validator.NOT_RUN_VOLUME_NOT_MOUNTED)
    assert f"artifact_id={TARGET_ID}" in str(caught.value)
    assert "root_id=physical_external_archive_t7_v1" in str(caught.value)
    assert "expected_volume_name=T7 Shield" in str(caught.value)
    receipt = caught.value.as_not_run_receipt()
    assert receipt["status"] == "NOT_RUN"
    assert receipt["artifact_id"] == TARGET_ID
    assert receipt["root_id"] == "physical_external_archive_t7_v1"
    assert receipt["expected_mount"]["expected_volume_name"] == "T7 Shield"
    assert receipt["expected_mount"]["volume_uuid"] == (
        "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    )
    assert receipt["expected_mount"]["relative_root"] == "archive/v1"

    monkeypatch.setattr(validator, "ROOT", fixture.repo)
    assert validator.main(["check", "--artifact-id", TARGET_ID]) == 4
    captured = capsys.readouterr()
    assert captured.err.startswith(validator.NOT_RUN_VOLUME_NOT_MOUNTED)
    assert f"artifact_id={TARGET_ID}" in captured.err
    assert captured.out == ""

    assert validator.main(["report", "--artifact-id", TARGET_ID]) == 4
    reported = capsys.readouterr()
    assert reported.err.startswith(validator.NOT_RUN_VOLUME_NOT_MOUNTED)
    payload = json.loads(reported.out)
    assert payload["status"] == "NOT_RUN"
    assert payload["artifact_id"] == TARGET_ID
    assert payload["root_id"] == "physical_external_archive_t7_v1"
    assert str(fixture.repo) not in reported.out
    assert str(fixture.external) not in reported.out


@pytest.mark.parametrize(
    "wrong_value",
    ["2", True, 2.5, {"member_count": 1}],
    ids=["string", "bool", "float", "object"],
)
def test_top_level_total_wrong_type_does_not_fall_back_to_aggregate(
    tmp_path: Path,
    wrong_value: object,
) -> None:
    files = {"a.bin": b"aa", "b.bin": b"bbb"}
    fixture = _make_fixture(tmp_path, files)
    _write_aggregate_manifest(
        fixture,
        files=files,
        include_top_level=True,
    )
    manifest = json.loads(fixture.manifest_path.read_text(encoding="utf-8"))
    manifest["total_files"] = wrong_value
    _write_json(fixture.manifest_path, manifest)
    _rebind_manifest(fixture)

    _expect_error(fixture, "PAYLOAD_MANIFEST_TOTAL_TYPE_INVALID")


def test_aggregate_wrong_type_is_rejected_instead_of_being_swallowed(
    tmp_path: Path,
) -> None:
    files = {"result.bin": b"fixture payload\n"}
    fixture = _make_fixture(tmp_path, files)
    manifest = json.loads(fixture.manifest_path.read_text(encoding="utf-8"))
    del manifest["total_files"]
    del manifest["total_bytes"]
    manifest["aggregate"] = "not-an-object"
    _write_json(fixture.manifest_path, manifest)
    _rebind_manifest(fixture)

    _expect_error(fixture, "PAYLOAD_MANIFEST_TOTAL_TYPE_INVALID")


def test_report_does_not_false_positive_when_home_name_is_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", "/root")
    fixture = _make_fixture(tmp_path)
    report = validator.validate_payload(TARGET_ID, fixture.repo)
    serialized = validator._json_bytes(report)

    assert report["status"] == "PASS"
    assert b'"root_id"' in serialized
    assert Path.home() == Path("/root")
    assert str(Path.home()).encode() not in serialized
    assert b"/root/" not in serialized


def test_governance_readme_s06b_points_to_machine_policy_not_hardcoded_whitelist() -> None:
    text = (ROOT / "governance/README.md").read_text(encoding="utf-8")
    start = text.index("## S-06-B")
    end = text.index("## S-06-C")
    section = text[start:end]
    assert "external_payload_validation_policy.json" in section
    assert "当前白名单有 S-05-B 回放包" not in section
    assert "86 个文件／1,664,821 字节" not in section
    assert "S-07-G-A／G-B-A" not in section
    assert "`targets`" in section
    assert "`exclusions`" in section

