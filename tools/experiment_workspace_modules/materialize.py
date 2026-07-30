from __future__ import annotations

import ctypes
import errno
import os
import stat
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import (
    ALLOWLIST_CONTRACT_ID,
    CAPABILITY_LIMITS,
    ContractError,
    MaterializeItem,
    MaterializePlan,
    bundle_source_paths,
    canonical_json_bytes,
    canonical_json_sha256,
    is_repo_relative_path,
    load_json_object,
    parse_plan,
    sha256_bytes,
)
from .security import (
    SENSITIVE_RULE_IDS,
    FileSnapshot,
    SecurityError,
    open_directory,
    open_directory_at,
    open_directory_chain,
    read_regular_file,
    sensitive_rule_for,
    write_new_file_at,
)


PLAN_ROOTS = ("experiments", "tests/fixtures/experiment_workspace")
S0_RECEIPT_WAVE_ID = "S0_MATERIALIZE_ONLY"
S0_RECEIPT_CONTRACT = "repository-restructure-wave-receipt-v1"
S0_WAVE_PLAN_CONTRACT = "repository-restructure-wave-plan-v1"
S0_REQUIRED_CHECK_IDS = {
    "baseline_receipt_current",
    "bound_input_sha",
    "candidate_write_paths_disjoint_from_dirty",
    "conflict_lock_active",
    "decision_ticket_exact",
    "governance_generated_green",
    "head_frozen",
    "live_snapshot_stable",
    "read_allowlist_complete",
    "responsibility_window_time",
    "test_impact_complete",
    "wave_dependencies_satisfied",
    "wave_scope_exact",
}
S0_ELIGIBLE_WRITE_PATHS = [
    "tools/experiment_workspace.py",
    "tools/experiment_workspace_modules",
    "tests/test_experiment_workspace.py",
    "tests/test_experiment_workspace_security.py",
    "tests/fixtures/experiment_workspace",
    "tools/README.md",
    "tests/README.md",
    "governance/tool_registry.json",
    "governance/test_policy.json",
]
S0_RECEIPT_TOP_LEVEL_KEYS = {
    "authorization_boundary",
    "blockers",
    "checks",
    "contract_version",
    "evaluated_at",
    "evidence_snapshot",
    "head_sha",
    "plan_content_sha256",
    "plan_id",
    "responsibility_window",
    "route",
    "runtime_effects",
    "status",
    "wave_id",
}
S0_BOUNDARY_KEYS = {
    "authorization_context_claim_is_cryptographic_proof",
    "authorizes_delete",
    "authorizes_external_removal",
    "authorizes_model_api",
    "authorizes_notion_write",
    "authorizes_physical_move",
    "authorizes_preflight",
    "authorizes_wave",
    "eligible_wave_id",
    "eligible_write_paths",
    "mechanical_preconditions_pass",
    "requires_same_task_human_readback",
}


class MaterializeError(RuntimeError):
    def __init__(self, code: str, path: str | None = None):
        super().__init__(code)
        self.code = code
        self.path = path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_within(relative: str, roots: tuple[str, ...]) -> bool:
    return any(relative == root or relative.startswith(f"{root}/") for root in roots)


def _translate_security_error(exc: SecurityError) -> MaterializeError:
    return MaterializeError(exc.code, exc.path)


def _read_git_head(repo_root: Path) -> str:
    git_marker = repo_root / ".git"
    if git_marker.is_file():
        raise MaterializeError("GIT_WORKTREE_METADATA_UNSUPPORTED")
    if not git_marker.is_dir() or git_marker.is_symlink():
        raise MaterializeError("GIT_METADATA_MISSING")

    try:
        head = read_regular_file(repo_root, ".git/HEAD").data.decode("ascii").strip()
    except (SecurityError, UnicodeDecodeError) as exc:
        raise MaterializeError("GIT_METADATA_INVALID") from exc
    if not head.startswith("ref: "):
        return head
    reference = head.removeprefix("ref: ")
    if not is_repo_relative_path(reference):
        raise MaterializeError("GIT_REFERENCE_INVALID")
    try:
        return (
            read_regular_file(repo_root / ".git", reference)
            .data.decode("ascii")
            .strip()
        )
    except SecurityError:
        pass

    try:
        packed = read_regular_file(repo_root, ".git/packed-refs").data.decode("ascii")
    except (SecurityError, UnicodeDecodeError) as exc:
        raise MaterializeError("GIT_HEAD_UNRESOLVED") from exc
    for line in packed.splitlines():
        if line.startswith(("#", "^")):
            continue
        digest, _, name = line.partition(" ")
        if name == reference:
            return digest
    raise MaterializeError("GIT_HEAD_UNRESOLVED")


def _load_bound_json(
    repo_root: Path,
    relative: str,
    expected_sha: str,
    *,
    sha_error: str,
    json_error: str,
) -> dict[str, Any]:
    try:
        snapshot = read_regular_file(repo_root, relative)
    except SecurityError as exc:
        raise _translate_security_error(exc) from exc
    if snapshot.sha256 != expected_sha:
        raise MaterializeError(sha_error, relative)
    try:
        return load_json_object(snapshot.data, code=json_error)
    except ContractError as exc:
        raise MaterializeError(exc.code, relative) from exc


def _verify_s0_receipt(repo_root: Path, plan: MaterializePlan) -> None:
    wave_plan = _load_bound_json(
        repo_root,
        plan.s0_wave_plan_path,
        plan.s0_wave_plan_sha256,
        sha_error="S0_WAVE_PLAN_SHA256_MISMATCH",
        json_error="S0_WAVE_PLAN_JSON_INVALID",
    )
    wave_plan_content_sha = canonical_json_sha256(wave_plan)
    valid_wave_plan = (
        wave_plan.get("contract_version") == S0_WAVE_PLAN_CONTRACT
        and wave_plan.get("route") == "S0"
        and wave_plan.get("wave_id") == S0_RECEIPT_WAVE_ID
        and wave_plan.get("expected_head_sha") == plan.expected_head_sha
        and isinstance(wave_plan.get("plan_id"), str)
        and wave_plan.get("capability_limits")
        == {
            **CAPABILITY_LIMITS,
            "register_only": False,
        }
    )
    if not valid_wave_plan:
        raise MaterializeError(
            "S0_WAVE_PLAN_NOT_ELIGIBLE",
            plan.s0_wave_plan_path,
        )

    receipt = _load_bound_json(
        repo_root,
        plan.s0_receipt_path,
        plan.s0_receipt_sha256,
        sha_error="S0_RECEIPT_SHA256_MISMATCH",
        json_error="S0_RECEIPT_JSON_INVALID",
    )
    if set(receipt) != S0_RECEIPT_TOP_LEVEL_KEYS:
        raise MaterializeError("S0_RECEIPT_SHAPE_INVALID", plan.s0_receipt_path)
    boundary = receipt["authorization_boundary"]
    if not isinstance(boundary, dict) or set(boundary) != S0_BOUNDARY_KEYS:
        raise MaterializeError("S0_RECEIPT_BOUNDARY_INVALID", plan.s0_receipt_path)
    authorization_values = {
        key: value
        for key, value in boundary.items()
        if key.startswith("authorizes_")
    }
    valid_boundary = (
        authorization_values
        and all(value is False for value in authorization_values.values())
        and boundary["mechanical_preconditions_pass"] is True
        and boundary["eligible_wave_id"] == S0_RECEIPT_WAVE_ID
        and boundary["eligible_write_paths"] == S0_ELIGIBLE_WRITE_PATHS
        and boundary["requires_same_task_human_readback"] is True
        and boundary["authorization_context_claim_is_cryptographic_proof"] is False
    )
    checks = receipt["checks"]
    valid_checks = (
        isinstance(checks, list)
        and len(checks) == len(S0_REQUIRED_CHECK_IDS)
        and {row.get("check_id") for row in checks if isinstance(row, dict)}
        == S0_REQUIRED_CHECK_IDS
        and all(
            isinstance(row, dict)
            and set(row) == {"check_id", "evidence", "passed"}
            and row["passed"] is True
            and isinstance(row["evidence"], dict)
            for row in checks
        )
    )
    runtime_effects = receipt["runtime_effects"]
    valid_runtime = runtime_effects == {
        "model_api_calls": 0,
        "network_attempts": 0,
        "receipt_writes": 1,
        "tracked_repository_writes": 0,
    }
    evidence_snapshot = receipt["evidence_snapshot"]
    valid_evidence = (
        isinstance(evidence_snapshot, list)
        and bool(evidence_snapshot)
        and all(
            isinstance(row, dict)
            and set(row) == {"path", "sha256"}
            and is_repo_relative_path(row["path"])
            and isinstance(row["sha256"], str)
            and len(row["sha256"]) == 64
            for row in evidence_snapshot
        )
    )
    responsibility = receipt["responsibility_window"]
    valid_receipt = (
        receipt["contract_version"] == S0_RECEIPT_CONTRACT
        and receipt["status"] == "PASS"
        and receipt["route"] == "S0"
        and receipt["wave_id"] == S0_RECEIPT_WAVE_ID
        and receipt["head_sha"] == plan.expected_head_sha
        and receipt["plan_id"] == wave_plan["plan_id"]
        and receipt["plan_content_sha256"] == wave_plan_content_sha
        and receipt["blockers"] == []
        and isinstance(receipt["evaluated_at"], str)
        and isinstance(responsibility, dict)
        and responsibility.get("wave_id") == S0_RECEIPT_WAVE_ID
        and valid_boundary
        and valid_checks
        and valid_runtime
        and valid_evidence
    )
    if not valid_receipt:
        raise MaterializeError("S0_RECEIPT_NOT_ELIGIBLE", plan.s0_receipt_path)


def _load_plan_bytes(repo_root: Path, plan_relative: str) -> bytes:
    if not is_repo_relative_path(plan_relative) or not _is_within(
        plan_relative,
        PLAN_ROOTS,
    ):
        raise MaterializeError("PLAN_PATH_NOT_ALLOWED")
    try:
        return read_regular_file(repo_root, plan_relative).data
    except SecurityError as exc:
        raise _translate_security_error(exc) from exc


def _secure_bundle_manifest(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in bundle_source_paths(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        try:
            snapshot = read_regular_file(repo_root, relative)
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        rows.append({"path": relative, "sha256": snapshot.sha256})
    return rows


def _validate_sources(
    repo_root: Path,
    items: tuple[MaterializeItem, ...],
) -> dict[str, FileSnapshot]:
    snapshots: dict[str, FileSnapshot] = {}
    for item in items:
        try:
            snapshot = read_regular_file(repo_root, item.source)
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        if snapshot.size != item.size:
            raise MaterializeError("SOURCE_SIZE_MISMATCH", item.source)
        if snapshot.sha256 != item.sha256:
            raise MaterializeError("SOURCE_SHA256_MISMATCH", item.source)
        sensitive_rule = sensitive_rule_for(item.source, snapshot.data)
        if sensitive_rule is not None:
            raise MaterializeError(sensitive_rule, item.source)
        snapshots[item.source] = snapshot
    return snapshots


def _entry_at(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _reserve_run(runs_fd: int, run_id: str, plan_sha: str) -> tuple[str, str]:
    try:
        locks_fd = open_directory_at(runs_fd, ".locks", create=True)
    except SecurityError as exc:
        raise _translate_security_error(exc) from exc
    lock_name = f"{run_id}.lock"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    payload = {
        "contract_version": "experiment-materialize-lock-v1",
        "created_at": _utc_now(),
        "plan_sha256": plan_sha,
        "run_id": run_id,
    }
    payload_bytes = canonical_json_bytes(payload)
    try:
        try:
            descriptor = os.open(lock_name, flags, 0o600, dir_fd=locks_fd)
        except FileExistsError as exc:
            raise MaterializeError("RUN_ALREADY_RESERVED") from exc
        except OSError as exc:
            raise MaterializeError("LOCK_CREATE_REJECTED") from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(locks_fd)
        except OSError as exc:
            raise MaterializeError("LOCK_WRITE_FAILED") from exc
    finally:
        os.close(locks_fd)
    return f"runs/.locks/{lock_name}", sha256_bytes(payload_bytes)


def _aggregate(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(rows))


def _write_json_at(root_fd: int, relative: str, value: dict[str, Any]) -> None:
    try:
        write_new_file_at(root_fd, relative, canonical_json_bytes(value))
    except SecurityError as exc:
        raise _translate_security_error(exc) from exc


def _replace_json_at(root_fd: int, relative: str, value: dict[str, Any]) -> None:
    parts = tuple(relative.split("/"))
    if not parts or any(not part or part in {".", ".."} for part in parts):
        raise MaterializeError("TARGET_PATH_INVALID", relative)
    try:
        parent_fd = open_directory_chain(root_fd, parts[:-1], create=False)
    except SecurityError as exc:
        raise _translate_security_error(exc) from exc
    temporary_name = f".{parts[-1]}.{uuid.uuid4().hex}.tmp"
    try:
        try:
            write_new_file_at(
                parent_fd,
                temporary_name,
                canonical_json_bytes(value),
            )
            os.replace(
                temporary_name,
                parts[-1],
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        except (OSError, SecurityError) as exc:
            raise MaterializeError("IDENTITY_COMMIT_FAILED", relative) from exc
    finally:
        try:
            os.close(parent_fd)
        except OSError:
            pass


def _sync_directory(descriptor: int, *, code: str) -> None:
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise MaterializeError(code) from exc


def _write_rejection(
    runs_fd: int,
    *,
    run_id: str,
    plan_sha: str,
    code: str,
    path: str | None,
    staging_name: str | None,
) -> None:
    try:
        rejected_fd = open_directory_at(runs_fd, ".rejected", create=True)
    except SecurityError as exc:
        raise _translate_security_error(exc) from exc
    value: dict[str, Any] = {
        "contract_version": "experiment-materialize-rejection-v1",
        "error_code": code,
        "plan_sha256": plan_sha,
        "rejected_at": _utc_now(),
        "run_id": run_id,
        "staging_retained": staging_name is not None,
    }
    if path is not None and is_repo_relative_path(path):
        value["path"] = path
    if staging_name is not None:
        value["staging_name"] = staging_name
    try:
        _write_json_at(rejected_fd, f"{run_id}.json", value)
    finally:
        os.close(rejected_fd)


def _copy_into_staging(
    repo_root: Path,
    staging_fd: int,
    items: tuple[MaterializeItem, ...],
    snapshots: dict[str, FileSnapshot],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows: list[dict[str, Any]] = []
    workspace_rows: list[dict[str, Any]] = []
    for item in items:
        before = snapshots[item.source]
        try:
            current = read_regular_file(repo_root, item.source)
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        if current != before:
            raise MaterializeError("SOURCE_CHANGED_BEFORE_COPY", item.source)
        try:
            target = write_new_file_at(
                staging_fd,
                item.destination,
                current.data,
            )
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        if target.size != item.size or target.sha256 != item.sha256:
            raise MaterializeError("TARGET_VERIFICATION_FAILED", item.destination)
        try:
            after = read_regular_file(repo_root, item.source)
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        if after != before:
            raise MaterializeError("SOURCE_CHANGED_AFTER_COPY", item.source)

        source_rows.append(
            {
                "bytes": before.size,
                "device": before.device,
                "inode": before.inode,
                "links": before.links,
                "mtime_ns": before.mtime_ns,
                "path": item.source,
                "sha256_after": after.sha256,
                "sha256_before": before.sha256,
            }
        )
        workspace_rows.append(
            {
                "bytes": target.size,
                "path": item.destination,
                "role": item.role,
                "sha256": target.sha256,
                "source": item.source,
            }
        )
    return source_rows, workspace_rows


def _create_staging(staging_root_fd: int, run_id: str) -> tuple[str, int]:
    staging_name = f"{run_id}.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        os.mkdir(staging_name, mode=0o700, dir_fd=staging_root_fd)
        staging_fd = open_directory_at(
            staging_root_fd,
            staging_name,
            create=False,
        )
    except (OSError, SecurityError) as exc:
        raise MaterializeError("STAGING_CREATE_REJECTED") from exc
    return staging_name, staging_fd


def _atomic_publish_no_replace(
    staging_root_fd: int,
    staging_name: str,
    runs_fd: int,
    run_id: str,
) -> str:
    library = ctypes.CDLL(None, use_errno=True)
    source = os.fsencode(staging_name)
    target = os.fsencode(run_id)
    if hasattr(library, "renameatx_np"):
        function = library.renameatx_np
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        function.restype = ctypes.c_int
        result = function(staging_root_fd, source, runs_fd, target, 0x00000004)
        backend = "renameatx_np_RENAME_EXCL"
    elif hasattr(library, "renameat2"):
        function = library.renameat2
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        function.restype = ctypes.c_int
        result = function(staging_root_fd, source, runs_fd, target, 0x1)
        backend = "renameat2_RENAME_NOREPLACE"
    else:
        raise MaterializeError("ATOMIC_NOREPLACE_UNAVAILABLE")
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise MaterializeError("RUN_OUTPUT_ALREADY_EXISTS")
        raise MaterializeError("ATOMIC_PUBLISH_FAILED")
    return backend


def materialize(*, repo_root: Path, plan_relative: str) -> Path:
    repo_root = repo_root.resolve()
    plan_bytes = _load_plan_bytes(repo_root, plan_relative)
    plan_sha = sha256_bytes(plan_bytes)
    try:
        plan = parse_plan(load_json_object(plan_bytes, code="PLAN_JSON_INVALID"))
    except ContractError as exc:
        raise MaterializeError(exc.code, exc.path) from exc

    actual_head = _read_git_head(repo_root)
    if actual_head != plan.expected_head_sha:
        raise MaterializeError("GIT_HEAD_MISMATCH")
    bundle_manifest = _secure_bundle_manifest(repo_root)
    actual_bundle_sha = sha256_bytes(canonical_json_bytes(bundle_manifest))
    if actual_bundle_sha != plan.materializer_bundle_sha256:
        raise MaterializeError("MATERIALIZER_BUNDLE_SHA256_MISMATCH")
    _verify_s0_receipt(repo_root, plan)

    # 全部来源和敏感内容先验完，再创建 runs、锁或临时复制目录。
    snapshots = _validate_sources(repo_root, plan.items)
    try:
        repo_fd = open_directory(repo_root)
    except SecurityError as exc:
        raise _translate_security_error(exc) from exc
    runs_fd: int | None = None
    staging_root_fd: int | None = None
    staging_fd: int | None = None
    staging_name: str | None = None
    lock_created = False
    published = False
    try:
        try:
            runs_fd = open_directory_at(repo_fd, "runs", create=True)
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        if _entry_at(runs_fd, plan.run_id) is not None:
            raise MaterializeError("RUN_OUTPUT_ALREADY_EXISTS")
        lock_path, lock_sha = _reserve_run(runs_fd, plan.run_id, plan_sha)
        lock_created = True
        try:
            staging_root_fd = open_directory_at(
                runs_fd,
                ".staging",
                create=True,
            )
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        staging_name, staging_fd = _create_staging(
            staging_root_fd,
            plan.run_id,
        )
        staging_info = os.fstat(staging_fd)
        runs_info = os.fstat(runs_fd)
        if staging_info.st_dev != runs_info.st_dev:
            raise MaterializeError("STAGING_FILESYSTEM_MISMATCH")

        source_rows, workspace_rows = _copy_into_staging(
            repo_root,
            staging_fd,
            plan.items,
            snapshots,
        )
        created_at = _utc_now()
        source_manifest = {
            "contract_version": "experiment-source-manifest-v1",
            "files": source_rows,
            "source_aggregate_sha256": _aggregate(source_rows),
        }
        _write_json_at(
            staging_fd,
            "receipts/SOURCE_MANIFEST.json",
            source_manifest,
        )
        copy_receipt = {
            "allowlist_contract_id": ALLOWLIST_CONTRACT_ID,
            "allowlist_contract_sha256": plan.allowlist_contract_sha256,
            "capability_limits": CAPABILITY_LIMITS,
            "contract_version": "experiment-copy-receipt-v1",
            "copied_at": created_at,
            "isolation_verified": False,
            "lock_path": lock_path,
            "lock_sha256": lock_sha,
            "materializer_bundle": bundle_manifest,
            "materializer_bundle_sha256": actual_bundle_sha,
            "plan_id": plan.plan_id,
            "plan_path": plan_relative,
            "plan_sha256": plan_sha,
            "publish_contract": {
                "atomic_noreplace_required": True,
                "final_device_expected": staging_info.st_dev,
                "final_inode_expected": staging_info.st_ino,
                "same_filesystem": True,
                "staging_device": staging_info.st_dev,
                "staging_inode": staging_info.st_ino,
            },
            "revision": plan.revision,
            "run_id": plan.run_id,
            "s0_receipt_path": plan.s0_receipt_path,
            "s0_receipt_sha256": plan.s0_receipt_sha256,
            "s0_wave_plan_path": plan.s0_wave_plan_path,
            "s0_wave_plan_sha256": plan.s0_wave_plan_sha256,
            "scope": "copy_only",
            "sensitive_scan": {
                "result": "PASS",
                "rule_ids": list(SENSITIVE_RULE_IDS),
            },
            "source_aggregate_sha256": source_manifest[
                "source_aggregate_sha256"
            ],
            "workspace_aggregate_sha256": _aggregate(workspace_rows),
            "workspace_files": workspace_rows,
        }
        copy_receipt_bytes = canonical_json_bytes(copy_receipt)
        _write_json_at(
            staging_fd,
            "receipts/COPY_RECEIPT.json",
            copy_receipt,
        )
        reserved_identity = {
            "contract_version": "experiment-run-identity-v1",
            "copy_receipt_sha256": sha256_bytes(copy_receipt_bytes),
            "created_at": created_at,
            "lock_sha256": lock_sha,
            "plan_id": plan.plan_id,
            "plan_sha256": plan_sha,
            "previous_state": None,
            "revision": plan.revision,
            "run_id": plan.run_id,
            "state": "reserved",
            "workspace_aggregate_sha256": copy_receipt[
                "workspace_aggregate_sha256"
            ],
        }
        _write_json_at(staging_fd, "RUN_IDENTITY.json", reserved_identity)
        os.fsync(staging_fd)

        backend = _atomic_publish_no_replace(
            staging_root_fd,
            staging_name,
            runs_fd,
            plan.run_id,
        )
        published = True
        staging_name = None
        _sync_directory(
            runs_fd,
            code="PUBLISH_DIRECTORY_SYNC_FAILED",
        )
        final_info = _entry_at(runs_fd, plan.run_id)
        if (
            final_info is None
            or not stat.S_ISDIR(final_info.st_mode)
            or final_info.st_dev != staging_info.st_dev
            or final_info.st_ino != staging_info.st_ino
        ):
            raise MaterializeError("PUBLISHED_IDENTITY_MISMATCH")
        if backend not in {
            "renameatx_np_RENAME_EXCL",
            "renameat2_RENAME_NOREPLACE",
        }:
            raise MaterializeError("ATOMIC_PUBLISH_BACKEND_INVALID")
        try:
            final_fd = open_directory_at(
                runs_fd,
                plan.run_id,
                create=False,
            )
        except SecurityError as exc:
            raise _translate_security_error(exc) from exc
        try:
            materialized_identity = {
                **reserved_identity,
                "materialized_at": _utc_now(),
                "previous_state": "reserved",
                "publish_backend": backend,
                "state": "materialized",
            }
            _replace_json_at(
                final_fd,
                "RUN_IDENTITY.json",
                materialized_identity,
            )
            try:
                _sync_directory(
                    final_fd,
                    code="IDENTITY_DIRECTORY_SYNC_FAILED",
                )
            except MaterializeError as sync_error:
                try:
                    _replace_json_at(
                        final_fd,
                        "RUN_IDENTITY.json",
                        reserved_identity,
                    )
                    _sync_directory(
                        final_fd,
                        code="IDENTITY_ROLLBACK_SYNC_FAILED",
                    )
                except MaterializeError as rollback_error:
                    raise MaterializeError(
                        "IDENTITY_DURABILITY_UNKNOWN"
                    ) from rollback_error
                raise sync_error
        finally:
            try:
                os.close(final_fd)
            except OSError:
                pass
        return repo_root / "runs" / plan.run_id
    except (MaterializeError, SecurityError) as exc:
        code = getattr(exc, "code", "MATERIALIZE_FAILED")
        path = getattr(exc, "path", None)
        if lock_created and runs_fd is not None and not published:
            _write_rejection(
                runs_fd,
                run_id=plan.run_id,
                plan_sha=plan_sha,
                code=code,
                path=path,
                staging_name=staging_name,
            )
        if isinstance(exc, MaterializeError):
            raise
        raise MaterializeError(code, path) from exc
    finally:
        for descriptor in (staging_fd, staging_root_fd, runs_fd, repo_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
