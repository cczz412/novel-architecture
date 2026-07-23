from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/batches/Z00n_X01_第6至10章程序清点单变量_5章_v1.1.json"
SPEC = importlib.util.spec_from_file_location("z00n", ROOT / "tools" / "z00n_classification_split.py")
assert SPEC and SPEC.loader
z00n = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z00n)


class Z00nClassificationSplitTests(unittest.TestCase):
    def test_prompt_change_is_exactly_self_audit_deletion(self):
        ok, sha = z00n.prompt_change_is_exact()
        self.assertTrue(ok)
        self.assertEqual(sha, z00n.EXPECTED_PROMPT_SHA256)

    def test_transport_contract_remains_z00m(self):
        provider = json.loads((ROOT / "config/providers/sensenova_z00m.json").read_text(encoding="utf-8"))
        self.assertEqual(provider["model"], "deepseek-v4-flash")
        self.assertEqual(provider["temperature"], 0.2)
        self.assertEqual(provider["reasoning_effort"], "medium")
        self.assertEqual(provider["n"], 1)
        self.assertEqual(provider["max_tokens_by_stage"]["extract"], 16000)

    def test_rules_and_old_adapters_remain_pinned(self):
        pairs = [
            ("work/zbatch_prompts/candidates/main_control_classification_rules_v1.0.md", z00n.EXPECTED_RULES_SHA256),
            ("tools/z00l_classification_split.py", z00n.EXPECTED_Z00L_ADAPTER_SHA256),
            ("tools/z00m_classification_split.py", z00n.EXPECTED_Z00M_ADAPTER_SHA256),
            ("tools/z00n_event_audit.py", z00n.EXPECTED_CHECKER_SHA256),
        ]
        for relative_path, expected_sha in pairs:
            self.assertEqual(z00n.zbatch.sha256_file(ROOT / relative_path), expected_sha)

    def test_historical_preflight_is_read_only_and_locked_after_cutover(self):
        result = z00n.z00n_preflight(CONFIG, require_key=False)
        failed = {row["name"] for row in result["checks"] if not row["ok"]}
        self.assertIn("runner_sha256", failed)
        self.assertIn("provider_has_no_global_sampling", failed)
        self.assertIn("classification_contract_configured", failed)
        self.assertEqual(result["preflight"], "fail")
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["z00n_contract"]["d_mod_modules_connected"])

    def test_expected_chapter_files_are_still_exactly_five(self):
        batch = {"chapter_start": 6, "chapter_end": 10}
        self.assertEqual(
            z00n.z00m.expected_parsed_files(batch),
            ["ch0006.json", "ch0007.json", "ch0008.json", "ch0009.json", "ch0010.json"],
        )

    def test_complete_set_rejects_missing_files_before_classification(self):
        batch = {"chapter_start": 6, "chapter_end": 10}
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "01_event_extract" / "parsed").mkdir(parents=True)
            with self.assertRaisesRegex(z00n.zbatch.ZBatchError, "解析件未齐套"):
                z00n.verify_complete_event_set(run_dir, batch)


if __name__ == "__main__":
    unittest.main()
