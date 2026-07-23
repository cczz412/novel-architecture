#!/usr/bin/env python3
"""执行 T5 缓存排法小实验。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from zbatch_modules import t5_cache_benchmark


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config/diagnostics/Z01a_X01_缓存排法AB_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "run"))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(ROOT)))
    args = parser.parse_args()
    manifest_path = (ROOT / args.manifest).resolve()
    if manifest_path != DEFAULT_MANIFEST.resolve():
        raise t5_cache_benchmark.T5BenchmarkError("T5 正式工具只允许默认实验清单")
    manifest = t5_cache_benchmark.read_json(manifest_path)
    if args.command == "preflight":
        result = t5_cache_benchmark.preflight(manifest, ROOT, require_fresh_run=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "pass" else 2
    result = t5_cache_benchmark.run_benchmark(manifest, ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
