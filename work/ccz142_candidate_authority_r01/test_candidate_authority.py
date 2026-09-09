from __future__ import annotations

import inspect
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Event, Thread

import pytest

import candidate_authority as candidate_authority_module

from candidate_authority import (
    CandidateAuthorityError,
    CandidateAuthorityStore,
    CandidateRootInitializer,
    record_ref,
)
from b01_contract import FixtureStore, canonical_bytes
from legacy_migration import LegacyCandidateMigration, file_sha256
from shadow_fixtures import (
    MutableRootAuthorityReader,
    authority_snapshot,
    build_full_shadow,
    root_request,
)
from work.ccz142_candidate_authority_r01.self_check import run_self_check
from work.ccz57_m3_b01_candidate_version_r03_5 import fixtures as b01_fixtures
from work.ccz57_m3_b06_commit_core_r01 import fixtures as b06_fixtures

ROOT = Path(__file__).resolve().parent
PROJECT = "fixture-project-001"
UPGRADED_METADATA_KEYS = {
    "authority_identity",
    "candidate_contract_version",
    "candidate_access",
    "pointer_namespace",
    "authority_store_id",
}


def new_store(
    root: Path, *, failure_point: str | None = None
) -> CandidateAuthorityStore:
    store = CandidateAuthorityStore(
        root,
        project_scope_id=PROJECT,
        root_failure_point=failure_point,
    )
    store.initialize_authority_schema()
    return store


def publish_root(
    store: CandidateAuthorityStore,
    request: dict,
    *,
    reader: MutableRootAuthorityReader | None = None,
) -> dict:
    selected_reader = reader or MutableRootAuthorityReader(
        authority_snapshot(request)
    )
    return CandidateRootInitializer(
        store=store,
        authority_reader=selected_reader,
    ).initialize_root(request)


def remove_post_pr230_metadata(store: CandidateAuthorityStore) -> None:
    with sqlite3.connect(store.database_path) as connection:
        connection.executemany(
            "DELETE FROM metadata WHERE key = ?",
            [(key,) for key in sorted(UPGRADED_METADATA_KEYS)],
        )
        connection.commit()


def test_public_root_capability_has_no_generic_read_or_commit(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    capability = CandidateRootInitializer(
        store=store,
        authority_reader=MutableRootAuthorityReader(authority_snapshot(request)),
    )
    assert set(inspect.signature(capability.initialize_root).parameters) == {"request"}
    assert not hasattr(capability, "read")
    assert not hasattr(capability, "commit")
    assert not hasattr(store, "initialize_root")


def test_direct_root_publish_without_capability_is_rejected(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    with pytest.raises(CandidateAuthorityError, match="ROOT_PUBLISHER_SCOPE_ESCAPE"):
        store._publish_root(staged_state={}, authority_snapshot={})
    assert store.visible_counts()["candidate_versions"] == 0


def test_root_initialization_and_same_operation_replay(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    first = publish_root(store, request)
    replay = publish_root(store, request)
    assert first["reused_existing_initialization"] is False
    assert replay["reused_existing_initialization"] is True
    assert first["candidate_version_ref"] == replay["candidate_version_ref"]
    assert store.visible_counts() == {
        "candidate_versions": 1,
        "current_pointers": 1,
        "merge_receipts": 0,
    }
    assert store.table_counts()["candidate_root_operations"] == 1


def test_same_operation_changed_candidate_fails_closed(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    publish_root(store, request)
    changed = deepcopy(request)
    changed["raw_items"][0]["fact"] = "甲已经进入北塔。"
    before = store.table_counts()
    with pytest.raises(CandidateAuthorityError, match="ROOT_OPERATION_INPUT_CONFLICT"):
        publish_root(store, changed)
    assert store.table_counts() == before


def test_same_pointer_new_operation_fails_closed(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    publish_root(store, request)
    changed = deepcopy(request)
    changed["operation_id"] = "root-operation-conflict"
    before = store.table_counts()
    with pytest.raises(CandidateAuthorityError, match="ROOT_POINTER_ALREADY_INITIALIZED"):
        publish_root(store, changed)
    assert store.table_counts() == before


def test_multiple_segments_share_one_store_without_pointer_collision(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    first = root_request(seg=1, operation_id="root-seg-1")
    second = root_request(seg=2, operation_id="root-seg-2")
    result_one = publish_root(store, first)
    result_two = publish_root(store, second)
    assert result_one["logical_pointer_key"] != result_two["logical_pointer_key"]
    counts = store.table_counts()
    assert counts["candidate_versions"] == 2
    assert counts["current_pointers"] == 2
    assert counts["candidate_root_operations"] == 2
    assert counts["candidate_aux_records"] == 3


def test_multiple_chapters_and_input_generations_have_distinct_roots(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    requests = [
        root_request(operation_id="root-chapter-1"),
        root_request(
            operation_id="root-chapter-2",
            chapter_id="synthetic-chapter-002",
            revision_no=1,
            author_workspace_logical_key="fixture-workspace-002",
            generation_hex="d",
        ),
        root_request(
            operation_id="root-generation-2",
            author_workspace_logical_key="fixture-workspace-generation-2",
            generation_hex="e",
        ),
    ]
    results = [publish_root(store, request) for request in requests]
    assert len({item["logical_pointer_key"] for item in results}) == 3
    assert len(
        {item["candidate_version_ref"]["record_hash"] for item in results}
    ) == 3
    assert store.visible_counts()["candidate_versions"] == 3
    assert store.visible_counts()["current_pointers"] == 3


def test_project_scope_mismatch_is_rejected_before_write(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request(project_scope_id="other-project")
    with pytest.raises(CandidateAuthorityError, match="ROOT_AUTHORITY_SCOPE_MISMATCH"):
        publish_root(store, request)
    assert store.visible_counts()["candidate_versions"] == 0


def test_existing_store_rejects_wrong_project_before_read(tmp_path: Path) -> None:
    authority_root = tmp_path / "authority"
    store = new_store(authority_root)
    publish_root(store, root_request())
    with pytest.raises(CandidateAuthorityError, match="PROJECT_SCOPE_STORE_MISMATCH"):
        CandidateAuthorityStore(
            authority_root,
            project_scope_id="other-project",
        )


def test_stale_chapter_or_input_generation_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    snapshot = authority_snapshot(request)
    snapshot["chapter_revision_ref"] = {
        **snapshot["chapter_revision_ref"],
        "revision_no": snapshot["chapter_revision_ref"]["revision_no"] + 1,
    }
    reader = MutableRootAuthorityReader(snapshot)
    with pytest.raises(CandidateAuthorityError, match="ROOT_AUTHORITY_SCOPE_MISMATCH"):
        publish_root(store, request, reader=reader)
    assert store.visible_counts()["candidate_versions"] == 0


def test_authority_drift_between_reads_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    reader = MutableRootAuthorityReader(authority_snapshot(request))
    reader.drift_on_read = 2
    with pytest.raises(CandidateAuthorityError, match="ROOT_AUTHORITY_SCOPE_MISMATCH"):
        publish_root(store, request, reader=reader)
    assert store.visible_counts()["candidate_versions"] == 0


def test_root_rejects_authority_reader_without_serialization(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    with pytest.raises(
        CandidateAuthorityError, match="ROOT_AUTHORITY_SERIALIZATION_REQUIRED"
    ):
        CandidateRootInitializer(
            store=store,
            authority_reader=lambda: authority_snapshot(request),
        ).initialize_root(request)
    assert store.visible_counts()["candidate_versions"] == 0


def test_authority_writer_cannot_cross_root_commit_linearization(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    request = root_request()
    reader = MutableRootAuthorityReader(authority_snapshot(request))
    original_publish = store._publish_root
    mutation_started = Event()
    mutation_finished = Event()
    mutation_threads: list[Thread] = []

    def publish_while_writer_races(**kwargs: object) -> dict:
        changed = authority_snapshot(request)
        changed["input_generation_hash"] = "f" * 64

        def mutate_authority() -> None:
            mutation_started.set()
            reader.replace_snapshot(changed)
            mutation_finished.set()

        thread = Thread(target=mutate_authority)
        mutation_threads.append(thread)
        thread.start()
        assert mutation_started.wait(timeout=1)
        assert not mutation_finished.wait(timeout=0.05)
        return original_publish(**kwargs)

    store._publish_root = publish_while_writer_races
    result = CandidateRootInitializer(
        store=store,
        authority_reader=reader,
    ).initialize_root(request)
    for thread in mutation_threads:
        thread.join(timeout=1)
        assert not thread.is_alive()
    assert mutation_finished.is_set()
    assert result["reused_existing_initialization"] is False
    stored = store.read_root_operation(request["operation_id"])
    assert stored["authority_snapshot"] == authority_snapshot(request)


@pytest.mark.parametrize(
    "failure_point",
    ["after_records_insert", "after_pointer_insert", "before_commit"],
)
def test_root_transaction_failure_rolls_back_everything(
    tmp_path: Path, failure_point: str
) -> None:
    store = new_store(tmp_path / failure_point, failure_point=failure_point)
    with pytest.raises(
        CandidateAuthorityError, match="ROOT_SIMULATED_TRANSACTION_FAILURE"
    ):
        publish_root(store, root_request())
    counts = store.table_counts()
    assert counts["candidate_versions"] == 0
    assert counts["current_pointers"] == 0
    assert counts["candidate_aux_records"] == 0
    assert counts["candidate_root_operations"] == 0


def test_concurrent_same_root_has_one_physical_commit(tmp_path: Path) -> None:
    authority_root = tmp_path / "authority"
    new_store(authority_root)
    request = root_request()

    def run_once() -> dict:
        store = CandidateAuthorityStore(
            authority_root,
            project_scope_id=PROJECT,
        )
        return publish_root(store, request)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: run_once(), range(2)))
    assert sorted(item["reused_existing_initialization"] for item in results) == [
        False,
        True,
    ]
    reopened = CandidateAuthorityStore(authority_root, project_scope_id=PROJECT)
    assert reopened.visible_counts()["candidate_versions"] == 1
    assert reopened.visible_counts()["current_pointers"] == 1
    assert reopened.table_counts()["candidate_root_operations"] == 1


def test_two_processes_concurrently_initialize_one_root(tmp_path: Path) -> None:
    authority_root = tmp_path / "authority"
    new_store(authority_root)
    start_file = tmp_path / "start"
    command = [
        sys.executable,
        str(ROOT / "root_process_probe.py"),
        "--root",
        str(authority_root),
        "--project-scope-id",
        PROJECT,
        "--start-file",
        str(start_file),
    ]
    environment = {**os.environ, "PYTHONPATH": str(ROOT.parent.parent)}
    processes = [
        subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        for _index in range(2)
    ]
    start_file.write_text("go", encoding="utf-8")
    outputs = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, stderr
        outputs.append(json.loads(stdout))
    assert sorted(item["reused_existing_initialization"] for item in outputs) == [
        False,
        True,
    ]
    assert outputs[0]["candidate_version_ref"] == outputs[1][
        "candidate_version_ref"
    ]
    reopened = CandidateAuthorityStore(authority_root, project_scope_id=PROJECT)
    assert reopened.visible_counts()["candidate_versions"] == 1
    assert reopened.visible_counts()["current_pointers"] == 1
    assert reopened.table_counts()["candidate_root_operations"] == 1


def test_b06_bootstrap_copy_is_forbidden_on_authority_store(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    with pytest.raises(CandidateAuthorityError, match="B06_BOOTSTRAP_COPY_FORBIDDEN"):
        store.initialize()
    assert store.bootstrap_copy_attempt_count == 1
    assert store.visible_counts()["candidate_versions"] == 0


def test_full_b01_to_b08_shadow_uses_one_candidate_database(
    tmp_path: Path,
) -> None:
    environment = build_full_shadow(tmp_path / "shadow")
    result = environment.result
    assert result["result"] == "PASS"
    assert result["candidate_database_files"] == 1
    assert result["b01_state_json_files"] == 0
    assert result["b06_bootstrap_copy_calls"] == 0
    assert result["pointer_generation"] == 2
    assert result["pointer_targets_child"] is True
    assert result["terminal_binds_child"] is True
    assert result["terminal_binds_merge_receipt"] is True
    assert result["formal_tables"] == []
    assert result["formal_writes"] == 0
    assert result["model_api_calls"] == 0
    assert result["network_api_calls"] == 0


def test_cross_process_reopen_reads_child_pointer_receipt_and_terminal(
    tmp_path: Path,
) -> None:
    environment = build_full_shadow(tmp_path / "shadow")
    command = [
        sys.executable,
        str(ROOT / "reopen_probe.py"),
        "--root",
        str(environment.authority_root),
        "--project-scope-id",
        PROJECT,
        "--pointer-key",
        environment.pointer_key,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT.parent.parent)},
    )
    result = json.loads(completed.stdout)
    assert result["candidate_id"] == environment.result["child_candidate_id"]
    assert result["candidate_hash"] == environment.result["child_candidate_hash"]
    assert result["pointer_generation"] == 2
    assert result["merge_receipt_count"] == 1
    assert result["table_counts"]["b08_segment_terminal_receipts"] == 1


def test_b01_json_then_b06_sqlite_migration_is_exact_and_replayable(
    tmp_path: Path,
) -> None:
    legacy_b01_root = tmp_path / "legacy-b01"
    legacy_service, legacy_admit = b01_fixtures.fixture_runtime(
        FixtureStore(legacy_b01_root)
    )
    legacy_request = b01_fixtures.base_request()
    b01_fixtures.initialize_request(
        legacy_service,
        legacy_admit,
        legacy_request,
    )
    b01_state_path = legacy_b01_root / "state.json"
    b01_hash = file_sha256(b01_state_path)

    legacy_b06 = b06_fixtures.build_environment(tmp_path / "legacy-b06")
    legacy_b06.commit()
    b06_database = legacy_b06.store.root / "b06-commit-core.sqlite3"
    b06_hash = file_sha256(b06_database)

    destination = new_store(tmp_path / "destination")
    migration = LegacyCandidateMigration(destination)
    augmented_request = {
        **legacy_request,
        "input_generation_id": next(
            record
            for record in legacy_request["reference_records"]
            if canonical_bytes(record_ref(record))
            == canonical_bytes(legacy_request["accepted_source_generation_ref"])
        )["payload"]["workspace_generation_id"],
    }
    b01_result = migration.migrate_b01_json(
        source_state_path=b01_state_path,
        authority_snapshot=authority_snapshot(augmented_request),
        reference_records=legacy_request["reference_records"],
        migration_id="migrate-b01-001",
    )
    b06_result = migration.migrate_b06_sqlite(
        source_database_path=b06_database,
        reference_records=legacy_b06.reference_records,
        migration_id="migrate-b06-001",
    )
    b01_replay = migration.migrate_b01_json(
        source_state_path=b01_state_path,
        authority_snapshot=authority_snapshot(augmented_request),
        reference_records=legacy_request["reference_records"],
        migration_id="migrate-b01-001",
    )
    b06_replay = migration.migrate_b06_sqlite(
        source_database_path=b06_database,
        reference_records=legacy_b06.reference_records,
        migration_id="migrate-b06-001",
    )
    assert b01_result["reused"] is False
    assert b06_result["reused"] is False
    assert b01_replay["reused"] is True
    assert b06_replay["reused"] is True
    assert file_sha256(b01_state_path) == b01_hash
    assert file_sha256(b06_database) == b06_hash
    counts = destination.table_counts()
    assert counts["candidate_versions"] == 2
    assert counts["current_pointers"] == 1
    assert counts["merge_receipts"] == 1
    assert counts["candidate_migrations"] == 2
    pointer = destination.read_pointer(b01_result["pointer_logical_key"])
    assert pointer["generation"] == 2


def test_b01_source_change_before_commit_rolls_back_destination(
    tmp_path: Path,
) -> None:
    legacy_root = tmp_path / "legacy-b01"
    request = b01_fixtures.base_request()
    service, admit = b01_fixtures.fixture_runtime(FixtureStore(legacy_root))
    b01_fixtures.initialize_request(service, admit, request)
    source = legacy_root / "state.json"
    generation = next(
        record
        for record in request["reference_records"]
        if canonical_bytes(record_ref(record))
        == canonical_bytes(request["accepted_source_generation_ref"])
    )
    augmented = {
        **request,
        "input_generation_id": generation["payload"]["workspace_generation_id"],
    }
    destination = new_store(tmp_path / "destination")
    original_import = destination.import_legacy_b01_snapshot

    def import_after_source_change(**kwargs: object) -> dict:
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        return original_import(**kwargs)

    destination.import_legacy_b01_snapshot = import_after_source_change
    with pytest.raises(
        CandidateAuthorityError, match="MIGRATION_SOURCE_MUTATED_BEFORE_COMMIT"
    ):
        LegacyCandidateMigration(destination).migrate_b01_json(
            source_state_path=source,
            authority_snapshot=authority_snapshot(augmented),
            reference_records=request["reference_records"],
            migration_id="source-change-b01",
        )
    counts = destination.table_counts()
    assert counts["candidate_versions"] == 0
    assert counts["current_pointers"] == 0
    assert counts["candidate_root_operations"] == 0
    assert counts["candidate_migrations"] == 0


def test_b06_source_change_before_commit_rolls_back_destination(
    tmp_path: Path,
) -> None:
    legacy = b06_fixtures.build_environment(tmp_path / "legacy-b06")
    legacy.commit()
    source = legacy.store.root / "b06-commit-core.sqlite3"
    destination = new_store(tmp_path / "destination")
    original_import = destination.import_legacy_b06_snapshot

    def import_after_source_change(**kwargs: object) -> dict:
        with sqlite3.connect(source) as connection:
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                ("review-source-change", sqlite3.Binary(b"1")),
            )
            connection.commit()
        return original_import(**kwargs)

    destination.import_legacy_b06_snapshot = import_after_source_change
    with pytest.raises(
        CandidateAuthorityError, match="MIGRATION_SOURCE_MUTATED_BEFORE_COMMIT"
    ):
        LegacyCandidateMigration(destination).migrate_b06_sqlite(
            source_database_path=source,
            reference_records=legacy.reference_records,
            migration_id="source-change-b06",
        )
    counts = destination.table_counts()
    assert counts["candidate_versions"] == 0
    assert counts["current_pointers"] == 0
    assert counts["merge_receipts"] == 0
    assert counts["candidate_migrations"] == 0


@pytest.mark.parametrize("tamper", ["row_key", "payload_project"])
def test_b06_migration_rejects_pointer_row_identity_mismatch(
    tmp_path: Path, tamper: str
) -> None:
    legacy = b06_fixtures.build_environment(tmp_path / f"legacy-{tamper}")
    legacy.commit()
    source = legacy.store.root / "b06-commit-core.sqlite3"
    with sqlite3.connect(source) as connection:
        row = connection.execute(
            "SELECT logical_pointer_key, pointer_json FROM current_pointers"
        ).fetchone()
        if tamper == "row_key":
            connection.execute(
                "UPDATE current_pointers SET logical_pointer_key = ? "
                "WHERE logical_pointer_key = ?",
                ("mismatched-row-key", row[0]),
            )
        else:
            pointer = json.loads(bytes(row[1]).decode("utf-8"))
            pointer["project_scope_id"] = "other-project"
            connection.execute(
                "UPDATE current_pointers SET pointer_json = ? "
                "WHERE logical_pointer_key = ?",
                (sqlite3.Binary(canonical_bytes(pointer)), row[0]),
            )
        connection.commit()
    destination = new_store(tmp_path / f"destination-{tamper}")
    with pytest.raises(
        CandidateAuthorityError, match="MIGRATION_POINTER_ROW_MISMATCH"
    ):
        LegacyCandidateMigration(destination).migrate_b06_sqlite(
            source_database_path=source,
            reference_records=legacy.reference_records,
            migration_id=f"row-mismatch-{tamper}",
        )
    assert destination.visible_counts() == {
        "candidate_versions": 0,
        "current_pointers": 0,
        "merge_receipts": 0,
    }
    assert destination.table_counts()["candidate_migrations"] == 0


def test_same_legacy_source_cannot_use_a_second_migration_id(
    tmp_path: Path,
) -> None:
    legacy = b06_fixtures.build_environment(tmp_path / "legacy-b06")
    legacy.commit()
    source = legacy.store.root / "b06-commit-core.sqlite3"
    destination = new_store(tmp_path / "destination")
    migration = LegacyCandidateMigration(destination)
    migration.migrate_b06_sqlite(
        source_database_path=source,
        reference_records=legacy.reference_records,
        migration_id="source-once-001",
    )
    before = destination.table_counts()
    with pytest.raises(
        CandidateAuthorityError, match="MIGRATION_SOURCE_ALREADY_IMPORTED"
    ):
        migration.migrate_b06_sqlite(
            source_database_path=source,
            reference_records=legacy.reference_records,
            migration_id="source-once-002",
        )
    assert destination.table_counts() == before
    assert before["candidate_migrations"] == 1


def test_b01_migration_id_cannot_be_reused_for_changed_source(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "legacy-first"
    first_service, first_admit = b01_fixtures.fixture_runtime(FixtureStore(first_root))
    first_request = b01_fixtures.base_request()
    b01_fixtures.initialize_request(first_service, first_admit, first_request)
    generation = next(
        record
        for record in first_request["reference_records"]
        if canonical_bytes(record_ref(record))
        == canonical_bytes(first_request["accepted_source_generation_ref"])
    )
    augmented = {
        **first_request,
        "input_generation_id": generation["payload"]["workspace_generation_id"],
    }
    store = new_store(tmp_path / "destination")
    migration = LegacyCandidateMigration(store)
    migration.migrate_b01_json(
        source_state_path=first_root / "state.json",
        authority_snapshot=authority_snapshot(augmented),
        reference_records=first_request["reference_records"],
        migration_id="fixed-migration-id",
    )

    second_root = tmp_path / "legacy-second"
    second_service, second_admit = b01_fixtures.fixture_runtime(
        FixtureStore(second_root)
    )
    second_request = b01_fixtures.base_request(
        raw_items=[
            {
                "fact": "乙停在门外。",
                "status": "已发生",
                "evidence": "乙停在门外。",
                "speaker": "旁白",
            }
        ]
    )
    second_request["seg"] = 2
    second_request["operation_id"] = "legacy-second-operation"
    b01_fixtures.initialize_request(second_service, second_admit, second_request)
    before = store.table_counts()
    with pytest.raises(CandidateAuthorityError, match="MIGRATION_ID_INPUT_CONFLICT"):
        migration.migrate_b01_json(
            source_state_path=second_root / "state.json",
            authority_snapshot=authority_snapshot(augmented),
            reference_records=second_request["reference_records"],
            migration_id="fixed-migration-id",
        )
    assert store.table_counts() == before


def test_b06_migration_rejects_destination_as_source(tmp_path: Path) -> None:
    store = new_store(tmp_path / "authority")
    migration = LegacyCandidateMigration(store)
    with pytest.raises(
        CandidateAuthorityError, match="MIGRATION_SOURCE_EQUALS_DESTINATION"
    ):
        migration.migrate_b06_sqlite(
            source_database_path=store._database_path,
            reference_records=[],
            migration_id="self-migration",
        )


def test_reopen_rejects_wrong_authority_schema_identity(tmp_path: Path) -> None:
    authority_root = tmp_path / "authority"
    store = new_store(authority_root)
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE metadata SET value = ? WHERE key = 'authority_schema'",
            (sqlite3.Binary(b"unexpected-schema"),),
        )
        connection.commit()
    with pytest.raises(
        CandidateAuthorityError, match="AUTHORITY_SCHEMA_IDENTITY_MISMATCH"
    ):
        CandidateAuthorityStore(authority_root, project_scope_id=PROJECT)


def test_reopen_accepts_exact_authority_schema(tmp_path: Path) -> None:
    authority_root = tmp_path / "authority"
    new_store(authority_root)
    reopened = CandidateAuthorityStore(authority_root, project_scope_id=PROJECT)
    assert reopened.visible_counts() == {
        "candidate_versions": 0,
        "current_pointers": 0,
        "merge_receipts": 0,
    }


def test_reopen_upgrades_exact_pr230_metadata_gap_before_validation(
    tmp_path: Path,
) -> None:
    authority_root = tmp_path / "authority"
    store = new_store(authority_root)
    result = publish_root(store, root_request())
    before_counts = store.table_counts()
    before_pointer = store.read_pointer(result["logical_pointer_key"])
    before_candidate = store.read_candidate(result["candidate_version_ref"])
    remove_post_pr230_metadata(store)

    reopened = CandidateAuthorityStore(authority_root, project_scope_id=PROJECT)

    assert reopened.table_counts() == before_counts
    assert reopened.read_pointer(result["logical_pointer_key"]) == before_pointer
    assert reopened.read_candidate(result["candidate_version_ref"]) == before_candidate
    assert len(reopened.authority_store_id) == 64
    with sqlite3.connect(reopened.database_path) as connection:
        metadata = {
            row[0]: bytes(row[1]).decode("utf-8")
            for row in connection.execute(
                "SELECT key, value FROM metadata WHERE key IN (?, ?, ?, ?, ?)",
                tuple(sorted(UPGRADED_METADATA_KEYS)),
            ).fetchall()
        }
    assert set(metadata) == UPGRADED_METADATA_KEYS
    assert metadata["authority_identity"] == "FIXTURE_CANDIDATE_AUTHORITY"
    assert metadata["candidate_contract_version"] == "r03.5-candidate"
    assert metadata["candidate_access"] == "POLICY_FIXTURE_READ_ONLY"
    assert metadata["pointer_namespace"] == "FIXTURE_ONLY"


def test_pr230_metadata_upgrade_failure_rolls_back_without_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_root = tmp_path / "authority"
    store = new_store(authority_root)
    publish_root(store, root_request())
    remove_post_pr230_metadata(store)
    before = file_sha256(store.database_path)
    monkeypatch.setattr(
        candidate_authority_module.secrets,
        "token_hex",
        lambda _size: "not-a-valid-store-id",
    )

    with pytest.raises(CandidateAuthorityError, match="AUTHORITY_STORE_ID_INVALID"):
        CandidateAuthorityStore(authority_root, project_scope_id=PROJECT)

    assert file_sha256(store.database_path) == before
    with sqlite3.connect(store.database_path) as connection:
        remaining = connection.execute(
            "SELECT key FROM metadata WHERE key IN (?, ?, ?, ?, ?)",
            tuple(sorted(UPGRADED_METADATA_KEYS)),
        ).fetchall()
    assert remaining == []


@pytest.mark.parametrize(
    ("table", "replacement_sql"),
    [
        (
            "current_pointers",
            "CREATE TABLE current_pointers ("
            "logical_pointer_key TEXT, project_scope_id TEXT NOT NULL, "
            "pointer_json BLOB NOT NULL)",
        ),
        (
            "candidate_versions",
            "CREATE TABLE candidate_versions ("
            "ref_hash TEXT, record_json BLOB NOT NULL)",
        ),
        (
            "merge_receipts",
            "CREATE TABLE merge_receipts ("
            "project_scope_id TEXT NOT NULL, operation_id TEXT NOT NULL, "
            "request_hash TEXT NOT NULL UNIQUE, receipt_json BLOB NOT NULL)",
        ),
        (
            "candidate_root_operations",
            "CREATE TABLE candidate_root_operations ("
            "operation_id TEXT PRIMARY KEY, pointer_logical_key TEXT NOT NULL, "
            "request_hash TEXT NOT NULL UNIQUE, scope_hash TEXT NOT NULL, "
            "authority_snapshot_json BLOB NOT NULL, result_json BLOB NOT NULL)",
        ),
        (
            "candidate_versions",
            "CREATE TABLE candidate_versions ("
            "ref_hash TEXT PRIMARY KEY, record_json TEXT NOT NULL)",
        ),
        (
            "candidate_versions",
            "CREATE TABLE candidate_versions ("
            "ref_hash TEXT PRIMARY KEY, record_json BLOB)",
        ),
        (
            "candidate_versions",
            "CREATE TABLE candidate_versions ("
            "ref_hash TEXT PRIMARY KEY, "
            "record_json BLOB NOT NULL DEFAULT X'')",
        ),
    ],
    ids=[
        "pointer-primary-key",
        "candidate-primary-key",
        "receipt-composite-primary-key",
        "root-operation-pointer-unique",
        "column-type",
        "not-null",
        "default-value",
    ],
)
def test_reopen_rejects_inexact_authority_schema_before_data_access(
    tmp_path: Path,
    table: str,
    replacement_sql: str,
) -> None:
    authority_root = tmp_path / table
    store = new_store(authority_root)
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(f'DROP TABLE "{table}"')
        connection.execute(replacement_sql)
        connection.commit()
    before = file_sha256(store.database_path)
    with pytest.raises(CandidateAuthorityError, match="AUTHORITY_SCHEMA_"):
        CandidateAuthorityStore(authority_root, project_scope_id=PROJECT)
    assert file_sha256(store.database_path) == before


def test_current_contract_namespace_is_not_misreported_as_product_adoption(
    tmp_path: Path,
) -> None:
    store = new_store(tmp_path / "authority")
    result = publish_root(store, root_request())
    pointer = store.read_pointer(result["logical_pointer_key"])
    assert pointer["pointer_namespace"] == "FIXTURE_ONLY"


def test_schema_contains_no_formal_fact_or_ledger_tables(tmp_path: Path) -> None:
    environment = build_full_shadow(tmp_path / "shadow")
    forbidden = [
        table
        for table in environment.store.table_counts()
        if "formal" in table.lower() or "ledger" in table.lower()
    ]
    assert forbidden == []


def test_only_candidate_authority_store_mutates_destination_tables() -> None:
    mutation_needles = (
        "INSERT INTO candidate_versions",
        "INSERT INTO current_pointers",
        "UPDATE current_pointers",
        "INSERT INTO candidate_migrations",
    )
    production_files = [
        ROOT / "candidate_authority.py",
        ROOT / "legacy_migration.py",
        ROOT / "reopen_probe.py",
    ]
    owners = {
        path.name
        for path in production_files
        if any(needle in path.read_text(encoding="utf-8") for needle in mutation_needles)
    }
    assert owners == {"candidate_authority.py"}


def test_self_check_matches_frozen_offline_report() -> None:
    expected = json.loads(
        (ROOT / "OFFLINE_REPLAY_REPORT.json").read_text(encoding="utf-8")
    )
    assert run_self_check() == expected


def test_manifest_matches_every_committed_payload_file() -> None:
    manifest = ROOT / "MANIFEST.sha256"
    listed = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        listed[name] = digest
    expected_names = {
        path.name
        for path in ROOT.iterdir()
        if path.is_file() and path.name != manifest.name
    }
    assert set(listed) == expected_names
    for name, expected in listed.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert actual == expected
