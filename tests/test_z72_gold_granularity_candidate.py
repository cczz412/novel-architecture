from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z72_gold_granularity_candidate.py"
SPEC = importlib.util.spec_from_file_location("z72_gold_granularity_candidate", MODULE_PATH)
assert SPEC and SPEC.loader
z72 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z72)


class Z72GoldGranularityCandidateTests(unittest.TestCase):
    def build(self, name: str) -> tuple[Path, dict]:
        temp_root = Path(tempfile.mkdtemp(prefix=f"z72-{name}-"))
        out = temp_root / "report"
        result = z72.write_outputs(out)
        return out, result

    def test_candidate_keeps_formal_v11_untouched_and_declares_pending_semantics(self) -> None:
        out, _ = self.build("candidate")
        candidate = json.loads((out / "第3章结构层金标v1.2候选草案.json").read_text(encoding="utf-8"))
        summary = candidate["layer_summary"]
        self.assertEqual(candidate["status"], "candidate_pending_cz_review")
        self.assertEqual(summary["base_item_total"], 14)
        self.assertEqual(summary["candidate_part_total"], 24)
        self.assertEqual(summary["on_chapter_atomic_part_total"], 23)
        self.assertEqual(summary["evidence_insufficient_candidate_total"], 1)
        self.assertEqual(summary["review_state_unit_total"], 26)
        self.assertEqual(summary["hindsight_part_total"], 2)
        self.assertEqual(summary["declared_old_semantic_point_total"], 31)
        self.assertEqual(summary["declared_destination_point_total"], 31)
        self.assertEqual(summary["declared_point_id_orphan_total"], 0)
        self.assertEqual(summary["local_text_semantic_review_pass_total"], 28)
        self.assertEqual(summary["cz_semantic_review_pending_total"], 3)
        self.assertNotIn("semantic_point_loss", summary)
        self.assertFalse(candidate["protected_state"]["gold_v1_1_rewritten"])
        self.assertEqual(candidate["protected_state"]["model_api_calls"], 0)

    def test_mapping_has_no_orphans_and_all_anchors_read_back(self) -> None:
        out, _ = self.build("mapping")
        mapping = json.loads((out / "v1.1到v1.2逐条映射与语义点账.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping["status"], "pass_declared_point_ids_no_orphans_semantic_equivalence_pending")
        self.assertEqual(mapping["mapped_old_base_item_total"], 14)
        self.assertEqual(mapping["orphan_old_item_ids"], [])
        self.assertEqual(mapping["orphan_semantic_point_ids"], [])
        self.assertNotIn("semantic_point_loss", mapping)
        self.assertEqual(mapping["cz_semantic_review_pending_ids"], ["G10-SP03", "G13-SP01", "G13-SP02"])
        self.assertGreater(mapping["anchor_validation"]["anchor_occurrence_total"], 0)
        self.assertTrue(all(row["status"] == "pass" for row in mapping["anchor_validation"]["checks"]))

    def test_four_round_rejudge_is_manual_zero_call_and_scores_are_locked(self) -> None:
        out, _ = self.build("scores")
        scores = json.loads((out / "四轮新旧尺零调用重判.json").read_text(encoding="utf-8"))
        self.assertEqual(scores["model_api_calls"], 0)
        self.assertEqual(scores["sample_reruns"], 0)
        self.assertEqual(scores["score_policy"]["automation"], "none_manual_verdicts_only")
        actual = {
            row["round_id"]: (
                row["v1_2_candidate_atomic"]["strict_hit"],
                row["v1_2_candidate_atomic"]["semantic_recalled"],
                row["v1_2_candidate_old_item_diagnostic"]["complete"],
                row["v1_2_candidate_old_item_diagnostic"]["observed"],
                row["v1_2_candidate_old_item_diagnostic"]["pending_evidence_review"],
            )
            for row in scores["rounds"]
        }
        self.assertEqual(
            actual,
            {
                "B0_Z57": (1, 7, 1, 7, 2),
                "Z68C": (1, 8, 0, 6, 2),
                "Z70": (4, 12, 4, 10, 2),
                "Z71": (1, 6, 0, 4, 2),
            },
        )

    def test_invalid_anchor_coverage_never_enters_effective_recall(self) -> None:
        out, _ = self.build("invalid-support")
        scores = json.loads((out / "四轮新旧尺零调用重判.json").read_text(encoding="utf-8"))
        by_round = {row["round_id"]: row for row in scores["rounds"]}
        expected_invalid = {"B0_Z57": 2, "Z68C": 3, "Z70": 2, "Z71": 5}
        for round_id, expected in expected_invalid.items():
            atomic = by_round[round_id]["v1_2_candidate_atomic"]
            self.assertEqual(atomic["coverage_only_invalid_support"], expected)
            invalid_rows = [
                row
                for row in by_round[round_id]["rows"]
                if row["verdict"] == "coverage_only_invalid_support"
            ]
            self.assertTrue(invalid_rows)
            self.assertTrue(all(not row["counts_toward_effective_semantic_recall"] for row in invalid_rows))

        z71_rows = {row["part_id"]: row for row in by_round["Z71"]["rows"]}
        self.assertEqual(z71_rows["GOLD-C0003-06-N01"]["verdict"], "coverage_only_invalid_support")
        for round_row in scores["rounds"]:
            row_by_id = {row["part_id"]: row for row in round_row["rows"]}
            self.assertEqual(row_by_id["GOLD-C0003-11-N03"]["verdict"], "miss")
        b0_rows = {row["part_id"]: row for row in by_round["B0_Z57"]["rows"]}
        self.assertEqual(b0_rows["GOLD-C0003-11-N02"]["verdict"], "miss")

    def test_g13_causal_alias_and_food_wording_remain_pending(self) -> None:
        out, _ = self.build("g13-pending")
        candidate = json.loads((out / "第3章结构层金标v1.2候选草案.json").read_text(encoding="utf-8"))
        item_by_id = {item["item_id"]: item for item in candidate["layered_items"]}
        self.assertNotIn("因", item_by_id["GOLD-C0003-06"]["parts"][0]["claim"])
        self.assertNotIn("早餐", item_by_id["GOLD-C0003-13"]["parts"][0]["claim"])
        alias_flag = next(flag for flag in candidate["review_flags"] if flag["flag_id"] == "Z72-DUP-CAND-01")
        self.assertIn("因果等价待拍", alias_flag["kind"])
        self.assertEqual(alias_flag["target_semantic_point_ids"], ["G13-SP02"])
        for file_name in (
            "第3章结构层金标v1.2候选草案.json",
            "剔除候选与证据风险.json",
            "四轮新旧尺零调用重判.json",
            "第72道停点回包｜第3章金标粒度v1.2候选_20260721.md",
        ):
            self.assertNotIn("早餐", (out / file_name).read_text(encoding="utf-8"))

        scores = json.loads((out / "四轮新旧尺零调用重判.json").read_text(encoding="utf-8"))
        for round_row in scores["rounds"]:
            item13 = next(
                row for row in round_row["base_item_rollup_rows"] if row["old_item_id"] == "GOLD-C0003-13"
            )
            self.assertEqual(item13["diagnostic_rollup"], "pending_evidence_review")
            self.assertNotEqual(item13["alias_observation"], "complete")

    def test_z70_z71_fail_hard_stop_manifests_are_live_verified(self) -> None:
        out, _ = self.build("run-gates")
        scores = json.loads((out / "四轮新旧尺零调用重判.json").read_text(encoding="utf-8"))
        for run_id in ("Z70", "Z71"):
            gate = scores["run_level_gates_preserved"][run_id]
            self.assertEqual(gate["status"], "fail")
            self.assertEqual(gate["disposition"], "hard_stop_no_repair")
            self.assertTrue(gate["preserved"])
            self.assertEqual(gate["source_sha256"], z72.EXPECTED_SHA256[f"run_gate:{run_id}"])

    def test_gold05_is_one_continuous_adjustment_atom(self) -> None:
        out, _ = self.build("gold05")
        candidate = json.loads((out / "第3章结构层金标v1.2候选草案.json").read_text(encoding="utf-8"))
        item05 = next(item for item in candidate["layered_items"] if item["item_id"] == "GOLD-C0003-05")
        self.assertEqual(item05["decision"], "保留同一调表过程并措辞对齐")
        self.assertEqual(len(item05["parts"]), 1)

    def test_review_flags_do_not_delete_candidate_atoms(self) -> None:
        out, _ = self.build("flags")
        flags = json.loads((out / "剔除候选与证据风险.json").read_text(encoding="utf-8"))
        self.assertEqual(len(flags["flags"]), 3)
        self.assertTrue(all(flag["candidate_still_present"] for flag in flags["flags"]))
        self.assertEqual(flags["status"], "pending_cz_no_candidate_deleted")

    def test_two_builds_are_byte_identical(self) -> None:
        out1, result1 = self.build("repeat-a")
        out2, result2 = self.build("repeat-b")
        self.assertEqual(result1["fingerprint"], result2["fingerprint"])
        names1 = sorted(path.relative_to(out1) for path in out1.rglob("*") if path.is_file())
        names2 = sorted(path.relative_to(out2) for path in out2.rglob("*") if path.is_file())
        self.assertEqual(names1, names2)
        for name in names1:
            self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes())

    def test_repeat_validation_receipt_is_explicit(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="z72-repeat-final-"))
        out = temp_root / "report"
        result = z72.repeat_validate_and_write(out)
        receipt = json.loads((out / "机械验收连续两次一致回执.json").read_text(encoding="utf-8"))
        self.assertEqual(result["repeat_validation"], "pass_byte_identical")
        self.assertTrue(receipt["same"])
        self.assertEqual(receipt["pass1_fingerprint"], receipt["pass2_fingerprint"])
        self.assertTrue((out / "机械验收_pass1.json").is_file())
        self.assertTrue((out / "机械验收_pass2.json").is_file())


if __name__ == "__main__":
    unittest.main()
