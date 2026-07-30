from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


LOCAL_EVIDENCE_REGISTRY_PATH = Path(__file__).with_name("local_evidence_registry.json")
ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "tools", ROOT / "tests"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.historical_test_replay import (  # noqa: E402
    ReplayError,
    historical_nodeids,
    load_registry,
    verify_materialization_receipt,
)


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


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--historical-replay",
        action="store_true",
        default=False,
        help="只在已物化的历史工作副本中回放登记的 40 个精确节点。",
    )


def _load_historical_replay_registry() -> dict:
    try:
        return load_registry(ROOT)
    except ReplayError as exc:
        raise pytest.UsageError(f"历史测试回放登记无效：{exc.code}") from exc


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


def _reject_registry_overlap(
    historical: set[str],
    local_evidence_registry: dict,
) -> None:
    historical_files = {Path(nodeid.split("::", 1)[0]).name for nodeid in historical}
    local_nodeids: set[str] = set()
    for group in local_evidence_registry["groups"]:
        local_nodeids.update(group.get("nodeids", []))
        for pattern in group.get("test_file_globs", []):
            if any(Path(name).match(pattern) for name in historical_files):
                raise pytest.UsageError(
                    "历史回放与本地证据文件规则重叠，必须先拆清消费者"
                )
    overlap = historical & local_nodeids
    if overlap:
        raise pytest.UsageError(f"历史回放与本地证据节点重叠：{sorted(overlap)[0]}")


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    registry = _load_historical_replay_registry()
    local_evidence_registry = _load_local_evidence_registry()
    registered = set(historical_nodeids(registry))
    _reject_registry_overlap(registered, local_evidence_registry)

    replay_items = [item for item in items if item.nodeid in registered]
    if config.getoption("--historical-replay"):
        collected = {item.nodeid for item in replay_items}
        all_collected = {item.nodeid for item in items}
        if collected != registered or all_collected != registered:
            raise pytest.UsageError("历史回放必须一次只收集登记的 40 个精确节点")
        try:
            verify_materialization_receipt(ROOT)
        except ReplayError as exc:
            raise pytest.UsageError(f"历史回放工作副本无效：{exc.code}") from exc
        for item in replay_items:
            item.add_marker(pytest.mark.historical_replay)
    else:
        for item in replay_items:
            item.add_marker(pytest.mark.historical_replay)
        if replay_items:
            replay_ids = {id(item) for item in replay_items}
            items[:] = [item for item in items if id(item) not in replay_ids]
            config.hook.pytest_deselected(items=replay_items)

    run_without_local_evidence_guard = (
        os.environ.get("NOVEL_RUN_LOCAL_EVIDENCE_TESTS") == "1"
    )
    for group in local_evidence_registry["groups"]:
        missing = [
            path for path in group["required_paths"] if not (ROOT / path).is_file()
        ]
        if not missing or run_without_local_evidence_guard:
            continue
        patterns = tuple(str(pattern) for pattern in group.get("test_file_globs", []))
        nodeids = set(str(nodeid) for nodeid in group.get("nodeids", []))
        for item in items:
            test_name = Path(str(item.fspath)).name
            file_matches = any(Path(test_name).match(pattern) for pattern in patterns)
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
