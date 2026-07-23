#!/usr/bin/env python3
"""第60道试点B：把人工语义判词机械落盘，并核算双臂差异、成本和运输账。"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHAPTERS = (3, 4, 5, 13, 19)
RUBRIC = ROOT / "config/experiments/Z60_大纲逻辑双臂语义复核尺_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def failure(trigger: str, claim: str, reason: str) -> dict[str, str]:
    return {"trigger": trigger, "claim": claim, "reason": reason}


def row(
    source: str = "full",
    actor: str = "complete",
    causal: str = "no_causal_claim",
    state: str = "supported",
    effect: str = "none",
    verdict: str = "pass",
    judgement: str = "逻辑句与状态变化均可由所挂中性事件支撑。",
    failures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "source_semantic_support": source,
        "actor_action_object_completeness": actor,
        "causal_claim_support": causal,
        "state_change_support": state,
        "entity_table_effect": effect,
        "verdict": verdict,
        "judgement": judgement,
        "failure_claims": failures or [],
    }


AUDIT: dict[tuple[str, int, str], dict[str, Any]] = {
    ("base", 3, "OL-C0003-01"): row(causal="supported", judgement="计划、审视记忆和得知面试形成一条受支撑的信息链。"),
    ("base", 3, "OL-C0003-02"): row(
        state="incorrect", verdict="new_failure",
        judgement="动作与发现有来源，但把发现既有愈合结果写成了本条发生的愈合过程。",
        failures=[failure("incorrect_state_change", "伤口从尚未愈合变为已愈合", "输入只说周明瑞发现伤口已经愈合，没有给出本条内的愈合前态。")],
    ),
    ("base", 3, "OL-C0003-03"): row(judgement="修好怀表并归还，可支撑怀表由损坏到修复。"),
    ("base", 3, "OL-C0003-04"): row(judgement="购物嘱咐、答应和离家上学均由三条输入直接支撑。"),
    ("base", 3, "OL-C0003-05"): row(judgement="注意力转向转运仪式与输入同义。"),
    ("base", 4, "OL-C0004-01"): row(judgement="取积蓄、抽两张纸币、放回其余及现金持有变化均有来源。"),
    ("base", 4, "OL-C0004-02"): row(
        causal="supported", state="incorrect", verdict="new_failure",
        judgement="左摆转轮、自杀空弹巢、合拢和安全后果均见同事件锚；只有“调整前位置不确定”没有来源。",
        failures=[failure("incorrect_state_change", "弹巢从位置不确定变为待击发位", "事件摘要和锚都没有声明调整前的位置不确定。")],
    ),
    ("base", 4, "OL-C0004-03"): row(causal="supported", judgement="买面包、净支出6便士和价格下降原因均可由两条输入合并得出。"),
    ("base", 4, "OL-C0004-04"): row(judgement="相遇、免费占卜、同意及女子外貌均见同事件摘要或锚。"),
    ("base", 5, "OL-C0005-01"): row(judgement="愚者牌被翻开和获知结果均由输入支撑。"),
    ("base", 5, "OL-C0005-02"): row(judgement="翻译、摆面包和逆时针诵念按输入顺序编排，未增加事实。"),
    ("base", 5, "OL-C0005-03"): row(
        state="incorrect", verdict="new_failure",
        judgement="异常感受与发现灰雾均有来源；“房间内正常状态”不是这两条来源事件给出的前态。",
        failures=[failure("incorrect_state_change", "周明瑞从房间内正常状态变为漂浮在灰雾中", "所挂EV05和EV06未给出房间内这一前态。")],
    ),
    ("base", 5, "OL-C0005-04"): row(causal="supported", judgement="触碰、星辰爆发和精神涣散为输入明示链。"),
    ("base", 5, "OL-C0005-05"): row(judgement="两处深红异象及两人随后出现在灰雾中，合并表述未越过三条输入。"),
    ("base", 13, "OL-C0013-01"): row(
        causal="unsupported", verdict="new_failure",
        judgement="入梦引导与确认失忆分别有来源，但“因此”把入梦误接成失忆原因。",
        failures=[failure("unsupported_causal_claim", "邓恩入梦引导后，克莱恩因此遗失记忆", "输入说克莱恩因这次事件遗失记忆，未说由邓恩入梦造成。")],
    ),
    ("base", 13, "OL-C0013-02"): row(
        state="incorrect", verdict="new_failure",
        judgement="要求、现场信息、死亡信息和同意均有来源；“最终还是选择”支持此前未明确同意，但不能支持已经不同意。",
        failures=[failure("incorrect_state_change", "克莱恩从犹豫／不同意变为同意", "同意事件锚可见决策过程，却没有记录克莱恩曾经明确不同意。")],
    ),
    ("base", 13, "OL-C0013-03"): row(
        source="partial", state="explicit_none_correct", verdict="new_failure",
        judgement="邪教事件与马车场景均见同事件锚；锚没有明确把克莱恩钉成这次讲述的接收者。",
        failures=[failure("unsupported_by_source_events", "邓恩向克莱恩讲述邪教事件", "所挂事件和锚给出讲述者、事件与马车场景，没有明确接收者是克莱恩。")],
    ),
    ("base", 13, "OL-C0013-04"): row(
        source="partial", state="incorrect", verdict="new_failure",
        judgement="马车到达住所有来源；锚只出现“我们下”的提议开头，不能证明两人已经下车并到达住所外。",
        failures=[failure("unsupported_by_source_events", "克莱恩和邓恩已经下车，位置变为住所外", "所挂锚最多给出下车提议，未给出完成动作和住所外落点。")],
    ),
    ("base", 13, "OL-C0013-05"): row(state="explicit_none_correct", judgement="专家的公开伪装和真实身份均由输入支撑。"),
    ("base", 19, "OL-C0019-01"): row(judgement="每日走访道路、寻找日记线索及获得任务均有来源。"),
    ("base", 19, "OL-C0019-02"): row(judgement="阅读武器库文献作为第二项工作与输入一致。"),
    ("base", 19, "OL-C0019-03"): row(judgement="邓恩介绍四级封印物，知识状态变化可由输入支撑。"),
    ("base", 19, "OL-C0019-04"): row(judgement="因斯携0-08潜逃和羽毛笔外形均由两条输入支撑。"),

    ("entity", 3, "OL-C0003-01"): row(causal="supported", effect="supported_detail_change", judgement="带表臂增加计划形成的状态描述，其余信息链由输入支撑。"),
    ("entity", 3, "OL-C0003-02"): row(
        state="incorrect", effect="supported_detail_change", verdict="new_failure",
        judgement="手枪位置变化有来源；伤口仍被误写成本条内发生的愈合过程。",
        failures=[failure("incorrect_state_change", "伤口从存在状态变为愈合状态", "输入只说发现伤口已经愈合。")],
    ),
    ("entity", 3, "OL-C0003-03"): row(effect="supported_detail_change", judgement="修复、归还及持有者变化均由输入支撑。"),
    ("entity", 3, "OL-C0003-04"): row(effect="supported_detail_change", judgement="购物任务和梅丽莎离家两项状态变化均由输入支撑。"),
    ("entity", 3, "OL-C0003-05"): row(effect="normalization_only", judgement="只改写了注意力转移措辞，没有新增事实。"),
    ("entity", 4, "OL-C0004-01"): row(
        source="partial", causal="unsupported", verdict="new_failure",
        judgement="取钱动作有来源；“为了买面包”的目的不在本条所挂事件里。",
        failures=[failure("unsupported_causal_claim", "取两张纸币是为了购买面包", "所挂事件只记录取钱；买面包是另一条未挂入的事件。")],
    ),
    ("entity", 4, "OL-C0004-02"): row(
        causal="supported", state="incorrect", verdict="new_failure",
        judgement="操作和安全目的有同事件锚；随机前态及把安全后果写成概率变化仍过界。",
        failures=[failure("incorrect_state_change", "弹巢从随机状态变为指定位置并降低走火概率", "锚未声明调整前随机，也只给出空弹巢承接走火的安全后果，未量化概率变化。")],
    ),
    ("entity", 4, "OL-C0004-03"): row(
        state="incorrect", verdict="new_failure",
        judgement="逻辑句正确记录支付9便士并找回3便士，状态句却把净减少写成9便士。",
        failures=[failure("contradiction_with_source_events", "现金减少9便士", "输入同时记录找回3便士，净减少应为6便士。")],
    ),
    ("entity", 4, "OL-C0004-04"): row(effect="supported_detail_change", judgement="删除了基线无来源外貌，保留相遇、提议和同意；互动关系有动作支撑。"),
    ("entity", 5, "OL-C0005-01"): row(
        state="incorrect", verdict="new_failure",
        judgement="逻辑句有来源，但把塔罗牌从未揭示到翻开为愚者误判成无独立状态变化。",
        failures=[failure("incorrect_state_change", "本条无独立状态转变", "输入明确记录代表现在的牌被翻开为愚者。")],
    ),
    ("entity", 5, "OL-C0005-02"): row(effect="supported_detail_change", judgement="翻译、仪式步骤和异常感受均由四条输入完整支撑。"),
    ("entity", 5, "OL-C0005-03"): row(
        state="incorrect", verdict="new_failure",
        judgement="发现漂浮在灰雾之上有来源；从房间转移到灰雾空间不在本条所挂事件中。",
        failures=[failure("incorrect_state_change", "周明瑞从房间转移到灰雾空间", "所挂事件只记录发现自己漂浮在灰雾之上。")],
    ),
    ("entity", 5, "OL-C0005-04"): row(causal="supported", effect="normalization_only", judgement="触碰后星辰爆发和精神涣散均由输入支撑。"),
    ("entity", 5, "OL-C0005-05"): row(effect="normalization_only", judgement="两人的异象、进入灰雾及会面均由输入支撑。"),
    ("entity", 13, "OL-C0013-01"): row(effect="supported_detail_change", judgement="入梦引导和确认失忆均有来源，认知由不确定到确认可由“确认”支撑。"),
    ("entity", 13, "OL-C0013-02"): row(effect="supported_detail_change", judgement="要求见专家与克莱恩同意两条事件被独立编排，状态描述未超出输入。"),
    ("entity", 13, "OL-C0013-03"): row(
        source="partial", state="incorrect", verdict="new_failure",
        judgement="现场事实和死亡事实有来源；由邓恩告知克莱恩以及克莱恩认知增加没有来源。",
        failures=[
            failure("unsupported_by_source_events", "邓恩把现场信息告知克莱恩", "两条输入没有给出告知动作、说话者或接收者。"),
            failure("incorrect_state_change", "克莱恩增加了对自身处境的认知", "所挂事件只记录客观信息，没有记录克莱恩获知。"),
        ],
    ),
    ("entity", 13, "OL-C0013-04"): row(
        source="partial", state="explicit_none_correct", verdict="new_failure",
        judgement="邪教事件与马车场景均见同事件锚；接收者克莱恩没有被该事件单独钉明。",
        failures=[failure("unsupported_by_source_events", "邓恩向克莱恩讲述邪教事件", "所挂事件和锚没有明确这次讲述的接收者是克莱恩。")],
    ),
    ("entity", 13, "OL-C0013-05"): row(
        state="incorrect", verdict="new_failure",
        judgement="马车到达韦尔奇住所有来源；路途前态和住所门口落点没有来源。",
        failures=[failure("incorrect_state_change", "地点从路途变为韦尔奇住所门口", "输入只说到达韦尔奇住所，没有给出前态或门口这一细化地点。")],
    ),
    ("entity", 13, "OL-C0013-06"): row(
        state="incorrect", verdict="new_failure",
        judgement="专家公开伪装和真实身份有来源；所挂事件没有明确接收者，不能直接写成克莱恩完成了认知变化。",
        failures=[failure("incorrect_state_change", "克莱恩对专家身份的认识发生变化", "所挂事件只记录邓恩介绍专家，没有钉明接收者是克莱恩。")],
    ),
    ("entity", 19, "OL-C0019-01"): row(
        source="partial", verdict="new_failure",
        judgement="任务内容有来源；把被动安排者具体写成邓恩没有来源。",
        failures=[failure("unsupported_by_source_events", "邓恩安排克莱恩外出寻找日记", "所挂事件使用被动表述，没有给出安排者。")],
    ),
    ("entity", 19, "OL-C0019-02"): row(
        source="partial", verdict="new_failure",
        judgement="第二项工作内容有来源；把安排者具体写成邓恩没有来源。",
        failures=[failure("unsupported_by_source_events", "邓恩安排克莱恩阅读武器库文献", "所挂事件没有给出安排者。")],
    ),
    ("entity", 19, "OL-C0019-03"): row(effect="normalization_only", judgement="邓恩介绍封印物四级分类及知识变化均有来源。"),
    ("entity", 19, "OL-C0019-04"): row(effect="supported_detail_change", judgement="潜逃、羽毛笔外形和不用墨水书写均见两条来源事件及其锚。"),
}


DIFF_GROUPS = [
    (3, ["OL-C0003-01"], ["OL-C0003-01"], "more_specific_supported", "带表臂增加计划形成状态，来源可支撑。"),
    (3, ["OL-C0003-02"], ["OL-C0003-02"], "more_specific_supported", "带表臂增加手枪持有位置变化；两臂仍共享伤口状态误写。"),
    (3, ["OL-C0003-03"], ["OL-C0003-03"], "more_specific_supported", "带表臂增加怀表持有者变化。"),
    (3, ["OL-C0003-04"], ["OL-C0003-04"], "more_specific_supported", "带表臂增加购物任务状态。"),
    (3, ["OL-C0003-05"], ["OL-C0003-05"], "normalization_only", "只改写措辞。"),
    (4, ["OL-C0004-01"], ["OL-C0004-01"], "unsupported_change", "带表臂增加未挂源的买面包目的。"),
    (4, ["OL-C0004-02"], ["OL-C0004-02"], "unsupported_change", "两臂的操作和安全说明均有锚；带表臂仍把未给出的前态写成随机，并把安全后果写成概率变化。"),
    (4, ["OL-C0004-03"], ["OL-C0004-03"], "unsupported_change", "带表臂把净支出6便士误写成9便士。"),
    (4, ["OL-C0004-04"], ["OL-C0004-04"], "less_specific", "带表臂省略了同事件锚里可见的女子外貌。"),
    (5, ["OL-C0005-01"], ["OL-C0005-01"], "less_specific", "带表臂丢掉牌面翻开带来的状态变化。"),
    (5, ["OL-C0005-02", "OL-C0005-03"], ["OL-C0005-02", "OL-C0005-03"], "different_grouping", "异常感受在两臂归入不同逻辑组，五条来源事件总覆盖不变。"),
    (5, ["OL-C0005-04"], ["OL-C0005-04"], "normalization_only", "只改写触碰前态措辞。"),
    (5, ["OL-C0005-05"], ["OL-C0005-05"], "normalization_only", "只改写两人进入灰雾的措辞。"),
    (13, ["OL-C0013-01"], ["OL-C0013-01"], "more_specific_supported", "带表臂把基线错误因果改为邓恩确认记忆状况。"),
    (13, ["OL-C0013-02"], ["OL-C0013-02", "OL-C0013-03"], "different_grouping", "带表臂将见专家的请求／同意与现场信息拆成两条。"),
    (13, ["OL-C0013-03"], ["OL-C0013-04"], "exact_same", "逻辑句完全一致；马车地点有锚，两臂共同未钉明接收者克莱恩。"),
    (13, ["OL-C0013-04"], ["OL-C0013-05"], "unsupported_change", "带表臂删掉下车动作，却增加未给出的住所门口。"),
    (13, ["OL-C0013-05"], ["OL-C0013-06"], "unsupported_change", "带表臂把没有钉明接收者的介绍写成克莱恩已经完成认知变化。"),
    (19, ["OL-C0019-01"], ["OL-C0019-01"], "unsupported_change", "带表臂把未给出的任务安排者写成邓恩。"),
    (19, ["OL-C0019-02"], ["OL-C0019-02"], "unsupported_change", "带表臂把未给出的任务安排者写成邓恩。"),
    (19, ["OL-C0019-03"], ["OL-C0019-03"], "normalization_only", "只改写知识获得措辞。"),
    (19, ["OL-C0019-04"], ["OL-C0019-04"], "more_specific_supported", "带表臂增加同事件锚已经给出的0-08不用墨水也能书写。"),
]


def load_items(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    rows: list[dict[str, Any]] = []
    source_ids: dict[str, set[str]] = {}
    for chapter in TARGET_CHAPTERS:
        source = read_json(run_dir / "inputs/neutral_events" / f"ch{chapter:04d}.json")["events"]
        source_ids[str(chapter)] = {str(event["event_id"]) for event in source}
        for arm in ("base", "entity"):
            items = read_json(run_dir / "01_outline" / arm / f"ch{chapter:04d}.json")["outline_items"]
            for item in items:
                key = (arm, chapter, str(item["item_id"]))
                if key not in AUDIT:
                    raise RuntimeError(f"缺人工判词：{key}")
                rows.append({"arm": arm, "chapter": chapter, **item, **AUDIT[key]})
    observed = {(row["arm"], row["chapter"], row["item_id"]) for row in rows}
    if observed != set(AUDIT):
        raise RuntimeError(f"人工判词与实物不等集：少={set(AUDIT)-observed}，多={observed-set(AUDIT)}")
    return rows, source_ids


def validate_reviews(rows: list[dict[str, Any]], rubric: dict[str, Any]) -> None:
    for item in rows:
        for field in rubric["row_review_fields"]:
            if field not in item:
                raise RuntimeError(f"判词字段缺失：{item['arm']}/{item['item_id']}/{field}")
        for field, allowed in rubric["allowed_values"].items():
            if item[field] not in allowed:
                raise RuntimeError(f"判词枚举非法：{item['arm']}/{item['item_id']}/{field}={item[field]}")
        if item["verdict"] == "new_failure" and not item["failure_claims"]:
            raise RuntimeError(f"新失败面没有证据判词：{item['arm']}/{item['item_id']}")
        if item["verdict"] != "new_failure" and item["failure_claims"]:
            raise RuntimeError(f"非失败行夹带失败判词：{item['arm']}/{item['item_id']}")


def aggregate(rows: list[dict[str, Any]], source_ids: dict[str, set[str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arm in ("base", "entity"):
        arm_rows = [item for item in rows if item["arm"] == arm]
        used = {event_id for item in arm_rows for event_id in item["source_event_ids"]}
        expected = set().union(*(source_ids[str(chapter)] for chapter in TARGET_CHAPTERS))
        verdicts = Counter(item["verdict"] for item in arm_rows)
        result[arm] = {
            "condition": "不带实体表" if arm == "base" else "含全程演员表输入",
            "item_count": len(arm_rows),
            "source_event_id_coverage": {
                "used": len(used), "expected": len(expected), "rate": len(used) / len(expected),
                "missing": sorted(expected - used),
            },
            "semantically_supported_item_rate": {
                "full": sum(item["source_semantic_support"] == "full" for item in arm_rows),
                "total": len(arm_rows),
            },
            "actor_action_object_complete_rate": {
                "complete": sum(item["actor_action_object_completeness"] == "complete" for item in arm_rows),
                "total": len(arm_rows),
            },
            "supported_or_explicit_none_state_rate": {
                "supported": sum(item["state_change_support"] in {"supported", "explicit_none_correct"} for item in arm_rows),
                "total": len(arm_rows),
            },
            "unsupported_detail_count": sum(len(item["failure_claims"]) for item in arm_rows),
            "verdict_counts": dict(sorted(verdicts.items())),
        }
    return result


def build_semantic_diff(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(item["arm"], item["chapter"], item["item_id"]): item for item in rows}
    covered: dict[str, set[tuple[int, str]]] = defaultdict(set)
    groups: list[dict[str, Any]] = []
    counts = Counter()
    for index, (chapter, base_ids, entity_ids, category, judgement) in enumerate(DIFF_GROUPS, 1):
        base = [by_key[("base", chapter, item_id)] for item_id in base_ids]
        entity = [by_key[("entity", chapter, item_id)] for item_id in entity_ids]
        for item_id in base_ids:
            covered["base"].add((chapter, item_id))
        for item_id in entity_ids:
            covered["entity"].add((chapter, item_id))
        counts[category] += 1
        groups.append({
            "group_id": f"Z60-DIFF-{index:02d}", "chapter": chapter, "category": category,
            "base_item_ids": base_ids, "entity_item_ids": entity_ids,
            "base_source_event_ids": sorted({event for item in base for event in item["source_event_ids"]}),
            "entity_source_event_ids": sorted({event for item in entity for event in item["source_event_ids"]}),
            "judgement": judgement,
        })
    for arm in ("base", "entity"):
        expected = {(item["chapter"], item["item_id"]) for item in rows if item["arm"] == arm}
        if covered[arm] != expected:
            raise RuntimeError(f"语义diff没有逐条覆盖{arm}：少={expected-covered[arm]}，多={covered[arm]-expected}")
    return {
        "schema_version": "z60-b-semantic-dual-arm-diff-v1",
        "status": "hard_stop_candidate_samples_no_direct_winner",
        "comparison_boundary": "同池同章同模型同参数，各n=1；带表臂标为含全程演员表输入。样张并列，不直接判长期胜负。",
        "semantic_review_completed": True,
        "shadow_score_used": False,
        "group_count": len(groups),
        "category_counts": dict(sorted(counts.items())),
        "groups": groups,
    }


def build_cost(run_dir: Path) -> dict[str, Any]:
    rows = read_jsonl(run_dir / "usage.jsonl")
    result: dict[str, Any] = {}
    for arm in ("base", "entity"):
        selected = [item for item in rows if str(item["case_id"]).startswith(f"{arm}_")]
        chapter_rows: list[dict[str, Any]] = []
        totals = Counter()
        for item in selected:
            usage = item["usage"]
            reasoning = int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
            chapter = int(str(item["case_id"]).rsplit("ch", 1)[1])
            row_data = {
                "chapter": chapter, "case_id": item["case_id"],
                "prompt_tokens": int(usage["prompt_tokens"]),
                "completion_tokens": int(usage["completion_tokens"]),
                "reasoning_tokens_in_completion": reasoning,
                "total_tokens": int(usage["total_tokens"]),
                "elapsed_ms": int(item["elapsed_ms"]),
                "http_status": int(item["http_status"]), "finish_reason": item["finish_reason"],
            }
            chapter_rows.append(row_data)
            for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens_in_completion", "total_tokens", "elapsed_ms"):
                totals[key] += row_data[key]
        result[arm] = {
            "condition": "不带实体表" if arm == "base" else "含全程演员表输入",
            "successful_model_calls": len(selected), "totals": dict(totals), "chapters": chapter_rows,
        }
    combined = Counter()
    for arm in result.values():
        for key, value in arm["totals"].items():
            combined[key] += value
    return {
        "schema_version": "z60-b-arm-cost-v1", "source_of_truth": "usage.jsonl",
        "price_not_calculated": True, "arms": result, "combined": dict(combined),
    }


def build_transport(run_dir: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    attempts = read_jsonl(run_dir / "call_attempts.jsonl")
    usage = read_jsonl(run_dir / "usage.jsonl")
    errors = sorted((run_dir / "errors").glob("*.txt")) if (run_dir / "errors").is_dir() else []
    return {
        "schema_version": "z60-b-transport-observation-v1",
        "logical_samples": 10, "successful_model_calls": len(usage), "network_attempts": len(attempts),
        "retry_count": len(attempts) - len(usage), "retry_budget": metrics["transport_budget"],
        "http_status_counts": dict(Counter(str(item["http_status"]) for item in usage)),
        "finish_reason_counts": dict(Counter(str(item["finish_reason"]) for item in usage)),
        "errors": [
            {"path": path.relative_to(run_dir).as_posix(), "sha256": sha256_file(path), "first_line": path.read_text(encoding="utf-8").splitlines()[0]}
            for path in errors
        ],
        "observation": "base_ch0003首次SSL EOF且无响应字节，按运输合同重试一次成功；其余九个逻辑样张均一次成功。没有新增逻辑样张。",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    metrics = read_json(run_dir / "01_outline/metrics.json")
    if metrics.get("status") != "completed_candidate_only" or metrics.get("usage", {}).get("successful_model_calls") != 10:
        raise RuntimeError("正式双臂样张未完整完成，拒绝语义落账")
    rubric = read_json(RUBRIC)
    preflight = read_json(run_dir / "preflight.json")
    pinned_rubric = run_dir / "provenance/pinned/Z60_大纲逻辑双臂语义复核尺_v1.json"
    if sha256_file(RUBRIC) != preflight["semantic_review_rubric"]["sha256"] or sha256_file(pinned_rubric) != sha256_file(RUBRIC):
        raise RuntimeError("语义复核尺漂移")
    rows, source_ids = load_items(run_dir)
    validate_reviews(rows, rubric)
    summary = aggregate(rows, source_ids)
    review = {
        "schema_version": "z60-b-semantic-review-v1",
        "status": "hard_stop_new_failure_no_repair_no_rerun",
        "rubric_sha256": sha256_file(RUBRIC),
        "review_scope": {"arms": ["base", "entity"], "chapters": list(TARGET_CHAPTERS), "item_count": len(rows)},
        "shadow_score_used": False,
        "summary": summary,
        "rows": rows,
    }
    semantic_diff = build_semantic_diff(rows)
    cost = build_cost(run_dir)
    transport = build_transport(run_dir, metrics)
    failures = [
        {"arm": item["arm"], "chapter": item["chapter"], "item_id": item["item_id"], "claims": item["failure_claims"]}
        for item in rows if item["verdict"] == "new_failure"
    ]
    protected_current: dict[str, str] = {}
    for relative, expected in preflight["protected"].items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise RuntimeError(f"保护件漂移：{relative}")
        protected_current[relative] = actual
    if metrics["outbox_after"] != preflight["outbox_before"]:
        raise RuntimeError("outbox前后指纹不一致")
    hard_stop = {
        "schema_version": "z60-b-semantic-hard-stop-v1",
        "status": "hard_stop_no_repair_no_rerun",
        "reason": "47条输出逐项语义复核发现未由source_event_ids支撑的细节、错误因果或错误状态变化。",
        "failed_item_count": len(failures),
        "failure_claim_count": sum(len(item["claims"]) for item in failures),
        "failures": failures,
        "scope_effect": {
            "trial_b": "失败候选，保留全部原始样张与审计件",
            "trial_a": "既有失败候选原样留档，未混入本道供料或判分",
            "repair": "未做", "rerun": "禁止", "default_or_gold_or_current_records": "未改", "outbox": "未改",
        },
        "protected": protected_current,
        "outbox_fingerprint": metrics["outbox_after"],
    }
    outputs = {
        "双臂语义复核.json": review,
        "双臂信息变化语义账.json": semantic_diff,
        "分臂成本账.json": cost,
        "运输层实跑观察.json": transport,
        "语义硬停单.json": hard_stop,
    }
    for name, document in outputs.items():
        write_json(run_dir / "analysis" / name, document)
    receipt = {
        "schema_version": "z60-b-semantic-audit-receipt-v1",
        "status": "hard_stop_artifacts_written",
        "script_sha256": sha256_file(Path(__file__)),
        "rubric_sha256": sha256_file(RUBRIC),
        "outputs": {f"analysis/{name}": sha256_file(run_dir / "analysis" / name) for name in outputs},
    }
    write_json(run_dir / "analysis/语义审计机械回执.json", receipt)
    print(json.dumps({"summary": summary, "diff": semantic_diff["category_counts"], "cost": cost["combined"], "hard_stop": {"failed_items": len(failures), "failure_claims": hard_stop["failure_claim_count"]}, "receipt": receipt}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
