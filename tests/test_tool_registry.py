from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "governance/tool_registry.json"
IDENTITIES = {
    "active_entry",
    "reusable_component",
    "batch_reproducer",
    "retired_compat",
    "pending",
}
REVIEWED_LATE_ROOT_TOOLS = {
    "tools/chatgpt_review_pack.py",
    "tools/v02_anchor_first_experiment.py",
    "tools/v02_anchor_first_live_runner.py",
    "tools/v02_c4_transport_probe.py",
    "tools/v02_c5_offline_score.py",
    "tools/v02_c5_stability.py",
    "tools/v02_c6_control_runner.py",
    "tools/v02_c6_crosswalk.py",
    "tools/v02_c7_consensus_tally.py",
    "tools/v02_c7_consensus_workspace.py",
    "tools/v02_c7_finalize_mapping.py",
    "tools/v02_c7_human_verdict_export.py",
    "tools/v02_c7_rescore_c5.py",
    "tools/v02_c8_control_consensus.py",
    "tools/v02_c8_control_workspace.py",
    "tools/v02_c8_gap_inventory.py",
    "tools/v02_c8_n10_reverse_outcomes.py",
    "tools/v02_c8_n11_floor_baselines.py",
    "tools/v02_density_fence_calculator.py",
    "tools/v02_duse_contract.py",
    "tools/v02_duse_query.py",
    "tools/v02_error_notebook.py",
    "tools/v02_four_view_reprojection.py",
    "tools/v02_gate_contracts.py",
    "tools/v02_granularity_casebook.py",
    "tools/v02_nominate_fill_contracts.py",
    "tools/v02_reporting_views.py",
    "tools/v02_scoreability_preflight.py",
    "tools/v02_thinking_replay.py",
    "tools/z83_retry13_atomic_repair.py",
    "tools/z89_deepseek_v4_pro_benchmark.py",
    "tools/z91_crossbook_exam_prep.py",
    "tools/z91_crossbook_exam_run.py",
    "tools/z91_source_fact_seal.py",
    "tools/z93_five_gold_gate.py",
    "tools/z93_five_gold_promote.py",
    "tools/z93_five_gold_revision.py",
    "tools/z94_local_semantic_live.py",
    "tools/z94_local_semantic_supply.py",
    "tools/z98_knife_a_step2_runner.py",
    "tools/z99_blind_gold_mining.py",
    "tools/z99_chapter_fact_graph_projection.py",
    "tools/z99_supply_tables.py",
}


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _root_python_entities() -> set[str]:
    return {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tools").glob("*.py")
        if path.is_file() and not path.is_symlink()
    }


def test_every_root_python_entity_is_registered_exactly_once() -> None:
    registry = _registry()
    paths = [row["path"] for row in registry["tools"]]

    assert len(paths) == len(set(paths))
    assert set(paths) == _root_python_entities()
    assert registry["scope"]["root_entity_count"] == len(paths)
    assert registry["scope"]["root_visible_python_entry_count"] == len(paths) + 1


def test_tool_ids_identities_and_summary_are_mechanically_consistent() -> None:
    registry = _registry()
    rows = registry["tools"]
    ids = [row["tool_id"] for row in rows]

    assert ids == [f"TOOL-{index:03d}" for index in range(1, len(rows) + 1)]
    assert len(ids) == len(set(ids))
    assert {row["primary_identity"] for row in rows} <= IDENTITIES
    summary = Counter(row["primary_identity"] for row in rows)
    assert registry["identity_summary"] == {
        identity: summary.get(identity, 0)
        for identity in (
            "reusable_component",
            "batch_reproducer",
            "active_entry",
            "retired_compat",
            "pending",
        )
    }


def test_registered_test_references_exist() -> None:
    missing: list[str] = []
    for row in _registry()["tools"]:
        for relative in row["test_references"]:
            if not (ROOT / relative).is_file():
                missing.append(f"{row['path']} -> {relative}")
    assert missing == []


def test_birth_gate_violation_paths_are_unique_registered_and_present() -> None:
    registry = _registry()
    registered = {row["path"] for row in registry["tools"]}
    violations = registry["birth_gate"]["birth_gate_violations"]
    paths = [row["path"] for row in violations]

    assert len(paths) == len(set(paths))
    assert set(paths) <= registered
    assert all((ROOT / relative).is_file() for relative in paths)
    assert REVIEWED_LATE_ROOT_TOOLS <= set(paths)
    assert registry["unresolved_identity_paths"] == []
