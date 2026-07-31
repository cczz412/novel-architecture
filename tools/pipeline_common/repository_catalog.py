#!/usr/bin/env python3
"""Build a read-only repository navigation view from existing truth sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

try:
    from repo_slim_inventory import (
        InventoryError,
        scan_with_git_index_details,
    )
except ModuleNotFoundError:  # package import in tests and library consumers
    from tools.repo_slim_inventory import (
        InventoryError,
        scan_with_git_index_details,
    )


ROOT = Path(__file__).resolve().parents[2]
CATALOG_VERSION = "repository-catalog-view-v1"
VIEWS = ("menu", "status", "models", "experiments", "artifacts", "slim", "all")
MAX_SOURCE_BYTES = 16 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

CURRENT_STATE_PATH = "governance/CURRENT_STATE.json"
MODULE_REGISTRY_PATH = "governance/module_registry.json"
ROUTE_REGISTRY_PATH = "governance/route_registry.json"
MODEL_PROFILE_REGISTRY_PATH = "config/model_call_profiles/registry.json"
EXTERNAL_ARCHIVE_REGISTRY_PATH = "governance/external_archive_registry.json"
ARTIFACT_RETRIEVAL_POLICY_PATH = "governance/artifact_retrieval_policy.json"
TOOL_REGISTRY_PATH = "governance/tool_registry.json"
FIXED_SOURCE_PATHS = {
    CURRENT_STATE_PATH,
    MODULE_REGISTRY_PATH,
    ROUTE_REGISTRY_PATH,
    MODEL_PROFILE_REGISTRY_PATH,
    EXTERNAL_ARCHIVE_REGISTRY_PATH,
    ARTIFACT_RETRIEVAL_POLICY_PATH,
    TOOL_REGISTRY_PATH,
}

AUTHORITY = {
    "mode": "derived_read_only_view",
    "defines_current_state": False,
    "writes": False,
    "reads_external_payload": False,
    "protected_discovery": False,
}

MENU = {
    "purpose": "按用途找到现役状态、模型零件、实验结论、仓外材料和瘦身入口。",
    "commands": [
        {
            "task": "我现在该看什么",
            "command": "python3 tools/novel_pipeline.py catalog status",
        },
        {
            "task": "模型怎么配、哪些零件已齐",
            "command": "python3 tools/novel_pipeline.py catalog models",
        },
        {
            "task": "实验做过什么、短结论在哪",
            "command": "python3 tools/novel_pipeline.py catalog experiments",
        },
        {
            "task": "仓外对象能否取、还缺什么",
            "command": "python3 tools/novel_pipeline.py catalog artifacts",
        },
        {
            "task": "仓库哪里重、离 10MB 还有多远",
            "command": "python3 tools/novel_pipeline.py catalog slim",
        },
        {
            "task": "一次交给其他 AI 看完整目录",
            "command": "python3 tools/novel_pipeline.py catalog all --json",
        },
    ],
    "truth_map": [
        {
            "view": "status",
            "authority": "CURRENT_STATE 加模块／路线登记，只说明当前执行和登记摘要。",
        },
        {
            "view": "models",
            "authority": "模型调用档登记，只说明登记状态、偏好映射与已登记组装包。",
        },
        {
            "view": "experiments",
            "authority": "实验对象、路线和显式结论卡，不扫描目录猜实验结论。",
        },
        {
            "view": "artifacts",
            "authority": "仓外对象登记与显式取件卡，不证明全部材料可恢复。",
        },
        {
            "view": "slim",
            "authority": "每次重新运行只读扫描器，不读取旧缓存冒充当前体积。",
        },
    ],
}


class CatalogError(RuntimeError):
    """A fixed catalog source is malformed or outside the read-only contract."""


def _safe_relative_path(value: object) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or "//" in value
        or value.endswith("/")
    ):
        raise CatalogError("目录来源路径格式错误")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or relative.as_posix() != value
        or any(part in {"", ".", ".."} for part in relative.parts)
        or ".git" in relative.parts
    ):
        raise CatalogError("目录来源必须是规范的仓内相对路径")
    return relative


def _read_beneath_root(repo_root: Path, relative_value: str) -> bytes:
    """Read one validated regular file without following repository symlinks."""

    relative = _safe_relative_path(relative_value)
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    file_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        file_flags |= os.O_NOFOLLOW

    descriptors: list[int] = []
    file_descriptor: int | None = None
    try:
        descriptors.append(os.open(repo_root, directory_flags))
        for part in relative.parts[:-1]:
            descriptors.append(
                os.open(part, directory_flags, dir_fd=descriptors[-1])
            )
        file_descriptor = os.open(
            relative.name,
            file_flags,
            dir_fd=descriptors[-1],
        )
        info = os.fstat(file_descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SOURCE_BYTES:
            raise CatalogError(f"目录来源不是普通小文件：{relative.as_posix()}")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(file_descriptor, 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_SOURCE_BYTES:
                raise CatalogError(f"目录来源超过读取上限：{relative.as_posix()}")
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError as exc:
        raise CatalogError(f"目录来源无法安全读取：{relative.as_posix()}") from exc
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(descriptors):
            os.close(descriptor)


class SourceReader:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._values: dict[str, dict[str, Any]] = {}
        self._sources: dict[str, dict[str, Any]] = {}

    def fixed_json(self, relative: str) -> dict[str, Any]:
        if relative not in FIXED_SOURCE_PATHS:
            raise CatalogError(f"目录没有获准读取这个来源：{relative}")
        return self._json(relative)

    def result_card_json(self, relative: str, card_id: str) -> dict[str, Any]:
        _validate_result_card_path(relative, card_id)
        return self._json(relative)

    def source_sha256(self, relative: str) -> str:
        source = self._sources.get(relative)
        if source is None:
            raise CatalogError(f"目录来源尚未读取：{relative}")
        return str(source["sha256"])

    def _json(self, relative: str) -> dict[str, Any]:
        cached = self._values.get(relative)
        if cached is not None:
            return cached
        raw = _read_beneath_root(self.repo_root, relative)
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CatalogError(f"目录来源不是合法 JSON：{relative}") from exc
        if not isinstance(value, dict):
            raise CatalogError(f"目录来源顶层必须是对象：{relative}")
        self._values[relative] = value
        self._sources[relative] = {
            "path": relative,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        return value

    def sources(self) -> list[dict[str, Any]]:
        return [self._sources[path] for path in sorted(self._sources)]


def _require_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CatalogError(f"{label} 不是列表")
    return value


def _require_dict(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogError(f"{label} 不是对象")
    return value


def _status_counts(rows: list[dict[str, Any]], field: str = "status") -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field, "unknown")) for row in rows).items()))


def _build_status(reader: SourceReader) -> dict[str, Any]:
    current = reader.fixed_json(CURRENT_STATE_PATH)
    modules = reader.fixed_json(MODULE_REGISTRY_PATH)
    routes = reader.fixed_json(ROUTE_REGISTRY_PATH)
    execution = _require_dict(current.get("current_execution"), "当前执行状态")
    task = _require_dict(execution.get("task"), "当前任务")
    run = _require_dict(execution.get("run"), "当前运行")
    controls = _require_dict(execution.get("controls"), "当前控制条件")
    module_rows = [
        _require_dict(row, "模块登记项")
        for row in _require_list(modules.get("modules"), "模块登记")
    ]
    route_rows = [
        _require_dict(row, "路线登记项")
        for row in _require_list(routes.get("routes"), "路线登记")
    ]
    direction = execution.get("product_direction")
    if isinstance(direction, dict):
        product_direction: dict[str, Any] = {
            "registration": "registered_in_current_state",
            "value": direction,
        }
    else:
        product_direction = {
            "registration": "not_registered_as_current_state_field",
            "message": (
                "当前机器状态没有单独登记产品方向；目录不会从聊天、TEMP 或仓外现场猜测。"
            ),
        }
    return {
        "snapshot_at": current.get("snapshot_at"),
        "current_execution": {
            "task_id": task.get("task_id"),
            "label": task.get("label"),
            "status": task.get("status"),
            "status_label": task.get("status_label"),
            "run_id": run.get("run_id"),
            "run_status": run.get("status_label"),
            "next_action": controls.get("next_action"),
            "stop_rule": controls.get("stop_rule"),
            "blockers": execution.get("blockers", []),
        },
        "product_direction": product_direction,
        "modules": {
            "total": len(module_rows),
            "status_counts": _status_counts(module_rows),
            "items": [
                {
                    "module_id": row.get("module_id"),
                    "name": row.get("name"),
                    "version": row.get("version"),
                    "status": row.get("status"),
                    "consumers": row.get("consumers", []),
                    "limitations": row.get("limitations", []),
                }
                for row in module_rows
            ],
        },
        "routes": {
            "total": len(route_rows),
            "status_counts": _status_counts(route_rows),
            "items": [
                {
                    "route_id": row.get("route_id"),
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "status_label": row.get("status_label"),
                    "current_run_gate": row.get("current_run_gate"),
                    "reopen_requires": row.get("reopen_requires"),
                }
                for row in route_rows
            ],
        },
        "boundary": (
            "这里显示的是 CURRENT_STATE 当前执行镜像及登记摘要，不替代 Notion 拍板，"
            "也不把候选或受保护现场晋升为现役。"
        ),
    }


def _build_models(reader: SourceReader) -> dict[str, Any]:
    registry = reader.fixed_json(MODEL_PROFILE_REGISTRY_PATH)
    profiles = [
        _require_dict(row, "模型调用档")
        for row in _require_list(registry.get("profiles"), "模型调用档登记")
    ]
    bundles = [
        _require_dict(row, "模型组装包")
        for row in _require_list(registry.get("rule_bundles"), "模型组装包登记")
    ]
    preferred = _require_dict(registry.get("preferred_profiles"), "推荐候选档")
    preferred_for: dict[str, list[str]] = {}
    for model_name, profile_id in preferred.items():
        preferred_for.setdefault(str(profile_id), []).append(str(model_name))
    bundle_by_profile: dict[str, list[dict[str, Any]]] = {}
    for bundle in bundles:
        bundle_by_profile.setdefault(str(bundle.get("profile_id")), []).append(bundle)
    return {
        "registry_status": registry.get("status"),
        "catalog_may_define_default_chain": False,
        "online_or_credential_check": "not_performed",
        "automatic_retries": registry.get("automatic_retries"),
        "default_temperature": registry.get("default_temperature"),
        "default_output_token_policy": registry.get("default_output_token_policy"),
        "preferred_candidate_profiles": preferred,
        "profiles": [
            {
                "profile_id": row.get("profile_id"),
                "role": row.get("role"),
                "preferred_for": sorted(preferred_for.get(str(row.get("profile_id")), [])),
                "assembly_status": (
                    "registered"
                    if bundle_by_profile.get(str(row.get("profile_id")))
                    else "not_registered"
                ),
                "rule_bundle_ids": sorted(
                    str(bundle.get("bundle_id"))
                    for bundle in bundle_by_profile.get(str(row.get("profile_id")), [])
                ),
            }
            for row in profiles
        ],
        "rule_bundles": [
            {
                "bundle_id": row.get("bundle_id"),
                "profile_id": row.get("profile_id"),
                "status": row.get("status"),
                "materialize_item_count": len(
                    _require_list(row.get("materialize_items"), "组装零件")
                ),
            }
            for row in bundles
        ],
        "boundary": (
            "本页只照读登记册状态，无权把任何调用档升级成默认；登记了调用档也不"
            "等于 API 在线或钥匙存在。只有明确关联 rule bundle 的调用档才算组装包"
            "已登记。"
        ),
    }


def _protected_rows(policy: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        _require_dict(row, "受保护对象")
        for row in _require_list(policy.get("protected_non_targets"), "受保护对象登记")
    ]
    return [
        row
        for row in rows
        if row.get("discovery_prohibited") is True
        and isinstance(row.get("subject_id"), str)
    ]


def _validate_result_card_path(relative: object, card_id: object) -> str:
    if (
        not isinstance(card_id, str)
        or SAFE_ID.fullmatch(card_id) is None
        or not isinstance(relative, str)
    ):
        raise CatalogError("结论卡编号或路径格式错误")
    path = _safe_relative_path(relative)
    historical = PurePosixPath(
        "config",
        "test_replay",
        "result_cards",
        card_id,
        "result_card.json",
    )
    experimental = (
        len(path.parts) == 3
        and path.parts[0] == "experiments"
        and path.parts[2] == "result_card.json"
        and SAFE_ID.fullmatch(path.parts[1]) is not None
    )
    if path != historical and not experimental:
        raise CatalogError("结论卡不在固定登记位置")
    return path.as_posix()


def _load_result_cards(
    reader: SourceReader,
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    protected_ids = {
        str(row["subject_id"]).casefold() for row in _protected_rows(policy)
    }
    cards: list[dict[str, Any]] = []
    blocked = 0
    policy_rows = [
        _require_dict(row, "取件卡")
        for row in _require_list(policy.get("cards"), "取件卡登记")
    ]
    for row in policy_rows:
        card_id = row.get("card_id")
        ref = _require_dict(row.get("result_card_ref"), "结论卡引用")
        relative = ref.get("path")
        protected_reference = (
            isinstance(card_id, str) and card_id.casefold() in protected_ids
        ) or (
            isinstance(relative, str)
            and any(subject_id in relative.casefold() for subject_id in protected_ids)
        )
        if protected_reference:
            blocked += 1
            continue
        validated = _validate_result_card_path(relative, card_id)
        card = reader.result_card_json(validated, str(card_id))
        expected_sha = ref.get("sha256")
        if (
            not isinstance(expected_sha, str)
            or len(expected_sha) != 64
            or reader.source_sha256(validated) != expected_sha
        ):
            raise CatalogError(f"结论卡 SHA 不匹配：{card_id}")
        if card.get("card_id") != card_id:
            raise CatalogError(f"结论卡编号与登记不一致：{card_id}")
        cards.append(
            {
                "card_id": card.get("card_id"),
                "experiment_id": card.get("experiment_id"),
                "title": card.get("title"),
                "terminal_status": card.get("terminal_status"),
                "quality_verdict": card.get("quality_verdict"),
                "purpose": card.get("purpose"),
                "short_conclusion": card.get("short_conclusion", []),
                "evidence_boundary": card.get("evidence_boundary"),
                "source_git_commit": card.get("source_git_commit"),
                "allowed_selection_ids": row.get("allowed_selection_ids", []),
            }
        )
    return cards, blocked


def _policy_card_is_protected(
    row: dict[str, Any],
    protected_ids: set[str],
) -> bool:
    card_id = row.get("card_id")
    ref = row.get("result_card_ref")
    relative = ref.get("path") if isinstance(ref, dict) else None
    return (
        isinstance(card_id, str) and card_id.casefold() in protected_ids
    ) or (
        isinstance(relative, str)
        and any(subject_id in relative.casefold() for subject_id in protected_ids)
    )


def _visible_objects(
    registry: dict[str, Any],
    protected_ids: set[str],
    *,
    experiment_only: bool,
) -> tuple[list[dict[str, Any]], int]:
    rows = [
        _require_dict(row, "仓外对象")
        for row in _require_list(registry.get("objects"), "仓外对象登记")
    ]
    visible: list[dict[str, Any]] = []
    excluded = 0
    for row in rows:
        artifact_id = str(row.get("artifact_id", ""))
        relative = str(row.get("relative_path", ""))
        if artifact_id.casefold() in protected_ids or any(
            protected_id in relative.casefold() for protected_id in protected_ids
        ):
            excluded += 1
            continue
        if experiment_only and row.get("category") not in {
            "repository_experiment",
            "isolated_experiment",
        }:
            continue
        visible.append(
            {
                "artifact_id": row.get("artifact_id"),
                "category": row.get("category"),
                "status": row.get("status"),
                "lifecycle": row.get("lifecycle"),
                "verification_level": row.get("verification_level"),
                "consumer_closure": row.get("consumer_closure"),
                "purpose_summary": row.get("purpose_summary"),
                "location": {
                    "root_id": row.get("root_id"),
                    "relative_path": row.get("relative_path"),
                },
                "consumers": row.get("consumers", []),
                "keep_in_repository": row.get("keep_in_repository", []),
                "externalize_later": row.get("externalize_later", []),
                "boundary": row.get("boundary"),
            }
        )
    return visible, excluded


def _build_experiments(reader: SourceReader) -> dict[str, Any]:
    registry = reader.fixed_json(EXTERNAL_ARCHIVE_REGISTRY_PATH)
    routes = reader.fixed_json(ROUTE_REGISTRY_PATH)
    policy = reader.fixed_json(ARTIFACT_RETRIEVAL_POLICY_PATH)
    protected = _protected_rows(policy)
    protected_ids = {str(row["subject_id"]).casefold() for row in protected}
    objects, excluded_objects = _visible_objects(
        registry,
        protected_ids,
        experiment_only=True,
    )
    cards, blocked_card_refs = _load_result_cards(reader, policy)
    route_rows = [
        _require_dict(row, "路线登记项")
        for row in _require_list(routes.get("routes"), "路线登记")
    ]
    return {
        "registered_experiment_objects": objects,
        "route_lifecycle": [
            {
                "route_id": row.get("route_id"),
                "name": row.get("name"),
                "status": row.get("status"),
                "status_label": row.get("status_label"),
                "current_run_gate": row.get("current_run_gate"),
                "reopen_requires": row.get("reopen_requires"),
            }
            for row in route_rows
        ],
        "result_cards": cards,
        "coverage": {
            "registered_experiment_object_count": len(objects),
            "registered_result_card_count": len(cards),
            "protected_object_excluded_count": excluded_objects,
            "blocked_protected_card_ref_count": blocked_card_refs,
            "directory_tree_scanned": False,
            "complete_experiment_ledger_claim": False,
        },
        "boundary": (
            "用途说明不冒充实验结论；只有显式结论卡才显示短结论。未登记不等于垃圾，"
            "本页也不会整树扫描 experiments、TEMP 或隔离实验目录补猜。"
        ),
    }


def _build_artifacts(reader: SourceReader) -> dict[str, Any]:
    registry = reader.fixed_json(EXTERNAL_ARCHIVE_REGISTRY_PATH)
    policy = reader.fixed_json(ARTIFACT_RETRIEVAL_POLICY_PATH)
    protected = _protected_rows(policy)
    protected_ids = {str(row["subject_id"]).casefold() for row in protected}
    objects, excluded_objects = _visible_objects(
        registry,
        protected_ids,
        experiment_only=False,
    )
    policy_cards = [
        _require_dict(row, "取件卡")
        for row in _require_list(policy.get("cards"), "取件卡登记")
    ]
    visible_cards = [
        {
            "card_id": row.get("card_id"),
            "allowed_selection_ids": row.get("allowed_selection_ids", []),
        }
        for row in policy_cards
        if not _policy_card_is_protected(row, protected_ids)
    ]
    blocked_cards = len(policy_cards) - len(visible_cards)
    roots = [
        _require_dict(row, "仓外根")
        for row in _require_list(registry.get("storage_roots"), "仓外根登记")
    ]
    conflicts = [
        _require_dict(row, "仓外冲突")
        for row in _require_list(registry.get("known_conflicts"), "仓外冲突登记")
    ]
    return {
        "storage_roots": [
            {
                "root_id": row.get("root_id"),
                "role": row.get("role"),
                "required": row.get("required"),
                "failure_domain": row.get("failure_domain"),
                "boundary": row.get("boundary"),
            }
            for row in roots
        ],
        "objects": objects,
        "retrieval_cards": visible_cards,
        "protected_non_targets": [
            {
                "subject_id": row.get("subject_id"),
                "reason": row.get("reason"),
                "discovery_prohibited": True,
            }
            for row in protected
        ],
        "coverage": {
            "registered_object_count": len(objects),
            "retrieval_card_count": len(visible_cards),
            "protected_object_excluded_count": excluded_objects,
            "blocked_protected_card_ref_count": blocked_cards,
            "external_payload_read": False,
            "absolute_external_paths_exposed": False,
        },
        "known_open_conflicts": [
            {
                "conflict_id": row.get("conflict_id"),
                "severity": row.get("severity"),
                "summary": row.get("summary"),
                "boundary": row.get("boundary"),
            }
            for row in conflicts
            if row.get("status") == "open"
        ],
        "boundary": (
            "位置只显示根编号加相对路径。登记对象不自动等于可恢复；只有显式取件卡"
            "可以进入后续计划，且本页本身不复制、移动、删除或读取 payload。"
        ),
    }


def _prefix_summary(entries: list[dict[str, Any]], prefix: str) -> dict[str, int]:
    selected = [
        row
        for row in entries
        if str(row["path"]) == prefix
        or str(row["path"]).startswith(f"{prefix}/")
    ]
    return {
        "tracked_path_count": len(selected),
        "tracked_bytes": sum(int(row["bytes"]) for row in selected),
    }


def _scanner_protected_reference_count(
    registry: dict[str, Any],
    protected_ids: set[str],
) -> int:
    """Inspect registry strings that the slim scanner can resolve as paths."""

    references: list[object] = []
    size_policy = registry.get("size_policy")
    if isinstance(size_policy, dict):
        receipt = size_policy.get("activation_receipt")
        if isinstance(receipt, dict):
            references.append(receipt.get("path"))
    for root in _require_list(registry.get("storage_roots"), "仓外根登记"):
        root_row = _require_dict(root, "仓外根")
        locator = root_row.get("locator")
        if isinstance(locator, dict):
            references.append(locator.get("suffix"))
    for row in _require_list(registry.get("objects"), "仓外对象登记"):
        object_row = _require_dict(row, "仓外对象")
        references.extend(
            [
                object_row.get("artifact_id"),
                object_row.get("relative_path"),
            ]
        )
        for anchor in _require_list(
            object_row.get("identity_anchors"),
            "对象身份锚",
        ):
            anchor_row = _require_dict(anchor, "对象身份锚")
            references.append(anchor_row.get("relative_path"))
        manifest = object_row.get("manifest")
        if isinstance(manifest, dict):
            references.append(manifest.get("relative_path"))
    return sum(
        1
        for value in references
        if isinstance(value, str)
        and any(protected_id in value.casefold() for protected_id in protected_ids)
    )


def _build_slim(reader: SourceReader) -> dict[str, Any]:
    registry = reader.fixed_json(EXTERNAL_ARCHIVE_REGISTRY_PATH)
    policy = reader.fixed_json(ARTIFACT_RETRIEVAL_POLICY_PATH)
    protected_ids = {
        str(row["subject_id"]).casefold() for row in _protected_rows(policy)
    }
    protected_reference_count = _scanner_protected_reference_count(
        registry,
        protected_ids,
    )
    if protected_reference_count:
        return {
            "available": False,
            "error": {
                "code": "PROTECTED_NON_TARGET_REGISTERED",
                "message": (
                    "仓外登记含受保护非目标；已在启动扫描器前停止，未探测对象路径。"
                ),
            },
            "protected_reference_excluded_count": protected_reference_count,
            "stale_pass_fallback_used": False,
            "boundary": "受保护对象与瘦身扫描范围冲突，本页硬停且不读取旧缓存。",
        }
    tool_registry = reader.fixed_json(TOOL_REGISTRY_PATH)
    try:
        report, details = scan_with_git_index_details(reader.repo_root)
    except InventoryError as exc:
        return {
            "available": False,
            "error": {
                "code": exc.code,
                "message": "原扫描器返回错误；目录没有使用旧缓存补答案。",
            },
            "stale_pass_fallback_used": False,
            "boundary": "原扫描器失败，本页不拿旧数字冒充当前 PASS。",
        }

    entries = [
        _require_dict(row, "Git 索引体积项")
        for row in _require_list(details.get("entries"), "Git 索引体积项")
    ]
    top_level: dict[str, dict[str, int]] = {}
    by_path = {str(row["path"]): int(row["bytes"]) for row in entries}
    for row in entries:
        path = str(row["path"])
        group = path.split("/", 1)[0] if "/" in path else "(root)"
        summary = top_level.setdefault(
            group,
            {"tracked_path_count": 0, "tracked_bytes": 0},
        )
        summary["tracked_path_count"] += 1
        summary["tracked_bytes"] += int(row["bytes"])
    top_level_rows = [
        {
            "path": path,
            **summary,
        }
        for path, summary in top_level.items()
    ]
    top_level_rows.sort(key=lambda row: (-row["tracked_bytes"], row["path"]))

    tool_rows = [
        _require_dict(row, "工具登记项")
        for row in _require_list(tool_registry.get("tools"), "工具登记")
    ]
    historical_paths = sorted(
        str(row.get("path"))
        for row in tool_rows
        if row.get("status") == "historical_replay_only"
        and isinstance(row.get("path"), str)
    )
    historical_tool_bytes = sum(by_path.get(path, 0) for path in historical_paths)
    inventory = _require_dict(report.get("git_inventory"), "瘦身体积报告")
    conflicts = _require_dict(report.get("conflicts"), "瘦身冲突报告")
    return {
        "available": True,
        "status": report.get("status"),
        "claim": report.get("claim"),
        "tracked_path_count": inventory.get("tracked_path_count"),
        "tracked_bytes": inventory.get("tracked_bytes"),
        "active_limit_bytes": inventory.get("active_limit_bytes"),
        "active_gate": inventory.get("active_gate"),
        "active_gate_passed": inventory.get("active_gate_passed"),
        "target_bytes": inventory.get("target_bytes"),
        "target_met": inventory.get("target_met"),
        "bytes_to_target": max(
            0,
            int(inventory.get("tracked_bytes", 0))
            - int(inventory.get("target_bytes", 0)),
        ),
        "top_level": top_level_rows,
        "large_known_groups": {
            "experiments/model_benchmarks": _prefix_summary(
                entries,
                "experiments/model_benchmarks",
            ),
            "tests": _prefix_summary(entries, "tests"),
            "historical_replay_only_tools": {
                "registered_tool_count": len(historical_paths),
                "tracked_bytes": historical_tool_bytes,
            },
        },
        "known_open_conflict_ids": conflicts.get("known_open_ids", []),
        "blockers": report.get("blockers", []),
        "boundary": (
            "当前无增长闸通过不等于 10MB 目标达成；这里仍只做库存测量，"
            "没有移动、删除、迁移或证明独立备份。"
        ),
    }


def _build_view_data(reader: SourceReader, view: str) -> dict[str, Any]:
    if view == "menu":
        return MENU
    if view == "status":
        return _build_status(reader)
    if view == "models":
        return _build_models(reader)
    if view == "experiments":
        return _build_experiments(reader)
    if view == "artifacts":
        return _build_artifacts(reader)
    if view == "slim":
        return _build_slim(reader)
    if view == "all":
        return {
            "menu": MENU,
            "status": _build_status(reader),
            "models": _build_models(reader),
            "experiments": _build_experiments(reader),
            "artifacts": _build_artifacts(reader),
            "slim": _build_slim(reader),
        }
    raise CatalogError(f"未知目录视图：{view}")


def build_catalog(repo_root: Path, view: str) -> dict[str, Any]:
    if view not in VIEWS:
        raise CatalogError(f"未知目录视图：{view}")
    reader = SourceReader(repo_root)
    data = _build_view_data(reader, view)
    return {
        "catalog_version": CATALOG_VERSION,
        "view": view,
        "authority": dict(AUTHORITY),
        "sources": reader.sources(),
        "data": data,
    }


def _render_human(catalog: dict[str, Any]) -> str:
    view = str(catalog["view"])
    data = _require_dict(catalog["data"], "目录数据")
    if view == "menu":
        lines = ["仓库统一目录（只读导航，不是第二份总账）", ""]
        for row in data["commands"]:
            lines.append(f"- {row['task']}：{row['command']}")
        lines.extend(
            [
                "",
                "边界：不复制、不移动、不删除、不联网，不读取受保护运行现场。",
            ]
        )
        return "\n".join(lines)
    if view == "status":
        task = data["current_execution"]
        direction = data["product_direction"]
        direction_label = (
            "已在当前状态登记"
            if direction["registration"] == "registered_in_current_state"
            else "当前状态没有单独登记，不从现场猜"
        )
        return "\n".join(
            [
                f"当前执行镜像：{task['label']}",
                f"镜像时间：{data['snapshot_at']}",
                f"运行状态：{task['run_status']}",
                f"产品方向登记：{direction_label}",
                (
                    f"模块：{data['modules']['total']} 项；"
                    f"路线：{data['routes']['total']} 条。"
                ),
                f"边界：{data['boundary']}",
            ]
        )
    if view == "models":
        registry_label = (
            "候选，尚未接入默认链"
            if data["registry_status"] == "candidate_only_not_wired_to_default_chain"
            else str(data["registry_status"])
        )
        profile_count = len(data["profiles"])
        bundled_count = sum(
            row["assembly_status"] == "registered" for row in data["profiles"]
        )
        return "\n".join(
            [
                f"模型调用档：{profile_count} 个。",
                f"已登记规则组装包：{len(data['rule_bundles'])} 个。",
                f"已有组装包的调用档：{bundled_count} 个；其余 {profile_count - bundled_count} 个未登记完整包。",
                f"登记状态：{registry_label}",
                f"边界：{data['boundary']}",
            ]
        )
    if view == "experiments":
        coverage = data["coverage"]
        return "\n".join(
            [
                (
                    "已登记实验对象："
                    f"{coverage['registered_experiment_object_count']} 个。"
                ),
                f"可读轻量结论卡：{coverage['registered_result_card_count']} 张。",
                f"路线登记：{len(data['route_lifecycle'])} 条。",
                f"边界：{data['boundary']}",
            ]
        )
    if view == "artifacts":
        coverage = data["coverage"]
        return "\n".join(
            [
                f"已登记对象：{coverage['registered_object_count']} 个。",
                f"显式取件卡：{coverage['retrieval_card_count']} 张。",
                f"开放矛盾：{len(data['known_open_conflicts'])} 项。",
                f"受保护排除：{len(data['protected_non_targets'])} 项。",
                f"边界：{data['boundary']}",
            ]
        )
    if view == "slim":
        if data.get("available") is not True:
            error = data.get("error", {})
            return f"瘦身实时状态不可用：{error.get('code', 'UNKNOWN')}"
        return "\n".join(
            [
                (
                    f"Git 跟踪体积：{data['tracked_bytes']} 字节，"
                    f"{data['tracked_path_count']} 个路径。"
                ),
                (
                    "当前无增长闸："
                    f"{'通过' if data['active_gate_passed'] else '未通过'}。"
                ),
                f"10MB 目标：{'已达到' if data['target_met'] else '尚未达到'}。",
                f"距目标还需减少：{data['bytes_to_target']} 字节。",
                f"边界：{data['boundary']}",
            ]
        )
    if view == "all":
        status = data["status"]["current_execution"]
        slim = data["slim"]
        slim_line = (
            f"{slim['tracked_bytes']} 字节，10MB "
            f"{'已达到' if slim['target_met'] else '尚未达到'}"
            if slim.get("available") is True
            else "实时扫描不可用"
        )
        return "\n".join(
            [
                "仓库统一目录（完整只读摘要）",
                f"当前执行镜像：{status['label']}",
                f"模型调用档：{len(data['models']['profiles'])} 个",
                (
                    "实验对象／结论卡："
                    f"{data['experiments']['coverage']['registered_experiment_object_count']}"
                    "／"
                    f"{data['experiments']['coverage']['registered_result_card_count']}"
                ),
                f"仓外显式取件卡：{len(data['artifacts']['retrieval_cards'])} 张",
                f"Git 体积：{slim_line}",
                "要给其他 AI 看完整字段，请在命令末尾加 --json。",
            ]
        )
    raise CatalogError(f"未知目录视图：{view}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="novel_pipeline.py catalog",
        description="从现有真源即时生成只读仓库导航，不新建第二份总账。",
        allow_abbrev=False,
    )
    parser.add_argument(
        "view",
        nargs="?",
        choices=VIEWS,
        default="menu",
        help="menu/status/models/experiments/artifacts/slim/all",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="输出稳定 JSON，方便交给其他 AI 或脚本读取",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        catalog = build_catalog(ROOT, args.view)
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    if args.as_json:
        print(
            json.dumps(
                catalog,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(_render_human(catalog))
    if args.view in {"slim", "all"}:
        slim = catalog["data"] if args.view == "slim" else catalog["data"]["slim"]
        if slim.get("available") is not True:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
