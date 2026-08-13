#!/usr/bin/env python3
"""比较两次 EVALUATOR_R02 产物并写出可审计清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    names_1 = sorted(path.name for path in args.run_1.iterdir() if path.is_file())
    names_2 = sorted(path.name for path in args.run_2.iterdir() if path.is_file())
    if names_1 != names_2:
        raise SystemExit("RUN_MEMBER_SET_MISMATCH")
    rows = []
    all_equal = True
    for name in names_1:
        left, right = args.run_1 / name, args.run_2 / name
        left_sha, right_sha = sha256(left), sha256(right)
        equal = left_sha == right_sha and left.stat().st_size == right.stat().st_size
        all_equal &= equal
        rows.append({
            "path": name,
            "run_1_sha256": left_sha,
            "run_2_sha256": right_sha,
            "run_1_bytes": left.stat().st_size,
            "run_2_bytes": right.stat().st_size,
            "byte_identical": equal,
        })
    value = {
        "schema_version": "t5-r04-evaluator-r02-two-run-comparison-v1",
        "status": "PASS_TWO_RUN_BYTE_IDENTICAL" if all_equal else "FAIL_TWO_RUN_DRIFT",
        "file_count": len(rows),
        "all_byte_identical": all_equal,
        "files": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all_equal else 2


if __name__ == "__main__":
    raise SystemExit(main())
