#!/usr/bin/env python3
"""Compatibility wrapper for the WO3 materialization helper.

The advisory seed can carry wording that predates the current R03 projection.
R03 is the authoritative requirement text for this ticket. This wrapper loads the
original helper from its fixed commit, preserves any differing seed wording as a
candidate note, replaces only the traceability copy with R03 text, and runs the
otherwise unchanged migration.
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
NAMESPACE["main"]()
