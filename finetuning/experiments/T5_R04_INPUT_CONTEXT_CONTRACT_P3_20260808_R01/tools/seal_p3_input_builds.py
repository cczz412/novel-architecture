#!/usr/bin/env python3
"""Verify two deterministic P3 input builds and seal run 1 without overwriting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


EXP = Path("/Users/a1234/挣钱/小说架构/finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01")
RUN1 = EXP / "build/run_1"
RUN2 = EXP / "build/run_2"
SEALED = EXP / "sealed_inputs_r01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path) -> list[dict[str, object]]:
    return [
        {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def main() -> None:
    if SEALED.exists():
        raise RuntimeError(f"封版目录已存在，禁止覆盖：{SEALED}")
    first = inventory(RUN1)
    second = inventory(RUN2)
    if first != second:
        raise RuntimeError("P3 两遍输入构建不一致")
    shutil.copytree(RUN1, SEALED)
    sealed = inventory(SEALED)
    if sealed != first:
        raise RuntimeError("P3 封版复制后字节漂移")
    receipt = {
        "status": "PASS_P3_TWO_RUN_BYTE_IDENTICAL_AND_SEALED",
        "file_count": len(first),
        "run_1_inventory_sha256": hashlib.sha256(json.dumps(first, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()).hexdigest(),
        "run_2_inventory_sha256": hashlib.sha256(json.dumps(second, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()).hexdigest(),
        "sealed_inventory_sha256": hashlib.sha256(json.dumps(sealed, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()).hexdigest(),
        "rights_groups": 74,
        "runnable_context_arms": ["c0_current_minimal", "c1_rulebook_8", "c2_purpose_short", "c4_previous_state_confirmed"],
        "gap_only_arms": ["c3_background_min_confirmed", "c5_structure_metadata"],
        "training": False,
    }
    (EXP / "P3_INPUT_TWO_RUN_AND_SEAL_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
