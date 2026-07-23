#!/usr/bin/env python3
"""Z00n 分类收权单变量入口。

相对 Z00m 只改一处：弱模型不再自报 ``coverage_audit``；程序从实际
``events`` 生成清点账并核对冻结证据 ID。运输参数、主控分类规则、五章齐套闸和
分类后核锚都继续沿用 Z00m/Z00l 的封存实现。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import zbatch  # noqa: E402
import z00l_classification_split as legacy  # noqa: E402
import z00m_classification_split as z00m  # noqa: E402
import z00n_event_audit as event_audit  # noqa: E402


EXPECTED_BATCH = "Z00n"
EXPECTED_ITEM = "X01"
EXPECTED_CHAPTER_RANGE = (6, 10)
EXPECTED_CHAPTERS = 5
EXPECTED_STAGES = ["event_extract", "classify", "verify"]
EXPECTED_MODEL = "deepseek-v4-flash"
EXPECTED_TEMPERATURE = 0.2
EXPECTED_REASONING_EFFORT = "medium"
EXPECTED_EXTRACT_MAX_TOKENS = 16000
EXPECTED_N = 1
EXPECTED_PROMPT_SHA256 = "91270576f44986bc0c2610bedb93e28fca90000688bb0f5a40caa72a594c3c7f"
EXPECTED_OLD_PROMPT_SHA256 = "9beb1bfd83863cc39b3e899a706a9dc60fb901ef47547ae859bda2720a9a411c"
EXPECTED_RULES_SHA256 = "95ded675da3dac0fb3a7102c64175f1102eeea23af269f7cbed285d8cb21b804"
EXPECTED_CHECKER_SHA256 = "a74b0f660796eb803a746e925a0c7a99b39e3dc62c3f28d618ba961e63a89e7d"
EXPECTED_Z00L_ADAPTER_SHA256 = "7a28e1c151b0d0f21aede010eeace5ba3cc54f1b8003e06869397e516f8504ec"
EXPECTED_Z00M_ADAPTER_SHA256 = "913f1abf502567dd4235df1e657574d2f32d12f2cd8b1de0cb4e1483e599db95"
DEFAULT_PROMPT_SHA256 = "b5f30ab1e3e9cae7870db6bf2a951448d391981c0cfb257bd577686bd0a2c6b9"

OLD_PROMPT_PATH = "work/zbatch_prompts/candidates/extract_event_only_v1.0.md"
NEW_PROMPT_PATH = "work/zbatch_prompts/candidates/extract_event_only_no_self_audit_v1.1.md"
RULES_PATH = "work/zbatch_prompts/candidates/main_control_classification_rules_v1.0.md"
CHECKER_PATH = "tools/z00n_event_audit.py"

_REMOVED_AUDIT_OBJECT = (
    '  "coverage_audit": {\n'
    '    "status": "emitted|none",\n'
    '    "event_ids": [],\n'
    '    "reason": "说明已按原文顺序检查哪些可继续读取的信息，为什么产出或不产出"\n'
    "  },\n"
)
_REMOVED_AUDIT_RULE = (
    "`coverage_audit.event_ids` 必须与 `events` 的 ID 完全一致、顺序一致。"
    "全章没有合格事件时可以输出空数组，但理由不能只写“无”。\n\n"
)


def prompt_change_is_exact() -> tuple[bool, str]:
    """证明新 Prompt 只删除模型自报清点的对象和对应说明。"""
    old_path = zbatch.root_path(OLD_PROMPT_PATH)
    new_path = zbatch.root_path(NEW_PROMPT_PATH)
    if not old_path.is_file() or not new_path.is_file():
        return False, "prompt_missing"
    old = old_path.read_text(encoding="utf-8")
    expected = old.replace(_REMOVED_AUDIT_OBJECT, "", 1).replace(_REMOVED_AUDIT_RULE, "", 1)
    expected = expected.rstrip("\n") + "\n"
    actual = new_path.read_text(encoding="utf-8")
    return actual == expected, zbatch.sha256_bytes(actual.encode("utf-8"))


def z00n_preflight(config_path: Path, *, require_key: bool = False) -> dict[str, Any]:
    """在通用零调用预演上钉死 Z00n 的单变量和 Z00m 运输合同。"""
    result = zbatch.preflight(config_path, require_key=require_key)
    batch, provider = zbatch.load_configs(config_path)
    checks = list(result.get("checks") or [])

    zbatch.add_check(checks, "z00n_batch", batch.get("batch_id") == EXPECTED_BATCH, batch.get("batch_id"))
    zbatch.add_check(checks, "z00n_item", batch.get("item_id") == EXPECTED_ITEM, batch.get("item_id"))
    zbatch.add_check(
        checks,
        "z00n_chapter_range",
        (batch.get("chapter_start"), batch.get("chapter_end"), batch.get("expected_chapters"))
        == (*EXPECTED_CHAPTER_RANGE, EXPECTED_CHAPTERS),
        [batch.get("chapter_start"), batch.get("chapter_end"), batch.get("expected_chapters")],
    )
    zbatch.add_check(checks, "z00n_stages", batch.get("stages") == EXPECTED_STAGES, batch.get("stages"))
    zbatch.add_check(checks, "z00n_model", provider.get("model") == EXPECTED_MODEL, provider.get("model"))
    zbatch.add_check(
        checks,
        "z00n_temperature",
        float(provider.get("temperature", -1)) == EXPECTED_TEMPERATURE,
        provider.get("temperature"),
    )
    zbatch.add_check(
        checks,
        "z00n_reasoning_effort",
        provider.get("reasoning_effort") == EXPECTED_REASONING_EFFORT,
        provider.get("reasoning_effort"),
    )
    zbatch.add_check(checks, "z00n_n", provider.get("n") == EXPECTED_N, provider.get("n"))
    extract_max = (provider.get("max_tokens_by_stage") or {}).get("extract")
    zbatch.add_check(
        checks,
        "z00n_extract_max_tokens",
        extract_max == EXPECTED_EXTRACT_MAX_TOKENS,
        extract_max,
    )

    prompts = batch.get("prompts") if isinstance(batch.get("prompts"), dict) else {}
    zbatch.add_check(
        checks,
        "z00n_prompt_paths",
        prompts == {"event_extract": NEW_PROMPT_PATH, "classifier_rules": RULES_PATH},
        prompts,
    )
    for check_name, relative_path, expected_sha in [
        ("z00n_prompt_sha", NEW_PROMPT_PATH, EXPECTED_PROMPT_SHA256),
        ("z00n_old_prompt_unchanged", OLD_PROMPT_PATH, EXPECTED_OLD_PROMPT_SHA256),
        ("z00n_rules_unchanged", RULES_PATH, EXPECTED_RULES_SHA256),
        ("z00n_checker_sha", CHECKER_PATH, EXPECTED_CHECKER_SHA256),
        ("z00l_adapter_unchanged", "tools/z00l_classification_split.py", EXPECTED_Z00L_ADAPTER_SHA256),
        ("z00m_adapter_unchanged", "tools/z00m_classification_split.py", EXPECTED_Z00M_ADAPTER_SHA256),
        ("default_extract_unchanged", "work/zbatch_prompts/extract_v1.3.md", DEFAULT_PROMPT_SHA256),
    ]:
        path = zbatch.root_path(relative_path)
        actual_sha = zbatch.sha256_file(path) if path.is_file() else "missing"
        zbatch.add_check(checks, check_name, actual_sha == expected_sha, actual_sha)

    exact_change, change_detail = prompt_change_is_exact()
    zbatch.add_check(checks, "z00n_prompt_single_variable_diff", exact_change, change_detail)
    run_id = str(batch.get("run_id") or "")
    zbatch.add_check(checks, "z00n_run_id", run_id.startswith("Z00n_"), run_id)
    outbox_path = zbatch.OUTBOX_DIR / run_id
    zbatch.add_check(checks, "z00n_outbox_absent", not outbox_path.exists(), zbatch.rel(outbox_path))
    snapshots = [str(value) for value in batch.get("spec_snapshots") or []]
    zbatch.add_check(
        checks,
        "z00n_d_mod_not_connected",
        not any("zbatch_modules/" in value for value in snapshots),
        snapshots,
    )

    result["checks"] = checks
    result["preflight"] = "pass" if all(item.get("ok") for item in checks) else "fail"
    result["model_calls"] = 0
    result["z00n_contract"] = {
        "single_variable": "删除模型自报coverage_audit；程序从events生成清点账并核锚",
        "transport": {
            "source": "tools/z00m_classification_split.py:Z00mRunContext",
            "extract_max_tokens": EXPECTED_EXTRACT_MAX_TOKENS,
            "reasoning_effort": EXPECTED_REASONING_EFFORT,
            "n": EXPECTED_N,
        },
        "classifier_rules_unchanged": True,
        "five_parsed_files_before_classification": True,
        "classification_model_calls": 0,
        "semantic_coverage_claimed_by_program": False,
        "d_mod_modules_connected": False,
    }
    return result


def _run_legacy(
    function: Callable[..., dict[str, Any]],
    *args: Any,
    audit_run_dir: Path | None = None,
) -> dict[str, Any]:
    """当前调用内接上 Z00n 预演、Z00m 运输和程序清点器，随后全部还原。"""
    original_preflight = legacy.z00l_preflight
    original_context = zbatch.RunContext
    original_validator = legacy.event_envelope_reasons

    def audited_validator(data: Any, chapter: int, catalog: list[dict[str, Any]]) -> list[str]:
        reasons, audit = event_audit.audit_event_envelope(data, chapter, catalog)
        if audit_run_dir is not None:
            zbatch.write_json(
                audit_run_dir / "01_event_extract" / "program_audits" / f"ch{chapter:04d}.json",
                audit,
            )
        return reasons

    legacy.z00l_preflight = z00n_preflight
    zbatch.RunContext = z00m.Z00mRunContext
    legacy.event_envelope_reasons = audited_validator
    try:
        return function(*args)
    finally:
        legacy.z00l_preflight = original_preflight
        zbatch.RunContext = original_context
        legacy.event_envelope_reasons = original_validator


def verify_complete_event_set(run_dir: Path, batch: dict[str, Any]) -> dict[str, Any]:
    """五章齐套后，再逐章重算程序清点账并核对展开锚。"""
    base = z00m.verify_complete_event_set(run_dir, batch)
    audit_shas: dict[str, str] = {}
    for chapter in range(int(batch["chapter_start"]), int(batch["chapter_end"]) + 1):
        parsed_path = run_dir / "01_event_extract" / "parsed" / f"ch{chapter:04d}.json"
        data = zbatch.read_json(parsed_path)
        if set(data) != event_audit.ROOT_KEYS:
            raise zbatch.ZBatchError(f"第 {chapter} 章仍带模型自报清点或外壳漂移")
        catalog_data = zbatch.read_json(
            run_dir / "01_event_extract" / "evidence_catalogs" / f"ch{chapter:04d}.json"
        )
        catalog = catalog_data.get("entries") or []
        raw_shape = {
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
        reasons, expected_audit = event_audit.audit_event_envelope(raw_shape, chapter, catalog)
        if reasons:
            raise zbatch.ZBatchError(f"第 {chapter} 章程序重算清点失败：{reasons}")
        audit_path = run_dir / "01_event_extract" / "program_audits" / f"ch{chapter:04d}.json"
        if not audit_path.is_file():
            raise zbatch.ZBatchError(f"第 {chapter} 章缺程序清点账")
        actual_audit = zbatch.read_json(audit_path)
        if actual_audit != expected_audit or actual_audit.get("status") != "pass":
            raise zbatch.ZBatchError(f"第 {chapter} 章程序清点账与events不一致")
        audit_shas[str(chapter)] = zbatch.sha256_file(audit_path)

    return {
        **base,
        "program_audits": len(audit_shas),
        "program_audit_sha256_by_chapter": audit_shas,
        "semantic_coverage_claimed": False,
    }


def extract_events(config_path: Path) -> dict[str, Any]:
    batch, _ = zbatch.load_configs(config_path)
    run_dir = zbatch.RUNS_DIR / str(batch.get("run_id"))
    result = _run_legacy(legacy.extract_events, config_path, audit_run_dir=run_dir)
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
        report = report_path.read_text(encoding="utf-8").replace(
            "# Z00l 程序核锚报告", "# Z00n 程序核锚报告", 1
        )
        zbatch.write_text(report_path, report)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Z00n 程序清点单变量入口")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight", help="零调用预演")
    pre.add_argument("--config", required=True)
    extract = sub.add_parser("extract", help="抽中性事件并由程序清点")
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
            result = z00n_preflight(config_path, require_key=False)
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
