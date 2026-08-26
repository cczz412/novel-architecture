# 14 最低思考开／关对照

同一冻结 Prompt、同一四题、温度 0、输出预算 4096、每题一次、重试 0。已经完成的 32 次非思考没有重跑。思考档一律用各家能开的最低档，没有上最高档。

这不是 CCZ-57 正式成果，也不评分、不升 Gold。

机器回执：
- [13_thinking_low_agent_plan_partial.json](13_thinking_low_agent_plan_partial.json)
- [13_thinking_low_deepseek_partial.json](13_thinking_low_deepseek_partial.json)
- [13_thinking_low_sensenova_partial.json](13_thinking_low_sensenova_partial.json)
- [13_thinking_low_ling_partial.json](13_thinking_low_ling_partial.json)
- [15_qwen_nonthinking_partial.json](15_qwen_nonthinking_partial.json)
- [15_qwen_thinking_low_partial.json](15_qwen_thinking_low_partial.json)
- [15_glm53flash_nonthinking_partial.json](15_glm53flash_nonthinking_partial.json)
- [15_glm53flash_thinking_low_partial.json](15_glm53flash_thinking_low_partial.json)

## 一句话

最低思考不是自动升级。这轮里它更常干的事是：把输出预算吃光、把 JSON 写坏、把本来有的因果句拆回并列事件。真正变好的点很少，而且集中在「空 speaker」这种守合同问题，不是跨句推理。

## Q4 因果：开思考没有帮上忙

非思考时，只有 Mini 和 Lite 把跳闸和渗水写成一条因果。开了最低思考之后，这两家都改回并列事件，「因／因为」那条没了。

Turbo、官方 Flash、MiniMax、GLM-5.2、SenseNova、Ling、千问、GLM-5.3 Flash，开思考后仍然没有明确因果命题。GLM-5.2 思考稿里出现过「跳闸后开始渗水」这种句子，但整段包在没写完的代码围栏里，解析失败，不能算命中。

## 格式和预算：好几家开思考后更差

**输出被思考过程吃光（completion_tokens=4096，正文空）**

- Doubao Turbo Q1／Q2：思考写了约一千字，最终答案是空的。耗时从约 10 秒变成约 95 秒。
- MiniMax M3 四题全空。思考过程上万字，JSON 一个字没有。非思考时这四题 Schema 都是合法的。
- GLM-5.2 的 Q2／Q3、Ling 的 Q1／Q3／Q4，同样顶满 4096。

**JSON 写坏**

- 千问非思考 4/4 合法；最低思考只有 Q1 合法，Q2–Q4 句子里的中文引号没转义。
- SenseNova 非思考 Q2 合法；开思考后同样把「货已经卸完」的引号写进字符串，解析失败。思考 Token 仍是 0，像是档位打了，但账单上没有真正的思考量。
- Doubao Mini 非思考 Q2 合法；开思考后 Q2 被 4096 截断。
- Doubao Lite 非思考 Q2 本来就坏；开思考后 Q2 反而合法了。这是这轮里少数格式变好的例子，但 Q4 因果丢了。

## 空 speaker：官方 Flash 的 Q2 变好了

官方 DeepSeek V4 Flash 非思考 Q2 有 9 个空 `speaker`，Schema 不合法。最低思考 Q2 改成省略 `speaker`，Schema 合法。Q1／Q3／Q4 两边都合法。Q4 还是并列事件。思考 Token 389–2862，耗时大约变成非思考的 2–12 倍。

Turbo 非思考 Q1／Q2 也是空 `speaker`。开思考后这两题没有最终 JSON，谈不上修好。

## 新补的两家

**千问 `qwen3.8-max`**（北京 DashScope，目录精确命中）

- 非思考：身份对，四题直接 JSON、Schema 合法。Q4 事件都在，没有因果句。
- 最低思考：`reasoning_effort=low`（官方默认是 `xhigh`）。Q1 合法；Q2–Q4 引号把 JSON 写坏。耗时大约 5–8 倍。

千问这族思考模式不能跟 `json_object` 一起发，所以思考轮只靠冻结 Prompt 约束 JSON。这是通道限制，不是改了题面。

**GLM 5.3 Flash**（OpenRouter `z-ai/glm-5.3-flash`，目录精确命中，思考强制）

- 非思考 Q1 被接口拒绝：`Reasoning is mandatory for this endpoint and cannot be disabled.` 后面三题没再打。
- 最低思考 `low`（官方默认 `max`）四题身份对、JSON／Schema 合法。思考 Token 每次只有 3，几乎等于开关开着但没怎么想。Q4 仍是并列事件。

## 对照表（只看合同和 Q4 因果）

| 模型 | 非思考 Schema（Q1–Q4） | 最低思考 Schema（Q1–Q4） | 非思考 Q4 因果 | 思考 Q4 因果 |
|---|---|---|---|---|
| Doubao Turbo | 空 speaker／空 speaker／合法／合法 | 截断空／截断空／合法／合法 | 无 | 无 |
| Doubao Mini | 四题合法 | 合法／截断空／合法／合法 | 有 | 无 |
| Doubao Lite | 合法／JSON 坏／合法／合法 | 四题合法 | 有 | 无 |
| MiniMax M3 | 四题合法 | 四题截断空 | 无 | 无 |
| GLM-5.2 | 围栏／围栏／合法／合法 | 围栏可剥／截断／截断／围栏写坏 | 无 | 无（稿子里有「跳闸后」但解析失败） |
| 官方 Flash | 合法／空 speaker／合法／合法 | 四题合法 | 无 | 无 |
| SenseNova 6.8 Flash Lite | 四题合法 | 合法／引号写坏／合法／合法 | 无 | 无 |
| Ling-3.0-flash | 四题合法 | 截断／合法／截断／截断 | 无 | 无 |
| 千问 qwen3.8-max | 四题合法 | 合法／引号写坏／引号写坏／引号写坏 | 无 | 无 |
| GLM-5.3 Flash | 关不掉（Q1 400） | 四题合法 | 无对照 | 无 |

GLM-5.2 没有 `low`，这轮用的是官方更低的那档 `high`（不传会默认 `max`）。MiniMax 和 Ling 没有力度档，开思考就是开。

## 这轮说明什么

顾问说的那层切分，这批结果更站得住：

- 明说事实（动作、位置、改状态、台词）用非思考更稳、更便宜。
- 跨句因果没有因为打开最低思考就出现；Mini／Lite 反而是非思考才写成因果。
- 思考输出不能直接当客观事实。这轮甚至经常连合法 JSON 都交不出来。

旧整章实验里 Flash 最高思考档几乎没加有效命中、Token 却大约 4 倍。这次短题、最低档，方向还是一样：更贵、更慢，不保证更好。
