"""M7 一致性体检：全书扫矛盾（人名称谓/时间线/设定/事项互斥），只读事实账。

吃 contracts/C4_FACT_QUERY.md（store.facts 全量，rejected 不参与体检），
吐 contracts/C6_HEALTH_REPORT.md（conflicts / insufficient / alias_hints 三账分开）。

工作方式：1352 条两两比对不可行，先机械分组（实体名挖掘＋时间线＋兜底，不花调用），
每组打包一次模型调用（走 M3 的 call_json 通道）问「这批陈述里有没有互相矛盾」，
最后合并去重、按事实状态分层——真值矛盾 ≠ 候选矛盾，报告永远分开说。

三条判定纪律（旧设计打捞采信，CZ 2026-08-13）：
- 材料不足 ≠ 内容矛盾：insufficient 单独一账，不混进矛盾；
- 灯和说明分开：severity 只管红/黄；为何亮、证据、下一步各有字段；
- 别名不自动合并：疑似同一实体只进 alias_hints 提示，不算矛盾。
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter

from mvp import extract as ex
from mvp import store

# ── 分组参数（模块内常量；调它们不碰 config.json）────────────────────
MAX_ENTITY_GROUPS = 6     # 每本书最多单独扫几个实体
MIN_ENTITY_FACTS = 4      # 实体至少牵到几条事实才值得单独一组
MIN_DF = 3                # 实体名至少出现在几条事实里才算候选
MAX_FACTS_PER_CALL = 110  # 单次调用最多打包多少条事实
CHUNK_OVERLAP = 15        # 大组切块时相邻块的重叠条数
SUBSET_SKIP = 0.85        # 一组的事实被某个已排组覆盖到该比例就不再单独扫
MAX_CALLS = 14            # 单本书调用数安全上限，超出的组记 skipped
MAX_ALIAS_HINTS = 8       # 疑似同一实体提示条数上限
QUOTE_CLIP = 60           # 打包给模型时引文截断长度（报告里的证据不截）

KINDS = ("naming", "timeline", "setting", "event")
KIND_LABEL = {
    "naming": "人名/称谓",
    "timeline": "时间线",
    "setting": "设定",
    "event": "事项互斥",
}
LAYER_LABEL = {
    "confirmed": "真值层",
    "mixed": "候选顶撞真值",
    "candidate": "候选层",
}


def _id_sort_key(f: dict) -> int:
    fid = str(f.get("id") or "")
    m = re.fullmatch(r"f(\d+)", fid)
    return int(m.group(1)) if m else 10**9

# 含这些字符的字串不可能是想单独立组的实体名（功能字/代词/语气字）
_STOP_CHARS = set(
    "的了着过是在不没与就都被把对从到之其此你我他她它您谁吗呢吧啊呀哦嘛么"
    "也又还再且或而及等以为使让给跟同像若如很太更最刚才将正要会能可当个和只"
)
# 差异字是方位/结构字的对子（账本纸/账本上）不是名字变体
_NON_NAME_DIFF = set("上下里外中内间处旁边面头口底顶")
# 由干净字组成、但本身是叙事常用词的整词黑名单
_STOP_GRAMS = set("""
时候 时间 事情 东西 地方 声音 感觉 心里 心中 身上 身后 身前 手中 眼中 面前 眼前 脑海
现在 已经 开始 知道 觉得 认为 表示 发现 出现 突然 忽然 顿时 随后 接着 然后 于是
立刻 立即 马上 直接 出来 起来 下来 过去 回来 进来 看到 听到 想到 感到 受到 遇到
找到 见到 来到 走到 得到 准备 决定 打算 继续 离开 回到 进入 走进 拿出 放下 抬头
低头 转身 转头 回头 起身 点头 摇头 微笑 笑道 说道 问道 答道 喊道 叫道 开口 沉默
皱眉 目光 眼神 脸色 神色 表情 语气 双手 双眼 双腿 两人 三人 众人 所有 全部 整个
一切 如今 此时 此刻 当时 今天 明天 昨天 晚上 早上 中午 下午 上午 深夜 半夜 凌晨
清晨 傍晚 夜里 白天 每天 瞬间 刹那 片刻 因此 所以 可能 应该 必须 需要 能够 无法
只能 只见 大家 咱们 什么 怎么 为何 如何 任何 何况 哪里 这里 那里 这样 那样 这么
那么 如此 一样 同样 一般 一些 有些 有点 一点 一下 一次 一起 一边 一声 一口 一手
一眼 心想 心道 想着 看着 听着 说着 笑着 走着 站着 坐着 躺着 似乎 仿佛 好像 果然
居然 竟然 显然 确实 真正 非常 十分 特别 尤其 甚至 几乎 差点 终于 总算 刚刚 赶紧
连忙 急忙 慢慢 渐渐 逐渐 越来 越发 更加 一直 始终 从来 从未 曾经 正在 依然 仍然
依旧 明白 清楚 完全 彻底 根本 原来 原本 本来 后来 之后 之前 以后 以前 以来 至于
对于 关于 由于 毕竟 究竟 到底 反正 其实 当然 自然 或许 也许 大概 恐怕 万一 一旦
希望 担心 害怕 惊讶 愤怒 高兴 开心 难过 痛苦 自己 别人 有人 无人 没人 女人 男人
孩子 名字 问题 消息 情况 结果 办法 样子 意思 关系 心情 力气 周围 附近 旁边 中间
上面 下面 里面 外面 前面 后面 左右 内心 全身 浑身 脸上 头上 手里 屋里 家里 房间
门口 窗外 街上 路上 城中 城外 忍不住 不由得 情不自禁 迫不及待 小心翼翼 无缘无故
""".split())
_DIGIT_CHARS = set("0123456789零〇一二两三四五六七八九十百千万亿第")

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
_TIME_PAT = re.compile(
    r"[0-9〇零一二两三四五六七八九十百千几半]+\s*"
    r"(?:年|个月|月|日|号|天|夜|岁|时辰|更|旬|载|分钟|小时|周|星期)"
    r"|次日|翌日|昨日|前日|明日|当晚|当夜|当天|当日|清晨|黎明|黄昏|傍晚"
    r"|正午|午后|午时|深夜|半夜|凌晨|三更|五更|开春|入冬|年前|年后|月初|月底"
)

CHECK_INSTRUCTIONS = (
    "你是小说一致性体检员。输入是同一本小说里的一批事实陈述"
    "（每行：编号|章节|陈述|原文依据），按故事先后排列。\n"
    "任务：只在这批陈述内部找互相矛盾的地方，四类：\n"
    "- naming 人名/称谓不一致：同一人物的名字写法前后冲突（如 周淑芬/周淑兰），或称谓指代错乱\n"
    "- timeline 时间线冲突：时间顺序、年龄、日期、时段互相对不上\n"
    "- setting 设定矛盾：身份、能力、规则、物品状态等与先前确立的设定打架\n"
    "- event 事项互斥：同一件事被无解释地推翻（先说A后说非A）\n"
    "判定纪律：\n"
    "- 只看给出的陈述，不引入书外知识，不脑补书里没写的解释\n"
    "- 正常剧情推进不算矛盾：受伤后痊愈、改变主意、修为提升、局势变化都是发展\n"
    "- 同一人物换用大名/官职/绰号不算矛盾，除非写法冲突或指代错乱\n"
    "- 两条陈述可能矛盾、但仅凭这批材料判不死的 → verdict 填 insufficient，不硬判\n"
    "- hard 只在铁矛盾时为 true：同一事项被无解释推翻、明说的设定被违反\n"
    "- 同一个问题只报一条，把涉及的编号都放进 fact_ids，不拆成多条\n"
    '只输出 JSON：{"findings":[{"fact_ids":["f001","f002"],'
    '"kind":"naming|timeline|setting|event","verdict":"conflict|insufficient",'
    '"hard":false,"confidence":"high|low","note":"一句话说明哪里打架"}]}\n'
    '没有发现就输出 {"findings":[]}'
)


# ── 第零步：账本完整性预检（机械，不花调用）─────────────────────────

def _loc(f: dict) -> dict:
    return {"chapter_id": f["chapter_id"], "seg": f.get("seg"), "text": f["text"][:40]}


def _dedupe_ids(facts: list[dict]) -> tuple[list[dict], list[dict]]:
    """C4 说事实号项目内唯一；账本违约（并发入账/重抽事故）时体检只认
    每个号首次出现的那条，副本整理成完整性问题单独报——这是数据事故，
    不能混进小说矛盾，更不能把两条不同事实当同一条喂给模型。"""
    seen: dict[str, dict] = {}
    dups: dict[str, list[dict]] = {}
    for f in facts:
        if f["id"] in seen:
            dups.setdefault(f["id"], []).append(f)
        else:
            seen[f["id"]] = f
    records = [
        {"problem": "duplicate_id", "id": i, "kept": _loc(seen[i]),
         "dropped": [_loc(f) for f in fs]}
        for i, fs in dups.items()
    ]
    return list(seen.values()), records


# ── 第一步：机械挖实体名（不花调用）──────────────────────────────

def _gram_ok(g: str) -> bool:
    return (
        g not in _STOP_GRAMS
        and not (set(g) & _STOP_CHARS)
        and not (set(g) & _DIGIT_CHARS)
    )


def _mine_names(facts: list[dict], min_df: int) -> dict[str, int]:
    """事实句里挖高频 2–4 字词 → {词: 出现的事实条数}。只是候选，junk 由上层再筛。"""
    df: Counter = Counter()
    for f in facts:
        seen = set()
        for run in _CJK_RUN.findall(f["text"]):
            for n in (2, 3, 4):
                for i in range(len(run) - n + 1):
                    seen.add(run[i : i + n])
        df.update(g for g in seen if _gram_ok(g))
    return {g: c for g, c in df.items() if c >= min_df}


def _pick_entities(cand: dict[str, int]) -> list[str]:
    """长词优先去包含（「李星燃」在就不要「星燃」），按出现条数取前几名。"""
    kept: list[str] = []
    for g in sorted(cand, key=lambda x: (-len(x), -cand[x])):
        covered = any(
            g in longer and cand[longer] >= cand[g] * 0.8 for longer in kept
        )
        if not covered:
            kept.append(g)
    return sorted(kept, key=lambda x: -cand[x])[:MAX_ENTITY_GROUPS]


def _alias_pairs(cand: dict[str, int]) -> list[tuple[str, str]]:
    """疑似同一实体：等长（≥3字）、恰好差 1 字、首字相同。只提示，不合并判定。

    三道降噪闸：
    - 频次闸：两边都低频（<2×MIN_DF）的多是切词碎片，不提示；
    - 前缀闸：末字不同时，真名字变体（沈织宁/沈织岳）加起来撑得起共同前缀
      出现量的大头，「名字＋动词」碎片（刘瑁说/刘瑁看）只占零头；
      前缀本身是功能词（自己X/脸上X）的直接不要；
    - 回声闸：同一对差异字（卫/新）只报频次最高的一对，
      不让「周卫军看≈周新军看」跟在「周卫军≈周新军」后面复读。
    """
    buckets: dict[tuple[int, str], list[str]] = {}
    for g in sorted(cand, key=lambda x: -cand[x]):
        if len(g) >= 3:
            buckets.setdefault((len(g), g[0]), []).append(g)
    raw = []
    for names in buckets.values():
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                diff = [k for k, (x, y) in enumerate(zip(a, b)) if x != y]
                if len(diff) != 1:
                    continue
                if {a[diff[0]], b[diff[0]]} & _NON_NAME_DIFF:
                    continue
                if max(cand[a], cand[b]) < 2 * MIN_DF:
                    continue
                if diff[0] == len(a) - 1:
                    prefix_df = cand.get(a[:-1], 0)
                    if not prefix_df or cand[a] + cand[b] < 0.75 * prefix_df:
                        continue
                raw.append((a, b, diff[0], cand[a] + cand[b]))
    raw.sort(key=lambda p: -p[3])
    seen_diff, pairs = set(), []
    for a, b, d, _ in raw:
        key = tuple(sorted((a[d], b[d])))
        if key in seen_diff:
            continue
        seen_diff.add(key)
        pairs.append((a, b))
    return pairs[:MAX_ALIAS_HINTS]


# ── 第二步：拼扫描组 ─────────────────────────────────────────

def _hits(facts: list[dict], names: list[str]) -> list[dict]:
    """名字出现在事实句或引文里都算牵涉（引文保留着原始写法，别名靠它现形）。"""
    return [
        f for f in facts
        if any(n in f["text"] or n in f.get("quote", "") for n in names)
    ]


def _chunks(members: list[dict]) -> list[list[dict]]:
    if len(members) <= MAX_FACTS_PER_CALL:
        return [members]
    step = MAX_FACTS_PER_CALL - CHUNK_OVERLAP
    out = []
    i = 0
    while True:
        out.append(members[i : i + MAX_FACTS_PER_CALL])
        if i + MAX_FACTS_PER_CALL >= len(members):
            return out
        i += step


def build_groups(facts: list[dict]) -> dict:
    """扫描计划：实体组（别名并组）→ 时间线组 → 兜底组，附带别名提示。"""
    cand = _mine_names(facts, 2)  # 低门槛挖全量，低频的名字变体才捞得着
    entities = _pick_entities({g: c for g, c in cand.items() if c >= MIN_DF})
    pairs = _alias_pairs(cand)

    # 别名对并进同一组扫（模型同屏看到两种写法才能发现 naming 冲突）
    alias_of: dict[str, list[str]] = {}
    for a, b in pairs:
        main = a if cand.get(a, 0) >= cand.get(b, 0) else b
        other = b if main == a else a
        alias_of.setdefault(main, []).append(other)

    raw_groups = []
    for name in entities:
        names = [name] + alias_of.get(name, [])
        members = _hits(facts, names)
        if len(members) >= MIN_ENTITY_FACTS:
            raw_groups.append({"name": "／".join(names), "kind": "entity", "members": members})

    # 覆盖去重：小组的事实基本都在某个大组里，就不再花一次调用
    raw_groups.sort(key=lambda g: -len(g["members"]))
    kept = []
    for g in raw_groups:
        ids = {f["id"] for f in g["members"]}
        if any(
            len(ids & {f["id"] for f in k["members"]}) >= SUBSET_SKIP * len(ids)
            for k in kept
        ):
            continue
        kept.append(g)

    t_members = [f for f in facts if _TIME_PAT.search(f["text"])]
    if len(t_members) >= 2:
        kept.append({"name": "时间线", "kind": "timeline", "members": t_members})

    covered = {f["id"] for g in kept for f in g["members"]}
    rest = [f for f in facts if f["id"] not in covered]
    if len(rest) >= 2:
        kept.append({"name": "兜底", "kind": "leftover", "members": rest})

    # 时间线/兜底同样受覆盖去重约束（输入集几乎重合就是白花一次调用）
    final = []
    for g in kept:
        ids = {f["id"] for f in g["members"]}
        if any(
            len(ids & {f["id"] for f in k["members"]}) >= SUBSET_SKIP * len(ids)
            for k in final
        ):
            continue
        final.append(g)

    # 大组切块，块按账序（章节顺序）排
    calls = []
    for g in final:
        members = sorted(g["members"], key=_id_sort_key)
        for j, chunk in enumerate(_chunks(members)):
            label = g["name"] if len(chunk) == len(members) else f"{g['name']}·块{j + 1}"
            calls.append({"name": label, "kind": g["kind"], "members": chunk})

    return {"calls": calls, "alias_pairs": pairs, "entities": entities}


# ── 第三步：一组一次模型调用 ──────────────────────────────────

def _pack(project: str, group: dict) -> str:
    lines = [
        f"《{project}》围绕「{group['name']}」的一批事实陈述，请找其中互相矛盾的地方：",
        "",
    ]
    for f in group["members"]:
        quote = f.get("quote", "").replace("\n", " ")
        if len(quote) > QUOTE_CLIP:
            quote = quote[:QUOTE_CLIP] + "…"
        lines.append(f"{f['id']}|{f['chapter_id']}|{f['text']}|{quote}")
    return "\n".join(lines)


def _scan_group(project: str, group: dict, cfg: dict) -> tuple[list[dict], dict]:
    """一次调用＋失败重试一次。返回（规范化后的 findings, usage）。"""
    user_content = _pack(project, group)
    last_err = None
    for _ in range(2):
        try:
            r = ex.call_json(CHECK_INSTRUCTIONS, user_content, cfg)
            data = r["data"] if isinstance(r["data"], dict) else {}
            return _norm_findings(data, group), r.get("usage", {})
        except RuntimeError as e:
            last_err = e
    raise last_err


def _norm_findings(data: dict, group: dict) -> list[dict]:
    """模型返回 → 只留结构合法、事实号真实存在的条目；不合格的丢弃并计数。"""
    valid = {f["id"] for f in group["members"]}
    out = []
    raw = data.get("findings", [])
    if not isinstance(raw, list):
        raw = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ids = []
        for i in item.get("fact_ids", []) or []:
            if isinstance(i, str) and i in valid and i not in ids:
                ids.append(i)
        if len(ids) < 2:
            continue  # 矛盾至少要有两方；模型编造的事实号也在这里被拦下
        out.append({
            "fact_ids": ids,
            "kind": item.get("kind") if item.get("kind") in KINDS else "event",
            "verdict": "insufficient" if item.get("verdict") == "insufficient" else "conflict",
            "hard": bool(item.get("hard")),
            "confidence": "high" if item.get("confidence") == "high" else "low",
            "note": str(item.get("note", "")).strip()[:300],
            "found_by": group["name"],
        })
    return out


# ── 第四步：合并、分灯、分层 ──────────────────────────────────

def _severity(f: dict) -> str:
    """红灯只给硬矛盾：模型判 hard 且置信高；其余（含 AI 拿不准的推断）一律黄灯。

    时间线封顶黄灯：v0 没有「故事顺序 ≠ 叙述顺序」的双序概念，倒叙/回忆
    在模型眼里全是时间冲突（两书抽查 3 条时间线红灯全是这类误报），
    证据基础撑不起硬判，一律降黄；等体检 v1 上双序再放开。
    """
    if f["kind"] == "timeline":
        return "yellow"
    if f["verdict"] == "conflict" and f["hard"] and f["confidence"] == "high":
        return "red"
    return "yellow"


def _layer(fact_ids: list[str], by_id: dict[str, dict]) -> str:
    statuses = {by_id[i]["status"] for i in fact_ids}
    if statuses == {store.STATUS_CONFIRMED}:
        return "confirmed"
    if store.STATUS_CONFIRMED in statuses:
        return "mixed"
    return "candidate"


def _next_step(layer: str, verdict: str) -> str:
    if verdict == "insufficient":
        return "材料不足：导入后续章节或回对应章·段人工核对后再判，不当矛盾处理"
    if layer == "confirmed":
        return "真值层矛盾：回对应章·段复核原文；确属笔误就在审查台改写或驳回其中一方"
    if layer == "mixed":
        return "候选与已确认真值抵触：先回原文核对该候选，确认前不要采纳"
    return "双方都还是候选：先在审查台（confirm）核对真伪；都被确认时才升级为真值矛盾"


def _evidence(fact_ids: list[str], by_id: dict[str, dict]) -> list[dict]:
    return [
        {
            "fact_id": i,
            "chapter_id": by_id[i]["chapter_id"],
            "seg": by_id[i].get("seg"),
            "status": by_id[i]["status"],
            "text": by_id[i]["text"],
            "quote": by_id[i].get("quote", ""),
        }
        for i in fact_ids
    ]


def _merge_findings(all_findings: list[dict]) -> list[dict]:
    """零唠叨：同一组事实号只留一条。conflict 压过 insufficient，红压过黄。"""
    merged: dict[frozenset, dict] = {}
    for f in all_findings:
        key = frozenset(f["fact_ids"])
        old = merged.get(key)
        if old is None:
            merged[key] = dict(f, found_by=[f["found_by"]])
            continue
        if f["found_by"] not in old["found_by"]:
            old["found_by"].append(f["found_by"])
        rank = {"conflict": 1, "insufficient": 0}
        stronger = (
            rank[f["verdict"]] > rank[old["verdict"]]
            or (f["verdict"] == old["verdict"] and _severity(f) == "red" and _severity(old) != "red")
        )
        if stronger:
            merged[key] = dict(f, found_by=old["found_by"])
    return list(merged.values())


def _merge_overlaps(findings: list[dict]) -> list[dict]:
    """零唠叨第二层：同类、同判定、事实号有交集的是同一个问题，并成一条
    （例：「f001↔f036」和「f001↔f002↔f048…」都在说陈医生/陈博学，不该各报一条）。"""
    out: list[dict] = []
    for f in sorted(findings, key=lambda x: -len(x["fact_ids"])):
        home = None
        for g in out:
            if (g["kind"] == f["kind"] and g["verdict"] == f["verdict"]
                    and set(g["fact_ids"]) & set(f["fact_ids"])):
                home = g
                break
        if home is None:
            out.append(dict(f))
            continue
        home["fact_ids"] = sorted(
            set(home["fact_ids"]) | set(f["fact_ids"]), key=lambda i: int(i[1:]))
        if len(f["note"]) > len(home["note"]):
            home["note"] = f["note"]
        home["hard"] = home["hard"] or f["hard"]
        if f["confidence"] == "high":
            home["confidence"] = "high"
        for fb in f["found_by"]:
            if fb not in home["found_by"]:
                home["found_by"].append(fb)
    return out


# ── 对外入口 ────────────────────────────────────────────────

def run_check(project: str, cfg: dict, on_group=None) -> dict:
    """全书体检 → C6 报告 dict。on_group(label, i, n) 用于编排层打进度。"""
    all_facts = store.facts(project)
    scannable = [f for f in all_facts if f["status"] != store.STATUS_REJECTED]
    n_rejected = len(all_facts) - len(scannable)
    scannable, dup_records = _dedupe_ids(scannable)
    if len(scannable) < 2:
        raise SystemExit("事实账不足 2 条，没有可体检的内容（先 extract）")

    plan = build_groups(scannable)
    calls = plan["calls"][:MAX_CALLS]
    skipped = plan["calls"][MAX_CALLS:]

    by_id = {f["id"]: f for f in scannable}
    findings: list[dict] = []
    group_log = []
    tokens = 0
    t0 = time.time()
    for i, g in enumerate(calls):
        if on_group:
            on_group(g["name"], i + 1, len(calls), len(g["members"]))
        try:
            fs, usage = _scan_group(project, g, cfg)
            findings.extend(fs)
            tokens += usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
            group_log.append({
                "name": g["name"], "kind": g["kind"],
                "facts": len(g["members"]), "status": "ok", "findings": len(fs),
            })
        except RuntimeError as e:
            group_log.append({
                "name": g["name"], "kind": g["kind"],
                "facts": len(g["members"]), "status": "failed", "error": str(e)[:200],
            })
    for g in skipped:
        group_log.append({
            "name": g["name"], "kind": g["kind"],
            "facts": len(g["members"]), "status": "skipped_budget",
        })

    merged = _merge_overlaps(_merge_findings(findings))
    conflicts, insufficient = [], []
    for f in merged:
        layer = _layer(f["fact_ids"], by_id)
        rec = {
            "kind": f["kind"],
            "layer": layer,
            "fact_ids": f["fact_ids"],
            "note": f["note"],
            "next_step": _next_step(layer, f["verdict"]),
            "evidence": _evidence(f["fact_ids"], by_id),
            "found_by": f["found_by"],
            "confidence": f["confidence"],
            "hard": f["hard"],
        }
        if f["verdict"] == "conflict":
            rec["severity"] = _severity(f)
            conflicts.append(rec)
        else:
            insufficient.append(rec)

    # 矛盾账已覆盖的问题不在材料不足账里复读（零唠叨）
    conflict_ids = {}
    for r in conflicts:
        conflict_ids.setdefault(r["kind"], []).append(set(r["fact_ids"]))
    insufficient = [
        r for r in insufficient
        if not any(set(r["fact_ids"]) & s for s in conflict_ids.get(r["kind"], []))
    ]

    sev_rank = {"red": 0, "yellow": 1}
    layer_rank = {"confirmed": 0, "mixed": 1, "candidate": 2}
    conflicts.sort(key=lambda r: (
        layer_rank[r["layer"]], sev_rank[r["severity"]], r["fact_ids"][0]))
    insufficient.sort(key=lambda r: r["fact_ids"][0])
    for i, r in enumerate(conflicts):
        r["issue_id"] = f"h{i + 1:03d}"
    for i, r in enumerate(insufficient):
        r["issue_id"] = f"n{i + 1:03d}"

    alias_hints = []
    for i, (a, b) in enumerate(plan["alias_pairs"]):
        ids_a = [f["id"] for f in _hits(scannable, [a])][:3]
        ids_b = [f["id"] for f in _hits(scannable, [b])][:3]
        alias_hints.append({
            "hint_id": f"a{i + 1:03d}",
            "names": [a, b],
            "fact_ids_a": ids_a,
            "fact_ids_b": ids_b,
            "note": "写法只差一字，疑似同一实体；程序不自动合并、不算矛盾，请作者认",
        })

    n_confirmed = sum(1 for f in scannable if f["status"] == store.STATUS_CONFIRMED)
    return {
        "contract": "C6_HEALTH_REPORT v0",
        "project": project,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": cfg["model_id"],
        "scan": {
            "facts_total": len(scannable),
            "confirmed": n_confirmed,
            "extracted": len(scannable) - n_confirmed,
            "rejected_excluded": n_rejected,
            "duplicate_dropped": sum(len(r["dropped"]) for r in dup_records),
            "api_calls": len(calls),
            "failed_calls": sum(1 for g in group_log if g["status"] == "failed"),
            "clean_groups": sum(
                1 for g in group_log if g["status"] == "ok" and g["findings"] == 0),
            "total_tokens": tokens,
            "seconds": round(time.time() - t0, 1),
            "groups": group_log,
        },
        "conflicts": conflicts,
        "insufficient": insufficient,
        "alias_hints": alias_hints,
        "integrity": {
            "duplicate_ids": dup_records,
            "note": ("同一事实号对应多条不同事实——入账事故，不是小说矛盾；"
                     "体检只认每号首次出现的那条" if dup_records else ""),
            "next_step": "回 M4 修账（重编号或重抽本书）后重跑体检才算数" if dup_records else "",
        },
        "summary": {
            "red": sum(1 for r in conflicts if r["severity"] == "red"),
            "yellow": sum(1 for r in conflicts if r["severity"] == "yellow"),
            "by_layer": {
                k: sum(1 for r in conflicts if r["layer"] == k)
                for k in ("confirmed", "mixed", "candidate")
            },
            "by_kind": {
                k: sum(1 for r in conflicts if r["kind"] == k) for k in KINDS
            },
            "insufficient": len(insufficient),
            "alias_hints": len(alias_hints),
            "duplicate_ids": len(dup_records),
        },
    }


def save_report(project: str, report: dict):
    """报告是事实账的只读投影快照，落项目目录，重跑覆盖；绝不回写 facts.json。"""
    path = store.project_dir(project) / "health_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# ── 人读输出 ────────────────────────────────────────────────

def format_plan(project: str) -> str:
    """--plan 预演：只分组不调用，让人先看钱会花在哪。"""
    scannable = [f for f in store.facts(project) if f["status"] != store.STATUS_REJECTED]
    scannable, dup_records = _dedupe_ids(scannable)
    if len(scannable) < 2:
        return "事实账不足 2 条，没有可体检的内容"
    plan = build_groups(scannable)
    lines = [f"《{project}》体检分组预演（不调用模型）：事实 {len(scannable)} 条"]
    if dup_records:
        lines.append(f"  ⚠️ 账本有 {len(dup_records)} 个重复事实号（入账事故），只认首次出现的那条")
    for g in plan["calls"]:
        lines.append(f"  [{g['kind']}] {g['name']}（{len(g['members'])} 条）")
    n = len(plan["calls"])
    lines.append(f"预计调用 {min(n, MAX_CALLS)} 次" + (f"（超上限截去 {n - MAX_CALLS} 组）" if n > MAX_CALLS else ""))
    for a, b in plan["alias_pairs"]:
        lines.append(f"  疑似同一实体：「{a}」≈「{b}」（提示，不算矛盾）")
    return "\n".join(lines)


def _fmt_issue(r: dict) -> list[str]:
    lamp = "🔴" if r.get("severity") == "red" else "🟡"
    head = f"  {r['issue_id']} {lamp} [{KIND_LABEL[r['kind']]}] " + " ↔ ".join(r["fact_ids"])
    lines = [head, f"     说明：{r['note']}"]
    for e in r["evidence"]:
        seg = f"·段{e['seg']}" if e.get("seg") else ""
        st = "真值" if e["status"] == store.STATUS_CONFIRMED else "候选"
        lines.append(f"     {e['fact_id']} [{e['chapter_id']}{seg}·{st}] {e['text']}")
        if e["quote"]:
            lines.append(f"          依据：{e['quote'][:80]}")
    lines.append(f"     👉 {r['next_step']}")
    return lines


def format_report(report: dict) -> str:
    s, sm = report["scan"], report["summary"]
    lines = [
        "",
        f"━━ 一致性体检 ·《{report['project']}》 {report['generated_at']} ━━",
        f"扫描 {s['facts_total']} 条（真值 {s['confirmed']}＋候选 {s['extracted']}；"
        f"已拒绝 {s['rejected_excluded']} 条不扫）",
        f"分组调用 {s['api_calls']} 次（失败 {s['failed_calls']}），{s['clean_groups']} 组未见问题",
        "灯的含义：🔴 硬矛盾（同一事项被无解释推翻/设定被违反）；🟡 疑似或低置信。",
    ]
    dup = report["integrity"]["duplicate_ids"]
    if dup:
        n_copies = s.get("duplicate_dropped", 0)
        lines.append(f"\n⚠️ 账本完整性：{len(dup)} 个事实号重复（{n_copies} 条副本未扫）——"
                     f"{report['integrity']['note']}")
        for r in dup[:3]:
            k, d0 = r["kept"], r["dropped"][0]
            lines.append(f"     {r['id']} 保留[{k['chapter_id']}·段{k['seg']}]{k['text'][:20]}…"
                         f"｜副本[{d0['chapter_id']}·段{d0['seg']}]{d0['text'][:20]}…")
        if len(dup) > 3:
            lines.append(f"     …等共 {len(dup)} 个号，全名单见 health_report.json")
        lines.append(f"     👉 {report['integrity']['next_step']}")
    conflicts = report["conflicts"]
    for layer in ("confirmed", "mixed", "candidate"):
        subset = [r for r in conflicts if r["layer"] == layer]
        if layer == "confirmed":
            if s["confirmed"] == 0:
                lines.append(f"\n【{LAYER_LABEL[layer]}】本书还没有已确认真值，谈不上真值矛盾")
                continue
            if not subset:
                lines.append(f"\n【{LAYER_LABEL[layer]}】未发现矛盾 ✅")
                continue
        if not subset:
            continue
        reds = sum(1 for r in subset if r["severity"] == "red")
        lines.append(f"\n【{LAYER_LABEL[layer]}】红 {reds} 黄 {len(subset) - reds}"
                     + ("——候选互相打架，先确认真伪再谈剧情矛盾" if layer == "candidate" else ""))
        for r in subset:
            lines.extend(_fmt_issue(r))
    if report["insufficient"]:
        lines.append(f"\n【材料不足待补】{len(report['insufficient'])} 条（拿不准，不算矛盾）")
        for r in report["insufficient"]:
            lines.append(f"  {r['issue_id']} [{KIND_LABEL[r['kind']]}] "
                         + " ↔ ".join(r["fact_ids"]) + f"：{r['note']}")
            lines.append(f"     👉 {r['next_step']}")
    if report["alias_hints"]:
        lines.append(f"\n【疑似同一实体】{len(report['alias_hints'])} 条（提示，不自动合并、不算矛盾）")
        for h in report["alias_hints"]:
            lines.append(f"  {h['hint_id']} 「{h['names'][0]}」≈「{h['names'][1]}」"
                         f"（例：{'、'.join(h['fact_ids_a'][:2])} vs {'、'.join(h['fact_ids_b'][:2])}）")
    if not conflicts and not report["insufficient"]:
        lines.append("\n未发现矛盾 ✅")
    failed = [g for g in s["groups"] if g["status"] == "failed"]
    for g in failed:
        lines.append(f"\n⚠️ 组「{g['name']}」调用失败未扫到：{g.get('error', '')}")
    lines.append(f"\n汇总：红 {sm['red']} 黄 {sm['yellow']}｜材料不足 {sm['insufficient']}"
                 f"｜别名提示 {sm['alias_hints']}｜用时 {s['seconds']}s")
    return "\n".join(lines)
