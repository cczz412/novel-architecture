#!/usr/bin/env python3
"""MC00a：MiniCPM5-1B 不训练的中性事件 Prompt 上限试点。"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from zbatch_modules import neutral_extract  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402
from zbatch_modules.prompt_render_pin import sha256_file  # noqa: E402


DEFAULT_CONFIG = ROOT / "config/batches/MC00a_X01_第6至10章MiniCPM前置抽取上限_5章_v1.0.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in value.split("."):
        digits = "".join(char for char in piece if char.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def strict_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ZBatchError("MiniCPM 回包不是裸 JSON；不去思考块、不去围栏、不修补") from exc
    if not isinstance(value, dict):
        raise ZBatchError("MiniCPM 回包顶层不是对象")
    return value


def load_catalog(path: Path, chapter: int) -> list[dict[str, Any]]:
    value = read_json(path)
    if not isinstance(value, dict) or value.get("chapter") != chapter:
        raise ZBatchError(f"第 {chapter} 章冻结证据目录外壳错误")
    entries = value.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ZBatchError(f"第 {chapter} 章冻结证据目录为空")
    return entries


def load_config(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ZBatchError("MC00a 配置不是对象")
    return value


def chapter_filename(chapter_dir: Path, chapter: int) -> str:
    matches = sorted(chapter_dir.glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"第 {chapter} 章正文文件应唯一，实际 {len(matches)} 个")
    return matches[0].name


def runtime_version() -> str | None:
    try:
        return importlib.metadata.version("mlx-lm")
    except importlib.metadata.PackageNotFoundError:
        return None


def prestart_resume_allowed(run_dir: Path) -> bool:
    """只允许模型加载前的纯预演目录续开，绝不允许覆盖任何生成工件。"""
    if not run_dir.is_dir():
        return False
    files = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file()
    }
    return bool(files) and files <= {"preflight.json", "config_snapshot.json"}


def preflight(config_path: Path, *, require_runtime: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    chapters = config.get("chapters")
    add("chapters_exactly_6_to_10", chapters == [6, 7, 8, 9, 10], chapters)
    add("no_training", config.get("training") is False, config.get("training"))
    add("one_sample_per_chapter", config.get("samples_per_chapter") == 1, config.get("samples_per_chapter"))
    add("official_model_id", config.get("model_id") == "openbmb/MiniCPM5-1B-MLX", config.get("model_id"))
    add("no_think", config.get("enable_thinking") is False, config.get("enable_thinking"))
    add("stop_boundary_blocks_20_chapters", "不扩20章" in str(config.get("stop_boundary")), config.get("stop_boundary"))

    for raw_path, expected in (config.get("pins") or {}).items():
        path = ROOT / raw_path
        actual = sha256_file(path) if path.is_file() else None
        add(f"pin:{raw_path}", actual == expected, {"expected": expected, "actual": actual})

    source_dir = ROOT / str(config.get("source_catalog_dir"))
    chapter_dir = ROOT / str(config.get("book_chapter_dir"))
    catalog_entry_total = 0
    for chapter in chapters or []:
        catalog_entry_total += len(load_catalog(source_dir / f"ch{chapter:04d}.json", chapter))
        chapter_filename(chapter_dir, chapter)
    add("five_nonempty_catalogs", catalog_entry_total > 0 and len(chapters or []) == 5, {"entries": catalog_entry_total})

    installed = runtime_version()
    minimum = str(config.get("minimum_mlx_lm_version"))
    runtime_ok = installed is not None and version_tuple(installed) >= version_tuple(minimum)
    add("mlx_lm_runtime", runtime_ok if require_runtime else True, {"installed": installed, "minimum": minimum, "required_now": require_runtime})

    passed = all(row["ok"] for row in checks)
    return {
        "at": now_iso(),
        "preflight": "pass" if passed else "fail",
        "model_calls": 0,
        "checks": checks,
        "catalog_entry_total": catalog_entry_total,
        "semantic_score_evaluated": False,
        "evaluation_boundary": config.get("evaluation_boundary"),
    }


def reference_diagnostic(reference: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    reference_events = reference.get("events") if isinstance(reference.get("events"), list) else []
    actual_events = actual.get("events") if isinstance(actual.get("events"), list) else []
    reference_anchor_ids = {
        str(anchor.get("anchor_id"))
        for event in reference_events if isinstance(event, dict)
        for anchor in (event.get("anchors") or []) if isinstance(anchor, dict)
    }
    actual_anchor_ids = {
        str(anchor.get("anchor_id"))
        for event in actual_events if isinstance(event, dict)
        for anchor in (event.get("anchors") or []) if isinstance(anchor, dict)
    }
    union = reference_anchor_ids | actual_anchor_ids
    return {
        "reference_event_count": len(reference_events),
        "actual_event_count": len(actual_events),
        "event_count_delta": len(actual_events) - len(reference_events),
        "reference_unique_anchor_ids": len(reference_anchor_ids),
        "actual_unique_anchor_ids": len(actual_anchor_ids),
        "anchor_id_overlap_count": len(reference_anchor_ids & actual_anchor_ids),
        "anchor_id_jaccard_descriptive_only": (len(reference_anchor_ids & actual_anchor_ids) / len(union)) if union else None,
        "reference_role": "DeepSeek历史结果只作银标描述，不裁判MiniCPM语义对错",
    }


def run(config_path: Path, *, resume_prestart: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    pre = preflight(config_path, require_runtime=True)
    if pre["preflight"] != "pass":
        raise ZBatchError("MC00a 零调用预演未通过，拒绝加载模型")

    run_dir = ROOT / "runs" / str(config["run_id"])
    if run_dir.exists() and any(run_dir.iterdir()):
        if not resume_prestart or not prestart_resume_allowed(run_dir):
            raise ZBatchError(f"运行目录已存在，拒绝重跑挑结果：{run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "preflight.json", pre)
    write_json(run_dir / "config_snapshot.json", config)

    try:
        import mlx.core as mx
        from huggingface_hub import model_info, snapshot_download
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler
    except ImportError as exc:
        raise ZBatchError(f"MiniCPM 本地运行依赖缺失：{exc}") from exc

    model_id = str(config["model_id"])
    info = model_info(model_id)
    revision = str(info.sha)
    hf_home = Path(os.environ.get("HF_HOME") or (ROOT / "TEMP/MiniCPM5-1B_20260718/hf_home"))
    hf_home.mkdir(parents=True, exist_ok=True)
    print(f"MC00a 下载/复用官方模型：{model_id}@{revision[:12]}", flush=True)
    model_path = snapshot_download(repo_id=model_id, revision=revision, cache_dir=str(hf_home / "hub"))
    print("MC00a 正在把模型装入 Apple 芯片内存", flush=True)
    model, tokenizer = load(model_path)
    mx.random.seed(int(config["seed"]))
    sampler = make_sampler(temp=float(config["temperature"]), top_p=float(config["top_p"]))

    source_dir = ROOT / str(config["source_catalog_dir"])
    reference_dir = ROOT / str(config["reference_parsed_dir"])
    chapter_dir = ROOT / str(config["book_chapter_dir"])
    prompt_path = ROOT / str(config["prompt"])
    prompt_sha = str(config["pins"][config["prompt"]])
    chapters = [int(value) for value in config["chapters"]]
    rows: list[dict[str, Any]] = []
    total_prompt_tokens = 0
    total_generation_tokens = 0
    manifest = {
        "run_id": config["run_id"],
        "status": "running",
        "started_at": now_iso(),
        "model_id": model_id,
        "model_revision": revision,
        "backend": "mlx-lm",
        "runtime_version": runtime_version(),
        "training": False,
        "resumed_from_prestart_only": resume_prestart,
    }
    write_json(run_dir / "run_manifest.json", manifest)

    try:
        for chapter in chapters:
            case_id = f"ch{chapter:04d}"
            catalog = load_catalog(source_dir / f"{case_id}.json", chapter)
            built = neutral_extract.build_messages(
                prompt_path=prompt_path,
                expected_prompt_sha256=prompt_sha,
                chapter=chapter,
                chapter_filename=chapter_filename(chapter_dir, chapter),
                catalog=catalog,
            )
            messages = built["messages"]
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            if not isinstance(prompt, str) or not prompt:
                raise ZBatchError(f"第 {chapter} 章聊天模板没有生成文本")
            write_json(
                run_dir / "requests" / f"{case_id}.json",
                {
                    "model_id": model_id,
                    "model_revision": revision,
                    "messages": messages,
                    "rendered_prompt_sha256": __import__("hashlib").sha256(prompt.encode("utf-8")).hexdigest(),
                    "template_sha256": built["template_sha256"],
                    "catalog_sha256": built["catalog_sha256"],
                    "sampling": {
                        "temperature": config["temperature"],
                        "top_p": config["top_p"],
                        "max_tokens": config["max_tokens"],
                        "samples": 1,
                        "enable_thinking": False,
                        "seed": config["seed"],
                    },
                },
            )
            print(f"MC00a 生成 {case_id}：冻结证据 {len(catalog)} 条", flush=True)
            started = time.monotonic()
            chunks: list[str] = []
            last = None
            for response in stream_generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=int(config["max_tokens"]),
                sampler=sampler,
            ):
                chunks.append(response.text)
                last = response
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if last is None:
                raise ZBatchError(f"第 {chapter} 章本地模型没有返回任何 token")
            output_text = "".join(chunks)
            (run_dir / "responses").mkdir(parents=True, exist_ok=True)
            (run_dir / "responses" / f"{case_id}.txt").write_text(output_text, encoding="utf-8")
            finish_reason = last.finish_reason
            write_json(
                run_dir / "responses" / f"{case_id}.meta.json",
                {
                    "finish_reason": finish_reason,
                    "elapsed_ms": elapsed_ms,
                    "prompt_tokens": last.prompt_tokens,
                    "generation_tokens": last.generation_tokens,
                    "generation_tps": last.generation_tps,
                    "peak_memory_gb": last.peak_memory,
                },
            )
            if finish_reason != "stop":
                raise ZBatchError(f"第 {chapter} 章本地生成未正常结束：finish_reason={finish_reason}")
            parsed = strict_json_object(output_text)
            expanded, audit = neutral_extract.process_model_data(parsed, chapter=chapter, catalog=catalog)
            write_json(run_dir / "parsed" / f"{case_id}.json", expanded)
            write_json(run_dir / "program_audits" / f"{case_id}.json", audit)
            reference = read_json(reference_dir / f"{case_id}.json")
            diagnostic = reference_diagnostic(reference, expanded)
            write_json(run_dir / "diagnostics" / f"{case_id}.json", diagnostic)
            event_count = len(expanded.get("events") or [])
            if event_count == 0:
                raise ZBatchError(f"第 {chapter} 章输出为空；按硬闸停止")
            total_prompt_tokens += int(last.prompt_tokens)
            total_generation_tokens += int(last.generation_tokens)
            rows.append(
                {
                    "chapter": chapter,
                    "finish_reason": finish_reason,
                    "events": event_count,
                    "anchor_references": audit["anchor_reference_count"],
                    "missing_catalog_anchor_ids": len(audit["missing_catalog_anchor_ids"]),
                    "invalid_event_ids": audit["invalid_event_id_count"],
                    "elapsed_ms": elapsed_ms,
                    "prompt_tokens": last.prompt_tokens,
                    "generation_tokens": last.generation_tokens,
                    "generation_tps": last.generation_tps,
                    "reference_diagnostic": diagnostic,
                }
            )
    except Exception as exc:
        manifest.update({"status": "failed", "stopped_at": now_iso(), "error": f"{type(exc).__name__}: {exc}", "chapters_completed": len(rows)})
        write_json(run_dir / "run_manifest.json", manifest)
        failure = {
            "run_id": config["run_id"],
            "status": "hard_stop",
            "model_id": model_id,
            "model_revision": revision,
            "chapters_completed": len(rows),
            "chapters_attempted": len(rows) + 1,
            "error": f"{type(exc).__name__}: {exc}",
            "rows": rows,
            "semantic_score_evaluated": False,
            "training": False,
            "expanded_to_20_chapters": False,
            "outbox_written": False,
        }
        write_json(run_dir / "summary.json", failure)
        raise

    summary = {
        "run_id": config["run_id"],
        "status": "pass_mechanical_upper_bound_stop",
        "model_id": model_id,
        "model_revision": revision,
        "backend": "mlx-lm",
        "runtime_version": runtime_version(),
        "chapters_expected": len(chapters),
        "chapters_completed": len(rows),
        "local_model_sample_count": len(rows),
        "retry_count": 0,
        "truncation_count": sum(1 for row in rows if row["finish_reason"] != "stop"),
        "empty_output_chapter_count": sum(1 for row in rows if row["events"] == 0),
        "event_total": sum(int(row["events"]) for row in rows),
        "anchor_reference_total": sum(int(row["anchor_references"]) for row in rows),
        "missing_catalog_anchor_id_count": sum(int(row["missing_catalog_anchor_ids"]) for row in rows),
        "invalid_event_id_count": sum(int(row["invalid_event_ids"]) for row in rows),
        "finish_reason_stop_count": sum(1 for row in rows if row["finish_reason"] == "stop"),
        "prompt_tokens": total_prompt_tokens,
        "generation_tokens": total_generation_tokens,
        "rows": rows,
        "mechanical_acceptance": {"passed": True, "thresholds": config["mechanical_acceptance_prewrite"]},
        "semantic_score_evaluated": False,
        "evaluation_boundary": config["evaluation_boundary"],
        "training": False,
        "prompt_sha256": prompt_sha,
        "pilot_script_sha256": sha256_file(Path(__file__)),
        "neutral_extract_module_sha256": sha256_file(ROOT / "tools/zbatch_modules/neutral_extract.py"),
        "default_promoted": False,
        "expanded_to_20_chapters": False,
        "outbox_written": False,
        "rights": config["rights"],
        "stop_boundary": config["stop_boundary"],
    }
    write_json(run_dir / "summary.json", summary)
    manifest.update({"status": "completed", "completed_at": now_iso(), "summary": "summary.json", "chapters_completed": len(rows)})
    write_json(run_dir / "run_manifest.json", manifest)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="MiniCPM5-1B 中性事件 Prompt 上限试点")
    value.add_argument("command", choices=("preflight", "run"))
    value.add_argument("--config", default=str(DEFAULT_CONFIG))
    value.add_argument("--require-runtime", action="store_true", help="预演时同时检查 mlx-lm >= 0.31")
    value.add_argument("--resume-prestart", action="store_true", help="仅续开尚无任何模型工件的纯预演目录")
    return value


def main() -> int:
    args = parser().parse_args()
    config_path = Path(args.config).resolve()
    try:
        result = (
            preflight(config_path, require_runtime=args.require_runtime)
            if args.command == "preflight"
            else run(config_path, resume_prestart=args.resume_prestart)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("preflight", "pass") == "pass" else 2
    except ZBatchError as exc:
        print(f"HARD_STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
