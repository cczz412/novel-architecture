from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c8_n10_reverse_outcomes as n10  # noqa: E402


pytestmark = pytest.mark.v02

ACTIVE_CONTROL_MAPPING = (
    n10.C8_ROOT / "control_mapping/final_control_mapping.json"
)
ACTIVE_CONTROL_FREEZE_RECEIPT = (
    n10.C8_ROOT / "control_mapping/mapping_freeze_receipt.json"
)


@pytest.fixture(autouse=True)
def _replay_historical_blocked_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """C8 用例显式回放当时“对照映射尚不存在”的历史状态。"""

    monkeypatch.setattr(
        n10,
        "CONTROL_MAPPING",
        tmp_path / "historical_missing_control_mapping.json",
    )


def _activate_control_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(n10, "CONTROL_MAPPING", ACTIVE_CONTROL_MAPPING)
    monkeypatch.setattr(
        n10,
        "CONTROL_FREEZE_RECEIPT",
        ACTIVE_CONTROL_FREEZE_RECEIPT,
    )


def _built() -> dict[str, object]:
    return {
        name: json.loads(raw.decode("utf-8"))
        for name, raw in n10.build_artifacts().items()
    }


def test_treatment_reverse_table_is_complete_and_balanced() -> None:
    table = _built()["treatment_reverse_table.json"]
    assert table["status"] == (
        "TREATMENT_REVERSE_TABLE_READY_REASON_GAP_OPEN"
    )
    assert table["scoring_atom_total"] == 49
    assert table["produced_event_total"] == 37
    assert table["mapped_atom_total"] == 25
    assert table["unmapped_atom_total"] == 24
    assert table["mapped_output_event_total"] == 21
    assert table["unmapped_output_event_total"] == 16
    assert table["atom_to_event_link_total"] == 28
    assert table["forward_reverse_edges_equal"] is True

    forward = {
        (row["case_id"], row["atom_id"], event_id)
        for row in table["atom_rows"]
        for event_id in row["mapped_event_ids"]
    }
    reverse = {
        (row["case_id"], atom_id, row["event_id"])
        for row in table["event_rows"]
        for atom_id in row["mapped_atom_ids"]
    }
    assert forward == reverse


def test_n_to_one_and_one_to_many_are_preserved() -> None:
    table = _built()["treatment_reverse_table.json"]
    event_rows = {
        (row["case_id"], row["event_id"]): row
        for row in table["event_rows"]
    }
    atom_rows = {
        row["atom_id"]: row for row in table["atom_rows"]
    }
    assert event_rows[("B01-U0033", "EV-C0033-13")]["atom_count"] == 3
    assert atom_rows["Z74B-B03-U0041-A08"]["mapped_event_ids"] == [
        "EV-C0041-04",
        "EV-C0041-06",
    ]


def test_no_correspondence_does_not_guess_semantic_reason() -> None:
    built = _built()
    table = built["treatment_reverse_table.json"]
    gap = built["unmatched_reason_gap.json"]
    assert gap["status"] == "MISSING_UNMATCHED_REASON_VERDICTS"
    assert gap["gap_total"] == 24
    assert table["semantic_unmatched_reason_counts"] == {
        "MISSING_UNMATCHED_REASON": 24,
        "OMISSION": 0,
        "POSITION_NO_CANDIDATE": 0,
        "SEMANTIC_MISMATCH": 0,
    }
    assert table["unmapped_atom_mechanical_route_status_counts"] == {
        "NO_POSITION_ROUTE": 24
    }
    assert all(
        row["semantic_unmatched_reason"] == n10.MISSING_REASON
        for row in table["atom_rows"]
        if row["mapping_outcome"] == "NO_CORRESPONDENCE"
    )
    assert all(
        row["automatic_inference_forbidden"] is True for row in gap["rows"]
    )


def test_control_reverse_table_is_explicitly_blocked() -> None:
    built = _built()
    control = built["control_reverse_table.json"]
    receipt = built["control_mapping_block_receipt.json"]
    assert control["status"] == n10.BLOCKED_CONTROL
    assert control["mapping_file_exists"] is False
    assert control["reverse_table_generated"] is False
    assert control["mechanical_routes_counted_as_semantic_mapping"] is False
    assert receipt["status"] == n10.BLOCKED_CONTROL
    assert receipt["quality_result_registered"] is False


def test_outputs_do_not_emit_gold_text_or_absolute_paths() -> None:
    combined = b"\n".join(n10.build_artifacts().values())
    assert b'"claim"' not in combined
    assert b'"quote"' not in combined
    assert b"/Users/a1234/" not in combined
    assert b'"formal_gold_text_emitted": false' in combined


def test_double_build_and_write_are_byte_identical(tmp_path: Path) -> None:
    assert n10.build_artifacts() == n10.build_artifacts()
    output = tmp_path / "N10"
    first = n10.write_or_verify(output)
    before = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    second = n10.write_or_verify(output)
    after = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    assert first == second
    assert before == after


def test_active_control_mapping_builds_both_directions_without_guessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _activate_control_mapping(monkeypatch)
    built = {
        name: json.loads(raw.decode("utf-8"))
        for name, raw in n10.build_artifacts().items()
    }
    manifest = built["artifact_manifest.json"]
    control = built["control_reverse_table.json"]
    control_gap = built["control_unmatched_reason_gap.json"]
    activation = built["control_mapping_activation_receipt.json"]

    assert manifest["status"] == n10.ACTIVE_BOTH_ARMS
    assert control["status"] == (
        "CONTROL_REVERSE_TABLE_READY_REASON_GAP_OPEN"
    )
    assert control["scoring_atom_total"] == 49
    assert control["produced_event_total"] == 129
    assert control["mapped_atom_total"] == 40
    assert control["unmapped_atom_total"] == 9
    assert control["mapped_output_event_total"] == 38
    assert control["atom_to_event_link_total"] == 46
    assert control["forward_reverse_edges_equal"] is True
    assert control_gap["gap_total"] == 9
    assert all(
        row["semantic_unmatched_reason"] == n10.MISSING_REASON
        for row in control["atom_rows"]
        if row["mapping_outcome"] == "NO_CORRESPONDENCE"
    )
    assert all(
        row["automatic_inference_forbidden"] is True
        for row in control_gap["rows"]
    )
    assert activation["mapping_sha256"] == n10.EXPECTED_SHAS[
        "control_mapping"
    ]
    assert activation["freeze_receipt_sha256"] == n10.EXPECTED_SHAS[
        "control_freeze_receipt"
    ]
    assert activation["mapping_identity"] == "working_mapping_not_gold"
    assert activation["conditional_invalidation"] == (
        n10.EXPECTED_CONDITIONAL_INVALIDATION
    )
    assert activation["semantic_unmatched_reasons_inferred"] is False


@pytest.mark.parametrize("target", ["mapping", "receipt"])
def test_active_control_requires_both_exact_pins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: str,
) -> None:
    _activate_control_mapping(monkeypatch)
    corrupt = tmp_path / f"corrupt_{target}.json"
    source = (
        ACTIVE_CONTROL_MAPPING
        if target == "mapping"
        else ACTIVE_CONTROL_FREEZE_RECEIPT
    )
    corrupt.write_bytes(source.read_bytes() + b"\n")
    monkeypatch.setattr(
        n10,
        "CONTROL_MAPPING"
        if target == "mapping"
        else "CONTROL_FREEZE_RECEIPT",
        corrupt,
    )
    with pytest.raises(n10.N10Error, match="SHA 漂移"):
        n10.build_artifacts()


def test_active_write_requires_new_output_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _activate_control_mapping(monkeypatch)
    with pytest.raises(n10.N10Error, match="C8 历史 N10 输出只读"):
        n10.write_or_verify(n10.DEFAULT_OUTPUT_DIR)

    result = n10.write_or_verify(tmp_path / "C11_N10")
    assert result["status"] == n10.ACTIVE_BOTH_ARMS
    assert result["control_mapped_atom_total"] == 40
    assert result["control_missing_unmatched_reason_total"] == 9
