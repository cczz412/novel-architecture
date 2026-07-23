from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("z00m", ROOT / "tools" / "z00m_classification_split.py")
assert SPEC and SPEC.loader
z00m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z00m)


class Z00mClassificationSplitTests(unittest.TestCase):
    def test_transport_contract_is_single_sample(self):
        provider = json.loads((ROOT / "config/providers/sensenova_z00m.json").read_text(encoding="utf-8"))
        self.assertEqual(provider["model"], "deepseek-v4-flash")
        self.assertEqual(provider["temperature"], 0.2)
        self.assertEqual(provider["reasoning_effort"], "medium")
        self.assertEqual(provider["n"], 1)
        self.assertEqual(provider["max_tokens_by_stage"]["extract"], 16000)

    def test_prompt_and_rules_remain_pinned(self):
        self.assertEqual(
            z00m.zbatch.sha256_file(ROOT / "work/zbatch_prompts/candidates/extract_event_only_v1.0.md"),
            z00m.EXPECTED_PROMPT_SHA256,
        )
        self.assertEqual(
            z00m.zbatch.sha256_file(ROOT / "work/zbatch_prompts/candidates/main_control_classification_rules_v1.0.md"),
            z00m.EXPECTED_RULES_SHA256,
        )

    def test_z00l_adapter_remains_unchanged(self):
        self.assertEqual(
            z00m.zbatch.sha256_file(ROOT / "tools/z00l_classification_split.py"),
            z00m.EXPECTED_Z00L_ADAPTER_SHA256,
        )

    def test_expected_parsed_files_are_exactly_five(self):
        batch = {"chapter_start": 6, "chapter_end": 10}
        self.assertEqual(
            z00m.expected_parsed_files(batch),
            ["ch0006.json", "ch0007.json", "ch0008.json", "ch0009.json", "ch0010.json"],
        )

    def test_complete_set_rejects_missing_files(self):
        batch = {"chapter_start": 6, "chapter_end": 10}
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "01_event_extract" / "parsed").mkdir(parents=True)
            with self.assertRaisesRegex(z00m.zbatch.ZBatchError, "解析件未齐套"):
                z00m.verify_complete_event_set(run_dir, batch)


if __name__ == "__main__":
    unittest.main()
