"""Deterministic artifact builder and offline replay check for B-05 r03.5."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from acceptance_spec import FAILURE_FIXTURES, NORMAL_FIXTURES, RUNTIME_COUNTERS
from b05_contracts import (
    BUILDER_MAP,
    CANDIDATE_SCHEMA_ID,
    CONTRACT_VERSION,
    DOCUMENT_IDENTITY,
    OUTPUT_TYPES,
    PAYLOAD_KEYS,
    PROJECTOR_MAP,
    WRITER_MAP,
    canonical_bytes,
    record_ref,
    reference_cycle_count,
    sha256_value,
    validate_output_record,
)
from fixtures import REOPENED_AT, build_environment, external_record, fixture_catalog
from patch_route_projection import PatchAggregateProjector

ROOT = Path(__file__).resolve().parent
OBJECT_SHAPES = ROOT / "OBJECT_SHAPES.json"
REPORT = ROOT / "OFFLINE_REPLAY_REPORT.json"
MANIFEST = ROOT / "MANIFEST.sha256"


def _summary(env, result: dict[str, Any]) -> dict[str, Any]:
    records = env.store.read_records()
    for record in records:
        validate_output_record(record)
    if reference_cycle_count(records) != 0:
        raise AssertionError("B05_REFERENCE_CYCLE")
    projection = PatchAggregateProjector.project(records)
    return {
        "route_units": [
            {
                "route_unit_id": item["route_unit_id"],
                "route": item["route"],
                "reason_codes": item["reason_codes"],
            }
            for item in result["route_units"]
        ],
        "causal_routes": [
            {
                "causal_hint_proposal_ref": item["causal_hint_proposal_ref"],
                "route": item["route"],
                "reason_codes": item["reason_codes"],
            }
            for item in result["causal_hint_routes"]
        ],
        "record_refs": sorted(
            [record_ref(item) for item in records], key=canonical_bytes
        ),
        "projection_hash": sha256_value(projection),
        "visible_snapshot_hash": sha256_value(env.store.visible_snapshot()),
    }


def fixed_vectors() -> list[dict[str, Any]]:
    vectors = []
    scenarios = [
        ("N01_REPLACE_ALLOWED", "replace", {}),
        ("N02_ADD_ALLOWED", "add", {}),
        (
            "N03_INDEPENDENT_MIXED_ROUTES_WITH_EFFECTIVE_PROTECTION",
            "two-replace",
            {"semantic_unknown_groups": ["replace-b"]},
        ),
        ("N04_DEPENDENT_GROUPS_SINGLE_ROUTE_UNIT", "dependent", {}),
        (
            "N05_EXPAND_CHECK_MINIMAL_TARGET",
            "replace",
            {"semantic_unknown_groups": ["replace-a"]},
        ),
        (
            "N06_DEFER_EXACT_DECLARED_NON_CONTENT_GATE",
            "replace",
            {"closed_gate": True},
        ),
        (
            "N07_TRUSTED_STALE_OR_UNSAFE_PROPOSAL_REJECTED",
            "replace",
            {"stale_pointer": True},
        ),
        ("N08_CAUSAL_ROUTE_TO_B09_ALL_SUPPORT_UNITS_ALLOWED", "causal", {}),
    ]
    with tempfile.TemporaryDirectory(prefix="ccz57-b05-self-check-") as directory:
        base = Path(directory)
        for fixture_id, mode, kwargs in scenarios:
            env = build_environment(base / fixture_id, mode=mode, **kwargs)
            result = env.evaluate(f"operation-{fixture_id}")
            vectors.append({"fixture_id": fixture_id, **_summary(env, result)})
        env = build_environment(base / "N09")
        first = env.evaluate("n09-creator")
        replay = env.evaluate("n09-replay", created_at="2026-08-30T08:03:00Z")
        if replay["route_receipt_ref"] != first["route_receipt_ref"]:
            raise AssertionError("B05_N09_REPLAY_DRIFT")
        vectors.append(
            {
                "fixture_id": "N09_IDEMPOTENT_AND_CONTENT_DEDUP_REPLAY",
                "reused_existing_bundle": replay["reused_existing_bundle"],
                **_summary(env, replay),
            }
        )
        env = build_environment(base / "N10", closed_gate=True)
        initial = env.evaluate("n10-initial")
        projection = PatchAggregateProjector.project(env.store.read_records())
        prior_route = projection["series"][0]["active_route_receipt_ref"]
        prior_head = projection["series"][0]["lifecycle_head_ref"]
        new_gate_state = external_record(
            "M3_NON_CONTENT_GATE_STATE",
            {"current_state": "OPEN", "material": "self-check"},
            created_at=REOPENED_AT,
        )
        env.policy_reader.gate_bindings[0]["gate_state_ref"] = record_ref(
            new_gate_state
        )
        env.policy_reader.gate_bindings[0]["current_state"] = "OPEN"
        reopened = env.evaluate(
            "n10-reopen",
            created_at=REOPENED_AT,
            prior_active_route_receipt_ref_or_null=prior_route,
            prior_lifecycle_head_ref_or_null=prior_head,
            material_delta_refs=[record_ref(new_gate_state)],
        )
        vectors.append(
            {
                "fixture_id": "N10_ATOMIC_SUPERSEDE_AND_REOPEN_WITH_NEW_MATERIAL",
                "initial_route": initial["route_units"][0]["route"],
                **_summary(env, reopened),
            }
        )
    if len(vectors) != 10:
        raise AssertionError("B05_NORMAL_VECTOR_COUNT_DRIFT")
    return vectors


def build_object_shapes() -> dict[str, Any]:
    catalog = fixture_catalog()
    result = {
        "document_identity": DOCUMENT_IDENTITY,
        "contract_version": CONTRACT_VERSION,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "output_types": sorted(OUTPUT_TYPES),
        "payload_keys": {
            key: sorted(value) for key, value in sorted(PAYLOAD_KEYS.items())
        },
        "writer_map": WRITER_MAP,
        "builder_map": BUILDER_MAP,
        "projector_map": PROJECTOR_MAP,
        "normal_fixture_count": len(NORMAL_FIXTURES),
        "failure_fixture_count": len(FAILURE_FIXTURES),
        "fixture_catalog_hash": catalog["catalog_hash"],
        "fixed_vectors": fixed_vectors(),
        "catalog_hash": "",
    }
    result["catalog_hash"] = sha256_value(
        {key: value for key, value in result.items() if key != "catalog_hash"}
    )
    return result


def build_report(catalog: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_kind": "CCZ57_M3_B05_R03_5_OFFLINE_REPLAY",
        "mechanical_pass": True,
        "contract_version": CONTRACT_VERSION,
        "candidate_schema_id": CANDIDATE_SCHEMA_ID,
        "normal_fixture_count": len(NORMAL_FIXTURES),
        "failure_fixture_count": len(FAILURE_FIXTURES),
        "targeted_pytest_expected": "58 passed",
        "fixed_vector_count": len(catalog["fixed_vectors"]),
        "catalog_hash": catalog["catalog_hash"],
        "writer_count": len(set(WRITER_MAP.values())),
        "persistent_type_count": len(OUTPUT_TYPES),
        "projector_count": len(PROJECTOR_MAP),
        "reference_cycles": 0,
        "runtime_counters": RUNTIME_COUNTERS,
        "real_model_api_calls": 0,
        "network_calls": 0,
        "real_novel_reads": 0,
        "text_slice_reads": 0,
        "candidate_version_writes": 0,
        "pointer_writes": 0,
        "b09_sidecar_writes": 0,
        "pr_gate": "SKIPPED_NOT_CI_PASS",
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.parent != ROOT:
        raise AssertionError("B05_ARTIFACT_PATH_ESCAPE")
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
        if not path.is_file():
            raise AssertionError(f"B05_MANIFEST_MEMBER_MISSING:{relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise AssertionError(f"B05_MANIFEST_MISMATCH:{relative}")
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
        print("B05_R03_5_ARTIFACTS_REFRESHED")
        return 0
    if args.refresh_manifest:
        print(f"B05_R03_5_MANIFEST_REFRESHED={refresh_manifest()}")
        return 0
    if json.loads(OBJECT_SHAPES.read_text(encoding="utf-8")) != catalog:
        raise AssertionError("B05_OBJECT_SHAPES_DRIFT")
    if json.loads(REPORT.read_text(encoding="utf-8")) != report:
        raise AssertionError("B05_OFFLINE_REPORT_DRIFT")
    manifest_count = verify_manifest()
    print(
        "B05_R03_5_SELF_CHECK=PASS; "
        f"normal={len(NORMAL_FIXTURES)}; failure={len(FAILURE_FIXTURES)}; "
        f"vectors={len(catalog['fixed_vectors'])}; manifest={manifest_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
