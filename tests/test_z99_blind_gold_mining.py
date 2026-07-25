from __future__ import annotations

import hashlib
import json
import socket
import sys
import tempfile
import unittest
import urllib.request
from collections import Counter
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import z99_blind_gold_mining as z99  # noqa: E402


class Z99BlindGoldMiningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = z99.build_artifacts(repo_root=ROOT)
        cls.candidate_rows = [
            json.loads(line)
            for line in cls.result.artifacts[
                "candidate_surface_uncovered_pending_semantic_review.jsonl"
            ]
            .decode("utf-8")
            .splitlines()
        ]

    def test_normalization_contract_is_exact_and_nonsemantic(self) -> None:
        self.assertEqual("abc123克莱恩", z99.normalize_claim("ＡＢＣ 123，克莱恩！"))
        self.assertEqual("知否知否", z99.normalize_claim("知否？知否？"))
        contract = z99.comparison_contract()
        self.assertFalse(contract["normalization"]["traditional_simplified_conversion"])
        self.assertFalse(contract["normalization"]["synonym_rewrite"])
        self.assertFalse(contract["normalization"]["semantic_embedding"])
        self.assertEqual("claim only", contract["selection"]["comparison_field"])
        self.assertEqual(
            "screening_constant_not_semantically_calibrated",
            contract["candidate_gate"]["threshold_calibration_status"],
        )
        self.assertIn(
            "不得称为语义漏项",
            contract["candidate_gate"]["not_allowed_inference"],
        )

    def test_similarity_evidence_formula_and_audit_blocks(self) -> None:
        evidence = z99.similarity_evidence(
            "梅丽莎立志成为蒸汽机械师。",
            "梅丽莎立志成为一名蒸汽机械师。",
        )
        recomputed = round(
            z99.SEQUENCE_WEIGHT * evidence["sequence_ratio"]
            + z99.BIGRAM_DICE_WEIGHT * evidence["bigram_dice"]
            + z99.TRIGRAM_DICE_WEIGHT * evidence["trigram_dice"],
            z99.SCORE_DECIMAL_PLACES,
        )
        self.assertAlmostEqual(recomputed, evidence["composite_score"], places=5)
        self.assertGreater(evidence["composite_score"], z99.SIMILARITY_THRESHOLD)
        self.assertTrue(evidence["sequence_matching_blocks_min_length_2"])
        self.assertTrue(
            all(
                row["length"] >= 2
                for row in evidence["sequence_matching_blocks_min_length_2"]
            )
        )
        identical = z99.similarity_evidence("同一条", "同一条")
        self.assertEqual(1.0, identical["composite_score"])
        self.assertTrue(identical["blind_is_exact_normalized_substring_of_formal"])
        self.assertTrue(identical["formal_is_exact_normalized_substring_of_blind"])

    def test_threshold_is_strictly_below_after_rounding(self) -> None:
        self.assertTrue(z99.is_surface_candidate({"composite_score": 0.499999}))
        self.assertFalse(z99.is_surface_candidate({"composite_score": 0.500000}))
        self.assertFalse(z99.is_surface_candidate({"composite_score": 0.500001}))
        contract = z99.comparison_contract()
        self.assertEqual(0.5, contract["candidate_gate"]["threshold"])
        self.assertEqual(
            "rounded_composite_score < threshold",
            contract["candidate_gate"]["operator"],
        )

    def test_nearest_formal_tie_break_is_part_id_then_group_id(self) -> None:
        blind = {"claim": "完全相同", "part_id": "B"}
        formal_rows = [
            {
                "group_ordinal": 1,
                "group_id": "G2",
                "part_ordinal": 1,
                "part_id": "F2",
                "claim": "完全相同",
                "row": {"part_id": "F2", "claim": "完全相同"},
            },
            {
                "group_ordinal": 2,
                "group_id": "G1",
                "part_ordinal": 1,
                "part_id": "F1",
                "claim": "完全相同",
                "row": {"part_id": "F1", "claim": "完全相同"},
            },
        ]
        nearest, evidence = z99._nearest_formal(blind, formal_rows)
        self.assertEqual("F1", nearest["part_id"])
        self.assertEqual(1.0, evidence["composite_score"])

    def test_six_window_counts_and_candidate_counts_are_pinned(self) -> None:
        self.assertEqual(
            {
                "window_total": 6,
                "blind_group_total": 44,
                "blind_part_total": 827,
                "formal_group_total": 90,
                "formal_part_total_all_layers": 131,
                "formal_part_total_scoreable_single_chapter": 114,
                "pairwise_comparison_total": 18681,
                "candidate_total": 777,
                "not_in_candidate_pool_total": 50,
            },
            {
                key: self.result.summary[key]
                for key in (
                    "window_total",
                    "blind_group_total",
                    "blind_part_total",
                    "formal_group_total",
                    "formal_part_total_all_layers",
                    "formal_part_total_scoreable_single_chapter",
                    "pairwise_comparison_total",
                    "candidate_total",
                    "not_in_candidate_pool_total",
                )
            },
        )
        by_slot = Counter(row["window"]["slot"] for row in self.candidate_rows)
        self.assertEqual(
            {
                "01_X01_guimi": 141,
                "02_B01_zhifou": 137,
                "03_B02_dawang": 96,
                "04_B03_shenmi": 135,
                "05_B04_wuxian": 171,
                "06_B05_fanren": 97,
            },
            dict(by_slot),
        )

    def test_every_candidate_keeps_both_rows_and_reproducible_evidence(self) -> None:
        self.assertEqual(777, len(self.candidate_rows))
        candidate_ids = [row["candidate_id"] for row in self.candidate_rows]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))
        for row in self.candidate_rows:
            with self.subTest(candidate_id=row["candidate_id"]):
                self.assertEqual(z99.CANDIDATE_STATUS, row["status"])
                self.assertEqual("pending_not_performed", row["semantic_review_status"])
                self.assertIsNone(row["semantic_verdict"])
                self.assertTrue(row["blind_row"]["claim"])
                self.assertTrue(row["nearest_formal_row"]["claim"])
                self.assertEqual(
                    row["nearest_formal_location"]["part_id"],
                    row["nearest_formal_row"]["part_id"],
                )
                self.assertLess(
                    row["similarity_evidence"]["composite_score"],
                    z99.SIMILARITY_THRESHOLD,
                )
                self.assertEqual(
                    z99.similarity_evidence(
                        row["blind_row"]["claim"],
                        row["nearest_formal_row"]["claim"],
                    ),
                    row["similarity_evidence"],
                )
                self.assertTrue(row["boundary"]["mechanical_surface_difference_only"])
                self.assertFalse(row["boundary"]["semantic_missing_item_claimed"])
                self.assertFalse(row["boundary"]["formal_gold_change_allowed"])
                self.assertFalse(row["boundary"]["current_pointer_change_allowed"])

    def test_input_manifest_pins_blind_pointer_and_active_artifact_shas(self) -> None:
        manifest = json.loads(self.result.artifacts["input_manifest.json"])
        self.assertEqual(6, manifest["window_total"])
        self.assertEqual(
            6, manifest["cross_checks"]["formal_gold_registry"]["entry_total"]
        )
        for row in manifest["windows"]:
            for key in (
                "blind_candidate",
                "formal_current_pointer",
                "formal_active_artifact",
            ):
                item = row[key]
                path = ROOT / item["path"]
                with self.subTest(slot=row["slot"], kind=key):
                    self.assertTrue(path.is_file())
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                        item["sha256"],
                    )
            self.assertEqual(
                row["formal_active_artifact"]["sha256"],
                row["formal_active_artifact"]["declared_pointer_sha256"],
            )
            self.assertEqual("active_gold", row["formal_active_artifact"]["status"])
            self.assertEqual(
                "blind_produce_candidate_not_active",
                row["blind_candidate"]["status"],
            )

    def test_granularity_table_counts_groups_without_semantic_alignment(self) -> None:
        table = json.loads(self.result.artifacts["granularity_calibration.json"])
        self.assertEqual(self.result.summary["blind_group_total"], 44)
        self.assertEqual(44, table["totals"]["blind_group_total"])
        self.assertEqual(90, table["totals"]["formal_group_total"])
        for row in table["rows"]:
            with self.subTest(slot=row["slot"]):
                self.assertFalse(row["grouping"]["group_alignment_performed"])
                self.assertEqual(
                    row["blind"]["part_total"],
                    sum(row["blind"]["parts_per_group"]["part_counts_in_group_order"]),
                )
                self.assertEqual(
                    row["formal"]["part_total_all_layers"],
                    sum(
                        row["formal"]["parts_per_group_all_layers"][
                            "part_counts_in_group_order"
                        ]
                    ),
                )
                self.assertEqual(
                    row["formal"]["part_total_all_layers"],
                    row["formal"]["part_total_scoreable_single_chapter"]
                    + row["formal"]["part_total_other_layers"],
                )

    def test_acceptance_and_output_manifest_cover_generated_files(self) -> None:
        acceptance = json.loads(self.result.artifacts["mechanical_acceptance.json"])
        self.assertEqual("PASS", acceptance["status"])
        self.assertEqual(
            {
                "model_api_logical_samples": 0,
                "model_api_network_attempts": 0,
                "model_api_usage_tokens": 0,
                "network_requests": 0,
                "novel_body_read_count": 0,
            },
            acceptance["usage"],
        )
        self.assertFalse(acceptance["checks"]["semantic_review_performed"])
        self.assertFalse(acceptance["checks"]["formal_gold_changed"])
        self.assertFalse(acceptance["checks"]["current_pointer_changed"])
        positive_checks = {
            key: value
            for key, value in acceptance["checks"].items()
            if key
            not in {
                "semantic_review_performed",
                "formal_gold_changed",
                "current_pointer_changed",
            }
        }
        self.assertTrue(all(positive_checks.values()))

        output_manifest = json.loads(self.result.artifacts["output_manifest.json"])
        expected_names = set(self.result.artifacts) - {"output_manifest.json"}
        self.assertEqual(
            expected_names,
            {row["path"] for row in output_manifest["entries"]},
        )
        for row in output_manifest["entries"]:
            raw = self.result.artifacts[row["path"]]
            with self.subTest(path=row["path"]):
                self.assertEqual(len(raw), row["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])

    def test_markdown_deliverables_end_with_codex_source(self) -> None:
        for name in ("README.md", "granularity_calibration.md"):
            with self.subTest(path=name):
                text = self.result.artifacts[name].decode("utf-8")
                self.assertTrue(text.rstrip().endswith("来源：Codex"))
                self.assertNotIn("语义漏项。", text.splitlines()[0])

    def test_two_builds_are_byte_identical_and_do_not_touch_network(self) -> None:
        with (
            mock.patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("不得访问网络"),
            ),
            mock.patch.object(
                urllib.request,
                "urlopen",
                side_effect=AssertionError("不得访问网络"),
            ),
        ):
            second = z99.build_artifacts(repo_root=ROOT)
        self.assertEqual(self.result.artifacts, second.artifacts)
        self.assertEqual(self.result.summary, second.summary)

    def test_write_readback_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "blind_mining"
            z99._write_artifacts(output_dir, self.result.artifacts)
            z99._check_artifacts(output_dir, self.result.artifacts)
            target = output_dir / "candidate_pool_summary.json"
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaisesRegex(z99.Z99MiningError, "输出回读不一致"):
                z99._check_artifacts(output_dir, self.result.artifacts)


if __name__ == "__main__":
    unittest.main()
