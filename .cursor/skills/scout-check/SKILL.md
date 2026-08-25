---
name: scout-check
description: >
  施工护栏（不是主菜）：帮你把已定任务跑完、少跑偏。
  用户说「探路」「探路模式」「自检」「自检模式」「自检skill」时启用。
  主目标＝执行并交付任务产物；四段护栏穿插在干活里；Challenge 只占回传一小角。
  禁止把本 skill 当成「只写自检报告」或用长 Challenge 顶替交件／Notion 回传。
  Task 子 agent 的 model 必须与主会话 slug 逐字相同；Cursor Grok 4.6 extra high／口语「4.6 xhigh」→ cursor-grok-4.6-xhigh（禁止加 -fast）；旧界面 Cursor Grok 4.5 → cursor-grok-4.5-high；禁止偷跑 fable/其它族。
  方案多角辩论仍用 composer-team / cursor 团队。
---

# 探路｜自检（同一 skill）

施工护栏，用来**更好地执行任务**。不是辩论团，也不是「交一份自检报告就算完工」。

## 🔥 子 agent 模型（最高优先级，先于一切派发）

> **CZ 2026-07-14 钉死**：探路／自检只要派 `Task`，`model` 必须与主会话 slug **逐字相同**；**禁止偷跑别的模型**。

| 主会话（界面名） | Task 必须写的 `model` | ❌ 禁止写成 |
| --- | --- | --- |
| Cursor Grok 4.6／口语「4.6 extra high」「4.6 xhigh」 | **`cursor-grok-4.6-xhigh`** | `cursor-grok-4.6-xhigh-fast`（带 fast）、`cursor-grok-4.5-high`、任何 fable／claude、`composer-*`、漏写 `model` |
| Cursor Grok 4.5／口语「Grok 4.5 high」 | **`cursor-grok-4.5-high`** | `claude-fable-5-thinking-medium`、任何 fable／claude、`composer-*`、`grok-4.5-xhigh`、`grok-4.5-high`、漏写 `model` |
| Composer 2.5 | `composer-2.5` | `composer-2.5-fast` 或其它族 |
| Composer 2.5 Fast | `composer-2.5-fast` | `composer-2.5` 或其它族 |

- 每次 `Task` **必须显式传 `model`**，不得省略指望平台默认。
- 探路子 agent、定点核对、Challenge 红队：**同一条禁令**，无一例外。
- 写错模型＝本 skill **执行失败**；先改参再派，不得用错模型输出充数。

## 防误解（先读）

| ❌ 误解 | ✅ 正解 |
| --- | --- |
| 喊「自检」＝本轮主产物是四段自检文 | 主产物仍是用户要的活（脚本／实验／Notion 页…） |
| Challenge 要写很长、当回传中心 | Challenge＝收工前短挑刺；回传里**一小角**即可 |
| 自检过了、本地有文件＝已回传 | 用户要 Notion／对外交件时：**活干完必须上传／指路**，别停在本地 |
| 「自检skill」可以只做护栏不干活 | 护栏穿插在执行里；**重点仍是执行** |

一句话：探路／定点／偏航／Challenge 是安全带，车还是要开到目的地。

## 口令（显式才进）

命中任一即启用（可带「模式」／「skill」）：

- `探路` / `探路模式`
- `自检` / `自检模式` / `自检skill`
- 可与执行连说，如「自检 执行」「自检skill，把 XX 做完」→ **先护栏、主线仍是做完 XX**

模糊说法（「看看」「注意点」）**不进入**。

**触发词只负责开门，不改变四段都要跑；也不把「写自检」升级成主任务。**

与 `composer-team`（cursor 团队）分工：

| | 本 skill | composer-team |
| --- | --- | --- |
| 干什么 | 干活时防跑偏 | 拍板前多角对质 |
| 子 agent | 默认很少（探路 + 关键点 + Challenge） | 默认三轮满编 |
| 何时用 | 已定方向，要动手 | 方向未定，要辩论 |
| 对用户怎么回 | **先说交付了什么**；护栏／Challenge 附后 | 方案对质纪要 |

## 声明（进门先打一行）

```text
> 探路｜自检 ｜ 护栏四段穿插执行（非主菜）｜ 任务：<一句话交付>
```

## 主线：执行 → 交件

在四段之外，主 agent 必须自己盯住：

1. **本轮最小交付**是什么（探路第 3 句写下的那个）
2. 护栏挡住的只停相关刀，**不**改成另写长报告充数
3. 收工对用户：先交件清单（路径／链接／Notion 入口），再附极短 Challenge 裁决
4. 若任务惯例含 Notion／对外页：本地跑通后**马上回传上传**，不要等用户追问「给 Notion 了吗」

```text
【交付】（主菜，必有）
- 做了：…
- 放哪：本地 … ｜ Notion …
- 未做／未闭合：…（若有）

【Challenge】（配菜，短）
- 攻击一句 + 裁决一句 × 几条
```

## 四段（全跑，穿插在干活里，不可跳）

```text
① 探路 → ② 定点检查 → ③ 偏航提醒 → ④ Challenge
```

四段产出默认**短**：方便自己不跑偏；不是给用户的主阅读材料。

### ① 探路（动文件 / 大改之前）

**未完成探路，禁止大改、禁止新建平行工具台、禁止覆盖正式资产。**

只回答三句：

1. 工作区根目录 / 该进哪个入口？
2. 已有工具、网页、资产能不能复用？（列路径）
3. 本轮最小交付是什么？什么明确不做？

默认派 **1～2 个只读子 agent** 扫目录/入口文档；主 agent 汇总后**立刻动手执行交付**，不要停在探路段扩写。

探路产出格式：

```text
【探路】
- 入口：…
- 可复用：…
- 本轮交付：…
- 明确不做：…
```

### ② 定点检查（关键位置必须停）

碰到 [reference/checkpoints.md](reference/checkpoints.md) 里的点，**先停再动**：

1. 对照清单勾选
2. 需要时派 **1 个子 agent** 只核这一点（别开满编）
3. 主 agent 写一行：`【定点】<点名>｜通过/挡住｜一句理由` 再继续

禁止：跳过定点闷头改；定点不过还继续扩 scope。

### ③ 偏航提醒（干了一段之后）

触发（满足任一）：

- 完成 1 个 Todo 块
- 本轮已改 ≥3 个文件
- 用户连续说「继续」满 2 次

主 agent **自己说一句**（默认不派子 agent）：

```text
【偏航检查】当前交付 vs 原目标：…｜下刀是补齐还是扩 scope？
```

只有明显跑偏（新开平行方案、改无关目录、发明已有能力）才加派 1 个子 agent 挑刺。

### ④ Challenge（收工前必做，但是配菜）

未做 Challenge，**禁止**对用户说「做完了 / 可以收工」。

但 Challenge **不是**回传主体：

- 派 **1 个子 agent**（红队）短攻：缺证据／再发明／撑不住（每块尽量 ≤5 条）
- 主 agent 逐条：`采纳 / 不采纳` + 一句理由
- 对用户最终答复里：Challenge **压缩成一小段**；前面必须先有【交付】
- 若 Challenge 揭出「交件没上传／Notion 没回传」→ **先补交件**，再宣称收工

```text
【Challenge】
- 攻击：…
- 裁决：采纳/不采纳 — …
【交付】…   ← 若还没写，先写这个；Challenge 不能单独收工
```

## 子 agent 用法（保持好调）

- 用 Cursor `Task` 并发；**先看上文「🔥 子 agent 模型」**：`model` 与主会话 slug 逐字相同（Grok 4.6 extra high → `cursor-grok-4.6-xhigh`，禁止加 `-fast`；旧 4.5 → `cursor-grok-4.5-high`；有 `-fast` 就全员有，没有就不要加）
- 默认总量 **0～3 个/整轮任务**，不是 6+6+3
- 每个子 agent prompt 写清：`你只负责 X，不要发散`
- 写盘默认仅工作区 `temp/` / `TEMP/`；改正式源码/资产前要过定点

## 硬禁令

1. 因触发词偏科（只探路或只自检、不执行交付）＝执行失败  
2. 探路未完就大改 / 新建平行工具台＝执行失败  
3. 跳过 Challenge 宣称做完＝执行失败  
4. **用长自检／长 Challenge 顶替交件，或本地做完却不按任务惯例回传 Notion**＝执行失败  
5. 用本 skill 冒充 cursor 团队满编辩论＝应改口令去 `composer-team`  
6. **Task 偷跑错模型**（含 Grok 主会话却派 fable／claude／composer）＝执行失败

## 参考

- 定点表：[reference/checkpoints.md](reference/checkpoints.md)

## 变更

- 2026-08-13：CZ 钉——Grok 4.6 extra high／口语「4.6 xhigh」派发 slug＝`cursor-grok-4.6-xhigh`，**不用 fast**；禁止写成 `cursor-grok-4.6-xhigh-fast`。旧 4.5 仍映射 `cursor-grok-4.5-high`。
- 2026-07-14：CZ 钉——顶部「🔥 子 agent 模型」；当时 Grok 派发 slug＝`cursor-grok-4.5-high`；禁止偷跑 fable／其它族；硬禁令第 6 条。
- 2026-07-11：CZ 纠偏——自检＝护栏助执行；Challenge 仅为回传一小角；交件／Notion 回传优先于自检文。
