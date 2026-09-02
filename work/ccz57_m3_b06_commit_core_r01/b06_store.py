"""SQLite-backed B-06 commit core for synthetic exact-head fixtures."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import threading
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
B05_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b05_patch_route_r03_5"
for candidate in (REPOSITORY_ROOT, B05_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from work.ccz57_m3_b01_candidate_version_r03_5.b01_contract import (  # noqa: E402
    B01ContractError,
    FIXTURE_AUTHORITY_PROFILE,
    CandidateAuthorityProfile,
    require_authority_profile,
    validate_candidate_version,
)
from b05_contracts import (  # noqa: E402
    B05ContractError,
    canonical_bytes,
    record_ref,
    sha256_value,
    validate_immutable_record,
)
from b05_store import B05RouteStore  # noqa: E402
from candidate_mutation_kernel import (  # noqa: E402
    apply_groups,
    build_child_payload,
)
from patch_route_projection import B06AdmissionGuard  # noqa: E402

from b06_contracts import (  # noqa: E402
    build_merge_receipt,
    fail,
    validate_merge_receipt,
    validate_mutable_pointer,
)

FRESHNESS_KEYS = {
    "b02_scope_snapshot_hash",
    "active_policy_selection_hash",
    "non_content_gate_snapshot_hash",
}
RUN_FENCE_KEYS = {
    "project_scope_id",
    "run_id",
    "expected_run_epoch",
    "expected_state_revision",
}
_B06_COMMIT_PUBLISH_TOKEN = object()
_CANDIDATE_AUTHORITY_STORE_TOKEN = object()


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _record_bytes(record: dict[str, Any]) -> bytes:
    return canonical_bytes(record)


def _record_ref_hash(record: dict[str, Any]) -> str:
    return sha256_value(record_ref(record))


class B06TransactionReadView:
    """Expose SELECT-only access to the connection owning the B-06 transaction."""

    __slots__ = ("__connection",)

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.__connection = connection

    def _execute(self, query: str, parameters: tuple[Any, ...]) -> sqlite3.Cursor:
        if (
            not isinstance(query, str)
            or re.match(r"\A\s*SELECT\b", query, re.I) is None
        ):
            fail("B06_RUN_FENCE_QUERY_NOT_READ_ONLY")
        return self.__connection.execute(query, parameters)

    def fetchone(
        self, query: str, parameters: tuple[Any, ...] = ()
    ) -> tuple[Any, ...] | None:
        return self._execute(query, parameters).fetchone()

    def fetchall(
        self, query: str, parameters: tuple[Any, ...] = ()
    ) -> list[tuple[Any, ...]]:
        return self._execute(query, parameters).fetchall()


RunFenceReader = Callable[[B06TransactionReadView, dict[str, Any]], None]


def _validate_run_fence(
    run_fence: dict[str, Any], *, project_scope_id: str
) -> dict[str, Any]:
    if not isinstance(run_fence, dict) or set(run_fence) != RUN_FENCE_KEYS:
        fail("B06_RUN_FENCE_SHAPE_INVALID")
    if (
        run_fence["project_scope_id"] != project_scope_id
        or not isinstance(run_fence["run_id"], str)
        or not run_fence["run_id"]
        or any(
            isinstance(run_fence[key], bool)
            or not isinstance(run_fence[key], int)
            or run_fence[key] < 0
            for key in ("expected_run_epoch", "expected_state_revision")
        )
    ):
        fail("B06_RUN_FENCE_SHAPE_INVALID")
    return deepcopy(run_fence)


class B06CommitStore:
    """Own one mutable pointer and atomically publish child plus receipt."""

    __slots__ = (
        "root",
        "failure_point",
        "events",
        "physical_write_attempts",
        "_database_path",
        "_lock_path",
        "_authority_profile",
        "_thread_lock",
    )

    def __init__(
        self,
        root: Path,
        *,
        failure_point: str | None = None,
        authority_profile: CandidateAuthorityProfile = FIXTURE_AUTHORITY_PROFILE,
        _candidate_authority_store_token: object | None = None,
    ) -> None:
        profile = require_authority_profile(authority_profile)
        if (
            profile != FIXTURE_AUTHORITY_PROFILE
            and _candidate_authority_store_token is not _CANDIDATE_AUTHORITY_STORE_TOKEN
        ):
            fail("B06_PRODUCT_PROFILE_REQUIRES_CANDIDATE_AUTHORITY_STORE")
        self.root = self._guard_storage_path(root)
        self.failure_point = failure_point
        self._authority_profile = profile
        self.events: list[dict[str, str]] = []
        self.physical_write_attempts: list[dict[str, str]] = []
        self._database_path = self.root / "b06-commit-core.sqlite3"
        self._lock_path = self.root / ".b06-commit.lock"
        self._thread_lock = threading.RLock()

    @property
    def authority_profile(self) -> CandidateAuthorityProfile:
        return self._authority_profile

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
            fail("B06_WRITE_SET_ESCAPE", str(path))
        return resolved

    def initialize(
        self,
        *,
        base_candidate: dict[str, Any],
        live_pointer: dict[str, Any],
        reference_records: list[dict[str, Any]],
    ) -> None:
        try:
            validate_candidate_version(
                base_candidate,
                allow_child=base_candidate["payload"]["parent_candidate_version_ref"]
                is not None,
                reference_records=reference_records,
                authority_profile=self._authority_profile,
            )
        except (B01ContractError, KeyError) as error:
            fail("B06_BOOTSTRAP_CANDIDATE_INVALID", str(error))
        validate_mutable_pointer(
            live_pointer,
            candidate=base_candidate,
            reference_records=reference_records,
            authority_profile=self._authority_profile,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("PRAGMA journal_mode=TRUNCATE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS candidate_versions "
                "(ref_hash TEXT PRIMARY KEY, record_json BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS current_pointers "
                "(logical_pointer_key TEXT PRIMARY KEY, project_scope_id TEXT NOT NULL, "
                "pointer_json BLOB NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS merge_receipts "
                "(project_scope_id TEXT NOT NULL, operation_id TEXT NOT NULL, "
                "request_hash TEXT NOT NULL UNIQUE, receipt_json BLOB NOT NULL, "
                "PRIMARY KEY(project_scope_id, operation_id))"
            )
            initialized = connection.execute(
                "SELECT value FROM metadata WHERE key = 'initialized'"
            ).fetchone()
            if initialized is None:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO candidate_versions(ref_hash, record_json) VALUES (?, ?)",
                    (
                        _record_ref_hash(base_candidate),
                        sqlite3.Binary(_record_bytes(base_candidate)),
                    ),
                )
                connection.execute(
                    "INSERT INTO current_pointers(logical_pointer_key, project_scope_id, pointer_json) "
                    "VALUES (?, ?, ?)",
                    (
                        live_pointer["logical_pointer_key"],
                        live_pointer["project_scope_id"],
                        sqlite3.Binary(canonical_bytes(live_pointer)),
                    ),
                )
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES ('initialized', ?)",
                    (sqlite3.Binary(b"1"),),
                )
                connection.commit()

    @contextmanager
    def serialization(self) -> Iterator[None]:
        with self._thread_lock:
            if not self._lock_path.is_file():
                fail("B06_STORE_NOT_INITIALIZED")
            flags = os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self._lock_path, flags)
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    fail("B06_COMMIT_LOCK_INVALID")
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def _inject(self, point: str) -> None:
        if self.failure_point == point:
            fail("B06_SIMULATED_TRANSACTION_FAILURE", point)

    @staticmethod
    def _decode(raw: Any) -> dict[str, Any]:
        value = json.loads(bytes(raw).decode("utf-8"))
        if not isinstance(value, dict):
            fail("B06_STORED_VALUE_INVALID")
        return value

    def read_pointer(self, logical_pointer_key: str) -> dict[str, Any]:
        if not self._database_path.is_file():
            fail("B06_STORE_NOT_INITIALIZED")
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT pointer_json FROM current_pointers WHERE logical_pointer_key = ?",
                (logical_pointer_key,),
            ).fetchone()
        if row is None:
            fail("B06_POINTER_NOT_FOUND")
        return self._decode(row[0])

    def read_candidate(self, ref: dict[str, Any]) -> dict[str, Any]:
        if not self._database_path.is_file():
            fail("B06_STORE_NOT_INITIALIZED")
        ref_hash = sha256_value(ref)
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
                (ref_hash,),
            ).fetchone()
        if row is None:
            fail("B06_CANDIDATE_NOT_FOUND")
        record = self._decode(row[0])
        if canonical_bytes(record_ref(record)) != canonical_bytes(ref):
            fail("B06_CANDIDATE_REF_MISMATCH")
        return record

    def read_receipts(self) -> list[dict[str, Any]]:
        if not self._database_path.is_file():
            return []
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT receipt_json FROM merge_receipts "
                "ORDER BY project_scope_id, operation_id"
            ).fetchall()
        receipts = [self._decode(row[0]) for row in rows]
        for receipt in receipts:
            validate_merge_receipt(receipt)
        return receipts

    def visible_counts(self) -> dict[str, int]:
        if not self._database_path.is_file():
            return {"candidate_versions": 0, "current_pointers": 0, "merge_receipts": 0}
        with sqlite3.connect(self._database_path) as connection:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "candidate_versions",
                    "current_pointers",
                    "merge_receipts",
                )
            }

    def schema_objects(self) -> list[str]:
        with sqlite3.connect(self._database_path) as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            ]

    def write_attempt_count(self) -> int:
        return len(self.physical_write_attempts)

    def commit_atomic(
        self,
        *,
        project_scope_id: str,
        logical_pointer_key: str,
        operation_id: str,
        request_hash: str,
        run_fence_context: dict[str, Any] | None = None,
        run_fence_reader: RunFenceReader | None = None,
        publisher_token: object | None = None,
        builder: Callable[
            [dict[str, Any], dict[str, Any]],
            tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
        ],
    ) -> dict[str, Any]:
        if publisher_token is not _B06_COMMIT_PUBLISH_TOKEN:
            fail("B06_PUBLISHER_SCOPE_ESCAPE")
        with self.serialization():
            connection = sqlite3.connect(self._database_path)
            try:
                connection.execute("PRAGMA journal_mode=TRUNCATE")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT request_hash, receipt_json FROM merge_receipts "
                    "WHERE project_scope_id = ? AND operation_id = ?",
                    (project_scope_id, operation_id),
                ).fetchone()
                if prior is not None:
                    if prior[0] != request_hash:
                        fail("B06_OPERATION_ID_INPUT_CONFLICT")
                    receipt = self._decode(prior[1])
                    validate_merge_receipt(receipt)
                    connection.rollback()
                    pointer = self.read_pointer(logical_pointer_key)
                    return self._result(receipt, pointer=pointer, reused=True)
                if (run_fence_context is None) != (run_fence_reader is None):
                    fail("B06_RUN_FENCE_CONFIGURATION_INVALID")
                if run_fence_context is not None and run_fence_reader is not None:
                    connection.execute("PRAGMA query_only=ON")
                    try:
                        run_fence_reader(
                            B06TransactionReadView(connection),
                            deepcopy(run_fence_context),
                        )
                    finally:
                        connection.execute("PRAGMA query_only=OFF")
                pointer_row = connection.execute(
                    "SELECT project_scope_id, pointer_json FROM current_pointers "
                    "WHERE logical_pointer_key = ?",
                    (logical_pointer_key,),
                ).fetchone()
                if pointer_row is None or pointer_row[0] != project_scope_id:
                    fail("B06_POINTER_SCOPE_INVALID")
                pointer_before = self._decode(pointer_row[1])
                base_ref = pointer_before["current_candidate_version_ref"]
                base_row = connection.execute(
                    "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
                    (sha256_value(base_ref),),
                ).fetchone()
                if base_row is None:
                    fail("B06_BASE_CANDIDATE_MISSING")
                base_candidate = self._decode(base_row[0])
                if canonical_bytes(record_ref(base_candidate)) != canonical_bytes(
                    base_ref
                ):
                    fail("B06_BASE_CANDIDATE_REF_MISMATCH")
                child, pointer_after, receipt = builder(pointer_before, base_candidate)
                validate_merge_receipt(receipt)
                if receipt["payload"]["request_hash"] != request_hash:
                    fail("B06_RECEIPT_REQUEST_HASH_MISMATCH")
                child_ref_hash = _record_ref_hash(child)
                existing_child = connection.execute(
                    "SELECT record_json FROM candidate_versions WHERE ref_hash = ?",
                    (child_ref_hash,),
                ).fetchone()
                if existing_child is None:
                    connection.execute(
                        "INSERT INTO candidate_versions(ref_hash, record_json) VALUES (?, ?)",
                        (child_ref_hash, sqlite3.Binary(_record_bytes(child))),
                    )
                elif canonical_bytes(
                    self._decode(existing_child[0])
                ) != canonical_bytes(child):
                    fail("B06_CHILD_IDENTITY_COLLISION")
                self._inject("after_child_insert")
                cursor = connection.execute(
                    "UPDATE current_pointers SET pointer_json = ? "
                    "WHERE logical_pointer_key = ? AND project_scope_id = ? "
                    "AND pointer_json = ?",
                    (
                        sqlite3.Binary(canonical_bytes(pointer_after)),
                        logical_pointer_key,
                        project_scope_id,
                        sqlite3.Binary(canonical_bytes(pointer_before)),
                    ),
                )
                if cursor.rowcount != 1:
                    fail("B06_POINTER_CAS_CONFLICT")
                self._inject("after_pointer_cas")
                connection.execute(
                    "INSERT INTO merge_receipts(project_scope_id, operation_id, "
                    "request_hash, receipt_json) VALUES (?, ?, ?, ?)",
                    (
                        project_scope_id,
                        operation_id,
                        request_hash,
                        sqlite3.Binary(canonical_bytes(receipt)),
                    ),
                )
                self._inject("after_receipt_insert")
                self._inject("before_commit")
                connection.commit()
                transaction_id = receipt["record_id"]
                self.physical_write_attempts.append(
                    {"event": "sqlite_atomic_commit", "transaction_id": transaction_id}
                )
                self.events.append(
                    {
                        "event": "child_pointer_receipt_committed",
                        "transaction_id": transaction_id,
                    }
                )
                return self._result(receipt, pointer=pointer_after, reused=False)
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _result(
        receipt: dict[str, Any], *, pointer: dict[str, Any], reused: bool
    ) -> dict[str, Any]:
        payload = receipt["payload"]
        return {
            "merge_receipt_ref": record_ref(receipt),
            "child_candidate_version_ref": deepcopy(
                payload["child_candidate_version_ref"]
            ),
            "current_pointer": deepcopy(pointer),
            "request_hash": payload["request_hash"],
            "reused_existing_commit": reused,
        }


class B06CommitService:
    """Validate one allowed route unit and commit it without model or text access."""

    __slots__ = (
        "store",
        "b05_store",
        "freshness_reader",
        "run_fence_reader",
        "reference_records",
    )

    def __init__(
        self,
        *,
        store: B06CommitStore,
        b05_store: B05RouteStore,
        freshness_reader: Callable[[], dict[str, str]],
        run_fence_reader: RunFenceReader | None = None,
        reference_records: list[dict[str, Any]],
    ) -> None:
        self.store = store
        self.b05_store = b05_store
        self.freshness_reader = freshness_reader
        self.run_fence_reader = run_fence_reader
        self.reference_records = deepcopy(reference_records)

    def _freshness(self) -> dict[str, str]:
        try:
            value = self.freshness_reader()
        except Exception as error:
            fail("B06_AUTHORITY_READER_UNAVAILABLE", str(error))
        if (
            not isinstance(value, dict)
            or set(value) != FRESHNESS_KEYS
            or any(not _sha(item) for item in value.values())
        ):
            fail("B06_AUTHORITY_SNAPSHOT_INVALID")
        return deepcopy(value)

    @staticmethod
    def _record_by_ref(
        records: list[dict[str, Any]], ref: dict[str, Any], record_type: str
    ) -> dict[str, Any]:
        matches = [
            item
            for item in records
            if item.get("record_type") == record_type
            and canonical_bytes(record_ref(item)) == canonical_bytes(ref)
        ]
        if len(matches) != 1:
            fail("B06_B05_RECORD_UNRESOLVABLE", record_type)
        return matches[0]

    @staticmethod
    def _groups_for_entry(
        patch: dict[str, Any], route_entry: dict[str, Any]
    ) -> list[dict[str, Any]]:
        bindings = route_entry["atomic_group_bindings"]
        by_binding = {
            canonical_bytes(
                {
                    "atomic_group_id": group["atomic_group_id"],
                    "group_payload_hash": group["group_payload_hash"],
                }
            ): group
            for group in patch["payload"]["atomic_groups"]
        }
        groups = [by_binding.get(canonical_bytes(binding)) for binding in bindings]
        if any(group is None for group in groups):
            fail("B06_PATCH_GROUP_BINDING_MISMATCH")
        return [deepcopy(group) for group in groups if group is not None]

    def commit(
        self,
        *,
        project_scope_id: str,
        logical_pointer_key: str,
        operation_id: str,
        route_receipt_ref: dict[str, Any],
        route_unit_id: str,
        patch_proposal: dict[str, Any],
        protection_set: dict[str, Any],
        committed_at: str,
        run_fence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if any(
            not isinstance(item, str) or not item
            for item in (
                project_scope_id,
                logical_pointer_key,
                operation_id,
                route_unit_id,
                committed_at,
            )
        ):
            fail("B06_REQUEST_SHAPE_INVALID")
        try:
            validate_immutable_record(patch_proposal, expected_type="M3_PATCH_PROPOSAL")
            validate_immutable_record(
                protection_set, expected_type="M3_CANDIDATE_PROTECTION_SET"
            )
        except B05ContractError as error:
            fail("B06_PATCH_CLOSURE_INVALID", str(error))
        if (run_fence is None) != (self.run_fence_reader is None):
            fail("B06_RUN_FENCE_CONFIGURATION_INVALID")
        validated_run_fence = (
            None
            if run_fence is None
            else _validate_run_fence(run_fence, project_scope_id=project_scope_id)
        )
        request_preimage = {
            "project_scope_id": project_scope_id,
            "logical_pointer_key": logical_pointer_key,
            "operation_id": operation_id,
            "route_receipt_ref": route_receipt_ref,
            "route_unit_id": route_unit_id,
            "patch_proposal_ref": record_ref(patch_proposal),
            "protection_set_ref": record_ref(protection_set),
            "committed_at": committed_at,
        }
        if validated_run_fence is not None:
            request_preimage["run_fence"] = validated_run_fence
        request_hash = sha256_value(request_preimage)
        run_fence_context = (
            None
            if validated_run_fence is None
            else {
                "project_scope_id": project_scope_id,
                "operation_id": operation_id,
                "request_hash": request_hash,
                "run_fence": validated_run_fence,
            }
        )

        with self.b05_store.serialization():
            records = self.b05_store.read_records()

            def builder(
                pointer_before: dict[str, Any], base_candidate: dict[str, Any]
            ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
                validate_mutable_pointer(
                    pointer_before,
                    candidate=base_candidate,
                    reference_records=self.reference_records,
                    authority_profile=self.store.authority_profile,
                )
                if (
                    pointer_before["project_scope_id"] != project_scope_id
                    or pointer_before["logical_pointer_key"] != logical_pointer_key
                ):
                    fail("B06_POINTER_SCOPE_INVALID")
                route = self._record_by_ref(
                    records, route_receipt_ref, "M3_PATCH_ROUTE_RECEIPT"
                )
                pvr = self._record_by_ref(
                    records,
                    route["payload"]["validation_receipt_ref"],
                    "M3_PATCH_VALIDATION_RECEIPT",
                )
                binding = route["payload"]["binding_header"]
                if (
                    canonical_bytes(binding["patch_proposal_ref"])
                    != canonical_bytes(record_ref(patch_proposal))
                    or canonical_bytes(binding["protection_set_ref"])
                    != canonical_bytes(record_ref(protection_set))
                    or canonical_bytes(binding["base_candidate_version_ref"])
                    != canonical_bytes(record_ref(base_candidate))
                ):
                    fail("B06_ROUTE_INPUT_BINDING_MISMATCH")
                freshness_before = self._freshness()
                route_entry = B06AdmissionGuard.require_allow(
                    records,
                    route_receipt_ref=route_receipt_ref,
                    route_unit_id=route_unit_id,
                    base_candidate_version_record=base_candidate,
                    live_pointer_binding_hash=sha256_value(pointer_before),
                    **freshness_before,
                )
                groups = self._groups_for_entry(patch_proposal, route_entry)
                proofs = [
                    item
                    for item in pvr["payload"]["route_unit_proofs"]
                    if item["route_unit_id"] == route_unit_id
                ]
                if len(proofs) != 1:
                    fail("B06_UNIT_PROOF_MISSING")
                expected_apply_hash = proofs[0]["canonical_apply_result_hash"]
                payload_candidates: dict[bytes, dict[str, Any]] = {}
                for canonical_add_sort in (False, True):
                    mutated_payload, errors = apply_groups(
                        base_candidate["payload"],
                        groups,
                        canonical_add_sort=canonical_add_sort,
                    )
                    if errors:
                        continue
                    child_payload = build_child_payload(base_candidate, mutated_payload)
                    if sha256_value(child_payload) == expected_apply_hash:
                        payload_candidates[canonical_bytes(child_payload)] = (
                            child_payload
                        )
                if len(payload_candidates) != 1:
                    fail("B06_CANONICAL_APPLY_RESULT_MISMATCH")
                child_payload = next(iter(payload_candidates.values()))
                child = {
                    key: deepcopy(value)
                    for key, value in base_candidate.items()
                    if key != "record_hash"
                }
                child["record_id"] = (
                    f"{self.store.authority_profile.candidate_id_prefix}:"
                    f"{sha256_value(pointer_before['author_workspace_logical_key'])[:12]}:"
                    f"{child_payload['version_payload_hash'][:32]}"
                )
                child["record_version"] = base_candidate["record_version"] + 1
                child["created_at"] = committed_at
                child["payload"] = child_payload
                child["record_hash"] = sha256_value(child)
                try:
                    validate_candidate_version(
                        child,
                        allow_child=True,
                        reference_records=self.reference_records,
                        authority_profile=self.store.authority_profile,
                    )
                except B01ContractError as error:
                    fail("B06_CHILD_CANDIDATE_INVALID", str(error))
                pointer_after = deepcopy(pointer_before)
                pointer_after["generation"] += 1
                pointer_after["current_candidate_version_ref"] = record_ref(child)
                validate_mutable_pointer(
                    pointer_after,
                    candidate=child,
                    reference_records=self.reference_records,
                    authority_profile=self.store.authority_profile,
                )
                freshness_after = self._freshness()
                if canonical_bytes(freshness_after) != canonical_bytes(
                    freshness_before
                ):
                    fail("B06_AUTHORITY_SNAPSHOT_DRIFT")
                B06AdmissionGuard.require_allow(
                    records,
                    route_receipt_ref=route_receipt_ref,
                    route_unit_id=route_unit_id,
                    base_candidate_version_record=base_candidate,
                    live_pointer_binding_hash=sha256_value(pointer_before),
                    **freshness_after,
                )
                receipt_payload = {
                    "operation_id": operation_id,
                    "request_hash": request_hash,
                    "route_receipt_ref": deepcopy(route_receipt_ref),
                    "validation_receipt_ref": deepcopy(
                        route["payload"]["validation_receipt_ref"]
                    ),
                    "route_unit_id": route_unit_id,
                    "atomic_group_bindings": deepcopy(
                        route_entry["atomic_group_bindings"]
                    ),
                    "patch_proposal_ref": record_ref(patch_proposal),
                    "protection_set_ref": record_ref(protection_set),
                    "base_candidate_version_ref": record_ref(base_candidate),
                    "child_candidate_version_ref": record_ref(child),
                    "pointer_logical_key": logical_pointer_key,
                    "pointer_generation_before": pointer_before["generation"],
                    "pointer_generation_after": pointer_after["generation"],
                    "pointer_binding_hash_before": sha256_value(pointer_before),
                    "pointer_binding_hash_after": sha256_value(pointer_after),
                    "canonical_apply_result_hash": expected_apply_hash,
                    "committed_at": committed_at,
                }
                receipt = build_merge_receipt(
                    payload=receipt_payload, created_at=committed_at
                )
                return child, pointer_after, receipt

            try:
                return self.store.commit_atomic(
                    project_scope_id=project_scope_id,
                    logical_pointer_key=logical_pointer_key,
                    operation_id=operation_id,
                    request_hash=request_hash,
                    run_fence_context=run_fence_context,
                    run_fence_reader=self.run_fence_reader,
                    publisher_token=_B06_COMMIT_PUBLISH_TOKEN,
                    builder=builder,
                )
            except B05ContractError as error:
                fail("B06_B05_ADMISSION_FAILED", str(error))
