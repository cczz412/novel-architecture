"""从机器真源生成治理索引，不改历史运行工件。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

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
DIRECTORY_REGISTRY_PATH = "governance/directory_registry.json"
DIRECTORY_REGISTRY_SCHEMA_PATH = (
    "governance/contracts/directory_registry_v1.schema.json"
)

GENERATED_PATHS = [
    "governance/INDEX.md",
    "governance/module_registry.json",
    "governance/dependency_map.json",
    "governance/indexes/gold_current.md",
    "governance/indexes/silver_candidates.md",
    "governance/indexes/runs_and_reports.md",
    "governance/indexes/source_registry.md",
    "governance/indexes/route_health.md",
    "governance/indexes/directory_map.md",
    "governance/indexes/new_file_routing.md",
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
RESTRUCTURE_WAVE_COMPLETION_REQUEST_V2 = (
    "repository-restructure-wave-completion-request-v2"
)
RESTRUCTURE_WAVE_COMPLETION_V2 = "repository-restructure-wave-completion-v2"
RESTRUCTURE_DECISION_TICKET_V1 = "repository-restructure-decision-ticket-v1"
RESTRUCTURE_WAVE2_PREPARATION_TICKET_V1 = (
    "repository-restructure-wave2-preparation-ticket-v1"
)
RESTRUCTURE_WAVE5_AUTHORIZATION_V1 = (
    "repository-restructure-wave5-authorization-v1"
)
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
WAVE2_PREPARATION_VALUES = {
    "W2-PREP-01": (
        "approved",
        "s02a_add_s0_completion_and_wave2_machine_gate_only",
    ),
    "W2-PREP-02": (
        "deferred",
        "wave2_construction_requires_later_same_task_positive_confirmation",
    ),
}
WAVE2_PREPARATION_SOURCE_TEXT = "a"
WAVE5_AUTHORIZATION_SOURCE_TEXT = "B｜机器闸和实际扫描器连续施工"
WAVE5_AUTHORIZATION_DECISION_VALUES = {
    "W5-01": (
        "approved",
        "machine_gate_then_read_only_scanner_in_same_task",
    ),
    "W5-02": (
        "approved",
        "three_fixed_legacy_manifests_only",
    ),
    "W5-03": (
        "approved",
        "all_148_entries_inventory_only",
    ),
    "W5-04": (
        "approved",
        "no_move_delete_stub_restore_pass_or_external_cleanup",
    ),
}
WAVE1_DIRECTORY_REGISTRY = "WAVE1_DIRECTORY_REGISTRY"
S0_MATERIALIZE_ONLY = "S0_MATERIALIZE_ONLY"
WAVE2_RULE_BUNDLES = "WAVE2_RULE_BUNDLES"
WAVE5_EXTERNAL_ARCHIVE_READONLY = "WAVE5_EXTERNAL_ARCHIVE_READONLY"
WAVE5_EXTERNAL_ROOT_ID = "repository_sibling_external_archive_v1"
WAVE5_EXTERNAL_MANIFESTS = (
    {
        "source_id": "legacy_archive_batch_20260723",
        "batch_relative_path": "archive_batch_20260723",
        "manifest_relative_path": "MANIFEST.json",
        "expected_entries": 51,
    },
    {
        "source_id": "legacy_archive_batch_slim_20260723",
        "batch_relative_path": "archive_batch_slim_20260723",
        "manifest_relative_path": "MANIFEST.json",
        "expected_entries": 91,
    },
    {
        "source_id": "legacy_archive_batch_slim_overlay_z94_20260723",
        "batch_relative_path": "archive_batch_slim_overlay_z94_20260723",
        "manifest_relative_path": "MANIFEST.json",
        "expected_entries": 6,
    },
)
WAVE5_MAX_MANIFEST_BYTES = 5 * 1024 * 1024
WAVE2_PILOT_PROFILE_ID = (
    "qianwen_qwen3_7_flash_json_object_no_thinking"
)
WAVE2_PILOT_ARTIFACT_ID = "wave2_synthetic_json_probe_v1"
WAVE2_CANDIDATE_WRITE_PATHS = [
    "config/model_call_profiles/contracts/README.md",
    "config/model_call_profiles/contracts/contract_bundle.schema.json",
    "config/model_call_profiles/contracts/"
    f"{WAVE2_PILOT_PROFILE_ID}/bundle.json",
    "config/model_call_profiles/contracts/"
    f"{WAVE2_PILOT_PROFILE_ID}/request_envelope.schema.json",
    "config/model_call_profiles/contracts/"
    f"{WAVE2_PILOT_PROFILE_ID}/response_envelope.schema.json",
    "config/model_call_profiles/contracts/"
    f"{WAVE2_PILOT_PROFILE_ID}/normalization.json",
    "config/prompts/README.md",
    "config/prompts/prompt_manifest.schema.json",
    f"config/prompts/{WAVE2_PILOT_ARTIFACT_ID}/prompt.md",
    f"config/prompts/{WAVE2_PILOT_ARTIFACT_ID}/manifest.json",
    "config/context_recipes/README.md",
    "config/context_recipes/context_recipe.schema.json",
    f"config/context_recipes/{WAVE2_PILOT_ARTIFACT_ID}.json",
    f"config/contracts/{WAVE2_PILOT_ARTIFACT_ID}.schema.json",
    "config/model_call_profiles/registry.json",
    "config/model_call_profiles/README.md",
    "config/README.md",
    "tools/model_call_profiles.py",
    "tests/test_model_call_profiles.py",
    "tools/README.md",
    "tests/README.md",
    "governance/tool_registry.json",
]
WAVE2_REQUIRED_INPUTS = {
    ".gitignore",
    "AGENTS.md",
    CURRENT_STATE_PATH,
    CONTROL_PATH,
    "config/model_call_profiles/profile.schema.json",
    "config/model_call_profiles/registry.json",
    "config/model_call_profiles/README.md",
    "config/model_call_profiles/profiles/"
    f"{WAVE2_PILOT_PROFILE_ID}.json",
    "config/providers/provider_access_policy.json",
    "config/providers/qianwen_platform_multi_model.json",
    "config/README.md",
    "governance/directory_registry.json",
    "governance/index_manifest.json",
    "governance/module_registry.json",
    "governance/test_policy.json",
    "governance/tool_registry.json",
    "tools/model_call_profiles.py",
    "tools/governance_index.py",
    "tools/README.md",
    "tests/test_model_call_profiles.py",
    "tests/test_governance_index.py",
    "tests/README.md",
    "TEMP/restructure_wave_preflight/"
    "route-a-plus-s0-20260730/"
    "S0_DECISION_TICKET_20260730.json",
}
WAVE2_REQUIRED_READ_SCOPES = sorted(
    {
        ".gitignore",
        "AGENTS.md",
        "TEMP/restructure_wave_preflight",
        *WAVE2_REQUIRED_INPUTS,
        *WAVE2_CANDIDATE_WRITE_PATHS,
    }
)
WAVE2_READ_DIRECTORY_SCOPES = {
    "TEMP/restructure_wave_preflight",
}
WAVE2_REQUIRED_REFERENCE_PATHS = {
    "baseline_plan": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave2-20260730/"
        "BASELINE_PLAN_WAVE2_20260730.json"
    ),
    "baseline_receipt": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave2-20260730/"
        "BASELINE_RECEIPT_WAVE2_20260730.json"
    ),
    "decision_ticket": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave2-20260730/"
        "WAVE2_PREPARATION_TICKET_20260730.json"
    ),
    "conflict_lock": (
        "TEMP/restructure_wave_preflight/locks/"
        "WAVE2_RULE_BUNDLES.lock.json"
    ),
    "test_impact": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave2-20260730/"
        "WAVE2_TEST_IMPACT_20260730.json"
    ),
    "dependency": {
        "path": (
            "TEMP/restructure_wave_preflight/"
            "route-a-plus-s0-20260730/"
            "S0_MATERIALIZE_COMPLETION_V2_20260730.json"
        ),
        "wave_id": S0_MATERIALIZE_ONLY,
    },
}
WAVE5_CANDIDATE_WRITE_PATHS = [
    "config/external_storage/README.md",
    "config/external_storage/legacy_manifests.json",
    "config/external_storage/legacy_manifest_scan_receipt_v1.schema.json",
    "governance/contracts/external_archive_registry_v1.schema.json",
    "governance/external_archive_registry.json",
    "tools/external_archive.py",
    "tests/test_external_archive.py",
    "config/README.md",
    "tools/README.md",
    "tests/README.md",
    "governance/README.md",
    "governance/directory_registry.json",
    "governance/indexes/directory_map.md",
    "governance/indexes/new_file_routing.md",
    "governance/tool_registry.json",
    "governance/test_policy.json",
    "governance/index_manifest.json",
]
WAVE5_REQUIRED_INPUTS = {
    ".gitignore",
    "AGENTS.md",
    CURRENT_STATE_PATH,
    CONTROL_PATH,
    "config/README.md",
    "governance/README.md",
    "governance/directory_registry.json",
    "governance/index_manifest.json",
    "governance/module_registry.json",
    "governance/test_policy.json",
    "governance/tool_registry.json",
    "tests/test_governance_index.py",
    "tests/README.md",
    "tools/governance_index.py",
    "tools/README.md",
    (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-s0-20260730/"
        "S0_DECISION_TICKET_20260730.json"
    ),
}
WAVE5_REQUIRED_READ_SCOPES = sorted(
    {
        "TEMP/restructure_wave_preflight",
        *WAVE5_REQUIRED_INPUTS,
        *WAVE5_CANDIDATE_WRITE_PATHS,
    }
)
WAVE5_READ_DIRECTORY_SCOPES = {
    "TEMP/restructure_wave_preflight",
}
WAVE5_REQUIRED_REFERENCE_PATHS = {
    "baseline_plan": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave5-20260730/"
        "BASELINE_PLAN_WAVE5_20260730.json"
    ),
    "baseline_receipt": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave5-20260730/"
        "BASELINE_RECEIPT_WAVE5_20260730.json"
    ),
    "decision_ticket": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave5-20260730/"
        "WAVE5_CONSTRUCTION_AUTHORIZATION_20260730.json"
    ),
    "conflict_lock": (
        "TEMP/restructure_wave_preflight/locks/"
        "WAVE5_EXTERNAL_ARCHIVE_READONLY.lock.json"
    ),
    "test_impact": (
        "TEMP/restructure_wave_preflight/"
        "route-a-plus-wave5-20260730/"
        "WAVE5_TEST_IMPACT_20260730.json"
    ),
}
RESTRUCTURE_WAVE_SPECS = {
    WAVE1_DIRECTORY_REGISTRY: {
        "route": "S0",
        "candidate_write_paths": [
            "governance/directory_registry.json",
            "governance/contracts/directory_registry_v1.schema.json",
            "governance/indexes/directory_map.md",
            "governance/indexes/new_file_routing.md",
            "tests/test_repository_layout.py",
            "governance/README.md",
            "governance/index_manifest.json",
            "governance/module_registry.json",
            "governance/test_policy.json",
            "tools/governance_index.py",
            "tests/test_governance_index.py",
        ],
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
            "root_refresh": False,
        },
        "required_read_scopes": sorted(RESTRUCTURE_WAVE_FIXED_READ_SCOPES),
        "required_completion_wave_ids": [],
    },
    S0_MATERIALIZE_ONLY: {
        "route": "S0",
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
        "required_read_scopes": sorted(RESTRUCTURE_WAVE_FIXED_READ_SCOPES),
        "required_completion_wave_ids": [WAVE1_DIRECTORY_REGISTRY],
    },
    WAVE2_RULE_BUNDLES: {
        "route": "A_PLUS",
        "candidate_write_paths": WAVE2_CANDIDATE_WRITE_PATHS,
        "required_inputs": WAVE2_REQUIRED_INPUTS,
        "capability_limits": {
            "rule_bundle_only": True,
            "offline_resolve_only": True,
            "physical_move": False,
            "delete_source": False,
            "preflight": False,
            "network": False,
            "credential_read": False,
            "request_send": False,
            "model_api": False,
            "notion_write": False,
            "external_removal": False,
        },
        "required_read_scopes": WAVE2_REQUIRED_READ_SCOPES,
        "required_completion_wave_ids": [S0_MATERIALIZE_ONLY],
        "required_reference_paths": WAVE2_REQUIRED_REFERENCE_PATHS,
        "required_completion_source": {
            "wave_plan": {
                "path": (
                    "TEMP/restructure_wave_preflight/"
                    "route-a-plus-s0-20260730/"
                    "S0_MATERIALIZE_PLAN_20260730.json"
                ),
                "sha256": (
                    "2ed17afdbe3ee655638fc29f7f6272f8"
                    "b32bd5e08a2880e576dad7faca11e7c0"
                ),
            },
            "wave_receipt": {
                "path": (
                    "TEMP/restructure_wave_preflight/"
                    "route-a-plus-s0-20260730/"
                    "S0_MATERIALIZE_MECHANICAL_RECEIPT_20260730.json"
                ),
                "sha256": (
                    "a7c4cb30a3502fd020dcd290f303238b"
                    "5ad5c66af8261080cadf92d9e9054b60"
                ),
            },
            "pre_commit_sha": "c7ad18e734a9c6c2a5cbf03508903ec3f9db7c47",
            "post_commit_sha": "22746e67541cfcdbc7874720c127c91c4b6ab150",
        },
        "required_prior_decision_ticket": {
            "path": (
                "TEMP/restructure_wave_preflight/"
                "route-a-plus-s0-20260730/"
                "S0_DECISION_TICKET_20260730.json"
            ),
            "sha256": (
                "cc594657d6603a9280678b30ea377cf85"
                "a46b6b89b8fc2ac23df65fdf1fa2bf0"
            ),
        },
    },
    WAVE5_EXTERNAL_ARCHIVE_READONLY: {
        "route": "A_PLUS_EXTERNAL_READONLY",
        "candidate_write_paths": WAVE5_CANDIDATE_WRITE_PATHS,
        "required_inputs": WAVE5_REQUIRED_INPUTS,
        "capability_limits": {
            "legacy_manifest_read_only": True,
            "offline_scan_only": True,
            "receipt_create_only": True,
            "registry_create_only": True,
            "manifest_rewrite": False,
            "external_content_traversal": False,
            "physical_move": False,
            "delete_source": False,
            "write_stub": False,
            "restore_verification": False,
            "cryptographic_restorability_claim": False,
            "preflight": False,
            "network": False,
            "credential_read": False,
            "request_send": False,
            "model_api": False,
            "notion_write": False,
            "external_removal": False,
            "root_refresh": False,
        },
        "required_read_scopes": WAVE5_REQUIRED_READ_SCOPES,
        "required_completion_wave_ids": [],
        "required_reference_paths": WAVE5_REQUIRED_REFERENCE_PATHS,
        "required_prior_decision_ticket": {
            "path": (
                "TEMP/restructure_wave_preflight/"
                "route-a-plus-s0-20260730/"
                "S0_DECISION_TICKET_20260730.json"
            ),
            "sha256": (
                "cc594657d6603a9280678b30ea377cf85"
                "a46b6b89b8fc2ac23df65fdf1fa2bf0"
            ),
        },
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


def _reject_unsafe_text(value: Any, name: str) -> None:
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ArtifactError(f"{name} 含无法写成 UTF-8 的字符") from exc
        if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
            raise ArtifactError(f"{name} 含控制字符")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_unsafe_text(item, f"{name}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_unsafe_text(key, f"{name}.key")
            _reject_unsafe_text(item, f"{name}.{key}")


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


def _wave_read_path_is_allowed(
    wave_id: str,
    path: str,
    allowed: str,
) -> bool:
    if (
        wave_id in {
            WAVE2_RULE_BUNDLES,
            WAVE5_EXTERNAL_ARCHIVE_READONLY,
        }
        and allowed
        not in (
            WAVE2_READ_DIRECTORY_SCOPES
            if wave_id == WAVE2_RULE_BUNDLES
            else WAVE5_READ_DIRECTORY_SCOPES
        )
    ):
        return path == allowed
    return _path_is_allowed(path, allowed)


def _wave_candidate_write_path_is_allowed(
    wave_id: str,
    path: str,
    allowed: str,
) -> bool:
    if wave_id in {
        WAVE2_RULE_BUNDLES,
        WAVE5_EXTERNAL_ARCHIVE_READONLY,
    }:
        return path == allowed
    return _path_is_allowed(path, allowed)


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
        opened_stat = os.fstat(descriptor)
        if opened_stat.st_nlink != 1:
            raise ArtifactError(
                f"受绑定输入不得通过硬链接读取：{relative_path}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        opened_stat = os.fstat(descriptor)
        if opened_stat.st_nlink != 1:
            raise ArtifactError(
                f"受绑定输入读取期间变成硬链接：{relative_path}"
            )
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


def _wave5_external_root(root: Path) -> Path:
    root = root.resolve()
    return root.parent / f"{root.name}_外置仓"


def _wave5_external_identity(batch_relative_path: str) -> str:
    return (
        f"external://{WAVE5_EXTERNAL_ROOT_ID}/"
        f"{batch_relative_path}/MANIFEST.json"
    )


def _read_wave5_external_manifest_once(
    root: Path,
    batch_relative_path: str,
) -> bytes:
    allowed_batches = {
        row["batch_relative_path"] for row in WAVE5_EXTERNAL_MANIFESTS
    }
    if batch_relative_path not in allowed_batches:
        raise ArtifactError("Wave5 只能读取登记过的三份旧 MANIFEST")

    root = root.resolve()
    external_root = _wave5_external_root(root)
    if external_root.is_symlink():
        raise ArtifactError("Wave5 外置仓根不得是软链")
    try:
        root_stat = os.stat(external_root, follow_symlinks=False)
    except OSError as exc:
        raise ArtifactError(f"Wave5 外置仓根不可读：{exc}") from exc
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ArtifactError("Wave5 外置仓根不是目录")
    visible_batch = external_root / batch_relative_path
    if visible_batch.is_symlink():
        raise ArtifactError("Wave5 旧批次目录不得是软链")
    try:
        visible_batch_before = os.stat(
            visible_batch,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise ArtifactError(f"Wave5 旧批次目录不可读：{exc}") from exc
    if not stat.S_ISDIR(visible_batch_before.st_mode):
        raise ArtifactError("Wave5 旧批次路径不是目录")

    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    file_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        file_flags |= os.O_NOFOLLOW

    root_descriptor: int | None = None
    batch_descriptor: int | None = None
    file_descriptor: int | None = None
    try:
        root_descriptor = os.open(external_root, directory_flags)
        batch_descriptor = os.open(
            batch_relative_path,
            directory_flags,
            dir_fd=root_descriptor,
        )
        file_descriptor = os.open(
            "MANIFEST.json",
            file_flags,
            dir_fd=batch_descriptor,
        )
        opened = os.fstat(file_descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ArtifactError("Wave5 旧 MANIFEST 必须是普通文件")
        if opened.st_nlink != 1:
            raise ArtifactError("Wave5 旧 MANIFEST 不得是硬链接")
        if opened.st_size > WAVE5_MAX_MANIFEST_BYTES:
            raise ArtifactError("Wave5 旧 MANIFEST 超过安全大小上限")

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > WAVE5_MAX_MANIFEST_BYTES:
                raise ArtifactError("Wave5 旧 MANIFEST 读取时超过安全大小上限")
            chunks.append(chunk)

        closed_view = os.fstat(file_descriptor)
        signature = (
            opened.st_dev,
            opened.st_ino,
            opened.st_mode,
            opened.st_nlink,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        closed_signature = (
            closed_view.st_dev,
            closed_view.st_ino,
            closed_view.st_mode,
            closed_view.st_nlink,
            closed_view.st_size,
            closed_view.st_mtime_ns,
            closed_view.st_ctime_ns,
        )
        if signature != closed_signature:
            raise ArtifactError("Wave5 旧 MANIFEST 在读取期间发生变化")

        if visible_batch.is_symlink():
            raise ArtifactError("Wave5 旧批次目录不得是软链")
        visible_batch_stat = os.stat(
            visible_batch,
            follow_symlinks=False,
        )
        opened_batch_stat = os.fstat(batch_descriptor)
        if (
            visible_batch_stat.st_dev,
            visible_batch_stat.st_ino,
        ) != (
            opened_batch_stat.st_dev,
            opened_batch_stat.st_ino,
        ):
            raise ArtifactError("Wave5 旧批次目录在读取期间被替换")

        visible_manifest = visible_batch / "MANIFEST.json"
        if visible_manifest.is_symlink():
            raise ArtifactError("Wave5 旧 MANIFEST 不得是软链")
        visible = os.stat(visible_manifest, follow_symlinks=False)
        if (
            visible.st_dev,
            visible.st_ino,
            visible.st_mode,
            visible.st_nlink,
            visible.st_size,
            visible.st_mtime_ns,
            visible.st_ctime_ns,
        ) != closed_signature:
            raise ArtifactError("Wave5 旧 MANIFEST 在读取期间被替换")
        return b"".join(chunks)
    except OSError as exc:
        raise ArtifactError(f"Wave5 旧 MANIFEST 安全读取失败：{exc}") from exc
    finally:
        for descriptor in (
            file_descriptor,
            batch_descriptor,
            root_descriptor,
        ):
            if descriptor is not None:
                os.close(descriptor)


def _wave5_external_snapshot(
    root: Path,
    sources: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for source in sources:
        batch = source["batch_relative_path"]
        identity = _wave5_external_identity(batch)
        try:
            raw = _read_wave5_external_manifest_once(root, batch)
            actual_sha = hashlib.sha256(raw).hexdigest()
            payload = _must_dict(
                json.loads(raw.decode("utf-8")),
                identity,
            )
            entries = _must_list(payload.get("entries"), f"{identity}.entries")
            actual_entries = len(entries)
            matched = (
                actual_sha == source["expected_sha256"]
                and actual_entries == source["expected_entries"]
            )
            error = None
            if not matched:
                errors.append(f"{identity} 的 SHA 或条目数不匹配")
        except (
            ArtifactError,
            OSError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            actual_sha = None
            actual_entries = None
            matched = False
            error = str(exc)
            errors.append(f"{identity}: {exc}")
        rows.append(
            {
                "kind": "wave5_fixed_sibling_manifest",
                "path": identity,
                "batch_relative_path": batch,
                "expected_sha256": source["expected_sha256"],
                "actual_sha256": actual_sha,
                "expected_entries": source["expected_entries"],
                "actual_entries": actual_entries,
                "matched": matched,
                "error": error,
            }
        )
    return not errors, rows, errors


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


def git_name_status_between_exact(
    root: Path,
    older_sha: str,
    newer_sha: str,
) -> list[dict[str, str]]:
    completed = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "-z",
            "--find-renames=1%",
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
    changes: list[dict[str, str]] = []
    index = 0
    while index < len(chunks):
        status = chunks[index]
        index += 1
        if status.startswith(("R", "C")):
            if index + 1 >= len(chunks):
                raise ArtifactError("无法解析带改名的 Wave Git 变更清单")
            changes.append(
                {
                    "status": status,
                    "old_path": chunks[index],
                    "path": chunks[index + 1],
                }
            )
            index += 2
            continue
        if index >= len(chunks):
            raise ArtifactError("无法解析 Wave Git 变更清单")
        changes.append({"status": status, "path": chunks[index]})
        index += 1
    return changes


def git_commit_exists(root: Path, commit_sha: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode not in {0, 1, 128}:
        raise ArtifactError(
            "无法核对 Git 提交对象："
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.returncode == 0


def git_blob_evidence(
    root: Path,
    commit_sha: str,
    relative_path: str,
) -> dict[str, Any]:
    path = _repo_relative_path(relative_path, "Git blob path")
    tree = subprocess.run(
        ["git", "ls-tree", "-z", commit_sha, "--", path],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows = [row for row in tree.stdout.split(b"\0") if row]
    if len(rows) != 1:
        raise ArtifactError(f"完成提交里找不到唯一文件 blob：{path}")
    try:
        metadata, actual_path = rows[0].split(b"\t", 1)
        mode, object_type, object_sha = metadata.decode("ascii").split(" ", 2)
        decoded_path = actual_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ArtifactError(f"无法解析完成提交文件 blob：{path}") from exc
    if (
        decoded_path != path
        or object_type != "blob"
        or mode == "120000"
        or not re.fullmatch(r"[0-9a-f]{40,64}", object_sha)
    ):
        raise ArtifactError(f"完成提交对象不是普通文件 blob：{path}")
    blob = subprocess.run(
        ["git", "cat-file", "blob", object_sha],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    return {
        "path": path,
        "git_mode": mode,
        "git_blob_sha": object_sha,
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


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


def validate_directory_registry(root: Path, registry: dict[str, Any]) -> None:
    _reject_unsafe_text(registry, "directory_registry")
    schema = _must_dict(
        read_json(root / DIRECTORY_REGISTRY_SCHEMA_PATH),
        "directory_registry_schema",
    )
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(registry)
    except (SchemaError, ValidationError) as exc:
        raise ArtifactError(f"目录登记不符合正式 schema：{exc.message}") from exc
    if registry.get("schema_version") != "directory-registry-v1":
        raise ArtifactError("目录登记 schema_version 必须是 directory-registry-v1")
    if registry.get("inherit_to_children_default") is not False:
        raise ArtifactError("目录身份默认不得递归覆盖子对象")
    authority = _must_dict(registry.get("authority"), "directory_registry.authority")
    if authority != {
        "scope": "container_identity_only",
        "may_define_current_task": False,
        "may_override_object_registries": False,
        "conflict_rule": "higher_precedence_registry_wins",
    }:
        raise ArtifactError("目录登记权限必须只限容器身份")
    expected_precedence = [
        CURRENT_STATE_PATH,
        "governance/module_registry.json",
        "governance/tool_registry.json",
        ROUTE_REGISTRY_PATH,
        "governance/external_archive_registry.json",
        DIRECTORY_REGISTRY_PATH,
    ]
    if registry.get("identity_precedence") != expected_precedence:
        raise ArtifactError("目录身份优先级漂移")

    rows = _must_list(registry.get("directories"), "directory_registry.directories")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_identities: set[str] = set()
    seen_objects: set[str] = set()
    forbidden_state_keys = {
        "current_task",
        "current_run",
        "next_action",
        "business_status",
        "business_conclusion",
    }
    allowed_git_policies = {
        "tracked",
        "ignored",
        "mixed",
        "local_untracked",
        "tracked_pointer",
    }
    for index, raw in enumerate(rows):
        row = _must_dict(raw, f"directory_registry.directories[{index}]")
        leaked = sorted(forbidden_state_keys & set(row))
        if leaked:
            raise ArtifactError(f"目录登记不得保存当前业务状态字段：{leaked}")
        directory_id = _must_nonempty_string(
            row.get("directory_id"),
            f"directories[{index}].directory_id",
        )
        path = _repo_relative_path(row.get("path"), f"directories[{index}].path")
        identity = _must_nonempty_string(
            row.get("identity"),
            f"directories[{index}].identity",
        )
        if len(PurePosixPath(path).parts) != 1:
            raise ArtifactError(f"Wave 1 只登记仓库顶层目录：{path}")
        if directory_id in seen_ids:
            raise ArtifactError(f"目录编号重复：{directory_id}")
        if path in seen_paths:
            raise ArtifactError(f"目录路径重复：{path}")
        if identity in seen_identities:
            raise ArtifactError(f"目录身份重复：{identity}")
        seen_ids.add(directory_id)
        seen_paths.add(path)
        seen_identities.add(identity)

        if row.get("inherit_to_children") is not False:
            raise ArtifactError(f"目录身份不得递归覆盖子对象：{path}")
        path_kind = row.get("path_kind")
        if path_kind not in {"directory", "symlink"}:
            raise ArtifactError(f"目录路径类型非法：{path}")
        candidate = root / Path(*PurePosixPath(path).parts)
        if candidate.is_symlink() and path_kind != "symlink":
            raise ArtifactError(f"软链目录必须明确登记：{path}")
        if candidate.exists() and not candidate.is_symlink() and not candidate.is_dir():
            raise ArtifactError(f"登记路径不是目录：{path}")
        if row.get("git_policy") not in allowed_git_policies:
            raise ArtifactError(f"目录 Git 规则非法：{path}")
        if row.get("git_policy") == "mixed":
            ignored_probe = _repo_relative_path(
                row.get("ignored_probe"),
                f"{path}.ignored_probe",
            )
            if PurePosixPath(ignored_probe).parts[0] != path:
                raise ArtifactError(f"Git 忽略探针越出登记目录：{path}")
        elif "ignored_probe" in row:
            raise ArtifactError(f"非 mixed 目录不得登记忽略探针：{path}")
        if path == "analysis_library" and row.get("git_policy") == "ignored":
            raise ArtifactError("analysis_library 当前未被 .gitignore 忽略，不得写成 ignored")

        _must_list(row.get("consumers"), f"{path}.consumers")
        _must_nonempty_string(row.get("new_content_rule"), f"{path}.new_content_rule")
        _must_list(row.get("open_decisions"), f"{path}.open_decisions")
        evidence_refs = _must_list(row.get("evidence_refs"), f"{path}.evidence_refs")
        if not evidence_refs:
            raise ArtifactError(f"目录登记缺证据引用：{path}")
        for ref in evidence_refs:
            relative = _repo_relative_path(ref, f"{path}.evidence_ref")
            if not (root / Path(*PurePosixPath(relative).parts)).exists():
                raise ArtifactError(f"目录证据不存在：{path}：{relative}")

        accepted = _must_list(row.get("accepted_content"), f"{path}.accepted_content")
        for accepted_index, raw_content in enumerate(accepted):
            content = _must_dict(
                raw_content,
                f"{path}.accepted_content[{accepted_index}]",
            )
            object_id = _must_nonempty_string(
                content.get("object_id"),
                f"{path}.accepted_content[{accepted_index}].object_id",
            )
            if object_id in seen_objects:
                raise ArtifactError(f"新文件对象身份重复：{object_id}")
            seen_objects.add(object_id)
            target = _repo_relative_path(
                content.get("target_pattern"),
                f"{path}.accepted_content[{accepted_index}].target_pattern",
            )
            if PurePosixPath(target).parts[0] != path:
                raise ArtifactError(f"新文件落点越出登记目录：{object_id}：{target}")
            _must_nonempty_string(content.get("label"), f"{object_id}.label")
            _must_nonempty_string(content.get("rule"), f"{object_id}.rule")


def render_directory_map(registry: dict[str, Any]) -> str:
    lines = [
        "# 仓库目录身份图",
        "",
        "这张表只解释容器身份，不解释当前任务。子对象身份冲突时，按登记表里的优先级让位。",
        "",
        "| 目录 | 主要身份 | 类别 | 权限 | 读取规则 | 生命周期 | Git 规则 | 新内容规则 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in registry["directories"]:
        lines.append(
            f"| `{row['path']}` | `{row['identity']}` | `{row['category']}` | "
            f"`{row['container_authority']}` | `{row['load_policy']}` | "
            f"`{row['lifecycle']}` | `{row['git_policy']}` | {row['new_content_rule']} |"
        )
    git_semantics = registry["git_policy_semantics"]
    lines.extend(
        [
            "",
            "Git 规则口径："
            f"`tracked`＝{git_semantics['tracked']}；"
            f"`ignored`＝{git_semantics['ignored']}；"
            f"`mixed`＝{git_semantics['mixed']}；"
            f"`local_untracked`＝{git_semantics['local_untracked']}；"
            f"`tracked_pointer`＝{git_semantics['tracked_pointer']}。",
            "",
            "默认规则：目录身份不递归覆盖子对象；当前状态、模块、工具、路线和外置对象登记的权限都高于本表。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def render_new_file_routing(registry: dict[str, Any]) -> str:
    lines = [
        "# 新文件放哪里",
        "",
        "这张表从目录身份账生成。找不到合适落点时先放 `work/<id>`，不要临时发明新的顶层目录。",
        "",
        "| 要放的对象 | 目标位置 | 准入规则 | 容器身份 |",
        "|---|---|---|---|",
    ]
    for row in registry["directories"]:
        for content in row["accepted_content"]:
            lines.append(
                f"| {content['label']} | `{content['target_pattern']}` | "
                f"{content['rule']} | `{row['identity']}` |"
            )
    lines.extend(
        [
            "",
            "本表不授权移动旧文件，也不授权创建 `active/`、`staging/`、`frozen/`、`runtime/` 顶层目录。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


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
    directory_registry: dict[str, Any],
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
    status_counts = registry["status_counts"]
    route_counts = {
        status: sum(1 for row in route_registry["routes"] if row["status"] == status)
        for status in ROUTE_STATUS_VALUES
    }
    index = f"""# 小说流水线治理索引

> 本页由 `tools/governance_index.py` 从仓库登记册生成，只负责稳定寻路，不保存整体任务进度。主线、支线、领票、依赖和阻塞现场读取 Linear；工程 Issue、PR、检查和合并现场读取 GitHub。`CURRENT_STATE.json` 只是带日期的技术兼容／控制快照。

## 去哪里看

| 要看什么 | 入口 | 边界 |
|---|---|---|
| 整体任务、主支线、领票、父子、硬前置、阻塞、并行线 | [Linear 项目](https://linear.app/ccz/project/novel-architecture-e0f2a433c335)，推荐 `$linear-github-task-map` | 必须现场读取，不从仓库静态页复原 |
| 工程施工、PR、检查、合并 | [GitHub](https://github.com/cczz412/novel-architecture) | GitHub 是工程线真值 |
| 上工规矩 | [START_HERE](START_HERE.md)、[Agent 必读：建票、拆票与依赖规则](agent_ticket_rules.md)与[三边协作约定](COLLAB_GITHUB_LINEAR_SLACK.md) | CZ 最新明确指令仍优先 |
| 版本、路径、候选身份 | [current pointers](current_pointers.json) | 不保存领票、依赖或运行成绩 |
| 技术兼容／控制字段 | [CURRENT_STATE](CURRENT_STATE.json) | 带日期快照，不是全局任务地图 |
| 金标入口 | 正式金标共 {len(formal_gold_entries)} 个入口：X01 第3章 **{gold['version']}**＋五本 v1.3；统一登记 `{formal_registry_control['path']}` | 只认正式登记，不从文件名猜 |
| 模块登记 | 可用 {status_counts['可用']} 个版本／在改 {status_counts['在改']} 个版本／试验 {status_counts['试验']} 个版本；见 [模块状态登记](module_registry.json) | 模块登记不是施工票 |
| 实验路线登记 | 在试 {route_counts['in_trial']} 条／失败 {route_counts['failed']} 条／退役 {route_counts['retired']} 条／允许重开 {route_counts['allowed_to_reopen']} 条；见 [路线状态登记](route_registry.json) | 路线身份不等于当前开工 |

## 当前正式入口

- 默认链：`{default['path']}`，版本 `{default['version']}`。
- 旧运行入口：`tools/zbatch.py`，继续保留。
- 新统一薄入口：`tools/novel_pipeline.py`；现役命令原样转发给旧入口，不复制运行逻辑。
- 密钥加载入口：只用 `tools/sensenova_deepseek_key.sh`；共享环境和外部项目加载器已退役。
- 试验专区：`experiments/`；旧试验原件不搬，新试验从这里起。

## 快速入口

- [Agent 必读：建票、拆票与依赖规则](agent_ticket_rules.md)
- [技术兼容／控制快照](CURRENT_STATE.json)
- [当前版本、路径和候选身份](current_pointers.json)
- [实验路线状态](route_registry.json)
- [正式金标](indexes/gold_current.md)
- [银标候选](indexes/silver_candidates.md)
- [运行与回包](indexes/runs_and_reports.md)
- [材料与参考](indexes/source_registry.md)
- [旧路牌健康检查](indexes/route_health.md)
- [模块依赖图](dependency_map.json)
- [合同说明](contracts/README.md)
- [试验专区](../experiments/INDEX.md)

来源：Codex
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
        "governance/indexes/gold_current.md": gold_page,
        "governance/indexes/silver_candidates.md": "\n".join(silver_lines),
        "governance/indexes/runs_and_reports.md": "\n".join(runs_lines),
        "governance/indexes/source_registry.md": "\n".join(source_lines),
        "governance/indexes/route_health.md": route_page,
        "governance/indexes/directory_map.md": render_directory_map(
            directory_registry
        ),
        "governance/indexes/new_file_routing.md": render_new_file_routing(
            directory_registry
        ),
        "experiments/INDEX.md": render_experiments_index(root),
    }


def refresh(root: Path = ROOT, output_root: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    destination = (output_root or root).resolve()
    control = _must_dict(read_json(root / CONTROL_PATH), "control_plane")
    current_state = _must_dict(read_json(root / CURRENT_STATE_PATH), "CURRENT_STATE")
    route_registry = _must_dict(read_json(root / ROUTE_REGISTRY_PATH), "route_registry")
    registry_source = _must_dict(read_json(root / REGISTRY_SOURCE_PATH), "module_registry.source")
    directory_registry = _must_dict(
        read_json(root / DIRECTORY_REGISTRY_PATH),
        "directory_registry",
    )
    validate_control_plane(root, control)
    validate_current_state(root, current_state)
    validate_route_registry(root, route_registry, current_state)
    validate_directory_registry(root, directory_registry)
    registry = materialize_registry(root, registry_source)
    documents = build_documents(
        root,
        control,
        current_state,
        route_registry,
        registry,
        directory_registry,
    )

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
            [
                CONTROL_PATH,
                CURRENT_STATE_PATH,
                ROUTE_REGISTRY_PATH,
                REGISTRY_SOURCE_PATH,
                DIRECTORY_REGISTRY_PATH,
                DIRECTORY_REGISTRY_SCHEMA_PATH,
            ],
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
    expected_read_scopes = sorted(RESTRUCTURE_BASELINE_FIXED_READ_SCOPES)
    if window["read_allowlist"] != expected_read_scopes:
        raise ArtifactError("一级计划 read_allowlist 必须与固定读取范围完全相等")
    reads_outside = sorted(
        row["path"]
        for row in normalized_bindings
        if not any(
            _path_is_allowed(row["path"], allowed)
            for allowed in expected_read_scopes
        )
    )
    if reads_outside:
        raise ArtifactError(
            "一级计划绑定输入超出许可范围，拒绝在读文件后再补判："
            f"{reads_outside}"
        )
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
    wave_id = _must_nonempty_string(plan.get("wave_id"), "wave_id")
    if wave_id not in RESTRUCTURE_WAVE_SPECS:
        raise ArtifactError(f"不支持的 Wave：{wave_id}")
    expected_route = RESTRUCTURE_WAVE_SPECS[wave_id]["route"]
    if plan.get("route") != expected_route:
        raise ArtifactError(
            f"第二级 Wave 计划 route 必须是 {expected_route}"
        )
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
    expected_limit_keys = set(
        RESTRUCTURE_WAVE_SPECS[wave_id]["capability_limits"]
    )
    if set(limits) != expected_limit_keys:
        unknown = sorted(set(limits) - expected_limit_keys)
        missing = sorted(expected_limit_keys - set(limits))
        raise ArtifactError(
            "capability_limits 字段必须与当前 Wave 完全相等；"
            f"多余={unknown}，缺少={missing}"
        )
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

    if wave_id in {
        WAVE2_RULE_BUNDLES,
        WAVE5_EXTERNAL_ARCHIVE_READONLY,
    }:
        required_references = RESTRUCTURE_WAVE_SPECS[wave_id][
            "required_reference_paths"
        ]
        reference_errors = {
            reference_name: {
                "expected": required_references[reference_name],
                "actual": plan[reference_name]["path"],
            }
            for reference_name in (
                "baseline_plan",
                "baseline_receipt",
                "decision_ticket",
                "conflict_lock",
                "test_impact",
            )
            if plan[reference_name]["path"]
            != required_references[reference_name]
        }
        if wave_id == WAVE2_RULE_BUNDLES:
            expected_dependency = required_references["dependency"]
            if (
                len(normalized_dependencies) != 1
                or normalized_dependencies[0]["path"]
                != expected_dependency["path"]
                or normalized_dependencies[0]["wave_id"]
                != expected_dependency["wave_id"]
            ):
                reference_errors["dependency"] = {
                    "expected": expected_dependency,
                    "actual": normalized_dependencies,
                }
        elif normalized_dependencies:
            reference_errors["dependency"] = {
                "expected": [],
                "actual": normalized_dependencies,
            }
        if reference_errors:
            raise ArtifactError(
                f"{wave_id} 票据必须使用固定引用路径和依赖类型；"
                f"不匹配={reference_errors}"
            )
        expected_binding_paths = (
            set(RESTRUCTURE_WAVE_SPECS[wave_id]["required_inputs"])
            | {
                plan["baseline_plan"]["path"],
                plan["baseline_receipt"]["path"],
                plan["decision_ticket"]["path"],
                plan["conflict_lock"]["path"],
                plan["test_impact"]["path"],
            }
            | {
                dependency["path"]
                for dependency in normalized_dependencies
            }
        )
        actual_binding_paths = {
            binding["path"] for binding in normalized_bindings
        }
        if actual_binding_paths != expected_binding_paths:
            raise ArtifactError(
                f"{wave_id} bound_inputs 必须与必绑输入和当前票据引用完全相等；"
                f"多余={sorted(actual_binding_paths - expected_binding_paths)}，"
                f"缺少={sorted(expected_binding_paths - actual_binding_paths)}"
            )

    expected_read_scopes = RESTRUCTURE_WAVE_SPECS[wave_id][
        "required_read_scopes"
    ]
    if window["read_allowlist"] != expected_read_scopes:
        raise ArtifactError(
            "responsibility_window.read_allowlist 必须与当前 Wave "
            "读取范围完全相等"
        )
    declared_read_paths = {
        *(row["path"] for row in normalized_bindings),
        *(row["path"] for row in normalized_dependencies),
        plan["baseline_plan"]["path"],
        plan["baseline_receipt"]["path"],
        plan["decision_ticket"]["path"],
        plan["conflict_lock"]["path"],
        plan["test_impact"]["path"],
    }
    reads_outside = sorted(
        path
        for path in declared_read_paths
        if not any(
            _wave_read_path_is_allowed(wave_id, path, allowed)
            for allowed in expected_read_scopes
        )
    )
    if reads_outside:
        raise ArtifactError(
            "Wave 声明读取路径超出许可范围，拒绝在读文件后再补判："
            f"{reads_outside}"
        )
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


def _wave2_preparation_ticket_evidence(
    root: Path,
    ticket: dict[str, Any] | None,
    *,
    ticket_path: str,
    upstream_dependency: dict[str, str] | None,
    expected_ticket_id: str,
    expected_context_id: str,
    evidence_reads: dict[str, str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    if ticket is None:
        return False, {
            "valid": False,
            "errors": ["Wave2 专用准备票不存在或 SHA 不匹配"],
        }
    errors: list[str] = []
    expected_keys = {
        "contract_version",
        "ticket_id",
        "ticket_kind",
        "authority",
        "authorization_context_id",
        "evidence_class",
        "human_readback",
        "selected_route",
        "selected_scope",
        "source_messages",
        "decisions",
        "upstream_completion",
        "eligibility_capability_ceiling",
        "authorization_boundary",
    }
    if set(ticket) != expected_keys:
        errors.append("Wave2 专用准备票字段不完整或含未知字段")
    if (
        ticket.get("contract_version")
        != RESTRUCTURE_WAVE2_PREPARATION_TICKET_V1
    ):
        errors.append("必须使用 Wave2 专用准备票合同，旧 S0 票不可复用")
    if ticket.get("ticket_id") != expected_ticket_id:
        errors.append("ticket_id 不匹配")
    if ticket.get("ticket_kind") != "wave2_gate_extension_eligibility":
        errors.append("ticket_kind 不匹配")
    if ticket.get("authority") != "CZ":
        errors.append("authority 必须是 CZ")
    if ticket.get("authorization_context_id") != expected_context_id:
        errors.append("authorization_context_id 不匹配")
    if ticket.get("evidence_class") != "same_task_human_readback":
        errors.append("evidence_class 必须是 same_task_human_readback")
    if ticket.get("human_readback") != {
        "required": True,
        "confirmed": True,
        "cryptographic_proof": False,
    }:
        errors.append("human_readback 不匹配")
    if ticket.get("selected_route") != "A_PLUS":
        errors.append("selected_route 必须是 A_PLUS")
    if ticket.get("selected_scope") != [WAVE2_RULE_BUNDLES]:
        errors.append("selected_scope 必须只含 WAVE2_RULE_BUNDLES")
    messages = ticket.get("source_messages")
    source_texts: set[str] = set()
    if not isinstance(messages, list) or len(messages) != 1:
        errors.append("source_messages 必须恰好记录本任务的一条人工选择")
    else:
        for index, row in enumerate(messages):
            if (
                not isinstance(row, dict)
                or set(row) != {"text", "sha256"}
                or not isinstance(row.get("text"), str)
                or not row["text"]
                or row.get("sha256") != _sha256_text(row["text"])
            ):
                errors.append(f"source_messages[{index}] 无效")
            else:
                source_texts.add(row["text"])
    if source_texts != {WAVE2_PREPARATION_SOURCE_TEXT}:
        errors.append("source_messages 必须精确记录当前 S-02-A 选择 a")
    decisions = ticket.get("decisions")
    if not isinstance(decisions, dict):
        errors.append("decisions 必须是对象")
    else:
        actual_decisions = {
            decision_id: (
                (row.get("status"), row.get("value"))
                if isinstance(row, dict)
                else None
            )
            for decision_id, row in decisions.items()
        }
        if actual_decisions != WAVE2_PREPARATION_VALUES:
            errors.append("decisions 必须精确匹配 Wave2 准备边界")
    expected_dependency = (
        {
            "path": upstream_dependency["path"],
            "sha256": upstream_dependency["sha256"],
        }
        if upstream_dependency is not None
        else None
    )
    if ticket.get("upstream_completion") != expected_dependency:
        errors.append("Wave2 准备票没有绑定本次 S0 完成票 v2")
    if (
        ticket.get("eligibility_capability_ceiling")
        != RESTRUCTURE_WAVE_SPECS[WAVE2_RULE_BUNDLES]["capability_limits"]
    ):
        errors.append("Wave2 准备能力上限不匹配")
    expected_boundary = {
        "authorizes_wave": False,
        "authorizes_rule_bundle_construction": False,
        "authorizes_offline_resolve": False,
        "authorizes_preflight": False,
        "authorizes_network": False,
        "authorizes_credential_read": False,
        "authorizes_request_send": False,
        "authorizes_model_api": False,
        "authorizes_notion_write": False,
        "authorizes_external_removal": False,
        "requires_later_same_task_positive_construction_confirmation": True,
    }
    if ticket.get("authorization_boundary") != expected_boundary:
        errors.append("Wave2 准备票授权边界不匹配")

    source_s0_ticket: dict[str, str] | None = copy.deepcopy(
        RESTRUCTURE_WAVE_SPECS[WAVE2_RULE_BUNDLES][
            "required_prior_decision_ticket"
        ]
    )
    source_s0_ticket_evidence = None
    if source_s0_ticket is not None:
        try:
            source_s0_ticket = _sha256_reference(
                source_s0_ticket,
                "旧 S0 决策票",
            )
            _, source_s0_ticket_evidence = _reference_payload(
                root,
                source_s0_ticket,
                evidence_reads=evidence_reads,
            )
            if not source_s0_ticket_evidence["sha256_matched"]:
                errors.append("旧 S0 决策票已缺失或被改写")
        except ArtifactError as exc:
            errors.append(str(exc))
        if ticket_path == source_s0_ticket.get("path"):
            errors.append("Wave2 准备票必须新建，不能改写旧 S0 决策票")
        try:
            new_path = _repo_path_without_symlinks(
                root,
                Path(ticket_path),
                name="Wave2 专用准备票",
            )
            old_path = _repo_path_without_symlinks(
                root,
                Path(source_s0_ticket["path"]),
                name="旧 S0 决策票",
            )
            if new_path.is_file() and old_path.is_file():
                new_stat = os.stat(new_path, follow_symlinks=False)
                old_stat = os.stat(old_path, follow_symlinks=False)
                if (new_stat.st_dev, new_stat.st_ino) == (
                    old_stat.st_dev,
                    old_stat.st_ino,
                ):
                    errors.append("Wave2 准备票不得与旧 S0 票共用硬链接")
        except (ArtifactError, OSError, KeyError) as exc:
            errors.append(f"无法核对新旧决策票分离：{exc}")
    return not errors, {
        "valid": not errors,
        "errors": errors,
        "source_s0_decision_ticket": source_s0_ticket,
        "source_s0_decision_ticket_evidence": source_s0_ticket_evidence,
    }


def _wave5_authorization_ticket_evidence(
    root: Path,
    ticket: dict[str, Any] | None,
    *,
    ticket_path: str,
    expected_ticket_id: str,
    expected_context_id: str,
    evidence_reads: dict[str, str] | None = None,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    if ticket is None:
        return (
            False,
            {
                "valid": False,
                "errors": ["Wave5 专用授权票不存在或 SHA 不匹配"],
            },
            [],
        )
    errors: list[str] = []
    expected_keys = {
        "contract_version",
        "ticket_id",
        "ticket_kind",
        "authority",
        "authorization_context_id",
        "evidence_class",
        "human_readback",
        "selected_route",
        "selected_scope",
        "source_messages",
        "decisions",
        "external_root_identity",
        "external_sources",
        "upstream_decision",
        "eligibility_capability_ceiling",
        "authorization_boundary",
    }
    if set(ticket) != expected_keys:
        errors.append("Wave5 专用授权票字段不完整或含未知字段")
    if ticket.get("contract_version") != RESTRUCTURE_WAVE5_AUTHORIZATION_V1:
        errors.append("必须使用 Wave5 专用授权票合同")
    if ticket.get("ticket_id") != expected_ticket_id:
        errors.append("ticket_id 不匹配")
    if ticket.get("ticket_kind") != "wave5_gate_and_scanner_authorization":
        errors.append("ticket_kind 不匹配")
    if ticket.get("authority") != "CZ":
        errors.append("authority 必须是 CZ")
    if ticket.get("authorization_context_id") != expected_context_id:
        errors.append("authorization_context_id 不匹配")
    if ticket.get("evidence_class") != "same_task_human_readback":
        errors.append("evidence_class 必须是 same_task_human_readback")
    if ticket.get("human_readback") != {
        "required": True,
        "confirmed": True,
        "cryptographic_proof": False,
    }:
        errors.append("human_readback 不匹配")
    if ticket.get("selected_route") != "A_PLUS_EXTERNAL_READONLY":
        errors.append("selected_route 必须是 A_PLUS_EXTERNAL_READONLY")
    if ticket.get("selected_scope") != [WAVE5_EXTERNAL_ARCHIVE_READONLY]:
        errors.append("selected_scope 必须只含 Wave5 外置仓只读适配")

    messages = ticket.get("source_messages")
    if not isinstance(messages, list) or len(messages) != 1:
        errors.append("source_messages 必须恰好记录本任务的一条人工选择")
    else:
        row = messages[0]
        if (
            not isinstance(row, dict)
            or set(row) != {"text", "sha256"}
            or row.get("text") != WAVE5_AUTHORIZATION_SOURCE_TEXT
            or row.get("sha256") != _sha256_text(WAVE5_AUTHORIZATION_SOURCE_TEXT)
        ):
            errors.append("source_messages 必须精确记录 CZ 的 S-04-B 选择")

    decisions = ticket.get("decisions")
    if not isinstance(decisions, dict):
        errors.append("decisions 必须是对象")
    else:
        actual_decisions = {
            decision_id: (
                (row.get("status"), row.get("value"))
                if isinstance(row, dict)
                else None
            )
            for decision_id, row in decisions.items()
        }
        if actual_decisions != WAVE5_AUTHORIZATION_DECISION_VALUES:
            errors.append("decisions 必须精确匹配 Wave5 只读施工边界")

    if ticket.get("external_root_identity") != WAVE5_EXTERNAL_ROOT_ID:
        errors.append("external_root_identity 不匹配")
    sources = ticket.get("external_sources")
    normalized_sources: list[dict[str, Any]] = []
    if not isinstance(sources, list) or len(sources) != len(
        WAVE5_EXTERNAL_MANIFESTS
    ):
        errors.append("external_sources 必须恰好登记三份旧 MANIFEST")
    else:
        for index, (raw, expected) in enumerate(
            zip(sources, WAVE5_EXTERNAL_MANIFESTS, strict=True)
        ):
            if not isinstance(raw, dict) or set(raw) != {
                "source_id",
                "batch_relative_path",
                "manifest_relative_path",
                "expected_sha256",
                "expected_entries",
            }:
                errors.append(f"external_sources[{index}] 字段不完整")
                continue
            digest = raw.get("expected_sha256")
            expected_static = {
                "source_id": expected["source_id"],
                "batch_relative_path": expected["batch_relative_path"],
                "manifest_relative_path": expected["manifest_relative_path"],
                "expected_entries": expected["expected_entries"],
            }
            actual_static = {
                key: raw.get(key) for key in expected_static
            }
            if actual_static != expected_static:
                errors.append(f"external_sources[{index}] 身份或条目数不匹配")
            if (
                not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                errors.append(f"external_sources[{index}] SHA-256 无效")
                continue
            normalized_sources.append(copy.deepcopy(raw))
    if (
        len(normalized_sources) == len(WAVE5_EXTERNAL_MANIFESTS)
        and sum(row["expected_entries"] for row in normalized_sources) != 148
    ):
        errors.append("Wave5 三份旧账必须精确合计 148 条")

    expected_prior_reference = _sha256_reference(
        copy.deepcopy(
            RESTRUCTURE_WAVE_SPECS[WAVE5_EXTERNAL_ARCHIVE_READONLY][
                "required_prior_decision_ticket"
            ]
        ),
        "固定旧 S0 决策票",
    )
    try:
        reported_prior_reference = _sha256_reference(
            ticket.get("upstream_decision"),
            "Wave5 授权票.upstream_decision",
        )
    except ArtifactError as exc:
        errors.append(str(exc))
        reported_prior_reference = None
    if reported_prior_reference != expected_prior_reference:
        errors.append("Wave5 授权票没有绑定固定路径和 SHA 的原 S0 决策票")
    prior_reference = copy.deepcopy(expected_prior_reference)
    prior_payload = None
    prior_evidence = None
    prior_payload, prior_evidence = _reference_payload(
        root,
        prior_reference,
        evidence_reads=evidence_reads,
    )
    if prior_payload is None:
        errors.append("固定旧 S0 决策票已缺失或被改写")
    else:
        prior_passed, prior_validation = _decision_ticket_evidence(
            prior_payload,
            expected_ticket_id="S0-DECISIONS-CZ-20260730-01",
            wave_id=S0_MATERIALIZE_ONLY,
            expected_context_id=expected_context_id,
        )
        if not prior_passed:
            errors.append("原 S0 决策票身份、内容或授权上下文不匹配")
            if prior_evidence is not None:
                prior_evidence["ticket_validation"] = prior_validation
    try:
        new_path = _repo_path_without_symlinks(
            root,
            Path(ticket_path),
            name="Wave5 专用授权票",
        )
        old_path = _repo_path_without_symlinks(
            root,
            Path(prior_reference["path"]),
            name="旧 S0 决策票",
        )
        if new_path.is_file() and old_path.is_file():
            new_stat = os.stat(new_path, follow_symlinks=False)
            old_stat = os.stat(old_path, follow_symlinks=False)
            if (new_stat.st_dev, new_stat.st_ino) == (
                old_stat.st_dev,
                old_stat.st_ino,
            ):
                errors.append("Wave5 授权票不得与旧 S0 票共用硬链接")
    except (ArtifactError, OSError, KeyError) as exc:
        errors.append(f"无法核对新旧决策票分离：{exc}")

    if (
        ticket.get("eligibility_capability_ceiling")
        != RESTRUCTURE_WAVE_SPECS[WAVE5_EXTERNAL_ARCHIVE_READONLY][
            "capability_limits"
        ]
    ):
        errors.append("Wave5 准备能力上限不匹配")
    expected_boundary = {
        "authorizes_gate_extension": True,
        "authorizes_read_only_scanner_construction_after_mechanical_pass": True,
        "requires_additional_construction_confirmation": False,
        "authorizes_manifest_rewrite": False,
        "authorizes_external_content_traversal": False,
        "authorizes_physical_move": False,
        "authorizes_delete": False,
        "authorizes_write_stub": False,
        "authorizes_restore_pass": False,
        "authorizes_network": False,
        "authorizes_credential_read": False,
        "authorizes_request_send": False,
        "authorizes_model_api": False,
        "authorizes_notion_write": False,
        "authorizes_external_removal": False,
    }
    if ticket.get("authorization_boundary") != expected_boundary:
        errors.append("Wave5 授权边界不匹配")

    external_rows: list[dict[str, Any]] = []
    if (
        len(normalized_sources) == len(WAVE5_EXTERNAL_MANIFESTS)
        and not errors
    ):
        _, external_rows, external_errors = _wave5_external_snapshot(
            root,
            normalized_sources,
        )
        errors.extend(external_errors)
    return (
        not errors,
        {
            "valid": not errors,
            "errors": errors,
            "external_sources": normalized_sources,
            "external_snapshot": external_rows,
            "source_s0_decision_ticket": prior_reference,
            "source_s0_decision_ticket_evidence": prior_evidence,
        },
        external_rows,
    )


def _baseline_receipt_evidence(
    root: Path,
    plan: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
    *,
    expected_plan_id: str,
    expected_head_sha: str,
    expected_context_id: str,
    outer_wave_id: str,
    outer_read_scopes: list[str],
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
    nested_reads_outside = sorted(
        row["path"]
        for row in normalized_plan["bound_inputs"]
        if not any(
            _wave_read_path_is_allowed(
                outer_wave_id,
                row["path"],
                allowed,
            )
            for allowed in outer_read_scopes
        )
    )
    if nested_reads_outside:
        errors.append(
            "一级计划绑定输入超出外层 Wave 读取范围，拒绝重放："
            f"{nested_reads_outside}"
        )
    nested_binding_paths = {
        row["path"] for row in normalized_plan["bound_inputs"]
    }
    nested_binding_extra: list[str] = []
    nested_binding_missing: list[str] = []
    if outer_wave_id in {
        WAVE2_RULE_BUNDLES,
        WAVE5_EXTERNAL_ARCHIVE_READONLY,
    }:
        nested_binding_extra = sorted(
            nested_binding_paths - RESTRUCTURE_BASELINE_REQUIRED_INPUTS
        )
        nested_binding_missing = sorted(
            RESTRUCTURE_BASELINE_REQUIRED_INPUTS - nested_binding_paths
        )
        if nested_binding_extra or nested_binding_missing:
            wave_label = (
                "Wave2"
                if outer_wave_id == WAVE2_RULE_BUNDLES
                else "Wave5"
            )
            errors.append(
                f"{wave_label} 的一级计划 bound_inputs "
                "必须与一级基线必绑输入完全相等；"
                f"多余={nested_binding_extra}，缺少={nested_binding_missing}"
            )
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
    nested_replay_allowed = (
        not nested_reads_outside
        and not nested_binding_extra
        and not nested_binding_missing
    )
    fresh = (
        _evaluate_restructure_baseline_snapshot(
            root,
            normalized_plan,
            dirty_paths=dirty_paths,
            head_sha=expected_head_sha,
            governance_mismatch_paths=governance_mismatch_paths,
            evaluated_at=now,
        )
        if nested_replay_allowed
        else {
            "status": "BLOCKED",
            "blockers": ["nested_baseline_inputs_rejected_before_replay"],
            "evidence_snapshot": [],
        }
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
        "nested_reads_outside": nested_reads_outside,
        "nested_binding_extra": nested_binding_extra,
        "nested_binding_missing": nested_binding_missing,
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
    expected_route: str,
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
    if (
        impact.get("wave_id") != wave_id
        or impact.get("route") != expected_route
    ):
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


def _completion_request_v2(value: Any) -> dict[str, Any]:
    request = _must_dict(value, "Wave 完成票 v2 请求")
    expected_keys = {
        "contract_version",
        "completion_id",
        "wave_id",
        "authorization_context_id",
        "pre_commit_sha",
        "post_commit_sha",
        "wave_plan",
        "wave_receipt",
    }
    if set(request) != expected_keys:
        raise ArtifactError(
            "Wave 完成票 v2 请求字段必须完全相等；"
            f"多余={sorted(set(request) - expected_keys)}，"
            f"缺少={sorted(expected_keys - set(request))}"
        )
    if (
        request.get("contract_version")
        != RESTRUCTURE_WAVE_COMPLETION_REQUEST_V2
    ):
        raise ArtifactError(
            "Wave 完成票 v2 请求 contract_version 必须是 "
            f"{RESTRUCTURE_WAVE_COMPLETION_REQUEST_V2}"
        )
    _must_nonempty_string(request.get("completion_id"), "completion_id")
    wave_id = _must_nonempty_string(request.get("wave_id"), "wave_id")
    if wave_id not in RESTRUCTURE_WAVE_SPECS:
        raise ArtifactError(f"不支持的完成 Wave：{wave_id}")
    _must_nonempty_string(
        request.get("authorization_context_id"),
        "authorization_context_id",
    )
    for key in ("pre_commit_sha", "post_commit_sha"):
        value = _must_nonempty_string(request.get(key), key)
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ArtifactError(f"{key} 必须是小写 40 位 Git SHA")
    request["wave_plan"] = _sha256_reference(
        request.get("wave_plan"),
        "wave_plan",
    )
    request["wave_receipt"] = _sha256_reference(
        request.get("wave_receipt"),
        "wave_receipt",
    )
    allowed_read_scopes = RESTRUCTURE_WAVE_SPECS[wave_id][
        "required_read_scopes"
    ]
    outside_references = sorted(
        reference["path"]
        for reference in (request["wave_plan"], request["wave_receipt"])
        if not any(
            _wave_read_path_is_allowed(
                wave_id,
                reference["path"],
                allowed,
            )
            for allowed in allowed_read_scopes
        )
    )
    if outside_references:
        raise ArtifactError(
            "Wave 完成请求引用超出当前 Wave 读取范围，拒绝先读后判："
            f"{outside_references}"
        )
    return request


def _wave5_completion_external_evidence(
    root: Path,
    plan: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
    *,
    expected_context_id: str,
    evidence_reads: dict[str, str] | None,
) -> tuple[bool, dict[str, Any]]:
    """把 Wave5 开工票的外置快照与固定授权票和当前现场重新对齐。"""

    errors: list[str] = []
    ticket_reference: dict[str, str] | None = None
    ticket_reference_evidence: dict[str, Any] | None = None
    ticket_validation: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = []
    live_rows: list[dict[str, Any]] = []

    if plan is None:
        errors.append("原 Wave5 计划无效，无法回放外置证据")
    else:
        ticket_reference = plan["decision_ticket"]
        ticket, ticket_reference_evidence = _reference_payload(
            root,
            ticket_reference,
            evidence_reads=evidence_reads,
        )
        ticket_passed, ticket_validation, live_rows = (
            _wave5_authorization_ticket_evidence(
                root,
                ticket,
                ticket_path=ticket_reference["path"],
                expected_ticket_id=plan["expected_decision_ticket_id"],
                expected_context_id=expected_context_id,
                evidence_reads=evidence_reads,
            )
        )
        if not ticket_passed:
            errors.append("Wave5 固定授权票或其外置来源无法通过重放")
        raw_sources = ticket_validation.get("external_sources")
        if isinstance(raw_sources, list):
            sources = copy.deepcopy(raw_sources)

    expected_snapshot = [
        {
            "kind": "wave5_fixed_sibling_manifest",
            "path": _wave5_external_identity(source["batch_relative_path"]),
            "batch_relative_path": source["batch_relative_path"],
            "sha256": source["expected_sha256"],
            "entries": source["expected_entries"],
        }
        for source in sources
    ]
    if len(expected_snapshot) != len(WAVE5_EXTERNAL_MANIFESTS):
        errors.append("Wave5 授权票没有给出恰好三份固定外置来源")

    receipt_snapshot = (
        receipt.get("external_evidence_snapshot")
        if isinstance(receipt, dict)
        else None
    )
    if receipt_snapshot != expected_snapshot:
        errors.append("原 Wave5 开工票的外置证据快照缺失、伪造或字段漂移")

    live_snapshot = [
        {
            "kind": row.get("kind"),
            "path": row.get("path"),
            "batch_relative_path": row.get("batch_relative_path"),
            "sha256": row.get("actual_sha256"),
            "entries": row.get("actual_entries"),
        }
        for row in live_rows
    ]
    if live_snapshot != expected_snapshot:
        errors.append("三份固定外置 MANIFEST 的当前 SHA 或条目数已漂移")

    return not errors, {
        "valid": not errors,
        "errors": errors,
        "authorization_ticket": ticket_reference,
        "authorization_ticket_reference_evidence": ticket_reference_evidence,
        "authorization_ticket_validation": ticket_validation,
        "expected_snapshot": expected_snapshot,
        "receipt_snapshot": receipt_snapshot,
        "live_snapshot": live_snapshot,
    }


def evaluate_restructure_wave_completion_v2(
    root: Path,
    request_raw: Any,
    *,
    evidence_reads: dict[str, str] | None = None,
) -> dict[str, Any]:
    """只用 Git 历史对象和受 SHA 绑定的票生成可重放完成证据。"""

    root = root.resolve()
    request = _completion_request_v2(copy.deepcopy(request_raw))
    wave_id = request["wave_id"]
    context_id = request["authorization_context_id"]
    pre_commit = request["pre_commit_sha"]
    post_commit = request["post_commit_sha"]
    spec = RESTRUCTURE_WAVE_SPECS[wave_id]
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, evidence: Any) -> None:
        checks.append({"check_id": check_id, "passed": passed, "evidence": evidence})

    plan_raw, plan_reference = _reference_payload(
        root,
        request["wave_plan"],
        evidence_reads=evidence_reads,
    )
    normalized_plan: dict[str, Any] | None = None
    plan_errors: list[str] = []
    if plan_raw is None:
        plan_errors.append("原 Wave 计划不存在或 SHA 不匹配")
    else:
        try:
            normalized_plan = _wave_plan(copy.deepcopy(plan_raw))
        except ArtifactError as exc:
            plan_errors.append(f"原 Wave 计划无效：{exc}")
    if normalized_plan is not None:
        window = normalized_plan["responsibility_window"]
        if normalized_plan["wave_id"] != wave_id:
            plan_errors.append("原 Wave 计划 wave_id 不匹配")
        if normalized_plan["expected_head_sha"] != pre_commit:
            plan_errors.append("原 Wave 计划起始提交不匹配")
        if window["authorization_context_id"] != context_id:
            plan_errors.append("原 Wave 计划授权上下文不匹配")
        if window["candidate_write_paths"] != spec["candidate_write_paths"]:
            plan_errors.append("原 Wave 计划写集不匹配")
        if normalized_plan["capability_limits"] != spec["capability_limits"]:
            plan_errors.append("原 Wave 计划能力边界不匹配")
    add(
        "source_wave_plan_bound",
        not plan_errors,
        {
            "errors": plan_errors,
            "reference": plan_reference,
            "content_sha256": (
                _canonical_json_sha256(normalized_plan)
                if normalized_plan is not None
                else None
            ),
        },
    )

    receipt_raw, receipt_reference = _reference_payload(
        root,
        request["wave_receipt"],
        evidence_reads=evidence_reads,
    )
    receipt_errors: list[str] = []
    expected_check_ids = {
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
    if wave_id == WAVE5_EXTERNAL_ARCHIVE_READONLY:
        expected_check_ids.add("external_manifest_snapshot_stable")
    if receipt_raw is None:
        receipt_errors.append("原 Wave 开工票不存在或 SHA 不匹配")
    else:
        receipt_checks = receipt_raw.get("checks")
        receipt_check_ids = {
            row.get("check_id")
            for row in receipt_checks
            if isinstance(row, dict)
        } if isinstance(receipt_checks, list) else set()
        receipt_window = receipt_raw.get("responsibility_window")
        boundary = receipt_raw.get("authorization_boundary")
        if (
            receipt_raw.get("contract_version") != RESTRUCTURE_WAVE_RECEIPT_V1
            or receipt_raw.get("wave_id") != wave_id
            or receipt_raw.get("status") != "PASS"
            or receipt_raw.get("blockers") != []
            or receipt_raw.get("head_sha") != pre_commit
        ):
            receipt_errors.append("原 Wave 开工票不是当前起始提交的无阻塞 PASS")
        if (
            normalized_plan is None
            or receipt_raw.get("plan_id") != normalized_plan.get("plan_id")
            or receipt_raw.get("plan_content_sha256")
            != _canonical_json_sha256(normalized_plan)
        ):
            receipt_errors.append("原 Wave 开工票没有绑定实际计划")
        if (
            not isinstance(receipt_window, dict)
            or receipt_window.get("authorization_context_id") != context_id
        ):
            receipt_errors.append("原 Wave 开工票授权上下文不匹配")
        if (
            not isinstance(receipt_checks, list)
            or len(receipt_checks) != len(expected_check_ids)
            or receipt_check_ids != expected_check_ids
            or any(
                not isinstance(row, dict) or row.get("passed") is not True
                for row in receipt_checks
            )
        ):
            receipt_errors.append("原 Wave 开工票检查集不完整或未全过")
        if (
            not isinstance(boundary, dict)
            or boundary.get("mechanical_preconditions_pass") is not True
            or boundary.get("authorizes_wave") is not False
            or boundary.get("eligible_wave_id") != wave_id
            or boundary.get("eligible_write_paths")
            != spec["candidate_write_paths"]
        ):
            receipt_errors.append("原 Wave 开工票机械边界不匹配")
    add(
        "source_wave_receipt_pass",
        not receipt_errors,
        {"errors": receipt_errors, "reference": receipt_reference},
    )
    if wave_id == WAVE5_EXTERNAL_ARCHIVE_READONLY:
        external_passed, external_evidence = (
            _wave5_completion_external_evidence(
                root,
                normalized_plan,
                receipt_raw,
                expected_context_id=context_id,
                evidence_reads=evidence_reads,
            )
        )
        add(
            "source_wave5_external_evidence_replayed",
            external_passed,
            external_evidence,
        )

    commits_exist = False
    try:
        pre_exists = git_commit_exists(root, pre_commit)
        post_exists = git_commit_exists(root, post_commit)
        commits_exist = pre_exists and post_exists
        commit_evidence: dict[str, Any] = {
            "pre_commit_sha": pre_commit,
            "pre_exists": pre_exists,
            "post_commit_sha": post_commit,
            "post_exists": post_exists,
        }
    except (ArtifactError, OSError, subprocess.SubprocessError) as exc:
        commit_evidence = {"error": str(exc)}
    add("git_commits_exist", commits_exist, commit_evidence)

    ancestor = False
    changes: list[dict[str, str]] = []
    transition_error = None
    if commits_exist:
        try:
            ancestor = git_is_ancestor(root, pre_commit, post_commit)
            changes = git_name_status_between_exact(
                root,
                pre_commit,
                post_commit,
            )
        except (ArtifactError, OSError, subprocess.SubprocessError) as exc:
            transition_error = str(exc)
    add(
        "git_ancestry",
        ancestor,
        {
            "pre_commit_sha": pre_commit,
            "post_commit_sha": post_commit,
            "ancestor": ancestor,
            "error": transition_error,
        },
    )

    allowed_paths = list(spec["candidate_write_paths"])
    statuses_valid = bool(changes) and all(
        row.get("status") in {"A", "M"} for row in changes
    )
    changed_paths = [
        row["path"]
        for row in changes
        if isinstance(row.get("path"), str)
    ]
    unique_paths = len(changed_paths) == len(set(changed_paths))
    outside_paths = sorted(
        path
        for path in changed_paths
        if not any(
            _wave_candidate_write_path_is_allowed(
                wave_id,
                path,
                allowed,
            )
            for allowed in allowed_paths
        )
    )
    diff_valid = (
        ancestor
        and statuses_valid
        and unique_paths
        and len(changed_paths) == len(changes)
        and not outside_paths
    )
    add(
        "git_diff_exact_scope",
        diff_valid,
        {
            "changes": changes,
            "candidate_write_paths": allowed_paths,
            "outside_paths": outside_paths,
            "only_add_or_modify_no_delete_or_rename": statuses_valid,
            "paths_unique": unique_paths,
        },
    )

    blobs: list[dict[str, Any]] = []
    blob_errors: list[str] = []
    if diff_valid:
        for path in changed_paths:
            try:
                blobs.append(git_blob_evidence(root, post_commit, path))
            except (ArtifactError, OSError, subprocess.SubprocessError) as exc:
                blob_errors.append(str(exc))
    add(
        "git_blob_manifest_complete",
        diff_valid and len(blobs) == len(changed_paths) and not blob_errors,
        {
            "files": blobs,
            "manifest_sha256": _canonical_json_sha256(blobs),
            "errors": blob_errors,
        },
    )

    passed = all(row["passed"] for row in checks)
    return {
        "contract_version": RESTRUCTURE_WAVE_COMPLETION_V2,
        "completion_id": request["completion_id"],
        "wave_id": wave_id,
        "status": "GIT_SCOPE_PASS" if passed else "BLOCKED",
        "authorization_context_id": context_id,
        "pre_commit_sha": pre_commit,
        "post_commit_sha": post_commit,
        "completion_request": request,
        "source_wave_plan": request["wave_plan"],
        "source_wave_receipt": request["wave_receipt"],
        "git_diff": changes,
        "git_blob_manifest": blobs,
        "git_blob_manifest_sha256": _canonical_json_sha256(blobs),
        "authorization_boundary": {
            "authorizes_next_wave": False,
            "proves_historical_git_transition_only": True,
            "authorizes_preflight": False,
            "authorizes_network": False,
            "authorizes_credential_read": False,
            "authorizes_request_send": False,
            "authorizes_model_api": False,
            "authorizes_notion_write": False,
            "authorizes_external_removal": False,
            "tests_not_proven_or_evaluated": True,
        },
        "checks": checks,
        "blockers": [row["check_id"] for row in checks if not row["passed"]],
    }


def _completion_v2_dependency_evidence(
    root: Path,
    dependency: dict[str, str],
    *,
    expected_wave_id: str,
    expected_head_sha: str,
    expected_context_id: str,
    expected_source: dict[str, Any],
    evidence_reads: dict[str, str] | None,
) -> tuple[bool, dict[str, Any]]:
    errors: list[str] = []
    payload, reference = _reference_payload(
        root,
        dependency,
        evidence_reads=evidence_reads,
    )
    fresh: dict[str, Any] | None = None
    current_blob_rows: list[dict[str, Any]] = []
    current_blob_errors: list[str] = []
    allowed_blob_drift: list[dict[str, Any]] = []
    unauthorized_blob_drift: list[dict[str, Any]] = []
    if payload is None:
        errors.append("完成票 v2 不存在或 SHA 不匹配")
    elif payload.get("contract_version") != RESTRUCTURE_WAVE_COMPLETION_V2:
        errors.append("上游完成票不是 v2")
    else:
        request = payload.get("completion_request")
        top_level_source = {
            "wave_plan": payload.get("source_wave_plan"),
            "wave_receipt": payload.get("source_wave_receipt"),
            "pre_commit_sha": payload.get("pre_commit_sha"),
            "post_commit_sha": payload.get("post_commit_sha"),
        }
        request_source = (
            {
                "wave_plan": request.get("wave_plan"),
                "wave_receipt": request.get("wave_receipt"),
                "pre_commit_sha": request.get("pre_commit_sha"),
                "post_commit_sha": request.get("post_commit_sha"),
            }
            if isinstance(request, dict)
            else None
        )
        source_anchor_matched = (
            top_level_source == expected_source
            and request_source == expected_source
        )
        if not source_anchor_matched:
            errors.append("上游完成票 v2 的顶层或内嵌请求来源不匹配固定锚点")
        else:
            try:
                fresh = evaluate_restructure_wave_completion_v2(
                    root,
                    request,
                    evidence_reads=evidence_reads,
                )
            except (
                ArtifactError,
                OSError,
                subprocess.SubprocessError,
            ) as exc:
                errors.append(f"上游完成票 v2 无法重放：{exc}")
        if fresh is not None and payload != fresh:
            errors.append("上游完成票 v2 与 Git/原票重放结果不一致")
        if payload.get("wave_id") != expected_wave_id:
            errors.append("上游完成票 v2 wave_id 不匹配")
        if payload.get("authorization_context_id") != expected_context_id:
            errors.append("上游完成票 v2 授权上下文不匹配")
        if (
            payload.get("status") != "GIT_SCOPE_PASS"
            or payload.get("blockers") != []
        ):
            errors.append("上游完成票 v2 不是可重放的 GIT_SCOPE_PASS")
        if top_level_source != expected_source:
            errors.append("上游完成票 v2 不是 Wave2 规格钉住的真实 S0 来源")
        post_commit = payload.get("post_commit_sha")
        if not isinstance(post_commit, str):
            errors.append("上游完成票 v2 缺完成提交")
        else:
            try:
                if not git_is_ancestor(root, post_commit, expected_head_sha):
                    errors.append("上游完成提交不是当前 Wave HEAD 的祖先")
            except (
                ArtifactError,
                OSError,
                subprocess.SubprocessError,
            ) as exc:
                errors.append(f"无法核对上游完成提交：{exc}")
        blob_manifest = (
            fresh.get("git_blob_manifest")
            if fresh is not None
            else None
        )
        if not isinstance(blob_manifest, list) or not blob_manifest:
            current_blob_errors.append("上游完成票 v2 缺 Git blob 清单")
        else:
            historical_paths: list[str] = []
            for index, row in enumerate(blob_manifest):
                path = row.get("path") if isinstance(row, dict) else None
                if not isinstance(path, str):
                    current_blob_errors.append(
                        f"git_blob_manifest[{index}] 路径无效"
                    )
                    continue
                historical_paths.append(path)
                try:
                    current = git_blob_evidence(
                        root,
                        expected_head_sha,
                        path,
                    )
                    current_blob_rows.append(current)
                    historical_identity = {
                        key: row.get(key)
                        for key in ("git_mode", "git_blob_sha", "sha256")
                    }
                    current_identity = {
                        key: current.get(key)
                        for key in ("git_mode", "git_blob_sha", "sha256")
                    }
                    if historical_identity != current_identity:
                        drift = {
                            "path": path,
                            "historical": historical_identity,
                            "current": current_identity,
                        }
                        if path == "governance/tool_registry.json":
                            allowed_blob_drift.append(drift)
                        else:
                            unauthorized_blob_drift.append(drift)
                except (
                    ArtifactError,
                    OSError,
                    subprocess.SubprocessError,
                ) as exc:
                    current_blob_errors.append(str(exc))
            current_paths = [
                row["path"]
                for row in current_blob_rows
                if isinstance(row.get("path"), str)
            ]
            if (
                len(historical_paths) != len(set(historical_paths))
                or current_paths != historical_paths
            ):
                current_blob_errors.append(
                    "S0 历史输出与当前输出路径不能一一对应"
                )
        if current_blob_errors:
            errors.append("S0 输出在当前 Wave HEAD 已缺失或不再是普通 blob")
        if unauthorized_blob_drift:
            errors.append(
                "除 governance/tool_registry.json 外，S0 历史输出内容或模式已漂移"
            )
    return not errors, {
        "valid": not errors,
        "errors": errors,
        "reference": reference,
        "fresh_status": fresh.get("status") if fresh is not None else None,
        "current_head_blobs": current_blob_rows if payload is not None else [],
        "allowed_current_head_blob_drift": allowed_blob_drift,
        "unauthorized_current_head_blob_drift": unauthorized_blob_drift,
        "current_head_blob_errors": (
            current_blob_errors if payload is not None else []
        ),
    }


def _wave_dependency_evidence(
    root: Path,
    dependencies: list[dict[str, str]],
    *,
    wave_id: str,
    expected_head_sha: str,
    expected_context_id: str,
    evidence_reads: dict[str, str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    required_wave_ids = RESTRUCTURE_WAVE_SPECS[wave_id][
        "required_completion_wave_ids"
    ]
    if not required_wave_ids:
        return not dependencies, {
            "valid": not dependencies,
            "errors": [] if not dependencies else ["当前 Wave 不得声明上游依赖"],
        }
    if required_wave_ids == [S0_MATERIALIZE_ONLY]:
        if (
            len(dependencies) != 1
            or dependencies[0]["wave_id"] != S0_MATERIALIZE_ONLY
        ):
            return False, {
                "valid": False,
                "errors": ["Wave2 必须绑定唯一 S0 完成票 v2"],
            }
        return _completion_v2_dependency_evidence(
            root,
            dependencies[0],
            expected_wave_id=S0_MATERIALIZE_ONLY,
            expected_head_sha=expected_head_sha,
            expected_context_id=expected_context_id,
            expected_source=RESTRUCTURE_WAVE_SPECS[wave_id][
                "required_completion_source"
            ],
            evidence_reads=evidence_reads,
        )
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
            if not any(
                _path_is_allowed(wave_plan_reference["path"], allowed)
                for allowed in RESTRUCTURE_WAVE_SPECS[wave_id][
                    "required_read_scopes"
                ]
            ):
                errors.append("Wave1 二级计划引用超出外层 S0 读取范围")
                wave_plan_reference = None
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
            if not any(
                _path_is_allowed(wave_receipt_reference["path"], allowed)
                for allowed in RESTRUCTURE_WAVE_SPECS[wave_id][
                    "required_read_scopes"
                ]
            ):
                errors.append("Wave1 二级票引用超出外层 S0 读取范围")
                wave_receipt_reference = None
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
        outer_wave_id=wave_id,
        outer_read_scopes=spec["required_read_scopes"],
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
    wave5_external_rows: list[dict[str, Any]] = []
    if wave_id == WAVE2_RULE_BUNDLES:
        decision_passed, decision_evidence = (
            _wave2_preparation_ticket_evidence(
                root,
                decision,
                ticket_path=plan["decision_ticket"]["path"],
                upstream_dependency=(
                    plan["dependencies"][0]
                    if len(plan["dependencies"]) == 1
                    else None
                ),
                expected_ticket_id=plan["expected_decision_ticket_id"],
                expected_context_id=window["authorization_context_id"],
                evidence_reads=evidence_reads,
            )
        )
    elif wave_id == WAVE5_EXTERNAL_ARCHIVE_READONLY:
        (
            decision_passed,
            decision_evidence,
            wave5_external_rows,
        ) = _wave5_authorization_ticket_evidence(
            root,
            decision,
            ticket_path=plan["decision_ticket"]["path"],
            expected_ticket_id=plan["expected_decision_ticket_id"],
            expected_context_id=window["authorization_context_id"],
            evidence_reads=evidence_reads,
        )
    else:
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
        expected_route=spec["route"],
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
    expected_read_scopes = spec["required_read_scopes"]
    missing_read_scopes = sorted(set(expected_read_scopes) - set(read_allowlist))
    extra_read_scopes = sorted(set(read_allowlist) - set(expected_read_scopes))
    reads_outside = sorted(
        path
        for path in binding_paths
        if not any(
            _wave_read_path_is_allowed(wave_id, path, allowed)
            for allowed in read_allowlist
        )
    )
    add(
        "read_allowlist_complete",
        read_allowlist == expected_read_scopes
        and not missing_read_scopes
        and not extra_read_scopes
        and not reads_outside,
        {
            "read_allowlist": read_allowlist,
            "expected_read_allowlist": expected_read_scopes,
            "missing_fixed_scopes": missing_read_scopes,
            "extra_scopes": extra_read_scopes,
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

    if wave_id == WAVE5_EXTERNAL_ARCHIVE_READONLY:
        sources = decision_evidence.get("external_sources")
        if (
            decision_passed
            and isinstance(sources, list)
            and len(sources) == len(WAVE5_EXTERNAL_MANIFESTS)
        ):
            second_passed, second_rows, second_errors = (
                _wave5_external_snapshot(root, sources)
            )
        else:
            second_passed = False
            second_rows = []
            second_errors = ["Wave5 授权票无效，未重复读取外置证据"]
        stable = (
            decision_passed
            and second_passed
            and wave5_external_rows == second_rows
        )
        add(
            "external_manifest_snapshot_stable",
            stable,
            {
                "first": wave5_external_rows,
                "second": second_rows,
                "errors": second_errors,
            },
        )

    passed = all(row["passed"] for row in checks)
    authorization_boundary = {
        "authorizes_wave": False,
        "mechanical_preconditions_pass": passed,
        "eligible_wave_id": wave_id if passed else None,
        "eligible_write_paths": expected_paths if passed else [],
        "requires_same_task_human_readback": True,
        "authorizes_physical_move": False,
        "authorizes_delete": False,
        "authorizes_preflight": False,
        "authorizes_network": False,
        "authorizes_credential_read": False,
        "authorizes_request_send": False,
        "authorizes_notion_write": False,
        "authorizes_model_api": False,
        "authorizes_external_removal": False,
        "authorization_context_claim_is_cryptographic_proof": False,
    }
    if wave_id == WAVE2_RULE_BUNDLES:
        authorization_boundary.update(
            {
                "preparation_ticket_is_not_construction_authorization": True,
                "requires_later_same_task_positive_construction_confirmation": True,
            }
        )
    elif wave_id == WAVE5_EXTERNAL_ARCHIVE_READONLY:
        authorization_boundary.update(
            {
                "same_task_construction_authorization_recorded": decision_passed,
                "requires_additional_construction_confirmation": False,
                "external_manifest_read_only": True,
                "authorizes_external_manifest_rewrite": False,
                "authorizes_external_content_traversal": False,
                "authorizes_restore_pass": False,
            }
        )
    receipt = {
        "contract_version": RESTRUCTURE_WAVE_RECEIPT_V1,
        "plan_id": plan["plan_id"],
        "plan_content_sha256": _canonical_json_sha256(plan),
        "status": "PASS" if passed else "BLOCKED",
        "evaluated_at": now.isoformat(),
        "head_sha": head_sha,
        "route": spec["route"],
        "wave_id": wave_id,
        "responsibility_window": window,
        "authorization_boundary": authorization_boundary,
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
    if wave_id == WAVE5_EXTERNAL_ARCHIVE_READONLY:
        receipt["external_evidence_snapshot"] = [
            {
                "kind": row["kind"],
                "path": row["path"],
                "batch_relative_path": row["batch_relative_path"],
                "sha256": row["actual_sha256"],
                "entries": row["actual_entries"],
            }
            for row in wave5_external_rows
            if row.get("matched")
        ]
    return receipt


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
    if receipt.get("wave_id") == WAVE5_EXTERNAL_ARCHIVE_READONLY:
        external_snapshot = receipt.get("external_evidence_snapshot")
        if (
            not isinstance(external_snapshot, list)
            or len(external_snapshot) != len(WAVE5_EXTERNAL_MANIFESTS)
        ):
            evidence_errors.append("Wave5 缺少三份固定外置证据快照")
        else:
            for index, (row, expected_source) in enumerate(
                zip(
                    external_snapshot,
                    WAVE5_EXTERNAL_MANIFESTS,
                    strict=True,
                )
            ):
                if not isinstance(row, dict):
                    evidence_errors.append(
                        f"external_evidence_snapshot[{index}] 格式无效"
                    )
                    continue
                batch = row.get("batch_relative_path")
                expected_identity = _wave5_external_identity(
                    expected_source["batch_relative_path"]
                )
                if (
                    row.get("kind") != "wave5_fixed_sibling_manifest"
                    or batch != expected_source["batch_relative_path"]
                    or row.get("path") != expected_identity
                    or row.get("entries")
                    != expected_source["expected_entries"]
                    or not isinstance(row.get("sha256"), str)
                ):
                    evidence_errors.append(
                        f"external_evidence_snapshot[{index}] 字段无效"
                    )
                    continue
                try:
                    actual_raw = _read_wave5_external_manifest_once(
                        root,
                        batch,
                    )
                    actual_sha = hashlib.sha256(actual_raw).hexdigest()
                except (ArtifactError, OSError) as exc:
                    evidence_errors.append(f"{expected_identity}: {exc}")
                    continue
                if actual_sha != row["sha256"]:
                    evidence_errors.append(
                        f"{expected_identity}: SHA 已变化"
                    )
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
    parser.add_argument(
        "--wave-completion-request",
        type=Path,
        help="读取 Wave 完成票 v2 请求",
    )
    parser.add_argument(
        "--wave-completion-output",
        type=Path,
        help="把 Wave 完成票 v2 写入 TEMP 的新路径",
    )
    parser.add_argument("--wave-lock-request", type=Path, help="读取 Wave 冲突锁请求")
    parser.add_argument("--wave-lock-output", type=Path, help="原子创建固定 Wave 冲突锁")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pairs = (
        ("--baseline-plan", args.baseline_plan, "--baseline-output", args.baseline_output),
        ("--wave-plan", args.wave_plan, "--wave-output", args.wave_output),
        (
            "--wave-completion-request",
            args.wave_completion_request,
            "--wave-completion-output",
            args.wave_completion_output,
        ),
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
            bool(args.wave_completion_request),
            bool(args.wave_lock_request),
        )
    )
    if selected_modes > 1:
        raise ArtifactError(
            "治理检查、一级票、二级票、完成票和冲突锁模式不能同时使用"
        )
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
    if args.wave_completion_request:
        request = read_json(args.wave_completion_request)
        receipt = evaluate_restructure_wave_completion_v2(ROOT, request)
        output = _receipt_output_path(ROOT, args.wave_completion_output)
        _write_json_exclusive(ROOT, output, receipt)
        try:
            fresh = evaluate_restructure_wave_completion_v2(ROOT, request)
        except Exception as exc:
            removed = _safe_unlink_repo_file(ROOT, output)
            result = "已撤销新票" if removed else "无法安全撤销新票"
            raise ArtifactError(f"完成票写入后复验失败，{result}：{exc}") from exc
        if fresh != receipt:
            removed = _safe_unlink_repo_file(ROOT, output)
            result = "已撤销新票" if removed else "无法安全撤销新票"
            raise ArtifactError(f"完成票写入后证据发生变化，{result}")
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0 if receipt["status"] == "GIT_SCOPE_PASS" else 2
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
