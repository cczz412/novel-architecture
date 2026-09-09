from __future__ import annotations

from copy import deepcopy
import unittest
from pathlib import Path

import pytest

from tools import test_impact


ROOT = Path(__file__).resolve().parents[1]
PR_GATE_WORKFLOW = ROOT / ".github/workflows/pr-gate.yml"
B09_COMPONENT_ROOT = "work/ccz57_m3_b09_current_causal_hint_view_r01"
B09_DIRECTED_TEST = f"{B09_COMPONENT_ROOT}/test_current_causal_hint_view.py"
B09_AUTHORITY_DEPENDENCY_PATHS = [
    "work/ccz57_m3_b01_candidate_version_r03_5/b01_contract.py",
    "work/ccz57_m3_b02_diagnostic_coverage_r03_5/b02_contracts.py",
    "work/ccz57_m3_b03_bound_evidence_read_r03_5/b03_contracts.py",
    "work/ccz57_m3_b04_patch_atomic_group_r03_5/b04_contracts.py",
    "work/ccz57_m3_b05_patch_route_r03_5/b05_contracts.py",
    "work/ccz57_m3_b06_commit_core_r01/b06_contracts.py",
    "work/ccz57_m3_b07_local_recovery_stop_r01/b07_contracts.py",
    "work/ccz57_m3_b08_segment_terminal_r01/b08_contracts.py",
]
B10_COMPONENT_ROOT = "work/ccz57_m3_b10_chapter_candidate_progress_view_r01"
B10_DIRECTED_TEST = f"{B10_COMPONENT_ROOT}/test_current_chapter_progress_view.py"
B10_AUTHORITY_DEPENDENCY_PATHS = [
    "work/ccz57_m3_b01_candidate_version_r03_5/b01_contract.py",
    "work/ccz57_m3_b06_commit_core_r01/b06_contracts.py",
    "work/ccz57_m3_b07_local_recovery_stop_r01/b07_contracts.py",
    "work/ccz57_m3_b08_segment_terminal_r01/b08_contracts.py",
]
B_STAGE_PRODUCER_CASES = [
    (
        "B-01",
        "work/ccz57_m3_b01_candidate_version_r03_5",
        "CCZ-57 B-01 当前候选版本生产者自测",
        "work/ccz57_m3_b01_candidate_version_r03_5/test_b01_contract.py",
    ),
    (
        "B-02",
        "work/ccz57_m3_b02_diagnostic_coverage_r03_5",
        "CCZ-57 B-02 当前诊断覆盖生产者自测",
        "work/ccz57_m3_b02_diagnostic_coverage_r03_5/test_b02_diagnostic_coverage.py",
    ),
    (
        "B-03",
        "work/ccz57_m3_b03_bound_evidence_read_r03_5",
        "CCZ-57 B-03 当前证据读取生产者自测",
        "work/ccz57_m3_b03_bound_evidence_read_r03_5/test_b03_bound_evidence_read.py",
    ),
    (
        "B-04",
        "work/ccz57_m3_b04_patch_atomic_group_r03_5",
        "CCZ-57 B-04 当前原子补丁生产者自测",
        "work/ccz57_m3_b04_patch_atomic_group_r03_5/test_b04_patch_atomic_group.py",
    ),
    (
        "B-05",
        "work/ccz57_m3_b05_patch_route_r03_5",
        "CCZ-57 B-05 当前安全路线生产者自测",
        "work/ccz57_m3_b05_patch_route_r03_5/test_b05_patch_route.py",
    ),
    (
        "B-06",
        "work/ccz57_m3_b06_commit_core_r01",
        "CCZ-57 B-06 当前提交核心生产者自测",
        "work/ccz57_m3_b06_commit_core_r01/test_b06_commit_core.py",
    ),
    (
        "B-07",
        "work/ccz57_m3_b07_local_recovery_stop_r01",
        "CCZ-57 B-07 当前恢复停损生产者自测",
        "work/ccz57_m3_b07_local_recovery_stop_r01/test_b07_local_recovery.py",
    ),
    (
        "B-08",
        "work/ccz57_m3_b08_segment_terminal_r01",
        "CCZ-57 B-08 当前责任段终态生产者自测",
        "work/ccz57_m3_b08_segment_terminal_r01/test_b08_segment_terminal.py",
    ),
]
B_STAGE_OWN_TEST_BY_DEPENDENCY_PATH = {
    dependency_path: own_test
    for dependency_path, own_test in zip(
        B09_AUTHORITY_DEPENDENCY_PATHS,
        [case[3] for case in B_STAGE_PRODUCER_CASES],
        strict=True,
    )
}


def spec(
    paths: list[str],
    *,
    flags: list[str] | None = None,
    contract_changes: list[dict] | None = None,
    head_paths: list[str] | None = None,
) -> dict:
    result = {
        "contract_version": test_impact.SPEC_CONTRACT,
        "change_id": "CHANGE-1",
        "changed_paths": paths,
        "flags": flags or [],
        "contract_changes": contract_changes or [],
    }
    if head_paths is not None:
        result["head_paths"] = head_paths
    return result


class TestImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = test_impact.load_policy()
        cls.registry = test_impact._mapping(test_impact.read_json(test_impact.DEFAULT_REGISTRY), "registry")

    def test_documentation_change_does_not_run_full_chain(self) -> None:
        plan = test_impact.build_plan(
            spec(["reports/Z76/example.md"]), policy=self.policy, registry=self.registry
        )
        self.assertEqual(plan["scope"], "documentation_only")
        self.assertFalse(plan["full_chain"])

    def test_available_local_module_with_unchanged_contract_uses_targeted_tests(self) -> None:
        plan = test_impact.build_plan(
            spec(["tools/demo_score_helper.py"]), policy=self.policy, registry=self.registry
        )
        self.assertEqual(plan["scope"], "targeted")
        self.assertFalse(plan["full_chain"])
        self.assertIn("M10", plan["affected_modules"])
        self.assertIn("tests/test_z75_multidirection_score.py", plan["selected_tests"])
        self.assertIn(
            "uv run --locked ruff check -- tools/demo_score_helper.py",
            plan["commands"],
        )
        self.assertTrue(plan["commands"][0].startswith("uv run --locked pytest -q "))
        self.assertEqual(
            plan["execution_steps"][0]["argv"][:5],
            ["uv", "run", "--locked", "pytest", "-q"],
        )
        self.assertEqual(plan["execution_steps"][0]["cwd"], "repo_root")

    def test_existing_contract_change_runs_full_chain(self) -> None:
        plan = test_impact.build_plan(
            spec(
                ["tools/pipeline_inspector.py"],
                contract_changes=[{"module_id": "M11", "kind": "compatible_minor"}],
            ),
            policy=self.policy,
            registry=self.registry,
        )
        self.assertTrue(plan["full_chain"])
        self.assertIn(
            "uv run --locked ruff check -- tools/pipeline_inspector.py",
            plan["commands"],
        )
        self.assertEqual(plan["scope"], "full_chain")

    def test_unified_entry_change_runs_full_chain(self) -> None:
        plan = test_impact.build_plan(
            spec(["tools/novel_pipeline.py"], flags=["unified_entry_changed"]),
            policy=self.policy,
            registry=self.registry,
        )
        self.assertTrue(plan["full_chain"])
        self.assertIn(
            "uv run --locked ruff check -- tools/novel_pipeline.py",
            plan["commands"],
        )

    def test_unknown_path_fails_safe_to_full_chain(self) -> None:
        plan = test_impact.build_plan(
            spec(["mystery/unknown.bin"]), policy=self.policy, registry=self.registry
        )
        self.assertTrue(plan["full_chain"])
        self.assertEqual(
            plan["commands"][0], test_impact.PORTABLE_FULL_CHAIN_COMMAND
        )
        self.assertNotIn("/Users/", plan["commands"][0])
        self.assertEqual(plan["unknown_paths"], ["mystery/unknown.bin"])
        self.assertEqual(
            plan["execution_steps"][0]["argv"],
            test_impact.PORTABLE_FULL_CHAIN_ARGV,
        )

    def test_governance_json_change_schedules_live_root_checkers(self) -> None:
        plan = test_impact.build_plan(
            spec(["governance/current_pointers.json"]),
            policy=self.policy,
            registry=self.registry,
        )
        self.assertFalse(plan["full_chain"])
        self.assertIn("tests/test_drift.py", plan["selected_tests"])
        self.assertIn("tests/test_current_freshness.py", plan["selected_tests"])
        self.assertIn("tests/test_design_currentness.py", plan["selected_tests"])
        self.assertIn("tests/test_traceability.py", plan["selected_tests"])

    def test_documentation_commands_are_locked_structured_steps(self) -> None:
        plan = test_impact.build_plan(
            spec(["governance/notes/example.md"]),
            policy=self.policy,
            registry=self.registry,
        )
        self.assertEqual(plan["scope"], "documentation_only")
        self.assertEqual(len(plan["commands"]), len(plan["execution_steps"]))
        for step in plan["execution_steps"]:
            self.assertEqual(step["argv"][:3], ["uv", "run", "--locked"])
            self.assertEqual(step["cwd"], "repo_root")

    def test_gate_policy_and_planner_changes_are_full_chain(self) -> None:
        cases = {
            ".github/workflows/pr-gate.yml": "PR 基础门禁工作流",
            "governance/test_policy.json": "测试纪律本体",
            "tools/test_impact.py": "测试影响规划器",
        }
        for path, rule_name in cases.items():
            with self.subTest(path=path):
                plan = test_impact.build_plan(
                    spec([path]), policy=self.policy, registry=self.registry
                )
                self.assertTrue(plan["full_chain"])
                self.assertIn(rule_name, plan["matched_paths"][path])
                self.assertTrue(
                    any(rule_name in reason for reason in plan["full_chain_reasons"])
                )

    def test_b01_to_b08_producers_run_own_tests_before_consumers_and_full_chain(
        self,
    ) -> None:
        b10_stages = {"B-01", "B-06", "B-07", "B-08"}
        for stage, component_root, rule_name, own_test in B_STAGE_PRODUCER_CASES:
            python_paths = sorted(
                path.relative_to(ROOT).as_posix()
                for path in (ROOT / component_root).glob("*.py")
            )
            self.assertTrue(python_paths, stage)
            expected_tests = [own_test, B09_DIRECTED_TEST]
            if stage in b10_stages:
                expected_tests.append(B10_DIRECTED_TEST)
            expected_tests = sorted(expected_tests)
            for path in python_paths:
                with self.subTest(stage=stage, path=path):
                    plan = test_impact.build_plan(
                        spec([path]), policy=self.policy, registry=self.registry
                    )
                    self.assertEqual(plan["scope"], "full_chain")
                    self.assertTrue(plan["full_chain"])
                    self.assertEqual(plan["unknown_paths"], [])
                    self.assertEqual(plan["affected_modules"], [])
                    selected = expected_with_ccz180(path, expected_tests)
                    self.assertEqual(plan["selected_tests"], selected)
                    self.assertIn(rule_name, plan["matched_paths"][path])
                    pytest_steps = [
                        step
                        for step in plan["execution_steps"]
                        if step["step_id"].startswith("pytest-")
                    ]
                    self.assertEqual(
                        [step["argv"] for step in pytest_steps[:-1]],
                        [
                            ["uv", "run", "--locked", "pytest", "-q", test_path]
                            for test_path in [own_test, *sorted(set(selected) - {own_test})]
                        ],
                    )
                    self.assertEqual(
                        pytest_steps[-1]["argv"],
                        test_impact.PORTABLE_FULL_CHAIN_ARGV,
                    )
                    self.assertEqual(pytest_steps[0]["argv"][-1], own_test)

    def test_b09_pure_derived_view_has_long_term_targeted_registration(self) -> None:
        paths = [
            f"{B09_COMPONENT_ROOT}/b09_contracts.py",
            f"{B09_COMPONENT_ROOT}/b09_authority_reader.py",
            f"{B09_COMPONENT_ROOT}/current_causal_hint_view.py",
            f"{B09_COMPONENT_ROOT}/self_check.py",
            B09_DIRECTED_TEST,
        ]
        for path in paths:
            with self.subTest(path=path):
                plan = test_impact.build_plan(
                    spec([path]), policy=self.policy, registry=self.registry
                )
                self.assertEqual(plan["scope"], "targeted")
                self.assertFalse(plan["full_chain"])
                self.assertEqual(plan["unknown_paths"], [])
                self.assertEqual(plan["affected_modules"], [])
                self.assertEqual(plan["selected_tests"], [B09_DIRECTED_TEST])
                self.assertEqual(
                    plan["execution_steps"][0]["argv"],
                    ["uv", "run", "--locked", "pytest", "-q", B09_DIRECTED_TEST],
                )
                self.assertIn(
                    "CCZ-57 B-09 当前因果提示纯派生视图",
                    plan["matched_paths"][path],
                )

    def test_b09_authority_dependencies_add_consumer_without_downgrade(
        self,
    ) -> None:
        for path in B09_AUTHORITY_DEPENDENCY_PATHS:
            with self.subTest(path=path):
                plan = test_impact.build_plan(
                    spec([path]), policy=self.policy, registry=self.registry
                )
                self.assertEqual(plan["scope"], "full_chain")
                self.assertTrue(plan["full_chain"])
                self.assertEqual(plan["unknown_paths"], [])
                self.assertEqual(plan["affected_modules"], [])
                expected_tests = [
                    B_STAGE_OWN_TEST_BY_DEPENDENCY_PATH[path],
                    B09_DIRECTED_TEST,
                ]
                if path in B10_AUTHORITY_DEPENDENCY_PATHS:
                    expected_tests.append(B10_DIRECTED_TEST)
                expected_tests = expected_with_ccz180(path, expected_tests)
                self.assertEqual(plan["selected_tests"], expected_tests)
                self.assertEqual(
                    [step["step_id"] for step in plan["execution_steps"]],
                    [
                        *[
                            f"pytest-outside-default-{index:02d}"
                            for index in range(1, len(expected_tests) + 1)
                        ],
                        "pytest-full",
                        "ruff",
                    ],
                )
                self.assertEqual(
                    [
                        step["argv"]
                        for step in plan["execution_steps"][:-2]
                    ],
                    [
                        ["uv", "run", "--locked", "pytest", "-q", test_path]
                        for test_path in producer_first(path, expected_tests)
                    ],
                )
                self.assertIn(
                    "CCZ-57 B-09 权威上游与传递合同",
                    plan["matched_paths"][path],
                )
                self.assertTrue(
                    any(
                        "CCZ-57 B-09 权威上游与传递合同" in reason
                        for reason in plan["full_chain_reasons"]
                    )
                )

    def test_b09_direct_nonpython_fixture_input_selects_directed_test(self) -> None:
        path = "work/ccz57_m3_b01_candidate_version_r03_5/OBJECT_SHAPES.json"
        plan = test_impact.build_plan(
            spec([path]), policy=self.policy, registry=self.registry
        )
        self.assertEqual(plan["scope"], "full_chain")
        self.assertTrue(plan["full_chain"])
        self.assertEqual(plan["unknown_paths"], [])
        self.assertEqual(
            plan["selected_tests"], [B09_DIRECTED_TEST, B10_DIRECTED_TEST]
        )
        self.assertEqual(
            [step["step_id"] for step in plan["execution_steps"]],
            [
                "pytest-outside-default-01",
                "pytest-outside-default-02",
                "pytest-full",
            ],
        )
        self.assertEqual(
            [step["argv"] for step in plan["execution_steps"][:2]],
            [
                ["uv", "run", "--locked", "pytest", "-q", B09_DIRECTED_TEST],
                ["uv", "run", "--locked", "pytest", "-q", B10_DIRECTED_TEST],
            ],
        )
        self.assertIn(
            "CCZ-57 B-09 直接读取的 B-01 样例合同",
            plan["matched_paths"][path],
        )

    def test_b10_pure_derived_view_has_long_term_targeted_registration(self) -> None:
        paths = [
            f"{B10_COMPONENT_ROOT}/b10_contracts.py",
            f"{B10_COMPONENT_ROOT}/b10_authority_reader.py",
            f"{B10_COMPONENT_ROOT}/current_chapter_progress_view.py",
            f"{B10_COMPONENT_ROOT}/self_check.py",
            B10_DIRECTED_TEST,
        ]
        for path in paths:
            with self.subTest(path=path):
                plan = test_impact.build_plan(
                    spec([path]), policy=self.policy, registry=self.registry
                )
                self.assertEqual(plan["scope"], "targeted")
                self.assertFalse(plan["full_chain"])
                self.assertEqual(plan["unknown_paths"], [])
                self.assertEqual(plan["affected_modules"], [])
                self.assertEqual(plan["selected_tests"], [B10_DIRECTED_TEST])
                self.assertEqual(
                    plan["execution_steps"][0]["argv"],
                    ["uv", "run", "--locked", "pytest", "-q", B10_DIRECTED_TEST],
                )
                self.assertIn(
                    "CCZ-57 B-10 当前章节候选进度纯派生视图",
                    plan["matched_paths"][path],
                )

    def test_b10_authority_dependencies_append_consumer_without_downgrade(
        self,
    ) -> None:
        for path in B10_AUTHORITY_DEPENDENCY_PATHS:
            with self.subTest(path=path):
                plan = test_impact.build_plan(
                    spec([path]), policy=self.policy, registry=self.registry
                )
                self.assertEqual(plan["scope"], "full_chain")
                self.assertTrue(plan["full_chain"])
                self.assertEqual(plan["unknown_paths"], [])
                self.assertEqual(plan["affected_modules"], [])
                expected_tests = sorted(
                    [
                        B_STAGE_OWN_TEST_BY_DEPENDENCY_PATH[path],
                        B09_DIRECTED_TEST,
                        B10_DIRECTED_TEST,
                    ]
                )
                expected_tests = expected_with_ccz180(path, expected_tests)
                self.assertEqual(
                    plan["selected_tests"], expected_tests
                )
                self.assertEqual(
                    [step["step_id"] for step in plan["execution_steps"]],
                    [
                        *[f"pytest-outside-default-{i:02d}"
                          for i in range(1, len(expected_tests) + 1)],
                        "pytest-full",
                        "ruff",
                    ],
                )
                self.assertEqual(
                    [step["argv"] for step in plan["execution_steps"][:-2]],
                    [
                        ["uv", "run", "--locked", "pytest", "-q", test_path]
                        for test_path in producer_first(path, expected_tests)
                    ],
                )
                self.assertIn(
                    "CCZ-57 B-10 当前章节候选进度权威上游",
                    plan["matched_paths"][path],
                )

    def test_full_chain_keeps_registered_tests_outside_default_collection(
        self,
    ) -> None:
        changed_paths = [
            "governance/test_policy.json",
            f"{B09_COMPONENT_ROOT}/b09_authority_reader.py",
        ]
        plan = test_impact.build_plan(
            spec(changed_paths), policy=self.policy, registry=self.registry
        )
        self.assertTrue(plan["full_chain"])
        self.assertEqual(plan["scope"], "full_chain")
        steps = plan["execution_steps"]
        self.assertEqual(
            [step["step_id"] for step in steps],
            ["pytest-full", "pytest-outside-default-01", "ruff"],
        )
        self.assertEqual(
            steps[1]["argv"],
            ["uv", "run", "--locked", "pytest", "-q", B09_DIRECTED_TEST],
        )

    def test_full_chain_does_not_repeat_tests_inside_default_collection(self) -> None:
        plan = test_impact.build_plan(
            spec(["tools/test_impact.py"]),
            policy=self.policy,
            registry=self.registry,
        )
        self.assertEqual(
            [step["step_id"] for step in plan["execution_steps"]],
            ["pytest-full", "ruff"],
        )

    def test_policy_and_planner_cannot_downgrade_their_own_full_chain_rule(self) -> None:
        weakened_policy = deepcopy(self.policy)
        weakened_policy["unknown_path_full_chain"] = False
        weakened_policy["path_rules"] = [
            row
            for row in weakened_policy["path_rules"]
            if row.get("pattern")
            not in test_impact.NON_DOWNGRADABLE_PLANNER_PATHS
        ]
        for path in sorted(test_impact.NON_DOWNGRADABLE_PLANNER_PATHS):
            with self.subTest(path=path):
                plan = test_impact.build_plan(
                    spec([path], head_paths=[path]),
                    policy=weakened_policy,
                    registry=self.registry,
                )
                self.assertTrue(plan["full_chain"])
                self.assertEqual(plan["scope"], "full_chain")
                self.assertTrue(
                    any("不可降级" in reason for reason in plan["full_chain_reasons"])
                )

    def test_deleted_python_path_is_not_sent_to_ruff(self) -> None:
        plan = test_impact.build_plan(
            spec(["tools/demo_score_helper.py"], head_paths=[]),
            policy=self.policy,
            registry=self.registry,
        )
        self.assertEqual(plan["linted_python_paths"], [])
        self.assertNotIn("ruff", {step["step_id"] for step in plan["execution_steps"]})

    def test_renamed_python_path_only_lints_the_head_path(self) -> None:
        old_path = "tools/deleted_demo_score_helper.py"
        new_path = "tools/demo_score_helper.py"
        plan = test_impact.build_plan(
            spec([old_path, new_path], head_paths=[new_path]),
            policy=self.policy,
            registry=self.registry,
        )
        ruff = next(
            step for step in plan["execution_steps"] if step["step_id"] == "ruff"
        )
        self.assertEqual(ruff["argv"][-1], new_path)
        self.assertNotIn(old_path, ruff["argv"])

    def test_shell_like_filename_stays_one_literal_argument(self) -> None:
        suspicious = "mystery/name with spaces;echo-owned.py"
        plan = test_impact.build_plan(
            spec([suspicious]), policy=self.policy, registry=self.registry
        )
        self.assertTrue(plan["full_chain"])
        ruff = next(
            step for step in plan["execution_steps"] if step["step_id"] == "ruff"
        )
        self.assertEqual(ruff["argv"][-1], suspicious)
        self.assertNotIn("eval", "\n".join(plan["commands"]))

    def test_unlocked_policy_command_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            test_impact.TestImpactError, "必须以 uv run --locked 开头"
        ):
            test_impact._locked_command_argv("pytest -q", "demo")

    def test_pr_gate_workflow_keeps_permissions_and_receipts_bounded(self) -> None:
        text = PR_GATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertNotIn("pull_request_target", text)
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn('PR_GATE_RECEIPT_DIR=$receipt_dir', text)
        self.assertIn('>> "$GITHUB_ENV"', text)
        self.assertNotIn("UV_PROJECT_ENVIRONMENT: ${{ runner.temp }}", text)
        self.assertIn("uv sync --locked", text)
        self.assertIn("uv run --locked python tools/test_impact.py", text)
        self.assertIn("execution_steps", text)
        self.assertIn('executed_argv.extend(["--ci-lane", "main-portable"])', text)
        self.assertIn('step_id == "pytest-full"', text)
        self.assertIn("if: always()", text)
        self.assertIn("selection-input.json", text)
        self.assertIn("test-plan.json", text)
        self.assertIn("execution-result.json", text)
        self.assertIn("job-started.txt", text)
        self.assertIn("--name-status", text)
        self.assertIn("head_paths", text)
        self.assertIn("不可降级的选测核心文件", text)
        self.assertNotIn("eval", text)
        self.assertIn(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", text
        )
        self.assertIn(
            "astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d",
            text,
        )
        self.assertIn(
            "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
            text,
        )


# Frozen CCZ-180 consumers; this table checks actual executable argv, not labels.
CCZ180_TESTS = {
    "authority": "work/ccz142_candidate_authority_r01/test_candidate_authority.py",
    "display": "work/ccz142_current_candidate_read_display_r01/test_current_read_display.py",
    "entry": "work/ccz142_current_candidate_read_entry_r01/test_current_read_entry.py",
    "preview": "work/ccz142_current_candidate_read_preview_r01/test_current_read_preview.py",
    "proof": "work/ccz142_current_candidate_read_proof_r01/test_current_read_proof.py",
    "coverage": "work/ccz142_human_card_coverage_wire_r01/test_human_card_coverage_wire.py",
    "catalog": "work/ccz142_human_card_gold_catalog_r01/test_human_card_gold_catalog.py",
    "vertical": "work/ccz142_human_card_vertical_wire_r01/test_human_card_vertical_wire.py",
    "card_identity": "work/ccz142_named_chapter_card_identity_r01/test_named_chapter_card_identity.py",
    "named": "work/ccz142_named_chapter_txt_card_r01/test_named_chapter_txt_card.py",
    "identity_read": "work/ccz142_named_identity_read_r01/test_named_identity_read.py",
    "identity_store": "work/ccz142_named_identity_store_r01/test_named_identity_store.py",
    "duty": "work/ccz142_q9_duty_freeze_r01/test_duty_freeze.py",
    "door": "work/door1_author_intake_view_r01/test_door1_view.py",
}
CCZ180_DIRECT_UPSTREAM = {
    "authority": [
        "work/ccz57_m3_b01_candidate_version_r03_5/b01_contract.py",
        "work/ccz57_m3_b05_patch_route_r03_5/b05_contracts.py",
        "work/ccz57_m3_b06_commit_core_r01/b06_contracts.py",
        "work/ccz57_m3_b06_commit_core_r01/b06_store.py",
        "work/ccz57_m3_b07_local_recovery_stop_r01/b07_store.py",
        "work/ccz57_m3_b08_segment_terminal_r01/b08_store.py",
        "work/ccz57_m3_b01_candidate_version_r03_5/fixtures.py",
        "work/ccz57_m3_b05_patch_route_r03_5/fixtures.py",
        "work/ccz57_m3_b06_commit_core_r01/fixtures.py",
        "work/ccz57_m3_b07_local_recovery_stop_r01/fixtures.py",
        "work/ccz57_m3_b08_segment_terminal_r01/fixtures.py",
    ],
    "display": [
        "work/ccz142_candidate_authority_r01/candidate_authority.py",
        "work/ccz142_candidate_authority_r01/shadow_fixtures.py",
        "work/ccz142_current_candidate_read_proof_r01/current_read_proof.py",
    ],
    "entry": [],
    "preview": [
        "work/ccz142_candidate_authority_r01/candidate_authority.py",
        "work/ccz142_candidate_authority_r01/shadow_fixtures.py",
        "work/ccz142_current_candidate_read_display_r01/card_render.py",
    ],
    "proof": [
        "work/ccz142_candidate_authority_r01/candidate_authority.py",
        "work/ccz142_candidate_authority_r01/shadow_fixtures.py",
        "work/ccz57_m3_b06_commit_core_r01/b06_contracts.py",
    ],
    "coverage": [
        "work/ccz142_current_candidate_read_proof_r01/current_read_proof.py",
        "work/ccz142_current_candidate_read_preview_r01/html_render.py",
        "work/ccz142_named_chapter_txt_card_r01/named_chapter.py",
        "work/ccz142_named_identity_store_r01/store_identity.py",
    ],
    "catalog": ["references/corpus-pointers.md", "references/book-meta/INDEX.md"],
    "vertical": [
        "work/ccz142_candidate_authority_r01/candidate_authority.py",
        "work/ccz142_candidate_authority_r01/shadow_fixtures.py",
        "work/ccz142_current_candidate_read_preview_r01/html_render.py",
        "work/ccz57_m3_b01_candidate_version_r03_5/fixtures.py",
    ],
    "card_identity": [
        "work/ccz142_current_candidate_read_display_r01/card_render.py",
        "work/ccz142_current_candidate_read_preview_r01/html_render.py",
        "work/ccz142_named_chapter_txt_card_r01/named_chapter.py",
    ],
    "named": [
        "work/ccz142_current_candidate_read_preview_r01/html_render.py",
        "work/ccz142_human_card_vertical_wire_r01/vertical_wire.py",
    ],
    "identity_read": [
        "work/ccz142_current_candidate_read_proof_r01/current_read_proof.py",
        "work/ccz142_current_candidate_read_preview_r01/html_render.py",
        "work/ccz142_named_chapter_txt_card_r01/named_chapter.py",
        "work/ccz142_named_identity_store_r01/store_identity.py",
    ],
    "identity_store": [
        "work/ccz142_current_candidate_read_display_r01/card_render.py",
        "work/ccz142_current_candidate_read_preview_r01/html_render.py",
        "work/ccz142_named_chapter_card_identity_r01/identity_card.py",
        "work/ccz142_named_chapter_txt_card_r01/named_chapter.py",
    ],
    "duty": [
        "work/ccz57_m3_b03_bound_evidence_read_r03_5/README.md",
        "work/ccz57_m3_b04_patch_atomic_group_r03_5/README.md",
        "work/ccz57_m3_b05_patch_route_r03_5/README.md",
        "work/ccz57_m3_b09_current_causal_hint_view_r01/README.md",
    ],
    "door": [
        "work/ccz142_current_candidate_read_proof_r01/current_read_proof.py",
        "work/ccz142_named_chapter_txt_card_r01/named_chapter.py",
        "work/ccz142_named_chapter_txt_card_r01/ALLOWLIST.json",
        "work/ccz57_m3_b01_candidate_version_r03_5/fixtures.py",
        "work/ccz57_m3_b05_patch_route_r03_5/b05_store.py",
        "work/ccz57_m3_b06_commit_core_r01/b06_store.py",
        "work/ccz57_m3_b06_commit_core_r01/b06_contracts.py",
        "work/ccz57_m3_b07_local_recovery_stop_r01/b07_store.py",
        "work/ccz57_m3_b08_segment_terminal_r01/b08_store.py",
        "work/ccz142_human_card_vertical_wire_r01/vertical_wire.py",
    ],
}


def expected_with_ccz180(path, existing):
    added = [
        CCZ180_TESTS[key]
        for key, paths in CCZ180_DIRECT_UPSTREAM.items()
        if path in paths
    ]
    return sorted(set(existing) | set(added))


def producer_first(path, expected):
    own = B_STAGE_OWN_TEST_BY_DEPENDENCY_PATH[path]
    return [own, *sorted(set(expected) - {own})]


def ccz180_plan(paths, *, flags=None):
    return test_impact.build_plan(spec(paths, flags=flags))


@pytest.mark.parametrize("extra", [[], ["governance/test_policy.json"]])
def test_shared_chapter_fixture_dispatches_every_direct_consumer(extra):
    fixture = "work/ccz142_human_card_vertical_wire_r01/synthetic_chapter.txt"
    plan = ccz180_plan([fixture, *extra])
    for key in (
        "vertical", "coverage", "card_identity", "named",
        "identity_read", "identity_store", "door",
    ):
        assert_individual_dispatch(plan, CCZ180_TESTS[key])


def assert_individual_dispatch(plan, test_path):
    matching = [step for step in plan["execution_steps"] if test_path in step["argv"]]
    # A Ruff argument or display-only selected_tests entry cannot satisfy this.
    assert [step["argv"] for step in matching] == [
        ["uv", "run", "--locked", "pytest", "-q", test_path]
    ]
    assert matching[0]["cwd"] == "repo_root"


@pytest.mark.parametrize("key,test_path", list(CCZ180_TESTS.items()))
def test_ccz180_test_and_own_python_changes_dispatch_original_test(key, test_path):
    # Each current Python file in this bounded component must call its own test.
    paths = sorted((ROOT / test_path).parent.glob("*.py"))
    for path in paths:
        changed = path.relative_to(ROOT).as_posix()
        plan = ccz180_plan([changed])
        # The test path itself also occurs in Ruff, so only inspect pytest steps.
        pytest_plan = {
            **plan,
            "execution_steps": [
                step for step in plan["execution_steps"] if step["argv"][3] == "pytest"
            ],
        }
        assert_individual_dispatch(pytest_plan, test_path)
        assert not plan["unknown_paths"]


@pytest.mark.parametrize("key", list(CCZ180_TESTS))
def test_ccz180_direct_upstream_changes_dispatch_consumer(key):
    for upstream in CCZ180_DIRECT_UPSTREAM[key]:
        assert (ROOT / upstream).is_file(), upstream
        assert_individual_dispatch(ccz180_plan([upstream]), CCZ180_TESTS[key])


@pytest.mark.parametrize(
    "extra,flags",
    [
        (["governance/test_policy.json"], []),
        (["unregistered/example.bin"], []),
        ([], ["test_collection_changed"]),
    ],
)
def test_ccz180_mixed_and_full_chain_keep_all_fourteen_original_tests(extra, flags):
    plan = ccz180_plan([*CCZ180_TESTS.values(), *extra], flags=flags)
    assert plan["scope"] == "full_chain"
    assert test_impact.PORTABLE_FULL_CHAIN_ARGV in [
        s["argv"] for s in plan["execution_steps"]
    ]
    pytest_plan = {
        **plan,
        "execution_steps": [
            step for step in plan["execution_steps"] if step["argv"][3] == "pytest"
        ],
    }
    for test_path in CCZ180_TESTS.values():
        assert_individual_dispatch(pytest_plan, test_path)


@pytest.mark.parametrize(
    "paths,flags",
    [
        (
            [
                "work/ccz57_m3_b01_candidate_version_r03_5/b01_contract.py",
                "work/ccz57_m3_b06_commit_core_r01/b06_contracts.py",
            ],
            [],
        ),
        (["work/ccz142_current_candidate_read_proof_r01/current_read_proof.py"], []),
        (
            ["work/ccz142_current_candidate_read_proof_r01/current_read_proof.py"],
            ["test_collection_changed"],
        ),
    ],
)
def test_ccz180_changed_components_precede_consumers(paths, flags):
    plan = ccz180_plan(paths, flags=flags)
    tests = [
        step["argv"][-1]
        for step in plan["execution_steps"]
        if step["step_id"].startswith("pytest-outside-default-")
    ]
    own = [
        test
        for test in tests
        if any(Path(path).parent == Path(test).parent for path in paths)
    ]
    assert own
    assert tests[: len(own)] == sorted(own)
    assert tests[len(own) :] == sorted(set(tests) - set(own))
    assert tests == [
        step["argv"][-1]
        for step in ccz180_plan(list(reversed(paths)), flags=flags)["execution_steps"]
        if step["step_id"].startswith("pytest-outside-default-")
    ]


def test_ccz180_browser_is_never_in_portable_pytest_steps():
    browser = "work/ccz142_current_candidate_read_entry_r01/test_entry_browser.py"
    plan = ccz180_plan([browser, *CCZ180_TESTS.values(), "governance/test_policy.json"])
    assert all(
        browser not in step["argv"]
        for step in plan["execution_steps"]
        if step["argv"][3] == "pytest"
    )
    assert test_impact.load_policy()["default_collection_root"] == "tests"


def test_ccz180_metadata_and_html_inputs_are_executable_triggers():
    cases = [
        ("entry", "打开人话结果卡.html"),
        ("entry", "SOURCE_SAMPLES.json"),
        ("entry", "samples/no_live_store.html"),
        ("catalog", "CATALOG.json"),
        ("catalog", "second_batch_gold_r01/ROW_VERDICTS.csv"),
        ("duty", "DUTY_FREEZE.json"),
        ("named", "ALLOWLIST.json"),
    ]
    for key, name in cases:
        path = str(Path(CCZ180_TESTS[key]).parent / name)
        assert (ROOT / path).is_file()
        assert_individual_dispatch(ccz180_plan([path]), CCZ180_TESTS[key])


if __name__ == "__main__":
    unittest.main()
