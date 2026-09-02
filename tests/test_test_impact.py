from __future__ import annotations

from copy import deepcopy
import unittest
from pathlib import Path

from tools import test_impact


ROOT = Path(__file__).resolve().parents[1]
PR_GATE_WORKFLOW = ROOT / ".github/workflows/pr-gate.yml"
B09_COMPONENT_ROOT = "work/ccz57_m3_b09_current_causal_hint_view_r01"
B09_DIRECTED_TEST = f"{B09_COMPONENT_ROOT}/test_current_causal_hint_view.py"


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


if __name__ == "__main__":
    unittest.main()
