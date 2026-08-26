from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest


LOCAL_EVIDENCE_REGISTRY_PATH = Path(__file__).with_name("local_evidence_registry.json")
ROOT = Path(__file__).resolve().parents[1]
CI_LANES_PATH = ROOT / "governance/ci_lanes.json"
PYTEST_CI_LANES = ("main-portable", "macos-keychain", "local-evidence")
for import_root in (ROOT, ROOT / "tools", ROOT / "tests"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from isolation import (  # noqa: E402
    apply_isolated_git_environ,
    clear_vendor_api_keys,
    install_network_guard,
)
from tools.historical_test_replay import (  # noqa: E402
    ReplayError,
    historical_nodeids,
    load_registry,
    verify_materialization_receipt,
)


@pytest.fixture(autouse=True)
def _clear_vendor_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_vendor_api_keys(monkeypatch)


@pytest.fixture(autouse=True)
def _isolate_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_isolated_git_environ(monkeypatch)


@pytest.fixture(autouse=True)
def _block_outbound_network(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[bool]:
    ci_lane = request.config.getoption("--ci-lane")
    if request.node.get_closest_marker("allow_network") and ci_lane != "main-portable":
        yield False
        return
    install_network_guard(monkeypatch)
    yield True


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
    parser.addoption(
        "--ci-lane",
        choices=PYTEST_CI_LANES,
        default=None,
        help="只运行登记的 main、macOS Keychain 或本机材料测试线。",
    )
    parser.addoption(
        "--local-evidence-group",
        action="append",
        default=[],
        help="本机材料测试线要运行的登记分组；可重复，未提供时运行全部分组。",
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


def _load_ci_lanes_contract() -> dict:
    data = json.loads(CI_LANES_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != "ci-test-lanes-v1":
        raise pytest.UsageError("CI 测试线合同版本不受支持")
    lanes = data.get("lanes")
    if not isinstance(lanes, dict) or set(lanes) != {
        "main-portable",
        "macos-keychain",
        "local-evidence",
        "historical-replay",
    }:
        raise pytest.UsageError("CI 测试线合同必须精确登记四条测试线")
    for lane_id, lane in lanes.items():
        if not isinstance(lane, dict) or lane.get("lane_id") != lane_id:
            raise pytest.UsageError(f"CI 测试线身份不一致：{lane_id}")
    nodeids = lanes["macos-keychain"].get("pytest_nodeids")
    if (
        not isinstance(nodeids, list)
        or not nodeids
        or len(nodeids) != len(set(nodeids))
        or not all(isinstance(nodeid, str) and nodeid for nodeid in nodeids)
    ):
        raise pytest.UsageError("macOS Keychain 测试线必须登记唯一精确节点")
    return data


def _reject_registry_overlap(
    historical: set[str],
    local_evidence_registry: dict,
    keychain: set[str],
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
    if historical & keychain:
        raise pytest.UsageError("历史回放与 macOS Keychain 测试线节点重叠")
    if local_nodeids & keychain:
        raise pytest.UsageError("本机材料与 macOS Keychain 测试线节点重叠")


def _matching_local_evidence_items(
    group: dict,
    items: list[pytest.Item],
) -> list[pytest.Item]:
    patterns = tuple(str(pattern) for pattern in group.get("test_file_globs", []))
    nodeids = set(str(nodeid) for nodeid in group.get("nodeids", []))
    matched: list[pytest.Item] = []
    for item in items:
        test_name = Path(str(item.fspath)).name
        file_matches = any(Path(test_name).match(pattern) for pattern in patterns)
        if file_matches or item.nodeid in nodeids:
            matched.append(item)
    return matched


def _deselect_except(
    config: pytest.Config,
    items: list[pytest.Item],
    selected: list[pytest.Item],
) -> None:
    selected_ids = {id(item) for item in selected}
    deselected = [item for item in items if id(item) not in selected_ids]
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)


def _local_items_by_group(
    local_evidence_registry: dict,
    items: list[pytest.Item],
) -> dict[str, list[pytest.Item]]:
    return {
        str(group["group_id"]): _matching_local_evidence_items(group, items)
        for group in local_evidence_registry["groups"]
    }


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    registry = _load_historical_replay_registry()
    local_evidence_registry = _load_local_evidence_registry()
    ci_lanes = _load_ci_lanes_contract()
    registered = set(historical_nodeids(registry))
    keychain_nodeids = set(ci_lanes["lanes"]["macos-keychain"]["pytest_nodeids"])
    _reject_registry_overlap(registered, local_evidence_registry, keychain_nodeids)

    ci_lane = config.getoption("--ci-lane")
    selected_local_groups = config.getoption("--local-evidence-group")
    if config.getoption("--historical-replay") and ci_lane is not None:
        raise pytest.UsageError("历史回放不能与其他 CI 测试线混跑")
    if selected_local_groups and ci_lane != "local-evidence":
        raise pytest.UsageError("本机材料分组只能与 local-evidence 测试线一起使用")

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

    if config.getoption("--historical-replay"):
        return

    local_items_by_group = _local_items_by_group(local_evidence_registry, items)
    local_items = {
        id(item): item
        for group_items in local_items_by_group.values()
        for item in group_items
    }
    for item in local_items.values():
        item.add_marker(pytest.mark.local_evidence)

    keychain_items = [item for item in items if item.nodeid in keychain_nodeids]
    collected_keychain = {item.nodeid for item in keychain_items}
    if ci_lane in {"main-portable", "macos-keychain"} and (
        collected_keychain != keychain_nodeids
    ):
        missing_keychain = sorted(keychain_nodeids - collected_keychain)
        raise pytest.UsageError(
            "macOS Keychain 测试线登记节点未被完整收集："
            + ",".join(missing_keychain)
        )

    if ci_lane == "main-portable":
        excluded_ids = set(local_items) | {id(item) for item in keychain_items}
        portable_items = [item for item in items if id(item) not in excluded_ids]
        if not portable_items:
            raise pytest.UsageError("main 可移植全量没有收集到任何测试")
        _deselect_except(config, items, portable_items)
        return

    if ci_lane == "macos-keychain":
        if sys.platform != "darwin":
            raise pytest.UsageError("macOS Keychain 测试线只能在 Darwin 上派发")
        _deselect_except(config, items, keychain_items)
        return

    if ci_lane == "local-evidence":
        groups_by_id = {
            str(group["group_id"]): group
            for group in local_evidence_registry["groups"]
        }
        requested_group_ids = selected_local_groups or list(groups_by_id)
        if len(requested_group_ids) != len(set(requested_group_ids)):
            raise pytest.UsageError("本机材料测试线分组不能重复")
        unknown = sorted(set(requested_group_ids) - set(groups_by_id))
        if unknown:
            raise pytest.UsageError("未知本机材料测试分组：" + ",".join(unknown))
        selected_items = {
            id(item): item
            for group_id in requested_group_ids
            for item in local_items_by_group[group_id]
        }
        if not selected_items:
            raise pytest.UsageError("本机材料测试线没有收集到登记节点")
        for group_id in requested_group_ids:
            group = groups_by_id[group_id]
            missing = [
                path for path in group["required_paths"] if not (ROOT / path).is_file()
            ]
            if missing:
                raise pytest.UsageError(
                    "本机证据专线材料不完整："
                    f"group_id={group_id}；missing={','.join(missing)}。"
                    "required_paths 是该分组的登记材料边界，不代表历史文件的全部材料清单。"
                )
        _deselect_except(config, items, list(selected_items.values()))
        return

    require_complete_local_evidence = (
        os.environ.get("NOVEL_RUN_LOCAL_EVIDENCE_TESTS") == "1"
    )
    for group in local_evidence_registry["groups"]:
        matched_items = _matching_local_evidence_items(group, items)
        if not matched_items:
            continue
        missing = [
            path for path in group["required_paths"] if not (ROOT / path).is_file()
        ]
        for item in matched_items:
            item.add_marker(pytest.mark.local_evidence)
        if not missing:
            continue
        if require_complete_local_evidence:
            raise pytest.UsageError(
                "本机证据专线材料不完整："
                f"group_id={group['group_id']}；missing={','.join(missing)}。"
                "required_paths 是该分组的登记材料边界，不代表历史文件的全部材料清单。"
            )
        for item in matched_items:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"{group['reason']}；缺失={','.join(missing)}；"
                        "本机证据专线必须先补齐登记材料，再设置 "
                        "NOVEL_RUN_LOCAL_EVIDENCE_TESTS=1"
                    )
                )
            )
