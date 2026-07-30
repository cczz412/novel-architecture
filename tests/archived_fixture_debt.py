from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from tools.historical_test_replay import (  # noqa: E402
    ReplayError,
    historical_nodeids,
    load_registry,
    verify_materialization_receipt,
)


def require_materialized_historical_replay(nodeid: str) -> None:
    """旧导入名保留兼容；这里只验真工作副本，不再挂账或 xfail。"""

    registry = load_registry(ROOT)
    if nodeid not in set(historical_nodeids(registry)):
        raise AssertionError(f"历史回放节点未登记：{nodeid}")
    try:
        verify_materialization_receipt(ROOT)
    except ReplayError as exc:
        raise AssertionError(f"历史回放工作副本无效：{exc.code}") from exc
