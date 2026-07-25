from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import v02_error_notebook as notebook


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "v02_error_notebook.py"
BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B4_3_error_notebook"
)


class V02ErrorNotebookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.allowlist = notebook.load_failure_allowlist()
        cls.schema = notebook.build_schema(cls.allowlist)
        cls.good = notebook.valid_example()
        cls.artifacts = notebook.build_artifacts()

    def test_b2_allowlist_is_read_only_and_complete(self) -> None:
        before = notebook.DEFAULT_FAILURE_MAP_PATH.read_bytes()
        allowlist = notebook.load_failure_allowlist()
        after = notebook.DEFAULT_FAILURE_MAP_PATH.read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(len(allowlist.fine_to_route), 69)
        self.assertEqual(
            set(allowlist.fine_to_route.values()),
            set(notebook.ROUTE_IDS),
        )
        self.assertEqual(
            allowlist.source_sha256,
            "7d609bb5b16e2ee53c58c59501cfd1d82e6db68c16818b64956440bdac07d44f",
        )
        self.assertEqual(
            allowlist.contract_hash,
            "6041b9822b3b8beea5f0d45f59f0d9276cfe7e7e31b22a370c1a71e342e69013",
        )

    def test_schema_allows_exactly_seven_fields(self) -> None:
        self.assertEqual(self.schema["$schema"], notebook.DRAFT_2020_12)
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(tuple(self.schema["properties"]), notebook.ENTRY_FIELDS)
        self.assertEqual(tuple(self.schema["required"]), notebook.ENTRY_FIELDS)
        self.assertEqual(
            tuple(self.schema["properties"]["status"]["enum"]),
            notebook.ERROR_STATUSES,
        )
        self.assertEqual(
            tuple(self.schema["properties"]["failure_route"]["enum"]),
            notebook.ROUTE_IDS,
        )
        self.assertEqual(
            len(self.schema["properties"]["failure_fine_code"]["enum"]),
            69,
        )
        self.assertEqual(len(self.schema["allOf"]), 6)
        self.assertEqual(
            {
                clause["then"]["properties"]["failure_route"]["const"]
                for clause in self.schema["allOf"]
            },
            set(notebook.ROUTE_IDS),
        )

    def test_valid_example_passes_and_invalid_counterexample_leak_stops(self) -> None:
        self.assertEqual(
            notebook.validate_entry(self.good, self.allowlist),
            self.good,
        )
        with self.assertRaisesRegex(
            notebook.LeakageRejectedError,
            "forbidden field",
        ):
            notebook.validate_entry(notebook.invalid_example(), self.allowlist)

    def test_every_b2_fine_code_accepts_only_its_registered_route(self) -> None:
        for index, (fine_code, route) in enumerate(
            self.allowlist.fine_to_route.items(),
            start=1,
        ):
            entry = copy.deepcopy(self.good)
            entry["error_candidate_id"] = f"B4-3-MAP-{index:03d}"
            entry["candidate_sha256"] = f"{index:064x}"
            entry["failure_fine_code"] = fine_code
            entry["failure_route"] = route
            validated = notebook.validate_entry(entry, self.allowlist)
            self.assertEqual(validated["failure_route"], route)

            wrong = copy.deepcopy(entry)
            wrong["failure_route"] = next(
                candidate for candidate in notebook.ROUTE_IDS if candidate != route
            )
            with self.assertRaisesRegex(
                notebook.ContractValidationError,
                "does not match",
            ):
                notebook.validate_entry(wrong, self.allowlist)

    def test_unknown_fine_code_and_truth_promotion_status_are_rejected(self) -> None:
        unknown = copy.deepcopy(self.good)
        unknown["failure_fine_code"] = "UNKNOWN_FINE_CODE"
        with self.assertRaisesRegex(
            notebook.ContractValidationError,
            "not in the B2 allowlist",
        ):
            notebook.validate_entry(unknown, self.allowlist)

        for forbidden_status in ("ACTIVE", "PASS", "GOLD", "FIXED", "FORMAL_TRUTH"):
            promoted = copy.deepcopy(self.good)
            promoted["status"] = forbidden_status
            with self.assertRaisesRegex(
                notebook.ContractValidationError,
                "cannot activate or promote",
            ):
                notebook.validate_entry(promoted, self.allowlist)

    def test_forbidden_fields_are_rejected_before_unknown_field_validation(self) -> None:
        forbidden_fields = (
            "formal_gold",
            "answer",
            "quote",
            "source_text",
            "body",
            "content",
            "corpus",
            "api_key",
            "human_judgment",
            "manual_verdict",
            "reasoning",
        )
        for field in forbidden_fields:
            changed = copy.deepcopy(self.good)
            changed[field] = "SYNTHETIC_CANARY"
            with self.subTest(field=field):
                with self.assertRaises(notebook.LeakageRejectedError):
                    notebook.validate_entry(changed, self.allowlist)

    def test_suspected_body_and_secret_values_are_rejected_without_echo(self) -> None:
        body_like = copy.deepcopy(self.good)
        body_like["error_candidate_id"] = "SYNTHETIC。CANARY"
        with self.assertRaisesRegex(
            notebook.LeakageRejectedError,
            "prose-like",
        ):
            notebook.validate_entry(body_like, self.allowlist)

        long_prose_like = copy.deepcopy(self.good)
        long_prose_like["error_candidate_id"] = "A" * 161
        with self.assertRaisesRegex(
            notebook.LeakageRejectedError,
            "free-text-like",
        ):
            notebook.validate_entry(long_prose_like, self.allowlist)

        secret_like = copy.deepcopy(self.good)
        secret_like["program_assertion"] = "sk-SYNTHETIC_CANARY_123456789"
        raw = json.dumps(secret_like).encode("utf-8")
        with self.assertRaises(notebook.LeakageRejectedError) as caught:
            notebook.load_entry_bytes(raw, self.allowlist)
        self.assertNotIn("SYNTHETIC_CANARY", str(caught.exception))

    def test_program_assertion_is_an_identifier_not_free_text(self) -> None:
        for value in (
            "assertion with prose",
            "lowercase_assertion",
            "ASSERTION\nWITH_NEWLINE",
        ):
            changed = copy.deepcopy(self.good)
            changed["program_assertion"] = value
            with self.subTest(value=value):
                with self.assertRaises(notebook.ErrorNotebookError):
                    notebook.validate_entry(changed, self.allowlist)

    def test_append_preserves_prior_bytes_and_readback_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "notebook.jsonl"
            first_receipt = notebook.append_entry(
                ledger,
                self.good,
                notebook.DEFAULT_FAILURE_MAP_PATH,
            )
            prefix = ledger.read_bytes()
            self.assertEqual(first_receipt["entry_count"], 1)

            second = copy.deepcopy(self.good)
            second["error_candidate_id"] = "B4-3-CANDIDATE-002"
            second["candidate_sha256"] = "3" * 64
            second["failure_fine_code"] = "H02_SUBJECT_MISSING_OR_WRONG"
            second["failure_route"] = "FACT"
            second["program_assertion"] = "ASSERT_SUBJECT_CHECK_FAILED"
            second["source_receipt_sha256"] = "4" * 64
            second_receipt = notebook.append_entry(
                ledger,
                second,
                notebook.DEFAULT_FAILURE_MAP_PATH,
            )
            after = ledger.read_bytes()
            self.assertTrue(after.startswith(prefix))
            self.assertGreater(len(after), len(prefix))
            self.assertEqual(second_receipt["entry_count"], 2)
            self.assertEqual(notebook.read_ledger(ledger), [self.good, second])
            self.assertEqual(
                notebook.validate_ledger(ledger)["unique_failure_identity_count"],
                2,
            )

    def test_duplicate_identity_cannot_hide_behind_status_or_receipt_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "notebook.jsonl"
            notebook.append_entry(ledger, self.good)
            before = ledger.read_bytes()

            duplicate = copy.deepcopy(self.good)
            duplicate["status"] = "QUARANTINED_ERROR_CANDIDATE"
            duplicate["source_receipt_sha256"] = "9" * 64
            with self.assertRaises(notebook.DuplicateIdentityError):
                notebook.append_entry(ledger, duplicate)
            self.assertEqual(ledger.read_bytes(), before)

    def test_candidate_id_and_sha_cannot_be_rebound(self) -> None:
        first = notebook.validate_entry(self.good, self.allowlist)

        changed_sha = copy.deepcopy(first)
        changed_sha["candidate_sha256"] = "3" * 64
        changed_sha["failure_fine_code"] = "H02_SUBJECT_MISSING_OR_WRONG"
        changed_sha["failure_route"] = "FACT"
        changed_sha["program_assertion"] = "ASSERT_SUBJECT_CHECK_FAILED"
        with self.assertRaisesRegex(
            notebook.DuplicateIdentityError,
            "error_candidate_id",
        ):
            notebook.validate_entry_sequence([first, changed_sha])

        changed_id = copy.deepcopy(first)
        changed_id["error_candidate_id"] = "B4-3-CANDIDATE-ALIAS"
        changed_id["failure_fine_code"] = "H02_SUBJECT_MISSING_OR_WRONG"
        changed_id["failure_route"] = "FACT"
        changed_id["program_assertion"] = "ASSERT_SUBJECT_CHECK_FAILED"
        with self.assertRaisesRegex(
            notebook.DuplicateIdentityError,
            "candidate SHA",
        ):
            notebook.validate_entry_sequence([first, changed_id])

    def test_corrupt_jsonl_is_rejected(self) -> None:
        line = notebook._ledger_line(self.good)
        with self.assertRaisesRegex(
            notebook.ContractValidationError,
            "incomplete final line",
        ):
            notebook.read_ledger_bytes(line.rstrip(b"\n"), self.allowlist)
        with self.assertRaisesRegex(
            notebook.ContractValidationError,
            "blank ledger lines",
        ):
            notebook.read_ledger_bytes(line + b"\n", self.allowlist)

        duplicate_key = (
            b'{"error_candidate_id":"B4-3-CANDIDATE-001",'
            b'"error_candidate_id":"B4-3-CANDIDATE-001"}'
        )
        with self.assertRaisesRegex(
            notebook.ContractValidationError,
            "duplicate JSON key",
        ):
            notebook.load_entry_bytes(duplicate_key, self.allowlist)

        with self.assertRaisesRegex(
            notebook.ContractValidationError,
            "non-finite",
        ):
            notebook.load_entry_bytes(b'{"value":NaN}', self.allowlist)

    def test_canary_rejects_every_case_without_persisting_runtime_inputs(self) -> None:
        receipt = notebook.run_canary(self.allowlist)
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["case_count"], 7)
        self.assertEqual(receipt["passed_count"], 7)
        self.assertFalse(receipt["runtime_inputs_persisted"])
        self.assertFalse(receipt["real_secret_or_novel_text_used"])
        self.assertTrue(
            all(
                case["result"] == "REJECTED_AS_EXPECTED"
                for case in receipt["cases"]
            )
        )

    def test_two_builds_and_isolated_directories_are_byte_identical(self) -> None:
        second = notebook.build_artifacts()
        self.assertEqual(self.artifacts, second)
        double_run = notebook.double_run()
        self.assertTrue(double_run["byte_identical"])
        self.assertEqual(
            double_run["pass1_tree_sha256"],
            double_run["pass2_tree_sha256"],
        )
        with tempfile.TemporaryDirectory() as first_tmp:
            with tempfile.TemporaryDirectory() as second_tmp:
                first_dir = Path(first_tmp)
                second_dir = Path(second_tmp)
                notebook.write_artifacts(first_dir, self.artifacts)
                notebook.write_artifacts(second_dir, second)
                self.assertEqual(
                    {
                        path.relative_to(first_dir).as_posix(): path.read_bytes()
                        for path in first_dir.rglob("*")
                        if path.is_file()
                    },
                    {
                        path.relative_to(second_dir).as_posix(): path.read_bytes()
                        for path in second_dir.rglob("*")
                        if path.is_file()
                    },
                )
                self.assertEqual(notebook.check_bundle(first_dir)["result"], "PASS")

    def test_checked_in_candidate_matches_deterministic_builder(self) -> None:
        self.assertEqual(
            {
                path.relative_to(BUNDLE_DIR).as_posix(): path.read_bytes()
                for path in BUNDLE_DIR.rglob("*")
                if path.is_file()
            },
            self.artifacts,
        )
        checked = notebook.check_bundle(BUNDLE_DIR)
        self.assertEqual(checked["result"], "PASS")
        manifest = json.loads((BUNDLE_DIR / "manifest.json").read_text())
        self.assertFalse(manifest["release_isolation"]["activation_allowed"])
        self.assertFalse(manifest["release_isolation"]["active_runner_connected"])
        self.assertFalse(manifest["release_isolation"]["semantic_auto_repair"])
        self.assertFalse(manifest["release_isolation"]["truth_promotion_allowed"])
        self.assertEqual(
            manifest["append_only_identity_rule"]["dedupe_key"],
            [
                "candidate_sha256",
                "failure_fine_code",
                "program_assertion",
            ],
        )

    def test_cli_build_append_read_validate_and_double_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            ledger = root / "ledger.jsonl"
            entry_path = root / "entry.json"
            entry_path.write_text(json.dumps(self.good), encoding="utf-8")

            commands = (
                ("build", "--output-dir", str(bundle)),
                ("validate-bundle", "--bundle-dir", str(bundle)),
                ("append", "--ledger", str(ledger), "--entry", str(entry_path)),
                ("read", "--ledger", str(ledger)),
                ("validate-ledger", "--ledger", str(ledger)),
                ("double-run",),
            )
            outputs = []
            for command in commands:
                completed = subprocess.run(
                    [sys.executable, str(TOOL_PATH), *command],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                outputs.append(json.loads(completed.stdout))
            self.assertEqual(outputs[0]["result"], "PASS")
            self.assertEqual(outputs[1]["result"], "PASS")
            self.assertEqual(outputs[2]["result"], "APPENDED")
            self.assertEqual(outputs[3]["entries"], [self.good])
            self.assertEqual(outputs[4]["entry_count"], 1)
            self.assertTrue(outputs[5]["byte_identical"])

    def test_tool_has_no_network_or_active_runner_import(self) -> None:
        source = TOOL_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden_roots = {"http", "requests", "socket", "urllib", "aiohttp"}
        self.assertTrue(
            forbidden_roots.isdisjoint(name.split(".")[0] for name in imported)
        )
        self.assertFalse(any("runner" in name for name in imported))


if __name__ == "__main__":
    unittest.main()
