#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from zbatch_modules.net_benefit_recompute import NetBenefitError, read_json, recompute


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Z批净收益三口径零调用重算")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    config_path = (ROOT / args.config).resolve()
    config_path.relative_to(ROOT)
    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.relative_to(ROOT)
    if output_dir.exists():
        raise NetBenefitError(f"输出目录已存在，拒绝覆盖：{output_dir}")

    config = read_json(config_path)
    result = recompute(config, ROOT)
    output_dir.mkdir(parents=True)
    output_path = output_dir / "net_benefit_recompute.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "run_id": result["run_id"],
        "status": result["status"],
        "model_calls": 0,
        "output": str(output_path.relative_to(ROOT)),
        "output_sha256": sha256_file(output_path),
        "net": {name: result["net_benefit"][name]["net"] for name in ("main", "strict", "wide")},
        "gates": result["gates"],
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

