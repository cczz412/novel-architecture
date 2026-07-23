#!/usr/bin/env python3
"""第75道件②：A线正反例多方向内测运输器。

每个方向使用独立运行目录，五靶章各采样一次。基线来自第70道已经
验证过的五章统一 32k 请求；候选只在原 system 与原 user 之间插入
一条异题材示例 system 消息。语义判分由独立人工判词账完成。
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
import z70_compression_contract_pilot as z70
from zbatch_modules import api_transport, candidate_envelope, neutral_extract
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAPTERS = (3, 4, 5, 13, 19)
MAX_TOKENS = 32000
MAX_NETWORK_ATTEMPTS = 7
SOURCE_EXAMPLES = ROOT / "reports/Z74A_正反例换皮候选_20260721/三联例候选.json"
SOURCE_EXAMPLES_SHA256 = "16648bf988501c9b0968e41e4aef51b36d0b0c47ec9e1c47900c3dbfe3fcb945"
FORBIDDEN_SOURCE_NAME = "原料来源与病灶提炼.json"
CURRENT_GOLD_POINTER = ROOT / "config/gold/X01_ch0003_structure_gold_current.json"
CURRENT_GOLD_POINTER_SHA256 = "6a5c785dc98381ff4d9b7e207c599c29914f394e4b43e399d37f65093cc5a60c"
CURRENT_GOLD_V1_2 = ROOT / "reports/Z73_第3章金标v1.2定稿转正_20260721/第3章结构层金标v1.2.json"
CURRENT_GOLD_V1_2_SHA256 = "0df08ede4fa1a33f4bd9e1aea3e45387c8d77131ce79ff1496fe1320fa48a10e"
# 复用第70道已经验证过的五章统一32k运输合同文件形状。
RUN_LOCAL_CONTRACT = z70.RUN_LOCAL_CONTRACT
RUN_CLAIM = Path("run_claim.json")

SELECTED_EIGHT = (
    "LARGE-01",
    "LARGE-04",
    "SMALL-01",
    "SMALL-04",
    "MISS-01",
    "MISS-04",
    "ANCHOR-01",
    "ANCHOR-04",
)

DIRECTIONS: dict[str, dict[str, Any]] = {
    "jr08": {
        "label": "八组只放刚好版",
        "group_ids": SELECTED_EIGHT,
        "mode": "just_right_only",
    },
    "jr28": {
        "label": "十六组全部刚好版",
        "group_ids": None,
        "mode": "just_right_only",
    },
    "triad08": {
        "label": "八组三联对照",
        "group_ids": SELECTED_EIGHT,
        "mode": "full_triad",
    },
    "triad16": {
        "label": "十六组三联对照",
        "group_ids": None,
        "mode": "full_triad",
    },
}


def write_json(path: Path, value: Any) -> None:
    z68.write_json(path, value)


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    return z68.read_json(path)


def default_run_dir(direction: str) -> Path:
    return ROOT / "runs" / f"Z75_X01_正反例内测_{direction}_五靶章_v1.0_20260721"


def assert_direction(direction: str) -> None:
    if direction not in DIRECTIONS:
        raise ZBatchError(f"未知方向：{direction}")


def assert_protected() -> dict[str, str]:
    protected = z68.assert_protected()
    for path, expected in (
        (CURRENT_GOLD_POINTER, CURRENT_GOLD_POINTER_SHA256),
        (CURRENT_GOLD_V1_2, CURRENT_GOLD_V1_2_SHA256),
    ):
        actual = z68.sha256_file(path)
        if actual != expected:
            raise ZBatchError(
                f"第75道保护件SHA漂移：{path.relative_to(ROOT)}，预期 {expected}，实际 {actual}"
            )
        protected[path.relative_to(ROOT).as_posix()] = actual
    return protected


def load_example_source() -> dict[str, Any]:
    if z68.sha256_file(SOURCE_EXAMPLES) != SOURCE_EXAMPLES_SHA256:
        raise ZBatchError("A线三联例候选SHA漂移")
    doc = read_json(SOURCE_EXAMPLES)
    groups = doc.get("groups")
    if not isinstance(groups, list) or len(groups) != 16:
        raise ZBatchError("A线三联例不是16组")
    ids = [str(row.get("group_id")) for row in groups]
    expected = [
        *(f"LARGE-{index:02d}" for index in range(1, 5)),
        *(f"SMALL-{index:02d}" for index in range(1, 5)),
        *(f"MISS-{index:02d}" for index in range(1, 5)),
        *(f"ANCHOR-{index:02d}" for index in range(1, 5)),
    ]
    if ids != expected or len(set(ids)) != 16:
        raise ZBatchError(f"A线三联例组序漂移：{ids}")
    if sum(len(row["just_right"]["records"]) for row in groups) != 28:
        raise ZBatchError("A线刚好版不是28条")
    return doc


def selected_groups(direction: str) -> list[dict[str, Any]]:
    assert_direction(direction)
    groups = load_example_source()["groups"]
    selected = DIRECTIONS[direction]["group_ids"]
    if selected is None:
        return copy.deepcopy(groups)
    wanted = set(selected)
    result = [copy.deepcopy(row) for row in groups if row["group_id"] in wanted]
    if [row["group_id"] for row in result] != [
        group_id for group_id in (row["group_id"] for row in groups) if group_id in wanted
    ]:
        raise ZBatchError("八组方向的机械筛选顺序漂移")
    if len(result) != 8:
        raise ZBatchError("八组方向没有得到8组")
    return result


def _event_line(record: Mapping[str, Any]) -> str:
    anchors = "；".join(str(value) for value in record.get("anchors") or [])
    return f"- 事件：{record['text']}｜示例短引：{anchors}"


def render_example_block(direction: str) -> tuple[str, dict[str, Any]]:
    groups = selected_groups(direction)
    mode = str(DIRECTIONS[direction]["mode"])
    lines = [
        "【异题材原子事件颗粒度示例｜只作尺度教学】",
        "下面全是与当前小说无关的人造样例，只用于理解一段材料该拆成几条，以及事件句应写到什么粒度。",
        "禁止把样例人物、地点、情节或短引输出成当前章事实；当前章只能依据后续 user 消息中的连续正文。",
        "示例里的短引不是当前章 anchor_id；正式输出的 anchors 只能填写后续冻结证据目录中的 anchor_id。",
        "判断标准：太大是把可独立判真的事实吞成一条或补了原文没有的关系；太小是把完整动作切成残片；刚好是主体、动作、结果及原文明示限定能够由短引托住。",
        "",
    ]
    just_right_count = 0
    for group in groups:
        lines.append(f"### {group['group_id']}｜{group['pathology_type']}｜{group['subpattern']}")
        lines.append("材料：" + "".join(group["source_scenario"]))
        if mode == "full_triad":
            lines.append("太大版（错误，不要照抄）：")
            lines.extend(f"- {row['text']}" for row in group["too_large"]["records"])
            lines.append("错因：" + group["too_large"]["why_wrong"])
            lines.append("太小版（错误，不要照抄）：")
            lines.extend(f"- {row['text']}" for row in group["too_small"]["records"])
            lines.append("错因：" + group["too_small"]["why_wrong"])
        lines.append("刚好版（只学粒度）：")
        records = group["just_right"]["records"]
        just_right_count += len(records)
        lines.extend(_event_line(row) for row in records)
        lines.append("教学点：" + group["just_right"]["teaching_point"])
        lines.append("")
    lines.extend(
        [
            "【示例块结束】",
            "现在只处理后续 user 消息里的当前章；不要复述、改写或输出上面的样例。",
        ]
    )
    block = "\n".join(lines)
    if FORBIDDEN_SOURCE_NAME in block or z68.request_has_prohibited_input(
        {"messages": [{"role": "system", "content": block}]}
    ):
        raise ZBatchError("示例块夹入禁入材料")
    return block, {
        "direction": direction,
        "label": DIRECTIONS[direction]["label"],
        "mode": mode,
        "group_ids": [row["group_id"] for row in groups],
        "group_count": len(groups),
        "just_right_record_count": just_right_count,
        "block_bytes": len(block.encode("utf-8")),
        "block_sha256": z68.sha256_bytes(block.encode("utf-8")),
    }


def build_candidate_body(direction: str, chapter: int) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline, baseline_meta = z70.build_baseline_body(chapter)
    if baseline["max_tokens"] != MAX_TOKENS or len(baseline["messages"]) != 2:
        raise ZBatchError(f"第{chapter}章32k基线形状漂移")
    if baseline["messages"][0].get("role") != "system" or baseline["messages"][1].get("role") != "user":
        raise ZBatchError(f"第{chapter}章32k基线消息角色漂移")
    block, block_meta = render_example_block(direction)
    candidate = copy.deepcopy(baseline)
    candidate["messages"] = [
        copy.deepcopy(baseline["messages"][0]),
        {"role": "system", "content": block},
        copy.deepcopy(baseline["messages"][1]),
    ]
    restored = copy.deepcopy(candidate)
    removed = restored["messages"].pop(1)
    if restored != baseline or removed != {"role": "system", "content": block}:
        raise ZBatchError("删除示例消息后不能逐字段还原32k基线")
    prohibited = z68.request_has_prohibited_input(candidate)
    if prohibited or FORBIDDEN_SOURCE_NAME in json.dumps(candidate, ensure_ascii=False):
        raise ZBatchError(f"第{chapter}章候选请求夹入禁入材料：{prohibited}")
    return candidate, {
        "schema_version": "z75-request-diff-v1",
        "chapter": chapter,
        "direction": direction,
        "baseline": baseline_meta,
        "single_variable": "messages[1]新增一条异题材示例system消息",
        "message_count_before": 2,
        "message_count_after": 3,
        "removed_message_restores_baseline_exactly": True,
        "unchanged_original_system": candidate["messages"][0] == baseline["messages"][0],
        "unchanged_original_user": candidate["messages"][2] == baseline["messages"][1],
        "unchanged_top_level_except_messages": {
            key: candidate[key] == baseline[key] for key in baseline if key != "messages"
        },
        "example_block": block_meta,
        "baseline_canonical_sha256": z68.canonical_sha(baseline),
        "candidate_canonical_sha256": z68.canonical_sha(candidate),
    }
def _build_run_contract(run_dir: Path) -> None:
    z70.build_run_local_contract(run_dir / RUN_LOCAL_CONTRACT)


def _assert_body_contract(body: Mapping[str, Any], run_dir: Path) -> None:
    z70.assert_body_matches_contract(body, run_dir)


def _copy_frozen_inputs(run_dir: Path) -> list[dict[str, Any]]:
    return z70.copy_frozen_inputs(run_dir)


def _source_inputs() -> dict[str, Any]:
    return z70.assert_source_inputs()


def prepare(direction: str, run_dir: Path) -> dict[str, Any]:
    assert_direction(direction)
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    source_inputs = _source_inputs()
    protected = assert_protected()
    outbox_before = z68.tree_fingerprint(z68.OUTBOX)
    run_dir.mkdir(parents=True)
    _build_run_contract(run_dir)
    block, block_meta = render_example_block(direction)
    (run_dir / "prompt_candidates").mkdir(parents=True, exist_ok=True)
    block_path = run_dir / f"prompt_candidates/{direction}_example_block.txt"
    block_path.write_text(block, encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        baseline, _ = z70.build_baseline_body(chapter)
        candidate, diff = build_candidate_body(direction, chapter)
        _assert_body_contract(baseline, run_dir)
        _assert_body_contract(candidate, run_dir)
        baseline_path = run_dir / f"baseline_requests/ch{chapter:04d}.json"
        prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        diff_path = run_dir / f"request_diffs/ch{chapter:04d}.json"
        write_json(baseline_path, baseline)
        write_json(prepared_path, candidate)
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
    input_receipts = _copy_frozen_inputs(run_dir)
    preflight = {
        "schema_version": "z75-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": z68.now_iso(),
        "task": "第75道件②正反例多方向内测",
        "direction": direction,
        "direction_label": DIRECTIONS[direction]["label"],
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
            "location": "messages[1]",
            "shape": "原system + 示例system + 原user",
            "delete_middle_message_restores_32k_baseline": True,
            "example_block": block_meta,
            "example_block_file": block_path.relative_to(run_dir).as_posix(),
            "example_block_file_sha256": z68.sha256_file(block_path),
        },
        "request_policy": {
            "all_chapters_start_at_32000": True,
            "baseline_not_called": True,
            "one_new_sample_per_chapter": True,
            "rerun_for_selection": False,
            "same_request_only_for_network_retry": True,
            "gold_or_answer_in_request": False,
            "forbidden_raw_source_in_request": False,
            "candidate_only_reversible": True,
        },
        "source_examples": {
            "path": SOURCE_EXAMPLES.relative_to(ROOT).as_posix(),
            "sha256": SOURCE_EXAMPLES_SHA256,
        },
        "source_inputs": source_inputs,
        "copied_inputs": input_receipts,
        "protected": protected,
        "outbox_before": outbox_before,
        "producer": {
            "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": z68.sha256_file(Path(__file__).resolve()),
        },
        "rows": rows,
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z75-run-manifest-v1",
            "run_id": run_dir.name,
            "direction": direction,
            "status": "prepared",
            "model_api_calls": 0,
            "network_attempts": 0,
        },
    )
    verify_prepared(direction, run_dir, require_zero_call=True)
    return preflight


def call_artifacts_present(run_dir: Path) -> list[str]:
    paths = (
        run_dir / RUN_CLAIM,
        run_dir / "call_attempts.jsonl",
        run_dir / "usage.jsonl",
        run_dir / "requests",
        run_dir / "responses",
        run_dir / "01_extract",
        run_dir / "hard_stop.json",
    )
    return [path.relative_to(run_dir).as_posix() for path in paths if path.exists()]


def verify_prepared(direction: str, run_dir: Path, *, require_zero_call: bool) -> dict[str, Any]:
    assert_direction(direction)
    preflight = read_json(run_dir / "preflight.json")
    manifest = read_json(run_dir / "run_manifest.json")
    if preflight.get("direction") != direction or preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第75道预演方向或状态漂移")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("第75道预演调用账不为0")
    if require_zero_call and (manifest.get("status") != "prepared" or call_artifacts_present(run_dir)):
        raise ZBatchError("第75道目录不是可首次运行的零调用prepared状态")
    if _source_inputs() != preflight["source_inputs"]:
        raise ZBatchError("第75道预演后冻结输入漂移")
    if z68.tree_fingerprint(run_dir / "inputs") != preflight["source_inputs"]:
        raise ZBatchError("第75道隔离输入与冻结输入不一致")
    if assert_protected() != preflight["protected"]:
        raise ZBatchError("第75道保护件账漂移")
    producer = preflight.get("producer") or {}
    producer_path = ROOT / str(producer.get("path") or "")
    if (
        not producer_path.is_file()
        or z68.sha256_file(producer_path) != producer.get("sha256")
    ):
        raise ZBatchError("第75道运输器在prepare后发生漂移，拒绝开跑")
    if z68.tree_fingerprint(z68.OUTBOX) != preflight["outbox_before"]:
        raise ZBatchError("第75道期间outbox漂移")
    block, block_meta = render_example_block(direction)
    block_path = run_dir / preflight["single_variable"]["example_block_file"]
    if block_path.read_text(encoding="utf-8") != block or block_meta != preflight["single_variable"]["example_block"]:
        raise ZBatchError("第75道示例块不能机械重建")
    checks: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        expected_baseline, _ = z70.build_baseline_body(chapter)
        expected_candidate, expected_diff = build_candidate_body(direction, chapter)
        baseline = read_json(run_dir / f"baseline_requests/ch{chapter:04d}.json")
        candidate = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        diff = read_json(run_dir / f"request_diffs/ch{chapter:04d}.json")
        restored = copy.deepcopy(candidate)
        middle = restored["messages"].pop(1)
        passed = (
            baseline == expected_baseline
            and candidate == expected_candidate
            and diff == expected_diff
            and restored == baseline
            and middle == {"role": "system", "content": block}
            and baseline["max_tokens"] == candidate["max_tokens"] == MAX_TOKENS
            and not z68.request_has_prohibited_input(candidate)
            and FORBIDDEN_SOURCE_NAME not in json.dumps(candidate, ensure_ascii=False)
        )
        _assert_body_contract(candidate, run_dir)
        if not passed:
            raise ZBatchError(f"第{chapter}章候选请求不能机械重建")
        checks.append(
            {
                "chapter": chapter,
                "passed": True,
                "message_shape": ["原system", "示例system", "原user"],
                "effective_max_tokens": MAX_TOKENS,
                "delete_middle_message_restores_baseline": True,
            }
        )
    receipt = {
        "schema_version": "z75-prepared-verification-v1",
        "status": "pass",
        "direction": direction,
        "require_zero_call": require_zero_call,
        "checks": checks,
        "source_inputs_unchanged": True,
        "protected_unchanged": True,
        "outbox_unchanged": True,
    }
    write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def acquire_run_claim(direction: str, run_dir: Path) -> dict[str, Any]:
    claim_path = run_dir / RUN_CLAIM
    claim = {
        "schema_version": "z75-run-claim-v1",
        "direction": direction,
        "status": "claimed_do_not_resume",
        "claimed_at": z68.now_iso(),
        "pid": os.getpid(),
    }
    try:
        descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ZBatchError("第75道本方向已经开跑或曾中断，拒绝重复采样") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(claim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def transport_receipt(direction: str, run_dir: Path) -> dict[str, Any]:
    attempts = z68.read_jsonl(run_dir / "call_attempts.jsonl")
    allowed = [f"{direction}_ch{chapter:04d}" for chapter in TARGET_CHAPTERS]
    order: list[str] = []
    attempts_by_case: Counter[str] = Counter()
    request_hashes: dict[str, set[str]] = {}
    for number, row in enumerate(attempts, 1):
        case_id = str(row.get("case_id") or "")
        if row.get("call_number") != number or row.get("max_calls") != MAX_NETWORK_ATTEMPTS:
            raise ZBatchError("第75道运输账序号或总尝试预算漂移")
        if row.get("stage") != "neutral_extract" or case_id not in allowed:
            raise ZBatchError("第75道运输账混入范围外case")
        if case_id not in order:
            if case_id != allowed[len(order)]:
                raise ZBatchError("第75道章次未按3→4→5→13→19进入")
            order.append(case_id)
        elif order[-1] != case_id:
            raise ZBatchError("第75道运输账跨章后又回到旧章")
        attempts_by_case[case_id] += 1
        if row.get("attempt") != attempts_by_case[case_id] or attempts_by_case[case_id] > 3:
            raise ZBatchError("第75道单章网络重试账不连续或超过3次")
        request_hashes.setdefault(case_id, set()).add(str(row.get("request_sha256") or ""))
    if len(attempts) > MAX_NETWORK_ATTEMPTS:
        raise ZBatchError("第75道本方向网络尝试超过7次")
    if any(len(values) != 1 for values in request_hashes.values()):
        raise ZBatchError("第75道同章网络重试不是同一请求")
    return {
        "max_network_attempts": MAX_NETWORK_ATTEMPTS,
        "actual_network_attempts": len(attempts),
        "logical_case_order": order,
        "attempts_by_case": dict(attempts_by_case),
        "same_request_on_network_retries": True,
    }


def artifact_receipt(direction: str, run_dir: Path, chapter: int) -> dict[str, str]:
    case_id = f"{direction}_ch{chapter:04d}"
    paths = {
        "request": run_dir / f"requests/neutral_extract/{case_id}_request.json",
        "raw_response": run_dir / f"responses/neutral_extract/{case_id}_raw.json",
        "response_meta": run_dir / f"responses/neutral_extract/{case_id}_meta.json",
        "model_json": run_dir / f"01_extract/model_json/ch{chapter:04d}.json",
        "events": run_dir / f"01_extract/events/ch{chapter:04d}.json",
        "program_audit": run_dir / f"01_extract/program_audits/ch{chapter:04d}.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ZBatchError(f"第{chapter}章运行工件不完整：{missing}")
    return {f"{name}_sha256": z68.sha256_file(path) for name, path in paths.items()}


def run(direction: str, run_dir: Path) -> dict[str, Any]:
    verify_prepared(direction, run_dir, require_zero_call=True)
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest.get("status") != "prepared" or z68.read_jsonl(run_dir / "call_attempts.jsonl"):
        raise ZBatchError("第75道本方向不是首次运行状态")
    preflight = read_json(run_dir / "preflight.json")
    claim = acquire_run_claim(direction, run_dir)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z75-run-manifest-v1",
            "run_id": run_dir.name,
            "direction": direction,
            "status": "running_do_not_resume",
            "usable_model_outputs": 0,
            "run_claim": claim,
        },
    )
    completed: list[int] = []
    receipts: dict[str, Any] = {}
    try:
        transport = api_transport.ApiTransport.from_bundle(
            z70.load_bundle(run_dir), run_dir=run_dir, max_calls=MAX_NETWORK_ATTEMPTS
        )
        for chapter in TARGET_CHAPTERS:
            case_id = f"{direction}_ch{chapter:04d}"
            prepared = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
            _assert_body_contract(prepared, run_dir)
            result = transport.call(
                stage="neutral_extract", case_id=case_id, messages=prepared["messages"]
            )
            actual = read_json(run_dir / f"requests/neutral_extract/{case_id}_request.json")
            if result.request_record.get("body") != prepared or actual.get("body") != prepared:
                raise ZBatchError(f"第{chapter}章实际请求不等于prepared")
            if result.finish_reason != "stop" or not result.content.strip():
                raise ZBatchError(f"第{chapter}章回包未stop或正文为空")
            model_json = candidate_envelope.parse_json_content(result.content)
            events = model_json.get("events")
            if not isinstance(events, list) or not events:
                raise ZBatchError(f"第{chapter}章events为空")
            catalog = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")["entries"]
            materialized, audit = neutral_extract.process_model_data(
                model_json, chapter=chapter, catalog=catalog
            )
            if audit.get("status") != "pass" or audit.get("missing_catalog_anchor_ids"):
                raise ZBatchError(f"第{chapter}章证据锚合同失败")
            write_json(run_dir / f"01_extract/model_json/ch{chapter:04d}.json", model_json)
            write_json(run_dir / f"01_extract/events/ch{chapter:04d}.json", materialized)
            write_json(run_dir / f"01_extract/program_audits/ch{chapter:04d}.json", audit)
            receipts[str(chapter)] = {
                **artifact_receipt(direction, run_dir, chapter),
                "event_count": len(events),
                "anchor_reference_count": audit["anchor_reference_count"],
                "outside_catalog_anchor_count": len(audit["missing_catalog_anchor_ids"]),
            }
            completed.append(chapter)
    except BaseException as exc:
        receipt = transport_receipt(direction, run_dir)
        hard_stop = {
            "schema_version": "z75-hard-stop-v1",
            "status": "hard_stop_no_repair_no_rerun",
            "at": z68.now_iso(),
            "direction": direction,
            "completed_chapters": completed,
            "next_chapter": next((ch for ch in TARGET_CHAPTERS if ch not in completed), None),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "transport": receipt,
            "source_inputs_unchanged": _source_inputs() == preflight["source_inputs"],
            "protected_after": assert_protected(),
            "outbox_unchanged": z68.tree_fingerprint(z68.OUTBOX) == preflight["outbox_before"],
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json_atomic(
            run_dir / "run_manifest.json",
            {
                "schema_version": "z75-run-manifest-v1",
                "run_id": run_dir.name,
                "direction": direction,
                "status": "hard_stop",
                "usable_model_outputs": len(completed),
                "run_claim": claim,
                "transport": receipt,
            },
        )
        raise
    receipt = transport_receipt(direction, run_dir)
    metrics = {
        "schema_version": "z75-run-metrics-v1",
        "status": "completed_candidate_silver_only",
        "direction": direction,
        "chapters_completed": completed,
        "transport": receipt,
        "receipts": receipts,
    }
    write_json(run_dir / "01_extract/metrics.json", metrics)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z75-run-manifest-v1",
            "run_id": run_dir.name,
            "direction": direction,
            "status": "completed_candidate_silver_only",
            "usable_model_outputs": len(completed),
            "run_claim": claim,
            "transport": receipt,
        },
    )
    return metrics


def _scan_secret(run_dir: Path) -> dict[str, Any]:
    secret = os.environ.get("SENSENOVA_API_KEY", "")
    exact_hits: list[str] = []
    auth_hits: list[str] = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(run_dir).as_posix()
        if secret and secret in text:
            exact_hits.append(rel)
        if "Authorization:" in text or "Bearer " in text:
            auth_hits.append(rel)
    return {
        "real_secret_available_for_scan": bool(secret),
        "exact_secret_hits": exact_hits,
        "authorization_header_hits": auth_hits,
        "passed": not exact_hits and not auth_hits,
    }


def verify(direction: str, run_dir: Path) -> dict[str, Any]:
    prepared = verify_prepared(direction, run_dir, require_zero_call=False)
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest.get("status") not in {"prepared", "completed_candidate_silver_only", "hard_stop"}:
        raise ZBatchError(f"第75道未知运行状态：{manifest.get('status')}")
    transport = transport_receipt(direction, run_dir)
    checks: list[dict[str, Any]] = [
        {"name": "prepared_requests", "passed": prepared["status"] == "pass"},
        {"name": "network_attempt_budget", "passed": transport["actual_network_attempts"] <= MAX_NETWORK_ATTEMPTS},
        {"name": "protected_unchanged", "passed": bool(assert_protected())},
        {"name": "outbox_unchanged", "passed": z68.tree_fingerprint(z68.OUTBOX) == read_json(run_dir / "preflight.json")["outbox_before"]},
    ]
    if manifest.get("status") == "completed_candidate_silver_only":
        expected_cases = [f"{direction}_ch{chapter:04d}" for chapter in TARGET_CHAPTERS]
        usage = z68.read_jsonl(run_dir / "usage.jsonl")
        claim = read_json(run_dir / RUN_CLAIM) if (run_dir / RUN_CLAIM).is_file() else None
        request_names = {
            item.name
            for item in (run_dir / "requests/neutral_extract").glob("*_request.json")
            if item.is_file()
        }
        expected_request_names = {f"{case_id}_request.json" for case_id in expected_cases}
        outside_total = 0
        for chapter in TARGET_CHAPTERS:
            case_id = f"{direction}_ch{chapter:04d}"
            prepared_body = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
            actual_body = read_json(run_dir / f"requests/neutral_extract/{case_id}_request.json")["body"]
            meta = read_json(run_dir / f"responses/neutral_extract/{case_id}_meta.json")
            model_json = read_json(run_dir / f"01_extract/model_json/ch{chapter:04d}.json")
            audit = read_json(run_dir / f"01_extract/program_audits/ch{chapter:04d}.json")
            catalog = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")["entries"]
            reasons, rebuilt_audit = neutral_extract.audit_event_envelope(
                model_json, chapter, catalog
            )
            outside = len(rebuilt_audit.get("missing_catalog_anchor_ids") or [])
            outside_total += outside
            artifact_receipt(direction, run_dir, chapter)
            checks.extend(
                [
                    {
                        "name": f"ch{chapter:04d}_actual_equals_prepared",
                        "passed": actual_body == prepared_body
                        and actual_body["max_tokens"] == MAX_TOKENS,
                    },
                    {
                        "name": f"ch{chapter:04d}_stop_nonempty_json_anchor_contract",
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
        checks.extend(
            [
                {
                    "name": "terminal_run_claim_pinned",
                    "passed": claim is not None and manifest.get("run_claim") == claim,
                },
                {
                    "name": "five_unique_samples_in_order",
                    "passed": transport["logical_case_order"] == expected_cases,
                },
                {
                    "name": "exactly_five_request_artifacts",
                    "passed": request_names == expected_request_names,
                },
                {
                    "name": "one_successful_usage_per_chapter",
                    "passed": Counter(str(row.get("case_id")) for row in usage)
                    == Counter({case_id: 1 for case_id in expected_cases}),
                },
                {"name": "outside_catalog_anchor_zero", "passed": outside_total == 0, "value": outside_total},
                {
                    "name": "terminal_transport_receipt",
                    "passed": manifest.get("transport") == transport,
                },
            ]
        )
    elif manifest.get("status") == "prepared":
        checks.append({"name": "prepared_zero_call", "passed": not call_artifacts_present(run_dir)})
    else:
        hard_stop = read_json(run_dir / "hard_stop.json")
        completed = hard_stop.get("completed_chapters")
        completed_ok = (
            isinstance(completed, list)
            and completed == list(TARGET_CHAPTERS[: len(completed)])
        )
        expected_next = (
            TARGET_CHAPTERS[len(completed)]
            if completed_ok and len(completed) < len(TARGET_CHAPTERS)
            else None
        )
        completed_cases = (
            [f"{direction}_ch{chapter:04d}" for chapter in completed]
            if completed_ok
            else []
        )
        allowed_started_orders = [completed_cases]
        if expected_next is not None:
            allowed_started_orders.append(
                completed_cases + [f"{direction}_ch{expected_next:04d}"]
            )
        started_cases = transport["logical_case_order"]
        later = (
            list(TARGET_CHAPTERS[len(completed) + 1 :])
            if completed_ok and len(completed) < len(TARGET_CHAPTERS)
            else []
        )
        request_names = {
            item.name
            for item in (run_dir / "requests/neutral_extract").glob("*_request.json")
            if item.is_file()
        }
        expected_request_names = {f"{case_id}_request.json" for case_id in started_cases}
        actual_requests_match = True
        for case_id in started_cases:
            chapter = int(case_id.rsplit("ch", 1)[1])
            actual_path = run_dir / f"requests/neutral_extract/{case_id}_request.json"
            prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
            actual_requests_match = (
                actual_requests_match
                and actual_path.is_file()
                and prepared_path.is_file()
                and read_json(actual_path).get("body") == read_json(prepared_path)
            )
        completed_artifacts_ok = True
        for chapter in completed if completed_ok else []:
            try:
                artifact_receipt(direction, run_dir, chapter)
            except ZBatchError:
                completed_artifacts_ok = False
        usage_cases = [
            str(row.get("case_id")) for row in z68.read_jsonl(run_dir / "usage.jsonl")
        ]
        claim = read_json(run_dir / RUN_CLAIM) if (run_dir / RUN_CLAIM).is_file() else None
        checks.extend(
            [
                {
                    "name": "hard_stop_prefix_and_next_chapter",
                    "passed": completed_ok
                    and hard_stop.get("next_chapter") == expected_next,
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
                    "passed": manifest.get("usable_model_outputs")
                    == len(completed_cases)
                    and claim is not None
                    and manifest.get("run_claim") == claim,
                },
                {
                    "name": "hard_stop_prevents_later_chapters",
                    "passed": all(
                        not (
                            run_dir
                            / f"requests/neutral_extract/{direction}_ch{chapter:04d}_request.json"
                        ).exists()
                        for chapter in later
                    ),
                },
                {
                    "name": "terminal_transport_receipt",
                    "passed": manifest.get("transport") == transport
                    and hard_stop.get("transport") == transport,
                },
            ]
        )
    secret_scan = _scan_secret(run_dir)
    checks.append({"name": "secret_and_auth_header_zero", "passed": secret_scan["passed"]})
    failed = [row for row in checks if not row["passed"]]
    if failed:
        raise ZBatchError(f"第75道机械验收失败：{failed}")
    receipt = {
        "schema_version": "z75-mechanical-verification-v1",
        "status": "pass",
        "direction": direction,
        "run_status": manifest.get("status"),
        "checks": checks,
        "transport": transport,
        "secret_scan": secret_scan,
    }
    write_json(run_dir / "mechanical_verification.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "verify"))
    parser.add_argument("--direction", choices=tuple(DIRECTIONS), required=True)
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args(argv)
    run_dir = (args.run_dir or default_run_dir(args.direction)).resolve()
    result = {
        "prepare": prepare,
        "run": run,
        "verify": verify,
    }[args.action](args.direction, run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
