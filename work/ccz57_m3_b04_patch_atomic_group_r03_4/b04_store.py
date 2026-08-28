"""Atomic fixture store and the three B-04 unique record writers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from b04_contracts import (
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
    validate_source_slice_refs,
    validate_upstream_inputs,
)
from patch_preview_projection import PatchPreviewProjector

_FIXED_PROTECTION_PAYLOAD_HASH = (
    "fc0c724ea0b3c753316fbd3782f608a5122f3ddbae2a7c28e612de4e0d02b2ac"
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

    __slots__ = ("root", "transactions_root", "failure_point", "events")

    def __init__(self, root: Path, *, failure_point: str | None = None) -> None:
        resolved = root.resolve(strict=False)
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
            fail("B04_WRITE_SET_ESCAPE", str(root))
        self.root = root
        self.transactions_root = root / "transactions"
        self.failure_point = failure_point
        self.events: list[dict[str, str]] = []

    def _inject(self, point: str) -> None:
        if self.failure_point == point:
            fail("B04_SIMULATED_TRANSACTION_FAILURE", point)

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

    def _commit_bundle(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            return [deepcopy(existing[_identity(record)]) for record in records]

        transaction_id = sha256_value(
            sorted(
                [record_ref(record) for record in missing],
                key=lambda ref: canonical_bytes(ref),
            )
        )
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
            self._inject("before_atomic_publish")
            self.transactions_root.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(staging, destination)
            except FileExistsError:
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
            raise
        published = {_identity(item): item for item in self.read_records()}
        return [deepcopy(published[_identity(record)]) for record in records]


class ProtectionSetBuilder:
    """Unique writer for M3_CANDIDATE_PROTECTION_SET."""

    WRITER_NAME = "ProtectionSetBuilder"

    @staticmethod
    def build(
        *,
        base: dict[str, Any],
        policy: dict[str, Any],
        groups: list[dict[str, Any]],
        created_at: str,
        access: str = FIXTURE_ACCESS,
    ) -> dict[str, Any]:
        payload = {
            "base_candidate_version_ref": record_ref(base),
            "protection_policy_ref": record_ref(policy),
            "chapter_revision_ref": deepcopy(base["payload"]["chapter_revision_ref"]),
            "protected_entries": expected_protected_entries(base=base, groups=groups),
        }
        payload_hash = sha256_value(payload)
        record_id = (
            "protect_fixture_001"
            if payload_hash == _FIXED_PROTECTION_PAYLOAD_HASH
            else f"protection-set:{payload_hash}"
        )
        return build_record(
            record_type="M3_CANDIDATE_PROTECTION_SET",
            record_id=record_id,
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

    __slots__ = ("_store",)

    def __init__(self, store: FixtureStore) -> None:
        self._store = store

    def propose(
        self,
        *,
        base: dict[str, Any],
        policy: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        coverages: list[dict[str, Any]],
        source_slice_refs: list[dict[str, Any]],
        source_slice_revision: dict[str, Any] | None,
        groups: list[dict[str, Any]],
        causal_payloads: list[dict[str, Any]],
        created_at: str,
        access: str = FIXTURE_ACCESS,
    ) -> dict[str, Any]:
        base = deepcopy(base)
        policy = deepcopy(policy)
        diagnostics = deepcopy(diagnostics)
        coverages = deepcopy(coverages)
        source_slice_refs = deepcopy(source_slice_refs)
        source_slice_revision = deepcopy(source_slice_revision)
        groups = deepcopy(groups)
        causal_payloads = deepcopy(causal_payloads)

        validate_upstream_inputs(
            base=base, diagnostics=diagnostics, coverages=coverages
        )
        validate_source_slice_refs(
            source_slice_refs,
            source_slice_revision=source_slice_revision,
            revision=base["payload"]["chapter_revision_ref"],
        )
        validate_atomic_groups(
            groups, base=base, diagnostics=diagnostics, coverages=coverages
        )
        protection = ProtectionSetBuilder.build(
            base=base,
            policy=policy,
            groups=groups,
            created_at=created_at,
            access=access,
        )
        validate_protection_record(protection, base=base, policy=policy, groups=groups)
        causal_records = [
            CausalHintProposalRecorder.build(
                payload=payload, created_at=created_at, access=access
            )
            for payload in causal_payloads
        ]
        for causal in causal_records:
            validate_causal_record(
                causal,
                base=base,
                diagnostics=diagnostics,
                source_slice_refs=source_slice_refs,
            )
        patch_payload = {
            "base_candidate_version_ref": record_ref(base),
            "diagnostic_refs": [record_ref(item) for item in diagnostics],
            "authorized_source_slice_refs": source_slice_refs,
            "protection_set_ref": record_ref(protection),
            "chapter_revision_ref": deepcopy(base["payload"]["chapter_revision_ref"]),
            "atomic_groups": groups,
            "sidecar_proposal_refs": [record_ref(item) for item in causal_records],
        }
        patch = PatchRecorder.build(
            payload=patch_payload, created_at=created_at, access=access
        )
        validate_patch_record(
            patch,
            base=base,
            diagnostics=diagnostics,
            coverages=coverages,
            protection=protection,
            causal_records=causal_records,
            source_slice_revision=source_slice_revision,
        )
        published = self._store._commit_bundle([protection, *causal_records, patch])
        by_type = {}
        for item in published:
            by_type.setdefault(item["record_type"], []).append(item)
        published_protection = by_type["M3_CANDIDATE_PROTECTION_SET"][0]
        published_causal = by_type.get("M3_CAUSAL_HINT_PROPOSAL", [])
        published_patch = by_type["M3_PATCH_PROPOSAL"][0]
        preview = PatchPreviewProjector.project(
            base=base,
            protection=published_protection,
            patch=published_patch,
            causal_records=published_causal,
        )
        return {
            "protection_set_ref": record_ref(published_protection),
            "causal_hint_proposal_refs": [
                record_ref(item) for item in published_causal
            ],
            "patch_proposal_ref": record_ref(published_patch),
            "patch_preview": preview,
        }
