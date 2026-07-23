#!/usr/bin/env python3
"""第94道步一：构造 Flash 局部语义包，冻结请求但绝不发网。

这份工具只做三件机械工作：
1. 用本条必用锚在冻结正文中的唯一位置确定目标段和相邻段窗口；
2. 从冻结证据目录收取与窗口有字符交叠的候选锚；
3. 从 retry13 已冻结任务逐字派生必须保留项，再生成 32 份单对象请求。

它没有任何 HTTP、SDK 或模型调用入口。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import z68_revised_request_pilot as z68
import z83_program_side_repair_pilot as z83
import z83_retry13_atomic_repair as retry13
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
SOURCE_RUN = (
    ROOT
    / "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry13"
)
SOURCE_RETRY09 = (
    ROOT
    / "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry09"
)
RUN_DIR = ROOT / "runs/Z94_X01_Flash局部语义包_步一备料_v1.0_20260723"
REPORT_DIR = ROOT / "reports/Z94_Flash局部语义包实验_步一备料_20260723"

SOURCE_PLAN = SOURCE_RUN / "repair/atomic_plan.json"
SOURCE_ADJUDICATION = SOURCE_RETRY09 / "review/adjudication_completed.json"
SOURCE_PLAN_SHA256 = "8ad6bd77c7590c0c2493305b91c84fbad573565ba7f1671eeb6d7d1e10c843e4"
SOURCE_ADJUDICATION_SHA256 = (
    "dd954f9fdc420872a2d6f52e4b3cff9a89364463ea69da3bff33f8addd8fa292"
)
SOURCE_V3_PROMPT_SHA256 = (
    "a302920537349d37c75d5bac9df19a83bfab667891458ef65de9d98e84bc2116"
)
SOURCE_CHAPTER_SHA256 = {
    3: "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    13: "418efe90277893207d2623d14c9093a30a68f38f44dd51ebcee6315813ddd8c0",
    19: "127af1d2061e3e4cccca7f893ae98e511c2902a7ae06aecc9fa783eb22ca5caa",
}
SOURCE_CATALOG_SHA256 = {
    3: "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    13: "47d5a5f13b227e4c1470530a1962060f7800f05f30e9e73b815a17604bd9457e",
    19: "dd7b2215801668b3896ccf5c3c651752fa9293b4da0916465f9f3b6fcfd6ba7e",
}
EXPECTED_ATOMIC_SPLIT_COUNTS = {
    "EV-C0003-05": 4,
    "EV-C0013-35": 4,
    "EV-C0013-46": 2,
    "EV-C0019-34": 5,
    "EV-C0019-40": 4,
    "EV-C0019-47": 6,
}
EXPECTED_PARENT_IDS = {
    "EV-C0003-05",
    "EV-C0003-08",
    "EV-C0003-09",
    "EV-C0003-10",
    "EV-C0013-06",
    "EV-C0013-35",
    "EV-C0013-46",
    "EV-C0019-05",
    "EV-C0019-25",
    "EV-C0019-34",
    "EV-C0019-40",
    "EV-C0019-46",
    "EV-C0019-47",
}

Z94_PARAMETERS = {
    "temperature": 0.0,
    "max_tokens": 32000,
    "n": 1,
    "response_format": {"type": "json_object"},
    "reasoning_effort": "medium",
}
RETRY13_REPAIR_PARAMETERS = {
    "temperature": 0.2,
    "max_tokens": 8000,
    "n": 1,
    "response_format": {"type": "json_object"},
    "reasoning_effort": "medium",
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _assert_file(path: Path, expected_sha: str, label: str) -> None:
    if not path.is_file():
        raise ZBatchError(f"缺少{label}：{relative(path)}")
    actual = sha256_file(path)
    if actual != expected_sha:
        raise ZBatchError(f"{label} SHA 漂移：预期 {expected_sha}，实际 {actual}")


def _chapter_path(chapter: int) -> Path:
    matches = sorted((SOURCE_RUN / "inputs/chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"第{chapter}章冻结正文数不是1")
    _assert_file(matches[0], SOURCE_CHAPTER_SHA256[chapter], f"第{chapter}章冻结正文")
    return matches[0]


def _catalog_path(chapter: int) -> Path:
    path = SOURCE_RUN / f"inputs/evidence_catalogs/ch{chapter:04d}.json"
    _assert_file(path, SOURCE_CATALOG_SHA256[chapter], f"第{chapter}章冻结目录")
    return path


def _normalized_text(path: Path) -> tuple[str, bool]:
    raw = path.read_text(encoding="utf-8")
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    return normalized, normalized == raw


def _paragraphs(text: str) -> list[dict[str, Any]]:
    """每个非空物理行是一段；空行只作分隔，不单独编号。"""

    rows: list[dict[str, Any]] = []
    offset = 0
    for physical_line, line_with_break in enumerate(text.splitlines(keepends=True), 1):
        line = line_with_break[:-1] if line_with_break.endswith("\n") else line_with_break
        if line.strip():
            rows.append(
                {
                    "paragraph_id": f"P{len(rows) + 1:04d}",
                    "paragraph_ordinal": len(rows) + 1,
                    "physical_line": physical_line,
                    "start_offset": offset,
                    "end_offset": offset + len(line),
                    "text": line,
                }
            )
        offset += len(line_with_break)
    if not rows:
        raise ZBatchError("冻结正文没有非空段落")
    return rows


def _unique_quote_span(text: str, quote: str, label: str) -> tuple[int, int]:
    start = text.find(quote)
    if start < 0:
        raise ZBatchError(f"{label} 短引不在冻结正文")
    if text.find(quote, start + 1) >= 0:
        raise ZBatchError(f"{label} 短引在冻结正文中不唯一")
    return start, start + len(quote)


def _overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


def paragraph_window_rule() -> dict[str, Any]:
    body = {
        "schema_version": "z94-paragraph-window-rule-v1",
        "source_text": "retry13 隔离冻结章节正文，逐字 SHA 复验",
        "newline_normalization": "只把 CRLF/CR 确定性归一为 LF；本批三章归一前后字节文本等值",
        "paragraph_boundary": "LF 分行；每个非空物理行是一段；空白行只作分隔；标题也编号但只有被必用锚覆盖时才可成为目标段",
        "target_paragraph": "取本子请求全部 required_anchor_ids 的唯一短引字符区间所覆盖段落的并集",
        "window": "目标段并集的最小至最大连续段区间，向前和向后各扩1个非空段，章首章尾截断",
        "cross_paragraph_anchor": "锚跨段时，短引字符实际覆盖的所有非空段都进入目标段并集",
        "hard_stop": [
            "任一必用锚短引在正文中0命中或多命中",
            "任一必用锚不覆盖非空段",
            "窗口为空",
        ],
        "hand_selection": False,
    }
    return {**body, "rule_sha256": canonical_sha(body)}


def anchor_cluster_rule() -> dict[str, Any]:
    body = {
        "schema_version": "z94-anchor-cluster-rule-v1",
        "candidate_universe": "同章冻结证据目录全部 entries",
        "selection": "短引在冻结正文中的唯一字符区间与局部窗口字符区间有交叠即入选",
        "ordering": "按 anchor_id 数字升序，去重",
        "required_policy": "全部 required_anchor_ids 必须在候选簇内；单对象合同仍要求最终只使用冻结必用锚闭集",
        "catalog_validation": "每个候选锚逐字回查同章冻结目录；目录外锚数必须为0",
        "hard_stop": [
            "任一目录短引在正文中0命中或多命中",
            "候选簇为空",
            "任一必用锚未进入候选簇",
            "候选锚重复或目录外",
        ],
        "keyword_or_semantic_ranking": False,
        "hand_selection": False,
    }
    return {**body, "rule_sha256": canonical_sha(body)}


def must_preserve_rule() -> dict[str, Any]:
    body = {
        "schema_version": "z94-must-preserve-rule-v1",
        "semantic_authority": "不重判语义；逐字复用 retry13 atomic_plan 已冻结的 fact_target、permission 与原父事件",
        "fact_head": (
            "fact_target 若为具体事实则逐字使用；若其只是“保持原事件同一中心事实”的许可句，"
            "事实头改取原父事件 event 逐字文本"
        ),
        "necessary_qualifiers": "逐字使用本子请求 permission，不拆词、不改写、不补充",
        "provenance": (
            "非模型可见旁账保留 retry13 父源 adjudication_references，"
            "并钉 retry09 246行判词源 SHA；不把判词正文、gold_rows、分数送入模型"
        ),
        "atomic_n_policy": (
            "六个 N=4/4/2/5/4/6 是 retry13 后续获批冻结输入，"
            "只复验不声称由 retry09 程序自动推导"
        ),
        "hand_selection": False,
    }
    return {**body, "rule_sha256": canonical_sha(body)}


def _load_sources() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    _assert_file(SOURCE_PLAN, SOURCE_PLAN_SHA256, "retry13 原子计划")
    _assert_file(
        SOURCE_ADJUDICATION,
        SOURCE_ADJUDICATION_SHA256,
        "retry09 246行判词",
    )
    v3_prompt = SOURCE_RUN / "prompt_frozen/事实说明书注入包_v3.json"
    _assert_file(v3_prompt, SOURCE_V3_PROMPT_SHA256, "v3冻结提示词")

    plan = read_json(SOURCE_PLAN)
    if (
        plan.get("parent_count") != 13
        or plan.get("logical_request_count") != 32
        or plan.get("atomic_split_counts") != EXPECTED_ATOMIC_SPLIT_COUNTS
        or {row.get("event_id") for row in plan.get("parents", [])}
        != EXPECTED_PARENT_IDS
        or plan.get("pending_parent_ids") != []
    ):
        raise ZBatchError("retry13 13父/32子/N 冻结计划漂移")
    adjudication = read_json(SOURCE_ADJUDICATION)
    collections = ("anchor_rows", "current_rows", "gold_rows", "risk_rows")
    if [len(adjudication.get(name, [])) for name in collections] != [156, 25, 23, 42]:
        raise ZBatchError("retry09 判词不再是156+25+23+42=246行")
    events = retry13._source_event_map(SOURCE_RUN)
    if not EXPECTED_PARENT_IDS.issubset(events):
        raise ZBatchError("retry13 主样事件缺获批父源")
    return plan, events


def _catalog(chapter: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = read_json(_catalog_path(chapter))
    entries = data.get("entries") if isinstance(data, dict) else None
    if (
        not isinstance(entries, list)
        or not entries
        or data.get("chapter") != chapter
        or data.get("coverage") != 1.0
    ):
        raise ZBatchError(f"第{chapter}章冻结目录结构或覆盖率漂移")
    return data, entries


def _task_supply(
    task: Mapping[str, Any],
    source_event: Mapping[str, Any],
) -> dict[str, Any]:
    chapter = int(task["chapter"])
    chapter_path = _chapter_path(chapter)
    text, line_endings_equal = _normalized_text(chapter_path)
    paragraphs = _paragraphs(text)
    catalog_data, catalog_entries = _catalog(chapter)
    catalog_by_id = {str(row["anchor_id"]): row for row in catalog_entries}
    if len(catalog_by_id) != len(catalog_entries):
        raise ZBatchError(f"第{chapter}章冻结目录锚 ID 重复")

    all_spans: dict[str, tuple[int, int]] = {}
    for row in catalog_entries:
        anchor_id = str(row["anchor_id"])
        all_spans[anchor_id] = _unique_quote_span(
            text, str(row["quote"]), f"第{chapter}章{anchor_id}"
        )

    required_ids = [str(value) for value in task["required_anchor_ids"]]
    if not required_ids or len(required_ids) != len(set(required_ids)):
        raise ZBatchError(f"{task['task_id']} 必用锚为空或重复")
    if not set(required_ids).issubset(catalog_by_id):
        raise ZBatchError(f"{task['task_id']} 含目录外必用锚")

    target_ordinals: set[int] = set()
    required_spans: list[dict[str, Any]] = []
    for anchor_id in required_ids:
        start, end = all_spans[anchor_id]
        hit_paragraphs = [
            row
            for row in paragraphs
            if _overlap(start, end, row["start_offset"], row["end_offset"])
        ]
        if not hit_paragraphs:
            raise ZBatchError(f"{task['task_id']} 的 {anchor_id} 不覆盖非空段")
        target_ordinals.update(int(row["paragraph_ordinal"]) for row in hit_paragraphs)
        required_spans.append(
            {
                "anchor_id": anchor_id,
                "start_offset": start,
                "end_offset": end,
                "paragraph_ids": [row["paragraph_id"] for row in hit_paragraphs],
            }
        )

    first = max(1, min(target_ordinals) - 1)
    last = min(len(paragraphs), max(target_ordinals) + 1)
    window_paragraphs = paragraphs[first - 1 : last]
    window_start = int(window_paragraphs[0]["start_offset"])
    window_end = int(window_paragraphs[-1]["end_offset"])
    window_text = text[window_start:window_end]
    if not window_text.strip():
        raise ZBatchError(f"{task['task_id']} 局部窗口为空")

    selected_entries: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    for anchor_id in sorted(
        catalog_by_id, key=lambda value: int(value.removeprefix("E"))
    ):
        start, end = all_spans[anchor_id]
        selected = _overlap(start, end, window_start, window_end)
        if selected:
            selected_entries.append(copy.deepcopy(catalog_by_id[anchor_id]))
        selection_rows.append(
            {
                "anchor_id": anchor_id,
                "selected": selected,
                "reason": "span_intersects_window" if selected else "outside_window",
                "start_offset": start,
                "end_offset": end,
            }
        )
    selected_ids = [str(row["anchor_id"]) for row in selected_entries]
    if (
        not selected_ids
        or len(selected_ids) != len(set(selected_ids))
        or not set(required_ids).issubset(selected_ids)
    ):
        raise ZBatchError(f"{task['task_id']} 候选锚簇为空、重复或漏必用锚")

    fact_target = str(task["fact_target"])
    source_fact = str(source_event["event"])
    fact_head = (
        source_fact if fact_target.startswith("保持原事件同一中心事实") else fact_target
    )
    must_preserve = {
        "fact_head": fact_head,
        "necessary_qualifiers_and_permission": [str(task["permission"])],
        "required_anchor_ids": required_ids,
        "derivation": {
            "fact_head_source": (
                "source_parent_event.event"
                if fact_head == source_fact and fact_target != source_fact
                else "atomic_plan.task.fact_target"
            ),
            "qualifier_source": "atomic_plan.task.permission",
            "semantic_rejudgment": False,
            "hand_selection": False,
        },
    }
    return {
        "schema_version": "z94-local-semantic-supply-v1",
        "task_id": task["task_id"],
        "parent_event_id": task["parent_event_id"],
        "parent_event_sha256": task["parent_event_sha256"],
        "source_identity_sha256": task["source_identity_sha256"],
        "chapter": chapter,
        "source_chapter": {
            "path": relative(chapter_path),
            "sha256": sha256_file(chapter_path),
            "newline_normalization_changed_text": not line_endings_equal,
            "normalized_text_sha256": sha256_bytes(text.encode("utf-8")),
        },
        "source_catalog": {
            "path": relative(_catalog_path(chapter)),
            "sha256": sha256_file(_catalog_path(chapter)),
            "coverage": catalog_data["coverage"],
            "entry_count": len(catalog_entries),
        },
        "paragraph_window": {
            "chapter_paragraph_count": len(paragraphs),
            "target_paragraph_ids": [
                paragraphs[index - 1]["paragraph_id"] for index in sorted(target_ordinals)
            ],
            "window_paragraph_ids": [
                row["paragraph_id"] for row in window_paragraphs
            ],
            "window_start_offset": window_start,
            "window_end_offset": window_end,
            "window_text": window_text,
            "window_text_sha256": sha256_bytes(window_text.encode("utf-8")),
            "required_anchor_spans": required_spans,
        },
        "anchor_cluster": {
            "candidate_anchor_ids": selected_ids,
            "candidate_entries": selected_entries,
            "candidate_count": len(selected_entries),
            "required_anchor_ids": required_ids,
            "outside_catalog_anchor_count": 0,
            "selection_rows": selection_rows,
        },
        "must_preserve": must_preserve,
        "candidate_silver_only": True,
    }


def _model_input_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event": str(event["event"]),
        "anchors": [
            {"anchor_id": str(row["anchor_id"])}
            for row in event.get("anchors", [])
            if isinstance(row, Mapping) and row.get("anchor_id")
        ],
    }


def _static_prefix(
    task: Mapping[str, Any],
    source_event: Mapping[str, Any],
) -> str:
    return (
        f"当前章：{task['chapter']}\n"
        "程序已把复合父事件预拆成本次唯一事实单元；本次不得重抽整章。\n"
        f"本次唯一事实目标：{task['fact_target']}\n"
        f"本条唯一许可动作：{task['permission']}\n"
        "程序预校验的本条完整锚集合（必须全部挂入 anchor_ids，且不得增加集合外 ID）："
        f"{json.dumps(task['required_anchor_ids'], ensure_ascii=False, separators=(',', ':'))}\n"
        "原父事件仅供定位，不得把未点名的其他事实重新并入本条："
        f"{json.dumps(_model_input_event(source_event), ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def _messages(
    task: Mapping[str, Any],
    source_event: Mapping[str, Any],
    supply: Mapping[str, Any],
) -> list[dict[str, str]]:
    system = retry13._extract_single_object_system_contract()
    preserve_visible = {
        "fact_head": supply["must_preserve"]["fact_head"],
        "necessary_qualifiers_and_permission": supply["must_preserve"][
            "necessary_qualifiers_and_permission"
        ],
        "required_anchor_ids": supply["must_preserve"]["required_anchor_ids"],
    }
    user = (
        _static_prefix(task, source_event)
        + "【程序机械生成必须保留项｜不得新增、漏掉或跨子请求合并】\n"
        + json.dumps(preserve_visible, ensure_ascii=False, separators=(",", ":"))
        + "\n\n【局部章节正文窗口｜目标段及前后各1段】\n"
        + str(supply["paragraph_window"]["window_text"])
        + "\n\n【候选锚簇｜anchor_ids 仍只准使用程序冻结必用锚闭集】\n"
        + json.dumps(
            supply["anchor_cluster"]["candidate_entries"],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n\n只按一对一单对象输出合同 v1 返回一个 JSON 对象。"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    forbidden = z83.forbidden_model_hits(messages)
    serialized = json.dumps(messages, ensure_ascii=False)
    extra_forbidden = [
        token
        for token in (
            "GOLD-C",
            "gold_rows",
            "formal_gold",
            "scorecard",
            "金标",
            "答案",
            "旧25",
            "现役122条",
        )
        if token in serialized
    ]
    if forbidden or extra_forbidden:
        raise ZBatchError(
            f"{task['task_id']} 模型可见请求夹入禁入材料："
            f"{sorted(set(forbidden + extra_forbidden))}"
        )
    return messages


def _baseline_request(task_id: str) -> tuple[Path, dict[str, Any]]:
    path = (
        SOURCE_RUN
        / "repair/prepared_single_object_requests"
        / f"z83r13-{task_id}.json"
    )
    if not path.is_file():
        raise ZBatchError(f"缺 retry13 冻结请求：{task_id}")
    body = read_json(path)
    observed = {
        key: body.get(key)
        for key in ("temperature", "max_tokens", "n", "response_format", "reasoning_effort")
    }
    if observed != RETRY13_REPAIR_PARAMETERS:
        raise ZBatchError(f"{task_id} retry13 参数不等于0.2/8k冻结基线")
    return path, body


def _parameter_audit() -> dict[str, Any]:
    differences = [
        {"field": key, "retry13_repair": RETRY13_REPAIR_PARAMETERS[key], "z94": value}
        for key, value in Z94_PARAMETERS.items()
        if RETRY13_REPAIR_PARAMETERS[key] != value
    ]
    return {
        "schema_version": "z94-parameter-attribution-audit-v1",
        "retry13_repair_parameters": RETRY13_REPAIR_PARAMETERS,
        "z94_latest_work_order_parameters": Z94_PARAMETERS,
        "differences": differences,
        "difference_count": len(differences),
        "single_variable_claim_allowed": False,
        "reason": (
            "第94道明写温度0和32k，但 retry13 修复请求实物为0.2和8k；"
            "步一按最新施工令冻结请求，步二发网前须由云端确认如何标注归因。"
        ),
        "step2_release_allowed": False,
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _protection_snapshot() -> dict[str, Any]:
    registry_path = ROOT / "config/gold/formal_gold_registry.json"
    registry = read_json(registry_path)
    registry_entries = registry.get("entries") if isinstance(registry, dict) else None
    rows: dict[str, str] = {
        relative(ROOT / "config/defaults/zbatch_v1.2_full_chain.json"): sha256_file(
            ROOT / "config/defaults/zbatch_v1.2_full_chain.json"
        ),
        relative(ROOT / "config/contracts/classify_rules_v1.2_semantic_identity_v1.json"): sha256_file(
            ROOT / "config/contracts/classify_rules_v1.2_semantic_identity_v1.json"
        ),
        relative(SOURCE_RUN / "inputs/current_formal_records_122.json"): sha256_file(
            SOURCE_RUN / "inputs/current_formal_records_122.json"
        ),
        relative(registry_path): sha256_file(registry_path),
    }
    if not isinstance(registry_entries, list) or len(registry_entries) != 6:
        raise ZBatchError("正式金标登记册不再是六入口")
    for entry in registry_entries:
        pointer = ROOT / str(entry["pointer_path"])
        artifact = ROOT / str(entry["artifact_path"])
        expected_pointer = str(entry["pointer_sha256"])
        expected_artifact = str(entry["artifact_sha256"])
        _assert_file(pointer, expected_pointer, f"{entry['gold_id']}正式指针")
        _assert_file(artifact, expected_artifact, f"{entry['gold_id']}正式金标")
        rows[relative(pointer)] = expected_pointer
        rows[relative(artifact)] = expected_artifact
    return {
        "files": dict(sorted(rows.items())),
        "trees": {
            "outbox": z68.tree_fingerprint(ROOT / "outbox"),
            "retry09_frozen": z68.tree_fingerprint(SOURCE_RETRY09),
            "retry13_frozen": z68.tree_fingerprint(SOURCE_RUN),
        },
    }


def _authorization() -> dict[str, Any]:
    return {
        "schema_version": "z94-authorization-readback-v1",
        "task_id": "Z94",
        "label": "Flash局部语义包实验｜步一零调用备料",
        "authority": {
            "decision": "CZ 2026-07-23 16:07 亲拍乙上桌",
            "work_order_time": "2026-07-23T16:12:00+08:00",
            "ledger_url": "https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c",
            "queue_url": "https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc",
        },
        "scope": "只做步一；13父/32子请求冻结；0模型API；等待云端审收后才可放行步二",
        "source_plan_sha256": SOURCE_PLAN_SHA256,
        "source_adjudication_sha256": SOURCE_ADJUDICATION_SHA256,
        "candidate_silver_only": True,
        "step2_release_allowed": False,
    }


def build_primary_artifacts() -> tuple[dict[str, bytes], dict[str, Any]]:
    plan, events = _load_sources()
    rules = {
        "paragraph_window": paragraph_window_rule(),
        "anchor_cluster": anchor_cluster_rule(),
        "must_preserve": must_preserve_rule(),
    }
    protection = _protection_snapshot()
    artifacts: dict[str, bytes] = {
        "authorization_readback.json": json_bytes(_authorization()),
        "rules/paragraph_window_rule.json": json_bytes(rules["paragraph_window"]),
        "rules/candidate_anchor_cluster_rule.json": json_bytes(rules["anchor_cluster"]),
        "rules/must_preserve_rule.json": json_bytes(rules["must_preserve"]),
        "parameter_diff_vs_retry13.json": json_bytes(_parameter_audit()),
        "protection_snapshot_before.json": json_bytes(protection),
    }
    parent_refs = {
        str(row["event_id"]): copy.deepcopy(row["adjudication_references"])
        for row in plan["parents"]
    }
    preflight_rows: list[dict[str, Any]] = []
    chapter_task_counts: Counter[int] = Counter()
    request_shas: list[str] = []
    system_contract = retry13._extract_single_object_system_contract()
    suffix = "只按一对一单对象输出合同 v1 返回一个 JSON 对象。"

    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        parent_id = str(task["parent_event_id"])
        source_event = events[parent_id]
        supply = _task_supply(task, source_event)
        supply["provenance"] = {
            "retry09_source_path": relative(SOURCE_ADJUDICATION),
            "retry09_source_sha256": SOURCE_ADJUDICATION_SHA256,
            "retry13_plan_path": relative(SOURCE_PLAN),
            "retry13_plan_sha256": SOURCE_PLAN_SHA256,
            "parent_adjudication_references": parent_refs[parent_id],
            "references_model_visible": False,
        }
        messages = _messages(task, source_event, supply)
        baseline_path, baseline = _baseline_request(task_id)
        baseline_messages = baseline.get("messages")
        if (
            not isinstance(baseline_messages, list)
            or baseline_messages[0].get("content") != system_contract
            or not str(baseline_messages[1].get("content", "")).startswith(
                _static_prefix(task, source_event)
            )
            or not str(baseline_messages[1].get("content", "")).endswith(suffix)
            or messages[0].get("content") != baseline_messages[0].get("content")
            or not messages[1]["content"].startswith(_static_prefix(task, source_event))
            or not messages[1]["content"].endswith(suffix)
        ):
            raise ZBatchError(f"{task_id} 非供料合同前后文或 system 漂移")

        body = copy.deepcopy(baseline)
        body["messages"] = messages
        body.update(Z94_PARAMETERS)
        case_name = f"z94-{task_id}.json"
        request_path = f"prepared_requests/{case_name}"
        supply_path = f"supply_bundles/{task_id}.json"
        artifacts[request_path] = json_bytes(body)
        artifacts[supply_path] = json_bytes(supply)
        request_sha = sha256_bytes(artifacts[request_path])
        request_shas.append(request_sha)
        chapter_task_counts[int(task["chapter"])] += 1
        preflight_rows.append(
            {
                "task_id": task_id,
                "parent_event_id": parent_id,
                "chapter": task["chapter"],
                "fact_ordinal": task["fact_ordinal"],
                "fact_count": task["fact_count"],
                "baseline_request_path": relative(baseline_path),
                "baseline_request_sha256": sha256_file(baseline_path),
                "prepared_request_path": request_path,
                "prepared_request_sha256": request_sha,
                "messages_sha256": canonical_sha(messages),
                "system_contract_sha256": canonical_sha(messages[0]["content"]),
                "static_prefix_sha256": sha256_bytes(
                    _static_prefix(task, source_event).encode("utf-8")
                ),
                "static_suffix_sha256": sha256_bytes(suffix.encode("utf-8")),
                "window_sha256": supply["paragraph_window"]["window_text_sha256"],
                "window_paragraph_ids": supply["paragraph_window"][
                    "window_paragraph_ids"
                ],
                "candidate_anchor_count": supply["anchor_cluster"]["candidate_count"],
                "candidate_anchor_ids": supply["anchor_cluster"][
                    "candidate_anchor_ids"
                ],
                "required_anchor_ids": task["required_anchor_ids"],
                "required_anchors_all_in_cluster": True,
                "outside_catalog_anchor_count": 0,
                "gold_or_answer_hits": [],
                "model_api_calls": 0,
                "network_attempts": 0,
            }
        )

    if len(preflight_rows) != 32 or chapter_task_counts != Counter({19: 18, 3: 7, 13: 7}):
        raise ZBatchError("Z94 请求数或分章数量不等于32（7/7/18）")
    parent_counts = Counter(row["parent_event_id"] for row in preflight_rows)
    if {
        parent_id: count
        for parent_id, count in parent_counts.items()
        if count > 1
    } != EXPECTED_ATOMIC_SPLIT_COUNTS:
        raise ZBatchError("Z94 六个原子化 N 漂移")

    preflight = {
        "schema_version": "z94-local-semantic-supply-preflight-v1",
        "status": "pass_zero_call_requests_frozen_with_parameter_attribution_hold",
        "run_id": RUN_DIR.name,
        "source_plan_sha256": SOURCE_PLAN_SHA256,
        "source_adjudication_sha256": SOURCE_ADJUDICATION_SHA256,
        "source_v3_prompt_sha256": SOURCE_V3_PROMPT_SHA256,
        "parent_count": 13,
        "logical_request_count": 32,
        "chapter_task_counts": {str(key): value for key, value in sorted(chapter_task_counts.items())},
        "atomic_split_counts": EXPECTED_ATOMIC_SPLIT_COUNTS,
        "atomic_split_total": 25,
        "one_to_one_total": 7,
        "rules": {
            name: value["rule_sha256"] for name, value in rules.items()
        },
        "system_contract_sha256": canonical_sha(system_contract),
        "request_sha256_set_sha256": canonical_sha(request_shas),
        "rows": preflight_rows,
        "gold_or_answer_material_sent_to_model": False,
        "candidate_silver_only": True,
        "parameter_attribution_hold": True,
        "step2_release_allowed": False,
        "model_api_calls": 0,
        "network_attempts": 0,
        "usage_tokens": 0,
        "tool_sha256": sha256_file(THIS_FILE),
        "protected_before": protection,
    }
    artifacts["preflight.json"] = json_bytes(preflight)
    artifacts["usage_zero_call.json"] = json_bytes(
        {
            "schema_version": "z94-zero-call-ledger-v1",
            "model_api_calls": 0,
            "network_attempts": 0,
            "usage_tokens": 0,
            "http_requests": 0,
            "note": "步一只构造并冻结请求，未创建 call_attempts.jsonl、usage.jsonl、request claim 或响应目录。",
        }
    )
    artifacts["run_manifest.json"] = json_bytes(
        {
            "schema_version": "z94-run-manifest-v1",
            "run_id": RUN_DIR.name,
            "status": "prepared_zero_call_awaiting_cloud_review",
            "step": 1,
            "parent_count": 13,
            "logical_request_count": 32,
            "atomic_split_total": 25,
            "model_api_calls": 0,
            "network_attempts": 0,
            "usage_tokens": 0,
            "candidate_silver_only": True,
            "step2_release_allowed": False,
            "stop_reason": "步一停点；等待云端审收，并确认0/32k相对retry13 0.2/8k的归因标签。",
        }
    )
    summary = {
        "parent_count": 13,
        "request_count": 32,
        "chapter_task_counts": dict(sorted(chapter_task_counts.items())),
        "request_sha256_set_sha256": canonical_sha(request_shas),
        "rules": {name: value["rule_sha256"] for name, value in rules.items()},
        "protected_snapshot": protection,
    }
    return artifacts, summary


def _artifact_set_sha(artifacts: Mapping[str, bytes]) -> str:
    rows = [
        (name, sha256_bytes(raw), len(raw)) for name, raw in sorted(artifacts.items())
    ]
    return canonical_sha(rows)


def _write_artifacts(root: Path, artifacts: Mapping[str, bytes]) -> None:
    for name, raw in sorted(artifacts.items()):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def _tree_file_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def build_supply_boundary_audit(run_dir: Path = RUN_DIR) -> dict[str, Any]:
    """证明模型可见消息中，只有前后固定合同之间的供料切片被替换。"""

    plan, events = _load_sources()
    rows: list[dict[str, Any]] = []
    suffix = "只按一对一单对象输出合同 v1 返回一个 JSON 对象。"
    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        source_event = events[str(task["parent_event_id"])]
        prefix = _static_prefix(task, source_event)
        baseline_path, baseline = _baseline_request(task_id)
        z94_path = run_dir / f"prepared_requests/z94-{task_id}.json"
        if not z94_path.is_file():
            raise ZBatchError(f"缺Z94冻结请求：{task_id}")
        current = read_json(z94_path)
        baseline_messages = baseline.get("messages")
        current_messages = current.get("messages")
        if (
            not isinstance(baseline_messages, list)
            or not isinstance(current_messages, list)
            or len(baseline_messages) != 2
            or len(current_messages) != 2
        ):
            raise ZBatchError(f"{task_id} 请求 messages 外形漂移")
        baseline_user = str(baseline_messages[1].get("content", ""))
        current_user = str(current_messages[1].get("content", ""))
        if (
            not baseline_user.startswith(prefix)
            or not current_user.startswith(prefix)
            or not baseline_user.endswith(suffix)
            or not current_user.endswith(suffix)
            or baseline_messages[0] != current_messages[0]
        ):
            raise ZBatchError(f"{task_id} 供料切片外模型可见正文漂移")
        baseline_non_messages = {
            key: value for key, value in baseline.items() if key != "messages"
        }
        current_non_messages = {
            key: value for key, value in current.items() if key != "messages"
        }
        changed_envelope_fields = sorted(
            key
            for key in set(baseline_non_messages) | set(current_non_messages)
            if baseline_non_messages.get(key) != current_non_messages.get(key)
        )
        if changed_envelope_fields != ["max_tokens", "temperature"]:
            raise ZBatchError(f"{task_id} 参数差异不只温度与最大输出")
        outside_bytes = (prefix + suffix).encode("utf-8")
        rows.append(
            {
                "task_id": task_id,
                "baseline_request_path": relative(baseline_path),
                "z94_request_path": (
                    relative(z94_path)
                    if z94_path.is_relative_to(ROOT)
                    else z94_path.relative_to(run_dir).as_posix()
                ),
                "system_message_equal": True,
                "static_prefix_equal": True,
                "static_suffix_equal": True,
                "outside_supply_slice_sha256_baseline": sha256_bytes(outside_bytes),
                "outside_supply_slice_sha256_z94": sha256_bytes(outside_bytes),
                "outside_supply_slice_equal": True,
                "baseline_supply_slice": {
                    "start_offset": len(prefix),
                    "end_offset": len(baseline_user) - len(suffix),
                    "sha256": sha256_bytes(
                        baseline_user[len(prefix) : -len(suffix)].encode("utf-8")
                    ),
                },
                "z94_supply_slice": {
                    "start_offset": len(prefix),
                    "end_offset": len(current_user) - len(suffix),
                    "sha256": sha256_bytes(
                        current_user[len(prefix) : -len(suffix)].encode("utf-8")
                    ),
                },
                "changed_envelope_fields": changed_envelope_fields,
                "changed_model_visible_scope": "supply_slice_only",
                "model_api_calls": 0,
                "network_attempts": 0,
            }
        )
    if len(rows) != 32 or not all(row["outside_supply_slice_equal"] for row in rows):
        raise ZBatchError("Z94 供料边界差异账不是32行全通过")
    return {
        "schema_version": "z94-supply-boundary-diff-audit-v1",
        "status": "pass_32_outside_supply_slice_byte_equal",
        "scope_definition": (
            "模型可见 user 消息固定前缀与固定收尾之外为供料切片；"
            "system必须逐字相同；请求外壳只另记温度和最大输出两项已知差异"
        ),
        "row_count": 32,
        "rows": rows,
        "rows_sha256": canonical_sha(rows),
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _callback_markdown(
    summary: Mapping[str, Any],
    artifact_set_sha: str,
    supply_boundary_audit_sha: str,
) -> str:
    rules = summary["rules"]
    return f"""# 第94道步一停点回包｜Flash局部语义包零调用备料

✅ 步一已完成，停在云端审收前，没有发模型。

- 固定父事件：13 条；原子化子事实：25 条；一对一：7 条；模型可见单对象请求：32 份。
- 分章数量：第3章 7 份、第13章 7 份、第19章 18 份。
- 六个拆分数保持 `4／4／2／5／4／6`，没有第14条，也没有重做 retry09 的246行语义判词。
- 三条机械规则已经冻结：段落窗口 `{rules['paragraph_window']}`；候选锚簇 `{rules['anchor_cluster']}`；必须保留项 `{rules['must_preserve']}`。
- 32份请求集合 SHA：`{summary['request_sha256_set_sha256']}`；两次独立构造的全工件集合 SHA：`{artifact_set_sha}`。
- 每份请求都保留 retry13 的单对象 system 合同和非供料前后文；供料只换成局部段落窗口、窗口交叠锚簇、程序机械生成必须保留项。
- 32行供料边界差异账 SHA：`{supply_boundary_audit_sha}`；逐请求证明 system 相同、供料切片外前后字节相同，请求外壳另有温度与最大输出两项已知差异。
- 金标、答案、分数、gold_rows、现役122条均未进入模型可见正文；目录外锚 0。

⚠️ 发网前有一项必须由云端确认：retry13 修复请求实物是温度0.2、8k，本道步二条文写温度0、32k。步一按最新施工令冻结为0、32k，但这意味着整份请求相对 retry13 不只改了供料。当前已写入参数差异账，`step2_release_allowed=false`；云端确认归因标签或参数口径后才能发网。

调用账：模型 API 0；网络请求 0；token 0。第83道 retry09／retry13 封存树、六本金标及指针、现役122条、默认登记、分类合同与 outbox 保护态前后相同。

本地工件：

- `{relative(RUN_DIR)}`
- `{relative(REPORT_DIR)}`

来源：Codex
"""


def _write_report_manifest(
    *,
    run_dir: Path,
    report_dir: Path,
    artifact_set_sha: str,
) -> dict[str, Any]:
    manifest_rows = _tree_file_rows(run_dir) + [
        {
            **row,
            "path": f"report/{row['path']}",
        }
        for row in _tree_file_rows(report_dir)
        if row["path"] != "report_manifest.json"
    ]
    manifest = {
        "schema_version": "z94-report-manifest-v1",
        "status": "prepared_zero_call_awaiting_cloud_review",
        "run_dir": relative(run_dir),
        "report_dir": relative(report_dir),
        "artifact_set_sha256": artifact_set_sha,
        "files": manifest_rows,
        "manifest_rows_sha256": canonical_sha(manifest_rows),
        "model_api_calls": 0,
        "network_attempts": 0,
        "usage_tokens": 0,
    }
    (report_dir / "report_manifest.json").write_bytes(json_bytes(manifest))
    return manifest


def prepare(run_dir: Path = RUN_DIR, report_dir: Path = REPORT_DIR) -> dict[str, Any]:
    if run_dir.exists() or report_dir.exists():
        raise ZBatchError("Z94 步一正式目录已存在，拒绝覆盖或原位复跑")
    artifacts_a, summary_a = build_primary_artifacts()
    artifacts_b, summary_b = build_primary_artifacts()
    set_sha_a = _artifact_set_sha(artifacts_a)
    set_sha_b = _artifact_set_sha(artifacts_b)
    if set_sha_a != set_sha_b or summary_a != summary_b or artifacts_a != artifacts_b:
        raise ZBatchError("Z94 步一两次独立机械构造不一致")

    with tempfile.TemporaryDirectory(prefix="z94-prepare-a-") as first_temp, tempfile.TemporaryDirectory(
        prefix="z94-prepare-b-"
    ) as second_temp:
        first = Path(first_temp)
        second = Path(second_temp)
        _write_artifacts(first, artifacts_a)
        _write_artifacts(second, artifacts_b)
        if _tree_file_rows(first) != _tree_file_rows(second):
            raise ZBatchError("Z94 步一两次隔离落盘字节不一致")

    _write_artifacts(run_dir, artifacts_a)
    protected_after = _protection_snapshot()
    if protected_after != summary_a["protected_snapshot"]:
        raise ZBatchError("Z94 步一生成后保护件漂移")

    report_dir.mkdir(parents=True, exist_ok=False)
    double_run = {
        "schema_version": "z94-mechanical-double-run-receipt-v1",
        "status": "pass_two_independent_builds_byte_identical",
        "first_artifact_set_sha256": set_sha_a,
        "second_artifact_set_sha256": set_sha_b,
        "file_count": len(artifacts_a),
        "parent_count": 13,
        "logical_request_count": 32,
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    (report_dir / "mechanical_double_run_receipt.json").write_bytes(
        json_bytes(double_run)
    )
    (report_dir / "protected_state_audit.json").write_bytes(
        json_bytes(
            {
                "schema_version": "z94-protected-state-audit-v1",
                "status": "pass_unchanged",
                "before": summary_a["protected_snapshot"],
                "after": protected_after,
                "changed": [],
                "model_api_calls": 0,
                "network_attempts": 0,
            }
        )
    )
    boundary_audit_path = report_dir / "supply_boundary_diff_audit.json"
    boundary_audit_path.write_bytes(
        json_bytes(build_supply_boundary_audit(run_dir))
    )
    (report_dir / "第94道步一停点回包.md").write_text(
        _callback_markdown(
            summary_a,
            set_sha_a,
            sha256_file(boundary_audit_path),
        ),
        encoding="utf-8",
    )
    manifest = _write_report_manifest(
        run_dir=run_dir,
        report_dir=report_dir,
        artifact_set_sha=set_sha_a,
    )
    return {
        "status": manifest["status"],
        "run_dir": relative(run_dir),
        "report_dir": relative(report_dir),
        "parent_count": 13,
        "logical_request_count": 32,
        "artifact_set_sha256": set_sha_a,
        "model_api_calls": 0,
        "network_attempts": 0,
        "usage_tokens": 0,
        "step2_release_allowed": False,
    }


def add_supply_boundary_audit(
    run_dir: Path = RUN_DIR,
    report_dir: Path = REPORT_DIR,
) -> dict[str, Any]:
    """给已经生成、尚未回传的步一目录补独立差异审计，不改请求。"""

    if not run_dir.is_dir() or not report_dir.is_dir():
        raise ZBatchError("Z94 步一正式目录尚未生成")
    path = report_dir / "supply_boundary_diff_audit.json"
    if path.exists():
        raise ZBatchError("Z94 供料边界差异账已存在，拒绝覆盖")
    before_requests = z68.tree_fingerprint(run_dir / "prepared_requests")
    expected, summary = build_primary_artifacts()
    expected_second, summary_second = build_primary_artifacts()
    if expected != expected_second or summary != summary_second:
        raise ZBatchError("补边界账前两次核心工件重建不一致")
    drift = [
        name
        for name, raw in expected.items()
        if not (run_dir / name).is_file() or (run_dir / name).read_bytes() != raw
    ]
    if drift not in ([], ["preflight.json"]):
        raise ZBatchError(f"补边界账前核心工件出现非工具SHA漂移：{drift}")
    if drift:
        (run_dir / "preflight.json").write_bytes(expected["preflight.json"])
        set_sha = _artifact_set_sha(expected)
        (report_dir / "mechanical_double_run_receipt.json").write_bytes(
            json_bytes(
                {
                    "schema_version": "z94-mechanical-double-run-receipt-v1",
                    "status": "pass_two_independent_builds_byte_identical",
                    "first_artifact_set_sha256": set_sha,
                    "second_artifact_set_sha256": set_sha,
                    "file_count": len(expected),
                    "parent_count": 13,
                    "logical_request_count": 32,
                    "model_api_calls": 0,
                    "network_attempts": 0,
                    "refresh_note": "只同步新增边界审计后的工具SHA；32份请求字节未变。",
                }
            )
        )
    audit = build_supply_boundary_audit(run_dir)
    path.write_bytes(json_bytes(audit))
    after_requests = z68.tree_fingerprint(run_dir / "prepared_requests")
    if before_requests != after_requests:
        raise ZBatchError("补差异账时Z94冻结请求发生漂移")
    artifact_set_sha = _artifact_set_sha(expected)
    (report_dir / "第94道步一停点回包.md").write_text(
        _callback_markdown(summary, artifact_set_sha, sha256_file(path)),
        encoding="utf-8",
    )
    manifest = _write_report_manifest(
        run_dir=run_dir,
        report_dir=report_dir,
        artifact_set_sha=artifact_set_sha,
    )
    return {
        "status": audit["status"],
        "audit_path": relative(path),
        "audit_sha256": sha256_file(path),
        "request_tree_unchanged": True,
        "request_tree_sha256": before_requests["sha256"],
        "report_manifest_sha256": sha256_file(report_dir / "report_manifest.json"),
        "model_api_calls": 0,
        "network_attempts": 0,
        "manifest_status": manifest["status"],
    }


def verify(run_dir: Path = RUN_DIR, report_dir: Path = REPORT_DIR) -> dict[str, Any]:
    if not run_dir.is_dir() or not report_dir.is_dir():
        raise ZBatchError("Z94 步一正式目录尚未生成")
    expected, summary = build_primary_artifacts()
    for name, raw in expected.items():
        path = run_dir / name
        if not path.is_file() or path.read_bytes() != raw:
            raise ZBatchError(f"Z94 步一工件漂移：{name}")
    manifest = read_json(report_dir / "report_manifest.json")
    double_run = read_json(report_dir / "mechanical_double_run_receipt.json")
    protected = read_json(report_dir / "protected_state_audit.json")
    boundary_audit_path = report_dir / "supply_boundary_diff_audit.json"
    boundary_audit = read_json(boundary_audit_path)
    expected_boundary_audit = build_supply_boundary_audit(run_dir)
    if (
        manifest.get("status") != "prepared_zero_call_awaiting_cloud_review"
        or manifest.get("artifact_set_sha256") != _artifact_set_sha(expected)
        or double_run.get("status") != "pass_two_independent_builds_byte_identical"
        or protected.get("status") != "pass_unchanged"
        or protected.get("after") != _protection_snapshot()
        or protected.get("after") != summary["protected_snapshot"]
        or boundary_audit != expected_boundary_audit
        or boundary_audit.get("status")
        != "pass_32_outside_supply_slice_byte_equal"
    ):
        raise ZBatchError("Z94 步一收口票或保护态漂移")
    forbidden_call_paths = (
        run_dir / "call_attempts.jsonl",
        run_dir / "usage.jsonl",
        run_dir / "requests",
        run_dir / "responses",
        run_dir / "run_claim.json",
    )
    present = [relative(path) for path in forbidden_call_paths if path.exists()]
    if present:
        raise ZBatchError(f"Z94 步一出现发网工件：{present}")
    return {
        "schema_version": "z94-verification-v1",
        "status": "pass_zero_call_prepared_awaiting_cloud_review",
        "parent_count": 13,
        "logical_request_count": 32,
        "atomic_split_total": 25,
        "request_sha256_set_sha256": summary["request_sha256_set_sha256"],
        "artifact_set_sha256": _artifact_set_sha(expected),
        "model_api_calls": 0,
        "network_attempts": 0,
        "usage_tokens": 0,
        "step2_release_allowed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare", help="零调用构造并冻结第94道步一工件")
    subparsers.add_parser("add-boundary-audit", help="给现有步一目录补供料边界差异账")
    subparsers.add_parser("verify", help="只读复验正式步一工件")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare()
    elif args.command == "add-boundary-audit":
        result = add_supply_boundary_audit()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
