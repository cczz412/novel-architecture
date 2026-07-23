"""第41道件C：非思考模式单变量轮。

本模块不接默认流水线。它完整复用 v1.2 默认链的中性事件 Prompt、章节、
采样参数与评分件，只在本次旁路请求中省略 ``reasoning_effort`` 字段。
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import (
    api_transport,
    candidate_envelope,
    evidence_catalog,
    extraction_method_ab,
    neutral_extract,
    stage_sampling,
)
from .errors import ZBatchError


SCHEMA_VERSION = "z-nonthinking-pilot-v1"
PREFLIGHT_SCHEMA = "z-nonthinking-pilot-preflight-v1"
PERMIT_SCHEMA = "z-nonthinking-pilot-permit-v1"
RESULT_SCHEMA = "z-nonthinking-pilot-result-v1"
EXPECTED_CHAPTERS = [3, 4, 5, 13, 19]
EXPECTED_BATCH_ID = "Z01h"
EXPECTED_METHOD = "omit_reasoning_effort"
EXPECTED_STAGE = "neutral_extract"
EXPECTED_MODEL = "deepseek-v4-flash"
EXPECTED_BASELINE_TRANSPORT = {
    "model": EXPECTED_MODEL,
    "temperature": 0.2,
    "max_tokens": 16000,
    "n": 1,
    "reasoning_effort": "medium",
    "response_format": {"type": "json_object"},
}


class NonThinkingPilotError(ZBatchError):
    """件C预演、调用或收尾失败。"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return extraction_method_ab.read_json(path)


def write_json(path: Path, data: Any) -> None:
    extraction_method_ab.write_json(path, data)


def sha256_file(path: Path) -> str:
    return extraction_method_ab.sha256_file(path)


def _repo_path(root: Path, value: str) -> Path:
    try:
        return extraction_method_ab._repo_path(root, value)
    except extraction_method_ab.ExtractionMethodError as exc:
        raise NonThinkingPilotError(str(exc)) from exc


def _relative(root: Path, path: Path) -> str:
    return extraction_method_ab._relative(root, path)


def _verify_ref(root: Path, ref: dict[str, Any], label: str) -> Path:
    try:
        return extraction_method_ab._verify_ref(root, ref, label)
    except extraction_method_ab.ExtractionMethodError as exc:
        raise NonThinkingPilotError(str(exc)) from exc


def tree_fingerprint(path: Path) -> dict[str, Any]:
    """只登记目录内文件名与 SHA 的总指纹，不写入该目录。"""

    rows = []
    if path.is_dir():
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            rows.append(
                {
                    "path": str(item.relative_to(path)),
                    "sha256": sha256_file(item),
                }
            )
    digest = extraction_method_ab.sha256_bytes(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {"file_count": len(rows), "sha256": digest}


def validate_artifact_paths(config: dict[str, Any], root: Path) -> dict[str, str]:
    if config.get("batch_id") != EXPECTED_BATCH_ID:
        raise NonThinkingPilotError(f"件C batch_id 必须是 {EXPECTED_BATCH_ID}")
    run_id = str(config.get("run_id") or "")
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise NonThinkingPilotError("run_id 必须是 runs/ 下的单个安全目录名")
    run_dir = _repo_path(root, f"runs/{run_id}")
    if run_dir.parent != _repo_path(root, "runs"):
        raise NonThinkingPilotError("运行工件只能落在 runs/ 的直属目录")
    permit = _repo_path(root, str(config.get("permit_path") or ""))
    permit_root = _repo_path(root, "work/zbatch_nonthinking/permits")
    if permit.parent != permit_root or permit.suffix != ".json":
        raise NonThinkingPilotError(
            "调用证只能落在 work/zbatch_nonthinking/permits/ 的直属 JSON 文件"
        )
    preflight = _repo_path(root, f"work/zbatch_nonthinking/preflight/{EXPECTED_BATCH_ID}.json")
    rejection = _repo_path(root, f"work/zbatch_nonthinking/rejections/{EXPECTED_BATCH_ID}.json")
    return {
        "run_dir": _relative(root, run_dir),
        "permit_path": _relative(root, permit),
        "preflight_path": _relative(root, preflight),
        "rejection_path": _relative(root, rejection),
    }


def resolve_report_output(root: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        raise NonThinkingPilotError("--output 不接受绝对路径")
    output = _repo_path(root, value)
    allowed = _repo_path(root, "reports/Z01h_非思考模式单变量轮_20260719")
    try:
        output.relative_to(allowed)
    except ValueError as exc:
        raise NonThinkingPilotError("件C回执只能写入登记过的 reports/Z01h 目录") from exc
    if output.suffix.lower() != ".json":
        raise NonThinkingPilotError("--output 只接受 .json 回执")
    return output


def _load_bundle(config: dict[str, Any], root: Path) -> stage_sampling.StageContractBundle:
    contract_ref = config["stage_contract"]
    contract_path = _verify_ref(root, contract_ref, "阶段采样合同")
    _verify_ref(root, config["provider"], "运输路由")
    return stage_sampling.load_contract_bundle(
        contract_path, profile=str(contract_ref["profile"])
    )


def candidate_contract(
    bundle: stage_sampling.StageContractBundle,
) -> stage_sampling.StageSamplingContract:
    baseline = bundle.stage(EXPECTED_STAGE)
    return replace(
        baseline,
        reasoning_effort=None,
        status=stage_sampling.CANDIDATE_STATUS,
        note="第41道件C旁路候选；请求体只省略 reasoning_effort。",
    )


def transport_audit(
    config: dict[str, Any], root: Path, messages: list[dict[str, str]]
) -> dict[str, Any]:
    bundle = _load_bundle(config, root)
    route = api_transport.TransportRoute.from_mapping(bundle.route)
    baseline = bundle.stage(EXPECTED_STAGE)
    actual_baseline = {
        "model": route.model,
        "temperature": baseline.temperature,
        "max_tokens": baseline.max_tokens,
        "n": baseline.n,
        "reasoning_effort": baseline.reasoning_effort,
        "response_format": dict(baseline.response_format),
    }
    if actual_baseline != EXPECTED_BASELINE_TRANSPORT:
        raise NonThinkingPilotError(f"v1.2运输基线漂移：{actual_baseline}")
    if config.get("baseline_transport") != EXPECTED_BASELINE_TRANSPORT:
        raise NonThinkingPilotError("配置登记的v1.2运输基线不一致")
    candidate = candidate_contract(bundle)
    baseline_body = api_transport.build_request_body(
        model=route.model,
        messages=messages,
        contract=baseline,
    )
    candidate_body = api_transport.build_request_body(
        model=route.model,
        messages=messages,
        contract=candidate,
        allow_unverified_candidate=True,
    )
    removed = sorted(set(baseline_body) - set(candidate_body))
    added = sorted(set(candidate_body) - set(baseline_body))
    changed = sorted(
        key
        for key in set(baseline_body).intersection(candidate_body)
        if baseline_body[key] != candidate_body[key]
    )
    if removed != ["reasoning_effort"] or added or changed:
        raise NonThinkingPilotError(
            f"非思考请求不是单变量：removed={removed}, added={added}, changed={changed}"
        )
    return {
        "status": "pass",
        "baseline": actual_baseline,
        "candidate": {
            "model": route.model,
            "temperature": candidate.temperature,
            "max_tokens": candidate.max_tokens,
            "n": candidate.n,
            "reasoning_effort_field": "omitted",
            "response_format": dict(candidate.response_format),
        },
        "request_body_diff": {
            "removed_keys": removed,
            "added_keys": added,
            "changed_keys": changed,
        },
        "logical_samples": int(config["transport_limits"]["logical_samples"]),
        "max_network_attempts": int(config["transport_limits"]["max_network_attempts"]),
    }


def verify_default_activation(config: dict[str, Any], root: Path) -> dict[str, Any]:
    try:
        refs = extraction_method_ab.verify_compatible_default_refs(
            root,
            config["default_registry"],
            config["default_commit_marker"],
        )
    except extraction_method_ab.ExtractionMethodError as exc:
        raise NonThinkingPilotError(str(exc)) from exc
    registry_path = refs["registry_path"]
    marker_path = refs["marker_path"]
    registry = refs["registry"]
    marker = refs["marker"]
    if registry.get("status") != "active" or registry.get("version") != "v1.2":
        raise NonThinkingPilotError("v1.2默认登记未处于active状态")
    binding = marker.get("default_registry") or {}
    if (
        marker.get("status") != "committed"
        or binding.get("path") != config["default_registry"]["path"]
        or binding.get("sha256") != refs["actual_registry_sha256"]
    ):
        raise NonThinkingPilotError("提交标记没有绑定当前v1.2默认登记")
    prompt = registry.get("chain", {}).get("neutral_extract_prompt")
    if prompt != config.get("prompt"):
        raise NonThinkingPilotError("件C Prompt 不等于当前v1.2默认 Prompt")
    transport = registry.get("chain", {}).get("transport", {}).get(EXPECTED_STAGE)
    if transport != {
        "temperature": 0.2,
        "max_tokens": 16000,
        "n": 1,
        "reasoning_effort": "medium",
    }:
        raise NonThinkingPilotError("件C参照的v1.2默认运输参数漂移")
    return {
        "status": "pass",
        "default_registry_sha256": sha256_file(registry_path),
        "commit_marker_sha256": sha256_file(marker_path),
        "default_id": registry.get("default_id"),
        "pin_resolution": refs["mode"],
        "requested_predecessor_registry_sha256": refs["requested_registry_sha256"],
        "compatibility_revision_id": refs.get("revision_id"),
    }


def build_chapter_input(
    config: dict[str, Any], root: Path, chapter: int
) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    book_dir = _repo_path(root, config["book_dir"])
    try:
        chapter_path = extraction_method_ab._chapter_path(book_dir, chapter)
    except extraction_method_ab.ExtractionMethodError as exc:
        raise NonThinkingPilotError(str(exc)) from exc
    text = chapter_path.read_text(encoding="utf-8")
    catalog = evidence_catalog.build_evidence_catalog(chapter, text)
    if not catalog:
        raise NonThinkingPilotError(f"第 {chapter} 章冻结目录为空")
    prompt_path = _verify_ref(root, config["prompt"], "v1.2默认 Prompt")
    built = neutral_extract.build_messages(
        prompt_path=prompt_path,
        expected_prompt_sha256=config["prompt"]["sha256"],
        chapter=chapter,
        chapter_filename=chapter_path.name,
        catalog=catalog,
    )
    built["chapter_file_sha256"] = sha256_file(chapter_path)
    return built, catalog, chapter_path


def _targets_and_samples(
    config: dict[str, Any], root: Path
) -> tuple[dict[int, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    targets = extraction_method_ab._targets_by_chapter(
        read_json(_verify_ref(root, config["targets"], "五章靶点"))
    )
    samples = extraction_method_ab._samples_by_chapter(
        read_json(_verify_ref(root, config["old_event_samples"], "旧事件抽查件"))
    )
    return targets, samples


def verify_baseline_event_sources(config: dict[str, Any], root: Path) -> dict[int, Path]:
    try:
        return extraction_method_ab.verify_old_source_files(config, root)
    except extraction_method_ab.ExtractionMethodError as exc:
        raise NonThinkingPilotError(str(exc)) from exc


def usage_row_from_source(
    root: Path, ref: dict[str, Any], *, chapter: int
) -> dict[str, Any]:
    path = _verify_ref(root, ref, f"第 {chapter} 章v1.2用量真源")
    expected_case = str(ref.get("case_id") or "")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict) and value.get("case_id") == expected_case:
            rows.append(value)
    if len(rows) != 1:
        raise NonThinkingPilotError(
            f"第 {chapter} 章v1.2用量真源匹配行数异常：{len(rows)}"
        )
    return rows[0]


def baseline_snapshot(config: dict[str, Any], root: Path) -> dict[str, Any]:
    targets, samples = _targets_and_samples(config, root)
    source_files = verify_baseline_event_sources(config, root)
    usage_refs = {
        int(ref["chapter"]): ref for ref in config.get("baseline_usage_sources") or []
    }
    if sorted(usage_refs) != EXPECTED_CHAPTERS:
        raise NonThinkingPilotError("v1.2用量真源不是五章各一条")
    rows = []
    for chapter in EXPECTED_CHAPTERS:
        document = read_json(source_files[chapter])
        text = _repo_path(root, config["book_dir"])
        try:
            chapter_path = extraction_method_ab._chapter_path(text, chapter)
        except extraction_method_ab.ExtractionMethodError as exc:
            raise NonThinkingPilotError(str(exc)) from exc
        catalog = evidence_catalog.build_evidence_catalog(
            chapter, chapter_path.read_text(encoding="utf-8")
        )
        target = extraction_method_ab.evaluate_target(targets[chapter], document, catalog)
        old_audit = extraction_method_ab.old_event_spot_audit(
            chapter=chapter,
            samples=samples[chapter],
            old_document=document,
            new_document=document,
        )
        segment_rows = extraction_method_ab.build_segment_tasks(
            catalog, segment_size=int(config["audit_segment_size"])
        )
        coverage = extraction_method_ab.method_coverage_ledger("A", segment_rows, document)
        usage_row = usage_row_from_source(root, usage_refs[chapter], chapter=chapter)
        usage = usage_row.get("usage") if isinstance(usage_row.get("usage"), dict) else {}
        details = usage.get("completion_tokens_details")
        rows.append(
            {
                "chapter": chapter,
                "event_source": _relative(root, source_files[chapter]),
                "event_source_sha256": sha256_file(source_files[chapter]),
                "target": target,
                "old_event_spot_audit": old_audit,
                "audit_segment_total": len(segment_rows),
                "silent_segment_count": coverage["no_event_returned_count"],
                "usage_source": _relative(root, _verify_ref(root, usage_refs[chapter], f"第 {chapter} 章v1.2用量真源")),
                "usage_case_id": usage_refs[chapter]["case_id"],
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
                "reasoning_tokens": int(details.get("reasoning_tokens") or 0)
                if isinstance(details, dict)
                else 0,
                "elapsed_ms": int(usage_row.get("elapsed_ms") or 0),
            }
        )
    return summarize_rows(rows, mode="v1.2_default_reference")


def summarize_rows(rows: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    old_passes = sum(
        item["pass"]
        for row in rows
        for item in row.get("old_event_spot_audit", {}).get("rows", [])
    )
    return {
        "mode": mode,
        "chapters": rows,
        "metrics": {
            "target_hits": sum(bool(row.get("target", {}).get("pass")) for row in rows),
            "old_event_spot_passes": old_passes,
            "silent_segment_count": sum(int(row.get("silent_segment_count") or 0) for row in rows),
            "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in rows),
            "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in rows),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in rows),
            "reasoning_tokens": sum(int(row.get("reasoning_tokens") or 0) for row in rows),
            "elapsed_ms": sum(int(row.get("elapsed_ms") or 0) for row in rows),
        },
    }


def actual_cost_totals(run_dir: Path) -> dict[str, int]:
    """从运输真账汇总成本；已调用失败章也必须计入。"""

    totals = extraction_method_ab.usage_totals(run_dir, strict=False)
    elapsed_ms = 0
    usage_path = run_dir / "usage.jsonl"
    if usage_path.is_file():
        for line in usage_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                elapsed_ms += int(row.get("elapsed_ms") or 0)
    return {
        "usage_row_count": int(totals["usage_row_count"]),
        "invalid_usage_row_count": int(totals["invalid_usage_row_count"]),
        "prompt_tokens": int(totals["prompt_tokens"]),
        "completion_tokens": int(totals["completion_tokens"]),
        "total_tokens": int(totals["total_tokens"]),
        "reasoning_tokens": int(totals["reasoning_tokens"]),
        "cached_tokens": int(totals["cached_tokens"]),
        "elapsed_ms": elapsed_ms,
    }


def preflight(
    config: dict[str, Any], root: Path, *, require_fresh_run: bool = True
) -> dict[str, Any]:
    artifact_paths = validate_artifact_paths(config, root)
    if config.get("schema_version") != SCHEMA_VERSION:
        raise NonThinkingPilotError("件C配置 schema 错误")
    if config.get("method") != EXPECTED_METHOD:
        raise NonThinkingPilotError("件C只允许省略 reasoning_effort 这一种方法")
    if list(config.get("chapters") or []) != EXPECTED_CHAPTERS:
        raise NonThinkingPilotError("件C章节必须固定为 3/4/5/13/19")
    if config.get("transport_limits") != {
        "logical_samples": 5,
        "max_network_attempts": 15,
    }:
        raise NonThinkingPilotError("件C调用闸必须固定为5次逻辑采样、最多15次网络尝试")
    default_audit = verify_default_activation(config, root)
    pins = []
    for group_name in ("protected_chain", "experiment_code"):
        for name, ref in config[group_name].items():
            path = _verify_ref(root, ref, f"{group_name}.{name}")
            pins.append(
                {
                    "label": f"{group_name}.{name}",
                    "path": _relative(root, path),
                    "sha256": ref["sha256"],
                }
            )
    targets, samples = _targets_and_samples(config, root)
    source_files = verify_baseline_event_sources(config, root)
    chapter_rows = []
    representative_transport = None
    for chapter in EXPECTED_CHAPTERS:
        built, catalog, chapter_path = build_chapter_input(config, root, chapter)
        current_transport = transport_audit(config, root, built["messages"])
        if representative_transport is None:
            representative_transport = current_transport
        elif current_transport != representative_transport:
            raise NonThinkingPilotError("五章请求体单变量审计不一致")
        old_document = read_json(source_files[chapter])
        old_ids = {
            str(row.get("event_id"))
            for row in old_document.get("events") or []
            if isinstance(row, dict)
        }
        expected_old_ids = {str(row["event_id"]) for row in samples[chapter]}
        if not expected_old_ids.issubset(old_ids):
            raise NonThinkingPilotError(f"第 {chapter} 章旧事件抽查 ID 不存在")
        chapter_rows.append(
            {
                "chapter": chapter,
                "chapter_file": _relative(root, chapter_path),
                "chapter_file_sha256": built["chapter_file_sha256"],
                "catalog_anchor_count": len(catalog),
                "template_sha256": built["template_sha256"],
                "rendered_prompt_sha256": built["prompt_sha256"],
                "catalog_sha256": built["catalog_sha256"],
                "target_id": targets[chapter]["id"],
                "old_event_sample_count": len(expected_old_ids),
                "request_body_single_variable": "pass",
            }
        )
    run_dir = _repo_path(root, f"runs/{config['run_id']}")
    if require_fresh_run and run_dir.exists():
        raise NonThinkingPilotError(f"运行目录已存在，拒绝复跑：{run_dir}")
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "pass",
        "at": now_iso(),
        "model_calls": 0,
        "batch_id": EXPECTED_BATCH_ID,
        "method": EXPECTED_METHOD,
        "run_id": config["run_id"],
        "config_sha256": extraction_method_ab.sha256_bytes(
            extraction_method_ab.canonical_json_bytes(config)
        ),
        "default_activation": default_audit,
        "transport_audit": representative_transport,
        "baseline": baseline_snapshot(config, root),
        "pins": pins,
        "artifact_paths": artifact_paths,
        "protected_state": {
            "default_registry_sha256": config["default_registry"]["sha256"],
            "default_commit_marker_sha256": config["default_commit_marker"]["sha256"],
            "outbox": tree_fingerprint(_repo_path(root, "outbox")),
        },
        "chapters": chapter_rows,
        "fresh_run_required": require_fresh_run,
        "fresh_run_pass": not run_dir.exists(),
        "api_key_environment_name": api_transport.PINNED_API_KEY_ENV,
        "api_key_present": bool(os.environ.get(api_transport.PINNED_API_KEY_ENV)),
        "rights": config["rights"],
    }


def preflight_path(config: dict[str, Any], root: Path) -> Path:
    validate_artifact_paths(config, root)
    return _repo_path(root, f"work/zbatch_nonthinking/preflight/{EXPECTED_BATCH_ID}.json")


def save_preflight(config: dict[str, Any], root: Path) -> dict[str, Any]:
    document = preflight(config, root, require_fresh_run=True)
    write_json(preflight_path(config, root), document)
    return document


def permit_document(config: dict[str, Any], root: Path) -> dict[str, Any]:
    saved_path = preflight_path(config, root)
    if not saved_path.is_file():
        raise NonThinkingPilotError("缺已落盘的零调用预演")
    saved = read_json(saved_path)
    current = preflight(config, root, require_fresh_run=True)
    left = dict(saved)
    right = dict(current)
    for transient in ("at", "api_key_present"):
        left.pop(transient, None)
        right.pop(transient, None)
    if left != right:
        raise NonThinkingPilotError("零调用预演已漂移，拒绝发调用证")
    if not current["api_key_present"]:
        raise NonThinkingPilotError("缺 SENSENOVA_API_KEY，拒绝发调用证")
    return {
        "schema_version": PERMIT_SCHEMA,
        "issued_at": now_iso(),
        "batch_id": EXPECTED_BATCH_ID,
        "run_id": config["run_id"],
        "method": EXPECTED_METHOD,
        "chapters": EXPECTED_CHAPTERS,
        "model": EXPECTED_MODEL,
        "logical_sample_limit": 5,
        "network_attempt_limit": 15,
        "config_sha256": current["config_sha256"],
        "preflight_path": _relative(root, saved_path),
        "preflight_sha256": sha256_file(saved_path),
        "reuse_or_resume_allowed": False,
        "single_variable": "只省略请求体 reasoning_effort 字段",
    }


def create_permit(config: dict[str, Any], root: Path) -> Path:
    path = _repo_path(root, config["permit_path"])
    if path.exists():
        raise NonThinkingPilotError("一次性调用证已存在，拒绝覆盖")
    write_json(path, permit_document(config, root))
    return path


def verify_permit(config: dict[str, Any], root: Path) -> dict[str, Any]:
    path = _repo_path(root, config["permit_path"])
    actual = read_json(path)
    expected = permit_document(config, root)
    for key in (
        "schema_version",
        "batch_id",
        "run_id",
        "method",
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
        if actual.get(key) != expected.get(key):
            raise NonThinkingPilotError(f"一次性调用证字段漂移：{key}")
    return actual


def _candidate_transport(
    config: dict[str, Any], root: Path, run_dir: Path
) -> api_transport.ApiTransport:
    bundle = _load_bundle(config, root)
    route = api_transport.TransportRoute.from_mapping(bundle.route)
    return api_transport.ApiTransport(
        route=route,
        contracts={EXPECTED_STAGE: candidate_contract(bundle)},
        run_dir=run_dir,
        max_calls=int(config["transport_limits"]["max_network_attempts"]),
        allow_unverified_candidates=True,
    )


def _reasoning_tokens(usage: dict[str, Any]) -> tuple[int, bool]:
    details = usage.get("completion_tokens_details")
    if not isinstance(details, dict) or "reasoning_tokens" not in details:
        return 0, False
    return int(details.get("reasoning_tokens") or 0), True


def _candidate_row(
    *,
    chapter: int,
    materialized: dict[str, Any],
    program_audit: dict[str, Any],
    target: dict[str, Any],
    old_audit: dict[str, Any],
    coverage: dict[str, Any],
    result: api_transport.TransportResult,
) -> dict[str, Any]:
    usage = dict(result.usage)
    reasoning_tokens, reasoning_reported = _reasoning_tokens(usage)
    return {
        "chapter": chapter,
        "status": extraction_method_ab.CHAPTER_STATUS_COMPLETED,
        "event_count": len(materialized.get("events") or []),
        "anchor_reference_count": program_audit["anchor_reference_count"],
        "outside_catalog_anchor_count": len(program_audit["missing_catalog_anchor_ids"]),
        "target": target,
        "old_event_spot_audit": old_audit,
        "audit_segment_total": len(coverage["rows"]),
        "silent_segment_count": coverage["no_event_returned_count"],
        "silent_segment_boundary": coverage["boundary"],
        "finish_reason": result.finish_reason,
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "reasoning_tokens": reasoning_tokens,
        "reasoning_tokens_reported": reasoning_reported,
        "elapsed_ms": int(result.metadata.get("elapsed_ms") or 0),
        "usage": usage,
        "transport_metadata": dict(result.metadata),
    }


def _hard_stop(exc: Exception, *, chapter: int | None) -> dict[str, Any]:
    base = extraction_method_ab.classify_hard_stop(
        exc, phase="chapter_execution" if chapter else "initialization_or_finalize", chapter=chapter
    )
    return dict(base)


def _run_core(config: dict[str, Any], root: Path) -> dict[str, Any]:
    verify_permit(config, root)
    run_dir = _repo_path(root, f"runs/{config['run_id']}")
    if run_dir.exists():
        raise NonThinkingPilotError("运行目录已存在，拒绝复跑或续跑")
    run_dir.mkdir(parents=True)
    saved_preflight = read_json(preflight_path(config, root))
    write_json(run_dir / "config.snapshot.json", config)
    write_json(run_dir / "preflight.snapshot.json", saved_preflight)
    targets, samples = _targets_and_samples(config, root)
    baseline_sources = verify_baseline_event_sources(config, root)
    transport = _candidate_transport(config, root, run_dir)
    rows: list[dict[str, Any]] = []
    hard_stop = None
    attempted_failure_chapter = None
    permit_path = _repo_path(root, config["permit_path"])
    try:
        for chapter in EXPECTED_CHAPTERS:
            built, catalog, chapter_path = build_chapter_input(config, root, chapter)
            write_json(
                run_dir / "inputs" / f"ch{chapter:04d}.json",
                {
                    "chapter": chapter,
                    "chapter_file": _relative(root, chapter_path),
                    "messages": built["messages"],
                    "fingerprints": {key: value for key, value in built.items() if key != "messages"},
                    "single_variable": "请求体省略 reasoning_effort；其他输入等于v1.2默认链",
                },
            )
            write_json(
                run_dir / "evidence_catalogs" / f"ch{chapter:04d}.json",
                {"chapter": chapter, "entries": catalog},
            )
            segment_rows = extraction_method_ab.build_segment_tasks(
                catalog, segment_size=int(config["audit_segment_size"])
            )
            write_json(
                run_dir / "audit_segments" / f"ch{chapter:04d}.json",
                {
                    "chapter": chapter,
                    "rows": segment_rows,
                    "boundary": "只作第40道尺的事后沉默段清点，不进入模型请求。",
                },
            )
            try:
                result = transport.call(
                    stage=EXPECTED_STAGE,
                    case_id=f"{chapter:04d}",
                    messages=built["messages"],
                )
                request_body = result.request_record.get("body") or {}
                if "reasoning_effort" in request_body:
                    raise NonThinkingPilotError("件C请求意外带入 reasoning_effort")
                raw_document = candidate_envelope.parse_json_content(result.content)
                write_json(
                    run_dir / "raw_event_documents" / f"ch{chapter:04d}.json",
                    raw_document,
                )
                materialized, program_audit = neutral_extract.process_model_data(
                    raw_document, chapter=chapter, catalog=catalog
                )
                write_json(run_dir / "events" / f"ch{chapter:04d}.json", materialized)
                write_json(
                    run_dir / "program_audits" / f"ch{chapter:04d}.json", program_audit
                )
                target = extraction_method_ab.evaluate_target(
                    targets[chapter], materialized, catalog
                )
                old_audit = extraction_method_ab.old_event_spot_audit(
                    chapter=chapter,
                    samples=samples[chapter],
                    old_document=read_json(baseline_sources[chapter]),
                    new_document=materialized,
                )
                coverage = extraction_method_ab.method_coverage_ledger(
                    "A", segment_rows, materialized
                )
                write_json(run_dir / "target_audits" / f"ch{chapter:04d}.json", target)
                write_json(
                    run_dir / "old_event_spot_audits" / f"ch{chapter:04d}.json",
                    old_audit,
                )
                write_json(
                    run_dir / "silent_segment_audits" / f"ch{chapter:04d}.json",
                    coverage,
                )
                row = _candidate_row(
                    chapter=chapter,
                    materialized=materialized,
                    program_audit=program_audit,
                    target=target,
                    old_audit=old_audit,
                    coverage=coverage,
                    result=result,
                )
                if row["reasoning_tokens_reported"] and row["reasoning_tokens"] != 0:
                    raise NonThinkingPilotError(
                        f"第 {chapter} 章省略思考参数后仍返回 {row['reasoning_tokens']} reasoning tokens"
                    )
                rows.append(row)
            except Exception as exc:
                attempted_failure_chapter = chapter
                hard_stop = _hard_stop(exc, chapter=chapter)
                write_json(run_dir / "hard_stop.json", hard_stop)
                break
    finally:
        permit_path.unlink(missing_ok=True)

    completed = [row["chapter"] for row in rows]
    failed = [attempted_failure_chapter] if attempted_failure_chapter is not None else []
    chapter_statuses = extraction_method_ab.chapter_status_rows(completed, failed)
    not_called = [
        row["chapter"]
        for row in chapter_statuses
        if row["status"] == extraction_method_ab.CHAPTER_STATUS_NOT_CALLED
    ]
    attempts = extraction_method_ab._attempt_summary(
        run_dir / "call_attempts.jsonl", completed + failed
    )
    completed_all = len(rows) == len(EXPECTED_CHAPTERS) and hard_stop is None
    if completed_all and attempts["status"] != "pass":
        hard_stop = _hard_stop(
            NonThinkingPilotError("调用账不满足五章各一次逻辑采样或总尝试上限"),
            chapter=None,
        )
        write_json(run_dir / "hard_stop.json", hard_stop)
        completed_all = False
    current_default = verify_default_activation(config, root)
    current_outbox = tree_fingerprint(_repo_path(root, "outbox"))
    expected_state = saved_preflight["protected_state"]
    protected_unchanged = (
        current_default["default_registry_sha256"]
        == expected_state["default_registry_sha256"]
        and current_default["commit_marker_sha256"]
        == expected_state["default_commit_marker_sha256"]
        and current_outbox == expected_state["outbox"]
    )
    if completed_all and not protected_unchanged:
        hard_stop = _hard_stop(
            NonThinkingPilotError("默认登记、提交标记或outbox在件C期间发生漂移"),
            chapter=None,
        )
        write_json(run_dir / "hard_stop.json", hard_stop)
        completed_all = False
    candidate_summary = summarize_rows(rows, mode="reasoning_effort_omitted")
    actual_cost = actual_cost_totals(run_dir)
    candidate_summary["cost_from_usage_jsonl"] = actual_cost
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "reasoning_tokens",
        "elapsed_ms",
    ):
        candidate_summary["metrics"][key] = actual_cost[key]
    baseline = saved_preflight["baseline"]
    metrics = candidate_summary["metrics"]
    all_reasoning_reported = len(rows) == len(EXPECTED_CHAPTERS) and all(
        row["reasoning_tokens_reported"] for row in rows
    )
    acceptance = {
        "known_targets": [
            {
                "chapter": row["chapter"],
                "id": row["target"]["id"],
                "label": row["target"]["label"],
                "pass": row["target"]["pass"],
                "missing_anchor_ids": row["target"]["missing_anchor_ids"],
            }
            for row in rows
        ],
        "known_targets_all_hit": completed_all and metrics["target_hits"] == 5,
        "outside_catalog_anchor_zero": completed_all
        and all(row["outside_catalog_anchor_count"] == 0 for row in rows),
        "no_new_technical_failure": completed_all,
        "old_event_spot_check_10_of_10": completed_all
        and metrics["old_event_spot_passes"] == 10,
        "silent_segments_zero": completed_all and metrics["silent_segment_count"] == 0,
        "reasoning_field_omitted_all_requests": completed_all,
        "reasoning_tokens_zero_when_reported": completed_all
        and all(row["reasoning_tokens"] == 0 for row in rows),
        "reasoning_tokens_reported_all_chapters": all_reasoning_reported,
        "winner_not_decided": True,
    }
    acceptance["full_ruler_pass"] = all(
        acceptance[key]
        for key in (
            "known_targets_all_hit",
            "outside_catalog_anchor_zero",
            "no_new_technical_failure",
            "old_event_spot_check_10_of_10",
            "silent_segments_zero",
            "reasoning_field_omitted_all_requests",
            "reasoning_tokens_zero_when_reported",
        )
    )
    result_document = {
        "schema_version": RESULT_SCHEMA,
        "at": now_iso(),
        "status": "completed" if completed_all else "hard_stopped",
        "candidate_status": "pass" if acceptance["full_ruler_pass"] else "fail",
        "batch_id": EXPECTED_BATCH_ID,
        "method": EXPECTED_METHOD,
        "run_id": config["run_id"],
        "chapters_planned": EXPECTED_CHAPTERS,
        "chapters_completed": completed,
        "chapters_failed": failed,
        "chapters_not_called": not_called,
        "chapter_statuses": chapter_statuses,
        "transport": attempts,
        "single_variable": {
            "baseline": "reasoning_effort=medium",
            "candidate": "reasoning_effort字段省略",
            "other_request_body_changes": [],
        },
        "candidate": candidate_summary,
        "baseline": baseline,
        "comparison": {
            "target_hit_delta": metrics["target_hits"] - baseline["metrics"]["target_hits"],
            "old_event_spot_delta": metrics["old_event_spot_passes"]
            - baseline["metrics"]["old_event_spot_passes"],
            "silent_segment_delta": metrics["silent_segment_count"]
            - baseline["metrics"]["silent_segment_count"],
            "total_token_delta": metrics["total_tokens"] - baseline["metrics"]["total_tokens"],
            "reasoning_token_delta": metrics["reasoning_tokens"]
            - baseline["metrics"]["reasoning_tokens"],
            "elapsed_ms_delta": metrics["elapsed_ms"] - baseline["metrics"]["elapsed_ms"],
            "boundary": "旧基线取同一v1.2连续运行链的真实usage行；时间会受服务端负载影响，只登记不判默认。",
        },
        "acceptance": acceptance,
        "protected_state_unchanged": protected_unchanged,
        "hard_stop": hard_stop,
        "cost_accounting": {
            "source": "usage.jsonl",
            "includes_called_failed_chapter": True,
            **actual_cost,
        },
        "api_key_trace_count": extraction_method_ab._key_trace_count(
            run_dir, os.environ.get(api_transport.PINNED_API_KEY_ENV, "")
        ),
        "outbox_written": False,
        "rights": config["rights"],
    }
    write_json(run_dir / "result.json", result_document)
    return result_document


def run(config: dict[str, Any], root: Path) -> dict[str, Any]:
    validate_artifact_paths(config, root)
    run_dir = _repo_path(root, f"runs/{config['run_id']}")
    permit_path = _repo_path(root, config["permit_path"])
    preexisting = run_dir.exists()
    try:
        return _run_core(config, root)
    except Exception as exc:
        hard_stop = _hard_stop(exc, chapter=None)
        if run_dir.exists() and not preexisting:
            recovered = extraction_method_ab.recover_partial_run(run_dir)
            actual_cost = actual_cost_totals(run_dir)
        else:
            recovered = {
                "chapters_completed": [],
                "chapters_failed": [],
                "chapters_not_called": EXPECTED_CHAPTERS,
                "chapter_statuses": extraction_method_ab.chapter_status_rows([], []),
            }
            actual_cost = {
                "usage_row_count": 0,
                "invalid_usage_row_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
                "cached_tokens": 0,
                "elapsed_ms": 0,
            }
        result = {
            "schema_version": RESULT_SCHEMA,
            "at": now_iso(),
            "status": "hard_stopped",
            "candidate_status": "fail",
            "batch_id": config.get("batch_id"),
            "method": config.get("method"),
            "run_id": config.get("run_id"),
            "chapters_planned": EXPECTED_CHAPTERS,
            "chapters_completed": recovered["chapters_completed"],
            "chapters_failed": recovered["chapters_failed"],
            "chapters_not_called": recovered["chapters_not_called"],
            "chapter_statuses": recovered["chapter_statuses"],
            "hard_stop": hard_stop,
            "cost_accounting": {
                "source": "usage.jsonl",
                "includes_called_failed_chapter": True,
                **actual_cost,
            },
            "outbox_written": False,
            "rights": config.get("rights"),
        }
        if run_dir.exists() and not preexisting:
            write_json(run_dir / "hard_stop.json", hard_stop)
            write_json(run_dir / "result.json", result)
        else:
            rejection = _repo_path(
                root,
                f"work/zbatch_nonthinking/rejections/{config.get('batch_id', 'unknown')}.json",
            )
            write_json(rejection, result)
        return result
    finally:
        permit_path.unlink(missing_ok=True)
