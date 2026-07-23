#!/usr/bin/env python3
"""第64道件B/C：生成差距表与横向对比表（0 模型 API）。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/Z64_三窗回包语义抽查与差距表_20260720"
MEASURE = REPORT / "件B_C_机械母数.json"
AUDIT_A = REPORT / "件A_分层样本逐条语义复核.json"
Z57_SCORE = ROOT / "reports/Z57_稳定语义身份解耦与全链后半_20260719/第3章当章层诚实成绩单.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


RETURN50 = {
    "GOLD-C0003-01": ("hit", "B000301", "面试时间与应参加面试均进入B类触发器。"),
    "GOLD-C0003-09": ("shadow", "A000301", "原短引列出记忆缺口，但正式delta只收‘知识残缺/面试能力下降’，不能算完整事件。"),
    "GOLD-C0003-10": (
        "partial",
        "A000301",
        "正式delta记录知识碎片与面试能力下降，但没有记录‘面试结果关系全家收入改善’，不能算严格命中。",
    ),
}

RETURN20 = {
    "GOLD-C0003-01": ("hit", "B000301", "面试触发器完整。"),
    "GOLD-C0003-04": ("hit", "A000301", "伤口完全愈合的delta完整。"),
    "GOLD-C0003-06": ("hit", "B000302", "采购面包、羔羊肉和豌豆的触发条件与动作完整。"),
}

EVIDENCE50 = {
    "GOLD-C0003-01": ("hit", ["E-03-04"], "面试事实直接在证据层。"),
    "GOLD-C0003-02": ("miss", [], "证据层没有单独记录‘里面房门打开、梅丽莎走出’这一动作头。"),
    "GOLD-C0003-03": ("hit", ["E-03-19"], "藏枪进入抽屉直接记录。"),
    "GOLD-C0003-04": ("hit", ["E-03-20"], "伤口愈合直接记录。"),
    "GOLD-C0003-05": ("hit", ["E-03-25", "E-03-26"], "怀表恢复走动与校时分两条记录。"),
    "GOLD-C0003-06": ("hit", ["E-03-28"], "采购内容与面试用途直接记录。"),
    "GOLD-C0003-07": (
        "partial",
        ["E-03-32"],
        "证据条记录带午餐、旧纱帽、自制书包去上学，但没有记录‘关门’，只能覆盖金标的一部分。",
    ),
    "GOLD-C0003-08": ("hit", ["E-03-38"], "转回仪式和返乡愿望直接记录。"),
    "GOLD-C0003-09": ("hit", ["E-03-02"], "枪、死亡方式、笔记和缺失记忆直接记录。"),
    "GOLD-C0003-10": ("partial", ["E-03-03", "E-03-04", "E-03-15", "E-03-16"], "知识残缺、面试与家庭经济事实都在，但证据条没有把它们合成‘面试结果关系收入改善’这一完整结构主张。"),
    "GOLD-C0003-11": ("hit", ["E-03-11", "E-03-24", "E-03-25"], "机械志向、修表与操作都直接记录。"),
    "GOLD-C0003-12": ("partial", ["E-03-16", "E-03-17", "E-03-18"], "班森负担与克莱恩能力差距有记录，但‘克莱恩已经想帮哥哥’这一意愿句没有独立证据条。"),
    "GOLD-C0003-13": ("hit", ["E-03-28", "E-03-29", "E-03-30"], "面试羔羊肉与家庭早餐节俭共同托住该条。"),
    "GOLD-C0003-14": ("hit", ["E-03-33"], "五十分钟与省车费步行直接记录。"),
}


def build_gold_crosswalk(measure: dict[str, Any]) -> list[dict[str, Any]]:
    z57 = json.loads(Z57_SCORE.read_text(encoding="utf-8"))
    local = {row["gold_item_id"]: row for row in z57["rows"]}
    result: list[dict[str, Any]] = []
    for item in measure["gold_chapter3"]["items"]:
        gold_id = item["gold_id"]
        local_row = local[gold_id]
        return50 = RETURN50.get(gold_id, ("miss", None, "50章事件卡没有对应正式结构事件。"))
        return20 = RETURN20.get(gold_id, ("miss", None, "20章事件卡没有对应正式结构事件。"))
        evidence = EVIDENCE50[gold_id]
        result.append(
            {
                "gold_id": gold_id,
                "claim": item["claim"],
                "local_v1_2": {
                    "verdict": local_row["verdict"],
                    "event_id": local_row.get("corresponding_event_id_run_local_only"),
                    "loss_stage": local_row.get("loss_stage"),
                },
                "return_50_event_records": {
                    "verdict": return50[0],
                    "record_id": return50[1],
                    "note": return50[2],
                },
                "return_20_event_records": {
                    "verdict": return20[0],
                    "record_id": return20[1],
                    "note": return20[2],
                },
                "return_50_evidence_layer": {
                    "verdict": evidence[0],
                    "evidence_ids": evidence[1],
                    "note": evidence[2],
                },
            }
        )
    return result


def verdict_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts = {"hit": 0, "shadow": 0, "partial": 0, "miss": 0}
    for row in rows:
        counts[row[key]["verdict"]] += 1
    return counts


def build_b(measure: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    crosswalk = build_gold_crosswalk(measure)
    event_sets = measure["event_sets"]
    local = event_sets["local_current_122"]
    return20 = event_sets["return_20_window"]
    return50_20 = event_sets["return_50_window_first20"]
    type_diff = {}
    for label, data in (("20章窗2", return20), ("50章窗2前20章", return50_20)):
        type_diff[label] = {
            event_type: data["records_by_type"][event_type] - local["records_by_type"][event_type]
            for event_type in "ABCD"
        }
        type_diff[label]["total"] = data["records"] - local["records"]
    return {
        "task": "第64道件B：回包件与本地链差距表",
        "created_at": "2026-07-20",
        "model_api_calls": 0,
        "comparison_boundary": "现役122条仅覆盖前20章；50章事件卡只取前20章作同窗机械母数。第3章金标按当章层14条逐条判。各轮考条件不同，只并列，不据此改判现役链。",
        "event_density": {
            "local_current_122": local,
            "return_20_window": return20,
            "return_50_window_first20": return50_20,
            "difference_vs_local": type_diff,
        },
        "semantic_sample_summary": {
            key: audit["summary"][key]
            for key in ("20章窗2事件记录", "50章窗2事件记录", "50章窗3逐章证据")
        },
        "chapter3_gold_crosswalk": crosswalk,
        "chapter3_score_summary": {
            "local_v1_2": verdict_counts(crosswalk, "local_v1_2"),
            "return_50_event_records": verdict_counts(crosswalk, "return_50_event_records"),
            "return_20_event_records": verdict_counts(crosswalk, "return_20_event_records"),
            "return_50_evidence_layer": verdict_counts(crosswalk, "return_50_evidence_layer"),
        },
        "main_findings": [
            "数量不是同一种覆盖：20章回包比现役多84条，但增量主要落在C、D；50章回包前20章总量接近现役，却把A、B大幅换成C、D。",
            "现役每条平均4.7459个短锚；两个回包事件集均为每条1个连续短引。件A显示50章事件卡类型大多放对，但复合字段常超出单锚承载范围。",
        "第3章严格结构命中：现役2/14、50章事件卡1/14、20章事件卡3/14。50章事件卡另有1条部分、1条影子。1,761证据层不是结构事件合同，事实覆盖为10条全覆盖、3条部分、1条缺失，不能冒充10/14结构命中。",
        ],
        "protected_sources": measure["protected_sources"],
    }


def build_c(measure: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    docs = measure["document_windows"]
    event_sets = measure["event_sets"]
    deep20 = docs["deep_analysis_20"]
    deep50 = docs["deep_analysis_50"]
    return20 = event_sets["return_20_window"]
    return50 = event_sets["return_50_window_full"]
    two = measure["package_comparison"]["two_step"]
    one = measure["package_comparison"]["one_step"]

    category_rows = []
    for category in ("世界观设定", "人物档案", "地点档案", "人物关系", "每章大纲", "逻辑句", "每章写法"):
        two_item = two["categories"][category]
        one_item = one["categories"][category]
        category_rows.append(
            {
                "category": category,
                "two_step_primary_units": two_item["primary_units"],
                "one_step_primary_units": one_item["primary_units"],
                "primary_unit_difference": two_item["primary_units"] - one_item["primary_units"],
                "two_step_field_claims": two_item["field_claims"],
                "one_step_field_claims": one_item["field_claims"],
                "field_claim_difference": two_item["field_claims"] - one_item["field_claims"],
            }
        )

    return {
        "task": "第64道件C：20比50及两步法比一步直出",
        "created_at": "2026-07-20",
        "model_api_calls": 0,
        "window_20_vs_50": {
            "deep_analysis": {
                "20_total_characters": deep20["characters"],
                "50_total_characters": deep50["characters"],
                "20_characters_per_chapter": round(deep20["characters"] / 20, 2),
                "50_characters_per_chapter": round(deep50["characters"] / 50, 2),
                "per_chapter_change_ratio": round((deep50["characters"] / 50) / (deep20["characters"] / 20) - 1, 6),
                "20_heading_count": deep20["heading_count"],
                "50_heading_count": deep50["heading_count"],
                "20_table_rows": deep20["table_row_count"],
                "50_table_rows": deep50["table_row_count"],
            },
            "event_cards": {
                "20_records": return20["records"],
                "50_records": return50["records"],
                "20_records_per_chapter": return20["records_per_chapter"]["mean"],
                "50_records_per_chapter": return50["records_per_chapter"]["mean"],
                "per_chapter_change_ratio": round(return50["records_per_chapter"]["mean"] / return20["records_per_chapter"]["mean"] - 1, 6),
                "20_type_counts": return20["records_by_type"],
                "50_type_counts": return50["records_by_type"],
            },
            "evidence_layer_50": measure["evidence_50_window"],
            "strategy_trace_files": {
                key: docs[key]
                for key in ("thought_trace_evidence50", "thought_trace_events50", "thought_trace_deep50")
            },
            "verdict": "部分印证：50章回包中存在彼此独立的证据、事件卡和深拆产物；现有材料不能证明生成先后、谁主动拆分，也不能把三类产物的出现单独归因于窗口长度。深拆每章字符从2626.35降到971.48，事件卡从10.3条/章降到6.16条/章，单章结构密度仍明显缩水。",
        },
        "two_step_vs_one_step": {
            "cloud_count_verification": measure["cloud_count_verification"],
            "category_rows": category_rows,
            "totals": {
                "two_step": two["totals"],
                "one_step": one["totals"],
                "primary_unit_difference": two["totals"]["primary_units"] - one["totals"]["primary_units"],
                "primary_unit_increase_ratio": round(two["totals"]["primary_units"] / one["totals"]["primary_units"] - 1, 6),
                "field_claim_difference": two["totals"]["field_claims"] - one["totals"]["field_claims"],
                "field_claim_increase_ratio": round(two["totals"]["field_claims"] / one["totals"]["field_claims"] - 1, 6),
                "character_increase_ratio": round(two["totals"]["non_whitespace_characters"] / one["totals"]["non_whitespace_characters"] - 1, 6),
            },
            "citation_methods": {
                "two_step": "七类567个主单元全部挂E编号；七份正文共3,765次E编号引用，可逐条回到1,761证据母集。",
                "one_step": "不使用E编号，改用章号＋短引/证据强度；读起来短，但跨文件去重与机器回放成本更高。",
            },
            "semantic_samples": {
                "two_step": audit["summary"]["两步法新增包"],
                "one_step": audit["summary"]["一步直出新增包"],
            },
            "verdict": "在当前两份材料里，两步法的密度与可回查性明显更强，一步直出更短、更适合人读。35条/臂的本地语义判读中，两步法引文全通过33、一步直出32；一步直出没有E编号且定位合同不同，这个1条差异只登记，不用于宣判准确率胜负。",
        },
        "book_selection_implication": "金标多本化若要保留可追溯底料，优先选择能稳定切章、人物多且跨章伏笔明确的书做两步法；一步直出可做浏览层，不宜单独当银标母层。",
    }


def render_b(payload: dict[str, Any]) -> str:
    density = payload["event_density"]
    scores = payload["chapter3_score_summary"]
    lines = [
        "# 第64道件B｜回包件与本地链差距表",
        "",
        "结论：回包更密，不等于结构层更接近金标。20章回包把大量内容放进C/D，50章回包则常用一个短引承载一条复合事件；第3章严格命中分别只有3/14和1/14。",
        "",
        "## 前20章同窗母数",
        "",
        "| 材料 | 总条数 | A | B | C | D | 条/章 | 锚/条 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "local_current_122": "现役122条",
        "return_20_window": "20章回包",
        "return_50_window_first20": "50章回包的前20章",
    }
    for key in labels:
        row = density[key]
        types = row["records_by_type"]
        lines.append(
            f"| {labels[key]} | {row['records']} | {types['A']} | {types['B']} | {types['C']} | {types['D']} | {row['records_per_chapter']['mean']} | {row['anchors_per_record_mean']} |"
        )
    lines.extend(
        [
            "",
            "## 第3章金标14条",
            "",
            "| 金标 | 本地v1.2 | 50章事件卡 | 20章事件卡 | 1,761证据层 |",
            "|---|---|---|---|---|",
        ]
    )
    mark = {"hit": "命中", "shadow": "影子", "partial": "部分", "miss": "漏"}
    for row in payload["chapter3_gold_crosswalk"]:
        lines.append(
            f"| {row['gold_id']} {row['claim']} | {mark[row['local_v1_2']['verdict']]} | "
            f"{mark[row['return_50_event_records']['verdict']]}{(' '+row['return_50_event_records']['record_id']) if row['return_50_event_records']['record_id'] else ''} | "
            f"{mark[row['return_20_event_records']['verdict']]}{(' '+row['return_20_event_records']['record_id']) if row['return_20_event_records']['record_id'] else ''} | "
            f"{mark[row['return_50_evidence_layer']['verdict']]}{(' '+','.join(row['return_50_evidence_layer']['evidence_ids'])) if row['return_50_evidence_layer']['evidence_ids'] else ''} |"
        )
    lines.extend(
        [
            "",
            f"- 现役v1.2：{scores['local_v1_2']['hit']}/14 严格命中。",
            f"- 50章事件卡：{scores['return_50_event_records']['hit']}/14 严格命中，另有 {scores['return_50_event_records']['partial']} 条部分、{scores['return_50_event_records']['shadow']} 条影子。",
            f"- 20章事件卡：{scores['return_20_event_records']['hit']}/14 严格命中。",
            f"- 1,761证据层：{scores['return_50_evidence_layer']['hit']} 条事实全覆盖、{scores['return_50_evidence_layer']['partial']} 条部分、{scores['return_50_evidence_layer']['miss']} 条缺失；它不是结构事件合同，不能换算成结构命中率。",
            "",
            "⚠️ 考条件不同，这张表只说明差距落在哪，不改判本地基线，也不把回包升成真值。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def render_c(payload: dict[str, Any]) -> str:
    window = payload["window_20_vs_50"]
    packages = payload["two_step_vs_one_step"]
    deep = window["deep_analysis"]
    events = window["event_cards"]
    totals = packages["totals"]
    lines = [
        "# 第64道件C｜20 vs 50＋两步法 vs 一步直出",
        "",
        "结论：50章回包中存在独立的证据、事件卡和深拆产物；现有材料不能证明生成先后、谁主动拆分，也不能归因于窗口长度。当前两步法材料更厚、更好回查；两臂定位合同不同，不做准确率胜负判断。",
        "",
        "## 20章窗 vs 50章窗",
        "",
        "| 指标 | 20章 | 50章 | 变化 |",
        "|---|---:|---:|---:|",
        f"| 深拆总字符 | {deep['20_total_characters']} | {deep['50_total_characters']} | 50章总量反而少 {deep['20_total_characters']-deep['50_total_characters']} |",
        f"| 深拆字符/章 | {deep['20_characters_per_chapter']} | {deep['50_characters_per_chapter']} | {pct(deep['per_chapter_change_ratio'])} |",
        f"| 事件条数 | {events['20_records']} | {events['50_records']} | +{events['50_records']-events['20_records']}（章数多30） |",
        f"| 事件条数/章 | {events['20_records_per_chapter']} | {events['50_records_per_chapter']} | {pct(events['per_chapter_change_ratio'])} |",
        f"| 独立逐章证据 | 无单独母集 | {window['evidence_layer_50']['records']} | 35.22条/章 |",
        "",
        f"判词：{window['verdict']}",
        "",
        "## 两步法 vs 一步直出",
        "",
        "| 类别 | 两步法主单元 | 一步主单元 | 两步字段 | 一步字段 |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in packages["category_rows"]:
        lines.append(
            f"| {row['category']} | {row['two_step_primary_units']} | {row['one_step_primary_units']} | {row['two_step_field_claims']} | {row['one_step_field_claims']} |"
        )
    lines.extend(
        [
            "",
            f"- 主单元：两步法 {totals['two_step']['primary_units']}，一步直出 {totals['one_step']['primary_units']}，多 {totals['primary_unit_difference']}（{pct(totals['primary_unit_increase_ratio'])}）。",
            f"- 字段主张：两步法 {totals['two_step']['field_claims']}，一步直出 {totals['one_step']['field_claims']}，多 {totals['field_claim_difference']}（{pct(totals['field_claim_increase_ratio'])}）。",
            f"- 非空白字符：两步法比一步直出多 {pct(totals['character_increase_ratio'])}。",
            f"- 证据方式：{packages['citation_methods']['two_step']}",
            f"- 一步方式：{packages['citation_methods']['one_step']}",
            "",
            f"判词：{packages['verdict']}",
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
    measure = json.loads(MEASURE.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT_A.read_text(encoding="utf-8"))
    b = build_b(measure, audit)
    c = build_c(measure, audit)
    if args.check:
        print(json.dumps({"B": b["chapter3_score_summary"], "C": c["two_step_vs_one_step"]["totals"]}, ensure_ascii=False, sort_keys=True))
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "件B_与本地链差距表.json": json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "件B_与本地链差距表.md": render_b(b),
        "件C_20比50及两步法比一步直出.json": json.dumps(c, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "件C_20比50及两步法比一步直出.md": render_c(c),
    }
    for name, content in outputs.items():
        path = args.out / name
        path.write_text(content, encoding="utf-8")
        print(f"{name}={sha256_file(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
