#!/usr/bin/env python3
"""第41道件C的零调用预演、一次性授权与五章实跑入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from zbatch_modules import nonthinking_pilot


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/diagnostics/Z01h_X01_非思考模式_5章_v1.json"
REPORT_DIR = "reports/Z01h_非思考模式单变量轮_20260719"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "authorize", "run"))
    parser.add_argument("--config", default=str(CONFIG.relative_to(ROOT)))
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        selected = (ROOT / args.config).resolve()
        if args.command in {"authorize", "run"} and selected != CONFIG:
            raise nonthinking_pilot.NonThinkingPilotError(
                "正式授权与实跑只接受登记过的件C标准配置"
            )
        config = nonthinking_pilot.read_json(selected)
        if args.command == "preflight":
            output = nonthinking_pilot.resolve_report_output(
                ROOT,
                args.output or f"{REPORT_DIR}/preflight.json",
            )
            result = nonthinking_pilot.save_preflight(config, ROOT)
        elif args.command == "authorize":
            output = nonthinking_pilot.resolve_report_output(
                ROOT,
                args.output or f"{REPORT_DIR}/authorization.json",
            )
            permit = nonthinking_pilot.create_permit(config, ROOT)
            result = {
                "status": "authorized",
                "batch_id": config["batch_id"],
                "permit_path": str(permit.relative_to(ROOT)),
                "permit_sha256": nonthinking_pilot.sha256_file(permit),
                "model_calls": 0,
            }
        else:
            output = nonthinking_pilot.resolve_report_output(
                ROOT,
                args.output or f"{REPORT_DIR}/Z01h_result.json",
            )
            result = nonthinking_pilot.run(config, ROOT)
        nonthinking_pilot.write_json(output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "run" and result.get("status") != "completed":
            return 2
        return 0
    except (nonthinking_pilot.NonThinkingPilotError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
