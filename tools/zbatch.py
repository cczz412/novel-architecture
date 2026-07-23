#!/usr/bin/env python3
"""Z 批本地测试运行器。

只依赖 Python 标准库。它负责：材料预演、SenseNova 调用、证据锚核验、
事件级压薄、折叠视图、四型答题、银标对撞、报告和打包。
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

from zbatch_modules import (
    anchor_kit as modular_anchor_kit,
    api_transport as modular_api_transport,
    candidate_envelope as modular_candidate_envelope,
    classify_rules as modular_classify_rules,
    downstream_validate as modular_downstream_validate,
    evidence_catalog as modular_evidence_catalog,
    neutral_extract as modular_neutral_extract,
    prompt_render_pin as modular_prompt_render_pin,
    stage_sampling as modular_stage_sampling,
    verbatim_restatement as modular_verbatim_restatement,
)
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
REPORTS_DIR = ROOT / "reports"
OUTBOX_DIR = ROOT / "outbox"
INTAKE_DIR = ROOT / "intake"
ACTIVE_STAGE_CONTRACT_PATH = ROOT / "config/contracts/sensenova_stage_sampling_v1.json"
ACTIVE_STAGE_PROFILE = "d_mod_cutover_v1"

SENSENOVA_PROVIDER = "sensenova"
SENSENOVA_BASE_URL = "https://token.sensenova.cn/v1"
SENSENOVA_ENDPOINT = "/chat/completions"
ALLOWED_TEXT_MODELS = {"deepseek-v4-flash"}

TYPE_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "A": ("story_line", "delta", "direct_cause", "future_use"),
    "B": ("trigger_condition", "trigger_action"),
    "C": ("reader_expectation", "payoff_test"),
    "D": ("condition", "consequence", "scope_exception"),
}
ALLOWED_STATUS = {"开", "收", "废"}
ALLOWED_ASSERTION = {"明", "推", "存疑"}
RECORD_ID_PATTERN = re.compile(r"^[ABCD]-(?:C\d{4}-\d{2}|\d{4})$")
ALLOWED_DIFF_LABELS = {"我对它错", "它对我错", "等价", "待裁"}
QUESTION_TYPES = {"回指", "转线", "伸缩", "梯度"}
ANSWER_STATUSES = {"answered", "not_applicable"}
NOT_APPLICABLE_QUESTION_TYPES = {"转线", "伸缩"}
REQUIRED_QUESTION_SPECS: dict[str, dict[str, Any]] = {
    "backtrace-ch0010": {"question_type": "回指", "target_chapter": 10},
    "backtrace-ch0020": {"question_type": "回指", "target_chapter": 20},
    "cross-line": {"question_type": "转线", "target_chapter": None},
    "compression": {"question_type": "伸缩", "target_chapter": None},
    "gradient": {"question_type": "梯度", "target_chapter": "sample_end"},
}
GRADIENT_BUCKETS: dict[str, tuple[int, int | None]] = {
    "0-1": (0, 1),
    "2-5": (2, 5),
    "6-20": (6, 20),
    "21-50": (21, 50),
    "50+": (51, None),
}
COMPARABILITY_VALUES = {
    "same_question",
    "different_question",
    "different_scope",
    "missing_ours",
    "missing_silver",
    "insufficient_evidence",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def root_path(value: str | Path) -> Path:
    """把仓库相对路径变成绝对路径，并拒绝越出仓库。"""
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ZBatchError(f"路径越出小说架构仓库：{resolved}") from exc
    return resolved


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ZBatchError(f"JSON 读取失败：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise ZBatchError(f"JSON 顶层必须是对象：{path}")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_fingerprint(path: Path) -> dict[str, Any]:
    """目录指纹包含相对文件名和逐文件 SHA，忽略 macOS 杂项。"""
    if path.is_file():
        return {
            "kind": "file",
            "files": 1,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    if not path.is_dir():
        raise ZBatchError(f"不存在：{path}")
    rows: list[tuple[str, str, int]] = []
    for file in sorted(p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store"):
        rows.append((str(file.relative_to(path)), sha256_file(file), file.stat().st_size))
    payload = "\n".join(f"{name}\t{digest}\t{size}" for name, digest, size in rows)
    return {
        "kind": "directory",
        "files": len(rows),
        "bytes": sum(size for _, _, size in rows),
        "sha256": sha256_bytes(payload.encode("utf-8")),
    }


def parse_json_content(content: str) -> dict[str, Any]:
    """活路径统一走候选外壳模块；旧函数名只留兼容调用面。"""
    return modular_candidate_envelope.parse_json_content(content)


def chapter_number_from_name(name: str) -> int | None:
    match = re.match(r"^(\d{4})_", name)
    return int(match.group(1)) if match else None


def load_chapters(book_dir: Path, start: int, end: int) -> dict[int, dict[str, Any]]:
    chapter_dir = book_dir / "chapters"
    if not chapter_dir.is_dir():
        raise ZBatchError(f"缺章节目录：{chapter_dir}")
    chapters: dict[int, dict[str, Any]] = {}
    for file in sorted(chapter_dir.glob("*.txt")):
        number = chapter_number_from_name(file.name)
        if number is None or number < start or number > end:
            continue
        if number in chapters:
            raise ZBatchError(f"章节号重复：{number}：{chapters[number]['path']} / {file}")
        text = file.read_text(encoding="utf-8")
        chapters[number] = {
            "number": number,
            "path": file,
            "filename": file.name,
            "text": text,
            "sha256": sha256_bytes(text.encode("utf-8")),
            "chars": len(text),
        }
    expected = list(range(start, end + 1))
    missing = [number for number in expected if number not in chapters]
    if missing:
        preview = ", ".join(map(str, missing[:20]))
        raise ZBatchError(f"章节不完整，缺 {len(missing)} 章：{preview}")
    return chapters


def load_configs(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    batch = read_json(config_path)
    provider_path = root_path(batch.get("provider_config", ""))
    provider = read_json(provider_path)
    batch["_config_path"] = rel(config_path)
    provider["_config_path"] = rel(provider_path)
    return batch, provider


def _verify_receipt_hashes(receipt: dict[str, Any]) -> None:
    for path_key, sha_key in [
        ("output_path", "output_sha256"),
        ("request_path", "request_sha256"),
        ("raw_response_path", "raw_response_sha256"),
        ("response_meta_path", "response_meta_sha256"),
    ]:
        path = root_path(str(receipt.get(path_key) or ""))
        if not path.is_file() or sha256_file(path) != receipt.get(sha_key):
            raise ZBatchError(f"导入来源工件漂移：{path}")


def verify_verified_run_import(source_run_id: str, batch: dict[str, Any]) -> dict[str, Any]:
    """核验一个失败/完成运行里已经正式完成的 extract+verify 阶段。"""
    source_dir = RUNS_DIR / source_run_id
    if not source_dir.is_dir():
        raise ZBatchError(f"找不到待复用运行：{source_run_id}")
    run_manifest = read_json(source_dir / "run_manifest.json")
    completed = set(run_manifest.get("stages_completed") or [])
    if not {"extract", "verify"}.issubset(completed):
        raise ZBatchError("待复用运行没有完成 extract+verify")
    snapshot = read_json(source_dir / "config_snapshot.json")
    source_batch = snapshot.get("batch") if isinstance(snapshot.get("batch"), dict) else {}
    for key in ("item_id", "book_name", "chapter_start", "chapter_end", "expected_chapters"):
        if source_batch.get(key) != batch.get(key):
            raise ZBatchError(f"待复用运行与当前批次不一致：{key}")
    if source_batch.get("book_dir") != batch.get("book_dir"):
        raise ZBatchError("待复用运行正文路径与当前批次不一致")

    parsed_dir = source_dir / "01_extract" / "parsed"
    outputs = sorted(parsed_dir.glob("ch[0-9][0-9][0-9][0-9].json"))
    expected = int(batch.get("expected_chapters", 0))
    if len(outputs) != expected:
        raise ZBatchError(f"待复用运行提取章数不完整：{len(outputs)}/{expected}")
    receipt_hashes: list[str] = []
    for output in outputs:
        receipt_file = receipt_path(output)
        if not receipt_file.is_file():
            raise ZBatchError(f"待复用提取工件缺回执：{output}")
        receipt = read_json(receipt_file)
        if receipt.get("stage") != "extract":
            raise ZBatchError(f"待复用回执阶段错误：{receipt_file}")
        if receipt.get("runner_sha256") != source_batch.get("runner_sha256"):
            raise ZBatchError(f"待复用回执 runner SHA 与原批次不一致：{receipt_file}")
        _verify_receipt_hashes(receipt)
        receipt_hashes.append(sha256_file(receipt_file))

    valid_path = source_dir / "02_verify" / "valid_records.json"
    metrics_path = source_dir / "02_verify" / "metrics.json"
    if not valid_path.is_file() or not metrics_path.is_file():
        raise ZBatchError("待复用运行缺核锚结果")
    valid_data = read_json(valid_path)
    metrics = read_json(metrics_path)
    valid_records = valid_data.get("records")
    if not isinstance(valid_records, list) or len(valid_records) != metrics.get("valid_total"):
        raise ZBatchError("待复用过锚条数与指标不一致")
    provenance = verify_provenance_snapshot(source_dir)
    return {
        "source_run_id": source_run_id,
        "source_status": run_manifest.get("status"),
        "completed_stages": sorted(completed),
        "chapters": expected,
        "valid_records": len(valid_records),
        "valid_records_sha256": sha256_file(valid_path),
        "metrics_sha256": sha256_file(metrics_path),
        "run_manifest_sha256": sha256_file(source_dir / "run_manifest.json"),
        "receipt_set_sha256": sha256_bytes("\n".join(receipt_hashes).encode("utf-8")),
        "source_provenance": provenance,
    }


def verify_thin_run_import(source_run_id: str, batch: dict[str, Any]) -> dict[str, Any]:
    """核验另一次运行里已经完成且可复用的事件级压薄阶段。"""
    source_dir = RUNS_DIR / source_run_id
    if not source_dir.is_dir():
        raise ZBatchError(f"找不到待复用压薄运行：{source_run_id}")
    run_manifest = read_json(source_dir / "run_manifest.json")
    completed = set(run_manifest.get("stages_completed") or [])
    if "thin" not in completed:
        raise ZBatchError("待复用运行没有完成 thin")
    snapshot = read_json(source_dir / "config_snapshot.json")
    source_batch = snapshot.get("batch") if isinstance(snapshot.get("batch"), dict) else {}
    for key in ("item_id", "book_name", "book_dir", "chapter_start", "chapter_end", "expected_chapters"):
        if source_batch.get(key) != batch.get(key):
            raise ZBatchError(f"待复用压薄运行与当前批次不一致：{key}")
    source_prompt = (source_batch.get("prompts") or {}).get("thin")
    current_prompt = (batch.get("prompts") or {}).get("thin")
    source_pin = (source_batch.get("pinned_sha256") or {}).get(source_prompt)
    current_pin = (batch.get("pinned_sha256") or {}).get(current_prompt)
    if not source_prompt or source_prompt != current_prompt or source_pin != current_pin:
        raise ZBatchError("待复用压薄 Prompt 或固定 SHA 与当前批次不一致")
    if current_pin != sha256_file(root_path(current_prompt)):
        raise ZBatchError("当前压薄 Prompt 已漂移")

    source_preflight = read_json(source_dir / "preflight.json")
    current_book_dir = root_path(batch["book_dir"])
    current_fingerprint = tree_fingerprint(current_book_dir)
    if source_preflight.get("input_fingerprint") != current_fingerprint:
        raise ZBatchError("待复用压薄运行的输入材料指纹不同")

    thin_dir = source_dir / "03_thin"
    ledger_path = thin_dir / "main_ledger.json"
    metrics_path = thin_dir / "metrics.json"
    if not ledger_path.is_file() or not metrics_path.is_file():
        raise ZBatchError("待复用运行缺压薄主账或指标")
    ledger = read_json(ledger_path)
    metrics = read_json(metrics_path)
    records = ledger.get("records")
    if not isinstance(records, list) or not records or len(records) != metrics.get("thin_records"):
        raise ZBatchError("待复用压薄主账条数与指标不一致")

    receipts = sorted(thin_dir.rglob("*.receipt.json"))
    if not receipts:
        raise ZBatchError("待复用压薄阶段缺 API 回执")
    receipt_hashes: list[str] = []
    for receipt_path_value in receipts:
        receipt = read_json(receipt_path_value)
        if receipt.get("stage") != "thin":
            raise ZBatchError(f"待复用压薄回执阶段错误：{receipt_path_value}")
        if receipt.get("runner_sha256") != source_batch.get("runner_sha256"):
            raise ZBatchError(f"待复用压薄回执 runner SHA 与原批次不一致：{receipt_path_value}")
        _verify_receipt_hashes(receipt)
        receipt_hashes.append(sha256_file(receipt_path_value))
    provenance = verify_provenance_snapshot(source_dir)
    return {
        "source_run_id": source_run_id,
        "source_status": run_manifest.get("status"),
        "completed_stages": sorted(completed),
        "thin_records": len(records),
        "thin_tree_fingerprint": tree_fingerprint(thin_dir),
        "run_manifest_sha256": sha256_file(source_dir / "run_manifest.json"),
        "receipt_set_sha256": sha256_bytes("\n".join(receipt_hashes).encode("utf-8")),
        "input_fingerprint": current_fingerprint,
        "source_provenance": provenance,
    }


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def load_active_stage_bundle(batch: dict[str, Any]) -> modular_stage_sampling.StageContractBundle:
    """只允许 D-MOD-002 生效档案；不提供运行时新旧双轨开关。"""
    configured_path = root_path(
        batch.get("stage_sampling_contract", rel(ACTIVE_STAGE_CONTRACT_PATH))
    )
    configured_profile = str(batch.get("stage_sampling_profile") or ACTIVE_STAGE_PROFILE)
    if configured_path != ACTIVE_STAGE_CONTRACT_PATH:
        raise ZBatchError("运行器只允许 D-MOD-002 阶段合同路径")
    if configured_profile != ACTIVE_STAGE_PROFILE:
        raise ZBatchError("运行器只允许 D-MOD-002 接线生效档案")
    return modular_stage_sampling.load_contract_bundle(
        ACTIVE_STAGE_CONTRACT_PATH,
        profile=ACTIVE_STAGE_PROFILE,
    )


def preflight(config_path: Path, *, require_key: bool = False) -> dict[str, Any]:
    batch, provider = load_configs(config_path)
    checks: list[dict[str, Any]] = []

    provider_path = root_path(batch.get("provider_config", ""))
    provider_sha = sha256_file(provider_path) if provider_path.is_file() else None
    add_check(
        checks,
        "provider_config_sha256",
        provider_sha == batch.get("provider_config_sha256"),
        provider_sha,
    )
    runner_sha = sha256_file(Path(__file__).resolve())
    add_check(
        checks,
        "runner_sha256",
        runner_sha == batch.get("runner_sha256"),
        runner_sha,
    )

    add_check(checks, "provider", provider.get("provider") == SENSENOVA_PROVIDER, provider.get("provider"))
    add_check(checks, "base_url", provider.get("base_url") == SENSENOVA_BASE_URL, provider.get("base_url"))
    add_check(checks, "endpoint", provider.get("endpoint") == SENSENOVA_ENDPOINT, provider.get("endpoint"))
    model = provider.get("model")
    allowed = set(provider.get("allowed_models") or [])
    add_check(
        checks,
        "model_allowlist",
        model in ALLOWED_TEXT_MODELS and allowed == ALLOWED_TEXT_MODELS,
        {"model": model, "allowed_models": sorted(allowed)},
    )

    try:
        stage_bundle = load_active_stage_bundle(batch)
        route = modular_api_transport.TransportRoute.from_mapping(stage_bundle.route)
        provider_matches_route = all(
            (
                provider.get("provider") == route.provider,
                provider.get("base_url") == route.base_url,
                provider.get("endpoint") == route.endpoint,
                provider.get("model") == route.model,
                provider.get("api_key_env") == route.api_key_env,
                provider.get("timeout_seconds") == route.timeout_seconds,
                provider.get("network_attempts") == route.network_attempts,
            )
        )
        forbidden_provider_sampling = sorted(
            key
            for key in ("temperature", "max_tokens", "max_tokens_by_stage", "n", "reasoning_effort", "response_format")
            if key in provider
        )
        add_check(checks, "stage_sampling_profile", True, stage_bundle.profile)
        add_check(checks, "provider_matches_active_route", provider_matches_route, route.model)
        add_check(
            checks,
            "provider_has_no_global_sampling",
            not forbidden_provider_sampling,
            forbidden_provider_sampling or "none",
        )
        add_check(
            checks,
            "verbatim_candidate_locked",
            "verbatim_restatement" not in stage_bundle.stages
            and stage_bundle.candidates["verbatim_restatement"].status == "candidate_unverified",
            stage_bundle.candidates["verbatim_restatement"].status,
        )
    except ZBatchError as exc:
        stage_bundle = None
        add_check(checks, "stage_sampling_profile", False, str(exc))

    configured_stages = list(batch.get("stages") or [])
    add_check(
        checks,
        "no_legacy_runtime_switch",
        not any(key in batch for key in ("use_legacy", "legacy_mode", "pipeline_mode")),
        "fixed_modular_path",
    )
    add_check(
        checks,
        "verbatim_not_auto_started",
        "verbatim_restatement" not in configured_stages,
        configured_stages,
    )
    if "classify" in configured_stages:
        classification_contract_value = str(batch.get("classification_contract") or "")
        classification_decisions_value = str(batch.get("classification_decisions") or "")
        add_check(
            checks,
            "classification_contract_configured",
            bool(classification_contract_value),
            classification_contract_value or "missing",
        )
        add_check(
            checks,
            "classification_decisions_configured",
            bool(classification_decisions_value),
            classification_decisions_value or "missing",
        )
        add_check(
            checks,
            "classification_regression_gate_required",
            batch.get("classification_regression_gate") is True,
            batch.get("classification_regression_gate"),
        )
        for check_name, value, expected in (
            (
                "classification_contract_sha256",
                classification_contract_value,
                batch.get("classification_contract_sha256"),
            ),
            (
                "classification_decisions_sha256",
                classification_decisions_value,
                batch.get("classification_decisions_sha256"),
            ),
        ):
            try:
                path = root_path(value)
                actual = sha256_file(path) if path.is_file() else None
                add_check(checks, check_name, bool(expected) and actual == expected, actual or "missing")
            except ZBatchError as exc:
                add_check(checks, check_name, False, str(exc))

    key_env = str(provider.get("api_key_env") or "")
    key_present = bool(key_env and os.environ.get(key_env))
    add_check(
        checks,
        "api_key_environment",
        key_present if require_key else True,
        "present" if key_present else "not_loaded_for_preflight",
    )

    book_dir = root_path(batch.get("book_dir", ""))
    start = int(batch.get("chapter_start", 0))
    end = int(batch.get("chapter_end", 0))
    try:
        chapters = load_chapters(book_dir, start, end)
        add_check(checks, "chapters", len(chapters) == int(batch.get("expected_chapters", 0)), {
            "found": len(chapters),
            "expected": batch.get("expected_chapters"),
            "range": [start, end],
        })
    except ZBatchError as exc:
        chapters = {}
        add_check(checks, "chapters", False, str(exc))

    intake_value = str(batch.get("intake_manifest") or "").strip()
    if intake_value:
        intake_path = root_path(intake_value)
        if intake_path.is_file():
            actual_manifest_sha = sha256_file(intake_path)
            expected_manifest_sha = batch.get("intake_manifest_sha256")
            add_check(
                checks,
                "intake_manifest_sha256",
                actual_manifest_sha == expected_manifest_sha,
                actual_manifest_sha,
            )
            intake = read_json(intake_path)
            registered_value = str(intake.get("registered_path") or "")
            registered_path = root_path(registered_value) if registered_value else ROOT / "__missing__"
            add_check(
                checks,
                "intake_manifest_identity",
                intake.get("item") == batch.get("item_id") and intake.get("kind") == "material",
                {"item": intake.get("item"), "kind": intake.get("kind")},
            )
            add_check(
                checks,
                "intake_registered_path",
                registered_path == book_dir,
                {"registered_path": rel(registered_path), "book_dir": rel(book_dir)},
            )
            actual_input_fingerprint = tree_fingerprint(book_dir) if book_dir.is_dir() else None
            add_check(
                checks,
                "intake_fingerprint",
                actual_input_fingerprint == intake.get("fingerprint"),
                actual_input_fingerprint,
            )
        else:
            add_check(checks, "intake_manifest", False, rel(intake_path))
    else:
        add_check(checks, "intake_manifest", False, "missing")

    source_zip = root_path(batch.get("source_zip", ""))
    if source_zip.is_file():
        actual_zip_sha = sha256_file(source_zip)
        add_check(checks, "source_zip_sha256", actual_zip_sha == batch.get("source_zip_sha256"), actual_zip_sha)
        try:
            with zipfile.ZipFile(source_zip) as archive:
                bad = archive.testzip()
            add_check(checks, "source_zip_integrity", bad is None, bad or "ok")
        except zipfile.BadZipFile as exc:
            add_check(checks, "source_zip_integrity", False, str(exc))
    else:
        add_check(checks, "source_zip", False, rel(source_zip))

    pinned: list[dict[str, Any]] = []
    expected_pins = batch.get("pinned_sha256") if isinstance(batch.get("pinned_sha256"), dict) else {}
    for value in list(batch.get("spec_snapshots") or []) + list((batch.get("prompts") or {}).values()):
        path = root_path(value)
        if path.is_file():
            actual_sha = sha256_file(path)
            expected_sha = expected_pins.get(value)
            pinned.append({
                "path": rel(path),
                "sha256": actual_sha,
                "expected_sha256": expected_sha,
                "matches_pin": actual_sha == expected_sha,
                "bytes": path.stat().st_size,
            })
            if actual_sha != expected_sha:
                add_check(checks, f"pinned_sha256:{value}", False, {"expected": expected_sha, "actual": actual_sha})
        else:
            add_check(checks, f"pinned_file:{value}", False, "missing")
    add_check(checks, "pinned_files", len(pinned) == len(batch.get("spec_snapshots") or []) + len(batch.get("prompts") or {}), pinned)

    silver_answer = root_path(batch.get("silver_answer", ""))
    silver_manifest = root_path(batch.get("silver_manifest", ""))
    add_check(checks, "silver_answer", silver_answer.is_file(), rel(silver_answer))
    add_check(checks, "silver_manifest", silver_manifest.is_file(), rel(silver_manifest))
    if silver_answer.is_file():
        actual = sha256_file(silver_answer)
        add_check(checks, "silver_answer_sha256", actual == batch.get("silver_answer_sha256"), actual)
    if silver_manifest.is_file():
        actual = sha256_file(silver_manifest)
        add_check(checks, "silver_manifest_sha256", actual == batch.get("silver_manifest_sha256"), actual)
    add_check(checks, "rights_statement", bool(str(batch.get("rights") or "").strip()), batch.get("rights"))
    add_check(checks, "max_calls", int(batch.get("max_calls", 0)) > 0, batch.get("max_calls"))
    import_run = str(batch.get("import_verified_run") or "").strip()
    if import_run:
        try:
            import_check = verify_verified_run_import(import_run, batch)
            add_check(checks, "import_verified_run", True, import_check)
        except ZBatchError as exc:
            add_check(checks, "import_verified_run", False, str(exc))
    import_thin_run = str(batch.get("import_thin_run") or "").strip()
    if import_thin_run:
        try:
            import_thin_check = verify_thin_run_import(import_thin_run, batch)
            add_check(checks, "import_thin_run", True, import_thin_check)
        except ZBatchError as exc:
            add_check(checks, "import_thin_run", False, str(exc))

    result = {
        "preflight": "pass" if all(item["ok"] for item in checks) else "fail",
        "created_at": now_iso(),
        "config": rel(config_path),
        "run_id": batch.get("run_id"),
        "model_calls": 0,
        "checks": checks,
        "pinned_files": pinned,
        "input_fingerprint": tree_fingerprint(book_dir) if book_dir.is_dir() else None,
    }
    return result


def prompt_text(batch: dict[str, Any], stage: str) -> str:
    value = (batch.get("prompts") or {}).get(stage)
    if not value:
        raise ZBatchError(f"批次配置缺 Prompt：{stage}")
    expected = (batch.get("pinned_sha256") or {}).get(value)
    if not isinstance(expected, str) or not expected:
        raise ZBatchError(f"批次配置缺 Prompt SHA：{stage}")
    return modular_prompt_render_pin.load_pinned_text(root_path(value), expected)


def replace_prompt(template: str, values: dict[str, str]) -> str:
    return modular_prompt_render_pin.render_prompt(template, values)


def response_content(data: dict[str, Any]) -> tuple[str, str | None]:
    return modular_api_transport.response_content(data)


class RunContext:
    def __init__(self, batch: dict[str, Any], provider: dict[str, Any], run_dir: Path):
        self.batch = batch
        self.provider = provider
        self.run_dir = run_dir
        self.max_calls = int(batch.get("max_calls", 0))
        self.stage_bundle = load_active_stage_bundle(batch)
        route = modular_api_transport.TransportRoute.from_mapping(self.stage_bundle.route)
        if (
            provider.get("provider") != route.provider
            or provider.get("base_url") != route.base_url
            or provider.get("endpoint") != route.endpoint
            or provider.get("model") != route.model
            or provider.get("api_key_env") != route.api_key_env
            or provider.get("timeout_seconds") != route.timeout_seconds
            or provider.get("network_attempts") != route.network_attempts
            or set(provider.get("allowed_models") or []) != ALLOWED_TEXT_MODELS
        ):
            raise ZBatchError("provider 与 D-MOD-002 活跃运输合同不一致")
        self.transport = modular_api_transport.ApiTransport.from_bundle(
            self.stage_bundle,
            run_dir=run_dir,
            max_calls=self.max_calls,
        )
        self.calls_made = self.transport.calls_made

    def call_json(self, *, stage: str, case_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            result = self.transport.call(stage=stage, case_id=case_id, messages=messages)
        finally:
            self.calls_made = self.transport.calls_made
        return modular_candidate_envelope.parse_json_content(result.content)


def api_artifact_paths(ctx: RunContext, stage: str, case_id: str) -> tuple[Path, Path, Path]:
    return (
        ctx.run_dir / "requests" / stage / f"{case_id}_request.json",
        ctx.run_dir / "responses" / stage / f"{case_id}_raw.json",
        ctx.run_dir / "responses" / stage / f"{case_id}_meta.json",
    )


def receipt_path(output_path: Path) -> Path:
    return output_path.with_suffix(output_path.suffix + ".receipt.json")


def write_api_artifact(
    ctx: RunContext,
    *,
    stage: str,
    case_id: str,
    output_path: Path,
    data: dict[str, Any],
    input_sha256: str,
    prompt_sha256: str,
) -> None:
    """解析结果和外置回执一起落盘，续跑时逐份复核。"""
    write_json(output_path, data)
    request_path, raw_path, meta_path = api_artifact_paths(ctx, stage, case_id)
    for path in (request_path, raw_path, meta_path):
        if not path.is_file():
            raise ZBatchError(f"API 工件不完整，拒绝写完成回执：{path}")
    provider_path = root_path(ctx.provider["_config_path"])
    receipt = {
        "stage": stage,
        "case_id": case_id,
        "created_at": now_iso(),
        "output_path": rel(output_path),
        "output_sha256": sha256_file(output_path),
        "input_sha256": input_sha256,
        "prompt_sha256": prompt_sha256,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "provider_config_sha256": sha256_file(provider_path),
        "request_path": rel(request_path),
        "request_sha256": sha256_file(request_path),
        "raw_response_path": rel(raw_path),
        "raw_response_sha256": sha256_file(raw_path),
        "response_meta_path": rel(meta_path),
        "response_meta_sha256": sha256_file(meta_path),
    }
    write_json(receipt_path(output_path), receipt)


def resume_api_artifact(
    ctx: RunContext,
    *,
    stage: str,
    case_id: str,
    output_path: Path,
    input_sha256: str,
    prompt_sha256: str,
) -> dict[str, Any] | None:
    """只有结果、请求、原始响应、元数据和依赖哈希全对，才允许跳过调用。"""
    receipt_file = receipt_path(output_path)
    request_path, raw_path, meta_path = api_artifact_paths(ctx, stage, case_id)
    if not output_path.exists():
        if raw_path.exists():
            raise ZBatchError(
                f"{stage}/{case_id} 已有原始 API 响应但没有完成回执；"
                "这通常是 JSON/结构失败，按纪律拒绝二次生成"
            )
        return None
    if not receipt_file.is_file():
        raise ZBatchError(f"续跑工件缺外置回执，拒绝跳过或覆盖：{output_path}")
    receipt = read_json(receipt_file)
    expected = {
        "stage": stage,
        "case_id": case_id,
        "output_path": rel(output_path),
        "input_sha256": input_sha256,
        "prompt_sha256": prompt_sha256,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "provider_config_sha256": sha256_file(root_path(ctx.provider["_config_path"])),
        "request_path": rel(request_path),
        "raw_response_path": rel(raw_path),
        "response_meta_path": rel(meta_path),
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ZBatchError(f"续跑回执漂移：{stage}/{case_id} 字段 {key}")
    for path, key in [
        (output_path, "output_sha256"),
        (request_path, "request_sha256"),
        (raw_path, "raw_response_sha256"),
        (meta_path, "response_meta_sha256"),
    ]:
        if not path.is_file() or sha256_file(path) != receipt.get(key):
            raise ZBatchError(f"续跑工件字节漂移：{path}")
    return read_json(output_path)


def nonspace_chars(value: str) -> int:
    """兼容函数名；确定性实现由 evidence_catalog 模块单独维护。"""
    return modular_evidence_catalog.nonspace_chars(value)


def _quote_windows(text: str, *, width: int = 22, step: int = 16) -> list[str]:
    """兼容函数名；确定性实现由 evidence_catalog 模块单独维护。"""
    return modular_evidence_catalog.quote_windows(text, width=width, step=step)


def build_evidence_catalog(chapter: int, text: str) -> list[dict[str, Any]]:
    """兼容函数名；证据目录实现由 evidence_catalog 模块单独维护。"""
    return modular_evidence_catalog.build_evidence_catalog(chapter, text)


def evidence_catalog_coverage(text: str, catalog: list[dict[str, Any]]) -> float:
    """兼容函数名；证据覆盖实现由 evidence_catalog 模块单独维护。"""
    return modular_evidence_catalog.evidence_catalog_coverage(text, catalog)


def materialize_anchor_ids(
    data: dict[str, Any],
    catalog: list[dict[str, Any]],
    chapter: int,
) -> dict[str, Any]:
    """兼容函数名；冻结锚展开由 anchor_kit 模块单独维护。"""
    return modular_anchor_kit.materialize_anchor_ids(data, catalog, chapter)


def materialize_anchors_from_sources(
    items: Any,
    source_records: dict[str, dict[str, Any]],
    *,
    source_field: str,
) -> list[Any]:
    """兼容函数名；来源锚解引用由 anchor_kit 模块单独维护。"""
    return modular_anchor_kit.materialize_anchors_from_sources(
        items,
        source_records,
        source_field=source_field,
    )


def validate_anchors(
    anchors: Any,
    chapters: dict[int, dict[str, Any]],
    *,
    expected_chapter: int | None = None,
    evidence_catalog: dict[str, str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """兼容函数名；核锚合同由 anchor_kit 模块单独维护。"""
    return modular_anchor_kit.validate_anchors(
        anchors,
        chapters,
        expected_chapter=expected_chapter,
        evidence_catalog=evidence_catalog,
    )


def validate_record(
    record: Any,
    chapters: dict[int, dict[str, Any]],
    *,
    expected_chapter: int | None = None,
    require_sources: bool = False,
    allowed_source_ids: set[str] | None = None,
    evidence_catalog: dict[str, str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """兼容函数名；记录验收由 anchor_kit 模块单独维护。"""
    return modular_anchor_kit.validate_record(
        record,
        chapters,
        expected_chapter=expected_chapter,
        require_sources=require_sources,
        allowed_source_ids=allowed_source_ids,
        evidence_catalog=evidence_catalog,
    )


def validate_candidate_coverage_audit(data: dict[str, Any]) -> list[str]:
    """兼容函数名；候选清点验收由 candidate_envelope 模块单独维护。"""
    return modular_candidate_envelope.validate_candidate_coverage_audit(data)


def validate_candidate_envelope(data: dict[str, Any], chapter: int) -> list[str]:
    """兼容函数名；候选外壳验收由 candidate_envelope 模块单独维护。"""
    return modular_candidate_envelope.validate_candidate_envelope(data, chapter)


def cross_type_anchor_overlap(records: list[dict[str, Any]]) -> dict[str, Any]:
    """兼容函数名；跨类型共享锚诊断由 candidate_envelope 模块单独维护。"""
    return modular_candidate_envelope.cross_type_anchor_overlap(records)


def legacy_stage_extract(
    ctx: RunContext,
    chapters: dict[int, dict[str, Any]],
    *,
    resume: bool,
) -> dict[str, Any]:
    """兼容函数名；旧候选直出实现已退役，固定转发活跃中性提取路径。"""
    return stage_extract(ctx, chapters, resume=resume)


def _neutral_prompt_spec(batch: dict[str, Any]) -> tuple[Path, str]:
    value = str((batch.get("prompts") or {}).get("neutral_extract") or "")
    if not value:
        raise ZBatchError("批次配置缺中性事件 Prompt：neutral_extract")
    expected = str((batch.get("pinned_sha256") or {}).get(value) or "")
    if not expected:
        raise ZBatchError("批次配置缺中性事件 Prompt SHA")
    return root_path(value), expected


def _raw_neutral_event_document(data: dict[str, Any]) -> dict[str, Any]:
    """把已展开短引的事件还原成模型合同形状，供续跑与真实工件重放。"""
    return {
        "schema_version": data.get("schema_version"),
        "chapter": data.get("chapter"),
        "events": [
            {
                "event_id": event.get("event_id"),
                "event": event.get("event"),
                "anchors": [
                    {"anchor_id": anchor.get("anchor_id")}
                    for anchor in event.get("anchors") or []
                    if isinstance(anchor, dict)
                ],
            }
            for event in data.get("events") or []
            if isinstance(event, dict)
        ],
    }


def stage_extract(ctx: RunContext, chapters: dict[int, dict[str, Any]], *, resume: bool) -> dict[str, Any]:
    """活跃模块路径：弱模型只交中性事件，程序生成清点账并展开冻结短引。"""
    prompt_path, prompt_pin = _neutral_prompt_spec(ctx.batch)
    events_dir = ctx.run_dir / "01_extract" / "events"
    completed = 0
    empty_chapters: list[int] = []
    events_by_chapter: dict[str, int] = {}
    audit_shas: dict[str, str] = {}
    for number, chapter in chapters.items():
        catalog = modular_evidence_catalog.build_evidence_catalog(number, chapter["text"])
        if not catalog:
            raise ZBatchError(f"第 {number} 章没有生成可用的冻结证据目录")
        coverage = modular_evidence_catalog.evidence_catalog_coverage(chapter["text"], catalog)
        if coverage != 1.0:
            raise ZBatchError(f"第 {number} 章冻结证据目录覆盖率不是 100%：{coverage:.6%}")
        catalog_path = ctx.run_dir / "01_extract" / "evidence_catalogs" / f"ch{number:04d}.json"
        write_json(catalog_path, {"chapter": number, "coverage": coverage, "entries": catalog})

        built = modular_neutral_extract.build_messages(
            prompt_path=prompt_path,
            expected_prompt_sha256=prompt_pin,
            chapter=number,
            chapter_filename=chapter["filename"],
            catalog=catalog,
        )
        output_path = events_dir / f"ch{number:04d}.json"
        input_sha = sha256_bytes(
            (chapter["sha256"] + "\n" + str(built["catalog_sha256"])).encode("utf-8")
        )
        materialized: dict[str, Any] | None = None
        if resume:
            materialized = resume_api_artifact(
                ctx,
                stage="neutral_extract",
                case_id=f"ch{number:04d}",
                output_path=output_path,
                input_sha256=input_sha,
                prompt_sha256=str(built["prompt_sha256"]),
            )

        if materialized is None:
            raw_data = ctx.call_json(
                stage="neutral_extract",
                case_id=f"ch{number:04d}",
                messages=built["messages"],
            )
            materialized, audit = modular_neutral_extract.process_model_data(
                raw_data,
                chapter=number,
                catalog=catalog,
            )
            write_api_artifact(
                ctx,
                stage="neutral_extract",
                case_id=f"ch{number:04d}",
                output_path=output_path,
                data=materialized,
                input_sha256=input_sha,
                prompt_sha256=str(built["prompt_sha256"]),
            )
        else:
            rematerialized, audit = modular_neutral_extract.process_model_data(
                _raw_neutral_event_document(materialized),
                chapter=number,
                catalog=catalog,
            )
            if rematerialized != materialized:
                raise ZBatchError(f"第 {number} 章续跑事件与冻结证据展开结果不一致")

        audit_path = ctx.run_dir / "01_extract" / "program_audits" / f"ch{number:04d}.json"
        write_json(audit_path, audit)
        audit_shas[str(number)] = sha256_file(audit_path)
        event_count = len(materialized.get("events") or [])
        events_by_chapter[str(number)] = event_count
        if event_count == 0:
            empty_chapters.append(number)
            print(f"[{now_iso()}] warning=empty_chapter chapter={number} program_audit=pass", flush=True)
        completed += 1

    metrics = {
        "chapters_completed": completed,
        "chapters_expected": len(chapters),
        "empty_chapters": empty_chapters,
        "empty_chapter_count": len(empty_chapters),
        "events_by_chapter": events_by_chapter,
        "event_total": sum(events_by_chapter.values()),
        "program_audit_pass": True,
        "program_audit_sha256_by_chapter": audit_shas,
        "semantic_coverage_claimed": False,
        "classification_model_calls": 0,
    }
    write_json(ctx.run_dir / "01_extract" / "metrics.json", metrics)
    return metrics


def _classification_inputs(
    batch: dict[str, Any],
) -> tuple[
    modular_classify_rules.ClassificationContract,
    dict[str, Any],
    dict[str, Any],
]:
    """验收本批决定单，同时单独取回批准的历史回归参照件。"""
    contract_value = str(batch.get("classification_contract") or "")
    decisions_value = str(batch.get("classification_decisions") or "")
    if not contract_value or not decisions_value:
        raise ZBatchError("分类阶段缺合同或主控决定路径")
    contract_path = root_path(contract_value)
    decisions_path = root_path(decisions_value)
    contract = modular_classify_rules.load_contract(contract_path, project_root=ROOT)
    expected_sha = str(batch.get("classification_decisions_sha256") or "")
    if not expected_sha or sha256_file(decisions_path) != expected_sha:
        raise ZBatchError("主控分类决定 SHA 漂移")
    regression_reference = modular_classify_rules.promote_approved_reference(
        contract,
        project_root=ROOT,
    )
    if (
        rel(decisions_path) == contract.predecessor_decisions_path
        and expected_sha == contract.predecessor_decisions_sha256
    ):
        if batch.get("replay_source_run_id") != contract.predecessor_run_id:
            raise ZBatchError("批准的 Z00n 决定只允许显式历史回放批次使用")
        decisions = regression_reference
    else:
        decisions = read_json(decisions_path)
        if decisions.get("run_id") != batch.get("run_id"):
            raise ZBatchError("本批主控分类决定 run_id 与批次不一致")
        if decisions.get("rules_sha256") != contract.rules_sha256:
            raise ZBatchError("本批主控分类决定未登记现行分类规则 SHA")
    return contract, decisions, regression_reference


def compile_with_regression_gate(
    event_documents: Iterable[dict[str, Any]],
    decisions_data: dict[str, Any],
    *,
    contract: modular_classify_rules.ClassificationContract,
    chapters: dict[int, dict[str, Any]],
    catalogs: dict[int, dict[str, str]],
    regression_decisions_data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """先显式过三项个案回归闸，再允许编译和独立核锚。"""
    documents = list(event_documents)
    regression_input = (
        regression_decisions_data
        if regression_decisions_data is not None
        else decisions_data
    )
    regression_failures = modular_classify_rules.regression_reasons(
        regression_input,
        contract=contract,
    )
    if regression_failures:
        raise ZBatchError(f"分类个案回归闸失败：{regression_failures}")
    compilation = modular_classify_rules.compile_records(
        documents,
        decisions_data,
        contract=contract,
        evidence_catalogs=catalogs,
    )
    validation = modular_classify_rules.validate_compiled_records(
        compilation,
        chapters=chapters,
        catalogs=catalogs,
    )
    if validation["invalid_total"]:
        raise ZBatchError(f"分类编译后有 {validation['invalid_total']} 条未过锚，拒绝接入核锚阶段")
    return compilation, validation


def _empty_candidate_envelope(chapter: int, rules_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "z-candidate-v1",
        "chapter": chapter,
        "decision_markers": [f"分类权由主控规则执行；弱模型仅交中性事件。规则SHA={rules_sha256}"],
        "coverage_audit": {
            kind: {
                "status": "none",
                "record_ids": [],
                "reason": f"主控按独立规则逐事件裁定；{kind}类共0条，未命中者均在处置账显式登记。",
            }
            for kind in "ABCD"
        },
        "records": [],
    }


def stage_classify(ctx: RunContext, chapters: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """活跃模块路径：主控语义决定只验收、编译，不再交给弱模型分类。"""
    if ctx.batch.get("classification_regression_gate") is not True:
        raise ZBatchError("分类阶段没有显式开启 regression_reasons() 回归闸")
    contract, decisions, regression_reference = _classification_inputs(ctx.batch)
    event_documents: list[dict[str, Any]] = []
    catalogs: dict[int, dict[str, str]] = {}
    for number in chapters:
        event_path = ctx.run_dir / "01_extract" / "events" / f"ch{number:04d}.json"
        catalog_path = ctx.run_dir / "01_extract" / "evidence_catalogs" / f"ch{number:04d}.json"
        if not event_path.is_file() or not catalog_path.is_file():
            raise ZBatchError(f"分类前本批工件未齐：第 {number} 章")
        event_documents.append(read_json(event_path))
        catalog_data = read_json(catalog_path)
        catalogs[number] = {
            str(entry.get("anchor_id")): str(entry.get("quote"))
            for entry in catalog_data.get("entries") or []
            if isinstance(entry, dict) and entry.get("anchor_id") and entry.get("quote")
        }
        if not catalogs[number]:
            raise ZBatchError(f"第 {number} 章冻结证据目录为空")

    compilation, validation = compile_with_regression_gate(
        event_documents,
        decisions,
        contract=contract,
        chapters=chapters,
        catalogs=catalogs,
        regression_decisions_data=regression_reference,
    )
    classify_dir = ctx.run_dir / "01_classify"
    for number in chapters:
        envelope = compilation["candidate_envelopes"].get(number) or _empty_candidate_envelope(
            number,
            contract.rules_sha256,
        )
        envelope_failures = modular_candidate_envelope.validate_candidate_envelope(envelope, number)
        if envelope_failures:
            raise ZBatchError(f"第 {number} 章分类后候选外壳无效：{envelope_failures}")
        write_json(classify_dir / "parsed" / f"ch{number:04d}.json", envelope)
        write_json(ctx.run_dir / "01_extract" / "parsed" / f"ch{number:04d}.json", envelope)

    write_json(classify_dir / "classification_decisions_resolved.json", {
        "schema_version": decisions.get("schema_version"),
        "run_id": decisions.get("run_id"),
        "rules_sha256": decisions.get("rules_sha256"),
        "decisions": compilation["resolved_decisions"],
    })
    write_json(classify_dir / "classification_conflicts.json", compilation["classification_conflicts"])
    write_json(classify_dir / "validation_rows.json", {"rows": validation["rows"]})
    metrics = {
        **compilation["metrics"],
        "regression_gate_called": True,
        "regression_gate_pass": True,
        "compiled_anchor_valid_total": validation["valid_total"],
        "compiled_anchor_invalid_total": validation["invalid_total"],
        "compiled_anchor_valid_rate": validation["anchor_valid_rate"],
    }
    write_json(classify_dir / "metrics.json", metrics)

    extract_metrics = read_optional_json(ctx.run_dir / "01_extract" / "metrics.json") or {}
    extract_metrics.update({
        "records_by_chapter": {
            str(number): len((compilation["candidate_envelopes"].get(number) or {}).get("records") or [])
            for number in chapters
        },
        "candidate_total": compilation["metrics"]["candidate_total"],
        "classification_regression_gate_pass": True,
        "coverage_audit_pass": True,
    })
    write_json(ctx.run_dir / "01_extract" / "metrics.json", extract_metrics)
    return metrics


def prepare_verbatim_restatement_candidate(
    batch: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    """只构造 0.1 候选阶段输入；D-MOD-002 不把它接进自动运行。"""
    value = str((batch.get("prompts") or {}).get("verbatim_restatement") or "")
    expected = str((batch.get("pinned_sha256") or {}).get(value) or "")
    if not value or not expected:
        raise ZBatchError("原样复述候选缺 Prompt 或 SHA")
    bundle = load_active_stage_bundle(batch)
    candidate = bundle.candidates["verbatim_restatement"]
    built = modular_verbatim_restatement.build_messages(
        source,
        prompt_path=root_path(value),
        expected_prompt_sha256=expected,
    )
    return {
        **built,
        "contract_status": candidate.status,
        "temperature": candidate.temperature,
        "n": candidate.n,
        "auto_callable": False,
    }


def stage_verify(ctx: RunContext, chapters: dict[int, dict[str, Any]]) -> dict[str, Any]:
    parsed_dir = ctx.run_dir / "01_extract" / "parsed"
    rows: list[dict[str, Any]] = []
    ids: Counter[str] = Counter()
    loaded: list[tuple[int, Path, dict[str, Any]]] = []
    for number in chapters:
        path = parsed_dir / f"ch{number:04d}.json"
        if not path.is_file():
            raise ZBatchError(f"核锚前缺提取结果：{path}")
        data = read_json(path)
        loaded.append((number, path, data))
        for record in data.get("records") or []:
            if isinstance(record, dict) and isinstance(record.get("id"), str):
                ids[record["id"]] += 1

    for number, path, data in loaded:
        catalog_path = ctx.run_dir / "01_extract" / "evidence_catalogs" / f"ch{number:04d}.json"
        if not catalog_path.is_file():
            raise ZBatchError(f"核锚缺冻结证据目录，拒绝降级放行：{catalog_path}")
        catalog_data = read_json(catalog_path)
        if catalog_data.get("coverage") != 1.0:
            raise ZBatchError(f"冻结证据目录覆盖率记录异常：{catalog_path}")
        catalog_map = {
            str(entry.get("anchor_id")): str(entry.get("quote"))
            for entry in catalog_data.get("entries") or []
            if isinstance(entry, dict) and entry.get("anchor_id") and entry.get("quote")
        }
        if not catalog_map:
            raise ZBatchError(f"冻结证据目录为空：{catalog_path}")
        for record in data.get("records") or []:
            reasons, anchor_checks = modular_anchor_kit.validate_record(
                record,
                chapters,
                expected_chapter=number,
                evidence_catalog=catalog_map,
            )
            record_id = record.get("id") if isinstance(record, dict) else None
            if isinstance(record_id, str) and ids[record_id] > 1:
                reasons = sorted(set(reasons + ["ID重复"]))
            rows.append({
                "source_chapter": number,
                "source_file": rel(path),
                "record": record,
                "valid": not reasons,
                "reasons": reasons,
                "anchor_checks": anchor_checks,
            })

    valid_records: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    for row in rows:
        if row["valid"]:
            record = copy.deepcopy(row["record"])
            record["_source_chapter"] = row["source_chapter"]
            valid_records.append(record)
        else:
            invalid_rows.append(row)

    type_total = Counter(
        row["record"].get("type")
        for row in rows
        if isinstance(row.get("record"), dict) and row["record"].get("type") in TYPE_REQUIRED_FIELDS
    )
    type_valid = Counter(record.get("type") for record in valid_records)
    reason_counts = Counter(reason for row in invalid_rows for reason in row.get("reasons") or [])
    extract_metrics = read_optional_json(ctx.run_dir / "01_extract" / "metrics.json") or {}
    overlap = modular_candidate_envelope.cross_type_anchor_overlap(valid_records)
    metrics = {
        "candidate_total": len(rows),
        "valid_total": len(valid_records),
        "invalid_total": len(invalid_rows),
        "anchor_valid_rate": round(len(valid_records) / len(rows), 6) if rows else 0.0,
        "by_type": {
            kind: {
                "total": type_total[kind],
                "valid": type_valid[kind],
                "invalid": type_total[kind] - type_valid[kind],
                "valid_rate": round(type_valid[kind] / type_total[kind], 6) if type_total[kind] else None,
            }
            for kind in "ABCD"
        },
        "invalid_reasons": dict(reason_counts),
        "empty_chapters": extract_metrics.get("empty_chapters") or [],
        "empty_chapter_count": extract_metrics.get("empty_chapter_count", 0),
        "coverage_audit_pass": extract_metrics.get("coverage_audit_pass") is True,
        "cross_type_anchor_overlap": {
            "shared_anchor_count": overlap["shared_anchor_count"],
            "cross_type_pair_count": overlap["cross_type_pair_count"],
        },
    }
    out = ctx.run_dir / "02_verify"
    write_json(out / "validation_rows.json", rows)
    write_json(out / "valid_records.json", {"records": valid_records})
    write_json(out / "invalid_records.json", {"rows": invalid_rows})
    write_json(out / "跨类型共享锚诊断.json", overlap)
    write_json(out / "metrics.json", metrics)
    report = (
        "# 程序核锚报告\n\n"
        f"- 候选：{len(rows)} 条\n"
        f"- 过锚：{len(valid_records)} 条\n"
        f"- 判废：{len(invalid_rows)} 条\n"
        f"- 有效率：{metrics['anchor_valid_rate']:.2%}\n"
        f"- A/B/C/D：{json.dumps(metrics['by_type'], ensure_ascii=False)}\n"
        f"- 废因：{json.dumps(metrics['invalid_reasons'], ensure_ascii=False)}\n\n"
        f"- 跨类型共享锚：{overlap['shared_anchor_count']} 个锚、{overlap['cross_type_pair_count']} 对记录（只报警，待语义复核）\n\n"
        "失败条只进统计，没有改写或补锚。\n\n"
        "来源：Codex\n"
    )
    write_text(out / "程序核锚报告.md", report)
    if not valid_records:
        raise ZBatchError("全部候选都被核锚判废，后续阶段停止")
    return metrics


def derived_records_valid(
    records: Any,
    chapters: dict[int, dict[str, Any]],
    allowed_source_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """兼容函数名；压薄记录验收由 downstream_validate 模块单独维护。"""
    return modular_downstream_validate.derived_records_valid(
        records,
        chapters,
        allowed_source_ids,
    )


def stage_thin(ctx: RunContext, chapters: dict[int, dict[str, Any]], *, resume: bool) -> dict[str, Any]:
    verified = read_json(ctx.run_dir / "02_verify" / "valid_records.json").get("records") or []
    if not isinstance(verified, list) or not verified:
        raise ZBatchError("没有可压薄的过锚候选")
    raw_source_ids = {str(record.get("id")) for record in verified if isinstance(record, dict)}
    raw_record_map = {
        str(record.get("id")): record
        for record in verified
        if isinstance(record, dict) and record.get("id")
    }
    template = prompt_text(ctx.batch, "thin")
    segment_size = int(ctx.batch.get("thin_segment_size", 20))
    start = int(ctx.batch["chapter_start"])
    end = int(ctx.batch["chapter_end"])
    segment_dir = ctx.run_dir / "03_thin" / "segments"
    all_segment_records: list[dict[str, Any]] = []
    segment_invalid: list[dict[str, Any]] = []
    segment_count = 0
    for seg_start in range(start, end + 1, segment_size):
        seg_end = min(seg_start + segment_size - 1, end)
        segment_count += 1
        source = [
            {k: v for k, v in record.items() if k != "_source_chapter"}
            for record in verified
            if seg_start <= int(record.get("_source_chapter", -1)) <= seg_end
        ]
        case_id = f"ch{seg_start:04d}-{seg_end:04d}"
        parsed_path = segment_dir / f"{case_id}.json"
        if not source:
            write_json(parsed_path, {
                "schema_version": "z-thin-v1",
                "segment": case_id,
                "decision_markers": ["本段没有过锚候选，机械跳过 API 调用"],
                "records": [],
            })
            continue
        source_json = json.dumps(source, ensure_ascii=False, indent=2)
        prompt = replace_prompt(template, {
            "SEGMENT_LABEL": f"第 {seg_start}～{seg_end} 章",
            "VALID_RECORDS_JSON": source_json,
        })
        input_sha = sha256_bytes(source_json.encode("utf-8"))
        prompt_sha = sha256_bytes(prompt.encode("utf-8"))
        data = None
        if resume:
            data = resume_api_artifact(
                ctx,
                stage="thin",
                case_id=case_id,
                output_path=parsed_path,
                input_sha256=input_sha,
                prompt_sha256=prompt_sha,
            )
        if data is None:
            data = ctx.call_json(
                stage="thin",
                case_id=case_id,
                messages=[
                    {"role": "system", "content": "你是事件级结构压薄器。只能合并已给候选，不能新增事实或锚。只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
            )
            data["records"] = modular_anchor_kit.materialize_anchors_from_sources(
                data.get("records"), raw_record_map, source_field="source_record_ids"
            )
            write_api_artifact(
                ctx,
                stage="thin",
                case_id=case_id,
                output_path=parsed_path,
                data=data,
                input_sha256=input_sha,
                prompt_sha256=prompt_sha,
            )
        valid, invalid = modular_downstream_validate.derived_records_valid(
            data.get("records"), chapters, raw_source_ids
        )
        all_segment_records.extend(valid)
        segment_invalid.extend({"segment": case_id, **row} for row in invalid)

    if not all_segment_records:
        raise ZBatchError("分段压薄后没有任何合法记录")
    final_path = ctx.run_dir / "03_thin" / "main_ledger.json"
    final_source_json = json.dumps(all_segment_records, ensure_ascii=False, indent=2)
    prompt = replace_prompt(template, {
        "SEGMENT_LABEL": "全书总合并；保留原始 source_record_ids",
        "VALID_RECORDS_JSON": final_source_json,
    })
    final_input_sha = sha256_bytes(final_source_json.encode("utf-8"))
    final_prompt_sha = sha256_bytes(prompt.encode("utf-8"))
    final_data = None
    if resume:
        final_data = resume_api_artifact(
            ctx,
            stage="thin",
            case_id="full_merge",
            output_path=final_path,
            input_sha256=final_input_sha,
            prompt_sha256=final_prompt_sha,
        )
    if final_data is not None:
        final_valid = final_data.get("records") or []
        invalid_data = read_optional_json(ctx.run_dir / "03_thin" / "invalid_records.json") or {}
        final_invalid = invalid_data.get("rows") or []
    else:
        final_response = ctx.call_json(
            stage="thin",
            case_id="full_merge",
            messages=[
                {"role": "system", "content": "你是全书事件账合并器。只能合并已给分段记录，source_record_ids 必须追到原始候选。只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
        )
        final_response["records"] = modular_anchor_kit.materialize_anchors_from_sources(
            final_response.get("records"), raw_record_map, source_field="source_record_ids"
        )
        final_valid, final_invalid = modular_downstream_validate.derived_records_valid(
            final_response.get("records"), chapters, raw_source_ids
        )
        final_data = {
            "schema_version": "z-thin-v1",
            "segment": "full",
            "decision_markers": final_response.get("decision_markers") or [],
            "review_groups": final_response.get("review_groups") or [],
            "records": final_valid,
        }
        write_api_artifact(
            ctx,
            stage="thin",
            case_id="full_merge",
            output_path=final_path,
            data=final_data,
            input_sha256=final_input_sha,
            prompt_sha256=final_prompt_sha,
        )
        write_json(ctx.run_dir / "03_thin" / "invalid_records.json", {
            "segment_rows": segment_invalid,
            "rows": final_invalid,
        })

    by_type = Counter(record.get("type") for record in final_valid if isinstance(record, dict))
    metrics = {
        "dense_valid_records": len(verified),
        "segment_count": segment_count,
        "segment_valid_records": len(all_segment_records),
        "segment_invalid_records": len(segment_invalid),
        "thin_records": len(final_valid),
        "thin_invalid_records": len(final_invalid),
        "thin_A_records": by_type["A"],
        "by_type": {kind: by_type[kind] for kind in "ABCD"},
        "dense_to_thin_ratio": round(len(final_valid) / len(verified), 6),
        "review_groups": len(final_data.get("review_groups") or []),
        "near_zero_thinning": len(verified) >= 20 and len(final_valid) / len(verified) >= 0.98,
    }
    write_json(ctx.run_dir / "03_thin" / "metrics.json", metrics)
    if not final_valid:
        raise ZBatchError("全书压薄后没有合法记录")
    return metrics


def record_anchor_chapters(record: Any) -> set[int]:
    """兼容函数名；锚章集合计算由 downstream_validate 模块单独维护。"""
    return modular_downstream_validate.record_anchor_chapters(record)


def validate_macro(
    macro: Any,
    chapters: dict[int, dict[str, Any]],
    ledger_map: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """兼容函数名；折叠宏节点验收由 downstream_validate 模块单独维护。"""
    return modular_downstream_validate.validate_macro(macro, chapters, ledger_map)


def enforce_fold_gate(metrics: dict[str, Any]) -> None:
    """兼容函数名；折叠闸由 downstream_validate 模块单独维护。"""
    modular_downstream_validate.enforce_fold_gate(metrics)


def enforce_answer_gate(metrics: dict[str, Any]) -> None:
    """兼容函数名；答题闸由 downstream_validate 模块单独维护。"""
    modular_downstream_validate.enforce_answer_gate(metrics)


def enforce_compare_gate(metrics: dict[str, Any]) -> None:
    """兼容函数名；对撞闸由 downstream_validate 模块单独维护。"""
    modular_downstream_validate.enforce_compare_gate(metrics)


def stage_fold(ctx: RunContext, chapters: dict[int, dict[str, Any]], *, resume: bool) -> dict[str, Any]:
    ledger = read_json(ctx.run_dir / "03_thin" / "main_ledger.json")
    ledger_map = {
        str(record.get("id")): record
        for record in ledger.get("records") or []
        if isinstance(record, dict) and record.get("id")
    }
    ledger_ids = set(ledger_map)
    output_path = ctx.run_dir / "04_fold" / "fold_view.json"
    ledger_json = json.dumps(ledger, ensure_ascii=False, indent=2)
    prompt = replace_prompt(prompt_text(ctx.batch, "fold"), {
        "THIN_LEDGER_JSON": ledger_json,
    })
    input_sha = sha256_bytes(ledger_json.encode("utf-8"))
    prompt_sha = sha256_bytes(prompt.encode("utf-8"))
    data = None
    if resume:
        data = resume_api_artifact(
            ctx,
            stage="fold",
            case_id="full_view",
            output_path=output_path,
            input_sha256=input_sha,
            prompt_sha256=prompt_sha,
        )
    if data is None:
        data = ctx.call_json(
            stage="fold",
            case_id="full_view",
            messages=[
                {"role": "system", "content": "你是只读折叠视图生成器。不能删除底账或新增证据。只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
        )
        data["macros"] = modular_anchor_kit.materialize_anchors_from_sources(
            data.get("macros"), ledger_map, source_field="source_record_ids"
        )
        write_api_artifact(
            ctx,
            stage="fold",
            case_id="full_view",
            output_path=output_path,
            data=data,
            input_sha256=input_sha,
            prompt_sha256=prompt_sha,
        )
    macros = data.get("macros")
    if not isinstance(macros, list):
        raise ZBatchError("折叠输出 macros 不是数组")
    rows = []
    for macro in macros:
        reasons, checks = modular_downstream_validate.validate_macro(macro, chapters, ledger_map)
        rows.append({"macro": macro, "valid": not reasons, "reasons": reasons, "anchor_checks": checks})
    compressed = data.get("compressed_view_markdown")
    if not isinstance(compressed, str) or not compressed.strip():
        raise ZBatchError("折叠输出缺 compressed_view_markdown")
    open_ids = data.get("open_record_ids")
    coverage_reasons: list[str] = []
    if not isinstance(open_ids, list):
        coverage_reasons.append("开放记录ID不是数组")
        open_ids = []
    normalized_open_ids = [str(value) for value in open_ids]
    if any(not isinstance(value, str) for value in open_ids):
        coverage_reasons.append("开放记录ID不是字符串")
    if len(normalized_open_ids) != len(set(normalized_open_ids)):
        coverage_reasons.append("开放记录ID重复")
    unknown_open_ids = sorted(set(normalized_open_ids) - ledger_ids)
    if unknown_open_ids:
        coverage_reasons.append("开放记录ID不存在")
    macro_source_lists = [
        macro.get("source_record_ids") or []
        for macro in macros
        if isinstance(macro, dict) and isinstance(macro.get("source_record_ids"), list)
    ]
    macro_source_ids = [str(value) for values in macro_source_lists for value in values]
    if len(macro_source_ids) != len(set(macro_source_ids)):
        coverage_reasons.append("同一主账记录被多个宏重复折叠")
    overlap = sorted(set(macro_source_ids) & set(normalized_open_ids))
    if overlap:
        coverage_reasons.append("宏来源与开放记录重叠")
    covered = set(macro_source_ids) | set(normalized_open_ids)
    missing = sorted(ledger_ids - covered)
    extras = sorted(covered - ledger_ids)
    if missing:
        coverage_reasons.append("主账记录未被折叠或保留")
    if extras:
        coverage_reasons.append("折叠视图引用主账外记录")
    cross_line_exits = data.get("cross_line_exits")
    if not isinstance(cross_line_exits, list):
        coverage_reasons.append("跨线出口不是数组")
        cross_line_exits = []
    if any(not isinstance(value, str) for value in cross_line_exits):
        coverage_reasons.append("跨线出口ID不是字符串")
    if any(str(value) not in ledger_ids for value in cross_line_exits):
        coverage_reasons.append("跨线出口ID不存在")

    metrics = {
        "macros_total": len(rows),
        "macros_valid": sum(1 for row in rows if row["valid"]),
        "macros_invalid": sum(1 for row in rows if not row["valid"]),
        "coverage_pass": not coverage_reasons and covered == ledger_ids,
        "coverage_reasons": sorted(set(coverage_reasons)),
        "covered_record_ids": len(covered & ledger_ids),
        "ledger_record_ids": len(ledger_ids),
        "compressed_view_nonspace_chars": nonspace_chars(compressed),
        "open_record_ids": len(open_ids),
        "cross_line_exits": len(cross_line_exits),
    }
    write_json(ctx.run_dir / "04_fold" / "validation.json", {
        "rows": rows,
        "coverage": {
            "valid": not coverage_reasons and covered == ledger_ids,
            "reasons": sorted(set(coverage_reasons)),
            "missing_record_ids": missing,
            "extra_record_ids": extras,
            "overlap_record_ids": overlap,
        },
    })
    write_json(ctx.run_dir / "04_fold" / "metrics.json", metrics)
    write_text(ctx.run_dir / "04_fold" / "压缩视图.md", compressed.rstrip() + "\n\n来源：DeepSeek 原始视图；Codex 仅落盘\n")
    modular_downstream_validate.enforce_fold_gate(metrics)
    return metrics


def gradient_bucket_for_distance(distance: int) -> str | None:
    """兼容函数名；梯度分档由 downstream_validate 模块单独维护。"""
    return modular_downstream_validate.gradient_bucket_for_distance(distance)


def validate_gradient_points(
    item: dict[str, Any],
    ledger_map: dict[str, dict[str, Any]],
    sample_end: int,
) -> list[str]:
    """兼容函数名；梯度落点验收由 downstream_validate 模块单独维护。"""
    return modular_downstream_validate.validate_gradient_points(item, ledger_map, sample_end)


def validate_answer_items(
    items: Any,
    chapters: dict[int, dict[str, Any]],
    ledger_map: dict[str, dict[str, Any]],
    sample_end: int,
    fold: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """兼容函数名；四型答题验收由 downstream_validate 模块单独维护。"""
    return modular_downstream_validate.validate_answer_items(
        items,
        chapters,
        ledger_map,
        sample_end,
        fold,
    )


def stage_answer(ctx: RunContext, chapters: dict[int, dict[str, Any]], *, resume: bool) -> dict[str, Any]:
    ledger = read_json(ctx.run_dir / "03_thin" / "main_ledger.json")
    fold = read_json(ctx.run_dir / "04_fold" / "fold_view.json")
    ledger_map = {
        str(record.get("id")): record
        for record in ledger.get("records") or []
        if isinstance(record, dict) and record.get("id")
    }
    output_path = ctx.run_dir / "05_answer" / "answer.json"
    ledger_json = json.dumps(ledger, ensure_ascii=False, indent=2)
    fold_json = json.dumps(fold, ensure_ascii=False, indent=2)
    prompt = replace_prompt(prompt_text(ctx.batch, "answer"), {
        "THIN_LEDGER_JSON": ledger_json,
        "FOLD_VIEW_JSON": fold_json,
    })
    input_sha = sha256_bytes((ledger_json + "\n" + fold_json).encode("utf-8"))
    prompt_sha = sha256_bytes(prompt.encode("utf-8"))
    data = None
    if resume:
        data = resume_api_artifact(
            ctx,
            stage="answer",
            case_id="four_types",
            output_path=output_path,
            input_sha256=input_sha,
            prompt_sha256=prompt_sha,
        )
    if data is None:
        data = ctx.call_json(
            stage="answer",
            case_id="four_types",
            messages=[
                {"role": "system", "content": "你是结构账自测答题器。不能读取银标，也不能脱离账本编剧情。只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
        )
        data["items"] = modular_anchor_kit.materialize_anchors_from_sources(
            data.get("items"), ledger_map, source_field="record_ids"
        )
        write_api_artifact(
            ctx,
            stage="answer",
            case_id="four_types",
            output_path=output_path,
            data=data,
            input_sha256=input_sha,
            prompt_sha256=prompt_sha,
        )
    rows, metrics = modular_downstream_validate.validate_answer_items(
        data.get("items"),
        chapters,
        ledger_map,
        int(ctx.batch["chapter_end"]),
        fold,
    )
    write_json(ctx.run_dir / "05_answer" / "validation.json", {"rows": rows})
    write_json(ctx.run_dir / "05_answer" / "metrics.json", metrics)
    modular_downstream_validate.enforce_answer_gate(metrics)
    return metrics


def validate_compare_items(
    items: Any,
    answer_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """兼容函数名；银标对撞验收由 downstream_validate 模块单独维护。"""
    return modular_downstream_validate.validate_compare_items(items, answer_items)


def stage_compare(ctx: RunContext, *, resume: bool) -> dict[str, Any]:
    answer = read_json(ctx.run_dir / "05_answer" / "answer.json")
    silver_text = root_path(ctx.batch["silver_answer"]).read_text(encoding="utf-8")
    output_path = ctx.run_dir / "06_compare" / "diff.json"
    answer_json = json.dumps(answer, ensure_ascii=False, indent=2)
    prompt = replace_prompt(prompt_text(ctx.batch, "compare"), {
        "OUR_ANSWER_JSON": answer_json,
        "SILVER_ANSWER_TEXT": silver_text,
    })
    input_sha = sha256_bytes((answer_json + "\n" + silver_text).encode("utf-8"))
    prompt_sha = sha256_bytes(prompt.encode("utf-8"))
    data = None
    if resume:
        data = resume_api_artifact(
            ctx,
            stage="compare",
            case_id="silver_diff",
            output_path=output_path,
            input_sha256=input_sha,
            prompt_sha256=prompt_sha,
        )
    if data is None:
        data = ctx.call_json(
            stage="compare",
            case_id="silver_diff",
            messages=[
                {"role": "system", "content": "你是银标对撞记录员，不是裁判。证据不够必须留待裁。只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
        )
        write_api_artifact(
            ctx,
            stage="compare",
            case_id="silver_diff",
            output_path=output_path,
            data=data,
            input_sha256=input_sha,
            prompt_sha256=prompt_sha,
        )
    answer_items = answer.get("items")
    if not isinstance(answer_items, list):
        raise ZBatchError("本地答案 items 不是数组")
    rows, metrics = modular_downstream_validate.validate_compare_items(data.get("items"), answer_items)
    metrics["silver_role"] = ctx.batch.get("silver_role")
    metrics["score_verdict"] = "not_set"
    write_json(ctx.run_dir / "06_compare" / "validation.json", {"rows": rows})
    write_json(ctx.run_dir / "06_compare" / "metrics.json", metrics)
    modular_downstream_validate.enforce_compare_gate(metrics)
    return metrics


def stage_review(ctx: RunContext) -> dict[str, Any]:
    """机械外发闸；语义结论仍需独立团队审查签收。"""
    thin = read_json(ctx.run_dir / "03_thin" / "metrics.json")
    fold = read_json(ctx.run_dir / "04_fold" / "metrics.json")
    answer = read_json(ctx.run_dir / "05_answer" / "metrics.json")
    compare = read_json(ctx.run_dir / "06_compare" / "metrics.json")
    preflight_data = read_json(ctx.run_dir / "preflight.json")
    preflight_checks = preflight_data.get("checks") if isinstance(preflight_data.get("checks"), list) else []
    intake_checks = [
        check for check in preflight_checks
        if isinstance(check, dict) and str(check.get("name") or "").startswith("intake_")
    ]
    imported = verify_materialized_import(ctx.run_dir, ctx.batch)
    imported_thin = verify_materialized_thin_import(ctx.run_dir, ctx.batch)
    checks = [
        {
            "name": "fold_structure",
            "ok": fold.get("macros_invalid") == 0 and fold.get("coverage_pass") is True,
            "detail": fold,
        },
        {
            "name": "answer_question_identity",
            "ok": answer.get("five_question_pass") is True,
            "detail": answer,
        },
        {
            "name": "compare_compatibility",
            "ok": compare.get("comparison_pass") is True,
            "detail": compare,
        },
        {
            "name": "intake_binding",
            "ok": bool(intake_checks) and all(check.get("ok") is True for check in intake_checks),
            "detail": intake_checks,
        },
        {
            "name": "imported_verify_integrity",
            "ok": imported.get("status") in {"pass", "not_used"},
            "detail": imported,
        },
        {
            "name": "imported_thin_integrity",
            "ok": imported_thin.get("status") in {"pass", "not_used"},
            "detail": imported_thin,
        },
    ]
    warnings: list[dict[str, Any]] = []
    if thin.get("dense_valid_records", 0) >= 20 and thin.get("dense_to_thin_ratio", 0) >= 0.98:
        warnings.append({
            "code": "ZERO_OR_NEAR_ZERO_THINNING",
            "message": "压薄率接近 1，团队语义审查必须抽查同事件重复和期待生命周期。",
        })
    mechanical_pass = all(check["ok"] for check in checks)
    review = {
        "schema_version": "z-review-v1",
        "created_at": now_iso(),
        "run_id": ctx.batch.get("run_id"),
        "mechanical_pass": mechanical_pass,
        "ready_for_semantic_review": mechanical_pass,
        "semantic_attestation_required": True,
        "external_ready": False,
        "checks": checks,
        "warnings": warnings,
        "boundary": "机械校验通过不等于语义结论成立；打包前必须有独立团队审查签收。",
    }
    review_dir = ctx.run_dir / "07_review"
    write_json(review_dir / "mechanical_review.json", review)
    warning_text = "\n".join(f"- {item['message']}" for item in warnings) or "- 无机械预警。"
    write_text(
        review_dir / "机械外发闸.md",
        f"""# 机械外发闸

- 机械校验：{'通过' if mechanical_pass else '未通过'}
- 可进入团队语义审查：{'是' if mechanical_pass else '否'}
- 当前可外发：否

## 预警

{warning_text}

机械命中只能证明格式、ID、章号和规则计算没有直接冲突，不能代替语义审查。团队签收前，正式包不会进入 `outbox/`。

来源：Codex
""",
    )
    if not mechanical_pass:
        raise ZBatchError("机械外发闸未通过，拒绝生成正式报告")
    return review


def verify_semantic_attestation(run_dir: Path) -> dict[str, Any]:
    review_dir = run_dir / "07_review"
    mechanical_path = review_dir / "mechanical_review.json"
    attestation_path = review_dir / "semantic_attestation.json"
    if not mechanical_path.is_file() or not attestation_path.is_file():
        raise ZBatchError("打包前缺团队语义审查签收")
    mechanical = read_json(mechanical_path)
    attestation = read_json(attestation_path)
    if mechanical.get("mechanical_pass") is not True:
        raise ZBatchError("机械外发闸未通过，不能签收")
    if attestation.get("decision") != "pass":
        raise ZBatchError("团队语义审查未放行，不能打包")
    if attestation.get("mechanical_review_sha256") != sha256_file(mechanical_path):
        raise ZBatchError("团队签收绑定的机械审查已漂移")
    review_file = root_path(str(attestation.get("review_file") or ""))
    try:
        review_file.resolve().relative_to(review_dir.resolve())
    except ValueError as exc:
        raise ZBatchError("团队审查文件不在本运行的 07_review 内") from exc
    if not review_file.is_file() or sha256_file(review_file) != attestation.get("review_file_sha256"):
        raise ZBatchError("团队审查文件缺失或漂移")
    if not str(attestation.get("reviewer") or "").strip():
        raise ZBatchError("团队签收缺审查者")
    return {
        "status": "pass",
        "attestation": rel(attestation_path),
        "attestation_sha256": sha256_file(attestation_path),
        "review_file": rel(review_file),
        "review_file_sha256": sha256_file(review_file),
        "reviewer": attestation.get("reviewer"),
    }


def attest_review(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = (RUNS_DIR / args.run_id).resolve()
    try:
        run_dir.relative_to(RUNS_DIR.resolve())
    except ValueError as exc:
        raise ZBatchError("运行编号越出 runs 目录") from exc
    if run_dir.parent != RUNS_DIR.resolve() or not run_dir.is_dir():
        raise ZBatchError(f"找不到运行：{args.run_id}")
    review_dir = run_dir / "07_review"
    mechanical_path = review_dir / "mechanical_review.json"
    if not mechanical_path.is_file():
        raise ZBatchError("签收前缺机械外发闸结果")
    mechanical = read_json(mechanical_path)
    if args.decision == "pass" and mechanical.get("mechanical_pass") is not True:
        raise ZBatchError("机械外发闸未通过，不能放行")
    review_file = root_path(args.review_file)
    try:
        review_file.resolve().relative_to(review_dir.resolve())
    except ValueError as exc:
        raise ZBatchError("审查文件必须放在该运行的 07_review 目录") from exc
    if not review_file.is_file() or review_file.stat().st_size == 0:
        raise ZBatchError("审查文件不存在或为空")
    target = review_dir / "semantic_attestation.json"
    if target.exists():
        raise ZBatchError("团队语义签收已存在，拒绝覆盖；结论变化请新开运行")
    attestation = {
        "schema_version": "z-semantic-attestation-v1",
        "run_id": args.run_id,
        "reviewed_at": now_iso(),
        "reviewer": args.reviewer,
        "decision": args.decision,
        "review_file": rel(review_file),
        "review_file_sha256": sha256_file(review_file),
        "mechanical_review_sha256": sha256_file(mechanical_path),
        "boundary": "团队核验意见只决定本次测试包能否外发，不替 CZ 拍产品口径。",
    }
    write_json(target, attestation)
    return {"attestation": rel(target), **attestation}


def read_optional_json(path: Path) -> dict[str, Any] | None:
    return read_json(path) if path.is_file() else None


def usage_summary(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "usage.jsonl"
    rows: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    totals = Counter()
    by_stage: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        stage = str(row.get("stage") or "unknown")
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                totals[key] += int(value)
                by_stage[stage][key] += int(value)
    return {
        "successful_calls": len(rows),
        "totals": dict(totals),
        "by_stage": {stage: dict(counts) for stage, counts in by_stage.items()},
    }


def collect_decision_markers(run_dir: Path) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*.json")):
        if any(part in {"requests", "responses"} for part in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        values = data.get("decision_markers")
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value.strip():
                    markers.append({"source": rel(path), "marker": value.strip()})
    return markers


def stage_report(ctx: RunContext) -> dict[str, Any]:
    run_id = str(ctx.batch["run_id"])
    report_dir = REPORTS_DIR / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    verify = read_optional_json(ctx.run_dir / "02_verify" / "metrics.json")
    thin = read_optional_json(ctx.run_dir / "03_thin" / "metrics.json")
    fold = read_optional_json(ctx.run_dir / "04_fold" / "metrics.json")
    answer = read_optional_json(ctx.run_dir / "05_answer" / "metrics.json")
    diff = read_optional_json(ctx.run_dir / "06_compare" / "metrics.json")
    review = read_optional_json(ctx.run_dir / "07_review" / "mechanical_review.json")
    attestation = read_optional_json(ctx.run_dir / "07_review" / "semantic_attestation.json")
    imported_source = read_optional_json(ctx.run_dir / "imports" / "verified_source.json")
    usage = usage_summary(ctx.run_dir)
    markers = collect_decision_markers(ctx.run_dir)

    summary = {
        "run_id": run_id,
        "batch_id": ctx.batch.get("batch_id"),
        "item_id": ctx.batch.get("item_id"),
        "book_name": ctx.batch.get("book_name"),
        "model": ctx.provider.get("model"),
        "created_at": now_iso(),
        "verify": verify,
        "thin": thin,
        "fold": fold,
        "answer": answer,
        "diff": diff,
        "review": review,
        "semantic_attestation": attestation,
        "usage": usage,
        "rights": ctx.batch.get("rights"),
        "silver_role": ctx.batch.get("silver_role"),
        "prompt_change_note": ctx.batch.get("prompt_change_note"),
        "import_verified_run": ctx.batch.get("import_verified_run"),
        "import_thin_run": ctx.batch.get("import_thin_run"),
        "imported_source_status": (
            "上游提取与核锚已验证；原运行在下游中断"
            if imported_source and imported_source.get("source_verification", {}).get("source_status") == "failed"
            else "未复用失败运行的已验证上游"
        ),
    }
    write_json(report_dir / "summary.json", summary)

    if (ctx.run_dir / "03_thin" / "main_ledger.json").is_file():
        ledger = read_json(ctx.run_dir / "03_thin" / "main_ledger.json")
        write_json(report_dir / "结构记录_事件级主账.json", ledger)
        by_type: dict[str, list[dict[str, Any]]] = {kind: [] for kind in "ABCD"}
        for record in ledger.get("records") or []:
            if isinstance(record, dict) and record.get("type") in by_type:
                by_type[record["type"]].append(record)
        for kind, records in by_type.items():
            write_json(report_dir / f"结构记录_{kind}账.json", {"type": kind, "records": records})
    for source, target in [
        (ctx.run_dir / "02_verify" / "metrics.json", "程序核锚指标.json"),
        (ctx.run_dir / "02_verify" / "程序核锚报告.md", "程序核锚报告.md"),
        (ctx.run_dir / "04_fold" / "fold_view.json", "折叠视图.json"),
        (ctx.run_dir / "04_fold" / "压缩视图.md", "压缩视图.md"),
        (ctx.run_dir / "05_answer" / "answer.json", "四型答题.json"),
        (ctx.run_dir / "06_compare" / "diff.json", "银标对撞diff.json"),
        (ctx.run_dir / "07_review" / "mechanical_review.json", "机械外发闸.json"),
        (ctx.run_dir / "07_review" / "机械外发闸.md", "机械外发闸.md"),
        (ctx.run_dir / "07_review" / "team_review.md", "团队语义审查.md"),
        (ctx.run_dir / "07_review" / "semantic_attestation.json", "团队语义签收.json"),
    ]:
        if source.is_file():
            shutil.copy2(source, report_dir / target)

    verify_text = "未到核锚阶段"
    if verify:
        verify_text = f"{verify['valid_total']}/{verify['candidate_total']}（{verify['anchor_valid_rate']:.2%}）"
    thin_text = "本次未跑"
    if thin:
        thin_text = f"密账 {thin['dense_valid_records']} → 事件账 {thin['thin_records']}，其中 A {thin['thin_A_records']}"
    fold_text = "本次未跑"
    if fold:
        fold_text = f"{fold['compressed_view_nonspace_chars']} 个非空白字符"
    diff_text = "本次未跑"
    if diff:
        diff_text = json.dumps(diff.get("labels") or {}, ensure_ascii=False)
    review_text = "本次未跑"
    if review:
        review_text = "机械通过，待团队语义签收" if review.get("mechanical_pass") else "机械未通过"
    if attestation:
        review_text = f"团队语义审查：{attestation.get('decision')}（{attestation.get('reviewer')}）"
    import_text = summary["imported_source_status"]

    receipt = f"""# 回包·{ctx.batch.get('batch_id')}·{ctx.batch.get('item_id')}·{ctx.batch.get('book_name')}·DeepSeek

✅ 本回包只记录测试数据，不替 CZ 拍薄厚取舍、梯度切点或达标线。

- 运行编号：`{run_id}`
- 模型：`{ctx.provider.get('model')}`
- 章节：{ctx.batch.get('chapter_start')}～{ctx.batch.get('chapter_end')}
- 证据锚有效率：{verify_text}
- 薄厚数据：{thin_text}
- 压缩视图：{fold_text}
- 银标差异：{diff_text}
- 外发审查：{review_text}
- 上游复用：{import_text}
- 成功 API 调用：{usage['successful_calls']}
- 银标地位：{ctx.batch.get('silver_role')}
- 用途：{ctx.batch.get('rights')}
- Prompt 改动：{ctx.batch.get('prompt_change_note') or '本批无单列改动说明'}

⚠️ `我对它错 / 它对我错 / 等价 / 待裁` 只是逐题对撞标签，不是总判词。四件套字段级金标尚未建立。

来源：Codex
"""
    write_text(report_dir / "回执.md", receipt)
    write_text(
        report_dir / "00_用途声明.md",
        f"# 用途声明\n\n{ctx.batch.get('rights')}。\n\n来源：Codex\n",
    )

    marker_preview = markers[:80]
    method = f"""# 方法复盘

## 颗粒度

密候选按一章一次调用；程序核锚后，再按 {ctx.batch.get('thin_segment_size')} 章一段做事件级压薄，保留逐章底账。

## 断链

流水线不靠事后补写原锚接断链。跨章关系只能引用已经过锚的候选；找不到来源 ID 的派生条判废。

## 折叠

只生成视图，保留根因、最大转折、结果、开放口和跨线出口。底账不删除。

## 故事线

提取时每条 A 都带故事线；合并时人物相同或章节相邻不算同一事件，交叉关系用 ID 引用。

## 弯路和失败

- JSON 解析失败：停止该链，不发第二次请求修补。
- 无锚、短引不命中、长度越界：判废，不缝补。
- 银标不一致：不直接判错，证据不够留待裁。

## 关键决策标记

已收集 {len(markers)} 条模型短标记；下面最多展示 80 条，完整来源仍在运行目录：

```json
{json.dumps(marker_preview, ensure_ascii=False, indent=2)}
```

来源：Codex
"""
    write_text(report_dir / "方法复盘.md", method)
    return {"report_dir": rel(report_dir), "summary": summary}


def zip_tree(source_dir: Path, target: Path, *, include: Callable[[Path], bool] | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(p for p in source_dir.rglob("*") if p.is_file() and p.name != ".DS_Store"):
            if include is not None and not include(file):
                continue
            archive.write(file, arcname=str(file.relative_to(source_dir)))


def stage_pack(ctx: RunContext) -> dict[str, Any]:
    run_id = str(ctx.batch["run_id"])
    report_dir = REPORTS_DIR / run_id
    if not report_dir.is_dir():
        raise ZBatchError("打包前缺报告目录")
    semantic_attestation = verify_semantic_attestation(ctx.run_dir)
    provenance = verify_provenance_snapshot(ctx.run_dir)
    imported = verify_materialized_import(ctx.run_dir, ctx.batch)
    imported_thin = verify_materialized_thin_import(ctx.run_dir, ctx.batch)
    out_dir = OUTBOX_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    report_zip = out_dir / f"{run_id}_report.zip"
    audit_zip = out_dir / f"{run_id}_audit.zip"
    zip_tree(report_dir, report_zip)
    zip_tree(ctx.run_dir, audit_zip)
    packages = []
    for path, role in [(report_zip, "notion_report"), (audit_zip, "local_audit")]:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
        if bad is not None:
            raise ZBatchError(f"zip 校验失败：{path}：{bad}")
        packages.append({
            "role": role,
            "path": rel(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "zip_test": "ok",
        })
    manifest = {
        "run_id": run_id,
        "created_at": now_iso(),
        "packages": packages,
        "notion_parent_page_id": "409fe87655b542b6813c2a0b567fba27",
        "upload_status": "pending",
        "provenance": provenance,
        "imported_verified_stage": imported,
        "imported_thin_stage": imported_thin,
        "semantic_attestation": semantic_attestation,
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest


def register_intake(args: argparse.Namespace) -> dict[str, Any]:
    source = root_path(args.path)
    registered_path = source
    if args.copy:
        destination = INTAKE_DIR / "raw" / args.batch / args.item / source.name
        if destination.exists():
            raise ZBatchError(f"收件目标已存在，拒绝覆盖：{destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        registered_path = destination
    fingerprint = tree_fingerprint(registered_path)
    manifest = {
        "batch": args.batch,
        "item": args.item,
        "kind": args.kind,
        "registered_at": now_iso(),
        "source_path": rel(source),
        "registered_path": rel(registered_path),
        "copied": bool(args.copy),
        "fingerprint": fingerprint,
        "provenance": args.provenance or "未填写",
    }
    target = INTAKE_DIR / "manifests" / f"{args.batch}_{args.item}_{args.kind}.json"
    if target.exists() and not args.replace:
        raise ZBatchError(f"登记单已存在，拒绝覆盖：{target}；确需更新加 --replace")
    write_json(target, manifest)
    return {"manifest": rel(target), **manifest}


def create_provenance_snapshot(run_dir: Path, batch: dict[str, Any], provider: dict[str, Any]) -> dict[str, Any]:
    """保存开跑代码和钉死文件，后续升级不会覆盖本次证据。"""
    provenance_dir = run_dir / "provenance"
    manifest_path = provenance_dir / "manifest.json"
    if manifest_path.exists():
        raise ZBatchError(f"来源快照已存在，拒绝覆盖：{manifest_path}")
    sources: list[Path] = [
        Path(__file__).resolve(),
        root_path(batch["_config_path"]),
        root_path(provider["_config_path"]),
    ]
    if batch.get("intake_manifest"):
        sources.append(root_path(batch["intake_manifest"]))
    sources.extend(root_path(value) for value in batch.get("spec_snapshots") or [])
    sources.extend(root_path(value) for value in (batch.get("prompts") or {}).values())
    unique_sources: list[Path] = []
    seen_sources: set[str] = set()
    for source in sources:
        source_rel = rel(source)
        if source_rel in seen_sources:
            continue
        seen_sources.add(source_rel)
        unique_sources.append(source)
    rows: list[dict[str, Any]] = []
    for source in unique_sources:
        source_rel = rel(source)
        destination = (
            provenance_dir / "runner_zbatch.py"
            if source == Path(__file__).resolve()
            else provenance_dir / "pinned" / source_rel
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        rows.append({
            "source": source_rel,
            "snapshot": rel(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        })
    manifest = {
        "created_at": now_iso(),
        "expected_files": len(unique_sources),
        "expected_sources": sorted(seen_sources),
        "files": rows,
    }
    write_json(manifest_path, manifest)
    return manifest


def verify_provenance_snapshot(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "provenance" / "manifest.json"
    if not manifest_path.is_file():
        raise ZBatchError("打包前缺来源快照清单")
    manifest = read_json(manifest_path)
    config_snapshot = read_json(run_dir / "config_snapshot.json")
    batch = config_snapshot.get("batch") if isinstance(config_snapshot.get("batch"), dict) else {}
    provider = config_snapshot.get("provider") if isinstance(config_snapshot.get("provider"), dict) else {}
    expected_sources = {
        rel(Path(__file__).resolve()),
        str(batch.get("_config_path") or ""),
        str(provider.get("_config_path") or ""),
        str(batch.get("intake_manifest") or ""),
        *(str(value) for value in batch.get("spec_snapshots") or []),
        *(str(value) for value in (batch.get("prompts") or {}).values()),
    }
    expected_sources.discard("")
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise ZBatchError("来源快照清单 files 不是数组")
    row_sources = {str(row.get("source")) for row in rows if isinstance(row, dict)}
    if (
        len(rows) != len(expected_sources)
        or manifest.get("expected_files") != len(expected_sources)
        or set(manifest.get("expected_sources") or []) != expected_sources
        or row_sources != expected_sources
    ):
        raise ZBatchError("来源快照清单缺行、多行或来源集合漂移")
    checked = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ZBatchError("来源快照清单行非法")
        path = root_path(str(row.get("snapshot") or ""))
        if not path.is_file() or sha256_file(path) != row.get("sha256"):
            raise ZBatchError(f"来源快照漂移：{path}")
        checked += 1
    if checked == 0:
        raise ZBatchError("来源快照清单为空")
    return {"status": "pass", "files": checked, "manifest": rel(manifest_path)}


def verify_materialized_import(run_dir: Path, batch: dict[str, Any]) -> dict[str, Any]:
    source_run_id = str(batch.get("import_verified_run") or "").strip()
    if not source_run_id:
        return {"status": "not_used"}
    manifest_path = run_dir / "imports" / "verified_source.json"
    if not manifest_path.is_file():
        raise ZBatchError("导入批缺 verified_source.json")
    manifest = read_json(manifest_path)
    if manifest.get("source_run_id") != source_run_id:
        raise ZBatchError("导入来源运行编号漂移")
    copied_dir = run_dir / "02_verify"
    fingerprint = tree_fingerprint(copied_dir)
    if fingerprint != manifest.get("copied_verify_fingerprint"):
        raise ZBatchError("导入后的核锚工件发生漂移")
    current_source = verify_verified_run_import(source_run_id, batch)
    if current_source != manifest.get("source_verification"):
        raise ZBatchError("导入源在复制后发生漂移")
    return {"status": "pass", "source_run_id": source_run_id, "fingerprint": fingerprint}


def materialize_verified_import(run_dir: Path, batch: dict[str, Any], *, resume: bool) -> dict[str, Any]:
    source_run_id = str(batch.get("import_verified_run") or "").strip()
    if not source_run_id:
        return {"status": "not_used"}
    if resume:
        return verify_materialized_import(run_dir, batch)
    source_verification = verify_verified_run_import(source_run_id, batch)
    source_dir = RUNS_DIR / source_run_id / "02_verify"
    destination = run_dir / "02_verify"
    if destination.exists():
        raise ZBatchError(f"导入目标已存在，拒绝覆盖：{destination}")
    shutil.copytree(source_dir, destination)
    manifest = {
        "created_at": now_iso(),
        "source_run_id": source_run_id,
        "source_verification": source_verification,
        "copied_verify_fingerprint": tree_fingerprint(destination),
    }
    write_json(run_dir / "imports" / "verified_source.json", manifest)
    return {"status": "imported", **manifest}


def verify_materialized_thin_import(run_dir: Path, batch: dict[str, Any]) -> dict[str, Any]:
    source_run_id = str(batch.get("import_thin_run") or "").strip()
    if not source_run_id:
        return {"status": "not_used"}
    manifest_path = run_dir / "imports" / "thin_source.json"
    if not manifest_path.is_file():
        raise ZBatchError("导入批缺 thin_source.json")
    manifest = read_json(manifest_path)
    if manifest.get("source_run_id") != source_run_id:
        raise ZBatchError("导入压薄来源运行编号漂移")
    copied_dir = run_dir / "03_thin"
    fingerprint = tree_fingerprint(copied_dir)
    if fingerprint != manifest.get("copied_thin_fingerprint"):
        raise ZBatchError("导入后的压薄工件发生漂移")
    current_source = verify_thin_run_import(source_run_id, batch)
    if current_source != manifest.get("source_verification"):
        raise ZBatchError("压薄导入源在复制后发生漂移")
    return {"status": "pass", "source_run_id": source_run_id, "fingerprint": fingerprint}


def materialize_thin_import(run_dir: Path, batch: dict[str, Any], *, resume: bool) -> dict[str, Any]:
    source_run_id = str(batch.get("import_thin_run") or "").strip()
    if not source_run_id:
        return {"status": "not_used"}
    if resume:
        return verify_materialized_thin_import(run_dir, batch)
    source_verification = verify_thin_run_import(source_run_id, batch)
    source_dir = RUNS_DIR / source_run_id / "03_thin"
    destination = run_dir / "03_thin"
    if destination.exists():
        raise ZBatchError(f"压薄导入目标已存在，拒绝覆盖：{destination}")
    shutil.copytree(source_dir, destination)
    manifest = {
        "created_at": now_iso(),
        "source_run_id": source_run_id,
        "source_verification": source_verification,
        "copied_thin_fingerprint": tree_fingerprint(destination),
    }
    write_json(run_dir / "imports" / "thin_source.json", manifest)
    return {"status": "imported", **manifest}


def initialize_run(batch: dict[str, Any], provider: dict[str, Any], pre: dict[str, Any], *, resume: bool) -> RunContext:
    run_dir = RUNS_DIR / str(batch["run_id"])
    if run_dir.exists() and not resume:
        meaningful = [p for p in run_dir.iterdir() if p.name != ".DS_Store"]
        if meaningful:
            raise ZBatchError(f"运行目录已存在：{run_dir}；续跑请加 --resume")
    run_dir.mkdir(parents=True, exist_ok=True)
    current_snapshot = {"batch": batch, "provider": provider}
    snapshot_path = run_dir / "config_snapshot.json"
    if snapshot_path.exists():
        if not resume:
            raise ZBatchError(f"运行配置快照已存在：{snapshot_path}")
        if read_json(snapshot_path) != current_snapshot:
            raise ZBatchError("续跑配置与开跑快照不一致；拒绝在旧运行上混入新配置")
    else:
        write_json(snapshot_path, current_snapshot)
        create_provenance_snapshot(run_dir, batch, provider)
    if resume and not (run_dir / "provenance" / "manifest.json").is_file():
        raise ZBatchError("续跑缺开跑时来源快照，拒绝继续")
    materialize_verified_import(run_dir, batch, resume=resume)
    materialize_thin_import(run_dir, batch, resume=resume)
    if not (run_dir / "preflight.json").exists():
        write_json(run_dir / "preflight.json", pre)
    return RunContext(batch, provider, run_dir)


def update_run_manifest(ctx: RunContext, *, status: str, stage: str | None = None, error: str | None = None) -> None:
    path = ctx.run_dir / "run_manifest.json"
    data = read_json(path) if path.is_file() else {
        "run_id": ctx.batch.get("run_id"),
        "started_at": now_iso(),
        "stages_completed": [],
    }
    data["updated_at"] = now_iso()
    data["status"] = status
    data["calls_made"] = ctx.calls_made
    data["max_calls"] = ctx.max_calls
    if stage and stage not in data["stages_completed"]:
        data["stages_completed"].append(stage)
    if error:
        data["error"] = error
    write_json(path, data)


def resolve_stages(batch: dict[str, Any], stages_override: str | None) -> list[str]:
    configured_stages = list(batch.get("stages") or [])
    if not stages_override:
        return configured_stages
    requested = [value.strip() for value in stages_override.split(",") if value.strip()]
    extra = [stage for stage in requested if stage not in configured_stages]
    if extra:
        raise ZBatchError(f"--stages 不能越出批次白名单：{extra}")
    stages = [stage for stage in configured_stages if stage in requested]
    if stages != requested:
        raise ZBatchError("--stages 必须保持批次既定顺序，不能倒序运行")
    return stages


def run_pipeline(config_path: Path, *, resume: bool, stages_override: str | None = None) -> dict[str, Any]:
    batch, provider = load_configs(config_path)
    stages = resolve_stages(batch, stages_override)
    allowed_stages = {
        "extract",
        "classify",
        "verify",
        "thin",
        "fold",
        "answer",
        "compare",
        "review",
        "report",
        "pack",
    }
    unknown = [stage for stage in stages if stage not in allowed_stages]
    if unknown:
        raise ZBatchError(f"未知阶段：{unknown}")
    api_stages = {"extract", "thin", "fold", "answer", "compare"}
    pre = preflight(config_path, require_key=bool(set(stages) & api_stages))
    if pre["preflight"] != "pass":
        raise ZBatchError("预演未通过，拒绝创建 API 运行")
    ctx = initialize_run(batch, provider, pre, resume=resume)
    chapters = load_chapters(
        root_path(batch["book_dir"]),
        int(batch["chapter_start"]),
        int(batch["chapter_end"]),
    )
    results: dict[str, Any] = {}
    update_run_manifest(ctx, status="running")
    try:
        for stage in stages:
            print(f"[{now_iso()}] stage={stage}", flush=True)
            if stage == "extract":
                result = stage_extract(ctx, chapters, resume=resume)
            elif stage == "classify":
                result = stage_classify(ctx, chapters)
            elif stage == "verify":
                result = stage_verify(ctx, chapters)
            elif stage == "thin":
                result = stage_thin(ctx, chapters, resume=resume)
            elif stage == "fold":
                result = stage_fold(ctx, chapters, resume=resume)
            elif stage == "answer":
                result = stage_answer(ctx, chapters, resume=resume)
            elif stage == "compare":
                result = stage_compare(ctx, resume=resume)
            elif stage == "review":
                result = stage_review(ctx)
            elif stage == "report":
                result = stage_report(ctx)
            elif stage == "pack":
                result = stage_pack(ctx)
            else:  # pragma: no cover
                raise ZBatchError(stage)
            results[stage] = result
            update_run_manifest(ctx, status="running", stage=stage)
        update_run_manifest(ctx, status="completed")
    except Exception as exc:
        update_run_manifest(ctx, status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    return {
        "run_id": batch.get("run_id"),
        "run_dir": rel(ctx.run_dir),
        "calls_made": ctx.calls_made,
        "max_calls": ctx.max_calls,
        "results": results,
    }


def status_for(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    if not run_dir.is_dir():
        raise ZBatchError(f"找不到运行：{run_id}")
    manifest = read_optional_json(run_dir / "run_manifest.json")
    return {
        "run_id": run_id,
        "manifest": manifest,
        "usage": usage_summary(run_dir),
        "report_dir": rel(REPORTS_DIR / run_id) if (REPORTS_DIR / run_id).is_dir() else None,
        "outbox_dir": rel(OUTBOX_DIR / run_id) if (OUTBOX_DIR / run_id).is_dir() else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Z 批弱模型提取流水线")
    sub = parser.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight", help="零调用预演")
    pre.add_argument("--config", required=True)

    run = sub.add_parser("run", help="执行批次")
    run.add_argument("--config", required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--stages", help="逗号分隔的阶段覆盖")

    register = sub.add_parser("register", help="登记入站材料或报告")
    register.add_argument("--kind", choices=["material", "report"], required=True)
    register.add_argument("--batch", required=True)
    register.add_argument("--item", required=True)
    register.add_argument("--path", required=True)
    register.add_argument("--provenance")
    register.add_argument("--copy", action="store_true")
    register.add_argument("--replace", action="store_true")

    status = sub.add_parser("status", help="查看运行状态")
    status.add_argument("--run-id", required=True)

    attest = sub.add_parser("attest", help="登记团队语义审查签收")
    attest.add_argument("--run-id", required=True)
    attest.add_argument("--reviewer", required=True)
    attest.add_argument("--decision", choices=["pass", "block"], required=True)
    attest.add_argument("--review-file", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(root_path(args.config), require_key=False)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["preflight"] == "pass" else 2
        if args.command == "run":
            result = run_pipeline(root_path(args.config), resume=args.resume, stages_override=args.stages)
        elif args.command == "register":
            result = register_intake(args)
        elif args.command == "status":
            result = status_for(args.run_id)
        elif args.command == "attest":
            result = attest_review(args)
        else:  # pragma: no cover
            raise ZBatchError(f"未知命令：{args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ZBatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
