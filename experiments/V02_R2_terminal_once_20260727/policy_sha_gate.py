from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "v02-r2-terminal-preauthorization-sha-gate.v1"
REQUEST_SCHEMA = "v02-r2-terminal-preauthorization-sha-request.v1"
POLICY_SCHEMA = "v02-r2-terminal-preauthorization-sha-policy.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_NAME = "experiments.V02_R2_terminal_once_20260727.policy_sha_gate"

RETIRED_TICKET_IDS = {
    "M3-06-R2-TERMINAL-30-REOPEN-20260727-2145",
}
RETIRED_CYCLE_IDS = {
    "review-cycle-c3f73bd3-80a7-412b-8605-be1260d52939",
}
RETIRED_RUN_IDS = {
    "V02-R2-M1-03-terminal-reopen-r03-20260728",
}
EXPECTED_ARTIFACT_ROLES = {
    "source_bindings": "MODEL_RUNTIME_INPUT",
    "question_set": "MODEL_RUNTIME_INPUT",
    "gold_binding": "SCORING_RUNTIME_INPUT",
}
REQUEST_KEYS = {
    "schema_version",
    "expected_ticket_id",
    "seal_ticket_path",
    "seal_ticket_sha256",
    "public_rehearsal_receipt_path",
    "public_rehearsal_receipt_sha256",
    "gate_program_path",
    "gate_program_sha256",
    "retired_ticket_ids",
    "retired_cycle_ids",
    "retired_run_ids",
}
POLICY_KEYS = {
    "schema_version",
    "policy_id",
    "ticket_id",
    "phase",
    "operation",
    "runtime_root",
    "runtime_root_role",
    "exact_artifact_count",
    "files",
    "excluded_audit_roots",
    "public_rehearsal_required",
}
POLICY_FILE_KEYS = {
    "artifact_id",
    "role",
    "relative_path",
    "sha256",
    "required",
}
TICKET_POLICY_REFERENCE_KEYS = {
    "policy_id",
    "path",
    "sha256",
}


class ShaGateError(RuntimeError):
    """授权前机械 SHA 闸拒收错误。"""


def _reject(code: str) -> None:
    raise ShaGateError(code)


def _expect(condition: bool, code: str) -> None:
    if not condition:
        _reject(code)


def _as_mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _reject(code)
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_fd(descriptor: int) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pairs_without_duplicates(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _reject("PUBLIC_JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _load_public_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_without_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShaGateError("PUBLIC_JSON_INVALID") from exc


def _is_lower_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _relative_parts(
    recorded: Any,
    *,
    code: str,
    filename_only: bool = False,
) -> tuple[str, ...]:
    _expect(isinstance(recorded, str) and bool(recorded), code)
    _expect("\x00" not in recorded and "\\" not in recorded, code)
    pure = PurePosixPath(recorded)
    parts = pure.parts
    _expect(
        not pure.is_absolute()
        and bool(parts)
        and all(part not in {"", ".", ".."} for part in parts),
        code,
    )
    if filename_only:
        _expect(len(parts) == 1, code)
    return parts


def _path_is_related(left: PurePosixPath, right: PurePosixPath) -> bool:
    return left == right or left in right.parents or right in left.parents


def _assert_no_symlink_chain(path: Path, *, project_root: Path, code: str) -> None:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        _reject(code)
    current = project_root
    _expect(not stat.S_ISLNK(os.lstat(current).st_mode), code)
    for part in relative.parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except OSError as exc:
            raise ShaGateError(code) from exc
        _expect(not stat.S_ISLNK(mode), code)


def _public_project_path(
    recorded: Any,
    *,
    project_root: Path,
    code: str,
) -> Path:
    parts = _relative_parts(recorded, code=code)
    _expect(
        all(
            part.lower() != "sealed" and "private" not in part.lower() for part in parts
        ),
        code,
    )
    path = project_root.joinpath(*parts)
    _assert_no_symlink_chain(path, project_root=project_root, code=code)
    _expect(path.is_file(), code)
    return path


def _argument_project_path(
    path: Path,
    *,
    project_root: Path,
    code: str,
) -> Path:
    candidate = path if path.is_absolute() else project_root / path
    candidate = Path(os.path.abspath(candidate))
    _assert_no_symlink_chain(candidate, project_root=project_root, code=code)
    _expect(candidate.is_file(), code)
    return candidate


def _output_project_path(
    path: Path,
    *,
    project_root: Path,
) -> Path:
    candidate = path if path.is_absolute() else project_root / path
    candidate = Path(os.path.abspath(candidate))
    _expect(not candidate.exists(), "OUTPUT_ALREADY_EXISTS")
    _assert_no_symlink_chain(
        candidate.parent,
        project_root=project_root,
        code="OUTPUT_PARENT_INVALID",
    )
    _expect(candidate.parent.is_dir(), "OUTPUT_PARENT_INVALID")
    return candidate


def _write_json_exclusive(path: Path, value: Any) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        data = _canonical_bytes(value)
        total = 0
        while total < len(data):
            total += os.write(descriptor, data[total:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_retired_id_lists(request: Mapping[str, Any]) -> None:
    for key, required in (
        ("retired_ticket_ids", RETIRED_TICKET_IDS),
        ("retired_cycle_ids", RETIRED_CYCLE_IDS),
        ("retired_run_ids", RETIRED_RUN_IDS),
    ):
        values = request.get(key)
        _expect(
            isinstance(values, list)
            and len(values) == len(set(values))
            and all(isinstance(value, str) and value for value in values)
            and required <= set(values),
            f"REQUEST_{key.upper()}_INVALID",
        )


def _validate_public_rehearsal(
    *,
    receipt: Mapping[str, Any],
    expected_ticket_id: str,
    expected_ticket_sha256: str,
) -> None:
    ticket = _as_mapping(
        receipt.get("ticket"),
        "REHEARSAL_TICKET_BINDING_MISSING",
    )
    _expect(
        receipt.get("status") == "PASS"
        and ticket.get("ticket_id") == expected_ticket_id
        and ticket.get("ticket_sha256") == expected_ticket_sha256,
        "REHEARSAL_TICKET_BINDING_INVALID",
    )
    zero_fields = (
        "model_api_calls",
        "network_requests",
        "private_terminal_files_read",
        "sealed_directory_reads",
        "formal_terminal_runs",
        "formal_score_runs",
    )
    _expect(
        all(receipt.get(field) == 0 for field in zero_fields)
        and receipt.get("formal_cycle_created") is False
        and receipt.get("formal_run_created") is False
        and receipt.get("formal_authority_issued") is False
        and receipt.get("formal_terminal_ticket_consumed") is False,
        "REHEARSAL_ZERO_USE_GATE_INVALID",
    )


def _validate_policy_files(
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    files = policy.get("files")
    _expect(
        isinstance(files, list)
        and len(files)
        == policy.get("exact_artifact_count")
        == len(EXPECTED_ARTIFACT_ROLES),
        "POLICY_FILE_COUNT_INVALID",
    )
    normalized: list[dict[str, Any]] = []
    artifact_ids: list[str] = []
    relative_paths: list[str] = []
    for raw in files:
        row = _as_mapping(raw, "POLICY_FILE_NOT_OBJECT")
        _expect(set(row) == POLICY_FILE_KEYS, "POLICY_FILE_KEYS_INVALID")
        artifact_id = row.get("artifact_id")
        role = row.get("role")
        _expect(
            artifact_id in EXPECTED_ARTIFACT_ROLES
            and role == EXPECTED_ARTIFACT_ROLES[artifact_id],
            "POLICY_ARTIFACT_ROLE_INVALID",
        )
        parts = _relative_parts(
            row.get("relative_path"),
            code="POLICY_FILE_PATH_INVALID",
            filename_only=True,
        )
        _expect(
            row.get("required") is True and _is_lower_sha256(row.get("sha256")),
            "POLICY_FILE_COMMITMENT_INVALID",
        )
        artifact_ids.append(str(artifact_id))
        relative_paths.append(parts[0])
        normalized.append(dict(row))
    _expect(
        set(artifact_ids) == set(EXPECTED_ARTIFACT_ROLES)
        and len(artifact_ids) == len(set(artifact_ids)),
        "POLICY_ARTIFACT_SET_INVALID",
    )
    _expect(
        len(relative_paths) == len(set(relative_paths)),
        "POLICY_FILE_PATH_DUPLICATED",
    )
    return sorted(normalized, key=lambda row: row["artifact_id"])


def _validate_runtime_root(
    *,
    policy: Mapping[str, Any],
    project_root: Path,
    files: Sequence[Mapping[str, Any]],
) -> Path:
    root_parts = _relative_parts(
        policy.get("runtime_root"),
        code="POLICY_RUNTIME_ROOT_INVALID",
    )
    _expect(
        policy.get("runtime_root_role") == "RUNTIME_SHA_INPUTS_ONLY",
        "POLICY_RUNTIME_ROOT_ROLE_INVALID",
    )
    root_pure = PurePosixPath(*root_parts)
    audit_roots = policy.get("excluded_audit_roots")
    _expect(
        isinstance(audit_roots, list)
        and bool(audit_roots)
        and len(audit_roots) == len(set(audit_roots)),
        "POLICY_AUDIT_ROOTS_INVALID",
    )
    for recorded in audit_roots:
        audit_parts = _relative_parts(
            recorded,
            code="POLICY_AUDIT_ROOT_INVALID",
        )
        audit_pure = PurePosixPath(*audit_parts)
        _expect(
            not _path_is_related(root_pure, audit_pure),
            "POLICY_AUDIT_ROOT_NOT_ISOLATED",
        )
    root = project_root.joinpath(*root_parts)
    _assert_no_symlink_chain(
        root,
        project_root=project_root,
        code="RUNTIME_ROOT_SYMLINK_OR_MISSING",
    )
    _expect(root.is_dir(), "RUNTIME_ROOT_NOT_DIRECTORY")
    expected_names = {str(row["relative_path"]) for row in files}
    try:
        with os.scandir(root) as iterator:
            entries = list(iterator)
    except OSError as exc:
        raise ShaGateError("RUNTIME_ROOT_SCAN_FAILED") from exc
    _expect(
        {entry.name for entry in entries} == expected_names
        and all(
            not entry.is_symlink() and entry.is_file(follow_symlinks=False)
            for entry in entries
        ),
        "RUNTIME_ROOT_EXACT_SET_MISMATCH",
    )
    return root


def _hash_runtime_files(
    *,
    runtime_root: Path,
    files: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_CLOEXEC", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    directory_descriptor = os.open(runtime_root, directory_flags)
    results: list[dict[str, Any]] = []
    try:
        for row in files:
            filename = str(row["relative_path"])
            path_stat = os.lstat(runtime_root / filename)
            _expect(
                stat.S_ISREG(path_stat.st_mode)
                and not stat.S_ISLNK(path_stat.st_mode)
                and path_stat.st_nlink == 1,
                f"RUNTIME_FILE_TYPE_INVALID:{row['artifact_id']}",
            )
            file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            file_flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(
                filename,
                file_flags,
                dir_fd=directory_descriptor,
            )
            try:
                opened_stat = os.fstat(descriptor)
                _expect(
                    stat.S_ISREG(opened_stat.st_mode)
                    and opened_stat.st_nlink == 1
                    and opened_stat.st_dev == path_stat.st_dev
                    and opened_stat.st_ino == path_stat.st_ino,
                    f"RUNTIME_FILE_RACE_OR_TYPE_INVALID:{row['artifact_id']}",
                )
                actual_sha256 = _sha256_fd(descriptor)
            finally:
                os.close(descriptor)
            _expect(
                actual_sha256 == row["sha256"],
                f"RUNTIME_FILE_SHA_MISMATCH:{row['artifact_id']}",
            )
            results.append(
                {
                    "artifact_id": row["artifact_id"],
                    "role": row["role"],
                    "sha256": actual_sha256,
                    "status": "MATCH",
                }
            )
    finally:
        os.close(directory_descriptor)
    return results


def run_gate(
    *,
    request_path: Path,
    output_path: Path,
    project_root: Path = PROJECT_ROOT,
    expected_program_path: Path | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve(strict=True)
    expected_program_path = (
        Path(__file__).resolve()
        if expected_program_path is None
        else expected_program_path.resolve(strict=True)
    )
    request_path = _argument_project_path(
        request_path,
        project_root=project_root,
        code="REQUEST_PATH_INVALID",
    )
    output_path = _output_project_path(
        output_path,
        project_root=project_root,
    )
    request = _as_mapping(
        _load_public_json(request_path),
        "REQUEST_NOT_OBJECT",
    )
    _expect(set(request) == REQUEST_KEYS, "REQUEST_KEYS_INVALID")
    _expect(request.get("schema_version") == REQUEST_SCHEMA, "REQUEST_SCHEMA_INVALID")
    expected_ticket_id = request.get("expected_ticket_id")
    _expect(
        isinstance(expected_ticket_id, str)
        and bool(expected_ticket_id)
        and expected_ticket_id not in RETIRED_TICKET_IDS,
        "REQUEST_TICKET_ID_INVALID",
    )
    for key in (
        "seal_ticket_sha256",
        "public_rehearsal_receipt_sha256",
        "gate_program_sha256",
    ):
        _expect(_is_lower_sha256(request.get(key)), f"REQUEST_{key.upper()}_INVALID")
    _validate_retired_id_lists(request)

    program_path = _public_project_path(
        request.get("gate_program_path"),
        project_root=project_root,
        code="GATE_PROGRAM_PATH_INVALID",
    )
    _expect(
        program_path == expected_program_path
        and _sha256_file(program_path) == request["gate_program_sha256"],
        "GATE_PROGRAM_BINDING_INVALID",
    )

    ticket_path = _public_project_path(
        request.get("seal_ticket_path"),
        project_root=project_root,
        code="SEAL_TICKET_PATH_INVALID",
    )
    ticket_sha256 = _sha256_file(ticket_path)
    _expect(
        ticket_sha256 == request["seal_ticket_sha256"],
        "SEAL_TICKET_SHA_MISMATCH",
    )
    ticket = _as_mapping(
        _load_public_json(ticket_path),
        "SEAL_TICKET_NOT_OBJECT",
    )
    _expect(
        ticket.get("ticket_id") == expected_ticket_id
        and ticket.get("ticket_id") not in RETIRED_TICKET_IDS,
        "SEAL_TICKET_ID_INVALID",
    )
    _expect(
        ticket.get("status")
        == "SEALED_AWAITING_MAINLINE1_PUBLIC_REHEARSAL_AND_NEW_AUTHORITY",
        "SEAL_TICKET_STATUS_INVALID",
    )

    rehearsal_path = _public_project_path(
        request.get("public_rehearsal_receipt_path"),
        project_root=project_root,
        code="REHEARSAL_RECEIPT_PATH_INVALID",
    )
    rehearsal_sha256 = _sha256_file(rehearsal_path)
    _expect(
        rehearsal_sha256 == request["public_rehearsal_receipt_sha256"],
        "REHEARSAL_RECEIPT_SHA_MISMATCH",
    )
    rehearsal = _as_mapping(
        _load_public_json(rehearsal_path),
        "REHEARSAL_RECEIPT_NOT_OBJECT",
    )
    _validate_public_rehearsal(
        receipt=rehearsal,
        expected_ticket_id=expected_ticket_id,
        expected_ticket_sha256=ticket_sha256,
    )

    policy_reference = _as_mapping(
        ticket.get("preauthorization_sha_policy"),
        "TICKET_SHA_POLICY_REFERENCE_MISSING",
    )
    _expect(
        set(policy_reference) == TICKET_POLICY_REFERENCE_KEYS
        and _is_lower_sha256(policy_reference.get("sha256")),
        "TICKET_SHA_POLICY_REFERENCE_INVALID",
    )
    policy_path = _public_project_path(
        policy_reference.get("path"),
        project_root=project_root,
        code="SHA_POLICY_PATH_INVALID",
    )
    policy_sha256 = _sha256_file(policy_path)
    _expect(
        policy_sha256 == policy_reference["sha256"],
        "SHA_POLICY_SHA_MISMATCH",
    )
    policy = _as_mapping(
        _load_public_json(policy_path),
        "SHA_POLICY_NOT_OBJECT",
    )
    _expect(set(policy) == POLICY_KEYS, "SHA_POLICY_KEYS_INVALID")
    _expect(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("policy_id") == policy_reference.get("policy_id")
        and policy.get("ticket_id") == expected_ticket_id
        and policy.get("phase") == "PRE_AUTHORIZATION"
        and policy.get("operation") == "HASH_ONLY"
        and policy.get("public_rehearsal_required") is True,
        "SHA_POLICY_BINDING_INVALID",
    )
    files = _validate_policy_files(policy)
    runtime_root = _validate_runtime_root(
        policy=policy,
        project_root=project_root,
        files=files,
    )
    checks = _hash_runtime_files(
        runtime_root=runtime_root,
        files=files,
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "phase": "PRE_AUTHORIZATION",
        "operation": "HASH_ONLY",
        "ticket_id": expected_ticket_id,
        "ticket_sha256": ticket_sha256,
        "policy_id": policy["policy_id"],
        "policy_sha256": policy_sha256,
        "request_sha256": _sha256_file(request_path),
        "public_rehearsal_receipt_sha256": rehearsal_sha256,
        "gate_program_sha256": request["gate_program_sha256"],
        "runtime_root_role": policy["runtime_root_role"],
        "checked_artifact_count": len(checks),
        "expected_artifact_count": len(EXPECTED_ARTIFACT_ROLES),
        "mismatch_count": 0,
        "checked_artifacts": checks,
        "directory_scan_scope": "RUNTIME_ROOT_ONLY",
        "private_content_parse_count": 0,
        "private_content_echo_count": 0,
        "audit_root_access_count": 0,
        "manual_private_path_argument_count": 0,
        "model_api_calls": 0,
        "network_requests": 0,
        "formal_cycle_created": False,
        "formal_run_created": False,
        "formal_authority_issued": False,
        "completed_at_utc": _utc_now(),
    }
    result["receipt_payload_sha256"] = _sha256_bytes(_canonical_bytes(result))
    _write_json_exclusive(output_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main() -> None:
    args = parse_args()
    result = run_gate(
        request_path=args.request,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "schema_version": result["schema_version"],
                "ticket_id": result["ticket_id"],
                "checked_artifact_count": result["checked_artifact_count"],
                "receipt_payload_sha256": result["receipt_payload_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
