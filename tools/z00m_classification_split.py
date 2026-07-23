#!/usr/bin/env python3
"""Z00m 分类收权复跑入口。

Z00m 继续复用 Z00l 的中性事件提取与主控分类实现，只加三道施工护栏：

1. 运输参数独立钉死：extract max_tokens=16000、reasoning_effort=medium、n=1；
2. Prompt 与分类规则必须保持 Z00l 已封存 SHA；
3. 第 6～10 章五份解析件齐套并逐份验票后，才允许进入分类层。

本文件不改 Z00l 原适配器，也不接入 D-MOD 新模块。
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import zbatch  # noqa: E402
import z00l_classification_split as legacy  # noqa: E402


EXPECTED_BATCH = "Z00m"
EXPECTED_ITEM = "X01"
EXPECTED_CHAPTER_RANGE = (6, 10)
EXPECTED_CHAPTERS = 5
EXPECTED_STAGES = ["event_extract", "classify", "verify"]
EXPECTED_MODEL = "deepseek-v4-flash"
EXPECTED_TEMPERATURE = 0.2
EXPECTED_REASONING_EFFORT = "medium"
EXPECTED_EXTRACT_MAX_TOKENS = 16000
EXPECTED_N = 1
EXPECTED_PROMPT_SHA256 = "9beb1bfd83863cc39b3e899a706a9dc60fb901ef47547ae859bda2720a9a411c"
EXPECTED_RULES_SHA256 = "95ded675da3dac0fb3a7102c64175f1102eeea23af269f7cbed285d8cb21b804"
EXPECTED_Z00L_ADAPTER_SHA256 = "7a28e1c151b0d0f21aede010eeace5ba3cc54f1b8003e06869397e516f8504ec"
DEFAULT_PROMPT_SHA256 = "b5f30ab1e3e9cae7870db6bf2a951448d391981c0cfb257bd577686bd0a2c6b9"
PARSED_NAME = re.compile(r"^ch(?P<chapter>\d{4})\.json$")


class Z00mRunContext(zbatch.RunContext):
    """只给 Z00m 使用的运输覆写；旧运行器源码和其他批次请求保持不变。"""

    def call_json(self, *, stage: str, case_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        provider = self.provider
        if provider.get("provider") != zbatch.SENSENOVA_PROVIDER:
            raise zbatch.ZBatchError("运行器只允许 provider=sensenova")
        if (
            provider.get("base_url") != zbatch.SENSENOVA_BASE_URL
            or provider.get("endpoint") != zbatch.SENSENOVA_ENDPOINT
        ):
            raise zbatch.ZBatchError("SenseNova 路由与钉死地址不一致，拒绝调用")
        model = str(provider.get("model") or "")
        if model not in zbatch.ALLOWED_TEXT_MODELS:
            raise zbatch.ZBatchError(f"模型不在文字白名单：{model}")
        key_env = str(provider.get("api_key_env") or "")
        key = os.environ.get(key_env)
        if not key:
            raise zbatch.ZBatchError(f"缺少 {key_env}；先载入 SenseNova 环境脚本")

        sample_count = int(provider.get("n", 0))
        if sample_count != EXPECTED_N:
            raise zbatch.ZBatchError(f"Z00m 采样合同只允许 n=1，收到：{sample_count}")
        max_tokens = int((provider.get("max_tokens_by_stage") or {}).get(stage, 8000))
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(provider.get("temperature", 0.2)),
            "max_tokens": max_tokens,
            "n": sample_count,
            "response_format": {"type": "json_object"},
        }
        effort = str(provider.get("reasoning_effort") or "").strip()
        if effort and effort.lower() not in {"omit", "off", "-"}:
            body["reasoning_effort"] = effort

        request_record = {
            "provider": zbatch.SENSENOVA_PROVIDER,
            "api_base_url": zbatch.SENSENOVA_BASE_URL,
            "api_endpoint": zbatch.SENSENOVA_ENDPOINT,
            "stage": stage,
            "case_id": case_id,
            "body": body,
            "_security": "no_api_key_no_authorization",
        }
        request_path = self.run_dir / "requests" / stage / f"{case_id}_request.json"
        zbatch.write_json(request_path, request_record)
        request_sha = zbatch.sha256_file(request_path)

        attempts = int(provider.get("network_attempts", 3))
        timeout = int(provider.get("timeout_seconds", 600))
        url = zbatch.SENSENOVA_BASE_URL + zbatch.SENSENOVA_ENDPOINT
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            if self.calls_made >= self.max_calls:
                raise zbatch.ZBatchError(f"调用闸已满：{self.calls_made}/{self.max_calls}，拒绝多发一次")
            self.calls_made += 1
            attempt_row = {
                "at": zbatch.now_iso(),
                "call_number": self.calls_made,
                "max_calls": self.max_calls,
                "stage": stage,
                "case_id": case_id,
                "attempt": attempt,
                "request_sha256": request_sha,
            }
            zbatch.append_jsonl(self.run_dir / "call_attempts.jsonl", attempt_row)
            request = urllib.request.Request(
                url,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
            started = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read()
                    status = getattr(response, "status", None)
                    safe_headers = {
                        name: value
                        for name, value in response.headers.items()
                        if name.lower() in {"content-type", "date", "x-request-id", "request-id"}
                    }
                if key.encode("utf-8") in raw:
                    raise zbatch.ZBatchError("服务端响应意外回显 API Key；原始响应拒绝落盘")
                elapsed_ms = int((time.monotonic() - started) * 1000)
                raw_path = self.run_dir / "responses" / stage / f"{case_id}_raw.json"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(raw)
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise zbatch.ZBatchError(f"HTTP 成功但响应不是 JSON：{case_id}") from exc
                if not isinstance(data, dict):
                    raise zbatch.ZBatchError(f"HTTP 成功但响应顶层不是对象：{case_id}")
                content, finish_reason = zbatch.response_content(data)
                metadata = {
                    "at": zbatch.now_iso(),
                    "http_status": status,
                    "elapsed_ms": elapsed_ms,
                    "provider": zbatch.SENSENOVA_PROVIDER,
                    "api_base_url": zbatch.SENSENOVA_BASE_URL,
                    "api_endpoint": zbatch.SENSENOVA_ENDPOINT,
                    "requested_model": model,
                    "response_model": data.get("model"),
                    "finish_reason": finish_reason,
                    "request_sha256": request_sha,
                    "raw_response_sha256": zbatch.sha256_bytes(raw),
                    "headers": safe_headers,
                    "sampling_n": sample_count,
                }
                zbatch.write_json(self.run_dir / "responses" / stage / f"{case_id}_meta.json", metadata)
                usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                zbatch.append_jsonl(
                    self.run_dir / "usage.jsonl",
                    {**metadata, "stage": stage, "case_id": case_id, "usage": usage},
                )
                return zbatch.parse_json_content(content)
            except urllib.error.HTTPError as exc:
                last_error = exc
                error_body = exc.read() if hasattr(exc, "read") else b""
                zbatch.write_text(
                    self.run_dir / "errors" / f"{stage}_{case_id}_attempt{attempt}.txt",
                    (
                        f"HTTP {exc.code}\n"
                        f"error_body_bytes={len(error_body)}\n"
                        f"error_body_sha256={zbatch.sha256_bytes(error_body)}\n"
                        "error_body_not_persisted=security_policy\n"
                    ),
                )
                retryable = exc.code == 429 or exc.code >= 500
                if not retryable or attempt >= attempts:
                    break
            except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, ConnectionError) as exc:
                last_error = exc
                partial = exc.partial if isinstance(exc, http.client.IncompleteRead) else b""
                zbatch.write_text(
                    self.run_dir / "errors" / f"{stage}_{case_id}_attempt{attempt}.txt",
                    (
                        f"{type(exc).__name__}: {exc}\n"
                        f"partial_bytes={len(partial)}\n"
                        f"partial_sha256={zbatch.sha256_bytes(partial)}\n"
                        "partial_body_not_persisted=security_and_integrity_policy\n"
                    ),
                )
                if attempt >= attempts:
                    break
            if attempt < attempts:
                time.sleep(min(2 * attempt, 6))
        raise zbatch.ZBatchError(f"API 调用失败：{stage}/{case_id}：{last_error}")


def z00m_preflight(config_path: Path, *, require_key: bool = False) -> dict[str, Any]:
    """在原 zbatch 零调用预演上追加 Z00m 的运输与封存护栏。"""
    result = zbatch.preflight(config_path, require_key=require_key)
    batch, provider = zbatch.load_configs(config_path)
    checks = list(result.get("checks") or [])

    zbatch.add_check(checks, "z00m_batch", batch.get("batch_id") == EXPECTED_BATCH, batch.get("batch_id"))
    zbatch.add_check(checks, "z00m_item", batch.get("item_id") == EXPECTED_ITEM, batch.get("item_id"))
    zbatch.add_check(
        checks,
        "z00m_chapter_range",
        (batch.get("chapter_start"), batch.get("chapter_end"), batch.get("expected_chapters"))
        == (*EXPECTED_CHAPTER_RANGE, EXPECTED_CHAPTERS),
        [batch.get("chapter_start"), batch.get("chapter_end"), batch.get("expected_chapters")],
    )
    zbatch.add_check(checks, "z00m_stages", batch.get("stages") == EXPECTED_STAGES, batch.get("stages"))
    zbatch.add_check(checks, "z00m_model", provider.get("model") == EXPECTED_MODEL, provider.get("model"))
    zbatch.add_check(
        checks,
        "z00m_temperature",
        float(provider.get("temperature", -1)) == EXPECTED_TEMPERATURE,
        provider.get("temperature"),
    )
    zbatch.add_check(
        checks,
        "z00m_reasoning_effort",
        provider.get("reasoning_effort") == EXPECTED_REASONING_EFFORT,
        provider.get("reasoning_effort"),
    )
    zbatch.add_check(checks, "z00m_n", provider.get("n") == EXPECTED_N, provider.get("n"))
    extract_max = (provider.get("max_tokens_by_stage") or {}).get("extract")
    zbatch.add_check(
        checks,
        "z00m_extract_max_tokens",
        extract_max == EXPECTED_EXTRACT_MAX_TOKENS,
        extract_max,
    )

    prompts = batch.get("prompts") if isinstance(batch.get("prompts"), dict) else {}
    prompt_path = zbatch.root_path(str(prompts.get("event_extract") or ""))
    rules_path = zbatch.root_path(str(prompts.get("classifier_rules") or ""))
    prompt_sha = zbatch.sha256_file(prompt_path) if prompt_path.is_file() else "missing"
    rules_sha = zbatch.sha256_file(rules_path) if rules_path.is_file() else "missing"
    zbatch.add_check(checks, "z00m_prompt_sha", prompt_sha == EXPECTED_PROMPT_SHA256, prompt_sha)
    zbatch.add_check(checks, "z00m_rules_sha", rules_sha == EXPECTED_RULES_SHA256, rules_sha)

    legacy_path = TOOLS_DIR / "z00l_classification_split.py"
    legacy_sha = zbatch.sha256_file(legacy_path) if legacy_path.is_file() else "missing"
    zbatch.add_check(
        checks,
        "z00l_adapter_unchanged",
        legacy_sha == EXPECTED_Z00L_ADAPTER_SHA256,
        legacy_sha,
    )
    default_prompt = zbatch.root_path("work/zbatch_prompts/extract_v1.3.md")
    default_sha = zbatch.sha256_file(default_prompt) if default_prompt.is_file() else "missing"
    zbatch.add_check(checks, "default_extract_unchanged", default_sha == DEFAULT_PROMPT_SHA256, default_sha)

    run_id = str(batch.get("run_id") or "")
    zbatch.add_check(checks, "z00m_new_run_id", run_id.startswith("Z00m_"), run_id)
    outbox_path = zbatch.OUTBOX_DIR / run_id
    zbatch.add_check(checks, "z00m_outbox_absent", not outbox_path.exists(), zbatch.rel(outbox_path))

    result["checks"] = checks
    result["preflight"] = "pass" if all(item.get("ok") for item in checks) else "fail"
    result["model_calls"] = 0
    result["z00m_contract"] = {
        "legacy_pipeline": "tools/z00l_classification_split.py",
        "transport_only_changes": {
            "extract_max_tokens": EXPECTED_EXTRACT_MAX_TOKENS,
            "reasoning_effort": EXPECTED_REASONING_EFFORT,
            "n": EXPECTED_N,
        },
        "five_parsed_files_before_classification": True,
        "classification_model_calls": 0,
        "d_mod_modules_connected": False,
    }
    return result


def expected_parsed_files(batch: dict[str, Any]) -> list[str]:
    start = int(batch.get("chapter_start", 0))
    end = int(batch.get("chapter_end", 0))
    return [f"ch{chapter:04d}.json" for chapter in range(start, end + 1)]


def verify_complete_event_set(run_dir: Path, batch: dict[str, Any]) -> dict[str, Any]:
    """五份解析件齐套、回执未漂移、展开锚与目录逐字一致才放行。"""
    parsed_dir = run_dir / "01_event_extract" / "parsed"
    actual_paths = sorted(parsed_dir.glob("ch[0-9][0-9][0-9][0-9].json"))
    actual_names = [path.name for path in actual_paths]
    expected_names = expected_parsed_files(batch)
    if actual_names != expected_names:
        raise zbatch.ZBatchError(f"中性事件解析件未齐套：expected={expected_names},actual={actual_names}")

    total_events = 0
    total_anchors = 0
    for path in actual_paths:
        match = PARSED_NAME.fullmatch(path.name)
        if match is None:
            raise zbatch.ZBatchError(f"中性事件解析件文件名非法：{path.name}")
        chapter = int(match.group("chapter"))
        data = zbatch.read_json(path)
        if data.get("chapter") != chapter or data.get("schema_version") != legacy.EVENT_SCHEMA_VERSION:
            raise zbatch.ZBatchError(f"第 {chapter} 章中性事件解析件身份错误")

        receipt_path = zbatch.receipt_path(path)
        if not receipt_path.is_file():
            raise zbatch.ZBatchError(f"第 {chapter} 章中性事件解析件缺回执")
        receipt = zbatch.read_json(receipt_path)
        if receipt.get("stage") != "extract":
            raise zbatch.ZBatchError(f"第 {chapter} 章中性事件回执阶段错误")
        zbatch._verify_receipt_hashes(receipt)

        catalog_path = run_dir / "01_event_extract" / "evidence_catalogs" / f"ch{chapter:04d}.json"
        catalog_data = zbatch.read_json(catalog_path)
        catalog = {
            str(row.get("anchor_id")): str(row.get("quote"))
            for row in catalog_data.get("entries") or []
            if isinstance(row, dict) and row.get("anchor_id") and row.get("quote")
        }
        if not catalog or catalog_data.get("coverage") != 1.0:
            raise zbatch.ZBatchError(f"第 {chapter} 章冻结证据目录不完整")

        events = data.get("events")
        if not isinstance(events, list):
            raise zbatch.ZBatchError(f"第 {chapter} 章 events 不是数组")
        expected_ids = [f"EV-C{chapter:04d}-{index:02d}" for index in range(1, len(events) + 1)]
        actual_ids = [event.get("event_id") for event in events if isinstance(event, dict)]
        if actual_ids != expected_ids:
            raise zbatch.ZBatchError(f"第 {chapter} 章事件 ID 不连续")
        for event in events:
            if not isinstance(event, dict) or set(event) != legacy.EVENT_KEYS:
                raise zbatch.ZBatchError(f"第 {chapter} 章事件外壳漂移")
            anchors = event.get("anchors")
            if not isinstance(anchors, list) or not anchors:
                raise zbatch.ZBatchError(f"{event.get('event_id')} 没有展开锚")
            for anchor in anchors:
                if not isinstance(anchor, dict) or set(anchor) != {"chapter", "anchor_id", "quote"}:
                    raise zbatch.ZBatchError(f"{event.get('event_id')} 展开锚字段错误")
                anchor_id = str(anchor.get("anchor_id"))
                if anchor.get("chapter") != chapter or catalog.get(anchor_id) != anchor.get("quote"):
                    raise zbatch.ZBatchError(f"{event.get('event_id')} 展开锚与目录不一致")
                total_anchors += 1
        total_events += len(events)

    return {
        "chapters": len(actual_paths),
        "chapter_files": actual_names,
        "events": total_events,
        "anchors": total_anchors,
        "complete": True,
    }


def _run_legacy(function: Callable[..., dict[str, Any]], *args: Any) -> dict[str, Any]:
    """只在当前调用内替换预演入口，Z00l 源文件和行为实现保持原样。"""
    original_preflight = legacy.z00l_preflight
    original_context = zbatch.RunContext
    legacy.z00l_preflight = z00m_preflight
    zbatch.RunContext = Z00mRunContext
    try:
        return function(*args)
    finally:
        legacy.z00l_preflight = original_preflight
        zbatch.RunContext = original_context


def extract_events(config_path: Path) -> dict[str, Any]:
    result = _run_legacy(legacy.extract_events, config_path)
    batch, _ = zbatch.load_configs(config_path)
    run_dir = zbatch.RUNS_DIR / str(batch.get("run_id"))
    complete = verify_complete_event_set(run_dir, batch)
    zbatch.write_json(run_dir / "01_event_extract" / "complete_set_check.json", complete)
    result.setdefault("results", {})["complete_set_check"] = complete
    return result


def classify_and_verify(config_path: Path, decisions_path: Path) -> dict[str, Any]:
    batch, _ = zbatch.load_configs(config_path)
    run_dir = zbatch.RUNS_DIR / str(batch.get("run_id"))
    complete = verify_complete_event_set(run_dir, batch)
    zbatch.write_json(run_dir / "01_event_extract" / "complete_set_check.json", complete)
    result = _run_legacy(legacy.classify_and_verify, config_path, decisions_path)
    report_path = run_dir / "03_verify" / "程序核锚报告.md"
    if report_path.is_file():
        text = report_path.read_text(encoding="utf-8").replace("# Z00l 程序核锚报告", "# Z00m 程序核锚报告", 1)
        report_path.write_text(text, encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Z00m 分类收权单变量复跑入口")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight", help="零调用预演")
    pre.add_argument("--config", required=True)
    extract = sub.add_parser("extract", help="按旧路径抽中性事件")
    extract.add_argument("--config", required=True)
    classify = sub.add_parser("classify", help="五章齐套后主控分类并核锚")
    classify.add_argument("--config", required=True)
    classify.add_argument("--decisions", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config_path = zbatch.root_path(args.config)
        if args.command == "preflight":
            result = z00m_preflight(config_path, require_key=False)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("preflight") == "pass" else 2
        if args.command == "extract":
            result = extract_events(config_path)
        elif args.command == "classify":
            result = classify_and_verify(config_path, Path(args.decisions))
        else:  # pragma: no cover
            raise zbatch.ZBatchError(f"未知命令：{args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except zbatch.ZBatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
