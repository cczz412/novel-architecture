from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import z83_program_side_repair_pilot as z83  # noqa: E402
import z83_retry13_atomic_repair as retry13  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402


CATALOG = [
    {"anchor_id": "E0001", "quote": "甲对乙完成了一项明确动作。"},
    {"anchor_id": "E0002", "quote": "这项动作产生了一个明确结果。"},
]


def sensenova_envelope(*, choices=None, model="deepseek-v4-flash", usage=None):
    return json.dumps(
        {
            "model": model,
            "choices": choices
            if choices is not None
            else [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "event": "甲对乙完成了一项明确动作并得到结果。",
                                "anchor_ids": ["E0001", "E0002"],
                            },
                            ensure_ascii=False,
                        )
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": usage
            if usage is not None
            else {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
        ensure_ascii=False,
    ).encode("utf-8")


class Retry13SingleObjectParserTests(unittest.TestCase):
    def test_sensenova_envelope_requires_exactly_one_choice_stop_and_usage(self) -> None:
        parsed, content, finish, usage = retry13._parse_sensenova_envelope(
            sensenova_envelope(), expected_model="deepseek-v4-flash"
        )
        self.assertEqual("deepseek-v4-flash", parsed["model"])
        self.assertIn('"event"', content)
        self.assertEqual("stop", finish)
        self.assertEqual(12, usage["total_tokens"])
        for raw, pattern in (
            (sensenova_envelope(choices=[]), "且只能有1项"),
            (
                sensenova_envelope(
                    choices=[
                        {"message": {"content": "{}"}, "finish_reason": "stop"},
                        {"message": {"content": "{}"}, "finish_reason": "stop"},
                    ]
                ),
                "且只能有1项",
            ),
            (
                sensenova_envelope(
                    choices=[{"message": {"content": "{}"}, "finish_reason": "length"}]
                ),
                "未正常结束",
            ),
            (sensenova_envelope(usage={}), "usage"),
            (sensenova_envelope(model="wrong-model"), "模型不一致"),
        ):
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(ZBatchError, pattern):
                    retry13._parse_sensenova_envelope(
                        raw, expected_model="deepseek-v4-flash"
                    )

    def test_approved_contract_is_single_object_and_has_no_output_array(self) -> None:
        text = retry13._extract_single_object_system_contract()
        self.assertIn('"event"', text)
        self.assertIn('"anchor_ids"', text)
        self.assertIn("不得输出 replacement_events", text)
        self.assertNotIn('"replacement_events":', text)

    def test_canonical_string_anchor_result_passes(self) -> None:
        normalized, diagnostics = retry13.parse_single_object_result(
            json.dumps(
                {
                    "event": "甲对乙完成了一项明确动作并得到结果。",
                    "anchor_ids": ["E0001", "E0002"],
                },
                ensure_ascii=False,
            ),
            catalog=CATALOG,
        )
        self.assertEqual(
            [{"anchor_id": "E0001"}, {"anchor_id": "E0002"}],
            normalized["anchors"],
        )
        self.assertEqual([], diagnostics)

    def test_legacy_anchor_leaf_objects_are_the_only_compatibility_exception(self) -> None:
        normalized, diagnostics = retry13.parse_single_object_result(
            json.dumps(
                {
                    "event": "甲对乙完成了一项明确动作并得到结果。",
                    "anchor_ids": [
                        {"anchor_id": "E0001", "quote": "只作旁账"},
                        {"anchor_id": "E0002", "confidence": 0.9},
                    ],
                },
                ensure_ascii=False,
            ),
            catalog=CATALOG,
        )
        self.assertEqual(2, len(diagnostics))
        self.assertTrue(all(not row["entered_formal_record"] for row in diagnostics))
        self.assertEqual(
            [{"anchor_id": "E0001"}, {"anchor_id": "E0002"}],
            normalized["anchors"],
        )

    def test_duplicate_json_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ZBatchError, "重复 JSON 键"):
            retry13.strict_json_loads(
                '{"event":"甲对乙完成动作。","event":"重复","anchor_ids":["E0001"]}'
            )

    def test_code_fence_and_trailing_second_object_are_rejected(self) -> None:
        with self.assertRaisesRegex(ZBatchError, "代码围栏"):
            retry13.strict_json_loads(
                '```json\n{"event":"甲对乙完成动作。","anchor_ids":["E0001"]}\n```'
            )
        with self.assertRaisesRegex(ZBatchError, "唯一合法 JSON"):
            retry13.strict_json_loads(
                '{"event":"甲对乙完成动作。","anchor_ids":["E0001"]}{}'
            )
        with self.assertRaisesRegex(ZBatchError, "非标准 JSON 常量"):
            retry13.strict_json_loads(
                '{"event":"甲对乙完成动作。","anchor_ids":["E0001"],"x":NaN}'
            )

    def test_array_root_container_pollution_and_mixed_anchors_are_rejected(self) -> None:
        with self.assertRaisesRegex(ZBatchError, "根字段"):
            retry13.parse_single_object_result(
                '[{"event":"甲对乙完成动作。","anchor_ids":["E0001"]},"reasoning"]',
                catalog=CATALOG,
            )
        with self.assertRaisesRegex(ZBatchError, "不得混用"):
            retry13.parse_single_object_result(
                json.dumps(
                    {
                        "event": "甲对乙完成了一项明确动作。",
                        "anchor_ids": ["E0001", {"anchor_id": "E0002"}],
                    },
                    ensure_ascii=False,
                ),
                catalog=CATALOG,
            )

    def test_illegal_duplicate_or_external_anchor_is_rejected(self) -> None:
        for anchor_ids, pattern in (
            (["E0001", "E0001"], "重复"),
            (["E9999"], "目录外"),
            (["e0001"], "非法"),
        ):
            with self.subTest(anchor_ids=anchor_ids):
                with self.assertRaisesRegex(ZBatchError, pattern):
                    retry13.parse_single_object_result(
                        json.dumps(
                            {
                                "event": "甲对乙完成了一项明确动作。",
                                "anchor_ids": anchor_ids,
                            },
                            ensure_ascii=False,
                        ),
                        catalog=CATALOG,
                    )

    def test_program_prechecked_anchor_set_must_match_exactly(self) -> None:
        content = json.dumps(
            {
                "event": "甲对乙完成了一项明确动作并得到结果。",
                "anchor_ids": ["E0001"],
            },
            ensure_ascii=False,
        )
        with self.assertRaisesRegex(ZBatchError, "完整锚集合"):
            retry13.parse_single_object_result(
                content,
                catalog=CATALOG,
                required_anchor_ids=["E0001", "E0002"],
            )


class Retry13AtomicPlanTests(unittest.TestCase):
    def synthetic_plan(self, *, pending: bool = False):
        parents = []
        tasks = []
        ordinal = 0
        for parent_ordinal, event_id in enumerate(retry13.PARENT_ORDER, 1):
            specs = retry13._parent_task_specs(event_id)
            route = "pending_cz_not_sent" if pending and event_id == "EV-C0019-25" else "direct"
            task_ids = []
            if route != "pending_cz_not_sent":
                for fact_ordinal, spec in enumerate(specs, 1):
                    ordinal += 1
                    task_id = retry13._task_id(event_id, fact_ordinal)
                    task_ids.append(task_id)
                    tasks.append(
                        {
                            "task_id": task_id,
                            "parent_event_id": event_id,
                            "chapter": int(event_id[4:8]),
                            "fact_ordinal": fact_ordinal,
                            "fact_count": len(specs),
                            "fact_target_sha256": retry13.canonical_sha(spec["fact"]),
                        }
                    )
            parents.append(
                {
                    "parent_ordinal": parent_ordinal,
                    "event_id": event_id,
                    "chapter": int(event_id[4:8]),
                    "route": route,
                    "fact_count": len(specs),
                    "task_ids": task_ids,
                }
            )
        return {
            "parents": parents,
            "tasks": tasks,
            "pending_parent_ids": ["EV-C0019-25"] if pending else [],
        }

    def result_map(self, plan):
        return {
            task["task_id"]: {
                "normalized_replacement": {
                    "event": f"第{index}条原子事件有明确主体动作结果。",
                    "anchors": [{"anchor_id": "E0001"}],
                }
            }
            for index, task in enumerate(plan["tasks"], 1)
        }

    def test_six_atomic_counts_freeze_to_twenty_five_and_total_to_thirty_two(self) -> None:
        self.assertEqual(
            {
                "EV-C0003-05": 4,
                "EV-C0013-35": 4,
                "EV-C0013-46": 2,
                "EV-C0019-34": 5,
                "EV-C0019-40": 4,
                "EV-C0019-47": 6,
            },
            {key: len(value) for key, value in retry13.ATOMIC_FACT_SPECS.items()},
        )
        self.assertEqual(25, sum(len(value) for value in retry13.ATOMIC_FACT_SPECS.values()))
        self.assertEqual(32, sum(len(retry13._parent_task_specs(value)) for value in retry13.PARENT_ORDER))

    def test_same_parent_children_are_aggregated_without_last_write_wins(self) -> None:
        plan = self.synthetic_plan()
        replacements, ledgers = retry13.aggregate_parent_results(
            plan, self.result_map(plan)
        )
        source_index = int("EV-C0003-05".rsplit("-", 1)[1]) - 1
        self.assertEqual(4, len(replacements[3][source_index]))
        parent = next(row for row in ledgers if row["parent_event_id"] == "EV-C0003-05")
        self.assertEqual(4, parent["replacement_count"])
        self.assertEqual(13, len(ledgers))
        self.assertEqual(13, len({row["parent_event_id"] for row in ledgers}))

    def test_missing_or_extra_child_result_is_rejected(self) -> None:
        plan = self.synthetic_plan()
        results = self.result_map(plan)
        results.pop(next(iter(results)))
        with self.assertRaisesRegex(ZBatchError, "结果不齐"):
            retry13.aggregate_parent_results(plan, results)

    def test_pending_parent_blocks_release_and_is_not_removed_from_denominator(self) -> None:
        plan = self.synthetic_plan(pending=True)
        results = self.result_map(plan)
        with self.assertRaisesRegex(ZBatchError, "不得释放"):
            retry13.aggregate_parent_results(plan, results)
        self.assertIn("EV-C0019-25", plan["pending_parent_ids"])
        pending = next(row for row in plan["parents"] if row["event_id"] == "EV-C0019-25")
        self.assertEqual("pending_cz_not_sent", pending["route"])

    def test_retry13_is_only_added_to_completed_seed_and_punctuation_whitelists(self) -> None:
        run_dir = ROOT / "runs" / retry13.RUN_NAME
        self.assertTrue(z83._formal_completed_seed_target(run_dir))
        self.assertTrue(z83._formal_punctuation_unit_target(run_dir))
        self.assertFalse(z83._formal_thirteen_retry_target(run_dir))
        self.assertFalse(z83._uses_retry11_request_contract(run_dir))


if __name__ == "__main__":
    unittest.main()
