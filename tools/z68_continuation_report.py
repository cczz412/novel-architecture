#!/usr/bin/env python3
"""生成第68道32k兼容续跑的语义成绩、差距账和停点回包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import z68_continuation_32k as z68c


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.1_20260720"
REPORT = ROOT / "reports/Z68续令_32k参数兼容修复与裸考成绩_20260720"
GOLD = ROOT / "reports/Z56_金标双轨分层与全链体检_20260719/第3章结构层金标v1.1.json"
BASELINE_SCORE = (
    ROOT / "reports/Z57_稳定语义身份解耦与全链后半_20260719/第3章当章层诚实成绩单.json"
)
PRIOR_HARD_STOP_REPORT = (
    ROOT / "reports/Z68_修正版请求体裸考_20260720/运输与真实成本补账.json"
)
TARGET_CHAPTERS = (3, 4, 5, 13, 19)


GOLD_ADJUDICATION: dict[str, dict[str, Any]] = {
    "GOLD-C0003-01": {
        "verdict": "semantic_shadow",
        "candidate_event_ids": ["EV-C0003-03"],
        "note": "抽到了大学面试和推荐信，但事件句漏掉‘两天后’这一时间限定。",
    },
    "GOLD-C0003-02": {
        "verdict": "semantic_shadow",
        "candidate_event_ids": ["EV-C0003-04"],
        "note": "只把梅丽莎即将出来写成藏枪条件，没有独立写出她打开里间门走出。",
    },
    "GOLD-C0003-03": {
        "verdict": "strict_hit",
        "candidate_event_ids": ["EV-C0003-04"],
        "note": "主体、藏枪动作、抽屉去向和梅丽莎将出来的条件均在。",
    },
    "GOLD-C0003-04": {
        "verdict": "strict_hit",
        "candidate_event_ids": ["EV-C0003-05"],
        "note": "明确写出周明瑞通过触摸确认太阳穴伤口愈合。",
    },
    "GOLD-C0003-05": {
        "verdict": "strict_hit",
        "candidate_event_ids": ["EV-C0003-07"],
        "note": "拿表、正确操作、秒针走动、校时和归还均完整。",
    },
    "GOLD-C0003-06": {
        "verdict": "strict_hit",
        "candidate_event_ids": ["EV-C0003-11"],
        "note": "购买面包、肉和豌豆并做豌豆炖羔羊肉的安排完整。",
    },
    "GOLD-C0003-07": {
        "verdict": "strict_hit",
        "candidate_event_ids": ["EV-C0003-20"],
        "note": "明确写出梅丽莎关门、离开公寓并前往技术学校。",
    },
    "GOLD-C0003-08": {
        "verdict": "strict_hit",
        "candidate_event_ids": ["EV-C0003-21"],
        "note": "转向转运仪式和想回家的目标均明确。",
    },
    "GOLD-C0003-09": {
        "verdict": "semantic_shadow",
        "candidate_event_ids": ["EV-C0003-02", "EV-C0003-09"],
        "note": "看见了记忆碎片和自杀诡异，但手枪来历、笔记句子及记忆缺失组合没有抽全。",
    },
    "GOLD-C0003-10": {
        "verdict": "semantic_shadow",
        "candidate_event_ids": ["EV-C0003-02", "EV-C0003-03"],
        "note": "看见了记忆碎片、面试和推荐信，漏掉面试风险及对全家收入的意义。",
    },
    "GOLD-C0003-11": {
        "verdict": "semantic_shadow",
        "candidate_event_ids": ["EV-C0003-07"],
        "note": "操作怀表显示了机械能力，但没有抽出蒸汽机械师志向和她宣称修好怀表。",
    },
    "GOLD-C0003-12": {
        "verdict": "miss",
        "candidate_event_ids": [],
        "note": "没有抽到班森为保工作承担重任，也没有抽到克莱恩想帮哥哥却暂时无力。",
    },
    "GOLD-C0003-13": {
        "verdict": "semantic_shadow",
        "candidate_event_ids": ["EV-C0003-11", "EV-C0003-12", "EV-C0003-13"],
        "note": "抽到了羔羊肉安排、劣等茶和黑麦面包，未明确合成‘平日肉少、为面试特意安排’。",
    },
    "GOLD-C0003-14": {
        "verdict": "semantic_shadow",
        "candidate_event_ids": ["EV-C0003-16", "EV-C0003-20"],
        "note": "抽到了出门准备和去学校，漏掉省车费、提前出门及步行约五十分钟。",
    },
}


CURRENT_ADJUDICATION: dict[str, dict[str, Any]] = {
    "B-C0003-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0003-03"],
        "note": "面试事项保留，但‘两天后’时间条件丢失。",
    },
    "A-C0003-01": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0003-04"],
        "note": "藏枪事实保留，并补出当时条件和响声。",
    },
    "A-C0003-02": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0003-05"],
        "note": "伤口愈合事实保留；引用锚前移一格但语义连续。",
    },
    "A-C0003-03": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0003-07"],
        "note": "怀表操作、走动和校时均保留。",
    },
    "B-C0003-02": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0003-11"],
        "note": "采购内容和做饭用途保留，但事件句漏掉‘当天外出采购时’的时间条件。",
    },
    "C-C0003-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0003-21"],
        "note": "保留转运仪式和回家目标，没有写出能否成功及安全路径这一承诺结构。",
    },
    "A-C0004-01": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0004-06", "EV-C0004-07", "EV-C0004-08"],
        "note": "携枪和调整弹巢被拆成三个原子事件，组合后语义完整。",
    },
    "B-C0004-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0004-16", "EV-C0004-17"],
        "note": "保留愿意尝试和免费条件，没有写出实际占卜及取得结果。",
    },
    "A-C0005-01": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0005-09"],
        "note": "两种本地语言翻译完整保留。",
    },
    "B-C0005-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0005-09"],
        "note": "保留翻译动作，漏掉原中文咒语无效和隔天重试计划。",
    },
    "A-C0005-02": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0005-11"],
        "note": "逆时针正方形路线和四句名号完整保留。",
    },
    "A-C0005-03": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0005-12"],
        "note": "保留仪式异状和抵达灰雾，漏掉呢喃声退去及成功睁眼两个明确结果。",
    },
    "A-C0005-04": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0005-13"],
        "note": "触摸、水纹和深红爆发完整保留。",
    },
    "A-C0005-05": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0005-14"],
        "note": "第二颗星辰发光及精神涣散完整保留。",
    },
    "A-C0005-06": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0005-17"],
        "note": "保留三方出现和相互发现，漏掉恢复视线及斜对面身影朦胧的具体视觉事实。",
    },
    "A-C0013-01": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0013-01"],
        "note": "值夜者身份保留。",
    },
    "A-C0013-02": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0013-01"],
        "note": "进入梦境并引导的动作保留。",
    },
    "D-C0013-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0013-01"],
        "note": "保留邓恩的具体梦境引导实例，没有抽成可复用的熟练操作者规则。",
    },
    "A-C0013-03": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0013-02"],
        "note": "遗失部分记忆的确认保留。",
    },
    "A-C0013-04": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0013-04"],
        "note": "笔记丢失和克莱恩是唯一线索均保留。",
    },
    "B-C0013-01": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0013-03", "EV-C0013-05", "EV-C0013-06"],
        "note": "见专家、锁门离家和前往韦尔奇住所被拆开，组合后保留。",
    },
    "B-C0013-02": {
        "verdict": "not_observed",
        "candidate_event_ids": [],
        "note": "没有抽到专家排除诅咒等条件后解除直接嫌疑这一待触发安排。",
    },
    "C-C0013-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0013-07"],
        "note": "抽到非凡事件可能再次降临，但没有明确落到克莱恩当前风险能否解除。",
    },
    "D-C0013-02": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0013-07"],
        "note": "保留恐怖方式再次降临，漏掉‘原以为结束且恢复正常’的前置条件。",
    },
    "A-C0013-05": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0013-09"],
        "note": "专家是真正通灵者的事实保留，并补出对外身份。",
    },
    "B-C0019-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0019-01"],
        "note": "保留成为非凡者的意愿和风险权衡，漏掉功劳或人员安排两条机会条件。",
    },
    "B-C0019-02": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0019-02"],
        "note": "保留每天巡查和重点道路，漏掉‘上午或下午’的时间条件。",
    },
    "B-C0019-03": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0019-03"],
        "note": "保留武器库阅读和读完轮换，漏掉‘不在外巡时’的触发条件。",
    },
    "A-C0019-01": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0019-04"],
        "note": "不得随意靠近查尼斯门及厄运后果完整保留。",
    },
    "D-C0019-01": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0019-05"],
        "note": "保留四级分类标准，事件句压缩了总部主体和危险、保密两套尺度。",
    },
    "D-C0019-02": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0019-05"],
        "note": "保留四级分类，事件句没有明确写出‘等级数字＋序号’的编号读法。",
    },
    "B-C0019-04": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0019-06"],
        "note": "发现目标后不惊动并回来禀报完整保留。",
    },
    "A-C0019-02": {
        "verdict": "partially_preserved",
        "candidate_event_ids": ["EV-C0019-06"],
        "note": "只写到0-08的外形，漏掉普通羽毛笔和无需墨水也能书写两项明确信息。",
    },
    "B-C0019-05": {
        "verdict": "preserved",
        "candidate_event_ids": ["EV-C0019-07"],
        "note": "去武器库找老尼尔安排阅读完整保留。",
    },
}


TEAM_REVIEW = {
    "status": "pass_p0_p1_p2_0_0_0",
    "note": "最终回读确认回包证据、统计和边界一致；只表示审计收口，候选质量仍不升默认。",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event_map(run_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for chapter in TARGET_CHAPTERS:
        rows = read_json(run_dir / f"01_extract/events/ch{chapter:04d}.json")["events"]
        for row in rows:
            result[str(row["event_id"])] = row
    return result


def formal_summary(record: Mapping[str, Any]) -> str:
    return z68c.formal_record_summary(record)


def gold_score(run_dir: Path) -> dict[str, Any]:
    gold = read_json(GOLD)
    events = event_map(run_dir)
    gold_parts: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for item in gold["layered_items"]:
        parts = [part for part in item["parts"] if part.get("score_in_single_chapter")]
        if len(parts) != 1:
            raise RuntimeError(f"当章金标层数量异常：{item['item_id']}")
        gold_parts[str(item["item_id"])] = (item, parts[0])
    if set(gold_parts) != set(GOLD_ADJUDICATION):
        raise RuntimeError("14条金标判词没有一一覆盖")
    rows: list[dict[str, Any]] = []
    for gold_id, (item, part) in gold_parts.items():
        decision = GOLD_ADJUDICATION[gold_id]
        candidate_ids = decision["candidate_event_ids"]
        missing = [event_id for event_id in candidate_ids if event_id not in events]
        if missing:
            raise RuntimeError(f"金标判词引用不存在的候选事件：{missing}")
        rows.append(
            {
                "gold_item_id": gold_id,
                "part_id": part["part_id"],
                "claim": part["claim"],
                "gold_anchor_ids": [row["anchor_id"] for row in part["source_evidence"]],
                "verdict": decision["verdict"],
                "candidate_event_ids": candidate_ids,
                "candidate_events": [
                    {"event_id": event_id, "event": events[event_id]["event"]}
                    for event_id in candidate_ids
                ],
                "semantic_review_note": decision["note"],
            }
        )
    counts = Counter(row["verdict"] for row in rows)
    strict = counts["strict_hit"]
    shadow_only = counts["semantic_shadow"]
    recalled = strict + shadow_only
    baseline = read_json(BASELINE_SCORE)["summary"]
    return {
        "schema_version": "z68-continuation-chapter3-gold-semantic-score-v1",
        "status": "completed_candidate_score_only",
        "condition": "连续正文＋冻结目录双视图；第3章复用16k正常stop样张，续跑章采用32k上限",
        "gold": {"path": str(GOLD.relative_to(ROOT)), "sha256": sha256_file(GOLD)},
        "policy": {
            "strict_hit": "候选事件句完整覆盖金标事实和必要限定；证据锚不能替事件句补写缺失语义",
            "semantic_shadow": "看见同一事实或同一结构附近内容，但必要限定或组合关系不全",
            "miss": "没有同一事实或结构的候选影子",
            "hindsight": "回看层单列，不计单章漏项",
        },
        "summary": {
            "gold_total": len(rows),
            "strict_hit": strict,
            "strict_hit_rate": strict / len(rows),
            "semantic_shadow_only": shadow_only,
            "semantic_shadow_recalled": recalled,
            "semantic_shadow_recall_rate": recalled / len(rows),
            "miss": counts["miss"],
            "baseline_strict_hit": baseline["hit"],
            "baseline_semantic_shadow_recalled": baseline["shadow_recalled"],
            "strict_hit_delta": strict - baseline["hit"],
            "semantic_shadow_recalled_delta": recalled - baseline["shadow_recalled"],
        },
        "rows": rows,
        "hindsight_layer_excluded": [
            {
                "gold_item_id": item["item_id"],
                "part_id": part["part_id"],
                "claim": part["claim"],
                "single_chapter_score": "excluded",
            }
            for item in gold["layered_items"]
            for part in item["parts"]
            if part.get("layer") == "回看件"
        ],
        "write_policy": "只出候选成绩，不修改金标、现役记录、默认链或分类规则。",
    }


def current_diff(run_dir: Path) -> dict[str, Any]:
    current = read_json(run_dir / "inputs/current_formal_records_122.json")["records"]
    target = [row for row in current if row.get("_source_chapter") in TARGET_CHAPTERS]
    if set(str(row["id"]) for row in target) != set(CURRENT_ADJUDICATION):
        raise RuntimeError("五靶章现役记录判词没有一一覆盖")
    events = event_map(run_dir)
    rows: list[dict[str, Any]] = []
    for record in target:
        record_id = str(record["id"])
        decision = CURRENT_ADJUDICATION[record_id]
        candidate_ids = decision["candidate_event_ids"]
        missing = [event_id for event_id in candidate_ids if event_id not in events]
        if missing:
            raise RuntimeError(f"现役diff引用不存在的候选事件：{missing}")
        rows.append(
            {
                "chapter": record["_source_chapter"],
                "record_id": record_id,
                "type": record["type"],
                "current_semantics": formal_summary(record),
                "current_anchor_ids": [row["anchor_id"] for row in record.get("anchors", [])],
                "verdict": decision["verdict"],
                "candidate_event_ids": candidate_ids,
                "candidate_events": [
                    {"event_id": event_id, "event": events[event_id]["event"]}
                    for event_id in candidate_ids
                ],
                "semantic_review_note": decision["note"],
            }
        )
    counts = Counter(row["verdict"] for row in rows)
    chapter_summary: dict[str, Any] = {}
    for chapter in TARGET_CHAPTERS:
        chapter_rows = [row for row in rows if row["chapter"] == chapter]
        chapter_counts = Counter(row["verdict"] for row in chapter_rows)
        chapter_summary[str(chapter)] = {"total": len(chapter_rows), **dict(chapter_counts)}
    return {
        "schema_version": "z68-continuation-current122-semantic-diff-v1",
        "status": "completed_candidate_diff_only",
        "scope": {
            "current_records_total": 122,
            "target_chapters": list(TARGET_CHAPTERS),
            "target_records": len(rows),
        },
        "verdict_policy": {
            "preserved": "同一语义完整保留；允许一个旧记录被多个原子事件拆开承载",
            "partially_preserved": "存在同一事实影子，但旧记录的必要条件、结果或规则概括不全",
            "not_observed": "候选事件池没有同一语义影子",
        },
        "summary": {"total": len(rows), **dict(counts), "by_chapter": chapter_summary},
        "quality_gate": {
            "old_event_no_degradation": counts["partially_preserved"] == 0
            and counts["not_observed"] == 0,
            "disposition": "candidate_quality_fail_do_not_promote",
            "reason": "存在部分保留和未观察旧记录，只登记候选差距，不回写现役件。",
        },
        "rows": rows,
    }


def overflow_report(run_dir: Path, gold_doc: Mapping[str, Any], current_doc: Mapping[str, Any]) -> dict[str, Any]:
    events = event_map(run_dir)
    gold_used = {
        event_id for row in gold_doc["rows"] for event_id in row["candidate_event_ids"]
    }
    current_used_by_chapter: dict[int, set[str]] = {chapter: set() for chapter in TARGET_CHAPTERS}
    for row in current_doc["rows"]:
        current_used_by_chapter[int(row["chapter"])].update(row["candidate_event_ids"])
    gold_overflow = [
        {**events[event_id], "status": "待判溢出"}
        for event_id in sorted(events)
        if event_id.startswith("EV-C0003-") and event_id not in gold_used
    ]
    current_unmapped: dict[str, list[dict[str, Any]]] = {}
    for chapter in TARGET_CHAPTERS:
        prefix = f"EV-C{chapter:04d}-"
        current_unmapped[str(chapter)] = [
            {**events[event_id], "status": "待判候选；仅表示未映射现役记录"}
            for event_id in sorted(events)
            if event_id.startswith(prefix) and event_id not in current_used_by_chapter[chapter]
        ]
    return {
        "schema_version": "z68-continuation-pending-overflow-v1",
        "status": "pending_no_self_adjudication",
        "chapter3_gold_overflow": {
            "count": len(gold_overflow),
            "events": gold_overflow,
        },
        "current122_unmapped_candidates": {
            "count": sum(len(rows) for rows in current_unmapped.values()),
            "by_chapter": current_unmapped,
        },
        "boundary": "未映射不等于正确、错误或应并表；全部留给CZ另拍。",
    }


def exact_secret_scan(run_dir: Path) -> dict[str, Any]:
    secret = os.environ.get("SENSENOVA_API_KEY")
    if not secret:
        raise RuntimeError("缺少 SENSENOVA_API_KEY，无法做真实密钥精确扫描")
    secret_bytes = secret.encode("utf-8")
    exact_hits: list[str] = []
    authorization_hits: list[str] = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        data = path.read_bytes()
        relative = path.relative_to(ROOT).as_posix()
        if secret_bytes in data:
            exact_hits.append(relative)
        if b"Authorization" in data:
            authorization_hits.append(relative)
    return {
        "scope": run_dir.relative_to(ROOT).as_posix(),
        "method": "从现有本机凭据环境读取实际密钥，只做逐文件精确字面量扫描；不打印、不写入密钥",
        "exact_key_file_hits": len(exact_hits),
        "exact_key_hit_paths": exact_hits,
        "authorization_literal_file_hits": len(authorization_hits),
        "authorization_literal_paths": authorization_hits,
        "independent_replay_boundary": "实际密钥不落盘；独立复跑需要同一凭据环境。",
    }


def transport_receipt(run_dir: Path) -> dict[str, Any]:
    metrics = read_json(run_dir / "01_extract/metrics.json")
    mechanics = read_json(run_dir / "analysis/机械十项成绩单.json")
    prior = read_json(PRIOR_HARD_STOP_REPORT)
    usage = metrics["transport"]["usage"]
    prior_ch5 = prior["chapters"][2]["attempts"][1]["usage"]
    candidate_usage = mechanics["ten_metrics"]["10_token成本对第57道"]["candidate"]
    baseline_usage = mechanics["ten_metrics"]["10_token成本对第57道"][
        "baseline_reused_from_z56_z57"
    ]
    return {
        "schema_version": "z68-continuation-transport-and-cost-v1",
        "status": "completed_candidate_only_mixed_caps",
        "logical_samples": {"new": 3, "reused": 2, "scorecard_total": 5},
        "transport": metrics["transport"],
        "chapter5_compatibility_comparison": {
            "prior_16k_invalid_response": {
                "finish_reason": "length",
                "formal_content_characters": 0,
                **prior_ch5,
            },
            "current_32k_valid_response": usage["rows"][0],
            "verdict": "本次32k样张正常stop并交出正文；只证明这次参数兼容修复成功，不外推稳定胜率。",
        },
        "five_chapter_condition_cost": {
            "candidate": candidate_usage,
            "baseline": baseline_usage,
            "total_token_delta": candidate_usage["totals"]["total_tokens"]
            - baseline_usage["totals"]["total_tokens"],
            "total_token_delta_rate": (
                candidate_usage["totals"]["total_tokens"]
                - baseline_usage["totals"]["total_tokens"]
            )
            / baseline_usage["totals"]["total_tokens"],
            "elapsed_ms_delta": candidate_usage["totals"]["elapsed_ms"]
            - baseline_usage["totals"]["elapsed_ms"],
            "elapsed_ms_delta_rate": (
                candidate_usage["totals"]["elapsed_ms"]
                - baseline_usage["totals"]["elapsed_ms"]
            )
            / baseline_usage["totals"]["elapsed_ms"],
        },
        "unknown_cost_boundary": "第13章首次HTTP 429没有usage，不能断言供应商计费为0。",
    }


def assert_main_semantic_counts(markdown: str, current_doc: Mapping[str, Any]) -> None:
    summary = current_doc["summary"]
    preserved = int(summary.get("preserved", 0))
    partial = int(summary.get("partially_preserved", 0))
    missing = int(summary.get("not_observed", 0))
    required = (
        f"只做到{preserved}条完整保留、{partial}条部分保留、{missing}条未观察",
        f"完整保留 {preserved}，部分保留 {partial}，未观察 {missing}",
        f"仍有{missing}条现役记录完全未观察、{partial}条只部分保留",
    )
    absent = [marker for marker in required if marker not in markdown]
    if absent:
        raise RuntimeError(f"主回包统计没有跟随现役diff：{absent}")


def build_documents(report_dir: Path) -> dict[str, Any]:
    manifest = read_json(RUN / "run_manifest.json")
    if manifest.get("status") != "completed_candidate_only_mixed_caps":
        raise RuntimeError("续跑未完成，禁止生成成绩回包")
    verification = read_json(RUN / "mechanical_verification.json")
    if verification.get("status") != "pass":
        raise RuntimeError("机械验收未通过")
    report_dir.mkdir(parents=True, exist_ok=True)
    gold_doc = gold_score(RUN)
    current_doc = current_diff(RUN)
    overflow_doc = overflow_report(RUN, gold_doc, current_doc)
    transport_doc = transport_receipt(RUN)
    preflight = read_json(RUN / "preflight.json")
    mechanics = read_json(RUN / "analysis/机械十项成绩单.json")
    recorded_at = read_json(RUN / "responses/neutral_extract/ch0019_meta.json")["at"]
    supply_doc = {
        "schema_version": "z68-continuation-input-protection-v1",
        "status": "pass",
        "run": RUN.relative_to(ROOT).as_posix(),
        "single_variable": preflight["single_variable"],
        "request_rows": preflight["rows"],
        "reused_chapters": preflight["reused_chapters"],
        "called_chapters": preflight["called_chapters"],
        "protected": preflight["protected"],
        "mechanical_verification": {
            "path": (RUN / "mechanical_verification.json").relative_to(ROOT).as_posix(),
            "sha256": sha256_file(RUN / "mechanical_verification.json"),
            "status": verification["status"],
        },
        "protected_state": {
            "protected_hashes_equal_before_after": True,
            "prior_run_unchanged": True,
            "outbox_unchanged": True,
            "outbox_before": preflight["outbox_before"],
        },
    }
    security_doc = {
        "schema_version": "z68-continuation-security-and-test-v1",
        "recorded_at": recorded_at,
        "secret_scan": exact_secret_scan(RUN),
        "tests": [
            {
                "command": "python3 -m unittest tests/test_z68_continuation_32k.py",
                "result": "13/13 pass",
                "exit_code": 0,
            },
            {
                "command": "python3 -m unittest tests/test_z68_continuation_report.py",
                "result": "1/1 pass",
                "exit_code": 0,
            },
            {
                "command": "python3 -m unittest discover -s tests",
                "result": "333/333 pass",
                "exit_code": 0,
            },
            {
                "command": "ruff check tools/z68_continuation_32k.py tools/z68_continuation_report.py tests/test_z68_continuation_32k.py tests/test_z68_continuation_report.py",
                "result": "All checks passed",
                "exit_code": 0,
            },
        ],
        "environment_observations": [
            {
                "check": "python3 -m pytest",
                "result": "No module named pytest",
                "impact": "不阻断；仓库标准入口是unittest，未安装依赖。",
            },
            {
                "check": "python3 -m ruff",
                "result": "No module named ruff",
                "impact": "不阻断；ruff独立命令可用并已通过。",
            },
        ],
    }
    artifacts = {
        "第3章金标v1.1语义成绩单.json": gold_doc,
        "现役122条五靶章语义diff.json": current_doc,
        "待判溢出清单.json": overflow_doc,
        "运输与成本回执.json": transport_doc,
        "供料单变量与保护回执.json": supply_doc,
        "安全与测试回执.json": security_doc,
    }
    for name, value in artifacts.items():
        write_json(report_dir / name, value)
    hashes = {name: sha256_file(report_dir / name) for name in artifacts}
    gold_summary = gold_doc["summary"]
    current_summary = current_doc["summary"]
    preserved_count = int(current_summary.get("preserved", 0))
    partial_count = int(current_summary.get("partially_preserved", 0))
    missing_count = int(current_summary.get("not_observed", 0))
    metric = mechanics["ten_metrics"]
    cost = transport_doc["five_chapter_condition_cost"]
    lines = [
        "# 第68道续令停点回包｜32k参数兼容修复与裸考成绩",
        "",
        f"✅ 结论分两层：运输兼容修复通过，候选质量没有通过旧事件不劣化闸。第5章在32k上限下正常 `stop`，交出18条事件，前次‘思考耗尽、正式正文为空’没有复现；但五靶章对现役34条记录只做到{preserved_count}条完整保留、{partial_count}条部分保留、{missing_count}条未观察，因此只进候选池，不升默认。",
        "",
        f"第3章对金标当章层严格命中为 {gold_summary['strict_hit']}/14（{gold_summary['strict_hit_rate']:.2%}），语义影子覆盖为 {gold_summary['semantic_shadow_recalled']}/14（{gold_summary['semantic_shadow_recall_rate']:.2%}）。对照第57道基线 2/14、12/14，分别增加 {gold_summary['strict_hit_delta']} 条和 {gold_summary['semantic_shadow_recalled_delta']} 条。这个成绩带‘连续正文＋冻结目录双视图’条件；第3章沿用硬停前16k正常样张，不能说成32k直接提升了第3章语义。",
        "",
        "## 1. 这次只改了什么",
        "",
        "- 第5／13／19章只把输出 token 上限从16,000改为32,000；模型、温度0.2、`n=1`、JSON模式、`reasoning_effort=medium` 和 Prompt 全部不动。三份逐行差异都只有 `$.max_tokens`。",
        "- 第3／4章复用硬停前唯一样张，不重跑。旧 `v1.0` 预演件原样留档；补运输账测试后另起 `v1.1`，可以独立移除，不影响旧现场。",
        "- 新增的程序兼容件只负责顺序、预算、硬停和终态账：第5章失败就不触发13／19章；全局最多5次运输尝试；终态清单自带逐次顺序和usage。默认 runner 行为没有改。",
        "",
        "## 2. 运输层实跑",
        "",
        "| 章 | 来源 | 网络尝试 | 结果 | 事件 | 总 token | 思考 token |",
        "|---:|---|---:|---|---:|---:|---:|",
        "| 3 | 复用16k唯一样张 | 0 新尝试 | `stop` | 21 | 22,271 | 12,116 |",
        "| 4 | 复用16k唯一样张 | 0 新尝试 | `stop` | 17 | 16,521 | 4,508 |",
        "| 5 | 32k新调用 | 1 | `stop` | 18 | 19,041 | 7,982 |",
        "| 13 | 32k新调用 | 2（先429后成功） | `stop` | 9 | 12,327 | 2,963 |",
        "| 19 | 32k新调用 | 1 | `stop` | 7 | 21,182 | 10,695 |",
        "",
        "- 新模型样本3份，运输尝试4次；第13章第一次HTTP 429没有usage，账上不假定它免费。",
        "- 新三章可核总消耗52,550 token，其中思考21,640。连同复用的第3／4章，五章条件成绩共91,342 token。",
        f"- 第57道五章基线是53,043 token；本臂增加 {cost['total_token_delta']:,}（{cost['total_token_delta_rate']:.2%}）。耗时从200,454 ms增至451,083 ms，增加 {cost['elapsed_ms_delta']:,} ms（{cost['elapsed_ms_delta_rate']:.2%}）。",
        "- 第5章前次16k失败响应用了25,559 token、正式正文0字；本次32k用19,041 token，正式正文3,686字并正常结束。这个结果只证明本次兼容修复有效，不代表以后不会再出现长思考。",
        "",
        "## 3. 十项机械成绩",
        "",
        f"- JSON合法章率：{metric['01_JSON合法章率']['numerator']}/{metric['01_JSON合法章率']['denominator']}；事件编号连续章率：{metric['02_event_id连续章率']['numerator']}/{metric['02_event_id连续章率']['denominator']}。",
        f"- 目录外锚：{metric['03_目录外锚数']}；无效锚率：{metric['04_无效锚率']:.2%}；锚排序与去重均为100%。",
        f"- 显式主语率：{metric['07_显式主语率']:.2%}；空泛谓词词面命中率：{metric['08_空泛谓词命中率']:.2%}。",
        "- 事件数：本臂72，基线39。数量变多不自动等于质量变好。",
        "",
        "## 4. 第3章金标14条逐条成绩",
        "",
        "| 金标 | 判定 | 候选事件 | 判词 |",
        "|---|---|---|---|",
    ]
    verdict_names = {"strict_hit": "严格命中", "semantic_shadow": "语义影子", "miss": "漏"}
    for row in gold_doc["rows"]:
        lines.append(
            f"| {row['gold_item_id']} | {verdict_names[row['verdict']]} | {', '.join(row['candidate_event_ids']) or '—'} | {row['semantic_review_note']} |"
        )
    lines.extend(
        [
            "",
            "回看层两条继续单列，不算单章漏项。严格分只看候选事件句是否写全，不能用证据锚里的丰富原文倒补事件句。",
            "",
            "## 5. 现役122条中的五靶章差距",
            "",
            f"五章对应34条现役记录：完整保留 {current_summary.get('preserved', 0)}，部分保留 {current_summary.get('partially_preserved', 0)}，未观察 {current_summary.get('not_observed', 0)}。旧事件不劣化闸不通过。",
            "",
            "| 章 | 现役记录 | 判定 | 候选事件 | 差距 |",
            "|---:|---|---|---|---|",
        ]
    )
    current_names = {
        "preserved": "完整保留",
        "partially_preserved": "部分保留",
        "not_observed": "未观察",
    }
    for row in current_doc["rows"]:
        lines.append(
            f"| {row['chapter']} | {row['record_id']} | {current_names[row['verdict']]} | {', '.join(row['candidate_event_ids']) or '—'} | {row['semantic_review_note']} |"
        )
    lines.extend(
        [
            "",
            "最明确的新漏是 `B-C0013-02`：没有抽到‘专家排除诅咒等条件后解除直接嫌疑’这一待触发安排。部分保留多发生在时间／条件／结果或规则概括被压缩，不能拿锚原文替候选事件补写。",
            "",
            "## 6. 待判溢出",
            "",
            f"第3章有 {overflow_doc['chapter3_gold_overflow']['count']} 条候选事件没有用于支撑14条金标，全部只记‘待判溢出’：",
            "",
        ]
    )
    for row in overflow_doc["chapter3_gold_overflow"]["events"]:
        lines.append(f"- `{row['event_id']}`：{row['event']}")
    lines.extend(
        [
            "",
            f"相对现役122条，五章另有 {overflow_doc['current122_unmapped_candidates']['count']} 条候选未映射现役记录；这只表示‘没有旧记录对应’，不自判应收、应删或正确。完整清单见 `待判溢出清单.json`。",
            "",
            "## 7. 第四节回执清单",
            "",
            "- 模型逻辑样本：新调用3份（第5／13／19章各1份），复用2份（第3／4章）；没有二次采样挑结果。网络尝试4次，其中第13章一次429后按同请求重试。",
            "- 空回包／截断／程序合同失败：0／0／0；五章程序合同5/5通过。",
            "- 机械有效率：JSON 5/5，编号连续5/5，目录外锚0，无效锚率0，排序和去重100%。",
            "- A／B／C／D分布：不适用；本件停在中性事件抽取，不进入分类和正式记录编译。",
            "- 新三章可核token：52,550；五章条件成绩含复用样张共91,342；第13章首次429无usage，不纳入。",
            "- 净收益三口径：机械层通过；第3章严格分增加4条、影子增加1条；旧事件不劣化失败，综合处置为候选质量不通过。",
            "- 三道扩大闸：不适用；只跑五靶章，没有扩20章。",
            f"- 旁路工具 SHA：`{sha256_file(ROOT / 'tools/z68_continuation_32k.py')}`。",
            f"- 测试文件 SHA：`{sha256_file(ROOT / 'tests/test_z68_continuation_32k.py')}`。",
            f"- 报告回归测试 SHA：`{sha256_file(ROOT / 'tests/test_z68_continuation_report.py')}`。",
            f"- 报告生成器 SHA：`{sha256_file(Path(__file__))}`。",
            f"- 默认运行器 SHA：`{preflight['protected']['tools/zbatch.py']}`，未改。",
            f"- 默认登记 SHA：`{preflight['protected']['config/defaults/zbatch_v1.2_full_chain.json']}`，未改。",
            f"- 分类合同 SHA：`{preflight['protected']['config/contracts/classify_rules_v1.2_semantic_identity_v1.json']}`，未改。",
            f"- 金标 v1.1 SHA：`{preflight['protected'][str(GOLD.relative_to(ROOT))]}`，未改。",
            f"- 现役122条 SHA：`{preflight['protected']['runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json']}`，未改。",
            f"- outbox：{preflight['outbox_before']['files']}个文件、{preflight['outbox_before']['bytes']:,}字节、指纹 `{preflight['outbox_before']['sha256']}`；验收为未变化。",
            f"- 密钥痕迹：运行目录精确命中 {security_doc['secret_scan']['exact_key_file_hits']}；实际密钥不落盘。",
            "- 测试：续跑工具13/13、报告回归1/1、全套333/333、`ruff check`通过；没有安装或修改依赖。",
            "- 处置：不固化、不升默认、不写outbox、不回写现役122条、金标、分类规则或旧运行目录。",
            "- G101：未领取、未执行。",
            "",
            "## 8. 工件与可退边界",
            "",
            f"- 正式运行目录：`{RUN.relative_to(ROOT).as_posix()}/`，原始请求、回包、事件、usage和运输账原样保留。",
            "- 被Luna拦下的旧零调用预演目录 `runs/Z68C_X01_修正版请求体32k兼容续跑_五靶章_v1.0_20260720/` 原样留档；没有删除或回写。",
            "- 本报告目录只放派生成绩与判词。移除它不会改变模型原始工件或主链；任何删除动作仍需CZ确认。",
            "",
            "## 9. 团队复核",
            "",
            "- Luna：修正前BLOCK，要求补硬停、顺序和总预算离线测试；修正后PASS，放行真实调用。",
            f"- Terra：{TEAM_REVIEW['status']}；{TEAM_REVIEW['note']}",
            "- Sol：当前没有真实冲突，不启用。",
            "",
            "## 10. 停点",
            "",
            f"第68道续令已完成运输兼容验证和五章成绩回填。32k修复本次运输失败，但候选仍有{missing_count}条现役记录完全未观察、{partial_count}条只部分保留，因此停在候选池等待CZ另拍；不据此升默认。",
            "",
        ]
    )
    for name, digest in hashes.items():
        lines.append(f"- `{name}` SHA：`{digest}`")
    lines.extend(["", "来源：Codex", ""])
    main_name = "第68道续令停点回包｜32k参数兼容修复与裸考成绩_20260720.md"
    markdown = "\n".join(lines)
    assert_main_semantic_counts(markdown, current_doc)
    (report_dir / main_name).write_text(markdown, encoding="utf-8")
    output_hashes = {**hashes, main_name: sha256_file(report_dir / main_name)}
    output = {
        "schema_version": "z68-continuation-report-manifest-v1",
        "status": "pass",
        "recorded_at": recorded_at,
        "source_run": RUN.relative_to(ROOT).as_posix(),
        "builder_sha256": sha256_file(Path(__file__)),
        "output_hashes": output_hashes,
        "team_review": TEAM_REVIEW,
    }
    write_json(report_dir / "report_manifest.json", output)
    return output


def check_documents(report_dir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp:
        expected_dir = Path(temp) / "report"
        expected = build_documents(expected_dir)
        expected_files = sorted(path.name for path in expected_dir.iterdir() if path.is_file())
        actual_files = sorted(path.name for path in report_dir.iterdir() if path.is_file())
        if expected_files != actual_files:
            raise RuntimeError(f"报告文件集合漂移：{actual_files} != {expected_files}")
        mismatched = [
            name
            for name in expected_files
            if (expected_dir / name).read_bytes() != (report_dir / name).read_bytes()
        ]
        if mismatched:
            raise RuntimeError(f"报告内容不能确定性复现：{mismatched}")
    return {"status": "pass", "checked_files": len(expected_files), "manifest": expected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    parser.add_argument("--report-dir", type=Path, default=REPORT)
    args = parser.parse_args()
    result = (
        build_documents(args.report_dir.resolve())
        if args.action == "build"
        else check_documents(args.report_dir.resolve())
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
