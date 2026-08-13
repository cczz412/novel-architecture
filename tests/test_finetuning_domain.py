import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools/finetuning_domain.py"
CONTROL_PATH = ROOT / "tools/finetuning_control.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("finetuning_domain", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_control():
    spec = importlib.util.spec_from_file_location("finetuning_control", CONTROL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FinetuningDomainTests(unittest.TestCase):
    def test_current_pointer_resolves_to_registered_experiment(self):
        current = json.loads((ROOT / "finetuning/CURRENT.json").read_text())
        experiment_id = current["current_experiment_id"]
        experiment_dir = ROOT / "finetuning/experiments" / experiment_id
        experiment_spec = json.loads((experiment_dir / "SPEC.json").read_text())
        self.assertEqual(experiment_spec["experiment_id"], experiment_id)

    def test_tracked_store_registry_contains_no_machine_absolute_path(self):
        stores = json.loads((ROOT / "finetuning/stores.json").read_text())
        self.assertTrue(stores["local_binding_file"].startswith(".local/"))
        self.assertNotIn("/Users/", json.dumps(stores, ensure_ascii=False))

    def test_manifest_builder_is_canonical_and_templates_use_placeholders(self):
        tool = load_tool()
        sample = {"z": 1, "a": "中文"}
        self.assertEqual(tool.canonical_json(sample), tool.canonical_json(sample))
        for path in (ROOT / "finetuning/experiments").glob("*/templates/*.tmpl"):
            self.assertIn("{{", path.read_text())

    def test_current_manifest_matches_real_files_when_local_lab_is_available(self):
        if not (ROOT / ".local/finetuning/stores.local.json").exists():
            self.skipTest("这台机器没有微调重资产仓位绑定")
        tool = load_tool()
        spec, experiment_dir, _ = tool.load_current()
        if spec.get("schema_version") == "finetuning-experiment-spec-v2":
            control = load_control()
            _, expected, experiment_dir = control.build_manifest_v2(spec["experiment_id"])
        else:
            _, expected, experiment_dir, _ = tool.build_manifest()
        self.assertEqual((experiment_dir / "MANIFEST.json").read_bytes(), expected)
        self.assertIn(
            tool.sha256_bytes(expected),
            (experiment_dir / "MANIFEST.sha256").read_text(),
        )
        manifest = json.loads(expected)
        if spec.get("schema_version") != "finetuning-experiment-spec-v2":
            rebuilt_summary = tool.render_summary(manifest, tool.sha256_bytes(expected))
            self.assertEqual((experiment_dir / "SUMMARY.md").read_bytes(), rebuilt_summary)

    def test_current_generated_counts_are_not_literal_in_builder_or_templates(self):
        if not (ROOT / ".local/finetuning/stores.local.json").exists():
            self.skipTest("这台机器没有微调重资产仓位绑定")
        tool = load_tool()
        spec, experiment_dir, _ = tool.load_current()
        if spec.get("schema_version") == "finetuning-experiment-spec-v2":
            control = load_control()
            manifest, _, experiment_dir = control.build_manifest_v2(spec["experiment_id"])
        else:
            manifest, _, experiment_dir, _ = tool.build_manifest()
        facts = manifest["derived_facts"]
        legacy_keys = [
            "full_rows_each_arm",
            "training_rows_each_arm",
            "stage_1_positive_rows_each_arm",
            "stage_2_special_rows_each_arm",
            "current_exam_rows_each_arm",
            "current_gold_facts_each_arm",
            "raw_answer_records_total",
        ]
        keys = [key for key in legacy_keys if key in facts]
        texts = [TOOL_PATH.read_text()] + [
            path.read_text()
            for path in sorted((experiment_dir / "templates").glob("*.tmpl"))
        ]
        for value in (str(facts[key]) for key in keys):
            pattern = re.compile(rf"(?<![0-9]){re.escape(value)}(?![0-9])")
            self.assertFalse(any(pattern.search(text) for text in texts), value)


if __name__ == "__main__":
    unittest.main()
