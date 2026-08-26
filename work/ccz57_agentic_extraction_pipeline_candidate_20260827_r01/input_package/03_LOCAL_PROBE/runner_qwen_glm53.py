#!/usr/bin/env python3
"""Qwen3.8-max + OpenRouter GLM-5.3-Flash thinking A/B. Same frozen Prompt/items."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tl_runner", HERE / "runner_thinking_low.py")
tl = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tl)

QWEN_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen3.8-max"
OR_BASE = "https://openrouter.ai/api/v1"
OR_MODEL = "z-ai/glm-5.3-flash"


def http_json(method: str, url: str, key: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int = tl.TIMEOUT):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    if data is not None:
        tl.assert_no_secret(data, key, "request body")
    hdrs = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return getattr(resp, "status", 200), resp.read(), False
    except urllib.error.HTTPError as exc:
        return int(exc.code), (exc.read() if hasattr(exc, "read") else b""), False
    except TimeoutError:
        return 0, b"", True


def extract_ids(parsed: Any) -> list[str]:
    return tl.extract_http_ids(parsed)


def elapsed(started: str, ended: str) -> int | None:
    try:
        return int((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds() * 1000)
    except ValueError:
        return None


def run_items(lane: str, stub: str, base: str, key: str, model: str, expected: str, extra_headers: dict[str, str], body_for, catalog_name: str, effort_note: str, catalog_must_contain: str, receipt_prefix: str = "15") -> dict[str, Any]:
    prompt, schema, by_id = tl.load_frozen()
    status, raw, timed_out = http_json("GET", f"{base}/models", key, headers=extra_headers, timeout=180)
    tl.assert_no_secret(raw, key, "catalog")
    try:
        parsed = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    ids = extract_ids(parsed)
    tl.write_json(
        tl.FROZEN / catalog_name,
        {
            "http_status": status,
            "timed_out": timed_out,
            "n": len(ids),
            "has_target": catalog_must_contain in ids,
            "raw_sha256": tl.sha256_bytes(raw),
            "raw_bytes": len(raw),
        },
        key,
        overwrite=True,
    )
    print(f"CATALOG {lane} status={status} n={len(ids)} has={catalog_must_contain in ids}")
    if status != 200 or timed_out or catalog_must_contain not in ids:
        tl.die(f"{lane} catalog failed or {catalog_must_contain} missing")

    stop = None
    items: dict[str, Any] = {}
    calls = 0
    for item_id in ("Q1", "Q2", "Q3", "Q4"):
        user = (tl.FROZEN / f"user_message_{item_id}.md").read_text(encoding="utf-8")
        if tl.sha256_bytes(user.encode()) != tl.USER_SHA[item_id]:
            tl.die("user sha mismatch")
        input_sha = by_id[item_id]["input_material_sha256"] if "input_material_sha256" in by_id[item_id] else by_id[item_id]["input_sha256"]
        req_path = tl.REQUESTS / f"{stub}_{item_id}.json"
        meta_path = tl.RESPONSES / f"{stub}_{item_id}.meta.json"
        if req_path.exists() and not meta_path.exists():
            stop = {"item_id": item_id, "crashed_after_request_no_retry": True}
            print(f"STOP {lane} {item_id} request exists without meta; retry=0")
            break
        if req_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            print(f"SKIP {lane} {item_id} already on disk")
            items[item_id] = meta
            calls += 1
            if meta.get("identity_drift") or meta.get("timed_out") or meta.get("http_status") not in (200, None):
                stop = {"item_id": item_id, "resume_stop": True}
                break
            continue
        body = body_for(prompt, user)
        tl.write_json(
            req_path,
            {
                "item_id": item_id,
                "lane": lane,
                "request_model_name": model,
                "expected_response_model": expected,
                "frozen_prompt_sha256": tl.PROMPT_SHA,
                "input_material_sha256": input_sha,
                "user_message_sha256": tl.USER_SHA[item_id],
                "retries": 0,
                "effort_note": effort_note,
                "body": body,
                "_security": "no_api_key",
            },
            key,
        )
        started = tl.now_iso()
        status, raw, timed_out = http_json("POST", f"{base}/chat/completions", key, body, extra_headers)
        ended = tl.now_iso()
        calls += 1
        tl.assert_no_secret(raw, key, f"{item_id} response")
        tl.write_bytes(tl.RAW / f"{stub}_{item_id}.stdout.bin", raw, key)
        envelope = None
        try:
            envelope = json.loads(raw.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            envelope = None
        response_model = None
        content = None
        usage: dict[str, Any] = {}
        finish = None
        message: dict[str, Any] = {}
        err = None
        if isinstance(envelope, dict):
            response_model = envelope.get("model")
            usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
            err = envelope.get("error")
            choices = envelope.get("choices") if isinstance(envelope.get("choices"), list) else []
            first = choices[0] if choices and isinstance(choices[0], dict) else {}
            finish = first.get("finish_reason")
            message = first.get("message") if isinstance(first.get("message"), dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
        analysis = tl.analyze_content(content, schema)
        identity_drift = response_model != expected
        think = tl.thinking_from_usage_and_message(usage, message, envelope if isinstance(envelope, dict) else {})
        meta = {
            "item_id": item_id,
            "lane": lane,
            "request_model_name": model,
            "response_model_name": response_model,
            "identity_drift": identity_drift,
            "http_status": status,
            "timed_out": timed_out,
            "finish_reason": finish,
            "error_type": (err.get("type") if isinstance(err, dict) else None),
            "error_message": (err.get("message") if isinstance(err, dict) else None),
            "started_at": started,
            "ended_at": ended,
            "elapsed_ms": elapsed(started, ended),
            "retries": 0,
            "usage": usage,
            "thinking": think,
            "analysis": analysis,
            "raw_sha256": tl.sha256_bytes(raw),
        }
        tl.write_json(meta_path, meta, key)
        print(
            f"CALL {lane} {item_id} status={status} model={response_model} "
            f"drift={identity_drift} json={analysis['direct_json']} schema={analysis['schema_legal']} "
            f"think={think['thinking_appears_on']} rt={think['reasoning_tokens']}"
        )
        items[item_id] = meta
        if identity_drift or timed_out or status != 200:
            stop = {
                "item_id": item_id,
                "identity_drift": identity_drift,
                "timeout": timed_out,
                "http_status": status,
                "error_message": meta.get("error_message"),
            }
            break
    receipt = {
        "lane": lane,
        "git_head": tl.GIT_HEAD,
        "request_model_id": model,
        "expected_response_model": expected,
        "effort_note": effort_note,
        "calls": calls,
        "stop_reason": stop,
        "status": "COMPLETED" if calls == 4 and stop is None else "STOPPED",
        "items": {
            k: {
                "direct_json": v["analysis"]["direct_json"],
                "schema_legal": v["analysis"]["schema_legal"],
                "thinking_appears_on": v["thinking"]["thinking_appears_on"],
                "reasoning_tokens": v["thinking"]["reasoning_tokens"],
                "identity_drift": v["identity_drift"],
                "http_status": v.get("http_status"),
                "q4_causal": bool(v["analysis"]["q4_causal_hits"]) if k == "Q4" else None,
                "empty_speaker": (v["analysis"]["schema"] or {}).get("empty_speaker"),
                "usage": v["usage"],
                "elapsed_ms": v.get("elapsed_ms"),
                "error_message": v.get("error_message"),
            }
            for k, v in items.items()
        },
        "retries": 0,
    }
    tl.write_json(tl.OUT / f"{receipt_prefix}_{lane}_partial.json", receipt, key, overwrite=True)
    return receipt


def qwen_body(mode: str, prompt: str, user: str, max_tokens: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if mode == "nonthinking":
        body["enable_thinking"] = False
        body["response_format"] = {"type": "json_object"}
    else:
        body["enable_thinking"] = True
        body["reasoning_effort"] = "low"
        # vendor family: thinking + json_object is a documented conflict; Prompt still requires JSON
    return body


def glm_body(mode: str, prompt: str, user: str, max_tokens: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": OR_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if mode == "nonthinking":
        body["reasoning"] = {"effort": "none"}
    else:
        body["reasoning"] = {"enabled": True, "effort": "low"}
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=("qwen", "glm53flash"), required=True)
    parser.add_argument("--mode", choices=("nonthinking", "thinking_low", "both"), default="both")
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--thinking-stub-prefix", default="tl_")
    parser.add_argument("--receipt-prefix", default="15")
    parser.add_argument("--timeout", type=int, default=420)
    args = parser.parse_args()
    tl.TIMEOUT = args.timeout
    modes = ("nonthinking", "thinking_low") if args.mode == "both" else (args.mode,)
    max_tokens = args.max_output_tokens
    if args.lane == "qwen":
        key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not key:
            tl.die("missing DASHSCOPE_API_KEY", 1)
        for mode in modes:
            stub = "qwen38_max" if mode == "nonthinking" else f"{args.thinking_stub_prefix}qwen38_max"
            note = (
                "enable_thinking=false + json_object"
                if mode == "nonthinking"
                else "enable_thinking=true reasoning_effort=low; no thinking_budget; no json_object"
            )
            run_items(
                lane=f"qwen_{mode}",
                stub=stub,
                base=QWEN_BASE,
                key=key,
                model=QWEN_MODEL,
                expected=QWEN_MODEL,
                extra_headers={},
                body_for=lambda p, u, m=mode: qwen_body(m, p, u, max_tokens),
                catalog_name="live_catalog_qianwen_models_ab_20260827.json",
                effort_note=note,
                catalog_must_contain=QWEN_MODEL,
                receipt_prefix=args.receipt_prefix,
            )
    else:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            tl.die("missing OPENROUTER_API_KEY", 1)
        headers = {
            "HTTP-Referer": "https://github.com/cczz412/novel-architecture",
            "X-Title": "ccz57-l1-probe",
        }
        for mode in modes:
            stub = "glm53_flash_openrouter" if mode == "nonthinking" else f"{args.thinking_stub_prefix}glm53_flash_openrouter"
            note = (
                "OpenRouter reasoning.effort=none; catalog says mandatory=true"
                if mode == "nonthinking"
                else "OpenRouter reasoning.effort=low; lowest ON; not max"
            )
            run_items(
                lane=f"glm53flash_{mode}",
                stub=stub,
                base=OR_BASE,
                key=key,
                model=OR_MODEL,
                expected=OR_MODEL,
                extra_headers=headers,
                body_for=lambda p, u, m=mode: glm_body(m, p, u, max_tokens),
                catalog_name="live_catalog_openrouter_glm53_ab_20260827.json",
                effort_note=note,
                catalog_must_contain=OR_MODEL,
                receipt_prefix=args.receipt_prefix,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
