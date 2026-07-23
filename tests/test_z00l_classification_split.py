from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("z00l", ROOT / "tools" / "z00l_classification_split.py")
assert SPEC and SPEC.loader
z00l = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z00l)


class Z00lClassificationSplitTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {"anchor_id": "E0001", "quote": "甲在门外听见钟声，于是推门进入密室"},
            {"anchor_id": "E0002", "quote": "随后机关彻底关闭，众人无法原路返回"},
        ]
        self.event = {
            "schema_version": "z-event-v1",
            "chapter": 6,
            "coverage_audit": {
                "status": "emitted",
                "event_ids": ["EV-C0006-01"],
                "reason": "已经按原文顺序检查本章发生变化和后续安排。",
            },
            "events": [
                {
                    "event_id": "EV-C0006-01",
                    "event": "甲听见钟声后进入密室，机关随后关闭",
                    "anchors": [{"anchor_id": "E0001"}],
                }
            ],
        }

    def test_event_envelope_accepts_neutral_event(self):
        self.assertEqual(z00l.event_envelope_reasons(self.event, 6, self.catalog), [])

    def test_event_envelope_rejects_classification_field(self):
        data = {**self.event, "events": [{**self.event["events"][0], "type": "A"}]}
        self.assertIn("EV-C0006-01字段越出中性事件合同", z00l.event_envelope_reasons(data, 6, self.catalog))

    def test_event_envelope_rejects_classification_label(self):
        data = {**self.event, "events": [{**self.event["events"][0], "event": "这是跨章因果，甲进入密室"}]}
        self.assertIn("EV-C0006-01夹带分类标签", z00l.event_envelope_reasons(data, 6, self.catalog))

    def test_materialize_event_anchor_is_exact(self):
        data = z00l.materialize_event_anchors(self.event, self.catalog, 6)
        self.assertEqual(
            data["events"][0]["anchors"][0],
            {"chapter": 6, "anchor_id": "E0001", "quote": "甲在门外听见钟声，于是推门进入密室"},
        )

    def test_decisions_must_cover_every_event(self):
        data = {
            "schema_version": "z-main-control-classification-v1",
            "run_id": "run",
            "rules_sha256": "rules",
            "decisions": [],
        }
        reasons = z00l.decision_reasons(
            data,
            run_id="run",
            rules_sha256="rules",
            event_ids={"EV-C0006-01"},
        )
        self.assertTrue(any(reason.startswith("分类决定未一对一覆盖事件") for reason in reasons))

    def test_overlap_requires_conflict_reason(self):
        decision = {
            "event_id": "EV-C0006-01",
            "disposition": "classified",
            "matched_types": ["A", "C"],
            "primary_type": "A",
            "rule_ids": ["A-01"],
            "basis": "事实头是已经发生的进入密室变化",
            "assertion": "明",
            "fields": {
                "story_line": "密室线",
                "delta": "甲从门外变为进入密室",
                "direct_cause": "听见钟声后推门",
                "future_use": "机关关闭限制退路",
            },
            "related_event_ids": [],
            "duplicate_group": None,
            "conflict_reason": "",
        }
        data = {
            "schema_version": "z-main-control-classification-v1",
            "run_id": "run",
            "rules_sha256": "rules",
            "decisions": [decision],
        }
        reasons = z00l.decision_reasons(
            data,
            run_id="run",
            rules_sha256="rules",
            event_ids={"EV-C0006-01"},
        )
        self.assertIn("EV-C0006-01重叠或重复未写冲突说明", reasons)


if __name__ == "__main__":
    unittest.main()
