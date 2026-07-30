from __future__ import annotations

import copy
import inspect
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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
            "https://app.notion.com/p/e1eb141272b24db3afd5cf95b5cfe2c6",
        )
        self.assertEqual(
            state["authority"]["external_truth"]["legacy_frozen_ledger_url"],
            "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c",
        )
        self.assertEqual(
            state["authority"]["external_truth"]["queue_url"],
            "https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc",
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

    def test_index_answers_four_questions_and_demotes_old_routes(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        current_state = read_json(ROOT / governance_index.CURRENT_STATE_PATH)
        route_registry = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        source = read_json(ROOT / governance_index.REGISTRY_SOURCE_PATH)
        registry = governance_index.materialize_registry(ROOT, source)
        documents = governance_index.build_documents(
            ROOT, control, current_state, route_registry, registry
        )
        index = documents["governance/INDEX.md"]
        for phrase in ("现在跑到哪道", "金标哪版哪指针", "各模块什么状态", "银标候选在哪"):
            self.assertIn(phrase, index)
        current, _history = governance_index.state_layers(current_state)
        self.assertIn(current["task"]["label"], index)
        self.assertIn(current["task"]["status_label"], index)
        self.assertIn(current["controls"]["next_action"], index)
        self.assertNotIn("retry01 第3章 HTTP 200", index)
        route = documents["governance/indexes/route_health.md"]
        self.assertIn("current.md", route)
        self.assertIn("governance/INDEX.md", route)
        self.assertIn("tools/zbatch_modules/README.md", route)

    def test_generated_current_pages_do_not_render_historical_context(self) -> None:
        control = read_json(ROOT / governance_index.CONTROL_PATH)
        current_state = _as_v2(read_json(ROOT / governance_index.CURRENT_STATE_PATH))
        routes = read_json(ROOT / governance_index.ROUTE_REGISTRY_PATH)
        source = read_json(ROOT / governance_index.REGISTRY_SOURCE_PATH)
        registry = governance_index.materialize_registry(ROOT, source)
        current_state["current_execution"]["task"]["label"] = "V2当前任务唯一标记"
        current_state["current_execution"]["controls"]["next_action"] = "V2当前下一动作唯一标记"
        current_state["historical_context"]["legacy_mainline"][
            "label"
        ] = "禁止出现在路牌的历史标记"
        current_state["historical_context"]["issue_ledger"][0][
            "summary"
        ] = "禁止出现在路牌的历史问题标记"
        control["recent_score"]["path"] = "禁止出现在当前页的历史成绩标记"

        documents = governance_index.build_documents(
            ROOT,
            control,
            current_state,
            routes,
            registry,
        )
        for relative in ("governance/INDEX.md", "governance/current_run.md"):
            text = documents[relative]
            self.assertIn("V2当前任务唯一标记", text)
            self.assertIn("V2当前下一动作唯一标记", text)
            self.assertNotIn("禁止出现在路牌的历史标记", text)
            self.assertNotIn("禁止出现在路牌的历史问题标记", text)
            self.assertNotIn("禁止出现在当前页的历史成绩标记", text)

    def test_root_readme_has_one_hop_governance_route(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[治理索引](governance/INDEX.md)", readme)

    def test_test_command_is_one_fixed_tests_only_command(self) -> None:
        policy = read_json(ROOT / "governance/test_policy.json")
        expected = (
            "cd /Users/a1234/挣钱/小说架构 && "
            "/Users/a1234/挣钱/小说架构/.venv/bin/python -m pytest -q"
        )
        self.assertEqual(policy["full_chain_command"], expected)
        self.assertIn(expected, (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(expected, (ROOT / "governance/README.md").read_text(encoding="utf-8"))

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
            receipt = governance_index._evaluate_restructure_baseline_snapshot(
                root,
                plan,
                dirty_paths=[],
                head_sha="a" * 40,
                governance_mismatch_paths=[],
                evaluated_at=datetime(2026, 7, 30, 5, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("read_allowlist_complete", receipt["blockers"])

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
            governance_index.acquire_restructure_wave_lock,
        ):
            parameters = inspect.signature(function).parameters
            self.assertNotIn("dirty_paths", parameters)
            self.assertNotIn("head_sha", parameters)
            self.assertNotIn("governance_mismatch_paths", parameters)


if __name__ == "__main__":
    unittest.main()
