# 结论

先不要重训 C2。

你们的结果很像一个适合优先试 runtime constrained decoding 的案例：C2 已经会抽事实，也会绑定证据，主要损失集中在 24 条里的 6 条格式失败。此时改权重会同时扰动事实判断和格式能力，而推理期约束是可撤销、可做逐样本对照的。

但要把目标写成：

> 用最小约束把 18/24 提升到 24/24，同时验证事实集合、Status 和 evidence 绑定没有变化。

而不是：

> Schema Valid 达到 100% 就算成功。

我最推荐的零训练路线是：

1. 保留当前 C2 checkpoint、prompt 和解码设置。
2. 在同一个推理引擎里比较自由解码、通用 JSON grammar、最小 C2 JSON Schema。
3. 优先用 XGrammar 接 Hugging Face，或在现有 vLLM/SGLang 内启用 XGrammar。
4. Schema 只写字段、类型、容器和必要枚举，不写事实数量、`minItems`、`uniqueItems`、内容正则等语义性条件。
5. 把“事实集合是否逐样本不变”设为主要安全指标。

## 1. 这些术语分别指什么

| 方法                        | 工作方式                                           | 通常能保证                                                   | 通常不能保证                           |
| --------------------------- | -------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------- |
| Structured generation       | 结构化生成的总称                                   | 取决于内部约束方式                                           | 没有统一保证                           |
| JSON grammar                | 维护 JSON 语法状态，屏蔽当前不合法 token           | 括号、引号、逗号、JSON 类型语法、合法结束位置                | 必需 key、字段类型合同、事实正确性     |
| JSON Schema decoding        | 把 Schema 编译成 grammar、自动机或增量解析器       | 支持子集内的 required、类型、容器、enum、const、额外字段限制 | 字段内容是否符合小说原文               |
| CFG decoding                | 用上下文无关文法和解析栈处理嵌套结构               | 任意深度的递归括号、嵌套对象、复杂语法                       | 事实真伪、完整召回                     |
| Finite-state decoding       | 用 DFA/NFA/FSM 表示合法前缀                        | 正则语言、固定格式、枚举，速度通常较好                       | 无界递归嵌套，除非限制深度             |
| Parser-guided decoding      | 每生成一个 token，就让增量解析器检查；不合法则拒绝 | 可覆盖语法，还能接入 SQL schema、候选 ID 等领域规则          | 未编码进解析器的语义                   |
| Semantic/domain constraints | 把候选实体、有效 ID、类型系统等加入约束            | ID 必须存在、字段间某些静态关系                              | “存在的 ID 是否选对”、文本事实是否真实 |

PICARD 就是典型的增量 parser-guided decoding：每一步拒绝无法继续构成合法 SQL 的 token。[PICARD，EMNLP 2021](https://aclanthology.org/2021.emnlp-main.779/)

有个容易混淆的地方：JSON Schema 最终经常也会被编译成 CFG、FSM 或增量解析程序。因此，“grammar vs JSON Schema”不是天然不同的解码算法。为了让你们的三组实验有可解释性，应这样定义：

- `C2 + grammar`：只约束通用 JSON 语法；
- `C2 + JSON Schema`：约束完整的 C2 字段合同。

如果 grammar 直接写成完整 C2 文法，它和 JSON Schema 组约束的语言几乎相同，实验就变成了“两个后端实现对比”，无法回答“只修语法还是修完整 Schema”。

## 2. 约束是否会改变事实 precision/recall

会，但不是必然会。

模型产生原始 logits 后，约束处理器会把不合法 token 的 logit 设为负无穷，再对剩余 token 重新归一化。也就是：

[
q(v\mid h)=
\begin{cases}
\frac{p(v\mid h)}{\sum_{u\in A(h)}p(u\mid h)},& v\in A(h)\
0,&v\notin A(h)
\end{cases}
]

所以：

- 模型原始 logits 没被改写；
- 实际用于采样的 token probability 被改变了；
- 存在搜索偏差；
- 一旦输出路径发生分叉，后续所有 logits 都可能变化；
- 温度采样时，即使自由解码本来可能抽到合法 token，重新归一化也可能抽到另一个合法 token；
- 相同 seed 不再意味着逐 token 可比。

在贪心解码下，如果自由解码的最高概率 token 始终合法，一个“最小干预、token 对齐正确”的约束器应保持输出不变，直到第一次自由 argmax 不合法。DOMINO 把这一性质称为 minimal invasiveness。

实现质量很关键。DOMINO 发现，朴素约束因词表 token 与 grammar 终结符不对齐，可把 Mistral-7B 的 GSM8K 准确率从 41.5% 降到 30.8%；token 对齐的实现得到 41.8%。[DOMINO，ICML 2024](https://proceedings.mlr.press/v235/beurer-kellner24a.html)

局部屏蔽也不等于从“原模型在所有合法完整序列上的条件分布”中采样。Grammar-Aligned Decoding 指出，常见逐 token masking 会扭曲合法序列之间的概率比例。[Grammar-Aligned Decoding，NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/2bdc2267c3d7d01523e2e17ac0a754f3-Abstract-Conference.html)

对 C2 来说，风险主要出现在：

- 模型想漏掉某个 required key，Schema 迫使它填值；
- 模型想输出字符串，但 Schema 只允许数组，于是它重新生成内容；
- 模型想提前停止，但 grammar 迫使它继续；
- 固定字段顺序和训练时常见顺序不同；
- Schema 强制 `status` 从 enum 中选一个，导致“合法但语义错”。

因此，不能声称 constrained decoding 只改变标点、绝不影响内容。可以做到的是，把干预面收窄，并用配对实验验证内容没有被扰动。

## 3. 与你们最接近的研究和实现

| 研究或实现                                                   | 和 C2 的关系                                 | 主要结果或警示                                               |
| ------------------------------------------------------------ | -------------------------------------------- | ------------------------------------------------------------ |
| [PICARD，EMNLP 2021](https://aclanthology.org/2021.emnlp-main.779/) | 增量解析器拒绝非法 token                     | 不重训即可提升 text-to-SQL 的可执行性和准确率                |
| [Constrained Language Models Yield Few-Shot Semantic Parsers，EMNLP 2021](https://aclanthology.org/2021.emnlp-main.608/) | 小样本结构抽取                               | 受控子语言和约束可提升语义解析                               |
| [Synchromesh，ICLR 2022](https://openreview.net/forum?id=KmtVD97J43e) | 无需重训的 parser/completion-engine decoding | 可同时编码语法和部分领域约束                                 |
| [Grammar-Constrained Decoding，EMNLP 2023](https://aclanthology.org/2023.emnlp-main.674/) | 信息抽取、解析、小模型                       | 约束后的 LLaMA 在抽取和 constituency parsing 上，语法与 F1 都明显提高 |
| [LMQL，PLDI 2023](https://dl.acm.org/doi/10.1145/3591300)    | 动态约束、类型、长度、停止条件               | 约束能力强，但对固定 JSON 抽取稍显重                         |
| [Outlines](https://arxiv.org/abs/2307.09702)                 | JSON Schema/正则转 FSM                       | 模型无关、开销较低，适合本地类型化输出                       |
| [DOMINO，ICML 2024](https://proceedings.mlr.press/v235/beurer-kellner24a.html) | 直接研究约束是否伤准确率                     | 朴素 token masking 会显著伤语义；token 对齐可消除大部分损失  |
| [Let Me Speak Freely，EMNLP Industry 2024](https://aclanthology.org/2024.emnlp-industry.91/) | 比较自然语言、JSON mode、JSON Schema         | 严格格式在部分推理任务上降低准确率；影响随任务和 prompt 变化 |
| [Grammar-Aligned Decoding，NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/2bdc2267c3d7d01523e2e17ac0a754f3-Abstract-Conference.html) | 分析搜索分布偏差                             | 逐步屏蔽并不保持原模型对合法完整序列的概率比例               |
| [XGrammar，MLSys 2025](https://arxiv.org/abs/2411.15100)     | Qwen/HF/vLLM/SGLang 可用的高速 CFG           | byte-level PDA、预编译 mask，重点处理 token 与 grammar 对齐问题 |
| [JSONSchemaBench，2025 预印本](https://arxiv.org/html/2501.10868v3) | 10,000 个真实 Schema、多个引擎               | 引擎支持度、过约束和欠约束差异很大；该实验中约束没有降低三项任务质量 |
| [ACL Industry 2025 逻辑解析研究](https://aclanthology.org/2025.acl-industry.34/) | 小模型和结构化逻辑输出                       | grammar 同时改善语法与语义，部分替代示例提示                 |
| [The Hidden Cost of Structure，RANLP 2025](https://aclanthology.org/2025.ranlp-1.124/) | 11 个模型的结构约束比较                      | base model 常受益，instruction-tuned model 的生成任务更容易下降 |
| [The Constraint Tax，2026 预印本](https://arxiv.org/abs/2605.26128) | 小型 Qwen、Schema Valid 与语义分离           | 部分任务中 Valid 接近 100%，答案准确率却明显下降；证据较新，尚不宜单独作为定论 |

现有结果并不支持“constrained decoding 一定提高语义”，也不支持“它通常一定会伤语义”。任务、prompt、模型对格式的熟悉程度，以及约束器的 token 对齐方式都会改变结果。

你们的 C2 已在 SFT 中见过目标结构，distribution mismatch 很可能比“让未见过 JSON 的模型突然输出 JSON”更小，但我没有找到与“Qwen3-4B、中文小说事实抽取、同一格式 SFT”完全对应的公开实验。

## 4. JSON grammar 能保证和不能保证什么

| 问题                  | 通用 JSON grammar        | JSON Schema                                      | 更强的输入相关约束       |
| --------------------- | ------------------------ | ------------------------------------------------ | ------------------------ |
| 括号、逗号、引号正确  | 能                       | 能                                               | 能                       |
| JSON 可以解析         | 能，未触顶时             | 能，未触顶时                                     | 能                       |
| 必需 key 不遗漏       | 不能                     | 能                                               | 能                       |
| key 的类型正确        | 不能                     | 能                                               | 能                       |
| 数组/对象容器正确     | 只能保证它们各自语法合法 | 能                                               | 能                       |
| `status` 属于允许枚举 | 不能                     | 能                                               | 能                       |
| `status` 语义正确     | 不能                     | 不能                                             | 通常不能                 |
| evidence ID 存在      | 不能                     | 可用逐文档 enum 表示                             | 能                       |
| evidence ID 选对      | 不能                     | 不能                                             | 除非另有可靠语义判定器   |
| 重复事实              | 不能                     | `uniqueItems` 只能挡完全相同对象，且要看后端支持 | 语义重复仍需去重判定     |
| 事实数组数量          | 不能                     | 可限制 min/max，但不知道金标准数量               | 只有外部已知数量时才可靠 |
| 是否应继续抽事实      | 不能                     | 不能                                             | 通常不能                 |
| 完成 JSON 后不再继续  | 能                       | 能                                               | 能                       |
| max token 前保证完成  | 不能                     | 不能                                             | 不能                     |
| 事实符合小说原文      | 不能                     | 不能                                             | 仍需模型或验证器         |

OpenAI 也明确区分 JSON mode 和 Structured Outputs：前者只保证有效 JSON，后者匹配所支持的 JSON Schema；Structured Outputs 仍可能出现字段内容错误、幻觉、拒答或长度截断。[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

数组数量尤其危险：

- `maxItems` 可能截断召回；
- `minItems` 可能逼模型编造事实；
- 固定数量会把“还应不应该继续”从事实判断改成格式要求；
- `uniqueItems` 只能处理完全相同的 JSON 对象，挡不住同一事实的两种措辞。

## 5. 小模型该优先 runtime constraint 还是格式 SFT

没有足够直接研究可以证明“小模型通常使用 constrained decoding 一定比格式 SFT 更安全”。两者改变的东西不同：

- 格式 SFT 改变模型权重，可能影响所有事实决策；
- runtime constraint 不改权重，但会改变当前生成路径；
- runtime constraint 容易关闭、比较和逐条定位；
- 24 条训练数据上的继续 SFT，格式收益和语义漂移更难分开。

因此，在你们这个具体状态下，runtime constraint 是更安全的下一项诊断实验，而不是被证明普遍更安全的方法。

优先级可以这样定：

- 只有闭括号、引号、尾逗号问题：固定规则的非模型后处理可能最少干预，因为完全不改变模型已生成内容。
- 会漏 key、类型错、容器错：试最小 JSON Schema。
- 模型经常填空数组、错误默认值或被迫编造 required 字段：退回更窄的 grammar，检查 prompt 和字段合同。
- 更大锁定集上仍出现显著语义损失，或部署环境不能承受约束开销：再评估格式 SFT。
- 不要因为一次 constrained decoding 失败就直接推导出必须重训。

## 6. 本地方案怎么选

| 方案                      | 适合场景                          | 成熟经验和限制                                               |
| ------------------------- | --------------------------------- | ------------------------------------------------------------ |
| XGrammar                  | Qwen + HF、vLLM、SGLang；JSON/CFG | 我对本实验的首选。支持 JSON Schema、JSON、EBNF，并提供 HF logits processor；官方文档也提醒 prompt 应描述预期输出，让模型分布与约束对齐。[XGrammar](https://github.com/mlc-ai/xgrammar) |
| vLLM                      | GPU 服务和批处理                  | 当前接口支持 `json`、`regex`、`choice`、`grammar` 等 structured outputs，并可选 XGrammar/Guidance 后端。[vLLM structured outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/) |
| SGLang                    | 高吞吐 Qwen 服务                  | 支持 JSON Schema、regex、EBNF；XGrammar 是主要后端，也可用 Outlines/llguidance。[SGLang structured outputs](https://docs.sglang.ai/advanced_features/structured_outputs.html) |
| Hugging Face Transformers | 最严格的单 checkpoint 控制实验    | 用 `LogitsProcessor` 或 `prefix_allowed_tokens_fn`；接 XGrammar/Outlines 时可保持同一 `model.generate` 路径。[HF generation](https://huggingface.co/docs/transformers/main_classes/text_generation) |
| Outlines                  | Pydantic/JSON Schema、HF、MLX     | 使用方便，通常把类型或 Schema 编译为约束；适合快速实验。[Outlines](https://github.com/dottxt-ai/outlines) |
| Guidance / llguidance     | JSON 与复杂程序式约束             | 表达能力强；历史实现里的 token healing、空白模板等细节可能改变输出分布。[Guidance](https://github.com/guidance-ai/guidance)、[llguidance](https://github.com/guidance-ai/llguidance) |
| llama.cpp grammar         | GGUF、CPU、Apple 环境             | 支持 GBNF 和 JSON Schema。文档明确说 grammar 不会自动注入 prompt，模型仍应被告知结构。[llama.cpp grammar](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) |
| MLX + Outlines            | Apple Silicon                     | 有直接 MLX-LM 接入，可做 JSON Schema、regex 和 CFG；目前 constrained batching 有限制。[Outlines MLX](https://dottxt-ai.github.io/outlines/latest/features/models/mlxlm/) |
| LMQL                      | 动态多阶段约束、控制流            | 很强，但固定 C2 JSON 抽取没有必要先引入完整查询语言。[LMQL constraints](https://lmql.ai/docs/language/constraints.html) |

Qwen 官方部署文档也给出了 vLLM 和 SGLang 的 structured output 用法，并建议在提示中清楚描述期望结构。[Qwen vLLM](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)、[Qwen SGLang](https://qwen.readthedocs.io/en/latest/deployment/sglang.html)

托管服务的经验也一致：它们保证的是所支持 Schema 子集，不是内容正确性。

- Anthropic 的 `strict: true` tool use 会对参数做 grammar-constrained sampling；普通非 strict tool use 没有相同保证。[Anthropic strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- Google 的官方文档明确警告，structured output 用在 tuned Gemini models 上可能降低模型质量，Schema 过于复杂或字段顺序冲突也可能出错。[Google controlled generation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output)
- OpenAI 支持 JSON Schema 子集，并要求正确处理 refusal 和 `max_tokens` 截断，不能把每个返回都默认成完整结构。[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

## 7. 推荐的零训练最小实验

### 三个实验臂

| 实验臂                      | 约束                                                         |
| --------------------------- | ------------------------------------------------------------ |
| A：C2 原始自由解码          | 当前设置原样保留                                             |
| B：C2 + JSON grammar        | 只保证任意合法 JSON；不固定 key、类型、枚举、数组数量        |
| C：C2 + minimal JSON Schema | required key、字段类型、对象/数组容器、`additionalProperties:false`；仅对真正封闭的 `status` 使用 enum |

C 组暂时不要加入：

- `minItems` / `maxItems`；
- 固定事实数量；
- `uniqueItems`；
- 非空字符串约束；
- 事实文本正则；
- evidence 数量限制；
- 跨字段语义规则；
- 为每篇文章动态建立 evidence-ID enum。

C2 已经是不存在 ID 为 0，因此把 ID enum 放进主实验只会扩大干预，不能解决当前最大问题。可以作为后续 D 组单独研究。

### 必须相同的控制变量

- checkpoint、adapter、tokenizer；
- chat template、system prompt、字段顺序；
- DEV24 输入和输入顺序；
- temperature、top-p、top-k、seed；
- repetition penalty；
- `max_new_tokens`；
- EOS、stop 条件；
- 精度、batch size、硬件；
- 同一个推理引擎和模型加载实例；
- 不允许失败后重试；
- 不允许自动 repair 后再算 Schema Valid。

不要用 HF 跑自由组、vLLM 跑约束组。后端、浮点和 batching 的变化本身就可能改变输出。

建议按每条文本交错运行 A/B/C，并随机化三臂次序，以降低温度、缓存和批处理顺序影响。Schema 编译一次，另行记录首次编译时间。

如果当前设置是随机采样，相同 seed 只能控制随机数源，不能保证配对 token 一致，因为 mask 改变了概率区间。若当前是贪心解码，逐 token 干预分析会更清楚。

## 8. 预注册指标

| 指标                    | 建议定义                                                     |
| ----------------------- | ------------------------------------------------------------ |
| Semantic Fact F1        | 对规范化后的事实多重集合算 micro precision/recall/F1；无效 JSON 也使用当前容错抽取器参与语义评分，不能直接丢弃 |
| Schema Valid            | 原始 completion 直接通过独立 JSON parser 和独立 JSON Schema validator；不得 repair |
| Status                  | 沿用当前 exact correctness，同时报告逐样本变化               |
| Evidence ID correctness | 分开报告 ID existence，以及“语义匹配事实的证据绑定正确率”，保留分子/分母 |
| Repetition              | 完全重复事实率、规范化后的语义重复率、token loop             |
| Termination             | 正常 EOS/grammar accept、触顶、截断、非法提前结束            |
| Output tokens           | 用同一 tokenizer 数序列化输出 token；另记实际 sampling/forward steps |
| Latency                 | 冷启动 Schema 编译、warm end-to-end p50/p95、TTFT、每 token 时间或吞吐 |

强烈建议再增加三个诊断指标：

- `Wrong-but-valid rate`：Schema 合法，但事实、Status 或 evidence 至少一项错误；
- 首个自由解码与约束解码分叉的 token 位置；
- 18 个原本 Schema 合法样本中，规范化事实集合完全相同的比例。

其中第三项最能回答“是不是只修格式”。如果原本合法的 18 条也发生大量内容变化，约束器就不是最小干预。

还应记录每一步“自由 argmax 是否被约束判为非法”。这能把语义下降直接定位到 grammar 干预，而不是笼统归因于模型波动。

## 9. 什么结果足以说明不必为了 Schema 重训

### 强结论

同时达到：

- C 组 Schema Valid = 24/24；
- 18 个原本合法样本的规范化事实集合全部不变；
- 6 个原本非法样本变为合法后，事实集合没有新增 FP、没有丢失 TP；
- Semantic Fact F1 不低于 89.36%；
- Status 不下降；
- evidence 绑定保持 42/42，或新增命中事实的绑定同样全部正确；
- 没有新增重复、触顶或异常停止；
- 延迟在部署预算内。

这时可以较有力地说：

> 在 DEV24 上，C2 的主要问题是序列化失败，runtime JSON Schema 已把格式修复，没有观察到语义损失，因此没有证据支持为了 Schema 继续训练。

### 工程上的非劣标准

如果不要求绝对逐事实不变，可预注册：

- Schema = 24/24；
- Semantic F1 下降不超过 2 个百分点；
- 原本合法的 18 条中至多 1 条发生事实决策变化；
- Status 和 evidence 没有新增错误；
- `Wrong-but-valid rate` 不升高。

不过，DEV24 很小，一个事实就可能造成接近 1–2 个百分点的变化。仅仅说“F1 差异不显著”说服力不足，逐事实 paired diff 更重要。

24/24 也不能证明真实 Schema 成功率已经接近 100%。若把每条视为独立 Bernoulli 试验，24/24 的双侧 95% 置信区间下界大约只有 86%。它足以决定下一步方向，但上生产前仍应在更大的锁定集复验。

## 10. 哪些“100% Schema”会把内容错误藏起来

这些输出都可以是完美合法的 JSON：

```json
{"status":"ok","facts":[]}
```

Schema 100%，但可能把全部事实漏掉。

```json
{"status":"not_found","facts":[]}
```

`status` 在 enum 中，却选错。

```json
{
  "status":"ok",
  "facts":[
    {"fact":"张三离开客栈","evidence_ids":["U17"]}
  ]
}
```

`U17` 确实存在，却可能对应另一段文本。

其他典型假象还有：

- 同一事实换两种说法重复两次；
- 主客体交换，但字段类型都正确；
- required key 被迫填成空字符串、`null` 或看似合理的幻觉；
- 模型过早关闭 `facts` 数组，语法上正常结束；
- `maxItems` 把多余的真实事实截掉；
- `minItems` 逼模型补一条假事实；
- `additionalProperties:false` 让本来正确但无法归类的信息被塞入错误字段；
- 重试直到合法，最终只保留较短、较保守甚至空数组的答案；
- 只在 Schema-valid 子集上算语义 F1，把非法但语义正确的自由输出排除。

因此报告中要并列放：

- Schema Valid；
- Semantic Fact F1；
- Wrong-but-valid rate；
- 空事实数组率；
- 平均及分布上的事实数量；
- Status/evidence 正确率；
- 原始输出，不只保存 validator 结果。

最终决策可以浓缩成一句：

> 对 C2，先用同引擎、最小 JSON Schema、无重试的 constrained decoding 做逐样本配对；只有当 Schema 达到 24/24 且事实集合、Status、evidence 均不退化时，才把它认定为“只修格式”。如果出现合法空数组、错误 enum、错误 evidence 或召回下降，那只是把错误装进了合法 JSON，并没有解决任务。

来源：ChatGPT