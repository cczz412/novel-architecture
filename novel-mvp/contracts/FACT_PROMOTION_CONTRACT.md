# 正式事实晋级｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[正式事实晋级机器合同 v1｜三类来源、证据与章末结算](https://linear.app/ccz/document/0f53514ba07d)（文档 ID：`20944fa7-87c9-4d77-a544-d318238f3737`）。
> 原版本：FACT_PROMOTION_CONTRACT v1；请求 FACT_PROMOTION_REQUEST v1；回执 FACT_PROMOTION_DECISION_RECEIPT v1。
> 原文区 SHA-256：`56e8a61f09e402512a3da59a7e5f0fe570d065600ff6fdbb5a8f160c6de343fd`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 承载票：CCZ-86
> 合同身份：`FACT_PROMOTION_CONTRACT`
> 产品版本：`v1`
> 基线：GitHub `main@56a623b2e42e649c975177374ea27a2e3df15431`
> 状态：产品合同已冻结；runtime 尚未授权、尚未实现
> 执行身份：Codex

## 1. 这份合同解决什么

它只回答一件事：一个事实候选在什么条件下可以变成正式事实，以及系统必须留下哪种真实来源。

正式事实有三类晋级来源：作者亲自采用、系统在有效托管权限下采用、章节验收通过后的章末结算提交。三者必须互斥，不能把系统动作或章末结算伪装成作者签字。

候选怎样抽出来，和候选怎样晋级，是两条不同的轴。正文抽取来自 CCZ-142；本合同只消费其稳定候选版本，不接管抽取算法。正式事实的稳定编号、历史版本、原子持久化和重开由 CCZ-82 承担。

## 2. 两条身份不能混

### 候选形成来源

字段名为 `candidate_provenance_kind`，只允许：

| 值 | 中文含义 | 必须带什么 |
| -- | -- | -- |
| `PROSE_EXTRACTION` | 从正文抽取 | current 章节版本、可回验正文锚、候选版本；隐含表达还要有推导记录 |
| `AUTHOR_DECLARATION` | 作者直接声明 | 作者声明动作和当时可见内容；不得伪造正文锚 |
| `SYSTEM_PROPOSAL` | 系统提出候选 | 模型／规则版本、输入来源和候选回执；它仍不是正式事实 |
| `CHAPTER_LOCAL_DELTA` | 本章尚未结算的局部增量 | 章节内核、选中路径、本地增量集和形成回执 |

### 正式晋级来源

字段名为 `promotion_source_kind`，只允许：

| 值 | 中文含义 | 谁能提交 | 关键证据 |
| -- | -- | -- | -- |
| `AUTHOR_ADOPTION` | 作者亲自采用 | `AUTHOR` | 作者看到的候选版本、明确动作、动作回执；只有这类可以产生 `AUTHOR_ATTESTATION` |
| `DELEGATED_SYSTEM_ADOPTION` | 系统按托管权限采用 | `SYSTEM` | principal 作者、权限快照、范围、阶段、策略版本、未撤销证明；禁止产生 `AUTHOR_ATTESTATION` |
| `CHAPTER_CLOSEOUT_ADMISSION` | 章节验收通过后随章末结算提交 | `AUTHOR` 或获准的 `SYSTEM` 协调器 | 章节内核、选中路径、本地增量集、验收回执、结算操作和事务引用；禁止把整批事实伪装成逐条作者签字 |

`candidate_provenance_kind` 不决定 `promotion_source_kind`。例如正文抽取候选可以由作者采用，也可以在托管权限下由系统采用；本章局部增量只有通过章末验收后，才可以走章末结算。

## 3. 晋级请求

机器请求名为 `FACT_PROMOTION_REQUEST`，版本固定 `v1`。字段如下：

| 字段 | 类型 | 规则 |
| -- | -- | -- |
| `contract` | str | 固定 `FACT_PROMOTION_REQUEST` |
| `version` | str | 固定 `v1` |
| `operation_id` | str | 幂等动作号；同号同语义载荷回放原结果，同号不同载荷拒绝 |
| `candidate_ref` | str | 上游稳定候选号；不得拿它当正式事实号 |
| `candidate_version_ref` | obj | 上游候选代际、版本和 current 指针水位的精确引用 |
| `candidate_sha256` | str | 上游冻结候选内容的规范摘要 |
| `candidate_provenance_kind` | enum | 四类候选形成来源之一 |
| `promotion_source_kind` | enum | 三类正式晋级来源之一 |
| `submitted_by` | enum | `AUTHOR` 或 `SYSTEM`，必须与晋级来源相容 |
| `principal_author_id` | str | 真值所属作者；系统提交也不能改写 |
| `project_id` | str | 唯一项目绑定 |
| `scope` | obj | 点名对象、账本、章节范围、阶段和允许写入的业务边界 |
| `story_effective_time` | obj/null | 故事内生效位置或时间；无法表达时为 null 并进入待确认，禁止猜测 |
| `expected_current` | obj | 写前必须仍 current 的候选、章节、依赖、权限或结算水位 |
| `evidence_bundle` | obj | 候选证据、采用证据、权限证据或章末结算证据的互斥组合 |
| `decision` | enum | `ADMIT`／`REJECT`／`DEFER` |
| `write_plan` | obj | 交给 CCZ-82 的逻辑 owner 和原子组计划；不能带文件路径或绕过 writer |
| `reason` | str | 可空但不能省略 |

`REJECT` 和 `DEFER` 只允许作者动作，正式真值零写入。`DEFER` 不新增一个长期事实状态；它只返回本次没有采用。系统托管和章末结算只允许提交 `ADMIT`。

## 4. 三类来源各自的硬门

### 作者亲自采用

* `submitted_by` 必须是 `AUTHOR`。
* 必须点名作者实际看到的 `candidate_version_ref` 和 `candidate_sha256`。
* 必须有明确采用动作；“看起来不错”“全部都行”或模型推测不能代替。
* 只有这条路径可以产生作者签字证据 `AUTHOR_ATTESTATION`。
* 作者改写事实句后采用，改写文本和采用结果必须进入同一原子组。

### 系统托管采用

* `submitted_by` 必须是 `SYSTEM`，同时保存 `principal_author_id`。
* 必须引用不可变的权限快照：权限号、版本、策略版本、对象、动作、范围、阶段、有效期、撤销状态和摘要。
* 预览与执行之间权限被撤回、范围缩小或策略版本前进时，失败关闭并要求重新预览。
* 系统不能写 `AUTHOR_ATTESTATION`，不能把托管权限扩大成整项目长期写权。
* 高影响事实没有被权限快照明确允许时，转 `AWAITING_AUTHOR`，不自动采用。

### 章末结算提交

* 必须引用 current 章节内核、current 章节 revision、作者选中的路径、本章局部增量集和章末验收回执。
* 验收必须明确为通过；拒绝、待修、材料不全或来源前进时不形成晋级请求。
* 重大死亡、复活、身份揭露、强因果承诺等可以在章内形成增量，但只有结算通过后才进入正式组。
* 章末结算保存的是结算证据，不把每条增量伪装成作者逐条签字。
* 如果结算同时采用新章节正文，C11／C1 投影和受影响事实必须进入同一代提交；如果章节 revision 已经 current，本组只钉死其精确引用，不重复写 C11。

## 5. 证据规则

`evidence_bundle` 采用按来源分支的结构，只有当前分支需要的字段可以非空：

| 字段 | 什么时候使用 | 规则 |
| -- | -- | -- |
| `candidate_evidence_ref` | 所有路径 | 回到上游候选原件；正文抽取还要回到 current revision 的 VERIFIED 锚 |
| `author_action_ref` | `AUTHOR_ADOPTION` | 作者明确动作、看到的版本和动作时间 |
| `permission_snapshot_ref` | `DELEGATED_SYSTEM_ADOPTION` | 精确权限快照和执行时仍有效证明 |
| `chapter_closeout_ref` | `CHAPTER_CLOSEOUT_ADMISSION` | 章节内核、选中路径、增量集、验收与结算回执 |
| `inference_trace_ref` | 隐含正文事实 | 从正文锚到事实结论的可回读推导；不能用结论反填正文 |

正文抽取必须有正文证据。作者声明、系统采用和章末结算分别保存自己的动作、权限或结算证据；没有正文时不得制造假的 quote 或 anchor。

## 6. 作用范围与故事时间

`scope` 至少包含 `object_types`、`object_refs`、`ledger_names`、`chapter_refs`、`stage` 和 `write_boundary`。空数组表示没有获准对象，不表示全选。

`story_effective_time` 必须使用现行账本合同允许的故事时间形状。时间不明可以保留 null 或转作者确认；不得把提交时间、文件时间或章节序号直接冒充故事时间。

作者／项目绑定、稳定对象号、章节 revision、候选版本和权限范围任一不一致，整次失败关闭。权限检查完成前，不返回目标是否存在。

## 7. 交给 CCZ-82 的同代提交边界

本合同只产生一份冻结的 `promotion_plan`。CCZ-82 为正式事实分配稳定号，并负责 current／历史／撤回／重开。

`write_plan.atomic_groups[]` 每组至少点名：

* 正式事实记录与正式事实号分配；
* 晋级决定记录和本合同回执；
* 适用的作者动作、权限快照或章末结算引用；
* 适用的 C11／C1 投影；
* 十本账中真正受影响的增量；
* 依赖失效、current 指针和事务回执。

同一依赖连通组全成或全不成。互不依赖的候选可以分成独立原子组：一个组失败只隔离它和真正依赖它的组，干净组可以继续，但顶层必须诚实返回 `PARTIAL_INDEPENDENT_GROUPS`。

任一原子组内禁止出现事实已正式、来源记录没写、账本增量缺失或 current 指针提前前进。实现必须复用现有事实／规划事务协调器，不能为本合同增加第二套裸写入口。

## 8. 撤回、恢复与重开

* 已提交正式事实和来源证据只追加，不原地改写历史。
* 撤回必须点名 current 正式事实版本和预期摘要；受影响依赖在同一代转为失效或待复核。
* 恢复旧内容不能回拨 current 指针，只能形成新代，并引用恢复来源。
* 重开从某个历史决定产生新的候选／正式代；旧决定和旧权限快照继续可回读。
* 权限已经撤回时，历史系统采用仍可审计，但不得自动重放。
* 作者重新确认不会静默复活旧依赖；依赖必须重新验算。

## 9. 晋级回执

回执名为 `FACT_PROMOTION_DECISION_RECEIPT`，版本固定 `v1`，至少包含：

* `operation_id`、请求规范摘要和是否幂等回放；
* 候选引用、候选版本、正式晋级来源和实际提交者；
* 权限／章节结算／正文证据的精确引用；
* `outcome`：`ADMITTED`、`NO_CHANGE`、`REJECTED_BY_AUTHOR`、`DEFERRED_BY_AUTHOR`、`FAILED_CLOSED`、`AWAITING_AUTHOR`、`NEEDS_MANUAL_RECOVERY`；
* 原子组状态、逻辑写入计数、正式事实引用和 before／after 版本；
* 失败原因、可否重试和下一步；
* 回读结果。没有完成回读时不得报 `ADMITTED`。

## 10. 稳定失败身份

| 原因码 | 含义 | 处理 |
| -- | -- | -- |
| `PROMOTION_SOURCE_MISMATCH` | 来源类型、提交者或证据分支互相矛盾 | 修正请求，零写入 |
| `AUTHOR_ACTION_REQUIRED` | 作者路径没有明确动作 | 等作者，零写入 |
| `AUTHOR_ATTESTATION_FORBIDDEN` | 系统或章末路径试图伪造作者签字 | 拒绝，零写入 |
| `PERMISSION_SNAPSHOT_REQUIRED` | 系统路径缺权限快照 | 拒绝，零写入 |
| `PERMISSION_REVOKED_OR_STALE` | 权限撤销、过期或版本前进 | 重新授权／预览 |
| `PERMISSION_SCOPE_MISMATCH` | 目标、动作、范围或阶段不在权限内 | 等作者或缩小范围 |
| `CANDIDATE_VERSION_CONFLICT` | 候选 current、版本或摘要已经变化 | 刷新候选后重来 |
| `EVIDENCE_NOT_VERIFIABLE` | 正文锚、推导、声明或结算证据不能回验 | 补证据，零写入 |
| `CHAPTER_ACCEPTANCE_REQUIRED` | 章末验收未通过 | 返回章内返工 |
| `SETTLEMENT_BASIS_STALE` | 章节内核、路径、增量或 revision 已变化 | 重跑结算 |
| `STORY_TIME_UNRESOLVED` | 业务要求故事时间但无法合法表达 | 等作者或保留候选 |
| `DEPENDENCY_INVALID` | 依赖不成立或版本失效 | 重算影响 |
| `ATOMIC_PREPARE_FAILED` | 原子组无法完整准备 | 整组零写入 |
| `NEEDS_MANUAL_RECOVERY` | 发现既不是完整 before 也不是完整 after | 强停人工恢复 |

## 11. 三条正常示例

### 作者采用正文抽取候选

候选形成来源为 `PROSE_EXTRACTION`，晋级来源为 `AUTHOR_ADOPTION`。作者看到候选 v7 和正文锚后明确采用。回执保存作者动作并允许 `AUTHOR_ATTESTATION`，CCZ-82 在同组分配正式号和写入受影响账本。

### 系统按托管权限采用

候选形成来源为 `SYSTEM_PROPOSAL` 或 `PROSE_EXTRACTION`，晋级来源为 `DELEGATED_SYSTEM_ADOPTION`。权限快照只允许当前章、低风险事实、候选阶段的采用动作。系统保存权限版本和 principal 作者，不产生作者签字；超出范围转 `AWAITING_AUTHOR`。

### 章末结算采用本章增量

候选形成来源为 `CHAPTER_LOCAL_DELTA`，晋级来源为 `CHAPTER_CLOSEOUT_ADMISSION`。章节内核、选中路径、增量集和验收都 current 后，按依赖连通组提交。作者拒绝某个高影响变化时，该组返回章内返工，不能用其余成功掩盖。

## 12. 现行能力兼容和下游开工条件

GitHub current 的 `cap.fact.confirm` 和 `FACT_REVIEW_ACTION v1` 只允许作者动作，不能被扩义成系统托管或章末结算。

系统托管采用与章末结算必须使用新的稳定能力身份；新增能力 ID 冻结为 `cap.fact.admit_delegated` 和 `cap.fact.admit_chapter_closeout`。在能力目录完成版本化登记、CCZ-82 完成 writer、且端到端回读通过前，两项必须报告不可调用，不能借用 `cap.fact.confirm`。

CCZ-82 可以直接读取本合同施工：它不再决定三类来源，也不再补产品二选一；只负责稳定身份、同代事务、撤回／重开、恢复和机械验收。

## 13. 固定子结构与摘要算法

下面这些子结构属于 v1，后继实现不能换一组同义字段。

### `candidate_version_ref`

| 字段 | 规则 |
| -- | -- |
| `candidate_id` | 上游稳定候选号 |
| `generation_id` | 本次抽取／声明／章内增量代际 |
| `version_no` | 该候选的版本号 |
| `current_pointer_version` | 调用方看到的 current 指针版本 |
| `content_sha256` | 冻结候选规范摘要，必须等于顶层 `candidate_sha256` |
| `source_revision_ref` | 正文类候选的章节 revision；不适用时为 null |
| `producer_receipt_ref` | 形成候选的原始回执 |

### `scope`

`scope` 固定包含 `object_types`、`object_refs`、`ledger_names`、`chapter_refs`、`stage`、`write_boundary`。六项都不能省略；不适用使用空数组或 null，空数组绝不解释成全项目。

### `expected_current`

`expected_current` 固定包含 `candidate_ref`、`chapter_revision_ref`、`target_before_refs`、`permission_snapshot_ref`、`chapter_closeout_ref`、`dependency_basis_sha256`。不适用项为 null。执行前逐项 exact match，不允许只比较其中一个版本号。

### `evidence_bundle`

`evidence_bundle` 固定包含 `candidate_evidence_ref`、`author_action_ref`、`permission_snapshot_ref`、`chapter_closeout_ref`、`inference_trace_ref`。所有键都存在，不适用项为 null。作者动作、权限快照、章末结算三项只能有一条主分支非空；候选证据始终非空；隐含正文事实的推导引用必须非空。

### `write_plan`

`write_plan` 固定包含 `atomicity` 和 `atomic_groups`。`atomicity` 只允许 `ATOMIC`／`INDEPENDENT_GROUPS`。每个组固定包含 `group_id`、`dependency_group_refs`、`owners`、`expected_before_refs`、`write_intents`、`required_receipt_contracts`。owner 使用逻辑合同名，禁止物理路径、表名或另开 writer。

### 规范摘要

请求摘要统一使用 UTF-8 JSON：对象键按 Unicode 码点排序、无多余空白、数组保留业务顺序；被合同声明为集合的数组按稳定引用元组排序。所有必填键必须存在，不适用用 null。计算 SHA-256 小写十六进制。`operation_id` 不进入语义载荷摘要；同 operation ID 对应的语义摘要必须唯一。

## 14. 两条工程线怎样并行

事实晋级线和共同调用线没有互相开工的硬前置：

* 事实线由 CCZ-82 直接消费 `FACT_PROMOTION_REQUEST v1` 和 `FACT_PROMOTION_DECISION_RECEIPT v1`，先用内部调用完成业务 writer、原子事务和单元验收，不等待 CLI／MCP／主 AI 外壳。
* 调用线由 CCZ-153／154／155 消费 `UNIFIED_ACTION_CALL v1`，可以用固定 mock 能力和 mock 业务回执完成 Focus、权限、预览、幂等和跨入口等价，不等待事实 writer。
* 两线只在稳定 `action_id`、`action_contract_version`、`domain_receipt_ref`／摘要这三个接缝汇合。外壳不导入事实线内部状态，事实线不判断调用来自 CLI、MCP 还是网页。
* 两边各自通过后再做集成；CCZ-156 的正式采用／保存端到端验收必须等 CCZ-82 和目标适配器都有真实运行证据。

作者路径继续使用现有 `cap.fact.confirm`。新增能力 ID 冻结为 `cap.fact.admit_delegated` 和 `cap.fact.admit_chapter_closeout`；没有完成能力目录版本化登记与 runtime 验收前，两项必须显示不可调用。

## 15. 本票完成边界

CCZ-86 Done 只表示上述机器合同已冻结，并解除 CCZ-82 的产品合同阻塞。它不表示新能力已经登记、runtime 已写、GitHub 施工已授权，或正式事实端到端链已经跑通。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
