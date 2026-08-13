# Tiny SFT：为什么 24 条就能迁移到未见 24 条？MICRO24 更像“学规则”，还是小数据偶然？

## 结论先放前面

按你给出的结果，我的判断是：

> **MICRO24 已经给出了相当有价值的“任务行为迁移”证据，但还没有给出“模型学会了一个全新的语义能力”的证据。**

更准确地说，这个现象最像：

**预训练 / instruction model 原本就有阅读、实体识别、指代解析、关系理解、信息抽取这些底层能力；24 个高信息量 SFT 样本把“你到底把什么算作一个 Fact、该怎么边界化、怎么输出、证据怎么算有效”写进了 LoRA adapter。**

也就是：

**已有语言能力 + 新任务协议/决策边界 + 持久的 behavioral steering（行为引导）**。

这与 LIMA 的“少量 SFT 更多是在告诉强预训练模型该如何表现，而不是重新灌入知识”的结果非常吻合；LIMA 用 1,000 条精心选择的数据就让 65B LLaMA 学会特定输出形式，并迁移到训练中没有出现的任务。citeturn21view0 少样本参数高效微调的研究也已经证明：对一个已经很强的预训练模型，任务适配并不一定需要大规模数据。T-Few 一类方法甚至在未见任务上的 few-shot setting 中，能优于纯 in-context learning。citeturn6view1

但这里有一个非常关键的缺口：

**你现在给了 A_FULL 在 DEV24 上的 76.92%，却没有给出同一 evaluator、同一 prompt、同一 decoding 下 Qwen3-4B 原始 checkpoint 的 DEV24 分数。**

所以目前还不能仅凭 76.92% 说：

> “24 条训练数据让模型获得了 76.92% 的能力。”

真正应该看的量是：

\[
\Delta F1=F1_{\text{A\_FULL}}-F1_{\text{BASE}}
\]

如果 BASE 已经有 70%，那么 24 条 SFT 主要是输出校准；如果 BASE 只有 20%–30%，A_FULL 到 76.92%，那就是非常强的任务学习/任务激活证据。

### 你要的 A–G，我先直接给判断

| 问题 | 我的判断 |
|---|---|
| **A. 24 TRAIN + 24 DEV 能证明什么？** | 能证明：在排除泄漏的前提下，模型不是简单逐字背 TRAIN；它至少把某种任务行为迁移到了未见文本。不能证明：学到了普适规则、产生了全新能力、能迁移到真实小说，也不能精确证明总体 F1 就是 76.92%。 |
| **B. 为什么 24 条能有明显迁移？** | 因为 4B instruct model 不是白纸；真正新学的很可能只是一个很窄的“任务协议”和语义边界。24 case 里还有 43 个 facts、很多 supervised tokens，并不是只有“24 个信息点”。 |
| **C. 怎么排查泄漏 / evaluator 偏差？** | 最关键的是 BASE、ICL、shuffled-label、template-counterfactual、独立生成器 Set C、人工复核 evaluator 六组控制。 |
| **D. 下一批加什么？** | **不要单纯加数量。**优先加新的决策边界 / fact coverage，其次是 minimal pairs + hard negatives，再加真实小说式语言风格；单纯把现有模板改名字扩到 48，信息增量最低。 |
| **E. 进入真实小说前还加多少 synthetic？** | **我建议只再加 24 条，做到 TRAIN48 就开始真实小说 pilot。**只有 TRAIN48 明显继续改善时，才考虑把 synthetic 扩到 96。 |
| **F. Blind Set C 多大？** | **推荐 96 个独立 case；论文级/强结论最好 192。**按 case 做 bootstrap，不要把同一片段里的多个 facts 当完全独立样本。最终确认真实小说能力时，C 应来自真实目标分布。 |
| **G. 最省成本路线？** | **24 → 做控制实验 → +24 高信息 synthetic → 48 → 24–48 条真实小说 pilot → 冻结方案 → C96 一次性 blind test。**不建议先无脑做 96/500 synthetic。 |

🔥 **我认为你现在最值得追的不是“24 为什么这么神奇”，而是一个更精确的问题：这 24 条到底教会了模型哪一层东西？**

这个问题是可以用很便宜的实验拆出来的。

## 文献里，几十到几千条高质量数据到底能改变模型多少

少量 SFT 能产生大变化，并不是 MICRO24 独有的反常现象。过去几年的研究越来越指向同一个方向：**当底座已经足够强时，后训练数据的边际价值高度不均匀；一条覆盖新行为边界的数据，可能比几十条重复数据更有用。**

LIMA 是最直接的经典案例。作者只用 1,000 条精心策划的 prompt-response 对微调 65B LLaMA，就观察到了很强的 instruction following，并且模型可以从训练集里“少数几个例子”学会具体输出格式，还能迁移到未见任务。论文据此提出了后来非常有影响力的 “superficial alignment hypothesis”：大量知识和能力来自预训练，少量 alignment 数据主要告诉模型**应该怎样调用和表达这些能力**。citeturn21view0

这不能直接推出“24 条等于 1,000 条”，模型规模、任务宽度也完全不同。不过你的任务比 LIMA 的开放式聊天窄得多。因此，**24 条对于一个窄语义抽取规则，有可能已经覆盖了很大一部分有效任务空间。**

数据选择工作的结果更激进。LESS 不是把所有 instruction data 都喂给模型，而是利用少量代表目标能力的 examples，寻找训练梯度上最相关的数据；作者报告，选出来的 **5% 数据经常能超过完整数据集**，并发现有效数据相关的是需要的 reasoning skill，而不只是表面文字相似。citeturn21view1

AlpaGasus 也发现 Alpaca 的 52k instruction data 中存在大量低质量样本。过滤后只用约 9k 高质量样本训练，结果反而明显超过使用完整 52k 数据的 Alpaca，同时训练快约 5.7 倍。citeturn16search0turn16search6

所以，关于你问的：

> **24 个精心设计样本 vs 500 个普通样本，有没有研究？**

我没有找到一个与你的“4B + LoRA + 小说事实抽取 + 24 vs 500”完全 apples-to-apples 的实验。**目前不能引用论文直接说 24 一定胜过 500。**

但 LIMA、LESS、AlpaGasus 三条证据共同说明了一件相当稳的事：

> **在已经预训练好的模型上，SFT 性能不是训练样本数量的简单单调函数。高质量、相关、覆盖互补行为的数据子集，完全可能超过一个更大但重复、嘈杂的数据集。** citeturn21view0turn21view1turn16search0

这也是为什么你的 24 条不能只看成“24”。

### 一条训练 case 实际上提供了很多监督信号

你的 TRAIN 是：

- 24 个片段；
- 43 个 facts；
- 约 72 optimizer updates。

而 Transformer SFT 的 loss 是作用在目标序列里的很多 token 上，不是“一个 case 只贡献一个标签”。

比如某个训练样本同时告诉模型：

> 哪段文字属于事实 → 哪两个实体参与 → 哪类关系有效 → 哪些看似有关的内容不要提取 → evidence 边界在哪里 → 输出结构如何排列。

这是一组高度相关但信息密度很高的监督。

Distilling Step-by-Step 得到的一个重要结果就是：**给模型更有信息量的监督目标，例如额外 rationale，可以显著降低达到某个性能水平所需的数据量。** 它不是 MICRO24 同类型任务，但它说明“样本数”本身不是监督信息量的好代理。citeturn18search1

Self-Instruct 也不是简单无脑生成更多 synthetic examples。其流程会生成 instruction/input/output，再过滤无效或相似项目；用这种自生成 instruction 数据微调 GPT-3 后，在 Super-NaturalInstructions 上相对原始模型获得了 33 个百分点的提升，并能迁移到人工编写的新任务。citeturn14search0turn18search12

Phi-1 的 “textbook quality” 工作则从更大尺度证明了数据质量的力量：作者特意构造高质量、类似教材和练习的 synthetic data，而不是纯追求 token 数量。这个工作属于预训练/继续训练尺度，不能直接拿来解释 24-shot SFT，但它进一步说明**数据的信息结构和教学质量会大幅影响样本效率**。citeturn6view7

FLAN 的 instruction tuning 结果则从另一个方向说明为什么“覆盖”重要：随着参与 instruction tuning 的任务种类增加，模型对未见任务的 zero-shot 泛化会改善；自然语言 instruction、任务多样性和模型规模都是关键变量。citeturn11search0turn11search3

所以这里不能简单总结成“quality > quantity”。

更准确的是：

> **在小数据区间，边际新增样本有没有覆盖新的决策边界，往往比它让数据集从 24 变成 25 这件事重要得多。**

## 这次更像规则学习、task vector，还是已有能力被叫出来

我会把几种解释按当前证据强弱排成这样：

| 解释 | 当前可信度 | MICRO24 能否证明 |
|---|---:|---|
| **Behavioral steering / 持久任务规范** | 很高 | 基本符合 |
| **重新激活 pretrained 已有抽取能力** | 高 | 很符合，但需 BASE control |
| **学习了一部分新的任务规则 / ontology** | 中高 | DEV24 提供初步支持 |
| **ICL-like task specification** | 中 | 很好的类比，但不是同一机制 |
| **Task vector** | 中 | 参数空间上很像，机制上未证明 |
| **真正获得了以前没有的新 capability** | 低到中 | 目前证据远远不够 |

### 我最倾向的解释：旧能力，新协议

你可以直接理解成：

Qwen3-4B 大概率早就会：

> 读小说 → 理解谁做了什么 → 处理代词 → 判断句间关系 → 抽取文本 span → 输出结构化文本。

它以前不知道的是：

> **MICRO24 定义的“事实”究竟是什么。**

比如很多任务真正困难的地方并不是：

> “模型能不能理解小明去了医院？”

而是：

> “这在我们的 schema 里算不算一个 fact？”  
> “事实粒度应该切到哪里？”  
> “引用一句还是半句？”  
> “隐含关系算不算？”  
> “一句里两个事件是一个 fact 还是两个？”  
> “哪些东西虽然语义相关，但 evaluator 不认？”

这些都是**决策规则和接口约定**。

对于一个已经会中文、会小说理解、会抽取的模型，教会这层东西需要的数据量可能非常小。

LIMA 恰好支持这种解释：强模型的大部分知识已经在预训练阶段获得，少量 SFT 可以教会它以特定方式使用这些知识。citeturn21view0

### “像 ICL”是很好的直觉，但别把两者当成同一个机制

In-context learning，也就是把几个 demonstration 放进 prompt、不改权重，确实有研究发现模型内部会形成紧凑的 task representation。

Hendel 等人的 *In-Context Learning Creates Task Vectors* 发现，在多个任务里，ICL demonstrations 可以被压缩成一种内部 “task vector”，之后这个向量会调制模型执行相应任务。citeturn21view3 Todd 等人的 Function Vectors 工作也通过因果干预发现，一些 attention heads 携带了输入输出函数的紧凑表示，而且这些 function vectors 在脱离原 ICL 上下文后仍然能触发相应行为。citeturn15search3turn21view4

你的 Tiny SFT 在功能效果上很像：

> 24 demonstrations  
> ↓  
> 提炼任务定义  
> ↓  
> 新输入时继续执行

区别是：

**ICL 把任务信息临时存在 activation/context 里；你的 LoRA 是通过梯度把东西写进了参数增量。**

所以我会叫它：

> **persistent task specification，持久化的任务说明。**

而不是直接说“就是 ICL”。

### 它是不是 task vector？

这里容易把两个同名概念混起来。

一个是刚才说的 **ICL activation task vector**。

另一个是 Task Arithmetic 这一类工作里的**参数 task vector**：

\[
\tau=\theta_{\text{finetuned}}-\theta_{\text{base}}
\]

也就是微调前后参数之差。研究发现，有些这种 weight-space vector 可以进行加减、组合，从而增加、删除或组合特定任务行为。citeturn2search1

LoRA 本来就在学习低秩的参数变化：

\[
W'=W+\Delta W,\qquad \Delta W=BA
\]

其中原始模型参数被冻结，只训练低秩矩阵。LoRA 原论文证明，这种受限制的参数更新可以在大量 downstream task 上达到与 full fine-tuning 相近甚至更好的效果。citeturn18academia20

所以从几何角度：

**你的 LoRA adapter 完全可以被看成一个低秩 weight delta。**

但这还不能证明它具有论文里更强的 “task vector” 性质。

要这么称呼，我建议至少做下面一个非常便宜的实验：

\[
\theta(\alpha)=\theta_{\text{base}}+\alpha\Delta_{\text{LoRA}}
\]

测：

`α = 0, 0.25, 0.5, 0.75, 1.0, 1.25`

如果 Semantic Fact F1 随 adapter strength 呈现比较稳定的行为变化，而且没有同时造成大范围能力崩坏，那么“低维 behavioral direction”这个解释会更有说服力。

更狠一点可以测：

`α = -0.5` 或 `-1`

看行为是否朝相反方向变化。

这才开始接近 task-vector-style 的机制证据，而不是因为“它是 LoRA”就叫 task vector。

### True capability learning 的门槛应该很高

我不会因为 DEV24=76.92% 就说 Qwen “学会了全新的语义推理能力”。

真正的新 capability 应该出现这种情况：

1. Base zero-shot 做不到；
2. Base 加很明确的 instruction 还是做不到；
3. Base 加 few-shot ICL 仍明显做不到；
4. LoRA24 可以做到；
5. 新能力在**结构性 OOD** 样本上保持；
6. 改掉训练模板、词汇、人物、句式以后仍保持；
7. 甚至出现训练示例里没有直接展示的组合。

满足越多，才越接近“learned procedure/capability”。

目前 DEV24 已经完成了第一个重要跨越：

> **不是训练文本原样复现。**

但“人物、场景和表述不同”仍可能与 TRAIN 来自同一套生成逻辑、同一种事实 ontology、同一种叙事语法。所以它还不能把“规则学习”和“synthetic template family 泛化”分开。

## 怎么区分背模板、学规则、能力激活，以及排查数据泄漏

🔥 如果只能做一轮诊断，我建议你暂时**不要继续堆 96 条训练数据**，先跑下面这套控制。

它能比单纯再看一次 F1 告诉你更多东西。

### 最关键的对照不是更多 checkpoint，而是 BASE

应该至少得到这四条线：

| 模型 | DEV24 | 目的 |
|---|---:|---|
| `BASE + 普通 instruction` | ? | 原模型到底已经会多少 |
| `BASE + 3~8 个 ICL examples` | ? | 任务能不能只靠上下文学会 |
| `LoRA24` | 76.92 | 当前结果 |
| `LoRA24 + shuffled labels control` | ? | 改善是否真的来自语义映射 |

尤其是 **shuffled-label control** 很有价值。

把 TRAIN 的目标随机错配，例如：

> 小说 A → fact B  
> 小说 B → fact C

仍然保持输出格式完全合法。

如果这种训练还能在 DEV 上明显提高 Semantic F1，那就很可疑：

- evaluator 可能主要奖励格式；
- prompt 里可能泄漏答案；
- metric/parser 可能有 bug；
- 或底座本身已经贡献了绝大多数分数。

如果正常 24 条明显提升、随机标签完全不提升，这才说明**训练中的语义对应关系确实重要**。

### 检测 template memorization，最有效的不是普通 paraphrase

你现在已经做了“人物不同、场景不同、措辞不同”，很好，但还能更狠。

真正有杀伤力的是 **counterfactual minimal pair，反事实最小对照**。

也就是两个片段表面几乎一样，只改一个决定标签的语义因素：

> A：赵宁把钥匙交给了林夏。  
> B：赵宁本想把钥匙交给林夏，但最终没有交。

或者：

> A：医生告诉周岚，检查已经完成。  
> B：周岚猜测医生可能已经完成检查。

或者：

> A：她离开后，王启才收到信。  
> B：王启收到信后，她才离开。

如果模型学的是：

> “看到 `交给` → 提取 transfer fact”

它会在 hard negative 上翻车。

如果它真的学到了任务语义边界，A/B 应该产生不同结果。

**这种 1 对 minimal pair 的信息量，通常比再生成十个正常正例高得多。**

这与 LESS 的观察很一致：高价值数据的意义不是表面相似，而是是否包含目标任务真正需要的 reasoning skill。citeturn21view1

### 我建议专门造一套“破模板探针”

不用拿来训练，24 个就够，专门诊断：

**表面变、语义不变**

同一 fact 做：

- 主动 → 被动；
- 直接叙述 → 对话；
- 第一人称 → 第三人称；
- 明说名字 → 代词 / 指代；
- 顺叙 → 倒叙；
- 一句话 → 跨两三句表达；
- 直接陈述 → 含蓄表达。

这是测“语义不变性”。

**表面基本不变、语义改变**

做：

- 否定；
- 未遂；
- 假设；
- 梦境；
- 转述；
- 传闻；
- 错误信念；
- 时间先后逆转；
- 同样 trigger word，但关系不成立。

这是测“有没有走 lexical shortcut”。

第二类比第一类更重要。

### 怎么区分“规则学习”和“已有能力激活”

最干净的办法是测一个小的 factorial experiment：

\[
\text{BASE}
\rightarrow
\text{BASE + instruction}
\rightarrow
\text{BASE + ICL}
\rightarrow
\text{SFT}
\]

假设得到：

| 方法 | F1 |
|---|---:|
| BASE | 25 |
| +详细 instruction | 58 |
| +8-shot ICL | 73 |
| LoRA24 | 77 |

这种情况下，我会说：

> **主要是能力激活 + 任务持久化。**

因为不改参数就已经能到 73。

相反，如果：

| 方法 | F1 |
|---|---:|
| BASE | 20 |
| +详细 instruction | 24 |
| +8-shot ICL | 28 |
| LoRA24 | 77 |

而且 LoRA 在 minimal pairs / structural OOD 上仍然很强，那么“参数更新真正学习了新的决策程序”的证据就强很多。

还有一种很可能发生的情况：

| 方法 | F1 |
|---|---:|
| BASE | 50 |
| instruction | 55 |
| ICL | 65 |
| LoRA24 | 77 |

那就是混合型：

> **原模型已经具备抽取能力，SFT 又确实学到了 MICRO24 特有的 ontology / boundary policy。**

我觉得这是目前最可能的结果。

### 泄漏最容易发生的地方，可能不是 TRAIN→DEV 文本复制

因为 DEV 是原创文本，如果它们是在 Qwen3 预训练完成以后才创建的，那么“模型预训练见过这 24 篇原文”的可能性自然很低。

真正需要排查的是**pipeline-level leakage**：

| 风险 | 怎么查 |
|---|---|
| TRAIN/DEV 片段重复或近重复 | normalized n-gram + embedding nearest-neighbor |
| 人名换了，但剧情骨架相同 | 去掉实体名后再做相似度和人工检查 |
| 同一个 synthetic generator 总在重复固定句法 | 用独立 generator prompt / 不同生成模型造 C |
| TRAIN 和 DEV 用同一个 seed/template bank | 查 generation metadata |
| evaluator 读取了 gold/reference 字段 | 从 evaluation input 端彻底 audit |
| parser 对某种 evidence representation 特别宽松 | 人工逐项重算 10–20 case |
| checkpoint / evidence format 是看 DEV 后选的 | DEV 归为 validation，不能再叫 blind test |
| inference prompt 意外包含 TRAIN demonstration | 保存最终发送给模型的完整 prompt 并 hash/audit |

特别是你的：

- `C2_FULL ≈ 89.36%`
- `E_UNIT_QUOTE ≈ 86.60%`
- `D_RANGE ≈ 80.43%`

这些差异说明 **representation / evaluator interface 本身可能是相当大的变量**。

不一定有问题，但这意味着 Set C 之前应该把：

> evidence representation、normalization、matching rule、threshold、parser、checkpoint selection

全部冻结。

否则你不断在 DEV 上比较这些选项，实际上就是在对 DEV 做 hyperparameter optimization。

### 如果 evaluator 用了 LLM judge，要再多一层防护

LLM-as-a-judge 的研究已经发现 position、verbosity、自增强等系统性偏差；强 judge 与人类可以有较高一致率，但并不意味着没有方向性偏差。citeturn14search6

所以如果 Semantic Fact F1 里任何环节使用了 LLM judge，我建议抽至少 20–30 个 case：

> 两个人独立 blind adjudication → resolve disagreements → 和 evaluator 对比。

你真正想知道的不是“judge 和人平均相关不相关”，而是：

> **judge 会不会特别偏爱 A_FULL 使用的输出样式。**

如果 F1 完全是 deterministic set matching，那就不需要 LLM judge 这一步，但要重点 audit normalization 和 matching code。

## 为什么 TRAIN F1 和 DEV F1 会接近，甚至 DEV 更高

这件事**完全不需要反常解释**。

特别是在 `24 cases / 43–48 facts` 这种尺寸下，TRAIN > DEV 并不是必须发生的。

### TRAIN 可能就是更难

如果你的 24 TRAIN 是为了“教模型”而精心覆盖各种边缘情况，DEV 却是随机写的新小说，那么 TRAIN 可能含有更多：

- 边界情况；
- 罕见 fact；
- 多 facts 同句；
- 指代；
- 隐含语义；
- difficult negatives。

这样 DEV 比 TRAIN 高很正常。

这反而是我建议你未来**不要把 TRAIN performance 当主指标**的原因。

### SFT 优化的也不是 Semantic Fact F1

训练直接最小化的是 token-level prediction loss。

你最终看的却是：

> 解析生成结果 → 对齐 facts → 算 precision/recall → 算 F1。

两者不是同一个目标。

所以“训练 loss 更低”不等于“TRAIN Semantic F1 一定比 DEV 高”。

### 24 case 的随机波动非常大

这一点特别容易被百分数的两位小数遮住。

`76.92%` 看起来很精确，但 DEV 只有：

- 24 passages；
- 48 facts。

24 个 case 里，一个 case 就占：

\[
1/24=4.17\%
\]

如果粗暴把表现想象成 Bernoulli accuracy，并以约 77% 的命中率做量级估计，那么 95% 波动范围大概是：

| 独立 case 数 | 粗略 95% margin |
|---:|---:|
| 24 | ±16.9 pp |
| 48 | ±11.9 pp |
| 96 | ±8.4 pp |
| 192 | ±6.0 pp |
| 300 | ±4.8 pp |

⚠️ **这不是你 F1 的置信区间。**

F1 不是简单 Bernoulli accuracy，而且一个 passage 中的两个 facts 往往相关。因此真正评估应该**以 passage/case 为 bootstrap 单位**，重新计算整个 F1 分布，而不是把每个 fact 假装成独立样本。

这张表只是告诉你：

> **24 case 下，“76.92 和 80.00 谁更好”这种比较几乎没有你看到的两位小数那么精确。**

所以 DEV 高于 TRAIN 两三个百分点，几乎不用解释。

### 还有一个更危险的原因：DEV 已经参与研究决策

如果你看过 DEV24 之后：

- 选过 checkpoint；
- 改过 learning rate；
- 改过 epoch；
- 改过 evidence format；
- 改过 prompt；
- 改过 parser；
- 根据错误案例修改 synthetic data；
- 在 C2/E/D 里选表现最好的方案；

那么 DEV 已经是**development/validation set**。

它不是最终 holdout 了。

这里没有一个神奇的：

> “看五次以后才不算 holdout。”

只要第 N+1 个设计决策利用了第 N 次 DEV 结果，适应性选择已经开始。统计学习里早就知道，反复对同一 holdout 做 adaptive queries 会逐渐产生 selection bias；超参数优化研究也观察到 validation overtuning 在小数据情况下尤其值得警惕。citeturn19search11turn19search9

这并不是说 DEV24 “废了”。

恰恰相反：

✅ **DEV24 现在就应该大胆作为开发集使用。**

错误的做法才是：

> 一边根据 DEV 调模型，一边继续把 DEV 的 76.92% 当“独立验证”。

公开 benchmark 的标准做法也是把最终 test 数据隔离，避免方法能够根据测试结果继续适配。citeturn19search8

## 下一批 synthetic 应该增加什么，以及什么时候切真实小说

我的建议非常明确：

> **不要现在直接从 24 扩到 96，更不要为了“数据量看起来正常”扩到 500。先只加 24 条。**

而且这 24 条不能是：

> 换人物名 + 换场景 + 同一结构再生成一轮。

那主要是在增加 token，而不是增加任务信息。

### 我会把下一批 24 条这样分

**大约 10 条：新 / 稀缺的语义边界和 fact coverage**

重点不是“新的故事”，而是 TRAIN24 没覆盖或者只覆盖一次的：

- fact 类型；
- relation 方向；
- 多主体；
- 多事件；
- 跨句；
- 指代；
- 时序；
- 隐含关系；
- 一句多候选 fact；
- 容易混淆的 boundary。

这是最高优先级。

FLAN、LESS 和关于 instruction data diversity 的研究都支持这种思路：覆盖更多有效任务行为、选择真正相关的 capability examples，比堆大量相似 instruction 更有利于未见任务表现与鲁棒性。citeturn11search0turn21view1turn6view3

**大约 8 条：minimal pairs + hard negatives**

例如：

> 发生 / 没发生  
> 事实 / 猜测  
> 本人行为 / 他人转述  
> 当前事实 / 过去事实  
> 想做 / 做了  
> 看似同一 lexical cue、实际关系不同

这是专门干掉 shortcut 的。

我甚至宁愿这 8 条故事写得很普通，也不要八篇华丽但都是正例的小说。

**剩下大约 6 条：强 style shift**

这部分要开始往真正小说靠：

- 对话密集；
- 省略主语；
- 第一人称；
- 倒叙；
- 内心独白；
- 长句；
- 修辞；
- 非模板化叙述。

这 6 条的目的不是把任务搞得“更难”，而是让模型明白：

> **任务规则不能和 synthetic prose style 绑定。**

### difficulty 不应该单独追

“难”不是天然的高价值。

一个极难但代表性很差的 synthetic puzzle，可能对真实小说完全没帮助。

更合理的是：

> **只增加真实部署中确实会遇到的难度。**

也就是：

`difficulty × coverage`

而不是 difficulty for difficulty's sake。

LESS 的数据选择结果尤其支持这个观点：关键是训练例子是否体现下游真正需要的技能，而不是表面形式。citeturn21view1

### 输出格式反而应该保持一致

这里要把“diversity”拆成两部分。

**输入侧：越多样越好**

小说语气、结构、人物、事件、句法、长度都应该变。

**输出侧：尽量统一**

schema、字段名、fact ordering rule、evidence convention 应该固定。

不然模型需要同时猜两件事：

> “文本是什么意思？”  
> “今天标注员又喜欢哪种输出方式？”

你真正想让模型学习的是前者。

所以你列出的几个 synthetic 因素，我会这样排：

> **标注正确性 > semantic coverage > minimal pairs / negative examples > 输入 diversity > 与真实任务匹配的 difficulty > 单纯数量**

而 `format consistency` 更像基础卫生条件：它不是提高语义覆盖的主要来源，但做不好会白白制造 label noise。

Self-Instruct 的方法同样强调过滤无效和相似 synthetic instructions，而不是把所有生成内容直接拿去训练。citeturn14search0

### 为什么我不建议 synthetic 一路做到 500 再碰小说

因为 synthetic→synthetic 泛化和 synthetic→real 泛化是两件完全不同的事。

现实分布变化可以带来非常明显的性能下降。经典的 SQuAD distribution-shift 研究发现，同一 QA 系统移到不同自然文本来源时可以出现显著 F1 drop，而人工表现受到的影响要小得多。citeturn19search5

近期 synthetic reasoning 的研究也观察到类似风险：模型可以在规则生成的 synthetic tasks 上学得很好，却不能相应迁移到真实任务，说明模型可能学到了 synthetic task distribution，而不是想要的更一般规律。citeturn5search33

所以：

❌ `24 synthetic → 48 → 96 → 192 → 500 → 然后终于看真实小说`

是我最不推荐的路线。

因为可能到 500 时才发现：

> “我们非常成功地解决了 synthetic novel benchmark。”

这和你的真实目标不是同一个东西。

## 最省成本的验证路线，以及 Blind Set C 怎么设计

我会把整个项目改成下面这条路径：

> **24 → 控制实验 → 48 → 真实小说 pilot → 冻结 → Blind C96**

这里每一步都回答一个不同问题。

### 现在别新增数据，先把 MICRO24 的因果关系弄清

当前 A_FULL 保存下来，不再动它。

把以下内容一起保存：

- BASE checkpoint；
- LoRA checkpoint；
- TRAIN24 内容 hash；
- DEV24 内容 hash；
- inference prompt；
- generation parameters；
- evaluator 版本；
- parser 版本；
- evidence format；
- random seed；
- metric implementation。

然后在现有 DEV24 上跑：

**BASE / instruction / ICL / LoRA 四组。**

这是现在最高 ROI 的实验。

例如你最终看到：

```text
BASE                  31
BASE + instruction    39
BASE + 8-shot ICL     61
LoRA24                77
```

这一个表比多训练三十个 checkpoint 都更能解释 MICRO24 在发生什么。

再做一次：

```text
LoRA24 true labels
vs
LoRA24 shuffled labels
```

最好至少跑 **3 个训练 seed**。

如果 77 其实是：

```text
seed1 77
seed2 55
seed3 68
```

那“24 条规则学习”的故事要降温。

如果是：

```text
75
77
79
```

证据会强很多。

### 再加 24 条，但只加“新信息”

做到：

```text
TRAIN48
```

而不是重新生成另一个随机 48。

保留原 DEV24，当普通 development set 使用。

同时保留一个**不用于调参的 24-case diagnostic probe**，里面尽量全是 minimal pairs / hard negatives / style transformations。

这时你关心的已经不只是总体 DEV F1：

```text
TRAIN24 → DEV24 = 76.9
TRAIN48 → DEV24 = ?
```

更应该看：

```text
normal cases
minimal pairs
negative cases
new fact types
style shift
cross-sentence
implicit semantics
```

各自怎么动。

💡 一个很有信息量的结果可能是：

```text
Overall:
77 → 79

Hard semantic:
48 → 70
```

总体只涨 2 点，但实际上比：

```text
Overall:
77 → 84

Hard semantic:
48 → 49
```

更让我相信 TRAIN48 学到了规则。

第二种很可能只是把常见模式做得更熟练。

### 到 48 就碰真实小说

这是我对问题 E 最明确的回答：

> ✅ **进入真实小说前，我只建议再增加 24 个高质量 synthetic cases。也就是总 synthetic TRAIN = 48。**

然后马上做：

```text
REAL-PILOT24 或 REAL-PILOT48
```

这些真实片段现在可以当开发数据，**不要当最终测试集**。

不用一上来标几百条。

24–48 条真实样本已经能回答最值钱的问题：

> “synthetic 上学到的东西有没有跨过 synthetic→real 这道墙？”

同时比较：

```text
BASE
LoRA24-synthetic
LoRA48-synthetic
```

在 REAL-PILOT 上的结果。

如果出现：

```text
DEV synthetic: 80
REAL pilot:    72
```

很好，说明 synthetic learning 大体可迁移。

如果：

```text
DEV synthetic: 80
REAL pilot:    35
```

就不要继续生成 96/192 synthetic。

此时你缺的是 domain coverage，不是样本数。

### 只有满足条件，才扩 synthetic 到 96

我会给 TRAIN96 设置一个门槛：

**只有 TRAIN48 同时满足下面两个方向，才继续增加 synthetic：**

1. 在 DEV / diagnostic probes 上，比 TRAIN24 更稳定，尤其 hard cases 有进步；
2. REAL-PILOT 没有出现巨大的 synthetic→real collapse。

否则直接把预算放在真实小说。

所以推荐路径不是：

```text
24 → 48 → 96 → real
```

而是：

```text
24
 ↓
48
 ↓
REAL PILOT
 ↓
判断是否还值得 synthetic 96
```

这会便宜很多。

### Blind Set C 我推荐 96 case

对当前这种规模，我认为：

> **C = 96 个 case 是一个很合理的最低正式 blind confirmation。**

不是因为 96 有什么统计魔法，而是因为：

- 24 明显太小；
- 48 仍然很容易被少数 case 主导；
- 96 已经能把几个主要 strata 都放进去；
- 对“提升很大还是没有提升”这种工程判断，成本仍然可控。

如果你将来要对外给出比较强的结论，例如：

> “24/48 条 SFT 可以可靠地把这种语义规则迁移到新小说。”

我会更喜欢：

> **192 cases。**

96 是工程验证级。

192 更接近“我要认真相信这个数字”的级别。

如果目标是把误差压到大约 ±5 percentage points 的量级，往往还要接近 300 个独立 observation；而你的 F1 又存在 case 内 facts 相关性，所以不能简单把“192 facts”当成“192 个独立样本”。

### Set C 应该按 case，而不是 fact 数量设计

你现在：

```text
DEV24
24 cases
48 facts
```

这不是 48 个完全独立的数据点。

假设一篇小说因为：

> 特殊叙事方式 / 特殊实体关系 / 特殊标注难度

让模型同时漏掉其中两个 facts，这两个 error 明显是相关的。

所以 C 的统计单位应该优先是：

> **novel passage / case**

最终计算 uncertainty 时，也按 case resampling：

```text
抽 96 个 case with replacement
→ 汇总里面所有 predictions / gold
→ 重算 Semantic Fact F1
→ 重复很多次
→ 得到 bootstrap CI
```

不要：

```text
把全部 facts 打散
→ 假设每个事实完全独立
```

后者通常会给出过分乐观的误差范围。

### 最终 Set C 最好用真实小说，而不是同源 synthetic

这里有一个概念要分开。

**如果你想证明：**

> “Tiny SFT 能不能学会 synthetic task rule？”

可以做一个独立 synthetic C。

**如果你想证明：**

> “这个方案可以进入真实小说正式训练/部署。”

那最终 C 应该来自**真实目标分布**。

我的推荐是：

```text
DEV24 synthetic
→ 开发集，随便看

DIAG24 synthetic
→ minimal pairs / stress tests，可反复看

REAL-PILOT24~48
→ 真实小说开发集，可以看

C96 REAL
→ 最终 blind confirmation，一直锁住
```

如果真实小说标注很贵，也可以先做：

```text
C48_SYN
```

作为“机制确认”。

但不要用它替代最终 real C。

### C 什么时候才能打开

答案很严格：

> **当打开 C 后，你已经不准备再根据结果修改任何会影响最终输出的东西。**

至少这些必须冻结：

```text
训练数据选择规则
synthetic / real 比例
LoRA rank
learning rate
epochs / optimizer updates
checkpoint selection rule
prompt
decoding
evidence representation
parser
normalization
matching rule
evaluator
threshold
primary metric
```

而且在打开 C 前就写好：

> “什么结果算成功？”

例如：

```text
Primary:
Semantic Fact F1

Secondary:
Evidence F1
Precision
Recall

Gate:
Semantic Fact F1 >= X
and no major slice below Y
```

真正打开后：

```text
C = 74
```

你不能说：

> “哦，原来 D_RANGE 在 C 上不好，那换成 C2_FULL 再跑一下。”

这样 C 当场就变成新的 DEV。

同理：

```text
C = 74
→ 看 error
→ 生成专门修这些 error 的 24 条 synthetic
→ 重训
→ C = 82
```

82 不再是 blind confirmation。

此时要再做最终确认，只能建：

```text
Set D
```

反复利用验证结果进行模型/超参数选择会产生 validation overtuning，这一点在 adaptive data analysis 与 hyperparameter optimization 文献中都有理论和实证依据。citeturn19search11turn19search9

## 我对 MICRO24 的最终判断

**A. 当前 24 TRAIN + 24 DEV 已经证明了什么？**

在没有 pipeline leakage 的前提下，它已经很有力地否定了最简单的：

> “模型只是把 24 篇训练小说逐字记住。”

因为 DEV 的人物、场景和表达都是未见的。

它还提供了**某种任务表示发生迁移**的证据。

但它暂时无法区分：

> template-family generalization  
> vs semantic decision rule learning  
> vs pretrained capability elicitation。

而且在没有 BASE DEV24 score 的情况下，还无法知道 LoRA 真正贡献了多少百分点。

**B. 为什么 Tiny SFT 可能这么有效？**

因为这不是训练一个 4B 模型从零学“理解小说”。

更像是：

\[
\text{强预训练语言能力}
+
\text{强 instruction prior}
+
\text{43 个高密度事实监督}
+
\text{窄任务 ontology}
+
\text{72 次梯度更新}
\rightarrow
\text{稳定的任务行为}
\]

LIMA、few-shot PEFT、LESS、AlpaGasus 等工作共同说明，强 pretrained model 的 downstream adaptation 可以非常 data-efficient，而且训练数据价值高度不均匀。citeturn21view0turn6view1turn21view1turn16search0

LoRA 又刚好适合这种窄适配：它冻结 base weights，只学习低秩增量，因此天然更偏向“在已有模型上做有限方向的调整”，而不是全模型重写。citeturn18academia20

不过：

> **LoRA rank 32 绝不等于“不可能 memorization”。**

rank 是每个适配矩阵更新的低秩约束，不是“模型只能存 32 条规则”。只要多个层/模块都挂了 LoRA，可训练自由度仍然足以拟合一个 24-case 数据集。

近期专门研究 LoRA memorization 的工作发现，在其测试设置和 similarity-based memorization 指标下，LoRA 比 full fine-tuning 的训练数据记忆/泄漏明显更低，同时保持较强任务性能；但这项研究并不是你的 24-shot 小说抽取设置，因此只能说明 **LoRA 不等于纯 memorizer**，不能替你的实验证明泛化。citeturn21view2

**C. 怎么判断是不是泄漏 / evaluator bias？**

我认为必须做的四个控制是：

> **BASE、few-shot ICL、shuffled-label LoRA、counterfactual minimal pairs。**

再加：

> 独立 generator 的 blind C + 人工复核 evaluator。

这六个过了以后，76.92% 的可信度会提升非常多。

**D. 下一批到底加什么？**

优先级是：

> **新语义/fact coverage → minimal pairs 和 negatives → 新语言风格 → 与真实小说相符的 difficulty → 单纯数量。**

下一批 24 我会近似：

```text
10  新/稀缺 fact boundary
 8  minimal pair / hard negative
 6  style shift
```

输入尽量多样，输出 schema 尽量稳定。

**E. 正式进入真实小说前，再增加多少 synthetic？**

我的答案不是 96。

是：

> **再增加 24。**

也就是：

```text
TRAIN24 → TRAIN48 → REAL-PILOT
```

如果 TRAIN48 没有明显增加 hard-case 泛化，继续 synthetic scaling 的价值已经很可疑。

如果 TRAIN48 好，而且 REAL-PILOT 也好，再考虑把 synthetic 总数加到 96。

**F. Blind Set C 多少 case？**

我的正式推荐：

> ✅ **96 case。**

而且最终面向小说应用的 C96 应尽量来自真实目标分布。

如果未来要写成非常强的研究结论：

> **192 case 更稳。**

结果用 case-level bootstrap 给 95% CI，不要只报：

```text
76.92%
```

最好最终变成：

```text
Semantic Fact F1 = xx.x
95% case-bootstrap CI = [xx.x, xx.x]
n = 96 passages
facts = N
```

这样数字才真正有解释力。

**G. 最省钱的“24 → 48 → 真实小说”路线**

我最终推荐的是这一条：

```text
现有 TRAIN24
        │
        ├── BASE control
        ├── detailed-instruction BASE
        ├── few-shot ICL
        ├── shuffled-label control
        └── 3 个 LoRA seeds
        │
        ▼
确认 24-shot effect 确实存在
        │
        ▼
新增 24 个高信息 synthetic
10 coverage + 8 contrastive + 6 style
        │
        ▼
TRAIN48
        │
        ├── DEV24
        └── DIAG24 minimal-pair stress test
        │
        ▼
REAL-PILOT 24~48
        │
        ├── synthetic→real 掉得少
        │       ↓
        │   进入真实小说训练
        │
        └── synthetic→real 暴跌
                ↓
        停止 synthetic 扩量
        改补真实语言/语义分布
        │
        ▼
冻结 recipe + evaluator + metric
        │
        ▼
Blind REAL C96
        │
        ▼
只打开一次
```

🔥 **所以我不会把 MICRO24 当成“小数据偶然”直接丢掉。相反，我认为它是一个很值得追的信号。**

但我同样不会现在就把它解释成：

> “24 条让 Qwen3-4B 学会了一套全新的通用语义推理规则。”

目前最合理的描述是：

> **24 个精心选择的 examples 很可能足以把一个窄任务的“语义判定协议”写入 LoRA，并调用底座原本已经拥有的大量阅读和抽取能力。DEV24 显示这种协议已经跨越了具体文本实例，但还没有证明它跨越了 synthetic data distribution。**

而你下一阶段最重要的一刀，并不是 `24 → 96`。

是：

> **`BASE → ICL → LoRA24 → LoRA48 → REAL24/48`。**

这组实验一旦出来，你基本就能回答“它究竟是模板记忆、任务规则、能力激活，还是三者混合”这个核心问题。现有文献恰恰表明，高质量数据、目标能力覆盖和有信息量的监督可能远比原始样本数重要，因此现在优先测清**新增一条数据到底提供了什么新信息**，比把训练集快速扩到几百条更划算。citeturn21view0turn21view1turn16search0turn18search1