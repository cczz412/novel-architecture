#!/usr/bin/env python3
"""T4 局部段覆盖试点的零调用准备与停点判定命令。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from zbatch_modules import t4_local_segment


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "baseline-audit", "run-chapter", "evaluate"))
    parser.add_argument(
        "--manifest",
        default="config/diagnostics/Z00z_X01_局部段覆盖试点_v1.json",
    )
    parser.add_argument("--preparation", default="work/zbatch_t4/Z00z_pilot_preparation.json")
    parser.add_argument("--output")
    parser.add_argument("--chapter", type=int)
    args = parser.parse_args()

    manifest_path = (ROOT / args.manifest).resolve()
    canonical_manifest = (ROOT / "config/diagnostics/Z00z_X01_局部段覆盖试点_v1.json").resolve()
    canonical_preparation = (ROOT / "work/zbatch_t4/Z00z_pilot_preparation.json").resolve()
    if args.command in {"run-chapter", "evaluate"} and manifest_path != canonical_manifest:
        raise t4_local_segment.T4PilotError("正式调用与总判只允许默认 T4 清单")
    if args.command in {"run-chapter", "evaluate"} and (ROOT / args.preparation).resolve() != canonical_preparation:
        raise t4_local_segment.T4PilotError("正式调用与总判只允许标准五章准备单")
    manifest = t4_local_segment.read_json(manifest_path)
    if args.command == "prepare":
        result = t4_local_segment.prepare_pilot_configs(manifest, ROOT)
        output = Path(args.output) if args.output else Path(args.preparation)
    elif args.command == "baseline-audit":
        result = t4_local_segment.baseline_equivalence_audit(manifest, ROOT)
        output = Path(args.output) if args.output else Path("work/zbatch_t4/Z00z_baseline_equivalence.json")
    elif args.command == "run-chapter":
        if args.chapter is None:
            parser.error("run-chapter 必须带 --chapter")
        preparation_path = (ROOT / args.preparation).resolve()
        preparation = t4_local_segment.read_json(preparation_path)
        baseline_path = ROOT / "work/zbatch_t4/Z00z_baseline_equivalence.json"
        call_gate = t4_local_segment.validate_call_gate(
            manifest,
            preparation,
            ROOT,
            chapter=args.chapter,
            saved_baseline_path=baseline_path,
        )
        gate_path = ROOT / f"work/zbatch_t4/call_gates/ch{args.chapter:04d}_before.json"
        t4_local_segment.write_json(gate_path, call_gate)
        permit_path = t4_local_segment.create_call_permit(
            manifest,
            ROOT,
            args.chapter,
            call_gate["run_id"],
        )
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/zbatch.py"),
                    "run",
                    "--config",
                    call_gate["config_path"],
                ],
                cwd=ROOT,
                check=False,
            )
        finally:
            permit_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            return completed.returncode or 2
        t4_local_segment.create_run_seal(
            root=ROOT,
            config_path=(ROOT / call_gate["config_path"]).resolve(),
            chapter=args.chapter,
        )
        order = [int(value) for value in manifest["pilot_chapters"]]
        completed_chapters = order[: order.index(args.chapter) + 1]
        result = t4_local_segment.chapter_stop_evaluation(
            manifest,
            preparation,
            ROOT,
            completed_chapters,
        )
        output = Path(args.output) if args.output else Path(
            f"work/zbatch_t4/chapter_gates/ch{args.chapter:04d}_after.json"
        )
    else:
        preparation = t4_local_segment.read_json((ROOT / args.preparation).resolve())
        result = t4_local_segment.evaluate_pilot(manifest, preparation, ROOT)
        output = Path(args.output) if args.output else Path("work/zbatch_t4/Z00z_pilot_evaluation.json")
    output_path = output if output.is_absolute() else ROOT / output
    t4_local_segment.write_json(output_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return t4_local_segment.result_exit_code(args.command, result)


if __name__ == "__main__":
    raise SystemExit(main())
