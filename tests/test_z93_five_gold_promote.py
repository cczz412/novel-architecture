from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z93_five_gold_promote.py"
SPEC = importlib.util.spec_from_file_location("z93_five_gold_promote", MODULE_PATH)
assert SPEC and SPEC.loader
z93p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z93p)


class Z93FiveGoldPromoteTests(unittest.TestCase):
    REGISTERED_AT = "2026-07-23T15:20:00+08:00"

    def build(self) -> dict[str, bytes]:
        return z93p.build_all(self.REGISTERED_AT)

    def json_payload(self, payloads: dict[str, bytes], relative: str) -> dict:
        return json.loads(payloads[relative].decode("utf-8"))

    def test_five_formal_gold_artifacts_have_105_parts_and_gold_tier(self) -> None:
        payloads = self.build()
        formal_paths = sorted(
            path
            for path in payloads
            if path.startswith(str(z93p.REPORT_DIR / "formal_gold/"))
        )
        self.assertEqual(len(formal_paths), 5)
        documents = [self.json_payload(payloads, path) for path in formal_paths]
        self.assertEqual(sum(len(z93p.all_parts(doc)) for doc in documents), 105)
        self.assertEqual(
            sum(doc["evaluation_policy"]["formal_denominator"] for doc in documents),
            91,
        )
        self.assertEqual(
            sum(
                len(z93p.all_parts(doc))
                - doc["evaluation_policy"]["formal_denominator"]
                for doc in documents
            ),
            14,
        )
        for doc in documents:
            self.assertEqual(doc["schema_version"], "structure-gold-v1.3")
            self.assertEqual(doc["status"], "active_gold")
            self.assertEqual(doc["label_tier"], "gold")
            self.assertEqual(doc["provenance"]["label"], z93p.PROVENANCE_LABEL)
            self.assertFalse(doc["provenance"]["cz_personal_item_review"])
            self.assertEqual(doc["provenance"]["tier_effect"], "none_formal_gold")
            for part in z93p.all_parts(doc):
                self.assertEqual(part["review_status"], "formal_gold_accepted")
                self.assertEqual(
                    part["formal_score_eligible"],
                    part["score_in_single_chapter"],
                )

    def test_candidate_to_formal_semantic_payload_and_anchors_do_not_change(self) -> None:
        payloads = self.build()
        identity = self.json_payload(
            payloads,
            str(z93p.REPORT_DIR / "candidate_to_formal_identity_audit.json"),
        )
        self.assertEqual(identity["status"], "pass_no_semantic_payload_change")
        self.assertEqual(identity["counts"]["formal_part_total"], 105)
        self.assertEqual(identity["counts"]["anchor_total"], 184)
        self.assertEqual(identity["counts"]["semantic_payload_mismatch_total"], 0)
        self.assertTrue(all(row["part_ids_preserved"] for row in identity["books"]))
        self.assertIn(
            "版本作用域",
            identity["anchor_identity_policy"]["cross_version_v1_2_to_v1_3"],
        )

    def test_five_current_pointers_resolve_and_registry_keeps_x01(self) -> None:
        payloads = self.build()
        registry = self.json_payload(
            payloads,
            "config/gold/formal_gold_registry.json",
        )
        self.assertEqual(registry["counts"]["formal_gold_entry_total"], 6)
        self.assertEqual(registry["counts"]["z93_promoted_book_total"], 5)
        x01 = registry["entries"][0]
        self.assertEqual(
            x01["artifact_sha256"],
            z93p.PROTECTED_FILES["x01_formal_gold"][1],
        )
        z93_rows = registry["entries"][1:]
        self.assertEqual({row["label_tier"] for row in z93_rows}, {"gold"})
        for row in z93_rows:
            pointer = self.json_payload(payloads, row["pointer_path"])
            artifact = payloads[row["artifact_path"]]
            self.assertEqual(pointer["active_gold"]["sha256"], z93p.sha256_bytes(artifact))
            self.assertEqual(row["pointer_sha256"], z93p.sha256_bytes(payloads[row["pointer_path"]]))
            self.assertEqual(pointer["provenance_label"], z93p.PROVENANCE_LABEL)

    def test_mechanical_receipts_and_zero_call_boundary(self) -> None:
        payloads = self.build()
        double = self.json_payload(
            payloads,
            str(z93p.REPORT_DIR / "mechanical_double_run_receipt.json"),
        )
        acceptance = self.json_payload(
            payloads,
            str(z93p.REPORT_DIR / "mechanical_acceptance.json"),
        )
        usage = self.json_payload(payloads, str(z93p.REPORT_DIR / "usage.json"))
        self.assertTrue(double["identical"])
        self.assertEqual(double["run_1"], double["run_2"])
        self.assertEqual(acceptance["status"], "pass_formal_gold_registered")
        self.assertTrue(all(acceptance["gates"].values()))
        self.assertEqual(usage["model_api_logical_calls"], 0)
        self.assertEqual(usage["model_api_network_attempts"], 0)
        self.assertEqual(usage["model_api_usage_tokens"], 0)

    def test_two_isolated_writes_are_byte_identical(self) -> None:
        payloads = self.build()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first)
            second_root = Path(second)
            z93p.write_payloads(first_root, payloads)
            z93p.write_payloads(second_root, payloads)
            self.assertEqual(
                z93p.verify_written(first_root, payloads),
                z93p.verify_written(second_root, payloads),
            )
            for relative in payloads:
                self.assertEqual(
                    (first_root / relative).read_bytes(),
                    (second_root / relative).read_bytes(),
                )

    def test_existing_target_is_rejected_without_overwrite(self) -> None:
        payloads = self.build()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            relative = next(iter(payloads))
            target = root / relative
            target.parent.mkdir(parents=True)
            target.write_text("occupied", encoding="utf-8")
            with self.assertRaises(AssertionError):
                z93p.write_payloads(root, payloads)


if __name__ == "__main__":
    unittest.main()
