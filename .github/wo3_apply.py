#!/usr/bin/env python3
"""Final compatibility wrapper for the temporary WO3 materializer.

The previous wrapper already normalizes R03 wording, runtime evidence, execution
tiers, and the 42 external-lane-only legacy tests. This layer fixes one source
identity distinction: the advisory JSON records the *input window package* SHA,
while the repository advisory index records the *returned result ZIP* SHA that
this work order must cite. Both identities are preserved without modifying the
read-only advisory source.
"""

from __future__ import annotations

import copy
import re
import subprocess
from pathlib import Path
from typing import Any

THIS_FILE = Path(__file__).resolve()
PREVIOUS_WRAPPER_COMMIT = "22eb2658391e4673b78123718c799ee9b28ef975"
PREVIOUS = subprocess.check_output(
    ["git", "show", f"{PREVIOUS_WRAPPER_COMMIT}:.github/wo3_apply.py"],
    text=True,
)
RUN_MARKER = 'NAMESPACE["main"]()'
if not PREVIOUS.rstrip().endswith(RUN_MARKER):
    raise SystemExit("previous WO3 wrapper no longer ends with the expected run marker")
PREVIOUS = PREVIOUS[: PREVIOUS.rfind(RUN_MARKER)]
WRAPPER_NAMESPACE: dict[str, object] = {
    "__name__": "wo3_previous_wrapper",
    "__file__": str(THIS_FILE),
}
exec(compile(PREVIOUS, "wo3_previous_wrapper.py", "exec"), WRAPPER_NAMESPACE)
NAMESPACE: dict[str, Any] = WRAPPER_NAMESPACE["NAMESPACE"]

ORIGINAL_BUILD_ADDENDUM = NAMESPACE["build_addendum_package"]
ORIGINAL_READ_JSON = NAMESPACE["read_json"]
WRITE_JSON = NAMESPACE["write_json"]
SHA256 = NAMESPACE["sha256"]
ADDENDUM_SOURCE_PATH: Path = NAMESPACE["ADDENDUM_SOURCE_PATH"]
ADDENDUM_INDEX_PATH: Path = NAMESPACE["ADDENDUM_INDEX_PATH"]
ADDENDUM_DESIGN: Path = NAMESPACE["ADDENDUM_DESIGN"]
ADDENDUM_MANIFEST: Path = NAMESPACE["ADDENDUM_MANIFEST"]
ADDENDUM_RECEIPT: Path = NAMESPACE["ADDENDUM_RECEIPT"]


def build_addendum_package(traceability: dict[str, Any]) -> dict[str, Any]:
    index_text = ADDENDUM_INDEX_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"\[atomic_test_design_r03_addendum/\]\([^\n)]*\).*?`([0-9a-f]{64})`",
        index_text,
    )
    if match is None:
        raise SystemExit("could not resolve advisory return ZIP SHA from 00_INDEX.md")
    return_zip_sha = match.group(1)

    source_payload = ORIGINAL_READ_JSON(ADDENDUM_SOURCE_PATH)
    source_window_sha = source_payload["source_verification"]["window_package"]["sha256"]
    if source_window_sha == return_zip_sha:
        raise SystemExit("source window package SHA unexpectedly equals advisory return ZIP SHA")

    def patched_read_json(path: Path) -> Any:
        value = ORIGINAL_READ_JSON(path)
        if Path(path).resolve() != ADDENDUM_SOURCE_PATH.resolve():
            return value
        patched = copy.deepcopy(value)
        patched["source_verification"]["window_package"]["sha256"] = return_zip_sha
        return patched

    NAMESPACE["read_json"] = patched_read_json
    try:
        receipt = ORIGINAL_BUILD_ADDENDUM(traceability)
    finally:
        NAMESPACE["read_json"] = ORIGINAL_READ_JSON

    design = ORIGINAL_READ_JSON(ADDENDUM_DESIGN)
    embedded_source = copy.deepcopy(source_payload)
    embedded_source["source_verification"]["advisory_return_package"] = {
        "logical_name": "atomic_test_design_r03_addendum advisory return ZIP",
        "sha256": return_zip_sha,
        "index_path": str(ADDENDUM_INDEX_PATH.relative_to(NAMESPACE["ROOT"])),
        "identity": "ADVISORY_RETURN_ZIP_NOT_SOURCE_WINDOW_PACKAGE",
    }
    design["source_advisory_payload"] = embedded_source
    source_meta = design["source"]
    source_meta.pop("window_package_sha256", None)
    source_meta["advisory_return_zip_sha256"] = return_zip_sha
    source_meta["source_window_package_sha256"] = source_window_sha
    source_meta["identity_boundary"] = (
        "The return ZIP SHA comes from work/advisory_returns_20260820_r01/00_INDEX.md; "
        "the source window-package SHA remains inside source_verification for provenance."
    )
    WRITE_JSON(ADDENDUM_DESIGN, design)

    manifest = ORIGINAL_READ_JSON(ADDENDUM_MANIFEST)
    design_rows = [
        row
        for row in manifest.get("files", [])
        if isinstance(row, dict) and row.get("path") == ADDENDUM_DESIGN.name
    ]
    if len(design_rows) != 1:
        raise SystemExit("addendum manifest does not have exactly one design row")
    design_rows[0]["bytes"] = ADDENDUM_DESIGN.stat().st_size
    design_rows[0]["sha256"] = SHA256(ADDENDUM_DESIGN)
    WRITE_JSON(ADDENDUM_MANIFEST, manifest)

    final_receipt = ORIGINAL_READ_JSON(ADDENDUM_RECEIPT)
    final_receipt.pop("source_window_zip_sha256", None)
    final_receipt["source_return_zip_sha256"] = return_zip_sha
    final_receipt["source_window_package_sha256"] = source_window_sha
    final_receipt["design_sha256"] = SHA256(ADDENDUM_DESIGN)
    final_receipt["manifest_sha256"] = SHA256(ADDENDUM_MANIFEST)
    checks = final_receipt.setdefault("checks", [])
    if "SOURCE_RETURN_ZIP_SHA_MATCHES_ADVISORY_INDEX" not in checks:
        checks.append("SOURCE_RETURN_ZIP_SHA_MATCHES_ADVISORY_INDEX")
    WRITE_JSON(ADDENDUM_RECEIPT, final_receipt)
    return final_receipt


NAMESPACE["build_addendum_package"] = build_addendum_package
NAMESPACE["main"]()
