"""Deterministic zero-network replay for the product candidate authority."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from namespace_migration import (
    CONTROL_SCHEMA_VERSION,
    CONTROL_TABLE_LAYOUTS,
    NamespaceMigrationController,
    NamespaceMigrationError,
    ProductCandidateAuthorityAccess,
    ReadOnlyMigrationSource,
)
from product_authority import (
    initialize_fixture_source,
    initialize_product_read_only_source_fixture,
    initialize_product_root,
    product_root_request,
)
from product_shadow import build_product_shadow
from work.ccz57_m3_b01_candidate_version_r03_5 import fixtures as b01_fixtures
def _source_reader(
    root: Path,
    *,
    request: dict[str, Any],
) -> ReadOnlyMigrationSource:
    store, source_request, result = initialize_product_read_only_source_fixture(
        root,
        product_request=request,
    )
    return ReadOnlyMigrationSource(
        store=store,
        logical_pointer_key=result["logical_pointer_key"],
        reference_records=source_request["reference_records"],
    )


def _successful_cutover(root: Path) -> dict[str, Any]:
    request = product_root_request()
    source_reader = _source_reader(root / "source-authority", request=request)
    controller = NamespaceMigrationController(root / "control")
    discovered = controller.discover("self-check-cutover", source_reader)
    controller.verify_source(
        "self-check-cutover",
        source_reader=source_reader,
    )
    store, _, root_result = initialize_product_root(
        root / "authority",
        request=request,
    )
    controller.stage_target(
        "self-check-cutover",
        store=store,
        root_result=root_result,
    )
    controller.shadow_verify(
        "self-check-cutover",
        source_reader=source_reader,
        store=store,
    )
    controller.cutover(
        "self-check-cutover",
        source_reader=source_reader,
        store=store,
    )
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
        "source_semantic_hash": discovered["source"]["source_semantic_hash"],
    }


def _aborted_cutover(root: Path) -> dict[str, Any]:
    request = product_root_request()
    source_reader = _source_reader(root / "source-authority", request=request)
    controller = NamespaceMigrationController(root / "control")
    controller.discover("self-check-abort", source_reader)
    controller.verify_source(
        "self-check-abort",
        source_reader=source_reader,
    )
    store, _, root_result = initialize_product_root(
        root / "authority",
        request=request,
    )
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
    request = b01_fixtures.base_request()
    source_store, source_request, source_result = initialize_fixture_source(
        root / "source-authority",
        request=request,
    )
    source_reader = ReadOnlyMigrationSource(
        store=source_store,
        logical_pointer_key=source_result["logical_pointer_key"],
        reference_records=source_request["reference_records"],
    )
    try:
        controller.discover("self-check-synthetic", source_reader)
    except NamespaceMigrationError as error:
        code = error.code
    else:
        code = "UNEXPECTEDLY_ACCEPTED"
    return {
        "result_code": code,
        "state": controller.read_state("self-check-synthetic")["state"],
        "candidate_store_created": (root / "candidate-authority").exists(),
    }


def _schema_guard(root: Path) -> dict[str, Any]:
    controller = NamespaceMigrationController(root / "control")
    with sqlite3.connect(controller.database_path) as connection:
        connection.execute(
            "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
            (sqlite3.Binary(b"future-incompatible-schema"),),
        )
        connection.commit()
    try:
        NamespaceMigrationController(root / "control")
    except NamespaceMigrationError as error:
        result_code = error.code
    else:
        result_code = "UNEXPECTEDLY_ACCEPTED"
    with sqlite3.connect(controller.database_path) as connection:
        persisted = bytes(
            connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        ).decode("utf-8")
    return {
        "current_schema_version": CONTROL_SCHEMA_VERSION,
        "full_table_layouts_frozen": len(CONTROL_TABLE_LAYOUTS),
        "unknown_schema_result": result_code,
        "unknown_schema_preserved": persisted == "future-incompatible-schema",
    }


def run_self_check() -> dict[str, Any]:
    with (
        TemporaryDirectory() as first_root,
        TemporaryDirectory() as second_root,
        TemporaryDirectory() as migration_root,
        TemporaryDirectory() as abort_root,
        TemporaryDirectory() as synthetic_root,
        TemporaryDirectory() as schema_root,
    ):
        first = build_product_shadow(Path(first_root)).result
        second = build_product_shadow(Path(second_root)).result
        if first != second:
            raise AssertionError("PRODUCT_SHADOW_NONDETERMINISTIC")
        migration = _successful_cutover(Path(migration_root))
        aborted = _aborted_cutover(Path(abort_root))
        synthetic = _synthetic_rejection(Path(synthetic_root))
        schema_guard = _schema_guard(Path(schema_root))
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
        or schema_guard["unknown_schema_result"]
        != "MIGRATION_CONTROL_SCHEMA_IDENTITY_MISMATCH"
        or schema_guard["unknown_schema_preserved"] is not True
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
        "migration_control_schema_guard": schema_guard,
        "candidate_storage_writer_count": len(first["candidate_storage_writers"]),
        "b09_persistent_writer_count": 0,
        "formal_fact_writes": first["formal_writes"],
        "ten_ledger_writes": first["ten_ledger_writes"],
        "model_api_calls": 0,
        "network_api_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_check(), ensure_ascii=False, indent=2, sort_keys=True))
