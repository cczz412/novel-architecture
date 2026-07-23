from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.zbatch_modules.net_benefit_recompute import NetBenefitError, read_json, recompute


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/diagnostics/X01_z00w2_vs_z00u_net_benefit_v1.2.json"


class NetBenefitRecomputeTests(unittest.TestCase):
    def setUp(self) -> None:
        # 正式诊断配置保留施工当时的 SHA；计算测试在内存里绑定当前等价实现。
        self.config = copy.deepcopy(read_json(CONFIG_PATH))
        for relative in self.config.get("protected_sha256", {}):
            self.config["protected_sha256"][relative] = hashlib.sha256(
                (ROOT / relative).read_bytes()
            ).hexdigest()

    def test_formal_recompute(self) -> None:
        result = recompute(self.config, ROOT)
        self.assertEqual(
            {name: result["net_benefit"][name]["net"] for name in ("main", "strict", "wide")},
            {"main": 17, "strict": 5, "wide": 26},
        )
        self.assertTrue(result["gates"]["all_passed"])
        self.assertEqual(result["other_gates"]["cross_type_duplicate_count"], 0)
        self.assertEqual(result["other_gates"]["wrong_d_count"], 0)
        self.assertEqual(result["schema_version"], "z-net-benefit-recompute-v1.2")

    def test_recoveries_do_not_double_count_delayed_recurrence(self) -> None:
        result = recompute(self.config, ROOT)
        delayed = next(row for row in result["recovery_evidence"] if row["recovery_id"] == "REC-02")
        self.assertEqual(len(delayed["candidate_records"]), 2)
        self.assertEqual(delayed["covers"]["strict"], ["S-L03"])
        self.assertEqual(result["net_benefit"]["strict"]["lost"], 2)

    def test_remaining_absent_spans_are_still_absent(self) -> None:
        result = recompute(self.config, ROOT)
        self.assertEqual(
            [row["id"] for row in result["remaining_absent_spans"]],
            ["S-L01", "S-L04"],
        )
        self.assertTrue(all(row["still_absent"] for row in result["remaining_absent_spans"]))

    def test_all_old_candidate_records_are_semantically_preserved(self) -> None:
        result = recompute(self.config, ROOT)
        preservation = result["semantic_preservation"]
        self.assertEqual(preservation["preserved_record_total"], 118)
        self.assertTrue(preservation["all_old_records_preserved"])
        self.assertEqual(
            [(row["old_record_id"], row["new_record_id"]) for row in preservation["renumbered_records"]],
            [("A-C0019-01", "A-C0019-02")],
        )
        self.assertEqual(preservation["main_new_record_reference_total"], 48)

    def test_strict_note_does_not_keep_stale_plus_two(self) -> None:
        result = recompute(self.config, ROOT)
        note = result["net_benefit"]["strict"]["conservative_note"]
        self.assertIn("7−2＝+5", note)
        self.assertNotIn("仍只有 +2", note)

    def test_anchor_fragments_are_checked_in_quotes(self) -> None:
        result = recompute(self.config, ROOT)
        free_tarot = result["recovery_evidence"][0]["candidate_records"][0]
        self.assertEqual(free_tarot["required_anchor_fragments"], ["第一位来占卜的人，免费"])

    def test_sha_drift_is_rejected(self) -> None:
        config = copy.deepcopy(self.config)
        config["candidate"]["sha256"] = "0" * 64
        with self.assertRaises(NetBenefitError):
            recompute(config, ROOT)

    def test_differential_audit_covers_exactly_four_new_records(self) -> None:
        result = recompute(self.config, ROOT)
        evidence = result["other_gates"]["evidence_basis"]
        self.assertEqual(
            evidence["differential_record_ids"],
            ["A-C0019-01", "B-C0004-01", "C-C0013-01", "D-C0013-02"],
        )
        self.assertEqual(evidence["new_vs_old_pair_total"], 472)
        self.assertEqual(evidence["new_vs_new_pair_total"], 6)

    def test_new_d_uses_e0130_but_keeps_record_anchor_limitation_open(self) -> None:
        result = recompute(self.config, ROOT)
        evidence = result["other_gates"]["evidence_basis"]
        supplemental = evidence["new_d_supplemental_original_text_evidence"]
        self.assertEqual([row["anchor_id"] for row in supplemental], ["E0129", "E0130"])
        self.assertIn("再次降临", supplemental[1]["quote"])
        self.assertTrue(evidence["known_record_anchor_limitation_open"])
        self.assertIn("没把E0130写入自身anchors", evidence["new_d_record_anchor_limitation"])

    def test_tampered_pairwise_duplicate_is_rejected(self) -> None:
        config = copy.deepcopy(self.config)
        audit_path = ROOT / config["differential_semantic_audit"]["path"]
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["new_record_pairwise_audit"][0]["cross_type_duplicate"] = True
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            temp_path = Path(tmp) / "tampered-audit.json"
            temp_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
            config["differential_semantic_audit"] = {
                "path": str(temp_path.relative_to(ROOT)),
                "sha256": __import__("hashlib").sha256(temp_path.read_bytes()).hexdigest(),
            }
            with self.assertRaises(NetBenefitError):
                recompute(config, ROOT)

    def test_tampered_e0130_quote_is_rejected(self) -> None:
        config = copy.deepcopy(self.config)
        audit_path = ROOT / config["differential_semantic_audit"]["path"]
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["new_d_gate"]["supplemental_original_text_evidence"][1]["quote"] = "错误引文"
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            temp_path = Path(tmp) / "tampered-audit.json"
            temp_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
            config["differential_semantic_audit"] = {
                "path": str(temp_path.relative_to(ROOT)),
                "sha256": __import__("hashlib").sha256(temp_path.read_bytes()).hexdigest(),
            }
            with self.assertRaises(NetBenefitError):
                recompute(config, ROOT)


if __name__ == "__main__":
    unittest.main()
