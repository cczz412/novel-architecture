"""Deterministic offline self-check for the B-04 r03.5 fixture shell."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from b04_contracts import (
    CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION,
    DOCUMENT_IDENTITY,
    OUTPUT_TYPES,
    PROJECTOR_MAP,
    WRITER_MAP,
    canonical_bytes,
    record_ref,
    reference_cycle_count,
    validate_output_record,
)
from b04_store import B04Service, FixtureStore
from fixtures import (
    FAILURE_FIXTURES,
    NORMAL_FIXTURES,
    build_authoritative_b02_store,
    route_inputs,
)

ROOT = Path(__file__).resolve().parent
OBJECT_SHAPES = ROOT / "OBJECT_SHAPES.json"
REPORT = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST = ROOT / "MANIFEST.sha256"
LEGACY_MANIFEST = (
    ROOT.parent / "ccz57_m3_b04_patch_atomic_group_r03_4" / "MANIFEST.sha256"
)
LEGACY_MANIFEST_SHA256 = (
    "5f9e896429ef7b2497c931d0f450d4f0b9689217f8bf07a189c6236aad7f188b"
)
ROUTES = (
    "replace_only",
    "add_only",
    "replace_with_evidence",
    "replace_and_add",
    "causal_sidecar",
)


def _run_route(route: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ccz57-b04-r035-") as directory:
        store = FixtureStore(Path(directory) / "b04-output")
        args = route_inputs(route)
        data = args.pop("catalog")
        b02_store, _ = build_authoritative_b02_store(
            Path(directory) / "b02-current-state", data
        )
        result = B04Service(store, b02_store=b02_store).propose(**args)
        records = store.read_records()
        for record in records:
            validate_output_record(record)
        if reference_cycle_count(records) != 0:
            raise AssertionError(f"reference cycle: {route}")
        replay = B04Service(store, b02_store=b02_store).propose(**args)
        if replay != result:
            raise AssertionError(f"replay drift: {route}")
        return {
            "route": route,
            "record_refs": sorted(
                [record_ref(record) for record in records], key=canonical_bytes
            ),
            "record_hashes": sorted(record["record_hash"] for record in records),
            "patch_ref": result["patch_proposal_ref"],
            "group_hashes": [
                group["group_payload_hash"]
                for group in next(
                    record
                    for record in records
                    if record["record_type"] == "M3_PATCH_PROPOSAL"
                )["payload"]["atomic_groups"]
            ],
            "preview_hash": hashlib.sha256(
                canonical_bytes(result["patch_preview"])
            ).hexdigest(),
            "visible_record_count": len(records),
            "idempotent_replay": True,
        }


def build_object_shapes() -> dict[str, Any]:
    vectors = [_run_route(route) for route in ROUTES]
    catalog = {
        "document_identity": DOCUMENT_IDENTITY,
        "contract_version": CONTRACT_VERSION,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "output_types": sorted(OUTPUT_TYPES),
        "writer_map": WRITER_MAP,
        "projector_map": PROJECTOR_MAP,
        "normal_fixture_count": len(NORMAL_FIXTURES),
        "failure_fixture_count": len(FAILURE_FIXTURES),
        "fixed_vectors": vectors,
        "catalog_hash": "",
    }
    catalog["catalog_hash"] = hashlib.sha256(
        canonical_bytes(
            {key: value for key, value in catalog.items() if key != "catalog_hash"}
        )
    ).hexdigest()
    return catalog


def build_report(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_kind": "CCZ57_M3_B04_R03_5_OFFLINE_REPLAY",
        "mechanical_pass": True,
        "contract_version": CONTRACT_VERSION,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "normal_fixture_count": len(NORMAL_FIXTURES),
        "failure_fixture_count": len(FAILURE_FIXTURES),
        "fixed_route_count": len(ROUTES),
        "catalog_hash": catalog["catalog_hash"],
        "route_preview_hashes": {
            item["route"]: item["preview_hash"] for item in catalog["fixed_vectors"]
        },
        "writer_count": len(WRITER_MAP),
        "projector_count": len(PROJECTOR_MAP),
        "reference_cycles": 0,
        "legacy_r03_4_manifest_sha256": LEGACY_MANIFEST_SHA256,
        "legacy_r03_4_mode": "READ_ONLY",
        "real_model_api_calls": 0,
        "network_calls": 0,
        "real_novel_reads": 0,
        "patch_apply_calls": 0,
        "candidate_version_writes": 0,
        "formal_fact_writes": 0,
        "pr_gate": "SKIPPED_NOT_CI_PASS",
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.parent != ROOT:
        raise AssertionError("artifact path escaped B-04 write set")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_manifest() -> int:
    if not MANIFEST.is_file():
        raise AssertionError("MANIFEST.sha256 missing")
    count = 0
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        path = ROOT / relative
        if not path.is_file():
            raise AssertionError(f"manifest member missing: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise AssertionError(f"manifest mismatch: {relative}")
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-artifacts", action="store_true")
    args = parser.parse_args()

    if (
        hashlib.sha256(LEGACY_MANIFEST.read_bytes()).hexdigest()
        != LEGACY_MANIFEST_SHA256
    ):
        raise AssertionError("legacy B-04 r03.4 manifest drift")
    catalog = build_object_shapes()
    report = build_report(catalog)
    if args.refresh_artifacts:
        _write_json(OBJECT_SHAPES, catalog)
        _write_json(REPORT, report)
        print("B04_R03_5_ARTIFACTS_REFRESHED")
        return 0
    if json.loads(OBJECT_SHAPES.read_text(encoding="utf-8")) != catalog:
        raise AssertionError("OBJECT_SHAPES.json drift")
    if json.loads(REPORT.read_text(encoding="utf-8")) != report:
        raise AssertionError("OFFLINE_REPLAY_REPORT.json drift")
    manifest_count = verify_manifest()
    print(
        "B04_R03_5_SELF_CHECK=PASS; "
        f"routes={len(ROUTES)}; normal={len(NORMAL_FIXTURES)}; "
        f"failure={len(FAILURE_FIXTURES)}; manifest={manifest_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
