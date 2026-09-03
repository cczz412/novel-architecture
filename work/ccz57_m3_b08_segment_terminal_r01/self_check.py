"""Build and verify deterministic B-08 offline artifacts."""

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
from work.ccz57_m3_b08_segment_terminal_r01.fixtures import (  # noqa: E402
    build_environment,
)

OBJECT_SHAPES = ROOT / "OBJECT_SHAPES.json"
REPORT = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST = ROOT / "MANIFEST.sha256"


def fixed_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ccz57-b08-self-check-") as directory:
        base = Path(directory)

        env = build_environment(base / "N01_COMPLETE_CURRENT")
        result = env.publish()
        env.bind_succeeded(result)
        exact = env.reader.exact_current_view(result["terminal_record_ref"])
        adapter = env.reader.adapter_ready_view(result["terminal_record_ref"])
        vectors.append(
            {
                "fixture_id": "N01_COMPLETE_CURRENT",
                "terminal_record_hash": result["terminal_record"]["record_hash"],
                "currentness": exact["currentness"],
                "exact_view_hash": exact["view_hash"],
                "adapter_ready": adapter["ready"],
                "adapter_view_hash": adapter["view_hash"],
                "visible_counts": env.store.visible_counts(),
            }
        )

        env = build_environment(base / "N02_PARTIAL_STOPPED")
        env.authority.classification.update(
            {
                "product_result": "INSUFFICIENT_EVIDENCE",
                "terminal_delivery": "PARTIAL",
                "reason_code": "EVIDENCE_GAP_REMAINS",
                "expected_unit_count": 2,
                "covered_unit_count": 1,
                "missing_unit_count": 1,
                "coverage_complete": False,
            }
        )
        result = env.publish()
        env.bind_then_stop(result)
        exact = env.reader.exact_current_view(result["terminal_record_ref"])
        adapter = env.reader.adapter_ready_view(result["terminal_record_ref"])
        vectors.append(
            {
                "fixture_id": "N02_PARTIAL_STOPPED",
                "terminal_record_hash": result["terminal_record"]["record_hash"],
                "currentness": exact["currentness"],
                "delivery": exact["terminal_delivery"],
                "adapter_ready": adapter["ready"],
                "b07_status": env.state()["status"],
            }
        )

        env = build_environment(base / "N03_B06_CHILD")
        env.commit_b06_child()
        result = env.publish()
        vectors.append(
            {
                "fixture_id": "N03_B06_CHILD",
                "candidate_origin": result["terminal_record"]["payload"][
                    "pointer_binding"
                ]["candidate_origin"],
                "merge_receipt_bound": result["terminal_record"]["payload"][
                    "b06_merge_receipt_ref_or_null"
                ]
                is not None,
                "terminal_record_hash": result["terminal_record"]["record_hash"],
            }
        )

        env = build_environment(
            base / "F01_TRANSACTION_ROLLBACK",
            failure_point="after_terminal_insert",
        )
        error_code = None
        try:
            env.publish()
        except ValueError as error:
            error_code = str(error).split(":", 1)[0]
        vectors.append(
            {
                "fixture_id": "F01_TRANSACTION_ROLLBACK",
                "error_code": error_code,
                "visible_counts": env.store.visible_counts(),
            }
        )

        env = build_environment(base / "F02_RESUME_SUPERSEDES")
        result = env.publish()
        state = env.state()
        env.b07.b07.resume(
            project_scope_id=env.project_scope_id,
            run_id=env.run_id,
            operation_id="resume-self-check",
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"],
            authority_reader=env.b07.authority,
        )
        exact = env.reader.exact_current_view(result["terminal_record_ref"])
        vectors.append(
            {
                "fixture_id": "F02_RESUME_SUPERSEDES",
                "currentness": exact["currentness"],
                "old_run_epoch": result["terminal_record"]["payload"]["run_binding"][
                    "run_epoch"
                ],
                "current_run_epoch": env.state()["run_epoch"],
                "visible_counts": env.store.visible_counts(),
            }
        )
    return vectors


def build_object_shapes() -> dict[str, Any]:
    value = {
        "document_identity": "CCZ57-M3-B08-SEGMENT-TERMINAL-R01",
        "transaction_domain": "b06-commit-core.sqlite3",
        "persistent_product_types": [
            "M3_SEGMENT_CANDIDATE_TERMINAL_RECEIPT"
        ],
        "writer_map": {
            "M3_SEGMENT_CANDIDATE_TERMINAL_RECEIPT": "B08SegmentTerminalStore",
            "M3_EXACT_CURRENT_SEGMENT_TERMINAL_VIEW": None,
            "M3_ADAPTER_READY_SEGMENT_VIEW": None,
        },
        "derived_views": [
            "M3_EXACT_CURRENT_SEGMENT_TERMINAL_VIEW",
            "M3_ADAPTER_READY_SEGMENT_VIEW",
        ],
        "authority_reader": {
            "constructor_owned": True,
            "caller_result_fields": 0,
            "shared_sqlite_read": True,
            "ccz142_product_adapter_connected": False,
        },
        "run_binding": [
            "logical_run_generation",
            "run_epoch",
            "finalized_from_state_revision",
            "finalized_from_state_hash",
        ],
        "current_binding": [
            "chapter_revision_ref",
            "segment_scope_hash",
            "source_generation_ref",
            "pointer_generation",
            "current_candidate_version_ref",
            "b07_last_component_observation",
        ],
        "product_results": [
            "CANDIDATES_READY",
            "NO_CHANGE",
            "LEGAL_ZERO",
            "NOT_APPLICABLE",
            "INSUFFICIENT_EVIDENCE",
            "EXTRACTION_FAILED",
        ],
        "terminal_deliveries": [
            "COMPLETE",
            "EMPTY_VALID",
            "PARTIAL",
            "BLOCKED",
        ],
        "forbidden_persistent_types": [
            "M3_SEGMENT_STALE_RECORD",
            "M3_EXACT_CURRENT_SEGMENT_TERMINAL_VIEW_RECORD",
            "M3_ADAPTER_READY_SEGMENT_VIEW_RECORD",
            "M3_CHECKPOINT",
            "M3_COMMIT_INTENT",
            "M3_POINTER_SNAPSHOT",
        ],
        "b07_boundary": {
            "new_b07_statuses": 0,
            "new_b07_fields": 0,
            "new_b07_writers": 0,
            "uses_active_finalizing": True,
            "uses_last_component_observation": True,
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
        "report_kind": "CCZ57_M3_B08_SEGMENT_TERMINAL_R01_OFFLINE_REPLAY",
        "mechanical_pass": True,
        "targeted_pytest_expected": "29 passed",
        "direct_dependency_regression_expected": "165 passed",
        "fixed_vector_count": len(catalog["fixed_vectors"]),
        "catalog_hash": catalog["catalog_hash"],
        "persistent_product_type_count": 1,
        "writer_count": 1,
        "derived_view_count": 2,
        "derived_view_writer_count": 0,
        "new_b07_status_count": 0,
        "new_b07_field_count": 0,
        "b08_candidate_version_writes": 0,
        "b08_pointer_writes": 0,
        "b08_merge_receipt_writes": 0,
        "b08_formal_fact_writes": 0,
        "real_model_api_calls": 0,
        "network_calls": 0,
        "real_novel_reads": 0,
        "ten_ledger_writes": 0,
        "semantic_accuracy": None,
        "speed_improvement": None,
        "token_improvement": None,
        "ccz142_product_authority_reader_connected": False,
        "pr_gate": "NOT_RUN_LOCAL_CONSTRUCTION",
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.parent != ROOT:
        raise AssertionError("B08_ARTIFACT_PATH_ESCAPE")
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
            raise AssertionError(f"B08_MANIFEST_MISMATCH:{relative}")
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
        print("B08_R01_ARTIFACTS_REFRESHED")
        return 0
    if args.refresh_manifest:
        print(f"B08_R01_MANIFEST_REFRESHED={refresh_manifest()}")
        return 0
    if json.loads(OBJECT_SHAPES.read_text(encoding="utf-8")) != catalog:
        raise AssertionError("B08_OBJECT_SHAPES_DRIFT")
    if json.loads(REPORT.read_text(encoding="utf-8")) != report:
        raise AssertionError("B08_OFFLINE_REPORT_DRIFT")
    manifest_count = verify_manifest()
    print(
        "B08_R01_SELF_CHECK=PASS; "
        f"vectors={len(catalog['fixed_vectors'])}; manifest={manifest_count}; "
        f"catalog={catalog['catalog_hash']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
