from __future__ import annotations

import unittest

from tools import test_impact


def spec(paths: list[str], *, flags: list[str] | None = None, contract_changes: list[dict] | None = None) -> dict:
    return {
        "contract_version": test_impact.SPEC_CONTRACT,
        "change_id": "CHANGE-1",
        "changed_paths": paths,
        "flags": flags or [],
        "contract_changes": contract_changes or [],
    }


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
        self.assertIn("ruff check tools/demo_score_helper.py", plan["commands"])

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
        self.assertIn("ruff check tools/pipeline_inspector.py", plan["commands"])
        self.assertEqual(plan["scope"], "full_chain")

    def test_unified_entry_change_runs_full_chain(self) -> None:
        plan = test_impact.build_plan(
            spec(["tools/novel_pipeline.py"], flags=["unified_entry_changed"]),
            policy=self.policy,
            registry=self.registry,
        )
        self.assertTrue(plan["full_chain"])
        self.assertIn("ruff check tools/novel_pipeline.py", plan["commands"])

    def test_unknown_path_fails_safe_to_full_chain(self) -> None:
        plan = test_impact.build_plan(
            spec(["mystery/unknown.bin"]), policy=self.policy, registry=self.registry
        )
        self.assertTrue(plan["full_chain"])
        self.assertEqual(plan["unknown_paths"], ["mystery/unknown.bin"])


if __name__ == "__main__":
    unittest.main()
