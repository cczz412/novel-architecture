#!/usr/bin/env python3
"""CCZ-57 L1 thinking-low A/B. Same frozen Prompt + 4 items. Does not overwrite non-thinking artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
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
    "Q1": "e8bdbb3db916f2170225f906e8d0ca78268b0f05b018338aa694aa4d62785e72",
    "Q2": "f3793e9dbbfd7d01b1515beac438185ea57902b7038f6bd925d2c88461ac5d1b",
    "Q3": "537d8f1735f3a610b92bbc8180e18be525f834d96737954bc1963693f9e94ad0",
    "Q4": "4673ac4abe647ef475d0007c25b4f4f5eae1ea04c80091610dca02936bfc8c33",
}
GIT_HEAD = "8872887690fd018474a69979016b428f2c2faf56"
TIMEOUT = 420
MAX_OUTPUT_TOKENS = 4096
STUB_PREFIX = "tl_"
RECEIPT_PREFIX = "13_thinking_low"


def remap_stub(stub: str) -> str:
    if stub.startswith("tl_"):
        return STUB_PREFIX + stub[3:]
    return stub

MAX_PER_MODEL = 4
UNSET = [
    "ARK_API_KEY",
    "ARK_BASE_URL",
    "ARK_REGION",
    "ARK_PROFILE",
    "VOLCENGINE_AGENT_PLAN_API_KEY",
]

AGENT_PLAN_MODELS = [
    {
        "slot": "turbo",
        "stub": "tl_doubao_seed_2_1_turbo",
        "request_model_id": "doubao-seed-2-1-turbo-260628",
        "expected_response_model": "doubao-seed-2-1-turbo-260628",
        "effort": "low",
        "effort_note": "Volcengine lowest real thinking is low; minimal means no thinking",
    },
    {
        "slot": "mini",
        "stub": "tl_doubao_seed_2_0_mini",
        "request_model_id": "doubao-seed-2-0-mini-260215",
        "expected_response_model": "doubao-seed-2-0-mini-260215",
        "effort": "low",
        "effort_note": "Volcengine lowest real thinking is low; minimal means no thinking",
    },
    {
        "slot": "lite",
        "stub": "tl_doubao_seed_2_0_lite",
        "request_model_id": "doubao-seed-2-0-lite-260215",
        "expected_response_model": "doubao-seed-2-0-lite-260215",
        "effort": "low",
        "effort_note": "Volcengine lowest real thinking is low; minimal means no thinking",
    },
    {
        "slot": "minimax_m3",
        "stub": "tl_minimax_m3",
        "request_model_id": "minimax-m3-modelhub",
        "expected_response_model": "minimax-m3",
        "effort": None,
        "effort_note": "M3 has enabled/adaptive/disabled only; lowest ON is enabled; do not send reasoning_effort",
    },
    {
        "slot": "glm_5_2",
        "stub": "tl_glm_5_2",
        "request_model_id": "glm-5-2-260601",
        "expected_response_model": "glm-5-2-260617",
        "effort": "high",
        "effort_note": "GLM-5.2 official ON levels are high and max; unset defaults to max; lowest ON is explicit high",
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def assert_no_secret(blob: bytes | str, key: str, where: str) -> None:
    if not key:
        return
    text = blob if isinstance(blob, str) else blob.decode("utf-8", "replace")
    raw = blob if isinstance(blob, bytes) else blob.encode("utf-8")
    if key in text or key.encode("utf-8") in raw:
        die(f"secret leaked into {where}")


def write_bytes(path: Path, data: bytes, key: str = "", overwrite: bool = False) -> None:
    assert_no_secret(data, key, str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        die(f"refuse to overwrite {path}")
    path.write_bytes(data)


def write_json(path: Path, data: Any, key: str = "", overwrite: bool = False) -> None:
    write_bytes(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode(), key, overwrite=overwrite)


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
    return {
        "schema_legal": not errors,
        "error_count": len(errors),
        "first_error": errors[0].message if errors else None,
        "empty_speaker": empty_speaker,
        "omitted_speaker": omitted_speaker,
        "fact_count": len(facts) if isinstance(facts, list) else None,
    }


def causal_hits(facts: list[Any]) -> list[str]:
    keys = ("因为", "因", "所以", "导致", "于是", "使得")
    hits = []
    for fact in facts:
        if isinstance(fact, dict) and isinstance(fact.get("fact"), str):
            if any(k in fact["fact"] for k in keys):
                hits.append(fact["fact"])
    return hits


def load_frozen() -> tuple[str, dict[str, Any], dict[str, Any]]:
    prompt = (FROZEN / "system_prompt_novel_fact_extraction_v2.md").read_text(encoding="utf-8")
    if sha256_bytes(prompt.encode()) != PROMPT_SHA:
        die("frozen prompt sha mismatch")
    schema_bytes = (FROZEN / "novel_fact_extraction_v2.schema.json").read_bytes()
    if sha256_bytes(schema_bytes) != SCHEMA_SHA:
        die("frozen schema sha mismatch")
    items = json.loads((OUT / "01_合成题面.json").read_text(encoding="utf-8"))["items"]
    return prompt, json.loads(schema_bytes.decode()), {row["item_id"]: row for row in items}


def analyze_content(content: Any, schema: dict[str, Any]) -> dict[str, Any]:
    if isinstance(content, list):
        texts = [
            b.get("text")
            for b in content
            if isinstance(b, dict) and isinstance(b.get("text"), str)
        ]
        content = "".join(texts) if texts else json.dumps(content, ensure_ascii=False)
    out = {
        "direct_json": False,
        "fenced_json": False,
        "schema_legal": False,
        "schema": None,
        "facts_preview": [],
        "q4_causal_hits": [],
        "task_err": None,
    }
    if not isinstance(content, str) or not content.strip():
        out["task_err"] = "empty_or_non_string_content"
        return out
    try:
        task = json.loads(content)
        out["direct_json"] = True
        rep = schema_report(task, schema)
        out["schema"] = rep
        out["schema_legal"] = bool(rep["schema_legal"])
        if isinstance(task, dict) and isinstance(task.get("facts"), list):
            out["facts_preview"] = [
                row.get("fact")
                for row in task["facts"]
                if isinstance(row, dict) and isinstance(row.get("fact"), str)
            ]
            out["q4_causal_hits"] = causal_hits(task["facts"])
        return out
    except json.JSONDecodeError as exc:
        out["task_err"] = type(exc).__name__
        stripped = strip_fence(content)
        if stripped != content.strip():
            try:
                task = json.loads(stripped)
                out["fenced_json"] = True
                rep = schema_report(task, schema)
                out["schema"] = rep
                if isinstance(task, dict) and isinstance(task.get("facts"), list):
                    out["facts_preview"] = [
                        row.get("fact")
                        for row in task["facts"]
                        if isinstance(row, dict) and isinstance(row.get("fact"), str)
                    ]
                    out["q4_causal_hits"] = causal_hits(task["facts"])
            except json.JSONDecodeError:
                pass
        return out


def catalog_ids_agent_plan() -> tuple[list[str], dict[str, Any]]:
    env = os.environ.copy()
    for name in UNSET:
        env.pop(name, None)
    env["ARKCLI_CALLER_TYPE"] = "ai_agent"
    env["ARKCLI_CALLER_NAME"] = "cursor"
    env["ARKCLI_SKILL_NAME"] = "arkcli-plans"
    argv = [
        "arkcli",
        "plans",
        "model-list",
        "--plan",
        "agent-plan",
        "--format",
        "json",
        "--profile",
        "agent-plan_cn-beijing_personal",
    ]
    started = now_iso()
    proc = subprocess.run(argv, capture_output=True, env=env, timeout=60)
    ended = now_iso()
    raw = proc.stdout
    try:
        parsed = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    ids: list[str] = []
    if isinstance(parsed, dict) and isinstance(parsed.get("models"), list):
        for row in parsed["models"]:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                ids.append(row["id"])
            elif isinstance(row, dict) and isinstance(row.get("model_id"), str):
                ids.append(row["model_id"])
            elif isinstance(row, str):
                ids.append(row)
    receipt = {
        "fetched_at_start": started,
        "fetched_at_end": ended,
        "exit_code": proc.returncode,
        "model_ids": ids,
        "raw_sha256": sha256_bytes(raw),
        "stderr_bytes": len(proc.stderr),
    }
    write_json(FROZEN / "live_catalog_plans_model_list_thinking_low_20260827.json", receipt, overwrite=True)
    print(f"CATALOG agent_plan exit={proc.returncode} n={len(ids)} sha={receipt['raw_sha256']}")
    if proc.returncode != 0:
        die("agent plan catalog failed")
    return ids, receipt


def http_json(method: str, url: str, key: str, body: dict[str, Any] | None = None, timeout: int | None = None):
    if timeout is None:
        timeout = TIMEOUT
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    if data is not None:
        assert_no_secret(data, key, "request body")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return getattr(resp, "status", 200), raw, False
    except urllib.error.HTTPError as exc:
        return int(exc.code), (exc.read() if hasattr(exc, "read") else b""), False
    except TimeoutError:
        return 0, b"", True


def extract_http_ids(parsed: Any) -> list[str]:
    ids = []
    rows = []
    if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
        rows = parsed["data"]
    elif isinstance(parsed, list):
        rows = parsed
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


def thinking_from_usage_and_message(usage: dict[str, Any], message: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
    reasoning_tokens = details.get("reasoning_tokens")
    if reasoning_tokens is None and isinstance(usage.get("output_tokens_details"), dict):
        reasoning_tokens = usage["output_tokens_details"].get("reasoning_tokens")
    field = None
    for name in ("reasoning_content", "reasoning"):
        value = message.get(name)
        if isinstance(value, str) and value.strip():
            field = name
            break
    extra_rc = extra.get("reasoning_content")
    if field is None and isinstance(extra_rc, str) and extra_rc.strip():
        field = "envelope.reasoning_content"
    return {
        "reasoning_tokens": reasoning_tokens,
        "nonempty_reasoning_field": field,
        "thinking_appears_on": bool(
            (isinstance(reasoning_tokens, int) and reasoning_tokens > 0)
            or field
        ),
        "reasoning_chars": len(extra_rc) if isinstance(extra_rc, str) else (
            len(message.get(field) or "") if field and field in message else 0
        ),
    }


def run_agent_plan() -> dict[str, Any]:
    prompt, schema, by_id = load_frozen()
    ids, _catalog = catalog_ids_agent_plan()
    env = os.environ.copy()
    for name in UNSET:
        env.pop(name, None)
    env["ARKCLI_CALLER_TYPE"] = "ai_agent"
    env["ARKCLI_CALLER_NAME"] = "cursor"
    env["ARKCLI_SKILL_NAME"] = "arkcli-chat"
    models_out = []
    for spec in AGENT_PLAN_MODELS:
        if spec["request_model_id"] not in ids:
            print(f"STOP {spec['slot']} not in live catalog")
            models_out.append({"slot": spec["slot"], "status": "STOPPED_NOT_IN_CATALOG", "calls": 0})
            continue
        stop = None
        items = {}
        calls = 0
        for item_id in ("Q1", "Q2", "Q3", "Q4"):
            user = (FROZEN / f"user_message_{item_id}.md").read_text(encoding="utf-8")
            if sha256_bytes(user.encode()) != USER_SHA[item_id]:
                die(f"{item_id} user sha mismatch")
            input_sha = by_id[item_id]["input_sha256"]
            if input_sha != INPUT_SHA[item_id]:
                die(f"{item_id} input sha mismatch")
            argv = [
                "arkcli", "+chat",
                "--profile", "agent-plan_cn-beijing_personal",
                "--model", spec["request_model_id"],
                "--instructions", prompt,
                "--temperature", "0",
                "--max-output-tokens", str(MAX_OUTPUT_TOKENS),
                "--thinking", "enabled",
                "--text-format", "json_object",
                "--no-progress",
                "--format", "json",
                user,
            ]
            if spec["effort"] is not None:
                argv[argv.index("--thinking") + 2:argv.index("--thinking") + 2]  # no-op keep order
                # insert effort after thinking enabled
                idx = argv.index("enabled") + 1
                argv[idx:idx] = ["--reasoning-effort", spec["effort"]]
            req_path = REQUESTS / f"{remap_stub(spec['stub'])}_{item_id}.json"
            meta_path = RESPONSES / f"{remap_stub(spec['stub'])}_{item_id}.meta.json"
            if req_path.exists() and not meta_path.exists():
                stop = {"item_id": item_id, "crashed_after_request_no_retry": True}
                print(f"STOP {spec['slot']} {item_id} request exists without meta; retry=0")
                break
            if req_path.exists() and meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                print(f"SKIP {spec['slot']} {item_id} already on disk")
                items[item_id] = meta
                calls += 1
                if meta.get("identity_drift") or meta.get("arkcli_exit_code") not in (0, None):
                    stop = {"item_id": item_id, "resume_stop": True, "identity_drift": meta.get("identity_drift")}
                    break
                continue
            write_json(
                req_path,
                {
                    "item_id": item_id,
                    "lane": "agent_plan_thinking_low",
                    "request_model_name": spec["request_model_id"],
                    "expected_response_model": spec["expected_response_model"],
                    "frozen_prompt_sha256": PROMPT_SHA,
                    "input_material_sha256": input_sha,
                    "user_message_sha256": USER_SHA[item_id],
                    "retries": 0,
                    "argv": [
                        x if x not in (prompt, user) else (
                            f"<system_prompt sha={PROMPT_SHA}>" if x == prompt else f"<user sha={USER_SHA[item_id]}>"
                        )
                        for x in argv
                    ],
                    "sampling": {
                        "temperature": 0,
                        "thinking": "enabled",
                        "reasoning_effort": spec["effort"],
                        "effort_note": spec["effort_note"],
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                    },
                },
            )
            started = now_iso()
            proc = subprocess.run(argv, capture_output=True, env=env, timeout=TIMEOUT)
            ended = now_iso()
            calls += 1
            raw = proc.stdout
            write_bytes(RAW / f"{remap_stub(spec['stub'])}_{item_id}.stdout.bin", raw)
            write_bytes(RAW / f"{remap_stub(spec['stub'])}_{item_id}.stderr.bin", proc.stderr)
            model = None
            content = None
            usage: dict[str, Any] = {}
            envelope = None
            try:
                envelope = json.loads(raw.decode())
            except (UnicodeDecodeError, json.JSONDecodeError):
                envelope = None
            if isinstance(envelope, dict):
                model = envelope.get("model") if isinstance(envelope.get("model"), str) else None
                content = envelope.get("content") if isinstance(envelope.get("content"), str) else None
                usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
            analysis = analyze_content(content, schema)
            identity_drift = model != spec["expected_response_model"]
            think = thinking_from_usage_and_message(
                usage,
                envelope.get("message") if isinstance(envelope, dict) and isinstance(envelope.get("message"), dict) else {},
                envelope if isinstance(envelope, dict) else {},
            )
            elapsed_ms = None
            try:
                elapsed_ms = int((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds() * 1000)
            except ValueError:
                pass
            meta = {
                "item_id": item_id,
                "lane": "agent_plan_thinking_low",
                "request_model_name": spec["request_model_id"],
                "response_model_name": model,
                "identity_drift": identity_drift,
                "arkcli_exit_code": proc.returncode,
                "started_at": started,
                "ended_at": ended,
                "elapsed_ms": elapsed_ms,
                "retries": 0,
                "usage": usage,
                "thinking": think,
                "analysis": analysis,
                "raw_sha256": sha256_bytes(raw),
            }
            write_json(RESPONSES / f"{remap_stub(spec['stub'])}_{item_id}.meta.json", meta)
            print(
                f"CALL {spec['slot']} {item_id} exit={proc.returncode} model={model} "
                f"drift={identity_drift} json={analysis['direct_json']} schema={analysis['schema_legal']} "
                f"think={think['thinking_appears_on']} rt={think['reasoning_tokens']}"
            )
            items[item_id] = meta
            if identity_drift or proc.returncode != 0:
                stop = {"item_id": item_id, "identity_drift": identity_drift, "exit": proc.returncode}
                break
        models_out.append({
            "slot": spec["slot"],
            "request_model_id": spec["request_model_id"],
            "expected_response_model": spec["expected_response_model"],
            "effort": spec["effort"],
            "effort_note": spec["effort_note"],
            "calls": calls,
            "stop_reason": stop,
            "status": "COMPLETED" if calls == 4 and stop is None else "STOPPED",
            "items": {k: {
                "direct_json": v["analysis"]["direct_json"],
                "schema_legal": v["analysis"]["schema_legal"],
                "thinking_appears_on": v["thinking"]["thinking_appears_on"],
                "reasoning_tokens": v["thinking"]["reasoning_tokens"],
                "identity_drift": v["identity_drift"],
                "q4_causal": bool(v["analysis"]["q4_causal_hits"]) if k == "Q4" else None,
                "empty_speaker": (v["analysis"]["schema"] or {}).get("empty_speaker"),
                "usage": v["usage"],
                "elapsed_ms": v["elapsed_ms"],
            } for k, v in items.items()},
        })
    receipt = {
        "lane": "agent_plan_thinking_low",
        "git_head": GIT_HEAD,
        "models": models_out,
        "retries": 0,
    }
    write_json(OUT / f"{RECEIPT_PREFIX}_agent_plan_partial.json", receipt, overwrite=True)
    return receipt


def run_http_lane(lane: str) -> dict[str, Any]:
    prompt, schema, by_id = load_frozen()
    if lane == "deepseek":
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if os.environ.get("CZ_DEEPSEEK_OFFICIAL_API_APPROVAL") != "USE_OFFICIAL_DEEPSEEK_API_ONCE":
            die("missing DeepSeek official machine ack", 77)
        if not key:
            die("missing DEEPSEEK_API_KEY", 1)
        base = "https://api.deepseek.com"
        model = "deepseek-v4-flash"
        expected = "deepseek-v4-flash"
        stub = remap_stub("tl_deepseek_official_v4_flash")
        catalog_name = "live_catalog_deepseek_official_models_thinking_low_20260827.json"
        def body_for(user: str) -> dict[str, Any]:
            return {
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "thinking": {"type": "enabled"},
                "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
            }
        effort_note = "official docs: low maps to low; this is lowest ON, not max/high"
    elif lane == "sensenova":
        key = os.environ.get("SENSENOVA_API_KEY", "")
        if not key:
            die("missing SENSENOVA_API_KEY", 1)
        base = "https://token.sensenova.cn/v1"
        model = "sensenova-6.8-flash-lite"
        expected = "sensenova-6.8-flash-lite"
        stub = remap_stub("tl_sensenova_6_8_flash_lite")
        catalog_name = "live_catalog_sensenova_models_thinking_low_20260827.json"
        def body_for(user: str) -> dict[str, Any]:
            return {
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
            }
        effort_note = "Token Plan 6.8 Flash Lite: none/low/medium/high; lowest ON is low"
    elif lane == "ling":
        key = os.environ.get("ANT_LING_API_KEY", "")
        if not key:
            die("missing ANT_LING_API_KEY", 1)
        base = "https://api.ant-ling.com/v1"
        model = "Ling-3.0-flash"
        expected = "Ling-3.0-flash"
        stub = remap_stub("tl_ant_ling_3_0_flash")
        catalog_name = "live_catalog_ant_ling_models_thinking_low_20260827.json"
        def body_for(user: str) -> dict[str, Any]:
            return {
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "thinking": {"type": "enabled"},
                "response_format": {"type": "json_object"},
            }
        effort_note = "Ling only has enabled/disabled; lowest ON is enabled; no reasoning_effort"
    else:
        die(f"unknown lane {lane}")

    status, raw, timed_out = http_json("GET", f"{base}/models", key, timeout=60)
    assert_no_secret(raw, key, "catalog")
    try:
        parsed = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    ids = extract_http_ids(parsed)
    write_json(
        FROZEN / catalog_name,
        {
            "http_status": status,
            "timed_out": timed_out,
            "model_ids": ids,
            "raw_sha256": sha256_bytes(raw),
            "raw_bytes": len(raw),
        },
        key,
        overwrite=True,
    )
    print(f"CATALOG {lane} status={status} n={len(ids)} sha={sha256_bytes(raw)}")
    if status != 200 or timed_out or model not in ids:
        die(f"{lane} catalog failed or {model} missing; ids={ids}")

    stop = None
    items = {}
    calls = 0
    for item_id in ("Q1", "Q2", "Q3", "Q4"):
        user = (FROZEN / f"user_message_{item_id}.md").read_text(encoding="utf-8")
        if sha256_bytes(user.encode()) != USER_SHA[item_id]:
            die("user sha mismatch")
        input_sha = by_id[item_id]["input_sha256"]
        body = body_for(user)
        req_path = REQUESTS / f"{stub}_{item_id}.json"
        meta_path = RESPONSES / f"{stub}_{item_id}.meta.json"
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
        write_json(
            REQUESTS / f"{stub}_{item_id}.json",
            {
                "item_id": item_id,
                "lane": f"{lane}_thinking_low",
                "request_model_name": model,
                "expected_response_model": expected,
                "frozen_prompt_sha256": PROMPT_SHA,
                "input_material_sha256": input_sha,
                "user_message_sha256": USER_SHA[item_id],
                "retries": 0,
                "effort_note": effort_note,
                "body": body,
                "_security": "no_api_key",
            },
            key,
        )
        started = now_iso()
        status, raw, timed_out = http_json("POST", f"{base}/chat/completions", key, body)
        ended = now_iso()
        calls += 1
        assert_no_secret(raw, key, f"{item_id} response")
        write_bytes(RAW / f"{stub}_{item_id}.stdout.bin", raw, key)
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
        if isinstance(envelope, dict):
            response_model = envelope.get("model")
            usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
            choices = envelope.get("choices") if isinstance(envelope.get("choices"), list) else []
            first = choices[0] if choices and isinstance(choices[0], dict) else {}
            finish = first.get("finish_reason")
            message = first.get("message") if isinstance(first.get("message"), dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
        analysis = analyze_content(content, schema)
        identity_drift = response_model != expected
        think = thinking_from_usage_and_message(usage, message, envelope if isinstance(envelope, dict) else {})
        elapsed_ms = None
        try:
            elapsed_ms = int((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds() * 1000)
        except ValueError:
            pass
        meta = {
            "item_id": item_id,
            "lane": f"{lane}_thinking_low",
            "request_model_name": model,
            "response_model_name": response_model,
            "identity_drift": identity_drift,
            "http_status": status,
            "timed_out": timed_out,
            "finish_reason": finish,
            "started_at": started,
            "ended_at": ended,
            "elapsed_ms": elapsed_ms,
            "retries": 0,
            "usage": usage,
            "thinking": think,
            "analysis": analysis,
            "raw_sha256": sha256_bytes(raw),
        }
        write_json(RESPONSES / f"{stub}_{item_id}.meta.json", meta, key)
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
            }
            break
    receipt = {
        "lane": f"{lane}_thinking_low",
        "git_head": GIT_HEAD,
        "request_model_id": model,
        "expected_response_model": expected,
        "effort_note": effort_note,
        "calls": calls,
        "stop_reason": stop,
        "status": "COMPLETED" if calls == 4 and stop is None else "STOPPED",
        "items": items,
        "retries": 0,
    }
    write_json(OUT / f"{RECEIPT_PREFIX}_{lane}_partial.json", receipt, key, overwrite=True)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=("agent_plan", "deepseek", "sensenova", "ling"), required=True)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--stub-prefix", default="tl_")
    parser.add_argument("--receipt-prefix", default="13_thinking_low")
    parser.add_argument("--timeout", type=int, default=420)
    args = parser.parse_args()
    global MAX_OUTPUT_TOKENS, STUB_PREFIX, RECEIPT_PREFIX, TIMEOUT
    MAX_OUTPUT_TOKENS = args.max_output_tokens
    STUB_PREFIX = args.stub_prefix
    RECEIPT_PREFIX = args.receipt_prefix
    TIMEOUT = args.timeout
    if args.lane == "agent_plan":
        run_agent_plan()
    else:
        run_http_lane(args.lane)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
