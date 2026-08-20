#!/usr/bin/env python3
"""Compatibility wrapper for the WO3 materialization helper.

R03 is authoritative for requirement wording. The runtime-gap register exposes
one atomic row per expectation with an explicit ``evidence_status`` field. The
R03 addendum exposes its 42 legacy scope-only tests through delta ``R03-D01``
and uses blocked/not-ready vocabulary for its 17 non-executable cases. This
wrapper keeps the original generator fixed and replaces only those input
normalizers before running the otherwise unchanged migration.
"""

from __future__ import annotations

import collections
import re
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
        if "CONFLICT" in normalized or "CONTRADICT" in normalized:
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


def extract_external_lane_only(
    addendum: Any,
    old_design: Any,
) -> list[dict[str, Any]]:
    """Normalize addendum delta R03-D01 into EXTERNAL_LANE_ONLY annotations."""

    old_test_ids = {
        value
        for value in NAMESPACE["iter_strings"](old_design)
        if isinstance(value, str) and re.match(r"^AT[1-4]-", value)
    }
    preservation = addendum.get("legacy_preservation")
    register = addendum.get("legacy_reword_register")
    audit = addendum.get("legacy_audit")
    self_checks = addendum.get("self_check", {}).get("checks", {})
    if not isinstance(preservation, dict):
        raise SystemExit("addendum lacks legacy_preservation")
    if not isinstance(register, list):
        raise SystemExit("addendum lacks legacy_reword_register")
    if not isinstance(audit, dict):
        raise SystemExit("addendum lacks legacy_audit")

    deltas = [
        row
        for row in register
        if isinstance(row, dict)
        and row.get("delta_id") == "R03-D01"
        and row.get("change_kind") == "APPLICABILITY_SCOPE_TAG"
    ]
    if len(deltas) != 1:
        raise SystemExit(f"expected one R03-D01 applicability delta, found {len(deltas)}")
    delta = deltas[0]

    requirement_ids = delta.get("requirement_ids")
    affected_test_ids = delta.get("affected_test_ids")
    if not isinstance(requirement_ids, list) or not all(
        isinstance(item, str) and item for item in requirement_ids
    ):
        raise SystemExit("R03-D01 requirement_ids is invalid")
    if not isinstance(affected_test_ids, list) or not all(
        isinstance(item, str) and item for item in affected_test_ids
    ):
        raise SystemExit("R03-D01 affected_test_ids is invalid")

    expected_requirements = preservation.get("scope_only_requirement_ids")
    if sorted(requirement_ids) != sorted(expected_requirements or []):
        raise SystemExit("R03-D01 requirement IDs differ from legacy_preservation")
    if len(set(requirement_ids)) != 7:
        raise SystemExit(f"expected 7 scope-only requirements, found {len(set(requirement_ids))}")
    if delta.get("affected_test_count") != 42:
        raise SystemExit("R03-D01 affected_test_count is not 42")
    if preservation.get("scope_only_test_count") != 42:
        raise SystemExit("legacy_preservation scope_only_test_count is not 42")
    if self_checks.get("scope_only_requirement_count") != 7:
        raise SystemExit("self-check scope_only_requirement_count is not 7")
    if self_checks.get("scope_only_legacy_test_count") != 42:
        raise SystemExit("self-check scope_only_legacy_test_count is not 42")
    if len(affected_test_ids) != 42 or len(set(affected_test_ids)) != 42:
        raise SystemExit("R03-D01 must contain 42 unique legacy test IDs")
    unknown = sorted(set(affected_test_ids) - old_test_ids)
    if unknown:
        raise SystemExit(f"R03-D01 references tests absent from the frozen old design: {unknown}")

    inventory = audit.get("requirement_inventory")
    if not isinstance(inventory, list):
        raise SystemExit("legacy_audit lacks requirement_inventory")
    test_to_requirement: dict[str, str] = {}
    for row in inventory:
        if not isinstance(row, dict):
            continue
        req_id = row.get("requirement_id")
        test_ids = row.get("test_ids")
        if not isinstance(req_id, str) or not isinstance(test_ids, list):
            continue
        for test_id in test_ids:
            if not isinstance(test_id, str):
                continue
            if test_id in test_to_requirement:
                raise SystemExit(f"duplicate legacy inventory test ID: {test_id}")
            test_to_requirement[test_id] = req_id

    mapped_counts: collections.Counter[str] = collections.Counter()
    annotations: list[dict[str, Any]] = []
    for test_id in sorted(affected_test_ids):
        req_id = test_to_requirement.get(test_id)
        if req_id not in requirement_ids:
            raise SystemExit(
                f"scope-only test {test_id} maps outside R03-D01 requirements: {req_id}"
            )
        mapped_counts[req_id] += 1
        annotations.append(
            {
                "test_id": test_id,
                "scope": "EXTERNAL_LANE_ONLY",
                "requirement_ids": [req_id],
                "source_delta_id": "R03-D01",
                "source_change_kind": "APPLICABILITY_SCOPE_TAG",
                "source_wording": delta.get("new_wording"),
                "sources": [
                    "work/advisory_returns_20260820_r01/atomic_test_design_r03_addendum/ATOMIC_TEST_DESIGN_R03_ADDENDUM.json#R03-D01",
                    "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md#R14-新增的共同口径",
                    "references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/03_CREATION_AND_MEMORY_PIPELINES.md",
                ],
                "boundary": (
                    "旧测试正文、ID、权重和冻结字节保持不动；只适用于外来旧章／"
                    "外部手写书稿车道，不得套到产品自产章事实稿车道。"
                ),
            }
        )

    if set(mapped_counts) != set(requirement_ids):
        raise SystemExit("scope-only annotations do not cover the seven R03-D01 requirements")
    if any(count != 6 for count in mapped_counts.values()):
        raise SystemExit(f"scope-only requirements are not six tests each: {dict(mapped_counts)}")
    return annotations


NAMESPACE["classify_execution_label"] = classify_execution_label
NAMESPACE["extract_runtime_evidence"] = extract_runtime_evidence
NAMESPACE["extract_external_lane_only"] = extract_external_lane_only
NAMESPACE["main"]()
