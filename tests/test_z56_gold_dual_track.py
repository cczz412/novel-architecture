from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719"
GOLD_V1 = ROOT / "reports/Z52续令_候选桶语义清洗与金标转换_20260719/第3章结构层金标v1.json"
GOLD_V1_1 = REPORT_DIR / "第3章结构层金标v1.1.json"
REPEAT_RECEIPT = REPORT_DIR / "件一连续两次一致回执.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Z56GoldDualTrackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = load_json(GOLD_V1_1)

    def test_v1_is_frozen_predecessor(self) -> None:
        self.assertEqual(
            sha256(GOLD_V1),
            "6d826b103657d5326224c8ef925138b98e0c23578bd7ed1864cd763f733a6488",
        )
        self.assertEqual(self.gold["predecessor"]["sha256"], sha256(GOLD_V1))
        self.assertEqual(self.gold["predecessor"]["mutation"], "none")

    def test_fourteen_base_items_all_have_on_chapter_part(self) -> None:
        items = self.gold["layered_items"]
        self.assertEqual(len(items), 14)
        self.assertTrue(
            all(
                any(
                    part["layer"] == "当章可知"
                    and part["score_in_single_chapter"] is True
                    for part in item["parts"]
                )
                for item in items
            )
        )

    def test_only_two_later_halves_are_hindsight(self) -> None:
        items = self.gold["layered_items"]
        split_items = [item["item_id"] for item in items if len(item["parts"]) == 2]
        hindsight = [
            part
            for item in items
            for part in item["parts"]
            if part["layer"] == "回看件"
        ]
        self.assertEqual(split_items, ["GOLD-C0003-12", "GOLD-C0003-14"])
        self.assertEqual(len(hindsight), 2)
        self.assertTrue(all(part["score_in_single_chapter"] is False for part in hindsight))

    def test_open_mystery_stays_on_chapter(self) -> None:
        mystery = self.gold["layered_items"][8]
        self.assertEqual(mystery["source_id"], "Z49-CAND-C0003-01")
        self.assertEqual([part["layer"] for part in mystery["parts"]], ["当章可知"])

    def test_window_is_19_blocks_50_anchors_within_chapter_200(self) -> None:
        audit = self.gold["window_audit"]
        blocks = audit["evidence_blocks"]
        self.assertEqual(len(blocks), 19)
        self.assertEqual(sum(len(block["anchors"]) for block in blocks), 50)
        self.assertGreaterEqual(min(block["chapter"] for block in blocks), 1)
        self.assertLessEqual(max(block["chapter"] for block in blocks), 200)
        self.assertEqual(audit["out_of_window_evidence_ids"], [])

    def test_scoring_contract_excludes_predecessor_claim_and_window_audit(self) -> None:
        contract = self.gold["consumer_contract"]
        self.assertEqual(
            contract["single_chapter_scoring_source"],
            "layered_items[].parts[layer=当章可知]",
        )
        self.assertIn(
            "layered_items[].predecessor_claim_audit",
            contract["forbidden_scoring_sources"],
        )
        self.assertTrue(
            all(
                item["predecessor_claim_audit"]["usage"]
                == "traceability_only_not_for_scoring"
                for item in self.gold["layered_items"]
            )
        )

    def test_window_anchor_identity_is_chapter_local_and_unique(self) -> None:
        keys = [
            anchor["identity_key"]
            for block in self.gold["window_audit"]["evidence_blocks"]
            for anchor in block["anchors"]
        ]
        self.assertEqual(len(keys), 50)
        self.assertEqual(len(set(keys)), 50)
        self.assertTrue(all(key.startswith("ch") and ":E" in key for key in keys))

    def test_two_readbacks_are_byte_identical(self) -> None:
        receipt = load_json(REPEAT_RECEIPT)
        self.assertEqual(receipt["status"], "pass")
        self.assertTrue(receipt["identical"])
        self.assertEqual(receipt["runs"], 2)
        self.assertEqual(receipt["run_1"], receipt["run_2"])
        self.assertEqual(receipt["run_2"]["gold_v1_1_sha256"], sha256(GOLD_V1_1))
        self.assertEqual(
            receipt["run_2"]["verdict_sha256"],
            sha256(REPORT_DIR / "第3章金标双轨逐条判词.md"),
        )
        self.assertEqual(
            receipt["run_2"]["validation_sha256"],
            sha256(REPORT_DIR / "件一机械验收.json"),
        )


if __name__ == "__main__":
    unittest.main()
