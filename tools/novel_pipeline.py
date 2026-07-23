"""统一薄入口：现役命令原样交给 zbatch，只新增治理索引命令。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from governance_index import (  # noqa: E402
    CONTROL_PATH,
    CURRENT_STATE_PATH,
    ROOT,
    ROUTE_REGISTRY_PATH,
    refresh,
)
from pipeline_common.model_benchmark import main as model_benchmark_main  # noqa: E402
from pipeline_inspector import main as inspector_main  # noqa: E402
from pipeline_common.artifacts import read_json  # noqa: E402
from test_impact import main as test_impact_main  # noqa: E402
from zbatch import main as zbatch_main  # noqa: E402


def governance_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="novel_pipeline.py governance", description="治理索引")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("refresh", help="从机器真源重建治理索引")
    subparsers.add_parser("status", help="只读当前治理状态")
    args = parser.parse_args(argv)
    if args.command == "refresh":
        result = refresh()
    else:
        result = {
            "current_state": read_json(ROOT / CURRENT_STATE_PATH),
            "route_registry": read_json(ROOT / ROUTE_REGISTRY_PATH),
            "control_plane": read_json(ROOT / CONTROL_PATH),
            "module_registry": read_json(ROOT / "governance/module_registry.json"),
            "index": str(Path("governance/INDEX.md")),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "governance":
        return governance_main(arguments[1:])
    if arguments and arguments[0] == "inspect":
        return inspector_main(arguments[1:])
    if arguments and arguments[0] == "test-plan":
        return test_impact_main(arguments[1:])
    if arguments and arguments[0] == "model-benchmark":
        return model_benchmark_main(arguments[1:])
    return zbatch_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
