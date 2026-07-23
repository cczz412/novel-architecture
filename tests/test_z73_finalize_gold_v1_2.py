from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z73_finalize_gold_v1_2.py"
SPEC = importlib.util.spec_from_file_location("z73_finalize_gold_v1_2", MODULE_PATH)
assert SPEC and SPEC.loader
z73 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z73)


class Z73FinalizeGoldV12Tests(unittest.TestCase):
    def build(self, name: str) -> tuple[Path, dict]:
        temp_root = Path(tempfile.mkdtemp(prefix=f"z73-{name}-"))
        out = temp_root / "report"
        result = z73.write_outputs(out)
        return out, result

    def test_formal_gold_has_23_scoreable_atoms_and_three_hindsight_parts(self) -> None:
        formal = z73.build_formal_gold()
        parts = [part for item in formal["layered_items"] for part in item["parts"]]
        scoreable = [part for part in parts if part["score_in_single_chapter"]]
        hindsight = [part for part in parts if part["layer"] == "回看件"]
        self.assertEqual(formal["schema_version"], "structure-gold-v1.2")
        self.assertEqual(formal["status"], "active_gold")
        self.assertEqual(len(formal["layered_items"]), 14)
        self.assertEqual(len(parts), 26)
        self.assertEqual(len(scoreable), 23)
        self.assertEqual(len(hindsight), 3)
        self.assertEqual(formal["evaluation_policy"]["formal_denominator"], 23)

    def test_g10_is_non_scoring_observation_without_fake_support(self) -> None:
        formal = z73.build_formal_gold()
        observation = next(
            part
            for item in formal["layered_items"]
            for part in item["parts"]
            if part["part_id"] == "GOLD-C0003-10-N03"
        )
        self.assertEqual(observation["layer"], "回看件")
        self.assertEqual(observation["part_role"], "hindsight_observation")
        self.assertFalse(observation["score_in_single_chapter"])
        self.assertEqual(observation["source_evidence"], [])
        self.assertEqual(observation["window_evidence_refs"], [])
        self.assertEqual(len(observation["origin_trace_evidence_audit_only"]), 4)

    def test_g13_keeps_current_instance_and_neutral_alias_only(self) -> None:
        formal = z73.build_formal_gold()
        item_by_id = {item["item_id"]: item for item in formal["layered_items"]}
        g13 = next(part for part in item_by_id["GOLD-C0003-13"]["parts"] if part["part_id"] == "GOLD-C0003-13-N01")
        g06 = next(part for part in item_by_id["GOLD-C0003-06"]["parts"] if part["part_id"] == "GOLD-C0003-06-N01")
        self.assertTrue(g13["score_in_single_chapter"])
        self.assertIn("不承载长期肉食频率语义", g13["semantic_scope"])
        self.assertNotIn("待拍", g13["verdict"])
        self.assertEqual(g06["non_scoring_alias_semantic_point_ids"], ["G13-SP02"])
        self.assertIn("因果语义", g06["semantic_scope"])
        self.assertNotIn("待拍", item_by_id["GOLD-C0003-13"]["granularity_decision"])

    def test_mapping_disposes_all_31_points_without_orphans(self) -> None:
        formal = z73.build_formal_gold()
        mapping = z73.build_mapping(formal)
        self.assertEqual(mapping["status"], "pass_all_points_disposed_no_orphans")
        self.assertEqual(mapping["summary"]["old_base_item_total"], 14)
        self.assertEqual(mapping["summary"]["old_semantic_point_total"], 31)
        self.assertEqual(mapping["summary"]["scoreable_destination_part_total"], 23)
        self.assertEqual(mapping["summary"]["supported_point_orphan_total"], 0)
        self.assertEqual(mapping["summary"]["old_point_without_explicit_disposition_total"], 0)
        self.assertEqual(mapping["summary"]["unresolved_total"], 0)
        by_point = {row["semantic_point_id"]: row for row in mapping["semantic_point_rows"]}
        self.assertEqual(by_point["G10-SP03"]["disposition"], "mapped_to_hindsight_observation")
        self.assertTrue(by_point["G13-SP01"]["counts_toward_denominator"])
        self.assertFalse(by_point["G13-SP02"]["counts_toward_denominator"])

    def test_four_round_dual_baseline_numbers_are_locked(self) -> None:
        formal = z73.build_formal_gold()
        baseline = z73.build_baseline(formal)
        actual = {
            row["round_id"]: (
                row["v1_2_formal"]["strict_hit"],
                row["v1_2_formal"]["effective_recall"],
                row["v1_2_formal"]["surface_coverage"],
                row["v1_2_formal"]["invalid_anchor_observation"],
            )
            for row in baseline["rounds"]
        }
        self.assertEqual(
            actual,
            {
                "B0_Z57": (1, 7, 9, 2),
                "Z68C": (1, 8, 11, 3),
                "Z70": (4, 12, 14, 2),
                "Z71": (1, 6, 11, 5),
            },
        )
        self.assertTrue(all(row["sample_rerun"] is False for row in baseline["rounds"]))

    def test_z71_g06_wording_changes_but_score_does_not(self) -> None:
        baseline = z73.build_baseline(z73.build_formal_gold())
        self.assertEqual(len(baseline["adjudication_corrections"]), 1)
        correction = baseline["adjudication_corrections"][0]
        self.assertEqual(correction["round_id"], "Z71")
        self.assertEqual(correction["part_id"], "GOLD-C0003-06-N01")
        self.assertEqual(correction["old_verdict"], correction["new_verdict"])
        self.assertEqual(correction["numeric_effect"], "none")
        self.assertIn("E0132/E0133", correction["new_note"])

    def test_current_pointer_matches_formal_sha_and_has_rollback(self) -> None:
        formal_sha = z73.json_sha(z73.build_formal_gold())
        pointer = json.loads(z73.CURRENT_POINTER.read_text(encoding="utf-8"))
        self.assertEqual(pointer, z73.expected_pointer(formal_sha))
        self.assertEqual(pointer["active_gold"]["formal_denominator"], 23)
        self.assertEqual(pointer["predecessor"]["sha256"], z73.EXPECTED_SHA256["gold_v1_1"])
        self.assertIn("回退", pointer["rollback"])

    def test_historical_references_are_preserved_not_bulk_migrated(self) -> None:
        formal_sha = z73.json_sha(z73.build_formal_gold())
        audit = z73.build_reference_audit(formal_sha)
        self.assertEqual(audit["affected_active_reference_change_total"], 1)
        self.assertEqual(audit["historical_reference_change_total"], 0)
        self.assertEqual(len(audit["historical_rows"]), 9)
        self.assertTrue(all(row["before_sha256"] == row["after_sha256"] for row in audit["historical_rows"]))

    def test_frozen_inputs_protected_state_and_decision_pass(self) -> None:
        actual = z73.check_frozen_inputs()
        formal_sha = z73.json_sha(z73.build_formal_gold())
        pointer_and_decision = z73.validate_pointer_and_decision(formal_sha)
        self.assertEqual(actual["gold_v1"], z73.EXPECTED_SHA256["gold_v1"])
        self.assertEqual(actual["gold_v1_1"], z73.EXPECTED_SHA256["gold_v1_1"])
        self.assertEqual(actual["current_122"], z73.EXPECTED_SHA256["current_122"])
        self.assertEqual(pointer_and_decision["status"], "pass")
        self.assertIn(z73.DECISION_ID, pointer_and_decision["decision_line"])

    def test_two_isolated_builds_are_byte_identical(self) -> None:
        out1, result1 = self.build("repeat-a")
        out2, result2 = self.build("repeat-b")
        self.assertEqual(result1["formal_gold_sha256"], result2["formal_gold_sha256"])
        names1 = sorted(path.relative_to(out1) for path in out1.rglob("*") if path.is_file())
        names2 = sorted(path.relative_to(out2) for path in out2.rglob("*") if path.is_file())
        self.assertEqual(names1, names2)
        for name in names1:
            self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
