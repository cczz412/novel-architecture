from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z93_five_gold_gate.py"
SPEC = importlib.util.spec_from_file_location("z93_five_gold_gate", MODULE_PATH)
assert SPEC and SPEC.loader
z93 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z93)


class Z93FiveGoldGateTests(unittest.TestCase):
    def setUp(self) -> None:
        (ROOT / "TEMP").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="z93-test-", dir=ROOT / "TEMP")
        self.output = Path(self.temp.name) / "run"
        z93.prepare(self.output)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fill(self, path: Path, *, one_dispute: bool = False) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        for index, row in enumerate(data["rows"]):
            row["checks"] = {field: "pass" for field in z93.CHECK_FIELDS}
            row["disposition"] = "candidate_ready"
            row["major_issue"] = False
            row["reasoning"] = "原文上下文与四项要求一致。"
            row["original_evidence_excerpt"] = "用于测试的原文短引"
            if one_dispute and index == 0:
                row["checks"]["one_sentence_one_fact"] = "fail"
                row["disposition"] = "needs_modification"
                row["suggested_revision"] = "拆成两个独立事实。"
        z93.write_json(path, data)

    def test_prepare_locks_five_drafts_and_160_anchors(self) -> None:
        manifest = z93.read_json(self.output / "run_manifest.json")
        self.assertEqual(5, manifest["counts"]["book_total"])
        self.assertEqual(76, manifest["counts"]["candidate_part_total"])
        self.assertEqual(160, manifest["counts"]["anchor_total"])
        packet = z93.read_json(self.output / "review_packet.json")
        self.assertEqual(76, len(packet["rows"]))
        self.assertEqual(76, len({row["part_id"] for row in packet["rows"]}))

    def test_two_votes_only_send_disagreements_to_r3_and_finalize(self) -> None:
        paths = sorted((self.output / "reviews").glob("review_*.json"))
        for path in paths:
            self.fill(path, one_dispute=path.name == "review_R2_A.json")
        register = z93.build_disputes(self.output, paths)
        self.assertEqual(1, register["dispute_total"])
        target = register["disputes"][0]["R3"]
        target["checks"] = {field: "pass" for field in z93.CHECK_FIELDS}
        target["disposition"] = "candidate_ready"
        target["major_issue"] = False
        target["reasoning"] = "第三票只裁分歧，判定原粒度可保留。"
        target["original_evidence_excerpt"] = "用于测试的原文短引"
        adjudication = self.output / "reviews/review_R3_disputes.json"
        z93.write_json(adjudication, {"reviewer_id": "R3", "rows": [target]})
        result = z93.finalize(self.output, adjudication)
        self.assertEqual(76, result["counts"]["total"])
        self.assertEqual(1, result["counts"]["r3_adjudicated"])
        self.assertEqual(76, result["counts"]["candidate_ready"])
        self.assertFalse(result["counts"]["major_issue"])
        packaged = z93.package(self.output, adjudication, self.output / "report")
        self.assertEqual("codex_gate_complete_cursor_red_team_pending", packaged["status"])
        self.assertEqual(
            "pass_identical_twice",
            packaged["mechanical_double_run"]["status"],
        )
        handoff = z93.read_json(self.output / "cursor_red_team_handoff.json")
        self.assertEqual(6, handoff["artifact_total"])
        self.assertEqual("ready_not_executed", handoff["status"])
        self.assertTrue((self.output / "report/report_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
