#!/usr/bin/env python3
"""Compatibility wrapper for the WO3 materialization helper.

R03 is authoritative for requirement wording. The runtime-gap register exposes
one atomic row per expectation with an explicit ``evidence_status`` field, and
the addendum uses blocked/not-ready vocabulary for its 17 non-executable cases.
This wrapper keeps the original generator fixed, replaces only those three input
normalizers, and runs the otherwise unchanged migration.
"""

from __future__ import annotations

import collections
import subprocess
from pathlib import Path
from typing import Any

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


def extract_runtime_evidence(
    runtime_gap: Any,
    r03_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """Use the register's explicit atomic evidence_status, not prose inference."""

    result: dict[str, dict[str, Any]] = {}
    raw_counts: collections.Counter[str] = collections.Counter()
    iter_dicts = NAMESPACE["iter_dicts"]
    expected_counts = NAMESPACE["EXPECTED_RUNTIME_COUNTS"]

    for node in iter_dicts(runtime_gap):
        req_id = node.get("expectation_id")
        raw_status = node.get("evidence_status")
        if req_id not in r03_ids or not isinstance(raw_status, str):
            continue
        normalized = raw_status.upper().replace("-", "_").replace(" ", "_")
        if "CONFLICT" in normalized:
            classification = "CURRENT_PATH_CONFLICT"
        elif "BACKGROUND" in normalized:
            classification = "BACKGROUND_ONLY"
        elif "PARTIAL" in normalized:
            classification = "PARTIAL_CODE_EVIDENCE"
        elif "DIRECT" in normalized:
            classification = "DIRECT_CODE_EVIDENCE"
        else:
            raise SystemExit(
                f"unknown runtime evidence_status for {req_id}: {raw_status}"
            )
        if req_id in result:
            raise SystemExit(f"duplicate runtime atomic evidence row for {req_id}")
        result[req_id] = {
            "classification": classification,
            "raw": raw_status,
        }
        raw_counts[raw_status] += 1

    missing = sorted(r03_ids - set(result))
    counts = collections.Counter(
        item["classification"] for item in result.values()
    )
    if missing or dict(counts) != expected_counts:
        print("RUNTIME_EVIDENCE_STATUS_DIAGNOSTIC")
        print("mapped", len(result), "missing", missing[:30])
        print("classification_counts", dict(counts))
        print("raw_status_counts", dict(sorted(raw_counts.items())))
        raise SystemExit(
            "runtime atomic evidence_status rows did not resolve to 61/43/36/2"
        )
    return result


NAMESPACE["classify_execution_label"] = classify_execution_label
NAMESPACE["extract_runtime_evidence"] = extract_runtime_evidence
NAMESPACE["main"]()
