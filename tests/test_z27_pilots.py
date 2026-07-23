from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


z00o = load_script("z00o_verbatim_pilot", "z00o_verbatim_pilot.py")
minicpm = load_script("minicpm_preextract_pilot", "minicpm_preextract_pilot.py")


class Z27PilotTests(unittest.TestCase):
    def test_z00o_source_uses_event_text_as_ordered_items(self):
        parsed = {
            "chapter": 6,
            "events": [
                {"event_id": "EV-C0006-01", "event": "第一件事"},
                {"event_id": "EV-C0006-02", "event": "第二件事"},
            ],
        }
        source = z00o.source_for_chapter(parsed, 6)
        self.assertEqual([item["item_id"] for item in source["items"]], ["EV-C0006-01", "EV-C0006-02"])
        self.assertEqual(source["items"][0]["source_text"], "第一件事")
        self.assertEqual(source["items"][0]["source_sha256"], hashlib.sha256("第一件事".encode()).hexdigest())

    def test_both_parsers_reject_markdown_fences_instead_of_repairing(self):
        with self.assertRaisesRegex(Exception, "不修补"):
            z00o.strict_json_object("```json\n{}\n```")
        with self.assertRaisesRegex(Exception, "不修补"):
            minicpm.strict_json_object("```json\n{}\n```")

    def test_z00o_historical_config_reports_runner_pin_drift(self):
        receipt = z00o.preflight(z00o.DEFAULT_CONFIG)
        self.assertEqual(receipt["preflight"], "fail")
        self.assertEqual(receipt["model_calls"], 0)
        self.assertEqual(receipt["source_item_total"], 82)
        failed = [row for row in receipt["checks"] if not row["ok"]]
        self.assertEqual([row["name"] for row in failed], ["pin:tools/zbatch.py"])
        self.assertFalse(receipt["global_three_gates"]["evaluated"])

    def test_minicpm_historical_config_reports_new_contract_pin_without_runtime(self):
        receipt = minicpm.preflight(minicpm.DEFAULT_CONFIG, require_runtime=False)
        self.assertEqual(receipt["preflight"], "fail")
        self.assertEqual(receipt["model_calls"], 0)
        failed = [row for row in receipt["checks"] if not row["ok"]]
        self.assertEqual(
            [row["name"] for row in failed],
            ["pin:tools/zbatch_modules/neutral_extract.py"],
        )
        self.assertFalse(receipt["semantic_score_evaluated"])

    def test_minicpm_reference_diagnostic_is_descriptive_only(self):
        reference = {"events": [{"anchors": [{"anchor_id": "E1"}, {"anchor_id": "E2"}]}]}
        actual = {"events": [{"anchors": [{"anchor_id": "E2"}, {"anchor_id": "E3"}]}]}
        result = minicpm.reference_diagnostic(reference, actual)
        self.assertEqual(result["anchor_id_overlap_count"], 1)
        self.assertIn("不裁判", result["reference_role"])

    def test_minicpm_uses_real_unique_chapter_filename(self):
        config = minicpm.load_config(minicpm.DEFAULT_CONFIG)
        chapter_dir = ROOT / config["book_chapter_dir"]
        self.assertEqual(minicpm.chapter_filename(chapter_dir, 6), "0006_第6章_非凡者.txt")

    def test_minicpm_prestart_resume_rejects_any_model_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "preflight.json").write_text("{}")
            (run_dir / "config_snapshot.json").write_text("{}")
            self.assertTrue(minicpm.prestart_resume_allowed(run_dir))
            (run_dir / "responses").mkdir()
            (run_dir / "responses/ch0006.txt").write_text("generated")
            self.assertFalse(minicpm.prestart_resume_allowed(run_dir))


if __name__ == "__main__":
    unittest.main()
