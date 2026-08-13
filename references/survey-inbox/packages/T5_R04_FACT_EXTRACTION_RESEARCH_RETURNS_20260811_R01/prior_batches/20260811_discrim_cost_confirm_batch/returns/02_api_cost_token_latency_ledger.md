✅ 结论：下一轮不能只在结果表里补一列“费用”。要把“一道题”和“实际发出的 API 请求”拆开记：

* `task_id`：一道正式考题。
* `attempt_id`：一次真实 HTTP/API 请求。重试必须新建一行，不能覆盖原请求。
* 选型主指标用 `cost@quality`：先过质量、格式、失败率门，再选平均任务成本最低的条件。
* 套餐调用允许“本次实付 0 元”，但跨平台比较成本绝不能记 0；至少同时保留实付成本、摊销成本、按量参考成本。
* HTTP 200 但空正文、非法 JSON、截断、只有思考没有答案，都属于模型条件失败，不得从质量分母里消失。

公开领域目前没有一个基准完整覆盖 Token、套餐、重试、失败和质量。比较稳妥的做法是把四套口径拼起来：

| 公开口径                | 可以直接借用什么                                                                                                                                                                                                                      |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HELM                | 每个请求保留实际运行时间，并同时考虑提示 Token 和生成 Token；但它不是商业 API 账单规范。[[HELM Metrics](https://crfm-helm.readthedocs.io/en/latest/metrics/)](https://crfm-helm.readthedocs.io/en/latest/metrics/)                                                                                                      |
| Artificial Analysis | 区分供应商原生 Token 和统一性能 Token；成本用供应商返回的输入、缓存、推理、输出 Token 算 `cost per task`；时延拆 TTFT、首个答案 Token、完整响应时间。[[总方法](https://artificialanalysis.ai/methodology)](https://artificialanalysis.ai/methodology)、[[性能方法](https://artificialanalysis.ai/methodology/performance-benchmarking)](https://artificialanalysis.ai/methodology/performance-benchmarking) |
| OpenTelemetry GenAI | 已形成跨厂商字段：请求／响应模型、完成原因、输入／输出／缓存写入／缓存读取／推理 Token、首块时间和错误类型。[[GenAI 字段规范](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md)](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md)                                                    |
| FinOps FOCUS        | 区分目录价、合同价、账单实付价和包含预付／订阅摊销的有效成本，正好解决套餐不能记零的问题。[[FOCUS 1.1](https://focus.finops.org/focus-specification/v1-1/)](https://focus.finops.org/focus-specification/v1-1/)                                                                                                                  |

## 每次调用最小必记字段

建议一行只代表一次真实请求。绝大部分字段应由调用器自动写，不要让执行人员手填。

| 分组       | 必记字段                                                                                                                                       | 填写规则                                             | 依据                                                                                                                          |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| 任务身份     | `run_id`、`task_id`、`case_id`、`condition_id`                                                                                                | `condition_id` 至少绑定平台、接入点、模型、Prompt 版本、思考档、服务档   | 同模型经不同平台调用也属于不同 endpoint；Artificial Analysis 也把 model 与 endpoint 分开                                                         |
| 请求身份     | `attempt_id`、`attempt_no`、`is_final_attempt`、`retry_of_attempt_id`                                                                         | 初次为 1；每次重试新建一行                                   | 行业惯例；防止重试覆盖原账                                                                                                               |
| 平台身份     | `provider`、`endpoint`、`region`、`service_tier`、`billing_mode`、`plan_id`                                                                     | `billing_mode` 取 `payg/subscription/free_credit` | 成本和时延都依赖 endpoint、区域和服务档                                                                                                    |
| 模型身份     | `request_model`、`response_model`、`model_revision`、`system_fingerprint`                                                                     | 请求别名和响应实际模型都记；缺失写 `null`，不能自行猜                   | OpenTelemetry 要求尽量记录实际返回模型；硅基流动也返回 `system_fingerprint`                                                                     |
| 调用器      | `api_family`、`sdk_name_version`、`sdk_max_retries`                                                                                          | 正式评测建议 SDK 自动重试设为 0                              | OpenAI 官方 SDK 默认会自动重试连接错误、408、409、429 和 5xx 两次，不控制就会漏记真实请求。[[SDK 重试说明](https://github.com/openai/openai-python)](https://github.com/openai/openai-python)              |
| 请求合同     | `prompt_version`、`request_sha256`、`temperature`、`top_p`、`seed`、`max_output_tokens`、`timeout_ms`、`stream`                                   | 原始请求另存，只在表内放路径和 SHA                              | 保证调用条件可回验                                                                                                                   |
| 思考配置     | `reasoning_enabled`、`reasoning_effort_requested`、`reasoning_effort_effective`、`thinking_budget`                                            | “请求档位”和“平台实际映射档位”分开记                             | 硅基流动等平台存在档位映射；同模型不同思考档必须拆条件。[[硅基流动 Chat API](https://docs.siliconflow.cn/cn/api-reference/chat-completions/chat-completions)](https://docs.siliconflow.cn/cn/api-reference/chat-completions/chat-completions) |
| 缓存配置     | `cache_mode`、`cache_state`、`cache_prefix_sha256`                                                                                           | `cache_state` 取 `cold/warm/uncontrolled`         | 缓存读、写价格不同，且会同时改变时延                                                                                                          |
| 原始用量     | `usage_raw_json`、`usage_source`、`usage_mapping_version`                                                                                    | 原样保存供应商返回值；本地重新分词只能做辅助，不能替代账单 Token              | Artificial Analysis 用供应商原生 Token 算钱                                                                                         |
| Token 分账 | `input_tokens_total`、`cache_read_input_tokens`、`cache_write_input_tokens`、`output_tokens_total`、`reasoning_output_tokens`、`total_tokens`   | 缺失写 `null`，绝不补 0                                 | OpenTelemetry 标准字段；硅基流动响应也已给出这些分账                                                                                           |
| 套餐用量     | `plan_unit_type`、`plan_units_consumed`、`plan_balance_before`、`plan_balance_after`                                                          | Agent Plan 可记 `AFP`；至少保存运行前后额度快照                 | 火山方舟把 AFP 定义为统一套餐用量单位。[[Agent Plan 概览](https://www.volcengine.com/docs/82379/2366394)](https://www.volcengine.com/docs/82379/2366394)                                        |
| 时间戳      | `task_ready_at`、`request_sent_at`、`first_chunk_at`、`first_answer_at`、`completed_at`                                                        | 使用同一台机器的单调时钟计算耗时                                 | 对应 TTFT、TTFA 和完整响应时间                                                                                                        |
| 等待分账     | `client_queue_ms`、`rate_limit_wait_ms`、`retry_backoff_ms`                                                                                  | 没发生填 0；无法观测写 `null`                              | 限流等待不能混进“模型生成速度”                                                                                                            |
| 请求结果     | `http_status`、`provider_request_id`、`finish_reason`、`content_empty`                                                                        | 流式调用还要保存最后一个 usage 事件                            | OpenTelemetry；硅基流动响应头提供 trace ID                                                                                            |
| 失败分类     | `transport_status`、`parse_status`、`schema_status`、`failure_class`、`error_code`、`retry_eligible`、`retry_reason`                             | 使用冻结枚举，禁止自由发挥                                    | OpenTelemetry 统一用 `error.type` 记录失败                                                                                         |
| 质量去向     | `primary_quality_disposition`、`conditional_semantic_eligible`、`format_gate_pass`                                                           | 明确该任务是正常评分、按零分计入，还是仅在条件分中 N/A                    | 防止失败样本从质量分母消失                                                                                                               |
| 成本       | `price_snapshot_id`、`cost_list_estimated`、`cost_reference_payg`、`cost_effective_allocated`、`cost_billed_actual`、`billing_reconcile_status` | 估算、摊销、实付不能互相覆盖                                   | FOCUS 的 List／Effective／Billed Cost 分账                                                                                       |
| 环境       | `client_region`、`concurrency_at_send`                                                                                                      | 整轮相同也必须有运行级快照                                    | TTFT 含网络位置影响；并发会改变排队与吞吐                                                                                                     |

🔥 两个最容易记错的地方：

* `reasoning_output_tokens` 通常已经包含在 `output_tokens_total` 中，不能再相加一次。
* 缓存读写 Token 在规范化后的 `input_tokens_total` 中通常也是子集，不能重复计数。

OpenTelemetry明确要求推理 Token 包含在输出总数中，缓存 Token 包含在输入总数中；供应商原始字段关系不一致，所以必须保留 `usage_raw_json`，再通过带版本号的映射规则转成统一字段。[[OpenTelemetry GenAI](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md)](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md)

另建一张不可修改的 `PRICE_SNAPSHOT` 表，至少保存：

`price_snapshot_id`、价格生效时间、官方来源 URL、币种、汇率及日期、普通输入价、缓存读取价、缓存写入价、输出价、推理价、缓存存储价、长上下文阶梯、Batch／优先服务倍率、套餐费、套餐总额度、模型抵扣系数和各时间窗口上限。

硅基流动的公开价已经同时存在输入、输出、缓存命中价和上下文长度阶梯；Google 也存在长上下文阶梯，并明确输出价格包含 thinking Token。说明“每百万 Token 单价”不是一个数字，而是一组带条件的价格。[[硅基流动价格页](https://siliconflow.cn/pricing)](https://siliconflow.cn/pricing)、[[Gemini API 定价](https://ai.google.dev/gemini-api/docs/pricing)](https://ai.google.dev/gemini-api/docs/pricing)

## 归一化公式

先把供应商原始字段转换成互不重叠的计费桶：

* (I)：计费输入总 Token，包含缓存部分。
* (C_r)：缓存读取 Token。
* (C_w)：缓存写入 Token。
* (O)：计费输出总 Token，包含推理和不可见结构 Token。
* (R)：推理 Token，是 (O) 的子集。

一次真实请求的参考按量成本：

[
C_a =
\frac{
(I-C_r-C_w)P_i+
C_rP_{cr}+
C_wP_{cw}+
(O-R)P_o+
RP_{reason}
}{10^6}
+C_{extra}
]

如果该平台把推理 Token 按普通输出价收费，令 (P_{reason}=P_o)，输出部分就等价于 (O\times P_o)。不要再把 (R) 加到 (O) 上。

OpenAI、Anthropic、Google 当前官方口径都存在“思考 Token 按输出 Token 计费”的情况；火山方舟也明确原始思考 Token 参与计费。但这不能外推给所有平台和转售接口，仍应逐 endpoint 冻结价格规则。[[OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning)](https://developers.openai.com/api/docs/guides/reasoning)、[[Claude extended thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)、[[火山方舟深度思考](https://www.volcengine.com/docs/82379/1449737)](https://www.volcengine.com/docs/82379/1449737)

整组条件的基础成本指标：

[
\text{cost-per-scheduled-task}
==============================

\frac{\sum_{\text{全部真实 attempts}} C_a}
{N_{\text{预定任务}}}
]

同时报告：

[
\text{cost-per-valid-task}
==========================

\frac{\sum C_a}
{N_{\text{最终格式有效任务}}}
]

前者防止失败多的接口显得“便宜”；后者直接反映得到一份可用结果要花多少钱。

⚠️ 不建议拿“输入价和输出价平均一下”或套通用输入输出比例。Artificial Analysis 的 blended price 使用固定 `缓存:输入:输出 = 7:2:1`，那只是统一展示假设；它真正的 cost-per-task 仍按实际工作负载消耗计算。不同模型 tokenizer 不同，同一段中文会产生不同数量的原生 Token，因此相同题目的实际任务成本才是可比单位。[[Artificial Analysis 方法](https://artificialanalysis.ai/methodology)](https://artificialanalysis.ai/methodology)

## `cost-per-task` 和 `cost@quality` 怎么用

两者不是二选一：

* `cost-per-task` 是底账：每做一道题平均花多少钱。
* `cost@quality` 是选型规则：达到产品线的条件中，谁的任务成本最低。

推荐写成约束优化：

[
j^*=
\arg\min_j \text{cost-per-scheduled-task}_j
]

前提是条件 (j) 同时满足：

* F1 的置信下界 ≥ 预设门槛；
* Recall 的置信下界 ≥ 预设门槛；
* 格式通过率 ≥ 门槛；
* 假事实率的置信上界 ≤ 门槛；
* 最终任务失败率 ≤ 门槛；
* 如果产品有要求，P95 端到端时延 ≤ 门槛。

说白了就是：先确认“够不够用”，再在够用的条件里找最便宜的。成本感知 LLM 研究通常也是在固定质量下最小化成本，或在固定预算下最大化质量，而不是简单算“分数除以价格”。[[FrugalGPT](https://arxiv.org/abs/2305.05176)](https://arxiv.org/abs/2305.05176)

如果没有任何条件过线，就报告质量—成本 Pareto 前沿，不强行选冠军。

## 套餐和按量怎么公平放在一起

套餐至少保留三本账：

| 成本字段                       | 含义                         | 能不能拿来跨平台排名  |
| -------------------------- | -------------------------- | ----------- |
| `cost_billed_actual`       | 这轮账单实际新增金额；套餐内可能为 0        | ❌ 不能单独使用    |
| `cost_reference_payg`      | 按冻结的公开价／合同价，对实际 Token 重新估值 | ✅ 可做基准对照    |
| `cost_effective_allocated` | 把套餐费按预计或实际使用量摊到任务          | ✅ 最适合真实部署预算 |

指定月业务量 (V) 后：

[
C_{\text{month}}(V)
===================

F_{\text{plan}}
+C_{\text{overage}}(V)
+C_{\text{extra}}(V)
]

[
C_{\text{effective/task}}(V)
============================

\frac{C_{\text{month}}(V)}
{N_{\text{scheduled}}(V)}
]

如果要把套餐费分到单次调用：

[
C_{\text{allocated},a}
======================

F_{\text{plan}}
\times
\frac{u_a}{U_{\text{period}}}
+
C_{\text{overage},a}
]

其中 (u_a) 是这次调用实际消耗的套餐积分，(U_{\text{period}}) 是整个月预计或实际用掉的积分，不能未经说明直接拿“套餐最大额度”当分母。否则默认 100% 用满，会得到过分乐观的成本。

火山方舟 Agent Plan 的 AFP 本身就是带模型输入／输出抵扣系数的复合单位，官方公式形如：

[
AFP=\frac{\text{输入 Token}\times输入系数+
\text{输出 Token}\times输出系数}{10,000}
]

所以一 AFP 不能直接理解成固定数量的 Token；必须保存调用时的模型系数版本。[[AFP 抵扣规则](https://www.volcengine.com/docs/82379/2516283)](https://www.volcengine.com/docs/82379/2516283)

生产量还没定时，至少给出 25%、50%、100% 套餐利用率三种 `cost_effective/task`。正式选型按共同的预计月任务量比较，不按这次一两百次测试产生的边际现金支出比较。FOCUS 同样要求预付或订阅费用按使用量和时间摊销，而不是把被套餐覆盖的使用记成永久零成本。

## 思考模型的特殊规则

1. 同一模型的关闭思考、低思考、高思考、Max 思考分别建立 `condition_id`。它们的质量、Token、成本和时延都可能不同，不能合并平均。

2. 同时记录请求档和实际档。有的平台会把 `low/medium` 映射到同一个后端档位；只记请求参数会制造不存在的条件差异。

3. 时延至少拆成：

| 指标                 | 定义                | 限流等待怎么处理               |
| ------------------ | ----------------- | ---------------------- |
| `TTFT`             | 请求发出到首个 Token／数据块 | 不含请求发出前等待；供应商内部排队自然包含  |
| `TTFA`             | 请求发出到首个正式答案 Token | 思考模型必须单列               |
| `attempt_e2e`      | 本次请求发出到响应完成       | 包含该请求在供应商内部的全部处理       |
| `logical_task_e2e` | 任务可执行到最终结果完成      | 包含客户端限流、429 等待、退避和所有重试 |

Artificial Analysis 也明确区分首个 Token 和首个答案 Token；对公开思维链的模型，TTFT 可能只是首个思考 Token，并不代表用户已经看到答案。[[时延定义](https://artificialanalysis.ai/methodology/performance-benchmarking)](https://artificialanalysis.ai/methodology/performance-benchmarking)

4. 非流式请求拿不到真实 TTFT。这种情况下只能记录完整响应时间，不能把“收到整包响应的时间”冒充首 Token 时间。

5. 空答案也可能很贵。推理模型可能先消耗大量隐藏思考 Token，随后因输出上限结束，正式答案仍为空。OpenAI 官方文档明确提示这种情况可能发生并产生费用。因此成本必须看 usage，不能看可见正文长度。[[OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning)](https://developers.openai.com/api/docs/guides/reasoning)

## 失败和空输出处理规则

| 情况                                         | 成本账                                       | 主质量账                          | 条件语义分                | 重试              | 失败率                       |
| ------------------------------------------ | ----------------------------------------- | ----------------------------- | -------------------- | --------------- | ------------------------- |
| HTTP 成功、格式合法                               | 计全部成本                                     | 正常评分                          | 正常评分                 | 否               | 否                         |
| HTTP 200，但空正文、非法 JSON、Schema 失败、拒答、只有思考无答案 | 计全部成本                                     | 按失败／零分计入；抽取任务可视为空预测，并另记格式失败   | `N/A`，不能进入“有效输出语义均分” | 否               | 计模型输出失败                   |
| 因长度触顶、正文被截断                                | 计全部成本                                     | 失败或按预注册截断规则评分                 | 通常 `N/A`             | 否               | 单列截断率                     |
| 连接错误、超时、408、429、5xx                        | 每个 attempt 都记成本；没 usage 时记 `pending`，不填 0 | 若预注册重试成功，只评分最终结果；最终仍失败则主质量按零分 | 最终失败时 `N/A`          | 只按预注册规则、同一请求体重试 | 计 attempt 失败率和最终 task 失败率 |
| 明确属于调用器错误，如错误密钥、请求体生成错误                    | 实际现金支出进入“实验浪费账”                           | 该观察作废，不能归罪模型                  | 不评分                  | 修复后按配对规则补跑      | 不进入模型失败率，但必须公开数量          |

“记成本但不记质量分”只适用于某次失败 attempt 后又成功重试：它不是一道新题，所以不单独给语义分，但成本、等待和 attempt 失败都保留。

如果一个逻辑任务最终仍失败，就不能从质量表中删掉。主运营质量按失败处理，另外再报告“仅格式有效输出上的条件语义分”。这样既不会把平台故障说成语义错误，也不会让爱失败的平台通过删分母获得虚高 F1。

所有费用不明的失败调用都写 `billing_reconcile_status=pending`。等控制台、AFP 余额或账单核对后才能改成实际金额；在此之前该条件不得参加“最低成本”排名。

建议冻结这几个失败指标：

[
\text{attempt failure rate}
===========================

\frac{\text{失败真实请求数}}{\text{全部真实请求数}}
]

[
\text{task failure rate}
========================

\frac{\text{最终没有有效输出的任务数}}{\text{预定任务数}}
]

[
\text{retry rate}
=================

\frac{\text{发生过重试的任务数}}{\text{预定任务数}}
]

另列 `empty_output_rate`、`format_pass_rate`、`truncation_rate`。

## 可直接抄进执行票

> **费用、Token、时延与失败记账锁**
>
> 1. 一行只代表一次真实 API 请求；一道题使用 `task_id`，每次物理请求使用独立 `attempt_id`。
> 2. 正式调用前关闭 SDK 隐式自动重试；只允许调用器按预注册失败类型显式重试，并为重试新建一行。
> 3. 每次请求必须保存原始 usage、响应头、供应商 request/trace ID、请求与响应 SHA；缺失字段写 `null`，不得补零。
> 4. 输入、缓存读取、缓存写入、总输出、推理 Token 分账保存；推理 Token 已包含在总输出时不得重复相加。
> 5. 每个条件冻结平台、endpoint、模型、Prompt、思考档、最大输出、缓存策略、服务档、SDK 版本和价格快照。任一项变化即为新条件。
> 6. 同模型不同思考档分别评分和计费；同时记录请求思考档和平台实际思考档。
> 7. 时延同时记录 TTFT、TTFA、单次请求完整时延和逻辑任务完整时延；限流、退避和重试等待进入逻辑任务时延，并另行分账。
> 8. 所有真实 attempts 的成本均进入总成本，包括失败请求和重试；费用未知记 `pending`，不得视为免费。
> 9. 套餐调用同时保存实付成本、按量参考成本、套餐摊销成本和套餐积分消耗；跨平台排名不得使用套餐边际零成本。
> 10. HTTP 200 但空输出、非法结构、截断、拒答或只有思考无正式答案，均为最终输出失败，不允许静默删除或自动重试。
> 11. 主成本指标为“全部 attempts 总成本 ÷ 预定任务数”；另报“全部成本 ÷ 有效输出数”。
> 12. 选型使用 `cost@quality`：只有通过预注册质量、Recall、格式、假事实、失败率和时延门的条件，才按任务成本排序。
> 13. 官方网格开跑前，每个 API 家族至少做一次非评分记账烟测；只要 usage、重试次数、request ID、时延或价格映射有一项不能回验，立即停跑，不进入正式题。

来源：ChatGPT
