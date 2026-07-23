#!/usr/bin/env python3
"""第64道件A：把本地逐条判词写入机械工作底稿（0 模型 API）。"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/Z64_三窗回包语义抽查与差距表_20260720"
WORKBOOK = REPORT / "语义复核工作底稿.json"
CONFIRMED_PASS_IDS_SHA256 = "ea45374282bdbc9c29719d9a5c8c3f9c27714ed3b9618603899f4b46d3bdd677"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def event_key(population: str, source_id: str) -> str:
    return f"{population}:{source_id}"


# 181 条本地逐条确认通过项由身份集 SHA 冻结；这里单列 52 条偏离“两个问题均通过”的判词。
OVERRIDES: dict[str, dict[str, str]] = {
    # 50章窗2：复合事件的短引只支撑部分字段。
    event_key("50章窗2事件记录", "A000101"): {
        "citation": "partial",
        "note": "短引只证明周明瑞怀疑穿越，未单独证明地球职场身份及克莱恩身体身份；章内事实成立，但该锚不足以独立托住整条delta。",
    },
    event_key("50章窗2事件记录", "A000103"): {
        "citation": "partial",
        "note": "短引直接托住太阳穴伤口，只间接涉及左轮与血手印；复合delta需要同章其他原句共同支撑。",
    },
    event_key("50章窗2事件记录", "A000503"): {
        "citation": "partial",
        "note": "短引只显示奥黛丽、阿尔杰同时说话，没有直接呈现触星、深红投影与拉入灰雾的因果。",
    },
    event_key("50章窗2事件记录", "A000803"): {
        "citation": "partial",
        "note": "“巨舰和大炮时代”支撑时代宣告，但命名、试射成功和海军认知变化还需前文共同支撑。",
    },
    event_key("50章窗2事件记录", "A001201"): {
        "citation": "partial",
        "note": "短引支撑韦尔奇失枪及邓恩怀疑枪在克莱恩家，尚未直接确认这就是原主开枪所用左轮。",
    },
    event_key("50章窗2事件记录", "A001203"): {
        "citation": "partial",
        "note": "“做了个噩梦”不能独立证明邓恩进入并引导梦境；该机制需与前后对话合读。",
    },
    event_key("50章窗2事件记录", "A002003"): {
        "citation": "partial",
        "structure": "partial",
        "note": "简体字短引支撑克莱恩识别文字；“无人能读”把当时值夜者不识读扩成绝对范围，语义过满。",
    },
    event_key("50章窗2事件记录", "A002601"): {
        "citation": "partial",
        "note": "短引直接支撑按原路正常行动，却没托住邓恩对跟踪者来源的判断。",
    },
    event_key("50章窗2事件记录", "A002702"): {
        "citation": "partial",
        "note": "庆祝短引支撑共同用餐目的；牛肉、鱼、调料和亲自烹饪需同章其他原句。",
    },
    event_key("50章窗2事件记录", "A002901"): {
        "citation": "partial",
        "note": "询问“占卜家有什么能力”只提出问题，没有独立列出星象、卡牌、灵摆和灵视能力。",
    },
    event_key("50章窗2事件记录", "A003503"): {
        "citation": "partial",
        "note": "短引支撑克莱恩形成扮演占卜家的推测；近因“阿尔杰讲观众原则”在前段对话，不在本锚内。",
    },
    event_key("50章窗2事件记录", "B001201"): {
        "citation": "partial",
        "note": "“她提前到了”只支撑时间变化；专家所在地点与立即前往复核需后续动作补证。",
    },
    event_key("50章窗2事件记录", "B002501"): {
        "citation": "partial",
        "note": "暗门路线直接成立，但“暂时摆脱注视”不在短引中。",
    },
    event_key("50章窗2事件记录", "B002801"): {
        "citation": "partial",
        "note": "询问可选序列只证明进入选择阶段，未直接证明已完成权衡并应提交最终选择。",
    },
    event_key("50章窗2事件记录", "B003101"): {
        "citation": "partial",
        "note": "魔药已配好由短引直接成立，喝下及融合过程发生在后续正文。",
    },
    event_key("50章窗2事件记录", "B004001"): {
        "citation": "partial",
        "note": "短引只提出可申请经费，未直接证明申请已经提交、批准且金额为5镑。",
    },
    event_key("50章窗2事件记录", "B004201"): {
        "citation": "partial",
        "note": "期待占卜发挥作用不等于已经取得衣物媒介、锁定地点并完成解救。",
    },
    event_key("50章窗2事件记录", "B004501"): {
        "citation": "partial",
        "note": "短引确认笔记痕迹在对面房间，未直接托住报告与组织重返现场两步。",
    },
    event_key("50章窗2事件记录", "B004601"): {
        "citation": "partial",
        "note": "短引支撑画像核实与通缉，不直接支撑值夜者、地下渠道和密修会之间的竞速。",
    },
    event_key("50章窗2事件记录", "C002601"): {
        "citation": "fail",
        "note": "所引“任何……不要吓跑、不要违法”只是行动约束，不能独立支撑‘跟踪者何时怎样被控制’这一读者承诺。",
    },
    event_key("50章窗2事件记录", "C005001"): {
        "citation": "fail",
        "note": "“这样也行？”只是反应句，本身没有债务、仪式、成功或代价信息；需引用老尼尔前后原话。",
    },
    event_key("50章窗2事件记录", "D000101"): {
        "citation": "partial",
        "note": "短引只确认文字属于赫密斯文；识读能力、词汇范围与例外是相邻记忆信息。",
    },
    event_key("50章窗2事件记录", "D000603"): {
        "citation": "partial",
        "note": "短引只给出“观众”配方名称，能力效果和保持旁观位置需后续句补证。",
    },
    event_key("50章窗2事件记录", "D001401"): {
        "citation": "partial",
        "note": "“凡存在必留痕迹”托住残痕逻辑，但安曼达、灵之眼、诱导方式和敌对例外不在本锚。",
    },
    event_key("50章窗2事件记录", "D001801"): {
        "citation": "partial",
        "note": "短引只引出三种悲剧结果，死亡、怪物化与人格变化的具体枚举在后文。",
    },
    event_key("50章窗2事件记录", "D002101"): {
        "citation": "partial",
        "note": "短引只到“不是掌握，是消化”，扮演、具体意象和钥匙在紧接着的原文中。",
    },
    event_key("50章窗2事件记录", "D002202"): {
        "citation": "partial",
        "note": "短引支撑序列9占多数，不能单独托住廷根总人数、漏计群体与高序列稀少等完整边界。",
    },
    event_key("50章窗2事件记录", "D002803"): {
        "citation": "partial",
        "structure": "partial",
        "note": "原文明确限定为摩斯苦修会‘那时候尚未堕落’的道德与格言；记录虽留了执行边界，condition仍容易被读成当代成员普遍遵循。",
    },
    event_key("50章窗2事件记录", "D003201"): {
        "citation": "partial",
        "note": "想象不存在物品的步骤有锚；进入冥想与收束灵性的结果需后续表现补证。",
    },
    event_key("50章窗2事件记录", "D004002"): {
        "citation": "partial",
        "note": "短引支撑象征解读的重要性，未独立说明启示来自灵界、星空或未知领域。",
    },
    event_key("50章窗2事件记录", "D004202"): {
        "citation": "fail",
        "structure": "fail",
        "note": "短引只是邓恩去教堂、伦纳德代守门的一次排班快照；无法推出六名成员按能力和排班分工的稳定世界规则，属于状态事实误放D类。",
    },
    event_key("50章窗2事件记录", "D004502"): {
        "citation": "fail",
        "note": "“没有恶灵”只给检查结论，不支撑收尸人无检查识别腐尸、看见多类灵体的能力范围；结论在同章可另证，但本锚不合格。",
    },
    event_key("50章窗2事件记录", "D004601"): {
        "citation": "partial",
        "note": "画像来自残留信息由短引成立；隔绝仪式、材料咒文和失败边界需要前序过程补证。",
    },
    event_key("50章窗2事件记录", "D004904"): {
        "citation": "partial",
        "structure": "partial",
        "note": "向正统神灵祈求较安全、普通人难获启示有直接支撑；对应象征时间与非凡者清晰画面并非本锚内容。",
    },

    # 20章窗2：少量复合锚与类型边界。
    event_key("20章窗2事件记录", "A000103"): {
        "citation": "partial",
        "note": "死亡宣言短引支撑可读结果，未单独呈现残留赫密斯文知识被记忆融合唤起的近因。",
    },
    event_key("20章窗2事件记录", "A000502"): {
        "structure": "partial",
        "note": "驯兽师假扮身份被揭穿是当场转折，事实无误；把它列成跨章因果A并预写‘愚者牌可信度线’，后续消费强度偏弱。",
    },
    event_key("20章窗2事件记录", "A001004"): {
        "citation": "partial",
        "note": "短引支撑承认记忆缺失，未单独托住警官发现死亡宣言和以部分真话求保护的近因。",
    },
    event_key("20章窗2事件记录", "A002005"): {
        "citation": "partial",
        "note": "见面问候成立，但从财务手续到武器库区域的路径与任务安排不在短引中。",
    },
    event_key("20章窗2事件记录", "B000701"): {
        "citation": "partial",
        "note": "短引直接给出每周一三点与独处条件，召集动作需结合此前灰雾机制理解。",
    },
    event_key("20章窗2事件记录", "B001002"): {
        "structure": "partial",
        "note": "离城前通知的触发器语义成立；但status为‘废’而type_state仍为‘待’，状态组合没有解释过期时点。",
    },
    event_key("20章窗2事件记录", "C000102"): {
        "citation": "partial",
        "note": "短引只提出枪支来源与家境不相称，未独立覆盖死亡宣言和伤口机制两部分承诺。",
    },
    event_key("20章窗2事件记录", "C001802"): {
        "citation": "partial",
        "structure": "partial",
        "note": "固定途径规则有直接支撑；‘克莱恩将选哪条并如何避险’是读者可推想的问题，但本锚没有建立明确等待承诺。",
    },
    event_key("20章窗2事件记录", "C002002"): {
        "citation": "partial",
        "note": "短引直接支撑改善住房需求，未独立支撑购买正装、手杖以及完整兑现条件。",
    },
    event_key("20章窗2事件记录", "D000502"): {
        "citation": "partial",
        "note": "触星爆发深红光有锚；现实人物被笼罩并投影至灰雾需同章后续段落。",
    },
    event_key("20章窗2事件记录", "D001502"): {
        "structure": "partial",
        "note": "这是教会审判机关内部警语，文本没有给出可检验机制；作为人物信条成立，作为客观世界规则需降低确信度。",
    },

    # 1,761母集：抽中的两条省略了关键叙述层级。
    "50章窗3逐章证据:E-10-17": {
        "citation": "partial",
        "note": "原文是警官依据现场痕迹作出的‘自杀’说明；证据条去掉说话人后写成客观结论，动作与血迹吻合，但确信度层级被抹平。",
    },
    "50章窗3逐章证据:E-12-07": {
        "citation": "partial",
        "note": "‘在床板背面’发生于邓恩诱导的梦境回答；证据条写‘主动告知’会弱化梦境审查这一条件。",
    },

    # 两步法新增包：核心事实成立，少数总结词比证据更满。
    "two_step:人物关系:030": {
        "citation": "partial",
        "structure": "partial",
        "note": "获救后进入值夜者系统并担任会计均有证据；‘核心会计和行政人员’中的‘核心’及行政职责没有独立证据。",
    },
    "two_step:逻辑句:063": {
        "citation": "partial",
        "note": "失控比例、原因、三年规则和多人提醒均有证据；‘组织文化始终以克制为核心’属于这些事实上的分析归纳，不是原文直接结论。",
    },

    # 一步直出新增包：跨章同人、隐瞒关系与第2章确信度三处边界。
    "one_step:人物档案:012": {
        "citation": "partial",
        "structure": "partial",
        "note": "第8章黄发闪电袍男子与第41章赛恩斯特征高度同构，可合理回看为同一人；正文第8章未点名，报告却标成‘明确’，应标回看推定。",
    },
    "one_step:人物关系:011": {
        "citation": "partial",
        "note": "安妮负责衣着照料、奥黛丽会用理由避开安排均有正文；‘日常信任’与持续隐瞒神秘学实验是关系归纳，并非直接陈述。",
    },
    "one_step:每章大纲:002": {
        "citation": "partial",
        "structure": "partial",
        "note": "伤口、弹头、空弹壳和转运仪式均有支撑；正文说‘暂时算自杀’，大纲写成‘判断原主曾自杀’，略抬高了自杀结论的确信度。",
    },
}


def confirmed_pass_verdict(row: dict[str, Any]) -> dict[str, str]:
    population = row["population"]
    if population in {"50章窗2事件记录", "20章窗2事件记录"}:
        return {
            "citation": "pass",
            "structure": "pass",
            "note": "短引在所记章节可原样定位，并能直接托住核心主张；按A/B/C/D合同复核，类型、变化或触发/承诺/规则边界成立。",
        }
    if population == "50章窗3逐章证据":
        return {
            "citation": "pass",
            "structure": "not_applicable",
            "note": "逐章事实与同章正文段落逐句对齐，没有把说话人判断、推测或相邻撞词扩成额外事实。",
        }
    if population == "两步法新增包":
        return {
            "citation": "pass",
            "structure": "pass",
            "note": "所列E编号均回指1,761母集并复到正文；主张没有越过证据确信度，七类位置及因果/状态边界成立。",
        }
    if population == "一步直出新增包":
        return {
            "citation": "pass",
            "structure": "pass",
            "note": "章号、短引或同章上下文能托住核心主张；七类位置及因果/状态边界成立。",
        }
    raise ValueError(f"未知母集：{population}")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def locator_trace(row: dict[str, Any]) -> dict[str, Any]:
    evidence_ids = list(row.get("evidence_ids") or [])
    direct_locations = list(row.get("citation_exact_locations") or [])
    embedded_exact = [
        location
        for quote in row.get("embedded_quotes") or []
        for location in quote.get("exact_locations") or []
    ]
    if evidence_ids:
        locator_class = "evidence_id_chain"
    elif direct_locations or embedded_exact:
        locator_class = "frozen_text_exact_quote"
    else:
        locator_class = "chapter_reference_manual_read"
    return {
        "locator_class": locator_class,
        "evidence_id_count": len(evidence_ids),
        "exact_location_count": len(direct_locations) + len(embedded_exact),
    }


def apply_verdicts() -> dict[str, Any]:
    workbook = json.loads(WORKBOOK.read_text(encoding="utf-8"))
    confirmed_pass_ids = sorted(
        row["review_id"] for row in workbook["rows"] if row["review_id"] not in OVERRIDES
    )
    confirmed_pass_id_sha256 = hashlib.sha256("\n".join(confirmed_pass_ids).encode("utf-8")).hexdigest()
    if confirmed_pass_id_sha256 != CONFIRMED_PASS_IDS_SHA256:
        raise ValueError(
            "全通过签认身份集发生变化："
            f"expected={CONFIRMED_PASS_IDS_SHA256} actual={confirmed_pass_id_sha256}"
        )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_row in workbook["rows"]:
        row = dict(source_row)
        review_id = row["review_id"]
        if review_id in seen:
            raise ValueError(f"重复review_id：{review_id}")
        seen.add(review_id)
        verdict = confirmed_pass_verdict(row)
        verdict.update(OVERRIDES.get(review_id, {}))
        row["questions"] = {
            "citation_semantic_support": verdict["citation"],
            "type_delta_cause_correct": verdict["structure"],
            "verdict_note": verdict["note"],
            "review_method": "local_reading_against_X01_frozen_chapters_1_50",
        }
        reviewed_content = {
            key: row.get(key)
            for key in (
                "review_id",
                "population",
                "chapter",
                "record_type",
                "claim",
                "citation",
                "citation_exact_locations",
                "embedded_quotes",
                "evidence_ids",
                "evidence_refs",
                "context_candidates",
            )
            if key in row
        }
        row["review_trace"] = {
            "adjudication_route": (
                "explicit_exception" if review_id in OVERRIDES else "explicit_confirmed_pass"
            ),
            "manual_confirmation": True,
            "reviewed_content_sha256": canonical_sha256(reviewed_content),
            **locator_trace(row),
        }
        rows.append(row)
    unknown_overrides = sorted(set(OVERRIDES) - seen)
    if unknown_overrides:
        raise ValueError(f"判词指向不存在的样本：{unknown_overrides}")

    summary: dict[str, Any] = {}
    for population in sorted({row["population"] for row in rows}):
        selected = [row for row in rows if row["population"] == population]
        citation = Counter(row["questions"]["citation_semantic_support"] for row in selected)
        structure = Counter(row["questions"]["type_delta_cause_correct"] for row in selected)
        summary[population] = {
            "sample_units": len(selected),
            "citation_semantic_support": dict(sorted(citation.items())),
            "type_delta_cause_correct": dict(sorted(structure.items())),
            "citation_full_pass_rate": round(citation["pass"] / len(selected), 6),
            "structure_full_pass_rate": (
                None
                if structure["not_applicable"] == len(selected)
                else round(structure["pass"] / len(selected), 6)
            ),
        }
    route_counts = Counter(row["review_trace"]["adjudication_route"] for row in rows)
    locator_counts = Counter(row["review_trace"]["locator_class"] for row in rows)
    one_step_rows = [row for row in rows if row["population"] == "一步直出新增包"]
    one_step_pass_without_exact_locator = sum(
        row["questions"]["citation_semantic_support"] == "pass"
        and row["review_trace"]["locator_class"] == "chapter_reference_manual_read"
        for row in one_step_rows
    )
    return {
        "task": "第64道件A分层样本逐条语义复核",
        "created_at": "2026-07-20",
        "model_api_calls": 0,
        "reviewer": "Codex local reading",
        "policy": {
            "question_a": "所挂短引/E编号是否在冻结正文内，并在不借相邻事实补洞时语义支撑整条主张。",
            "question_b": "A/B/C/D或七类位置是否正确；delta、触发、兑现、规则、因果和确信度是否越界。",
            "pass": "整条成立",
            "partial": "核心方向成立，但锚只托住部分字段或确信度/范围偏满",
            "fail": "锚不支撑核心主张或类型位置错误",
            "not_applicable": "逐章事实证据没有独立A/B/C/D类型字段",
            "auditability_boundary": "语义判词与证据定位分开登记；一步直出若只有章号和概述，可做本地语义判读，但不得冒充E编号或精确短引级机器回放。",
        },
        "source_workbook": str(WORKBOOK.relative_to(ROOT)),
        "source_workbook_sha256": sha256_file(WORKBOOK),
        "sample_units": len(rows),
        "review_trace_summary": {
            "adjudication_routes": dict(sorted(route_counts.items())),
            "confirmed_pass_ids_sha256": confirmed_pass_id_sha256,
            "locator_classes": dict(sorted(locator_counts.items())),
            "one_step_pass_without_exact_locator": one_step_pass_without_exact_locator,
        },
        "summary": summary,
        "rows": rows,
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# 第64道件A｜分层样本逐条语义复核",
        "",
        "结论：五层共复核233个主单元。‘部分’表示方向大体对，但当前所挂证据不能独立托住整条，不能按全对计。",
        "",
        "| 材料 | 样本 | 引文全通过 | 引文部分 | 引文不通过 | 类型/因果全通过 | 类型/因果部分 | 类型/因果不通过 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in payload["summary"].items():
        citation = item["citation_semantic_support"]
        structure = item["type_delta_cause_correct"]
        lines.append(
            f"| {name} | {item['sample_units']} | {citation.get('pass', 0)} | {citation.get('partial', 0)} | {citation.get('fail', 0)} | "
            f"{structure.get('pass', 0)} | {structure.get('partial', 0)} | {structure.get('fail', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 审计可回查性",
            "",
            f"- 明确异常判词：{payload['review_trace_summary']['adjudication_routes'].get('explicit_exception', 0)} 条。",
            f"- 明确签认通过：{payload['review_trace_summary']['adjudication_routes'].get('explicit_confirmed_pass', 0)} 条；身份集 SHA-256：`{payload['review_trace_summary']['confirmed_pass_ids_sha256']}`。",
            f"- 定位方式：{payload['review_trace_summary']['locator_classes']}。",
            f"- 一步直出中有 {payload['review_trace_summary']['one_step_pass_without_exact_locator']} 条语义通过项只有章号／概述、没有E编号或精确短引定位；它们保留本地判词，但不进入跨臂准确率胜负证据。",
            "",
            "逐条判词、原短引、正文候选段和证据编号均保存在同名 JSON。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = apply_verdicts()
    if args.check:
        print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "件A_分层样本逐条语义复核.json"
    md_path = args.out / "件A_分层样本逐条语义复核.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_md(payload), encoding="utf-8")
    print(f"JSON={json_path}")
    print(f"JSON_SHA256={sha256_file(json_path)}")
    print(f"MD={md_path}")
    print(f"MD_SHA256={sha256_file(md_path)}")
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
