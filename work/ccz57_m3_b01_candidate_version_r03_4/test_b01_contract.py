"""Targeted B-01 contract tests. All inputs are synthetic and offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from b01_contract import (
    B01ContractError,
    B01Service,
    CandidatePointerSnapshotWriter,
    CandidateVersionStore,
    FixtureStore,
    SegmentIndexSnapshotWriter,
    VersionDiffProjector,
    canonical_bytes,
    state_counts,
    state_file_hash,
)
from fixtures import (
    FAILURE_SCENARIOS,
    NORMAL_SCENARIOS,
    base_request,
    canonical_fixture_vector,
    run_failure_scenario,
    run_normal_scenario,
)


@pytest.mark.parametrize("scenario_name", sorted(NORMAL_SCENARIOS))
def test_normal_fixture_family(scenario_name: str, tmp_path: Path) -> None:
    result = run_normal_scenario(scenario_name, tmp_path / scenario_name)
    assert result


@pytest.mark.parametrize("scenario_name", sorted(FAILURE_SCENARIOS))
def test_failure_fixture_family_is_fail_closed(
    scenario_name: str, tmp_path: Path
) -> None:
    codes = run_failure_scenario(scenario_name, tmp_path / scenario_name)
    assert codes
    assert all(code.startswith("B01_") for code in codes)


@pytest.mark.parametrize(
    "crash_point",
    [
        "before_staging",
        "after_records_staged_before_pointer_cas",
        "after_pointer_staged_before_commit",
    ],
)
def test_precommit_crash_leaves_zero_visible_state(
    crash_point: str, tmp_path: Path
) -> None:
    root = tmp_path / crash_point
    request = base_request()
    request["crash_point"] = crash_point
    with pytest.raises(B01ContractError, match="B01_SIMULATED_CRASH"):
        B01Service(FixtureStore(root)).initialize_root_baseline(**request)
    assert state_counts(root / "state.json") == (0, 0, 0)
    assert state_file_hash(root / "state.json") is None


def test_after_commit_crash_reopens_as_complete_transaction(tmp_path: Path) -> None:
    root = tmp_path / "after-commit"
    request = base_request()
    request["crash_point"] = "after_commit_before_readback"
    with pytest.raises(B01ContractError, match="B01_SIMULATED_CRASH_AFTER_COMMIT"):
        B01Service(FixtureStore(root)).initialize_root_baseline(**request)
    assert state_counts(root / "state.json") == (3, 1, 1)


def test_fixture_store_contains_only_contract_outputs(tmp_path: Path) -> None:
    root = tmp_path / "outputs"
    run_normal_scenario("N01_NONEMPTY_BASELINE", root)
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert {record["record_type"] for record in state["records"].values()} == {
        "M3_SEGMENT_INDEX_SNAPSHOT",
        "M3_CANDIDATE_VERSION",
        "M3_CANDIDATE_POINTER_SNAPSHOT",
    }
    assert len(state["pointers"]) == 1


def test_unique_writer_and_projector_surface_is_fixed() -> None:
    assert [
        SegmentIndexSnapshotWriter.__name__,
        CandidateVersionStore.__name__,
        CandidatePointerSnapshotWriter.__name__,
        VersionDiffProjector.__name__,
    ] == [
        "SegmentIndexSnapshotWriter",
        "CandidateVersionStore",
        "CandidatePointerSnapshotWriter",
        "VersionDiffProjector",
    ]


def test_canonical_json_is_nfc_compact_and_stable() -> None:
    vector = canonical_fixture_vector()
    assert bytes.fromhex(vector["canonical_utf8_hex"]) == canonical_bytes(
        {"z": "é", "a": [3, True, None, "synthetic"]}
    )
    assert len(vector["sha256"]) == 64


def test_only_fixture_pointer_namespace_can_be_written(tmp_path: Path) -> None:
    request = base_request()
    request["pointer_namespace"] = "PRODUCT"
    with pytest.raises(B01ContractError, match="B01_POINTER_SCOPE_MISMATCH"):
        B01Service(FixtureStore(tmp_path)).initialize_root_baseline(**request)
    assert state_counts(tmp_path / "state.json") == (0, 0, 0)


def test_runtime_event_evidence_contains_no_forbidden_event(tmp_path: Path) -> None:
    store = FixtureStore(tmp_path)
    B01Service(store).initialize_root_baseline(**base_request())
    assert set(store.events) <= {
        "fixture_storage_read",
        "fixture_storage_atomic_replace",
    }
