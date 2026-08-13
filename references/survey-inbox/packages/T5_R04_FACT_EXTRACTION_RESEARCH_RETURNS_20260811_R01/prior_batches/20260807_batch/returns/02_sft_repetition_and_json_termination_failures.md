# 小模型 SFT 后疯狂复读与 JSON 崩坏：真实根因、诊断与修复研究

## 结论摘要

✅ **你们这批结果更像“模型会抽事实，但停止机制和序列控制坏了”，而不是单纯“不会抽事实”。**

164 个案例中，非法 JSON 占 **40.9%**，事实复读占 **65.2%**；把上限从 2048 提到 4096 后，原先触顶的 22 个案例全部继续触顶，而且新增内容几乎都是重复对象。这组现象有三个很强的诊断信号：

1. **正确事实经常在失控前已经出现**，说明语义抽取能力至少部分存在。
2. **增加 token 预算没有增加新事实，只延长循环**，说明 `max_new_tokens` 不是答案长度瓶颈，只是外部保险丝。
3. **模型在生成第一个正确对象后越来越容易再生成同一对象**，符合已有研究发现的“重复自强化”：相同句段在上下文中出现次数越多，模型继续重复它的概率越高。citeturn2search1turn11view0

对你们当前事故，我的综合判断是：

> **主要故障是 termination failure（终止失败），并混有 schema failure（格式失败）和 decoding amplification（解码放大）；semantic failure（语义失败）需要独立测量，不能再用最终 JSON 是否可解析来代替。**

最高优先级不是立刻加 repetition penalty，也不是继续调大生成长度，而是核查下面这条链路：

> **训练 completion 末尾是否真的存在正确的 Qwen turn-end token → 该 token 是否进入 labels → 是否被 truncation 切掉 → 是否被 padding/mask 忽略 → 推理是否使用同一个 chat template、EOS ID 和 stopping 配置。**

TRL 官方文档明确要求 Qwen 的 EOS 与聊天模板对齐，例如 Qwen2.5 应将 `<|im_end|>` 配为训练 EOS；Qwen 官方也区分 `<|endoftext|>`、`<|im_start|>` 和 `<|im_end|>`，其中聊天轮结束依赖 `<|im_end|>`。citeturn9view2turn9view3

另一个高概率来源是训练输出分布。已有受控实验发现，训练数据中的重复率与模型生成重复显著相关；即使换成更大模型或做 instruction tuning，这种关联依然存在。citeturn9view0

**一句话结论：**

> 你们现在不应把“非法 JSON”直接记成“事实抽取错误”。其中相当一部分很可能是：模型先完成了正确抽取，随后因为 EOS、模板、长度分布或重复自强化继续生成，把原本正确的容器毁掉。

## 机制与证据地图

模型为什么已经输出正确对象，还会继续输出同一个对象？可以把生成过程理解成一个逐 token 的选择：

```text
…… {"主体":"甲","关系":"任职","客体":"乙"}
                                        ↓
下一步可能是：
A. ]           结束数组
B. <|im_end|>  结束回答
C. , {         再生成一个对象
```

SFT 训练的目标主要是“在给定正确前缀时预测下一个 token”。如果训练数据让模型学到以下任一倾向，选项 C 的概率就可能超过 A、B：

- 很多 completion 包含长对象列表；
- 同一事实或同一模板对象在数据中重复；
- 长 completion、特殊 completion 占据过多训练 token；
- 结束 token 出现少、被切掉或未参与 loss；
- 数组结束形式不统一；
- 推理前缀和训练 chat template 不一样；
- 第一次误生成重复对象后，重复上下文本身又增强下一次重复概率。

“重复自强化”不是纯社区猜测。Xu 等人的实验发现，模型本来就偏向重复前一句，并且一句话重复得越多，继续重复的概率越高；初始概率越高的句子，自强化效应通常越强。citeturn2search1 训练数据视角的研究也发现，数据里的重复模式与生成退化高度相关，并通过降低训练时模型对重复部分的学习，显著减少了生成重复。citeturn9view0

对 JSON 抽取来说，情况会更危险：一个对象模板通常非常固定，字段名、引号、冒号和逗号都是高频结构。模型一旦进入：

```json
,
{
  "主体": "...",
  "关系": "...",
  "客体": "..."
}
```

这条路径，后面的 token 往往比“现在应该结束”更容易预测。小模型可用来表达“内容差异”和“控制何时结束”的容量更有限，容易把“稳定输出合法对象模板”学得很强，却没有同样强地学会“对象数量取决于输入语义”。

下面是各因素与循环问题的关系。这里把**有受控实验或官方实现依据**、**有机制支持但缺少直接 JSON 实验**、**社区工程案例**分开看。

| 因素 | 与循环的关系 | 证据判断 |
|---|---|---|
| 训练数据重复 | 直接提高重复模式的学习概率；完全相同对象、近似对象和同输入多版本 completion 都有风险 | **强实验支持**。多数据集实验发现训练重复率与生成重复高度相关。citeturn9view0 |
| 特殊样本比例过高 | 如果“特殊样本”多为超长列表、空结果、固定兜底文案或高密度对象，会扭曲对象数、长度和结束方式的先验 | **机制较强，直接证据有限**。应按 assistant token 数而非仅样本数统计占比 |
| completion 长度分布 | 常见 token-level loss 下，长 completion 提供更多监督 token；少量超长列表可能在总梯度中权重很大 | **机制强**。特别要统计长度分桶的 token 占比和尾部样本 |
| EOS 学习不足 | 模型不知道何时结束，正确内容之后仍继续预测普通文本或新对象 | **最高风险之一**。TRL 官方要求 EOS 与模板对齐；社区有缺失 EOS 后生成过长的复现。citeturn9view2turn9view4 |
| JSON / bracket completion | 模型既要完成事实，又要维护括号栈、逗号位置、字符串转义和容器结束，小模型更容易把语义正确与结构正确拆开失败 | **有基准支持**。SchemaBench 发现复杂 JSON 仍很困难，整体正确率仅 61.06%，而且 SFT 后仍可能不会基础 JSON 语法。citeturn9view11turn10view0 |
| teacher forcing / exposure bias | 训练总是在正确历史上预测；推理时一旦自己生成了一个多余逗号或重复对象，后续进入训练中较少见的前缀 | **合理放大器，但不宜当唯一根因**。曝光偏差理论支持错误累积，但也有研究发现模型存在自恢复，影响未必持续递增。citeturn11view1turn11view2 |
| LoRA | LoRA 本身没有被证明天然导致复读；风险来自更新过强、目标层配置，以及新增或更换特殊 token 时 embedding/lm_head 未训练 | **条件性风险**。Qwen 社区复现了修改 EOS、但 LoRA 不训练 embedding/lm_head 时无法停止的问题。citeturn9view6 |
| learning rate | LR 太高可能让狭窄数据分布快速覆盖原模型的停止和通用生成行为 | **中等证据，强依赖任务**。不能因为 Qwen 示例使用 `1e-4` 就认定所有 4B 窄任务都适合；该示例同时只训练 1 epoch。citeturn11view6 |
| epoch | 更新次数过多会放大数据里的模板、长度和错误 completion；但“多 epoch 必然坏”并不成立 | **任务相关**。2026 年 long-CoT 实验甚至发现多 epoch 可改善性能和终止率，因此应根据 held-out 终止指标选 checkpoint，而非固定迷信 1 或 3 epoch。citeturn3search2turn3academia19 |
| batch size | 主要通过梯度噪声、有效更新次数和 LR 配合间接影响；没有足够证据证明小 batch 或大 batch 单独制造循环 | **低直接证据**。做消融时应固定总 assistant token 和更新预算 |
| packing | 正确实现时只是效率优化；若样本边界没有 EOT/EOS、attention 隔离错误，模型可能学会从一个 completion 继续到下一个 | **条件性高风险**。TRL packing 会把多个序列组成定长块，具体边界必须审计。citeturn11view5 |
| truncation | 右截断最容易切掉长 completion 尾部的 `]}` 和 EOS，模型大量看到“开始和中间”，很少看到“正确结束” | **强风险**。TRL 文档说明超过 `max_length` 的序列默认从右侧截断。citeturn11view5 |
| stop token | 正确 stop token 能终止生成；配置错 ID、`ignore_eos=True` 或训练推理不一致，会让模型一直生成 | **强工程证据**。Qwen 社区多次出现 EOS 配置不一致导致不能停止的案例。citeturn11view8turn9view6 |
| chat template | 模型看到的角色标记、assistant 起点和轮结束标记改变后，下一 token 分布也会变 | **官方明确要求一致**。Qwen 表示应使用指定 ChatML 模板。citeturn9view3 |
| 只训练 assistant loss | 通常是合理做法，但前提是 assistant mask 确实覆盖整个回答及末尾 EOS；若 EOS 被 mask 掉，模型不会收到终止监督 | **实现相关**。TRL 要求模板提供正确 assistant mask，并支持 completion-only loss。citeturn9view2 |
| schema 不统一 | 字段顺序、空值、数组层级、代码块、中文/英文 key、单双引号、缺省字段不统一，会让结束位置和合法后继 token 变得模糊 | **强实践合理性，结构生成研究支持**。结构生成基准把 schema 理解、合法 JSON 和字符串转义列为不同困难。citeturn9view11 |
| padding / attention mask | 当 pad 与 EOS 共用 ID、但 mask 又把相关位置屏蔽时，可能意外削弱 EOS 训练；推理不传 attention mask 也可能出现异常 | **社区工程证据**。HF 与 Qwen issue 均记录过这类警告和不停止现象，但不是受控因果实验。citeturn9view4turn11view7 |

这里有一个容易误解的点：

> **SFT 后的“模式坍塌”通常不是 GAN 文献里严格意义上的 mode collapse，而是输出分布变窄、模板概率过高、EOS 概率变低，最终形成少数高概率序列吸引子。**

对于你们的对象数组，那个“吸引子”很可能正是：

```text
逗号 → 左花括号 → 固定字段名 → 已出现的字段值 → 右花括号 → 逗号……
```

## 根因树

### A．按可能性和可验证性排序

| 优先级 | 根因分支 | 为什么与你们现象吻合 | 最快验证方式 | 当前判断 |
|---:|---|---|---|---|
| 1 | **EOS、EOT、chat template 或 label mask 不一致** | 正确内容已经生成，却一直不结束；增加生成上限只延长输出 | 抽 100 条训练样本，打印最后 20 个 token、token 名称、labels、attention mask | **极高可能，极易验证** |
| 2 | **truncation 切掉 JSON 闭合和 EOS** | 长 completion 尤其容易成为“永远没有结尾”的训练样本 | 统计截断率；比较截断前后尾 token；统计被切样本中 `]}`/EOS 丢失率 | **极高可验证性** |
| 3 | **训练 completion 或对象级重复污染** | 107/164 出现事实复读，模型重复的是完整对象而非随机乱码 | 对输入、完整 completion、canonical object 三层去重并计算重复率 | **高可能** |
| 4 | **长列表与特殊样本按 token 数占比过高** | 模型学到“数组通常还没结束”；对象数先验大于真实输入所需 | 画 completion token 长度、对象数分布；按 token 统计各类样本权重 | **高可能** |
| 5 | **schema 和结束策略不统一** | 正确事实出现后，模型不确定是 `]`、`}`、说明文字还是继续对象 | 将训练输出 canonicalize 后比较 schema variant 数量 | **高可能** |
| 6 | **greedy / 低温解码把局部高概率循环完全暴露** | 22/22 在更长预算下继续同一轨迹，符合确定性循环 | 对同一 checkpoint 做温度、top-p、采样 seed 和 grammar A/B | **高放大作用，但通常不是唯一根因** |
| 7 | **SFT 更新过强：LR、epoch、窄数据共同破坏原始停止能力** | base 模型正常、SFT 后坏；模板能力增强但控制能力下降 | 比较 base、早期 checkpoint、最终 checkpoint；关闭 adapter 推理 | **中高可能** |
| 8 | **packing 边界或 padding/mask 问题** | 可能让模型学会一个样本结束后继续另一个样本，或忽略 EOS | 暂时关闭 packing；审计 block 边界和 position/attention mask | **中等可能** |
| 9 | **LoRA 新特殊 token 不可学习或 adapter 加载异常** | 使用新增 EOS、修改 tokenizer、冻结 embedding/lm_head 时尤其危险 | 检查 vocab 是否变化、EOS 是否原生 token、modules_to_save、adapter load/merge 一致性 | **条件性高风险** |
| 10 | **纯语义能力不足** | 仍可能存在，但无法解释“正确事实出现后才被复读毁掉” | 对“第一次有效或最小闭合前缀”算事实 F1 | **存在，但不像主因** |

结合你们的现象，建议暂定一个工作假设：

```text
主要故障
├── 终止监督缺失或削弱
│   ├── EOS/EOT 不一致
│   ├── EOS 被 mask
│   ├── EOS 被 truncation 切掉
│   └── 推理 stop 配置不一致
├── 继续生成先验过强
│   ├── 长列表 token 权重过高
│   ├── 对象重复和训练数据重复
│   ├── 特殊样本比例失衡
│   └── schema 结束方式不统一
└── 推理阶段放大
    ├── greedy / temperature=0
    ├── 第一个重复对象进入上下文
    └── 重复自强化进入稳定循环
```

这个树比“模型过拟合了”更可操作。因为“过拟合”只描述结果，不能告诉你是 EOS 没学到、长样本权重过高，还是训练数据本身就在教重复。

## 零训练诊断与“会抽但不会停”判定

### B．最便宜的零训练诊断实验

下面这些实验都不需要重新训练。建议使用同一批 164 个案例，并保存逐 token 输出、token ID、logprob 和 stopping reason。

| 实验 | 怎么做 | 结果怎么解释 |
|---:|---|---|
| 1 | **第一次有效前缀评估**：逐 token 扫描输出，记录最早能解析成完整顶层 JSON 的位置；同时做“只补闭合括号、不改内容”的最小修复解析 | 第一次有效前缀事实正确、最终输出非法或重复，直接判为 termination failure |
| 2 | **增量 JSON parser 强制停**：顶层对象/数组完整闭合后立即停止，不等模型 EOS | 非法率大幅下降且事实 F1 不下降，说明模型语义已完成，主要不会停 |
| 3 | **EOS logit 追踪**：在每个正确对象结束、数组应结束的位置，记录 EOS、`]`、`,`、`{` 的 logprob 或排名 | `,`/`{` 长期高于 `]`/EOS，说明继续生成先验过强；`]` 高但 EOS 低，更像 EOT 配置问题 |
| 4 | **解码参数小矩阵**：固定 prompt，跑 greedy、`temperature=0.2/0.5/0.8`、`top_p=0.8/0.95/1.0`、轻度 repetition penalty，并换 3 个 seed | 只有 greedy 循环、采样可恢复：解码放大明显；所有配置都重复：训练分布或 EOS 更可疑 |
| 5 | **base / adapter ablation**：同模板比较原始模型、关闭 LoRA、不同 checkpoint、最终 adapter、merge 前后 | 早期 checkpoint 正常而后期坏：更新过强；关 adapter 立刻恢复：问题来自 SFT 而非服务层 |
| 6 | **训练 token 管道审计**：打印随机样本及所有超长样本的 rendered text、input IDs、labels、assistant mask、attention mask 和最后 20 个 token | 这是识别 EOS 被切、被 mask、重复添加或模板错配的最高收益实验 |
| 7 | **重复自强化 probe**：给模型喂入“正确 JSON + 一个重复对象的开头”，比较继续重复的概率；再喂入“正确 JSON + `]`”看 EOS 概率 | 加入一次重复后重复概率明显升高，说明模型进入自强化循环，符合已有实验结论。citeturn2search1 |
| 8 | **grammar / schema A/B**：一组使用原始自由生成，一组使用 JSON grammar，并为数组设置合理 `maxItems` | 只修复解析、不修复重复：schema failure 为辅，termination/semantic cardinality 仍有问题 |

vLLM 的新版本已经提供按 N-gram 模式检测重复并触发停止的配置，这类能力适合作为实验和生产保险丝，但它检测的是循环结果，不会修复模型为什么进入循环。citeturn9view9

### F．如何判断“模型理解正确但不会停”

建议把每个案例拆成四个互斥或可组合标签，而不是只记“JSON 合法/非法”。

| 类型 | 判定标准 | 典型现象 |
|---|---|---|
| **semantic failure** | 在第一次可用前缀、最小闭合前缀、grammar constrained 输出中，事实仍错、漏或幻觉 | key 和括号都对，但主体、关系、客体错 |
| **termination failure** | 正确事实已经齐全；继续生成后出现重复、尾巴或触顶；parser-stop 可无损恢复 | 正确数组后又输出同样对象，或闭合后继续文本 |
| **schema failure** | 事实可以从输出中识别，但字段、类型、引号、转义、数组层级或括号错误 | `"facts"` 应为数组却输出对象，或漏引号 |
| **decoding failure** | 同一模型换小幅解码策略、合法 token 约束或 seed 后可恢复；teacher-forced EOS/闭合 token 概率并不低 | greedy 循环，温和采样不循环 |
| **mixed failure** | 正确事实部分出现，但同时漏事实、重复和格式损坏 | 实际项目中很常见 |

可以建立一个非常直接的“语义已完成但终止失败”指标：

```text
理解正确但不会停 =
    首次可用前缀 Fact-F1 达标
    AND
    最终输出存在重复 / 非法 / 触顶
    AND
    parser-stop 后 Fact-F1 基本不下降
```

更强的确认条件是同时满足：

- 第一个正确对象或正确事实集合在循环开始前已经出现；
- 删除循环尾部后，无需修改事实内容即可得到正确答案；
- 强制在顶层 JSON 闭合处停止后，事实指标恢复；
- 增加 token 上限只增加重复、不增加新的正确事实；
- 在应结束位置，模型对 `,` 或新对象起始 token 的概率高于 EOS；
- 原始模型或早期 checkpoint 能停，后期 SFT checkpoint 不能停。

你们目前已经满足其中至少前四类证据的一部分，因此“会抽但不会停”不是宽泛猜测，而是很值得优先验证的工作假设。

## 解码层与重训边界

### C．哪些能在 decoding 层处理，哪些必须重训

| 问题 | 解码层能否处理 | 是否建议重训 |
|---|---|---|
| 顶层 JSON 闭合后仍继续输出 | 可以用增量 parser、stop string、stop token 立即停 | 若模型 EOS 明显异常，仍应修训练 |
| JSON 引号、括号、逗号非法 | grammar constrained decoding 通常可以强制语法合法 | 语义错误、字段选择错误仍需数据或训练修正 |
| 数组无限追加重复对象 | 可以设置 `maxItems`、循环检测、对象去重和 parser stop | 若模型普遍倾向继续对象，必须修数据/EOS/训练 |
| greedy 才出现循环 | 可用低强度采样或 contrastive decoding 缓解 | 若生产必须确定性输出，仍应修模型 |
| EOS ID 或 stop token 配错 | 直接改推理配置 | 若训练时也配错，需要重训或补训 |
| EOS 在训练中被截断或 mask | 推理无法真正补回这项能力，只能外部截断 | **必须重训或至少继续训练修复** |
| 训练数据包含重复对象和坏 completion | 后处理可隐藏，但模型分布仍错误 | **必须清洗后重训** |
| schema 多版本冲突 | grammar 可统一最终外观 | 模型仍会浪费概率学习冲突格式，建议重训 |
| 事实本身错漏 | 解码参数通常无法稳定修复 | **需要数据、模型或训练改进** |

各解码参数的实际作用如下。

| 参数 | 能解决什么 | 主要副作用 | 结论 |
|---|---|---|---|
| `repetition_penalty` | 降低已经出现 token 再次出现的概率 | JSON 的字段名、引号、标点、实体重复本来就可能合法；过高会把合法内容扭曲 | **症状缓解，不能证明根因消失** |
| `frequency_penalty` | 一个 token 出现越多，惩罚越大 | 对固定 schema 很不友好，可能破坏重复 key、共同实体和标点 | 适合轻度试验，不建议作为核心修法 |
| `temperature` | 提高随机性，可能跳出 greedy 的局部循环 | 结构错误、字段漂移、事实波动会上升 | 诊断价值大，生产价值取决于容错 |
| `top_p` | 排除长尾 token 或允许更多候选，改变循环可逃逸性 | 太低可能让闭合/EOS 永远进不了候选集；太高增加错误 token | 与 temperature 联动测试，不是单独药方 |
| `no_repeat_ngram` | 硬性禁止同一 N-gram 再出现 | JSON 模板天然重复，可能连字段名和合法实体都禁止；HF 官方也提醒会误伤必要短语。citeturn11view4 | **结构抽取通常不推荐** |
| stop sequences | 出现指定字符串后立即停止 | 依赖字符串与 tokenizer 对齐；只能在模型已经输出 stop 时工作 | 很好的生产保险丝 |
| parser-based stop | 顶层 JSON 一闭合就停 | 若模型一直不闭合，仍需 maxItems 或循环检测 | 对你们最推荐的零训练措施 |
| grammar constrained decoding | 保证输出符合 grammar 或 JSON Schema | 只保证形式合法，不保证事实正确、对象唯一或及时结束 | 应作为格式层，不应替代模型评估 |

vLLM 对这些参数的定义也表明，它们是在 logits 层惩罚已出现 token 或控制采样候选，并不会改变模型参数。citeturn7search1

🔥 **结构约束有一个关键盲点：**

如果 schema 定义的是一个没有 `maxItems` 限制的数组，那么在每个对象后面：

```text
]
```

和

```text
, { 下一个对象 }
```

在语法上都可能是合法的。grammar 只能过滤非法 token，不能知道“事实已经抽完”。结构生成研究也强调，形式约束与语义、运行时正确性是不同层次的问题。citeturn5search9turn9view7

所以 constrained decoding 可能把你们的：

```text
非法 JSON + 无限重复
```

变成：

```text
始终合法的 JSON + 大量重复对象
```

解析率会很好看，但 termination 和 semantic cardinality 并没有真正修好。

## 下一轮 SFT 配方

### D．最值得改的五项

### 数据只保留一种标准输出形式

所有 completion 先经过程序生成或严格 canonicalization，不允许人工随意拼 JSON。建议统一：

- 固定顶层结构；
- 固定字段名、字段顺序和数据类型；
- 固定空结果表达，例如始终 `{"facts":[]}`；
- 固定 `null`、空字符串、缺失字段的策略；
- 固定字符串转义；
- 不要代码围栏，不要解释文字，不要“以下是结果”；
- 同一事实对象 canonicalize 后去重；
- completion 末尾只允许一次正确 EOT/EOS。

SchemaBench 将“合法 JSON”“理解 schema”“特殊字符转义”识别为不同困难，说明只在 prompt 中写一句“请输出 JSON”并不足以得到稳定结构。citeturn9view11turn10view0

训练前应建立硬校验：

```text
JSON parse
→ schema validate
→ canonical object dedup
→ 事实数量核对
→ completion 尾 token 核对
→ EOS/EOT 核对
```

任何失败样本都不进入 SFT。

### 把 EOS 当成独立训练目标审计

不要只看原始字符串里“好像有 `<|im_end|>`”，而要检查 token 化和 loss 之后的真实状态：

```text
最后一个非 padding input_id 是不是预期 EOT？
对应 label 是否等于该 token ID？
label 是否不是 -100？
attention_mask 是否为 1？
是否被 max_length 截掉？
推理 eos_token_id 是否指向同一个 token？
```

TRL 官方文档明确要求 Qwen 的 EOS 和 chat template 对齐；HF issue 也展示了 EOS 被当成 padding 并对应 `attention_mask=0` 后，模型无法有效学习结束的风险。citeturn9view2turn9view4

使用 Qwen3/Qwen2.5 Instruct 时，应尽量沿用 tokenizer 自带模板，不要自行混合 Llama `[INST]`、Alpaca `### Response` 和 Qwen ChatML。

如果你们给 tokenizer 新增了终止 token，必须确认 embedding 和 `lm_head` 是否一起训练、保存和加载。Qwen 社区的 LoRA 案例表明，替换 EOS 而又不更新相关层，可能直接造成无法停止。citeturn9view6

### 按长度和对象数重新采样

不要只统计“样本条数占比”，需要同时统计：

```text
样本数占比
assistant token 占比
事实对象数占比
长度分桶占比
被截断 token 占比
```

例如 5% 的超长样本，如果每条长度是普通样本的 20 倍，就可能贡献约一半的 completion token 监督。

建议按以下维度分桶：

| 分桶 | 建议作用 |
|---|---|
| 0 个事实 | 教模型快速输出空数组并结束 |
| 1 个事实 | 强化最简单的正确闭合和 EOS |
| 2–5 个事实 | 主体分布 |
| 6–20 个事实 | 适量覆盖长列表 |
| 极长或特殊样本 | 单独限额，不让其按 token 淹没其他数据 |
| 含特殊字符、引号、换行 | 单独覆盖转义能力 |

所谓 interleaving，可以直接理解成：训练 batch 不要连续堆满同一种超长或特殊格式，而是让空、短、中、长样本交错出现。

curriculum 可以尝试“短且规范 → 中等长度 → 长列表和复杂转义”，但目前针对 JSON 复读的直接实验依据有限，因此它的优先级低于去重、canonicalization 和 EOS 修复。

### 用终止指标选择 checkpoint，而不是只看 loss

下一轮不要只保存“训练 loss 最低”的 checkpoint。至少每 0.25–0.5 epoch 在固定验证集运行一次真实自由生成，并同时看：

- Fact-F1；
- 最终 JSON parse rate；
- 第一次有效前缀 Fact-F1；
- duplicate object rate；
- EOS/正常停止率；
- token-limit hit rate；
- tail waste ratio。

Qwen 公开的一个 LoRA 示例采用 `learning_rate=1e-4`、1 epoch、cosine schedule 和 0.1 warmup，但这只是示例 recipe，不是小模型窄域抽取任务的通用最优值。citeturn11view6

建议做小网格，而不是一次押注：

| 项目 | 建议实验 |
|---|---|
| LoRA learning rate | `1e-5`、`3e-5`、`1e-4` |
| epoch | `0.5`、`1`、`2`，中间 checkpoint 必须评估 |
| packing | 第一轮全部关闭；稳定后再单独开启做 A/B |
| max length | 至少覆盖 prompt + completion 的目标分位数，禁止静默切掉尾部 |
| loss | assistant-only 可以保留，但必须验证 EOS 在 assistant mask 内 |
| 评价解码 | 保留一套 greedy 诊断配置，以及一套生产候选配置 |

epoch 多不一定天然坏。long-CoT SFT 的受控实验表明，多次重复数据有时反而会改善任务表现和终止率。citeturn3search2 因此真正该控制的是：

> **数据是否干净、总更新强度是否合适、模型什么时候开始出现 termination 指标恶化。**

### 负例和偏好训练只在干净 SFT 后使用

把错误 completion 当普通 SFT target 放进数据，会直接教坏模型。所谓 negative examples，必须通过能表达“这个输出不应该出现”的训练目标使用，例如：

- unlikelihood training；
- DITTO 式伪重复惩罚；
- contrastive loss；
- DPO 的 chosen/rejected 对；
- schema-aware reward 或 RL。

DITTO 通过构造伪重复文本并惩罚句级重复概率，在开放生成和摘要任务上降低了重复，同时没有牺牲 perplexity。citeturn11view0 其他研究也用 unlikelihood 或 contrastive token objective 直接降低重复 token 概率。citeturn0academia22turn0academia24

针对你们任务，可以构造非常干净的偏好对：

```text
chosen:
{"facts":[对象A, 对象B]}<|im_end|>

rejected:
{"facts":[对象A, 对象B, 对象B, 对象B, 对象B ...]}
```

或者：

```text
chosen:
正确事实 + 正确闭合 + EOS

rejected:
正确事实 + 多余逗号 + 重复对象
```

不过 DPO 不应排在第一轮。若 EOS 被截断、模板混乱或训练数据本身重复，先做 DPO 只是让一个更复杂的优化过程替你遮住数据错误。

## Repetition evaluator 指标集合

### E．建议的评估体系

单独使用“JSON 合法率”会把语义、结构和终止混在一起。单独使用 Fact-F1 又可能漏掉“正确答案后面输出几千 token”的严重生产事故。

建议 evaluator 分成五组。

| 维度 | 指标 | 定义或用途 |
|---|---|---|
| 语义 | `Fact Precision / Recall / F1` | canonicalize 后比较事实三元组或对象 |
| 语义 | `Prefix Fact-F1` | 在第一次有效或最小闭合前缀上计算 |
| 结构 | `Final JSON Parse Rate` | 最终原始输出是否直接可解析 |
| 结构 | `Schema Compliance Rate` | 类型、必填字段、枚举、层级是否合规 |
| 结构 | `Minimal Repair Rate` | 只补闭合括号是否可解析；不允许改内容 |
| 终止 | `EOS Termination Rate` | 是否由正确 EOS/EOT 而非长度上限停止 |
| 终止 | `Token-limit Hit Rate` | 是否撞 `max_new_tokens` |
| 终止 | `Tail Waste Tokens` | 第一次语义完成或 JSON 完整后又生成了多少 token |
| 终止 | `Tail Waste Ratio` | `尾部多余 token / 总生成 token` |
| 对象重复 | `Exact Object Duplicate Rate` | `1 - 唯一 canonical 对象数 / 总对象数` |
| 对象重复 | `Semantic Duplicate Rate` | 忽略 key 顺序、空格、表述差异后的事实重复率 |
| 循环 | `Max Consecutive Repeat Count` | 同一对象连续出现的最大次数 |
| 循环 | `Loop Onset Position` | 第一次进入重复循环时占输出长度的比例 |
| 循环 | `Cycle Length` | 重复循环的最短 token 或对象周期 |
| 文本重复 | `Rep-2 / Rep-3 / Rep-4` | 重复 N-gram 比例 |
| 文本重复 | `Rep-r` | 输出中属于重复片段的 token 比例 |
| 文本重复 | `Compression Ratio` | 高度重复文本更容易压缩，用来捕获长周期重复 |
| 概率诊断 | `EOS Rank at Closure` | 应结束位置 EOS 在候选 token 中的排名 |
| 概率诊断 | `EOS Margin` | `logit(EOS) - logit(最佳继续 token)` |
| 综合 | `Semantic Salvage Rate` | 最终失败案例中，有多少能从循环前缀无损救回正确事实 |

Rep-n、rep-w 和 rep-r 是已有重复研究中使用的指标；rep-r 的目标是衡量序列中有多少长度落入重复片段，而不只统计某个固定 N-gram。citeturn11view3turn12view2 后续文本多样性研究建议组合使用长 N-gram 自重复、压缩率和 Self-BLEU，因为这些指标捕获的重复形态并不完全相同。citeturn9view10turn8search18

对事实抽取任务，最重要的不是 Self-BLEU，而是下面四个业务指标：

```text
Semantic Duplicate Rate
Tail Waste Tokens
EOS Termination Rate
Prefix Fact-F1
```

建议额外生成一个故障分类混淆表：

|  | 最终 JSON 合法 | 最终 JSON 非法 |
|---|---:|---:|
| 前缀事实正确 | 正常或合法复读 | **典型 termination failure** |
| 前缀事实错误 | semantic failure | semantic + schema/termination mixed failure |

这样你们可以直接回答：

> 67 个非法 JSON 里，究竟有多少是事实没抽对，多少只是正确事实被后续输出破坏？

## 假修复与落地判断

### G．看起来有效、其实只把循环截断的做法

| 做法 | 为什么看起来有效 | 没治好的问题 |
|---|---|---|
| 把 `max_new_tokens` 调小 | 输出不再生成几千 token，成本和延迟下降 | 模型仍不会结束，只是更早被掐断；还可能截断真正长答案 |
| 把 `max_new_tokens` 调大 | 希望模型“有机会生成完” | 你们已经证明循环会同步变长，22/22 继续触顶 |
| 看到第一个 `]` 就截断 | JSON 合法率和延迟立刻改善 | EOS 仍没学会；嵌套字符串或复杂结构还可能误停 |
| post-process 删除重复对象 | 最终事实集合可能正确 | 模型仍浪费大量 token，循环风险、延迟和服务阻塞不变 |
| `repetition_penalty` 调很高 | 重复率迅速下降 | 可能改成乱码、字段变形、遗漏合法重复实体；EOS 问题仍在 |
| `no_repeat_ngram_size` | 硬性阻止短片段复现 | 固定 JSON key、实体和标点也会被误伤。citeturn11view4 |
| 提高 temperature | 部分循环可以跳出 | 结构合法率和事实稳定性可能下降；模型分布本身没修 |
| constrained decoding | 输出可达到近乎 100% 语法合法 | 不保证事实正确、对象不重复、数组及时结束 |
| regex 抽第一个 `{` 到最后一个 `}` | 解析成功率上涨 | 中间可能仍有重复、错对象；指标掩盖原始生成质量 |
| 直接上 DPO | chosen/rejected 可压制明显循环 | 若 SFT 数据、EOS 和模板仍错，偏好训练会在坏地基上继续优化 |
| 只看 validation loss | loss 下降让人觉得训练正常 | teacher-forced token loss 不直接衡量自由生成是否能终止 |
| 只去重完整样本 | 数据条数看起来不重复 | 同一对象可能散落在不同输入、不同 key 顺序或不同包装中 |

这些做法并非都不应该使用。生产系统应该保留：

```text
增量 parser stop
+ schema validation
+ 合理 maxItems
+ 循环检测
+ 最大 token 保险丝
+ 输出对象去重
```

但应把它们标记为 **runtime guardrail（运行时护栏）**，不要把护栏带来的 JSON 合法率提升当成训练问题已经解决。

综合你们目前的数据，建议的处理顺序是：

```text
审计 EOS / template / labels / truncation
        ↓
重算训练数据的对象重复率和 token 长度权重
        ↓
用 Prefix Fact-F1 拆开语义与终止问题
        ↓
增量 parser stop + loop detector 作为临时生产护栏
        ↓
用 canonical 数据、显式 EOT、长度重采样重新做轻量 SFT
        ↓
按 termination evaluator 选早期 checkpoint
        ↓
仍有循环时再考虑 unlikelihood、DITTO 或 DPO
```

🔥 **最重要的判断标准不是“最终字符串能不能 parse”，而是：**

> 模型在什么时候已经拥有完整、正确的事实集合；从那个时刻起，它给 EOS、闭合容器和继续生成新对象分别分配了多大概率。

一旦你们把“语义完成点”和“实际停止点”分开测，这个问题通常就不再模糊：

- 语义完成点本身错，才是不会抽事实；
- 语义完成点正确，但之后继续输出，是不会停；
- 强制闭合后事实正确，是结构或终止问题；
- 只有调解码参数才恢复，是解码放大；
- 所有解码方式都重复，而且 EOS 排名极低，则必须回到数据、模板和训练链路。

来源：ChatGPT