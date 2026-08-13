# 调查任务 6｜4B 小模型上的微调配方，能否迁移到更大的商用 MoE？

状态：**研究结论与未来验证设计，不构成训练或云任务授权**  
研究截止：2026-08-09（Asia/Seoul）  
适用问题：Qwen3-4B Dense 本地代理 → 一大一小两档商用 MoE；SFT／LoRA；中文小说事实与证据抽取；严格 JSON／Schema 输出

---

## 一页结论

**不能把“4B 上的赢家”直接写成“商用模型上的赢家”。**

公开研究支持把小模型当作廉价的**候选淘汰器**：它能发现明显坏的数据、明显不合适的提示、明显过拟合或格式崩溃的方案，也常能给出粗粒度的数据质量信号。但没有系统研究证明，一整套 4B SFT／LoRA 配方——输出表示、数据配比、提示模板、数据量、学习率和 LoRA 参数——在更大的商用 MoE 上保持同一排序。现有最接近证据反而显示：排名会因模型家族、规模、训练预算、学习率、目标分布和 Dense／MoE 架构而改变。

对本项目，最稳妥的工作定义是：

> **迁移假设 = 待验证的工程假设。迁移候选，不迁移冠军结论。**

4B 可以承担：

- 清除数据错误、冲突标签、重复和越界证据；
- 淘汰大幅落后的候选；
- 发现 JSON、停止、复读、召回崩塌和前态泄漏等失败面；
- 把昂贵的云端对照压缩到 2 个候选。

4B 不应单独承担：

- 在相近候选中选唯一冠军；
- 决定精确数据配比、最佳数据量或训练轮数；
- 把本地最优学习率、batch、LoRA rank／alpha／target modules 复制到商用 MoE；
- 证明严格 JSON 在目标模型上会自然达到生产可靠性；
- 用合成 DEV 代替真实、隔离的最终 blind。

**最低可辩护的跨两档商用模型验证是 4 个逻辑 SFT 臂：**

| 商用目标 | 臂 B：冻结基线 | 臂 W：4B 候选 | 目的 |
|---|---|---|---|
| 商用小档 MoE | 同一真实 Canonical 派生的基线表示 | 同源、只改变一个变量的候选表示 | 判断低成本目标上是否保序 |
| 商用大档 MoE | 同一基线 | 同一候选 | 判断规模与 MoE 交互后是否仍保序 |

如果只跑每档的 4B 赢家，共 2 个任务，那只能证明“能训练、能出结果”，**不能验证排名迁移**。若最终只会部署一档模型，则该档 2 个 SFT 臂是最低排名桥；另一档只做零训练推理探针，不能声称完成了它的微调迁移验证。

项目当前还缺 Production Canonical、真实 final blind、现行训练授权和 Mini／Lite 角色裁定；因此上表是**未来预注册设计**，不是现在开跑的任务单。Mini／Lite 的角色只能写作：**角色冲突待 CZ 对齐**。

---

## 1. 先把“迁移”拆成三件事

同一句“这个结论可迁移”，可能混了三种完全不同的含义：

| 含义 | 例子 | 能否从 4B 直接带走 |
|---|---|---|
| **合同不变量** | 同一字段定义、同一事实边界、同一 evidence 合法性、同一 TRAIN／DEV／blind 隔离 | **可以且应该**。这是任务定义与数据治理，不是模型效果外推 |
| **方向性信号** | 清除错标通常有益；复杂冗长规则可能伤害当前候选；候选 A 明显优于候选 B | **可以带成先验**，仍要在目标模型抽检 |
| **经验赢家与最优数值** | C2 一定胜 A；20% 特殊样本最好；LR=2e-4 最优；rank=32 最优 | **不能直接带走**，必须在目标模型重估 |

这一区分很重要。比如“所有模型都必须遵守同一 Schema”是高置信合同；“某个模型用 SFT 最容易学会这份 Schema”却是低置信经验结论。

---

## 2. 迁移性证据总表

置信度表示“把 4B 观察当成目标模型决策先验”的可信度，不表示该变量本身的重要性。

| 变量 | 4B 上可带走什么 | 不可直接带走什么 | 迁移置信度 | 目标模型处理 |
|---|---|---|---|---|
| 数据权利、来源身份、SHA、位置、证据回填 | 合法性与可回验合同 | 对模型效果的增益幅度 | **高：治理不变量** | 原样执行，不需用模型重证 |
| 明显错标、矛盾标签、泄漏、重复、TRAIN／blind 污染 | “必须修”的判断 | 修复后能提高多少分 | **高：数据正确性** | 进入任何模型前修完 |
| JSON 字段语义与业务边界 | 同一字段应表达什么、空值与 unknown 怎样定义 | 哪种表面序列化最容易学、自然生成能否 100% 合规 | **高／低双层**：语义合同高；学习难度低 | 固定语义；格式尽量交给约束解码与程序 |
| 粗粒度数据质量／样本难度 | 用于清除底部样本、形成候选池 | 精确 top-k 样本集合 | **中** | 4B 粗筛；目标端保留对照 |
| 目标化 instruction 子集 | 同家族、相似预训练与目标分布下的有用方向 | 跨家族、跨候选池的 exact 排名 | **中偏低** | 优先选与目标最相似的 proxy；保留 runner-up |
| 输出表示家族（如 A vs C2_UNIT） | 作为两个待复验候选 | 合成 Dense 上的胜负 | **低到中** | 同一真实 Canonical 机械派生，在目标端做两臂 |
| JSON vs 自然文本这种粗格式方向 | 结构化训练常有总体收益 | 每个下游指标、每种 Schema 的赢家 | **中偏低** | 只把“值得测”带走，不带分数 |
| 输入提示模板（如 P3 C0 vs C2 短任务目的） | 淘汰大幅失败的当前写法 | 相近模板的细排序 | **低** | 在同一 checkpoint 上做零训练配对推理，通常不增加 SFT 任务 |
| 规则数量、示例数量、上下文卡 | 当前写法的具体失败面 | “规则越少越好”等普遍规律 | **低** | 每次只改一个变量；目标端看召回与泄漏 |
| 数据配比／领域权重 | 极端坏配比可淘汰 | 精确最优权重 | **低** | 目标规模重估；不以 validation loss 单独选胜者 |
| 数据量、epoch、重复次数 | 早期学习曲线与过拟合警报 | 最优条目数／token 数／停止点 | **低** | 用目标 checkpoint 曲线或分段评测重估 |
| 学习率、batch、warmup、weight decay | 仅作为搜索范围线索 | 本地最优数值 | **很低** | 采用目标平台／架构适配的初值；相近或翻转时再加一档 LR |
| LoRA rank、alpha、初始化 | 参数化关系与失败范围 | 数值最优点 | **很低** | 与目标 width、参数化和平台实现一起校准 |
| LoRA target modules、router／experts 是否训练 | Dense 上不存在或含义不同 | 任何具体设置 | **不可直接迁移** | 先向供应商核实；黑盒时只能做结果级 A/B |
| 单一综合分 | 只能快速浏览 | 格式、语义、证据错误之间的真实取舍 | **不应迁移** | 始终保留分层指标与 must-not-fail 门 |

### 表后最重要的解释

“数据清洗可迁移”不是因为论文证明同一清洗能在所有模型上提高相同分数，而是因为错标、泄漏和证据越界违反任务定义。相反，“某批样本是 top 5%”属于模型依赖的经验排序，不能当作不变量。

---

## 3. 有没有研究证明“小模型赢家到大模型仍是赢家”？

### 3.1 最短答案

**预训练数据 recipe 有条件性的系统证据；SFT／LoRA 的完整配方没有。**

最强的预训练结果能证明“小实验有预测力”，却也都保留了目标规模验证；SFT 的直接研究只覆盖样本过滤、目标化数据选择、JSON-vs-text 等局部变量，而且已经出现跨家族失败、top-k 不重合、单任务排名翻转。

### 3.2 关键证据

| 研究 | 直接结果 | 对本项目能支持什么 | 关键边界 |
|---|---|---|---|
| [DataDecide，ICML 2025](https://arxiv.org/abs/2504.11393) | 25 种预训练 recipe、14 个规模（4M–1B）、3 seeds。150M 单尺度预测 1B 的成对赢家，约 **80% 判断正确**；不同任务可预测性差异很大，1B seed 波动可达约 2 个准确率点 | 小 proxy 的 pairwise 排序可有实用价值；应报告排序与噪声，不只拟合绝对分数 | 预训练，不是 SFT；同一实验系统，最大 1B；80% 不是保证 |
| [Can Small Training Runs Reliably Guide Data Curation?](https://arxiv.org/abs/2512.24503) | 23 种预训练 recipe、70M–1B。标准 proxy LR 时 Spearman 常低于 .75；特殊 tiny-LR 探针可把多组相关推到 **>.92／.95** | 数据 recipe 与超参有强交互；“同一 LR 公平比较”仍可能选错 | 只到 1B、单轮预训练；tiny-LR 不能直接变成本项目 LoRA 规则 |
| [Superfiltering，ACL 2024](https://aclanthology.org/2024.acl-long.769/) | 124M–1.5B proxy 与 Llama2-7B 的样本排序 Spearman **.679–.893**；但 top-5% 集合重合仅 **.18–.52**。小 proxy 选出的 5%–15% 数据仍可有效训练 Llama2-7B／13B | 4B 可以做粗筛；高全局相关不代表精确头部集合一致 | 三个 instruction 数据集、一个过滤定义；不测多种提示／配比 recipe |
| [LESS，ICML 2024](https://arxiv.org/abs/2402.04333) | Llama2-7B 选 5% 数据可帮助 Llama2-13B 和 Mistral-7B；但 Pythia 14M／410M／1B 选择器用于 Llama2-7B 时，三者中两者低于 random | 同家族或能力匹配时有用；跨家族可失败 | 单 seed 较多；选择器状态、候选池与目标任务都会改变结果 |
| [JsonTuning，ACL Findings 2025](https://aclanthology.org/2025.findings-acl.1232/) | JSON structured tuning 在 LLaMA／Llama2 的 7B→13B 六任务平均上保持总体优势；但 MMLU 单项从 7B 的正增益变成 13B 的负增益 | 粗粒度格式方向可迁移成候选先验 | 不是严格 Schema 保证；单任务与多模板排序会翻 |
| [When Scaling Meets LLM Finetuning，ICLR 2024](https://arxiv.org/abs/2402.17193) | 1B–16B、full FT／prompt／LoRA。loss 常可缩放，但最佳方法随数据量和任务 crossover；LoRA rank 增大通常没有稳定收益，部分 16B 外推失败 | 数据量、微调方法和 rank 不能从 4B 直接锁死 | 两个模型家族与少数任务；不含商用 MoE |
| [Data Mixing Optimization for SFT](https://arxiv.org/abs/2508.11953) | Qwen2.5 0.5B／1.5B、Llama 3B／8B，三类任务、三档 token 预算、21 个配比；最优 domain weights 随模型与预算变化，validation loss 与下游赢家也会脱钩 | 精确数据配比必须按目标模型、预算和目标分布重估 | 公开 Dense 模型；不是本项目 Schema／MoE |
| [Llama 3 技术报告](https://arxiv.org/html/2407.21783) | Meta 用多组小模型筛 data mix，再训练更大候选复验；同报告中，退火数据让 8B 的 GSM8K／MATH 分别 +24.0／+6.4 点，在 405B 上收益却可忽略 | 大幅小模型收益也可能在大模型消失；工业流程仍保留大规模验证 | 主要是预训练末段数据，不是本项目 LoRA |
| [Massive SFT Experiments，2025](https://arxiv.org/abs/2506.14681) | 1,070 个 SFT 模型、12 个约 7–9B base、10 个数据集。相同数据对在不同 base 上可从互补变为中性或冲突；1k vs 20k 没有一致赢家 | SFT 数据效应高度依赖 base 模型；更多数据不必然更好 | 不含 70B／MoE，也非本任务 |

### 3.3 为什么“缩放曲线拟合得好”仍可能选错配方

预测绝对 loss 与预测两个候选谁赢，不是同一个问题。两条曲线都拟合得很好，只要差距小于 seed 噪声、评测噪声或超参交互，排名仍会翻。

[Compute-Efficient Model Ladders](https://arxiv.org/abs/2412.04403) 用同架构、同 data mix 的 190M–1.3B ladder 预测 7B／13B：8 个分类任务中只有 4 个目标准确率误差不超过 2 点，另 4 个平均绝对误差约 6.9 点。对 46 项公开 task-scaling 数据的再分析则发现，只有 18／46（39%）呈平滑可预测趋势；其余包含反向、非单调、噪声和能力突现。[Scaling Laws Are Unreliable for Downstream Tasks](https://arxiv.org/abs/2507.00885)

因此，proxy 结果应以这些量报告：

- pairwise decision accuracy；
- Spearman／Kendall 排名相关；
- top-k overlap；
- winner regret（选错时损失多少）；
- seed／bootstrap 不确定性；
- 跨 LR 是否仍保持方向。

单个最高 F1 小数点不够。

学习率还有一层 LoRA 参数化依赖。[Learning Rate Scaling across LoRA Ranks](https://arxiv.org/abs/2602.06204) 的分析与实验显示，普通初始化／缩放下的最优 LR 会随 rank 和 width 改变；换初始化或 alpha 参数化后，缩放关系也会改变，最优值可相差一个数量级以上。它不能给出本项目的目标 LR，却足以说明“把 Qwen3-4B 的 LoRA LR 数值复制给商用模型”没有可靠依据。

---

## 4. Dense 小模型代理 MoE 的额外风险

### 4.1 结论

Dense→MoE 不只是“模型变大”，而是增加了**路由、专家负载、专家专用正则、容量溢出和 adapter 放置**等新变量。公开研究已经证明，同一微调流程在 Dense 与 MoE 上可能产生明显不同、甚至方向相反的结果；但没有论文直接报告“Qwen3-4B Dense 多套抽取 SFT recipe → 商用 MoE”的排名相关或 Top-1 保留率。

### 4.2 直接证据

| 风险 | 公开证据 | 对本项目的含义 |
|---|---|---|
| 同一 fine-tuning 流程的效果可翻转 | [Efficient Large Scale Language Modeling with MoE](https://arxiv.org/abs/2112.10684) 的全参下游微调中，Dense 几乎全面改善；MoE 在 HellaSwag、PIQA、WinoGrande 的多个尺度上退化。最大 207B MoE 的 HellaSwag 从 70.5 降到 42.2 | Dense 上“有效”的处理方向不是 MoE 保证。此证据是分类任务／全参 FT，不能写成对本项目具体排名的直接预测 |
| 最优 LR／batch 不同 | [ST-MoE](https://arxiv.org/abs/2202.08906) 的 SuperGLUE 网格中，0.8B Dense 与 4.1B sparse 的最佳 LR／batch 组合不同；稀疏模型对小数据也更易快速拟合并过拟合 | 数据候选和训练超参必须解耦。把 Dense 最优 LR 固定到 MoE，可能把好数据测成坏数据 |
| instruction 数量与多样性的边际收益不同 | [Mixture-of-Experts Meets Instruction Tuning](https://arxiv.org/abs/2305.14705) 中，MoE 在直接单任务微调时整体弱于 FLOP 匹配 Dense；加入 instruction tuning 后获益更大并反超 | Dense 上偏好的“窄而集中”与“多任务多模板”排序可能不保留 |
| MoE 内部实现也会改变响应 | 同一研究中，load-balance loss 与 z-loss 在两种 MoE 路由架构上的方向可相反 | “两档都是 MoE”不等于两档可互相代理 |
| adapter 放置决定专门能力与遗忘 | [Expert-Specialized Fine-Tuning](https://arxiv.org/abs/2407.01906) 在 DeepSeek-V2-Lite 上，普通 LoRA、全参 FT 和只调任务相关 experts 的效果不同；Text-to-JSON exact match 约为 67.8、78.8、75.6–78.6 | 同样叫 LoRA，shared／router／routed experts 的 target modules 不同，实际训练容量就不同 |
| 格式 token 可能影响路由 | ESFT 观察到任务间专家选择差异；[Mixtral 报告](https://arxiv.org/abs/2401.04088) 观察到缩进、`Question`、`self` 等句法／模板 token 的路由规律 | JSON 标点、固定字段名、B／T 编号和坐标可能改变专家负载。这是合理推论，不是本项目格式排名翻转的直接实证 |

### 4.3 黑盒商用 MoE 需要承认的未知量

若平台不披露下列信息，就无法用公开论文校正 Dense→MoE 误差：

- LoRA 的 target modules 与 rank 分配；
- router 是否训练或冻结；
- shared experts 与 routed experts 是否适配；
- top-k、expert granularity、capacity factor；
- overflow／drop token 策略；
- load-balance／z-loss、expert dropout；
- seed、数据顺序与训练确定性。

不能取得这些遥测时，正确做法不是猜内部机制，而是在结果层建立“基线 vs 候选”的最小排名桥。

---

## 5. 严格 JSON／Schema：大模型一定更容易吗？

### 5.1 两个方向都不是必然命题

- **4B 学得会 → 大模型一定学得会：不成立。** 大模型通常容量更强，但 tokenizer、聊天模板、对齐数据、MoE 路由、微调实现、截断和解码器都可能不同。
- **4B 学不会 → 大模型也学不会：不成立。** 更强基座或约束解码可能让小模型的语法失败直接消失。
- **大模型学得会 → 小模型一定学得会：也不成立。** 小模型可能容量不足，或把表面模板记住却填错语义。

### 5.2 公开结果

[SchemaBench](https://arxiv.org/html/2502.18878) 含 40,706 个复杂 Schema。Llama 3.2 3B 的 Schema-only／SFT／Schema-RL 通过率约为 28.51%／56.48%／72.50%；Llama 3.1 8B 为 36.45%／60.59%／79.67%。规模通常有帮助，但 SFT 后仍远非结构保证；而在另一项下游函数调用评测里，3B SFT 总分还高于 8B SFT，说明能力并非处处随规模单调。

[SLOT](https://arxiv.org/html/2505.04016) 在统一 LoRA 配方下报告：1B／3B／7B 单用 SFT 的 Schema accuracy 约为 88.9%／94.7%／98.2%；SFT＋XGrammar 约为 96.2%／98.2%／99.5%。同一组实验里，纯约束解码有时提高结构却损伤内容相似度，而 SFT＋约束通常最好。

OpenAI 的 Structured Outputs 官方说明也把 100% Schema 合规归因于**模型训练＋受约束解码**，不是单纯“模型更大”：`gpt-4o-2024-08-06` 配合 strict Structured Outputs 在其复杂 Schema 内部评测达到 100%，而旧 `gpt-4-0613` 低于 40%；生成时会用 CFG 屏蔽非法 token。官方同时提醒，截断、拒答和字段值错误仍可能发生。[Structured Outputs 官方说明](https://openai.com/index/introducing-structured-outputs-in-the-api/)

[JSONSchemaBench](https://arxiv.org/html/2501.10868) 用约 10,000 个真实 Schema 测六套受约束解码引擎，最佳与最差引擎支持的 Schema 数量可相差约 2 倍。这意味着“支持 JSON Schema”也必须验证具体子集、编译失败、过约束和欠约束。

### 5.3 对产品的工程分工

| 层 | 最适合负责什么 | 不该冒充什么 |
|---|---|---|
| SFT／LoRA | 抽哪些事实；主体、状态、证据 ID 与 unknown 怎么填；什么不能填 | 括号、逗号、固定键名永不出错的唯一保证 |
| 约束解码／Structured Outputs | JSON 可解析、键／类型／枚举／层级合法 | 字段值在语义上正确 |
| 确定性程序 | evidence ID 合法性、原文回填、位置、SHA、排序、Schema 二次验证 | 判断证据是否真正支持主张 |
| 独立 evaluator／人工复核 | 事实语义、证据承托、越界与泄漏 | 让生产模型给自己签绿票 |

只要商用 API 支持严格 Schema，训练预算应更多花在“字段里填对什么”，而不是反复教模型输出逗号和括号。

---

## 6. 工业界怎样做

公开成熟案例的共同模式是：

> 小模型多臂筛选 → 较大候选复验 → 目标规模 final eval → 允许按规模调整数据混合与学习率

它是一种常见实践，不是有统一预算比例的行业标准。

- Meta Llama 3 对候选 data mix 训练多组小模型、预测大模型表现，再训练更大候选跑关键 benchmark；同报告的 8B→405B 退火数据失效案例说明他们没有把 proxy 预测当终局。[Llama 3 技术报告](https://arxiv.org/html/2407.21783)
- Ai2 把 Tülu 3 的 8B／70B 后训练路线扩到 405B 时，保留开发集、未见评测和最终标准化评测；405B 的 RLVR 数据从小模型偏好的多样混合改成 MATH-only，并使用更低学习率。[Tülu 3 405B 官方报告](https://allenai.org/blog/tulu-3-405b)、[技术报告](https://arxiv.org/abs/2411.15124)
- DataComp-LM 做了 416 次标准化数据实验；412M／1.4B 对 6.9B 的 10 种数据方法表现相关约为 Pearson .885／.919，但仍实际训练 7B 验证。[DataComp-LM](https://arxiv.org/html/2406.11794)
- DoReMi 用 280M proxy 学领域权重，再训练 8B，平均 few-shot 相比默认配比提高 6.5 点；成功结论来自完整 8B 复验，不是来自 proxy 自身。[DoReMi](https://arxiv.org/abs/2305.10429)

没有可靠一级来源给出“目标大模型必须保留总预算的 X%”这种统一规定。可以迁移的是流程纪律，不是固定百分比。

---

## 7. 本项目的最低成本验证设计

### 7.1 当前证据怎样解释

P3 的四个输入臂使用同一 `C2_FULL update72` checkpoint、同一 Qwen 本地 Dense 代理和同一合成 DEV24：

| 输入臂 | 语义 F1 | 本研究后的解释 |
|---|---:|---|
| C0 极简输入 | 0.894 | 冻结基线 |
| C1 八条规则 | 0.622 | 当前写法是明显失败项，可在本地退出；不能推广成“规则越多越差” |
| C2 短任务目的 | 0.891 | 与 C0 统计上应视为并列候选，不应按 0.003 差距封冠军 |
| C4 确认前态 | 0.825 | 两例前态泄漏是 must-not-fail 风险；当前写法不晋升 |

四臂都 24／24 正常停止、零复读、零触顶，只能说明生成稳定性过门，不能替代语义与证据结论。

需要防止三个“C2”混名：

- `C2_UNIT`：输出合同／表示家族；
- `C2_FULL`：M1 完整答案格式与本地 checkpoint 名；
- P3 `C2 短任务目的`：同一 checkpoint 上的输入提示臂。

M1 比较输出表示，P3 比较输入上下文。不能把两条线合成一句“C2 赢了”。

### 7.2 零训练阶段：不增加 SFT 任务

在数据与授权门齐全后、提交商业训练前，先冻结一组同源诊断样本，在两档目标 base 模型上做：

1. C0 与 P3 C2 短任务目的的配对推理；
2. JSON mode／strict Schema／普通生成三种可用解码路径的能力探针；
3. 空答案、否定、计划 vs 已发生、引语归属、前态泄漏、长上下文和截断探针；
4. 记录精确 endpoint、模型快照、温度、max tokens、Schema 子集和拒答行为。

输入提示通常能在同一权重上 A/B，因此 C0／C2 不需要各训练一个 checkpoint。P3 已经排除的 C1／C4 当前写法不值得花云端 SFT 预算复跑。

### 7.3 最低排名桥：4 个逻辑 SFT 臂

当且仅当 Production Canonical、真实隔离评测、模型角色、预算与执行锁全部就绪：

| 目标模型 | 训练臂 1 | 训练臂 2 | 固定项 |
|---|---|---|---|
| 小档商用 MoE | A 基线或当前正式 baseline | C2_UNIT 或 4B 选出的单变量候选 | 同一 Canonical、相同事实、相同切分、相同目标端训练配置 |
| 大档商用 MoE | 同一 baseline | 同一候选 | 同上；评测分布按裁定后的实际角色预注册 |

推荐优先把昂贵的两个训练臂用在 **P1-01：A vs C2_UNIT**，因为它改变训练输出表示；P1-03 的 C0 vs C2 短任务目的可在每个 checkpoint 上做推理 A/B，不应重复支付训练费。

逻辑上是 4 个臂；平台能否把多臂放在一次提交、是否按 checkpoint／数据版本分别收费，取决于账号能力和 P1-07 的任务口径。**逻辑臂数不能被静默写成 billable task 数。**

### 7.4 三档预算解释

| 预算档 | 训练安排 | 能回答什么 | 不能声称什么 |
|---|---|---|---|
| 烟雾档 | 两档各只训 4B 赢家，共 2 个逻辑臂 | 能否训练、是否严重崩溃、成本与延迟 | 不能验证 4B 排名迁移 |
| 最低可辩护档 | 两档各跑 baseline＋候选，共 4 个逻辑臂 | 每档的 pairwise 排名是否保持；规模间是否翻转 | 不能证明更多 recipe 的全排序 |
| 仲裁档 | 只在持平／翻转的目标档，为两臂增加一档 LR 或独立重复，通常 +2；若带 runner-up，再按相同原则增加 | 区分小差距、seed 噪声与超参交互 | 仍不能替代真实 final blind |

如果 Mini／Lite 裁定后只有一档会正式微调，最低可辩护档可先收缩到该档 2 个训练臂；另一档只保留 base 探针。若两档都要承担不同生产角色，则必须分别建桥，不能用一档替另一档签字。

### 7.5 训练配置怎样省钱又不自欺

- **一次只验证一个变量。** 不要把 4B 上的“最佳格式＋最佳配比＋最佳 LR＋最佳数据量”捆成一个云端 recipe；一旦翻转，无法定位原因。
- **不复制 4B LR。** 第一轮使用目标平台为该模型建议的稳定配置，并把结论写成“在此目标配置下的排名”。若两臂持平或翻转，再只给争议两臂增加相邻一档 LR。
- **数据量先不做完整云端网格。** 若平台提供中间 checkpoint，在同一训练任务的 25%／50%／100% 进度评测学习曲线；若不提供，先在本地缩小范围，目标端只对最终两臂重估停止点。
- **近似并列就按并列处理。** 预注册业务最小有效差 `δ_min`；paired bootstrap 95% CI 含 0，或差值小于 `δ_min`，不得按小数点选冠军。
- **只对争议项加重复。** 明显失败不重复；相近或 rank reversal 才增加 seed／独立任务。
- **保留目标 base。** 微调前后同卷评测，才能分清 SFT 增益、基座差异和灾难性遗忘。

### 7.6 评测不能压成一个总分

冻结同一评测版本，并至少分开报告：

1. 是否生成、停止、触顶、复读、拒答；
2. JSON 可解析率与 Schema 合规率；
3. 逐字 exact；
4. 事实语义 precision／recall／F1；
5. evidence ID、原文、位置、SHA 的合法性与 provenance；
6. evidence 是否在语义上支持事实，以及独立人工复核；
7. 常规分布与 hard subset 的分层结果；
8. 微调前后通用能力／非目标行为退化。

建议 hard subset 至少覆盖：否定、计划 vs 已发生、说话者归属、前态只读泄漏、跨责任区、空事实／unknown、重复 evidence、长上下文截断、相似人物、严格 Schema 和多条证据数组。

生产模型不得给自己的输出签质量绿票；JSON 100% 也不能遮住事实或证据错误。

### 7.7 迁移判定门

对每个目标模型单独判：

- **保序通过**：候选相对 baseline 的方向与预注册假设一致，且差异超过不确定性／`δ_min`；所有 must-not-fail 指标不退化。
- **统计并列**：CI 含 0 或低于 `δ_min`。记录为“未分胜负”，不是 proxy 成功。
- **排名翻转**：目标模型方向相反。此后 Qwen3-4B 只能做该变量的粗筛，最终选优必须包含架构更相近的 proxy 或目标端对照。
- **结构过门、语义失败**：JSON／Schema 合规但语义或 evidence 退化。不得晋升。
- **一档通过、一档失败**：说明存在规模／实现交互；分别维护 recipe，不寻找虚假的统一赢家。

---

## 8. 下一代 proxy 怎样选

模型参数量不是最重要的匹配维度。LESS 等研究表明，一个更小但家族／能力匹配的 selector，可能胜过更大但预训练与目标不匹配的 selector。

建议按以下顺序选择本地代理：

1. 能稳定完成本任务，避免把能力阈值误当 recipe 差异；
2. tokenizer、chat template、role／control／EOS 处理接近目标；
3. base vs instruct 状态与目标微调入口一致；
4. 预训练语料、语言和已有能力接近目标；
5. Dense／MoE 架构、shared experts、top-k 与 adapter placement 尽量接近；
6. 参数规模和本地成本。

理想的廉价筛选不是只换成“另一个 4B”，而是一个小面板：

- 当前 Dense 4B：持续承担快速淘汰；
- 一个经过权重、许可、工具链和硬件核验的小型开放 MoE：专门发现架构交互；
- 商用目标端的最小 pairwise 排名桥：负责最终选优。

当前材料里的 Ling 3.0 Tiny 只有未来稀疏代理占位，精确模型、许可和工具链尚未核验，因此不能把它写成已选 proxy，也不能据此开新实验。

---

## 9. 项目当前能下的决策

| 问题 | 现在的结论 |
|---|---|
| Qwen3-4B 能否继续用 | 能。定位为离线诊断与候选筛查，不是生产效果代理 |
| P3 C0 vs C2 短任务目的 | 0.894 vs 0.891，按并列候选；未来在真实／生产模型做同源推理复验 |
| P3 C1／C4 | 当前写法不晋升；没有理由在同一 Qwen＋DEV24 重跑 |
| A vs C2_UNIT | 仍是 P1-01；必须用同一真实 Canonical、同一目标模型、同一评分做两臂 |
| 商用模型角色 | **角色冲突待 CZ 对齐**；不能擅自指定 Mini 或 Lite 为首发 |
| 当前是否可训练 | 否。没有 Production Canonical；A v2.7 的 74／74 来源本地权利状态仍未知；`may_authorize_training=false`；真实 final blind 不存在 |
| 本报告能否授权云任务 | 不能。它只提供未来的验证合同与费用路线 |

---

## 10. 关键论文与技术报告索引

### 小模型 proxy、数据选择与 downstream scaling

- [DataDecide: How to Predict Best Pretraining Data with Small Experiments](https://arxiv.org/abs/2504.11393)
- [Can Small Training Runs Reliably Guide Data Curation?](https://arxiv.org/abs/2512.24503)
- [Superfiltering: Weak-to-Strong Data Filtering for Fast Instruction-Tuning](https://aclanthology.org/2024.acl-long.769/)
- [LESS: Selecting Influential Data for Targeted Instruction Tuning](https://arxiv.org/abs/2402.04333)
- [When Scaling Meets LLM Finetuning](https://arxiv.org/abs/2402.17193)
- [Data Mixing Optimization for Supervised Fine-Tuning of LLMs](https://arxiv.org/abs/2508.11953)
- [Learning Rate Scaling across LoRA Ranks and Transfer to Full Finetuning](https://arxiv.org/abs/2602.06204)
- [Compute-Efficient Model Ladders](https://arxiv.org/abs/2412.04403)
- [Scaling Laws Are Unreliable for Downstream Tasks](https://arxiv.org/abs/2507.00885)
- [Massive SFT Experiments](https://arxiv.org/abs/2506.14681)

### Dense／MoE 与适配

- [Efficient Large Scale Language Modeling with Mixtures of Experts](https://arxiv.org/abs/2112.10684)
- [ST-MoE: Designing Stable and Transferable Sparse Expert Models](https://arxiv.org/abs/2202.08906)
- [Mixture-of-Experts Meets Instruction Tuning](https://arxiv.org/abs/2305.14705)
- [Expert-Specialized Fine-Tuning for Sparse Architectural Large Language Models](https://arxiv.org/abs/2407.01906)
- [Mixtral of Experts](https://arxiv.org/abs/2401.04088)

### JSON／Schema

- [JsonTuning](https://aclanthology.org/2025.findings-acl.1232/)
- [SchemaBench](https://arxiv.org/abs/2502.18878)
- [SLOT](https://arxiv.org/abs/2505.04016)
- [JSONSchemaBench](https://arxiv.org/abs/2501.10868)
- [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)

### 工业流程

- [The Llama 3 Herd of Models](https://arxiv.org/abs/2407.21783)
- [Tülu 3 405B 官方报告](https://allenai.org/blog/tulu-3-405b)
- [Tülu 3 技术报告](https://arxiv.org/abs/2411.15124)
- [DataComp-LM](https://arxiv.org/abs/2406.11794)
- [DoReMi](https://arxiv.org/abs/2305.10429)

---

## 研究边界

没有找到同时满足这些条件的一级研究：同一批多个 SFT 输出格式／数据配方；约 4B Dense 与更大 MoE；中文 JSON＋逐字证据抽取；LoRA；并报告 Spearman／Kendall、Top-1 保留率或 winner reversal；更没有覆盖隐藏内部实现的商业微调 API。

因此，本报告对“架构与规模会造成交互、不能无条件迁移”具有高置信；对“本项目某个具体候选一定在某个商用模型上翻转”没有直接证据。最小目标端 A/B 的作用，正是补上这块证据空白。

来源：ChatGPT
