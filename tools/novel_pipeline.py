"""统一薄入口：只分流命名空间，旧 zbatch 参数保持原样。"""

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
from pipeline_common.repository_catalog import main as repository_catalog_main  # noqa: E402
from pipeline_inspector import main as inspector_main  # noqa: E402
from pipeline_common.artifacts import read_json  # noqa: E402
from test_impact import main as test_impact_main  # noqa: E402
from zbatch import main as zbatch_main  # noqa: E402


TOP_LEVEL_HELP = """\
小说架构统一入口

用法：
  python3 tools/novel_pipeline.py <命令> [参数]

统一命名空间：
  governance       刷新或查看治理索引
  inspect          运行隔离检查员
  test-plan        生成按改动选测试的计划
  model-benchmark  运行隔离模型横向试验
  catalog          查看只读仓库统一目录

兼容的旧流水线命令（参数原样交给 zbatch）：
  preflight        运行前预检
  run              执行已获批流水线
  register         登记材料或批次
  status           查看旧流水线运行状态
  attest           写入旧流水线审查票

查看具体参数：
  python3 tools/novel_pipeline.py <命令> --help
"""


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


def print_top_level_help() -> None:
    print(TOP_LEVEL_HELP)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in (["-h"], ["--help"]):
        print_top_level_help()
        return 0
    if arguments and arguments[0] == "governance":
        return governance_main(arguments[1:])
    if arguments and arguments[0] == "inspect":
        return inspector_main(arguments[1:])
    if arguments and arguments[0] == "test-plan":
        return test_impact_main(arguments[1:])
    if arguments and arguments[0] == "model-benchmark":
        return model_benchmark_main(arguments[1:])
    if arguments and arguments[0] == "catalog":
        return repository_catalog_main(arguments[1:])
    return zbatch_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
