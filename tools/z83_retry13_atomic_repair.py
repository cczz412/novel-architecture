#!/usr/bin/env python3
"""第83道续令⑪：受控原子化、单对象修复与 retry13 隔离运行。

这份工具只服务 retry13。旧 retry09～12 的数组合同和封存目录均不回写。
计划分成 13 个父源事件与 32 个逻辑子请求；六个复合父源先由程序冻结事实
闭集，再让模型每次只处理一个事实、只返回一个对象。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import z83_program_side_repair_pilot as z83
import z77_fact_sheet_v2_pilot as z77
from zbatch_modules import api_transport, neutral_extract
from zbatch_modules.evidence_catalog import nonspace_chars
from zbatch_modules.errors import ZBatchError
from zbatch_modules import z83_retry_transport


ROOT = Path(__file__).resolve().parents[1]
RUN_NAME = z83.APPROVED_ATOMIC_SPLIT_TARGET_NAME
DEFAULT_RUN_DIR = ROOT / "runs" / RUN_NAME
RETRY09_RUN_DIR = ROOT / "runs" / z83.APPROVED_CAPACITY_OVERRIDE_TARGET_NAME
RETRY09_ADJUDICATION = RETRY09_RUN_DIR / "review/adjudication_completed.json"
RETRY09_ADJUDICATION_SHA256 = z83.RETRY09_ADJUDICATION_SHA256
CONTRACT_VERSION = "z83-one-to-one-single-object-repair-v1"
PLAN_SCHEMA = "z83-retry13-atomic-plan-v1"
PREFLIGHT_SCHEMA = "z83-retry13-preflight-v1"
MODEL_RESULT_KEYS = {"event", "anchor_ids"}
EVENT_NONSPACE_MIN = 6
EVENT_NONSPACE_MAX = z77.MAX_EVENT_NONSPACE_CHARS
EXPECTED_MAIN_EVENT_COUNTS = {3: 58, 13: 46, 19: 52}
EXPECTED_FINAL_EVENT_COUNTS = {3: 61, 13: 50, 19: 64}
EXPECTED_REWRITTEN_DESCENDANT_COUNTS = {3: 7, 13: 7, 19: 18}
PARENT_ORDER = (
    "EV-C0013-06",
    "EV-C0003-08",
    "EV-C0003-09",
    "EV-C0003-10",
    "EV-C0019-05",
    "EV-C0019-25",
    "EV-C0019-46",
    "EV-C0003-05",
    "EV-C0013-35",
    "EV-C0013-46",
    "EV-C0019-34",
    "EV-C0019-40",
    "EV-C0019-47",
)
DIRECT_PARENT_IDS = {
    "EV-C0013-06",
    "EV-C0003-08",
    "EV-C0003-09",
    "EV-C0003-10",
    "EV-C0019-05",
}
CONDITIONAL_PARENT_IDS = {"EV-C0019-25", "EV-C0019-46"}
ATOMIC_PARENT_IDS = {
    "EV-C0003-05",
    "EV-C0013-35",
    "EV-C0013-46",
    "EV-C0019-34",
    "EV-C0019-40",
    "EV-C0019-47",
}

SUPPLY_DIR = ROOT / "reports/Z83_熔断后合同改造备料_20260722"
SUPPLY_FILES = {
    "single_object_contract": (
        SUPPLY_DIR / "01_一对一单对象输出合同v1_候选草案.md",
        "3ba3def4d6a927c4cc1bc3b4c87e7fdaf940a8177d9d23df51b66a5715e3e674",
    ),
    "immutable_checkpoint": (
        SUPPLY_DIR / "02_单条不可变检查点机制_纸面演算.md",
        "8171fbc9a8b82fde85b15dcdb85466606a7c3b59b25ba75ba9979092203a91e6",
    ),
    "transport_throttle": (
        SUPPLY_DIR / "03_运输节流固定规则v1_候选草案.md",
        "f5a3e10eb00af9f5f976c81f3baefd352ffa94605985b8d807c2043dc0f99bbe",
    ),
}

# 这些文字不是答案样张，而是 retry09 人工判词确认过的事实闭集路由。
# 每个字符串对应一个单对象模型请求；父源只在全部子请求齐套后聚合一次。
ATOMIC_FACT_SPECS: dict[str, tuple[dict[str, Any], ...]] = {
    "EV-C0003-05": (
        {
            "fact": "克莱恩对做工精致的转轮手枪从何而来缺少具体记忆。",
            "permission": "只准单列“转轮手枪来源”这一项记忆缺口，不得带入另外三个未解问题。",
            "support_anchor_candidates": ["E0012", "E0013", "E0014"],
        },
        {
            "fact": "克莱恩对原主是自杀还是他杀缺少具体记忆。",
            "permission": "只准单列“自杀还是他杀”这一项记忆缺口，不得带入另外三个未解问题。",
            "support_anchor_candidates": ["E0012", "E0013", "E0014"],
        },
        {
            "fact": "克莱恩对笔记本上那句话的含义缺少具体记忆。",
            "permission": "只准单列“笔记本那句话的含义”这一项记忆缺口，不得带入另外三个未解问题。",
            "support_anchor_candidates": ["E0012", "E0013", "E0015", "E0016"],
        },
        {
            "fact": "克莱恩对事发前两天是否参与奇怪事情缺少具体记忆。",
            "permission": "只准单列“事发前两天是否参与奇怪事情”这一项记忆缺口，不得带入另外三个未解问题。",
            "support_anchor_candidates": ["E0012", "E0013", "E0016", "E0017"],
        },
    ),
    "EV-C0013-35": (
        {
            "fact": "在专家证实克莱恩确实遗忘且没有其他证据证明他是加害者的前提下，邓恩回答事情理论上结束。",
            "permission": "只准写“确实遗忘且无其他直接加害证据”这一前提及“事情理论上结束”这一回答结论，不得省掉解除直接嫌疑所依赖的前提。",
            "support_anchor_candidates": ["E0110", "E0111", "E0112", "E0113"],
        },
        {
            "fact": "值夜者会从别的途径寻找笔记，只要笔记仍存在就能被发现。",
            "permission": "只准写寻找笔记的行动及“仍存在即可发现”的条件。",
            "support_anchor_candidates": ["E0113", "E0114", "E0115"],
        },
        {
            "fact": "值夜者会核验克莱恩没有诅咒、遗留恶灵味道和对应心理问题。",
            "permission": "只准写放行前的三项并列核验；诅咒、遗留恶灵味道、对应心理问题三项不得省略。",
            "support_anchor_candidates": ["E0115", "E0116", "E0117"],
        },
        {
            "fact": "邓恩说克莱恩能平安、健康地迎接将来的人生。",
            "permission": "只准写邓恩明说的平安、健康迎接将来人生，不得自行加写“核验通过后”等原句未明示的条件因果。",
            "support_anchor_candidates": ["E0117", "E0118"],
        },
    ),
    "EV-C0013-46": (
        {
            "fact": "克莱恩询问那位专家的实际身份。",
            "permission": "只准保留克莱恩的提问，不得代写邓恩的回答。",
            "support_anchor_candidates": ["E0170"],
        },
        {
            "fact": "邓恩回答那位专家是真正的通灵者。",
            "permission": "只准保留邓恩的回答及身份结论，不得代写克莱恩的提问。",
            "support_anchor_candidates": ["E0171", "E0172"],
        },
    ),
    "EV-C0019-34": (
        {
            "fact": "查尼斯门以现代值夜者体系创立者查尼斯大主教的名字命名。",
            "permission": "只准写查尼斯门名称的来源。",
            "support_anchor_candidates": ["E0114", "E0115"],
        },
        {
            "fact": "每个大城市的中央教堂地下都有一扇查尼斯门。",
            "permission": "只准写查尼斯门在大城市中央教堂地下的分布。",
            "support_anchor_candidates": ["E0115", "E0116", "E0117"],
        },
        {
            "fact": "查尼斯门由正式值夜者轮换看守，门内至少另有两位教会看守者。",
            "permission": "只准写轮换看守及门内至少两位看守者这一看守安排。",
            "support_anchor_candidates": ["E0117", "E0118", "E0119"],
        },
        {
            "fact": "查尼斯门内布有数不清的陷阱。",
            "permission": "只准写门内陷阱这一项事实。",
            "support_anchor_candidates": ["E0119"],
        },
        {
            "fact": "邓恩禁止克莱恩随意靠近查尼斯门，否则会沾染厄运。",
            "permission": "只准写禁止靠近与明示后果，不能只保留禁令或只保留后果。",
            "support_anchor_candidates": ["E0119", "E0120"],
        },
    ),
    "EV-C0019-40": (
        {
            "fact": "有的非凡物品太重要、太神奇，被邪恶者得到会造成极大破坏。",
            "permission": "只准写物品同时明示的“太重要、太神奇”性质及落入邪恶者之手的破坏风险，不得把并列关系弱化成二选一。",
            "support_anchor_candidates": ["E0134", "E0135", "E0136"],
        },
        {
            "fact": "这类非凡物品必须严格保密和看管，值夜者也只能在特定情况下使用。",
            "permission": "只准写保密、看管与特定情况下使用的规则。",
            "support_anchor_candidates": ["E0136", "E0137", "E0138"],
        },
        {
            "fact": "部分非凡物品具有活着的特性，会引诱看守者、影响周围并自行逃脱。",
            "permission": "只准写“活着”特性的三个明示表现；引诱、影响、逃脱不得挑选性省略。",
            "support_anchor_candidates": ["E0139", "E0140", "E0141", "E0142"],
        },
        {
            "fact": "这类活着的封印物会造成灾难性后果，因此必须严格控制。",
            "permission": "只准写灾难性后果与严格控制的因果结论。",
            "support_anchor_candidates": ["E0142", "E0143"],
        },
    ),
    "EV-C0019-47": (
        {
            "fact": "邓恩从抽屉底层取出一张纸，让克莱恩查看。",
            "permission": "只准写邓恩取出并交代查看该信息的动作。",
            "support_anchor_candidates": ["E0162", "E0163"],
        },
        {
            "fact": "三年前一位新任大主教失控。",
            "permission": "只准写三年前新任大主教失控，不得写姓名、年龄或其他身份资料。",
            "support_anchor_candidates": ["E0164"],
        },
        {
            "fact": "失控的大主教不知道怎么闯过重重保护，并带着一件0级封印物神秘失踪。",
            "permission": "只准写未知方式限定、闯过重重保护、带走0级封印物并神秘失踪这一连续行动结果；“不知道怎么”不得省略。",
            "support_anchor_candidates": ["E0164", "E0165", "E0166"],
        },
        {
            "fact": "邓恩要求克莱恩认下照片。",
            "permission": "只准写认下照片这一要求，不得把纸张载体或照片中的身份资料并入本条。",
            "support_anchor_candidates": ["E0166"],
        },
        {
            "fact": "若发现照片中的人，克莱恩不得惊动或打扰，必须回来禀报。",
            "permission": "只准写发现后的三项行动要求；不要惊动、不要打扰、回来禀报不得省略。",
            "support_anchor_candidates": ["E0166", "E0167", "E0168"],
        },
        {
            "fact": "克莱恩若违反指令会百分之一千殉职。",
            "permission": "只准写违反指令的明示后果。",
            "support_anchor_candidates": ["E0168"],
        },
    ),
}

DIRECT_FACT_TEXT = {
    "EV-C0013-06": "保持原事件同一中心事实，只补挂能直接支撑来源主张的锚，或删除无支撑措辞。",
    "EV-C0003-08": "保持原事件同一中心事实，只补挂能直接支撑记忆来源的锚，或删除无支撑措辞。",
    "EV-C0003-09": "保持原事件同一中心事实，只补挂能直接支撑结论与问题状态的锚，或删除无支撑措辞。",
    "EV-C0003-10": "保持原事件同一中心事实，只补挂能直接支撑立志或意愿主张的锚，或删除无支撑措辞。",
    "EV-C0019-05": "保持原事件同一中心事实，只补挂能直接支撑全部主张的锚，或删除无支撑措辞。",
}

DIRECT_SUPPORT_ANCHORS = {
    "EV-C0013-06": ["E0015", "E0018", "E0019", "E0020"],
    "EV-C0003-08": ["E0005", "E0022", "E0023"],
    "EV-C0003-09": ["E0005", "E0024"],
    "EV-C0003-10": ["E0005", "E0024", "E0025"],
    "EV-C0019-05": ["E0012", "E0013", "E0014"],
}

CONDITIONAL_FACT_TEXT = {
    "EV-C0019-25": (
        "邓恩说克莱恩不用和罗珊等人做相同事情，因为他是专业人士，并安排他每天上午或下午外出，重点走韦尔奇住所到家之间的各条道路。"
    ),
    "EV-C0019-46": (
        "邓恩说明封印物编号中前一数字表示危险等级、后一数字表示该等级内序号，编号本身不直接说明封印物的具体效果，并以2—125为例说明它是危险级125号封印物。"
    ),
}

CONDITIONAL_SUPPORT_ANCHORS = {
    "EV-C0019-25": ["E0077", "E0078", "E0079", "E0080", "E0081"],
    "EV-C0019-46": ["E0159", "E0160", "E0161"],
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: Any) -> None:
    z83.write_json_atomic(path, value)


def _extract_single_object_system_contract() -> str:
    path, expected = SUPPLY_FILES["single_object_contract"]
    if not path.is_file() or z83.sha256_file(path) != expected:
        raise ZBatchError("一对一单对象合同供料件 SHA 漂移")
    text = path.read_text(encoding="utf-8")
    marker = "## 模型可见硬合同全文\n\n```text\n"
    if text.count(marker) != 1:
        raise ZBatchError("一对一单对象合同找不到唯一模型可见代码块")
    tail = text.split(marker, 1)[1]
    if "\n```" not in tail:
        raise ZBatchError("一对一单对象合同代码块未闭合")
    result = tail.split("\n```", 1)[0]
    if (
        "唯一合法外形：\n{\n  \"event\"" not in result
        or "不得输出 replacement_events" not in result
        or "```" in result
    ):
        raise ZBatchError("单对象合同没有把单对象钉成唯一合法外形")
    return result


def _assert_supply_and_copy(run_dir: Path) -> list[dict[str, Any]]:
    target_root = run_dir / "provenance/approved_supply"
    rows = []
    for label, (source, expected_sha) in SUPPLY_FILES.items():
        if not source.is_file() or z83.sha256_file(source) != expected_sha:
            raise ZBatchError(f"已审收供料件漂移：{label}")
        target = target_root / source.name
        if target.exists():
            if target.read_bytes() != source.read_bytes():
                raise ZBatchError(f"供料隔离副本漂移：{label}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if z83.sha256_file(target) != expected_sha:
            raise ZBatchError(f"供料隔离副本 SHA 不一致：{label}")
        rows.append(
            {
                "label": label,
                "source_path": source.relative_to(ROOT).as_posix(),
                "target_path": target.relative_to(run_dir).as_posix(),
                "sha256": expected_sha,
            }
        )
    return rows


def _adjudication_row_refs(adjudication: Mapping[str, Any], event_id: str) -> list[dict[str, Any]]:
    order = ("anchor_rows", "current_rows", "gold_rows", "risk_rows")
    offsets: dict[str, int] = {}
    running = 0
    for name in order:
        offsets[name] = running
        rows = adjudication.get(name)
        if not isinstance(rows, list):
            raise ZBatchError(f"retry09 判词缺 {name}")
        running += len(rows)
    refs: list[dict[str, Any]] = []
    for name in order:
        rows = adjudication[name]
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                continue
            hit = row.get("event_id") == event_id or event_id in (
                row.get("candidate_event_ids") or []
            )
            if not hit:
                continue
            refs.append(
                {
                    "collection": name,
                    "collection_row": index,
                    "logical_row": offsets[name] + index,
                    "row_sha256": canonical_sha(row),
                    "verdict": row.get("verdict"),
                    "reason": row.get("reason"),
                }
            )
    if not refs:
        raise ZBatchError(f"retry09 判词没有覆盖父源事件：{event_id}")
    return refs


def _conditional_review(
    adjudication: Mapping[str, Any], event_id: str
) -> dict[str, Any]:
    current_rows = [
        row
        for row in adjudication["current_rows"]
        if event_id in (row.get("candidate_event_ids") or [])
    ]
    risk_rows = [
        row for row in adjudication["risk_rows"] if row.get("event_id") == event_id
    ]
    anchor_rows = [
        row for row in adjudication["anchor_rows"] if row.get("event_id") == event_id
    ]
    same_center = False
    reason = ""
    if event_id == "EV-C0019-25":
        same_center = (
            len(current_rows) == 1
            and "漏上午或下午明确时段" in str(current_rows[0].get("reason"))
            and len(risk_rows) == 1
            and risk_rows[0].get("verdict") == "clear"
            and len(anchor_rows) == 1
            and anchor_rows[0].get("verdict") == "valid"
        )
        reason = "缺口只是同一外巡安排里的明示时段，主体、行动和路线中心未变。"
    elif event_id == "EV-C0019-46":
        same_center = (
            len(current_rows) == 1
            and "2-125实例有影子" in str(current_rows[0].get("reason"))
            and len(risk_rows) == 1
            and risk_rows[0].get("verdict") == "clear"
            and len(anchor_rows) == 1
            and anchor_rows[0].get("verdict") == "valid"
        )
        reason = (
            "缺口仍围绕同一封印物编号说明；但当章未明示的抽象边界禁止补写，"
            "因此只按冻结正文可证部分进入。"
        )
    else:
        raise ZBatchError(f"不是获批条件进入项：{event_id}")
    return {
        "source_event_id": event_id,
        "status": "eligible_one_to_one_same_center_fact"
        if same_center
        else "pending_cz_not_sent",
        "same_center_fact": same_center,
        "reason": reason,
        "row_references": _adjudication_row_refs(adjudication, event_id),
        "not_removed_from_parent_plan": True,
        "blocks_batch_release_if_pending": True,
        "model_api_calls": 0,
    }


def _task_id(event_id: str, fact_ordinal: int) -> str:
    return f"{event_id.lower()}-f{fact_ordinal:02d}"


def _parent_task_specs(event_id: str) -> tuple[dict[str, Any], ...]:
    if event_id in ATOMIC_PARENT_IDS:
        return ATOMIC_FACT_SPECS[event_id]
    if event_id in DIRECT_PARENT_IDS:
        return (
            {
                "fact": DIRECT_FACT_TEXT[event_id],
                "permission": DIRECT_FACT_TEXT[event_id],
                "support_anchor_candidates": DIRECT_SUPPORT_ANCHORS[event_id],
            },
        )
    if event_id in CONDITIONAL_PARENT_IDS:
        return (
            {
                "fact": CONDITIONAL_FACT_TEXT[event_id],
                "permission": CONDITIONAL_FACT_TEXT[event_id],
                "support_anchor_candidates": CONDITIONAL_SUPPORT_ANCHORS[event_id],
            },
        )
    raise ZBatchError(f"父源事件不在获批闭集：{event_id}")


def _source_event_map(run_dir: Path) -> dict[str, dict[str, Any]]:
    return z83._event_map(run_dir / "main")


def _copy_retry09_adjudication(run_dir: Path) -> tuple[dict[str, Any], Path]:
    if (
        not RETRY09_ADJUDICATION.is_file()
        or z83.sha256_file(RETRY09_ADJUDICATION) != RETRY09_ADJUDICATION_SHA256
    ):
        raise ZBatchError("retry09 246 行判词来源 SHA 漂移")
    source = read_json(RETRY09_ADJUDICATION)
    if sum(len(source[name]) for name in ("anchor_rows", "current_rows", "gold_rows", "risk_rows")) != 246:
        raise ZBatchError("retry09 判词不再是 246 行")
    target = run_dir / "review/adjudication_reused_from_retry09.json"
    derived = copy.deepcopy(source)
    derived["run_id"] = run_dir.name
    if target.exists():
        if read_json(target) != derived:
            raise ZBatchError("retry13 判词复用件漂移")
    else:
        write_json_atomic(target, derived)
    z83.validate_adjudication(run_dir, target, phase="main")
    return derived, target


def create_plan(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if run_dir.name != RUN_NAME:
        raise ZBatchError("原子化正式计划只准写入 retry13")
    plan_path = run_dir / "repair/atomic_plan.json"
    if plan_path.exists():
        raise ZBatchError("retry13 原子化计划已存在，拒绝覆盖")
    z83.verify_main(run_dir)
    if not (run_dir / "review/build_receipt.json").is_file():
        raise ZBatchError("retry13 须先生成主样复核材料")
    supply = _assert_supply_and_copy(run_dir)
    adjudication, adjudication_path = _copy_retry09_adjudication(run_dir)
    validated = z83.validate_adjudication(run_dir, adjudication_path, phase="main")
    expected_event_sha = {
        str(chapter): value for chapter, value in z83.APPROVED_COMPLETED_EVENT_SHA256.items()
    }
    if validated["event_set_sha256"] != expected_event_sha:
        raise ZBatchError("retry13 主样张不等于 retry03 三章冻结事件 SHA")
    events = _source_event_map(run_dir)
    lineage = z83._validate_main_lineage(run_dir)["rows"]
    reason_codes = z83._collect_retry_reason_codes(run_dir, validated)
    if set(reason_codes) != set(z83.RETRY10_APPROVED_EVENT_IDS):
        raise ZBatchError("retry13 父源闭集不等于 retry09 已核实 13 条")

    conditional_rows = {
        event_id: _conditional_review(adjudication, event_id)
        for event_id in sorted(CONDITIONAL_PARENT_IDS)
    }
    parents: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    for parent_ordinal, event_id in enumerate(PARENT_ORDER, 1):
        event = events[event_id]
        specs = _parent_task_specs(event_id)
        route = (
            "direct_one_to_one"
            if event_id in DIRECT_PARENT_IDS
            else "conditional_one_to_one"
            if event_id in CONDITIONAL_PARENT_IDS
            else "program_atomic_split"
        )
        pending = bool(
            event_id in CONDITIONAL_PARENT_IDS
            and not conditional_rows[event_id]["same_center_fact"]
        )
        parent_tasks = []
        if not pending:
            for fact_ordinal, spec in enumerate(specs, 1):
                task_id = _task_id(event_id, fact_ordinal)
                task = {
                    "task_id": task_id,
                    "parent_ordinal": parent_ordinal,
                    "parent_event_id": event_id,
                    "parent_event_sha256": z83.canonical_sha(event),
                    "source_event_id": lineage[event_id]["source_event_id"],
                    "source_event_sha256": lineage[event_id]["source_event_sha256"],
                    "source_identity_sha256": lineage[event_id]["source_identity_sha256"],
                    "chapter": int(event_id[4:8]),
                    "fact_ordinal": fact_ordinal,
                    "fact_count": len(specs),
                    "fact_target": spec["fact"],
                    "fact_target_sha256": canonical_sha(spec["fact"]),
                    "permission": spec["permission"],
                    "support_anchor_candidates": list(spec["support_anchor_candidates"]),
                    "required_anchor_ids": list(spec["support_anchor_candidates"]),
                    "anchor_binding_policy": "exact_program_prechecked_set",
                    "output_contract": CONTRACT_VERSION,
                    "single_object_required": True,
                    "candidate_silver_only": True,
                }
                tasks.append(task)
                parent_tasks.append(task_id)
        parents.append(
            {
                "parent_ordinal": parent_ordinal,
                "event_id": event_id,
                "chapter": int(event_id[4:8]),
                "event_sha256": z83.canonical_sha(event),
                "source_event_id": lineage[event_id]["source_event_id"],
                "source_event_sha256": lineage[event_id]["source_event_sha256"],
                "source_identity_sha256": lineage[event_id]["source_identity_sha256"],
                "reason_codes": sorted(reason_codes[event_id]),
                "route": "pending_cz_not_sent" if pending else route,
                "fact_count": len(specs),
                "fact_target_sha256_set": [canonical_sha(spec["fact"]) for spec in specs],
                "task_ids": parent_tasks,
                "adjudication_references": _adjudication_row_refs(adjudication, event_id),
                "counts_as_one_parent_rewrite": True,
                "facts_may_not_be_added_or_dropped": True,
            }
        )

    atomic_counts = {
        event_id: len(ATOMIC_FACT_SPECS[event_id]) for event_id in sorted(ATOMIC_PARENT_IDS)
    }
    pending_ids = [row["event_id"] for row in parents if row["route"] == "pending_cz_not_sent"]
    logical_count = len(tasks)
    if not pending_ids and (atomic_counts != {
        "EV-C0003-05": 4,
        "EV-C0013-35": 4,
        "EV-C0013-46": 2,
        "EV-C0019-34": 5,
        "EV-C0019-40": 4,
        "EV-C0019-47": 6,
    } or logical_count != 32):
        raise ZBatchError("retry13 原子化 N 或逻辑请求总量不等于获批冻结值")
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise ZBatchError("retry13 子任务身份重复")
    if len({row["source_identity_sha256"] for row in parents}) != 13:
        raise ZBatchError("retry13 父源稳定身份不是 13 个唯一值")
    plan = {
        "schema_version": PLAN_SCHEMA,
        "status": "ready_zero_call" if not pending_ids else "ready_with_pending_cz_release_block",
        "run_id": run_dir.name,
        "authority": {
            "decision": "CZ 2026-07-22 17:20 亲拍乙：受控一对多原子化",
            "queue_url": "https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc",
            "facts_not_events_invariant": "不得新增事实、不得丢弃有锚事实",
        },
        "source_adjudication": {
            "path": adjudication_path.relative_to(run_dir).as_posix(),
            "sha256": z83.sha256_file(adjudication_path),
            "source_sha256": RETRY09_ADJUDICATION_SHA256,
            "row_count": 246,
            "semantic_pre_review_redone": False,
        },
        "source_event_set_sha256": validated["event_set_sha256"],
        "supply_artifacts": supply,
        "parent_count": len(parents),
        "parents": parents,
        "conditional_entry_reviews": conditional_rows,
        "atomic_split_counts": atomic_counts,
        "atomic_split_total": sum(atomic_counts.values()),
        "logical_request_count": logical_count,
        "network_attempt_budget": logical_count + 4,
        "network_attempt_budget_scope": "完成全部逻辑请求且整轮429不超过4次时的成功预算；不是硬停观测上限",
        "network_attempt_hard_stop_observation_ceiling": logical_count + 5,
        "transport_policy": {
            "max_429_retries_per_request": 2,
            "retry_delays_seconds": [5, 10],
            "same_chapter_gap_seconds": 10,
            "cross_chapter_gap_seconds": 30,
            "fifth_429_hard_stop": True,
            "retry_after_over_300_hard_stop": True,
            "http_401_403_5xx_or_network_error_auto_retry": False,
        },
        "tasks": tasks,
        "pending_parent_ids": pending_ids,
        "pending_policy": {
            "continue_other_requests": True,
            "excluded_from_plan_denominator": False,
            "batch_quality_status": "not_concluded" if pending_ids else "eligible_for_full_run",
            "candidate_release_allowed": not pending_ids,
        },
        "model_visible_contract_version": CONTRACT_VERSION,
        "gold_or_score_material_sent_to_model": False,
        "model_api_calls": 0,
        "network_attempts": 0,
    }
    write_json_atomic(plan_path, plan)
    write_json_atomic(
        run_dir / "review/retry13_plan_receipt.json",
        {
            "schema_version": "z83-retry13-plan-receipt-v1",
            "status": "pass_zero_call_parent13_child32_frozen"
            if not pending_ids
            else "pass_zero_call_with_pending_release_block",
            "plan_path": plan_path.relative_to(run_dir).as_posix(),
            "plan_sha256": z83.sha256_file(plan_path),
            "parent_count": 13,
            "logical_request_count": logical_count,
            "atomic_split_total": sum(atomic_counts.values()),
            "pending_parent_ids": pending_ids,
            "model_api_calls": 0,
            "network_attempts": 0,
        },
    )
    return plan


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ZBatchError(f"单对象响应含重复 JSON 键：{key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    if not isinstance(text, str) or not text.strip():
        raise ZBatchError("单对象响应为空")
    if "```" in text:
        raise ZBatchError("单对象响应夹带代码围栏")
    def reject_constant(value: str) -> Any:
        raise ZBatchError(f"单对象响应含非标准 JSON 常量：{value}")
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ZBatchError(f"单对象响应不是唯一合法 JSON：{exc.msg}") from exc


def _parse_sensenova_envelope(
    raw: bytes,
    *,
    expected_model: str,
) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    """严格拆供应商外壳；业务单对象合同由下一层解析。"""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ZBatchError("retry13 供应商响应不是 UTF-8") from exc

    def reject_constant(value: str) -> Any:
        raise ZBatchError(f"retry13 供应商响应含非标准 JSON 常量：{value}")

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ZBatchError(f"retry13 供应商响应不是合法 JSON：{exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ZBatchError("retry13 供应商响应顶层不是对象")
    if parsed.get("model") != expected_model:
        raise ZBatchError("retry13 响应模型与冻结请求模型不一致")
    choices = parsed.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ZBatchError("retry13 供应商 choices 必须且只能有1项")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ZBatchError("retry13 供应商 choice 不是对象")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise ZBatchError("retry13 供应商 choice 缺 message 对象")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ZBatchError("retry13 供应商正文为空")
    finish_reason = choice.get("finish_reason")
    if finish_reason != "stop":
        raise ZBatchError(
            f"retry13 响应未正常结束：finish_reason={finish_reason}"
        )
    usage = parsed.get("usage")
    if not isinstance(usage, Mapping) or not usage:
        raise ZBatchError("retry13 成功响应缺供应商 usage")
    return dict(parsed), content, str(finish_reason), dict(usage)


def parse_single_object_result(
    content: str,
    *,
    catalog: Sequence[Mapping[str, Any]],
    required_anchor_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parsed = strict_json_loads(content)
    if not isinstance(parsed, dict) or set(parsed) != MODEL_RESULT_KEYS:
        raise ZBatchError("单对象响应根字段必须且只能是 event、anchor_ids")
    event = parsed.get("event")
    if (
        not isinstance(event, str)
        or not EVENT_NONSPACE_MIN <= nonspace_chars(event) <= EVENT_NONSPACE_MAX
    ):
        raise ZBatchError("单对象 event 非空白字符数必须为 6～100")
    if any(label in event for label in neutral_extract.CLASSIFICATION_LABELS):
        raise ZBatchError("单对象 event 夹带分类标签")
    anchors = parsed.get("anchor_ids")
    if not isinstance(anchors, list) or not anchors:
        raise ZBatchError("单对象 anchor_ids 必须是非空数组")
    all_strings = all(isinstance(row, str) for row in anchors)
    all_objects = all(isinstance(row, dict) for row in anchors)
    if not all_strings and not all_objects:
        raise ZBatchError("anchor_ids 字符串与旧式锚叶对象不得混用")
    catalog_map = {
        str(row["anchor_id"]): str(row["quote"])
        for row in catalog
        if isinstance(row, Mapping) and row.get("anchor_id") and row.get("quote") is not None
    }
    ids: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    if all_strings:
        ids = [str(row) for row in anchors]
    else:
        for ordinal, row in enumerate(anchors, 1):
            assert isinstance(row, dict)
            if "anchor_id" not in row:
                raise ZBatchError(f"旧式锚叶对象第 {ordinal} 项缺 anchor_id")
            anchor_id = row.get("anchor_id")
            if not isinstance(anchor_id, str):
                raise ZBatchError(f"旧式锚叶对象第 {ordinal} 项 anchor_id 不是字符串")
            extras = {key: copy.deepcopy(value) for key, value in row.items() if key != "anchor_id"}
            if extras:
                diagnostics.append(
                    {
                        "anchor_ordinal": ordinal,
                        "anchor_id": anchor_id,
                        "extra_field_names": sorted(extras),
                        "extra_fields": extras,
                        "extra_fields_sha256": canonical_sha(extras),
                        "used_for_validation": False,
                        "entered_formal_record": False,
                    }
                )
            ids.append(anchor_id)
    for anchor_id in ids:
        if (
            re.fullmatch(r"E[0-9]{4}", anchor_id) is None
            or anchor_id not in catalog_map
        ):
            raise ZBatchError(f"单对象响应含非法或目录外锚：{anchor_id}")
    if len(ids) != len(set(ids)):
        raise ZBatchError("单对象响应 anchor_id 重复")
    if required_anchor_ids is not None:
        required = list(required_anchor_ids)
        if not required or len(required) != len(set(required)):
            raise ZBatchError("程序冻结的本条锚集合为空或重复")
        if set(ids) != set(required):
            raise ZBatchError(
                "单对象响应没有逐字覆盖程序预校验的完整锚集合："
                f"required={required} observed={ids}"
            )
    normalized = {
        "event": event,
        "anchors": [{"anchor_id": anchor_id} for anchor_id in ids],
    }
    return normalized, diagnostics


def aggregate_parent_results(
    plan: Mapping[str, Any],
    results_by_task: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[int, dict[int, list[dict[str, Any]]]], list[dict[str, Any]]]:
    tasks = plan.get("tasks")
    parents = plan.get("parents")
    if not isinstance(tasks, list) or not isinstance(parents, list):
        raise ZBatchError("原子化计划缺父／子任务")
    expected_task_ids = [str(row["task_id"]) for row in tasks]
    if set(results_by_task) != set(expected_task_ids):
        missing = sorted(set(expected_task_ids) - set(results_by_task))
        extra = sorted(set(results_by_task) - set(expected_task_ids))
        raise ZBatchError(f"子请求结果不齐或越权：缺={missing} 多={extra}")
    pending_ids = list(plan.get("pending_parent_ids") or [])
    if pending_ids:
        raise ZBatchError("仍有 pending_CZ 父项，整批不得释放或生成四闸总判")
    tasks_by_parent: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for task in tasks:
        tasks_by_parent[str(task["parent_event_id"])].append(task)
    replacements: dict[int, dict[int, list[dict[str, Any]]]] = defaultdict(dict)
    ledgers: list[dict[str, Any]] = []
    for parent in parents:
        event_id = str(parent["event_id"])
        if parent.get("route") == "pending_cz_not_sent":
            ledgers.append(
                {
                    "parent_event_id": event_id,
                    "status": "pending_cz_not_sent",
                    "replacement_count": 0,
                    "excluded_from_denominator": False,
                }
            )
            continue
        parent_tasks = sorted(
            tasks_by_parent[event_id], key=lambda row: int(row["fact_ordinal"])
        )
        expected_ordinals = list(range(1, int(parent["fact_count"]) + 1))
        if [int(row["fact_ordinal"]) for row in parent_tasks] != expected_ordinals:
            raise ZBatchError(f"{event_id} 子事实序号不连续")
        parent_results: list[dict[str, Any]] = []
        child_rows = []
        seen_fact_targets: set[str] = set()
        for task in parent_tasks:
            task_id = str(task["task_id"])
            result = results_by_task[task_id]
            normalized = result.get("normalized_replacement")
            if not isinstance(normalized, dict):
                raise ZBatchError(f"{task_id} 缺规范单对象结果")
            fact_sha = str(task["fact_target_sha256"])
            if fact_sha in seen_fact_targets:
                raise ZBatchError(f"{event_id} 子事实身份重复")
            seen_fact_targets.add(fact_sha)
            parent_results.append(copy.deepcopy(normalized))
            child_rows.append(
                {
                    "task_id": task_id,
                    "fact_ordinal": task["fact_ordinal"],
                    "fact_target_sha256": fact_sha,
                    "replacement_sha256": canonical_sha(normalized),
                    **(
                        {
                            "checkpoint_id": result["checkpoint_id"],
                            "checkpoint_path": result["checkpoint_path"],
                            "request_artifact_sha256": result[
                                "request_artifact_sha256"
                            ],
                            "wire_body_sha256": result["wire_body_sha256"],
                            "raw_response_sha256": result["raw_response_sha256"],
                        }
                        if all(
                            key in result
                            for key in (
                                "checkpoint_id",
                                "checkpoint_path",
                                "request_artifact_sha256",
                                "wire_body_sha256",
                                "raw_response_sha256",
                            )
                        )
                        else {}
                    ),
                }
            )
        if len(parent_results) != int(parent["fact_count"]):
            raise ZBatchError(f"{event_id} 子事实结果数量不等于冻结 N")
        chapter = int(parent["chapter"])
        source_index = int(event_id.rsplit("-", 1)[1]) - 1
        if source_index in replacements[chapter]:
            raise ZBatchError(f"{event_id} 父源聚合位置重复")
        replacements[chapter][source_index] = parent_results
        ledgers.append(
            {
                "parent_event_id": event_id,
                "status": "complete_parent_aggregated_once",
                "replacement_count": len(parent_results),
                "child_results": child_rows,
                "facts_added": None,
                "facts_dropped": None,
                "fact_closed_set_semantic_review": "pending_not_inferred_from_sha",
                "counts_as_parent_rewrite": 1,
            }
        )
    if len({row["parent_event_id"] for row in ledgers}) != 13:
        raise ZBatchError("父源聚合账不是 13 条唯一记录")
    return {chapter: dict(rows) for chapter, rows in replacements.items()}, ledgers


def _model_input_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event": str(event["event"]),
        "anchors": [
            {"anchor_id": str(row["anchor_id"])}
            for row in event.get("anchors", [])
            if isinstance(row, Mapping) and row.get("anchor_id")
        ],
    }


def build_task_messages(
    run_dir: Path,
    task: Mapping[str, Any],
    source_event: Mapping[str, Any],
) -> list[dict[str, str]]:
    chapter = int(task["chapter"])
    system = _extract_single_object_system_contract()
    user = (
        f"当前章：{chapter}\n"
        "程序已把复合父事件预拆成本次唯一事实单元；本次不得重抽整章。\n"
        f"本次唯一事实目标：{task['fact_target']}\n"
        f"本条唯一许可动作：{task['permission']}\n"
        "程序预校验的本条完整锚集合（必须全部挂入 anchor_ids，且不得增加集合外 ID）："
        f"{json.dumps(task['required_anchor_ids'], ensure_ascii=False, separators=(',', ':'))}\n"
        "原父事件仅供定位，不得把未点名的其他事实重新并入本条："
        f"{json.dumps(_model_input_event(source_event), ensure_ascii=False, separators=(',', ':'))}\n\n"
        "【连续章节正文｜只供核对本条，不得重抽其他事件】\n"
        f"{z83._chapter_text_path(run_dir, chapter).read_text(encoding='utf-8')}\n\n"
        "【冻结证据目录｜anchor_ids 只能从这里选择】\n"
        f"{json.dumps(z83._catalog(run_dir, chapter), ensure_ascii=False, separators=(',', ':'))}\n\n"
        "只按一对一单对象输出合同 v1 返回一个 JSON 对象。"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    serialized = json.dumps(messages, ensure_ascii=False)
    forbidden = z83.forbidden_model_hits(messages)
    if forbidden:
        raise ZBatchError(f"{task['task_id']} 模型请求夹入判分材料：{forbidden}")
    for token in ("GOLD-C", "旧25", "金标v1.2"):
        if token in serialized:
            raise ZBatchError(f"{task['task_id']} 模型请求夹入禁入词：{token}")
    return messages


def _validate_plan(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "repair/atomic_plan.json"
    if not path.is_file():
        raise ZBatchError("retry13 缺原子化计划")
    plan = read_json(path)
    if plan.get("schema_version") != PLAN_SCHEMA or plan.get("run_id") != run_dir.name:
        raise ZBatchError("retry13 原子化计划版本或运行编号错误")
    if plan.get("parent_count") != 13 or plan.get("atomic_split_total") != 25:
        raise ZBatchError("retry13 父源数量或 ΣN 漂移")
    if not plan.get("pending_parent_ids") and plan.get("logical_request_count") != 32:
        raise ZBatchError("retry13 逻辑请求总量不等于 32")
    if plan.get("network_attempt_budget") != int(plan["logical_request_count"]) + 4:
        raise ZBatchError("retry13 网络 attempt 预算未按最多 4 次 429 冻结")
    if (
        plan.get("network_attempt_budget_scope")
        != "完成全部逻辑请求且整轮429不超过4次时的成功预算；不是硬停观测上限"
        or plan.get("network_attempt_hard_stop_observation_ceiling")
        != int(plan["logical_request_count"]) + 5
    ):
        raise ZBatchError("retry13 第5次429硬停观测上限没有与成功预算分账")
    if z83.sha256_file(RETRY09_ADJUDICATION) != RETRY09_ADJUDICATION_SHA256:
        raise ZBatchError("retry09 判词来源漂移")

    receipt_path = run_dir / "review/retry13_plan_receipt.json"
    if not receipt_path.is_file():
        raise ZBatchError("retry13 缺计划身份票")
    receipt = read_json(receipt_path)
    if (
        receipt.get("plan_path") != "repair/atomic_plan.json"
        or receipt.get("plan_sha256") != z83.sha256_file(path)
        or receipt.get("parent_count") != 13
        or receipt.get("logical_request_count") != plan.get("logical_request_count")
        or receipt.get("atomic_split_total") != 25
        or receipt.get("pending_parent_ids") != plan.get("pending_parent_ids")
        or receipt.get("model_api_calls") != 0
        or receipt.get("network_attempts") != 0
    ):
        raise ZBatchError("retry13 计划身份票与计划原件不一致")

    source_info = plan.get("source_adjudication")
    if not isinstance(source_info, Mapping):
        raise ZBatchError("retry13 计划缺判词来源")
    adjudication_path = run_dir / str(source_info.get("path") or "")
    if (
        not adjudication_path.is_file()
        or adjudication_path.resolve().parent != (run_dir / "review").resolve()
        or source_info.get("source_sha256") != RETRY09_ADJUDICATION_SHA256
        or source_info.get("sha256") != z83.sha256_file(adjudication_path)
        or source_info.get("row_count") != 246
        or source_info.get("semantic_pre_review_redone") is not False
    ):
        raise ZBatchError("retry13 计划没有绑定本轮 retry09 判词机械实例")
    adjudication = read_json(adjudication_path)
    validated = z83.validate_adjudication(run_dir, adjudication_path, phase="main")
    events = _source_event_map(run_dir)
    lineage = z83._validate_main_lineage(run_dir)["rows"]
    reason_codes = z83._collect_retry_reason_codes(run_dir, validated)
    if set(reason_codes) != set(PARENT_ORDER):
        raise ZBatchError("retry13 计划不再对应已核实 13 条父源")
    conditionals = {
        event_id: _conditional_review(adjudication, event_id)
        for event_id in sorted(CONDITIONAL_PARENT_IDS)
    }
    expected_tasks: list[dict[str, Any]] = []
    expected_pending: list[str] = []
    for parent_ordinal, event_id in enumerate(PARENT_ORDER, 1):
        specs = _parent_task_specs(event_id)
        pending = bool(
            event_id in CONDITIONAL_PARENT_IDS
            and not conditionals[event_id]["same_center_fact"]
        )
        if pending:
            expected_pending.append(event_id)
            continue
        for fact_ordinal, spec in enumerate(specs, 1):
            event = events[event_id]
            expected_tasks.append(
                {
                    "task_id": _task_id(event_id, fact_ordinal),
                    "parent_ordinal": parent_ordinal,
                    "parent_event_id": event_id,
                    "parent_event_sha256": z83.canonical_sha(event),
                    "source_event_id": lineage[event_id]["source_event_id"],
                    "source_event_sha256": lineage[event_id]["source_event_sha256"],
                    "source_identity_sha256": lineage[event_id]["source_identity_sha256"],
                    "chapter": int(event_id[4:8]),
                    "fact_ordinal": fact_ordinal,
                    "fact_count": len(specs),
                    "fact_target": spec["fact"],
                    "fact_target_sha256": canonical_sha(spec["fact"]),
                    "permission": spec["permission"],
                    "support_anchor_candidates": list(spec["support_anchor_candidates"]),
                    "required_anchor_ids": list(spec["support_anchor_candidates"]),
                    "anchor_binding_policy": "exact_program_prechecked_set",
                    "output_contract": CONTRACT_VERSION,
                    "single_object_required": True,
                    "candidate_silver_only": True,
                }
            )
    if plan.get("tasks") != expected_tasks:
        raise ZBatchError("retry13 子任务事实、许可、锚集合或稳定身份不能从代码闭集重建")
    if plan.get("pending_parent_ids") != expected_pending:
        raise ZBatchError("retry13 条件进入结果或 pending 分母纪律漂移")
    if plan.get("conditional_entry_reviews") != conditionals:
        raise ZBatchError("retry13 两条条件进入判词漂移")

    parents = plan.get("parents")
    if (
        not isinstance(parents, list)
        or [row.get("event_id") for row in parents] != list(PARENT_ORDER)
    ):
        raise ZBatchError("retry13 父源顺序或集合漂移")
    task_ids = {str(row["task_id"]) for row in expected_tasks}
    for parent, event_id in zip(parents, PARENT_ORDER, strict=True):
        specs = _parent_task_specs(event_id)
        expected_ids = (
            []
            if event_id in expected_pending
            else [_task_id(event_id, index) for index in range(1, len(specs) + 1)]
        )
        expected_route = (
            "pending_cz_not_sent"
            if event_id in expected_pending
            else "direct_one_to_one"
            if event_id in DIRECT_PARENT_IDS
            else "conditional_one_to_one"
            if event_id in CONDITIONAL_PARENT_IDS
            else "program_atomic_split"
        )
        if (
            parent.get("parent_ordinal") != PARENT_ORDER.index(event_id) + 1
            or parent.get("chapter") != int(event_id[4:8])
            or parent.get("event_sha256") != z83.canonical_sha(events[event_id])
            or parent.get("source_event_id") != lineage[event_id]["source_event_id"]
            or parent.get("source_event_sha256") != lineage[event_id]["source_event_sha256"]
            or parent.get("source_identity_sha256")
            != lineage[event_id]["source_identity_sha256"]
            or parent.get("reason_codes") != sorted(reason_codes[event_id])
            or parent.get("route") != expected_route
            or parent.get("fact_count") != len(specs)
            or parent.get("fact_target_sha256_set")
            != [canonical_sha(spec["fact"]) for spec in specs]
            or parent.get("task_ids") != expected_ids
            or any(task_id not in task_ids for task_id in expected_ids)
            or parent.get("counts_as_one_parent_rewrite") is not True
            or parent.get("facts_may_not_be_added_or_dropped") is not True
            or parent.get("adjudication_references")
            != _adjudication_row_refs(adjudication, event_id)
        ):
            raise ZBatchError(f"retry13 父源绑定漂移：{event_id}")
    expected_supply = {
        label: expected_sha for label, (_, expected_sha) in SUPPLY_FILES.items()
    }
    actual_supply = {
        str(row.get("label")): str(row.get("sha256"))
        for row in plan.get("supply_artifacts", [])
        if isinstance(row, Mapping)
    }
    if actual_supply != expected_supply:
        raise ZBatchError("retry13 三件已审收供料 SHA 漂移")
    for task in expected_tasks:
        catalog_ids = {
            str(row["anchor_id"])
            for row in z83._catalog(run_dir, int(task["chapter"]))
        }
        required = task["required_anchor_ids"]
        if (
            not required
            or len(required) != len(set(required))
            or not set(required).issubset(catalog_ids)
        ):
            raise ZBatchError(f"{task['task_id']} 程序预校验锚集合为空、重复或越目录")
    return plan


def preflight(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    receipt_path = run_dir / "repair/atomic_preflight.json"
    prepared_root = run_dir / "repair/prepared_single_object_requests"
    if receipt_path.exists() or prepared_root.exists():
        raise ZBatchError("retry13 预构造件已存在，拒绝覆盖")
    plan = _validate_plan(run_dir)
    bundle = z83.load_bundle(run_dir)
    contract = bundle.stage("targeted_retry")
    source_events = _source_event_map(run_dir)
    rows = []
    for task in plan["tasks"]:
        messages = build_task_messages(
            run_dir, task, source_events[str(task["parent_event_id"])]
        )
        body = api_transport.build_request_body(
            model=str(bundle.route["model"]), messages=messages, contract=contract
        )
        case_id = f"z83r13-{task['task_id']}"
        path = prepared_root / f"{case_id}.json"
        z83.write_json(path, body)
        rows.append(
            {
                "task_id": task["task_id"],
                "parent_event_id": task["parent_event_id"],
                "chapter": task["chapter"],
                "fact_ordinal": task["fact_ordinal"],
                "fact_count": task["fact_count"],
                "fact_target_sha256": task["fact_target_sha256"],
                "case_id": case_id,
                "prepared_request_path": path.relative_to(run_dir).as_posix(),
                "prepared_request_sha256": z83.sha256_file(path),
                "body_canonical_sha256": canonical_sha(body),
                "messages_sha256": canonical_sha(messages),
                "single_object_contract_present": _extract_single_object_system_contract()
                == messages[0]["content"],
                "output_array_contract_present": False,
                "gold_or_score_hits": [],
            }
        )
    if len(rows) != int(plan["logical_request_count"]):
        raise ZBatchError("retry13 预构造请求数量与计划不一致")
    receipt = {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "pass_zero_call_requests_frozen",
        "run_id": run_dir.name,
        "plan_path": "repair/atomic_plan.json",
        "plan_sha256": z83.sha256_file(run_dir / "repair/atomic_plan.json"),
        "contract_version": CONTRACT_VERSION,
        "contract_text_sha256": canonical_sha(_extract_single_object_system_contract()),
        "parent_count": 13,
        "task_count": len(rows),
        "atomic_split_counts": plan["atomic_split_counts"],
        "atomic_split_total": plan["atomic_split_total"],
        "pending_parent_ids": plan["pending_parent_ids"],
        "rows": rows,
        "tool_artifacts": {
            "retry13_runner_sha256": z83.sha256_file(Path(__file__)),
            "retry13_transport_sha256": z83.sha256_file(
                ROOT / "tools/zbatch_modules/z83_retry_transport.py"
            ),
        },
        "model_api_calls": 0,
        "network_attempts": 0,
        "protected_before": z83.protected_snapshot(),
    }
    write_json_atomic(receipt_path, receipt)
    return receipt


def verify_preflight(run_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    plan = _validate_plan(run_dir)
    receipt_path = run_dir / "repair/atomic_preflight.json"
    if not receipt_path.is_file():
        raise ZBatchError("retry13 缺预构造票")
    receipt = read_json(receipt_path)
    if (
        receipt.get("schema_version") != PREFLIGHT_SCHEMA
        or receipt.get("status") != "pass_zero_call_requests_frozen"
        or receipt.get("plan_sha256") != z83.sha256_file(run_dir / "repair/atomic_plan.json")
        or receipt.get("task_count") != plan.get("logical_request_count")
        or receipt.get("model_api_calls") != 0
        or receipt.get("network_attempts") != 0
    ):
        raise ZBatchError("retry13 预构造票总账漂移")
    source_events = _source_event_map(run_dir)
    bundle = z83.load_bundle(run_dir)
    contract = bundle.stage("targeted_retry")
    row_by_task = {str(row["task_id"]): row for row in receipt["rows"]}
    if len(row_by_task) != len(receipt["rows"]):
        raise ZBatchError("retry13 预构造票含重复任务")
    expected_tools = {
        "retry13_runner_sha256": z83.sha256_file(Path(__file__)),
        "retry13_transport_sha256": z83.sha256_file(
            ROOT / "tools/zbatch_modules/z83_retry_transport.py"
        ),
    }
    if receipt.get("tool_artifacts") != expected_tools:
        raise ZBatchError("retry13 预构造后执行工具或运输工具发生漂移")
    checks = []
    for task in plan["tasks"]:
        task_id = str(task["task_id"])
        row = row_by_task.get(task_id)
        if not isinstance(row, dict):
            raise ZBatchError(f"retry13 预构造票缺任务：{task_id}")
        messages = build_task_messages(
            run_dir, task, source_events[str(task["parent_event_id"])]
        )
        expected = api_transport.build_request_body(
            model=str(bundle.route["model"]), messages=messages, contract=contract
        )
        path = run_dir / str(row["prepared_request_path"])
        prepared_root = (run_dir / "repair/prepared_single_object_requests").resolve()
        if (
            not path.is_file()
            or not path.resolve().is_relative_to(prepared_root)
            or read_json(path) != expected
            or z83.sha256_file(path) != row.get("prepared_request_sha256")
            or canonical_sha(expected) != row.get("body_canonical_sha256")
            or row.get("single_object_contract_present") is not True
            or row.get("output_array_contract_present") is not False
            or row.get("gold_or_score_hits") != []
        ):
            raise ZBatchError(f"retry13 预构造请求漂移：{task_id}")
        checks.append({"task_id": task_id, "sha256": z83.sha256_file(path), "passed": True})
    if set(row_by_task) != {str(task["task_id"]) for task in plan["tasks"]}:
        raise ZBatchError("retry13 预构造票夹入计划外任务")
    if z83.protected_snapshot() != receipt.get("protected_before"):
        raise ZBatchError("retry13 零调用准备后保护件漂移")
    return {
        "schema_version": "z83-retry13-preflight-verification-v1",
        "status": "pass",
        "task_count": len(checks),
        "checks_canonical_sha256": canonical_sha(checks),
        "plan_sha256": z83.sha256_file(run_dir / "repair/atomic_plan.json"),
        "preflight_sha256": z83.sha256_file(receipt_path),
        "model_api_calls": 0,
        "network_attempts": 0,
    }


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for ordinal, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ZBatchError(f"{path.name} 第 {ordinal} 行不是对象")
        rows.append(value)
    return rows


def _append_jsonl_fsync(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_bytes_exclusive(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    _write_bytes_exclusive(
        path,
        (json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def _safe_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    allowed = {"content-type", "date", "x-request-id", "request-id", "retry-after"}
    return {
        str(key): str(value)
        for key, value in headers.items()
        if str(key).lower() in allowed
    }


def _request_checkpoint_record(
    *,
    task_id: str,
    request_path: Path,
    request_sha256: str,
    wire_body_sha256: str,
    model: str,
    run_dir: Path,
) -> dict[str, Any]:
    return {
        "schema": "z83-retry13-checkpoint-request-v1",
        "logical_request_id": task_id,
        "request_artifact_path": request_path.relative_to(run_dir).as_posix(),
        "request_artifact_sha256": request_sha256,
        "wire_body_sha256": wire_body_sha256,
        "model": model,
        "stage": "targeted_retry_single_object",
        "contract_version": CONTRACT_VERSION,
    }


def _response_checkpoint_record(
    *,
    task_id: str,
    request_sha256: str,
    http_status: int,
    raw_path: Path | None,
    raw_sha256: str | None,
    response_json: Mapping[str, Any] | None,
    content: str | None,
    run_dir: Path,
    error_code: str | None,
) -> dict[str, Any]:
    finish_reason: str | None = None
    response_model: str | None = None
    if isinstance(response_json, Mapping):
        response_model_raw = response_json.get("model")
        response_model = str(response_model_raw) if response_model_raw is not None else None
        choices = response_json.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
            raw_finish = choices[0].get("finish_reason")
            finish_reason = str(raw_finish) if raw_finish is not None else None
    return {
        "schema": "z83-retry13-checkpoint-response-v1",
        "logical_request_id": task_id,
        "request_artifact_sha256": request_sha256,
        "http_status": http_status,
        "raw_response_path": raw_path.relative_to(run_dir).as_posix() if raw_path else None,
        "raw_response_sha256": raw_sha256,
        "response_model": response_model,
        "finish_reason": finish_reason,
        "content_sha256": sha256_bytes(content.encode("utf-8")) if content is not None else None,
        "error_code": error_code,
    }


def _usage_checkpoint_record(
    *,
    task_id: str,
    request_sha256: str,
    raw_response_sha256: str | None,
    usage: Mapping[str, Any] | str,
) -> dict[str, Any]:
    return {
        "schema": "z83-retry13-checkpoint-usage-v1",
        "logical_request_id": task_id,
        "request_artifact_sha256": request_sha256,
        "raw_response_sha256": raw_response_sha256,
        "usage": dict(usage) if isinstance(usage, Mapping) else str(usage),
    }


def _attempt_reservation(
    *,
    run_dir: Path,
    task: Mapping[str, Any],
    attempt: int,
    request_sha256: str,
    wire_body_sha256: str,
) -> None:
    path = run_dir / "repair/attempt_reservations.jsonl"
    existing = _read_jsonl(path)
    identity = (str(task["task_id"]), attempt)
    if any((str(row.get("logical_request_id")), row.get("attempt")) == identity for row in existing):
        raise ZBatchError(f"{identity[0]} attempt={attempt} 已占用，拒绝再次发网")
    row = {
        "schema": "z83-retry13-attempt-reservation-v1",
        "logical_request_id": str(task["task_id"]),
        "parent_event_id": str(task["parent_event_id"]),
        "chapter": int(task["chapter"]),
        "attempt": attempt,
        "request_artifact_sha256": request_sha256,
        "wire_body_sha256": wire_body_sha256,
        "reserved_at": _now_iso(),
        "state": "reserved_before_network_do_not_resend_if_unmatched",
    }
    row["row_sha256"] = canonical_sha(row)
    _append_jsonl_fsync(path, row)


def _build_request_artifact(
    *,
    run_dir: Path,
    plan: Mapping[str, Any],
    task: Mapping[str, Any],
    preflight_row: Mapping[str, Any],
    body: Mapping[str, Any],
    route: api_transport.TransportRoute,
) -> tuple[Path, str, bytes, str]:
    case_id = str(preflight_row["case_id"])
    path = run_dir / f"repair/requests/single_object/{case_id}_request.json"
    record = {
        "schema_version": "z83-retry13-actual-request-v1",
        "run_id": run_dir.name,
        "logical_request_id": task["task_id"],
        "parent_event_id": task["parent_event_id"],
        "fact_ordinal": task["fact_ordinal"],
        "fact_count": task["fact_count"],
        "provider": route.provider,
        "api_base_url": route.base_url,
        "api_endpoint": route.endpoint,
        "stage": "targeted_retry_single_object",
        "contract_version": CONTRACT_VERSION,
        "plan_sha256": z83.sha256_file(run_dir / "repair/atomic_plan.json"),
        "prepared_request_path": preflight_row["prepared_request_path"],
        "prepared_request_sha256": preflight_row["prepared_request_sha256"],
        "body": copy.deepcopy(body),
        "_security": "no_api_key_no_authorization",
    }
    key = os.environ.get(route.api_key_env) or ""
    serialized = json.dumps(record, ensure_ascii=False)
    if key and key in serialized:
        raise ZBatchError("retry13 请求工件意外包含 API Key")
    _write_json_exclusive(path, record)
    request_sha = z83.sha256_file(path)
    # 冻结 JSON 文件是可读工件；真正 POST 的字节始终由冻结 body 按
    # json.dumps(..., ensure_ascii=False).encode("utf-8") 重建。
    wire = json.dumps(body, ensure_ascii=False).encode("utf-8")
    wire_sha = sha256_bytes(wire)
    prepared_path = run_dir / str(preflight_row["prepared_request_path"])
    if read_json(prepared_path) != body:
        raise ZBatchError(f"{task['task_id']} 冻结请求正文不能还原实发 body")
    if z83.sha256_file(prepared_path) != preflight_row.get("prepared_request_sha256"):
        raise ZBatchError(f"{task['task_id']} 冻结请求文件 SHA 漂移")
    if canonical_sha(body) != preflight_row.get("body_canonical_sha256"):
        raise ZBatchError(f"{task['task_id']} 实发 body 不等于预构造件")
    return path, request_sha, wire, wire_sha


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _send_once_factory(
    *,
    run_dir: Path,
    task: Mapping[str, Any],
    route: api_transport.TransportRoute,
    request_sha256: str,
    request_artifact_sha256: str,
    wire_body: bytes,
    wire_body_sha256: str,
    opener: Any = None,
):
    key = os.environ.get(route.api_key_env)
    if not key:
        raise ZBatchError(f"缺少 {route.api_key_env}；未创建调用占用票")
    open_fn = opener or urllib.request.build_opener(_NoRedirectHandler()).open

    def send_once(attempt: int) -> z83_retry_transport.AttemptOutcome:
        _attempt_reservation(
            run_dir=run_dir,
            task=task,
            attempt=attempt,
            request_sha256=request_artifact_sha256,
            wire_body_sha256=wire_body_sha256,
        )
        started_at = _now_iso()
        request = urllib.request.Request(
            route.url,
            data=wire_body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with open_fn(request, timeout=route.timeout_seconds) as response:
                raw = response.read()
                status = int(getattr(response, "status", 200) or 200)
                headers = _safe_headers(dict(response.headers.items()))
            if key.encode("utf-8") in raw:
                raise ZBatchError("服务端响应意外回显 API Key；拒绝落盘")
            raw_path = run_dir / (
                f"repair/raw_responses/single_object/{task['task_id']}/attempt{attempt:02d}.json"
            )
            _write_bytes_exclusive(raw_path, raw)
            raw_sha = sha256_bytes(raw)
            response_json: Mapping[str, Any] | None = None
            usage: Mapping[str, Any] = {}
            envelope_error: str | None = None
            try:
                parsed = json.loads(raw.decode("utf-8"))
                if isinstance(parsed, dict):
                    response_json = parsed
                    if isinstance(parsed.get("usage"), Mapping):
                        usage = dict(parsed["usage"])
                else:
                    envelope_error = "http_200_non_object"
            except (UnicodeDecodeError, json.JSONDecodeError):
                envelope_error = "http_200_invalid_json"
            return z83_retry_transport.AttemptOutcome(
                http_status=status,
                request_sha256=request_sha256,
                raw_response_sha256=raw_sha,
                usage=usage,
                headers=headers,
                payload={
                    "raw_path": raw_path,
                    "response_json": response_json,
                    "envelope_error": envelope_error,
                },
                wire_body_sha256=wire_body_sha256,
                request_artifact_sha256=request_artifact_sha256,
                started_at=started_at,
                finished_at=_now_iso(),
            )
        except urllib.error.HTTPError as exc:
            error_body = exc.read() if hasattr(exc, "read") else b""
            headers = _safe_headers(dict(exc.headers.items())) if exc.headers else {}
            return z83_retry_transport.AttemptOutcome(
                http_status=int(exc.code),
                request_sha256=request_sha256,
                headers=headers,
                error_code=f"http_{int(exc.code)}",
                wire_body_sha256=wire_body_sha256,
                request_artifact_sha256=request_artifact_sha256,
                error_body_sha256=sha256_bytes(error_body),
                started_at=started_at,
                finished_at=_now_iso(),
            )
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, ConnectionError, socket.timeout) as exc:
            partial = exc.partial if isinstance(exc, http.client.IncompleteRead) else b""
            return z83_retry_transport.AttemptOutcome(
                http_status=598,
                request_sha256=request_sha256,
                error_code=f"transport_{type(exc).__name__}",
                wire_body_sha256=wire_body_sha256,
                request_artifact_sha256=request_artifact_sha256,
                error_body_sha256=sha256_bytes(partial),
                started_at=started_at,
                finished_at=_now_iso(),
            )

    return send_once


def _task_attempt_rows(run_dir: Path, task_id: str) -> list[dict[str, Any]]:
    return [
        row
        for row in _read_jsonl(run_dir / "repair/call_attempts.jsonl")
        if row.get("logical_request_id") == task_id
    ]


def _write_usage_row(
    *,
    run_dir: Path,
    task: Mapping[str, Any],
    request_sha256: str,
    raw_response_sha256: str,
    usage: Mapping[str, Any],
) -> dict[str, Any]:
    row = {
        "schema_version": "z83-retry13-usage-v1",
        "logical_request_id": task["task_id"],
        "parent_event_id": task["parent_event_id"],
        "chapter": task["chapter"],
        "request_artifact_sha256": request_sha256,
        "raw_response_sha256": raw_response_sha256,
        "usage": dict(usage),
        "at": _now_iso(),
    }
    row["row_sha256"] = canonical_sha(row)
    _append_jsonl_fsync(run_dir / "repair/usage.jsonl", row)
    return row


def _write_hard_stop(
    *,
    run_dir: Path,
    error: BaseException,
    active_task: Mapping[str, Any] | None,
    reason_code: str,
) -> dict[str, Any]:
    path = run_dir / "repair/hard_stop.json"
    if path.exists():
        return read_json(path)
    attempts = _read_jsonl(run_dir / "repair/call_attempts.jsonl")
    reservations = _read_jsonl(run_dir / "repair/attempt_reservations.jsonl")
    results = sorted((run_dir / "repair/results").glob("*.json")) if (run_dir / "repair/results").is_dir() else []
    receipt = {
        "schema_version": "z83-retry13-hard-stop-v1",
        "status": "hard_stop_no_unapproved_repair_no_resume",
        "reason_code": reason_code,
        "error_type": type(error).__name__,
        "error": str(error),
        "active_task_id": active_task.get("task_id") if active_task else None,
        "active_parent_event_id": active_task.get("parent_event_id") if active_task else None,
        "completed_task_count": len(results),
        "network_attempts": len(attempts),
        "reservations": len(reservations),
        "unmatched_reservation_possible": len(reservations) != len(attempts),
        "prefix_results_reusable_as_retry13_result": False,
        "partial_formal_repair_written": False,
        "candidate_silver_only": True,
        "stopped_at": _now_iso(),
    }
    _write_json_exclusive(path, receipt)
    manifest_path = run_dir / "repair/retry13_run_manifest.json"
    if not manifest_path.exists():
        _write_json_exclusive(manifest_path, receipt)
    return receipt


def _seal_failed_checkpoint(
    *,
    run_dir: Path,
    task: Mapping[str, Any],
    request_record: Mapping[str, Any],
    request_sha256: str,
    error_code: str,
) -> None:
    root = run_dir / f"repair/checkpoints/{task['task_id']}"
    if root.exists():
        return
    rows = _task_attempt_rows(run_dir, str(task["task_id"]))
    if not rows:
        return
    last = rows[-1]
    raw_sha = last.get("raw_response_sha256")
    raw_path = None
    if isinstance(raw_sha, str):
        candidate = run_dir / (
            f"repair/raw_responses/single_object/{task['task_id']}/attempt{int(last['attempt']):02d}.json"
        )
        if candidate.is_file() and z83.sha256_file(candidate) == raw_sha:
            raw_path = candidate
    response_json = None
    content = None
    if raw_path is not None:
        try:
            parsed = json.loads(raw_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                response_json = parsed
                try:
                    content, _ = api_transport.response_content(parsed)
                except ZBatchError:
                    content = None
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    z83_retry_transport.write_checkpoint_bundle(
        root,
        request_record=request_record,
        response_record=_response_checkpoint_record(
            task_id=str(task["task_id"]),
            request_sha256=request_sha256,
            http_status=int(last["http_status"]),
            raw_path=raw_path,
            raw_sha256=raw_sha if isinstance(raw_sha, str) else None,
            response_json=response_json,
            content=content,
            run_dir=run_dir,
            error_code=error_code,
        ),
        usage_record=_usage_checkpoint_record(
            task_id=str(task["task_id"]),
            request_sha256=request_sha256,
            raw_response_sha256=raw_sha if isinstance(raw_sha, str) else None,
            usage=last.get("usage") if isinstance(last.get("usage"), Mapping) else "unknown",
        ),
        attempt_rows=rows,
        contract_version=CONTRACT_VERSION,
        mechanical_verdict="fail",
    )


def _task_result_document(
    *,
    run_dir: Path,
    task: Mapping[str, Any],
    request_record: Mapping[str, Any],
    raw_response_sha256: str,
    content: str,
    normalized: Mapping[str, Any],
    diagnostics: Sequence[Mapping[str, Any]],
    checkpoint_seal: Mapping[str, Any],
) -> dict[str, Any]:
    checkpoint_id = checkpoint_seal.get("checkpoint_id")
    if not isinstance(checkpoint_id, str) or re.fullmatch(r"[0-9a-f]{64}", checkpoint_id) is None:
        raise ZBatchError("retry13 成功结果缺不可变检查点身份")
    checkpoint_path = run_dir / f"repair/checkpoints/{task['task_id']}"
    return {
        "schema_version": "z83-retry13-task-result-v1",
        "status": "contract_pass_semantic_review_pending",
        "task_id": task["task_id"],
        "parent_event_id": task["parent_event_id"],
        "fact_ordinal": task["fact_ordinal"],
        "fact_count": task["fact_count"],
        "fact_target_sha256": task["fact_target_sha256"],
        "request_artifact_sha256": request_record["request_artifact_sha256"],
        "wire_body_sha256": request_record["wire_body_sha256"],
        "raw_response_sha256": raw_response_sha256,
        "content_sha256": sha256_bytes(content.encode("utf-8")),
        "checkpoint_path": checkpoint_path.relative_to(run_dir).as_posix(),
        "checkpoint_id": checkpoint_id,
        "normalized_replacement": copy.deepcopy(dict(normalized)),
        "normalized_replacement_sha256": canonical_sha(normalized),
        "anchor_leaf_extra_diagnostics": [copy.deepcopy(dict(row)) for row in diagnostics],
        "candidate_silver_only": True,
        "semantic_truth": False,
    }


def _process_successful_task(
    *,
    run_dir: Path,
    task: Mapping[str, Any],
    request_record: Mapping[str, Any],
    request_sha256: str,
    transport_result: z83_retry_transport.LogicalRequestResult,
    expected_model: str | None = None,
) -> dict[str, Any]:
    if transport_result.outcome.http_status != 200:
        raise ZBatchError("retry13 成功处理只接受 HTTP 200")
    payload = transport_result.outcome.payload
    raw_path = payload.get("raw_path") if isinstance(payload, Mapping) else None
    if not isinstance(raw_path, Path):
        raise ZBatchError("HTTP 200 响应缺原始落盘路径")
    raw_resolved = raw_path.resolve()
    if not raw_resolved.is_relative_to(run_dir.resolve()) or not raw_resolved.is_file():
        raise ZBatchError("retry13 原始响应路径越界或不存在")
    raw = raw_resolved.read_bytes()
    raw_sha = sha256_bytes(raw)
    if raw_sha != transport_result.outcome.raw_response_sha256:
        raise ZBatchError("retry13 原始响应 SHA 与运输结果不一致")
    if expected_model is None:
        route = api_transport.TransportRoute.from_mapping(z83.load_bundle(run_dir).route)
        expected_model = route.model
    response_json, content, _finish_reason, usage = _parse_sensenova_envelope(
        raw, expected_model=expected_model
    )
    if dict(transport_result.outcome.usage or {}) != usage:
        raise ZBatchError("retry13 运输层 usage 与原始响应不一致")
    normalized, diagnostics = parse_single_object_result(
        content,
        catalog=z83._catalog(run_dir, int(task["chapter"])),
        required_anchor_ids=list(task["required_anchor_ids"]),
    )
    usage_record = _usage_checkpoint_record(
        task_id=str(task["task_id"]),
        request_sha256=request_sha256,
        raw_response_sha256=raw_sha,
        usage=usage,
    )
    checkpoint_root = run_dir / f"repair/checkpoints/{task['task_id']}"
    checkpoint_seal = z83_retry_transport.write_checkpoint_bundle(
        checkpoint_root,
        request_record=request_record,
        response_record=_response_checkpoint_record(
            task_id=str(task["task_id"]),
            request_sha256=request_sha256,
            http_status=200,
            raw_path=raw_resolved,
            raw_sha256=raw_sha,
            response_json=response_json,
            content=content,
            run_dir=run_dir,
            error_code=None,
        ),
        usage_record=usage_record,
        attempt_rows=transport_result.attempt_rows,
        contract_version=CONTRACT_VERSION,
        mechanical_verdict="pass",
    )
    _write_usage_row(
        run_dir=run_dir,
        task=task,
        request_sha256=request_sha256,
        raw_response_sha256=raw_sha,
        usage=usage,
    )
    if diagnostics:
        for row in diagnostics:
            diagnostic = {
                "schema_version": "z83-retry13-anchor-leaf-extra-diagnostic-v1",
                "task_id": task["task_id"],
                "parent_event_id": task["parent_event_id"],
                "raw_response_sha256": raw_sha,
                **row,
            }
            diagnostic["row_sha256"] = canonical_sha(diagnostic)
            _append_jsonl_fsync(
                run_dir / "repair/anchor_leaf_extra_diagnostics.jsonl", diagnostic
            )
    result = _task_result_document(
        run_dir=run_dir,
        task=task,
        request_record=request_record,
        raw_response_sha256=raw_sha,
        content=content,
        normalized=normalized,
        diagnostics=diagnostics,
        checkpoint_seal=checkpoint_seal,
    )
    _write_json_exclusive(run_dir / f"repair/results/{task['task_id']}.json", result)
    return result


def _bound_run_file(run_dir: Path, relative: Any, *, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ZBatchError(f"retry13 {label}路径为空")
    path = (run_dir / relative).resolve()
    if not path.is_relative_to(run_dir.resolve()) or not path.is_file():
        raise ZBatchError(f"retry13 {label}路径越界或不存在")
    return path


def _rebuild_task_result(
    *, run_dir: Path, plan: Mapping[str, Any], task: Mapping[str, Any]
) -> dict[str, Any]:
    """只从冻结请求、原始响应与检查点重建结果，不信中间结果文件。"""

    task_id = str(task["task_id"])
    checkpoint_root = run_dir / f"repair/checkpoints/{task_id}"
    seal = z83_retry_transport.validate_checkpoint_bundle(checkpoint_root)
    if seal.get("mechanical_verdict") != "pass" or seal.get("contract_version") != CONTRACT_VERSION:
        raise ZBatchError(f"retry13 {task_id} 检查点不是合同 PASS")
    request_record = read_json(checkpoint_root / "01_request.json")
    response_record = read_json(checkpoint_root / "02_response.json")
    usage_record = read_json(checkpoint_root / "03_usage.json")
    attempt_document = read_json(checkpoint_root / "04_attempts.json")
    checkpoint_attempts = attempt_document.get("rows")
    global_attempts = _task_attempt_rows(run_dir, task_id)
    if checkpoint_attempts != global_attempts:
        raise ZBatchError(f"retry13 {task_id} 检查点与全局尝试账不一致")
    request_path = _bound_run_file(
        run_dir, request_record.get("request_artifact_path"), label="请求工件"
    )
    raw_path = _bound_run_file(
        run_dir, response_record.get("raw_response_path"), label="原始响应"
    )
    actual_request = read_json(request_path)
    preflight = read_json(run_dir / "repair/atomic_preflight.json")
    preflight_rows = {
        str(row.get("task_id") or ""): row
        for row in preflight.get("rows", [])
        if isinstance(row, Mapping)
    }
    preflight_row = preflight_rows.get(task_id)
    if not isinstance(preflight_row, Mapping):
        raise ZBatchError(f"retry13 {task_id} 缺冻结请求总票")
    prepared_path = _bound_run_file(
        run_dir, actual_request.get("prepared_request_path"), label="冻结单对象请求"
    )
    prepared_body = read_json(prepared_path)
    request_sha = z83.sha256_file(request_path)
    wire_sha = sha256_bytes(
        json.dumps(prepared_body, ensure_ascii=False).encode("utf-8")
    )
    raw = raw_path.read_bytes()
    raw_sha = sha256_bytes(raw)
    expected_model = str(request_record.get("model") or "")
    response_json, content, finish_reason, usage = _parse_sensenova_envelope(
        raw, expected_model=expected_model
    )
    normalized, diagnostics = parse_single_object_result(
        content,
        catalog=z83._catalog(run_dir, int(task["chapter"])),
        required_anchor_ids=list(task["required_anchor_ids"]),
    )
    if (
        actual_request.get("schema_version") != "z83-retry13-actual-request-v1"
        or actual_request.get("run_id") != run_dir.name
        or actual_request.get("logical_request_id") != task_id
        or actual_request.get("parent_event_id") != task.get("parent_event_id")
        or actual_request.get("fact_ordinal") != task.get("fact_ordinal")
        or actual_request.get("fact_count") != task.get("fact_count")
        or actual_request.get("stage") != "targeted_retry_single_object"
        or actual_request.get("contract_version") != CONTRACT_VERSION
        or actual_request.get("plan_sha256")
        != z83.sha256_file(run_dir / "repair/atomic_plan.json")
        or actual_request.get("prepared_request_path")
        != preflight_row.get("prepared_request_path")
        or actual_request.get("prepared_request_sha256")
        != z83.sha256_file(prepared_path)
        or preflight_row.get("prepared_request_sha256")
        != z83.sha256_file(prepared_path)
        or preflight_row.get("body_canonical_sha256") != canonical_sha(prepared_body)
        or preflight_row.get("fact_target_sha256") != task.get("fact_target_sha256")
        or actual_request.get("body") != prepared_body
        or actual_request.get("_security") != "no_api_key_no_authorization"
        or request_record.get("logical_request_id") != task_id
        or request_record.get("request_artifact_sha256") != request_sha
        or request_record.get("wire_body_sha256") != wire_sha
        or request_record.get("contract_version") != CONTRACT_VERSION
        or response_record.get("logical_request_id") != task_id
        or response_record.get("request_artifact_sha256") != request_sha
        or response_record.get("http_status") != 200
        or response_record.get("raw_response_sha256") != raw_sha
        or response_record.get("response_model") != expected_model
        or response_record.get("finish_reason") != finish_reason
        or response_record.get("content_sha256")
        != sha256_bytes(content.encode("utf-8"))
        or response_record.get("error_code") is not None
        or usage_record.get("logical_request_id") != task_id
        or usage_record.get("request_artifact_sha256") != request_sha
        or usage_record.get("raw_response_sha256") != raw_sha
        or usage_record.get("usage") != usage
        or response_json.get("usage") != usage
    ):
        raise ZBatchError(f"retry13 {task_id} 请求／响应／usage 无法相互重建")
    expected = _task_result_document(
        run_dir=run_dir,
        task=task,
        request_record=request_record,
        raw_response_sha256=raw_sha,
        content=content,
        normalized=normalized,
        diagnostics=diagnostics,
        checkpoint_seal=seal,
    )
    stored = read_json(run_dir / f"repair/results/{task_id}.json")
    if stored != expected:
        raise ZBatchError(f"retry13 {task_id} 结果文件不能从原始五件套重建")
    return expected


def _rebuild_all_task_results(
    *, run_dir: Path, plan: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    task_ids = {str(task["task_id"]) for task in plan["tasks"]}
    result_dir = run_dir / "repair/results"
    checkpoint_dir = run_dir / "repair/checkpoints"
    if (
        {path.stem for path in result_dir.glob("*.json")} != task_ids
        or {path.name for path in checkpoint_dir.iterdir() if path.is_dir()} != task_ids
    ):
        raise ZBatchError("retry13 结果或不可变检查点不是32份唯一工件")
    return {
        str(task["task_id"]): _rebuild_task_result(
            run_dir=run_dir, plan=plan, task=task
        )
        for task in plan["tasks"]
    }


def _stable_mechanical_verification_sha256(receipt: Mapping[str, Any]) -> str:
    """机械验收身份忽略“回读进程当下是否载入密钥”这个运行态。"""

    stable = copy.deepcopy(dict(receipt))
    secret_scan = stable.get("secret_scan")
    if isinstance(secret_scan, dict):
        secret_scan.pop("real_secret_available_for_scan", None)
    return canonical_sha(stable)


def _materialize_completed_repair(
    *, run_dir: Path, plan: Mapping[str, Any]
) -> dict[str, Any]:
    results = _rebuild_all_task_results(run_dir=run_dir, plan=plan)
    replacements, parent_ledgers = aggregate_parent_results(plan, results)
    main_stage = run_dir / "main"
    main_lineage = z83._validate_main_lineage(run_dir)["rows"]
    ledger_rows: list[dict[str, Any]] = []
    main_event_counts: dict[int, int] = {}
    final_event_counts: dict[int, int] = {}
    rewritten_descendant_counts: dict[int, int] = {}
    for chapter in z83.TARGET_CHAPTERS:
        original = read_json(z83._model_file(main_stage, chapter))
        lineage_original = read_json(z83._event_file(main_stage, chapter))
        original_events = original.get("events")
        if not isinstance(original_events, list):
            raise ZBatchError(f"retry13 第{chapter}章主样缺事件数组")
        main_event_counts[chapter] = len(original_events)
        if main_event_counts[chapter] != EXPECTED_MAIN_EVENT_COUNTS[chapter]:
            raise ZBatchError(f"retry13 第{chapter}章主样事件数不等于冻结基线")
        final_json = z77.apply_replacements(
            original,
            chapter=chapter,
            replacements=replacements.get(chapter, {}),
        )
        materialized, audit = neutral_extract.process_model_data(
            final_json, chapter=chapter, catalog=z83._catalog(run_dir, chapter)
        )
        receipts_by_index: dict[int, dict[str, Any]] = {}
        for parent in plan["parents"]:
            if int(parent["chapter"]) != chapter:
                continue
            event_id = str(parent["event_id"])
            index = int(event_id.rsplit("-", 1)[1]) - 1
            parent_ledger = next(
                row for row in parent_ledgers if row["parent_event_id"] == event_id
            )
            receipts_by_index[index] = {
                "reason_codes": list(parent["reason_codes"]),
                **parent_ledger,
            }
        prior_rows = {
            event_id: row
            for event_id, row in main_lineage.items()
            if int(event_id[4:8]) == chapter
        }
        lineage, descendants = z83._build_event_lineage(
            chapter=chapter,
            original=lineage_original,
            final=materialized,
            replacements=replacements.get(chapter, {}),
            retry_receipts=receipts_by_index,
            stage="semantic_targeted_retry_atomic_program_split",
            prior_rows=prior_rows,
        )
        materialized_events = materialized.get("events")
        if not isinstance(materialized_events, list):
            raise ZBatchError(f"retry13 第{chapter}章物化产物缺事件数组")
        final_event_counts[chapter] = len(materialized_events)
        if final_event_counts[chapter] != EXPECTED_FINAL_EVENT_COUNTS[chapter]:
            raise ZBatchError(f"retry13 第{chapter}章物化后事件数不等于冻结值")
        chapter_parent_ids = [
            str(parent["event_id"])
            for parent in plan["parents"]
            if int(parent["chapter"]) == chapter
        ]
        chapter_descendants = [
            event_id
            for parent_id in chapter_parent_ids
            for event_id in descendants[parent_id]
        ]
        rewritten_descendant_counts[chapter] = len(chapter_descendants)
        if (
            len(chapter_descendants) != len(set(chapter_descendants))
            or rewritten_descendant_counts[chapter]
            != EXPECTED_REWRITTEN_DESCENDANT_COUNTS[chapter]
        ):
            raise ZBatchError(f"retry13 第{chapter}章重写后代数不等于冻结值")
        for index, receipt in sorted(receipts_by_index.items()):
            input_event_id = str(original["events"][index]["event_id"])
            parent = next(row for row in plan["parents"] if row["event_id"] == input_event_id)
            row = {
                "schema_version": "z83-retry13-parent-rewrite-ledger-v1",
                "chapter": chapter,
                "original_event_id": input_event_id,
                "original_event_sha256": parent["event_sha256"],
                "source_event_id": parent["source_event_id"],
                "source_event_sha256": parent["source_event_sha256"],
                "source_identity_sha256": parent["source_identity_sha256"],
                "source_retry_count_before": prior_rows[input_event_id]["retry_count"],
                "source_retry_count_after": prior_rows[input_event_id]["retry_count"] + 1,
                "reason_codes": list(parent["reason_codes"]),
                "materialized_event_ids": descendants[input_event_id],
                "replacement_count": receipt["replacement_count"],
                "child_results": receipt["child_results"],
                "fact_closed_set_semantic_review": "pending_not_inferred_from_sha",
            }
            row["row_sha256"] = canonical_sha(row)
            ledger_rows.append(row)
        write_json_atomic(
            run_dir / f"repair/01_extract/model_json/ch{chapter:04d}.json", final_json
        )
        write_json_atomic(
            run_dir / f"repair/01_extract/events/ch{chapter:04d}.json", materialized
        )
        write_json_atomic(
            run_dir / f"repair/01_extract/program_audits/ch{chapter:04d}.json", audit
        )
        write_json_atomic(
            run_dir / f"repair/01_extract/event_lineage/ch{chapter:04d}.json", lineage
        )
    if (
        len(ledger_rows) != 13
        or sum(main_event_counts.values()) != 156
        or sum(final_event_counts.values()) != 175
        or sum(rewritten_descendant_counts.values()) != 32
    ):
        raise ZBatchError("retry13 父源／主样／物化／后代总数不合同")
    ledger_path = run_dir / "repair/targeted_retry_ledger.jsonl"
    _write_bytes_exclusive(
        ledger_path,
        b"".join(
            (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            for row in ledger_rows
        ),
    )
    mechanical = z83.verify_event_stage(
        run_dir,
        run_dir / "repair",
        schema_version="z83-retry13-repair-mechanical-verification-v1",
    )
    attempts = _read_jsonl(run_dir / "repair/call_attempts.jsonl")
    reservations = _read_jsonl(run_dir / "repair/attempt_reservations.jsonl")
    if len(attempts) != len(reservations):
        raise ZBatchError("retry13 收口发现 attempt 与发网前占用票数量不一致")
    reservation_keys = []
    for row in reservations:
        preimage = {key: value for key, value in row.items() if key != "row_sha256"}
        if row.get("row_sha256") != canonical_sha(preimage):
            raise ZBatchError("retry13 发网前占用票行 SHA 不能重建")
        reservation_keys.append(
            (
                row.get("logical_request_id"),
                row.get("attempt"),
                row.get("request_artifact_sha256"),
                row.get("wire_body_sha256"),
            )
        )
    attempt_keys = [
        (
            row.get("logical_request_id"),
            row.get("attempt"),
            row.get("request_artifact_sha256"),
            row.get("wire_body_sha256"),
        )
        for row in attempts
    ]
    if reservation_keys != attempt_keys or len(set(reservation_keys)) != len(reservation_keys):
        raise ZBatchError("retry13 占用票与终态 attempt 不是逐次一一对应")
    usage_rows = _read_jsonl(run_dir / "repair/usage.jsonl")
    if len(usage_rows) != len(plan["tasks"]):
        raise ZBatchError("retry13 收口 usage 不是每个逻辑请求恰好一行")
    metrics = {
        "schema_version": "z83-retry13-repair-metrics-v1",
        "status": "completed_candidate_silver_only_awaiting_targeted_semantic_review",
        "parent_rewrite_count": 13,
        "logical_request_count": len(plan["tasks"]),
        "network_attempts": len(attempts),
        "http_429_count": sum(row.get("http_status") == 429 for row in attempts),
        "usage_row_count": len(usage_rows),
        "main_event_count": sum(main_event_counts.values()),
        "final_event_count": sum(final_event_counts.values()),
        "rewritten_descendant_count": sum(rewritten_descendant_counts.values()),
        "main_event_count_by_chapter": {
            str(chapter): main_event_counts[chapter] for chapter in z83.TARGET_CHAPTERS
        },
        "final_event_count_by_chapter": {
            str(chapter): final_event_counts[chapter] for chapter in z83.TARGET_CHAPTERS
        },
        "rewritten_descendant_count_by_chapter": {
            str(chapter): rewritten_descendant_counts[chapter]
            for chapter in z83.TARGET_CHAPTERS
        },
        "parent_ledgers": parent_ledgers,
        "mechanical_verification_sha256": _stable_mechanical_verification_sha256(
            mechanical
        ),
        "candidate_silver_only": True,
    }
    write_json_atomic(run_dir / "repair/01_extract/metrics.json", metrics)
    final_dir = run_dir / "final"
    if final_dir.exists():
        raise ZBatchError("retry13 final 已存在，拒绝覆盖或挑结果")
    shutil.copytree(run_dir / "repair/01_extract", final_dir / "01_extract")
    write_json_atomic(
        final_dir / "run_manifest.json",
        {
            "schema_version": "z83-retry13-final-event-manifest-v1",
            "status": "awaiting_targeted_semantic_review",
            "source_atomic_plan_sha256": z83.sha256_file(
                run_dir / "repair/atomic_plan.json"
            ),
            "parent_rewrite_count": 13,
            "logical_request_count": len(plan["tasks"]),
            "rewritten_descendant_count": 32,
            "final_event_count": 175,
            "candidate_silver_only": True,
        },
    )
    z83.verify_event_stage(
        run_dir,
        final_dir,
        schema_version="z83-retry13-final-mechanical-verification-v1",
    )
    return metrics


def run_atomic_requests(
    run_dir: Path = DEFAULT_RUN_DIR,
    *,
    opener: Any = None,
    sleeper: Any = None,
    monotonic: Any = None,
    jitter: Any = None,
) -> dict[str, Any]:
    if run_dir.name != RUN_NAME:
        raise ZBatchError("retry13 发网器只准用于获批新运行编号")
    verification = verify_preflight(run_dir)
    plan = _validate_plan(run_dir)
    if plan.get("pending_parent_ids"):
        raise ZBatchError("retry13 尚有 pending_CZ 项，整批不能发网或缩分母")
    route = api_transport.TransportRoute.from_mapping(z83.load_bundle(run_dir).route)
    key = os.environ.get(route.api_key_env)
    if not key:
        raise ZBatchError(f"缺少 {route.api_key_env}；零调用停在发网前")
    repair_dir = run_dir / "repair"
    forbidden = [
        repair_dir / "retry13_run_claim.json",
        repair_dir / "hard_stop.json",
        repair_dir / "retry13_run_manifest.json",
        repair_dir / "call_attempts.jsonl",
        repair_dir / "attempt_reservations.jsonl",
        repair_dir / "usage.jsonl",
        repair_dir / "requests/single_object",
        repair_dir / "raw_responses/single_object",
        repair_dir / "results",
        repair_dir / "checkpoints",
        repair_dir / "01_extract",
    ]
    present = [path.relative_to(run_dir).as_posix() for path in forbidden if path.exists()]
    if present:
        raise ZBatchError(f"retry13 已有发网或收口痕迹，禁止原位续跑：{present}")
    claim = {
        "schema_version": "z83-retry13-run-claim-v1",
        "status": "running_do_not_resume_or_cherry_pick",
        "run_id": run_dir.name,
        "plan_sha256": z83.sha256_file(run_dir / "repair/atomic_plan.json"),
        "preflight_sha256": z83.sha256_file(run_dir / "repair/atomic_preflight.json"),
        "preflight_verification_sha256": canonical_sha(verification),
        "logical_request_count": len(plan["tasks"]),
        "claimed_at": _now_iso(),
    }
    _write_json_exclusive(repair_dir / "retry13_run_claim.json", claim)
    preflight = read_json(repair_dir / "atomic_preflight.json")
    preflight_by_task = {str(row["task_id"]): row for row in preflight["rows"]}
    state = z83_retry_transport.RetryRunState()
    active_task: Mapping[str, Any] | None = None
    try:
        for task in plan["tasks"]:
            active_task = task
            task_id = str(task["task_id"])
            row = preflight_by_task[task_id]
            prepared_path = run_dir / str(row["prepared_request_path"])
            body = read_json(prepared_path)
            request_path, request_sha, wire_body, wire_sha = _build_request_artifact(
                run_dir=run_dir,
                plan=plan,
                task=task,
                preflight_row=row,
                body=body,
                route=route,
            )
            checkpoint_request = _request_checkpoint_record(
                task_id=task_id,
                request_path=request_path,
                request_sha256=request_sha,
                wire_body_sha256=wire_sha,
                model=route.model,
                run_dir=run_dir,
            )
            send_once = _send_once_factory(
                run_dir=run_dir,
                task=task,
                route=route,
                request_sha256=request_sha,
                request_artifact_sha256=request_sha,
                wire_body=wire_body,
                wire_body_sha256=wire_sha,
                opener=opener,
            )
            try:
                result = z83_retry_transport.run_logical_request(
                    logical_request_id=task_id,
                    chapter=int(task["chapter"]),
                    send_once=send_once,
                    attempt_ledger_path=repair_dir / "call_attempts.jsonl",
                    contract_version=CONTRACT_VERSION,
                    state=state,
                    sleeper=sleeper,
                    monotonic=monotonic,
                    jitter=jitter,
                )
                _process_successful_task(
                    run_dir=run_dir,
                    task=task,
                    request_record=checkpoint_request,
                    request_sha256=request_sha,
                    transport_result=result,
                )
            except BaseException as exc:
                reason = (
                    exc.reason_code
                    if isinstance(exc, z83_retry_transport.RetryTransportHardStop)
                    else "single_object_contract_or_processing_failure"
                )
                _seal_failed_checkpoint(
                    run_dir=run_dir,
                    task=task,
                    request_record=checkpoint_request,
                    request_sha256=request_sha,
                    error_code=reason,
                )
                _write_hard_stop(
                    run_dir=run_dir,
                    error=exc,
                    active_task=task,
                    reason_code=reason,
                )
                raise
        metrics = _materialize_completed_repair(run_dir=run_dir, plan=plan)
        manifest = {
            "schema_version": "z83-retry13-run-manifest-v1",
            "status": "completed_candidate_silver_only_awaiting_targeted_semantic_review",
            "run_claim": claim,
            "logical_request_count": len(plan["tasks"]),
            "network_attempts": metrics["network_attempts"],
            "http_429_count": metrics["http_429_count"],
            "rewritten_descendant_count": metrics["rewritten_descendant_count"],
            "final_event_count": metrics["final_event_count"],
            "prefix_cherry_picked": False,
            "candidate_silver_only": True,
        }
        _write_json_exclusive(repair_dir / "retry13_run_manifest.json", manifest)
        return metrics
    except BaseException as exc:
        if not (repair_dir / "hard_stop.json").exists():
            _write_hard_stop(
                run_dir=run_dir,
                error=exc,
                active_task=active_task,
                reason_code="retry13_unexpected_hard_stop",
            )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("plan", "preflight", "verify-preflight", "run"),
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    z83.assert_safe_run_dir(run_dir)
    if args.action == "plan":
        result = create_plan(run_dir)
    elif args.action == "preflight":
        result = preflight(run_dir)
    elif args.action == "verify-preflight":
        result = verify_preflight(run_dir)
    else:
        result = run_atomic_requests(run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
