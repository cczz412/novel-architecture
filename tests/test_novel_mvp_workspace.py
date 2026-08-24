from __future__ import annotations

import copy
import inspect
import json
import os
import pickle
import stat
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp.workspace import (
        AuthorWorkspace,
        AuthenticationError,
        InjectedWorkspaceCrash,
        IntegrityError,
        InvalidLogicalKeyError,
        OperationConflictError,
        ProjectNotFoundError,
        UnsafePathError,
        VersionConflictError,
        WorkspaceError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


def _project_dir(runtime_root: Path, workspace) -> Path:
    return (
        runtime_root
        / "authors"
        / workspace.author_id
        / "projects"
        / workspace.project_id
    )


def _current_blob(runtime_root: Path, workspace, logical_key: str) -> Path:
    project_dir = _project_dir(runtime_root, workspace)
    pointer = json.loads((project_dir / "state/CURRENT.json").read_text())
    manifest = json.loads(
        (
            project_dir
            / "generations"
            / pointer["generation_id"]
            / "manifest.json"
        ).read_text()
    )
    blob_sha = manifest["entries"][logical_key]["blob_sha256"]
    return project_dir / "blobs" / f"{blob_sha}.json"


def _immutable_paths(
    runtime_root: Path,
    workspace,
    receipt: dict,
) -> tuple[Path, Path]:
    root = (
        runtime_root
        / "authors"
        / workspace.author_id
        / "immutable"
        / receipt["kind"]
    )
    content_sha = receipt["content_sha256"]
    return (
        root / "blobs" / f"{content_sha}.blob",
        root
        / "metadata"
        / content_sha
        / f"{receipt['metadata_sha256']}.json",
    )


def _reference_raw_upload(workspace, receipt: dict, operation_id: str) -> None:
    workspace.commit(
        operation_id,
        {
            "input_manifest": {
                "uploads": [
                    {
                        "source_name": "sample.txt",
                        "source_sha256": receipt["content_sha256"],
                        "bytes": receipt["size"],
                        "encoding_hint": "utf-8",
                        "cloud_swap_point": "UPLOAD_SOURCE_CONSTRUCTION",
                        "immutable_receipt": receipt,
                    }
                ]
            }
        },
        {"input_manifest": 0},
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def test_reads_do_not_create_directories_and_missing_projects_share_one_error(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)

    assert router.list_projects("principal-a") == []
    assert not runtime_root.exists()

    with pytest.raises(ProjectNotFoundError) as missing:
        router.open_project("principal-a", "p_" + "0" * 32)
    with pytest.raises(ProjectNotFoundError) as malformed:
        router.open_project("principal-a", "../project")

    assert missing.value.code == malformed.value.code == "PROJECT_NOT_FOUND"
    assert not runtime_root.exists()


def test_runtime_root_rejects_existing_symlink_ancestor(tmp_path: Path) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(UnsafePathError, match="SYMLINK_NOT_ALLOWED"):
        WorkspaceRouter(alias / "runtime")


def test_same_display_name_isolated_by_authenticated_principal_and_guess_is_hidden(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)

    alice = router.create_project("auth:alice", "../同名项目")
    bob = router.create_project("auth:bob", "../同名项目")

    assert alice.author_id != bob.author_id
    assert alice.project_id != bob.project_id
    assert router.list_projects("auth:alice") == [
        {
            "project_id": alice.project_id,
            "display_name": "../同名项目",
            "created_at": router.list_projects("auth:alice")[0]["created_at"],
        }
    ]
    assert [item["project_id"] for item in router.list_projects("auth:bob")] == [
        bob.project_id
    ]
    assert "同名项目" not in str(_project_dir(runtime_root, alice))

    with pytest.raises(ProjectNotFoundError) as guessed:
        router.open_project("auth:alice", bob.project_id)
    with pytest.raises(ProjectNotFoundError) as absent:
        router.open_project("auth:alice", "p_" + "f" * 32)
    assert guessed.value.code == absent.value.code == "PROJECT_NOT_FOUND"

    assert not hasattr(alice, "open_path")
    assert not hasattr(alice, "glob")
    assert not hasattr(router, "search_projects")


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("schema_version", "author-workspace-project-v2", "PROJECT_METADATA_INVALID"),
        ("project_id", "p_" + "0" * 32, "PROJECT_ID_BINDING_MISMATCH"),
        ("author_id", "a_" + "0" * 32, "PROJECT_AUTHOR_BINDING_MISMATCH"),
        ("display_name", None, "PROJECT_METADATA_INVALID"),
        ("created_at", "2026-02-30T00:00:00Z", "PROJECT_METADATA_INVALID"),
        ("remove:created_at", None, "PROJECT_METADATA_INVALID"),
        ("unexpected", "extra", "PROJECT_METADATA_INVALID"),
    ],
)
def test_list_and_open_share_strict_project_metadata_validation(
    tmp_path: Path,
    field: str,
    value: object,
    expected_code: str,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("auth:alice", "项目")
    metadata_path = _project_dir(runtime_root, workspace) / "project.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if field.startswith("remove:"):
        metadata.pop(field.removeprefix("remove:"))
    else:
        metadata[field] = value
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(IntegrityError) as listed:
        router.list_projects("auth:alice")
    with pytest.raises(IntegrityError) as opened:
        router.open_project("auth:alice", workspace.project_id)

    assert listed.value.code == opened.value.code == expected_code


def test_list_and_open_normalize_broken_project_json_to_one_metadata_error(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("auth:alice", "项目")
    metadata_path = _project_dir(runtime_root, workspace) / "project.json"
    metadata_path.write_text("{", encoding="utf-8")

    with pytest.raises(IntegrityError) as listed:
        router.list_projects("auth:alice")
    with pytest.raises(IntegrityError) as opened:
        router.open_project("auth:alice", workspace.project_id)

    assert listed.value.code == opened.value.code == "PROJECT_METADATA_INVALID"


def test_list_and_open_normalize_invalid_project_metadata_utf8(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("auth:alice", "项目")
    metadata_path = _project_dir(runtime_root, workspace) / "project.json"
    metadata_path.write_bytes(b"\xff")

    with pytest.raises(IntegrityError) as listed:
        router.list_projects("auth:alice")
    with pytest.raises(IntegrityError) as opened:
        router.open_project("auth:alice", workspace.project_id)

    assert listed.value.code == opened.value.code == "PROJECT_METADATA_INVALID"


def test_list_omits_project_missing_metadata_without_repairing_it(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("auth:alice", "项目")
    metadata_path = _project_dir(runtime_root, workspace) / "project.json"
    metadata_path.unlink()

    assert router.list_projects("auth:alice") == []
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("auth:alice", workspace.project_id)
    assert not metadata_path.exists()


@pytest.mark.parametrize("attribute", ["author_id", "project_id", "_backend"])
def test_author_workspace_public_binding_cannot_be_reassigned(
    tmp_path: Path,
    attribute: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "auth:alice",
        "项目",
    )

    with pytest.raises(
        AuthenticationError,
        match="AUTHOR_WORKSPACE_BINDING_IMMUTABLE",
    ):
        setattr(workspace, attribute, "changed")

    assert workspace.read("state") is None


def test_author_workspace_exposes_no_backend_router_or_runtime_root(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("auth:alice", "甲")
    attributes = set(dir(alice))

    assert "_backend" not in attributes
    assert "_bound" not in attributes
    assert "runtime_root" not in attributes
    assert "router" not in attributes
    assert vars(alice) == {}
    assert alice.author_id.startswith("a_")
    assert alice.project_id.startswith("p_")


def test_unissued_author_workspace_cannot_read_or_write(
    tmp_path: Path,
) -> None:
    issued = WorkspaceRouter(tmp_path / "runtime").create_project(
        "auth:bob",
        "项目",
    )
    forged = object.__new__(AuthorWorkspace)

    with pytest.raises(AuthenticationError, match="AUTHOR_WORKSPACE_ROUTER_REQUIRED"):
        AuthorWorkspace()
    with pytest.raises(AuthenticationError, match="AUTHOR_WORKSPACE_BINDING_INVALID"):
        forged.read("state")

    assert issued.read("state") is None


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy, pickle.dumps])
def test_author_workspace_cannot_be_copied_or_serialized(
    tmp_path: Path,
    copier,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "auth:alice",
        "项目",
    )

    with pytest.raises(
        AuthenticationError,
        match="AUTHOR_WORKSPACE_SERIALIZATION_FORBIDDEN",
    ):
        copier(workspace)


@pytest.mark.parametrize(
    "logical_key",
    ["../state", "/tmp/state", "state/child", "state\\child", "..", "unknown"],
)
def test_logical_key_rejects_paths_and_non_whitelisted_names(
    tmp_path: Path,
    logical_key: str,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )

    with pytest.raises(InvalidLogicalKeyError, match="LOGICAL_KEY_NOT_ALLOWED"):
        workspace.read(logical_key)
    with pytest.raises(InvalidLogicalKeyError, match="LOGICAL_KEY_NOT_ALLOWED"):
        workspace.commit(
            "op-invalid-key",
            {logical_key: {"value": 1}},
            {logical_key: 0},
        )


def test_multi_object_commit_read_sha_and_operation_idempotency(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    mutations = {
        "state": {"phase": "draft"},
        "plan": {"cards": ["card-01"]},
    }

    receipt = workspace.commit(
        "op-initial",
        mutations,
        {"state": 0, "plan": None},
    )
    assert receipt["status"] == "COMMITTED"
    assert receipt["versions"] == {"plan": 1, "state": 1}
    assert receipt["replayed"] is False
    assert workspace.read("state") == {
        "logical_key": "state",
        "version": 1,
        "sha256": receipt["payload_sha256"]["state"],
        "payload": {"phase": "draft"},
    }
    assert workspace.read("plan")["payload"] == {"cards": ["card-01"]}

    replay = workspace.commit(
        "op-initial",
        mutations,
        {"state": 0, "plan": None},
    )
    assert replay["generation_id"] == receipt["generation_id"]
    assert replay["replayed"] is True

    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        workspace.commit(
            "op-initial",
            {"state": {"phase": "other"}},
            {"state": 1},
        )


def test_expected_version_and_sha_are_both_compared(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    workspace.commit("op-1", {"state": {"n": 1}}, {"state": 0})
    current = workspace.read("state")

    with pytest.raises(VersionConflictError, match="SHA_CONFLICT"):
        workspace.commit(
            "op-bad-sha",
            {"state": {"n": 2}},
            {"state": {"version": 1, "sha256": "0" * 64}},
        )

    receipt = workspace.commit(
        "op-2",
        {"state": {"n": 2}},
        {"state": {"version": 1, "sha256": current["sha256"]}},
    )
    assert receipt["versions"]["state"] == 2


def test_guarded_commit_checks_source_without_rewriting_it(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    workspace.commit("op-draft", {"draft": {"text": "初稿"}}, {"draft": 0})
    draft = workspace.read("draft")

    receipt = workspace.commit_guarded(
        "op-derived-state",
        {"state": {"source": "draft-v1"}},
        {"state": 0},
        {"draft": {"version": draft["version"], "sha256": draft["sha256"]}},
    )

    assert receipt["versions"] == {"state": 1}
    assert workspace.read("draft") == draft
    assert workspace.read("state")["payload"] == {"source": "draft-v1"}


def test_guarded_commit_rejects_stale_guard_without_partial_write(
    tmp_path: Path,
) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    workspace.commit("op-draft-1", {"draft": {"text": "初稿"}}, {"draft": 0})
    stale = workspace.read("draft")
    workspace.commit("op-draft-2", {"draft": {"text": "新稿"}}, {"draft": 1})

    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        workspace.commit_guarded(
            "op-stale-derived-state",
            {"state": {"source": "stale"}},
            {"state": 0},
            {"draft": {"version": stale["version"], "sha256": stale["sha256"]}},
        )

    assert workspace.read("state") is None
    assert workspace.read("draft")["payload"] == {"text": "新稿"}


def test_guarded_commit_rejects_guard_mutation_overlap(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )

    with pytest.raises(
        VersionConflictError,
        match="GUARD_KEY_MUST_NOT_BE_MUTATED",
    ):
        workspace.commit_guarded(
            "op-overlap",
            {"draft": {"text": "初稿"}},
            {"draft": 0},
            {"draft": 0},
        )

    assert workspace.read("draft") is None


def test_recover_after_prepare_exposes_none_of_multi_object_commit(
    tmp_path: Path,
) -> None:
    router = WorkspaceRouter(tmp_path / "runtime")
    workspace = router.create_project("principal-a", "项目")

    def fail_after_prepare(point: str) -> None:
        if point == "after_prepare":
            raise InjectedWorkspaceCrash(point)

    router._set_failure_hook_for_testing(fail_after_prepare)
    with pytest.raises(InjectedWorkspaceCrash, match="after_prepare"):
        workspace.commit(
            "op-crash-before-pointer",
            {"state": {"n": 1}, "plan": {"n": 1}},
            {"state": 0, "plan": 0},
        )

    assert workspace.read("state") is None
    assert workspace.read("plan") is None
    router._set_failure_hook_for_testing(None)
    assert workspace.recover() == {
        "status": "ROLLED_BACK",
        "operation_id": "op-crash-before-pointer",
    }
    assert workspace.read("state") is None
    assert workspace.read("plan") is None


def test_recover_after_pointer_exposes_all_and_finishes_receipt(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("principal-a", "项目")

    def fail_after_pointer(point: str) -> None:
        if point == "after_pointer_swap":
            raise InjectedWorkspaceCrash(point)

    router._set_failure_hook_for_testing(fail_after_pointer)
    with pytest.raises(InjectedWorkspaceCrash, match="after_pointer_swap"):
        workspace.commit(
            "op-crash-after-pointer",
            {"state": {"n": 1}, "plan": {"n": 1}},
            {"state": 0, "plan": 0},
        )

    assert workspace.read("state")["payload"] == {"n": 1}
    assert workspace.read("plan")["payload"] == {"n": 1}
    router._set_failure_hook_for_testing(None)
    recovery = workspace.recover()
    assert recovery["status"] == "COMMIT_COMPLETED"
    assert recovery["operation_id"] == "op-crash-after-pointer"

    restarted = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )
    assert restarted.read("state")["payload"] == {"n": 1}
    assert restarted.read("plan")["payload"] == {"n": 1}


def test_concurrent_commits_allow_one_version_winner(tmp_path: Path) -> None:
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    workspace.commit("op-base", {"state": {"winner": None}}, {"state": 0})
    barrier = Barrier(2)

    def compete(name: str):
        barrier.wait()
        try:
            return workspace.commit(
                f"op-{name}",
                {"state": {"winner": name}},
                {"state": 1},
            )
        except VersionConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, ["a", "b"]))

    receipts = [result for result in results if isinstance(result, dict)]
    conflicts = [
        result for result in results if isinstance(result, VersionConflictError)
    ]
    assert len(receipts) == len(conflicts) == 1
    assert conflicts[0].code == "VERSION_CONFLICT"
    assert workspace.read("state")["version"] == 2
    assert workspace.read("state")["payload"]["winner"] in {"a", "b"}


def test_symlink_leaf_and_ancestor_are_rejected(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("principal-a", "项目")
    workspace.commit("op-state", {"state": {"n": 1}}, {"state": 0})

    outside = tmp_path / "outside.json"
    outside.write_text('{"not":"workspace"}', encoding="utf-8")
    blob = _current_blob(runtime_root, workspace, "state")
    blob.unlink()
    blob.symlink_to(outside)
    with pytest.raises(UnsafePathError, match="SYMLINK_NOT_ALLOWED"):
        workspace.read("state")

    other = WorkspaceRouter(runtime_root).create_project("principal-a", "另一项目")
    other_project_dir = _project_dir(runtime_root, other)
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (other_project_dir / "state").symlink_to(outside_dir, target_is_directory=True)
    with pytest.raises(UnsafePathError, match="SYMLINK_NOT_ALLOWED"):
        other.read("state")

    metadata_project = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "元数据软链"
    )
    metadata_path = _project_dir(runtime_root, metadata_project) / "project.json"
    metadata_path.unlink()
    metadata_path.symlink_to(outside)
    with pytest.raises(UnsafePathError, match="SYMLINK_NOT_ALLOWED"):
        WorkspaceRouter(runtime_root).open_project(
            "principal-a", metadata_project.project_id
        )


def test_immutable_upload_is_author_scoped_content_addressed(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    alice = router.create_project("principal-a", "项目")
    bob = router.create_project("principal-b", "项目")
    payload = b"synthetic-upload-bytes"

    alice_blob = alice.store_immutable(
        "raw_upload", payload, {"file_name": "sample.bin"}
    )
    bob_blob = bob.store_immutable(
        "raw_upload", payload, {"file_name": "sample.bin"}
    )

    assert alice_blob["content_sha256"] == bob_blob["content_sha256"]
    assert alice_blob["blob_id"] != bob_blob["blob_id"]
    alice_path = (
        runtime_root
        / "authors"
        / alice.author_id
        / "immutable/raw_upload/blobs"
        / f"{alice_blob['content_sha256']}.blob"
    )
    bob_path = (
        runtime_root
        / "authors"
        / bob.author_id
        / "immutable/raw_upload/blobs"
        / f"{bob_blob['content_sha256']}.blob"
    )
    assert alice_path != bob_path
    assert alice_path.read_bytes() == bob_path.read_bytes() == payload


def test_referenced_raw_upload_roundtrip_is_read_only_and_project_bound(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("principal-a", "项目")
    other_project = router.create_project("principal-a", "另一项目")
    payload = b"synthetic raw upload"
    metadata = {"source_name": "sample.txt", "bytes": len(payload)}
    receipt = workspace.store_immutable("raw_upload", payload, metadata)

    with pytest.raises(
        WorkspaceError,
        match="IMMUTABLE_RECEIPT_NOT_REFERENCED",
    ):
        workspace.read_immutable(receipt)
    with pytest.raises(
        WorkspaceError,
        match="IMMUTABLE_RECEIPT_NOT_REFERENCED",
    ):
        other_project.read_immutable(receipt)

    _reference_raw_upload(workspace, receipt, "op-reference-upload")
    before = _tree_bytes(runtime_root)
    loaded = workspace.read_immutable(receipt)

    assert loaded == {
        "receipt": receipt,
        "metadata": metadata,
        "raw_bytes": payload,
    }
    assert _tree_bytes(runtime_root) == before


def test_raw_upload_reader_rejects_cross_author_other_kind_and_path_impostor(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    router = WorkspaceRouter(runtime_root)
    alice = router.create_project("principal-a", "项目")
    bob = router.create_project("principal-b", "项目")
    bob_receipt = bob.store_immutable("raw_upload", b"bob", {"name": "bob"})
    _reference_raw_upload(bob, bob_receipt, "op-bob-reference")

    with pytest.raises(
        AuthenticationError,
        match="IMMUTABLE_RECEIPT_AUTHOR_MISMATCH",
    ):
        alice.read_immutable(bob_receipt)

    attachment = alice.store_immutable("attachment", b"x", {"name": "x"})
    alice.commit(
        "op-attachment-reference",
        {"input_manifest": {"uploads": [{"immutable_receipt": attachment}]}},
        {"input_manifest": 0},
    )
    with pytest.raises(
        WorkspaceError,
        match="IMMUTABLE_READ_KIND_NOT_ALLOWED",
    ):
        alice.read_immutable(attachment)
    with pytest.raises(WorkspaceError, match="IMMUTABLE_RECEIPT_INVALID"):
        alice.read_immutable(Path("/tmp/not-a-receipt"))
    assert list(inspect.signature(alice.read_immutable).parameters) == ["receipt"]


@pytest.mark.parametrize("target", ["blob", "metadata"])
def test_raw_upload_reader_detects_actual_immutable_corruption_without_writing(
    tmp_path: Path,
    target: str,
) -> None:
    runtime_root = tmp_path / f"runtime-{target}"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "项目"
    )
    receipt = workspace.store_immutable(
        "raw_upload",
        b"original bytes",
        {"source_name": "sample.txt"},
    )
    _reference_raw_upload(workspace, receipt, "op-reference")
    blob_path, metadata_path = _immutable_paths(runtime_root, workspace, receipt)
    damaged_path = blob_path if target == "blob" else metadata_path
    damaged_path.write_bytes(b"tampered")
    before = _tree_bytes(runtime_root)

    expected = (
        "IMMUTABLE_BLOB_INTEGRITY_MISMATCH"
        if target == "blob"
        else "IMMUTABLE_METADATA_SHA_MISMATCH"
    )
    with pytest.raises(IntegrityError, match=expected):
        workspace.read_immutable(receipt)
    assert _tree_bytes(runtime_root) == before


@pytest.mark.parametrize("target", ["blob", "metadata"])
def test_raw_upload_reader_rejects_symlink_without_following(
    tmp_path: Path,
    target: str,
) -> None:
    runtime_root = tmp_path / f"runtime-symlink-{target}"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "项目"
    )
    receipt = workspace.store_immutable(
        "raw_upload",
        b"original bytes",
        {"source_name": "sample.txt"},
    )
    _reference_raw_upload(workspace, receipt, "op-reference")
    blob_path, metadata_path = _immutable_paths(runtime_root, workspace, receipt)
    target_path = blob_path if target == "blob" else metadata_path
    outside = tmp_path / f"outside-{target}"
    outside.write_bytes(b"outside")
    target_path.unlink()
    target_path.symlink_to(outside)

    with pytest.raises(UnsafePathError, match="SYMLINK_NOT_ALLOWED"):
        workspace.read_immutable(receipt)


def test_created_directories_and_files_have_private_modes(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = WorkspaceRouter(runtime_root).create_project("principal-a", "项目")
    workspace.commit("op-state", {"state": {"n": 1}}, {"state": 0})
    workspace.store_immutable("raw_upload", b"bytes", {"name": "x.bin"})

    author_root = runtime_root / "authors" / workspace.author_id
    for current_root, directory_names, file_names in os.walk(author_root):
        current = Path(current_root)
        assert stat.S_IMODE(current.stat().st_mode) == 0o700
        for directory_name in directory_names:
            directory = current / directory_name
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        for file_name in file_names:
            file_path = current / file_name
            assert stat.S_IMODE(file_path.stat().st_mode) == 0o600
