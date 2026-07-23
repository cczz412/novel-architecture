"""SenseNova API 活跃运输模块。

输入只有 messages、阶段合同和固定路由；输出保留原始 HTTP 回包与可审计元数据。
D-MOD-002 已把它接入 ``tools/zbatch.py``；温度、模型和 ``n=1`` 只从固定合同读取。
"""

from __future__ import annotations

import fcntl
import hashlib
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from .errors import ZBatchError
from .stage_sampling import StageContractBundle, StageSamplingContract


PINNED_PROVIDER = "sensenova"
PINNED_BASE_URL = "https://token.sensenova.cn/v1"
PINNED_ENDPOINT = "/chat/completions"
PINNED_MODEL = "deepseek-v4-flash"
PINNED_API_KEY_ENV = "SENSENOVA_API_KEY"
SAFE_RESPONSE_HEADERS = frozenset({"content-type", "date", "x-request-id", "request-id"})
SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_response_failure(
    *,
    run_dir: Path,
    stage: str,
    case_id: str,
    raw: bytes,
    reason_code: str,
    safe_details: Mapping[str, Any] | None = None,
) -> None:
    lines = [
        f"reason_code={reason_code}",
        f"raw_response_bytes={len(raw)}",
        f"raw_response_sha256={_sha256_bytes(raw)}",
        "raw_response_persisted=true",
    ]
    for name, value in sorted((safe_details or {}).items()):
        lines.append(f"{name}={value}")
    _write_text(
        run_dir / "errors" / f"{stage}_{case_id}_response.txt",
        "\n".join(lines) + "\n",
    )


@dataclass(frozen=True)
class TransportRoute:
    provider: str
    base_url: str
    endpoint: str
    model: str
    api_key_env: str
    timeout_seconds: int
    network_attempts: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TransportRoute":
        misplaced = sorted(
            name
            for name in ("temperature", "max_tokens", "max_tokens_by_stage", "n", "reasoning_effort", "response_format")
            if name in raw
        )
        if misplaced:
            raise ZBatchError(f"路由层混入阶段采样字段：{misplaced}")
        provider = str(raw.get("provider") or "")
        base_url = str(raw.get("base_url") or "")
        endpoint = str(raw.get("endpoint") or "")
        model = str(raw.get("model") or "")
        allowed = raw.get("allowed_models")
        if provider != PINNED_PROVIDER:
            raise ZBatchError("运输模块只允许 provider=sensenova")
        if base_url != PINNED_BASE_URL or endpoint != PINNED_ENDPOINT:
            raise ZBatchError("SenseNova 路由与钉死地址不一致，拒绝调用")
        if model != PINNED_MODEL:
            raise ZBatchError(f"运输模块只允许模型 {PINNED_MODEL}，收到：{model}")
        if allowed != [PINNED_MODEL]:
            raise ZBatchError(f"allowed_models 必须且只能登记 {PINNED_MODEL}")
        key_env = str(raw.get("api_key_env") or "").strip()
        if key_env != PINNED_API_KEY_ENV:
            raise ZBatchError(f"api_key_env 必须钉死为 {PINNED_API_KEY_ENV}")
        timeout_raw = raw.get("timeout_seconds")
        attempts_raw = raw.get("network_attempts")
        if isinstance(timeout_raw, bool) or not isinstance(timeout_raw, int):
            raise ZBatchError("timeout_seconds 必须是整数")
        if isinstance(attempts_raw, bool) or not isinstance(attempts_raw, int):
            raise ZBatchError("network_attempts 必须是整数")
        timeout = timeout_raw
        attempts = attempts_raw
        if timeout <= 0 or attempts <= 0:
            raise ZBatchError("timeout_seconds 与 network_attempts 必须大于 0")
        return cls(provider, base_url, endpoint, model, key_env, timeout, attempts)

    @property
    def url(self) -> str:
        return self.base_url + self.endpoint


@dataclass(frozen=True)
class TransportResult:
    """一次成功运输的原始回包与最小解包结果。"""

    request_record: Mapping[str, Any]
    raw_response: bytes
    response_json: Mapping[str, Any]
    content: str
    finish_reason: str | None
    usage: Mapping[str, Any]
    metadata: Mapping[str, Any]


def validate_messages(messages: list[dict[str, str]]) -> None:
    if not isinstance(messages, list) or not messages:
        raise ZBatchError("messages 必须是非空列表")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ZBatchError(f"messages[{index}] 必须是对象")
        if message.get("role") not in {"system", "user", "assistant"}:
            raise ZBatchError(f"messages[{index}] 的 role 不受支持")
        content = message.get("content")
        if not isinstance(content, str) or not content:
            raise ZBatchError(f"messages[{index}] 的 content 不能为空")


def build_request_body(
    *,
    model: str,
    messages: list[dict[str, str]],
    contract: StageSamplingContract,
    allow_unverified_candidate: bool = False,
) -> dict[str, Any]:
    """把阶段合同逐字段投影到请求体；不读任何全局 temperature。"""

    if model != PINNED_MODEL:
        raise ZBatchError(f"请求体只允许模型 {PINNED_MODEL}")
    validate_messages(messages)
    contract.assert_callable(allow_unverified_candidate=allow_unverified_candidate)
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": contract.temperature,
        "max_tokens": contract.max_tokens,
        "n": contract.n,
        "response_format": dict(contract.response_format),
    }
    if contract.reasoning_effort and contract.reasoning_effort.lower() not in {"omit", "off", "-"}:
        body["reasoning_effort"] = contract.reasoning_effort
    return body


def response_content(data: Mapping[str, Any]) -> tuple[str, str | None]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ZBatchError("API 响应没有 choices")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ZBatchError("API 响应正文为空")
    finish_reason = first.get("finish_reason")
    return content, str(finish_reason) if finish_reason is not None else None


class ApiTransport:
    """可独测的 API 运输器；默认拒绝未验证候选合同。"""

    def __init__(
        self,
        *,
        route: TransportRoute,
        contracts: Mapping[str, StageSamplingContract],
        run_dir: Path,
        max_calls: int,
        allow_unverified_candidates: bool = False,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
        now_iso: Callable[[], str] | None = None,
    ):
        if max_calls <= 0:
            raise ZBatchError("max_calls 必须大于 0")
        self.route = route
        self.contracts = dict(contracts)
        self.run_dir = run_dir
        self.max_calls = max_calls
        self.allow_unverified_candidates = allow_unverified_candidates
        self.opener = opener or urllib.request.urlopen
        self.sleeper = sleeper or time.sleep
        self.monotonic = monotonic or time.monotonic
        self.now_iso = now_iso or _now_iso
        attempts_path = run_dir / "call_attempts.jsonl"
        self.calls_made = 0
        if attempts_path.is_file():
            self.calls_made = sum(1 for line in attempts_path.read_text(encoding="utf-8").splitlines() if line.strip())

    @classmethod
    def from_bundle(
        cls,
        bundle: StageContractBundle,
        *,
        run_dir: Path,
        max_calls: int,
        **kwargs: Any,
    ) -> "ApiTransport":
        return cls(
            route=TransportRoute.from_mapping(bundle.route),
            contracts=bundle.stages,
            run_dir=run_dir,
            max_calls=max_calls,
            **kwargs,
        )

    def request_body(self, *, stage: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        contract = self._contract(stage)
        return build_request_body(
            model=self.route.model,
            messages=messages,
            contract=contract,
            allow_unverified_candidate=self.allow_unverified_candidates,
        )

    def _contract(self, stage: str) -> StageSamplingContract:
        if not SAFE_ARTIFACT_NAME.fullmatch(stage):
            raise ZBatchError(f"阶段名不安全：{stage}")
        try:
            contract = self.contracts[stage]
        except KeyError as exc:
            raise ZBatchError(f"没有阶段级采样合同：{stage}") from exc
        if contract.stage != stage:
            raise ZBatchError(f"阶段合同键名与内容不一致：{stage}/{contract.stage}")
        return contract

    def _reserve_attempt(self, *, stage: str, case_id: str, attempt: int, request_sha: str) -> None:
        """跨对象、跨进程原子占用一次调用名额；占到即记账，崩溃也不退额度。"""

        lock_path = self.run_dir / ".api_call_budget.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        attempts_path = self.run_dir / "call_attempts.jsonl"
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                current = 0
                if attempts_path.is_file():
                    current = sum(
                        1
                        for line in attempts_path.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    )
                if current >= self.max_calls:
                    self.calls_made = current
                    raise ZBatchError(f"调用闸已满：{current}/{self.max_calls}，拒绝多发一次")
                call_number = current + 1
                _append_jsonl(
                    attempts_path,
                    {
                        "at": self.now_iso(),
                        "call_number": call_number,
                        "max_calls": self.max_calls,
                        "stage": stage,
                        "case_id": case_id,
                        "attempt": attempt,
                        "request_sha256": request_sha,
                    },
                )
                self.calls_made = call_number
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def call(self, *, stage: str, case_id: str, messages: list[dict[str, str]]) -> TransportResult:
        key = os.environ.get(self.route.api_key_env)
        if not key:
            raise ZBatchError(f"缺少 {self.route.api_key_env}；先载入 SenseNova 环境脚本")
        if not isinstance(case_id, str) or not SAFE_ARTIFACT_NAME.fullmatch(case_id):
            raise ZBatchError(f"case_id 不安全：{case_id}")
        contract = self._contract(stage)
        body = build_request_body(
            model=self.route.model,
            messages=messages,
            contract=contract,
            allow_unverified_candidate=self.allow_unverified_candidates,
        )
        candidate_override = contract.status == "candidate_unverified"
        request_record = {
            "provider": self.route.provider,
            "api_base_url": self.route.base_url,
            "api_endpoint": self.route.endpoint,
            "stage": stage,
            "case_id": case_id,
            "contract_status": contract.status,
            "unverified_candidate_override": candidate_override,
            "body": body,
            "_security": "no_api_key_no_authorization",
        }
        if key in json.dumps(request_record, ensure_ascii=False):
            raise ZBatchError("请求内容意外包含 API Key；拒绝落盘与发送")
        request_path = self.run_dir / "requests" / stage / f"{case_id}_request.json"
        request_text = json.dumps(request_record, ensure_ascii=False, indent=2) + "\n"
        request_sha = _sha256_bytes(request_text.encode("utf-8"))

        last_error: Exception | None = None
        for attempt in range(1, self.route.network_attempts + 1):
            self._reserve_attempt(stage=stage, case_id=case_id, attempt=attempt, request_sha=request_sha)
            if attempt == 1:
                _write_text(request_path, request_text)
            request = urllib.request.Request(
                self.route.url,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST",
            )
            started = self.monotonic()
            try:
                with self.opener(request, timeout=self.route.timeout_seconds) as response:
                    raw = response.read()
                    status = getattr(response, "status", None)
                    safe_headers = {
                        name: value
                        for name, value in response.headers.items()
                        if name.lower() in SAFE_RESPONSE_HEADERS
                    }
                if key.encode("utf-8") in raw:
                    raise ZBatchError("服务端响应意外回显 API Key；原始响应拒绝落盘")
                elapsed_ms = int((self.monotonic() - started) * 1000)
                raw_path = self.run_dir / "responses" / stage / f"{case_id}_raw.json"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(raw)
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    _write_response_failure(
                        run_dir=self.run_dir,
                        stage=stage,
                        case_id=case_id,
                        raw=raw,
                        reason_code="http_200_invalid_json",
                    )
                    raise ZBatchError(f"HTTP 成功但响应不是 JSON：{case_id}") from exc
                if not isinstance(data, dict):
                    _write_response_failure(
                        run_dir=self.run_dir,
                        stage=stage,
                        case_id=case_id,
                        raw=raw,
                        reason_code="http_200_non_object",
                        safe_details={"top_level_type": type(data).__name__},
                    )
                    raise ZBatchError(f"HTTP 成功但响应顶层不是对象：{case_id}")
                response_model = data.get("model")
                if response_model != self.route.model:
                    model_text = response_model if isinstance(response_model, str) else type(response_model).__name__
                    _write_response_failure(
                        run_dir=self.run_dir,
                        stage=stage,
                        case_id=case_id,
                        raw=raw,
                        reason_code="response_model_mismatch",
                        safe_details={
                            "expected_model": self.route.model,
                            "response_model_bytes": len(model_text.encode("utf-8")),
                            "response_model_sha256": _sha256_bytes(model_text.encode("utf-8")),
                        },
                    )
                    raise ZBatchError(f"API 响应模型与请求不一致：{case_id}")
                try:
                    content, finish_reason = response_content(data)
                except ZBatchError:
                    _write_response_failure(
                        run_dir=self.run_dir,
                        stage=stage,
                        case_id=case_id,
                        raw=raw,
                        reason_code="response_envelope_invalid",
                    )
                    raise
                if finish_reason != "stop":
                    _write_response_failure(
                        run_dir=self.run_dir,
                        stage=stage,
                        case_id=case_id,
                        raw=raw,
                        reason_code="response_finish_reason_not_stop",
                        safe_details={"finish_reason": finish_reason or "missing"},
                    )
                    raise ZBatchError(
                        f"API 响应未正常结束：{case_id}，finish_reason={finish_reason or 'missing'}"
                    )
                metadata = {
                    "at": self.now_iso(),
                    "http_status": status,
                    "elapsed_ms": elapsed_ms,
                    "provider": self.route.provider,
                    "api_base_url": self.route.base_url,
                    "api_endpoint": self.route.endpoint,
                    "requested_model": self.route.model,
                    "response_model": response_model,
                    "finish_reason": finish_reason,
                    "request_sha256": request_sha,
                    "raw_response_sha256": _sha256_bytes(raw),
                    "headers": safe_headers,
                    "sampling_n": body["n"],
                    "stage_temperature": body["temperature"],
                    "stage_max_tokens": body["max_tokens"],
                    "contract_status": contract.status,
                    "unverified_candidate_override": candidate_override,
                }
                _write_json(self.run_dir / "responses" / stage / f"{case_id}_meta.json", metadata)
                usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                _append_jsonl(
                    self.run_dir / "usage.jsonl",
                    {**metadata, "stage": stage, "case_id": case_id, "usage": usage},
                )
                return TransportResult(
                    request_record=request_record,
                    raw_response=raw,
                    response_json=data,
                    content=content,
                    finish_reason=finish_reason,
                    usage=usage,
                    metadata=metadata,
                )
            except urllib.error.HTTPError as exc:
                last_error = exc
                error_body = exc.read() if hasattr(exc, "read") else b""
                _write_text(
                    self.run_dir / "errors" / f"{stage}_{case_id}_attempt{attempt}.txt",
                    (
                        f"HTTP {exc.code}\n"
                        f"error_body_bytes={len(error_body)}\n"
                        f"error_body_sha256={_sha256_bytes(error_body)}\n"
                        "error_body_not_persisted=security_policy\n"
                    ),
                )
                retryable = exc.code == 429 or exc.code >= 500
                if not retryable or attempt >= self.route.network_attempts:
                    break
            except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, ConnectionError) as exc:
                last_error = exc
                partial = exc.partial if isinstance(exc, http.client.IncompleteRead) else b""
                _write_text(
                    self.run_dir / "errors" / f"{stage}_{case_id}_attempt{attempt}.txt",
                    (
                        f"{type(exc).__name__}: {exc}\n"
                        f"partial_bytes={len(partial)}\n"
                        f"partial_sha256={_sha256_bytes(partial)}\n"
                        "partial_body_not_persisted=security_and_integrity_policy\n"
                    ),
                )
                if attempt >= self.route.network_attempts:
                    break
            if attempt < self.route.network_attempts:
                self.sleeper(min(2 * attempt, 6))
        raise ZBatchError(f"API 调用失败：{stage}/{case_id}：{last_error}")
