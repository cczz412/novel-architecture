✅ 结论：前置信息不是越多越好。你们最合理的起始假设应当是：

> **CTX-S 常驻，CTX-M 按需检索，CTX-L 暂不常驻。**

也就是：正文前固定放最小合同、短规则和纯结构 metadata；人物背景、previous state 只有在当前窗口确实存在消歧需求时才加入；examples 不默认塞进去。

这只是实验先验，不是生产结论。Dense Qwen、Ling Tiny、Doubao Mini、Doubao Lite 必须分别选自己的最小充分上下文，不能把排名互相继承。

当前最有希望的 Prompt 骨架是：

```text
静态最小合同
→ 短规则／纯结构 metadata
→ 有条件选中的 confirmed background / previous state
→ BEFORE / TARGET / AFTER 原文
→ 极短 checklist
→ 输出触发语／schema 骨架
```

其中“正文后的短 checklist”仍是实验项。研究证明重复提醒有时有效，也证明某些小模型会被重复内容带偏。

------

## A｜相关度最高的研究与工业实现

| 研究／实现                                                   | 对你们最有用的发现                                           | 不能怎样外推                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| [Lost in the Middle，TACL 2024](https://aclanthology.org/2024.tacl-1.9/) | 只移动同一条关键信息的位置，就会明显改变结果；开头和结尾通常优于中间。其多文档 QA 正文约 1K～3K，已经进入你们关心的区间。 | 不能认定所有模型都呈同样的 U 形；部分小模型更接近单纯“只顾后面”。 |
| [Same Task, More Tokens，ACL 2024](https://aclanthology.org/2024.acl-long.818/) | 固定题目，只改变 padding 的长度、类型和位置，模型在远低于标称上限时已经退化。 | 是推理 QA，不是小说抽取。                                    |
| [Context Length Alone Hurts，EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.1264/) | 证据保持完整、甚至把干扰 token attention-mask 后，长度本身仍能降低表现；大量下降发生在约 7K token 以内。 | 不能直接套用论文中的下降幅度。                               |
| [Irrelevant Context，ICML 2023](https://proceedings.mlr.press/v202/shi23a.html) | 无关信息会分散模型；提示“忽略无关信息”只能缓解一部分。       | 研究对象主要是数学题。                                       |
| [How Easily do Irrelevant Inputs Skew Responses，COLM 2024](https://arxiv.org/abs/2404.03302) | 与问题“看起来很像”但实际无用的 hard distractor，比完全无关文本更危险；干扰数量越多，错误越多。 | 不能把 embedding 相似度当作上下文价值。                      |
| [RULER，COLM 2024](https://arxiv.org/abs/2404.06654)         | 17 个长上下文模型几乎都随长度、任务复杂度增加而退化；标称 32K+ 的模型，只有约一半能在 32K 保持满意水平。 | MoE、Dense、激活参数量都不能单独预测有效窗口。               |
| [NoLiMa，ICML 2025](https://proceedings.mlr.press/v267/modarressi25a.html) | 当 query 与证据没有明显词面重合时，很多模型从 1K～8K 已明显下降；小模型下降更快。 | 是英文合成关联检索，不是事件抽取。                           |
| [LongBench，ACL 2024](https://aclanthology.org/2024.acl-long.172/) | 少数直接包含中文长文本的基准；中文输入平均约 1.3 万字符。检索压缩能帮助弱长上下文模型，但不能完全补偿能力差距。 | 不是严格的长度因果实验。                                     |
| [Demos Position，EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1503/) | 在 Qwen、Llama、Mistral、Cohere 中，仅移动相同 examples 的位置就能改变大量输出；整体上 examples 放靠前更稳定，小模型更敏感。 | 不能把 examples 的结论自动套到规则或背景。                   |
| [Self-Consistency Falls Short，TACL 2026](https://aclanthology.org/2026.tacl-1.15/) | 在约 5K～10K 的任务中，前后重复 query 只带来有限且不稳定的改善；Qwen2.5-7B 也存在明显位置偏差。 | 不支持“尾部 checklist 必然有效”。                            |
| [We Are What We Repeatedly Do，EACL 2026](https://aclanthology.org/2026.findings-eacl.254/) | 长上下文中重新提醒规则有时能恢复遵守率，但某些重复方式会让较小模型更差。 | 研究是多轮对话，不能直接当单轮 Prompt 答案。                 |
| [Sufficient Context，ICLR 2025](https://research.google/pubs/sufficient-context-a-new-lens-on-retrieval-augmented-generation-systems/) | “相关”不等于“足够”；加入不充分上下文可能提高模型信心，却增加错误生成。 | 它判断“够不够回答”，不能直接给出最小 token 数。              |
| [LongLLMLingua，ACL 2024](https://aclanthology.org/2024.acl-long.91/)／[RECOMP，ICLR 2024](https://arxiv.org/abs/2310.04408) | 提高有效信息密度、删除无益检索内容，可能同时改善准确率、成本和延迟；RECOMP 甚至允许“没有帮助就返回空上下文”。 | 你们不能压缩或改写负责取证的正文，只能压缩背景和规则。       |
| [ContextCite，NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/adbea136219b64db96a9941e4249a857-Abstract-Conference.html) | 可以通过随机保留／删除上下文块，估计每块对结果的影响，并用于 pruning。 | attribution 只能找候选，最终删除仍要用真实抽取分数确认。     |
| [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) | 其内部实验中，embedding＋BM25＋reranker 比只做向量相似度明显减少检索失败。 | 是厂商自有数据和模型结果，只能借方法，不能借数值。           |

### B｜哪些证据证明“更多可能更差”

“更多信息变差”至少要拆成四种原因：

1. **长度本身**：正文、证据完全不变，只增加 padding 也下降。
2. **一般干扰**：加入完全无关内容，模型被分散。
3. **语义吸引／冲突**：加入看起来高度相关、实际无用或错误的背景，造成锚定。
4. **位置改变**：新内容把规则、TARGET 或关键证据推到模型不擅长的位置。

因此，只做“短 Prompt vs 长 Prompt”无法解释原因；只做一个 distractor 臂也不够干净。

------

## C｜CTX-0／S／M／L 分层实验

下面的 token 是“正文以外的可选上下文累计上限”，不是要求填满。正文必须逐字相同，不得为了满足预算而截断。

| 实验臂 | 新增内容                                                     | 可选上下文累计起始上限     |
| ------ | ------------------------------------------------------------ | -------------------------- |
| CTX-0  | 一句任务目的、负责区标记、字段名、最小证据合同；无背景、无 previous state、无 examples | ≤256 token                 |
| CTX-S  | CTX-0＋不超过 8 条原子短规则＋纯结构 metadata                | ≤640 token                 |
| CTX-M  | CTX-S＋最多约 6 条 confirmed background 原子卡               | ≤1,536 token               |
| CTX-L  | CTX-M＋query-focused previous state＋1 个正例／1 个 minimal pair | ≤3,072 token，且总输入≤10K |

每个新增项都记录：

```text
ctx_item_id
type
source_cutoff
truth_status
retrieval_reason
token_count
position
eligible_as_evidence=false
```

🔥 `CTX-0/S/M/L` 是产品层级筛选，不是纯长度实验。因为每一级同时改变了内容类型和 token 数。

某一级出现变化后，需要拆包：

- S 有收益：再比 `rule-only` 与 `metadata-only`；
- L 有变化：再比 `state-only` 与 `examples-only`；
- M 的背景按实体、事件、时间、人物关系分别删除复验。

建议另外做总输入约 `1K/2K/4K/6K/8K/10K` 的长度曲线，正文和有效背景不变，只改变受控 padding。

------

## D｜Placement 实验

为了不把“移动”和“新增 checklist”混在一起，定义：

```text
FullRules = CoreRules + ShortChecklist
```

| 臂   | 顺序                                                         | 测什么                                                    |
| ---- | ------------------------------------------------------------ | --------------------------------------------------------- |
| P1   | FullRules → Background → Body → OutputTrigger                | 全规则靠前                                                |
| P2   | Background → FullRules → Body → OutputTrigger                | 背景和规则换位                                            |
| P3   | CoreRules → Background → Body → ShortChecklist → OutputTrigger | 把同一组 checklist 从前面移动到正文后，不增加语义和 token |

再加一对诊断臂，专门测“重复”：

```text
P4-repeat：
FullRules → Background → Body → ShortChecklist → OutputTrigger

P4-tail-control：
FullRules → Background → Body → 等 token 中性尾注 → OutputTrigger
```

`P4-repeat - P4-tail-control` 才是尾部重复提醒的净效果。

短 checklist 建议只保留四个硬约束：

```text
只抽取 TARGET 负责区。
背景只用于消歧，不能单独作为事实或证据。
evidence 必须来自可见正文／合法 evidence ID。
不确定时不猜，严格按 schema 输出。
```

正文内部仍保持 `BEFORE → TARGET → AFTER` 的自然顺序。不要为了把 TARGET 放到结尾而破坏叙事时间，只需清楚标记边界，并保证正文之后不再出现人物背景、剧情 examples 或 previous state。

------

## E｜等 token distractor 控制

本地 Qwen 建议完整跑五臂：

| 臂   | 内容                                                         |
| ---- | ------------------------------------------------------------ |
| E-Ø  | 不增加背景                                                   |
| E-R  | 等预算的 relevant＋confirmed 背景                            |
| E-N  | 跨故事中性合成背景，体裁、句长、标点和 token 匹配            |
| E-H  | 同故事、时间合法、看起来相关，但人工确认对本窗无帮助的 hard distractor |
| E-X  | 从 E-R 中机械改错一个实体、状态或时间；只用于合成实验        |

主要解释：

- `R−N`：有效背景的净价值；
- `H−N`：同域词语和人物造成的锚定；
- `X−R`：错误／冲突背景的损害；
- `N−Ø`：只能称为“中性 padding 总效应”，不能完全等同纯长度。

本地模型若能控制 attention mask，可增加真正的 masked-padding 臂。公开 API 做不到这一点，不应假装自然语言 padding 没有语义。

------

## F｜预注册指标

主指标：

- semantic micro precision / recall / F1；
- window-macro F1；
- 相对 CTX-0 的 `Δprecision`、`Δrecall`；
- speaker accuracy / F1；
- status accuracy；
- evidence exact／evidence ID 合法率。

安全指标：

- 背景中有、正文中没有，却被抽成事实的比例；
- 模型跟随背景而忽视正文的冲突错误；
- future leakage 数量；
- 背景被错误当作 evidence 的数量；
- 空事实窗口的 false positive；
- JSON/schema 合法性和复读，作为护栏单列。

成本指标：

```text
grounded TP
= 语义事实正确
+ evidence/evidence_id 真正支持该事实
```

`strict grounded TP` 再要求 status、适用时的 speaker 正确。

```text
cost per grounded TP
= 所有未缓存输入费
+ 缓存命中费
+ 输出费
+ 缓存存储分摊
+ 重试／升级 Lite 的费用
────────────────────────
grounded TP 总数
```

同时报：

- input/output token；
- cached/uncached token；
- P50/P95 latency；
- cache hit ratio；
- `每新增 1K input token 带来的额外 grounded TP`；
- `每多获得一个 grounded TP 的边际成本`。

非法输出和复读所消耗的 token 也必须计费，不能从成本中删掉。

------

## G｜怎样找“最小充分上下文”

你们要找的不是最高点，而是：

[
C^*=\arg\min_C tokens(C)
]

约束条件是：

- F1 与最佳臂相比没有低过预设容忍线；
- precision 不越线；
- speaker、背景污染不恶化；
- future leakage 为 0。

推荐流程：

1. 所有窗口跨 arm 配对，用“作品／章节”为单位做 paired cluster bootstrap。
2. 本地筛选可先用 `δF1=2 个百分点`；Doubao 生产确认可收紧到约 `1 个百分点`。precision 单独设线，不能靠 recall 抵消。
3. 找出与最佳臂“统计上不劣”的候选。
4. 在这些候选里选 median input token 最少的。
5. 用未参与选择的冻结集再确认。

DEV24 只有 24 题，适合筛方向，不足以证明生产规律。若置信区间很宽，结论应写 `UNRESOLVED`，不要按点估计硬选。

一条 context item 的价值可以这样测：

- 先做 group ablation；
- 对剩余条目做 leave-one-out；
- 本地把上下文压到不超过约 8 组后，再做 128～256 次随机排列近似 Shapley；
- Doubao 若没有 logprob，就直接比较删除前后的实际语义分数。

Attention 热力图只能帮忙定位可疑项，不能直接作为删除依据。[Attention is not Explanation](https://aclanthology.org/N19-1357/) 已经证明，注意力权重不等于可靠因果解释。

------

## H｜推荐的 context selection / pruning

小说事实抽取不适合只拿整段文字做 embedding top-k。推荐用分层筛选：

```text
时间／权限／确认状态硬过滤
→ 当前 TARGET 中的实体、别名、指代、speaker 候选
→ 当前窗口触及的事件／状态字段
→ BM25 精确词面＋embedding 语义召回
→ “是否能解决当前消歧”重排
→ 去重、时间覆盖、token 裁剪
→ 允许返回空背景
```

具体规则：

- 未来时间切面的记录在检索阶段直接不可见；
- 人物背景必须是 confirmed，并附 provenance；
- previous state 只取当前实体的“最近有效状态＋必要变化点”，不要塞完整时间线；
- 已抽事实只能取目标窗口之前的记录，避免让模型复读旧事实；
- examples 按“错误类型”选，不按剧情相似度选，避免人物和事件锚定；
- embedding 负责召回，不能负责最终决定；
- 背景卡保持原子化，一卡一个断言；
- 背景、状态和 examples 全部标记为 `context_only`；
- 负责区正文不做摘要、不改写、不做有损 token compression。

压缩只允许用于：

- 合并重复规则；
- 删除无用背景；
- 把长 previous state 机械转成原子状态卡；
- 对 BEFORE/AFTER 做经过独立验证的单元级裁剪。

TARGET 和其 evidence ID 映射不能压缩。

------

## I｜Prompt caching 能否降低 Mini/Lite 成本

✅ 可以，但只降低“重复计算和输入账单”，不会减少模型看到的 token，也不会消除 context dilution。

火山方舟官方文档目前支持前缀缓存和 Session 缓存；其文档列出的最低缓存长度为：

- Context API：约 1,024 token；
- Responses API 前缀缓存：约 256 token。

参见[上下文缓存原理及选型](https://docs.volcengine.com/docs/82379/1398933)和[上下文缓存说明](https://www.volcengine.com/docs/82379/1602228)。

截至 2026-08-08 的公开基础价表，在 ≤32K 文本档中：

- Mini：普通输入约 0.2 元／百万 token，缓存命中约 0.04；
- Lite：普通输入约 0.6 元／百万 token，缓存命中约 0.12。

也就是命中部分约便宜 80%。具体以[方舟当前模型价格表](https://docs.volcengine.com/docs/82379/1544106)和精调 endpoint 的实际 usage 为准。

但不能把它理解成“总输入成本下降 80%”。例如：

```text
总输入 6,000 token
静态可缓存前缀 600 token
缓存部分便宜 80%
```

满足缓存门槛时，总输入成本只下降约：

```text
600 / 6000 × 80% = 8%
```

所以：

- 静态规则、schema、固定 examples 必须放在最前面，才能成为共同前缀；
- dynamic metadata 和正文放在静态前缀之后；
- 不要为了达到缓存门槛硬塞无用规则；
- 不能因为背景已经缓存，就允许它常驻 Prompt。

### 对训练 loss 的影响

推理 prefix cache 不能直接用于普通 SFT/LoRA 训练：

- 每一步训练后 LoRA 参数都会更新，旧 KV 失效；
- 训练还需要反向传播所需的 activation；
- 重复静态前缀仍消耗训练 token、显存和序列长度。

如果训练采用 assistant-only loss：

- system/user token 通常不直接计入交叉熵；
- 但它们仍影响 assistant 输出、计算量和梯度；
- 云平台通常仍按完整训练 token 计费。

如果没有正确 mask 输入 token，重复前缀可能占据大量 loss，让训练曲线显得很好看，却不代表事实抽取变好了。要实际检查 labels/loss mask，不能靠配置名猜。

------

## J｜三层模型迁移方案

### 1. Dense Qwen 本地代理

完整跑：

- CTX-0/S/M/L；
- P1/P2/P3，加 P4 重复诊断；
- E-Ø/R/N/H/X；
- 总输入 1K/2K/4K/6K/8K/10K；
- TARGET／关键事实位于约 20%/50%/80% 的位置诊断；
- 本地 3 个 seed。

它负责筛出：

- 哪类信息有希望；
- 哪类信息稳定有害；
- 候选 token 拐点；
- 最值得交给后续模型复验的 2～3 个结论。

这些结论只写成 `QWEN_DENSE_PROXY_RESULT`。

### 2. Sparse Ling Tiny

截至 2026-08-08，第三方网关已经在 8 月 6 日上线 Ling 3.0 Tiny API，公开描述为 7.9B 总参数、约 1.3B 激活参数、256K context。[Vercel AI Gateway 公告](https://vercel.com/changelog/ling-3-0-tiny-is-now-available-on-ai-gateway)

但我目前没有在 [InclusionAI 官方 Hugging Face](https://huggingface.co/inclusionAI) 找到 Tiny 的正式可下载权重和完整模型卡。因此：

> 远程 API 可以做侦察，但还不满足你们“本地下载＋本地微调的稀疏代理”条件。

正式权重出现后只复验：

1. Qwen 选出的最小充分臂 vs CTX-0／相邻更长臂；
2. 最佳 placement vs runner-up；
3. relevant background vs 等 token hard distractor；
4. 一个 short/long 配对，测 Ling 自己的长度斜率。

token 必须用 Ling 自己的 tokenizer 重算，并锁定 checkpoint SHA、chat template、推理模式。最好在基座和最终 LoRA 上各复验一次，防止微调改变 Prompt 敏感度。

### 3. Doubao Mini / Lite

云端不跑完整多臂探索。

Mini 只保留：

- CTX-0；
- 代理模型选出的最短候选；
- 相邻更长候选；
- 一个等 token hard distractor。

Lite 在同一冻结集和复杂案例子集上跑完全相同的 contrast。

迁移顺序建议：

```text
生产基座 API 小规模筛选
→ Mini 锁定 2 个候选
→ 按选定合同做一次正式 SFT
→ 最终 LoRA checkpoint 上做“winner vs 更短消融”
→ Lite 独立确认复杂案例
```

Mini 和 Lite 分别下结论，不能因为 Lite 更强，就认为 Mini 也能承受相同背景长度。

------

## K｜停止线

出现下面任一情况，就应删信息或改成条件检索：

1. 任一确认的 future leakage：该 arm 失去生产资格。
2. 背景 provenance 不明、晚于 cutoff、或 truth status 不是 confirmed：直接不进入候选。
3. 增加 token 后 grounded TP 没增加：被更短臂严格支配。
4. precision 未通过非劣界：不能用 recall 上升把它洗过去。
5. 连续两个预算等级 `ΔF1 < 1 个百分点`，且置信区间跨 0：停止继续扩 Prompt。
6. 新内容只对少数 background-dependent 案例有效：改成触发式检索，不常驻。
7. 删除某项后 F1、precision、安全指标都不下降：删除。
8. 一条内容的 LOO／Shapley 长期为负：删除或降级为不召回。
9. cost per grounded TP 上升超过预注册业务上限：停止。
10. 只有缓存成本变低，但准确率变差：仍然删除。缓存便宜不等于没有注意力成本。

🔥 如果现在就冻结第一轮实验，我建议把 `CTX-S` 设为默认候选、`CTX-M` 设为条件检索候选、`CTX-L` 设为压力测试臂。不要从 CTX-L 开始往回删，那会让实验成本和解释难度都更高。

来源：ChatGPT