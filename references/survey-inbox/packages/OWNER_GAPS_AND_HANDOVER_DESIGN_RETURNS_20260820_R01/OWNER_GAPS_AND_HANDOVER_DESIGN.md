# Owner 缺口与正式交棒设计

- 身份：`ADVISORY_OWNER_DESIGN_ONLY`
- 日期：2026-08-20
- 来源包：`01_REMAINING_GAPS_SHARED_PACKAGE.zip`
- 权限：不写产品代码，不调用 API，不生成 Gold，不改变正式合同、R13、训练、生产或作者真值
- 完整读取：247 个成员已逐文件打开；`SHA256SUMS` 246/246 对平，缺失 0、错配 0

## 结论

✅ **四组 owner 可以收成一条清楚的分工：**

1. **M8 的稳定规划身份和最终选择落账都归 planstore。** M8 只提出候选；C7 是只读展示快照；selection action builder 只组命令；planstore 负责 AC／OPT 发号、完整 option record、stop point 校验和规划消化。
2. **工作稿先在 AuthorWorkspace 变成合法章节，再由 planstore 消费现成 chapter ID。** C10 source、C11 INITIAL、C1 current 必须先完成；planstore 不能再接收工作稿全文、标题并自己发章号。
3. **M10 不拥有人物状态或故事时间真值。** 人物阶段读取面和故事时间轴各有上游 owner；planstore 只保存计划 scene/event 对稳定时间锚的引用；M10 只组装可重建 binding projection，继续调用现有 interval resolver 做唯一命中。
4. **M11 的真实 recall handle 归绑定作者的 AuthorWorkspace 解析。** 源材料 owner 声明“回取什么”；AuthorWorkspace mint／validate／resolve 不透明句柄；M11 只在打包前验证。作者页继续只显示安全序号。
5. **INITIAL 章节标题仍需 CZ 选择。** 当前没有独立、已确认的章节标题 owner；`slot.title_hint` 明确不是实际标题，C10 的 `TITLE` 也不是章节标题。推荐把作者确认标题直接放进 handover action 的下一版本，但本报告不替 CZ 冻结。

🔥 核心不是多建几本账，而是把这句话落实：**谁拥有长期身份，谁才有权发号和判 current；读取模块只拿带版本水位的结果，不自己补真值。**

## 取材与权威顺序

本设计按下面顺序判断：

1. 本窗 Prompt；
2. `01_current_truth/.../LOCAL_CURRENT_REBASE_R01.md`；
3. `02_current_route/novel-mvp/contracts/` 正式合同；
4. 当前代码与直接测试；
5. 原子预期；
6. `04_external_reviews/` 仅作建议和反例。

当前回归是 1184/1184，Ruff 与 `git diff --check` 通过；这只证明机械回归，不证明内容质量或 owner 缺口已经关闭。当前 rebase 已明确：M10 区间唯一命中和 M11 作者安全序号已关闭，不能重做；仍开放的是长期 owner、正式交棒和 handle 生命周期。

---

## 一、对象 owner 总表

### M8：规划卡、选项、停点和选择

| 对象 | 谁创建 | 谁保存 | 谁读取 | 谁能改 | current／stale |
|---|---|---|---|---|---|
| 稳定 planning card | M8 提交候选；planstore 校验后发 `AC-*` | planstore | M8、C7、action builder、consumer、审计 | 只有 planstore，rev +1 | 最新 card rev 且所引规划对象 rev current；旧 rev 可审计但 stale。已有该 rev 的终局 option record 后不再 selectable |
| 完整选项源 | 与稳定 card 同时创建 | planstore planning card prototype | C7 投影、action builder | 只有 planstore | 跟 card rev 同生共失；不能从 C7 短标签反推 |
| C7 v1 | M8 从 current card／事实／意图投影 | 短命输出；可保存结果但不是规划真源 | 作者、action builder | 不修改；来源变化后重出 | 完整 C7 SHA、card rev、来源 refs 均 current 才可选 |
| `C7_SELECTION_ACTION v1` | action builder | 默认不进入 plan.json | planstore consumer | 不可修改；变化后重建 | 只在消费瞬间 current；任一绑定 rev、SHA、stop point 变化即 stale |
| `option_record` | builder 组候选；planstore 写前校验后真正创建 | planstore | M8、审计、历史读取 | 只有 planstore；不静默覆盖 | 它是历史决定，不是当前推荐；规划效果是否仍 current 看后续对象与 history |
| `stop_points` | 作者设置 | planstore／设置模块 | action builder、planstore consumer 等只读 | 作者通过设置模块改 | 读取时绑定 plan 水位；未知值不补默认。现有正式信息只足以支持 P1 `auto_pass` 和 P3 不可绕过等窄门 |

**推荐 owner 形状：** 在 planstore 内增加 prototype `planning_cards[]` 和 `id_counters.AC`。每张卡保存完整选项：

```text
key / summary / why_fit / changes / risks / digest_refs / reveal_intent
```

其中前六项复用正式 `option_record.options[]`；`reveal_intent` 只服务 C7 展示。C7 继续只显示 `{id, label, reveal_intent}`，选择时由 builder 回到 planstore 读完整源，不事后编造。

⚠️ `planning_cards[]`、`id_counters.AC` 和 selection provenance receipt 目前都只能叫 **prototype**。现行 `PLAN_LEDGER_STORAGE.md` 没有这些顶层字段，不能在施工时顺手改成“正式已冻结”。

### 工作稿正式交棒

| 对象 | 谁创建 | 谁保存 | 谁读取 | 谁能改 | current／stale |
|---|---|---|---|---|---|
| `WRITING_DESK_WORK_DRAFT` | 作者写作区 | AuthorWorkspace `draft` | 写作区、检测、handover admission | 工作稿 owner；`work_rev +1` | 只有 current work rev 可普通交棒；旧 rev stale |
| controlled raw source | C11 INITIAL admission coordinator 从 current work exact UTF-8 bytes 创建 | AuthorWorkspace immutable `raw_upload`，并由 `input_manifest` 引用 | C10/C11 replay、审计 | 不可覆盖 | receipt、size、SHA 与 exact bytes 对上才有效 |
| C10 material unit | admission coordinator | AuthorWorkspace 受限 C10 owner store | C11、审计 | identity revision 只追加 | 交棒时引用的 identity rev 必须仍为 `CONFIRMED + CHAPTER`，source span 可逐字回放 |
| C11 ledger | C11 owner | AuthorWorkspace chapter revision store | C1、M2、planstore handover bridge、事实消费者 | 只有 C11 writer；只追加 revision | `current_revision_no` 等于最后一项；旧 revision 保留但不是 current |
| C1 v1 | C11 current 物化器 | AuthorWorkspace `chapters` | M2、展示、planstore bridge | 不能独立改；随 C11 current 重物化 | `chapter_revision_ref`、title、text、SHA 必须等于 C11 current |
| handover operation | coordinator | AuthorWorkspace operation store | 恢复扫描、planstore bridge | 只允许阶段迁移 | `AW_COMMITTED_PLANSTORE_PENDING` 或 `HANDOVER_COMPLETE`；receipt/SHA 不闭合则手工恢复 |
| slot mapping／handover parts | planstore consumer | planstore | 开章、战报、后续规划 | 只有 planstore | 必须绑定已有 stable chapter ID；slot／outline／chapter ref 变化后旧 pending 不能静默继续 |

### M10：人物阶段、故事时间与 binding

| 对象 | 谁创建 | 谁保存 | 谁读取 | 谁能改 | current／stale |
|---|---|---|---|---|---|
| character state timeline projection | `CHARACTER_STATE_TIMELINE_OWNER` 从 current confirmed C4／AUTHOR_ATTESTATION 生成 | 物理复用 AuthorWorkspace `state` domain | M10、M8、M11、检查器 | 只能通过上游真值变化重建 | source ref/revision/SHA 全 current、同 entity+state_key 区间无歧义才 current |
| story-time axis | `STORY_TIME_AXIS_OWNER` | AuthorWorkspace state/time domain | planstore binding、M10、检查器 | 只有时间轴 owner，需作者权力的决定回作者 | axis rev、anchor 次序和来源决定 current；自然语言 hint 不能冒充 |
| planned scene/event time binding | 作者/M8 提案，planstore 校验落盘 | planstore | M10、M8、M11 | 只有 planstore | scene/event rev 与 axis rev 都 current 才有效 |
| M10 binding projection | M10 binding reader | 默认可重建；保存时沿用 scene export workspace | adapter、exporter | M10 只重编译 | 真实依赖的 plan/state/time/entity 水位全部一致才 current |
| interval resolver result | 现有纯函数 | 不保存真值 | M10 projection | 不修改 | 对显式半开区间唯一包含才成功；zero/multi/overlap 失败关闭 |

### M11：recall handle

| 对象 | 谁创建 | 谁保存 | 谁读取 | 谁能改 | current／stale |
|---|---|---|---|---|---|
| recall target declaration | 各源材料 owner | 源 owner 自己的 current 对象 | AuthorWorkspace handle registry | 源 owner | 目标 revision/SHA 变化后旧 declaration 不再 current |
| opaque recall handle | AuthorWorkspace 在 author/project scope 内 mint | AuthorWorkspace `recall_handles` prototype registry | M11 preflight、内部机器回取 | 不可 retarget；换版 mint 新 handle | active＋目标存在＋exact revision/SHA＋有权限＝current；换版 stale；删除/撤权 missing/revoked |
| 作者安全序号 | M11 renderer 对本次 omitted list 临时编号 | 不作长期 handle | 作者页面 | 每次重算 | 只对本次结果有效，不可用于机器回取 |

---

## 二、AuthorWorkspace 与 planstore 怎样诚实恢复

### 2.1 不是跨存储原子事务

这条链只能诚实写成：**两个业务提交，外加一个完成标记。**

```text
作者动作 handover_id
  ├─ A. AuthorWorkspace admission commit
  │    operation_id = <handover_id>:aw-admit
  │    C10 source + C10 material + C11 r1 + C1 current + chapter index
  │    phase = AW_COMMITTED_PLANSTORE_PENDING
  │
  ├─ B. planstore handover commit
  │    operation_id = <handover_id>:plan-handover
  │    existing chapter_id -> slot_mapping + handover_parts + history + receipt
  │
  └─ C. AuthorWorkspace completion marker
       operation_id = <handover_id>:aw-complete
       phase = HANDOVER_COMPLETE
```

A、B 是两次真实业务写入；C 只保存恢复水位。**不能说 A+B 原子。** AuthorWorkspace 和 planstore 各自仍使用自己的锁、expected version、journal 和幂等回执。

### 2.2 为什么不能三步共用一个 operation_id

AuthorWorkspace 已有规则：同一 `operation_id` 携带不同载荷会冲突。因此同一个 handover 根 ID 要派生稳定阶段后缀，不能把 `op-123` 同时用于 admission 和 complete marker。

### 2.3 崩溃点与恢复

| 崩溃／失败位置 | 可见事实 | 恢复动作 | 能否自动重试 |
|---|---|---|---|
| immutable source 尚未写完 | 没有业务对象 | 按 content SHA 重写 | 可以 |
| source blob 已写、A 未 commit | 可能有未引用 blob，业务不可读 | 重做 A；blob 可复用 | 可以 |
| A prepare／pointer swap 中断 | AuthorWorkspace recover 决定 all-before 或 all-after | 先 recover，再继续 | 可以；SHA 不明则人工 |
| A 已 commit、B 未开始／失败 | C10/C11/C1 已合法存在；phase pending；plan 未交棒 | 只重试 B，不删除章节 | 可以，前提是 slot/outline/chapter ref 语义未变 |
| B 已 commit、C 未写 | planstore 已交棒；AW 仍 pending | 用 B receipt 补 C | 可以，不能重复写 B |
| slot／outline 在 pending 期间发生语义变化 | 章节已存在，目标规划不再等同 | 停下让作者决定重绑、改章或取消 | 不可自动 |
| C1 current 已从 admission revision 变化 | stable chapter 仍在，但作者动作所见正文已变化 | 停下让作者确认是否仍交同章 | 不可自动 |
| 任一侧 journal、receipt、SHA 相互矛盾 | 无法证明 before/after | `NEEDS_MANUAL_RECOVERY` | 不可猜 |

🔥 **`AW_COMMITTED_PLANSTORE_PENDING` 是合法中间态，不是失败。** 作者已经拥有一个正式章节版本，只是规划账还没接上。planstore 失败不能反向删除 C11 INITIAL。

### 2.4 chapter ID owner

- 正式 owner：`CHAPTER_REVISION_LEDGER`。
- 建议发号方式：C11 INITIAL coordinator 在读取 current chapter ledgers／index 后计算下一 `cNN`，并把“没有该 ID”的 expected-version 条件放进 A 提交。
- 发号只在 A 成功后生效；并发冲突时重新读取、重新计算，不做提前占号。
- `planstore._next_c1_id` 退出正式交棒路径。

---

## 三、字段身份：哪些正式，哪些只能 prototype

| 范围 | 已有正式合同／现行硬字段 | 本轮只能 prototype |
|---|---|---|
| M8 C7 | C7 card、options、recommended ref、planning card ref/rev、guidance、conflicts | 稳定 planning card 的持久表、AC counter、完整卡 source watermark |
| M8 action | `C7_SELECTION_ACTION v1` 全字段，无额外字段 | builder API、专用错误码、selection commit provenance receipt |
| M8 long-term record | `PLAN_LEDGER_STORAGE.option_record`、公共规划字段、OPT counter | 若要求 option_record 自身保存 source card rev/C7 SHA，需要另升合同；本轮不能偷加 |
| stop points | plan-v2 有 `stop_points`；P1 auto_pass 与 P3 不可绕过在选择合同中有窄规则 | P2/P4/P5 全枚举、默认值、UI 名称、收费含义 |
| 工作稿 | `WRITING_DESK_WORK_DRAFT v1` | 历史 work revision 交棒能力 |
| handover action | `WORK_DRAFT_HANDOVER_ACTION v1`，当前无 title | 方案 A 的 `chapter_title` 或方案 B 的 `chapter_title_ref` |
| C10/C11/C1 | C10 v4、C11 v1、C1 v1 | AuthorWorkspace logical key/envelope、INITIAL admission saga、chapter ID allocator 实现 |
| plan handover | stable chapter ID mapping、handover transaction 方向已有正式依据 | AW pending/complete operation record、跨存储 recovery receipt |
| M10 | `CHAPTER_SLOT_SNAPSHOT v1`、显式 interval resolver、现有 adapter 输入形状 | character state timeline、story-time axis、scene/event interval ref、binding projection envelope |
| M11 | 当前代码已有 `recall_disposition/recall_handle` 形状，作者安全序号已实现 | handle registry、mint/validate/resolve、生命周期状态、保留期 |

---

## 四、INITIAL 章节标题：两案与推荐

### 方案 A：标题直接进入 handover action

建议形状：`WORK_DRAFT_HANDOVER_ACTION` 下一版本增加作者确认的 `chapter_title`。

- handover action 是 INITIAL 的短命来源；
- A 提交成功后，长期 title owner 立即变成 `C11.revisions[].title`；
- C1 只物化 current C11 title；
- 不会形成第二本长期标题账。

**优点：** 最窄、与作者“以这篇为准”同一次明确动作、无需先造新 owner。  
**代价：** 必须正式升合同与 validator；还要由 CZ 决定空标题／占位标题是否允许。

### 方案 B：action 引用已有 author-confirmed title owner

建议形状：action 带 `chapter_title_ref`，指向一个稳定、版本化、作者确认的标题对象。

**问题：当前材料里没有这个 owner。**

- `chapter_slot.title_hint` 正式写明“不是实际章节标题”；
- C10 的 `TITLE` 材料角色是书名／材料身份，不是章节 INITIAL title；
- 工作稿合同也没有标题字段。

要走 B，必须先新建 title object 的 owner、版本、作者确认、current/stale 和删除规则，施工半径明显更大。

✅ **推荐：方案 A。** 原因很简单：标题只在 INITIAL 入场时缺一次明确来源，进入 C11 后已经有长期 owner，没有必要再建一套标题账。  
⚠️ 这只是推荐。CZ 未明确选择前，OGH-04 必须停在标题合同门前，不能默认采用 A。

---

## 五、失败后是重试，还是回作者

| 缺口 | 可机械重试 | 必须回作者 | 必须人工恢复 |
|---|---|---|---|
| M8 card admission | plan 纯版本冲突、语义对象没变 | 选项语义已变、卡已终局处置 | plan SHA/history 不闭合 |
| M8 action builder | 重读 current plan/card 后重建 | P3、选项消失、混合输入改变变化集 | — |
| M8 consumer | expected version 冲突且动作仍等价 | 已有不同终局选择、stop policy 改变 | planstore journal 不明 |
| AW INITIAL | raw blob 重试；AW 纯版本冲突且 work 仍 current | work stale、标题不合规、slot 已有不相容章节 | workspace pointer/blob SHA 不明 |
| plan handover | B 或 C 幂等重放 | slot/outline/C1 revision 语义变了 | 两侧 receipt 不明 |
| M10 owner | 上游 source 更新后重建 projection | 时间先后、跨阶段场景、冲突作者事实 | source 无法回放 |
| M10 projection | 补齐 current binding 后重编译 | 是否拆场、角色是否在场等语义冲突 | 已保存 export 水位损坏 |
| M11 handle | 源 owner mint 新 current handle | 作者删除／撤权、来源身份冲突 | registry 与目标 SHA 不闭合 |

---

## 六、旧入口退出正式路线，但本轮不删除

1. `plan_selection_target_tool.py`：继续保留 transport-only/debug fixture；正式路线改为 OGH-02 builder。
2. C7 v0 写 `plan_latest.json`：不再作为正式选择持久化入口。
3. `planstore.accept_work_draft_handover(action, current_work, title, timestamp)` 与现有 `handover --work --title`：标 legacy；正式路线只消费已提交 C11/C1 引用。
4. `planstore._next_c1_id`：不再为正式 handover 发章节 ID。
5. M10 由任意调用方直接提供 `state_candidates/scene_bindings/event_bindings`：保留纯对象与 fixture 测试，退出 production owner 路线。
6. `story_time_hint` 作为机器区间：退出，只保留人读提示。
7. 任意 URI/string 作为可信 recall handle：退出。
8. 作者页展示真实 handle：继续禁止；现有安全序号保持现状。

---

## 七、窄任务卡总览

| 卡 | 目标 | 主要 owner | 前置 |
|---|---|---|---|
| OGH-01 | 稳定 planning card＋完整选项源 | planstore | 无代码前置；正式 schema 仍候选 |
| OGH-02 | 严格 selection action builder | 短命动作层 | OGH-01 读接口 |
| OGH-03 | planstore selection consumer | planstore | OGH-01、02 |
| OGH-04 | work→C10→C11 INITIAL→C1 | AuthorWorkspace/C11 | CZ 标题方案 |
| OGH-05 | 已提交 chapter→planstore＋恢复 | saga coordinator + planstore | OGH-04 |
| OGH-06 | 人物阶段／故事时间 owner | state/time owners + planstore binding | C4/attestation current refs |
| OGH-07 | M10 binding projection | M10 read adapter | OGH-06 |
| OGH-08 | recall handle registry／preflight | source owner + AuthorWorkspace | 现有 M11 safe ordinal |


## OGH-01｜M8 稳定规划卡 owner 与完整选项源

- 状态：`PROTOTYPE_READY__FORMAL_PLAN_SCHEMA_NOT_YET_FROZEN`
- 用户问题：作者过一会儿、重启后或换进程再点 C7 选项时，系统仍能找到同一张稳定规划卡、当时全部候选和真实规划目标，不能只靠 C7 里的短标签临时拼回长期记录。
- owner：
  - 语义 owner：planstore
  - 创建：M8 只提交候选；planstore 在写前校验后发 AC 号并落盘
  - 保存：planstore／AuthorWorkspace 逻辑键 plan
  - 读取：M8；C7 v1 renderer；C7 selection action builder；planstore selection consumer；审计读取
  - 修改：只有 planstore；每次修订 rev +1，旧 revision 可追溯
  - current/stale：最新 card rev 且所引 slot／PE／其它规划目标 rev 仍 current 才是 current；已产生该 card revision 的终局 option_record 后，该 revision 仍可审计但不再 selectable；任一来源 rev 改变则旧 C7／旧选择动作 stale。

### 输入

- 当前 plan-v2 的版本、SHA 和 id_counters
- 稳定 slot_ref
- 题目 question
- 完整 options：key、summary、why_fit、changes、risks、digest_refs，以及 C7 展示需要的 reveal_intent
- recommended_key
- 所有被引用规划对象的 current rev
- 来源身份与产生依据

### 输出

- planstore-owned 稳定 planning card（建议 AC-0001 形状）及 rev
- 可机械投影为 C7 cards[] 的只读视图
- 规划卡准入回执；失败时零 AC 发号、零 plan 变化

### 字段身份

**已有正式字段／规则：**

- PLAN_LEDGER_STORAGE 的公共规划对象字段
- option_record.options[] 的 key／summary／why_fit／changes／risks／digest_refs
- C7 cards[] 的 planning_card_ref／planning_card_rev／options.label／reveal_intent／recommended_option_ref

**只能 prototype：**

- plan-v2 顶层 planning_cards[]
- id_counters.AC
- 规划卡如何保存 C7 展示字段与来源水位
- 同一 card revision 是否 selectable 的派生索引

### 建议写集

- novel-mvp/design/M8_PLANNING_CARD_OWNER_R01.md（候选 owner／读写合同）
- novel-mvp/contracts/PLAN_LEDGER_STORAGE.md（只在正式批准后升版；不得原位偷加正式字段）
- novel-mvp/mvp/planning_card_workspace.py（候选新文件）
- novel-mvp/mvp/planstore.py（仅稳定卡准入与 AC 发号接缝）
- tests/test_novel_mvp_planning_card_owner.py（候选新测试）

### 禁改

- 不得让 C7 局部 card01 之类 ID 进入长期账
- 不得另建 plan_latest、planning_cards.json 等第二规划真源
- 不得让 M8 或模型直接发 AC／OPT 号
- 不得写 facts、actual、C4、冻结书稿
- 不得用标题或 option 文本模糊寻找旧卡
- 不得在本票顺手冻结 stop point 全枚举

### 正常例

planstore 在 S-0004 下接纳 AC-0007 r3，保存 A/B/C 的完整 why_fit、changes、risks、digest_refs；C7 只展示短标签。重启后作者选 B，动作 builder 从 AC-0007 r3 读回完整 B，而不是从短标签猜。

### 反例

系统只保存 C7 的 label='直接让爷爷忘记他'，选择时临时生成 why_fit、risks 和 PE 引用，或把 card01 当长期主键。

### 失败不变式

- plan 版本／SHA、目标 rev 或 AC 计数器冲突时，plan.json、history、commit log 均不变
- 失败不消耗 AC 号；重试重新读取 current plan 后再发号
- 已提交旧 card revision 不被静默改写
- 不存在完整选项源时不得生成可选择 C7

### 失败后怎么走

**可自动重试：**

- 纯版本冲突且语义对象未改变：重读 current plan 后重建准入请求

**必须回作者：**

- 规划目标已被替换、选项语义需重出、同一题已作终局处置

**必须人工恢复：**

- plan SHA 或历史完整性无法闭合

### 依赖

- C7_PLOT_LAYER v1
- C7_SELECTION_ACTION v1
- PLAN_LEDGER_STORAGE plan-v2
- AuthorWorkspace plan logical key
- M8-E01～M8-E07 的现行原子预期

### 停下问 CZ 的条件

- CZ 想让稳定规划卡脱离 planstore 成为跨项目独立知识对象
- CZ 要求 option_record 自身必须内嵌 source card rev／C7 SHA，而不是由 planstore commit receipt 与 card revision history共同追溯
- CZ 要允许同一 card revision 在终局选择后再次选择

### 完成后仍不能宣称什么

- 不能宣称 M8 完成
- 不能宣称规划质量已验证
- 不能宣称 planning_cards 字段已经成为正式合同
- 不能宣称选择已经落账；那属于 OGH-03

## OGH-02｜M8 C7 selection action builder

- 状态：`IMPLEMENTABLE_AFTER_OGH_01_READ_INTERFACE`
- 用户问题：作者点了 C7 的某个选项后，需要得到一份严格、可重放、能被 planstore 写前校验的 C7_SELECTION_ACTION；系统不能只返回当前 transport prototype，也不能把被停点挡住当成已选择。
- owner：
  - 语义 owner：短命动作层；无长期真值 owner
  - 创建：C7 selection action builder
  - 保存：默认不持久化整份 action；可由调用方保存短期命令／回执
  - 读取：planstore selection consumer
  - 修改：动作不可修改；输入变化后重建新 operation_id
  - current/stale：只在 source C7 SHA、planning card rev、目标 expected_revs、stop point 水位均仍 current 时可消费；任一变化即 stale。

### 输入

- 完整 C7 v1 与 expected C7 snapshot SHA
- card_local_id、作者 choice 或合规 auto 请求
- OGH-01 的 current planning card 完整记录
- current plan 目标 rev 与 id_counters.OPT
- planstore stop_points 当前值

### 输出

- 字段严格等于 C7_SELECTION_ACTION v1 的动作
- digest_selection 或 discard_group 的合法 option_record、expected_revs、plan_mutations
- 被挡住、stale 或不完整时无 action、无 option_record

### 字段身份

**已有正式字段／规则：**

- C7_SELECTION_ACTION v1 全字段
- PLAN_LEDGER_STORAGE option_record 全字段

**只能 prototype：**

- builder 的读取接口和错误码
- OPT 下一号作为写前请求的生成方式；真正发号仍归 planstore

### 建议写集

- novel-mvp/mvp/c7_selection_action_builder.py（候选新文件）
- novel-mvp/mvp/plan_selection_target_tool.py（保留；改为 debug／transport-only 旧入口说明，不删除）
- tests/test_novel_mvp_c7_selection_action_builder.py（候选新测试）

### 禁改

- 不得写 plan.json 或任何 workspace logical key
- 不得在动作外自造字段
- 不得默认 options[0]、按标题匹配或自动改用新 card rev
- 不得给未知 stop point 值补默认
- 不得让 actor=model
- variant_note 不得夹带改变 digest_refs／plan_mutations 的新方案；这种输入必须重出规划卡

### 正常例

作者在 current C7 的 AC-0007 r3 上选 B。builder 核对完整卡、P1/P3、PE-0412 r2 后，生成 digest_selection；option_record 保留 A/B/C 全部候选和当时推荐 B。

### 反例

P3 要求作者确认时，auto builder 仍生成动作；或作者写了一段新方案，builder 只塞进 variant_note 却沿用旧 PE 变化。

### 失败不变式

- 任何失败只返回错误，不产生正式 action
- 输入对象不被修改
- 相同输入和固定 operation_id 生成字节稳定动作；不同载荷不得复用同一 operation_id
- 被停点挡住与 discard_group 严格分开

### 失败后怎么走

**可自动重试：**

- current plan 纯版本冲突：重读后重建动作

**必须回作者：**

- choice 不存在、卡已被语义修订、P3 要求作者确认、混合输入改变规划语义

**必须人工恢复：**

- 无。

### 依赖

- OGH-01
- C7_SELECTION_ACTION v1
- plan_tool.c7_snapshot_sha256
- stop_points current read

### 停下问 CZ 的条件

- 要允许 variant_note 改变选项语义或规划目标
- 要新增 P 号、默认值或改变 P1／P3 权力
- 要把完整动作长期存进 plan.json

### 完成后仍不能宣称什么

- 不能宣称选择已保存
- 不能宣称规划已消化
- 不能宣称作者确认了事实或 actual
- 不能取代 planstore 写前校验

## OGH-03｜M8 planstore selection consumer

- 状态：`IMPLEMENTABLE_AFTER_OGH_01_AND_OGH_02`
- 用户问题：合法选择动作需要由唯一 plan writer 一次性保存完整 option_record、规划消化、历史和提交回执；失败或重试不能留下半条选择，也不能重复发 OPT 号。
- owner：
  - 语义 owner：planstore
  - 创建：planstore selection consumer 在写前校验通过后创建持久结果
  - 保存：planstore／AuthorWorkspace plan logical key
  - 读取：M8；审计；撤销／历史读取；后续规划消费者
  - 修改：只有 planstore；option_record 作为历史选择记录不静默覆盖，纠错走新提交与 history
  - current/stale：option_record 是历史记录，不冒充当前推荐；其规划效果是否 current 由被消化对象 rev、plan history 与后续变更决定。

### 输入

- 严格 C7_SELECTION_ACTION v1
- 动作绑定的完整 C7 快照
- current planning card 与完整选项源
- current plan version／SHA、目标对象 rev、stop_points
- 现有 planstore operation／transaction primitives

### 输出

- 一次 planstore 原子提交：option_record、合法 digest_event 变化、history、commit log、OPT counter
- 幂等 commit receipt
- discard_group 时只写明确驳回记录，不做规划消化

### 字段身份

**已有正式字段／规则：**

- PLAN_LEDGER_STORAGE option_record
- C7_SELECTION_ACTION 写前硬门
- planstore 既有 history／commit transaction

**只能 prototype：**

- selection consumer 的函数入口与专用 receipt 展示字段

### 建议写集

- novel-mvp/mvp/planstore.py（新增窄 selection consumer，不改其它 writer 权力）
- novel-mvp/mvp/plan_workspace.py（如需绑定 AuthorWorkspace expected plan version）
- tests/test_novel_mvp_planstore_selection_consumer.py（候选新测试）
- novel-mvp/contracts/C7_SELECTION_ACTION.md（只在发现正式冲突时另开合同修订，不随实现偷改）

### 禁改

- 不得写 facts.json、C4、actual、state 或书稿
- 不得把 action envelope 整份复制进 plan.json
- 不得让 auto 选非推荐项、discard_group 或越过 P3
- 不得先写 option_record 再校验 digest target
- 不得重用已消费的 card revision 产生第二个终局选择

### 正常例

AC-0007 r3、PE-0412 r2、P1=auto_pass 均 current；planstore 用 OPT-0009 一次提交完整 option_record 与 PE digest。相同 operation_id 重放只返回原 receipt。

### 反例

PE rev 已变，consumer 仍先追加 OPT-0009，再把 digest 失败写成 warning；或同一 auto 动作采用非推荐 C。

### 失败不变式

- 任一写前硬门失败，plan、history、commit log、counter 全部不变
- 同 operation_id＋同载荷幂等；同 operation_id＋不同载荷冲突
- 提交恢复只能得到完整 before 或完整 after
- 失败不把尚未处理改写成 discarded

### 失败后怎么走

**可自动重试：**

- plan version 冲突但 card／target 语义未变：重读并重新构建动作

**必须回作者：**

- 卡已被替换、选择项消失、stop point 改成需作者确认、同一题已有不同终局处置

**必须人工恢复：**

- planstore journal／SHA 无法确认 before 或 after

### 依赖

- OGH-01
- OGH-02
- PLAN_LEDGER_STORAGE
- planstore existing transaction/recovery

### 停下问 CZ 的条件

- 要允许一张卡多次终局选择
- 要让选择直接产生事实、actual 或作者 Canon
- 要把 stop point 自动放行扩大到现行 P1 之外

### 完成后仍不能宣称什么

- 不能宣称故事已发生
- 不能宣称 M8 到 M10 主循环已接通
- 不能宣称任何真实模型规划质量
- 不能宣称整组撤销／改判 UX 已完成

## OGH-04｜工作稿进入 AuthorWorkspace：受控 C10 source → C11 INITIAL → C1 current

- 状态：`BLOCKED_ONLY_ON_CZ_TITLE_SCHEME__OTHER_OWNER_DESIGN_READY`
- 用户问题：作者点“以这篇为准”后，工作稿要逐字变成可回验的 C10 source、C11 r1 和 C1 current；章节 ID 必须由章节版本 owner 产生，不能由 planstore 先猜，也不能在 C11 之前出现 C1。
- owner：
  - 语义 owner：AuthorWorkspace 内的 C10 source owner＋CHAPTER_REVISION_LEDGER owner；C1 只是 current 物化视图
  - 创建：C11 INITIAL admission coordinator
  - 保存：AuthorWorkspace；raw bytes 用现有 immutable raw_upload，C10/C11/operation envelope 使用受限 logical keys
  - 读取：C1/M2 current chapter consumers；OGH-05 handover bridge；审计／恢复
  - 修改：C10 identity 只追加 revision；C11 只追加 revision；C1 由 C11 current 重物化；章 ID 只在成功 AW commit 后可见
  - current/stale：work_rev 必须 current；C10 identity revision 必须仍是 CONFIRMED+CHAPTER；C1 ref 必须等于 C11 current。任一不一致在 AW 写前失败。

### 输入

- current WRITING_DESK_WORK_DRAFT v1
- current WORK_DRAFT_HANDOVER_ACTION v1 或 CZ 选定后的标题版动作
- 作者确认的 INITIAL 章节标题来源
- AuthorWorkspace 当前 input_manifest／chapters／chapter_index／chapter revision store／handover operation store 水位

### 输出

- exact UTF-8 work text 的 immutable raw_upload receipt，并被 input_manifest 引用
- C10 material unit：full-span、no normalization、USER_DECLARATION、CONFIRMED+CHAPTER
- C11 stable chapter_id 的 revision 1，change_kind=INITIAL
- 与 C11 current 完全一致的 C1 v1 与 chapter_index 项
- handover operation phase=AW_COMMITTED_PLANSTORE_PENDING
- AW admission commit receipt

### 字段身份

**已有正式字段／规则：**

- WRITING_DESK_WORK_DRAFT v1
- WORK_DRAFT_HANDOVER_ACTION v1（当前不含标题）
- C10_INTAKE_MATERIAL_IDENTITY v4
- C11_CHAPTER_REVISION_LEDGER v1
- C1_CHAPTER_DOC v1

**只能 prototype：**

- AuthorWorkspace 新 logical key／envelope：例如 intake_materials、chapter_revisions、chapter_admission_operations
- chapter_id 在 AW expected-version 门内发号的具体算法
- AW_COMMITTED_PLANSTORE_PENDING operation record 字段
- 标题方案 A 所需 WORK_DRAFT_HANDOVER_ACTION v2 字段，或方案 B 的 title_ref

### 建议写集

- novel-mvp/design/WORK_DRAFT_C10_C11_INITIAL_ADMISSION_R01.md（候选设计）
- novel-mvp/mvp/workspace.py（仅经批准增加受限 logical keys；复用 raw_upload，不新建任意路径入口）
- novel-mvp/mvp/chapter_initial_admission_workspace.py（候选新文件）
- novel-mvp/mvp/chapter_workspace.py（只接 C1 current 物化）
- tests/test_novel_mvp_work_draft_c11_initial_admission.py（候选新测试）
- 标题方案确定后才允许修订 WORK_DRAFT_HANDOVER_ACTION 合同／validator

### 禁改

- 不得调用 planstore 或写 handover_parts
- 不得复用 planstore._next_c1_id
- 不得把 slot.title_hint 当实际章节标题
- 不得把 C10 的 TITLE 材料角色误当章节标题 owner
- 不得改工作稿一个字、规范化空格或标点
- 不得创建 facts、actual、对账边、关章状态
- 不得在 AW commit 失败时留下可见 C1 或已消费 chapter_id

### 正常例

current work S-0004@work-r2 的 UTF-8 SHA 为 X。作者明确标题后，系统存 raw_upload，生成 C10 full span、C11 c07 r1、C1 c07，并在一个 AW commit 中把 operation 标为 AW_COMMITTED_PLANSTORE_PENDING；plan 此时仍零变化。

### 反例

CLI 收到 work JSON 和 title 后，由 planstore 先发 c07、直接写 legacy C1，再事后补 C11；或直接采用章槽 title_hint='归家'。

### 失败不变式

- immutable blob 在 AW commit 前可以成为未引用孤儿，但不得被业务读取；后续可按内容寻址复用或清理
- AW 多 logical key 提交只能 all-before／all-after
- stale work-r1 不得静默升级为 r2
- 发号冲突时重新读取并重算，失败不保留空号
- 任何失败不改 planstore

### 失败后怎么走

**可自动重试：**

- raw_upload 写入中断：按内容 SHA 重试
- AW version conflict 且 work/action 仍完全 current：重读并重算 chapter_id 后重试
- 相同阶段 operation_id＋相同载荷：幂等返回原 receipt

**必须回作者：**

- work_rev stale
- 标题缺失或标题来源不符合 CZ 选定方案
- 作者是否要交历史 work revision
- 同一 slot 已有不相容 stable chapter identity

**必须人工恢复：**

- AuthorWorkspace current pointer／manifest／blob SHA 无法闭合

### 依赖

- CZ 对 INITIAL 章节标题方案的选择
- C10/C11/C1 validators
- AuthorWorkspace commit/store_immutable/read_immutable
- AE-AW-C01～C06、M1-E06、跨模块版本家规

### 停下问 CZ 的条件

- 在标题方案 A 与 B 之间选择
- 要允许自动生成、空标题或默认“未命名章节”而不经作者确认
- 要允许选择历史 work revision 交棒
- 一个 slot 已有章节时要 INITIAL、REPLACE 还是另开章

### 完成后仍不能宣称什么

- 不能宣称正式交棒完成
- 不能宣称 planstore 已消费 chapter_id
- 不能宣称跨存储原子
- 不能宣称章节已关、已发表或事实已入账

## OGH-05｜已提交章节的 planstore 交棒与两存储恢复

- 状态：`IMPLEMENTABLE_AFTER_OGH_04`
- 用户问题：AuthorWorkspace 已经形成合法 C10/C11/C1 后，planstore 才能消费现成 chapter_id；任一进程在 AW 提交后、planstore 提交前或 planstore 提交后崩溃，都必须可恢复，不能把两个存储说成一个原子事务。
- owner：
  - 语义 owner：交棒协调器只拥有 saga 状态；章节真值归 AuthorWorkspace/C11，规划写入归 planstore
  - 创建：handover bridge/recovery coordinator
  - 保存：AW 保存 phase marker；planstore 保存 mapping／handover_parts／history／receipt
  - 读取：恢复扫描；作者工作区状态；后续 plan consumers
  - 修改：阶段 A 由 OGH-04；阶段 B 只有 planstore；B 成功后用小型 AW marker commit 标 HANDOVER_COMPLETE
  - current/stale：AW pending 记录绑定的 chapter_id、chapter_revision_ref、slot_ref、source_outline_ref 必须仍 current；planstore receipt 与 operation_id 对上后才能完成 marker。

### 输入

- AW phase=AW_COMMITTED_PLANSTORE_PENDING 的持久记录
- 已存在的 C11 current revision 与 C1 v1
- current plan slot／outline／mapping／plan version SHA
- 确定性阶段 operation IDs：<handover_id>:aw-admit、:plan-handover、:aw-complete

### 输出

- planstore 一次原子提交：active slot_mapping、handover_parts、必要 slot 状态／history／commit receipt
- AW phase=HANDOVER_COMPLETE 与 planstore receipt 指针
- 可重放恢复结果；不会重复 mapping、handover part 或 chapter ID

### 字段身份

**已有正式字段／规则：**

- C11 stable chapter ID/current revision
- C1 v1
- PLAN_LEDGER_STORAGE slot_mapping 与 handover 事务规则
- WORK_DRAFT_HANDOVER_ACTION target_planstore_result

**只能 prototype：**

- AW 两阶段 operation envelope
- 三段 operation_id 后缀
- planstore committed receipt 的 AW marker 引用字段
- 恢复错误分类

### 建议写集

- novel-mvp/design/AW_PLANSTORE_HANDOVER_RECOVERY_R01.md（候选设计）
- novel-mvp/mvp/chapter_handover_bridge.py（候选新文件）
- novel-mvp/mvp/planstore.py（新增 consume_committed_chapter_handover 窄入口）
- novel-mvp/mvp/workspace.py 或 chapter admission workspace（只更新 operation marker）
- tests/test_novel_mvp_aw_planstore_handover_recovery.py（候选新测试）
- 现有 accept_work_draft_handover／CLI 标记 legacy，不删除

### 禁改

- 不得接受 work text、title 或路径作为 planstore 新入口
- 不得由 planstore 新发 chapter_id 或 C11 revision
- 不得宣称跨 AuthorWorkspace 与 planstore 原子提交
- planstore 失败后不得删除、回滚或隐藏已合法提交的 C10/C11/C1
- 不得因 slot 标题相似自动改绑
- 不得自动产生 facts、actual、RE 或关章

### 正常例

AW 已提交 c07 r1 后进程崩溃。恢复进程读取 pending，planstore 用 :plan-handover 提交 mapping/handover；若在 AW complete marker 前再崩溃，下一次发现 planstore 已有同 operation receipt，只补 :aw-complete，最终 HANDOVER_COMPLETE。

### 反例

一个函数同时写 AW 和 planstore，抛异常后把两边都标成 rollback；或 planstore 失败就删除 c07，假装没有发生过。

### 失败不变式

- 业务阶段只有 A：AW 已提交、B：planstore 已提交；最后 marker 只是恢复标记，不冒充第三个真值动作
- AW_COMMITTED_PLANSTORE_PENDING 是合法可见状态，不等于失败或完整交棒
- planstore B 失败时 C10/C11/C1 保持 current，重试只做 B
- B 已提交而 marker 未写时，重试不得重复新增 mapping／handover part
- 未知 SHA／journal 分歧进入 NEEDS_MANUAL_RECOVERY，不猜 before/after

### 失败后怎么走

**可自动重试：**

- planstore 纯版本冲突且 slot／outline／chapter ref 语义未变
- B 已提交但 AW marker 缺失
- 相同阶段 operation_id 同载荷重放

**必须回作者：**

- slot 已改绑或已映射到另一章
- source_outline_ref 已被作者换成不相容版本
- C1 current 已从 admission revision 变成另一 revision
- 作者要求取消已提交章节或改交另一槽

**必须人工恢复：**

- 任一存储的 receipt／SHA／journal 无法确定提交结果

### 依赖

- OGH-04
- planstore transaction/recovery
- PLAN_LEDGER_STORAGE slot_mapping
- AuthorWorkspace idempotent commit

### 停下问 CZ 的条件

- 计划槽在 pending 期间变化时是否允许自动重绑
- 作者取消交棒时已提交 C11 INITIAL 应保留为未映射章节、另发 revision，还是允许专门删除流程
- 要把 HANDOVER_COMPLETE 扩大解释为关章、事实入账或可开下一章

### 完成后仍不能宣称什么

- 不能宣称跨存储原子
- 不能宣称章节关闭
- 不能宣称书稿事实已确认或实际发生
- 不能宣称 legacy handover 已删除

## OGH-06｜M10 人物阶段账与故事时间轴／计划绑定 owner

- 状态：`PROTOTYPE_OWNER_FOUND__FIELD_CONTRACT_OPEN`
- 用户问题：现有 interval resolver 只会对调用方给的区间做唯一命中。系统还缺少可持续保存、可回源、能判旧的人物阶段读取面，以及 scene/event 到故事时间区间的稳定绑定来源。
- owner：
  - 语义 owner：人物阶段读取面归 CHARACTER_STATE_TIMELINE_OWNER；故事时间锚与次序归 STORY_TIME_AXIS_OWNER；计划 scene/event 对时间锚的引用归 planstore
  - 创建：时间轴／状态 owner 从 current confirmed C4 或 AUTHOR_ATTESTATION 产生 source-bound 投影；作者/M8 只能提案计划绑定，planstore 落盘
  - 保存：物理上复用 AuthorWorkspace state domain；计划引用留在 plan，不新建第二事实库
  - 读取：M10 binding reader；M8/M11 只读消费者；一致性检查
  - 修改：只能通过上游事实／作者签字／时间轴作者决定变更；M10 不可写
  - current/stale：每条阶段记录必须绑定 source ref/revision/SHA；来源不再 current confirmed、区间被新决定接替或同一 entity+state_key 出现重叠歧义时旧记录 stale／superseded。计划 binding 还必须绑定 scene/event rev 与 axis rev。

### 输入

- current confirmed C4 facts 与 AUTHOR_ATTESTATION
- stable character/entity IDs
- 作者确认的故事时间锚、顺序和区间决定
- plan-v2 current scenes/events 及 rev
- 现有 story_time_hint 仅作人读提示

### 输出

- 只读 state candidate API，输出复用 resolver 现有字段：entity_ref、state_anchor_ref、effective_interval、source_ref、source_revision、state_summary
- scene/event story interval resolver API，返回半开区间与 axis/source watermark
- planstore-owned scene/event→story interval ref 绑定
- current/stale/ambiguous 的机械结果，不直接生成 M10 卡

### 字段身份

**已有正式字段／规则：**

- scene_state_interval_resolver 的显式半开区间输入形状
- C4 current confirmed／AUTHOR_ATTESTATION 作为上游权力
- plan-v2 scene/event stable id 与 rev
- R13 三种时间分账原则

**只能 prototype：**

- CHARACTER_STATE_TIMELINE_OWNER 存储字段与 logical key 内部结构
- STORY_TIME_AXIS_OWNER 的 anchor/interval 字段
- scene/event story_interval_ref 字段
- 开放端点、排序号与时间锚迁移的具体机器合同

### 建议写集

- novel-mvp/design/M10_STATE_TIMELINE_AND_STORY_TIME_OWNER_R01.md（候选设计）
- novel-mvp/mvp/character_state_timeline_workspace.py（候选新文件）
- novel-mvp/mvp/story_time_axis_workspace.py（候选新文件）
- novel-mvp/mvp/planstore.py（仅 scene/event 时间绑定的候选写入口；正式字段批准后）
- tests/test_novel_mvp_m10_state_timeline_owner.py
- tests/test_novel_mvp_story_time_axis_owner.py

### 禁改

- 不得让 M10 或 resolver 成为真值 writer
- 不得把 state timeline 建成与 C4 并列的第二历史真源
- 不得用 story_time_hint、章号、数组位置直接当机器区间
- 不得用人物心理标签单独生成硬阶段
- 不得在区间重叠时按最新时间戳或第一条猜唯一答案
- 不得把 planned scene/event 的未来状态写成已发生 current state

### 正常例

伤势来源 f120 在故事时间 T20 生效，f168 在 T35 明确痊愈。timeline 提供 [T20,T35) 的“左臂包扎”和 [T35,+∞) 的“已痊愈”；计划场 SCN-0040 绑定 [T10,T12)，因此 resolver 不会装入绷带。

### 反例

场景只写 story_time_hint='几天前'，M10 直接取当前人物状态“左臂包扎”；或同一伤势有两条重叠区间时选数组最后一条。

### 失败不变式

- 任何重建／读取失败不改 C4、作者签字、plan 或书稿
- 同一 entity+state_key 的重叠、断锚、来源 stale 均显式失败
- 状态投影可全部重建；丢失投影不能反向改真源
- planned 时间绑定失败不创建虚构 story anchor

### 失败后怎么走

**可自动重试：**

- 来源版本变化后由 owner 重建 timeline／binding，再重新读取

**必须回作者：**

- 故事时间先后无法唯一确定、作者故意让场景跨越状态变化、冲突事实均有作者权力、计划是否允许创建新时间锚

**必须人工恢复：**

- source ref/SHA 指向损坏或不可回放对象

### 依赖

- C4 current confirmed/attestation
- R13 state ledger principle
- PLAN_LEDGER_STORAGE scene/event
- scene_state_interval_resolver

### 停下问 CZ 的条件

- 是否允许机器在无作者确认时把自然语言 story_time_hint 升成稳定时间锚
- 场景跨两个阶段时是强停、拆场还是允许返回多阶段
- 开放区间、并列时间、倒叙与无法排序事件的正式表示
- 计划层能否自行创建未来 story-time anchor

### 完成后仍不能宣称什么

- 不能宣称故事时间字段已正式冻结
- 不能宣称人物账完整或穷尽全书
- 不能宣称 M10 已会自动理解自然语言时间
- 不能宣称当前状态是真值历史的第二份副本

## OGH-07｜M10 scene/event binding 读取与可重建投影

- 状态：`IMPLEMENTABLE_AFTER_OGH_06_READ_APIS`
- 用户问题：M10 需要从 current 章槽、故事时间、人物阶段和稳定实体锚组装 scene/event bindings；调用方不能继续随意塞 state_candidates 和 bindings，让 M10 在不知道来源水位的情况下导出场景卡。
- owner：
  - 语义 owner：M10 只拥有 M10_BINDING_PROJECTION／scene slice assembly，不拥有人物状态、故事时间、计划或实体真值
  - 创建：M10 binding reader/adapter
  - 保存：默认可重建；若保存 scene export，沿用 scene_export_workspace 并保存完整 source watermark
  - 读取：m10_scene_slice_adapter；scene_export；Markdown/JSON/ZIP exporter
  - 修改：M10 只能重编译投影；上游变更后不修改真源
  - current/stale：CHAPTER_SLOT_SNAPSHOT plan version/SHA、slot/scene/event rev、story-time axis rev、state source refs、entity/location anchors 全部一致才 current；只对真实依赖变化判 stale。

### 输入

- current CHAPTER_SLOT_SNAPSHOT v1
- OGH-06 scene/event story interval binding
- OGH-06 state candidate read API
- stable character/location/entity anchors
- 计划侧 visual、shot_hint、dialogue info、writing guidance 等展示供料

### 输出

- 对每个 scene 的规范化 scene_story_interval request
- 现有 interval resolver 的唯一 state selections 或明确失败
- 供 m10_scene_slice_adapter 的完整 scene_bindings／event_bindings
- source watermark 与依赖 refs；可保存的 M10 projection／export

### 字段身份

**已有正式字段／规则：**

- CHAPTER_SLOT_SNAPSHOT v1
- scene_state_interval_resolver request/result shape
- m10_scene_slice_adapter 现有 binding 输入形状

**只能 prototype：**

- M10_BINDING_PROJECTION envelope
- 跨 owner source watermark
- entity/location anchor read interface

### 建议写集

- novel-mvp/mvp/m10_binding_reader.py（候选新文件）
- novel-mvp/mvp/m10_scene_slice_adapter.py（只改为消费受控 reader 输出；保留纯对象验证）
- novel-mvp/mvp/scene_export_workspace.py（补齐真实依赖水位时）
- tests/test_novel_mvp_m10_binding_reader.py（候选新测试）
- 现有 resolver tests 保留并扩来源 stale 回归

### 禁改

- 不得写 state、plan、C4、C11 或实体 owner
- 不得把任意调用方 JSON 当 production binding 来源
- 不得在 zero/multi match 时取 current state 兜底
- 不得把 visual／shot_hint／writing_guidance 升成事实
- 不得因无关人物或无关场景变化把全部 M10 export 判 stale

### 正常例

SCN-0007 的 plan rev、时间区间和 CH-0001 状态候选都 current，resolver 唯一命中对应阶段；M10 输出引用具体 state_anchor_ref 和完整 watermark，重复运行逐字一致。

### 反例

SCN-0007 没有故事时间绑定，adapter 仍使用调用方写的 time='清晨'和当前人物衣着生成卡；或状态区间重叠时偷偷选第一条。

### 失败不变式

- 任一依赖 missing/stale/ambiguous 时不保存 current scene export
- 失败不产生部分 scene cards 或只导出已过的前半场
- 同一完整输入必须字节稳定
- M10 projection 可删除重建，不影响上游 owner

### 失败后怎么走

**可自动重试：**

- 上游 owner 补齐 current binding/timeline 后重新编译
- 保存时发生纯 expected-version 冲突且依赖未变

**必须回作者：**

- 场景跨阶段且产品没有拆场规则
- 角色是否在场／时间位置存在语义冲突
- 计划与作者锁定时间不一致

**必须人工恢复：**

- 已保存 export 的 source watermark/SHA 损坏

### 依赖

- OGH-06
- CHAPTER_SLOT_SNAPSHOT
- scene_state_interval_resolver
- m10_scene_slice_adapter
- scene_export_workspace

### 停下问 CZ 的条件

- 需要把跨阶段场景自动拆成多张卡
- 允许缺时间时使用 current state 作为软提示
- 要把 M10 投影反写人物账或规划账

### 完成后仍不能宣称什么

- 不能宣称 M10 拥有真值
- 不能宣称场景卡内容质量已验证
- 不能宣称所有人物阶段都已建立
- 不能宣称跨媒介生产包已完成

## OGH-08｜M11 recall handle 存在性、新鲜度与解析 owner

- 状态：`OWNER_SPLIT_RECOMMENDED__LIFECYCLE_PROTOTYPE`
- 用户问题：M11 可以告诉作者“第 1 项可回取”，但机器还不知道真实 recall_handle 是否存在、是否仍指向同一版材料、是否属于当前作者。系统不能把任意字符串当可回取承诺。
- owner：
  - 语义 owner：源材料 owner 声明可回取目标；AuthorWorkspace 负责 opaque handle registry、mint、validate、resolve；M11 只做 preflight 和消费
  - 创建：AuthorWorkspace 在绑定作者／项目的 source owner 注册请求通过后 mint immutable handle
  - 保存：AuthorWorkspace 受限 recall_handles logical key／registry（候选）
  - 读取：M11 packer preflight；内部调试／机器回取
  - 修改：handle 本身不可改指向；来源换版后旧 handle stale，owner mint 新 handle；撤权／删除后 revoked/missing
  - current/stale：registry active、目标存在、author/project scope 匹配、source revision 与 SHA 完全相同且仍有权限时 current；目标换版为 stale；删除/撤权为 missing/revoked；跨作者查询对外与 missing 不可区分。

### 输入

- 绑定作者／项目的 AuthorWorkspace handle
- source owner、source kind、logical key/object ref
- exact source revision 与 content/body SHA
- recall_disposition=RETRIEVABLE 或 NOT_RETRIEVABLE
- 当前读取权限

### 输出

- opaque immutable recall_handle
- 内部 validate 结果：CURRENT／STALE／MISSING_OR_FORBIDDEN／REVOKED（具体对外错误按安全边界收敛）
- resolve 后的受控材料与来源水位
- 作者页继续只使用安全序号，不显示真实 handle

### 字段身份

**已有正式字段／规则：**

- 当前 packer 的 recall_disposition 与 recall_handle 形状
- AuthorWorkspace 作者／项目隔离与 immutable/read 权限原则
- 作者安全 omission 序号现行实现

**只能 prototype：**

- recall handle registry row
- 状态枚举与 mint/validate/resolve API
- source owner 注册协议
- 是否保存 source kind/logical key/object ref 的具体字段

### 建议写集

- novel-mvp/design/M11_RECALL_HANDLE_OWNER_R01.md（候选设计）
- novel-mvp/mvp/recall_handle_workspace.py（候选新文件）
- novel-mvp/mvp/m11_recall_preflight.py（候选新文件）
- novel-mvp/mvp/packer.py（只接 preflight；不改预算／actuality 主逻辑）
- novel-mvp/mvp/packer_tool.py（保留作者安全序号；真实 handle 仅 debug/machine channel）
- tests/test_novel_mvp_m11_recall_handle_workspace.py（候选新测试）

### 禁改

- 不得把 file://、绝对路径、任意 URI 或调用方字符串直接当可信 handle
- 不得让 M11 自己 mint／重定向 handle
- 不得把旧 handle 静默改指向新 revision
- 不得在作者视图渲染真实 handle 或被挡材料 ID
- 不得用 normalized request SHA 代替 source freshness
- 不得默认 TTL、过期天数、跨项目共享或可复制公共链接

### 正常例

材料 EV-0042 r5 的源 owner 注册 exact SHA，AuthorWorkspace mint h_xxx。M11 打包前验证 current；材料升到 r6 后 h_xxx 返回 STALE，源 owner mint 新 handle，作者页仍只显示“第 1 项可回取”。

### 反例

候选传 recall_handle='demo://evidence/identity' 就被标为 RETRIEVABLE；或来源变版后旧 handle 自动改指向最新内容。

### 失败不变式

- RETRIEVABLE 但 handle 不存在／stale 时，M11 不得输出“可回取”承诺
- NOT_RETRIEVABLE 时 handle 必须为 null，且不临时 mint
- 跨作者／跨项目解析不泄露目标是否存在
- registry 失败不改变候选材料、预算选择或源对象
- 旧 handle 始终保留原版本身份，不能 retarget

### 失败后怎么走

**可自动重试：**

- 源 owner 为 current revision mint 新 handle 后重跑 M11 preflight

**必须回作者：**

- 材料被作者主动删除／撤权、来源身份冲突、是否允许回取需要作者决定

**必须人工恢复：**

- registry 与目标 SHA/receipt 无法闭合

### 依赖

- AuthorWorkspace isolation
- packer recall fields
- packer_tool author-safe ordinal
- M11-E01～M11-E06 原子预期

### 停下问 CZ 的条件

- handle 要给作者复制、跨设备公开或跨项目复用
- handle 要做可变 alias 而不是不可变版本句柄
- 要设置 TTL／自动过期／保留期限
- 删除后是否允许指向历史恢复区

### 完成后仍不能宣称什么

- 不能宣称 M11 已有完整回捞 UI
- 不能宣称所有材料都有 handle
- 不能宣称 handle 是作者可见链接
- 不能宣称当前 C9 正式合同已经补齐生命周期字段

---

## 八、主要直接证据路径

### 当前真源

- `01_current_truth/TEMP/chatgpt_pro_remaining_gaps_and_atomic_tests_20260820_r01/LOCAL_CURRENT_REBASE_R01.md`
- `01_current_truth/TEMP/chatgpt_pro_remaining_gaps_and_atomic_tests_20260820_r01/PROMPT_11_OWNER_GAPS_AND_HANDOVER_DESIGN.md`

### 正式合同

- `02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`
- `02_current_route/novel-mvp/contracts/C7_SELECTION_ACTION.md`
- `02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md`
- `02_current_route/novel-mvp/contracts/WRITING_DESK_WORK_DRAFT.md`
- `02_current_route/novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md`
- `02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`
- `02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`
- `02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md`
- `02_current_route/novel-mvp/contracts/CHAPTER_SLOT_SNAPSHOT.md`

### 当前代码与直接测试

- `02_current_route/novel-mvp/mvp/workspace.py`
- `02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`
- `02_current_route/novel-mvp/mvp/plan_tool.py`
- `02_current_route/novel-mvp/mvp/planstore.py`
- `02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`
- `02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`
- `02_current_route/novel-mvp/mvp/scene_export_workspace.py`
- `02_current_route/novel-mvp/mvp/packer.py`
- `02_current_route/novel-mvp/mvp/packer_tool.py`
- `02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`
- `02_current_route/tests/test_novel_mvp_planstore_handover.py`
- `02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`
- `02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`
- `02_current_route/tests/test_novel_mvp_packer.py`

### 只作资料的外部／上游报告

- `04_external_reviews/pro_component_pilot_followup_bundle/SIX_REPORT_COMPONENT_DESIGN_AND_CLEAN_TASKS.md`
- `04_external_reviews/pro_m7_m11_usability_review/M7_M11_PRO_REVIEW.md`
- `04_external_reviews/pro_pa_author_loop_review/PA_AUTHOR_DRAFT_CHECK_CLOSEOUT_HANDOVER_REVIEW.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/`

## 九、收口边界

即使 8 张卡全部完成，仍只能宣称：owner 接缝、机器写前门和两存储恢复有了可验收窄切片。仍不能宣称 M8/M10/M11 模块完成、作者主循环完成、真实小说质量合格、产品可上线，或跨存储已经原子化。

来源：ChatGPT
