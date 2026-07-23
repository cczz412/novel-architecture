from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z68_continuation_report as report  # noqa: E402


class Z68ContinuationReportTests(unittest.TestCase):
    def test_main_report_counts_follow_current_diff(self) -> None:
        current = report.current_diff(report.RUN)
        self.assertEqual(current["summary"]["preserved"], 17)
        self.assertEqual(current["summary"]["partially_preserved"], 16)
        self.assertEqual(current["summary"]["not_observed"], 1)
        markdown = (
            report.REPORT
            / "第68道续令停点回包｜32k参数兼容修复与裸考成绩_20260720.md"
        ).read_text(encoding="utf-8")
        report.assert_main_semantic_counts(markdown, current)


if __name__ == "__main__":
    unittest.main()
