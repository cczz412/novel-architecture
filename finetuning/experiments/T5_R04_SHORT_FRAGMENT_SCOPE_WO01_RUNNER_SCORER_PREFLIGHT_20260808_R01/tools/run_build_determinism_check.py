#!/usr/bin/env python3
"""Run two isolated TEST_ONLY builds and bind their full member identities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import build_preflight_evidence as builder
import finalize_preflight as finalizer


EXP = Path(__file__).resolve().parents[1]


def member_rows(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": builder.sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def tree_digest(rows: list[dict[str, object]]) -> str:
    return hashlib.sha256(
        b"".join(
            str(row["path"]).encode()
            + b"\0"
            + str(row["bytes"]).encode()
            + b"\0"
            + str(row["sha256"]).encode()
            + b"\n"
            for row in rows
        )
    ).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="wo01-determinism-") as temporary:
        root = Path(temporary)
        first, second = root / "run_1", root / "run_2"
        builder.build(first)
        builder.build(second)
        comparison = builder.compare(first, second)
        first_rows, second_rows = member_rows(first), member_rows(second)
    bindings = finalizer.source_bindings()
    input_set_sha = hashlib.sha256(
        json.dumps(bindings, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    receipt = {
        "schema_version": "t5-r04-wo01-build-determinism-v2",
        "status": comparison["status"],
        "file_count_each": len(first_rows),
        "mismatches": comparison["mismatches"],
        "tree_digest": comparison["tree_digest"],
        "run_1_tree_digest": tree_digest(first_rows),
        "run_2_tree_digest": tree_digest(second_rows),
        "run_1_members": first_rows,
        "run_2_members": second_rows,
        "source_bindings": bindings,
        "input_set_sha256": input_set_sha,
        "builder_sha256": bindings["builder_sha256"],
        "model_loaded": False,
        "model_inference_calls": 0,
        "api_calls": 0,
        "training_started": False,
    }
    (EXP / "BUILD_DETERMINISM_RECEIPT.json").write_bytes(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
