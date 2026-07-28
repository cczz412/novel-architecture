from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest


REGISTRY_PATH = Path(__file__).with_name("test_debt_registry.json")
LOCAL_EVIDENCE_REGISTRY_PATH = Path(__file__).with_name(
    "local_evidence_registry.json"
)
ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "tools", ROOT / "tests"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


@pytest.fixture(scope="session", autouse=True)
def _ensure_ignored_test_workdirs() -> None:
    """干净克隆不带空 TEMP；测试会话按需建目录，能空则在结束时收回。"""

    temporary_root = ROOT / "TEMP"
    created_here = not temporary_root.exists()
    temporary_root.mkdir(parents=True, exist_ok=True)
    yield
    if created_here:
        try:
            temporary_root.rmdir()
        except OSError:
            pass


def _load_registry() -> dict:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != "pytest-archived-fixture-debt-v2":
        raise pytest.UsageError("旧测试挂账登记版本不受支持")
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        raise pytest.UsageError("旧测试挂账必须有非空分组")
    seen: set[str] = set()
    for group in groups:
        nodeids = group.get("nodeids")
        required_paths = group.get("required_paths")
        if not isinstance(nodeids, list) or not nodeids:
            raise pytest.UsageError("旧测试挂账分组必须有精确节点")
        if not isinstance(required_paths, list) or not required_paths:
            raise pytest.UsageError("旧测试挂账分组必须写清缺失夹具路径")
        if not str(group.get("owner") or "").strip():
            raise pytest.UsageError("旧测试挂账分组必须写负责人")
        if group.get("application", "collection") not in {"collection", "runtime_guard"}:
            raise pytest.UsageError("旧测试挂账应用层只允许collection或runtime_guard")
        due = date.fromisoformat(str(group.get("due_date") or ""))
        if date.today() > due:
            raise pytest.UsageError(
                f"旧测试挂账已过期：分组={group.get('group_id')}，"
                f"负责人={group.get('owner')}，到期日={due.isoformat()}"
            )
        for nodeid in nodeids:
            if nodeid in seen:
                raise pytest.UsageError(f"旧测试挂账节点重复：{nodeid}")
            seen.add(nodeid)
    return data


def _load_local_evidence_registry() -> dict:
    data = json.loads(LOCAL_EVIDENCE_REGISTRY_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != "pytest-local-evidence-v1":
        raise pytest.UsageError("本地证据测试登记版本不受支持")
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        raise pytest.UsageError("本地证据测试登记必须有非空分组")
    seen: set[str] = set()
    seen_nodeids: set[str] = set()
    for group in groups:
        group_id = str(group.get("group_id") or "").strip()
        globs = group.get("test_file_globs", [])
        nodeids = group.get("nodeids", [])
        portable_program_paths = group.get("portable_program_paths", [])
        required_paths = group.get("required_paths")
        if not group_id or group_id in seen:
            raise pytest.UsageError("本地证据测试分组 ID 缺失或重复")
        seen.add(group_id)
        if not isinstance(globs, list) or not isinstance(nodeids, list):
            raise pytest.UsageError("本地证据测试规则必须是列表")
        if not globs and not nodeids:
            raise pytest.UsageError("本地证据测试分组必须写文件规则或精确节点")
        for nodeid in nodeids:
            if not isinstance(nodeid, str) or not nodeid.strip():
                raise pytest.UsageError("本地证据测试精确节点不能为空")
            if nodeid in seen_nodeids:
                raise pytest.UsageError(f"本地证据测试节点重复：{nodeid}")
            seen_nodeids.add(nodeid)
        if not isinstance(portable_program_paths, list) or any(
            not isinstance(path, str) or not path.strip()
            for path in portable_program_paths
        ):
            raise pytest.UsageError("可移植程序路径必须是非空字符串列表")
        if not isinstance(required_paths, list) or not required_paths:
            raise pytest.UsageError("本地证据测试分组必须写证据路径")
        if not str(group.get("reason") or "").strip():
            raise pytest.UsageError("本地证据测试分组必须写明隔离原因")
    return data


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    registry = _load_registry()
    local_evidence_registry = _load_local_evidence_registry()
    run_without_fixture_guard = os.environ.get("NOVEL_RUN_ARCHIVED_FIXTURE_TESTS") == "1"
    debt: dict[str, tuple[dict, list[str]]] = {}
    for group in registry["groups"]:
        missing = [path for path in group["required_paths"] if not (ROOT / path).is_file()]
        for nodeid in group["nodeids"]:
            debt[nodeid] = (group, missing)
    for item in items:
        record = debt.get(item.nodeid)
        if record is None:
            continue
        group, missing = record
        item.add_marker(pytest.mark.archived_fixture)
        if group.get("application", "collection") == "runtime_guard":
            continue
        if missing and not run_without_fixture_guard:
            reason = (
                f"{group['reason']} 缺失={','.join(missing)}；"
                f"负责人={group['owner']}；到期日={group['due_date']}"
            )
            item.add_marker(pytest.mark.xfail(reason=reason, strict=True))

    run_without_local_evidence_guard = (
        os.environ.get("NOVEL_RUN_LOCAL_EVIDENCE_TESTS") == "1"
    )
    for group in local_evidence_registry["groups"]:
        missing = [
            path for path in group["required_paths"] if not (ROOT / path).is_file()
        ]
        if not missing or run_without_local_evidence_guard:
            continue
        patterns = tuple(
            str(pattern) for pattern in group.get("test_file_globs", [])
        )
        nodeids = set(str(nodeid) for nodeid in group.get("nodeids", []))
        for item in items:
            test_name = Path(str(item.fspath)).name
            file_matches = any(
                Path(test_name).match(pattern) for pattern in patterns
            )
            if not file_matches and item.nodeid not in nodeids:
                continue
            item.add_marker(pytest.mark.local_evidence)
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"{group['reason']}；缺失={','.join(missing)}；"
                        "需要本地证据时设置 NOVEL_RUN_LOCAL_EVIDENCE_TESTS=1"
                    )
                )
            )
