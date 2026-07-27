from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from experiments.extraction_redesign_v02_overnight_20260725.V02_C15_pipeline_v1_20260726 import (
    v02_c15_pipeline_v1 as c15,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "extraction_redesign_v02_overnight_20260725"
    / "V02_C15_pipeline_v1_20260726"
    / "v02_c15_pipeline_v1.py"
)


class C15PipelineV1Test(unittest.TestCase):
    def test_unknown_diagnostic_label_cannot_enter_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "未登记诊断标签"):
            c15.C15ContractError("UNBOUND_FUTURE_LABEL", "不得穿透")

    def test_diagnostic_labels_bind_to_frozen_b2_codes(self) -> None:
        binding = c15.failure_code_binding()
        c15.validate_failure_code_binding(binding)
        self.assertEqual(binding["unknown_code_policy"], "REJECT")
        self.assertTrue(binding["frozen_spectrum_unchanged"])
        self.assertEqual(binding["spectrum_extension_count"], 0)
        self.assertEqual(len(binding["diagnostic_bindings"]), 5)
        self.assertEqual(
            {
                row["diagnostic_label"]: row["existing_fine_code"]
                for row in binding["diagnostic_bindings"]
            },
            {
                "PROVENANCE_SOURCE_EMPTY": "PF_BODY_EMPTY",
                "PROVENANCE_SOURCE_HASH_MISMATCH": (
                    "S6_SNAPSHOT_HASH_MISMATCH"
                ),
                "BOUNDARY_SOURCE_RANGEREVERSED": "H01_ATOMIC_BOUNDARY",
                "REPAIR_UNAUTHORIZED_FIELD_CHANGE": "S3_ENUM_INVALID",
                "MISSING_REQUIRES_CALIBRATION": (
                    "S0_BLOCK_SIZE_POLICY_MISSING"
                ),
            },
        )

    def test_s0_catalog_roundtrips_body_and_ticket(self) -> None:
        text = "甲做出决定。\n　　乙记录结果！\n"
        catalog = c15.build_source_catalog(
            run_id="TEST-RUN",
            source_id="B01-U0001",
            chapter=1,
            source_text=text,
        )
        ticket = c15.build_source_run_ticket(catalog)
        receipt = c15.validate_source_catalog(catalog, run_ticket=ticket)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            "".join(row["original_text"] for row in catalog["paragraphs"]),
            text,
        )
        self.assertEqual(
            "".join(row["original_text"] for row in catalog["sentences"]),
            text,
        )

    def test_s0_rejects_empty_reverse_and_hash_drift(self) -> None:
        with self.assertRaisesRegex(c15.C15ContractError, "正文为空"):
            c15.build_source_catalog(
                run_id="TEST-RUN",
                source_id="B01-U0001",
                chapter=1,
                source_text="",
            )
        catalog = c15.build_source_catalog(
            run_id="TEST-RUN",
            source_id="B01-U0001",
            chapter=1,
            source_text="甲完成任务。\n",
        )
        reversed_range = copy.deepcopy(catalog)
        reversed_range["paragraphs"][0]["char_end_exclusive"] = -1
        reversed_range["catalog_sha256"] = c15._sha_without_field(
            reversed_range,
            "catalog_sha256",
        )
        with self.assertRaises(c15.C15ContractError) as caught:
            c15.validate_source_catalog(reversed_range)
        self.assertEqual(
            caught.exception.failure_code,
            "H01_ATOMIC_BOUNDARY",
        )
        self.assertEqual(
            caught.exception.diagnostic_label,
            "BOUNDARY_SOURCE_RANGEREVERSED",
        )
        drifted = copy.deepcopy(catalog)
        drifted["source_body_sha256"] = "0" * 64
        drifted["catalog_sha256"] = c15._sha_without_field(
            drifted,
            "catalog_sha256",
        )
        with self.assertRaises(c15.C15ContractError) as caught:
            c15.validate_source_catalog(drifted)
        self.assertEqual(
            caught.exception.failure_code,
            "S6_SNAPSHOT_HASH_MISMATCH",
        )

    def test_s1_blocks_real_plan_until_calibration(self) -> None:
        catalog = c15.build_source_catalog(
            run_id="TEST-RUN",
            source_id="B01-U0001",
            chapter=1,
            source_text="甲完成任务。\n乙记录结果。\n",
        )
        plan = c15.build_chunk_plan(catalog, primary_ranges=None)
        receipt = c15.validate_chunk_plan(plan, catalog=catalog)
        self.assertEqual(receipt["status"], "BLOCKED_MISSING_CALIBRATION")
        self.assertEqual(plan["chunks"], [])
        self.assertEqual(
            plan["failure_codes"],
            ["S0_BLOCK_SIZE_POLICY_MISSING"],
        )
        self.assertEqual(
            plan["diagnostic_labels"],
            ["MISSING_REQUIRES_CALIBRATION"],
        )

    def test_s1_explicit_ranges_cover_once_and_context_does_not_score(self) -> None:
        text = "甲完成任务。\n乙记录结果。\n"
        catalog = c15.build_source_catalog(
            run_id="TEST-RUN",
            source_id="B01-U0001",
            chapter=1,
            source_text=text,
        )
        split_at = len("甲完成任务。\n")
        plan = c15.build_chunk_plan(
            catalog,
            primary_ranges=[(0, split_at), (split_at, len(text))],
            context_chars=2,
        )
        receipt = c15.validate_chunk_plan(plan, catalog=catalog)
        self.assertEqual(receipt["primary_coverage"], 1.0)
        self.assertEqual(receipt["duplicate_primary_owner_count"], 0)
        self.assertGreater(
            sum(len(row["visible_source_ids"]) for row in plan["chunks"]),
            len(catalog["sentences"]),
        )

    def test_s3_replays_exactly_5_plus_10_without_semantic_green(self) -> None:
        receipt = c15.replay_c2_c5()
        self.assertEqual(receipt["legacy_violation_count"], 15)
        self.assertEqual(receipt["program_backfill_string_mismatch_count"], 0)
        self.assertEqual(
            receipt["semantic_support_status"],
            "ANCHOR_SUPPORT_SEMANTIC_OPEN",
        )
        self.assertFalse(
            any(
                row["string_mismatch_after_program_backfill"]
                for row in receipt["replay_rows"]
            )
        )

    def test_model_cannot_overwrite_source_quotes(self) -> None:
        output = {
            "schema_version": "closed_anchor_alignment.v1",
            "chapter": 1,
            "events": [
                {
                    "event_id": "EV-C0001-01",
                    "event": "甲完成任务",
                    "minimal_anchor_ids": ["E0001"],
                    "source_quotes": [{"source_id": "E0001", "original_text": "伪造"}],
                    "support_obligations": [
                        {
                            "claim_span": "甲完成任务",
                            "anchor_ids": ["E0001"],
                            "combination": "all_required",
                        }
                    ],
                }
            ],
        }
        catalog = {
            "entries": [
                {
                    "anchor_id": "E0001",
                    "quote": "甲完成任务",
                    "body_start_char": 0,
                    "body_end_char_exclusive": 5,
                }
            ]
        }
        with self.assertRaises(c15.C15ContractError) as caught:
            c15.backfill_source_quotes(output, legacy_catalog=catalog)
        self.assertEqual(
            caught.exception.failure_code,
            "S3_ENUM_INVALID",
        )

    def test_s3_backfills_obligation_source_ids_not_only_event_minimum(self) -> None:
        output = {
            "schema_version": "closed_anchor_alignment.v1",
            "chapter": 1,
            "events": [
                {
                    "event_id": "EV-C0001-01",
                    "event": "甲完成任务",
                    "minimal_anchor_ids": ["E0001"],
                    "support_obligations": [
                        {
                            "claim_span": "甲完成任务",
                            "anchor_ids": ["E0002"],
                            "combination": "all_required",
                        }
                    ],
                }
            ],
        }
        catalog = {
            "entries": [
                {
                    "anchor_id": "E0001",
                    "quote": "甲",
                    "body_start_char": 0,
                    "body_end_char_exclusive": 1,
                },
                {
                    "anchor_id": "E0002",
                    "quote": "完成任务",
                    "body_start_char": 1,
                    "body_end_char_exclusive": 5,
                },
            ]
        }
        transformed, violations = c15.backfill_source_quotes(
            output,
            legacy_catalog=catalog,
        )
        self.assertEqual(violations, [])
        self.assertEqual(
            [row["source_id"] for row in transformed["events"][0]["source_quotes"]],
            ["E0001", "E0002"],
        )

    def test_s4_arm_whitelist_and_field_scope(self) -> None:
        before = {"actuality": "ACTUAL", "qualifier": "旧限定"}
        issue = {
            "issue_id": "ISSUE-01",
            "object_id": "EV-C0001-01",
            "before_object_sha256": c15.canonical_sha(before),
            "allowed_diff_paths": ["/actuality", "/qualifier"],
            "allowed_operations": ["replace_field", "replace_qualifier"],
            "allowed_fields": ["actuality", "qualifier"],
        }
        valid = {
            "issue_id": "ISSUE-01",
            "operation": "replace_field",
            "target_field": "actuality",
            "full_chunk_rewrite": False,
            "object_id": "EV-C0001-01",
            "before_object": before,
            "after_object": {
                "actuality": "PLANNED",
                "qualifier": "旧限定",
            },
        }
        self.assertEqual(
            c15.validate_patch(valid, issue=issue, arm="A_FLASH_SELF_REPAIR")[
                "status"
            ],
            "PASS",
        )
        semantic_only = {
            "issue_id": "ISSUE-01",
            "operation": "replace_qualifier",
            "target_field": "qualifier",
            "full_chunk_rewrite": False,
            "object_id": "EV-C0001-01",
            "before_object": before,
            "after_object": {
                "actuality": "ACTUAL",
                "qualifier": "新限定",
            },
        }
        with self.assertRaises(c15.C15ContractError):
            c15.validate_patch(
                semantic_only,
                issue=issue,
                arm="A_FLASH_SELF_REPAIR",
            )
        self.assertEqual(
            c15.validate_patch(
                semantic_only,
                issue=issue,
                arm="B_V4_PRO_PATCH",
            )["status"],
            "PASS",
        )
        out_of_scope = copy.deepcopy(valid)
        out_of_scope["target_field"] = "unapproved_field"
        out_of_scope["after_object"]["unapproved_field"] = "夹带"
        with self.assertRaises(c15.C15ContractError) as caught:
            c15.validate_patch(
                out_of_scope,
                issue=issue,
                arm="A_FLASH_SELF_REPAIR",
            )
        self.assertEqual(
            caught.exception.failure_code,
            "S3_ENUM_INVALID",
        )
        add_issue = {
            "issue_id": "ISSUE-02",
            "object_id": "CHUNK-B01-01",
            "before_object_sha256": c15.canonical_sha({"facts": []}),
            "allowed_diff_paths": ["/facts"],
            "fact_scope_id": "B01-A01",
            "allowed_operations": ["add_fact"],
            "allowed_fields": [],
        }
        add_patch = {
            "issue_id": "ISSUE-02",
            "operation": "add_fact",
            "fact_scope_id": "B01-A01",
            "full_chunk_rewrite": False,
            "object_id": "CHUNK-B01-01",
            "before_object": {"facts": []},
            "after_object": {"facts": [{"fact_id": "B01-A01"}]},
        }
        self.assertEqual(
            c15.validate_patch(
                add_patch,
                issue=add_issue,
                arm="B_V4_PRO_PATCH",
            )["status"],
            "PASS",
        )
        add_patch["fact_scope_id"] = "B01-A02"
        with self.assertRaises(c15.C15ContractError) as caught:
            c15.validate_patch(
                add_patch,
                issue=add_issue,
                arm="B_V4_PRO_PATCH",
            )
        self.assertEqual(
            caught.exception.failure_code,
            "S3_ENUM_INVALID",
        )

    def test_s4_rejects_payload_field_smuggled_behind_authorized_metadata(self) -> None:
        before = {"actuality": "ACTUAL"}
        issue = {
            "issue_id": "ISSUE-03",
            "object_id": "EV-C0001-03",
            "before_object_sha256": c15.canonical_sha(before),
            "allowed_diff_paths": ["/actuality"],
            "allowed_operations": ["replace_field"],
            "allowed_fields": ["actuality"],
        }
        patch = {
            "issue_id": "ISSUE-03",
            "operation": "replace_field",
            "target_field": "actuality",
            "full_chunk_rewrite": False,
            "object_id": "EV-C0001-03",
            "before_object": before,
            "after_object": {
                "actuality": "PLANNED",
                "unapproved_field": "夹带内容",
            },
        }
        with self.assertRaises(c15.C15ContractError) as caught:
            c15.validate_patch(
                patch,
                issue=issue,
                arm="A_FLASH_SELF_REPAIR",
            )
        self.assertEqual(
            caught.exception.failure_code,
            "S3_ENUM_INVALID",
        )

    def test_s4_add_and_split_fact_cannot_replace_unrelated_facts(self) -> None:
        before = {
            "facts": [
                {"fact_id": "OLD-01", "claim": "原有事实"},
                {"fact_id": "KEEP-01", "claim": "必须保留"},
            ]
        }
        add_issue = {
            "issue_id": "ISSUE-04",
            "object_id": "CHUNK-B01-04",
            "before_object_sha256": c15.canonical_sha(before),
            "allowed_diff_paths": ["/facts"],
            "fact_scope_id": "B01-A01",
            "allowed_operations": ["add_fact"],
            "allowed_fields": [],
        }
        replacement_patch = {
            "issue_id": "ISSUE-04",
            "operation": "add_fact",
            "fact_scope_id": "B01-A01",
            "full_chunk_rewrite": False,
            "object_id": "CHUNK-B01-04",
            "before_object": before,
            "after_object": {
                "facts": [
                    {"fact_id": "UNRELATED-99", "claim": "无关替换"},
                    {"fact_id": "KEEP-01", "claim": "必须保留"},
                ]
            },
        }
        with self.assertRaises(c15.C15ContractError) as caught:
            c15.validate_patch(
                replacement_patch,
                issue=add_issue,
                arm="B_V4_PRO_PATCH",
            )
        self.assertEqual(
            caught.exception.failure_code,
            "S3_ENUM_INVALID",
        )

        split_issue = {
            "issue_id": "ISSUE-05",
            "object_id": "CHUNK-B01-05",
            "before_object_sha256": c15.canonical_sha(before),
            "allowed_diff_paths": ["/facts"],
            "fact_scope_id": "OLD-01",
            "split_result_fact_ids": ["OLD-01-A", "OLD-01-B"],
            "allowed_operations": ["split_fact"],
            "allowed_fields": [],
        }
        valid_split = {
            "issue_id": "ISSUE-05",
            "operation": "split_fact",
            "fact_scope_id": "OLD-01",
            "full_chunk_rewrite": False,
            "object_id": "CHUNK-B01-05",
            "before_object": before,
            "after_object": {
                "facts": [
                    {"fact_id": "KEEP-01", "claim": "必须保留"},
                    {
                        "fact_id": "OLD-01-A",
                        "source_fact_id": "OLD-01",
                        "claim": "拆分事实甲",
                    },
                    {
                        "fact_id": "OLD-01-B",
                        "source_fact_id": "OLD-01",
                        "claim": "拆分事实乙",
                    },
                ]
            },
        }
        self.assertEqual(
            c15.validate_patch(
                valid_split,
                issue=split_issue,
                arm="B_V4_PRO_PATCH",
            )["status"],
            "PASS",
        )
        tampered_split = copy.deepcopy(valid_split)
        tampered_split["after_object"]["facts"][0]["claim"] = "偷改其他事实"
        with self.assertRaises(c15.C15ContractError):
            c15.validate_patch(
                tampered_split,
                issue=split_issue,
                arm="B_V4_PRO_PATCH",
            )

    def test_exact_duplicates_are_hints_only(self) -> None:
        hints = c15.exact_duplicate_hints(
            [
                {"fact_id": "F01", "claim": "甲完成任务"},
                {"fact_id": "F02", "claim": "甲完成任务"},
                {"fact_id": "F03", "claim": "乙记录结果"},
            ]
        )
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["action"], "HINT_ONLY_NO_AUTO_MERGE")

    def test_q3_is_18_calls_zero_retry_and_not_executable(self) -> None:
        prereg = c15.q3_preregistration()
        self.assertEqual(prereg["call_budget"]["total"], 18)
        self.assertEqual(prereg["call_budget"]["retry"], 0)
        self.assertEqual(
            prereg["models"]["arm_b"]["model"],
            "deepseek-v4-pro-202606",
        )
        self.assertFalse(prereg["network_authorization"]["execute_allowed"])
        self.assertEqual(
            prereg["execution_priority"],
            "AFTER_R1_SCOPE_EXPERIMENT",
        )
        self.assertEqual(
            prereg["superseding_correction"],
            "C15_CORRECTION_20260726_1940",
        )
        self.assertEqual(
            prereg["block_size_policy"],
            "MISSING_REQUIRES_CALIBRATION",
        )
        self.assertEqual(
            prereg["preregistration_sha256"],
            c15._sha_without_field(prereg, "preregistration_sha256"),
        )

    def test_contract_build_is_deterministic_and_zero_network(self) -> None:
        first = c15.build_contract_artifacts()
        second = c15.build_contract_artifacts()
        self.assertEqual(first, second)
        manifest = json.loads(first["manifest.json"])
        self.assertEqual(manifest["model_api_calls"], 0)
        self.assertEqual(manifest["network_requests"], 0)
        self.assertFalse(manifest["active_pipeline_changed"])

    def test_cli_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "contract"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "build",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            receipt = json.loads(completed.stdout)
            self.assertEqual(receipt["status"], "PASS_ZERO_API_ZERO_NETWORK")
            self.assertEqual(receipt["model_api_calls"], 0)
            self.assertEqual(receipt["network_requests"], 0)
            self.assertTrue((output_dir / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
