from __future__ import annotations

import copy
import inspect
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from isolation import run_git
from tools import governance_index
from tools.pipeline_common.artifacts import read_json, verify_manifest


ROOT = Path(__file__).resolve().parents[1]
V2_LEDGER = "https://app.notion.com/p/e1eb141272b24db3afd5cf95b5cfe2c6"
LEGACY_LEDGER = "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c"
QUEUE = "https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc"


def _as_v2(state: dict) -> dict:
    current, history = governance_index.state_layers(copy.deepcopy(state))
    return {
        "schema_version": governance_index.CURRENT_STATE_SCHEMA_V2,
        "snapshot_at": state["snapshot_at"],
        "authority": copy.deepcopy(state["authority"]),
        "current_execution": current,
        "historical_context": history,
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _refresh_plan_reference(plan: dict, name: str, path: Path) -> None:
    digest = governance_index.sha256_file(path)
    plan[name]["sha256"] = digest
    next(
        row
        for row in plan["bound_inputs"]
        if row["path"] == plan[name]["path"]
    )["sha256"] = digest


def _refresh_dependency_reference(
    plan: dict,
    index: int,
    path: Path,
) -> None:
    digest = governance_index.sha256_file(path)
    plan["dependencies"][index]["sha256"] = digest
    next(
        row
        for row in plan["bound_inputs"]
        if row["path"] == plan["dependencies"][index]["path"]
    )["sha256"] = digest


def _baseline_fixture(root: Path) -> dict:
    (root / "governance").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text(
        "\n".join(
            [
                f"2. **账序真源 v2（测试）**：{V2_LEDGER}",
                f"3. **LEGACY 在跑队列（测试）**：{QUEUE}",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        root / governance_index.CURRENT_STATE_PATH,
        {
            "authority": {
                "external_truth": {
                    "ledger_url": V2_LEDGER,
                    "queue_url": QUEUE,
                    "legacy_frozen_ledger_url": LEGACY_LEDGER,
                }
            }
        },
    )
    _write_json(
        root / governance_index.CONTROL_PATH,
        {
            "source_authority": {"ledger_url": V2_LEDGER, "queue_url": QUEUE},
            "run_report_pairs": [
                {
                    "name": "HISTORICAL",
                    "acceptance_authority_url": LEGACY_LEDGER,
                }
            ],
        },
    )
    _write_json(root / "governance/module_registry.json", {"schema_version": "test"})
    _write_json(root / "governance/index_manifest.json", {"schema_version": "test"})
    (root / "tools/governance_index.py").write_text("test fixture\n", encoding="utf-8")
    bindings = [
        {
            "path": relative,
            "sha256": governance_index.sha256_file(root / relative),
        }
        for relative in sorted(governance_index.RESTRUCTURE_BASELINE_REQUIRED_INPUTS)
    ]
    return {
        "contract_version": governance_index.RESTRUCTURE_BASELINE_PLAN_V1,
        "plan_id": "ROUTE-A-PLUS-BASELINE-TEST",
        "expected_head_sha": "a" * 40,
        "responsibility_window": {
            "source_system": "codex",
            "authorization_context_id": "test-context",
            "owner": "test-owner",
            "task_id": "TEST-WAVE0",
            "wave_id": "BASELINE",
            "starts_at": "2026-07-30T00:00:00+08:00",
            "expires_at": "2026-07-31T00:00:00+08:00",
            "read_allowlist": sorted(
                governance_index.RESTRUCTURE_BASELINE_FIXED_READ_SCOPES
            ),
            "write_allowlist": ["tools/governance_index.py"],
            "candidate_write_paths": ["governance/directory_registry.json"],
        },
        "historical_authority_expectations": [
            {
                "name": "HISTORICAL",
                "path": "run_report_pairs[0].acceptance_authority_url",
                "url": LEGACY_LEDGER,
            }
        ],
        "bound_inputs": bindings,
    }


def _wave_fixture(
    root: Path,
    wave_id: str = governance_index.WAVE1_DIRECTORY_REGISTRY,
) -> tuple[dict, datetime]:
    now = datetime(2026, 7, 30, 5, 0, tzinfo=timezone.utc)
    baseline_plan = _baseline_fixture(root)
    (root / ".gitignore").write_text("TEMP/\n", encoding="utf-8")
    _write_json(root / "governance/tool_registry.json", {"schema_version": "test"})
    _write_json(
        root / "governance/test_policy.json",
        {
            "full_chain_command": "python -m pytest -q",
            "lint_command": "ruff check",
        },
    )
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests/test_governance_index.py").write_text(
        "test fixture\n",
        encoding="utf-8",
    )

    baseline_plan_path = (
        root
        / "TEMP/restructure_wave_preflight/test/BASELINE_PLAN.json"
    )
    _write_json(baseline_plan_path, baseline_plan)
    baseline_receipt = governance_index._evaluate_restructure_baseline_snapshot(
        root,
        baseline_plan,
        dirty_paths=[],
        head_sha="a" * 40,
        governance_mismatch_paths=[],
        evaluated_at=now,
    )
    baseline_receipt["checks"].append(
        {
            "check_id": "live_snapshot_stable",
            "passed": True,
            "evidence": {"fixture": True},
        }
    )
    baseline_path = (
        root
        / "TEMP/restructure_wave_preflight/test/BASELINE_RECEIPT.json"
    )
    _write_json(baseline_path, baseline_receipt)

    decision_ticket = {
        "contract_version": governance_index.RESTRUCTURE_DECISION_TICKET_V1,
        "ticket_id": "S0-DECISIONS-TEST",
        "authority": "CZ",
        "authorization_context_id": "test-context",
        "evidence_class": "same_task_human_readback",
        "human_readback": {
            "required": True,
            "confirmed": True,
            "cryptographic_proof": False,
        },
        "selected_route": "S0",
        "selected_scope": [
            governance_index.WAVE1_DIRECTORY_REGISTRY,
            governance_index.S0_MATERIALIZE_ONLY,
        ],
        "source_messages": [
            {
                "text": "按s0",
                "sha256": governance_index._sha256_text("按s0"),
            },
            {
                "text": "S-01-A",
                "sha256": governance_index._sha256_text("S-01-A"),
            },
        ],
        "decisions": {
            decision_id: {"status": status, "value": value}
            for decision_id, (status, value) in (
                governance_index.S0_DECISION_VALUES.items()
            )
        },
        "authorization_boundary": {
            "authorizes_wave_without_second_level_pass": False,
            "authorizes_notion_write": False,
            "authorizes_model_api": False,
            "authorizes_preflight": False,
            "authorizes_external_removal": False,
        },
    }
    decision_path = (
        root
        / "TEMP/restructure_wave_preflight/test/DECISION_TICKET.json"
    )
    _write_json(decision_path, decision_ticket)

    candidate_paths = list(
        governance_index.RESTRUCTURE_WAVE_SPECS[wave_id]["candidate_write_paths"]
    )
    lock_request = {
        "contract_version": governance_index.RESTRUCTURE_WAVE_LOCK_REQUEST_V1,
        "lock_id": f"{wave_id}-LOCK-TEST",
        "scope": wave_id,
        "holder": "test-owner",
        "authorization_context_id": "test-context",
        "expected_head_sha": "a" * 40,
        "starts_at": "2026-07-30T00:00:00+08:00",
        "expires_at": "2026-07-31T00:00:00+08:00",
        "candidate_write_paths": candidate_paths,
    }
    lock_path = (
        root
        / "TEMP/restructure_wave_preflight/locks/"
        f"{wave_id}.lock.json"
    )
    governance_index._acquire_restructure_wave_lock_snapshot(
        root,
        lock_request,
        output_path=lock_path.relative_to(root),
        head_sha="a" * 40,
        acquired_at=now,
    )

    impact = {
        "contract_version": governance_index.RESTRUCTURE_TEST_IMPACT_V1,
        "wave_id": wave_id,
        "route": "S0",
        "head_sha": "a" * 40,
        "authorization_context_id": "test-context",
        "classification": "full_chain_required",
        "planned_changed_paths": candidate_paths,
        "pre_start_evidence": {
            "governance_check": "PASS",
            "ruff_check": "PASS",
            "full_suite": {
                "status": "KNOWN_FAILURE_SET_UNCHANGED",
                "passed": 100,
                "failed": 1,
                "xfailed": 0,
                "subtests_passed": 0,
                "new_failure_count": 0,
                "known_failure_nodeids": ["tests/test_known.py::test_known"],
            },
        },
        "required_after_change_commands": [
            "python -m pytest -q",
            "ruff check",
            "python3 tools/governance_index.py --check",
        ],
    }
    impact_path = (
        root
        / "TEMP/restructure_wave_preflight/test/TEST_IMPACT.json"
    )
    _write_json(impact_path, impact)

    references = {
        "baseline_plan": {
            "path": baseline_plan_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(baseline_plan_path),
        },
        "baseline_receipt": {
            "path": baseline_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(baseline_path),
        },
        "decision_ticket": {
            "path": decision_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(decision_path),
        },
        "conflict_lock": {
            "path": lock_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(lock_path),
        },
        "test_impact": {
            "path": impact_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(impact_path),
        },
    }
    dependencies = []
    if wave_id == governance_index.S0_MATERIALIZE_ONLY:
        wave1_paths = list(
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE1_DIRECTORY_REGISTRY
            ]["candidate_write_paths"]
        )
        for relative in wave1_paths:
            output_path = root / relative
            if not output_path.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("wave1 fixture\n", encoding="utf-8")
        wave1_outputs = [
            {
                "path": relative,
                "sha256": governance_index.sha256_file(root / relative),
            }
            for relative in wave1_paths
        ]
        wave1_required_paths = set(
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE1_DIRECTORY_REGISTRY
            ]["required_inputs"]
        ) | {
            reference["path"] for reference in references.values()
        }
        wave1_plan = {
            "contract_version": governance_index.RESTRUCTURE_WAVE_PLAN_V1,
            "plan_id": "S0-WAVE1-SOURCE-TEST",
            "route": "S0",
            "wave_id": governance_index.WAVE1_DIRECTORY_REGISTRY,
            "expected_head_sha": "c" * 40,
            "expected_baseline_plan_id": baseline_receipt["plan_id"],
            "expected_decision_ticket_id": decision_ticket["ticket_id"],
            "expected_lock_id": lock_request["lock_id"],
            **copy.deepcopy(references),
            "responsibility_window": {
                "source_system": "codex",
                "authorization_context_id": "test-context",
                "owner": "test-owner",
                "task_id": "TEST-S0-WAVE1-SOURCE",
                "wave_id": governance_index.WAVE1_DIRECTORY_REGISTRY,
                "starts_at": "2026-07-30T00:00:00+08:00",
                "expires_at": "2026-07-31T00:00:00+08:00",
                "read_allowlist": sorted(
                    governance_index.RESTRUCTURE_WAVE_FIXED_READ_SCOPES
                ),
                "candidate_write_paths": wave1_paths,
            },
            "capability_limits": copy.deepcopy(
                governance_index.RESTRUCTURE_WAVE_SPECS[
                    governance_index.WAVE1_DIRECTORY_REGISTRY
                ]["capability_limits"]
            ),
            "bound_inputs": [
                {
                    "path": path,
                    "sha256": governance_index.sha256_file(root / path),
                    "role": f"wave1_input_{index:02d}",
                }
                for index, path in enumerate(
                    sorted(wave1_required_paths),
                    start=1,
                )
            ],
            "dependencies": [],
        }
        normalized_wave1_plan = governance_index._wave_plan(
            copy.deepcopy(wave1_plan)
        )
        wave1_plan_sha = governance_index._canonical_json_sha256(
            normalized_wave1_plan
        )
        wave1_plan_path = (
            root
            / "TEMP/restructure_wave_preflight/test/WAVE1_WAVE_PLAN.json"
        )
        _write_json(wave1_plan_path, wave1_plan)
        wave_receipt = {
            "contract_version": governance_index.RESTRUCTURE_WAVE_RECEIPT_V1,
            "plan_id": "S0-WAVE1-SOURCE-TEST",
            "plan_content_sha256": wave1_plan_sha,
            "status": "PASS",
            "blockers": [],
            "head_sha": "c" * 40,
            "route": "S0",
            "wave_id": governance_index.WAVE1_DIRECTORY_REGISTRY,
            "responsibility_window": {
                "authorization_context_id": "test-context",
            },
            "authorization_boundary": {
                "authorizes_wave": False,
                "mechanical_preconditions_pass": True,
                "requires_same_task_human_readback": True,
                "eligible_wave_id": (
                    governance_index.WAVE1_DIRECTORY_REGISTRY
                ),
                "eligible_write_paths": wave1_paths,
            },
            "checks": [
                {
                    "check_id": check_id,
                    "passed": True,
                    "evidence": {"fixture": True},
                }
                for check_id in (
                    "responsibility_window_time",
                    "governance_generated_green",
                    "head_frozen",
                    "wave_scope_exact",
                    "baseline_receipt_current",
                    "decision_ticket_exact",
                    "conflict_lock_active",
                    "test_impact_complete",
                    "bound_input_sha",
                    "read_allowlist_complete",
                    "candidate_write_paths_disjoint_from_dirty",
                    "wave_dependencies_satisfied",
                    "live_snapshot_stable",
                )
            ],
        }
        wave_receipt_path = (
            root
            / "TEMP/restructure_wave_preflight/test/WAVE1_WAVE_RECEIPT.json"
        )
        _write_json(wave_receipt_path, wave_receipt)
        completion = {
            "contract_version": governance_index.RESTRUCTURE_WAVE_COMPLETION_V1,
            "wave_id": governance_index.WAVE1_DIRECTORY_REGISTRY,
            "status": "PASS",
            "head_sha": "a" * 40,
            "pre_wave_head_sha": "c" * 40,
            "authorization_context_id": "test-context",
            "wave_plan_content_sha256": wave1_plan_sha,
            "wave_plan": {
                "path": wave1_plan_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(wave1_plan_path),
            },
            "wave_receipt": {
                "path": wave_receipt_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(wave_receipt_path),
            },
            "outputs": wave1_outputs,
            "output_manifest_sha256": (
                governance_index._canonical_json_sha256(wave1_outputs)
            ),
        }
        completion_path = (
            root
            / "TEMP/restructure_wave_preflight/test/WAVE1_COMPLETION.json"
        )
        _write_json(completion_path, completion)
        dependencies = [
            {
                "path": completion_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(completion_path),
                "wave_id": governance_index.WAVE1_DIRECTORY_REGISTRY,
            }
        ]

    required_paths = set(
        governance_index.RESTRUCTURE_WAVE_SPECS[wave_id]["required_inputs"]
    ) | {
        reference["path"] for reference in references.values()
    } | {
        dependency["path"] for dependency in dependencies
    }
    bindings = [
        {
            "path": path,
            "sha256": governance_index.sha256_file(root / path),
            "role": f"input_{index:02d}",
        }
        for index, path in enumerate(sorted(required_paths), start=1)
    ]
    plan = {
        "contract_version": governance_index.RESTRUCTURE_WAVE_PLAN_V1,
        "plan_id": f"S0-{wave_id}-TEST",
        "route": "S0",
        "wave_id": wave_id,
        "expected_head_sha": "a" * 40,
        "expected_baseline_plan_id": baseline_receipt["plan_id"],
        "expected_decision_ticket_id": decision_ticket["ticket_id"],
        "expected_lock_id": lock_request["lock_id"],
        **references,
        "responsibility_window": {
            "source_system": "codex",
            "authorization_context_id": "test-context",
            "owner": "test-owner",
            "task_id": f"TEST-S0-{wave_id}",
            "wave_id": wave_id,
            "starts_at": "2026-07-30T00:00:00+08:00",
            "expires_at": "2026-07-31T00:00:00+08:00",
            "read_allowlist": sorted(
                governance_index.RESTRUCTURE_WAVE_FIXED_READ_SCOPES
            ),
            "candidate_write_paths": candidate_paths,
        },
        "capability_limits": copy.deepcopy(
            governance_index.RESTRUCTURE_WAVE_SPECS[wave_id][
                "capability_limits"
            ]
        ),
        "bound_inputs": bindings,
        "dependencies": dependencies,
    }
    return plan, now


def _wave5_fixture(
    parent: Path,
) -> tuple[Path, dict, datetime, Path]:
    parent = parent.resolve()
    root = parent / "novel-repository"
    root.mkdir()
    now = datetime(2026, 7, 30, 15, 30, tzinfo=timezone.utc)
    context_id = "019fa2e0-08a5-7110-b263-a183b0230f3c"
    baseline_plan = _baseline_fixture(root)
    baseline_plan["responsibility_window"]["candidate_write_paths"] = list(
        governance_index.WAVE5_CANDIDATE_WRITE_PATHS
    )
    baseline_plan["responsibility_window"][
        "authorization_context_id"
    ] = context_id

    (root / ".gitignore").write_text("TEMP/\n", encoding="utf-8")
    for relative in (
        "config/README.md",
        "governance/README.md",
        "tests/README.md",
        "tools/README.md",
        "tests/test_governance_index.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative} fixture\n", encoding="utf-8")
    for relative in (
        "governance/directory_registry.json",
        "governance/test_policy.json",
        "governance/tool_registry.json",
    ):
        payload = {"schema_version": "test"}
        if relative == "governance/test_policy.json":
            payload.update(
                {
                    "full_chain_command": "python -m pytest -q",
                    "lint_command": "ruff check",
                }
            )
        _write_json(root / relative, payload)

    s0_ticket = {
        "contract_version": governance_index.RESTRUCTURE_DECISION_TICKET_V1,
        "ticket_id": "S0-DECISIONS-CZ-20260730-01",
        "authority": "CZ",
        "authorization_context_id": context_id,
        "evidence_class": "same_task_human_readback",
        "human_readback": {
            "required": True,
            "confirmed": True,
            "cryptographic_proof": False,
        },
        "selected_route": "S0",
        "selected_scope": [
            governance_index.WAVE1_DIRECTORY_REGISTRY,
            governance_index.S0_MATERIALIZE_ONLY,
        ],
        "source_messages": [
            {
                "text": "按s0",
                "sha256": governance_index._sha256_text("按s0"),
            },
            {
                "text": "S-01-A",
                "sha256": governance_index._sha256_text("S-01-A"),
            },
        ],
        "decisions": {
            decision_id: {"status": status, "value": value}
            for decision_id, (status, value) in (
                governance_index.S0_DECISION_VALUES.items()
            )
        },
        "authorization_boundary": {
            "authorizes_wave_without_second_level_pass": False,
            "authorizes_notion_write": False,
            "authorizes_model_api": False,
            "authorizes_preflight": False,
            "authorizes_external_removal": False,
        },
    }
    s0_path = (
        root
        / "TEMP/restructure_wave_preflight/"
        "route-a-plus-s0-20260730/"
        "S0_DECISION_TICKET_20260730.json"
    )
    s0_path.parent.mkdir(parents=True, exist_ok=True)
    s0_path.write_text(
        json.dumps(s0_ticket, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    external_root = parent / f"{root.name}_外置仓"
    external_sources = []
    for manifest_spec in governance_index.WAVE5_EXTERNAL_MANIFESTS:
        batch_root = external_root / manifest_spec["batch_relative_path"]
        batch_root.mkdir(parents=True)
        entries = [
            {"path": f"item-{index:03d}"}
            for index in range(manifest_spec["expected_entries"])
        ]
        payload = {
            "entries": entries,
            "entry_count": manifest_spec["expected_entries"],
        }
        manifest_path = batch_root / "MANIFEST.json"
        _write_json(manifest_path, payload)
        external_sources.append(
            {
                **copy.deepcopy(manifest_spec),
                "expected_sha256": governance_index.sha256_file(
                    manifest_path
                ),
            }
        )

    reference_paths = governance_index.WAVE5_REQUIRED_REFERENCE_PATHS
    baseline_plan_path = root / reference_paths["baseline_plan"]
    _write_json(baseline_plan_path, baseline_plan)
    baseline_receipt = governance_index._evaluate_restructure_baseline_snapshot(
        root,
        baseline_plan,
        dirty_paths=[],
        head_sha="a" * 40,
        governance_mismatch_paths=[],
        evaluated_at=now,
    )
    baseline_receipt["checks"].append(
        {
            "check_id": "live_snapshot_stable",
            "passed": True,
            "evidence": {"fixture": True},
        }
    )
    baseline_path = root / reference_paths["baseline_receipt"]
    _write_json(baseline_path, baseline_receipt)

    decision_ticket = {
        "contract_version": (
            governance_index.RESTRUCTURE_WAVE5_AUTHORIZATION_V1
        ),
        "ticket_id": "WAVE5-AUTHORIZATION-TEST",
        "ticket_kind": "wave5_gate_and_scanner_authorization",
        "authority": "CZ",
        "authorization_context_id": context_id,
        "evidence_class": "same_task_human_readback",
        "human_readback": {
            "required": True,
            "confirmed": True,
            "cryptographic_proof": False,
        },
        "selected_route": "A_PLUS_EXTERNAL_READONLY",
        "selected_scope": [
            governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY
        ],
        "source_messages": [
            {
                "text": governance_index.WAVE5_AUTHORIZATION_SOURCE_TEXT,
                "sha256": governance_index._sha256_text(
                    governance_index.WAVE5_AUTHORIZATION_SOURCE_TEXT
                ),
            }
        ],
        "decisions": {
            decision_id: {"status": status, "value": value}
            for decision_id, (status, value) in (
                governance_index.WAVE5_AUTHORIZATION_DECISION_VALUES.items()
            )
        },
        "external_root_identity": governance_index.WAVE5_EXTERNAL_ROOT_ID,
        "external_sources": external_sources,
        "upstream_decision": {
            "path": s0_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(s0_path),
        },
        "eligibility_capability_ceiling": copy.deepcopy(
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY
            ]["capability_limits"]
        ),
        "authorization_boundary": {
            "authorizes_gate_extension": True,
            "authorizes_read_only_scanner_construction_after_mechanical_pass": True,
            "requires_additional_construction_confirmation": False,
            "authorizes_manifest_rewrite": False,
            "authorizes_external_content_traversal": False,
            "authorizes_physical_move": False,
            "authorizes_delete": False,
            "authorizes_write_stub": False,
            "authorizes_restore_pass": False,
            "authorizes_network": False,
            "authorizes_credential_read": False,
            "authorizes_request_send": False,
            "authorizes_model_api": False,
            "authorizes_notion_write": False,
            "authorizes_external_removal": False,
        },
    }
    decision_path = root / reference_paths["decision_ticket"]
    _write_json(decision_path, decision_ticket)

    candidate_paths = list(governance_index.WAVE5_CANDIDATE_WRITE_PATHS)
    lock_request = {
        "contract_version": governance_index.RESTRUCTURE_WAVE_LOCK_REQUEST_V1,
        "lock_id": "WAVE5-LOCK-TEST",
        "scope": governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY,
        "holder": "test-owner",
        "authorization_context_id": context_id,
        "expected_head_sha": "a" * 40,
        "starts_at": "2026-07-30T00:00:00+08:00",
        "expires_at": "2026-07-31T00:00:00+08:00",
        "candidate_write_paths": candidate_paths,
    }
    lock_path = root / reference_paths["conflict_lock"]
    governance_index._acquire_restructure_wave_lock_snapshot(
        root,
        lock_request,
        output_path=lock_path.relative_to(root),
        head_sha="a" * 40,
        acquired_at=now,
    )

    impact = {
        "contract_version": governance_index.RESTRUCTURE_TEST_IMPACT_V1,
        "wave_id": governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY,
        "route": "A_PLUS_EXTERNAL_READONLY",
        "head_sha": "a" * 40,
        "authorization_context_id": context_id,
        "classification": "full_chain_required",
        "planned_changed_paths": candidate_paths,
        "pre_start_evidence": {
            "governance_check": "PASS",
            "ruff_check": "PASS",
            "full_suite": {
                "status": "KNOWN_FAILURE_SET_UNCHANGED",
                "passed": 100,
                "failed": 1,
                "xfailed": 0,
                "subtests_passed": 0,
                "new_failure_count": 0,
                "known_failure_nodeids": ["tests/test_known.py::test_known"],
            },
        },
        "required_after_change_commands": [
            "python -m pytest -q",
            "ruff check",
            "python3 tools/governance_index.py --check",
        ],
    }
    impact_path = root / reference_paths["test_impact"]
    _write_json(impact_path, impact)

    references = {
        name: {
            "path": path,
            "sha256": governance_index.sha256_file(root / path),
        }
        for name, path in reference_paths.items()
    }
    required_paths = set(
        governance_index.WAVE5_REQUIRED_INPUTS
    ) | {
        row["path"] for row in references.values()
    }
    bindings = [
        {
            "path": path,
            "sha256": governance_index.sha256_file(root / path),
            "role": f"wave5_input_{index:02d}",
        }
        for index, path in enumerate(sorted(required_paths), start=1)
    ]
    plan = {
        "contract_version": governance_index.RESTRUCTURE_WAVE_PLAN_V1,
        "plan_id": "WAVE5-READONLY-TEST",
        "route": "A_PLUS_EXTERNAL_READONLY",
        "wave_id": governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY,
        "expected_head_sha": "a" * 40,
        "expected_baseline_plan_id": baseline_receipt["plan_id"],
        "expected_decision_ticket_id": decision_ticket["ticket_id"],
        "expected_lock_id": lock_request["lock_id"],
        **references,
        "responsibility_window": {
            "source_system": "codex",
            "authorization_context_id": context_id,
            "owner": "test-owner",
            "task_id": "TEST-WAVE5",
            "wave_id": governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY,
            "starts_at": "2026-07-30T00:00:00+08:00",
            "expires_at": "2026-07-31T00:00:00+08:00",
            "read_allowlist": list(
                governance_index.WAVE5_REQUIRED_READ_SCOPES
            ),
            "candidate_write_paths": candidate_paths,
        },
        "capability_limits": copy.deepcopy(
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY
            ]["capability_limits"]
        ),
        "bound_inputs": bindings,
        "dependencies": [],
    }
    return root, plan, now, external_root


def _evaluate_s0_fixture(
    root: Path,
    plan: dict,
    now: datetime,
    *,
    changes: list[dict[str, str]] | None = None,
) -> dict:
    git_changes = changes or [
        {
            "status": "A",
            "path": path,
        }
        for path in governance_index.RESTRUCTURE_WAVE_SPECS[
            governance_index.WAVE1_DIRECTORY_REGISTRY
        ]["candidate_write_paths"]
    ]
    with (
        patch.object(governance_index, "git_head", return_value="a" * 40),
        patch.object(governance_index, "git_is_ancestor", return_value=True),
        patch.object(
            governance_index,
            "git_name_status_between",
            return_value=git_changes,
        ),
    ):
        return governance_index._evaluate_restructure_wave_snapshot(
            root,
            plan,
            dirty_paths=[],
            head_sha="a" * 40,
            governance_mismatch_paths=[],
            evaluated_at=now,
        )


def _git(root: Path, *args: str) -> str:
    return run_git(*args, cwd=root, check=True, text=True).stdout.strip()


def _completion_v2_fixture(
    root: Path,
) -> tuple[dict, dict, Path, Path]:
    plan, _ = _wave_fixture(root, governance_index.S0_MATERIALIZE_ONLY)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Governance Tests")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "pre wave")
    pre_commit = _git(root, "rev-parse", "HEAD")

    plan["expected_head_sha"] = pre_commit
    plan_path = (
        root
        / "TEMP/restructure_wave_preflight/test/S0_COMPLETION_SOURCE_PLAN.json"
    )
    _write_json(plan_path, plan)
    normalized_plan = governance_index._wave_plan(copy.deepcopy(plan))
    plan_sha = governance_index._canonical_json_sha256(normalized_plan)
    source_receipt = {
        "contract_version": governance_index.RESTRUCTURE_WAVE_RECEIPT_V1,
        "plan_id": normalized_plan["plan_id"],
        "plan_content_sha256": plan_sha,
        "status": "PASS",
        "blockers": [],
        "head_sha": pre_commit,
        "route": "S0",
        "wave_id": governance_index.S0_MATERIALIZE_ONLY,
        "responsibility_window": copy.deepcopy(
            normalized_plan["responsibility_window"]
        ),
        "authorization_boundary": {
            "authorizes_wave": False,
            "mechanical_preconditions_pass": True,
            "requires_same_task_human_readback": True,
            "eligible_wave_id": governance_index.S0_MATERIALIZE_ONLY,
            "eligible_write_paths": list(
                governance_index.RESTRUCTURE_WAVE_SPECS[
                    governance_index.S0_MATERIALIZE_ONLY
                ]["candidate_write_paths"]
            ),
        },
        "checks": [
            {"check_id": check_id, "passed": True, "evidence": {"fixture": True}}
            for check_id in (
                "responsibility_window_time",
                "governance_generated_green",
                "head_frozen",
                "wave_scope_exact",
                "baseline_receipt_current",
                "decision_ticket_exact",
                "conflict_lock_active",
                "test_impact_complete",
                "bound_input_sha",
                "read_allowlist_complete",
                "candidate_write_paths_disjoint_from_dirty",
                "wave_dependencies_satisfied",
                "live_snapshot_stable",
            )
        ],
    }
    source_receipt_path = (
        root
        / "TEMP/restructure_wave_preflight/test/S0_COMPLETION_SOURCE_RECEIPT.json"
    )
    _write_json(source_receipt_path, source_receipt)

    output_path = root / "tools/experiment_workspace.py"
    output_path.write_text("print('historical blob')\n", encoding="utf-8")
    _write_json(
        root / "governance/tool_registry.json",
        {"schema_version": "test", "s0_registered": True},
    )
    _git(
        root,
        "add",
        "governance/tool_registry.json",
        "tools/experiment_workspace.py",
    )
    _git(root, "commit", "-qm", "complete s0")
    post_commit = _git(root, "rev-parse", "HEAD")

    request = {
        "contract_version": (
            governance_index.RESTRUCTURE_WAVE_COMPLETION_REQUEST_V2
        ),
        "completion_id": "S0-COMPLETION-V2-TEST",
        "wave_id": governance_index.S0_MATERIALIZE_ONLY,
        "authorization_context_id": "test-context",
        "pre_commit_sha": pre_commit,
        "post_commit_sha": post_commit,
        "wave_plan": {
            "path": plan_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(plan_path),
        },
        "wave_receipt": {
            "path": source_receipt_path.relative_to(root).as_posix(),
            "sha256": governance_index.sha256_file(source_receipt_path),
        },
    }
    receipt = governance_index.evaluate_restructure_wave_completion_v2(
        root,
        request,
    )
    return request, receipt, plan_path, source_receipt_path


class GovernanceIndexTests(unittest.TestCase):
    def test_experiment_index_only_lists_registered_directories(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiments = root / "experiments"
            experiments.mkdir()
            for name in (
                "z_unregistered",
                "_template",
                "a_registered",
                "m_unregistered",
            ):
                (experiments / name).mkdir()
            (experiments / "a_registered" / "experiment.json").write_text(
                json.dumps(
                    {
                        "experiment_id": "EXP-A",
                        "status": "trial",
                        "summary": "已登记样例",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (experiments / "_template" / "experiment.json").write_text(
                json.dumps(
                    {
                        "experiment_id": "TEMPLATE",
                        "status": "template",
                        "summary": "不得进入索引",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            registered = governance_index.discover_registered_experiment_files(root)
            self.assertEqual(
                [path.parent.name for path in registered],
                ["a_registered"],
            )

            first = governance_index.render_experiments_index(root)
            second = governance_index.render_experiments_index(root)
            self.assertEqual(first, second)
            self.assertIn("## 当前登记", first)
            self.assertIn("| EXP-A | trial | `experiments/a_registered`", first)
            self.assertIn("未登记的本地候选与证据目录不写进生成页", first)
            self.assertNotIn("m_unregistered", first)
            self.assertNotIn("z_unregistered", first)
            self.assertNotIn("TEMPLATE", first)
            self.assertNotIn("_template", first)

    def test_registry_has_all_modules_and_only_three_states(self) -> None:
        source = read_json(ROOT / governance_index.REGISTRY_SOURCE_PATH)
        registry = governance_index.materialize_registry(ROOT, source)
        ids = {row["module_id"] for row in registry["modules"]}
        self.assertEqual(ids, {f"M{number:02d}" for number in range(12)})
        self.assertEqual(
            {row["status"] for row in registry["modules"]},
            {"可用", "在改", "试验"},
        )
        for row in registry["modules"]:
            self.assertTrue(row["source_refs"])
            self.assertTrue(all(ref["exists"] for ref in row["source_refs"]))

    def test_refresh_is_reproducible_and_manifest_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first)
            second_root = Path(second)
            first_manifest = governance_index.refresh(ROOT, first_root)
            second_manifest = governance_index.refresh(ROOT, second_root)
            self.assertEqual(first_manifest, second_manifest)
            self.assertTrue(verify_manifest(first_root, first_manifest["outputs"])["passed"])
            for relative in governance_index.GENERATED_PATHS + ["governance/index_manifest.json"]:
                self.assertEqual(
                    (first_root / relative).read_bytes(),
                    (second_root / relative).read_bytes(),
                    relative,
                )

    def test_current_state_and_route_registry_are_single_machine_sources(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        state = read_json(ROOT / governance_index.CURRENT_STATE_PATH)
        routes = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        governance_index.validate_control_plane(ROOT, control)
        governance_index.validate_current_state(ROOT, state)
        governance_index.validate_route_registry(ROOT, routes, state)

        current, history = governance_index.state_layers(state)
        self.assertNotIn("current_task", control)
        self.assertEqual(control["current_state_path"], governance_index.CURRENT_STATE_PATH)
        task = current["task"]
        for key in ("task_id", "label", "status", "status_label"):
            self.assertIsInstance(task.get(key), str)
            self.assertTrue(task[key].strip(), key)
        self.assertEqual(
            state["authority"]["external_truth"]["ledger_url"],
            "https://github.com/cczz412/novel-architecture/blob/main/governance/START_HERE.md",
        )
        self.assertEqual(
            state["authority"]["external_truth"]["legacy_frozen_ledger_url"],
            "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c",
        )
        self.assertEqual(
            state["authority"]["external_truth"]["queue_url"],
            "https://github.com/cczz412/novel-architecture/issues",
        )
        self.assertEqual(
            control["source_authority"]["ledger_url"],
            state["authority"]["external_truth"]["ledger_url"],
        )
        self.assertEqual(
            control["source_authority"]["queue_url"],
            state["authority"]["external_truth"]["queue_url"],
        )
        self.assertEqual(
            control["formal_gold_registry"]["path"],
            "config/gold/formal_gold_registry.json",
        )
        self.assertEqual(control["formal_gold_registry"]["entry_total"], 6)
        self.assertTrue(
            any(
                row["name"] == "第93道续令②五本v1.3修订候选"
                for row in control["silver_candidates"]
            )
        )
        self.assertTrue(
            any(
                row["name"] == "第93道续令②五本金标候选修订"
                for row in control["run_report_pairs"]
            )
        )
        self.assertTrue(
            any(
                row["name"] == "第93道续令③五本结构层金标v1.3转正"
                for row in control["run_report_pairs"]
            )
        )
        self.assertTrue(
            any(
                row["issue_id"] == "Z93-X01-GOLD-C0003-07-N01-ANCHOR-ISSUE-001"
                and row["status"] == "deferred_by_cz_choice_a_to_z92_anchor_gate"
                for row in history["issue_ledger"]
            )
        )
        self.assertEqual(
            history["legacy_mainline"]["latest_authorization"]["status"],
            "executed_hard_stop",
        )
        self.assertTrue(
            history["legacy_mainline"]["latest_authorization"]["local_process_observed"]
        )
        self.assertEqual(
            history["legacy_mainline"]["z85_gate"]["status"],
            "completed_before_retry06",
        )
        self.assertTrue(
            any(
                row["task_id"] == "Z84-repo-hygiene" and row["status"] == "accepted"
                for row in history["accepted_steps"]
            )
        )
        self.assertTrue(
            any(
                row["task_id"] == "Z93-five-formal-gold-promotion"
                and row["status"] == "accepted_full_chain_closed"
                and row["formal_gold_entry_total"] == 6
                for row in history["accepted_steps"]
            )
        )
        run_states = {row["run_id"]: row for row in history["archived_run_states"]}
        z89 = run_states["Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723"]
        self.assertEqual(z89["effective_status"], "candidate_silver_scored_callback_returned")
        self.assertEqual(z89["strict_hit"], 10)
        self.assertEqual(z89["effective_recall"], 20)
        self.assertEqual(z89["surface_coverage"], 23)
        original = run_states["Z83_X01_v3程序侧治法_三章复验_v1.0_20260722"]
        self.assertTrue(original["authoritative_ticket"].endswith("/main/hard_stop.json"))
        retry = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry01"
        ]
        self.assertIn("未找到", retry["evidence_gap"])
        retry04 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry04"
        ]
        self.assertEqual(retry04["effective_status"], "inspector_hard_stop_quote_drift")
        self.assertEqual(retry04["retry04_new_inspector_network_attempts"], 1)
        self.assertEqual(retry04["accepted_inspector_logical_results"], 0)
        retry05 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry05"
        ]
        self.assertEqual(
            retry05["effective_status"],
            "inspector_hard_stop_quote_truncation",
        )
        self.assertEqual(retry05["retry05_new_inspector_network_attempts"], 2)
        self.assertEqual(retry05["accepted_inspector_logical_results"], 1)
        self.assertEqual(retry05["chapter_19_inspector_calls"], 0)
        retry06 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry06"
        ]
        self.assertEqual(
            retry06["effective_status"],
            "inspector_hard_stop_true_non_substring",
        )
        self.assertEqual(retry06["retry06_new_inspector_network_attempts"], 1)
        self.assertEqual(retry06["accepted_inspector_logical_results"], 0)
        self.assertEqual(retry06["chapter_19_inspector_calls"], 0)
        retry08 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry08"
        ]
        self.assertEqual(
            retry08["effective_status"],
            "hard_stop_semantic_pre_retry_capacity_exceeded",
        )
        self.assertEqual(retry08["retry08_new_inspector_network_attempts"], 2)
        self.assertEqual(retry08["retry08_new_usage_tokens"], 37024)
        self.assertFalse(retry08["retry_plan_created"])
        retry09 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry09"
        ]
        self.assertEqual(
            retry09["effective_status"],
            "hard_stop_total_retry_capacity_exceeded",
        )
        self.assertEqual(retry09["retry09_new_inspector_network_attempts"], 0)
        self.assertEqual(retry09["retry09_new_usage_tokens"], 0)
        self.assertEqual(retry09["full_semantic_adjudication_rows"], 246)
        self.assertEqual(retry09["confirmed_retry_source_events"], 13)
        self.assertFalse(retry09["retry_plan_created"])
        retry10 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry10"
        ]
        self.assertEqual(
            retry10["effective_status"],
            "hard_stop_fifth_targeted_rewrite_contract_violation",
        )
        self.assertEqual(retry10["planned_targeted_rewrites"], 13)
        self.assertEqual(retry10["called_targeted_rewrites"], 5)
        self.assertEqual(retry10["accepted_targeted_rewrite_results"], 0)
        self.assertEqual(retry10["failed_event_id"], "EV-C0013-06")
        self.assertEqual(retry10["remaining_events_not_called"], 8)
        self.assertFalse(retry10["four_gate_scorecard_created"])
        retry11 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry11"
        ]
        self.assertEqual(
            retry11["effective_status"],
            "hard_stop_second_targeted_rewrite_anchor_field_violation",
        )
        self.assertEqual(retry11["planned_targeted_rewrites"], 13)
        self.assertEqual(retry11["called_targeted_rewrites"], 2)
        self.assertEqual(retry11["accepted_targeted_rewrite_results"], 0)
        self.assertEqual(retry11["failed_event_id"], "EV-C0003-05")
        self.assertEqual(retry11["failed_event_unexpected_anchor_field"], "quote")
        self.assertEqual(retry11["remaining_events_not_called"], 11)
        self.assertFalse(retry11["four_gate_scorecard_created"])
        retry12 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry12"
        ]
        self.assertEqual(
            retry12["effective_status"],
            "hard_stop_ninth_targeted_rewrite_exact_count_violation",
        )
        self.assertEqual(retry12["planned_targeted_rewrites"], 13)
        self.assertEqual(retry12["called_targeted_rewrites"], 9)
        self.assertEqual(retry12["accepted_targeted_rewrite_results"], 0)
        self.assertEqual(retry12["anchor_extra_field_strip_rows"], 0)
        self.assertEqual(retry12["failed_event_id"], "EV-C0019-25")
        self.assertEqual(retry12["failed_event_returned_replacements"], 2)
        self.assertEqual(retry12["remaining_events_not_called"], 4)
        self.assertFalse(retry12["four_gate_scorecard_created"])
        retry13 = run_states[
            "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry13"
        ]
        self.assertEqual(
            retry13["effective_status"],
            "hard_stop_candidate_failed_four_gates_and_risk",
        )
        self.assertEqual(retry13["retry13_parent_source_events"], 13)
        self.assertEqual(retry13["retry13_frozen_single_object_requests"], 32)
        self.assertEqual(retry13["retry13_repair_network_attempts"], 32)
        self.assertEqual(retry13["retry13_inspector_network_attempts"], 3)
        self.assertEqual(retry13["retry13_new_network_attempts"], 35)
        self.assertEqual(retry13["retry13_new_429_attempts"], 0)
        self.assertEqual(retry13["retry13_new_usage_tokens"], 301277)
        self.assertEqual(retry13["historical_main_usage_tokens_imported"], 83297)
        self.assertEqual(retry13["lineage_usage_tokens"], 384574)
        self.assertEqual(retry13["stable_source_event_count"], 156)
        self.assertEqual(retry13["final_event_count"], 175)
        self.assertTrue(retry13["double_verification_consistent"])
        self.assertTrue(retry13["final_review_created"])
        self.assertTrue(retry13["four_gate_scorecard_created"])
        self.assertEqual(
            retry13["four_gates"],
            {
                "mechanical_three_gates": True,
                "old25_zero_regression": False,
                "chapter3_gold_floor": False,
                "semantic_anchor_invalid_zero": False,
            },
        )
        self.assertTrue(retry13["frozen"])
        route_states = {row["route_id"]: row["status"] for row in routes["routes"]}
        self.assertEqual(route_states["ROUTE-PROGRAM-SIDE-REPAIR"], "in_trial")
        self.assertEqual(route_states["ROUTE-PROMPT-LEAK-REPAIR"], "retired")
        self.assertEqual(
            {row["issue_id"] for row in history["issue_ledger"]},
            {
                "Z83-RETRY13-ANCHOR-GOLD-ISSUE-001",
                "Z83-RETRY13-OLD25-REGRESSION-ISSUE-001",
                "Z83-RETRY13-INSTRUCTION-SCOPE-ISSUE-001",
                "Z83-RETRY13-MANIFEST-PROJECTION-ISSUE-001",
                "Z83-RETRY11-ANCHOR-OBJECT-SCHEMA-ISSUE-001",
                "Z83-RETRY12-EXACT-COUNT-REGRESSION-ISSUE-001",
                "Z83-RETRY11-TOP-MANIFEST-PROJECTION-ISSUE-001",
                "Z83-RETRY12-TOP-MANIFEST-PROJECTION-ISSUE-001",
                "Z83-RETRY10-SPLIT-CONTRACT-ISSUE-001",
                "Z83-RETRY09-TOTAL-CAPACITY-ISSUE-001",
                "Z83-RETRY08-CAPACITY-ISSUE-001",
                "Z83-RETRY07-PREFLIGHT-ISSUE-001",
                "Z83-RETRY06-ISSUE-001",
                "Z83-RETRY05-ISSUE-001",
                "Z83-RETRY04-ISSUE-001",
                "Z86-ISSUE-001",
                "Z86-ISSUE-002",
                "Z93-X01-GOLD-C0003-07-N01-ANCHOR-ISSUE-001",
            },
        )

        governance_index.validate_route_registry(ROOT, routes, {})
        overclaimed_routes = copy.deepcopy(routes)
        program = next(
            row
            for row in overclaimed_routes["routes"]
            if row["route_id"] == "ROUTE-PROGRAM-SIDE-REPAIR"
        )
        program["status"] = "failed"
        with self.assertRaisesRegex(
            governance_index.ArtifactError,
            "路线末事件仍未判死",
        ):
            governance_index.validate_route_registry(ROOT, overclaimed_routes, {})

    def test_current_state_rejects_status_that_disagrees_with_hard_stop_ticket(self) -> None:
        state = read_json(ROOT / governance_index.CURRENT_STATE_PATH)
        broken = copy.deepcopy(state)
        history = (
            broken["historical_context"]
            if broken.get("schema_version") == governance_index.CURRENT_STATE_SCHEMA_V2
            else broken
        )
        run_states = (
            history["archived_run_states"]
            if "archived_run_states" in history
            else history["run_states"]
        )
        original = next(
            row
            for row in run_states
            if row["run_id"] == "Z83_X01_v3程序侧治法_三章复验_v1.0_20260722"
        )
        original["effective_status"] = "hard_stop_interrupted"
        with self.assertRaisesRegex(governance_index.ArtifactError, "中断状态与硬停票不符"):
            governance_index.validate_current_state(ROOT, broken)

    def test_v2_layers_current_execution_and_rejects_legacy_top_level_aliases(self) -> None:
        state = _as_v2(read_json(ROOT / governance_index.CURRENT_STATE_PATH))
        governance_index.validate_current_state(ROOT, state)
        for key in governance_index.LEGACY_TOP_LEVEL_STATE_KEYS:
            self.assertNotIn(key, state)

        broken = copy.deepcopy(state)
        broken["current_step"] = {"task_id": "duplicate"}
        with self.assertRaisesRegex(
            governance_index.ArtifactError,
            "不得保留旧顶层键",
        ):
            governance_index.validate_current_state(ROOT, broken)

    def test_v2_rejects_absolute_current_artifact_identity(self) -> None:
        state = _as_v2(read_json(ROOT / governance_index.CURRENT_STATE_PATH))
        state["current_execution"]["artifacts"]["report_directory"] = "/tmp/report"
        with self.assertRaisesRegex(
            governance_index.ArtifactError,
            "必须是仓库相对路径",
        ):
            governance_index.validate_current_state(ROOT, state)

    def test_governance_docs_pin_key_gates_and_check_stop_line(self) -> None:
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        governance_readme = (ROOT / "governance/README.md").read_text(encoding="utf-8")
        self.assertIn("现役密钥加载入口只有本仓", root_readme)
        self.assertIn("进程读取闸", root_readme)
        self.assertIn("供应商认证闸", root_readme)
        self.assertIn("两份相互独立的证据给出同一结论就停", governance_readme)
        self.assertIn("同时运行的子任务最多 3 个", governance_readme)

    def test_index_routes_task_progress_external_and_demotes_old_routes(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        current_state = read_json(ROOT / governance_index.CURRENT_STATE_PATH)
        route_registry = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        registry = read_json(ROOT / "governance/module_registry.json")
        directory_registry = read_json(
            ROOT / governance_index.DIRECTORY_REGISTRY_PATH
        )
        documents = governance_index.build_documents(
            ROOT,
            control,
            current_state,
            route_registry,
            registry,
            directory_registry,
        )
        index = documents["governance/INDEX.md"]
        for phrase in (
            "整体任务、主支线、领票、父子、硬前置、阻塞、并行线",
            "工程施工、PR、检查、合并",
            "技术兼容／控制字段",
            "$linear-github-task-map",
        ):
            self.assertIn(phrase, index)
        current, _history = governance_index.state_layers(current_state)
        self.assertNotIn(current["task"]["label"], index)
        self.assertNotIn(current["task"]["status_label"], index)
        self.assertNotIn(current["controls"]["next_action"], index)
        self.assertNotIn("governance/current_run.md", documents)
        self.assertNotIn("retry01 第3章 HTTP 200", index)
        route = documents["governance/indexes/route_health.md"]
        self.assertIn("current.md", route)
        self.assertIn("governance/INDEX.md", route)
        self.assertIn("tools/zbatch_modules/README.md", route)

    def test_generated_index_does_not_render_task_or_historical_context(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        current_state = _as_v2(read_json(ROOT / governance_index.CURRENT_STATE_PATH))
        routes = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        registry = read_json(ROOT / "governance/module_registry.json")
        directory_registry = read_json(
            ROOT / governance_index.DIRECTORY_REGISTRY_PATH
        )
        current_state["current_execution"]["task"]["label"] = "V2当前任务唯一标记"
        current_state["current_execution"]["controls"]["next_action"] = "V2当前下一动作唯一标记"
        current_state["historical_context"]["legacy_mainline"] = {
            "label": "禁止出现在路牌的历史标记"
        }
        current_state["historical_context"]["issue_ledger"] = [
            {"summary": "禁止出现在路牌的历史问题标记"}
        ]
        control["recent_score"]["path"] = "禁止出现在当前页的历史成绩标记"

        documents = governance_index.build_documents(
            ROOT,
            control,
            current_state,
            routes,
            registry,
            directory_registry,
        )
        text = documents["governance/INDEX.md"]
        self.assertNotIn("V2当前任务唯一标记", text)
        self.assertNotIn("V2当前下一动作唯一标记", text)
        self.assertNotIn("禁止出现在路牌的历史标记", text)
        self.assertNotIn("禁止出现在路牌的历史问题标记", text)
        self.assertNotIn("禁止出现在当前页的历史成绩标记", text)
        self.assertNotIn("governance/current_run.md", documents)

    def test_root_readme_has_one_hop_governance_route(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[治理索引](governance/INDEX.md)", readme)

    def test_test_command_is_one_fixed_tests_only_command(self) -> None:
        policy = read_json(ROOT / "governance/test_policy.json")
        expected = (
            'cd "$(git rev-parse --show-toplevel)" && '
            "uv run --locked pytest -q"
        )
        self.assertEqual(policy["full_chain_command"], expected)
        self.assertIn(
            "cd <repo-root> && uv run --locked pytest -q",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            expected,
            (ROOT / "governance/README.md").read_text(encoding="utf-8"),
        )
        self.assertNotIn("/Users/", policy["full_chain_command"])

    def test_restructure_baseline_passes_without_authorizing_a_wave(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = _baseline_fixture(root)
            receipt = governance_index._evaluate_restructure_baseline_snapshot(
                root,
                plan,
                dirty_paths=["tools/governance_index.py"],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=datetime(2026, 7, 30, 5, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["blockers"], [])
        self.assertFalse(receipt["authorization_boundary"]["authorizes_wave"])
        self.assertEqual(
            receipt["authorization_boundary"]["next_human_decision_if_pass"],
            "D-08",
        )
        historical = next(
            row
            for row in receipt["checks"]
            if row["check_id"] == "historical_authority_exact_match"
        )
        self.assertEqual(
            historical["evidence"]["actual_fields"],
            [
                {
                    "name": "HISTORICAL",
                    "path": "run_report_pairs[0].acceptance_authority_url",
                    "url": LEGACY_LEDGER,
                }
            ],
        )

    def test_restructure_baseline_blocks_foreign_dirty_candidate_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = _baseline_fixture(root)
            plan["expected_head_sha"] = "b" * 40
            plan["responsibility_window"]["candidate_write_paths"] = [
                "governance/README.md"
            ]
            receipt = governance_index._evaluate_restructure_baseline_snapshot(
                root,
                plan,
                dirty_paths=["governance/README.md"],
                head_sha="b" * 40,
                governance_mismatch_paths=[],
                evaluated_at=datetime(2026, 7, 30, 5, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn(
            "candidate_write_paths_disjoint_from_foreign_dirty",
            receipt["blockers"],
        )

    def test_restructure_baseline_blocks_missing_read_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = _baseline_fixture(root)
            plan["responsibility_window"]["read_allowlist"] = []
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "固定读取范围完全相等",
            ):
                governance_index._evaluate_restructure_baseline_snapshot(
                    root,
                    plan,
                    dirty_paths=[],
                    head_sha="a" * 40,
                    governance_mismatch_paths=[],
                    evaluated_at=datetime(
                        2026,
                        7,
                        30,
                        5,
                        0,
                        tzinfo=timezone.utc,
                    ),
                )

    def test_restructure_baseline_blocks_historical_authority_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = _baseline_fixture(root)
            control_path = root / governance_index.CONTROL_PATH
            control = read_json(control_path)
            control["run_report_pairs"][0]["acceptance_authority_url"] = V2_LEDGER
            _write_json(control_path, control)
            for row in plan["bound_inputs"]:
                if row["path"] == governance_index.CONTROL_PATH:
                    row["sha256"] = governance_index.sha256_file(control_path)
            receipt = governance_index._evaluate_restructure_baseline_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=datetime(2026, 7, 30, 5, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("historical_authority_exact_match", receipt["blockers"])

    def test_restructure_baseline_blocks_authority_and_sha_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = _baseline_fixture(root)
            plan["expected_head_sha"] = "c" * 40
            control_path = root / governance_index.CONTROL_PATH
            control = read_json(control_path)
            control["source_authority"]["ledger_url"] = LEGACY_LEDGER
            _write_json(control_path, control)
            receipt = governance_index._evaluate_restructure_baseline_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="c" * 40,
                governance_mismatch_paths=["governance/index_manifest.json"],
                evaluated_at=datetime(2026, 7, 30, 5, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertEqual(
            set(receipt["blockers"]),
            {
                "governance_generated_green",
                "current_authority_three_way",
                "bound_input_sha",
            },
        )

    def test_restructure_wave_gate_marks_only_exact_wave1_scope_eligible(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=["analysis_library/local.json"],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["blockers"], [])
        boundary = receipt["authorization_boundary"]
        self.assertFalse(boundary["authorizes_wave"])
        self.assertTrue(boundary["mechanical_preconditions_pass"])
        self.assertTrue(boundary["requires_same_task_human_readback"])
        self.assertEqual(
            boundary["eligible_wave_id"],
            governance_index.WAVE1_DIRECTORY_REGISTRY,
        )
        self.assertEqual(
            boundary["eligible_write_paths"],
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE1_DIRECTORY_REGISTRY
            ]["candidate_write_paths"],
        )
        self.assertIn(
            "governance/module_registry.json",
            boundary["eligible_write_paths"],
        )
        self.assertFalse(
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE1_DIRECTORY_REGISTRY
            ]["capability_limits"]["root_refresh"]
        )
        for key in (
            "authorizes_physical_move",
            "authorizes_delete",
            "authorizes_preflight",
            "authorizes_notion_write",
            "authorizes_model_api",
            "authorizes_external_removal",
        ):
            self.assertFalse(boundary[key])

    def test_restructure_wave_gate_blocks_decision_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            decision_path = root / plan["decision_ticket"]["path"]
            decision = read_json(decision_path)
            decision["decisions"]["D-07"]["value"] = "invented_location"
            _write_json(decision_path, decision)
            new_sha = governance_index.sha256_file(decision_path)
            plan["decision_ticket"]["sha256"] = new_sha
            next(
                row
                for row in plan["bound_inputs"]
                if row["path"] == plan["decision_ticket"]["path"]
            )["sha256"] = new_sha
            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("decision_ticket_exact", receipt["blockers"])
        decision_check = next(
            row
            for row in receipt["checks"]
            if row["check_id"] == "decision_ticket_exact"
        )
        self.assertFalse(
            decision_check["evidence"]["decisions"]["D-07"]["matched"]
        )

    def test_restructure_wave_gate_rejects_forged_minimal_baseline_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            receipt_path = root / plan["baseline_receipt"]["path"]
            original = read_json(receipt_path)
            forged = {
                "contract_version": (
                    governance_index.RESTRUCTURE_BASELINE_RECEIPT_V1
                ),
                "plan_id": original["plan_id"],
                "plan_content_sha256": original["plan_content_sha256"],
                "status": "PASS",
                "blockers": [],
                "head_sha": "a" * 40,
                "authorization_boundary": original["authorization_boundary"],
                "responsibility_window": original["responsibility_window"],
                "checks": [],
            }
            _write_json(receipt_path, forged)
            _refresh_plan_reference(plan, "baseline_receipt", receipt_path)
            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("baseline_receipt_current", receipt["blockers"])

    def test_restructure_wave_rejects_nested_baseline_read_before_access(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            probe_path = root / "foundation/probe.json"
            _write_json(probe_path, {"must_not_be_read": True})
            baseline_path = root / plan["baseline_plan"]["path"]
            baseline_plan = read_json(baseline_path)
            baseline_plan["bound_inputs"].append(
                {
                    "path": "foundation/probe.json",
                    "sha256": governance_index.sha256_file(probe_path),
                }
            )
            _write_json(baseline_path, baseline_plan)
            _refresh_plan_reference(plan, "baseline_plan", baseline_path)
            with patch.object(
                governance_index,
                "_read_repo_bytes_once",
                wraps=governance_index._read_repo_bytes_once,
            ) as reader:
                receipt = governance_index._evaluate_restructure_wave_snapshot(
                    root,
                    plan,
                    dirty_paths=[],
                    head_sha="a" * 40,
                    governance_mismatch_paths=[],
                    evaluated_at=now,
                )
            read_paths = [
                call.args[1]
                for call in reader.call_args_list
                if len(call.args) >= 2
            ]

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("baseline_receipt_current", receipt["blockers"])
        self.assertNotIn("foundation/probe.json", read_paths)

    def test_wave2_rejects_nonexact_nested_baseline_inputs_before_replay(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            baseline_plan = read_json(root / plan["baseline_plan"]["path"])
            baseline_receipt = read_json(
                root / plan["baseline_receipt"]["path"]
            )
            private_path = (
                root
                / "TEMP/restructure_wave_preflight/test/"
                "PRIVATE_NESTED_BASELINE.json"
            )
            _write_json(private_path, {"must_not_be_read": True})
            baseline_plan["bound_inputs"].append(
                {
                    "path": private_path.relative_to(root).as_posix(),
                    "sha256": governance_index.sha256_file(private_path),
                }
            )
            baseline_receipt["plan_content_sha256"] = (
                governance_index._canonical_json_sha256(
                    governance_index._baseline_plan(
                        copy.deepcopy(baseline_plan)
                    )
                )
            )
            with (
                patch.object(
                    governance_index,
                    "_evaluate_restructure_baseline_snapshot",
                ) as replay,
                patch.object(
                    governance_index,
                    "_read_repo_bytes_once",
                    wraps=governance_index._read_repo_bytes_once,
                ) as reader,
            ):
                passed, evidence = (
                    governance_index._baseline_receipt_evidence(
                        root,
                        baseline_plan,
                        baseline_receipt,
                        expected_plan_id=baseline_receipt["plan_id"],
                        expected_head_sha="a" * 40,
                        expected_context_id="test-context",
                        outer_wave_id=governance_index.WAVE2_RULE_BUNDLES,
                        outer_read_scopes=(
                            governance_index.WAVE2_REQUIRED_READ_SCOPES
                        ),
                        dirty_paths=[],
                        governance_mismatch_paths=[],
                        evidence_reads={},
                        now=now,
                    )
                )

            self.assertFalse(passed)
            self.assertIn(
                "Wave2 的一级计划 bound_inputs "
                "必须与一级基线必绑输入完全相等",
                "\n".join(evidence["errors"]),
            )
            self.assertEqual(
                evidence["nested_binding_extra"],
                [private_path.relative_to(root).as_posix()],
            )
            self.assertEqual(evidence["nested_binding_missing"], [])
            replay.assert_not_called()
            reader.assert_not_called()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            baseline_plan = read_json(root / plan["baseline_plan"]["path"])
            baseline_receipt = read_json(
                root / plan["baseline_receipt"]["path"]
            )
            baseline_plan["bound_inputs"] = [
                row
                for row in baseline_plan["bound_inputs"]
                if row["path"] != "AGENTS.md"
            ]
            with (
                patch.object(
                    governance_index,
                    "_evaluate_restructure_baseline_snapshot",
                ) as replay,
                patch.object(
                    governance_index,
                    "_read_repo_bytes_once",
                    wraps=governance_index._read_repo_bytes_once,
                ) as reader,
            ):
                passed, evidence = (
                    governance_index._baseline_receipt_evidence(
                        root,
                        baseline_plan,
                        baseline_receipt,
                        expected_plan_id=baseline_receipt["plan_id"],
                        expected_head_sha="a" * 40,
                        expected_context_id="test-context",
                        outer_wave_id=governance_index.WAVE2_RULE_BUNDLES,
                        outer_read_scopes=(
                            governance_index.WAVE2_REQUIRED_READ_SCOPES
                        ),
                        dirty_paths=[],
                        governance_mismatch_paths=[],
                        evidence_reads={},
                        now=now,
                    )
                )

            self.assertFalse(passed)
            self.assertIn(
                "一级计划无效：bound_inputs 缺少必绑输入：AGENTS.md",
                evidence["errors"],
            )
            replay.assert_not_called()
            reader.assert_not_called()

    def test_restructure_wave_gate_binds_one_authorization_context(self) -> None:
        for reference_name in ("decision_ticket", "conflict_lock"):
            with self.subTest(reference_name=reference_name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    plan, now = _wave_fixture(root)
                    path = root / plan[reference_name]["path"]
                    payload = read_json(path)
                    payload["authorization_context_id"] = "foreign-context"
                    _write_json(path, payload)
                    _refresh_plan_reference(plan, reference_name, path)
                    receipt = (
                        governance_index._evaluate_restructure_wave_snapshot(
                            root,
                            plan,
                            dirty_paths=[],
                            head_sha="a" * 40,
                            governance_mismatch_paths=[],
                            evaluated_at=now,
                        )
                    )

                self.assertEqual(receipt["status"], "BLOCKED")
                expected_blocker = (
                    "decision_ticket_exact"
                    if reference_name == "decision_ticket"
                    else "conflict_lock_active"
                )
                self.assertIn(expected_blocker, receipt["blockers"])

    def test_restructure_wave_gate_blocks_dirty_candidate_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[
                    "analysis_library/local.json",
                    "governance/directory_registry.json",
                ],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn(
            "candidate_write_paths_disjoint_from_dirty",
            receipt["blockers"],
        )

    def test_restructure_wave_gate_blocks_stale_lock_and_new_test_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            lock_path = root / plan["conflict_lock"]["path"]
            lock = read_json(lock_path)
            lock["expires_at"] = "2026-07-30T04:59:00+00:00"
            _write_json(lock_path, lock)
            lock_sha = governance_index.sha256_file(lock_path)
            plan["conflict_lock"]["sha256"] = lock_sha
            next(
                row
                for row in plan["bound_inputs"]
                if row["path"] == plan["conflict_lock"]["path"]
            )["sha256"] = lock_sha

            impact_path = root / plan["test_impact"]["path"]
            impact = read_json(impact_path)
            impact["pre_start_evidence"]["full_suite"]["new_failure_count"] = 1
            _write_json(impact_path, impact)
            impact_sha = governance_index.sha256_file(impact_path)
            plan["test_impact"]["sha256"] = impact_sha
            next(
                row
                for row in plan["bound_inputs"]
                if row["path"] == plan["test_impact"]["path"]
            )["sha256"] = impact_sha

            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("conflict_lock_active", receipt["blockers"])
        self.assertIn("test_impact_complete", receipt["blockers"])

    def test_s0_materialize_gate_requires_wave1_completion_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            passed, evidence = governance_index._wave_dependency_evidence(
                root,
                [],
                wave_id=governance_index.S0_MATERIALIZE_ONLY,
                expected_head_sha="a" * 40,
                expected_context_id="test-context",
            )
        self.assertFalse(passed)
        self.assertIn("唯一 Wave1 完成票", evidence["errors"][0])

    def test_s0_materialize_gate_passes_without_expanding_capabilities(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(
                root,
                governance_index.S0_MATERIALIZE_ONLY,
            )
            receipt = _evaluate_s0_fixture(root, plan, now)
            plan["capability_limits"]["preflight"] = True
            drifted = _evaluate_s0_fixture(root, plan, now)

        self.assertEqual(receipt["status"], "PASS")
        self.assertFalse(receipt["authorization_boundary"]["authorizes_wave"])
        self.assertTrue(
            receipt["authorization_boundary"]["mechanical_preconditions_pass"]
        )
        self.assertFalse(receipt["authorization_boundary"]["authorizes_preflight"])
        self.assertEqual(drifted["status"], "BLOCKED")
        self.assertIn("wave_scope_exact", drifted["blockers"])

    def test_s0_materialize_gate_blocks_untraceable_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(
                root,
                governance_index.S0_MATERIALIZE_ONLY,
            )
            completion_path = root / plan["dependencies"][0]["path"]
            completion = read_json(completion_path)
            completion.pop("wave_receipt")
            _write_json(completion_path, completion)
            _refresh_dependency_reference(plan, 0, completion_path)
            receipt = _evaluate_s0_fixture(root, plan, now)

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("wave_dependencies_satisfied", receipt["blockers"])

    def test_s0_materialize_gate_requires_actual_wave1_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(
                root,
                governance_index.S0_MATERIALIZE_ONLY,
            )
            completion_path = root / plan["dependencies"][0]["path"]
            completion = read_json(completion_path)
            completion.pop("wave_plan")
            _write_json(completion_path, completion)
            _refresh_dependency_reference(plan, 0, completion_path)
            receipt = _evaluate_s0_fixture(root, plan, now)

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("wave_dependencies_satisfied", receipt["blockers"])

    def test_s0_dependency_rejects_nested_wave1_read_before_access(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(
                root,
                governance_index.S0_MATERIALIZE_ONLY,
            )
            probe_path = root / "foundation/probe.json"
            _write_json(probe_path, {"must_not_be_read": True})
            completion_path = root / plan["dependencies"][0]["path"]
            completion = read_json(completion_path)
            completion["wave_plan"] = {
                "path": "foundation/probe.json",
                "sha256": governance_index.sha256_file(probe_path),
            }
            _write_json(completion_path, completion)
            _refresh_dependency_reference(plan, 0, completion_path)
            with patch.object(
                governance_index,
                "_read_repo_bytes_once",
                wraps=governance_index._read_repo_bytes_once,
            ) as reader:
                receipt = _evaluate_s0_fixture(root, plan, now)
            read_paths = [
                call.args[1]
                for call in reader.call_args_list
                if len(call.args) >= 2
            ]

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("wave_dependencies_satisfied", receipt["blockers"])
        self.assertNotIn("foundation/probe.json", read_paths)

    def test_s0_materialize_gate_blocks_out_of_scope_git_transition(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(
                root,
                governance_index.S0_MATERIALIZE_ONLY,
            )
            receipt = _evaluate_s0_fixture(
                root,
                plan,
                now,
                changes=[{"status": "M", "path": "foundation/forbidden.md"}],
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("wave_dependencies_satisfied", receipt["blockers"])

    def test_s0_materialize_gate_blocks_partial_git_write_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(
                root,
                governance_index.S0_MATERIALIZE_ONLY,
            )
            receipt = _evaluate_s0_fixture(
                root,
                plan,
                now,
                changes=[
                    {
                        "status": "A",
                        "path": "governance/directory_registry.json",
                    }
                ],
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("wave_dependencies_satisfied", receipt["blockers"])

    def test_s0_materialize_gate_blocks_output_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(
                root,
                governance_index.S0_MATERIALIZE_ONLY,
            )
            completion_path = root / plan["dependencies"][0]["path"]
            completion = read_json(completion_path)
            completion["outputs"][0]["sha256"] = "0" * 64
            completion["output_manifest_sha256"] = (
                governance_index._canonical_json_sha256(
                    completion["outputs"]
                )
            )
            _write_json(completion_path, completion)
            _refresh_dependency_reference(plan, 0, completion_path)
            receipt = _evaluate_s0_fixture(root, plan, now)

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("wave_dependencies_satisfied", receipt["blockers"])

    def test_completion_v2_derives_exact_historical_blobs_not_worktree(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, receipt, _, _ = _completion_v2_fixture(root)
            historical = copy.deepcopy(receipt)
            (root / "tools/experiment_workspace.py").write_text(
                "print('dirty worktree replacement')\n",
                encoding="utf-8",
            )
            replayed = (
                governance_index.evaluate_restructure_wave_completion_v2(
                    root,
                    request,
                )
            )

        self.assertEqual(receipt["status"], "GIT_SCOPE_PASS")
        self.assertEqual(receipt, replayed)
        self.assertEqual(
            [row["path"] for row in receipt["git_blob_manifest"]],
            [
                "governance/tool_registry.json",
                "tools/experiment_workspace.py",
            ],
        )
        self.assertRegex(
            receipt["git_blob_manifest"][0]["git_blob_sha"],
            r"^[0-9a-f]{40}$",
        )
        self.assertEqual(receipt["git_blob_manifest"], historical["git_blob_manifest"])
        self.assertTrue(
            receipt["authorization_boundary"][
                "tests_not_proven_or_evaluated"
            ]
        )
        self.assertFalse(
            any(key.startswith("source_test") for key in receipt)
        )
        self.assertFalse(any("failure" in key for key in receipt))

    def test_completion_v2_rejects_bad_source_plan_or_receipt_sha(self) -> None:
        for reference_name, blocker in (
            ("wave_plan", "source_wave_plan_bound"),
            ("wave_receipt", "source_wave_receipt_pass"),
        ):
            with self.subTest(reference_name=reference_name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    request, _, _, _ = _completion_v2_fixture(root)
                    request[reference_name]["sha256"] = "0" * 64
                    receipt = (
                        governance_index.evaluate_restructure_wave_completion_v2(
                            root,
                            request,
                        )
                    )
                self.assertEqual(receipt["status"], "BLOCKED")
                self.assertIn(blocker, receipt["blockers"])

    def test_completion_v2_rejects_reference_before_out_of_scope_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, _, plan_path, _ = _completion_v2_fixture(root)
            copied_plan_path = root / "foundation/copied_valid_plan.json"
            _write_json(copied_plan_path, read_json(plan_path))
            request["wave_plan"] = {
                "path": copied_plan_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(copied_plan_path),
            }
            with (
                patch.object(
                    governance_index,
                    "_read_repo_bytes_once",
                    wraps=governance_index._read_repo_bytes_once,
                ) as reader,
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "完成请求引用超出",
                ),
            ):
                governance_index.evaluate_restructure_wave_completion_v2(
                    root,
                    request,
                )

        reader.assert_not_called()

    def test_completion_v2_rejects_non_ancestor_outside_delete_and_rename(
        self,
    ) -> None:
        cases = (
            (
                "non_ancestor",
                {"git_is_ancestor": False},
                "git_ancestry",
            ),
            (
                "outside",
                {
                    "changes": [
                        {"status": "M", "path": "foundation/forbidden.md"}
                    ]
                },
                "git_diff_exact_scope",
            ),
            (
                "delete",
                {
                    "changes": [
                        {
                            "status": "D",
                            "path": "tools/experiment_workspace.py",
                        }
                    ]
                },
                "git_diff_exact_scope",
            ),
            (
                "rename",
                {
                    "changes": [
                        {
                            "status": "R100",
                            "old_path": "tools/experiment_workspace.py",
                            "path": "tools/renamed_workspace.py",
                        }
                    ]
                },
                "git_diff_exact_scope",
            ),
        )
        for label, overrides, blocker in cases:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    request, _, _, _ = _completion_v2_fixture(root)
                    patches = []
                    if "git_is_ancestor" in overrides:
                        patches.append(
                            patch.object(
                                governance_index,
                                "git_is_ancestor",
                                return_value=overrides["git_is_ancestor"],
                            )
                        )
                    if "changes" in overrides:
                        patches.append(
                            patch.object(
                                governance_index,
                                "git_name_status_between_exact",
                                return_value=overrides["changes"],
                            )
                        )
                    for active_patch in patches:
                        active_patch.start()
                    try:
                        receipt = (
                            governance_index.evaluate_restructure_wave_completion_v2(
                                root,
                                request,
                            )
                        )
                    finally:
                        for active_patch in reversed(patches):
                            active_patch.stop()
                self.assertEqual(receipt["status"], "BLOCKED")
                self.assertIn(blocker, receipt["blockers"])

    def test_wave2_completion_rejects_descendants_of_file_candidates(
        self,
    ) -> None:
        forbidden_paths = (
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking/run.py",
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking/secret.env",
            "config/prompts/wave2_synthetic_json_probe_v1/part.json",
            "config/README.md/evil.json",
        )
        for forbidden_path in forbidden_paths:
            with self.subTest(forbidden_path=forbidden_path):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    plan, _ = _wave_fixture(root)
                    wave2_spec = governance_index.RESTRUCTURE_WAVE_SPECS[
                        governance_index.WAVE2_RULE_BUNDLES
                    ]
                    plan["route"] = "A_PLUS"
                    plan["wave_id"] = governance_index.WAVE2_RULE_BUNDLES
                    plan["responsibility_window"]["wave_id"] = (
                        governance_index.WAVE2_RULE_BUNDLES
                    )
                    plan["responsibility_window"]["read_allowlist"] = list(
                        wave2_spec["required_read_scopes"]
                    )
                    plan["responsibility_window"][
                        "candidate_write_paths"
                    ] = list(wave2_spec["candidate_write_paths"])
                    plan["capability_limits"] = copy.deepcopy(
                        wave2_spec["capability_limits"]
                    )
                    required_references = wave2_spec[
                        "required_reference_paths"
                    ]
                    for reference_name in (
                        "baseline_plan",
                        "baseline_receipt",
                        "decision_ticket",
                        "conflict_lock",
                        "test_impact",
                    ):
                        plan[reference_name] = {
                            "path": required_references[reference_name],
                            "sha256": "2" * 64,
                        }
                    plan["dependencies"] = [
                        {
                            "path": required_references["dependency"]["path"],
                            "sha256": "1" * 64,
                            "wave_id": required_references["dependency"][
                                "wave_id"
                            ],
                        }
                    ]
                    required_binding_paths = (
                        set(wave2_spec["required_inputs"])
                        | {
                            plan[reference_name]["path"]
                            for reference_name in (
                                "baseline_plan",
                                "baseline_receipt",
                                "decision_ticket",
                                "conflict_lock",
                                "test_impact",
                            )
                        }
                        | {
                            dependency["path"]
                            for dependency in plan["dependencies"]
                        }
                    )
                    plan["bound_inputs"] = [
                        {
                            "path": path,
                            "sha256": "0" * 64,
                            "role": f"wave2_input_{index:02d}",
                        }
                        for index, path in enumerate(
                            sorted(required_binding_paths),
                            start=1,
                        )
                    ]

                    _git(root, "init", "-q")
                    _git(root, "config", "user.email", "tests@example.invalid")
                    _git(root, "config", "user.name", "Governance Tests")
                    _git(root, "add", ".")
                    _git(root, "commit", "-qm", "pre wave2")
                    pre_commit = _git(root, "rev-parse", "HEAD")
                    plan["expected_head_sha"] = pre_commit
                    plan_path = (
                        root
                        / "TEMP/restructure_wave_preflight/test/"
                        "WAVE2_COMPLETION_SOURCE_PLAN.json"
                    )
                    _write_json(plan_path, plan)
                    normalized_plan = governance_index._wave_plan(
                        copy.deepcopy(plan)
                    )
                    receipt = {
                        "contract_version": (
                            governance_index.RESTRUCTURE_WAVE_RECEIPT_V1
                        ),
                        "plan_id": normalized_plan["plan_id"],
                        "plan_content_sha256": (
                            governance_index._canonical_json_sha256(
                                normalized_plan
                            )
                        ),
                        "status": "PASS",
                        "blockers": [],
                        "head_sha": pre_commit,
                        "route": "A_PLUS",
                        "wave_id": governance_index.WAVE2_RULE_BUNDLES,
                        "responsibility_window": copy.deepcopy(
                            normalized_plan["responsibility_window"]
                        ),
                        "authorization_boundary": {
                            "authorizes_wave": False,
                            "mechanical_preconditions_pass": True,
                            "eligible_wave_id": (
                                governance_index.WAVE2_RULE_BUNDLES
                            ),
                            "eligible_write_paths": list(
                                wave2_spec["candidate_write_paths"]
                            ),
                        },
                        "checks": [
                            {
                                "check_id": check_id,
                                "passed": True,
                                "evidence": {"fixture": True},
                            }
                            for check_id in (
                                "responsibility_window_time",
                                "governance_generated_green",
                                "head_frozen",
                                "wave_scope_exact",
                                "baseline_receipt_current",
                                "decision_ticket_exact",
                                "conflict_lock_active",
                                "test_impact_complete",
                                "bound_input_sha",
                                "read_allowlist_complete",
                                "candidate_write_paths_disjoint_from_dirty",
                                "wave_dependencies_satisfied",
                                "live_snapshot_stable",
                            )
                        ],
                    }
                    receipt_path = (
                        root
                        / "TEMP/restructure_wave_preflight/test/"
                        "WAVE2_COMPLETION_SOURCE_RECEIPT.json"
                    )
                    _write_json(receipt_path, receipt)
                    target = root / forbidden_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("forbidden\n", encoding="utf-8")
                    _git(root, "add", forbidden_path)
                    _git(root, "commit", "-qm", "forbidden descendant")
                    post_commit = _git(root, "rev-parse", "HEAD")
                    request = {
                        "contract_version": (
                            governance_index.RESTRUCTURE_WAVE_COMPLETION_REQUEST_V2
                        ),
                        "completion_id": "WAVE2-FILE-BOUNDARY-TEST",
                        "wave_id": governance_index.WAVE2_RULE_BUNDLES,
                        "authorization_context_id": "test-context",
                        "pre_commit_sha": pre_commit,
                        "post_commit_sha": post_commit,
                        "wave_plan": {
                            "path": plan_path.relative_to(root).as_posix(),
                            "sha256": governance_index.sha256_file(plan_path),
                        },
                        "wave_receipt": {
                            "path": receipt_path.relative_to(root).as_posix(),
                            "sha256": governance_index.sha256_file(
                                receipt_path
                            ),
                        },
                    }
                    result = (
                        governance_index.evaluate_restructure_wave_completion_v2(
                            root,
                            request,
                        )
                    )

                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("git_diff_exact_scope", result["blockers"])

    def test_completion_v2_rejects_request_reported_outputs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, _, _, _ = _completion_v2_fixture(root)
            forged = copy.deepcopy(request)
            forged["outputs"] = [
                {
                    "path": "foundation/forbidden.md",
                    "sha256": "0" * 64,
                }
            ]
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "字段必须完全相等",
            ):
                governance_index.evaluate_restructure_wave_completion_v2(
                    root,
                    forged,
                )

    def test_wave2_dependency_requires_exact_s0_completion_v2(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, completion, _, _ = _completion_v2_fixture(root)
            completion_path = (
                root
                / "TEMP/restructure_wave_preflight/test/S0_COMPLETION_V2.json"
            )
            _write_json(completion_path, completion)
            dependency = {
                "path": completion_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(completion_path),
                "wave_id": governance_index.S0_MATERIALIZE_ONLY,
            }
            trusted_source = {
                "wave_plan": completion["source_wave_plan"],
                "wave_receipt": completion["source_wave_receipt"],
                "pre_commit_sha": completion["pre_commit_sha"],
                "post_commit_sha": completion["post_commit_sha"],
            }

            def evaluate_dependency(
                dependencies: list[dict],
                *,
                context_id: str = "test-context",
                head_sha: str = completion["post_commit_sha"],
            ) -> tuple[bool, dict]:
                spec = governance_index.RESTRUCTURE_WAVE_SPECS[
                    governance_index.WAVE2_RULE_BUNDLES
                ]
                with patch.dict(
                    spec,
                    {"required_completion_source": trusted_source},
                ):
                    return governance_index._wave_dependency_evidence(
                        root,
                        dependencies,
                        wave_id=governance_index.WAVE2_RULE_BUNDLES,
                        expected_head_sha=head_sha,
                        expected_context_id=context_id,
                    )

            passed, _ = evaluate_dependency([dependency])
            missing, _ = evaluate_dependency([])
            bad_sha = copy.deepcopy(dependency)
            bad_sha["sha256"] = "0" * 64
            bad, _ = evaluate_dependency([bad_sha])
            wrong_context, _ = evaluate_dependency(
                [dependency],
                context_id="foreign-context",
            )
            with patch.object(
                governance_index,
                "git_name_status_between_exact",
                return_value=[],
            ):
                blocked_completion = (
                    governance_index.evaluate_restructure_wave_completion_v2(
                        root,
                        request,
                    )
                )
            blocked_path = completion_path.with_name("S0_COMPLETION_BLOCKED.json")
            _write_json(blocked_path, blocked_completion)
            blocked_dependency = {
                "path": blocked_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(blocked_path),
                "wave_id": governance_index.S0_MATERIALIZE_ONLY,
            }
            non_pass, _ = evaluate_dependency([blocked_dependency])
            probe_path = root / "foundation/probe.json"
            _write_json(probe_path, {"must_not_be_read": True})
            forged_completion = copy.deepcopy(completion)
            forged_completion["completion_request"]["wave_plan"] = {
                "path": "foundation/probe.json",
                "sha256": governance_index.sha256_file(probe_path),
            }
            forged_path = completion_path.with_name("S0_COMPLETION_FORGED.json")
            _write_json(forged_path, forged_completion)
            forged_dependency = {
                "path": forged_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(forged_path),
                "wave_id": governance_index.S0_MATERIALIZE_ONLY,
            }
            early_reads: dict[str, str] = {}
            spec = governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE2_RULE_BUNDLES
            ]
            with patch.dict(
                spec,
                {"required_completion_source": trusted_source},
            ):
                forged_passed, _ = (
                    governance_index._wave_dependency_evidence(
                        root,
                        [forged_dependency],
                        wave_id=governance_index.WAVE2_RULE_BUNDLES,
                        expected_head_sha=completion["post_commit_sha"],
                        expected_context_id="test-context",
                        evidence_reads=early_reads,
                    )
                )
            wrong_source = copy.deepcopy(trusted_source)
            wrong_source["post_commit_sha"] = "0" * 40
            with patch.dict(
                spec,
                {"required_completion_source": wrong_source},
            ):
                untrusted, _ = governance_index._wave_dependency_evidence(
                    root,
                    [dependency],
                    wave_id=governance_index.WAVE2_RULE_BUNDLES,
                    expected_head_sha=completion["post_commit_sha"],
                    expected_context_id="test-context",
                )
            _write_json(
                root / "governance/tool_registry.json",
                {
                    "schema_version": "test",
                    "s0_registered": True,
                    "gate_extension": True,
                },
            )
            _git(root, "add", "governance/tool_registry.json")
            _git(root, "commit", "-qm", "extend gate registry")
            allowed_drift_head = _git(root, "rev-parse", "HEAD")
            allowed_drift_passed, allowed_drift_evidence = (
                evaluate_dependency(
                    [dependency],
                    head_sha=allowed_drift_head,
                )
            )
            (root / "tools/experiment_workspace.py").write_text(
                "print('unauthorized replacement')\n",
                encoding="utf-8",
            )
            _git(root, "add", "tools/experiment_workspace.py")
            _git(root, "commit", "-qm", "replace s0 output")
            replaced_head = _git(root, "rev-parse", "HEAD")
            replaced_output, replaced_evidence = evaluate_dependency(
                [dependency],
                head_sha=replaced_head,
            )
            (root / "tools/experiment_workspace.py").unlink()
            _git(root, "add", "-u", "tools/experiment_workspace.py")
            _git(root, "commit", "-qm", "remove s0 output")
            deleted_head = _git(root, "rev-parse", "HEAD")
            missing_output, _ = evaluate_dependency(
                [dependency],
                head_sha=deleted_head,
            )

        self.assertTrue(passed)
        self.assertFalse(missing)
        self.assertFalse(bad)
        self.assertFalse(wrong_context)
        self.assertFalse(non_pass)
        self.assertFalse(forged_passed)
        self.assertNotIn("foundation/probe.json", early_reads)
        self.assertFalse(untrusted)
        self.assertTrue(allowed_drift_passed)
        self.assertEqual(
            [
                row["path"]
                for row in allowed_drift_evidence[
                    "allowed_current_head_blob_drift"
                ]
            ],
            ["governance/tool_registry.json"],
        )
        self.assertFalse(replaced_output)
        self.assertEqual(
            [
                row["path"]
                for row in replaced_evidence[
                    "unauthorized_current_head_blob_drift"
                ]
            ],
            ["tools/experiment_workspace.py"],
        )
        self.assertFalse(missing_output)

    def test_wave2_requires_new_preparation_ticket_without_construction_auth(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, completion, plan_path, _ = _completion_v2_fixture(root)
            completion_path = (
                root
                / "TEMP/restructure_wave_preflight/test/S0_COMPLETION_V2.json"
            )
            _write_json(completion_path, completion)
            dependency = {
                "path": completion_path.relative_to(root).as_posix(),
                "sha256": governance_index.sha256_file(completion_path),
                "wave_id": governance_index.S0_MATERIALIZE_ONLY,
            }
            ticket = {
                "contract_version": (
                    governance_index.RESTRUCTURE_WAVE2_PREPARATION_TICKET_V1
                ),
                "ticket_id": "WAVE2-PREPARATION-TEST",
                "ticket_kind": "wave2_gate_extension_eligibility",
                "authority": "CZ",
                "authorization_context_id": "test-context",
                "evidence_class": "same_task_human_readback",
                "human_readback": {
                    "required": True,
                    "confirmed": True,
                    "cryptographic_proof": False,
                },
                "selected_route": "A_PLUS",
                "selected_scope": [governance_index.WAVE2_RULE_BUNDLES],
                "source_messages": [
                    {
                        "text": governance_index.WAVE2_PREPARATION_SOURCE_TEXT,
                        "sha256": governance_index._sha256_text(
                            governance_index.WAVE2_PREPARATION_SOURCE_TEXT
                        ),
                    }
                ],
                "decisions": {
                    decision_id: {"status": status, "value": value}
                    for decision_id, (status, value) in (
                        governance_index.WAVE2_PREPARATION_VALUES.items()
                    )
                },
                "upstream_completion": {
                    "path": dependency["path"],
                    "sha256": dependency["sha256"],
                },
                "eligibility_capability_ceiling": copy.deepcopy(
                    governance_index.RESTRUCTURE_WAVE_SPECS[
                        governance_index.WAVE2_RULE_BUNDLES
                    ]["capability_limits"]
                ),
                "authorization_boundary": {
                    "authorizes_wave": False,
                    "authorizes_rule_bundle_construction": False,
                    "authorizes_offline_resolve": False,
                    "authorizes_preflight": False,
                    "authorizes_network": False,
                    "authorizes_credential_read": False,
                    "authorizes_request_send": False,
                    "authorizes_model_api": False,
                    "authorizes_notion_write": False,
                    "authorizes_external_removal": False,
                    "requires_later_same_task_positive_construction_confirmation": True,
                },
            }
            self.assertFalse(
                any(
                    value
                    for key, value in ticket["authorization_boundary"].items()
                    if key.startswith("authorizes_")
                )
            )
            s0_plan = read_json(plan_path)

            def evaluate_ticket(
                value: dict,
                *,
                ticket_path: str,
                ticket_id: str,
            ) -> tuple[bool, dict]:
                spec = governance_index.RESTRUCTURE_WAVE_SPECS[
                    governance_index.WAVE2_RULE_BUNDLES
                ]
                with patch.dict(
                    spec,
                    {
                        "required_prior_decision_ticket": s0_plan[
                            "decision_ticket"
                        ]
                    },
                ):
                    return (
                        governance_index._wave2_preparation_ticket_evidence(
                            root,
                            value,
                            ticket_path=ticket_path,
                            upstream_dependency=dependency,
                            expected_ticket_id=ticket_id,
                            expected_context_id="test-context",
                        )
                    )

            passed, _ = evaluate_ticket(
                ticket,
                ticket_path=(
                    "TEMP/restructure_wave_preflight/test/"
                    "WAVE2_RULE_BUNDLES_PREPARATION.json"
                ),
                ticket_id="WAVE2-PREPARATION-TEST",
            )
            old_ticket_path = root / s0_plan["decision_ticket"]["path"]
            old_ticket = read_json(old_ticket_path)
            reused, _ = evaluate_ticket(
                old_ticket,
                ticket_path=s0_plan["decision_ticket"]["path"],
                ticket_id=old_ticket["ticket_id"],
            )
            construction_claim = copy.deepcopy(ticket)
            construction_claim["source_messages"] = [
                {
                    "text": "现在开始写 Wave2 候选文件",
                    "sha256": governance_index._sha256_text(
                        "现在开始写 Wave2 候选文件"
                    ),
                }
            ]
            construction_claim_passed, _ = evaluate_ticket(
                construction_claim,
                ticket_path=(
                    "TEMP/restructure_wave_preflight/test/"
                    "WAVE2_RULE_BUNDLES_CONSTRUCTION_CLAIM.json"
                ),
                ticket_id="WAVE2-PREPARATION-TEST",
            )
            forged_authorization = copy.deepcopy(ticket)
            forged_authorization["authorization_boundary"][
                "authorizes_rule_bundle_construction"
            ] = True
            forged_authorization_passed, _ = evaluate_ticket(
                forged_authorization,
                ticket_path=(
                    "TEMP/restructure_wave_preflight/test/"
                    "WAVE2_RULE_BUNDLES_FORGED_AUTH.json"
                ),
                ticket_id="WAVE2-PREPARATION-TEST",
            )

        self.assertTrue(passed)
        self.assertFalse(reused)
        self.assertFalse(construction_claim_passed)
        self.assertFalse(forged_authorization_passed)

    def test_wave2_does_not_expand_old_read_scopes_and_rejects_capability_keys(
        self,
    ) -> None:
        self.assertNotIn(
            "config",
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE1_DIRECTORY_REGISTRY
            ]["required_read_scopes"],
        )
        self.assertIn(
            ".git",
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE1_DIRECTORY_REGISTRY
            ]["required_read_scopes"],
        )
        self.assertNotIn(
            "config",
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.S0_MATERIALIZE_ONLY
            ]["required_read_scopes"],
        )
        self.assertIn(
            ".git",
            governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.S0_MATERIALIZE_ONLY
            ]["required_read_scopes"],
        )
        wave2_spec = governance_index.RESTRUCTURE_WAVE_SPECS[
            governance_index.WAVE2_RULE_BUNDLES
        ]
        self.assertEqual(
            wave2_spec["required_read_scopes"],
            governance_index.WAVE2_REQUIRED_READ_SCOPES,
        )
        for broad_scope in (
            ".git",
            "config",
            "governance",
            "tests",
            "tools",
        ):
            self.assertNotIn(
                broad_scope,
                wave2_spec["required_read_scopes"],
            )
        self.assertIn(
            "config/model_call_profiles/profile.schema.json",
            wave2_spec["required_read_scopes"],
        )
        self.assertEqual(
            wave2_spec["candidate_write_paths"],
            governance_index.WAVE2_CANDIDATE_WRITE_PATHS,
        )
        self.assertEqual(len(wave2_spec["candidate_write_paths"]), 22)
        self.assertEqual(
            wave2_spec["required_reference_paths"],
            {
                "baseline_plan": (
                    "TEMP/restructure_wave_preflight/"
                    "route-a-plus-wave2-20260730/"
                    "BASELINE_PLAN_WAVE2_20260730.json"
                ),
                "baseline_receipt": (
                    "TEMP/restructure_wave_preflight/"
                    "route-a-plus-wave2-20260730/"
                    "BASELINE_RECEIPT_WAVE2_20260730.json"
                ),
                "decision_ticket": (
                    "TEMP/restructure_wave_preflight/"
                    "route-a-plus-wave2-20260730/"
                    "WAVE2_PREPARATION_TICKET_20260730.json"
                ),
                "conflict_lock": (
                    "TEMP/restructure_wave_preflight/locks/"
                    "WAVE2_RULE_BUNDLES.lock.json"
                ),
                "test_impact": (
                    "TEMP/restructure_wave_preflight/"
                    "route-a-plus-wave2-20260730/"
                    "WAVE2_TEST_IMPACT_20260730.json"
                ),
                "dependency": {
                    "path": (
                        "TEMP/restructure_wave_preflight/"
                        "route-a-plus-s0-20260730/"
                        "S0_MATERIALIZE_COMPLETION_V2_20260730.json"
                    ),
                    "wave_id": governance_index.S0_MATERIALIZE_ONLY,
                },
            },
        )
        expanded_exact_files = {
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking/bundle.json",
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking/"
            "request_envelope.schema.json",
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking/"
            "response_envelope.schema.json",
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking/"
            "normalization.json",
            "config/prompts/wave2_synthetic_json_probe_v1/prompt.md",
            "config/prompts/wave2_synthetic_json_probe_v1/manifest.json",
        }
        self.assertTrue(
            expanded_exact_files
            <= set(wave2_spec["candidate_write_paths"])
        )
        self.assertNotIn(
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking",
            wave2_spec["candidate_write_paths"],
        )
        self.assertNotIn(
            "config/prompts/wave2_synthetic_json_probe_v1",
            wave2_spec["candidate_write_paths"],
        )
        for existing_candidate in (
            "tools/model_call_profiles.py",
            "tests/test_model_call_profiles.py",
            "tools/README.md",
            "tests/README.md",
        ):
            self.assertIn(
                existing_candidate,
                wave2_spec["required_inputs"],
            )
        self.assertFalse(
            any(
                "api_rule_bundles" in path
                for path in wave2_spec["candidate_write_paths"]
            )
        )
        for exact_file in (
            "config/README.md",
            "config/model_call_profiles/contracts/"
            "contract_bundle.schema.json",
            "config/model_call_profiles/contracts/"
            "qianwen_qwen3_7_flash_json_object_no_thinking/bundle.json",
            "config/prompts/wave2_synthetic_json_probe_v1/prompt.md",
            "tools/model_call_profiles.py",
        ):
            self.assertFalse(
                governance_index._wave_candidate_write_path_is_allowed(
                    governance_index.WAVE2_RULE_BUNDLES,
                    f"{exact_file}/evil",
                    exact_file,
                )
            )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            plan["responsibility_window"]["read_allowlist"].append("config")
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "读取范围完全相等",
            ):
                governance_index._evaluate_restructure_wave_snapshot(
                    root,
                    plan,
                    dirty_paths=[],
                    head_sha="a" * 40,
                    governance_mismatch_paths=[],
                    evaluated_at=now,
                )
            plan["responsibility_window"]["read_allowlist"].remove("config")
            probe_path = root / "foundation/probe.json"
            _write_json(probe_path, {"must_not_be_read": True})
            plan["bound_inputs"].append(
                {
                    "path": "foundation/probe.json",
                    "sha256": governance_index.sha256_file(probe_path),
                    "role": "forbidden_probe",
                }
            )
            with (
                patch.object(
                    governance_index,
                    "_read_repo_bytes_once",
                    wraps=governance_index._read_repo_bytes_once,
                ) as reader,
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "超出许可范围",
                ),
            ):
                governance_index._evaluate_restructure_wave_snapshot(
                    root,
                    plan,
                    dirty_paths=[],
                    head_sha="a" * 40,
                    governance_mismatch_paths=[],
                    evaluated_at=now,
                )
            reader.assert_not_called()
            plan["bound_inputs"].pop()
            plan["capability_limits"]["unknown_future_power"] = False
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "字段必须与当前 Wave 完全相等",
            ):
                governance_index._wave_plan(plan)

            wave2_plan = copy.deepcopy(plan)
            wave2_plan["route"] = "A_PLUS"
            wave2_plan["wave_id"] = governance_index.WAVE2_RULE_BUNDLES
            wave2_plan["responsibility_window"]["wave_id"] = (
                governance_index.WAVE2_RULE_BUNDLES
            )
            wave2_plan["responsibility_window"]["read_allowlist"] = list(
                wave2_spec["required_read_scopes"]
            )
            wave2_plan["responsibility_window"]["candidate_write_paths"] = list(
                wave2_spec["candidate_write_paths"]
            )
            wave2_plan["capability_limits"] = copy.deepcopy(
                wave2_spec["capability_limits"]
            )
            required_references = wave2_spec["required_reference_paths"]
            for reference_name in (
                "baseline_plan",
                "baseline_receipt",
                "decision_ticket",
                "conflict_lock",
                "test_impact",
            ):
                wave2_plan[reference_name] = {
                    "path": required_references[reference_name],
                    "sha256": "2" * 64,
                }
            wave2_plan["dependencies"] = [
                {
                    "path": required_references["dependency"]["path"],
                    "sha256": "1" * 64,
                    "wave_id": required_references["dependency"]["wave_id"],
                }
            ]
            required_binding_paths = (
                set(wave2_spec["required_inputs"])
                | {
                    wave2_plan[reference_name]["path"]
                    for reference_name in (
                        "baseline_plan",
                        "baseline_receipt",
                        "decision_ticket",
                        "conflict_lock",
                        "test_impact",
                    )
                }
                | {
                    dependency["path"]
                    for dependency in wave2_plan["dependencies"]
                }
            )
            wave2_plan["bound_inputs"] = [
                {
                    "path": path,
                    "sha256": "0" * 64,
                    "role": f"wave2_exact_input_{index:02d}",
                }
                for index, path in enumerate(
                    sorted(required_binding_paths),
                    start=1,
                )
            ]
            forbidden_reads = (
                ".git/config",
                "config/private/secret.json",
                "config/README.md/evil.json",
            )
            for index, relative in enumerate(forbidden_reads):
                with self.subTest(forbidden_read=relative):
                    forbidden_path = root / relative
                    _write_json(
                        forbidden_path,
                        {"secret": "must-not-be-read"},
                    )
                    rejected_plan = copy.deepcopy(wave2_plan)
                    rejected_plan["bound_inputs"].append(
                        {
                            "path": relative,
                            "sha256": governance_index.sha256_file(
                                forbidden_path
                            ),
                            "role": f"forbidden_wave2_read_{index}",
                        }
                    )
                    with (
                        patch.object(
                            governance_index,
                            "_read_repo_bytes_once",
                            wraps=governance_index._read_repo_bytes_once,
                        ) as private_reader,
                        self.assertRaisesRegex(
                            governance_index.ArtifactError,
                            "bound_inputs 必须",
                        ),
                    ):
                        governance_index._evaluate_restructure_wave_snapshot(
                            root,
                            rejected_plan,
                            dirty_paths=[],
                            head_sha="a" * 40,
                            governance_mismatch_paths=[],
                            evaluated_at=now,
                        )
                    private_reader.assert_not_called()

            missing_binding_plan = copy.deepcopy(wave2_plan)
            missing_binding_plan["bound_inputs"].pop()
            with (
                patch.object(
                    governance_index,
                    "_read_repo_bytes_once",
                    wraps=governance_index._read_repo_bytes_once,
                ) as missing_reader,
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "bound_inputs 必须",
                ),
            ):
                governance_index._evaluate_restructure_wave_snapshot(
                    root,
                    missing_binding_plan,
                    dirty_paths=[],
                    head_sha="a" * 40,
                    governance_mismatch_paths=[],
                    evaluated_at=now,
                )
            missing_reader.assert_not_called()

            dynamic_reference_names = (
                "baseline_plan",
                "baseline_receipt",
                "decision_ticket",
                "conflict_lock",
                "test_impact",
                "dependency",
            )
            for reference_index, reference_name in enumerate(
                dynamic_reference_names
            ):
                with self.subTest(dynamic_reference=reference_name):
                    private_reference_path = (
                        root
                        / "TEMP/restructure_wave_preflight/test/"
                        f"PRIVATE_{reference_name.upper()}.json"
                    )
                    _write_json(private_reference_path, {"private": True})
                    dynamic_plan = copy.deepcopy(wave2_plan)
                    private_reference = {
                        "path": private_reference_path.relative_to(
                            root
                        ).as_posix(),
                        "sha256": governance_index.sha256_file(
                            private_reference_path
                        ),
                    }
                    if reference_name == "dependency":
                        dynamic_plan["dependencies"] = [
                            {
                                **private_reference,
                                "wave_id": (
                                    governance_index.S0_MATERIALIZE_ONLY
                                ),
                            }
                        ]
                    else:
                        dynamic_plan[reference_name] = private_reference
                    dynamic_binding_paths = (
                        set(wave2_spec["required_inputs"])
                        | {
                            dynamic_plan[ticket_name]["path"]
                            for ticket_name in (
                                "baseline_plan",
                                "baseline_receipt",
                                "decision_ticket",
                                "conflict_lock",
                                "test_impact",
                            )
                        }
                        | {
                            dependency["path"]
                            for dependency in dynamic_plan["dependencies"]
                        }
                    )
                    dynamic_plan["bound_inputs"] = [
                        {
                            "path": path,
                            "sha256": "0" * 64,
                            "role": (
                                f"dynamic_reference_{reference_index:02d}_"
                                f"{index:02d}"
                            ),
                        }
                        for index, path in enumerate(
                            sorted(dynamic_binding_paths),
                            start=1,
                        )
                    ]
                    with (
                        patch.object(
                            governance_index,
                            "_read_repo_bytes_once",
                            wraps=governance_index._read_repo_bytes_once,
                        ) as dynamic_reader,
                        self.assertRaisesRegex(
                            governance_index.ArtifactError,
                            "固定引用路径",
                        ),
                    ):
                        governance_index._evaluate_restructure_wave_snapshot(
                            root,
                            dynamic_plan,
                            dirty_paths=[],
                            head_sha="a" * 40,
                            governance_mismatch_paths=[],
                            evaluated_at=now,
                        )
                    dynamic_reader.assert_not_called()

            wrong_dependency_path = (
                root
                / "TEMP/restructure_wave_preflight/test/"
                "PRIVATE_WRONG_TYPE.json"
            )
            extra_dependency_path = (
                root
                / "TEMP/restructure_wave_preflight/test/"
                "PRIVATE_EXTRA_DEPENDENCY.json"
            )
            _write_json(wrong_dependency_path, {"private": True})
            _write_json(extra_dependency_path, {"private": True})
            invalid_dependency_sets = (
                [
                    {
                        "path": wrong_dependency_path.relative_to(
                            root
                        ).as_posix(),
                        "sha256": governance_index.sha256_file(
                            wrong_dependency_path
                        ),
                        "wave_id": (
                            governance_index.WAVE1_DIRECTORY_REGISTRY
                        ),
                    }
                ],
                [
                    *wave2_plan["dependencies"],
                    {
                        "path": extra_dependency_path.relative_to(
                            root
                        ).as_posix(),
                        "sha256": governance_index.sha256_file(
                            extra_dependency_path
                        ),
                        "wave_id": governance_index.S0_MATERIALIZE_ONLY,
                    },
                ],
            )
            for case_index, dependencies in enumerate(
                invalid_dependency_sets
            ):
                with self.subTest(invalid_dependencies=case_index):
                    invalid_dependency_plan = copy.deepcopy(wave2_plan)
                    invalid_dependency_plan["dependencies"] = dependencies
                    invalid_binding_paths = (
                        set(wave2_spec["required_inputs"])
                        | {
                            invalid_dependency_plan[reference_name]["path"]
                            for reference_name in (
                                "baseline_plan",
                                "baseline_receipt",
                                "decision_ticket",
                                "conflict_lock",
                                "test_impact",
                            )
                        }
                        | {
                            dependency["path"]
                            for dependency in dependencies
                        }
                    )
                    invalid_dependency_plan["bound_inputs"] = [
                        {
                            "path": path,
                            "sha256": "0" * 64,
                            "role": f"invalid_dependency_{index:02d}",
                        }
                        for index, path in enumerate(
                            sorted(invalid_binding_paths),
                            start=1,
                        )
                    ]
                    with (
                        patch.object(
                            governance_index,
                            "_read_repo_bytes_once",
                            wraps=governance_index._read_repo_bytes_once,
                        ) as dependency_reader,
                        self.assertRaisesRegex(
                            governance_index.ArtifactError,
                            "固定引用路径",
                        ),
                    ):
                        governance_index._evaluate_restructure_wave_snapshot(
                            root,
                            invalid_dependency_plan,
                            dirty_paths=[],
                            head_sha="a" * 40,
                            governance_mismatch_paths=[],
                            evaluated_at=now,
                        )
                    dependency_reader.assert_not_called()

            hardlink_source = root / "config/private/hardlink_secret.json"
            _write_json(hardlink_source, {"secret": "must-not-be-read"})
            hardlink_alias = (
                root
                / "config/context_recipes/"
                "wave2_synthetic_json_probe_v1.json"
            )
            hardlink_alias.parent.mkdir(parents=True, exist_ok=True)
            governance_index.os.link(hardlink_source, hardlink_alias)
            with (
                patch.object(
                    governance_index.os,
                    "read",
                    wraps=governance_index.os.read,
                ) as byte_reader,
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "硬链接",
                ),
            ):
                governance_index._read_repo_bytes_once(
                    root,
                    hardlink_alias.relative_to(root).as_posix(),
                )
            byte_reader.assert_not_called()

    def test_restructure_wave_lock_is_fixed_path_and_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, now = _wave_fixture(root)
            lock_path = root / plan["conflict_lock"]["path"]
            request = {
                "contract_version": (
                    governance_index.RESTRUCTURE_WAVE_LOCK_REQUEST_V1
                ),
                "lock_id": "SECOND-LOCK",
                "scope": governance_index.WAVE1_DIRECTORY_REGISTRY,
                "holder": "test-owner",
                "authorization_context_id": "test-context",
                "expected_head_sha": "a" * 40,
                "starts_at": "2026-07-30T00:00:00+08:00",
                "expires_at": "2026-07-31T00:00:00+08:00",
                "candidate_write_paths": list(
                    governance_index.RESTRUCTURE_WAVE_SPECS[
                        governance_index.WAVE1_DIRECTORY_REGISTRY
                    ]["candidate_write_paths"]
                ),
            }
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "拒绝覆盖",
            ):
                governance_index._acquire_restructure_wave_lock_snapshot(
                    root,
                    request,
                    output_path=lock_path.relative_to(root),
                    head_sha="a" * 40,
                    acquired_at=now,
                )
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "固定路径",
            ):
                governance_index._acquire_restructure_wave_lock_snapshot(
                    root,
                    request,
                    output_path=Path(
                        "TEMP/restructure_wave_preflight/locks/other.json"
                    ),
                    head_sha="a" * 40,
                    acquired_at=now,
                )

    def test_restructure_baseline_receipt_stays_under_temp_and_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            allowed = governance_index._receipt_output_path(
                root,
                Path("TEMP/restructure_wave_preflight/example/receipt.json"),
            )
            self.assertTrue(
                str(allowed).endswith(
                    "TEMP/restructure_wave_preflight/example/receipt.json"
                )
            )
            allowed.parent.mkdir(parents=True)
            allowed.write_text("sealed", encoding="utf-8")
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "拒绝覆盖",
            ):
                governance_index._receipt_output_path(
                    root,
                    Path("TEMP/restructure_wave_preflight/example/receipt.json"),
                )
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "只能写入",
            ):
                governance_index._receipt_output_path(
                    root,
                    Path("reports/receipt.json"),
                )

    def test_restructure_receipts_reject_symlinked_temp_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "repo"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "TEMP").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "父目录不得是软链",
            ):
                governance_index._receipt_output_path(
                    root,
                    Path(
                        "TEMP/restructure_wave_preflight/test/receipt.json"
                    ),
                )
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "父目录不得是软链",
            ):
                governance_index._wave_lock_output_path(
                    root,
                    Path(
                        "TEMP/restructure_wave_preflight/locks/"
                        f"{governance_index.WAVE1_DIRECTORY_REGISTRY}.lock.json"
                    ),
                    governance_index.WAVE1_DIRECTORY_REGISTRY,
                )

    def test_exclusive_writer_rejects_intermediate_symlink_swap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "repo"
            outside = base / "outside"
            target = root / "TEMP/restructure_wave_preflight"
            backup = root / "TEMP/restructure_wave_preflight-original"
            target.mkdir(parents=True)
            outside.mkdir()
            real_open = governance_index.os.open
            swapped = False

            def racing_open(path, *args, **kwargs):
                nonlocal swapped
                if (
                    path == "restructure_wave_preflight"
                    and kwargs.get("dir_fd") is not None
                    and not swapped
                ):
                    target.rename(backup)
                    target.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return real_open(path, *args, **kwargs)

            with (
                patch.object(
                    governance_index.os,
                    "open",
                    side_effect=racing_open,
                ),
                self.assertRaises(governance_index.ArtifactError),
            ):
                governance_index._write_json_exclusive(
                    root,
                    Path(
                        "TEMP/restructure_wave_preflight/raced-receipt.json"
                    ),
                    {"status": "PASS"},
                )

            self.assertTrue(swapped)
            self.assertFalse((outside / "raced-receipt.json").exists())

    def test_restructure_gate_rejects_evidence_through_parent_symlink(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "repo"
            root.mkdir()
            plan, now = _wave_fixture(root)
            outside = base / "outside"
            outside.mkdir()
            decision = read_json(root / plan["decision_ticket"]["path"])
            outside_decision = outside / "DECISION_TICKET.json"
            _write_json(outside_decision, decision)
            linked_parent = (
                root
                / "TEMP/restructure_wave_preflight/test/linked-evidence"
            )
            linked_parent.symlink_to(outside, target_is_directory=True)
            old_path = plan["decision_ticket"]["path"]
            new_path = (
                "TEMP/restructure_wave_preflight/test/"
                "linked-evidence/DECISION_TICKET.json"
            )
            plan["decision_ticket"] = {
                "path": new_path,
                "sha256": governance_index.sha256_file(outside_decision),
            }
            binding = next(
                row
                for row in plan["bound_inputs"]
                if row["path"] == old_path
            )
            binding["path"] = new_path
            binding["sha256"] = governance_index.sha256_file(
                outside_decision
            )
            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("decision_ticket_exact", receipt["blockers"])
        self.assertIn("bound_input_sha", receipt["blockers"])

    def test_reference_hash_and_json_use_the_same_opened_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence_path = root / "TEMP/evidence.json"
            old_payload = {"status": "BLOCKED"}
            new_payload = {"status": "PASS"}
            _write_json(evidence_path, old_payload)
            old_bytes = evidence_path.read_bytes()
            reference = {
                "path": "TEMP/evidence.json",
                "sha256": governance_index.sha256_file(evidence_path),
            }

            def read_then_replace(_root, _relative):
                _write_json(evidence_path, new_payload)
                return old_bytes

            with patch.object(
                governance_index,
                "_read_repo_bytes_once",
                side_effect=read_then_replace,
            ):
                payload, evidence = governance_index._reference_payload(
                    root,
                    reference,
                )

        self.assertTrue(evidence["sha256_matched"])
        self.assertEqual(payload, old_payload)

    def test_receipt_write_postcheck_revokes_raced_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "TEMP/restructure_wave_preflight/receipt.json"
            output.parent.mkdir(parents=True)
            output.write_text("{}\n", encoding="utf-8")
            receipt = {
                "checks": [
                    {
                        "check_id": "live_snapshot_stable",
                        "passed": True,
                        "evidence": {
                            "after": {
                                "head_sha": "a" * 40,
                                "dirty_paths": [],
                                "governance_mismatch_paths": [],
                            }
                        },
                    }
                ]
            }
            with (
                patch.object(
                    governance_index,
                    "_live_restructure_snapshot",
                    return_value={
                        "head_sha": "b" * 40,
                        "dirty_paths": ["foreign.txt"],
                        "governance_mismatch_paths": [],
                    },
                ),
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "已撤销新票",
                ),
            ):
                governance_index._verify_snapshot_after_receipt_write(
                    root,
                    receipt,
                    output.resolve(),
                )

            self.assertFalse(output.exists())

    def test_receipt_write_postcheck_revalidates_all_evidence_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence_path = root / "TEMP/evidence.json"
            output = root / "TEMP/restructure_wave_preflight/receipt.json"
            _write_json(evidence_path, {"status": "PASS"})
            output.parent.mkdir(parents=True)
            output.write_text("{}\n", encoding="utf-8")
            snapshot = {
                "head_sha": "a" * 40,
                "dirty_paths": [],
                "governance_mismatch_paths": [],
            }
            receipt = {
                "checks": [
                    {
                        "check_id": "live_snapshot_stable",
                        "passed": True,
                        "evidence": {"after": snapshot},
                    }
                ],
                "evidence_snapshot": [
                    {
                        "path": "TEMP/evidence.json",
                        "sha256": governance_index.sha256_file(
                            evidence_path
                        ),
                    }
                ],
            }
            _write_json(evidence_path, {"status": "CHANGED"})
            with (
                patch.object(
                    governance_index,
                    "_live_restructure_snapshot",
                    return_value=snapshot,
                ),
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "受绑定证据发生变化",
                ),
            ):
                governance_index._verify_snapshot_after_receipt_write(
                    root,
                    receipt,
                    output.resolve(),
                )

            self.assertFalse(output.exists())

    def test_wave_lock_postcheck_revokes_dirty_snapshot_race(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wave_id = governance_index.WAVE1_DIRECTORY_REGISTRY
            output = Path(
                "TEMP/restructure_wave_preflight/locks/"
                f"{wave_id}.lock.json"
            )
            request = {
                "contract_version": (
                    governance_index.RESTRUCTURE_WAVE_LOCK_REQUEST_V1
                ),
                "lock_id": "RACE-LOCK",
                "scope": wave_id,
                "holder": "test-owner",
                "authorization_context_id": "test-context",
                "expected_head_sha": "a" * 40,
                "starts_at": "2026-07-30T00:00:00+08:00",
                "expires_at": "2026-07-31T00:00:00+08:00",
                "candidate_write_paths": list(
                    governance_index.RESTRUCTURE_WAVE_SPECS[wave_id][
                        "candidate_write_paths"
                    ]
                ),
            }
            before = {
                "head_sha": "a" * 40,
                "dirty_paths": [],
                "governance_mismatch_paths": [],
            }
            after = {
                **before,
                "dirty_paths": ["governance/directory_registry.json"],
            }
            with (
                patch.object(
                    governance_index,
                    "_live_restructure_snapshot",
                    side_effect=[before, after],
                ),
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "已撤销新锁",
                ),
            ):
                governance_index.acquire_restructure_wave_lock(
                    root,
                    request,
                    output_path=output,
                    acquired_at=datetime(
                        2026,
                        7,
                        30,
                        5,
                        0,
                        tzinfo=timezone.utc,
                    ),
                )

            self.assertFalse((root / output).exists())

    def test_public_restructure_gates_do_not_accept_injected_git_snapshots(
        self,
    ) -> None:
        for function in (
            governance_index.evaluate_restructure_baseline,
            governance_index.evaluate_restructure_wave,
            governance_index.evaluate_restructure_wave_completion_v2,
            governance_index.acquire_restructure_wave_lock,
        ):
            parameters = inspect.signature(function).parameters
            self.assertNotIn("dirty_paths", parameters)
            self.assertNotIn("head_sha", parameters)
            self.assertNotIn("governance_mismatch_paths", parameters)

    def test_wave5_gate_passes_only_for_three_fixed_external_manifests(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, plan, now, _ = _wave5_fixture(Path(temporary))
            prior_reference = governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY
            ]["required_prior_decision_ticket"]

            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["blockers"], [])
            self.assertEqual(
                governance_index.sha256_file(root / prior_reference["path"]),
                prior_reference["sha256"],
            )
            self.assertEqual(
                len(receipt["external_evidence_snapshot"]),
                3,
            )
            self.assertEqual(
                sum(
                    row["entries"]
                    for row in receipt["external_evidence_snapshot"]
                ),
                148,
            )
            self.assertTrue(
                receipt["authorization_boundary"][
                    "same_task_construction_authorization_recorded"
                ]
            )
            self.assertFalse(
                receipt["authorization_boundary"][
                    "authorizes_external_manifest_rewrite"
                ]
            )

    def test_wave5_gate_rejects_upstream_s0_self_reported_sha_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, plan, now, _ = _wave5_fixture(Path(temporary))
            prior_reference = governance_index.RESTRUCTURE_WAVE_SPECS[
                governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY
            ]["required_prior_decision_ticket"]
            prior_path = root / prior_reference["path"]
            prior_payload = read_json(prior_path)
            _write_json(prior_path, prior_payload)
            changed_prior_sha = governance_index.sha256_file(prior_path)
            self.assertNotEqual(
                changed_prior_sha,
                prior_reference["sha256"],
            )

            decision_path = root / plan["decision_ticket"]["path"]
            decision = read_json(decision_path)
            decision["upstream_decision"]["sha256"] = changed_prior_sha
            _write_json(decision_path, decision)
            _refresh_plan_reference(plan, "decision_ticket", decision_path)
            next(
                row
                for row in plan["bound_inputs"]
                if row["path"] == prior_reference["path"]
            )["sha256"] = changed_prior_sha

            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

            self.assertEqual(receipt["status"], "BLOCKED")
            self.assertIn("decision_ticket_exact", receipt["blockers"])
            decision_check = next(
                row
                for row in receipt["checks"]
                if row["check_id"] == "decision_ticket_exact"
            )
            self.assertIn(
                "固定路径和 SHA",
                json.dumps(decision_check, ensure_ascii=False),
            )

    def test_wave5_gate_blocks_manifest_sha_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, plan, now, external_root = _wave5_fixture(
                Path(temporary)
            )
            manifest = (
                external_root
                / "archive_batch_slim_20260723/MANIFEST.json"
            )
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["entries"].append({"path": "late-entry"})
            _write_json(manifest, payload)

            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

            self.assertEqual(receipt["status"], "BLOCKED")
            self.assertIn("decision_ticket_exact", receipt["blockers"])
            self.assertIn(
                "external_manifest_snapshot_stable",
                receipt["blockers"],
            )

    def test_wave5_gate_rejects_external_parent_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, plan, now, external_root = _wave5_fixture(
                Path(temporary)
            )
            batch = external_root / "archive_batch_20260723"
            real_batch = external_root / "archive_batch_real"
            batch.rename(real_batch)
            batch.symlink_to(real_batch, target_is_directory=True)

            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

            self.assertEqual(receipt["status"], "BLOCKED")
            decision_check = next(
                row
                for row in receipt["checks"]
                if row["check_id"] == "decision_ticket_exact"
            )
            self.assertIn(
                "旧批次目录不得是软链",
                json.dumps(decision_check, ensure_ascii=False),
            )

    def test_wave5_gate_rejects_external_manifest_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, plan, now, external_root = _wave5_fixture(
                Path(temporary)
            )
            manifest = (
                external_root
                / "archive_batch_slim_overlay_z94_20260723/MANIFEST.json"
            )
            alias = manifest.with_name("MANIFEST.alias.json")
            alias.hardlink_to(manifest)

            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )

            self.assertEqual(receipt["status"], "BLOCKED")
            decision_check = next(
                row
                for row in receipt["checks"]
                if row["check_id"] == "decision_ticket_exact"
            )
            self.assertIn(
                "不得是硬链接",
                json.dumps(decision_check, ensure_ascii=False),
            )

    def test_wave5_plan_rejects_dependency_and_path_prefix_expansion(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, plan, _, _ = _wave5_fixture(Path(temporary))
            plan["dependencies"] = [
                {
                    "path": plan["decision_ticket"]["path"],
                    "sha256": plan["decision_ticket"]["sha256"],
                    "wave_id": governance_index.WAVE2_RULE_BUNDLES,
                }
            ]
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "依赖类型",
            ):
                governance_index._wave_plan(copy.deepcopy(plan))

            plan["dependencies"] = []
            plan["responsibility_window"]["read_allowlist"][
                plan["responsibility_window"]["read_allowlist"].index(
                    "config/README.md"
                )
            ] = "config"
            with self.assertRaisesRegex(
                governance_index.ArtifactError,
                "读取范围完全相等",
            ):
                governance_index._wave_plan(copy.deepcopy(plan))

    def test_wave5_post_write_verifier_rechecks_external_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, plan, now, external_root = _wave5_fixture(
                Path(temporary)
            )
            receipt = governance_index._evaluate_restructure_wave_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=now,
            )
            snapshot = {
                "head_sha": "a" * 40,
                "dirty_paths": [],
                "governance_mismatch_paths": [],
            }
            receipt["checks"].append(
                {
                    "check_id": "live_snapshot_stable",
                    "passed": True,
                    "evidence": {"before": snapshot, "after": snapshot},
                }
            )
            output = (
                root
                / "TEMP/restructure_wave_preflight/test/WAVE5_RECEIPT.json"
            )
            _write_json(output, receipt)
            manifest = (
                external_root
                / "archive_batch_20260723/MANIFEST.json"
            )
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["changed_after_receipt"] = True
            _write_json(manifest, payload)

            with (
                patch.object(
                    governance_index,
                    "_live_restructure_snapshot",
                    return_value=snapshot,
                ),
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "受绑定证据发生变化",
                ),
            ):
                governance_index._verify_snapshot_after_receipt_write(
                    root,
                    receipt,
                    output,
                )

            self.assertFalse(output.exists())

    def test_wave5_completion_replays_external_evidence_not_passed_flags(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, plan, now, _ = _wave5_fixture(Path(temporary))
            source_receipt = (
                governance_index._evaluate_restructure_wave_snapshot(
                    root,
                    plan,
                    dirty_paths=[],
                    head_sha="a" * 40,
                    governance_mismatch_paths=[],
                    evaluated_at=now,
                )
            )
            source_receipt["checks"].append(
                {
                    "check_id": "live_snapshot_stable",
                    "passed": True,
                    "evidence": {"fixture": True},
                }
            )
            plan_path = (
                root
                / "TEMP/restructure_wave_preflight/test/"
                "WAVE5_COMPLETION_SOURCE_PLAN.json"
            )
            receipt_path = (
                root
                / "TEMP/restructure_wave_preflight/test/"
                "WAVE5_COMPLETION_SOURCE_RECEIPT.json"
            )
            _write_json(plan_path, plan)
            _write_json(receipt_path, source_receipt)
            request = {
                "contract_version": (
                    governance_index.RESTRUCTURE_WAVE_COMPLETION_REQUEST_V2
                ),
                "completion_id": "WAVE5-COMPLETION-REPLAY-TEST",
                "wave_id": (
                    governance_index.WAVE5_EXTERNAL_ARCHIVE_READONLY
                ),
                "authorization_context_id": (
                    "019fa2e0-08a5-7110-b263-a183b0230f3c"
                ),
                "pre_commit_sha": "a" * 40,
                "post_commit_sha": "b" * 40,
                "wave_plan": {
                    "path": plan_path.relative_to(root).as_posix(),
                    "sha256": governance_index.sha256_file(plan_path),
                },
                "wave_receipt": {
                    "path": receipt_path.relative_to(root).as_posix(),
                    "sha256": governance_index.sha256_file(receipt_path),
                },
            }
            git_changes = [
                {"status": "M", "path": "governance/README.md"}
            ]
            blob_evidence = {
                "path": "governance/README.md",
                "git_mode": "100644",
                "git_blob_sha": "c" * 40,
                "bytes": 1,
                "sha256": "d" * 64,
            }
            with (
                patch.object(
                    governance_index,
                    "git_commit_exists",
                    return_value=True,
                ),
                patch.object(
                    governance_index,
                    "git_is_ancestor",
                    return_value=True,
                ),
                patch.object(
                    governance_index,
                    "git_name_status_between_exact",
                    return_value=git_changes,
                ),
                patch.object(
                    governance_index,
                    "git_blob_evidence",
                    return_value=blob_evidence,
                ),
            ):
                valid = (
                    governance_index.evaluate_restructure_wave_completion_v2(
                        root,
                        request,
                    )
                )
                forged_receipt = copy.deepcopy(source_receipt)
                forged_receipt.pop("external_evidence_snapshot")
                _write_json(receipt_path, forged_receipt)
                request["wave_receipt"]["sha256"] = (
                    governance_index.sha256_file(receipt_path)
                )
                forged = (
                    governance_index.evaluate_restructure_wave_completion_v2(
                        root,
                        request,
                    )
                )

            self.assertEqual(valid["status"], "GIT_SCOPE_PASS")
            self.assertEqual(forged["status"], "BLOCKED")
            self.assertIn(
                "source_wave5_external_evidence_replayed",
                forged["blockers"],
            )

    def test_completion_v2_cli_arguments_are_a_paired_mode(self) -> None:
        parser = governance_index.build_parser()
        args = parser.parse_args(
            [
                "--wave-completion-request",
                "TEMP/request.json",
                "--wave-completion-output",
                "TEMP/receipt.json",
            ]
        )
        self.assertEqual(args.wave_completion_request, Path("TEMP/request.json"))
        self.assertEqual(args.wave_completion_output, Path("TEMP/receipt.json"))

    def test_completion_v2_cli_removes_new_receipt_when_replay_raises(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request_path = root / "TEMP/request.json"
            _write_json(request_path, {"fixture": True})
            output = Path(
                "TEMP/restructure_wave_preflight/test/COMPLETION.json"
            )
            receipt = {"status": "GIT_SCOPE_PASS", "blockers": []}
            with (
                patch.object(governance_index, "ROOT", root),
                patch.object(
                    governance_index,
                    "evaluate_restructure_wave_completion_v2",
                    side_effect=[
                        receipt,
                        governance_index.ArtifactError("replay drift"),
                    ],
                ),
                self.assertRaisesRegex(
                    governance_index.ArtifactError,
                    "已撤销新票",
                ),
            ):
                governance_index.main(
                    [
                        "--wave-completion-request",
                        str(request_path),
                        "--wave-completion-output",
                        output.as_posix(),
                    ]
                )

            self.assertFalse((root / output).exists())


if __name__ == "__main__":
    unittest.main()
