from __future__ import annotations

import json
from pathlib import Path

from isolation import run_git


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "tests/local_evidence_registry.json"


def _git(*args: str) -> str:
    return run_git(*args, cwd=ROOT, check=True, text=True).stdout


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


def test_legacy_local_evidence_keeps_pure_tests_outside_the_skip_boundary() -> None:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    legacy = next(
        row
        for row in document["groups"]
        if row["group_id"] == "LEGACY-LOCAL-REPLAY-EVIDENCE"
    )
    assert "test_governance_index.py" not in legacy["test_file_globs"]
    assert "test_model_benchmark.py" not in legacy["test_file_globs"]
    assert (
        "tests/test_governance_index.py::GovernanceIndexTests::"
        "test_root_readme_has_one_hop_governance_route"
        not in legacy["nodeids"]
    )
    assert (
        "tests/test_model_benchmark.py::"
        "test_official_deepseek_is_not_available_through_generic_slot"
        not in legacy["nodeids"]
    )


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
