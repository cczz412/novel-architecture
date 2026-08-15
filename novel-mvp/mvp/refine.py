"""M3b 抽取质检管线：主抽候选 → 引文回填 → 补漏 → 验真 → 去噪 → 去重。

主抽（M3a，extract.py）用 config.json 的 model_id（豆包）；
补漏/验真/去噪调 checker_model_id（GLM 5.2）——CZ 2026-08-13 拍板：
抽取和质检必须用不同家族的 API，同一个模型思路趋同、自查自话拦不住错。
交叉审计：豆包抽的 GLM 查；GLM 补的豆包查——谁的产出都不由自己签绿票。

五段全部可独立开关（stages 参数）；anchor/dedup 是机械段，零调用。
产出：精修后的候选列表＋质量小票（每段改了什么、调用几次、各花多久）。

合同：候选沿用 C3 的 text/quote/seg，精修追加 origin/quote_status/
quote_start/quote_end/verify 等审计字段（C3 升 v1 前先当扩展字段用）。
"""

from __future__ import annotations

import difflib
import re
import time

from . import extract as ex

ALL_STAGES = ["anchor", "supplement", "verify", "denoise", "dedup"]

VERIFY_INSTRUCTIONS = (
    "你是小说事实复查员。给你一个【责任段】和一批带编号的【候选事实句】。\n"
    "逐条判断：责任段原文是否真的支持这句话。\n"
    "- support：原文明确支持\n"
    "- fixable：仅限人名、数字、对象、时序、归因（谁说的/谁做的）写错这类具体错误，能一句改对\n"
    "- unsupported：原文没说（编造、过度推断、把心理/比喻/未发生的计划当事实）\n"
    "引文与原文一致、只是措辞简略或语气差异的算 support，不算 fixable。\n"
    "【前文背景】【后文背景】只读；候选若只有背景支持、责任段本身不支持，也算 unsupported。\n"
    '只输出 JSON：{"verdicts":[{"i":编号,"verdict":"support|fixable|unsupported",'
    '"fix":"仅 fixable 给修正后的完整事实句","reason":"一句话"}]}\n'
    "每个编号都必须有一条判定，不得遗漏。"
)

SUPPLEMENT_INSTRUCTIONS = (
    "你是小说事实补漏员。给你一个【责任段】和一批【已抽出的事实句】。\n"
    "找出责任段里已发生、但清单里漏掉的客观事实。\n"
    "- 每句独立完整、主语明确、能回责任段原文验证\n"
    "- 心理活动、比喻、猜测、未发生的计划不算事实\n"
    "- 与已有清单意思相同或仅措辞不同的不要重复报\n"
    "- 已抽清单里长句包含的信息也算已抽，不得拆开重报\n"
    "- 【前文背景】【后文背景】只读，不得从背景产出事实\n"
    '只输出 JSON：{"missing":[{"text":"事实句","quote":"责任段中的原文依据片段"}]}\n'
    '没有遗漏时输出 {"missing":[]}'
)

DENOISE_INSTRUCTIONS = (
    "你是小说事实账管理员。事实账是长期账本：只收后文可能引用、不能安全遗忘的关键信息。\n"
    "给你一个【责任段】和一批带编号的【候选事实句】，逐条判断值不值得进长期账。\n"
    "值得（keep=true）：改变人物状态/关系/位置、揭示设定或世界规则、发生了具体事件、\n"
    "给出后文可能引用的具体信息（名字、数字、物品、能力、约定）。\n"
    "不值得（keep=false）：纯场面描写复述、同一动作的碎步拆分、无信息量的过渡、修辞感受。\n"
    "拿不准时倾向 keep=true，宁多勿漏。\n"
    '只输出 JSON：{"items":[{"i":编号,"keep":true,"reason":"一句话"}]}\n'
    "每个编号都必须有一条判定，不得遗漏。"
)


# ---------- 底层：带计时的调用 ----------

def timed_call(instructions: str, user_content: str, cfg: dict, model_id: str) -> dict:
    """带指定模型调 call_json 并计时。返回 {'data':…, 'usage':…, 'model':…, 'seconds':…}"""
    call_cfg = {**cfg, "model_id": model_id}
    t0 = time.monotonic()
    r = ex.call_json(instructions, user_content, call_cfg)
    r["seconds"] = round(time.monotonic() - t0, 1)
    return r


def _numbered(facts: list[dict]) -> str:
    return "\n".join(f"{i}. {f['text']}" for i, f in enumerate(facts, 1))


# ---------- anchor：程序回填引文（机械，修 I-013） ----------

def _norm(s: str) -> str:
    return re.sub(r"[\s“”\"'‘’…·]+", "", s)


def _fuzzy_span(hay: str, needle: str) -> tuple[int, int] | None:
    """在 hay 里找与 needle 大致对应的连续区间；找不到返回 None。"""
    sm = difflib.SequenceMatcher(None, hay, needle, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size > 0]
    if not blocks:
        return None
    covered = sum(b.size for b in blocks)
    if covered < max(6, int(len(needle) * 0.6)):
        return None
    start = min(b.a for b in blocks)
    end = max(b.a + b.size for b in blocks)
    if end - start > len(needle) * 2 + 20:
        # 匹配块散得太开：退回以最长块为锚
        big = max(blocks, key=lambda b: b.size)
        start = max(0, big.a - big.b)
        end = min(len(hay), start + len(needle))
    return start, end


def anchor_candidate(seg: dict, cand: dict) -> None:
    """就地给候选补 quote_status（exact/fuzzy/missing）＋章内字符坐标。
    fuzzy 命中时把 quote 换成原文逐字片段——引文从「模型转抄」变「程序回填」。"""
    quote = (cand.get("quote") or "").strip()
    text = seg["text"]
    if not quote:
        cand["quote_status"] = "missing"
        return
    idx = text.find(quote)
    if idx < 0:
        nq, nt = _norm(quote), _norm(text)
        if nq and nq in nt:
            # 只差空白/引号：定位规范化命中的原文区间
            span = _fuzzy_span(text, quote)
            if span:
                idx, end = span
                cand["quote"] = text[idx:end]
                cand["quote_status"] = "exact_after_norm"
                cand["quote_start"] = seg["start"] + idx
                cand["quote_end"] = seg["start"] + end
                return
        span = _fuzzy_span(text, quote)
        if span:
            s, e = span
            cand["quote_before_anchor"] = quote
            cand["quote"] = text[s:e]
            cand["quote_status"] = "fuzzy"
            cand["quote_start"] = seg["start"] + s
            cand["quote_end"] = seg["start"] + e
        else:
            cand["quote_status"] = "missing"
        return
    cand["quote_status"] = "exact"
    cand["quote_start"] = seg["start"] + idx
    cand["quote_end"] = seg["start"] + idx + len(quote)


# ---------- supplement / verify / denoise：API 段 ----------

def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；])", text)
    return [p.strip() for p in parts if p.strip()]


def supplement_segment(seg: dict, existing: list[dict], cfg: dict, model_id: str) -> dict:
    # 已抽清单先机械拆句再喂：主抽的巨条拆成原子行，补漏员才看得见「长句里已含的信息」
    # （I-019：大理寺主抽独白巨条被补漏拆开原子化重报，八成是假补）
    sentences: list[str] = []
    for f in existing:
        sentences.extend(_split_sentences(f["text"]))
    listing = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1)) or "（无）"
    user = ex.build_user_content(seg) + "\n\n【已抽出的事实句】\n" + listing
    r = timed_call(SUPPLEMENT_INSTRUCTIONS, user, cfg, model_id)
    items = [
        {"text": (m.get("text") or "").strip(), "quote": (m.get("quote") or "").strip(),
         "seg": seg["seg"], "origin": "supplement"}
        for m in r["data"].get("missing", [])
        if isinstance(m, dict) and (m.get("text") or "").strip()
    ]
    return {"items": items, "seconds": r["seconds"], "usage": r["usage"]}


def verify_segment(seg: dict, cands: list[dict], cfg: dict, model_id: str) -> dict:
    user = ex.build_user_content(seg) + "\n\n【候选事实句】\n" + _numbered(cands)
    r = timed_call(VERIFY_INSTRUCTIONS, user, cfg, model_id)
    by_i = {}
    for v in r["data"].get("verdicts", []):
        if isinstance(v, dict) and isinstance(v.get("i"), int):
            by_i[v["i"]] = v
    for i, c in enumerate(cands, 1):
        v = by_i.get(i)
        if not v:
            c["verify"] = "unreviewed"  # 模型漏判：不算通过也不算毙，留人看
            continue
        verdict = v.get("verdict", "")
        c["verify"] = verdict if verdict in ("support", "fixable", "unsupported") else "unreviewed"
        if v.get("reason"):
            c["verify_reason"] = str(v["reason"])[:120]
        if c["verify"] == "fixable" and (v.get("fix") or "").strip():
            # 修正文本是质检模型手写的，不自动上账（实测 2 条里 1 条是误改）；
            # 只挂建议＋待人审标记，原句保留，作者在审查台裁决。
            c["fix_suggest"] = str(v["fix"]).strip()
            c["needs_review"] = True
    return {"seconds": r["seconds"], "usage": r["usage"]}


def denoise_segment(seg: dict, cands: list[dict], cfg: dict, model_id: str) -> dict:
    user = ex.build_user_content(seg) + "\n\n【候选事实句】\n" + _numbered(cands)
    r = timed_call(DENOISE_INSTRUCTIONS, user, cfg, model_id)
    by_i = {}
    for v in r["data"].get("items", []):
        if isinstance(v, dict) and isinstance(v.get("i"), int):
            by_i[v["i"]] = v
    for i, c in enumerate(cands, 1):
        v = by_i.get(i)
        c["keep"] = bool(v.get("keep", True)) if v else True  # 漏判默认留
        if v and v.get("reason"):
            c["keep_reason"] = str(v["reason"])[:120]
    return {"seconds": r["seconds"], "usage": r["usage"]}


# ---------- dedup：机械去重 ----------

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_NUM_LINKERS = "是为有了达到至升降变成加减共约计"


def _numeric_pairs(norm_text: str) -> frozenset:
    """数值句签名：句中每个数字 →（属性词, 数值）对的集合。
    属性词＝数字前去掉连接字（是/为/达到…）后的最后 3 个字。"""
    pairs = set()
    for m in _NUM_RE.finditer(norm_text):
        attr = norm_text[max(0, m.start() - 6):m.start()].rstrip(_NUM_LINKERS)
        pairs.add((attr[-3:], m.group()))
    return frozenset(pairs)


def dedup(cands: list[dict]) -> list[dict]:
    """返回被判重的候选列表（就地打 dup_of 标）。main 优先于 supplement 存活。

    两级判重（I-019：0.92 相似度五本书零命中，「短句被长句包含」全放行）：
    1. 包含：规范化后是已存活条目的子串（信息已被长句覆盖）；
    2. 相似：SequenceMatcher > 0.85。
    数值句守门（I-021：「魔抗值是6」被判「魔法值是6」重复）：两句都含数字时
    先比（属性词, 数值）对，互不包含（属性或数值对不上）就不判重复——
    游戏面板类短句结构全同、只差属性名，纯字符相似度会互撞。
    """
    def norm(text: str) -> str:
        return re.sub(r"[^\w]", "", text)  # 判重用强归一化：剥掉全部标点空白

    order = sorted(range(len(cands)),
                   key=lambda i: (0 if cands[i].get("origin", "main") == "main" else 1, i))
    kept: list[int] = []
    dropped = []
    for i in order:
        ni = norm(cands[i]["text"])
        pi = _numeric_pairs(ni)
        dup_against = None
        for j in kept:
            nj = norm(cands[j]["text"])
            if pi:
                pj = _numeric_pairs(nj)
                if pj and not (pi <= pj or pj <= pi):
                    continue  # 数值句守门：签名互不兼容，是不同事实
            if (len(ni) >= 6 and ni in nj) or ni == nj \
                    or difflib.SequenceMatcher(None, ni, nj).ratio() > 0.85:
                dup_against = j
                break
        if dup_against is None:
            kept.append(i)
        else:
            cands[i]["dup_of"] = cands[dup_against]["text"]
            dropped.append(cands[i])
    return dropped


# ---------- 编排 ----------

def run_pipeline(segs: list[dict], main_cands: list[dict], cfg: dict,
                 stages: list[str] | None = None, on_call=None) -> dict:
    """跑质检管线。main_cands 是主抽产出（C3 形态，带 seg）。

    返回 report：candidates（存活）＋removed（被毙，带原因）＋calls（逐次调用账）＋counts。
    """
    stages = stages or ALL_STAGES
    extractor = cfg["model_id"]
    checker = cfg.get("checker_model_id") or extractor
    seg_by_id = {s["seg"]: s for s in segs}
    calls: list[dict] = []

    def record(stage, seg_no, model_id, result):
        row = {"stage": stage, "seg": seg_no, "model": model_id,
               "seconds": result["seconds"], "usage": result.get("usage", {})}
        calls.append(row)
        if on_call:
            on_call(row)

    errors: list[str] = []

    def guarded(stage, seg_no, fn):
        """单段调用失败重试一次（坏 JSON 常是偶发），仍失败记错误账不炸管线。"""
        last = None
        for _ in range(2):
            try:
                return fn()
            except RuntimeError as e:
                last = e
        errors.append(f"{stage}·段{seg_no}: {last}")
        row = {"stage": stage, "seg": seg_no, "model": "-", "seconds": 0,
               "usage": {}, "error": str(last)[:200]}
        calls.append(row)
        if on_call:
            on_call(row)
        return None

    cands = []
    for c in main_cands:
        cands.append({**c, "origin": c.get("origin", "main")})

    counts = {"main": len(cands)}

    if "anchor" in stages:
        for c in cands:
            seg = seg_by_id.get(c.get("seg"))
            if seg:
                anchor_candidate(seg, c)
            else:
                c["quote_status"] = "no_seg"
        counts["anchor"] = {
            s: sum(1 for c in cands if c.get("quote_status") == s)
            for s in ("exact", "exact_after_norm", "fuzzy", "missing", "no_seg")}

    if "supplement" in stages:
        added = []
        for seg in segs:
            seg_cands = [c for c in cands if c.get("seg") == seg["seg"]]
            r = guarded("supplement", seg["seg"],
                        lambda s=seg, sc=seg_cands: supplement_segment(s, sc, cfg, checker))
            if r is None:
                continue
            record("supplement", seg["seg"], checker, r)
            for item in r["items"]:
                anchor_candidate(seg, item)
                added.append(item)
        cands.extend(added)
        counts["supplement_added"] = len(added)

    if "verify" in stages:
        # 交叉审计：主抽（豆包产）由 checker 查；补漏（checker 产）由主抽模型查
        for seg in segs:
            for origin, model_id in (("main", checker), ("supplement", extractor)):
                batch = [c for c in cands if c.get("seg") == seg["seg"] and c.get("origin") == origin]
                if not batch:
                    continue
                r = guarded(f"verify_{origin}", seg["seg"],
                            lambda s=seg, b=batch, m=model_id: verify_segment(s, b, cfg, m))
                if r is None:
                    continue
                record(f"verify_{origin}", seg["seg"], model_id, r)
        counts["verify"] = {
            s: sum(1 for c in cands if c.get("verify") == s)
            for s in ("support", "fixable", "unsupported", "unreviewed")}

    if "denoise" in stages:
        for seg in segs:
            batch = [c for c in cands
                     if c.get("seg") == seg["seg"] and c.get("verify") != "unsupported"]
            if not batch:
                continue
            r = guarded("denoise", seg["seg"],
                        lambda s=seg, b=batch: denoise_segment(s, b, cfg, checker))
            if r is None:
                continue
            record("denoise", seg["seg"], checker, r)
        counts["denoise_dropped"] = sum(
            1 for c in cands if c.get("keep") is False and not c.get("needs_review"))
        counts["denoise_flagged"] = sum(
            1 for c in cands if c.get("keep") is False and c.get("needs_review"))

    removed = []
    alive = []
    for c in cands:
        if c.get("verify") == "unsupported":
            removed.append({**c, "removed_by": "verify"})
        elif c.get("keep") is False and not c.get("needs_review"):
            removed.append({**c, "removed_by": "denoise"})
        else:
            # I-020：needs_review 优先——挂着修正建议待人审的条目去噪不得剔除，
            # 去噪意见改挂 denoise_flag 保留在存活账里，人审时一起看，账只有一份。
            if c.get("keep") is False:
                c["denoise_flag"] = c.get("keep_reason", "去噪判不值得入长期账")
            alive.append(c)

    if "dedup" in stages:
        for c in dedup(alive):
            removed.append({**c, "removed_by": "dedup"})
        alive = [c for c in alive if "dup_of" not in c]
        counts["dedup_dropped"] = sum(1 for r in removed if r["removed_by"] == "dedup")

    counts["final"] = len(alive)
    return {"stages_run": stages, "extractor_model": extractor, "checker_model": checker,
            "counts": counts, "calls": calls, "errors": errors,
            "candidates": alive, "removed": removed}


def format_receipt(report: dict) -> str:
    """抽取质量小票：透明但不啰嗦。"""
    c = report["counts"]
    lines = ["── 抽取质量小票 ──"]
    lines.append(f"主抽候选 {c['main']} 条")
    if "anchor" in c:
        a = c["anchor"]
        ok = a.get("exact", 0) + a.get("exact_after_norm", 0)
        lines.append(f"引文回填：{ok} 条逐字命中，{a.get('fuzzy', 0)} 条模糊修正，{a.get('missing', 0)} 条找不到原文")
    if "supplement_added" in c:
        lines.append(f"补漏：补出 {c['supplement_added']} 条")
    if "verify" in c:
        v = c["verify"]
        lines.append(f"验真：{v.get('support', 0)} 条通过，{v.get('fixable', 0)} 条带修正建议（待你裁决），"
                     f"{v.get('unsupported', 0)} 条原文不支持（已剔除），{v.get('unreviewed', 0)} 条漏判待人看")
    if "denoise_dropped" in c:
        flagged = f"（另 {c['denoise_flagged']} 条待人审保留，去噪意见已挂条上）" if c.get("denoise_flagged") else ""
        lines.append(f"去噪：滤掉 {c['denoise_dropped']} 条流水账{flagged}")
    if "dedup_dropped" in c:
        lines.append(f"去重：合并 {c['dedup_dropped']} 条重复")
    lines.append(f"最终入账候选 {c['final']} 条")
    n_calls = len(report["calls"])
    total_s = round(sum(r["seconds"] for r in report["calls"]), 1)
    lines.append(f"（质检调用 {n_calls} 次，共 {total_s} 秒）")
    return "\n".join(lines)
