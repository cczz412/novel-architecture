from __future__ import annotations

import ast
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "z99_supply_tables.py"
SPEC = importlib.util.spec_from_file_location("z99_supply_tables", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
z99 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = z99
SPEC.loader.exec_module(z99)


class Z99SupplyTablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts = z99.build_artifacts(REPO_ROOT)
        cls.table_a = json.loads(cls.artifacts["table_a_thinking_inputs.json"])
        cls.table_b = json.loads(cls.artifacts["table_b_historical_api_rounds.json"])
        cls.receipt = json.loads(cls.artifacts["acceptance_receipt.json"])

    def test_exact_twelve_thinking_inputs(self) -> None:
        rows = self.table_a["rows"]
        self.assertEqual(len(rows), 12)
        self.assertEqual(
            {
                code: sum(row["source_batch_code"] == code for row in rows)
                for code in ("UCR", "blind")
            },
            {"UCR": 6, "blind": 6},
        )
        expected = z99._table_a_expected_paths(REPO_ROOT)
        expected_paths = {
            path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
            for paths in expected.values()
            for path in paths
        }
        self.assertEqual({row["file_path"] for row in rows}, expected_paths)
        expected_notion_entries = {
            "UCR": {
                "parent": "https://app.notion.com/p/3a75cadc4d0f81509388ec91289d2cac",
                "batch_index": (
                    "https://app.notion.com/p/3a75cadc4d0f81b8b165daae23487712"
                ),
            },
            "blind": {
                "parent": "https://app.notion.com/p/b1c51430b1374d0a96b7bfb7d672e489",
                "batch_index": (
                    "https://app.notion.com/p/3a75cadc4d0f81e8956bcf6fbc38ea4c"
                ),
            },
        }
        for row in rows:
            data = (REPO_ROOT / row["file_path"]).read_bytes()
            text = data.decode("utf-8")
            self.assertEqual(row["bytes"], len(data))
            self.assertEqual(row["unicode_char_count"], len(text))
            self.assertEqual(row["sha256"], z99._sha256(data))
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            notion = expected_notion_entries[row["source_batch_code"]]
            self.assertEqual(row["notion_parent_entry"], notion["parent"])
            self.assertEqual(
                row["notion_batch_index_entry"],
                notion["batch_index"],
            )

    def test_table_b_has_requested_twelve_rounds(self) -> None:
        rows = self.table_b["rows"]
        self.assertEqual(len(rows), 12)
        self.assertEqual(
            [row["row_id"] for row in rows],
            [
                "retry03",
                "Z57",
                "Z59-A",
                "Z68C",
                "Z70",
                "Z71",
                "Z79",
                "Z80",
                "Z83-retry13",
                "Z89",
                "Z94",
                "Z98",
            ],
        )
        self.assertEqual(
            self.table_b["strict_score_groups"],
            {
                "denominator_14": ["Z57", "Z59-A", "Z68C", "Z70", "Z71"],
                "denominator_23": [
                    "retry03",
                    "Z79",
                    "Z80",
                    "Z83-retry13",
                    "Z89",
                    "Z94",
                ],
                "unjudged": ["Z98"],
            },
        )

    def test_cost_and_ucr_boundaries(self) -> None:
        rows = {row["row_id"]: row for row in self.table_b["rows"]}
        missing = [
            row_id
            for row_id, row in rows.items()
            if row["cost_cny"]["status"] == "missing"
        ]
        self.assertEqual(
            missing,
            [
                "retry03",
                "Z59-A",
                "Z68C",
                "Z70",
                "Z71",
                "Z79",
                "Z80",
                "Z83-retry13",
                "Z94",
            ],
        )
        for row_id in missing:
            self.assertEqual(rows[row_id]["cost_cny"]["amount_cny"], "missing")
            self.assertFalse(rows[row_id]["cost_cny"]["calculated_now"])
        self.assertEqual(rows["Z89"]["cost_cny"]["status"], "estimated")
        self.assertEqual(rows["Z89"]["cost_cny"]["amount_cny"], 0.190266)
        self.assertFalse(rows["Z89"]["cost_cny"]["calculated_now"])
        self.assertEqual(
            rows["Z57"]["cost_cny"]["status"],
            "exact_zero_no_new_model_call",
        )
        self.assertEqual(
            rows["Z98"]["cost_cny"]["status"],
            "exact_zero_no_new_model_call",
        )

        non_null_ucr = {
            row_id: row["ucr"] for row_id, row in rows.items() if row["ucr"] is not None
        }
        self.assertEqual(set(non_null_ucr), {"Z89"})
        self.assertEqual(non_null_ucr["Z89"]["numerator"], 10)
        self.assertEqual(non_null_ucr["Z89"]["denominator"], 23)
        self.assertFalse(non_null_ucr["Z89"]["formal_score_eligible"])
        for row_id, row in rows.items():
            if row_id != "Z89":
                self.assertIsNone(row["ucr"])

    def test_high_risk_accounting_rows(self) -> None:
        rows = {row["row_id"]: row for row in self.table_b["rows"]}
        expected = {
            "retry03": (3, 3, 83621, 6, 23),
            "Z57": (0, 0, 0, 2, 14),
            "Z59-A": (5, 5, 58672, 3, 14),
            "Z68C": (3, 4, 52550, 6, 14),
            "Z70": (5, 5, 94698, 6, 14),
            "Z71": (25, 25, 157941, 6, 14),
            "Z79": (3, 4, 70611, 10, 23),
            "Z80": (3, 3, 101493, 6, 23),
            "Z83-retry13": (35, 35, 301277, 6, 23),
            "Z89": (1, 1, 37226, 10, 23),
            "Z94": (35, 35, 71084, 6, 23),
        }
        for row_id, values in expected.items():
            logical, attempts, tokens, numerator, denominator = values
            row = rows[row_id]
            self.assertEqual(row["api"]["logical_requests_started"], logical)
            self.assertEqual(row["api"]["network_attempts"], attempts)
            self.assertEqual(row["api"]["new_work_usage"]["total_tokens"], tokens)
            self.assertEqual(row["strict_score"]["numerator"], numerator)
            self.assertEqual(row["strict_score"]["denominator"], denominator)
        self.assertIsNone(rows["Z98"]["strict_score"])
        self.assertEqual(rows["Z98"]["api"]["network_attempts"], 0)
        self.assertEqual(rows["Z98"]["api"]["new_work_usage"]["total_tokens"], 0)

    def test_comparison_and_reuse_are_explicit(self) -> None:
        for row in self.table_b["rows"]:
            self.assertIn("used", row["reuse"])
            self.assertTrue(row["reuse"]["details"])
            self.assertTrue(row["comparison"]["single_variable_status"])
            self.assertIsInstance(
                row["comparison"]["known_second_variables"],
                list,
            )
            self.assertGreater(len(row["comparison"]["limitations"]), 0)
        z94 = next(row for row in self.table_b["rows"] if row["row_id"] == "Z94")
        self.assertEqual(
            z94["comparison"]["known_second_variables"],
            ["provider_channel"],
        )

    def test_markdown_source_footer_and_null_language(self) -> None:
        for name in (
            "table_a_thinking_inputs.md",
            "table_b_historical_api_rounds.md",
            "acceptance_receipt.md",
        ):
            text = self.artifacts[name].decode("utf-8")
            self.assertTrue(text.endswith("来源：Codex\n"), name)
        table_b_md = self.artifacts["table_b_historical_api_rounds.md"].decode("utf-8")
        self.assertIn("其余轮次都写 `null`", table_b_md)
        self.assertIn("约¥0.190266（estimated）", table_b_md)

    def test_double_build_and_two_output_directories_are_byte_identical(self) -> None:
        again = z99.build_artifacts(REPO_ROOT)
        self.assertEqual(self.artifacts, again)
        self.assertEqual(
            self.receipt["checks"]["deterministic_double_build"],
            "PASS_BYTE_IDENTICAL",
        )
        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = Path(first_dir)
                second = Path(second_dir)
                z99.write_artifacts(first, self.artifacts)
                z99.write_artifacts(second, again)
                self.assertEqual(
                    sorted(path.name for path in first.iterdir()),
                    sorted(path.name for path in second.iterdir()),
                )
                for name in z99.ALL_FILENAMES:
                    self.assertEqual(
                        (first / name).read_bytes(),
                        (second / name).read_bytes(),
                    )
                z99.check_artifacts(first, self.artifacts)
                z99.check_artifacts(second, again)

    def test_no_network_client_import(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", maxsplit=1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
                assert node.module is not None
                imported_roots.add(node.module.split(".", maxsplit=1)[0])
        self.assertEqual(
            imported_roots,
            {
                "argparse",
                "dataclasses",
                "hashlib",
                "json",
                "pathlib",
                "typing",
            },
        )
        for forbidden in (
            "import requests",
            "from requests",
            "urllib.request",
            "http.client",
            "subprocess",
            "__import__",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(self.receipt["model_api_calls"], 0)
        self.assertEqual(self.receipt["network_requests"], 0)


if __name__ == "__main__":
    unittest.main()
