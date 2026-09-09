# generation 接纳｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[CCZ-88｜generation 接纳、终态重建与父链保留合同（Codex）](https://linear.app/ccz/document/0283c30f7f9d)（文档 ID：`5a15678b-a396-4032-9ac8-999776ff0434`）。
> 原版本：author-workspace-generation-v2；2026-08-24 冻结稿＋08-25 作品档案扩展。
> 原文区 SHA-256：`40eee8d992a55b3ad9176745b40feea1b2e11db87adebb9ccd7196635f3b8507`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 执行身份：Codex
> 冻结日期：2026-08-24
> 对应票：[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)
> 动作合同：[CCZ-89｜M1 动作身份、请求封存与项目级幂等合同（Codex）](<https://linear.app/ccz/document/ccz-89m1-%E5%8A%A8%E4%BD%9C%E8%BA%AB%E4%BB%BD%E8%AF%B7%E6%B1%82%E5%B0%81%E5%AD%98%E4%B8%8E%E9%A1%B9%E7%9B%AE%E7%BA%A7%E5%B9%82%E7%AD%89%E5%90%88%E5%90%8Ccodex-4e7563eb6d19>)
> 验证合同：[CCZ-94｜待接纳 raw 的动作授权与全文验证合同（Codex）](<https://linear.app/ccz/document/ccz-94%E5%BE%85%E6%8E%A5%E7%BA%B3-raw-%E7%9A%84%E5%8A%A8%E4%BD%9C%E6%8E%88%E6%9D%83%E4%B8%8E%E5%85%A8%E6%96%87%E9%AA%8C%E8%AF%81%E5%90%88%E5%90%8Ccodex-90abc86c731d>)
> 原始证据：[CCZ-87｜关键存储语义原始来源核对（Codex）](<https://linear.app/ccz/document/ccz-87%E5%85%B3%E9%94%AE%E5%AD%98%E5%82%A8%E8%AF%AD%E4%B9%89%E5%8E%9F%E5%A7%8B%E6%9D%A5%E6%BA%90%E6%A0%B8%E5%AF%B9codex-0a8b17726873>)
> GitHub 代码真值：`main@5b4321c8ccf68f419fc0d5de5d8bba50702a79bd`

## 结论

这张票冻结三条线：

* 同一份 sealed target spec 只能派生一个 fixed target generation，重试不能换 base、mutations、receipt plan 或 target。
* **current 从 sealed base 条件切换到 fixed target，是唯一项目接纳点。** raw 已写、全文验证通过、target manifest 已存在、prepare 已写，都不等于接纳。
* 响应、prepare 或 terminal 丢失后，只能用 target、current 和完整父链重建真实结果；证据不够时返回 `RECOVERY_BLOCKED`，不能猜成功、猜 loser 或猜“可以清理”。

durable terminal 是把已经证明的结果长期保存下来，方便重放；它不能替代 current 的接纳事实，也不能靠“先写者赢”掩盖证据冲突。

本票还明确纠正当前恢复语义：prepare 已写但 current 仍等于 sealed base，只说明动作尚未接纳、可以按原 target 重试，不是永久“回滚终态”。

## 当前输入、输出和产品缺失

本票读取：

* [CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 持久化的 ActionIntent、sealed receipt plan、target spec、request identity 和 sealed base pointer；
* [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 在本次接纳尝试中产生的一次性 `FULL_CONTENT_VERIFIED_FOR_ACTION`；
* 当前 current pointer；
* fixed target manifest；
* 项目保留的 generation manifests 和父链；
* 已有 prepare、operation receipt 或 durable terminal。

本票输出：

* 确定性的 fixed target generation 和 target pointer；
* sealed base → fixed target 的 current 条件切换结果；
* 可重放的动作 durable terminal；
* 或在证据不足时输出非终态 `RECOVERY_BLOCKED`。

小说辅助产品还缺少把一次 M1 动作、固定 generation、current 接纳和动作终态长期绑定并进行版本判断的能力。这会卡住作者判断导入结果：响应或回执丢失后，作者无法安全知道“内容已经接纳，只是回执没回来”，还是“动作没有接纳，可以按原请求继续”，容易重复导入或在重试时静默换目标。

## GitHub 当前代码告诉我们的事

当前提交顺序是：

`不可变状态块 → generation manifest → prepare → CURRENT → operation receipt → 删除 prepare`

已经有的保护：

* generation ID 由作者、项目、父代、动作号、请求摘要和全部 entries 确定性派生；
* manifest 不可变，保存 `parent_generation_id`；
* current pointer 保存 generation ID 和 manifest SHA；
* 本地文件用临时写、文件同步、原子替换和目录同步；
* prepare 保存 old／new pointer 和候选 receipt；
* current 已经等于 new pointer 时，现有恢复会补 receipt；
* 项目文件锁和版本检查能让正常 API 并发只有一个赢家。

还缺的保护：

* prepare 不存在时，`recover()` 直接返回“不需要恢复”，不会沿 generation 父链重建丢失的 receipt；
* current 仍是 old pointer 时，现有恢复删除 prepare 并返回 `ROLLED_BACK`，不保存动作终态，动作号可能再次使用；
* 旧 receipt 重放只比动作号和 request SHA，没有证明 receipt generation 仍是 current 或祖先；
* 父代目前只是字段，恢复不会遍历并验证完整链；
* current 在正常 API 里向前，但读取没有证明它没有被外部拨回旧 generation；
* 打开项目和普通读取不会处理遗留 prepare。

代码入口：

* [generation 构造与不可变写入](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L824-L871>)
* [prepare、current 和 receipt 顺序](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L872-L910>)
* [当前恢复分支](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L714-L756>)
* [旧 receipt 重放检查](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L694-L712>)
* [当前 manifest 校验范围](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L568-L598>)
* [现有 prepare／pointer 故障测试](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/tests/test_novel_mvp_workspace.py#L484-L543>)

## 1. fixed target generation

[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 冻结 generation 身份规则版本 `author-workspace-generation-v2`。

同一 sealed target spec 必须派生同一 target。身份材料至少包括：

* generation schema 版本；
* 作者、项目和动作号；
* ActionIntent identity；
* request SHA；
* target spec SHA；
* receipt plan identity；
* sealed base generation ID 和 base manifest SHA；空项目时为 null；
* exact mutations 及每个 payload SHA；
* [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 验证策略版本；
* 从 base manifest 继承、再应用 exact mutations 得到的完整 entries。

时间戳、路径、进程号、随机数、响应内容、重试次数和当前观察到的最新 tip 不得进入 target identity。

target manifest 必须：

* `parent_generation_id` 精确等于 sealed base generation；
* 同时绑定 base manifest SHA，防止同 generation 名称对应不同内容；
* 绑定 ActionIntent、request、receipt plan 和 target spec identity；
* 只引用 [CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) sealed plan 中的 raw／metadata receipts；
* 在碰 current 之前完成不可变写入、文件／目录耐久化和完整读回；
* 重复创建时同 bytes 通过，不同 bytes 按完整性冲突拒绝。

generation ID 从版本化 canonical generation core 的 SHA-256 确定性派生；manifest SHA 从完整 manifest bytes 计算。target pointer 是 generation ID＋manifest SHA。

## 2. 内部状态和终态

| 内部状态 | 是否耐久／终态 | 含义 |
| -- | -- | -- |
| `INTENT_SEALED` | 耐久／非终态 | [CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 已固定动作、base、plan 和 target spec |
| `VERIFIED_FOR_ATTEMPT` | 内存／非终态 | [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 本次全文验证通过；进程重启或水位变化即失效 |
| `TARGET_DURABLE_CAS_PENDING` | 耐久／非终态 | target／prepare 已耐久，current 尚未证明切换 |
| `ACTION_ACCEPTED` | 耐久／终态 | 唯一 CAS 成功，或 current／完整父链证明 target 曾被接纳 |
| `ACTION_UNACCEPTED_CONCURRENT_LOSER` | 耐久／终态 | 完整父链证明其他动作从同一 base 推进，target 未进入该链 |
| `ACTION_ABANDONED` | 耐久／终态 | 显式授权放弃，且放弃时已证明 target 尚未接纳 |
| `ACTION_PERMANENT_INPUT_FAILURE` | 耐久／终态 | ActionIntent 后出现、对同一 sealed request 可重复证明的永久输入失败 |
| `RECOVERY_BLOCKED` | 非终态恢复结果 | 证据缺失、损坏或互相冲突；修复证据后仍要重建真实终态 |

`RECOVERY_BLOCKED` 不是“失败已结束”，不能占用 durable terminal 文件，也不能产生删除资格。

存储错误分开处理：

* 临时 I/O、空间不足、同步失败，而 current 仍是 base：保留 action／target，修复后按原 target 重试；
* generation、current、父链或 terminal 损坏，真实接纳历史无法证明：`RECOVERY_BLOCKED`；
* 已经证明 accepted 后 raw 或 metadata 后来损坏：`ACTION_ACCEPTED` 历史不变，当前可用性由 [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 判断；
* 本票不把普通存储错误轻率写成永久 terminal。

## 3. 接纳顺序

一次新接纳尝试必须在同一项目独占边界里按下面顺序运行：

 1. 处理旧 prepare／terminal 线索，并校验 ActionIntent、target spec 和动作 identity。
 2. 重新读取 sealed base 和 current；current 不等于 base 时先跑恢复证明，不重新封 plan。
 3. 取得 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 本次新产生的一次性验证凭证。
 4. 从 target spec 确定性派生 fixed target，写 target manifest，完成耐久化和读回。
 5. 写项目私有、按 action 绑定的 prepare 记录；它只声明“准备尝试 base → target”，不宣称成功。
 6. 再次读 current，要求它仍精确等于 sealed base generation＋manifest SHA。
 7. 执行唯一接纳操作：current 从 sealed base 条件切到 fixed target。
 8. 对本地后端，项目锁内的精确 base 比较＋原子替换＋文件／目录同步＋读回承担这次条件切换；未来后端必须提供等价条件写，不能普通覆盖。
 9. 读回 current。返回值、同步或响应不确定时不猜，直接进入父链证明。
10. 证明 target 已接纳后，用 create-if-absent 写 deterministic `ACTION_ACCEPTED` terminal，再返回结果。

prepare 必须按 action／target 绑定。它是恢复加速材料，不是接纳真值；prepare 存在或 target 存在都不能单独产生 `ACTION_ACCEPTED`。

[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 的一次性凭证必须在这次尝试里立即消费。进程重启、凭证错配、current 水位变化或恢复重试，都要重新全文验证。

## 4. 唯一接纳点

以下都不算接纳：

* ActionIntent 已写；
* raw／metadata 已写；
* 全文验证通过；
* state blobs 已写；
* target manifest 已写；
* prepare 已写；
* CAS 请求已经发出但结果无法证明；
* operation receipt 或 terminal 候选已经在内存中。

只有这一件事算接纳：

> current 被证明从 sealed base 条件切换到了 fixed target。

CAS 成功但客户端没收到响应，仍然可能已经接纳；要按下面的父链算法证明，不能按网络异常猜失败。

## 5. 父链证明算法

恢复按固定顺序判断：

1. 如果 durable terminal 存在，先校验 schema、action、request、base、target 和 terminal bytes 是否完全自洽；同路径不同 terminal 是证据冲突，返回 `RECOVERY_BLOCKED`。
2. 读取 current pointer，并核对 current manifest 的 generation ID、manifest SHA、作者和项目。
3. 如果 current 精确等于 target，证明动作已接纳，可补写同一份 `ACTION_ACCEPTED` terminal。
4. 如果 current 不等于 target，从 current 沿每代不可变 `parent_generation_id` 向后走；每一代都要重新计算 manifest SHA、generation ID，核作者／项目和 parent link，并检测缺失、循环和重复。
5. 先遇到 target，证明 target 曾是 current 的祖先，动作已接纳；即使后面又有新 generation，也补写同一份 `ACTION_ACCEPTED`。
6. current 精确等于 sealed base，或遍历起点就是 base：动作仍未接纳，可在重新全文验证后继续原 target；不写 loser terminal。
7. 完整父链先遇到 sealed base，且从 current 到 base 的路径中没有 target：证明别的动作从同一 base 推进，本动作稳定成为 `ACTION_UNACCEPTED_CONCURRENT_LOSER`。不得 rebase 或换 target。
8. 链到 root 仍没有 target／base，manifest 缺失或损坏、链循环、作者／项目漂移、pointer／terminal 互相冲突，或资源限制使证明未完成：返回 `RECOVERY_BLOCKED`，不写 terminal。

如果 terminal 声称 accepted，但 target 不在保留的 current 父链中，视为 current 倒退、历史缺失或证据冲突，返回 `RECOVERY_BLOCKED`，不能只信 terminal。

如果 loser／abandoned／permanent-input terminal 与“target 已在 current 或父链”证据同时存在，同样返回 `RECOVERY_BLOCKED`；不能覆盖其中一份证据来制造确定结果。

父链证明读取的是完整 generation identity，不是只比 generation 名称。

## 6. deterministic durable terminal

terminal 路径按项目动作唯一，使用 create-if-absent。已存在相同 bytes 表示重放；不同 bytes 表示证据冲突，返回 `RECOVERY_BLOCKED`。

所有 terminal 都绑定：

* terminal schema 版本；
* 作者、项目、动作号和 action kind；
* ActionIntent、request、receipt plan 和 target spec identity；
* sealed base pointer；
* fixed target pointer；
* terminal result；
* 与 result 对应的稳定 proof identity。

terminal identity 不包含：

* 写入时间；
* 当前观察到的 tip；
* 本次遍历路径长度；
* 临时错误文本；
  -恢复次数；
* 日志或机器信息。

这样 target 刚成为 current 时补写，和它后来成为祖先时补写，必须得到完全相同的 `ACTION_ACCEPTED` bytes。

`ACTION_UNACCEPTED_CONCURRENT_LOSER` 的稳定 proof identity 取“current 链上 sealed base 的第一个后继 generation”，不是不断变化的最新 tip。完整父链必须先证明 target 不在 base→current 路径。

`ACTION_ABANDONED` 只能由显式、已认证、幂等的人工放弃动作产生；写入前要再次证明 target 尚未接纳。放弃后动作号不复用，不删除 artifacts，后来若出现 accepted 证据则进入 `RECOVERY_BLOCKED`。

`ACTION_PERMANENT_INPUT_FAILURE` 只接受同一 sealed request 下可重复得到的规则错误码和规则版本；临时 I/O、缺文件、权限波动或内容存储损坏不能冒充永久输入失败。

## 7. 崩溃和并发场景

| 断点／场景 | 恢复后必须判断 | 明确禁止 |
| -- | -- | -- |
| 验证后、target 写前崩溃 | 凭证作废，重新全文验证 | 复用旧凭证 |
| target 写入／同步失败 | current 不变，无 terminal；修复后按原 target 重试 | 先碰 current |
| target 已耐久、prepare 前崩溃 | current==base 时重新验证并续跑 | target 存在=accepted |
| prepare 已耐久、CAS 前崩溃 | current==base 时按原 target续跑 | 写永久 ROLLED_BACK、换 target |
| CAS 比较失败 | 跑 target／父链／base 证明，得到 accepted、loser 或 blocked | 一律写 loser |
| 原子替换可能已发生，但同步／响应报错 | 读 current 和父链；target 在链中则 accepted，否则继续证明 | 按异常猜失败 |
| CAS 成功、terminal 前崩溃 | current==target，重建 `ACTION_ACCEPTED` | 再建另一个 target |
| CAS 成功后又有后继、terminal 前崩溃 | 父链到 target，重建相同 `ACTION_ACCEPTED` | current!=target 就判 loser |
| terminal 已耐久、响应丢失 | 同请求重放原 terminal | 再次 CAS |
| 两动作竞争同一 base | 只有一个 CAS 赢家；另一动作完整链到 base且无 target后才成 loser | loser 静默 rebase |
| current==base、target 已存在 | pending，可重新验证续跑 | 提前写 loser／abandoned |
| current／父链缺失、损坏或循环 | `RECOVERY_BLOCKED`，无 terminal、无清理 | 猜 target 是 orphan |
| terminal 与 action／spec 不一致 | `RECOVERY_BLOCKED` | 覆盖旧 terminal |
| accepted 后 raw 缺失／损坏 | acceptance 历史不变，交 [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) | 抹掉 accepted |
| loser 与 winner 共享物理 blob | 保留 blob，winner 继续可读 | 按 loser 删除共享 blob |
| 直接回拨 current 到旧代 | 拒绝；创建新的补偿 generation | 倒写 pointer |

## 8. current 不能直接倒退

所有正式 current 更新都必须从当前 tip 指向它的直接子 generation。

想恢复旧内容时，创建一个新的补偿 generation：

* parent 是当前 tip；
* payload 表达希望恢复到的旧逻辑内容；
* generation identity 和动作号都是新的；
* 仍通过 current 的条件切换接纳。

不能把 current 直接改回旧 generation。这样旧 target 仍留在父链里，动作的 accepted 历史不会被抹掉。

如果外部文件操作或旧备份让 current 指向非预期祖先，小说辅助产品只能在 lineage／terminal 证据发现冲突时返回 `RECOVERY_BLOCKED`；不能假装完全防住了产品边界外的任意磁盘篡改。

## 9. 未接纳 artifacts 和保留

“未接纳”是 action 与 artifact 的关系，不是 blob 的全局属性。

* 没有 durable terminal 前，ActionIntent、sealed plan、fixed target、prepare，以及证明 current→target／base 所需 generations 全部不得删除。
* loser、abandoned 或 permanent input failure 的 raw／metadata／target 继续保留并安全报告。
* 同一个物理 blob 可能被另一个动作或项目接纳，不能因为一条 loser 关系就删除。
* 当前本地最小切片冻结为：[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 不做 GC，不自动删除任何未接纳对象。
* terminal 只让未来清理流程有资格评估，不自动产生删除授权。
* generation 父链在本切片完整保留，不做截断、压缩或历史重写。

## 10. 旧数据兼容

当前 v1 generation／receipt／prepare 没有 ActionIntent 和新 terminal，不能当成空闲动作号。

* v1 receipt、generation、prepare 的作者、项目、动作号、request SHA、parent 和 manifest identity 都能互相证明，且 generation 在 current／父链中时，可以迁移为 `ACTION_ACCEPTED`，proof kind 标记为 legacy chain。
* current==legacy new pointer 且 prepare 在时，要先核 target manifest 和父链，再补 accepted terminal，不能只信 prepare。
* current==legacy old pointer 且 prepare 在时，不再删除所有证据后永久宣称 rolled back；保留动作线索，能绑定 sealed request 时转为 pending retry，无法绑定时返回 `RECOVERY_BLOCKED`。
* v1 receipt 指向的 generation 不在 current／父链时，不能直接重放成功。
* 只有散落 raw、没有动作号或 generation 证据的旧对象，无法被这份合同倒推出归属；保持未分类、只报告、不自动关联或删除。

## 11. 和后票的边界

* [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 把本票的 accepted history、父链证明和恢复结果映射成作者可见的 ACCEPTED、READY、NEEDS_CONTENT_VERIFICATION、DEGRADED、RECOVERY_BLOCKED；本票不宣称内容现在仍可用。
* [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 覆盖 raw action、target、prepare、CAS、terminal、响应丢失、父链缺失／循环、并发 loser、回滚和共享 blob 的故障注入。
* [CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 汇总四张子合同后解除 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 的合同阻塞。
* [CCZ-92](https://linear.app/ccz/issue/CCZ-92/后备支线云对象存储适配能力证明与条件写)／93 的云后端与流式输入不进入当前本地、完整 bytes 切片。

## 12. [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 验收条件

本票只有同时满足下面条件，才算合同冻结完成：

* 同 target spec 必得同 target ID；任一 identity 字段变化必得不同 target；
* target manifest parent 精确等于 sealed base，并在碰 current 前耐久读回；
* 只有 sealed base → fixed target 的 current 条件切换能产生接纳；
* current==target、target 是祖先、current==base、完整链到 base但无 target、链不可证明五类都有确定结果；
* CAS／terminal／响应丢失后可重建，且不同恢复时机写出相同 `ACTION_ACCEPTED` bytes；
* prepare 不是接纳点，pre-CAS 崩溃不写永久 ROLLED_BACK；
* concurrent loser、人工放弃和永久输入失败都有各自证据门；
* 存储损坏与 accepted 历史分离；证据不足只能 `RECOVERY_BLOCKED`；
* current 不可直接倒退，逻辑回滚创建新 generation；
* ActionIntent、target、terminal 和证明链有最低保留，本票不做 GC；
* 旧 receipt／prepare 不会被误判成空闲动作或直接可信；
* 文档不定义 READY／DEGRADED，也不把 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 一次性验证凭证当长期可用性证明。

来源：Codex

## [CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本) 作品档案扩展（2026-08-25）

generation identity 与 manifest 绑定 profile revision／identity；第一次正式入库让 raw 与 profile 同代接纳；profile-only child generation 继承 raw；旧项目可以补档；不另设 profile current。

关联合同：[CCZ-97 作品档案合同](<https://linear.app/ccz/document/ccz-97%E4%BD%9C%E5%93%81%E5%BB%BA%E6%A1%A3%E8%A1%A8%E9%BB%98%E8%AE%A4%E9%A1%B9%E7%9B%AE%E5%90%8D%E7%B1%BB%E5%9E%8B%E4%B8%BB%E8%A7%92%E5%BF%85%E5%A1%AB%E4%B8%8E%E6%A1%A3%E6%A1%88%E7%89%88%E6%9C%AC%E5%90%88%E5%90%8Ccodex-95c53ae186c4>)。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
