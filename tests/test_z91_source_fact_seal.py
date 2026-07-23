from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z91_source_fact_seal.py"
SPEC = importlib.util.spec_from_file_location("z91_source_fact_seal", MODULE_PATH)
assert SPEC and SPEC.loader
z91 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z91)


FACT_DIR = ROOT / (
    "runs/Z91_双臂跨书基线_步二双臂_v1.0_20260723/review/source_facts"
)


def test_committed_source_fact_seal_rebuilds() -> None:
    result = z91.audit_documents(FACT_DIR)
    assert result["status"] == "pass"
    assert result["probe_count"] == 18
    assert result["disagreement_field_count"] > 0


def test_adjudication_only_lists_differing_fields() -> None:
    reviewer_a = json.loads((FACT_DIR / "reviewer_A.json").read_text(encoding="utf-8"))
    reviewer_b = json.loads((FACT_DIR / "reviewer_B.json").read_text(encoding="utf-8"))
    rows = json.loads((FACT_DIR / "field_adjudication.json").read_text(encoding="utf-8"))["rows"]
    by_a = {row["probe_id"]: row for row in reviewer_a["items"]}
    by_b = {row["probe_id"]: row for row in reviewer_b["items"]}
    for row in rows:
        field = row["field_path"].removeprefix("/")
        assert by_a[row["probe_id"]][field] != by_b[row["probe_id"]][field]


def test_reviewer_declaring_output_visibility_is_rejected() -> None:
    document = json.loads((FACT_DIR / "reviewer_A.json").read_text(encoding="utf-8"))
    document["dual_arm_outputs_read"] = True
    with pytest.raises(z91.SourceFactSealError, match="独立声明"):
        z91.validate_reviewer(document, "A")
