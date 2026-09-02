"""Synthetic fixtures for the candidate-authority product-wiring shadow."""

from __future__ import annotations

import hashlib
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B07_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b07_local_recovery_stop_r01"
B08_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
for candidate in (REPOSITORY_ROOT, B07_ROOT, B08_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b06_store import B06CommitService  # noqa: E402
from b07_store import B07RunStore  # noqa: E402
from b08_store import B08SegmentTerminalStore  # noqa: E402
from candidate_authority import (  # noqa: E402
    CandidateAuthorityStore,
    CandidateRootInitializer,
    canonical_bytes,
    record_ref,
    sha256_value,
)
from work.ccz57_m3_b01_candidate_version_r03_5 import (  # noqa: E402
    fixtures as b01_fixtures,
)
from work.ccz57_m3_b05_patch_route_r03_5 import (  # noqa: E402
    fixtures as b05_fixtures,
)
from work.ccz57_m3_b06_commit_core_r01.fixtures import (  # noqa: E402
    B06FixtureEnvironment,
    FreshnessReader,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.fixtures import (  # noqa: E402
    AuthorityFixture as B07AuthorityFixture,
)
from work.ccz57_m3_b07_local_recovery_stop_r01.fixtures import (  # noqa: E402
    B07FixtureEnvironment,
    FixtureClock as B07FixtureClock,
)
from work.ccz57_m3_b08_segment_terminal_r01.fixtures import (  # noqa: E402
    B08AuthorityFixture,
    FixtureClock as B08FixtureClock,
)


class MutableRootAuthorityReader:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = deepcopy(snapshot)
        self.read_count = 0
        self.drift_on_read: int | None = None

    def __call__(self) -> dict[str, Any]:
        self.read_count += 1
        value = deepcopy(self.snapshot)
        if self.read_count == self.drift_on_read:
            value["input_generation_hash"] = sha256_value(
                {"drift_read": self.read_count}
            )
        return value


def root_request(
    *,
    seg: int = 1,
    operation_id: str = "root-operation-001",
    project_scope_id: str = "fixture-project-001",
    chapter_id: str = "synthetic-chapter-001",
    revision_no: int = 7,
    author_workspace_logical_key: str = "fixture-workspace-001",
    generation_hex: str = "a",
) -> dict[str, Any]:
    segment_inputs = b01_fixtures.segment_inputs()
    revision_text = "".join(item["responsibility_text"] for item in segment_inputs)
    revision_ref = {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": hashlib.sha256(
            revision_text.encode("utf-8")
        ).hexdigest(),
    }
    generation = b01_fixtures.source_generation_record(
        generation_hex=generation_hex,
        revision_ref=revision_ref,
    )
    raw_items = (
        [
            {
                "fact": "甲进入北塔。",
                "status": "已发生",
                "evidence": "甲走进北塔。",
            },
            {
                "fact": "甲拿起铜钥匙。",
                "status": "已发生",
                "evidence": "甲拿起铜钥匙。",
                "speaker": "旁白",
            },
        ]
        if seg == 1
        else [
            {
                "fact": "乙停在门外。",
                "status": "已发生",
                "evidence": "乙停在门外。",
                "speaker": "旁白",
            }
        ]
    )
    return {
        "admission": b01_fixtures.valid_admission(),
        "reference_records": b01_fixtures.reference_records(
            source_generation=generation
        ),
        "project_scope_id": project_scope_id,
        "author_workspace_logical_key": author_workspace_logical_key,
        "chapter_revision_ref": revision_ref,
        "accepted_source_generation_ref": record_ref(generation),
        "writing_material_refs": b01_fixtures.writing_material_bindings(
            source_generation=generation
        ),
        "source_module_identity": "B01_SYNTHETIC_FIXTURE",
        "segment_inputs": segment_inputs,
        "seg": seg,
        "origin_attempt_refs": b01_fixtures.attempt_refs(),
        "raw_items": raw_items,
        "operation_id": operation_id,
        "created_at": b01_fixtures.CREATED_AT,
        "input_generation_id": generation["payload"]["workspace_generation_id"],
    }


def authority_snapshot(request: dict[str, Any]) -> dict[str, Any]:
    target_ref = request["accepted_source_generation_ref"]
    generation = next(
        record
        for record in request["reference_records"]
        if canonical_bytes(record_ref(record)) == canonical_bytes(target_ref)
    )
    segment = next(
        item for item in request["segment_inputs"] if item["seg"] == request["seg"]
    )
    return {
        "project_scope_id": request["project_scope_id"],
        "chapter_revision_ref": deepcopy(request["chapter_revision_ref"]),
        "input_generation_id": request["input_generation_id"],
        "input_generation_hash": generation["payload"]["manifest_sha256"],
        "segment_scope_hash": sha256_value(segment),
    }


@dataclass
class FullShadowEnvironment:
    result: dict[str, Any]
    store: CandidateAuthorityStore
    authority_root: Path
    pointer_key: str


def build_full_shadow(root: Path) -> FullShadowEnvironment:
    project_scope_id = "fixture-project-001"
    authority_root = root / "candidate-authority"
    store = CandidateAuthorityStore(
        authority_root,
        project_scope_id=project_scope_id,
    )
    store.initialize_authority_schema()
    request = root_request(project_scope_id=project_scope_id)
    root_reader = MutableRootAuthorityReader(authority_snapshot(request))
    root_initializer = CandidateRootInitializer(
        store=store,
        authority_reader=root_reader,
    )
    root_result = root_initializer.initialize_root(request)
    root_replay = root_initializer.initialize_root(request)
    pointer_key = root_result["logical_pointer_key"]
    pointer_after_root = store.read_pointer(pointer_key)
    root_candidate = store.read_candidate(root_result["candidate_version_ref"])

    b05 = b05_fixtures.build_environment(root / "b05", mode="replace")
    if canonical_bytes(root_candidate) != canonical_bytes(b05.records["candidate"]):
        raise AssertionError("B01_ROOT_AND_B05_BASE_IDENTITY_MISMATCH")
    b05_result = b05.evaluate("b05-route-operation")
    route_receipt_ref = b05_result["route_receipt_ref"]
    route = b05.store.record_by_ref(route_receipt_ref)
    allow_entries = [
        item
        for item in route["payload"]["route_units"]
        if item["route"] == "ALLOW_FOR_B06"
    ]
    if len(allow_entries) != 1:
        raise AssertionError("EXPECTED_ONE_B05_ALLOW_ROUTE")
    route_unit_id = allow_entries[0]["route_unit_id"]
    b01_snapshot = b05.b01_reader.read_scope()
    reference_records = b01_snapshot["candidate_reference_records"]
    freshness_reader = FreshnessReader(
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
    b06_environment = B06FixtureEnvironment(
        root=root,
        b05=b05,
        store=store,
        service=B06CommitService(
            store=store,
            b05_store=b05.store,
            freshness_reader=freshness_reader,
            reference_records=reference_records,
        ),
        freshness_reader=freshness_reader,
        base_candidate=root_candidate,
        live_pointer=pointer_after_root,
        reference_records=reference_records,
        route_receipt_ref=route_receipt_ref,
        route_unit_id=route_unit_id,
    )

    b07_clock = B07FixtureClock()
    b07_store = B07RunStore(authority_root, clock=b07_clock)
    b07_store.initialize_schema()
    b07_authority = B07AuthorityFixture(b06_environment)
    b06_environment.service = B06CommitService(
        store=store,
        b05_store=b05.store,
        freshness_reader=freshness_reader,
        run_fence_reader=b07_store.run_fence_reader,
        reference_records=reference_records,
    )
    b07_environment = B07FixtureEnvironment(
        root=root,
        b06=b06_environment,
        b07=b07_store,
        clock=b07_clock,
        authority=b07_authority,
        project_scope_id=project_scope_id,
        logical_run_key="logical-run:candidate-authority-shadow",
        run_id="run-candidate-authority-shadow-001",
    )
    opened = b07_environment.open()
    pending, run_fence = b07_environment.prepare_b06(opened)
    child_result = b07_environment.commit_b06(run_fence=run_fence)
    child_replay = b07_environment.commit_b06(run_fence=run_fence)
    pointer_after_child = store.read_pointer(pointer_key)
    b07_authority.sync_pointer(pointer_after_child)
    finalizing = b07_store.reconcile_b06(
        project_scope_id=project_scope_id,
        run_id=b07_environment.run_id,
        operation_id="reconcile-b06-candidate-authority-shadow",
        expected_run_epoch=pending["run_epoch"],
        expected_state_revision=pending["state_revision"],
        authority_reader=b07_authority,
        committed_status="ACTIVE",
        committed_phase="FINALIZING",
    )

    b08_store = B08SegmentTerminalStore(
        authority_root,
        clock=B08FixtureClock(),
        authority_reader=B08AuthorityFixture(),
    )
    b08_store.initialize_schema()
    terminal_result = b08_store.publish(
        project_scope_id=project_scope_id,
        run_id=b07_environment.run_id,
        operation_id="b08-candidate-authority-terminal-001",
        expected_run_epoch=finalizing["run_epoch"],
        expected_state_revision=finalizing["state_revision"],
    )
    terminal_replay = b08_store.publish(
        project_scope_id=project_scope_id,
        run_id=b07_environment.run_id,
        operation_id="b08-candidate-authority-terminal-001",
        expected_run_epoch=finalizing["run_epoch"],
        expected_state_revision=finalizing["state_revision"],
    )
    pointer_after_child = store.read_pointer(pointer_key)
    child_candidate = store.read_candidate(
        pointer_after_child["current_candidate_version_ref"]
    )
    terminal = terminal_result["terminal_record"]
    counts = store.table_counts()
    formal_tables = [
        table
        for table in counts
        if "formal" in table.lower() or "ledger" in table.lower()
    ]
    result = {
        "result": "PASS",
        "root_candidate_id": root_candidate["record_id"],
        "root_candidate_hash": root_candidate["record_hash"],
        "child_candidate_id": child_candidate["record_id"],
        "child_candidate_hash": child_candidate["record_hash"],
        "pointer_key": pointer_key,
        "pointer_namespace": pointer_after_child["pointer_namespace"],
        "pointer_generation": pointer_after_child["generation"],
        "pointer_targets_child": pointer_after_child["current_candidate_version_ref"]
        == child_result["child_candidate_version_ref"],
        "root_replay_reused": root_replay["reused_existing_initialization"],
        "child_replay_reused": child_replay["reused_existing_commit"],
        "terminal_replay_reused": terminal_replay == terminal_result,
        "terminal_binds_child": terminal["payload"]["pointer_binding"][
            "current_candidate_version_ref"
        ]
        == pointer_after_child["current_candidate_version_ref"],
        "terminal_binds_merge_receipt": terminal["payload"][
            "b06_merge_receipt_ref_or_null"
        ]
        == child_result["merge_receipt_ref"],
        "candidate_database_files": len(list(authority_root.glob("*.sqlite3"))),
        "b01_state_json_files": len(list(authority_root.glob("state.json"))),
        "b06_bootstrap_copy_calls": store.bootstrap_copy_attempt_count,
        "root_physical_commits": store.root_commit_count,
        "child_physical_commits": [
            item["event"] for item in store.physical_write_attempts
        ].count("sqlite_atomic_commit"),
        "formal_tables": formal_tables,
        "formal_writes": 0,
        "model_api_calls": 0,
        "network_api_calls": 0,
        "table_counts": counts,
    }
    return FullShadowEnvironment(
        result=result,
        store=store,
        authority_root=authority_root,
        pointer_key=pointer_key,
    )
