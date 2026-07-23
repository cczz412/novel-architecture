from __future__ import annotations

import unittest
from pathlib import Path

from tools.zbatch_modules import t5_cache_benchmark


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/diagnostics/Z01a_X01_缓存排法AB_v1.json"


class T5CacheBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = t5_cache_benchmark.read_json(MANIFEST)

    def test_preflight_contract_without_freshness(self) -> None:
        result = t5_cache_benchmark.preflight(self.manifest, ROOT, require_fresh_run=False)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(result["checks"]["same_segments_only_reordered"])

    def test_arm_only_reorders_identical_segments(self) -> None:
        segments = t5_cache_benchmark.build_segments(self.manifest, ROOT, 6)
        arm_a = t5_cache_benchmark.build_messages(segments, "A")[1]["content"]
        arm_b = t5_cache_benchmark.build_messages(segments, "B")[1]["content"]
        self.assertEqual(arm_a, f"{segments['fixed_task']}\n\n{segments['dynamic_payload']}")
        self.assertEqual(arm_b, f"{segments['dynamic_payload']}\n\n{segments['fixed_task']}")

    def test_task_first_has_longer_shared_prefix(self) -> None:
        ch6 = t5_cache_benchmark.build_segments(self.manifest, ROOT, 6)
        ch7 = t5_cache_benchmark.build_segments(self.manifest, ROOT, 7)
        a_prefix = t5_cache_benchmark.common_prefix_bytes(
            t5_cache_benchmark.build_messages(ch6, "A")[1]["content"],
            t5_cache_benchmark.build_messages(ch7, "A")[1]["content"],
        )
        b_prefix = t5_cache_benchmark.common_prefix_bytes(
            t5_cache_benchmark.build_messages(ch6, "B")[1]["content"],
            t5_cache_benchmark.build_messages(ch7, "B")[1]["content"],
        )
        self.assertGreater(a_prefix, b_prefix + 1000)

    def test_cache_usage_normalizes_cached_tokens(self) -> None:
        result = t5_cache_benchmark.normalize_cache_usage(
            {"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 256}}
        )
        self.assertEqual(result["prompt_cache_hit_tokens"], 256)
        self.assertEqual(result["prompt_cache_miss_tokens"], 744)
        self.assertEqual(result["miss_field_source"], "derived:prompt_tokens-hit_tokens")

    def test_native_cache_fields_take_priority(self) -> None:
        result = t5_cache_benchmark.normalize_cache_usage(
            {
                "prompt_tokens": 1000,
                "prompt_tokens_details": {
                    "cached_tokens": 1,
                    "prompt_cache_hit_tokens": 300,
                    "prompt_cache_miss_tokens": 700,
                },
            }
        )
        self.assertEqual(result["prompt_cache_hit_tokens"], 300)
        self.assertEqual(result["prompt_cache_miss_tokens"], 700)

    def test_missing_cache_field_is_unmeasured_not_zero(self) -> None:
        result = t5_cache_benchmark.normalize_cache_usage({"prompt_tokens": 1000})
        self.assertFalse(result["measured"])
        self.assertIsNone(result["prompt_cache_hit_tokens"])
        self.assertIsNone(result["prompt_cache_miss_tokens"])

    def test_impossible_cache_count_is_unmeasured(self) -> None:
        result = t5_cache_benchmark.normalize_cache_usage(
            {"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 1200}}
        )
        self.assertFalse(result["measured"])
        self.assertIn("大于输入", result["invalid_reason"])

    def test_cached_tokens_without_prompt_total_is_unmeasured(self) -> None:
        result = t5_cache_benchmark.normalize_cache_usage(
            {"prompt_tokens_details": {"cached_tokens": 0}}
        )
        self.assertFalse(result["measured"])
        self.assertIsNone(result["prompt_tokens"])
        self.assertIn("输入 token 总数", result["invalid_reason"])

    def test_experiment_marker_is_same_system_prefix(self) -> None:
        segments = t5_cache_benchmark.build_segments(self.manifest, ROOT, 6)
        system_a = t5_cache_benchmark.build_messages(segments, "A")[0]["content"]
        system_b = t5_cache_benchmark.build_messages(segments, "B")[0]["content"]
        self.assertEqual(system_a, system_b)
        self.assertTrue(system_a.startswith(self.manifest["fixed_experiment_marker"]))


if __name__ == "__main__":
    unittest.main()
