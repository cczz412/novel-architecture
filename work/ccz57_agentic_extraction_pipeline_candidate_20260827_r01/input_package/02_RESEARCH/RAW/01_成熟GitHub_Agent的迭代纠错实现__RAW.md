# 成熟 GitHub Agent 的迭代纠错实现：代码、状态与失败恢复

**研究访问时间：2026-08-26，America/Montreal。**

本轮只回答“生成之后怎么纠错”，不再展开权限门控、工作流游标、生成前覆盖检查和缺料回取。

结论很明确：**成熟项目并没有收敛到一个统一的“Planner → Verifier → Fixer”架构。真正收敛的是三种不同粒度的恢复循环：**

1. **模型级纠错**：模型给了坏参数、坏结构化输出，不重跑整件事，只把验证错误反馈给模型，让它修这一处。PydanticAI 做得最明确。
2. **步骤级恢复**：某个节点或 executor 失败，从持久化边界恢复；已经成功的兄弟节点尽量不再执行。LangGraph 在这一层最完整，Microsoft Agent Framework 也把 checkpoint 做成正式能力。
3. **工作区级修复**：代码已经改到磁盘，再运行命令/测试，把 stdout、stderr、测试失败当观察结果，模型继续改工作区。OpenHands 和 mini-swe-agent 属于这一类；“测试失败”通常并不是框架里的特殊状态，而只是下一条 observation。citeturn22search1turn21search0turn17search3turn15search0

🔥 **真正最难、而且到 2026 年仍没有被这些项目普遍解决的是“副作用恰好执行一次”。** Checkpoint 能告诉系统从哪里恢复，却不能自动证明“崩溃前那个数据库写入、shell 命令、外部 API 或文件修改到底有没有已经生效”。MAF 目前仍有公开 issue：executor 在一个 superstep 中途崩溃时，恢复会重放整个 agent turn，因此已经成功的 tool call 可能再次产生真实副作用；PydanticAI 也有当前 issue 指出 durable execution 下 capability hook 无法保证外部写入 exactly-once；OpenHands 曾实际出现 crash recovery 后同一个 tool call 获得两个 observation-like event；LangGraph 的恢复语义也明确要求把可重放代码写成确定性的、幂等的任务。citeturn14search5turn19search3turn17search4turn22search1

## 结论与样本边界

我最终把 **OpenHands Software Agent SDK、mini-swe-agent、LangGraph、PydanticAI、Microsoft Agent Framework** 作为核心样本。它们代表了五种不同但互补的现行实现，不靠 Star 数判断成熟度，而是看当前 release、现行代码、公开运行/基准、真实 bug 和恢复语义。

| 项目 | 本轮定位 | 截至访问日的维护证据 | 为什么纳入 |
|---|---|---|---|
| **OpenHands Software Agent SDK** | 完整 Coding Agent/runtime | GitHub API 显示 `v1.43.1` 于 2026-08-21 发布；它是 OpenHands CLI 和 Cloud 背后的执行引擎。fileciteturn6file0L2-L2 citeturn17search2 | 有真实工作区、tool observation、event persistence、stuck detection、暂停恢复和大量生产故障记录。 |
| **mini-swe-agent** | 极简但真实跑代码任务的 Agent | 当前 `main` 的核心 `DefaultAgent` 仍在修改；项目公开用于 SWE-bench 等软件工程任务，并明确将 mini 作为当前默认实现。citeturn16view0turn15search0 | 控制流极简单，能非常清楚地看出“Agent 最少需要多少状态才能纠错”，也暴露了这种简单方案的恢复上限。 |
| **LangGraph** | 低层耐久编排 runtime | `langgraph 1.2.11` 于 2026-08-11 发布，SDK `0.4.3` 于 8 月 19 日发布。fileciteturn7file0L2-L2 | checkpoint、pending writes、replay、fork、interrupt 都是正式 runtime 语义，非常适合研究失败步骤怎么恢复。 |
| **PydanticAI** | 强类型 Agent loop + durable integrations | `v2.35.0` 于 2026-08-25/26 发布，V2 已在 2026-06-23 稳定。fileciteturn8file0L2-L2 citeturn18search10 | 对“坏工具参数/坏结构化输出怎样精确返修”定义最清楚，也有 Temporal、DBOS、Prefect 等恢复层的真实故障。 |
| **Microsoft Agent Framework** | 当前 Microsoft 正式多 Agent/Workflow runtime | Python `1.15.0` 于 2026-08-21、.NET `1.19.0` 于 8 月 22 日发布。fileciteturn9file0L2-L2 | checkpoint 明确定义了 executor state、pending message/request/shared state，且已有大量恢复故障和修复。 |

几个搜索种子没有强行塞进核心样本。

**AutoGen 已进入 Maintenance Mode**，仓库明确说不再增加新 feature/enhancement，并让新用户转向 Microsoft Agent Framework，因此本轮只把它当历史背景，不把它当“研究当日仍积极演进的主样本”。citeturn18search7

**Semantic Kernel 也已经把 Microsoft Agent Framework 作为后继路线**；当前 Microsoft 的新 checkpoint、workflow 和多 Agent 机制主要在 Agent Framework 继续演进，所以没有重复研究两套相近 Microsoft 栈。citeturn7search1turn7search5

**旧 SWE-agent 已被项目方明确说成由 mini-swe-agent supersede，旧项目进入 maintenance-oriented 状态。** 不过旧 SWE-agent 的 `RetryAgent` 非常有研究价值，因为它实现过“整次尝试重置 → reviewer 评分 → 再跑一遍 → 最后选最好结果”的显式多尝试循环；我会把它作为历史对照，而不是现行推荐样本。citeturn10search4turn10search5

**CrewAI 仍在活跃发布，并有 Flow persistence。** 但在本轮检索到的原始证据里，能确认的是 workflow state persistence 和活跃 release；我没有找到同样清楚、稳定、能直接追到核心 runtime 的“生成后 verifier → repair → durable replay”契约，尤其不足以区分哪些是正式 Coding Agent 能力、哪些只是 crew/flow 组合方式，因此不把它放进核心比较。这里的结论是“本轮证据不足”，不是“CrewAI 没有纠错能力”。citeturn6search0turn8search3

## 代码型 Agent：OpenHands 与 mini-swe-agent

### OpenHands：保存的不是一份最终答案，而是一棵可追溯的事件树

OpenHands 当前的持久化分成两层。`base_state.json` 保存 agent 配置、执行状态、统计、secret、agent-specific state 等可变基线；message、tool call、observation 等则一个事件一个文件追加到 `events/`。官方文档明确区分“base state 可以覆盖更新”和“event history 增量追加”。这使恢复时不用为了更新一个执行状态去重写整段历史。citeturn17search3

更关键的是当前 `ConversationState` 已经不是单纯的线性 message list。代码里有 `leaf_event_id`、`parent_id`、active branch 和 movable HEAD；追加事件时会给它盖上当前 parent，然后推进 HEAD。`active_branch()` 只把当前分支投影给 Agent，但被放弃的分支仍留在 event log；`rebuild_view()` 会在 cold load、fork、navigation 和 error recovery 时从事件分支重新构造视图。也就是说，**“修正当前路线”和“删除旧证据”是两回事**。旧路线可以不再参与模型上下文，却不必从存储中消失。fileciteturn2file0L2-L2

同一份当前代码还保存了 `execution_status`、`max_iterations`、`stuck_detection`、统计信息、被 hook 阻止的 action/message、当前 HEAD、agent-specific runtime state 等。默认 `max_iterations` 为 500；终态明确区分 `FINISHED`、`ERROR`、`STUCK`。这说明 OpenHands 的“停止”并不只靠模型说一句完成，而有 runtime 可观察状态。fileciteturn2file0L2-L2

它的 **stuck detector 是少数真正把“没有进展”做成正式 runtime 能力的项目之一**：当前文档列出连续重复 action/observation、连续重复 action/error、重复 monologue、交替重复模式、重复 context error 等模式，命中后终止执行，而不是一直让模型自我反思。citeturn2search4

不过这里有个很重要的边界：**OpenHands 的基础 Agent 并没有一个稳定、通用的“Verifier 角色”在每次代码修改后自动跑测试并判定通过。** 文件编辑、终端、任务追踪等是正式工具，但“该跑什么测试、测试失败后怎么改”通常还是 Agent 根据 observation 决定。它确实有 Critic，可以根据当前 action/history 打分，并提供 iterative refinement，但官方当前把 Critic 明确标成高度实验性能力，因此不能把它当成熟核心契约。citeturn17search2turn2search2

这点从真实故障更能看清。2026 年 5 月的 #3045 记录了一个生产 conversation：crash recovery 后，同一个 tool call 在 event stream 中出现了两个 observation-like event，随后 condensation 因事件关系不符合预期而崩溃。也就是说，**append-only 能保住证据，但 append-only 本身不能保证事件恰好一次、也不能保证恢复后的事件图一定语义合法。** citeturn17search4

另一个 #2966 暴露的是“重复执行”更危险的一面：两个 agent-server 指向相同 `conversations_path` 时，可能同时装载并恢复同一个 active conversation，形成 split-brain。维护者讨论的修复方向包括独占锁、conversation lease/ownership 等。这已经不是模型问题，而是典型分布式状态所有权问题。citeturn17search0

还有一个当前未完全解决的反例：#4080 报告单个无法反序列化的 persisted event kind 可以让整个 conversation load 失败，即使磁盘上其他事件仍完整。它说明“保住原始证据”与“能局部降级读取损坏证据”仍是两个不同能力。citeturn17search7

OpenHands 的 context condensation 也不是无风险的“重新编译上下文”。2026 年公开 issue 曾记录 condensation 自己进入循环，用户靠暂停 conversation 再发消息才恢复；另一个长会话 bug 则在 summarization LLM call 失败后让 conversation 停止推进。**所以“上下文压缩后再继续”应被看作一项会失败的执行步骤，而不是透明、无损的后台优化。** citeturn17search5turn17search1

### mini-swe-agent：纠错循环几乎就是 messages + shell + budget

mini-swe-agent 的价值在于它把复杂性砍到了很低。项目自己明确说明：history 完全线性，每一步只向 messages 追加；唯一主要执行工具是 bash；action 用独立的 `subprocess.run` 风格执行，而不是维护一个长寿命 shell session。citeturn15search0

当前 `DefaultAgent` 代码因此非常直白。运行态主要就是：

`messages`、累计 `cost`、`n_calls`、连续 format error 数、墙钟起始时间，再加配置中的 `step_limit`、`cost_limit`、`wall_time_limit_seconds` 和 `max_consecutive_format_errors`。`step()` 只是 query model，然后 `execute_actions()`；action 输出格式化成 observation，再追加回 messages。每轮 `finally` 都调用 `save()`，序列化内容包括 messages、模型调用次数、成本、config、exit status 和 submission。citeturn16view0

这也是一个很好的负结果：**在我审阅的当前 `DefaultAgent` 中，没有看到类似 LangGraph checkpoint 或 OpenHands conversation event tree 的“可从中间步骤重建执行”的 durable cursor。** `save()` 保存的是 trajectory 快照，方便审计和离线分析；它并不等于一个能在进程崩溃后精确从某个 action 边界继续执行的 workflow engine。这是从当前核心代码能直接得到的范围结论。citeturn16view0

它对“模型输出坏掉”的处理倒很具体。当前 main 中 `FormatError` 会把失败 model call 的费用补记进 agent cost，把失败返回携带的 messages 加回 trajectory/history，并累加连续格式错误；超过配置阈值后写入 `RepeatedFormatError` 退出。2026 年 7 月的 #914 曾发现一个 bug：API 已经收费，但 parse 失败导致 cost 没加到 agent budget，Agent 因而可能超过 `cost_limit` 继续跑；当前 main 的异常分支已经明确补上了这笔费用。这个例子很说明成熟纠错 loop 的现实：**预算计数本身也是失败恢复状态，不能只在“成功返回”路径上更新。** citeturn15search3turn16view0

但当前还有一个非常直接的 state-isolation bug。#909 指出复用同一个 `DefaultAgent` 跑第二个任务时，`run()` 会清空 messages，却没有重置 `n_calls`、cost、连续 format error 计数和 wall-clock start。于是第二个任务可能一启动就撞到上一个任务留下的限制；当前代码依然能看到 `run()` 重置 messages、而这些计数初始化只发生在构造函数中的结构。citeturn15search2turn16view0

工具层也暴露出“有时间预算 ≠ 能及时取回控制权”。#874 用公开的 `mini-swe-agent==2.4.2` 和 mock provider 重现了 provider 在 tool-call stream 中途卡住时，Agent 不能在预期 bounded run 内顺利回到上层控制；项目随后持续处理 timeout 路径。citeturn16view1

对于代码正确性，mini 并没有单独的 Verifier。模型自己决定何时执行 pytest、编译、grep 或其他 shell 命令，命令输出就是下一轮 observation；最终 SWE-bench 等 benchmark 再从 Agent 外部验证 patch 是否解决任务。项目公开报告了 SWE-bench Verified 等成绩和公开 evaluation 路径，但这些是外部任务 oracle，不是 `DefaultAgent` 内部的通用 validator。citeturn15search0turn15search7

这里可以用旧 SWE-agent 做一个很有价值的历史对照。它曾有正式 `RetryAgent`：保存每次 attempt 的 trajectory 和统计，reviewer 对 submission 评分；需要再试时会 `hard_reset()` 环境，建立新的子 Agent，按剩余总费用收紧单次 attempt budget，最后从多个 attempt 里选最好的一个。**这不是“修当前 patch”，而是“保留旧 attempt 证据，清空工作区后整次重跑”。** 当前项目已经把主方向转向 mini，因此这个机制适合当设计对照，不能当 2026 年 SWE-agent 栈的现行主路线。fileciteturn4file0L2-L2 citeturn10search4

## 编排型 Agent：LangGraph、PydanticAI 与 Microsoft Agent Framework

### LangGraph：把“失败的哪一步”保存得最明确

LangGraph 的 `StateSnapshot` 当前正式暴露 `values`、`next`、checkpoint config、`metadata.writes`、superstep `step`、`parent_config` 和 `tasks`；每个 task 还能带 `error`、`interrupts` 和 subgraph state。换句话说，它保存的不是单纯聊天记录，而是“现在有哪些值、下一步轮到谁、谁写了什么、谁失败了、父 checkpoint 是谁”。citeturn22search1

对并行失败尤其重要的是 **pending writes**。一个 superstep 里，如果 A、B 已经成功而 C 失败，A/B 的 task-level writes 会先写进 checkpointer；恢复这个 superstep 时，成功节点不必重新计算，只需要继续失败部分。完整 checkpoint 仍然只在 superstep 边界形成，但成功 task 的中间结果已经耐久化。这个机制比“整步全重跑”更接近真正的局部恢复。citeturn22search1

LangGraph 的历史修正也不覆盖旧 checkpoint。`update_state()` 会创建新 checkpoint；从旧 checkpoint replay 时，旧节点结果可以被跳过，之后的节点重新执行；也可以从旧 checkpoint fork 出另一条路线。这对“保留原证据、尝试替代修复”很强。citeturn22search1

⚠️ 但它的恢复边界非常明确：**checkpoint 是节点/superstep 边界，不是 Python 函数内部任意一行。** Interrupt、retry 或 replay 涉及一个节点时，节点可能从头进入；因此 interrupt 之前执行的非幂等副作用必须单独包装或设计成可安全重放。LangGraph 的 durable-execution 文档一直把确定性和幂等副作用作为关键约束，而不是声称 checkpoint 能自动解决副作用。citeturn1search22turn22search3

公开问题也印证了这个边界。#5672 记录过用户已经在流式 UI 看见的部分 state，因为 run 被 cancel 时尚未完整 flush 到 checkpoint，下一次加载时后端可能回到较旧状态；到 2026 年仍有人提供复现和 cleanup/write flush 分析。也就是说，**“用户看见了”不等于“durable state 已经 commit”。** citeturn22search0

LangGraph 有 runtime recursion limit。当前文档说明自 1.0.6 起默认是 1000 supersteps，并暴露当前 step 计数和 `RemainingSteps`，可以在达到硬限制之前自行降级。它能回答“循环最多跑多久”，但不能自动回答“这两次输出语义上是否没有进展”；后者仍需应用自己的状态和条件。citeturn14search15turn14search9

也因此，LangGraph 的 Planner、Verifier、Fixer **通常不是框架角色**。正式能力是 graph、node、edge、state、retry、checkpoint、interrupt；“planner node”“test node”“repair node”是应用定义。其上层 Deep Agents 增加规划和 subagent，但不能倒推成 LangGraph 基础 runtime 自带了一个代码验证器。citeturn18search0

### PydanticAI：最清楚地区分“应该让模型修”与“工具已经失败”

PydanticAI 最值得迁移的地方不是 graph，而是它把**可修复错误**做成了模型协议的一部分。

当前 API 中，工具参数 Pydantic validation 失败、validator 主动抛出 `ModelRetry`、tool timeout、调用不存在工具等情况可以产生 retry feedback，让模型收到具体失败原因再给一份新参数；`ToolFailed` 则用于表示这个工具执行已经失败，把失败作为结果交回模型，让模型换办法，而不是机械重复同一次调用。citeturn5search8turn5search11

这和“所有 exception 都 retry”差别很大。一个是：

> 你的这个字段/参数不合法，请只修这次生成。

另一个是：

> 这条路径本身失败了，你应该改变行动。

这两个状态被拆开，能明显减少无效循环。PydanticAI 也正式区分 tool retry 和 output retry 预算，而不是只给整个 Agent 一个模糊的 retry 次数。citeturn5search3turn5search8

它同时有 run-level `UsageLimits`，可约束请求、token、tool call 和成本；不过当前 issue 也指出，tool-call limit 更像 hard kill switch，模型默认不会因为“只剩两次工具调用”而提前知道自己快耗尽预算。换句话说，**计量和“预算感知”仍是两件事。** citeturn5search0turn19search10

跨进程 durable execution 则不是由 PydanticAI 自己维护一个统一数据库。官方现在把 Temporal、DBOS、Prefect 等作为正式/一方协作的 durability 后端，把 Agent 的模型调用和工具执行包装进各自的 durable unit；DBOS 这类后端会保存 workflow input 和每个完成 step 的 output，step 失败后从该 step 的开始重试。citeturn5search1turn5search12

🔥 这产生了一个非常重要的 **“双层重试冲突”**。2026-07-30 的 #6979 给出了完整可复现结果：同一个坏 tool argument，在普通 PydanticAI 中会转成 `RetryPromptPart`，模型随后把参数修好；可是在 Temporal/带 retry 的 DBOS 下，参数 `ValidationError` 先被 durable engine 当成 activity/step exception 重试了三次，最终 workflow 失败，错误根本没有成功回到模型纠错层。Prefect 在该复现里虽然最终成功，却也先浪费了 engine retry。citeturn19search0

说白了就是：

**模型可修的错误如果在错误的层被 durable runtime 截走，越“可靠”的自动重试反而越难修。**

这也是本轮最有价值的实现结论之一。citeturn19search0

PydanticAI 的 durable 层同样没有完全解决副作用。#7176 指出 capability hooks 在 orchestration replay/recovery 时可能重复触发外部状态写入；问题中甚至以 spend counter 举例，同一个已付费模型请求可能被重复累计，导致成本限制提前触发。citeturn19search3

另一个现实风险是“单轮爆炸”而不是循环次数。#6884 报告一个 model turn 产生 792 个并发 tool call，而当时没有 per-turn tool concurrency ceiling；在 Temporal 场景中因此出现 workflow-task completion 体积和资源问题。这说明只限制总 tool count、总 token 和循环次数，还不等于控制住瞬时故障半径。citeturn19search6

PydanticAI 也支持 deferred tools 和 approval：先产生带 `tool_call_id` 的 pending request，外部执行/人工批准后，再把与原 ID 匹配的 result/approval 填回后续 run。它适合长时间人工介入，因为“等待中的工具调用”本身就是外部可观察状态，不需要保留任何隐藏思维过程。citeturn5search2turn5search15

### Microsoft Agent Framework：checkpoint 很完整，但失败 superstep 仍可能整段重放

MAF 当前 checkpoint 文档非常具体。一个 checkpoint 在每个 superstep **全部 executor 完成后**创建，包含：

- 所有 executor 的当前状态；
- 下一 superstep 的 pending messages；
- pending requests 和 responses；
- shared states。  

Python 从 1.13.0 起还在首个 superstep 前和 request response 到达时增加 entry checkpoint，让一整次 workflow 更完整地可 replay。citeturn21search0

这里有一个经常被忽略的实现细节：**自定义 executor 的内部对象字段并不会凭空自动耐久化。** Python executor 要通过 `on_checkpoint_save()` 显式返回要存的状态，再在 `on_checkpoint_restore()` 中自己恢复；.NET 同样有对应 checkpointing/restored hook。也就是说，框架保存得很完整的前提，是 executor 把真正影响后续行为的本地状态声明出来。citeturn21search0

对于 `AgentExecutor`，框架则已经代劳一部分：当前文档说明它会序列化 agent session、当前 turn 的事件配置以及 pending 用户输入/function-call request，恢复后重新构造这些 pending 状态。citeturn21search10

MAF 的 HITL 也和 checkpoint 连起来了。pending request 会跟 checkpoint 一起保存，restore 后重新发出 `RequestInfoEvent`；调用者可以在 resume 时直接提供 response。普通 Sequential/Concurrent/Group Chat orchestration 本身并不会自动在任意位置等自由文本输入，需要显式加 `RequestPort` 或相应 workflow 结构。citeturn21search4

不过它和 LangGraph 的恢复粒度不同。MAF 文档建议对 partial failure 结合“tool 内部 retry”和“从 checkpoint 恢复”；而 checkpoint 是 superstep 完成后才有。于是一个 executor 在 superstep 中途已经调用了几个具有真实副作用的工具、然后崩溃时，恢复只能回到上一个成功 checkpoint。#3938 当前公开记录的正是这个问题：整次 agent turn 会从头 replay，已经执行过的 tool side effects 也可能再次发生。citeturn21search1turn14search5

MAF 在 2026 年还暴露过一些很典型的“持久化正确但审计/恢复关系不正确”的 bug。例如 #4588 中 runner 确实恢复了 `_iteration` 和 state，但恢复后创建的新 checkpoint 一度把 `previous_checkpoint_id` 重新设成 `None`，导致 checkpoint ancestry 断裂；该 issue 已进入修复链。另有 fan-in checkpoint state、subworkflow graph signature 和 SDK upgrade compatibility 等问题，说明 checkpoint schema 不光要保存数据，还必须稳定描述“这是哪一个 workflow 的哪条谱系”。citeturn14search1turn14search7turn14search12turn14search20

当前官方文档因此明确要求：从旧 checkpoint rehydrate 时，workflow topology 和 executor identity 必须兼容，Agent 还要使用稳定 ID；否则恢复应失败，而不能假装旧 state 能安全套到新 graph 上。citeturn21search0

## 失败恢复实证：真正会破的地方

把五个项目放到同一组故障里看，区别会非常明显。

| 失败类型 | 当前项目真正怎么做 | 已公开的边界 |
|---|---|---|
| **模型输出格式坏掉** | mini 捕获 `FormatError`，保留错误返回、计费、连续错误计数后继续问模型；PydanticAI 把 validation error / `ModelRetry` 反馈成下一轮修正请求。citeturn16view0turn5search8 | mini 曾漏记失败调用成本；PydanticAI durable backend 可能先把“模型可修错误”当系统 exception 重试，导致模型拿不到修正信息。citeturn15search3turn19search0 |
| **工具执行失败** | OpenHands/mini 主要把执行结果变成 observation，下一轮由模型决定换命令还是继续；PydanticAI 可以区分 `ModelRetry` 与 `ToolFailed`；MAF 推荐 tool 层 retry。citeturn17search2turn16view0turn5search11turn21search1 | “所有 error 都重试”会把不可恢复错误变成死循环；PydanticAI 过去 MCP `isError=true` 就曾被统一映射为 `ModelRetry`，后来出现专门 issue 修正这种分类。citeturn19search16 |
| **测试不通过** | OpenHands/mini 没有把 pytest/compiler failure 做成独立 universal state；测试输出就是工具 observation，模型再修改工作区。外部 benchmark 再判定最终 patch。citeturn17search2turn15search0 | 因为 verifier 不是强制 runtime 节点，Agent 可以漏跑测试、选错测试或误判“够好了”；是否修好取决于外部 oracle 是否被实际调用。 |
| **一个并行步骤中部分成功、部分失败** | LangGraph 把已成功 task 的 pending writes 单独持久化，resume 时不重跑它们。citeturn22search1 | 这是针对 graph state/write 的恢复；节点内部已经发生的外部副作用仍要自己保证幂等。citeturn1search22 |
| **进程/worker 中断** | OpenHands autosave base state + events；LangGraph 从 checkpoint/pending writes；MAF 从 workflow checkpoint；PydanticAI 依赖 Temporal/DBOS/Prefect 等 durable engine。citeturn17search3turn22search1turn21search0turn5search1 | mini 的核心 `DefaultAgent` 没有同级 durable resume；OpenHands 仍可能出现 duplicate observations；LangGraph cancellation 可能丢尚未 flush 的 streamed state；MAF failed superstep 内副作用可能重放。citeturn16view0turn17search4turn22search0turn14search5 |
| **重复执行/重复副作用** | 没有任何一个核心样本能普遍自动实现 exactly-once；普遍做法是缩小 checkpoint/task 边界、保存调用 ID、依赖幂等操作或业务去重。citeturn17search4turn19search3turn14search5turn22search1 | 这是当前最明确的共同负结果。 |
| **一直做同样的错事** | OpenHands 有正式 stuck detection；mini 只专门限制连续 format error 并有总 step/time/cost；LangGraph 主要靠 recursion limit；PydanticAI 靠局部 retry/usage budgets；MAF 本轮未找到统一语义级 stagnation detector。citeturn2search4turn16view0turn14search15turn5search0 | 除 OpenHands 外，多数 runtime 的“循环上限”只能判断跑太久，不能判断新结果与旧结果是否真的没有进展。 |
| **需要人工接手** | OpenHands pause/confirmation；LangGraph `interrupt()`；PydanticAI deferred approval/result；MAF RequestPort + persisted requests。citeturn2search14turn22search3turn5search2turn21search4 | mini 当前核心类没有同等级的 durable HITL 状态机。citeturn16view0 |

这里最值得强调的是“测试失败”这一行。

**成熟 Coding Agent 并没有普遍把测试框架变成一个内建 Verifier Agent。** OpenHands、mini-swe-agent 这种真正操作代码库的系统，通常是让模型调用 shell，再把测试结果当 observation；LangGraph、MAF 则只提供能挂 verifier 的运行框架；PydanticAI 的 validator 很正式，但验证的是 schema、tool/output contract，不是任意 Git 仓库的业务正确性。citeturn15search0turn17search2turn22search1turn21search3turn5search8

所以公开项目里更常见的实际链路不是：

> Planner 写代码 → 独立 Verifier Agent → Fixer Agent。

而是：

> Agent 改工作区 → Agent 自己运行某个检查 → 检查结果进入 observation → 同一个 Agent 再改。

或者在编排框架里：

> execution node → deterministic validator node → 条件 edge → repair node → 再回 validator。

后一种结构完全可以做，但多数时候是应用图，而不是框架默认替你定义好的角色。citeturn16view0turn22search1turn21search3

## 修复粒度、停止条件与预算控制

公开实现里至少能区分四种修复粒度，它们的失败性质差别很大。

| 修复粒度 | 代表实现 | 优点 | 公开暴露的问题 |
|---|---|---|---|
| **只修坏字段/坏工具参数** | PydanticAI `ModelRetry`、output/tool validation。citeturn5search8turn5search11 | 原成功上下文不动，成本最低；错误说明可以非常具体。 | durable engine 和 model retry 分层不当时，确定性 validation error 会被底层反复重试。citeturn19search0 |
| **重跑失败节点/step** | LangGraph checkpoint + pending writes；MAF checkpoint resume。citeturn22search1turn21search0 | 已完成步骤可以不重算，恢复范围比较清楚。 | 节点内部/failed superstep 内的副作用仍可能重复；checkpoint 边界太粗时风险扩大。citeturn14search5turn1search22 |
| **保留工作区，继续局部改代码** | OpenHands、mini-swe-agent。citeturn17search2turn15search0 | 已经正确的代码修改无需丢弃；测试结果直接驱动下一 patch。 | 错误修改也会累积在同一工作区；框架通常没有确定性办法知道应该回滚哪一处，而不是继续叠 patch。 |
| **清空环境，整次 attempt 重跑** | 旧 SWE-agent `RetryAgent` 历史实现。fileciteturn4file0L2-L2 | 能摆脱已经污染的工作区/路线，并保留多个 attempt 供 reviewer 选择。 | 重新支付大量模型/工具成本；前一 attempt 中的正确局部工作不能自然继承。 |

“重新编译上下文”则是第五类，但它和修代码不同。OpenHands condensation 会把长事件历史压缩为更小的可用上下文；mini 的默认 loop 则刻意保持线性 messages，不做复杂历史处理。公开故障表明，condensation/summarization 自己也会进入 loop 或 crash，因此它更适合被当作一个**可失败、可观察的转换步骤**，不能假设压缩完的 context 与原 evidence 等价。citeturn17search5turn17search1turn15search0

预算控制也没有统一方案：

| 项目 | 当前能确认的硬预算/停止机制 | “没进展”是否一等能力 |
|---|---|---|
| **OpenHands** | `max_iterations`，当前状态代码默认 500；execution status；stuck detector；LLM usage stats 被保存。fileciteturn2file0L2-L2 | **是，较强。** 有多种重复行为模式检测。citeturn2search4 |
| **mini-swe-agent** | `step_limit`、`cost_limit`、wall-clock limit、连续 format-error limit。citeturn16view0 | **否。** 能发现格式连续坏、时间/钱耗尽，但没有当前 core 的语义 stagnation detector。 |
| **LangGraph** | graph recursion limit；当前默认 1000 supersteps，并可读取剩余 steps。citeturn14search15 | **否，runtime 不替应用判断。** conditional edge 可以做，但判定逻辑由应用提供。 |
| **PydanticAI** | request/token/tool-call/cost `UsageLimits`，以及 tool/output retry budgets。citeturn5search0turn5search3 | **主要是局部失败次数，不是全局语义停滞。** |
| **MAF** | 本轮审阅的 workflow/checkpoint 核心文档没有给出一个统一的 token/cost/stagnation budget 合约。 | **无法判断有统一正式能力。** Handoff、conditional workflow 能换路线，但“什么叫没进展”仍需业务逻辑决定。citeturn21search2turn21search3 |

这里能得到一个比较稳的判断：

**“循环次数上限”和“没有进展”不应该被混成一个信号。** LangGraph recursion limit、mini step limit、Pydantic usage limits 能阻止无限消耗；只有 OpenHands 当前有较明确的行为级重复检测。至于“测试还是失败，但错误已经从 40 个减少到 2 个”这种情况，现有通用 runtime 并没有办法天然判断是进步还是原地踏步。citeturn2search4turn14search15turn16view0turn5search0

“需要换路线”也类似。MAF 提供正式 Handoff orchestration，LangGraph 可以条件跳到另一节点，OpenHands 同一 Agent 也能根据 observation 自己换工具；但我没有找到这些框架存在一个普遍正式算法，会因为连续两个验证结果相似，就自动废弃策略、生成新 plan。**路线切换的执行结构很成熟，路线切换的语义判断仍主要由 Agent/application 决定。** citeturn21search2turn22search1turn17search2

## 对长文结构化抽取的可迁移性

从这些项目迁移到长文结构化抽取时，最有价值的并不是复制 Coding Agent 的 shell/test loop，而是复制**纠错粒度和错误分类**。

### 可以直接迁移的机制

**PydanticAI 的“局部可修错误”模式最直接。** 对长文抽取而言，schema violation、字段类型错误、枚举不合法、缺少必填字段、引用位置不存在，都更接近“坏 tool arguments / 坏 structured output”，适合返回结构化 validation error，只修失败字段或失败记录，而不是把整篇抽取重新生成一遍。PydanticAI 的公开实现说明这种 model-facing retry 可以作为正式协议，而不是靠自然语言说“再检查一下”。citeturn5search8turn5search11

**LangGraph 的 pending writes 适合“批量抽取里局部失败”。** 例如多个章节/实体并行处理时，已经通过验证的分支可以作为 durable writes 保存；某一个分支失败后，只让失败 task 重算，而不是丢掉整批成功结果。它和代码编译器无关，是纯执行语义，因此可迁移性很高。citeturn22search1

**OpenHands 的事件谱系/分支机制适合“保留旧提取证据，但切换当前答案路线”。** 当前视图可以只走新 branch，旧 extraction、旧 validator 回执仍留在 event history。它比把某个 JSON 字段原地覆盖更适合做审计，因为之后还能回答“为什么这一条后来被改掉”。fileciteturn2file0L2-L2

**MAF 的 pending request checkpoint 适合把人工判定变成长期挂起状态。** 人工接手并不需要让 Agent 的整个上下文常驻内存；待确认 request 可以进入 checkpoint，恢复时重新发出。这个机制同样不依赖代码测试。citeturn21search4turn21search0

**OpenHands 的 stuck detection 思路也可迁移，但迁移的是可观察行为签名，不是它现成的代码规则。** “连续同一 action+error”“重复交替模式”可以对应到连续相同 validator error、相同证据区间反复抽取、同一字段反复在两个值间震荡。这里需要领域自己的 signature，但“由 runtime 判重，而不是要求模型自己意识到自己卡住”这一实现方向已经被现实 Agent 验证。citeturn2search4

### 不应该直接照搬的代码专用机制

**git hard reset + 整次 attempt 重跑** 很依赖软件工程任务。旧 SWE-agent 可以重置 repository 到 base commit，然后独立再做一次 patch；长文抽取中的原始文档当然可以重新读，但已经得到的可靠 evidence、人工确认和局部抽取不应该为了“换路线”一起丢掉。旧 RetryAgent 更适合作为反例：它证明整次重试可行，同时也说明这种粒度成本很高。fileciteturn4file0L2-L2

**编译器和测试套件提供的确定性 oracle 不能直接迁移。** `pytest` exit code、编译成功、静态类型检查通常有明确机器结果；长文中的“人物动机是否抽对”“关系是否暗示而非明说”“某段是否足以支持结论”往往不是同等级确定性信号。因此 Coding Agent 中“测试绿了就停”的模式不能直接变成“LLM judge 说 OK 就停”。公开项目本身也说明，大部分 Agent runtime 只负责把 checker 输出带回来，并不保证 checker 就是正确 oracle。citeturn15search0turn22search1turn21search3

**shell 重执行天然更容易隐藏重复副作用。** 对只读文档抽取，重新读一段文本风险较低；一旦抽取流程同时更新索引、数据库、用户确认状态或外部系统，就重新遇到 MAF/PydanticAI/OpenHands 已经公开暴露的 exactly-once 问题。因此最该迁移的不是“自动 retry”，而是把“纯计算重试”和“已经产生外部写入的步骤”严格区分。citeturn14search5turn19search3turn17search4

**context condensation 也不能当“修复”。** OpenHands 已经证明压缩自身会出错；PydanticAI 也出现过 retry 时上下文/Responses API history 重发导致重复 stored messages 的 bug。它最多解决上下文容量问题，不证明新上下文保留了足够证据，也不证明上一轮失败原因已经消失。citeturn17search5turn19search4

因此，对长文结构化抽取最有参考价值的不是“多 Agent 角色数量”，而是下面这组已经被现行项目实证过的纠错边界：

**坏结构 → 局部返修；失败分支 → 只重跑失败分支；旧结果 → 保留谱系而非覆盖；重复错误 → runtime 判停；需要人 → 把 pending request 持久化；有副作用 → 不把普通 retry 当 exactly-once。** 这些都可以只依赖外部可观察的输入、输出、validator receipt 和执行状态，不需要也不应该依赖模型隐藏思维链。citeturn5search8turn22search1turn21search4turn2search4turn14search5

## 证据边界与负结果

本轮有几项不能从公开证据可靠推出，我明确保留为“无法判断”。

**无法判断哪个项目拥有普遍最好的自动修复成功率。** OpenHands 和 mini-swe-agent 有公开软件工程/Agent evaluation，mini 也公开报告 SWE-bench Verified 成绩；LangGraph、PydanticAI、MAF 更多是基础框架，任务成功率取决于其上应用。把这些 benchmark 直接横向排名会把 framework quality、model quality、prompt、tooling 和 benchmark harness 混在一起。citeturn15search0turn17search9turn18search0

**无法判断 OpenHands Critic 已经足够稳定，能当通用生成后 Verifier。** 官方目前仍明确标注该能力 highly experimental；所以本报告没有把它等同于正式 checkpoint/event runtime。citeturn2search2

**无法判断 MAF 存在一个统一的“token + cost + semantic stagnation”控制器。** 当前 workflow 文档非常完整地定义 checkpoint、state、HITL 和 orchestration，但本轮没有找到一个和 PydanticAI `UsageLimits` 或 OpenHands stuck detector 等价的跨 workflow 统一正式接口，因此没有用通用 Agent 概念补这个空白。citeturn21search0turn21search2

**无法把 mini-swe-agent 的 trajectory persistence 称为 durable resume。** 当前 `DefaultAgent` 的保存内容非常清楚，但我没有在该核心类中找到从 trajectory checkpoint 精确恢复 action loop 的对应 runner；因此这里严格称为“持续保存轨迹/状态快照”，不提升为进程级耐久执行。citeturn16view0

**公开 issue 只能证明失败模式存在，不能证明发生频率。** #3045、#3938、#6979、#5672 等有些是生产报告，有些是维护者或用户构造的最小复现，还有部分 issue 明确由 Agent 代用户提交。它们足够用来证明“机制存在这个边界”，但不能据此推导“某框架经常崩”。citeturn17search4turn14search5turn19search0turn22search0

综合这些原始证据，成熟 Agent 在 2026 年的真正分水岭不是“会不会反思并再生成一次”，而是：**失败能不能被分类到正确层；能不能只重做最小必要范围；旧证据是否仍可追溯；成功的局部工作能否免于重算；预算是否覆盖失败路径；以及重放时是否会重复真实副作用。** OpenHands 强在事件证据与行为停滞检测，LangGraph 强在 checkpoint/pending-write 粒度，PydanticAI 强在 model-facing typed repair，MAF 强在完整 workflow state 与长期 request 恢复，mini-swe-agent 则清楚展示了一个真实 Coding Agent 在极简状态机下能做到什么、又在哪些地方必须依赖外部 harness。citeturn17search3turn2search4turn22search1turn5search8turn21search0turn16view0

来源：ChatGPT