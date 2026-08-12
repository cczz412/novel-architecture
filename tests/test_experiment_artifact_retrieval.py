from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from tools import experiment_artifact_retrieval as retrieval


ROOT = Path(__file__).resolve().parents[1]
CARD_IDS = ("fixture-card-alpha", "fixture-card-beta")
ARTIFACT_IDS = ("fixture-artifact-alpha", "fixture-artifact-beta")
SELECTION_IDS = ("full-payload", "selected-payload")
SCHEMA_PATHS = {
    "card": ROOT / "governance/contracts/experiment_result_card_v1.schema.json",
    "pointer": ROOT / "governance/contracts/external_artifact_pointer_v1.schema.json",
    "profile": ROOT / "governance/contracts/artifact_retrieval_profile_v1.schema.json",
    "policy": ROOT / "governance/contracts/artifact_retrieval_policy_v1.schema.json",
    "plan": ROOT / "governance/contracts/artifact_retrieval_plan_v1.schema.json",
}


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _manifest(entries: dict[str, bytes]) -> dict[str, Any]:
    files = [
        {
            "path": path,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        for path, payload in sorted(entries.items())
    ]
    return {
        "total_files": len(files),
        "total_bytes": sum(row["bytes"] for row in files),
        "files": files,
    }


def _profile(artifact_id: str, selection_id: str, *, exact: bool) -> dict[str, Any]:
    return {
        "contract_version": "artifact-retrieval-profile-v1",
        "profile_id": f"{artifact_id}-retrieval",
        "artifact_id": artifact_id,
        "operation": "copy",
        "source_scope": "registered_external_payload_manifest",
        "destination": {
            "root_id": "repository_sibling_test_workspace_v1",
            "relative_root": "payload",
            "fresh_workspace_required": True,
            "no_overwrite": True,
        },
        "selections": [
            {
                "selection_id": selection_id,
                "mode": ("exact_manifest_paths" if exact else "all_manifest_entries"),
                "manifest_paths": ["a.txt"] if exact else [],
                "purpose": "只生成合成复制计划，不执行复制。",
            }
        ],
        "safety": {
            "reject_symlink": True,
            "reject_hardlink": True,
            "reject_special_file": True,
            "verify_source_before_copy": True,
            "verify_target_after_copy": True,
            "no_source_write": True,
            "no_runtime_source_reference": True,
        },
        "boundary": "合成取件组合只供只读解析。",
    }


def _pointer(
    card_id: str,
    artifact_id: str,
    manifest_sha256: str,
    profile_path: str,
    profile_sha256: str,
) -> dict[str, Any]:
    return {
        "contract_version": "external-artifact-pointer-v1",
        "pointer_id": f"{card_id}-pointer",
        "card_id": card_id,
        "artifact_id": artifact_id,
        "registry_id": "fixture-storage-registry",
        "expected_manifest_sha256": manifest_sha256,
        "validation_policy_id": "fixture-s06b-validation",
        "retrieval_profile_ref": {
            "path": profile_path,
            "sha256": profile_sha256,
        },
        "root_resolution": "registry_only_no_absolute_path",
        "claims": {
            "same_failure_domain": True,
            "independent_backup_proven": False,
            "retrieval_copy_performed": False,
            "migration_complete": False,
        },
        "boundary": "只保存对象编号和清单身份，不保存绝对路径。",
    }


def _card(
    card_id: str,
    pointer_path: str,
    pointer_sha256: str,
    evidence_path: str,
    evidence_sha256: str,
    *,
    alpha: bool,
) -> dict[str, Any]:
    return {
        "contract_version": "experiment-result-card-v1",
        "card_id": card_id,
        "experiment_id": card_id.upper(),
        "record_kind": "historical_replay",
        "title": f"{card_id} 合成轻量结论",
        "terminal_status": "superseded" if alpha else "completed",
        "quality_verdict": "failed" if alpha else "passed",
        "purpose": "验证固定清单能否被安全解析成复制计划。",
        "assembly_summary": [
            "程序钉在合成 Git 提交。",
            "材料只从显式登记的仓外对象解析。",
        ],
        "short_conclusion": [
            "这是一张测试用轻量结论卡。",
            "解析器没有读取 payload，也没有复制、移动或删除。",
        ],
        "evidence_boundary": "只证明机器合同链和固定清单可解析。",
        "consumer_closure": {
            "status": "verified",
            "consumers": ["tools/fixture_consumer.py"],
            "evidence_refs": [
                {
                    "path": evidence_path,
                    "sha256": evidence_sha256,
                }
            ],
        },
        "source_git_commit": ("a" if alpha else "b") * 40,
        "pointer_ref": {
            "path": pointer_path,
            "sha256": pointer_sha256,
        },
        "relations": {
            "supersedes_card_ids": [] if alpha else [CARD_IDS[0]],
            "superseded_by_card_ids": [CARD_IDS[1]] if alpha else [],
        },
        "boundary": "本卡不授权复制、移动、删除、恢复或迁移。",
    }


def _registry(
    manifest_paths: dict[str, Path],
    manifest_documents: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    objects = []
    for artifact_id in ARTIFACT_IDS:
        manifest = manifest_documents[artifact_id]
        manifest_path = manifest_paths[artifact_id]
        objects.append(
            {
                "artifact_id": artifact_id,
                "root_id": retrieval.EXTERNAL_ROOT_ID,
                "relative_path": manifest_path.parent.name,
                "externalization": "already_external",
                "consumer_closure": "verified",
                "manifest": {
                    "relative_path": manifest_path.name,
                    "sha256": _sha256(manifest_path),
                    "expected_entry_count": len(manifest["files"]),
                    "entries_field": "files",
                    "entry_path_field": "path",
                    "entry_sha256_field": "sha256",
                },
            }
        )
    return {
        "schema_version": "artifact-storage-v1",
        "registry_id": "fixture-storage-registry",
        "authority": {
            "may_authorize_migration": False,
            "may_authorize_deletion": False,
        },
        "capability_limits": {
            "write": False,
            "move": False,
            "delete": False,
        },
        "storage_roots": [
            {
                "root_id": retrieval.EXTERNAL_ROOT_ID,
                "locator": {
                    "kind": "repository_sibling_suffix",
                    "suffix": "_外置仓",
                },
                "role": "external_archive",
                "required": True,
                "failure_domain": "same_volume_as_repository",
            }
        ],
        "objects": objects,
    }


def _validation_policy(
    manifest_paths: dict[str, Path],
) -> dict[str, Any]:
    return {
        "contract_version": "external-payload-validation-policy-v1",
        "policy_id": "fixture-s06b-validation",
        "registry_id": "fixture-storage-registry",
        "authority": {
            "may_discover_targets": False,
            "may_move": False,
            "may_delete": False,
            "may_activate_hard_limit": False,
        },
        "targets": [
            {
                "artifact_id": artifact_id,
                "manifest_sha256": _sha256(manifest_paths[artifact_id]),
                "payload_root_relative_path": "payload",
                "entry_size_field": "bytes",
                "manifest_total_files_field": "total_files",
                "manifest_total_bytes_field": "total_bytes",
                "exact_file_set": True,
            }
            for artifact_id in ARTIFACT_IDS
        ],
    }


def _retrieval_policy(card_paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "contract_version": "artifact-retrieval-policy-v1",
        "policy_id": "fixture-s06c-retrieval",
        "registry_id": "fixture-storage-registry",
        "validation_policy_id": "fixture-s06b-validation",
        "authority": {
            "scope": "registered_manifest_to_copy_plan_only",
            "may_discover_targets": False,
            "may_read_payload": False,
            "may_copy": False,
            "may_move": False,
            "may_delete": False,
            "may_restore": False,
            "may_issue_migration_receipt": False,
            "may_activate_hard_limit": False,
        },
        "capability_limits": {
            "one_card_per_command": True,
            "registered_manifest_read": True,
            "deterministic_plan_output": True,
            "write": False,
            "network": False,
            "credential_read": False,
            "model_call": False,
            "notion_write": False,
        },
        "allowed_root_ids": [retrieval.EXTERNAL_ROOT_ID],
        "cards": [
            {
                "card_id": card_id,
                "result_card_ref": {
                    "path": card_paths[card_id]
                    .relative_to(card_paths[card_id].parents[4])
                    .as_posix(),
                    "sha256": _sha256(card_paths[card_id]),
                },
                "allowed_selection_ids": [SELECTION_IDS[index]],
            }
            for index, card_id in enumerate(CARD_IDS)
        ],
        "protected_non_targets": [
            {
                "subject_id": retrieval.PROTECTED_R02_ID,
                "reason": "正在运行的 R02 只保留排除事实，禁止发现和枚举。",
                "discovery_prohibited": True,
            }
        ],
        "boundary": "只允许两张显式卡生成复制计划。",
    }


@dataclass
class RetrievalFixture:
    repo: Path
    external: Path
    registry_path: Path
    validation_policy_path: Path
    retrieval_policy_path: Path
    evidence_path: Path
    card_paths: dict[str, Path]
    pointer_paths: dict[str, Path]
    profile_paths: dict[str, Path]
    readme_paths: dict[str, Path]
    manifest_paths: dict[str, Path]


def _make_fixture(tmp_path: Path) -> RetrievalFixture:
    repo = tmp_path / "repo"
    external = tmp_path / "repo_外置仓"
    repo.mkdir()
    external.mkdir()

    resolver_path = repo / retrieval.RESOLVER_RELATIVE
    resolver_path.parent.mkdir(parents=True)
    shutil.copy2(ROOT / retrieval.RESOLVER_RELATIVE, resolver_path)

    evidence_path = repo / "config/test_replay/evidence.json"
    _write_json(evidence_path, {"fixture": True})

    manifest_documents = {
        ARTIFACT_IDS[0]: _manifest(
            {
                "a.txt": b"a",
                "dir/b.json": b"{}",
            }
        ),
        ARTIFACT_IDS[1]: _manifest(
            {
                "a.txt": b"alpha",
                "z.bin": b"\x00\x01",
            }
        ),
    }
    manifest_paths: dict[str, Path] = {}
    for artifact_id, document in manifest_documents.items():
        manifest_path = external / artifact_id / "MANIFEST.json"
        _write_json(manifest_path, document)
        manifest_paths[artifact_id] = manifest_path

    card_paths: dict[str, Path] = {}
    pointer_paths: dict[str, Path] = {}
    profile_paths: dict[str, Path] = {}
    readme_paths: dict[str, Path] = {}
    for index, (card_id, artifact_id) in enumerate(zip(CARD_IDS, ARTIFACT_IDS)):
        card_dir = repo / "config/test_replay/result_cards" / card_id
        profile_path = card_dir / "retrieval_profile.json"
        pointer_path = card_dir / "external_pointer.json"
        card_path = card_dir / "result_card.json"
        readme_path = card_dir / "README.md"

        _write_json(
            profile_path,
            _profile(
                artifact_id,
                SELECTION_IDS[index],
                exact=index == 1,
            ),
        )
        profile_relative = profile_path.relative_to(repo).as_posix()
        pointer = _pointer(
            card_id,
            artifact_id,
            _sha256(manifest_paths[artifact_id]),
            profile_relative,
            _sha256(profile_path),
        )
        _write_json(pointer_path, pointer)
        card = _card(
            card_id,
            pointer_path.relative_to(repo).as_posix(),
            _sha256(pointer_path),
            evidence_path.relative_to(repo).as_posix(),
            _sha256(evidence_path),
            alpha=index == 0,
        )
        _write_json(card_path, card)

        card_paths[card_id] = card_path
        pointer_paths[card_id] = pointer_path
        profile_paths[card_id] = profile_path
        readme_paths[card_id] = readme_path

    registry_path = repo / retrieval.REGISTRY_RELATIVE
    validation_policy_path = repo / retrieval.VALIDATION_POLICY_RELATIVE
    retrieval_policy_path = repo / retrieval.RETRIEVAL_POLICY_RELATIVE
    _write_json(
        registry_path,
        _registry(manifest_paths, manifest_documents),
    )
    _write_json(
        validation_policy_path,
        _validation_policy(manifest_paths),
    )
    _write_json(
        retrieval_policy_path,
        _retrieval_policy(card_paths),
    )
    for card_id in CARD_IDS:
        readme_paths[card_id].write_text(
            retrieval.render_card_markdown(repo, card_id),
            encoding="utf-8",
        )

    return RetrievalFixture(
        repo=repo,
        external=external,
        registry_path=registry_path,
        validation_policy_path=validation_policy_path,
        retrieval_policy_path=retrieval_policy_path,
        evidence_path=evidence_path,
        card_paths=card_paths,
        pointer_paths=pointer_paths,
        profile_paths=profile_paths,
        readme_paths=readme_paths,
        manifest_paths=manifest_paths,
    )


def _refresh_card_chain(fixture: RetrievalFixture, card_id: str) -> None:
    profile_path = fixture.profile_paths[card_id]
    pointer_path = fixture.pointer_paths[card_id]
    card_path = fixture.card_paths[card_id]

    pointer = _read_json(pointer_path)
    pointer["retrieval_profile_ref"]["sha256"] = _sha256(profile_path)
    _write_json(pointer_path, pointer)

    card = _read_json(card_path)
    card["pointer_ref"]["sha256"] = _sha256(pointer_path)
    _write_json(card_path, card)

    _update_policy_card_hash(fixture, card_id)

    fixture.readme_paths[card_id].write_text(
        retrieval.render_card_markdown(fixture.repo, card_id),
        encoding="utf-8",
    )


def _update_policy_card_hash(
    fixture: RetrievalFixture,
    card_id: str,
) -> None:
    policy = _read_json(fixture.retrieval_policy_path)
    policy_row = next(row for row in policy["cards"] if row["card_id"] == card_id)
    policy_row["result_card_ref"]["sha256"] = _sha256(fixture.card_paths[card_id])
    _write_json(fixture.retrieval_policy_path, policy)


def _reseal_manifest(
    fixture: RetrievalFixture,
    card_id: str,
    manifest: dict[str, Any],
) -> None:
    index = CARD_IDS.index(card_id)
    artifact_id = ARTIFACT_IDS[index]
    manifest_path = fixture.manifest_paths[artifact_id]
    _write_json(manifest_path, manifest)
    digest = _sha256(manifest_path)

    registry = _read_json(fixture.registry_path)
    object_row = next(
        row for row in registry["objects"] if row["artifact_id"] == artifact_id
    )
    object_row["manifest"]["sha256"] = digest
    object_row["manifest"]["expected_entry_count"] = len(manifest["files"])
    _write_json(fixture.registry_path, registry)

    validation_policy = _read_json(fixture.validation_policy_path)
    target = next(
        row for row in validation_policy["targets"] if row["artifact_id"] == artifact_id
    )
    target["manifest_sha256"] = digest
    _write_json(fixture.validation_policy_path, validation_policy)

    pointer = _read_json(fixture.pointer_paths[card_id])
    pointer["expected_manifest_sha256"] = digest
    _write_json(fixture.pointer_paths[card_id], pointer)
    _refresh_card_chain(fixture, card_id)


def _schema(name: str) -> dict[str, Any]:
    return _read_json(SCHEMA_PATHS[name])


def _assert_schema(name: str, value: object) -> None:
    errors = sorted(
        Draft202012Validator(_schema(name)).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    assert not errors, "\n".join(
        f"{'/'.join(map(str, error.absolute_path))}: {error.message}"
        for error in errors
    )


@pytest.mark.parametrize(
    ("card_id", "selection_id", "expected_paths"),
    [
        (
            CARD_IDS[0],
            SELECTION_IDS[0],
            ["a.txt", "dir/b.json"],
        ),
        (
            CARD_IDS[1],
            SELECTION_IDS[1],
            ["a.txt"],
        ),
    ],
)
def test_two_cards_check_resolve_and_schema_chain(
    tmp_path: Path,
    card_id: str,
    selection_id: str,
    expected_paths: list[str],
) -> None:
    fixture = _make_fixture(tmp_path)

    context = retrieval.check_card(fixture.repo, card_id)
    first_plan = retrieval.build_plan(fixture.repo, card_id, selection_id)
    second_plan = retrieval.build_plan(fixture.repo, card_id, selection_id)

    assert context.chain.card["card_id"] == card_id
    assert first_plan == second_plan
    assert [row["source_manifest_path"] for row in first_plan["items"]] == (
        expected_paths
    )
    assert [row["destination"] for row in first_plan["items"]] == [
        f"payload/{path}" for path in expected_paths
    ]
    assert first_plan["summary"]["file_count"] == len(expected_paths)
    assert first_plan["claims"] == {
        "manifest_resolved": True,
        "payload_bytes_revalidated": False,
        "copy_performed": False,
        "move_performed": False,
        "delete_performed": False,
        "migration_complete": False,
        "hard_limit_activated": False,
    }

    _assert_schema("policy", _read_json(fixture.retrieval_policy_path))
    _assert_schema("card", _read_json(fixture.card_paths[card_id]))
    _assert_schema("pointer", _read_json(fixture.pointer_paths[card_id]))
    _assert_schema("profile", _read_json(fixture.profile_paths[card_id]))
    _assert_schema("plan", first_plan)


def test_plan_schema_rejects_empty_items(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    plan = retrieval.build_plan(
        fixture.repo,
        CARD_IDS[0],
        SELECTION_IDS[0],
    )
    plan["items"] = []
    errors = list(Draft202012Validator(_schema("plan")).iter_errors(plan))

    assert errors
    assert any(list(error.absolute_path) == ["items"] for error in errors)


@pytest.mark.parametrize("card_id", CARD_IDS)
def test_cli_check_resolve_and_render_use_only_fixture_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    card_id: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    selection_id = SELECTION_IDS[CARD_IDS.index(card_id)]
    monkeypatch.setattr(retrieval, "ROOT", fixture.repo)

    assert retrieval.main(["check", "--card-id", card_id]) == 0
    check_output = capsys.readouterr()
    assert check_output.err == ""
    assert "未读取 payload、未复制、未移动、未删除" in check_output.out

    assert (
        retrieval.main(
            [
                "resolve",
                "--card-id",
                card_id,
                "--selection-id",
                selection_id,
            ]
        )
        == 0
    )
    resolve_output = capsys.readouterr()
    assert resolve_output.err == ""
    _assert_schema("plan", json.loads(resolve_output.out))

    assert retrieval.main(["render", "--card-id", card_id]) == 0
    render_output = capsys.readouterr()
    assert render_output.err == ""
    assert render_output.out == fixture.readme_paths[card_id].read_text(
        encoding="utf-8"
    )
    assert str(fixture.external) not in (
        check_output.out + resolve_output.out + render_output.out
    )


def _all_parser_options(parser: argparse.ArgumentParser) -> set[str]:
    options = {option for action in parser._actions for option in action.option_strings}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                options.update(_all_parser_options(child))
    return options


def test_cli_has_no_arbitrary_path_or_mutating_surface() -> None:
    parser = retrieval.build_parser()
    subparser_action = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert set(subparser_action.choices) == {
        "check",
        "resolve",
        "render",
        "restore-archive",
    }
    assert {
        "--root",
        "--path",
        "--glob",
        "--copy",
        "--move",
        "--delete",
    }.isdisjoint(_all_parser_options(parser))

    for forbidden_command in ("copy", "move", "delete"):
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([forbidden_command])
        assert exc_info.value.code == 2


def test_policy_only_allows_explicit_cards_without_touching_external_root(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    fixture.external.rename(fixture.external.with_name("external-hidden"))

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, "unlisted-card")

    assert exc_info.value.code == "CARD_NOT_ALLOWED"


def test_missing_active_r02_exclusion_is_a_hard_stop(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    policy = _read_json(fixture.retrieval_policy_path)
    policy["protected_non_targets"] = []
    _write_json(fixture.retrieval_policy_path, policy)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.load_card_chain(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "ACTIVE_R02_EXCLUSION_MISSING"


@pytest.mark.parametrize(
    ("reference_kind", "expected_code"),
    [
        ("policy_card", "RESULT_CARD_LOCATION_INVALID"),
        ("card_pointer", "EXTERNAL_POINTER_LOCATION_INVALID"),
        ("pointer_profile", "RETRIEVAL_PROFILE_LOCATION_INVALID"),
        ("evidence", "RESULT_CARD_EVIDENCE_LOCATION_INVALID"),
    ],
)
def test_r02_reference_is_rejected_before_any_target_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference_kind: str,
    expected_code: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    card_id = CARD_IDS[0]
    forbidden = f"TEMP/CMIN-B-REFREEZE-20260730-R02/{reference_kind}.json"

    if reference_kind == "policy_card":
        policy = _read_json(fixture.retrieval_policy_path)
        row = next(row for row in policy["cards"] if row["card_id"] == card_id)
        row["result_card_ref"] = {
            "path": forbidden,
            "sha256": "0" * 64,
        }
        _write_json(fixture.retrieval_policy_path, policy)
    elif reference_kind == "card_pointer":
        card = _read_json(fixture.card_paths[card_id])
        card["pointer_ref"] = {
            "path": forbidden,
            "sha256": "0" * 64,
        }
        _write_json(fixture.card_paths[card_id], card)
        _update_policy_card_hash(fixture, card_id)
    elif reference_kind == "pointer_profile":
        pointer = _read_json(fixture.pointer_paths[card_id])
        pointer["retrieval_profile_ref"] = {
            "path": forbidden,
            "sha256": "0" * 64,
        }
        _write_json(fixture.pointer_paths[card_id], pointer)
        card = _read_json(fixture.card_paths[card_id])
        card["pointer_ref"]["sha256"] = _sha256(fixture.pointer_paths[card_id])
        _write_json(fixture.card_paths[card_id], card)
        _update_policy_card_hash(fixture, card_id)
    else:
        card = _read_json(fixture.card_paths[card_id])
        card["consumer_closure"]["evidence_refs"] = [
            {
                "path": forbidden,
                "sha256": "0" * 64,
            }
        ]
        _write_json(fixture.card_paths[card_id], card)
        _update_policy_card_hash(fixture, card_id)

    forbidden_path = fixture.repo / forbidden
    assert not forbidden_path.exists()
    original = retrieval._read_beneath_root
    observed: list[str] = []

    def reject_forbidden_read(
        root: Path,
        relative_value: object,
        *,
        max_bytes: int,
        code: str,
    ) -> tuple[bytes, retrieval.FileSnapshot, PurePosixPath]:
        relative_text = str(relative_value)
        observed.append(relative_text)
        assert not relative_text.startswith("TEMP/CMIN-B-REFREEZE-20260730-R02/")
        return original(
            root,
            relative_value,
            max_bytes=max_bytes,
            code=code,
        )

    monkeypatch.setattr(
        retrieval,
        "_read_beneath_root",
        reject_forbidden_read,
    )
    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.load_card_chain(fixture.repo, card_id)

    assert exc_info.value.code == expected_code
    assert forbidden not in observed
    assert not forbidden_path.exists()


@pytest.mark.parametrize("card_id", CARD_IDS)
def test_pointer_contains_no_absolute_path(
    tmp_path: Path,
    card_id: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    pointer = _read_json(fixture.pointer_paths[card_id])

    def strings(value: object) -> list[str]:
        if isinstance(value, dict):
            return [item for child in value.values() for item in strings(child)]
        if isinstance(value, list):
            return [item for child in value for item in strings(child)]
        return [value] if isinstance(value, str) else []

    assert pointer["root_resolution"] == "registry_only_no_absolute_path"
    assert not any(value.startswith("/") for value in strings(pointer))
    assert str(fixture.repo) not in json.dumps(pointer, ensure_ascii=False)
    assert str(fixture.external) not in json.dumps(pointer, ensure_ascii=False)


@pytest.mark.parametrize(
    ("path_kind", "expected_code"),
    [
        ("manifest", "ARTIFACT_MANIFEST_SHA_MISMATCH"),
        ("card", "RESULT_CARD_SHA_MISMATCH"),
        ("pointer", "EXTERNAL_POINTER_SHA_MISMATCH"),
        ("profile", "RETRIEVAL_PROFILE_SHA_MISMATCH"),
    ],
)
def test_bound_file_sha_drift_fails_closed(
    tmp_path: Path,
    path_kind: str,
    expected_code: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    card_id = CARD_IDS[0]
    paths = {
        "manifest": fixture.manifest_paths[ARTIFACT_IDS[0]],
        "card": fixture.card_paths[card_id],
        "pointer": fixture.pointer_paths[card_id],
        "profile": fixture.profile_paths[card_id],
    }
    path = paths[path_kind]
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, card_id)

    assert exc_info.value.code == expected_code


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("externalization", "in_repository"),
        ("consumer_closure", "open"),
        ("root_id", "repository_main_v1"),
    ],
)
def test_artifact_must_be_external_and_consumer_verified(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    registry = _read_json(fixture.registry_path)
    object_row = next(
        row for row in registry["objects"] if row["artifact_id"] == ARTIFACT_IDS[0]
    )
    object_row[field] = value
    _write_json(fixture.registry_path, registry)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "ARTIFACT_NOT_RETRIEVAL_ELIGIBLE"


def test_artifact_must_remain_an_s06b_validation_target(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    policy = _read_json(fixture.validation_policy_path)
    policy["targets"] = [
        row for row in policy["targets"] if row["artifact_id"] != ARTIFACT_IDS[0]
    ]
    _write_json(fixture.validation_policy_path, policy)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "ARTIFACT_NOT_PAYLOAD_VALIDATION_TARGET"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("suffix_reroute", "EXTERNAL_ROOT_LOCATOR_INVALID"),
        ("duplicate_root_id", "REGISTRY_ROOT_IDS_INVALID"),
        ("duplicate_object_id", "REGISTRY_OBJECT_IDS_INVALID"),
    ],
)
def test_registry_cannot_reroute_or_duplicate_identity(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    registry = _read_json(fixture.registry_path)
    if mutation == "suffix_reroute":
        registry["storage_roots"][0]["locator"]["suffix"] = "_改道仓"
    elif mutation == "duplicate_root_id":
        registry["storage_roots"].append(
            json.loads(json.dumps(registry["storage_roots"][0]))
        )
    else:
        registry["objects"].append(json.loads(json.dumps(registry["objects"][0])))
    _write_json(fixture.registry_path, registry)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == expected_code


def test_two_cards_cannot_point_to_the_same_artifact_id(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    card_id = CARD_IDS[1]
    pointer = _read_json(fixture.pointer_paths[card_id])
    pointer["artifact_id"] = ARTIFACT_IDS[0]
    _write_json(fixture.pointer_paths[card_id], pointer)

    card = _read_json(fixture.card_paths[card_id])
    card["pointer_ref"]["sha256"] = _sha256(fixture.pointer_paths[card_id])
    _write_json(fixture.card_paths[card_id], card)
    _update_policy_card_hash(fixture, card_id)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.load_card_chain(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "RETRIEVAL_POLICY_ARTIFACT_ID_DUPLICATE"


def test_verified_card_requires_nonempty_evidence_refs(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    card_id = CARD_IDS[0]
    card = _read_json(fixture.card_paths[card_id])
    assert card["consumer_closure"]["status"] == "verified"
    card["consumer_closure"]["evidence_refs"] = []
    _write_json(fixture.card_paths[card_id], card)
    _update_policy_card_hash(fixture, card_id)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.load_card_chain(fixture.repo, card_id)

    assert exc_info.value.code == "RESULT_CARD_EVIDENCE_REFS_INVALID"


def test_card_relations_must_be_reciprocal(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    card_id = CARD_IDS[1]
    card = _read_json(fixture.card_paths[card_id])
    card["relations"]["supersedes_card_ids"] = []
    _write_json(fixture.card_paths[card_id], card)
    _update_policy_card_hash(fixture, card_id)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.load_card_chain(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "RESULT_CARD_RELATION_NOT_RECIPROCAL"


def test_manifest_path_traversal_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    manifest = _read_json(fixture.manifest_paths[ARTIFACT_IDS[0]])
    manifest["files"][0]["path"] = "../escape.txt"
    _reseal_manifest(fixture, CARD_IDS[0], manifest)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "MANIFEST_ENTRY_PATH_INVALID"


def test_manifest_double_slash_path_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    manifest = _read_json(fixture.manifest_paths[ARTIFACT_IDS[0]])
    manifest["files"][0]["path"] = "a//b.txt"
    _reseal_manifest(fixture, CARD_IDS[0], manifest)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "MANIFEST_ENTRY_PATH_INVALID"


def test_manifest_filename_is_fixed_before_external_read(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    registry = _read_json(fixture.registry_path)
    object_row = next(
        row for row in registry["objects"] if row["artifact_id"] == ARTIFACT_IDS[0]
    )
    object_row["manifest"]["relative_path"] = "alternate.json"
    _write_json(fixture.registry_path, registry)
    assert not (
        fixture.manifest_paths[ARTIFACT_IDS[0]].parent / "alternate.json"
    ).exists()

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "ARTIFACT_MANIFEST_PATH_NOT_FIXED"


def test_manifest_casefold_collision_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    manifest = _manifest(
        {
            "A.txt": b"upper",
            "a.txt": b"lower",
        }
    )
    _reseal_manifest(fixture, CARD_IDS[0], manifest)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "MANIFEST_ENTRY_PATH_COLLISION"


@pytest.mark.parametrize(
    ("field", "expected_code"),
    [
        ("total_files", "MANIFEST_TOTAL_FILES_MISMATCH"),
        ("total_bytes", "MANIFEST_TOTAL_BYTES_MISMATCH"),
    ],
)
def test_manifest_declared_totals_must_match_entries(
    tmp_path: Path,
    field: str,
    expected_code: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    manifest = _read_json(fixture.manifest_paths[ARTIFACT_IDS[0]])
    manifest[field] += 1
    _reseal_manifest(fixture, CARD_IDS[0], manifest)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == expected_code


def test_exact_selection_missing_from_manifest_is_rejected(tmp_path: Path) -> None:
    fixture = _make_fixture(tmp_path)
    profile_path = fixture.profile_paths[CARD_IDS[1]]
    profile = _read_json(profile_path)
    profile["selections"][0]["manifest_paths"] = ["missing.bin"]
    _write_json(profile_path, profile)
    _refresh_card_chain(fixture, CARD_IDS[1])

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.build_plan(
            fixture.repo,
            CARD_IDS[1],
            SELECTION_IDS[1],
        )

    assert exc_info.value.code == "SELECTION_PATH_NOT_IN_MANIFEST"


@pytest.mark.parametrize("unsafe_kind", ["symlink", "hardlink", "fifo"])
def test_manifest_symlink_hardlink_and_special_file_are_rejected(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    manifest_path = fixture.manifest_paths[ARTIFACT_IDS[0]]
    if unsafe_kind == "symlink":
        shadow = manifest_path.with_name("shadow.json")
        shutil.copy2(manifest_path, shadow)
        manifest_path.unlink()
        manifest_path.symlink_to(shadow.name)
    elif unsafe_kind == "hardlink":
        os.link(manifest_path, manifest_path.with_name("second-link.json"))
    else:
        if not hasattr(os, "mkfifo"):
            pytest.skip("platform has no FIFO support")
        manifest_path.unlink()
        os.mkfifo(manifest_path)

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "ARTIFACT_MANIFEST_UNSAFE"


def test_stable_symlink_in_manifest_parent_chain_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _make_fixture(tmp_path)
    manifest_path = fixture.manifest_paths[ARTIFACT_IDS[0]]
    artifact_directory = manifest_path.parent
    shadow_directory = fixture.external / "shadow-artifact"
    artifact_directory.rename(shadow_directory)
    artifact_directory.symlink_to(
        shadow_directory.name,
        target_is_directory=True,
    )

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert exc_info.value.code == "ARTIFACT_MANIFEST_PARENT_UNSAFE"


def test_manifest_parent_replacement_race_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    artifact_directory = fixture.manifest_paths[ARTIFACT_IDS[0]].parent
    original = retrieval._open_directory_chain
    swapped = False

    def swap_parent_after_first_open(
        root: Path,
        relative: PurePosixPath,
        *,
        code: str,
    ) -> tuple[list[int], int, tuple[tuple[int, ...], ...]]:
        nonlocal swapped
        result = original(root, relative, code=code)
        if not swapped and root == fixture.external and code == "ARTIFACT_MANIFEST":
            old_directory = fixture.external / "artifact-before-swap"
            artifact_directory.rename(old_directory)
            artifact_directory.mkdir()
            shutil.copy2(
                old_directory / "MANIFEST.json",
                artifact_directory / "MANIFEST.json",
            )
            swapped = True
        return result

    monkeypatch.setattr(
        retrieval,
        "_open_directory_chain",
        swap_parent_after_first_open,
    )
    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.resolve_context(fixture.repo, CARD_IDS[0])

    assert swapped is True
    assert exc_info.value.code == "ARTIFACT_MANIFEST_PARENT_RACE"


@pytest.mark.parametrize("card_id", CARD_IDS)
def test_readme_is_deterministic_and_drift_is_rejected(
    tmp_path: Path,
    card_id: str,
) -> None:
    fixture = _make_fixture(tmp_path)
    first = retrieval.render_card_markdown(fixture.repo, card_id)
    second = retrieval.render_card_markdown(fixture.repo, card_id)

    assert first == second
    assert first == fixture.readme_paths[card_id].read_text(encoding="utf-8")

    fixture.readme_paths[card_id].write_text(
        first + "手工改写\n",
        encoding="utf-8",
    )
    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.check_card(fixture.repo, card_id)

    assert exc_info.value.code == "RESULT_CARD_README_DRIFT"


def test_input_identity_drift_during_resolution_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    target = fixture.retrieval_policy_path
    original = retrieval._read_beneath_root
    reads = 0

    def mutate_before_second_read(
        root: Path,
        relative_value: object,
        *,
        max_bytes: int,
        code: str,
    ) -> tuple[bytes, retrieval.FileSnapshot, Any]:
        nonlocal reads
        if (
            root == fixture.repo
            and relative_value == retrieval.RETRIEVAL_POLICY_RELATIVE
        ):
            reads += 1
            if reads == 2:
                target.write_bytes(target.read_bytes() + b" ")
        return original(
            root,
            relative_value,
            max_bytes=max_bytes,
            code=code,
        )

    monkeypatch.setattr(
        retrieval,
        "_read_beneath_root",
        mutate_before_second_read,
    )

    with pytest.raises(retrieval.RetrievalError) as exc_info:
        retrieval.build_plan(
            fixture.repo,
            CARD_IDS[0],
            SELECTION_IDS[0],
        )

    assert exc_info.value.code == "INPUT_DRIFT_DURING_RESOLUTION"


def test_registered_tar_restore_preserves_file_and_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_fixture(tmp_path)
    artifact_id = ARTIFACT_IDS[0]
    object_root = fixture.external / artifact_id
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "a.txt").write_bytes(b"a")
    (payload / "link.txt").symlink_to("a.txt")
    manifest = {
        "aggregate_sha256": "b" * 64,
        "source_total_bytes": 6,
        "files": [
            {"path": "a.txt", "bytes": 1, "sha256": _sha256_bytes(b"a")}
        ],
        "symlinks": [
            {
                "path": "link.txt",
                "bytes": 5,
                "sha256": _sha256_bytes(b"a.txt"),
                "archive_link_target": "a.txt",
                "archive_target_exists": True,
                "resolved_sha256": _sha256_bytes(b"a"),
            }
        ],
    }
    _write_json(object_root / "MANIFEST.json", manifest)
    container = object_root / "payload.tar"
    with tarfile.open(container, "w", format=tarfile.PAX_FORMAT) as archive:
        archive.add(payload / "a.txt", arcname="a.txt", recursive=False)
        archive.add(payload / "link.txt", arcname="link.txt", recursive=False)
    registry = _read_json(fixture.registry_path)
    object_row = next(
        row for row in registry["objects"] if row["artifact_id"] == artifact_id
    )
    manifest_sha = _sha256(object_root / "MANIFEST.json")
    object_row["manifest"]["sha256"] = manifest_sha
    object_row["manifest"]["expected_entry_count"] = 1
    object_row["representation"] = {
        "kind": "tar_posix_tree_v1",
        "original_tree_manifest_sha256": manifest_sha,
        "original_aggregate_sha256": "b" * 64,
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
    _write_json(fixture.registry_path, registry)
    monkeypatch.setattr(
        retrieval,
        "_resolve_external_root",
        lambda _repo, _registry, _root_id=retrieval.EXTERNAL_ROOT_ID: (
            fixture.external,
            {},
        ),
    )
    destination = fixture.repo / "TEMP/restore/fixture"

    receipt = retrieval.restore_registered_archive(
        fixture.repo,
        artifact_id,
        destination,
    )

    assert receipt["status"] == "RESTORE_VERIFIED"
    assert receipt["member_count"] == 2
    assert receipt["symlink_count"] == 1
    assert (destination / "a.txt").read_bytes() == b"a"
    assert (destination / "link.txt").is_symlink()
    assert os.readlink(destination / "link.txt") == "a.txt"
