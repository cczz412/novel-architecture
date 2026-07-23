"""从机器真源生成治理索引，不改历史运行工件。"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
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

    experiment_lines = [
        "# 试验专区索引",
        "",
        "新专项试验只写 `experiments/<experiment_id>/`。历史 `runs/`、`reports/` 原件不搬、不回写。",
        "",
        "## 当前登记",
        "",
        "| 试验 | 状态 | 位置 | 说明 |",
        "|---|---|---|---|",
    ]
    experiment_dirs = sorted((root / "experiments").glob("*/experiment.json")) if (root / "experiments").is_dir() else []
    for path in experiment_dirs:
        if path.parent.name.startswith("_"):
            continue
        data = read_json(path)
        experiment_lines.append(
            f"| {data.get('experiment_id')} | {data.get('status')} | `{path.parent.relative_to(root).as_posix()}` | {data.get('summary', '')} |"
        )
    if len(experiment_lines) == 8:
        experiment_lines.append("| 暂无新制试验 | — | — | 旧候选见银标索引；不做搬迁 |")
    experiment_lines.extend(["", "来源：Codex", ""])

    return {
        "governance/INDEX.md": index,
        "governance/current_run.md": current,
        "governance/indexes/gold_current.md": gold_page,
        "governance/indexes/silver_candidates.md": "\n".join(silver_lines),
        "governance/indexes/runs_and_reports.md": "\n".join(runs_lines),
        "governance/indexes/source_registry.md": "\n".join(source_lines),
        "governance/indexes/route_health.md": route_page,
        "experiments/INDEX.md": "\n".join(experiment_lines),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成小说流水线治理索引")
    parser.add_argument("--check", action="store_true", help="在临时目录生成并与当前索引逐字比较")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.check:
        manifest = refresh()
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    import tempfile

    with tempfile.TemporaryDirectory(prefix="governance-index-check-") as temporary:
        output_root = Path(temporary)
        refresh(output_root=output_root)
        mismatches = [
            relative
            for relative in GENERATED_PATHS + ["governance/index_manifest.json"]
            if not (ROOT / relative).is_file()
            or (ROOT / relative).read_bytes() != (output_root / relative).read_bytes()
        ]
    result = {"passed": not mismatches, "mismatches": mismatches}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
