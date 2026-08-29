"""Atomic fixture store and the three B-04 unique record writers."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import sys
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterator

from b04_contracts import (
    CANDIDATE_SCHEMA_ID,
    FIXTURE_ACCESS,
    _WRITER_TOKENS,
    build_record,
    canonical_bytes,
    expected_protected_entries,
    fail,
    record_ref,
    reference_cycle_count,
    sha256_value,
    validate_atomic_groups,
    validate_causal_record,
    validate_output_record,
    validate_patch_record,
    validate_protection_record,
    validate_source_slice_records,
    validate_upstream_inputs,
)
from patch_preview_projection import PatchPreviewProjector

from work.ccz57_m3_b02_diagnostic_coverage_r03_5 import (  # noqa: E402
    b02_contracts as _b02_contracts_module,
)

sys.modules.setdefault("b02_contracts", _b02_contracts_module)

from work.ccz57_m3_b02_diagnostic_coverage_r03_5.b02_store import (  # noqa: E402
    FixtureStore as B02FixtureStore,
)
from work.ccz57_m3_b03_bound_evidence_read_r03_5 import (  # noqa: E402
    b03_contracts as _b03_contracts_module,
)

sys.modules.setdefault("b03_contracts", _b03_contracts_module)

_B03_MODULE_ROOT = (
    Path(__file__).resolve().parent.parent / "ccz57_m3_b03_bound_evidence_read_r03_5"
)
if str(_B03_MODULE_ROOT) not in sys.path:
    sys.path.append(str(_B03_MODULE_ROOT))

from work.ccz57_m3_b03_bound_evidence_read_r03_5.b03_contracts import (  # noqa: E402
    B03ContractError,
    record_ref as b03_record_ref,
)
from work.ccz57_m3_b03_bound_evidence_read_r03_5.service import (  # noqa: E402
    B03Service,
)

_TYPE_DIRECTORIES = {
    "M3_CANDIDATE_PROTECTION_SET": "M3_CANDIDATE_PROTECTION_SET",
    "M3_PATCH_PROPOSAL": "M3_PATCH_PROPOSAL",
    "M3_CAUSAL_HINT_PROPOSAL": "M3_CAUSAL_HINT_PROPOSAL",
}


def _identity(record: dict[str, Any]) -> tuple[str, str, int]:
    return record["record_type"], record["record_id"], record["record_version"]


def _identity_text(record: dict[str, Any]) -> str:
    return ":".join(str(value) for value in _identity(record))


class FixtureStore:
    """One-directory-per-transaction store with a single publish rename."""

    __slots__ = (
        "root",
        "transactions_root",
        "failure_point",
        "events",
        "before_publish_guard_hook",
        "_publish_lock_path",
    )

    @staticmethod
    def _resolve_allowed_storage_path(path: Path) -> Path:
        resolved = path.resolve(strict=False)
        module_root = Path(__file__).resolve().parent
        repository_root = module_root.parents[1]
        temporary_root = Path(tempfile.gettempdir()).resolve()
        inside_repository = (
            resolved == repository_root or repository_root in resolved.parents
        )
        inside_write_set = resolved == module_root or module_root in resolved.parents
        inside_temp = resolved == temporary_root or temporary_root in resolved.parents
        if (inside_repository and not inside_write_set) or (
            not inside_repository and not inside_temp
        ):
            fail("B04_WRITE_SET_ESCAPE", str(path))
        return resolved

    def __init__(self, root: Path, *, failure_point: str | None = None) -> None:
        resolved = self._resolve_allowed_storage_path(root)
        module_root = Path(__file__).resolve().parent
        temporary_root = Path(tempfile.gettempdir()).resolve()
        self.root = root
        self.transactions_root = root / "transactions"
        self.failure_point = failure_point
        self.events: list[dict[str, str]] = []
        self.before_publish_guard_hook: Callable[[], None] | None = None
        lock_path = (
            resolved / ".ccz57-b04-publish.lock"
            if resolved in {module_root, temporary_root}
            else resolved.parent / f".{resolved.name}.ccz57-b04-publish.lock"
        )
        self._publish_lock_path = self._resolve_allowed_storage_path(lock_path)

    def _inject(self, point: str) -> None:
        if self.failure_point == point:
            fail("B04_SIMULATED_TRANSACTION_FAILURE", point)

    @contextmanager
    def _publish_serialization(self) -> Iterator[None]:
        """Serialize identity resolution and publication across store instances."""

        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        lock_path = self._resolve_allowed_storage_path(self._publish_lock_path)
        try:
            descriptor = os.open(lock_path, flags, 0o600)
        except OSError as error:
            fail("B04_PUBLISH_LOCK_UNAVAILABLE", type(error).__name__)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                fail("B04_PUBLISH_LOCK_INVALID")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except OSError as error:
                fail("B04_PUBLISH_LOCK_UNAVAILABLE", type(error).__name__)
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _visible_paths(self) -> list[Path]:
        if not self.transactions_root.exists():
            return []
        return sorted(self.transactions_root.rglob("*.json"))

    def read_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: dict[tuple[str, str, int], bytes] = {}
        for path in self._visible_paths():
            raw = path.read_bytes()
            record = json.loads(raw.decode("utf-8"))
            validate_output_record(record)
            identity = _identity(record)
            previous = seen.get(identity)
            if previous is not None and previous != canonical_bytes(record):
                fail("B04_IMMUTABLE_IDENTITY_COLLISION", _identity_text(record))
            if previous is None:
                seen[identity] = canonical_bytes(record)
                records.append(record)
        return records

    def file_snapshot(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in self._visible_paths():
            raw = path.read_bytes()
            result.append(
                {
                    "path": path.relative_to(self.root).as_posix(),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        return result

    def object_snapshot(self) -> list[dict[str, Any]]:
        result = []
        for record in self.read_records():
            result.append(
                {
                    "storage_key": _identity_text(record),
                    "record_type": record["record_type"],
                    "record_id": record["record_id"],
                    "record_version": record["record_version"],
                    "record_hash": record["record_hash"],
                    "raw_sha256": hashlib.sha256(canonical_bytes(record)).hexdigest(),
                }
            )
        return sorted(result, key=lambda item: item["storage_key"].encode("utf-8"))

    def visible_snapshot(self) -> list[dict[str, str]]:
        """Include directories so a failed transaction cannot leave empty traces."""

        if not self.root.exists():
            return []
        result = [{"path": ".", "kind": "directory", "sha256": ""}]
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root).as_posix()
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

    @staticmethod
    def _clear_staging(staging: Path) -> None:
        if not staging.exists():
            return
        for path in sorted(staging.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        staging.rmdir()

    @staticmethod
    def _reuse_existing_original(
        candidate: dict[str, Any],
        existing: dict[tuple[str, str, int], dict[str, Any]],
    ) -> dict[str, Any]:
        """Reuse exact bytes when payload-addressed identity already exists."""

        validate_output_record(candidate)
        prior = existing.get(_identity(candidate))
        if prior is None:
            return deepcopy(candidate)
        stable_prior = {
            key: value
            for key, value in prior.items()
            if key not in {"created_at", "record_hash"}
        }
        stable_candidate = {
            key: value
            for key, value in candidate.items()
            if key not in {"created_at", "record_hash"}
        }
        if canonical_bytes(stable_prior) != canonical_bytes(stable_candidate):
            fail("B04_IMMUTABLE_IDENTITY_COLLISION", _identity_text(candidate))
        return deepcopy(prior)

    def _commit_bundle(
        self,
        records: list[dict[str, Any]],
        *,
        pre_publish_guard: Callable[[], None] | None = None,
        _serialized: bool = False,
    ) -> list[dict[str, Any]]:
        if not _serialized:
            with self._publish_serialization():
                return self._commit_bundle(
                    records,
                    pre_publish_guard=pre_publish_guard,
                    _serialized=True,
                )
        for record in records:
            validate_output_record(record)
        existing = {_identity(item): item for item in self.read_records()}
        missing: list[dict[str, Any]] = []
        for record in records:
            prior = existing.get(_identity(record))
            if prior is not None:
                if canonical_bytes(prior) != canonical_bytes(record):
                    fail("B04_IMMUTABLE_IDENTITY_COLLISION", _identity_text(record))
            else:
                missing.append(record)
        if not missing:
            if self.before_publish_guard_hook is not None:
                self.before_publish_guard_hook()
            if pre_publish_guard is not None:
                pre_publish_guard()
            return [deepcopy(existing[_identity(record)]) for record in records]

        transaction_id = sha256_value(
            sorted(
                [record_ref(record) for record in missing],
                key=lambda ref: canonical_bytes(ref),
            )
        )
        root_existed = self.root.exists()
        transactions_root_existed = self.transactions_root.exists()
        self.root.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".b04-staging-{transaction_id[:12]}-", dir=self.root
            )
        )
        destination = self.transactions_root / transaction_id
        try:
            for record in sorted(
                missing, key=lambda item: canonical_bytes(record_ref(item))
            ):
                directory = staging / _TYPE_DIRECTORIES[record["record_type"]]
                directory.mkdir(parents=True, exist_ok=True)
                name = hashlib.sha256(
                    _identity_text(record).encode("utf-8")
                ).hexdigest()
                path = directory / f"{name}.json"
                path.write_bytes(canonical_bytes(record) + b"\n")
                if record["record_type"] == "M3_CANDIDATE_PROTECTION_SET":
                    self._inject("after_protection_staging")
                elif record["record_type"] == "M3_CAUSAL_HINT_PROPOSAL":
                    self._inject("after_causal_staging")
                elif record["record_type"] == "M3_PATCH_PROPOSAL":
                    self._inject("after_patch_staging")
            self._inject("before_final_graph_check")
            combined = list(existing.values()) + missing
            if reference_cycle_count(combined) != 0:
                fail("B04_REFERENCE_CYCLE")
            for path in sorted(staging.rglob("*.json")):
                validate_output_record(json.loads(path.read_text(encoding="utf-8")))
            self.transactions_root.mkdir(parents=True, exist_ok=True)
            self._inject("before_atomic_publish")
            if self.before_publish_guard_hook is not None:
                self.before_publish_guard_hook()
            if pre_publish_guard is not None:
                pre_publish_guard()
            published = dict(existing)
            try:
                os.replace(staging, destination)
                published.update({_identity(item): item for item in missing})
            except OSError:
                if not destination.exists():
                    raise
                published = {_identity(item): item for item in self.read_records()}
                for record in records:
                    prior = published.get(_identity(record))
                    if prior is None or canonical_bytes(prior) != canonical_bytes(
                        record
                    ):
                        fail("B04_CONCURRENT_PUBLISH_CONFLICT", _identity_text(record))
                self._clear_staging(staging)
            self.events.append(
                {"event": "atomic_publish", "transaction_id": transaction_id}
            )
        except Exception:
            self._clear_staging(staging)
            if not transactions_root_existed:
                try:
                    self.transactions_root.rmdir()
                except (FileNotFoundError, OSError):
                    pass
            if not root_existed:
                try:
                    self.root.rmdir()
                except (FileNotFoundError, OSError):
                    pass
            raise
        return [deepcopy(published[_identity(record)]) for record in records]


class ProtectionSetBuilder:
    """Unique writer for M3_CANDIDATE_PROTECTION_SET."""

    WRITER_NAME = "ProtectionSetBuilder"

    @staticmethod
    def build(
        *,
        context: dict[str, Any],
        policy: dict[str, Any],
        groups: list[dict[str, Any]],
        created_at: str,
        access: str = FIXTURE_ACCESS,
    ) -> dict[str, Any]:
        base = context["candidate_version"]
        payload = {
            "base_candidate_version_ref": record_ref(base),
            "protection_policy_ref": record_ref(policy),
            "chapter_revision_ref": deepcopy(base["payload"]["chapter_revision_ref"]),
            "protected_entries": expected_protected_entries(
                context=context, groups=groups
            ),
        }
        payload_hash = sha256_value(payload)
        return build_record(
            record_type="M3_CANDIDATE_PROTECTION_SET",
            record_id=f"protection-set:{payload_hash}",
            payload=payload,
            created_at=created_at,
            access=access,
            writer_token=_WRITER_TOKENS["M3_CANDIDATE_PROTECTION_SET"],
        )


class CausalHintProposalRecorder:
    """Unique writer for noncommittable M3_CAUSAL_HINT_PROPOSAL originals."""

    WRITER_NAME = "CausalHintProposalRecorder"

    @staticmethod
    def build(
        *, payload: dict[str, Any], created_at: str, access: str = FIXTURE_ACCESS
    ) -> dict[str, Any]:
        payload_hash = sha256_value(payload)
        return build_record(
            record_type="M3_CAUSAL_HINT_PROPOSAL",
            record_id=f"causal-hint-proposal:{payload_hash}",
            payload=payload,
            created_at=created_at,
            access=access,
            writer_token=_WRITER_TOKENS["M3_CAUSAL_HINT_PROPOSAL"],
        )


class PatchRecorder:
    """Unique writer for immutable M3_PATCH_PROPOSAL originals."""

    WRITER_NAME = "PatchRecorder"

    @staticmethod
    def build(
        *, payload: dict[str, Any], created_at: str, access: str = FIXTURE_ACCESS
    ) -> dict[str, Any]:
        payload_hash = sha256_value(payload)
        return build_record(
            record_type="M3_PATCH_PROPOSAL",
            record_id=f"patch-proposal:{payload_hash}",
            payload=payload,
            created_at=created_at,
            access=access,
            writer_token=_WRITER_TOKENS["M3_PATCH_PROPOSAL"],
        )


class B04Service:
    """Orchestrates one fail-closed proposal transaction without a fourth writer."""

    __slots__ = ("_store", "__b02_store", "__b03_service")

    def __init__(
        self,
        store: FixtureStore,
        *,
        b02_store: B02FixtureStore,
        b03_service: B03Service | None = None,
    ) -> None:
        if not isinstance(b02_store, B02FixtureStore):
            fail("B04_B02_CURRENT_STATE_READER_REQUIRED")
        if b03_service is not None and not isinstance(b03_service, B03Service):
            fail("B04_B03_CURRENT_STATE_READER_INVALID")
        self._store = store
        self.__b02_store = b02_store
        self.__b03_service = b03_service

    @staticmethod
    def __stable_record_bytes(records: list[dict[str, Any]]) -> bytes:
        return canonical_bytes(
            sorted(records, key=lambda item: canonical_bytes(record_ref(item)))
        )

    def __require_live_source_slices(
        self, source_slice_records: list[dict[str, Any]]
    ) -> None:
        if not source_slice_records:
            return
        if self.__b03_service is None:
            fail("B04_B03_CURRENT_STATE_READER_REQUIRED")
        for source_slice in source_slice_records:
            try:
                source_slice_ref = b03_record_ref(source_slice)
                content = self.__b03_service.read_slice_content(source_slice_ref)
                stored = self.__b03_service.slice_core(source_slice_ref)
            except B03ContractError as error:
                fail("B04_B03_SOURCE_NOT_ACTIVE", error.code)
            if stored is None or stored.get("record_ref") != source_slice_ref:
                fail("B04_B03_CURRENT_STATE_MISMATCH", "missing exact slice")
            expected_core = deepcopy(source_slice)
            del expected_core["payload"]["content"]
            if canonical_bytes(stored.get("core")) != canonical_bytes(expected_core):
                fail("B04_B03_CURRENT_STATE_MISMATCH", "slice core drift")
            expected_content = source_slice["payload"]["content"]
            expected_bytes = expected_content.encode("utf-8")
            if (
                content != expected_content
                or stored.get("content_sha256")
                != hashlib.sha256(expected_bytes).hexdigest()
                or stored.get("content_utf8_bytes") != len(expected_bytes)
            ):
                fail("B04_B03_CURRENT_STATE_MISMATCH", "content drift")

    def propose(
        self,
        *,
        context: dict[str, Any],
        policy: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        coverages: list[dict[str, Any]],
        source_slice_records: list[dict[str, Any]],
        groups: list[dict[str, Any]],
        causal_payloads: list[dict[str, Any]],
        created_at: str,
        access: str = FIXTURE_ACCESS,
    ) -> dict[str, Any]:
        context = deepcopy(context)
        policy = deepcopy(policy)
        diagnostics = deepcopy(diagnostics)
        coverages = deepcopy(coverages)
        source_slice_records = deepcopy(source_slice_records)
        groups = deepcopy(groups)
        causal_payloads = deepcopy(causal_payloads)

        diagnostics = sorted(
            diagnostics, key=lambda item: canonical_bytes(record_ref(item))
        )
        coverages = sorted(
            coverages, key=lambda item: canonical_bytes(record_ref(item))
        )
        upstream_records = self.__b02_store.read_records()
        upstream_snapshot = self.__stable_record_bytes(upstream_records)
        authoritative_by_ref = {
            canonical_bytes(record_ref(item)): item for item in upstream_records
        }
        for selected in [*diagnostics, *coverages]:
            authoritative = authoritative_by_ref.get(
                canonical_bytes(record_ref(selected))
            )
            if authoritative is None or canonical_bytes(
                authoritative
            ) != canonical_bytes(selected):
                fail("B04_B02_CURRENT_STATE_MISMATCH")
        lifecycle_receipts = [
            item
            for item in upstream_records
            if item["record_type"] == "M3_DIAGNOSTIC_LIFECYCLE_RECEIPT"
        ]
        base = context["candidate_version"]

        validate_upstream_inputs(
            context=context,
            diagnostics=diagnostics,
            coverages=coverages,
            lifecycle_receipts=lifecycle_receipts,
            upstream_records=upstream_records,
        )
        validate_atomic_groups(
            groups,
            context=context,
            diagnostics=diagnostics,
            coverages=coverages,
            lifecycle_receipts=lifecycle_receipts,
        )
        source_slice_refs = validate_source_slice_records(
            source_slice_records,
            context=context,
            groups=groups,
        )
        self.__require_live_source_slices(source_slice_records)
        protection_candidate = ProtectionSetBuilder.build(
            context=context,
            policy=policy,
            groups=groups,
            created_at=created_at,
            access=access,
        )
        validate_protection_record(
            protection_candidate, context=context, policy=policy, groups=groups
        )
        causal_candidates = [
            CausalHintProposalRecorder.build(
                payload=payload, created_at=created_at, access=access
            )
            for payload in causal_payloads
        ]
        for causal in causal_candidates:
            validate_causal_record(
                causal,
                context=context,
                diagnostic_refs=[record_ref(item) for item in diagnostics],
                coverage_refs=[record_ref(item) for item in coverages],
                source_slice_refs=source_slice_refs,
            )

        def pre_publish_guard() -> None:
            if self.__stable_record_bytes(self.__b02_store.read_records()) != (
                upstream_snapshot
            ):
                fail("B04_B02_CURRENT_STATE_CHANGED")
            self.__require_live_source_slices(source_slice_records)

        with self._store._publish_serialization():
            existing = {_identity(item): item for item in self._store.read_records()}
            protection = self._store._reuse_existing_original(
                protection_candidate, existing
            )
            validate_protection_record(
                protection, context=context, policy=policy, groups=groups
            )
            causal_records = [
                self._store._reuse_existing_original(candidate, existing)
                for candidate in causal_candidates
            ]
            for causal in causal_records:
                validate_causal_record(
                    causal,
                    context=context,
                    diagnostic_refs=[record_ref(item) for item in diagnostics],
                    coverage_refs=[record_ref(item) for item in coverages],
                    source_slice_refs=source_slice_refs,
                )
            patch_payload = {
                "base_candidate_version_ref": record_ref(base),
                "candidate_schema_id": CANDIDATE_SCHEMA_ID,
                "diagnostic_refs": [record_ref(item) for item in diagnostics],
                "coverage_observation_refs": [record_ref(item) for item in coverages],
                "authorized_source_slice_refs": source_slice_refs,
                "protection_set_ref": record_ref(protection),
                "chapter_revision_ref": deepcopy(
                    base["payload"]["chapter_revision_ref"]
                ),
                "atomic_groups": groups,
                "sidecar_proposal_refs": [record_ref(item) for item in causal_records],
            }
            patch_candidate = PatchRecorder.build(
                payload=patch_payload, created_at=created_at, access=access
            )
            validate_patch_record(
                patch_candidate,
                context=context,
                diagnostics=diagnostics,
                coverages=coverages,
                lifecycle_receipts=lifecycle_receipts,
                source_slice_records=source_slice_records,
                protection=protection,
                causal_records=causal_records,
            )
            patch = self._store._reuse_existing_original(patch_candidate, existing)
            validate_patch_record(
                patch,
                context=context,
                diagnostics=diagnostics,
                coverages=coverages,
                lifecycle_receipts=lifecycle_receipts,
                source_slice_records=source_slice_records,
                protection=protection,
                causal_records=causal_records,
            )
            preview = PatchPreviewProjector.project(
                context=context,
                protection=protection,
                patch=patch,
                causal_records=causal_records,
            )
            published = self._store._commit_bundle(
                [protection, *causal_records, patch],
                pre_publish_guard=pre_publish_guard,
                _serialized=True,
            )
        by_type = {}
        for item in published:
            by_type.setdefault(item["record_type"], []).append(item)
        published_protection = by_type["M3_CANDIDATE_PROTECTION_SET"][0]
        published_causal = by_type.get("M3_CAUSAL_HINT_PROPOSAL", [])
        published_patch = by_type["M3_PATCH_PROPOSAL"][0]
        return {
            "protection_set_ref": record_ref(published_protection),
            "causal_hint_proposal_refs": [
                record_ref(item) for item in published_causal
            ],
            "patch_proposal_ref": record_ref(published_patch),
            "patch_preview": preview,
        }
