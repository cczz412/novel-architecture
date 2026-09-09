# 待接纳授权验证｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[CCZ-94｜待接纳 raw 的动作授权与全文验证合同（Codex）](https://linear.app/ccz/document/90abc86c731d)（文档 ID：`eaef32be-5ead-4508-85a3-41f962e67c4b`）。
> 原版本：未标独立总版本号；2026-08-24 冻结稿＋08-25 扩展；验证策略 full-content-verification-v1。
> 原文区 SHA-256：`b3dd6d7efd19a490b0c413c5053c29d3968132414e5983f14b7dfe62b87eba76`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 执行身份：Codex
> 冻结日期：2026-08-24
> 对应票：[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)
> 上游合同：[CCZ-89｜M1 动作身份、请求封存与项目级幂等合同（Codex）](<https://linear.app/ccz/document/ccz-89m1-%E5%8A%A8%E4%BD%9C%E8%BA%AB%E4%BB%BD%E8%AF%B7%E6%B1%82%E5%B0%81%E5%AD%98%E4%B8%8E%E9%A1%B9%E7%9B%AE%E7%BA%A7%E5%B9%82%E7%AD%89%E5%90%88%E5%90%8Ccodex-4e7563eb6d19>)
> 上游证据：[CCZ-87｜关键存储语义原始来源核对（Codex）](<https://linear.app/ccz/document/ccz-87%E5%85%B3%E9%94%AE%E5%AD%98%E5%82%A8%E8%AF%AD%E4%B9%89%E5%8E%9F%E5%A7%8B%E6%9D%A5%E6%BA%90%E6%A0%B8%E5%AF%B9codex-0a8b17726873>)
> GitHub 代码真值：`main@5b4321c8ccf68f419fc0d5de5d8bba50702a79bd`

## 结论

这张票冻结一条“待接纳内容的临时通行证”：

**generation 还没有接纳 raw 时，只有** [CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) **已经登记并封存的当前项目动作，才能完整读取自己 receipt plan 里的 raw 和 metadata。调用方不能提交任意 receipt、digest 或路径来换取读取。**

验证通过后，只返回一次性的内部验证凭证。它表达的是：

`FULL_CONTENT_VERIFIED_FOR_ACTION`

大白话就是“这次动作计划里的全部内容，刚刚确实从头到尾读过，身份也都对得上，可以交给 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 尝试接纳”。

它不表达：

* current 已切换；
* target 已经 ACCEPTED；
* 作者现在可以继续；
* 当前内容仍是 READY；
* 动作已经形成 durable terminal。

验证凭证不长期缓存。进程重启、恢复重试、验证期间 current 变化，或凭证要交给另一个动作时，都要重新完整验证。

本票不授权改代码；只把 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 的安全入口、验证强度和下游边界冻结清楚。

## 当前输入、输出和产品缺失

当前不可变对象保存能力读取绑定好的作者与项目工作区、完整 raw bytes 和 metadata，能够输出作者级不可变对象回执。

当前不可变对象读取能力读取绑定好的项目工作区和一份完整 receipt，能够在 receipt 已被 current input manifest 精确引用时，完整读取 raw／metadata 并核对 SHA-256、size 和 descriptor。

小说辅助产品还缺少一条“generation 尚未接纳时，只让当前项目的当前动作核对自己 sealed receipt plan”的安全读取能力。这会卡住作者提交 M1：提交前无法通过正常读取路径确认 raw 完整可用；如果直接放开任意 receipt 或 digest，又会穿透项目隔离，让一个项目探测或读取另一个项目的作者级对象。

本票输出：

* 一次完整、全量、动作绑定的待接纳验证；
* 一份只在本次接纳尝试中有效的内部验证凭证；
* 对缺失、损坏、计划漂移、越权和并发水位变化的稳定安全拒绝；
* 交给 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 的“精确 plan 刚完成全文验证”证据。

## GitHub 当前代码告诉我们的事

当前 `read_immutable` 的授权来自 current input manifest 的精确 receipt 引用：

* receipt 字段集合必须完全符合合同；
* kind 只能是 `raw_upload`；
* blob identity 必须属于当前作者；
* current manifest 在读取前必须引用这份完整 receipt；
* raw 和 metadata 都会完整读取并重新计算身份；
* descriptor 的 schema、kind、content SHA、size 和 metadata 都要匹配；
* 读取前后的 current manifest 必须相同。

这条路径很适合“已接纳对象”，但 M1 新 raw 在提交前还不可能被 current 引用，所以不能用它完成提交前验证。把 current 引用检查简单删掉也不行，那会变成通用按 digest 读取。

代码入口：

* [current manifest 精确引用检查](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L974-L1026>)
* [raw 与 metadata 的完整读取和身份核对](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L1028-L1069>)
* [作者级 raw／metadata 存储和 receipt](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L931-L972>)
* [M1 预先拥有并校验完整 bytes](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/ingest_workspace.py#L53-L94>)

## 1. 授权入口

最小对外入口可以表达为：

`AuthorWorkspace.verify_pending_immutables(operation_id)`

规则如下：

* 作者和项目身份只能来自已经认证、绑定且不可伪造的 AuthorWorkspace；调用方不能自由填写。
* 调用方只提交动作号。动作号先按现有格式校验，再在当前项目私有区查找唯一 ActionIntent。
* receipt、digest、metadata、对象列表和对象路径全部由后端从 sealed receipt plan 读取。
* 不存在 ActionIntent、ActionIntent 损坏或作用域不匹配时，在读取对象前安全拒绝。
* 如果内部编排还携带 request／plan commitment，它只能用来发现调用方拿着旧版本，不能成为授权来源。
* 真正授权只来自“当前绑定项目内、完整性可证明、已经 sealed 的 ActionIntent”。

验证入口不得接收：

* receipt 列表；
* 单个 receipt；
* raw digest 或 metadata digest；
* 文件路径、对象 key 或 blob ID；
* 调用方临时拼出来的对象子集；
* 另一个 action 的验证结果。

这不是通用 pending-object 读取接口。它只执行验证并返回内部凭证，不把 raw bytes 或 metadata 正文交给普通调用方。

## 2. 验证前水位

验证开始前必须同时满足：

* 当前 AuthorWorkspace 的作者、项目绑定可证明，动作号格式合法；
* ActionIntent 存在、schema 合法、内容 SHA 可证明；
* ActionIntent 中的作者、项目、动作号和 request commitment 自洽；
* sealed receipt plan 和 target spec 的 identity 与 ActionIntent 一致；
* ActionIntent 仍是不可变 sealed 记录；
* 当前 pointer 精确等于 ActionIntent 封存的 expected base pointer；空项目时两边都应为 null。

如果 current 已经离开 expected base，本票不猜动作是已接纳、竞争失败还是恢复受阻，也不生成验证凭证。后续由 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 根据 fixed target、current 和父链判断。

## 3. 每个对象怎样验证

验证器只能按 sealed receipt plan 的原始 slot 顺序遍历全量对象。不能跳过、增加、替换或只验证子集。

每个 slot 必须完成：

1. 核对 receipt 字段集合、kind、slot 角色和计划中的完整 receipt 完全一致。
2. 由受信后端按 receipt 内部解析对象位置；不接受调用方路径。
3. 把 raw bytes 从头读到尾，重新计算应用层 SHA-256 和实际字节数。
4. raw SHA-256、size、kind 和作者范围 blob identity 必须与计划一致。
5. 把 metadata descriptor bytes 从头读到尾，重新计算 descriptor SHA-256。
6. descriptor 必须能解析，顶层字段集合、schema 版本、kind、content SHA、size 都要精确匹配。
7. descriptor 内的 metadata 要和 ActionIntent 计划中的预期 metadata 完全相等：字段集合、值、类型和数组顺序都不能漂移。
8. 对应 `input_manifest` 和 `module_state` mutations 中的 source identity、receipt 和 metadata 也必须与同一 slot 对齐。

只要一项失败，整批验证失败，不返回“部分通过”凭证。已经通过的前几个 slot 不能单独交给 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)。

`HEAD`、`stat`、文件存在、key 存在、mtime、inode、ETag 或旧验证回执都不能代替本次完整读取。

## 4. 三组水位和并发

这里最麻烦的地方是：内容刚验完，真正切 current 之前，项目可能又变化。

本票用三组水位约束：

* **授权水位**：ActionIntent identity、request commitment、sealed receipt plan 和 target spec identity；
* **内容水位**：本次完整读回算出的每个 raw SHA、size 和 metadata identity；
* **并发水位**：ActionIntent 的 expected base，以及验证前后两次 current pointer。

全部对象验证后，必须再次读回：

* ActionIntent／plan identity 仍与开始时一致；
* current pointer 仍精确等于 expected base。

任一水位变化，本次结果作废，不发验证凭证。

验证完成到真正切换 current 之间仍可能有另一个动作抢先。[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 必须在同一次项目接纳尝试里立即消费凭证，并继续做 expected base → fixed target 的条件切换。验证凭证不能绕过这次条件切换，也不能在竞争失败后换 base 或 target。

## 5. 一次性内部验证凭证

成功输出可以叫 `VerifiedPendingRawPlan`。它是内存里的不透明能力，不是可长期复用的 JSON 回执。

内部至少绑定：

* 作者、项目和动作号；
* ActionIntent identity；
* request commitment；
* sealed receipt plan 和 target spec identity；
* expected base pointer；
* 验证策略版本 `full-content-verification-v1`；
* 已验证 slot 数量；
* 每个 slot 的 raw SHA、size 和 metadata identity；
* `FULL_CONTENT_VERIFIED_FOR_ACTION` 标志。

普通调用结果只可返回：

* 验证语义；
* 动作号；
* 计划对象数量；
* “本次执行了全文验证”这一事实。

普通结果、日志和安全摘要不得返回 raw bytes、metadata 正文、source name、路径、digest、digest 前缀或可跨项目猜测的对象身份。

这个凭证：

* 只能交给同一工作区、同一动作、同一 request／plan／target spec 的 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)；
* current 离开 expected base 后失效；
* 进程重启或恢复重试后失效；
* 不能序列化成以后永久有效的跳过全文验证证明；
* 被错配到另一个动作、另一个项目或变化后的 plan 时必须稳定拒绝。

[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 可以把“采用了哪个验证策略、验证绑定哪个 action／plan”写入它自己的 generation／terminal 证据，但不能把这张一次性凭证当作以后 READY 的替代品。

## 6. 同作者跨项目与对象复用

物理 raw blob 可以继续在同一作者范围按内容去重；metadata 继续用独立 metadata identity 和 raw identity 配对。

项目 B 要验证一个已经由项目 A 写过的物理对象，仍必须满足：

* 项目 B 有自己的 ActionIntent；
* 该对象的完整 receipt 出现在项目 B 的 sealed receipt plan；
* 验证调用使用项目 B 自己绑定的 AuthorWorkspace 和动作号；
* 项目 B 完整读回并验证这对 raw／metadata；
* 对外不透露对象是不是由项目 A 先写入。

项目 A 的 ActionIntent、plan 或验证凭证不能授权项目 B。不同作者的对象身份和存储范围不能互通。

已存在对象不能因为“路径存在”就算成功。raw、size、metadata identity 和完整内容都一致才可复用；不一致按损坏或身份冲突拒绝，禁止覆盖原对象。

## 7. 场景合同

| 场景 | 必须结果 | 明确禁止 |
| -- | -- | -- |
| 正常全量验证 | 返回绑定当前 action／plan／base 的一次性验证凭证 | 不写 generation/current，不宣称 ACCEPTED/READY |
| 同动作同 plan 重验 | 重新完整读取并返回同一语义的新一次性凭证 | 不用旧凭证跳过读取 |
| ActionIntent 缺失或未封存 | 读对象前安全拒绝 | 不靠临时 receipt/digest 补做授权 |
| raw 缺失或截断 | 整批失败，报告内容缺失／完整性失败 | 不因 metadata 或 stat 成功而通过 |
| metadata 缺失、损坏或字段漂移 | 整批失败，报告 metadata 身份失败 | 不接受“能解析”代替精确相等 |
| plan／request／target spec 漂移 | 读对象前或后置水位处拒绝 | 不自行采用看起来更新的 plan |
| 跨作者或同作者跨项目越权 | 对外统一“当前项目不可用” | 不泄露另一项目动作或对象是否存在 |
| 调用方传任意 digest／receipt／路径 | API 边界拒绝 | 不建立通用按 digest 读取入口 |
| 验证期间 current 推进 | 本次凭证作废；[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 不写 current | 不因对象验证成功推断 ACCEPTED |
| A 凭证交给 B action／plan | 下游按绑定不一致拒绝 | 不把凭证当通用 bearer token |
| 一个 slot 失败 | 全量失败，无部分凭证 | 不把已通过 slot 单独接纳 |
| 已存在对象完全一致 | 本次完整读回后可为当前 action 验证 | 不因存在直接通过，不覆盖 |

## 8. 失败和副作用

[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 是纯验证能力，自身不写：

* generation；
* current pointer；
* ACCEPTED receipt；
* durable terminal；
* READY／DEGRADED 状态；
* 可长期复用的验证成功记录。

验证失败时不删除、不覆盖已经发布的 raw 或 metadata。它们继续留给 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 按 action 关系判断；本票不把它们命名成终态，也不授权清理。

“零 current 写入”表示 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 没有发出 current 写操作。如果别的动作并发推进 current，指针值可以变化，但不能把那个变化记到 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 头上。

## 9. 对外错误和隐私

下面几种情况对外使用同一类“当前项目不可用”拒绝，不能形成存在性探针：

* 动作不存在；
* 动作属于另一个作者；
* 动作属于同作者另一个项目；
* ActionIntent 无法证明、损坏或作用域不匹配；
* 调用方尝试用任意 digest／receipt／路径进入。

在已经证明是当前项目当前动作后，可以区分“内容缺失”“内容损坏”“metadata 不匹配”“并发水位变化”，方便作者安全重试，但错误仍不能带正文、路径、digest 或其他项目线索。

## 10. TOCTOU 的剩余边界

当前合同依赖存储层兑现“对象创建后不可修改”。本地后端使用不可变创建和内容复核，普通产品调用不能覆盖同一路径。

如果未来后端不能保证对象不可变，也不能把读取钉在明确对象版本上，[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 不能宣称消除了“验完后被替换”的窗口。云后端能力证明和条件读取留给 [CCZ-92](https://linear.app/ccz/issue/CCZ-92/后备支线云对象存储适配能力证明与条件写)。

接纳后发生的外部删除或损坏由 [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 显示为 DEGRADED，不能倒推成当初没有接纳。

## 11. 交给后票的边界

* [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)：从 sealed target spec 确定性派生 target，消费同动作的一次性验证凭证，执行 expected base → fixed target 的 current 条件切换，并定义 ACCEPTED、竞争失败、父链和 durable terminal。
* [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回)：重新读取 current 所需内容，区分 ACCEPTED、READY、NEEDS_CONTENT_VERIFICATION、DEGRADED、RECOVERY_BLOCKED；不能拿本票凭证冒充当前 READY。
* [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入)：验证跨项目越权、任意 digest、metadata 多字段／少字段、对象截断、已存在对象冲突、验证中 current 推进、一个 slot 失败和失败零 current 写入。
* [CCZ-92](https://linear.app/ccz/issue/CCZ-92/后备支线云对象存储适配能力证明与条件写)：未来云后端的不可变对象版本、完整内容证明和条件读取能力，不阻塞本次本地切片。

## 12. [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 验收条件

本票只有同时满足下面条件，才算合同冻结完成：

* 入口不接受 receipt、digest、路径或调用方对象列表；
* 授权只来自当前项目持久 ActionIntent 和 sealed receipt plan；
* 入口只接受绑定 AuthorWorkspace 和动作号，作者／项目不能由调用方自报；
* plan 中每个对象都经过完整 bytes 读取、应用层 SHA-256、size 和 metadata identity 核对；
* metadata 字段集合、值、类型和数组顺序精确匹配；
* 验证前后 ActionIntent／plan 和 current 水位都稳定；
* 一个对象失败时整批失败，没有部分凭证；
* 成功只返回一次性 `FULL_CONTENT_VERIFIED_FOR_ACTION`，不返回 ACCEPTED／READY；
* 凭证不能跨动作、跨 plan、跨项目、跨进程或在 current 变化后复用；
* 同作者物理对象复用不穿透项目授权；
* 越权和任意 digest 错误不泄露对象是否存在；
* 本票自身对 generation、current、terminal 和 READY 保持零写入；
* 文档没有冻结 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 的终态，也没有把云后端拉进当前建设范围。

来源：Codex

## [CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本) 作品档案扩展（2026-08-25）

动作类型固定验证范围：初始入库全文验证 raw、metadata 与 profile；profile-only 更新全文验证新 profile，并证明继承的 raw 集合与父 generation 相同，不把它冒充为 raw READY。

关联合同：[CCZ-97 作品档案合同](<https://linear.app/ccz/document/ccz-97%E4%BD%9C%E5%93%81%E5%BB%BA%E6%A1%A3%E8%A1%A8%E9%BB%98%E8%AE%A4%E9%A1%B9%E7%9B%AE%E5%90%8D%E7%B1%BB%E5%9E%8B%E4%B8%BB%E8%A7%92%E5%BF%85%E5%A1%AB%E4%B8%8E%E6%A1%A3%E6%A1%88%E7%89%88%E6%9C%AC%E5%90%88%E5%90%8Ccodex-95c53ae186c4>)。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
