from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import z83_retry13_atomic_repair as retry13  # noqa: E402
import z94_local_semantic_supply as z94  # noqa: E402


class Z94LocalSemanticSupplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts, cls.summary = z94.build_primary_artifacts()
        cls.preflight = json.loads(cls.artifacts["preflight.json"])

    def test_frozen_parent_child_counts_and_atomic_n(self) -> None:
        self.assertEqual(13, self.preflight["parent_count"])
        self.assertEqual(32, self.preflight["logical_request_count"])
        self.assertEqual(25, self.preflight["atomic_split_total"])
        self.assertEqual({"3": 7, "13": 7, "19": 18}, self.preflight["chapter_task_counts"])
        self.assertEqual(
            z94.EXPECTED_ATOMIC_SPLIT_COUNTS,
            self.preflight["atomic_split_counts"],
        )
        parent_counts = Counter(row["parent_event_id"] for row in self.preflight["rows"])
        self.assertEqual(
            z94.EXPECTED_ATOMIC_SPLIT_COUNTS,
            {key: value for key, value in parent_counts.items() if value > 1},
        )

    def test_source_shas_and_rule_shas_are_pinned(self) -> None:
        self.assertEqual(
            z94.SOURCE_PLAN_SHA256,
            self.preflight["source_plan_sha256"],
        )
        self.assertEqual(
            z94.SOURCE_ADJUDICATION_SHA256,
            self.preflight["source_adjudication_sha256"],
        )
        self.assertEqual(z94.SOURCE_V3_PROMPT_SHA256, self.preflight["source_v3_prompt_sha256"])
        self.assertEqual(
            {
                "paragraph_window": z94.paragraph_window_rule()["rule_sha256"],
                "anchor_cluster": z94.anchor_cluster_rule()["rule_sha256"],
                "must_preserve": z94.must_preserve_rule()["rule_sha256"],
            },
            self.preflight["rules"],
        )

    def test_window_and_anchor_cluster_are_mechanical_and_closed(self) -> None:
        for row in self.preflight["rows"]:
            with self.subTest(task_id=row["task_id"]):
                supply = json.loads(
                    self.artifacts[f"supply_bundles/{row['task_id']}.json"]
                )
                window = supply["paragraph_window"]
                target_ordinals = [
                    int(value.removeprefix("P")) for value in window["target_paragraph_ids"]
                ]
                window_ordinals = [
                    int(value.removeprefix("P")) for value in window["window_paragraph_ids"]
                ]
                self.assertTrue(window["window_text"].strip())
                self.assertEqual(
                    max(1, min(target_ordinals) - 1),
                    min(window_ordinals),
                    msg=row["task_id"],
                )
                self.assertEqual(
                    min(
                        window["chapter_paragraph_count"],
                        max(target_ordinals) + 1,
                    ),
                    max(window_ordinals),
                    msg=row["task_id"],
                )
                cluster = supply["anchor_cluster"]
                selected_by_audit = [
                    item["anchor_id"]
                    for item in cluster["selection_rows"]
                    if item["selected"]
                ]
                self.assertEqual(cluster["candidate_anchor_ids"], selected_by_audit)
                self.assertTrue(
                    set(cluster["required_anchor_ids"]).issubset(
                        cluster["candidate_anchor_ids"]
                    )
                )
                self.assertEqual(0, cluster["outside_catalog_anchor_count"])
                self.assertEqual(
                    len(cluster["candidate_anchor_ids"]),
                    len(set(cluster["candidate_anchor_ids"])),
                )

    def test_single_object_contract_and_non_supply_text_are_unchanged(self) -> None:
        system = retry13._extract_single_object_system_contract()
        plan = json.loads(z94.SOURCE_PLAN.read_text(encoding="utf-8"))
        events = retry13._source_event_map(z94.SOURCE_RUN)
        task_by_id = {row["task_id"]: row for row in plan["tasks"]}
        for row in self.preflight["rows"]:
            task_id = row["task_id"]
            with self.subTest(task_id=task_id):
                body = json.loads(
                    self.artifacts[f"prepared_requests/z94-{task_id}.json"]
                )
                task = task_by_id[task_id]
                source_event = events[task["parent_event_id"]]
                self.assertEqual(system, body["messages"][0]["content"])
                self.assertTrue(
                    body["messages"][1]["content"].startswith(
                        z94._static_prefix(task, source_event)
                    )
                )
                self.assertTrue(
                    body["messages"][1]["content"].endswith(
                        "只按一对一单对象输出合同 v1 返回一个 JSON 对象。"
                    )
                )
                self.assertEqual(z94.Z94_PARAMETERS["temperature"], body["temperature"])
                self.assertEqual(z94.Z94_PARAMETERS["max_tokens"], body["max_tokens"])
                self.assertEqual(z94.Z94_PARAMETERS["n"], body["n"])
                self.assertEqual(
                    z94.Z94_PARAMETERS["reasoning_effort"], body["reasoning_effort"]
                )

    def test_gold_answers_and_score_material_are_not_model_visible(self) -> None:
        forbidden = (
            "GOLD-C",
            "gold_rows",
            "formal_gold",
            "scorecard",
            "金标",
            "答案",
            "旧25",
            "现役122条",
        )
        for name, raw in self.artifacts.items():
            if not name.startswith("prepared_requests/"):
                continue
            body = json.loads(raw)
            text = json.dumps(body["messages"], ensure_ascii=False)
            with self.subTest(request=name):
                self.assertEqual([], [token for token in forbidden if token in text])
        self.assertFalse(self.preflight["gold_or_answer_material_sent_to_model"])

    def test_must_preserve_is_exact_derivative_not_rejudgment(self) -> None:
        for row in self.preflight["rows"]:
            supply = json.loads(
                self.artifacts[f"supply_bundles/{row['task_id']}.json"]
            )
            preserve = supply["must_preserve"]
            with self.subTest(task_id=row["task_id"]):
                self.assertTrue(preserve["fact_head"])
                self.assertTrue(preserve["necessary_qualifiers_and_permission"])
                self.assertFalse(preserve["derivation"]["semantic_rejudgment"])
                self.assertFalse(preserve["derivation"]["hand_selection"])
                self.assertFalse(supply["provenance"]["references_model_visible"])

    def test_parameter_conflict_is_explicit_and_blocks_step2(self) -> None:
        audit = json.loads(self.artifacts["parameter_diff_vs_retry13.json"])
        self.assertEqual(2, audit["difference_count"])
        self.assertEqual(
            {"temperature", "max_tokens"},
            {row["field"] for row in audit["differences"]},
        )
        self.assertFalse(audit["single_variable_claim_allowed"])
        self.assertFalse(audit["step2_release_allowed"])
        self.assertTrue(self.preflight["parameter_attribution_hold"])
        self.assertFalse(self.preflight["step2_release_allowed"])

    def test_supply_boundary_audit_limits_model_visible_change_to_middle_slice(self) -> None:
        with self.subTest(scope="all_32_requests"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                run_dir = Path(tmp)
                z94._write_artifacts(run_dir, self.artifacts)
                audit = z94.build_supply_boundary_audit(run_dir)
        self.assertEqual("pass_32_outside_supply_slice_byte_equal", audit["status"])
        self.assertEqual(32, audit["row_count"])
        self.assertTrue(all(row["system_message_equal"] for row in audit["rows"]))
        self.assertTrue(all(row["outside_supply_slice_equal"] for row in audit["rows"]))
        self.assertTrue(
            all(
                row["changed_envelope_fields"] == ["max_tokens", "temperature"]
                for row in audit["rows"]
            )
        )

    def test_two_independent_builds_are_byte_identical_and_zero_call(self) -> None:
        second, second_summary = z94.build_primary_artifacts()
        self.assertEqual(self.artifacts, second)
        self.assertEqual(self.summary, second_summary)
        self.assertEqual(
            z94._artifact_set_sha(self.artifacts),
            z94._artifact_set_sha(second),
        )
        usage = json.loads(self.artifacts["usage_zero_call.json"])
        self.assertEqual(0, usage["model_api_calls"])
        self.assertEqual(0, usage["network_attempts"])
        self.assertEqual(0, usage["usage_tokens"])

    def test_protection_snapshot_contains_six_gold_entries_and_frozen_runs(self) -> None:
        protected = self.preflight["protected_before"]
        pointer_paths = [
            path
            for path in protected["files"]
            if path.startswith("config/gold/") and path.endswith("_current.json")
        ]
        self.assertEqual(6, len(pointer_paths))
        self.assertEqual(80, protected["trees"]["retry09_frozen"]["files"])
        self.assertEqual(485, protected["trees"]["retry13_frozen"]["files"])
        self.assertGreater(protected["trees"]["outbox"]["files"], 0)


if __name__ == "__main__":
    unittest.main()
