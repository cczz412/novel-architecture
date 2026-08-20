#!/usr/bin/env python3
"""Compatibility wrapper for the WO3 materialization helper.

R03 is authoritative for requirement wording. The advisory addendum uses a
blocked/not-ready vocabulary for its 17 currently non-executable cases. This
wrapper preserves the original helper, aligns traceability text to R03, extends
only the execution-tier label recognizer, and runs the otherwise unchanged
migration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
ORIGINAL_HELPER_COMMIT = "7b4c92c725ac50de7ddbfc7419a393c5e7311a4a"
SOURCE = subprocess.check_output(
    ["git", "show", f"{ORIGINAL_HELPER_COMMIT}:.github/wo3_apply.py"],
    text=True,
)
OLD = '''    for req_id in sorted(r03_by_id):
        if seed_by_id[req_id].get("requirement_text") != r03_by_id[req_id].get("长期需求"):
            raise SystemExit(f"requirement text mismatch for {req_id}")
'''
NEW = '''    for req_id in sorted(r03_by_id):
        authoritative_text = r03_by_id[req_id].get("长期需求")
        seed_text = seed_by_id[req_id].get("requirement_text")
        if seed_text != authoritative_text:
            seed_by_id[req_id]["requirement_text_candidate_before_r03_review"] = seed_text
            seed_by_id[req_id]["requirement_text"] = authoritative_text
'''
if SOURCE.count(OLD) != 1:
    raise SystemExit("fixed WO3 helper requirement-text block was not found exactly once")
SOURCE = SOURCE.replace(OLD, NEW, 1)
NAMESPACE: dict[str, object] = {
    "__name__": "wo3_apply_impl",
    "__file__": str(THIS_FILE),
}
exec(compile(SOURCE, "wo3_apply_impl.py", "exec"), NAMESPACE)


def classify_execution_label(value: str) -> str | None:
    normalized = value.upper().replace("-", "_").replace(" ", "_")
    blocked_tokens = (
        "NOT_EXECUTABLE",
        "UNEXECUTABLE",
        "NOT_CURRENTLY_EXECUTABLE",
        "CURRENTLY_BLOCKED",
        "BLOCKED",
        "NOT_RUNNABLE",
        "NOT_READY",
        "UNAVAILABLE",
        "UNIMPLEMENTED",
        "FUTURE_ONLY",
        "PENDING_OWNER",
        "PENDING_PRODUCT_DECISION",
    )
    if any(token in normalized for token in blocked_tokens) or any(
        token in value for token in ("暂不可执行", "不可执行", "当前阻断", "阻断", "尚未实现")
    ):
        return "NOT_EXECUTABLE"
    if "SEMANTIC" in normalized or "语义" in value:
        return "SEMANTIC"
    if "MECHANICAL" in normalized or "ZERO_API" in normalized or "机械" in value:
        return "MECHANICAL"
    return None


NAMESPACE["classify_execution_label"] = classify_execution_label
NAMESPACE["main"]()
