"""Focused product identity, full-chain, migration, and rollback checks."""

from __future__ import annotations

import hashlib
import json
import sys
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
    NamespaceMigrationController,
    NamespaceMigrationError,
    ProductCandidateAuthorityAccess,
)
from work.ccz142_product_candidate_authority_r01.self_check import (  # noqa: E402
    run_self_check,
)
from work.ccz57_m3_b01_candidate_version_r03_5 import (  # noqa: E402
    fixtures as b01_fixtures,
)
from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    FIXTURE_ACCESS,
    FIXTURE_POINTER_NAMESPACE,
    PRODUCT_AUTHORITY_PROFILE,
    PRODUCT_CANDIDATE_ACCESS,
    PRODUCT_CONTRACT_VERSION,
    PRODUCT_POINTER_NAMESPACE,
    PRODUCT_READ_ONLY_ACCESS,
    FixtureStore,
    canonical_bytes,
    record_ref,
    validate_candidate_version,
)
from work.ccz57_m3_b05_patch_route_r03_5.fixtures import (  # noqa: E402
    build_environment,
)
from work.ccz57_m3_b06_commit_core_r01.fixtures import FreshnessReader  # noqa: E402

from b06_contracts import B06ContractError, validate_mutable_pointer  # noqa: E402
from b06_store import B06CommitService  # noqa: E402

from candidate_authority import (  # noqa: E402
    CandidateAuthorityError,
    CandidateAuthorityStore,
)

from product_authority import (  # noqa: E402
    initialize_product_root,
    new_product_store,
    product_b01_scope,
    product_root_request,
)
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


def _eligible_source(project_scope_id: str) -> dict[str, Any]:
    return {
        "source_namespace": FIXTURE_POINTER_NAMESPACE,
        "candidate_access": FIXTURE_ACCESS,
        "upstream_access": PRODUCT_READ_ONLY_ACCESS,
        "project_scope_id": project_scope_id,
        "source_head_sha256": "a" * 64,
        "synthetic_fixture": False,
    }


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
    initialize_product_root(root)
    with pytest.raises(
        CandidateAuthorityError,
        match="AUTHORITY_PROFILE_STORE_MISMATCH",
    ):
        CandidateAuthorityStore(root, project_scope_id="product-project-001")


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
    assert result["formal_tables"] == []
    assert result["formal_writes"] == 0
    assert result["ten_ledger_writes"] == 0
    assert result["model_api_calls"] == 0
    assert result["network_api_calls"] == 0


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
    source = _eligible_source("product-project-001")
    discovered = controller.discover("migration-001", source)
    controller.verify_source(
        "migration-001",
        observed_source_hash=discovered["source_hash"],
    )
    store, _, result = initialize_product_root(tmp_path / "authority")
    controller.stage_target("migration-001", store=store, root_result=result)
    access = ProductCandidateAuthorityAccess(
        controller=controller,
        store=store,
        migration_id="migration-001",
    )
    with pytest.raises(NamespaceMigrationError, match="PRODUCT_NAMESPACE_NOT_ACTIVE"):
        access.read_pointer(result["logical_pointer_key"])
    semantic_hash = "c" * 64
    controller.shadow_verify(
        "migration-001",
        source_semantic_hash=semantic_hash,
        target_semantic_hash=semantic_hash,
    )
    controller.cutover("migration-001", store=store)
    with pytest.raises(NamespaceMigrationError, match="PRODUCT_NAMESPACE_NOT_ACTIVE"):
        access.read_pointer(result["logical_pointer_key"])
    active = controller.activate_product_run("migration-001")
    assert active["state"] == "POST_CUTOVER_ACTIVE"
    assert access.read_pointer(result["logical_pointer_key"])["generation"] == 1
    assert access.read_candidate(result["candidate_version_ref"])[
        "access"
    ] == PRODUCT_CANDIDATE_ACCESS


def test_synthetic_source_rejection_never_creates_candidate_store(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    source = {
        **_eligible_source("product-project-001"),
        "upstream_access": FIXTURE_ACCESS,
        "synthetic_fixture": True,
    }
    candidate_root = tmp_path / "candidate-authority"
    with pytest.raises(
        NamespaceMigrationError,
        match="MIGRATION_SYNTHETIC_FIXTURE_INELIGIBLE",
    ):
        controller.discover("migration-synthetic", source)
    assert not candidate_root.exists()
    state = controller.read_state("migration-synthetic")
    assert state["state"] == "REJECTED_READ_ONLY"


def test_abort_before_cutover_keeps_product_access_closed(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    discovered = controller.discover(
        "migration-abort",
        _eligible_source("product-project-001"),
    )
    controller.verify_source(
        "migration-abort",
        observed_source_hash=discovered["source_hash"],
    )
    store, _, result = initialize_product_root(tmp_path / "authority")
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
    discovered = controller.discover(
        "migration-drift",
        _eligible_source("product-project-001"),
    )
    controller.verify_source(
        "migration-drift",
        observed_source_hash=discovered["source_hash"],
    )
    store, request, root_result = initialize_product_root(tmp_path / "authority")
    controller.stage_target("migration-drift", store=store, root_result=root_result)
    controller.shadow_verify(
        "migration-drift",
        source_semantic_hash="d" * 64,
        target_semantic_hash="d" * 64,
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
        controller.cutover("migration-drift", store=store)
    assert controller.read_state("migration-drift")["state"] == "SHADOW_VERIFIED"


def test_after_cutover_recovery_is_forward_only_and_persisted(
    tmp_path: Path,
) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    discovered = controller.discover(
        "migration-recovery",
        _eligible_source("product-project-001"),
    )
    controller.verify_source(
        "migration-recovery",
        observed_source_hash=discovered["source_hash"],
    )
    store, request, root_result = initialize_product_root(tmp_path / "authority")
    controller.stage_target("migration-recovery", store=store, root_result=root_result)
    controller.shadow_verify(
        "migration-recovery",
        source_semantic_hash="e" * 64,
        target_semantic_hash="e" * 64,
    )
    controller.cutover("migration-recovery", store=store)
    controller.activate_product_run("migration-recovery")
    before, after, _ = _commit_product_child(
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
    assert controller.events("migration-recovery")[-1]["payload"] == {
        "legacy_writer_reactivated": False,
        "pointer_generation_after": 2,
        "pointer_generation_before": 1,
    }


def test_migration_control_has_no_candidate_or_formal_tables(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    tables = controller.schema_objects()
    assert tables == ["metadata", "migration_events", "migration_state"]
    assert all(
        "candidate_version" not in table
        and "current_pointer" not in table
        and "formal" not in table
        and "ledger" not in table
        for table in tables
    )


def test_product_access_rejects_fixture_candidate_ref(tmp_path: Path) -> None:
    controller = NamespaceMigrationController(tmp_path / "control")
    discovered = controller.discover(
        "migration-access",
        _eligible_source("product-project-001"),
    )
    controller.verify_source(
        "migration-access",
        observed_source_hash=discovered["source_hash"],
    )
    store, _, result = initialize_product_root(tmp_path / "authority")
    controller.stage_target("migration-access", store=store, root_result=result)
    controller.shadow_verify(
        "migration-access",
        source_semantic_hash="f" * 64,
        target_semantic_hash="f" * 64,
    )
    controller.cutover("migration-access", store=store)
    controller.activate_product_run("migration-access")
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
