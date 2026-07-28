from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("z59_entity_supply_pilot", ROOT / "tools/z59_entity_supply_pilot.py")
assert SPEC and SPEC.loader
Z59 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = Z59
SPEC.loader.exec_module(Z59)


class Z59EntitySupplyTests(unittest.TestCase):
    def test_strip_exported_header(self) -> None:
        raw = "第3章 第3章 梅丽莎\n\n　　第3章梅丽莎\n　　周明瑞见到梅丽莎。\n"
        self.assertEqual(Z59.strip_exported_header(raw, 3), "　　周明瑞见到梅丽莎。\n")

    def test_global_longest_span_wins(self) -> None:
        entities = [
            {"entity_id": "LOC-1", "surfaces": [{"text": "廷根"}]},
            {"entity_id": "LOC-2", "surfaces": [{"text": "廷根大学"}]},
        ]
        matches = Z59.raw_matches_for_chapter(3, "去廷根大学，再回廷根。", entities)
        self.assertEqual([(row.entity_id, row.surface) for row in matches], [("LOC-2", "廷根大学"), ("LOC-1", "廷根")])

    def test_scope_blocks_ambiguous_title(self) -> None:
        entities = [{"entity_id": "PER-1", "surfaces": [{"text": "正义", "chapters": [7]}]}]
        self.assertEqual(Z59.raw_matches_for_chapter(6, "他追求正义。", entities), [])
        self.assertEqual(len(Z59.raw_matches_for_chapter(7, "代号正义。", entities)), 1)

    def test_range_format(self) -> None:
        self.assertEqual(Z59.compress_ranges(list(range(1, 21))), "1～20全出现")
        self.assertEqual(Z59.compress_ranges([3, 4, 5, 13, 19, 20]), "3～5、13、19～20")

    def test_entity_message_is_single_insert(self) -> None:
        base = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        candidate = Z59.build_entity_messages(base, "table")
        self.assertEqual(candidate, [base[0], {"role": "system", "content": "table"}, base[1]])

    def test_a_candidate_request_changes_only_messages(self) -> None:
        bundle = Z59.load_neutral_bundle()
        contract = bundle.stage("neutral_extract")
        model = str(bundle.route["model"])
        base_messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        candidate_messages = Z59.build_entity_messages(base_messages, "entity table")
        base_body = Z59.api_transport.build_request_body(model=model, messages=base_messages, contract=contract)
        candidate_body = Z59.api_transport.build_request_body(model=model, messages=candidate_messages, contract=contract)
        changed = sorted(field for field in set(base_body) | set(candidate_body) if base_body.get(field) != candidate_body.get(field))
        self.assertEqual(changed, ["messages"])

    def test_outline_contract_rejects_unknown_event(self) -> None:
        data = {
            "schema_version": Z59.OUTLINE_SCHEMA,
            "chapter": 3,
            "outline_items": [
                {
                    "item_id": "OL-C0003-01",
                    "source_event_ids": ["EV-C0003-99"],
                    "logic_sentence": "克莱恩完成了一项动作。",
                    "state_change": "本条无独立状态转变",
                }
            ],
        }
        with self.assertRaisesRegex(Exception, "目录外事件ID"):
            Z59.validate_outline(data, 3, {"EV-C0003-01"})

    def test_outline_contract_accepts_valid(self) -> None:
        data = {
            "schema_version": Z59.OUTLINE_SCHEMA,
            "chapter": 3,
            "outline_items": [
                {
                    "item_id": "OL-C0003-01",
                    "source_event_ids": ["EV-C0003-01"],
                    "logic_sentence": "克莱恩完成了一项可核对动作。",
                    "state_change": "本条无独立状态转变",
                }
            ],
        }
        self.assertEqual(Z59.validate_outline(data, 3, {"EV-C0003-01"})["status"], "pass")

    def test_b_candidate_request_changes_only_messages(self) -> None:
        bundle = Z59.load_neutral_bundle()
        contract = Z59.outline_contract_from_neutral()
        model = str(bundle.route["model"])
        base_messages = Z59.outline_messages("同一事件池", None)
        entity_messages = Z59.outline_messages("同一事件池", "件⓪v1.1实体表")
        base_body = Z59.api_transport.build_request_body(model=model, messages=base_messages, contract=contract)
        entity_body = Z59.api_transport.build_request_body(model=model, messages=entity_messages, contract=contract)
        changed = sorted(field for field in set(base_body) | set(entity_body) if base_body.get(field) != entity_body.get(field))
        self.assertEqual(changed, ["messages"])

    def test_b_preflight_freezes_source_pool_supply_and_single_variable(self) -> None:
        supply_dir = ROOT / "runs/Z59_0_X01_模拟实体供料_20章_v1.1_20260719"
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "z60-b-preflight"
            preflight = Z59.prepare_b(supply_dir, run_dir)
            self.assertEqual(
                Z59.sha256_file(run_dir / preflight["sampling_contract"]["pinned_path"]),
                preflight["sampling_contract"]["sha256"],
            )
            self.assertEqual(
                Z59.sha256_file(run_dir / preflight["provider_config"]["pinned_path"]),
                preflight["provider_config"]["sha256"],
            )
        self.assertEqual(preflight["model_api_calls"], 0)
        self.assertEqual(preflight["source_pool"]["chapter_count"], 20)
        self.assertEqual(preflight["source_pool"]["event_total"], 233)
        self.assertEqual(preflight["source_event_total"], 39)
        self.assertEqual(preflight["entity_supply_v1_1"]["mechanical_verification_status"], "pass")
        self.assertEqual(preflight["transport_budget"]["logical_cases"], 10)
        self.assertEqual(preflight["transport_budget"]["network_retry_slack"], 3)
        self.assertEqual(preflight["transport_budget"]["max_network_attempts"], 13)
        self.assertEqual(preflight["sampling_contract"]["sha256"], Z59.sha256_file(Z59.SAMPLING_CONTRACT))
        self.assertEqual(preflight["provider_config"]["sha256"], Z59.sha256_file(Z59.PROVIDER_CONFIG))
        self.assertTrue(all(row["request_body_changed_fields"] == ["messages"] for row in preflight["inputs"]))
        self.assertTrue(all(row["message_position_audit"][1]["entity_index"] == 1 for row in preflight["inputs"]))

    def test_b_semantic_rubric_is_frozen_before_calls_and_forbids_machine_shadow_claims(self) -> None:
        rubric = json.loads(Z59.B_SEMANTIC_RUBRIC_PATH.read_text(encoding="utf-8"))
        self.assertTrue(rubric["frozen_before_model_calls"])
        self.assertEqual(rubric["shadow_score_policy"], "禁止直接引用机器影子分；如需影子类判断，逐条语义复核后另列")
        self.assertIn("unsupported_by_source_events", rubric["hard_stop_triggers"])

    def test_b_semantic_audit_covers_every_item_and_hard_stops(self) -> None:
        run_dir = ROOT / "runs/Z60_B_X01_实体供料大纲逻辑双臂_五靶章_v1.1_20260720"
        review = json.loads((run_dir / "analysis/双臂语义复核.json").read_text(encoding="utf-8"))
        hard_stop = json.loads((run_dir / "analysis/语义硬停单.json").read_text(encoding="utf-8"))
        rows = review["rows"]
        identities = [(row["arm"], row["chapter"], row["item_id"]) for row in rows]
        self.assertEqual(len(rows), 47)
        self.assertEqual(len(identities), len(set(identities)))
        self.assertFalse(review["shadow_score_used"])
        self.assertEqual(review["summary"]["base"]["source_event_id_coverage"]["used"], 39)
        self.assertEqual(review["summary"]["entity"]["source_event_id_coverage"]["used"], 39)
        self.assertEqual(review["summary"]["base"]["semantically_supported_item_rate"], {"full": 21, "total": 23})
        self.assertEqual(review["summary"]["entity"]["semantically_supported_item_rate"], {"full": 19, "total": 24})
        self.assertEqual(review["summary"]["base"]["supported_or_explicit_none_state_rate"], {"supported": 18, "total": 23})
        self.assertEqual(review["summary"]["entity"]["supported_or_explicit_none_state_rate"], {"supported": 16, "total": 24})
        self.assertEqual(review["summary"]["base"]["verdict_counts"], {"new_failure": 7, "pass": 16})
        self.assertEqual(review["summary"]["entity"]["verdict_counts"], {"new_failure": 12, "pass": 12})
        self.assertEqual(hard_stop["status"], "hard_stop_no_repair_no_rerun")
        self.assertEqual(hard_stop["failed_item_count"], 19)
        self.assertEqual(hard_stop["failure_claim_count"], 20)

    def test_b_semantic_diff_cost_and_transport_are_complete(self) -> None:
        run_dir = ROOT / "runs/Z60_B_X01_实体供料大纲逻辑双臂_五靶章_v1.1_20260720"
        diff = json.loads((run_dir / "analysis/双臂信息变化语义账.json").read_text(encoding="utf-8"))
        cost = json.loads((run_dir / "analysis/分臂成本账.json").read_text(encoding="utf-8"))
        transport = json.loads((run_dir / "analysis/运输层实跑观察.json").read_text(encoding="utf-8"))
        self.assertTrue(diff["semantic_review_completed"])
        self.assertFalse(diff["shadow_score_used"])
        self.assertEqual(diff["group_count"], 22)
        self.assertEqual(sum(diff["category_counts"].values()), 22)
        self.assertEqual(cost["arms"]["base"]["totals"]["total_tokens"], 20098)
        self.assertEqual(cost["arms"]["entity"]["totals"]["total_tokens"], 19582)
        self.assertEqual(cost["combined"]["total_tokens"], 39680)
        self.assertEqual(transport["logical_samples"], 10)
        self.assertEqual(transport["successful_model_calls"], 10)
        self.assertEqual(transport["network_attempts"], 11)
        self.assertEqual(transport["retry_count"], 1)

    def test_supply_build_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "left"
            right = Path(temp) / "right"
            Z59.build_supply(left)
            Z59.build_supply(right)
            inventory = json.loads((left / "entity_inventory.json").read_text(encoding="utf-8"))["entities"]
            by_id = {row["entity_id"]: row for row in inventory}
            self.assertFalse(by_id["PER-012"]["accepted"])
            self.assertFalse(by_id["PER-015"]["accepted"])
            for volatile in ("source_manifest.json",):
                (left / volatile).unlink()
                (right / volatile).unlink()
            self.assertEqual(Z59.tree_fingerprint(left), Z59.tree_fingerprint(right))

    def test_alias_audit_rejects_cross_entity_identity_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "supply"
            Z59.build_supply(output)
            audit = json.loads((output / "alias_candidate_audit.json").read_text(encoding="utf-8"))
        row = next(item for item in audit["rows"] if item["row_number"] == 26)
        self.assertEqual(row["identity_group_status"], "cross_entity_conflict")
        self.assertEqual(row["disposition"], "not_used_cross_entity_identity_conflict")

    def test_verify_recomputes_chapter_fields_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "supply"
            Z59.build_supply(output)
            chapter_path = output / "chapters" / "ch0003.json"
            chapter = json.loads(chapter_path.read_text(encoding="utf-8"))
            chapter["tables"]["人物演员表"][0]["window_range"] = "伪造范围"
            Z59.write_json(chapter_path, chapter)
            with self.assertRaisesRegex(Exception, "实体供料机械验收失败"):
                Z59.verify_supply(output)

    def test_a_semantic_review_covers_all_baseline_events_and_hard_stops(self) -> None:
        run_dir = ROOT / "runs/Z59_A_X01_实体供料注入中性抽取_五靶章_v1.0_20260719"
        review = json.loads((run_dir / "analysis/旧事件语义复核.json").read_text(encoding="utf-8"))
        hard_stop = json.loads((run_dir / "analysis/语义硬停单.json").read_text(encoding="utf-8"))
        rows = review["rows"]
        identities = [(row["chapter"], row["baseline_event_id_run_local_only"]) for row in rows]
        self.assertEqual(len(rows), 39)
        self.assertEqual(len(identities), len(set(identities)))
        counts = {verdict: sum(row["verdict"] == verdict for row in rows) for verdict in ("完整保留", "部分损失", "缺失")}
        self.assertEqual(counts, {key: review["summary"][key] for key in counts})
        self.assertEqual(sum(counts.values()), review["summary"]["baseline_events"])
        self.assertEqual(review["summary"]["degraded_total"], counts["部分损失"] + counts["缺失"])
        self.assertFalse(review["summary"]["old_event_nondegradation"])
        self.assertEqual(review["status"], "hard_stop_old_event_degradation")
        self.assertEqual(hard_stop["status"], "hard_stop_no_repair_no_rerun")
        self.assertEqual(hard_stop["scope_effect"]["trial_b"], "未启动")


if __name__ == "__main__":
    unittest.main()
