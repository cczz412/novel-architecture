from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tools.zbatch_modules import nonthinking_pilot


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/diagnostics/Z01h_X01_非思考模式_5章_v1.json"


class NonThinkingPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = nonthinking_pilot.read_json(CONFIG_PATH)

    def isolated_config(self) -> dict:
        """给要求新运行目录的测试分配一次性夹具，不碰正式 Z01h。"""

        config = copy.deepcopy(self.config)
        marker = uuid.uuid4().hex
        config["run_id"] = f"UNIT_Z01H_PREFLIGHT_{marker}"
        config["permit_path"] = (
            f"work/zbatch_nonthinking/permits/UNIT_Z01H_PREFLIGHT_{marker}.json"
        )
        for group_name in ("protected_chain", "experiment_code"):
            for ref in config[group_name].values():
                path = ROOT / ref["path"]
                ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return config

    def test_preflight_is_zero_call_and_pins_five_chapters(self) -> None:
        result = nonthinking_pilot.preflight(self.isolated_config(), ROOT)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual([row["chapter"] for row in result["chapters"]], [3, 4, 5, 13, 19])
        self.assertTrue(all(row["request_body_single_variable"] == "pass" for row in result["chapters"]))

    def test_request_body_diff_only_removes_reasoning_effort(self) -> None:
        built, _, _ = nonthinking_pilot.build_chapter_input(self.config, ROOT, 3)
        audit = nonthinking_pilot.transport_audit(self.config, ROOT, built["messages"])
        self.assertEqual(audit["request_body_diff"]["removed_keys"], ["reasoning_effort"])
        self.assertEqual(audit["request_body_diff"]["added_keys"], [])
        self.assertEqual(audit["request_body_diff"]["changed_keys"], [])

    def test_candidate_contract_is_unverified_and_omits_effort(self) -> None:
        bundle = nonthinking_pilot._load_bundle(self.config, ROOT)
        contract = nonthinking_pilot.candidate_contract(bundle)
        self.assertIsNone(contract.reasoning_effort)
        self.assertEqual(contract.status, "candidate_unverified")
        self.assertEqual(contract.temperature, 0.2)
        self.assertEqual(contract.max_tokens, 16000)
        self.assertEqual(contract.n, 1)

    def test_default_registry_and_commit_marker_are_bound(self) -> None:
        audit = nonthinking_pilot.verify_default_activation(self.config, ROOT)
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(audit["default_id"], "zbatch-v1.2-full-chain")
        self.assertEqual(audit["pin_resolution"], "compatible_successor")

    def test_baseline_snapshot_uses_real_usage_rows(self) -> None:
        snapshot = nonthinking_pilot.baseline_snapshot(self.config, ROOT)
        self.assertEqual(len(snapshot["chapters"]), 5)
        self.assertGreater(snapshot["metrics"]["total_tokens"], 0)
        self.assertGreater(snapshot["metrics"]["reasoning_tokens"], 0)
        self.assertGreater(snapshot["metrics"]["elapsed_ms"], 0)

    def test_baseline_usage_source_requires_exact_case(self) -> None:
        bad = copy.deepcopy(self.config["baseline_usage_sources"][0])
        bad["case_id"] = "missing"
        with self.assertRaisesRegex(nonthinking_pilot.NonThinkingPilotError, "匹配行数异常"):
            nonthinking_pilot.usage_row_from_source(ROOT, bad, chapter=3)

    def test_artifact_paths_cannot_escape(self) -> None:
        bad = copy.deepcopy(self.config)
        bad["run_id"] = "../outbox/escaped"
        with self.assertRaisesRegex(nonthinking_pilot.NonThinkingPilotError, "run_id"):
            nonthinking_pilot.validate_artifact_paths(bad, ROOT)
        bad = copy.deepcopy(self.config)
        bad["permit_path"] = "outbox/escaped.json"
        with self.assertRaisesRegex(nonthinking_pilot.NonThinkingPilotError, "调用证"):
            nonthinking_pilot.validate_artifact_paths(bad, ROOT)

    def test_report_output_cannot_reach_outbox(self) -> None:
        with self.assertRaisesRegex(nonthinking_pilot.NonThinkingPilotError, "只能写入"):
            nonthinking_pilot.resolve_report_output(ROOT, "outbox/forbidden.json")

    def test_tree_fingerprint_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp:
            folder = Path(temp)
            path = folder / "a.txt"
            path.write_text("a", encoding="utf-8")
            before = nonthinking_pilot.tree_fingerprint(folder)
            path.write_text("b", encoding="utf-8")
            after = nonthinking_pilot.tree_fingerprint(folder)
        self.assertEqual(before["file_count"], 1)
        self.assertNotEqual(before["sha256"], after["sha256"])

    def test_permit_refuses_when_key_is_absent(self) -> None:
        config = self.isolated_config()
        saved = nonthinking_pilot.preflight(config, ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp:
            saved_path = Path(temp) / "preflight.json"
            nonthinking_pilot.write_json(saved_path, saved)
            with mock.patch.object(nonthinking_pilot, "preflight_path", return_value=saved_path):
                with mock.patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(nonthinking_pilot.NonThinkingPilotError, "缺 SENSENOVA_API_KEY"):
                        nonthinking_pilot.permit_document(config, ROOT)

    def test_reasoning_tokens_are_read_from_usage(self) -> None:
        count, reported = nonthinking_pilot._reasoning_tokens(
            {"completion_tokens_details": {"reasoning_tokens": 7}}
        )
        self.assertEqual((count, reported), (7, True))
        self.assertEqual(nonthinking_pilot._reasoning_tokens({}), (0, False))

    def test_actual_cost_includes_called_failed_chapter(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp:
            run_dir = Path(temp)
            (run_dir / "usage.jsonl").write_text(
                json.dumps(
                    {
                        "case_id": "0003",
                        "elapsed_ms": 1234,
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 20,
                            "total_tokens": 120,
                            "completion_tokens_details": {"reasoning_tokens": 7},
                            "prompt_tokens_details": {"cached_tokens": 3}
                        }
                    }
                ) + "\n",
                encoding="utf-8",
            )
            totals = nonthinking_pilot.actual_cost_totals(run_dir)
        self.assertEqual(totals["usage_row_count"], 1)
        self.assertEqual(totals["total_tokens"], 120)
        self.assertEqual(totals["reasoning_tokens"], 7)
        self.assertEqual(totals["elapsed_ms"], 1234)

    def test_outer_failure_recovers_usage_cost(self) -> None:
        config = copy.deepcopy(self.config)
        marker = uuid.uuid4().hex
        config["run_id"] = f"UNIT_Z01H_OUTER_{marker}"
        config["permit_path"] = f"work/zbatch_nonthinking/permits/UNIT_Z01H_OUTER_{marker}.json"
        run_dir = ROOT / "runs" / config["run_id"]

        def fail_after_usage(*_args, **_kwargs):
            run_dir.mkdir(parents=True)
            (run_dir / "call_attempts.jsonl").write_text(
                json.dumps({"case_id": "0003", "attempt": 1}) + "\n",
                encoding="utf-8",
            )
            nonthinking_pilot.write_json(
                run_dir / "hard_stop.json", {"chapter": 3, "is_truncation": False}
            )
            (run_dir / "usage.jsonl").write_text(
                json.dumps(
                    {
                        "elapsed_ms": 999,
                        "usage": {
                            "prompt_tokens": 80,
                            "completion_tokens": 20,
                            "total_tokens": 100,
                            "completion_tokens_details": {"reasoning_tokens": 0},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            raise nonthinking_pilot.NonThinkingPilotError("模拟收尾失败")

        try:
            with mock.patch.object(nonthinking_pilot, "_run_core", side_effect=fail_after_usage):
                result = nonthinking_pilot.run(config, ROOT)
            self.assertEqual(result["status"], "hard_stopped")
            self.assertEqual(result["chapters_failed"], [3])
            self.assertEqual(result["cost_accounting"]["total_tokens"], 100)
            self.assertEqual(result["cost_accounting"]["elapsed_ms"], 999)
        finally:
            import shutil

            shutil.rmtree(run_dir, ignore_errors=True)
            (ROOT / config["permit_path"]).unlink(missing_ok=True)

    def test_config_contains_no_unfilled_sha(self) -> None:
        self.assertNotIn("TO_FILL", json.dumps(self.config, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
