from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import v02_c8_control_workspace as c8  # noqa: E402


pytestmark = pytest.mark.v02


def _built() -> dict[str, bytes]:
    return c8.build_artifacts()


def _loaded(name: str) -> dict[str, object]:
    return json.loads(_built()[name])


def test_c8_build_is_deterministic_zero_call_and_not_final() -> None:
    first = _built()
    second = _built()
    assert first == second
    gate = json.loads(first["preparation_gate.json"])
    assert gate == {
        "c5_rescore_allowed": False,
        "decision_rule_exact_copy": True,
        "decision_rule_sha256": c8.DECISION_RULE_SHA256,
        "hidden_audit_packet_total": 6,
        "mapping_freeze_allowed": False,
        "mechanical_prefreeze_total": 28,
        "mixed_blind_packet_total": 27,
        "model_api_calls": 0,
        "network_requests": 0,
        "old_source_write_total": 0,
        "real_event_alias_private": True,
        "route_row_total": 49,
        "schema_version": "v02-c8-preparation-gate.v1",
        "source_lock_pass": True,
        "status": "PASS_PREPARATION_ONLY_PENDING_TWO_VOTES",
        "target_blind_review_total": 21,
        "visible_role_label_hits": 0,
    }


def test_c8_route_ledger_has_17_plus_11_prefreeze_and_21_pending() -> None:
    ledger = _loaded("route_ledger_private.json")
    assert ledger["row_total"] == 49
    assert ledger["counts"] == {
        "blind_multiple_position_candidates": 13,
        "blind_no_position": 8,
        "blind_review_total": 21,
        "c6_unique": 17,
        "c7_5_single_candidate": 11,
        "mechanical_prefreeze_total": 28,
    }
    rows = ledger["rows"]
    assert len(rows) == 49
    assert len({row["atom_id"] for row in rows}) == 49
    assert sum(
        row["mapping_source"] == "MECHANICAL_C6_UNIQUE_ROUTE"
        for row in rows
    ) == 17
    c75_rows = [
        row
        for row in rows
        if row["mapping_source"]
        == "MECHANICAL_C7_5_SINGLE_CANDIDATE"
    ]
    assert len(c75_rows) == 11
    assert all(
        row["position_candidate_degree"] == 1
        and len(row["selected_event_ids"]) == 1
        for row in c75_rows
    )
    pending = [
        row for row in rows if row["blind_review_reason"] is not None
    ]
    assert len(pending) == 21
    assert sum(
        row["blind_review_reason"] == "MULTIPLE_POSITION_CANDIDATES"
        for row in pending
    ) == 13
    assert sum(
        row["blind_review_reason"] == "NO_POSITION_ROUTE"
        for row in pending
    ) == 8


def test_c8_true_multiple_candidates_are_not_silently_auto_selected() -> None:
    ledger = _loaded("route_ledger_private.json")
    rows = {
        row["atom_id"]: row
        for row in ledger["rows"]
        if row["blind_review_reason"] == "MULTIPLE_POSITION_CANDIDATES"
    }
    assert len(rows) == 13
    assert rows["Z74B-B02-U0039-A01"][
        "blind_review_event_ids"
    ] == ["EV-C0039-10", "EV-C0039-11"]
    assert rows["Z74B-B01-U0033-A02"][
        "blind_review_event_ids"
    ] == ["EV-C0033-13", "EV-C0033-42"]
    assert all(row["selected_event_ids"] == [] for row in rows.values())
    assert all(row["mapping_source"] is None for row in rows.values())


def test_c8_c7_5_single_candidate_rows_are_exact() -> None:
    ledger = _loaded("route_ledger_private.json")
    observed = {
        row["atom_id"]: row["selected_event_ids"]
        for row in ledger["rows"]
        if row["mapping_source"]
        == "MECHANICAL_C7_5_SINGLE_CANDIDATE"
    }
    assert observed == {
        "Z74B-B01-U0033-A03-R01": ["EV-C0033-42"],
        "Z74B-B01-U0033-A03-R02": ["EV-C0033-42"],
        "Z74B-B01-U0033-A05-R01": ["EV-C0033-15"],
        "Z74B-B01-U0033-A05-R02": ["EV-C0033-15"],
        "Z74B-B01-U0033-A10-R01": ["EV-C0033-61"],
        "Z74B-B01-U0033-A10-R02": ["EV-C0033-61"],
        "Z74B-B01-U0033-A11-R01": ["EV-C0033-50"],
        "Z74B-B01-U0033-A11-R02": ["EV-C0033-50"],
        "Z74B-B01-U0033-A15": ["EV-C0033-67"],
        "Z74B-B01-U0033-A16": ["EV-C0033-68"],
        "Z74B-B01-U0033-A17-R02": ["EV-C0033-70"],
    }


def test_c8_visible_packets_use_private_aliases_and_exact_c7_rule() -> None:
    built = _built()
    manifest = json.loads(built["blind_packet_manifest.json"])
    assert manifest["packet_total"] == 27
    assert manifest["decision_rule_sha256"] == c8.DECISION_RULE_SHA256
    private = json.loads(built["event_alias_crosswalk_private.json"])
    aliases = private["aliases"]
    assert private["reversible"] is True
    assert private["collision_total"] == 0
    assert len({row["alias_id"] for row in aliases}) == len(aliases)
    real_event_ids = [row["real_event_id"] for row in aliases]
    for row in manifest["packets"]:
        packet = json.loads(built[row["packet_path"]])
        assert packet["packet_id"] == row["packet_id"]
        assert packet["decision_rule"] == c8.DECISION_RULE
        assert (
            hashlib.sha256(packet["decision_rule"].encode()).hexdigest()
            == c8.DECISION_RULE_SHA256
        )
        assert packet["choices"][-1] == {
            "candidate_event_text": None,
            "choice_id": "NO_CORRESPONDENCE",
        }
        for choice in packet["choices"][:-1]:
            assert choice["choice_id"].startswith("MAP_TO::OPT-")
            assert "EV-C" not in choice["choice_id"]
    ticket = c8.assert_model_visible_safe(built, real_event_ids)
    assert ticket["status"] == "PASS"
    assert ticket["real_event_id_hits"] == 0
    assert ticket["source_role_label_hits"] == 0
    assert ticket["run_directory_hits"] == 0


def test_c8_private_crosswalk_hides_21_plus_6_roles_from_visible_manifest() -> None:
    built = _built()
    crosswalk = json.loads(
        built["packet_source_crosswalk_private.json"]
    )
    assert crosswalk["packet_total"] == 27
    assert crosswalk["source_set_counts"] == {"S1": 21, "S2": 6}
    assert crosswalk["visible_role_label_emitted"] is False
    visible = built["blind_packet_manifest.json"].decode("utf-8")
    for forbidden in (
        '"private_source_set"',
        '"case_id"',
        '"atom_id"',
        '"source_row_id"',
        '"source_packet_id"',
        "control",
        "treatment",
        "runs/",
        "EV-C",
    ):
        assert forbidden not in visible


def test_c8_audit_sample_is_fixed_sha_ranked_six_from_c7_26() -> None:
    plan = _loaded("audit_sampling_plan_private.json")
    assert plan["mother_packet_total"] == 26
    assert plan["sample_total"] == 6
    assert plan["roles_visible_to_voters"] is False
    ranked = plan["ranked_mother_set"]
    assert len(ranked) == 26
    recomputed = sorted(
        ranked,
        key=lambda row: (
            hashlib.sha256(
                (
                    f"{c8.AUDIT_SAMPLE_SEED}\0{row['packet_id']}"
                ).encode()
            ).hexdigest(),
            row["packet_id"],
        ),
    )
    assert ranked == recomputed
    assert plan["selected_source_packet_ids"] == [
        "C7-001",
        "C7-006",
        "C7-007",
        "C7-017",
        "C7-018",
        "C7-029",
    ]
    selected = {row["packet_id"] for row in ranked[:6]}
    assert selected == set(plan["selected_source_packet_ids"])


def test_c8_rejects_source_sha_or_decision_rule_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        c8.EXPECTED_INPUT_SHAS,
        "c7_5_policy",
        "0" * 64,
    )
    with pytest.raises(c8.C8WorkspaceError, match="SHA 漂移"):
        c8.build_artifacts()
    monkeypatch.undo()
    monkeypatch.setattr(c8, "DECISION_RULE", "漂移后的规则")
    with pytest.raises(c8.C8WorkspaceError, match="判定规则漂移"):
        c8.build_artifacts()


def test_c8_leakage_gate_rejects_real_event_or_source_label() -> None:
    built = _built()
    contaminated = dict(built)
    contaminated["blind_packets/C8-BLIND-001.json"] = (
        b'{"choice_id":"MAP_TO::EV-C0039-01","label":"control"}\n'
    )
    with pytest.raises(c8.C8WorkspaceError, match="泄漏"):
        c8.assert_model_visible_safe(
            contaminated,
            ["EV-C0039-01"],
        )


def test_c8_write_is_byte_stable_and_rejects_unregistered_files(
    tmp_path: Path,
) -> None:
    output = tmp_path / "preparation"
    first = c8.write_or_verify(output)
    before = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    second = c8.write_or_verify(output)
    after = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    assert first == second
    assert before == after
    extra = output / "blind_packets/UNREGISTERED.json"
    extra.write_text("{}\n", encoding="utf-8")
    with pytest.raises(c8.C8WorkspaceError, match="文件集合漂移"):
        c8.write_or_verify(output)


def test_c8_build_does_not_write_c7_sources() -> None:
    source_paths = [
        c8.C75_POLICY,
        c8.C76_POLICY,
        c8.C77_CONTRACT,
        c8.C77_PACKET_MANIFEST,
    ]
    before = {path: c8.sha256_file(path) for path in source_paths}
    c8.build_artifacts()
    after = {path: c8.sha256_file(path) for path in source_paths}
    assert before == after
