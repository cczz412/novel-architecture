#!/usr/bin/env python3
"""Compatibility wrapper for the temporary WO2 migration helper.

The original helper assumed count fields existed directly in
TEST_DESIGN_CURRENT.json. The frozen pointer stores those counts in its signed
validation receipt instead. This wrapper loads the prior helper from Git history,
verifies the frozen design and receipt bytes, exposes the receipt counts to that
helper, and then runs the unchanged migration.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
SOURCE = subprocess.check_output(
    ["git", "show", "HEAD^:.github/wo2_apply.py"],
    text=True,
)
NAMESPACE: dict[str, object] = {
    "__name__": "wo2_apply_impl",
    "__file__": str(THIS_FILE),
}
exec(compile(SOURCE, "wo2_apply_impl.py", "exec"), NAMESPACE)

original_load_json = NAMESPACE["load_json"]
root = NAMESPACE["ROOT"]
test_current = NAMESPACE["TEST_CURRENT"]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compatible_load_json(path: str) -> dict:
    data = original_load_json(path)
    if path != test_current:
        return data

    base = root / "references/atomic-expectations"
    receipt_path = base / data["validation_receipt"]
    design_path = base / data["design"]
    manifest_relative = "ATOMIC_TEST_DESIGN_20260820_R01/MANIFEST.json"
    manifest_path = base / manifest_relative

    assert receipt_path.is_file()
    assert design_path.is_file()
    assert manifest_path.is_file()
    assert file_sha256(receipt_path) == data["validation_receipt_sha256"]
    assert file_sha256(design_path) == data["design_sha256"]

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS"
    assert receipt["expectation_count"] == 127
    assert receipt["small_test_count"] == 762
    assert receipt["unique_expectation_ids"] == 127
    assert receipt["unique_test_ids"] == 762

    return {
        **data,
        "covered_expectation_count": receipt["expectation_count"],
        "designed_test_count": receipt["small_test_count"],
        "manifest_path": manifest_relative,
        "manifest_sha256": file_sha256(manifest_path),
    }


NAMESPACE["load_json"] = compatible_load_json
NAMESPACE["main"]()
