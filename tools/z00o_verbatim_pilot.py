#!/usr/bin/env python3
"""Z00o：用模块化运输层执行温度 0.1 原样复述单变量轮。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from zbatch_modules import api_transport, stage_sampling, verbatim_restatement  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402
from zbatch_modules.prompt_render_pin import sha256_file  # noqa: E402


DEFAULT_CONFIG = ROOT / "config/batches/Z00o_X01_第6至10章原样复述温度0.1_5章_v1.0.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def strict_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ZBatchError("原样复述回包不是裸 JSON；不去围栏、不修补") from exc
    if not isinstance(value, dict):
        raise ZBatchError("原样复述回包顶层不是对象")
    return value


def source_for_chapter(parsed: dict[str, Any], chapter: int) -> dict[str, Any]:
    if parsed.get("chapter") != chapter:
        raise ZBatchError(f"复述来源章号错误：期望 {chapter}")
    events = parsed.get("events")
    if not isinstance(events, list) or not events:
        raise ZBatchError(f"第 {chapter} 章复述来源为空")
    items: list[dict[str, str]] = []
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict):
            raise ZBatchError(f"第 {chapter} 章来源事件 {index} 不是对象")
        item_id = event.get("event_id")
        source_text = event.get("event")
        if not isinstance(item_id, str) or not isinstance(source_text, str) or not source_text:
            raise ZBatchError(f"第 {chapter} 章来源事件 {index} 缺编号或正文")
        items.append(
            {
                "item_id": item_id,
                "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                "source_text": source_text,
            }
        )
    source = {"schema_version": verbatim_restatement.INPUT_SCHEMA_VERSION, "items": items}
    reasons = verbatim_restatement.validate_input(source)
    if reasons:
        raise ZBatchError(f"第 {chapter} 章复述来源无效：{reasons}")
    return source


def load_config(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ZBatchError("Z00o 配置不是对象")
    return value


def preflight(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    chapters = config.get("chapters")
    add("chapters_exactly_6_to_10", chapters == [6, 7, 8, 9, 10], chapters)
    add("one_request_per_chapter", config.get("one_request_per_chapter") is True, config.get("one_request_per_chapter"))
    add("candidate_override_explicitly_approved", config.get("approved_candidate_override") is True, config.get("decision"))
    add("stop_boundary_blocks_20_chapters", "不扩20章" in str(config.get("stop_boundary")), config.get("stop_boundary"))

    for raw_path, expected in (config.get("pins") or {}).items():
        path = ROOT / raw_path
        actual = sha256_file(path) if path.is_file() else None
        add(f"pin:{raw_path}", actual == expected, {"expected": expected, "actual": actual})

    contract_path = ROOT / str(config.get("stage_sampling_contract"))
    bundle = stage_sampling.load_contract_bundle(contract_path, profile=str(config.get("stage_sampling_profile")))
    candidate = bundle.candidates[str(config.get("stage"))]
    add("model_is_deepseek_v4_flash", bundle.route.get("model") == "deepseek-v4-flash", bundle.route.get("model"))
    add(
        "sampling_is_exact_0_1_n1_8000",
        (candidate.temperature, candidate.n, candidate.max_tokens, candidate.status)
        == (0.1, 1, 8000, stage_sampling.CANDIDATE_STATUS),
        {
            "temperature": candidate.temperature,
            "n": candidate.n,
            "max_tokens": candidate.max_tokens,
            "status": candidate.status,
        },
    )

    source_dir = ROOT / str(config.get("source_parsed_dir"))
    event_total = 0
    for chapter in chapters or []:
        source = source_for_chapter(read_json(source_dir / f"ch{chapter:04d}.json"), chapter)
        event_total += len(source["items"])
    add("five_nonempty_source_chapters", event_total > 0 and len(chapters or []) == 5, {"items": event_total})

    passed = all(row["ok"] for row in checks)
    return {
        "at": now_iso(),
        "preflight": "pass" if passed else "fail",
        "model_calls": 0,
        "checks": checks,
        "source_item_total": event_total,
        "global_three_gates": {
            "evaluated": False,
            "status": "not_reached",
            "reason": "原样复述不产出A/B/C/D候选，不能拿组件验票替代扩大三闸",
            "prewritten_thresholds": config.get("global_three_gates_prewrite"),
        },
    }


def usage_totals(run_dir: Path) -> dict[str, int]:
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    path = run_dir / "usage.jsonl"
    if not path.is_file():
        return totals
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        usage = (json.loads(line).get("usage") or {})
        for key in totals:
            value = usage.get(key)
            if isinstance(value, int):
                totals[key] += value
    return totals


def attempt_rows(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "call_attempts.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def secret_trace_count(run_dir: Path, key: str) -> int:
    if not key:
        return 0
    needle = key.encode("utf-8")
    count = 0
    for path in run_dir.rglob("*"):
        if path.is_file() and needle in path.read_bytes():
            count += 1
    return count


def run(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    pre = preflight(config_path)
    if pre["preflight"] != "pass":
        raise ZBatchError("Z00o 零调用预演未通过，拒绝真实调用")
    key = os.environ.get("SENSENOVA_API_KEY", "")
    if not key:
        raise ZBatchError("缺少 SENSENOVA_API_KEY")

    run_dir = ROOT / "runs" / str(config["run_id"])
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ZBatchError(f"运行目录已存在，拒绝重跑挑结果：{run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "preflight.json", pre)
    write_json(run_dir / "config_snapshot.json", config)

    contract_path = ROOT / str(config["stage_sampling_contract"])
    bundle = stage_sampling.load_contract_bundle(contract_path, profile=str(config["stage_sampling_profile"]))
    stage = str(config["stage"])
    candidate = bundle.candidates[stage]
    transport = api_transport.ApiTransport(
        route=api_transport.TransportRoute.from_mapping(bundle.route),
        contracts={stage: candidate},
        run_dir=run_dir,
        max_calls=int(config["max_attempt_calls"]),
        allow_unverified_candidates=True,
    )
    prompt_path = ROOT / str(config["prompt"])
    prompt_sha = str((config["pins"])[config["prompt"]])
    source_dir = ROOT / str(config["source_parsed_dir"])
    chapters = [int(value) for value in config["chapters"]]
    chapter_rows: list[dict[str, Any]] = []
    total_items = 0

    manifest = {
        "run_id": config["run_id"],
        "status": "running",
        "started_at": now_iso(),
        "model": bundle.route.get("model"),
        "stage": stage,
        "temperature": candidate.temperature,
        "n": candidate.n,
        "candidate_override": True,
    }
    write_json(run_dir / "run_manifest.json", manifest)
    try:
        for chapter in chapters:
            case_id = f"ch{chapter:04d}"
            source = source_for_chapter(read_json(source_dir / f"{case_id}.json"), chapter)
            total_items += len(source["items"])
            write_json(run_dir / "inputs" / f"{case_id}.json", source)
            built = verbatim_restatement.build_messages(
                source,
                prompt_path=prompt_path,
                expected_prompt_sha256=prompt_sha,
            )
            write_json(
                run_dir / "prepared" / f"{case_id}.json",
                {name: value for name, value in built.items() if name != "messages"},
            )
            print(f"Z00o 调用 {case_id}：{len(source['items'])} 条", flush=True)
            result = transport.call(stage=stage, case_id=case_id, messages=built["messages"])
            output = strict_json_object(result.content)
            reasons = verbatim_restatement.output_reasons(output, source)
            write_json(run_dir / "parsed" / f"{case_id}.json", output)
            write_json(
                run_dir / "verification" / f"{case_id}.json",
                {
                    "chapter": chapter,
                    "item_count": len(source["items"]),
                    "exact": not reasons,
                    "reasons": reasons,
                    "finish_reason": result.finish_reason,
                },
            )
            if reasons:
                raise ZBatchError(f"第 {chapter} 章原样复述验票失败：{reasons}；不做修补")
            chapter_rows.append(
                {
                    "chapter": chapter,
                    "item_count": len(source["items"]),
                    "exact_item_count": len(source["items"]),
                    "finish_reason": result.finish_reason,
                    "elapsed_ms": result.metadata.get("elapsed_ms"),
                    "retry_count": 0,
                }
            )
    except Exception as exc:
        manifest.update({"status": "failed", "stopped_at": now_iso(), "error": f"{type(exc).__name__}: {exc}"})
        write_json(run_dir / "run_manifest.json", manifest)
        raise

    attempts = attempt_rows(run_dir)
    retry_count = sum(1 for row in attempts if int(row.get("attempt") or 0) > 1)
    per_case_attempts: dict[str, int] = {}
    for row in attempts:
        per_case_attempts[str(row.get("case_id"))] = per_case_attempts.get(str(row.get("case_id")), 0) + 1
    for row in chapter_rows:
        row["retry_count"] = max(0, per_case_attempts.get(f"ch{int(row['chapter']):04d}", 1) - 1)

    summary = {
        "run_id": config["run_id"],
        "status": "pass_component_stop",
        "model": bundle.route.get("model"),
        "stage": stage,
        "temperature": candidate.temperature,
        "n": candidate.n,
        "chapters_expected": len(chapters),
        "chapters_completed": len(chapter_rows),
        "model_sample_count": len(chapter_rows),
        "transport_attempt_count": len(attempts),
        "retry_count": retry_count,
        "truncation_count": sum(1 for row in chapter_rows if row["finish_reason"] != "stop"),
        "empty_input_chapter_count": 0,
        "source_item_total": total_items,
        "exact_item_total": sum(int(row["exact_item_count"]) for row in chapter_rows),
        "exact_item_copy_rate": 1.0,
        "changed_missing_reordered_item_count": 0,
        "finish_reason_stop_count": sum(1 for row in chapter_rows if row["finish_reason"] == "stop"),
        "chapter_transport": chapter_rows,
        "usage": usage_totals(run_dir),
        "component_acceptance": {
            "passed": True,
            "thresholds": config["component_acceptance_prewrite"],
        },
        "global_three_gates": pre["global_three_gates"],
        "runner_sha256": sha256_file(ROOT / "tools/zbatch.py"),
        "pilot_script_sha256": sha256_file(Path(__file__)),
        "verbatim_module_sha256": sha256_file(ROOT / "tools/zbatch_modules/verbatim_restatement.py"),
        "transport_module_sha256": sha256_file(ROOT / "tools/zbatch_modules/api_transport.py"),
        "sampling_contract_sha256": sha256_file(contract_path),
        "prompt_sha256": prompt_sha,
        "plaintext_secret_trace_file_count": secret_trace_count(run_dir, key),
        "default_promoted": False,
        "expanded_to_20_chapters": False,
        "outbox_written": False,
        "old_monolith_deleted": False,
        "silver_used_as_judge": False,
        "rights": config["rights"],
        "stop_boundary": config["stop_boundary"],
    }
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "transport_observation.json", {"chapters": chapter_rows, "totals": {
        "attempts": len(attempts), "retries": retry_count, "truncations": 0, "empty_chapters": 0
    }})
    manifest.update({"status": "completed", "completed_at": now_iso(), "summary": "summary.json"})
    write_json(run_dir / "run_manifest.json", manifest)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Z00o 原样复述温度 0.1 单变量轮")
    value.add_argument("command", choices=("preflight", "run"))
    value.add_argument("--config", default=str(DEFAULT_CONFIG))
    return value


def main() -> int:
    args = parser().parse_args()
    config_path = Path(args.config).resolve()
    try:
        result = preflight(config_path) if args.command == "preflight" else run(config_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("preflight", "pass") == "pass" else 2
    except ZBatchError as exc:
        print(f"HARD_STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
