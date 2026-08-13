#!/usr/bin/env python3
"""R02 environment-only wrapper around the frozen minimal R01 Demo runner."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[4]
R01_RUNNER = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_RUN_20260808_R01/tools/run_demo.py"
EXPECTED_PYTHON = "/opt/homebrew/opt/python@3.12/bin/python3.12"


def load_r01():
    spec = importlib.util.spec_from_file_location("wo01_demo_r01_runner", R01_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("R01_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smoke_plan(module) -> list[dict]:
    plan = module.load_plan()
    return [row for row in plan if row["row_index"] < 2]


def run(mode: str, output_dir: Path) -> None:
    if sys.executable != EXPECTED_PYTHON:
        raise RuntimeError(f"WRONG_PYTHON:{sys.executable}")
    module = load_r01()
    if mode == "smoke":
        original = module.selected_plan
        module.selected_plan = lambda selected: smoke_plan(module) if selected == "smoke" else original(selected)
    module.run(mode, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("validate", "smoke", "full"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    module = load_r01()
    if args.mode == "validate":
        plan = module.load_plan()
        print(json.dumps({"status": "PASS_R02_INPUTS", "rows": len(plan), "smoke_rows": len(smoke_plan(module)), "python_required": EXPECTED_PYTHON, "model_loaded": False}, ensure_ascii=False))
        return
    if args.output_dir is None:
        parser.error("smoke/full 需要 --output-dir")
    run(args.mode, args.output_dir)


if __name__ == "__main__":
    main()
