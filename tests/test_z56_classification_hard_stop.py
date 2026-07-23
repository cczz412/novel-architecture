from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from zbatch_modules import classify_rules  # noqa: E402


REPORT_DIR = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719"
EVIDENCE_PATH = REPORT_DIR / "第56道分类正门硬停证据.json"
DECISIONS_PATH = ROOT / "work/zbatch_decisions/Z56c_X01_ch1_20_main_control_decisions_v1.2.json"
CONTRACT_PATH = ROOT / "config/contracts/classify_rules_v1.2.json"
EXTRACT_RUN_DIR = ROOT / "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719"
CLASSIFY_RUN_DIR = ROOT / "runs/Z56c_X01_端到端全链体检_分类核锚20章_v1.0_20260719"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Z56ClassificationHardStopTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = load_json(EVIDENCE_PATH)
        cls.decisions = load_json(DECISIONS_PATH)
        cls.events = []
        for chapter in range(1, 21):
            cls.events.extend(
                load_json(
                    EXTRACT_RUN_DIR / f"01_extract/events/ch{chapter:04d}.json"
                )["events"]
            )

    def test_formal_extract_was_exactly_one_sample_per_chapter(self) -> None:
        extract = self.evidence["extract_run"]
        usage = extract["usage"]
        self.assertEqual(extract["status"], "completed")
        self.assertEqual(extract["calls_made"], 20)
        self.assertEqual(extract["chapters_completed"], 20)
        self.assertEqual(extract["event_total"], 233)
        self.assertEqual(usage["rows"], 20)
        self.assertEqual(usage["case_ids"], [f"ch{chapter:04d}" for chapter in range(1, 21)])
        self.assertEqual(usage["total_tokens"], 238556)

    def test_v1_2_gate_failure_is_reproducible(self) -> None:
        contract = classify_rules.load_contract(CONTRACT_PATH, project_root=ROOT)
        reasons = classify_rules.decision_reasons(
            self.decisions,
            run_id=self.decisions["run_id"],
            event_ids={event["event_id"] for event in self.events},
            contract=contract,
        )
        self.assertEqual(reasons, self.evidence["gate_failures"])
        self.assertEqual(len(reasons), 19)
        self.assertIn("t1_personal_risk_remains_open缺事件EV-C0013-14", reasons)
        self.assertIn("t1_probabilistic_stated_world_rule缺事件EV-C0013-15", reasons)

    def test_classification_compile_and_verify_were_not_run(self) -> None:
        self.assertEqual(self.evidence["status"], "hard_stop")
        self.assertFalse(CLASSIFY_RUN_DIR.exists())
        self.assertEqual(
            self.evidence["classification_draft"]["status"],
            "preflight_draft_not_executed",
        )
        self.assertEqual(
            self.evidence["diff_against_current_122"]["status"],
            "not_produced",
        )

    def test_chapter3_score_is_labeled_partial_and_conservative(self) -> None:
        score = self.evidence["chapter3_partial_extraction_score"]
        self.assertEqual(score["gold_on_chapter_total"], 14)
        self.assertEqual(score["complete_hit"], 2)
        self.assertEqual(score["partial_shadow"], 10)
        self.assertEqual(score["no_shadow"], 2)
        self.assertEqual(len(score["hindsight_excluded"]), 2)
        self.assertEqual(
            [row["event_id"] for row in score["pending_overflow"]],
            ["EV-C0003-01", "EV-C0003-08"],
        )

    def test_protected_assets_keep_their_frozen_hashes(self) -> None:
        protected = self.evidence["protected_state"]
        self.assertEqual(protected["status"], "pass")
        self.assertEqual(
            protected["sha256"]["default_registry"],
            "61bc6ca45fe450d382995b29dd998c9119ade2db6049d29963c83eee30c5f9da",
        )
        self.assertEqual(
            protected["sha256"]["current_122"],
            "dafa16901a6edb5018a5176f3f5f7388273e72051def7fe4e997489d01e804ba",
        )
        self.assertEqual(
            protected["sha256"]["classify_rules"],
            sha256(CONTRACT_PATH),
        )


if __name__ == "__main__":
    unittest.main()
