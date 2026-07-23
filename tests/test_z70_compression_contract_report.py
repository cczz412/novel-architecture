from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z70_compression_contract_report as report  # noqa: E402


class Z70CompressionContractReportTests(unittest.TestCase):
    def make_semantic_source(self, path: Path) -> dict[str, object]:
        old_gold = report.read_json(report.OLD_REPORT / report.OLD_GOLD_NAME)
        old_current = report.read_json(report.OLD_REPORT / report.OLD_CURRENT_NAME)
        gold_rows = [
            {
                "gold_item_id": row["gold_item_id"],
                "verdict": row["verdict"],
                "candidate_event_ids": row["candidate_event_ids"],
                "note": f"测试人工判词：{row['gold_item_id']}",
            }
            for row in old_gold["rows"]
        ]
        current_rows = [
            {
                "record_id": row["record_id"],
                "verdict": row["verdict"],
                "candidate_event_ids": row["candidate_event_ids"],
                "note": f"测试人工判词：{row['record_id']}",
            }
            for row in old_current["rows"]
        ]

        old_partial = [
            row for row in current_rows if row["verdict"] == "partially_preserved"
        ]
        old_preserved = [row for row in current_rows if row["verdict"] == "preserved"]
        for row in old_partial[:5]:
            row["verdict"] = "preserved"
        for row in old_preserved[:3]:
            row["verdict"] = "partially_preserved"
        old_partial[5]["verdict"] = "not_observed"
        old_partial[5]["candidate_event_ids"] = []

        source: dict[str, object] = {
            "schema_version": "z70-test-semantic-source-v1",
            "gold_rows": gold_rows,
            "current_rows": current_rows,
        }
        path.write_text(
            json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return source

    def test_build_uses_manual_verdicts_and_derives_all_gate_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            source_path = temp_dir / "semantic.json"
            self.make_semantic_source(source_path)
            output_dir = temp_dir / "report"
            manifest = report.build_documents(output_dir, semantic_source=source_path)

            self.assertEqual(sorted(path.name for path in output_dir.iterdir()), sorted(report.OUTPUT_NAMES))
            gold = report.read_json(output_dir / "第3章金标v1.1语义成绩单.json")
            current = report.read_json(output_dir / "现役122条五靶章语义diff.json")
            transport = report.read_json(output_dir / "运输与成本回执.json")
            mechanics = report.read_json(output_dir / "五靶章机械与成本成绩单.json")

            self.assertEqual(gold["summary"]["strict_hit"], 6)
            self.assertEqual(gold["summary"]["semantic_shadow_recalled"], 13)
            self.assertTrue(gold["quality_gate"]["passed"])
            self.assertEqual(current["summary"]["preserved"], 19)
            self.assertEqual(current["summary"]["partially_preserved"], 13)
            self.assertEqual(current["summary"]["not_observed"], 2)
            self.assertEqual(current["comparison_to_z68"]["old_partial_rescued_count"], 5)
            self.assertEqual(current["comparison_to_z68"]["degradation_count"], 4)
            self.assertEqual(current["quality_gate"]["disposition"], "hard_stop_no_repair")
            self.assertEqual(manifest["status"], "fail")
            self.assertEqual(manifest["disposition"], "hard_stop_no_repair")
            self.assertEqual(transport["transport_summary"]["logical_samples"], 5)
            self.assertEqual(transport["transport_summary"]["network_attempts"], 5)
            self.assertEqual(transport["transport_summary"]["transport_retries"], 0)
            self.assertEqual(mechanics["ten_metrics"]["03_目录外锚数"], 0)
            self.assertEqual(
                mechanics["ten_metrics"]["10_token与耗时成本"]["z70_all_32k"][
                    "totals"
                ]["total_tokens"],
                94698,
            )
            markdown = (output_dir / report.MAIN_REPORT_NAME).read_text(encoding="utf-8")
            self.assertIn("## 4. 第四节回执清单", markdown)
            self.assertIn("hard_stop_no_repair", markdown)
            self.assertTrue(markdown.endswith("来源：Codex\n"))

    def test_check_rebuilds_and_compares_all_generated_file_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            source_path = temp_dir / "semantic.json"
            self.make_semantic_source(source_path)
            output_dir = temp_dir / "report"
            report.build_documents(output_dir, semantic_source=source_path)
            result = report.check_documents(output_dir, semantic_source=source_path)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["checked_files"], len(report.OUTPUT_NAMES))
            self.assertEqual(set(result["sha256"]), set(report.OUTPUT_NAMES))

    def test_rejects_candidate_event_from_another_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            source_path = temp_dir / "semantic.json"
            source = self.make_semantic_source(source_path)
            broken = copy.deepcopy(source)
            broken["gold_rows"][0]["candidate_event_ids"] = ["EV-C0004-01"]
            source_path.write_text(
                json.dumps(broken, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(report.ReportError, "不在同章"):
                report.build_documents(temp_dir / "report", semantic_source=source_path)

    def test_rejects_semantic_id_set_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            source_path = temp_dir / "semantic.json"
            source = self.make_semantic_source(source_path)
            broken = copy.deepcopy(source)
            broken["current_rows"][0]["record_id"] = "A-C0003-DOES-NOT-EXIST"
            source_path.write_text(
                json.dumps(broken, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(report.ReportError, "ID 不一致"):
                report.build_documents(temp_dir / "report", semantic_source=source_path)


if __name__ == "__main__":
    unittest.main()
