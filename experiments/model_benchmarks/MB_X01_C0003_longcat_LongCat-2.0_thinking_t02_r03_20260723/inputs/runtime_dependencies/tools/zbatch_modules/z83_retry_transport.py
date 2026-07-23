"""Z83 retry13 专用的运输节流与不可变检查点辅助件。

这个模块故意不修改 :mod:`api_transport` 的默认行为。主工具把“发一次”
的函数传进来，本模块只负责章间间隔、429 退避、每次尝试的追加记账，
以及成功后的五件套检查点。它不作任何语义判定。
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .errors import ZBatchError


ATTEMPT_LEDGER_SCHEMA = "z83-retry-attempt-v1"
RETRY_WAIT_LEDGER_SCHEMA = "z83-retry-wait-v1"
CHECKPOINT_SCHEMA = "z83-immutable-checkpoint-v1"
UNKNOWN_USAGE = "unknown"
SHA256_HEX_LENGTH = 64


class RetryTransportHardStop(ZBatchError):
    """本轮运输已触发预写止损线。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class RetryPolicy:
    """retry13 的固定运输参数。"""

    same_chapter_gap_seconds: float = 10.0
    cross_chapter_gap_seconds: float = 30.0
    retry_delays_seconds: tuple[float, float] = (5.0, 10.0)
    max_429_retries_per_request: int = 2
    max_429_per_run: int = 5
    max_retry_after_seconds: float = 300.0

    def validate(self) -> None:
        if self.same_chapter_gap_seconds < 0 or self.cross_chapter_gap_seconds < 0:
            raise ZBatchError("章间间隔不能为负数")
        if self.cross_chapter_gap_seconds < self.same_chapter_gap_seconds:
            raise ZBatchError("跨章间隔不能短于同章间隔")
        if self.max_429_retries_per_request != len(self.retry_delays_seconds):
            raise ZBatchError("429 重试次数必须与退避档位数一致")
        if any(delay < 0 for delay in self.retry_delays_seconds):
            raise ZBatchError("429 退避时间不能为负数")
        if self.max_429_per_run <= 0 or self.max_retry_after_seconds <= 0:
            raise ZBatchError("整轮 429 上限与 Retry-After 上限必须大于 0")


@dataclass(frozen=True)
class AttemptOutcome:
    """调用方的“发一次”函数返回的最小运输结果。

    ``payload`` 是调用方需要继续处理的成功结果；本模块不解析它。
    HTTP 失败时 ``raw_response_sha256`` 可为 ``None``，但不允许把响应正文写进尝试账。
    """

    http_status: int
    request_sha256: str
    raw_response_sha256: str | None = None
    usage: Mapping[str, Any] | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    payload: Any = None
    error_code: str | None = None
    wire_body_sha256: str | None = None
    request_artifact_sha256: str | None = None
    error_body_sha256: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class RetryRunState:
    """跨逻辑请求的限流状态；可从既有尝试账重建。"""

    total_429: int = 0
    last_logical_completed_monotonic: float | None = None
    last_chapter: int | None = None

    @classmethod
    def from_attempt_rows(cls, rows: Sequence[Mapping[str, Any]]) -> "RetryRunState":
        total_429 = sum(1 for row in rows if row.get("http_status") == 429)
        return cls(total_429=total_429)


@dataclass(frozen=True)
class LogicalRequestResult:
    outcome: AttemptOutcome
    attempt_rows: tuple[Mapping[str, Any], ...]
    checkpoint: Mapping[str, Any]


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def retry_wait_ledger_path(attempt_ledger_path: Path) -> Path:
    """返回追加式等待票路径；它与尝试账并排，但不回写尝试行。"""

    return attempt_ledger_path.with_name(
        f"{attempt_ledger_path.stem}_retry_waits.jsonl"
    )


def validate_retry_wait_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    required = {
        "schema",
        "logical_request_id",
        "chapter",
        "attempt",
        "attempt_row_sha256",
        "planned_seconds",
        "actual_seconds",
        "status",
        "started_at",
        "finished_at",
        "interruption_type",
        "row_sha256",
    }
    identities: set[tuple[str, int]] = set()
    for index, row in enumerate(rows, start=1):
        if set(row) != required:
            raise ZBatchError(f"等待票第 {index} 行字段不合同")
        identity = (str(row.get("logical_request_id") or ""), row.get("attempt"))
        if (
            row.get("schema") != RETRY_WAIT_LEDGER_SCHEMA
            or not identity[0]
            or isinstance(identity[1], bool)
            or not isinstance(identity[1], int)
            or identity[1] <= 0
            or identity in identities
            or not _is_sha256(row.get("attempt_row_sha256"))
            or row.get("status") not in {"completed", "interrupted"}
            or not isinstance(row.get("planned_seconds"), (int, float))
            or isinstance(row.get("planned_seconds"), bool)
            or float(row["planned_seconds"]) < 0
            or not isinstance(row.get("actual_seconds"), (int, float))
            or isinstance(row.get("actual_seconds"), bool)
            or float(row["actual_seconds"]) < 0
            or row.get("row_sha256") != _row_sha256(row)
        ):
            raise ZBatchError(f"等待票第 {index} 行身份、状态或 SHA 无效")
        if row.get("status") == "completed" and row.get("interruption_type") is not None:
            raise ZBatchError("已完成等待票不得夹带中断类型")
        if row.get("status") == "interrupted" and not isinstance(
            row.get("interruption_type"), str
        ):
            raise ZBatchError("中断等待票必须记录中断类型")
        identities.add(identity)


def read_retry_wait_rows(attempt_ledger_path: Path) -> list[dict[str, Any]]:
    path = retry_wait_ledger_path(attempt_ledger_path)
    if not path.is_file():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    validate_retry_wait_rows(rows)
    return rows


def validate_retry_wait_sequence(
    attempt_ledger_path: Path,
    attempt_rows: Sequence[Mapping[str, Any]],
    *,
    require_all_429_completed: bool,
) -> dict[tuple[str, int], dict[str, Any]]:
    """把追加等待票绑定到已 fsync 的 429 尝试行。"""

    validate_attempt_rows(attempt_rows)
    receipts = read_retry_wait_rows(attempt_ledger_path)
    attempts = {
        (str(row.get("logical_request_id") or ""), int(row.get("attempt") or 0)): row
        for row in attempt_rows
    }
    receipt_map: dict[tuple[str, int], dict[str, Any]] = {}
    for receipt in receipts:
        identity = (
            str(receipt["logical_request_id"]),
            int(receipt["attempt"]),
        )
        attempt = attempts.get(identity)
        if (
            attempt is None
            or attempt.get("http_status") != 429
            or attempt.get("row_sha256") != receipt.get("attempt_row_sha256")
            or float(attempt.get("retry_wait_seconds") or 0.0)
            != float(receipt["planned_seconds"])
        ):
            raise ZBatchError("等待票未绑定真实429尝试行或计划等待漂移")
        receipt_map[identity] = receipt
    for identity, attempt in attempts.items():
        if attempt.get("http_status") == 429:
            receipt = receipt_map.get(identity)
            if require_all_429_completed and (
                receipt is None or receipt.get("status") != "completed"
            ):
                raise ZBatchError("完成态429尝试缺已完成追加等待票")
            if receipt is not None and receipt.get("status") == "completed" and (
                float(receipt["actual_seconds"])
                < float(receipt["planned_seconds"])
            ):
                raise ZBatchError("429实际等待短于冻结计划")
            if receipt is not None:
                if attempt.get("retry_wait_actual_seconds") is not None:
                    raise ZBatchError("429尝试行不得预填尚未发生的实际等待")
            elif attempt.get("retry_wait_actual_seconds") != 0.0:
                raise ZBatchError("未进入重试等待的429尝试必须记实际等待0秒")
        elif attempt.get("retry_wait_actual_seconds") != 0.0:
            raise ZBatchError("非429尝试不得记录重试等待")
    return receipt_map


def _append_retry_wait_receipt(
    attempt_ledger_path: Path,
    *,
    logical_request_id: str,
    chapter: int,
    attempt: int,
    attempt_row_sha256: str,
    planned_seconds: float,
    actual_seconds: float,
    status: str,
    started_at: str,
    finished_at: str,
    interruption_type: str | None,
) -> dict[str, Any]:
    row = {
        "schema": RETRY_WAIT_LEDGER_SCHEMA,
        "logical_request_id": logical_request_id,
        "chapter": chapter,
        "attempt": attempt,
        "attempt_row_sha256": attempt_row_sha256,
        "planned_seconds": planned_seconds,
        "actual_seconds": actual_seconds,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "interruption_type": interruption_type,
    }
    row["row_sha256"] = _row_sha256(row)
    validate_retry_wait_rows([row])
    path = retry_wait_ledger_path(attempt_ledger_path)
    existing = read_retry_wait_rows(attempt_ledger_path)
    if any(
        existing_row.get("logical_request_id") == logical_request_id
        and existing_row.get("attempt") == attempt
        for existing_row in existing
    ):
        raise RetryTransportHardStop(
            "retry_wait_receipt_duplicate",
            f"{logical_request_id} attempt={attempt} 已有等待票，拒绝覆盖",
        )
    _append_jsonl(path, row)
    return row


def _row_sha256(row: Mapping[str, Any]) -> str:
    preimage = {key: value for key, value in row.items() if key != "row_sha256"}
    return _sha256_json(preimage)


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    """用 O_EXCL 写不可覆盖证据件，并在返回前 fsync。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def write_checkpoint_bundle(
    root: Path,
    *,
    request_record: Mapping[str, Any],
    response_record: Mapping[str, Any],
    usage_record: Mapping[str, Any],
    attempt_rows: Sequence[Mapping[str, Any]],
    contract_version: str,
    mechanical_verdict: str,
) -> dict[str, Any]:
    """落五个不可覆盖文件；seal 的 ID 不参与自己的哈希前像。"""

    if mechanical_verdict not in {"pass", "fail", "pending"}:
        raise ZBatchError("检查点机械判词只能是 pass/fail/pending")
    if root.exists() and any(root.iterdir()):
        raise ZBatchError(f"检查点目录已有内容，拒绝覆盖：{root}")
    _validate_checkpoint_records(
        request_record=request_record,
        response_record=response_record,
        usage_record=usage_record,
        attempt_rows=attempt_rows,
        contract_version=contract_version,
        mechanical_verdict=mechanical_verdict,
    )
    files = {
        "request": (root / "01_request.json", dict(request_record)),
        "response": (root / "02_response.json", dict(response_record)),
        "usage": (root / "03_usage.json", dict(usage_record)),
        "attempts": (
            root / "04_attempts.json",
            {
                "schema": "z83-immutable-attempt-set-v1",
                "rows": [dict(row) for row in attempt_rows],
            },
        ),
    }
    references: dict[str, Any] = {}
    for label, (path, value) in files.items():
        _write_json_exclusive(path, value)
        references[label] = {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    seal_preimage = {
        "schema": "z83-immutable-checkpoint-seal-v1",
        "contract_version": contract_version,
        "mechanical_verdict": mechanical_verdict,
        "artifacts": references,
        "sealed": True,
    }
    seal = {**seal_preimage, "checkpoint_id": _sha256_json(seal_preimage)}
    _write_json_exclusive(root / "05_seal.json", seal)
    validate_checkpoint_bundle(root)
    return seal


def validate_checkpoint_bundle(root: Path) -> dict[str, Any]:
    paths = [root / f"0{index}_{name}.json" for index, name in enumerate(
        ("request", "response", "usage", "attempts", "seal"), 1
    )]
    if any(not path.is_file() for path in paths):
        raise ZBatchError("不可变检查点五件不齐")
    if {path.name for path in root.iterdir()} != {path.name for path in paths}:
        raise ZBatchError("不可变检查点目录夹入第六件或未知文件")
    request_record = json.loads(paths[0].read_text(encoding="utf-8"))
    response_record = json.loads(paths[1].read_text(encoding="utf-8"))
    usage_record = json.loads(paths[2].read_text(encoding="utf-8"))
    attempt_document = json.loads(paths[3].read_text(encoding="utf-8"))
    seal = json.loads(paths[-1].read_text(encoding="utf-8"))
    checkpoint_id = seal.pop("checkpoint_id", None)
    if not _is_sha256(checkpoint_id) or checkpoint_id != _sha256_json(seal):
        raise ZBatchError("检查点 seal 身份 SHA 不能重建")
    references = seal.get("artifacts")
    if not isinstance(references, Mapping):
        raise ZBatchError("检查点 seal 缺四件引用")
    for label, path in zip(("request", "response", "usage", "attempts"), paths[:4], strict=True):
        row = references.get(label)
        if (
            not isinstance(row, Mapping)
            or row.get("path") != path.name
            or row.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            raise ZBatchError(f"检查点 {label} 引用漂移")
    rows = attempt_document.get("rows") if isinstance(attempt_document, Mapping) else None
    if (
        not isinstance(rows, list)
        or attempt_document.get("schema") != "z83-immutable-attempt-set-v1"
    ):
        raise ZBatchError("检查点尝试件结构错误")
    _validate_checkpoint_records(
        request_record=request_record,
        response_record=response_record,
        usage_record=usage_record,
        attempt_rows=rows,
        contract_version=str(seal.get("contract_version") or ""),
        mechanical_verdict=str(seal.get("mechanical_verdict") or ""),
    )
    return {**seal, "checkpoint_id": checkpoint_id}


def _validate_checkpoint_records(
    *,
    request_record: Mapping[str, Any],
    response_record: Mapping[str, Any],
    usage_record: Mapping[str, Any],
    attempt_rows: Sequence[Mapping[str, Any]],
    contract_version: str,
    mechanical_verdict: str,
) -> None:
    """把五件套真正绑到同一次逻辑请求，拒绝空壳 PASS。"""

    request_keys = {
        "schema",
        "logical_request_id",
        "request_artifact_path",
        "request_artifact_sha256",
        "wire_body_sha256",
        "model",
        "stage",
        "contract_version",
    }
    response_keys = {
        "schema",
        "logical_request_id",
        "request_artifact_sha256",
        "http_status",
        "raw_response_path",
        "raw_response_sha256",
        "response_model",
        "finish_reason",
        "content_sha256",
        "error_code",
    }
    usage_keys = {
        "schema",
        "logical_request_id",
        "request_artifact_sha256",
        "raw_response_sha256",
        "usage",
    }
    if set(request_record) != request_keys:
        raise ZBatchError("检查点请求件字段不合同")
    if set(response_record) != response_keys:
        raise ZBatchError("检查点响应件字段不合同")
    if set(usage_record) != usage_keys:
        raise ZBatchError("检查点 usage 件字段不合同")
    logical_id = request_record.get("logical_request_id")
    request_sha = request_record.get("request_artifact_sha256")
    wire_sha = request_record.get("wire_body_sha256")
    if not isinstance(logical_id, str) or not logical_id:
        raise ZBatchError("检查点逻辑请求 ID 为空")
    if not _is_sha256(request_sha) or not _is_sha256(wire_sha):
        raise ZBatchError("检查点请求工件或线上字节 SHA 无效")
    if (
        request_record.get("schema") != "z83-retry13-checkpoint-request-v1"
        or request_record.get("contract_version") != contract_version
        or not isinstance(request_record.get("request_artifact_path"), str)
        or not request_record.get("request_artifact_path")
        or not isinstance(request_record.get("model"), str)
        or not request_record.get("model")
        or request_record.get("stage")
        not in {"targeted_retry_single_object", "semantic_route_final_retry13"}
    ):
        raise ZBatchError("检查点请求件身份或合同版本错误")
    if (
        response_record.get("schema") != "z83-retry13-checkpoint-response-v1"
        or usage_record.get("schema") != "z83-retry13-checkpoint-usage-v1"
        or response_record.get("logical_request_id") != logical_id
        or usage_record.get("logical_request_id") != logical_id
        or response_record.get("request_artifact_sha256") != request_sha
        or usage_record.get("request_artifact_sha256") != request_sha
    ):
        raise ZBatchError("检查点三件没有绑定同一逻辑请求")
    validate_attempt_rows(attempt_rows)
    if not attempt_rows:
        raise ZBatchError("检查点没有网络尝试")
    if any(
        row.get("logical_request_id") != logical_id
        or row.get("request_artifact_sha256") != request_sha
        or row.get("wire_body_sha256") != wire_sha
        for row in attempt_rows
    ):
        raise ZBatchError("检查点尝试账与请求工件或线上字节不一致")
    raw_sha = response_record.get("raw_response_sha256")
    if usage_record.get("raw_response_sha256") != raw_sha:
        raise ZBatchError("检查点 usage 与响应原字节 SHA 不一致")
    if mechanical_verdict == "pass":
        if (
            not _is_sha256(raw_sha)
            or not isinstance(response_record.get("raw_response_path"), str)
            or not response_record.get("raw_response_path")
            or response_record.get("finish_reason") != "stop"
            or response_record.get("http_status") != 200
            or not _is_sha256(response_record.get("content_sha256"))
            or not isinstance(usage_record.get("usage"), Mapping)
            or not usage_record.get("usage")
            or attempt_rows[-1].get("http_status") != 200
        ):
            raise ZBatchError("检查点 PASS 缺真实响应、stop 或 usage")
    elif mechanical_verdict == "fail":
        if response_record.get("http_status") == 200 and not _is_sha256(raw_sha):
            raise ZBatchError("HTTP 200 失败检查点仍须绑定原始响应")


def _retry_after_value(headers: Mapping[str, str]) -> str | None:
    for key, value in headers.items():
        if key.lower() == "retry-after":
            return str(value).strip()
    return None


def parse_retry_after_seconds(
    value: str | None,
    *,
    now: Callable[[], datetime] | None = None,
) -> float | None:
    """把 Retry-After 的秒数或 HTTP 日期转成等待秒数。

    无法识别的值不当成运输真值，返回 ``None`` 后使用本地预写退避。
    """

    if value is None or not value.strip():
        return None
    text = value.strip()
    try:
        seconds = float(text)
    except ValueError:
        try:
            target = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        current = (now or (lambda: datetime.now(timezone.utc)))()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        seconds = (target - current).total_seconds()
    return max(0.0, seconds)


def build_checkpoint(
    *,
    request_sha256: str,
    raw_response_sha256: str,
    usage: Mapping[str, Any],
    attempt_rows: Sequence[Mapping[str, Any]],
    contract_version: str,
    mechanical_verdict: str = "pending",
) -> dict[str, Any]:
    """生成五件套检查点，不填写语义结论。"""

    checkpoint = {
        "schema": CHECKPOINT_SCHEMA,
        "request_sha256": request_sha256,
        "raw_response_sha256": raw_response_sha256,
        "mechanical_verdict": mechanical_verdict,
        "usage_and_attempts": {
            "usage": dict(usage),
            "attempt_count": len(attempt_rows),
            "attempt_rows_sha256": _sha256_json(list(attempt_rows)),
        },
        "contract_version": contract_version,
    }
    validate_checkpoint(checkpoint)
    return checkpoint


def validate_checkpoint(checkpoint: Mapping[str, Any]) -> None:
    """验证五件套结构与机械完整性，不审语义。"""

    expected = {
        "schema",
        "request_sha256",
        "raw_response_sha256",
        "mechanical_verdict",
        "usage_and_attempts",
        "contract_version",
    }
    if set(checkpoint) != expected:
        raise ZBatchError("不可变检查点字段不完整或夹带额外字段")
    if checkpoint.get("schema") != CHECKPOINT_SCHEMA:
        raise ZBatchError("不可变检查点版本不受支持")
    if not _is_sha256(checkpoint.get("request_sha256")):
        raise ZBatchError("检查点请求 SHA 无效")
    if not _is_sha256(checkpoint.get("raw_response_sha256")):
        raise ZBatchError("检查点原始响应 SHA 无效")
    if checkpoint.get("mechanical_verdict") not in {"pending", "pass", "fail"}:
        raise ZBatchError("机械闸判词只能是 pending/pass/fail")
    contract_version = checkpoint.get("contract_version")
    if not isinstance(contract_version, str) or not contract_version.strip():
        raise ZBatchError("检查点缺少合同版本")
    usage_attempts = checkpoint.get("usage_and_attempts")
    if not isinstance(usage_attempts, Mapping):
        raise ZBatchError("检查点缺少 usage/attempt 账")
    if set(usage_attempts) != {"usage", "attempt_count", "attempt_rows_sha256"}:
        raise ZBatchError("检查点 usage/attempt 账结构不合同")
    if not isinstance(usage_attempts.get("usage"), Mapping):
        raise ZBatchError("成功检查点 usage 必须是对象")
    count = usage_attempts.get("attempt_count")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ZBatchError("检查点尝试次数必须大于 0")
    if not _is_sha256(usage_attempts.get("attempt_rows_sha256")):
        raise ZBatchError("检查点尝试账 SHA 无效")


def validate_attempt_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    """验证追加尝试账；429 的 usage 必须显式是 unknown。"""

    required = {
        "schema",
        "logical_request_id",
        "chapter",
        "attempt",
        "http_status",
        "outcome",
        "request_sha256",
        "raw_response_sha256",
        "usage",
        "retry_after_raw",
        "retry_after_seconds",
        "wire_body_sha256",
        "request_artifact_sha256",
        "error_code",
        "error_body_sha256",
        "started_at",
        "finished_at",
        "pre_request_spacing_planned_seconds",
        "pre_request_spacing_seconds",
        "retry_wait_seconds",
        "retry_wait_actual_seconds",
        "previous_attempt",
        "usage_status",
        "row_sha256",
    }
    for index, row in enumerate(rows, start=1):
        if set(row) != required:
            raise ZBatchError(f"尝试账第 {index} 行字段不合同")
        if row.get("schema") != ATTEMPT_LEDGER_SCHEMA:
            raise ZBatchError(f"尝试账第 {index} 行版本不受支持")
        if not _is_sha256(row.get("request_sha256")):
            raise ZBatchError(f"尝试账第 {index} 行请求 SHA 无效")
        status = row.get("http_status")
        if isinstance(status, bool) or not isinstance(status, int):
            raise ZBatchError(f"尝试账第 {index} 行 HTTP 状态无效")
        if status == 429 and row.get("usage") != UNKNOWN_USAGE:
            raise ZBatchError("429 usage 必须记 unknown，不得记 0")
        if row.get("row_sha256") != _row_sha256(row):
            raise ZBatchError(f"尝试账第 {index} 行 SHA 不能重建")
        for key in ("wire_body_sha256", "request_artifact_sha256"):
            value = row.get(key)
            if value is not None and not _is_sha256(value):
                raise ZBatchError(f"尝试账第 {index} 行 {key} 无效")


def _spacing_wait(
    *,
    chapter: int,
    state: RetryRunState,
    policy: RetryPolicy,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
    jitter: Callable[[], float],
) -> tuple[float, float]:
    now_value = monotonic()
    if state.last_logical_completed_monotonic is None:
        return 0.0, 0.0
    base_required = (
        policy.same_chapter_gap_seconds
        if state.last_chapter == chapter
        else policy.cross_chapter_gap_seconds
    )
    jitter_cap = 2.0 if state.last_chapter == chapter else 5.0
    required = base_required + max(0.0, float(jitter())) * jitter_cap
    elapsed = max(0.0, now_value - state.last_logical_completed_monotonic)
    planned = max(0.0, required - elapsed)
    before = monotonic()
    if planned:
        sleeper(planned)
    return planned, max(0.0, monotonic() - before)


def run_logical_request(
    *,
    logical_request_id: str,
    chapter: int,
    send_once: Callable[[int], AttemptOutcome],
    attempt_ledger_path: Path,
    contract_version: str,
    state: RetryRunState,
    policy: RetryPolicy | None = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    now: Callable[[], datetime] | None = None,
    jitter: Callable[[], float] | None = None,
) -> LogicalRequestResult:
    """按 retry13 限流合同执行一个逻辑请求。

    ``send_once`` 每次只能发同一份冻结请求。本函数把每次结果追加后
    才决定是否继续，因此崩溃不会把已发过的尝试变成“没发过”。
    """

    active_policy = policy or RetryPolicy()
    active_policy.validate()
    if not logical_request_id or not isinstance(logical_request_id, str):
        raise ZBatchError("逻辑请求 ID 不能为空")
    if isinstance(chapter, bool) or not isinstance(chapter, int) or chapter <= 0:
        raise ZBatchError("章号必须是正整数")
    if not isinstance(contract_version, str) or not contract_version.strip():
        raise ZBatchError("运输请求缺少合同版本")

    existing_rows: list[Mapping[str, Any]] = []
    if attempt_ledger_path.is_file():
        for line in attempt_ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("logical_request_id") == logical_request_id:
                existing_rows.append(row)
    if existing_rows:
        raise RetryTransportHardStop(
            "logical_request_already_attempted",
            f"{logical_request_id} 已有尝试账，拒绝再次发网或挑结果",
        )

    sleep_fn = sleeper or time.sleep
    clock = monotonic or time.monotonic
    jitter_fn = jitter or random.random
    spacing_planned, spacing_actual = _spacing_wait(
        chapter=chapter,
        state=state,
        policy=active_policy,
        sleeper=sleep_fn,
        monotonic=clock,
        jitter=jitter_fn,
    )

    rows: list[Mapping[str, Any]] = []
    expected_request_sha: str | None = None
    expected_wire_sha: str | None = None
    expected_artifact_sha: str | None = None
    max_attempts = 1 + active_policy.max_429_retries_per_request
    for attempt in range(1, max_attempts + 1):
        outcome = send_once(attempt)
        if not _is_sha256(outcome.request_sha256):
            raise RetryTransportHardStop("request_sha_invalid", "单次尝试返回的请求 SHA 无效")
        if expected_request_sha is None:
            expected_request_sha = outcome.request_sha256
        elif outcome.request_sha256 != expected_request_sha:
            raise RetryTransportHardStop("retry_request_drift", "429 重试请求与首发请求 SHA 不一致")
        if not _is_sha256(outcome.wire_body_sha256):
            raise RetryTransportHardStop("wire_body_sha_missing", "尝试账缺线上发送字节 SHA")
        if not _is_sha256(outcome.request_artifact_sha256):
            raise RetryTransportHardStop("request_artifact_sha_missing", "尝试账缺请求工件 SHA")
        if expected_wire_sha is None:
            expected_wire_sha = outcome.wire_body_sha256
            expected_artifact_sha = outcome.request_artifact_sha256
        elif (
            outcome.wire_body_sha256 != expected_wire_sha
            or outcome.request_artifact_sha256 != expected_artifact_sha
        ):
            raise RetryTransportHardStop(
                "retry_wire_or_artifact_drift",
                "429 重试的线上发送字节或请求工件与首发不一致",
            )

        retry_after_raw = _retry_after_value(outcome.headers)
        retry_after = parse_retry_after_seconds(retry_after_raw, now=now)
        status = outcome.http_status
        outcome_name = "success" if 200 <= status < 300 else "http_error"
        usage: Mapping[str, Any] | str
        if status == 429:
            usage = UNKNOWN_USAGE
        elif 200 <= status < 300:
            usage = dict(outcome.usage or {})
        else:
            usage = UNKNOWN_USAGE if outcome.usage is None else dict(outcome.usage)
        retry_wait = 0.0
        if status == 429 and attempt < max_attempts:
            base = active_policy.retry_delays_seconds[attempt - 1]
            retry_wait = max(base + max(0.0, float(jitter_fn())) * 2.0, retry_after or 0.0)
        should_retry_429 = (
            status == 429
            and attempt < max_attempts
            and not (retry_after is not None and retry_after > active_policy.max_retry_after_seconds)
            and state.total_429 + 1 < active_policy.max_429_per_run
        )
        # 429 尝试必须先追加并 fsync，再开始等待。真实等待另写追加票，
        # 这样进程在 sleep 中退出时，已收到的 429 不会从运输账消失。
        retry_wait_actual: float | None = (
            None if should_retry_429 else 0.0
        )
        row = {
            "schema": ATTEMPT_LEDGER_SCHEMA,
            "logical_request_id": logical_request_id,
            "chapter": chapter,
            "attempt": attempt,
            "http_status": status,
            "outcome": outcome_name,
            "request_sha256": outcome.request_sha256,
            "raw_response_sha256": outcome.raw_response_sha256,
            "usage": usage,
            "retry_after_raw": retry_after_raw,
            "retry_after_seconds": retry_after,
            "wire_body_sha256": outcome.wire_body_sha256,
            "request_artifact_sha256": outcome.request_artifact_sha256,
            "error_code": outcome.error_code,
            "error_body_sha256": outcome.error_body_sha256,
            "started_at": outcome.started_at,
            "finished_at": outcome.finished_at,
            "pre_request_spacing_planned_seconds": spacing_planned if attempt == 1 else 0.0,
            "pre_request_spacing_seconds": spacing_actual if attempt == 1 else 0.0,
            "retry_wait_seconds": retry_wait,
            "retry_wait_actual_seconds": retry_wait_actual,
            "previous_attempt": attempt - 1 if attempt > 1 else None,
            "usage_status": (
                "returned" if 200 <= status < 300 else "unknown"
            ),
        }
        row["row_sha256"] = _row_sha256(row)
        validate_attempt_rows([row])
        _append_jsonl(attempt_ledger_path, row)
        rows.append(row)

        if outcome.error_code == "api_key_echoed":
            raise RetryTransportHardStop(
                "api_key_echoed", "服务端响应回显 API Key，禁止任何重试"
            )

        if 200 <= status < 300:
            if not _is_sha256(outcome.raw_response_sha256):
                raise RetryTransportHardStop("raw_response_sha_invalid", "成功回包缺少有效原始响应 SHA")
            if not isinstance(outcome.usage, Mapping):
                raise RetryTransportHardStop("success_usage_missing", "成功回包缺少 usage 对象")
            checkpoint = build_checkpoint(
                request_sha256=outcome.request_sha256,
                raw_response_sha256=outcome.raw_response_sha256,
                usage=outcome.usage,
                attempt_rows=rows,
                contract_version=contract_version,
            )
            state.last_logical_completed_monotonic = clock()
            state.last_chapter = chapter
            return LogicalRequestResult(outcome, tuple(rows), checkpoint)

        if status == 429:
            state.total_429 += 1
            if retry_after is not None and retry_after > active_policy.max_retry_after_seconds:
                raise RetryTransportHardStop(
                    "retry_after_over_300",
                    f"Retry-After={retry_after:g}s 超过 {active_policy.max_retry_after_seconds:g}s，硬停",
                )
            if state.total_429 >= active_policy.max_429_per_run:
                raise RetryTransportHardStop("run_fifth_429", "整轮第 5 次 429，运输硬停")
            if attempt >= max_attempts:
                raise RetryTransportHardStop("request_third_429", "同一逻辑请求第 3 次 429，运输硬停")
            wait_started = datetime.now(timezone.utc).isoformat()
            before_retry_wait = clock()
            try:
                sleep_fn(retry_wait)
            except BaseException as exc:
                wait_finished = datetime.now(timezone.utc).isoformat()
                _append_retry_wait_receipt(
                    attempt_ledger_path,
                    logical_request_id=logical_request_id,
                    chapter=chapter,
                    attempt=attempt,
                    attempt_row_sha256=str(row["row_sha256"]),
                    planned_seconds=retry_wait,
                    actual_seconds=max(0.0, clock() - before_retry_wait),
                    status="interrupted",
                    started_at=wait_started,
                    finished_at=wait_finished,
                    interruption_type=type(exc).__name__,
                )
                raise
            _append_retry_wait_receipt(
                attempt_ledger_path,
                logical_request_id=logical_request_id,
                chapter=chapter,
                attempt=attempt,
                attempt_row_sha256=str(row["row_sha256"]),
                planned_seconds=retry_wait,
                actual_seconds=max(0.0, clock() - before_retry_wait),
                status="completed",
                started_at=wait_started,
                finished_at=datetime.now(timezone.utc).isoformat(),
                interruption_type=None,
            )
            continue

        state.last_logical_completed_monotonic = clock()
        state.last_chapter = chapter
        if isinstance(outcome.error_code, str) and outcome.error_code.startswith(
            "transport_"
        ):
            raise RetryTransportHardStop(
                "transport_error_no_retry", "网络异常不自动重试"
            )
        if status in {401, 403}:
            raise RetryTransportHardStop(f"http_{status}_no_retry", f"HTTP {status} 不自动重试")
        if 500 <= status < 600:
            raise RetryTransportHardStop("http_5xx_no_retry", f"HTTP {status} 不自动重试")
        raise RetryTransportHardStop("http_nonretryable", f"HTTP {status} 不在允许重试范围")

    raise RetryTransportHardStop("unreachable_transport_state", "运输状态不可达")
