"""T5：任务前置与正文前置的 SenseNova 缓存小实验。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import api_transport, candidate_envelope, evidence_catalog, neutral_extract, stage_sampling


class T5BenchmarkError(RuntimeError):
    """T5 预演、调用或收口失败。"""


SYSTEM_MESSAGE = neutral_extract.SYSTEM_MESSAGE


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T5BenchmarkError(f"JSON 读取失败：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise T5BenchmarkError(f"JSON 顶层不是对象：{path}")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _path(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise T5BenchmarkError(f"路径越出仓库：{path}") from exc
    return path


def _verify_ref(root: Path, ref: dict[str, Any], label: str) -> Path:
    path = _path(root, str(ref.get("path") or ""))
    actual = sha256_file(path) if path.is_file() else None
    expected = str(ref.get("sha256") or "")
    if not expected or actual != expected:
        raise T5BenchmarkError(f"{label} SHA 漂移：expected={expected}, actual={actual}")
    return path


def _tree_fingerprint(path: Path) -> str:
    rows = []
    for file in sorted(item for item in path.rglob("*") if item.is_file() and item.name != ".DS_Store"):
        rows.append((str(file.relative_to(path)), sha256_file(file), file.stat().st_size))
    payload = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return sha256_bytes(payload.encode("utf-8"))


def _chapter_file(book_dir: Path, chapter: int) -> Path:
    matches = sorted((book_dir / "chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise T5BenchmarkError(f"第 {chapter} 章正文文件数量异常：{len(matches)}")
    return matches[0]


def build_segments(manifest: dict[str, Any], root: Path, chapter: int) -> dict[str, Any]:
    prompt_ref = manifest["source_prompt"]
    prompt_path = _verify_ref(root, prompt_ref, "T5 固定任务来源 Prompt")
    source = prompt_path.read_text(encoding="utf-8")
    marker = str(prompt_ref["fixed_cut_marker"])
    if source.count(marker) != 1:
        raise T5BenchmarkError("T5 固定任务切点不是恰好一个")
    fixed_source, _ = source.split(marker, 1)
    fixed_task = fixed_source.rstrip()
    book_dir = _path(root, manifest["book_dir"])
    chapter_path = _chapter_file(book_dir, chapter)
    text = chapter_path.read_text(encoding="utf-8")
    catalog = evidence_catalog.build_evidence_catalog(chapter, text)
    coverage = evidence_catalog.evidence_catalog_coverage(text, catalog)
    if coverage != 1.0:
        raise T5BenchmarkError(f"第 {chapter} 章证据目录覆盖率不是 100%")
    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    dynamic_payload = (
        "T5动态章节载荷开始\n"
        f"当前章号：`{chapter}`\n\n"
        f"当前章四位号：`{chapter:04d}`\n\n"
        f"当前章文件名：`{chapter_path.name}`\n\n"
        "事件 ID 中的 `{{CHAPTER_PADDED}}` 必须替换为当前章四位号；"
        "JSON 的 `{{CHAPTER_NUMBER}}` 必须替换为当前章整数。\n\n"
        "冻结证据目录：\n\n```json\n"
        f"{catalog_json}\n"
        "```\nT5动态章节载荷结束"
    )
    return {
        "chapter": chapter,
        "experiment_marker": manifest["fixed_experiment_marker"],
        "chapter_path": str(chapter_path.relative_to(root)),
        "chapter_sha256": sha256_file(chapter_path),
        "catalog": catalog,
        "catalog_sha256": sha256_bytes(catalog_json.encode("utf-8")),
        "fixed_task": fixed_task,
        "fixed_task_sha256": sha256_bytes(fixed_task.encode("utf-8")),
        "fixed_task_bytes": len(fixed_task.encode("utf-8")),
        "dynamic_payload": dynamic_payload,
        "dynamic_payload_sha256": sha256_bytes(dynamic_payload.encode("utf-8")),
        "dynamic_payload_bytes": len(dynamic_payload.encode("utf-8")),
    }


def build_messages(segments: dict[str, Any], arm: str) -> list[dict[str, str]]:
    if arm == "A":
        user = f"{segments['fixed_task']}\n\n{segments['dynamic_payload']}"
    elif arm == "B":
        user = f"{segments['dynamic_payload']}\n\n{segments['fixed_task']}"
    else:
        raise T5BenchmarkError(f"未知缓存排法：{arm}")
    return [
        {
            "role": "system",
            "content": f"{segments['experiment_marker']}\n{SYSTEM_MESSAGE}",
        },
        {"role": "user", "content": user},
    ]


def common_prefix_bytes(left: str, right: str) -> int:
    count = 0
    for left_byte, right_byte in zip(left.encode("utf-8"), right.encode("utf-8")):
        if left_byte != right_byte:
            break
        count += 1
    return count


def preflight(manifest: dict[str, Any], root: Path, *, require_fresh_run: bool) -> dict[str, Any]:
    provider_path = _verify_ref(root, manifest["provider"], "provider")
    contract_path = _verify_ref(root, manifest["stage_contract"], "阶段合同")
    for name, ref in manifest["protected_code"].items():
        _verify_ref(root, ref, f"保护代码 {name}")
    provider = read_json(provider_path)
    bundle = stage_sampling.load_contract_bundle(
        contract_path,
        profile=manifest["stage_contract"]["profile"],
    )
    route = api_transport.TransportRoute.from_mapping(bundle.route)
    contract = bundle.stage(manifest["stage_contract"]["stage"])
    book_dir = _path(root, manifest["book_dir"])
    checks = {
        "book_tree_sha256": _tree_fingerprint(book_dir) == manifest["book_tree_sha256"],
        "provider_model": provider.get("model") == "deepseek-v4-flash" == route.model,
        "provider_route": provider.get("base_url") == route.base_url and provider.get("endpoint") == route.endpoint,
        "sampling": {
            "temperature": contract.temperature,
            "max_tokens": contract.max_tokens,
            "n": contract.n,
            "reasoning_effort": contract.reasoning_effort,
            "response_format": dict(contract.response_format),
        }
        == {
            "temperature": 0.2,
            "max_tokens": 16000,
            "n": 1,
            "reasoning_effort": "medium",
            "response_format": {"type": "json_object"},
        },
        "sequence": [row["case_id"] for row in manifest["sequence"]]
        == [
            "A_ch0006_exposure1",
            "B_ch0006_exposure1",
            "A_ch0007_exposure2",
            "B_ch0007_exposure2",
        ],
        "logical_samples": manifest["transport"]["logical_samples"] == 4,
        "network_budget": manifest["transport"]["max_network_attempts"] == 12,
    }
    segment_rows = {}
    for chapter in manifest["chapters"]:
        segments = build_segments(manifest, root, int(chapter))
        arm_a = build_messages(segments, "A")[1]["content"]
        arm_b = build_messages(segments, "B")[1]["content"]
        segment_rows[str(chapter)] = {
            "fixed_task_sha256": segments["fixed_task_sha256"],
            "dynamic_payload_sha256": segments["dynamic_payload_sha256"],
            "same_segments_only_reordered": arm_a
            == f"{segments['fixed_task']}\n\n{segments['dynamic_payload']}"
            and arm_b == f"{segments['dynamic_payload']}\n\n{segments['fixed_task']}",
        }
    checks["same_segments_only_reordered"] = all(
        row["same_segments_only_reordered"] for row in segment_rows.values()
    )
    sample_segments = build_segments(manifest, root, int(manifest["chapters"][0]))
    sample_system = build_messages(sample_segments, "A")[0]["content"]
    checks["experiment_marker_is_common_system_prefix"] = sample_system.startswith(
        manifest["fixed_experiment_marker"]
    )
    run_dir = _path(root, f"runs/{manifest['run_id']}")
    checks["fresh_run_dir"] = not run_dir.exists() if require_fresh_run else True
    status = "pass" if all(value is True for value in checks.values()) else "fail"
    return {
        "schema_version": "z-t5-cache-preflight-v1",
        "status": status,
        "model_calls": 0,
        "checks": checks,
        "segments": segment_rows,
    }


def normalize_cache_usage(usage: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens_raw = usage.get("prompt_tokens")
    prompt_tokens = (
        prompt_tokens_raw
        if isinstance(prompt_tokens_raw, int) and not isinstance(prompt_tokens_raw, bool) and prompt_tokens_raw > 0
        else None
    )
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    native_hit = details.get("prompt_cache_hit_tokens")
    native_miss = details.get("prompt_cache_miss_tokens")
    cached = details.get("cached_tokens")
    measured = True
    invalid_reason = None
    if isinstance(native_hit, int):
        hit = native_hit
        hit_source = "prompt_tokens_details.prompt_cache_hit_tokens"
    elif isinstance(cached, int):
        hit = cached
        hit_source = "prompt_tokens_details.cached_tokens"
    else:
        measured = False
        hit = None
        hit_source = "missing_not_measured"
        invalid_reason = "供应商未返回可识别的缓存命中字段"
    if prompt_tokens is None:
        measured = False
        invalid_reason = "供应商未返回有效的输入 token 总数"
    if isinstance(hit, int) and isinstance(prompt_tokens, int) and (hit < 0 or hit > prompt_tokens):
        measured = False
        invalid_reason = "缓存命中 token 小于0或大于输入 token"
    if isinstance(native_miss, int):
        miss = native_miss
        miss_source = "prompt_tokens_details.prompt_cache_miss_tokens"
    elif measured and isinstance(hit, int) and isinstance(prompt_tokens, int):
        miss = prompt_tokens - hit
        miss_source = "derived:prompt_tokens-hit_tokens"
    else:
        miss = None
        miss_source = "not_measured"
    if isinstance(miss, int) and (
        miss < 0 or hit is None or prompt_tokens is None or hit + miss != prompt_tokens
    ):
        measured = False
        invalid_reason = "缓存命中与未命中 token 无法还原输入 token"
    return {
        "measured": measured,
        "invalid_reason": invalid_reason,
        "prompt_tokens": prompt_tokens,
        "prompt_cache_hit_tokens": hit,
        "prompt_cache_miss_tokens": miss,
        "hit_field_source": hit_source,
        "miss_field_source": miss_source,
        "native_prompt_tokens_details": details,
    }


def _request_paths(run_dir: Path, case_id: str) -> tuple[Path, Path, Path]:
    return (
        run_dir / "requests/neutral_extract" / f"{case_id}_request.json",
        run_dir / "responses/neutral_extract" / f"{case_id}_raw.json",
        run_dir / "responses/neutral_extract" / f"{case_id}_meta.json",
    )


def run_benchmark(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    pre = preflight(manifest, root, require_fresh_run=True)
    if pre["status"] != "pass":
        raise T5BenchmarkError(f"T5 零调用预演未过：{pre['checks']}")
    run_dir = _path(root, f"runs/{manifest['run_id']}")
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "preflight.json", pre)
    write_json(run_dir / "benchmark_manifest.json", manifest)
    contract_path = _path(root, manifest["stage_contract"]["path"])
    bundle = stage_sampling.load_contract_bundle(
        contract_path,
        profile=manifest["stage_contract"]["profile"],
    )
    transport = api_transport.ApiTransport.from_bundle(
        bundle,
        run_dir=run_dir,
        max_calls=int(manifest["transport"]["max_network_attempts"]),
    )
    rows = []
    messages_by_case: dict[str, list[dict[str, str]]] = {}
    for case in manifest["sequence"]:
        chapter = int(case["chapter"])
        segments = build_segments(manifest, root, chapter)
        messages = build_messages(segments, str(case["arm"]))
        messages_by_case[str(case["case_id"])] = messages
        result = transport.call(
            stage="neutral_extract",
            case_id=str(case["case_id"]),
            messages=messages,
        )
        raw_document = candidate_envelope.parse_json_content(result.content)
        materialized, audit = neutral_extract.process_model_data(
            raw_document,
            chapter=chapter,
            catalog=segments["catalog"],
        )
        output_path = run_dir / "outputs" / f"{case['case_id']}.json"
        audit_path = run_dir / "program_audits" / f"{case['case_id']}.json"
        catalog_path = run_dir / "catalogs" / f"ch{chapter:04d}.json"
        write_json(output_path, materialized)
        write_json(audit_path, audit)
        if not catalog_path.exists():
            write_json(catalog_path, {"chapter": chapter, "entries": segments["catalog"]})
        request_path, raw_path, meta_path = _request_paths(run_dir, str(case["case_id"]))
        meta = read_json(meta_path)
        normalized = normalize_cache_usage(dict(result.usage))
        row = {
            **case,
            "http_status": meta.get("http_status"),
            "finish_reason": meta.get("finish_reason"),
            "response_model": meta.get("response_model"),
            "elapsed_ms": meta.get("elapsed_ms"),
            "usage": dict(result.usage),
            "cache": normalized,
            "completion_tokens": int(result.usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(
                (result.usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            ),
            "event_count": len(materialized.get("events") or []),
            "anchor_reference_count": audit.get("anchor_reference_count"),
            "request_sha256": sha256_file(request_path),
            "raw_response_sha256": sha256_file(raw_path),
            "response_meta_sha256": sha256_file(meta_path),
            "output_sha256": sha256_file(output_path),
            "program_audit_sha256": sha256_file(audit_path),
            "fixed_task_sha256": segments["fixed_task_sha256"],
            "fixed_task_bytes": segments["fixed_task_bytes"],
            "dynamic_payload_sha256": segments["dynamic_payload_sha256"],
            "dynamic_payload_bytes": segments["dynamic_payload_bytes"],
            "system_sha256": sha256_bytes(messages[0]["content"].encode("utf-8")),
            "system_bytes": len(messages[0]["content"].encode("utf-8")),
            "active_output_contract": manifest["output_contract_authority"],
        }
        rows.append(row)
    attempt_rows = [
        json.loads(line)
        for line in (run_dir / "call_attempts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    attempts_by_case: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempt_rows:
        attempts_by_case.setdefault(str(attempt.get("case_id")), []).append(attempt)
    for row in rows:
        case_attempts = attempts_by_case.get(str(row["case_id"]), [])
        row["actual_network_attempts"] = len(case_attempts)
        row["retries"] = max(0, len(case_attempts) - 1)
        row["network_attempt_sequence"] = [attempt.get("attempt") for attempt in case_attempts]
        write_json(run_dir / "receipts" / f"{row['case_id']}.json", row)
    key = os.environ.get("SENSENOVA_API_KEY", "")
    key_trace_count = 0
    if key:
        key_bytes = key.encode("utf-8")
        for file in (item for item in run_dir.rglob("*") if item.is_file()):
            key_trace_count += file.read_bytes().count(key_bytes)
    by_case = {str(row["case_id"]): row for row in rows}
    a_first = by_case["A_ch0006_exposure1"]
    b_first = by_case["B_ch0006_exposure1"]
    a_second = by_case["A_ch0007_exposure2"]
    b_second = by_case["B_ch0007_exposure2"]
    a_prefix = common_prefix_bytes(
        messages_by_case["A_ch0006_exposure1"][1]["content"],
        messages_by_case["A_ch0007_exposure2"][1]["content"],
    )
    b_prefix = common_prefix_bytes(
        messages_by_case["B_ch0006_exposure1"][1]["content"],
        messages_by_case["B_ch0007_exposure2"][1]["content"],
    )
    a_hit = a_second["cache"]["prompt_cache_hit_tokens"]
    b_hit = b_second["cache"]["prompt_cache_hit_tokens"]
    cache_fields_measured = all(row["cache"]["measured"] for row in rows)
    retry_free = transport.calls_made == 4 and all(row["actual_network_attempts"] == 1 for row in rows)
    performance_verdict_allowed = cache_fields_measured and retry_free
    if not performance_verdict_allowed:
        cache_signal = "withheld_due_to_retry_or_unmeasured_cache_fields"
    elif a_hit > b_hit:
        cache_signal = "A_task_first_observed_more_cache_hits"
    elif a_hit < b_hit:
        cache_signal = "B_text_first_observed_more_cache_hits"
    elif a_hit == 0:
        cache_signal = "no_cache_hit_observed_in_either_arm"
    else:
        cache_signal = "equal_cache_hits_in_both_arms"
    summary = {
        "schema_version": "z-t5-cache-layout-result-v1",
        "status": "completed",
        "model_calls": len(rows),
        "network_attempts": transport.calls_made,
        "model": "deepseek-v4-flash",
        "sequence": [row["case_id"] for row in rows],
        "single_variable_audit": {
            "same_fixed_task_sha_across_all": len({row["fixed_task_sha256"] for row in rows}) == 1,
            "same_dynamic_payload_for_same_chapter": (
                a_first["dynamic_payload_sha256"] == b_first["dynamic_payload_sha256"]
                and a_second["dynamic_payload_sha256"] == b_second["dynamic_payload_sha256"]
            ),
            "only_segment_order_differs_between_arms": True,
            "call_order_interleaved": True,
            "system_sha_identical": len({row["system_sha256"] for row in rows}) == 1,
        },
        "common_user_prefix_bytes": {"A_task_first": a_prefix, "B_text_first": b_prefix},
        "second_exposure_comparison": {
            "A_task_first": {
                "prompt_cache_hit_tokens": a_hit,
                "prompt_cache_miss_tokens": a_second["cache"]["prompt_cache_miss_tokens"],
                "elapsed_ms": a_second["elapsed_ms"],
            },
            "B_text_first": {
                "prompt_cache_hit_tokens": b_hit,
                "prompt_cache_miss_tokens": b_second["cache"]["prompt_cache_miss_tokens"],
                "elapsed_ms": b_second["elapsed_ms"],
            },
            "observed_signal": cache_signal,
            "performance_verdict_allowed": performance_verdict_allowed,
            "retry_free_four_attempt_gate": retry_free,
            "cache_fields_measured_gate": cache_fields_measured,
        },
        "first_exposure_comparison": {
            "A_elapsed_ms": a_first["elapsed_ms"],
            "B_elapsed_ms": b_first["elapsed_ms"],
            "A_cache_hit_tokens": a_first["cache"]["prompt_cache_hit_tokens"],
            "B_cache_hit_tokens": b_first["cache"]["prompt_cache_hit_tokens"],
        },
        "cases": rows,
        "key_trace_count": key_trace_count,
        "contract_boundary": manifest["output_contract_authority"],
        "interpretation_boundary": manifest["interpretation_boundary"],
    }
    write_json(run_dir / "result.json", summary)
    return summary
