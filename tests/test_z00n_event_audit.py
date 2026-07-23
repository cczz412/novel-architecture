from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("z00n_event_audit", ROOT / "tools" / "z00n_event_audit.py")
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class Z00nEventAuditTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {"anchor_id": "E0001", "quote": "甲听见钟声后推门进入密室，机关随即关闭"},
            {"anchor_id": "E0002", "quote": "众人确认原路已经无法返回，只能继续前进"},
        ]
        self.data = {
            "schema_version": "z-event-v1",
            "chapter": 6,
            "events": [
                {
                    "event_id": "EV-C0006-01",
                    "event": "甲进入密室后机关关闭，众人无法原路返回",
                    "anchors": [{"anchor_id": "E0001"}, {"anchor_id": "E0002"}],
                }
            ],
        }

    def test_accepts_events_without_model_self_audit(self):
        reasons, result = audit.audit_event_envelope(self.data, 6, self.catalog)
        self.assertEqual(reasons, [])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["event_ids"], ["EV-C0006-01"])
        self.assertEqual(result["anchor_reference_count"], 2)
        self.assertFalse("coverage_audit" in self.data)

    def test_rejects_model_self_audit_as_extra_field(self):
        data = {**self.data, "coverage_audit": {"event_ids": ["EV-C0006-01"]}}
        reasons, result = audit.audit_event_envelope(data, 6, self.catalog)
        self.assertIn("事件外壳字段不等于固定合同", reasons)
        self.assertEqual(result["status"], "fail")

    def test_rejects_unknown_anchor_id(self):
        data = {
            **self.data,
            "events": [{**self.data["events"][0], "anchors": [{"anchor_id": "E9999"}]}],
        }
        reasons, result = audit.audit_event_envelope(data, 6, self.catalog)
        self.assertIn("EV-C0006-01证据目录ID不存在", reasons)
        self.assertEqual(result["missing_catalog_anchor_ids"], ["E9999"])

    def test_rejects_non_contiguous_event_ids(self):
        data = {
            **self.data,
            "events": [{**self.data["events"][0], "event_id": "EV-C0006-02"}],
        }
        reasons, result = audit.audit_event_envelope(data, 6, self.catalog)
        self.assertIn("事件ID集合或顺序不连续", reasons)
        self.assertFalse(result["event_ids_contiguous"])

    def test_empty_events_are_mechanically_valid_without_semantic_claim(self):
        data = {"schema_version": "z-event-v1", "chapter": 6, "events": []}
        reasons, result = audit.audit_event_envelope(data, 6, self.catalog)
        self.assertEqual(reasons, [])
        self.assertEqual(result["event_count"], 0)
        self.assertIn("不声称语义无遗漏", result["scope_note"])


if __name__ == "__main__":
    unittest.main()
