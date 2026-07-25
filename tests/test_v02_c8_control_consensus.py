from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c8_control_consensus as c8  # noqa: E402


pytestmark = pytest.mark.v02


def _copy_second_vote(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    document = json.loads(c8.SECOND_VOTE.read_text(encoding="utf-8"))
    path = tmp_path / "second_vote.json"
    return path, document


def _write_vote(path: Path, document: dict[str, object]) -> None:
    path.write_bytes(c8.canonical_bytes(document))


def _bind_mutated_second_vote(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
) -> None:
    monkeypatch.setattr(c8, "SECOND_VOTE", path)
    monkeypatch.setattr(
        c8,
        "EXPECTED_SECOND_VOTE_SHA256",
        c8.sha256_file(path),
    )


def _build_with_verified_public(
    tmp_path: Path,
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    public, context = c8._build_public_preunblind_phase()
    public_dir = tmp_path / "verified_public"
    c8._write_artifacts(public_dir, public)
    verified = c8._verify_public_preunblind_files(public_dir, public)
    return c8._build_private_unblind_phase(context, verified)


def _target_all_agree(document: dict[str, object]) -> None:
    first = json.loads(c8.FIRST_VOTE.read_text(encoding="utf-8"))
    first_by_packet = {
        row["packet_id"]: row["selected_choice_ids"]
        for row in first["votes"]
    }
    for row in document["votes"]:
        if row["packet_id"] == "C8-BLIND-018":
            row["selected_choice_ids"] = first_by_packet["C8-BLIND-018"]


def test_current_votes_tally_before_unblind_and_block_target_disagreement(
    tmp_path: Path,
) -> None:
    consensus, control = _build_with_verified_public(tmp_path)
    visible = json.loads(consensus["visible_tally.json"])
    unblinded = json.loads(consensus["unblinded_tally_private.json"])
    queue = json.loads(consensus["target_disagreement_queue_private.json"])
    gate = json.loads(consensus["control_mapping_gate_receipt.json"])

    assert visible["packet_total"] == 27
    assert visible["agreement_total"] == 26
    assert visible["disagreement_total"] == 1
    assert visible["private_crosswalk_opened_before_tally"] is False
    assert unblinded["access_order"] == [
        "PUBLIC_PREPARATION_BOUND",
        "FIRST_VOTE_VALIDATED",
        "SECOND_VOTE_VALIDATED",
        "VISIBLE_TALLY_FROZEN",
        "PRIVATE_CROSSWALK_OPENED",
        "UNBLIND_COMPLETE",
    ]
    assert unblinded["target_agreement_total"] == 20
    assert unblinded["target_disagreement_total"] == 1
    assert unblinded["audit_agreement_total"] == 6
    assert queue["row_total"] == 1
    assert queue["rows"][0]["packet_id"] == "C8-BLIND-018"
    assert queue["rows"][0]["source_row_id"] == "C8-R036"
    assert queue["rows"][0]["atom_id"] == "Z74B-B01-U0033-A09"
    assert gate["status"] == "BLOCKED_TARGET_DISAGREEMENT"
    assert gate["mapping_freeze_allowed"] is False
    assert gate["final_control_mapping_generated"] is False
    assert control == {}
    assert not (
        c8.DEFAULT_CONTROL_MAPPING_DIR / "final_control_mapping.json"
    ).exists()


def test_visible_tally_contains_no_private_role_or_real_event_identity(
    tmp_path: Path,
) -> None:
    consensus, _control = _build_with_verified_public(tmp_path)
    visible = consensus["visible_tally.json"].decode("utf-8")
    for forbidden in (
        "EV-C",
        '"S1"',
        '"S2"',
        '"atom_id"',
        '"case_id"',
        '"source_row_id"',
        '"source_packet_id"',
        "control",
        "treatment",
    ):
        assert forbidden not in visible


def test_invalid_vote_is_rejected_before_private_crosswalk_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_path, document = _copy_second_vote(tmp_path)
    document["votes"][0]["selected_choice_ids"] = ["MAP_TO::NOT_ALLOWED"]
    _write_vote(second_path, document)
    _bind_mutated_second_vote(monkeypatch, second_path)

    original_read_json = c8.read_json
    observed_paths: list[Path] = []

    def recording_read(path: Path) -> object:
        observed_paths.append(path.resolve())
        return original_read_json(path)

    monkeypatch.setattr(c8, "read_json", recording_read)
    with pytest.raises(c8.C8ConsensusError, match="选项非法"):
        c8.build_artifact_sets()
    private_paths = {
        c8.PRIVATE_CROSSWALK.resolve(),
        c8.PRIVATE_PREFREEZE.resolve(),
        c8.PRIVATE_LEDGER.resolve(),
        c8.PRIVATE_QUEUE.resolve(),
        c8.PRIVATE_AUDIT_PLAN.resolve(),
    }
    assert private_paths.isdisjoint(observed_paths)


def test_vote_choice_order_is_part_of_frozen_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_path, document = _copy_second_vote(tmp_path)
    row = next(
        row
        for row in document["votes"]
        if len(row["selected_choice_ids"]) == 2
    )
    row["selected_choice_ids"] = list(reversed(row["selected_choice_ids"]))
    _write_vote(second_path, document)
    _bind_mutated_second_vote(monkeypatch, second_path)
    with pytest.raises(c8.C8ConsensusError, match="顺序漂移"):
        c8.build_artifact_sets()


def test_second_vote_must_bind_first_vote_sha_without_reading_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_path, document = _copy_second_vote(tmp_path)
    document["first_vote_sha256"] = "0" * 64
    document["first_ballot_sha256_seen_only"] = "0" * 64
    _write_vote(second_path, document)
    _bind_mutated_second_vote(monkeypatch, second_path)
    with pytest.raises(c8.C8ConsensusError, match="只读绑定第一票 SHA"):
        c8.build_artifact_sets()

    document["first_vote_sha256"] = c8.EXPECTED_FIRST_VOTE_SHA256
    document["first_ballot_sha256_seen_only"] = (
        c8.EXPECTED_FIRST_VOTE_SHA256
    )
    document["first_vote_content_read"] = True
    _write_vote(second_path, document)
    monkeypatch.setattr(
        c8,
        "EXPECTED_SECOND_VOTE_SHA256",
        c8.sha256_file(second_path),
    )
    with pytest.raises(c8.C8ConsensusError, match="已读取票面"):
        c8.build_artifact_sets()


def test_second_vote_sha_drift_is_rejected_before_private_unblind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_path = tmp_path / "second_vote.json"
    second_path.write_bytes(c8.SECOND_VOTE.read_bytes() + b"\n")
    monkeypatch.setattr(c8, "SECOND_VOTE", second_path)

    original_read_json = c8.read_json
    observed_paths: list[Path] = []

    def recording_read(path: Path) -> object:
        observed_paths.append(path.resolve())
        return original_read_json(path)

    monkeypatch.setattr(c8, "read_json", recording_read)
    with pytest.raises(c8.C8ConsensusError, match="second_vote.json"):
        c8.build_artifact_sets()
    assert c8.PRIVATE_CROSSWALK.resolve() not in observed_paths
    assert c8.PRIVATE_AUDIT_PLAN.resolve() not in observed_paths


def test_visible_tally_seal_rejects_tamper_before_private_unblind(
    tmp_path: Path,
) -> None:
    public, _context = c8._build_public_preunblind_phase()
    c8._write_artifacts(tmp_path, public)
    visible_path = tmp_path / "visible_tally.json"
    visible_path.write_bytes(visible_path.read_bytes() + b"\n")

    with pytest.raises(c8.C8ConsensusError, match="公开工件未落盘或漂移"):
        c8._verify_public_preunblind_files(tmp_path, public)


def test_hidden_audit_sample_rejects_seed_or_source_row_drift() -> None:
    private = c8._private_documents(
        c8._manifest_index(c8.read_json(c8.PREPARATION_MANIFEST))
    )
    crosswalk_rows = private["crosswalk"]["rows"]
    bad_seed = dict(private["audit_plan"])
    bad_seed["seed"] = "DRIFTED-SEED"
    with pytest.raises(c8.C8ConsensusError, match="原种子"):
        c8._validated_audit_sampling_receipt(bad_seed, crosswalk_rows)

    bad_crosswalk = [dict(row) for row in crosswalk_rows]
    audit_rows = [
        row
        for row in bad_crosswalk
        if row["private_source_set"] == c8.AUDIT_SOURCE_SET
    ]
    audit_rows[0]["source_packet_id"] = audit_rows[1]["source_packet_id"]
    with pytest.raises(c8.C8ConsensusError, match="源行不完整"):
        c8._validated_audit_sampling_receipt(
            private["audit_plan"],
            bad_crosswalk,
        )


def test_write_persists_public_seals_before_any_private_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consensus_dir = tmp_path / "consensus"
    original_private_documents = c8._private_documents

    def guarded_private_documents(
        manifest_index: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        for relative in (
            "second_vote_preunblind_seal.json",
            "visible_tally.json",
            "visible_tally_preunblind_seal.json",
        ):
            assert (consensus_dir / relative).is_file()
        c8._verify_public_preunblind_files(
            consensus_dir,
            {
                relative: (consensus_dir / relative).read_bytes()
                for relative in (
                    "second_vote_preunblind_seal.json",
                    "visible_tally.json",
                    "visible_tally_preunblind_seal.json",
                )
            },
        )
        return original_private_documents(manifest_index)

    monkeypatch.setattr(c8, "_private_documents", guarded_private_documents)
    receipt = c8.write_or_verify(
        consensus_dir=consensus_dir,
        control_mapping_dir=tmp_path / "control_mapping",
    )
    assert receipt["target_disagreement_total"] == 1
    assert receipt["mapping_freeze_executed"] is False
    assert not (tmp_path / "control_mapping").exists()


def test_forced_public_verify_failure_cannot_read_private_or_emit_source_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consensus_dir = tmp_path / "consensus"
    private_read_total = 0

    def forced_verify_failure(
        output_dir: Path,
        expected_artifacts: dict[str, bytes],
    ) -> object:
        del output_dir, expected_artifacts
        raise c8.C8ConsensusError("FORCED_PUBLIC_VERIFY_FAILURE")

    def forbidden_private_read(
        manifest_index: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        nonlocal private_read_total
        del manifest_index
        private_read_total += 1
        raise AssertionError("公开验证失败后不应读取私有件")

    monkeypatch.setattr(
        c8,
        "_verify_public_preunblind_files",
        forced_verify_failure,
    )
    monkeypatch.setattr(c8, "_private_documents", forbidden_private_read)
    with pytest.raises(
        c8.C8ConsensusError,
        match="FORCED_PUBLIC_VERIFY_FAILURE",
    ):
        c8.write_or_verify(
            consensus_dir=consensus_dir,
            control_mapping_dir=tmp_path / "control_mapping",
        )
    assert private_read_total == 0
    assert not (consensus_dir / "source_receipt.json").exists()
    assert not (tmp_path / "control_mapping").exists()


def test_read_only_build_cannot_bypass_missing_public_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_read_total = 0

    def forbidden_private_read(
        manifest_index: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        nonlocal private_read_total
        del manifest_index
        private_read_total += 1
        raise AssertionError("缺公开落盘件时不应读取私有件")

    monkeypatch.setattr(c8, "_private_documents", forbidden_private_read)
    with pytest.raises(c8.C8ConsensusError, match="公开工件未落盘"):
        c8.build_artifact_sets(tmp_path / "missing_public")
    assert private_read_total == 0


def test_voter_and_model_family_must_both_be_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = json.loads(c8.FIRST_VOTE.read_text(encoding="utf-8"))
    second_path, document = _copy_second_vote(tmp_path)
    document["model_family"] = first["model_family"]
    _write_vote(second_path, document)
    _bind_mutated_second_vote(monkeypatch, second_path)
    with pytest.raises(c8.C8ConsensusError, match="model_family 相同"):
        c8.build_artifact_sets()


def test_all_21_target_agreements_generate_49_row_control_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_path, document = _copy_second_vote(tmp_path)
    _target_all_agree(document)
    _write_vote(second_path, document)
    _bind_mutated_second_vote(monkeypatch, second_path)
    consensus, control = _build_with_verified_public(tmp_path)

    gate = json.loads(consensus["control_mapping_gate_receipt.json"])
    mapping = json.loads(control["final_control_mapping.json"])
    metrics = json.loads(control["control_cardinality_metrics.json"])
    assert gate["target_agreement_total"] == 21
    assert gate["target_disagreement_total"] == 0
    assert gate["mapping_freeze_allowed"] is True
    assert gate["final_control_mapping_generated"] is True
    assert mapping["status"] == "FROZEN_V02_WORKING_TRUTH"
    assert mapping["row_total"] == 49
    assert mapping["source_counts"] == {
        "AI_CONSENSUS": 21,
        "MECHANICAL_C6_UNIQUE_ROUTE": 17,
        "MECHANICAL_C7_5_SINGLE_CANDIDATE": 11,
    }
    assert metrics["produced_parent_event_total"] == 129
    assert metrics["scoring_atom_total"] == 49
    assert (
        metrics["mapped_atom_total"] + metrics["unmapped_atom_total"] == 49
    )
    assert metrics["atom_to_event_link_total"] >= metrics["mapped_atom_total"]


def test_hidden_audit_disagreement_only_makes_consistency_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_sha = c8.sha256_file(c8.TREATMENT_MAPPING)
    second_path, document = _copy_second_vote(tmp_path)
    _target_all_agree(document)
    packet = json.loads(
        (
            c8.PREPARATION_DIR
            / "blind_packets/C8-BLIND-004.json"
        ).read_text(encoding="utf-8")
    )
    legal_non_no = packet["choices"][0]["choice_id"]
    row = next(
        row
        for row in document["votes"]
        if row["packet_id"] == "C8-BLIND-004"
    )
    row["selected_choice_ids"] = [legal_non_no]
    _write_vote(second_path, document)
    _bind_mutated_second_vote(monkeypatch, second_path)
    consensus, control = _build_with_verified_public(tmp_path)

    gate = json.loads(consensus["control_mapping_gate_receipt.json"])
    audit = json.loads(consensus["audit_bias_receipt.json"])
    assert gate["target_disagreement_total"] == 0
    assert gate["audit_disagreement_total"] == 1
    assert gate["mapping_freeze_allowed"] is True
    assert "final_control_mapping.json" in control
    assert audit["status"] == "MISSING_VOTER_DISAGREEMENT"
    assert audit["consistency_rate"] is None
    assert audit["treatment_mapping_write_total"] == 0
    assert c8.sha256_file(c8.TREATMENT_MAPPING) == before_sha


def test_current_audit_consistency_is_six_of_six_without_rewrite(
    tmp_path: Path,
) -> None:
    consensus, _control = _build_with_verified_public(tmp_path)
    audit = json.loads(consensus["audit_bias_receipt.json"])
    assert audit["status"] == "AVAILABLE_C9_REVALIDATED"
    assert audit["audit_packet_total"] == 6
    assert audit["audit_voter_disagreement_total"] == 0
    assert audit["matches_old_working_mapping_total"] == 6
    assert audit["consistency_rate"] == 1.0
    assert audit["old_c8_six_of_six_treated_as_observation_only"] is True
    sampling = json.loads(
        consensus["audit_sampling_validation_private.json"]
    )
    assert sampling["status"] == "PASS_RECOMPUTED_FROM_FROZEN_MOTHER_SET"
    assert sampling["selected_source_row_ids"] == list(
        c8.EXPECTED_AUDIT_SOURCE_ROW_IDS
    )
    assert audit["treatment_mapping_read_only"] is True
    assert audit["treatment_mapping_write_total"] == 0


def test_build_is_deterministic_and_matches_written_consensus(
    tmp_path: Path,
) -> None:
    consensus_dir = tmp_path / "consensus"
    receipt = c8.write_or_verify(
        consensus_dir=consensus_dir,
        control_mapping_dir=tmp_path / "control_mapping",
    )
    assert receipt["mapping_freeze_executed"] is False
    first, first_control = c8.build_artifact_sets(consensus_dir)
    second, second_control = c8.build_artifact_sets(consensus_dir)
    assert first == second
    assert first_control == second_control == {}
    for relative, raw in first.items():
        assert (consensus_dir / relative).read_bytes() == raw
