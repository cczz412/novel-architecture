"""Synthetic B-05 to B-06 fixture assembly; contains no novel text."""

from __future__ import annotations

import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
for candidate in (REPOSITORY_ROOT, B05_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b05_patch_route_r03_5.b05_contracts import (  # noqa: E402
    record_ref,
    sha256_value,
)
from work.ccz57_m3_b05_patch_route_r03_5.fixtures import (  # noqa: E402
    FixtureEnvironment as B05FixtureEnvironment,
    build_environment as build_b05_environment,
)

from b06_store import B06CommitService, B06CommitStore  # noqa: E402

COMMITTED_AT = "2026-08-31T23:00:00Z"


class FreshnessReader:
    def __init__(self, snapshot: dict[str, str]) -> None:
        self.snapshot = deepcopy(snapshot)
        self.read_count = 0
        self.drift_on_read: int | None = None

    def __call__(self) -> dict[str, str]:
        self.read_count += 1
        if self.drift_on_read == self.read_count:
            self.snapshot["b02_scope_snapshot_hash"] = sha256_value(
                {"drift_read": self.read_count}
            )
        return deepcopy(self.snapshot)


@dataclass
class B06FixtureEnvironment:
    root: Path
    b05: B05FixtureEnvironment
    store: B06CommitStore
    service: B06CommitService
    freshness_reader: FreshnessReader
    base_candidate: dict[str, Any]
    live_pointer: dict[str, Any]
    reference_records: list[dict[str, Any]]
    route_receipt_ref: dict[str, Any]
    route_unit_id: str

    def commit(
        self, operation_id: str = "b06-operation-1", **kwargs: Any
    ) -> dict[str, Any]:
        return self.service.commit(
            project_scope_id=self.live_pointer["project_scope_id"],
            logical_pointer_key=self.live_pointer["logical_pointer_key"],
            operation_id=operation_id,
            route_receipt_ref=kwargs.pop(
                "route_receipt_ref", deepcopy(self.route_receipt_ref)
            ),
            route_unit_id=kwargs.pop("route_unit_id", self.route_unit_id),
            patch_proposal=kwargs.pop("patch_proposal", deepcopy(self.b05.patch)),
            protection_set=kwargs.pop("protection_set", deepcopy(self.b05.protection)),
            committed_at=kwargs.pop("committed_at", COMMITTED_AT),
            **kwargs,
        )

    def reopen(self) -> None:
        self.store = B06CommitStore(self.root / "b06")
        self.service = B06CommitService(
            store=self.store,
            b05_store=self.b05.store,
            freshness_reader=self.freshness_reader,
            reference_records=self.reference_records,
        )


def build_environment(
    root: Path,
    *,
    mode: str = "replace",
    b05_kwargs: dict[str, Any] | None = None,
    failure_point: str | None = None,
) -> B06FixtureEnvironment:
    b05 = build_b05_environment(root / "b05", mode=mode, **(b05_kwargs or {}))
    result = b05.evaluate("b05-route-operation")
    route_ref = result["route_receipt_ref"]
    route = b05.store.record_by_ref(route_ref)
    route_entries = route["payload"]["route_units"]
    allow_entries = [item for item in route_entries if item["route"] == "ALLOW_FOR_B06"]
    selected = allow_entries[0] if allow_entries else route_entries[0]
    b01_snapshot = b05.b01_reader.read_scope()
    base_candidate = b01_snapshot["candidate_version_record"]
    live_pointer = b01_snapshot["live_pointer_binding"]
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
    store = B06CommitStore(root / "b06", failure_point=failure_point)
    store.initialize(
        base_candidate=base_candidate,
        live_pointer=live_pointer,
        reference_records=reference_records,
    )
    service = B06CommitService(
        store=store,
        b05_store=b05.store,
        freshness_reader=freshness_reader,
        reference_records=reference_records,
    )
    return B06FixtureEnvironment(
        root=root,
        b05=b05,
        store=store,
        service=service,
        freshness_reader=freshness_reader,
        base_candidate=base_candidate,
        live_pointer=live_pointer,
        reference_records=reference_records,
        route_receipt_ref=record_ref(route),
        route_unit_id=selected["route_unit_id"],
    )
