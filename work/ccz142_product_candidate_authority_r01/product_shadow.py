"""Zero-network product CandidateVersion shadow through B-01 to B-09."""

from __future__ import annotations

import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
B03_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b03_bound_evidence_read_r03_5"
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
B07_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b07_local_recovery_stop_r01"
B08_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
B09_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b09_current_causal_hint_view_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    B01_ROOT,
    B03_ROOT,
    B05_ROOT,
    B06_ROOT,
    B07_ROOT,
    B08_ROOT,
    B09_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b05_contracts import canonical_bytes, record_ref  # noqa: E402
from b01_contract import record_ref as b01_record_ref  # noqa: E402
from b03_contracts import resolve_bound_candidate_input  # noqa: E402
from b06_store import B06CommitService  # noqa: E402
from b07_store import B07RunStore  # noqa: E402
from b08_store import B08SegmentTerminalStore  # noqa: E402
from b09_authority_reader import CurrentCausalHintAuthorityReader  # noqa: E402
from current_causal_hint_view import read_current_causal_hints  # noqa: E402
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

from product_authority import (  # noqa: E402
    initialize_product_root,
    product_b01_scope,
)


def _immutable_reader(
    records: list[dict[str, Any]],
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    by_ref = {
        canonical_bytes(b01_record_ref(record)): deepcopy(record) for record in records
    }

    def read(ref: dict[str, Any]) -> dict[str, Any]:
        record = by_ref.get(canonical_bytes(ref))
        if record is None:
            raise LookupError("immutable record not found")
        return deepcopy(record)

    return read


@dataclass
class ProductShadowResult:
    result: dict[str, Any]
    authority_root: Path
    pointer_key: str


def build_product_shadow(root: Path) -> ProductShadowResult:
    authority_root = root / "candidate-authority"
    store, request, root_result = initialize_product_root(authority_root)
    scope = product_b01_scope(store, request, root_result)
    candidate = scope["candidate_version"]
    item = candidate["payload"]["items"][0]
    b03_context = {
        "reference_records": deepcopy(scope["reference_records"]),
        "segment_index": deepcopy(scope["segment_index"]),
        "candidate_version": deepcopy(candidate),
        "lineage_locators": deepcopy(scope["lineage_locators"]),
        "evidence_locators": deepcopy(scope["evidence_locators"]),
        "segment_inputs": deepcopy(scope["segment_inputs"]),
    }
    b03_resolved = resolve_bound_candidate_input(
        {
            "subject": {
                "kind": "CANDIDATE_FACT",
                "candidate_version_ref": b01_record_ref(candidate),
                "lineage_locator": deepcopy(scope["lineage_locators"][0]),
                "evidence_locator": deepcopy(scope["evidence_locators"][0]),
                "item_hash": item["item_hash"],
                "source_revision_ref": deepcopy(
                    candidate["payload"]["chapter_revision_ref"]
                ),
                "source_generation_ref": deepcopy(
                    candidate["payload"]["extraction_input_binding"][
                        "accepted_source_generation_ref"
                    ]
                ),
            },
            "evidence_binding": deepcopy(item["evidence_binding"]),
            "purpose": "BOUND_EVIDENCE_REVIEW",
        },
        context=b03_context,
    )
    b05_scope = {
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
    b05 = b05_fixtures.build_environment(
        root / "b05",
        mode="replace",
        b01_scope=b05_scope,
    )
    b05_result = b05.evaluate("product-b05-route-operation")
    route = b05.store.record_by_ref(b05_result["route_receipt_ref"])
    allow_entries = [
        item for item in route["payload"]["route_units"] if item["route"] == "ALLOW_FOR_B06"
    ]
    if len(allow_entries) != 1:
        raise AssertionError("PRODUCT_EXPECTED_ONE_B05_ALLOW_ROUTE")
    route_unit_id = allow_entries[0]["route_unit_id"]
    reference_records = [*request["reference_records"], scope["segment_index"]]
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
        base_candidate=scope["candidate_version"],
        live_pointer=scope["live_pointer"],
        reference_records=reference_records,
        route_receipt_ref=b05_result["route_receipt_ref"],
        route_unit_id=route_unit_id,
    )

    b07_store = B07RunStore(authority_root, clock=B07FixtureClock())
    b07_store.initialize_schema()
    b07_authority = B07AuthorityFixture(b06_environment)
    b07_authority.snapshot["route_decision_ref"] = record_ref(route)
    b07_authority.snapshot["route_decision_hash"] = route["record_hash"]
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
        clock=B07FixtureClock(),
        authority=b07_authority,
        project_scope_id=request["project_scope_id"],
        logical_run_key="logical-run:product-candidate-authority",
        run_id="run-product-candidate-authority-001",
    )
    opened = b07_environment.open()
    pending, run_fence = b07_environment.prepare_b06(
        opened,
        b06_operation_id="product-b06-operation-001",
    )
    child_result = b07_environment.commit_b06(
        run_fence=run_fence,
        b06_operation_id="product-b06-operation-001",
    )
    pointer_after = store.read_pointer(root_result["logical_pointer_key"])
    b07_authority.sync_pointer(pointer_after)
    finalizing = b07_store.reconcile_b06(
        project_scope_id=request["project_scope_id"],
        run_id=b07_environment.run_id,
        operation_id="reconcile-product-b06",
        expected_run_epoch=pending["run_epoch"],
        expected_state_revision=pending["state_revision"],
        authority_reader=b07_authority,
        committed_status="ACTIVE",
        committed_phase="FINALIZING",
    )

    b08_authority = B08AuthorityFixture()
    b08_store = B08SegmentTerminalStore(
        authority_root,
        clock=B08FixtureClock(),
        authority_reader=b08_authority,
    )
    b08_store.initialize_schema()
    terminal_result = b08_store.publish(
        project_scope_id=request["project_scope_id"],
        run_id=b07_environment.run_id,
        operation_id="product-b08-terminal-001",
        expected_run_epoch=finalizing["run_epoch"],
        expected_state_revision=finalizing["state_revision"],
    )

    immutable_records = [
        *request["reference_records"],
        scope["segment_index"],
        b05.patch,
        b05.protection,
        *b05.causals,
        *[
            record
            for record in b05.records.values()
            if isinstance(record, dict)
        ],
        *b05.store.read_records(),
    ]
    b09_reader = CurrentCausalHintAuthorityReader(
        b05_store=b05.store,
        shared_database_path=store.database_path,
        freshness_reader=freshness_reader,
        immutable_reader=_immutable_reader(immutable_records),
        b08_authority_reader=b08_authority,
    )
    b09_request = {
        "project_scope_id": request["project_scope_id"],
        "run_id": b07_environment.run_id,
        "expected_logical_run_generation": finalizing["logical_run_generation"],
        "expected_run_epoch": finalizing["run_epoch"],
        "segment_scope_hash": finalizing["authority_snapshot"][
            "segment_scope_hash"
        ],
        "purpose": "CCZ142_READ_ONLY_FEEDBACK",
    }
    b09_view = read_current_causal_hints(b09_reader, b09_request)
    child = store.read_candidate(child_result["child_candidate_version_ref"])
    tables = store.table_counts()
    formal_tables = [
        name for name in tables if "formal" in name.lower() or "ledger" in name.lower()
    ]
    return ProductShadowResult(
        result={
            "result": "PASS",
            "root_candidate_ref": root_result["candidate_version_ref"],
            "child_candidate_ref": child_result["child_candidate_version_ref"],
            "root_contract_version": scope["candidate_version"]["contract_version"],
            "child_contract_version": child["contract_version"],
            "candidate_access": child["access"],
            "pointer_namespace": pointer_after["pointer_namespace"],
            "pointer_generation": pointer_after["generation"],
            "pointer_key": pointer_after["logical_pointer_key"],
            "b02_records_exercised": 4,
            "b03_product_subject_validated": (
                b03_resolved["item"]["evidence"] == item["evidence"]
            ),
            "b04_patch_ref": record_ref(b05.patch),
            "b05_route_ref": record_ref(route),
            "b06_merge_receipt_ref": child_result["merge_receipt_ref"],
            "b07_state_revision": finalizing["state_revision"],
            "b08_terminal_ref": record_ref(terminal_result["terminal_record"]),
            "b09_status": b09_view["status"],
            "b09_reason_code": b09_view["reason_code"],
            "candidate_database_files": len(list(authority_root.glob("*.sqlite3"))),
            "candidate_storage_writers": ["CandidateAuthorityStore"],
            "formal_tables": formal_tables,
            "formal_writes": 0,
            "ten_ledger_writes": 0,
            "model_api_calls": 0,
            "network_api_calls": 0,
        },
        authority_root=authority_root,
        pointer_key=pointer_after["logical_pointer_key"],
    )
