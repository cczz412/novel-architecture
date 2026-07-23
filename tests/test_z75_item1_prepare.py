from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z75_item1_prepare.py"
SPEC = importlib.util.spec_from_file_location("z75_item1_prepare", MODULE_PATH)
assert SPEC and SPEC.loader
z75 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z75)


class Z75Item1PrepareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_path = ROOT / z75.SOURCE_REL
        cls.source_bytes = cls.source_path.read_bytes()
        cls.candidate = json.loads(cls.source_bytes.decode("utf-8"))

    def test_source_is_pinned_and_counts_are_exact(self) -> None:
        self.assertEqual(z75.EXPECTED_SOURCE_SHA256, z75.sha256_bytes(self.source_bytes))
        counts = z75.source_counts(self.candidate)
        self.assertEqual(16, counts["triplet_group_total"])
        self.assertEqual(48, counts["variant_total"])
        self.assertEqual(28, counts["just_right_record_total"])
        self.assertEqual(42, counts["anchor_total"])
        self.assertEqual(178, counts["support_term_total"])

    def test_field_support_terms_and_anchors_all_pass(self) -> None:
        audit = z75.build_support_audit(self.candidate)
        self.assertEqual("pass", audit["status"])
        self.assertEqual(28, audit["checks"]["record_total"])
        self.assertEqual(42, audit["checks"]["anchor_total"])
        self.assertEqual(0, audit["checks"]["failed_record_total"])
        for row in audit["rows"]:
            self.assertEqual("pass", row["status"], row["record_key"])
            self.assertTrue(
                all(
                    anchor["length_10_to_25"] and anchor["verbatim_in_source_scenario"]
                    for anchor in row["anchor_checks"]
                ),
                row["record_key"],
            )

    def test_landing_table_has_one_candidate_for_every_just_right_record(self) -> None:
        table = z75.build_landing_table(self.candidate)
        self.assertEqual(28, table["summary"]["row_total"])
        self.assertEqual(28, table["summary"]["row_with_primary_receiver_total"])
        self.assertEqual(28, table["summary"]["l0_anchor_receiver_total"])
        self.assertEqual(0, table["summary"]["t_or_v_primary_total"])
        self.assertEqual(0, table["summary"]["unfrozen_receiver_path_total"])
        self.assertEqual({"K": 2, "L1": 25, "L6": 1}, table["summary"]["primary_layer_counts"])
        self.assertEqual(28, len({row["record_key"] for row in table["rows"]}))
        allowed_layers = {layer["layer"] for layer in z75.LAYER_DEFINITIONS}
        for row in table["rows"]:
            self.assertIn(row["primary_layer"], allowed_layers)
            self.assertTrue(row["primary_field_paths"])
            self.assertEqual("L0.原文位置", row["evidence_receiver"])
            self.assertEqual("candidate_pending_cloud_review", row["status"])
            receiver_paths = [row["evidence_receiver"], *row["primary_field_paths"]]
            for targets in row["field_mapping"].values():
                receiver_paths.extend(targets)
            for receiver in row["secondary_receivers"]:
                receiver_paths.extend(receiver["field_paths"])
            self.assertTrue(set(receiver_paths) <= z75.FROZEN_RECEIVER_PATHS, row["record_key"])

    def test_schema_authority_has_frozen_ten_layers(self) -> None:
        reference = z75.build_schema_reference()
        self.assertEqual(10, reference["layer_total"])
        self.assertEqual(
            ["L0", "L1", "L2", "L3", "K", "L4", "L5", "L6", "T", "V"],
            [layer["layer"] for layer in reference["layers"]],
        )
        self.assertEqual("4e3a7a30-0862-4fd0-9869-b5d9045be8a0", reference["authority"]["page_id"])

    def test_prepare_and_verify_bundle_without_touching_source(self) -> None:
        before = z75.sha256_bytes(self.source_bytes)
        with tempfile.TemporaryDirectory() as raw:
            out_dir = Path(raw) / "item1"
            result = z75.prepare_bundle(out_dir)
            self.assertEqual("pass", result["status"], result["mismatches"])
            self.assertEqual(self.source_bytes, (out_dir / z75.RAW_COPY_NAME).read_bytes())
            split_index = z75.read_json(out_dir / z75.SPLIT_INDEX_JSON_NAME)
            reconstructed = b"".join((out_dir / part["path"]).read_bytes() for part in split_index["parts"])
            self.assertEqual(self.source_bytes, reconstructed)
            self.assertEqual(4, split_index["counts"]["page_total"])
            self.assertEqual(16, split_index["counts"]["triplet_group_total"])
            self.assertEqual(28, split_index["counts"]["just_right_record_total"])
            self.assertEqual(42, split_index["counts"]["anchor_total"])
            verify_again = z75.verify_bundle(out_dir)
            self.assertEqual("pass", verify_again["status"], verify_again["mismatches"])
        self.assertEqual(before, z75.sha256_path(self.source_path))

    def test_forbidden_source_is_path_only_metadata(self) -> None:
        self.assertEqual(
            "reports/Z74A_正反例换皮候选_20260721/原料来源与病灶提炼.json",
            z75.FORBIDDEN_SOURCE,
        )
        table = z75.build_landing_table(self.candidate)
        serialized = json.dumps(table, ensure_ascii=False)
        self.assertNotIn(z75.FORBIDDEN_SOURCE, serialized)
        self.assertNotIn("fce54974", serialized)


if __name__ == "__main__":
    unittest.main()
