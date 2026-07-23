from __future__ import annotations

import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z71_semantic_fill_report as report  # noqa: E402


class Z71SemanticFillReportTests(unittest.TestCase):
    maxDiff = None

    def make_run(self, run_dir: Path) -> list[dict[str, object]]:
        source_events = (
            ROOT
            / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720/01_extract/events"
        )
        source_catalogs = (
            ROOT
            / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720/inputs/evidence_catalogs"
        )
        fill_rows: list[dict[str, object]] = []
        batch_rows: list[dict[str, object]] = []
        usage_rows: list[dict[str, object]] = []
        attempt_rows: list[dict[str, object]] = []
        call_number = 0
        for chapter in report.TARGET_CHAPTERS:
            source_doc = report.read_json(source_events / f"ch{chapter:04d}.json")
            before_rows = copy.deepcopy(source_doc["events"])
            after_rows = copy.deepcopy(before_rows)
            changed_row = after_rows[0]
            changed_row["event"] += "（测试补全）"
            catalog = report.read_json(source_catalogs / f"ch{chapter:04d}.json")
            anchor = changed_row["anchors"][0]
            report.write_json(
                run_dir / f"inputs/events/ch{chapter:04d}.json",
                {"schema_version": "test", "chapter": chapter, "events": before_rows},
            )
            report.write_json(
                run_dir / f"outputs/events/ch{chapter:04d}.json",
                {"schema_version": "test", "chapter": chapter, "events": after_rows},
            )
            report.write_json(
                run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json", catalog
            )
            event_id = changed_row["event_id"]
            batch_id = f"ch{chapter:04d}_b001"
            report.write_json(
                run_dir / f"sidecars/event_diffs/ch{chapter:04d}.json",
                {
                    "schema_version": "test",
                    "chapter": chapter,
                    "source_event_count": len(before_rows),
                    "changed_count": 1,
                    "unchanged_count": len(before_rows) - 1,
                    "events": [
                        {
                            "event_id": event_id,
                            "before": before_rows[0]["event"],
                            "after": changed_row["event"],
                            "changed": True,
                            "batch_id": batch_id,
                            "provenance_anchor_ids": [anchor["anchor_id"]],
                            "provenance": [
                                {
                                    "anchor_id": anchor["anchor_id"],
                                    "quote": anchor["quote"],
                                }
                            ],
                        }
                    ],
                },
            )
            fill_rows.append(
                {
                    "chapter": chapter,
                    "event_id": event_id,
                    "verdict": "pass",
                    "note": f"测试人工确认第{chapter}章补全有原句锚支撑。",
                }
            )
            batches = math.ceil(len(before_rows) / 3)
            for batch_index in range(1, batches + 1):
                call_number += 1
                case_id = f"ch{chapter:04d}_b{batch_index:03d}"
                body_path = run_dir / f"prepared_requests/{case_id}.json"
                report.write_json(
                    body_path,
                    {
                        "model": "test-model",
                        "messages": [{"role": "system", "content": "test"}],
                    },
                )
                batch_rows.append(
                    {
                        "chapter": chapter,
                        "batch_id": case_id,
                        "prepared_request_sha256": report.sha256_file(body_path),
                    }
                )
                usage_rows.append(
                    {
                        "case_id": case_id,
                        "chapter": chapter,
                        "http_status": 200,
                        "finish_reason": "stop",
                        "elapsed_ms": 1,
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                            "completion_tokens_details": {"reasoning_tokens": 0},
                        },
                    }
                )
                attempt_rows.append(
                    {
                        "call_number": call_number,
                        "case_id": case_id,
                        "chapter": chapter,
                        "attempt": 1,
                        "http_status": 200,
                    }
                )
        self.assertEqual(call_number, report.EXPECTED_LOGICAL_BATCHES)
        (run_dir / "usage.jsonl").parent.mkdir(parents=True, exist_ok=True)
        (run_dir / "usage.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in usage_rows),
            encoding="utf-8",
        )
        (run_dir / "call_attempts.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in attempt_rows),
            encoding="utf-8",
        )
        report.write_json(
            run_dir / "preflight.json",
            {
                "schema_version": "test",
                "sandbox_to_formal_differences": [
                    "TEMP三样本改为五靶章25个正式逻辑批",
                    "原始事件与补全成品独立落盘",
                ],
                "rows": batch_rows,
            },
        )
        report.write_json(
            run_dir / "run_manifest.json",
            {
                "schema_version": "test",
                "status": "completed_candidate_only",
                "completed_at": "2026-07-21T06:30:00+08:00",
                "runner": {
                    "path": "tools/z71_semantic_fill_pilot.py",
                    "sha256": "test-runner-sha",
                },
            },
        )
        report.write_json(
            run_dir / "mechanical_verification.json",
            {"schema_version": "test", "status": "pass"},
        )
        return fill_rows

    def make_semantic_source(
        self, path: Path, fill_rows: list[dict[str, object]]
    ) -> dict[str, object]:
        old_gold = report.read_json(report.Z68_REPORT / report.Z68_GOLD_NAME)
        old_current = report.read_json(report.Z68_REPORT / report.Z68_CURRENT_NAME)
        source: dict[str, object] = {
            "schema_version": "z71-test-human-source-v1",
            "fill_rows": copy.deepcopy(fill_rows),
            "gold_rows": [
                {
                    "gold_item_id": row["gold_item_id"],
                    "verdict": row["verdict"],
                    "candidate_event_ids": row["candidate_event_ids"],
                    "note": f"测试人工金标判词：{row['gold_item_id']}",
                }
                for row in old_gold["rows"]
            ],
            "current_rows": [
                {
                    "record_id": row["record_id"],
                    "verdict": row["verdict"],
                    "candidate_event_ids": row["candidate_event_ids"],
                    "note": f"测试人工现役判词：{row['record_id']}",
                }
                for row in old_current["rows"]
            ],
        }
        report.write_json(path, source)
        return source

    def fixture(self, temp_dir: Path) -> tuple[Path, Path, dict[str, object]]:
        run_dir = temp_dir / "run"
        fill_rows = self.make_run(run_dir)
        source_path = temp_dir / "semantic.json"
        source = self.make_semantic_source(source_path, fill_rows)
        return run_dir, source_path, source

    @staticmethod
    def verify_pass() -> dict[str, object]:
        return {
            "schema_version": "test-verify-v1",
            "status": "pass",
            "run_status": "completed_candidate_only",
            "checks": {"all": True},
            "transport": {"logical_batches": 25},
        }

    def build(self, output_dir: Path, run_dir: Path, source_path: Path) -> dict[str, object]:
        with mock.patch.object(report.z71, "verify", return_value=self.verify_pass()):
            return report.build_documents(
                output_dir, run_dir=run_dir, semantic_source=source_path
            )

    def test_success_requires_all_three_gates_and_reports_incremental_cost(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            run_dir, source_path, _source = self.fixture(temp_dir)
            output_dir = temp_dir / "report"
            manifest = self.build(output_dir, run_dir, source_path)

            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["disposition"], "candidate_gate_pass")
            self.assertEqual(manifest["counts"]["changed_events"], 5)
            self.assertEqual(manifest["counts"]["gold_strict"], 6)
            self.assertEqual(manifest["counts"]["gold_shadow_recalled"], 13)
            self.assertEqual(manifest["counts"]["old_partial_rescued"], 0)
            self.assertEqual(manifest["incremental_total_tokens"], 50)
            self.assertEqual(sorted(item.name for item in output_dir.iterdir()), sorted(report.OUTPUT_NAMES))
            markdown = (output_dir / report.MAIN_REPORT_NAME).read_text(encoding="utf-8")
            self.assertIn("Z68C＋z70旁路补全", markdown)
            self.assertIn("预计逻辑批 25，实际 25", markdown)
            self.assertTrue(markdown.endswith("来源：Codex\n"))

    def test_fill_semantic_failure_hard_stops_with_exact_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            run_dir, source_path, source = self.fixture(temp_dir)
            broken = copy.deepcopy(source)
            broken["fill_rows"][0]["verdict"] = "unsupported"
            broken["fill_rows"][0]["note"] = "新增时间不在所挂原句锚中。"
            report.write_json(source_path, broken)
            manifest = self.build(temp_dir / "report", run_dir, source_path)

            self.assertEqual(manifest["status"], "fail")
            self.assertEqual(manifest["disposition"], "hard_stop_no_repair")
            fill_doc = report.read_json(temp_dir / "report/补全逐条diff与provenance.json")
            self.assertEqual(fill_doc["quality_gate"]["failures"][0]["verdict"], "unsupported")
            self.assertEqual(fill_doc["quality_gate"]["failures"][0]["reason"], "新增时间不在所挂原句锚中。")

    def test_gold_floor_drop_hard_stops(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            run_dir, source_path, source = self.fixture(temp_dir)
            broken = copy.deepcopy(source)
            strict = next(row for row in broken["gold_rows"] if row["verdict"] == "strict_hit")
            strict["verdict"] = "semantic_shadow"
            report.write_json(source_path, broken)
            manifest = self.build(temp_dir / "report", run_dir, source_path)

            self.assertEqual(manifest["status"], "fail")
            gold = report.read_json(temp_dir / "report/第3章金标v1.1语义成绩单.json")
            self.assertEqual(gold["summary"]["strict_hit"], 5)
            self.assertFalse(gold["quality_gate"]["strict_floor_pass"])

    def test_old_current_record_degradation_hard_stops(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            run_dir, source_path, source = self.fixture(temp_dir)
            broken = copy.deepcopy(source)
            preserved = next(
                row for row in broken["current_rows"] if row["verdict"] == "preserved"
            )
            preserved["verdict"] = "partially_preserved"
            preserved["note"] = "补全后丢失旧记录的结果限定。"
            report.write_json(source_path, broken)
            manifest = self.build(temp_dir / "report", run_dir, source_path)

            self.assertEqual(manifest["status"], "fail")
            current = report.read_json(temp_dir / "report/现役34条逐条账.json")
            self.assertEqual(current["quality_gate"]["degradation_count"], 1)
            self.assertEqual(
                current["quality_gate"]["degradations"][0]["reason"],
                "补全后丢失旧记录的结果限定。",
            )

    def test_rejects_fill_row_set_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            run_dir, source_path, source = self.fixture(temp_dir)
            broken = copy.deepcopy(source)
            broken["fill_rows"].pop()
            report.write_json(source_path, broken)
            with mock.patch.object(report.z71, "verify", return_value=self.verify_pass()):
                with self.assertRaisesRegex(report.ReportError, "fill_rows.*集合不一致"):
                    report.build_documents(
                        temp_dir / "report", run_dir=run_dir, semantic_source=source_path
                    )

    def test_check_rebuilds_all_files_with_identical_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_dir = Path(temp)
            run_dir, source_path, _source = self.fixture(temp_dir)
            output_dir = temp_dir / "report"
            self.build(output_dir, run_dir, source_path)
            with mock.patch.object(report.z71, "verify", return_value=self.verify_pass()):
                result = report.check_documents(
                    output_dir, run_dir=run_dir, semantic_source=source_path
                )
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["checked_files"], len(report.OUTPUT_NAMES))
            self.assertEqual(set(result["sha256"]), set(report.OUTPUT_NAMES))


if __name__ == "__main__":
    unittest.main()
