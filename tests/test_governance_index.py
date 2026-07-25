from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools import governance_index
from tools.pipeline_common.artifacts import read_json, verify_manifest


ROOT = Path(__file__).resolve().parents[1]


def _as_v2(state: dict) -> dict:
    current, history = governance_index.state_layers(copy.deepcopy(state))
    return {
        "schema_version": governance_index.CURRENT_STATE_SCHEMA_V2,
        "snapshot_at": state["snapshot_at"],
        "authority": copy.deepcopy(state["authority"]),
        "current_execution": current,
        "historical_context": history,
    }


class GovernanceIndexTests(unittest.TestCase):
    def test_experiment_index_only_lists_registered_directories(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiments = root / "experiments"
            experiments.mkdir()
            for name in (
                "z_unregistered",
                "_template",
                "a_registered",
                "m_unregistered",
            ):
                (experiments / name).mkdir()
            (experiments / "a_registered" / "experiment.json").write_text(
                json.dumps(
                    {
                        "experiment_id": "EXP-A",
                        "status": "trial",
                        "summary": "已登记样例",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (experiments / "_template" / "experiment.json").write_text(
                json.dumps(
                    {
                        "experiment_id": "TEMPLATE",
                        "status": "template",
                        "summary": "不得进入索引",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            registered = governance_index.discover_registered_experiment_files(root)
            self.assertEqual(
                [path.parent.name for path in registered],
                ["a_registered"],
            )

            first = governance_index.render_experiments_index(root)
            second = governance_index.render_experiments_index(root)
            self.assertEqual(first, second)
            self.assertIn("## 当前登记", first)
            self.assertIn("| EXP-A | trial | `experiments/a_registered`", first)
            self.assertIn("未登记的本地候选与证据目录不写进生成页", first)
            self.assertNotIn("m_unregistered", first)
            self.assertNotIn("z_unregistered", first)
            self.assertNotIn("TEMPLATE", first)
            self.assertNotIn("_template", first)

    def test_registry_has_all_modules_and_only_three_states(self) -> None:
        source = read_json(ROOT / governance_index.REGISTRY_SOURCE_PATH)
        registry = governance_index.materialize_registry(ROOT, source)
        ids = {row["module_id"] for row in registry["modules"]}
        self.assertEqual(ids, {f"M{number:02d}" for number in range(12)})
        self.assertEqual(
            {row["status"] for row in registry["modules"]},
            {"可用", "在改", "试验"},
        )
        for row in registry["modules"]:
            self.assertTrue(row["source_refs"])
            self.assertTrue(all(ref["exists"] for ref in row["source_refs"]))

    def test_refresh_is_reproducible_and_manifest_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first)
            second_root = Path(second)
            first_manifest = governance_index.refresh(ROOT, first_root)
            second_manifest = governance_index.refresh(ROOT, second_root)
            self.assertEqual(first_manifest, second_manifest)
            self.assertTrue(verify_manifest(first_root, first_manifest["outputs"])["passed"])
            for relative in governance_index.GENERATED_PATHS + ["governance/index_manifest.json"]:
                self.assertEqual(
                    (first_root / relative).read_bytes(),
                    (second_root / relative).read_bytes(),
                    relative,
                )

    def test_current_state_and_route_registry_are_single_machine_sources(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        state = read_json(ROOT / governance_index.CURRENT_STATE_PATH)
        routes = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        governance_index.validate_control_plane(ROOT, control)
        governance_index.validate_current_state(ROOT, state)
        governance_index.validate_route_registry(ROOT, routes, state)

        current, history = governance_index.state_layers(state)
        self.assertNotIn("current_task", control)
        self.assertEqual(control["current_state_path"], governance_index.CURRENT_STATE_PATH)
        task = current["task"]
        for key in ("task_id", "label", "status", "status_label"):
            self.assertIsInstance(task.get(key), str)
            self.assertTrue(task[key].strip(), key)
        self.assertEqual(
            state["authority"]["external_truth"]["ledger_url"],
            "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c",
        )
        self.assertEqual(
            state["authority"]["external_truth"]["queue_url"],
            "https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc",
        )
        self.assertEqual(
            control["formal_gold_registry"]["path"],
            "config/gold/formal_gold_registry.json",
        )
        self.assertEqual(control["formal_gold_registry"]["entry_total"], 6)
        self.assertTrue(
            any(
                row["name"] == "第93道续令②五本v1.3修订候选"
                for row in control["silver_candidates"]
            )
        )
        self.assertTrue(
            any(
                row["name"] == "第93道续令②五本金标候选修订"
                for row in control["run_report_pairs"]
            )
        )
        self.assertTrue(
            any(
                row["name"] == "第93道续令③五本结构层金标v1.3转正"
                for row in control["run_report_pairs"]
            )
        )
        self.assertTrue(
            any(
                row["issue_id"] == "Z93-X01-GOLD-C0003-07-N01-ANCHOR-ISSUE-001"
                and row["status"] == "deferred_by_cz_choice_a_to_z92_anchor_gate"
                for row in history["issue_ledger"]
            )
        )
        self.assertEqual(
            history["legacy_mainline"]["latest_authorization"]["status"],
            "executed_hard_stop",
        )
        self.assertTrue(
            history["legacy_mainline"]["latest_authorization"]["local_process_observed"]
        )
        self.assertEqual(
            history["legacy_mainline"]["z85_gate"]["status"],
            "completed_before_retry06",
        )
        self.assertTrue(
            any(
                row["task_id"] == "Z84-repo-hygiene" and row["status"] == "accepted"
                for row in history["accepted_steps"]
            )
        )
        self.assertTrue(
            any(
                row["task_id"] == "Z93-five-formal-gold-promotion"
                and row["status"] == "accepted_full_chain_closed"
                and row["formal_gold_entry_total"] == 6
                for row in history["accepted_steps"]
            )
        )
        run_states = {row["run_id"]: row for row in history["archived_run_states"]}
        z89 = run_states["Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723"]
        self.assertEqual(z89["effective_status"], "candidate_silver_scored_callback_returned")
        self.assertEqual(z89["strict_hit"], 10)
        self.assertEqual(z89["effective_recall"], 20)
        self.assertEqual(z89["surface_coverage"], 23)
        original = run_states["Z83_X01_v3程序侧治法_三章复验_v1.0_20260722"]
        self.assertTrue(original["authoritative_ticket"].endswith("/main/hard_stop.json"))
        retry = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry01"
        ]
        self.assertIn("未找到", retry["evidence_gap"])
        retry04 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry04"
        ]
        self.assertEqual(retry04["effective_status"], "inspector_hard_stop_quote_drift")
        self.assertEqual(retry04["retry04_new_inspector_network_attempts"], 1)
        self.assertEqual(retry04["accepted_inspector_logical_results"], 0)
        retry05 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry05"
        ]
        self.assertEqual(
            retry05["effective_status"],
            "inspector_hard_stop_quote_truncation",
        )
        self.assertEqual(retry05["retry05_new_inspector_network_attempts"], 2)
        self.assertEqual(retry05["accepted_inspector_logical_results"], 1)
        self.assertEqual(retry05["chapter_19_inspector_calls"], 0)
        retry06 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry06"
        ]
        self.assertEqual(
            retry06["effective_status"],
            "inspector_hard_stop_true_non_substring",
        )
        self.assertEqual(retry06["retry06_new_inspector_network_attempts"], 1)
        self.assertEqual(retry06["accepted_inspector_logical_results"], 0)
        self.assertEqual(retry06["chapter_19_inspector_calls"], 0)
        retry08 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry08"
        ]
        self.assertEqual(
            retry08["effective_status"],
            "hard_stop_semantic_pre_retry_capacity_exceeded",
        )
        self.assertEqual(retry08["retry08_new_inspector_network_attempts"], 2)
        self.assertEqual(retry08["retry08_new_usage_tokens"], 37024)
        self.assertFalse(retry08["retry_plan_created"])
        retry09 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry09"
        ]
        self.assertEqual(
            retry09["effective_status"],
            "hard_stop_total_retry_capacity_exceeded",
        )
        self.assertEqual(retry09["retry09_new_inspector_network_attempts"], 0)
        self.assertEqual(retry09["retry09_new_usage_tokens"], 0)
        self.assertEqual(retry09["full_semantic_adjudication_rows"], 246)
        self.assertEqual(retry09["confirmed_retry_source_events"], 13)
        self.assertFalse(retry09["retry_plan_created"])
        retry10 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry10"
        ]
        self.assertEqual(
            retry10["effective_status"],
            "hard_stop_fifth_targeted_rewrite_contract_violation",
        )
        self.assertEqual(retry10["planned_targeted_rewrites"], 13)
        self.assertEqual(retry10["called_targeted_rewrites"], 5)
        self.assertEqual(retry10["accepted_targeted_rewrite_results"], 0)
        self.assertEqual(retry10["failed_event_id"], "EV-C0013-06")
        self.assertEqual(retry10["remaining_events_not_called"], 8)
        self.assertFalse(retry10["four_gate_scorecard_created"])
        retry11 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry11"
        ]
        self.assertEqual(
            retry11["effective_status"],
            "hard_stop_second_targeted_rewrite_anchor_field_violation",
        )
        self.assertEqual(retry11["planned_targeted_rewrites"], 13)
        self.assertEqual(retry11["called_targeted_rewrites"], 2)
        self.assertEqual(retry11["accepted_targeted_rewrite_results"], 0)
        self.assertEqual(retry11["failed_event_id"], "EV-C0003-05")
        self.assertEqual(retry11["failed_event_unexpected_anchor_field"], "quote")
        self.assertEqual(retry11["remaining_events_not_called"], 11)
        self.assertFalse(retry11["four_gate_scorecard_created"])
        retry12 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry12"
        ]
        self.assertEqual(
            retry12["effective_status"],
            "hard_stop_ninth_targeted_rewrite_exact_count_violation",
        )
        self.assertEqual(retry12["planned_targeted_rewrites"], 13)
        self.assertEqual(retry12["called_targeted_rewrites"], 9)
        self.assertEqual(retry12["accepted_targeted_rewrite_results"], 0)
        self.assertEqual(retry12["anchor_extra_field_strip_rows"], 0)
        self.assertEqual(retry12["failed_event_id"], "EV-C0019-25")
        self.assertEqual(retry12["failed_event_returned_replacements"], 2)
        self.assertEqual(retry12["remaining_events_not_called"], 4)
        self.assertFalse(retry12["four_gate_scorecard_created"])
        retry13 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry13"
        ]
        self.assertEqual(
            retry13["effective_status"],
            "hard_stop_candidate_failed_four_gates_and_risk",
        )
        self.assertEqual(retry13["retry13_parent_source_events"], 13)
        self.assertEqual(retry13["retry13_frozen_single_object_requests"], 32)
        self.assertEqual(retry13["retry13_repair_network_attempts"], 32)
        self.assertEqual(retry13["retry13_inspector_network_attempts"], 3)
        self.assertEqual(retry13["retry13_new_network_attempts"], 35)
        self.assertEqual(retry13["retry13_new_429_attempts"], 0)
        self.assertEqual(retry13["retry13_new_usage_tokens"], 301277)
        self.assertEqual(retry13["historical_main_usage_tokens_imported"], 83297)
        self.assertEqual(retry13["lineage_usage_tokens"], 384574)
        self.assertEqual(retry13["stable_source_event_count"], 156)
        self.assertEqual(retry13["final_event_count"], 175)
        self.assertTrue(retry13["double_verification_consistent"])
        self.assertTrue(retry13["final_review_created"])
        self.assertTrue(retry13["four_gate_scorecard_created"])
        self.assertEqual(
            retry13["four_gates"],
            {
                "mechanical_three_gates": True,
                "old25_zero_regression": False,
                "chapter3_gold_floor": False,
                "semantic_anchor_invalid_zero": False,
            },
        )
        self.assertTrue(retry13["frozen"])
        route_states = {row["route_id"]: row["status"] for row in routes["routes"]}
        self.assertEqual(route_states["ROUTE-PROGRAM-SIDE-REPAIR"], "in_trial")
        self.assertEqual(route_states["ROUTE-PROMPT-LEAK-REPAIR"], "retired")
        self.assertEqual(
            {row["issue_id"] for row in history["issue_ledger"]},
            {
                "Z83-RETRY13-ANCHOR-GOLD-ISSUE-001",
                "Z83-RETRY13-OLD25-REGRESSION-ISSUE-001",
                "Z83-RETRY13-INSTRUCTION-SCOPE-ISSUE-001",
                "Z83-RETRY13-MANIFEST-PROJECTION-ISSUE-001",
                "Z83-RETRY11-ANCHOR-OBJECT-SCHEMA-ISSUE-001",
                "Z83-RETRY12-EXACT-COUNT-REGRESSION-ISSUE-001",
                "Z83-RETRY11-TOP-MANIFEST-PROJECTION-ISSUE-001",
                "Z83-RETRY12-TOP-MANIFEST-PROJECTION-ISSUE-001",
                "Z83-RETRY10-SPLIT-CONTRACT-ISSUE-001",
                "Z83-RETRY09-TOTAL-CAPACITY-ISSUE-001",
                "Z83-RETRY08-CAPACITY-ISSUE-001",
                "Z83-RETRY07-PREFLIGHT-ISSUE-001",
                "Z83-RETRY06-ISSUE-001",
                "Z83-RETRY05-ISSUE-001",
                "Z83-RETRY04-ISSUE-001",
                "Z86-ISSUE-001",
                "Z86-ISSUE-002",
                "Z93-X01-GOLD-C0003-07-N01-ANCHOR-ISSUE-001",
            },
        )

        governance_index.validate_route_registry(ROOT, routes, {})
        overclaimed_routes = copy.deepcopy(routes)
        program = next(
            row
            for row in overclaimed_routes["routes"]
            if row["route_id"] == "ROUTE-PROGRAM-SIDE-REPAIR"
        )
        program["status"] = "failed"
        with self.assertRaisesRegex(
            governance_index.ArtifactError,
            "路线末事件仍未判死",
        ):
            governance_index.validate_route_registry(ROOT, overclaimed_routes, {})

    def test_current_state_rejects_status_that_disagrees_with_hard_stop_ticket(self) -> None:
        state = read_json(ROOT / governance_index.CURRENT_STATE_PATH)
        broken = copy.deepcopy(state)
        history = (
            broken["historical_context"]
            if broken.get("schema_version") == governance_index.CURRENT_STATE_SCHEMA_V2
            else broken
        )
        run_states = (
            history["archived_run_states"]
            if "archived_run_states" in history
            else history["run_states"]
        )
        original = next(
            row
            for row in run_states
            if row["run_id"] == "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722"
        )
        original["effective_status"] = "hard_stop_interrupted"
        with self.assertRaisesRegex(governance_index.ArtifactError, "中断状态与硬停票不符"):
            governance_index.validate_current_state(ROOT, broken)

    def test_v2_layers_current_execution_and_rejects_legacy_top_level_aliases(self) -> None:
        state = _as_v2(read_json(ROOT / governance_index.CURRENT_STATE_PATH))
        governance_index.validate_current_state(ROOT, state)
        for key in governance_index.LEGACY_TOP_LEVEL_STATE_KEYS:
            self.assertNotIn(key, state)

        broken = copy.deepcopy(state)
        broken["current_step"] = {"task_id": "duplicate"}
        with self.assertRaisesRegex(
            governance_index.ArtifactError,
            "不得保留旧顶层键",
        ):
            governance_index.validate_current_state(ROOT, broken)

    def test_v2_rejects_absolute_current_artifact_identity(self) -> None:
        state = _as_v2(read_json(ROOT / governance_index.CURRENT_STATE_PATH))
        state["current_execution"]["artifacts"]["report_directory"] = "/tmp/report"
        with self.assertRaisesRegex(
            governance_index.ArtifactError,
            "必须是仓库相对路径",
        ):
            governance_index.validate_current_state(ROOT, state)

    def test_governance_docs_pin_key_gates_and_check_stop_line(self) -> None:
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        governance_readme = (ROOT / "governance/README.md").read_text(encoding="utf-8")
        self.assertIn("现役密钥加载入口只有本仓", root_readme)
        self.assertIn("进程读取闸", root_readme)
        self.assertIn("供应商认证闸", root_readme)
        self.assertIn("两份相互独立的证据给出同一结论就停", governance_readme)
        self.assertIn("同时运行的子任务最多 3 个", governance_readme)

    def test_index_answers_four_questions_and_demotes_old_routes(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        current_state = read_json(ROOT / governance_index.CURRENT_STATE_PATH)
        route_registry = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        source = read_json(ROOT / governance_index.REGISTRY_SOURCE_PATH)
        registry = governance_index.materialize_registry(ROOT, source)
        documents = governance_index.build_documents(
            ROOT, control, current_state, route_registry, registry
        )
        index = documents["governance/INDEX.md"]
        for phrase in ("现在跑到哪道", "金标哪版哪指针", "各模块什么状态", "银标候选在哪"):
            self.assertIn(phrase, index)
        current, _history = governance_index.state_layers(current_state)
        self.assertIn(current["task"]["label"], index)
        self.assertIn(current["task"]["status_label"], index)
        self.assertIn(current["controls"]["next_action"], index)
        self.assertNotIn("retry01 第3章 HTTP 200", index)
        route = documents["governance/indexes/route_health.md"]
        self.assertIn("current.md", route)
        self.assertIn("governance/INDEX.md", route)
        self.assertIn("tools/zbatch_modules/README.md", route)

    def test_generated_current_pages_do_not_render_historical_context(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        current_state = _as_v2(read_json(ROOT / governance_index.CURRENT_STATE_PATH))
        routes = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        source = read_json(ROOT / governance_index.REGISTRY_SOURCE_PATH)
        registry = governance_index.materialize_registry(ROOT, source)
        current_state["current_execution"]["task"]["label"] = "V2当前任务唯一标记"
        current_state["current_execution"]["controls"]["next_action"] = "V2当前下一动作唯一标记"
        current_state["historical_context"]["legacy_mainline"][
            "label"
        ] = "禁止出现在路牌的历史标记"
        current_state["historical_context"]["issue_ledger"][0][
            "summary"
        ] = "禁止出现在路牌的历史问题标记"
        control["recent_score"]["path"] = "禁止出现在当前页的历史成绩标记"

        documents = governance_index.build_documents(
            ROOT,
            control,
            current_state,
            routes,
            registry,
        )
        for relative in ("governance/INDEX.md", "governance/current_run.md"):
            text = documents[relative]
            self.assertIn("V2当前任务唯一标记", text)
            self.assertIn("V2当前下一动作唯一标记", text)
            self.assertNotIn("禁止出现在路牌的历史标记", text)
            self.assertNotIn("禁止出现在路牌的历史问题标记", text)
            self.assertNotIn("禁止出现在当前页的历史成绩标记", text)

    def test_root_readme_has_one_hop_governance_route(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[治理索引](governance/INDEX.md)", readme)

    def test_test_command_is_one_fixed_tests_only_command(self) -> None:
        policy = read_json(ROOT / "governance/test_policy.json")
        expected = (
            "cd /Users/a1234/挣钱/小说架构 && "
            "/opt/homebrew/opt/python@3.11/bin/python3.11 -m pytest -q"
        )
        self.assertEqual(policy["full_chain_command"], expected)
        self.assertIn(expected, (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(expected, (ROOT / "governance/README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
