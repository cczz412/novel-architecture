from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest


REGISTRY_PATH = Path(__file__).with_name("test_debt_registry.json")
ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "tools", ROOT / "tests"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


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


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    registry = _load_registry()
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
