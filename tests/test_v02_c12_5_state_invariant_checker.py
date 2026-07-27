from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments/extraction_redesign_v02_overnight_20260725"
    / "V02_C12_5_state_invariant_checker_20260725"
    / "program/v02_c12_5_state_invariant_checker.py"
)
SPEC = importlib.util.spec_from_file_location("v02_c12_5_checker", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
sys.dont_write_bytecode = True
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def _tree_sha(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): checker.sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_b1_sources_are_frozen_and_real_material_is_not_falsely_green() -> None:
    before = _tree_sha(checker.B1_DIR)
    receipt = checker._locked_source_receipt()
    eligibility = checker._scan_b1_eligibility()
    after = _tree_sha(checker.B1_DIR)

    assert before == after
    assert len(receipt["sources"]) == 3
    assert all(
        sample["eligibility"] == "NOT_EVALUATED"
        and sample["finding_total"] is None
        and sample["not_evaluated_codes"]
        == list(checker.NOT_EVALUATED_CODES)
        for sample in eligibility["samples"]
    )
    assert all(
        sample["natural_language_before_after_used_for_rules"] is False
        and sample["narrative_order_used_as_story_time"] is False
        for sample in eligibility["samples"]
    )


def test_real_material_eligibility_is_a_field_scan_not_a_static_label() -> None:
    path, expected_sha = checker.B1_SOURCES["z99_reprojection"]
    document = json.loads(path.read_text(encoding="utf-8"))
    original = checker.scan_material_eligibility(
        source_role="original",
        source_path=path,
        source_sha256=expected_sha,
        document=document,
    )
    assert original["not_evaluated_codes"] == list(checker.NOT_EVALUATED_CODES)

    enriched = copy.deepcopy(document)
    for index, row in enumerate(enriched["views"]["character_states"], 1):
        row["state_id"] = f"S{index:02d}"
        row["valid_from"] = [1, 0, index, 0]
        row["scope"] = {
            "world_id": "W",
            "timeline_id": "T",
            "branch_id": "B",
            "policy_scope_id": "P",
        }
    enriched["state_invariant_rules"] = {
        "schema_version": "v02-c12.5-state-invariant-rules.v1"
    }
    rescanned = checker.scan_material_eligibility(
        source_role="enriched",
        source_path=path,
        source_sha256=expected_sha,
        document=enriched,
    )
    assert rescanned["not_evaluated_codes"] == []
    assert rescanned["eligibility"].startswith("STRUCTURALLY_ELIGIBLE")


def test_clean_fixture_has_no_findings_but_is_not_a_quality_pass() -> None:
    result = checker.diagnose(
        rules=checker.build_rules_fixture(),
        stream=checker.build_clean_stream(),
    )
    assert result["finding_total"] == 0
    assert result["status"] == "DIAGNOSTIC_ONLY"
    assert result["quality_result_registered"] is False
    assert result["quality_score_eligible"] is False
    assert result["traffic_light_eligible"] is False
    assert result["blocks_execution"] is False
    assert result["winner"] is None
    assert result["changes_applied"] is False


@pytest.mark.parametrize(
    ("mutant_id", "expected_code"),
    [
        ("irreversible_reverse", checker.DIAGNOSTIC_CODES["irreversible"]),
        ("exclusive_interval_overlap", checker.DIAGNOSTIC_CODES["exclusive"]),
        ("predecessor_time_regression", checker.DIAGNOSTIC_CODES["monotonic"]),
    ],
)
def test_each_single_mutation_hits_only_its_rule(
    mutant_id: str,
    expected_code: str,
) -> None:
    result = checker.diagnose(
        rules=checker.build_rules_fixture(),
        stream=checker.build_mutants()[mutant_id],
    )
    assert [finding["code"] for finding in result["findings"]] == [expected_code]


def test_input_order_does_not_change_diagnostic_bytes() -> None:
    stream = checker.build_mutants()["exclusive_interval_overlap"]
    reversed_stream = copy.deepcopy(stream)
    reversed_stream["assertions"].reverse()
    left = checker.diagnose(rules=checker.build_rules_fixture(), stream=stream)
    right = checker.diagnose(
        rules=checker.build_rules_fixture(),
        stream=reversed_stream,
    )
    assert checker.canonical_bytes(left) == checker.canonical_bytes(right)


def test_time_requires_explicit_integer_tuple_and_same_time_has_no_hidden_order() -> None:
    stream = checker.build_clean_stream()
    stream["assertions"][0]["valid_from"] = ["1", 0, 1, 0]
    with pytest.raises(checker.StateInvariantError, match="整数数组"):
        checker.diagnose(rules=checker.build_rules_fixture(), stream=stream)

    same_time = checker.build_clean_stream()
    for row in same_time["assertions"]:
        if row["assertion_id"] == "A-KNOW-2":
            row["valid_from"] = [1, 0, 1, 0]
            row["valid_until"] = [1, 0, 3, 0]
            break
    result = checker.diagnose(
        rules=checker.build_rules_fixture(),
        stream=same_time,
    )
    assert [row["code"] for row in result["findings"]] == [
        checker.DIAGNOSTIC_CODES["monotonic"]
    ]


def test_half_open_boundary_and_scope_isolation_prevent_false_conflict() -> None:
    clean = checker.build_clean_stream()
    assert (
        checker.diagnose(rules=checker.build_rules_fixture(), stream=clean)[
            "finding_total"
        ]
        == 0
    )

    changed = checker.build_mutants()["exclusive_interval_overlap"]
    mutant = next(
        row for row in changed["assertions"] if row["assertion_id"] == "M-EXCLUSIVE"
    )
    mutant["scope"]["branch_id"] = "B02"
    result = checker.diagnose(
        rules=checker.build_rules_fixture(),
        stream=changed,
    )
    assert result["finding_total"] == 0


def test_no_registry_means_no_keyword_guess_and_unknown_is_not_a_conflict() -> None:
    rules = checker.build_rules_fixture()
    rules["irreversible_states"] = []
    stream = checker.build_clean_stream()
    for row in stream["assertions"]:
        if row["assertion_id"] == "A-LIFE-2":
            row["state_id"] = checker.UNKNOWN_STATE_ID
            break
    result = checker.diagnose(rules=rules, stream=stream)
    assert result["unknown_state_total"] == 1
    assert result["diagnostic_completeness"] == "INCOMPLETE_UNKNOWN_STATE_PRESENT"
    assert result["finding_total"] == 0

    textual = checker.build_clean_stream()
    textual["assertions"][0]["state_id"] = "已死亡"
    with pytest.raises(checker.StateInvariantError, match="未知槽或状态"):
        checker.diagnose(rules=rules, stream=textual)


def test_rule_ambiguity_and_bad_predecessor_are_rejected_before_scan() -> None:
    duplicate_member = checker.build_rules_fixture()
    duplicate_member["exclusive_sets"].append(
        {
            "set_id": "EX-SECOND",
            "members": [
                {"slot_id": "location", "state_id": "city_a"},
                {"slot_id": "location", "state_id": "city_b"},
            ],
        }
    )
    with pytest.raises(checker.StateInvariantError, match="成员跨组重复"):
        checker.diagnose(
            rules=duplicate_member,
            stream=checker.build_clean_stream(),
        )

    bad_scope = checker.build_clean_stream()
    for row in bad_scope["assertions"]:
        if row["assertion_id"] == "A-KNOW-2":
            row["scope"]["branch_id"] = "B02"
            break
    with pytest.raises(
        checker.StateInvariantError,
        match="跨身份、实体、槽或作用域",
    ):
        checker.diagnose(
            rules=checker.build_rules_fixture(),
            stream=bad_scope,
        )


def test_binding_and_time_contract_are_not_decorative_fields() -> None:
    bad_binding = checker.build_clean_stream()
    bad_binding["assertions"][0]["identity_binding_sha256"] = "not-a-sha"
    with pytest.raises(checker.StateInvariantError, match="SHA-256"):
        checker.diagnose(
            rules=checker.build_rules_fixture(),
            stream=bad_binding,
        )

    bad_evidence = checker.build_clean_stream()
    bad_evidence["assertions"][0]["evidence_refs"][0]["span_sha256"] = "f" * 63
    with pytest.raises(checker.StateInvariantError, match="SHA-256"):
        checker.diagnose(
            rules=checker.build_rules_fixture(),
            stream=bad_evidence,
        )

    bad_time_contract = checker.build_rules_fixture()
    bad_time_contract["time_contract"]["interval_semantics"] = "CLOSED"
    with pytest.raises(checker.StateInvariantError, match="time_contract"):
        checker.diagnose(
            rules=bad_time_contract,
            stream=checker.build_clean_stream(),
        )


def test_identity_binding_drift_cannot_merge_entities_or_chain_predecessors() -> None:
    drift = checker.build_clean_stream()
    drift["assertions"][1]["identity_binding_sha256"] = "4" * 64
    with pytest.raises(checker.StateInvariantError, match="身份绑定漂移"):
        checker.diagnose(
            rules=checker.build_rules_fixture(),
            stream=drift,
        )


def test_cycle_is_rejected_and_terminal_repeat_is_not_reverse() -> None:
    cycle = checker.build_clean_stream()
    for row in cycle["assertions"]:
        if row["assertion_id"] == "A-KNOW-1":
            row["predecessor_assertion_id"] = "A-KNOW-2"
            break
    with pytest.raises(checker.StateInvariantError, match="形成环"):
        checker.diagnose(rules=checker.build_rules_fixture(), stream=cycle)

    repeated = checker.build_clean_stream()
    repeated["assertions"].append(
        checker._assertion(
            "A-LIFE-3",
            slot_id="life",
            state_id="dead",
            valid_from=[1, 0, 3, 0],
            valid_until=None,
            predecessor="A-LIFE-2",
        )
    )
    result = checker.diagnose(
        rules=checker.build_rules_fixture(),
        stream=repeated,
    )
    assert result["finding_total"] == 0


def test_irreversible_terminal_detects_preexisting_state_that_stays_active() -> None:
    stream = checker.build_clean_stream()
    for row in stream["assertions"]:
        if row["assertion_id"] == "A-LIFE-1":
            row["valid_until"] = None
            break
    result = checker.diagnose(
        rules=checker.build_rules_fixture(),
        stream=stream,
    )
    assert [finding["code"] for finding in result["findings"]] == [
        checker.DIAGNOSTIC_CODES["irreversible"]
    ]


def test_bundle_is_closed_double_built_and_binds_implementation() -> None:
    files, manifest_raw = checker.build_artifacts()
    manifest = json.loads(manifest_raw)
    listed = {row["path"]: row["sha256"] for row in manifest["files"]}
    assert set(listed) == set(files)
    assert all(listed[name] == checker.sha256_bytes(raw) for name, raw in files.items())
    double_run = json.loads(files["double_run_receipt.json"])
    assert double_run["byte_identical"] is True
    assert double_run["compared_file_total"] == 8
    binding = json.loads(files["implementation_binding_receipt.json"])
    assert binding["program"]["sha256"] == checker.sha256_file(PROGRAM)
    assert binding["test"]["sha256"] == checker.sha256_file(Path(__file__))
    assert manifest["model_api_calls"] == 0
    assert manifest["network_requests"] == 0
    assert manifest["quality_result_registered"] is False
    assert manifest["c13_touched"] is False


def test_bundle_check_ignores_only_python_import_cache() -> None:
    cache_file = (
        checker.OUTPUT_DIR
        / "program/__pycache__/c12_5_runtime_cache_regression.pyc"
    )
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"runtime cache is not an artifact")
    try:
        assert checker._is_ignorable_runtime_cache(
            cache_file.relative_to(checker.OUTPUT_DIR)
        )
        assert not checker._is_ignorable_runtime_cache(
            Path("program/unexpected.json")
        )
        manifest = checker.check_bundle()
        assert manifest["quality_result_registered"] is False
    finally:
        cache_file.unlink(missing_ok=True)


def test_generator_has_no_network_or_api_import_and_no_c13_dependency() -> None:
    tree = ast.parse(PROGRAM.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported.isdisjoint(
        {"requests", "httpx", "urllib", "socket", "openai", "anthropic"}
    )
    assert all(
        "C13" not in path.as_posix()
        for path, _expected_sha in checker.B1_SOURCES.values()
    )
    assert "C13" not in checker.OUTPUT_DIR.as_posix()
