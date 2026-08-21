from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import ledger_directory_tool, ledger_directory_workspace, workspace
finally:
    sys.path.pop(0)


FIXED_NAMES = list(ledger_directory_tool.FIXED_LEDGER_NAMES)
REUSABLE = {"章节账", "事实账", "规划账"}
SCATTERED = {"人物账", "地点账", "世界规则账", "长线账"}
UNAVAILABLE = set(FIXED_NAMES) - REUSABLE


def _capability_snapshot(*, snapshot_id: str = "capabilities-r01") -> dict:
    ledgers = []
    for name in reversed(FIXED_NAMES):
        if name in REUSABLE:
            capability = "REUSABLE_STORAGE_AVAILABLE"
            content = "EMPTY" if name == "规划账" else "PRESENT"
            read_route = f"读取{name}的当前适配器"
            write_route = f"保存{name}的当前适配器"
        elif name in SCATTERED:
            capability = "SCATTERED_MATERIALS_ONLY"
            content = "UNKNOWN"
            read_route = f"只查看{name}散落线索"
            write_route = None
        else:
            capability = "NO_FIXED_REGISTRATION"
            content = "UNKNOWN"
            read_route = None
            write_route = None
        ledgers.append(
            {
                "ledger_name": name,
                "capability_status": capability,
                "content_status": content,
                "read_route_advisory": read_route,
                "write_route_advisory": write_route,
            }
        )
    return {"capability_snapshot_id": snapshot_id, "ledgers": ledgers}


def _tree_bytes(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _new_workspace(tmp_path: Path, principal: str = "principal-a"):
    runtime_root = tmp_path / "runtime"
    handle = workspace.WorkspaceRouter(runtime_root).create_project(principal, "项目")
    return runtime_root, handle


def _registration_payload() -> dict:
    return {
        "schema": ledger_directory_workspace.REGISTRATION_SCHEMA,
        "directory_identity": ledger_directory_workspace.REGISTRATION_IDENTITY,
        "ledger_names": FIXED_NAMES,
    }


def test_explicit_initialization_persists_only_fixed_registration(tmp_path: Path) -> None:
    _runtime_root, handle = _new_workspace(tmp_path)

    receipt = ledger_directory_workspace.initialize_directory(
        handle,
        "op-directory-initialize",
    )
    state = handle.read("ledger_directory")

    assert receipt["status"] == "COMMITTED"
    assert receipt["version"] == 1
    assert receipt["sha256"] == state["sha256"]
    assert state["payload"] == _registration_payload()
    persisted_text = json.dumps(state["payload"], ensure_ascii=False)
    for forbidden in (
        "capability_status",
        "content_status",
        "capability_snapshot_id",
        "read_route_advisory",
        "write_route_advisory",
        "REUSABLE_STORAGE_AVAILABLE",
        "SCATTERED_MATERIALS_ONLY",
        "NO_FIXED_REGISTRATION",
    ):
        assert forbidden not in persisted_text

    populated = [
        key for key in workspace.LOGICAL_KEY_FILES if handle.read(key) is not None
    ]
    assert populated == ["ledger_directory"]


def test_restart_reads_same_registration_and_current_overlay_without_writing(
    tmp_path: Path,
) -> None:
    runtime_root, handle = _new_workspace(tmp_path)
    receipt = ledger_directory_workspace.initialize_directory(
        handle,
        "op-directory-initialize",
    )
    before = _tree_bytes(runtime_root)

    restarted = workspace.WorkspaceRouter(runtime_root).open_project(
        "principal-a",
        handle.project_id,
    )
    result = ledger_directory_workspace.read_directory(
        restarted,
        _capability_snapshot(),
    )

    assert result["registration"] == {
        "identity": ledger_directory_workspace.REGISTRATION_IDENTITY,
        "version": 1,
        "sha256": receipt["sha256"],
        "ledger_names": FIXED_NAMES,
    }
    assert [
        item["ledger_name"] for item in result["directory_view"]["ledgers"]
    ] == FIXED_NAMES
    assert result["directory_view"]["capability_snapshot_id"] == "capabilities-r01"
    assert _tree_bytes(runtime_root) == before


def test_initialization_is_idempotent_and_conflicts_do_not_overwrite(
    tmp_path: Path,
) -> None:
    _runtime_root, handle = _new_workspace(tmp_path)
    first = ledger_directory_workspace.initialize_directory(handle, "op-directory")
    original = copy.deepcopy(handle.read("ledger_directory"))

    replay = ledger_directory_workspace.initialize_directory(handle, "op-directory")
    assert replay["replayed"] is True
    assert replay["generation_id"] == first["generation_id"]

    changed = {**_registration_payload(), "ledger_names": list(reversed(FIXED_NAMES))}
    with pytest.raises(
        workspace.OperationConflictError,
        match="OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST",
    ):
        handle.commit(
            "op-directory",
            {"ledger_directory": changed},
            {"ledger_directory": 1},
        )
    with pytest.raises(workspace.VersionConflictError, match="VERSION_CONFLICT"):
        ledger_directory_workspace.initialize_directory(
            handle,
            "op-directory-stale",
            expected_version=0,
        )
    assert handle.read("ledger_directory") == original


def test_uninitialized_read_is_stable_and_does_not_create_files(tmp_path: Path) -> None:
    runtime_root, handle = _new_workspace(tmp_path)
    before = _tree_bytes(runtime_root)

    with pytest.raises(
        ledger_directory_workspace.LedgerDirectoryWorkspaceError,
        match="^DIRECTORY_NOT_INITIALIZED$",
    ):
        ledger_directory_workspace.read_directory(handle, _capability_snapshot())

    assert _tree_bytes(runtime_root) == before
    assert handle.read("ledger_directory") is None


def test_seven_unavailable_ledgers_are_registered_and_must_remain_unknown(
    tmp_path: Path,
) -> None:
    _runtime_root, handle = _new_workspace(tmp_path)
    ledger_directory_workspace.initialize_directory(handle, "op-directory")

    result = ledger_directory_workspace.read_directory(
        handle,
        _capability_snapshot(),
    )
    by_name = {
        item["ledger_name"]: item for item in result["directory_view"]["ledgers"]
    }
    assert set(result["registration"]["ledger_names"]) == set(FIXED_NAMES)
    assert all(by_name[name]["content_status"] == "UNKNOWN" for name in UNAVAILABLE)

    invalid = _capability_snapshot(snapshot_id="invalid-empty")
    next(
        item for item in invalid["ledgers"] if item["ledger_name"] == "人物账"
    )["content_status"] = "EMPTY"
    with pytest.raises(
        ledger_directory_workspace.LedgerDirectoryWorkspaceError,
        match="^UNAVAILABLE_LEDGER_CONTENT_MUST_BE_UNKNOWN:人物账$",
    ):
        ledger_directory_workspace.read_directory(handle, invalid)


def test_live_snapshot_changes_are_not_written_to_registration(tmp_path: Path) -> None:
    _runtime_root, handle = _new_workspace(tmp_path)
    ledger_directory_workspace.initialize_directory(handle, "op-directory")
    registration = copy.deepcopy(handle.read("ledger_directory"))
    first_snapshot = _capability_snapshot(snapshot_id="capabilities-r01")
    second_snapshot = _capability_snapshot(snapshot_id="capabilities-r02")
    planning = next(
        item for item in second_snapshot["ledgers"] if item["ledger_name"] == "规划账"
    )
    planning["content_status"] = "PRESENT"
    planning["read_route_advisory"] = "新版规划读取入口"

    first = ledger_directory_workspace.read_directory(handle, first_snapshot)
    second = ledger_directory_workspace.read_directory(handle, second_snapshot)

    assert first["directory_view"] != second["directory_view"]
    assert handle.read("ledger_directory") == registration


@pytest.mark.parametrize(
    "bad_names",
    [
        FIXED_NAMES[:-1],
        [*FIXED_NAMES[:-1], FIXED_NAMES[0]],
        list(reversed(FIXED_NAMES)),
    ],
)
def test_bad_persisted_registration_fails_closed_without_writing(
    tmp_path: Path,
    bad_names: list[str],
) -> None:
    runtime_root, handle = _new_workspace(tmp_path)
    bad = {**_registration_payload(), "ledger_names": bad_names}
    handle.commit("op-bad-directory", {"ledger_directory": bad}, {"ledger_directory": 0})
    before = _tree_bytes(runtime_root)

    with pytest.raises(
        ledger_directory_workspace.LedgerDirectoryWorkspaceError,
        match="^DIRECTORY_REGISTRATION_INVALID$",
    ):
        ledger_directory_workspace.read_directory(handle, _capability_snapshot())

    assert _tree_bytes(runtime_root) == before


def test_read_rejects_directory_watermark_change(tmp_path: Path, monkeypatch) -> None:
    _runtime_root, handle = _new_workspace(tmp_path)
    ledger_directory_workspace.initialize_directory(handle, "op-directory")
    original_read = handle.read
    calls = 0

    def racing_read(logical_key: str):
        nonlocal calls
        calls += 1
        if calls == 2:
            handle.commit(
                "op-directory-race",
                {"ledger_directory": _registration_payload()},
                {"ledger_directory": 1},
            )
        return original_read(logical_key)

    monkeypatch.setattr(handle, "read", racing_read)

    with pytest.raises(
        ledger_directory_workspace.LedgerDirectoryWorkspaceError,
        match="^DIRECTORY_CHANGED_DURING_READ$",
    ):
        ledger_directory_workspace.read_directory(handle, _capability_snapshot())


def test_path_forged_handle_and_cross_author_project_are_rejected(
    tmp_path: Path,
) -> None:
    runtime_root, handle = _new_workspace(tmp_path)
    router = workspace.WorkspaceRouter(runtime_root)

    for impostor in (Path("/tmp/project"), object()):
        with pytest.raises(
            ledger_directory_workspace.LedgerDirectoryWorkspaceError,
            match="^AUTHOR_WORKSPACE_HANDLE_REQUIRED$",
        ):
            ledger_directory_workspace.initialize_directory(impostor, "op-directory")
        with pytest.raises(
            ledger_directory_workspace.LedgerDirectoryWorkspaceError,
            match="^AUTHOR_WORKSPACE_HANDLE_REQUIRED$",
        ):
            ledger_directory_workspace.read_directory(
                impostor,
                _capability_snapshot(),
            )

    with pytest.raises(workspace.ProjectNotFoundError, match="PROJECT_NOT_FOUND"):
        router.open_project("principal-b", handle.project_id)


def test_read_returns_deep_copy_and_invalid_snapshot_writes_nothing(
    tmp_path: Path,
) -> None:
    runtime_root, handle = _new_workspace(tmp_path)
    ledger_directory_workspace.initialize_directory(handle, "op-directory")
    before = _tree_bytes(runtime_root)

    result = ledger_directory_workspace.read_directory(
        handle,
        _capability_snapshot(),
    )
    result["registration"]["ledger_names"].clear()
    result["directory_view"]["ledgers"][0]["read_route_advisory"] = "被调用方修改"
    fresh = ledger_directory_workspace.read_directory(
        handle,
        _capability_snapshot(),
    )
    assert fresh["registration"]["ledger_names"] == FIXED_NAMES
    assert fresh["directory_view"]["ledgers"][0]["read_route_advisory"] != "被调用方修改"

    invalid = _capability_snapshot()
    invalid["ledgers"].pop()
    with pytest.raises(
        ledger_directory_workspace.LedgerDirectoryWorkspaceError,
        match="^CAPABILITY_SNAPSHOT_INVALID:LEDGER_COUNT_INVALID:9$",
    ):
        ledger_directory_workspace.read_directory(handle, invalid)
    assert _tree_bytes(runtime_root) == before
