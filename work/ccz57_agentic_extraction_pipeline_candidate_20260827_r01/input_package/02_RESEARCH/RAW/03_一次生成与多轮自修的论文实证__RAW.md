# 一次生成与多轮自修：哪些真的有效，哪些只是“多花了算力”

## 结论摘要

✅ **这轮文献最清楚的结论是：把“多轮”当成一个统一方法是错的。** 现有实证至少要拆成三类：纯同模型自我批评、带外部证据或确定性反馈的修复、以及把任务拆成多步的结构化工作流。三类的结果差异很大。**纯同模型、无新证据的自审，在数学与常识推理上没有稳定净收益，强模型也会把正确答案改错；而搜索结果、程序执行、测试用例、可靠 verifier 等能够提供模型原来不知道的新信息时，修复成功率明显更可靠。** Huang 等人在 ICLR 2024 的独立实验里，GPT‑4 在 GSM8K 上从初始 95.5% 经两轮无外部反馈自修降到 89.0%，GPT‑3.5 在 CommonsenseQA 上甚至从 75.8% 降到 41.8%；同一套实验一旦用真值判断何时值得修，性能反而上升，说明“知道哪里错了”比“再想一遍”更关键。citeturn6view0turn6view1

**目前最有说服力的正证据集中在“错误可被外部观测”的任务。** Reflexion 在 HumanEval 的一个 50 题困难子集上，单独加入 self-reflection 从 0.60 降到 0.52，只有测试生成和 reflection 同时存在时才升到 0.68；CRITIC 在开放域问答中，拿掉搜索工具后增益大幅缩小甚至消失；代码自修研究也发现，更准确的外部 critic 和人工反馈明显优于同模型自反馈。citeturn4view5turn10view1turn9view0turn12view1

**对“少漏抽”最相关的直接证据，其实不是 Self‑Refine，而是任务分解。** ChatIE 用同一个 ChatGPT，把一次性抽取拆成“先识别存在什么类型，再按类型逐项抽取”，六个中英文 IE 数据集平均 F1 比单轮 prompt 高 16.65 个百分点；但提升极不均匀：两个关系抽取数据集分别提高约 60.2 和 30.1 点，而两个 NER 和两个事件抽取数据集只提高约 1.1–3.3 点。它说明**复杂候选空间的分解可能显著减少遗漏，但并不能证明“生成后让模型反思”有效**，而且没有等 Token 预算控制。citeturn19view0

**“多给 Token 就能让弱模型追上强模型”也只能有条件成立。** ICLR 2025 的 test-time compute 工作在经过专门 revision/verifier 训练的 PaLM 2 模型和 MATH 上发现，容易到中等难度问题可以用额外推理算力超过约 14 倍参数量的大模型，但最难题几乎不随 test-time compute 改善；实验用于分析的题目难度还依赖大量采样和真值信息，作者明确说部署时这部分成本尚未解决。citeturn15view0

因此，对你真正关心的“中文小说长文抽取补漏”来说，现阶段证据支持的是一个更窄的命题：

> **有独立、可观测的错误信号，或者能把一个大候选空间拆成多个小而明确的覆盖任务时，多轮有较可信的净收益；只是让同一个模型重新看自己的答案并自由修改，没有足够证据证明能稳定降低漏抽，反而存在自我确认、正确改错、过度修改和错误放大的实证风险。** citeturn6view0turn10view1turn19view0turn22view4

## 比较口径与证据强弱

这类论文最容易出现的错觉，是把“一次调用”和“六七次调用”直接比较，然后把所有差值都叫作 reflection 的收益。真正有解释力的比较至少要控制四件事：模型能力、输入可见信息、输出任务合同，以及总推理预算。现有知名工作里，能同时做到的并不多。Self‑Refine、Reflexion、CRITIC、ChatIE 都提供了有价值的端到端结果，但它们分别加入了反馈 prompt、历史轨迹、搜索/执行工具、任务分解等新变量，因此不能把全部提升归因给“重新思考”。citeturn3view0turn4view4turn10view1turn19view0

我按这个标准把核心证据分成下面几档：

| 研究 | 状态与任务 | one-shot 可比性 | 关键实证 | 这项证据真正能说明什么 |
|---|---|---|---|---|
| **Self‑Refine** | NeurIPS 2023；7 类生成/推理任务 | 同底模，但反馈和修订增加调用、上下文与 Token；没有严格等 Token 主实验 | 情感、约束生成、代码等明显升；GSM8K 几乎不升 citeturn4view0turn4view1 | 某些任务能用迭代 prompt 改善输出；不能隔离“reflection”贡献 |
| **Huang et al. self-correction** | ICLR 2024；GSM8K、CSQA、HotpotQA | 同模型、同题，明确测多轮；额外调用仍非等 Token one-shot | 无 oracle 时 GPT‑3.5/GPT‑4 多数下降；oracle 指导时上升 citeturn6view0turn6view1 | **纯 intrinsic self-correction 不可靠；错误定位信号很关键** |
| **Reflexion** | NeurIPS 2023；代码、QA、交互环境 | 多轮可看到 evaluator、测试、环境反馈 | HumanEval Rust 消融中 reflection alone 0.60→0.52，测试+reflection 0.68 citeturn4view5 | 正收益不能归给“自省”；测试反馈与修复配合才有价值 |
| **CRITIC** | ICLR 2024；QA、程序化数学、毒性控制 | 同模型，但工具版获得搜索/执行等额外信息 | QA 中去掉工具后增益大幅缩水；text-davinci 平均甚至近零 citeturn9view0turn10view1 | **外部 grounding 是主要收益来源之一** |
| **ChatIE** | arXiv 预印本；RE/NER/EE，6 个中英文数据集 | 同 ChatGPT，但单轮与两阶段 prompt/合同不同，无等 Token | 平均 +16.65 F1 点，主要来自 RE citeturn19view0 | 多轮任务分解对复杂抽取有直接证据，但不是 self-repair |
| **Olausson et al. self-repair** | ICLR 2024；HumanEval、APPS | 明确比较样本预算，并另外提出按程序+反馈 Token 计费的 pass@t | 算上反馈成本后优势明显缩小；强 critic/人工反馈更有效 citeturn12view2turn12view3turn12view1 | 是目前对“多轮是否只是多花 Token”控制较好的研究之一 |
| **Snell et al. test-time compute** | ICLR 2025；MATH | 明确控制 generation budget，并做 FLOPs-matched 比较 | 策略随题目难度而变；最难题额外算力帮助很小 citeturn15view0 | 多算力可有效，但“顺序修订”并非始终优于独立重采样 |
| **RARR** | ACL 2023；事实性文本修订 | 有额外 Web 检索，因此不是 intrinsic 对比 | 检索证据后修改可提高 attribution，同时尽量保留原文 citeturn22view0 | 证明 retrieval+revision 有价值，不证明 self-reflection 有价值 |
| **Pride and Prejudice** | ACL 2024；翻译、约束生成、数学 | 专门研究多轮 self-refine 的评价偏差 | 六种 LLM 均发现 self-bias；自修可让模型更确信自己改善而真实性能未同步改善 citeturn22view4turn22view5turn22view6 | **同模型既写又判存在系统性风险** |

这里有两个特别重要的预算问题。

一个是 **“调用次数相同”仍不等于“预算相同”**。多轮方案会把上一轮答案、critic 文本、搜索结果、测试日志重新塞回上下文，输入 Token 往往也大幅增长。Olausson 等人为此专门提出 pass@t，把程序生成和反馈 Token 一起计入；按这种口径算后，自修相对独立采样的优势变得“modest”，而不是简单的巨大提升。citeturn12view2turn12view3

另一个是 **独立重采样本身就是非常强的 test-time baseline**。Huang 等复现 multi-agent debate 时，同一 gpt‑3.5‑turbo‑0301 在 GSM8K 上，标准单次为 76.7%；6 个回答预算下 debate 为 83.2%，但简单 self-consistency 为 85.3%；9 个回答时 debate 83.0%，self-consistency 88.2%。因此“多 agent 比 one-shot 高”并不能说明 agent 讨论本身有效，因为同样多生成几份独立答案再选择可能更好。这个实验仍未严格等输入 Token，但至少控制了回答数量。citeturn6view2

## 同模型自审为什么最不稳定

Self‑Refine 是正面结果最常被引用的一篇。它固定底层 LLM，让同一个模型依次负责生成、反馈和修订，在 sentiment reversal、dialogue、代码优化、代码可读性、GSM8K、acronym、constrained generation 七类任务上实验；其中情感转换、约束生成、代码任务有明显提升，但 GSM8K 基本没有：GPT‑3.5 为 64.1→64.1，ChatGPT 74.8→75.0，GPT‑4 92.9→93.1。作者还观察到，在数学题上 ChatGPT 有约 94% 的情况直接认为现有解答没有问题，因此根本没有识别出可修错误。citeturn3view0turn4view0turn4view1

这篇论文自身已经暴露了一个关键失败边界：在代码优化和数学的 70 个成功/失败案例人工分析里，失败反馈中约 33% 找错了错误位置，61% 给出了不合适的修复建议，只有约 6% 属于“critic 说对了但 refiner 没执行好”。也就是说，在那些失败样本上，瓶颈主要不是“模型不会改”，而是**模型不知道该改哪里、改成什么**。citeturn3view0

它对弱模型也没有显示“多轮自然补偿模型能力”。Vicuna‑13B 甚至难以稳定生成要求的反馈格式；作者给它人工设定的反馈后，它仍会重复原答案或产生与任务无关的内容。这与后续“小模型需要强 verifier”的工作方向是一致的：弱模型没有自动获得一个比自己更可靠的内置 critic。citeturn3view0turn4view3

更麻烦的是，Self‑Refine 部分收益经不起更强 one-shot prompt。Huang 等独立复现其 constrained generation 实验后发现，原 one-shot 约 53% coverage、Self‑Refine 约 61.1%；可是只把初始 prompt 明确写成必须覆盖 **全部** concepts，单轮直接达到 81.8%。在这个更强起点之后继续运行 Self‑Refine，反而下降到 75.1%。这不是说 Self‑Refine 整篇论文无效，而是说明其中至少一部分“迭代收益”其实可能来自后续反馈 prompt 补上了初始 prompt 没说清楚的任务要求。citeturn6view2

同一篇 ICLR 2024 工作把这个问题扩展到推理任务。GPT‑4 的 GSM8K 从 95.5 降至 91.5、再到 89.0；CommonsenseQA 从 82.0 降至 79.5、80.0；HotpotQA 从 49 降至 49、43。GPT‑3.5 在 CommonsenseQA 上的下降更剧烈，从 75.8 到 38.1，再到 41.8。作者发现“正确→错误”的修改次数可以高于“错误→正确”，也展示了模型把一个正确常识答案经过所谓 review 改错的案例。citeturn6view0turn6view4

而当实验允许一个 oracle 根据真值判断当前答案是否值得修时，同样的模型会明显改善：GPT‑3.5 在 GSM8K 从 75.9 到 84.3，CommonsenseQA 从 75.8 到 89.7；GPT‑4 的 HotpotQA 从 49 到 59。这里最合理、同时也最保守的解释不是“reflection 突然有效”，而是**可靠的错误检测改变了修复的精确率**；论文没有证明真实部署中模型自身可以获得等价 oracle。citeturn6view0

ACL 2024 的 *Pride and Prejudice* 给出了另一个独立反例。作者检查 GPT‑4、GPT‑3.5、Gemini、LLaMA2、Mixtral、DeepSeek 等六种模型，在翻译、约束文本生成和数学推理上发现 self-bias 普遍存在：随着迭代，模型对自身输出的评价看起来越来越高，但参考指标和人工评价并没有同步变好。论文在 CommonGen 上甚至画出了“模型估计的 coverage 持续上升、真实 coverage 很快饱和”的分离现象；人工标注也确认十轮后 bias 显著扩大。citeturn22view4turn22view5turn22view6

图示说明（原下载附件未随 Markdown 一同取得）：ACL 2024 的实验中，模型自估 coverage 持续提高，而真实 coverage 很快饱和；数学任务中的自偏差也随迭代上升。

这直接影响 LLM-as-judge。Panickssery 等进一步发现，GPT‑4、Llama 2 等模型能够以高于随机的水平识别哪些文本像是自己生成的，而且 self-recognition 能力与 self-preference 强度相关；也就是说，让同一模型一边生成、一边给候选打分，不是一个天然中立的验证器。citeturn14search2

因此，**“两个模型同意”“critic 给高分”“修改后模型更自信”都不是正确性的代理变量。** Self‑Refine 的多轮偏好、self-judge 的分数或者候选间一致性，除非最终能落到独立人工标注、真值指标、搜索证据、执行器或测试上，否则都不足以证明端到端错误率真的下降。citeturn22view4turn14search2turn6view2

## 外部 critic、verifier 和检索为什么更可信

CRITIC 是区分“自我反思”和“获得新证据”最干净的论文之一。ICLR 2024 的实验覆盖 AmbigNQ、TriviaQA、HotpotQA、程序化数学任务和毒性控制，用 text-davinci-003、ChatGPT 以及 LLaMA‑2 7B/13B/70B 等模型，让 critic 可以调用搜索引擎或执行器。三个 QA 数据集各取 500 个样本，最多修三轮，并专门做了 **CRITIC without Tool** 消融。citeturn10view0turn10view1

结果非常说明问题。以 ChatGPT 为例，AmbigNQ F1 从 64.3 升到 74.9，但不使用工具只有 67.3；HotpotQA 从 42.8 升到 52.9，不用工具只有 46.1；TriviaQA 从 79.2 到 81.7，不用工具只有 79.9。对 text-davinci-003，作者汇总的纯模型 critic 平均 F1 变化约为 −0.03，而接入工具的 CRITIC 平均提高约 5.6；ChatGPT 分别约 +2.33 和 +7.7。citeturn10view1turn9view0

程序化数学也呈现类似但没那么整齐的趋势：执行反馈往往进一步提升效果，不过个别数据集纯 critic 也能有所改善，因此不能把论文归纳成“所有收益都来自工具”。作者自己的结论更谨慎：没有可靠外部反馈时，自我 critique 的能力有限且不稳定；前两三轮已经获得大部分收益，之后边际收益快速下降。citeturn9view0turn10view2

Reflexion 的消融甚至更直观。它常被描述成“让 agent 反思就会学习”，实际上系统里还有 evaluator reward、环境轨迹、测试或执行反馈和记忆。HumanEval 的 Rust 困难子集只有 50 个题，但这个小实验非常有诊断价值：base 为 0.60；只有 self-reflection 是 0.52；只有 test generation 是 0.60；两者一起才达到 0.68。**这里 reflection 本身是负贡献，可靠测试信号与定向修改组合后才变成正收益。** citeturn4view4turn4view5

弱模型也不会因为这套循环自动追上强模型。Reflexion 在 HumanEval Python 上用 StarChat‑Beta，baseline 和 Reflexion 都是 0.26，没有改善。citeturn4view6

SCORE 则专门研究“小模型如何自修”。论文在 Llama‑2‑13B‑Chat、Gemma‑7B‑IT 等 ≤13B 模型上训练一个 refiner；当使用 GPT‑4 作为 verifier 时，五个数学/常识数据集平均比原模型高约 14.6%。但这里有两个很大的限定：refiner 的训练数据生成阶段用到了正确解答作为 hint，并根据正确答案筛选 critique；推理时 verifier 也可以是 GPT‑4。它因此证明的是“**弱生成器 + 经过训练的修复器 + 强验证器**可以显著改善”，而不是“弱模型靠自己反思就能追上强模型”。citeturn13view0turn13view1

论文自己的弱 verifier 消融也支持这个判断。在 Llama‑2‑13B 的 GSM8K dev 上，初始 39.4，使用其设计的 self-verifier/refiner 流程只有约 40.2，而 oracle verification 能到 49.5；不同 critique 粒度甚至还会更差。部分阈值又是在开发集上调的，因此这些数字不能当作未见测试集上的普适增益。citeturn13view2turn13view3

RARR 是“检索后重写”的另一类证据。ACL 2023 的系统不是让模型凭记忆重新想，而是针对初始文本产生研究问题、Web 搜索证据，再修改不受支持的内容。作者在多种生成任务和模型输出上发现 attribution 显著改善，并特别优化了“尽量少破坏原文”。因此它是 retrieval‑augmented repair 的正证据，但因为修订阶段可以看到 one-shot 没有的外部证据，绝不能拿它来证明“多轮思考优于一次生成”。citeturn22view0

这几组结果放在一起，外部验证方式的证据强弱大致可以这样理解：

| 验证来源 | 已有实证中的典型效果 | 主要失败边界 |
|---|---|---|
| **同模型自由自审** | 最不稳定；推理任务有明显负结果 citeturn6view0turn22view4 | 同错、自我确认、把正确答案改错、评分自偏差 |
| **更强/独立 LLM critic** | 可显著提高修复率，特别是弱生成器 citeturn12view4turn13view0 | 提升可能只是用了更强模型；critic 自己仍会错 |
| **搜索/检索证据** | QA、事实性改写效果较稳定 citeturn10view1turn22view0 | 检索错、证据冲突、检索成本；不能验证未被检索到的信息 |
| **程序执行/测试** | 代码和可执行数学中证据最强 citeturn4view5turn10view2 | 测试覆盖不足会把“通过测试”误当“正确” |
| **人工 critic** | 质量最高的直接对照之一 citeturn12view1 | 成本和时延高，论文通常没有做同预算经济比较 |

这里尤其不应把“独立 critic”简单理解成“换另一个模型就行”。现有最漂亮的正结果往往同时改变了 critic **能力或信息条件**：例如 GPT‑4 批评 GPT‑3.5、InstructScore 可以看到参考答案、CRITIC 可以搜索或执行。因此，目前没有足够独立证据证明：**两个同等级、都没有外部真值的 LLM 互审，在严格等 Token 条件下会稳定优于一个 LLM 多采样。** citeturn12view4turn13view1turn22view7turn6view2

## 抽取、补漏和长文场景的直接证据

和你的目标最接近的论文里，ChatIE 很重要，因为它真的测了结构化信息抽取，而不是把数学 benchmark 当代理。它把 IE 变成两阶段、多轮 QA：关系抽取先判断哪些 relation type 存在，再针对每种关系取实体对；NER 先判断存在哪些实体类型，再逐类抽实体；事件抽取先判断 event type，再抽 argument。六个数据集包含中文 DuIE2.0、MSRA、DuEE1.0，以及英文 NYT11‑HRL、CoNLL++、ACE05。citeturn19view0

最有价值的不是“平均 +16.65”这个 headline，而是分任务看：

| 数据集 | 任务 | 单轮 F1 | ChatIE F1 | 差值 |
|---|---:|---:|---:|---:|
| DuIE2.0 | 中文关系抽取 | 10.7 | 70.9 | **+60.2** |
| NYT11‑HRL | 英文关系抽取 | 7.4 | 37.5 | **+30.1** |
| MSRA | 中文 NER | 53.7 | 55.8 | +2.1 |
| CoNLL++ | 英文 NER | 49.8 | 52.9 | +3.1 |
| DuEE1.0 | 中文事件抽取 | 68.7 | 72.0 | +3.3 |
| ACE05 | 英文事件抽取 | 13.2 | 14.3 | +1.1 |

这些数值来自同一主表。citeturn19view0

这个分布很有启发：**多轮的巨大收益集中在候选关系类型和实体组合都比较复杂的 RE；已经相对容易一次完成的 NER/EE，额外轮次只带来几个点。** 这更像“搜索空间分解”而不是“自我反思”。而且两个版本使用的 prompt 并不具有同一输出合同：单轮要求一次交付完整结构，ChatIE 则先把一个困难大问题变成一系列更窄的问题，所以它不满足严格的“只改变是否迭代”消融。citeturn19view0turn19view2

它还有一些复现友好的材料：作者测试了五种 NER prompt wording，在随机 100 样本上 F1 波动较小；又做了 3 组经实体替换的 100 样本数据来检查潜在训练泄漏，平均 F1 从原数据的 46.13 降至 45.01，仍保持相对基线优势。代码仓库也公开。另一方面，最早主实验依赖 2023 年早期 ChatGPT 的在线版本，论文自己也因为模型版本变化重新跑了 gpt‑3.5‑turbo‑0301，这使今天逐数复现原表受到模型漂移限制。citeturn19view1turn17search8

但它仍然不能直接回答长小说中的**跨句因果、代词指代、时间关系、长距离事件合并**。ChatIE 的形式化和示例都是以单个 sentence 为主要输入单位；它没有把“跨几十页保持人物身份、事件链和漏抽率”拆出来做消融。citeturn19view0turn19view1

GraphRAG 经常被拿来支持 “gleaning 会补漏”，但论文证据没有这么强。微软的 GraphRAG 技术报告在知识图构建时确实使用 entity/relation extraction，并在 Podcast 数据上配置了 **1 次 gleaning**，News 数据上则是 **0 次 gleaning**；可是主论文目标是 query-focused summarization，比较的是全局问答质量，而且对没有真值的 broad questions 使用 LLM-as-a-judge。论文没有给出一个“同模型、同数据、0 gleaning vs 1/2/3 gleaning 的实体/关系 gold recall”主实验。citeturn16search2turn22view1

所以对 gleaning 最稳妥的判定是：**它是已部署工作流中的候选补漏机制，不是已经通过独立 extraction recall 消融证明的规律。** 特别是 GraphRAG 本身又使用 LLM judge，而前述研究已经证明 LLM judge 存在 self-preference/self-bias，因此不能把下游 judge 分数反推成“上游实体漏抽更少”。citeturn22view1turn14search2turn22view4

DocETL 对长文更接近真实工程。它让 agent 自动搜索不同文档处理计划，可组合 document chunking、header lineage、summarization、map-stage gleaning、duplicate-key resolution 等 rewrite；在四类非结构化文档分析任务中，作者报告优化计划比基线高约 21%–80% 的准确度。citeturn16search3turn20search14

但这里同样不能把差值归给 gleaning。一项案例里的最终优化计划同时用了 chunking、header context、summarization、gleaning 和 duplicate resolution；优化器评估了 200 多个 pipeline variant，优化阶段约花 100 美元、20 分钟，而真正处理 227 份样本文档的一次 pipeline 运行只有约 0.55–2.24 美元。也就是说，它证明的是**自动搜索一整个长文 pipeline 有可能值回成本**，不是“再问一遍有没有遗漏”单独贡献了多少。citeturn22view2

因此，截至这轮调查，针对下面这些更贴近中文小说的能力，证据依然应该标成 **未知或不足**：长距离人物指代后的补漏、跨章节事件共指、隐含因果、相对时间换算、同一事件的多次提及合并、先正向抽取再反向按角色/事件类型扫描的 recall 提升。现有直接 IE 证据主要是句级 ChatIE；长文证据主要来自多机制混合的 GraphRAG/DocETL，而不是可归因的 one-shot vs reverse-covering 消融。citeturn19view0turn22view1turn22view2

## 代码修复和 test-time compute 给出的预算答案

代码是目前最适合研究 iterative repair 的领域，因为错误可以被编译器、单元测试和执行器相对客观地观测。Olausson 等 ICLR 2024 的 *Is Self-Repair a Silver Bullet for Code Generation?* 特别有价值，因为它没有只报告“修一次之后 pass@1 上升”，而是把独立采样作为主要竞争基线，并讨论生成反馈本身的 Token 成本。实验使用固定版本的 GPT‑3.5、GPT‑4 和 CodeLlama‑13B‑Instruct，在 HumanEval 和随机抽取的 300 个 APPS 问题上构造较大的 repair tree。citeturn12view0

作者指出，传统 pass@k 如果只把一次 repair 当成“一份新程序”，却不计算中间 critic 文本，就会系统性高估修复方法的计算效率，因此又计算了 pass@t，把程序和 feedback token 一起算进去。按这个更公平的口径，多轮自修确实有一些收益，但比不计成本时小得多，而且依赖题型和反馈质量。citeturn12view2turn12view3

更关键的是 critic 能力消融。APPS 上 CodeLlama‑13B 自修的 repair success 约 1.1%，给它 GPT‑3.5 critic 后约 2.2%；GPT‑3.5 自修约 4.7%，换 GPT‑4 critic 约 11.5%。HumanEval 上 CodeLlama 自修约 9.1%，GPT‑3.5 critic 可到 20.1%；GPT‑3.5 自修约 22.4%，GPT‑4 critic 可到约 39.3%，而 GPT‑4 自修自身约 49.6%。所以**强 critic 可以让弱模型明显接近强模型，但没有证据显示它普遍消除了生成器能力差距。** citeturn12view4

人工对照更能说明问题。研究者抽取 80 个案例比较 GPT‑4 自反馈与人类反馈：GPT‑4 的反馈有 32/80 被判不准确，人类只有 7/80；使用人类反馈后，总体 repair success 大约是 GPT‑4 自反馈的 1.58 倍。作者还观察到人类更常给高层修复建议，并会表达不确定，而 GPT‑4 critic 在该实验中几乎不会这样做。citeturn12view1

这也是对“修复器不能顺便当验真器”的很强实证支持：一个模型可以非常流畅地给出修改建议，却并不意味着建议的错误定位是准确的。论文的官方代码和结果数据已公开，仓库后来被归档但仍可读取和复跑分析脚本；涉及人类实验的原始数据因 IRB 没有全部公开。citeturn12view5

在真实代码库上，Agentless 又提供了另一个很重要的反例：**更长、更自主的 agent trajectory 并不天然更好。** 它刻意去掉复杂自主 agent loop，只保留 localization → repair → patch validation 三阶段，并用 regression tests 和生成的 reproduction tests 选最终 patch。在 SWE-bench Lite 的 300 个问题上，论文版本报告 96 个修复、32.0%，平均约 0.70 美元；在当时公开可复现的 open-source 方法里表现最高或非常有竞争力。citeturn22view3

这项实验并不是严格的“一次生成 vs 多轮修复”消融，所以不能说 Agentless 证明 agent loop 无效。它能支持的更窄结论是：**把算力放在明确的定位、候选生成和确定性验证上，完全可能优于让 LLM 自由决定下一步做什么。** citeturn22view3

test-time compute 的系统研究进一步解释了原因。Snell 等 ICLR 2025 在 MATH 上把额外推理分成两个方向：一类是顺序 revision，另一类是产生更多并行候选再由 verifier 搜索/选择。论文明确按 generation budget 比较，并计算 lookahead 等搜索额外消耗，属于现有文献里预算控制较严的一篇。citeturn15view0

结果没有出现“多轮越深越好”这种简单规律。容易问题因为初始答案已经接近正确，连续 revision 往往比完全重新采样更划算；困难问题更需要探索不同解法，并行 sampling 或 verifier search 更合适；最难的 difficulty bin 中，无论怎么增加 test-time compute 都几乎没有实质进展。Beam search 在容易题上甚至随着预算增加出现对 verifier 的过度优化，性能反而下降。citeturn15view0

论文用自适应策略可以在一些条件下以约四分之一的 generation budget 达到或超过 best-of-N，并在 FLOPs-matched 的特定设置里让小模型超过约 14 倍参数量的大模型。但这不是“普通弱模型靠多想几遍追上强模型”：使用的 PaLM 2 模型专门为 revision/verifier 能力做过 fine-tuning，而且分析阶段的题目难度最初通过每题最多 2048 个样本和真值估计；作者明确承认部署时准确估难度本身需要算力，这部分没有完整计入主结论。citeturn15view0

所以在固定预算下，更准确的工程描述不是“one-shot 还是 iterative 二选一”，而是：

> **容易、可局部修的问题适合定向 revision；不知道错在哪的问题更适合独立重采样增加探索；有可靠 verifier 时可以搜索候选；连 verifier 和生成器都无法识别正确方向的极难问题，多轮往往只是增加成本。** citeturn15view0turn12view2

## 复现状态、证据缺口与对目标任务的实际含义

同行评审证据和预印本最好分开看。Self‑Refine 与 Reflexion 均进入 NeurIPS 2023；CRITIC、Huang 等关于 intrinsic self-correction 的负结果、Olausson 的 code self-repair 均为 ICLR 2024；RARR 为 ACL 2023；*Pride and Prejudice* 为 ACL 2024；Snell 等 test-time compute 工作进入 ICLR 2025。它们构成这轮最可靠的核心证据层。citeturn2search2turn0search1turn22view0turn22view4turn14search1

ChatIE、GraphRAG、DocETL 以及本轮引用的 SCORE 版本，我这里按检索到的预印本/技术报告证据处理，不把它们和前述顶会论文当成同等独立复现。尤其 GraphRAG 和 DocETL 更像完整系统评估：它们同时改变多个 pipeline 组件，能证明“整个系统可能更好”，却不适合作为某一个补漏步骤的因果证据。citeturn17search0turn22view1turn22view2turn13view0

开源情况相对好的包括 Self‑Refine，其官方仓库提供任务代码、数据目录和 Colab；ChatIE 有公开仓库；Olausson 的 self-repair 仓库包含代码、结果数据和复现图表的脚本；ACL 2024 的 self-bias 工作明确公开代码与数据。citeturn3view2turn17search8turn12view5turn22view4

但“有代码”不等于能逐数复现。Self‑Refine、ChatIE、CRITIC 等使用了会更新的商用 API 或 Web 搜索；CRITIC 因此特意缓存 API/search 结果，ChatIE 也直接记录早期 ChatGPT 版本变化对结果的影响。模型 endpoint、搜索结果、系统 prompt 和服务端解码变化，都可能让今天的绝对分数与论文不同。citeturn10view1turn19view0turn19view1

对于你这次真正要决定的路线，我认为可以把证据浓缩成下面这张判断表：

| 路线 | 当前实证判断 | 对“减少漏抽”的可信度 | 最大风险 |
|---|---|---|---|
| one-shot 强 prompt | **必须作为强基线** | 高 | prompt 本身若遗漏 coverage 条件，会人为做弱 baseline citeturn6view2 |
| 同模型“请检查并修正” | **不应默认启用** | 低 | 正确改错、自我确认、同错 citeturn6view0turn22view4 |
| 同模型按明确维度逐项复查 | **有条件值得实验** | 中等、未充分验证 | 多出的维度提示本身可能才是收益来源 citeturn6view2turn19view0 |
| 先类型/角色，再逐项抽取 | **抽取领域直接正证据最好** | 中等偏高 | 更多调用；收益在不同 IE 类型差异极大 citeturn19view0 |
| 搜索/检索后定向修复 | **事实性任务有稳定正证据** | 对证据可检索事实较高 | 检索不到的信息仍无法验证 citeturn10view1turn22view0 |
| 程序/Schema/测试校验后修复 | **最可信的多轮路线之一** | 对可机械检查错误高 | validator 覆盖范围就是上限 citeturn4view5turn12view1 |
| 更强独立 critic | **常有明显提升** | 中高 | 成本高，而且可能只是“用了更强模型” citeturn12view4turn13view0 |
| 同级多模型互审/投票 | **证据不足以证明优于等预算采样** | 低到中 | 共识不等于真值；同类模型可能共享错误 citeturn6view2turn14search2 |
| gleaning / “还有遗漏吗” | **候选路线，尚缺干净消融** | 未知 | GraphRAG 主论文没有直接 gold-recall 证明 citeturn16search2turn22view1 |
| 长文 agentic optimizer | **整体系统有正结果** | 中等 | 多组件混合，优化成本高，难归因 citeturn22view2 |

🔥 **对中文小说抽取，现阶段最不能跳过的一项实验，不是“one-shot vs self-reflection”，而是把预算拆开。** 一个合理的复现设计至少应同时放入：强 one-shot、等总输出 Token 的独立多采样、同模型自审、按候选类型/角色的定向二次扫描、独立 critic、以及确定性校验后只修失败项。否则只要多轮方案多看到一份类型清单、多拿了几倍 Token、或者 critic 是更强模型，就无法知道提高 recall 的究竟是哪一部分。这个判断直接来自 Self‑Refine 强 prompt 复现、ChatIE 的任务分解结果、Olausson 的 pass@t 成本分析和 test-time compute 的等预算结果。citeturn6view2turn19view0turn12view2turn15view0

如果最终指标是“**在不显著牺牲 precision、证据承托和结构合法性的情况下，多找回多少真实遗漏**”，那么当前论文没有给出一个可以直接套用到中文小说的预期增益百分比。最接近的 ChatIE 是句级 IE，而且主要提升关系抽取；GraphRAG 的 gleaning 没有独立 gold-recall 消融；DocETL 把多种优化混在一起；self-reflection 在独立推理复现中又存在明确负结果。citeturn19view0turn22view1turn22view2turn6view0

因此，证据支持的优先级不是“多轮 > one-shot”，而更接近：

**强 one-shot 基线 → 明确覆盖维度的独立扫描 → 用可独立验证的信号判定候选错误 → 只对失败项做定向修复 → 修复后重新验证。**

这里每一个箭头都应该单独做消融；尤其不能让“负责提出修复的模型”同时成为唯一的“修复已正确”的裁判。现有最可靠的论文结果，恰恰是在搜索、程序执行、测试、人工标注或独立真值把这两个角色分开时出现的。citeturn10view1turn4view5turn12view1turn22view0

来源：ChatGPT
