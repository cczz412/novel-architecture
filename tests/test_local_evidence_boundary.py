from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from isolation import run_git


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "tests/local_evidence_registry.json"
LEGACY_GROUP_ID = "LEGACY-LOCAL-REPLAY-EVIDENCE"
LEGACY_TARGET_NODE = (
    "tests/test_classify_rules_v1_2.py::ClassifyRulesV12Tests::"
    "test_compiler_emits_source_and_scope_metadata"
)
UNRELATED_PORTABLE_NODES = (
    "tests/test_governance_index.py::GovernanceIndexTests::"
    "test_root_readme_has_one_hop_governance_route",
    "tests/test_model_benchmark.py::"
    "test_official_deepseek_is_not_available_through_generic_slot",
)
RETIRED_LONGCAT_NODE = (
    "tests/test_model_benchmark.py::"
    "test_longcat_thinking_profile_uses_only_official_parameters"
)


def _git(*args: str) -> str:
    return run_git(*args, cwd=ROOT, check=True, text=True).stdout


def _legacy_group(document: dict) -> dict:
    return next(
        row for row in document["groups"] if row["group_id"] == LEGACY_GROUP_ID
    )


def _run_pytest(
    *targets: str,
    require_local_evidence: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("NOVEL_RUN_LOCAL_EVIDENCE_TESTS", None)
    if require_local_evidence:
        environment["NOVEL_RUN_LOCAL_EVIDENCE_TESTS"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", *targets],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_local_evidence_registry_is_complete_and_points_to_tests() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert document["schema_version"] == "pytest-local-evidence-v1"
    group_ids = [row["group_id"] for row in document["groups"]]
    assert len(group_ids) == len(set(group_ids))
    for row in document["groups"]:
        patterns = row.get("test_file_globs", [])
        nodeids = row.get("nodeids", [])
        matched = {
            path.name
            for pattern in patterns
            for path in (ROOT / "tests").glob(pattern)
        }
        assert matched or nodeids, row["group_id"]
        for nodeid in nodeids:
            test_path = nodeid.split("::", 1)[0]
            assert test_path.startswith("tests/")
            assert (ROOT / test_path).is_file(), nodeid
        assert row["required_paths"]
        assert row["reason"].strip()


def test_legacy_local_evidence_uses_exact_nodes_and_keeps_retired_node_out() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    legacy = _legacy_group(document)
    assert legacy["test_file_globs"] == []
    assert set(UNRELATED_PORTABLE_NODES).isdisjoint(legacy["nodeids"])
    assert RETIRED_LONGCAT_NODE not in legacy["nodeids"]


def test_legacy_local_evidence_nodeids_are_unique_and_bound_to_collection() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    legacy = _legacy_group(document)
    nodeids = legacy["nodeids"]
    assert nodeids
    assert len(nodeids) == len(set(nodeids))

    snapshot = legacy["node_scope_migration_snapshot"]
    assert snapshot["former_whole_file_rule_count"] == 28
    assert (
        snapshot["collected_nodeid_count"]
        + snapshot["preexisting_exact_nodeid_count"]
        == snapshot["merged_exact_nodeid_count"]
        == len(nodeids)
    )
    snapshot_bytes = "".join(f"{nodeid}\n" for nodeid in sorted(nodeids)).encode(
        "utf-8"
    )
    assert hashlib.sha256(snapshot_bytes).hexdigest() == snapshot[
        "merged_exact_nodeids_sha256"
    ]

    test_files = sorted({nodeid.split("::", 1)[0] for nodeid in nodeids})
    result = _run_pytest("--collect-only", *test_files)
    assert result.returncode == 0, result.stdout + result.stderr
    collected = {
        line.strip()
        for line in result.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    }
    assert set(nodeids) <= collected


def test_missing_legacy_material_skips_only_the_exact_registered_node() -> None:
    result = _run_pytest(LEGACY_TARGET_NODE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 skipped" in result.stdout
    assert "本机证据专线必须先补齐登记材料" in result.stdout


def test_evidence_lane_rejects_missing_material_before_test_body() -> None:
    result = _run_pytest(LEGACY_TARGET_NODE, require_local_evidence=True)
    output = result.stdout + result.stderr
    assert result.returncode == 4, output
    assert f"group_id={LEGACY_GROUP_ID}" in output
    assert "missing=" in output
    assert "no tests ran" in output
    assert "passed" not in output
    assert "failed" not in output


def test_evidence_lane_does_not_block_unrelated_portable_nodes() -> None:
    result = _run_pytest(*UNRELATED_PORTABLE_NODES, require_local_evidence=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_evidence_lane_checks_items_after_keyword_selection() -> None:
    result = _run_pytest(
        "tests/test_model_benchmark.py",
        "-k",
        "official_deepseek_is_not_available_through_generic_slot",
        require_local_evidence=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_local_evidence_changes_route_through_m11_and_full_chain() -> None:
    policy = json.loads(
        (ROOT / "governance/test_policy.json").read_text(encoding="utf-8")
    )
    assert "tests/test_local_evidence_boundary.py" in policy["module_tests"]["M11"]

    registry_rule = next(
        row
        for row in policy["path_rules"]
        if row["pattern"] == "tests/local_evidence_registry.json"
    )
    assert registry_rule["modules"] == ["M11"]
    assert registry_rule["full_chain"] is True
    assert registry_rule["tests"] == [
        "tests/test_local_evidence_boundary.py",
        "tests/test_test_debt_policy.py",
        "tests/test_ci_lanes.py",
    ]

    conftest_rule = next(
        row for row in policy["path_rules"] if row["pattern"] == "tests/conftest.py"
    )
    assert "tests/test_local_evidence_boundary.py" in conftest_rule["tests"]
    assert "tests/test_ci_lanes.py" in conftest_rule["tests"]


def test_v02_portable_programs_keep_pure_tests_in_clean_clone() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    group = next(
        row
        for row in document["groups"]
        if row["group_id"] == "V02-C11-C12-C15-R1-LOCAL-EVIDENCE-NODES"
    )
    assert group["test_file_globs"] == []
    assert len(group["nodeids"]) == 81
    assert len(set(group["nodeids"])) == 81
    assert len(group["portable_program_paths"]) == 18
    assert (
        "tests/test_v02_r1_route_r04.py"
        not in {nodeid.split("::", 1)[0] for nodeid in group["nodeids"]}
    )
    for relative in group["portable_program_paths"]:
        assert (ROOT / relative).is_file(), relative
        result = run_git("check-ignore", "-q", relative, cwd=ROOT, check=False)
        assert result.returncode == 1, relative

    r2_group = next(
        row
        for row in document["groups"]
        if row["group_id"] == "V02-C11-R2-A8-QEC-LOCAL-EVIDENCE-NODES"
    )
    assert r2_group["test_file_globs"] == []
    assert len(r2_group["nodeids"]) == 39
    assert len(set(r2_group["nodeids"])) == 39


def test_c13_skip_uses_exact_nodeids_not_whole_files() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    group = next(row for row in document["groups"] if row["group_id"] == "V02-C13-LOCAL-EVIDENCE")
    assert group["test_file_globs"] == []
    assert group["nodeids"]
    assert len(group["nodeids"]) == len(set(group["nodeids"]))
    mechanical = {
        "tests/test_v02_c13_downstream_consumer.py::test_task_a_rejects_unknown_fields_and_dangling_fact_ids",
        "tests/test_v02_c13_provider_wire.py::test_generator_has_no_network_or_provider_sdk_imports",
        "tests/test_v02_c13_signoff_floor_v2.py::test_generator_has_no_network_or_provider_sdk_imports",
        "tests/test_v02_c13_execution_runner.py::test_runner_source_keeps_live_network_behind_ticket_gate",
    }
    assert mechanical.isdisjoint(set(group["nodeids"]))


def test_local_evidence_roots_are_ignored_and_not_tracked() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for row in document["groups"]:
        for relative in row["required_paths"]:
            result = run_git("check-ignore", "-q", relative, cwd=ROOT, check=False)
            assert result.returncode == 0, relative
            assert _git("ls-files", "--", relative) == ""
