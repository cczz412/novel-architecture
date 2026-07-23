from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tools.zbatch_modules import extraction_method_ab


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATHS = {
    "A": ROOT / "config/diagnostics/Z01b_X01_段级任务拆分_5章_v1.json",
    "B": ROOT / "config/diagnostics/Z01c_X01_程序点名靶_5章_v1.json",
    "C": ROOT / "config/diagnostics/Z01e_X01_结构地图前置块_5章_v1.json",
    "D": ROOT / "config/diagnostics/Z01d_X01_每段强合同_5章_v1.json",
}
Z01F_CONFIG_PATH = ROOT / "config/diagnostics/Z01f_X01_每段强合同v2_5章_v1.json"


class ExtractionMethodABTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configs = {
            arm: extraction_method_ab.read_json(path) for arm, path in CONFIG_PATHS.items()
        }

    def currentized_config(self, arm: str) -> dict:
        """历史实验配置保持原 SHA；行为测试只在内存里绑定当前受保护件。"""
        config = copy.deepcopy(self.configs[arm])
        for group_name in ("protected_chain", "experiment_code"):
            for ref in config[group_name].values():
                path = ROOT / ref["path"]
                ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return config

    def test_configs_and_prompts_are_fully_pinned(self) -> None:
        for arm, config in self.configs.items():
            self.assertNotIn("TO_FILL", json.dumps(config, ensure_ascii=False))
            audit = extraction_method_ab.audit_prompt(config, ROOT)
            self.assertEqual(audit["status"], "pass")
            self.assertTrue(all(audit["checks"].values()))
            self.assertEqual(audit["arm"], arm)

    def test_z01f_adds_only_the_summary_rule_and_has_scoped_artifacts(self) -> None:
        config = extraction_method_ab.read_json(Z01F_CONFIG_PATH)
        audit = extraction_method_ab.audit_prompt(config, ROOT)
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(config["arm"], "D")
        self.assertEqual(config["batch_id"], "Z01f")
        paths = extraction_method_ab.validate_artifact_paths(config, ROOT)
        self.assertEqual(paths["permit_path"], "work/zbatch_ab/permits/Z01f.call_permit.json")
        self.assertTrue(paths["run_dir"].startswith("runs/Z01f_"))

        old_lines = (
            ROOT / "work/zbatch_prompts/candidates/extract_event_strong_segment_contract_v1.0.md"
        ).read_text(encoding="utf-8").splitlines()
        new_lines = (ROOT / config["prompt"]["path"]).read_text(encoding="utf-8").splitlines()
        summary_rule = (
            "- 每事件摘要≥6 个非空字符且含谓词细节（谁对谁做了什么），"
            "禁止只写主语＋单动词。"
        )
        self.assertEqual(new_lines.count(summary_rule), 1)
        new_body = new_lines[1:]
        new_body.remove(summary_rule)
        self.assertEqual(new_body, old_lines[1:])

    def test_z01e_adds_only_the_structure_map_preface(self) -> None:
        config = self.configs["C"]
        audit = extraction_method_ab.audit_prompt(config, ROOT)
        self.assertEqual(audit["status"], "pass")
        self.assertTrue(all(audit["checks"].values()))
        self.assertEqual(
            audit["placeholder_order"],
            [
                "CHAPTER_PADDED",
                "CHAPTER_NUMBER",
                "CHAPTER_PADDED",
                "CHAPTER_NUMBER",
                "CHAPTER_FILENAME",
                "EVIDENCE_CATALOG_JSON",
            ],
        )
        prompt_text = (ROOT / config["prompt"]["path"]).read_text(encoding="utf-8")
        self.assertEqual(prompt_text.count("【C 臂前置块｜产品结构地图】"), 1)
        self.assertEqual(
            extraction_method_ab._remove_structure_map_block(prompt_text),
            (ROOT / config["baseline_prompt"]["path"]).read_text(encoding="utf-8"),
        )

    def test_z01e_uses_audit_only_segments_without_prompt_payload(self) -> None:
        config = self.configs["C"]
        built, catalog, rows, _ = extraction_method_ab.build_messages(config, ROOT, 3)
        self.assertEqual(
            [value for row in rows for value in row["anchor_ids"]],
            [row["anchor_id"] for row in catalog],
        )
        rendered = built["messages"][1]["content"]
        self.assertNotIn("SEGMENT_TASKS_JSON", rendered)
        self.assertNotIn('"segment_id":"SEG-', rendered)
        self.assertIn("产品结构地图", rendered)

    def test_z01e_is_bound_to_active_v1_2_default(self) -> None:
        audit = extraction_method_ab.verify_default_activation(self.configs["C"], ROOT)
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(audit["default_id"], "zbatch-v1.2-full-chain")
        self.assertEqual(audit["pin_resolution"], "compatible_successor")
        self.assertEqual(audit["compatibility_revision_id"], "Z57-stable-semantic-identity-v1")
        paths = extraction_method_ab.validate_artifact_paths(self.configs["C"], ROOT)
        self.assertEqual(paths["permit_path"], "work/zbatch_ab/permits/Z01e.call_permit.json")
        self.assertTrue(paths["run_dir"].startswith("runs/Z01e_"))

    def test_z01e_rejects_unrelated_default_sha_drift(self) -> None:
        config = copy.deepcopy(self.configs["C"])
        config["default_registry"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(
            extraction_method_ab.ExtractionMethodError,
            "不是受信的等义直系后继",
        ):
            extraction_method_ab.verify_default_activation(config, ROOT)

    def test_z01e_rejects_forged_successor_authority(self) -> None:
        registry_path = (ROOT / self.configs["C"]["default_registry"]["path"]).resolve()
        real_read_json = extraction_method_ab.read_json

        def forged_read(path: Path) -> dict:
            document = real_read_json(path)
            if path.resolve() == registry_path:
                document = copy.deepcopy(document)
                document["compatibility_revision"]["authority"] = "伪造授权"
            return document

        with mock.patch.object(extraction_method_ab, "read_json", side_effect=forged_read):
            with self.assertRaisesRegex(
                extraction_method_ab.ExtractionMethodError,
                "不是受信的等义直系后继",
            ):
                extraction_method_ab.verify_default_activation(self.configs["C"], ROOT)

    def test_z01e_preflight_is_zero_call_and_checks_silent_segments(self) -> None:
        config = self.currentized_config("C")
        config["run_id"] = f"UNIT_Z01E_{uuid.uuid4().hex}"
        result = extraction_method_ab.preflight(config, ROOT, require_fresh_run=True)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["arm"], "C")
        self.assertEqual(result["default_activation"]["status"], "pass")
        self.assertTrue(all(row["method_payload_check"] == "pass" for row in result["chapters"]))

        ledger = extraction_method_ab.method_coverage_ledger(
            "C",
            [
                {"segment_id": "SEG-001", "anchor_ids": ["E0001"]},
                {"segment_id": "SEG-002", "anchor_ids": ["E0002"]},
            ],
            {
                "events": [
                    {
                        "event_id": "EV-C0003-01",
                        "event": "一个足够长的中性事件",
                        "anchors": [{"anchor_id": "E0001"}],
                    }
                ]
            },
        )
        self.assertEqual(ledger["no_event_returned_count"], 1)
        self.assertEqual(ledger["rows"][1]["method_row_id"], "SEG-002")

    def test_segment_tasks_cover_catalog_once_in_order(self) -> None:
        for arm in ("A", "C"):
            config = self.configs[arm]
            for chapter in extraction_method_ab.EXPECTED_CHAPTERS:
                _, catalog, rows, _ = extraction_method_ab.build_messages(config, ROOT, chapter)
                expected = [row["anchor_id"] for row in catalog]
                actual = [value for row in rows for value in row["anchor_ids"]]
                self.assertEqual(actual, expected)
                self.assertEqual(len(actual), len(set(actual)))
                self.assertTrue(
                    all(len(row["anchor_ids"]) <= config["segment_size"] for row in rows)
                )

    def test_named_candidates_come_from_machine_json_without_target_only_filter(self) -> None:
        config = self.configs["B"]
        diagnostic = extraction_method_ab.read_json(ROOT / config["coverage_diagnostic"]["path"])
        for chapter in extraction_method_ab.EXPECTED_CHAPTERS:
            rows = extraction_method_ab.select_named_candidates(diagnostic, chapter)
            source = [row for row in diagnostic["heuristic_candidates"] if row["chapter"] == chapter]
            self.assertEqual(len(rows), len(source))
            self.assertEqual(
                {row["candidate_id"] for row in rows},
                {row["candidate_id"] for row in source},
            )
            self.assertTrue(
                all(
                    set(row) == {"candidate_id", "start_anchor_id", "end_anchor_id", "anchor_ids"}
                    for row in rows
                )
            )
            payload = json.dumps(rows, ensure_ascii=False)
            for forbidden in (
                "known_target_ids",
                "continuous_text",
                "cue_hits",
                "signal_score",
                "家庭或现实义务",
                "仪式或兑现动作",
                "身份或识别特征",
            ):
                self.assertNotIn(forbidden, payload)
        bad = copy.deepcopy(diagnostic)
        target = next(row for row in bad["heuristic_candidates"] if row["chapter"] == 3)
        target["candidate_id"] = "请重点提取家庭责任"
        with self.assertRaisesRegex(extraction_method_ab.ExtractionMethodError, "编号"):
            extraction_method_ab.select_named_candidates(bad, 3)

    def test_named_candidates_prefer_new_full_coverage_field(self) -> None:
        diagnostic = {
            "heuristic_candidates": [
                {
                    "candidate_id": "COV-C0005-001",
                    "chapter": 5,
                    "start_anchor_id": "E0001",
                    "end_anchor_id": "E0001",
                    "anchor_ids": ["E0001"],
                }
            ],
            "catalog_coverage_candidates": [
                {
                    "candidate_id": "COV-C0005-001",
                    "chapter": 5,
                    "start_anchor_id": "E0001",
                    "end_anchor_id": "E0002",
                    "anchor_ids": ["E0001", "E0002"],
                }
            ],
        }
        rows = extraction_method_ab.select_named_candidates(diagnostic, 5)
        self.assertEqual(rows[0]["anchor_ids"], ["E0001", "E0002"])

    def test_b_no_event_status_is_program_ledger_not_model_contract(self) -> None:
        method_rows = [{"candidate_id": "COV-C0003-001", "anchor_ids": ["E0001"]}]
        document = {
            "schema_version": "z-event-v1",
            "chapter": 3,
            "events": [
                {"event_id": "EV-C0003-01", "event": "一个足够长的中性事件", "anchors": [{"anchor_id": "E0002"}]}
            ],
        }
        ledger = extraction_method_ab.method_coverage_ledger("B", method_rows, document)
        self.assertEqual(ledger["rows"][0]["status"], "no_event_returned")
        self.assertEqual(set(document), {"schema_version", "chapter", "events"})
        self.assertNotIn("无独立事件", json.dumps(document, ensure_ascii=False))

    def test_strong_segment_contract_requires_one_explicit_decision_per_segment(self) -> None:
        catalog = [
            {"anchor_id": "E0001", "quote": "第一段连续短引"},
            {"anchor_id": "E0002", "quote": "第二段连续短引"},
        ]
        method_rows = [
            {
                "segment_id": "SEG-001",
                "start_anchor_id": "E0001",
                "end_anchor_id": "E0001",
                "anchor_ids": ["E0001"],
            },
            {
                "segment_id": "SEG-002",
                "start_anchor_id": "E0002",
                "end_anchor_id": "E0002",
                "anchor_ids": ["E0002"],
            },
        ]
        document = {
            "schema_version": "z-event-strong-segment-v1",
            "chapter": 3,
            "events": [
                {
                    "event_id": "EV-C0003-01",
                    "event": "这里发生一个足够长的中性变化",
                    "anchors": [{"anchor_id": "E0001"}],
                }
            ],
            "segment_decisions": [
                {
                    "segment_id": "SEG-001",
                    "status": "emitted",
                    "event_ids": ["EV-C0003-01"],
                    "reason": "本段交出该独立事件",
                },
                {
                    "segment_id": "SEG-002",
                    "status": "none",
                    "event_ids": [],
                    "reason": "本段无独立事件",
                },
            ],
        }
        materialized, program_audit, strong_audit = (
            extraction_method_ab.process_strong_segment_document(
                document,
                chapter=3,
                catalog=catalog,
                method_rows=method_rows,
            )
        )
        self.assertEqual(program_audit["status"], "pass")
        self.assertEqual(strong_audit["status"], "pass")
        self.assertEqual(strong_audit["silent_segment_count"], 0)
        self.assertEqual(strong_audit["explicit_none_segment_total"], 1)
        self.assertEqual(len(materialized["events"]), 1)

        missing = copy.deepcopy(document)
        missing["segment_decisions"].pop()
        with self.assertRaisesRegex(
            extraction_method_ab.ExtractionMethodError,
            "段决定缺失",
        ):
            extraction_method_ab.process_strong_segment_document(
                missing,
                chapter=3,
                catalog=catalog,
                method_rows=method_rows,
            )

        wrong_segment = copy.deepcopy(document)
        wrong_segment["segment_decisions"][0]["segment_id"] = "SEG-002"
        with self.assertRaisesRegex(
            extraction_method_ab.ExtractionMethodError,
            "段决定缺失",
        ):
            extraction_method_ab.process_strong_segment_document(
                wrong_segment,
                chapter=3,
                catalog=catalog,
                method_rows=method_rows,
            )

    def test_z01d_preflight_is_zero_call_and_full_segment_coverage(self) -> None:
        config = self.currentized_config("D")
        config["run_id"] = f"UNIT_Z01D_{uuid.uuid4().hex}"
        result = extraction_method_ab.preflight(config, ROOT, require_fresh_run=True)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["arm"], "D")
        self.assertTrue(all(row["method_payload_check"] == "pass" for row in result["chapters"]))
        self.assertTrue(all(row["method_row_count"] > 0 for row in result["chapters"]))

    def test_target_gate_requires_all_predeclared_anchors_and_fragments(self) -> None:
        target = {
            "id": "T",
            "label": "测试",
            "chapter": 3,
            "anchor_ids": ["E0001", "E0002"],
            "required_quote_fragments": ["命中短语"],
        }
        catalog = [
            {"anchor_id": "E0001", "quote": "这里包含命中短语"},
            {"anchor_id": "E0002", "quote": "另一条连续短引"},
        ]
        complete = {
            "events": [
                {"event_id": "EV-C0003-01", "event": "一个足够长的中性事件", "anchors": [{"anchor_id": "E0001"}, {"anchor_id": "E0002"}]}
            ]
        }
        self.assertTrue(extraction_method_ab.evaluate_target(target, complete, catalog)["pass"])
        incomplete = copy.deepcopy(complete)
        incomplete["events"][0]["anchors"].pop()
        self.assertFalse(extraction_method_ab.evaluate_target(target, incomplete, catalog)["pass"])

    def test_old_event_spot_audit_is_anchor_overlap_only(self) -> None:
        old = {
            "events": [
                {"event_id": "EV-C0003-01", "anchors": [{"anchor_id": "E0001"}, {"anchor_id": "E0002"}]}
            ]
        }
        new = {
            "events": [
                {"event_id": "EV-C0003-09", "anchors": [{"anchor_id": "E0002"}]}
            ]
        }
        result = extraction_method_ab.old_event_spot_audit(
            chapter=3,
            samples=[{"chapter": 3, "event_id": "EV-C0003-01"}],
            old_document=old,
            new_document=new,
        )
        self.assertEqual(result["status"], "pass")
        self.assertIn("不声称", result["boundary"])

    def test_transport_and_three_layer_layout_are_exact(self) -> None:
        for config in self.configs.values():
            audit = extraction_method_ab._contract_audit(config, ROOT)
            self.assertEqual(audit["values"], extraction_method_ab.EXPECTED_TRANSPORT)
            built, _, _, _ = extraction_method_ab.build_messages(config, ROOT, 3)
            self.assertEqual(
                built["messages"][0],
                {"role": "system", "content": "你只做证据约束的中性事件摘取，不做类型判断。只输出合法 JSON。"},
            )

    def test_permit_is_one_time_and_fresh_run_is_required(self) -> None:
        config = self.currentized_config("A")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # 这里只验一次性文件行为，不伪造仓库真源。
            permit = root / "permit.json"
            permit.write_text("{}", encoding="utf-8")
            self.assertTrue(permit.exists())
            with self.assertRaises(FileExistsError):
                permit.open("x").close()
        config["run_id"] = f"UNIT_Z01B_{uuid.uuid4().hex}"
        run_dir = ROOT / "runs" / config["run_id"]
        self.assertFalse(run_dir.exists(), "测试用运行目录必须是新目录")
        extraction_method_ab.preflight(config, ROOT, require_fresh_run=True)
        run_dir.mkdir()
        try:
            with self.assertRaisesRegex(extraction_method_ab.ExtractionMethodError, "运行目录已存在"):
                extraction_method_ab.preflight(config, ROOT, require_fresh_run=True)
        finally:
            run_dir.rmdir()

    def test_no_key_preflight_can_be_authorized_after_key_is_loaded(self) -> None:
        config = self.currentized_config("A")
        config["run_id"] = f"UNIT_Z01B_{uuid.uuid4().hex}"
        with mock.patch.dict("os.environ", {}, clear=True):
            saved = extraction_method_ab.preflight(config, ROOT, require_fresh_run=True)
        self.assertFalse(saved["api_key_present"])
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp:
            saved_path = Path(temp) / "preflight.json"
            extraction_method_ab.write_json(saved_path, saved)
            with mock.patch.object(extraction_method_ab, "preflight_path", return_value=saved_path):
                with mock.patch.dict("os.environ", {"SENSENOVA_API_KEY": "unit-only-key"}, clear=False):
                    document = extraction_method_ab.permit_document(config, ROOT)
        self.assertEqual(document["logical_sample_limit"], 5)
        self.assertEqual(document["model"], "deepseek-v4-flash")

    def test_old_event_sources_are_sha_pinned_and_drift_is_rejected(self) -> None:
        for config in self.configs.values():
            verified = extraction_method_ab.verify_old_source_files(config, ROOT)
            self.assertEqual(sorted(verified), extraction_method_ab.EXPECTED_CHAPTERS)
        bad = copy.deepcopy(self.configs["A"])
        bad["old_event_samples"]["source_files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(extraction_method_ab.ExtractionMethodError, "SHA 漂移"):
            extraction_method_ab.verify_old_source_files(bad, ROOT)

    def test_hard_stop_marks_truncation_and_output_cannot_reach_outbox(self) -> None:
        stop = extraction_method_ab.classify_hard_stop(
            extraction_method_ab.ExtractionMethodError(
                "API 响应未正常结束：0003，finish_reason=length"
            ),
            phase="chapter_execution",
            chapter=3,
        )
        self.assertEqual(stop["reason_code"], "finish_reason_not_stop")
        self.assertTrue(stop["is_truncation"])
        with self.assertRaisesRegex(extraction_method_ab.ExtractionMethodError, "只能写入"):
            extraction_method_ab.resolve_scoped_output(
                ROOT,
                "outbox/forbidden.json",
                "reports/Z01bc_提取漏对照轮_20260718",
            )

    def test_output_is_rejected_before_preflight_writes(self) -> None:
        path = extraction_method_ab.preflight_path(self.configs["A"], ROOT)
        before = path.read_bytes()
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/zbatch_extraction_method_ab.py"),
                "preflight",
                "--arm",
                "A",
                "--output",
                "outbox/forbidden.json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(path.read_bytes(), before)

    def test_config_derived_artifact_paths_cannot_escape_their_scopes(self) -> None:
        bad = copy.deepcopy(self.configs["A"])
        bad["run_id"] = "../outbox/escaped"
        with self.assertRaisesRegex(extraction_method_ab.ExtractionMethodError, "run_id"):
            extraction_method_ab.validate_artifact_paths(bad, ROOT)
        bad = copy.deepcopy(self.configs["A"])
        bad["permit_path"] = "outbox/escaped.json"
        with self.assertRaisesRegex(extraction_method_ab.ExtractionMethodError, "调用证"):
            extraction_method_ab.validate_artifact_paths(bad, ROOT)

    def test_outer_failure_recovery_keeps_partial_calls_and_completed_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            extraction_method_ab.write_json(run_dir / "events/ch0003.json", {"events": []})
            (run_dir / "call_attempts.jsonl").write_text(
                "\n".join(
                    json.dumps(row)
                    for row in (
                        {"case_id": "0003", "attempt": 1},
                        {"case_id": "0004", "attempt": 1},
                        {"case_id": "0004", "attempt": 2},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            extraction_method_ab.write_json(run_dir / "target_audits/ch0003.json", {"pass": True})
            extraction_method_ab.write_json(
                run_dir / "old_event_spot_audits/ch0003.json",
                {"rows": [{"pass": True}, {"pass": False}]},
            )
            extraction_method_ab.write_json(
                run_dir / "hard_stop.json",
                {"chapter": 4, "is_truncation": True},
            )
            (run_dir / "usage.jsonl").write_text(
                json.dumps(
                    {
                        "usage": {
                            "prompt_tokens": 7,
                            "completion_tokens": 5,
                            "total_tokens": 12,
                            "completion_tokens_details": {"reasoning_tokens": 3},
                            "prompt_tokens_details": {"cached_tokens": 2},
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            recovered = extraction_method_ab.recover_partial_run(run_dir)
        self.assertEqual(recovered["chapters_completed"], [3])
        self.assertEqual(recovered["chapters_failed"], [4])
        self.assertEqual(recovered["network_attempts"], 3)
        self.assertEqual(recovered["logical_samples"], 2)
        self.assertEqual(recovered["retries"], 1)
        self.assertEqual(recovered["truncated_chapters"], [4])
        self.assertEqual(recovered["chapters_not_called"], [5, 13, 19])
        self.assertEqual(recovered["chapters_not_evaluated"], [5, 13, 19])
        self.assertEqual(
            recovered["chapter_statuses"],
            [
                {"chapter": 3, "status": "正式完成"},
                {"chapter": 4, "status": "已调用失败"},
                {"chapter": 5, "status": "未调用"},
                {"chapter": 13, "status": "未调用"},
                {"chapter": 19, "status": "未调用"},
            ],
        )
        self.assertEqual(recovered["usage_row_count"], 1)
        self.assertEqual(recovered["prompt_tokens"], 7)
        self.assertEqual(recovered["completion_tokens"], 5)
        self.assertEqual(recovered["reasoning_tokens"], 3)
        self.assertEqual(recovered["cached_tokens"], 2)
        self.assertEqual(recovered["invalid_usage_row_count"], 0)
        self.assertEqual(recovered["total_tokens"], 12)

    def test_chapter_statuses_are_mutually_exclusive(self) -> None:
        rows = extraction_method_ab.chapter_status_rows([3], [4])
        self.assertEqual(len(rows), len(extraction_method_ab.EXPECTED_CHAPTERS))
        self.assertEqual({row["chapter"] for row in rows}, set(extraction_method_ab.EXPECTED_CHAPTERS))
        self.assertEqual(sum(row["status"] == "正式完成" for row in rows), 1)
        self.assertEqual(sum(row["status"] == "已调用失败" for row in rows), 1)
        self.assertEqual(sum(row["status"] == "未调用" for row in rows), 3)
        with self.assertRaisesRegex(extraction_method_ab.ExtractionMethodError, "同时标为"):
            extraction_method_ab.chapter_status_rows([3], [3])

    def test_outer_failure_writes_recovered_accounting_even_with_bad_usage_row(self) -> None:
        config = self.currentized_config("D")
        unit_id = uuid.uuid4().hex
        config["run_id"] = f"UNIT_Z01D_OUTER_{unit_id}"
        config["permit_path"] = f"work/zbatch_ab/permits/UNIT_Z01D_OUTER_{unit_id}.json"
        run_dir = ROOT / "runs" / config["run_id"]

        def fail_after_partial_write(*_args, **_kwargs):
            run_dir.mkdir(parents=True)
            (run_dir / "call_attempts.jsonl").write_text(
                json.dumps({"case_id": "0003", "attempt": 1}) + "\n",
                encoding="utf-8",
            )
            (run_dir / "usage.jsonl").write_text("{bad-json}\n", encoding="utf-8")
            extraction_method_ab.write_json(
                run_dir / "hard_stop.json",
                {"chapter": 3, "is_truncation": False},
            )
            raise extraction_method_ab.ExtractionMethodError("模拟收尾失败")

        try:
            with mock.patch.object(
                extraction_method_ab, "_run_arm_core", side_effect=fail_after_partial_write
            ):
                result = extraction_method_ab.run_arm(config, ROOT)
            self.assertEqual(result["status"], "hard_stopped")
            self.assertEqual(result["chapters_failed"], [3])
            self.assertEqual(result["chapters_not_called"], [4, 5, 13, 19])
            self.assertEqual(result["metrics"]["invalid_usage_row_count"], 1)
            self.assertEqual(result["metrics"]["total_tokens"], 0)
            saved = extraction_method_ab.read_json(run_dir / "result.json")
            self.assertEqual(saved["chapter_statuses"], result["chapter_statuses"])
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)
            (ROOT / config["permit_path"]).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
