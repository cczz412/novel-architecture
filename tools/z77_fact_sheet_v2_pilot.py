#!/usr/bin/env python3
"""第77道：事实说明书注入包 v2 与三章复验隔离运行器。

主采样只跑第3、13、19章各一次。主回包若只有事件句超长或证据锚 ID
不在冻结目录两类错误，只把违规事件送入定点重写；其他错误仍硬停。
本工具不改现役默认链、中性事件验收器或任何正式记录。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import z68_revised_request_pilot as z68
import z70_compression_contract_pilot as z70
import z75_triplet_prompt_pilot as z75
from zbatch_modules import api_transport, candidate_envelope, neutral_extract, stage_sampling
from zbatch_modules.evidence_catalog import nonspace_chars
from zbatch_modules.errors import ZBatchError


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAPTERS = (3, 13, 19)
RUN_ID = "Z77_X01_事实说明书注入包v2_三章复验_v1.0_20260721"
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_ID
RUN_CLAIM = Path("run_claim.json")
RUN_LOCAL_CONTRACT = Path("provenance/sensenova_stage_sampling_z77_v1.json")
PROFILE = "z77_fact_sheet_v2_32k_v1"

MAX_TOKENS = 32000
RETRY_MAX_TOKENS = 8000
MAX_EVENT_NONSPACE_CHARS = 100
MAX_TARGETED_RETRIES_PER_EVENT = 1
MAX_TARGETED_RETRIES_PER_CHAPTER = 3
MAX_TARGETED_RETRIES_TOTAL = 6
MAX_NETWORK_ATTEMPTS = 27

ANCHOR_ID_PATTERN = re.compile(r"^E\d{4}$")
RETRY_ROOT_KEYS = {"replacement_events"}
RETRY_EVENT_KEYS = {"event", "anchors"}

SOURCE_EXAMPLES = ROOT / "reports/Z74A_正反例换皮候选_20260721/三联例候选.json"
SOURCE_EXAMPLES_SHA256 = "16648bf988501c9b0968e41e4aef51b36d0b0c47ec9e1c47900c3dbfe3fcb945"
SOURCE_SANDBOX = Path(
    "/Users/a1234/挣钱/小说架构_外置仓/TEMP外置_20260720/"
    "CZ_EXTRA_事实说明书三章沙箱_20260721"
)
SOURCE_V1_BLOCK = SOURCE_SANDBOX / "runs/manual_pos/prompt_candidates/manual_pos_example_block.txt"
SOURCE_V1_BLOCK_SHA256 = "f646b0c410bde57abb0fb26ed638a5021384ac41a6f9b6e369b8a6a4c3ea9bca"
SOURCE_ARM2_ADJUDICATION = SOURCE_SANDBOX / "adjudication_manual_pos.json"
SOURCE_ARM2_ADJUDICATION_SHA256 = "f7482387740646f28545a73fef6b5af3ef82ae03b4a7a1f6a4758bba9efe52ca"

Z75_PROTECTED_PATHS = (
    ROOT / "reports/Z75_正反例全文回传与内测_20260721",
    ROOT / "runs/Z75_X01_正反例内测_jr08_五靶章_v1.0_20260721",
    ROOT / "runs/Z75_X01_正反例内测_jr28_五靶章_v1.0_20260721",
    ROOT / "runs/Z75_X01_正反例内测_triad08_五靶章_v1.0_20260721",
    ROOT / "runs/Z75_X01_正反例内测_triad16_五靶章_v1.0_20260721",
)

SELECTED_EIGHT = z75.SELECTED_EIGHT


def write_json(path: Path, value: Any) -> None:
    z68.write_json(path, value)


def read_json(path: Path) -> Any:
    return z68.read_json(path)


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def multi_tree_fingerprint(paths: tuple[Path, ...]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for root in paths:
        if not root.exists():
            raise ZBatchError(f"第75道保护路径不存在：{root}")
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rows.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": z68.sha256_file(path),
                }
            )
    wire = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "files": len(rows),
        "bytes": sum(row["bytes"] for row in rows),
        "sha256": hashlib.sha256(wire).hexdigest(),
    }


def assert_protected() -> dict[str, Any]:
    return {
        "formal": z75.assert_protected(),
        "outbox": z68.tree_fingerprint(z68.OUTBOX),
        "z75_untracked_artifacts": multi_tree_fingerprint(Z75_PROTECTED_PATHS),
    }


def length_threshold_receipt() -> dict[str, Any]:
    path = ROOT / "tools/zbatch_modules/neutral_extract.py"
    needle = (
        "if not isinstance(summary, str) or not 6 <= "
        "nonspace_chars(summary) <= 100:"
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [index for index, line in enumerate(lines, 1) if line.strip() == needle]
    if len(hits) != 1:
        raise ZBatchError(f"现役事件句长度阈值源码锚漂移：{hits}")
    return {
        "minimum_nonspace_characters": 6,
        "maximum_nonspace_characters": MAX_EVENT_NONSPACE_CHARS,
        "source": path.relative_to(ROOT).as_posix(),
        "source_line": hits[0],
        "source_sha256": z68.sha256_file(path),
        "exact_condition": needle,
    }


def load_selected_examples() -> list[dict[str, Any]]:
    if z68.sha256_file(SOURCE_EXAMPLES) != SOURCE_EXAMPLES_SHA256:
        raise ZBatchError("八组正例源 SHA 漂移")
    doc = read_json(SOURCE_EXAMPLES)
    groups = doc.get("groups")
    if not isinstance(groups, list):
        raise ZBatchError("正反例源 groups 不是数组")
    wanted = set(SELECTED_EIGHT)
    selected = [copy.deepcopy(row) for row in groups if row.get("group_id") in wanted]
    if [row.get("group_id") for row in selected] != list(SELECTED_EIGHT):
        raise ZBatchError("八组正例的组序或内容源漂移")
    return selected


def event_line(record: Mapping[str, Any]) -> str:
    anchors = "；".join(str(value) for value in record.get("anchors") or [])
    return f"- 事件：{record['text']}｜示例短引：{anchors}"


def render_positive_examples() -> tuple[str, dict[str, Any]]:
    lines = [
        "【异题材正例区｜例子不是当前章事实】",
        "下面材料只教事实颗粒度。禁止输出例子中的人物、地点、情节、示例短引或虚构锚。",
        "示例短引不是当前章 anchor_id；当前章 anchors 只准逐字复制当前冻结目录中的 ID。",
        "",
    ]
    record_count = 0
    groups = load_selected_examples()
    for group in groups:
        lines.append(
            f"### {group['group_id']}｜{group['pathology_type']}｜{group['subpattern']}"
        )
        lines.append("材料：" + "".join(group["source_scenario"]))
        lines.append("刚好版（正例）：")
        records = group["just_right"]["records"]
        record_count += len(records)
        lines.extend(event_line(row) for row in records)
        lines.append("教学点：" + group["just_right"]["teaching_point"])
        lines.append("")

    lines.extend(
        [
            "### COG-BG-01｜认知、意愿与长期背景分别单列",
            "材料：旧值班簿写明，河堤泵站每逢汛期都由夜班人工复核闸门。档案员林澈据此判断，自动记录不足以证明昨夜闸门状态。林澈决定次日询问夜班值守人。",
            "刚好版（正例）：",
            "- 事件：旧值班簿记载，河堤泵站每逢汛期都由夜班人工复核闸门。｜示例短引：旧值班簿写明，河堤泵站每逢汛期都由夜班人工复核闸门。",
            "- 事件：档案员林澈判断自动记录不足以证明昨夜闸门状态。｜示例短引：档案员林澈据此判断，自动记录不足以证明昨夜闸门状态。",
            "- 事件：林澈决定次日询问夜班值守人。｜示例短引：林澈决定次日询问夜班值守人。",
            "教学点：长期背景、当前认知和后续意愿是三个可分别判真的事实，不得合成一条“得知”长句，也不得因它们不是身体动作而漏掉。",
            "",
            "### UNRESOLVED-01｜同段多个未解问题逐条拆开",
            "材料：检验员查看封存箱后，仍无法确定铅封由谁更换，也不知道箱内清单何时被抽走；摄像记录为何中断同样没有答案。",
            "刚好版（正例）：",
            "- 事件：检验员仍无法确定封存箱铅封由谁更换。｜示例短引：仍无法确定铅封由谁更换。",
            "- 事件：检验员仍不知道箱内清单何时被抽走。｜示例短引：也不知道箱内清单何时被抽走。",
            "- 事件：检验员尚未查明摄像记录为何中断。｜示例短引：摄像记录为何中断同样没有答案。",
            "教学点：每个未解问题都有独立真假边界，必须逐条列出，不能用一条“得知多个问题仍未解决”吞并。",
            "",
            "### ANCHOR-COPY-01｜anchor_id 逐字誊抄微型示范",
            "虚构目录片段：[{\"anchor_id\":\"E9001\",\"quote\":\"仓管员核对封条编号。\"},{\"anchor_id\":\"E9002\",\"quote\":\"核对后确认编号一致。\"}]",
            "正确事件 JSON：{\"event_id\":\"EV-C0099-01\",\"event\":\"仓管员核对封条后确认编号一致。\",\"anchors\":[{\"anchor_id\":\"E9001\"},{\"anchor_id\":\"E9002\"}]} ",
            "教学点：E9001、E9002 必须逐字复制，不能誊成 E901、E0901、E9101；这些虚构 ID 不得用于当前章。",
            "",
            "【正例区结束】现在只处理 user 消息中的当前章。",
        ]
    )
    block = "\n".join(lines)
    return block, {
        "retained_source_group_ids": list(SELECTED_EIGHT),
        "retained_source_group_count": 8,
        "retained_just_right_record_count": record_count,
        "added_content_groups": ["COG-BG-01", "UNRESOLVED-01"],
        "added_anchor_copy_group": "ANCHOR-COPY-01",
        "full_triad_negative_examples_injected": False,
        "bytes": len(block.encode("utf-8")),
        "sha256": sha256_text(block),
    }


def render_system(chapter: int) -> tuple[str, dict[str, Any]]:
    examples, examples_meta = render_positive_examples()
    system = f"""你是中文网络小说单章的“中性原子事件抽取器”。你的任务不是摘要、评价、分类或预测后文，而是高召回、可核验地列出本章发生或明确陈述的中性原子事实，并为每条绑定证据锚。

【信息边界与来源分工】
1. 只使用当前 user 消息中的连续章节正文和冻结证据目录，禁止使用本章之后的知识、常识补全或未提供的实体信息。
2. 连续正文用于理解语义、时间顺序、指代和原文明示的因果；冻结目录只用于选择 anchor_id，不得把割裂短引当成唯一正文。
3. 猜测、怀疑、计划、问题和意愿必须保留其认知强度，不得改写成已确认的客观事实。

【判断规则】
1. 一条事实必须能回答：谁或什么，在什么原文明示条件下，做了什么或发生了什么，产生了什么明示结果。正文没有某类限定时不得补造。
2. 主体可为人物、群体、物品、地点、制度、信息或状态。正文能解析姓名时，event 必须显式写姓名，不得用“他／她／其／对方／有人”代替。
3. 可抽动作包括身体行动，也包括原文明示的得知、认出、判断、决定、同意、拒绝、承诺、担忧、计划、身份变化、关系变化、物品归属变化和规则生效。
4. 回忆中已发生且改变当前身份、资源、能力、关系、风险、约束或后续选择的背景事实可以单列；普通外貌、气氛、比喻、修辞、静态百科、重复复述和作者附言不抽。
5. 每条只保留一个中心事实头。不同主体、不同动作、不同结果，或任一部分可独立判真时拆开；同一主体围绕同一对象连续完成且共同产生一个完成态的必要步骤可合写。
6. 因为、所以、为了、如果、只有、直到、随后等关系只有原文明示时才写，不得把先后自动改写成因果。
7. 太大错误：把可独立判真的动作、背景、认知、意愿或多个未解问题吞成一条；太小错误：把同一主体、同一对象、共同形成一个完成态的必要步骤切成词组碎片。
8. 回忆或背景类事实不得把多个对象、多个时期合成一条长“得知”句；长期背景、当前认知、后续意愿和每个独立未解问题各自单列。
9. 只写“面临情况”“涉及问题”“发生变化”“进行处理”等空泛句不合格，必须写具体主体、动作、对象和明示结果。

【证据规则】
1. 每条至少一个锚；所有锚合起来必须直接支撑 event 的主体、动作、结果和关键限定，只能证明半句的锚不合格。
2. 选择按原文顺序排列的最小非冗余锚集合。同一事件内 anchor_id 不重复；不同事件可以共用同一 anchor_id。
3. 证据不足时缩回原文能证明的范围，禁止靠常识补齐。

【静默检查】
先完整阅读正文，再逐段列候选，检查人物进出、物品转移、状态完成、明确安排、认知与意愿、背景约束和未解问题；随后逐条检查原子性、长度与锚。不要输出检查过程。

{examples}

【输出合同与硬红线｜交卷前以本节为准】
只输出一个合法 JSON 对象，不要代码围栏、解释或额外字段：
{{
  "schema_version": "z-event-v1",
  "chapter": {chapter},
  "events": [
    {{
      "event_id": "EV-C{chapter:04d}-01",
      "event": "一句包含明确主体、动作、明示结果和必要限定的中性原子事实",
      "anchors": [{{"anchor_id": "E0001"}}]
    }}
  ]
}}
1. event_id 按正文顺序从 EV-C{chapter:04d}-01 连续编号；events 不得为空；不得输出重复事件。
2. 每条 event 不超过 {MAX_EVENT_NONSPACE_CHARS} 个非空字符，超过 {MAX_EVENT_NONSPACE_CHARS} 个非空字符的该条不合格；不得靠删掉原文明示要素硬压长度，应把独立事实拆开。
3. 回忆或背景类事实不得把多个对象、多个时期合成一条长“得知”句，各自单列。
4. anchor_id 必须从当前冻结目录逐字复制，格式固定为大写 E 加 4 位数字；输出前逐条确认每个 ID 真实存在于当前目录。
5. anchors 只能放 anchor_id；同一事件内不重复，不同事件可以共用同一锚。"""
    if z68.request_has_prohibited_input({"messages": [{"role": "system", "content": system}]}):
        raise ZBatchError("v2 system 夹入禁入材料")
    required_order = [
        "【信息边界与来源分工】",
        "【判断规则】",
        "【证据规则】",
        "【异题材正例区｜例子不是当前章事实】",
        "【输出合同与硬红线｜交卷前以本节为准】",
    ]
    positions = [system.index(marker) for marker in required_order]
    if positions != sorted(positions):
        raise ZBatchError("v2 system 段序漂移")
    return system, {
        "chapter": chapter,
        "message_count": 1,
        "section_order": required_order,
        "examples": examples_meta,
        "event_nonspace_character_limit": MAX_EVENT_NONSPACE_CHARS,
        "sha256": sha256_text(system),
        "bytes": len(system.encode("utf-8")),
    }


FINAL_REMINDER = f"""【最终提醒｜交卷前逐条自查】
1. 每条 event 最多 {MAX_EVENT_NONSPACE_CHARS} 个非空字符；原文明示的独立事实要拆开，不得压成超长句。
2. 每个 anchor_id 必须按大写 E＋4 位数字的格式从冻结目录逐字复制。
3. 只用当前冻结目录真实存在的 ID；同一事件内不重复，不同事件可以共用同一锚。"""


def build_candidate_body(chapter: int) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline, baseline_meta = z70.build_baseline_body(chapter)
    if baseline["max_tokens"] != MAX_TOKENS or len(baseline["messages"]) != 2:
        raise ZBatchError(f"第{chapter}章32k基线形状漂移")
    system, system_meta = render_system(chapter)
    user = str(baseline["messages"][1]["content"]).rstrip() + "\n\n" + FINAL_REMINDER
    candidate = copy.deepcopy(baseline)
    candidate["messages"] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    changed = z70.deep_diff_paths(baseline, candidate)
    if changed != ["$.messages[0].content", "$.messages[1].content"]:
        raise ZBatchError(f"第{chapter}章 v2 注入混入额外字段变化：{changed}")
    prohibited = z68.request_has_prohibited_input(candidate)
    if prohibited:
        raise ZBatchError(f"第{chapter}章 v2 请求夹入禁入材料：{prohibited}")
    return candidate, {
        "schema_version": "z77-request-diff-v1",
        "chapter": chapter,
        "baseline": baseline_meta,
        "changed_paths": changed,
        "message_roles_before": [row["role"] for row in baseline["messages"]],
        "message_roles_after": [row["role"] for row in candidate["messages"]],
        "single_system_message_after": True,
        "top_level_unchanged_except_messages": all(
            candidate[key] == baseline[key] for key in baseline if key != "messages"
        ),
        "system": system_meta,
        "user_final_reminder_sha256": sha256_text(FINAL_REMINDER),
        "baseline_canonical_sha256": z68.canonical_sha(baseline),
        "candidate_canonical_sha256": z68.canonical_sha(candidate),
    }


RETRY_SYSTEM = f"""你只修正一个被程序打回的中性事件，不重抽整章，不新增与原事件无关的事实。
若原事件含多个可独立判真的事实，拆成多条替换项；否则保留一条。每条 event 为 6～{MAX_EVENT_NONSPACE_CHARS} 个非空字符，保留原文明示的主体、动作、结果与必要限定，禁止编造。
anchors 只能从本次 user 消息的冻结目录逐字复制；anchor_id 格式固定为大写 E 加 4 位数字，同一替换项内不得重复。不同替换项可以共用同一锚。
只输出合法 JSON：{{"replacement_events":[{{"event":"修正后的事实句","anchors":[{{"anchor_id":"E0001"}}]}}]}}。不要输出 event_id、解释或额外字段。"""


def build_retry_messages(
    *,
    chapter: int,
    original_event: Mapping[str, Any],
    violations: list[str],
    chapter_text: str,
    catalog: list[dict[str, Any]],
) -> list[dict[str, str]]:
    user = (
        f"当前章：{chapter}\n"
        f"程序打回原因：{json.dumps(violations, ensure_ascii=False)}\n"
        f"只重写这一条：{json.dumps(original_event, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "【连续章节正文｜只供核对原事件，不得重抽其他事件】\n"
        f"{chapter_text}\n\n"
        "【冻结证据目录｜只准逐字复制其中 ID】\n"
        f"{json.dumps(catalog, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "只交 replacement_events；修正范围不得越出被打回事件。"
    )
    messages = [
        {"role": "system", "content": RETRY_SYSTEM},
        {"role": "user", "content": user},
    ]
    prohibited = z68.request_has_prohibited_input({"messages": messages})
    if prohibited:
        raise ZBatchError(f"第{chapter}章定点重试夹入禁入材料：{prohibited}")
    return messages


def build_run_contract(path: Path) -> dict[str, Any]:
    raw = read_json(z68.SAMPLING_CONTRACT)
    raw["contract_version"] = "z77-fact-sheet-v2-transport-v1"
    status = "approved_transport_reference"
    raw["profiles"][PROFILE] = {
        "status": status,
        "note": "第77道隔离投影；主采样32k，违规事件定点重写8k。",
        "stages": {
            "neutral_extract": {
                "temperature": 0.2,
                "max_tokens": MAX_TOKENS,
                "n": 1,
                "reasoning_effort": "medium",
                "response_format": {"type": "json_object"},
                "status": status,
            },
            "targeted_retry": {
                "temperature": 0.2,
                "max_tokens": RETRY_MAX_TOKENS,
                "n": 1,
                "reasoning_effort": "medium",
                "response_format": {"type": "json_object"},
                "status": status,
            },
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
        raise ZBatchError("第77道主请求不能由本轮运输合同逐字段复现")


def copy_inputs(run_dir: Path) -> list[dict[str, Any]]:
    receipts = z70.copy_frozen_inputs(run_dir)
    provenance_dir = run_dir / "provenance/source_observation"
    provenance_dir.mkdir(parents=True, exist_ok=True)
    for source, expected, target_name in (
        (SOURCE_V1_BLOCK, SOURCE_V1_BLOCK_SHA256, "事实说明书加八组正例_v1.txt"),
        (SOURCE_ARM2_ADJUDICATION, SOURCE_ARM2_ADJUDICATION_SHA256, "旧臂2逐条判分账.json"),
    ):
        if z68.sha256_file(source) != expected:
            raise ZBatchError(f"第77道旧观察源 SHA 漂移：{source}")
        target = provenance_dir / target_name
        shutil.copyfile(source, target)
        receipts.append(
            {
                "source": str(source),
                "source_sha256": expected,
                "target": target.relative_to(run_dir).as_posix(),
                "target_sha256": z68.sha256_file(target),
            }
        )
    return receipts


def deduplication_receipt() -> dict[str, Any]:
    return {
        "schema_version": "z77-system-deduplication-v1",
        "precedence": "事实说明书判断表述优先，原合同的来源边界、四要素、原子性、证据与输出外壳保留一次",
        "merged_duplicates": [
            {"topic": "任务定位", "old_locations": ["原system开头", "说明书开头"], "new_location": "单system开头"},
            {"topic": "主体与四要素", "old_locations": ["原system强制句式", "说明书第一节"], "new_location": "判断规则1～3"},
            {"topic": "原子拆分", "old_locations": ["原system原子性", "说明书第二节"], "new_location": "判断规则5～8"},
            {"topic": "排除项", "old_locations": ["原system什么算事件", "说明书第三节"], "new_location": "判断规则4与9"},
            {"topic": "证据锚", "old_locations": ["原system证据锚", "说明书第四节"], "new_location": "证据规则1～3"},
            {"topic": "静默逐段检查", "old_locations": ["原system静默流程", "说明书第五节"], "new_location": "静默检查"},
        ],
        "moved_near_output": ["100非空字符上限", "背景长得知句禁合并", "anchor_id逐字复制与E加4位数字"],
        "clarified": "同一事件内锚不重复；不同事件可以共用同一锚",
        "full_triad_negatives": "不注入；太大与太小错误压成判断规则第7条",
    }


def build_package() -> dict[str, Any]:
    systems: dict[str, Any] = {}
    for chapter in TARGET_CHAPTERS:
        system, meta = render_system(chapter)
        systems[str(chapter)] = {"content": system, "meta": meta}
    return {
        "schema_version": "z77-fact-sheet-injection-package-v2",
        "status": "candidate_silver_only",
        "event_length_threshold": length_threshold_receipt(),
        "systems": systems,
        "user_final_reminder": FINAL_REMINDER,
        "user_final_reminder_sha256": sha256_text(FINAL_REMINDER),
        "targeted_retry_system": RETRY_SYSTEM,
        "targeted_retry_system_sha256": sha256_text(RETRY_SYSTEM),
        "targeted_retry_policy": {
            "eligible": ["event超过100个非空字符", "anchor_id格式非法或不在当前冻结目录"],
            "per_event_limit": MAX_TARGETED_RETRIES_PER_EVENT,
            "per_chapter_limit": MAX_TARGETED_RETRIES_PER_CHAPTER,
            "total_limit": MAX_TARGETED_RETRIES_TOTAL,
            "other_errors": "hard_stop_no_repair",
        },
        "deduplication": deduplication_receipt(),
    }


def prepare(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.exists():
        raise ZBatchError(f"运行目录已存在，拒绝复跑：{run_dir}")
    source_inputs = z70.assert_source_inputs()
    protected = assert_protected()
    run_dir.mkdir(parents=True)
    build_run_contract(run_dir / RUN_LOCAL_CONTRACT)
    copied_inputs = copy_inputs(run_dir)
    package = build_package()
    package_path = run_dir / "prompt_candidates/事实说明书注入包_v2.json"
    write_json(package_path, package)
    write_json(run_dir / "prompt_candidates/去重与重排差异账.json", package["deduplication"])
    rows = []
    for chapter in TARGET_CHAPTERS:
        baseline, _ = z70.build_baseline_body(chapter)
        candidate, diff = build_candidate_body(chapter)
        assert_body_matches_contract(candidate, run_dir)
        baseline_path = run_dir / f"baseline_requests/ch{chapter:04d}.json"
        prepared_path = run_dir / f"prepared_requests/ch{chapter:04d}.json"
        diff_path = run_dir / f"request_diffs/ch{chapter:04d}.json"
        write_json(baseline_path, baseline)
        write_json(prepared_path, candidate)
        write_json(diff_path, diff)
        system_path = run_dir / f"prompt_candidates/system_ch{chapter:04d}.txt"
        system_path.parent.mkdir(parents=True, exist_ok=True)
        system_path.write_text(candidate["messages"][0]["content"], encoding="utf-8")
        rows.append(
            {
                "chapter": chapter,
                "baseline_request_sha256": z68.sha256_file(baseline_path),
                "prepared_request_sha256": z68.sha256_file(prepared_path),
                "request_diff_sha256": z68.sha256_file(diff_path),
                "system_prompt_sha256": z68.sha256_file(system_path),
            }
        )
    preflight = {
        "schema_version": "z77-preflight-v1",
        "status": "pass_zero_call_prepared",
        "created_at": z68.now_iso(),
        "run_id": run_dir.name,
        "model_api_calls": 0,
        "network_attempts": 0,
        "target_chapters": list(TARGET_CHAPTERS),
        "main_samples_per_chapter": 1,
        "sampling": {
            "main": {"model": "deepseek-v4-flash", "temperature": 0.2, "max_tokens": MAX_TOKENS, "n": 1, "reasoning_effort": "medium", "response_format": {"type": "json_object"}},
            "targeted_retry": {"model": "deepseek-v4-flash", "temperature": 0.2, "max_tokens": RETRY_MAX_TOKENS, "n": 1, "reasoning_effort": "medium", "response_format": {"type": "json_object"}},
        },
        "event_length_threshold": length_threshold_receipt(),
        "targeted_retry_policy": package["targeted_retry_policy"],
        "source_inputs": source_inputs,
        "copied_inputs": copied_inputs,
        "protected_before": protected,
        "package": {
            "path": package_path.relative_to(run_dir).as_posix(),
            "sha256": z68.sha256_file(package_path),
        },
        "producer": {
            "path": Path(__file__).relative_to(ROOT).as_posix(),
            "sha256": z68.sha256_file(Path(__file__)),
        },
        "rows": rows,
    }
    write_json(run_dir / "preflight.json", preflight)
    write_json(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z77-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "prepared",
            "model_api_calls": 0,
            "network_attempts": 0,
        },
    )
    verify_prepared(run_dir, require_zero_call=True)
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


def verify_prepared(run_dir: Path, *, require_zero_call: bool) -> dict[str, Any]:
    preflight = read_json(run_dir / "preflight.json")
    manifest = read_json(run_dir / "run_manifest.json")
    if preflight.get("status") != "pass_zero_call_prepared":
        raise ZBatchError("第77道预演状态漂移")
    if preflight.get("model_api_calls") != 0 or preflight.get("network_attempts") != 0:
        raise ZBatchError("第77道预演调用账不为0")
    if require_zero_call and (manifest.get("status") != "prepared" or call_artifacts_present(run_dir)):
        raise ZBatchError("第77道目录不是可首次运行的零调用状态")
    if z70.assert_source_inputs() != preflight["source_inputs"]:
        raise ZBatchError("第77道冻结输入源漂移")
    if z68.tree_fingerprint(run_dir / "inputs") != preflight["source_inputs"]:
        raise ZBatchError("第77道隔离输入漂移")
    producer = ROOT / preflight["producer"]["path"]
    if z68.sha256_file(producer) != preflight["producer"]["sha256"]:
        raise ZBatchError("第77道运行器 prepare 后漂移")
    if assert_protected() != preflight["protected_before"]:
        raise ZBatchError("第77道保护件漂移")
    expected_package = build_package()
    package_path = run_dir / preflight["package"]["path"]
    if read_json(package_path) != expected_package:
        raise ZBatchError("第77道 v2 注入包不能机械重建")
    checks = []
    for chapter in TARGET_CHAPTERS:
        expected, _ = build_candidate_body(chapter)
        actual = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        assert_body_matches_contract(actual, run_dir)
        passed = (
            expected == actual
            and [row["role"] for row in actual["messages"]] == ["system", "user"]
            and actual["messages"][1]["content"].endswith(FINAL_REMINDER)
            and not z68.request_has_prohibited_input(actual)
        )
        if not passed:
            raise ZBatchError(f"第{chapter}章 v2 请求不能机械重建")
        checks.append({"chapter": chapter, "passed": True})
    receipt = {
        "schema_version": "z77-prepared-verification-v1",
        "status": "pass",
        "require_zero_call": require_zero_call,
        "checks": checks,
        "protected_unchanged": True,
        "package_rebuilt_equal": True,
    }
    write_json(run_dir / "prepared_request_verification.json", receipt)
    return receipt


def acquire_run_claim(run_dir: Path) -> dict[str, Any]:
    claim_path = run_dir / RUN_CLAIM
    claim = {
        "schema_version": "z77-run-claim-v1",
        "status": "claimed_do_not_resume",
        "claimed_at": z68.now_iso(),
        "pid": os.getpid(),
    }
    try:
        descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ZBatchError("第77道已经开跑或曾中断，拒绝重复采样") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(claim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def analyze_main_response(
    data: Any, *, chapter: int, catalog: list[dict[str, Any]]
) -> dict[str, Any]:
    hard_reasons: list[str] = []
    eligible: list[dict[str, Any]] = []
    catalog_ids = {str(row.get("anchor_id")) for row in catalog if isinstance(row, dict)}
    if not isinstance(data, dict) or set(data) != neutral_extract.ROOT_KEYS:
        return {"hard_reasons": ["事件根外壳字段错误"], "eligible": []}
    if data.get("schema_version") != neutral_extract.EVENT_SCHEMA_VERSION:
        hard_reasons.append("事件 schema 错误")
    if data.get("chapter") != chapter:
        hard_reasons.append("章号错误")
    events = data.get("events")
    if not isinstance(events, list) or not events:
        hard_reasons.append("events 不是非空数组")
        return {"hard_reasons": hard_reasons, "eligible": []}
    observed_ids: list[str] = []
    for index, event in enumerate(events, 1):
        expected_id = f"EV-C{chapter:04d}-{index:02d}"
        violations: list[str] = []
        if not isinstance(event, dict) or set(event) != neutral_extract.EVENT_KEYS:
            hard_reasons.append(f"{expected_id} 事件字段错误")
            continue
        event_id = event.get("event_id")
        observed_ids.append(str(event_id))
        if event_id != expected_id:
            hard_reasons.append(f"{expected_id} 事件 ID 不连续")
        summary = event.get("event")
        if not isinstance(summary, str):
            hard_reasons.append(f"{expected_id} event 不是字符串")
        else:
            length = nonspace_chars(summary)
            if length < 6:
                hard_reasons.append(f"{expected_id} event 少于6个非空字符")
            elif length > MAX_EVENT_NONSPACE_CHARS:
                violations.append(f"event_nonspace_chars={length}>{MAX_EVENT_NONSPACE_CHARS}")
            if any(label in summary for label in neutral_extract.CLASSIFICATION_LABELS):
                hard_reasons.append(f"{expected_id} 夹带分类标签")
        anchors = event.get("anchors")
        anchor_ids: list[str] = []
        if not isinstance(anchors, list) or not anchors:
            hard_reasons.append(f"{expected_id} anchors 不是非空数组")
        else:
            for anchor in anchors:
                if not isinstance(anchor, dict) or set(anchor) != neutral_extract.ANCHOR_KEYS:
                    hard_reasons.append(f"{expected_id} anchor 字段错误")
                    continue
                anchor_id = anchor.get("anchor_id")
                if not isinstance(anchor_id, str):
                    violations.append("anchor_id_not_string")
                    continue
                anchor_ids.append(anchor_id)
                if ANCHOR_ID_PATTERN.fullmatch(anchor_id) is None:
                    violations.append(f"anchor_id_bad_format:{anchor_id}")
                elif anchor_id not in catalog_ids:
                    violations.append(f"anchor_id_not_in_catalog:{anchor_id}")
            if len(anchor_ids) != len(set(anchor_ids)):
                hard_reasons.append(f"{expected_id} 同一事件 anchor_id 重复")
        if violations:
            eligible.append(
                {
                    "index": index - 1,
                    "event_id": expected_id,
                    "violations": sorted(set(violations)),
                    "original_event": copy.deepcopy(event),
                }
            )
    if len(observed_ids) != len(set(observed_ids)):
        hard_reasons.append("事件 ID 重复")
    return {
        "hard_reasons": sorted(set(hard_reasons)),
        "eligible": eligible,
        "event_count": len(events),
    }


def validate_replacements(
    data: Any,
    *,
    catalog: list[dict[str, Any]],
    allow_multiple: bool,
) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or set(data) != RETRY_ROOT_KEYS:
        raise ZBatchError("定点重试根字段不等于 replacement_events 合同")
    rows = data.get("replacement_events")
    if not isinstance(rows, list) or not rows or len(rows) > 4:
        raise ZBatchError("定点重试替换条数必须为1～4")
    if not allow_multiple and len(rows) != 1:
        raise ZBatchError("仅锚ID违规的事件不得在定点重试时拆成多条")
    catalog_ids = {str(row.get("anchor_id")) for row in catalog if isinstance(row, dict)}
    result = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != RETRY_EVENT_KEYS:
            raise ZBatchError(f"定点重试替换项{index}字段错误")
        summary = row.get("event")
        if not isinstance(summary, str) or not 6 <= nonspace_chars(summary) <= MAX_EVENT_NONSPACE_CHARS:
            raise ZBatchError(f"定点重试替换项{index}长度仍不合格")
        if any(label in summary for label in neutral_extract.CLASSIFICATION_LABELS):
            raise ZBatchError(f"定点重试替换项{index}夹带分类标签")
        anchors = row.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            raise ZBatchError(f"定点重试替换项{index}没有锚")
        ids: list[str] = []
        for anchor in anchors:
            if not isinstance(anchor, dict) or set(anchor) != neutral_extract.ANCHOR_KEYS:
                raise ZBatchError(f"定点重试替换项{index}锚字段错误")
            anchor_id = anchor.get("anchor_id")
            if (
                not isinstance(anchor_id, str)
                or ANCHOR_ID_PATTERN.fullmatch(anchor_id) is None
                or anchor_id not in catalog_ids
            ):
                raise ZBatchError(f"定点重试替换项{index}仍含非法锚：{anchor_id}")
            ids.append(anchor_id)
        if len(ids) != len(set(ids)):
            raise ZBatchError(f"定点重试替换项{index}锚重复")
        result.append(copy.deepcopy(row))
    return result


def apply_replacements(
    original: Mapping[str, Any],
    *,
    chapter: int,
    replacements: Mapping[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(original["events"]):
        if index in replacements:
            rows.extend(copy.deepcopy(replacements[index]))
        else:
            rows.append(
                {
                    "event": str(event["event"]),
                    "anchors": copy.deepcopy(event["anchors"]),
                }
            )
    events = []
    for serial, row in enumerate(rows, 1):
        events.append(
            {
                "event_id": f"EV-C{chapter:04d}-{serial:02d}",
                "event": row["event"],
                "anchors": row["anchors"],
            }
        )
    return {
        "schema_version": neutral_extract.EVENT_SCHEMA_VERSION,
        "chapter": chapter,
        "events": events,
    }


def chapter_text(run_dir: Path, chapter: int) -> str:
    matches = sorted((run_dir / "inputs/chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise ZBatchError(f"第{chapter}章隔离正文数不是1")
    return matches[0].read_text(encoding="utf-8")


def acquire_retry(
    *,
    transport: api_transport.ApiTransport,
    run_dir: Path,
    chapter: int,
    row: Mapping[str, Any],
    catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_id = f"z77_ch{chapter:04d}_{row['event_id'].lower()}"
    messages = build_retry_messages(
        chapter=chapter,
        original_event=row["original_event"],
        violations=list(row["violations"]),
        chapter_text=chapter_text(run_dir, chapter),
        catalog=catalog,
    )
    result = transport.call(stage="targeted_retry", case_id=case_id, messages=messages)
    if result.finish_reason != "stop" or not result.content.strip():
        raise ZBatchError(f"第{chapter}章 {row['event_id']} 定点重试未stop或正文为空")
    parsed = candidate_envelope.parse_json_content(result.content)
    allow_multiple = any(value.startswith("event_nonspace_chars=") for value in row["violations"])
    replacements = validate_replacements(parsed, catalog=catalog, allow_multiple=allow_multiple)
    receipt = {
        "chapter": chapter,
        "original_event_id": row["event_id"],
        "violations": list(row["violations"]),
        "attempt": 1,
        "max_attempts_per_event": MAX_TARGETED_RETRIES_PER_EVENT,
        "replacement_count": len(replacements),
        "original_event": row["original_event"],
        "replacement_events": replacements,
        "request_sha256": z68.sha256_file(run_dir / f"requests/targeted_retry/{case_id}_request.json"),
        "raw_response_sha256": z68.sha256_file(run_dir / f"responses/targeted_retry/{case_id}_raw.json"),
    }
    return replacements, receipt


def run(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    verify_prepared(run_dir, require_zero_call=True)
    preflight = read_json(run_dir / "preflight.json")
    claim = acquire_run_claim(run_dir)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z77-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "running_do_not_resume",
            "run_claim": claim,
        },
    )
    completed: list[int] = []
    retry_total = 0
    retry_ledger: list[dict[str, Any]] = []
    try:
        transport = api_transport.ApiTransport.from_bundle(
            load_bundle(run_dir), run_dir=run_dir, max_calls=MAX_NETWORK_ATTEMPTS
        )
        for chapter in TARGET_CHAPTERS:
            case_id = f"z77_ch{chapter:04d}"
            prepared = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
            assert_body_matches_contract(prepared, run_dir)
            result = transport.call(
                stage="neutral_extract", case_id=case_id, messages=prepared["messages"]
            )
            actual = read_json(run_dir / f"requests/neutral_extract/{case_id}_request.json")
            if actual.get("body") != prepared or result.request_record.get("body") != prepared:
                raise ZBatchError(f"第{chapter}章实际主请求不等于 prepared")
            if result.finish_reason != "stop" or not result.content.strip():
                raise ZBatchError(f"第{chapter}章主回包未stop或正文为空")
            model_json = candidate_envelope.parse_json_content(result.content)
            write_json(run_dir / f"01_extract/model_json_original/ch{chapter:04d}.json", model_json)
            catalog = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")["entries"]
            analysis = analyze_main_response(model_json, chapter=chapter, catalog=catalog)
            write_json(run_dir / f"01_extract/initial_audits/ch{chapter:04d}.json", analysis)
            if analysis["hard_reasons"]:
                raise ZBatchError(f"第{chapter}章出现非授权失败面：{analysis['hard_reasons']}")
            eligible = analysis["eligible"]
            if len(eligible) > MAX_TARGETED_RETRIES_PER_CHAPTER:
                raise ZBatchError(
                    f"第{chapter}章违规事件{len(eligible)}条，超过定点重试上限"
                )
            if retry_total + len(eligible) > MAX_TARGETED_RETRIES_TOTAL:
                raise ZBatchError("第77道定点重试总上限已满")
            replacements: dict[int, list[dict[str, Any]]] = {}
            for row in eligible:
                fixed, receipt = acquire_retry(
                    transport=transport,
                    run_dir=run_dir,
                    chapter=chapter,
                    row=row,
                    catalog=catalog,
                )
                replacements[int(row["index"])] = fixed
                retry_total += 1
                retry_ledger.append(receipt)
                append_jsonl(run_dir / "targeted_retry_ledger.jsonl", receipt)
            final_json = apply_replacements(
                model_json, chapter=chapter, replacements=replacements
            )
            materialized, audit = neutral_extract.process_model_data(
                final_json, chapter=chapter, catalog=catalog
            )
            write_json(run_dir / f"01_extract/model_json/ch{chapter:04d}.json", final_json)
            write_json(run_dir / f"01_extract/events/ch{chapter:04d}.json", materialized)
            write_json(run_dir / f"01_extract/program_audits/ch{chapter:04d}.json", audit)
            completed.append(chapter)
    except BaseException as exc:
        attempts = z68.read_jsonl(run_dir / "call_attempts.jsonl")
        hard_stop = {
            "schema_version": "z77-hard-stop-v1",
            "status": "hard_stop_no_unapproved_repair",
            "at": z68.now_iso(),
            "completed_chapters": completed,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "targeted_retry_count": retry_total,
            "network_attempts": len(attempts),
            "protected_unchanged": assert_protected() == preflight["protected_before"],
        }
        write_json(run_dir / "hard_stop.json", hard_stop)
        write_json_atomic(
            run_dir / "run_manifest.json",
            {
                "schema_version": "z77-run-manifest-v1",
                "run_id": run_dir.name,
                "status": "hard_stop",
                "completed_chapters": completed,
                "run_claim": claim,
                "network_attempts": len(attempts),
                "targeted_retry_count": retry_total,
            },
        )
        raise
    attempts = z68.read_jsonl(run_dir / "call_attempts.jsonl")
    usage = z68.read_jsonl(run_dir / "usage.jsonl")
    usage_totals: Counter[str] = Counter()
    for row in usage:
        for key, value in (row.get("usage") or {}).items():
            if isinstance(value, int):
                usage_totals[key] += value
    metrics = {
        "schema_version": "z77-run-metrics-v1",
        "status": "completed_candidate_silver_only",
        "chapters_completed": completed,
        "main_logical_calls": len(TARGET_CHAPTERS),
        "targeted_retry_logical_calls": retry_total,
        "successful_responses": len(usage),
        "network_attempts": len(attempts),
        "usage_totals": dict(usage_totals),
        "targeted_retry_ledger": retry_ledger,
    }
    write_json(run_dir / "01_extract/metrics.json", metrics)
    write_json_atomic(
        run_dir / "run_manifest.json",
        {
            "schema_version": "z77-run-manifest-v1",
            "run_id": run_dir.name,
            "status": "completed_candidate_silver_only",
            "chapters_completed": completed,
            "run_claim": claim,
            "network_attempts": len(attempts),
            "targeted_retry_count": retry_total,
        },
    )
    return metrics


def secret_scan(run_dir: Path) -> dict[str, Any]:
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


def verify(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    prepared = verify_prepared(run_dir, require_zero_call=False)
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest.get("status") != "completed_candidate_silver_only":
        raise ZBatchError(f"第77道尚未完成：{manifest.get('status')}")
    preflight = read_json(run_dir / "preflight.json")
    checks: list[dict[str, Any]] = []
    outside_total = 0
    overlength_total = 0
    chapter_invalidations = 0
    for chapter in TARGET_CHAPTERS:
        case_id = f"z77_ch{chapter:04d}"
        prepared_body = read_json(run_dir / f"prepared_requests/ch{chapter:04d}.json")
        actual_body = read_json(run_dir / f"requests/neutral_extract/{case_id}_request.json")["body"]
        final_json = read_json(run_dir / f"01_extract/model_json/ch{chapter:04d}.json")
        audit = read_json(run_dir / f"01_extract/program_audits/ch{chapter:04d}.json")
        catalog = read_json(run_dir / f"inputs/evidence_catalogs/ch{chapter:04d}.json")["entries"]
        reasons, rebuilt = neutral_extract.audit_event_envelope(final_json, chapter, catalog)
        outside = len(rebuilt.get("missing_catalog_anchor_ids") or [])
        overlength = sum(
            1
            for event in final_json["events"]
            if nonspace_chars(str(event["event"])) > MAX_EVENT_NONSPACE_CHARS
        )
        outside_total += outside
        overlength_total += overlength
        if reasons or audit != rebuilt:
            chapter_invalidations += 1
        checks.append(
            {
                "chapter": chapter,
                "actual_equals_prepared": actual_body == prepared_body,
                "final_program_audit_pass": not reasons and audit == rebuilt and audit.get("status") == "pass",
                "outside_catalog_anchor_count": outside,
                "overlength_event_count": overlength,
                "event_count": len(final_json["events"]),
            }
        )
    scan = secret_scan(run_dir)
    protected_unchanged = assert_protected() == preflight["protected_before"]
    passed = (
        prepared["status"] == "pass"
        and all(row["actual_equals_prepared"] and row["final_program_audit_pass"] for row in checks)
        and outside_total == 0
        and overlength_total == 0
        and chapter_invalidations == 0
        and scan["passed"]
        and protected_unchanged
    )
    receipt = {
        "schema_version": "z77-mechanical-verification-v1",
        "status": "pass" if passed else "fail",
        "checks": checks,
        "gates": {
            "outside_catalog_anchor_zero": outside_total == 0,
            "length_rejection_zero": overlength_total == 0,
            "whole_chapter_invalidation_zero": chapter_invalidations == 0,
        },
        "targeted_retry_count": read_json(run_dir / "01_extract/metrics.json")["targeted_retry_logical_calls"],
        "secret_scan": scan,
        "protected_unchanged": protected_unchanged,
    }
    write_json(run_dir / "mechanical_verification.json", receipt)
    if not passed:
        raise ZBatchError("第77道机械复验失败")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "verify", "show-package"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if args.action == "show-package":
        print(json.dumps(build_package(), ensure_ascii=False, indent=2))
        return 0
    result = {
        "prepare": prepare,
        "run": run,
        "verify": verify,
    }[args.action](run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
