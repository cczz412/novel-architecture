#!/usr/bin/env python3
"""第70道：事件句压缩合同单变量五靶章旁路。

五章基线都由第68道 ``build_instantiated_body`` 现场生成，再统一把
``max_tokens`` 设为 32000。候选请求只在 system 强合同第6条后加一行；
预演只写隔离工件，不发网络请求。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import z68_revised_request_pilot as z68
from zbatch_modules import api_transport, candidate_envelope, neutral_extract, stage_sampling
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAPTERS = (3, 4, 5, 13, 19)
RUN_ID = "Z70_X01_事件句压缩合同_五靶章_v1.0_20260721"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
SOURCE_RUN = ROOT / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720"
SOURCE_INPUTS = SOURCE_RUN / "inputs"
SOURCE_INPUTS_FINGERPRINT = {
    "files": 17,
    "bytes": 404520,
    "sha256": "e355299e169df2d9d2a22e9cd61c938cb4164944e07329e6154cbe32351053af",
}

MAX_TOKENS = 32000
BASELINE_MAX_TOKENS = MAX_TOKENS
MAX_NETWORK_ATTEMPTS = 7
PROFILE = "z70_compression_contract_32k_v1"
RUN_LOCAL_CONTRACT = Path("provenance/sensenova_stage_sampling_z70_32k_v1.json")
RUN_CLAIM = Path("run_claim.json")

STRONG_CONTRACT_CLAUSE_6 = (
    "6. 当前行动使用正文在当前场景中的姓名；回忆中的原人物经历要写清“某人从某人的记忆中得知”或"
    "“某人的记忆显示”，不得混淆当前行动者与记忆主体。"
)
COMPRESSION_CONTRACT_CLAUSE = (
    "每条事件句中，时间、前提／条件、结果三类要素凡原文明示者必须写入本条事件句，不得省略、不得把多条独立事实并成一句压缩；"
    "原文未明示的要素留空，禁止编造"
)


def write_json(path: Path, value: Any) -> None:
    z68.write_json(path, value)


def write_json_atomic(path: Path, value: Any) -> None:
    """同目录临时文件落盘后原子替换，避免中断留下半份状态。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    return z68.read_json(path)


def deep_diff_paths(left: Any, right: Any, prefix: str = "$") -> list[str]:
    if type(left) is not type(right):
        return [prefix]
    if isinstance(left, dict):
        result: list[str] = []
        for key in sorted(set(left) | set(right)):
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


def assert_source_inputs() -> dict[str, Any]:
    observed = z68.tree_fingerprint(SOURCE_INPUTS)
    if observed != SOURCE_INPUTS_FINGERPRINT:
        raise ZBatchError(
            f"Z68C冻结输入漂移：预期 {SOURCE_INPUTS_FINGERPRINT}，实际 {observed}"
        )
    for chapter in TARGET_CHAPTERS:
        source_chapters = sorted((SOURCE_INPUTS / "chapters").glob(f"{chapter:04d}_*.txt"))
        if len(source_chapters) != 1:
            raise ZBatchError(f"Z68C第{chapter}章冻结正文数不是1")
        if z68.sha256_file(source_chapters[0]) != z68.sha256_file(z68.chapter_file(chapter)):
            raise ZBatchError(f"Z68实例化正文与Z68C第{chapter}章冻结输入不同")
        frozen_catalog = SOURCE_INPUTS / f"evidence_catalogs/ch{chapter:04d}.json"
        if z68.sha256_file(frozen_catalog) != z68.sha256_file(z68.source_catalog(chapter)):
            raise ZBatchError(f"Z68实例化目录与Z68C第{chapter}章冻结输入不同")
    return observed


def request_has_prohibited_input(body: Mapping[str, Any]) -> list[str]:
    return z68.request_has_prohibited_input(body)


def build_baseline_body(chapter: int) -> tuple[dict[str, Any], dict[str, Any]]:
    source, source_diff = z68.build_instantiated_body(chapter)
    if source.get("max_tokens") != 16000:
        raise ZBatchError(f"第{chapter}章Z68实例化请求不是16000基底")
    body = copy.deepcopy(source)
    body["max_tokens"] = MAX_TOKENS
    changed = deep_diff_paths(source, body)
    if changed != ["$.max_tokens"]:
        raise ZBatchError(f"第{chapter}章32k基线混入额外变化：{changed}")
    if request_has_prohibited_input(body):
        raise ZBatchError(f"第{chapter}章32k基线夹入禁入材料")
    return body, {
        "chapter": chapter,
        "builder": "z68_revised_request_pilot.build_instantiated_body",
        "builder_mode": source_diff["mode"],
        "changed_paths_from_z68_instantiation": changed,
        "old_max_tokens": 16000,
        "new_max_tokens": MAX_TOKENS,
        "body_canonical_sha256": z68.canonical_sha(body),
    }


def remove_candidate_clause(system: str) -> str:
    inserted_line = "\n" + COMPRESSION_CONTRACT_CLAUSE
    if system.count(inserted_line) != 1:
        raise ZBatchError("候选合同原句行数不是1")
    return system.replace(inserted_line, "", 1)


def build_candidate_body(chapter: int) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline, baseline_diff = build_baseline_body(chapter)
    baseline_system = baseline["messages"][0]["content"]
    if baseline_system.count(STRONG_CONTRACT_CLAUSE_6) != 1:
        raise ZBatchError("基线system强合同第6条数量不是1")
    if COMPRESSION_CONTRACT_CLAUSE in baseline_system:
        raise ZBatchError("基线system已含候选合同原句")
    candidate = copy.deepcopy(baseline)
    candidate_system = baseline_system.replace(
        STRONG_CONTRACT_CLAUSE_6,
        STRONG_CONTRACT_CLAUSE_6 + "\n" + COMPRESSION_CONTRACT_CLAUSE,
        1,
    )
    candidate["messages"][0]["content"] = candidate_system
    changed = deep_diff_paths(baseline, candidate)
    if changed != ["$.messages[0].content"]:
        raise ZBatchError(f"候选请求混入多余字段变化：{changed}")
    if candidate_system.count(COMPRESSION_CONTRACT_CLAUSE) != 1:
        raise ZBatchError("候选合同原句不是唯一1次")
    if remove_candidate_clause(candidate_system) != baseline_system:
        raise ZBatchError("删除候选合同行后system不能逐字节还原基线")
    if request_has_prohibited_input(candidate):
        raise ZBatchError(f"第{chapter}章候选请求夹入禁入材料")
    return candidate, {
        "schema_version": "z70-request-diff-v1",
        "chapter": chapter,
        "baseline": baseline_diff,
        "changed_paths_baseline_to_candidate": changed,
        "insert_after": STRONG_CONTRACT_CLAUSE_6,
        "inserted_exact_line": COMPRESSION_CONTRACT_CLAUSE,
        "inserted_occurrences": candidate_system.count(COMPRESSION_CONTRACT_CLAUSE),
        "system_byte_equal_after_line_deletion": True,
        "baseline_body_canonical_sha256": z68.canonical_sha(baseline),
        "prepared_body_canonical_sha256": z68.canonical_sha(candidate),
        "unchanged_user_message": baseline["messages"][1] == candidate["messages"][1],
        "effective_max_tokens": candidate["max_tokens"],
    }


# 给测试和临时检查留下直观入口；两个名字不另走逻辑。
baseline_body = build_baseline_body
candidate_body = build_candidate_body


def build_run_local_contract(path: Path) -> dict[str, Any]:
    raw = read_json(z68.SAMPLING_CONTRACT)
    raw["contract_version"] = "z70-compression-contract-32k-v1"
    raw["profiles"][PROFILE] = {
        "status": "approved_transport_reference",
        "note": "第70道隔离运行投影；五章从一开始都是32k，不做8/16/32爬坡。",
        "stages": {
            "neutral_extract": {
                "temperature": 0.2,
                "max_tokens": MAX_TOKENS,
                "n": 1,
                "reasoning_effort": "medium",
                "response_format": {"type": "json_object"},
                "status": "approved_transport_reference",
            }
        },
    }
    write_json(path, raw)
    return raw


def load_bundle(run_dir: Path) -> stage_sampling.StageContractBundle:
    return stage_sampling.load_contract_bundle(run_dir / RUN_LOCAL_CONTRACT, profile=PROFILE)


def assert_body_matches_contract(body: Mapping[str, Any], run_dir: Path) -> None:
    bundle = load_bundle(run_dir)
    rebuilt = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=copy.deepcopy(body["messages"]),
        contract=bundle.stage("neutral_extract"),
    )
    if rebuilt != body:
        raise ZBatchError("Z70请求体不能由本轮32k运输合同逐字段复现")


def copy_frozen_inputs(run_dir: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for source in sorted(item for item in SOURCE_INPUTS.rglob("*") if item.is_file()):
        relative = source.relative_to(SOURCE_INPUTS)
        receipts.append(z68.copy_input(source, run_dir / "inputs" / relative))
    if z68.tree_fingerprint(run_dir / "inputs") != SOURCE_INPUTS_FINGERPRINT:
        raise ZBatchError("隔离run内冻结输入与Z68C源目录不等")
    return receipts


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    source_inputs = assert_source_inputs()
    protected = z68.assert_protected()
    outbox_before = z68.tree_fingerprint(z68.OUTBOX)
    run_dir.mkdir(parents=True)
    build_run_local_contract(run_dir / RUN_LOCAL_CONTRACT)

    rows: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        baseline, _ = build_baseline_body(chapter)
        prepared, diff = build_candidate_body(chapter)
        assert_body_matches_contract(baseline, run_dir)
        assert_body_matches_contract(prepared, run_dir)
        baseline_path = run_dir / f"baseline_requests/ch{chapter:04d}.json"
        prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        diff_path = run_dir / f"request_diffs/ch{chapter:04d}.json"
        write_json(baseline_path, baseline)
        write_json(prepared_path, prepared)
        write_json(diff_path, diff)
        rows.append(
            {
                "chapter": chapter,
                "baseline_request": baseline_path.relative_to(run_dir).as_posix(),
                "baseline_file_sha256": z68.sha256_file(baseline_path),
                "prepared_request": prepared_path.relative_to(run_dir).as_posix(),
                "prepared_file_sha256": z68.sha256_file(prepared_path),
                "diff": diff_path.relative_to(run_dir).as_posix(),
                "diff_file_sha256": z68.sha256_file(diff_path),
            }
        )

    input_receipts = copy_frozen_inputs(run_dir)
    provenance: list[dict[str, Any]] = []
    for source, target in (
        (Path(__file__), run_dir / "provenance/z70_compression_contract_pilot.py"),
        (ROOT / "tools/z68_revised_request_pilot.py", run_dir / "provenance/z68_revised_request_pilot.py"),
        (z68.SAMPLING_CONTRACT, run_dir / "provenance/active_sampling_contract_16k.json"),
        (SOURCE_RUN / "preflight.json", run_dir / "provenance/z68c_preflight.json"),
        (SOURCE_RUN / "run_manifest.json", run_dir / "provenance/z68c_run_manifest.json"),
    ):
        provenance.append(z68.copy_input(source, target))

    preflight = {
        "schema_version": "z70-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": z68.now_iso(),
        "task": "第70道事件句压缩合同单变量五靶章",
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "logical_samples_per_chapter": 1,
        "max_network_attempts": MAX_NETWORK_ATTEMPTS,
        "sampling": {
            "model": "deepseek-v4-flash",
            "temperature": 0.2,
            "max_tokens": MAX_TOKENS,
            "n": 1,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "medium",
        },
        "single_variable": {
            "location": "messages[0].content",
            "insert_after": "system强合同第6条",
            "inserted_exact_line": COMPRESSION_CONTRACT_CLAUSE,
        },
        "request_policy": {
            "all_chapters_built_from_z68_build_instantiated_body": True,
            "all_chapters_start_at_32000": True,
            "ramp_8000_16000_32000": False,
            "same_request_only_for_network_retry": True,
            "rerun_for_selection": False,
            "hard_stop_on_any_failure": True,
            "gold_in_request": False,
            "chatgpt_32_demo_in_request": False,
            "current_122_in_request": False,
        },
        "source_inputs": source_inputs,
        "copied_inputs": input_receipts,
        "protected": protected,
        "outbox_before": outbox_before,
        "rows": rows,
        "provenance": provenance,
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z70-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared",
            "model_api_calls": 0,
            "network_attempts": 0,
        },
    )
    verify_prepared(run_dir, require_zero_call=True)
    return preflight


def verify_prepared(run_dir: Path, *, require_zero_call: bool = False) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    manifest = read_json(run_dir / "run_manifest.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("Z70预演状态不是零调用通过")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("Z70预演调用账不为0")
    if require_zero_call:
        if manifest.get("status") != "prepared":
            raise ZBatchError("Z70不是可首次开跑的prepared状态")
        started = call_artifacts_present(run_dir)
        if started:
            raise ZBatchError(f"Z70零调用预演目录出现正式运行工件：{started}")
    if assert_source_inputs() != preflight["source_inputs"]:
        raise ZBatchError("Z70预演后Z68C冻结输入漂移")
    if z68.tree_fingerprint(run_dir / "inputs") != preflight["source_inputs"]:
        raise ZBatchError("Z70隔离输入不再等于Z68C冻结输入")
    z68.assert_protected()
    if z68.tree_fingerprint(z68.OUTBOX) != preflight["outbox_before"]:
        raise ZBatchError("Z70期间outbox漂移")
    for row in preflight.get("provenance") or []:
        source = ROOT / str(row["source"])
        target = Path(str(row["target"]))
        if (
            not source.is_file()
            or not target.is_file()
            or z68.sha256_file(source) != row["sha256"]
            or z68.sha256_file(target) != row["sha256"]
        ):
            raise ZBatchError(f"Z70来源保护件漂移：{row['source']}")

    checks: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        expected_baseline, _ = build_baseline_body(chapter)
        expected_prepared, expected_diff = build_candidate_body(chapter)
        baseline = read_json(run_dir / f"baseline_requests/ch{chapter:04d}.json")
        prepared = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        diff = read_json(run_dir / f"request_diffs/ch{chapter:04d}.json")
        passed = (
            baseline == expected_baseline
            and prepared == expected_prepared
            and diff == expected_diff
            and baseline["max_tokens"] == MAX_TOKENS
            and prepared["max_tokens"] == MAX_TOKENS
            and deep_diff_paths(baseline, prepared) == ["$.messages[0].content"]
            and remove_candidate_clause(prepared["messages"][0]["content"])
            == baseline["messages"][0]["content"]
            and not request_has_prohibited_input(prepared)
        )
        assert_body_matches_contract(baseline, run_dir)
        assert_body_matches_contract(prepared, run_dir)
        if not passed:
            raise ZBatchError(f"第{chapter}章baseline/prepared/diff不能机械重建")
        checks.append(
            {
                "chapter": chapter,
                "passed": True,
                "changed_paths": ["$.messages[0].content"],
                "effective_max_tokens": MAX_TOKENS,
                "system_byte_equal_after_line_deletion": True,
            }
        )
    receipt = {
        "schema_version": "z70-prepared-verification-v1",
        "status": "pass",
        "require_zero_call": require_zero_call,
        "checks": checks,
        "source_inputs_unchanged": True,
        "protected_unchanged": True,
        "outbox_unchanged": True,
    }
    write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def attempt_count(run_dir: Path) -> int:
    return len(z68.read_jsonl(run_dir / "call_attempts.jsonl"))


def call_artifacts_present(run_dir: Path) -> list[str]:
    """列出一切说明正式运行已经开始的工件。"""
    candidates = (
        run_dir / RUN_CLAIM,
        run_dir / "call_attempts.jsonl",
        run_dir / "usage.jsonl",
        run_dir / "requests",
        run_dir / "responses",
        run_dir / "01_extract",
        run_dir / "hard_stop.json",
    )
    return [path.relative_to(run_dir).as_posix() for path in candidates if path.exists()]


def acquire_run_claim(run_dir: Path) -> dict[str, Any]:
    """用 O_EXCL 抢整轮独占权；残留 claim 也禁止自动续跑。"""
    claim_path = run_dir / RUN_CLAIM
    claim = {
        "schema_version": "z70-run-claim-v1",
        "status": "claimed_do_not_resume",
        "claimed_at": z68.now_iso(),
        "pid": os.getpid(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(claim_path, flags, 0o600)
    except FileExistsError as exc:
        raise ZBatchError("Z70整轮运行权已被占用或曾中断，拒绝重复采样") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(claim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def transport_receipt(run_dir: Path) -> dict[str, Any]:
    attempts = z68.read_jsonl(run_dir / "call_attempts.jsonl")
    allowed = [f"ch{chapter:04d}" for chapter in TARGET_CHAPTERS]
    logical_order: list[str] = []
    attempts_by_case: Counter[str] = Counter()
    hashes_by_case: dict[str, set[str]] = {}
    for call_number, row in enumerate(attempts, 1):
        case_id = str(row.get("case_id") or "")
        if row.get("call_number") != call_number or row.get("max_calls") != MAX_NETWORK_ATTEMPTS:
            raise ZBatchError("Z70运输账序号或总尝试预算漂移")
        if row.get("stage") != "neutral_extract" or case_id not in allowed:
            raise ZBatchError("Z70运输账混入范围外阶段或章次")
        if case_id not in logical_order:
            if case_id != allowed[len(logical_order)]:
                raise ZBatchError("Z70章次没有按3→4→5→13→19进入")
            logical_order.append(case_id)
        elif logical_order[-1] != case_id:
            raise ZBatchError("Z70运输账跨章后又回到旧章")
        attempts_by_case[case_id] += 1
        if row.get("attempt") != attempts_by_case[case_id] or attempts_by_case[case_id] > 3:
            raise ZBatchError("Z70单章网络重试账不连续或超过3次")
        hashes_by_case.setdefault(case_id, set()).add(str(row.get("request_sha256") or ""))
    if len(attempts) > MAX_NETWORK_ATTEMPTS:
        raise ZBatchError("Z70网络尝试超过全局7次硬闸")
    same_request = all(len(values) == 1 for values in hashes_by_case.values())
    if not same_request:
        raise ZBatchError("Z70同章网络重试的请求不是同一body")
    return {
        "max_network_attempts": MAX_NETWORK_ATTEMPTS,
        "actual_network_attempts": len(attempts),
        "logical_case_order": logical_order,
        "logical_samples_started": {case_id: 1 for case_id in logical_order},
        "attempts_by_case": dict(attempts_by_case),
        "same_request_on_network_retries": same_request,
    }


def artifact_receipt(run_dir: Path, chapter: int) -> dict[str, str]:
    case_id = f"ch{chapter:04d}"
    paths = {
        "request_sha256": run_dir / f"requests/neutral_extract/{case_id}_request.json",
        "raw_response_sha256": run_dir / f"responses/neutral_extract/{case_id}_raw.json",
        "response_meta_sha256": run_dir / f"responses/neutral_extract/{case_id}_meta.json",
        "model_json_sha256": run_dir / f"01_extract/model_json/{case_id}.json",
        "events_sha256": run_dir / f"01_extract/events/{case_id}.json",
        "program_audit_sha256": run_dir / f"01_extract/program_audits/{case_id}.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ZBatchError(f"第{chapter}章运行工件不完整：{missing}")
    return {name: z68.sha256_file(path) for name, path in paths.items()}


def run(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    verify_prepared(run_dir, require_zero_call=True)
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest.get("status") != "prepared":
        raise ZBatchError(f"Z70当前状态不是prepared，拒绝重进run：{manifest.get('status')}")
    if attempt_count(run_dir):
        raise ZBatchError("Z70已有调用账，拒绝复跑或补跑")
    preflight = read_json(run_dir / "preflight.json")
    claim = acquire_run_claim(run_dir)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z70-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "running_do_not_resume",
            "usable_model_outputs": 0,
            "run_claim": claim,
        },
    )
    completed: list[int] = []
    receipts: dict[str, Any] = {}
    try:
        transport = api_transport.ApiTransport.from_bundle(
            load_bundle(run_dir), run_dir=run_dir, max_calls=MAX_NETWORK_ATTEMPTS
        )
        for chapter in TARGET_CHAPTERS:
            case_id = f"ch{chapter:04d}"
            prepared = read_json(run_dir / f"prepared_requests/{case_id}.json")
            assert_body_matches_contract(prepared, run_dir)
            result = transport.call(
                stage="neutral_extract", case_id=case_id, messages=prepared["messages"]
            )
            if result.request_record.get("body") != prepared:
                raise ZBatchError(f"第{chapter}章实际请求与prepared不等")
            actual = read_json(run_dir / f"requests/neutral_extract/{case_id}_request.json")
            if actual.get("body") != prepared:
                raise ZBatchError(f"第{chapter}章落盘实际请求与prepared不等")
            if result.finish_reason != "stop" or not result.content.strip():
                raise ZBatchError(f"第{chapter}章回包未 stop 或正文为空")
            model_json = candidate_envelope.parse_json_content(result.content)
            events = model_json.get("events")
            if not isinstance(events, list) or not events:
                raise ZBatchError(f"第{chapter}章events为空；立即硬停")
            catalog = read_json(run_dir / f"inputs/evidence_catalogs/{case_id}.json")["entries"]
            materialized, audit = neutral_extract.process_model_data(
                model_json, chapter=chapter, catalog=catalog
            )
            if audit.get("status") != "pass" or audit.get("missing_catalog_anchor_ids"):
                raise ZBatchError(f"第{chapter}章证据锚合同失败")
            write_json(run_dir / f"01_extract/model_json/{case_id}.json", model_json)
            write_json(run_dir / f"01_extract/events/{case_id}.json", materialized)
            write_json(run_dir / f"01_extract/program_audits/{case_id}.json", audit)
            receipts[str(chapter)] = {
                **artifact_receipt(run_dir, chapter),
                "event_count": len(events),
                "anchor_reference_count": audit["anchor_reference_count"],
                "outside_catalog_anchor_count": len(audit["missing_catalog_anchor_ids"]),
            }
            completed.append(chapter)
    except BaseException as exc:
        receipt = transport_receipt(run_dir)
        hard_stop = {
            "schema_version": "z70-hard-stop-v1",
            "status": "hard_stop_no_repair_no_rerun",
            "at": z68.now_iso(),
            "completed_chapters": completed,
            "next_chapter": next(
                (chapter for chapter in TARGET_CHAPTERS if chapter not in completed), None
            ),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "transport": receipt,
            "source_inputs_unchanged": assert_source_inputs() == preflight["source_inputs"],
            "protected_after": z68.assert_protected(),
            "outbox_unchanged": z68.tree_fingerprint(z68.OUTBOX) == preflight["outbox_before"],
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json_atomic(
            run_dir / "run_manifest.json",
            {
                "schema_version": "z70-run-manifest-v1",
                "run_id": run_dir.name,
                "status": "hard_stop",
                "usable_model_outputs": len(completed),
                "run_claim": claim,
                "transport": receipt,
            },
        )
        raise

    receipt = transport_receipt(run_dir)
    metrics = {
        "schema_version": "z70-run-metrics-v1",
        "status": "completed_candidate_only",
        "chapters_completed": completed,
        "logical_samples_per_chapter": 1,
        "chapter_max_tokens": {str(chapter): MAX_TOKENS for chapter in TARGET_CHAPTERS},
        "transport": receipt,
        "receipts": receipts,
    }
    write_json(run_dir / "01_extract/metrics.json", metrics)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z70-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "completed_candidate_only",
            "usable_model_outputs": len(completed),
            "run_claim": claim,
            "transport": receipt,
        },
    )
    return metrics


def _exact_artifact_names(path: Path, suffix: str) -> set[str]:
    return {item.name for item in path.glob(suffix) if item.is_file()}


def verify(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    prepared = verify_prepared(run_dir, require_zero_call=False)
    manifest = read_json(run_dir / "run_manifest.json")
    transport = transport_receipt(run_dir)
    preflight = read_json(run_dir / "preflight.json")
    checks: list[dict[str, Any]] = [
        {"name": "prepared_requests", "passed": prepared["status"] == "pass"},
        {"name": "source_inputs_unchanged", "passed": assert_source_inputs() == preflight["source_inputs"]},
        {"name": "protected_unchanged", "passed": bool(z68.assert_protected())},
        {"name": "outbox_unchanged", "passed": z68.tree_fingerprint(z68.OUTBOX) == preflight["outbox_before"]},
        {"name": "network_attempt_budget", "passed": transport["actual_network_attempts"] <= MAX_NETWORK_ATTEMPTS},
    ]

    if manifest.get("status") == "completed_candidate_only":
        expected_cases = [f"ch{chapter:04d}" for chapter in TARGET_CHAPTERS]
        claim = read_json(run_dir / RUN_CLAIM) if (run_dir / RUN_CLAIM).is_file() else None
        checks.append(
            {
                "name": "terminal_run_claim_pinned",
                "passed": claim is not None and manifest.get("run_claim") == claim,
            }
        )
        checks.append(
            {
                "name": "five_unique_logical_samples_in_order",
                "passed": transport["logical_case_order"] == expected_cases
                and transport["logical_samples_started"]
                == {case_id: 1 for case_id in expected_cases},
            }
        )
        expected_request_names = {f"{case_id}_request.json" for case_id in expected_cases}
        checks.append(
            {
                "name": "exactly_five_request_artifacts",
                "passed": _exact_artifact_names(
                    run_dir / "requests/neutral_extract", "*_request.json"
                )
                == expected_request_names,
            }
        )
        usage_rows = z68.read_jsonl(run_dir / "usage.jsonl")
        checks.append(
            {
                "name": "one_successful_sample_per_chapter",
                "passed": Counter(str(row.get("case_id")) for row in usage_rows)
                == Counter({case_id: 1 for case_id in expected_cases}),
            }
        )
        outside_total = 0
        for chapter in TARGET_CHAPTERS:
            case_id = f"ch{chapter:04d}"
            prepared_body = read_json(run_dir / f"prepared_requests/{case_id}.json")
            actual_body = read_json(
                run_dir / f"requests/neutral_extract/{case_id}_request.json"
            )["body"]
            meta = read_json(run_dir / f"responses/neutral_extract/{case_id}_meta.json")
            model_json = read_json(run_dir / f"01_extract/model_json/{case_id}.json")
            audit = read_json(run_dir / f"01_extract/program_audits/{case_id}.json")
            catalog = read_json(run_dir / f"inputs/evidence_catalogs/{case_id}.json")["entries"]
            reasons, rebuilt_audit = neutral_extract.audit_event_envelope(
                model_json, chapter, catalog
            )
            outside = len(rebuilt_audit["missing_catalog_anchor_ids"])
            outside_total += outside
            checks.extend(
                [
                    {
                        "name": f"{case_id}_actual_equals_prepared_32k",
                        "passed": actual_body == prepared_body
                        and actual_body["max_tokens"] == MAX_TOKENS,
                    },
                    {
                        "name": f"{case_id}_stop_nonempty_json_anchor_contract",
                        "passed": meta.get("finish_reason") == "stop"
                        and isinstance(model_json.get("events"), list)
                        and bool(model_json["events"])
                        and not reasons
                        and audit == rebuilt_audit
                        and audit.get("status") == "pass"
                        and outside == 0,
                    },
                ]
            )
            artifact_receipt(run_dir, chapter)
        checks.append({"name": "outside_catalog_anchor_total_zero", "passed": outside_total == 0, "value": outside_total})
        checks.append({"name": "terminal_transport_receipt", "passed": manifest.get("transport") == transport})
    elif manifest.get("status") == "hard_stop":
        hard_stop = read_json(run_dir / "hard_stop.json")
        completed = hard_stop.get("completed_chapters")
        next_chapter = hard_stop.get("next_chapter")
        completed_ok = (
            isinstance(completed, list)
            and completed == list(TARGET_CHAPTERS[: len(completed)])
        )
        expected_next = (
            TARGET_CHAPTERS[len(completed)]
            if completed_ok and len(completed) < len(TARGET_CHAPTERS)
            else None
        )
        completed_cases = [f"ch{chapter:04d}" for chapter in completed] if completed_ok else []
        allowed_started_orders = [completed_cases]
        if expected_next is not None:
            allowed_started_orders.append(completed_cases + [f"ch{expected_next:04d}"])
        started_cases = transport["logical_case_order"]
        later = (
            list(TARGET_CHAPTERS[len(completed) + 1 :])
            if completed_ok and len(completed) < len(TARGET_CHAPTERS)
            else []
        )
        request_names = _exact_artifact_names(
            run_dir / "requests/neutral_extract", "*_request.json"
        )
        expected_request_names = {f"{case_id}_request.json" for case_id in started_cases}
        actual_requests_match = True
        for case_id in started_cases:
            actual_path = run_dir / f"requests/neutral_extract/{case_id}_request.json"
            prepared_path = run_dir / f"prepared_requests/{case_id}.json"
            actual_requests_match = (
                actual_requests_match
                and actual_path.is_file()
                and prepared_path.is_file()
                and read_json(actual_path).get("body") == read_json(prepared_path)
            )
        completed_artifacts_ok = True
        for chapter in completed if completed_ok else []:
            try:
                artifact_receipt(run_dir, chapter)
            except ZBatchError:
                completed_artifacts_ok = False
        usage_cases = [str(row.get("case_id")) for row in z68.read_jsonl(run_dir / "usage.jsonl")]
        claim = read_json(run_dir / RUN_CLAIM) if (run_dir / RUN_CLAIM).is_file() else None
        checks.extend(
            [
                {
                    "name": "hard_stop_prefix_and_next_chapter",
                    "passed": completed_ok and next_chapter == expected_next,
                },
                {
                    "name": "hard_stop_started_case_order",
                    "passed": started_cases in allowed_started_orders,
                },
                {
                    "name": "hard_stop_requests_equal_prepared",
                    "passed": request_names == expected_request_names
                    and actual_requests_match,
                },
                {
                    "name": "hard_stop_completed_artifacts",
                    "passed": completed_artifacts_ok,
                },
                {
                    "name": "hard_stop_usage_matches_started_cases",
                    "passed": len(usage_cases) == len(set(usage_cases))
                    and all(case_id in started_cases for case_id in usage_cases)
                    and all(case_id in usage_cases for case_id in completed_cases),
                },
                {
                    "name": "hard_stop_manifest_counts_and_claim",
                    "passed": manifest.get("usable_model_outputs") == len(completed_cases)
                    and claim is not None
                    and manifest.get("run_claim") == claim,
                },
            ]
        )
        checks.append(
            {
                "name": "hard_stop_prevents_later_chapters",
                "passed": all(
                    not (run_dir / f"requests/neutral_extract/ch{chapter:04d}_request.json").exists()
                    for chapter in later
                ),
            }
        )
        checks.append({"name": "terminal_transport_receipt", "passed": manifest.get("transport") == transport})
    elif manifest.get("status") == "prepared":
        started = call_artifacts_present(run_dir)
        checks.append(
            {
                "name": "prepared_means_zero_call_and_unclaimed",
                "passed": not started and transport["actual_network_attempts"] == 0,
                "unexpected_artifacts": started,
            }
        )
    elif manifest.get("status") != "prepared":
        checks.append({"name": "known_run_status", "passed": False, "value": manifest.get("status")})

    failed = [row for row in checks if not row["passed"]]
    if failed:
        raise ZBatchError(f"Z70机械验收失败：{failed}")
    receipt = {
        "schema_version": "z70-mechanical-verification-v1",
        "status": "pass",
        "run_status": manifest.get("status"),
        "checks": checks,
        "transport": transport,
    }
    write_json(run_dir / "mechanical_verification.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "verify"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args(argv)
    result = {"prepare": prepare, "run": run, "verify": verify}[args.action](
        args.run_dir.resolve()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
