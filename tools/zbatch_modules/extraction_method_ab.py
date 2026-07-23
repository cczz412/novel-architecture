"""第37道两臂提取对照的机械准备、一次性调用闸与停点判定。

本模块不接默认流水线。A 臂只增加按连续证据段检查的组织方式；B 臂只把
Z00x4 机械诊断的候选段注入动态载荷。两臂都沿用 ``z-event-v1`` 三字段合同。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from . import (
    api_transport,
    candidate_envelope,
    evidence_catalog,
    neutral_extract,
    prompt_render_pin,
    stage_sampling,
)
from .errors import ZBatchError


SCHEMA_VERSION = "z-extraction-method-arm-v1"
PREFLIGHT_SCHEMA = "z-extraction-method-preflight-v1"
PERMIT_SCHEMA = "z-extraction-method-one-time-permit-v1"
RESULT_SCHEMA = "z-extraction-method-result-v1"
COMPARISON_SCHEMA = "z-extraction-method-comparison-v1"
EXPECTED_CHAPTERS = [3, 4, 5, 13, 19]
EXPECTED_MODEL = "deepseek-v4-flash"
EXPECTED_TRANSPORT = {
    "model": EXPECTED_MODEL,
    "temperature": 0.2,
    "max_tokens": 16000,
    "n": 1,
    "reasoning_effort": "medium",
    "response_format": {"type": "json_object"},
    "logical_samples": 5,
    "max_network_attempts": 15,
}
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
ANCHOR_ID = re.compile(r"^E(?P<number>\d{4})$")
CANDIDATE_ID = re.compile(r"^COV-C\d{4}-\d{3}$")
STRONG_EVENT_SCHEMA_VERSION = "z-event-strong-segment-v1"
STRONG_ROOT_KEYS = {"schema_version", "chapter", "events", "segment_decisions"}
SEGMENT_DECISION_KEYS = {"segment_id", "status", "event_ids", "reason"}
CHAPTER_STATUS_COMPLETED = "正式完成"
CHAPTER_STATUS_FAILED = "已调用失败"
CHAPTER_STATUS_NOT_CALLED = "未调用"
Z57_TRUSTED_SUCCESSOR = {
    "active_registry_sha256": "b23b5cce26b9cfe584dd97dbff6422efa2b22ccd5cba38c6ed6a44c4543bc0a1",
    "active_marker_sha256": "0c8f0024f3ddbb0be992883d2ba79789a4b50b7e003761c26aaea3692ba448de",
    "predecessor_registry_sha256": "61bc6ca45fe450d382995b29dd998c9119ade2db6049d29963c83eee30c5f9da",
    "predecessor_marker_sha256": "9259d3958e97aed982a798545ae889e3c608a3c8ef12dad87ea9f18f9cdddc48",
    "revision_schema": "zbatch-default-compatibility-revision-v1",
    "revision_id": "Z57-stable-semantic-identity-v1",
    "authority": "第57道；CZ 2026-07-19 19:41拍a",
    "activated_at": "2026-07-19T19:41:00+08:00",
    "semantic_rules_sha256": "514eb54735b2fe6de83824c10e63ec1134fcdbbe5b92fd6cd8c496ee9e78e433",
    "old_contract": {
        "path": "config/contracts/classify_rules_v1.2.json",
        "sha256": "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de",
    },
    "new_contract": {
        "path": "config/contracts/classify_rules_v1.2_semantic_identity_v1.json",
        "sha256": "45f7610b86d5962e0d3d9d4d95886aad9022f1beaece200c2452b9a361f6c108",
    },
    "classify_rules_module": {
        "path": "tools/zbatch_modules/classify_rules.py",
        "sha256": "eed588211111f89f5c6968c490686124bf94e7cd09d65aee3f1bc02dd9011104",
    },
    "runner": {
        "path": "tools/zbatch.py",
        "sha256": "160c28b3ef0210fd05c392f713534cf1ffdf041fa596ec790545b64955280850",
    },
    "predecessor_classify_rules_module_sha256": "76b3c1e208abaf0ab47c8dafee4c4e1ccb7d6d4cb3d364fc30afa00c6179eb7b",
    "predecessor_runner_sha256": "4090169dd53a71badd21d42d3c1c1e8809bd54ac46f461ab3e33137e94c3ca11",
    "validation_fixture": {
        "decisions_path": "work/zbatch_decisions/Z57_X01_ch1_20_main_control_decisions_v1.2.json",
        "decisions_sha256": "ba856a487e6fcc416c83b05a0b9e6c458ea85f5d8a7e23354f8c2865b8e97650",
        "source_extract_path": "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719/01_extract",
        "event_total": 233,
        "gate_failures": [],
    },
    "rollback": {
        "default_registry_archive": "config/defaults/history/zbatch_v1.2_full_chain_61bc6ca45fe450d382995b29dd998c9119ade2db6049d29963c83eee30c5f9da.json",
        "commit_marker_archive": "config/defaults/history/zbatch_v1.2_full_chain.COMMITTED_9259d3958e97aed982a798545ae889e3c608a3c8ef12dad87ea9f18f9cdddc48.json",
        "old_contract_path": "config/contracts/classify_rules_v1.2.json",
        "old_runner_pinned_path": "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/provenance/runner_zbatch.py",
        "old_classify_module_pinned_path": "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/provenance/pinned/tools/zbatch_modules/classify_rules.py",
    },
    "frozen_outbox": {
        "mode": "historical_promotion_snapshot_no_rewrite",
        "manifest_path": "outbox/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/manifest.json",
        "manifest_sha256": "aecfcf93a265fa5f9f61ee7003bf8f7118833a12b8e2a0ffcc4899631cec6aa2",
    },
}


class ExtractionMethodError(ZBatchError):
    """第37道准备、许可、调用或判定失败。"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionMethodError(f"JSON 读取失败：{path}：{exc}") from exc
    if not isinstance(value, dict):
        raise ExtractionMethodError(f"JSON 顶层不是对象：{path}")
    return value


def usage_totals(run_dir: Path, *, strict: bool = True) -> dict[str, int]:
    """只读汇总运输用量账；外层恢复可保留坏账告警而不丢硬停回执。"""

    totals = {
        "usage_row_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cached_tokens": 0,
        "invalid_usage_row_count": 0,
    }
    usage_path = run_dir / "usage.jsonl"
    if not usage_path.is_file():
        return totals
    for line_number, line in enumerate(
        usage_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            if strict:
                raise ExtractionMethodError(
                    f"usage.jsonl 第 {line_number} 行不是合法 JSON"
                ) from exc
            totals["invalid_usage_row_count"] += 1
            continue
        usage = row.get("usage") if isinstance(row, dict) else None
        if not isinstance(usage, dict):
            if strict:
                raise ExtractionMethodError(f"usage.jsonl 第 {line_number} 行缺 usage 对象")
            totals["invalid_usage_row_count"] += 1
            continue
        completion_details = usage.get("completion_tokens_details")
        prompt_details = usage.get("prompt_tokens_details")
        totals["usage_row_count"] += 1
        totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        totals["total_tokens"] += int(usage.get("total_tokens") or 0)
        if isinstance(completion_details, dict):
            totals["reasoning_tokens"] += int(
                completion_details.get("reasoning_tokens") or 0
            )
        if isinstance(prompt_details, dict):
            totals["cached_tokens"] += int(prompt_details.get("cached_tokens") or 0)
    return totals


def chapter_status_rows(
    completed_chapters: Iterable[int], failed_chapters: Iterable[int]
) -> list[dict[str, Any]]:
    """把每章压成一个互斥状态，禁止失败章再次落入未调用。"""

    completed = {int(chapter) for chapter in completed_chapters}
    failed = {int(chapter) for chapter in failed_chapters}
    if completed & failed:
        raise ExtractionMethodError("章节不能同时标为正式完成和已调用失败")
    unexpected = (completed | failed) - set(EXPECTED_CHAPTERS)
    if unexpected:
        raise ExtractionMethodError(f"章节状态包含计划外章节：{sorted(unexpected)}")
    rows = []
    for chapter in EXPECTED_CHAPTERS:
        if chapter in completed:
            status = CHAPTER_STATUS_COMPLETED
        elif chapter in failed:
            status = CHAPTER_STATUS_FAILED
        else:
            status = CHAPTER_STATUS_NOT_CALLED
        rows.append({"chapter": chapter, "status": status})
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_json_bytes(data))
    temporary.replace(path)


def _repo_path(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ExtractionMethodError(f"路径越出仓库：{path}") from exc
    return path


def _relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def resolve_scoped_output(root: Path, value: str, allowed_dir: str) -> Path:
    """命令输出只能落到本命令的仓内目录，拒绝 outbox 与关键工件覆盖。"""

    raw = Path(value)
    if raw.is_absolute():
        raise ExtractionMethodError("--output 不接受绝对路径")
    output = _repo_path(root, value)
    allowed = _repo_path(root, allowed_dir)
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise ExtractionMethodError(f"--output 只能写入 {allowed_dir}") from exc
    if output.suffix.lower() != ".json":
        raise ExtractionMethodError("--output 只接受 .json 回执")
    return output


def validate_artifact_paths(config: dict[str, Any], root: Path) -> dict[str, str]:
    """把配置派生的主工件限定在各自目录；必须在任何写入或调用前执行。"""

    arm = str(config.get("arm") or "")
    expected_batches = {
        "A": {"Z01b"},
        "B": {"Z01c"},
        "C": {"Z01e"},
        "D": {"Z01d", "Z01f"},
    }.get(arm, set())
    batch_id = str(config.get("batch_id") or "")
    if batch_id not in expected_batches:
        expected_text = "／".join(sorted(expected_batches)) or "无合法值"
        raise ExtractionMethodError(f"{arm or '未知'} 臂 batch_id 必须是 {expected_text}")
    run_id = str(config.get("run_id") or "")
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ExtractionMethodError("run_id 必须是 runs/ 下的单个安全目录名")
    run_dir = _repo_path(root, f"runs/{run_id}")
    runs_root = _repo_path(root, "runs")
    if run_dir.parent != runs_root:
        raise ExtractionMethodError("运行工件只能落在 runs/ 的直属目录")
    permit = _repo_path(root, str(config.get("permit_path") or ""))
    permit_root = _repo_path(root, "work/zbatch_ab/permits")
    if permit.parent != permit_root or permit.suffix != ".json":
        raise ExtractionMethodError("调用证只能落在 work/zbatch_ab/permits/ 的直属 JSON 文件")
    preflight = _repo_path(root, f"work/zbatch_ab/preflight/{batch_id}.json")
    rejection = _repo_path(root, f"work/zbatch_ab/rejections/{batch_id}.json")
    return {
        "run_dir": _relative(root, run_dir),
        "permit_path": _relative(root, permit),
        "preflight_path": _relative(root, preflight),
        "rejection_path": _relative(root, rejection),
    }


def _verify_ref(root: Path, ref: dict[str, Any], label: str) -> Path:
    path = _repo_path(root, str(ref.get("path") or ""))
    expected = str(ref.get("sha256") or "")
    actual = sha256_file(path) if path.is_file() else None
    if not expected or actual != expected:
        raise ExtractionMethodError(
            f"{label} SHA 漂移：expected={expected or 'missing'}, actual={actual}"
        )
    return path


def verify_compatible_default_refs(
    root: Path,
    registry_ref: dict[str, Any],
    marker_ref: dict[str, Any],
) -> dict[str, Any]:
    """验默认登记；只接受精确钉死值或第57道声明的等义直系后继。"""

    registry_path = _repo_path(root, str(registry_ref.get("path") or ""))
    marker_path = _repo_path(root, str(marker_ref.get("path") or ""))
    expected_registry_sha = str(registry_ref.get("sha256") or "")
    expected_marker_sha = str(marker_ref.get("sha256") or "")
    actual_registry_sha = sha256_file(registry_path) if registry_path.is_file() else None
    actual_marker_sha = sha256_file(marker_path) if marker_path.is_file() else None
    if not expected_registry_sha or not expected_marker_sha:
        raise ExtractionMethodError("默认登记或提交标记缺少固定 SHA")

    registry = read_json(registry_path)
    marker = read_json(marker_path)
    binding = marker.get("default_registry") or {}
    if (
        actual_registry_sha == expected_registry_sha
        and actual_marker_sha == expected_marker_sha
    ):
        return {
            "mode": "exact_pin",
            "registry_path": registry_path,
            "marker_path": marker_path,
            "registry": registry,
            "marker": marker,
            "actual_registry_sha256": actual_registry_sha,
            "actual_marker_sha256": actual_marker_sha,
            "requested_registry_sha256": expected_registry_sha,
            "requested_marker_sha256": expected_marker_sha,
        }

    revision = registry.get("compatibility_revision")
    if not isinstance(revision, dict):
        raise ExtractionMethodError(
            "v1.2默认登记 SHA 漂移且没有兼容修订声明："
            f"expected={expected_registry_sha}, actual={actual_registry_sha}"
        )
    rollback = revision.get("rollback") or {}
    registry_archive_value = str(rollback.get("default_registry_archive") or "")
    marker_archive_value = str(rollback.get("commit_marker_archive") or "")
    registry_archive = _repo_path(root, registry_archive_value)
    marker_archive = _repo_path(root, marker_archive_value)
    archive_registry_sha = sha256_file(registry_archive) if registry_archive.is_file() else None
    archive_marker_sha = sha256_file(marker_archive) if marker_archive.is_file() else None
    semantic_rule_sha = str(revision.get("semantic_rules_sha256") or "")
    active_rule_sha = str(
        ((registry.get("chain") or {}).get("classification_prompt") or {}).get("sha256")
        or ""
    )
    active_contract = (registry.get("chain") or {}).get("classify_contract") or {}
    revision_contract = revision.get("new_contract") or {}
    trusted = Z57_TRUSTED_SUCCESSOR
    trusted_old_contract = trusted["old_contract"]
    trusted_new_contract = trusted["new_contract"]
    trusted_module = trusted["classify_rules_module"]
    trusted_runner = trusted["runner"]
    revision_module = revision.get("classify_rules_module") or {}
    revision_runner = revision.get("runner") or {}
    validation_fixture = revision.get("validation_fixture") or {}
    chain = registry.get("chain") or {}
    checks = {
        "active_files_exist": actual_registry_sha is not None and actual_marker_sha is not None,
        "active_registry_exact": actual_registry_sha == trusted["active_registry_sha256"],
        "active_marker_exact": actual_marker_sha == trusted["active_marker_sha256"],
        "both_pins_advanced": (
            actual_registry_sha != expected_registry_sha
            and actual_marker_sha != expected_marker_sha
        ),
        "requested_predecessor_is_z57_source": (
            expected_registry_sha == trusted["predecessor_registry_sha256"]
            and expected_marker_sha == trusted["predecessor_marker_sha256"]
        ),
        "revision_schema_exact": revision.get("schema_version") == trusted["revision_schema"],
        "revision_id_exact": revision.get("revision_id") == trusted["revision_id"],
        "authority_exact": revision.get("authority") == trusted["authority"],
        "activation_time_exact": revision.get("activated_at") == trusted["activated_at"],
        "predecessor_registry_exact": (
            revision.get("predecessor_default_registry_sha256") == expected_registry_sha
        ),
        "predecessor_marker_exact": (
            revision.get("predecessor_commit_marker_sha256") == expected_marker_sha
        ),
        "rollback_registry_exact": archive_registry_sha == expected_registry_sha,
        "rollback_marker_exact": archive_marker_sha == expected_marker_sha,
        "semantic_rules_unchanged": revision.get("semantic_rules_changed") is False,
        "semantic_rule_sha_bound": (
            semantic_rule_sha == trusted["semantic_rules_sha256"]
            and active_rule_sha == trusted["semantic_rules_sha256"]
        ),
        "sequential_ids_run_local": revision.get("sequential_event_id_scope") == "run_local_only",
        "identity_carrier_named": bool(str(revision.get("identity_carrier") or "")),
        "old_contract_exact": (
            {key: (revision.get("old_contract") or {}).get(key) for key in ("path", "sha256")}
            == trusted_old_contract
            and sha256_file(_repo_path(root, trusted_old_contract["path"]))
            == trusted_old_contract["sha256"]
        ),
        "contract_revision_bound": (
            active_contract == trusted_new_contract
            and revision_contract == trusted_new_contract
            and sha256_file(_repo_path(root, trusted_new_contract["path"]))
            == trusted_new_contract["sha256"]
        ),
        "classify_module_exact": (
            chain.get("classify_rules_module") == trusted_module
            and {key: revision_module.get(key) for key in ("path", "sha256")} == trusted_module
            and sha256_file(_repo_path(root, trusted_module["path"])) == trusted_module["sha256"]
        ),
        "predecessor_classify_module_exact": (
            revision_module.get("predecessor_pinned_path")
            == trusted["rollback"]["old_classify_module_pinned_path"]
            and revision_module.get("predecessor_sha256")
            == trusted["predecessor_classify_rules_module_sha256"]
            and sha256_file(
                _repo_path(root, trusted["rollback"]["old_classify_module_pinned_path"])
            )
            == trusted["predecessor_classify_rules_module_sha256"]
        ),
        "runner_exact": (
            chain.get("runner") == trusted_runner
            and {key: revision_runner.get(key) for key in ("path", "sha256")} == trusted_runner
            and sha256_file(_repo_path(root, trusted_runner["path"])) == trusted_runner["sha256"]
        ),
        "predecessor_runner_exact": (
            revision_runner.get("predecessor_pinned_path")
            == trusted["rollback"]["old_runner_pinned_path"]
            and revision_runner.get("predecessor_sha256")
            == trusted["predecessor_runner_sha256"]
            and sha256_file(_repo_path(root, trusted["rollback"]["old_runner_pinned_path"]))
            == trusted["predecessor_runner_sha256"]
        ),
        "validation_fixture_exact": validation_fixture == trusted["validation_fixture"],
        "rollback_paths_exact": rollback == trusted["rollback"],
        "frozen_outbox_exact": revision.get("frozen_outbox") == trusted["frozen_outbox"],
        "marker_committed": marker.get("status") == "committed",
        "marker_binds_active_registry": (
            binding.get("path") == registry_ref.get("path")
            and binding.get("sha256") == actual_registry_sha
        ),
        "marker_binds_revision": (
            marker.get("compatibility_revision_id") == revision.get("revision_id")
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ExtractionMethodError(
            "v1.2默认登记不是受信的等义直系后继：" + "、".join(failed)
        )
    return {
        "mode": "compatible_successor",
        "registry_path": registry_path,
        "marker_path": marker_path,
        "registry": registry,
        "marker": marker,
        "actual_registry_sha256": actual_registry_sha,
        "actual_marker_sha256": actual_marker_sha,
        "requested_registry_sha256": expected_registry_sha,
        "requested_marker_sha256": expected_marker_sha,
        "revision_id": revision.get("revision_id"),
        "checks": checks,
        "rollback_registry_path": registry_archive_value,
        "rollback_marker_path": marker_archive_value,
    }


def _chapter_path(book_dir: Path, chapter: int) -> Path:
    matches = sorted((book_dir / "chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ExtractionMethodError(f"第 {chapter} 章正文文件数量异常：{len(matches)}")
    return matches[0]


def _source_run_path(root: Path, value: str) -> Path:
    relative = value if value.startswith("runs/") else f"runs/{value}"
    return _repo_path(root, relative)


def _anchor_number(anchor_id: str) -> int:
    match = ANCHOR_ID.fullmatch(anchor_id)
    if match is None:
        raise ExtractionMethodError(f"证据 ID 非法：{anchor_id}")
    return int(match.group("number"))


def build_segment_tasks(catalog: list[dict[str, Any]], *, segment_size: int) -> list[dict[str, Any]]:
    """把目录确定性切成连续、无遗漏、无重叠的段级子任务。"""

    if isinstance(segment_size, bool) or not isinstance(segment_size, int) or segment_size <= 0:
        raise ExtractionMethodError("segment_size 必须是正整数")
    anchor_ids = [str(row.get("anchor_id") or "") for row in catalog]
    if any(not ANCHOR_ID.fullmatch(value) for value in anchor_ids):
        raise ExtractionMethodError("证据目录含非法 ID")
    tasks: list[dict[str, Any]] = []
    for offset in range(0, len(anchor_ids), segment_size):
        selected = anchor_ids[offset : offset + segment_size]
        tasks.append(
            {
                "segment_id": f"SEG-{len(tasks) + 1:03d}",
                "start_anchor_id": selected[0],
                "end_anchor_id": selected[-1],
                "anchor_ids": selected,
            }
        )
    if [value for task in tasks for value in task["anchor_ids"]] != anchor_ids:
        raise ExtractionMethodError("段级子任务没有逐项覆盖证据目录")
    return tasks


def select_named_candidates(diagnostic: dict[str, Any], chapter: int) -> list[dict[str, Any]]:
    """只从机器 JSON 取同章候选；新诊断优先用冻结目录全覆盖段。"""

    rows = diagnostic.get("catalog_coverage_candidates")
    source_name = "catalog_coverage_candidates"
    if rows is None:
        rows = diagnostic.get("heuristic_candidates")
        source_name = "heuristic_candidates"
    if not isinstance(rows, list):
        raise ExtractionMethodError(f"覆盖诊断缺 {source_name}")
    selected = [row for row in rows if isinstance(row, dict) and row.get("chapter") == chapter]
    selected.sort(
        key=lambda row: (
            _anchor_number(str(row.get("start_anchor_id") or "")),
            str(row.get("candidate_id") or ""),
        )
    )
    compact: list[dict[str, Any]] = []
    for row in selected:
        anchor_ids = row.get("anchor_ids")
        if not isinstance(anchor_ids, list) or not anchor_ids:
            raise ExtractionMethodError(f"候选段 {row.get('candidate_id')} 没有 anchor_ids")
        clean_ids = [str(value) for value in anchor_ids]
        numbers = [_anchor_number(value) for value in clean_ids]
        expected_numbers = list(range(numbers[0], numbers[-1] + 1))
        if numbers != expected_numbers:
            raise ExtractionMethodError(f"候选段 {row.get('candidate_id')} 的证据 ID 不连续")
        if str(row.get("start_anchor_id") or "") != clean_ids[0]:
            raise ExtractionMethodError(f"候选段 {row.get('candidate_id')} 起点与列表不一致")
        if str(row.get("end_anchor_id") or "") != clean_ids[-1]:
            raise ExtractionMethodError(f"候选段 {row.get('candidate_id')} 终点与列表不一致")
        compact.append(
            {
                "candidate_id": str(row.get("candidate_id") or ""),
                "start_anchor_id": str(row.get("start_anchor_id") or ""),
                "end_anchor_id": str(row.get("end_anchor_id") or ""),
                "anchor_ids": clean_ids,
            }
        )
    if not compact:
        raise ExtractionMethodError(f"第 {chapter} 章没有程序候选段")
    candidate_ids = [row["candidate_id"] for row in compact]
    if (
        len(candidate_ids) != len(set(candidate_ids))
        or any(CANDIDATE_ID.fullmatch(value) is None for value in candidate_ids)
    ):
        raise ExtractionMethodError(f"第 {chapter} 章候选段编号为空或重复")
    return compact


def _remove_method_sections(text: str, arm: str) -> str:
    """去掉本轮唯一新增的固定块和动态块，供基线正文同序审计。"""

    fixed_heading = {
        "A": "【A 臂固定任务｜段级拆分】",
        "B": "【B 臂固定任务｜程序点名段】",
    }.get(arm)
    dynamic_heading = {
        "A": "程序生成的段级子任务清单：",
        "B": "Z00x4 程序候选段清单：",
    }.get(arm)
    if fixed_heading is None or dynamic_heading is None:
        raise ExtractionMethodError(f"{arm} 臂不走旧 Prompt 剥离审计")
    fixed_start = text.find(fixed_heading)
    fixed_end = text.find("每条必须满足：")
    if fixed_start < 0 or fixed_end <= fixed_start:
        raise ExtractionMethodError("新 Prompt 固定方法块边界异常")
    text = text[:fixed_start] + text[fixed_end:]
    dynamic_start = text.find(dynamic_heading)
    source_start = text.find("来源：Codex", dynamic_start)
    if dynamic_start < 0 or source_start <= dynamic_start:
        raise ExtractionMethodError("新 Prompt 动态方法块边界异常")
    text = text[:dynamic_start] + text[source_start:]
    lines = text.splitlines()
    lines[0] = "# Z00l 中性事件提取 Prompt v1.0"
    return "\n".join(lines).rstrip() + "\n"


def _remove_structure_map_block(text: str) -> str:
    """只去掉 Z01e 前置结构地图，供相对 v1.2 的单变量审计。"""

    heading = "【C 臂前置块｜产品结构地图】"
    next_baseline_line = "下方“冻结证据目录”按原文顺序覆盖当前章全文"
    block_start = text.find(heading)
    block_end = text.find(next_baseline_line, block_start)
    if block_start < 0 or block_end <= block_start:
        raise ExtractionMethodError("C 臂结构地图前置块边界异常")
    stripped = text[:block_start] + text[block_end:]
    return stripped.rstrip() + "\n"


def audit_prompt(config: dict[str, Any], root: Path) -> dict[str, Any]:
    prompt_path = _verify_ref(root, config["prompt"], "实验 Prompt")
    baseline_path = _verify_ref(root, config["baseline_prompt"], "默认 Prompt")
    prompt_text = prompt_path.read_text(encoding="utf-8")
    baseline_text = baseline_path.read_text(encoding="utf-8")
    arm = str(config.get("arm") or "")
    baseline_placeholders = PLACEHOLDER.findall(baseline_text)
    prompt_placeholders = PLACEHOLDER.findall(prompt_text)
    extra = "COVERAGE_CANDIDATES_JSON" if arm == "B" else "SEGMENT_TASKS_JSON"
    if arm == "C":
        stripped = _remove_structure_map_block(prompt_text)
        map_start = prompt_text.find("【C 臂前置块｜产品结构地图】")
        checks = {
            "baseline_body_preserved_in_order": stripped == baseline_text,
            "baseline_placeholder_order_preserved": prompt_placeholders
            == baseline_placeholders,
            "no_method_payload_placeholder_added": prompt_placeholders.count(
                "SEGMENT_TASKS_JSON"
            )
            == 0
            and prompt_placeholders.count("COVERAGE_CANDIDATES_JSON") == 0,
            "same_output_schema": '"schema_version": "z-event-v1"' in prompt_text
            and all(
                f'"{name}"' in prompt_text for name in ("event_id", "event", "anchors")
            ),
            "classification_still_forbidden": "不要输出 A／B／C／D" in prompt_text,
            "structure_map_precedes_dynamic_payload": 0
            <= map_start
            < prompt_text.find("{{CHAPTER_PADDED}}"),
            "structure_map_names_current_and_later_components": all(
                phrase in prompt_text
                for phrase in (
                    "原文与冻结证据目录",
                    "当前中性事件提取",
                    "下一阶段主控",
                    "跨章拼接",
                    "不要提前分类",
                )
            ),
        }
    elif arm == "D":
        strong_expected_placeholders = list(baseline_placeholders)
        strong_expected_placeholders.insert(2, "CHAPTER_PADDED")
        checks = {
            "baseline_instruction_core_preserved": all(
                phrase in prompt_text
                for phrase in (
                    "你只看当前一章，不得使用本章之后的知识",
                    "找出以后可能被继续读取的**原子事件**",
                    "分类由下一阶段主控统一处理",
                    "普通动作、气氛描写、无后续读取价值的场景复述不凑数",
                )
            ),
            "baseline_placeholder_order_preserved": prompt_placeholders[:-1]
            == strong_expected_placeholders,
            "one_method_payload_placeholder_added": prompt_placeholders[-1:]
            == [extra]
            and prompt_placeholders.count(extra) == 1,
            "strong_output_schema": (
                f'"schema_version": "{STRONG_EVENT_SCHEMA_VERSION}"' in prompt_text
                and '"segment_decisions"' in prompt_text
                and '"status": "none"' in prompt_text
                and "不得沉默跳段" in prompt_text
            ),
            "classification_still_forbidden": "不要输出 A／B／C／D" in prompt_text,
            "method_payload_after_catalog": prompt_text.find("{{EVIDENCE_CATALOG_JSON}}")
            < prompt_text.find("{{" + extra + "}}"),
        }
    else:
        stripped = _remove_method_sections(prompt_text, arm)
        checks = {
            "baseline_body_preserved_in_order": stripped == baseline_text,
            "baseline_placeholder_order_preserved": prompt_placeholders[:-1]
            == baseline_placeholders,
            "one_method_payload_placeholder_added": prompt_placeholders[-1:]
            == [extra]
            and prompt_placeholders.count(extra) == 1,
            "same_output_schema": '"schema_version": "z-event-v1"' in prompt_text
            and all(
                f'"{name}"' in prompt_text for name in ("event_id", "event", "anchors")
            ),
            "classification_still_forbidden": "不要输出 A／B／C／D" in prompt_text,
            "method_payload_after_catalog": prompt_text.find("{{EVIDENCE_CATALOG_JSON}}")
            < prompt_text.find("{{" + extra + "}}"),
        }
    if not all(checks.values()):
        raise ExtractionMethodError(f"Prompt 单变量审计失败：{checks}")
    first_dynamic = prompt_text.find("{{")
    return {
        "status": "pass",
        "arm": arm,
        "checks": checks,
        "baseline_prompt_sha256": config["baseline_prompt"]["sha256"],
        "experiment_prompt_sha256": config["prompt"]["sha256"],
        "placeholder_order": prompt_placeholders,
        "cache_layers": {
            "layer_1_system_sha256": sha256_bytes(neutral_extract.SYSTEM_MESSAGE.encode("utf-8")),
            "layer_2_fixed_task_prefix_sha256": sha256_bytes(
                prompt_text[:first_dynamic].encode("utf-8")
            ),
            "layer_2_fixed_task_prefix_bytes": len(prompt_text[:first_dynamic].encode("utf-8")),
            "layer_3_dynamic_payloads": prompt_placeholders,
            "claim_boundary": "只证明三层位置固定，不声称服务端缓存命中。",
        },
    }


def _method_rows(
    config: dict[str, Any],
    root: Path,
    chapter: int,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if config["arm"] in {"A", "C", "D"}:
        return build_segment_tasks(catalog, segment_size=int(config["segment_size"]))
    diagnostic_path = _verify_ref(root, config["coverage_diagnostic"], "Z00x4 诊断件")
    return select_named_candidates(read_json(diagnostic_path), chapter)


def build_messages(
    config: dict[str, Any], root: Path, chapter: int
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], Path]:
    book_dir = _repo_path(root, config["book_dir"])
    chapter_path = _chapter_path(book_dir, chapter)
    text = chapter_path.read_text(encoding="utf-8")
    catalog = evidence_catalog.build_evidence_catalog(chapter, text)
    if not catalog:
        raise ExtractionMethodError(f"第 {chapter} 章冻结目录为空")
    method_rows = _method_rows(config, root, chapter, catalog)
    prompt_path = _verify_ref(root, config["prompt"], "实验 Prompt")
    template = prompt_path.read_text(encoding="utf-8")
    values = {
        "CHAPTER_NUMBER": str(chapter),
        "CHAPTER_PADDED": f"{chapter:04d}",
        "CHAPTER_FILENAME": chapter_path.name,
        "EVIDENCE_CATALOG_JSON": json.dumps(catalog, ensure_ascii=False, separators=(",", ":")),
    }
    if config["arm"] in {"A", "D"}:
        values["SEGMENT_TASKS_JSON"] = json.dumps(
            method_rows, ensure_ascii=False, separators=(",", ":")
        )
    elif config["arm"] == "B":
        values["COVERAGE_CANDIDATES_JSON"] = json.dumps(
            method_rows, ensure_ascii=False, separators=(",", ":")
        )
    rendered = prompt_render_pin.render_prompt(template, values)
    built = {
        "messages": [
            {"role": "system", "content": neutral_extract.SYSTEM_MESSAGE},
            {"role": "user", "content": rendered},
        ],
        "template_sha256": config["prompt"]["sha256"],
        "rendered_prompt_sha256": sha256_bytes(rendered.encode("utf-8")),
        "catalog_sha256": sha256_bytes(values["EVIDENCE_CATALOG_JSON"].encode("utf-8")),
        "method_payload_sha256": sha256_bytes(
            json.dumps(method_rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ),
        "chapter_file_sha256": sha256_file(chapter_path),
    }
    return built, catalog, method_rows, chapter_path


def _contract_audit(config: dict[str, Any], root: Path) -> dict[str, Any]:
    contract_path = _verify_ref(root, config["stage_contract"], "阶段采样合同")
    _verify_ref(root, config["provider"], "运输路由")
    bundle = stage_sampling.load_contract_bundle(
        contract_path, profile=str(config["stage_contract"]["profile"])
    )
    route = api_transport.TransportRoute.from_mapping(bundle.route)
    contract = bundle.stage(str(config["stage_contract"]["stage"]))
    actual = {
        "model": route.model,
        "temperature": contract.temperature,
        "max_tokens": contract.max_tokens,
        "n": contract.n,
        "reasoning_effort": contract.reasoning_effort,
        "response_format": dict(contract.response_format),
        "logical_samples": int(config["transport"]["logical_samples"]),
        "max_network_attempts": int(config["transport"]["max_network_attempts"]),
    }
    if actual != EXPECTED_TRANSPORT or config["transport"] != EXPECTED_TRANSPORT:
        raise ExtractionMethodError(
            f"两臂运输参数不等于预写基线：actual={actual}, config={config['transport']}"
        )
    return {
        "status": "pass",
        "values": actual,
        "route_network_attempts_per_logical_sample": route.network_attempts,
        "maximum_reserved_attempts": EXPECTED_TRANSPORT["max_network_attempts"],
    }


def verify_default_activation(config: dict[str, Any], root: Path) -> dict[str, Any]:
    """Z01e 必须真的相对第36道落地后的 v1.2 默认链。"""

    refs = verify_compatible_default_refs(
        root,
        config["default_registry"],
        config["default_commit_marker"],
    )
    registry_path = refs["registry_path"]
    marker_path = refs["marker_path"]
    registry = refs["registry"]
    marker = refs["marker"]
    binding = marker.get("default_registry") or {}
    if registry.get("status") != "active" or registry.get("version") != "v1.2":
        raise ExtractionMethodError("v1.2默认登记未处于active状态")
    if (
        marker.get("status") != "committed"
        or binding.get("path") != config["default_registry"]["path"]
        or binding.get("sha256") != refs["actual_registry_sha256"]
    ):
        raise ExtractionMethodError("提交标记没有绑定当前v1.2默认登记")
    if registry.get("chain", {}).get("neutral_extract_prompt") != config.get(
        "baseline_prompt"
    ):
        raise ExtractionMethodError("Z01e基线 Prompt 不等于当前v1.2默认 Prompt")
    transport = registry.get("chain", {}).get("transport", {}).get("neutral_extract")
    if transport != {
        "temperature": 0.2,
        "max_tokens": 16000,
        "n": 1,
        "reasoning_effort": "medium",
    }:
        raise ExtractionMethodError("Z01e参照的v1.2默认运输参数漂移")
    return {
        "status": "pass",
        "default_id": registry.get("default_id"),
        "default_registry_sha256": sha256_file(registry_path),
        "commit_marker_sha256": sha256_file(marker_path),
        "pin_resolution": refs["mode"],
        "requested_predecessor_registry_sha256": refs["requested_registry_sha256"],
        "compatibility_revision_id": refs.get("revision_id"),
    }


def _targets_by_chapter(document: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = document.get("targets")
    if not isinstance(rows, list):
        raise ExtractionMethodError("靶点件缺 targets")
    result = {int(row["chapter"]): row for row in rows if isinstance(row, dict)}
    if sorted(result) != EXPECTED_CHAPTERS or len(rows) != len(EXPECTED_CHAPTERS):
        raise ExtractionMethodError("靶点件不是五章各一靶")
    return result


def _samples_by_chapter(document: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    rows = document.get("samples")
    if not isinstance(rows, list):
        raise ExtractionMethodError("旧事件抽查件缺 samples")
    result = {chapter: [] for chapter in EXPECTED_CHAPTERS}
    for row in rows:
        if not isinstance(row, dict) or row.get("chapter") not in result:
            raise ExtractionMethodError("旧事件抽查件含越界行")
        result[int(row["chapter"])].append(row)
    if any(len(value) != 2 for value in result.values()):
        raise ExtractionMethodError("旧事件抽查件不是每章两条")
    for chapter, selected in result.items():
        event_ids = [str(row.get("event_id") or "") for row in selected]
        if len(event_ids) != len(set(event_ids)) or any(not value for value in event_ids):
            raise ExtractionMethodError(f"第 {chapter} 章旧事件抽查 ID 为空或重复")
    return result


def verify_old_source_files(config: dict[str, Any], root: Path) -> dict[int, Path]:
    rows = config.get("old_event_samples", {}).get("source_files")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_CHAPTERS):
        raise ExtractionMethodError("旧事件真源 SHA 清单不是五章")
    result: dict[int, Path] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("chapter") not in EXPECTED_CHAPTERS:
            raise ExtractionMethodError("旧事件真源 SHA 清单含越界行")
        chapter = int(row["chapter"])
        if chapter in result:
            raise ExtractionMethodError(f"旧事件真源 SHA 清单重复第 {chapter} 章")
        result[chapter] = _verify_ref(root, row, f"第 {chapter} 章旧事件真源")
    if sorted(result) != EXPECTED_CHAPTERS:
        raise ExtractionMethodError("旧事件真源 SHA 清单缺章")
    return result


def preflight(config: dict[str, Any], root: Path, *, require_fresh_run: bool = True) -> dict[str, Any]:
    artifact_paths = validate_artifact_paths(config, root)
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ExtractionMethodError("实验配置 schema 错误")
    if config.get("arm") not in {"A", "B", "C", "D"}:
        raise ExtractionMethodError("实验配置 arm 只能是 A、B、C 或 D")
    if config.get("method") not in {
        "segment_tasks",
        "named_coverage_candidates",
        "structure_map_preface",
        "strong_segment_contract",
    }:
        raise ExtractionMethodError("实验方法名不受支持")
    if list(config.get("chapters") or []) != EXPECTED_CHAPTERS:
        raise ExtractionMethodError("试点章节必须固定为 3/4/5/13/19")
    if config["arm"] == "A" and config["method"] != "segment_tasks":
        raise ExtractionMethodError("A 臂方法登记不一致")
    if config["arm"] == "B" and config["method"] != "named_coverage_candidates":
        raise ExtractionMethodError("B 臂方法登记不一致")
    if config["arm"] == "C" and config["method"] != "structure_map_preface":
        raise ExtractionMethodError("C 臂方法登记不一致")
    if config["arm"] == "D" and config["method"] != "strong_segment_contract":
        raise ExtractionMethodError("D 臂方法登记不一致")

    prompt_audit = audit_prompt(config, root)
    contract_audit = _contract_audit(config, root)
    default_activation = (
        verify_default_activation(config, root) if config["arm"] == "C" else None
    )
    pins: list[dict[str, Any]] = []
    for group_name in ("protected_chain", "experiment_code"):
        for name, ref in config[group_name].items():
            path = _verify_ref(root, ref, f"{group_name}.{name}")
            pins.append({"label": f"{group_name}.{name}", "path": _relative(root, path), "sha256": ref["sha256"]})
    target_path = _verify_ref(root, config["targets"], "五章靶点")
    sample_path = _verify_ref(root, config["old_event_samples"], "旧事件抽查件")
    target_document = read_json(target_path)
    targets = _targets_by_chapter(target_document)
    samples = _samples_by_chapter(read_json(sample_path))
    source_run = _source_run_path(root, str(config["old_event_samples"]["source_run"]))
    source_files = verify_old_source_files(config, root)
    chapter_rows = []
    for chapter in EXPECTED_CHAPTERS:
        built, catalog, method_rows, chapter_path = build_messages(config, root, chapter)
        catalog_ids = [str(row["anchor_id"]) for row in catalog]
        flattened = [value for row in method_rows for value in row["anchor_ids"]]
        if config["arm"] in {"A", "C", "D"}:
            method_check = flattened == catalog_ids and len(flattened) == len(set(flattened))
        else:
            exact_keys = {"candidate_id", "start_anchor_id", "end_anchor_id", "anchor_ids"}
            payload_text = json.dumps(method_rows, ensure_ascii=False, separators=(",", ":"))
            forbidden_values = {
                str(value)
                for target in targets.values()
                for value in (
                    [target.get("id"), target.get("label")]
                    + list(target.get("required_quote_fragments") or [])
                )
                if value
            }
            method_check = (
                all(set(row) == exact_keys for row in method_rows)
                and all(set(row["anchor_ids"]).issubset(catalog_ids) for row in method_rows)
                and not any(value in payload_text for value in forbidden_values)
            )
        if not method_check:
            raise ExtractionMethodError(f"第 {chapter} 章方法载荷越界或覆盖异常")
        old_events_path = source_files[chapter]
        expected_old_path = source_run / "01_extract/events" / f"ch{chapter:04d}.json"
        if old_events_path != expected_old_path:
            raise ExtractionMethodError(f"第 {chapter} 章旧事件真源路径不等于登记来源目录")
        old_document = read_json(old_events_path)
        old_ids = {str(row.get("event_id")) for row in old_document.get("events") or [] if isinstance(row, dict)}
        expected_samples = {str(row["event_id"]) for row in samples[chapter]}
        if not expected_samples.issubset(old_ids):
            raise ExtractionMethodError(f"第 {chapter} 章旧事件抽查 ID 不存在")
        chapter_rows.append(
            {
                "chapter": chapter,
                "chapter_file": _relative(root, chapter_path),
                "chapter_file_sha256": built["chapter_file_sha256"],
                "catalog_anchor_count": len(catalog),
                "method_row_count": len(method_rows),
                "method_payload_sha256": built["method_payload_sha256"],
                "rendered_prompt_sha256": built["rendered_prompt_sha256"],
                "method_payload_check": "pass",
                "old_event_sample_count": len(expected_samples),
                "old_event_source_path": _relative(root, old_events_path),
                "old_event_source_sha256": sha256_file(old_events_path),
            }
        )
    run_dir = _repo_path(root, f"runs/{config['run_id']}")
    if require_fresh_run and run_dir.exists():
        raise ExtractionMethodError(f"运行目录已存在，拒绝复跑：{run_dir}")
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "pass",
        "at": now_iso(),
        "model_calls": 0,
        "arm": config["arm"],
        "method": config["method"],
        "run_id": config["run_id"],
        "config_sha256": sha256_bytes(canonical_json_bytes(config)),
        "prompt_audit": prompt_audit,
        "transport_audit": contract_audit,
        "default_activation": default_activation,
        "pins": pins,
        "artifact_paths": artifact_paths,
        "chapters": chapter_rows,
        "fresh_run_required": require_fresh_run,
        "fresh_run_pass": not run_dir.exists(),
        "api_key_environment_name": "SENSENOVA_API_KEY",
        "api_key_present": bool(os.environ.get("SENSENOVA_API_KEY")),
        "rights": config["rights"],
    }


def preflight_path(config: dict[str, Any], root: Path) -> Path:
    validate_artifact_paths(config, root)
    return _repo_path(root, f"work/zbatch_ab/preflight/{config['batch_id']}.json")


def save_preflight(config: dict[str, Any], root: Path) -> dict[str, Any]:
    result = preflight(config, root, require_fresh_run=True)
    write_json(preflight_path(config, root), result)
    return result


def permit_document(config: dict[str, Any], root: Path) -> dict[str, Any]:
    saved = preflight_path(config, root)
    if not saved.is_file():
        raise ExtractionMethodError("缺已落盘的零调用预演")
    saved_data = read_json(saved)
    current = preflight(config, root, require_fresh_run=True)
    comparable_saved = dict(saved_data)
    comparable_current = dict(current)
    for transient in ("at", "api_key_present"):
        comparable_saved.pop(transient, None)
        comparable_current.pop(transient, None)
    if comparable_saved != comparable_current:
        raise ExtractionMethodError("零调用预演已漂移，拒绝发调用证")
    if not current["api_key_present"]:
        raise ExtractionMethodError("缺 SENSENOVA_API_KEY，拒绝发调用证")
    return {
        "schema_version": PERMIT_SCHEMA,
        "issued_at": now_iso(),
        "batch_id": config["batch_id"],
        "run_id": config["run_id"],
        "arm": config["arm"],
        "chapters": EXPECTED_CHAPTERS,
        "model": EXPECTED_MODEL,
        "logical_sample_limit": 5,
        "network_attempt_limit": 15,
        "config_sha256": current["config_sha256"],
        "preflight_path": _relative(root, saved),
        "preflight_sha256": sha256_file(saved),
        "reuse_or_resume_allowed": False,
        "single_variable": config["method"],
    }


def create_permit(config: dict[str, Any], root: Path) -> Path:
    path = _repo_path(root, config["permit_path"])
    if path.exists():
        raise ExtractionMethodError("一次性调用证已存在，拒绝覆盖")
    document = permit_document(config, root)
    write_json(path, document)
    return path


def verify_permit(config: dict[str, Any], root: Path) -> dict[str, Any]:
    path = _repo_path(root, config["permit_path"])
    actual = read_json(path)
    expected = permit_document(config, root)
    for name in (
        "schema_version",
        "batch_id",
        "run_id",
        "arm",
        "chapters",
        "model",
        "logical_sample_limit",
        "network_attempt_limit",
        "config_sha256",
        "preflight_path",
        "preflight_sha256",
        "reuse_or_resume_allowed",
        "single_variable",
    ):
        if actual.get(name) != expected.get(name):
            raise ExtractionMethodError(f"一次性调用证字段漂移：{name}")
    return actual


def _selected_anchor_ids(document: dict[str, Any]) -> set[str]:
    return {
        str(anchor.get("anchor_id"))
        for event in document.get("events") or []
        if isinstance(event, dict)
        for anchor in event.get("anchors") or []
        if isinstance(anchor, dict) and isinstance(anchor.get("anchor_id"), str)
    }


def evaluate_target(
    target: dict[str, Any], document: dict[str, Any], catalog: list[dict[str, Any]]
) -> dict[str, Any]:
    selected = _selected_anchor_ids(document)
    expected = [str(value) for value in target.get("anchor_ids") or []]
    catalog_map = {str(row["anchor_id"]): str(row["quote"]) for row in catalog}
    selected_quotes = [catalog_map[value] for value in sorted(selected) if value in catalog_map]
    fragment_checks = {
        str(fragment): any(str(fragment) in quote for quote in selected_quotes)
        for fragment in target.get("required_quote_fragments") or []
    }
    missing = [value for value in expected if value not in selected]
    return {
        "id": target["id"],
        "label": target["label"],
        "chapter": target["chapter"],
        "expected_anchor_ids": expected,
        "missing_anchor_ids": missing,
        "required_quote_checks": fragment_checks,
        "pass": not missing and all(fragment_checks.values()),
        "boundary": target.get("boundary"),
    }


def method_coverage_ledger(
    arm: str, method_rows: list[dict[str, Any]], document: dict[str, Any]
) -> dict[str, Any]:
    events = [row for row in document.get("events") or [] if isinstance(row, dict)]
    rows = []
    for method_row in method_rows:
        method_anchors = set(str(value) for value in method_row.get("anchor_ids") or [])
        event_ids = [
            str(event.get("event_id"))
            for event in events
            if method_anchors.intersection(
                str(anchor.get("anchor_id"))
                for anchor in event.get("anchors") or []
                if isinstance(anchor, dict)
            )
        ]
        identifier = (
            method_row["segment_id"]
            if arm in {"A", "C"}
            else method_row["candidate_id"]
        )
        rows.append(
            {
                "method_row_id": identifier,
                "event_ids_with_anchor_overlap": event_ids,
                "status": "event_returned" if event_ids else "no_event_returned",
            }
        )
    return {
        "schema_version": "z-method-coverage-ledger-v1",
        "arm": arm,
        "rows": rows,
        "event_returned_count": sum(row["status"] == "event_returned" for row in rows),
        "no_event_returned_count": sum(row["status"] == "no_event_returned" for row in rows),
        "boundary": "只登记本次输出是否引用该段；no_event_returned 不是模型显式声明，也不是该段无独立事件的语义裁决。",
    }


def process_strong_segment_document(
    data: Any,
    *,
    chapter: int,
    catalog: list[dict[str, Any]],
    method_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """验收每段强合同，再把 events 交给现役中性事件合同。"""

    if not isinstance(data, dict):
        raise ExtractionMethodError(f"第 {chapter} 章每段强合同回包不是对象")
    reasons: list[str] = []
    if set(data) != STRONG_ROOT_KEYS:
        reasons.append("根字段不等于每段强合同")
    if data.get("schema_version") != STRONG_EVENT_SCHEMA_VERSION:
        reasons.append("schema错误")
    if data.get("chapter") != chapter:
        reasons.append("章号错误")
    raw_events = data.get("events")
    if not isinstance(raw_events, list):
        reasons.append("events不是数组")
        raw_events = []
    event_only = {
        "schema_version": neutral_extract.EVENT_SCHEMA_VERSION,
        "chapter": chapter,
        "events": raw_events,
    }
    try:
        materialized, program_audit = neutral_extract.process_model_data(
            event_only,
            chapter=chapter,
            catalog=catalog,
        )
    except ZBatchError as exc:
        reasons.append(str(exc))
        materialized = event_only
        program_audit = {"status": "fail", "reasons": [str(exc)]}

    decisions = data.get("segment_decisions")
    if not isinstance(decisions, list):
        reasons.append("segment_decisions不是数组")
        decisions = []
    expected_ids = [str(row["segment_id"]) for row in method_rows]
    observed_ids = [
        str(row.get("segment_id") or "") if isinstance(row, dict) else ""
        for row in decisions
    ]
    if observed_ids != expected_ids:
        reasons.append("段决定缺失、重复或顺序错误")

    event_map = {
        str(row.get("event_id")): row
        for row in materialized.get("events") or []
        if isinstance(row, dict)
    }
    method_map = {str(row["segment_id"]): row for row in method_rows}
    referenced_event_ids: set[str] = set()
    audit_rows: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            reasons.append(f"第 {index + 1} 个段决定不是对象")
            continue
        segment_id = str(decision.get("segment_id") or "")
        if set(decision) != SEGMENT_DECISION_KEYS:
            reasons.append(f"{segment_id or index + 1} 段决定字段越界")
        status = decision.get("status")
        event_ids = decision.get("event_ids")
        reason = decision.get("reason")
        if status not in {"emitted", "none"}:
            reasons.append(f"{segment_id} 状态非法")
        if not isinstance(event_ids, list) or any(
            not isinstance(value, str) or not value for value in (event_ids or [])
        ):
            reasons.append(f"{segment_id} event_ids非法")
            event_ids = []
        if len(event_ids) != len(set(event_ids)):
            reasons.append(f"{segment_id} event_ids重复")
        if not isinstance(reason, str) or not reason.strip():
            reasons.append(f"{segment_id} 缺明确理由")
        if status == "emitted" and not event_ids:
            reasons.append(f"{segment_id} 声明有事件但未列事件ID")
        if status == "none" and event_ids:
            reasons.append(f"{segment_id} 声明无事件却列了事件ID")
        method_row = method_map.get(segment_id)
        segment_anchor_ids = set(str(value) for value in (method_row or {}).get("anchor_ids", []))
        overlaps: dict[str, list[str]] = {}
        for event_id in event_ids:
            event = event_map.get(event_id)
            if event is None:
                reasons.append(f"{segment_id} 引用不存在事件 {event_id}")
                continue
            event_anchor_ids = {
                str(anchor.get("anchor_id"))
                for anchor in event.get("anchors") or []
                if isinstance(anchor, dict)
            }
            shared = sorted(segment_anchor_ids.intersection(event_anchor_ids))
            if not shared:
                reasons.append(f"{segment_id} 的事件 {event_id} 未引用本段证据")
            overlaps[event_id] = shared
            referenced_event_ids.add(event_id)
        audit_rows.append(
            {
                "segment_id": segment_id,
                "status": status,
                "event_ids": list(event_ids),
                "reason": reason,
                "event_anchor_overlaps": overlaps,
            }
        )
    unassigned = sorted(set(event_map) - referenced_event_ids)
    if unassigned:
        reasons.append(f"事件未挂入任何段决定：{unassigned}")
    unique_reasons = sorted(set(reasons))
    contract_audit = {
        "schema_version": "z-strong-segment-contract-audit-v1",
        "chapter": chapter,
        "status": "pass" if not unique_reasons else "fail",
        "segment_total": len(method_rows),
        "decision_total": len(decisions),
        "emitted_segment_total": sum(row.get("status") == "emitted" for row in decisions if isinstance(row, dict)),
        "explicit_none_segment_total": sum(row.get("status") == "none" for row in decisions if isinstance(row, dict)),
        "silent_segment_count": max(0, len(method_rows) - len(set(observed_ids))),
        "unassigned_event_ids": unassigned,
        "reasons": unique_reasons,
        "rows": audit_rows,
        "boundary": "只验每段是否显式交账及事件是否引用本段证据，不替代靶点与旧事件抽查。",
    }
    if unique_reasons:
        raise ExtractionMethodError(
            f"第 {chapter} 章每段强合同回包无效：{unique_reasons}；不做二次生成"
        )
    return materialized, program_audit, contract_audit


def old_event_spot_audit(
    *,
    chapter: int,
    samples: list[dict[str, Any]],
    old_document: dict[str, Any],
    new_document: dict[str, Any],
) -> dict[str, Any]:
    old_map = {
        str(row.get("event_id")): row
        for row in old_document.get("events") or []
        if isinstance(row, dict)
    }
    new_events = [row for row in new_document.get("events") or [] if isinstance(row, dict)]
    rows = []
    for sample in samples:
        event_id = str(sample["event_id"])
        old_event = old_map[event_id]
        old_anchors = {
            str(anchor.get("anchor_id"))
            for anchor in old_event.get("anchors") or []
            if isinstance(anchor, dict)
        }
        matches = []
        for event in new_events:
            new_anchors = {
                str(anchor.get("anchor_id"))
                for anchor in event.get("anchors") or []
                if isinstance(anchor, dict)
            }
            overlap = sorted(old_anchors.intersection(new_anchors))
            if overlap:
                matches.append({"event_id": event.get("event_id"), "shared_anchor_ids": overlap})
        rows.append(
            {
                "old_event_id": event_id,
                "old_anchor_ids": sorted(old_anchors),
                "new_matches": matches,
                "pass": bool(matches),
            }
        )
    return {
        "chapter": chapter,
        "status": "pass" if all(row["pass"] for row in rows) else "fail",
        "rows": rows,
        "boundary": "只要求每条预写旧事件至少有一个锚被新事件继续承接；不声称摘要逐字或语义完全等价。",
    }


def _attempt_summary(path: Path, chapters: Iterable[int]) -> dict[str, Any]:
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    per_chapter = []
    logical_samples = 0
    retries = 0
    for chapter in chapters:
        case_id = f"{chapter:04d}"
        selected = [row for row in rows if row.get("case_id") == case_id]
        attempts = [row.get("attempt") for row in selected]
        same_request = len({row.get("request_sha256") for row in selected}) <= 1
        one_sample = bool(selected) and attempts == list(range(1, len(selected) + 1)) and same_request
        if selected:
            logical_samples += 1
            retries += max(0, len(selected) - 1)
        per_chapter.append(
            {
                "chapter": chapter,
                "network_attempts": len(selected),
                "retries": max(0, len(selected) - 1),
                "one_logical_sample": one_sample,
            }
        )
    guard_pass = (
        len(rows) <= EXPECTED_TRANSPORT["max_network_attempts"]
        and logical_samples <= EXPECTED_TRANSPORT["logical_samples"]
        and all(row["one_logical_sample"] for row in per_chapter)
    )
    return {
        "status": "pass" if guard_pass else "fail",
        "network_attempts": len(rows),
        "logical_samples": logical_samples,
        "retries": retries,
        "chapters": per_chapter,
    }


def _key_trace_count(run_dir: Path, secret: str) -> int:
    if not secret:
        return 0
    needle = secret.encode("utf-8")
    return sum(
        needle in path.read_bytes()
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != ".DS_Store"
    )


def classify_hard_stop(exc: Exception, *, phase: str, chapter: int | None = None) -> dict[str, Any]:
    message = str(exc)
    lowered = message.lower()
    if "finish_reason" in lowered and "stop" not in lowered.replace("not_stop", ""):
        reason_code = "finish_reason_not_stop"
        truncated = True
    elif "未正常结束" in message or "finish_reason_not_stop" in lowered:
        reason_code = "finish_reason_not_stop"
        truncated = True
    elif "回包无效" in message or "模型返回不是合法 json" in lowered or "模型 json" in lowered:
        reason_code = "model_contract_invalid"
        truncated = False
    elif "调用失败" in message or "http" in lowered or "响应" in message:
        reason_code = "transport_failed"
        truncated = False
    elif "sha 漂移" in lowered:
        reason_code = "pin_drift"
        truncated = False
    else:
        reason_code = "mechanical_or_unknown_failure"
        truncated = False
    return {
        "phase": phase,
        "chapter": chapter,
        "reason_code": reason_code,
        "is_truncation": truncated,
        "error_type": type(exc).__name__,
        "error": message,
        "policy": "技术失败硬停；不缝补、不继续、不重采样。",
    }


def _run_arm_core(config: dict[str, Any], root: Path) -> dict[str, Any]:
    """凭一次性调用证跑五章；技术失败即停，不重采样挑结果。"""

    permit_path = _repo_path(root, config["permit_path"])
    verify_permit(config, root)
    run_dir = _repo_path(root, f"runs/{config['run_id']}")
    if run_dir.exists():
        raise ExtractionMethodError("运行目录已存在，拒绝复跑或续跑")
    run_dir.mkdir(parents=True)
    write_json(run_dir / "config.snapshot.json", config)
    write_json(run_dir / "preflight.snapshot.json", read_json(preflight_path(config, root)))
    target_document = read_json(_verify_ref(root, config["targets"], "五章靶点"))
    targets = _targets_by_chapter(target_document)
    sample_document = read_json(_verify_ref(root, config["old_event_samples"], "旧事件抽查件"))
    samples = _samples_by_chapter(sample_document)
    source_files = verify_old_source_files(config, root)
    write_json(
        run_dir / "old_event_sources.snapshot.json",
        {
            "source_run": config["old_event_samples"]["source_run"],
            "files": [
                {
                    "chapter": chapter,
                    "path": _relative(root, source_files[chapter]),
                    "sha256": sha256_file(source_files[chapter]),
                }
                for chapter in EXPECTED_CHAPTERS
            ],
        },
    )
    contract_path = _verify_ref(root, config["stage_contract"], "阶段采样合同")
    bundle = stage_sampling.load_contract_bundle(
        contract_path, profile=str(config["stage_contract"]["profile"])
    )
    transport = api_transport.ApiTransport.from_bundle(
        bundle,
        run_dir=run_dir,
        max_calls=int(config["transport"]["max_network_attempts"]),
    )
    chapter_rows = []
    hard_stop: dict[str, Any] | None = None
    try:
        for chapter in EXPECTED_CHAPTERS:
            built, catalog, method_rows, chapter_path = build_messages(config, root, chapter)
            input_dir = run_dir / "inputs"
            write_json(
                input_dir / f"ch{chapter:04d}.json",
                {
                    "chapter": chapter,
                    "chapter_file": _relative(root, chapter_path),
                    "messages": built["messages"],
                    "fingerprints": {key: value for key, value in built.items() if key != "messages"},
                },
            )
            write_json(run_dir / "evidence_catalogs" / f"ch{chapter:04d}.json", {"chapter": chapter, "entries": catalog})
            write_json(run_dir / "method_payloads" / f"ch{chapter:04d}.json", {"chapter": chapter, "rows": method_rows})
            try:
                result = transport.call(
                    stage="neutral_extract",
                    case_id=f"{chapter:04d}",
                    messages=built["messages"],
                )
                raw_document = candidate_envelope.parse_json_content(result.content)
                write_json(run_dir / "raw_event_documents" / f"ch{chapter:04d}.json", raw_document)
                strong_contract_audit = None
                if config["arm"] == "D":
                    materialized, program_audit, strong_contract_audit = (
                        process_strong_segment_document(
                            raw_document,
                            chapter=chapter,
                            catalog=catalog,
                            method_rows=method_rows,
                        )
                    )
                    write_json(
                        run_dir / "strong_segment_audits" / f"ch{chapter:04d}.json",
                        strong_contract_audit,
                    )
                else:
                    materialized, program_audit = neutral_extract.process_model_data(
                        raw_document, chapter=chapter, catalog=catalog
                    )
                write_json(run_dir / "events" / f"ch{chapter:04d}.json", materialized)
                write_json(run_dir / "program_audits" / f"ch{chapter:04d}.json", program_audit)
                target_audit = evaluate_target(targets[chapter], materialized, catalog)
                coverage_ledger = (
                    strong_contract_audit
                    if strong_contract_audit is not None
                    else method_coverage_ledger(config["arm"], method_rows, materialized)
                )
                old_document = read_json(source_files[chapter])
                old_audit = old_event_spot_audit(
                    chapter=chapter,
                    samples=samples[chapter],
                    old_document=old_document,
                    new_document=materialized,
                )
                write_json(run_dir / "target_audits" / f"ch{chapter:04d}.json", target_audit)
                write_json(run_dir / "method_coverage" / f"ch{chapter:04d}.json", coverage_ledger)
                write_json(run_dir / "old_event_spot_audits" / f"ch{chapter:04d}.json", old_audit)
                chapter_rows.append(
                    {
                        "chapter": chapter,
                        "status": "completed",
                        "event_count": len(materialized.get("events") or []),
                        "anchor_reference_count": program_audit["anchor_reference_count"],
                        "outside_catalog_anchor_count": len(program_audit["missing_catalog_anchor_ids"]),
                        "target": target_audit,
                        "old_event_spot_audit": old_audit,
                        "method_coverage": coverage_ledger,
                        "strong_segment_contract": strong_contract_audit,
                        "finish_reason": result.finish_reason,
                        "usage": dict(result.usage),
                        "transport_metadata": dict(result.metadata),
                    }
                )
            except Exception as exc:  # hard-stop receipt must survive every technical failure
                hard_stop = classify_hard_stop(exc, phase="chapter_execution", chapter=chapter)
                write_json(run_dir / "hard_stop.json", hard_stop)
                break
    finally:
        permit_path.unlink(missing_ok=True)

    attempts = _attempt_summary(run_dir / "call_attempts.jsonl", [row["chapter"] for row in chapter_rows] + ([hard_stop["chapter"]] if hard_stop else []))
    completed_all = len(chapter_rows) == len(EXPECTED_CHAPTERS) and hard_stop is None
    if completed_all and attempts["status"] != "pass":
        hard_stop = {
            "phase": "finalize",
            "chapter": None,
            "reason_code": "logical_sample_ledger_invalid",
            "is_truncation": False,
            "error_type": "ExtractionMethodError",
            "error": "调用账不满足每章一次逻辑采样或总尝试上限",
            "policy": "技术失败硬停；不缝补、不继续、不重采样。",
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        completed_all = False
    target_hits = sum(row["target"]["pass"] for row in chapter_rows)
    old_passes = sum(
        sample["pass"]
        for row in chapter_rows
        for sample in row["old_event_spot_audit"]["rows"]
    )
    completed_chapters = [row["chapter"] for row in chapter_rows]
    failed_chapters = [hard_stop["chapter"]] if hard_stop and hard_stop.get("chapter") else []
    chapter_statuses = chapter_status_rows(completed_chapters, failed_chapters)
    not_called_chapters = [
        row["chapter"]
        for row in chapter_statuses
        if row["status"] == CHAPTER_STATUS_NOT_CALLED
    ]
    real_usage = usage_totals(run_dir)
    if config["arm"] == "D":
        silent_segment_count = sum(
            int(
                (row.get("strong_segment_contract") or {}).get("silent_segment_count")
                or 0
            )
            for row in chapter_rows
        )
    elif config["arm"] == "C":
        silent_segment_count = sum(
            int((row.get("method_coverage") or {}).get("no_event_returned_count") or 0)
            for row in chapter_rows
        )
    else:
        silent_segment_count = 0
    result_document = {
        "schema_version": RESULT_SCHEMA,
        "at": now_iso(),
        "status": "completed" if completed_all else "hard_stopped",
        "arm": config["arm"],
        "method": config["method"],
        "run_id": config["run_id"],
        "model": EXPECTED_MODEL,
        "temperature": 0.2,
        "chapters_planned": EXPECTED_CHAPTERS,
        "chapters_completed": completed_chapters,
        "chapters_failed": failed_chapters,
        "chapters_not_called": not_called_chapters,
        "chapters_not_evaluated": not_called_chapters,
        "chapter_statuses": chapter_statuses,
        "logical_sample_policy": "每章一次逻辑采样；同请求网络重试不算新增采样。",
        "transport": attempts,
        "metrics": {
            "model_logical_samples": attempts["logical_samples"],
            "network_attempts": attempts["network_attempts"],
            "retries": attempts["retries"],
            "empty_chapters": sum(row["event_count"] == 0 for row in chapter_rows),
            "truncated_chapter_count": int(bool(hard_stop and hard_stop.get("is_truncation"))),
            "truncated_chapters": [hard_stop["chapter"]]
            if hard_stop and hard_stop.get("is_truncation") and hard_stop.get("chapter")
            else [],
            "target_span_coverage_passes": target_hits,
            "target_span_coverage_evaluated": len(chapter_rows),
            "target_span_coverage_planned": len(EXPECTED_CHAPTERS),
            "outside_catalog_anchor_count": sum(row["outside_catalog_anchor_count"] for row in chapter_rows),
            "old_event_anchor_overlap_passes": old_passes,
            "old_event_anchor_overlap_evaluated": len(chapter_rows) * 2,
            "old_event_anchor_overlap_planned": len(EXPECTED_CHAPTERS) * 2,
            **real_usage,
            "silent_segment_count": silent_segment_count,
            "segment_decision_total": sum(
                int((row.get("strong_segment_contract") or {}).get("decision_total") or 0)
                for row in chapter_rows
            ),
            "explicit_none_segment_total": sum(
                int((row.get("strong_segment_contract") or {}).get("explicit_none_segment_total") or 0)
                for row in chapter_rows
            ),
        },
        "acceptance": {
            "known_target_span_coverage": {
                "pass": target_hits,
                "evaluated": len(chapter_rows),
                "planned": len(EXPECTED_CHAPTERS),
                "role": "机械锚覆盖横向供数，不等于靶事件语义恢复；漏靶不触发技术硬停。",
            },
            "outside_catalog_anchor_zero": completed_all
            and all(row["outside_catalog_anchor_count"] == 0 for row in chapter_rows),
            "no_new_technical_failure": completed_all,
            "silent_segments_zero": completed_all
            and config["arm"] in {"C", "D"}
            and silent_segment_count == 0,
            "old_event_anchor_overlap_spot_check": {
                "pass": old_passes,
                "evaluated": len(chapter_rows) * 2,
                "planned": len(EXPECTED_CHAPTERS) * 2,
                "role": "只看预写旧事件是否至少保留一个共享锚，不等于旧事件未劣化。",
            },
            "winner_not_decided": True,
        },
        "hard_stop": hard_stop,
        "chapters": chapter_rows,
        "api_key_trace_count": _key_trace_count(
            run_dir, os.environ.get("SENSENOVA_API_KEY", "")
        ),
        "outbox_written": False,
        "rights": config["rights"],
    }
    write_json(run_dir / "result.json", result_document)
    return result_document


def recover_partial_run(run_dir: Path) -> dict[str, Any]:
    """从已落盘工件恢复外层异常前的真实调用与完成状态。"""

    completed = sorted(
        int(path.stem.removeprefix("ch"))
        for path in (run_dir / "events").glob("ch*.json")
        if path.stem.removeprefix("ch").isdigit()
    )
    attempt_rows: list[dict[str, Any]] = []
    attempt_path = run_dir / "call_attempts.jsonl"
    if attempt_path.is_file():
        for line in attempt_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                attempt_rows.append(row)
    attempted = sorted(
        {
            int(str(row.get("case_id")))
            for row in attempt_rows
            if str(row.get("case_id") or "").isdigit()
        }
    )
    prior_hard_stop = None
    if (run_dir / "hard_stop.json").is_file():
        try:
            prior_hard_stop = read_json(run_dir / "hard_stop.json")
        except ExtractionMethodError:
            prior_hard_stop = None
    failed = sorted(set(attempted) - set(completed))
    if prior_hard_stop and isinstance(prior_hard_stop.get("chapter"), int):
        failed = sorted(set(failed) | {int(prior_hard_stop["chapter"])})
    target_passes = 0
    target_evaluated = 0
    for path in sorted((run_dir / "target_audits").glob("ch*.json")):
        try:
            row = read_json(path)
        except ExtractionMethodError:
            continue
        target_evaluated += 1
        target_passes += int(row.get("pass") is True)
    old_passes = 0
    old_evaluated = 0
    for path in sorted((run_dir / "old_event_spot_audits").glob("ch*.json")):
        try:
            row = read_json(path)
        except ExtractionMethodError:
            continue
        samples = row.get("rows") if isinstance(row.get("rows"), list) else []
        old_evaluated += len(samples)
        old_passes += sum(item.get("pass") is True for item in samples if isinstance(item, dict))
    real_usage = usage_totals(run_dir, strict=False)
    truncated = []
    if prior_hard_stop and prior_hard_stop.get("is_truncation") and prior_hard_stop.get("chapter"):
        truncated.append(int(prior_hard_stop["chapter"]))
    for path in (run_dir / "errors").glob("*.txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "finish_reason=length" in text or "finish_reason=max_tokens" in text:
            match = re.search(r"(\d{4})", path.name)
            if match:
                truncated.append(int(match.group(1)))
    unique_cases = {str(row.get("case_id")) for row in attempt_rows if row.get("case_id") is not None}
    chapter_statuses = chapter_status_rows(completed, failed)
    not_called_chapters = [
        row["chapter"]
        for row in chapter_statuses
        if row["status"] == CHAPTER_STATUS_NOT_CALLED
    ]
    return {
        "chapters_completed": completed,
        "chapters_failed": failed,
        "chapters_not_called": not_called_chapters,
        "chapters_not_evaluated": not_called_chapters,
        "chapter_statuses": chapter_statuses,
        "network_attempts": len(attempt_rows),
        "logical_samples": len(unique_cases),
        "retries": max(0, len(attempt_rows) - len(unique_cases)),
        "target_span_coverage_passes": target_passes,
        "target_span_coverage_evaluated": target_evaluated,
        "old_event_anchor_overlap_passes": old_passes,
        "old_event_anchor_overlap_evaluated": old_evaluated,
        "truncated_chapters": sorted(set(truncated)),
        **real_usage,
        "prior_hard_stop": prior_hard_stop,
    }


def run_arm(config: dict[str, Any], root: Path) -> dict[str, Any]:
    """给初始化、章内执行和收尾统一加可审计外壳。"""

    validate_artifact_paths(config, root)
    run_dir = _repo_path(root, f"runs/{config['run_id']}")
    permit_path = _repo_path(root, config["permit_path"])
    run_preexisted = run_dir.exists()
    try:
        return _run_arm_core(config, root)
    except Exception as exc:
        hard_stop = classify_hard_stop(exc, phase="initialization_or_finalize")
        recovered = recover_partial_run(run_dir) if run_dir.exists() and not run_preexisted else {
            "chapters_completed": [],
            "chapters_failed": [],
            "chapters_not_called": EXPECTED_CHAPTERS,
            "chapters_not_evaluated": EXPECTED_CHAPTERS,
            "chapter_statuses": chapter_status_rows([], []),
            "network_attempts": 0,
            "logical_samples": 0,
            "retries": 0,
            "target_span_coverage_passes": 0,
            "target_span_coverage_evaluated": 0,
            "old_event_anchor_overlap_passes": 0,
            "old_event_anchor_overlap_evaluated": 0,
            "truncated_chapters": [],
            "total_tokens": 0,
            "usage_row_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "cached_tokens": 0,
            "invalid_usage_row_count": 0,
            "prior_hard_stop": None,
        }
        result = {
            "schema_version": RESULT_SCHEMA,
            "at": now_iso(),
            "status": "hard_stopped",
            "arm": config.get("arm"),
            "method": config.get("method"),
            "run_id": config.get("run_id"),
            "chapters_planned": EXPECTED_CHAPTERS,
            "chapters_completed": recovered["chapters_completed"],
            "chapters_failed": recovered["chapters_failed"],
            "chapters_not_called": recovered["chapters_not_called"],
            "chapters_not_evaluated": recovered["chapters_not_evaluated"],
            "chapter_statuses": recovered["chapter_statuses"],
            "metrics": {
                "model_logical_samples": recovered["logical_samples"],
                "network_attempts": recovered["network_attempts"],
                "retries": recovered["retries"],
                "target_span_coverage_passes": recovered["target_span_coverage_passes"],
                "target_span_coverage_evaluated": recovered["target_span_coverage_evaluated"],
                "target_span_coverage_planned": len(EXPECTED_CHAPTERS),
                "old_event_anchor_overlap_passes": recovered["old_event_anchor_overlap_passes"],
                "old_event_anchor_overlap_evaluated": recovered["old_event_anchor_overlap_evaluated"],
                "old_event_anchor_overlap_planned": len(EXPECTED_CHAPTERS) * 2,
                "truncated_chapter_count": len(recovered["truncated_chapters"]),
                "truncated_chapters": recovered["truncated_chapters"],
                "total_tokens": recovered["total_tokens"],
                "usage_row_count": recovered["usage_row_count"],
                "prompt_tokens": recovered["prompt_tokens"],
                "completion_tokens": recovered["completion_tokens"],
                "reasoning_tokens": recovered["reasoning_tokens"],
                "cached_tokens": recovered["cached_tokens"],
                "invalid_usage_row_count": recovered["invalid_usage_row_count"],
            },
            "hard_stop": hard_stop,
            "prior_hard_stop": recovered["prior_hard_stop"],
            "model_calls_known": recovered["network_attempts"],
            "outbox_written": False,
            "rights": config.get("rights"),
        }
        if run_dir.exists() and not run_preexisted:
            write_json(run_dir / "hard_stop.json", hard_stop)
            write_json(run_dir / "result.json", result)
        else:
            rejection = _repo_path(root, f"work/zbatch_ab/rejections/{config.get('batch_id', 'unknown')}.json")
            write_json(rejection, result)
        return result
    finally:
        permit_path.unlink(missing_ok=True)


def compare_results(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    if a.get("arm") != "A" or b.get("arm") != "B":
        raise ExtractionMethodError("对照输入必须按 A、B 两臂传入")
    rows = []
    a_by_chapter = {row["chapter"]: row for row in a.get("chapters") or []}
    b_by_chapter = {row["chapter"]: row for row in b.get("chapters") or []}
    for chapter in EXPECTED_CHAPTERS:
        left = a_by_chapter.get(chapter)
        right = b_by_chapter.get(chapter)
        rows.append(
            {
                "chapter": chapter,
                "target": (left or right or {}).get("target", {}).get("label"),
                "arm_a_target_hit": bool(left and left["target"]["pass"]),
                "arm_b_target_hit": bool(right and right["target"]["pass"]),
                "arm_a_event_count": left.get("event_count") if left else None,
                "arm_b_event_count": right.get("event_count") if right else None,
                "arm_a_old_spot_pass": sum(row["pass"] for row in left["old_event_spot_audit"]["rows"]) if left else None,
                "arm_b_old_spot_pass": sum(row["pass"] for row in right["old_event_spot_audit"]["rows"]) if right else None,
            }
        )
    return {
        "schema_version": COMPARISON_SCHEMA,
        "at": now_iso(),
        "arm_a": {"run_id": a.get("run_id"), "status": a.get("status"), "metrics": a.get("metrics")},
        "arm_b": {"run_id": b.get("run_id"), "status": b.get("status"), "metrics": b.get("metrics")},
        "chapters": rows,
        "winner": None,
        "decision_boundary": "本件只横向列数，不固化胜臂；哪臂胜、是否扩20章由 CZ 另拍。",
    }
