#!/usr/bin/env python3
"""Build the frozen source-only manifest for the vendored mlx_lm runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
OUTPUT = EXP / "VENDOR_SOURCE_MANIFEST.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    members = []
    for path in sorted(VENDOR.rglob("*.py")):
        if "__pycache__" in path.parts or path.is_symlink() or not path.is_file():
            continue
        members.append(
            {
                "path": str(path.relative_to(VENDOR)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    required = {
        "mlx_lm/__init__.py",
        "mlx_lm/_version.py",
        "mlx_lm/utils.py",
        "mlx_lm/generate.py",
        "mlx_lm/sample_utils.py",
    }
    if not required.issubset({row["path"] for row in members}):
        raise RuntimeError("VENDOR_REQUIRED_IMPORT_SOURCE_MISSING")
    tree_digest = hashlib.sha256(
        b"".join(
            row["path"].encode("utf-8")
            + b"\0"
            + str(row["bytes"]).encode("ascii")
            + b"\0"
            + row["sha256"].encode("ascii")
            + b"\n"
            for row in members
        )
    ).hexdigest()
    payload = {
        "schema_version": "t5-r04-wo01-mlx-lm-vendor-source-manifest-v1",
        "status": "FROZEN_SOURCE_ONLY_RUNTIME_IDENTITY",
        "vendor_root": str(VENDOR.relative_to(REPO)),
        "mlx_lm_version": "0.30.7",
        "member_count": len(members),
        "tree_digest": tree_digest,
        "required_runtime_import_sources": sorted(required),
        "members": members,
    }
    OUTPUT.write_bytes(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )


if __name__ == "__main__":
    main()
