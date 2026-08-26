#!/usr/bin/env python3
"""CCZ-57 L1 batch 2: 4 Agent Plan models, non-thinking, frozen 4 items, retry 0."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
FROZEN = OUT / "frozen"
REQUESTS = OUT / "requests"
RESPONSES = OUT / "responses"
RAW = RESPONSES / "raw"

PROMPT_SHA = "57ab1d68a4ebe3ee4bc7c57693247e9fa7bc1879252b57254ff25b0220bd2a2b"
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
MODELS = [
    {
        "slot": "mini",
        "file_stub": "doubao_seed_2_0_mini",
        "request_model_id": "doubao-seed-2-0-mini-260215",
        "expected_response_model": "doubao-seed-2-0-mini-260215",
    },
    {
        "slot": "lite",
        "file_stub": "doubao_seed_2_0_lite",
        "request_model_id": "doubao-seed-2-0-lite-260215",
        "expected_response_model": "doubao-seed-2-0-lite-260215",
    },
    {
        "slot": "minimax_m3",
        "file_stub": "minimax_m3",
        "request_model_id": "minimax-m3-modelhub",
        "expected_response_model": "minimax-m3",
    },
    {
        "slot": "glm_5_2",
        "file_stub": "glm_5_2",
        "request_model_id": "glm-5-2-260601",
        "expected_response_model": "glm-5-2-260617",
    },
]
UNSET = [
    "ARK_API_KEY",
    "ARK_BASE_URL",
    "ARK_REGION",
    "ARK_PROFILE",
    "VOLCENGINE_AGENT_PLAN_API_KEY",
]
TIMEOUT = 180


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def redacted_argv(argv: list[str], prompt: str, user: str) -> list[str]:
    out = []
    for item in argv:
        if item == prompt:
            out.append(f"<system_prompt sha256={PROMPT_SHA} bytes={len(prompt.encode())}>")
        elif item == user:
            out.append(f"<user_message sha256={sha256_bytes(user.encode())} bytes={len(user.encode())}>")
        else:
            out.append(item)
    return out


def extract_content_and_model(stdout: bytes) -> tuple[str | None, str | None, dict, str | None, str | None]:
    envelope_err = None
    try:
        data = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, None, {}, type(exc).__name__, None
    if not isinstance(data, dict):
        return None, None, {}, "non_object", None
    model = data.get("model") if isinstance(data.get("model"), str) else None
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    content = data.get("content") if isinstance(data.get("content"), str) else None
    return model, content, usage, None, None


def main() -> int:
    prompt = (FROZEN / "system_prompt_novel_fact_extraction_v2.md").read_text(encoding="utf-8")
    if sha256_bytes(prompt.encode()) != PROMPT_SHA:
        print("frozen prompt sha mismatch", file=sys.stderr)
        return 2
    items_meta = json.loads((OUT / "01_合成题面.json").read_text(encoding="utf-8"))["items"]
    by_id = {row["item_id"]: row for row in items_meta}

    env = os.environ.copy()
    for name in UNSET:
        env.pop(name, None)
    env["ARKCLI_CALLER_TYPE"] = "ai_agent"
    env["ARKCLI_CALLER_NAME"] = "cursor"
    env["ARKCLI_SKILL_NAME"] = "arkcli-chat"

    calls = []
    total = 0
    for spec in MODELS:
        model_stop = None
        for item_id in ("Q1", "Q2", "Q3", "Q4"):
            if model_stop:
                break
            user = (FROZEN / f"user_message_{item_id}.md").read_text(encoding="utf-8")
            user_sha = sha256_bytes(user.encode())
            if user_sha != USER_SHA[item_id]:
                print(f"{item_id} user sha mismatch", file=sys.stderr)
                return 2
            input_sha = by_id[item_id]["input_sha256"]
            if input_sha != INPUT_SHA[item_id]:
                print(f"{item_id} input sha mismatch", file=sys.stderr)
                return 2
            argv = [
                "arkcli",
                "+chat",
                "--profile",
                "agent-plan_cn-beijing_personal",
                "--model",
                spec["request_model_id"],
                "--instructions",
                prompt,
                "--temperature",
                "0",
                "--max-output-tokens",
                "4096",
                "--thinking",
                "disabled",
                "--text-format",
                "json_object",
                "--no-progress",
                "--format",
                "json",
                user,
            ]
            stub = spec["file_stub"]
            req_path = REQUESTS / f"{stub}_{item_id}.json"
            write_json(
                req_path,
                {
                    "item_id": item_id,
                    "slot": spec["slot"],
                    "request_model_name": spec["request_model_id"],
                    "expected_response_model": spec["expected_response_model"],
                    "frozen_prompt_sha256": PROMPT_SHA,
                    "input_material_sha256": input_sha,
                    "user_message_sha256": user_sha,
                    "retries": 0,
                    "argv": redacted_argv(argv, prompt, user),
                    "env_overrides_unset": UNSET,
                    "transport": "arkcli +chat",
                    "sampling": {
                        "temperature": 0,
                        "thinking": "disabled",
                        "text_format": "json_object",
                        "max_output_tokens": 4096,
                    },
                },
            )
            started = now_iso()
            timed_out = False
            try:
                proc = subprocess.run(
                    argv,
                    env=env,
                    capture_output=True,
                    timeout=TIMEOUT,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                exit_code = -1
            ended = now_iso()
            total += 1
            stdout_path = RAW / f"{stub}_{item_id}.stdout.bin"
            stderr_path = RAW / f"{stub}_{item_id}.stderr.bin"
            RAW.mkdir(parents=True, exist_ok=True)
            stdout_path.write_bytes(stdout)
            stderr_path.write_bytes(stderr)
            response_model, content, usage, envelope_err, _ = extract_content_and_model(stdout)
            identity_drift = bool(response_model) and response_model != spec["expected_response_model"]
            task_ok = False
            task_err = None
            fact_count = None
            if isinstance(content, str) and content.strip():
                try:
                    task = json.loads(content)
                    task_ok = True
                    if isinstance(task, dict) and isinstance(task.get("facts"), list):
                        fact_count = len(task["facts"])
                except json.JSONDecodeError:
                    task_err = "JSONDecodeError"
            elif envelope_err is None:
                task_err = "empty_or_non_string_content"
            t0 = datetime.fromisoformat(started)
            t1 = datetime.fromisoformat(ended)
            elapsed_ms = int((t1 - t0).total_seconds() * 1000)
            low = stderr.lower()
            auth_failure = exit_code != 0 and (b"unauthor" in low or b"not logged" in low or b"expired" in low)
            meta = {
                "item_id": item_id,
                "slot": spec["slot"],
                "request_model_name": spec["request_model_id"],
                "response_model_name": response_model,
                "expected_response_model": spec["expected_response_model"],
                "frozen_prompt_sha256": PROMPT_SHA,
                "input_material_sha256": input_sha,
                "user_message_sha256": user_sha,
                "raw_response_sha256": sha256_bytes(stdout),
                "stderr_sha256": sha256_bytes(stderr),
                "started_at": started,
                "ended_at": ended,
                "elapsed_ms": elapsed_ms,
                "http_or_interface_status": {
                    "arkcli_exit_code": exit_code,
                    "timed_out": timed_out,
                    "send_status": "sent_completed" if exit_code == 0 and not timed_out else "failed",
                },
                "legal_envelope_json": envelope_err is None and response_model is not None,
                "legal_task_json": task_ok,
                "envelope_parse_error": envelope_err,
                "task_json_parse_error": task_err,
                "timeout": timed_out,
                "auth_failure": bool(auth_failure),
                "identity_drift": identity_drift,
                "retries": 0,
                "stdout_bytes": len(stdout),
                "stderr_bytes": len(stderr),
                "request_path": f"requests/{stub}_{item_id}.json",
                "stdout_path": f"responses/raw/{stub}_{item_id}.stdout.bin",
                "stderr_path": f"responses/raw/{stub}_{item_id}.stderr.bin",
                "usage": usage,
                "fact_count": fact_count,
            }
            write_json(RESPONSES / f"{stub}_{item_id}.meta.json", meta)
            print(
                f"CALL {spec['slot']} {item_id} exit={exit_code} model={response_model} "
                f"drift={identity_drift} task_json={task_ok} sha={sha256_bytes(stdout)}",
                flush=True,
            )
            rec = {
                "slot": spec["slot"],
                "item_id": item_id,
                "exit_code": exit_code,
                "response_model": response_model,
                "identity_drift": identity_drift,
                "task_json": task_ok,
                "timeout": timed_out,
                "auth_failure": bool(auth_failure),
            }
            calls.append(rec)
            if timed_out or identity_drift or exit_code != 0 or auth_failure:
                model_stop = rec
                print(f"STOP model {spec['slot']}: {rec}", flush=True)
                if auth_failure:
                    write_json(OUT / "09_AgentPlan第二批运行回执.partial.json", {"status": "AUTH_STOP", "calls_made": total, "calls": calls})
                    return 3

    write_json(
        OUT / "09_AgentPlan第二批运行回执.partial.json",
        {"status": "RAN", "calls_made": total, "max_calls": 16, "retries": 0, "calls": calls},
    )
    print(json.dumps({"calls_made": total, "n_records": len(calls)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
