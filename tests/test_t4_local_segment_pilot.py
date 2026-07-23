from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.zbatch_modules import t4_local_segment


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config/diagnostics/Z00z_X01_局部段覆盖试点_v1.json"


class T4LocalSegmentPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # 正式试点清单保留当时的 SHA；回归测试在内存里绑定当前等价实现。
        cls.manifest = copy.deepcopy(t4_local_segment.read_json(MANIFEST_PATH))
        for group_name in ("protected_current_chain", "t4_gate_code"):
            for ref in cls.manifest[group_name].values():
                ref["sha256"] = t4_local_segment.sha256_file(ROOT / ref["path"])

    def test_prompt_is_exactly_one_added_line(self) -> None:
        audit = t4_local_segment.audit_prompt_change(self.manifest, ROOT)
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(audit["other_line_changes"], 0)
        self.assertTrue(audit["cache_layout_isomorphic"])

    def test_current_path_replays_old_twenty_chapters_exactly(self) -> None:
        audit = t4_local_segment.baseline_equivalence_audit(self.manifest, ROOT)
        self.assertEqual(audit["model_calls"], 0)
        self.assertEqual(audit["chapters_checked"], 20)
        self.assertEqual(audit["chapters_passed"], 20)
        self.assertEqual(audit["pilot_request_single_variable"]["status"], "pass")
        self.assertEqual(audit["pilot_request_single_variable"]["chapters_checked"], 5)

    def test_pilot_configs_keep_only_prompt_as_model_variable(self) -> None:
        base = t4_local_segment.read_json(ROOT / self.manifest["base_config"]["path"])
        for chapter in self.manifest["pilot_chapters"]:
            config = t4_local_segment.build_pilot_config(base, self.manifest, chapter)
            self.assertEqual(config["runner_sha256"], base["runner_sha256"])
            self.assertEqual(config["provider_config_sha256"], base["provider_config_sha256"])
            self.assertEqual(config["stages"], ["extract"])
            self.assertEqual(config["chapter_start"], chapter)
            self.assertEqual(config["chapter_end"], chapter)
            self.assertEqual(config["max_calls"], 3)
            self.assertEqual(
                config["prompts"]["neutral_extract"],
                self.manifest["prompt_change"]["new_path"],
            )
            permit = t4_local_segment.permit_relative_path(chapter)
            self.assertIn(permit, config["spec_snapshots"])
            self.assertEqual(
                config["pinned_sha256"][permit],
                t4_local_segment.permit_sha256(self.manifest, chapter, config["run_id"]),
            )

    def test_anchor_range_rejects_reverse_order(self) -> None:
        self.assertEqual(t4_local_segment.anchor_range("E0002", "E0004"), ["E0002", "E0003", "E0004"])
        with self.assertRaises(t4_local_segment.T4PilotError):
            t4_local_segment.anchor_range("E0004", "E0002")

    def test_target_gate_requires_every_primary_anchor(self) -> None:
        targets = json.loads((ROOT / self.manifest["coverage_targets"]["path"]).read_text(encoding="utf-8"))["targets"]
        target = next(row for row in targets if row["id"] == "S-L01")
        catalog = {
            "E0208": "也许罗塞尔是穿越者前辈吧",
            "E0209": "穿越者前辈吧，这个判断仍待验证",
        }
        complete = {
            4: {
                "events": [
                    {
                        "event_id": "EV-C0004-01",
                        "event": "克莱恩怀疑罗塞尔也是穿越者",
                        "anchors": [{"anchor_id": "E0208"}, {"anchor_id": "E0209"}],
                    }
                ]
            }
        }
        result = t4_local_segment.evaluate_target(target, complete, {4: catalog})
        self.assertTrue(result["pass"])
        incomplete = copy.deepcopy(complete)
        incomplete[4]["events"][0]["anchors"].pop()
        result = t4_local_segment.evaluate_target(target, incomplete, {4: catalog})
        self.assertFalse(result["pass"])
        self.assertEqual(result["missing_anchor_ids"], ["E0209"])

    def test_linked_event_must_be_one_coherent_event(self) -> None:
        targets = json.loads((ROOT / self.manifest["coverage_targets"]["path"]).read_text(encoding="utf-8"))["targets"]
        target = next(row for row in targets if row["id"] == "S-L02")
        primary_ids = t4_local_segment.anchor_range("E0048", "E0062")
        catalogs = {
            4: {"E0174": "克莱恩听见免费占卜邀请", "E0212": "他同意免费占卜的安排", "E0214": "双方约定稍后开始占卜"},
            5: {anchor_id: f"第{anchor_id}段占卜证据" for anchor_id in primary_ids},
        }
        catalogs[5]["E0048"] = "这张象征过去，牌面已经揭开"
        catalogs[5]["E0062"] = "牌面最后指向高位的愚者"
        documents = {
            4: {
                "events": [
                    {
                        "event_id": "EV-C0004-09",
                        "event": "克莱恩同意免费占卜",
                        "anchors": [{"anchor_id": value} for value in ("E0174", "E0212", "E0214")],
                    }
                ]
            },
            5: {
                "events": [
                    {
                        "event_id": "EV-C0005-01",
                        "event": "免费占卜实际执行",
                        "anchors": [{"anchor_id": value} for value in primary_ids],
                    }
                ]
            },
        }
        result = t4_local_segment.evaluate_target(target, documents, catalogs)
        self.assertTrue(result["pass"])
        self.assertEqual(result["linked_events"][0]["coherent_event_ids"], ["EV-C0004-09"])

        split = copy.deepcopy(documents)
        split[4]["events"] = [
            {
                "event_id": f"EV-C0004-{index:02d}",
                "event": "克莱恩同意免费占卜" if index == 1 else "占卜相关片段",
                "anchors": [{"anchor_id": anchor_id}],
            }
            for index, anchor_id in enumerate(("E0174", "E0212", "E0214"), 1)
        ]
        result = t4_local_segment.evaluate_target(target, split, catalogs)
        self.assertFalse(result["pass"])
        self.assertEqual(result["linked_events"][0]["coherent_event_ids"], [])

    def test_attempt_ledger_rejects_two_first_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "call_attempts.jsonl"
            rows = [
                {"call_number": 1, "stage": "neutral_extract", "case_id": "ch0003", "attempt": 1, "request_sha256": "a" * 64},
                {"call_number": 2, "stage": "neutral_extract", "case_id": "ch0003", "attempt": 1, "request_sha256": "a" * 64},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            result = t4_local_segment.parse_attempt_rows(path, case_id="ch0003", max_attempts=3)
            self.assertEqual(result["status"], "fail")
            self.assertFalse(result["checks"]["one_logical_sample"])

    def test_failed_evaluation_returns_nonzero(self) -> None:
        self.assertEqual(t4_local_segment.result_exit_code("evaluate", {"pilot_pass": False}), 2)
        self.assertEqual(t4_local_segment.result_exit_code("evaluate", {"pilot_pass": True}), 0)
        self.assertEqual(t4_local_segment.result_exit_code("run-chapter", {"status": "fail"}), 2)

    def test_generic_runner_preflight_is_blocked_without_one_time_permit(self) -> None:
        config_path = ROOT / "config/batches/Z00z_X01_局部段覆盖试点_ch0003_v1.0.json"
        config = t4_local_segment.read_json(config_path)
        permit_path = ROOT / t4_local_segment.permit_relative_path(3)
        self.assertFalse(permit_path.exists())
        self.assertIn(t4_local_segment.permit_relative_path(3), config["spec_snapshots"])
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/zbatch.py"), "preflight", "--config", str(config_path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('"preflight": "fail"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
