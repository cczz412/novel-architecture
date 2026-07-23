#!/usr/bin/env python3
"""提取方法单臂试验的零调用预演、一次性授权、实跑与 A/B 横向列数入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from zbatch_modules import extraction_method_ab


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CONFIGS = {
    "A": ROOT / "config/diagnostics/Z01b_X01_段级任务拆分_5章_v1.json",
    "B": ROOT / "config/diagnostics/Z01c_X01_程序点名靶_5章_v1.json",
    "C": ROOT / "config/diagnostics/Z01e_X01_结构地图前置块_5章_v1.json",
    "D": ROOT / "config/diagnostics/Z01d_X01_每段强合同_5章_v1.json",
}
FORMAL_CONFIGS = {
    "A": {CANONICAL_CONFIGS["A"]},
    "B": {CANONICAL_CONFIGS["B"]},
    "C": {CANONICAL_CONFIGS["C"]},
    "D": {
        CANONICAL_CONFIGS["D"],
        ROOT / "config/diagnostics/Z01f_X01_每段强合同v2_5章_v1.json",
    },
}


def _config(arm: str, path: str | None, *, formal: bool) -> tuple[Path, dict]:
    selected = (ROOT / path).resolve() if path else CANONICAL_CONFIGS[arm]
    if formal and selected not in FORMAL_CONFIGS[arm]:
        raise extraction_method_ab.ExtractionMethodError("正式授权与实跑只接受登记过的标准配置")
    return selected, extraction_method_ab.read_json(selected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "authorize", "run", "compare"))
    parser.add_argument("--arm", choices=("A", "B", "C", "D"))
    parser.add_argument("--config")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        if args.command == "compare":
            output = extraction_method_ab.resolve_scoped_output(
                ROOT,
                args.output or "reports/Z01bc_提取漏对照轮_20260718/comparison.json",
                "reports/Z01bc_提取漏对照轮_20260718",
            )
            a_config = extraction_method_ab.read_json(CANONICAL_CONFIGS["A"])
            b_config = extraction_method_ab.read_json(CANONICAL_CONFIGS["B"])
            a = extraction_method_ab.read_json(ROOT / "runs" / a_config["run_id"] / "result.json")
            b = extraction_method_ab.read_json(ROOT / "runs" / b_config["run_id"] / "result.json")
            result = extraction_method_ab.compare_results(a, b)
        else:
            if args.arm is None:
                parser.error("preflight/authorize/run 必须带 --arm")
            _, config = _config(args.arm, args.config, formal=args.command in {"authorize", "run"})
            if config.get("arm") != args.arm:
                raise extraction_method_ab.ExtractionMethodError("命令 arm 与配置不一致")
            if args.command == "preflight":
                output = extraction_method_ab.resolve_scoped_output(
                    ROOT,
                    args.output or f"work/zbatch_ab/preflight/{config['batch_id']}.json",
                    "work/zbatch_ab/preflight",
                )
                extraction_method_ab.validate_artifact_paths(config, ROOT)
                result = extraction_method_ab.save_preflight(config, ROOT)
            elif args.command == "authorize":
                output = extraction_method_ab.resolve_scoped_output(
                    ROOT,
                    args.output or f"work/zbatch_ab/authorizations/{config['batch_id']}.json",
                    "work/zbatch_ab/authorizations",
                )
                extraction_method_ab.validate_artifact_paths(config, ROOT)
                permit = extraction_method_ab.create_permit(config, ROOT)
                result = {
                    "status": "authorized",
                    "arm": args.arm,
                    "permit_path": str(permit.relative_to(ROOT)),
                    "permit_sha256": extraction_method_ab.sha256_file(permit),
                    "model_calls": 0,
                }
            else:
                if args.arm == "C":
                    default_output = "reports/Z01e_结构地图前置块单臂轮_20260719/Z01e_result.json"
                    allowed_dir = "reports/Z01e_结构地图前置块单臂轮_20260719"
                elif args.arm == "D" and config["batch_id"] == "Z01f":
                    default_output = "reports/Z01f_每段强合同v2单臂轮_20260719/Z01f_result.json"
                    allowed_dir = "reports/Z01f_每段强合同v2单臂轮_20260719"
                elif args.arm == "D":
                    default_output = "reports/Z01d_每段强合同单臂轮_20260719/Z01d_result.json"
                    allowed_dir = "reports/Z01d_每段强合同单臂轮_20260719"
                else:
                    default_output = (
                        f"reports/Z01bc_提取漏对照轮_20260718/{config['batch_id']}_result.json"
                    )
                    allowed_dir = "reports/Z01bc_提取漏对照轮_20260718"
                output = extraction_method_ab.resolve_scoped_output(
                    ROOT,
                    args.output or default_output,
                    allowed_dir,
                )
                extraction_method_ab.validate_artifact_paths(config, ROOT)
                result = extraction_method_ab.run_arm(config, ROOT)
        extraction_method_ab.write_json(output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "run" and result.get("status") != "completed":
            return 2
        return 0
    except extraction_method_ab.ExtractionMethodError as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
