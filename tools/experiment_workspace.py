#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from experiment_workspace_modules import MaterializeError, materialize


ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按冻结清单把本地零件复制进一次性试验工作区。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize_parser = subparsers.add_parser(
        "materialize",
        help="只复制并验收零件；不会运行程序、联网或调用模型。",
    )
    materialize_parser.add_argument(
        "--plan",
        required=True,
        help="仓库内 experiments/ 或测试夹具下的物化计划相对路径。",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "materialize":
        raise AssertionError("argparse accepted an unknown command")
    try:
        output = materialize(repo_root=ROOT, plan_relative=args.plan)
    except MaterializeError as exc:
        payload = {"error_code": exc.code, "status": "REJECTED"}
        if exc.path is not None:
            payload["path"] = exc.path
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "output": output.relative_to(ROOT).as_posix(),
                "scope": "copy_only",
                "status": "MATERIALIZED",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
