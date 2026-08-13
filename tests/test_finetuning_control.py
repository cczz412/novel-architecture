from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.finetuning_control as control


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


class FinetuningControlTests(unittest.TestCase):
    def make_spec(self, store_root: Path, experiment_id: str) -> dict:
        experiment_root = store_root / "lab" / experiment_id
        experiment_root.mkdir(parents=True)
        (experiment_root / "data.jsonl").write_text('{"value":1}\n', encoding="utf-8")
        receipt = store_root / "main" / "receipts" / f"{experiment_id}.json"
        write_json(receipt, {"status": "PASS"})
        return {
            "schema_version": "finetuning-experiment-spec-v2",
            "experiment_id": experiment_id,
            "manifest_revision": "r01",
            "source_root": {"store_id": "LAB", "relative_path": experiment_id},
            "state": {
                "lifecycle": "sealed",
                "storage_state": "lab",
                "promotion_state": "not_promoted",
            },
            "artifact_groups": [
                {
                    "group_id": "input",
                    "store_id": "LAB",
                    "base_relative_path": experiment_id,
                    "required": True,
                    "patterns": ["data.jsonl"],
                }
            ],
            "measurements": {
                "rows": {"operation": "jsonl_rows", "relative_path": "data.jsonl"}
            },
            "assertions": [{"type": "equal", "measurements": ["rows", "rows"]}],
            "current_gate": {
                "required_receipts": [
                    {
                        "store_id": "MAIN_REPO",
                        "relative_path": f"receipts/{experiment_id}.json",
                        "status_pointer": "/status",
                        "allowed_values": ["PASS"],
                    }
                ]
            },
            "boundaries": {
                "may_authorize_training": False,
                "may_authorize_promotion": False,
            },
        }

    def test_register_build_and_switch_are_three_separate_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            experiments_root = root / "main/finetuning/experiments"
            current_path = root / "main/finetuning/CURRENT.json"
            stores = {"MAIN_REPO": root / "main", "LAB": root / "lab"}
            for path in stores.values():
                path.mkdir(parents=True, exist_ok=True)
            spec = self.make_spec(root, "EXPERIMENT_TEST_R01")
            spec_path = root / "candidate-spec.json"
            write_json(spec_path, spec)
            write_json(
                current_path,
                {
                    "schema_version": "finetuning-current-pointer-v2",
                    "current_experiment_id": "UNCHANGED",
                },
            )
            with (
                patch.object(control, "EXPERIMENTS_ROOT", experiments_root),
                patch.object(control, "CURRENT_PATH", current_path),
                patch.object(control.domain, "load_stores", return_value=stores),
            ):
                control.command_register(spec_path)
                self.assertEqual(json.loads(current_path.read_text())["current_experiment_id"], "UNCHANGED")
                control.command_build(spec["experiment_id"])
                self.assertEqual(json.loads(current_path.read_text())["current_experiment_id"], "UNCHANGED")
                control.command_switch_current(spec["experiment_id"])
                current = json.loads(current_path.read_text())
                self.assertEqual(current["current_experiment_id"], spec["experiment_id"])
                self.assertRegex(current["manifest_sha256"], r"^[0-9a-f]{64}$")

    def test_switch_hard_stops_when_required_receipt_is_not_green(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            experiments_root = root / "main/finetuning/experiments"
            current_path = root / "main/finetuning/CURRENT.json"
            stores = {"MAIN_REPO": root / "main", "LAB": root / "lab"}
            for path in stores.values():
                path.mkdir(parents=True, exist_ok=True)
            spec = self.make_spec(root, "EXPERIMENT_TEST_FAIL")
            spec_path = root / "candidate-spec.json"
            write_json(spec_path, spec)
            with (
                patch.object(control, "EXPERIMENTS_ROOT", experiments_root),
                patch.object(control, "CURRENT_PATH", current_path),
                patch.object(control.domain, "load_stores", return_value=stores),
            ):
                control.command_register(spec_path)
                control.command_build(spec["experiment_id"])
                receipt = stores["MAIN_REPO"] / "receipts" / f"{spec['experiment_id']}.json"
                write_json(receipt, {"status": "FAIL"})
                with self.assertRaises(control.HardStop):
                    control.command_switch_current(spec["experiment_id"])


if __name__ == "__main__":
    unittest.main()
