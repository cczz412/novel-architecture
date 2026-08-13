#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


PROTOTYPE_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROTOTYPE_DIR / "config/SOURCE_CONFIG.json"
CONTRACTS_DIR = PROTOTYPE_DIR / "contracts"
OUTPUT_ROOT_RELATIVE = Path("TEMP/repo_bridge")
GENERATOR_VERSION = "0.2.0-protocol-freeze-candidate"
MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 10 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 25 * 1024 * 1024
MAX_ZIP_MEMBERS = 200
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
PACKAGE_MANIFEST = "_bridge/PACKAGE_MANIFEST.json"
PACKAGE_SHA256SUMS = "_bridge/SHA256SUMS"
SECRET_SCAN_MEMBER = "_bridge/SECRET_SCAN.json"
HANDOFF_BINDING_MEMBER = "_bridge/HANDOFF_BINDING.json"
RELEVANCE_GRANULARITY = "file_level"
SOURCE_FRESHNESS_MAX_AGE = timedelta(days=7)

SECRET_VALUE_PATTERNS = {
    "bearer_token": re.compile(rb"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    "sk_token": re.compile(rb"\bsk-[A-Za-z0-9_-]{12,}\b"),
    "api_key_assignment": re.compile(
        rb"(?:API[_-]?KEY|ACCESS[_-]?TOKEN|SECRET[_-]?KEY)"
        rb"[\"']?\s*[=:]\s*[\"'][A-Za-z0-9._~+/=-]{12,}[\"']",
        re.I,
    ),
}
SECRET_NAME_MARKERS = (
    ".env",
    ".key",
    ".pem",
    "apikey",
    "api_key",
    "credential",
    "private_key",
)
LEGACY_REQUIRED_MEMBERS = {
    "00_HANDOFF.md",
    "01_REPO_SNAPSHOT.md",
    "02_STRUCTURE.md",
    "03_CURRENT_STATE.md",
    "04_DECISIONS.md",
    "05_CHANGES_SINCE_LAST.md",
    "06_OPEN_QUESTIONS.md",
    "07_EVIDENCE_INDEX.md",
    "08_RETURN_INSTRUCTIONS.md",
    "_bridge/SNAPSHOT.json",
    "_bridge/DIRECTORY_SUMMARY.json",
    "_bridge/CURRENT_STATE.json",
    "_bridge/DECISION_EVENTS.jsonl",
    "_bridge/DECISIONS.jsonl",
    "_bridge/CHANGES.json",
    "_bridge/OPEN_QUESTIONS.json",
    "_bridge/EVIDENCE_INDEX.json",
    "_bridge/SOURCE_BINDINGS.json",
    "_bridge/EXCLUSIONS.json",
    SECRET_SCAN_MEMBER,
    "_bridge/CHATGPT_RETURN_TEMPLATE.json",
    "_bridge/schemas/REVIEW_RETURN.schema.json",
    PACKAGE_MANIFEST,
    PACKAGE_SHA256SUMS,
}
REQUIRED_MEMBERS = LEGACY_REQUIRED_MEMBERS | {HANDOFF_BINDING_MEMBER}
DERIVED_JSON_VIEWS = {
    "_bridge/SNAPSHOT.json",
    "_bridge/DIRECTORY_SUMMARY.json",
    "_bridge/CURRENT_STATE.json",
    "_bridge/CHANGES.json",
    "_bridge/OPEN_QUESTIONS.json",
    "_bridge/EVIDENCE_INDEX.json",
    "_bridge/SOURCE_BINDINGS.json",
    "_bridge/EXCLUSIONS.json",
    HANDOFF_BINDING_MEMBER,
}


class BridgeError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = code if not detail else f"{code}: {detail}"
        super().__init__(message)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00",
        "Z",
    )


def assess_source_freshness(
    source_declared_at: object,
    generated_at: datetime,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_declared_at": source_declared_at,
        "freshness": "unknown",
        "source_age_seconds": None,
        "freshness_max_age_seconds": int(SOURCE_FRESHNESS_MAX_AGE.total_seconds()),
        "reason": "source_declared_at_missing_or_invalid",
    }
    if not isinstance(source_declared_at, str) or not source_declared_at:
        return result
    try:
        declared = datetime.fromisoformat(source_declared_at.replace("Z", "+00:00"))
    except ValueError:
        return result
    if declared.tzinfo is None:
        result["reason"] = "source_declared_at_has_no_timezone"
        return result
    age = generated_at.astimezone(timezone.utc) - declared.astimezone(timezone.utc)
    if age < -timedelta(minutes=5):
        result["reason"] = "source_declared_at_is_in_future"
        return result
    age_seconds = max(0, int(age.total_seconds()))
    result.update(
        {
            "freshness": (
                "fresh" if age <= SOURCE_FRESHNESS_MAX_AGE else "stale"
            ),
            "source_age_seconds": age_seconds,
            "reason": "within_max_age" if age <= SOURCE_FRESHNESS_MAX_AGE else "older_than_max_age",
        }
    )
    return result


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def safe_relative(value: object, *, code: str = "UNSAFE_REPO_PATH") -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BridgeError(code, "路径必须是非空字符串")
    if "\x00" in value or "\\" in value or "//" in value:
        raise BridgeError(code, value)
    relative = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        relative.is_absolute()
        or bool(windows.drive)
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise BridgeError(code, value)
    if ".git" in relative.parts:
        raise BridgeError(code, "路径不得进入 .git")
    return relative


def _path_from_relative(root: Path, relative: PurePosixPath) -> Path:
    return root.joinpath(*relative.parts)


def _require_plain_chain(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as exc:
            raise BridgeError("SOURCE_MISSING", relative.as_posix()) from exc
        if stat.S_ISLNK(info.st_mode):
            raise BridgeError("SOURCE_SYMLINK_REJECTED", relative.as_posix())
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise BridgeError("SOURCE_PARENT_NOT_DIRECTORY", relative.as_posix())
    return current


def read_stable_repo_file(
    root: Path,
    relative_value: str,
    *,
    max_bytes: int = MAX_SOURCE_BYTES,
) -> bytes:
    relative = safe_relative(relative_value)
    path = _require_plain_chain(root, relative)
    opened = path.stat()
    if not stat.S_ISREG(opened.st_mode):
        raise BridgeError("SOURCE_NOT_REGULAR_FILE", relative.as_posix())
    if opened.st_nlink != 1:
        raise BridgeError("SOURCE_HARDLINK_REJECTED", relative.as_posix())
    if opened.st_size > max_bytes:
        raise BridgeError("SOURCE_TOO_LARGE", relative.as_posix())
    before = _identity(opened)
    chunks: list[bytes] = []
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise BridgeError("SOURCE_TOO_LARGE", relative.as_posix())
            chunks.append(chunk)
    if _identity(path.stat()) != before:
        raise BridgeError("SOURCE_DRIFT_DURING_READ", relative.as_posix())
    return b"".join(chunks)


def hash_worktree_path(root: Path, relative_value: str) -> dict[str, Any]:
    relative = safe_relative(relative_value, code="UNSAFE_GIT_PATH")
    path = _path_from_relative(root, relative)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"path": relative.as_posix(), "state": "missing"}
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path).encode("utf-8", errors="surrogateescape")
        return {
            "path": relative.as_posix(),
            "state": "symlink",
            "bytes": len(target),
            "sha256": sha256_bytes(target),
        }
    if not stat.S_ISREG(info.st_mode):
        raise BridgeError("GIT_DIRTY_SPECIAL_FILE", relative.as_posix())
    digest = hashlib.sha256()
    total = 0
    before = _identity(info)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            total += len(chunk)
            digest.update(chunk)
    if _identity(path.stat()) != before:
        raise BridgeError("GIT_DIRTY_FILE_DRIFT", relative.as_posix())
    return {
        "path": relative.as_posix(),
        "state": "regular",
        "bytes": total,
        "sha256": digest.hexdigest(),
    }


def read_json_bytes(data: bytes, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError(code, str(exc)) from exc
    if not isinstance(value, dict):
        raise BridgeError(code, "顶层必须是对象")
    return value


def validate_json(value: object, schema_path: Path, *, code: str) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError, ValidationError) as exc:
        raise BridgeError(code, str(exc)) from exc


def git_bytes(root: Path, args: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise BridgeError("GIT_COMMAND_FAILED", f"{' '.join(args)}: {detail}")
    return result.stdout


def _nul_paths(data: bytes) -> list[str]:
    paths: list[str] = []
    for raw in data.split(b"\x00"):
        if raw:
            paths.append(raw.decode("utf-8"))
    return paths


def _looks_secret_path(path: str) -> bool:
    lowered = path.casefold()
    return any(marker in lowered for marker in SECRET_NAME_MARKERS)


def collect_git_state(root: Path) -> dict[str, Any]:
    head = git_bytes(root, ["rev-parse", "HEAD"]).decode("ascii").strip()
    branch = git_bytes(root, ["branch", "--show-current"]).decode("utf-8").strip()
    index_raw = git_bytes(root, ["ls-files", "--stage", "-z"])
    status_raw = git_bytes(
        root,
        ["status", "--porcelain=v2", "-z", "--untracked-files=all"],
    )
    path_commands = (
        ["diff", "--name-only", "-z"],
        ["diff", "--cached", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
        ["ls-files", "--deleted", "-z"],
    )
    dirty_paths: set[str] = set()
    for command in path_commands:
        dirty_paths.update(_nul_paths(git_bytes(root, command)))
    secret_paths = sorted(path for path in dirty_paths if _looks_secret_path(path))
    if secret_paths:
        raise BridgeError("GIT_DIRTY_SECRET_NAMED_PATH", secret_paths[0])
    dirty_entries = [hash_worktree_path(root, path) for path in sorted(dirty_paths)]
    core = {
        "head": head,
        "branch": branch,
        "index_fingerprint_sha256": sha256_bytes(index_raw),
        "status_fingerprint_sha256": sha256_bytes(status_raw),
        "dirty_entries": dirty_entries,
    }
    core["workspace_fingerprint_sha256"] = sha256_bytes(canonical_json(core))
    return core


def load_source_config(root: Path, config_path: Path) -> tuple[dict[str, Any], bytes, str]:
    try:
        relative = config_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise BridgeError("CONFIG_OUTSIDE_REPO", str(config_path)) from exc
    data = read_stable_repo_file(root, relative)
    value = read_json_bytes(data, code="SOURCE_CONFIG_INVALID_JSON")
    validate_json(
        value,
        CONTRACTS_DIR / "SOURCE_CONFIG.schema.json",
        code="SOURCE_CONFIG_SCHEMA_INVALID",
    )
    source_ids = [row["source_id"] for row in value["semantic_sources"]]
    evidence_ids = [row["evidence_id"] for row in value["critical_evidence"]]
    if len(source_ids) != len(set(source_ids)):
        raise BridgeError("DUPLICATE_SOURCE_ID")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise BridgeError("DUPLICATE_EVIDENCE_ID")
    return value, data, relative


def _source_binding(
    *,
    source_id: str,
    adapter: str,
    authority_scope: str,
    path: str,
    data: bytes,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "adapter": adapter,
        "authority_scope": authority_scope,
        "path": path,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def _evidence_row(
    evidence_id: str,
    identity: str,
    path: str,
    authority_scope: str,
    data: bytes,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "identity": identity,
        "path_kind": "repo_relative",
        "path": path,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "authority_scope": authority_scope,
        "visibility": "index_only",
        "content_included": False,
    }


def collect_semantic_sources(
    root: Path,
    config: dict[str, Any],
    config_data: bytes,
    config_relative: str,
) -> dict[str, Any]:
    bindings: list[dict[str, Any]] = [
        _source_binding(
            source_id="repo_bridge_source_config",
            adapter="source_config",
            authority_scope="repo_bridge_reading_rules",
            path=config_relative,
            data=config_data,
        )
    ]
    evidence: list[dict[str, Any]] = []
    repo_current: dict[str, Any] | None = None
    directory_registry: dict[str, Any] | None = None
    finetuning_current: dict[str, Any] | None = None
    decision_evidence_ids: list[str] = []
    acceptance_receipts: list[dict[str, Any]] = []

    for row in config["semantic_sources"]:
        path = row["path"]
        data = read_stable_repo_file(root, path)
        adapter = row["adapter"]
        binding = _source_binding(
            source_id=row["source_id"],
            adapter=adapter,
            authority_scope=row["authority_scope"],
            path=path,
            data=data,
        )
        bindings.append(binding)
        evidence_id = row["source_id"].upper().replace("_", "-")
        evidence.append(
            _evidence_row(
                evidence_id,
                row["source_id"],
                path,
                row["authority_scope"],
                data,
            )
        )

        if adapter == "governance_current_state":
            value = read_json_bytes(data, code="CURRENT_STATE_INVALID_JSON")
            execution = value.get("current_execution")
            if not isinstance(execution, dict):
                raise BridgeError("CURRENT_STATE_CONTRACT_MISSING", "current_execution")
            task = execution.get("task")
            run = execution.get("run")
            controls = execution.get("controls")
            if not all(isinstance(item, dict) for item in (task, run, controls)):
                raise BridgeError("CURRENT_STATE_CONTRACT_MISSING", "task/run/controls")
            repo_current = {
                "source_path": path,
                "source_sha256": binding["sha256"],
                "source_snapshot_at": value.get("snapshot_at"),
                "task": {
                    "task_id": task.get("task_id"),
                    "label": task.get("label"),
                    "status": task.get("status"),
                    "status_label": task.get("status_label"),
                },
                "run": {
                    "run_id": run.get("run_id"),
                    "run_directory": run.get("run_directory"),
                    "status_label": run.get("status_label"),
                },
                "next_action": controls.get("next_action"),
                "blockers": execution.get("blockers") or [],
            }
        elif adapter == "directory_registry":
            value = read_json_bytes(data, code="DIRECTORY_REGISTRY_INVALID_JSON")
            if value.get("schema_version") != "directory-registry-v1":
                raise BridgeError("DIRECTORY_REGISTRY_SCHEMA_UNSUPPORTED")
            if not isinstance(value.get("directories"), list):
                raise BridgeError("DIRECTORY_REGISTRY_CONTRACT_MISSING")
            directory_registry = value
        elif adapter == "finetuning_current":
            value = read_json_bytes(data, code="FINETUNING_CURRENT_INVALID_JSON")
            experiment_id = value.get("current_experiment_id")
            manifest_sha = value.get("manifest_sha256")
            if (
                not isinstance(experiment_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]+", experiment_id)
                or not isinstance(manifest_sha, str)
                or not re.fullmatch(r"[0-9a-f]{64}", manifest_sha)
            ):
                raise BridgeError("FINETUNING_CURRENT_CONTRACT_INVALID")
            manifest_path = (
                f"finetuning/experiments/{experiment_id}/MANIFEST.json"
            )
            manifest_data = read_stable_repo_file(root, manifest_path)
            actual_manifest_sha = sha256_bytes(manifest_data)
            if actual_manifest_sha != manifest_sha:
                raise BridgeError(
                    "FINETUNING_MANIFEST_SHA_MISMATCH",
                    f"{manifest_sha} != {actual_manifest_sha}",
                )
            manifest = read_json_bytes(
                manifest_data,
                code="FINETUNING_MANIFEST_INVALID_JSON",
            )
            manifest_schema = root / "finetuning/policies/manifest.schema.json"
            if manifest_schema.is_file():
                validate_json(
                    manifest,
                    manifest_schema,
                    code="FINETUNING_MANIFEST_SCHEMA_INVALID",
                )
            manifest_binding = _source_binding(
                source_id="finetuning_current_manifest",
                adapter="finetuning_manifest",
                authority_scope="single_experiment_machine_facts",
                path=manifest_path,
                data=manifest_data,
            )
            bindings.append(manifest_binding)
            evidence.append(
                _evidence_row(
                    "FT-CURRENT-MANIFEST",
                    "current_finetuning_manifest",
                    manifest_path,
                    "single_experiment_machine_facts",
                    manifest_data,
                )
            )
            decision_path = (
                f"finetuning/experiments/{experiment_id}/DECISION.md"
            )
            decision_file = root / decision_path
            if decision_file.is_file() and not decision_file.is_symlink():
                decision_data = read_stable_repo_file(root, decision_path)
                bindings.append(
                    _source_binding(
                        source_id="finetuning_current_decision",
                        adapter="decision_evidence",
                        authority_scope="finetuning_current_decision",
                        path=decision_path,
                        data=decision_data,
                    )
                )
                evidence.append(
                    _evidence_row(
                        "FT-CURRENT-DECISION",
                        "current_finetuning_decision",
                        decision_path,
                        "finetuning_current_decision",
                        decision_data,
                    )
                )
                decision_evidence_ids.append("FT-CURRENT-DECISION")
            finetuning_current = {
                "source_path": path,
                "source_sha256": binding["sha256"],
                "current_experiment_id": experiment_id,
                "manifest_revision": value.get("manifest_revision"),
                "manifest_path": manifest_path,
                "manifest_sha256": actual_manifest_sha,
                "pointer_scope": value.get("scope"),
                "may_authorize_promotion": value.get("may_authorize_promotion"),
                "may_authorize_training": value.get("may_authorize_training"),
                "derived_facts": manifest.get("derived_facts") or {},
                "boundaries": manifest.get("boundaries") or {},
            }
        elif adapter == "evidence_only":
            decision_evidence_ids.append(evidence_id)
        elif adapter == "json_evidence":
            value = read_json_bytes(data, code="JSON_EVIDENCE_INVALID")
            acceptance_receipts.append(
                {
                    "evidence_id": evidence_id,
                    "status": value.get("status"),
                    "source_path": path,
                    "source_sha256": binding["sha256"],
                }
            )

    for row in config["critical_evidence"]:
        data = read_stable_repo_file(root, row["path"])
        source_id = "evidence_" + row["evidence_id"].lower().replace("-", "_")
        bindings.append(
            _source_binding(
                source_id=source_id,
                adapter="critical_evidence",
                authority_scope=row["authority_scope"],
                path=row["path"],
                data=data,
            )
        )
        evidence.append(
            _evidence_row(
                row["evidence_id"],
                source_id,
                row["path"],
                row["authority_scope"],
                data,
            )
        )

    if repo_current is None or directory_registry is None or finetuning_current is None:
        raise BridgeError("REQUIRED_ADAPTER_MISSING")
    bindings.sort(key=lambda item: item["source_id"])
    evidence.sort(key=lambda item: item["evidence_id"])
    if len({row["source_id"] for row in bindings}) != len(bindings):
        raise BridgeError("DUPLICATE_DERIVED_SOURCE_ID")
    if len({row["evidence_id"] for row in evidence}) != len(evidence):
        raise BridgeError("DUPLICATE_DERIVED_EVIDENCE_ID")
    return {
        "bindings": bindings,
        "evidence": evidence,
        "directory_registry": directory_registry,
        "current_state": {
            "repository": repo_current,
            "domains": {"finetuning": finetuning_current},
            "acceptance_receipts": acceptance_receipts,
        },
        "decisions": {
            "coverage": "partial_registered_only",
            "formal_event_count": 0,
            "proposal_inbox_is_formal_history": False,
            "decision_evidence_ids": sorted(set(decision_evidence_ids)),
        },
    }


def _excluded_subpath(relative: str, excluded: Iterable[str]) -> bool:
    return any(relative == item or relative.startswith(item + "/") for item in excluded)


def scan_directory_metrics(
    root: Path,
    relative_value: str,
    excluded_subpaths: Sequence[str],
) -> dict[str, int]:
    relative = safe_relative(relative_value, code="UNSAFE_INVENTORY_PATH")
    configured_exclusion_count = sum(
        1
        for item in excluded_subpaths
        if item == relative.as_posix()
        or item.startswith(relative.as_posix().rstrip("/") + "/")
    )
    start = _path_from_relative(root, relative)
    try:
        start_info = start.lstat()
    except FileNotFoundError:
        return {
            "file_count": 0,
            "directory_count": 0,
            "symlink_count": 0,
            "special_count": 0,
            "total_file_bytes": 0,
            "excluded_subpath_count": configured_exclusion_count,
        }
    if stat.S_ISLNK(start_info.st_mode):
        return {
            "file_count": 0,
            "directory_count": 0,
            "symlink_count": 1,
            "special_count": 0,
            "total_file_bytes": 0,
            "excluded_subpath_count": configured_exclusion_count,
        }
    if not stat.S_ISDIR(start_info.st_mode):
        raise BridgeError("INVENTORY_ROOT_NOT_DIRECTORY", relative.as_posix())
    metrics = {
        "file_count": 0,
        "directory_count": 0,
        "symlink_count": 0,
        "special_count": 0,
        "total_file_bytes": 0,
        "excluded_subpath_count": configured_exclusion_count,
    }
    stack = [start]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise BridgeError("INVENTORY_SCAN_FAILED", str(directory)) from exc
        for entry in entries:
            path = Path(entry.path)
            rel = path.relative_to(root).as_posix()
            if _excluded_subpath(rel, excluded_subpaths):
                continue
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise BridgeError("INVENTORY_ENTRY_STAT_FAILED", rel) from exc
            if stat.S_ISLNK(info.st_mode):
                metrics["symlink_count"] += 1
            elif stat.S_ISDIR(info.st_mode):
                metrics["directory_count"] += 1
                stack.append(path)
            elif stat.S_ISREG(info.st_mode):
                metrics["file_count"] += 1
                metrics["total_file_bytes"] += info.st_size
            else:
                metrics["special_count"] += 1
    return metrics


def collect_directory_summary(
    root: Path,
    registry: dict[str, Any],
    inventory_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    excluded_roots = set(inventory_config["exclude_roots"])
    excluded_subpaths = list(inventory_config["exclude_subpaths"])
    high_frequency = set(inventory_config["high_frequency_roots"])
    rows: list[dict[str, Any]] = []
    registered_paths: set[str] = set()
    for raw in registry["directories"]:
        path = raw.get("path")
        if not isinstance(path, str):
            raise BridgeError("DIRECTORY_REGISTRY_PATH_INVALID")
        safe_relative(path, code="DIRECTORY_REGISTRY_PATH_INVALID")
        registered_paths.add(path)
        excluded = path in excluded_roots
        metrics = None if excluded else scan_directory_metrics(
            root,
            path,
            excluded_subpaths,
        )
        rows.append(
            {
                "path": path,
                "identity": raw.get("identity"),
                "category": raw.get("category"),
                "container_authority": raw.get("container_authority"),
                "load_policy": raw.get("load_policy"),
                "lifecycle": raw.get("lifecycle"),
                "git_policy": raw.get("git_policy"),
                "new_content_rule": raw.get("new_content_rule"),
                "high_frequency_inventory_only": path in high_frequency,
                "content_read": False,
                "metrics_coverage": "excluded" if excluded else "recursive_lstat_only",
                "metrics": metrics,
            }
        )
    unregistered: list[str] = []
    for item in sorted(root.iterdir(), key=lambda value: value.name):
        if not item.is_dir() or item.name == ".git" or item.name in registered_paths:
            continue
        unregistered.append(item.name)
    rows.sort(key=lambda item: item["path"])
    return rows, unregistered


def generator_identity(root: Path, config_relative: str) -> dict[str, Any]:
    rows = []
    config_data = read_stable_repo_file(root, config_relative)
    rows.append(
        {
            "identity": "repo/SOURCE_CONFIG.json",
            "sha256": sha256_bytes(config_data),
            "bytes": len(config_data),
        }
    )
    implementation_data = Path(__file__).read_bytes()
    rows.append(
        {
            "identity": "implementation/repo_bridge.py",
            "sha256": sha256_bytes(implementation_data),
            "bytes": len(implementation_data),
        }
    )
    for path in sorted(CONTRACTS_DIR.glob("*.json")):
        data = path.read_bytes()
        rows.append(
            {
                "identity": f"contracts/{path.name}",
                "sha256": sha256_bytes(data),
                "bytes": len(data),
            }
        )
    rows.sort(key=lambda item: item["identity"])
    return {
        "version": GENERATOR_VERSION,
        "files": rows,
        "source_sha256": sha256_bytes(canonical_json(rows)),
    }


def derived_view(snapshot_id: str, **values: Any) -> dict[str, Any]:
    return {
        "schema_version": values.pop("schema_version"),
        "view_kind": "derived_snapshot_view",
        "authoritative": False,
        "snapshot_id": snapshot_id,
        **values,
    }


def build_snapshot_components(
    root: Path,
    config_path: Path,
    *,
    include_inventory: bool,
) -> dict[str, Any]:
    config, config_data, config_relative = load_source_config(root, config_path)
    git_state = collect_git_state(root)
    sources = collect_semantic_sources(root, config, config_data, config_relative)
    generator = generator_identity(root, config_relative)
    bindings_sha = sha256_bytes(canonical_json(sources["bindings"]))
    current_state_sha = sha256_bytes(canonical_json(sources["current_state"]))
    decisions_sha = sha256_bytes(canonical_json(sources["decisions"]))
    evidence_sha = sha256_bytes(canonical_json(sources["evidence"]))
    semantic_core = {
        "schema_version": "repo-bridge-semantic-core-v1",
        "repo_id": config["repo_id"],
        "workspace_fingerprint_sha256": git_state["workspace_fingerprint_sha256"],
        "source_bindings_sha256": bindings_sha,
        "current_state_sha256": current_state_sha,
        "decisions_sha256": decisions_sha,
        "evidence_index_sha256": evidence_sha,
        "generator_sha256": generator["source_sha256"],
    }
    snapshot_digest = sha256_bytes(canonical_json(semantic_core))
    snapshot_id = "rb1-" + snapshot_digest[:20]
    directory_rows: list[dict[str, Any]] = []
    unregistered: list[str] = []
    if include_inventory:
        directory_rows, unregistered = collect_directory_summary(
            root,
            sources["directory_registry"],
            config["inventory"],
        )
    inventory_basis = {
        "directories": directory_rows,
        "unregistered_top_level_directories": unregistered,
    }
    inventory_fingerprint = sha256_bytes(canonical_json(inventory_basis))
    observation_digest = sha256_bytes(
        canonical_json(
            {
                "snapshot_digest_sha256": snapshot_digest,
                "inventory_fingerprint_sha256": inventory_fingerprint,
            }
        )
    )
    observation_id = "obs1-" + observation_digest[:20]
    snapshot = {
        "schema_version": "repo-bridge-snapshot-v1",
        "view_kind": "derived_snapshot_view",
        "authoritative": False,
        "repo_id": config["repo_id"],
        "snapshot_id": snapshot_id,
        "snapshot_digest_sha256": snapshot_digest,
        "observation_id": observation_id,
        "observation_digest_sha256": observation_digest,
        "workspace_fingerprint_sha256": git_state["workspace_fingerprint_sha256"],
        "inventory_fingerprint_sha256": inventory_fingerprint,
        "source_bindings_sha256": bindings_sha,
        "git": {
            "head": git_state["head"],
            "branch": git_state["branch"],
            "index_fingerprint_sha256": git_state["index_fingerprint_sha256"],
            "status_fingerprint_sha256": git_state["status_fingerprint_sha256"],
            "dirty_entry_count": len(git_state["dirty_entries"]),
            "dirty_entries": git_state["dirty_entries"],
        },
        "generator": generator,
        "coverage": {
            "current_state": "complete_for_registered_sources",
            "decisions": "partial_registered_only",
            "ignored_payload_contents": "not_scanned",
            "inventory_changes_affect_snapshot_id": False,
            "relevance_granularity": RELEVANCE_GRANULARITY,
        },
    }
    validate_json(
        snapshot,
        CONTRACTS_DIR / "SNAPSHOT.schema.json",
        code="SNAPSHOT_SCHEMA_INVALID",
    )
    return {
        "config": config,
        "snapshot": snapshot,
        "source_bindings": sources["bindings"],
        "current_state": sources["current_state"],
        "decisions": sources["decisions"],
        "evidence": sources["evidence"],
        "directory_rows": directory_rows,
        "unregistered_top_level_directories": unregistered,
    }


def scan_payload_secrets(root: Path, payloads: Mapping[str, bytes]) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    root_value = root.resolve().as_posix().encode("utf-8")
    home_value = Path.home().resolve().as_posix().encode("utf-8")
    for member, data in payloads.items():
        if _looks_secret_path(member):
            hits.append({"member": member, "pattern": "secret_named_member"})
        if root_value and root_value in data:
            hits.append({"member": member, "pattern": "repo_absolute_path"})
        if home_value and home_value != root_value and home_value in data:
            hits.append({"member": member, "pattern": "home_absolute_path"})
        for label, pattern in SECRET_VALUE_PATTERNS.items():
            if pattern.search(data):
                hits.append({"member": member, "pattern": label})
    return {
        "schema_version": "repo-bridge-secret-scan-v1",
        "result": "PASS" if not hits else "FAIL",
        "scanned_member_count": len(payloads),
        "scanned_members": sorted(payloads),
        "hit_count": len(hits),
        "hits": hits,
    }


def _markdown_source(text: str) -> bytes:
    return (text.rstrip() + "\n\n来源：Codex\n").encode("utf-8")


def render_handoff(handoff: dict[str, Any], snapshot: dict[str, Any]) -> bytes:
    questions = "\n".join(f"- {item}" for item in handoff["questions"])
    domains = "、".join(handoff["review_scope"]["domains"]) or "未指定"
    paths = "、".join(f"`{item}`" for item in handoff["review_scope"]["paths"]) or "未指定"
    return _markdown_source(
        f"""# Repo Bridge 交接说明

这是一次真实的 Repo Bridge V1 原型出站包，不是模拟 ChatGPT 回包。

- 语义快照：`{snapshot['snapshot_id']}`
- 库存观察：`{snapshot['observation_id']}`
- 交接编号：`{handoff['handoff_id']}`
- 请求方：{handoff['requested_by']}
- 审查业务域：{domains}
- 审查路径：{paths}

## 这次要解决什么

{handoff['purpose']}

## 请回答

{questions}

这份包不授权执行、修改、批准或迁移。请按 `08_RETURN_INSTRUCTIONS.md` 生成 `CHATGPT_RETURN.json`。"""
    )


def render_snapshot(snapshot: dict[str, Any]) -> bytes:
    git = snapshot["git"]
    return _markdown_source(
        f"""# 仓库快照

- 语义快照：`{snapshot['snapshot_id']}`
- 语义摘要：`{snapshot['snapshot_digest_sha256']}`
- 库存观察：`{snapshot['observation_id']}`
- 库存摘要：`{snapshot['inventory_fingerprint_sha256']}`
- Git HEAD：`{git['head']}`
- Git 分支：`{git['branch'] or '(detached)'}`
- 工作区变化文件：{git['dirty_entry_count']}

`snapshot_id` 不受 `TEMP/runs/reports/outbox` 普通体量变化影响；这些变化只进入库存观察。所有本页内容都是派生视图，不是权威源。"""
    )


def render_structure(
    rows: Sequence[dict[str, Any]],
    unregistered: Sequence[str],
) -> bytes:
    table = [
        "| 目录 | 身份 | Git | 文件数 | 体量 | 高频库存 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        metrics = row["metrics"]
        files = "未扫描" if metrics is None else str(metrics["file_count"])
        size = "未扫描" if metrics is None else str(metrics["total_file_bytes"])
        table.append(
            "| `{}` | {} | {} | {} | {} | {} |".format(
                row["path"],
                row["identity"],
                row["git_policy"],
                files,
                size,
                "是" if row["high_frequency_inventory_only"] else "否",
            )
        )
    extra = "、".join(f"`{item}`" for item in unregistered) or "无"
    return _markdown_source(
        "# 仓库结构\n\n"
        "目录职责来自 `governance/directory_registry.json`；数量和体量只做机械观察，"
        "不读取文件内容，也不跟随软链。\n\n"
        + "\n".join(table)
        + f"\n\n未登记的顶层目录：{extra}。目录存在不代表可删、可续跑或是现役。"
    )


def render_current_state(current: dict[str, Any]) -> bytes:
    repo = current["repository"]
    ft = current["domains"]["finetuning"]
    return _markdown_source(
        f"""# 当前状态投影

## 全仓执行状态

- 任务：{repo['task']['label']}（`{repo['task']['task_id']}`）
- 状态：{repo['task']['status_label']}
- 当前运行：`{repo['run']['run_id']}`
- 下一动作：{repo['next_action']}
- 来源：`{repo['source_path']}`，SHA `{repo['source_sha256']}`
- 来源自己声明的时间：`{repo['source_snapshot_at'] or 'unknown'}`

## 微调域

- 当前实验：`{ft['current_experiment_id']}`
- MANIFEST：`{ft['manifest_path']}`
- MANIFEST SHA：`{ft['manifest_sha256']}`
- 当前指针只负责导航：`{ft['pointer_scope']}`

⚠️ 来源可验证，不代表来源仍然新鲜。机器新鲜度看 ZIP 同目录的 `BUILD_RECEIPTS/`；构建时间和新鲜度不进入稳定 `snapshot_id`。

本页是 snapshot 当时的只读投影，不是第二份 CURRENT。"""
    )


def render_decisions(decisions: dict[str, Any]) -> bytes:
    evidence = "\n".join(
        f"- `{item}`" for item in decisions["decision_evidence_ids"]
    ) or "- 无"
    return _markdown_source(
        f"""# 决定视图

- 覆盖率：`{decisions['coverage']}`
- 正式结构化事件：{decisions['formal_event_count']}
- ChatGPT proposal inbox 是否属于正式决定历史：否

当前只登记这些决定证据：

{evidence}

历史 `history/root-legacy-202607/decisions.md` 不由 AI 自动重写成正式事件。ChatGPT 回包只进 TEMP 收件箱。"""
    )


def render_evidence(evidence: Sequence[dict[str, Any]]) -> bytes:
    lines = ["# 关键证据索引", ""]
    for row in evidence:
        lines.append(
            f"- `{row['evidence_id']}`：`{row['path']}`；SHA `{row['sha256']}`；"
            f"范围＝{row['authority_scope']}；内容未复制"
        )
    return _markdown_source("\n".join(lines))


def review_template(
    snapshot: dict[str, Any],
    handoff: dict[str, Any],
    package_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "repo-bridge-review-v1",
        "review_id": "chatgpt-review-REPLACE-ME",
        "reply_to_snapshot_id": snapshot["snapshot_id"],
        "reply_to_snapshot_digest_sha256": snapshot["snapshot_digest_sha256"],
        "reply_to_package_id": package_id,
        "reply_to_handoff_id": handoff["handoff_id"],
        "review_scope": {
            "domains": handoff["review_scope"]["domains"],
            "paths": handoff["review_scope"]["paths"],
            "decision_ids": [],
            "evidence_ids": handoff["review_scope"]["evidence_ids"],
        },
        "summary": "请替换为对本次交接的审查结论",
        "findings": [],
        "open_questions": [],
        "execution_authorization": False,
    }


def render_return_instructions(
    snapshot: dict[str, Any],
    handoff: dict[str, Any],
    package_id: str,
) -> bytes:
    return _markdown_source(
        f"""# ChatGPT 回程说明

请读取本包后，按 `_bridge/schemas/REVIEW_RETURN.schema.json` 填写 `_bridge/CHATGPT_RETURN_TEMPLATE.json`，返回单独文件：

```text
CHATGPT_RETURN.json
```

必须保留：

- `reply_to_snapshot_id`＝`{snapshot['snapshot_id']}`；
- `reply_to_snapshot_digest_sha256`＝`{snapshot['snapshot_digest_sha256']}`；
- `reply_to_package_id`＝`{package_id}`；
- `reply_to_handoff_id`＝`{handoff['handoff_id']}`；
- 所有 finding 的 `kind` 只能是 `proposal`；
- `execution_authorization` 必须是 `false`；
- `review_scope` 要列清实际依赖的业务域、路径和 evidence ID。

当前相关性判断粒度是文件级（`file_level`），没有声称已经做到字段级判断。

不要声称建议已经得到 CZ 批准，也不要把 Markdown 冒充机器回程。"""
    )


def build_payloads(
    root: Path,
    components: dict[str, Any],
    handoff: dict[str, Any],
    handoff_data: bytes,
) -> tuple[dict[str, bytes], str]:
    snapshot = components["snapshot"]
    handoff_sha = sha256_bytes(handoff_data)
    package_digest = sha256_bytes(
        canonical_json(
            {
                "snapshot_digest_sha256": snapshot["snapshot_digest_sha256"],
                "observation_digest_sha256": snapshot["observation_digest_sha256"],
                "handoff_sha256": handoff_sha,
                "package_schema": "repo-bridge-full-package-v1",
            }
        )
    )
    package_id = "pkg1-" + package_digest[:20]
    current_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-current-state-view-v1",
        **components["current_state"],
    )
    directory_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-directory-summary-v1",
        observation_id=snapshot["observation_id"],
        directories=components["directory_rows"],
        unregistered_top_level_directories=components[
            "unregistered_top_level_directories"
        ],
    )
    evidence_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-evidence-index-v1",
        evidence=components["evidence"],
    )
    source_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-source-bindings-v1",
        relevance_granularity=RELEVANCE_GRANULARITY,
        bindings=components["source_bindings"],
    )
    handoff_binding_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-handoff-binding-v1",
        package_id=package_id,
        handoff_id=handoff["handoff_id"],
        handoff_sha256=handoff_sha,
    )
    changes_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-changes-v1",
        relation="no_base_full_snapshot",
        semantic_changes=[],
        inventory_changes=[],
    )
    questions_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-open-questions-v1",
        handoff_id=handoff["handoff_id"],
        questions=handoff["questions"],
    )
    exclusions_view = derived_view(
        snapshot["snapshot_id"],
        schema_version="repo-bridge-exclusions-v1",
        content_not_collected=[
            "novel_body",
            "private_gold_content",
            "model_weights",
            "checkpoints",
            "training_logs",
            "raw_answers",
            "credentials",
        ],
        high_frequency_inventory_only=components["config"]["inventory"][
            "high_frequency_roots"
        ],
        inventory_does_not_change_snapshot_id=True,
    )
    template = review_template(snapshot, handoff, package_id)
    validate_json(
        template,
        CONTRACTS_DIR / "REVIEW_RETURN.schema.json",
        code="REVIEW_TEMPLATE_SCHEMA_INVALID",
    )
    payloads = {
        "00_HANDOFF.md": render_handoff(handoff, snapshot),
        "01_REPO_SNAPSHOT.md": render_snapshot(snapshot),
        "02_STRUCTURE.md": render_structure(
            components["directory_rows"],
            components["unregistered_top_level_directories"],
        ),
        "03_CURRENT_STATE.md": render_current_state(components["current_state"]),
        "04_DECISIONS.md": render_decisions(components["decisions"]),
        "05_CHANGES_SINCE_LAST.md": _markdown_source(
            "# 相对变化\n\n这是第一份 FULL，没有提供基准 snapshot，暂不生成 delta。"
        ),
        "06_OPEN_QUESTIONS.md": _markdown_source(
            "# 待回答问题\n\n" + "\n".join(f"- {q}" for q in handoff["questions"])
        ),
        "07_EVIDENCE_INDEX.md": render_evidence(components["evidence"]),
        "08_RETURN_INSTRUCTIONS.md": render_return_instructions(
            snapshot,
            handoff,
            package_id,
        ),
        "_bridge/SNAPSHOT.json": canonical_json(snapshot),
        "_bridge/DIRECTORY_SUMMARY.json": canonical_json(directory_view),
        "_bridge/CURRENT_STATE.json": canonical_json(current_view),
        "_bridge/DECISION_EVENTS.jsonl": b"",
        "_bridge/DECISIONS.jsonl": b"",
        "_bridge/CHANGES.json": canonical_json(changes_view),
        "_bridge/OPEN_QUESTIONS.json": canonical_json(questions_view),
        "_bridge/EVIDENCE_INDEX.json": canonical_json(evidence_view),
        "_bridge/SOURCE_BINDINGS.json": canonical_json(source_view),
        HANDOFF_BINDING_MEMBER: canonical_json(handoff_binding_view),
        "_bridge/EXCLUSIONS.json": canonical_json(exclusions_view),
        "_bridge/CHATGPT_RETURN_TEMPLATE.json": canonical_json(template),
        "_bridge/schemas/REVIEW_RETURN.schema.json": (
            CONTRACTS_DIR / "REVIEW_RETURN.schema.json"
        ).read_bytes(),
    }
    secret_scan = scan_payload_secrets(root, payloads)
    if secret_scan["result"] != "PASS":
        raise BridgeError("PACKAGE_SECRET_SCAN_FAILED", json.dumps(secret_scan))
    payloads[SECRET_SCAN_MEMBER] = canonical_json(secret_scan)
    return payloads, package_id


def _zip_member_name(value: str) -> str:
    if "\\" in value:
        raise BridgeError("UNSAFE_ZIP_MEMBER", value)
    pure = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        not value
        or pure.is_absolute()
        or bool(windows.drive)
        or any(part in {"", ".", ".."} for part in pure.parts)
        or value.endswith("/")
        or pure.as_posix() != value
    ):
        raise BridgeError("UNSAFE_ZIP_MEMBER", value)
    return value


def _write_deterministic_zip(path: Path, members: Mapping[str, bytes]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for member, data in sorted(members.items()):
                info = zipfile.ZipInfo(member, FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, data)
        if path.exists():
            if sha256_file(path) != sha256_file(temporary):
                raise BridgeError("PACKAGE_CREATE_ONLY_CONFLICT", str(path))
            temporary.unlink()
        else:
            os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_members(
    payloads: Mapping[str, bytes],
    snapshot: dict[str, Any],
    package_id: str,
) -> dict[str, bytes]:
    safe_payloads = {_zip_member_name(path): data for path, data in payloads.items()}
    if len(safe_payloads) != len(payloads):
        raise BridgeError("DUPLICATE_ZIP_MEMBER")
    rows = [
        {"path": path, "bytes": len(data), "sha256": sha256_bytes(data)}
        for path, data in sorted(safe_payloads.items())
    ]
    handoff_binding = read_json_bytes(
        safe_payloads[HANDOFF_BINDING_MEMBER],
        code="HANDOFF_BINDING_INVALID",
    )
    recorded_scan = read_json_bytes(
        safe_payloads[SECRET_SCAN_MEMBER],
        code="SECRET_SCAN_INVALID",
    )
    scanned_members = recorded_scan.get("scanned_members")
    expected_scanned_members = sorted(set(safe_payloads) - {SECRET_SCAN_MEMBER})
    if (
        scanned_members != expected_scanned_members
        or recorded_scan.get("scanned_member_count") != len(expected_scanned_members)
    ):
        raise BridgeError("SECRET_SCAN_MEMBER_SET_MISMATCH")
    final_member_names = set(safe_payloads) | {PACKAGE_MANIFEST, PACKAGE_SHA256SUMS}
    count_contract = {
        "schema_version": "repo-bridge-member-count-contract-v1",
        "zip_member_count": len(final_member_names),
        "manifested_member_count": len(rows),
        "manifest_excluded_members": sorted(
            {PACKAGE_MANIFEST, PACKAGE_SHA256SUMS}
        ),
        "sha256sums_member_count": len(final_member_names) - 1,
        "sha256sums_excluded_members": [PACKAGE_SHA256SUMS],
        "secret_scan_scanned_member_count": len(scanned_members),
        "secret_scan_excluded_members": sorted(
            final_member_names - set(scanned_members)
        ),
    }
    manifest = canonical_json(
        {
            "schema_version": "repo-bridge-package-manifest-v1",
            "package_kind": "full",
            "package_id": package_id,
            "handoff_id": handoff_binding["handoff_id"],
            "handoff_sha256": handoff_binding["handoff_sha256"],
            "snapshot_id": snapshot["snapshot_id"],
            "snapshot_digest_sha256": snapshot["snapshot_digest_sha256"],
            "observation_id": snapshot["observation_id"],
            "payload_file_count": len(rows),
            "member_count_contract": count_contract,
            "files": rows,
        }
    )
    members = dict(safe_payloads)
    members[PACKAGE_MANIFEST] = manifest
    sums = "".join(
        f"{sha256_bytes(data)}  {path}\n" for path, data in sorted(members.items())
    ).encode("utf-8")
    members[PACKAGE_SHA256SUMS] = sums
    return members


def write_full_package(
    root: Path,
    payloads: Mapping[str, bytes],
    snapshot: dict[str, Any],
    package_id: str,
) -> dict[str, Any]:
    export_dir = root / OUTPUT_ROOT_RELATIVE / "exports" / package_id
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"CHATGPT_CODEX_BRIDGE_{snapshot['snapshot_id']}_{package_id}.zip"
    zip_path = export_dir / zip_name
    members = package_members(payloads, snapshot, package_id)
    _write_deterministic_zip(zip_path, members)
    verification = verify_package(root, zip_path)
    receipt = {
        "schema_version": "repo-bridge-outbound-receipt-v1",
        "status": "OUTBOUND_READY_REAL_RETURN_PENDING",
        "snapshot_id": snapshot["snapshot_id"],
        "observation_id": snapshot["observation_id"],
        "package_id": package_id,
        "zip_relative_path": zip_path.relative_to(root).as_posix(),
        "zip_sha256": verification["zip_sha256"],
        "zip_bytes": verification["zip_bytes"],
        "verification_passed": True,
        "real_chatgpt_return_received": False,
    }
    receipt_path = export_dir / "OUTBOUND_RECEIPT.json"
    receipt_data = canonical_json(receipt)
    if receipt_path.exists() and receipt_path.read_bytes() != receipt_data:
        raise BridgeError("OUTBOUND_RECEIPT_CREATE_ONLY_CONFLICT")
    if not receipt_path.exists():
        receipt_path.write_bytes(receipt_data)
    generated_at = datetime.now(timezone.utc)
    current_view = read_json_bytes(
        payloads["_bridge/CURRENT_STATE.json"],
        code="CURRENT_STATE_VIEW_INVALID",
    )
    repository_state = current_view.get("repository") or {}
    freshness = assess_source_freshness(
        repository_state.get("source_snapshot_at"),
        generated_at,
    )
    build_receipt_core = {
        "schema_version": "repo-bridge-build-receipt-v1",
        "generated_at": _utc_text(generated_at),
        "snapshot_id": snapshot["snapshot_id"],
        "observation_id": snapshot["observation_id"],
        "package_id": package_id,
        "zip_relative_path": zip_path.relative_to(root).as_posix(),
        "source_path": repository_state.get("source_path"),
        **freshness,
        "freshness_affects_snapshot_id": False,
    }
    build_id = "build1-" + sha256_bytes(canonical_json(build_receipt_core))[:20]
    build_receipt = {**build_receipt_core, "build_id": build_id}
    build_receipt_dir = export_dir / "BUILD_RECEIPTS"
    build_receipt_dir.mkdir(parents=True, exist_ok=True)
    build_receipt_path = build_receipt_dir / f"{build_id}.json"
    build_receipt_data = canonical_json(build_receipt)
    if (
        build_receipt_path.exists()
        and build_receipt_path.read_bytes() != build_receipt_data
    ):
        raise BridgeError("BUILD_RECEIPT_CREATE_ONLY_CONFLICT")
    if not build_receipt_path.exists():
        build_receipt_path.write_bytes(build_receipt_data)
    return {
        **receipt,
        "build_receipt_relative_path": build_receipt_path.relative_to(
            root
        ).as_posix(),
        "generated_at": build_receipt["generated_at"],
        "source_declared_at": build_receipt["source_declared_at"],
        "freshness": build_receipt["freshness"],
    }


def _read_zip_members(path: Path) -> dict[str, bytes]:
    if not path.is_file() or path.is_symlink():
        raise BridgeError("ZIP_NOT_PLAIN_FILE", str(path))
    if path.stat().st_size > MAX_ZIP_TOTAL_BYTES:
        raise BridgeError("ZIP_TOO_LARGE", str(path.stat().st_size))
    members: dict[str, bytes] = {}
    casefolded: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_MEMBERS:
            raise BridgeError("ZIP_TOO_MANY_MEMBERS")
        if archive.testzip() is not None:
            raise BridgeError("ZIP_CRC_FAILED")
        total = 0
        for info in infos:
            name = _zip_member_name(info.filename)
            folded = name.casefold()
            if name in members or folded in casefolded:
                raise BridgeError("ZIP_DUPLICATE_OR_CASEFOLD_MEMBER", name)
            casefolded.add(folded)
            mode = (info.external_attr >> 16) & 0o170000
            if mode and mode != stat.S_IFREG:
                raise BridgeError("ZIP_NON_REGULAR_MEMBER", name)
            if info.file_size > MAX_ZIP_MEMBER_BYTES:
                raise BridgeError("ZIP_MEMBER_TOO_LARGE", name)
            total += info.file_size
            if total > MAX_ZIP_TOTAL_BYTES:
                raise BridgeError("ZIP_EXPANDED_TOO_LARGE")
            members[name] = archive.read(info)
    return members


def verify_package(root: Path, path: Path) -> dict[str, Any]:
    members = _read_zip_members(path)
    expected_members = (
        REQUIRED_MEMBERS
        if HANDOFF_BINDING_MEMBER in members
        else LEGACY_REQUIRED_MEMBERS
    )
    missing = sorted(expected_members - set(members))
    extra = sorted(set(members) - expected_members)
    if missing or extra:
        raise BridgeError(
            "ZIP_MEMBER_SET_MISMATCH",
            json.dumps({"missing": missing, "extra": extra}, ensure_ascii=False),
        )
    manifest = read_json_bytes(
        members[PACKAGE_MANIFEST],
        code="PACKAGE_MANIFEST_INVALID",
    )
    if manifest.get("schema_version") != "repo-bridge-package-manifest-v1":
        raise BridgeError("PACKAGE_MANIFEST_SCHEMA_UNSUPPORTED")
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise BridgeError("PACKAGE_MANIFEST_FILES_INVALID")
    if manifest.get("payload_file_count") != len(rows):
        raise BridgeError("PACKAGE_MANIFEST_COUNT_MISMATCH")
    expected_payload_names = set(members) - {PACKAGE_MANIFEST, PACKAGE_SHA256SUMS}
    manifest_names = {row.get("path") for row in rows if isinstance(row, dict)}
    if manifest_names != expected_payload_names or len(rows) != len(manifest_names):
        raise BridgeError("PACKAGE_MANIFEST_MEMBER_SET_MISMATCH")
    for row in rows:
        data = members[row["path"]]
        if row.get("bytes") != len(data) or row.get("sha256") != sha256_bytes(data):
            raise BridgeError("PACKAGE_MANIFEST_HASH_MISMATCH", row["path"])
    sums: dict[str, str] = {}
    try:
        for line in members[PACKAGE_SHA256SUMS].decode("utf-8").splitlines():
            digest, name = line.split("  ", 1)
            sums[name] = digest
    except (UnicodeError, ValueError) as exc:
        raise BridgeError("PACKAGE_SHA256SUMS_INVALID") from exc
    expected_sums = set(members) - {PACKAGE_SHA256SUMS}
    if set(sums) != expected_sums:
        raise BridgeError("PACKAGE_SHA256SUMS_MEMBER_SET_MISMATCH")
    for name, digest in sums.items():
        if digest != sha256_bytes(members[name]):
            raise BridgeError("PACKAGE_SHA256SUMS_MISMATCH", name)
    recorded_scan = read_json_bytes(
        members[SECRET_SCAN_MEMBER],
        code="SECRET_SCAN_INVALID",
    )
    count_contract = manifest.get("member_count_contract")
    if count_contract is not None:
        scanned_members = recorded_scan.get("scanned_members")
        if not isinstance(scanned_members, list) or not all(
            isinstance(name, str) for name in scanned_members
        ):
            raise BridgeError("SECRET_SCAN_MEMBER_LIST_INVALID")
        expected_count_contract = {
            "schema_version": "repo-bridge-member-count-contract-v1",
            "zip_member_count": len(members),
            "manifested_member_count": len(rows),
            "manifest_excluded_members": sorted(
                {PACKAGE_MANIFEST, PACKAGE_SHA256SUMS}
            ),
            "sha256sums_member_count": len(sums),
            "sha256sums_excluded_members": [PACKAGE_SHA256SUMS],
            "secret_scan_scanned_member_count": len(scanned_members),
            "secret_scan_excluded_members": sorted(
                set(members) - set(scanned_members)
            ),
        }
        if count_contract != expected_count_contract:
            raise BridgeError("PACKAGE_MEMBER_COUNT_CONTRACT_MISMATCH")
    snapshot = read_json_bytes(members["_bridge/SNAPSHOT.json"], code="SNAPSHOT_INVALID")
    validate_json(
        snapshot,
        CONTRACTS_DIR / "SNAPSHOT.schema.json",
        code="SNAPSHOT_SCHEMA_INVALID",
    )
    if manifest.get("snapshot_id") != snapshot["snapshot_id"]:
        raise BridgeError("PACKAGE_SNAPSHOT_BINDING_MISMATCH")
    for name in DERIVED_JSON_VIEWS:
        if name == HANDOFF_BINDING_MEMBER and name not in members:
            continue
        view = read_json_bytes(members[name], code="DERIVED_VIEW_INVALID")
        if view.get("view_kind") != "derived_snapshot_view" or view.get("authoritative") is not False:
            raise BridgeError("DERIVED_VIEW_AUTHORITY_VIOLATION", name)
        if view.get("snapshot_id") != snapshot["snapshot_id"]:
            raise BridgeError("DERIVED_VIEW_SNAPSHOT_MISMATCH", name)
    review_schema = read_json_bytes(
        members["_bridge/schemas/REVIEW_RETURN.schema.json"],
        code="EMBEDDED_REVIEW_SCHEMA_INVALID",
    )
    template = read_json_bytes(
        members["_bridge/CHATGPT_RETURN_TEMPLATE.json"],
        code="EMBEDDED_REVIEW_TEMPLATE_INVALID",
    )
    try:
        Draft202012Validator.check_schema(review_schema)
        Draft202012Validator(review_schema).validate(template)
    except (SchemaError, ValidationError) as exc:
        raise BridgeError("EMBEDDED_REVIEW_CONTRACT_INVALID", str(exc)) from exc
    required_review_fields = set(review_schema.get("required") or [])
    package_binding_fields = {"reply_to_package_id", "reply_to_handoff_id"}
    if package_binding_fields.issubset(required_review_fields):
        if HANDOFF_BINDING_MEMBER not in members:
            raise BridgeError("HANDOFF_BINDING_MEMBER_MISSING")
        handoff_binding = read_json_bytes(
            members[HANDOFF_BINDING_MEMBER],
            code="HANDOFF_BINDING_INVALID",
        )
        if (
            handoff_binding.get("package_id") != manifest.get("package_id")
            or handoff_binding.get("handoff_id") != manifest.get("handoff_id")
            or handoff_binding.get("handoff_sha256")
            != manifest.get("handoff_sha256")
            or template.get("reply_to_package_id") != manifest.get("package_id")
            or template.get("reply_to_handoff_id") != manifest.get("handoff_id")
        ):
            raise BridgeError("PACKAGE_HANDOFF_BINDING_MISMATCH")
    scan_targets = {
        name: data for name, data in members.items() if name != SECRET_SCAN_MEMBER
    }
    scan = scan_payload_secrets(root, scan_targets)
    if scan["result"] != "PASS" or recorded_scan.get("result") != "PASS":
        raise BridgeError("PACKAGE_SECRET_SCAN_FAILED")
    return {
        "schema_version": "repo-bridge-package-verification-v1",
        "status": "PASS",
        "snapshot_id": snapshot["snapshot_id"],
        "observation_id": snapshot["observation_id"],
        "package_id": manifest["package_id"],
        "zip_sha256": sha256_file(path),
        "zip_bytes": path.stat().st_size,
        "member_count": len(members),
        "member_count_contract": (
            "explicit_v1" if count_contract is not None else "legacy_implicit"
        ),
        "manifested_member_count": len(rows),
        "secret_scan_scanned_member_count": recorded_scan.get(
            "scanned_member_count"
        ),
        "manifest_excluded_members": (
            count_contract.get("manifest_excluded_members")
            if isinstance(count_contract, dict)
            else [PACKAGE_MANIFEST, PACKAGE_SHA256SUMS]
        ),
        "secret_scan_excluded_members": (
            count_contract.get("secret_scan_excluded_members")
            if isinstance(count_contract, dict)
            else "legacy_implicit"
        ),
        "crc_passed": True,
        "secret_scan_passed": True,
    }


def read_package(path: Path) -> dict[str, Any]:
    members = _read_zip_members(path)
    return {
        "members": members,
        "manifest": read_json_bytes(
            members[PACKAGE_MANIFEST],
            code="PACKAGE_MANIFEST_INVALID",
        ),
        "snapshot": read_json_bytes(members["_bridge/SNAPSHOT.json"], code="SNAPSHOT_INVALID"),
        "handoff_binding": (
            read_json_bytes(
                members[HANDOFF_BINDING_MEMBER],
                code="HANDOFF_BINDING_INVALID",
            )
            if HANDOFF_BINDING_MEMBER in members
            else None
        ),
        "bindings": read_json_bytes(
            members["_bridge/SOURCE_BINDINGS.json"],
            code="SOURCE_BINDINGS_INVALID",
        )["bindings"],
        "evidence": read_json_bytes(
            members["_bridge/EVIDENCE_INDEX.json"],
            code="EVIDENCE_INDEX_INVALID",
        )["evidence"],
    }


def _mapping(rows: Sequence[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows}


def compare_package_to_current(
    package: dict[str, Any],
    current: dict[str, Any],
    review: dict[str, Any] | None,
) -> dict[str, Any]:
    old_snapshot = package["snapshot"]
    new_snapshot = current["snapshot"]
    old_bindings = _mapping(package["bindings"], "source_id")
    new_bindings = _mapping(current["source_bindings"], "source_id")
    changed_paths: set[str] = set()
    for source_id in set(old_bindings) | set(new_bindings):
        old = old_bindings.get(source_id)
        new = new_bindings.get(source_id)
        if old != new:
            if old:
                changed_paths.add(old["path"])
            if new:
                changed_paths.add(new["path"])
    old_dirty = _mapping(old_snapshot["git"]["dirty_entries"], "path")
    new_dirty = _mapping(new_snapshot["git"]["dirty_entries"], "path")
    for path in set(old_dirty) | set(new_dirty):
        if old_dirty.get(path) != new_dirty.get(path):
            changed_paths.add(path)
    old_evidence = _mapping(package["evidence"], "evidence_id")
    new_evidence = _mapping(current["evidence"], "evidence_id")
    changed_evidence_ids = sorted(
        evidence_id
        for evidence_id in set(old_evidence) | set(new_evidence)
        if old_evidence.get(evidence_id) != new_evidence.get(evidence_id)
    )
    inventory_changed = (
        old_snapshot["inventory_fingerprint_sha256"]
        != new_snapshot["inventory_fingerprint_sha256"]
    )
    if old_snapshot["snapshot_digest_sha256"] == new_snapshot["snapshot_digest_sha256"]:
        relation = "exact_match"
        relevant = []
    elif review is None:
        relation = "changed_relevant"
        relevant = sorted(changed_paths)
    else:
        scope = review["review_scope"]
        relevant: list[str] = []
        for path in sorted(changed_paths):
            if any(
                path == scope_path.rstrip("/")
                or path.startswith(scope_path.rstrip("/") + "/")
                for scope_path in scope["paths"]
            ):
                relevant.append(path)
        for evidence_id in changed_evidence_ids:
            if evidence_id in scope["evidence_ids"]:
                relevant.append("evidence:" + evidence_id)
        changed_domains = {
            "finetuning" for path in changed_paths if path.startswith("finetuning/")
        }
        if changed_domains.intersection(scope["domains"]):
            relevant.extend("domain:" + item for item in sorted(changed_domains))
        relation = "changed_relevant" if relevant else "changed_unrelated"
    return {
        "schema_version": "repo-bridge-status-v1",
        "relation": relation,
        "relevance_granularity": RELEVANCE_GRANULARITY,
        "base_snapshot_id": old_snapshot["snapshot_id"],
        "current_snapshot_id": new_snapshot["snapshot_id"],
        "inventory_changed": inventory_changed,
        "changed_paths": sorted(changed_paths),
        "changed_evidence_ids": changed_evidence_ids,
        "relevant_changes": sorted(set(relevant)),
        "direct_execution_allowed": False,
    }


def health_check(root: Path, config_path: Path) -> dict[str, Any]:
    components = build_snapshot_components(root, config_path, include_inventory=False)
    warnings = []
    if components["decisions"]["coverage"] != "complete":
        warnings.append("decision coverage is partial_registered_only")
    return {
        "schema_version": "repo-bridge-health-v1",
        "status": "PASS",
        "snapshot_id": components["snapshot"]["snapshot_id"],
        "adapter_count": len(components["config"]["semantic_sources"]),
        "source_binding_count": len(components["source_bindings"]),
        "evidence_count": len(components["evidence"]),
        "warnings": warnings,
    }


def load_handoff(root: Path, path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise BridgeError("HANDOFF_OUTSIDE_REPO", str(path)) from exc
    data = read_stable_repo_file(root, relative, max_bytes=1024 * 1024)
    value = read_json_bytes(data, code="HANDOFF_INVALID_JSON")
    validate_json(
        value,
        CONTRACTS_DIR / "HANDOFF_INPUT.schema.json",
        code="HANDOFF_SCHEMA_INVALID",
    )
    return value, data


def load_review(path: Path, schema: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], bytes]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
        raise BridgeError("REVIEW_NOT_SAFE_FILE", str(path))
    data = path.read_bytes()
    value = read_json_bytes(data, code="REVIEW_INVALID_JSON")
    if schema is None:
        validate_json(
            value,
            CONTRACTS_DIR / "REVIEW_RETURN.schema.json",
            code="REVIEW_SCHEMA_INVALID",
        )
    else:
        try:
            Draft202012Validator.check_schema(dict(schema))
            Draft202012Validator(dict(schema)).validate(value)
        except (SchemaError, ValidationError) as exc:
            raise BridgeError("REVIEW_SCHEMA_INVALID", str(exc)) from exc
    return value, data


def import_review(
    root: Path,
    config_path: Path,
    review_path: Path,
    snapshot_path: Path,
) -> dict[str, Any]:
    verify_package(root, snapshot_path)
    package = read_package(snapshot_path)
    embedded_schema = read_json_bytes(
        package["members"]["_bridge/schemas/REVIEW_RETURN.schema.json"],
        code="EMBEDDED_REVIEW_SCHEMA_INVALID",
    )
    review, review_data = load_review(review_path, embedded_schema)
    snapshot = package["snapshot"]
    if (
        review["reply_to_snapshot_id"] != snapshot["snapshot_id"]
        or review["reply_to_snapshot_digest_sha256"]
        != snapshot["snapshot_digest_sha256"]
    ):
        raise BridgeError("REVIEW_SNAPSHOT_BINDING_MISMATCH")
    handoff_binding = package["handoff_binding"]
    if handoff_binding is not None:
        if review.get("reply_to_package_id") != package["manifest"].get("package_id"):
            raise BridgeError("REVIEW_PACKAGE_BINDING_MISMATCH")
        if review.get("reply_to_handoff_id") != handoff_binding.get("handoff_id"):
            raise BridgeError("REVIEW_HANDOFF_BINDING_MISMATCH")
    current = build_snapshot_components(root, config_path, include_inventory=True)
    status = compare_package_to_current(package, current, review)
    inbox = root / OUTPUT_ROOT_RELATIVE / "inbox" / review["review_id"]
    inbox.mkdir(parents=True, exist_ok=True)
    original_path = inbox / "CHATGPT_RETURN.json"
    if original_path.exists() and original_path.read_bytes() != review_data:
        raise BridgeError("REVIEW_CREATE_ONLY_CONFLICT")
    if not original_path.exists():
        original_path.write_bytes(review_data)
    hard_stop = status["relation"] in {"changed_relevant", "cannot_assess"}
    receipt = {
        "schema_version": "repo-bridge-review-import-receipt-v1",
        "status": "HARD_STOP_REVIEW_STALE" if hard_stop else "RECEIVED_CZ_REVIEW_REQUIRED",
        "review_id": review["review_id"],
        "review_sha256": sha256_bytes(review_data),
        "proposal_inbox_relative_path": inbox.relative_to(root).as_posix(),
        "relation": status["relation"],
        "status_detail": status,
        "formal_decision_event_created": False,
        "execution_authorized": False,
        "real_chatgpt_return": True,
    }
    if handoff_binding is not None:
        receipt.update(
            {
                "package_id": package["manifest"]["package_id"],
                "handoff_id": handoff_binding["handoff_id"],
                "review_binding": "snapshot_package_handoff",
            }
        )
    receipt_path = inbox / "IMPORT_RECEIPT.json"
    receipt_data = canonical_json(receipt)
    if receipt_path.exists() and receipt_path.read_bytes() != receipt_data:
        raise BridgeError("IMPORT_RECEIPT_CREATE_ONLY_CONFLICT")
    if not receipt_path.exists():
        receipt_path.write_bytes(receipt_data)
    return receipt


def command_health(args: argparse.Namespace) -> int:
    result = health_check(ROOT, CONFIG_PATH)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def command_build(args: argparse.Namespace) -> int:
    health_check(ROOT, CONFIG_PATH)
    handoff, handoff_data = load_handoff(ROOT, args.handoff)
    components = build_snapshot_components(ROOT, CONFIG_PATH, include_inventory=True)
    payloads, package_id = build_payloads(ROOT, components, handoff, handoff_data)
    receipt = write_full_package(
        ROOT,
        payloads,
        components["snapshot"],
        package_id,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def command_verify(args: argparse.Namespace) -> int:
    result = verify_package(ROOT, args.zip_path)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def command_status(args: argparse.Namespace) -> int:
    verify_package(ROOT, args.snapshot)
    package = read_package(args.snapshot)
    current = build_snapshot_components(ROOT, CONFIG_PATH, include_inventory=True)
    result = compare_package_to_current(package, current, None)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["relation"] == "exact_match" else 2


def command_import_review(args: argparse.Namespace) -> int:
    result = import_review(ROOT, CONFIG_PATH, args.review, args.snapshot)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["status"].startswith("HARD_STOP") else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repo Bridge V1 候选原型")
    subparsers = parser.add_subparsers(dest="command", required=True)
    health = subparsers.add_parser("health", help="检查真源和适配器，零写入")
    health.set_defaults(func=command_health)
    build = subparsers.add_parser("build", help="生成真实 FULL Bridge ZIP")
    build.add_argument("--handoff", type=Path, required=True)
    build.set_defaults(func=command_build)
    verify = subparsers.add_parser("verify", help="回读验证 FULL Bridge ZIP")
    verify.add_argument("zip_path", type=Path)
    verify.set_defaults(func=command_verify)
    status_parser = subparsers.add_parser("status", help="检查旧快照是否过期")
    status_parser.add_argument("--snapshot", type=Path, required=True)
    status_parser.set_defaults(func=command_status)
    import_parser = subparsers.add_parser(
        "import-review",
        help="校验真实 ChatGPT 回包并写 TEMP 收件票",
    )
    import_parser.add_argument("--review", type=Path, required=True)
    import_parser.add_argument("--snapshot", type=Path, required=True)
    import_parser.set_defaults(func=command_import_review)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except BridgeError as exc:
        print(
            json.dumps(
                {"status": "HARD_STOP", "code": exc.code, "detail": exc.detail},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
