from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import pipeline_inspector as inspector


def sample_batch() -> dict:
    return {
        "contract_version": inspector.INPUT_CONTRACT,
        "batch_id": "BATCH-1",
        "decision_scope": "routing_only",
        "sampling_seed": "seed",
        "items": [
            {
                "item_id": "ITEM-1",
                "check_type": "semantic_support",
                "source_kind": "fixture",
                "claim": "甲把书交给乙。",
                "anchors": [
                    {"chapter": 1, "anchor_id": "E0001", "quote": "甲把书交给了乙"}
                ],
                "declared_risks": [],
                "metadata": {},
            }
        ],
    }


def model_output(
    item_id: str = "ITEM-1",
    *,
    anchor_id: str = "E0001",
    quote: str = "甲把书交给了乙",
) -> str:
    return json.dumps(
        {
            "contract_version": inspector.MODEL_OUTPUT_CONTRACT,
            "results": [
                {
                    "item_id": item_id,
                    "decision": "pass_candidate",
                    "support": "direct_support",
                    "rule_ids": ["SEM-01"],
                    "evidence": [
                        {
                            "anchor_id": anchor_id,
                            "quote": quote,
                            "reason": "主体、动作与对象一致",
                        }
                    ],
                    "confidence": 0.9,
                    "needs_strong_review": False,
                    "reason": "锚直接支撑，但只登记通过候选。",
                }
            ],
        },
        ensure_ascii=False,
    )


class PipelineInspectorTests(unittest.TestCase):
    def test_batch_contract_and_duplicate_ids(self) -> None:
        normalized = inspector.validate_review_batch(sample_batch())
        self.assertEqual(normalized["items"][0]["item_id"], "ITEM-1")
        broken = sample_batch()
        broken["items"].append(dict(broken["items"][0]))
        with self.assertRaisesRegex(inspector.InspectorError, "item_id 重复"):
            inspector.validate_review_batch(broken)

    def test_system_prompt_suffix_changes_only_system_message(self) -> None:
        batch = inspector.validate_review_batch(sample_batch())
        baseline = inspector.build_messages(batch, batch["items"])
        suffix = "短引必须逐字复制。"
        candidate = inspector.build_messages(
            batch,
            batch["items"],
            system_prompt_suffix=suffix,
        )
        self.assertEqual(candidate[0]["content"], f"{baseline[0]['content']}\n{suffix}")
        self.assertEqual(candidate[1], baseline[1])
        self.assertEqual(baseline[0]["content"], inspector.SYSTEM_PROMPT)

    def test_system_prompt_suffix_rejects_multiline_or_whitespace(self) -> None:
        batch = inspector.validate_review_batch(sample_batch())
        for suffix in ("", " 短引逐字", "短引逐字 ", "第一行\n第二行"):
            with self.assertRaisesRegex(inspector.InspectorError, "非空单行"):
                inspector.build_messages(
                    batch,
                    batch["items"],
                    system_prompt_suffix=suffix,
                )

    def test_rule_gate_escalates_ambiguity_negation_and_cross_chapter(self) -> None:
        batch = sample_batch()
        batch["items"] = [
            {**batch["items"][0], "item_id": "AMB", "claim": "甲可能把书交给乙。"},
            {**batch["items"][0], "item_id": "NEG", "claim": "甲未把书交给乙。"},
            {
                **batch["items"][0],
                "item_id": "XCH",
                "check_type": "cross_chapter_causality",
                "anchors": [
                    {"chapter": 1, "anchor_id": "E0001", "quote": "甲拿到了书"},
                    {"chapter": 2, "anchor_id": "E0002", "quote": "乙后来离开了"},
                ],
            },
            {**batch["items"][0], "item_id": "SAFE"},
        ]
        normalized = inspector.validate_review_batch(batch)
        api_items, escalated = inspector.split_by_rule_gate(normalized)
        self.assertEqual([row["item_id"] for row in api_items], ["SAFE"])
        self.assertEqual({row["item_id"] for row in escalated}, {"AMB", "NEG", "XCH"})

    def test_model_output_must_preserve_ids_and_quotes(self) -> None:
        batch = inspector.validate_review_batch(sample_batch())
        rows = inspector.parse_model_output(model_output(), batch["items"])
        self.assertEqual(rows[0]["decision"], "pass_candidate")
        altered = json.loads(model_output())
        altered["results"][0]["evidence"][0]["quote"] = "改写短引"
        with self.assertRaisesRegex(inspector.InspectorError, "改写了短引"):
            inspector.parse_model_output(
                json.dumps(altered, ensure_ascii=False), batch["items"]
            )

    def test_anchor_authoritative_substring_policy_fills_full_quote_and_audits(
        self,
    ) -> None:
        raw_batch = sample_batch()
        full_quote = "第1章 标题\n甲把书交给了乙。\n场景结束"
        raw_batch["items"][0]["anchors"][0]["quote"] = full_quote
        batch = inspector.validate_review_batch(raw_batch)
        audit_rows: list[dict] = []

        rows = inspector.parse_model_output(
            model_output(quote="甲把书交给了乙"),
            batch["items"],
            evidence_quote_policy=inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING,
            minimum_quote_nonspace_chars=6,
            quote_fill_audit_rows=audit_rows,
        )

        self.assertEqual(rows[0]["evidence"][0]["quote"], full_quote)
        self.assertEqual(audit_rows[0]["model_quote"], "甲把书交给了乙")
        self.assertEqual(audit_rows[0]["formal_quote"], full_quote)
        self.assertTrue(audit_rows[0]["has_fill_difference"])
        self.assertEqual(
            full_quote[
                audit_rows[0]["substring_start"] : audit_rows[0]["substring_end"]
            ],
            audit_rows[0]["model_quote"],
        )

    def test_anchor_authoritative_substring_policy_rejects_invalid_quotes(self) -> None:
        batch = inspector.validate_review_batch(sample_batch())
        kwargs = {
            "evidence_quote_policy": inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING,
            "minimum_quote_nonspace_chars": 6,
        }

        with self.assertRaisesRegex(inspector.InspectorError, "逐字连续子串"):
            inspector.parse_model_output(
                model_output(quote="甲把书改给了乙"), batch["items"], **kwargs
            )
        with self.assertRaisesRegex(inspector.InspectorError, "低于最短"):
            inspector.parse_model_output(
                model_output(quote="交给乙"), batch["items"], **kwargs
            )
        with self.assertRaisesRegex(inspector.InspectorError, "输入外锚"):
            inspector.parse_model_output(
                model_output(anchor_id="E9999", quote="甲把书交给了乙"),
                batch["items"],
                **kwargs,
            )

        with self.assertRaisesRegex(inspector.InspectorError, "改写了短引"):
            inspector.parse_model_output(
                model_output(quote="把书交给了"), batch["items"]
            )

    def test_punctuation_normalized_substring_policy_accepts_only_mapped_drift(
        self,
    ) -> None:
        raw_batch = sample_batch()
        full_quote = "第1章 标题\n甲说：“把书交给乙。”\n场景结束"
        raw_batch["items"][0]["anchors"][0]["quote"] = full_quote
        batch = inspector.validate_review_batch(raw_batch)
        audit_rows: list[dict] = []
        policy = inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING

        rows = inspector.parse_model_output(
            model_output(quote='甲说:"把书交给乙."'),
            batch["items"],
            evidence_quote_policy=policy,
            minimum_quote_nonspace_chars=6,
            quote_fill_audit_rows=audit_rows,
        )

        self.assertEqual(rows[0]["evidence"][0]["quote"], full_quote)
        self.assertEqual(audit_rows[0]["model_quote"], '甲说:"把书交给乙."')
        self.assertFalse(audit_rows[0]["raw_substring_matched"])
        self.assertIsNone(audit_rows[0]["raw_substring_start"])
        self.assertTrue(audit_rows[0]["normalization_required_for_match"])
        self.assertGreaterEqual(audit_rows[0]["normalized_substring_start"], 0)
        self.assertEqual(
            audit_rows[0]["punctuation_equivalence_sha256"],
            inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256,
        )

        with self.assertRaisesRegex(inspector.InspectorError, "映射表外内容差异"):
            inspector.parse_model_output(
                model_output(quote='甲说:"把笔交给乙."'),
                batch["items"],
                evidence_quote_policy=policy,
                minimum_quote_nonspace_chars=6,
            )
        for invalid_quote in (
            '甲说:"把书交给乙"',
            '甲说: "把书交给乙."',
            '甲说、"把书交给乙."',
        ):
            with self.assertRaisesRegex(
                inspector.InspectorError,
                "映射表外内容差异",
            ):
                inspector.parse_model_output(
                    model_output(quote=invalid_quote),
                    batch["items"],
                    evidence_quote_policy=policy,
                    minimum_quote_nonspace_chars=6,
                )

        with self.assertRaisesRegex(inspector.InspectorError, "低于最短"):
            inspector.parse_model_output(
                model_output(quote="乙。"),
                batch["items"],
                evidence_quote_policy=policy,
                minimum_quote_nonspace_chars=6,
            )

        with self.assertRaisesRegex(inspector.InspectorError, "改写了短引"):
            inspector.parse_model_output(
                model_output(quote='甲说:"把书交给乙."'),
                batch["items"],
            )

    def test_punctuation_mapping_is_longest_first_and_does_not_expand_scope(
        self,
    ) -> None:
        normalized, hits = inspector.normalize_quote_punctuation("“甲……”——（乙？！）")
        self.assertEqual(normalized, '"甲..."--(乙?!)')
        self.assertEqual(
            [row["source"] for row in hits],
            ["“", "……", "”", "——", "（", "？", "！", "）"],
        )
        self.assertEqual(
            inspector.normalize_quote_punctuation("…—、《甲》")[0],
            "…—、《甲》",
        )
        contract = inspector.quote_punctuation_equivalence_contract()
        for group in contract["groups"]:
            for variant in group["variants"]:
                self.assertEqual(
                    inspector.normalize_quote_punctuation(variant)[0],
                    group["canonical"],
                )
        self.assertEqual(contract["content_characters_normalized"], False)
        self.assertEqual(
            inspector.sha256_bytes(inspector.stable_json_bytes(contract)),
            inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256,
        )

    def test_punctuation_normalized_audit_declares_mapping_and_rescued_rows(
        self,
    ) -> None:
        policy = inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_NORMALIZED_SUBSTRING
        record = inspector._quote_fill_audit_record(
            item_id="ITEM-1",
            evidence_index=0,
            anchor_id="E0001",
            model_quote='甲说:"交给乙."',
            formal_quote="甲说：“交给乙。”",
            minimum_quote_nonspace_chars=6,
            evidence_quote_policy=policy,
        )
        audit = inspector.build_quote_fill_audit(
            batch_id="BATCH-1",
            rows=[record],
            minimum_quote_nonspace_chars=6,
            evidence_quote_policy=policy,
        )
        self.assertEqual(audit["normalization_rescued_rows"], 1)
        self.assertEqual(audit["normalization_hit_rows"], 1)
        self.assertEqual(audit["raw_substring_rows"], 0)
        self.assertEqual(
            audit["punctuation_equivalence_contract"],
            inspector.quote_punctuation_equivalence_contract(),
        )
        self.assertEqual(
            audit["punctuation_equivalence_sha256"],
            inspector.QUOTE_PUNCTUATION_EQUIVALENCE_SHA256,
        )

    def test_punctuation_unit_policy_accepts_authorized_equivalence_without_collision(
        self,
    ) -> None:
        raw_batch = sample_batch()
        formal_quote = "标题\n甲说：“稍等……然后出发。”\n尾注"
        raw_batch["items"][0]["anchors"][0]["quote"] = formal_quote
        batch = inspector.validate_review_batch(raw_batch)
        audit_rows: list[dict] = []
        policy = inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING

        rows = inspector.parse_model_output(
            model_output(quote='甲说:"稍等...然后出发."'),
            batch["items"],
            evidence_quote_policy=policy,
            minimum_quote_nonspace_chars=6,
            quote_fill_audit_rows=audit_rows,
        )

        self.assertEqual(rows[0]["evidence"][0]["quote"], formal_quote)
        self.assertFalse(audit_rows[0]["raw_substring_matched"])
        self.assertTrue(audit_rows[0]["unit_substring_matched"])
        self.assertTrue(audit_rows[0]["unit_equivalence_required_for_match"])
        self.assertEqual(
            formal_quote[
                audit_rows[0]["formal_source_start"] : audit_rows[0][
                    "formal_source_end"
                ]
            ],
            audit_rows[0]["formal_source_slice"],
        )
        self.assertEqual(
            audit_rows[0]["punctuation_unit_equivalence_sha256"],
            inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256,
        )

    def test_punctuation_unit_policy_rejects_all_five_collision_regressions(
        self,
    ) -> None:
        policy = inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
        negative_pairs = (
            ("甲……乙同行", "甲。。。乙同行"),
            ("甲……乙同行", "甲．。.乙同行"),
            ("甲……乙同行", "甲。..乙同行"),
            ("甲...乙同行", "甲。。。乙同行"),
            ("甲...乙同行", "甲．。.乙同行"),
        )
        for formal_quote, model_quote_value in negative_pairs:
            with self.subTest(formal=formal_quote, model=model_quote_value):
                raw_batch = sample_batch()
                raw_batch["items"][0]["anchors"][0]["quote"] = formal_quote
                batch = inspector.validate_review_batch(raw_batch)
                with self.assertRaisesRegex(
                    inspector.InspectorError, "标点单元比较后仍不是"
                ):
                    inspector.parse_model_output(
                        model_output(quote=model_quote_value),
                        batch["items"],
                        evidence_quote_policy=policy,
                        minimum_quote_nonspace_chars=6,
                    )

        self.assertTrue(
            inspector.compare_quote_punctuation_units(
                "甲...乙同行", "甲……乙同行"
            )["matched"]
        )

    def test_punctuation_unit_tokenizer_is_longest_first_and_typed(self) -> None:
        tokens = inspector.tokenize_quote_punctuation_units("……...。。。．。.。..")
        keys = [(row["kind"], row["value"]) for row in tokens]
        self.assertEqual(keys[:2], [("punctuation_unit", "PUNCT_ELLIPSIS")] * 2)
        self.assertEqual(
            keys[2:],
            [("punctuation_unit", "PUNCT_PERIOD")] * 9,
        )
        contract = inspector.quote_punctuation_unit_equivalence_contract()
        self.assertEqual(len(contract["groups"]), 12)
        self.assertEqual(
            len({row["unit_id"] for row in contract["groups"]}), 12
        )
        self.assertEqual(
            inspector.sha256_bytes(inspector.stable_json_bytes(contract)),
            inspector.QUOTE_PUNCTUATION_UNIT_EQUIVALENCE_SHA256,
        )

    def test_punctuation_unit_policy_keeps_unmapped_content_and_minimum_strict(
        self,
    ) -> None:
        policy = inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
        raw_batch = sample_batch()
        raw_batch["items"][0]["anchors"][0]["quote"] = "甲说：“把书交给乙。”"
        batch = inspector.validate_review_batch(raw_batch)
        for invalid_quote in (
            '甲说:"把笔交给乙."',
            '甲说: "把书交给乙."',
            '甲说、"把书交给乙."',
        ):
            with self.subTest(quote=invalid_quote), self.assertRaisesRegex(
                inspector.InspectorError, "标点单元比较后仍不是"
            ):
                inspector.parse_model_output(
                    model_output(quote=invalid_quote),
                    batch["items"],
                    evidence_quote_policy=policy,
                    minimum_quote_nonspace_chars=6,
                )
        with self.assertRaisesRegex(inspector.InspectorError, "低于最短"):
            inspector.parse_model_output(
                model_output(quote='乙."'),
                batch["items"],
                evidence_quote_policy=policy,
                minimum_quote_nonspace_chars=6,
            )

    def test_retry07_historical_collision_isolated_from_retry08(self) -> None:
        self.assertEqual(
            inspector.normalize_quote_punctuation("……")[0],
            inspector.normalize_quote_punctuation("。。。")[0],
        )
        with mock.patch.object(
            inspector,
            "normalize_quote_punctuation",
            side_effect=AssertionError("retry08 不应调用 retry07 字符串归一化"),
        ):
            comparison = inspector.compare_quote_punctuation_units(
                "甲...乙同行", "甲……乙同行"
            )
        self.assertTrue(comparison["matched"])

    def test_punctuation_unit_audit_declares_contract_and_rescued_rows(self) -> None:
        policy = inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_PUNCTUATION_UNIT_SUBSTRING
        match = inspector.compare_quote_punctuation_units(
            '甲说:"交给乙."', "甲说：“交给乙。”"
        )
        record = inspector._quote_fill_audit_record(
            item_id="ITEM-1",
            evidence_index=0,
            anchor_id="E0001",
            model_quote='甲说:"交给乙."',
            formal_quote="甲说：“交给乙。”",
            minimum_quote_nonspace_chars=6,
            evidence_quote_policy=policy,
            punctuation_unit_match=match,
        )
        audit = inspector.build_quote_fill_audit(
            batch_id="BATCH-1",
            rows=[record],
            minimum_quote_nonspace_chars=6,
            evidence_quote_policy=policy,
        )
        self.assertEqual(audit["unit_equivalence_rescued_rows"], 1)
        self.assertEqual(audit["unit_mapping_hit_rows"], 1)
        self.assertEqual(audit["raw_substring_rows"], 0)
        self.assertEqual(
            audit["punctuation_unit_equivalence_contract"],
            inspector.quote_punctuation_unit_equivalence_contract(),
        )

    def test_run_inspector_writes_quote_fill_audit_only_for_explicit_policy(
        self,
    ) -> None:
        raw_batch = sample_batch()
        full_quote = "标题前缀\n甲把书交给了乙\n尾注"
        raw_batch["items"][0]["anchors"][0]["quote"] = full_quote
        response = SimpleNamespace(
            content=model_output(quote="甲把书交给了乙"),
            usage={"total_tokens": 123},
            metadata={"finish_reason": "stop"},
        )
        transport = mock.Mock()
        transport.call.return_value = response

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch_path = root / "batch.json"
            run_dir = root / "run"
            batch_path.write_text(
                json.dumps(raw_batch, ensure_ascii=False), encoding="utf-8"
            )
            with (
                mock.patch.object(
                    inspector, "load_contract_bundle", return_value=object()
                ),
                mock.patch.object(
                    inspector.ApiTransport, "from_bundle", return_value=transport
                ),
            ):
                receipt = inspector.run_inspector(
                    batch_path=batch_path,
                    run_dir=run_dir,
                    evidence_quote_policy=inspector.EVIDENCE_QUOTE_POLICY_ANCHOR_ID_AUTHORITATIVE_SUBSTRING,
                    minimum_quote_nonspace_chars=6,
                )

            audit = json.loads(
                (run_dir / "quote_fill_audit.json").read_text(encoding="utf-8")
            )
            routing = json.loads(
                (run_dir / "routing_result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                receipt["outputs"]["quote_fill_audit"], "quote_fill_audit.json"
            )
            self.assertEqual(audit["differing_rows"], 1)
            self.assertEqual(audit["rows"][0]["formal_quote"], full_quote)
            self.assertEqual(
                routing["deepseek_results"][0]["evidence"][0]["quote"], full_quote
            )

    def test_pass_bucket_sampling_is_deterministic_and_has_minimum_one(self) -> None:
        ids = [f"I-{index:02d}" for index in range(20)]
        first = inspector.deterministic_sample(ids, ratio=0.10, seed="same")
        second = inspector.deterministic_sample(reversed(ids), ratio=0.10, seed="same")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(
            len(inspector.deterministic_sample(["ONLY"], ratio=0.10, seed="same")), 1
        )

    def test_feedback_over_two_percent_expands_to_thirty_percent(self) -> None:
        pass_ids = [f"I-{index:02d}" for index in range(20)]
        sampled = inspector.deterministic_sample(pass_ids, ratio=0.10, seed="same")
        routing = {
            "contract_version": inspector.RESULT_CONTRACT,
            "batch_id": "BATCH-1",
            "sample_policy": {"sample_ids": sampled, "seed": "same"},
            "routes": [
                {
                    "item_id": item_id,
                    "route": "strong_review_sample"
                    if item_id in sampled
                    else "provisional_pass_unreviewed",
                }
                for item_id in pass_ids
            ],
        }
        feedback = {
            "contract_version": inspector.FEEDBACK_CONTRACT,
            "batch_id": "BATCH-1",
            "reviews": [
                {
                    "item_id": item_id,
                    "verdict": "misjudged" if index == 0 else "confirmed_pass",
                }
                for index, item_id in enumerate(sampled)
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "result.json"
            feedback_path = root / "feedback.json"
            output_path = root / "receipt.json"
            result_path.write_text(json.dumps(routing), encoding="utf-8")
            feedback_path.write_text(json.dumps(feedback), encoding="utf-8")
            receipt = inspector.apply_feedback(
                result_path=result_path,
                feedback_path=feedback_path,
                output_path=output_path,
            )
        self.assertTrue(receipt["expanded_to_30_percent"])
        self.assertEqual(len(receipt["sample_ids"]), 6)

    def test_rule_registry_has_all_eighteen_program_checks(self) -> None:
        receipt = inspector.audit_rule_registry()
        self.assertEqual(receipt["checked"], 18)
        self.assertEqual(receipt["passed"], 18)


if __name__ == "__main__":
    unittest.main()
