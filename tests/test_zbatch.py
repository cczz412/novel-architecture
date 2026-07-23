from __future__ import annotations

import copy
import importlib.util
import http.client
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("zbatch", ROOT / "tools" / "zbatch.py")
assert SPEC and SPEC.loader
zbatch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zbatch)

CURRENT_SOURCE_PINS = {
    "tools/zbatch_modules/classify_rules.py": "eed588211111f89f5c6968c490686124bf94e7cd09d65aee3f1bc02dd9011104",
    "tools/zbatch_modules/README.md": "d00fa021517984b5279b3886ed2b63541da292d8a1569c4e35dafeb0d72d9480",
}


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "X-Request-Id": "test-request"}

    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class IncompleteResponse(FakeResponse):
    def read(self) -> bytes:
        raise http.client.IncompleteRead(b"partial-response-secret", 100)


class ZBatchTests(unittest.TestCase):
    def setUp(self):
        self.chapter_text = "甲在门外听见钟声，于是推门进入密室。随后机关彻底关闭。"
        chapter_texts = {
            1: self.chapter_text,
            10: "第十章现场留下清晰线索，调查者据此确认危险仍在继续。",
            20: "第二十章当事人完成签约，原先悬而未决的选择终于有了结果。",
        }
        self.chapters = {
            number: {
                "number": number,
                "path": Path(f"ch{number}.txt"),
                "filename": f"{number:04d}_第{number}章.txt",
                "text": text,
                "sha256": "x",
                "chars": len(text),
            }
            for number, text in chapter_texts.items()
        }

    def active_provider(self) -> dict:
        _, provider = zbatch.load_configs(
            ROOT / "config/batches/D-MOD-002_X01_接线切流零调用重放_5章_v1.0.json"
        )
        return provider

    def valid_record(self) -> dict:
        return {
            "id": "A-C0001-01",
            "type": "A",
            "story_line": "密室线",
            "delta": "甲从门外变为进入密室",
            "direct_cause": "听见钟声后推门",
            "future_use": "机关关闭限制退路",
            "status": "开",
            "type_state": "",
            "assertion": "明",
            "related_ids": [],
            "anchors": [{"chapter": 1, "quote": "甲在门外听见钟声，于是推门进入密室"}],
        }

    def ledger_record(self, record_id: str, chapter: int) -> dict:
        text = self.chapters[chapter]["text"]
        return {
            "id": record_id,
            "status": "开",
            "anchors": [{"chapter": chapter, "quote": text[:22]}],
        }

    def valid_answer_fixture(self) -> tuple[list[dict], dict[str, dict]]:
        ledger = {
            "A-0001": self.ledger_record("A-0001", 1),
            "A-0010": self.ledger_record("A-0010", 10),
            "A-0020": self.ledger_record("A-0020", 20),
        }

        def answered(question_id: str, question_type: str, target, record_ids: list[str]) -> dict:
            anchors = [anchor for record_id in record_ids for anchor in ledger[record_id]["anchors"]]
            return {
                "question_id": question_id,
                "question_type": question_type,
                "target_chapter": target,
                "question": f"{question_id} 的问题",
                "status": "answered",
                "not_applicable_reason": "",
                "answer_markdown": "有结构记录支持。",
                "record_ids": record_ids,
                "anchors": anchors,
            }

        unavailable = {
            "status": "not_applicable",
            "not_applicable_reason": "当前20章没有对应样本",
            "answer_markdown": "无样本，不作伪答。",
            "record_ids": [],
            "anchors": [],
        }
        items = [
            answered("backtrace-ch0010", "回指", 10, ["A-0010"]),
            answered("backtrace-ch0020", "回指", 20, ["A-0020"]),
            {
                "question_id": "cross-line",
                "question_type": "转线",
                "target_chapter": None,
                "question": "是否有真实转线",
                **unavailable,
            },
            {
                "question_id": "compression",
                "question_type": "伸缩",
                "target_chapter": None,
                "question": "是否有可折叠闭环",
                **unavailable,
            },
            {
                **answered("gradient", "梯度", 20, ["A-0020", "A-0010"]),
                "current_chapter": 20,
                "gradient_points": [
                    {"bucket": "0-1", "status": "sample", "chapter": 20, "distance": 0, "record_ids": ["A-0020"]},
                    {"bucket": "2-5", "status": "no_sample", "chapter": None, "distance": None, "record_ids": []},
                    {"bucket": "6-20", "status": "sample", "chapter": 10, "distance": 10, "record_ids": ["A-0010"]},
                    {"bucket": "21-50", "status": "no_sample", "chapter": None, "distance": None, "record_ids": []},
                    {"bucket": "50+", "status": "no_sample", "chapter": None, "distance": None, "record_ids": []},
                ],
            },
        ]
        return items, ledger

    def test_parse_json_content_accepts_one_fence(self):
        self.assertEqual(zbatch.parse_json_content("```json\n{\"ok\": true}\n```"), {"ok": True})

    def test_parse_json_content_does_not_repair(self):
        with self.assertRaises(zbatch.ZBatchError):
            zbatch.parse_json_content("{bad json}")

    def test_anchor_exact_hit_passes(self):
        reasons, checks = zbatch.validate_anchors(
            self.valid_record()["anchors"], self.chapters, expected_chapter=1
        )
        self.assertEqual(reasons, [])
        self.assertTrue(checks[0]["valid"])

    def test_anchor_mismatch_is_rejected(self):
        anchors = [{"chapter": 1, "quote": "甲在门外听见钟声，于是凭空飞走了"}]
        reasons, _ = zbatch.validate_anchors(anchors, self.chapters, expected_chapter=1)
        self.assertIn("短引不命中", reasons)

    def test_anchor_length_gate_is_rejected(self):
        anchors = [{"chapter": 1, "quote": "钟声"}]
        reasons, _ = zbatch.validate_anchors(anchors, self.chapters, expected_chapter=1)
        self.assertIn("短引长度越界", reasons)

    def test_A_record_shape_passes(self):
        reasons, _ = zbatch.validate_record(self.valid_record(), self.chapters, expected_chapter=1)
        self.assertEqual(reasons, [])

    def test_related_ids_reject_evidence_ids(self):
        record = self.valid_record()
        record["related_ids"] = ["E0149"]
        reasons, _ = zbatch.validate_record(record, self.chapters, expected_chapter=1)
        self.assertIn("关联ID格式非法", reasons)

    def test_candidate_related_ids_must_resolve_in_same_chapter(self):
        record = self.valid_record()
        record["related_ids"] = ["B-C0001-01"]
        data = {
            "schema_version": "z-candidate-v1",
            "chapter": 1,
            "decision_markers": [],
            "records": [record],
            "coverage_audit": {
                "A": {"status": "emitted", "record_ids": [record["id"]], "reason": "发现明确的状态变化并已输出候选"},
                "B": {"status": "none", "record_ids": [], "reason": "没有待执行的条件动作触发器"},
                "C": {"status": "none", "record_ids": [], "reason": "没有独立的长期读者承诺"},
                "D": {"status": "none", "record_ids": [], "reason": "没有可重复适用的世界规则"},
            },
        }
        self.assertIn("关联ID不存在于本章候选", zbatch.validate_candidate_envelope(data, 1))

    def test_cross_type_anchor_overlap_is_diagnostic(self):
        first = self.valid_record()
        first["anchors"][0]["anchor_id"] = "E0001"
        second = copy.deepcopy(first)
        second.update({
            "id": "C-C0001-01",
            "type": "C",
            "reader_expectation": "门后是谁",
            "payoff_test": "后文揭示门后人物身份",
        })
        result = zbatch.cross_type_anchor_overlap([first, second])
        self.assertEqual(result["shared_anchor_count"], 1)
        self.assertEqual(result["cross_type_pair_count"], 1)
        self.assertIn("不自动判废", result["role"])

    def test_evidence_catalog_is_exact_and_within_length_gate(self):
        catalog = zbatch.build_evidence_catalog(1, self.chapter_text)
        self.assertTrue(catalog)
        self.assertEqual(zbatch.evidence_catalog_coverage(self.chapter_text, catalog), 1.0)
        for entry in catalog:
            self.assertIn(entry["quote"], self.chapter_text)
            self.assertGreaterEqual(zbatch.nonspace_chars(entry["quote"]), 10)
            self.assertLessEqual(zbatch.nonspace_chars(entry["quote"]), 25)

    def test_catalog_id_and_quote_must_match(self):
        record = self.valid_record()
        record["anchors"][0]["anchor_id"] = "E0001"
        reasons, _ = zbatch.validate_record(
            record,
            self.chapters,
            expected_chapter=1,
            evidence_catalog={"E0001": "另一段完全不同但长度合格的原文短引"},
        )
        self.assertIn("证据目录短引不一致", reasons)

    def test_prompt_chapter_examples_are_dynamic(self):
        template = (ROOT / "work" / "zbatch_prompts" / "extract_v1.3.md").read_text(encoding="utf-8")
        rendered = zbatch.replace_prompt(template, {
            "CHAPTER_NUMBER": "2",
            "CHAPTER_PADDED": "0002",
            "CHAPTER_FILENAME": "0002.txt",
            "CHAPTER_TEXT": "正文",
            "EVIDENCE_CATALOG_JSON": "[]",
        })
        self.assertIn('"chapter": 2', rendered)
        self.assertIn('A-C0002-01', rendered)
        self.assertNotIn('A-C0001-01', rendered)

    def test_epistemic_guard_candidate_is_exactly_one_added_rule(self):
        baseline = (ROOT / "work" / "zbatch_prompts" / "extract_v1.3.md").read_text(encoding="utf-8")
        candidate = (
            ROOT / "work" / "zbatch_prompts" / "candidates" / "extract_epistemic_guard_v1.4.md"
        ).read_text(encoding="utf-8")
        guard = (
            "- 证据原文用“也许”“据说”或“猜测”表达某一命题时，该命题不得标 `assertion`＝“明”；"
            "只能标“推”或“存疑”，且不能把“有人说过这句话”偷换成“话中内容已经明示为真”。\n"
        )
        self.assertEqual(candidate.count(guard), 1)
        self.assertEqual(candidate.replace(guard, ""), baseline)

    def test_attention_candidate_orders_text_catalog_contract_and_records_first(self):
        template = (
            ROOT / "work" / "zbatch_prompts" / "candidates" / "extract_attention_v1.5.md"
        ).read_text(encoding="utf-8")
        rendered = zbatch.replace_prompt(template, {
            "CHAPTER_NUMBER": "10",
            "CHAPTER_PADDED": "0010",
            "CHAPTER_FILENAME": "0010_第10章.txt",
            "CHAPTER_TEXT": "第十章完整正文",
            "EVIDENCE_CATALOG_JSON": '[{"anchor_id":"E0001","quote":"第十章完整正文证据短引"}]',
        })
        self.assertLess(rendered.index("## 5. 当前章全文"), rendered.index("## 6. 同章冻结证据目录"))
        self.assertLess(rendered.index("## 6. 同章冻结证据目录"), rendered.index("## 7. JSON 输出契约"))
        contract = rendered.split("## 7. JSON 输出契约", 1)[1].split("## 8. 临交稿提醒", 1)[0]
        self.assertLess(contract.index('"records": []'), contract.index('"coverage_audit"'))
        self.assertIn("第十章完整正文", rendered)
        self.assertNotIn("警方正式介入并限制当事人离开", rendered)
        self.assertIn("输出前按原始事实去重", rendered)

    def test_fulltext_only_candidate_adds_text_without_attention_bundle(self):
        template = (
            ROOT / "work" / "zbatch_prompts" / "candidates" / "extract_fulltext_only_v1.4.md"
        ).read_text(encoding="utf-8")
        rendered = zbatch.replace_prompt(template, {
            "CHAPTER_NUMBER": "10",
            "CHAPTER_PADDED": "0010",
            "CHAPTER_FILENAME": "0010_第10章.txt",
            "CHAPTER_TEXT": "第十章连续全文",
            "EVIDENCE_CATALOG_JSON": '[{"anchor_id":"E0001","quote":"第十章连续全文证据短引"}]',
        })
        self.assertLess(
            rendered.index("当前章全文（只帮助理解跨句关系"),
            rendered.rindex("冻结证据目录（按原文顺序覆盖本章全文）："),
        )
        self.assertIn("第十章连续全文", rendered)
        self.assertNotIn("三个微型边界例", rendered)
        self.assertNotIn("临交稿提醒", rendered)
        self.assertNotIn("输出前按原始事实去重", rendered)

    def test_candidate_coverage_audit_matches_emitted_records(self):
        data = {
            "schema_version": "z-candidate-v1",
            "chapter": 1,
            "decision_markers": [],
            "records": [self.valid_record()],
            "coverage_audit": {
                "A": {"status": "emitted", "record_ids": ["A-C0001-01"], "reason": "发现人物进入密室的明确状态变化"},
                "B": {"status": "none", "record_ids": [], "reason": "没有公开以后到达条件就执行的动作"},
                "C": {"status": "none", "record_ids": [], "reason": "没有向读者公开吊起长期等待事项"},
                "D": {"status": "none", "record_ids": [], "reason": "没有可重复适用的如果就会规则"},
            },
        }
        self.assertEqual(zbatch.validate_candidate_envelope(data, 1), [])

    def test_empty_chapter_requires_four_type_attestation(self):
        data = {
            "schema_version": "z-candidate-v1",
            "chapter": 1,
            "decision_markers": ["空章自证"],
            "records": [],
            "coverage_audit": {
                kind: {"status": "none", "record_ids": [], "reason": f"已检查{kind}类定义但本章证据不满足条件"}
                for kind in "ABCD"
            },
        }
        self.assertEqual(zbatch.validate_candidate_envelope(data, 1), [])
        del data["coverage_audit"]["D"]
        self.assertIn("覆盖清点缺类型", zbatch.validate_candidate_envelope(data, 1))

    def test_anchor_id_materialization_is_deterministic(self):
        catalog = zbatch.build_evidence_catalog(1, self.chapter_text)
        raw = {
            "records": [{
                "id": "A-C0001-01",
                "anchors": [{"anchor_id": catalog[0]["anchor_id"], "quote": "模型不负责这段"}],
            }]
        }
        parsed = zbatch.materialize_anchor_ids(raw, catalog, 1)
        anchor = parsed["records"][0]["anchors"][0]
        self.assertEqual(anchor, {
            "chapter": 1,
            "anchor_id": catalog[0]["anchor_id"],
            "quote": catalog[0]["quote"],
        })
        self.assertEqual(raw["records"][0]["anchors"][0]["quote"], "模型不负责这段")

    def test_source_record_anchor_materialization_is_deterministic(self):
        source = self.valid_record()
        items = [{"id": "A-0001", "source_record_ids": [source["id"]]}]
        parsed = zbatch.materialize_anchors_from_sources(
            items, {source["id"]: source}, source_field="source_record_ids"
        )
        self.assertEqual(parsed[0]["anchors"], source["anchors"])
        self.assertEqual(parsed[0]["_anchor_materialization"]["unresolved_source_ids"], [])

    def test_not_applicable_is_a_valid_explicit_answer_state(self):
        items, ledger = self.valid_answer_fixture()
        rows, metrics = zbatch.validate_answer_items(items, self.chapters, ledger, 20)
        self.assertTrue(all(row["valid"] for row in rows))
        self.assertTrue(metrics["four_type_pass"])
        self.assertTrue(metrics["five_question_pass"])

    def test_backtrace_cannot_hide_behind_not_applicable(self):
        item = {
            "question_id": "backtrace-ch0010",
            "question_type": "回指",
            "target_chapter": 10,
            "question": "第10章回指",
            "status": "not_applicable",
            "not_applicable_reason": "不想回答",
            "answer_markdown": "无样本",
            "record_ids": [],
            "anchors": [],
        }
        rows, _ = zbatch.validate_answer_items([item], self.chapters, {}, 20)
        self.assertIn("该题型不允许无样本", rows[0]["reasons"])

    def test_backtrace_target_chapter_must_have_matching_anchor(self):
        items, ledger = self.valid_answer_fixture()
        items[0]["record_ids"] = ["A-0001"]
        items[0]["anchors"] = ledger["A-0001"]["anchors"]
        rows, metrics = zbatch.validate_answer_items(items, self.chapters, ledger, 20)
        self.assertIn("回指答案没有目标章原锚", rows[0]["reasons"])
        self.assertFalse(metrics["five_question_pass"])

    def test_missing_chapter20_backtrace_fails_question_set(self):
        items, ledger = self.valid_answer_fixture()
        items = [item for item in items if item["question_id"] != "backtrace-ch0020"]
        _, metrics = zbatch.validate_answer_items(items, self.chapters, ledger, 20)
        self.assertIn("backtrace-ch0020", metrics["question_ids_missing"])
        self.assertFalse(metrics["five_question_pass"])

    def test_gradient_distance_and_bucket_are_recomputed(self):
        items, ledger = self.valid_answer_fixture()
        gradient = next(item for item in items if item["question_id"] == "gradient")
        point = next(point for point in gradient["gradient_points"] if point["bucket"] == "6-20")
        point["distance"] = 4
        rows, metrics = zbatch.validate_answer_items(items, self.chapters, ledger, 20)
        gradient_row = next(row for row in rows if row["item"].get("question_id") == "gradient")
        self.assertIn("梯度步距计算错误", gradient_row["reasons"])
        self.assertFalse(metrics["five_question_pass"])

    def test_crossline_and_compression_must_match_fold_view(self):
        items, ledger = self.valid_answer_fixture()
        cross_line = next(item for item in items if item["question_id"] == "cross-line")
        cross_line.update({
            "status": "answered",
            "not_applicable_reason": "",
            "answer_markdown": "第20章记录是跨线出口。",
            "record_ids": ["A-0020"],
            "anchors": ledger["A-0020"]["anchors"],
        })
        compression = next(item for item in items if item["question_id"] == "compression")
        compression.update({
            "status": "answered",
            "not_applicable_reason": "",
            "macro_id": "M-001",
            "answer_markdown": "两条记录折成一个宏。",
            "record_ids": ["A-0001", "A-0010"],
            "anchors": ledger["A-0001"]["anchors"] + ledger["A-0010"]["anchors"],
        })
        fold = {
            "cross_line_exits": ["A-0020"],
            "macros": [{"id": "M-001", "source_record_ids": ["A-0001", "A-0010"]}],
        }
        rows, metrics = zbatch.validate_answer_items(items, self.chapters, ledger, 20, fold)
        self.assertTrue(metrics["five_question_pass"])
        cross_line["record_ids"] = ["A-0010"]
        cross_line["anchors"] = ledger["A-0010"]["anchors"]
        rows, metrics = zbatch.validate_answer_items(items, self.chapters, ledger, 20, fold)
        cross_row = next(row for row in rows if row["item"].get("question_id") == "cross-line")
        self.assertIn("转线答案未引用折叠视图跨线出口", cross_row["reasons"])
        self.assertFalse(metrics["five_question_pass"])

    def test_non_comparable_item_cannot_be_equal(self):
        answer_items, _ = self.valid_answer_fixture()
        compare_items = []
        for index, answer in enumerate(answer_items, 1):
            compare_items.append({
                "comparison_id": f"CMP-{index:03d}",
                "ours_question_id": answer["question_id"],
                "comparability": "different_scope" if index == 1 else "insufficient_evidence",
                "label": "等价" if index == 1 else "待裁",
                "reason": "范围不同" if index == 1 else "仍需回原文",
                "ours_record_ids": answer.get("record_ids") or [],
                "silver_section": "银标测试小节",
                "evidence_status": "仍待原文裁",
            })
        rows, metrics = zbatch.validate_compare_items(compare_items, answer_items)
        self.assertIn("非同题对撞只能待裁", rows[0]["reasons"])
        self.assertFalse(metrics["comparison_pass"])

    def test_all_non_comparable_items_can_cleanly_remain_pending(self):
        answer_items, _ = self.valid_answer_fixture()
        compare_items = [
            {
                "comparison_id": f"CMP-{index:03d}",
                "ours_question_id": answer["question_id"],
                "comparability": "different_scope",
                "label": "待裁",
                "reason": "银标范围与本地20章范围不同",
                "ours_record_ids": answer.get("record_ids") or [],
                "silver_section": "银标测试小节",
                "evidence_status": "仍待原文裁",
            }
            for index, answer in enumerate(answer_items, 1)
        ]
        rows, metrics = zbatch.validate_compare_items(compare_items, answer_items)
        self.assertTrue(all(row["valid"] for row in rows))
        self.assertTrue(metrics["comparison_pass"])
        self.assertEqual(metrics["labels"]["待裁"], 5)

    def test_fold_macro_rejects_reversed_causal_timeline(self):
        ledger = {
            "A-0001": self.ledger_record("A-0001", 1),
            "A-0010": self.ledger_record("A-0010", 10),
            "A-0020": self.ledger_record("A-0020", 20),
        }
        macro = {
            "id": "M-001",
            "summary": "根因→转折→结果",
            "status": "收",
            "source_record_ids": ["A-0001", "A-0020", "A-0010"],
            "roles": {
                "root_cause_id": "A-0001",
                "turning_point_ids": ["A-0020"],
                "result_id": "A-0010",
                "open_exit_ids": [],
            },
            "anchors": [anchor for record in ledger.values() for anchor in record["anchors"]],
        }
        reasons, _ = zbatch.validate_macro(macro, self.chapters, ledger)
        self.assertIn("宏节点因果时序倒置", reasons)

    def test_invalid_downstream_results_trip_hard_gates(self):
        with self.assertRaises(zbatch.ZBatchError):
            zbatch.enforce_fold_gate({"macros_invalid": 1})
        with self.assertRaises(zbatch.ZBatchError):
            zbatch.enforce_answer_gate({"four_type_pass": False})
        with self.assertRaises(zbatch.ZBatchError):
            zbatch.enforce_compare_gate({"comparison_pass": False})

    def test_derived_record_requires_source_ids(self):
        record = self.valid_record()
        reasons, _ = zbatch.validate_record(
            record,
            self.chapters,
            require_sources=True,
            allowed_source_ids={"A-C0001-01"},
        )
        self.assertIn("缺来源候选ID", reasons)

    def test_current_source_smoke_preflight_is_zero_call_and_passes(self):
        frozen = zbatch.read_json(
            ROOT / "config/batches/Z00s_X01_20章分类正门兼容_20章_v1.0.json"
        )
        frozen["runner_sha256"] = zbatch.sha256_file(ROOT / "tools/zbatch.py")
        frozen["pinned_sha256"]["tools/zbatch_modules/__init__.py"] = zbatch.sha256_file(
            ROOT / "tools/zbatch_modules/__init__.py"
        )
        for relative, expected_sha in CURRENT_SOURCE_PINS.items():
            self.assertEqual(zbatch.sha256_file(ROOT / relative), expected_sha)
            frozen["pinned_sha256"][relative] = expected_sha
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            config_path = Path(temp_dir) / "current_source_smoke.json"
            zbatch.write_json(config_path, frozen)
            result = zbatch.preflight(config_path)
        self.assertEqual(result["preflight"], "pass")
        self.assertEqual(result["model_calls"], 0)

    def test_api_key_never_enters_request_file(self):
        secret = "super-secret-test-key"
        provider = self.active_provider()
        batch = {"max_calls": 1}
        model_content = json.dumps({"ok": True}, ensure_ascii=False)
        response = {
            "model": "deepseek-v4-flash",
            "choices": [{"message": {"content": model_content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        temp_parent = ROOT / "TEMP"
        with tempfile.TemporaryDirectory(dir=temp_parent) as temp_dir:
            ctx = zbatch.RunContext(batch, provider, Path(temp_dir))
            with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": secret}, clear=False):
                ctx.transport.opener = mock.Mock(return_value=FakeResponse(response))
                with self.subTest("modular_transport"):
                    self.assertEqual(
                        ctx.call_json(
                            stage="neutral_extract",
                            case_id="unit",
                            messages=[{"role": "user", "content": "test"}],
                        ),
                        {"ok": True},
                    )
            request_path = Path(temp_dir) / "requests" / "neutral_extract" / "unit_request.json"
            request_text = request_path.read_text(encoding="utf-8")
            self.assertNotIn(secret, request_text)
            self.assertNotIn('"Authorization"', request_text)

    def test_http_error_body_is_hashed_not_persisted(self):
        secret = "server-echoed-secret"
        provider = self.active_provider()
        error = urllib.error.HTTPError(
            "https://token.sensenova.cn/v1/chat/completions",
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(secret.encode("utf-8")),
        )
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            ctx = zbatch.RunContext({"max_calls": 1}, provider, Path(temp_dir))
            with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False):
                ctx.transport.opener = mock.Mock(side_effect=error)
                with self.assertRaises(zbatch.ZBatchError):
                    ctx.call_json(
                        stage="neutral_extract",
                        case_id="error",
                        messages=[{"role": "user", "content": "test"}],
                    )
            error_text = next((Path(temp_dir) / "errors").glob("*.txt")).read_text(encoding="utf-8")
            self.assertNotIn(secret, error_text)
            self.assertIn("error_body_not_persisted=security_policy", error_text)

    def test_incomplete_chunked_response_retries_without_persisting_partial_body(self):
        provider = self.active_provider()
        response = {
            "model": "deepseek-v4-flash",
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 2},
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            ctx = zbatch.RunContext({"max_calls": 2}, provider, Path(temp_dir))
            with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False):
                ctx.transport.opener = mock.Mock(
                    side_effect=[IncompleteResponse({}), FakeResponse(response)]
                )
                ctx.transport.sleeper = lambda _: None
                self.assertEqual(
                    ctx.call_json(
                        stage="thin",
                        case_id="retry",
                        messages=[{"role": "user", "content": "test"}],
                    ),
                    {"ok": True},
                )
            self.assertEqual(ctx.calls_made, 2)
            error_text = next((Path(temp_dir) / "errors").glob("*.txt")).read_text(encoding="utf-8")
            self.assertNotIn("partial-response-secret", error_text)
            self.assertIn("partial_body_not_persisted=security_and_integrity_policy", error_text)

    def test_actual_failed_run_can_export_completed_verified_stage(self):
        batch, _ = zbatch.load_configs(
            ROOT / "config" / "batches" / "Z00d_X01_20章全链冒烟_v1.2.json"
        )
        result = zbatch.verify_verified_run_import(
            "Z00d_X01_20章全链冒烟_v1.2_20260717", batch
        )
        self.assertEqual(result["chapters"], 20)
        self.assertEqual(result["valid_records"], 43)

    def test_actual_failed_fold_run_can_export_completed_thin_stage(self):
        batch, _ = zbatch.load_configs(
            ROOT / "config" / "batches" / "Z00f_X01_20章语义闸续测_v1.3.json"
        )
        result = zbatch.verify_thin_run_import(
            "Z00f_X01_20章语义闸续测_v1.3_20260717", batch
        )
        self.assertEqual(result["thin_records"], 40)
        self.assertIn("thin", result["completed_stages"])

    def test_resume_receipt_detects_tampering(self):
        provider = self.active_provider()
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            ctx = zbatch.RunContext({"max_calls": 1}, provider, run_dir)
            request_path, raw_path, meta_path = zbatch.api_artifact_paths(ctx, "neutral_extract", "unit")
            zbatch.write_json(request_path, {"request": True})
            zbatch.write_json(raw_path, {"response": True})
            zbatch.write_json(meta_path, {"meta": True})
            output = run_dir / "parsed" / "unit.json"
            zbatch.write_api_artifact(
                ctx,
                stage="neutral_extract",
                case_id="unit",
                output_path=output,
                data={"ok": True},
                input_sha256="input-sha",
                prompt_sha256="prompt-sha",
            )
            self.assertEqual(
                zbatch.resume_api_artifact(
                    ctx,
                    stage="neutral_extract",
                    case_id="unit",
                    output_path=output,
                    input_sha256="input-sha",
                    prompt_sha256="prompt-sha",
                ),
                {"ok": True},
            )
            output.write_text('{"ok": false}\n', encoding="utf-8")
            with self.assertRaises(zbatch.ZBatchError):
                zbatch.resume_api_artifact(
                    ctx,
                    stage="neutral_extract",
                    case_id="unit",
                    output_path=output,
                    input_sha256="input-sha",
                    prompt_sha256="prompt-sha",
                )

    def test_stage_override_cannot_escape_batch_whitelist(self):
        batch = {"stages": ["extract", "verify", "report", "pack"]}
        with self.assertRaises(zbatch.ZBatchError):
            zbatch.resolve_stages(batch, "thin")
        self.assertEqual(zbatch.resolve_stages(batch, "extract,verify"), ["extract", "verify"])

    def test_provenance_manifest_cannot_drop_a_row(self):
        batch, provider = zbatch.load_configs(
            ROOT / "config" / "batches" / "Z00e_X01_20章下游续测_v1.2.json"
        )
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            zbatch.write_json(run_dir / "config_snapshot.json", {"batch": batch, "provider": provider})
            zbatch.create_provenance_snapshot(run_dir, batch, provider)
            self.assertEqual(zbatch.verify_provenance_snapshot(run_dir)["status"], "pass")
            manifest_path = run_dir / "provenance" / "manifest.json"
            manifest = zbatch.read_json(manifest_path)
            manifest["files"].pop()
            zbatch.write_json(manifest_path, manifest)
            with self.assertRaises(zbatch.ZBatchError):
                zbatch.verify_provenance_snapshot(run_dir)


if __name__ == "__main__":
    unittest.main()
