from __future__ import annotations

import ast
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RETIRED_RUNNER = ROOT / "runs/Z00z_X01_局部段覆盖试点_ch0003_v1.0_20260718/provenance/runner_zbatch.py"
RETIRED_RUNNER_SHA256 = "0b9334a34fcc5b5f866f43b2b3bc40aeff4cedf79a8ff83c51957496061a8080"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import zbatch  # noqa: E402
from zbatch_modules import (  # noqa: E402
    anchor_kit,
    candidate_envelope,
    downstream_validate,
    evidence_catalog,
    prompt_render_pin,
)


class ZBatchModuleEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("zbatch_retired_archive", RETIRED_RUNNER)
        if spec is None or spec.loader is None:
            raise RuntimeError("无法载入删除前运行器归档")
        cls.retired = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.retired)
        cls.book_dir = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主"
        cls.chapters = zbatch.load_chapters(cls.book_dir, 1, 20)
        cls.z00k = ROOT / "runs/Z00k_X01_第6至10章D类边界单变量_5章_v1.4_20260717"
        cls.z00e = ROOT / "runs/Z00e_X01_20章下游续测_v1.2_20260717"
        cls.z00m = ROOT / "runs/Z00m_X01_第6至10章分类收权单变量复跑_5章_v1.0_20260717"

    def test_retired_archive_sha_is_fixed(self):
        self.assertEqual(zbatch.sha256_file(RETIRED_RUNNER), RETIRED_RUNNER_SHA256)
        source = RETIRED_RUNNER.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        for name in (
            "build_evidence_catalog",
            "materialize_anchor_ids",
            "validate_record",
            "validate_candidate_envelope",
            "derived_records_valid",
            "validate_macro",
            "validate_answer_items",
            "validate_compare_items",
        ):
            self.assertGreater(len(functions[name].body), 2, name)

    def test_active_runner_changed_but_legacy_name_is_a_thin_forwarder(self):
        self.assertNotEqual(
            zbatch.sha256_file(ROOT / "tools/zbatch.py"),
            "cc4f42f798f8f537524f5a458008ae76f0bbbfea8588c7618dc03be17cbe437b",
        )
        self.assertTrue(callable(zbatch.legacy_stage_extract))
        self.assertIsNot(zbatch.stage_extract, zbatch.legacy_stage_extract)
        source = (ROOT / "tools/zbatch.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        compatibility_names = {
            "nonspace_chars",
            "_quote_windows",
            "build_evidence_catalog",
            "evidence_catalog_coverage",
            "materialize_anchor_ids",
            "materialize_anchors_from_sources",
            "validate_anchors",
            "validate_record",
            "validate_candidate_coverage_audit",
            "validate_candidate_envelope",
            "cross_type_anchor_overlap",
            "legacy_stage_extract",
            "derived_records_valid",
            "record_anchor_chapters",
            "validate_macro",
            "enforce_fold_gate",
            "enforce_answer_gate",
            "enforce_compare_gate",
            "gradient_bucket_for_distance",
            "validate_gradient_points",
            "validate_answer_items",
            "validate_compare_items",
        }
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in compatibility_names
        }
        self.assertEqual(set(functions), compatibility_names)
        for name, node in functions.items():
            executable = [
                statement
                for statement in node.body
                if not (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                )
            ]
            self.assertEqual(len(executable), 1, name)
            self.assertIsInstance(executable[0], (ast.Return, ast.Expr), name)

    def test_new_modules_do_not_import_old_monolith(self):
        for path in sorted((ROOT / "tools/zbatch_modules").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            self.assertFalse(any(name == "zbatch" or name.startswith("zbatch.") for name in imports), path.name)

    def test_evidence_catalog_matches_real_chapter(self):
        chapter = self.chapters[6]
        old = self.retired.build_evidence_catalog(6, chapter["text"])
        new = evidence_catalog.build_evidence_catalog(6, chapter["text"])
        self.assertEqual(new, old)
        self.assertEqual(
            evidence_catalog.evidence_catalog_coverage(chapter["text"], new),
            self.retired.evidence_catalog_coverage(chapter["text"], old),
        )

    def test_anchor_materialization_matches(self):
        catalog = zbatch.read_json(self.z00k / "01_extract/evidence_catalogs/ch0006.json")["entries"]
        raw = {
            "records": [
                {
                    "id": "A-C0006-01",
                    "anchors": [{"anchor_id": catalog[0]["anchor_id"]}],
                }
            ]
        }
        self.assertEqual(
            anchor_kit.materialize_anchor_ids(raw, catalog, 6),
            self.retired.materialize_anchor_ids(raw, catalog, 6),
        )

    def test_anchor_validation_matches_real_record(self):
        records = zbatch.read_json(self.z00k / "02_verify/valid_records.json")["records"]
        record = records[0]
        self.assertEqual(
            anchor_kit.validate_record(record, self.chapters, expected_chapter=6),
            self.retired.validate_record(record, self.chapters, expected_chapter=6),
        )

    def test_source_anchor_materialization_and_error_match(self):
        source_records = {
            "A-C0006-01": {
                "anchors": [
                    {"chapter": 6, "anchor_id": "E0001", "quote": "这是一段足够长度并且能够命中的原文短引"}
                ]
            }
        }
        items = [{"source_record_ids": ["A-C0006-01", "missing"]}]
        self.assertEqual(
            anchor_kit.materialize_anchors_from_sources(items, source_records, source_field="source_record_ids"),
            self.retired.materialize_anchors_from_sources(items, source_records, source_field="source_record_ids"),
        )
        with self.assertRaises(Exception) as old_error:
            self.retired.materialize_anchors_from_sources({}, source_records, source_field="source_record_ids")
        with self.assertRaises(Exception) as new_error:
            anchor_kit.materialize_anchors_from_sources({}, source_records, source_field="source_record_ids")
        self.assertEqual(type(new_error.exception).__name__, type(old_error.exception).__name__)
        self.assertEqual(str(new_error.exception), str(old_error.exception))

    def test_candidate_envelope_and_overlap_match(self):
        data = zbatch.read_json(self.z00k / "01_extract/parsed/ch0006.json")
        self.assertEqual(
            candidate_envelope.validate_candidate_envelope(data, 6),
            self.retired.validate_candidate_envelope(data, 6),
        )
        self.assertEqual(
            candidate_envelope.cross_type_anchor_overlap(data["records"]),
            self.retired.cross_type_anchor_overlap(data["records"]),
        )

    def test_json_parser_matches_valid_output_and_rejects_without_repair(self):
        payload = "```json\n{\"ok\": true}\n```"
        self.assertEqual(candidate_envelope.parse_json_content(payload), self.retired.parse_json_content(payload))
        with self.assertRaisesRegex(candidate_envelope.CandidateContractError, "不做二次缝补"):
            candidate_envelope.parse_json_content('{"broken":')

    def test_prompt_render_and_pin_match(self):
        template = "章={{CHAPTER}}；正文={{TEXT}}"
        values = {"CHAPTER": "6", "TEXT": "原文"}
        rendered = prompt_render_pin.render_prompt(template, values)
        self.assertEqual(rendered, self.retired.replace_prompt(template, values))
        self.assertEqual(prompt_render_pin.prompt_sha256(rendered), self.retired.sha256_bytes(rendered.encode("utf-8")))
        prompt_path = ROOT / "work/zbatch_prompts/candidates/extract_event_only_v1.0.md"
        expected = zbatch.sha256_file(prompt_path)
        self.assertEqual(prompt_render_pin.load_pinned_text(prompt_path, expected), prompt_path.read_text(encoding="utf-8"))

    def test_real_prompt_render_matches_stored_request(self):
        chapter = self.chapters[6]
        template = (ROOT / "work/zbatch_prompts/candidates/extract_event_only_v1.0.md").read_text(encoding="utf-8")
        catalog = zbatch.read_json(self.z00m / "01_event_extract/evidence_catalogs/ch0006.json")["entries"]
        values = {
            "CHAPTER_NUMBER": "6",
            "CHAPTER_PADDED": "0006",
            "CHAPTER_FILENAME": chapter["filename"],
            "CHAPTER_TEXT": chapter["text"],
            "EVIDENCE_CATALOG_JSON": json.dumps(catalog, ensure_ascii=False, separators=(",", ":")),
        }
        rendered = prompt_render_pin.render_prompt(template, values)
        request = zbatch.read_json(self.z00m / "requests/extract/ch0006_request.json")
        self.assertEqual(rendered, self.retired.replace_prompt(template, values))
        self.assertEqual(rendered, request["body"]["messages"][1]["content"])

    def test_error_interface_matches_old_name_base_and_message(self):
        cases = [
            (lambda: candidate_envelope.parse_json_content('{"broken":'), lambda: self.retired.parse_json_content('{"broken":')),
            (lambda: prompt_render_pin.render_prompt("{{LEFT}}", {}), lambda: self.retired.replace_prompt("{{LEFT}}", {})),
            (lambda: downstream_validate.enforce_answer_gate({"four_type_pass": False}), lambda: self.retired.enforce_answer_gate({"four_type_pass": False})),
        ]
        for new_call, old_call in cases:
            with self.assertRaises(Exception) as old_error:
                old_call()
            with self.assertRaises(Exception) as new_error:
                new_call()
            self.assertEqual(type(new_error.exception).__name__, type(old_error.exception).__name__)
            self.assertIsInstance(new_error.exception, RuntimeError)
            self.assertEqual(str(new_error.exception), str(old_error.exception))

    def test_thin_validation_matches_real_artifact(self):
        dense = zbatch.read_json(self.z00e / "02_verify/valid_records.json")["records"]
        allowed = {str(record["id"]) for record in dense}
        thin = zbatch.read_json(self.z00e / "03_thin/main_ledger.json")["records"]
        self.assertEqual(
            downstream_validate.derived_records_valid(thin, self.chapters, allowed),
            self.retired.derived_records_valid(thin, self.chapters, allowed),
        )

    def test_fold_answer_compare_validation_matches_real_artifacts(self):
        ledger = zbatch.read_json(self.z00e / "03_thin/main_ledger.json")
        ledger_map = {str(record["id"]): record for record in ledger["records"]}
        fold = zbatch.read_json(self.z00e / "04_fold/fold_view.json")
        for macro in fold.get("macros") or []:
            self.assertEqual(
                downstream_validate.validate_macro(macro, self.chapters, ledger_map),
                self.retired.validate_macro(macro, self.chapters, ledger_map),
            )

        answer = zbatch.read_json(self.z00e / "05_answer/answer.json")
        self.assertEqual(
            downstream_validate.validate_answer_items(answer["items"], self.chapters, ledger_map, 20, fold),
            self.retired.validate_answer_items(answer["items"], self.chapters, ledger_map, 20, fold),
        )
        compare = zbatch.read_json(self.z00e / "06_compare/diff.json")
        self.assertEqual(
            downstream_validate.validate_compare_items(compare["items"], answer["items"]),
            self.retired.validate_compare_items(compare["items"], answer["items"]),
        )

    def test_gate_messages_match(self):
        cases = [
            (
                downstream_validate.enforce_fold_gate,
                self.retired.enforce_fold_gate,
                {"macros_invalid": 1, "coverage_pass": False},
            ),
            (
                downstream_validate.enforce_answer_gate,
                self.retired.enforce_answer_gate,
                {"four_type_pass": False},
            ),
            (
                downstream_validate.enforce_compare_gate,
                self.retired.enforce_compare_gate,
                {"comparison_pass": False},
            ),
        ]
        for new_gate, old_gate, metrics in cases:
            with self.assertRaises(Exception) as old_error:
                old_gate(metrics)
            with self.assertRaises(Exception) as new_error:
                new_gate(metrics)
            self.assertEqual(str(new_error.exception), str(old_error.exception))


if __name__ == "__main__":
    unittest.main()
