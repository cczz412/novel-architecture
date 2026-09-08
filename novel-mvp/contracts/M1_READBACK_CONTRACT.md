# 诚实读回｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[CCZ-90｜M1 接纳历史与当前可用性诚实读回合同（Codex）](https://linear.app/ccz/document/589505871791)（文档 ID：`49227a4b-574e-462e-9170-7066a9881254`）。
> 原版本：无独立总版本号；2026-08-25 整理稿＋同日作品档案扩展。
> 原文区 SHA-256：`0ff7bca6f8b8c5650f6a88e8f6e6435e2fb881b0bf7d7924ce259ed95074ffa0`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 执行身份：Codex
> 整理日期：2026-08-25
> 对应票：[CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回)
> 接纳合同：[CCZ-88｜generation 接纳、终态重建与父链保留合同（Codex）](<https://linear.app/ccz/document/ccz-88generation-%E6%8E%A5%E7%BA%B3%E7%BB%88%E6%80%81%E9%87%8D%E5%BB%BA%E4%B8%8E%E7%88%B6%E9%93%BE%E4%BF%9D%E7%95%99%E5%90%88%E5%90%8Ccodex-0283c30f7f9d>)
> 待接纳验证合同：[CCZ-94｜待接纳 raw 的动作授权与全文验证合同（Codex）](<https://linear.app/ccz/document/ccz-94%E5%BE%85%E6%8E%A5%E7%BA%B3-raw-%E7%9A%84%E5%8A%A8%E4%BD%9C%E6%8E%88%E6%9D%83%E4%B8%8E%E5%85%A8%E6%96%87%E9%AA%8C%E8%AF%81%E5%90%88%E5%90%8Ccodex-90abc86c731d>)
> GitHub 代码真值：`main@5b4321c8ccf68f419fc0d5de5d8bba50702a79bd`

## 结论

[CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 不能把 ACCEPTED、READY、DEGRADED 硬塞进一个互斥状态。

它们回答的是两个不同问题：

* **历史接纳轴**：这个 generation 在历史上有没有通过 current 正式接纳；
* **当前可用性轴**：这次准备使用时，所需内容有没有刚刚完整读回并通过验证。

因此，一份内容可以同时是：

> 历史上 ACCEPTED；现在 DEGRADED。

这句话表示“当初确实接纳成功，但原件后来丢失或损坏”。它不能被改写成“当初没有接纳”。

内部数据合同冻结为三层：

```text
历史接纳：
NO_ACCEPTED_GENERATION | ACCEPTED | RECOVERY_BLOCKED

当前内容：
NOT_APPLICABLE | NEEDS_CONTENT_VERIFICATION | READY | DEGRADED

本次读回：
OK | RETRY_CURRENT_CHANGED | ACCESS_DENIED
```

CZ 已确认采用双标记：作者界面同时显示“历史已接纳”和“当前待验证／可用／受损”。底层与界面都保留两条事实。

## 当前输入、输出和产品缺失

当前 M1 安全摘要读取 current 可见的 input manifest、module state 和 receipt 结构，能够输出上传数量、结构摘要和逻辑版本。

当前完整再装载读取 current manifest 引用的 raw／metadata，能够输出经过完整校验的 `UploadSource` 给后续模块使用。

小说辅助产品还缺少把“历史上已经接纳”和“这次已经确认内容仍可用”分开判断的能力。这会卡住作者继续切段：只看结构时可能把从未完整读取的内容显示成 READY；raw 后来缺失或损坏时，也可能等到后续模块真正使用才失败。

本票读取：

* 绑定好的作者和项目工作区；
* current pointer 的 generation ID 和 manifest SHA；
* 当前 generation manifest 和 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 所需的接纳／父链证据；
* 当前 input manifest、module state 和 receipt 结构；
* 本次读取强度和受信模块需要的内容范围；
* full-use read 才读取 raw／metadata 全文。

本票输出：

* 历史接纳轴；
* 当前可用性轴；
* 本次读回结果；
* 不泄露正文和对象身份的安全摘要；
* full-use read 成功时交给受信内部消费者的完整 `UploadSource`。

## GitHub 当前代码告诉我们的事

当前 `read_persisted_m1_state()` 的 READY 能证明：

* input manifest 和 module state 都能从 current 的 generation／state blob 读取；
* 两个逻辑记录连续读取两遍没有变化；
* 两个记录版本相同；
* manifest、module state 和 format receipt 里的三份上传记录相等；
* 文件名、SHA 字符串、字节数和 receipt 形状在账面上自洽。

它不能证明：

* raw blob 或 metadata 文件仍存在；
* raw 实际 SHA／size 与 receipt 一致；
* metadata 实际内容与 manifest 一致；
* 原件能重新装载成 `UploadSource`；
* 整次读取固定在同一个 generation。

完整检查只发生在 `load_persisted_upload_sources()` → `read_immutable()`。现有测试已经证明：metadata descriptor 自身合法、receipt 也合法，但 metadata 内容与 manifest 不一致时，cheap summary 仍报 READY，完整装载才拒绝。

代码入口：

* [当前 cheap summary](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/ingest_workspace.py#L365-L382>)
* [当前双读结构水位](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/ingest_workspace.py#L203-L212>)
* [上传结构和 receipt 一致性检查](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/ingest_workspace.py#L215-L291>)
* [完整再装载](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/ingest_workspace.py#L385-L430>)
* [完整 raw／metadata 校验](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L993-L1069>)
* [READY 误判的现有测试证据](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/tests/test_novel_mvp_ingest_workspace.py#L503-L547>)

现有水位还只比较 input manifest／module state 两个逻辑记录。另一个模块提交新 generation、但这两个 M1 payload 没变时，现有检查可能看不见整代已经变化。正式 READY 必须绑定完整 current pointer：generation ID＋manifest SHA。

## 1. 三层结果

### 历史接纳

* `NO_ACCEPTED_GENERATION`：能够证明项目还没有已接纳的 M1 generation。
* `ACCEPTED`：[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 已用 current／完整父链证明当前 M1 内容所在 generation 被接纳；durable terminal 也必须和父链自洽。
* `RECOVERY_BLOCKED`：current、generation identity、必要父链或 terminal 缺失、损坏、循环、身份漂移或互相冲突，无法可靠证明接纳历史。

`RECOVERY_BLOCKED` 不是永久失败，也不表示可以清理；修复证据后要重新判断真实历史。

### 当前内容

* `NOT_APPLICABLE`：真空项目，没有已接纳 M1 内容。
* `NEEDS_CONTENT_VERIFICATION`：接纳历史可靠，但本次没有全文读取全部所需 raw／metadata，或本次验证因为 current 变化／临时错误没有形成可靠结论。
* `READY`：在同一 current 水位下，本次操作所需的全部 state、raw 和 metadata 刚刚完整读取并核验成功。
* `DEGRADED`：接纳历史可靠、current 水位稳定，但至少一个本次必需的 state、raw 或 metadata 被确认缺失、不可读、截断或身份不匹配。

### 本次读回

* `OK`：本次得到了可以采用的 EMPTY、NEEDS_CONTENT_VERIFICATION、READY 或 DEGRADED 结果。
* `RETRY_CURRENT_CHANGED`：读取期间 current 合法变化，本轮内容证据全部丢弃，需要从新 current 重读。
* `ACCESS_DENIED`：作者／项目绑定或读取授权失败；不返回项目状态和对象存在性。

## 2. 判断优先级

判断按固定顺序：

 1. 作者／项目绑定失败：`ACCESS_DENIED`，不查询对象存在性。
 2. 证明是真空项目：历史 `NO_ACCEPTED_GENERATION`，内容 `NOT_APPLICABLE`。
 3. 用 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 规则证明接纳历史；无法证明则历史 `RECOVERY_BLOCKED`，停止内容使用。
 4. 捕获完整 current pointer 水位 `P0 = generation ID＋manifest SHA`。
 5. 读取并验证当前 generation、input manifest 和 module state 的结构。
 6. cheap summary 到这里结束：结构正常时输出 `ACCEPTED＋NEEDS_CONTENT_VERIFICATION`。
 7. full-use read 从 P0 manifest 推导完整验证范围，全文读取所有必需 raw／metadata。
 8. 读取完成或发生对象错误后，都要再读 current 得到 P1。
 9. P1 != P0：丢弃内容通过／失败证据，返回 `RETRY_CURRENT_CHANGED`；不能判 READY 或 DEGRADED。
10. P1 == P0 且确认内容缺失／损坏／身份不匹配：`ACCEPTED＋DEGRADED`。
11. P1 == P0 且全部通过：`ACCEPTED＋READY`。
12. 暂时性 I/O／超时无法证明内容好坏：`ACCEPTED＋NEEDS_CONTENT_VERIFICATION`，不能冒充 DEGRADED。

作者主提示的严重程度是：

`RECOVERY_BLOCKED > DEGRADED > READY > NEEDS_CONTENT_VERIFICATION`

历史 `ACCEPTED` 作为独立事实保留，不被主提示覆盖。

## 3. cheap structural summary

cheap summary 只做结构检查：

* 读取 current pointer 和 manifest；
* 校验 current generation identity 和必要接纳证据；
* 读取 input manifest、module state 和 receipt 结构；
* 校验版本配对、三份上传清单和结构化字段；
* 捕获读前／读后完整 current pointer；
* 不读取 raw／metadata 正文。

正常结果只能是：

`ACCEPTED＋NEEDS_CONTENT_VERIFICATION`

cheap summary 不能：

* 因为上次 full-use read 是 READY 就继续报 READY；
* 把 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 的提交前验证凭证当本次 READY；
* 用 HEAD、stat、key 存在或 receipt 字段合法冒充全文验证；
* 返回 raw bytes、metadata／声明正文、路径或内容 identity。

如果 accepted 历史可靠，但 current manifest 引用的 input manifest／module state blob 已确认缺失或损坏，可以输出 `ACCEPTED＋DEGRADED`；这属于结构内容受损，不需要为了发现它再读 raw。

## 4. full-use read

full-use read 当前 M1 切片固定验证：

`ALL_CURRENT_M1_UPLOADS`

调用方不能为了更容易得到 READY，临时缩小验证集合。

流程如下：

1. 捕获 P0。
2. 从 P0 对应 manifest 读取并验证 input manifest／module state。
3. 得到全部 current M1 upload receipts 和精确 metadata 预期。
4. 对每个 upload 完整读取 raw bytes 和 descriptor bytes。
5. 重算 raw SHA-256、size、descriptor SHA；校验 descriptor schema、kind、content SHA、size 和完整 metadata。
6. 校验 manifest、module state、format receipt、descriptor 和重建 `UploadSource` 的 source identity 全部一致。
7. 一个对象失败时整批不返回部分 `UploadSource`。
8. 完成或失败后重读 P1。
9. 只有 P0 == P1 且全部对象通过，才返回内部 `UploadSource` 和 `READY`。

原始内容只交给已经授权的内部下游模块。作者页面、普通日志和安全摘要只拿安全投影。

READY 必须绑定：

* current generation ID 和 manifest SHA；
* 读取目的；
* 验证范围；
* 验证策略版本；
* 本次读回结果。

这些绑定只在内部使用，不作为作者可见 digest，也不保存成 generation 的永久属性。

## 5. current 在读取中变化

P1 != P0 时：

* 丢弃本轮已经读取的 raw bytes 和验证结论；
* 不把旧 generation 的结果套到新 current；
* 不输出 READY；
* 不因旧对象失败就把新 current 判成 DEGRADED；
* 返回 `RETRY_CURRENT_CHANGED`，从新 current 重新开始。

实现可以做有限自动重试，但次数不是状态合同的一部分。持续变化时，作者看到“内容正在更新，请重新读取”，当前内容保持 `NEEDS_CONTENT_VERIFICATION`。

## 6. 真空项目

只有能够证明：

* 没有 current M1 generation；
* 没有与“已经接纳 M1”冲突的 terminal／父链证据；

才能返回：

`NO_ACCEPTED_GENERATION＋NOT_APPLICABLE＋OK`

作者可以上传或导入内容。

不能只因 CURRENT 文件不存在就猜空项目。已有 accepted terminal、generation 历史或其他接纳证据却无法读取 current 时，返回 `RECOVERY_BLOCKED`。

散落 raw 或 pending action 不算 current，也不能把空项目变成 READY／DEGRADED。它们走 action 查询和恢复线。

## 7. 状态变化

允许的变化：

* `NEEDS_CONTENT_VERIFICATION → READY`：完成同一 current 的全文验证。
* `NEEDS_CONTENT_VERIFICATION → DEGRADED`：稳定水位下发现必需内容问题。
* `READY → DEGRADED`：内容后来丢失或损坏，并被新一次稳定全文读取确认。
* `DEGRADED → READY`：恢复了完全相同、身份仍匹配的内容，并重新全文验证。
* 上次 READY 后只做 cheap summary：本次仍返回 `NEEDS_CONTENT_VERIFICATION`。
* current 变化：上一代 READY 证据失效，对新 current 重新判断。

这些变化都不改写历史轴上的 `ACCEPTED`。

## 8. 场景合同

| 场景 | 历史接纳 | 当前内容 | 本次结果 |
| -- | -- | -- | -- |
| 真空项目 | NO_ACCEPTED_GENERATION | NOT_APPLICABLE | OK |
| accepted，cheap summary 未读 raw／metadata | ACCEPTED | NEEDS_CONTENT_VERIFICATION | OK |
| 全部 current M1 内容通过，P0==P1 | ACCEPTED | READY | OK |
| raw 缺失／截断／SHA 或 size 错，P0==P1 | ACCEPTED | DEGRADED | OK |
| metadata 缺失／SHA／schema／内容绑定错，P0==P1 | ACCEPTED | DEGRADED | OK |
| input manifest／module state blob 损坏，接纳链可靠 | ACCEPTED | DEGRADED | OK |
| current／generation／父链／terminal 无法证明 | RECOVERY_BLOCKED | 不判断 | OK |
| 全文读中 current 合法推进 | 已证明的旧历史不篡改 | 不采用本轮内容结论 | RETRY_CURRENT_CHANGED |
| current 非法倒退或 identity 漂移 | RECOVERY_BLOCKED | 不判断 | OK |
| 暂时 I/O 无法判断内容好坏 | ACCEPTED | NEEDS_CONTENT_VERIFICATION | OK |
| accepted 后内容后来损坏 | ACCEPTED | DEGRADED | OK |
| 空项目旁有未接纳 artifact | NO_ACCEPTED_GENERATION | NOT_APPLICABLE | OK |
| 跨作者／项目或未授权读取 | 不返回 | 不返回 | ACCESS_DENIED |

## 9. 安全摘要

作者可见安全摘要可以返回：

* 是否已有接纳历史；
* 当前可用性状态；
* 本次验证强度；
* 是否可以继续；
* 上传数量、总字数、警告数量等粗粒度统计；
* 项目内不透明的逻辑版本。

固定不返回：

* raw bytes、解码正文和 `original_bytes_base64`；
* declarations／warning 的正文；
* 本地／云路径、对象 key；
* receipt、blob identity；
* raw／metadata／request／plan／generation digest 或前缀；
* 可用于跨项目判断内容是否存在的线索。

CZ 已确认：作者自己的当前项目页面可以显示上传时的文件显示名。普通日志、跨项目错误和诊断不显示文件名，也不能返回内部物理路径。

## 10. 和后票的边界

* [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 验收 cheap summary 零 raw 全文读取、full-use 全量验证、current 水位变化、raw／metadata 删除损坏、父链缺失／循环、空项目、并发推进和跨项目拒绝。
* [CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 汇总 [CCZ-87](https://linear.app/ccz/issue/CCZ-87/子票关键存储语义原始来源核对)、89、94、88、90 后，决定是否解除 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 的合同阻塞。
* [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 只有取得 GitHub 当前施工授权并通过 [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入)，才能标完成。

## 11. [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 验收条件

本票只有同时满足下面条件，才算合同冻结完成：

* ACCEPTED 与当前可用性分成两条轴；
* cheap summary 正常情况下永不输出 READY；
* READY 绑定完整 current pointer、读取目的、全部 current M1 uploads 和验证策略；
* raw／metadata 失败且 P0==P1 时输出 DEGRADED，历史仍是 ACCEPTED；
* P1!=P0 时丢弃本轮证据，不误报 READY／DEGRADED；
* 空项目和 current／父链损坏严格分开；
* generation／父链证据不可信时只输出 RECOVERY_BLOCKED；
* READY 不保存成 generation 的永久属性；
* 一个对象失败时不返回部分内容；
* 安全摘要不泄露正文、路径、receipt 或内容 identity；
* [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 有对应故障注入和隐私断言。

## 12. CZ 已确认的作者界面规则（2026-08-25）

* 作者界面使用双标记：“历史已接纳”＋“当前待验证／可用／受损”。
* 作者自己的当前项目页面可以显示上传时的文件显示名。
* 文件显示名不进入普通日志、跨项目错误或诊断。
* digest、receipt、对象路径、内部 key 和跨项目存在性不显示。
* 如果文件显示名本身来自归档成员或用户输入，只作为作者项目内的显示字段使用，不能当物理路径或授权身份。

来源：Codex

## [CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本) 作品档案扩展（2026-08-25）

完整读取在同一 P0／P1 水位同时读取 raw 与 profile。合法旧项目的 `NEEDS_INITIAL_PROFILE` 不算损坏；只有新格式 profile 损坏才是 `DEGRADED`。作者页面可以显示档案，日志和跨项目错误不得泄露档案内容或内部身份。

关联合同：[CCZ-97 作品档案合同](<https://linear.app/ccz/document/ccz-97%E4%BD%9C%E5%93%81%E5%BB%BA%E6%A1%A3%E8%A1%A8%E9%BB%98%E8%AE%A4%E9%A1%B9%E7%9B%AE%E5%90%8D%E7%B1%BB%E5%9E%8B%E4%B8%BB%E8%A7%92%E5%BF%85%E5%A1%AB%E4%B8%8E%E6%A1%A3%E6%A1%88%E7%89%88%E6%9C%AC%E5%90%88%E5%90%8Ccodex-95c53ae186c4>)。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
