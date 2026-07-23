#!/usr/bin/env python3
"""第71道：Z68C 事件池的抽后语义补全旁路。

准备阶段只复制 Z68C 冻结底料并生成 25 份候选请求；正式运行按章、按原事件
顺序逐批调用。整轮不可续跑，也不会覆盖任何 Z68C、默认链或 outbox 工件。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import z68_revised_request_pilot as z68
from zbatch_modules import (
    api_transport,
    candidate_envelope,
    extraction_coverage,
    stage_sampling,
)
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAPTERS = (3, 4, 5, 13, 19)
EXPECTED_EVENT_COUNTS = {3: 21, 4: 17, 5: 18, 13: 9, 19: 7}
TOTAL_EVENTS = 72
BATCH_SIZE = 3
TOTAL_LOGICAL_BATCHES = 25
MAX_NETWORK_ATTEMPTS = TOTAL_LOGICAL_BATCHES * 3

RUN_ID = "Z71_X01_z70语义补全旁路_五靶章_v1.0_20260721"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
SOURCE_RUN = ROOT / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720"
SOURCE_MATERIAL_FINGERPRINT = {
    "files": 15,
    "bytes": 245129,
    "sha256": "a49f321e4b8b1a223a9d8a34565a8dc85a2505e5f1509e06fd0cf7f142b636a4",
}

STAGE = "semantic_fill"
PROFILE = "z71_semantic_fill_candidate_isolated_v1"
RUN_LOCAL_CONTRACT = Path("provenance/sensenova_stage_sampling_z71_semfill_v1.json")
RUN_CLAIM = Path("run_claim.json")
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0.0
MAX_TOKENS = 8000

SYSTEM_PROMPT = """你是小说中性原子事件的抽后语义补全组件。输入中的事件已经冻结；你不能新增、删除、拆分、合并、重排或分类事件，也不能改 event_id。

你只可补全每条既有事件句中，和当前主体、当前动作属于同一事件的时间、前提／条件、目的、结果。补入内容必须由该条输入的 nearby_anchors 或 source_windows 原文明示；原文没有明示就保持原句，不得猜测、概括或编造。邻近材料里的独立人物、独立动作、背景设定或后续事件，不得塞进当前事件句。存在指代或归属疑义时保持原句。

anchors 已锁定且不在输出中改写。若 event 有任何变化，provenance_anchor_ids 必须列出直接支撑新增语义的 nearby_anchors 编号；若 event 逐字不变，该数组必须为空。编号不得重复，并按 nearby_anchors 顺序排列。

每条事件句必须是 6～100 个非空字符，不得夹带分类标签。

只输出一个 JSON 对象，顶层字段严格为 schema_version、chapter、batch_id、events。schema_version 固定为 z-semantic-fill-v1。events 数量、顺序必须与输入一致；每项字段严格且仅为 event_id、event、provenance_anchor_ids。"""

SYSTEM_PROHIBITED_MARKERS = (
    "两天后",
    "省钱",
    "提前出门",
    "步行约五十分钟",
    "为面试",
    "GOLD-C",
    "金标",
    "32条示范",
    "现役122条",
    "【正例】",
    "【反例】",
)
REQUEST_PROHIBITED_MARKERS = (
    "GOLD-C",
    "第3章结构层金标",
    "8cca04f06ba21048e15420f178163c646d2effeead0970697fafbf5f45174b7c",
    "32条示范",
    "现役122条",
    "【正例】",
    "【反例】",
)
CLASSIFICATION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\[(?:A|B|C|D)\]",
        r"【(?:A|B|C|D)】",
        r"(?:主类型|分类标签|primary_type|disposition|rule_id)\s*[:：=]",
        r"\b(?:classified|discarded|unclassified)\b",
        r"\b(?:A|B|C|D)-0[1-4]\b",
        r"\bMC-0[78]\b",
        r"EVIDENCE-BOUNDARY",
    )
)


def read_json(path: Path) -> Any:
    return z68.read_json(path)


def write_json(path: Path, value: Any) -> None:
    z68.write_json(path, value)


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _source_chapter_file(chapter: int) -> Path:
    matches = sorted((SOURCE_RUN / "inputs/chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"Z68C第{chapter}章正文文件数不是1")
    return matches[0]


def source_material_rows() -> list[tuple[Path, Path]]:
    rows: list[tuple[Path, Path]] = []
    for chapter in TARGET_CHAPTERS:
        chapter_file = _source_chapter_file(chapter)
        rows.extend(
            (
                (
                    SOURCE_RUN / f"01_extract/events/ch{chapter:04d}.json",
                    Path(f"events/ch{chapter:04d}.json"),
                ),
                (
                    SOURCE_RUN / f"inputs/evidence_catalogs/ch{chapter:04d}.json",
                    Path(f"evidence_catalogs/ch{chapter:04d}.json"),
                ),
                (chapter_file, Path("chapters") / chapter_file.name),
            )
        )
    return rows


def _fingerprint_rows(rows: list[tuple[Path, Path]]) -> dict[str, Any]:
    receipt: list[tuple[str, str, int]] = []
    for source, relative in rows:
        if not source.is_file():
            raise ZBatchError(f"Z68C源件不存在：{source}")
        receipt.append(
            (relative.as_posix(), z68.sha256_file(source), source.stat().st_size)
        )
    wire = "\n".join(
        f"{name}\t{digest}\t{size}" for name, digest, size in sorted(receipt)
    )
    return {
        "files": len(receipt),
        "bytes": sum(size for _, _, size in receipt),
        "sha256": z68.sha256_bytes(wire.encode("utf-8")),
    }


def assert_source_materials() -> dict[str, Any]:
    observed = _fingerprint_rows(source_material_rows())
    if observed != SOURCE_MATERIAL_FINGERPRINT:
        raise ZBatchError(
            f"Z68C五章底料漂移：预期 {SOURCE_MATERIAL_FINGERPRINT}，实际 {observed}"
        )
    total = 0
    for chapter in TARGET_CHAPTERS:
        doc = read_json(SOURCE_RUN / f"01_extract/events/ch{chapter:04d}.json")
        events = doc.get("events") if isinstance(doc, dict) else None
        if (
            not isinstance(events, list)
            or len(events) != EXPECTED_EVENT_COUNTS[chapter]
        ):
            raise ZBatchError(f"Z68C第{chapter}章事件数漂移")
        total += len(events)
    if total != TOTAL_EVENTS:
        raise ZBatchError("Z68C五章事件总数不是72")
    return observed


def copied_input_fingerprint(run_dir: Path) -> dict[str, Any]:
    return z68.tree_fingerprint(run_dir / "inputs")


def _run_chapter_file(run_dir: Path, chapter: int) -> Path:
    matches = sorted((run_dir / "inputs/chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"隔离底料第{chapter}章正文文件数不是1")
    return matches[0]


def _catalog(run_dir: Path, chapter: int) -> list[dict[str, Any]]:
    doc = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ZBatchError(f"第{chapter}章证据目录为空")
    return entries


def _events_doc(run_dir: Path, chapter: int) -> dict[str, Any]:
    doc = read_json(run_dir / f"inputs/events/ch{chapter:04d}.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("events"), list):
        raise ZBatchError(f"第{chapter}章Z68C事件件形状非法")
    return doc


@lru_cache(maxsize=32)
def _chapter_context(
    run_dir: Path, chapter: int
) -> tuple[str, list[dict[str, Any]], dict[str, tuple[int, int]]]:
    """同一隔离 run 每章只读一次正文和目录，供全部小批共享。"""
    entries = _catalog(run_dir, chapter)
    chapter_text = _run_chapter_file(run_dir, chapter).read_text(encoding="utf-8")
    spans = extraction_coverage.locate_catalog_spans(chapter_text, entries)
    return chapter_text, entries, spans


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def build_item(run_dir: Path, chapter: int, event: Mapping[str, Any]) -> dict[str, Any]:
    event_id = event.get("event_id")
    event_text = event.get("event")
    locked_anchors = event.get("anchors")
    if not isinstance(event_id, str) or not isinstance(event_text, str):
        raise ZBatchError(f"第{chapter}章事件缺ID或事件句")
    if not isinstance(locked_anchors, list) or not locked_anchors:
        raise ZBatchError(f"{event_id}没有锁定锚")

    chapter_text, entries, spans = _chapter_context(run_dir, chapter)
    entry_map = {str(row.get("anchor_id")): row for row in entries}
    positions = {str(row.get("anchor_id")): index for index, row in enumerate(entries)}
    anchor_ids: list[str] = []
    for anchor in locked_anchors:
        anchor_id = anchor.get("anchor_id") if isinstance(anchor, dict) else None
        if not isinstance(anchor_id, str) or anchor_id not in entry_map:
            raise ZBatchError(f"{event_id}锁定锚不在冻结目录")
        if anchor.get("quote") != entry_map[anchor_id].get("quote"):
            raise ZBatchError(f"{event_id}锁定锚短引与冻结目录不等")
        anchor_ids.append(anchor_id)

    ranges = [
        (
            max(0, positions[anchor_id] - 8),
            min(len(entries) - 1, positions[anchor_id] + 8),
        )
        for anchor_id in anchor_ids
    ]
    merged = _merge_ranges(ranges)
    nearby_positions = sorted(
        {position for start, end in merged for position in range(start, end + 1)}
    )
    nearby = [copy.deepcopy(entries[position]) for position in nearby_positions]

    source_windows: list[dict[str, Any]] = []
    for start, end in merged:
        first_id = str(entries[start]["anchor_id"])
        last_id = str(entries[end]["anchor_id"])
        fragment = chapter_text[spans[first_id][0] : spans[last_id][1]]
        if not fragment or fragment == chapter_text or fragment not in chapter_text:
            raise ZBatchError(f"{event_id}连续原文窗越界或误含全章")
        source_windows.append(
            {
                "start_anchor_id": first_id,
                "end_anchor_id": last_id,
                "anchor_ids": [
                    str(entries[index]["anchor_id"]) for index in range(start, end + 1)
                ],
                "text": fragment,
                "text_sha256": z68.sha256_bytes(fragment.encode("utf-8")),
            }
        )
    return {
        "event_id": event_id,
        "event": event_text,
        "anchors": copy.deepcopy(locked_anchors),
        "nearby_anchors": nearby,
        "source_windows": source_windows,
    }


def case_id(chapter: int, batch_index: int) -> str:
    return f"ch{chapter:04d}_b{batch_index:03d}"


def expected_batch_specs(run_dir: Path) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        events = _events_doc(run_dir, chapter)["events"]
        for offset in range(0, len(events), BATCH_SIZE):
            index = offset // BATCH_SIZE + 1
            batch = events[offset : offset + BATCH_SIZE]
            specs.append(
                {
                    "chapter": chapter,
                    "batch_index": index,
                    "case_id": case_id(chapter, index),
                    "event_ids": [row["event_id"] for row in batch],
                    "events": batch,
                }
            )
    if len(specs) != TOTAL_LOGICAL_BATCHES:
        raise ZBatchError("补全批次数不是25")
    return specs


def request_prohibited_hits(body: Mapping[str, Any]) -> list[str]:
    messages = body.get("messages")
    wire = json.dumps(messages, ensure_ascii=False)
    hits = [marker for marker in REQUEST_PROHIBITED_MARKERS if marker in wire]
    system = ""
    if isinstance(messages, list) and messages and isinstance(messages[0], dict):
        system = str(messages[0].get("content") or "")
    hits.extend(
        f"system:{marker}" for marker in SYSTEM_PROHIBITED_MARKERS if marker in system
    )
    secret = os.environ.get("SENSENOVA_API_KEY", "")
    if secret and secret in wire:
        hits.append("实际API密钥")
    if "Authorization" in wire or "Bearer " in wire:
        hits.append("授权头痕迹")
    return hits


def build_run_local_contract(path: Path) -> dict[str, Any]:
    raw = read_json(z68.SAMPLING_CONTRACT)
    raw["contract_version"] = "z71-semantic-fill-candidate-isolated-v1"
    raw["profiles"][PROFILE] = {
        "status": "approved_transport_reference",
        "note": "仅授权第71道隔离候选运输；不是默认链登记。",
        "candidate_isolation": True,
        "stages": {
            STAGE: {
                "temperature": TEMPERATURE,
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
    return stage_sampling.load_contract_bundle(
        run_dir / RUN_LOCAL_CONTRACT, profile=PROFILE
    )


def build_prepared_body(run_dir: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    items = [
        build_item(run_dir, int(spec["chapter"]), event) for event in spec["events"]
    ]
    payload = {
        "schema_version": "z-semantic-fill-input-v1",
        "chapter": int(spec["chapter"]),
        "batch_id": str(spec["case_id"]),
        "items": items,
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]
    bundle = load_bundle(run_dir)
    body = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=messages,
        contract=bundle.stage(STAGE),
    )
    if request_prohibited_hits(body):
        raise ZBatchError(f"{spec['case_id']}候选请求夹入禁入材料")
    return body


def assert_body_matches_contract(body: Mapping[str, Any], run_dir: Path) -> None:
    bundle = load_bundle(run_dir)
    rebuilt = api_transport.build_request_body(
        model=str(bundle.route["model"]),
        messages=copy.deepcopy(body["messages"]),
        contract=bundle.stage(STAGE),
    )
    if rebuilt != body:
        raise ZBatchError("补全请求不能由隔离采样合同逐字段复现")


def call_artifacts_present(run_dir: Path) -> list[str]:
    paths = (
        run_dir / RUN_CLAIM,
        run_dir / "call_attempts.jsonl",
        run_dir / "usage.jsonl",
        run_dir / "requests",
        run_dir / "responses",
        run_dir / "outputs",
        run_dir / "sidecars",
        run_dir / "hard_stop.json",
    )
    return [path.relative_to(run_dir).as_posix() for path in paths if path.exists()]


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    source = assert_source_materials()
    protected = z68.assert_protected()
    outbox_before = z68.tree_fingerprint(z68.OUTBOX)
    run_dir.mkdir(parents=True)
    build_run_local_contract(run_dir / RUN_LOCAL_CONTRACT)
    copies: list[dict[str, Any]] = []
    for source_path, relative in source_material_rows():
        copies.append(z68.copy_input(source_path, run_dir / "inputs" / relative))
    if copied_input_fingerprint(run_dir) != SOURCE_MATERIAL_FINGERPRINT:
        raise ZBatchError("隔离run复制底料与Z68C源件不等")

    rows: list[dict[str, Any]] = []
    for spec in expected_batch_specs(run_dir):
        body = build_prepared_body(run_dir, spec)
        assert_body_matches_contract(body, run_dir)
        path = run_dir / f"prepared_requests/{spec['case_id']}.json"
        write_json(path, body)
        rows.append(
            {
                "chapter": spec["chapter"],
                "batch_index": spec["batch_index"],
                "case_id": spec["case_id"],
                "event_ids": spec["event_ids"],
                "event_count": len(spec["event_ids"]),
                "prepared_request": path.relative_to(run_dir).as_posix(),
                "prepared_request_sha256": z68.sha256_file(path),
                "prepared_body_canonical_sha256": z68.canonical_sha(body),
            }
        )

    provenance = []
    for source_path, target in (
        (Path(__file__), run_dir / "provenance/z71_semantic_fill_pilot.py"),
        (
            ROOT / "tools/z68_revised_request_pilot.py",
            run_dir / "provenance/z68_revised_request_pilot.py",
        ),
        (
            ROOT / "tools/zbatch_modules/extraction_coverage.py",
            run_dir / "provenance/extraction_coverage.py",
        ),
        (z68.SAMPLING_CONTRACT, run_dir / "provenance/active_sampling_contract.json"),
        (
            SOURCE_RUN / "run_manifest.json",
            run_dir / "provenance/z68c_run_manifest.json",
        ),
    ):
        provenance.append(z68.copy_input(source_path, target))

    preflight = {
        "schema_version": "z71-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": z68.now_iso(),
        "task": "第71道Z68C抽后语义补全旁路",
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "source_run": SOURCE_RUN.relative_to(ROOT).as_posix(),
        "source_material_fingerprint": source,
        "event_counts": {
            str(key): value for key, value in EXPECTED_EVENT_COUNTS.items()
        },
        "total_events": TOTAL_EVENTS,
        "batch_size_max": BATCH_SIZE,
        "logical_batches": TOTAL_LOGICAL_BATCHES,
        "max_network_attempts": MAX_NETWORK_ATTEMPTS,
        "sampling": {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "n": 1,
            "reasoning_effort": "medium",
            "response_format": {"type": "json_object"},
            "stage": STAGE,
            "candidate_isolation": True,
        },
        "sandbox_to_formal_differences": [
            "去除沙箱章专属答案与评测材料，只保留通用补全合同",
            "增加同一主体加同一动作的事件边界，疑义原样返回",
            "增加逐条provenance_anchor_ids并由冻结目录机械回填quote",
            "Z68C五章72条全覆盖，按每批至多3条固定调度为25批",
            "显式钉死deepseek-v4-flash、0.0、8000、n=1、medium、json_object",
            "增加连续正文source_windows，窗口由原锚前后各8个目录锚机械定位",
        ],
        "request_policy": {
            "source_z68c_only": True,
            "z70_fail_samples_read": False,
            "extract_resampled": False,
            "one_sample_per_batch": True,
            "same_request_only_for_network_retry": True,
            "resume_allowed": False,
            "gold_or_demo_or_current122_in_request": False,
        },
        "copied_inputs": copies,
        "protected": protected,
        "outbox_before": outbox_before,
        "rows": rows,
        "provenance": provenance,
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z71-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared",
            "model_api_calls": 0,
            "network_attempts": 0,
        },
    )
    verify_prepared(run_dir, require_zero_call=True)
    return preflight


def verify_prepared(
    run_dir: Path, *, require_zero_call: bool = False, write_receipt: bool = True
) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    manifest = read_json(run_dir / "run_manifest.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("Z71预演状态不是零调用通过")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("Z71预演调用账不为0")
    if assert_source_materials() != preflight.get("source_material_fingerprint"):
        raise ZBatchError("Z71准备后Z68C源底料漂移")
    if copied_input_fingerprint(run_dir) != SOURCE_MATERIAL_FINGERPRINT:
        raise ZBatchError("Z71隔离复制底料漂移")
    z68.assert_protected()
    if z68.tree_fingerprint(z68.OUTBOX) != preflight.get("outbox_before"):
        raise ZBatchError("Z71期间outbox漂移")
    for row in preflight.get("provenance") or []:
        source_path = ROOT / str(row.get("source") or "")
        target_path = Path(str(row.get("target") or ""))
        expected_sha = str(row.get("sha256") or "")
        if (
            not source_path.is_file()
            or not target_path.is_file()
            or z68.sha256_file(source_path) != expected_sha
            or z68.sha256_file(target_path) != expected_sha
        ):
            raise ZBatchError(f"Z71来源保护件漂移：{row.get('source')}")
    if require_zero_call:
        if manifest.get("status") != "prepared":
            raise ZBatchError("Z71不是可首次开跑的prepared状态")
        started = call_artifacts_present(run_dir)
        if started:
            raise ZBatchError(f"Z71零调用预演出现正式运行工件：{started}")

    specs = expected_batch_specs(run_dir)
    if len(preflight.get("rows") or []) != TOTAL_LOGICAL_BATCHES:
        raise ZBatchError("Z71预演请求账不是25份")
    checks: list[dict[str, Any]] = []
    for spec, row in zip(specs, preflight["rows"], strict=True):
        expected = build_prepared_body(run_dir, spec)
        path = run_dir / f"prepared_requests/{spec['case_id']}.json"
        actual = read_json(path)
        assert_body_matches_contract(actual, run_dir)
        if (
            actual != expected
            or row.get("case_id") != spec["case_id"]
            or row.get("event_ids") != spec["event_ids"]
            or row.get("prepared_request_sha256") != z68.sha256_file(path)
            or request_prohibited_hits(actual)
        ):
            raise ZBatchError(f"{spec['case_id']} prepared请求不能机械重建")
        payload = json.loads(actual["messages"][1]["content"])
        for item in payload["items"]:
            chapter_text, _, _ = _chapter_context(run_dir, int(spec["chapter"]))
            if any(
                not window["text"]
                or window["text"] == chapter_text
                or window["text"] not in chapter_text
                for window in item["source_windows"]
            ):
                raise ZBatchError(
                    f"{spec['case_id']} source_windows不是同章连续原文子串"
                )
        checks.append({"case_id": spec["case_id"], "passed": True})
    receipt = {
        "schema_version": "z71-prepared-verification-v1",
        "status": "pass",
        "require_zero_call": require_zero_call,
        "request_count": len(checks),
        "checks": checks,
        "source_inputs_unchanged": True,
        "protected_unchanged": True,
        "outbox_unchanged": True,
    }
    if write_receipt:
        write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def acquire_run_claim(run_dir: Path) -> dict[str, Any]:
    claim_path = run_dir / RUN_CLAIM
    claim = {
        "schema_version": "z71-run-claim-v1",
        "status": "claimed_do_not_resume",
        "claimed_at": z68.now_iso(),
        "pid": os.getpid(),
    }
    try:
        descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ZBatchError("Z71整轮运行权已被占用或曾中断，拒绝重复采样") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(claim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def _nonspace_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def _classification_hits(value: str) -> list[str]:
    return [
        pattern.pattern for pattern in CLASSIFICATION_PATTERNS if pattern.search(value)
    ]


def validate_batch_output(
    model_data: Any, *, spec: Mapping[str, Any], prepared_body: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(model_data, dict) or set(model_data) != {
        "schema_version",
        "chapter",
        "batch_id",
        "events",
    }:
        raise ZBatchError(f"{spec['case_id']}回包顶层字段不等于补全合同")
    if (
        model_data.get("schema_version") != "z-semantic-fill-v1"
        or model_data.get("chapter") != spec["chapter"]
        or model_data.get("batch_id") != spec["case_id"]
    ):
        raise ZBatchError(f"{spec['case_id']}回包身份字段漂移")
    output_events = model_data.get("events")
    if not isinstance(output_events, list) or len(output_events) != len(spec["events"]):
        raise ZBatchError(f"{spec['case_id']}回包事件数量漂移")
    payload = json.loads(prepared_body["messages"][1]["content"])
    rows: list[dict[str, Any]] = []
    for source, item, output in zip(
        spec["events"], payload["items"], output_events, strict=True
    ):
        if not isinstance(output, dict) or set(output) != {
            "event_id",
            "event",
            "provenance_anchor_ids",
        }:
            raise ZBatchError(f"{spec['case_id']}逐事件字段不等于补全合同")
        if output.get("event_id") != source.get("event_id"):
            raise ZBatchError(f"{spec['case_id']}修改了event_id或顺序")
        after = output.get("event")
        provenance_ids = output.get("provenance_anchor_ids")
        if not isinstance(after, str) or after != after.strip():
            raise ZBatchError(f"{source['event_id']}事件句不是首尾干净字符串")
        length = _nonspace_length(after)
        if length < 6 or length > 100:
            raise ZBatchError(
                f"{source['event_id']}事件句非空字符数越过6～100：{length}"
            )
        labels = _classification_hits(after)
        if labels:
            raise ZBatchError(f"{source['event_id']}事件句夹带分类标签：{labels}")
        if not isinstance(provenance_ids, list) or any(
            not isinstance(anchor_id, str) for anchor_id in provenance_ids
        ):
            raise ZBatchError(f"{source['event_id']} provenance不是字符串数组")
        allowed = [str(row["anchor_id"]) for row in item["nearby_anchors"]]
        if len(provenance_ids) != len(set(provenance_ids)) or any(
            anchor_id not in allowed for anchor_id in provenance_ids
        ):
            raise ZBatchError(
                f"{source['event_id']} provenance越出随请求提供的锚或重复"
            )
        if provenance_ids != sorted(provenance_ids, key=allowed.index):
            raise ZBatchError(f"{source['event_id']} provenance没有按目录顺序")
        changed = after != source["event"]
        if changed != bool(provenance_ids):
            raise ZBatchError(
                f"{source['event_id']} changed与provenance空/非空合同冲突"
            )
        quote_map = {
            str(row["anchor_id"]): str(row["quote"]) for row in item["nearby_anchors"]
        }
        rows.append(
            {
                "event_id": source["event_id"],
                "before": source["event"],
                "after": after,
                "changed": changed,
                "batch_id": spec["case_id"],
                "provenance_anchor_ids": provenance_ids,
                "provenance": [
                    {"anchor_id": anchor_id, "quote": quote_map[anchor_id]}
                    for anchor_id in provenance_ids
                ],
            }
        )
    return {
        "schema_version": "z71-batch-sidecar-v1",
        "chapter": spec["chapter"],
        "batch_id": spec["case_id"],
        "event_ids": spec["event_ids"],
        "changed_count": sum(row["changed"] for row in rows),
        "unchanged_count": sum(not row["changed"] for row in rows),
        "events": rows,
    }


def transport_receipt(run_dir: Path) -> dict[str, Any]:
    attempts = z68.read_jsonl(run_dir / "call_attempts.jsonl")
    allowed = [spec["case_id"] for spec in expected_batch_specs(run_dir)]
    logical_order: list[str] = []
    counts: Counter[str] = Counter()
    hashes: dict[str, set[str]] = {}
    for number, row in enumerate(attempts, 1):
        current = str(row.get("case_id") or "")
        if (
            row.get("call_number") != number
            or row.get("max_calls") != MAX_NETWORK_ATTEMPTS
            or row.get("stage") != STAGE
            or current not in allowed
        ):
            raise ZBatchError("Z71运输账序号、预算、阶段或case漂移")
        if current not in logical_order:
            if current != allowed[len(logical_order)]:
                raise ZBatchError("Z71逻辑批没有按冻结顺序进入")
            logical_order.append(current)
        elif logical_order[-1] != current:
            raise ZBatchError("Z71跨批后又回到旧批")
        counts[current] += 1
        if row.get("attempt") != counts[current] or counts[current] > 3:
            raise ZBatchError("Z71单批网络重试账不连续或超过3次")
        hashes.setdefault(current, set()).add(str(row.get("request_sha256") or ""))
    if len(attempts) > MAX_NETWORK_ATTEMPTS or any(
        len(value) != 1 for value in hashes.values()
    ):
        raise ZBatchError("Z71网络预算越界或同批重试body改变")
    return {
        "max_network_attempts": MAX_NETWORK_ATTEMPTS,
        "actual_network_attempts": len(attempts),
        "logical_case_order": logical_order,
        "logical_samples_started": {value: 1 for value in logical_order},
        "attempts_by_case": dict(counts),
        "same_request_on_network_retries": all(
            len(value) == 1 for value in hashes.values()
        ),
    }


def _assemble_outputs(run_dir: Path, specs: list[dict[str, Any]]) -> dict[str, Any]:
    rows_by_chapter: dict[int, list[dict[str, Any]]] = {
        chapter: [] for chapter in TARGET_CHAPTERS
    }
    for spec in specs:
        sidecar = read_json(run_dir / f"sidecars/batches/{spec['case_id']}.json")
        rows_by_chapter[int(spec["chapter"])].extend(sidecar["events"])
    changed_total = 0
    for chapter in TARGET_CHAPTERS:
        source = _events_doc(run_dir, chapter)
        diff_rows = rows_by_chapter[chapter]
        if [row["event_id"] for row in diff_rows] != [
            row["event_id"] for row in source["events"]
        ]:
            raise ZBatchError(f"第{chapter}章补全sidecar不能覆盖原事件顺序")
        final = copy.deepcopy(source)
        for event, row in zip(final["events"], diff_rows, strict=True):
            event["event"] = row["after"]
        assert_final_compatible(source, final, chapter=chapter)
        changed = sum(row["changed"] for row in diff_rows)
        changed_total += changed
        write_json(run_dir / f"outputs/events/ch{chapter:04d}.json", final)
        write_json(
            run_dir / f"sidecars/event_diffs/ch{chapter:04d}.json",
            {
                "schema_version": "z71-event-diff-sidecar-v1",
                "chapter": chapter,
                "source_event_count": len(source["events"]),
                "changed_count": changed,
                "unchanged_count": len(diff_rows) - changed,
                "events": diff_rows,
            },
        )
    return {
        "changed_events": changed_total,
        "unchanged_events": TOTAL_EVENTS - changed_total,
    }


def assert_final_compatible(
    source: Mapping[str, Any], final: Mapping[str, Any], *, chapter: int
) -> None:
    if (
        set(source) != set(final)
        or source.get("schema_version") != final.get("schema_version")
        or source.get("chapter") != final.get("chapter")
    ):
        raise ZBatchError(f"第{chapter}章补全成品顶层不兼容Z68C")
    source_events = source.get("events")
    final_events = final.get("events")
    if (
        not isinstance(source_events, list)
        or not isinstance(final_events, list)
        or len(source_events) != len(final_events)
    ):
        raise ZBatchError(f"第{chapter}章补全成品事件数不兼容Z68C")
    for before, after in zip(source_events, final_events, strict=True):
        if set(before) != set(after):
            raise ZBatchError(f"{before.get('event_id')}补全成品事件字段不兼容")
        for key in before:
            if key != "event" and before[key] != after[key]:
                raise ZBatchError(
                    f"{before.get('event_id')}除event外字段发生变化：{key}"
                )
        if json.dumps(
            before.get("anchors"), ensure_ascii=False, separators=(",", ":")
        ) != json.dumps(
            after.get("anchors"), ensure_ascii=False, separators=(",", ":")
        ):
            raise ZBatchError(f"{before.get('event_id')} anchors字节投影发生变化")


def run(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    verify_prepared(run_dir, require_zero_call=True)
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest.get("status") != "prepared" or z68.read_jsonl(
        run_dir / "call_attempts.jsonl"
    ):
        raise ZBatchError("Z71已有正式运行痕迹，拒绝复跑或续跑")
    preflight = read_json(run_dir / "preflight.json")
    claim = acquire_run_claim(run_dir)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z71-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "running_do_not_resume",
            "completed_batches": 0,
            "run_claim": claim,
        },
    )
    specs = expected_batch_specs(run_dir)
    completed: list[str] = []
    try:
        transport = api_transport.ApiTransport.from_bundle(
            load_bundle(run_dir), run_dir=run_dir, max_calls=MAX_NETWORK_ATTEMPTS
        )
        for spec in specs:
            current = str(spec["case_id"])
            prepared = read_json(run_dir / f"prepared_requests/{current}.json")
            assert_body_matches_contract(prepared, run_dir)
            result = transport.call(
                stage=STAGE, case_id=current, messages=prepared["messages"]
            )
            if result.request_record.get("body") != prepared:
                raise ZBatchError(f"{current}实际请求与prepared不等")
            actual = read_json(run_dir / f"requests/{STAGE}/{current}_request.json")
            if actual.get("body") != prepared:
                raise ZBatchError(f"{current}落盘实际请求与prepared不等")
            model_data = candidate_envelope.parse_json_content(result.content)
            sidecar = validate_batch_output(
                model_data, spec=spec, prepared_body=prepared
            )
            write_json(run_dir / f"outputs/model_json/{current}.json", model_data)
            write_json(run_dir / f"sidecars/batches/{current}.json", sidecar)
            completed.append(current)
    except BaseException as exc:
        transport = transport_receipt(run_dir)
        hard_stop = {
            "schema_version": "z71-hard-stop-v1",
            "status": "hard_stop_no_repair_no_resume",
            "at": z68.now_iso(),
            "completed_batches": completed,
            "next_batch": specs[len(completed)]["case_id"]
            if len(completed) < len(specs)
            else None,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "transport": transport,
            "source_materials_unchanged": assert_source_materials()
            == preflight["source_material_fingerprint"],
            "copied_inputs_unchanged": copied_input_fingerprint(run_dir)
            == SOURCE_MATERIAL_FINGERPRINT,
            "protected_after": z68.assert_protected(),
            "outbox_unchanged": z68.tree_fingerprint(z68.OUTBOX)
            == preflight["outbox_before"],
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json_atomic(
            run_dir / "run_manifest.json",
            {
                "schema_version": "z71-run-manifest-v1",
                "run_id": run_dir.name,
                "status": "hard_stop",
                "completed_batches": len(completed),
                "run_claim": claim,
                "transport": transport,
            },
        )
        raise

    changes = _assemble_outputs(run_dir, specs)
    transport = transport_receipt(run_dir)
    metrics = {
        "schema_version": "z71-run-metrics-v1",
        "status": "completed_candidate_only",
        "chapters_completed": list(TARGET_CHAPTERS),
        "logical_batches_completed": len(completed),
        "event_count": TOTAL_EVENTS,
        **changes,
        "transport": transport,
    }
    write_json(run_dir / "run_metrics.json", metrics)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z71-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "completed_candidate_only",
            "completed_batches": len(completed),
            "run_claim": claim,
            "transport": transport,
        },
    )
    return metrics


def verify(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    prepared = verify_prepared(run_dir, require_zero_call=False, write_receipt=False)
    manifest = read_json(run_dir / "run_manifest.json")
    preflight = read_json(run_dir / "preflight.json")
    transport = transport_receipt(run_dir)
    specs = expected_batch_specs(run_dir)
    expected_cases = [spec["case_id"] for spec in specs]
    checks: list[dict[str, Any]] = [
        {"name": "prepared_requests", "passed": prepared["status"] == "pass"},
        {
            "name": "source_materials_unchanged",
            "passed": assert_source_materials()
            == preflight["source_material_fingerprint"],
        },
        {
            "name": "copied_inputs_unchanged",
            "passed": copied_input_fingerprint(run_dir) == SOURCE_MATERIAL_FINGERPRINT,
        },
        {"name": "protected_unchanged", "passed": bool(z68.assert_protected())},
        {
            "name": "outbox_unchanged",
            "passed": z68.tree_fingerprint(z68.OUTBOX) == preflight["outbox_before"],
        },
        {
            "name": "network_attempt_budget",
            "passed": transport["actual_network_attempts"] <= MAX_NETWORK_ATTEMPTS,
        },
    ]
    status = manifest.get("status")
    if status == "completed_candidate_only":
        usage = z68.read_jsonl(run_dir / "usage.jsonl")
        checks.extend(
            (
                {
                    "name": "twenty_five_batches_once_in_order",
                    "passed": transport["logical_case_order"] == expected_cases
                    and Counter(str(row.get("case_id")) for row in usage)
                    == Counter({case: 1 for case in expected_cases}),
                },
                {
                    "name": "terminal_transport_receipt",
                    "passed": manifest.get("transport") == transport,
                },
            )
        )
        outside_provenance = 0
        total_rows = 0
        for chapter in TARGET_CHAPTERS:
            source = _events_doc(run_dir, chapter)
            final = read_json(run_dir / f"outputs/events/ch{chapter:04d}.json")
            assert_final_compatible(source, final, chapter=chapter)
            diff = read_json(run_dir / f"sidecars/event_diffs/ch{chapter:04d}.json")
            rows = diff.get("events") if isinstance(diff, dict) else None
            if (
                not isinstance(rows, list)
                or len(rows) != EXPECTED_EVENT_COUNTS[chapter]
            ):
                raise ZBatchError(f"第{chapter}章diff sidecar事件数漂移")
            catalog_ids = {str(row["anchor_id"]) for row in _catalog(run_dir, chapter)}
            outside_provenance += sum(
                anchor_id not in catalog_ids
                for row in rows
                for anchor_id in row.get("provenance_anchor_ids", [])
            )
            total_rows += len(rows)
        checks.extend(
            (
                {
                    "name": "all_72_events_compatible",
                    "passed": total_rows == TOTAL_EVENTS,
                },
                {
                    "name": "outside_catalog_provenance_zero",
                    "passed": outside_provenance == 0,
                    "value": outside_provenance,
                },
            )
        )
    elif status == "hard_stop":
        hard_stop = read_json(run_dir / "hard_stop.json")
        completed = hard_stop.get("completed_batches")
        prefix_ok = (
            isinstance(completed, list)
            and completed == expected_cases[: len(completed)]
        )
        expected_next = (
            expected_cases[len(completed)]
            if prefix_ok and len(completed) < len(expected_cases)
            else None
        )
        checks.extend(
            (
                {
                    "name": "hard_stop_prefix",
                    "passed": prefix_ok
                    and hard_stop.get("next_batch") == expected_next,
                },
                {
                    "name": "hard_stop_transport_prefix",
                    "passed": transport["logical_case_order"]
                    in (
                        completed,
                        completed + ([expected_next] if expected_next else []),
                    )
                    if prefix_ok
                    else False,
                },
                {
                    "name": "terminal_transport_receipt",
                    "passed": manifest.get("transport") == transport,
                },
            )
        )
    elif status == "prepared":
        checks.append(
            {
                "name": "prepared_means_zero_call",
                "passed": not call_artifacts_present(run_dir)
                and transport["actual_network_attempts"] == 0,
            }
        )
    else:
        checks.append({"name": "known_run_status", "passed": False, "value": status})
    failed = [row for row in checks if not row["passed"]]
    if failed:
        raise ZBatchError(f"Z71机械验收失败：{failed}")
    receipt = {
        "schema_version": "z71-mechanical-verification-v1",
        "status": "pass",
        "run_status": status,
        "checks": checks,
        "transport": transport,
    }
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
