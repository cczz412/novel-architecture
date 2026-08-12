#!/usr/bin/env python3
"""Resolve registered artifacts and restore approved POSIX tar archives.

Legacy S-06-C cards still resolve to deterministic copy plans.  The separate
``restore-archive`` command only accepts a registered tar representation, a
fresh repository TEMP destination, and a mounted volume resolved by UUID.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

if __package__:
    from tools import repo_slim_inventory as inventory
else:
    import repo_slim_inventory as inventory


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_RELATIVE = "governance/external_archive_registry.json"
VALIDATION_POLICY_RELATIVE = "governance/external_payload_validation_policy.json"
RETRIEVAL_POLICY_RELATIVE = "governance/artifact_retrieval_policy.json"
RESOLVER_RELATIVE = "tools/experiment_artifact_retrieval.py"
EXTERNAL_ROOT_ID = "repository_sibling_external_archive_v1"
EXTERNAL_ROOT_SUFFIX = "_外置仓"
TEST_WORKSPACE_ROOT_ID = "repository_sibling_test_workspace_v1"
PROTECTED_R02_ID = "cmin-b-refreeze-20260730-r02"
HISTORICAL_CARD_ROOT = PurePosixPath("config/test_replay/result_cards")
EVIDENCE_ROOTS = {
    "config",
    "experiments",
    "governance",
    "references",
    "schemas",
    "tests",
    "tools",
}
PROHIBITED_REPOSITORY_ROOTS = {"TEMP", "outbox", "reports", "runs"}
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]+$")
CONFIG_MAX_BYTES = 4 * 1024 * 1024
MANIFEST_MAX_BYTES = 32 * 1024 * 1024


class RetrievalError(RuntimeError):
    """Fail-closed S-06-C contract error."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = code if not detail else f"{code}: {detail}"
        super().__init__(message)


@dataclass(frozen=True)
class FileSnapshot:
    root: Path
    relative: PurePosixPath
    sha256: str
    directory_identities: tuple[tuple[int, int, int, int, int, int, int], ...]
    file_identity: tuple[int, int, int, int, int, int, int]
    size: int
    max_bytes: int

    @property
    def path(self) -> Path:
        return self.root.joinpath(*self.relative.parts)


@dataclass(frozen=True)
class CardChain:
    policy: dict[str, Any]
    policy_row: dict[str, Any]
    card: dict[str, Any]
    pointer: dict[str, Any]
    profile: dict[str, Any]
    snapshots: tuple[FileSnapshot, ...]


@dataclass(frozen=True)
class ResolvedContext:
    chain: CardChain
    registry: dict[str, Any]
    validation_policy: dict[str, Any]
    object_row: dict[str, Any]
    validation_target: dict[str, Any]
    manifest: dict[str, Any]
    manifest_entries: tuple[dict[str, Any], ...]
    snapshots: tuple[FileSnapshot, ...]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _identity(value: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _safe_relative_path(value: object, *, code: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "\x00" in value
        or "//" in value
        or value.endswith("/")
    ):
        raise RetrievalError(code, str(value))
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or relative.as_posix() in {"", "."}
        or any(part in {"", ".", ".."} for part in relative.parts)
        or relative.as_posix() != value
    ):
        raise RetrievalError(code, value)
    return relative


def _require_id(value: object, *, code: str) -> str:
    if not isinstance(value, str) or SAFE_ID.fullmatch(value) is None:
        raise RetrievalError(code, str(value))
    return value


def _require_sha(value: object, *, code: str) -> str:
    if not isinstance(value, str) or HEX_64.fullmatch(value) is None:
        raise RetrievalError(code, str(value))
    return value


def _require_text(value: object, *, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetrievalError(code, str(value))
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_tar_member_name(value: str) -> PurePosixPath:
    while value.startswith("./"):
        value = value[2:]
    return _safe_relative_path(value, code="TAR_MEMBER_PATH_INVALID")


def _symlink_target_stays_within_tree(
    member: PurePosixPath,
    target: str,
) -> bool:
    if not target or "\\" in target or "\x00" in target:
        return False
    candidate = member.parent.joinpath(PurePosixPath(target))
    depth = 0
    for part in candidate.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                return False
        else:
            depth += 1
    return True


def _verify_restored_tree(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    expected_files = {row["path"]: row for row in manifest.get("files", [])}
    expected_links = {row["path"]: row for row in manifest.get("symlinks", [])}
    actual_files: set[str] = set()
    actual_links: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            actual_links.add(relative)
        elif path.is_file():
            actual_files.add(relative)
    if actual_files != set(expected_files) or actual_links != set(expected_links):
        raise RetrievalError("RESTORE_MEMBER_SET_MISMATCH")
    for relative, row in expected_files.items():
        path = root.joinpath(*PurePosixPath(relative).parts)
        if path.stat().st_size != row["bytes"] or _sha256_file(path) != row["sha256"]:
            raise RetrievalError("RESTORE_FILE_IDENTITY_MISMATCH", relative)
    for relative, row in expected_links.items():
        path = root.joinpath(*PurePosixPath(relative).parts)
        expected_target = row.get("archive_link_target")
        if not path.is_symlink() or os.readlink(path) != expected_target:
            raise RetrievalError("RESTORE_SYMLINK_IDENTITY_MISMATCH", relative)
        if path.exists() != row.get("archive_target_exists"):
            raise RetrievalError("RESTORE_SYMLINK_TARGET_STATE_MISMATCH", relative)
        if path.exists() and isinstance(row.get("resolved_sha256"), str):
            if _sha256_file(path.resolve(strict=True)) != row["resolved_sha256"]:
                raise RetrievalError("RESTORE_SYMLINK_RESOLVED_DIGEST_MISMATCH")
    return {
        "member_count": len(expected_files) + len(expected_links),
        "regular_file_count": len(expected_files),
        "symlink_count": len(expected_links),
        "total_logical_bytes": manifest.get("source_total_bytes"),
        "aggregate_sha256": manifest.get("aggregate_sha256"),
    }


def _require_exact_keys(
    value: object,
    *,
    expected: set[str],
    code: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise RetrievalError(code, str(actual))
    return value


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _file_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _require_platform_capabilities() -> None:
    required = {
        "O_DIRECTORY": hasattr(os, "O_DIRECTORY"),
        "O_NOFOLLOW": hasattr(os, "O_NOFOLLOW"),
        "O_NONBLOCK": hasattr(os, "O_NONBLOCK"),
        "open_dir_fd": os.open in getattr(os, "supports_dir_fd", set()),
    }
    missing = sorted(name for name, available in required.items() if not available)
    if missing:
        raise RetrievalError(
            "PLATFORM_CAPABILITY_MISSING",
            ", ".join(missing),
        )


def _open_directory_chain(
    root: Path,
    relative: PurePosixPath,
    *,
    code: str,
) -> tuple[list[int], int, tuple[tuple[int, int, int, int, int, int, int], ...]]:
    descriptors: list[int] = []
    try:
        descriptor = os.open(root, _directory_flags())
    except OSError as exc:
        raise RetrievalError(f"{code}_ROOT_UNSAFE", str(root)) from exc
    descriptors.append(descriptor)
    try:
        root_info = os.fstat(descriptor)
        if not stat.S_ISDIR(root_info.st_mode):
            raise RetrievalError(f"{code}_ROOT_UNSAFE", str(root))
        root_device = root_info.st_dev
        identities = [_identity(root_info)]
        for part in relative.parts:
            try:
                child = os.open(
                    part,
                    _directory_flags(),
                    dir_fd=descriptors[-1],
                )
            except OSError as exc:
                raise RetrievalError(
                    f"{code}_PARENT_UNSAFE",
                    relative.as_posix(),
                ) from exc
            descriptors.append(child)
            info = os.fstat(child)
            if not stat.S_ISDIR(info.st_mode) or info.st_dev != root_device:
                raise RetrievalError(
                    f"{code}_PARENT_UNSAFE",
                    relative.as_posix(),
                )
            identities.append(_identity(info))
        return descriptors, root_device, tuple(identities)
    except Exception:
        for opened_descriptor in reversed(descriptors):
            os.close(opened_descriptor)
        raise


def _read_beneath_root(
    root: Path,
    relative_value: object,
    *,
    max_bytes: int,
    code: str,
) -> tuple[bytes, FileSnapshot, PurePosixPath]:
    _require_platform_capabilities()
    relative = _safe_relative_path(relative_value, code=f"{code}_PATH_INVALID")
    descriptors, root_device, directory_identities = _open_directory_chain(
        root,
        relative.parent,
        code=code,
    )
    file_descriptor: int | None = None
    verification_descriptors: list[int] = []
    verification_file: int | None = None
    try:
        try:
            file_descriptor = os.open(
                relative.name,
                _file_flags(),
                dir_fd=descriptors[-1],
            )
        except OSError as exc:
            raise RetrievalError(f"{code}_UNSAFE", relative.as_posix()) from exc
        opened = os.fstat(file_descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_dev != root_device
            or opened.st_size > max_bytes
        ):
            raise RetrievalError(f"{code}_UNSAFE", relative.as_posix())
        opened_identity = _identity(opened)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                file_descriptor,
                min(1024 * 1024, max_bytes + 1 - total),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise RetrievalError(f"{code}_TOO_LARGE", relative.as_posix())
        if _identity(os.fstat(file_descriptor)) != opened_identity:
            raise RetrievalError(f"{code}_RACE", relative.as_posix())

        verification_descriptors, _, verification_identities = _open_directory_chain(
            root,
            relative.parent,
            code=code,
        )
        if verification_identities != directory_identities:
            raise RetrievalError(f"{code}_PARENT_RACE", relative.as_posix())
        try:
            verification_file = os.open(
                relative.name,
                _file_flags(),
                dir_fd=verification_descriptors[-1],
            )
        except OSError as exc:
            raise RetrievalError(f"{code}_RACE", relative.as_posix()) from exc
        if _identity(os.fstat(verification_file)) != opened_identity:
            raise RetrievalError(f"{code}_RACE", relative.as_posix())

        payload = b"".join(chunks)
        if len(payload) != opened.st_size:
            raise RetrievalError(f"{code}_SIZE_DRIFT", relative.as_posix())
        return (
            payload,
            FileSnapshot(
                root=root,
                relative=relative,
                sha256=_sha256_bytes(payload),
                directory_identities=directory_identities,
                file_identity=opened_identity,
                size=len(payload),
                max_bytes=max_bytes,
            ),
            relative,
        )
    finally:
        if verification_file is not None:
            os.close(verification_file)
        for opened_descriptor in reversed(verification_descriptors):
            os.close(opened_descriptor)
        if file_descriptor is not None:
            os.close(file_descriptor)
        for opened_descriptor in reversed(descriptors):
            os.close(opened_descriptor)


def _read_repo_file(
    repo_root: Path,
    relative_value: object,
    *,
    expected_sha256: str | None = None,
    code: str,
) -> tuple[bytes, FileSnapshot, PurePosixPath]:
    payload, snapshot, relative = _read_beneath_root(
        repo_root,
        relative_value,
        max_bytes=CONFIG_MAX_BYTES,
        code=code,
    )
    if expected_sha256 is not None and snapshot.sha256 != expected_sha256:
        raise RetrievalError(f"{code}_SHA_MISMATCH", relative.as_posix())
    return payload, snapshot, relative


def _load_json_bytes(payload: bytes, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetrievalError(f"{code}_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise RetrievalError(f"{code}_ROOT_INVALID")
    return value


def _load_repo_json(
    repo_root: Path,
    relative_value: object,
    *,
    expected_sha256: str | None = None,
    code: str,
) -> tuple[dict[str, Any], FileSnapshot, PurePosixPath]:
    payload, snapshot, relative = _read_repo_file(
        repo_root,
        relative_value,
        expected_sha256=expected_sha256,
        code=code,
    )
    return _load_json_bytes(payload, code=code), snapshot, relative


def _validate_repo_ref(value: object, *, code: str) -> dict[str, str]:
    row = _require_exact_keys(
        value,
        expected={"path", "sha256"},
        code=f"{code}_FIELDS_INVALID",
    )
    path = _safe_relative_path(row["path"], code=f"{code}_PATH_INVALID").as_posix()
    digest = _require_sha(row["sha256"], code=f"{code}_SHA_INVALID")
    return {"path": path, "sha256": digest}


def _validate_card_location(path: str, card_id: str) -> None:
    relative = _safe_relative_path(path, code="RESULT_CARD_LOCATION_INVALID")
    historical = HISTORICAL_CARD_ROOT / card_id / "result_card.json"
    experiment_local = (
        len(relative.parts) == 3
        and relative.parts[0] == "experiments"
        and relative.parts[2] == "result_card.json"
        and not relative.parts[1].startswith((".", "_"))
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]+", relative.parts[1]) is not None
    )
    if relative != historical and not experiment_local:
        raise RetrievalError("RESULT_CARD_LOCATION_INVALID", path)


def _validate_evidence_location(path: str) -> None:
    relative = _safe_relative_path(path, code="RESULT_CARD_EVIDENCE_PATH_INVALID")
    first = relative.parts[0]
    if first in PROHIBITED_REPOSITORY_ROOTS or first not in EVIDENCE_ROOTS:
        raise RetrievalError("RESULT_CARD_EVIDENCE_LOCATION_INVALID", path)


def _validate_policy(policy: dict[str, Any]) -> list[dict[str, Any]]:
    _require_exact_keys(
        policy,
        expected={
            "contract_version",
            "policy_id",
            "registry_id",
            "validation_policy_id",
            "authority",
            "capability_limits",
            "allowed_root_ids",
            "cards",
            "protected_non_targets",
            "boundary",
        },
        code="RETRIEVAL_POLICY_FIELDS_INVALID",
    )
    if policy["contract_version"] != "artifact-retrieval-policy-v1":
        raise RetrievalError("RETRIEVAL_POLICY_VERSION_INVALID")
    _require_id(policy["policy_id"], code="RETRIEVAL_POLICY_ID_INVALID")
    _require_id(policy["registry_id"], code="RETRIEVAL_REGISTRY_ID_INVALID")
    _require_id(
        policy["validation_policy_id"],
        code="RETRIEVAL_VALIDATION_POLICY_ID_INVALID",
    )
    expected_authority = {
        "scope": "registered_manifest_to_copy_plan_only",
        "may_discover_targets": False,
        "may_read_payload": False,
        "may_copy": False,
        "may_move": False,
        "may_delete": False,
        "may_restore": False,
        "may_issue_migration_receipt": False,
        "may_activate_hard_limit": False,
    }
    if policy["authority"] != expected_authority:
        raise RetrievalError("RETRIEVAL_POLICY_AUTHORITY_INVALID")
    expected_capabilities = {
        "one_card_per_command": True,
        "registered_manifest_read": True,
        "deterministic_plan_output": True,
        "write": False,
        "network": False,
        "credential_read": False,
        "model_call": False,
        "notion_write": False,
    }
    if policy["capability_limits"] != expected_capabilities:
        raise RetrievalError("RETRIEVAL_POLICY_CAPABILITIES_INVALID")
    if policy["allowed_root_ids"] != [EXTERNAL_ROOT_ID]:
        raise RetrievalError("RETRIEVAL_ALLOWED_ROOTS_INVALID")
    _require_text(policy["boundary"], code="RETRIEVAL_POLICY_BOUNDARY_INVALID")

    cards = policy["cards"]
    if not isinstance(cards, list) or not cards:
        raise RetrievalError("RETRIEVAL_POLICY_CARDS_INVALID")
    normalized: list[dict[str, Any]] = []
    for value in cards:
        row = _require_exact_keys(
            value,
            expected={"card_id", "result_card_ref", "allowed_selection_ids"},
            code="RETRIEVAL_POLICY_CARD_FIELDS_INVALID",
        )
        card_id = _require_id(row["card_id"], code="RETRIEVAL_CARD_ID_INVALID")
        result_ref = _validate_repo_ref(
            row["result_card_ref"],
            code="RETRIEVAL_RESULT_CARD_REF",
        )
        _validate_card_location(result_ref["path"], card_id)
        selection_ids = row["allowed_selection_ids"]
        if (
            not isinstance(selection_ids, list)
            or not selection_ids
            or any(
                not isinstance(item, str) or SAFE_ID.fullmatch(item) is None
                for item in selection_ids
            )
            or selection_ids != sorted(set(selection_ids))
        ):
            raise RetrievalError("RETRIEVAL_SELECTION_ALLOWLIST_INVALID", card_id)
        normalized.append(
            {
                "card_id": card_id,
                "result_card_ref": result_ref,
                "allowed_selection_ids": selection_ids,
            }
        )
    if [row["card_id"] for row in normalized] != sorted(
        {row["card_id"] for row in normalized}
    ):
        raise RetrievalError("RETRIEVAL_POLICY_CARD_ORDER_INVALID")
    result_paths = [row["result_card_ref"]["path"] for row in normalized]
    if len(result_paths) != len(set(result_paths)):
        raise RetrievalError("RETRIEVAL_POLICY_CARD_PATH_DUPLICATE")

    protected = policy["protected_non_targets"]
    if not isinstance(protected, list):
        raise RetrievalError("PROTECTED_NON_TARGETS_INVALID")
    protected_ids: list[str] = []
    for value in protected:
        row = _require_exact_keys(
            value,
            expected={"subject_id", "reason", "discovery_prohibited"},
            code="PROTECTED_NON_TARGET_FIELDS_INVALID",
        )
        protected_ids.append(
            _require_id(row["subject_id"], code="PROTECTED_SUBJECT_ID_INVALID")
        )
        _require_text(row["reason"], code="PROTECTED_REASON_INVALID")
        if row["discovery_prohibited"] is not True:
            raise RetrievalError("PROTECTED_DISCOVERY_FLAG_INVALID")
    if PROTECTED_R02_ID not in protected_ids:
        raise RetrievalError("ACTIVE_R02_EXCLUSION_MISSING")
    if len(protected_ids) != len(set(protected_ids)):
        raise RetrievalError("PROTECTED_NON_TARGET_DUPLICATE")
    return normalized


def _validate_card(card: dict[str, Any], *, expected_card_id: str) -> None:
    _require_exact_keys(
        card,
        expected={
            "contract_version",
            "card_id",
            "experiment_id",
            "record_kind",
            "title",
            "terminal_status",
            "quality_verdict",
            "purpose",
            "assembly_summary",
            "short_conclusion",
            "evidence_boundary",
            "consumer_closure",
            "source_git_commit",
            "pointer_ref",
            "relations",
            "boundary",
        },
        code="RESULT_CARD_FIELDS_INVALID",
    )
    if card["contract_version"] != "experiment-result-card-v1":
        raise RetrievalError("RESULT_CARD_VERSION_INVALID")
    if card["card_id"] != expected_card_id:
        raise RetrievalError("RESULT_CARD_ID_MISMATCH")
    _require_id(card["card_id"], code="RESULT_CARD_ID_INVALID")
    _require_text(card["experiment_id"], code="EXPERIMENT_ID_INVALID")
    if card["record_kind"] not in {
        "model_experiment",
        "component_experiment",
        "repository_maintenance_experiment",
        "historical_replay",
    }:
        raise RetrievalError("RESULT_CARD_KIND_INVALID")
    if card["terminal_status"] not in {
        "completed",
        "negative_result",
        "hard_stopped",
        "superseded",
        "retired",
    }:
        raise RetrievalError("RESULT_CARD_NOT_TERMINAL")
    if card["quality_verdict"] not in {
        "passed",
        "failed",
        "negative_result",
        "mixed",
        "not_evaluated",
    }:
        raise RetrievalError("RESULT_CARD_VERDICT_INVALID")
    for key in ("title", "purpose", "evidence_boundary", "boundary"):
        _require_text(card[key], code=f"RESULT_CARD_{key.upper()}_INVALID")
    for key, maximum in (("assembly_summary", 6), ("short_conclusion", 5)):
        values = card[key]
        if (
            not isinstance(values, list)
            or not 1 <= len(values) <= maximum
            or any(not isinstance(item, str) or not item.strip() for item in values)
        ):
            raise RetrievalError(f"RESULT_CARD_{key.upper()}_INVALID")
    if (
        not isinstance(card["source_git_commit"], str)
        or HEX_40.fullmatch(card["source_git_commit"]) is None
    ):
        raise RetrievalError("RESULT_CARD_GIT_COMMIT_INVALID")
    _validate_repo_ref(card["pointer_ref"], code="RESULT_CARD_POINTER_REF")

    closure = _require_exact_keys(
        card["consumer_closure"],
        expected={"status", "consumers", "evidence_refs"},
        code="RESULT_CARD_CLOSURE_FIELDS_INVALID",
    )
    if closure["status"] != "verified":
        raise RetrievalError("RESULT_CARD_CONSUMER_CLOSURE_NOT_VERIFIED")
    consumers = closure["consumers"]
    if (
        not isinstance(consumers, list)
        or not consumers
        or consumers != sorted(set(consumers))
        or any(not isinstance(item, str) or not item for item in consumers)
    ):
        raise RetrievalError("RESULT_CARD_CONSUMERS_INVALID")
    refs = closure["evidence_refs"]
    if not isinstance(refs, list) or not refs:
        raise RetrievalError("RESULT_CARD_EVIDENCE_REFS_INVALID")
    normalized_refs = [
        _validate_repo_ref(value, code="RESULT_CARD_EVIDENCE_REF") for value in refs
    ]
    for ref in normalized_refs:
        _validate_evidence_location(ref["path"])
    if [row["path"] for row in normalized_refs] != sorted(
        {row["path"] for row in normalized_refs}
    ):
        raise RetrievalError("RESULT_CARD_EVIDENCE_REF_ORDER_INVALID")

    relations = _require_exact_keys(
        card["relations"],
        expected={"supersedes_card_ids", "superseded_by_card_ids"},
        code="RESULT_CARD_RELATIONS_FIELDS_INVALID",
    )
    for key in ("supersedes_card_ids", "superseded_by_card_ids"):
        values = relations[key]
        if (
            not isinstance(values, list)
            or values != sorted(set(values))
            or any(
                not isinstance(item, str) or SAFE_ID.fullmatch(item) is None
                for item in values
            )
        ):
            raise RetrievalError("RESULT_CARD_RELATIONS_INVALID", key)


def _validate_pointer(
    pointer: dict[str, Any],
    *,
    card_id: str,
    registry_id: str,
    validation_policy_id: str,
) -> None:
    _require_exact_keys(
        pointer,
        expected={
            "contract_version",
            "pointer_id",
            "card_id",
            "artifact_id",
            "registry_id",
            "expected_manifest_sha256",
            "validation_policy_id",
            "retrieval_profile_ref",
            "root_resolution",
            "claims",
            "boundary",
        },
        code="EXTERNAL_POINTER_FIELDS_INVALID",
    )
    if pointer["contract_version"] != "external-artifact-pointer-v1":
        raise RetrievalError("EXTERNAL_POINTER_VERSION_INVALID")
    _require_id(pointer["pointer_id"], code="EXTERNAL_POINTER_ID_INVALID")
    if pointer["card_id"] != card_id:
        raise RetrievalError("EXTERNAL_POINTER_CARD_MISMATCH")
    _require_id(pointer["artifact_id"], code="EXTERNAL_POINTER_ARTIFACT_INVALID")
    if pointer["registry_id"] != registry_id:
        raise RetrievalError("EXTERNAL_POINTER_REGISTRY_MISMATCH")
    if pointer["validation_policy_id"] != validation_policy_id:
        raise RetrievalError("EXTERNAL_POINTER_VALIDATION_POLICY_MISMATCH")
    _require_sha(
        pointer["expected_manifest_sha256"],
        code="EXTERNAL_POINTER_MANIFEST_SHA_INVALID",
    )
    _validate_repo_ref(
        pointer["retrieval_profile_ref"],
        code="EXTERNAL_POINTER_PROFILE_REF",
    )
    if pointer["root_resolution"] != "registry_only_no_absolute_path":
        raise RetrievalError("EXTERNAL_POINTER_ROOT_RESOLUTION_INVALID")
    if pointer["claims"] != {
        "same_failure_domain": True,
        "independent_backup_proven": False,
        "retrieval_copy_performed": False,
        "migration_complete": False,
    }:
        raise RetrievalError("EXTERNAL_POINTER_CLAIMS_INVALID")
    _require_text(pointer["boundary"], code="EXTERNAL_POINTER_BOUNDARY_INVALID")


def _validate_profile(
    profile: dict[str, Any], *, artifact_id: str
) -> list[dict[str, Any]]:
    _require_exact_keys(
        profile,
        expected={
            "contract_version",
            "profile_id",
            "artifact_id",
            "operation",
            "source_scope",
            "destination",
            "selections",
            "safety",
            "boundary",
        },
        code="RETRIEVAL_PROFILE_FIELDS_INVALID",
    )
    if profile["contract_version"] != "artifact-retrieval-profile-v1":
        raise RetrievalError("RETRIEVAL_PROFILE_VERSION_INVALID")
    _require_id(profile["profile_id"], code="RETRIEVAL_PROFILE_ID_INVALID")
    if profile["artifact_id"] != artifact_id:
        raise RetrievalError("RETRIEVAL_PROFILE_ARTIFACT_MISMATCH")
    if profile["operation"] != "copy":
        raise RetrievalError("RETRIEVAL_PROFILE_OPERATION_INVALID")
    if profile["source_scope"] != "registered_external_payload_manifest":
        raise RetrievalError("RETRIEVAL_PROFILE_SOURCE_SCOPE_INVALID")
    if profile["destination"] != {
        "root_id": TEST_WORKSPACE_ROOT_ID,
        "relative_root": "payload",
        "fresh_workspace_required": True,
        "no_overwrite": True,
    }:
        raise RetrievalError("RETRIEVAL_PROFILE_DESTINATION_INVALID")
    if profile["safety"] != {
        "reject_symlink": True,
        "reject_hardlink": True,
        "reject_special_file": True,
        "verify_source_before_copy": True,
        "verify_target_after_copy": True,
        "no_source_write": True,
        "no_runtime_source_reference": True,
    }:
        raise RetrievalError("RETRIEVAL_PROFILE_SAFETY_INVALID")
    _require_text(profile["boundary"], code="RETRIEVAL_PROFILE_BOUNDARY_INVALID")

    selections = profile["selections"]
    if not isinstance(selections, list) or not selections:
        raise RetrievalError("RETRIEVAL_PROFILE_SELECTIONS_INVALID")
    normalized: list[dict[str, Any]] = []
    for value in selections:
        row = _require_exact_keys(
            value,
            expected={"selection_id", "mode", "manifest_paths", "purpose"},
            code="RETRIEVAL_SELECTION_FIELDS_INVALID",
        )
        selection_id = _require_id(
            row["selection_id"],
            code="RETRIEVAL_SELECTION_ID_INVALID",
        )
        mode = row["mode"]
        if mode not in {"all_manifest_entries", "exact_manifest_paths"}:
            raise RetrievalError("RETRIEVAL_SELECTION_MODE_INVALID")
        paths = row["manifest_paths"]
        if not isinstance(paths, list):
            raise RetrievalError("RETRIEVAL_SELECTION_PATHS_INVALID")
        normalized_paths = [
            _safe_relative_path(
                item, code="RETRIEVAL_SELECTION_PATH_INVALID"
            ).as_posix()
            for item in paths
        ]
        if normalized_paths != sorted(set(normalized_paths)):
            raise RetrievalError("RETRIEVAL_SELECTION_PATH_ORDER_INVALID")
        if mode == "all_manifest_entries" and normalized_paths:
            raise RetrievalError("RETRIEVAL_ALL_SELECTION_MUST_NOT_LIST_PATHS")
        if mode == "exact_manifest_paths" and not normalized_paths:
            raise RetrievalError("RETRIEVAL_EXACT_SELECTION_PATHS_MISSING")
        normalized.append(
            {
                "selection_id": selection_id,
                "mode": mode,
                "manifest_paths": normalized_paths,
                "purpose": _require_text(
                    row["purpose"],
                    code="RETRIEVAL_SELECTION_PURPOSE_INVALID",
                ),
            }
        )
    if [row["selection_id"] for row in normalized] != sorted(
        {row["selection_id"] for row in normalized}
    ):
        raise RetrievalError("RETRIEVAL_SELECTION_ORDER_INVALID")
    return normalized


def _load_policy_card_metadata(
    repo_root: Path,
    policy: dict[str, Any],
    policy_rows: Sequence[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, PurePosixPath],
    tuple[FileSnapshot, ...],
]:
    cards: dict[str, dict[str, Any]] = {}
    pointers: dict[str, dict[str, Any]] = {}
    card_paths: dict[str, PurePosixPath] = {}
    snapshots: list[FileSnapshot] = []
    for row in policy_rows:
        current_card_id = row["card_id"]
        result_ref = row["result_card_ref"]
        card, card_snapshot, card_relative = _load_repo_json(
            repo_root,
            result_ref["path"],
            expected_sha256=result_ref["sha256"],
            code="RESULT_CARD",
        )
        _validate_card(card, expected_card_id=current_card_id)

        pointer_ref = _validate_repo_ref(
            card["pointer_ref"],
            code="RESULT_CARD_POINTER_REF",
        )
        pointer_relative = _safe_relative_path(
            pointer_ref["path"],
            code="EXTERNAL_POINTER_PATH_INVALID",
        )
        if pointer_relative != card_relative.parent / "external_pointer.json":
            raise RetrievalError("EXTERNAL_POINTER_LOCATION_INVALID")
        pointer, pointer_snapshot, _ = _load_repo_json(
            repo_root,
            pointer_ref["path"],
            expected_sha256=pointer_ref["sha256"],
            code="EXTERNAL_POINTER",
        )
        _validate_pointer(
            pointer,
            card_id=current_card_id,
            registry_id=policy["registry_id"],
            validation_policy_id=policy["validation_policy_id"],
        )
        profile_ref = _validate_repo_ref(
            pointer["retrieval_profile_ref"],
            code="EXTERNAL_POINTER_PROFILE_REF",
        )
        profile_relative = _safe_relative_path(
            profile_ref["path"],
            code="RETRIEVAL_PROFILE_PATH_INVALID",
        )
        if profile_relative != card_relative.parent / "retrieval_profile.json":
            raise RetrievalError("RETRIEVAL_PROFILE_LOCATION_INVALID")
        cards[current_card_id] = card
        pointers[current_card_id] = pointer
        card_paths[current_card_id] = card_relative
        snapshots.extend((card_snapshot, pointer_snapshot))

    artifact_ids = [pointers[row["card_id"]]["artifact_id"] for row in policy_rows]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise RetrievalError("RETRIEVAL_POLICY_ARTIFACT_ID_DUPLICATE")
    for current_card_id, card in cards.items():
        for prior in card["relations"]["supersedes_card_ids"]:
            if (
                prior not in cards
                or current_card_id
                not in cards[prior]["relations"]["superseded_by_card_ids"]
            ):
                raise RetrievalError("RESULT_CARD_RELATION_NOT_RECIPROCAL")
        for later in card["relations"]["superseded_by_card_ids"]:
            if (
                later not in cards
                or current_card_id
                not in cards[later]["relations"]["supersedes_card_ids"]
            ):
                raise RetrievalError("RESULT_CARD_RELATION_NOT_RECIPROCAL")
    return cards, pointers, card_paths, tuple(snapshots)


def load_card_chain(repo_root: Path, card_id: str) -> CardChain:
    """Load only repository metadata; do not touch any external root."""

    card_id = _require_id(card_id, code="CARD_ID_INVALID")
    policy, policy_snapshot, _ = _load_repo_json(
        repo_root,
        RETRIEVAL_POLICY_RELATIVE,
        code="RETRIEVAL_POLICY",
    )
    policy_rows = _validate_policy(policy)
    by_id = {row["card_id"]: row for row in policy_rows}
    policy_row = by_id.get(card_id)
    if policy_row is None:
        raise RetrievalError("CARD_NOT_ALLOWED", card_id)
    cards, pointers, card_paths, metadata_snapshots = _load_policy_card_metadata(
        repo_root,
        policy,
        policy_rows,
    )
    card = cards[card_id]
    pointer = pointers[card_id]
    card_relative = card_paths[card_id]

    profile_ref = _validate_repo_ref(
        pointer["retrieval_profile_ref"],
        code="EXTERNAL_POINTER_PROFILE_REF",
    )
    profile_relative = _safe_relative_path(
        profile_ref["path"],
        code="RETRIEVAL_PROFILE_PATH_INVALID",
    )
    expected_profile_relative = card_relative.parent / "retrieval_profile.json"
    if profile_relative != expected_profile_relative:
        raise RetrievalError("RETRIEVAL_PROFILE_LOCATION_INVALID")
    profile, profile_snapshot, profile_relative = _load_repo_json(
        repo_root,
        profile_ref["path"],
        expected_sha256=profile_ref["sha256"],
        code="RETRIEVAL_PROFILE",
    )
    selections = _validate_profile(profile, artifact_id=pointer["artifact_id"])
    if [row["selection_id"] for row in selections] != policy_row[
        "allowed_selection_ids"
    ]:
        raise RetrievalError("RETRIEVAL_SELECTION_ALLOWLIST_MISMATCH")

    snapshots: list[FileSnapshot] = [
        policy_snapshot,
        *metadata_snapshots,
        profile_snapshot,
    ]
    for ref_value in card["consumer_closure"]["evidence_refs"]:
        ref = _validate_repo_ref(ref_value, code="RESULT_CARD_EVIDENCE_REF")
        _, snapshot, _ = _read_repo_file(
            repo_root,
            ref["path"],
            expected_sha256=ref["sha256"],
            code="RESULT_CARD_EVIDENCE",
        )
        snapshots.append(snapshot)
    return CardChain(
        policy=policy,
        policy_row=policy_row,
        card=card,
        pointer=pointer,
        profile=profile,
        snapshots=tuple(snapshots),
    )


def _validate_registry(registry: dict[str, Any], *, expected_registry_id: str) -> None:
    if registry.get("schema_version") != "artifact-storage-v1":
        raise RetrievalError("REGISTRY_VERSION_INVALID")
    if registry.get("registry_id") != expected_registry_id:
        raise RetrievalError("REGISTRY_ID_MISMATCH")
    authority = registry.get("authority")
    limits = registry.get("capability_limits")
    if (
        not isinstance(authority, dict)
        or authority.get("may_authorize_migration") is not False
        or authority.get("may_authorize_deletion") is not False
        or not isinstance(limits, dict)
        or limits.get("write") is not False
        or limits.get("move") is not False
        or limits.get("delete") is not False
    ):
        raise RetrievalError("REGISTRY_BOUNDARY_INVALID")
    roots = registry.get("storage_roots")
    objects = registry.get("objects")
    if not isinstance(roots, list) or not isinstance(objects, list):
        raise RetrievalError("REGISTRY_COLLECTIONS_INVALID")
    root_ids = [
        row.get("root_id")
        for row in roots
        if isinstance(row, dict) and isinstance(row.get("root_id"), str)
    ]
    object_ids = [
        row.get("artifact_id")
        for row in objects
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    ]
    if len(root_ids) != len(roots) or len(root_ids) != len(set(root_ids)):
        raise RetrievalError("REGISTRY_ROOT_IDS_INVALID")
    if len(object_ids) != len(objects) or len(object_ids) != len(set(object_ids)):
        raise RetrievalError("REGISTRY_OBJECT_IDS_INVALID")


def _validate_validation_policy(
    policy: dict[str, Any],
    *,
    expected_policy_id: str,
    expected_registry_id: str,
) -> list[dict[str, Any]]:
    if policy.get("contract_version") != "external-payload-validation-policy-v1":
        raise RetrievalError("VALIDATION_POLICY_VERSION_INVALID")
    if policy.get("policy_id") != expected_policy_id:
        raise RetrievalError("VALIDATION_POLICY_ID_MISMATCH")
    if policy.get("registry_id") != expected_registry_id:
        raise RetrievalError("VALIDATION_POLICY_REGISTRY_MISMATCH")
    authority = policy.get("authority")
    if (
        not isinstance(authority, dict)
        or authority.get("may_discover_targets") is not False
        or authority.get("may_move") is not False
        or authority.get("may_delete") is not False
        or authority.get("may_activate_hard_limit") is not False
    ):
        raise RetrievalError("VALIDATION_POLICY_BOUNDARY_INVALID")
    targets = policy.get("targets")
    if not isinstance(targets, list):
        raise RetrievalError("VALIDATION_POLICY_TARGETS_INVALID")
    target_ids = [row.get("artifact_id") for row in targets if isinstance(row, dict)]
    if target_ids != sorted(set(target_ids)):
        raise RetrievalError("VALIDATION_POLICY_TARGET_ORDER_INVALID")
    return targets


def _resolve_external_root(
    repo_root: Path,
    registry: dict[str, Any],
    root_id: str = EXTERNAL_ROOT_ID,
) -> tuple[Path, dict[str, Any]]:
    roots = registry.get("storage_roots")
    if not isinstance(roots, list):
        raise RetrievalError("REGISTRY_ROOTS_INVALID")
    by_id = {
        row.get("root_id"): row
        for row in roots
        if isinstance(row, dict) and isinstance(row.get("root_id"), str)
    }
    row = by_id.get(root_id)
    if row is None:
        raise RetrievalError("EXTERNAL_ROOT_NOT_REGISTERED")
    if row.get("role") != "external_archive" or row.get("required") is not True:
        raise RetrievalError("EXTERNAL_ROOT_LOCATOR_INVALID")
    try:
        root = inventory.resolve_storage_root(repo_root, row)
    except inventory.InventoryError as exc:
        raise RetrievalError("EXTERNAL_ROOT_LOCATOR_INVALID", exc.detail) from exc
    return root, row


def _manifest_entries(
    manifest: dict[str, Any],
    *,
    target: dict[str, Any],
    object_row: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    manifest_info = object_row.get("manifest")
    if not isinstance(manifest_info, dict):
        raise RetrievalError("OBJECT_MANIFEST_MISSING")
    entries_field = manifest_info.get("entries_field")
    path_field = manifest_info.get("entry_path_field")
    sha_field = manifest_info.get("entry_sha256_field")
    size_field = target.get("entry_size_field")
    total_files_field = target.get("manifest_total_files_field")
    total_bytes_field = target.get("manifest_total_bytes_field")
    if not all(
        isinstance(value, str) and value
        for value in (
            entries_field,
            path_field,
            sha_field,
            size_field,
            total_files_field,
            total_bytes_field,
        )
    ):
        raise RetrievalError("MANIFEST_FIELD_BINDING_INVALID")
    values = manifest.get(entries_field)
    if not isinstance(values, list) or not values:
        raise RetrievalError("MANIFEST_ENTRIES_INVALID")

    normalized: list[dict[str, Any]] = []
    casefold_paths: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            raise RetrievalError("MANIFEST_ENTRY_INVALID")
        path = _safe_relative_path(
            value.get(path_field),
            code="MANIFEST_ENTRY_PATH_INVALID",
        ).as_posix()
        folded = path.casefold()
        if folded in casefold_paths:
            raise RetrievalError("MANIFEST_ENTRY_PATH_COLLISION", path)
        casefold_paths.add(folded)
        size = value.get(size_field)
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise RetrievalError("MANIFEST_ENTRY_SIZE_INVALID", path)
        digest = _require_sha(
            value.get(sha_field),
            code="MANIFEST_ENTRY_SHA_INVALID",
        )
        normalized.append({"path": path, "bytes": size, "sha256": digest})
    paths = [row["path"] for row in normalized]
    if paths != sorted(paths):
        raise RetrievalError("MANIFEST_ENTRY_ORDER_INVALID")
    expected_count = manifest.get(total_files_field)
    expected_bytes = manifest.get(total_bytes_field)
    if expected_count != len(normalized):
        raise RetrievalError("MANIFEST_TOTAL_FILES_MISMATCH")
    if expected_bytes != sum(row["bytes"] for row in normalized):
        raise RetrievalError("MANIFEST_TOTAL_BYTES_MISMATCH")
    if manifest_info.get("expected_entry_count") != len(normalized):
        raise RetrievalError("REGISTRY_MANIFEST_COUNT_MISMATCH")
    return tuple(normalized)


def resolve_context(repo_root: Path, card_id: str) -> ResolvedContext:
    """Resolve one approved card through one registered external MANIFEST."""

    chain = load_card_chain(repo_root, card_id)
    registry, registry_snapshot, _ = _load_repo_json(
        repo_root,
        REGISTRY_RELATIVE,
        code="EXTERNAL_REGISTRY",
    )
    _validate_registry(
        registry,
        expected_registry_id=chain.policy["registry_id"],
    )
    validation_policy, validation_snapshot, _ = _load_repo_json(
        repo_root,
        VALIDATION_POLICY_RELATIVE,
        code="VALIDATION_POLICY",
    )
    targets = _validate_validation_policy(
        validation_policy,
        expected_policy_id=chain.policy["validation_policy_id"],
        expected_registry_id=chain.policy["registry_id"],
    )

    artifact_id = chain.pointer["artifact_id"]
    objects = registry.get("objects")
    if not isinstance(objects, list):
        raise RetrievalError("REGISTRY_OBJECTS_INVALID")
    object_by_id = {
        row.get("artifact_id"): row
        for row in objects
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    }
    object_row = object_by_id.get(artifact_id)
    if object_row is None:
        raise RetrievalError("ARTIFACT_NOT_REGISTERED", artifact_id)
    root_by_id = {
        row.get("root_id"): row
        for row in registry.get("storage_roots", [])
        if isinstance(row, dict)
    }
    if (
        object_row.get("root_id") not in root_by_id
        or root_by_id[object_row["root_id"]].get("role") != "external_archive"
        or
        object_row.get("externalization") != "already_external"
        or object_row.get("consumer_closure") != "verified"
    ):
        raise RetrievalError("ARTIFACT_NOT_RETRIEVAL_ELIGIBLE", artifact_id)
    target_by_id = {
        row.get("artifact_id"): row
        for row in targets
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    }
    target = target_by_id.get(artifact_id)
    if target is None:
        raise RetrievalError("ARTIFACT_NOT_PAYLOAD_VALIDATION_TARGET", artifact_id)

    manifest_info = object_row.get("manifest")
    if not isinstance(manifest_info, dict):
        raise RetrievalError("ARTIFACT_MANIFEST_MISSING")
    expected_manifest_sha = chain.pointer["expected_manifest_sha256"]
    if (
        manifest_info.get("sha256") != expected_manifest_sha
        or target.get("manifest_sha256") != expected_manifest_sha
        or target.get("exact_file_set") is not True
    ):
        raise RetrievalError("ARTIFACT_MANIFEST_BINDING_MISMATCH")

    external_root, _ = _resolve_external_root(
        repo_root,
        registry,
        object_row["root_id"],
    )
    artifact_relative = _safe_relative_path(
        object_row.get("relative_path"),
        code="ARTIFACT_RELATIVE_PATH_INVALID",
    )
    manifest_relative = _safe_relative_path(
        manifest_info.get("relative_path"),
        code="ARTIFACT_MANIFEST_PATH_INVALID",
    )
    if manifest_relative != PurePosixPath("MANIFEST.json"):
        raise RetrievalError("ARTIFACT_MANIFEST_PATH_NOT_FIXED")
    combined_manifest = artifact_relative / manifest_relative
    manifest_bytes, manifest_snapshot, _ = _read_beneath_root(
        external_root,
        combined_manifest.as_posix(),
        max_bytes=MANIFEST_MAX_BYTES,
        code="ARTIFACT_MANIFEST",
    )
    if manifest_snapshot.sha256 != expected_manifest_sha:
        raise RetrievalError("ARTIFACT_MANIFEST_SHA_MISMATCH")
    manifest = _load_json_bytes(manifest_bytes, code="ARTIFACT_MANIFEST")
    entries = _manifest_entries(
        manifest,
        target=target,
        object_row=object_row,
    )
    return ResolvedContext(
        chain=chain,
        registry=registry,
        validation_policy=validation_policy,
        object_row=object_row,
        validation_target=target,
        manifest=manifest,
        manifest_entries=entries,
        snapshots=(
            *chain.snapshots,
            registry_snapshot,
            validation_snapshot,
            manifest_snapshot,
        ),
    )


def _verify_snapshots_unchanged(snapshots: Sequence[FileSnapshot]) -> None:
    for snapshot in snapshots:
        _, current, _ = _read_beneath_root(
            snapshot.root,
            snapshot.relative.as_posix(),
            max_bytes=snapshot.max_bytes,
            code="INPUT_RECHECK",
        )
        if current != snapshot:
            raise RetrievalError("INPUT_DRIFT_DURING_RESOLUTION", str(snapshot.path))


def _selection(profile: dict[str, Any], selection_id: str) -> dict[str, Any]:
    selection_id = _require_id(selection_id, code="SELECTION_ID_INVALID")
    selections = _validate_profile(profile, artifact_id=profile["artifact_id"])
    by_id = {row["selection_id"]: row for row in selections}
    value = by_id.get(selection_id)
    if value is None:
        raise RetrievalError("SELECTION_NOT_FOUND", selection_id)
    return value


def build_plan(
    repo_root: Path,
    card_id: str,
    selection_id: str,
) -> dict[str, Any]:
    context = resolve_context(repo_root, card_id)
    if selection_id not in context.chain.policy_row["allowed_selection_ids"]:
        raise RetrievalError("SELECTION_NOT_ALLOWED", selection_id)
    selection = _selection(context.chain.profile, selection_id)
    by_path = {row["path"]: row for row in context.manifest_entries}
    if selection["mode"] == "all_manifest_entries":
        selected = list(context.manifest_entries)
    else:
        missing = [path for path in selection["manifest_paths"] if path not in by_path]
        if missing:
            raise RetrievalError("SELECTION_PATH_NOT_IN_MANIFEST", missing[0])
        selected = [by_path[path] for path in selection["manifest_paths"]]
    if not selected:
        raise RetrievalError("SELECTION_EMPTY")

    destination_root = context.chain.profile["destination"]["relative_root"]
    payload_root = _safe_relative_path(
        context.validation_target["payload_root_relative_path"],
        code="PAYLOAD_ROOT_RELATIVE_PATH_INVALID",
    ).as_posix()
    items = [
        {
            "source_manifest_path": row["path"],
            "destination": (
                PurePosixPath(destination_root) / PurePosixPath(row["path"])
            ).as_posix(),
            "bytes": row["bytes"],
            "sha256": row["sha256"],
        }
        for row in selected
    ]
    items_sha = _sha256_bytes(_canonical_json_bytes(items))
    resolver_bytes, resolver_snapshot, _ = _read_repo_file(
        repo_root,
        RESOLVER_RELATIVE,
        code="RESOLVER",
    )
    all_snapshots = (*context.snapshots, resolver_snapshot)
    plan = {
        "contract_version": "artifact-retrieval-plan-v1",
        "plan_id": (f"{card_id}-{selection_id}-{items_sha[:12]}"),
        "card_id": card_id,
        "experiment_id": context.chain.card["experiment_id"],
        "pointer_id": context.chain.pointer["pointer_id"],
        "artifact_id": context.chain.pointer["artifact_id"],
        "selection_id": selection_id,
        "operation": "copy",
        "source": {
            "registry_id": context.chain.policy["registry_id"],
            "root_id": context.object_row["root_id"],
            "artifact_relative_path": context.object_row["relative_path"],
            "payload_root_relative_path": payload_root,
            "manifest_sha256": context.chain.pointer["expected_manifest_sha256"],
        },
        "destination": {
            "root_id": TEST_WORKSPACE_ROOT_ID,
            "fresh_workspace_required": True,
            "no_overwrite": True,
        },
        "items": items,
        "summary": {
            "file_count": len(items),
            "total_bytes": sum(row["bytes"] for row in items),
            "items_sha256": items_sha,
        },
        "bindings": {
            "registry_sha256": next(
                row.sha256
                for row in all_snapshots
                if row.path == repo_root / REGISTRY_RELATIVE
            ),
            "validation_policy_sha256": next(
                row.sha256
                for row in all_snapshots
                if row.path == repo_root / VALIDATION_POLICY_RELATIVE
            ),
            "retrieval_policy_sha256": next(
                row.sha256
                for row in all_snapshots
                if row.path == repo_root / RETRIEVAL_POLICY_RELATIVE
            ),
            "result_card_sha256": context.chain.policy_row["result_card_ref"]["sha256"],
            "pointer_sha256": context.chain.card["pointer_ref"]["sha256"],
            "retrieval_profile_sha256": context.chain.pointer["retrieval_profile_ref"][
                "sha256"
            ],
            "resolver_sha256": _sha256_bytes(resolver_bytes),
        },
        "claims": {
            "manifest_resolved": True,
            "payload_bytes_revalidated": False,
            "copy_performed": False,
            "move_performed": False,
            "delete_performed": False,
            "migration_complete": False,
            "hard_limit_activated": False,
        },
        "boundary": (
            "本计划只把已钉住的 MANIFEST 项翻译成未来复制清单；"
            "S-06-C 没有读取 payload 字节、创建工作区、复制、移动、删除或恢复。"
        ),
    }
    _verify_snapshots_unchanged(all_snapshots)
    return plan


def render_card_markdown(repo_root: Path, card_id: str) -> str:
    """Render the human view without resolving or reading any external root."""

    chain = load_card_chain(repo_root, card_id)
    selections = _validate_profile(
        chain.profile,
        artifact_id=chain.pointer["artifact_id"],
    )
    verdict_labels = {
        "passed": "通过",
        "failed": "失败",
        "negative_result": "负结果",
        "mixed": "混合",
        "not_evaluated": "未评估",
    }
    terminal_labels = {
        "completed": "已完成",
        "negative_result": "负结果停点",
        "hard_stopped": "硬停",
        "superseded": "已被后续版本替代",
        "retired": "已退役",
    }
    lines = [
        f"# {chain.card['title']}｜轻量结论卡",
        "",
        "> 本页由同目录 `result_card.json`、`external_pointer.json` 和",
        "> `retrieval_profile.json` 确定性生成；这张卡自身的机器真源只认这三份 JSON，请勿手改本页。",
        "",
        "## 一眼看懂",
        "",
        f"- 实验编号：`{chain.card['experiment_id']}`",
        f"- 当前停点：{terminal_labels[chain.card['terminal_status']]}",
        f"- 质量裁决：{verdict_labels[chain.card['quality_verdict']]}",
        f"- 仓外对象：`{chain.pointer['artifact_id']}`",
        f"- 固定清单 SHA：`{chain.pointer['expected_manifest_sha256']}`",
        "",
        "## 这次想验证什么",
        "",
        chain.card["purpose"],
        "",
        "## 怎么组装",
        "",
    ]
    lines.extend(f"- {item}" for item in chain.card["assembly_summary"])
    lines.extend(["", "## 结论", ""])
    lines.extend(f"- {item}" for item in chain.card["short_conclusion"])
    lines.extend(
        [
            "",
            "## 这张结论不能说明什么",
            "",
            chain.card["evidence_boundary"],
            "",
            "## 以后怎么取件",
            "",
            "日常只读本页。确实要复现时，先核卡片和仓外清单：",
            "",
            "```bash",
            "uv run --locked python tools/experiment_artifact_retrieval.py "
            f"check --card-id {card_id}",
            "```",
            "",
            "再按已登记组合生成复制计划。这个命令只输出 JSON，不会创建目录或复制文件：",
            "",
        ]
    )
    for selection in selections:
        lines.extend(
            [
                "```bash",
                (
                    "uv run --locked python tools/experiment_artifact_retrieval.py "
                    f"resolve --card-id {card_id} "
                    f"--selection-id {selection['selection_id']}"
                ),
                "```",
                "",
                f"- `{selection['selection_id']}`：{selection['purpose']}",
                "",
            ]
        )
    lines.extend(
        [
            "真正复制仍要等后续单独施工；当前没有复制子命令。",
            "",
            "## 使用边界",
            "",
            chain.card["boundary"],
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def _check_readme(repo_root: Path, card_id: str, chain: CardChain) -> None:
    card_relative = _safe_relative_path(
        chain.policy_row["result_card_ref"]["path"],
        code="RESULT_CARD_PATH_INVALID",
    )
    readme_relative = card_relative.parent / "README.md"
    readme_bytes, _, _ = _read_repo_file(
        repo_root,
        readme_relative.as_posix(),
        code="RESULT_CARD_README",
    )
    expected = render_card_markdown(repo_root, card_id).encode("utf-8")
    if readme_bytes != expected:
        raise RetrievalError("RESULT_CARD_README_DRIFT", readme_relative.as_posix())


def check_card(repo_root: Path, card_id: str) -> ResolvedContext:
    context = resolve_context(repo_root, card_id)
    _check_readme(repo_root, card_id, context.chain)
    _verify_snapshots_unchanged(context.snapshots)
    return context


def restore_registered_archive(
    repo_root: Path,
    artifact_id: str,
    destination: Path,
) -> dict[str, Any]:
    """Restore one registered tar archive into one fresh TEMP destination."""

    if destination.exists():
        raise RetrievalError("RESTORE_DESTINATION_EXISTS", str(destination))
    temp_root = repo_root / "TEMP"
    temp_root.mkdir(exist_ok=True)
    try:
        relative_destination = destination.resolve(strict=False).relative_to(
            temp_root.resolve(strict=True)
        )
    except ValueError as exc:
        raise RetrievalError(
            "RESTORE_DESTINATION_OUTSIDE_TEMP",
            str(destination),
        ) from exc
    if not relative_destination.parts:
        raise RetrievalError("RESTORE_DESTINATION_OUTSIDE_TEMP")

    registry, registry_snapshot, _ = _load_repo_json(
        repo_root,
        REGISTRY_RELATIVE,
        code="EXTERNAL_REGISTRY",
    )
    _validate_registry(registry, expected_registry_id=registry["registry_id"])
    objects = {
        row.get("artifact_id"): row
        for row in registry.get("objects", [])
        if isinstance(row, dict)
    }
    object_row = objects.get(artifact_id)
    if object_row is None:
        raise RetrievalError("ARTIFACT_NOT_REGISTERED", artifact_id)
    representation = object_row.get("representation")
    manifest_info = object_row.get("manifest")
    if (
        not isinstance(representation, dict)
        or representation.get("kind") != "tar_posix_tree_v1"
        or not isinstance(manifest_info, dict)
    ):
        raise RetrievalError("ARTIFACT_NOT_TAR_RESTORABLE", artifact_id)
    root, _ = _resolve_external_root(repo_root, registry, object_row["root_id"])
    object_relative = _safe_relative_path(
        object_row["relative_path"], code="ARTIFACT_RELATIVE_PATH_INVALID"
    )
    manifest_relative = _safe_relative_path(
        manifest_info["relative_path"], code="ARTIFACT_MANIFEST_PATH_INVALID"
    )
    manifest_bytes, manifest_snapshot, _ = _read_beneath_root(
        root,
        (object_relative / manifest_relative).as_posix(),
        max_bytes=MANIFEST_MAX_BYTES,
        code="ARTIFACT_MANIFEST",
    )
    if _sha256_bytes(manifest_bytes) != manifest_info["sha256"]:
        raise RetrievalError("ARTIFACT_MANIFEST_SHA_MISMATCH")
    manifest = _load_json_bytes(manifest_bytes, code="ARTIFACT_MANIFEST")
    if (
        representation["original_tree_manifest_sha256"] != manifest_info["sha256"]
        or representation["original_aggregate_sha256"]
        != manifest.get("aggregate_sha256")
    ):
        raise RetrievalError("ARTIFACT_REPRESENTATION_BINDING_MISMATCH")
    container_relative = _safe_relative_path(
        representation["container_relative_path"],
        code="ARTIFACT_CONTAINER_PATH_INVALID",
    )
    container = root.joinpath(
        *object_relative.parts,
        *container_relative.parts,
    )
    try:
        container_info = container.lstat()
    except FileNotFoundError as exc:
        raise RetrievalError("ARTIFACT_CONTAINER_MISSING") from exc
    if not stat.S_ISREG(container_info.st_mode) or container_info.st_nlink != 1:
        raise RetrievalError("ARTIFACT_CONTAINER_INVALID")
    if container_info.st_size != representation["container_bytes"]:
        raise RetrievalError("ARTIFACT_CONTAINER_SIZE_MISMATCH")
    if _sha256_file(container) != representation["container_sha256"]:
        raise RetrievalError("ARTIFACT_CONTAINER_SHA_MISMATCH")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        with tarfile.open(container, mode="r:") as archive:
            seen: set[str] = set()
            for member in archive:
                relative = _safe_tar_member_name(member.name)
                name = relative.as_posix()
                if member.isdir():
                    continue
                if name.casefold() in seen:
                    raise RetrievalError("TAR_MEMBER_PATH_COLLISION", name)
                seen.add(name.casefold())
                target = staging.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                if member.isfile():
                    source = archive.extractfile(member)
                    if source is None:
                        raise RetrievalError("TAR_MEMBER_READ_FAILED", name)
                    with target.open("xb") as handle:
                        shutil.copyfileobj(source, handle, length=8 * 1024 * 1024)
                elif member.issym():
                    if not _symlink_target_stays_within_tree(relative, member.linkname):
                        raise RetrievalError("TAR_SYMLINK_TARGET_UNSAFE", name)
                    target.symlink_to(member.linkname)
                else:
                    raise RetrievalError("TAR_MEMBER_TYPE_INVALID", name)
        summary = _verify_restored_tree(staging, manifest)
        if destination.exists():
            raise RetrievalError("RESTORE_DESTINATION_EXISTS", str(destination))
        staging.rename(destination)
        _verify_snapshots_unchanged((registry_snapshot, manifest_snapshot))
        return {
            "artifact_id": artifact_id,
            "root_id": object_row["root_id"],
            "representation": "tar_posix_tree_v1",
            "container_sha256": representation["container_sha256"],
            "manifest_sha256": manifest_info["sha256"],
            **summary,
            "restore_target": destination.relative_to(repo_root).as_posix(),
            "status": "RESTORE_VERIFIED",
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读核对实验轻量结论卡，并生成按需复制计划。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="核对一张获准结论卡、指针和外置 MANIFEST，不读取 payload。",
    )
    check_parser.add_argument("--card-id", required=True)

    resolve_parser = subparsers.add_parser(
        "resolve",
        help="把一个已登记取件组合解析成确定性复制计划；只写标准输出。",
    )
    resolve_parser.add_argument("--card-id", required=True)
    resolve_parser.add_argument("--selection-id", required=True)

    render_parser = subparsers.add_parser(
        "render",
        help="只从仓内机器真源渲染结论卡 Markdown；不读取仓外根。",
    )
    render_parser.add_argument("--card-id", required=True)
    restore_parser = subparsers.add_parser(
        "restore-archive",
        help="按登记的 UUID 与 tar 表示恢复一个对象到新的 TEMP 目录。",
    )
    restore_parser.add_argument("--artifact-id", required=True)
    restore_parser.add_argument("--destination", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            context = check_card(ROOT, args.card_id)
            print(
                "PASS: "
                f"{args.card_id} 已解析到 {context.chain.pointer['artifact_id']}；"
                f"固定清单 {len(context.manifest_entries)} 项；"
                "未读取 payload、未复制、未移动、未删除。"
            )
            return 0
        if args.command == "resolve":
            plan = build_plan(ROOT, args.card_id, args.selection_id)
            print(_canonical_json_bytes(plan).decode("utf-8"))
            return 0
        if args.command == "render":
            sys.stdout.write(render_card_markdown(ROOT, args.card_id))
            return 0
        if args.command == "restore-archive":
            destination = Path(args.destination)
            if not destination.is_absolute():
                destination = ROOT / destination
            result = restore_registered_archive(ROOT, args.artifact_id, destination)
            print(_canonical_json_bytes(result).decode("utf-8"))
            return 0
        parser.error("unknown command")
    except RetrievalError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
