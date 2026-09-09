# M1 统一父合同｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[CCZ-85｜M1 raw 动作终态、generation 接纳与诚实读回统一合同（Codex）](https://linear.app/ccz/document/1d7326ec4a61)（文档 ID：`415629c7-eba2-4950-af6b-f71f9bcb6313`）。
> 原版本：无独立总版本号；2026-08-25 整理稿及作品档案扩展。内部引用 generation-v2 等子合同版本。
> 原文区 SHA-256：`2084c6da0e27836f8b2a3d6e4f8a11658b2521b7268c293c54acc7a13b513930`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 执行身份：Codex
> 整理日期：2026-08-25
> 对应父票：[CCZ-85](<https://linear.app/ccz/issue/CCZ-85/%E5%90%88%E5%90%8C%E7%88%B6%E7%A5%A8m1-raw-%E5%8A%A8%E4%BD%9C%E7%BB%88%E6%80%81generation-%E6%8E%A5%E7%BA%B3%E4%B8%8E-orphan-%E6%81%A2%E5%A4%8D>)
> GitHub 代码真值快照：main@5b4321c8ccf68f419fc0d5de5d8bba50702a79bd
> 状态：等待 CZ 对这份统一合同做最终批准；批准前不代表 GitHub 施工授权。

## 结论

这条线冻结成一条完整动作链：

**封存动作请求 → 发布不可变 raw／metadata → 按动作全文验证 → 生成固定 target generation → 用 current 的条件切换完成唯一接纳 → 从持久证据重建终态 → 使用前重新判断当前内容是否可用。**

三句话不能混：

* **已验证**：这次动作绑定的内容刚通过全文验证，还没有获得项目接纳。
* **已接纳**：target generation 曾通过 current 的唯一条件切换进入项目历史。
* **可用**：这次准备使用时，当前 generation 所需内容又完整读回并通过验证。

raw、metadata 和 generation 可以先存在。只有 current 从计划里的 expected base 成功切到固定 target，才算项目接纳。没有被该动作接纳的 artifact 只是“与该动作存在未接纳关系”，不自动获得删除授权。

## 当前输入、输出和产品缺失

当前 M1 读取：

* 已绑定的作者与项目工作区；
* 作者给出的动作号和这次上传的完整 bytes；
* current 的 expected base；
* 动作请求、raw／metadata receipt、generation manifest、父链和动作终态；
* 读回时的 current generation 与 manifest 水位。

当前 M1 能够输出：

* 不可变 raw／metadata 回执；
* 固定 target generation；
* current 条件切换结果；
* 可重建的动作终态；
* 不泄露正文和对象身份的作者安全摘要；
* 完整读回成功后，交给已授权内部模块使用的上传内容。

小说辅助产品还缺少把“这个项目动作发布了哪些内容”“哪个 generation 正式接纳这些内容”“崩溃后这个动作究竟成功、失败还是仍待恢复”“当前接纳内容现在是否仍可用”长期绑定并一致判断的能力。这个缺失会卡住作者重试上传、恢复中断动作和继续切段：小说辅助产品可能重复发布另一批对象，也可能把未接纳或已经损坏的内容显示成可用。

## 1. 真源和合同层级

五张前置票已经完成。其中 [CCZ-87](https://linear.app/ccz/issue/CCZ-87/子票关键存储语义原始来源核对) 是证据核对，[CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等)／94／88／90 是四份产品合同：

* [CCZ-87｜关键存储语义原始来源核对](<https://linear.app/ccz/document/ccz-87%E5%85%B3%E9%94%AE%E5%AD%98%E5%82%A8%E8%AF%AD%E4%B9%89%E5%8E%9F%E5%A7%8B%E6%9D%A5%E6%BA%90%E6%A0%B8%E5%AF%B9codex-0a8b17726873>)
* [CCZ-89｜M1 动作身份、请求封存与项目级幂等合同](<https://linear.app/ccz/document/ccz-89m1-%E5%8A%A8%E4%BD%9C%E8%BA%AB%E4%BB%BD%E8%AF%B7%E6%B1%82%E5%B0%81%E5%AD%98%E4%B8%8E%E9%A1%B9%E7%9B%AE%E7%BA%A7%E5%B9%82%E7%AD%89%E5%90%88%E5%90%8Ccodex-4e7563eb6d19>)
* [CCZ-94｜待接纳 raw 的动作授权与全文验证合同](<https://linear.app/ccz/document/ccz-94%E5%BE%85%E6%8E%A5%E7%BA%B3-raw-%E7%9A%84%E5%8A%A8%E4%BD%9C%E6%8E%88%E6%9D%83%E4%B8%8E%E5%85%A8%E6%96%87%E9%AA%8C%E8%AF%81%E5%90%88%E5%90%8Ccodex-90abc86c731d>)
* [CCZ-88｜generation 接纳、终态重建与父链保留合同](<https://linear.app/ccz/document/ccz-88generation-%E6%8E%A5%E7%BA%B3%E7%BB%88%E6%80%81%E9%87%8D%E5%BB%BA%E4%B8%8E%E7%88%B6%E9%93%BE%E4%BF%9D%E7%95%99%E5%90%88%E5%90%8Ccodex-0283c30f7f9d>)
* [CCZ-90｜M1 接纳历史与当前可用性诚实读回合同](<https://linear.app/ccz/document/ccz-90m1-%E6%8E%A5%E7%BA%B3%E5%8E%86%E5%8F%B2%E4%B8%8E%E5%BD%93%E5%89%8D%E5%8F%AF%E7%94%A8%E6%80%A7%E8%AF%9A%E5%AE%9E%E8%AF%BB%E5%9B%9E%E5%90%88%E5%90%8Ccodex-589505871791>)

这份父合同负责跨票衔接和总验收边界。每张子合同继续负责自己范围内的精确字段、错误分支和测试向量。[CCZ-87](https://linear.app/ccz/issue/CCZ-87/子票关键存储语义原始来源核对) 是证据核对，不直接替代产品合同。子票之间出现新的冲突时，不允许实现者私下挑一条；必须回到 [CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 记录冲突并由 CZ 决定。

Deep Research 报告是顾问证据，不是施工授权。AWS S3 多段上传的 SHA-256 不能笼统当成整对象 SHA-256；ETag 不能当内容身份；“S3 兼容”供应商也不能自动继承 AWS S3 的全部保证。

## 2. 动作身份与请求封存

动作唯一键固定为作者身份＋项目身份＋动作号；同一项目的所有动作种类共用一套动作号空间。动作类型 action_kind 进入请求承诺，不另开身份命名空间。同一作者、同一项目、同一动作号的重试，必须回到同一份持久 ActionIntent。ActionIntent 必须在发布第一份正式 raw／metadata 之前存在。

请求内容使用项目自有的 canonical JSON v1 规则形成稳定字节，再计算 SHA-256 请求承诺。当前合同不把 RFC 8785 当现成实现，也不声称已经具备 HMAC 私钥认证。

同一动作号再次到达时：

* 请求承诺相同：恢复或重放原动作；
* 请求承诺不同：在发布任何新正式对象之前拒绝；
* 不能用文件名、字节数或对象 key 代替请求承诺。

动作计划封存 expected base、固定 target generation 规则、receipt plan 和合同版本。重试不能悄悄换 base、换 target 或 rebase 成另一笔动作。

## 3. 不可变对象与动作授权验证

raw 和 metadata 必须完整写入不可变对象，并留下能回到 ActionIntent 的私有 receipt。对象 key 存在、HEAD 成功、stat 成功或 receipt 字段形状合法，都不能单独证明内容完整。

待接纳验证接口只接收：

* 已绑定的 AuthorWorkspace；
* 动作号。

验证目的由接口内部固定为“待接纳 M1 全文核验”，不是调用方可以提交或改写的第三个参数。实现内部从 ActionIntent 和私有计划推导允许读取的对象集合。调用方不能直接传任意 digest、receipt、对象路径或对象 key 来读取内容。

每个对象都要全文读取并核对完整 bytes、SHA-256、size、metadata descriptor 的字节身份与结构、作者、项目、动作、顺序、receipt plan 和 generation 目标。

验证前后都要确认 ActionIntent、sealed plan identity 和 current pointer 没有变化，而且 current 仍精确等于 ActionIntent 封存的 expected base。水位或计划变化时，本轮内容证据全部丢弃。

全文通过后只能产生本次进程内、动作绑定的 **FULL_CONTENT_VERIFIED_FOR_ACTION** 证据。它不是 durable terminal，不等于 **ACCEPTED**，不能跨动作、跨进程或跨 current 水位复用。任一对象失败时整批失败，不能把部分内容交给 generation 接纳路径。

## 4. generation 与唯一接纳点

generation 身份规则固定为 **author-workspace-generation-v2**。它派生固定 target，并绑定 generation identity、manifest identity、parent generation、动作身份、请求承诺、sealed receipt plan 中的 raw／metadata receipts，以及重建终态所需的合同版本和证据。generation 记录验证策略版本，但不持久化一次性的 FULL_CONTENT_VERIFIED_FOR_ACTION 凭证。

current 的条件切换是唯一接纳点：

**CAS(current, expected base → fixed target)**

* 切换成功：这个动作的固定 target 获得唯一项目接纳；
* 条件比较失败只表示“这次 CAS 没有新增接纳事实”，不能直接判未接纳。随后必须读取 target、current 和完整父链：target 已在 current 或祖先链中是 ACTION_ACCEPTED；完整链回到 sealed base 且不含 target 才是 ACTION_UNACCEPTED_CONCURRENT_LOSER；证据不足或冲突是 RECOVERY_BLOCKED。任何结果都不允许把 target 改接到新 current 后再算原动作成功。

CAS 成功前崩溃，动作保持待恢复；不能因为进程结束就写成永久回滚。CAS 成功后即使 terminal 还没写出，也必须从 current、generation、完整父链和动作证据重建为已接纳。

所有正式 current 更新只能从当前 tip 指向它的直接子 generation。current 不允许直接回滚到旧 generation。需要撤销时，创建新的补偿 generation，并让它正常指向当前父代。

## 5. 动作终态与恢复

持久动作终态只从持久事实推导：

* **ACTION_ACCEPTED**：固定 target 已经通过 current 接纳；
* **ACTION_UNACCEPTED_CONCURRENT_LOSER**：完整父链证明另一个 generation 从同一 base 先推进 current，本动作 target 没有进入该链；
* **ACTION_ABANDONED**：经过明确授权放弃，且放弃时已经证明 target 没有接纳；
* **ACTION_PERMANENT_INPUT_FAILURE**：ActionIntent 形成后，对同一 sealed request 能重复证明的永久输入失败。

证据缺失、损坏、循环、身份漂移或互相冲突时，返回非终态恢复结果 **RECOVERY_BLOCKED**。它不能占用 durable terminal，也不产生清理授权；证据修复后要重新判断真实终态。

恢复时必须保留并验证完整父链。不能只看当前一代、某个 terminal 文件或对象是否存在。current 缺失也不能直接猜成空项目；只要已有接纳、generation 或 terminal 证据与“空项目”冲突，就进入恢复受阻。

orphan 是“某个 action 与某个 artifact 没有形成接纳”的关系，不是 blob 的全局标签。同一内容对象可能被另一笔已接纳动作引用，因此本线不做自动垃圾回收，也不把失败动作直接等同于可删除对象。

## 6. 历史接纳与当前可用性

读回使用两条轴。

历史接纳：

* NO_ACCEPTED_GENERATION
* ACCEPTED
* RECOVERY_BLOCKED

当前内容：

* NOT_APPLICABLE
* NEEDS_CONTENT_VERIFICATION
* READY
* DEGRADED

cheap structural summary 只检查 current、generation、父链、input manifest、module state 和 receipt 结构，不读取 raw／metadata 全文。正常结果最多是 **ACCEPTED + NEEDS_CONTENT_VERIFICATION**。

full-use read 要：

* 捕获 P0：current generation ID + manifest SHA；
* 从 P0 推导全部 current M1 uploads；
* 全文读取并验证全部 state、raw 和 metadata；
* 结束或发生对象错误后再次读取 P1；
* 只有 P0 == P1 且全部通过，才是 **ACCEPTED + READY**；
* P0 == P1 且确认必需内容缺失、损坏或身份不匹配，才是 **ACCEPTED + DEGRADED**；
* P0 != P1 时丢弃本轮通过与失败证据，返回 **RETRY_CURRENT_CHANGED**。

READY 是这次读取的观察结果，不是 generation 的永久属性。后来内容损坏，历史仍保持 ACCEPTED，当前变成 DEGRADED。

只有能证明项目没有 current M1 generation，也没有相冲突的 terminal 或父链证据，才能返回 **NO_ACCEPTED_GENERATION + NOT_APPLICABLE**。不能只因 current 文件缺失就猜空项目。

作者或项目绑定失败时，在查询对象存在性前返回 **ACCESS_DENIED**，不返回任何项目状态。

CZ 已确认作者界面使用双标记：“历史已接纳”＋“当前待验证／可用／受损”。

## 7. 作者可见内容与隐私边界

作者自己的当前项目页面可以显示上传时的文件显示名。

普通日志、跨项目错误和诊断不显示文件名，也不返回：

* raw bytes、解码正文、声明或 warning 正文；
* 本地／云路径、对象 key；
* receipt、blob identity；
* raw／metadata／request／plan／generation digest 或前缀；
* 内部 key；
* 可用于判断其他项目内容是否存在的线索。

归档成员名或用户输入的名字只作为当前项目内的显示字段，不能当物理路径、授权身份或对象定位依据。跨作者／项目请求必须在查询对象存在性前统一拒绝。

## 8. [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 必须验证的故障线

[CCZ-91](<https://linear.app/ccz/issue/CCZ-91/%E9%AA%8C%E6%94%B6%E5%AD%90%E7%A5%A8m1-raw-%E5%8A%A8%E4%BD%9C%E5%B4%A9%E6%BA%83%E4%B8%8E%E5%B9%B6%E5%8F%91%E6%95%85%E9%9A%9C%E6%B3%A8%E5%85%A5>) 是 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 的实施验收子票，不是新的产品选择。下面是总览，完整范围以 [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 票面和四份产品合同为准。真实实现至少要覆盖：

* ActionIntent 写前与写后；
* 每份 raw／metadata、generation、prepare、CAS、terminal 的关键崩溃点；
* current pointer 已成功切换，但响应、operation receipt 或 terminal 丢失时的恢复；
* 同动作同请求重放；
* 同动作不同请求在正式发布前拒绝；
* 两个动作竞争同一 expected base；
* current 合法推进、非法倒退和身份漂移；
* 父链缺失、损坏、循环和跨项目；
* raw／metadata 缺失、截断、内容或 descriptor 不匹配；
* 任意 digest／receipt／路径读取被安全拒绝；
* 一个 upload slot 失败时零 current 写入、零部分结果；
* winner 与 loser 共享同一物理 blob 时不误删；
* 文件同步、目录同步、ENOSPC 和 EIO 故障；
* cheap summary 零 raw／metadata 全文读取；
* full-use read 的 P0／P1 变化；
* 真空项目、未接纳 artifact 和恢复受阻的区别；
* 跨作者／项目统一拒绝与安全摘要不泄露；
* 崩溃恢复后不会出现两个动作都声称接纳。

测试必须读取真实持久化结果，不能只断言函数返回值。[CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 不能在实现出现前提前标 Done。

## 9. [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 的开工与完成边界

这份合同获得 CZ 批准后，[CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 的合同阻塞可以解除。它不自动等于 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 已获 GitHub 施工授权。

[CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 开工前仍要实时读取：

* GitHub main 当前提交；
* governance/START_HERE.md；
* GitHub Issue #123 的开放状态、施工授权、写集和验收要求；
* 目标分支与已有 PR，避免和其他窗口冲突。

[CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 的开工门是 GitHub 当前施工授权。完成门是代码按这份统一父合同和 [CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等)／94／88／90 四份产品合同落地、带入 [CCZ-87](https://linear.app/ccz/issue/CCZ-87/子票关键存储语义原始来源核对) 的证据纠偏、[CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 真实故障注入通过，并且 GitHub PR 获得验收和合并。[CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 不要求在写实现之前先通过，但它会阻止 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 提前标完成。

## 10. 这次明确不做

* 不自动删除 orphan；
* 不建设流式上传；后备票是 [CCZ-93](https://linear.app/ccz/issue/CCZ-93/后备支线流式上传动作占位与-receipt-plan-封存)；
* 不建设云对象存储适配；后备票是 [CCZ-92](https://linear.app/ccz/issue/CCZ-92/后备支线云对象存储适配能力证明与条件写)；
* 不把 ETag、对象 key 存在或 HEAD 成功当内容身份；
* 不开放任意 digest／receipt／路径读取；
* 不把 FULL_CONTENT_VERIFIED_FOR_ACTION 当 ACCEPTED；
* 不把 READY 持久化成永久事实；
* 不允许同动作换请求、换 base、换 target 或偷偷 rebase；
* 不允许 current 直接倒退到旧 generation；
* 不因为一次失败就清理未接纳 artifact。

## 11. [CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 批准条件

CZ 批准这份父合同时，表示同意：

* 一份证据核对（[CCZ-87](https://linear.app/ccz/issue/CCZ-87/子票关键存储语义原始来源核对)）和四份产品合同（[CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等)／94／88／90）按上述顺序组成一条工程主线；
* [CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 管动作身份与请求封存；
* [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 管接纳前的动作授权全文验证；
* [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 管 fixed target、current 唯一接纳、终态重建和父链；
* [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 管接纳历史与当前可用性的诚实读回；
* [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 在实现阶段执行故障注入；
* [CCZ-92](https://linear.app/ccz/issue/CCZ-92/后备支线云对象存储适配能力证明与条件写)、93 保持后备，不阻塞 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready)；
* GitHub 当前状态仍需在 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 开工前重新核对。

批准后，本票可移除 needs-cz 并标 Done。[CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 的开工门是 GitHub 当前施工授权；完成门是 [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 通过和 GitHub PR 验收合并。

来源：Codex

## [CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本) 作品档案扩展与批准条件（2026-08-25）

本统一父合同的主线更新为：**封存原稿＋作品档案请求 → 验证两者 → 同 generation／current 接纳 → 同水位读回。**

合同层级现为 **1 份证据核对＋5 份产品合同**，新增 [CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本)。批准条件增加：[CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本) 的默认名、必填建档、profile-only 更新、旧项目补档、同水位读取、隐私与验收边界均已冻结。

GitHub #123 尚未授权新增 UI／metadata 写集；本 Linear 合同不构成代码施工授权。

关联合同：[CCZ-97 作品档案合同](<https://linear.app/ccz/document/ccz-97%E4%BD%9C%E5%93%81%E5%BB%BA%E6%A1%A3%E8%A1%A8%E9%BB%98%E8%AE%A4%E9%A1%B9%E7%9B%AE%E5%90%8D%E7%B1%BB%E5%9E%8B%E4%B8%BB%E8%A7%92%E5%BF%85%E5%A1%AB%E4%B8%8E%E6%A1%A3%E6%A1%88%E7%89%88%E6%9C%AC%E5%90%88%E5%90%8Ccodex-95c53ae186c4>)。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
