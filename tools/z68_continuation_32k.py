#!/usr/bin/env python3
"""第68道续令：仅放宽 max_tokens 到 32000，续跑第5/13/19章。

第3/4章只复用上一轮唯一成功样张；旧运行目录、默认合同和现役件均不回写。
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import z59_entity_supply_pilot as z59
import z68_revised_request_pilot as z68
from zbatch_modules import api_transport, candidate_envelope, neutral_extract, stage_sampling
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
PRIOR_RUN = ROOT / "runs/Z68_X01_修正版请求体裸考_五靶章_v1.0_20260720"
PRIOR_HARD_STOP_SHA256 = "c211c294b1f80e19cef5c30b85c3c9879232ae7ce76229bbafbed7facb136e74"
PRIOR_TOOL_SHA256 = "d0855f240807992058ee0797070286cbbbddbbe34ddb89855b432ebc7f1ce28b"
REUSED_CHAPTERS = (3, 4)
CALLED_CHAPTERS = (5, 13, 19)
ALL_CHAPTERS = REUSED_CHAPTERS + CALLED_CHAPTERS
OLD_MAX_TOKENS = 16000
NEW_MAX_TOKENS = 32000
PROFILE = "z68_continuation_32k_v1"
MAX_NETWORK_ATTEMPTS = 5
RUN_LOCAL_CONTRACT = "provenance/sensenova_stage_sampling_z68_32k_v1.json"


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(dict(row), ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def deep_diff_paths(left: Any, right: Any, prefix: str = "$") -> list[str]:
    if type(left) is not type(right):
        return [prefix]
    if isinstance(left, dict):
        keys = sorted(set(left) | set(right))
        result: list[str] = []
        for key in keys:
            child = f"{prefix}.{key}"
            if key not in left or key not in right:
                result.append(child)
            else:
                result.extend(deep_diff_paths(left[key], right[key], child))
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [prefix]
        result = []
        for index, (old, new) in enumerate(zip(left, right, strict=True)):
            result.extend(deep_diff_paths(old, new, f"{prefix}[{index}]"))
        return result
    return [] if left == right else [prefix]


def assert_prior_run() -> dict[str, Any]:
    if z68.sha256_file(PRIOR_RUN / "hard_stop.json") != PRIOR_HARD_STOP_SHA256:
        raise ZBatchError("第68道原始硬停单漂移")
    if z68.sha256_file(ROOT / "tools/z68_revised_request_pilot.py") != PRIOR_TOOL_SHA256:
        raise ZBatchError("第68道原始旁路工具漂移")
    manifest = z68.read_json(PRIOR_RUN / "run_manifest.json")
    hard_stop = z68.read_json(PRIOR_RUN / "hard_stop.json")
    if manifest.get("status") != "hard_stop" or manifest.get("model_api_calls") != 2:
        raise ZBatchError("第68道原始运行清单不再是两章完成后的硬停态")
    if hard_stop.get("completed_chapters") != [3, 4] or hard_stop.get("next_chapter") != 5:
        raise ZBatchError("第68道原始硬停章序漂移")
    for chapter in REUSED_CHAPTERS:
        meta = z68.read_json(
            PRIOR_RUN / f"responses/neutral_extract/ch{chapter:04d}_meta.json"
        )
        request = z68.read_json(
            PRIOR_RUN / f"requests/neutral_extract/ch{chapter:04d}_request.json"
        )
        if meta.get("finish_reason") != "stop":
            raise ZBatchError(f"第{chapter}章旧样张不是正常 stop")
        if request.get("body", {}).get("max_tokens") != OLD_MAX_TOKENS:
            raise ZBatchError(f"第{chapter}章旧样张上限不是16000")
        z68.artifact_receipt(PRIOR_RUN, chapter)
    return {
        "hard_stop_sha256": PRIOR_HARD_STOP_SHA256,
        "tool_sha256": PRIOR_TOOL_SHA256,
        "tree_fingerprint": z68.tree_fingerprint(PRIOR_RUN),
    }


def prior_prepared_body(chapter: int) -> dict[str, Any]:
    if chapter not in ALL_CHAPTERS:
        raise ZBatchError(f"章次不在第68道五靶章：{chapter}")
    body = z68.read_json(PRIOR_RUN / f"prepared_requests/ch{chapter:04d}.json")
    if body.get("max_tokens") != OLD_MAX_TOKENS:
        raise ZBatchError(f"第{chapter}章冻结请求上限不是16000")
    return body


def continued_body(chapter: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if chapter not in CALLED_CHAPTERS:
        raise ZBatchError(f"第68道续令不调用第{chapter}章")
    old = prior_prepared_body(chapter)
    new = copy.deepcopy(old)
    new["max_tokens"] = NEW_MAX_TOKENS
    paths = deep_diff_paths(old, new)
    if paths != ["$.max_tokens"]:
        raise ZBatchError(f"第{chapter}章32k实例混入额外变化：{paths}")
    return new, {
        "chapter": chapter,
        "source": f"{PRIOR_RUN.relative_to(ROOT).as_posix()}/prepared_requests/ch{chapter:04d}.json",
        "old_body_sha256": z68.canonical_sha(old),
        "new_body_sha256": z68.canonical_sha(new),
        "changed_paths": paths,
        "old_max_tokens": OLD_MAX_TOKENS,
        "new_max_tokens": NEW_MAX_TOKENS,
        "messages_equal": old["messages"] == new["messages"],
        "messages_sha256": z68.canonical_sha(old["messages"]),
        "unchanged_top_level_fields": sorted(set(old) - {"max_tokens"}),
        "prohibited_request_marker_hits": z68.request_has_prohibited_input(new),
    }


def build_run_local_contract(path: Path) -> dict[str, Any]:
    raw = z68.read_json(z68.SAMPLING_CONTRACT)
    raw["contract_version"] = "z68-continuation-32k-v1"
    raw["profiles"][PROFILE] = {
        "status": "approved_transport_reference",
        "note": "第68道续令独立运行投影；只改neutral_extract max_tokens，不接默认链。",
        "stages": {
            "neutral_extract": {
                "temperature": 0.2,
                "max_tokens": NEW_MAX_TOKENS,
                "n": 1,
                "reasoning_effort": "medium",
                "response_format": {"type": "json_object"},
                "status": "approved_transport_reference",
            }
        },
    }
    z68.write_json(path, raw)
    return raw


def load_bundle(run_dir: Path) -> stage_sampling.StageContractBundle:
    return stage_sampling.load_contract_bundle(run_dir / RUN_LOCAL_CONTRACT, profile=PROFILE)


def assert_body_matches_32k_contract(body: Mapping[str, Any], run_dir: Path) -> None:
    bundle = load_bundle(run_dir)
    rebuilt = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=copy.deepcopy(body["messages"]),
        contract=bundle.stage("neutral_extract"),
    )
    if rebuilt != body:
        raise ZBatchError("32k请求体不能由本轮运行合同逐字段复现")


def copy_prior_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for chapter in REUSED_CHAPTERS:
        for group, relative in (
            ("model_json", f"01_extract/model_json/ch{chapter:04d}.json"),
            ("events", f"01_extract/events/ch{chapter:04d}.json"),
            ("program_audits", f"01_extract/program_audits/ch{chapter:04d}.json"),
        ):
            source = PRIOR_RUN / relative
            target = run_dir / relative
            receipt = z68.copy_input(source, target)
            receipt["reuse_kind"] = group
            copied.append(receipt)
        for relative in (
            f"requests/neutral_extract/ch{chapter:04d}_request.json",
            f"responses/neutral_extract/ch{chapter:04d}_raw.json",
            f"responses/neutral_extract/ch{chapter:04d}_meta.json",
        ):
            copied.append(z68.copy_input(PRIOR_RUN / relative, run_dir / "reused_16k" / relative))
    return copied


def core_artifact_receipt(run_dir: Path, chapter: int) -> dict[str, str]:
    paths = {
        "model_json_sha256": run_dir / f"01_extract/model_json/ch{chapter:04d}.json",
        "events_sha256": run_dir / f"01_extract/events/ch{chapter:04d}.json",
        "program_audit_sha256": run_dir / f"01_extract/program_audits/ch{chapter:04d}.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ZBatchError(f"第{chapter}章复用核心工件不完整：{missing}")
    return {name: z68.sha256_file(path) for name, path in paths.items()}


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    run_dir.mkdir(parents=True)
    prior = assert_prior_run()
    protected = z68.assert_protected()
    outbox_before = z68.tree_fingerprint(z68.OUTBOX)
    build_run_local_contract(run_dir / RUN_LOCAL_CONTRACT)
    rows: list[dict[str, Any]] = []
    for chapter in CALLED_CHAPTERS:
        body, diff = continued_body(chapter)
        assert_body_matches_32k_contract(body, run_dir)
        target = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        z68.write_json(target, body)
        rows.append(
            {
                **diff,
                "prepared_request": target.relative_to(run_dir).as_posix(),
                "prepared_file_sha256": z68.sha256_file(target),
            }
        )

    input_receipts: list[dict[str, Any]] = []
    for relative in (
        "inputs/chapters",
        "inputs/evidence_catalogs",
        "inputs/baseline_events",
    ):
        source_dir = PRIOR_RUN / relative
        for source in sorted(source_dir.glob("*")):
            input_receipts.append(z68.copy_input(source, run_dir / relative / source.name))
    input_receipts.append(
        z68.copy_input(
            PRIOR_RUN / "inputs/baseline_usage.jsonl",
            run_dir / "inputs/baseline_usage.jsonl",
        )
    )
    input_receipts.append(
        z68.copy_input(
            z68.CURRENT_122,
            run_dir / "inputs/current_formal_records_122.json",
        )
    )
    reuse_receipts = copy_prior_artifacts(run_dir)
    provenance: list[dict[str, Any]] = []
    for source, target in (
        (Path(__file__), run_dir / "provenance/z68_continuation_32k.py"),
        (z68.SAMPLING_CONTRACT, run_dir / "provenance/active_sampling_contract_16k.json"),
        (PRIOR_RUN / "preflight.json", run_dir / "provenance/prior_preflight.json"),
        (PRIOR_RUN / "hard_stop.json", run_dir / "provenance/prior_hard_stop.json"),
        (PRIOR_RUN / "run_manifest.json", run_dir / "provenance/prior_run_manifest.json"),
    ):
        provenance.append(z68.copy_input(source, target))
    prior_usage = [
        row
        for row in z68.read_jsonl(PRIOR_RUN / "usage.jsonl")
        if row.get("case_id") in {"ch0003", "ch0004"}
    ]
    if len(prior_usage) != 2:
        raise ZBatchError("第3/4章旧usage不是两行")
    write_jsonl(run_dir / "reused_16k/usage.jsonl", prior_usage)

    preflight = {
        "schema_version": "z68-continuation-32k-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": z68.now_iso(),
        "task": "第68道续令：第5章思考耗尽无正文参数兼容修复轮",
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "reused_chapters": list(REUSED_CHAPTERS),
        "called_chapters": list(CALLED_CHAPTERS),
        "all_scorecard_chapters": list(ALL_CHAPTERS),
        "single_variable": {"field": "max_tokens", "old": OLD_MAX_TOKENS, "new": NEW_MAX_TOKENS},
        "sampling": {
            "model": "deepseek-v4-flash",
            "temperature": 0.2,
            "max_tokens": NEW_MAX_TOKENS,
            "n": 1,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "medium",
        },
        "request_policy": {
            "messages_byte_semantics_equal_prior_frozen_requests": True,
            "logical_samples_per_called_chapter": 1,
            "rerun_for_selection": False,
            "global_network_attempt_budget": MAX_NETWORK_ATTEMPTS,
            "hard_stop_on_new_failure": True,
            "gold_in_request": False,
            "chatgpt_demo_in_request": False,
        },
        "rows": rows,
        "prior_run": prior,
        "protected": protected,
        "outbox_before": outbox_before,
        "inputs": input_receipts,
        "reused_artifacts": reuse_receipts,
        "provenance": provenance,
        "condition_note": "第3/4章复用16k且stop未触顶；第5/13/19章为32k，成绩旁注上限不同批。",
    }
    z68.write_json(run_dir / "preflight.json", preflight)
    z68.write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z68-continuation-32k-run-manifest-v2",
            "run_id": run_dir.name,
            "status": "prepared",
            "new_model_api_calls": 0,
            "reused_model_outputs": 2,
            "transport": transport_receipt(run_dir),
        },
    )
    verify_prepared(run_dir, require_zero_call=True)
    return preflight


def verify_prepared(run_dir: Path, *, require_zero_call: bool) -> dict[str, Any]:
    preflight = z68.read_json(run_dir / "preflight.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第68道续令预演状态不是零调用通过")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("第68道续令预演调用账不为0")
    if require_zero_call and any(
        (run_dir / name).exists() for name in ("call_attempts.jsonl", "usage.jsonl")
    ):
        raise ZBatchError("第68道续令零调用预演出现运输账")
    z68.assert_protected()
    if z68.tree_fingerprint(z68.OUTBOX) != preflight["outbox_before"]:
        raise ZBatchError("第68道续令预演期间outbox漂移")
    if z68.tree_fingerprint(PRIOR_RUN) != preflight["prior_run"]["tree_fingerprint"]:
        raise ZBatchError("第68道原始硬停目录被改写")
    rows = {int(row["chapter"]): row for row in preflight["rows"]}
    checks: list[dict[str, Any]] = []
    for chapter in CALLED_CHAPTERS:
        expected, diff = continued_body(chapter)
        observed = z68.read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        passed = (
            observed == expected
            and rows[chapter]["changed_paths"] == ["$.max_tokens"]
            and rows[chapter]["messages_equal"]
            and not z68.request_has_prohibited_input(observed)
        )
        assert_body_matches_32k_contract(observed, run_dir)
        if not passed or diff["changed_paths"] != ["$.max_tokens"]:
            raise ZBatchError(f"第{chapter}章32k请求不满足单变量")
        checks.append(
            {
                "chapter": chapter,
                "passed": passed,
                "changed_paths": ["$.max_tokens"],
                "effective_max_tokens": observed["max_tokens"],
                "messages_sha256": z68.canonical_sha(observed["messages"]),
                "body_canonical_sha256": z68.canonical_sha(observed),
            }
        )
    for chapter in REUSED_CHAPTERS:
        current = core_artifact_receipt(run_dir, chapter)
        prior = core_artifact_receipt(PRIOR_RUN, chapter)
        if current["model_json_sha256"] != prior["model_json_sha256"]:
            raise ZBatchError(f"第{chapter}章复用model_json漂移")
        if current["events_sha256"] != prior["events_sha256"]:
            raise ZBatchError(f"第{chapter}章复用events漂移")
        if current["program_audit_sha256"] != prior["program_audit_sha256"]:
            raise ZBatchError(f"第{chapter}章复用程序审计漂移")
    receipt = {
        "schema_version": "z68-continuation-32k-prepared-verification-v1",
        "status": "pass",
        "require_zero_call": require_zero_call,
        "model_api_calls_at_preflight": 0,
        "network_attempts_at_preflight": 0,
        "checks": checks,
        "preflight_sha256": z68.sha256_file(run_dir / "preflight.json"),
        "run_local_contract_sha256": z68.sha256_file(run_dir / RUN_LOCAL_CONTRACT),
    }
    z68.write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def attempt_count(run_dir: Path) -> int:
    path = run_dir / "call_attempts.jsonl"
    return len(z68.read_jsonl(path)) if path.is_file() else 0


def known_response_usage(run_dir: Path) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for path in sorted((run_dir / "responses/neutral_extract").glob("ch*_raw.json")):
        raw_data: Any
        try:
            raw_data = z68.read_json(path)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raw_data = None
        raw = raw_data if isinstance(raw_data, dict) else {}
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        details = (
            usage.get("completion_tokens_details")
            if isinstance(usage.get("completion_tokens_details"), dict)
            else {}
        )
        choices = raw.get("choices") if isinstance(raw.get("choices"), list) else []
        first = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        item = {
            "case_id": path.stem.removesuffix("_raw"),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "finish_reason": first.get("finish_reason"),
            "content_characters": len(str(message.get("content") or "")),
            "reasoning_characters": len(str(message.get("reasoning_content") or "")),
            "raw_response_sha256": z68.sha256_file(path),
            "response_json_object": isinstance(raw_data, dict),
            "usage_present": isinstance(raw.get("usage"), dict),
        }
        rows.append(item)
        for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens"):
            totals[key] += item[key]
    attempts = attempt_count(run_dir)
    responses_with_usage = sum(int(row["usage_present"]) for row in rows)
    return {
        "network_attempts": attempts,
        "persisted_responses": len(rows),
        "responses_with_usage": responses_with_usage,
        "attempts_without_persisted_usage": max(0, attempts - responses_with_usage),
        "rows": rows,
        "totals": dict(totals),
        "boundary": "只合计已持久化且自带usage的回包；HTTP错误无usage时不推断计费为0。",
    }


def transport_receipt(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "call_attempts.jsonl"
    attempts = z68.read_jsonl(path) if path.is_file() else []
    allowed_cases = [f"ch{chapter:04d}" for chapter in CALLED_CHAPTERS]
    logical_order: list[str] = []
    per_case_attempts: Counter[str] = Counter()
    call_sequence: list[dict[str, Any]] = []
    for call_number, row in enumerate(attempts, 1):
        case_id = row.get("case_id")
        if row.get("call_number") != call_number:
            raise ZBatchError("运输账 call_number 不连续")
        if row.get("max_calls") != MAX_NETWORK_ATTEMPTS:
            raise ZBatchError("运输账总尝试预算不是5")
        if row.get("stage") != "neutral_extract" or case_id not in allowed_cases:
            raise ZBatchError("运输账混入范围外阶段或章次")
        if case_id not in logical_order:
            expected_case = allowed_cases[len(logical_order)]
            if case_id != expected_case:
                raise ZBatchError("运输账章次没有按5→13→19进入")
            logical_order.append(str(case_id))
        elif logical_order[-1] != case_id:
            raise ZBatchError("运输账跨章后又回到旧章")
        per_case_attempts[str(case_id)] += 1
        if row.get("attempt") != per_case_attempts[str(case_id)]:
            raise ZBatchError("运输账单章 attempt 不连续")
        if per_case_attempts[str(case_id)] > 3:
            raise ZBatchError("运输账单章超过既有3次运输上限")
        call_sequence.append(
            {
                "call_number": call_number,
                "case_id": case_id,
                "attempt": row.get("attempt"),
                "stage": row.get("stage"),
                "request_sha256": row.get("request_sha256"),
            }
        )
    return {
        "max_network_attempts": MAX_NETWORK_ATTEMPTS,
        "actual_network_attempts": len(attempts),
        "logical_case_order": logical_order,
        "logical_samples_started": {case_id: 1 for case_id in logical_order},
        "attempts_by_case": dict(per_case_attempts),
        "call_sequence": call_sequence,
        "usage": known_response_usage(run_dir),
    }


def combine_usage(run_dir: Path) -> list[dict[str, Any]]:
    reused = z68.read_jsonl(run_dir / "reused_16k/usage.jsonl")
    current = z68.read_jsonl(run_dir / "usage.jsonl")
    if len(reused) != 2 or len(current) != 3:
        raise ZBatchError("五章合并usage不是2条复用＋3条新调用")
    rows = reused + current
    write_jsonl(run_dir / "combined_usage.jsonl", rows)
    return rows


def new_artifact_receipt(run_dir: Path, chapter: int) -> dict[str, Any]:
    return z68.artifact_receipt(run_dir, chapter)


def run(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    verify_prepared(run_dir, require_zero_call=True)
    if attempt_count(run_dir):
        raise ZBatchError("第68道续令已有调用账，拒绝复跑或补跑")
    preflight = z68.read_json(run_dir / "preflight.json")
    bundle = load_bundle(run_dir)
    transport = api_transport.ApiTransport.from_bundle(
        bundle,
        run_dir=run_dir,
        max_calls=MAX_NETWORK_ATTEMPTS,
    )
    completed: list[int] = []
    receipts: dict[str, Any] = {}
    try:
        for chapter in CALLED_CHAPTERS:
            body = z68.read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
            assert_body_matches_32k_contract(body, run_dir)
            result = transport.call(
                stage="neutral_extract",
                case_id=f"ch{chapter:04d}",
                messages=body["messages"],
            )
            model_json = candidate_envelope.parse_json_content(result.content)
            catalog_doc = z68.read_json(
                run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json"
            )
            materialized, audit = neutral_extract.process_model_data(
                model_json,
                chapter=chapter,
                catalog=catalog_doc["entries"],
            )
            z68.write_json(run_dir / f"01_extract/model_json/ch{chapter:04d}.json", model_json)
            z68.write_json(run_dir / f"01_extract/events/ch{chapter:04d}.json", materialized)
            z68.write_json(run_dir / f"01_extract/program_audits/ch{chapter:04d}.json", audit)
            request_record = z68.read_json(
                run_dir / f"requests/neutral_extract/ch{chapter:04d}_request.json"
            )
            if request_record.get("body") != body:
                raise ZBatchError(f"第{chapter}章实际上线请求与32k准备件不一致")
            receipts[str(chapter)] = {
                **new_artifact_receipt(run_dir, chapter),
                "event_count": len(materialized["events"]),
                "anchor_reference_count": audit["anchor_reference_count"],
                "effective_max_tokens": request_record["body"]["max_tokens"],
            }
            completed.append(chapter)
    except Exception as exc:
        transport = transport_receipt(run_dir)
        hard_stop = {
            "schema_version": "z68-continuation-32k-hard-stop-v1",
            "status": "hard_stop_no_repair_no_rerun",
            "at": z68.now_iso(),
            "reused_chapters": list(REUSED_CHAPTERS),
            "completed_new_chapters": completed,
            "next_chapter": next(
                (chapter for chapter in CALLED_CHAPTERS if chapter not in completed), None
            ),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "transport": transport,
            "protected_after": z68.assert_protected(),
            "prior_run_unchanged": (
                z68.tree_fingerprint(PRIOR_RUN) == preflight["prior_run"]["tree_fingerprint"]
            ),
            "outbox_unchanged": z68.tree_fingerprint(z68.OUTBOX) == preflight["outbox_before"],
        }
        z68.write_json(run_dir / "hard_stop.json", hard_stop)
        z68.write_json(
            run_dir / "run_manifest.json",
            {
                "schema_version": "z68-continuation-32k-run-manifest-v2",
                "run_id": run_dir.name,
                "status": "hard_stop",
                "new_usable_model_outputs": len(completed),
                "reused_model_outputs": 2,
                "transport": transport,
            },
        )
        raise
    combine_usage(run_dir)
    transport = transport_receipt(run_dir)
    metrics = {
        "schema_version": "z68-continuation-32k-run-metrics-v1",
        "status": "completed_candidate_only_mixed_caps",
        "reused_chapters": list(REUSED_CHAPTERS),
        "new_chapters_completed": completed,
        "all_scorecard_chapters": list(ALL_CHAPTERS),
        "chapter_max_tokens": {"3": 16000, "4": 16000, "5": 32000, "13": 32000, "19": 32000},
        "transport": transport,
        "new_receipts": receipts,
    }
    z68.write_json(run_dir / "01_extract/metrics.json", metrics)
    z68.write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z68-continuation-32k-run-manifest-v2",
            "run_id": run_dir.name,
            "status": "completed_candidate_only_mixed_caps",
            "new_usable_model_outputs": 3,
            "reused_model_outputs": 2,
            "transport": transport,
        },
    )
    return metrics


def usage_for_chapters(path: Path) -> dict[str, Any]:
    return z68.usage_for_chapters(path, ALL_CHAPTERS)


def formal_record_summary(record: Mapping[str, Any]) -> str:
    record_type = str(record.get("type") or "")
    if record_type == "A":
        return str(record.get("delta") or "")
    if record_type == "B":
        return f"{record.get('trigger_condition') or ''}：{record.get('trigger_action') or ''}"
    if record_type == "C":
        return f"{record.get('reader_expectation') or ''}；{record.get('payoff_test') or ''}"
    if record_type == "D":
        parts = [
            str(record.get(key) or "")
            for key in ("condition", "result", "rule", "scope", "exception")
        ]
        return "；".join(part for part in parts if part)
    return json.dumps(dict(record), ensure_ascii=False, sort_keys=True)


def formal_as_event(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": record.get("id"),
        "event": formal_record_summary(record),
        "anchors": copy.deepcopy(record.get("anchors") or []),
        "formal_record": copy.deepcopy(dict(record)),
    }


def analyze(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    manifest = z68.read_json(run_dir / "run_manifest.json")
    if manifest.get("status") != "completed_candidate_only_mixed_caps":
        raise ZBatchError("第68道续令五章未齐，禁止冒充成绩")
    preflight = z68.read_json(run_dir / "preflight.json")
    if z68.tree_fingerprint(z68.OUTBOX) != preflight["outbox_before"]:
        raise ZBatchError("第68道续令分析时outbox漂移")
    if z68.tree_fingerprint(PRIOR_RUN) != preflight["prior_run"]["tree_fingerprint"]:
        raise ZBatchError("第68道原始硬停目录被改写")

    chapter_rows = [z68.chapter_mechanics(run_dir, chapter) for chapter in ALL_CHAPTERS]
    event_total = sum(row["event_count"] for row in chapter_rows)
    anchor_total = sum(row["anchor_reference_count"] for row in chapter_rows)
    outside_total = sum(row["outside_catalog_anchor_count"] for row in chapter_rows)
    explicit_total = sum(row["explicit_subject_events"] for row in chapter_rows)
    vague_total = sum(row["vague_predicate_hit_events"] for row in chapter_rows)
    ordered_total = sum(row["anchor_order_compliant_events"] for row in chapter_rows)
    dedup_total = sum(row["anchor_deduplicated_events"] for row in chapter_rows)
    baseline_events = {
        str(chapter): len(
            z68.read_json(run_dir / f"inputs/baseline_events/ch{chapter:04d}.json")["events"]
        )
        for chapter in ALL_CHAPTERS
    }
    candidate_events = {str(row["chapter"]): row["event_count"] for row in chapter_rows}
    baseline_usage = usage_for_chapters(run_dir / "inputs/baseline_usage.jsonl")
    candidate_usage = usage_for_chapters(run_dir / "combined_usage.jsonl")
    baseline_tokens = int(baseline_usage["totals"].get("total_tokens") or 0)
    candidate_tokens = int(candidate_usage["totals"].get("total_tokens") or 0)
    scorecard = {
        "schema_version": "z68-continuation-32k-ten-mechanical-metrics-v1",
        "status": "completed_candidate_only",
        "condition": "连续正文＋目录双视图·32k上限",
        "batch_note": "第3/4章复用16k且stop未触顶；第5/13/19章为32k，上限不同批。",
        "chapter_max_tokens": {"3": 16000, "4": 16000, "5": 32000, "13": 32000, "19": 32000},
        "metric_policy": {
            "explicit_subject": "去掉一个不超过30字的前置时间／条件短语后，事件句必须以预写人物或明确群体词表开头",
            "vague_predicate": "只作词面命中观察，不自动判错",
            "invalid_anchor": "模型原始anchor_id不在同章冻结目录的引用数／全部引用数",
        },
        "ten_metrics": {
            "01_JSON合法章率": {"numerator": 5, "denominator": 5, "rate": 1.0},
            "02_event_id连续章率": {
                "numerator": sum(int(row["event_id_contiguous"]) for row in chapter_rows),
                "denominator": 5,
                "rate": sum(int(row["event_id_contiguous"]) for row in chapter_rows) / 5,
            },
            "03_目录外锚数": outside_total,
            "04_无效锚率": outside_total / anchor_total if anchor_total else 0.0,
            "05_锚排序合规率": ordered_total / event_total if event_total else 0.0,
            "06_锚去重合规率": dedup_total / event_total if event_total else 0.0,
            "07_显式主语率": explicit_total / event_total if event_total else 0.0,
            "08_空泛谓词命中率": vague_total / event_total if event_total else 0.0,
            "09_事件数": {
                "candidate_total": event_total,
                "baseline_total": sum(baseline_events.values()),
                "candidate_by_chapter": candidate_events,
                "baseline_by_chapter": baseline_events,
            },
            "10_token成本对第57道": {
                "candidate": candidate_usage,
                "baseline_reused_from_z56_z57": baseline_usage,
                "total_token_delta": candidate_tokens - baseline_tokens,
                "total_token_delta_rate": (
                    (candidate_tokens - baseline_tokens) / baseline_tokens if baseline_tokens else None
                ),
            },
        },
        "subject_lexicon": {
            str(chapter): list(z68.SUBJECT_LEXICON[chapter]) for chapter in ALL_CHAPTERS
        },
        "vague_predicate_terms": list(z68.VAGUE_PREDICATE_TERMS),
        "chapters": chapter_rows,
    }
    z68.write_json(run_dir / "analysis/机械十项成绩单.json", scorecard)

    current = z68.read_json(run_dir / "inputs/current_formal_records_122.json")["records"]
    diffs: dict[str, Any] = {}
    for chapter in ALL_CHAPTERS:
        formal = [
            formal_as_event(row) for row in current if row.get("_source_chapter") == chapter
        ]
        candidate = z68.read_json(run_dir / f"01_extract/events/ch{chapter:04d}.json")["events"]
        draft = z59.match_events(formal, candidate)
        draft["chapter"] = chapter
        draft["formal_record_count"] = len(formal)
        draft["candidate_event_count"] = len(candidate)
        diffs[str(chapter)] = draft
    diff_report = {
        "schema_version": "z68-continuation-current122-diff-draft-v1",
        "status": "mechanical_pairing_requires_row_level_semantic_review",
        "warning": "配对只按锚交集和文本相似度起草；每条现役记录必须另留语义判词。",
        "chapters": diffs,
    }
    z68.write_json(run_dir / "analysis/现役正式记录逐条diff_机械配对草稿.json", diff_report)

    chapter3_events = z68.read_json(run_dir / "01_extract/events/ch0003.json")["events"]
    lexical = z59.score_chapter3(chapter3_events)
    lexical["schema_version"] = "z68-continuation-chapter3-gold-lexical-precheck-v1"
    lexical["condition"] = "连续正文＋目录双视图·32k上限（第3章沿用16k stop样张）"
    lexical["status"] = "lexical_precheck_not_semantic_verdict"
    lexical["warning"] = "严格与影子最终分数必须经14条逐条语义复核。"
    z68.write_json(run_dir / "analysis/第3章金标词法预检.json", lexical)
    referenced = {
        row["candidate_event_id_run_local_only"]
        for row in lexical["rows"]
        if row.get("candidate_event_id_run_local_only")
    }
    overflow = {
        "schema_version": "z68-continuation-overflow-draft-v1",
        "status": "pending_adjudication_do_not_self_label",
        "events": [row for row in chapter3_events if row["event_id"] not in referenced],
    }
    z68.write_json(run_dir / "analysis/第3章待判溢出_机械草稿.json", overflow)
    summary = {
        "schema_version": "z68-continuation-analysis-summary-v1",
        "status": "mechanical_complete_semantic_review_pending",
        "scorecard_sha256": z68.sha256_file(run_dir / "analysis/机械十项成绩单.json"),
        "current122_diff_draft_sha256": z68.sha256_file(
            run_dir / "analysis/现役正式记录逐条diff_机械配对草稿.json"
        ),
        "chapter3_lexical_precheck_sha256": z68.sha256_file(
            run_dir / "analysis/第3章金标词法预检.json"
        ),
        "overflow_draft_sha256": z68.sha256_file(
            run_dir / "analysis/第3章待判溢出_机械草稿.json"
        ),
    }
    z68.write_json(run_dir / "analysis/机械分析汇总.json", summary)
    return summary


def verify(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    prepared = verify_prepared(run_dir, require_zero_call=False)
    manifest = z68.read_json(run_dir / "run_manifest.json")
    transport = transport_receipt(run_dir)
    checks: list[dict[str, Any]] = [
        {"name": "prepared_requests", "passed": prepared["status"] == "pass"},
        {"name": "protected", "passed": bool(z68.assert_protected())},
    ]
    preflight = z68.read_json(run_dir / "preflight.json")
    checks.extend(
        [
            {
                "name": "outbox_unchanged",
                "passed": z68.tree_fingerprint(z68.OUTBOX) == preflight["outbox_before"],
            },
            {
                "name": "prior_run_unchanged",
                "passed": (
                    z68.tree_fingerprint(PRIOR_RUN) == preflight["prior_run"]["tree_fingerprint"]
                ),
            },
            {
                "name": "network_attempt_budget",
                "passed": transport["actual_network_attempts"] <= MAX_NETWORK_ATTEMPTS,
                "value": transport["actual_network_attempts"],
            },
            {
                "name": "terminal_manifest_transport_receipt",
                "passed": manifest.get("transport") == transport,
            },
        ]
    )
    if manifest.get("status") == "completed_candidate_only_mixed_caps":
        checks.append(
            {
                "name": "called_chapter_order_and_uniqueness",
                "passed": transport["logical_case_order"]
                == [f"ch{chapter:04d}" for chapter in CALLED_CHAPTERS]
                and transport["logical_samples_started"]
                == {f"ch{chapter:04d}": 1 for chapter in CALLED_CHAPTERS},
            }
        )
        for chapter in ALL_CHAPTERS:
            checks.append(
                {
                    "name": f"chapter_{chapter}_events_and_audit",
                    "passed": all(
                        (
                            run_dir
                            / f"01_extract/{group}/ch{chapter:04d}.json"
                        ).is_file()
                        for group in ("model_json", "events", "program_audits")
                    ),
                }
            )
        for chapter in CALLED_CHAPTERS:
            actual = z68.read_json(
                run_dir / f"requests/neutral_extract/ch{chapter:04d}_request.json"
            )["body"]
            expected = z68.read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
            checks.append(
                {
                    "name": f"chapter_{chapter}_actual_request_32k_exact",
                    "passed": actual == expected and actual["max_tokens"] == NEW_MAX_TOKENS,
                }
            )
        for path in (
            run_dir / "combined_usage.jsonl",
            run_dir / "analysis/机械十项成绩单.json",
            run_dir / "analysis/现役正式记录逐条diff_机械配对草稿.json",
            run_dir / "analysis/第3章金标词法预检.json",
            run_dir / "analysis/第3章待判溢出_机械草稿.json",
            run_dir / "analysis/机械分析汇总.json",
        ):
            checks.append(
                {
                    "name": path.name,
                    "passed": path.is_file(),
                    "sha256": z68.sha256_file(path) if path.is_file() else None,
                }
            )
    failed = [row for row in checks if not row["passed"]]
    if failed:
        raise ZBatchError(f"第68道续令机械验收失败：{failed}")
    receipt = {
        "schema_version": "z68-continuation-32k-mechanical-verification-v1",
        "status": "pass",
        "run_status": manifest.get("status"),
        "checks": checks,
        "transport": transport,
    }
    z68.write_json(run_dir / "mechanical_verification.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "analyze", "verify"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args(argv)
    actions = {"prepare": prepare, "run": run, "analyze": analyze, "verify": verify}
    result = actions[args.action](args.run_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
