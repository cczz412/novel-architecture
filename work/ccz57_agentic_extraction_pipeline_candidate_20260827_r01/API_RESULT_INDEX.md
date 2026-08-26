# CCZ-57 L1 API 可拆性探针｜成绩总入口

## 怎么理解这些成绩

每个模型只面对同一套四道人工合成短材料：人物动作、状态变化、关系变化和明确因果。每题只调用一次，不重试，不改 Prompt 救结果。

所以这里记录的是“某个精确模型在这四题上实际交了什么”，不是正式分数、准确率、排名、Gold 或产品选型。

冻结系统 Prompt SHA-256：`57ab1d68a4ebe3ee4bc7c57693247e9fa7bc1879252b57254ff25b0220bd2a2b`。

## 非思考对照

| 精确模型／通道 | Q1 | Q2 | Q3 | Q4 | Q4 有没有明确因果 |
|---|---|---|---|---|---|
| `doubao-seed-2-1-turbo-260628`／Agent Plan | Schema 不合法：空 `speaker` | Schema 不合法：空 `speaker` | 合法 | 合法 | 无 |
| `deepseek-v4-flash`／官方 API | 合法 | Schema 不合法：空 `speaker` | 合法 | 合法 | 无 |
| Doubao Mini／Agent Plan | 合法 | 合法 | 合法 | 合法 | 有 |
| Doubao Lite／Agent Plan | 合法 | JSON 写坏 | 合法 | 合法 | 有 |
| MiniMax M3／Agent Plan | 合法 | 合法 | 合法 | 合法 | 无 |
| GLM-5.2／Agent Plan | 外层代码围栏 | 外层代码围栏 | 合法 | 合法 | 无 |
| `sensenova-6.8-flash-lite`／日日新 Token Plan | 合法 | 合法 | 合法 | 合法 | 无 |
| `Ling-3.0-flash`／蚂蚁百灵 | 合法 | 合法 | 合法 | 合法 | 无 |
| `qwen3.8-max`／DashScope | 合法 | 合法 | 合法 | 合法 | 无 |
| `z-ai/glm-5.3-flash`／OpenRouter | 端点不允许关闭思考，Q1 返回 400 后停止 | 未调用 | 未调用 | 未调用 | 没有非思考对照 |

这里的“合法”只表示 JSON 和冻结 v2.1 Schema 能通过，不表示事实完整、说话人正确或因果关系正确。

## 最低思考对照

输出预算是 4096，所有模型只开供应商允许的最低思考档：

| 模型 | Q1～Q4 合同表现 | Q4 明确因果 | 最明显的问题 |
|---|---|---|---|
| Doubao Turbo | 截断空／截断空／合法／合法 | 无 | Q1、Q2 思考吃满预算，最终答案为空 |
| Doubao Mini | 合法／截断空／合法／合法 | 无 | 非思考时出现的因果句丢失 |
| Doubao Lite | 四题合法 | 无 | Q2 格式修好，但 Q4 因果丢失 |
| MiniMax M3 | 四题截断空 | 无 | 四题都没有最终 JSON |
| GLM-5.2 | 围栏可剥／截断／截断／围栏写坏 | 无 | 多题没有可进入合同的完整结果 |
| 官方 DeepSeek Flash | 四题合法 | 无 | Q2 空 `speaker` 修好，但仍没补出因果 |
| SenseNova 6.8 Flash Lite | 合法／JSON 引号写坏／合法／合法 | 无 | Q2 从合法退化成坏 JSON |
| Ling-3.0-flash | 截断／合法／截断／截断 | 无 | 三题顶满 4096 |
| `qwen3.8-max` | 合法／JSON 引号写坏／JSON 引号写坏／JSON 引号写坏 | 无 | 三题从合法退化成坏 JSON |
| GLM-5.3 Flash | 四题合法 | 无 | 模型强制思考；没有可比较的关闭思考组 |

当前四题里，打开最低思考没有稳定补出因果关系。Mini 和 Lite 非思考时写出的“因／因为”，开思考后反而消失。这个现象只能描述本轮样本，不能外推到其他小说材料。

## 完整观察和回执去哪看

- Doubao Turbo 逐题观察：[`input_package/03_LOCAL_PROBE/04_逐题观察表.md`](input_package/03_LOCAL_PROBE/04_逐题观察表.md)
- 官方 DeepSeek Flash 非思考：[`input_package/03_LOCAL_PROBE/08_官方Flash非思考观察.md`](input_package/03_LOCAL_PROBE/08_官方Flash非思考观察.md)
- Agent Plan 第二批：[`input_package/03_LOCAL_PROBE/10_AgentPlan第二批观察.md`](input_package/03_LOCAL_PROBE/10_AgentPlan第二批观察.md)
- SenseNova 与 Ling：[`input_package/03_LOCAL_PROBE/12_sensenova68_ling30_observe.md`](input_package/03_LOCAL_PROBE/12_sensenova68_ling30_observe.md)
- 最低思考总对照：[`input_package/03_LOCAL_PROBE/14_thinking_low_observe.md`](input_package/03_LOCAL_PROBE/14_thinking_low_observe.md)
- 4096／8192 回执：`input_package/03_LOCAL_PROBE/17_t8k_*.json`
- 所有冻结请求：[`input_package/03_LOCAL_PROBE/requests/`](input_package/03_LOCAL_PROBE/requests/)
- 所有原始回复：[`input_package/03_LOCAL_PROBE/responses/raw/`](input_package/03_LOCAL_PROBE/responses/raw/)
- 运行回执与模型目录：[`input_package/03_LOCAL_PROBE/`](input_package/03_LOCAL_PROBE/)

## 当前能下的结论

较弱 API 模型不是完全拆不出内容；人物动作、状态变化和关系动作经常能够抽到。最明显的风险是：输出合同不稳定、正确项可能被后续思考破坏、因果两端虽然都在却没有被连起来。

小说辅助产品现在还不能把这些回件直接交给后续检索和续写。它缺少正式的接收检查、不可变原件保存、错误路由、局部修复、独立验证和版本选择能力。作者如果直接使用当前结果，仍可能遇到“看起来有 JSON，但关键关系已经丢了”的问题。

来源：Codex
