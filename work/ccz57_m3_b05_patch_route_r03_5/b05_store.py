"""Atomic B-05 fixture store and pure offline evaluation service."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    validate_candidate_version as b01_validate_candidate_version,
)

from authoritative_readers import (  # noqa: E402
    B01CurrentReaderAdapter,
    B02CurrentScopeReader,
    B04PatchClosureReader,
    PolicyGateReader,
)
from b05_contracts import (  # noqa: E402
    B05ContractError,
    PatchLifecycleBuilder,
    PatchRouteDecider,
    PatchValidator,
    RUNTIME_COUNTER_KEYS,
    ValidatorIdentityBuilder,
    canonical_bytes,
    fail,
    record_ref,
    reference_cycle_count,
    sha256_value,
    stable_sorted,
    validate_immutable_record,
    validate_output_record,
    validate_record_ref,
    validate_validation_policy_semantics,
)
from candidate_mutation_kernel import (  # noqa: E402
    apply_groups as _apply_groups,
    build_child_payload as _build_child_payload,
    find_lineage as _find_lineage,
    item_hash as _item_hash,
)


def _identity(record: dict[str, Any]) -> tuple[str, str, int]:
    return record["record_type"], record["record_id"], record["record_version"]


def _identity_text(record: dict[str, Any]) -> str:
    return ":".join(str(item) for item in _identity(record))


_IDENTITY_PUBLISH_TOKEN = object()
_ROUTE_BUNDLE_PUBLISH_TOKEN = object()


def _validate_bundle_membership(records: list[dict[str, Any]]) -> None:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_type.setdefault(record["record_type"], []).append(record)
    if set(by_type) == {"M3_VALIDATOR_IDENTITY_RECEIPT"}:
        if len(records) != 1:
            fail("B05_VALIDATOR_IDENTITY_BUNDLE_INVALID")
        return
    required = {
        "M3_PATCH_VALIDATION_RECEIPT",
        "M3_PATCH_ROUTE_RECEIPT",
        "M3_PATCH_LIFECYCLE_RECEIPT",
    }
    if set(by_type) != required:
        fail("B05_ROUTE_BUNDLE_MEMBER_SET_INVALID")
    if (
        len(by_type["M3_PATCH_VALIDATION_RECEIPT"]) != 1
        or len(by_type["M3_PATCH_ROUTE_RECEIPT"]) != 1
        or len(by_type["M3_PATCH_LIFECYCLE_RECEIPT"]) not in {1, 2}
    ):
        fail("B05_ROUTE_BUNDLE_MEMBER_COUNT_INVALID")
    pvr = by_type["M3_PATCH_VALIDATION_RECEIPT"][0]
    route = by_type["M3_PATCH_ROUTE_RECEIPT"][0]
    lifecycles = by_type["M3_PATCH_LIFECYCLE_RECEIPT"]
    if not _ref_equal(route["payload"]["validation_receipt_ref"], record_ref(pvr)):
        fail("B05_ROUTE_PVR_BINDING_MISMATCH")
    for field in ("evaluation_key", "evaluation_input_hash"):
        if route["payload"][field] != pvr["payload"][field]:
            fail("B05_ROUTE_PVR_BINDING_MISMATCH")
    if any(
        item["payload"]["route_series_id"] != route["payload"]["route_series_id"]
        or item["payload"]["evaluation_key"] != route["payload"]["evaluation_key"]
        for item in lifecycles
    ):
        fail("B05_LIFECYCLE_ROUTE_BINDING_MISMATCH")
    if len(lifecycles) == 1:
        lifecycle = lifecycles[0]["payload"]
        if lifecycle["event"] != "ROUTES_FROZEN" or not _ref_equal(
            lifecycle["subject_route_receipt_ref"], record_ref(route)
        ):
            fail("B05_INITIAL_BUNDLE_LIFECYCLE_INVALID")
        return
    by_event = {item["payload"]["event"]: item["payload"] for item in lifecycles}
    if set(by_event) != {"SUPERSEDED", "REOPENED_WITH_NEW_MATERIAL"}:
        fail("B05_REOPEN_BUNDLE_EVENT_SET_INVALID")
    superseded = by_event["SUPERSEDED"]
    reopened = by_event["REOPENED_WITH_NEW_MATERIAL"]
    if (
        superseded["lifecycle_sequence"] + 1 != reopened["lifecycle_sequence"]
        or not _ref_equal(
            superseded["replacement_route_receipt_ref_or_null"], record_ref(route)
        )
        or not _ref_equal(reopened["subject_route_receipt_ref"], record_ref(route))
        or not _ref_equal(
            reopened["prior_route_receipt_ref_or_null"],
            superseded["subject_route_receipt_ref"],
        )
        or superseded["effective_at"] != reopened["effective_at"]
    ):
        fail("B05_REOPEN_BUNDLE_LIFECYCLE_INVALID")


class B05RouteStore:
    """Only committed SQLite bundle rows are readable as product originals."""

    __slots__ = (
        "root",
        "_database_path",
        "failure_point",
        "events",
        "physical_write_attempts",
        "_lock_path",
    )

    def __init__(self, root: Path, *, failure_point: str | None = None) -> None:
        self.root = self._guard_storage_path(root)
        self._database_path = self.root / "b05-route-bundles.sqlite3"
        self.failure_point = failure_point
        self.events: list[dict[str, str]] = []
        self.physical_write_attempts: list[dict[str, str]] = []
        self._lock_path = self.root / ".b05-publish.lock"

    @staticmethod
    def _guard_storage_path(path: Path) -> Path:
        resolved = path.resolve(strict=False)
        module_root = Path(__file__).resolve().parent
        repository_root = module_root.parents[1]
        temporary_root = Path(tempfile.gettempdir()).resolve()
        inside_repository = (
            resolved == repository_root or repository_root in resolved.parents
        )
        inside_module = resolved == module_root or module_root in resolved.parents
        inside_temp = resolved == temporary_root or temporary_root in resolved.parents
        if (inside_repository and not inside_module) or (
            not inside_repository and not inside_temp
        ):
            fail("B05_WRITE_SET_ESCAPE", str(path))
        return resolved

    def initialize(self) -> None:
        """Deployment/setup step; route evaluation itself never creates these paths."""

        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA journal_mode=TRUNCATE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS published_bundles (
                    transaction_id TEXT PRIMARY KEY,
                    bundle_json BLOB NOT NULL
                )
                """
            )

    @contextmanager
    def serialization(self) -> Iterator[None]:
        if not self._lock_path.is_file():
            fail("B05_STORE_NOT_INITIALIZED")
        flags = os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self._lock_path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                fail("B05_PUBLISH_LOCK_INVALID")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _inject(self, point: str) -> None:
        if self.failure_point == point:
            fail("B05_SIMULATED_TRANSACTION_FAILURE", point)

    def read_bundles(self) -> list[list[dict[str, Any]]]:
        if not self._database_path.is_file():
            return []
        bundles: list[list[dict[str, Any]]] = []
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT transaction_id, bundle_json FROM published_bundles "
                "ORDER BY transaction_id"
            ).fetchall()
        for transaction_id, raw_bundle in rows:
            records = json.loads(bytes(raw_bundle).decode("utf-8"))
            if not isinstance(records, list) or not records:
                fail("B05_EMPTY_PUBLISHED_BUNDLE", str(transaction_id))
            for record in records:
                validate_output_record(record)
            bundles.append(records)
        return bundles

    def read_records(self) -> list[dict[str, Any]]:
        records = [record for bundle in self.read_bundles() for record in bundle]
        seen: dict[tuple[str, str, int], bytes] = {}
        for record in records:
            key = _identity(record)
            raw = canonical_bytes(record)
            if key in seen and seen[key] != raw:
                fail("B05_IMMUTABLE_IDENTITY_COLLISION", _identity_text(record))
            seen[key] = raw
        return records

    def visible_snapshot(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        result: list[dict[str, Any]] = []
        for path in [self.root, *sorted(self.root.rglob("*"))]:
            relative = (
                "." if path == self.root else path.relative_to(self.root).as_posix()
            )
            if path.is_dir():
                result.append({"path": relative, "kind": "directory", "sha256": ""})
            elif path.is_file():
                result.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
        return result

    def _publish_locked(
        self, records: list[dict[str, Any]], *, publisher_token: object
    ) -> list[dict[str, Any]]:
        """Publish a whole record set by one directory rename.

        The private stage is outside the readable store root.  Product readers can
        therefore observe only an absent bundle or a complete bundle.
        """

        for record in records:
            validate_output_record(record)
        _validate_bundle_membership(records)
        contains_identity = records[0]["record_type"] == "M3_VALIDATOR_IDENTITY_RECEIPT"
        expected_token = (
            _IDENTITY_PUBLISH_TOKEN
            if contains_identity
            else _ROUTE_BUNDLE_PUBLISH_TOKEN
        )
        if publisher_token is not expected_token:
            fail("B05_PUBLISHER_SCOPE_ESCAPE")
        if len({_identity(item) for item in records}) != len(records):
            fail("B05_BUNDLE_IDENTITY_DUPLICATE")
        existing_records = self.read_records()
        existing_by_identity = {_identity(item): item for item in existing_records}
        for record in records:
            prior = existing_by_identity.get(_identity(record))
            if prior is not None:
                if canonical_bytes(prior) != canonical_bytes(record):
                    fail("B05_IMMUTABLE_IDENTITY_COLLISION", _identity_text(record))
                fail("B05_DUPLICATE_ORIGINAL_REQUIRES_BUNDLE_REUSE")
        if reference_cycle_count([*existing_records, *records]) != 0:
            fail("B05_REFERENCE_CYCLE")
        transaction_id = sha256_value(
            stable_sorted([record_ref(item) for item in records])
        )
        bundle_bytes = canonical_bytes(stable_sorted(records))
        with sqlite3.connect(self._database_path) as connection:
            existing_row = connection.execute(
                "SELECT bundle_json FROM published_bundles WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        if existing_row is not None:
            existing = json.loads(bytes(existing_row[0]).decode("utf-8"))
            if canonical_bytes(stable_sorted(existing)) != canonical_bytes(
                stable_sorted(records)
            ):
                fail("B05_CONCURRENT_PUBLISH_CONFLICT")
            return existing
        # These named checkpoints deliberately occur while the bundle exists only
        # in memory.  A simulated abort therefore cannot leave a file to delete.
        for index, _ in enumerate(
            sorted(records, key=lambda item: canonical_bytes(record_ref(item))),
            start=1,
        ):
            self._inject(f"after_stage_{index}")
        self._inject("before_atomic_publish")
        connection = sqlite3.connect(self._database_path)
        try:
            connection.execute("PRAGMA journal_mode=TRUNCATE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO published_bundles(transaction_id, bundle_json) "
                "VALUES (?, ?)",
                (transaction_id, sqlite3.Binary(bundle_bytes)),
            )
            self._inject("after_sqlite_insert")
            connection.commit()
            self.physical_write_attempts.append(
                {
                    "event": "sqlite_atomic_bundle_commit",
                    "transaction_id": transaction_id,
                }
            )
            self.events.append(
                {"event": "atomic_publish", "transaction_id": transaction_id}
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return deepcopy(records)

    def write_attempt_count(self) -> int:
        return len(self.physical_write_attempts)

    def assert_no_write_attempts_since(self, baseline: int) -> None:
        if self.write_attempt_count() != baseline:
            fail("B05_ZERO_WRITE_PROOF_FAILED")

    def record_by_ref(self, ref: dict[str, Any]) -> dict[str, Any]:
        validate_record_ref(ref)
        matches = [
            item
            for item in self.read_records()
            if canonical_bytes(record_ref(item)) == canonical_bytes(ref)
        ]
        if len(matches) != 1:
            fail("B05_LOCAL_RECORD_UNRESOLVABLE_OR_AMBIGUOUS")
        return deepcopy(matches[0])

    def validator_identity(self, ref: dict[str, Any]) -> dict[str, Any]:
        record = self.record_by_ref(ref)
        if record["record_type"] != "M3_VALIDATOR_IDENTITY_RECEIPT":
            fail("B05_VALIDATOR_IDENTITY_NOT_PREEXISTING")
        return record

    def pvr_for_operation(
        self, operation_id: str, project_scope_id: str
    ) -> dict[str, Any] | None:
        matches = [
            item
            for item in self.read_records()
            if item["record_type"] == "M3_PATCH_VALIDATION_RECEIPT"
            and item["payload"]["operation_id"] == operation_id
            and item["payload"]["input_binding"]["live_pointer_binding"][
                "project_scope_id"
            ]
            == project_scope_id
        ]
        if len(matches) > 1:
            fail("B05_OPERATION_ID_AMBIGUOUS")
        return deepcopy(matches[0]) if matches else None

    def route_bundle_for_input(self, input_hash: str) -> list[dict[str, Any]] | None:
        matches = []
        for bundle in self.read_bundles():
            pvr = [
                item
                for item in bundle
                if item["record_type"] == "M3_PATCH_VALIDATION_RECEIPT"
                and item["payload"]["evaluation_input_hash"] == input_hash
            ]
            if pvr:
                matches.append(bundle)
        if len(matches) > 1:
            fail("B05_INPUT_HASH_AMBIGUOUS")
        return deepcopy(matches[0]) if matches else None


class ValidatorIdentityRegistry:
    """Unique writer used only before an evaluation starts."""

    @staticmethod
    def register(
        store: B05RouteStore, *, payload: dict[str, Any], created_at: str
    ) -> dict[str, Any]:
        candidate = ValidatorIdentityBuilder.build(
            payload=payload, created_at=created_at
        )
        store.initialize()
        with store.serialization():
            for record in store.read_records():
                if _identity(record) == _identity(candidate):
                    if canonical_bytes(record) != canonical_bytes(candidate):
                        fail("B05_VALIDATOR_IDENTITY_COLLISION")
                    return record_ref(record)
            published = store._publish_locked(
                [candidate], publisher_token=_IDENTITY_PUBLISH_TOKEN
            )
        return record_ref(published[0])


class B05RouteBundlePublisher:
    """The only persistence owner for PVR, Route and Lifecycle originals."""

    @staticmethod
    def publish(
        store: B05RouteStore,
        *,
        records: list[dict[str, Any]],
        operation_id: str,
        project_scope_id: str,
        evaluation_input_hash: str,
        expected_authoritative_hash: str,
        authoritative_reread: Callable[[], str],
        expected_prior_state_hash: str,
        prior_state_reread: Callable[[], str],
        deterministic_result_hash: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        with store.serialization():
            try:
                current_authoritative_hash = authoritative_reread()
            except B05ContractError:
                fail("B05_AUTHORITATIVE_SNAPSHOT_DRIFT")
            if current_authoritative_hash != expected_authoritative_hash:
                fail("B05_AUTHORITATIVE_SNAPSHOT_DRIFT")
            prior_operation = store.pvr_for_operation(operation_id, project_scope_id)
            if prior_operation is not None:
                if (
                    prior_operation["payload"]["evaluation_input_hash"]
                    != evaluation_input_hash
                ):
                    fail("B05_OPERATION_ID_INPUT_CONFLICT")
            existing = store.route_bundle_for_input(evaluation_input_hash)
            if existing is not None:
                if _bundle_deterministic_hash(existing) != deterministic_result_hash:
                    fail("B05_NONDETERMINISTIC_RESULT")
                return existing, True
            if prior_state_reread() != expected_prior_state_hash:
                fail("B05_PRIOR_ROUTE_STATE_DRIFT")
            if prior_operation is not None:
                fail("B05_OPERATION_ID_BUNDLE_MISSING")
            published = store._publish_locked(
                records, publisher_token=_ROUTE_BUNDLE_PUBLISH_TOKEN
            )
            return published, False


def _bundle_deterministic_hash(records: list[dict[str, Any]]) -> str:
    pvr = next(
        item for item in records if item["record_type"] == "M3_PATCH_VALIDATION_RECEIPT"
    )
    route = next(
        item for item in records if item["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
    )
    pvr_payload = deepcopy(pvr["payload"])
    pvr_payload.pop("operation_id", None)
    pvr_semantic_proof_hash = sha256_value(pvr_payload)
    route_payload = deepcopy(route["payload"])
    route_payload["validation_receipt_ref"] = {
        "pvr_semantic_proof_hash": pvr_semantic_proof_hash
    }
    return sha256_value(
        {
            "pvr_semantic_proof_view": pvr_payload,
            "route_semantic_decision_view": route_payload,
        }
    )


def _ref_equal(left: Any, right: Any) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _unique_sorted(values: list[Any]) -> list[Any]:
    unique = {canonical_bytes(item): deepcopy(item) for item in values}
    return [unique[key] for key in sorted(unique)]


def _base_lineage_locator(
    base_record: dict[str, Any], item: dict[str, Any], index: int
) -> dict[str, Any]:
    locator = {
        "contract": "M3_LINEAGE_LOCATOR",
        "contract_version": base_record["contract_version"],
        "candidate_version_ref": record_ref(base_record),
        "lineage_id": item.get("lineage_id"),
        "json_pointer": f"/items/{index}",
        "item_hash": item.get("item_hash") or _item_hash(item),
        "locator_hash": "",
    }
    locator["locator_hash"] = sha256_value(
        {key: value for key, value in locator.items() if key != "locator_hash"}
    )
    return locator


def _locator_resolves_exact_base(locator: Any, base_record: dict[str, Any]) -> bool:
    if not isinstance(locator, dict):
        return False
    lineage = _find_lineage(locator)
    matches = [
        (index, item)
        for index, item in enumerate(base_record["payload"].get("items", []))
        if item.get("lineage_id") == lineage
    ]
    if len(matches) != 1:
        return False
    index, item = matches[0]
    if set(locator) == {
        "contract",
        "contract_version",
        "candidate_version_ref",
        "lineage_id",
        "json_pointer",
        "item_hash",
        "locator_hash",
    }:
        return canonical_bytes(locator) == canonical_bytes(
            _base_lineage_locator(base_record, item, index)
        )
    if set(locator) == {
        "contract",
        "contract_version",
        "candidate_version_ref",
        "lineage_id",
        "evidence_json_pointer",
        "evidence_sha256",
        "binding_hash",
        "locator_hash",
    }:
        binding = item.get("evidence_binding", {})
        expected = {
            "contract": "M3_EVIDENCE_LOCATOR",
            "contract_version": base_record["contract_version"],
            "candidate_version_ref": record_ref(base_record),
            "lineage_id": lineage,
            "evidence_json_pointer": f"/items/{index}/evidence",
            "evidence_sha256": binding.get("evidence_sha256"),
            "binding_hash": binding.get("binding_hash"),
            "locator_hash": "",
        }
        expected["locator_hash"] = sha256_value(
            {key: value for key, value in expected.items() if key != "locator_hash"}
        )
        return canonical_bytes(locator) == canonical_bytes(expected)
    return False


def _exact_global_protection_entries(
    patch: dict[str, Any], base_record: dict[str, Any]
) -> list[dict[str, Any]]:
    replaced_lineages = {
        _find_lineage(operation.get("target"))
        for group in patch["payload"]["atomic_groups"]
        for operation in group["operations"]
        if operation.get("operation_kind") == "REPLACE_CANDIDATE_ITEM"
    }
    return stable_sorted(
        [
            {
                "lineage_locator": _base_lineage_locator(base_record, item, index),
                "json_pointer": f"/items/{index}",
                "protected_item_hash": item.get("item_hash") or _item_hash(item),
                "reason": "UNTOUCHED_BY_THIS_PATCH_PROTECTED",
            }
            for index, item in enumerate(base_record["payload"].get("items", []))
            if item.get("lineage_id") not in replaced_lineages
        ]
    )


def _protection_matches_exact_base(
    patch: dict[str, Any],
    protection: dict[str, Any],
    base_record: dict[str, Any],
) -> bool:
    payload = protection["payload"]
    if not _ref_equal(
        payload.get("base_candidate_version_ref"), record_ref(base_record)
    ):
        return False
    if not _ref_equal(
        payload.get("chapter_revision_ref"),
        base_record["payload"].get("chapter_revision_ref"),
    ):
        return False
    expected = _exact_global_protection_entries(patch, base_record)
    return canonical_bytes(stable_sorted(payload.get("protected_entries", []))) == (
        canonical_bytes(expected)
    )


def _operation_fingerprint(operation: dict[str, Any]) -> str:
    return sha256_value(operation)


def _operation_sets(operation: dict[str, Any]) -> dict[str, list[Any]]:
    kind = operation.get("operation_kind")
    support_refs = stable_sorted(
        [
            *deepcopy(operation.get("supporting_diagnostic_refs", [])),
            *deepcopy(operation.get("supporting_coverage_refs", [])),
        ]
    )
    if kind == "REPLACE_CANDIDATE_ITEM":
        lineage = _find_lineage(operation.get("target"))
        target = {
            "kind": "LINEAGE_TARGET",
            "lineage_id": lineage,
            "target": deepcopy(operation.get("target")),
        }
        return {
            "logical_read_set": stable_sorted(
                [
                    target,
                    {
                        "kind": "OLD_ITEM_HASH",
                        "value": operation.get("expected_old_item_hash"),
                    },
                ]
            ),
            "logical_write_set": [target],
            "lineage_set": [] if lineage is None else [lineage],
            "support_refs": support_refs,
        }
    if kind == "ADD_CANDIDATE_ITEM":
        lineage = _find_lineage(operation.get("new_item"))
        target = {
            "kind": "COLLECTION_ADD",
            "json_pointer": operation.get("target_collection_pointer"),
            "lineage_id": lineage,
        }
        return {
            "logical_read_set": [],
            "logical_write_set": [target],
            "lineage_set": [] if lineage is None else [lineage],
            "support_refs": support_refs,
        }
    return {
        "logical_read_set": [],
        "logical_write_set": [{"kind": "FORBIDDEN_OPERATION", "value": kind}],
        "lineage_set": [],
        "support_refs": support_refs,
    }


def _group_proof_inputs(group: dict[str, Any]) -> dict[str, Any]:
    reads: list[Any] = []
    writes: list[Any] = []
    lineages: list[Any] = []
    supports: list[Any] = []
    for operation in group["operations"]:
        sets = _operation_sets(operation)
        reads.extend(sets["logical_read_set"])
        writes.extend(sets["logical_write_set"])
        lineages.extend(sets["lineage_set"])
        supports.extend(sets["support_refs"])
    return {
        "logical_read_set": _unique_sorted(reads),
        "logical_write_set": _unique_sorted(writes),
        "lineage_set": _unique_sorted(lineages),
        "support_refs": _unique_sorted(supports),
    }


def _token_bytes(values: list[Any]) -> set[bytes]:
    return {canonical_bytes(item) for item in values}


def _known_edges(
    groups: list[dict[str, Any]], policy_payload: dict[str, Any]
) -> list[dict[str, Any]]:
    validate_validation_policy_semantics(
        policy_payload=policy_payload,
        atomic_group_bindings=stable_sorted(
            [
                {
                    "atomic_group_id": group["atomic_group_id"],
                    "group_payload_hash": group["group_payload_hash"],
                }
                for group in groups
            ]
        ),
    )
    proofs = {group["atomic_group_id"]: _group_proof_inputs(group) for group in groups}
    edges: list[dict[str, Any]] = []
    for left_index, left in enumerate(groups):
        for right in groups[left_index + 1 :]:
            left_id = left["atomic_group_id"]
            right_id = right["atomic_group_id"]
            left_sets = proofs[left_id]
            right_sets = proofs[right_id]
            left_writes = _token_bytes(left_sets["logical_write_set"])
            right_writes = _token_bytes(right_sets["logical_write_set"])
            left_reads = _token_bytes(left_sets["logical_read_set"])
            right_reads = _token_bytes(right_sets["logical_read_set"])
            edge_type = None
            if left_writes & right_writes:
                edge_type = "WRITE_WRITE_OVERLAP"
            elif (left_writes & right_reads) or (right_writes & left_reads):
                edge_type = "WRITE_READ_OVERLAP"
            elif set(left_sets["lineage_set"]) & set(right_sets["lineage_set"]):
                edge_type = "TARGET_OR_LINEAGE_DEPENDENCY"
            left_add = all(
                operation.get("operation_kind") == "ADD_CANDIDATE_ITEM"
                for operation in left["operations"]
            )
            right_add = all(
                operation.get("operation_kind") == "ADD_CANDIDATE_ITEM"
                for operation in right["operations"]
            )
            if (
                edge_type is None
                and left_add
                and right_add
                and not policy_payload.get("canonical_add_sort_frozen", False)
            ):
                left_targets = {
                    operation.get("target_collection_pointer")
                    for operation in left["operations"]
                }
                right_targets = {
                    operation.get("target_collection_pointer")
                    for operation in right["operations"]
                }
                if left_targets & right_targets:
                    edge_type = "NON_COMMUTATIVE_APPLICATION"
            if edge_type is not None:
                endpoints = sorted(
                    [left_id, right_id], key=lambda item: canonical_bytes(item)
                )
                edge = {
                    "left_atomic_group_id": endpoints[0],
                    "right_atomic_group_id": endpoints[1],
                    "edge_type": edge_type,
                    "evidence_tokens": [
                        {
                            "type": "STABLE_CHECK_CODE",
                            "value": f"B05_CHECK_{edge_type}",
                        }
                    ],
                }
                edges.append(edge)
    for declared in policy_payload.get("declared_dependency_edges", []):
        edges.append(deepcopy(declared))
    return stable_sorted(edges)


def _unknown_tokens(
    groups: list[dict[str, Any]], policy_payload: dict[str, Any]
) -> list[dict[str, Any]]:
    valid_ids = {group["atomic_group_id"] for group in groups}
    tokens = []
    for item in policy_payload.get("unknown_dependency_tokens", []):
        bounded = stable_sorted(item.get("bounded_atomic_group_ids", []))
        if any(group_id not in valid_ids for group_id in bounded):
            fail("B05_UNKNOWN_DEPENDENCY_ENDPOINT_INVALID")
        supporting_refs = stable_sorted(item.get("supporting_refs", []))
        reason = item.get("reason_code", "DEPENDENCY_ENDPOINT_UNKNOWN")
        preimage = {
            "reason_code": reason,
            "bounded_atomic_group_ids": bounded,
            "supporting_refs": supporting_refs,
        }
        tokens.append(
            {
                "token_id": f"unknown-dependency:{sha256_value(preimage)}",
                **preimage,
            }
        )
    if any(
        group_id not in valid_ids
        for group_id in policy_payload.get("semantic_unknown_group_ids", [])
    ):
        fail("B05_SEMANTIC_UNKNOWN_ENDPOINT_INVALID")
    return stable_sorted(tokens)


def _partition_groups(
    patch_ref: dict[str, Any],
    groups: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    unknown: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = [group["atomic_group_id"] for group in groups]
    adjacency = {group_id: set() for group_id in ids}
    for edge in edges:
        left = edge["left_atomic_group_id"]
        right = edge["right_atomic_group_id"]
        if left not in adjacency or right not in adjacency:
            fail("B05_DEPENDENCY_EDGE_ENDPOINT_INVALID")
        adjacency[left].add(right)
        adjacency[right].add(left)
    for token in unknown:
        bounded = token["bounded_atomic_group_ids"]
        if not bounded:
            bounded = ids
        for left in bounded:
            for right in bounded:
                if left != right:
                    adjacency[left].add(right)
    components: list[list[str]] = []
    remaining = set(ids)
    while remaining:
        start = min(remaining, key=canonical_bytes)
        stack = [start]
        component = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(adjacency[node] - component)
        remaining -= component
        components.append(sorted(component, key=canonical_bytes))
    by_id = {group["atomic_group_id"]: group for group in groups}
    partition = []
    for component in components:
        bindings = [
            {
                "atomic_group_id": group_id,
                "group_payload_hash": by_id[group_id]["group_payload_hash"],
            }
            for group_id in component
        ]
        bindings = stable_sorted(bindings)
        route_unit_id = f"route-unit:{sha256_value({'patch_proposal_ref': patch_ref, 'atomic_group_bindings': bindings})}"
        partition.append(
            {"route_unit_id": route_unit_id, "atomic_group_bindings": bindings}
        )
    return stable_sorted(partition)


def _build_and_validate_trial_candidate(
    base_record: dict[str, Any],
    trial_payload: dict[str, Any],
    *,
    reference_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    payload = _build_child_payload(base_record, trial_payload)
    record = {
        key: deepcopy(value) for key, value in base_record.items() if key != "record_hash"
    }
    record["record_id"] = f"b05-trial:{payload['version_payload_hash']}"
    record["record_version"] = max(2, base_record["record_version"] + 1)
    record["payload"] = payload
    record["record_hash"] = sha256_value(record)
    try:
        b01_validate_candidate_version(
            record,
            allow_child=True,
            reference_records=deepcopy(reference_records),
        )
    except B01ContractError:
        return record, ["CANDIDATE_STRUCTURE_INVALID"]
    return record, []


def _check_result(
    code: str, status: str, subjects: list[Any], evidence: list[Any]
) -> dict[str, Any]:
    return {
        "check_code": code,
        "status": status,
        "subject_bindings": stable_sorted(subjects),
        "evidence_hashes": stable_sorted(evidence),
    }


def _series_state_from_route(
    store: B05RouteStore, route_ref: dict[str, Any]
) -> dict[str, Any]:
    route_record = store.record_by_ref(route_ref)
    if route_record["record_type"] != "M3_PATCH_ROUTE_RECEIPT":
        fail("B05_PRIOR_ROUTE_TYPE_INVALID")
    series_id = route_record["payload"]["route_series_id"]
    routes = [
        record
        for record in store.read_records()
        if record["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
        and record["payload"]["route_series_id"] == series_id
    ]
    relevant = [
        record
        for record in store.read_records()
        if record["record_type"] == "M3_PATCH_LIFECYCLE_RECEIPT"
        and record["payload"]["route_series_id"] == series_id
    ]
    sequences = [item["payload"]["lifecycle_sequence"] for item in relevant]
    if sorted(sequences) != list(range(1, len(sequences) + 1)):
        fail("B05_LIFECYCLE_SEQUENCE_INVALID")
    superseded = {
        canonical_bytes(item["payload"]["subject_route_receipt_ref"])
        for item in relevant
        if item["payload"]["event"] == "SUPERSEDED"
    }
    active = [
        route
        for route in routes
        if canonical_bytes(record_ref(route)) not in superseded
    ]
    if len(active) != 1 or not relevant:
        fail("B05_ACTIVE_ROUTE_AMBIGUOUS")
    head = max(relevant, key=lambda item: item["payload"]["lifecycle_sequence"])
    return {
        "active_route_receipt_ref_or_null": record_ref(active[0]),
        "lifecycle_head_ref_or_null": record_ref(head),
        "series_count": 1,
    }


def _prior_state_snapshot(
    store: B05RouteStore, patch_ref: dict[str, Any]
) -> dict[str, Any]:
    routes = [
        record
        for record in store.read_records()
        if record["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
        and _ref_equal(
            record["payload"]["binding_header"]["patch_proposal_ref"], patch_ref
        )
    ]
    if not routes:
        return {
            "active_route_receipt_ref_or_null": None,
            "lifecycle_head_ref_or_null": None,
            "series_count": 0,
        }
    series_ids = {route["payload"]["route_series_id"] for route in routes}
    if len(series_ids) != 1:
        fail("B05_MULTIPLE_ROUTE_SERIES_FOR_PATCH")
    return _series_state_from_route(store, record_ref(routes[0]))


class B05Service:
    """Orchestrate one trusted-input evaluation; never reads text or calls a model."""

    __slots__ = (
        "store",
        "b01_reader",
        "b02_reader",
        "policy_gate_reader",
        "protection_policy",
        "source_slice_records",
        "validator_identity_ref",
    )

    def __init__(
        self,
        store: B05RouteStore,
        *,
        b01_reader: B01CurrentReaderAdapter,
        b02_reader: B02CurrentScopeReader,
        policy_gate_reader: PolicyGateReader,
        protection_policy: dict[str, Any],
        source_slice_records: list[dict[str, Any]],
        validator_identity_ref: dict[str, Any],
    ) -> None:
        self.store = store
        self.b01_reader = b01_reader
        self.b02_reader = b02_reader
        self.policy_gate_reader = policy_gate_reader
        self.protection_policy = deepcopy(protection_policy)
        self.source_slice_records = deepcopy(source_slice_records)
        self.validator_identity_ref = deepcopy(validator_identity_ref)

    def _read_authoritative(
        self,
        patch: dict[str, Any],
        protection: dict[str, Any],
        causals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = patch["payload"]
        b01 = self.b01_reader.read_scope()
        b02 = self.b02_reader.read_scope(
            base_candidate_version_ref=payload["base_candidate_version_ref"],
            upstream_context=b01["upstream_context"],
            selected_diagnostic_refs=payload.get("diagnostic_refs", []),
            selected_coverage_observation_refs=payload.get(
                "coverage_observation_refs", []
            ),
        )
        b04 = B04PatchClosureReader.read(
            patch_proposal=patch,
            protection_set=protection,
            causal_hint_proposals=causals,
            protection_policy=self.protection_policy,
            source_slice_records=self.source_slice_records,
            upstream_context=b01["upstream_context"],
            b02_scope=b02,
        )
        atomic_group_bindings = stable_sorted(
            [
                {
                    "atomic_group_id": group["atomic_group_id"],
                    "group_payload_hash": group["group_payload_hash"],
                }
                for group in b04["patch_proposal"]["payload"]["atomic_groups"]
            ]
        )
        policy = self.policy_gate_reader.read(
            patch_proposal_ref=record_ref(patch),
            atomic_group_bindings=atomic_group_bindings,
        )
        return {"b01": b01, "b02": b02, "b04": b04, "policy": policy}

    def _validate_validator_identity(self, record: dict[str, Any]) -> None:
        payload = record["payload"]
        implementation = payload["implementation_identity"]
        root = Path(__file__).resolve().parent
        member_names = [
            "authoritative_readers.py",
            "b05_contracts.py",
            "b05_store.py",
            "candidate_mutation_kernel.py",
            "patch_route_projection.py",
        ]
        manifest_lines = [
            f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}"
            for name in member_names
        ]
        manifest_text = "\n".join(manifest_lines) + "\n"
        manifest_hash = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
        if (
            implementation.get("repository") != "cczz412/novel-architecture"
            or implementation.get("manifest_members") != manifest_lines
            or implementation.get("manifest_hash") != manifest_hash
            or implementation.get("implementation_tree_or_artifact_hash")
            != manifest_hash
        ):
            fail("B05_VALIDATOR_IMPLEMENTATION_IDENTITY_DRIFT")
        reader_sha = hashlib.sha256(
            (root / "authoritative_readers.py").read_bytes()
        ).hexdigest()
        expected_readers = {
            "b01_current_reader_adapter": (
                self.b01_reader.reader_identity,
                self.b01_reader.reader_version,
            ),
            "b02_current_scope_reader": (
                self.b02_reader.reader_identity,
                self.b02_reader.reader_version,
            ),
            "policy_reader": (
                self.policy_gate_reader.reader_identity,
                self.policy_gate_reader.reader_version,
            ),
            "gate_reader": (
                self.policy_gate_reader.reader_identity,
                self.policy_gate_reader.reader_version,
            ),
        }
        for key, (identity, version) in expected_readers.items():
            binding = implementation.get(key)
            if binding != {
                "reader_identity": identity,
                "reader_version": version,
                "implementation_sha256": reader_sha,
            }:
                fail("B05_VALIDATOR_READER_IDENTITY_DRIFT", key)

    @staticmethod
    def _authoritative_hash(snapshot: dict[str, Any]) -> str:
        b01 = snapshot["b01"]
        b02 = snapshot["b02"]
        b04 = snapshot["b04"]
        policy = snapshot["policy"]
        return sha256_value(
            {
                "b01_reader_identity": b01["reader_identity"],
                "b01_reader_version": b01["reader_version"],
                "candidate_version_ref": record_ref(b01["candidate_version_record"]),
                "segment_index_ref": record_ref(b01["segment_index_record"]),
                "pointer_snapshot_ref_or_null": None
                if b01["candidate_pointer_snapshot_record_or_null"] is None
                else record_ref(b01["candidate_pointer_snapshot_record_or_null"]),
                "live_pointer_binding_hash": b01["live_pointer_binding_hash"],
                "b02_scope_snapshot_hash": b02["scope_snapshot_hash"],
                "b04_closure_snapshot_hash": b04["closure_snapshot_hash"],
                "active_policy_selection_hash": policy["active_policy_selection_hash"],
                "non_content_gate_snapshot_hash": policy[
                    "non_content_gate_snapshot_hash"
                ],
            }
        )

    def _build_unit_proofs_and_routes(
        self,
        *,
        patch: dict[str, Any],
        protection: dict[str, Any],
        snapshot: dict[str, Any],
        partition: list[dict[str, Any]],
        unknown_tokens: list[dict[str, Any]],
        policy_payload: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        patch_payload = patch["payload"]
        groups = patch_payload["atomic_groups"]
        by_id = {group["atomic_group_id"]: group for group in groups}
        base_record = snapshot["b01"]["candidate_version_record"]
        base_payload = base_record["payload"]
        base_ref = record_ref(base_record)
        global_protection_valid = _protection_matches_exact_base(
            patch, protection, base_record
        )
        live_current = snapshot["b01"]["live_pointer_binding"][
            "current_candidate_version_ref"
        ]
        base_is_current = _ref_equal(base_ref, live_current)
        diagnostic_states = {
            canonical_bytes(item["diagnostic_ref"]): item["current_terminal_state"]
            for item in snapshot["b02"]["diagnostic_state_bindings"]
        }
        gates = snapshot["policy"]["non_content_gate_bindings"]
        unit_groups: dict[str, list[dict[str, Any]]] = {}
        for unit in partition:
            unit_groups[unit["route_unit_id"]] = [
                by_id[binding["atomic_group_id"]]
                for binding in unit["atomic_group_bindings"]
            ]
        route_unit_ids = set(unit_groups)
        for gate in gates:
            for target in gate[
                "applicable_atomic_group_bindings_or_route_unit_ids"
            ]:
                if isinstance(target, str) and target not in route_unit_ids:
                    fail("B05_GATE_APPLICABILITY_INVALID")
        exchange_by_unit: dict[str, list[dict[str, Any]]] = {
            unit["route_unit_id"]: [] for unit in partition
        }
        for left_index, left in enumerate(partition):
            for right in partition[left_index + 1 :]:
                left_groups = unit_groups[left["route_unit_id"]]
                right_groups = unit_groups[right["route_unit_id"]]
                left_then_right, _ = _apply_groups(
                    base_payload,
                    [*left_groups, *right_groups],
                    canonical_add_sort=policy_payload.get(
                        "canonical_add_sort_frozen", False
                    ),
                )
                right_then_left, _ = _apply_groups(
                    base_payload,
                    [*right_groups, *left_groups],
                    canonical_add_sort=policy_payload.get(
                        "canonical_add_sort_frozen", False
                    ),
                )
                check = {
                    "left_binding": deepcopy(left["atomic_group_bindings"]),
                    "right_binding": deepcopy(right["atomic_group_bindings"]),
                    "left_then_right_payload_hash": sha256_value(left_then_right),
                    "right_then_left_payload_hash": sha256_value(right_then_left),
                    "byte_identical": canonical_bytes(left_then_right)
                    == canonical_bytes(right_then_left),
                }
                exchange_by_unit[left["route_unit_id"]].append(deepcopy(check))
                exchange_by_unit[right["route_unit_id"]].append(deepcopy(check))
        proofs = []
        route_entries = []
        for unit in partition:
            route_unit_id = unit["route_unit_id"]
            selected_groups = unit_groups[route_unit_id]
            reads: list[Any] = []
            writes: list[Any] = []
            lineages: list[Any] = []
            supports: list[Any] = []
            for group in selected_groups:
                group_sets = _group_proof_inputs(group)
                reads.extend(group_sets["logical_read_set"])
                writes.extend(group_sets["logical_write_set"])
                lineages.extend(group_sets["lineage_set"])
                supports.extend(group_sets["support_refs"])
            reads = _unique_sorted(reads)
            writes = _unique_sorted(writes)
            lineages = _unique_sorted(lineages)
            supports = _unique_sorted(supports)
            written_lineages = set(lineages)
            protected_entries = []
            for index, item in enumerate(base_payload.get("items", [])):
                if item.get("lineage_id") in written_lineages:
                    continue
                protected_entries.append(
                    {
                        "lineage_locator": _base_lineage_locator(
                            base_record, item, index
                        ),
                        "json_pointer": f"/items/{index}",
                        "protected_item_hash": item.get("item_hash")
                        or _item_hash(item),
                        "protected_item_canonical_bytes_hash": sha256_value(item),
                        "protection_reason": "NOT_WRITTEN_BY_THIS_ROUTE_UNIT",
                    }
                )
            trial_payload, trial_errors = _apply_groups(
                base_payload,
                selected_groups,
                canonical_add_sort=policy_payload.get(
                    "canonical_add_sort_frozen", False
                ),
            )
            trial_record, exact_trial_errors = _build_and_validate_trial_candidate(
                base_record,
                trial_payload,
                reference_records=snapshot["b01"]["candidate_reference_records"],
            )
            trial_payload = trial_record["payload"]
            trial_errors = sorted(set([*trial_errors, *exact_trial_errors]))
            unknown_for_unit = [
                token
                for token in unknown_tokens
                if not token["bounded_atomic_group_ids"]
                or set(token["bounded_atomic_group_ids"])
                & {group["atomic_group_id"] for group in selected_groups}
            ]
            check_results = [
                _check_result(
                    "B05_CHECK_BASE_CURRENT",
                    "PASS" if base_is_current else "FAIL",
                    unit["atomic_group_bindings"],
                    [snapshot["b01"]["live_pointer_binding_hash"]],
                ),
                _check_result(
                    "B05_CHECK_DEPENDENCY_BOUNDARY",
                    "UNKNOWN" if unknown_for_unit else "PASS",
                    unit["atomic_group_bindings"],
                    [token["token_id"] for token in unknown_for_unit],
                ),
                _check_result(
                    "B05_CHECK_EFFECTIVE_PROTECTION_COMPLETE",
                    "PASS" if global_protection_valid else "FAIL",
                    unit["atomic_group_bindings"],
                    [sha256_value(protected_entries)],
                ),
            ]
            structure_status = "FAIL" if trial_errors else "PASS"
            structure_checks = [
                _check_result(
                    "B05_CHECK_CANDIDATE_STRUCTURE",
                    structure_status,
                    unit["atomic_group_bindings"],
                    [sha256_value(trial_payload)],
                )
            ]
            proof = {
                "route_unit_id": route_unit_id,
                "atomic_group_bindings": deepcopy(unit["atomic_group_bindings"]),
                "logical_read_set": reads,
                "logical_write_set": writes,
                "lineage_set": lineages,
                "support_refs": supports,
                "validation_context_refs": stable_sorted(
                    [
                        record_ref(protection),
                        snapshot["policy"]["validation_policy_ref"],
                    ]
                ),
                "effective_protection_proof": protected_entries,
                "canonical_apply_result_hash": sha256_value(trial_payload),
                "exchange_order_checks": stable_sorted(exchange_by_unit[route_unit_id]),
                "candidate_structure_check_results": structure_checks,
                "check_results": check_results,
                "unit_proof_hash": "",
            }
            proof["unit_proof_hash"] = sha256_value(
                {key: value for key, value in proof.items() if key != "unit_proof_hash"}
            )
            proofs.append(proof)
            reject_reasons = []
            if not global_protection_valid:
                reject_reasons.append("PROTECTION_REGRESSION")
            if not base_is_current:
                reject_reasons.append("BASE_NOT_CURRENT")
            for support in supports:
                if diagnostic_states.get(canonical_bytes(support)) in {
                    "SUPERSEDED_BY_PATCH_REVIEW",
                    "CLOSED",
                }:
                    reject_reasons.append("SELECTED_DIAGNOSTIC_TERMINAL")
            reject_reasons.extend(
                error
                for error in trial_errors
                if error
                in {
                    "EXPECTED_OLD_ITEM_HASH_MISMATCH",
                    "CANDIDATE_STRUCTURE_INVALID",
                    "FORBIDDEN_B05_RESPONSIBILITY_REQUESTED",
                }
            )
            replace_targets = [
                _find_lineage(operation.get("target"))
                for group in selected_groups
                for operation in group["operations"]
                if operation.get("operation_kind") == "REPLACE_CANDIDATE_ITEM"
            ]
            if len(replace_targets) != len(set(replace_targets)):
                reject_reasons.append("ROUTE_UNIT_TARGET_CONFLICT")
            expand_reasons = sorted(
                {
                    token["reason_code"]
                    if token["reason_code"]
                    in {
                        "DEPENDENCY_ENDPOINT_UNKNOWN",
                        "SEMANTIC_IMPACT_UNKNOWN",
                        "EVIDENCE_SUPPORT_AMBIGUOUS",
                        "ADJACENT_SEGMENT_CHECK_REQUIRED",
                    }
                    else "DEPENDENCY_ENDPOINT_UNKNOWN"
                    for token in unknown_for_unit
                }
            )
            group_ids = {group["atomic_group_id"] for group in selected_groups}
            if group_ids & set(policy_payload.get("semantic_unknown_group_ids", [])):
                expand_reasons.append("SEMANTIC_IMPACT_UNKNOWN")
            if group_ids & set(policy_payload.get("adjacent_check_group_ids", [])):
                expand_reasons.append("ADJACENT_SEGMENT_CHECK_REQUIRED")
            applicable_closed_gates = []
            unit_binding_keys = {
                canonical_bytes(binding) for binding in unit["atomic_group_bindings"]
            }
            for gate in gates:
                targets = gate["applicable_atomic_group_bindings_or_route_unit_ids"]
                target_route_unit_ids = {
                    item for item in targets if isinstance(item, str)
                }
                target_group_binding_keys = {
                    canonical_bytes(item)
                    for item in targets
                    if isinstance(item, dict)
                }
                if gate["current_state"] == "CLOSED" and (
                    route_unit_id in target_route_unit_ids
                    or bool(unit_binding_keys & target_group_binding_keys)
                ):
                    applicable_closed_gates.append(
                        {
                            "gate_ref": gate["gate_ref"],
                            "gate_state_ref": gate["gate_state_ref"],
                        }
                    )
            if reject_reasons:
                route = "REJECT"
                reasons = sorted(set(reject_reasons))
                expand_target = None
                defer_refs = []
            elif expand_reasons:
                route = "EXPAND_CHECK"
                reasons = sorted(set(expand_reasons))
                expand_target = {
                    "return_module": "CCZ-142",
                    "patch_proposal_ref": record_ref(patch),
                    "route_unit_id": route_unit_id,
                    "atomic_group_bindings": deepcopy(unit["atomic_group_bindings"]),
                    "chapter_revision_ref": deepcopy(
                        patch_payload["chapter_revision_ref"]
                    ),
                    "segment_index_ref": record_ref(
                        snapshot["b01"]["segment_index_record"]
                    ),
                    "seg_targets": [snapshot["b01"]["live_pointer_binding"]["seg"]],
                    "diagnostic_refs": deepcopy(
                        patch_payload.get("diagnostic_refs", [])
                    ),
                    "coverage_observation_refs": deepcopy(
                        patch_payload.get("coverage_observation_refs", [])
                    ),
                    "authorized_source_slice_refs": deepcopy(
                        patch_payload.get("authorized_source_slice_refs", [])
                    ),
                    "causal_hint_proposal_refs": deepcopy(
                        patch_payload.get("sidecar_proposal_refs", [])
                    ),
                    "question_codes": reasons,
                }
                defer_refs = []
            elif applicable_closed_gates:
                route = "DEFER"
                reasons = ["DECLARED_NON_CONTENT_GATE_CLOSED"]
                expand_target = None
                defer_refs = stable_sorted(applicable_closed_gates)
            else:
                route = "ALLOW_FOR_B06"
                reasons = ["MECHANICAL_PROOF_COMPLETE"]
                expand_target = None
                defer_refs = []
            route_entries.append(
                {
                    "route_unit_id": route_unit_id,
                    "atomic_group_bindings": deepcopy(unit["atomic_group_bindings"]),
                    "unit_proof_hash": proof["unit_proof_hash"],
                    "route": route,
                    "reason_codes": reasons,
                    "expand_check_target_or_null": expand_target,
                    "defer_gate_refs": defer_refs,
                }
            )
        return stable_sorted(proofs), stable_sorted(route_entries)

    def _causal_mappings_and_routes(
        self,
        *,
        patch: dict[str, Any],
        causal_records: list[dict[str, Any]],
        partition: list[dict[str, Any]],
        route_entries: list[dict[str, Any]],
        snapshot: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        groups = patch["payload"]["atomic_groups"]
        group_sets = {
            group["atomic_group_id"]: _group_proof_inputs(group) for group in groups
        }
        group_to_unit = {
            binding["atomic_group_id"]: unit["route_unit_id"]
            for unit in partition
            for binding in unit["atomic_group_bindings"]
        }
        route_by_unit = {item["route_unit_id"]: item["route"] for item in route_entries}
        base_record = snapshot["b01"]["candidate_version_record"]
        mappings = []
        causal_routes = []
        for causal in causal_records:
            payload = causal["payload"]
            support_refs = stable_sorted(
                [
                    *deepcopy(payload.get("diagnostic_refs", [])),
                    *deepcopy(payload.get("coverage_observation_refs", [])),
                    *deepcopy(payload.get("authorized_source_slice_refs", [])),
                ]
            )
            ownership = []
            owner_groups: set[str] = set()
            complete = True
            for support_ref in support_refs:
                owners = [
                    group_id
                    for group_id, sets in group_sets.items()
                    if canonical_bytes(support_ref)
                    in {canonical_bytes(item) for item in sets["support_refs"]}
                ]
                if (
                    support_ref["record_type"] == "M3_AUTHORIZED_SOURCE_SLICE"
                    and not owners
                ):
                    replacements = [
                        group["atomic_group_id"]
                        for group in groups
                        if any(
                            operation.get("operation_kind") == "REPLACE_CANDIDATE_ITEM"
                            for operation in group["operations"]
                        )
                    ]
                    if len(replacements) == 1:
                        owners = replacements
                if not owners:
                    complete = False
                owner_groups.update(owners)
                ownership.append(
                    {
                        "support_ref": support_ref,
                        "owner_atomic_group_ids": stable_sorted(owners),
                    }
                )
            locators = [
                payload.get("from_lineage_locator"),
                payload.get("to_lineage_locator"),
                *payload.get("evidence_locators", []),
            ]
            locator_resolution = []
            affected_ownership = []
            for locator in locators:
                lineage = _find_lineage(locator)
                resolves_exact_base = _locator_resolves_exact_base(locator, base_record)
                affected = [
                    group_id
                    for group_id, sets in group_sets.items()
                    if resolves_exact_base
                    and lineage is not None
                    and lineage in sets["lineage_set"]
                ]
                if not resolves_exact_base:
                    complete = False
                owner_groups.update(affected)
                relation = (
                    "READ_OR_WRITTEN_BY_GROUP" if affected else "BASE_CONTEXT_ONLY"
                )
                resolution = {
                    "locator": deepcopy(locator),
                    "relation": relation,
                    "affected_atomic_group_ids": stable_sorted(affected),
                }
                locator_resolution.append(resolution)
                affected_ownership.append(
                    {
                        "locator_hash": sha256_value(locator),
                        "affected_atomic_group_ids": stable_sorted(affected),
                    }
                )
            supporting_groups = stable_sorted(list(owner_groups))
            supporting_units = stable_sorted(
                list({group_to_unit[group_id] for group_id in supporting_groups})
            )
            if not supporting_units:
                complete = False
            mapping = {
                "causal_hint_proposal_ref": record_ref(causal),
                "locator_resolution": stable_sorted(locator_resolution),
                "support_ref_ownership": stable_sorted(ownership),
                "affected_group_ownership": stable_sorted(affected_ownership),
                "supporting_atomic_group_ids": supporting_groups,
                "supporting_route_unit_ids": supporting_units,
                "mapping_status": "COMPLETE" if complete else "EXPAND_REQUIRED",
                "mapping_proof_hash": "",
            }
            mapping["mapping_proof_hash"] = sha256_value(
                {
                    key: value
                    for key, value in mapping.items()
                    if key != "mapping_proof_hash"
                }
            )
            mappings.append(mapping)
            if not complete:
                causal_route = "EXPAND_CHECK"
                reasons = ["CAUSAL_SUPPORT_MAPPING_AMBIGUOUS"]
                expand_target = {
                    "return_module": "CCZ-142",
                    "patch_proposal_ref": record_ref(patch),
                    "causal_hint_proposal_ref": record_ref(causal),
                    "chapter_revision_ref": deepcopy(
                        patch["payload"]["chapter_revision_ref"]
                    ),
                    "segment_index_ref": record_ref(
                        snapshot["b01"]["segment_index_record"]
                    ),
                    "seg_targets": [snapshot["b01"]["live_pointer_binding"]["seg"]],
                    "diagnostic_refs": deepcopy(
                        patch["payload"].get("diagnostic_refs", [])
                    ),
                    "coverage_observation_refs": deepcopy(
                        patch["payload"].get("coverage_observation_refs", [])
                    ),
                    "authorized_source_slice_refs": deepcopy(
                        patch["payload"].get("authorized_source_slice_refs", [])
                    ),
                    "question_codes": reasons,
                }
            else:
                support_routes = [
                    route_by_unit[unit_id] for unit_id in supporting_units
                ]
                if "REJECT" in support_routes:
                    causal_route = "REJECT"
                    reasons = ["SUPPORTING_ROUTE_UNIT_REJECTED"]
                elif "EXPAND_CHECK" in support_routes:
                    causal_route = "EXPAND_CHECK"
                    reasons = ["SUPPORTING_ROUTE_UNIT_EXPAND_CHECK"]
                elif "DEFER" in support_routes:
                    causal_route = "DEFER"
                    reasons = ["SUPPORTING_ROUTE_UNIT_DEFERRED"]
                else:
                    causal_route = "ROUTE_TO_B09"
                    reasons = ["ALL_SUPPORTING_ROUTE_UNITS_ALLOWED"]
                expand_target = None
            causal_routes.append(
                {
                    "causal_hint_proposal_ref": record_ref(causal),
                    "mapping_proof_hash": mapping["mapping_proof_hash"],
                    "supporting_route_unit_ids": supporting_units,
                    "route": causal_route,
                    "reason_codes": reasons,
                    "expand_check_target_or_null": expand_target,
                }
            )
        return stable_sorted(mappings), stable_sorted(causal_routes)

    def evaluate(
        self,
        *,
        patch_proposal: dict[str, Any],
        protection_set: dict[str, Any],
        causal_hint_proposals: list[dict[str, Any]],
        operation_id: str,
        created_at: str,
        prior_active_route_receipt_ref_or_null: dict[str, Any] | None = None,
        prior_lifecycle_head_ref_or_null: dict[str, Any] | None = None,
        material_delta_refs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(operation_id, str) or not operation_id:
            fail("B05_OPERATION_ID_INVALID")
        material_delta_refs = stable_sorted(material_delta_refs or [])
        for ref in material_delta_refs:
            validate_record_ref(ref)
        validate_output_inputs = [
            (patch_proposal, "M3_PATCH_PROPOSAL"),
            (protection_set, "M3_CANDIDATE_PROTECTION_SET"),
            *[
                (causal, "M3_CAUSAL_HINT_PROPOSAL")
                for causal in causal_hint_proposals
            ],
        ]
        for record, expected_type in validate_output_inputs:
            validate_immutable_record(record, expected_type=expected_type)
        first = self._read_authoritative(
            patch_proposal, protection_set, causal_hint_proposals
        )
        closure = first["b04"]
        patch = closure["patch_proposal"]
        protection = closure["protection_set"]
        causals = closure["causal_hint_proposals"]
        validator_identity = self.store.validator_identity(self.validator_identity_ref)
        self._validate_validator_identity(validator_identity)
        patch_payload = patch["payload"]
        candidate = first["b01"]["candidate_version_record"]
        if not _ref_equal(
            record_ref(candidate), patch_payload["base_candidate_version_ref"]
        ):
            fail("B05_B01_BASE_ORIGINAL_UNRESOLVABLE")
        if not _ref_equal(
            first["b02"]["base_candidate_version_ref"],
            patch_payload["base_candidate_version_ref"],
        ):
            fail("B05_B02_SCOPE_BASE_MISMATCH")
        request_has_route = prior_active_route_receipt_ref_or_null is not None
        request_has_head = prior_lifecycle_head_ref_or_null is not None
        if request_has_route != request_has_head:
            fail("B05_REOPEN_BINDING_INCOMPLETE")
        if request_has_route:
            validate_record_ref(
                prior_active_route_receipt_ref_or_null,
                expected_type="M3_PATCH_ROUTE_RECEIPT",
            )
            validate_record_ref(
                prior_lifecycle_head_ref_or_null,
                expected_type="M3_PATCH_LIFECYCLE_RECEIPT",
            )
            prior_state = _series_state_from_route(
                self.store, prior_active_route_receipt_ref_or_null
            )
            prior_route_record = self.store.record_by_ref(
                prior_active_route_receipt_ref_or_null
            )
            prior_head_record = self.store.record_by_ref(
                prior_lifecycle_head_ref_or_null
            )
            prior_binding_is_current = _ref_equal(
                prior_state["active_route_receipt_ref_or_null"],
                prior_active_route_receipt_ref_or_null,
            ) and _ref_equal(
                prior_state["lifecycle_head_ref_or_null"],
                prior_lifecycle_head_ref_or_null,
            )
            if not material_delta_refs:
                fail("B05_REOPEN_MATERIAL_DELTA_REQUIRED")
        else:
            prior_state = _prior_state_snapshot(self.store, record_ref(patch))
            prior_binding_is_current = True
            prior_route_record = None
            prior_head_record = None
            if material_delta_refs:
                fail("B05_INITIAL_MATERIAL_DELTA_FORBIDDEN")
        policy_record = first["policy"]["validation_policy_record"]
        policy_payload = deepcopy(policy_record["payload"])
        groups = patch_payload["atomic_groups"]
        group_catalog = [
            {
                "atomic_group_id": group["atomic_group_id"],
                "group_payload_hash": group["group_payload_hash"],
                "operation_count": len(group["operations"]),
                "operation_fingerprints": [
                    _operation_fingerprint(operation)
                    for operation in group["operations"]
                ],
            }
            for group in groups
        ]
        group_catalog = stable_sorted(group_catalog)
        edges = _known_edges(groups, policy_payload)
        unknown_tokens = _unknown_tokens(groups, policy_payload)
        partition = _partition_groups(record_ref(patch), groups, edges, unknown_tokens)
        if len(
            [binding for unit in partition for binding in unit["atomic_group_bindings"]]
        ) != len(groups):
            fail("B05_ROUTE_UNIT_PARTITION_INCOMPLETE")
        dependency_proof = {
            "group_catalog": group_catalog,
            "dependency_edges": edges,
            "unknown_dependency_tokens": unknown_tokens,
            "route_unit_partition": partition,
            "partition_hash": sha256_value(
                {
                    "group_catalog": group_catalog,
                    "dependency_edges": edges,
                    "unknown_dependency_tokens": unknown_tokens,
                    "route_unit_partition": partition,
                }
            ),
        }
        unit_proofs, route_entries = self._build_unit_proofs_and_routes(
            patch=patch,
            protection=protection,
            snapshot=first,
            partition=partition,
            unknown_tokens=unknown_tokens,
            policy_payload=policy_payload,
        )
        causal_mappings, causal_routes = self._causal_mappings_and_routes(
            patch=patch,
            causal_records=causals,
            partition=partition,
            route_entries=route_entries,
            snapshot=first,
        )
        b01 = first["b01"]
        b02 = first["b02"]
        policy = first["policy"]
        pointer_record = b01["candidate_pointer_snapshot_record_or_null"]
        b02_binding = {
            "reader_identity": b02["reader_identity"],
            "reader_version": b02["reader_version"],
            "base_candidate_version_ref": deepcopy(b02["base_candidate_version_ref"]),
            "diagnostic_state_bindings": deepcopy(b02["diagnostic_state_bindings"]),
            "coverage_observation_refs": deepcopy(b02["coverage_observation_refs"]),
            "scope_snapshot_hash": b02["scope_snapshot_hash"],
        }
        input_binding = {
            "patch_proposal_ref": record_ref(patch),
            "protection_set_ref": record_ref(protection),
            "causal_hint_proposal_refs": [record_ref(item) for item in causals],
            "base_candidate_version_ref": record_ref(candidate),
            "base_version_payload_hash": sha256_value(candidate["payload"]),
            "candidate_schema_id": patch_payload["candidate_schema_id"],
            "chapter_revision_ref": deepcopy(patch_payload["chapter_revision_ref"]),
            "seg": deepcopy(b01["live_pointer_binding"]["seg"]),
            "segment_index_ref": record_ref(b01["segment_index_record"]),
            "candidate_pointer_snapshot_ref_or_null": None
            if pointer_record is None
            else record_ref(pointer_record),
            "live_pointer_binding": deepcopy(b01["live_pointer_binding"]),
            "live_pointer_binding_hash": b01["live_pointer_binding_hash"],
            "b02_scope_binding": b02_binding,
            "b02_scope_snapshot_hash": b02["scope_snapshot_hash"],
            "non_content_gate_bindings": deepcopy(policy["non_content_gate_bindings"]),
            "non_content_gate_snapshot_hash": policy["non_content_gate_snapshot_hash"],
            "prior_active_route_receipt_ref_or_null": deepcopy(
                prior_active_route_receipt_ref_or_null
            ),
            "prior_lifecycle_head_ref_or_null": deepcopy(
                prior_lifecycle_head_ref_or_null
            ),
        }
        if request_has_route:
            prior_pvr = self.store.record_by_ref(
                prior_route_record["payload"]["validation_receipt_ref"]
            )

            def material_candidates(
                pvr_payload: dict[str, Any],
            ) -> list[dict[str, Any]]:
                binding = pvr_payload["input_binding"]
                return [
                    binding["patch_proposal_ref"],
                    pvr_payload["validator_identity_ref"],
                    pvr_payload["active_policy_selection_ref"],
                    *[
                        lifecycle_ref
                        for state in binding["b02_scope_binding"][
                            "diagnostic_state_bindings"
                        ]
                        for lifecycle_ref in state["lifecycle_receipt_refs"]
                    ],
                    *binding["b02_scope_binding"]["coverage_observation_refs"],
                    *[
                        gate["gate_state_ref"]
                        for gate in binding["non_content_gate_bindings"]
                    ],
                ]

            current_pvr_preview = {
                "input_binding": input_binding,
                "validator_identity_ref": self.validator_identity_ref,
                "active_policy_selection_ref": policy["active_policy_selection_ref"],
            }
            current_candidates = {
                canonical_bytes(ref): ref
                for ref in material_candidates(current_pvr_preview)
            }
            prior_candidates = {
                canonical_bytes(ref)
                for ref in material_candidates(prior_pvr["payload"])
            }
            genuine_new_refs = set(current_candidates) - prior_candidates
            provided = {canonical_bytes(ref) for ref in material_delta_refs}
            if not provided or not provided <= genuine_new_refs:
                fail("B05_REOPEN_MATERIAL_DELTA_NOT_AUTHORITATIVE")
        evaluation_preimage = {
            "patch_proposal": patch,
            "protection_set": protection,
            "causal_hint_proposals": causals,
            "base_candidate_version": candidate,
            "segment_index": b01["segment_index_record"],
            "candidate_pointer_snapshot_or_null": pointer_record,
            "live_pointer_binding": b01["live_pointer_binding"],
            "b02_scope_binding": b02_binding,
            "validator_identity_ref": self.validator_identity_ref,
            "validation_policy_ref": policy["validation_policy_ref"],
            "active_policy_selection_ref": policy["active_policy_selection_ref"],
            "active_policy_selection_hash": policy["active_policy_selection_hash"],
            "non_content_gate_bindings": policy["non_content_gate_bindings"],
            "non_content_gate_snapshot_hash": policy["non_content_gate_snapshot_hash"],
            "prior_active_route_receipt_ref_or_null": prior_active_route_receipt_ref_or_null,
            "prior_lifecycle_head_ref_or_null": prior_lifecycle_head_ref_or_null,
        }
        evaluation_input_hash = sha256_value(evaluation_preimage)
        evaluation_key = f"b05-evaluation:{evaluation_input_hash}"
        project_scope_id = b01["live_pointer_binding"]["project_scope_id"]
        prior_operation = self.store.pvr_for_operation(operation_id, project_scope_id)
        if (
            prior_operation is not None
            and prior_operation["payload"]["evaluation_input_hash"]
            != evaluation_input_hash
        ):
            fail("B05_OPERATION_ID_INPUT_CONFLICT")
        existing_input = self.store.route_bundle_for_input(evaluation_input_hash)
        if (
            request_has_route
            and not prior_binding_is_current
            and existing_input is None
        ):
            fail("B05_REOPEN_BINDING_NOT_CURRENT")
        if (
            prior_state["series_count"]
            and not request_has_route
            and existing_input is None
        ):
            fail("B05_EXISTING_SERIES_REQUIRES_EXACT_REOPEN_BINDING")
        if request_has_route:
            route_series_id = prior_route_record["payload"]["route_series_id"]
            route_generation = prior_route_record["payload"]["route_generation"] + 1
            lifecycle_start = prior_head_record["payload"]["lifecycle_sequence"]
        else:
            route_series_id = f"route-series:{sha256_value({'initial_patch_proposal_ref': record_ref(patch)})}"
            route_generation = 1
            lifecycle_start = 0
        counters = {key: 0 for key in RUNTIME_COUNTER_KEYS}
        pvr_payload = {
            "evaluation_key": evaluation_key,
            "operation_id": operation_id,
            "evaluation_input_hash": evaluation_input_hash,
            "validator_identity_ref": deepcopy(self.validator_identity_ref),
            "validation_policy_ref": deepcopy(policy["validation_policy_ref"]),
            "active_policy_selection_ref": deepcopy(
                policy["active_policy_selection_ref"]
            ),
            "active_policy_selection_hash": policy["active_policy_selection_hash"],
            "input_binding": input_binding,
            "dependency_proof": dependency_proof,
            "route_unit_proofs": unit_proofs,
            "causal_support_mappings": causal_mappings,
            "runtime_counters": counters,
        }
        pvr = PatchValidator.build(payload=pvr_payload, created_at=created_at)
        binding_header = {
            "patch_proposal_ref": record_ref(patch),
            "protection_set_ref": record_ref(protection),
            "base_candidate_version_ref": record_ref(candidate),
            "candidate_schema_id": patch_payload["candidate_schema_id"],
            "chapter_revision_ref": deepcopy(patch_payload["chapter_revision_ref"]),
            "seg": deepcopy(b01["live_pointer_binding"]["seg"]),
            "segment_index_ref": record_ref(b01["segment_index_record"]),
            "live_pointer_binding_hash": b01["live_pointer_binding_hash"],
            "b02_scope_snapshot_hash": b02["scope_snapshot_hash"],
            "non_content_gate_snapshot_hash": policy["non_content_gate_snapshot_hash"],
        }
        route_payload = {
            "evaluation_key": evaluation_key,
            "evaluation_input_hash": evaluation_input_hash,
            "route_series_id": route_series_id,
            "route_generation": route_generation,
            "validator_identity_ref": deepcopy(self.validator_identity_ref),
            "validation_policy_ref": deepcopy(policy["validation_policy_ref"]),
            "active_policy_selection_ref": deepcopy(
                policy["active_policy_selection_ref"]
            ),
            "active_policy_selection_hash": policy["active_policy_selection_hash"],
            "validation_receipt_ref": record_ref(pvr),
            "binding_header": binding_header,
            "binding_header_hash": sha256_value(binding_header),
            "route_units": route_entries,
            "causal_hint_routes": causal_routes,
        }
        route = PatchRouteDecider.build(payload=route_payload, created_at=created_at)
        if request_has_route:
            lifecycles = [
                PatchLifecycleBuilder.build(
                    payload={
                        "route_series_id": route_series_id,
                        "lifecycle_sequence": lifecycle_start + 1,
                        "subject_route_receipt_ref": deepcopy(
                            prior_active_route_receipt_ref_or_null
                        ),
                        "event": "SUPERSEDED",
                        "effective_at": created_at,
                        "reason_code": "SUPERSEDED_BY_NEW_ROUTE_RECEIPT",
                        "prior_route_receipt_ref_or_null": None,
                        "replacement_route_receipt_ref_or_null": record_ref(route),
                        "material_delta_refs": [],
                        "evaluation_key": evaluation_key,
                    },
                    created_at=created_at,
                ),
                PatchLifecycleBuilder.build(
                    payload={
                        "route_series_id": route_series_id,
                        "lifecycle_sequence": lifecycle_start + 2,
                        "subject_route_receipt_ref": record_ref(route),
                        "event": "REOPENED_WITH_NEW_MATERIAL",
                        "effective_at": created_at,
                        "reason_code": "REEVALUATED_WITH_MATERIAL_DELTA",
                        "prior_route_receipt_ref_or_null": deepcopy(
                            prior_active_route_receipt_ref_or_null
                        ),
                        "replacement_route_receipt_ref_or_null": None,
                        "material_delta_refs": material_delta_refs,
                        "evaluation_key": evaluation_key,
                    },
                    created_at=created_at,
                ),
            ]
        else:
            lifecycles = [
                PatchLifecycleBuilder.build(
                    payload={
                        "route_series_id": route_series_id,
                        "lifecycle_sequence": 1,
                        "subject_route_receipt_ref": record_ref(route),
                        "event": "ROUTES_FROZEN",
                        "effective_at": created_at,
                        "reason_code": "INITIAL_ROUTE_BUNDLE_COMMITTED",
                        "prior_route_receipt_ref_or_null": None,
                        "replacement_route_receipt_ref_or_null": None,
                        "material_delta_refs": [],
                        "evaluation_key": evaluation_key,
                    },
                    created_at=created_at,
                )
            ]
        candidate_bundle = [pvr, route, *lifecycles]
        deterministic_hash = _bundle_deterministic_hash(candidate_bundle)
        first_authoritative_hash = self._authoritative_hash(first)
        first_prior_hash = sha256_value(prior_state)

        def reread_authoritative() -> str:
            return self._authoritative_hash(
                self._read_authoritative(patch, protection, causals)
            )

        def reread_prior() -> str:
            if request_has_route:
                return sha256_value(
                    _series_state_from_route(
                        self.store, prior_active_route_receipt_ref_or_null
                    )
                )
            return sha256_value(_prior_state_snapshot(self.store, record_ref(patch)))

        published, reused = B05RouteBundlePublisher.publish(
            self.store,
            records=candidate_bundle,
            operation_id=operation_id,
            project_scope_id=project_scope_id,
            evaluation_input_hash=evaluation_input_hash,
            expected_authoritative_hash=first_authoritative_hash,
            authoritative_reread=reread_authoritative,
            expected_prior_state_hash=first_prior_hash,
            prior_state_reread=reread_prior,
            deterministic_result_hash=deterministic_hash,
        )
        published_pvr = next(
            item
            for item in published
            if item["record_type"] == "M3_PATCH_VALIDATION_RECEIPT"
        )
        published_route = next(
            item
            for item in published
            if item["record_type"] == "M3_PATCH_ROUTE_RECEIPT"
        )
        published_lifecycles = [
            item
            for item in published
            if item["record_type"] == "M3_PATCH_LIFECYCLE_RECEIPT"
        ]
        return {
            "validation_receipt_ref": record_ref(published_pvr),
            "route_receipt_ref": record_ref(published_route),
            "lifecycle_receipt_refs": stable_sorted(
                [record_ref(item) for item in published_lifecycles]
            ),
            "route_units": deepcopy(published_route["payload"]["route_units"]),
            "causal_hint_routes": deepcopy(
                published_route["payload"]["causal_hint_routes"]
            ),
            "evaluation_input_hash": evaluation_input_hash,
            "reused_existing_bundle": reused,
        }
