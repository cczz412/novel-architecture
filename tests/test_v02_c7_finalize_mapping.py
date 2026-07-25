from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c7_finalize_mapping as finalizer  # noqa: E402


pytestmark = pytest.mark.v02


def _built() -> dict[str, object]:
    return {
        name: json.loads(raw.decode("utf-8"))
        for name, raw in finalizer.build_artifacts().items()
    }


def test_final_mapping_is_complete_and_source_bound() -> None:
    built = _built()
    mapping = built["final_treatment_mapping.json"]
    assert mapping["status"] == "FROZEN_V02_WORKING_TRUTH"
    assert mapping["mapping_identity"] == "working_mapping_not_gold"
    assert mapping["row_total"] == 49
    assert len({row["atom_id"] for row in mapping["rows"]}) == 49
    assert mapping["source_counts"] == {
        "AI_CONSENSUS": 24,
        "CZ_MANUAL": 2,
        "MECHANICAL_C6_UNIQUE_ROUTE": 13,
        "MECHANICAL_C7_5": 8,
        "MECHANICAL_C7_6": 2,
    }
    assert mapping["mapping_freeze_allowed"] is True
    assert mapping["c5_rescore_allowed"] is True


def test_cz_manual_rows_are_exact() -> None:
    rows = {
        row["source_detail"].get("row_id"): row
        for row in _built()["final_treatment_mapping.json"]["rows"]
        if row["mapping_source"] == "CZ_MANUAL"
    }
    assert rows["C7-010"]["candidate_event_ids"] == [
        "EV-C0041-04",
        "EV-C0041-06",
    ]
    assert rows["C7-023"]["candidate_event_ids"] == ["EV-C0033-11"]
    assert all(row["verdict_identity"] == "working_mapping_not_gold" for row in rows.values())


def test_no_correspondence_is_exclusive() -> None:
    mapping = _built()["final_treatment_mapping.json"]
    for row in mapping["rows"]:
        if row["mapping_outcome"] == "NO_CORRESPONDENCE":
            assert row["selected_choice_ids"] == ["NO_CORRESPONDENCE"]
            assert row["candidate_event_ids"] == []
            assert row["split_degree"] == 0
        else:
            assert "NO_CORRESPONDENCE" not in row["selected_choice_ids"]
            assert row["split_degree"] == len(row["candidate_event_ids"])


def test_cardinality_metrics_balance() -> None:
    metrics = _built()["treatment_cardinality_metrics.json"]
    assert metrics["produced_parent_event_total"] == 37
    assert metrics["mapped_atom_total"] == 25
    assert metrics["unmapped_atom_total"] == 24
    assert metrics["coverage_rate"] == 25 / 49
    assert metrics["atom_to_event_link_total"] == 28
    assert metrics["mapped_parent_event_total"] == 21
    assert metrics["atom_split_degree_histogram"] == {"1": 22, "2": 3}
    assert metrics["mapped_event_degree_histogram"] == {
        "1": 16,
        "2": 3,
        "3": 2,
    }
    assert (
        sum(
            int(degree) * count
            for degree, count in metrics[
                "atom_split_degree_histogram"
            ].items()
        )
        == metrics["atom_to_event_link_total"]
    )
    assert (
        sum(
            int(degree) * count
            for degree, count in metrics[
                "mapped_event_degree_histogram"
            ].items()
        )
        == metrics["atom_to_event_link_total"]
    )
    assert {
        case_id: row["mapped_atom_total"]
        for case_id, row in metrics["by_case_breakdown"].items()
    } == {
        "B02-U0039": 5,
        "B03-U0041": 7,
        "B01-U0033": 13,
    }


def test_final_outputs_do_not_emit_gold_text_or_absolute_paths() -> None:
    combined = b"\n".join(finalizer.build_artifacts().values())
    assert b'"claim"' not in combined
    assert b'"quote"' not in combined
    assert b"/Users/a1234/" not in combined
    assert b'"formal_gold_text_emitted": false' in combined


def test_double_build_and_write_are_byte_identical(tmp_path: Path) -> None:
    assert finalizer.build_artifacts() == finalizer.build_artifacts()
    output = tmp_path / "mapping"
    first = finalizer.write_or_verify(output)
    before = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    second = finalizer.write_or_verify(output)
    after = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    assert first == second
    assert before == after
