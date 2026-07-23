#!/usr/bin/env python3
"""第89道：DeepSeek 官方 V4 Pro 第3章强模型单变量裸考。

这条运行线与第83道 retry 谱系完全隔离。模型可见消息逐字复用已经冻结的
v3 第3章请求；只把请求发往 DeepSeek 官方通道，并按第89道明确参数实例化。
金标只在 HTTP 成功且机械闸通过后进入本地判分区，绝不进入请求构造路径。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import http.client
import json
import os
import shutil
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import z68_revised_request_pilot as z68
import z75_multidirection_score as z75_score
import z79_fact_sheet_v3_pilot as z79
from zbatch_modules import neutral_extract, z83_retry_transport
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
REPORT_DIR = ROOT / "reports/Z89_DeepSeekV4Pro强模型对照_20260723"

SOURCE_RUN = ROOT / (
    "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry03"
)
SOURCE_BODY = SOURCE_RUN / "prepared_requests/ch0003.json"
SOURCE_BODY_SHA256 = "18fe2a9e9d2f0a4d48b5b4de29803a90c0db0fe1087080ff8f68d00b81e98eb4"
SOURCE_CHAPTER = SOURCE_RUN / "inputs/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt"
SOURCE_CHAPTER_SHA256 = "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288"
SOURCE_CATALOG = SOURCE_RUN / "inputs/evidence_catalogs/ch0003.json"
SOURCE_CATALOG_SHA256 = "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132"
SOURCE_PROMPT_PACKAGE = SOURCE_RUN / "prompt_frozen/事实说明书注入包_v3.json"
SOURCE_PROMPT_PACKAGE_SHA256 = (
    "a302920537349d37c75d5bac9df19a83bfab667891458ef65de9d98e84bc2116"
)
SOURCE_RETRY13 = ROOT / (
    "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry13"
)

PROVIDER_CONFIG = ROOT / "config/providers/deepseek_official_v4_pro.json"
PROVIDER_CONFIG_SHA256 = (
    "9f1e86b7a814b47cd866d939a9592c02f7f58f79904000e8cba77959d4cc2282"
)
GOLD_POINTER = ROOT / "config/gold/X01_ch0003_structure_gold_current.json"
GOLD_POINTER_SHA256 = (
    "6a5c785dc98381ff4d9b7e207c599c29914f394e4b43e399d37f65093cc5a60c"
)
GOLD_FILE = ROOT / "reports/Z73_第3章金标v1.2定稿转正_20260721/第3章结构层金标v1.2.json"
GOLD_FILE_SHA256 = (
    "0df08ede4fa1a33f4bd9e1aea3e45387c8d77131ce79ff1496fe1320fa48a10e"
)

MODEL = "deepseek-v4-pro"
CONTRACT_VERSION = "z89-deepseek-v4-pro-ch3-model-swap-v1"
LOGICAL_REQUEST_ID = "Z89-X01-C0003-STRONG-MODEL"
CHAPTER = 3
REQUESTED_TEMPERATURE = 0.0
MAX_TOKENS = 32000
REASONING_EFFORT_REQUESTED = "medium"
REASONING_EFFORT_EFFECTIVE = "high"
THINKING_REQUESTED = "provider_default"
THINKING_EFFECTIVE = "enabled"
OFFICIAL_APPROVAL_ENV = "CZ_DEEPSEEK_OFFICIAL_API_APPROVAL"
OFFICIAL_APPROVAL_VALUE = "USE_OFFICIAL_DEEPSEEK_API_ONCE"

FORBIDDEN_MODEL_TOKENS = (
    "GOLD-C0003-",
    "structure-gold-v1.2",
    "z83-semantic-adjudication",
    "strict_hit",
    "semantic_shadow",
    "coverage_only_invalid_support",
    "第3章结构层金标v1.2",
)


class Z89HardStop(ZBatchError):
    """第89道任何不可补缝失败。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def write_bytes_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def append_jsonl_fsync(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def assert_file(path: Path, expected_sha: str, label: str) -> None:
    if not path.is_file():
        raise ZBatchError(f"缺少{label}：{path}")
    actual = sha256_file(path)
    if actual != expected_sha:
        raise ZBatchError(f"{label} SHA 漂移：{actual}")


def copy_file(source: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": sha256_file(source),
        "target": target.as_posix(),
        "target_sha256": sha256_file(target),
    }


def load_provider() -> dict[str, Any]:
    assert_file(PROVIDER_CONFIG, PROVIDER_CONFIG_SHA256, "DeepSeek 官方通道配置")
    provider = read_json(PROVIDER_CONFIG)
    expected = {
        "provider": "deepseek_official",
        "base_url": "https://api.deepseek.com",
        "endpoint": "/chat/completions",
        "model": MODEL,
        "api_key_env": "DEEPSEEK_API_KEY",
    }
    for key, value in expected.items():
        if provider.get(key) != value:
            raise ZBatchError(f"DeepSeek 官方通道配置 {key} 漂移")
    if MODEL not in provider.get("allowed_models", []):
        raise ZBatchError("DeepSeek 官方通道未准入 V4 Pro")
    aliases = provider.get("request_rules", {}).get("reasoning_effort_aliases", {})
    if aliases.get(REASONING_EFFORT_REQUESTED) != REASONING_EFFORT_EFFECTIVE:
        raise ZBatchError("medium→high 思考强度映射漂移")
    return provider


def source_pins() -> dict[str, Any]:
    rows = (
        (SOURCE_BODY, SOURCE_BODY_SHA256, "retry03 第3章冻结请求"),
        (SOURCE_CHAPTER, SOURCE_CHAPTER_SHA256, "retry03 第3章冻结正文"),
        (SOURCE_CATALOG, SOURCE_CATALOG_SHA256, "retry03 第3章冻结目录"),
        (
            SOURCE_PROMPT_PACKAGE,
            SOURCE_PROMPT_PACKAGE_SHA256,
            "v3 Prompt 定稿包",
        ),
        (PROVIDER_CONFIG, PROVIDER_CONFIG_SHA256, "DeepSeek 官方通道配置"),
        (GOLD_POINTER, GOLD_POINTER_SHA256, "现役金标指针"),
        (GOLD_FILE, GOLD_FILE_SHA256, "第3章金标 v1.2"),
    )
    result = []
    for path, expected, label in rows:
        assert_file(path, expected, label)
        result.append(
            {
                "label": label,
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": expected,
            }
        )
    rebuilt, _ = z79.build_candidate_body(CHAPTER)
    if rebuilt != read_json(SOURCE_BODY):
        raise ZBatchError("retry03 第3章冻结请求不能由 v3 构造器重建")
    return {"status": "pass", "rows": result}


def protected_snapshot() -> dict[str, Any]:
    if not SOURCE_RETRY13.is_dir():
        raise ZBatchError("retry13 封存目录不存在")
    return {
        "formal_and_default": z79.assert_protected()["formal_and_z75"],
        "retry13_tree": z68.tree_fingerprint(SOURCE_RETRY13),
        "retry03_source_files": {
            "body": sha256_file(SOURCE_BODY),
            "chapter": sha256_file(SOURCE_CHAPTER),
            "catalog": sha256_file(SOURCE_CATALOG),
            "prompt_package": sha256_file(SOURCE_PROMPT_PACKAGE),
        },
    }


def build_body() -> tuple[dict[str, Any], dict[str, Any]]:
    """只复用冻结消息；参数差异逐项留账。"""

    source_pins()
    provider = load_provider()
    baseline = read_json(SOURCE_BODY)
    body = copy.deepcopy(baseline)
    body["model"] = MODEL
    body["temperature"] = REQUESTED_TEMPERATURE
    # 保留 retry03 的 medium 字段；官方兼容层会映射为 high。
    if body.get("reasoning_effort") != REASONING_EFFORT_REQUESTED:
        raise ZBatchError("冻结请求的 reasoning_effort 不再是 medium")
    if "thinking" in body:
        raise ZBatchError("冻结请求意外显式携带 thinking；不再是默认档")
    if (
        body.get("max_tokens") != MAX_TOKENS
        or body.get("n") != 1
        or body.get("response_format") != {"type": "json_object"}
    ):
        raise ZBatchError("冻结请求的 32k／n=1／JSON 合同漂移")
    changed = sorted(key for key in set(baseline) | set(body) if baseline.get(key) != body.get(key))
    if changed != ["model", "temperature"]:
        raise ZBatchError(f"第89道请求参数夹带改动：{changed}")
    if body["messages"] != baseline["messages"]:
        raise ZBatchError("第89道模型可见消息发生改动")
    visible = "\n".join(str(row.get("content", "")) for row in body["messages"])
    forbidden = [token for token in FORBIDDEN_MODEL_TOKENS if token in visible]
    if forbidden:
        raise ZBatchError(f"第89道请求混入判分材料：{forbidden}")
    diff = {
        "schema_version": "z89-model-swap-diff-v1",
        "baseline_request": {
            "path": SOURCE_BODY.relative_to(ROOT).as_posix(),
            "sha256": SOURCE_BODY_SHA256,
            "model": baseline["model"],
            "temperature": baseline["temperature"],
        },
        "candidate": {
            "model": body["model"],
            "temperature_requested": body["temperature"],
            "temperature_effective": "ignored_in_thinking_mode",
            "reasoning_effort_requested": body["reasoning_effort"],
            "reasoning_effort_effective": REASONING_EFFORT_EFFECTIVE,
            "thinking_requested": THINKING_REQUESTED,
            "thinking_effective": THINKING_EFFECTIVE,
        },
        "body_changed_paths": ["$.model", "$.temperature"],
        "semantic_independent_variable": "model_only",
        "temperature_compatibility_note": (
            "第89道令明确写0.0；DeepSeek官方思考模式接受该字段但不生效，"
            "因此它是字节差异，不构成有效采样变量。"
        ),
        "messages_byte_equal": canonical_bytes(body["messages"])
        == canonical_bytes(baseline["messages"]),
        "messages_sha256": canonical_sha(body["messages"]),
        "route_change": {
            "provider": provider["provider"],
            "base_url": provider["base_url"],
            "endpoint": provider["endpoint"],
            "api_key_env": provider["api_key_env"],
        },
        "gold_or_answer_hits": forbidden,
    }
    return body, diff


def request_artifact(body: Mapping[str, Any], provider: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "z89-actual-request-v1",
        "run_id": RUN_ID,
        "logical_request_id": LOGICAL_REQUEST_ID,
        "provider": provider["provider"],
        "api_base_url": provider["base_url"],
        "api_endpoint": provider["endpoint"],
        "stage": "neutral_extract_strong_model_benchmark",
        "contract_version": CONTRACT_VERSION,
        "body": copy.deepcopy(body),
        "_security": "no_api_key_no_authorization",
    }


def secret_scan(root: Path, key: str | None = None) -> dict[str, Any]:
    key_bytes = key.encode("utf-8") if key else b""
    exact_key_hits: list[str] = []
    authorization_header_hits: list[str] = []

    def has_authorization_key(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(
                str(name).lower() == "authorization" or has_authorization_key(child)
                for name, child in value.items()
            )
        if isinstance(value, list):
            return any(has_authorization_key(child) for child in value)
        return False

    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        if key_bytes and key_bytes in raw:
            exact_key_hits.append(relative)
        request_bearing = relative.startswith(
            ("prepared/", "main/requests/", "checkpoints/")
        )
        if request_bearing and path.suffix.lower() in {".json", ".jsonl"}:
            try:
                if path.suffix.lower() == ".jsonl":
                    values = [
                        json.loads(line)
                        for line in raw.decode("utf-8").splitlines()
                        if line.strip()
                    ]
                    auth_hit = any(has_authorization_key(value) for value in values)
                else:
                    auth_hit = has_authorization_key(json.loads(raw.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                auth_hit = False
            if auth_hit:
                authorization_header_hits.append(relative)
    return {
        "exact_key_hits": exact_key_hits,
        "exact_key_hit_count": len(exact_key_hits),
        "authorization_header_hits": authorization_header_hits,
        "authorization_header_hit_count": len(authorization_header_hits),
    }


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    pins = source_pins()
    protected = protected_snapshot()
    body, diff = build_body()
    provider = load_provider()

    run_dir.mkdir(parents=True)
    copies = [
        copy_file(SOURCE_CHAPTER, run_dir / "inputs/chapters" / SOURCE_CHAPTER.name),
        copy_file(SOURCE_CATALOG, run_dir / "inputs/evidence_catalogs/ch0003.json"),
        copy_file(SOURCE_PROMPT_PACKAGE, run_dir / "prompt_frozen/事实说明书注入包_v3.json"),
        copy_file(SOURCE_BODY, run_dir / "provenance/retry03_ch0003_baseline_body.json"),
        copy_file(PROVIDER_CONFIG, run_dir / "channel/deepseek_official_v4_pro.json"),
    ]
    write_json_exclusive(run_dir / "prepared/request_body.json", body)
    write_json_exclusive(run_dir / "prepared/request_artifact.json", request_artifact(body, provider))
    write_json_exclusive(run_dir / "prepared/model_swap_diff.json", diff)
    preflight = {
        "schema_version": "z89-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": now_iso(),
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "target_chapters": [CHAPTER],
        "samples_per_chapter": 1,
        "source_pins": pins,
        "copied_inputs": copies,
        "protected_before": protected,
        "sampling": {
            "model": MODEL,
            "temperature_requested": REQUESTED_TEMPERATURE,
            "temperature_effective": "ignored_in_thinking_mode",
            "n": 1,
            "max_tokens": MAX_TOKENS,
            "response_format": {"type": "json_object"},
            "reasoning_effort_requested": REASONING_EFFORT_REQUESTED,
            "reasoning_effort_effective": REASONING_EFFORT_EFFECTIVE,
            "thinking_requested": THINKING_REQUESTED,
            "thinking_effective": THINKING_EFFECTIVE,
        },
        "transport": {
            "provider": provider["provider"],
            "url": provider["base_url"] + provider["endpoint"],
            "api_key_env": provider["api_key_env"],
            "429_policy": {
                "same_request_retries": 2,
                "backoff_seconds": [5, 10],
                "retry_after_over_seconds_hard_stop": 300,
                "run_fifth_429_hard_stop": True,
            },
            "401_403_5xx_auto_retry": False,
        },
        "request": {
            "body_path": "prepared/request_body.json",
            "body_sha256": sha256_file(run_dir / "prepared/request_body.json"),
            "artifact_path": "prepared/request_artifact.json",
            "artifact_sha256": sha256_file(run_dir / "prepared/request_artifact.json"),
            "messages_sha256": canonical_sha(body["messages"]),
            "messages_equal_retry03": body["messages"] == read_json(SOURCE_BODY)["messages"],
            "gold_or_answer_hits": diff["gold_or_answer_hits"],
        },
        "producer": {
            "path": Path(__file__).relative_to(ROOT).as_posix(),
            "sha256": sha256_file(Path(__file__)),
        },
    }
    write_json_exclusive(run_dir / "preflight.json", preflight)
    write_json_exclusive(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z89-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared_zero_call",
            "model_api_calls": 0,
            "network_attempts": 0,
            "authoritative_result": None,
        },
    )
    first = verify_prepared(run_dir)
    second = verify_prepared(run_dir)
    if first != second:
        raise ZBatchError("第89道机械验收连续两次不一致")
    verification = {
        "schema_version": "z89-prepared-verification-v1",
        "status": "pass_twice_identical",
        "first": first,
        "second": second,
        "vector_sha256": canonical_sha(first),
    }
    write_json_exclusive(run_dir / "prepared/mechanical_verification.json", verification)
    return preflight


def verify_prepared(run_dir: Path) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第89道预演状态不是零调用准备通过")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("第89道预演调用账不为0")
    if (run_dir / "main/run_claim.json").exists():
        raise ZBatchError("第89道已占用正式调用票，不能再按零调用准备验收")
    pins = source_pins()
    body, diff = build_body()
    provider = load_provider()
    actual_body = read_json(run_dir / "prepared/request_body.json")
    actual_artifact = read_json(run_dir / "prepared/request_artifact.json")
    if actual_body != body or read_json(run_dir / "prepared/model_swap_diff.json") != diff:
        raise ZBatchError("第89道冻结请求或差异票漂移")
    if actual_artifact != request_artifact(body, provider):
        raise ZBatchError("第89道请求工件不能机械重建")
    if sha256_file(Path(__file__)) != preflight["producer"]["sha256"]:
        raise ZBatchError("第89道运行器在 prepare 后漂移")
    copied = preflight.get("copied_inputs")
    if not isinstance(copied, list) or len(copied) != 5:
        raise ZBatchError("第89道冻结副本收据数量错误")
    for row in copied:
        target = Path(str(row["target"]))
        if not target.is_file() or sha256_file(target) != row["target_sha256"]:
            raise ZBatchError(f"第89道冻结副本漂移：{target}")
    scan = secret_scan(run_dir)
    if scan["authorization_header_hit_count"]:
        raise ZBatchError("第89道零调用工件出现 Authorization 字段")
    return {
        "source_pins_sha256": canonical_sha(pins),
        "body_sha256": sha256_file(run_dir / "prepared/request_body.json"),
        "artifact_sha256": sha256_file(run_dir / "prepared/request_artifact.json"),
        "messages_sha256": canonical_sha(body["messages"]),
        "messages_equal_retry03": body["messages"] == read_json(SOURCE_BODY)["messages"],
        "body_changed_paths": diff["body_changed_paths"],
        "gold_or_answer_hits": diff["gold_or_answer_hits"],
        "secret_scan": scan,
        "provider_config_sha256": PROVIDER_CONFIG_SHA256,
        "protected_before_sha256": canonical_sha(preflight["protected_before"]),
    }


def _safe_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    allowed = {"retry-after", "content-type", "x-request-id", "request-id"}
    return {
        str(key): str(value)
        for key, value in headers.items()
        if str(key).lower() in allowed
    }


def reserve_attempt(run_dir: Path, *, attempt: int, request_sha: str, wire_sha: str) -> None:
    row = {
        "schema_version": "z89-attempt-reservation-v1",
        "logical_request_id": LOGICAL_REQUEST_ID,
        "attempt": attempt,
        "request_artifact_sha256": request_sha,
        "wire_body_sha256": wire_sha,
        "reserved_at": now_iso(),
    }
    row["row_sha256"] = canonical_sha(row)
    append_jsonl_fsync(run_dir / "main/attempt_reservations.jsonl", row)


def send_once_factory(
    *,
    run_dir: Path,
    provider: Mapping[str, Any],
    request_sha: str,
    wire_body: bytes,
    wire_sha: str,
    opener: Any = None,
):
    key = os.environ.get(str(provider["api_key_env"]))
    if not key:
        raise ZBatchError(f"缺少 {provider['api_key_env']}；未创建调用占用票")
    open_fn = opener or urllib.request.build_opener(_NoRedirectHandler()).open
    url = str(provider["base_url"]) + str(provider["endpoint"])

    def send_once(attempt: int) -> z83_retry_transport.AttemptOutcome:
        reserve_attempt(run_dir, attempt=attempt, request_sha=request_sha, wire_sha=wire_sha)
        started = now_iso()
        request = urllib.request.Request(
            url,
            data=wire_body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with open_fn(request, timeout=600) as response:
                raw = response.read()
                status = int(getattr(response, "status", 200) or 200)
                headers = _safe_headers(dict(response.headers.items()))
            if key.encode("utf-8") in raw:
                raise Z89HardStop("api_key_echoed", "服务端响应回显 API Key，拒绝落盘")
            raw_path = run_dir / f"main/raw_responses/attempt{attempt:02d}.json"
            write_bytes_exclusive(raw_path, raw)
            parsed: Mapping[str, Any] | None = None
            usage: Mapping[str, Any] = {}
            envelope_error: str | None = None
            try:
                value = json.loads(raw.decode("utf-8"))
                if isinstance(value, dict):
                    parsed = value
                    if isinstance(value.get("usage"), Mapping):
                        usage = dict(value["usage"])
                else:
                    envelope_error = "http_200_non_object"
            except (UnicodeDecodeError, json.JSONDecodeError):
                envelope_error = "http_200_invalid_json"
            return z83_retry_transport.AttemptOutcome(
                http_status=status,
                request_sha256=request_sha,
                raw_response_sha256=sha256_bytes(raw),
                usage=usage,
                headers=headers,
                payload={
                    "raw_path": raw_path,
                    "response_json": parsed,
                    "envelope_error": envelope_error,
                },
                wire_body_sha256=wire_sha,
                request_artifact_sha256=request_sha,
                started_at=started,
                finished_at=now_iso(),
            )
        except urllib.error.HTTPError as exc:
            error_body = exc.read() if hasattr(exc, "read") else b""
            if key.encode("utf-8") in error_body:
                raise Z89HardStop("api_key_echoed", "错误响应回显 API Key，拒绝落盘")
            error_path = run_dir / f"main/errors/attempt{attempt:02d}.bin"
            write_bytes_exclusive(error_path, error_body)
            return z83_retry_transport.AttemptOutcome(
                http_status=int(exc.code),
                request_sha256=request_sha,
                headers=_safe_headers(dict(exc.headers.items())) if exc.headers else {},
                error_code=f"http_{int(exc.code)}",
                wire_body_sha256=wire_sha,
                request_artifact_sha256=request_sha,
                error_body_sha256=sha256_bytes(error_body),
                started_at=started,
                finished_at=now_iso(),
            )
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.IncompleteRead,
            ConnectionError,
            socket.timeout,
        ) as exc:
            partial = exc.partial if isinstance(exc, http.client.IncompleteRead) else b""
            return z83_retry_transport.AttemptOutcome(
                http_status=598,
                request_sha256=request_sha,
                error_code=f"transport_{type(exc).__name__}",
                wire_body_sha256=wire_sha,
                request_artifact_sha256=request_sha,
                error_body_sha256=sha256_bytes(partial),
                started_at=started,
                finished_at=now_iso(),
            )

    return send_once


def response_envelope(response: Mapping[str, Any]) -> tuple[dict[str, Any], str, str, str]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise Z89HardStop("response_choice_contract", "正式响应 choices 不是唯一对象")
    choice = choices[0]
    finish = choice.get("finish_reason")
    if finish == "length":
        raise Z89HardStop("finish_reason_length", "32k 下仍触顶，按令硬停")
    if finish != "stop":
        raise Z89HardStop("finish_reason_not_stop", f"finish_reason={finish!r} 不是 stop")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise Z89HardStop("response_message_contract", "正式响应缺 message 对象")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise Z89HardStop("empty_final_content", "正式响应正文为空")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise Z89HardStop("content_invalid_json", f"正式响应正文不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise Z89HardStop("content_non_object", "正式响应 JSON 不是对象")
    reasoning = message.get("reasoning_content")
    if reasoning is None:
        reasoning = ""
    if not isinstance(reasoning, str):
        raise Z89HardStop("reasoning_content_contract", "reasoning_content 不是字符串")
    model = response.get("model")
    if model != MODEL:
        raise Z89HardStop("response_model_mismatch", f"响应模型为 {model!r}，不是 {MODEL}")
    return payload, content, reasoning, str(finish)


def checkpoint_records(
    *,
    run_dir: Path,
    request_path: Path,
    request_sha: str,
    wire_sha: str,
    raw_path: Path | None,
    raw_sha: str | None,
    response: Mapping[str, Any] | None,
    attempts: Sequence[Mapping[str, Any]],
    usage: Mapping[str, Any] | str,
    mechanical_verdict: str,
) -> dict[str, Any]:
    checkpoint_dir = run_dir / "checkpoints/ch0003"
    if checkpoint_dir.exists():
        raise ZBatchError("第89道不可变检查点已存在，拒绝覆盖")
    response_model = response.get("model") if isinstance(response, Mapping) else None
    finish_reason = None
    content_sha = None
    reasoning_sha = None
    if isinstance(response, Mapping):
        choices = response.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
            finish_reason = choices[0].get("finish_reason")
            message = choices[0].get("message")
            if isinstance(message, Mapping):
                content = message.get("content")
                reasoning = message.get("reasoning_content")
                if isinstance(content, str):
                    content_sha = sha256_bytes(content.encode("utf-8"))
                if isinstance(reasoning, str):
                    reasoning_sha = sha256_bytes(reasoning.encode("utf-8"))
    documents = {
        "01_request.json": {
            "schema_version": "z89-checkpoint-request-v1",
            "logical_request_id": LOGICAL_REQUEST_ID,
            "contract_version": CONTRACT_VERSION,
            "request_artifact_path": request_path.relative_to(run_dir).as_posix(),
            "request_artifact_sha256": request_sha,
            "wire_body_sha256": wire_sha,
            "model": MODEL,
        },
        "02_response.json": {
            "schema_version": "z89-checkpoint-response-v1",
            "logical_request_id": LOGICAL_REQUEST_ID,
            "http_status": attempts[-1].get("http_status") if attempts else None,
            "raw_response_path": raw_path.relative_to(run_dir).as_posix() if raw_path else None,
            "raw_response_sha256": raw_sha,
            "response_model": response_model,
            "finish_reason": finish_reason,
            "content_sha256": content_sha,
            "reasoning_content_sha256": reasoning_sha,
        },
        "03_usage.json": {
            "schema_version": "z89-checkpoint-usage-v1",
            "logical_request_id": LOGICAL_REQUEST_ID,
            "usage": usage,
        },
        "04_attempts.json": {
            "schema_version": "z89-checkpoint-attempts-v1",
            "logical_request_id": LOGICAL_REQUEST_ID,
            "rows": [dict(row) for row in attempts],
            "attempt_rows_sha256": canonical_sha(list(attempts)),
        },
    }
    refs: dict[str, Any] = {}
    for name, value in documents.items():
        path = checkpoint_dir / name
        write_json_exclusive(path, value)
        refs[name] = sha256_file(path)
    seal_base = {
        "schema_version": "z89-checkpoint-seal-v1",
        "contract_version": CONTRACT_VERSION,
        "logical_request_id": LOGICAL_REQUEST_ID,
        "mechanical_verdict": mechanical_verdict,
        "artifacts": refs,
        "sealed": True,
    }
    seal = {**seal_base, "checkpoint_id": canonical_sha(seal_base)}
    write_json_exclusive(checkpoint_dir / "05_seal.json", seal)
    return seal


def load_attempt_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_hard_stop(run_dir: Path, *, reason_code: str, error: BaseException) -> dict[str, Any]:
    path = run_dir / "main/hard_stop.json"
    if path.exists():
        return read_json(path)
    attempts = load_attempt_rows(run_dir / "main/call_attempts.jsonl")
    receipt = {
        "schema_version": "z89-hard-stop-v1",
        "status": "hard_stop_no_rerun_no_patch",
        "reason_code": reason_code,
        "error_type": type(error).__name__,
        "error": str(error),
        "logical_sample_count": 1 if attempts else 0,
        "network_attempts": len(attempts),
        "successful_responses": sum(1 for row in attempts if row.get("http_status") == 200),
        "usage_tokens": sum(
            int(row.get("usage", {}).get("total_tokens", 0))
            for row in attempts
            if isinstance(row.get("usage"), Mapping)
        ),
        "rerun_allowed": False,
        "created_at": now_iso(),
    }
    write_json_exclusive(path, receipt)
    return receipt


def build_score_template(run_dir: Path, event_ids: Sequence[str]) -> dict[str, Any]:
    formal = z75_score.load_formal_gold(GOLD_POINTER)
    if formal["gold_sha256"] != GOLD_FILE_SHA256 or formal["denominator"] != 23:
        raise ZBatchError("现役金标指针不再指向 v1.2 分母23")
    score_dir = run_dir / "score_only"
    copies = [
        copy_file(GOLD_POINTER, score_dir / "正式金标指针.json"),
        copy_file(GOLD_FILE, score_dir / "第3章结构层金标v1.2.json"),
    ]
    rows = [
        {
            "part_id": part_id,
            "claim": part["claim"],
            "verdict": "pending",
            "candidate_event_ids": [],
            "reason": "",
        }
        for part_id, part in formal["parts"].items()
    ]
    template = {
        "schema_version": "z89-gold-adjudication-template-v1",
        "status": "awaiting_local_semantic_review",
        "gold_sha256": GOLD_FILE_SHA256,
        "formal_denominator": 23,
        "candidate_event_ids": list(event_ids),
        "gold_rows": rows,
        "score_only_copies": copies,
        "model_visible_request_contains_score_material": False,
    }
    write_json_exclusive(run_dir / "review/adjudication_template.json", template)
    return template


def run(run_dir: Path = DEFAULT_RUN_DIR, *, opener: Any = None) -> dict[str, Any]:
    verify_prepared(run_dir)
    if os.environ.get(OFFICIAL_APPROVAL_ENV) != OFFICIAL_APPROVAL_VALUE:
        raise ZBatchError(
            "DeepSeek 官方 API 默认永久禁用；缺少 CZ 当前任务明确正向一次性授权"
        )
    provider = load_provider()
    key = os.environ.get(str(provider["api_key_env"]))
    if not key:
        raise ZBatchError("缺少 DEEPSEEK_API_KEY；0调用停在发网前")
    claim_path = run_dir / "main/run_claim.json"
    claim = {
        "schema_version": "z89-run-claim-v1",
        "run_id": run_dir.name,
        "logical_request_id": LOGICAL_REQUEST_ID,
        "single_sample_no_rerun": True,
        "claimed_at": now_iso(),
    }
    write_json_exclusive(claim_path, claim)

    body = read_json(run_dir / "prepared/request_body.json")
    artifact = request_artifact(body, provider)
    request_path = run_dir / "main/requests/z89_ch0003_request.json"
    write_json_exclusive(request_path, artifact)
    request_sha = sha256_file(request_path)
    wire = json.dumps(body, ensure_ascii=False).encode("utf-8")
    wire_sha = sha256_bytes(wire)
    if read_json(request_path)["body"] != body:
        raise ZBatchError("第89道实发 body 不能从请求工件逐字重建")
    if key in request_path.read_text(encoding="utf-8"):
        raise ZBatchError("第89道请求工件意外包含 API Key")

    attempt_path = run_dir / "main/call_attempts.jsonl"
    policy = z83_retry_transport.RetryPolicy(
        retry_delays_seconds=(5.0, 10.0),
        max_429_retries_per_request=2,
        max_429_per_run=5,
        max_retry_after_seconds=300.0,
        same_chapter_gap_seconds=10.0,
        cross_chapter_gap_seconds=30.0,
    )
    try:
        logical = z83_retry_transport.run_logical_request(
            logical_request_id=LOGICAL_REQUEST_ID,
            chapter=CHAPTER,
            send_once=send_once_factory(
                run_dir=run_dir,
                provider=provider,
                request_sha=request_sha,
                wire_body=wire,
                wire_sha=wire_sha,
                opener=opener,
            ),
            attempt_ledger_path=attempt_path,
            contract_version=CONTRACT_VERSION,
            state=z83_retry_transport.RetryRunState(),
            policy=policy,
        )
    except z83_retry_transport.RetryTransportHardStop as exc:
        write_hard_stop(run_dir, reason_code=exc.reason_code, error=exc)
        raise Z89HardStop(exc.reason_code, str(exc)) from exc

    payload = logical.outcome.payload
    if not isinstance(payload, Mapping) or payload.get("envelope_error"):
        exc = Z89HardStop(
            str(payload.get("envelope_error") if isinstance(payload, Mapping) else "missing_payload"),
            "HTTP 200 响应外壳不能解析",
        )
        write_hard_stop(run_dir, reason_code=exc.reason_code, error=exc)
        raise exc
    response = payload.get("response_json")
    raw_path = payload.get("raw_path")
    if not isinstance(response, Mapping) or not isinstance(raw_path, Path):
        exc = Z89HardStop("response_payload_contract", "正式响应工件缺失")
        write_hard_stop(run_dir, reason_code=exc.reason_code, error=exc)
        raise exc
    attempts = list(logical.attempt_rows)
    raw_sha = logical.outcome.raw_response_sha256
    usage = dict(logical.outcome.usage or {})

    try:
        model_data, content, reasoning, finish = response_envelope(response)
        catalog_doc = read_json(run_dir / "inputs/evidence_catalogs/ch0003.json")
        catalog = catalog_doc.get("entries") if isinstance(catalog_doc, Mapping) else None
        if not isinstance(catalog, list):
            raise Z89HardStop("catalog_contract", "冻结证据目录缺 entries")
        materialized, audit = neutral_extract.process_model_data(
            model_data, chapter=CHAPTER, catalog=catalog
        )
        if audit.get("missing_catalog_anchor_ids"):
            raise Z89HardStop("outside_catalog_anchor", "目录外锚不为0")
        model_path = run_dir / "main/01_extract/model_json/ch0003.json"
        events_path = run_dir / "main/01_extract/events/ch0003.json"
        audit_path = run_dir / "main/01_extract/program_audits/ch0003.json"
        write_json_exclusive(model_path, model_data)
        write_json_exclusive(events_path, materialized)
        write_json_exclusive(audit_path, audit)
        events = model_data.get("events")
        assert isinstance(events, list)
        mechanical = {
            "schema_version": "z89-mechanical-three-gates-v1",
            "status": "pass",
            "json_and_schema_gate": True,
            "catalog_anchor_gate": len(audit["missing_catalog_anchor_ids"]) == 0,
            "length_and_contiguous_id_gate": (
                audit["status"] == "pass"
                and audit["event_ids_contiguous"]
                and audit["invalid_event_id_count"] == 0
            ),
            "event_count": len(events),
            "anchor_reference_count": audit["anchor_reference_count"],
            "catalog_anchor_count": audit["catalog_anchor_count"],
            "outside_catalog_anchor_count": len(audit["missing_catalog_anchor_ids"]),
            "invalid_event_id_count": audit["invalid_event_id_count"],
            "events_without_anchors": audit["events_without_anchors"],
            "finish_reason": finish,
            "response_model": response.get("model"),
            "content_sha256": sha256_bytes(content.encode("utf-8")),
            "reasoning_content_sha256": sha256_bytes(reasoning.encode("utf-8")),
        }
        write_json_exclusive(run_dir / "main/mechanical_three_gates.json", mechanical)
        usage_row = {
            "schema_version": "z89-usage-v1",
            "logical_request_id": LOGICAL_REQUEST_ID,
            "chapter": CHAPTER,
            "request_artifact_sha256": request_sha,
            "raw_response_sha256": raw_sha,
            "usage": usage,
            "recorded_at": now_iso(),
        }
        usage_row["row_sha256"] = canonical_sha(usage_row)
        append_jsonl_fsync(run_dir / "main/usage.jsonl", usage_row)
        checkpoint = checkpoint_records(
            run_dir=run_dir,
            request_path=request_path,
            request_sha=request_sha,
            wire_sha=wire_sha,
            raw_path=raw_path,
            raw_sha=raw_sha,
            response=response,
            attempts=attempts,
            usage=usage,
            mechanical_verdict="pass",
        )
        template = build_score_template(
            run_dir, [str(row.get("event_id")) for row in events if isinstance(row, Mapping)]
        )
    except (Z89HardStop, ZBatchError) as exc:
        reason = exc.reason_code if isinstance(exc, Z89HardStop) else "mechanical_contract_failure"
        if not (run_dir / "checkpoints/ch0003").exists():
            checkpoint_records(
                run_dir=run_dir,
                request_path=request_path,
                request_sha=request_sha,
                wire_sha=wire_sha,
                raw_path=raw_path,
                raw_sha=raw_sha,
                response=response,
                attempts=attempts,
                usage=usage,
                mechanical_verdict="fail",
            )
        write_hard_stop(run_dir, reason_code=reason, error=exc)
        raise Z89HardStop(reason, str(exc)) from exc

    scan = secret_scan(run_dir, key)
    if scan["exact_key_hit_count"] or scan["authorization_header_hit_count"]:
        exc = Z89HardStop("secret_trace_detected", "运行目录检出密钥或 Authorization 痕迹")
        write_hard_stop(run_dir, reason_code=exc.reason_code, error=exc)
        raise exc
    protected_after = protected_snapshot()
    if protected_after != read_json(run_dir / "preflight.json")["protected_before"]:
        exc = Z89HardStop("protected_artifact_drift", "现役件或 retry13 封存树发生漂移")
        write_hard_stop(run_dir, reason_code=exc.reason_code, error=exc)
        raise exc
    completion = {
        "schema_version": "z89-sample-completion-v1",
        "status": "sample_completed_awaiting_semantic_score",
        "logical_samples": 1,
        "network_attempts": len(attempts),
        "429_count": sum(1 for row in attempts if row.get("http_status") == 429),
        "response_model": response.get("model"),
        "finish_reason": finish,
        "usage": usage,
        "event_count": mechanical["event_count"],
        "mechanical_three_gates": "pass",
        "checkpoint_id": checkpoint["checkpoint_id"],
        "adjudication_template_sha256": canonical_sha(template),
        "secret_scan": scan,
        "protected_unchanged": True,
        "completed_at": now_iso(),
    }
    write_json_exclusive(run_dir / "main/sample_completion.json", completion)
    return completion


def validate_adjudication(run_dir: Path, path: Path) -> list[dict[str, Any]]:
    doc = read_json(path)
    if not isinstance(doc, Mapping) or doc.get("schema_version") != "z89-gold-adjudication-v1":
        raise ZBatchError("第89道判词版本错误")
    if doc.get("gold_sha256") != GOLD_FILE_SHA256 or doc.get("formal_denominator") != 23:
        raise ZBatchError("第89道判词没有钉现役金标 v1.2／分母23")
    event_doc = read_json(run_dir / "main/01_extract/model_json/ch0003.json")
    events = event_doc.get("events") if isinstance(event_doc, Mapping) else None
    if not isinstance(events, list):
        raise ZBatchError("第89道缺模型事件")
    event_ids = {
        str(row.get("event_id")) for row in events if isinstance(row, Mapping)
    }
    formal = z75_score.load_formal_gold(GOLD_POINTER)
    rows = doc.get("gold_rows")
    if not isinstance(rows, list) or len(rows) != 23:
        raise ZBatchError("第89道判词必须逐条覆盖23个金标原子")
    allowed = {"strict_hit", "semantic_shadow", "coverage_only_invalid_support", "miss"}
    seen: set[str] = set()
    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ZBatchError("第89道判词含非对象")
        part_id = row.get("part_id")
        verdict = row.get("verdict")
        candidates = row.get("candidate_event_ids")
        reason = row.get("reason")
        if part_id not in formal["parts"] or part_id in seen:
            raise ZBatchError(f"第89道判词金标编号重复或越界：{part_id}")
        if verdict not in allowed:
            raise ZBatchError(f"第89道判词状态错误：{part_id}")
        if not isinstance(candidates, list) or any(value not in event_ids for value in candidates):
            raise ZBatchError(f"第89道判词引用不存在的候选事件：{part_id}")
        if verdict == "miss" and candidates:
            raise ZBatchError(f"第89道漏项不得夹带候选事件：{part_id}")
        if verdict != "miss" and not candidates:
            raise ZBatchError(f"第89道命中／影子必须引用候选事件：{part_id}")
        if not isinstance(reason, str) or not reason.strip():
            raise ZBatchError(f"第89道判词缺逐条理由：{part_id}")
        seen.add(str(part_id))
        result.append(dict(row))
    if seen != set(formal["parts"]):
        raise ZBatchError("第89道判词没有覆盖完整23条")
    return result


def score(run_dir: Path, adjudication: Path) -> dict[str, Any]:
    if (run_dir / "main/hard_stop.json").exists():
        raise ZBatchError("第89道已硬停，禁止判成正式质量结果")
    if not (run_dir / "main/sample_completion.json").is_file():
        raise ZBatchError("第89道正式样张尚未完成")
    rows = validate_adjudication(run_dir, adjudication)
    summary = z75_score.score_summary(rows, 23)
    strict = summary["strict_hit"]
    if strict >= 10:
        prewritten = "model_capability_contributes_change_arm_question_on_table"
        plain = "严格命中达到10条，病根包含模型能力；只把换模型方案端上桌，不自动升默认。"
    elif 5 <= strict <= 7:
        prewritten = "approximately_six_contract_scoring_or_supply_direction"
        plain = "严格命中仍约6条，优先回合同、判分或供料方向；不再把差距主要归给模型强弱。"
    else:
        prewritten = "between_prewritten_thresholds_requires_cz_review"
        plain = "严格命中落在两条预写判断之间，只登记读数，交CZ另拍。"
    protected_after = protected_snapshot()
    protected_before = read_json(run_dir / "preflight.json")["protected_before"]
    if protected_after != protected_before:
        raise ZBatchError("第89道判分前发现现役件或 retry13 封存树漂移")
    target = run_dir / "review/adjudication_completed.json"
    if adjudication.resolve() != target.resolve():
        copy_file(adjudication.resolve(), target)
    receipt = {
        "schema_version": "z89-scorecard-v1",
        "status": "candidate_silver_scored",
        "gold_chapter_3": summary,
        "comparisons": {
            "retry03_current_baseline": {"strict_hit": 6, "effective_recall": 20},
            "z79_v3_historical_best": {"strict_hit": 10},
            "z89_deepseek_v4_pro": {
                "strict_hit": summary["strict_hit"],
                "effective_recall": summary["effective_recall"],
            },
        },
        "prewritten_interpretation": prewritten,
        "interpretation_plain": plain,
        "mechanical_three_gates": read_json(run_dir / "main/mechanical_three_gates.json"),
        "single_sample_no_rerun": True,
        "candidate_tier": "silver_only",
        "promoted_or_default_changed": False,
        "protected_unchanged": True,
        "adjudication": {
            "path": target.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(target),
        },
        "created_at": now_iso(),
    }
    write_json_exclusive(run_dir / "final/scorecard.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify", "run", "score"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--adjudication", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    try:
        if args.action == "prepare":
            result = prepare(run_dir)
        elif args.action == "verify":
            result = verify_prepared(run_dir)
        elif args.action == "run":
            result = run(run_dir)
        else:
            if args.adjudication is None:
                parser.error("score 必须提供 --adjudication")
            result = score(run_dir, args.adjudication.resolve())
    except (ZBatchError, Z89HardStop) as exc:
        print(
            json.dumps(
                {"status": "error", "type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
