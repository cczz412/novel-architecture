from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c8_n11_floor_baselines as n11  # noqa: E402


pytestmark = pytest.mark.v02

ACTIVE_CONTROL_MAPPING = (
    n11.C8_ROOT / "control_mapping/final_control_mapping.json"
)
ACTIVE_CONTROL_FREEZE_RECEIPT = (
    n11.C8_ROOT / "control_mapping/mapping_freeze_receipt.json"
)


@pytest.fixture(autouse=True)
def _replay_historical_blocked_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """C8 用例显式回放当时“对照映射尚不存在”的历史状态。"""

    monkeypatch.setattr(
        n11,
        "CONTROL_MAPPING",
        tmp_path / "historical_missing_control_mapping.json",
    )


def _activate_control_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(n11, "CONTROL_MAPPING", ACTIVE_CONTROL_MAPPING)
    monkeypatch.setattr(
        n11,
        "CONTROL_FREEZE_RECEIPT",
        ACTIVE_CONTROL_FREEZE_RECEIPT,
    )


def _built() -> dict[str, object]:
    return {
        name: json.loads(raw.decode("utf-8"))
        for name, raw in n11.build_artifacts().items()
    }


def _synthetic_mapping(arm: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    ordinal = 0
    for case_id in n11.CASE_ORDER:
        for position in range(1, n11.CASE_DENOMINATORS[case_id] + 1):
            ordinal += 1
            atom_id = f"{case_id}-ATOM-{position:02d}"
            if arm == "treatment":
                if position % 3 == 0:
                    event_ids: list[str] = []
                elif position % 5 == 0:
                    event_ids = [
                        f"{case_id}-TE-{position:02d}-A",
                        f"{case_id}-TE-{position:02d}-B",
                    ]
                else:
                    event_ids = [f"{case_id}-TE-{position:02d}"]
            else:
                if position % 4 == 0:
                    event_ids = []
                elif position % 6 == 0:
                    event_ids = [f"{case_id}-CE-SHARED"]
                else:
                    event_ids = [f"{case_id}-CE-{position:02d}"]
            rows.append(
                {
                    "ordinal": ordinal,
                    "case_id": case_id,
                    "atom_id": atom_id,
                    "candidate_event_ids": event_ids,
                }
            )
    return {"rows": rows}


def test_actual_n11_is_blocked_without_control_mapping() -> None:
    built = _built()
    block = built["n11_block_receipt.json"]
    random_floor = built["random_alignment_floor.json"]
    seed = built["seed_receipt.json"]
    assert block["status"] == n11.BLOCKED_CONTROL
    assert block["random_trials_executed"] == 0
    assert block["five_layer_scores_fabricated"] is False
    assert random_floor["status"] == n11.BLOCKED_CONTROL
    assert random_floor["trial_count_executed"] == 0
    assert seed["root_seed_sha256"] is None


def test_empty_extraction_is_zero_coverage_not_fake_precision() -> None:
    empty = _built()["empty_extraction_floor.json"]
    assert empty["status"] == "EMPTY_EXTRACTION_MECHANICAL_FLOOR_READY"
    assert empty["effective_independent_sample_total"] == 1
    assert empty["shared_mechanical_floor"]["predicted_coverage_rate"] == 0
    assert empty["shared_mechanical_floor"]["edge_precision"] is None
    assert (
        empty["shared_mechanical_floor"]["edge_precision_status"]
        == "UNDEFINED_NO_PREDICTIONS"
    )
    assert empty["semantic_five_layer_scores_emitted"] is False


def test_trial_count_below_hard_minimum_is_rejected() -> None:
    with pytest.raises(n11.N11Error, match="至少需要 100 次"):
        n11.build_artifacts(99)


def test_seed_and_paired_permutation_are_deterministic() -> None:
    treatment = _synthetic_mapping("treatment")
    atom_sha = n11.atom_set_sha256(treatment)
    seed_one, preimage_one = n11.derive_root_seed(
        atom_set_sha=atom_sha,
        treatment_mapping_sha="1" * 64,
        control_mapping_sha="2" * 64,
        trial_count=100,
    )
    seed_two, preimage_two = n11.derive_root_seed(
        atom_set_sha=atom_sha,
        treatment_mapping_sha="1" * 64,
        control_mapping_sha="2" * 64,
        trial_count=100,
    )
    assert seed_one == seed_two
    assert preimage_one == preimage_two

    atom_cases = n11.atom_ids_by_case(treatment)
    permutation_one = n11.paired_permutation(atom_cases, seed_one, 7)
    permutation_two = n11.paired_permutation(atom_cases, seed_one, 7)
    assert permutation_one == permutation_two
    for case_id, atom_ids in atom_cases.items():
        assert {
            permutation_one[atom_id] for atom_id in atom_ids
        } == set(atom_ids)

    changed, _ = n11.derive_root_seed(
        atom_set_sha=atom_sha,
        treatment_mapping_sha="1" * 64,
        control_mapping_sha="3" * 64,
        trial_count=100,
    )
    assert changed != seed_one


def test_random_alignment_preserves_each_arm_topology_and_is_paired() -> None:
    treatment = _synthetic_mapping("treatment")
    control = _synthetic_mapping("control")
    floor, seed = n11.run_random_alignment_floors(
        treatment,
        control,
        treatment_mapping_sha="1" * 64,
        control_mapping_sha="2" * 64,
        trial_count=100,
    )
    assert floor["status"] == "RANDOM_ALIGNMENT_FLOOR_READY"
    assert floor["trial_count"] == 100
    assert floor["paired_across_arms"] is True
    assert seed["status"] == "SEED_FROZEN"
    treatment_rows = floor["arms"]["treatment"]["trial_rows"]
    control_rows = floor["arms"]["control"]["trial_rows"]
    assert len(treatment_rows) == len(control_rows) == 100
    assert [
        row["permutation_sha256"] for row in treatment_rows
    ] == [row["permutation_sha256"] for row in control_rows]

    atom_cases = n11.atom_ids_by_case(treatment)
    root_seed = seed["root_seed_sha256"]
    treatment_reference = n11.mapping_edges(treatment)
    control_reference = n11.mapping_edges(control)
    for trial_index in (0, 17, 99):
        permutation = n11.paired_permutation(
            atom_cases, root_seed, trial_index
        )
        assert n11.cardinality_signature(
            n11.permute_edges(treatment_reference, permutation)
        ) == n11.cardinality_signature(treatment_reference)
        assert n11.cardinality_signature(
            n11.permute_edges(control_reference, permutation)
        ) == n11.cardinality_signature(control_reference)


def test_nearest_rank_method_is_fixed() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert n11.nearest_rank(values, 0.05) == 1.0
    assert n11.nearest_rank(values, 0.5) == 2.0
    assert n11.nearest_rank(values, 0.95) == 4.0


def test_outputs_do_not_emit_gold_text_or_absolute_paths() -> None:
    combined = b"\n".join(n11.build_artifacts().values())
    assert b'"claim"' not in combined
    assert b'"quote"' not in combined
    assert b"/Users/a1234/" not in combined
    assert b'"formal_gold_text_emitted": false' in combined
    assert b'"semantic_five_layer_scores_emitted": false' in combined


def test_double_build_and_write_are_byte_identical(tmp_path: Path) -> None:
    assert n11.build_artifacts() == n11.build_artifacts()
    output = tmp_path / "N11"
    first = n11.write_or_verify(output)
    before = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    second = n11.write_or_verify(output)
    after = {
        path.name: path.read_bytes() for path in sorted(output.glob("*.json"))
    }
    assert first == second
    assert before == after


def test_active_control_mapping_enables_both_mechanical_floors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _activate_control_mapping(monkeypatch)
    built = {
        name: json.loads(raw.decode("utf-8"))
        for name, raw in n11.build_artifacts(100).items()
    }
    manifest = built["artifact_manifest.json"]
    random_floor = built["random_alignment_floor.json"]
    empty_floor = built["empty_extraction_floor.json"]
    activation = built["n11_activation_receipt.json"]

    assert manifest["status"] == n11.ACTIVE_BOTH_ARMS
    assert random_floor["status"] == "RANDOM_ALIGNMENT_FLOOR_READY"
    assert random_floor["trial_count"] == 100
    assert random_floor["reference_cardinality_signatures"]["control"] == {
        "edge_total": 46,
        "mapped_atom_total": 40,
        "mapped_event_total": 38,
        "split_degree_histogram": {"1": 34, "2": 6},
        "merge_degree_histogram": {"1": 30, "2": 8},
    }
    assert empty_floor["control_reference_comparison"]["status"] == (
        "EMPTY_EXTRACTION_CONTROL_COMPARISON_READY"
    )
    assert empty_floor["control_reference_comparison"]["metrics"][
        "reference_mapped_atom_total"
    ] == 40
    assert empty_floor["control_reference_comparison"]["metrics"][
        "predicted_coverage_rate"
    ] == 0
    assert activation["mapping_sha256"] == (
        n11.EXPECTED_CONTROL_MAPPING_SHA
    )
    assert activation["freeze_receipt_sha256"] == (
        n11.EXPECTED_CONTROL_FREEZE_RECEIPT_SHA
    )
    assert activation["conditional_invalidation"] == (
        n11.EXPECTED_CONDITIONAL_INVALIDATION
    )
    assert activation["semantic_five_layer_scores_emitted"] is False
    assert activation["anchor_partial_scores_emitted"] is False
    assert activation["quality_result_registered"] is False


def test_active_default_seed_is_bound_to_both_exact_mappings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _activate_control_mapping(monkeypatch)
    seed = json.loads(
        n11.build_artifacts()["seed_receipt.json"].decode("utf-8")
    )
    assert seed["root_seed_sha256"] == (
        "8cbfe1999a2f397be38b10abb303994a27f68be63a810b88ae3eed12095b010a"
    )
    assert seed["seed_preimage"]["control_mapping_sha256"] == (
        n11.EXPECTED_CONTROL_MAPPING_SHA
    )
    assert seed["human_selected_seed"] is False
    assert seed["time_based_seed"] is False


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
        n11,
        "CONTROL_MAPPING"
        if target == "mapping"
        else "CONTROL_FREEZE_RECEIPT",
        corrupt,
    )
    with pytest.raises(n11.N11Error, match="SHA 漂移"):
        n11.build_artifacts(100)


def test_active_write_requires_new_output_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _activate_control_mapping(monkeypatch)
    with pytest.raises(n11.N11Error, match="C8 历史 N11 输出只读"):
        n11.write_or_verify(n11.DEFAULT_OUTPUT_DIR, 100)

    result = n11.write_or_verify(tmp_path / "C11_N11", 100)
    assert result["status"] == n11.ACTIVE_BOTH_ARMS
    assert result["random_alignment_trial_count_executed"] == 100
