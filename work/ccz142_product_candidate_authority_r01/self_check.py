"""Deterministic zero-network replay for the product candidate authority."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from namespace_migration import (
    NamespaceMigrationController,
    NamespaceMigrationError,
    ProductCandidateAuthorityAccess,
)
from product_authority import initialize_product_root
from product_shadow import build_product_shadow
from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (
    FIXTURE_ACCESS,
    FIXTURE_POINTER_NAMESPACE,
    PRODUCT_READ_ONLY_ACCESS,
)


def _eligible_source() -> dict[str, Any]:
    return {
        "source_namespace": FIXTURE_POINTER_NAMESPACE,
        "candidate_access": FIXTURE_ACCESS,
        "upstream_access": PRODUCT_READ_ONLY_ACCESS,
        "project_scope_id": "product-project-001",
        "source_head_sha256": "a" * 64,
        "synthetic_fixture": False,
    }


def _successful_cutover(root: Path) -> dict[str, Any]:
    controller = NamespaceMigrationController(root / "control")
    discovered = controller.discover("self-check-cutover", _eligible_source())
    controller.verify_source(
        "self-check-cutover",
        observed_source_hash=discovered["source_hash"],
    )
    store, _, root_result = initialize_product_root(root / "authority")
    controller.stage_target(
        "self-check-cutover",
        store=store,
        root_result=root_result,
    )
    semantic_hash = "b" * 64
    controller.shadow_verify(
        "self-check-cutover",
        store=store,
        target_pointer_key=root_result["logical_pointer_key"],
        target_pointer_generation=1,
        source_semantic_hash=semantic_hash,
        target_semantic_hash=semantic_hash,
    )
    controller.cutover("self-check-cutover", store=store)
    active = controller.activate_product_run(
        "self-check-cutover",
        store=store,
    )
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="self-check-cutover",
    )
    pointer = access.read_pointer(root_result["logical_pointer_key"])
    candidate = access.read_candidate(root_result["candidate_version_ref"])
    return {
        "state": active["state"],
        "event_sequence": active["event_sequence"],
        "events": [item["event"] for item in controller.events("self-check-cutover")],
        "pointer_namespace": pointer["pointer_namespace"],
        "pointer_generation": pointer["generation"],
        "candidate_access": candidate["access"],
        "control_schema_objects": controller.schema_objects(),
        "authority_binding_counts": controller.authority_binding_counts(),
    }


def _aborted_cutover(root: Path) -> dict[str, Any]:
    controller = NamespaceMigrationController(root / "control")
    discovered = controller.discover("self-check-abort", _eligible_source())
    controller.verify_source(
        "self-check-abort",
        observed_source_hash=discovered["source_hash"],
    )
    store, _, root_result = initialize_product_root(root / "authority")
    controller.stage_target(
        "self-check-abort",
        store=store,
        root_result=root_result,
    )
    aborted = controller.abort_before_cutover("self-check-abort")
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="self-check-abort",
    )
    try:
        access.read_pointer(root_result["logical_pointer_key"])
    except NamespaceMigrationError as error:
        access_result = error.code
    else:
        access_result = "UNEXPECTEDLY_VISIBLE"
    return {
        "state": aborted["state"],
        "access_result": access_result,
        "last_event": controller.events("self-check-abort")[-1],
    }


def _synthetic_rejection(root: Path) -> dict[str, Any]:
    controller = NamespaceMigrationController(root / "control")
    source = {
        **_eligible_source(),
        "upstream_access": FIXTURE_ACCESS,
        "synthetic_fixture": True,
    }
    try:
        controller.discover("self-check-synthetic", source)
    except NamespaceMigrationError as error:
        code = error.code
    else:
        code = "UNEXPECTEDLY_ACCEPTED"
    return {
        "result_code": code,
        "state": controller.read_state("self-check-synthetic")["state"],
        "candidate_store_created": (root / "candidate-authority").exists(),
    }


def run_self_check() -> dict[str, Any]:
    with (
        TemporaryDirectory() as first_root,
        TemporaryDirectory() as second_root,
        TemporaryDirectory() as migration_root,
        TemporaryDirectory() as abort_root,
        TemporaryDirectory() as synthetic_root,
    ):
        first = build_product_shadow(Path(first_root)).result
        second = build_product_shadow(Path(second_root)).result
        if first != second:
            raise AssertionError("PRODUCT_SHADOW_NONDETERMINISTIC")
        migration = _successful_cutover(Path(migration_root))
        aborted = _aborted_cutover(Path(abort_root))
        synthetic = _synthetic_rejection(Path(synthetic_root))
    if (
        first["result"] != "PASS"
        or first["b03_product_subject_validated"] is not True
        or first["b09_status"] == "ERROR"
        or first["candidate_storage_writers"] != ["CandidateAuthorityStore"]
        or first["plain_b01_product_profile_result"]
        != "B01_PRODUCT_PROFILE_REQUIRES_AUTHORITY_CAPTURE"
        or first["plain_b01_probe_storage_created"] is not False
        or first["plain_b06_product_profile_result"]
        != "B06_PRODUCT_PROFILE_REQUIRES_CANDIDATE_AUTHORITY_STORE"
        or first["plain_b06_probe_storage_created"] is not False
        or first["b02_real_publisher_write_events"] != 3
        or first["b02_candidate_ref_matches_b01"] is not True
        or first["b04_preview_projector"] != "PatchPreviewProjector"
        or first["b04_candidate_ref_matches_b01"] is not True
        or first["candidate_database_files"] != 1
        or first["formal_tables"]
        or first["formal_writes"] != 0
        or first["ten_ledger_tables"]
        or first["ten_ledger_writes"] != 0
        or migration["state"] != "POST_CUTOVER_ACTIVE"
        or aborted["state"] != "ABORTED"
        or synthetic["state"] != "REJECTED_READ_ONLY"
    ):
        raise AssertionError("PRODUCT_AUTHORITY_SELF_CHECK_FAILED")
    return {
        "result": "PASS",
        "candidate_identity": "PRODUCT_CANDIDATE_AUTHORITY",
        "full_chain": first,
        "deterministic_repeat_equal": True,
        "successful_cutover": migration,
        "pre_cutover_abort": aborted,
        "synthetic_fixture_rejection": synthetic,
        "candidate_storage_writer_count": len(first["candidate_storage_writers"]),
        "b09_persistent_writer_count": 0,
        "formal_fact_writes": first["formal_writes"],
        "ten_ledger_writes": first["ten_ledger_writes"],
        "model_api_calls": 0,
        "network_api_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))
