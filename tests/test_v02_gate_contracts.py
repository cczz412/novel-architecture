from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import v02_gate_contracts as gates


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "tools" / "v02_gate_contracts.py"
BUNDLE_DIR = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "B2_gate_contract_v0.1"
)


class V02GateContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = gates.build_schemas()
        cls.valid = gates.build_valid_examples(cls.schemas)
        cls.invalid = gates.build_invalid_examples(cls.valid)
        cls.artifacts = gates.build_artifacts()
        cls.manifest = json.loads(cls.artifacts["manifest.json"])
        cls.acceptance = json.loads(cls.artifacts["acceptance_receipt.json"])

    def test_seven_schemas_use_draft_2020_12_and_are_strict(self) -> None:
        self.assertEqual(tuple(self.schemas), gates.SCHEMA_NAMES)
        self.assertEqual(len(self.schemas), 7)
        strict_nodes = 0
        for name, schema in self.schemas.items():
            self.assertEqual(schema["$schema"], gates.DRAFT_2020_12)
            strict_nodes += gates.validate_schema_document(name, schema)
        self.assertGreaterEqual(strict_nodes, 7)
        self.assertEqual(
            strict_nodes,
            self.acceptance["checks"]["strict_object_schema_nodes"],
        )

    def test_each_schema_has_one_passing_and_one_rejected_example(self) -> None:
        stats = gates.validate_examples(
            self.schemas,
            self.valid,
            self.invalid,
        )
        self.assertEqual(stats["valid_examples_passed"], 7)
        self.assertEqual(stats["invalid_examples_rejected"], 7)
        self.assertEqual(stats["unknown_field_injections_rejected"], 7)

    def test_failure_codes_have_one_complete_six_route_mapping(self) -> None:
        mapping = self.valid["failure_code_map"]
        rows = mapping["fine_codes"]
        self.assertEqual(len(rows), 69)
        self.assertEqual(len({row["fine_code"] for row in rows}), 69)
        self.assertEqual(
            {row["normalized_route"] for row in rows},
            set(gates.ROUTE_IDS),
        )
        self.assertEqual(len(mapping["routing_categories"]), 6)
        self.assertEqual(mapping["coverage"]["unmapped_codes"], [])
        self.assertEqual(mapping["coverage"]["duplicate_codes"], [])
        self.assertEqual(
            self.manifest["failure_code_coverage"],
            {
                "fine_code_count": 69,
                "route_count": 6,
                "covered_routes": list(gates.ROUTE_IDS),
                "content_hard_item_count": 12,
                "unmapped_code_count": 0,
                "duplicate_code_count": 0,
                "unknown_code_policy": "REJECT",
            },
        )

    def test_h01_h12_are_content_items_not_the_six_routes(self) -> None:
        mapping = self.valid["failure_code_map"]
        hard_items = mapping["content_hard_items"]
        self.assertEqual(
            [row["hard_item_id"] for row in hard_items],
            [f"H{index:02d}" for index in range(1, 13)],
        )
        self.assertTrue(mapping["six_routes_are_not_content_h01_h12"])
        self.assertTrue(
            set(row["hard_item_id"] for row in hard_items).isdisjoint(gates.ROUTE_IDS)
        )

    def test_unknown_fine_code_is_rejected_instead_of_routed_unknown(self) -> None:
        changed = copy.deepcopy(self.valid["failure_code_map"])
        changed["fine_codes"][0] = {
            "fine_code": "UNKNOWN_FINE_CODE",
            "source_stage": "P-1",
            "normalized_route": "STRUCTURE",
            "meaning": "不得放行。",
        }
        with self.assertRaises(gates.ContractValidationError):
            gates.validate_instance(
                "failure_code_map",
                changed,
                self.schemas["failure_code_map"],
            )
        self.assertEqual(changed["unknown_code_policy"], "REJECT")

    def test_producer_selfcheck_cannot_be_program_green(self) -> None:
        same_issuer = copy.deepcopy(self.valid["program_green_receipt"])
        same_issuer["issuer_id"] = same_issuer["producer_id"]
        with self.assertRaisesRegex(
            gates.ContractValidationError,
            "producer cannot validate itself",
        ):
            gates.validate_instance(
                "program_green_receipt",
                same_issuer,
                self.schemas["program_green_receipt"],
            )

        selfcheck_as_green = copy.deepcopy(self.valid["program_green_receipt"])
        selfcheck_as_green["producer_selfcheck_used_as_program_green"] = True
        with self.assertRaises(gates.ContractValidationError):
            gates.validate_instance(
                "program_green_receipt",
                selfcheck_as_green,
                self.schemas["program_green_receipt"],
            )
        self.assertTrue(self.valid["program_green_receipt"]["example_only"])

    def test_judge_ticket_is_unissued_red_and_cannot_fabricate_root(self) -> None:
        ticket = self.valid["judge_green_ticket"]
        self.assertEqual(ticket["format_mode"], "FORMAT_ONLY_UNISSUED")
        self.assertEqual(ticket["issuance_status"], "UNISSUED")
        self.assertEqual(ticket["trust_root_status"], "TRUST_ROOT_MISSING")
        self.assertEqual(ticket["trust_root_id"], "TRUST_ROOT_ID_MISSING")
        self.assertIsNone(ticket["signature"])
        self.assertEqual(ticket["engineering_gate"], "RED")
        self.assertFalse(ticket["activation_allowed"])
        with self.assertRaises(gates.ContractValidationError):
            gates.validate_instance(
                "judge_green_ticket",
                self.invalid["judge_green_ticket"],
                self.schemas["judge_green_ticket"],
            )
        self.assertFalse(self.manifest["release_isolation"]["judge_green_issued"])

    def test_snapshot_rejects_three_terminal_states(self) -> None:
        gates.validate_instance(
            "snapshot_receipt",
            self.valid["snapshot_receipt"],
            self.schemas["snapshot_receipt"],
        )
        with self.assertRaises(gates.ContractValidationError):
            gates.validate_instance(
                "snapshot_receipt",
                self.invalid["snapshot_receipt"],
                self.schemas["snapshot_receipt"],
            )

    def test_unknown_budget_and_block_values_are_explicit_missing(self) -> None:
        expected = {
            "T1_DEFINITION_MISSING",
            "T1_VALUE_MISSING",
            "UNIT_PRICE_MISSING",
            "K_VALUE_MISSING",
            "SMALL_BLOCK_SIZE_MISSING",
            "MEDIUM_BLOCK_SIZE_MISSING",
            "LARGE_BLOCK_SIZE_MISSING",
            "RULES_HASH_MISSING",
            "PROMPT_HASH_MISSING",
            "CANARY_HASH_MISSING",
            "FULL_CHAIN_CONTRACT_HASH_MISSING",
        }
        self.assertEqual(
            set(self.manifest["explicit_missing_values"]),
            expected,
        )
        ledger = self.valid["budget_ledger"]
        self.assertEqual(ledger["call_caps"]["normal_chapter_cap"], "B_PLUS_3")
        self.assertEqual(ledger["call_caps"]["key_chapter_cap"], "B_PLUS_5")
        self.assertEqual(
            ledger["upgrade_routing"]["denominator"],
            "FACT_PACKAGE_COUNT_MISSING",
        )
        self.assertEqual(ledger["upgrade_routing"]["u_cap"], 0.4)
        self.assertEqual(ledger["repair_ratio"]["formula"], "R <= 1.35 * T1")
        self.assertFalse(ledger["budget_ok"])
        with self.assertRaises(gates.ContractValidationError):
            gates.validate_instance(
                "budget_ledger",
                self.invalid["budget_ledger"],
                self.schemas["budget_ledger"],
            )

    def test_manifest_assigns_m01_through_m07_and_m09(self) -> None:
        modules = [row["module_id"] for row in self.manifest["module_ownership"]]
        self.assertEqual(
            modules,
            ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M09"],
        )
        self.assertEqual(
            self.manifest["candidate_status"],
            "candidate_silver_not_active",
        )
        release = self.manifest["release_isolation"]
        self.assertFalse(release["program_green_issued"])
        self.assertFalse(release["judge_green_issued"])
        self.assertFalse(release["engineering_green"])
        self.assertTrue(release["b2_schema_bundle_hash_locked"])
        self.assertFalse(release["full_chain_hash_locked"])
        self.assertFalse(release["budget_ok"])
        self.assertFalse(release["activation_allowed"])
        preflight = self.valid["preflight"]
        self.assertEqual(preflight["gate_status"], "HARD_STOP")
        self.assertEqual(
            preflight["failure_codes"],
            ["PF_CONTRACT_HASH_UNLOCKED"],
        )

    def test_two_builds_and_two_directories_are_byte_identical(self) -> None:
        second = gates.build_artifacts()
        self.assertEqual(self.artifacts, second)
        with tempfile.TemporaryDirectory() as first_tmp:
            with tempfile.TemporaryDirectory() as second_tmp:
                first_dir = Path(first_tmp)
                second_dir = Path(second_tmp)
                gates.write_artifacts(first_dir, self.artifacts)
                gates.write_artifacts(second_dir, second)
                self.assertEqual(
                    {path: (first_dir / path).read_bytes() for path in self.artifacts},
                    {path: (second_dir / path).read_bytes() for path in second},
                )
                self.assertEqual(gates.check_bundle(first_dir)["result"], "PASS")
                self.assertEqual(
                    gates.check_bundle(second_dir)["result"],
                    "PASS",
                )

    def test_cli_build_validate_and_double_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = Path(tmp) / "bundle"
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "build",
                    "--output-dir",
                    str(bundle_dir),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            validation = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "validate-bundle",
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(validation.stdout)["result"], "PASS")
            double_run = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "double-run",
                    "--bundle-dir",
                    str(bundle_dir),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(json.loads(double_run.stdout)["byte_identical"])

    def test_checked_in_candidate_matches_deterministic_builder(self) -> None:
        for relative_path, expected in self.artifacts.items():
            path = BUNDLE_DIR / relative_path
            self.assertTrue(path.is_file(), relative_path)
            self.assertEqual(path.read_bytes(), expected, relative_path)
        checked = gates.check_bundle(BUNDLE_DIR)
        self.assertEqual(checked["result"], "PASS")
        double_run_path = BUNDLE_DIR / "double_run_receipt.json"
        self.assertTrue(double_run_path.is_file())
        double_run = json.loads(double_run_path.read_text(encoding="utf-8"))
        self.assertTrue(double_run["byte_identical"])
        self.assertEqual(
            double_run["pass1_tree_sha256"], double_run["pass2_tree_sha256"]
        )
        self.assertEqual(
            double_run["pass1_tree_sha256"], double_run["target_tree_sha256"]
        )

    def test_tool_has_no_network_client_import(self) -> None:
        tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        forbidden = {
            "aiohttp",
            "httpx",
            "requests",
            "socket",
            "urllib",
            "websocket",
        }
        self.assertTrue(imported_roots.isdisjoint(forbidden))
        self.assertEqual(self.manifest["scope"]["model_api_calls"], 0)
        self.assertEqual(self.manifest["scope"]["network_requests"], 0)


if __name__ == "__main__":
    unittest.main()
