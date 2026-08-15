"""M8 续写规划 V0：目的挂卡 → 选项／前置卡 → 冲突爆出。

吃已确认事实（C4）＋作者一句目的；吐 C7 v0 剧情层（计划，不入事实账）。
写作指导是出题副产品，不另开 API。不代写正文（J1）。
"""

from __future__ import annotations

import json
import time

from mvp import extract as ex
from mvp import store

CONTRACT = "C7_PLOT_LAYER v0"
MAX_FACTS = 40
FACT_CLIP = 80

CONFLICT_PAIRS = (
    (("死", "去世", "身亡", "已死", "亡故", "埋"), ("活", "复活", "醒来", "走出来", "还活")),
    (("不知道", "不知情", "被瞒", "瞒住"), ("告诉", "告知", "知道真相", "坦白")),
    (("离开", "失踪", "消失"), ("回来", "现身")),
)

INSTRUCTIONS = (
    "你是网文规划助手，只出题、不写正文。\n"
    "根据【已确认事实】和作者【目的】生成卡片选项。\n"
    "- 目的挂到卡上：单独开卡或附着；作者注解影响选项内容，不要改事实账\n"
    "- 选项是方向，不是示范成文；对白只写「该透露什么信息点」\n"
    "- 跟已确认事实或本章原意图打架时必须进 conflicts，问改哪边\n"
    "- reverse=true 时先出前置卡（前面得先达成什么），再出目的卡\n"
    "- plugin_craft 没有插件就空串\n"
    "只输出 JSON 对象，形状：\n"
    '{"cards":[{"id":"card01","role":"purpose|prerequisite|attach","title":"",'
    '"purpose_note":"","options":[{"id":"A","label":"","reveal_intent":""}],'
    '"guidance":{"card_problem":"","dialogue_reveal":"","plugin_craft":""}}],'
    '"conflicts":[{"kind":"fact|intent","fact_id":"","fact_text":"","why":"","ask":""}]}'
)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def confirmed_facts(project: str) -> list[dict]:
    return [
        f for f in store.facts(project)
        if isinstance(f, dict) and f.get("status") == store.STATUS_CONFIRMED
    ]


def _hit(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def mechanical_conflicts(purpose: str, facts: list[dict], chapter_intent: str) -> list[dict]:
    """用几组反义词对拍目的 vs 真值／本章原意图。不花调用。"""
    out = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, fact_id: str, fact_text: str, why: str, ask: str) -> None:
        key = (kind, fact_id, why)
        if key in seen:
            return
        seen.add(key)
        out.append({
            "kind": kind, "fact_id": fact_id, "fact_text": fact_text,
            "why": why, "ask": ask,
        })

    for f in facts:
        text = f.get("text") or ""
        for left, right in CONFLICT_PAIRS:
            if _hit(text, left) and _hit(purpose, right):
                add("fact", f["id"], text,
                    f"已确认事实偏「{'／'.join(left[:2])}」，目的偏「{'／'.join(right[:2])}」",
                    "改目的，还是改已确认事实？")
            if _hit(text, right) and _hit(purpose, left):
                add("fact", f["id"], text,
                    f"已确认事实偏「{'／'.join(right[:2])}」，目的偏「{'／'.join(left[:2])}」",
                    "改目的，还是改已确认事实？")
    if chapter_intent:
        for left, right in CONFLICT_PAIRS:
            if _hit(chapter_intent, left) and _hit(purpose, right):
                add("intent", "", chapter_intent,
                    "本章原意图和这句目的对着干",
                    "改目的，还是改本章原意图？")
            if _hit(chapter_intent, right) and _hit(purpose, left):
                add("intent", "", chapter_intent,
                    "本章原意图和这句目的对着干",
                    "改目的，还是改本章原意图？")
    return out


def _option(oid: str, label: str, reveal: str) -> dict:
    return {"id": oid, "label": label, "reveal_intent": reveal}


def _card(cid: str, role: str, title: str, note: str, options: list, problem: str, reveal: str) -> dict:
    return {
        "id": cid,
        "role": role,
        "title": title,
        "purpose_note": note,
        "options": options,
        "guidance": {
            "card_problem": problem,
            "dialogue_reveal": reveal,
            "plugin_craft": "",
        },
    }


def stub_cards(purpose: str, purpose_note: str, reverse: bool) -> list[dict]:
    placement_note = purpose_note or purpose
    purpose_card = _card(
        "card03" if reverse else "card01",
        "attach" if purpose_note else "purpose",
        "目的卡：兑现作者这句话",
        placement_note,
        [
            _option("A", "正面对付这笔账，当场把目的立起来", "只立「发生了什么」，不解释为什么现在才发生"),
            _option("B", "侧面兑现：别人先撞上结果，主角后补动作", "旁人先说出结果，主角不自报"),
            _option("C", "压住半拍：这章只把目的推到门口，下章才进门", "只透露「瞒不住了」，不给完整答案"),
        ],
        f"这张卡要解决：{purpose}",
        "对白只透露与目的直接相关的信息点，不写示范台词",
    )
    if not reverse:
        return [purpose_card]
    pre1 = _card(
        "card01", "prerequisite",
        "前置：让关键人物处于能被改变的状态",
        "后面那张目的卡要成立，这里必须先成立",
        [
            _option("A", "先把公开认知拆开一条缝", "只透露有人在查，不透露结论"),
            _option("B", "先留下无法用旧解释圆过去的现场痕迹", "痕迹本身，不解释来源"),
            _option("C", "先让知情者自己动摇", "动摇，不给新设定"),
        ],
        "前面得先达成：旧状态不再铁板一块",
        "只能透露「这件事没结」",
    )
    pre2 = _card(
        "card02", "prerequisite",
        "前置：把信息缺口摆上台面",
        "有人必须处在「该知道却还不知道」的位置",
        [
            _option("A", "安排一次不得不问的场合", "问句本身，不给答句成文"),
            _option("B", "让第三者把缺口说破半句", "半句缺口，不补全"),
            _option("C", "用物件／痕迹代替开口", "看见什么，不解释什么"),
        ],
        "前面得先达成：有人处于必须被告知的位置",
        "只透露「有事没说完」",
    )
    return [pre1, pre2, purpose_card]


def _pack_facts(facts: list[dict]) -> str:
    lines = []
    for f in facts[:MAX_FACTS]:
        text = (f.get("text") or "").replace("\n", " ")[:FACT_CLIP]
        lines.append(f"{f['id']}｜{text}")
    return "\n".join(lines) if lines else "（尚无已确认事实）"


def _normalize_card(raw: dict, idx: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    title = (raw.get("title") or "").strip()
    opts_in = raw.get("options") or []
    options = []
    letters = "ABCDEF"
    for i, o in enumerate(opts_in):
        if not isinstance(o, dict):
            continue
        label = (o.get("label") or "").strip()
        if not label:
            continue
        oid = (o.get("id") or "").strip() or (letters[i] if i < len(letters) else str(i + 1))
        options.append(_option(oid, label, (o.get("reveal_intent") or "").strip()))
    if not title or not options:
        return None
    g = raw.get("guidance") if isinstance(raw.get("guidance"), dict) else {}
    role = (raw.get("role") or "purpose").strip()
    if role not in ("purpose", "prerequisite", "attach"):
        role = "purpose"
    return {
        "id": (raw.get("id") or f"card{idx:02d}").strip(),
        "role": role,
        "title": title,
        "purpose_note": (raw.get("purpose_note") or "").strip(),
        "options": options,
        "guidance": {
            "card_problem": (g.get("card_problem") or "").strip(),
            "dialogue_reveal": (g.get("dialogue_reveal") or "").strip(),
            "plugin_craft": (g.get("plugin_craft") or "").strip(),
        },
    }


def _normalize_conflict(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    why = (raw.get("why") or "").strip()
    if not why:
        return None
    kind = (raw.get("kind") or "fact").strip()
    if kind not in ("fact", "intent"):
        kind = "fact"
    ask = (raw.get("ask") or "").strip() or (
        "改目的，还是改已确认事实？" if kind == "fact" else "改目的，还是改本章原意图？"
    )
    return {
        "kind": kind,
        "fact_id": (raw.get("fact_id") or "").strip(),
        "fact_text": (raw.get("fact_text") or "").strip(),
        "why": why,
        "ask": ask,
    }


def _merge_conflicts(mech: list[dict], model_ones: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out = []
    for c in mech + model_ones:
        key = (c.get("kind"), c.get("fact_id"), c.get("why"))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def call_model_plan(purpose: str, purpose_note: str, reverse: bool,
                    chapter_intent: str, facts: list[dict], cfg: dict) -> dict:
    user = (
        f"【目的】\n{purpose}\n\n"
        f"【卡上注解】\n{purpose_note or '（无）'}\n\n"
        f"【本章原意图】\n{chapter_intent or '（未给）'}\n\n"
        f"【reverse】{str(reverse).lower()}\n\n"
        f"【已确认事实】\n{_pack_facts(facts)}"
    )
    r = ex.call_json(INSTRUCTIONS, user, cfg)
    data = r["data"]
    if not isinstance(data, dict):
        raise RuntimeError(f"出题模型输出不是对象：{str(data)[:200]}")
    cards = []
    for i, raw in enumerate(data.get("cards") or [], 1):
        card = _normalize_card(raw, i)
        if card:
            cards.append(card)
    if not cards:
        raise RuntimeError("出题模型没吐出可用卡片")
    conflicts = []
    for raw in data.get("conflicts") or []:
        c = _normalize_conflict(raw)
        if c:
            conflicts.append(c)
    return {"cards": cards, "conflicts": conflicts, "model": r.get("model") or cfg.get("model_id", "")}


def run_plan(project: str, purpose: str, *, purpose_note: str = "",
             reverse: bool = False, stub: bool = False,
             chapter_intent: str = "") -> dict:
    purpose = (purpose or "").strip()
    if not purpose:
        raise SystemExit("请用 --purpose 写一句要达成的目的")
    store._require(project)
    facts = confirmed_facts(project)
    purpose_note = (purpose_note or "").strip()
    chapter_intent = (chapter_intent or "").strip()
    mech = mechanical_conflicts(purpose, facts, chapter_intent)

    if stub:
        cards = stub_cards(purpose, purpose_note, reverse)
        model = "stub"
        extra = []
    else:
        cfg = ex.load_config()
        payload = call_model_plan(purpose, purpose_note, reverse, chapter_intent, facts, cfg)
        cards = payload["cards"]
        extra = payload["conflicts"]
        model = payload["model"]

    report = {
        "contract": CONTRACT,
        "project": project,
        "generated_at": _now(),
        "model": model,
        "purpose": purpose,
        "purpose_note": purpose_note,
        "mode": "reverse" if reverse else "forward",
        "purpose_placement": "attach" if purpose_note else "standalone",
        "chapter_intent": chapter_intent,
        "confirmed_fact_ids": [f["id"] for f in facts[:MAX_FACTS]],
        "cards": cards,
        "conflicts": _merge_conflicts(mech, extra if not stub else []),
    }
    return report


def save_plan(project: str, report: dict) -> str:
    path = store.project_dir(project) / "plan_latest.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(path)


def format_plan(report: dict) -> str:
    lines = [
        f"目的：{report['purpose']}",
        f"挂法：{'附着在卡上' if report['purpose_placement'] == 'attach' else '单独开卡'}"
        f"｜模式：{'反向拆前置卡' if report['mode'] == 'reverse' else '正向出题'}"
        f"｜模型：{report['model']}",
    ]
    if report.get("purpose_note"):
        lines.append(f"注解：{report['purpose_note']}")
    if report.get("chapter_intent"):
        lines.append(f"本章原意图：{report['chapter_intent']}")
    n_facts = len(report.get("confirmed_fact_ids") or [])
    lines.append(f"吃进已确认事实：{n_facts} 条")

    conflicts = report.get("conflicts") or []
    lines.append("")
    if conflicts:
        lines.append(f"🔥 冲突 {len(conflicts)} 条——先看这些，问改哪边")
        for c in conflicts:
            who = c.get("fact_id") or "本章原意图"
            text = (c.get("fact_text") or "")[:60]
            lines.append(f"  · [{c.get('kind')}] {who}「{text}」")
            lines.append(f"    {c.get('why')}")
            lines.append(f"    👉 {c.get('ask')}")
    else:
        lines.append("冲突：没有机械对拍到的硬打架（不代表语义上一定没事）")

    role_label = {
        "purpose": "目的卡",
        "prerequisite": "前置卡",
        "attach": "附着卡",
    }
    for card in report.get("cards") or []:
        lines.append("")
        lines.append(f"【{card['id']} {role_label.get(card['role'], card['role'])}】{card['title']}")
        if card.get("purpose_note"):
            lines.append(f"  本卡目的：{card['purpose_note']}")
        for o in card.get("options") or []:
            lines.append(f"  {o['id']}. {o['label']}")
            if o.get("reveal_intent"):
                lines.append(f"     对白透露：{o['reveal_intent']}")
        g = card.get("guidance") or {}
        lines.append("  写作指导（出题副产品，不另调 API）")
        lines.append(f"    卡片要解决：{g.get('card_problem') or '（空）'}")
        lines.append(f"    对白透露：{g.get('dialogue_reveal') or '（空）'}")
        lines.append(f"    插件写法：{g.get('plugin_craft') or '（空）'}")
    return "\n".join(lines)
