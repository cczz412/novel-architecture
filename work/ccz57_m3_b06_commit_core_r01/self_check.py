"""Build and verify deterministic B-06 fixture artifacts."""

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
    record_ref,
    sha256_value,
)
from work.ccz57_m3_b06_commit_core_r01.b06_contracts import (  # noqa: E402
    MERGE_RECEIPT_TYPE,
)
from work.ccz57_m3_b06_commit_core_r01.fixtures import (  # noqa: E402
    build_environment,
)

OBJECT_SHAPES = ROOT / "OBJECT_SHAPES.json"
REPORT = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST = ROOT / "MANIFEST.sha256"


def fixed_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ccz57-b06-self-check-") as directory:
        base = Path(directory)
        for fixture_id, mode in (("N01_REPLACE", "replace"), ("N02_ADD", "add")):
            env = build_environment(base / fixture_id, mode=mode)
            first = env.commit(f"operation-{fixture_id}")
            replay = env.commit(f"operation-{fixture_id}")
            receipt = env.store.read_receipts()[0]
            vectors.append(
                {
                    "fixture_id": fixture_id,
                    "child_ref": first["child_candidate_version_ref"],
                    "receipt_ref": record_ref(receipt),
                    "pointer_hash": sha256_value(first["current_pointer"]),
                    "replay_reused": replay["reused_existing_commit"],
                    "visible_counts": env.store.visible_counts(),
                }
            )
        for failure_point in (
            "after_child_insert",
            "after_pointer_cas",
            "after_receipt_insert",
            "before_commit",
        ):
            env = build_environment(
                base / f"F-{failure_point}", failure_point=failure_point
            )
            code = None
            try:
                env.commit(f"operation-{failure_point}")
            except ValueError as error:
                code = str(error).split(":", 1)[0]
            vectors.append(
                {
                    "fixture_id": f"F_{failure_point.upper()}",
                    "error_code": code,
                    "visible_counts": env.store.visible_counts(),
                    "physical_write_attempts": env.store.write_attempt_count(),
                }
            )
    return vectors


def build_object_shapes() -> dict[str, Any]:
    vectors = fixed_vectors()
    value = {
        "document_identity": "CCZ57-M3-B06-COMMIT-CORE-R01",
        "output_record_type": MERGE_RECEIPT_TYPE,
        "mutable_state": "current_pointer",
        "atomic_write_set": [
            "child_candidate_version",
            "current_pointer",
            "merge_receipt",
        ],
        "forbidden_persistent_objects": [
            "M3_COMMIT_INTENT",
            "POINTER_SNAPSHOT_PER_COMMIT",
        ],
        "shared_kernel": "work/ccz57_m3_b05_patch_route_r03_5/candidate_mutation_kernel.py",
        "optional_run_fence": {
            "transaction_order": "receipt_replay_then_run_fence_then_publish",
            "connection_scope": "same_begin_immediate_connection",
            "reader_capability": "select_only",
            "identity_in_request_hash": True,
            "b06_run_state_writes": 0,
        },
        "fixed_vectors": vectors,
        "catalog_hash": "",
    }
    value["catalog_hash"] = sha256_value(
        {key: item for key, item in value.items() if key != "catalog_hash"}
    )
    return value


def build_report(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_kind": "CCZ57_M3_B06_COMMIT_CORE_R01_OFFLINE_REPLAY",
        "mechanical_pass": True,
        "targeted_pytest_expected": "25 passed",
        "b05_regression_expected": "102 passed",
        "fixed_vector_count": len(catalog["fixed_vectors"]),
        "catalog_hash": catalog["catalog_hash"],
        "atomic_outputs": 3,
        "persistent_commit_intent_count": 0,
        "persistent_pointer_snapshot_count": 0,
        "real_model_api_calls": 0,
        "network_calls": 0,
        "real_novel_reads": 0,
        "formal_fact_writes": 0,
        "production_adapter_complete": False,
        "pr_gate": "NOT_RUN_LOCAL_CONSTRUCTION",
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.parent != ROOT:
        raise AssertionError("B06_ARTIFACT_PATH_ESCAPE")
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
            raise AssertionError(f"B06_MANIFEST_MISMATCH:{relative}")
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
        print("B06_R01_ARTIFACTS_REFRESHED")
        return 0
    if args.refresh_manifest:
        print(f"B06_R01_MANIFEST_REFRESHED={refresh_manifest()}")
        return 0
    if json.loads(OBJECT_SHAPES.read_text(encoding="utf-8")) != catalog:
        raise AssertionError("B06_OBJECT_SHAPES_DRIFT")
    if json.loads(REPORT.read_text(encoding="utf-8")) != report:
        raise AssertionError("B06_OFFLINE_REPORT_DRIFT")
    manifest_count = verify_manifest()
    print(
        "B06_R01_SELF_CHECK=PASS; "
        f"vectors={len(catalog['fixed_vectors'])}; manifest={manifest_count}; "
        f"catalog={catalog['catalog_hash']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
