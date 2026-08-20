from __future__ import annotations

import copy
import hashlib
import io
import inspect
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
LOCAL_FILESYSTEM_ONLY = True

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ingest, ingest_workspace, input_router, store
    from mvp.upload_source import UploadSource
    from mvp.workspace import (
        OperationConflictError,
        ProjectNotFoundError,
        VersionConflictError,
        WorkspaceRouter,
    )
finally:
    sys.path.pop(0)


def _declaration(length: int) -> list[dict]:
    return [
        {
            "start": 0,
            "end": length,
            "role": "CHAPTER",
            "state": "CONFIRMED",
            "basis": {"type": "USER_DECLARATION", "reference": "WORKSPACE-TEST"},
            "actor": {"type": "USER", "reference": "AUTHOR"},
            "reason": "作者明确声明为章节",
        }
    ]


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _m1_result(
    tmp_path: Path,
    monkeypatch,
    suffix: str = "one",
    text: str = "第一章 雨夜\n沈砚推门。\n",
) -> tuple[dict, bytes]:
    data_root = tmp_path / f"legacy-adapter-{suffix}"
    monkeypatch.setattr(store, "DATA_ROOT", data_root)
    project = f"m1-{suffix}"
    store.init_project(project)
    raw = text.encode()
    result = ingest.ingest_uploads(
        project,
        [
            UploadSource(
                f"chapter-{suffix}.txt",
                raw,
                declarations=_declaration(len(text)),
            )
        ],
    )
    return result, raw


def _m1_multi_result(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "legacy-adapter-multi")
    store.init_project("m1-multi")
    uploads = [
        UploadSource("one.txt", "第一章\n雨落下来。\n".encode()),
        UploadSource(
            "two.md",
            "第二章\n门被推开。\n".encode(),
            encoding_hint="utf-8",
        ),
    ]
    result = ingest.ingest_uploads(
        "m1-multi",
        uploads,
        material_role="CHAPTER",
    )
    return result, uploads


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _persisted_workspace(
    tmp_path: Path,
    monkeypatch,
    suffix: str,
):
    result, raw = _m1_result(tmp_path, monkeypatch, suffix)
    runtime_root = tmp_path / f"runtime-{suffix}"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "项目"
    )
    ingest_workspace.persist_m1_result(
        workspace,
        f"op-{suffix}",
        result,
        {"input_manifest": 0, "module_state": 0},
    )
    return workspace, runtime_root, raw


def test_persist_restart_readback_and_immutable_sha(
    tmp_path: Path, monkeypatch
) -> None:
    assert LOCAL_FILESYSTEM_ONLY is True
    result, raw = _m1_result(tmp_path, monkeypatch)
    runtime_root = tmp_path / "workspace-runtime"
    router = WorkspaceRouter(runtime_root)
    workspace = router.create_project("principal-a", "小说项目")

    receipt = ingest_workspace.persist_m1_result(
        workspace,
        "op-m1-persist-01",
        result,
        {"input_manifest": 0, "module_state": 0},
    )

    restarted = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )
    manifest = restarted.read("input_manifest")
    module_state = restarted.read("module_state")
    before_read = _tree_bytes(runtime_root)
    safe_state = ingest_workspace.read_persisted_m1_state(restarted)
    after_read = _tree_bytes(runtime_root)
    upload = manifest["payload"]["uploads"][0]
    assert receipt["status"] == "COMMITTED" and receipt["replayed"] is False
    assert manifest["version"] == module_state["version"] == 1
    assert module_state["payload"]["count"] == 1
    assert upload["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert upload["immutable_receipt"]["content_sha256"] == upload["source_sha256"]
    assert upload["immutable_receipt"]["size"] == len(raw)
    assert "raw_bytes" not in module_state["payload"]["upload_objects"][0]
    assert all(
        "original_bytes_base64" not in source
        for source in module_state["payload"]["sources"]
    )
    assert safe_state["status"] == "READY"
    safe_upload = copy.deepcopy(manifest["payload"]["uploads"][0])
    safe_upload.pop("declarations")
    assert safe_state["uploads"] == [safe_upload]
    assert safe_state["summary"] == {
        "count": 1,
        "total_chars": len(raw.decode()),
        "warning_count": 0,
        "terminal_source_count": 1,
    }
    assert before_read == after_read
    serialized = repr(safe_state)
    assert "raw_bytes" not in serialized
    assert "original_bytes_base64" not in serialized
    assert "declarations" not in serialized
    assert "作者明确声明为章节" not in serialized
    assert raw.decode() not in serialized


def test_same_operation_replays_and_different_request_conflicts(
    tmp_path: Path, monkeypatch
) -> None:
    result, _ = _m1_result(tmp_path, monkeypatch, "idem")
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    expected = {"input_manifest": 0, "module_state": 0}

    first = ingest_workspace.persist_m1_result(
        workspace, "op-m1-idem", result, expected
    )
    replay = ingest_workspace.persist_m1_result(
        workspace, "op-m1-idem", result, expected
    )
    assert replay["generation_id"] == first["generation_id"]
    assert replay["replayed"] is True

    changed = copy.deepcopy(result)
    changed["warnings"] = ["different request"]
    with pytest.raises(
        OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        ingest_workspace.persist_m1_result(
            workspace, "op-m1-idem", changed, expected
        )


def test_version_conflict_leaves_both_visible_keys_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    result, _ = _m1_result(tmp_path, monkeypatch, "version")
    workspace = WorkspaceRouter(tmp_path / "runtime").create_project(
        "principal-a", "项目"
    )
    ingest_workspace.persist_m1_result(
        workspace,
        "op-m1-base",
        result,
        {"input_manifest": 0, "module_state": 0},
    )
    before_manifest = workspace.read("input_manifest")
    before_state = workspace.read("module_state")

    changed_result, changed_raw = _m1_result(
        tmp_path,
        monkeypatch,
        "version-new",
        "第一章 清晨\n沈砚离开。\n",
    )
    with pytest.raises(VersionConflictError, match="VERSION_CONFLICT"):
        ingest_workspace.persist_m1_result(
            workspace,
            "op-m1-stale",
            changed_result,
            {"input_manifest": 0, "module_state": 0},
        )

    assert workspace.read("input_manifest") == before_manifest
    assert workspace.read("module_state") == before_state
    assert (
        hashlib.sha256(changed_raw).hexdigest()
        not in {
            item["source_sha256"]
            for item in workspace.read("input_manifest")["payload"]["uploads"]
        }
    )


def test_author_scope_stays_opaque_and_adapter_has_no_path_or_identity_args(
    tmp_path: Path, monkeypatch
) -> None:
    result, _ = _m1_result(tmp_path, monkeypatch, "scope")
    router = WorkspaceRouter(tmp_path / "runtime")
    alice = router.create_project("principal-a", "项目")
    bob = router.create_project("principal-b", "项目")

    alice_receipt = ingest_workspace.persist_m1_result(
        alice,
        "op-alice",
        result,
        {"input_manifest": 0, "module_state": 0},
    )
    bob_receipt = ingest_workspace.persist_m1_result(
        bob,
        "op-bob",
        result,
        {"input_manifest": 0, "module_state": 0},
    )
    assert (
        alice_receipt["immutable_receipts"][0]["content_sha256"]
        == bob_receipt["immutable_receipts"][0]["content_sha256"]
    )
    assert (
        alice_receipt["immutable_receipts"][0]["blob_id"]
        != bob_receipt["immutable_receipts"][0]["blob_id"]
    )
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("principal-a", bob.project_id)

    assert list(inspect.signature(ingest_workspace.persist_m1_result).parameters) == [
        "workspace",
        "operation_id",
        "m1_result",
        "expected_versions",
    ]


def test_empty_read_is_stable_and_has_zero_filesystem_side_effects(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime-empty"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "空项目"
    )
    before = _tree_bytes(runtime_root)

    first = ingest_workspace.read_persisted_m1_state(workspace)
    second = ingest_workspace.read_persisted_m1_state(workspace)

    assert first == second == {
        "status": "EMPTY",
        "state_identity": None,
        "uploads": [],
        "summary": None,
    }
    assert _tree_bytes(runtime_root) == before
    assert ingest_workspace.load_persisted_upload_sources(workspace) == []
    assert _tree_bytes(runtime_root) == before


def test_missing_key_and_version_divergence_fail_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing = WorkspaceRouter(tmp_path / "runtime-missing").create_project(
        "principal-a", "项目"
    )
    missing.commit(
        "op-manifest-only",
        {"input_manifest": {"uploads": []}},
        {"input_manifest": 0},
    )
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_VISIBLE_STATE_INCOMPLETE",
    ):
        ingest_workspace.read_persisted_m1_state(missing)
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_VISIBLE_STATE_INCOMPLETE",
    ):
        ingest_workspace.load_persisted_upload_sources(missing)

    diverged, runtime_root, _ = _persisted_workspace(
        tmp_path, monkeypatch, "diverged"
    )
    manifest_payload = diverged.read("input_manifest")["payload"]
    diverged.commit(
        "op-manifest-v2",
        {"input_manifest": manifest_payload},
        {"input_manifest": 1},
    )
    before = _tree_bytes(runtime_root)
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_VISIBLE_STATE_VERSION_DIVERGED",
    ):
        ingest_workspace.read_persisted_m1_state(diverged)
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_VISIBLE_STATE_VERSION_DIVERGED",
    ):
        ingest_workspace.load_persisted_upload_sources(diverged)
    assert _tree_bytes(runtime_root) == before


@pytest.mark.parametrize(
    "tamper",
    ["list_divergence", "receipt_shape", "sha", "size", "object_type"],
)
def test_malformed_visible_upload_state_is_rejected_without_read_side_effects(
    tmp_path: Path,
    monkeypatch,
    tamper: str,
) -> None:
    workspace, runtime_root, _ = _persisted_workspace(
        tmp_path, monkeypatch, f"tamper-{tamper}"
    )
    manifest = copy.deepcopy(workspace.read("input_manifest")["payload"])
    state = copy.deepcopy(workspace.read("module_state")["payload"])
    if tamper == "list_divergence":
        state["upload_objects"] = []
    else:
        records = [
            manifest["uploads"][0],
            state["upload_objects"][0],
            state["format_receipt"]["upload_objects"][0],
        ]
        for record in records:
            receipt = record["immutable_receipt"]
            if tamper == "receipt_shape":
                receipt.pop("metadata_sha256")
            elif tamper == "sha":
                receipt["content_sha256"] = "0" * 64
            elif tamper == "size":
                receipt["size"] += 1
            else:
                receipt["kind"] = "attachment"
    workspace.commit(
        f"op-visible-tamper-{tamper}",
        {"input_manifest": manifest, "module_state": state},
        {"input_manifest": 1, "module_state": 1},
    )
    before = _tree_bytes(runtime_root)

    with pytest.raises(ingest_workspace.IngestWorkspaceError):
        ingest_workspace.read_persisted_m1_state(workspace)
    with pytest.raises(ingest_workspace.IngestWorkspaceError):
        ingest_workspace.load_persisted_upload_sources(workspace)
    assert _tree_bytes(runtime_root) == before


def test_read_watermark_change_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace, _, _ = _persisted_workspace(tmp_path, monkeypatch, "race")
    manifest = copy.deepcopy(workspace.read("input_manifest")["payload"])
    state = copy.deepcopy(workspace.read("module_state")["payload"])
    real_read = workspace.read
    calls = 0

    def racing_read(logical_key: str):
        nonlocal calls
        calls += 1
        result = real_read(logical_key)
        if calls == 2:
            workspace.commit(
                "op-external-race",
                {"input_manifest": manifest, "module_state": state},
                {"input_manifest": 1, "module_state": 1},
            )
        return result

    monkeypatch.setattr(workspace, "read", racing_read)
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_READ_WATERMARK_CHANGED",
    ):
        ingest_workspace.read_persisted_m1_state(workspace)


def test_safe_result_is_deep_copy_and_identity_stays_bound_to_handle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace, _, _ = _persisted_workspace(tmp_path, monkeypatch, "copy")
    first = ingest_workspace.read_persisted_m1_state(workspace)
    first["uploads"][0]["source_name"] = "changed.txt"
    first["summary"]["count"] = 999
    second = ingest_workspace.read_persisted_m1_state(workspace)
    assert second["uploads"][0]["source_name"] != "changed.txt"
    assert second["summary"]["count"] != 999

    router = WorkspaceRouter(tmp_path / "runtime-other")
    alice = router.create_project("principal-a", "项目")
    bob = router.create_project("principal-b", "项目")
    with pytest.raises(ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("principal-a", bob.project_id)
    assert ingest_workspace.read_persisted_m1_state(alice)["status"] == "EMPTY"

    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        ingest_workspace.read_persisted_m1_state(Path("/tmp/not-a-workspace"))
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="AUTHOR_WORKSPACE_HANDLE_REQUIRED",
    ):
        ingest_workspace.load_persisted_upload_sources(
            Path("/tmp/not-a-workspace")
        )
    assert list(
        inspect.signature(ingest_workspace.read_persisted_m1_state).parameters
    ) == ["workspace"]


def test_two_uploads_restart_rehydrate_and_route_identically(
    tmp_path: Path,
    monkeypatch,
) -> None:
    result, original_uploads = _m1_multi_result(tmp_path, monkeypatch)
    runtime_root = tmp_path / "runtime-rehydrate"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "项目"
    )
    ingest_workspace.persist_m1_result(
        workspace,
        "op-persist-multi",
        result,
        {"input_manifest": 0, "module_state": 0},
    )
    restarted = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )
    before = _tree_bytes(runtime_root)

    loaded = ingest_workspace.load_persisted_upload_sources(restarted)

    assert len(loaded) == 2
    for actual, expected in zip(loaded, original_uploads, strict=True):
        assert actual.source_name == expected.source_name
        assert actual.raw_bytes == expected.raw_bytes
        assert actual.sha256 == expected.sha256
        assert actual.encoding_hint == expected.encoding_hint
    assert input_router.collect_uploads(loaded) == input_router.collect_uploads(
        original_uploads
    )
    assert _tree_bytes(runtime_root) == before


def test_descriptor_metadata_must_match_current_manifest_entry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace, runtime_root, raw = _persisted_workspace(
        tmp_path, monkeypatch, "metadata-mismatch"
    )
    manifest = copy.deepcopy(workspace.read("input_manifest")["payload"])
    state = copy.deepcopy(workspace.read("module_state")["payload"])
    original = manifest["uploads"][0]
    wrong_declarations = copy.deepcopy(original["declarations"])
    wrong_declarations[0]["role"] = "REFERENCE"
    wrong_receipt = workspace.store_immutable(
        "raw_upload",
        raw,
        {
            "source_name": original["source_name"],
            "source_sha256": original["source_sha256"],
            "bytes": original["bytes"],
            "declarations": wrong_declarations,
            "encoding_hint": original["encoding_hint"],
            "cloud_swap_point": original["cloud_swap_point"],
        },
    )
    manifest["uploads"][0]["immutable_receipt"] = wrong_receipt
    state["upload_objects"][0]["immutable_receipt"] = copy.deepcopy(
        wrong_receipt
    )
    state["format_receipt"]["upload_objects"][0][
        "immutable_receipt"
    ] = copy.deepcopy(wrong_receipt)
    workspace.commit(
        "op-wrong-descriptor-metadata",
        {"input_manifest": manifest, "module_state": state},
        {"input_manifest": 1, "module_state": 1},
    )
    before = _tree_bytes(runtime_root)

    assert ingest_workspace.read_persisted_m1_state(workspace)["status"] == "READY"
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_IMMUTABLE_METADATA_MISMATCH",
    ):
        ingest_workspace.load_persisted_upload_sources(workspace)
    assert _tree_bytes(runtime_root) == before


def test_list_declarations_survive_restart_and_repeat_same_chapter_handling(
    tmp_path: Path,
    monkeypatch,
) -> None:
    result, raw = _m1_result(tmp_path, monkeypatch, "list-declarations")
    runtime_root = tmp_path / "runtime-list-declarations"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "声明项目"
    )
    ingest_workspace.persist_m1_result(
        workspace,
        "op-list-declarations",
        result,
        {"input_manifest": 0, "module_state": 0},
    )
    restarted = WorkspaceRouter(runtime_root).open_project(
        "principal-a", workspace.project_id
    )
    before = _tree_bytes(runtime_root)

    loaded = ingest_workspace.load_persisted_upload_sources(restarted)

    expected_declarations = _declaration(len(raw.decode()))
    assert len(loaded) == 1
    assert loaded[0].raw_bytes == raw
    assert loaded[0].declarations == expected_declarations
    store.init_project("m1-rehydrated-list")
    repeated = ingest.ingest_uploads("m1-rehydrated-list", loaded)
    assert repeated["chapters"] == result["chapters"]
    assert repeated["material_units"][0]["identity_revisions"][-1]["role"] == (
        "CHAPTER"
    )
    assert _tree_bytes(runtime_root) == before

    loaded[0].declarations[0]["role"] = "REFERENCE"
    loaded_again = ingest_workspace.load_persisted_upload_sources(restarted)
    assert loaded_again[0].declarations == expected_declarations


def test_zip_dict_declarations_survive_restart_without_terminal_inference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(store, "DATA_ROOT", tmp_path / "legacy-zip-declarations")
    store.init_project("m1-zip-declarations")
    first = "第一章\n雨落下来。\n"
    second = "第二章\n门被推开。\n"
    raw = _zip({"one.txt": first.encode(), "two.txt": second.encode()})
    declarations = {
        "book.zip/one.txt": _declaration(len(first)),
        "book.zip/two.txt": _declaration(len(second)),
    }
    result = ingest.ingest_uploads(
        "m1-zip-declarations",
        [UploadSource("book.zip", raw, declarations=declarations)],
    )
    runtime_root = tmp_path / "runtime-zip-declarations"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "ZIP 声明项目"
    )
    ingest_workspace.persist_m1_result(
        workspace,
        "op-zip-declarations",
        result,
        {"input_manifest": 0, "module_state": 0},
    )

    loaded = ingest_workspace.load_persisted_upload_sources(
        WorkspaceRouter(runtime_root).open_project(
            "principal-a", workspace.project_id
        )
    )

    assert len(loaded) == 1
    assert loaded[0].raw_bytes == raw
    assert loaded[0].declarations == declarations
    assert loaded[0].caller_record()["declarations"] == declarations


def test_none_and_legacy_missing_declarations_are_persisted_as_explicit_none(
    tmp_path: Path,
    monkeypatch,
) -> None:
    result, _ = _m1_multi_result(tmp_path, monkeypatch)
    for record in result["upload_objects"]:
        record.pop("declarations", None)
    for record in result["format_receipt"]["upload_objects"]:
        record.pop("declarations", None)
    runtime_root = tmp_path / "runtime-legacy-none"
    workspace = WorkspaceRouter(runtime_root).create_project(
        "principal-a", "旧对象兼容"
    )

    ingest_workspace.persist_m1_result(
        workspace,
        "op-legacy-none",
        result,
        {"input_manifest": 0, "module_state": 0},
    )
    manifest_uploads = workspace.read("input_manifest")["payload"]["uploads"]
    loaded = ingest_workspace.load_persisted_upload_sources(workspace)

    assert [record["declarations"] for record in manifest_uploads] == [None, None]
    assert [source.declarations for source in loaded] == [None, None]


@pytest.mark.parametrize(
    "target",
    ["input_manifest", "module_upload_objects", "format_receipt"],
)
def test_declarations_drift_across_visible_tables_fails_before_return(
    tmp_path: Path,
    monkeypatch,
    target: str,
) -> None:
    workspace, runtime_root, _ = _persisted_workspace(
        tmp_path, monkeypatch, f"declaration-drift-{target}"
    )
    manifest = copy.deepcopy(workspace.read("input_manifest")["payload"])
    state = copy.deepcopy(workspace.read("module_state")["payload"])
    if target == "input_manifest":
        declaration = manifest["uploads"][0]["declarations"][0]
    elif target == "module_upload_objects":
        declaration = state["upload_objects"][0]["declarations"][0]
    else:
        declaration = state["format_receipt"]["upload_objects"][0][
            "declarations"
        ][0]
    declaration["role"] = "REFERENCE"
    workspace.commit(
        f"op-visible-declaration-drift-{target}",
        {"input_manifest": manifest, "module_state": state},
        {"input_manifest": 1, "module_state": 1},
    )
    before = _tree_bytes(runtime_root)

    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_PERSISTED_UPLOAD_LISTS_DIVERGED",
    ):
        ingest_workspace.read_persisted_m1_state(workspace)
    with pytest.raises(
        ingest_workspace.IngestWorkspaceError,
        match="M1_PERSISTED_UPLOAD_LISTS_DIVERGED",
    ):
        ingest_workspace.load_persisted_upload_sources(workspace)

    assert _tree_bytes(runtime_root) == before


def test_load_signature_accepts_only_bound_workspace() -> None:
    assert list(
        inspect.signature(
            ingest_workspace.load_persisted_upload_sources
        ).parameters
    ) == ["workspace"]
