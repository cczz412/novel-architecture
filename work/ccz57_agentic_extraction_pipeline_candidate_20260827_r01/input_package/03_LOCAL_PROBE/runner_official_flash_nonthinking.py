#!/usr/bin/env python3
"""CCZ-57 L1: official DeepSeek V4 Flash, non-thinking, frozen 4 items.

Does not overwrite Doubao artifacts. Retries = 0. Never writes the API key.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent
FROZEN = OUT / "frozen"
REQUESTS = OUT / "requests"
RESPONSES = OUT / "responses"
RAW = RESPONSES / "raw"

BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-v4-flash"
EXPECTED_RESPONSE_MODEL = "deepseek-v4-flash"
TIMEOUT_SECONDS = 180
MAX_CALLS = 4
APPROVAL_ENV = "CZ_DEEPSEEK_OFFICIAL_API_APPROVAL"
APPROVAL_VALUE = "USE_OFFICIAL_DEEPSEEK_API_ONCE"
KEY_ENV = "DEEPSEEK_API_KEY"

PROMPT_SHA = "57ab1d68a4ebe3ee4bc7c57693247e9fa7bc1879252b57254ff25b0220bd2a2b"
SCHEMA_SHA = "aa73696981b3b75717202db117ffac4df7584aad1dd3a086084f1c33a1f08352"
USER_SHA = {
    "Q1": "a44a5696ac4e5d6579e16abb58ea39e874e74d8281fd2137c7495270ade27313",
    "Q2": "261916a394434a876f13764f9452ee6764a87bbaf16bf4400b4e9db049c5a600",
    "Q3": "514d0d82468e60aebe486778e9cbf130bb3e75913c3e91cbbde8c27bc96445c1",
    "Q4": "70e345c4cd7aaf3dbec59b67c6ff1b2685ecc8701b45700d97d1ad878fd58682",
}
INPUT_SHA = {
    "Q1": "e8bdbb3db916f2170225f906e8d0ca78268b0f05b018338aa694aa4d62785e72",
    "Q2": "f3793e9dbbfd7d01b1515beac438185ea57902b7038f6bd925d2c88461ac5d1b",
    "Q3": "537d8f1735f3a610b92bbc8180e18be525f834d96737954bc1963693f9e94ad0",
    "Q4": "4673ac4abe647ef475d0007c25b4f4f5eae1ea04c80091610dca02936bfc8c33",
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
                if name.lower() in {"content-type", "date", "x-request-id", "request-id"}
            }
            return status, raw, safe_headers, False
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        return int(exc.code), raw, {}, False
    except TimeoutError:
        return 0, b"", {}, True


def main() -> int:
    if os.environ.get(APPROVAL_ENV) != APPROVAL_VALUE:
        die("missing machine execution ack", 77)
    key = os.environ.get(KEY_ENV, "")
    if not key:
        die(f"missing {KEY_ENV}", 1)

    prompt_path = FROZEN / "system_prompt_novel_fact_extraction_v2.md"
    schema_path = FROZEN / "novel_fact_extraction_v2.schema.json"
    prompt = prompt_path.read_text(encoding="utf-8")
    if sha256_bytes(prompt.encode("utf-8")) != PROMPT_SHA:
        die("frozen prompt sha mismatch")
    if sha256_bytes(schema_path.read_bytes()) != SCHEMA_SHA:
        die("frozen schema sha mismatch")

    items_meta = json.loads((OUT / "01_合成题面.json").read_text(encoding="utf-8"))["items"]
    by_id = {row["item_id"]: row for row in items_meta}

    catalog_started = now_iso()
    status, raw, headers, timed_out = http_json(
        method="GET",
        url=f"{BASE_URL}/models",
        key=key,
        timeout=60,
    )
    catalog_ended = now_iso()
    assert_no_secret(raw, key, "catalog response")
    catalog_path = FROZEN / "live_catalog_deepseek_official_models_20260827.json"
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    model_ids: list[str] = []
    if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
        for row in parsed["data"]:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                model_ids.append(row["id"])
        catalog_obj = parsed
    else:
        catalog_obj = {"unparsed": True, "http_status": status, "bytes": len(raw)}
    write_json(
        catalog_path,
        {
            "fetched_at_start": catalog_started,
            "fetched_at_end": catalog_ended,
            "http_status": status,
            "timed_out": timed_out,
            "headers": headers,
            "model_ids": model_ids,
            "raw": catalog_obj,
            "sha256": sha256_bytes(raw),
        },
        key,
    )
    print(f"CATALOG status={status} ids={model_ids} sha={sha256_bytes(raw)}")
    if status != 200 or timed_out:
        die("live catalog failed; stop before sampling")
    if MODEL not in model_ids:
        die(f"{MODEL} not in live catalog {model_ids}; stop before sampling")

    calls_made = 0
    stop_reason = None
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

        body = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 4096,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
        }
        request_record = {
            "item_id": item_id,
            "provider": "deepseek_official",
            "transport": "POST /chat/completions",
            "base_url": BASE_URL,
            "request_model_name": MODEL,
            "expected_response_model": EXPECTED_RESPONSE_MODEL,
            "frozen_prompt_sha256": PROMPT_SHA,
            "input_material_sha256": input_sha,
            "user_message_sha256": user_sha,
            "retries": 0,
            "sampling": {
                "temperature": 0,
                "thinking": {"type": "disabled"},
                "text_format": "json_object",
                "max_tokens": 4096,
            },
            "body": body,
            "_security": "no_api_key_no_authorization",
        }
        request_path = REQUESTS / f"deepseek_official_v4_flash_{item_id}.json"
        write_json(request_path, request_record, key)

        started = now_iso()
        calls_made += 1
        status, raw, headers, timed_out = http_json(
            method="POST",
            url=f"{BASE_URL}/chat/completions",
            key=key,
            body=body,
        )
        ended = now_iso()
        assert_no_secret(raw, key, f"{item_id} response")
        stdout_path = RAW / f"deepseek_official_v4_flash_{item_id}.stdout.bin"
        write_bytes(stdout_path, raw, key)

        envelope_ok = False
        task_ok = False
        envelope_err = None
        task_err = None
        response_model = None
        content = None
        usage = {}
        finish_reason = None
        identity_drift = False
        auth_failure = status in {401, 403}
        truncated = False
        fact_count = None
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
            if response_model != EXPECTED_RESPONSE_MODEL:
                identity_drift = True
            if finish_reason == "length":
                truncated = True
            if isinstance(content, str) and content.strip():
                try:
                    task = json.loads(content)
                    task_ok = True
                    if isinstance(task, dict) and isinstance(task.get("facts"), list):
                        fact_count = len(task["facts"])
                except json.JSONDecodeError as exc:
                    task_err = type(exc).__name__
            else:
                task_err = "empty_or_non_string_content"

        elapsed_ms = None
        try:
            t0 = datetime.fromisoformat(started)
            t1 = datetime.fromisoformat(ended)
            elapsed_ms = int((t1 - t0).total_seconds() * 1000)
        except ValueError:
            pass

        meta = {
            "item_id": item_id,
            "profile_id": None,
            "provider": "deepseek_official",
            "request_model_name": MODEL,
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
            "request_path": f"requests/deepseek_official_v4_flash_{item_id}.json",
            "stdout_path": f"responses/raw/deepseek_official_v4_flash_{item_id}.stdout.bin",
            "usage": usage,
            "fact_count": fact_count,
            "call_number": calls_made,
        }
        write_json(RESPONSES / f"deepseek_official_v4_flash_{item_id}.meta.json", meta, key)
        print(
            f"CALL {item_id} status={status} model={response_model} "
            f"identity_drift={identity_drift} task_json={task_ok} sha={sha256_bytes(raw)}"
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
        "schema_version": "ccz57-l1-official-flash-nonthinking-receipt-v1",
        "status": "COMPLETED" if calls_made == MAX_CALLS and stop_reason is None else "STOPPED",
        "calls_made": calls_made,
        "max_calls": MAX_CALLS,
        "retries": 0,
        "stop_reason": stop_reason,
        "request_model_id": MODEL,
        "expected_response_model": EXPECTED_RESPONSE_MODEL,
        "catalog_path": "frozen/live_catalog_deepseek_official_models_20260827.json",
        "catalog_model_ids": model_ids,
    }
    write_json(OUT / "07_官方Flash非思考运行回执.partial.json", receipt, key)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if stop_reason is None else 3


if __name__ == "__main__":
    raise SystemExit(main())
