"""Build and verify deterministic B-07 offline artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    sha256_value,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.fixtures import (  # noqa: E402
    build_environment,
)

OBJECT_SHAPES = ROOT / "OBJECT_SHAPES.json"
REPORT = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST = ROOT / "MANIFEST.sha256"


def fixed_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ccz57-b07-self-check-") as directory:
        base = Path(directory)

        env = build_environment(base / "N01_OPEN_RESUME_PLAN")
        state = env.open()
        plan = env.b07.derive_resume_plan(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            authority_reader=env.authority,
        )
        vectors.append(
            {
                "fixture_id": "N01_OPEN_RESUME_PLAN",
                "state_hash": state["state_hash"],
                "status": state["status"],
                "plan_hash": plan["plan_hash"],
                "disposition": plan["disposition"],
            }
        )

        env = build_environment(base / "N02_STOP_REOPEN")
        state = env.bind_terminal_observation(
            env.open(), operation_id="bind-self-check-stop", marker="self-check-stop"
        )
        receipt = env.b07.stop(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="stop-self-check",
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"],
            stop_reason_code="AUTHOR_ABORTED",
            stop_class="LOCAL_CONTROL",
            stop_source="SELF_CHECK",
            authority_reader=env.authority,
        )
        reopened = env.b07.reopen(
            project_scope_id=env.project_scope_id,
            source_run_id=env.run_id,
            new_run_id="run-b07-self-check-reopened",
            operation_id="reopen-self-check",
            authority_reader=env.authority,
        )
        vectors.append(
            {
                "fixture_id": "N02_STOP_REOPEN",
                "stop_receipt_hash": receipt["record_hash"],
                "old_status": env.b07.read_state(env.project_scope_id, env.run_id)[
                    "status"
                ],
                "new_generation": reopened["logical_run_generation"],
                "visible_counts": env.b07.visible_counts(),
            }
        )

        env = build_environment(base / "N03_B06_ACK_LOST")
        state = env.open()
        pending, fence = env.prepare_b06(state)
        committed = env.commit_b06(run_fence=fence)
        env.authority.sync_pointer(committed["current_pointer"])
        reconciled = env.b07.reconcile_b06(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="reconcile-self-check",
            expected_run_epoch=pending["run_epoch"],
            expected_state_revision=pending["state_revision"],
            authority_reader=env.authority,
        )
        replay = env.commit_b06(run_fence=fence)
        vectors.append(
            {
                "fixture_id": "N03_B06_ACK_LOST",
                "status": reconciled["status"],
                "pending_cleared": reconciled["pending_local_action"] is None,
                "replay_reused": replay["reused_existing_commit"],
                "b06_visible_counts": env.b06.store.visible_counts(),
            }
        )

        env = build_environment(base / "F01_STOP_ROLLBACK")
        state = env.bind_terminal_observation(
            env.open(),
            operation_id="bind-self-check-rollback",
            marker="self-check-rollback",
        )
        env.b07.failure_point = "after_stop_receipt_insert"
        error_code = None
        try:
            env.b07.stop(
                project_scope_id=env.project_scope_id,
                run_id=env.run_id,
                operation_id="stop-failure-self-check",
                expected_run_epoch=state["run_epoch"],
                expected_state_revision=state["state_revision"],
                stop_reason_code="AUTHOR_ABORTED",
                stop_class="LOCAL_CONTROL",
                stop_source="SELF_CHECK",
                authority_reader=env.authority,
            )
        except ValueError as error:
            error_code = str(error).split(":", 1)[0]
        vectors.append(
            {
                "fixture_id": "F01_STOP_ROLLBACK",
                "error_code": error_code,
                "state_unchanged": env.b07.read_state(env.project_scope_id, env.run_id)
                == state,
                "visible_counts": env.b07.visible_counts(),
            }
        )

        env = build_environment(base / "F02_PENDING_STOP_DENIED")
        state = env.open()
        pending, fence = env.prepare_b06(state)
        error_code = None
        try:
            env.b07.stop(
                project_scope_id=env.project_scope_id,
                run_id=env.run_id,
                operation_id="stop-before-b06-self-check",
                expected_run_epoch=pending["run_epoch"],
                expected_state_revision=pending["state_revision"],
                stop_reason_code="AUTHOR_ABORTED",
                stop_class="LOCAL_CONTROL",
                stop_source="SELF_CHECK",
                authority_reader=env.authority,
            )
        except ValueError as error:
            error_code = str(error).split(":", 1)[0]
        committed = env.commit_b06(run_fence=fence)
        vectors.append(
            {
                "fixture_id": "F02_PENDING_STOP_DENIED",
                "error_code": error_code,
                "b06_committed": committed["reused_existing_commit"] is False,
                "b06_visible_counts": env.b06.store.visible_counts(),
                "b07_visible_counts": env.b07.visible_counts(),
            }
        )
    return vectors


def build_object_shapes() -> dict[str, Any]:
    value = {
        "document_identity": "CCZ57-M3-B07-LOCAL-RECOVERY-STOP-R01",
        "persistent_product_types": [
            "M3_CURRENT_RUN_STATE",
            "M3_RUN_STOP_RECEIPT",
            "M3_RUN_INTERNAL_DEBUG_RECORD",
        ],
        "derived_views": ["M3_DERIVED_RESUME_PLAN"],
        "private_storage_helpers": ["b07_run_command_dedupe"],
        "writer_map": {
            "M3_CURRENT_RUN_STATE": "RunController",
            "M3_RUN_STOP_RECEIPT": "RunController",
            "M3_RUN_INTERNAL_DEBUG_RECORD": "RunController.InternalDebugWriter",
            "M3_DERIVED_RESUME_PLAN": None,
        },
        "transaction_domain": "b06-commit-core.sqlite3",
        "b06_boundary": {
            "b06_reads_b07_fence": True,
            "b06_writes_b07_objects": 0,
            "b07_writes_b06_objects": 0,
            "receipt_replay_before_fence": True,
        },
        "ccz142_saved_artifact_ref": {
            "artifact_kind": "required",
            "workspace_relative_locator": "required",
            "artifact_sha256": "required",
            "b05_record_ref_required": False,
            "component_contract_version_required": False,
            "caller_result_class_accepted": False,
        },
        "forbidden_persistent_types": [
            "M3_CHECKPOINT",
            "M3_COMMIT_INTENT",
            "M3_PROVIDER_CHECKPOINT",
            "M3_RESUME_PLAN_RECORD",
            "M3_FAILED_COMMIT_RECEIPT",
        ],
        "debug_limits": {
            "single_record_bytes": 4096,
            "records_per_run": 32,
            "total_bytes_per_run": 65536,
            "default_retention_days": 7,
            "hard_retention_days_without_new_policy": 30,
        },
        "fixed_vectors": fixed_vectors(),
        "catalog_hash": "",
    }
    value["catalog_hash"] = sha256_value(
        {key: item for key, item in value.items() if key != "catalog_hash"}
    )
    return value


def build_report(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_kind": "CCZ57_M3_B07_LOCAL_RECOVERY_STOP_R01_OFFLINE_REPLAY",
        "mechanical_pass": True,
        "targeted_pytest_expected": "39 passed",
        "b06_regression_expected": "25 passed",
        "fixed_vector_count": len(catalog["fixed_vectors"]),
        "catalog_hash": catalog["catalog_hash"],
        "persistent_product_type_count": 3,
        "derived_resume_plan_count": 1,
        "checkpoint_type_count": 0,
        "commit_intent_dependency_count": 0,
        "provider_checkpoint_type_count": 0,
        "persisted_resume_plan_type_count": 0,
        "b07_candidate_version_writes": 0,
        "b07_pointer_writes": 0,
        "b07_merge_receipt_writes": 0,
        "real_model_api_calls": 0,
        "network_calls": 0,
        "real_novel_reads": 0,
        "formal_fact_writes": 0,
        "ten_ledger_writes": 0,
        "semantic_accuracy": None,
        "speed_improvement": None,
        "token_improvement": None,
        "ccz142_exact_adapter_complete": False,
        "ccz142_saved_artifact_adapter_complete": True,
        "ccz142_result_classification_complete": False,
        "pr_gate": "NOT_RUN_LOCAL_CONSTRUCTION",
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.parent != ROOT:
        raise AssertionError("B07_ARTIFACT_PATH_ESCAPE")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def refresh_manifest() -> int:
    members = sorted(
        path for path in ROOT.iterdir() if path.is_file() and path.name != MANIFEST.name
    )
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in members
    ]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def verify_manifest() -> int:
    count = 0
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        path = ROOT / relative
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise AssertionError(f"B07_MANIFEST_MISMATCH:{relative}")
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-artifacts", action="store_true")
    parser.add_argument("--refresh-manifest", action="store_true")
    args = parser.parse_args()
    catalog = build_object_shapes()
    report = build_report(catalog)
    if args.refresh_artifacts:
        _write_json(OBJECT_SHAPES, catalog)
        _write_json(REPORT, report)
        print("B07_R01_ARTIFACTS_REFRESHED")
        return 0
    if args.refresh_manifest:
        print(f"B07_R01_MANIFEST_REFRESHED={refresh_manifest()}")
        return 0
    if json.loads(OBJECT_SHAPES.read_text(encoding="utf-8")) != catalog:
        raise AssertionError("B07_OBJECT_SHAPES_DRIFT")
    if json.loads(REPORT.read_text(encoding="utf-8")) != report:
        raise AssertionError("B07_OFFLINE_REPORT_DRIFT")
    manifest_count = verify_manifest()
    print(
        "B07_R01_SELF_CHECK=PASS; "
        f"vectors={len(catalog['fixed_vectors'])}; manifest={manifest_count}; "
        f"catalog={catalog['catalog_hash']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
