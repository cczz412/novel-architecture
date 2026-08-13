from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = REPO_ROOT / "references/t5-r04"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class T5R04DerivedRouteTests(unittest.TestCase):
    def test_route_registry_is_a_derived_compatibility_view(self):
        registry = load_json(REFERENCE_ROOT / "route_registry.json")
        self.assertEqual(registry["authority"]["scope"], "compatibility_derived_view")
        self.assertFalse(registry["authority"]["may_define_current_truth"])
        self.assertNotIn("roots", registry)
        self.assertNotIn("current_summary", registry)

    def test_historical_catalog_contains_no_current_status_or_absolute_roots(self):
        catalog_text = (REFERENCE_ROOT / "route_catalog.json").read_text()
        catalog = json.loads(catalog_text)
        self.assertEqual(catalog["authority"]["scope"], "historical_navigation_catalog")
        self.assertNotIn("current_summary", catalog)
        self.assertNotIn("/Users/", catalog_text)
        self.assertEqual(len(catalog["routes"]), 21)

    def test_current_view_binds_current_pointer_and_manifest(self):
        current = load_json(REPO_ROOT / "finetuning/CURRENT.json")
        registry = load_json(REFERENCE_ROOT / "route_registry.json")
        current_experiment = registry["current_experiment"]
        self.assertEqual(current_experiment["experiment_id"], current["current_experiment_id"])
        self.assertEqual(current_experiment["manifest_sha256"], current["manifest_sha256"])

    def test_critical_historical_files_keep_expected_sha_and_counts(self):
        catalog = load_json(REFERENCE_ROOT / "route_catalog.json")
        local_stores = load_json(REPO_ROOT / ".local/finetuning/stores.local.json")["stores"]
        for route in catalog["routes"]:
            expected_sha = route.get("sha256")
            if expected_sha is None:
                continue
            path = Path(local_stores[route["store_id"]]) / route["relative_path"]
            self.assertTrue(path.is_file(), route["route_id"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected_sha)

    def test_derived_route_files_can_be_rebuilt_in_an_empty_directory(self):
        import tools.finetuning_control as control

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            control.command_build_routes(output)
            self.assertEqual(
                (output / "route_registry.json").read_bytes(),
                (REFERENCE_ROOT / "route_registry.json").read_bytes(),
            )
            self.assertEqual(
                (output / "README.md").read_bytes(),
                (REFERENCE_ROOT / "README.md").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
