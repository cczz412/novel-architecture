"""从机器真源生成治理索引，不改历史运行工件。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from pipeline_common.artifacts import (  # noqa: E402
    ArtifactError,
    build_manifest,
    read_json,
    resolve_repo_path,
    sha256_file,
    verify_manifest,
    write_json_atomic,
    write_text_atomic,
)


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = "governance/control_plane.json"
CURRENT_STATE_PATH = "governance/CURRENT_STATE.json"
ROUTE_REGISTRY_PATH = "governance/route_registry.json"
REGISTRY_SOURCE_PATH = "governance/module_registry.source.json"

GENERATED_PATHS = [
    "governance/INDEX.md",
    "governance/current_run.md",
    "governance/module_registry.json",
    "governance/dependency_map.json",
    "governance/indexes/gold_current.md",
    "governance/indexes/silver_candidates.md",
    "governance/indexes/runs_and_reports.md",
    "governance/indexes/source_registry.md",
    "governance/indexes/route_health.md",
    "experiments/INDEX.md",
]

STATUS_VALUES = {"可用", "在改", "试验"}
ROUTE_STATUS_VALUES = {"in_trial", "failed", "retired", "allowed_to_reopen"}
CURRENT_STATE_SCHEMA_V2 = "governance-current-state-v2"
LEGACY_CURRENT_STATE_SCHEMA = "governance-current-state-v1"
LEGACY_TOP_LEVEL_STATE_KEYS = {
    "current_step",
    "accepted_steps",
    "mainline",
    "run_states",
    "open_issues",
    "closure_policy",
}
RESTRUCTURE_BASELINE_PLAN_V1 = "repository-restructure-baseline-plan-v1"
RESTRUCTURE_BASELINE_RECEIPT_V1 = "repository-restructure-baseline-receipt-v1"
RESTRUCTURE_WAVE_PLAN_V1 = "repository-restructure-wave-plan-v1"
RESTRUCTURE_WAVE_RECEIPT_V1 = "repository-restructure-wave-receipt-v1"
RESTRUCTURE_WAVE_COMPLETION_V1 = "repository-restructure-wave-completion-v1"
RESTRUCTURE_DECISION_TICKET_V1 = "repository-restructure-decision-ticket-v1"
RESTRUCTURE_WAVE_LOCK_REQUEST_V1 = "repository-restructure-wave-lock-request-v1"
RESTRUCTURE_WAVE_LOCK_RECEIPT_V1 = "repository-restructure-wave-lock-receipt-v1"
RESTRUCTURE_TEST_IMPACT_V1 = "repository-restructure-test-impact-v1"
RESTRUCTURE_BASELINE_REQUIRED_INPUTS = {
    "AGENTS.md",
    CURRENT_STATE_PATH,
    CONTROL_PATH,
    "governance/module_registry.json",
    "governance/index_manifest.json",
    "tools/governance_index.py",
}
RESTRUCTURE_BASELINE_FIXED_READ_SCOPES = {
    ".git",
    "AGENTS.md",
    "README.md",
    "TEMP/restructure_wave_preflight",
    "config",
    "experiments",
    "foundation",
    "governance",
    "history",
    "intake",
    "outbox",
    "references",
    "reports",
    "runs",
    "seed",
    "side-tracks",
    "tests",
    "tools",
    "work",
}
RESTRUCTURE_WAVE_FIXED_READ_SCOPES = {
    ".git",
    ".gitignore",
    "AGENTS.md",
    "TEMP/restructure_wave_preflight",
    "governance",
    "tests",
    "tools",
}
S0_DECISION_VALUES = {
    "D-01": ("approved", "route_a_plus_register_only_no_move"),
    "D-02": (
        "approved",
        "work_only_mutable_construction_area_formal_parts_return_fixed_dirs",
    ),
    "D-03": ("approved", "no_new_top_level_active_staging_frozen_runtime"),
    "D-04": (
        "approved",
        "analysis_library_local_truth_and_semantic_candidate_no_git_no_externalize",
    ),
    "D-05": (
        "approved",
        "new_experiment_programs_only_experiments_id_program",
    ),
    "D-06": (
        "approved",
        "side_tracks_closed_to_new_lines_history_stays_new_candidates_enter_work",
    ),
    "D-07": ("approved", "config_prompts_and_config_context_recipes"),
    "D-08": ("approved", "s0"),
    "D-09": ("deferred", "external_retention_and_cleanup_not_authorized"),
    "D-10": (
        "approved",
        "materialize_only_no_preflight_no_isolation_claim",
    ),
}
WAVE1_DIRECTORY_REGISTRY = "WAVE1_DIRECTORY_REGISTRY"
S0_MATERIALIZE_ONLY = "S0_MATERIALIZE_ONLY"
RESTRUCTURE_WAVE_SPECS = {
    WAVE1_DIRECTORY_REGISTRY: {
        "candidate_write_paths": [
            "governance/directory_registry.json",
            "governance/contracts/directory_registry_v1.schema.json",
            "governance/indexes/directory_map.md",
            "governance/indexes/new_file_routing.md",
            "tests/test_repository_layout.py",
            "governance/README.md",
            "governance/index_manifest.json",
            "governance/test_policy.json",
            "tools/governance_index.py",
            "tests/test_governance_index.py",
        ],
        "required_decisions": [f"D-{number:02d}" for number in range(1, 9)],
        "required_inputs": {
            ".gitignore",
            "AGENTS.md",
            CURRENT_STATE_PATH,
            CONTROL_PATH,
            "governance/module_registry.json",
            "governance/index_manifest.json",
            "governance/tool_registry.json",
            "governance/test_policy.json",
            "tools/governance_index.py",
            "tests/test_governance_index.py",
        },
        "capability_limits": {
            "register_only": True,
            "physical_move": False,
            "delete_source": False,
            "materialize_only": False,
            "preflight": False,
            "network": False,
            "model_api": False,
            "notion_write": False,
            "external_removal": False,
        },
        "requires_wave1_receipt": False,
    },
    S0_MATERIALIZE_ONLY: {
        "candidate_write_paths": [
            "tools/experiment_workspace.py",
            "tools/experiment_workspace_modules",
            "tests/test_experiment_workspace.py",
            "tests/test_experiment_workspace_security.py",
            "tests/fixtures/experiment_workspace",
            "tools/README.md",
            "tests/README.md",
            "governance/tool_registry.json",
            "governance/test_policy.json",
        ],
        "required_decisions": ["D-08", "D-10"],
        "required_inputs": {
            ".gitignore",
            "AGENTS.md",
            CURRENT_STATE_PATH,
            CONTROL_PATH,
            "governance/module_registry.json",
            "governance/index_manifest.json",
            "governance/tool_registry.json",
            "governance/test_policy.json",
            "tools/governance_index.py",
            "tests/test_governance_index.py",
        },
        "capability_limits": {
            "register_only": False,
            "physical_move": False,
            "delete_source": False,
            "materialize_only": True,
            "preflight": False,
            "network": False,
            "model_api": False,
            "notion_write": False,
            "external_removal": False,
        },
        "requires_wave1_receipt": True,
    },
}


def _must_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArtifactError(f"{name} 必须是对象")
    return value


def _must_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ArtifactError(f"{name} 必须是数组")
    return value


def _must_nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactError(f"{name} 必须是非空字符串")
    return value


def _validate_relative_identity(value: Any, name: str) -> None:
    if value is None:
        return
    text = _must_nonempty_string(value, name)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactError(f"{name} 必须是仓库相对路径")


def _repo_relative_path(value: Any, name: str) -> str:
    text = _must_nonempty_string(value, name).replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or path.as_posix() in {"", "."}:
        raise ArtifactError(f"{name} 必须是仓库内相对路径")
    return path.as_posix()


def _aware_datetime(value: Any, name: str) -> datetime:
    text = _must_nonempty_string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactError(f"{name} 不是 ISO 8601 时间") from exc
    if parsed.tzinfo is None:
        raise ArtifactError(f"{name} 必须带时区")
    return parsed


def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_list(values: list[str]) -> str:
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()


def _sha256_reference(value: Any, name: str) -> dict[str, str]:
    row = _must_dict(value, name)
    path = _repo_relative_path(row.get("path"), f"{name}.path")
    digest = _must_nonempty_string(row.get("sha256"), f"{name}.sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ArtifactError(f"{name}.sha256 必须是小写 SHA-256")
    return {"path": path, "sha256": digest}


def _reference_payload(
    root: Path,
    reference: dict[str, str],
    *,
    evidence_reads: dict[str, str] | None = None,
    captured_bytes: dict[str, bytes] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    try:
        path = _repo_path_without_symlinks(
            root,
            Path(reference["path"]),
            name=f"受绑定输入 {reference['path']}",
        )
        path_error = None
    except ArtifactError as exc:
        path = root / reference["path"]
        path_error = str(exc)
    evidence: dict[str, Any] = {
        "path": reference["path"],
        "expected_sha256": reference["sha256"],
        "exists": path.is_file(),
        "symlink": path.is_symlink() or path_error is not None,
        "actual_sha256": None,
        "sha256_matched": False,
        "json_object": False,
        "error": path_error,
    }
    if path_error is not None or not path.is_file() or path.is_symlink():
        return None, evidence
    try:
        raw = (
            captured_bytes[reference["path"]]
            if captured_bytes is not None
            and reference["path"] in captured_bytes
            else _read_repo_bytes_once(root, reference["path"])
        )
    except (ArtifactError, OSError) as exc:
        evidence["error"] = str(exc)
        return None, evidence
    actual = hashlib.sha256(raw).hexdigest()
    evidence["actual_sha256"] = actual
    evidence["sha256_matched"] = actual == reference["sha256"]
    if evidence_reads is not None:
        prior = evidence_reads.setdefault(reference["path"], actual)
        if prior != actual:
            evidence["error"] = "同一证据在本轮读取期间内容发生变化"
            return None, evidence
    if actual != reference["sha256"]:
        return None, evidence
    try:
        payload = json.loads(raw.decode("utf-8"))
        payload = _must_dict(payload, reference["path"])
    except (ArtifactError, UnicodeDecodeError, ValueError) as exc:
        evidence["error"] = str(exc)
        return None, evidence
    evidence["json_object"] = True
    return payload, evidence


def _markdown_authority_url(text: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}[^\n]*：(?P<url>https://[^\s*]+)", text)
    if match is None:
        raise ArtifactError(f"AGENTS.md 找不到现役入口：{label}")
    return match.group("url")


def _path_overlap(left: str, right: str) -> bool:
    left_parts = PurePosixPath(left).parts
    right_parts = PurePosixPath(right).parts
    shorter = min(len(left_parts), len(right_parts))
    return left_parts[:shorter] == right_parts[:shorter]


def _path_is_allowed(path: str, allowed: str) -> bool:
    path_parts = PurePosixPath(path).parts
    allowed_parts = PurePosixPath(allowed).parts
    return path_parts[: len(allowed_parts)] == allowed_parts


def _repo_path_without_symlinks(
    root: Path,
    value: Path,
    *,
    name: str,
) -> Path:
    root = root.resolve()
    raw = value if value.is_absolute() else root / value
    path = Path(os.path.abspath(raw))
    if path != root and root not in path.parents:
        raise ArtifactError(f"{name} 必须位于仓库内")
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ArtifactError(f"{name} 的父目录不得是软链：{current}")
        if current.exists() and not current.is_dir():
            raise ArtifactError(f"{name} 的父路径不是目录：{current}")
    if path.is_symlink():
        raise ArtifactError(f"{name} 本身不得是软链：{path}")
    return path


def _open_repo_directory_chain(
    root: Path,
    parts: tuple[str, ...],
    *,
    create: bool,
) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _read_repo_bytes_once(root: Path, relative_path: str) -> bytes:
    root = root.resolve()
    path = _repo_path_without_symlinks(
        root,
        Path(relative_path),
        name=f"受绑定输入 {relative_path}",
    )
    relative = path.relative_to(root)
    directory_descriptor = _open_repo_directory_chain(
        root,
        relative.parts[:-1],
        create=False,
    )
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(
            relative.name,
            flags,
            dir_fd=directory_descriptor,
        )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        opened_stat = os.fstat(descriptor)
        visible_path = _repo_path_without_symlinks(
            root,
            path,
            name=f"已读受绑定输入 {relative_path}",
        )
        visible_stat = os.stat(visible_path, follow_symlinks=False)
        if (
            visible_stat.st_dev,
            visible_stat.st_ino,
        ) != (
            opened_stat.st_dev,
            opened_stat.st_ino,
        ):
            raise ArtifactError(f"受绑定输入读取期间被替换：{relative_path}")
        return b"".join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)


def _git_path_set(root: Path, args: list[str]) -> set[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    }


def git_dirty_paths(root: Path = ROOT) -> list[str]:
    paths = set()
    paths.update(_git_path_set(root, ["diff", "--name-only", "-z"]))
    paths.update(_git_path_set(root, ["diff", "--cached", "--name-only", "-z"]))
    paths.update(_git_path_set(root, ["ls-files", "--others", "--exclude-standard", "-z"]))
    return sorted(paths)


def git_head(root: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def git_is_ancestor(root: Path, older_sha: str, newer_sha: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older_sha, newer_sha],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode not in {0, 1}:
        raise ArtifactError(
            "无法核对 Wave Git 祖先关系："
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.returncode == 0


def git_name_status_between(
    root: Path,
    older_sha: str,
    newer_sha: str,
) -> list[dict[str, str]]:
    completed = subprocess.run(
        [
            "git",
            "diff",
            "--no-renames",
            "--name-status",
            "-z",
            older_sha,
            newer_sha,
        ],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    chunks = [
        chunk.decode("utf-8")
        for chunk in completed.stdout.split(b"\0")
        if chunk
    ]
    if len(chunks) % 2:
        raise ArtifactError("无法解析 Wave Git 变更清单")
    return [
        {"status": chunks[index], "path": chunks[index + 1]}
        for index in range(0, len(chunks), 2)
    ]


def state_layers(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """返回当前执行态与历史上下文；v1 只作迁移期只读兼容。"""

    schema = state.get("schema_version")
    if schema == CURRENT_STATE_SCHEMA_V2:
        return (
            _must_dict(state.get("current_execution"), "current_execution"),
            _must_dict(state.get("historical_context"), "historical_context"),
        )
    if schema != LEGACY_CURRENT_STATE_SCHEMA:
        raise ArtifactError(f"CURRENT_STATE schema_version 不支持：{schema}")

    step = _must_dict(state.get("current_step"), "current_step")
    current = {
        "task": {
            key: step.get(key)
            for key in ("task_id", "label", "status", "status_label")
        },
        "authorization": {
            "kind": step.get("authority_kind"),
            "authority_time": step.get("authority_time"),
            "ledger_url": step.get("authority_url")
            or _must_dict(state.get("authority"), "authority")
            .get("external_truth", {})
            .get("ledger_url"),
            "queue_url": step.get("work_order_url")
            or _must_dict(state.get("authority"), "authority")
            .get("external_truth", {})
            .get("queue_url"),
        },
        "run": {
            "run_id": step.get("run_id"),
            "run_directory": step.get("run_directory"),
        },
        "controls": {
            "quality_boundary": step.get("quality_boundary")
            or step.get("evidence_boundary")
            or "旧版状态未独立登记质量边界",
            "evidence_boundary": step.get("evidence_boundary"),
            "stop_rule": step.get("stop_rule"),
            "next_action": step.get("next_action"),
        },
        "artifacts": {
            key: step.get(key)
            for key in (
                "report_directory",
                "local_stop_receipt",
                "machine_receipt",
                "notion_callback_url",
            )
        },
        "usage": {
            "model_api_logical_samples": step.get("model_api_logical_samples", 0),
            "model_api_network_attempts": step.get("model_api_network_attempts", 0),
            "model_api_usage_tokens": step.get("model_api_usage_tokens", 0),
        },
        "protection": step.get("protected_scope") or {},
        "blockers": [],
    }
    history = {
        "accepted_steps": state.get("accepted_steps"),
        "legacy_mainline": state.get("mainline"),
        "archived_run_states": state.get("run_states"),
        "issue_ledger": state.get("open_issues"),
        "closure_policy": state.get("closure_policy"),
    }
    return current, history


def _path_status(root: Path, relative: str) -> dict[str, Any]:
    path = resolve_repo_path(root, relative)
    return {
        "path": relative,
        "exists": path.is_file() or path.is_dir(),
        "kind": "file" if path.is_file() else "directory" if path.is_dir() else "missing",
        "sha256": sha256_file(path) if path.is_file() else None,
    }


def validate_control_plane(root: Path, control: dict[str, Any]) -> None:
    for key in (
        "source_authority",
        "current_default",
        "current_gold",
        "formal_gold_registry",
    ):
        _must_dict(control.get(key), key)
    if control.get("current_state_path") != CURRENT_STATE_PATH:
        raise ArtifactError("control_plane.current_state_path 未指向唯一当前状态真源")
    if control.get("route_registry_path") != ROUTE_REGISTRY_PATH:
        raise ArtifactError("control_plane.route_registry_path 未指向路线登记册")
    if "current_task" in control:
        raise ArtifactError("control_plane 不得重复保存 current_task")
    for key in ("silver_candidates", "run_report_pairs", "source_roots"):
        _must_list(control.get(key), key)
    protected = _must_list(control.get("protected_refs"), "protected_refs")
    for row in protected:
        item = _must_dict(row, "protected_ref")
        path = resolve_repo_path(root, str(item.get("path", "")))
        if not path.is_file():
            raise ArtifactError(f"保护件不存在：{item.get('path')}")
        actual = sha256_file(path)
        if actual != item.get("sha256"):
            raise ArtifactError(f"保护件漂移：{item.get('path')}：{actual}")
    for group_name in ("silver_candidates", "run_report_pairs"):
        for row in control[group_name]:
            item = _must_dict(row, group_name)
            relative = item.get("path") or item.get("report_path")
            if relative and not resolve_repo_path(root, str(relative)).exists():
                raise ArtifactError(f"索引目标不存在：{relative}")
    for row in control["source_roots"]:
        item = _must_dict(row, "source_roots")
        relative = str(item.get("path", ""))
        if not relative or not (root / relative).exists():
            raise ArtifactError(f"材料入口不存在：{relative}")
    formal_registry = control["formal_gold_registry"]
    formal_registry_path = resolve_repo_path(root, str(formal_registry.get("path", "")))
    if not formal_registry_path.is_file():
        raise ArtifactError("正式金标登记册不存在")
    formal_registry_sha = sha256_file(formal_registry_path)
    if formal_registry_sha != formal_registry.get("sha256"):
        raise ArtifactError(f"正式金标登记册漂移：{formal_registry_sha}")
    formal_registry_data = _must_dict(read_json(formal_registry_path), "formal_gold_registry")
    entries = _must_list(formal_registry_data.get("entries"), "formal_gold_registry.entries")
    if len(entries) != formal_registry.get("entry_total"):
        raise ArtifactError("正式金标登记册数量与控制面不符")
    for row in entries:
        entry = _must_dict(row, "formal_gold_registry.entry")
        if entry.get("label_tier") != "gold" or entry.get("status") != "active_gold":
            raise ArtifactError(f"正式金标登记项状态不符：{entry.get('gold_id')}")
        pointer = resolve_repo_path(root, str(entry.get("pointer_path", "")))
        artifact = resolve_repo_path(root, str(entry.get("artifact_path", "")))
        if not pointer.is_file() or sha256_file(pointer) != entry.get("pointer_sha256"):
            raise ArtifactError(f"正式金标指针漂移：{entry.get('gold_id')}")
        if not artifact.is_file() or sha256_file(artifact) != entry.get("artifact_sha256"):
            raise ArtifactError(f"正式金标工件漂移：{entry.get('gold_id')}")
    root_readme = (root / "README.md").read_text(encoding="utf-8")
    if "[治理索引](governance/INDEX.md)" not in root_readme:
        raise ArtifactError("根 README 缺治理索引的一跳入口")


def _validate_historical_context(root: Path, history: dict[str, Any]) -> None:
    for key in ("legacy_mainline", "closure_policy"):
        _must_dict(history.get(key), f"historical_context.{key}")
    accepted_steps = _must_list(
        history.get("accepted_steps"),
        "historical_context.accepted_steps",
    )
    open_issues = _must_list(
        history.get("issue_ledger"),
        "historical_context.issue_ledger",
    )
    run_states = _must_list(
        history.get("archived_run_states"),
        "historical_context.archived_run_states",
    )
    if not any(_must_dict(row, "accepted_step").get("task_id") == "Z84-repo-hygiene" for row in accepted_steps):
        raise ArtifactError("CURRENT_STATE 缺第84道审收状态")
    issue_ids = [str(_must_dict(row, "open_issue").get("issue_id", "")) for row in open_issues]
    if not all(issue_ids) or len(issue_ids) != len(set(issue_ids)):
        raise ArtifactError("CURRENT_STATE 挂账编号为空或重复")

    seen: set[str] = set()
    for row in run_states:
        item = _must_dict(row, "run_state")
        run_id = str(item.get("run_id", ""))
        if not run_id or run_id in seen:
            raise ArtifactError(f"运行编号为空或重复：{run_id}")
        seen.add(run_id)
        ticket = str(item.get("authoritative_ticket", ""))
        ticket_path = resolve_repo_path(root, ticket) if ticket else None
        if ticket_path is None or not ticket_path.is_file():
            raise ArtifactError(f"权威票据不存在：{run_id}：{ticket}")
        if item.get("ticket_level") == "main_hard_stop" and not ticket.endswith("/main/hard_stop.json"):
            raise ArtifactError(f"硬停票据层级错误：{run_id}：{ticket}")

        ticket_data = _must_dict(read_json(ticket_path), f"{run_id}.authoritative_ticket")
        effective_status = str(item.get("effective_status", ""))
        if item.get("ticket_level") == "main_hard_stop":
            if ticket_data.get("status") != "hard_stop_no_unapproved_repair":
                raise ArtifactError(f"硬停票内容状态不符：{run_id}")
            if effective_status == "hard_stop_401" and "401" not in str(ticket_data.get("error", "")):
                raise ArtifactError(f"401 状态与硬停票不符：{run_id}")
            if effective_status == "hard_stop_interrupted" and ticket_data.get("error_type") != "KeyboardInterrupt":
                raise ArtifactError(f"中断状态与硬停票不符：{run_id}")
        elif item.get("ticket_level") == "prepared_verification":
            if ticket_data.get("status") != "pass" or ticket_data.get("require_zero_call") is not True:
                raise ArtifactError(f"零调用准备票内容不符：{run_id}")
            if ticket_data.get("call_artifacts") not in (None, []):
                raise ArtifactError(f"零调用准备票出现调用工件：{run_id}")
            preflight = _must_dict(
                read_json(root / "runs" / run_id / "preflight.json"),
                f"{run_id}.preflight",
            )
            if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
                raise ArtifactError(f"零调用准备状态与 preflight 不符：{run_id}")
        elif item.get("ticket_level") == "main_run_claim":
            if ticket_data.get("status") != "claimed_do_not_resume":
                raise ArtifactError(f"运行中状态与占用票不符：{run_id}")
        elif item.get("ticket_level") == "main_completion":
            if ticket_data.get("status") != "completed_candidate_silver_only":
                raise ArtifactError(f"主采样收口状态与票据不符：{run_id}")
            if ticket_data.get("chapters_completed") != [3, 13, 19]:
                raise ArtifactError(f"主采样收口章次与票据不符：{run_id}")
            if ticket_data.get("network_attempts") != item.get("network_attempts"):
                raise ArtifactError(f"主采样运输账与状态登记不符：{run_id}")
        elif item.get("ticket_level") in {
            "subrun_hard_stop",
            "subrun_hard_stop_with_top_sync",
        }:
            if ticket_data.get("status") != "hard_stop_no_resume_or_result_selection":
                raise ArtifactError(f"子运行硬停状态与票据不符：{run_id}")
            error = str(ticket_data.get("error", ""))
            if item.get("ticket_level") == "subrun_hard_stop":
                if "finish_reason=length" not in error:
                    raise ArtifactError(f"检查员截断硬停与票据不符：{run_id}")
            elif effective_status == "inspector_hard_stop_true_non_substring":
                if (
                    "逐字连续子串" not in error
                    or ticket_data.get("new_attempted_chapters") != [13]
                    or ticket_data.get("network_attempts") != 1
                ):
                    raise ArtifactError(f"检查员真非子串硬停与票据不符：{run_id}")
            elif "改写了短引" not in error:
                raise ArtifactError(f"检查员短引改写硬停与票据不符：{run_id}")
        elif item.get("ticket_level") == "legacy_adjudication_receipt":
            if ticket_data.get("status") != "hard_stop_after_group_1":
                raise ArtifactError(f"Z80 历史裁定票内容不符：{run_id}")

        run_manifest = root / "runs" / run_id / "run_manifest.json"
        if run_manifest.is_file() and item.get("legacy_manifest_status"):
            manifest_data = _must_dict(read_json(run_manifest), f"{run_id}.run_manifest")
            if manifest_data.get("status") != item.get("legacy_manifest_status"):
                raise ArtifactError(f"登记的旧 manifest 状态不符：{run_id}")
        hard_stop_path = root / "runs" / run_id / "main" / "hard_stop.json"
        if hard_stop_path.is_file() and item.get("ticket_level") != "main_hard_stop":
            raise ArtifactError(f"已出现 main/hard_stop.json，CURRENT_STATE 尚未切到硬停票：{run_id}")
        inspector_hard_stop = root / "runs" / run_id / "review" / "inspector" / "hard_stop.json"
        if inspector_hard_stop.is_file() and ticket_path != inspector_hard_stop:
            raise ArtifactError(f"已出现检查员硬停票，CURRENT_STATE 尚未切换：{run_id}")

    expected_run_ids = {
        path.name
        for pattern in ("Z80_*", "Z83_*")
        for path in (root / "runs").glob(pattern)
        if path.is_dir()
    }
    missing_run_ids = sorted(expected_run_ids - seen)
    if missing_run_ids:
        raise ArtifactError(f"CURRENT_STATE 漏登记 Z80/Z83 运行目录：{missing_run_ids}")

    mainline = history["legacy_mainline"]
    original_ticket = str(mainline.get("original_hard_stop_ticket", ""))
    if not original_ticket.endswith("/main/hard_stop.json") or not resolve_repo_path(root, original_ticket).is_file():
        raise ArtifactError("第83道原运行硬停票缺失或层级错误")
    latest_authorization = _must_dict(
        mainline.get("latest_authorization"), "mainline.latest_authorization"
    )
    authorization_status = latest_authorization.get("status")
    if authorization_status == "authorized_not_observed":
        if latest_authorization.get("local_run_directory") is not None:
            raise ArtifactError("未观察到开跑时不得登记 retry04 运行目录")
        if latest_authorization.get("local_process_observed") is not False:
            raise ArtifactError("retry04 进程观察状态与授权未开跑口径冲突")
    z85_gate = _must_dict(mainline.get("z85_gate"), "mainline.z85_gate")
    if latest_authorization.get("step") == "Z83-retry04-inspector-32k":
        if authorization_status == "authorized_not_observed" and z85_gate.get("status") != "locked":
            raise ArtifactError("第83道 retry04 尚未停点时第85道必须保持锁定")
        if authorization_status == "executed_hard_stop":
            if latest_authorization.get("local_run_directory") is None:
                raise ArtifactError("retry04 已硬停时必须登记运行目录")
            if latest_authorization.get("local_process_observed") is not True:
                raise ArtifactError("retry04 已硬停时必须登记已观察到运行")
            if z85_gate.get("status") != "unlocked_pending_start":
                raise ArtifactError("retry04 硬停回传后第85道应解锁但不得冒充已启动")


def _validate_current_execution(current: dict[str, Any]) -> None:
    task = _must_dict(current.get("task"), "current_execution.task")
    for key in ("task_id", "label", "status", "status_label"):
        _must_nonempty_string(task.get(key), f"current_execution.task.{key}")

    authorization = _must_dict(
        current.get("authorization"),
        "current_execution.authorization",
    )
    for key in ("kind", "authority_time", "ledger_url", "queue_url"):
        _must_nonempty_string(
            authorization.get(key),
            f"current_execution.authorization.{key}",
        )

    run = _must_dict(current.get("run"), "current_execution.run")
    run_id = run.get("run_id")
    run_directory = run.get("run_directory")
    if (run_id is None) != (run_directory is None):
        raise ArtifactError("current_execution.run 的 run_id 与 run_directory 必须同时为空或同时存在")
    if run_id is not None:
        _must_nonempty_string(run_id, "current_execution.run.run_id")
        _validate_relative_identity(
            run_directory,
            "current_execution.run.run_directory",
        )
        if not str(run_directory).startswith("runs/"):
            raise ArtifactError("current_execution.run.run_directory 必须位于 runs/")

    controls = _must_dict(current.get("controls"), "current_execution.controls")
    for key in ("quality_boundary", "stop_rule", "next_action"):
        _must_nonempty_string(
            controls.get(key),
            f"current_execution.controls.{key}",
        )
    if controls.get("evidence_boundary") is not None:
        _must_nonempty_string(
            controls.get("evidence_boundary"),
            "current_execution.controls.evidence_boundary",
        )

    artifacts = _must_dict(current.get("artifacts"), "current_execution.artifacts")
    for key in ("report_directory", "local_stop_receipt", "machine_receipt"):
        _validate_relative_identity(
            artifacts.get(key),
            f"current_execution.artifacts.{key}",
        )

    usage = _must_dict(current.get("usage"), "current_execution.usage")
    for key in (
        "model_api_logical_samples",
        "model_api_network_attempts",
        "model_api_usage_tokens",
    ):
        value = usage.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ArtifactError(f"current_execution.usage.{key} 必须是非负整数")

    _must_dict(current.get("protection"), "current_execution.protection")
    blockers = _must_list(current.get("blockers"), "current_execution.blockers")
    blocker_ids: list[str] = []
    for row in blockers:
        item = _must_dict(row, "current_execution.blocker")
        blocker_id = str(item.get("blocker_id") or item.get("issue_id") or "")
        if not blocker_id:
            raise ArtifactError("current_execution.blocker 缺编号")
        _must_nonempty_string(item.get("summary"), f"{blocker_id}.summary")
        blocker_ids.append(blocker_id)
    if len(blocker_ids) != len(set(blocker_ids)):
        raise ArtifactError("current_execution.blockers 编号重复")


def validate_current_state(root: Path, state: dict[str, Any]) -> None:
    _must_dict(state.get("authority"), "authority")
    schema = state.get("schema_version")
    if schema == CURRENT_STATE_SCHEMA_V2:
        duplicate_keys = sorted(LEGACY_TOP_LEVEL_STATE_KEYS.intersection(state))
        if duplicate_keys:
            raise ArtifactError(f"CURRENT_STATE v2 不得保留旧顶层键：{duplicate_keys}")
    current, history = state_layers(state)
    _validate_current_execution(current)
    _validate_historical_context(root, history)

    task_id = current["task"]["task_id"]
    accepted_task_ids = {
        str(_must_dict(row, "accepted_step").get("task_id", ""))
        for row in history["accepted_steps"]
    }
    if schema == CURRENT_STATE_SCHEMA_V2 and task_id in accepted_task_ids:
        raise ArtifactError("当前任务不得同时出现在历史已收口任务中")
    run_id = current["run"].get("run_id")
    archived_run_ids = {
        str(_must_dict(row, "archived_run_state").get("run_id", ""))
        for row in history["archived_run_states"]
    }
    if schema == CURRENT_STATE_SCHEMA_V2 and run_id and run_id in archived_run_ids:
        raise ArtifactError("当前运行不得同时出现在历史冻结运行中")


def validate_route_registry(
    root: Path,
    registry: dict[str, Any],
    _current_state: dict[str, Any] | None = None,
) -> None:
    allowed = set(_must_list(registry.get("allowed_statuses"), "allowed_statuses"))
    if allowed != ROUTE_STATUS_VALUES:
        raise ArtifactError(f"路线状态枚举漂移：{sorted(allowed)}")
    routes = _must_list(registry.get("routes"), "routes")
    seen: set[str] = set()
    for row in routes:
        item = _must_dict(row, "route")
        route_id = str(item.get("route_id", ""))
        if not route_id or route_id in seen:
            raise ArtifactError(f"路线编号为空或重复：{route_id}")
        seen.add(route_id)
        if item.get("status") not in ROUTE_STATUS_VALUES:
            raise ArtifactError(f"路线状态非法：{route_id}：{item.get('status')}")
        lifecycle = _must_list(item.get("lifecycle"), f"{route_id}.lifecycle")
        if not lifecycle:
            raise ArtifactError(f"路线缺生命周期凭证：{route_id}")
        for event in lifecycle:
            entry = _must_dict(event, f"{route_id}.lifecycle_event")
            refs = []
            if entry.get("evidence_ref"):
                refs.append(str(entry["evidence_ref"]))
            refs.extend(str(ref) for ref in entry.get("evidence_refs", []))
            if not refs:
                raise ArtifactError(f"路线事件缺凭证：{route_id}：{entry.get('step')}")
            for ref in refs:
                if ref.startswith("https://"):
                    continue
                path_text = ref.split("#", 1)[0]
                if not resolve_repo_path(root, path_text).exists():
                    raise ArtifactError(f"路线凭证不存在：{route_id}：{ref}")

    program_route = next(
        (row for row in routes if row.get("route_id") == "ROUTE-PROGRAM-SIDE-REPAIR"),
        None,
    )
    if program_route is None:
        raise ArtifactError("路线登记缺程序侧治法")
    program_lifecycle = _must_list(
        program_route.get("lifecycle"),
        "ROUTE-PROGRAM-SIDE-REPAIR.lifecycle",
    )
    latest_program_event = str(program_lifecycle[-1].get("event", ""))
    if program_route.get("status") == "failed" and (
        "route_not_concluded" in latest_program_event
        or latest_program_event.startswith("candidate_")
    ):
        raise ArtifactError("路线末事件仍未判死，不得把程序侧整条路线登记为失败")


def materialize_registry(root: Path, source: dict[str, Any]) -> dict[str, Any]:
    registry = copy.deepcopy(source)
    modules = _must_list(registry.get("modules"), "modules")
    identities: set[tuple[str, str]] = set()
    for module in modules:
        row = _must_dict(module, "module")
        identity = (str(row.get("module_id", "")), str(row.get("version", "")))
        if not all(identity) or identity in identities:
            raise ArtifactError(f"模块身份为空或重复：{identity}")
        identities.add(identity)
        if row.get("status") not in STATUS_VALUES:
            raise ArtifactError(f"模块状态非法：{identity}：{row.get('status')}")
        sources = _must_list(row.pop("sources", []), f"{identity}.sources")
        row["source_refs"] = [_path_status(root, str(path)) for path in sources]
        missing = [item["path"] for item in row["source_refs"] if not item["exists"]]
        if missing:
            raise ArtifactError(f"模块来源缺失：{identity}：{missing}")
    registry["status_counts"] = {
        status: sum(1 for row in modules if row["status"] == status)
        for status in ("可用", "在改", "试验")
    }
    return registry


def dependency_map(registry: dict[str, Any]) -> dict[str, Any]:
    ids = []
    for row in registry["modules"]:
        if row["module_id"] not in ids:
            ids.append(row["module_id"])
    order = [f"M{number:02d}" for number in range(12)]
    if any(module not in ids for module in order):
        raise ArtifactError("模块登记缺 M00～M11")
    return {
        "schema_version": "pipeline-dependency-map-v1",
        "mainline_order": order,
        "edges": [
            {"from": order[index], "to": order[index + 1], "contract_gate": True}
            for index in range(len(order) - 1)
        ],
        "sandbox_rule": "只替换一个模块版本；上游只读；先验输出合同；候选只写 experiments/。",
    }


def _markdown_path(row: dict[str, Any]) -> str:
    path = str(row.get("path", ""))
    if not path:
        return "—"
    exists = "✅" if row.get("exists") else "❌"
    return f"{exists} `{path}`"


def discover_registered_experiment_files(root: Path) -> list[Path]:
    """只返回按合同登记的试验，避免生成页随本机候选目录漂移。"""

    experiments_root = root / "experiments"
    if not experiments_root.is_dir():
        return []

    directories = sorted(
        (
            path
            for path in experiments_root.iterdir()
            if path.is_dir() and not path.name.startswith(("_", "."))
        ),
        key=lambda path: path.name,
    )
    registered = [
        path / "experiment.json"
        for path in directories
        if (path / "experiment.json").is_file()
    ]
    return registered


def render_experiments_index(root: Path) -> str:
    registered = discover_registered_experiment_files(root)
    lines = [
        "# 试验专区索引",
        "",
        "新专项试验只写 `experiments/<experiment_id>/`。历史 `runs/`、`reports/` 原件不搬、不回写。",
        "",
        "## 当前登记",
        "",
        "| 试验 | 状态 | 位置 | 说明 |",
        "|---|---|---|---|",
    ]
    for path in registered:
        data = read_json(path)
        lines.append(
            f"| {data.get('experiment_id')} | {data.get('status')} | "
            f"`{path.parent.relative_to(root).as_posix()}` | "
            f"{data.get('summary', '')} |"
        )
    if not registered:
        lines.append("| 暂无已登记试验 | — | — | — |")

    lines.extend(
        [
            "",
            "未登记的本地候选与证据目录不写进生成页，避免干净副本和当前机器得到两张不同路牌。",
            "本机只读盘点方式见 `experiments/README.md`。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def build_documents(
    root: Path,
    control: dict[str, Any],
    current_state: dict[str, Any],
    route_registry: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, str]:
    default = control["current_default"]
    gold = control["current_gold"]
    formal_registry_control = control["formal_gold_registry"]
    formal_registry = _must_dict(
        read_json(root / formal_registry_control["path"]),
        "formal_gold_registry",
    )
    formal_gold_entries = _must_list(
        formal_registry.get("entries"),
        "formal_gold_registry.entries",
    )
    current, _history = state_layers(current_state)
    task = current["task"]
    authorization = current["authorization"]
    run = current["run"]
    controls = current["controls"]
    artifacts = current["artifacts"]
    usage = current["usage"]
    blockers = current["blockers"]
    status_counts = registry["status_counts"]
    route_counts = {
        status: sum(1 for row in route_registry["routes"] if row["status"] == status)
        for status in ROUTE_STATUS_VALUES
    }
    run_label = (
        f"`{run['run_id']}`（`{run['run_directory']}`）"
        if run.get("run_id")
        else "无独立模型运行"
    )
    blocker_label = (
        f"{len(blockers)} 项：{'；'.join(row['summary'] for row in blockers)}"
        if blockers
        else "0 项"
    )
    report_label = (
        f"`{artifacts['report_directory']}`"
        if artifacts.get("report_directory")
        else "尚未登记"
    )
    receipt_label = (
        f"`{artifacts['local_stop_receipt']}`"
        if artifacts.get("local_stop_receipt")
        else "尚未登记"
    )

    index = f"""# 小说流水线治理索引

> 本页由 `tools/governance_index.py` 从 `governance/CURRENT_STATE.json` 生成。人从这里看，机器读取当前任务／运行状态只认这份真源；模块与实验路线各看自己的登记册；Notion 账序和队列仍是最终真源。根 `current.md` 与模块 README 只作历史上下文。

## 一页回答关键问题

| 问题 | 当前答案 |
|---|---|
| 现在跑到哪道 | **{task['label']}**（`{task['task_id']}`）；状态＝**{task['status_label']}**；当前运行＝{run_label}；授权时间＝`{authorization['authority_time']}` |
| 金标哪版哪指针 | 正式金标共 {len(formal_gold_entries)} 个入口：X01 第3章 **{gold['version']}**＋五本 v1.3；统一登记 `{formal_registry_control['path']}` |
| 各模块什么状态 | 可用 {status_counts['可用']} 个版本／在改 {status_counts['在改']} 个版本／试验 {status_counts['试验']} 个版本；见 [模块状态登记](module_registry.json) |
| 银标候选在哪 | 五本底稿、正反例候选、第75道样张及沙箱观察均在 [银标候选索引](indexes/silver_candidates.md)；正式件不从候选标题自动推断 |
| 实验路线能不能再开 | 在试 {route_counts['in_trial']} 条／失败 {route_counts['failed']} 条／退役 {route_counts['retired']} 条／当前允许重开 {route_counts['allowed_to_reopen']} 条；见 [路线状态登记](route_registry.json) |
| 当前任务有什么阻断 | {blocker_label} |

## 当前正式入口

- 默认链：`{default['path']}`，版本 `{default['version']}`。
- 旧运行入口：`tools/zbatch.py`，继续保留。
- 新统一薄入口：`tools/novel_pipeline.py`；现役命令原样转发给旧入口，不复制运行逻辑。
- 密钥加载入口：只用 `tools/sensenova_deepseek_key.sh`；共享环境和外部项目加载器已退役。
- 试验专区：`experiments/`；旧试验原件不搬，新试验从这里起。

## 快速入口

- [当前停点](current_run.md)
- [机器当前状态](CURRENT_STATE.json)
- [实验路线状态](route_registry.json)
- [正式金标](indexes/gold_current.md)
- [银标候选](indexes/silver_candidates.md)
- [运行与回包](indexes/runs_and_reports.md)
- [材料与参考](indexes/source_registry.md)
- [旧路牌健康检查](indexes/route_health.md)
- [模块依赖图](dependency_map.json)
- [合同说明](contracts/README.md)
- [试验专区](../experiments/INDEX.md)

## 下一件

{controls['next_action']}

来源：Cursor（仓库治理窗）
"""

    current = f"""# 当前运行与停点

- 当前任务：{task['label']}
- 任务编号：`{task['task_id']}`
- 状态：{task['status_label']}
- 授权：{authorization['kind']}，时间 `{authorization['authority_time']}`
- 当前运行：{run_label}
- 质量边界：{controls['quality_boundary']}
- 当前停点：{controls['stop_rule']}
- 下一动作：{controls['next_action']}
- 当前阻断：{blocker_label}
- 模型调用账：逻辑样本 {usage['model_api_logical_samples']}／网络尝试 {usage['model_api_network_attempts']}／token {usage['model_api_usage_tokens']}
- 报告目录：{report_label}
- 本地停点回执：{receipt_label}
- 默认链：`{default['path']}`（{default['version']}）
- 当前金标：`{gold['pointer_path']}` → `{gold['artifact_path']}`
- 正式金标登记：`{formal_registry_control['path']}`，共 {len(formal_gold_entries)} 个独立 current 入口。
- 真源账序：{authorization['ledger_url']}
- 真源队列：{authorization['queue_url']}

本页由生成器维护，不再向根 `current.md` 手抄整段进度。

来源：Cursor（仓库治理窗）
"""

    gold_rows = [
        "# 正式金标索引",
        "",
        f"统一登记册：`{formal_registry_control['path']}`，SHA-256 "
        f"`{formal_registry_control['sha256']}`。",
        "",
        "| 金标 | 版本 | 分母 | 指针 | 正式工件 | 来源边界 |",
        "|---|---|---:|---|---|---|",
    ]
    for row in formal_gold_entries:
        pointer = _path_status(root, str(row["pointer_path"]))
        artifact = _path_status(root, str(row["artifact_path"]))
        gold_rows.append(
            f"| {row['book_id']} 第{row['inventory_unit']}单元 | {row['version']} | "
            f"{row['formal_denominator']} | {_markdown_path(pointer)} | "
            f"{_markdown_path(artifact)} | {row['provenance_label']} |"
        )
    gold_rows.extend(
        [
            "",
            "所有登记项的 `label_tier` 都是正式金标。是否由 CZ 逐条亲验只写来源链，"
            "不形成高低两档；候选底稿和外部回包不会因被索引而转正。",
            "",
            "X01 原件与指针保持原样；五本各有独立 current。回退按整份工件和对应指针办理。",
            "",
            "来源：Codex",
            "",
        ]
    )
    gold_page = "\n".join(gold_rows)

    silver_lines = [
        "# 银标候选索引",
        "",
        "索引只告诉你候选在哪里和能不能用，不改变候选地位。",
        "",
        "| 候选 | 位置 | 当前处置 | 使用边界 |",
        "|---|---|---|---|",
    ]
    for row in control["silver_candidates"]:
        path = row.get("path")
        location = f"`{path}`" if path else f"[Notion 观察页]({row['notion_url']})"
        silver_lines.append(
            f"| {row['name']} | {location} | {row['status']} | {row['usage_boundary']} |"
        )
    silver_lines.extend(["", "来源：Codex", ""])

    runs_lines = [
        "# 运行与回包配对索引",
        "",
        "| 运行／任务 | 模块范围 | 模型调用 | 状态 | 本地报告 | Notion | 可复用边界 |",
        "|---|---|---:|---|---|---|---|",
    ]
    for row in control["run_report_pairs"]:
        report = f"`{row['report_path']}`" if row.get("report_path") else "—"
        notion = f"[正文]({row['notion_url']})" if row.get("notion_url") else "—"
        runs_lines.append(
            f"| {row['name']} | {row['module_range']} | {row['model_calls']} | {row['status']} | {report} | {notion} | {row['reuse']} |"
        )
    runs_lines.extend(["", "来源：Codex", ""])

    source_lines = [
        "# 材料与参考索引",
        "",
        "| 区域 | 路径 | 用途 | 真值边界 |",
        "|---|---|---|---|",
    ]
    for row in control["source_roots"]:
        source_lines.append(
            f"| {row['name']} | `{row['path']}` | {row['purpose']} | {row['truth_boundary']} |"
        )
    source_lines.extend(["", "来源：Codex", ""])

    route_rows = []
    for row in control["legacy_routes"]:
        status = _path_status(root, row["path"])
        route_rows.append(
            f"| `{row['path']}` | {'存在' if status['exists'] else '缺失'} | {row['role']} | `{row['replacement']}` |"
        )
    route_page = "\n".join(
        [
            "# 旧路牌健康检查",
            "",
            "旧页不回写；生成器把它们明确降为历史上下文，并给出当前替代入口。",
            "",
            "| 旧路牌 | 文件状态 | 现在的角色 | 当前入口 |",
            "|---|---|---|---|",
            *route_rows,
            "",
            "来源：Codex",
            "",
        ]
    )

    return {
        "governance/INDEX.md": index,
        "governance/current_run.md": current,
        "governance/indexes/gold_current.md": gold_page,
        "governance/indexes/silver_candidates.md": "\n".join(silver_lines),
        "governance/indexes/runs_and_reports.md": "\n".join(runs_lines),
        "governance/indexes/source_registry.md": "\n".join(source_lines),
        "governance/indexes/route_health.md": route_page,
        "experiments/INDEX.md": render_experiments_index(root),
    }


def refresh(root: Path = ROOT, output_root: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    destination = (output_root or root).resolve()
    control = _must_dict(read_json(root / CONTROL_PATH), "control_plane")
    current_state = _must_dict(read_json(root / CURRENT_STATE_PATH), "CURRENT_STATE")
    route_registry = _must_dict(read_json(root / ROUTE_REGISTRY_PATH), "route_registry")
    registry_source = _must_dict(read_json(root / REGISTRY_SOURCE_PATH), "module_registry.source")
    validate_control_plane(root, control)
    validate_current_state(root, current_state)
    validate_route_registry(root, route_registry, current_state)
    registry = materialize_registry(root, registry_source)
    documents = build_documents(root, control, current_state, route_registry, registry)

    for relative, text in documents.items():
        write_text_atomic(destination / relative, text)
    write_json_atomic(destination / "governance/module_registry.json", registry)
    write_json_atomic(destination / "governance/dependency_map.json", dependency_map(registry))

    manifest_paths = [path for path in GENERATED_PATHS if path != "governance/index_manifest.json"]
    manifest = {
        "schema_version": "governance-index-manifest-v1",
        "generator": {
            "path": "tools/governance_index.py",
            "sha256": sha256_file(root / "tools/governance_index.py"),
        },
        "inputs": build_manifest(
            root,
            [CONTROL_PATH, CURRENT_STATE_PATH, ROUTE_REGISTRY_PATH, REGISTRY_SOURCE_PATH],
        ),
        "outputs": build_manifest(destination, manifest_paths),
    }
    manifest["verification"] = verify_manifest(destination, manifest["outputs"])
    write_json_atomic(destination / "governance/index_manifest.json", manifest)
    return manifest


def generated_mismatches(root: Path = ROOT) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="governance-index-check-") as temporary:
        output_root = Path(temporary)
        refresh(root=root, output_root=output_root)
        return [
            relative
            for relative in GENERATED_PATHS + ["governance/index_manifest.json"]
            if not (root / relative).is_file()
            or (root / relative).read_bytes() != (output_root / relative).read_bytes()
        ]


def _baseline_plan(value: Any) -> dict[str, Any]:
    plan = _must_dict(value, "基线校准计划")
    if plan.get("contract_version") != RESTRUCTURE_BASELINE_PLAN_V1:
        raise ArtifactError(
            f"基线校准计划 contract_version 必须是 {RESTRUCTURE_BASELINE_PLAN_V1}"
        )
    _must_nonempty_string(plan.get("plan_id"), "plan_id")
    expected_head = _must_nonempty_string(plan.get("expected_head_sha"), "expected_head_sha")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise ArtifactError("expected_head_sha 必须是小写 40 位 Git SHA")
    window = _must_dict(plan.get("responsibility_window"), "responsibility_window")
    for key in (
        "source_system",
        "authorization_context_id",
        "owner",
        "task_id",
        "wave_id",
        "starts_at",
        "expires_at",
    ):
        _must_nonempty_string(window.get(key), f"responsibility_window.{key}")
    if window["wave_id"] != "BASELINE":
        raise ArtifactError("第一级校准计划的 wave_id 必须是 BASELINE")
    starts_at = _aware_datetime(window["starts_at"], "responsibility_window.starts_at")
    expires_at = _aware_datetime(window["expires_at"], "responsibility_window.expires_at")
    if expires_at <= starts_at:
        raise ArtifactError("责任窗口 expires_at 必须晚于 starts_at")

    for key in ("write_allowlist", "candidate_write_paths"):
        values = _must_list(window.get(key), f"responsibility_window.{key}")
        normalized = [_repo_relative_path(item, key) for item in values]
        if len(normalized) != len(set(normalized)):
            raise ArtifactError(f"responsibility_window.{key} 不能重复")
        window[key] = normalized
    read_values = window.get("read_allowlist", [])
    if not isinstance(read_values, list):
        raise ArtifactError("responsibility_window.read_allowlist 必须是数组")
    normalized_reads = [_repo_relative_path(item, "read_allowlist") for item in read_values]
    if len(normalized_reads) != len(set(normalized_reads)):
        raise ArtifactError("responsibility_window.read_allowlist 不能重复")
    window["read_allowlist"] = normalized_reads

    historical_values = plan.get("historical_authority_expectations", [])
    if not isinstance(historical_values, list):
        raise ArtifactError("historical_authority_expectations 必须是数组")
    historical_expectations: list[dict[str, str]] = []
    for index, value in enumerate(historical_values):
        row = _must_dict(value, f"historical_authority_expectations[{index}]")
        historical_expectations.append(
            {
                "name": _must_nonempty_string(
                    row.get("name"),
                    f"historical_authority_expectations[{index}].name",
                ),
                "path": _must_nonempty_string(
                    row.get("path"),
                    f"historical_authority_expectations[{index}].path",
                ),
                "url": _must_nonempty_string(
                    row.get("url"),
                    f"historical_authority_expectations[{index}].url",
                ),
            }
        )
    plan["historical_authority_expectations"] = historical_expectations

    bindings = _must_list(plan.get("bound_inputs"), "bound_inputs")
    seen: set[str] = set()
    normalized_bindings: list[dict[str, str]] = []
    for index, value in enumerate(bindings):
        row = _must_dict(value, f"bound_inputs[{index}]")
        path = _repo_relative_path(row.get("path"), f"bound_inputs[{index}].path")
        digest = _must_nonempty_string(row.get("sha256"), f"bound_inputs[{index}].sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ArtifactError(f"bound_inputs[{index}].sha256 必须是小写 SHA-256")
        if path in seen:
            raise ArtifactError(f"bound_inputs 路径重复：{path}")
        seen.add(path)
        normalized_bindings.append({"path": path, "sha256": digest})
    missing = sorted(RESTRUCTURE_BASELINE_REQUIRED_INPUTS - seen)
    if missing:
        raise ArtifactError(f"bound_inputs 缺少必绑输入：{', '.join(missing)}")
    plan["bound_inputs"] = normalized_bindings
    return plan


def _evaluate_restructure_baseline_snapshot(
    root: Path,
    plan_raw: Any,
    *,
    dirty_paths: list[str],
    head_sha: str,
    governance_mismatch_paths: list[str],
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    plan = _baseline_plan(copy.deepcopy(plan_raw))
    window = plan["responsibility_window"]
    plan_content_sha256 = hashlib.sha256(
        json.dumps(
            plan,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    now = evaluated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ArtifactError("evaluated_at 必须带时区")

    bound_bytes: dict[str, bytes] = {}
    evidence_reads: dict[str, str] = {}
    binding_results: list[dict[str, Any]] = []
    binding_passed = True
    for binding in plan["bound_inputs"]:
        path_error = None
        try:
            raw = _read_repo_bytes_once(root, binding["path"])
            actual = hashlib.sha256(raw).hexdigest()
            prior = evidence_reads.setdefault(binding["path"], actual)
            if prior != actual:
                raise ArtifactError("同一输入在本轮读取期间内容发生变化")
            bound_bytes[binding["path"]] = raw
            exists = True
        except (ArtifactError, OSError) as exc:
            actual = None
            exists = False
            path_error = str(exc)
        matched = exists and actual == binding["sha256"]
        binding_passed = binding_passed and matched
        binding_results.append(
            {
                "path": binding["path"],
                "expected_sha256": binding["sha256"],
                "actual_sha256": actual,
                "matched": matched,
                "path_error": path_error,
            }
        )

    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, evidence: Any) -> None:
        checks.append({"check_id": check_id, "passed": passed, "evidence": evidence})

    add(
        "responsibility_window_time",
        _aware_datetime(window["starts_at"], "starts_at") <= now
        <= _aware_datetime(window["expires_at"], "expires_at"),
        {
            "starts_at": window["starts_at"],
            "evaluated_at": now.isoformat(),
            "expires_at": window["expires_at"],
        },
    )
    add(
        "governance_generated_green",
        not governance_mismatch_paths,
        {"mismatches": sorted(governance_mismatch_paths)},
    )
    read_allowlist = window["read_allowlist"]
    missing_fixed_reads = sorted(
        path
        for path in RESTRUCTURE_BASELINE_FIXED_READ_SCOPES
        if not any(_path_is_allowed(path, allowed) for allowed in read_allowlist)
    )
    bound_reads_outside_allowlist = sorted(
        binding["path"]
        for binding in plan["bound_inputs"]
        if not any(
            _path_is_allowed(binding["path"], allowed)
            for allowed in read_allowlist
        )
    )
    add(
        "read_allowlist_complete",
        bool(read_allowlist)
        and not missing_fixed_reads
        and not bound_reads_outside_allowlist,
        {
            "read_allowlist": read_allowlist,
            "missing_fixed_reads": missing_fixed_reads,
            "bound_inputs_outside_allowlist": bound_reads_outside_allowlist,
        },
    )

    try:
        agents_text = bound_bytes["AGENTS.md"].decode("utf-8")
        current_state = _must_dict(
            json.loads(bound_bytes[CURRENT_STATE_PATH].decode("utf-8")),
            "CURRENT_STATE",
        )
        control = _must_dict(
            json.loads(bound_bytes[CONTROL_PATH].decode("utf-8")),
            "control_plane",
        )
    except (KeyError, UnicodeDecodeError, ValueError) as exc:
        raise ArtifactError("一级计划的现役真源无法从受绑定字节解析") from exc
    authority = _must_dict(current_state.get("authority"), "CURRENT_STATE.authority")
    external = _must_dict(authority.get("external_truth"), "CURRENT_STATE.authority.external_truth")
    control_source = _must_dict(control.get("source_authority"), "control_plane.source_authority")
    current_ledger = _must_nonempty_string(external.get("ledger_url"), "CURRENT_STATE ledger")
    current_queue = _must_nonempty_string(external.get("queue_url"), "CURRENT_STATE queue")
    agents_ledger = _markdown_authority_url(agents_text, "账序真源 v2")
    agents_queue = _markdown_authority_url(agents_text, "LEGACY 在跑队列")
    add(
        "current_authority_three_way",
        agents_ledger == current_ledger == control_source.get("ledger_url")
        and agents_queue == current_queue == control_source.get("queue_url"),
        {
            "agents": {"ledger_url": agents_ledger, "queue_url": agents_queue},
            "current_state": {"ledger_url": current_ledger, "queue_url": current_queue},
            "control_plane": {
                "ledger_url": control_source.get("ledger_url"),
                "queue_url": control_source.get("queue_url"),
            },
        },
    )
    legacy_ledger = _must_nonempty_string(
        external.get("legacy_frozen_ledger_url"),
        "CURRENT_STATE legacy_frozen_ledger_url",
    )
    historical_authorities = [
        {
            "name": str(row.get("name") or ""),
            "path": f"run_report_pairs[{index}].acceptance_authority_url",
            "url": row["acceptance_authority_url"],
        }
        for index, value in enumerate(_must_list(control.get("run_report_pairs"), "run_report_pairs"))
        if isinstance(value, dict)
        and (row := value).get("acceptance_authority_url")
    ]
    expected_historical = plan["historical_authority_expectations"]
    history_matches = historical_authorities == expected_historical
    current_url_reused = any(
        row["url"] == current_ledger for row in historical_authorities
    )
    add(
        "historical_authority_exact_match",
        history_matches
        and bool(expected_historical)
        and not current_url_reused,
        {
            "legacy_frozen_ledger_url": legacy_ledger,
            "expected_fields": expected_historical,
            "actual_fields": historical_authorities,
            "matches_expected": history_matches,
            "current_ledger_reused_in_historical_fields": current_url_reused,
            "rewritten": not history_matches,
        },
    )

    add("bound_input_sha", binding_passed, binding_results)

    normalized_dirty = sorted(
        {_repo_relative_path(path, "dirty_path") for path in dirty_paths}
    )
    owned = set(window["write_allowlist"])
    foreign_dirty = [path for path in normalized_dirty if path not in owned]
    conflicts = sorted(
        {
            dirty
            for dirty in foreign_dirty
            for candidate in window["candidate_write_paths"]
            if _path_overlap(dirty, candidate)
        }
    )
    add(
        "candidate_write_paths_disjoint_from_foreign_dirty",
        not conflicts,
        {
            "dirty_path_count": len(normalized_dirty),
            "dirty_paths_sha256": hashlib.sha256(
                "\0".join(normalized_dirty).encode("utf-8")
            ).hexdigest(),
            "owned_dirty_paths": sorted(path for path in normalized_dirty if path in owned),
            "foreign_dirty_path_count": len(foreign_dirty),
            "candidate_write_paths": window["candidate_write_paths"],
            "conflicts": conflicts,
        },
    )
    add(
        "head_frozen",
        head_sha == plan["expected_head_sha"],
        {
            "expected_head_sha": plan["expected_head_sha"],
            "actual_head_sha": head_sha,
        },
    )

    passed = all(row["passed"] for row in checks)
    return {
        "contract_version": RESTRUCTURE_BASELINE_RECEIPT_V1,
        "plan_id": plan["plan_id"],
        "plan_content_sha256": plan_content_sha256,
        "status": "PASS" if passed else "BLOCKED",
        "evaluated_at": now.isoformat(),
        "head_sha": head_sha,
        "responsibility_window": window,
        "authorization_boundary": {
            "authorizes_wave": False,
            "authorizes_notion_write": False,
            "authorizes_model_api": False,
            "authorization_context_claim_is_cryptographic_proof": False,
            "next_human_decision_if_pass": "D-08",
        },
        "runtime_effects": {
            "network_attempts": 0,
            "model_api_calls": 0,
            "tracked_repository_writes": 0,
            "receipt_writes": 1,
        },
        "evidence_snapshot": [
            {"path": path, "sha256": digest}
            for path, digest in sorted(evidence_reads.items())
        ],
        "checks": checks,
        "blockers": [row["check_id"] for row in checks if not row["passed"]],
    }


def _wave_plan(value: Any) -> dict[str, Any]:
    plan = _must_dict(value, "第二级 Wave 计划")
    if plan.get("contract_version") != RESTRUCTURE_WAVE_PLAN_V1:
        raise ArtifactError(
            f"第二级 Wave 计划 contract_version 必须是 {RESTRUCTURE_WAVE_PLAN_V1}"
        )
    _must_nonempty_string(plan.get("plan_id"), "plan_id")
    if plan.get("route") != "S0":
        raise ArtifactError("第二级 Wave 计划 route 只接受 S0")
    wave_id = _must_nonempty_string(plan.get("wave_id"), "wave_id")
    if wave_id not in RESTRUCTURE_WAVE_SPECS:
        raise ArtifactError(f"不支持的 Wave：{wave_id}")
    expected_head = _must_nonempty_string(plan.get("expected_head_sha"), "expected_head_sha")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise ArtifactError("expected_head_sha 必须是小写 40 位 Git SHA")
    for key in (
        "expected_baseline_plan_id",
        "expected_decision_ticket_id",
        "expected_lock_id",
    ):
        _must_nonempty_string(plan.get(key), key)
    plan["baseline_plan"] = _sha256_reference(
        plan.get("baseline_plan"),
        "baseline_plan",
    )
    plan["baseline_receipt"] = _sha256_reference(
        plan.get("baseline_receipt"),
        "baseline_receipt",
    )
    plan["decision_ticket"] = _sha256_reference(
        plan.get("decision_ticket"),
        "decision_ticket",
    )
    plan["conflict_lock"] = _sha256_reference(
        plan.get("conflict_lock"),
        "conflict_lock",
    )
    plan["test_impact"] = _sha256_reference(
        plan.get("test_impact"),
        "test_impact",
    )

    window = _must_dict(plan.get("responsibility_window"), "responsibility_window")
    for key in (
        "source_system",
        "authorization_context_id",
        "owner",
        "task_id",
        "wave_id",
        "starts_at",
        "expires_at",
    ):
        _must_nonempty_string(window.get(key), f"responsibility_window.{key}")
    if window["wave_id"] != wave_id:
        raise ArtifactError("responsibility_window.wave_id 与计划 wave_id 不一致")
    starts_at = _aware_datetime(window["starts_at"], "responsibility_window.starts_at")
    expires_at = _aware_datetime(window["expires_at"], "responsibility_window.expires_at")
    if expires_at <= starts_at:
        raise ArtifactError("责任窗口 expires_at 必须晚于 starts_at")
    for key in ("read_allowlist", "candidate_write_paths"):
        values = _must_list(window.get(key), f"responsibility_window.{key}")
        normalized = [
            _repo_relative_path(item, f"responsibility_window.{key}")
            for item in values
        ]
        if len(normalized) != len(set(normalized)):
            raise ArtifactError(f"responsibility_window.{key} 不能重复")
        window[key] = normalized

    limits = _must_dict(plan.get("capability_limits"), "capability_limits")
    normalized_limits: dict[str, bool] = {}
    for key in RESTRUCTURE_WAVE_SPECS[wave_id]["capability_limits"]:
        value = limits.get(key)
        if not isinstance(value, bool):
            raise ArtifactError(f"capability_limits.{key} 必须是布尔值")
        normalized_limits[key] = value
    plan["capability_limits"] = normalized_limits

    bindings = _must_list(plan.get("bound_inputs"), "bound_inputs")
    normalized_bindings: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    seen_roles: set[str] = set()
    for index, value in enumerate(bindings):
        row = _must_dict(value, f"bound_inputs[{index}]")
        path = _repo_relative_path(row.get("path"), f"bound_inputs[{index}].path")
        digest = _must_nonempty_string(
            row.get("sha256"),
            f"bound_inputs[{index}].sha256",
        )
        role = _must_nonempty_string(row.get("role"), f"bound_inputs[{index}].role")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ArtifactError(f"bound_inputs[{index}].sha256 必须是小写 SHA-256")
        if path in seen_paths:
            raise ArtifactError(f"bound_inputs 路径重复：{path}")
        if role in seen_roles:
            raise ArtifactError(f"bound_inputs role 重复：{role}")
        seen_paths.add(path)
        seen_roles.add(role)
        normalized_bindings.append(
            {"path": path, "sha256": digest, "role": role}
        )
    plan["bound_inputs"] = normalized_bindings

    dependencies = _must_list(plan.get("dependencies"), "dependencies")
    normalized_dependencies: list[dict[str, str]] = []
    for index, value in enumerate(dependencies):
        row = _must_dict(value, f"dependencies[{index}]")
        reference = _sha256_reference(row, f"dependencies[{index}]")
        reference["wave_id"] = _must_nonempty_string(
            row.get("wave_id"),
            f"dependencies[{index}].wave_id",
        )
        normalized_dependencies.append(reference)
    plan["dependencies"] = normalized_dependencies
    return plan


def _decision_ticket_evidence(
    ticket: dict[str, Any] | None,
    *,
    expected_ticket_id: str,
    wave_id: str,
    expected_context_id: str,
) -> tuple[bool, dict[str, Any]]:
    if ticket is None:
        return False, {"valid": False, "errors": ["决策票不存在或 SHA 不匹配"]}
    errors: list[str] = []
    if ticket.get("contract_version") != RESTRUCTURE_DECISION_TICKET_V1:
        errors.append("contract_version 不匹配")
    if ticket.get("ticket_id") != expected_ticket_id:
        errors.append("ticket_id 不匹配")
    if ticket.get("authority") != "CZ":
        errors.append("authority 必须是 CZ")
    if ticket.get("authorization_context_id") != expected_context_id:
        errors.append("authorization_context_id 不匹配")
    if ticket.get("evidence_class") != "same_task_human_readback":
        errors.append("evidence_class 必须是 same_task_human_readback")
    review = ticket.get("human_readback")
    if review != {
        "required": True,
        "confirmed": True,
        "cryptographic_proof": False,
    }:
        errors.append("human_readback 必须明确同任务人工回读且不冒充密码学证明")
    if ticket.get("selected_route") != "S0":
        errors.append("selected_route 必须是 S0")
    selected_scope = ticket.get("selected_scope")
    if not isinstance(selected_scope, list) or wave_id not in selected_scope:
        errors.append("selected_scope 未包含当前 Wave")
    messages = ticket.get("source_messages")
    message_evidence: list[dict[str, Any]] = []
    source_texts: set[str] = set()
    if not isinstance(messages, list):
        errors.append("source_messages 必须是数组")
    else:
        for index, raw in enumerate(messages):
            if not isinstance(raw, dict):
                errors.append(f"source_messages[{index}] 不是对象")
                continue
            text = raw.get("text")
            digest = raw.get("sha256")
            matched = (
                isinstance(text, str)
                and isinstance(digest, str)
                and _sha256_text(text) == digest
            )
            if isinstance(text, str):
                source_texts.add(text)
            message_evidence.append(
                {"index": index, "sha256_matched": matched}
            )
            if not matched:
                errors.append(f"source_messages[{index}] SHA 不匹配")
    if not {"按s0", "S-01-A"} <= source_texts:
        errors.append("source_messages 缺少 CZ 的两次原始选择")

    decisions = ticket.get("decisions")
    decision_evidence: dict[str, Any] = {}
    if not isinstance(decisions, dict):
        errors.append("decisions 必须是对象")
        decisions = {}
    for decision_id, expected in S0_DECISION_VALUES.items():
        raw = decisions.get(decision_id)
        actual = (
            (raw.get("status"), raw.get("value"))
            if isinstance(raw, dict)
            else None
        )
        matched = actual == expected
        decision_evidence[decision_id] = {
            "expected": {"status": expected[0], "value": expected[1]},
            "actual": (
                {"status": actual[0], "value": actual[1]}
                if actual is not None
                else None
            ),
            "matched": matched,
        }
        if not matched:
            errors.append(f"{decision_id} 缺失或口径不匹配")
    if set(decisions) != set(S0_DECISION_VALUES):
        errors.append("decisions 必须恰好包含 D-01～D-10")

    boundary = ticket.get("authorization_boundary")
    expected_boundary = {
        "authorizes_wave_without_second_level_pass": False,
        "authorizes_notion_write": False,
        "authorizes_model_api": False,
        "authorizes_preflight": False,
        "authorizes_external_removal": False,
    }
    if boundary != expected_boundary:
        errors.append("authorization_boundary 不匹配")
    return not errors, {
        "valid": not errors,
        "errors": errors,
        "source_messages": message_evidence,
        "decisions": decision_evidence,
    }


def _baseline_receipt_evidence(
    root: Path,
    plan: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
    *,
    expected_plan_id: str,
    expected_head_sha: str,
    expected_context_id: str,
    dirty_paths: list[str],
    governance_mismatch_paths: list[str],
    evidence_reads: dict[str, str],
    now: datetime,
) -> tuple[bool, dict[str, Any]]:
    errors: list[str] = []
    fixed_check_ids = {
        "responsibility_window_time",
        "governance_generated_green",
        "read_allowlist_complete",
        "current_authority_three_way",
        "historical_authority_exact_match",
        "bound_input_sha",
        "candidate_write_paths_disjoint_from_foreign_dirty",
        "head_frozen",
        "live_snapshot_stable",
    }
    if plan is None:
        return False, {"valid": False, "errors": ["一级计划不存在或 SHA 不匹配"]}
    if receipt is None:
        return False, {"valid": False, "errors": ["一级票不存在或 SHA 不匹配"]}
    try:
        normalized_plan = _baseline_plan(copy.deepcopy(plan))
    except ArtifactError as exc:
        return False, {"valid": False, "errors": [f"一级计划无效：{exc}"]}
    plan_sha256 = _canonical_json_sha256(normalized_plan)
    if normalized_plan.get("plan_id") != expected_plan_id:
        errors.append("一级计划 plan_id 不匹配")
    plan_window = normalized_plan.get("responsibility_window")
    if (
        not isinstance(plan_window, dict)
        or plan_window.get("authorization_context_id") != expected_context_id
    ):
        errors.append("一级计划 authorization_context_id 不匹配")
    if receipt.get("contract_version") != RESTRUCTURE_BASELINE_RECEIPT_V1:
        errors.append("contract_version 不匹配")
    if receipt.get("plan_id") != expected_plan_id:
        errors.append("plan_id 不匹配")
    if receipt.get("status") != "PASS" or receipt.get("blockers") != []:
        errors.append("一级票不是无 blocker 的 PASS")
    if receipt.get("head_sha") != expected_head_sha:
        errors.append("一级票 HEAD 不匹配")
    if receipt.get("plan_content_sha256") != plan_sha256:
        errors.append("一级票没有绑定原始一级计划内容")
    checks = receipt.get("checks")
    if not isinstance(checks, list):
        errors.append("一级票缺完整 checks")
    else:
        check_ids = {
            row.get("check_id")
            for row in checks
            if isinstance(row, dict)
        }
        if check_ids != fixed_check_ids or len(checks) != len(fixed_check_ids):
            errors.append("一级票 checks 集合不完整或有重复")
        if any(
            not isinstance(row, dict) or row.get("passed") is not True
            for row in checks
        ):
            errors.append("一级票存在未通过 check")
    boundary = receipt.get("authorization_boundary")
    expected_boundary = {
        "authorizes_wave": False,
        "authorizes_notion_write": False,
        "authorizes_model_api": False,
        "authorization_context_claim_is_cryptographic_proof": False,
        "next_human_decision_if_pass": "D-08",
    }
    if boundary != expected_boundary:
        errors.append("一级票越权")
    window = receipt.get("responsibility_window")
    if not isinstance(window, dict):
        errors.append("一级票缺责任窗口")
    else:
        if window != plan_window:
            errors.append("一级票责任窗口与一级计划不一致")
        if window.get("authorization_context_id") != expected_context_id:
            errors.append("一级票 authorization_context_id 不匹配")
        try:
            starts = _aware_datetime(window.get("starts_at"), "baseline.starts_at")
            expires = _aware_datetime(window.get("expires_at"), "baseline.expires_at")
            if not starts <= now <= expires:
                errors.append("一级票责任窗口已失效")
        except ArtifactError as exc:
            errors.append(str(exc))
    fresh = _evaluate_restructure_baseline_snapshot(
        root,
        normalized_plan,
        dirty_paths=dirty_paths,
        head_sha=expected_head_sha,
        governance_mismatch_paths=governance_mismatch_paths,
        evaluated_at=now,
    )
    for row in fresh.get("evidence_snapshot", []):
        if not isinstance(row, dict):
            errors.append("一级重放证据快照格式无效")
            continue
        path = row.get("path")
        digest = row.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str):
            errors.append("一级重放证据快照字段无效")
            continue
        prior = evidence_reads.setdefault(path, digest)
        if prior != digest:
            errors.append(f"一级重放期间证据发生变化：{path}")
    if fresh["status"] != "PASS":
        errors.append("一级计划按当前现场重放不是 PASS")
    return not errors, {
        "valid": not errors,
        "errors": errors,
        "plan_content_sha256": plan_sha256,
        "fresh_status": fresh["status"],
        "fresh_blockers": fresh["blockers"],
    }


def _lock_receipt_evidence(
    receipt: dict[str, Any] | None,
    *,
    expected_lock_id: str,
    wave_id: str,
    expected_head_sha: str,
    owner: str,
    candidate_write_paths: list[str],
    expected_context_id: str,
    now: datetime,
) -> tuple[bool, dict[str, Any]]:
    errors: list[str] = []
    if receipt is None:
        return False, {"valid": False, "errors": ["冲突锁不存在或 SHA 不匹配"]}
    if receipt.get("contract_version") != RESTRUCTURE_WAVE_LOCK_RECEIPT_V1:
        errors.append("contract_version 不匹配")
    if receipt.get("status") != "ACTIVE":
        errors.append("冲突锁不是 ACTIVE")
    if receipt.get("lock_id") != expected_lock_id:
        errors.append("lock_id 不匹配")
    if receipt.get("scope") != wave_id:
        errors.append("scope 不匹配")
    if receipt.get("holder") != owner:
        errors.append("holder 不匹配")
    if receipt.get("authorization_context_id") != expected_context_id:
        errors.append("authorization_context_id 不匹配")
    if receipt.get("head_sha") != expected_head_sha:
        errors.append("冲突锁 HEAD 不匹配")
    expected_paths_sha = _sha256_list(candidate_write_paths)
    if receipt.get("candidate_write_paths_sha256") != expected_paths_sha:
        errors.append("冲突锁写集 SHA 不匹配")
    try:
        starts = _aware_datetime(receipt.get("starts_at"), "lock.starts_at")
        expires = _aware_datetime(receipt.get("expires_at"), "lock.expires_at")
        if not starts <= now <= expires:
            errors.append("冲突锁不在有效期")
    except ArtifactError as exc:
        errors.append(str(exc))
    return not errors, {"valid": not errors, "errors": errors}


def _test_impact_evidence(
    impact: dict[str, Any] | None,
    *,
    wave_id: str,
    expected_head_sha: str,
    candidate_write_paths: list[str],
    expected_context_id: str,
    policy: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    errors: list[str] = []
    if impact is None:
        return False, {"valid": False, "errors": ["测试影响单不存在或 SHA 不匹配"]}
    if impact.get("contract_version") != RESTRUCTURE_TEST_IMPACT_V1:
        errors.append("contract_version 不匹配")
    if impact.get("wave_id") != wave_id or impact.get("route") != "S0":
        errors.append("Wave 或路线不匹配")
    if impact.get("head_sha") != expected_head_sha:
        errors.append("测试影响单 HEAD 不匹配")
    if impact.get("authorization_context_id") != expected_context_id:
        errors.append("测试影响单 authorization_context_id 不匹配")
    if impact.get("classification") != "full_chain_required":
        errors.append("未知新路径必须标为 full_chain_required")
    if impact.get("planned_changed_paths") != candidate_write_paths:
        errors.append("planned_changed_paths 与精确写集不一致")
    evidence = impact.get("pre_start_evidence")
    if not isinstance(evidence, dict):
        errors.append("缺少 pre_start_evidence")
    else:
        if evidence.get("governance_check") != "PASS":
            errors.append("治理检查没有 PASS")
        if evidence.get("ruff_check") != "PASS":
            errors.append("Ruff 没有 PASS")
        full_suite = evidence.get("full_suite")
        if not isinstance(full_suite, dict):
            errors.append("缺少整仓测试证据")
        else:
            if full_suite.get("status") != "KNOWN_FAILURE_SET_UNCHANGED":
                errors.append("整仓测试状态不认识")
            if full_suite.get("new_failure_count") != 0:
                errors.append("出现新增失败")
            failed = full_suite.get("failed")
            nodeids = full_suite.get("known_failure_nodeids")
            if (
                not isinstance(failed, int)
                or not isinstance(nodeids, list)
                or failed != len(nodeids)
                or len(nodeids) != len(set(nodeids))
            ):
                errors.append("已知失败数量与 nodeid 清单不一致")
    commands = impact.get("required_after_change_commands")
    required_commands = {
        policy.get("full_chain_command"),
        policy.get("lint_command"),
        "python3 tools/governance_index.py --check",
    }
    if not isinstance(commands, list) or not required_commands <= set(commands):
        errors.append("改动后必跑命令不完整")
    return not errors, {"valid": not errors, "errors": errors}


def _wave_dependency_evidence(
    root: Path,
    dependencies: list[dict[str, str]],
    *,
    wave_id: str,
    expected_head_sha: str,
    expected_context_id: str,
    evidence_reads: dict[str, str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    requires_wave1 = bool(
        RESTRUCTURE_WAVE_SPECS[wave_id]["requires_wave1_receipt"]
    )
    if not requires_wave1:
        return not dependencies, {
            "valid": not dependencies,
            "errors": [] if not dependencies else ["Wave1 不得声明上游 Wave 依赖"],
        }
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if len(dependencies) != 1 or dependencies[0]["wave_id"] != WAVE1_DIRECTORY_REGISTRY:
        return False, {
            "valid": False,
            "errors": ["S0 materialize 必须绑定唯一 Wave1 完成票"],
        }
    payload, reference = _reference_payload(
        root,
        dependencies[0],
        evidence_reads=evidence_reads,
    )
    rows.append(reference)
    if payload is None:
        errors.append("Wave1 完成票不存在或 SHA 不匹配")
    else:
        if payload.get("contract_version") != RESTRUCTURE_WAVE_COMPLETION_V1:
            errors.append("Wave1 完成票 contract_version 不匹配")
        if payload.get("wave_id") != WAVE1_DIRECTORY_REGISTRY:
            errors.append("Wave1 完成票 wave_id 不匹配")
        if payload.get("status") != "PASS":
            errors.append("Wave1 完成票不是 PASS")
        if payload.get("head_sha") != expected_head_sha:
            errors.append("Wave1 完成票 HEAD 不匹配")
        if payload.get("authorization_context_id") != expected_context_id:
            errors.append("Wave1 完成票 authorization_context_id 不匹配")
        try:
            wave_plan_reference = _sha256_reference(
                payload.get("wave_plan"),
                "Wave1 完成票.wave_plan",
            )
        except ArtifactError as exc:
            errors.append(str(exc))
            wave_plan_reference = None
        wave_plan = None
        wave_plan_evidence = None
        normalized_wave_plan = None
        if wave_plan_reference is not None:
            wave_plan, wave_plan_evidence = _reference_payload(
                root,
                wave_plan_reference,
                evidence_reads=evidence_reads,
            )
            if wave_plan is None:
                errors.append("Wave1 二级计划不存在或 SHA 不匹配")
            else:
                try:
                    normalized_wave_plan = _wave_plan(
                        copy.deepcopy(wave_plan)
                    )
                except ArtifactError as exc:
                    errors.append(f"Wave1 二级计划无效：{exc}")
        wave_plan_sha = (
            _canonical_json_sha256(normalized_wave_plan)
            if normalized_wave_plan is not None
            else None
        )
        if normalized_wave_plan is not None:
            plan_window = normalized_wave_plan["responsibility_window"]
            expected_wave_spec = RESTRUCTURE_WAVE_SPECS[
                WAVE1_DIRECTORY_REGISTRY
            ]
            if (
                normalized_wave_plan.get("wave_id")
                != WAVE1_DIRECTORY_REGISTRY
                or normalized_wave_plan.get("expected_head_sha")
                != payload.get("pre_wave_head_sha")
                or plan_window.get("authorization_context_id")
                != expected_context_id
                or plan_window.get("candidate_write_paths")
                != expected_wave_spec["candidate_write_paths"]
                or normalized_wave_plan.get("capability_limits")
                != expected_wave_spec["capability_limits"]
                or normalized_wave_plan.get("dependencies") != []
            ):
                errors.append("Wave1 二级计划范围、HEAD 或授权上下文不匹配")
            if payload.get("wave_plan_content_sha256") != wave_plan_sha:
                errors.append("Wave1 完成票没有绑定实际二级计划内容")
        try:
            wave_receipt_reference = _sha256_reference(
                payload.get("wave_receipt"),
                "Wave1 完成票.wave_receipt",
            )
        except ArtifactError as exc:
            errors.append(str(exc))
            wave_receipt_reference = None
        wave_receipt = None
        wave_receipt_evidence = None
        if wave_receipt_reference is not None:
            wave_receipt, wave_receipt_evidence = _reference_payload(
                root,
                wave_receipt_reference,
                evidence_reads=evidence_reads,
            )
            if wave_receipt is None:
                errors.append("Wave1 二级开工票不存在或 SHA 不匹配")
        expected_wave_checks = {
            "responsibility_window_time",
            "governance_generated_green",
            "head_frozen",
            "wave_scope_exact",
            "baseline_receipt_current",
            "decision_ticket_exact",
            "conflict_lock_active",
            "test_impact_complete",
            "bound_input_sha",
            "read_allowlist_complete",
            "candidate_write_paths_disjoint_from_dirty",
            "wave_dependencies_satisfied",
            "live_snapshot_stable",
        }
        if wave_receipt is not None:
            if (
                wave_receipt.get("contract_version")
                != RESTRUCTURE_WAVE_RECEIPT_V1
                or wave_receipt.get("wave_id") != WAVE1_DIRECTORY_REGISTRY
                or wave_receipt.get("status") != "PASS"
                or wave_receipt.get("blockers") != []
            ):
                errors.append("Wave1 二级开工票不是无 blocker 的 PASS")
            wave_window = wave_receipt.get("responsibility_window")
            if (
                not isinstance(wave_window, dict)
                or wave_window.get("authorization_context_id")
                != expected_context_id
            ):
                errors.append("Wave1 二级开工票授权上下文不匹配")
            wave_checks = wave_receipt.get("checks")
            if not isinstance(wave_checks, list):
                errors.append("Wave1 二级开工票缺完整 checks")
            else:
                wave_check_ids = {
                    row.get("check_id")
                    for row in wave_checks
                    if isinstance(row, dict)
                }
                if (
                    wave_check_ids != expected_wave_checks
                    or len(wave_checks) != len(expected_wave_checks)
                    or any(
                        not isinstance(row, dict)
                        or row.get("passed") is not True
                        for row in wave_checks
                    )
                ):
                    errors.append("Wave1 二级开工票 checks 不完整或未全过")
            boundary = wave_receipt.get("authorization_boundary")
            expected_paths = RESTRUCTURE_WAVE_SPECS[
                WAVE1_DIRECTORY_REGISTRY
            ]["candidate_write_paths"]
            if (
                not isinstance(boundary, dict)
                or boundary.get("authorizes_wave") is not False
                or boundary.get("mechanical_preconditions_pass") is not True
                or boundary.get("requires_same_task_human_readback") is not True
                or boundary.get("eligible_wave_id")
                != WAVE1_DIRECTORY_REGISTRY
                or boundary.get("eligible_write_paths") != expected_paths
            ):
                errors.append("Wave1 二级票机械范围或人工回读边界不匹配")
            plan_sha = wave_receipt.get("plan_content_sha256")
            if (
                not isinstance(plan_sha, str)
                or not re.fullmatch(r"[0-9a-f]{64}", plan_sha)
                or wave_plan_sha != plan_sha
            ):
                errors.append("Wave1 完成票没有绑定二级计划 SHA")
            if (
                normalized_wave_plan is None
                or wave_receipt.get("plan_id")
                != normalized_wave_plan.get("plan_id")
            ):
                errors.append("Wave1 二级票 plan_id 与实际计划不一致")
            if payload.get("pre_wave_head_sha") != wave_receipt.get("head_sha"):
                errors.append("Wave1 完成票起始 HEAD 与二级票不一致")

        outputs = payload.get("outputs")
        expected_output_paths = RESTRUCTURE_WAVE_SPECS[
            WAVE1_DIRECTORY_REGISTRY
        ]["candidate_write_paths"]
        output_evidence: list[dict[str, Any]] = []
        if not isinstance(outputs, list):
            errors.append("Wave1 完成票缺逐文件输出清单")
            outputs = []
        actual_output_paths = [
            row.get("path") for row in outputs if isinstance(row, dict)
        ]
        if actual_output_paths != expected_output_paths:
            errors.append("Wave1 完成票输出路径不等于 Wave1 精确写集")
        for index, row in enumerate(outputs):
            if not isinstance(row, dict):
                errors.append(f"Wave1 outputs[{index}] 不是对象")
                continue
            try:
                _repo_path_without_symlinks(
                    root,
                    Path(row.get("path", "")),
                    name=f"Wave1 outputs[{index}]",
                )
            except (ArtifactError, TypeError) as exc:
                errors.append(str(exc))
                continue
            expected_sha = row.get("sha256")
            try:
                output_raw = _read_repo_bytes_once(
                    root,
                    row.get("path", ""),
                )
                actual_sha = hashlib.sha256(output_raw).hexdigest()
                exists = True
                if evidence_reads is not None:
                    prior = evidence_reads.setdefault(
                        row.get("path", ""),
                        actual_sha,
                    )
                    if prior != actual_sha:
                        raise ArtifactError(
                            "同一 Wave1 输出在本轮读取期间内容发生变化"
                        )
            except (ArtifactError, OSError, TypeError) as exc:
                exists = False
                actual_sha = None
                errors.append(str(exc))
            matched = (
                exists
                and isinstance(expected_sha, str)
                and re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None
                and actual_sha == expected_sha
            )
            output_evidence.append(
                {
                    "path": row.get("path"),
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "matched": matched,
                }
            )
            if not matched:
                errors.append(f"Wave1 输出文件不匹配：{row.get('path')}")
        if payload.get("output_manifest_sha256") != _canonical_json_sha256(outputs):
            errors.append("Wave1 输出清单 SHA 不匹配")

        pre_wave_head = payload.get("pre_wave_head_sha")
        if (
            not isinstance(pre_wave_head, str)
            or re.fullmatch(r"[0-9a-f]{40}", pre_wave_head) is None
        ):
            errors.append("Wave1 完成票缺合法起始 HEAD")
            git_evidence = {"valid": False}
        else:
            try:
                current_head = git_head(root)
                ancestor = git_is_ancestor(
                    root,
                    pre_wave_head,
                    expected_head_sha,
                )
                changes = git_name_status_between(
                    root,
                    pre_wave_head,
                    expected_head_sha,
                )
                changed_paths = [row["path"] for row in changes]
                changes_valid = (
                    len(changes) == len(expected_output_paths)
                    and all(row["status"] in {"A", "M"} for row in changes)
                    and set(changed_paths) == set(expected_output_paths)
                )
                if current_head != expected_head_sha:
                    errors.append("当前 Git HEAD 不是 Wave1 完成 HEAD")
                if not ancestor:
                    errors.append("Wave1 起始 HEAD 不是完成 HEAD 的祖先")
                if not changes_valid:
                    errors.append("Wave1 Git 变更不等于精确写集或含删除")
                git_evidence = {
                    "valid": (
                        current_head == expected_head_sha
                        and ancestor
                        and changes_valid
                    ),
                    "current_head": current_head,
                    "ancestor": ancestor,
                    "changes": changes,
                }
            except (ArtifactError, OSError, subprocess.SubprocessError) as exc:
                errors.append(f"Wave1 Git 变更无法回查：{exc}")
                git_evidence = {"valid": False, "error": str(exc)}
        rows.append(
            {
                "wave_plan": wave_plan_evidence,
                "wave_receipt": wave_receipt_evidence,
                "outputs": output_evidence,
                "git_transition": git_evidence,
            }
        )
    return not errors, {"valid": not errors, "errors": errors, "references": rows}


def _evaluate_restructure_wave_snapshot(
    root: Path,
    plan_raw: Any,
    *,
    dirty_paths: list[str],
    head_sha: str,
    governance_mismatch_paths: list[str],
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    plan = _wave_plan(copy.deepcopy(plan_raw))
    wave_id = plan["wave_id"]
    spec = RESTRUCTURE_WAVE_SPECS[wave_id]
    window = plan["responsibility_window"]
    now = evaluated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ArtifactError("evaluated_at 必须带时区")
    evidence_reads: dict[str, str] = {}
    bound_bytes: dict[str, bytes] = {}
    binding_results: list[dict[str, Any]] = []
    bindings_passed = True
    for binding in plan["bound_inputs"]:
        path_error = None
        try:
            raw = _read_repo_bytes_once(root, binding["path"])
            actual = hashlib.sha256(raw).hexdigest()
            prior = evidence_reads.setdefault(binding["path"], actual)
            if prior != actual:
                raise ArtifactError("同一输入在本轮读取期间内容发生变化")
            bound_bytes[binding["path"]] = raw
            exists = True
        except (ArtifactError, OSError) as exc:
            actual = None
            exists = False
            path_error = str(exc)
        matched = exists and actual == binding["sha256"]
        bindings_passed = bindings_passed and matched
        binding_results.append(
            {
                **binding,
                "exists": exists,
                "actual_sha256": actual,
                "matched": matched,
                "path_error": path_error,
            }
        )
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, evidence: Any) -> None:
        checks.append({"check_id": check_id, "passed": passed, "evidence": evidence})

    add(
        "responsibility_window_time",
        _aware_datetime(window["starts_at"], "starts_at") <= now
        <= _aware_datetime(window["expires_at"], "expires_at"),
        {
            "starts_at": window["starts_at"],
            "evaluated_at": now.isoformat(),
            "expires_at": window["expires_at"],
        },
    )
    add(
        "governance_generated_green",
        not governance_mismatch_paths,
        {"mismatches": sorted(governance_mismatch_paths)},
    )
    add(
        "head_frozen",
        head_sha == plan["expected_head_sha"],
        {
            "expected_head_sha": plan["expected_head_sha"],
            "actual_head_sha": head_sha,
        },
    )
    expected_paths = list(spec["candidate_write_paths"])
    add(
        "wave_scope_exact",
        window["candidate_write_paths"] == expected_paths
        and plan["capability_limits"] == spec["capability_limits"],
        {
            "expected_candidate_write_paths": expected_paths,
            "actual_candidate_write_paths": window["candidate_write_paths"],
            "expected_capability_limits": spec["capability_limits"],
            "actual_capability_limits": plan["capability_limits"],
        },
    )

    baseline_plan, baseline_plan_reference = _reference_payload(
        root,
        plan["baseline_plan"],
        evidence_reads=evidence_reads,
        captured_bytes=bound_bytes,
    )
    baseline, baseline_reference = _reference_payload(
        root,
        plan["baseline_receipt"],
        evidence_reads=evidence_reads,
        captured_bytes=bound_bytes,
    )
    baseline_passed, baseline_evidence = _baseline_receipt_evidence(
        root,
        baseline_plan,
        baseline,
        expected_plan_id=plan["expected_baseline_plan_id"],
        expected_head_sha=plan["expected_head_sha"],
        expected_context_id=window["authorization_context_id"],
        dirty_paths=dirty_paths,
        governance_mismatch_paths=governance_mismatch_paths,
        evidence_reads=evidence_reads,
        now=now,
    )
    baseline_evidence["plan_reference"] = baseline_plan_reference
    baseline_evidence["reference"] = baseline_reference
    add("baseline_receipt_current", baseline_passed, baseline_evidence)

    decision, decision_reference = _reference_payload(
        root,
        plan["decision_ticket"],
        evidence_reads=evidence_reads,
        captured_bytes=bound_bytes,
    )
    decision_passed, decision_evidence = _decision_ticket_evidence(
        decision,
        expected_ticket_id=plan["expected_decision_ticket_id"],
        wave_id=wave_id,
        expected_context_id=window["authorization_context_id"],
    )
    decision_evidence["reference"] = decision_reference
    add("decision_ticket_exact", decision_passed, decision_evidence)

    lock, lock_reference = _reference_payload(
        root,
        plan["conflict_lock"],
        evidence_reads=evidence_reads,
        captured_bytes=bound_bytes,
    )
    lock_passed, lock_evidence = _lock_receipt_evidence(
        lock,
        expected_lock_id=plan["expected_lock_id"],
        wave_id=wave_id,
        expected_head_sha=plan["expected_head_sha"],
        owner=window["owner"],
        candidate_write_paths=expected_paths,
        expected_context_id=window["authorization_context_id"],
        now=now,
    )
    lock_evidence["reference"] = lock_reference
    add("conflict_lock_active", lock_passed, lock_evidence)

    try:
        policy = _must_dict(
            json.loads(
                bound_bytes["governance/test_policy.json"].decode("utf-8")
            ),
            "test_policy",
        )
    except (KeyError, UnicodeDecodeError, ValueError) as exc:
        raise ArtifactError("测试纪律无法从受绑定字节解析") from exc
    impact, impact_reference = _reference_payload(
        root,
        plan["test_impact"],
        evidence_reads=evidence_reads,
        captured_bytes=bound_bytes,
    )
    impact_passed, impact_evidence = _test_impact_evidence(
        impact,
        wave_id=wave_id,
        expected_head_sha=plan["expected_head_sha"],
        candidate_write_paths=expected_paths,
        expected_context_id=window["authorization_context_id"],
        policy=policy,
    )
    impact_evidence["reference"] = impact_reference
    add("test_impact_complete", impact_passed, impact_evidence)

    required_paths = set(spec["required_inputs"]) | {
        plan["baseline_plan"]["path"],
        plan["baseline_receipt"]["path"],
        plan["decision_ticket"]["path"],
        plan["conflict_lock"]["path"],
        plan["test_impact"]["path"],
        *(row["path"] for row in plan["dependencies"]),
    }
    binding_paths = {row["path"] for row in plan["bound_inputs"]}
    missing_inputs = sorted(required_paths - binding_paths)
    bindings_passed = bindings_passed and not missing_inputs
    add(
        "bound_input_sha",
        bindings_passed,
        {"missing_required_inputs": missing_inputs, "inputs": binding_results},
    )

    read_allowlist = window["read_allowlist"]
    missing_read_scopes = sorted(
        path
        for path in RESTRUCTURE_WAVE_FIXED_READ_SCOPES
        if not any(_path_is_allowed(path, allowed) for allowed in read_allowlist)
    )
    reads_outside = sorted(
        path
        for path in binding_paths
        if not any(_path_is_allowed(path, allowed) for allowed in read_allowlist)
    )
    add(
        "read_allowlist_complete",
        bool(read_allowlist) and not missing_read_scopes and not reads_outside,
        {
            "read_allowlist": read_allowlist,
            "missing_fixed_scopes": missing_read_scopes,
            "bound_inputs_outside_allowlist": reads_outside,
        },
    )

    normalized_dirty = sorted(
        {_repo_relative_path(path, "dirty_path") for path in dirty_paths}
    )
    conflicts = sorted(
        {
            dirty
            for dirty in normalized_dirty
            for candidate in expected_paths
            if _path_overlap(dirty, candidate)
        }
    )
    add(
        "candidate_write_paths_disjoint_from_dirty",
        not conflicts,
        {
            "dirty_path_count": len(normalized_dirty),
            "dirty_paths_sha256": _sha256_list(normalized_dirty),
            "candidate_write_paths": expected_paths,
            "conflicts": conflicts,
        },
    )

    dependency_passed, dependency_evidence = _wave_dependency_evidence(
        root,
        plan["dependencies"],
        wave_id=wave_id,
        expected_head_sha=plan["expected_head_sha"],
        expected_context_id=window["authorization_context_id"],
        evidence_reads=evidence_reads,
    )
    add("wave_dependencies_satisfied", dependency_passed, dependency_evidence)

    passed = all(row["passed"] for row in checks)
    return {
        "contract_version": RESTRUCTURE_WAVE_RECEIPT_V1,
        "plan_id": plan["plan_id"],
        "plan_content_sha256": _canonical_json_sha256(plan),
        "status": "PASS" if passed else "BLOCKED",
        "evaluated_at": now.isoformat(),
        "head_sha": head_sha,
        "route": "S0",
        "wave_id": wave_id,
        "responsibility_window": window,
        "authorization_boundary": {
            "authorizes_wave": False,
            "mechanical_preconditions_pass": passed,
            "eligible_wave_id": wave_id if passed else None,
            "eligible_write_paths": expected_paths if passed else [],
            "requires_same_task_human_readback": True,
            "authorizes_physical_move": False,
            "authorizes_delete": False,
            "authorizes_preflight": False,
            "authorizes_notion_write": False,
            "authorizes_model_api": False,
            "authorizes_external_removal": False,
            "authorization_context_claim_is_cryptographic_proof": False,
        },
        "runtime_effects": {
            "network_attempts": 0,
            "model_api_calls": 0,
            "tracked_repository_writes": 0,
            "receipt_writes": 1,
        },
        "evidence_snapshot": [
            {"path": path, "sha256": digest}
            for path, digest in sorted(evidence_reads.items())
        ],
        "checks": checks,
        "blockers": [row["check_id"] for row in checks if not row["passed"]],
    }


def _wave_lock_request(value: Any) -> dict[str, Any]:
    request = _must_dict(value, "Wave 冲突锁请求")
    if request.get("contract_version") != RESTRUCTURE_WAVE_LOCK_REQUEST_V1:
        raise ArtifactError(
            f"Wave 冲突锁 contract_version 必须是 {RESTRUCTURE_WAVE_LOCK_REQUEST_V1}"
        )
    for key in (
        "lock_id",
        "scope",
        "holder",
        "authorization_context_id",
        "expected_head_sha",
        "starts_at",
        "expires_at",
    ):
        _must_nonempty_string(request.get(key), key)
    wave_id = request["scope"]
    if wave_id not in RESTRUCTURE_WAVE_SPECS:
        raise ArtifactError(f"不支持的 Wave 锁范围：{wave_id}")
    if not re.fullmatch(r"[0-9a-f]{40}", request["expected_head_sha"]):
        raise ArtifactError("expected_head_sha 必须是小写 40 位 Git SHA")
    starts_at = _aware_datetime(request["starts_at"], "starts_at")
    expires_at = _aware_datetime(request["expires_at"], "expires_at")
    if expires_at <= starts_at:
        raise ArtifactError("冲突锁 expires_at 必须晚于 starts_at")
    paths = _must_list(request.get("candidate_write_paths"), "candidate_write_paths")
    request["candidate_write_paths"] = [
        _repo_relative_path(path, "candidate_write_paths") for path in paths
    ]
    if request["candidate_write_paths"] != RESTRUCTURE_WAVE_SPECS[wave_id][
        "candidate_write_paths"
    ]:
        raise ArtifactError("冲突锁写集必须与 Wave 精确白名单一致")
    return request


def _wave_lock_output_path(root: Path, value: Path, wave_id: str) -> Path:
    root = root.resolve()
    path = _repo_path_without_symlinks(
        root,
        value,
        name="Wave 冲突锁",
    )
    expected = (
        root
        / "TEMP/restructure_wave_preflight/locks"
        / f"{wave_id}.lock.json"
    )
    if path != expected:
        raise ArtifactError(f"Wave 冲突锁只能写入固定路径：{expected}")
    if path.exists():
        raise ArtifactError(f"拒绝覆盖既有 Wave 冲突锁：{path}")
    return path


def _safe_unlink_repo_file(root: Path, output: Path) -> bool:
    root = root.resolve()
    try:
        path = _repo_path_without_symlinks(
            root,
            output,
            name="待撤销重构机器票",
        )
        relative = path.relative_to(root)
        directory_descriptor = _open_repo_directory_chain(
            root,
            relative.parts[:-1],
            create=False,
        )
    except (ArtifactError, OSError, ValueError):
        return False
    try:
        os.unlink(relative.name, dir_fd=directory_descriptor)
        os.fsync(directory_descriptor)
        return True
    except FileNotFoundError:
        return True
    finally:
        os.close(directory_descriptor)


def _write_json_exclusive(root: Path, output: Path, value: dict[str, Any]) -> None:
    root = root.resolve()
    output = _repo_path_without_symlinks(root, output, name="重构机器票")
    relative = output.relative_to(root)
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        directory_descriptor = _open_repo_directory_chain(
            root,
            relative.parts[:-1],
            create=True,
        )
    except OSError as exc:
        raise ArtifactError(
            f"重构机器票目录无法安全逐级打开：{output.parent}"
        ) from exc
    descriptor: int | None = None
    created = False
    try:
        try:
            descriptor = os.open(
                relative.name,
                flags,
                0o600,
                dir_fd=directory_descriptor,
            )
            created = True
        except FileExistsError as exc:
            raise ArtifactError(f"拒绝覆盖既有重构机器票：{output}") from exc
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(encoded)
                stream.flush()
            os.fsync(descriptor)
            written_stat = os.fstat(descriptor)
            verified_path = _repo_path_without_symlinks(
                root,
                output,
                name="已写重构机器票",
            )
            visible_stat = os.stat(verified_path, follow_symlinks=False)
            if (
                visible_stat.st_dev,
                visible_stat.st_ino,
            ) != (
                written_stat.st_dev,
                written_stat.st_ino,
            ):
                raise ArtifactError("机器票写入路径在落盘期间被替换")
            os.fsync(directory_descriptor)
        except BaseException:
            if created:
                try:
                    os.unlink(relative.name, dir_fd=directory_descriptor)
                except FileNotFoundError:
                    pass
            raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_descriptor)


def _acquire_restructure_wave_lock_snapshot(
    root: Path,
    request_raw: Any,
    *,
    output_path: Path,
    head_sha: str,
    acquired_at: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    request = _wave_lock_request(copy.deepcopy(request_raw))
    now = acquired_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ArtifactError("acquired_at 必须带时区")
    if head_sha != request["expected_head_sha"]:
        raise ArtifactError("当前 HEAD 与冲突锁请求不一致")
    if not (
        _aware_datetime(request["starts_at"], "starts_at")
        <= now
        <= _aware_datetime(request["expires_at"], "expires_at")
    ):
        raise ArtifactError("冲突锁请求不在有效期")
    output = _wave_lock_output_path(root, output_path, request["scope"])
    receipt = {
        "contract_version": RESTRUCTURE_WAVE_LOCK_RECEIPT_V1,
        "status": "ACTIVE",
        "lock_id": request["lock_id"],
        "scope": request["scope"],
        "holder": request["holder"],
        "authorization_context_id": request["authorization_context_id"],
        "head_sha": head_sha,
        "starts_at": request["starts_at"],
        "acquired_at": now.isoformat(),
        "expires_at": request["expires_at"],
        "candidate_write_paths_sha256": _sha256_list(
            request["candidate_write_paths"]
        ),
        "authorization_boundary": {
            "authorizes_wave": False,
            "authorizes_notion_write": False,
            "authorizes_model_api": False,
        },
    }
    _write_json_exclusive(root, output, receipt)
    return receipt


def _receipt_output_path(root: Path, value: Path) -> Path:
    root = root.resolve()
    path = _repo_path_without_symlinks(
        root,
        value,
        name="重构机器票",
    )
    allowed_root = root / "TEMP/restructure_wave_preflight"
    if allowed_root != path and allowed_root not in path.parents:
        raise ArtifactError("重构机器票只能写入 TEMP/restructure_wave_preflight/")
    if path.exists():
        raise ArtifactError(f"拒绝覆盖既有重构机器票：{path}")
    return path


def _live_restructure_snapshot(root: Path) -> dict[str, Any]:
    return {
        "head_sha": git_head(root),
        "dirty_paths": git_dirty_paths(root),
        "governance_mismatch_paths": generated_mismatches(root),
    }


def _finish_live_snapshot_receipt(
    receipt: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    stable = before == after
    receipt["checks"].append(
        {
            "check_id": "live_snapshot_stable",
            "passed": stable,
            "evidence": {
                "before": before,
                "after": after,
            },
        }
    )
    receipt["status"] = (
        "PASS" if all(row["passed"] for row in receipt["checks"]) else "BLOCKED"
    )
    receipt["blockers"] = [
        row["check_id"] for row in receipt["checks"] if not row["passed"]
    ]
    if receipt.get("wave_id"):
        passed = receipt["status"] == "PASS"
        boundary = receipt["authorization_boundary"]
        boundary["authorizes_wave"] = False
        boundary["mechanical_preconditions_pass"] = passed
        boundary["eligible_wave_id"] = receipt["wave_id"] if passed else None
        if not passed:
            boundary["eligible_write_paths"] = []
    return receipt


def _verify_snapshot_after_receipt_write(
    root: Path,
    receipt: dict[str, Any],
    output: Path,
) -> None:
    snapshot_check = next(
        (
            row
            for row in receipt.get("checks", [])
            if isinstance(row, dict)
            and row.get("check_id") == "live_snapshot_stable"
        ),
        None,
    )
    expected = (
        snapshot_check.get("evidence", {}).get("after")
        if isinstance(snapshot_check, dict)
        and isinstance(snapshot_check.get("evidence"), dict)
        else None
    )
    actual = _live_restructure_snapshot(root)
    evidence_errors: list[str] = []
    evidence_snapshot = receipt.get("evidence_snapshot")
    if not isinstance(evidence_snapshot, list) or not evidence_snapshot:
        evidence_errors.append("缺少出票所用证据快照")
    else:
        seen_paths: set[str] = set()
        for index, row in enumerate(evidence_snapshot):
            if not isinstance(row, dict):
                evidence_errors.append(f"evidence_snapshot[{index}] 格式无效")
                continue
            path = row.get("path")
            expected_sha = row.get("sha256")
            if (
                not isinstance(path, str)
                or path in seen_paths
                or not isinstance(expected_sha, str)
            ):
                evidence_errors.append(f"evidence_snapshot[{index}] 字段无效")
                continue
            seen_paths.add(path)
            try:
                actual_sha = hashlib.sha256(
                    _read_repo_bytes_once(root, path)
                ).hexdigest()
            except (ArtifactError, OSError) as exc:
                evidence_errors.append(f"{path}: {exc}")
                continue
            if actual_sha != expected_sha:
                evidence_errors.append(f"{path}: SHA 已变化")
    if expected != actual or evidence_errors:
        removed = _safe_unlink_repo_file(root, output)
        result = "已撤销新票" if removed else "无法安全撤销新票"
        reason = (
            "现场快照发生变化"
            if expected != actual
            else "受绑定证据发生变化"
        )
        raise ArtifactError(f"机器票写入后{reason}，{result}")


def evaluate_restructure_baseline(
    root: Path,
    plan_raw: Any,
    *,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    before = _live_restructure_snapshot(root)
    receipt = _evaluate_restructure_baseline_snapshot(
        root,
        plan_raw,
        dirty_paths=before["dirty_paths"],
        head_sha=before["head_sha"],
        governance_mismatch_paths=before["governance_mismatch_paths"],
        evaluated_at=evaluated_at,
    )
    return _finish_live_snapshot_receipt(
        receipt,
        before,
        _live_restructure_snapshot(root),
    )


def evaluate_restructure_wave(
    root: Path,
    plan_raw: Any,
    *,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    before = _live_restructure_snapshot(root)
    receipt = _evaluate_restructure_wave_snapshot(
        root,
        plan_raw,
        dirty_paths=before["dirty_paths"],
        head_sha=before["head_sha"],
        governance_mismatch_paths=before["governance_mismatch_paths"],
        evaluated_at=evaluated_at,
    )
    return _finish_live_snapshot_receipt(
        receipt,
        before,
        _live_restructure_snapshot(root),
    )


def acquire_restructure_wave_lock(
    root: Path,
    request_raw: Any,
    *,
    output_path: Path,
    acquired_at: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    before = _live_restructure_snapshot(root)
    receipt = _acquire_restructure_wave_lock_snapshot(
        root,
        request_raw,
        output_path=output_path,
        head_sha=before["head_sha"],
        acquired_at=acquired_at,
    )
    after = _live_restructure_snapshot(root)
    if after != before:
        lock_path = (
            root
            / "TEMP/restructure_wave_preflight/locks"
            / f"{receipt['scope']}.lock.json"
        )
        removed = _safe_unlink_repo_file(root, lock_path)
        result = "已撤销新锁" if removed else "无法安全撤销新锁"
        raise ArtifactError(f"冲突锁创建期间现场发生变化，{result}")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成小说流水线治理索引")
    parser.add_argument("--check", action="store_true", help="在临时目录生成并与当前索引逐字比较")
    parser.add_argument("--baseline-plan", type=Path, help="读取第一级仓库重构基线校准计划")
    parser.add_argument("--baseline-output", type=Path, help="把机器校准票写入 TEMP 的新路径")
    parser.add_argument("--wave-plan", type=Path, help="读取第二级精确 Wave 开工计划")
    parser.add_argument("--wave-output", type=Path, help="把第二级 Wave 票写入 TEMP 的新路径")
    parser.add_argument("--wave-lock-request", type=Path, help="读取 Wave 冲突锁请求")
    parser.add_argument("--wave-lock-output", type=Path, help="原子创建固定 Wave 冲突锁")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pairs = (
        ("--baseline-plan", args.baseline_plan, "--baseline-output", args.baseline_output),
        ("--wave-plan", args.wave_plan, "--wave-output", args.wave_output),
        (
            "--wave-lock-request",
            args.wave_lock_request,
            "--wave-lock-output",
            args.wave_lock_output,
        ),
    )
    for left_name, left, right_name, right in pairs:
        if bool(left) != bool(right):
            raise ArtifactError(f"{left_name} 与 {right_name} 必须同时提供")
    selected_modes = sum(
        (
            bool(args.check),
            bool(args.baseline_plan),
            bool(args.wave_plan),
            bool(args.wave_lock_request),
        )
    )
    if selected_modes > 1:
        raise ArtifactError("治理检查、一级票、二级票和冲突锁模式不能同时使用")
    if args.baseline_plan:
        receipt = evaluate_restructure_baseline(
            ROOT,
            read_json(args.baseline_plan),
        )
        output = _receipt_output_path(ROOT, args.baseline_output)
        _write_json_exclusive(ROOT, output, receipt)
        _verify_snapshot_after_receipt_write(ROOT, receipt, output)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0 if receipt["status"] == "PASS" else 2
    if args.wave_lock_request:
        receipt = acquire_restructure_wave_lock(
            ROOT,
            read_json(args.wave_lock_request),
            output_path=args.wave_lock_output,
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    if args.wave_plan:
        receipt = evaluate_restructure_wave(
            ROOT,
            read_json(args.wave_plan),
        )
        output = _receipt_output_path(ROOT, args.wave_output)
        _write_json_exclusive(ROOT, output, receipt)
        _verify_snapshot_after_receipt_write(ROOT, receipt, output)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0 if receipt["status"] == "PASS" else 2
    if not args.check:
        manifest = refresh()
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    mismatches = generated_mismatches(ROOT)
    result = {"passed": not mismatches, "mismatches": mismatches}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
