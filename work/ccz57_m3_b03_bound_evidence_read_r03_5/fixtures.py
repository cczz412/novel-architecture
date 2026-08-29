"""Synthetic B-01/B-02-backed inputs for the B-03 offline shell."""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from b03_contracts import make_input_record, record_ref

MODULE_ROOT = Path(__file__).resolve().parent
B02_ROOT = MODULE_ROOT.parent / "ccz57_m3_b02_diagnostic_coverage_r03_5"


def exact_context() -> dict[str, Any]:
    """Load B-02's read-only synthetic interface without reading novel files."""

    sys.path.insert(0, str(B02_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "b03_b02_fixtures", B02_ROOT / "fixtures.py"
        )
        if spec is None or spec.loader is None:
            raise AssertionError("B-02 fixture loader unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.exact_upstream_fixture()
    finally:
        sys.path.remove(str(B02_ROOT))


def policy_record() -> dict[str, Any]:
    return make_input_record(
        record_type="M3_BOUND_EVIDENCE_READ_POLICY",
        record_id="policy:fixture-bound-evidence-r03-5",
        created_at="2026-08-29T06:00:00Z",
        payload={
            "allowed_subject_types": ["CANDIDATE_FACT", "FORMAL_LEDGER_ITEM"],
            "authorization_modes": ["POLICY_FIXTURE_ONLY"],
            "adjacent_prose_access": "DENY",
            "plaintext_retention": "SHORT_TERM_EXPIRING",
            "revocation_effect": "IMMEDIATE_DENY_AND_PURGE",
            "expiry_effect": "DENY_AND_PURGE_AT_OR_AFTER_EXPIRY",
        },
    )


def trusted_time_records() -> list[dict[str, Any]]:
    values = [
        (1, "2026-08-29T06:01:00Z"),
        (2, "2026-08-29T06:02:00Z"),
    ]
    return [
        make_input_record(
            record_type="M3_TRUSTED_TIME_RECEIPT",
            record_id=f"time:fixture:{sequence}",
            created_at="2026-08-29T06:00:00Z",
            payload={
                "time_source_id": "fixture-clock-b03",
                "trusted_evaluation_time": time,
                "monotonic_sequence": sequence,
                "clock_mode": "DETERMINISTIC_FIXTURE",
            },
        )
        for sequence, time in values
    ]


def product_input(context: dict[str, Any]) -> dict[str, Any]:
    candidate = context["candidate_version"]
    item = candidate["payload"]["items"][0]
    return {
        "subject": {
            "kind": "CANDIDATE_FACT",
            "candidate_version_ref": record_ref(candidate),
            "lineage_locator": deepcopy(context["lineage_locators"][0]),
            "evidence_locator": deepcopy(context["evidence_locators"][0]),
            "item_hash": item["item_hash"],
            "source_revision_ref": deepcopy(
                candidate["payload"]["chapter_revision_ref"]
            ),
            "source_generation_ref": deepcopy(
                candidate["payload"]["extraction_input_binding"][
                    "accepted_source_generation_ref"
                ]
            ),
        },
        "evidence_binding": deepcopy(item["evidence_binding"]),
        "purpose": "BOUND_EVIDENCE_REVIEW",
    }
