# Deep Research｜正例、反例和 minimal pair 应不应该常驻事实抽取 Prompt？

## 决策摘要

✅ **当前不建议把固定 few-shot examples 直接升级成事实抽取 Prompt 的永久组成。更稳的默认架构是：Rulebook 常驻，EX0 保留为生产基线；examples 先作为可插拔模块测试，优先测试极短的 contrastive minimal pair，而不是完整小说案例。**

理由很明确：已有研究同时给出了两组看起来相反、其实并不矛盾的证据。

一边是，选得好的 demonstrations 确实可以提高结构化生成、语义解析、关系抽取和信息抽取表现；相似样本检索、结构匹配以及“错误示范 + 明确纠正”的 contrastive ICL 都有正结果。citeturn18search9turn17view1turn17view5

另一边是，demonstrations 不是一个稳定的“规则教学器”。模型可能主要学到格式、标签空间、输入分布和表面共现，而不是真正学会例子里面的逻辑；顺序、位置、样本选择甚至重复措辞都可以明显改变结果。信息抽取领域也已经有研究直接发现，单纯把大模型当 few-shot extractor，效果可能弱于专门微调的小模型，而且延迟和成本更高。citeturn20view5turn20view6turn20view7turn20view4turn21view0

所以对你们这个项目，我会把候选方案排成：

| 方案 | 当前判断 | 原因 |
|---|---:|---|
| **EX0：规则，无 examples** | **必须常驻基线** | 是判断 examples 到底有没有净收益的锚点 |
| **1 组 contrastive minimal pair** | **🔥 最值得试** | 单位 token 信息密度最高，特别适合“计划 vs 已发生”“否定 vs 肯定”这种窄边界；已有 IE 工作支持显式错误+纠正，而不是裸负例。citeturn17view2turn17view3 |
| **固定 2 个 examples** | 可测试，不建议预设为永久方案 | 最容易复现，也最容易产生句式、事实数量和顺序锚定。citeturn20view6turn20view7turn20view4 |
| **冻结 bank 随机 2 个** | 很适合做鲁棒性实验 | 能打散固定模板，但单次结果方差会变大，需要多 seed |
| **检索 2 个** | 有潜力，但工程风险最大 | retrieval 常比随机选择更好，但选择效果与任务、模型相关，而且必须严防 DEV/同书泄漏。citeturn18search9turn17view0turn17view5 |
| **4–8 examples 常驻** | 暂不推荐 | 没有证据说明你们任务需要这么多；更多 examples 会同时增加上下文、偏置面和延迟，IE 研究里负例过多甚至出现反向波动。citeturn17view3turn21view4 |

**三层结论必须分开看：**

**Dense Qwen3-4B 代理层：**可以大胆做五臂筛选。这里的目的不是证明“few-shot 是规律”，而是找出 **哪些 Input Context Contract 值得进入下一轮**。我会优先比较 EX0、EX-CONTRASTIVE、EX-RANDOM；EX-FIXED 和 EX-RETRIEVED 作为完整对照。

**Sparse Ling Tiny 层：**只复验 Qwen 已筛出的 2–3 个结论，例如“EX0 vs 一组 contrastive pair”“fixed vs random”“2-shot 顺序敏感性”。不能把 Qwen3-4B 的最优示例、最优顺序、最优 shot 数直接搬过去。demonstration selection 已被研究发现明显依赖 inference model，同一组示例在不同模型上的效果会变化。citeturn17view0turn20view7

**Doubao Mini/Lite 生产层：**不要把本地赢家直接当生产配置。Mini 应重新做 EX0 vs 1–2 个最终候选；Lite 也要单独验证，尤其是你们打算把它作为复杂案例升级模型时。火山引擎目前确实把 Doubao Seed 2.0 Mini 和 Lite 都作为 2.0 系列产品提供，并把它们定位到不同成本/能力区间，但官方公开材料并没有替你们回答“中文小说事实抽取应该用几条 demonstration”这个问题。citeturn19search1turn19search0

**我的生产先验不是“examples 常驻”，而是：**

> **Rulebook 常驻；examples 默认关闭。只有当某种极短 example 经过跨句式、跨材料、跨模型验证，能稳定增加 semantic F1，且不是靠压 recall、改变 fact 数量或复制模板换来的，才允许进入 permanent prompt。**
>
> 更有希望的长期形态可能是 **EX0 默认 + hard-case 时动态插入 1 组边界型 minimal pair**，而不是每个窗口无条件塞 2–8 个固定例子。

这个判断与 IE 中 contrastive demonstrations 的正证据、few-shot IE 的负结果、demonstration 顺序/格式敏感性，以及表面重复导致 shortcut 的观察是一致的。citeturn17view1turn17view3turn21view0turn20view4


## 证据地图与最相关研究

下面这 15 项是我认为与你们当前决策最贴近的工作。不是按论文影响力排，而是按“能不能直接改变你们实验设计”排。

| 研究 | 与本项目最相关的结果 | 应该怎么读 |
|---|---|---|
| **Zhao et al., 2021, Calibrate Before Use** | few-shot 结果对 prompt 格式、examples 和顺序都很敏感；同一任务可从接近随机猜测变化到接近当时 SOTA；还观察到靠近 prompt 末尾答案的偏置。citeturn20view6 | 强反证：固定 demo 并不是无害上下文 |
| **Lu et al., 2022, Fantastically Ordered Prompts** | 相同 examples 仅改变排列就可能造成极大差异；研究中的顺序选择方法在 11 个分类任务上带来 13% 相对提升，而且一个模型的好顺序不能直接迁移到另一个模型。citeturn20view7 | 直接要求你们测 example-order sensitivity |
| **Min et al., 2022, Rethinking the Role of Demonstrations** | 在分类/多选任务里，把 demo 的真实标签随机替换，性能竟然往往只小幅下降；重要作用来自标签空间、输入分布和格式。citeturn20view5 | 🔥 证明“few-shot 提分 ≠ 模型学会规则” |
| **Rubin et al., 2022, Learning to Retrieve Prompts** | 在三个 seq2seq 语义解析任务中，学习出来的 prompt retriever 明显优于多种基线。citeturn18search9 | 支持 EX-RETRIEVED，但不证明普通 embedding 最近邻就是最佳 |
| **Levy et al., 2023, Diverse Demonstrations Improve Compositional Generalization** | 相似 examples 可能重复而缺结构覆盖；更有结构多样性的 demonstrations 在三个语义解析数据集上显著提升，而且与 fine-tuning 联用时仍能带来收益；作者还用 noisy demos 缓解过度依赖。citeturn15view1 | 支持“bank 多样化”，反对固定同模板反复训练 |
| **Ma et al., 2023, LLM Is Not a Good Few-shot Information Extractor** | 九个数据集、四类 IE 任务的比较中，直接 few-shot LLM extractor 并没有普遍胜过微调小模型；作者反而发现让 LLM 只处理难例的 filter-then-rerank 更合算，并报告平均约 2.4 F1 增益。citeturn8search2turn21view0 | 🔥 few-shot IE 的重要反证 |
| **Pang et al., 2023, Guideline Learning for In-context IE** | 论文把 ICL-IE 的一个问题归因于有限上下文难以表达复杂指导与边界，并让系统从错误中学习/检索 guideline。citeturn9search1turn20view1 | 很适合你们 Rulebook + case 的思路：规则与例子并非二选一 |
| **Understanding ICL from Repetitions, 2023** | 上下文里的重复 token 共现会强化连接；重复 demonstrations 可能把模型卡在错误的表面模式上。citeturn20view4 | 支持你们担心的 boilerplate、固定字段措辞和模板 shortcut |
| **Mo et al., 2024, c-ICL** | NER/RE 中把正例与 hard negative 一起放入 demonstrations，优于 positive-only 消融；但负例过多后效果会波动，文本变长也可能拖累结果。citeturn17view1turn17view3 | 🔥 与“错误示范＋纠正”最直接相关 |
| **Peng et al., 2024, Revisiting Demonstration Selection** | demonstration 的好坏同时依赖数据和模型；同一 demonstrations 在不同 inference model 上可明显不同。citeturn17view0 | 直接支持“Qwen → Ling → Doubao 不得自动外推” |
| **Schoch & Ji, 2025, ICL of Length Biases** | 模型可以从 demonstrations 中学到长度相关偏置，说明上下文里的统计规律本身就可能变成预测捷径。citeturn21view4 | 对你们的“示例会不会诱导 fact 数量/输出长度”是重要风险信号 |
| **Cobbina & Zhou, 2025, Where to Show Demos** | 在多个开源模型家族上，仅改变 demonstrations 的位置就会改变准确率和预测；研究报告 demo 放前面通常更稳，小模型受到的位置影响更明显。citeturn8search4turn20view2 | 支持 demos 放 target 正文之前，不要正文后再塞一组例子 |
| **Bornschein et al., 2025, Fine-tuned In-Context Learners** | 直接把 k-shot prompt 形态纳入 fine-tuning，并在推理时继续给 examples；其任务集合里 ICL+FT 经常达到或超过单独 ICL/FT。训练过程会抽取不同上下文 examples，而不是只依赖一个固定 boilerplate。citeturn15view0 | 证明“微调后 examples 一定没用”也是错的 |
| **Chakma et al., ACL 2026, Structured Semantic Information… Few-shot RE** | 对关系抽取，按句法—语义结构选例子，与 LLM 生成例子组合后的方案比单一策略更强；论文报告在 FS-TACRED/FewRel 以及 Qwen/Gemma 间都有迁移结果。citeturn17view5 | 支持将来按“边界结构”检索，而不只是找字面最像句子 |
| **You et al., 2026, LC-ICL** | 在 c-ICL 基础上给负例增加 error-cause labels，让模型不只看到“错”，还知道错在哪里，并报告 NER/RE 改进。citeturn17view4 | 很贴近你们的 `计划误判 / 否定误抽 / 梦境误抽` error taxonomy |

这批研究有一个很重要的共同限制：**没有哪一项直接研究“中文长篇小说事实状态库 + 4B Dense Qwen + Sparse Ling Tiny + Doubao Seed 2.0”这一组合。** 很多结果来自分类、NER、RE、语义解析，模型从 GPT 系、LLaMA/CodeLlama 到 Gemma/Qwen 都有。因此它们最适合用来决定“该测什么风险”，不适合拿来宣布一个跨模型定律。demonstration selection 和顺序效果甚至已经被直接观察到具有模型依赖性。citeturn17view0turn20view7


## Few-shot、正反例与 minimal pair 到底会带来什么

### Few-shot 有真实收益，但不能把收益直接解释成“理解得更好了”

支持 examples 的证据并不少。

语义解析中，检索到合适 demonstrations 可以明显优于随机示例；关系抽取中，按语义结构检索例子也能提高结果；c-ICL 和 LC-ICL 则直接表明，在 NER/RE 中，让模型同时看到正确案例和明确标记的错误案例，可以超过 positive-only 方案。citeturn18search9turn17view5turn17view1turn17view4

这跟你们的任务很契合。比如：

```text
文本：
赵青说明天去城里。

错误：
赵青去了城里。

原因：
“明天”表示未来计划，不是已经发生。

正确：
赵青计划明天去城里。
```

这里真正有价值的部分不是“赵青”“城里”，而是把一个很窄的判定边界显式摆出来：

```text
将来计划 ≠ 已发生事实
```

这类 pair 的优势是 **每个 token 都在解释决策边界**，不像完整小说 demo 那样夹杂人物、场景、叙述结构、无关事实数量等大量变量。c-ICL 的结果尤其支持“负例必须有清楚的错误标记和正确答案”：作者明确指出，如果错误样本和正常样本长得完全一样，而又没有专门训练，模型很难知道它是“不能模仿的错误”；他们因此给负例加入 Wrong flag 和正确结果。citeturn17view2

所以：

❌ 不建议：

```text
示例：
赵青说明天去城里。
赵青去了城里。
```

模型不知道第二行是在展示错误还是答案。

✅ 推荐：

```text
示例：
赵青说明天去城里。
错误判断：赵青去了城里。
正确判断：赵青计划明天去城里。
关键区别：未来计划 ≠ 已发生。
```

或者更短：

```text
“明天去城里”
× 已去了城里
✓ 计划去城里
```

到底哪个版本更好，不应该凭直觉定，要把“有原因说明”和“无原因 minimal pair”也当一个小消融项。

### 正例、反例、纠错示例并不是一回事

你们最好不要把所有东西统称为“negative example”。

**普通正例**告诉模型“什么应该抽”。它比较适合教输出形态、典型关系和允许抽取的事实。风险是示例有几个 facts，模型可能跟着产几个；示例都是人物行为，模型也可能降低对状态、说话人等其他类别的注意。Min et al. 的结果提醒我们，demo 带来的提升相当一部分可能只是格式和分布 priming。citeturn20view5

**空答案反例**告诉模型“这里一个都不要抽”。它对控制 hallucination/过抽很有价值，但如果比例过高，很可能把决策阈值往“不抽”方向推。c-ICL 的实验没有证明“负例必然降低 recall”，但确实发现随着负例占比增加，效果不是单调上升，过多负例会引入噪声和歧义。citeturn17view3

**错误答案 + 纠正**跟普通负例不同。它同时告诉模型：

> 这是一个很诱人的错误 → 为什么错 → 应该怎么判。

现有 IE 证据更支持这种写法，而不是只给一个“NO”。citeturn17view2turn17view4

**minimal pair**则是更严格的控制实验：两句话只改一个最关键的信息，正确事实随之发生变化。例如：

```text
A：赵青说明天去城里。
→ 赵青计划去城里。

B：赵青说自己昨天去了城里。
→ 赵青陈述自己昨天去了城里。
```

或者：

```text
A：周宁没有杀死那匹狼。
→ 不抽“周宁杀死狼”。

B：周宁杀死了那匹狼。
→ 抽“周宁杀死狼”。
```

它特别适合你们，因为你们面对的很多错误就是 **一个状态词把事实类型翻转**。但这里也有一个坑：如果 bank 永远写成“明天 → 计划”“没有 → 不抽”，模型有可能学成关键词规则，而不处理更复杂的：

```text
他原说明天便走，谁知当夜已经偷偷离开。
```

所以 minimal pair 应该是**教学材料，不是最终泛化考卷**。真正判断学没学会，要靠后面讲的 paraphrase、结构变换和 cue-conflict 测试。

### 例子越多，不等于越好

研究没有给出一个适用于你们任务的“1/2/4/8 最优值”。

c-ICL 在其 NER/RE 设置里看到增加 shots 总体趋向有利，但它测试的示例规模和你们设想的 1–4 个并不相同，而且同一论文也发现负例增加到一定程度后结果开始波动，更长的上下文本身会伤害部分复杂 NER 数据集。citeturn17view3

长度偏置研究进一步说明，demonstrations 中反复出现的长度统计规律会被模型学到；重复模式研究也发现，共现次数增加会强化表面 token 连接。也就是说，从 1 个例子加到 8 个例子时，你增加的不只是“教学信息”，也增加了八倍左右的潜在 style/fact-count/label-frequency 信号。citeturn21view4turn20view4

因此我建议把 shot 数实验拆成两层：

**筛方案时所有 demo 臂固定 K=2。**

只有某一种 demonstration 类型已经确认有信号，才继续跑：

```text
K = 1
K = 2
K = 4
K = 8
```

这样不会把：

```text
5 种选择策略 × 4 种 shot 数
```

直接膨胀成一个昂贵的大搜索。

而且要记录的是 **边际收益**：

\[
\Delta F1_{1\to2},
\quad
\Delta F1_{2\to4},
\quad
\Delta F1_{4\to8}
\]

同时记录：

\[
\Delta input\ tokens,\quad
\Delta latency,\quad
\Delta overextract,\quad
\Delta recall
\]

很可能你们真正想找的并不是“最高 F1 的 K”，而是类似：

> K=1 已经拿到 80% 的收益；K=2 有一点增益；K=4/8 几乎不涨，还开始诱导输出变长。

如果出现这种曲线，生产上自然不会选 8。

### 顺序、标签、答案长度和事实数量都应该视为实验变量

example-order sensitivity 已经不是猜想。Zhao et al. 和 Lu et al. 都发现改变 demo 顺序可以大幅改变 few-shot 结果；Lu et al. 还发现一个模型上的好排列不能直接迁移到另一个模型。citeturn20view6turn20view7

对你们而言，应该额外测四种“污染探针”。

**事实数量探针：**

让同一个 target 配上：

```text
demo set A：每例 0~1 fact
demo set B：每例 3~4 facts
```

target 完全不变。

然后测：

\[
corr(\text{demo fact count},\text{predicted fact count})
\]

以及：

\[
E[\hat n-n_{\text{gold}} \mid \text{demo count}]
\]

如果 target 完全一样，但 demo facts 多的时候模型就多抽，这就是你们最担心的 fact-count anchoring。

**答案长度探针：**

同样语义的 demonstrations 做两个版本：

```text
短答案版
长解释版
```

比较 output tokens。模型从上下文里学习长度偏置已有直接实验依据。citeturn21view4

**标签顺序探针：**

例如永远写：

```text
错误 → 原因 → 正确
```

再改成：

```text
正确 → 错误 → 原因
```

看输出判定有没有变化。

这里不是为了寻找某个神奇顺序，而是为了判断模型是不是对顺序过敏。prompt 顺序偏置已经在多项 ICL 工作中出现。citeturn20view6turn20view7

**example 排列探针：**

K=2 很方便，直接跑：

```text
A → B
B → A
```

K=4 不必一上来跑全部 24 个排列；可以冻结 6 个预注册排列，计算：

```text
order_F1_range
prediction_flip_rate
```

如果一个方案平均 F1 高 1 点，但换个顺序就掉 5 点，它不适合成为生产常驻 prompt。


## 最小实验表与预注册指标

### 你要求的五臂，建议这样冻结

| Arm | Prompt 中 examples | 选择规则 | 这个 arm 真正在测什么 |
|---|---|---|---|
| **EX0** | 无 | 无 | Rulebook 自己够不够 |
| **EX-FIXED** | 固定 2 个 | 所有样本完全一样 | 固定教学材料的平均收益及锚定风险 |
| **EX-RANDOM** | 随机 2 个 | 从冻结 bank 采样 | 例子多样性是否比固定模板稳 |
| **EX-RETRIEVED** | 检索 2 个 | 只看 target 输入可观察信息 | 相似/同边界例子是否有额外价值 |
| **EX-CONTRASTIVE** | 1 组 minimal pair | 两例只变一个语义关键点 | 窄边界教学是否以最低 token 成本带来收益 |

retrieval 相比随机 selection 在语义解析和通用 ICL 研究中经常占优，但 demonstration choice 已被发现明显依赖模型，所以 EX-RETRIEVED 必须被当实验 arm，而不是默认赢家。citeturn18search9turn16view3turn17view0

🔥 **EX-RETRIEVED 有一条非常重要的规则：不得用 gold error type 选示例。**

比如 DEV 里一句：

```text
王成以为妹妹已经死了。
```

你不能因为 gold annotation 告诉你这是 `false_belief`，就检索一个 `false_belief` pair。

这样实际上已经把答案的一部分泄漏给模型。

允许的是：

```text
query text
    ↓
冻结的 cue detector / embedding retriever
    ↓
从 TRAIN-only bank 选 examples
```

例如 detector 看到：

```text
“以为”
“听说”
“似乎”
“准备”
“明日”
```

推测这里可能存在 epistemic/modal boundary，然后选例子。这是 inference-time 可用的信息。

### Token 怎么尽量公平

这里有一个很容易做错的地方：

❌ **不要为了让 EX0 和 few-shot 完全等长，往 EX0 塞随机废话。**

随机 filler 自己也会改变 attention 和上下文位置，所以它不是干净的控制。

更靠谱的是做两类比较。

**主实验保持真实成本：**

```text
EX0        = 真实无 demo
其他 arms  = 真实 demo 长度
```

记录精确 input token 数、latency、output token 数。

这回答的是：

> “实际部署时，加 examples 到底值不值？”

**再加一个可选的 token-budget control：**

```text
EX0-RULEMATCH
```

不用 examples，而是拿同样的 token 预算再写一遍简短 Rulebook 边界，例如：

```text
计划不是已发生事实。
否定内容不得当作肯定事实。
角色误信不得升级为客观事实。
```

这样比较：

```text
2 examples
vs
相同 token 数的明确规则
```

反而可以直接回答你们真正关心的问题：

> 是“例子”有效，还是因为我多花了 100 个 token 重申任务而已？

demo arms 内部则应尽量严格控长。我建议 example bank 生成时就分长度桶。比如以**当前测试模型自己的 tokenizer**计算：

```text
每个 example：48–64 input tokens
两例总预算：96–128 tokens
```

不是死守这组数字，而是让 FIXED、RANDOM、RETRIEVED、CONTRASTIVE 的 demonstration section 尽量落到同一预算带。

不同模型 tokenizer 不一样，因此到了 Ling/Doubao，要重新计算 token，不要沿用 Qwen 的字符数当 token 数。

### Shot 数要做两种实验，别混在一起

**Operational dose test：**

每个 demo 长度不变：

```text
K1 ≈ 60 tokens
K2 ≈ 120 tokens
K4 ≈ 240 tokens
K8 ≈ 480 tokens
```

这回答“多花上下文值不值”。

**Fixed-budget diversity test：**

总 demo budget 不变，例如都约 128 tokens：

```text
1 个较完整 example
2 个短 examples
4 个超短 examples
```

这回答“同样 token 下，多样性重要还是单例细节重要”。

两项不能混成一个结论，因为第一项同时改变了 shot 和 token，第二项则同时改变了 shot 和每例信息量。

### 预注册指标

**G｜主指标建议按下面冻结，不要只看一个 F1。**

| 指标 | 建议定义 | 为什么必须看 |
|---|---|---|
| **semantic Precision** | 匹配的正确 facts / predicted facts | 负例可能主要提高 P |
| **semantic Recall** | 匹配的正确 facts / gold facts | 防止模型靠“不抽”刷 F1 |
| **semantic F1** | P/R harmonic mean | 主结果 |
| **fact-count bias** | mean(predicted count − gold count) | 抓 demo 数量锚定 |
| **fact-count MAE** | mean\(|predicted count-gold count|\) | 防正负偏差互相抵消 |
| **gold-empty accuracy** | gold 为空时真正输出空的比例 | 看过抽 |
| **false-empty rate** | gold 非空却输出空 | 看“拒抽”副作用 |
| **status score** | 对已匹配事实评估状态字段 | 专门检查计划/推测/误信等 |
| **speaker score** | 对可匹配言语事实评估 speaker | 防 speaker 被 demo 人物结构带歪 |
| **over-extraction rate** | FP / predicted facts，同时另报每窗口 FP 数 | 生产状态库最危险指标之一 |
| **example wording reuse** | 去掉 schema 字段后，与 demos 的表面字符串重复比例 | 抓模板复制 |
| **output length** | output tokens + fact count | 抓答案长度锚定 |
| **input tokens** | 实际 tokenizer 统计 | 成本分母 |
| **latency** | p50、p95 | 生产代价 |

不要把：

```text
empty accuracy = 高
```

直接解释成好事。

一定要成对看：

```text
gold-empty accuracy ↑
false-empty rate ?
semantic recall ?
```

因为你们担心的“negative demos 教会模型拒抽”恰好会表现成：

```text
空题更好了
Precision 更高了
但 Recall 掉了
```

c-ICL 对正负示例比例的实验也给出了类似警示：负例增加并不是无限制单调受益，过多会带来噪声和更长上下文。citeturn17view3

### 必须按错误类型分层报告

总 F1 很容易掩掉真正变化。

每个 arm 至少拆：

```text
affirmed / ordinary positive
negation
failed attempt
future plan
speculation
belief / misbelief
reported speech
dream / imagined event
read-only region
gold-empty
same-word-different-relation
speaker ambiguity
```

例如 EX-CONTRASTIVE 可能：

```text
future-plan +12 F1
negation +8
普通正事实 -2
```

平均只涨 2 点。

这个结果非常有价值，因为它说明：

> 这个 example 不是 global prompt 组件，而是 **future/negation hard-case module**。

这可能比“全局常驻”更适合你们。


## Example bank、hard negative、训练和泄漏合同

### 小型 example bank 怎么设计

**J｜我建议第一版不是做几百个，而是做一个约 32–48 例的“小而干净”bank。**

重点不是数量，而是每个例子有明确用途。

一个合理的最小覆盖是：

| 边界类型 | 至少准备 | 典型 minimal contrast |
|---|---:|---|
| 否定 | 4 | 杀了 / 没杀 |
| 未遂、尝试 | 4 | 想杀 / 杀了；刺去但被挡 / 刺中 |
| 未来计划 | 4 | 明日去 / 已去 |
| 推测、不确定 | 4 | 似乎是 / 确认是 |
| 梦境、想象 | 4 | 梦见发生 / 现实发生 |
| 转述 | 4 | A 说 B 做了 / 叙述者确认 B 做了 |
| 误信 | 4 | A 以为 B 死了 / B 确实死了 |
| 只读区、上下文边界 | 4 | 背景只供理解 / 当前 extraction span |
| 同词不同关系 | 可额外 4–8 | “带走”“认作”“叫”等不同语义 |

LC-ICL 最新工作也在走类似方向：与其只给“错误答案”，不如明确指出错误原因类别，让 negative 提供可用的错误边界信息。citeturn17view4

每个 bank item 建议至少有这些元数据：

```text
example_id
bank_version
boundary_type
subtype
polarity
source_type
rights_status
source_group
author_group
template_family
surface_family
gold_fact_count
negative_fact_count
cue_words
token_count_qwen
token_count_ling
token_count_doubao
created_at
review_status
```

这是干嘛的：以后出现“这个 demo 为什么进 prompt？”时，你们可以追溯，而不是只看到一坨字符串。

### 每个 example 应该多长

我的建议是：

**正文只够表达一个边界。**

不要写：

```text
五百字小说情节
→ 6 个事实
→ 4 个状态
→ 2 个 speaker
```

而是尽量：

```text
1–2 个句子
1 个核心判断
最多 1–2 个 gold facts
```

完整 demonstration 尽量控制在 **大约 40–70 model tokens** 的量级，再按模型 tokenizer 实测，而不是按中文字数死算。

🔥 每个 example 最好只负责一个问题。

例如 future-plan pair 就不要同时带：

```text
未来计划 + 梦境 + 转述 + speaker ambiguity
```

否则你无法知道它为什么有效。

### Hard negative 怎么写

对你列出的几种 hard negative，我建议形式高度统一：

```text
输入
容易犯的错误
正确处理
边界原因
```

例如：

**否定**

```text
输入：沈岳没有打开木匣。
错误：沈岳打开了木匣。
正确：不得抽取“沈岳打开木匣”。
原因：动作被明确否定。
```

**未遂**

```text
输入：沈岳拔刀刺去，却被韩策一掌格开。
错误：沈岳刺中了韩策。
正确：沈岳尝试刺击韩策；不得抽取“刺中”。
原因：动作发起 ≠ 结果达成。
```

**未来计划**

```text
输入：沈岳说明早去青州。
错误：沈岳去了青州。
正确：沈岳计划明早去青州。
原因：未来计划 ≠ 已发生。
```

**误信**

```text
输入：沈岳一直以为韩策已经死了。
错误：韩策已经死亡。
正确：沈岳相信韩策已经死亡。
原因：人物信念 ≠ 客观事实。
```

**梦境**

```text
输入：梦里，他看见青州城已经烧成灰烬。
错误：青州城被烧毁。
正确：不得升级为现实世界事实。
原因：梦境内容 ≠ 当前现实状态。
```

**转述**

这里要特别小心，因为“转述”未必等于不抽。它可能产生：

```text
A 声称 P
```

而不是：

```text
P 是客观事实
```

所以 example 应明确展示的是 **provenance/status 的变化**，不能简单教模型“听说/说过 → 全部丢弃”。

**只读区**

```text
只读背景：上一章张衡已经受伤。
当前可抽区：张衡扶墙走进屋内。

错误：
从只读背景再次写入“张衡受伤”。

正确：
只抽当前写区产生或确认的目标事实。
```

这类 example 对你们尤其有意义，因为它直接对应 Input Context Contract，而不是自然语言里的普通 IE。

**同词不同关系**

要故意用相同 surface word：

```text
“他认了赵安作义子”
vs
“他认出了赵安”
```

让模型不能只靠“认”触发一个固定关系。

### Example retrieval 怎么防 DEV 泄漏

**F｜这里要采用比普通 RAG 更严格的隔离。**

retrieval bank 只能来自：

```text
rights-clear TRAIN
synthetic TRAIN bank
```

明确禁止：

```text
DEV examples
DEV 的 paraphrase
DEV 派生错误分析后重新写出的近似句
未来 Production Canonical 测试项
```

retrieval 类 ICL 的确可以优于随机选择，因此越是做 retrieval，越必须把“检索库是不是偷偷含测试信息”当独立风险看待。citeturn18search9turn17view5

我建议冻结下面四层隔离：

```text
book_id
author_id
source_family
template_family
```

对于真实文学材料，DEV 的某作者出现后，该作者的 examples 不允许进入其 retrieval bank。

对于合成数据也一样，别以为“都是合成的就不存在泄漏”。如果同一个生成模板：

```text
X 说明天去 Y
```

同时生成：

```text
TRAIN：赵青说明天去城里
DEV：陈远说明天去县城
```

这其实已经非常接近 template leakage。

所以 synthetic 还应按：

```text
generator_template_family
```

整组切分。

👉 **同书、同作者 isolation 应该在检索之前做，而不是检索后再过滤。**

也就是建立 index 时就没有这些禁用内容，而不是让 retriever 先看到，再说“不采用 top-1”。

另外每次推理必须日志化：

```text
query_id
retrieved_example_ids
retrieval_scores
filter_reason
bank_version
```

这样某个 DEV 分数异常高时才能查是不是 retrieval 泄漏。

### 训练时反复塞固定 examples，我不建议

**第七个问题的回答是：有明显 shortcut 风险，但“loss 稀释”要看你们具体怎么算 loss。**

固定 example 每个训练样本都重复：

```text
赵青……
赵青……
赵青……
```

会制造非常强的固定共现环境。关于上下文重复的研究已经表明，重复 token 共现会强化表面连接，甚至让模型陷入错误的 spurious pattern。citeturn20view4

至于所谓 **loss dilution**，要直接检查你们 trainer 的 `labels`：

如果 prompt token 被：

```text
labels = -100
```

全部 mask，只在 assistant target 上算 loss，那么固定 examples **不会直接占输出 token 的监督 loss**；但它们仍然每次参与 forward/attention，增加训练计算，并永远作为相同条件出现在 target 前面。

如果你们连 user prompt/examples token 也一起算 causal-LM loss，那么重复 boilerplate 就真的会占一部分训练目标。

所以这个问题不要争概念，直接查训练 batch：

```text
input_ids
labels
loss_mask
```

就能确定。

我的建议是：

❌ 不要把同一组 examples 复制进 100% SFT 样本。

如果将来确认“训练模型学会利用 demos”值得做，更好的实验是：

```text
一部分训练样本：EX0
一部分：随机 1–2 个合法 examples
一部分：contrastive pair
```

并随机改变：

```text
example identity
人物名
surface wording
example order
```

但不要随机改变：

```text
Rulebook 语义
字段语义
gold label 定义
```

已有工作已经证明，**variable demonstrations + fine-tuning 并不是必然导致训练不稳定**。Bornschein et al. 的 ICL+FT 会采样不同 context examples；Levy et al. 也发现 diverse demonstrations 与 fine-tuning 可以共同提高 compositional generalization，并特意用带噪 demonstrations 降低过度依赖。citeturn15view0turn15view1

所以第八个问题的答案不是“随机一定更鲁棒”，而是：

> **随机 example identity 是值得测试的正则化方向；随机任务定义不是。**

而且一定要保留一定比例的 EX0 训练样本，否则有可能训练出一个“没看到 examples 就不会做”的模型。


## 怎么证明模型学会了规则，而不是在复制示例

这是整个实验里最重要的一层。

**H｜只看未见 DEV24 F1 还不够。**

Min et al. 已经给过非常强的警告：在他们的分类/多选实验中，就算 demo 的真实 input-label mapping 被破坏，few-shot 性能也没有像直觉预期那样崩掉；模型很大一部分收益可能来自格式、标签和输入分布。citeturn20view5

所以你们至少要加下面几组 diagnosis。

### Lexical transfer：关键词换掉还会不会

训练/example bank：

```text
明天
准备
计划
```

测试故意写：

```text
待到天亮便动身
三日后启程
过些日子再去
待伤好以后前往
```

如果只有出现“明天/计划”才判 future plan，说明学的是 cue list。

### Structural transfer：句式完全变掉还会不会

demo：

```text
赵青说明天去城里。
```

test：

```text
“城里么？”赵青想了想，“待雨停，我过去一趟。”
```

仍然应该识别“未来意图”，但 surface structure 已经不同。

### Minimal semantic flip：只换一个词，输出必须翻

```text
他以为韩策死了。
他确认韩策死了。
```

或者：

```text
没有刺中。
已经刺中。
```

真正理解边界的模型应该随着语义 cue 翻转，而不是随着句子其他部分。

### Cue-conflict：关键词和真正语义故意打架

这是比普通 minimal pair 更强的测试。

```text
他原计划明日离开，不想当天夜里便已出了城。
```

里面同时存在：

```text
计划
明日
已
```

如果模型看到“计划”就只输出未来事实，它就露馅了。

再比如：

```text
众人都以为他死了，直到他推门走进大厅。
```

必须区分：

```text
众人的误信
vs
当前现实状态
```

### Fact-count invariance：demo 有几个 facts 不应该决定 target 有几个

固定同一批 target，分别配：

```text
demonstrations 平均 0.5 facts
demonstrations 平均 1 fact
demonstrations 平均 3 facts
```

计算：

\[
\beta_{\text{demo-count}}
\]

也就是 predicted fact count 对 demo fact count 的回归系数。

理想上接近 0。

如果显著为正，固定 examples 即使 F1 略涨，也很危险。

### Example-order invariance

相同 example set 换顺序。

记录：

```text
semantic prediction flip rate
fact-count flip rate
status flip rate
speaker flip rate
```

顺序敏感性在已有 few-shot 研究中非常强，而且好的顺序不能假定能跨模型迁移。citeturn20view7turn17view0

### Example ablation：微调模型拿掉 examples 还会不会

假设未来 Qwen/Ling 做了带 examples 的 SFT：

```text
train with demos
```

测试必须同时跑：

```text
inference with demos
inference without demos
```

如果：

```text
有 demo：90 F1
没 demo：65 F1
```

那不是“模型已经把规则学进权重”。

它更像是：

> 模型学会了一个依赖这种 prompt contract 的工作模式。

这不一定不能生产，但要明确知道你买到的是什么。

Bornschein et al. 的结果正说明 fine-tuning 与 ICL 可以形成组合方法；它并不意味着 fine-tune 完以后 demonstration 就自然冗余。citeturn15view0

### Copy detector：直接查它有没有抄 example

你要求的“示例措辞复用率”建议分三层。

去掉固定 schema token，例如：

```text
subject
predicate
object
status
speaker
evidence
```

再计算：

```text
最长公共字符串长度
character 4-gram Jaccard
输出与任一 demo 的 normalized edit similarity
```

还可以单独记录：

```text
demo-only lexical copy rate
```

也就是：

> output 中出现了 example 里的专有词/措辞，但这些词没有出现在 target 正文。

这个指标特别好抓这种问题：

```text
demo 人物：赵青
target 人物：陈川
输出居然出现：赵青
```

这种当然是严重污染。

更隐蔽的是：

```text
demo：
“计划明天前往”

target：
“待雨停后便走”

output：
“计划明天前往……”
```

事实可能勉强对，但模型已经把 demo wording 搬过来了。对于进入长期状态库的 canonical facts，这种模板迁移一样值得警惕。

### 只有通过这些测试，才叫“rule generalization”

我会把判定写得很严格：

✅ **可以认为有规则迁移迹象：**

```text
未见人物 ✔
未见措辞 ✔
未见句法结构 ✔
minimal semantic flip ✔
cue-conflict ✔
example 顺序变化仍稳定 ✔
demo fact count 改变仍稳定 ✔
example wording reuse 不上升 ✔
```

而：

```text
普通 DEV F1 ↑
但换同义词就掉
```

只能叫：

> example-compatible performance 提升。

不能叫“模型学会了规则”。


## Prompt 放置、Rulebook 优先级与生产合同

### Examples 不建议放 system 里当不可变事实

system 层更适合放：

```text
任务角色
不可违反的语义规则
上下文区域权限
冲突优先级
输出契约
```

而 demonstration 是“例子”，不是规范本身。

我建议 Prompt 结构更像：

```text
[SYSTEM]
任务身份
事实定义
禁止未来信息泄漏
只读区规则
冲突时 Rulebook 优先

[USER / TASK]
简版 Rulebook

以下例子只用于说明判定边界。
若例子与 Rulebook 冲突，以 Rulebook 为准。

[DEMONSTRATIONS]
1–2 个极短例子

[TARGET CONTEXT]
只读背景……
当前可抽正文……

[TASK]
只根据允许区域抽取。
```

demonstrations 放在 target 正文**前面**更值得作为默认测试位置。已有 positional-bias 研究在多个模型家族中发现，改变 demo 在 prompt 中的位置本身就会改变预测，而且小模型更容易受到影响。citeturn8search4turn20view2

❌ 我不建议这种：

```text
正文
↓
demonstrations
↓
“请照上面例子回答”
```

因为模型刚读完 target 后又被一组人工例子覆盖，很容易产生 recency anchoring；few-shot 文献已经观察到靠近 prompt 末端的信息和 demo 顺序会改变预测。citeturn20view6turn20view7

如果正文后面真的需要东西，我更建议放 **无新事实的 checklist**：

```text
提交前检查：
- 是否把计划写成已发生？
- 是否把否定内容写成肯定？
- 是否把角色误信写成客观事实？
- 是否从只读区新增事实？
```

而不是再重复完整 examples。

### Rulebook 和 examples 冲突时，必须在 contract 里明确 Rulebook 胜

研究表明 demonstrations 会提供强烈的格式、label 和 surface prior；如果它们跟文字指令冲突，不应指望模型自动选择你们希望的那个。citeturn20view5turn20view4

所以要写死：

```text
Rulebook 是规范。
Examples 只是说明。
若二者看起来冲突，遵循 Rulebook。
不得从 Example 推导未写在 Rulebook 中的新规则。
```

这句话本身也要做测试，因为“写了优先级”不代表模型一定遵守。

可以专门造一个 conflict DEV：

```text
Rulebook：
未来计划必须标记为 planned。

Example 故意错误：
“明天去城里” → completed。
```

看模型跟谁走。

这不是生产 prompt，而是 adversarial test。

如果模型经常跟 example 不跟 Rulebook，那我会把它判成 **不适合常驻 examples**，哪怕普通 F1 有提升。

### 已经微调的模型，推理时 examples 仍可能有价值

这个问题不能回答成：

> “微调了就不需要 examples。”

已有研究已经出现 FT + ICL 联用优于两者单独使用的结果；diverse demonstrations 在与 fine-tuning 结合时也能提高 compositional generalization。citeturn15view0turn15view1

但也不能反过来说：

> “既然论文里 FT + ICL 能赢，所以我们微调后也必须保留 examples。”

你们必须直接测四格：

| 训练 | 推理 | 目的 |
|---|---|---|
| 无 examples | EX0 | 标准 SFT |
| 无 examples | EX | 看裸 ICL 增益 |
| varied examples | EX0 | 看规则有没有进权重 |
| varied examples | EX | 看 ICL+FT 联用价值 |

这一张四格表，会比争论“few-shot 对裸模还是微调模有用”更快回答你们自己的问题。


## 三层复验、停用条件与最终生产判定

### Dense Qwen3-4B：把它当筛选器，不当立法者

按你给出的边界，Qwen3-4B 是低成本代理实验台。因此它最适合做高方差、多臂和 stress tests，而不是决定 Doubao 的 permanent prompt。

我建议在冻结的合成 TRAIN24/DEV24、已有冻结考卷和权利明确材料上这样走：

**主筛选：**

```text
EX0
EX-FIXED
EX-RANDOM
EX-RETRIEVED
EX-CONTRASTIVE
```

所有有 demo arm：

```text
K = 2 个 demonstration units
demo token budget 尽量一致
temperature / decoding 固定
Rulebook 完全相同
output contract 完全相同
```

EX-RANDOM 不应该只抽一次。至少冻结多个 `example_seed`，不然“随机抽中了两个特别好的案例”会被误判成策略优势。

**主筛选过关后才测 shot dose：**

```text
winner:
K=1 / 2 / 4 / 8
```

**再做三个 stress pack：**

```text
ORDER
FACT-COUNT
LEXICAL/STRUCTURAL TRANSFER
```

🔥 你们现有 MICRO24/M1 里“C2 evidence IDs 在未见合成 DEV24 的 semantic fact F1 高于逐字 evidence”的结果继续只当本地代理证据。examples 实验也一样：**Qwen 上 EX-CONTRASTIVE 赢了，不意味着 Doubao 或 Ling 也会赢。**

### Sparse Ling Tiny：只复验关键命题

等你们确认官方可本地下载、微调链路满足要求后，我建议 Ling Tiny 不再重跑所有探索。

只拿 Qwen 筛出的 2–3 条高价值结论，例如：

```text
H1：EX-CONTRASTIVE > EX0
H2：EX-RANDOM > EX-FIXED
H3：K=2 已经饱和，K=4/8 无净收益
```

每条重新验证。

其中 **示例内容也不要默认照搬最优 Qwen examples**。可以冻结同一 bank 做一轮“严格可比”实验，但还要允许 Ling 自己重新选一次 optimal examples，因为现有 ICL 研究已经明确发现 demonstration choice 和顺序都具有模型依赖性。citeturn17view0turn20view7

最有价值的 Ling 结果不是：

```text
Qwen 87.2
Ling 88.1
```

而是：

```text
EX-CONTRASTIVE - EX0
```

在两个架构上是否同号、是否落在接近的 error slices 上。

如果：

```text
Qwen：+3.0 F1
Ling：-0.8 F1
```

结论不是“哪个模型错了”，而是：

> **这个 Input Context Contract 明显依赖模型。不得升级成通用设计规则。**

### Doubao Mini/Lite：做迁移验证，不做云端大规模探索

你已经明确云微调成本高，所以生产模型上不应重新做几十个 prompt arms。

到了 Mini，我建议只带：

```text
EX0
Qwen/Ling 最稳候选 A
Qwen/Ling 最稳候选 B
```

如果本地只有一个方案表现稳定，甚至就：

```text
EX0
candidate
```

Mini 必须重新测：

```text
semantic P/R/F1
empty
status
speaker
overextract
fact-count bias
copy rate
latency
input/output tokens
```

不能只验证平均 F1。

Lite 也不应该简单继承 Mini 的 examples。它既然承担复杂案例升级，更应该在你们的：

```text
否定嵌套
误信嵌套
转述中的转述
计划后来提前发生
梦境与现实交错
多 speaker
只读背景与当前正文冲突
```

这些 hard slice 上独立比较：

```text
Lite EX0
Lite candidate
```

火山引擎当前官方产品线确实同时提供 Seed 2.0 Mini/Lite，并持续更新这些模型版本，因此生产评测时还应固定具体 model version，而不能只记“Doubao Mini”。citeturn19search0turn19search3

### 明确停用条件

**这是我最建议你们预注册的部分。**

某种 examples 即使平均 semantic F1 上涨，也应该在出现以下任一情况时停止作为“全局常驻候选”。

**⚠️ Recall trade-off**

例如：

```text
F1 +1.2
Precision +4.5
Recall -3.0
```

如果代价是大量少抽事实，对长期状态库未必是胜利。

**⚠️ 靠拒抽赚钱**

```text
gold-empty ↑
但 false-empty ↑
```

尤其负例 arm 出现这种结果时，应直接判风险。

**⚠️ Fact-count anchoring**

改变 demo 的事实数量后，target predicted facts 跟着系统性变化。

**⚠️ Order instability**

同一 demo 集仅换顺序，就出现明显 prediction flips 或 F1 范围大于它相对 EX0 的收益。

例如：

```text
EX0 = 84
EX = 86
不同 order = 80 ~ 88
```

这个“+2”没有生产意义。

few-shot order sensitivity 在已有研究中已经非常明显。citeturn20view6turn20view7

**⚠️ Surface dependence**

同义改写、人物换名、句式改写后收益消失。

**⚠️ Demo wording leakage**

输出开始复用 example 独有措辞、人物名、关系表述。

**⚠️ Rulebook conflict**

example 与 Rulebook 冲突时，模型更容易跟 example。

**⚠️ 8-shot 才有微小收益**

如果：

```text
K0  F1 85
K1  86
K2  86.5
K4  86.7
K8  86.8
```

那生产上 K8 没有什么吸引力。

**⚠️ 跨模型反号**

例如：

```text
Qwen   +3
Ling   +2
Doubao -1
```

进入生产时当然以 Doubao 为准。

**⚠️ 收益只存在于 synthetic template family**

真实冻结考卷或不同生成模板一换，收益消失。

这说明 example 很可能教会的是 generator/template distribution。

### 我建议的晋级规则

不要用“winner takes all”。

可以给 examples 一个比较严格的晋级合同：

```text
必须：
semantic F1 有稳定正向变化
AND semantic Recall 不出现不可接受下降
AND overextract 不恶化
AND fact-count bias 不恶化
AND status/speaker 无明显回归
AND order stress 仍稳
AND paraphrase / structural-transfer 仍有收益
AND wording reuse 不上升
AND 至少两个独立材料 family 同方向
```

到了 Doubao 再增加：

```text
AND latency / token 成本可接受
AND Mini 上重新成立
AND Lite hard-case 路径单独成立
```

“可接受下降”最好在实验开始前由你们按业务代价定，不要看到结果后再改阈值。

### 最终回答：examples 到底应不应该常驻？

**I｜按现有证据，我现在不会批准“固定 2 个正反例永久常驻所有事实抽取请求”。**

证据不足，而且风险非常具体：

```text
example choice bias
example order bias
surface repetition
length / count anchoring
negative-ratio bias
Rulebook conflict
retrieval leakage
cross-model non-transfer
```

这些问题都有直接或相邻研究支持。citeturn20view6turn20view7turn20view4turn21view4turn17view3turn17view0

但我也不会得出：

> “few-shot 没用，只写 Rulebook。”

IE、语义解析和 relation extraction 已经有足够证据表明，高质量、相关、结构合适或 contrastive 的 demonstrations 可以明显提高表现，而且 fine-tuned model 也可能继续从 in-context examples 获益。citeturn18search9turn17view1turn15view0turn17view5

**所以最合理的工程假设是：**

```text
Permanent:
    Rulebook
    Input-region contract
    precedence
    output contract

Experimental / optional:
    examples

Preferred example form:
    1 个极短 contrastive minimal pair
    或按当前边界安全检索的 1–2 个例子

Not preferred:
    每次固定塞完整小说 cases
    每次固定塞 4–8 个 demo
    裸错误示范
    从 DEV / 同书 / 同作者检索例子
```

🔥 **我最看好的终态甚至不是 “EX-CONTRASTIVE 永久开”，而是两档：**

```text
普通窗口：
EX0

边界风险窗口：
Rulebook
+ 1 个对应边界的 minimal pair
+ target
```

例如检测到：

```text
以为 / 据说 / 明日 / 原打算 / 梦见 / 未能 / 没有……
```

才调用一个小 bank。

这样 examples 不再是“所有请求缴纳的固定上下文税”，而是处理已知 hard boundary 的局部工具。检索 ICL 与结构化 RE 工作支持“相关例子比无差别 examples 更可能有价值”，但模型依赖性意味着这个方案仍然必须在你们自己的 Mini/Lite 上验证。citeturn18search9turn17view5turn17view0

**K｜因此三层最终判定可以压成一句话：**

> **Qwen 用来筛假设；Ling 用来检查这些假设有没有跨架构迹象；Doubao Mini/Lite 才决定生产 Prompt。任何一层都没有资格替下一层宣布 few-shot、shot 数、示例顺序或 retrieval 策略已经成立。**

这跟现有文献里最稳定的一条结论反而很一致：**examples 可以很有用，但它们非常依赖“选了什么、怎么排、放在哪、给哪个模型”。** citeturn20view6turn20view7turn17view0turn20view2

对你们当前阶段，我给的实际优先级是：

```text
🔥 最高优先
EX0 vs EX-CONTRASTIVE

接着
EX-FIXED vs EX-RANDOM

再看
EX-RETRIEVED

只有前面确认有收益后
K = 1 / 2 / 4 / 8 dose test

明确不做
拿权利不明数据训练
拿 DEV/同书案例做 retrieval
直接把 Qwen 胜者写进 Doubao 生产 Prompt
把固定 demos 重复进每一条 SFT 样本
```

按你给出的当前数据边界，在 Production Canonical 尚未就绪、P2 材料又高度特殊、A v2.7 训练权利未解决的阶段，**合成 TRAIN24/DEV24 + 冻结考卷 + 权利明确材料**很适合承担这轮 Input Context Contract 筛选；但最终是否 permanent，应该留到生产模型和真正可代表 production distribution 的评测集上裁决。

来源：ChatGPT