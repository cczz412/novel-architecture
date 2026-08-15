# DR-UX-03｜Agent 工具、MCP、覆盖回执、撤销与失败恢复：当前官方文档与代码级核验

**调查执行日：2026-08-14**  
**适用判断：**本报告只把外部实现当作候选证据，不把厂商能力直接映射为你们产品现状。报告重点回答：聊天 Agent、外部 MCP、管理员检修口应该共享什么执行内核，以及怎样防止 Agent 跳步、误关章、重复提交、断线后乱重试或越权写真源。

## 执行摘要与调查边界

**一页人话结论**

✅ **结论一：不要把“模型答应不乱改”当权限系统。真正可靠的阻断点必须在模型之外。证据等级 A。**  
MCP 当前规范明确说，工具描述和 annotations（工具声明的“只读”“幂等”等标签）对不可信服务器只能当提示，MCP 协议自己也不能替应用强制执行授权原则；宿主必须做明确同意和访问控制。Claude Code 的权限顺序是 `deny → ask → allow`，PreToolUse hook 即使返回 allow 也不能覆盖 deny/ask。VS Code 同样把文件修改、命令执行和外部访问放在 Agent 之外的审批/权限层。也就是说，**“系统提示词里写不得改写真源”只能减少模型尝试，不能成为真源写权限的最后一道门。** citeturn15view0turn17view0turn17view1turn16view4

这条还有很强的公开反例。GitHub Security Lab 对 VS Code Agent Mode 的安全评估发现，间接提示词注入曾可能导致本地 GitHub token、敏感文件泄露，甚至在没有用户确认的情况下执行任意代码；问题后来与 VS Code 团队一起修复。这里的攻击输入来自 Agent 读取的外部内容，而不是用户主动下达恶意命令。**证据等级 A：公开一手漏洞研究，有攻击路径和受影响机制。** citeturn17view5

✅ **结论二：MCP 现在有“幂等提示”，没有通用的“幂等保证”。证据等级 A。**  
2026-07-28 MCP schema 仍有 `idempotentHint`、`readOnlyHint`、`destructiveHint` 等字段，但规范直接强调这些都是 **hints**，服务器说“重复调用没副作用”并不构成可信保证。通用 `tools/call` 也没有一个协议级、服务端强制的业务 `idempotency_key`。因此，**对“关章、确认设定、接受修订、写入事实账”这种动作，必须由你们自己的 Action 服务持有幂等键和提交记录，不能依赖 MCP annotation。** citeturn19view7turn15view1

🔥 这个点和故障恢复直接连在一起。MCP stdio 规范规定服务器异常退出后客户端应重启，因为协议是无状态的，在途请求会丢失，客户端可以重新请求。对纯查询这很好；对已经在外部产生副作用、但回包恰好丢失的工具，**“可以 retry”不等于“安全 retry”**。重复副作用风险是由规范行为推出的工程结论，因此这一后半句评为 **B**。 citeturn15view4turn19view7

✅ **结论三：过期游标不能靠“继续翻下一页”补救；需要完整覆盖时，应整次扫描作废并从头读取。证据等级 A。**  
MCP 2026-07-28 明确规定分页之间**没有跨页一致性保证**，底层数据在翻页中变化可能造成重复或遗漏；如果需要一致的完整快照，应从第一页重新读取；旧 cursor 失效时，也应丢弃已缓存分页并从头开始。citeturn15view2  
所以检查器不能只输出“OK”。它至少要告诉作者：**要求读什么、实际读了什么、哪些没读、读的是哪个版本、游标有没有失效、结果是否完整。** “覆盖回执”这个名字不是 MCP 标准，而是本报告建议的产品层结构；跨 MCP、Agent SDK、工作流引擎的抽样中没有找到强制统一的 read-set receipt 标准，因此“行业已有统一覆盖回执协议”应判 **U**，不能下结论。

✅ **结论四：审批必须绑定“具体动作 + 具体参数 + 具体版本”，不能只让作者说一次“以后都同意”。证据等级 B。**  
OpenAI Agents SDK 当前 HITL 可以在敏感工具前暂停，把 `RunState` 序列化保存，之后在另一个进程恢复并批准或拒绝；MCP Tasks 也要求持久保存 task ID 以便崩溃后继续。但这些机制主要解决“流程在哪里停住”，并不自动替业务系统验证“作者批准时看到的对象是不是仍然是当前版本”。citeturn16view0turn16view1turn19view0turn19view1  
因此你们更安全的候选规则是：

> 作者签的是 `action_id + action payload hash + expected_version`，而不是“我授权 Agent 以后可以关章”。

批准后如果章节、人物事实或规划版本已经变化，旧批准应报 `stale_approval`，重新展示 diff，再签一次。这一具体字段组合是本报告的架构推导，不是外部标准，因此评 **B**。

✅ **结论五：聊天和按钮不要各写一套业务逻辑。两边应该只是同一个 Action 内核的两个入口。证据等级 B。**  
Temporal 的 Update 模型很接近这个思路：Update 有明确 ID，服务端能对重试去重，还可以在进入实际处理前用 Validator 接受或拒绝；Signal 则需要应用自己提供幂等键。citeturn20view2  
把这个模式映射到创作工作台，推荐结构不是：

`聊天 Agent → 写库代码 A`  
`画布按钮 → 写库代码 B`

而是：

```text
聊天 Agent ──┐
             ├──> Action API ──> 权限门 ──> 版本门 ──> 审批门 ──> 提交器 ──> 真源
画布按钮 ────┤
管理员检修口 ─┘
```

三种入口只改变 `principal`、允许调用的 action 范围和审批策略；**真正写真源的提交器只有一份。** 外部 MCP 再加一层限制，只开放 read / query / propose，不发 commit action。该结论是跨 Temporal、MCP、OpenAI/IDE 权限实现推出来的架构候选，不是某个厂商明文规定，故评 **B**。 citeturn15view0turn20view2turn16view0turn17view1

✅ **结论六：“撤销”不是一个统一能力。文件回滚、工作流补偿、业务事实纠正是三件不同的事。证据等级 A。**  
Claude Code 会给直接文件编辑保存 checkpoint，可以 rewind；但 Bash 命令修改的文件不在该 checkpoint 覆盖范围内，后台 code review 的 `--fix` 甚至明确发生在当前 session checkpoint 之外，`/rewind` 无法撤销，要靠 Git。citeturn16view6turn16view7  
LangGraph 对失败恢复提供 retry、checkpoint 和 error handler/compensation，但文档也明确说节点恢复时可能从函数开头重新运行，暂停点之前的副作用也会再跑，因此要求开发者自己做幂等；所谓 Saga compensation（补偿动作）也不是数据库时光倒流。citeturn16view2turn16view3  
所以你们应把产品术语拆开：**“撤销尚未提交的提案”“反向修订已提交事实”“失败后的补偿动作”“恢复一个中断流程”不能共用一个 Undo。**

✅ **结论七：长任务的“恢复”应靠持久任务/动作 ID，不靠连接还活着。证据等级 A。**  
MCP 2026-07-28 已取消协议级 session 概念；每个 HTTP JSON-RPC 请求都是独立 POST，SSE 不支持 `Last-Event-ID` 续传。Tasks 扩展则专门增加 durable task handle：客户端掉线或重启后用相同 task ID 继续轮询。citeturn19view4turn19view0turn19view1  
这意味着一个创作工作台不该把“聊天 WebSocket 断了没”当业务动作是否存在的依据。**动作生命周期应独立于会话连接。**

⚠️ **结论八：即使采用成熟工作流引擎，也不能假设“系统天然全审计”。证据等级 A。**  
Temporal 的 Workflow Event History 很适合记录工作流输入、Activity、Signals、Updates 和终态，也能导出做审计；但其当前 Activity Operations 文档明确指出，Pause、Reset、修改 Activity options 等管理操作**不会进入 Workflow Event History**，Activity 完成或 Workflow 关闭后，这些操作的证据甚至不再持久存在于该历史里。citeturn17view7turn17view6  
所以管理员检修口如果能做“强制恢复、跳过、改状态”，必须另写你们自己的不可抵赖审计记录，不能说“工作流引擎有 history，所以够了”。

**仍不知道什么**

当前没有足够一手证据证明某个公开协议已经同时标准化了：

`完整 read-set / 未读取项 + 数据版本 + 过期判定 + checker 版本 + 作者签字 + 幂等提交 + 补偿链`

这一整套“覆盖回执”。MCP 给了分页、缓存、资源版本线索、task、progress、cancel 等原语；OpenAI/LangGraph/Temporal 给了审批、持久状态、重试、历史等不同部件，但**拼成创作产品需要的检查证明，仍是应用层工作。** 因此任何“接 MCP/工作流框架以后，覆盖、撤销、审计就自动有了”的说法应判 **U/D**，不能拿来做能力承诺。citeturn15view2turn19view0turn16view0turn16view3turn17view7

**问题范围与调查方法**

本轮只查截至 **2026-08-14** 可访问的当前官方规范、官方 SDK 文档、官方 GitHub 仓库/issue/release、安全公告和产品技术文档。重点样本为 MCP 2026-07-28、MCP Python/TypeScript v2、OpenAI Agents SDK、LangGraph、Temporal、VS Code Agent、Claude Code、Figma MCP；不把营销案例、搜索排名、普通媒体报道当关键证据。MCP Python SDK 2.0.0 于 2026-07-28 发布并支持 2026-07-28 规范；LangGraph 当前 GitHub latest 为 1.2.11，2026-08-11 发布；OpenAI Agents SDK 当前 release 列表 latest 为 v0.20.0，2026-08-11 发布。citeturn18view0turn18view1turn18view2

调查主动找了三类反证：**“有审批但曾被绕过/实现有 bug”“有 checkpoint 但不是所有副作用都能撤”“有历史但仍存在审计空洞”**。对应样本分别包括 Claude Code v2.1.211 之前 hook `ask` 与 auto classifier 的冲突、Claude checkpoint 对 Bash/后台 review 的覆盖缺口、Temporal Activity Operations 不写 Event History。citeturn20view4turn16view6turn16view7turn17view6

明显偏差有两项。其一，IDE Agent 的安全文档比普通内容创作工具成熟，因此外推到中文网文工作台时只能拿“权限机制”而不能拿“用户行为结论”。其二，本题按要求没有使用作者社区帖子做代表性抽样，因此关于普通作者怎样理解“Agent 已经改了还是只是建议”，只能给产品风险假设，不能声称已有中国网文作者研究支持。

## 关键结论与证据等级

**关键结论表**

| 关键结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级 | 易过期 |
|---|---|---|---|---|---|
| 模型提示不能代替权限阻断 | MCP 安全原则；Claude deny/ask/allow；VS Code approvals；GitHub VS Code 漏洞研究 citeturn15view0turn17view0turn17view5 | 所有能产生副作用的 Agent | 只读、完全隔离环境风险较低，但仍不能把提示当 ACL | **A**：多份当前一手规则+真实漏洞路径 | 高 |
| MCP `idempotentHint` 只是提示，不是去重凭证 | MCP 2026-07-28 schema citeturn19view7 | MCP tool metadata | 可信自家 server 可把 hint 作为 UI 信息，但仍建议服务端实现幂等 | **A**：当前规范明确 | 中 |
| MCP 分页没有完整快照保证；过期 cursor 要重扫 | MCP caching/pagination 规范 citeturn15view2 | 完整工具表、资源列表及类似 paginated list | 单页读取无需跨页一致性 | **A**：当前规范明确 | 中 |
| MCP 断线后的请求重试不能自动视为安全重试 | stdio 异常退出允许重启并 retry；generic idempotency 仅 hint citeturn15view4turn19view7 | 有副作用工具 | 纯读、服务端有真实 idempotency key 时可安全重试 | **B**：规范事实明确，风险是工程推论 | 中 |
| Tasks 可让客户端跨断线恢复长任务 | MCP Tasks durable task ID、persist ID、poll/update citeturn19view0turn19view1 | 长任务、等待人工输入 | Tasks 是可选 extension，不是所有客户端/SDK 路径都等价支持 | **A** | 高 |
| Tasks 的 task ID 不能单独等于授权 | Tasks 要求高熵 ID，并且每次 task request 重新做认证和授权 citeturn19view2 | MCP Tasks | 自家内部单租户仍不应省略 auth binding | **A** | 中 |
| LangGraph resume 可能重跑节点前半段，副作用必须幂等 | 官方 Graph API、fault tolerance citeturn16view2turn16view3 | checkpoint/retry/interrupt 工作流 | task 结果能 checkpoint，可减少已经完成的重复工作 | **A** | 中 |
| LangGraph 可做补偿，但不是通用 Undo | error handler + Saga/compensation citeturn16view3 | 多步工作流失败恢复 | 外部系统不可逆动作仍需业务补偿接口 | **A** | 中 |
| OpenAI Agents SDK 能暂停敏感工具并持久化待审批运行 | HITL + `RunState` serialization/resume citeturn16view0turn16view1 | Agents SDK v0.20.0 当前线 | 它并不自动替业务对象做 optimistic version check | **A** 对 SDK 能力；后半边界为 **B** |
| Claude/VS Code 的权限控制在 Agent 模型之外 | Claude permission rules/hooks；VS Code permission levels citeturn17view0turn17view1turn17view2 | IDE Agent | assisted permission 可包含 LLM 风险判断，不能等同确定性 ACL | **A** | 高 |
| IDE checkpoint 不等于所有副作用可撤销 | Claude Bash、subagent/background review 明示缺口 citeturn16view6turn16view7 | IDE 文件工作流 | Git/VCS 可以补一层，但仍不是外部 API 的通用撤销 | **A** | 高 |
| “有 workflow history”仍可能有管理员操作审计空洞 | Temporal Activity Operations 与 Workflow Export citeturn17view6turn17view7 | 工作流引擎治理 | 普通 Workflow events 的历史很完整；缺口针对特定管理操作 | **A** | 中 |
| 聊天、按钮、管理员共用同一 Action 内核更安全 | Temporal Update 去重/validator + MCP/IDE 外置权限模型 citeturn20view2turn15view0turn17view1 | 本产品架构 | 这是架构推导，不是任何协议的强制模式 | **B** | 低 |
| checker 应产出覆盖回执而不是裸 OK | MCP 分页一致性/TTL/资源读取 + OpenAI MCP traces citeturn15view2turn19view6turn20view1 | 长篇一致性核对 | 没找到统一协议 schema；具体字段需本地实验 | **B**：一手原语支持设计，但 schema 为推导 | 低 |
| “业界已有统一 coverage receipt 标准” | 本轮跨样本未发现 | 跨行业普遍性声明 | 搜索不能证明不存在 | **U** | 高 |

### 当前工具对比：权限、幂等、游标、审批、撤销与审计

| 系统 | 权限 / 审批 | 幂等 / 重试 | 游标 / 恢复 | 撤销 / 补偿 | 审计 / 覆盖 |
|---|---|---|---|---|---|
| **MCP 2026-07-28** | 用户 consent、OAuth/resource audience；tool annotations 不可信 citeturn15view0turn15view5 | `idempotentHint` 只是 hint citeturn19view7 | pagination cursor；过期重扫；核心无 session citeturn15view2turn20view0 | cancellation 为协作式，不是 rollback citeturn15view3 | 有 progress、cache freshness 等原语，但没有强制 coverage receipt citeturn19view5turn15view2 |
| **MCP Tasks** | 每次 task request 都要 authz citeturn19view2 | task ID 是持续句柄，不等于业务幂等键 | durable task ID，可断线后继续 poll citeturn19view0turn19view1 | `tasks/cancel`，且 cancelled 不保证一定能成功取消正在发生的副作用 citeturn19view1 | task state 可见；并非完整业务审计 |
| **OpenAI Agents SDK 0.20.0** | 工具可要求人工批准，run 暂停再 resume citeturn16view0turn18view2 | 本轮没找到通用“所有工具调用业务幂等”保证 | `RunState` 可序列化后跨进程恢复 citeturn16view1 | 没有把任意外部副作用自动 rollback 的承诺 | tracing 可记录 MCP list/tool activity citeturn20view1 |
| **LangGraph 1.2.11** | interrupt 可做人审，但不是细粒度工具 ACL 产品 citeturn16view3turn18view1 | retry；官方要求副作用自行幂等 citeturn16view2 | checkpoint、resume、failure provenance citeturn16view3 | error handler / Saga compensation citeturn16view3 | checkpoint 有状态/任务，但不是“读了哪些文稿”的自动 coverage receipt |
| **Temporal** | Update Validator 可在业务变更接受前拒绝 citeturn20view2 | Update ID、request ID 去重；Signal 需业务 idempotency key citeturn20view2 | Durable Workflow / Event History | 通常用补偿，不是假装所有外部动作都可回滚 | Event History 很强，但 Activity admin operations 有审计缺口 citeturn17view6turn17view7 |
| **VS Code Agent** | permission level + tool/URL/command approvals citeturn16view4turn17view3 | terminal approval 甚至细到 command，而不是批准整个 terminal tool citeturn17view3 | session/workspace checkpoint 属 IDE 能力 | 可恢复文件/会话，不能外推到任意 MCP 副作用 | 有操作 UI，但本轮未找到覆盖证明标准 |
| **Claude Code** | deny/ask/allow；hooks 不能覆盖 deny/ask citeturn17view0turn17view1 | permission ≠ idempotency | session checkpoint / resume | 仅直接 file-edit 有可靠 rewind 边界；Bash、部分 subagent/background edits 不在内 citeturn16view6turn16view7 | hooks 有成功/失败/permission 事件，但也有 hook failure 的 fail-open 边界，需谨慎配置 citeturn20view4 |
| **Figma MCP** | 文件写入仍受 Figma seat/file edit permission 约束；远端 MCP 可直接创建/修改 native Figma 内容 citeturn13search6 | 没找到通用业务幂等保证 | 部分长工具暴露 run status/progress/cancel citeturn20view3 | cancel 明确不是 undo citeturn20view3 | 能返回运行状态，但不是文稿 coverage receipt |

这里有一个对本题很关键的反例：**Figma 当前远端 MCP 已经能让 Agent 用 `use_figma` 直接修改原生画布内容。** 这说明“MCP 工具天然只是只读上下文接口”已经不是事实。你们产品若坚持外部 MCP 只读/提案，就必须在自己服务端的能力暴露层明确限制，不能靠“大家通常不会给 MCP 写权限”这个假设。**证据等级 A。** citeturn13search6turn13search12

## 来源、说法与反例

**来源分级表**

| 层级 | 作者 / 机构 | 日期 / 当前版本 | 本报告使用目的 | 证据评价 |
|---|---|---|---|---|
| 一手规范 | Model Context Protocol | 2026-07-28 spec | 权限、工具、游标、缓存、cancel、transport、Tasks | A |
| 一手 SDK / release | MCP Python / TypeScript SDK | Python v2.0.0；TS v2 稳定线 | 规范落地、版本迁移、实现缺口 | A/B |
| 一手 SDK | OpenAI Agents SDK | v0.20.0，2026-08-11 | HITL、RunState、MCP tracing | A |
| 一手框架文档/源码 | LangChain / LangGraph | v1.2.11，2026-08-11 | checkpoint、retry、compensation | A |
| 一手工作流文档 | Temporal | 滚动官方文档 | idempotency、Update、audit/history | A |
| 一手产品技术文档 | Microsoft VS Code | 滚动官方文档 | 权限与审批 | A |
| 一手产品技术文档 | Anthropic Claude Code | 滚动官方文档；含历史行为版本号 | permissions、hooks、checkpoint 缺口 | A |
| 一手漏洞研究 | GitHub Security Lab | 2025-08-25，更新 2026-07-06 | Prompt injection 实际可越过预期行为 | A |
| 一手安全公告 | LangGraph GitHub Advisory | 2026-02-23 | 状态/缓存层也可能产生代码执行风险 | A |
| 一手设计工具文档 | Figma | 2026-08-14 当前访问状态，write-to-canvas beta | MCP 并非天然只读、run/cancel | A |
| 官方 repo issue + 源码核验 | MCP TypeScript SDK | Issue #2598，2026-08-01 | Tasks extension 与 dispatcher 的具体兼容缺口 | B：源码路径吻合，但本地未执行 |

**中国网文常用说法表**

本题没有对网文作者社区做代表性语言取样，按题面规则不拿零散论坛帖子冒充行业结论，因此工程概念的“中国网文固定术语”多数标为**不适用**。真正需要产品处理的是作者理解风险。

| 工程概念 | 中国网文常用说法 | 本题可用的作者界面说法 | 容易产生的误解 |
|---|---|---|---|
| tool approval | **不适用**，没有证据支持固定行业叫法 | “这一步会真的修改，确认后才执行” | “AI 问我意见”被误解成“只是聊天” |
| proposal | 可沿用“建议、修改建议、候选” | “建议，尚未写入” | 作者看到完整改稿后会自然认为系统已经记住 |
| commit | **不适用** | “已写入工作台记录 / 已确认” | “AI 说改好了”与“数据真的提交成功”混在一起 |
| rollback / compensation | **不适用** | “撤回这次未提交修改”或“新增一条更正” | 已发表事实被 UI 假装“无痕撤销”，破坏追源 |
| stale version | **不适用** | “你确认期间内容已经变了，请重新核对” | 用技术词“版本冲突”对普通作者不够直观 |
| coverage receipt | **不适用** | “本次检查范围” / “我实际检查了这些内容” | 裸“没问题”让作者误以为整本书全读过 |
| agent task resume | **不适用** | “任务已保存，断线不会丢；回来继续” | “聊天断了”被理解成“修改没发生”或反过来 |

这里最重要的产品风险不是术语翻译，而是**状态表述**。没有作者样本可以证明哪一种中文文案最好，因此“普通作者会怎样理解”的结论当前只能评 **D/U**；比较稳妥的本地实验是拿同一动作做三种状态文案，让目标作者区分“AI 建议”“等待我确认”“已经提交”“提交失败”四种状态，看是否能准确复述。

**分歧与负结果**

**负结果：MCP 的“幂等标签”不足以做执行控制。**  
`idempotentHint=true` 明确仍属于不可信 ToolAnnotations；这反驳了“给工具标一下幂等就可以自动重试”的简单方案。citeturn19view7

**负结果：Cancel 不是事务回滚。**  
MCP cancellation 是合作式：服务器应该尽量停，但如果任务已经完成、未知或不可取消，可以忽略取消；网络时序也可能让 cancel 到达时副作用已经发生。citeturn15view3  
因此“作者点停止”只能表示**停止请求已发出**，不能立即把 UI 显示成“什么都没改”。

**负结果：SSE 断线本身不能当持久恢复协议。**  
MCP 2026-07-28 Streamable HTTP 明确不支持 `Last-Event-ID` resumable SSE；subscriptions 断开后需要重新 listen，stdio 重连也不保留 subscription state。citeturn19view4turn19view3  
所以“进度流重连”与“业务任务恢复”要分开。前者可以重新订阅，后者要靠 task/action ID 查询真实状态。

**负结果：连 SDK 与刚发布规范之间也会出现实现窗口。**  
MCP TypeScript SDK 官方仓库 2026-08-01 的 issue #2598 报告，在 v2 中 Tasks extension 的 `tasks/get` / `tasks/cancel` 因为方法名曾属于旧 core registry，会在 custom handler 之前被 dispatcher 判成 `-32601`。本轮进一步直接查看当前源码，`protocol.ts` 的 era gate 确实在 handler lookup 之前执行：

```text
if (isSpecRequestMethod(request.method) && !codec.hasRequestMethod(request.method)) {
    ... MethodNotFound ...
    return;
}
const handler = this._requestHandlers.get(...)
```

官方 issue 给出的表现与代码路径吻合。citeturn13search2 fileciteturn2file0L2-L6  
因为本地环境没能实际安装该 SDK 重跑复现，所以这条给 **B，而不是 A**。它足以说明：**“规范已经有 Tasks”不能直接写成“所有客户端/SDK 的 Tasks 恢复链今天都稳定可用”。**

**负结果：权限系统本身也会有实现 bug。**  
Claude Code 当前 hooks 文档公开记录：**v2.1.211 以前**，PreToolUse hook 返回 `ask` 时，auto classifier 在某些 Bash 命令跑在 sandbox 外的情况下仍可能静默批准；`deny` 当时仍会被遵守。新版本改变了这个行为。citeturn20view4  
这个案例特别适合你们：**软审批路径可能出错，而服务端 deny 应保持不可绕过。**

**负结果：checkpoint 不能等于“恢复到世界没发生过”。**  
Claude 的 Bash 副作用不受 rewind 完整控制；LangGraph 重跑节点前半段可能再次发生外部调用；Temporal 的 compensation 也依赖应用自己定义。citeturn16view6turn16view2turn16view3  
所以“Undo everything”不是本题可以成立的产品承诺。

**负结果：审计事件也有“没写进历史”的情况。**  
Temporal 已明确承认 Activity Pause/Reset/option-change 不进 Workflow Event History。citeturn17view6  
因此管理员检修口必须有单独审计，不应直接复用“后台数据库改一下”。

另一个安全负样本来自状态层：LangGraph 2026-02-23 发布安全公告，`langgraph-checkpoint <4.0.0` 在特定启用 cache + `CachePolicy`、攻击者又能写 cache backend 的条件下，pickle fallback 可造成远程代码执行；4.0.0 将该 fallback 默认关闭。它不说明 LangGraph 普遍不安全，而是说明**持久化、缓存、checkpoint 本身也属于权限边界，不能只审 Agent tool。** **证据等级 A。** citeturn17view4

## 可复现性与最小原型

**可复现性记录**

本题按要求选择两个技术对象做最小原型目标：

- **MCP Python SDK 2.0.0 / MCP 2026-07-28**
- **LangGraph 1.2.11**

两者版本均由执行日官方 release 核验。MCP Python SDK v2.0.0 是 2026-07-28 stable release；LangGraph GitHub 当前 latest 是 1.2.11，2026-08-11 发布。citeturn18view0turn18view1

### 实际 SDK 运行状态

⚠️ **两个真实 SDK 均未能在本次执行环境安装，因此没有伪造“实际框架运行成功”的结果。**

执行环境：

```text
Python 3.13.5
mcp installed: False
langgraph installed: False
```

尝试：

```bash
python -m pip install 'mcp==2.0.0' 'langgraph==1.2.11'
```

实际失败原因为容器无法解析外部包源域名：

```text
Temporary failure in name resolution
ERROR: Could not find a version that satisfies the requirement mcp==2.0.0
```

这里的 `No matching distribution` 是 pip 在无法访问索引后的结果，**不能解释成包不存在**；官方 release 已确认包与版本存在。citeturn18view0turn18view1

因此本次把验证拆成两层：

**代码级核验**使用官方规范、官方仓库源码和 release；  
**故障行为最小验证**用一份不依赖第三方包的纯 Python harness 验证本产品需要的几个不变量。后者不是 MCP/LangGraph 官方代码，不能拿来证明厂商实现。

### MCP 原型应怎样复现

目标不是证明“能调用一个 hello tool”，而是验证这几个失败边界：

```text
读列表 page 1
→ 服务端数据版本变化
→ page 2 cursor 过期
→ checker 必须返回 incomplete
→ 丢弃此前覆盖判断
→ 从头重扫
```

预期行为直接来自 MCP caching 规范：跨页无一致性保证，invalid cursor 时整组 cached pages 作废并从头读取。citeturn15view2

第二个注入点：

```text
tools/call(mutating_action)
→ 服务端完成副作用
→ 在 response 返回前让 stdio server 崩溃
→ client restart
→ 重发同一逻辑请求
```

MCP 的确允许进程异常后 restart 并 retry；但协议只给 `idempotentHint`，没有强制业务 dedup ID。citeturn15view4turn19view7

所以该原型的**正确验收条件不是“第二次也成功”**，而是：

```text
相同业务 idempotency_key
→ 第二次返回第一次的 commit receipt
→ canonical revision 不再 +1
→ effect count 仍为 1
```

这层 idempotency key 应由应用 Action 服务实现，而不是放在 prompt 里。

第三个注入点是 Tasks：

```text
create long task
→ 持久化 taskId
→ 客户端进程退出
→ 新客户端恢复
→ tasks/get(taskId)
→ 返回原任务状态
```

这是 Tasks 官方设计的核心场景。citeturn19view0turn19view1

但 TypeScript v2 当前 issue #2598 提醒，实际采用某一 SDK 前要把 `tasks/get`/`tasks/cancel` 加进 conformance 测试，不能只看 spec checklist。官方 repo 代码的 dispatcher 目前确实先做 protocol-era method gate，再查 custom handler。citeturn13search2 fileciteturn2file0L2-L6

### LangGraph 原型应怎样复现

最小图：

```text
load_snapshot
    ↓
prepare_proposal
    ↓
interrupt(author approval)
    ↓
commit_action
    ↓
receipt
```

故障注入应放在 `interrupt()` 前后的外部副作用处。官方文档明确：checkpoint 存在于 super-step 边界，resume 后受影响节点可能从函数开头重跑，暂停之前的代码和 side effects 会再次运行，所以这里必须用 idempotency key、upsert 或 read-before-write。citeturn16view2

再注入：

```text
commit_action attempt 1
→ timeout
→ writes from failed attempt 清掉
→ RetryPolicy retry
→ attempt 2
```

LangGraph 1.2 当前 fault-tolerance 文档规定 timeout 后会清除失败 attempt 的 LangGraph writes，再由 retry policy 决定是否重试；重试耗尽后可以进入 `error_handler` 做 Saga 式 compensation。citeturn16view3  
源码侧也能看到当前 `_retry.py` 存在 per-attempt 生命周期、timeout scope、progress/heartbeat 与 guarded writes 等实现。fileciteturn4file0L2-L6

这里仍有一个关键边界：**LangGraph 清掉的是框架内失败 attempt 的 writes，不意味着它可以收回已经发到外部数据库/API 的副作用。** 这就是为什么官方同时要求 side effects 做幂等。citeturn16view2turn16view3

### 本轮实际跑通的故障 harness

为了不把上述风险只留在文字层，本轮另外跑了一份纯 Python、无第三方依赖的 **Action 不变量验证器**。它不是厂商 SDK；用途只是证明你们可以怎样定义验收标准。

实际注入并得到的结果：

| 故障 | 实际结果 | 应保护的不变量 |
|---|---|---|
| 第一页读完后 snapshot 从 42 变 43 | 返回 `status=incomplete`、`coverage_complete=false`、`stale_cursor` | 不允许残缺扫描给裸 OK |
| Action staged 后、publish 前注入 failure | canonical version 仍为 7，chapter 仍未关闭，facts 仍为空 | 部分失败不能污染真源 |
| 提案后模拟断线并序列化 pending state | 恢复后作者签字可提交 | 断线不丢待确认动作 |
| 同一 `idempotency_key` 再次提交 | 返回原 receipt，`replayed=true`，facts 仍只有 1 条 | 重试不重复生效 |
| 作者看到 v7 提案，批准前真源变为 v8 | 返回 `expected=7, actual=8` 并阻断 | 旧签字不能批准新状态 |

这几项是本轮**实际执行结果**，但证据作用仅限“候选 Action 内核可以做到这些不变量”，不能抬成 MCP/LangGraph 的产品事实。

推荐把后续真实集成测试的断言写成类似：

```text
assert no_commit_without_author_signature
assert commit_requires_expected_version
assert one_idempotency_key_has_at_most_one_effect
assert incomplete_read_never_returns_pass
assert stale_cursor_invalidates_full_coverage
assert disconnect_does_not_erase_pending_action
assert retry_returns_same_commit_receipt
assert admin_override_has_separate_audit_event
```

## 对产品的候选启示与旧报告关系

**对产品的候选启示**

### 共享的能力内核

🔥 对你们这题，最有价值的候选不是“统一成一个超级 Agent”，而是统一成一个**确定性的 Action Kernel（动作执行内核）**。

可以直接理解成：**Agent 只能提动作，Action Kernel 才能决定动作能不能真的发生。**

候选结构：

```text
                       ┌───────────────┐
聊天 Agent ───────────>│               │
画布按钮 ─────────────>│  Action API   │
管理员检修口 ─────────>│               │
                       └──────┬────────┘
                              │
                    ┌─────────▼─────────┐
                    │ principal / scope │  谁在请求、能做什么
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ expected version  │  看到的是不是当前版本
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ approval policy   │  是否需要作者签字
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ idempotency gate  │  这件事是否已执行
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ canonical commit  │  唯一写真源入口
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ durable receipt   │  成功/失败/版本/审计
                    └───────────────────┘
```

这与 MCP 的“宿主负责真实授权”、Claude/VS Code 的模型外权限、Temporal Update 去重/验证以及 OpenAI HITL 的暂停恢复方向一致。citeturn15view0turn17view1turn17view2turn20view2turn16view0

对三个入口，可以考虑**共核不同权**：

| 入口 | 可以共享 | 不建议共享 |
|---|---|---|
| 聊天 Agent | action schema、版本检查、审批、幂等、receipt、进度 | 不直接拿 canonical DB write credential |
| 画布按钮 | 完全相同的 action schema 与 commit path | 不单独写一套 mutation endpoint |
| 外部 MCP | read/query/propose action | 不暴露 commit / force-close / direct canonical write |
| 管理员检修口 | 同一 action executor、版本检查、审计格式 | 不给“直接 SQL 改状态”作为正常修复路径；override 要单独 reason/audit |

这不是字段冻结方案，而是一种候选边界。

### 把“探索、查询、提案、真改”变成能力边界，而不是提示词分类

你们题面已经要求这四类分开，外部证据支持把它进一步落实成**服务端 capability**：

```text
explore   → 可读、不产生业务承诺
query     → 可读、可产生 checker receipt
propose   → 写 proposal store，不写真源
commit    → 只有内部 Action Kernel + author approval 才可进入
override  → 只有受控管理员 principal；必须 reason + audit
```

这里尤其不要做一个 `update_story(any_json)` 大工具。MCP 工具可以带描述、schema 和 annotation，但 annotation 不可信，宽工具会把过大的能力一次性交给 Agent。citeturn19view7turn15view0

更合适的是少量**业务 action**，例如概念上：

```text
propose_fact_revision
propose_outline_revision
accept_proposal
reject_proposal
close_chapter
reopen_chapter
record_correction
```

但具体 action 名、字段和粒度仍要靠本地原型决定，本报告不能替产品冻结。

### 防“误关章”的门应该长什么样

候选提交条件可以不是：

```text
Agent says: "这一章已经确认完成"
```

而是：

```text
principal_can("close_chapter")
AND proposal.status == "awaiting_author"
AND approval.signature exists
AND approval.action_id == current.action_id
AND approval.payload_hash == current.payload_hash
AND expected_chapter_version == current_chapter_version
AND idempotency_key has no different committed payload
```

任一条件不成立就不写真源。

这样即使模型被提示注入、聊天内容说“作者已经同意”、或者 Agent 自己误判，也只会得到服务端拒绝。GitHub VS Code 漏洞研究与 Claude 的 deny-first 机制都支持把安全决策放到这一层。citeturn17view5turn17view0turn17view1

### “作者显式签字”最好不是聊天里的一个“好”

OpenAI Agents SDK 的 HITL 证明“工具调用暂停后再批准”已经是成熟 Agent SDK 模式。citeturn16view0  
但你们还可以再严一层：**审批 UI 展示确定性 action summary，而不是让模型自己写批准说明。**

例如：

```text
将要发生：
- 把第 12 章状态：草稿 → 已确认
- 写入 3 条人物状态
- 结束 1 个待核伏笔检查
- 不修改书稿正文

依据版本：
- 第 12 章：rev 84
- 人物状态账：rev 31
- 规划账：rev 18

[确认执行] [返回修改]
```

确认事件携带机器生成的 payload hash。这样作者签的是**动作事实**，不是一段可能漏项的自然语言。

### 覆盖回执不要只有 “OK”

这是本报告对产品最明确的候选接口之一。

建议 checker 的终态至少区分：

```text
pass
fail
incomplete
stale
error
```

而不是：

```text
ok / not ok
```

因为 MCP 已经明确存在 TTL stale、invalid cursor、分页 gaps/duplicates、read failure 等情况。citeturn15view2

一个候选 `coverage_receipt` 可以长这样：

```json
{
  "check_run_id": "chk_...",
  "checker": {
    "name": "continuity-checker",
    "version": "..."
  },
  "requested_scope": {
    "chapters": ["3", "4", "5", "6"],
    "accounts": ["published_text", "character_state", "outline"]
  },
  "snapshot": {
    "started_at": "...",
    "finished_at": "...",
    "read_set_fingerprint": "..."
  },
  "read": [
    {
      "source_id": "chapter:3",
      "revision": 17,
      "status": "read"
    }
  ],
  "not_read": [
    {
      "source_id": "private_decision:foo",
      "reason": "permission_denied"
    }
  ],
  "freshness": {
    "cursor_invalidated": false,
    "stale_sources": []
  },
  "coverage_complete": true,
  "result": "pass"
}
```

这里具体字段是**候选**，不是已验证行业 schema。其证据来自 MCP 的分页/freshness/read primitives 与现有 tracing，而不是一个现成 coverage 标准。citeturn15view2turn19view6turn20view1

产品层最重要的一条可先验证：

> **只要 `coverage_complete != true`，就禁止把结果渲染成“未发现问题”。**

可以显示：

> “已检查第 3～6 章正文和人物状态；规划账读取失败，因此本次不能确认‘没有冲突’。”

这能直接解决“Agent 到底读了什么”的信任问题。

### 进度也要区分“运行中”和“已提交”

MCP progress 本身只是 active request 的进度通知，服务器甚至可以选择不发 total；通知必须在任务完成后停止。citeturn19view5  
所以产品不要把：

> “正在整理第 12 章事实 80%”

画成：

> “已经写入 80%”。

推荐至少区分：

```text
reading
checking
proposal_ready
awaiting_approval
committing
committed
failed
compensating
compensated
```

其中只有 `committed` 可以让作者理解为“真的改了”。

### 失败恢复应回答三个问题

每次失败 UI 都应能回答：

**已经发生了什么？**  
例如：“提案已生成，但真源未修改。”

**现在真实状态是什么？**  
例如：“第 12 章仍为 rev 84、未关章。”

**下一步重试会不会重复执行？**  
例如：“重试将沿用 action `A123`，不会重复写入。”

这比“操作失败，请重试”重要得多。MCP 的 cancellation race、stdio retry 与 LangGraph 节点 re-execution 都说明，单纯让用户按“重试”并不够安全。citeturn15view3turn15view4turn16view2

### 撤销建议拆成三种能力

**未提交提案撤销**：直接丢 proposal，风险最低。

**已提交业务更正**：不要偷偷抹旧记录，产生新的 correction/revision，并保留原 action receipt。

**外部副作用补偿**：单独的 compensating action，明确可能失败。

LangGraph 把 compensation 当 error handler 后的业务动作，Claude Code 也明确暴露 checkpoint 的覆盖边界，这两类实现都反对“一个万能 Undo 按钮”的假设。citeturn16view3turn16view6

### 管理员检修口应比 Agent 更强，但不能更暗

管理员可以拥有 Agent 没有的 `override` 权限，但候选约束应该反过来更严格：

```text
principal = admin
action = force_recover / compensate / reopen
reason = required
before_revision = required
after_revision = generated
incident_id = optional/required by severity
receipt = mandatory
```

这是因为成熟工作流系统自己也可能存在“管理员操作没有进入正常 workflow history”的边界。citeturn17view6  
所以检修口不能靠隐蔽性安全，更不能把“直接改数据库”当标准动作。

**不能由本研究证明的东西**

本报告**不能证明**使用 MCP Tasks 就一定能得到你们想要的长任务 UX；TypeScript SDK 的当前 extension issue 已经说明规范和实现可能存在时间差。citeturn13search2

本报告**不能证明** LangGraph 比 Temporal 更适合你们。LangGraph 对 Agent/HITL 原型很直接，Temporal 的 durable history/idempotent messaging 更成熟，但选择还取决于部署复杂度、团队能力、吞吐、数据存储和运维要求。本题没有进行这些 benchmark。

本报告**不能证明**“所有写真源动作都必须逐次弹窗”。VS Code、Claude、OpenAI 都存在 session 级、规则级或自动审批选项，但什么动作需要一次一签，必须结合你们自己的作者研究和风险等级。citeturn17view2turn17view0turn16view0

本报告也**不能证明**作者最喜欢“签字”“确认执行”“写入记录”中的哪种中文。这个需要本地可用性测试。

**建议优先做的本地小实验**

不需要先搭完整 Agent，先拿同一个 `close_chapter` action 做一个窄实验最有价值：

```text
按钮触发一次
聊天 Agent 触发一次
管理员触发一次

→ 三者是否生成同一种 action envelope
→ 是否通过同一个 expected_version gate
→ 是否使用同一个 idempotency store
→ 是否进入同一种 receipt
→ 审批文案是否能让作者准确说出“现在改没改”
```

然后强制注入五种错误：

```text
网络断线
重复请求
批准后版本变化
提交中故障
一部分资料读取失败
```

只要这五项能保持真源、receipt 和 UI 状态一致，聊天/画布共核的方向才算有实证基础。

**与旧报告的关系**

由于题面只提供了 SI-008 和 SI-006 P1 的边界描述，没有提供历史原件，本报告不能声称核对过其中的具体句子或字段。

可以明确的关系只有：

**对 SI-008：补强 + 更新。**  
题面说 SI-008 已有七份成熟模式调查；本报告不重复宽综述，而是把 **2026-08-14 当前 MCP 2026-07-28、MCP SDK v2、OpenAI Agents SDK、LangGraph 1.2、IDE Agent 权限和最新公开缺陷**补到执行层，并加入 stale cursor、retry、Tasks extension SDK gap、checkpoint 边界等反例。citeturn15view0turn18view0turn18view1turn18view2turn13search2

**对 SI-006 P1：补强，不替换。**  
如果 SI-006 P1 讨论的是平台形态，本报告补的是**能力内核边界**：谁能 propose、谁能 commit、怎么 approval、怎么 durable receipt、怎么断线恢复。没有原文，因此不能说具体“反驳了哪一条”。

**没有要求删除历史原件。**  
特别是 MCP 在 2026-07-28 刚发生较大协议变化：Tasks 从 experimental core 移到 extension，HTTP/session 行为也变化明显，因此旧报告中关于 2025-era MCP session、Tasks core method 或 SSE resume 的描述即使当时正确，也应保留为历史版本，而不是覆盖删除。citeturn15view6turn19view4

## 更新触发器与完整来源

**更新触发器**

出现下面任一情况，这题应该重查。

**MCP 发布下一次 stable specification。**  
尤其重查 generic tool 是否出现正式 idempotency key、Tasks 是否进入更统一的 SDK API、stream recovery 是否变化。当前 stable 是 2026-07-28。citeturn15view6

**MCP TypeScript SDK #2598 被修复、关闭或设计改动。**  
这会直接改变本报告对 Tasks extension 实现成熟度的 B 级判断。citeturn13search2

**OpenAI Agents SDK 改 HITL / RunState 序列化格式或 MCP dependency major。**  
当前 v0.20.0 已经包含一次可能破坏自定义 MCP HTTP transport 的 dependency migration，说明这部分属于高时效内容。citeturn18view2

**LangGraph checkpoint/retry/error-handler major 行为变化。**  
尤其是节点重放语义、checkpoint serialization、cache security。当前 release 为 1.2.11。citeturn18view1turn17view4

**VS Code / Claude Code 权限模型新增自动化档位或发现新 prompt-injection 绕过。**  
Claude 文档自己已经留下 v2.1.211 前权限行为变化记录，说明这一层不能按稳定 API 看。citeturn20view4

**出现新的 Agent 真实事故。**  
特别是“读了不可信内容 → 调用写工具/凭证工具 → 未经用户明确确认产生副作用”的案例，应直接重审所有 auto-approval 规则。GitHub Security Lab 的 VS Code 案例已经证明该攻击链现实存在。citeturn17view5

**本地 prototype 出现下面任一失败。**

```text
同一 idempotency_key 产生两个 effect
stale approval 仍可 commit
incomplete coverage 被展示成 pass
断线后 action 状态无法确定
cancel 后 UI 错报“未发生任何修改”
admin override 没有独立 audit
按钮与聊天相同动作产生不同副作用
```

出现其中任何一个，都比“框架官方说支持 durable / checkpoint / approval”更应优先影响产品决策。

**完整来源清单**

以下为本报告实际用于关键结论的一手来源，访问日期均为 **2026-08-14**。

| 来源 | 发布 / 版本状态 | 支持的结论 |
|---|---|---|
| [MCP Specification 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) citeturn15view0 | 2026-07-28 | MCP 无状态请求、扩展、consent、工具安全边界 |
| [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) citeturn15view1turn20view0 | 2026-07-28 | `tools/call`、MRTR、无 protocol-level state handle |
| [MCP Schema Reference](https://modelcontextprotocol.io/specification/2026-07-28/schema) citeturn19view7 | 2026-07-28 | `readOnlyHint`、`destructiveHint`、`idempotentHint` 均只是 hints |
| [MCP Caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching) citeturn15view2 | 2026-07-28 | TTL、cacheScope、跨页不一致、invalid cursor 重扫 |
| [MCP Cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation) citeturn15view3 | 2026-07-28 | cooperative cancellation、timeout、race |
| [MCP stdio transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) citeturn15view4 | 2026-07-28 | server restart、in-flight lost、retry、subscription re-establish |
| [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) citeturn19view4 | 2026-07-28 | per-request POST、无 resumable SSE、disconnect cancel |
| [MCP Subscriptions](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/subscriptions) citeturn19view3 | 2026-07-28 | graceful/abrupt disconnect、重连需 re-listen |
| [MCP Progress](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/progress) citeturn19view5 | 2026-07-28 | progressToken、单调进度、结束后停止 |
| [MCP Authorization Security Considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations) citeturn15view5 | 2026-07-28 | token audience、PKCE、禁止 token passthrough |
| [MCP Tasks Overview](https://modelcontextprotocol.io/extensions/tasks/overview) citeturn19view0turn19view1 | 当前 Tasks extension | durable task ID、poll、input、跨重启恢复 |
| [SEP-2663 Tasks Extension](https://modelcontextprotocol.io/seps/2663-tasks-extension) citeturn19view2 | 当前扩展规范 | task ID entropy、每次 task request 重新 authz |
| [MCP 2026-07-28 Release Blog](https://blog.modelcontextprotocol.io/posts/2026-07-28/) citeturn15view6 | 2026-07-28 | Tasks 移出 experimental core、Tier-1 SDK 状态 |
| [MCP Python SDK Releases](https://github.com/modelcontextprotocol/python-sdk/releases) citeturn18view0 | v2.0.0，2026-07-28 | 当前 Python SDK 版本与协议支持 |
| [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) citeturn13search7 | v2 stable | 2026-07-28 SDK 实现线 |
| [MCP TypeScript SDK issue #2598](https://github.com/modelcontextprotocol/typescript-sdk/issues/2598) citeturn13search2 | 2026-08-01，执行日仍为公开 issue | `tasks/get` / `tasks/cancel` extension dispatcher 缺口 |
| [OpenAI Agents SDK HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/) citeturn16view0turn16view1 | 当前文档 | tool approval、interrupt、RunState persistence/resume |
| [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/) citeturn20view1 | 当前文档 | MCP pagination handling、cache、tracing |
| [OpenAI Agents SDK Releases](https://github.com/openai/openai-agents-python/releases) citeturn18view2 | v0.20.0，2026-08-11 | 当前版本及 MCP v1/v2 migration |
| [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) citeturn16view2 | 当前文档 | checkpoint boundary、resume re-execution、idempotent side effects |
| [LangGraph Fault Tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) citeturn16view3 | LangGraph ≥1.2 | timeout、retry、error handler、Saga、failure resume |
| [LangGraph Releases](https://github.com/langchain-ai/langgraph/releases) citeturn18view1 | v1.2.11，2026-08-11 | 执行日当前版本 |
| [LangGraph GHSA-mhr3-j7m5-c7c9](https://github.com/langchain-ai/langgraph/security/advisories/GHSA-mhr3-j7m5-c7c9) citeturn17view4 | 2026-02-23 | cache deserialization RCE，patched in checkpoint 4.0.0 |
| [Temporal Handling Signals, Queries & Updates](https://docs.temporal.io/handling-messages) citeturn20view2 | 滚动文档 | Update/Signal idempotency、Update validator |
| [Temporal Activity Operations](https://docs.temporal.io/activity-operations) citeturn17view6 | 滚动文档 | 管理操作不进入 Event History 的审计边界 |
| [Temporal Workflow History Export](https://docs.temporal.io/cloud/export) citeturn17view7 | Temporal Cloud 当前文档 | workflow history/compliance/audit export |
| [VS Code Manage Approvals and Permissions](https://code.visualstudio.com/docs/agents/run/approvals) citeturn16view4turn17view2turn17view3 | 滚动文档 | permission levels、tool/URL/terminal approval |
| [GitHub Security Lab: Safeguarding VS Code against prompt injections](https://github.blog/security/vulnerability-research/safeguarding-vs-code-against-prompt-injections/) citeturn17view5 | 2025-08-25；更新 2026-07-06 | 间接 prompt injection、token/file/code-exec 风险 |
| [Claude Code Permissions](https://code.claude.com/docs/en/permissions) citeturn16view5turn17view0turn17view1 | 滚动文档 | deny/ask/allow、hook 不可越过权限规则 |
| [Claude Code Hooks](https://code.claude.com/docs/en/hooks) citeturn20view4 | 滚动文档 | hook fail behavior、v2.1.211 前 ask/auto bug、defer/resume |
| [Claude Code Checkpointing](https://code.claude.com/docs/en/checkpointing) citeturn16view6 | 滚动文档 | file-edit checkpoint 与 Bash/subagent 限制 |
| [Claude Code Code Review](https://code.claude.com/docs/en/code-review) citeturn16view7 | 滚动文档 | background `--fix` 不受 session rewind 覆盖 |
| [Figma MCP Write to Canvas](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/) citeturn13search6 | 执行日 beta | Agent 可以通过 MCP 直接修改原生 Figma canvas |
| [Figma MCP Tools and Prompts](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/) citeturn20view3 | 当前文档 | tool run status/progress/cancel |
| [Figma MCP Known Client Issues](https://developers.figma.com/docs/figma-mcp-server/mcp-clients-issues/) citeturn13search10 | 当前文档 | MCP output 过大等真实客户端失败边界 |

**代码级核验补充**

MCP TypeScript SDK 当前 `protocol.ts` 的 era gate 确认是在 request handler lookup 之前执行；这与 Tasks extension issue #2598 的故障解释相符。fileciteturn2file0L2-L6

LangGraph 当前 1.2.11 对应源码中，`_retry.py` 存在 per-attempt timeout/progress/guarded-write 逻辑；checkpoint payload 类型也明确保存 task 的 result/error/interrupt/state 等信息。fileciteturn4file0L2-L6 fileciteturn5file0L2-L6

**研究结论压缩成一句产品判断：**

> **聊天 Agent、按钮和管理员可以共享 Action 能力内核，但不能共享无边界的写权限；MCP/模型负责“提出要做什么”，服务端 Action Kernel 负责“这件事现在是否允许、作者到底签了什么、是否已经执行过、写的是哪个版本、失败后真实状态是什么”。检查器同理：不给裸 OK，而给能证明“读了什么、没读什么、版本是什么、是否过期”的覆盖回执。**

这套方向有 **A/B 级外部证据支撑其必要性**，但具体 action schema、审批粒度、覆盖回执字段和作者文案仍需要本地失败注入与目标作者测试后再定，不能把本报告写成已实现能力。

**下载**

[下载本轮实际执行的失败注入最小验证脚本](sandbox:/mnt/data/dr_ux_03_failure_harness.py)

来源：ChatGPT