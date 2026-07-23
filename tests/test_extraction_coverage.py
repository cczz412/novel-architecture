from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.zbatch_modules import extraction_coverage

ROOT = Path(__file__).resolve().parents[1]


SOURCE_RUN = ROOT / "runs/Z00r_X01_第14章单次重采样续跑_20章_v1.0_20260718"
BOOK_DIR = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主"
TARGETS = ROOT / "config/diagnostics/X01_ch1_20_coverage_targets_v1.json"


class ExtractionCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = extraction_coverage.scan_book(
            book_dir=BOOK_DIR,
            extract_dir=SOURCE_RUN / "01_extract",
            target_config=json.loads(TARGETS.read_text(encoding="utf-8")),
            chapter_start=1,
            chapter_end=20,
        )

    def test_real_scope_counts_are_stable(self) -> None:
        self.assertEqual(
            self.report["schema_version"], "z-extraction-coverage-diagnostic-v3"
        )
        self.assertEqual(self.report["metrics"]["chapter_total"], 20)
        self.assertEqual(self.report["metrics"]["catalog_anchor_total"], 3811)
        self.assertEqual(self.report["metrics"]["event_total"], 263)
        self.assertEqual(self.report["metrics"]["anchor_reference_total"], 1036)
        self.assertEqual(self.report["metrics"]["used_unique_anchor_total"], 1030)
        self.assertEqual(self.report["metrics"]["unreferenced_anchor_total"], 2781)
        self.assertEqual(self.report["metrics"]["catalog_candidate_coverage_passes"], 20)
        self.assertEqual(self.report["scope"]["model_calls"], 0)

    def test_program_candidates_cover_every_catalog_anchor_and_e0059(self) -> None:
        audits = {row["chapter"]: row for row in self.report["candidate_coverage_audits"]}
        self.assertEqual(set(audits), set(range(1, 21)))
        self.assertTrue(all(row["status"] == "pass" for row in audits.values()))
        self.assertTrue(
            all(
                row["catalog_anchor_total"] == row["covered_unique_anchor_total"]
                for row in audits.values()
            )
        )
        chapter_five_ids = {
            anchor_id
            for row in self.report["catalog_coverage_candidates"]
            if row["chapter"] == 5
            for anchor_id in row["anchor_ids"]
        }
        self.assertIn("E0059", chapter_five_ids)

    def test_catalog_coverage_audit_rejects_missing_anchor(self) -> None:
        entries = [
            {"anchor_id": "E0001", "quote": "甲"},
            {"anchor_id": "E0002", "quote": "乙"},
        ]
        candidates = [
            {
                "candidate_id": "COV-C0005-001",
                "start_anchor_id": "E0001",
                "end_anchor_id": "E0001",
                "anchor_ids": ["E0001"],
            }
        ]
        with self.assertRaisesRegex(
            extraction_coverage.CoverageDiagnosticError,
            "E0002",
        ):
            extraction_coverage.audit_catalog_candidate_coverage(
                chapter=5,
                entries=entries,
                candidates=candidates,
            )

    def test_all_known_targets_are_unreferenced(self) -> None:
        targets = {row["id"]: row for row in self.report["known_targets"]}
        self.assertEqual(set(targets), {"S-L01", "S-L02", "S-L03", "S-L04", "A-F01-SUPPORT"})
        self.assertTrue(
            all(row["status"] == "anchor_span_unreferenced" for row in targets.values())
        )
        self.assertTrue(all(not row["missing_from_catalog"] for row in targets.values()))
        self.assertTrue(
            all(all(row["required_quote_checks"].values()) for row in targets.values())
        )

    def test_linked_cross_segment_events_are_present(self) -> None:
        targets = {row["id"]: row for row in self.report["known_targets"]}
        self.assertTrue(targets["S-L02"]["linked_events"][0]["present"])
        self.assertTrue(targets["A-F01-SUPPORT"]["linked_events"][0]["present"])
        for target_id in ("S-L02", "A-F01-SUPPORT"):
            link = targets[target_id]["linked_events"][0]
            self.assertTrue(link["expected_anchor_ids_match"])
            self.assertTrue(all(link["summary_fragment_checks"].values()))
        related = targets["A-F01-SUPPORT"]["related_spans"][0]
        self.assertEqual(related["status"], "anchor_span_unreferenced")
        self.assertTrue(all(related["required_quote_checks"].values()))

    def test_known_targets_overlap_heuristic_candidates(self) -> None:
        candidates = {
            row["candidate_id"]: row for row in self.report["heuristic_candidates"]
        }
        for target in self.report["known_targets"]:
            self.assertTrue(
                target["overlapping_heuristic_candidate_ids"],
                msg=f"已知靶未被候选层接住：{target['id']}",
            )
            self.assertTrue(
                all(
                    target["id"] in candidates[candidate_id]["known_target_ids"]
                    for candidate_id in target["overlapping_heuristic_candidate_ids"]
                )
            )

    def test_candidate_ids_are_unique_and_keep_review_boundary(self) -> None:
        rows = self.report["heuristic_candidates"]
        ids = [row["candidate_id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["boundary_hits"] for row in rows))
        self.assertTrue(all(row["status"] == "candidate_review" for row in rows))
        self.assertTrue(all(row["not_a_semantic_verdict"] for row in rows))

    def test_raw_gaps_also_keep_non_semantic_boundary(self) -> None:
        rows = self.report["raw_gap_runs"]
        self.assertEqual(len(rows), 286)
        self.assertTrue(all(row["status"] == "catalog_anchor_gap_review" for row in rows))
        self.assertTrue(all(row["not_a_semantic_verdict"] for row in rows))
        self.assertTrue(all("不等于" in row["boundary_note"] for row in rows))
        for target in self.report["known_targets"]:
            self.assertNotIn("semantic_term_event_hits", target)
            self.assertIn("event_summary_term_hits", target)

    def test_invalid_anchor_range_is_rejected(self) -> None:
        with self.assertRaises(extraction_coverage.CoverageDiagnosticError):
            extraction_coverage.anchor_range("E0002", "E0001")


if __name__ == "__main__":
    unittest.main()
