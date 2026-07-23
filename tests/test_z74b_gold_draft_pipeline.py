from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z74b_gold_draft_pipeline.py"
SPEC = importlib.util.spec_from_file_location("z74b_gold_draft_pipeline", MODULE_PATH)
assert SPEC and SPEC.loader
z74b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z74b)


class Z74BGoldDraftPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.booklist, cls.gaps = z74b.build_booklist()
        cls.drafts = [z74b.build_draft(book) for book in cls.booklist["books"]]
        cls.drafts_by_id = {draft["source"]["book_id"]: draft for draft in cls.drafts}
        cls.anchor_audit = z74b.validate_anchors(cls.drafts)

    @staticmethod
    def parts(draft: dict) -> list[dict]:
        return [part for item in draft["layered_items"] for part in item["parts"]]

    def test_cache_inventory_count_and_recognized_heading_count_are_separate(self) -> None:
        self.assertEqual([], self.gaps)
        expected_cache = {
            "Z74B-B01": 228,
            "Z74B-B02": 1359,
            "Z74B-B03": 1617,
            "Z74B-B04": 772,
            "Z74B-B05": 2562,
        }
        expected_headings = {
            "Z74B-B01": 148,
            "Z74B-B02": 1332,
            "Z74B-B03": 1606,
            "Z74B-B04": 772,
            "Z74B-B05": 2562,
        }
        for book in self.booklist["books"]:
            book_id = book["book_id"]
            self.assertEqual(expected_cache[book_id], book["cache_unit_total"])
            self.assertEqual(expected_headings[book_id], book["recognized_heading_total"])
            self.assertEqual(50, len(book["inventory_units_1_to_50"]))
            self.assertEqual(
                list(range(1, 51)),
                [unit["inventory_unit"] for unit in book["inventory_units_1_to_50"]],
            )
            self.assertIn("不冒充库存单元总数", book["counting_boundary"]["recognized_heading_total_role"])

    def test_first_50_cache_headings_and_bodies_match_full_txt_in_order(self) -> None:
        for book in self.booklist["books"]:
            full_text = Path(book["source_real_path"]).read_text(encoding="utf-8")
            previous_end = -1
            trim_applied = 0
            for unit in book["inventory_units_1_to_50"]:
                cache_path = Path(unit["cache_file_path"])
                cache_text = cache_path.read_text(encoding="utf-8")
                complete_heading, separator, raw_body = cache_text.partition("\n")
                self.assertTrue(separator)
                complete_heading = complete_heading.rstrip("\r")
                body, trim = z74b.trim_cache_body(book["book_id"], raw_body.lstrip("\r\n"))
                trim_applied += int(trim["applied"])
                self.assertEqual(unit["complete_heading"], complete_heading)
                self.assertEqual(unit["cache_file_sha256"], z74b.sha256(cache_path))
                self.assertEqual(
                    unit["cache_body_sha256"],
                    hashlib.sha256(body.encode("utf-8")).hexdigest(),
                )
                self.assertEqual(
                    body,
                    full_text[unit["full_txt_start_char"] : unit["full_txt_end_char_exclusive"]],
                )
                self.assertEqual(
                    complete_heading,
                    full_text[
                        unit["full_txt_heading_start_char"] : unit["full_txt_heading_end_char_exclusive"]
                    ],
                )
                gap = full_text[
                    unit["full_txt_heading_end_char_exclusive"] : unit["full_txt_start_char"]
                ]
                self.assertTrue(gap)
                self.assertFalse(gap.strip())
                self.assertGreaterEqual(unit["full_txt_heading_start_char"], previous_end)
                previous_end = unit["full_txt_end_char_exclusive"]
            if book["book_id"] == "Z74B-B01":
                self.assertGreater(trim_applied, 0)

    def test_external_ai_signal_is_nonblocking_observation(self) -> None:
        spec = dict(z74b.BOOK_SPECS[0])
        spec["signal_rel"] = "TEMP/Z74B_不存在的非阻断旁证.md"
        book, gaps = z74b.validate_book(spec)
        self.assertEqual([], gaps)
        self.assertEqual("verified_cache_inventory_and_full_txt_readback", book["truth_status"])
        self.assertFalse(book["selection_signal"]["present"])
        self.assertFalse(book["selection_signal"]["controls_target_or_generation"])
        self.assertTrue(book["selection_signal"]["warnings"])
        self.assertEqual(33, z74b.build_draft(book)["source"]["inventory_unit"])

    def test_target_units_and_infinite_dual_key_are_fixed(self) -> None:
        expected = {
            "Z74B-B01": (33, "第33回 生存环境改善指南"),
            "Z74B-B02": (39, "第39章 道元班开课了！"),
            "Z74B-B03": (41, "第41章 再次出现的尸臭"),
            "Z74B-B04": (3, "第二章 死亡擦肩而过（上）"),
            "Z74B-B05": (30, "第30章 枭雄末路"),
        }
        for book in self.booklist["books"]:
            ordinal, heading_fragment = expected[book["book_id"]]
            self.assertEqual(ordinal, book["target_unit"]["inventory_unit"])
            self.assertIn(heading_fragment, book["target_unit"]["complete_heading"])
            self.assertTrue(book["target_unit"]["cache_file_sha256"])
        infinite = next(book for book in self.booklist["books"] if book["book_id"] == "Z74B-B04")
        self.assertEqual(3, infinite["target_unit"]["inventory_unit"])
        self.assertEqual("二", infinite["target_unit"]["raw_number"])

    def test_candidate_layers_are_66_plus_10_and_hindsight_never_scores(self) -> None:
        expected_on_unit = {
            "Z74B-B01": 18,
            "Z74B-B02": 8,
            "Z74B-B03": 14,
            "Z74B-B04": 14,
            "Z74B-B05": 12,
        }
        self.assertEqual(66, sum(d["layer_summary"]["on_unit_candidate_part_total"] for d in self.drafts))
        self.assertEqual(10, sum(d["layer_summary"]["hindsight_part_total"] for d in self.drafts))
        for draft in self.drafts:
            book_id = draft["source"]["book_id"]
            self.assertEqual(expected_on_unit[book_id], draft["layer_summary"]["on_unit_candidate_part_total"])
            self.assertEqual(2, draft["layer_summary"]["hindsight_part_total"])
            self.assertEqual([1, 50], draft["source_window"]["inventory_window"])
            self.assertEqual(50, draft["source_window"]["hindsight_review_window"][1])
            self.assertEqual("candidate_pending_cz_review", draft["status"])
            self.assertEqual("silver_draft_not_formal_gold", draft["candidate_level"])
            for part in self.parts(draft):
                if part["layer"] == "回看件":
                    self.assertFalse(part["score_in_single_chapter"])
                    evidence_units = {row["inventory_unit"] for row in part["source_evidence"]}
                    self.assertTrue(all(draft["source"]["inventory_unit"] < unit <= 50 for unit in evidence_units))

    def test_all_160_anchors_read_back_from_cache_and_full_txt(self) -> None:
        self.assertEqual("pass_all_cache_and_full_txt_anchors_in_inventory_window", self.anchor_audit["status"])
        self.assertEqual(160, self.anchor_audit["anchor_total"])
        self.assertEqual(0, self.anchor_audit["failed_total"])
        self.assertTrue(all(row["cache_quote_verbatim_readback"] for row in self.anchor_audit["checks"]))
        self.assertTrue(all(row["full_txt_quote_verbatim_readback"] for row in self.anchor_audit["checks"]))
        self.assertTrue(all(row["cache_identity_valid"] for row in self.anchor_audit["checks"]))
        self.assertTrue(all(10 <= row["quote_char_count"] <= 25 for row in self.anchor_audit["checks"]))

    def test_reviewed_strength_guards_and_required_splits_are_present(self) -> None:
        claims = {
            book_id: [part["claim"] for part in self.parts(draft)]
            for book_id, draft in self.drafts_by_id.items()
        }
        self.assertTrue(any("或许能得到想要的答案" in claim for claim in claims["Z74B-B03"]))
        self.assertTrue(any("被点名进入激光通道" in claim and "可能增加难度" in claim for claim in claims["Z74B-B04"]))
        self.assertTrue(any("自称并告知" in claim for claim in claims["Z74B-B05"]))
        forbidden = ("确定交换", "客观兑现", "保护伞公司", "成年人不能中途改练", "被剧情惯性推入")
        self.assertFalse(any(term in claim for book_claims in claims.values() for claim in book_claims for term in forbidden))

        actions = {
            book_id: {part["claim_components"]["action_or_cognition_or_intention"] for part in self.parts(draft)}
            for book_id, draft in self.drafts_by_id.items()
        }
        self.assertIn("把暮苍斋失序定性为刁奴欺主", actions["Z74B-B01"])
        self.assertIn("指派王氏教明兰收拾院子", actions["Z74B-B01"])
        self.assertIn("拒绝回到长枫身边", actions["Z74B-B01"])
        self.assertIn("以长枫没有保护可儿为反证", actions["Z74B-B01"])
        self.assertIn("以母亲做妾后的遭遇为反证", actions["Z74B-B01"])
        self.assertIn("封闭整个蜂房", actions["Z74B-B04"])
        self.assertIn("使用内部防御系统杀人", actions["Z74B-B04"])
        self.assertIn("遭亲信暗算并控制住伤势发作", actions["Z74B-B05"])
        self.assertIn("抛下基业和家人并销声匿迹", actions["Z74B-B05"])

    def test_every_part_has_manual_four_field_coverage_ledger(self) -> None:
        expected_fields = {
            "subject",
            "action_or_cognition_or_intention",
            "object",
            "explicit_result_or_constraint",
        }
        for draft in self.drafts:
            for part in self.parts(draft):
                ledger = part["semantic_coverage_ledger"]
                self.assertEqual("human_checked_candidate_pending_cz_review", ledger["review_status"])
                self.assertEqual(expected_fields, set(ledger["fields"]))
                evidence_ids = {row["anchor_id"] for row in part["source_evidence"]}
                for field in ledger["fields"].values():
                    self.assertTrue(field["text"])
                    self.assertEqual(evidence_ids, set(field["support_anchor_ids"]))

    def test_protected_state_is_zero_call_and_not_promoted(self) -> None:
        for draft in self.drafts:
            protected = draft["protected_state"]
            self.assertEqual(0, protected["model_api_calls"])
            self.assertEqual(0, protected["network_requests"])
            self.assertEqual(0, protected["token_usage"])
            self.assertFalse(protected["formal_gold_promoted"])
            self.assertFalse(protected["gold_pointer_changed"])
            self.assertFalse(protected["extract_contract_changed"])
            self.assertFalse(protected["active_122_changed"])
            self.assertFalse(protected["classification_or_outbox_changed"])

    def test_two_isolated_builds_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="z74b-test-repeat-") as raw:
            root = Path(raw)
            out1 = root / "pass1"
            out2 = root / "pass2"
            result1 = z74b.write_outputs(out1)
            result2 = z74b.write_outputs(out2)
            self.assertEqual(result1["core_fingerprint"], result2["core_fingerprint"])
            self.assertEqual(result1["core_files"], result2["core_files"])
            self.assertFalse(any("第0033章" in name for name in result1["core_files"]))
            for name in result1["core_files"]:
                self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes())
            report = (out1 / "第74道B线停点回包｜五本结构层候选底稿_20260721.md").read_text(encoding="utf-8")
            self.assertIn("## 四｜回执", report)
            self.assertIn("模型 API 0、内容网络 0、token 0、重试 0", report)
            self.assertIn("当单元候选 66 条，回看件 10 条，双载体逐字回读锚 160 条", report)
            self.assertIn("机械通过不等于结构语义通过", report)


if __name__ == "__main__":
    unittest.main()
