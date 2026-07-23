from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/z93_five_gold_revision.py"
SPEC = importlib.util.spec_from_file_location("z93_five_gold_revision", MODULE_PATH)
assert SPEC and SPEC.loader
z93r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z93r)


class Z93FiveGoldRevisionTests(unittest.TestCase):
    def test_expected_scope_is_exactly_52_unique_source_parts(self) -> None:
        ids = [part_id for rows in z93r.EXPECTED_TARGETS.values() for part_id in rows]
        self.assertEqual(52, len(ids))
        self.assertEqual(52, len(set(ids)))
        self.assertEqual(
            {"Z74B-B01", "Z74B-B02", "Z74B-B03", "Z74B-B04", "Z74B-B05"},
            set(z93r.EXPECTED_TARGETS),
        )

    def test_specs_match_locked_scope_and_quotes(self) -> None:
        specs = z93r.load_specs(z93r.DEFAULT_SPEC_DIR)
        z74b = z93r.load_z74b_module()
        for book_id, spec in specs.items():
            draft = z93r.read_json(ROOT / spec["source_candidate_path"])
            source_text, units, _ = z74b.load_cache_inventory(
                Path(draft["source"]["full_txt_path"]),
                book_id,
                draft["source"]["cache_unit_total"],
            )
            for revision in spec["revisions"]:
                for replacement in revision["replacements"]:
                    rows = z93r.evidence_rows(
                        draft=draft,
                        replacement=replacement,
                        cache_units=units,
                        source_text=source_text,
                    )
                    self.assertTrue(rows)
                    self.assertTrue(all(10 <= len(row["quote"]) <= 25 for row in rows))

    def test_one_book_revision_keeps_untouched_parts_identical(self) -> None:
        specs = z93r.load_specs(z93r.DEFAULT_SPEC_DIR)
        z74b = z93r.load_z74b_module()
        spec = specs["Z74B-B04"]
        revised, scope, ledger = z93r.revise_one(spec=spec, z74b=z74b)
        self.assertTrue(scope["untouched_part_hash_match"])
        self.assertEqual([], scope["unexpected_changed_part_ids"])
        self.assertEqual(13, len(ledger["rows"]))
        self.assertEqual("candidate_pending_cz_review", revised["status"])
        self.assertFalse(revised["protected_state"]["formal_gold_promoted"])

    def test_missing_target_or_duplicate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="z93-revision-spec-", dir=ROOT / "TEMP") as name:
            temp = Path(name)
            for path in z93r.DEFAULT_SPEC_DIR.glob("*_revision_spec.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload["book_id"] == "Z74B-B01":
                    payload = copy.deepcopy(payload)
                    payload["target_ids"] = payload["target_ids"][:-1]
                (temp / path.name).write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            with self.assertRaises(AssertionError):
                z93r.load_specs(temp)

    def test_nonempty_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="z93-revision-output-", dir=ROOT / "TEMP") as name:
            output = Path(name)
            (output / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaises(AssertionError):
                z93r.assert_safe_output(output, z93r.DEFAULT_SPEC_DIR)


if __name__ == "__main__":
    unittest.main()
