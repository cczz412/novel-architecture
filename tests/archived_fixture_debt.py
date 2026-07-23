from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path(__file__).with_name("test_debt_registry.json")


def xfail_if_registered_fixture_missing(nodeid: str) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    for group in registry["groups"]:
        if nodeid not in group["nodeids"]:
            continue
        if group.get("application", "collection") != "runtime_guard":
            raise AssertionError(f"节点不是运行期挂账：{nodeid}")
        due = date.fromisoformat(group["due_date"])
        if date.today() > due:
            pytest.fail(
                f"历史夹具挂账已过期：负责人={group['owner']}；到期日={due.isoformat()}",
                pytrace=False,
            )
        missing = [path for path in group["required_paths"] if not (ROOT / path).is_file()]
        if missing:
            pytest.xfail(
                f"{group['reason']} 缺失={','.join(missing)}；"
                f"负责人={group['owner']}；到期日={group['due_date']}"
            )
        return
    raise AssertionError(f"运行期挂账节点未登记：{nodeid}")
