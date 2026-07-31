from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from tools import novel_pipeline


class NovelPipelineTests(unittest.TestCase):
    @staticmethod
    def _invoke_help(arguments: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            try:
                code = novel_pipeline.main(arguments)
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, output.getvalue()

    def test_existing_commands_are_forwarded_without_rewriting(self) -> None:
        commands = [
            ["preflight", "--config", "config.json"],
            ["run", "--config", "config.json", "--resume", "--stages", "classify,verify"],
            ["register", "--kind", "material", "--batch", "B", "--item", "I", "--path", "p"],
            ["status", "--run-id", "R"],
            ["attest", "--run-id", "R", "--reviewer", "A", "--decision", "pass", "--review-file", "r"],
        ]
        for command in commands:
            with self.subTest(command=command), mock.patch.object(
                novel_pipeline, "zbatch_main", return_value=7
            ) as delegated:
                self.assertEqual(novel_pipeline.main(command), 7)
                delegated.assert_called_once_with(command)

    def test_empty_arguments_keep_the_legacy_zbatch_behavior(self) -> None:
        with mock.patch.object(
            novel_pipeline, "zbatch_main", return_value=6
        ) as delegated:
            self.assertEqual(novel_pipeline.main([]), 6)
        delegated.assert_called_once_with([])

    def test_governance_status_is_read_only(self) -> None:
        with mock.patch.object(novel_pipeline, "refresh") as refresh_mock:
            output = io.StringIO()
            with redirect_stdout(output):
                code = novel_pipeline.main(["governance", "status"])
        self.assertEqual(code, 0)
        refresh_mock.assert_not_called()
        self.assertIn(
            "第89道 DeepSeek V4 Pro 第3章强模型对照裸考",
            output.getvalue(),
        )
        self.assertIn("ROUTE-STRONG-MODEL-COMPARISON", output.getvalue())
        self.assertIn('"current_state"', output.getvalue())

    def test_governance_refresh_uses_index_generator(self) -> None:
        with mock.patch.object(novel_pipeline, "refresh", return_value={"ok": True}) as refresh_mock:
            output = io.StringIO()
            with redirect_stdout(output):
                code = novel_pipeline.main(["governance", "refresh"])
        self.assertEqual(code, 0)
        refresh_mock.assert_called_once_with()
        self.assertIn('"ok": true', output.getvalue())

    def test_inspect_namespace_uses_new_sidecar(self) -> None:
        with mock.patch.object(novel_pipeline, "inspector_main", return_value=3) as delegated:
            self.assertEqual(novel_pipeline.main(["inspect", "audit-rules"]), 3)
        delegated.assert_called_once_with(["audit-rules"])

    def test_test_plan_namespace_uses_new_sidecar(self) -> None:
        with mock.patch.object(novel_pipeline, "test_impact_main", return_value=4) as delegated:
            self.assertEqual(novel_pipeline.main(["test-plan", "--spec", "changes.json"]), 4)
        delegated.assert_called_once_with(["--spec", "changes.json"])

    def test_model_benchmark_namespace_uses_isolated_sidecar(self) -> None:
        with mock.patch.object(novel_pipeline, "model_benchmark_main", return_value=5) as delegated:
            self.assertEqual(novel_pipeline.main(["model-benchmark", "list"]), 5)
        delegated.assert_called_once_with(["list"])

    def test_catalog_namespace_uses_read_only_sidecar_without_rewriting(self) -> None:
        commands = [
            [],
            ["menu"],
            ["status", "--json"],
            ["models"],
            ["experiments", "--json"],
            ["artifacts"],
            ["slim", "--json"],
            ["all"],
        ]
        for command in commands:
            with self.subTest(command=command), mock.patch.object(
                novel_pipeline, "repository_catalog_main", return_value=8
            ) as delegated:
                self.assertEqual(novel_pipeline.main(["catalog", *command]), 8)
                delegated.assert_called_once_with(command)

    def test_top_level_help_lists_legacy_and_sidecar_entrypoints(self) -> None:
        with mock.patch.object(novel_pipeline, "zbatch_main") as legacy:
            code, output = self._invoke_help(["--help"])

        self.assertEqual(code, 0)
        legacy.assert_not_called()
        for command in (
            "preflight",
            "run",
            "register",
            "status",
            "attest",
            "governance",
            "inspect",
            "test-plan",
            "model-benchmark",
            "catalog",
        ):
            with self.subTest(command=command):
                self.assertIn(command, output)

    def test_catalog_help_exposes_only_named_views_and_json_switch(self) -> None:
        code, output = self._invoke_help(["catalog", "--help"])

        self.assertEqual(code, 0)
        for view in (
            "menu",
            "status",
            "models",
            "experiments",
            "artifacts",
            "slim",
            "all",
        ):
            with self.subTest(view=view):
                self.assertIn(view, output)
        self.assertIn("--json", output)
        for forbidden in (
            "--root",
            "--path",
            "--glob",
            "--destination",
            "--copy",
            "--move",
            "--delete",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, output)


if __name__ == "__main__":
    unittest.main()
