"""Synthetic B-07 fixtures; no novel text, model call, or network access."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
for candidate in (REPOSITORY_ROOT, B06_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    CONTRACT_VERSION,
    RECORD_REF_CONTRACT,
    RUN_ACCESS,
    SOURCE_MODULE,
    sha256_value,
)
from b06_store import B06CommitService  # noqa: E402
from work.ccz57_m3_b06_commit_core_r01.fixtures import (  # noqa: E402
    B06FixtureEnvironment,
    build_environment as build_b06_environment,
)

from b07_adapters import derive_b06_request_hash  # noqa: E402
from b07_contracts import ACCESS_MAINTAINER_INTERNAL  # noqa: E402
from b07_store import B07RunStore  # noqa: E402


class FixtureClock:
    def __init__(self) -> None:
        self.tick = 0

    def __call__(self) -> str:
        value = f"2026-09-01T03:00:{self.tick:02d}Z"
        self.tick += 1
        return value


def generic_ref(record_type: str, record_id: str) -> dict[str, Any]:
    return {
        "contract": RECORD_REF_CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "record_version": 1,
        "record_contract_version": CONTRACT_VERSION,
        "record_hash": sha256_value(
            {"record_type": record_type, "record_id": record_id}
        ),
        "access": RUN_ACCESS,
        "source_module": SOURCE_MODULE,
    }


class AuthorityFixture:
    def __init__(self, b06: B06FixtureEnvironment) -> None:
        pointer = b06.store.read_pointer(b06.live_pointer["logical_pointer_key"])
        self.snapshot = {
            "chapter_revision_ref": deepcopy(pointer["chapter_revision_ref"]),
            "segment_scope_hash": sha256_value({"seg": pointer["seg"]}),
            "candidate_pointer_key": pointer["logical_pointer_key"],
            "observed_pointer_generation": pointer["generation"],
            "observed_candidate_version_ref": deepcopy(
                pointer["current_candidate_version_ref"]
            ),
            "budget_state_ref": generic_ref("M3_BUDGET_STATE", "budget:fixture"),
            "budget_state_hash": sha256_value({"budget": "active", "revision": 1}),
            "budget_revision": 1,
            "budget_allows_continue": True,
            "permission_state_ref": generic_ref(
                "M3_PERMISSION_STATE", "permission:fixture"
            ),
            "permission_state_hash": sha256_value(
                {"permission": "active", "revision": 1}
            ),
            "permission_revision": 1,
            "permission_active": True,
            "route_decision_ref": None,
            "route_decision_hash": None,
        }

    def __call__(self) -> dict[str, Any]:
        return deepcopy(self.snapshot)

    def sync_pointer(self, pointer: dict[str, Any]) -> None:
        self.snapshot["observed_pointer_generation"] = pointer["generation"]
        self.snapshot["observed_candidate_version_ref"] = deepcopy(
            pointer["current_candidate_version_ref"]
        )


@dataclass
class B07FixtureEnvironment:
    root: Path
    b06: B06FixtureEnvironment
    b07: B07RunStore
    clock: FixtureClock
    authority: AuthorityFixture
    project_scope_id: str
    logical_run_key: str
    run_id: str

    def open(self) -> dict[str, Any]:
        return self.b07.open_run(
            project_scope_id=self.project_scope_id,
            logical_run_key=self.logical_run_key,
            run_id=self.run_id,
            run_kind="FACT_EXTRACTION_REPAIR",
            operation_id="open-1",
            authority_reader=self.authority,
        )

    def publish_terminal(
        self,
        state: dict[str, Any],
        *,
        marker: str = "fixture",
        delivery: str = "BLOCKED",
    ) -> dict[str, Any]:
        b08_root = REPOSITORY_ROOT / "work" / "ccz57_m3_b08_segment_terminal_r01"
        if str(b08_root) not in sys.path:
            sys.path.insert(0, str(b08_root))
        from work.ccz57_m3_b08_segment_terminal_r01.b08_store import (
            B08SegmentTerminalStore,
        )
        from work.ccz57_m3_b08_segment_terminal_r01.fixtures import (
            B08AuthorityFixture,
            FixtureClock as B08FixtureClock,
        )

        authority = B08AuthorityFixture()
        if delivery == "BLOCKED":
            authority.classification.update(
                {
                    "product_result": "EXTRACTION_FAILED",
                    "terminal_delivery": "BLOCKED",
                    "reason_code": "B07_FIXTURE_STOP",
                    "candidate_count": 0,
                    "expected_unit_count": 1,
                    "covered_unit_count": 0,
                    "missing_unit_count": 1,
                    "coverage_complete": False,
                }
            )
        elif delivery != "COMPLETE":
            raise ValueError(f"B07_FIXTURE_DELIVERY_INVALID:{delivery}")
        store = B08SegmentTerminalStore(
            self.b06.store.root,
            clock=B08FixtureClock(),
            authority_reader=authority,
        )
        store.initialize_schema()
        return store.publish(
            project_scope_id=state["project_scope_id"],
            run_id=state["run_id"],
            operation_id=f"b08-{marker}",
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"],
        )

    def bind_terminal_observation(
        self,
        state: dict[str, Any],
        *,
        operation_id: str = "bind-terminal-observation",
        marker: str = "fixture",
    ) -> dict[str, Any]:
        if state["status"] == "ACTIVE" and state["phase"] == "FINALIZING":
            prepared = state
        else:
            prepared = self.b07.advance(
                project_scope_id=self.project_scope_id,
                run_id=self.run_id,
                operation_id=f"{operation_id}:finalizing",
                expected_run_epoch=state["run_epoch"],
                expected_state_revision=state["state_revision"],
                target_status="ACTIVE",
                target_phase="FINALIZING",
                wait_kind=None,
                authority_reader=self.authority,
            )
        terminal = self.publish_terminal(prepared, marker=marker)
        return self.b07.advance(
            project_scope_id=self.project_scope_id,
            run_id=self.run_id,
            operation_id=operation_id,
            expected_run_epoch=prepared["run_epoch"],
            expected_state_revision=prepared["state_revision"],
            target_status="ACTIVE",
            target_phase="FINALIZING",
            wait_kind=None,
            authority_reader=self.authority,
            component_observation=terminal["component_observation"],
        )

    def prepare_b06(
        self,
        state: dict[str, Any],
        *,
        b06_operation_id: str = "b06-operation-1",
        committed_at: str = "2026-09-01T03:01:00Z",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        run_fence = {
            "project_scope_id": self.project_scope_id,
            "run_id": self.run_id,
            "expected_run_epoch": state["run_epoch"],
            "expected_state_revision": state["state_revision"] + 1,
        }
        request_hash = derive_b06_request_hash(
            project_scope_id=self.project_scope_id,
            logical_pointer_key=self.b06.live_pointer["logical_pointer_key"],
            operation_id=b06_operation_id,
            route_receipt_ref=self.b06.route_receipt_ref,
            route_unit_id=self.b06.route_unit_id,
            patch_proposal=self.b06.b05.patch,
            protection_set=self.b06.b05.protection,
            committed_at=committed_at,
            run_fence=run_fence,
        )
        pointer = self.b06.store.read_pointer(
            self.b06.live_pointer["logical_pointer_key"]
        )
        pending = {
            "kind": "B06_PUBLISH",
            "operation_id": b06_operation_id,
            "request_hash": request_hash,
            "expected_pointer_key": pointer["logical_pointer_key"],
            "expected_pointer_generation": pointer["generation"],
            "expected_candidate_version_ref": deepcopy(
                pointer["current_candidate_version_ref"]
            ),
        }
        advanced = self.b07.advance(
            project_scope_id=self.project_scope_id,
            run_id=self.run_id,
            operation_id=f"prepare-{b06_operation_id}",
            expected_run_epoch=state["run_epoch"],
            expected_state_revision=state["state_revision"],
            target_status="B06_OUTCOME_PENDING",
            target_phase="COMMITTING",
            wait_kind=None,
            authority_reader=self.authority,
            pending_local_action=pending,
        )
        assert advanced["state_revision"] == run_fence["expected_state_revision"]
        return advanced, run_fence

    def commit_b06(
        self,
        *,
        run_fence: dict[str, Any],
        b06_operation_id: str = "b06-operation-1",
        committed_at: str = "2026-09-01T03:01:00Z",
    ) -> dict[str, Any]:
        return self.b06.service.commit(
            project_scope_id=self.project_scope_id,
            logical_pointer_key=self.b06.live_pointer["logical_pointer_key"],
            operation_id=b06_operation_id,
            route_receipt_ref=self.b06.route_receipt_ref,
            route_unit_id=self.b06.route_unit_id,
            patch_proposal=deepcopy(self.b06.b05.patch),
            protection_set=deepcopy(self.b06.b05.protection),
            committed_at=committed_at,
            run_fence=run_fence,
        )

    def debug_payload(self) -> dict[str, Any]:
        return {
            "event_kind": "LOCAL_COMPONENT_FAILURE",
            "component_kind": "FIXTURE_COMPONENT",
            "source_receipt_ref": generic_ref(
                "M3_COMPONENT_RECEIPT", "component:fixture"
            ),
            "source_receipt_hash": sha256_value({"component": "fixture"}),
            "stop_receipt_ref": None,
            "internal_error_code": "FIXTURE_FAILURE",
            "error_category": "LOCAL_COMPONENT",
            "error_fingerprint": sha256_value({"error": "fixture"}),
            "request_hash": sha256_value({"request": "fixture"}),
            "response_hash": None,
            "prompt_hash": None,
            "stack_fingerprint": None,
            "token_counts": {"input": 0, "output": 0, "cache": 0},
            "cost_microunits": 0,
            "currency": "USD",
            "latency_ms": 0,
            "retry_count": 0,
            "tool_call_count": 0,
            "provider_route_hash": None,
            "model_profile_hash": None,
            "retention_expires_at": "2026-09-08T03:00:00Z",
            "access_class": ACCESS_MAINTAINER_INTERNAL,
            "debug_payload_bytes": 512,
        }

    def saved_result_bytes(self) -> bytes:
        receipt = self.b06.b05.store.record_by_ref(self.b06.route_receipt_ref)
        return json.dumps(
            receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")


def build_environment(root: Path) -> B07FixtureEnvironment:
    b06 = build_b06_environment(root / "world")
    clock = FixtureClock()
    b07 = B07RunStore(b06.store.root, clock=clock)
    b07.initialize_schema()
    authority = AuthorityFixture(b06)
    b06.service = B06CommitService(
        store=b06.store,
        b05_store=b06.b05.store,
        freshness_reader=b06.freshness_reader,
        run_fence_reader=b07.run_fence_reader,
        reference_records=b06.reference_records,
    )
    return B07FixtureEnvironment(
        root=root,
        b06=b06,
        b07=b07,
        clock=clock,
        authority=authority,
        project_scope_id=b06.live_pointer["project_scope_id"],
        logical_run_key="logical-run:fixture",
        run_id="run-b07-fixture",
    )
