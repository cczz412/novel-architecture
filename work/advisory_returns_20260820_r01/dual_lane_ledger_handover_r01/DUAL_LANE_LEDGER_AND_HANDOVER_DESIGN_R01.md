# 双车道、章事实稿、十本账与检查交接设计 R01

- 工件身份：`ADVISORY_DESIGN_ONLY`
- 任务范围：外来正文道、自产章事实稿道、十账户籍、M11 供料、T14 检查、C11 登记、事实确认、规划交接与失败恢复
- 代码判断点：小说运行差量止于 `01efc50d863bf01ac048dc6c50284fcebc7e51f4`；本窗口代码／合同／测试取自 `79bd2e2d6d0eb28610d5ed4608288251c6ffa424` 的发布基线
- 权限：不调用 API，不改产品代码，不改 R14／R03，不生成 Gold，不替 CZ 冻结仍开放的产品决定

## 结论

✅ 两条路线必须共享“章节身份”和“作者确认权”，但不能共享错误的入料步骤：

- **外来道**继续是 `C10 → C11 文本修订 → C1 current → M2 → M3 → M4 → M5`。外来书稿是逐字证据源。
- **自产道**应是 `M8 → M11 → 章事实稿 → T14 → 作者明确交棒 → C11 结构化章节修订 → 逐条事实状态 → planstore 消费既有 chapter_id`。自产道的 **M2、M3 调用数必须为 0**。
- 章事实稿不能复用旧 `WORK_DRAFT` 的正文语义。可复用的是“稳定 lineage、单调 revision、current/stale、幂等保存”这些机械做法。
- 正式稳定章节身份仍由 **C11 的 `chapter_id + revision_no`** 承接；交棒前只使用章槽派生的章事实稿 lineage 和自己的 draft revision，不能提前伪造 chapter_id。
- 事实确认推荐 **“整包提交＋逐条状态”**：作者一次提交整章，普通项可批量确认，高影响项单签，未决项保持待确认；下游只读已确认项。这个推荐必须由 CZ 冻结后才能施工。
- AuthorWorkspace 与 planstore 按两次真实提交处理。`AW_COMMITTED_PLANSTORE_PENDING` 是合法、可见、可恢复的中间态；planstore 失败不能删除已提交的 C11 章节。
- 当前代码已证明不少机械切片可用，但**正式自产 C11 内容类型、自产事实准入、跨物理存储恢复、统一十账取件窗口仍不存在**。

---

## 1. 材料与测试核对

### 1.1 发布身份

本轮已核对：

- Project Sources release：`PROJECT_SOURCE_RELEASE_8e66fe30e71fdfed`
- 8 件发布工件 SHA-256 全部与 `RELEASE_SHA256SUMS` 一致
- workspace baseline：`WORKSPACE_BASELINE_79bd2e2d6d0e_1ea1f200`
- resolved commit：`79bd2e2d6d0eb28610d5ed4608288251c6ffa424`
- 窗口 ZIP 内部：237 件校验通过
- 窗口 route 中 223 份代码／合同／测试与 Project Sources baseline 逐字一致

### 1.2 当前测试证据

| 证据 | 结果 | 边界 |
|---|---:|---|
| 包内上游测试基线 | 1542 passed | 排除了 2 份依赖未版本化 TEMP fixture 的旧测试；不能写“全套通过” |
| 本轮章事实稿原型 | 36 passed | 证明有序条目、水位、SHA、文件安全与作者页；不证明正式 C11 |
| pending／M11／十账登记 | 41 passed | 证明保存、重启读回、只读双分区与户籍登记；不证明内容账齐全 |
| T14 结果／变化／unknown／full_check | 73 passed | 证明四种引文状态、覆盖完成语义、unknown 覆盖层与只读预检 |
| 章节 admission／handover 机械恢复 | 16 passed | 证明旧正文路线里的阶段和重放做法；不证明两个物理存储原子 |
| M5 batch／外来道读门 | 54 passed | 证明逐条状态可批量一次提交、外来 C10→C11→C1 current 读门 |
| **本轮定向复跑合计** | **220 passed** | 只认机械行为，不外推真实小说语义质量 |

窗口 route 未包含完整 `cli.py`，两份 CLI 依赖测试无法在该裁剪包内收集；本设计没有把它们作为唯一证据。

---

## 2. 双车道总图

```text
┌────────────────────────────── 外来正文道 ──────────────────────────────┐
│ 外来文件／外部手写书稿                                                 │
│   ↓ M1/C10：保存逐字 source、材料身份、来源 SHA、CONFIRMED+CHAPTER      │
│ C10 外来材料真源                                                       │
│   ↓ C11 INITIAL/REPLACE：stable chapter_id + text revision             │
│ C11 文本修订链 ──物化──> C1 current 文本                               │
│   ↓                                                                     │
│ M2 责任段 → M3 候选 → M4 C4 候选 → M5 作者逐条／批量明确处置           │
│   ↓                                                                     │
│ 仅 current + confirmed + VERIFIED 的事实供 M6/M7/M8/M9/M10/M11 使用    │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────── 自产章事实稿道 ──────────────────────────┐
│ M8 当前下一章规划 + 长线                                                │
│   ↓                                                                     │
│ M11 材料包：                                                            │
│   A. 已发生且已确认事实   B. 未来计划／写法批注（明确不是事实）          │
│   ↓ 作者编排                                                           │
│ AuthorWorkspace 章事实稿 owner：稳定 lineage + draft revision + 条目引用│
│   ↓ T14 只查未交棒当前 draft revision                                   │
│ T14 completed=覆盖判断完成，不等于全绿；unknown 裁决只加覆盖记录        │
│   ↓ full_check closeout 只证明引用了 current completed result           │
│ 作者明确交棒 + 作者确认 INITIAL 标题（方案 A）                          │
│   ↓ AuthorWorkspace 单存储提交                                          │
│ C11 结构化章节修订 + 章节目录 + 逐条事实准入状态                         │
│ operation = AW_COMMITTED_PLANSTORE_PENDING                              │
│   ↓ planstore 只消费既有 chapter_id/revision ref                        │
│ mapping + handover_parts                                                │
│   ↓ 独立 AuthorWorkspace ACK                                            │
│ HANDOVER_COMPLETE                                                       │
│   ↓                                                                     │
│ M8 可开下一章；M2=0，M3=0；下游只读已确认事实                           │
│                                                                         │
│ 可选分支：C11 章事实修订 ──渲染──> 正文投影／导出附件                    │
│           作者改正文产生新信息 ──只做差异候选──> 作者确认               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.1 每一步生成什么、保存在哪、怎样接、谁使用

| 车道／步骤 | 生成什么 | 保存在哪 | 怎样接下一步 | 谁使用 | 当前诚实状态 |
|---|---|---|---|---|---|
| 外来 1：C10 入料 | source bytes、material unit、身份 revision、source span | C10 owner | 必须是 current `CONFIRMED + CHAPTER` | C11 INITIAL、审计 | 正式合同与读门已有 |
| 外来 2：C11/C1 | stable chapter_id、文本 revision、C1 current | C11 ledger + C1 projection | C1 ref、标题、文本 SHA 必须等于 C11 current | M2、展示、修订迁移 | 正式合同已有；当前运行仍有 legacy 边界 |
| 外来 3：M2/M3 | C2 责任段、C3 候选 | 模块输出／受控 owner | 全部携带同一 current chapter revision ref | M4 | 当前机械切片已有 |
| 外来 4：M4/M5 | C4 候选、作者确认／驳回／改写状态 | facts owner | 只有 current confirmed + VERIFIED 可下游消费 | M6～M11 | 单条与 batch 机械事务已有 |
| 自产 1：M8/M11 | 当前规划、当前确认事实包、未来计划、写法批注、长线参考 | 只读短命包 | 各区带角色和来源水位 | 章事实稿、T14 | 原型可运行，写入 0 |
| 自产 2：章事实稿 | 有序事实句＋独立写法批注＋来源水位 | **待补正式 AuthorWorkspace owner** | current draft revision 才可 T14/交棒 | 作者、T14、C11 admission | 现在只有纯对象 prototype 与 pending request |
| 自产 3：T14 | completed 检测结果、findings、unknown 覆盖记录、closeout 引用 | T14 result owner | 精确绑定当前章事实稿 revision | 作者、交棒前审查 | 现役对象仍绑定 WORK_DRAFT，需窄适配 |
| 自产 4：C11 admission | 结构化章事实 revision、stable chapter_id、章节目录、事实准入清单 | AuthorWorkspace | operation 进入 pending | facts owner、planstore bridge、M7/M9/M11 | 正式自产内容类型和 consumer 缺失 |
| 自产 5：事实状态 | 每条事实独立状态与作者签字身份 | facts owner | confirmed 子集立即供下游；未决不消费 | M6～M11 | M5 batch 可借；自产 admission 缺失 |
| 自产 6：planstore | existing chapter ref 的 mapping/handover_parts | planstore | 成功 receipt 再由 AW 写完成标记 | M8、审计、恢复器 | 旧代码有单工作区机械样例；物理双存储缺失 |
| 自产 7：正文出口 | 可选渲染正文、段落→事实来源映射 | 投影／附件 owner | 不反写 C11/facts；作者改动只出差异 | 作者、导出、可选 M7 | 当前正式挂载合同缺失 |

---

## 3. 六类内容不能混账

| 内容 | 身份 | 能否表示“已发生” | 何时 current/stale | 能否直接写事实账 |
|---|---|---:|---|---:|
| M11 已确认事实包 | 已发生、current、confirmed 的前情 | 是，限原事实本身 | facts/chapter snapshot 任一变化即旧包过期 | 否；它只读已有事实 |
| M11 未来计划 | 准备这样写，尚未发生 | 否 | plan/slot/event rev 变化即过期 | 否 |
| 章事实稿条目 | 作者拟定“本章将按此登记”的事实句 | 交棒并按确认规则入账后才是 | draft rev、来源水位或 C11 revision 变化即旧 | 只能经正式 admission + 作者状态 |
| 写法批注 | 怎么表现、怎么写 | 否 | 跟随 draft/plan 来源 | 永不 |
| T14 judgment | 对当前 draft 是否覆盖／冲突的诊断 | 否 | draft/result/source 任一变化即 stale | 永不 |
| 渲染正文 | 章事实稿的可选展示／导出投影 | 否，不能单独裁决 | 绑定 exact C11 revision + renderer identity | 永不；新信息只升差异候选 |

🔥 **“计划被写进章事实稿”仍不等于已经发生；“T14 covered”也只表示稿内覆盖，不表示事实 confirmed。**

---

## 4. 章事实稿身份与版本设计

### 4.1 唯一推荐

采用两段身份，不提前发正式章号：

1. **交棒前**：AuthorWorkspace 内新增独立 `CHAPTER_FACT_DRAFT` 语义 owner。
   - lineage 从稳定 `slot_ref` 派生；
   - 保存作者当前有序事实句和写法批注；
   - 使用自己的单调 `draft_revision`；
   - current/stale、expected revision、operation replay 沿用工作稿已验证的机械做法；
   - 绝不叫 `WORK_DRAFT`，绝不发 chapter_id/fact_id。
2. **交棒成功后**：C11 继续拥有 stable `chapter_id` 和正式 `revision_no`。
   - INITIAL 时由 C11 owner 在成功提交里分配；
   - 后续修改在同一 chapter_id 下追加 revision；
   - 恢复旧内容也追加新 revision，不回拨；
   - planstore 只能消费 C11 已存在的 ref。

这同时满足：交棒前可编辑、可 T14、可判 stale；交棒后有稳定章节历史；没有第二套正式章节号。

### 4.2 当前 prototype 可直接复用的字段

| prototype 字段 | 复用方式 | 状态 |
|---|---|---|
| `slot_ref`、`slot_rev`、`source_outline_ref` | 作为 draft lineage 与规划来源门 | 可直接复用 |
| `source_plan_version`、`source_plan_sha256` | 当前规划水位 | 可直接复用 |
| `source_commit_seq` | 当前 outline/source 提交水位 | 可直接复用 |
| `chapter_slot_snapshot_sha256` | 证明构稿时看到的完整章槽快照 | 可直接复用 |
| `generation_watermark` | 保守水印；只做过期判断，不静默改字 | 可直接复用 |
| `entries[].fact_text` | 作者逐字事实句 | 可直接复用；全空白必须拒绝 |
| `entries[].writing_note` | 独立写法批注 | 可直接复用；不得升事实 |
| `operation_id`、`actor=author` | 幂等保存／作者动作 | 可直接复用 |
| `author_confirmed_title` 的动作位置 | 继续由作者在 INITIAL 交棒动作中明确给出，成功后长期 owner 转给 C11 | 只复用动作位置；当前 prototype 仅校验“非空”，正式方案 A 还必须校验单行、首尾无空白且不得猜测／补默认标题 |
| `prototype_sha256` 的做法 | 升格为正式 payload 完整性摘要 | 可复用算法，不沿用 prototype 身份名 |

### 4.3 当前缺失、必须补的窄字段

这些是设计候选，字段名需合同冻结：

- 稳定的章事实稿 lineage ref；
- 单调 draft revision；
- expected draft revision + expected payload SHA；
- 每条事实句的**局部稳定 entry ref**，用于改稿、撤回、逐条状态和下游失效；它不是 fact_id；
- last operation ID／保存 receipt；
- M11 bundle SHA 与 source snapshot set；
- current/stale 读取结果。

⚠️ 当前 prototype 只有“有序数组＋整包 SHA”。没有局部 entry ref 时，重排一条就无法安全判断哪条事实沿用、哪条需要重签。

### 4.4 不能复用的字段／语义

- 不能复用 `WORK_DRAFT.work_ref/work_rev` 的名称和正文语义；
- 不能把章事实 payload 塞进 C11 v1 的 `text_sha256/chars/C10_SOURCE_SPAN`；
- 不能把 prototype `effects=none` 冒充正式提交 receipt；
- 不能在 pending request 阶段分配 chapter_id/revision_no/fact_id；
- 不能拿 `slot.title_hint`、文件名、空串、当前时间补正式标题或身份；
- 不能沿用当前 chapter-fact prototype “只要非空就通过”的标题 validator；方案 A 的正式门必须是作者明确输入、单行、首尾无空白。

### CZ-01｜需要冻结

**推荐冻结：**“交棒前是 slot 派生的章事实稿 lineage + 单调 draft revision；交棒后由 C11 承接 chapter_id + revision_no；每条事实句有局部稳定 entry ref。”

CZ 未冻结前，施工只能停在 prototype/pending 层，不能假装已经有正式版本身份。

---

## 5. 事实确认粒度：三案比较与唯一推荐

| 方案 | 作者体验 | 改稿／撤回 | 下游失效 | 恢复成本 | 主要风险 |
|---|---|---|---|---|---|
| 逐条确认 | 控制最细，但几十条连续点击最累 | 单条最清楚 | 最细粒度 | 操作与回执最多 | 确认疲劳，作者可能机械点完 |
| 整包确认 | 一次最省事 | 一条有错会牵连整包；局部撤回难 | 常被迫整章失效 | 恢复最简单 | 把未看清的高影响事实一起签进真值 |
| **整包提交＋逐条状态** | 一次看到全章；普通项批量，高影响项单签；未决项可保留 | 单条修改、撤回、重签都清楚 | 只让受影响条目及依赖 stale | 一个包 receipt + 每条状态，仍可重放 | 需要稳定 entry ref 和明确状态规则 |

### 5.1 推荐的作者动作

✅ 推荐 **整包提交＋逐条状态**：

- 作者交棒时提交的是**整个章事实稿版本**；
- 系统同时展示每条事实的状态清单；
- 普通低影响项可在一次 batch 动作里确认；
- 高影响项必须单独勾选／签字；
- 作者未决定的项保持待确认，不用编默认值；
- rejected/撤回项保留历史，但不供下游；
- 一次保存要么整包 C11 revision 与这批 per-item admission 完整落下，要么 AW 内全部不落；
- 下游永远只读 per-item 已确认项，不因“整包已提交”自动读全部。

这套做法能让作者交棒后立刻规划下一章，同时不要求把所有未决项点完：M8/M11 使用已确认子集；关键前提仍待确认时，明确提示材料不足，不偷偷拿计划或 pending 项顶上。

### 5.2 改稿与失效规则

- 同一 entry ref、文本未变：可沿用原状态和来源关系；
- 同一 entry ref、文本变化：该条回到待确认／重签，直接依赖 stale；
- entry 删除：该条退出 current，依赖 stale；
- entry 新增：新 admission，不继承邻近条目状态；
- 仅重排且 entry ref/文本未变：事实身份不变，章内呈现顺序更新；
- 写法批注变化：不影响事实状态，除非它实际改了 fact_text；
- C11 revision 变化不能让所有旧事实自动继续 current，必须按 entry ref + content SHA 做确定性迁移。

### 5.3 与当前代码怎样接

可借用：

- `FACT_REVIEW_ACTION v1` 的 author-only、expected status、expected record SHA；
- `review_workspace.apply_review_batch` 的跨同一 revision 批量一次提交；
- 同 operation 同载荷重放、同号异载荷拒绝；
- batch 中任一坏动作时整批 0 写入。

不能直接照搬：

- 当前 C4 的初始状态名 `extracted` 带 M3/M4 抽取语义；自产条目不应假装“抽取所得”；
- 当前 FACT_REVIEW_ACTION 只改已有 fact_id；自产 admission 需要 facts owner 在提交时发号，调用方不能预填；
- 当前 C4 VERIFIED anchor 依赖章节正文文本；自产事实应带作者签字／C11 structured entry 来源，不伪造原文 anchor。

### CZ-02｜必须冻结

**推荐冻结：整包提交＋逐条状态；普通项允许 batch，高影响项单签；初始未确认状态使用中性语义，不叫 extracted。**

同时需要 CZ 冻结：哪些高影响事实必须单签、未决项是否允许完成章节交棒、作者撤回已确认自产事实的正式动作。

---

## 6. C11 存章事实稿，正文作为可选出口

### 6.1 现有 C11 为什么不能直接用

当前 `C11_CHAPTER_REVISION_LEDGER v1` 明确保存：

- `text_sha256`、`chars`；
- `content_ref = C10_SOURCE_SPAN | LEGACY_C1_SNAPSHOT`；
- C1 是 current 文本物化视图。

章事实稿是结构化有序条目，不是 C10 外来 source span，也不是 legacy C1 文本。把 JSON 串进 `text` 或把 payload SHA 填成 `text_sha256` 都会破坏合同语义。

### 6.2 推荐的 C11 双内容形状

C11 仍然只管一个 stable chapter revision chain，但 revision 明确区分两类内容：

- **外来文本 revision**：沿用 C10 source span + text SHA + C1 current；
- **自产章事实 revision**：引用 AuthorWorkspace 中不可变的章事实 payload，带 payload kind、payload SHA、条目数、来源 draft ref/revision、水位与作者交棒 action。

正式字段名和 schema 版本需要另行冻结；这里不把候选名冒充合同。

### 6.3 可选渲染正文的挂载方式

渲染正文应是 revision 的**派生附件／投影**：

- 精确绑定 `{chapter_id, revision_no, chapter_fact_payload_sha}`；
- 记录 renderer identity/version、生成参数摘要和输出 SHA；
- 每段保存它引用的 chapter-fact entry refs；
- 可以没有，可以有多个版本，可以重渲染；
- 不改变 C11 current，不改变 per-item facts，不触发 actual；
- 作者只改写法、不新增事实时，更新投影即可；
- 作者改出新信息时，只对变更片段产生差异候选，由作者确认；M2/M3 仍为 0。

### 6.4 C1 的兼容边界

✅ 推荐：**自产章默认不生成 C1 文本真值。**

- 需要导出正文时，读取渲染附件；
- 旧消费者只会读 C1 时，必须走明确的 compatibility projection adapter，并标注它是渲染投影；
- 只有作者另行明确采纳某份渲染正文为文本资产时，才讨论是否生成独立文本投影；这仍不能反过来覆盖章事实稿真值；
- M7 对自产章的主检查对象是 C11 current 章事实 revision；有渲染附件时可增加“出口质量”检查，但不能只看投影。

### CZ-03｜需要冻结

**推荐冻结：C11 revision 支持 external-text 与 native-chapter-fact 两种 content kind；自产正文只作可选 attachment，不自动物化为 C1。**

CZ 还需决定：旧只读界面必须看到正文时，是接受 compatibility projection，还是在界面层直接渲染而不落持久文本。

---

## 7. M11 供料怎样进入章事实稿与 T14

### 7.1 当前可直接复用的防混账门

`chapter_fact_material_bundle_workspace` 已经分开：

- `CURRENT_CONFIRMED_FACTS_ALREADY_OCCURRED`
- `FUTURE_PLAN_AND_WRITING_NOTES_NOT_FACT`

并锁定：plan/facts/chapter index 三类 snapshot、bundle SHA、workspace binding、writes=none。

### 7.2 正式接线

1. M11 只生成带角色的材料包，不直接生成事实；
2. 章事实稿 builder 读取：
   - 当前确认事实：只做前提／禁冲突材料；
   - 未来计划：只做本章拟实现目标；
   - 写法批注：单独旁挂；
3. 作者明确把某个计划转写成 fact_text 时，该条仍是**当前 draft 的 proposed fact**；
4. T14 输入包保存三个独立区：
   - prior confirmed facts；
   - future plan requirements；
   - current chapter-fact entries；
5. provider 只能给 judgment，不能改这三个区的身份；
6. T14 `covered` 只说明 current draft 覆盖了 requirement；不写 facts、不改 plan；
7. 交棒后，plan 保留“当初的打算”，另由明确 reconciliation 表示完成／偏离，不能因覆盖自动标 actual。

### 7.3 stale 门

下面任一变化都必须让旧 T14 result 失效：

- chapter-fact draft revision 或 payload SHA；
- source plan version/SHA；
- slot rev/outline source commit；
- M11 bundle SHA；
- prior facts snapshot 或 chapter index snapshot。

水印只负责发现变化和要求重编，不删除、纠正或补写作者句子。

---

## 8. T14、unknown、full_check 与 closeout 分工

| 对象／动作 | 负责什么 | 不负责什么 |
|---|---|---|
| T14 input package | 冻结 current 章事实稿、规划 requirement、当前事实与来源水位 | 不确认事实，不交棒 |
| T14 result | 每个 requirement 都得到 judgment；`completed`=覆盖判断完成 | 不表示全绿，不改稿，不写 facts/plan |
| finding | mismatch/missing/unknown 等诊断及引文 | 不自动阻断／修复，阻断策略另定 |
| unknown author adjudication | 作者给 unknown 加一层 self-reported decision | 不改原 judgment；原 category 仍为 unknown |
| full_check | closeout 动作引用一个 current completed result | 不要求 findings=0，不等于通过 |
| closeout | 记录作者结束本次检查／收工选择 | 不交棒、不关章、不写 C11/facts/actual |
| explicit handover | 作者确认当前章事实稿版本和 INITIAL 标题 | 不用 T14 结果替作者确认事实 |

### 8.1 必须保留的四种作者可读状态

| 机器状态 | 作者页文案 | evidence_quote |
|---|---|---|
| `missing_without_quote` | 明确缺失，所以没有引文 | `null` |
| `unknown_without_quote` | 无法判断，也没有可安全定位的引文 | `null` |
| `unknown_with_quote` | 有相关引文，但仍无法判断 | 非空逐字子串 |
| `quoted` | 有逐字引文 | 非空逐字子串 |

当前 `writing_check_result_tool.evidence_text_kind` 与变化视图已经做到：

- 空字符串、纯空白字符串都拒绝；
- missing 不能夹带引文；
- unknown 可有引文或无引文；
- covered/mismatch/unplanned 必须有逐字引文；
- 作者裁决只追加 overlay，原 unknown 不变；
- full_check 只验 current completed result。

需要补的是**章事实稿 identity adapter**，不是重写这套语义。

### CZ-04｜建议冻结

推荐交互：交棒前必须有一条 closeout receipt；`full_check` 引用 completed result，若产品保留 `skip_check`，也必须是作者明确选择并留下独立 receipt。无论哪条路，都不能把 `completed` 或 full_check 写成“全绿”。

是否允许没有任何 T14 closeout 就交棒，仍需 CZ 决定。

---

## 9. 十本账：当前真实能力与最小接线

### 9.1 当前代码重判

| 账本 | 当前可确认能力 | 当前等级 | 最小下一步 |
|---|---|---|---|
| 章节账 | C11/C1 文本 revision、INITIAL admission、current 读回、重启恢复；自产内容类型未接 | **已有可复用读写切片** | 增加 native chapter-fact content adapter |
| 事实账 | C4 保存/current filter、M5 单条与 batch、重启读回 | **已有可复用读写切片** | 增加自产 entry admission／author attestation 来源 |
| 规划账 | plan/slot/selection/handover 的读写与版本水位 | **已有可复用读写切片** | 改成真实 planstore consumer + receipt query |
| 长线账 | 当前 storylines/hooks 的只读投影视图；没有独立 owner/write contract | **散落材料＋只读切片** | 先登记 plan-owned read adapter，不造新库 |
| 人物账 | 人物锚和状态散在 facts/scene/plan；无独立版本 owner | **散落材料** | 目录只报 unavailable/scattered，M11 暂从已确认 facts 取 |
| 地点账 | 地点信息散在 scene/facts；无独立版本 owner | **散落材料** | 同上 |
| 世界规则账 | must_not/规则散在 plan/facts；无独立版本 owner | **散落材料** | 同上；不把未来禁写规则当已发生事实 |
| 物品账 | 只有十账户籍名称；内容可能出现在 facts，但无专门 owner | **只有登记** | 暂不声称专账可读写 |
| 势力账 | 同上 | **只有登记** | 暂不声称专账可读写 |
| 体系账 | 同上 | **只有登记** | 暂不声称专账可读写 |

### 9.2 目录代码已经有什么

`ledger_directory_workspace` 当前能：

- 初始化固定十账名称和顺序；
- 重启读回；
- 叠加调用方提供的 capability snapshot；
- 要求非 reusable 的账内容状态必须是 UNKNOWN；
- 不创建具体账本、不替模块写内容。

这正好适合“户籍处”，但它还不是统一取件窗口。

### 9.3 统一取件窗口还缺什么

只补一个薄路由，不做数据库平台：

- 目录项到 owner-specific reader 的明确映射；
- 请求必须带 ledger name、用途、所需范围与权限；
- 返回统一 envelope：ledger identity、owner、content role、source version/SHA、item refs、omission/unavailable reason；
- 跨多个 owner 读取时先读水位、取内容、再复读水位，任一变化整包拒绝；
- M11 只通过这些 reader 取料，不遍历任意 AuthorWorkspace logical key；
- 写入仍走各模块自己的 writer，目录永远无写真值权；
- v1 只接章节、事实、规划三个可读写 owner，加长线只读 adapter；其余账诚实返回 scattered/unavailable。

---

## 10. `AW_COMMITTED_PLANSTORE_PENDING → HANDOVER_COMPLETE` 恢复设计

### 10.1 三个真实动作，不冒充一个事务

```text
A. AuthorWorkspace commit
   - C11 native chapter-fact revision
   - chapter index/current pointer
   - per-item fact admission/status manifest（按 CZ 决定）
   - handover operation = AW_COMMITTED_PLANSTORE_PENDING

B. planstore commit
   - 只消费 A 产生的 existing chapter_id/revision ref
   - 写 slot mapping + handover_parts
   - 返回可查询的 operation receipt + request SHA + plan after SHA

C. AuthorWorkspace ACK commit
   - 读取 B 的精确 receipt
   - operation = HANDOVER_COMPLETE
   - 保存 plan receipt pointer/SHA
```

A、B、C 使用不同阶段 operation ID；B 的业务请求必须由 A 的不可变 ref 和 request SHA 唯一决定。

### 10.2 幂等恢复算法

当 AW 仍是 pending：

1. 读取并校验 C11 current ref、draft source、slot/outline 绑定；
2. 按 plan operation ID 查询 planstore receipt；
3. receipt 不存在：
   - 重新读取 plan current；
   - 语义目标未变则重试 B；
   - slot 已改绑／已映射其他章则回作者；
4. receipt 存在且 request SHA、chapter ref、mapping/part、plan after SHA 全匹配：
   - 不再写 plan；
   - 只补 C；
5. receipt 存在但载荷不一致，或 journal/SHA 不能判断 before/after：
   - `NEEDS_MANUAL_RECOVERY`；
   - 禁止猜测和重复新增 mapping。

### 10.3 作者看到什么

| 情况 | 作者页状态 | 作者能做什么 |
|---|---|---|
| A 成功、B 未开始／暂时失败 | **章节已保存，规划交接待完成** | 查看章节、继续处理其他内容；不可把它当完整交棒；可安全重试 |
| B 已成功、C 未写 | **规划已接收，完成标记待恢复** | 不重复点击提交；系统只补标记 |
| plan 纯版本冲突但目标语义未变 | **正在重新核对规划水位** | 系统可自动重试 |
| slot 改绑、outline 不兼容、chapter current 已变 | **章节已保存，但交接目标需要作者确认** | 选择新目标、另发修订或取消映射；系统不自动重绑 |
| receipt/SHA/journal 分歧 | **章节已保存，交接需要人工恢复** | 禁止新交棒覆盖；导出诊断包 |
| C 完成 | **交棒完成** | M7 可查当前已交棒内容；M8 可进入下一章 |

### 10.4 失败不变量

- planstore 失败不删除、回滚或隐藏 C11 revision；
- pending 不是失败，也不是 complete；
- B 已提交时重试不得新增第二条 mapping/handover part；
- planstore 不接章事实全文、标题或 caller-supplied chapter_id；
- C 只是完成 marker，不把 handover 扩大解释为关章、全事实确认或全绿；
- 作者取消交棒不能用“删除 C11”当默认补偿事务。

### CZ-05｜需要冻结

推荐：作者在 A 成功后取消交棒时，保留该 C11 revision 为“已保存、未映射”，后续用新 revision／新显式动作处理；不提供自动删除补偿。是否另做专门删除流程需 CZ 单独决定。

---

## 11. 当前代码分类

### 11.1 `DIRECTLY_REUSABLE`

- C11 的 stable chapter_id、单调 revision、append-only、restore-as-new-revision 原则；
- `chapter_slot_snapshot_tool` 的 plan/slot/outline 水位；
- `chapter_fact_draft_tool` 的有序条目、逐字保留、完整 SHA；
- `chapter_fact_handover_tool` 的显式 author intent、精确 source prototype SHA、标题方案 A 的动作位置；其现有“仅非空”标题校验不直接复用；
- `chapter_fact_handover_workspace` 的 pending 保存、重启读回、current preflight；
- M11 bundle 的 current-fact / future-plan role 分离与 source snapshots；
- T14 的 judgment 规则、四种引文状态、completed 语义；
- unknown overlay 不改原 judgment；
- full_check 只引用 current completed result；
- M5 batch 的 per-item action + 一次提交 + 失败整批 0 写；
- 十账户籍固定名称、顺序、显式初始化；
- 旧 chapter admission/handover 中的 stage、exact replay、crash recovery 测试思想。

### 11.2 `NARROW_ADAPTER_REQUIRED`

- 独立 `CHAPTER_FACT_DRAFT` owner 与 revision；
- 标题方案 A 的严格 validator：作者明确输入、单行、首尾无空白，禁止猜测和默认值；
- M11 bundle → draft builder，保留内容角色；
- T14 从 WORK_DRAFT 绑定改为 chapter-fact draft 绑定；
- C11 支持 native structured chapter content；
- optional rendered prose attachment + paragraph provenance；
- 自产 entry → facts admission，使用 author attestation，不伪造 text anchor；
- planstore 只消费 committed chapter ref；
- 两物理存储 receipt query + AW ACK；
- 十账 owner-specific read router。

### 11.3 `CZ_DECISION_REQUIRED`

1. 章事实稿正式 draft lineage/revision 与局部 entry ref 的字段合同；
2. 事实确认采用“整包提交＋逐条状态”，以及初始状态名／高影响单签表；
3. C11 native content kind 与 C1 compatibility projection 边界；
4. T14 closeout 是否是交棒硬门，skip_check 是否保留；
5. A 成功后作者取消交棒的保留／删除政策。

---

## 12. 施工卡依赖顺序

| 顺序 | 卡号 | 目标 | 阻断 |
|---:|---|---|---|
| 1 | `DLH-01` | 章事实稿正式 owner、draft revision、entry ref | CZ-01 字段冻结 |
| 2 | `DLH-02` | M11 角色防火墙与 T14 chapter-fact adapter | DLH-01；CZ-04 只影响交棒门，不影响结果层 |
| 3 | `DLH-03` | C11 native chapter-fact content + 可选正文附件 | DLH-01；CZ-03 |
| 4 | `DLH-04` | 整包提交＋逐条事实状态与作者签字来源 | DLH-01/03；CZ-02 |
| 5 | `DLH-05` | AuthorWorkspace phase A 单存储提交 | DLH-02/03/04 |
| 6 | `DLH-06` | planstore phase B + AW ACK + 恢复作者页 | DLH-05；CZ-05 只影响取消分支 |
| 7 | `DLH-07` | 十账薄取件路由，先接章节／事实／规划／长线只读 | DLH-03/04/06 的 owner 读接口 |

完整输入、输出、保存、使用、失败状态、最小写集、测试、禁改和剩余边界见同包 `DUAL_LANE_LEDGER_TASK_CARDS_R01.json`。

---

## 13. 不能在这些卡完成后宣称什么

- 不能宣称 AuthorWorkspace 与 planstore 跨存储原子；
- 不能宣称所有十本账已有内容 owner；
- 不能宣称章事实稿交棒等于全部事实 confirmed；
- 不能宣称 T14 completed/full_check 等于全绿；
- 不能宣称可选渲染正文是真源；
- 不能宣称自产章经过或需要 M2/M3；
- 不能宣称 M7 已经能查 native chapter-fact content，除非它的 reader adapter 与直接测试另行通过；
- 不能宣称真实小说语义质量已经由机械测试证明。

---

## 14. 主要证据路径

### Project Sources

- `00_PROJECT_SOURCE_ROUTER_PROJECT_SOURCE_RELEASE_8e66fe30e71fdfed.md`
- `PRODUCT_R14__SEMANTIC.md`
- `ATOMIC_R03__142_EXPECTATIONS.csv`
- `WORKSPACE_BASELINE_79bd2e2d6d0e_1ea1f200__INDEX.json`

相关原子预期：`M1-E06`、`M4-C05`、`M4-N01`、`AE-X-N01`、`AE-X-N02`、`AE-X-N03`、`AE-AW-N01`、`AE-M11-C01`、`AE-M11-C02`。

### 当前代码／合同

- `02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`
- `02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`
- `02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`
- `02_current_route/novel-mvp/mvp/chapter_fact_material_bundle_workspace.py`
- `02_current_route/novel-mvp/mvp/chapter_fact_material_bundle_tool.py`
- `02_current_route/novel-mvp/mvp/writing_check_result_tool.py`
- `02_current_route/novel-mvp/mvp/writing_check_unknown_adjudication_workspace.py`
- `02_current_route/novel-mvp/mvp/writing_closeout_workspace.py`
- `02_current_route/novel-mvp/mvp/chapter_initial_admission_workspace.py`
- `02_current_route/novel-mvp/mvp/chapter_handover_workspace.py`
- `02_current_route/novel-mvp/mvp/review_workspace.py`
- `02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`
- `02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`
- `02_current_route/novel-mvp/contracts/WRITING_DESK_CHECK_RESULT.md`
- `02_current_route/novel-mvp/contracts/WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION.md`
- `02_current_route/novel-mvp/contracts/WRITING_DESK_CLOSEOUT_ACTION.md`
- `02_current_route/novel-mvp/contracts/FACT_REVIEW_ACTION.md`

旧 `OWNER_GAPS_AND_HANDOVER_DESIGN` 只用于发现恢复模式线索；本报告没有沿用它的“工作稿→C10”自产语义。

来源：ChatGPT
