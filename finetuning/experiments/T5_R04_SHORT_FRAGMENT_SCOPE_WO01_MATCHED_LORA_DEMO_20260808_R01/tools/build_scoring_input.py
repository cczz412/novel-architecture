#!/usr/bin/env python3
"""Combine the three frozen DEV24 raw files for the existing recoverable scorer."""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
RUN = REPO / "runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_MATCHED_LORA_DEMO_R01"
ARMS = (
    ("target_only", "TARGET_ONLY"),
    ("small_halo", "SMALL_HALO"),
    ("current_window", "CURRENT_WINDOW"),
)
OUTPUT = RUN / "scoring/RAW_OUTPUTS_3X24.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    rows = []
    for internal, visible in ARMS:
        source = RUN / "results" / internal / "update_72" / "DEV24_RAW_OUTPUTS.jsonl"
        current = read_jsonl(source)
        if len(current) != 24:
            raise RuntimeError(f"DEV_DENOMINATOR_DRIFT:{internal}")
        for row in current:
            rows.append(
                {
                    **row,
                    "arm": visible,
                    "internal_arm": internal,
                    "output_tokens": row["output_tokens_excluding_stop"],
                }
            )
    if len(rows) != 72:
        raise RuntimeError("RAW_NOT_3X24")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"status": "PASS_RAW_3X24_COMBINED", "rows": len(rows), "path": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
