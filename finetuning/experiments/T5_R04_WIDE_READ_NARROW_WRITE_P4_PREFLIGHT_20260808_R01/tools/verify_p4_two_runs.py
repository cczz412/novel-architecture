#!/usr/bin/env python3
"""Compare the complete P4 toy-run member sets and raw bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_MEMBERS = ["TOY_SPLITTER_BUILD.json"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    members_1 = sorted(path.name for path in args.run_1.iterdir() if path.is_file())
    members_2 = sorted(path.name for path in args.run_2.iterdir() if path.is_file())
    if members_1 != EXPECTED_MEMBERS or members_2 != EXPECTED_MEMBERS:
        raise RuntimeError(
            f"run member drift: expected={EXPECTED_MEMBERS} run1={members_1} run2={members_2}"
        )

    comparisons = []
    for member in EXPECTED_MEMBERS:
        first = args.run_1 / member
        second = args.run_2 / member
        json.loads(first.read_text(encoding="utf-8"))
        json.loads(second.read_text(encoding="utf-8"))
        equal = first.read_bytes() == second.read_bytes()
        if not equal:
            raise RuntimeError(f"run bytes differ: {member}")
        comparisons.append(
            {
                "path": member,
                "run_1_sha256": sha256(first),
                "run_2_sha256": sha256(second),
                "byte_identical": equal,
                "bytes": first.stat().st_size,
            }
        )

    receipt = {
        "schema_version": "t5-r04-p4-two-run-comparison-v1",
        "status": "PASS_R02_TOY_SPLITTER_TWO_RUN_BYTE_IDENTICAL",
        "expected_members": EXPECTED_MEMBERS,
        "member_sets_identical": members_1 == members_2,
        "all_files_byte_identical": all(item["byte_identical"] for item in comparisons),
        "comparisons": comparisons,
        "model_inference_started": False,
        "real_novel_text_read": False,
        "synthetic_full_chapter_generated": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": receipt["status"], "receipt_sha256": sha256(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
