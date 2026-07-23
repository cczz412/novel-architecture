from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z74a_rewrite_examples.py"
SPEC = importlib.util.spec_from_file_location("z74a_rewrite_examples", MODULE_PATH)
assert SPEC and SPEC.loader
z74a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z74a)


class Z74ARewriteExamplesTest(unittest.TestCase):
    def test_has_four_types_four_subpatterns_and_triplets(self) -> None:
        candidate = z74a.build_model_candidate()
        receipt = z74a.validate_model_candidate(candidate)
        self.assertEqual("pass", receipt["status"])
        self.assertEqual(4, receipt["pathology_type_total"])
        self.assertEqual(16, receipt["triplet_group_total"])
        self.assertEqual(48, receipt["variant_total"])
        self.assertEqual({4}, set(receipt["type_counts"].values()))
        self.assertEqual(4, receipt["wrong_anchor_case_total"])
        self.assertEqual(z74a.CANDIDATE_STATUS, candidate["status"])
        self.assertEqual("候选银标／未语义审定／不固化不升默认", candidate["status_label"])

    def test_just_right_declares_count_and_complete_fields(self) -> None:
        for group in z74a.build_triplets():
            just_right = group["just_right"]
            self.assertEqual(just_right["expected_record_count"], len(just_right["records"]))
            self.assertGreater(just_right["expected_record_count"], 0)
            for record in just_right["records"]:
                for key in (
                    "subject",
                    "action",
                    "result",
                    "necessary_qualifiers",
                    "text",
                    "anchors",
                    "anchor_support",
                ):
                    self.assertTrue(record[key], (group["group_id"], key))
                for anchor in record["anchors"]:
                    self.assertGreaterEqual(len(anchor), 10)
                    self.assertLessEqual(len(anchor), 25)
                    self.assertTrue(any(anchor in text for text in group["source_scenario"]))

    def test_all_z71_and_z73_source_rows_are_integrated(self) -> None:
        material = z74a.build_source_material(z74a.DEFAULT_Z71_DIR, z74a.DEFAULT_Z73_DIR)
        self.assertEqual("source_only_not_prompt_visible", material["status"])
        self.assertFalse(material["future_prompt_visibility"])
        ledgers = material["z71_full_ledgers"]
        self.assertEqual(32, ledgers["fill_rows"]["row_total"])
        self.assertEqual(14, ledgers["gold_rows"]["row_total"])
        self.assertEqual(34, ledgers["current_rows"]["row_total"])
        four_round = material["z73_four_round_formal_parts"]
        self.assertEqual(4, four_round["round_total"])
        self.assertEqual(23, four_round["part_rows_per_round"])
        self.assertEqual(92, four_round["row_total"])
        self.assertEqual(92, sum(four_round["verdict_counts"].values()))
        self.assertTrue(four_round["invalid_anchor_rows"]["rows"])
        self.assertTrue(
            all(
                row["verdict"] == "coverage_only_invalid_support"
                for row in four_round["invalid_anchor_rows"]["rows"]
            )
        )
        for category in ("uncertain_cognition", "intention_or_plan", "background_or_limitation"):
            section = four_round["categorized_non_strict_rows"][category]
            self.assertGreater(section["row_total"], 0)
            self.assertTrue(all(row["verdict"] != "strict_hit" for row in section["rows"]))
        self.assertTrue(z74a.build_model_candidate()["provenance_is_excluded"])

    def test_all_16_subpatterns_have_resolvable_evidence_pointers(self) -> None:
        material = z74a.build_source_material(z74a.DEFAULT_Z71_DIR, z74a.DEFAULT_Z73_DIR)
        evidence = material["subpattern_evidence_map"]
        self.assertEqual(16, evidence["group_total"])
        self.assertEqual(16, len(evidence["rows"]))
        documents: dict[str, object] = {}

        def resolve_pointer(document: object, pointer: str) -> object:
            current = document
            for part in pointer.removeprefix("/").split("/"):
                current = current[int(part)] if isinstance(current, list) else current[part]
            return current

        for group in evidence["rows"]:
            self.assertGreater(group["evidence_ref_total"], 0)
            self.assertEqual(group["evidence_ref_total"], len(group["evidence_refs"]))
            for ref in group["evidence_refs"]:
                source = ref["source"]
                if source not in documents:
                    documents[source] = json.loads((ROOT / source).read_text(encoding="utf-8"))
                row = resolve_pointer(documents[source], ref["json_pointer"])
                self.assertIsInstance(row, dict)
                self.assertEqual(ref["verdict"], row["verdict"])
                for key, value in ref["locator"].items():
                    if key != "round_id":
                        self.assertEqual(value, row[key])
        large_01 = next(row for row in evidence["rows"] if row["group_id"] == "LARGE-01")
        self.assertIn(
            "EV-C0003-11",
            [ref["locator"].get("event_id") for ref in large_01["evidence_refs"]],
        )

    def test_four_anchor_pathologies_carry_mechanically_partial_wrong_anchors(self) -> None:
        groups = {group["group_id"]: group for group in z74a.build_triplets()}
        expected_true_claims = {
            "ANCHOR-01": "配送员把三箱样品送到接待台，接待员核对封条后完成签收。",
            "ANCHOR-02": "操作员按下复位键，指示灯由红色转为绿色。",
            "ANCHOR-03": "文员把退货单夹进蓝色文件夹，旁边的助理随后关上窗户。",
            "ANCHOR-04": "主管说：下午先清点三号货架，核完后把缺件数发给我；如果差额超过三件，暂停发货并通知值班经理。",
        }
        wrong_cases = []
        for group_id in ("ANCHOR-01", "ANCHOR-02", "ANCHOR-03", "ANCHOR-04"):
            group = groups[group_id]
            located_claims = []
            for variant_name in ("too_large", "too_small"):
                for record in group[variant_name]["records"]:
                    if "wrong_anchor_case" in record:
                        wrong_cases.append(record["wrong_anchor_case"])
                        located_claims.append(record["text"])
            self.assertEqual([expected_true_claims[group_id]], located_claims)
        self.assertEqual(4, len(wrong_cases))
        for case in wrong_cases:
            joined_anchors = z74a.normalize_text("\n".join(case["anchors"]))
            self.assertTrue(case["supported_claim_terms"])
            self.assertTrue(case["unsupported_claim_terms"])
            for terms in case["supported_claim_terms"].values():
                self.assertTrue(all(z74a.normalize_text(term) in joined_anchors for term in terms))
            for terms in case["unsupported_claim_terms"].values():
                self.assertTrue(all(z74a.normalize_text(term) not in joined_anchors for term in terms))

    def test_reviewed_granularity_edge_cases_stay_fixed(self) -> None:
        groups = {group["group_id"]: group for group in z74a.build_triplets()}
        large_03_text = "\n".join(
            row["text"] for row in groups["LARGE-03"]["too_large"]["records"]
        )
        self.assertNotIn("完成", large_03_text)
        self.assertEqual(
            ["检验员", "规程", "本页"],
            [row["subject"] for row in groups["LARGE-04"]["just_right"]["records"]],
        )
        self.assertEqual(
            ["管理员", "值班同事"],
            [row["subject"] for row in groups["SMALL-02"]["just_right"]["records"]],
        )
        for group_id in ("SMALL-01", "SMALL-02", "SMALL-03", "SMALL-04"):
            check = groups[group_id]["too_large"]["granularity_only_check"]
            self.assertEqual(0, check["invented_action_count"])
            source = z74a.normalize_text("\n".join(groups[group_id]["source_scenario"]))
            merged = z74a.normalize_text(
                "\n".join(row["text"] for row in groups[group_id]["too_large"]["records"])
            )
            for term in check["source_action_terms"]:
                self.assertIn(z74a.normalize_text(term), source)
                self.assertIn(z74a.normalize_text(term), merged)

    def test_protected_term_and_plot_signature_are_detected(self) -> None:
        candidate = z74a.build_model_candidate()
        candidate["groups"][0]["source_scenario"].append("测试文本含克莱恩和修仙。")
        model_text = z74a.normalize_text("\n".join(z74a.iter_string_values(candidate)))
        protected = [
            term
            for categories in z74a.PROTECTED_TERMS.values()
            for terms in categories.values()
            for term in terms
            if z74a.normalize_text(term) in model_text
        ]
        signatures = [term for term in z74a.PLOT_SIGNATURE_TERMS if z74a.normalize_text(term) in model_text]
        self.assertIn("克莱恩", protected)
        self.assertIn("修仙", signatures)

    def test_literal_matcher_detects_normalized_long_fragment(self) -> None:
        fragment = z74a.normalize_text("管理员切换到备用服务，页面恢复正常访问")[:18]
        matcher = z74a.LiteralMatcher([fragment])
        corpus = z74a.normalize_text("无关开头。管理员切换到备用服务，页面恢复正常访问。无关结尾。")
        self.assertEqual({fragment}, matcher.find(corpus))

    def test_corpus_parameter_requires_six_fixed_labels(self) -> None:
        with self.assertRaises(ValueError):
            z74a.parse_corpus_args(["X01_诡秘之主=/tmp/a"])

    def test_default_candidate_has_no_protected_or_signature_terms(self) -> None:
        candidate = z74a.build_model_candidate()
        model_text = z74a.normalize_text("\n".join(z74a.iter_string_values(candidate)))
        hits = [
            term
            for categories in z74a.PROTECTED_TERMS.values()
            for terms in categories.values()
            for term in terms
            if z74a.normalize_text(term) in model_text
        ]
        signature_hits = [
            term for term in z74a.PLOT_SIGNATURE_TERMS if z74a.normalize_text(term) in model_text
        ]
        self.assertEqual([], hits)
        self.assertEqual([], signature_hits)

    def test_real_corpus_windows_stop_at_authorized_boundaries(self) -> None:
        rows = {}
        for label, path in z74a.DEFAULT_CORPORA.items():
            _text, row = z74a.load_corpus_window(label, path)
            rows[label] = row
        self.assertEqual(200, rows["X01_诡秘之主"]["window_chapter_count"])
        self.assertEqual(200, rows["X01_诡秘之主"]["window_end_chapter"])
        for label in set(rows) - {"X01_诡秘之主"}:
            self.assertEqual(50, rows[label]["window_chapter_count"])
            self.assertEqual(50, rows[label]["window_end_chapter"])
            self.assertIn("window_next_heading", rows[label])

    def test_real_six_window_decoupling_is_zero(self) -> None:
        receipt = z74a.audit_decoupling(z74a.build_model_candidate(), z74a.DEFAULT_CORPORA)
        self.assertEqual("pass", receipt["status"])
        self.assertEqual(6, len(receipt["corpora"]))
        for gate in receipt["gates"].values():
            self.assertEqual("pass", gate["status"])

    def test_manual_structure_review_is_per_group_not_template_repetition(self) -> None:
        review = z74a.build_structure_review(z74a.build_model_candidate())
        self.assertEqual("pass", review["status"])
        self.assertEqual(16, len(review["rows"]))
        self.assertEqual(16, len({row["reason"] for row in review["rows"]}))
        self.assertTrue(all(row["manual_structure_review"] == "pass" for row in review["rows"]))

    def test_verify_bundle_checks_outputs_inputs_builder_test_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            out = Path(raw)
            payload = out / "a.json"
            input_file = out / "input.json"
            builder = out / "builder.py"
            test_file = out / "test_builder.py"
            payload.write_text("ok", encoding="utf-8")
            input_file.write_text("input", encoding="utf-8")
            builder.write_text("builder", encoding="utf-8")
            test_file.write_text("test", encoding="utf-8")
            manifest = {
                "outputs": [
                    {
                        "path": "a.json",
                        "bytes": payload.stat().st_size,
                        "sha256": z74a.sha256_path(payload),
                    }
                ],
                "inputs": [
                    {
                        "path": str(input_file),
                        "bytes": input_file.stat().st_size,
                        "sha256": z74a.sha256_path(input_file),
                    }
                ],
                "builder": {"path": str(builder), "sha256": z74a.sha256_path(builder)},
                "test_file": {"path": str(test_file), "sha256": z74a.sha256_path(test_file)},
                "corpora": [],
            }
            manifest_path = out / z74a.MANIFEST_FILE
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (out / z74a.SHA_FILE).write_text(
                f"{z74a.sha256_path(payload)}  a.json\n"
                f"{z74a.sha256_path(manifest_path)}  {z74a.MANIFEST_FILE}\n",
                encoding="utf-8",
            )
            receipt = z74a.verify_bundle(out)
            self.assertEqual("pass", receipt["status"])
            self.assertEqual(
                {
                    "outputs": 1,
                    "inputs": 1,
                    "builder": 1,
                    "test_file": 1,
                    "corpora": 0,
                    "checksums": 2,
                },
                receipt["checked"],
            )
            input_file.write_text("changed", encoding="utf-8")
            failed = z74a.verify_bundle(out)
            self.assertEqual("fail", failed["status"])
            self.assertIn("inputs", {row["scope"] for row in failed["mismatches"]})


if __name__ == "__main__":
    unittest.main()
