from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z68_revised_request_pilot as z68  # noqa: E402


class Z68RevisedRequestPilotTests(unittest.TestCase):
    def test_original_sha_and_parameters_are_pinned(self) -> None:
        body = z68.load_original_body()
        self.assertEqual(z68.sha256_file(z68.ORIGINAL_REQUEST), z68.ORIGINAL_REQUEST_SHA256)
        self.assertEqual(body["model"], "deepseek-v4-flash")
        self.assertEqual(body["temperature"], 0.2)
        self.assertEqual(body["max_tokens"], 16000)
        self.assertEqual(body["n"], 1)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["reasoning_effort"], "medium")

    def test_chapter3_uses_original_body_without_change(self) -> None:
        body, diff = z68.build_instantiated_body(3)
        self.assertEqual(body, z68.load_original_body())
        self.assertEqual(diff["mode"], "direct_original_no_change")
        self.assertEqual(diff["allowed_changes"], [])

    def test_chapter3_supply_equals_intake_and_frozen_catalog(self) -> None:
        body, _ = z68.build_instantiated_body(3)
        user = body["messages"][1]["content"]
        self.assertEqual(z68.extract_text_payload(user), z68.chapter_file(3).read_text(encoding="utf-8"))
        entries = json.loads(z68.extract_catalog_payload(user))
        self.assertEqual(entries, z68.read_json(z68.source_catalog(3))["entries"])

    def test_other_chapters_only_use_mechanical_instantiation(self) -> None:
        original = z68.load_original_body()
        for chapter in (4, 5, 13, 19):
            with self.subTest(chapter=chapter):
                body, diff = z68.build_instantiated_body(chapter)
                self.assertEqual(diff["mode"], "mechanical_instantiation")
                self.assertEqual(len(diff["allowed_changes"]), 7)
                self.assertEqual(
                    {key: value for key, value in body.items() if key != "messages"},
                    {key: value for key, value in original.items() if key != "messages"},
                )

    def test_other_chapter_system_contract_is_instantiated(self) -> None:
        for chapter in (4, 5, 13, 19):
            system = z68.build_instantiated_body(chapter)[0]["messages"][0]["content"]
            self.assertIn(f'"chapter": {chapter}', system)
            self.assertEqual(system.count(f"EV-C{chapter:04d}"), 2)
            self.assertNotIn('"chapter": 3,', system)
            self.assertNotIn("EV-C0003", system)

    def test_other_chapter_hint_is_deleted(self) -> None:
        for chapter in (4, 5, 13, 19):
            user = z68.build_instantiated_body(chapter)[0]["messages"][1]["content"]
            self.assertNotIn("【本章命名提示】", user)
            self.assertNotIn("以上提示只用于本章指代消解", user)

    def test_other_chapter_text_filename_and_catalog_equal_frozen_inputs(self) -> None:
        for chapter in (4, 5, 13, 19):
            with self.subTest(chapter=chapter):
                body, _ = z68.build_instantiated_body(chapter)
                user = body["messages"][1]["content"]
                self.assertIn(f"当前章号：{chapter}", user)
                self.assertIn(f"当前章文件名：{z68.chapter_file(chapter).name}", user)
                self.assertEqual(z68.extract_text_payload(user), z68.chapter_file(chapter).read_text(encoding="utf-8"))
                self.assertEqual(
                    json.loads(z68.extract_catalog_payload(user)),
                    z68.read_json(z68.source_catalog(chapter))["entries"],
                )

    def test_every_body_matches_active_transport_contract(self) -> None:
        for chapter in z68.TARGET_CHAPTERS:
            z68.assert_body_matches_transport(z68.build_instantiated_body(chapter)[0])

    def test_prohibited_request_markers_are_absent(self) -> None:
        for chapter in z68.TARGET_CHAPTERS:
            self.assertEqual(z68.request_has_prohibited_input(z68.build_instantiated_body(chapter)[0]), [])

    def test_prohibited_request_marker_is_detected(self) -> None:
        body = z68.load_original_body()
        body["messages"][1]["content"] += " GOLD-C0003-01"
        self.assertIn("GOLD-C", z68.request_has_prohibited_input(body))

    def test_subject_lexical_check_is_conservative(self) -> None:
        self.assertEqual(z68.has_explicit_subject("周明瑞藏起手枪", 3), (True, "周明瑞"))
        self.assertEqual(z68.has_explicit_subject("在梅丽莎出门前，周明瑞藏起手枪", 3), (True, "周明瑞"))
        self.assertEqual(z68.has_explicit_subject("他藏起手枪", 3), (False, None))

    def test_vague_predicate_check_reports_literal_hits(self) -> None:
        self.assertEqual(z68.vague_hits("克莱恩面临新的问题"), ["面临", "问题"])
        self.assertEqual(z68.vague_hits("克莱恩藏起手枪"), [])

    def test_prepare_is_zero_call_and_repeat_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z68-test-run"
            result = z68.prepare(run_dir)
            self.assertEqual(result["model_api_calls"], 0)
            self.assertFalse((run_dir / "call_attempts.jsonl").exists())
            self.assertEqual(len(list((run_dir / "prepared_requests").glob("*.json"))), 5)
            self.assertEqual(z68.verify_prepared(run_dir)["status"], "pass")
            with self.assertRaisesRegex(Exception, "运行目录已存在"):
                z68.prepare(run_dir)


if __name__ == "__main__":
    unittest.main()
