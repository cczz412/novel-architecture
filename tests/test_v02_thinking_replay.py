from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import v02_gate_contracts as gates
from tools import v02_thinking_replay as replay


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "v02_thinking_replay.py"
BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B3_thinking_replay"
)


class V02ThinkingReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frozen = replay.freeze_inputs()
        cls.artifacts = replay.build_artifacts_from_frozen(cls.frozen)
        cls.manifest = json.loads(cls.artifacts["manifest.json"])
        cls.acceptance = json.loads(cls.artifacts["acceptance_receipt.json"])
        cls.replay_results = {
            thinking_id: json.loads(
                cls.artifacts[f"replay_results/{thinking_id}.json"]
            )
            for thinking_id in (f"T{index:02d}" for index in range(1, 13))
        }
        cls.regression_results = {
            path: json.loads(data)
            for path, data in cls.artifacts.items()
            if path.startswith("regression_results/")
        }

    def test_input_freeze_locks_twelve_sources_before_analysis(self) -> None:
        lock = self.frozen.input_lock
        self.assertTrue(lock["freeze_before_trace_decode"])
        rows = lock["inventory"]["sources"]
        self.assertEqual([row["thinking_id"] for row in rows], [
            f"T{index:02d}" for index in range(1, 13)
        ])
        self.assertEqual(len(rows), 12)
        self.assertEqual(
            {row["shared_copy_relation"] for row in rows},
            {"BYTE_IDENTICAL", "TRAILING_LF_ONLY"},
        )
        relation_counts = {
            relation: sum(
                row["shared_copy_relation"] == relation for row in rows
            )
            for relation in {"BYTE_IDENTICAL", "TRAILING_LF_ONLY"}
        }
        self.assertEqual(
            relation_counts,
            {"BYTE_IDENTICAL": 2, "TRAILING_LF_ONLY": 10},
        )
        for row in rows:
            self.assertEqual(len(row["canonical_source_sha256"]), 64)
            self.assertEqual(len(row["shared_copy_sha256"]), 64)

    def test_b2_bundle_is_reused_read_only_with_frozen_authority(self) -> None:
        self.assertEqual(self.frozen.b2_check["result"], "PASS")
        self.assertEqual(
            self.frozen.b2_contract_hash,
            "6041b9822b3b8beea5f0d45f59f0d9276cfe7e7e31b22a370c1a71e342e69013",
        )
        self.assertEqual(
            self.manifest["b2_contract"]["producer_selfcheck_authority"],
            "DIAGNOSTIC_ONLY_NOT_GREEN_TICKET",
        )
        required_codes = {
            *replay.BASE_B2_FAILURE_CODES,
            *(
                definition["b2_failure_code"]
                for definition in replay.FINDING_DEFINITIONS.values()
            ),
        }
        self.assertTrue(required_codes.issubset(gates.FINE_CODES))

    def test_four_regression_classes_are_blocked_four_of_four(self) -> None:
        by_category = {
            result["category"]: result for result in self.regression_results.values()
        }
        self.assertEqual(
            set(by_category),
            {
                "path_resolution_error",
                "snapshot_count_drift",
                "producer_five_layer_full_score",
                "sop_ucr_divergence",
            },
        )
        self.assertTrue(all(result["blocked"] for result in by_category.values()))
        self.assertEqual(
            {result["result"] for result in by_category.values()},
            {"BLOCKED_AS_EXPECTED"},
        )
        self.assertEqual(
            self.acceptance["checks"]["required_regression_classes_blocked"],
            4,
        )

    def test_path_errors_in_t01_and_t10_are_not_silently_passed(self) -> None:
        for thinking_id in ("T01", "T10"):
            result = self.replay_results[thinking_id]
            finding = next(
                item
                for item in result["findings"]
                if item["finding_code"] == "B3_PATH_RESOLUTION_ERROR"
            )
            self.assertEqual(
                finding["b2_failure_code"],
                "S6_FIVE_LAYER_RECOMPUTE_FAILED",
            )
            self.assertGreaterEqual(finding["details"]["path_error_count"], 1)
            self.assertEqual(result["status"], "HARD_STOP")

    def test_t04_detects_the_same_round_96_99_100_drift(self) -> None:
        finding = next(
            item
            for item in self.replay_results["T04"]["findings"]
            if item["finding_code"] == "B3_SNAPSHOT_COUNT_DRIFT"
        )
        self.assertEqual(finding["details"]["observed_counts"], [96, 99, 100])
        self.assertEqual(
            finding["b2_failure_code"],
            "S6_SNAPSHOT_COUNT_MISMATCH",
        )

    def test_producer_full_score_cannot_become_program_green(self) -> None:
        finding = next(
            item
            for item in self.replay_results["T02"]["findings"]
            if item["finding_code"] == "B3_PRODUCER_FIVE_LAYER_FULL_SCORE"
        )
        self.assertEqual(
            finding["details"]["metrics"],
            {
                "asr_full": 1.0,
                "fcr": 1.0,
                "qcr_full": 1.0,
                "sop": 1.0,
                "ucr": 1.0,
            },
        )
        self.assertEqual(
            finding["b2_failure_code"],
            "R_PRODUCER_SELF_CHECK_AS_PROGRAM_GREEN",
        )

    def test_t07_sop_one_does_not_hide_ucr_00625(self) -> None:
        finding = next(
            item
            for item in self.replay_results["T07"]["findings"]
            if item["finding_code"] == "B3_SOP_UCR_DIVERGENCE_NOT_GREEN"
        )
        self.assertEqual(finding["details"]["sop"], 1.0)
        self.assertEqual(finding["details"]["ucr"], 0.0625)
        self.assertEqual(
            finding["b2_failure_code"],
            "R_PRODUCER_SELF_CHECK_AS_PROGRAM_GREEN",
        )

    def test_all_twelve_results_stay_isolated_and_hard_stopped(self) -> None:
        self.assertEqual(set(self.replay_results), {
            f"T{index:02d}" for index in range(1, 13)
        })
        for result in self.replay_results.values():
            self.assertEqual(result["status"], "HARD_STOP")
            self.assertFalse(result["activation_allowed"])
            self.assertTrue(result["freeze_verified_before_analysis"])
            self.assertEqual(result["model_api_calls"], 0)
            self.assertEqual(result["network_requests"], 0)
            self.assertTrue(
                set(replay.BASE_B2_FAILURE_CODES).issubset(
                    result["b2_failure_codes"]
                )
            )
        self.assertEqual(
            self.acceptance["result"],
            "PASS_4_OF_4_BLOCKED_12_OF_12_HARD_STOPPED",
        )

    def test_fixture_lineage_is_verified_against_frozen_full_text(self) -> None:
        for result in self.regression_results.values():
            self.assertTrue(result["source_lineage"])
            for row in result["source_lineage"]:
                self.assertEqual(row["lineage_check"], "PASS")
                self.assertEqual(len(row["source_sha256"]), 64)
        self.assertEqual(
            self.regression_results[
                "regression_results/B3-REG-SELF-SCORE-001.json"
            ]["supporting_lineage"][0]["lineage_check"],
            "PASS",
        )

    def test_checked_in_candidate_matches_deterministic_builder(self) -> None:
        for relative_path, expected in self.artifacts.items():
            path = BUNDLE_DIR / relative_path
            self.assertTrue(path.is_file(), relative_path)
            self.assertEqual(path.read_bytes(), expected, relative_path)
        checked = replay.check_bundle(BUNDLE_DIR)
        self.assertEqual(checked["result"], "PASS")
        self.assertEqual(checked["source_replay_count"], 12)
        self.assertEqual(checked["hard_stopped_count"], 12)
        self.assertEqual(checked["regression_blocked"], 4)

    def test_double_run_receipt_is_byte_identical(self) -> None:
        receipt_path = BUNDLE_DIR / "double_run_receipt.json"
        self.assertTrue(receipt_path.is_file())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertTrue(receipt["freeze_once_before_two_runs"])
        self.assertTrue(receipt["byte_identical"])
        self.assertEqual(
            receipt["pass1_tree_sha256"],
            receipt["pass2_tree_sha256"],
        )
        self.assertEqual(
            receipt["pass1_tree_sha256"],
            receipt["target_tree_sha256"],
        )

    def test_cli_build_validate_and_double_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = Path(tmp) / "bundle"
            built = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "build",
                    "--output-dir",
                    str(bundle_dir),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(built.stdout)["result"], "BUILT")
            validated = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "validate-bundle",
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(validated.stdout)["result"], "PASS")
            double_run = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "double-run",
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(json.loads(double_run.stdout)["byte_identical"])

    def test_tool_imports_no_network_client(self) -> None:
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
        self.assertTrue(imported_roots.isdisjoint(forbidden))
        self.assertEqual(self.manifest["scope"]["model_api_calls"], 0)
        self.assertEqual(self.manifest["scope"]["network_requests"], 0)


if __name__ == "__main__":
    unittest.main()
