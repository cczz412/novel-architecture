from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from zbatch_modules import (  # noqa: E402
    candidate_envelope,
    classify_rules,
    neutral_extract,
    stage_sampling,
    verbatim_restatement,
)
from zbatch_modules.errors import ZBatchError  # noqa: E402


RUN_ID = "Z00n_X01_第6至10章程序清点单变量_5章_v1.1_20260717"
RUN = ROOT / "runs" / RUN_ID
Z00P_RUN = ROOT / "runs/Z00p_X01_第1至20章正式扩大_20章_v1.0_20260718"
CLASSIFY_CONTRACT_PATH = ROOT / "config/contracts/classify_rules_v1.json"
SAMPLING_CONTRACT_PATH = ROOT / "config/contracts/sensenova_stage_sampling_v1.json"
NEUTRAL_PROMPT_PATH = ROOT / "work/zbatch_prompts/candidates/extract_event_only_no_self_audit_v1.1.md"
NEUTRAL_PROMPT_SHA = "91270576f44986bc0c2610bedb93e28fca90000688bb0f5a40caa72a594c3c7f"
VERBATIM_PROMPT_PATH = ROOT / "work/zbatch_prompts/candidates/verbatim_restatement_v1.0.md"
VERBATIM_PROMPT_SHA = "a66900697a61e79a63c89174138ef0fbd4576d109ed9008b91aeab5f773e700c"


class ExtractModuleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = classify_rules.load_contract(CLASSIFY_CONTRACT_PATH, project_root=ROOT)
        cls.promoted = classify_rules.promote_approved_reference(cls.contract, project_root=ROOT)
        cls.v1 = json.loads(
            (ROOT / "work/zbatch_decisions/Z00n_X01_ch6_10_main_control_decisions_v1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.event_documents = []
        cls.raw_documents = {}
        cls.catalog_entries = {}
        cls.catalog_maps = {}
        for chapter in range(6, 11):
            parsed = json.loads(
                (RUN / f"01_event_extract/parsed/ch{chapter:04d}.json").read_text(encoding="utf-8")
            )
            catalog = json.loads(
                (RUN / f"01_event_extract/evidence_catalogs/ch{chapter:04d}.json").read_text(
                    encoding="utf-8"
                )
            )["entries"]
            raw = {
                "schema_version": parsed["schema_version"],
                "chapter": chapter,
                "events": [
                    {
                        "event_id": event["event_id"],
                        "event": event["event"],
                        "anchors": [{"anchor_id": anchor["anchor_id"]} for anchor in event["anchors"]],
                    }
                    for event in parsed["events"]
                ],
            }
            cls.event_documents.append(parsed)
            cls.raw_documents[chapter] = raw
            cls.catalog_entries[chapter] = catalog
            cls.catalog_maps[chapter] = {row["anchor_id"]: row["quote"] for row in catalog}
        cls.compilation = classify_rules.compile_records(
            cls.event_documents,
            cls.promoted,
            contract=cls.contract,
        )
        cls.decision_map = {row["event_id"]: row for row in cls.promoted["decisions"]}

    def _document(self, rows: list[dict], run_id: str = "SYNTHETIC") -> dict:
        return {
            "schema_version": self.contract.decision_schema_version,
            "run_id": run_id,
            "rules_sha256": self.contract.rules_sha256,
            "decisions": rows,
        }

    def test_neutral_extract_matches_all_five_z00n_program_audits_and_events(self):
        for chapter in range(6, 11):
            raw = self.raw_documents[chapter]
            catalog = self.catalog_entries[chapter]
            materialized, audit = neutral_extract.process_model_data(
                raw,
                chapter=chapter,
                catalog=catalog,
            )
            stored_event = json.loads(
                (RUN / f"01_event_extract/parsed/ch{chapter:04d}.json").read_text(encoding="utf-8")
            )
            stored_audit = json.loads(
                (RUN / f"01_event_extract/program_audits/ch{chapter:04d}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(materialized, stored_event, chapter)
            self.assertEqual(audit, stored_audit, chapter)
            self.assertFalse(audit["scope_note"].startswith("语义无遗漏"))

    def test_neutral_prompt_messages_match_all_five_real_z00n_requests(self):
        chapter_dir = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters"
        for chapter in range(6, 11):
            chapter_file = next(chapter_dir.glob(f"{chapter:04d}_*.txt"))
            built = neutral_extract.build_messages(
                prompt_path=NEUTRAL_PROMPT_PATH,
                expected_prompt_sha256=NEUTRAL_PROMPT_SHA,
                chapter=chapter,
                chapter_filename=chapter_file.name,
                catalog=self.catalog_entries[chapter],
            )
            stored = json.loads(
                (RUN / f"requests/extract/ch{chapter:04d}_request.json").read_text(encoding="utf-8")
            )
            self.assertEqual(built["messages"], stored["body"]["messages"], chapter)

    def test_neutral_extract_rejects_self_audit_and_classification_fields(self):
        raw = copy.deepcopy(self.raw_documents[6])
        raw["coverage_audit"] = {"event_ids": []}
        reasons, _ = neutral_extract.audit_event_envelope(raw, 6, self.catalog_entries[6])
        self.assertIn("事件外壳字段不等于固定合同", reasons)
        raw = copy.deepcopy(self.raw_documents[6])
        raw["events"][0]["primary_type"] = "A"
        reasons, _ = neutral_extract.audit_event_envelope(raw, 6, self.catalog_entries[6])
        self.assertTrue(any("字段越出中性事件合同" in reason for reason in reasons))

    def test_neutral_extract_rejects_empty_events(self):
        raw = {"schema_version": "z-event-v1", "chapter": 6, "events": []}
        reasons, audit = neutral_extract.audit_event_envelope(raw, 6, self.catalog_entries[6])
        self.assertEqual(reasons, ["events为空"])
        self.assertEqual(audit["status"], "fail")

    def test_neutral_event_summary_boundary_is_six_to_one_hundred_nonspace_chars(self):
        def reasons_for(value: str) -> list[str]:
            raw = copy.deepcopy(self.raw_documents[6])
            raw["events"][0]["event"] = value
            reasons, _ = neutral_extract.audit_event_envelope(
                raw,
                6,
                self.catalog_entries[6],
            )
            return reasons

        self.assertTrue(any("事件摘要长度非法" in reason for reason in reasons_for("")))
        self.assertTrue(any("事件摘要长度非法" in reason for reason in reasons_for("摘要五个字")))
        self.assertFalse(any("事件摘要长度非法" in reason for reason in reasons_for("摘要恰好六字")))
        self.assertFalse(any("事件摘要长度非法" in reason for reason in reasons_for("甲" * 100)))
        self.assertTrue(any("事件摘要长度非法" in reason for reason in reasons_for("甲" * 101)))

    def test_z00p_first_six_raw_api_responses_revalidate_without_model_calls(self):
        for chapter in range(1, 7):
            response = json.loads(
                (Z00P_RUN / f"responses/neutral_extract/ch{chapter:04d}_raw.json").read_text(
                    encoding="utf-8"
                )
            )
            content = response["choices"][0]["message"]["content"]
            raw_document = candidate_envelope.parse_json_content(content)
            catalog = json.loads(
                (Z00P_RUN / f"01_extract/evidence_catalogs/ch{chapter:04d}.json").read_text(
                    encoding="utf-8"
                )
            )["entries"]
            materialized, audit = neutral_extract.process_model_data(
                raw_document,
                chapter=chapter,
                catalog=catalog,
            )
            self.assertEqual(audit["status"], "pass", chapter)
            if chapter <= 5:
                stored_event = json.loads(
                    (Z00P_RUN / f"01_extract/events/ch{chapter:04d}.json").read_text(
                        encoding="utf-8"
                    )
                )
                stored_audit = json.loads(
                    (Z00P_RUN / f"01_extract/program_audits/ch{chapter:04d}.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(materialized, stored_event, chapter)
                self.assertEqual(audit, stored_audit, chapter)
            else:
                self.assertEqual(len(materialized["events"]), 14)
                self.assertEqual(materialized["events"][-1]["event"], "周明瑞自称愚者")

    def test_approved_v2_promotes_without_mutating_history_and_regressions_pass(self):
        source = json.loads(
            (ROOT / self.contract.predecessor_decisions_path).read_text(encoding="utf-8")
        )
        self.assertEqual(source["rules_sha256"], self.contract.predecessor_rules_sha256)
        self.assertEqual(self.promoted["rules_sha256"], self.contract.rules_sha256)
        event_ids = set(classify_rules.index_events(self.event_documents)[0])
        self.assertEqual(
            classify_rules.decision_reasons(
                self.promoted,
                run_id=RUN_ID,
                event_ids=event_ids,
                contract=self.contract,
            ),
            [],
        )
        self.assertEqual(classify_rules.regression_reasons(self.promoted, contract=self.contract), [])

    def test_initial_v1_fails_the_three_approved_regression_pins(self):
        v1 = copy.deepcopy(self.v1)
        v1["rules_sha256"] = self.contract.rules_sha256
        reasons = classify_rules.regression_reasons(v1, contract=self.contract)
        self.assertTrue(any("return_mechanism" in reason for reason in reasons))
        self.assertTrue(any("regular_meeting" in reason for reason in reasons))
        self.assertTrue(any("single_observation" in reason for reason in reasons))

    def test_generic_duplicate_rule_passes_with_renamed_event_ids(self):
        winner = copy.deepcopy(self.decision_map["EV-C0006-04"])
        loser = copy.deepcopy(self.decision_map["EV-C0006-05"])
        winner["event_id"] = "EV-C0099-01"
        loser["event_id"] = "EV-C0099-02"
        winner["duplicate_group"] = loser["duplicate_group"] = "DUP-SYNTHETIC"
        document = self._document([winner, loser])
        reasons = classify_rules.decision_reasons(
            document,
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01", "EV-C0099-02"},
            contract=self.contract,
        )
        self.assertEqual(reasons, [])

    def test_generic_duplicate_rule_rejects_two_classified_representatives(self):
        left = copy.deepcopy(self.decision_map["EV-C0006-04"])
        right = copy.deepcopy(self.decision_map["EV-C0007-10"])
        left["event_id"] = "EV-C0099-01"
        right["event_id"] = "EV-C0099-02"
        left["duplicate_group"] = right["duplicate_group"] = "DUP-SYNTHETIC"
        right["conflict_reason"] = "同一事实组不应同时保留两条成记录。"
        document = self._document([left, right])
        reasons = classify_rules.decision_reasons(
            document,
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01", "EV-C0099-02"},
            contract=self.contract,
        )
        self.assertIn("重复组DUP-SYNTHETIC必须恰留1条成记录", reasons)

    def test_classified_related_event_with_invalid_id_reports_reason_without_crashing(self):
        left = copy.deepcopy(self.decision_map["EV-C0006-01"])
        right = copy.deepcopy(self.decision_map["EV-C0006-07"])
        left["event_id"] = "EV-C0099-01"
        right["event_id"] = "broken-id"
        left["related_event_ids"] = ["broken-id"]
        document = self._document([left, right])
        reasons = classify_rules.decision_reasons(
            document,
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01", "broken-id"},
            contract=self.contract,
        )
        self.assertIn("broken-id事件ID格式非法", reasons)
        self.assertIn("EV-C0099-01关联事件ID格式非法：broken-id", reasons)

    def test_classified_related_event_field_rejects_non_list_without_crashing(self):
        row = copy.deepcopy(self.decision_map["EV-C0006-01"])
        row["event_id"] = "EV-C0099-01"
        row["related_event_ids"] = 1
        reasons = classify_rules.decision_reasons(
            self._document([row]),
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01"},
            contract=self.contract,
        )
        self.assertIn("EV-C0099-01关联事件ID非法", reasons)

    def test_classified_related_event_field_rejects_object_member_without_crashing(self):
        row = copy.deepcopy(self.decision_map["EV-C0006-01"])
        row["event_id"] = "EV-C0099-01"
        row["related_event_ids"] = [{}]
        reasons = classify_rules.decision_reasons(
            self._document([row]),
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01"},
            contract=self.contract,
        )
        self.assertIn("EV-C0099-01关联事件ID非法", reasons)

    def test_classified_related_events_in_same_chapter_still_pass(self):
        left = copy.deepcopy(self.decision_map["EV-C0006-01"])
        right = copy.deepcopy(self.decision_map["EV-C0006-07"])
        left["event_id"] = "EV-C0099-01"
        right["event_id"] = "EV-C0099-02"
        left["related_event_ids"] = ["EV-C0099-02"]
        reasons = classify_rules.decision_reasons(
            self._document([left, right]),
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01", "EV-C0099-02"},
            contract=self.contract,
        )
        self.assertEqual(reasons, [])

    def test_classified_related_events_across_chapters_still_fail(self):
        left = copy.deepcopy(self.decision_map["EV-C0006-01"])
        right = copy.deepcopy(self.decision_map["EV-C0006-07"])
        left["event_id"] = "EV-C0099-01"
        right["event_id"] = "EV-C0100-01"
        left["related_event_ids"] = ["EV-C0100-01"]
        reasons = classify_rules.decision_reasons(
            self._document([left, right]),
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01", "EV-C0100-01"},
            contract=self.contract,
        )
        self.assertIn("EV-C0099-01关联跨章事件", reasons)

    def test_rule_registry_rejects_typo_and_requires_primary_base_rule(self):
        row = copy.deepcopy(self.decision_map["EV-C0006-04"])
        row["event_id"] = "EV-C0099-01"
        row["duplicate_group"] = None
        row["conflict_reason"] = ""
        row["rule_ids"] = ["TYPO-RULE"]
        document = self._document([row])
        reasons = classify_rules.decision_reasons(
            document,
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01"},
            contract=self.contract,
        )
        self.assertTrue(any("含未登记规则编号" in reason for reason in reasons))
        self.assertIn("EV-C0099-01A类缺基础规则A-01", reasons)

    def test_discarded_item_requires_mc07_but_unclassified_keeps_boundary_rules(self):
        discarded = copy.deepcopy(self.decision_map["EV-C0006-05"])
        discarded["event_id"] = "EV-C0099-01"
        discarded["duplicate_group"] = None
        discarded["conflict_reason"] = ""
        discarded["rule_ids"] = ["D-02"]
        reasons = classify_rules.decision_reasons(
            self._document([discarded]),
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01"},
            contract=self.contract,
        )
        self.assertIn("EV-C0099-01丢弃项缺MC-07", reasons)
        unclassified = copy.deepcopy(self.decision_map["EV-C0008-04"])
        unclassified["event_id"] = "EV-C0099-01"
        self.assertEqual(
            classify_rules.decision_reasons(
                self._document([unclassified]),
                run_id="SYNTHETIC",
                event_ids={"EV-C0099-01"},
                contract=self.contract,
            ),
            [],
        )

    def test_single_observation_d03_is_generic_and_requires_a_inference(self):
        row = copy.deepcopy(self.decision_map["EV-C0007-25"])
        row["event_id"] = "EV-C0099-01"
        row["rule_ids"] = ["A-01", "D-03", "主类型-3"]
        document = self._document([row])
        self.assertEqual(
            classify_rules.decision_reasons(
                document,
                run_id="SYNTHETIC",
                event_ids={"EV-C0099-01"},
                contract=self.contract,
            ),
            [],
        )
        row["assertion"] = "明"
        reasons = classify_rules.decision_reasons(
            document,
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01"},
            contract=self.contract,
        )
        self.assertIn("EV-C0099-01D-03只允许命中D后降为A/推", reasons)
        row = copy.deepcopy(self.decision_map["EV-C0007-10"])
        row["event_id"] = "EV-C0099-01"
        row["duplicate_group"] = None
        row["conflict_reason"] = "单次观察规则不能挂到待执行安排。"
        row["rule_ids"].append("D-03")
        reasons = classify_rules.decision_reasons(
            self._document([row]),
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01"},
            contract=self.contract,
        )
        self.assertIn("EV-C0099-01D-03只允许命中D后降为A/推", reasons)

    def test_legitimate_d_can_use_d02_to_exclude_a_policy_prediction(self):
        row = copy.deepcopy(self.decision_map["EV-C0008-19"])
        row["event_id"] = "EV-C0099-01"
        document = self._document([row])
        reasons = classify_rules.decision_reasons(
            document,
            run_id="SYNTHETIC",
            event_ids={"EV-C0099-01"},
            contract=self.contract,
        )
        self.assertEqual(reasons, [])

    def test_compiled_records_match_z00n_v2_exactly(self):
        stored = json.loads((RUN / "03_verify/valid_records.json").read_text(encoding="utf-8"))[
            "records"
        ]
        self.assertEqual(self.compilation["records"], stored)
        self.assertEqual(self.compilation["metrics"]["by_type"], {"A": 28, "B": 9, "C": 3, "D": 3})
        self.assertEqual(self.compilation["metrics"]["classification_model_calls"], 0)

    def test_compiled_records_all_pass_independent_anchor_validation(self):
        chapter_dir = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主/chapters"
        chapters = {}
        for chapter in range(6, 11):
            chapter_file = next(chapter_dir.glob(f"{chapter:04d}_*.txt"))
            chapters[chapter] = {"text": chapter_file.read_text(encoding="utf-8")}
        checked = classify_rules.validate_compiled_records(
            self.compilation,
            chapters=chapters,
            catalogs=self.catalog_maps,
        )
        self.assertEqual(checked["valid_total"], 43)
        self.assertEqual(checked["invalid_total"], 0)
        self.assertEqual(checked["anchor_valid_rate"], 1.0)

    def test_shared_anchor_remains_diagnostic_not_semantic_duplicate(self):
        metrics = self.compilation["metrics"]
        self.assertEqual(metrics["emitted_cross_type_shared_anchor_count"], 1)
        self.assertEqual(metrics["cross_type_semantic_duplicate_groups"], 0)
        self.assertIn("共享锚只作诊断", self.compilation["classification_conflicts"]["gate_note"])

    def test_rules_sha_drift_is_rejected(self):
        raw = json.loads(CLASSIFY_CONTRACT_PATH.read_text(encoding="utf-8"))
        raw["rules"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            path = Path(temp_dir) / "bad_contract.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ZBatchError, "新版分类规则SHA漂移"):
                classify_rules.load_contract(path, project_root=ROOT)

    def test_approved_run_tree_and_legacy_adapters_remain_byte_identical(self):
        self.assertEqual(
            classify_rules.tree_fingerprint(ROOT, RUN),
            self.contract.predecessor_run_tree_fingerprint,
        )
        expected = {
            "tools/z00l_classification_split.py": "7a28e1c151b0d0f21aede010eeace5ba3cc54f1b8003e06869397e516f8504ec",
            "tools/z00m_classification_split.py": "913f1abf502567dd4235df1e657574d2f32d12f2cd8b1de0cb4e1483e599db95",
            "tools/z00n_classification_split.py": "70b5f7d5a5b83b5f34d2620701e1e53fbf2233284448e1f4a5ae0dbe32cf8991",
            "tools/z00n_event_audit.py": "a74b0f660796eb803a746e925a0c7a99b39e3dc62c3f28d618ba961e63a89e7d",
        }
        for relative, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), digest, relative)
        self.assertNotEqual(
            hashlib.sha256((ROOT / "tools/zbatch.py").read_bytes()).hexdigest(),
            "cc4f42f798f8f537524f5a458008ae76f0bbbfea8588c7618dc03be17cbe437b",
        )

    def test_new_modules_do_not_import_old_monolith_or_legacy_adapters(self):
        forbidden = {
            "zbatch",
            "z00l_classification_split",
            "z00m_classification_split",
            "z00n_classification_split",
            "z00n_event_audit",
        }
        for name in ("neutral_extract.py", "classify_rules.py", "verbatim_restatement.py"):
            path = ROOT / "tools/zbatch_modules" / name
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            self.assertFalse(any(item.split(".")[0] in forbidden for item in imports), name)

    def test_step3_sampling_contract_has_neutral_reference_and_locked_verbatim_01(self):
        bundle = stage_sampling.load_contract_bundle(
            SAMPLING_CONTRACT_PATH,
            profile="d_mod_step3_reference",
        )
        neutral = bundle.stage("neutral_extract")
        self.assertEqual((neutral.temperature, neutral.max_tokens, neutral.n), (0.2, 16000, 1))
        verbatim = bundle.candidates["verbatim_restatement"]
        self.assertEqual((verbatim.temperature, verbatim.n), (0.1, 1))
        with self.assertRaisesRegex(ZBatchError, "未验证候选参数"):
            verbatim.assert_callable()

    def test_verbatim_contract_accepts_only_exact_ordered_copy(self):
        text = "原文第一行。\n原文第二行。"
        source = {
            "schema_version": "z-verbatim-restatement-input-v1",
            "items": [
                {
                    "item_id": "ITEM-0001",
                    "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "source_text": text,
                }
            ],
        }
        expected = verbatim_restatement.deterministic_output(source)
        self.assertEqual(verbatim_restatement.output_reasons(expected, source), [])
        built = verbatim_restatement.build_messages(
            source,
            prompt_path=VERBATIM_PROMPT_PATH,
            expected_prompt_sha256=VERBATIM_PROMPT_SHA,
        )
        self.assertEqual(built["messages"][0]["role"], "system")
        altered = copy.deepcopy(expected)
        altered["items"][0]["text"] = "原文第一行。 原文第二行。"
        self.assertIn("输出项1不是逐字原样复述", verbatim_restatement.output_reasons(altered, source))

    def test_verbatim_contract_rejects_missing_extra_and_bad_source_sha(self):
        text = "不能改。"
        source = {
            "schema_version": "z-verbatim-restatement-input-v1",
            "items": [
                {
                    "item_id": "ITEM-0001",
                    "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "source_text": text,
                }
            ],
        }
        missing = {"schema_version": "z-verbatim-restatement-v1", "items": []}
        self.assertIn("复述输出项数变化", verbatim_restatement.output_reasons(missing, source))
        bad_source = copy.deepcopy(source)
        bad_source["items"][0]["source_sha256"] = "0" * 64
        self.assertIn("输入项1原文SHA不匹配", verbatim_restatement.validate_input(bad_source))


if __name__ == "__main__":
    unittest.main()
