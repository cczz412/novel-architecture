from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = REPO_ROOT / "references/t5-r04"
SYNTHETIC_ARTIFACT = b'{"store":"LAB"}\n'
SYNTHETIC_ARTIFACT_SHA256 = (
    "b7e6e75a73530653d5faab3de45b5889dd06d3c9a3641a99167b569e04a83810"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def make_synthetic_store_binding(root: Path) -> tuple[Path, dict[str, Path], dict]:
    store_roots = {
        store_id: root / "stores" / store_id
        for store_id in ("MAIN_REPO", "LAB", "ARCHIVE")
    }
    for store_root in store_roots.values():
        store_root.mkdir(parents=True)

    relative_path = "fixtures/route.json"
    artifact_path = store_roots["LAB"] / relative_path
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(SYNTHETIC_ARTIFACT)
    if hashlib.sha256(SYNTHETIC_ARTIFACT).hexdigest() != SYNTHETIC_ARTIFACT_SHA256:
        raise AssertionError("合成材料 SHA 常量已漂移")

    binding_path = root / "stores.local.json"
    write_json(
        binding_path,
        {
            "stores": {
                store_id: str(store_root.resolve())
                for store_id, store_root in store_roots.items()
            }
        },
    )
    catalog = {
        "schema_version": "finetuning-legacy-route-catalog-v1",
        "authority": {
            "scope": "historical_navigation_catalog",
            "may_define_current_experiment": False,
            "may_authorize_training": False,
            "may_authorize_upload": False,
            "may_authorize_deletion_or_merge": False,
        },
        "routes": [
            {
                "route_id": "synthetic_route",
                "store_id": "LAB",
                "relative_path": relative_path,
                "path_kind": "file",
                "row_count": 1,
                "fact_count": 1,
                "sha256": SYNTHETIC_ARTIFACT_SHA256,
            }
        ],
    }
    return binding_path, store_roots, catalog


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
        import tools.finetuning_domain as domain

        with tempfile.TemporaryDirectory() as temp_dir:
            binding_path, _, catalog = make_synthetic_store_binding(Path(temp_dir))
            with patch.object(domain, "LOCAL_STORES", binding_path):
                local_stores = domain.load_stores()

            self.assertEqual(set(local_stores), {"MAIN_REPO", "LAB", "ARCHIVE"})
            self.assertTrue(all(path.is_absolute() for path in local_stores.values()))
            for route in catalog["routes"]:
                expected_sha = route.get("sha256")
                if expected_sha is None:
                    continue
                path = local_stores[route["store_id"]] / route["relative_path"]
                self.assertTrue(path.is_file(), route["route_id"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected_sha)

    def test_local_critical_historical_files_match_catalog_when_bound(self):
        import tools.finetuning_domain as domain

        catalog = load_json(REFERENCE_ROOT / "route_catalog.json")
        local_stores = domain.load_stores()
        for route in catalog["routes"]:
            expected_sha = route.get("sha256")
            if expected_sha is None:
                continue
            path = local_stores[route["store_id"]] / route["relative_path"]
            self.assertTrue(path.is_file(), route["route_id"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected_sha)

    def test_derived_route_files_can_be_rebuilt_in_an_empty_directory(self):
        import tools.finetuning_control as control

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            binding_path, store_roots, catalog = make_synthetic_store_binding(root)
            experiment_id = "SYNTHETIC_T5_R04"
            experiments_root = root / "control/experiments"
            manifest_path = experiments_root / experiment_id / "MANIFEST.json"
            derived_facts = {
                "full_rows_each_arm": 2,
                "training_rows_each_arm": 1,
                "current_exam_rows_each_arm": 1,
                "current_gold_facts_each_arm": 1,
            }
            manifest = {
                "schema_version": "finetuning-experiment-manifest-v1",
                "experiment_id": experiment_id,
                "manifest_revision": "r01",
                "spec_sha256": "0" * 64,
                "state": {"lifecycle": "sealed"},
                "source_root": {"store_id": "LAB", "relative_path": "fixtures"},
                "artifacts": [
                    {
                        "artifact_id": "synthetic::fixtures/route.json",
                        "store_id": "LAB",
                        "relative_path": "fixtures/route.json",
                        "bytes": len(SYNTHETIC_ARTIFACT),
                        "sha256": SYNTHETIC_ARTIFACT_SHA256,
                    }
                ],
                "derived_facts": derived_facts,
                "boundaries": {
                    "may_authorize_training": False,
                    "may_authorize_promotion": False,
                },
            }
            write_json(manifest_path, manifest)
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            current_path = root / "control/CURRENT.json"
            write_json(
                current_path,
                {
                    "schema_version": "finetuning-current-pointer-v2",
                    "current_experiment_id": experiment_id,
                    "manifest_revision": "r01",
                    "manifest_sha256": manifest_sha,
                },
            )
            catalog_path = root / "control/route_catalog.json"
            write_json(catalog_path, catalog)

            first_output = root / "first-empty-build"
            second_output = root / "second-empty-build"
            with (
                patch.object(control, "EXPERIMENTS_ROOT", experiments_root),
                patch.object(control, "CURRENT_PATH", current_path),
                patch.object(control, "ROUTE_CATALOG_PATH", catalog_path),
                patch.object(control.domain, "LOCAL_STORES", binding_path),
            ):
                control.command_build_routes(first_output)
                control.command_build_routes(second_output)

            self.assertEqual(
                (first_output / "route_registry.json").read_bytes(),
                (second_output / "route_registry.json").read_bytes(),
            )
            self.assertEqual(
                (first_output / "README.md").read_bytes(),
                (second_output / "README.md").read_bytes(),
            )
            registry = load_json(first_output / "route_registry.json")
            self.assertEqual(registry["generated_from"]["manifest_sha256"], manifest_sha)
            self.assertEqual(registry["historical_routes"], catalog["routes"])
            self.assertEqual(
                registry["current_experiment"]["derived_facts"],
                derived_facts,
            )
            self.assertEqual(
                Path(load_json(binding_path)["stores"]["LAB"]),
                store_roots["LAB"].resolve(),
            )

    def test_local_derived_route_files_match_committed_views_when_bound(self):
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
