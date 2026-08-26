#!/usr/bin/env python3
"""CCZ-57 L1: SenseNova 6.8 Flash Lite + Ling-3.0-flash, non-thinking, frozen 4 items.

Does not overwrite Doubao / official Flash / Agent Plan batch2 artifacts.
Retries = 0. Never writes API keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

OUT = Path(__file__).resolve().parent
FROZEN = OUT / "frozen"
REQUESTS = OUT / "requests"
RESPONSES = OUT / "responses"
RAW = RESPONSES / "raw"

PROMPT_SHA = "57ab1d68a4ebe3ee4bc7c57693247e9fa7bc1879252b57254ff25b0220bd2a2b"
SCHEMA_SHA = "aa73696981b3b75717202db117ffac4df7584aad1dd3a086084f1c33a1f08352"
USER_SHA = {
    "Q1": "a44a5696ac4e5d6579e16abb58ea39e874e74d8281fd2137c7495270ade27313",
    "Q2": "261916a394434a876f13764f9452ee6764a87bbaf16bf4400b4e9db049c5a600",
    "Q3": "514d0d82468e60aebe486778e9cbf130bb3e75913c3e91cbbde8c27bc96445c1",
    "Q4": "70e345c4cd7aaf3dbec59b67c6ff1b2685ecc8701b45700d97d1ad878fd58682",
}
INPUT_SHA = {
    "Q1": "e8bdbb3db916f2170225f906e8d0ca78268b0f05b018338aa694aa4d62785c72",
    "Q2": "f3793e9dbbfd7d01b1515beac438185ea57902b7038f6bd925d2c88461ac5d1b",
    "Q3": "537d8f1735f3a610b92bbc8180e18be525f834d96737954bc1963693f9e94ad0",
    "Q4": "4673ac4abe647ef475d0007c25b4f4f5eae1ea04c80091610dca02936bfc8c33",
}
# Fix Q1 SHA below after verify — do not ship a typo.
INPUT_SHA["Q1"] = "e8bdbb3db916f2170225f906e8d0ca78268b0f05b018338aa694aa4d62785e72"

TIMEOUT_SECONDS = 180
MAX_CALLS = 4
GIT_HEAD = "8872887690fd018474a69979016b428f2c2faf56"

PROVIDERS = {
    "sensenova": {
        "provider": "sensenova",
        "display": "SenseNova 6.8 Flash",
        "key_env": "SENSENOVA_API_KEY",
        "base_url": "https://token.sensenova.cn/v1",
        "catalog_path": "frozen/live_catalog_sensenova_models_20260827.json",
        "file_stem": "sensenova_6_8_flash_lite",
        "preferred_ids": ["sensenova-6.8-flash", "sensenova-6.8-flash-lite"],
        "forbidden_fallback": ["sensenova-6.7-flash-lite", "deepseek-v4-flash"],
    },
    "ant_ling": {
        "provider": "ant_ling",
        "display": "Ling-3.0-flash",
        "key_env": "ANT_LING_API_KEY",
        "base_url": "https://api.ant-ling.com/v1",
        "catalog_path": "frozen/live_catalog_ant_ling_models_20260827.json",
        "file_stem": "ant_ling_3_0_flash",
        "preferred_ids": ["Ling-3.0-flash"],
        "forbidden_fallback": ["Ling-3.0-tiny", "Ling-2.6-flash", "Ling-2.6-1T"],
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def assert_no_secret(blob: bytes | str, key: str, where: str) -> None:
    text = blob if isinstance(blob, str) else blob.decode("utf-8", "replace")
    raw = blob if isinstance(blob, bytes) else blob.encode("utf-8")
    if key and (key in text or key.encode("utf-8") in raw):
        die(f"secret leaked into {where}; refuse to write or send")


def write_bytes(path: Path, data: bytes, key: str) -> None:
    assert_no_secret(data, key, str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        die(f"refuse to overwrite existing {path}")
    path.write_bytes(data)


def write_json(path: Path, data: Any, key: str) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    write_bytes(path, text.encode("utf-8"), key)


def http_json(
    *,
    method: str,
    url: str,
    key: str,
    body: dict[str, Any] | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> tuple[int, bytes, dict[str, str], bool]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    if data is not None:
        assert_no_secret(data, key, "request body")
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = getattr(resp, "status", 200)
            safe_headers = {
                name: value
                for name, value in resp.headers.items()
                if name.lower()
                in {"content-type", "date", "x-request-id", "request-id"}
            }
            return status, raw, safe_headers, False
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        return int(exc.code), raw, {}, False
    except TimeoutError:
        return 0, b"", {}, True


def extract_model_ids(parsed: Any) -> list[str]:
    ids: list[str] = []
    if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
        rows = parsed["data"]
    elif isinstance(parsed, list):
        rows = parsed
    else:
        rows = []
    for row in rows:
        if isinstance(row, dict):
            for field in ("id", "model", "model_id", "name"):
                value = row.get(field)
                if isinstance(value, str) and value and value not in ids:
                    ids.append(value)
                    break
        elif isinstance(row, str) and row not in ids:
            ids.append(row)
    return ids


def choose_sensenova_model(model_ids: list[str]) -> tuple[str, str]:
    if "sensenova-6.8-flash" in model_ids:
        return "sensenova-6.8-flash", "live_catalog_exact_6.8_flash"
    if "sensenova-6.8-flash-lite" in model_ids:
        return (
            "sensenova-6.8-flash-lite",
            "CZ said 6.8flash; official Token Plan 6.8 Flash product currently is Flash Lite; stronger 6.8 Flash listed as coming soon; not a 6.7 swap",
        )
    die(f"no SenseNova 6.8 Flash id in live catalog; ids={model_ids}")
    raise AssertionError("unreachable")


def strip_fence(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def schema_report(obj: Any, schema: dict[str, Any]) -> dict[str, Any]:
    errors = list(Draft202012Validator(schema).iter_errors(obj))
    empty_speaker = 0
    omitted_speaker = 0
    facts = obj.get("facts") if isinstance(obj, dict) else None
    if isinstance(facts, list):
        for fact in facts:
            if isinstance(fact, dict):
                if "speaker" not in fact:
                    omitted_speaker += 1
                elif fact.get("speaker") == "":
                    empty_speaker += 1
    first = errors[0].message if errors else None
    return {
        "schema_legal": not errors,
        "error_count": len(errors),
        "first_error": first,
        "empty_speaker": empty_speaker,
        "omitted_speaker": omitted_speaker,
        "fact_count": len(facts) if isinstance(facts, list) else None,
    }


def causal_hits(facts: list[Any]) -> list[str]:
    keys = ("因为", "因", "所以", "导致", "于是", "使得")
    hits: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        text = fact.get("fact")
        if isinstance(text, str) and any(k in text for k in keys):
            hits.append(text)
    return hits


def build_body(provider_id: str, model: str, prompt: str, user: str) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user},
    ]
    if provider_id == "sensenova":
        return {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 4096,
            "reasoning_effort": "none",
            "response_format": {"type": "json_object"},
        }
    if provider_id == "ant_ling":
        return {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 4096,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
        }
    die(f"unknown provider {provider_id}")
    raise AssertionError("unreachable")


def thinking_off_evidence(provider_id: str, envelope: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {"checked": False}
    usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
    details = usage.get("completion_tokens_details")
    reasoning_tokens = None
    if isinstance(details, dict):
        reasoning_tokens = details.get("reasoning_tokens")
    choices = envelope.get("choices") if isinstance(envelope.get("choices"), list) else []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    reasoning = None
    if isinstance(message, dict):
        for field in ("reasoning_content", "reasoning"):
            value = message.get(field)
            if isinstance(value, str) and value.strip():
                reasoning = field
                break
    return {
        "checked": True,
        "reasoning_tokens": reasoning_tokens,
        "nonempty_reasoning_field": reasoning,
        "thinking_appears_on": bool(
            (isinstance(reasoning_tokens, int) and reasoning_tokens > 0) or reasoning
        ),
    }


def run_provider(provider_id: str) -> dict[str, Any]:
    cfg = PROVIDERS[provider_id]
    key = os.environ.get(cfg["key_env"], "")
    if not key:
        die(f"missing {cfg['key_env']}", 1)

    prompt_path = FROZEN / "system_prompt_novel_fact_extraction_v2.md"
    schema_path = FROZEN / "novel_fact_extraction_v2.schema.json"
    prompt = prompt_path.read_text(encoding="utf-8")
    if sha256_bytes(prompt.encode("utf-8")) != PROMPT_SHA:
        die("frozen prompt sha mismatch")
    schema_bytes = schema_path.read_bytes()
    if sha256_bytes(schema_bytes) != SCHEMA_SHA:
        die("frozen schema sha mismatch")
    schema = json.loads(schema_bytes.decode("utf-8"))
    items_meta = json.loads((OUT / "01_合成题面.json").read_text(encoding="utf-8"))["items"]
    by_id = {row["item_id"]: row for row in items_meta}

    catalog_started = now_iso()
    status, raw, headers, timed_out = http_json(
        method="GET",
        url=f"{cfg['base_url']}/models",
        key=key,
        timeout=60,
    )
    catalog_ended = now_iso()
    assert_no_secret(raw, key, "catalog response")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    model_ids = extract_model_ids(parsed) if parsed is not None else []
    catalog_obj: Any
    if isinstance(parsed, dict) or isinstance(parsed, list):
        catalog_obj = {"model_ids_only": True, "ids": model_ids}
    else:
        catalog_obj = {"unparsed": True, "http_status": status, "bytes": len(raw)}
    write_json(
        OUT / cfg["catalog_path"],
        {
            "fetched_at_start": catalog_started,
            "fetched_at_end": catalog_ended,
            "http_status": status,
            "timed_out": timed_out,
            "headers": headers,
            "model_ids": model_ids,
            "raw_sha256": sha256_bytes(raw),
            "raw_bytes": len(raw),
            "summary": catalog_obj,
        },
        key,
    )
    print(f"CATALOG {provider_id} status={status} n_ids={len(model_ids)} sha={sha256_bytes(raw)}")
    if status != 200 or timed_out:
        die(f"{provider_id} live catalog failed; stop before sampling")

    if provider_id == "sensenova":
        model, model_note = choose_sensenova_model(model_ids)
    else:
        model = "Ling-3.0-flash"
        if model not in model_ids:
            die(f"{model} not in live catalog {model_ids}; stop before sampling")
        model_note = "live_catalog_exact"
    expected = model
    print(f"SELECTED {provider_id} model={model} note={model_note}")

    calls_made = 0
    stop_reason = None
    item_rows: dict[str, Any] = {}
    for item_id in ("Q1", "Q2", "Q3", "Q4"):
        if calls_made >= MAX_CALLS:
            die("call cap reached")
        user_path = FROZEN / f"user_message_{item_id}.md"
        user = user_path.read_text(encoding="utf-8")
        user_sha = sha256_bytes(user.encode("utf-8"))
        if user_sha != USER_SHA[item_id]:
            die(f"{item_id} user message sha mismatch")
        input_sha = by_id[item_id]["input_sha256"]
        if input_sha != INPUT_SHA[item_id]:
            die(f"{item_id} input sha mismatch")

        body = build_body(provider_id, model, prompt, user)
        stem = cfg["file_stem"]
        request_record = {
            "item_id": item_id,
            "provider": cfg["provider"],
            "transport": "POST /chat/completions",
            "base_url": cfg["base_url"],
            "request_model_name": model,
            "expected_response_model": expected,
            "model_selection_note": model_note,
            "frozen_prompt_sha256": PROMPT_SHA,
            "input_material_sha256": input_sha,
            "user_message_sha256": user_sha,
            "retries": 0,
            "sampling": {
                "temperature": 0,
                "thinking": (
                    {"reasoning_effort": "none"}
                    if provider_id == "sensenova"
                    else {"type": "disabled"}
                ),
                "text_format": "json_object",
                "max_tokens": 4096,
            },
            "body": body,
            "_security": "no_api_key_no_authorization",
        }
        write_json(REQUESTS / f"{stem}_{item_id}.json", request_record, key)

        started = now_iso()
        calls_made += 1
        status, raw, headers, timed_out = http_json(
            method="POST",
            url=f"{cfg['base_url']}/chat/completions",
            key=key,
            body=body,
        )
        ended = now_iso()
        assert_no_secret(raw, key, f"{item_id} response")
        write_bytes(RAW / f"{stem}_{item_id}.stdout.bin", raw, key)

        envelope_ok = False
        task_ok = False
        fenced_ok = False
        envelope_err = None
        task_err = None
        response_model = None
        content = None
        usage: dict[str, Any] = {}
        finish_reason = None
        identity_drift = False
        auth_failure = status in {401, 403}
        truncated = False
        schema_direct: dict[str, Any] | None = None
        schema_fenced: dict[str, Any] | None = None
        facts_preview: list[str] = []
        causal: list[str] = []
        thinking_ev: dict[str, Any] = {"checked": False}
        try:
            envelope = json.loads(raw.decode("utf-8"))
            envelope_ok = isinstance(envelope, dict)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            envelope = None
            envelope_err = type(exc).__name__
        if envelope_ok and isinstance(envelope, dict):
            response_model = envelope.get("model")
            usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
            choices = envelope.get("choices") if isinstance(envelope.get("choices"), list) else []
            first = choices[0] if choices and isinstance(choices[0], dict) else {}
            finish_reason = first.get("finish_reason")
            message = first.get("message") if isinstance(first.get("message"), dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                texts = [
                    block.get("text")
                    for block in content
                    if isinstance(block, dict) and isinstance(block.get("text"), str)
                ]
                content = "".join(texts) if texts else json.dumps(content, ensure_ascii=False)
            if response_model != expected:
                identity_drift = True
            if finish_reason == "length":
                truncated = True
            thinking_ev = thinking_off_evidence(provider_id, envelope)
            if isinstance(content, str) and content.strip():
                try:
                    task = json.loads(content)
                    task_ok = True
                    schema_direct = schema_report(task, schema)
                    if isinstance(task, dict) and isinstance(task.get("facts"), list):
                        facts_preview = [
                            row.get("fact")
                            for row in task["facts"]
                            if isinstance(row, dict) and isinstance(row.get("fact"), str)
                        ]
                        causal = causal_hits(task["facts"])
                except json.JSONDecodeError as exc:
                    task_err = type(exc).__name__
                    stripped = strip_fence(content)
                    if stripped != content.strip():
                        try:
                            task = json.loads(stripped)
                            fenced_ok = True
                            schema_fenced = schema_report(task, schema)
                            if isinstance(task, dict) and isinstance(task.get("facts"), list):
                                facts_preview = [
                                    row.get("fact")
                                    for row in task["facts"]
                                    if isinstance(row, dict) and isinstance(row.get("fact"), str)
                                ]
                                causal = causal_hits(task["facts"])
                        except json.JSONDecodeError:
                            pass
            else:
                task_err = "empty_or_non_string_content"

        elapsed_ms = None
        try:
            t0 = datetime.fromisoformat(started)
            t1 = datetime.fromisoformat(ended)
            elapsed_ms = int((t1 - t0).total_seconds() * 1000)
        except ValueError:
            pass

        schema_legal = bool(schema_direct and schema_direct.get("schema_legal"))
        item_rows[item_id] = {
            "http_status": status,
            "direct_json": task_ok,
            "fenced_json": fenced_ok,
            "schema_legal": schema_legal,
            "schema_legal_after_fence": bool(
                schema_fenced and schema_fenced.get("schema_legal")
            ),
            "schema_direct": schema_direct,
            "schema_fenced": schema_fenced,
            "empty_speaker": (schema_direct or schema_fenced or {}).get("empty_speaker"),
            "omitted_speaker": (schema_direct or schema_fenced or {}).get("omitted_speaker"),
            "fact_count": (schema_direct or schema_fenced or {}).get("fact_count"),
            "facts_preview": facts_preview,
            "q4_causal_hits": causal if item_id == "Q4" else [],
            "thinking": thinking_ev,
            "response_model": response_model,
            "finish_reason": finish_reason,
            "identity_drift": identity_drift,
            "truncated": truncated,
            "timeout": timed_out,
            "task_json_parse_error": task_err,
        }
        meta = {
            "item_id": item_id,
            "provider": cfg["provider"],
            "request_model_name": model,
            "response_model_name": response_model,
            "frozen_prompt_sha256": PROMPT_SHA,
            "input_material_sha256": input_sha,
            "user_message_sha256": user_sha,
            "raw_response_sha256": sha256_bytes(raw),
            "started_at": started,
            "ended_at": ended,
            "elapsed_ms": elapsed_ms,
            "http_or_interface_status": {
                "http_status": status,
                "timed_out": timed_out,
                "send_status": "sent_completed" if status == 200 and not timed_out else "failed",
                "finish_reason": finish_reason,
                "headers": headers,
            },
            "legal_envelope_json": envelope_ok,
            "legal_task_json": task_ok,
            "envelope_parse_error": envelope_err,
            "task_json_parse_error": task_err,
            "truncated": truncated,
            "timeout": timed_out,
            "auth_failure": auth_failure,
            "identity_drift": identity_drift,
            "retries": 0,
            "secret_redacted": False,
            "stdout_bytes": len(raw),
            "request_path": f"requests/{stem}_{item_id}.json",
            "stdout_path": f"responses/raw/{stem}_{item_id}.stdout.bin",
            "usage": usage,
            "schema": schema_direct or schema_fenced,
            "fenced_json": fenced_ok,
            "thinking": thinking_ev,
            "facts_preview": facts_preview,
            "q4_causal_hits": causal if item_id == "Q4" else [],
            "call_number": calls_made,
        }
        write_json(RESPONSES / f"{stem}_{item_id}.meta.json", meta, key)
        print(
            f"CALL {provider_id} {item_id} status={status} model={response_model} "
            f"identity_drift={identity_drift} task_json={task_ok} schema={schema_legal} "
            f"sha={sha256_bytes(raw)}"
        )
        if auth_failure or identity_drift or timed_out or status != 200:
            stop_reason = {
                "item_id": item_id,
                "auth_failure": auth_failure,
                "identity_drift": identity_drift,
                "timeout": timed_out,
                "http_status": status,
            }
            break

    receipt = {
        "provider": cfg["provider"],
        "status": "COMPLETED" if calls_made == MAX_CALLS and stop_reason is None else "STOPPED",
        "request_model_id": model,
        "expected_response_model": expected,
        "model_selection_note": model_note,
        "catalog_path": cfg["catalog_path"],
        "catalog_model_count": len(model_ids),
        "calls_made": calls_made,
        "max_calls": MAX_CALLS,
        "retries": 0,
        "stop_reason": stop_reason,
        "items": item_rows,
    }
    write_json(OUT / f"11_{stem}_partial.json", receipt, key)
    print(json.dumps({"provider": provider_id, "status": receipt["status"], "calls": calls_made, "stop": stop_reason}, ensure_ascii=False))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("sensenova", "ant_ling"), required=True)
    args = parser.parse_args()
    run_provider(args.provider)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
