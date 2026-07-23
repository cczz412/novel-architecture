from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aa_anchor_audit", ROOT / "tools" / "aa_anchor_audit.py")
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class AAAnchorAuditTests(unittest.TestCase):
    def test_parse_multiple_corner_quotes(self):
        rows = audit.parse_anchor_line(
            "**锚｜**第12章「风不点灯，雨不燃烛。」；第14章「当拼图碎片凑齐12个」",
            section="R规则",
        )
        self.assertEqual([(row["locator_kind"], row["locator_number"]) for row in rows], [
            ("chapter", 12), ("chapter", 14),
        ])
        self.assertEqual(rows[0]["quote"], "风不点灯，雨不燃烛。")

    def test_parse_sequence_and_curly_quote(self):
        rows = audit.parse_anchor_line("| C001 | 序01“他的球象粘在脚下一样” |")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["locator_kind"], "sequence")
        self.assertEqual(rows[0]["locator_number"], 1)

    def test_parse_middle_dot_and_vertical_separator(self):
        dot = audit.parse_anchor_line("〔第1章·“花千骨体质太易招惹鬼怪”〕")
        vertical = audit.parse_anchor_line("第2章｜“一定时间内只能开启一道”")
        self.assertEqual(dot[0]["quote"], "花千骨体质太易招惹鬼怪")
        self.assertEqual(vertical[0]["quote"], "一定时间内只能开启一道")

    def test_heading_title_is_not_treated_as_anchor(self):
        self.assertEqual(audit.parse_anchor_line("### 第11章｜第11章 “旺旺早餐肠”"), [])

    def test_decision_marker_is_not_treated_as_anchor(self):
        self.assertEqual(
            audit.parse_anchor_line("读到第3章时放弃“每章固定一条”，改按事件切。"),
            [],
        )

    def test_markdown_wrapper_only_removes_outer_wrapper(self):
        rows = audit.parse_anchor_line("第3章「**甲  ……  ‘乙’**」")
        self.assertEqual(rows[0]["quote"], "甲  ……  ‘乙’")
        self.assertEqual(rows[0]["markdown_wrapper_removed"], "**")

    def test_chinese_chapter_number(self):
        self.assertEqual(audit.chinese_number("三十"), 30)
        self.assertEqual(audit.chinese_number("四十一"), 41)
        self.assertEqual(audit.chinese_number("十"), 10)

    def test_logical_chapter_and_non_story_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            story = root / "031_第三十章.txt"
            note = root / "030_上架感言！.txt"
            self.assertEqual(audit.source_logical_chapter(story, "第三十章\n正文"), 30)
            self.assertFalse(audit.is_non_story_source(story, "第三十章\n正文"))
            self.assertTrue(audit.is_non_story_source(note, "上架感言！\n说明"))

    def test_exact_check_does_not_normalize_ellipsis(self):
        source = {
            "rel_path": "chapter.txt",
            "text": "甲说……乙答。",
            "non_story_source": False,
        }
        anchor = {"locator_kind": "chapter", "locator_number": 1, "quote": "甲说…乙答", "length_gate": "pass"}
        result = audit.exact_check(anchor, {}, {1: [source]})
        self.assertEqual(result["status"], "no_exact_match")

    def test_spread_sample_covers_object_types(self):
        anchors = [
            {"object_type": "C", "locator_number": index}
            for index in range(1, 31)
        ]
        anchors[5]["object_type"] = "S"
        anchors[16]["object_type"] = "K"
        selected = audit.spread_sample(anchors, 10)
        selected_types = {anchors[index]["object_type"] for index in selected}
        self.assertEqual(len(selected), 10)
        self.assertTrue({"C", "S", "K"}.issubset(selected_types))

    def test_object_type_prefers_record_id_over_story_line(self):
        rows = audit.parse_anchor_line("| C001 | L0×L4 | 第1章「一段足够长的原文短引」 |")
        self.assertEqual(rows[0]["object_type"], "C")


if __name__ == "__main__":
    unittest.main()
