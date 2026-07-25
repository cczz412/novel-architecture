from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import v02_granularity_casebook as casebook


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "v02_granularity_casebook.py"
BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B4_1_granularity_casebook"
)


@pytest.fixture(scope="module")
def built_casebook() -> dict[str, object]:
    value = casebook.build_casebook()
    casebook.validate_casebook(value)
    return value


@pytest.fixture(scope="module")
def evaluated(built_casebook: dict[str, object]) -> dict[str, object]:
    return casebook.evaluate_casebook(built_casebook)


def _by_case(
    evaluated: dict[str, object],
) -> dict[str, dict[str, object]]:
    return {
        row["case_id"]: row
        for row in evaluated["results"]  # type: ignore[index]
    }


def test_casebook_has_exactly_ten_ordered_fictional_cases(
    built_casebook: dict[str, object],
) -> None:
    cases = built_casebook["cases"]  # type: ignore[index]
    assert [row["case_id"] for row in cases] == [
        f"B4-G{index:02d}" for index in range(1, 11)
    ]
    text = "\n".join(
        [row["title"] for row in cases]
        + [row["text"] for row in cases]
        + [part["text"] for row in cases for part in row["parts"]]
    )
    assert "《" not in text
    assert "》" not in text
    assert all(token not in text for token in casebook.SOURCE_SPECIFIC_TOKENS)


def test_every_part_has_the_full_six_value_fact_head(
    built_casebook: dict[str, object],
) -> None:
    cases = built_casebook["cases"]  # type: ignore[index]
    for row in cases:
        for part in row["parts"]:
            assert set(part["fact_head"]) == set(casebook.FACT_HEAD_FIELDS)
            assert all(part["fact_head"][field] for field in casebook.FACT_HEAD_FIELDS)
            assert (
                part["fact_head"]["actuality"]
                in casebook.ALLOWED_ACTUALITIES
            )


def test_program_runs_ten_of_ten_with_five_merges_and_five_splits(
    evaluated: dict[str, object],
) -> None:
    summary = evaluated["summary"]  # type: ignore[index]
    assert summary["required_cases"] == 10
    assert summary["evaluated_cases"] == 10
    assert summary["passed_cases"] == 10
    assert summary["decision_counts"] == {
        "MERGE": 5,
        "SPLIT": 5,
        "NEEDS_ADJUDICATION": 0,
    }
    assert summary["uncovered_boundary_count"] == 0


def test_every_output_atom_passes_closed_A_to_D(
    evaluated: dict[str, object],
) -> None:
    for result in evaluated["results"]:  # type: ignore[index]
        for atom in result["atom_contracts"]:
            assert atom["checks"] == {
                "A_COMPLETE_FACT_HEAD": True,
                "B_INDEPENDENT_LEDGER_OR_CAUSAL_ENDPOINT": True,
                "C_STANDALONE_OUTLINE_REUSE": True,
                "D_EXACTLY_ONE_PRIMARY_FUNCTION": True,
            }
            assert atom["passes"]


def test_all_five_merge_requirements_are_required_and_covered(
    evaluated: dict[str, object],
) -> None:
    rows = _by_case(evaluated)
    merge_ids = {"B4-G01", "B4-G03", "B4-G04", "B4-G05", "B4-G06"}
    assert {
        case_id
        for case_id, row in rows.items()
        if row["observed"]["decision"] == "MERGE"
    } == merge_ids
    for case_id in merge_ids:
        row = rows[case_id]
        assert row["observed"]["atom_count"] == 1
        assert row["observed"]["reason_codes"] == list(
            casebook.MERGE_REASON_ORDER
        )
        assert all(
            boundary["merge_condition_codes_passed"]
            == list(casebook.MERGE_REASON_ORDER)
            for boundary in row["boundaries"]
        )


def test_all_seven_split_triggers_have_a_regression_case(
    evaluated: dict[str, object],
) -> None:
    summary = evaluated["summary"]  # type: ignore[index]
    assert set(summary["split_reason_codes_covered"]) == set(
        casebook.SPLIT_REASONS
    )
    rows = _by_case(evaluated)
    assert rows["B4-G02"]["observed"]["reason_codes"] == [
        "S_DIFFERENT_SUBJECT_INDEPENDENT_ACTION",
        "S_INDEPENDENT_RESULTS",
        "S_CAUSAL_ENDPOINTS_REUSABLE",
        "S_EITHER_HALF_STANDALONE",
    ]
    assert rows["B4-G07"]["observed"]["reason_codes"] == [
        "S_DIFFERENT_STATE_SLOT_OR_ISSUE",
        "S_INDEPENDENT_RESULTS",
        "S_EITHER_HALF_STANDALONE",
    ]
    assert rows["B4-G09"]["observed"]["reason_codes"] == [
        "S_DIFFERENT_TIME_WINDOW",
        "S_ACTUALITY_DIFFERENT",
        "S_INDEPENDENT_RESULTS",
        "S_EITHER_HALF_STANDALONE",
    ]


def test_four_independent_issues_become_four_atoms(
    evaluated: dict[str, object],
) -> None:
    row = _by_case(evaluated)["B4-G08"]
    assert row["observed"]["decision"] == "SPLIT"
    assert row["observed"]["atom_count"] == 4
    assert row["observed"]["groups"] == [
        ["B4-G08-P01"],
        ["B4-G08-P02"],
        ["B4-G08-P03"],
        ["B4-G08-P04"],
    ]
    issue_keys = {
        key
        for atom in row["atom_contracts"]
        for key in atom["independent_ledger_keys"]
    }
    assert len(issue_keys) == 4


def test_speech_occurrence_does_not_upgrade_attributed_content(
    built_casebook: dict[str, object],
) -> None:
    cases = {
        row["case_id"]: row
        for row in built_casebook["cases"]  # type: ignore[index]
    }
    speech = cases["B4-G05"]["parts"]
    assert {part["fact_head"]["actuality"] for part in speech} == {
        "occurred"
    }
    assert {
        part["attributed_content"]["fact_head"]["actuality"]
        for part in speech
    } == {"planned"}
    assert {
        part["attributed_content"]["modality"] for part in speech
    } == {"instructed_future", "prohibited_future"}

    report = cases["B4-G09"]["parts"][2]
    assert report["fact_head"]["actuality"] == "occurred"
    assert (
        report["attributed_content"]["fact_head"]["actuality"]
        == "believed"
    )
    assert report["attributed_content"]["modality"] == "possible"


def test_missing_merge_condition_without_split_trigger_hangs_for_adjudication(
    built_casebook: dict[str, object],
) -> None:
    changed = copy.deepcopy(built_casebook["cases"][2])  # type: ignore[index]
    tail = changed["parts"][1]
    tail["ledger_writes"] = [
        {
            "view": "timeline",
            "key": "NEW-INDEPENDENT-KEY",
            "independent": True,
            "state_slot": None,
            "issue_id": None,
        }
    ]
    result = casebook.evaluate_case(changed)
    assert result["observed"]["decision"] == "NEEDS_ADJUDICATION"
    assert not result["passed"]
    assert result["boundaries"][0]["split_reason_codes"] == []
    assert result["boundaries"][0]["merge_condition_codes_missing"] == [
        "M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY"
    ]


def test_actuality_difference_is_a_split_trigger_not_a_merge_fallback(
    built_casebook: dict[str, object],
) -> None:
    changed = copy.deepcopy(built_casebook["cases"][2])  # type: ignore[index]
    changed["parts"][1]["fact_head"]["actuality"] = "planned"
    result = casebook.evaluate_case(changed)
    assert result["observed"]["decision"] == "SPLIT"
    assert "S_ACTUALITY_DIFFERENT" in result["observed"]["reason_codes"]
    assert not result["passed"]


def test_malformed_fact_head_is_rejected_before_decision(
    built_casebook: dict[str, object],
) -> None:
    changed = copy.deepcopy(built_casebook["cases"][0])  # type: ignore[index]
    del changed["parts"][0]["fact_head"]["result"]
    with pytest.raises(casebook.GranularityCasebookError, match="fact_head"):
        casebook.evaluate_case(changed)


def test_checked_in_bundle_matches_the_deterministic_builder() -> None:
    expected = casebook.build_artifacts()
    for relative_path, data in expected.items():
        target = BUNDLE_DIR / relative_path
        assert target.is_file(), relative_path
        assert target.read_bytes() == data, relative_path
    checked = casebook.check_bundle(BUNDLE_DIR)
    assert checked["result"] == "PASS"
    assert checked["case_pass_count"] == 10
    assert checked["decision_counts"] == {
        "MERGE": 5,
        "NEEDS_ADJUDICATION": 0,
        "SPLIT": 5,
    }
    assert checked["double_run_receipt_present"]


def test_manifest_hashes_artifacts_and_keeps_release_isolated() -> None:
    manifest = json.loads((BUNDLE_DIR / "manifest.json").read_text())
    assert manifest["candidate_status"] == "candidate_silver_not_active"
    assert manifest["rule_freeze"]["new_semantic_rules_added"] == 0
    assert manifest["scope"] == {
        "model_api_calls": 0,
        "network_requests": 0,
        "formal_gold_mutations": 0,
        "default_route_mutations": 0,
        "governance_mutations": 0,
        "notion_writes": 0,
    }
    assert manifest["release_isolation"] == {
        "activation_allowed": False,
        "formal_gold_changed": False,
        "default_chain_changed": False,
        "current_state_changed": False,
    }
    for row in manifest["artifacts"]:
        target = BUNDLE_DIR / row["path"]
        assert target.stat().st_size == row["bytes"]
        assert casebook._sha256(target.read_bytes()) == row["sha256"]


def test_double_run_receipt_is_byte_identical() -> None:
    receipt = json.loads(
        (BUNDLE_DIR / "double_run_receipt.json").read_text()
    )
    assert receipt["runs"] == 2
    assert receipt["byte_identical"]
    assert receipt["case_pass_count_each_run"] == 10
    assert receipt["uncovered_boundary_count_each_run"] == 0
    assert receipt["pass1_tree_sha256"] == receipt["pass2_tree_sha256"]
    assert receipt["pass1_tree_sha256"] == receipt["target_tree_sha256"]
    assert receipt["model_api_calls"] == 0
    assert receipt["network_requests"] == 0


def test_cli_build_validate_and_double_run(tmp_path: Path) -> None:
    output_dir = tmp_path / "bundle"
    built = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "build",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(built.stdout)["result"] == "BUILT"

    validated = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "validate-bundle",
            "--bundle-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(validated.stdout)["result"] == "PASS"

    double_run = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "double-run",
            "--bundle-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(double_run.stdout)["result"] == "PASS_BYTE_IDENTICAL"

    validated_again = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "validate-bundle",
            "--bundle-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(validated_again.stdout)[
        "double_run_receipt_present"
    ]


def test_tool_imports_no_network_client() -> None:
    tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    forbidden = {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "urllib",
        "websocket",
    }
    assert imported_roots.isdisjoint(forbidden)
