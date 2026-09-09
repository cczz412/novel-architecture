"""Focused product identity, full-chain, migration, and rollback checks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import threading
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = MODULE_ROOT.parents[1]
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    B01_ROOT,
    B05_ROOT,
    B06_ROOT,
    AUTHORITY_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz142_candidate_authority_r01.legacy_migration import (  # noqa: E402
    LegacyCandidateMigration,
    file_sha256,
)
from work.ccz142_product_candidate_authority_r01.namespace_migration import (  # noqa: E402
    CONTROL_SCHEMA_VERSION,
    NamespaceMigrationController,
    NamespaceMigrationError,
    ProductCandidateAuthorityAccess,
    ReadOnlyMigrationSource,
)
from work.ccz142_product_candidate_authority_r01.self_check import (  # noqa: E402
    run_self_check,
)
from work.ccz57_m3_b01_candidate_version_r03_5 import (  # noqa: E402
    fixtures as b01_fixtures,
)
from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    FIXTURE_ACCESS,
    FIXTURE_POINTER_NAMESPACE,
    PRODUCT_AUTHORITY_PROFILE,
    PRODUCT_CANDIDATE_ACCESS,
    PRODUCT_CONTRACT_VERSION,
    PRODUCT_POINTER_NAMESPACE,
    PRODUCT_READ_ONLY_ACCESS,
    FixtureStore,
    _compose_ccz142_b01_runtime,
    canonical_bytes,
    record_ref,
    validate_candidate_version,
)
from work.ccz57_m3_b05_patch_route_r03_5.fixtures import (  # noqa: E402
    build_environment,
)
from work.ccz57_m3_b06_commit_core_r01.fixtures import FreshnessReader  # noqa: E402

from b06_contracts import B06ContractError, validate_mutable_pointer  # noqa: E402
from b06_store import B06CommitService, B06CommitStore  # noqa: E402

from candidate_authority import (  # noqa: E402
    CandidateAuthorityError,
    CandidateAuthorityStore,
)

from product_authority import (  # noqa: E402
    initialize_fixture_source,
    initialize_product_root,
    initialize_product_read_only_source_fixture,
    new_product_store,
    product_b01_scope,
    product_root_request,
)
import product_shadow as product_shadow_module  # noqa: E402
from product_shadow import build_product_shadow  # noqa: E402

def _b05_scope(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        key: scope[key]
        for key in (
            "segment_index",
            "candidate_version",
            "pointer_snapshot",
            "live_pointer",
            "reference_records",
            "segment_inputs",
        )
    }


def _commit_product_child(
    root: Path,
    *,
    store: CandidateAuthorityStore,
    request: dict[str, Any],
    root_result: dict[str, Any],
    operation_id: str = "product-child-operation-001",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scope = product_b01_scope(store, request, root_result)
    b05 = build_environment(
        root / "b05",
        mode="replace",
        b01_scope=_b05_scope(scope),
    )
    route_result = b05.evaluate(f"route-{operation_id}")
    route = b05.store.record_by_ref(route_result["route_receipt_ref"])
    route_unit = next(
        item for item in route["payload"]["route_units"] if item["route"] == "ALLOW_FOR_B06"
    )
    freshness = FreshnessReader(
        {
            "b02_scope_snapshot_hash": route["payload"]["binding_header"][
                "b02_scope_snapshot_hash"
            ],
            "active_policy_selection_hash": route["payload"][
                "active_policy_selection_hash"
            ],
            "non_content_gate_snapshot_hash": route["payload"]["binding_header"][
                "non_content_gate_snapshot_hash"
            ],
        }
    )
    pointer_before = store.read_pointer(root_result["logical_pointer_key"])
    service = B06CommitService(
        store=store,
        b05_store=b05.store,
        freshness_reader=freshness,
        reference_records=[*request["reference_records"], scope["segment_index"]],
    )
    result = service.commit(
        project_scope_id=request["project_scope_id"],
        logical_pointer_key=root_result["logical_pointer_key"],
        operation_id=operation_id,
        route_receipt_ref=route_result["route_receipt_ref"],
        route_unit_id=route_unit["route_unit_id"],
        patch_proposal=b05.patch,
        protection_set=b05.protection,
        committed_at="2026-09-03T00:00:00Z",
    )
    pointer_after = store.read_pointer(root_result["logical_pointer_key"])
    return pointer_before, pointer_after, result


def _source_reader(
    root: Path,
    *,
    product_request: dict[str, Any],
) -> ReadOnlyMigrationSource:
    source_store, source_request, source_result = (
        initialize_product_read_only_source_fixture(
            root,
            product_request=product_request,
        )
    )
    return ReadOnlyMigrationSource(
        store=source_store,
        logical_pointer_key=source_result["logical_pointer_key"],
        reference_records=source_request["reference_records"],
    )


def _fixture_source_reader(
    root: Path,
    *,
    request: dict[str, Any],
) -> ReadOnlyMigrationSource:
    store, prepared, result = initialize_fixture_source(
        root,
        request=request,
    )
    return ReadOnlyMigrationSource(
        store=store,
        logical_pointer_key=result["logical_pointer_key"],
        reference_records=prepared["reference_records"],
    )


def _verify_shadow(
    controller: NamespaceMigrationController,
    migration_id: str,
    *,
    source_reader: ReadOnlyMigrationSource,
    store: CandidateAuthorityStore,
) -> dict[str, Any]:
    return controller.shadow_verify(
        migration_id,
        source_reader=source_reader,
        store=store,
    )


def _activate_migration(
    root: Path,
    *,
    migration_id: str = "active-migration",
    project_scope_id: str = "product-project-001",
) -> tuple[
    NamespaceMigrationController,
    CandidateAuthorityStore,
    dict[str, Any],
    dict[str, Any],
]:
    request = product_root_request(project_scope_id=project_scope_id)
    source_reader = _source_reader(
        root / "source-authority",
        product_request=request,
    )
    store, request, root_result = initialize_product_root(
        root / "authority",
        request=request,
    )
    controller = NamespaceMigrationController(root / "control")
    controller.discover(migration_id, source_reader)
    controller.verify_source(
        migration_id,
        source_reader=source_reader,
    )
    controller.stage_target(migration_id, store=store, root_result=root_result)
    _verify_shadow(
        controller,
        migration_id,
        source_reader=source_reader,
        store=store,
    )
    controller.cutover(migration_id, source_reader=source_reader, store=store)
    controller.activate_product_run(migration_id, store=store)
    return controller, store, request, root_result


def _stage_migration(
    controller: NamespaceMigrationController,
    migration_id: str,
    *,
    store: CandidateAuthorityStore,
    root_result: dict[str, Any],
    product_request: dict[str, Any] | None = None,
) -> ReadOnlyMigrationSource:
    prepared = (
        product_root_request(project_scope_id=store.project_scope_id)
        if product_request is None
        else deepcopy(product_request)
    )
    source_reader = _source_reader(
        controller.root.parent / f"source-{migration_id}",
        product_request=prepared,
    )
    controller.discover(migration_id, source_reader)
    controller.verify_source(
        migration_id,
        source_reader=source_reader,
    )
    controller.stage_target(migration_id, store=store, root_result=root_result)
    return source_reader


def test_product_profile_is_frozen_and_tampered_copy_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(FrozenInstanceError):
        PRODUCT_AUTHORITY_PROFILE.pointer_namespace = FIXTURE_POINTER_NAMESPACE  # type: ignore[misc]
    forged = replace(
        PRODUCT_AUTHORITY_PROFILE,
        pointer_namespace=FIXTURE_POINTER_NAMESPACE,
    )
    with pytest.raises(ValueError, match="B01_AUTHORITY_PROFILE_UNTRUSTED"):
        CandidateAuthorityStore(
            tmp_path / "forged",
            project_scope_id="product-project-001",
            authority_profile=forged,
        )


def test_plain_b06_rejects_product_profile_before_creating_storage(
    tmp_path: Path,
) -> None:
    target = tmp_path / "second-product-writer"
    with pytest.raises(
        B06ContractError,
        match="B06_PRODUCT_PROFILE_REQUIRES_CANDIDATE_AUTHORITY_STORE",
    ):
        B06CommitStore(
            target,
            authority_profile=PRODUCT_AUTHORITY_PROFILE,
        )
    assert not target.exists()


def test_plain_b01_fixture_store_rejects_product_profile_before_storage(
    tmp_path: Path,
) -> None:
    target = tmp_path / "second-product-root-writer"
    with pytest.raises(
        B01ContractError,
        match="B01_PRODUCT_PROFILE_REQUIRES_AUTHORITY_CAPTURE",
    ):
        _compose_ccz142_b01_runtime(
            FixtureStore(target),
            authority_profile=PRODUCT_AUTHORITY_PROFILE,
        )
    assert not target.exists()


def test_product_root_uses_new_record_and_pointer_identity(tmp_path: Path) -> None:
    store, request, result = initialize_product_root(tmp_path / "authority")
    scope = product_b01_scope(store, request, result)
    candidate = scope["candidate_version"]
    pointer = scope["live_pointer"]
    project_hash = hashlib.sha256(
        request["project_scope_id"].encode("utf-8")
    ).hexdigest()
    assert candidate["record_id"].startswith("pcv:")
    assert candidate["contract_version"] == PRODUCT_CONTRACT_VERSION
    assert candidate["access"] == PRODUCT_CANDIDATE_ACCESS
    assert pointer["pointer_namespace"] == PRODUCT_POINTER_NAMESPACE
    assert pointer["logical_pointer_key"].startswith(
        f"product:m3_candidate.current/{project_hash}/"
    )
    assert pointer["current_candidate_version_ref"] == record_ref(candidate)
    validate_candidate_version(
        candidate,
        reference_records=[*request["reference_records"], scope["segment_index"]],
        authority_profile=PRODUCT_AUTHORITY_PROFILE,
    )


def test_product_pointer_key_is_project_scoped(tmp_path: Path) -> None:
    first_request = product_root_request(project_scope_id="product-project-a")
    second_request = product_root_request(project_scope_id="product-project-b")
    first_store, _, first = initialize_product_root(
        tmp_path / "a", request=first_request
    )
    second_store, _, second = initialize_product_root(
        tmp_path / "b", request=second_request
    )
    assert first["logical_pointer_key"] != second["logical_pointer_key"]
    assert first_store.read_pointer(first["logical_pointer_key"])[
        "project_scope_id"
    ] == "product-project-a"
    assert second_store.read_pointer(second["logical_pointer_key"])[
        "project_scope_id"
    ] == "product-project-b"


def test_product_root_replay_is_idempotent(tmp_path: Path) -> None:
    request = product_root_request()
    store, _, first = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    before = store.table_counts()
    reopened, _, second = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    assert second["reused_existing_initialization"] is True
    assert first["candidate_version_ref"] == second["candidate_version_ref"]
    assert reopened.table_counts() == before


def test_product_child_and_pointer_cas_preserve_product_profile(
    tmp_path: Path,
) -> None:
    store, request, root_result = initialize_product_root(tmp_path / "authority")
    before, after, result = _commit_product_child(
        tmp_path,
        store=store,
        request=request,
        root_result=root_result,
    )
    child = store.read_candidate(result["child_candidate_version_ref"])
    assert before["generation"] == 1
    assert after["generation"] == 2
    assert after["pointer_namespace"] == PRODUCT_POINTER_NAMESPACE
    assert child["contract_version"] == PRODUCT_CONTRACT_VERSION
    assert child["access"] == PRODUCT_CANDIDATE_ACCESS
    assert child["record_id"].startswith("pcv:")


def test_mixed_namespace_pointer_is_rejected(tmp_path: Path) -> None:
    store, request, root_result = initialize_product_root(tmp_path / "authority")
    scope = product_b01_scope(store, request, root_result)
    forged = deepcopy(scope["live_pointer"])
    forged["pointer_namespace"] = FIXTURE_POINTER_NAMESPACE
    with pytest.raises(B06ContractError, match="B06_POINTER_SCOPE_INVALID"):
        validate_mutable_pointer(
            forged,
            candidate=scope["candidate_version"],
            reference_records=[*request["reference_records"], scope["segment_index"]],
            authority_profile=PRODUCT_AUTHORITY_PROFILE,
        )
    assert store.read_pointer(root_result["logical_pointer_key"])["generation"] == 1


def test_product_store_cannot_reopen_under_fixture_profile(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    store, _, _ = initialize_product_root(root)
    reopened = CandidateAuthorityStore(
        root,
        project_scope_id="product-project-001",
        authority_profile=PRODUCT_AUTHORITY_PROFILE,
    )
    assert reopened.authority_store_id == store.authority_store_id
    assert reopened.storage_locator_hash == store.storage_locator_hash
    with pytest.raises(
        CandidateAuthorityError,
        match="AUTHORITY_PROFILE_STORE_MISMATCH",
    ):
        CandidateAuthorityStore(root, project_scope_id="product-project-001")


def test_pr230_legacy_store_cannot_be_relabelled_as_product(
    tmp_path: Path,
) -> None:
    root = tmp_path / "legacy-authority"
    legacy = CandidateAuthorityStore(root, project_scope_id="product-project-001")
    legacy.initialize_authority_schema()
    metadata_keys = (
        "authority_identity",
        "candidate_contract_version",
        "candidate_access",
        "pointer_namespace",
        "authority_store_id",
    )
    with sqlite3.connect(legacy.database_path) as connection:
        connection.executemany(
            "DELETE FROM metadata WHERE key = ?",
            [(key,) for key in metadata_keys],
        )
        connection.commit()
    before = file_sha256(legacy.database_path)

    with pytest.raises(
        CandidateAuthorityError,
        match="AUTHORITY_LEGACY_PROFILE_UPGRADE_FORBIDDEN",
    ):
        CandidateAuthorityStore(
            root,
            project_scope_id="product-project-001",
            authority_profile=PRODUCT_AUTHORITY_PROFILE,
        )

    assert file_sha256(legacy.database_path) == before


def test_product_full_b01_to_b09_shadow(tmp_path: Path) -> None:
    result = build_product_shadow(tmp_path / "shadow").result
    assert result["result"] == "PASS"
    assert result["b03_product_subject_validated"] is True
    assert result["root_contract_version"] == PRODUCT_CONTRACT_VERSION
    assert result["child_contract_version"] == PRODUCT_CONTRACT_VERSION
    assert result["candidate_access"] == PRODUCT_CANDIDATE_ACCESS
    assert result["pointer_namespace"] == PRODUCT_POINTER_NAMESPACE
    assert result["pointer_generation"] == 2
    assert result["b09_status"] != "ERROR"
    assert result["candidate_storage_writers"] == ["CandidateAuthorityStore"]
    assert result["plain_b01_product_profile_result"] == (
        "B01_PRODUCT_PROFILE_REQUIRES_AUTHORITY_CAPTURE"
    )
    assert result["plain_b01_probe_storage_created"] is False
    assert result["plain_b06_product_profile_result"] == (
        "B06_PRODUCT_PROFILE_REQUIRES_CANDIDATE_AUTHORITY_STORE"
    )
    assert result["plain_b06_probe_storage_created"] is False
    assert result["candidate_database_files"] == 1
    assert result["candidate_database_paths"] == [
        "candidate-authority/b06-commit-core.sqlite3"
    ]
    assert result["formal_tables"] == []
    assert result["formal_writes"] == 0
    assert result["ten_ledger_writes"] == 0
    assert result["model_api_calls"] == 0
    assert result["network_api_calls"] == 0
    assert result["b02_records_exercised"] == 3
    assert result["b02_real_publisher_record_types"] == [
        "M3_COVERAGE_OBSERVATION",
        "M3_DIAGNOSTIC",
        "M3_DIAGNOSTIC_RECORDER_IDENTITY",
    ]
    assert result["b02_real_publisher_write_events"] == 3
    assert result["b02_candidate_ref_matches_b01"] is True
    assert result["b04_real_writer_record_types"] == [
        "M3_CANDIDATE_PROTECTION_SET",
        "M3_PATCH_PROPOSAL",
    ]
    assert result["b04_preview_projector"] == "PatchPreviewProjector"
    assert result["b04_candidate_ref_matches_b01"] is True


def test_product_shadow_cannot_bypass_real_b02_publisher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_real_b02(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("REAL_B02_PUBLISHER_REQUIRED")

    monkeypatch.setattr(
        product_shadow_module.B02Service,
        "add_diagnostic",
        reject_real_b02,
    )
    with pytest.raises(RuntimeError, match="REAL_B02_PUBLISHER_REQUIRED"):
        build_product_shadow(tmp_path / "shadow")


def test_product_shadow_cannot_bypass_real_b04_writers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_real_b04(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("REAL_B04_WRITERS_REQUIRED")

    monkeypatch.setattr(
        product_shadow_module.B04Service,
        "propose",
        reject_real_b04,
    )
    with pytest.raises(RuntimeError, match="REAL_B04_WRITERS_REQUIRED"):
        build_product_shadow(tmp_path / "shadow")


def test_legacy_synthetic_fixture_rejected_before_product_import(
    tmp_path: Path,
) -> None:
    legacy_root = tmp_path / "legacy"
    service, admit = b01_fixtures.fixture_runtime(FixtureStore(legacy_root))
    request = b01_fixtures.base_request()
    b01_fixtures.initialize_request(service, admit, request)
    source = legacy_root / "state.json"
    before_hash = file_sha256(source)
    product_store = new_product_store(tmp_path / "product")
    before_counts = product_store.table_counts()
    migration = LegacyCandidateMigration(product_store)
    with pytest.raises(
        CandidateAuthorityError,
        match="MIGRATION_SYNTHETIC_FIXTURE_INELIGIBLE",
    ):
        migration.migrate_b01_json(
            source_state_path=source,
            authority_snapshot={
                "project_scope_id": "product-project-001",
                "chapter_revision_ref": request["chapter_revision_ref"],
                "input_generation_id": "g_" + "a" * 64,
                "input_generation_hash": "a" * 64,
                "segment_scope_hash": "b" * 64,
            },
            reference_records=request["reference_records"],
            migration_id="synthetic-rejected-001",
        )
    assert file_sha256(source) == before_hash
    assert product_store.table_counts() == before_counts


def test_cutover_hides_target_until_product_run_is_active(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    request = product_root_request()
    source_reader = _source_reader(
        tmp_path / "source-authority",
        product_request=request,
    )
    controller.discover("migration-001", source_reader)
    controller.verify_source(
        "migration-001",
        source_reader=source_reader,
    )
    store, _, result = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    controller.stage_target("migration-001", store=store, root_result=result)
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="migration-001",
    )
    with pytest.raises(NamespaceMigrationError, match="PRODUCT_NAMESPACE_NOT_ACTIVE"):
        access.read_pointer(result["logical_pointer_key"])
    _verify_shadow(
        controller,
        "migration-001",
        source_reader=source_reader,
        store=store,
    )
    controller.cutover(
        "migration-001",
        source_reader=source_reader,
        store=store,
    )
    with pytest.raises(NamespaceMigrationError, match="PRODUCT_NAMESPACE_NOT_ACTIVE"):
        access.read_pointer(result["logical_pointer_key"])
    active = controller.activate_product_run("migration-001", store=store)
    assert active["state"] == "POST_CUTOVER_ACTIVE"
    assert access.read_pointer(result["logical_pointer_key"])["generation"] == 1
    assert access.read_candidate(result["candidate_version_ref"])[
        "access"
    ] == PRODUCT_CANDIDATE_ACCESS


def test_synthetic_source_rejection_never_creates_candidate_store(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    request = b01_fixtures.base_request()
    source_reader = _fixture_source_reader(
        tmp_path / "synthetic-source",
        request=request,
    )
    candidate_root = tmp_path / "candidate-authority"
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_SYNTHETIC_FIXTURE_INELIGIBLE",
    ):
        controller.discover("migration-synthetic", source_reader)
    assert not candidate_root.exists()
    state = controller.read_state("migration-synthetic")
    assert state["state"] == "REJECTED_READ_ONLY"


def test_abort_before_cutover_keeps_product_access_closed(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    request = product_root_request()
    source_reader = _source_reader(
        tmp_path / "source-authority",
        product_request=request,
    )
    controller.discover("migration-abort", source_reader)
    controller.verify_source(
        "migration-abort",
        source_reader=source_reader,
    )
    store, _, result = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    controller.stage_target("migration-abort", store=store, root_result=result)
    state = controller.abort_before_cutover("migration-abort")
    assert state["state"] == "ABORTED"
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="migration-abort",
    )
    with pytest.raises(NamespaceMigrationError, match="PRODUCT_NAMESPACE_NOT_ACTIVE"):
        access.read_pointer(result["logical_pointer_key"])
    assert controller.events("migration-abort")[-1]["payload"] == {
        "legacy_writer_reactivated": False,
        "target_visible": False,
    }


def test_cutover_detects_pointer_generation_drift(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    request = product_root_request()
    source_reader = _source_reader(
        tmp_path / "source-authority",
        product_request=request,
    )
    controller.discover("migration-drift", source_reader)
    controller.verify_source(
        "migration-drift",
        source_reader=source_reader,
    )
    store, request, root_result = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    controller.stage_target("migration-drift", store=store, root_result=root_result)
    _verify_shadow(
        controller,
        "migration-drift",
        source_reader=source_reader,
        store=store,
    )
    _commit_product_child(
        tmp_path,
        store=store,
        request=request,
        root_result=root_result,
        operation_id="drift-child",
    )
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_CUTOVER_CAS_MISMATCH",
    ):
        controller.cutover(
            "migration-drift",
            source_reader=source_reader,
            store=store,
        )
    assert controller.read_state("migration-drift")["state"] == "SHADOW_VERIFIED"


def test_after_cutover_recovery_is_forward_only_and_persisted(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    request = product_root_request()
    source_reader = _source_reader(
        tmp_path / "source-authority",
        product_request=request,
    )
    controller.discover("migration-recovery", source_reader)
    controller.verify_source(
        "migration-recovery",
        source_reader=source_reader,
    )
    store, request, root_result = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    controller.stage_target("migration-recovery", store=store, root_result=root_result)
    _verify_shadow(
        controller,
        "migration-recovery",
        source_reader=source_reader,
        store=store,
    )
    controller.cutover(
        "migration-recovery",
        source_reader=source_reader,
        store=store,
    )
    controller.activate_product_run("migration-recovery", store=store)
    before, after, child_result = _commit_product_child(
        tmp_path,
        store=store,
        request=request,
        root_result=root_result,
        operation_id="recovery-child",
    )
    recovered = controller.record_forward_recovery(
        "migration-recovery",
        store=store,
        pointer_before=before,
        pointer_after=after,
    )
    assert recovered["state"] == "POST_CUTOVER_ACTIVE"
    assert recovered["target_pointer_generation"] == 2
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="migration-recovery",
    )
    assert access.read_candidate(child_result["child_candidate_version_ref"])[
        "record_version"
    ] == 2
    assert access.read_candidate(root_result["candidate_version_ref"])[
        "record_version"
    ] == 1
    recovery_event = controller.events("migration-recovery")[-1]
    assert recovery_event["event"] == "FORWARD_RECOVERY_RECORDED"
    assert recovery_event["payload"] == {
        "legacy_writer_reactivated": False,
        "pointer_generation_after": 2,
        "pointer_generation_before": 1,
    }


def test_migration_control_has_no_candidate_or_formal_tables(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    tables = controller.schema_objects()
    assert tables == [
        "authority_pointer_bindings",
        "authority_project_bindings",
        "metadata",
        "migration_events",
        "migration_state",
    ]
    assert all(
        "candidate_version" not in table
        and "current_pointer" not in table
        and "formal" not in table
        and "ledger" not in table
        for table in tables
    )
    with sqlite3.connect(controller.database_path) as connection:
        schema_version = bytes(
            connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        ).decode("utf-8")
    assert schema_version == CONTROL_SCHEMA_VERSION


def test_migration_control_rejects_unknown_schema_without_rewriting(
    tmp_path: Path,
) -> None:
    root = tmp_path / "control"
    controller = NamespaceMigrationController(root)
    with sqlite3.connect(controller.database_path) as connection:
        connection.execute(
            "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
            (sqlite3.Binary(b"future-incompatible-schema"),),
        )
        connection.commit()
    before = file_sha256(controller.database_path)
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_CONTROL_SCHEMA_IDENTITY_MISMATCH",
    ):
        NamespaceMigrationController(root)
    assert file_sha256(controller.database_path) == before
    with sqlite3.connect(controller.database_path) as connection:
        persisted = bytes(
            connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()[0]
        )
    assert persisted == b"future-incompatible-schema"


@pytest.mark.parametrize(
    ("tamper_sql", "expected_code"),
    [
        (
            "ALTER TABLE migration_events ADD COLUMN unexpected TEXT",
            "MIGRATION_CONTROL_SCHEMA_LAYOUT_MISMATCH",
        ),
        (
            "CREATE UNIQUE INDEX migration_state_project_uq "
            "ON migration_state(project_scope_id)",
            "MIGRATION_CONTROL_SCHEMA_UNIQUE_INDEX_MISMATCH",
        ),
    ],
)
def test_migration_control_rejects_schema_structure_drift(
    tmp_path: Path,
    tamper_sql: str,
    expected_code: str,
) -> None:
    root = tmp_path / "control"
    controller = NamespaceMigrationController(root)
    with sqlite3.connect(controller.database_path) as connection:
        connection.execute(tamper_sql)
        connection.commit()
    with pytest.raises(NamespaceMigrationError, match=expected_code):
        NamespaceMigrationController(root)


def test_product_access_rejects_fixture_candidate_ref(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    request = product_root_request()
    source_reader = _source_reader(
        tmp_path / "source-authority",
        product_request=request,
    )
    controller.discover("migration-access", source_reader)
    controller.verify_source(
        "migration-access",
        source_reader=source_reader,
    )
    store, _, result = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    controller.stage_target("migration-access", store=store, root_result=result)
    _verify_shadow(
        controller,
        "migration-access",
        source_reader=source_reader,
        store=store,
    )
    controller.cutover(
        "migration-access",
        source_reader=source_reader,
        store=store,
    )
    controller.activate_product_run("migration-access", store=store)
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="migration-access",
    )
    fixture_ref = deepcopy(result["candidate_version_ref"])
    fixture_ref["contract_version"] = "r03.5-candidate"
    fixture_ref["record_contract_version"] = "r03.5-candidate"
    fixture_ref["access"] = FIXTURE_ACCESS
    with pytest.raises(NamespaceMigrationError, match="MIGRATION_MIXED_NAMESPACE_REF"):
        access.read_candidate(fixture_ref)


def test_fixture_and_product_record_refs_are_not_byte_equal(tmp_path: Path) -> None:
    product_store, _, product_result = initialize_product_root(tmp_path / "product")
    product_candidate = product_store.read_candidate(
        product_result["candidate_version_ref"]
    )
    fixture_store = FixtureStore(tmp_path / "fixture")
    service, admit = b01_fixtures.fixture_runtime(fixture_store)
    b01_fixtures.initialize_request(service, admit, b01_fixtures.base_request())
    fixture_candidate = next(
        record
        for record in fixture_store.read()["records"].values()
        if record["record_type"] == "M3_CANDIDATE_VERSION"
    )
    assert canonical_bytes(record_ref(product_candidate)) != canonical_bytes(
        record_ref(fixture_candidate)
    )
    assert product_candidate["record_hash"] != fixture_candidate["record_hash"]
    assert product_candidate["record_id"] != fixture_candidate["record_id"]


def test_migration_rejects_caller_claims_without_source_reader(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_SOURCE_READER_REQUIRED",
    ):
        controller.discover(  # type: ignore[arg-type]
            "migration-caller-claims",
            {
                "upstream_access": PRODUCT_READ_ONLY_ACCESS,
                "synthetic_fixture": False,
                "source_semantic_hash": "a" * 64,
            },
        )


def test_source_evidence_drift_is_rejected_before_verification(
    tmp_path: Path,
) -> None:
    request = product_root_request()
    source_store, source_request, source_result = (
        initialize_product_read_only_source_fixture(
            tmp_path / "source-authority",
            product_request=request,
        )
    )
    source_reader = ReadOnlyMigrationSource(
        store=source_store,
        logical_pointer_key=source_result["logical_pointer_key"],
        reference_records=source_request["reference_records"],
    )
    controller = NamespaceMigrationController(tmp_path / "control")
    controller.discover("migration-source-drift", source_reader)
    _commit_product_child(
        tmp_path / "source-child",
        store=source_store,
        request=source_request,
        root_result=source_result,
        operation_id="source-drift-child",
    )
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_SOURCE_EVIDENCE_DRIFT",
    ):
        controller.verify_source(
            "migration-source-drift",
            source_reader=source_reader,
        )
    assert controller.read_state("migration-source-drift")["state"] == "DISCOVERED"


def test_shadow_hashes_are_computed_from_source_and_target_evidence(
    tmp_path: Path,
) -> None:
    source_request = product_root_request()
    target_request = deepcopy(source_request)
    target_request["raw_items"][0]["fact"] = "甲离开北塔。"
    source_reader = _source_reader(
        tmp_path / "source-authority",
        product_request=source_request,
    )
    store, _, root_result = initialize_product_root(
        tmp_path / "authority",
        request=target_request,
    )
    controller = NamespaceMigrationController(tmp_path / "control")
    controller.discover("migration-semantic-divergence", source_reader)
    controller.verify_source(
        "migration-semantic-divergence",
        source_reader=source_reader,
    )
    controller.stage_target(
        "migration-semantic-divergence",
        store=store,
        root_result=root_result,
    )
    before = controller.read_state("migration-semantic-divergence")
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_SHADOW_DIVERGENCE",
    ):
        controller.shadow_verify(
            "migration-semantic-divergence",
            source_reader=source_reader,
            store=store,
        )
    assert controller.read_state("migration-semantic-divergence") == before


def test_cutover_rechecks_source_evidence_under_source_lock(
    tmp_path: Path,
) -> None:
    request = product_root_request()
    source_store, source_request, source_result = (
        initialize_product_read_only_source_fixture(
            tmp_path / "source-authority",
            product_request=request,
        )
    )
    source_reader = ReadOnlyMigrationSource(
        store=source_store,
        logical_pointer_key=source_result["logical_pointer_key"],
        reference_records=source_request["reference_records"],
    )
    store, _, root_result = initialize_product_root(
        tmp_path / "authority",
        request=request,
    )
    controller = NamespaceMigrationController(tmp_path / "control")
    controller.discover("migration-cutover-source-drift", source_reader)
    controller.verify_source(
        "migration-cutover-source-drift",
        source_reader=source_reader,
    )
    controller.stage_target(
        "migration-cutover-source-drift",
        store=store,
        root_result=root_result,
    )
    controller.shadow_verify(
        "migration-cutover-source-drift",
        source_reader=source_reader,
        store=store,
    )
    _commit_product_child(
        tmp_path / "source-child",
        store=source_store,
        request=source_request,
        root_result=source_result,
        operation_id="source-after-shadow-child",
    )
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_SOURCE_EVIDENCE_DRIFT",
    ):
        controller.cutover(
            "migration-cutover-source-drift",
            source_reader=source_reader,
            store=store,
        )
    assert controller.read_state("migration-cutover-source-drift")["state"] == (
        "SHADOW_VERIFIED"
    )


def test_shadow_verify_rejects_wrong_store(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    store, _, root_result = initialize_product_root(tmp_path / "authority")
    other_store, _, _ = initialize_product_root(
        tmp_path / "other-authority",
        request=product_root_request(operation_id="other-store-root"),
    )
    source_reader = _stage_migration(
        controller,
        "migration-wrong-shadow-store",
        store=store,
        root_result=root_result,
    )
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_TARGET_STORE_MISMATCH",
    ):
        controller.shadow_verify(
            "migration-wrong-shadow-store",
            source_reader=source_reader,
            store=other_store,
        )


def test_shadow_verify_rejects_target_pointer_generation_drift(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    store, request, root_result = initialize_product_root(tmp_path / "authority")
    source_reader = _stage_migration(
        controller,
        "migration-shadow-pointer-drift",
        store=store,
        root_result=root_result,
    )
    _commit_product_child(
        tmp_path / "target-child",
        store=store,
        request=request,
        root_result=root_result,
        operation_id="target-drift-child",
    )
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_SHADOW_GENERATION_MISMATCH",
    ):
        controller.shadow_verify(
            "migration-shadow-pointer-drift",
            source_reader=source_reader,
            store=store,
        )


def test_different_migration_id_cannot_activate_second_store_for_same_project(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    stores: list[CandidateAuthorityStore] = []
    results: list[dict[str, Any]] = []
    source_readers: list[ReadOnlyMigrationSource] = []
    for suffix in ("a", "b"):
        request = product_root_request(operation_id=f"root-{suffix}")
        store, _, root_result = initialize_product_root(
            tmp_path / f"authority-{suffix}",
            request=request,
        )
        source_reader = _stage_migration(
            controller,
            f"migration-{suffix}",
            store=store,
            root_result=root_result,
            product_request=request,
        )
        _verify_shadow(
            controller,
            f"migration-{suffix}",
            source_reader=source_reader,
            store=store,
        )
        stores.append(store)
        results.append(root_result)
        source_readers.append(source_reader)
    assert results[0]["logical_pointer_key"] == results[1]["logical_pointer_key"]
    assert stores[0].authority_store_id != stores[1].authority_store_id
    controller.cutover(
        "migration-a",
        source_reader=source_readers[0],
        store=stores[0],
    )
    controller.activate_product_run("migration-a", store=stores[0])
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_PROJECT_AUTHORITY_CONFLICT",
    ):
        controller.cutover(
            "migration-b",
            source_reader=source_readers[1],
            store=stores[1],
        )
    assert controller.read_state("migration-b")["state"] == "SHADOW_VERIFIED"
    assert controller.authority_binding_counts() == {
        "authority_project_bindings": 1,
        "authority_pointer_bindings": 1,
    }


def test_same_project_different_store_concurrent_cutover_has_one_winner(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    stores: dict[str, CandidateAuthorityStore] = {}
    source_readers: dict[str, ReadOnlyMigrationSource] = {}
    for suffix in ("a", "b"):
        request = product_root_request(operation_id=f"concurrent-root-{suffix}")
        store, _, root_result = initialize_product_root(
            tmp_path / f"authority-{suffix}",
            request=request,
        )
        source_reader = _stage_migration(
            controller,
            f"concurrent-{suffix}",
            store=store,
            root_result=root_result,
            product_request=request,
        )
        _verify_shadow(
            controller,
            f"concurrent-{suffix}",
            source_reader=source_reader,
            store=store,
        )
        stores[suffix] = store
        source_readers[suffix] = source_reader

    barrier = threading.Barrier(2)
    successes: list[str] = []
    failures: list[NamespaceMigrationError] = []

    def cutover(suffix: str) -> None:
        barrier.wait(timeout=5)
        try:
            controller.cutover(
                f"concurrent-{suffix}",
                source_reader=source_readers[suffix],
                store=stores[suffix],
            )
        except NamespaceMigrationError as error:
            failures.append(error)
        else:
            successes.append(suffix)

    threads = [
        threading.Thread(target=cutover, args=(suffix,)) for suffix in ("a", "b")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert len(successes) == 1
    assert [error.code for error in failures] == [
        "MIGRATION_PROJECT_AUTHORITY_CONFLICT"
    ]
    assert sorted(
        controller.read_state(f"concurrent-{suffix}")["state"]
        for suffix in ("a", "b")
    ) == ["CUTOVER_COMMITTED", "SHADOW_VERIFIED"]
    assert controller.authority_binding_counts() == {
        "authority_project_bindings": 1,
        "authority_pointer_bindings": 1,
    }


def test_same_product_store_can_bind_multiple_project_pointers(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    first_request = product_root_request(operation_id="first-root")
    store, _, first = initialize_product_root(
        tmp_path / "authority",
        request=first_request,
    )
    second_request = product_root_request(
        operation_id="second-root",
        chapter_id="product-chapter-002",
    )
    reopened, _, second = initialize_product_root(
        store.root,
        request=second_request,
    )
    assert reopened.authority_store_id == store.authority_store_id
    for suffix, active_store, root_result, request in (
        ("a", store, first, first_request),
        ("b", reopened, second, second_request),
    ):
        source_reader = _stage_migration(
            controller,
            f"multi-pointer-{suffix}",
            store=active_store,
            root_result=root_result,
            product_request=request,
        )
        _verify_shadow(
            controller,
            f"multi-pointer-{suffix}",
            source_reader=source_reader,
            store=active_store,
        )
        controller.cutover(
            f"multi-pointer-{suffix}",
            source_reader=source_reader,
            store=active_store,
        )
        controller.activate_product_run(
            f"multi-pointer-{suffix}",
            store=active_store,
        )
    assert first["logical_pointer_key"] != second["logical_pointer_key"]
    assert controller.authority_binding_counts() == {
        "authority_project_bindings": 1,
        "authority_pointer_bindings": 2,
    }


def test_active_access_rejects_another_project_store(tmp_path: Path) -> None:
    controller, _, _, _ = _activate_migration(
        tmp_path / "active",
        project_scope_id="product-project-a",
    )
    other_store, _, _ = initialize_product_root(
        tmp_path / "other",
        request=product_root_request(project_scope_id="product-project-b"),
    )
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_TARGET_STORE_MISMATCH",
    ):
        ProductCandidateAuthorityAccess(
            controller=controller,
            store=other_store,
            migration_id="active-migration",
        )


def test_active_access_rejects_a_second_store_for_same_project(
    tmp_path: Path,
) -> None:
    controller, _, _, _ = _activate_migration(tmp_path / "active")
    other_store, _, _ = initialize_product_root(tmp_path / "other")
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_TARGET_STORE_MISMATCH",
    ):
        ProductCandidateAuthorityAccess(
            controller=controller,
            store=other_store,
            migration_id="active-migration",
        )


def test_active_access_rejects_another_pointer_and_candidate_in_same_store(
    tmp_path: Path,
) -> None:
    controller, store, _, target_result = _activate_migration(tmp_path / "active")
    _, _, other_result = initialize_product_root(
        store.root,
        request=product_root_request(
            operation_id="other-pointer-root",
            chapter_id="product-chapter-002",
        ),
    )
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="active-migration",
    )
    assert access.read_pointer(target_result["logical_pointer_key"])[
        "logical_pointer_key"
    ] == target_result["logical_pointer_key"]
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_TARGET_POINTER_MISMATCH",
    ):
        access.read_pointer(other_result["logical_pointer_key"])
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_CANDIDATE_OUTSIDE_TARGET_LINEAGE",
    ):
        access.read_candidate(other_result["candidate_version_ref"])


def test_forward_recovery_rejects_another_pointer_in_same_store(
    tmp_path: Path,
) -> None:
    controller, store, _, _ = _activate_migration(tmp_path / "active")
    other_request = product_root_request(
        operation_id="other-recovery-root",
        chapter_id="product-chapter-003",
    )
    _, _, other_result = initialize_product_root(
        store.root,
        request=other_request,
    )
    pointer_before, pointer_after, _ = _commit_product_child(
        tmp_path / "other-recovery-child",
        store=store,
        request=other_request,
        root_result=other_result,
        operation_id="other-recovery-child",
    )
    state_before = controller.read_state("active-migration")
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_TARGET_POINTER_MISMATCH",
    ):
        controller.record_forward_recovery(
            "active-migration",
            store=store,
            pointer_before=pointer_before,
            pointer_after=pointer_after,
        )
    assert controller.read_state("active-migration") == state_before


def test_cutover_lock_blocks_child_and_activation_requires_forward_repair(
    tmp_path: Path,
) -> None:
    transition_reached = threading.Event()
    release_transition = threading.Event()
    child_lock_requested = threading.Event()
    child_done = threading.Event()

    class PausedCutoverController(NamespaceMigrationController):
        def _transition(
            self,
            migration_id: str,
            *,
            expected_state: str,
            next_state: str,
            event_payload: dict[str, Any],
            updates: dict[str, Any] | None = None,
            event_name: str | None = None,
            bind_cutover: bool = False,
            advance_pointer_binding: tuple[int, int] | None = None,
        ) -> dict[str, Any]:
            if next_state == "CUTOVER_COMMITTED":
                transition_reached.set()
                if not release_transition.wait(timeout=5):
                    raise AssertionError("CUTOVER_TEST_RELEASE_TIMEOUT")
            return super()._transition(
                migration_id,
                expected_state=expected_state,
                next_state=next_state,
                event_payload=event_payload,
                updates=updates,
                event_name=event_name,
                bind_cutover=bind_cutover,
                advance_pointer_binding=advance_pointer_binding,
            )

    store, request, root_result = initialize_product_root(tmp_path / "authority")
    controller = PausedCutoverController(tmp_path / "control")
    source_reader = _source_reader(
        tmp_path / "source-authority",
        product_request=request,
    )
    controller.discover("migration-cutover-race", source_reader)
    controller.verify_source(
        "migration-cutover-race",
        source_reader=source_reader,
    )
    controller.stage_target(
        "migration-cutover-race",
        store=store,
        root_result=root_result,
    )
    _verify_shadow(
        controller,
        "migration-cutover-race",
        source_reader=source_reader,
        store=store,
    )

    original_serialization = store.serialization

    @contextmanager
    def traced_serialization() -> Any:
        if threading.current_thread().name == "candidate-child":
            child_lock_requested.set()
        with original_serialization():
            yield

    store.serialization = traced_serialization  # type: ignore[method-assign]
    failures: list[BaseException] = []
    results: dict[str, Any] = {}

    def run_cutover() -> None:
        try:
            results["cutover"] = controller.cutover(
                "migration-cutover-race",
                source_reader=source_reader,
                store=store,
            )
        except BaseException as error:  # pragma: no cover - asserted below
            failures.append(error)

    def run_child() -> None:
        try:
            before, after, result = _commit_product_child(
                tmp_path / "race-child",
                store=store,
                request=request,
                root_result=root_result,
                operation_id="race-child",
            )
            results["pointer_before"] = before
            results["pointer_after"] = after
            results["child"] = result
        except BaseException as error:  # pragma: no cover - asserted below
            failures.append(error)
        finally:
            child_done.set()

    cutover_thread = threading.Thread(target=run_cutover, name="cutover")
    cutover_thread.start()
    assert transition_reached.wait(timeout=5)
    child_thread = threading.Thread(target=run_child, name="candidate-child")
    child_thread.start()
    assert child_lock_requested.wait(timeout=5)
    assert child_done.wait(timeout=0.1) is False
    release_transition.set()
    cutover_thread.join(timeout=5)
    child_thread.join(timeout=10)
    assert not cutover_thread.is_alive()
    assert not child_thread.is_alive()
    assert failures == []
    assert results["cutover"]["target_pointer_generation"] == 1
    assert results["pointer_after"]["generation"] == 2
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_ACTIVATION_POINTER_DRIFT",
    ):
        controller.activate_product_run(
            "migration-cutover-race",
            store=store,
        )
    recovered = controller.record_forward_recovery(
        "migration-cutover-race",
        store=store,
        pointer_before=results["pointer_before"],
        pointer_after=results["pointer_after"],
    )
    assert recovered["state"] == "CUTOVER_COMMITTED"
    active = controller.activate_product_run(
        "migration-cutover-race",
        store=store,
    )
    assert active["state"] == "POST_CUTOVER_ACTIVE"


def test_saved_offline_report_matches_fresh_self_check() -> None:
    saved = json.loads((MODULE_ROOT / "OFFLINE_REPLAY_REPORT.json").read_text())
    assert run_self_check() == saved


def test_manifest_covers_every_delivery_file_and_matches_bytes() -> None:
    manifest_path = MODULE_ROOT / "MANIFEST.sha256"
    entries: dict[str, str] = {}
    for line in manifest_path.read_text().splitlines():
        digest, name = line.split("  ", maxsplit=1)
        entries[name] = digest
    expected = {
        path.name
        for path in MODULE_ROOT.iterdir()
        if path.is_file() and path.name != manifest_path.name
    }
    assert set(entries) == expected
    for name, digest in entries.items():
        actual = hashlib.sha256((MODULE_ROOT / name).read_bytes()).hexdigest()
        assert actual == digest
