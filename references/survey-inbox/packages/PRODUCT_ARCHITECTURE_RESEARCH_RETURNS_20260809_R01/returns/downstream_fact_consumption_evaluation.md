# 结构化事实供给 → 下游创作：承接效率评测方案

研究日期：2026-08-09  
适用范围：中文长篇故事的场景级、章节段落级续写  
文献范围：故事规划生成、RAG 评测、长上下文退化、长篇故事评价、LLM-as-judge

## 一页结论

现有研究没有一项成熟指标，能单独回答“结构化事实是否被长篇创作正确、自然、有效地承接”。可执行的做法是把问题拆成四层：

1. **给得对不对**：当前场景需要的事实有没有进入执行包，包里有多少噪声。
2. **写没写到、守没守住**：剧情义务是否实现，静默约束是否被违反。
3. **有没有真正产生作用**：改变某条事实后，人物行为、事件或状态是否随之正确变化。
4. **写得好不好**：连贯、人物连续性、推进、阅读意愿、风格匹配是否提升。

不建议做一个“总承接分”。硬冲突、剧情义务、素材复述、趣味性不是可互相抵消的误差。正确决策顺序应是：

> 先过正史与状态一致性硬门；再比较必须事实实现率；只在安全候选中比较软质量、成本和延迟。

文献给出的稳定信号也支持“小而够用的执行包”，而不是整库倾倒：

- [DOC](https://aclanthology.org/2023.acl-long.190/) 的叶节点核验，是最接近“逐项计划是否在正文实现”的故事生成指标。
- [PlotMachines](https://aclanthology.org/2020.emnlp-main.349/) 证明要同时看遗漏和重复；覆盖越高并不自动代表故事越好。
- [RAGChecker](https://arxiv.org/html/2408.08067v1) 显示，增加检索条目能提升召回，但最终收益较小且噪声敏感性上升。
- [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) 显示，相关信息在长输入中部时常被利用得更差；结构化键值任务也出现这一现象。
- [ContextCite](https://arxiv.org/html/2409.00729v2) 区分“素材支持了输出”与“素材促成了输出”。后者需要删除、替换或随机子集干预，单看语义相似不能证明。

“最佳事实条数”没有可外推的统一答案。它会随模型版本、场景任务、事实密度、排序、长度和输出预算变化。项目应测自己的剂量曲线，并选择：

> 在硬冲突不变差的前提下，达到最佳方案近似水平的最小事实数。

---

## 1. 与当前产品约束的对齐

本方案按项目材料中的真相层、创作层和执行包边界设计：

- 已确认正文、历史事实和状态是冻结真相；计划不是已发生事实。
- 事实是可消费状态，但不是每条都要在当前场景明说。
- 新创作可以合法出现。不能把“材料中没有”一律判成幻觉。
- 查询结果、临时候选和反事实压力题不能自动写回永久记忆。
- 模型负责语义选择；事实 ID、证据位置、哈希和评测日志由确定性程序维护。
- 生产模型不能给自己的输出签质量绿票。
- 评测不产出单一总分，严重正史冲突也不能被文笔或趣味抵消。

反事实实验只在隔离的评测副本中进行，不修改冻结真相。

---

## 2. 文献到底测了什么

### 2.1 计划／大纲驱动故事生成

| 工作 | 原论文的评价方式 | 能否直接当作事实承接率 | 可移植部分 |
|---|---|---:|---|
| [Plan-And-Write](https://arxiv.org/abs/1811.05701) | 篇内／篇间 trigram 重复；人工评价标题切题、连贯、有趣；另报告 storyline 词的匹配与出现比例 | 弱 | 只能当表面覆盖诊断，不能判断事实是否正确实现 |
| [PlotMachines](https://aclanthology.org/2020.emnlp-main.349/) | 对每个 outline point，统计有多少段提及；精确匹配或超过 20% 的 n-gram 重合；另做人类成对比较 | 部分可以 | 统计每条要点的场景覆盖数，识别 0 次遗漏和多次机械复述 |
| [Re3](https://aclanthology.org/2022.emnlp-main.296/) | 人工判断有趣、整体情节连贯、贴合 premise、像人写；没有正式 outline coverage | 不可以 | 可借用同一 premise 下的盲配对评价，以及硬问题标签 |
| [DOC](https://aclanthology.org/2023.acl-long.190/) | Detailed-Relevant：逐个叶节点判断事件是否发生在责任段落或紧邻前后段；DOC 为 58.5%，无控制版本为 37.8% | 最接近 | 给必须事实指定责任场景，检查该场景 ±1 是否正确实现并保存证据跨度 |
| [EACL 2024：Precise Outline-Controlled Generation](https://aclanthology.org/2024.eacl-long.145/) | DV 看不同大纲项的句子相似度分布是否分离；PD 看峰值位置是否分散；CD 用重建大纲与原大纲的 ROUGE-L | 可作辅助 | 检查使用位置是否挤在局部、是否快速遗忘；不能代替事实正确性核验 |

几个容易写错的口径：

- Plan-And-Write 的 Fidelity 是对标题切题，不是对 storyline 忠实。
- Re3 的 Relevant 是对 premise 忠实，不是逐项 outline coverage。
- PlotMachines 名为 Coverage 的 ROUGE 是与金标准故事的重合，不是大纲覆盖率。
- DOC 的 Detailed-Relevant 才是明确的逐叶节点事件实现核验。

DOC 同时发现更强的控制可能让故事更窄、更重复。PlotMachines 也出现“更像是在使用大纲，却更爱重复要点、流动性更差”的情形。因此，原始覆盖率不能当主目标。

### 2.2 RAG 的“上下文利用率”能搬多少

RAG 文献里至少有四个不同问题，名称很像，但证据强度不同：

| 层级 | 典型指标 | 能回答 | 不能回答 |
|---|---|---|---|
| 供给相关性 | Context Precision | 输入选料是否相关、排序是否合理 | 模型有没有读 |
| 供给完整性 | Context Recall | 任务必需信息是否给齐 | 模型有没有用 |
| 输出承接／支持 | Context Utilization、Faithfulness | 输出是否承接已提供事实，输出主张是否有材料支持 | 素材是否促成了输出 |
| 贡献归因 | ContextCite、删除／反事实干预 | 改动某条素材是否改变输出分布或可观察后果 | 不能证明模型有人的推理意识 |

[RAGAS](https://aclanthology.org/2024.eacl-demo.16/) 的 Context Precision、Context Recall、Faithfulness 适合拆分检索与生成问题。[RAGChecker](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract-Datasets_and_Benchmarks_Track.html) 进一步给出 claim-level 的 Context Utilization、噪声敏感性和幻觉诊断。

这些方法可以移植原子主张拆分、蕴含／矛盾核验和分层归因，却不能照搬“所有输出主张都必须被上下文支持”。开放式创作允许出现材料未枚举的新动作、对白和细节。项目真正要拦的是：

- 与冻结历史或状态冲突；
- 把未确认信息非法回填成“过去早已发生”；
- 无授权地产生会改变长期状态的高影响承诺；
- 把干扰项误写入当前世界状态。

### 2.3 “喂多少条”没有通用答案

[Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) 在 10／20／30 文档问答和 75／140／300 个 JSON 键值条目中移动目标位置，多种模型呈现开头、结尾较好，中部较差的 U 形曲线。模型差异很大，论文不能给出小说事实卡的统一上限。

[RAGChecker](https://arxiv.org/html/2408.08067v1) 把检索 chunk 数从 5 增到 20 时，claim recall 从 61.5 升到 77.6，faithfulness 从 88.1 升到 92.2，但总体 F1 只从 51.7 升到 53.4，noise sensitivity 从 34.0 升到 35.4。更多材料同时带来更高召回和更高噪声风险。

[Same Task, More Tokens](https://aclanthology.org/2024.acl-long.818/) 固定真正需要的信息，只增加无关文本，平均准确率随长度明显下降。[Context Length Alone Hurts LLM Performance Despite Perfect Retrieval](https://aclanthology.org/2025.findings-emnlp.1264/) 进一步报告，即使目标证据已被精确取回，长输入仍可让不同任务的表现下降。

[Chroma Context Rot](https://www.trychroma.com/research/context-rot) 对 18 个模型做了更广的工程测试，也观察到长度、低相似度和干扰项会恶化表现；其[复现仓库](https://github.com/chroma-core/context-rot)公开。它是技术报告，不是同行评审论文，且任务多为检索、问答、复制，证据等级低于前述论文。

可下的结论是“本地测剂量曲线”，而不是“第 N 条以后一定坏”。

### 2.4 长篇续写与 LLM 裁判

故事自动评价仍不稳定：

- [OpenMEVA](https://aclanthology.org/2021.acl-long.500/) 和 [HANNA](https://aclanthology.org/2022.coling-1.509/) 都显示，传统重合与相似度指标很难识别篇章级因果、时间和连贯问题。
- [Do Language Models Enjoy Their Own Stories?](https://aclanthology.org/2024.tacl-1.62/) 发现，较好的 LLM 裁判在系统平均排名上可接近人类，但单篇故事相关仍弱；裁判解释还可能含无依据断言。
- [LongStoryEval](https://aclanthology.org/2025.acl-long.799/) 覆盖平均约 12.1 万 token 的 600 本书。整书一次评价较差，按章评价后汇总或先做高质量摘要更稳；零温度也不能保证裁判结果固定。
- [Large Language Models are not Fair Evaluators](https://aclanthology.org/2024.acl-long.511/) 证明成对裁判存在位置偏差，交换 A／B 顺序可能改变赢家。
- [CheckEval](https://aclanthology.org/2025.emnlp-main.796/) 显示，把宽泛 Likert 打分拆成可核查的布尔清单，可以提高裁判一致性并降低方差。

因此，LLM 裁判适合整批低成本筛选，不适合给单篇输出签生产绿票。硬一致性要逐条核验；软质量用盲配对；抽一批中文长篇专家样本做校准。

---

## 3. 评测对象与标注合同

### 3.1 每条事实先分角色

| 标签 | 定义 | 输出义务 | 例子 |
|---|---|---|---|
| MUST_REALIZE | 当前场景必须形成可观察后果的剧情义务 | 必须正确实现，不要求逐字复述 | “债务今晚到期”应促成人物立即筹款或应对 |
| MUST_RESPECT | 已确认历史、人物知情、关系、能力、时序或世界规则 | 可以不明说，但绝不能违反 | 某人尚不知道秘密，不能无解释直接利用它 |
| OPTIONAL_SUPPORT | 与场景有关，可提升细节、伏笔或人物层次 | 允许使用，也允许不使用 | 场所气味、旧物、次要关系线索 |
| IRRELEVANT_CONTROL | 与本场无关但表面形式相近的干扰项 | 应被忽略 | 另一地点、另一时期的非当前状态 |

冲突或过期控制项只能用于隔离的合成压力题，不得混入真实冻结真相。

### 3.2 “使用”不是一个二值词

对每条事实与输出的关系记录四态：

| 状态 | 判定 |
|---|---|
| 正确实现 | 事实产生了正确事件、行为、状态或约束效果 |
| 仅表面提及 | 改写或点名事实，但没有叙事作用 |
| 歪曲／矛盾 | 提到了事实，却实现错误、时态错、主体错或与真相冲突 |
| 未出现 | 没有显式承接；对 OPTIONAL 和部分 MUST_RESPECT 可能完全合法 |

每个“正确实现”或“冲突”判断都要保存：事实 ID、输出证据跨度、责任场景 ID、判定标签、裁判版本。

### 3.3 记号

- \(R\)：当前任务的 MUST_REALIZE 集合。
- \(C\)：当前任务的 MUST_RESPECT 集合。
- \(O\)：OPTIONAL_SUPPORT 集合。
- \(D\)：IRRELEVANT_CONTROL 集合。
- \(S\)：某实验臂实际提供的事实集合。
- \(Y\)：续写中抽取出的原子事件、状态与主张。
- \(e(f,Y)=1\)：事实 \(f\) 在续写中被正确实现。
- \(x(f,Y)=1\)：事实或约束 \(f\) 被续写违反。

---

## 4. 指标清单

文献原指标、移植改造和本报告新增指标分开标注，避免把项目定义误归给论文。

### 4.1 输入供给层

| 名称 | 定义与计算 | 用途 | 来源 |
|---|---|---|---|
| Required Supply Recall，必需供给召回 | \(\lvert R\cap S\rvert/\lvert R\rvert\)；约束也另算 \(\lvert C\cap S\rvert/\lvert C\rvert\) | 判断漏用来自选料还是生成 | RAGAS Context Recall 的创作改造 |
| Supply Precision，供给精度 | \(S\) 中属于 \(R\cup C\cup O\) 的条数 ÷ 供给总条数 | 衡量执行包噪声 | RAGAS／RAGChecker Context Precision 的创作改造 |
| Fact Token Share，事实 token 占比 | 结构化事实 token ÷ 总输入 token | 把条数和真实长度分开 | 本报告建议 |
| Critical Position，关键事实位置 | 每条 \(R\cup C\) 在执行包中的归一化位置 0–1 | 分析中部遗忘 | Lost in the Middle 启发 |

### 4.2 下游承接与安全层

| 名称 | 定义与计算 | 越高是否越好 | 来源 |
|---|---|---:|---|
| Available Required Utilization，可用必需事实承接率 | \(\sum_{f\in R\cap S} e(f,Y) / \lvert R\cap S\rvert\) | 是 | RAGChecker Context Utilization 的创作改造 |
| End-to-End Required Realization，端到端必须实现率 | \(\sum_{f\in R} e(f,Y) / \lvert R\rvert\) | 是 | DOC Detailed-Relevant + RAG 分层诊断 |
| Local Responsibility Hit，责任场景局部命中率 | 在预注册责任场景 ±1 内正确实现的 MUST 条数 ÷ 有责任场景的 MUST 条数 | 是 | DOC 的直接移植 |
| Constraint Violation Rate，约束违反率 | \(\sum_{f\in C}x(f,Y)/\lvert C\rvert\)；同时分报“已供给约束”和“未供给约束” | 否 | 项目改造 |
| Zero-Hard-Conflict Pass，无严重冲突通过率 | 不含任何确认历史、状态、知情、关系、规则或时序硬冲突的续写数 ÷ 总续写数 | 是 | Re3／DOC 问题标签 + 项目硬门 |
| Distortion Rate，歪曲率 | 被提及但主体、时间、否定、因果或状态实现错误的事实数 ÷ 被提及事实数 | 否 | PlotMachines／DOC 的项目补充 |
| Optional Meaningful Uptake，可选素材有效采纳率 | 在行动、情绪、因果、伏笔或状态中产生可定位作用的 OPTIONAL 条数 ÷ 已供给 OPTIONAL 条数 | 仅诊断 | RAGChecker CU 的创作改造 |
| Parroting Rate，机械复述率 | 只有复述、没有叙事作用的事实—输出连接数 ÷ 全部事实—输出连接数 | 否 | PlotMachines 重复分析的项目改造 |
| Scene Spread，每事实场景覆盖数 | 对每条事实统计出现于 0／1／2／3+ 个场景的分布 | 不是单调目标 | PlotMachines 的直接移植 |
| Distractor Adoption Rate，干扰采纳率 | 被续写错误写入当前状态的控制项数 ÷ 已供给控制项数 | 否 | RAGChecker noise sensitivity 的创作改造 |
| Unsupported Canonical Commitment Rate，未授权正史承诺率 | 无计划或历史授权、却会改变长期状态的新增主张数 ÷ 输出中的高影响新增主张数 | 否 | FActScore 原子拆分思路 + 项目边界 |

其中，可选素材有效采纳率不能被当作越高越好。把全部背景强行写进正文通常会制造说明书式堆料。

统一约定：分母为 0 时记 NA，不记 0 或 1。A0 没有提供 MUST_REALIZE，因此可用必需事实承接率为 NA；端到端必须实现率仍可计算，用来观察模型是否从前文或先验碰巧实现义务。

### 4.3 因果与位置诊断层

| 名称 | 定义与计算 | 用途 | 来源 |
|---|---|---|---|
| Counterfactual Switch Rate，成对切换率 | 同一场景只把关键事实 A 改为等长、同类、同样合理的 B；两版输出都产生预注册的对应后果时记 1，取平均 | 判断事实是否真的改变续写 | ClashEval 思路的创作改造 |
| Leave-One-Out Quality Delta，单事实删除差 | 删除事实 \(f\) 前后的必须实现、安全与软质量变化 | 判断必要性；容易被冗余事实低估 | ContextCite／删除实验 |
| Attribution Top-k Drop | 删除归因最高的 k 条后，原输出 log probability 的下降 | 有 token 概率的模型可用 | ContextCite 原指标 |
| Position Sensitivity，位置敏感度 | 同一关键事实放在开头／中部／结尾时，核心指标的最大差或方差 | 诊断布局脆弱性 | Lost in the Middle 的项目改造 |

ContextCite 需要多次随机删除和原输出概率，成本可到普通生成的数十倍；它解释的是固定原输出的概率，不直接评价重新生成故事的质量。闭源模型或没有 token 概率时，优先做成对反事实切换。

### 4.4 软质量与效率层

软质量采用同一现场的 A／B 盲配对，每个维度输出 A 胜／B 胜／平手：

| 名称 | 判定问题 |
|---|---|
| 全局连贯胜率 | 因果、时间和场景转接哪一版更通顺 |
| 人物连续性胜率 | 动机、知情、关系和行为演进哪一版更可信 |
| 剧情推进胜率 | 哪一版真正改变故事状态，而非复述、绕圈或机械塞料 |
| 阅读意愿胜率 | 哪一版更让读者愿意继续读 |
| 风格匹配胜率 | 哪一版更符合已确认的叙述风格和角色声音 |
| 长度控制胜率 | 两版字数匹配后，偏好是否仍存在 |

效率另报：

\[
\text{Marginal Fact Utility}
=
\frac{\Delta\text{核心指标}}
{\Delta\text{事实条数或每 1k 输入 token}}
\]

它只用于画剂量曲线，不与安全分合成。

---

## 5. 可直接执行的实验

### 5.1 评测单元

主评测单位是“独立故事现场”，不是事实条数、随机种子、裁判票或输出段落。

每个现场冻结：

- 最近正文与必要的历史摘要；
- 当前场景目标、允许推进范围、结束条件；
- 完整候选事实池与稳定事实 ID；
- MUST_REALIZE、MUST_RESPECT、OPTIONAL_SUPPORT、IRRELEVANT_CONTROL 标签；
- 每条 MUST_REALIZE 的可观察后果和责任场景；
- 每条 MUST_RESPECT 的禁止状态；
- 生成模型版本、system prompt、采样参数、输出长度；
- 评测裁判版本和评分规则版本。

建议输出长度固定在 1,200–1,800 个中文字符。整书评价留给后续压力轮，不用于这轮选择事实包策略。

### 5.2 事实池

每个现场准备一个固定母池，推荐 32 条：

- 4 条 MUST_REALIZE；
- 8 条 MUST_RESPECT；
- 12 条 OPTIONAL_SUPPORT，按场景相关度分成高／中两档；
- 8 条 IRRELEVANT_CONTROL，表面形式相近但与当前任务无关。

若真实现场不足 32 条，不复制事实，改用同样比例的可用母池，并同时报告条数与 token 数。所有实验臂都从同一母池取子集。

### 5.3 实验 A：事实数量剂量曲线

先用同一角色感知排序，构造真子集：

| 臂 | 供给 | 目的 |
|---|---|---|
| A0 | 0 条结构化事实 | 估计无事实地板，只作诊断 |
| A1 | 12 条：全部 MUST_REALIZE + MUST_RESPECT | 最小充分包 |
| A2 | 16 条：A1 + 4 条高相关 OPTIONAL | 测少量增益 |
| A3 | 24 条：A2 + 8 条中相关 OPTIONAL | 测边际收益 |
| A4 | 32 条：A3 + 8 条 IRRELEVANT_CONTROL | 测噪声与过载 |

A1 必须是 A2 的真子集，A2 必须是 A3 的真子集，A3 必须是 A4 的真子集。不能为每个 K 重新挑一套“最优事实”，否则数量与选择质量混在一起。

可加一个只用于机理诊断的 A1-PAD：事实仍为 A1，但用不含语义承诺、长度与 A4 匹配的中性结构填充。A4 变差而 A1-PAD 不变，问题更像事实竞争／噪声；两者都变差，输入长度本身可能是主因。中性填充也可能影响模型，结果只能解释为诊断信号。

### 5.4 实验 B：固定数量，只改选择策略

剂量轮选出安全范围后，把 K 固定为 16 或剂量轮的候选最小值，比较：

| 臂 | 选择策略 |
|---|---|
| B1 | 语义相似 top-k：只按当前场景文字与事实的相似度 |
| B2 | 角色感知选择：MUST_REALIZE、MUST_RESPECT 强制进入，OPTIONAL 再按人物／地点／时间／目标相关度排序 |
| B3 | 随机选择：同一母池、同 K、同 token 预算，作为 sanity control |

若项目已有当前启发式，把 B1 替换成真实现行策略。主 A/B 应预注册为“现行策略 vs 角色感知策略”；随机臂只作校验，不进入生产决策。

### 5.5 实验 C：位置诊断

集合、条数、文本和输出预算全部相同，只把关键事实块放在：

- 输入前段；
- 输入中段；
- 输入末段，紧邻续写指令。

用 Latin square 让每个现场均衡分配三种位置。记录 Position Sensitivity，并检查 MUST_REALIZE 与 MUST_RESPECT 是否在中部下降。这个实验诊断布局，不替代数量和选法实验。

### 5.6 实验 D：反事实承接

另建 12–20 个隔离压力现场。每个现场挑一条真正会改变行为的关键事实，制作等长、同类型、同样合理的 A／B：

- A：债务今晚到期；
- B：债务七天后到期。

其余输入完全相同。预注册可观察后果，不要求固定文案：

- A 应出现立即筹款、逃避、谈判或其他即时应对；
- B 允许延后计划，不应无缘无故按“今晚到期”行动。

两版都产生正确方向后果，才记成对切换成功。若改一条事实导致无关人物、语气或剧情目标大面积漂移，另记“无关溢出”。

### 5.7 生成控制

- 同一模型快照、system prompt、前文、场景任务、输出上限、温度和 top-p。
- 支持 seed 时做配对 seed；不支持时每臂生成 2 个独立样本。
- 两臂输出长度上限一致，报告实际字符数。
- 条件名、事实数和策略名不进入裁判输入。
- 事实顺序在数量轮固定；位置轮才主动改位置。
- 每次运行保存提示版本、事实 ID 顺序、token 数、模型版本、采样参数和原始输出。

---

## 6. 评分协议

### 6.1 自动核验链

对全部输出执行：

1. 把续写拆成原子事件、状态、知情、关系与时间主张。
2. 对 MUST_REALIZE 逐条判断：正确实现／表面提及／歪曲／未出现，并给证据跨度。
3. 对 MUST_RESPECT 逐条判断是否冲突。
4. 抽取可能影响长期状态的新主张，只判“合法新创作、未授权高影响承诺、非法历史回填”，不把所有新内容当错误。
5. 检查 OPTIONAL 是否有叙事作用，检查控制项是否被错误采纳。
6. 程序回验裁判引用的输出片段和事实 ID 是否真实存在。

事实核验问题写成窄布尔清单，不让一个宽泛 1–5 分同时混入多个标准。示例：

- “续写是否让 F017 的预注册后果发生？是／否；引用证据。”
- “续写是否与 C044 的人物知情状态冲突？是／否；引用证据。”
- “这处新增主张是否改变后续章节必须遵守的长期状态？是／否。”

### 6.2 软质量盲配对

同一现场的 A／B 并排；逐维度问 A 胜／B 胜／平手，并要求引用输出片段。交换左右顺序再判一次：

- 两次都指向同一内容，才记为稳定胜；
- 换序后翻票，记为不稳定／待人工；
- 不允许整体文笔抵消硬冲突；
- 裁判尽量与生成模型不同家族；
- LLM 结果只在整批层面使用。

### 6.3 人类校准

开发集：

- 15–20 对 A／B；
- 3 位熟悉中文长篇／网文的标注者共同修订规则；
- 这批不进入正式成绩。

冻结规则后的校准集：

- 至少 60 对独立 A／B；
- 每对 3 人独立判断，分歧再调解；
- 同时放入人名错换、已死亡人物复活、知情泄漏、时间倒置、关系重置、故意拉长、文笔漂亮但遗漏硬义务等压力题；
- 随机样本和压力题分开报告。

至少报告：

- 人—人一致率与 Krippendorff α 或 Gwet AC1；
- LLM 对人工最终票的三分类混淆表和 macro-F1；
- 严重冲突召回率；
- A／B 双顺序一致率；
- 按体裁、长度、事实密度分层的误差。

LLM 是否可用，不设一个凭空的统一正确率门槛。更合理的门是：它与人工最终票的一致性不能明显低于单个专家与其余专家共识的一致性；严重冲突召回率单独设高门。

---

## 7. 样本量与统计

### 7.1 推荐节奏

| 轮次 | 样本 | 用途 |
|---|---|---|
| 管线试跑 | 12 个独立现场 × 5 臂 × 每臂 2 次 = 120 个输出 | 查标注、日志、成本和裁判故障，不做产品定版 |
| 探索筛选 | 40 个独立现场 × 候选臂 × 每臂 2 次 | 估计效应、平手率、方差，筛到两种策略 |
| 正式 A/B | 新的 120 个独立现场 × 2 臂 × 每臂 2 次 = 480 个输出 | 检测约 65／35 量级的稳定偏好，并留平手余量 |
| 人类校准 | 规则开发 15–20 对；冻结后至少 60 对，每对 3 人 | 校准自动裁判 |

若资源只够一轮，可做 48 个独立现场 × 5 个剂量臂 × 每臂 2 次，共 480 个输出；自动清单评全部，人工只评候选最优与最小安全臂。它适合发现中等效应和画剂量曲线，不足以确认 60／40 这类小偏好。

样本量说明：

- 配对连续指标的标准化效应 \(d=0.5\) 约需 34 个独立现场，\(d=0.4\) 约需 50 个左右。
- 对非平手胜负做双侧检验时，真实 65／35 偏好约需 90 个非平手现场；若有约 15% 平手或剔除，准备约 106 个，取 120 较稳。
- 若只期望 60／40 的小提升，约需 199 个非平手现场，实际应准备约 230–250 个。

这些是功效规划建议，不是文献给出的固定规模。先用探索轮的真实平手率和配对差异做 bootstrap／模拟，再冻结正式 N。

### 7.2 统计方法

- 独立单位是故事现场；两个随机种子、多个事实、多个裁判票不能虚增 N。
- 多个现场来自同一书／同一作者时，用书或作者做聚类层。
- 二分类硬门：两臂可用 McNemar；有重复生成时用含现场随机截距的逻辑回归。
- 连续／序数指标：先在现场内汇总，再做配对 bootstrap 或混合效应模型。
- A／B 胜负：报告胜／平／负和 cluster bootstrap 95% 置信区间；多策略排序可用 Bradley–Terry。
- 只预注册一个主对比和少量共同主指标；其余计划比较用 Holm 校正。
- 均值必须连同 95% 置信区间、样本数、平手数和失败数一起报。

---

## 8. 生产决策规则

不要选“利用率最高”的臂。按下面顺序选：

1. **硬门**：严重正史冲突率不得劣于对照；置信区间上界不能越过预注册容忍差。
2. **任务门**：端到端必须实现率和责任场景局部命中率不得低于最佳安全臂的非劣界。
3. **质量门**：在通过前两门的候选中，人物连续性、剧情推进和阅读意愿至少有一个稳定改善，其他主维度不出现明确恶化。
4. **最小化**：选择满足三道门的最小 K；若两个 K 无明显差异，选输入更短、延迟更低的。
5. **分场景策略**：若不同任务类型的最佳 K 差异大，不强行给全产品一个固定条数；按场景义务数、约束数和可选素材边际收益决定预算。

若团队还没有业务容忍差，可把下面数值当作试运行起点，而不是论文结论：

- 严重正史冲突率：候选臂相对对照的绝对增幅，其单侧 95% 置信上界不超过 5 个百分点；
- 端到端必须实现率：候选臂相对最佳安全臂的下降，其单侧 95% 置信下界不低于 −5 个百分点；
- 软质量主指标：在非平手现场中的稳定胜率，双侧 95% 置信下界高于 50% 才宣称更优；
- 置信区间过宽而无法过门时，结论是“证据不足”，不是“等效”。

正式实验前应按真实错误成本和探索轮方差冻结这些界值；不能看完结果再改。

推荐把最终结果画成两条互不合并的曲线：

- 安全／任务曲线：K → 冲突率、必须实现率、噪声采纳率；
- 质量／成本曲线：K → A／B 偏好、输入 token、延迟、成本。

决策点是安全曲线过门且质量收益开始变平的最小 K。

---

## 9. 不建议采用的做法

- **所有供给事实都当分母**：静默约束和可选背景未被明说可能完全正确。
- **把提及等同于使用**：机械复述能让覆盖率虚高。
- **把不在材料中的新内容都判幻觉**：开放创作需要合法新动作、对白和细节。
- **只看 ROUGE／BLEU／embedding**：它们难识别主体、否定、时间、知情和因果错误。
- **一次评价整本书**：长篇裁判容易给泛化评论并漏掉细节。
- **让生成模型单次自评**：位置、长度、自偏好和零温度波动都会影响结果。
- **同时改数量、选法、排序和模板**：无法知道提升来自哪里。
- **把随机种子、事实条数或裁判票当独立样本**：会造成伪重复。
- **从 QA 或本地代理模型直接推出小说阈值**：任务、模型与输入合同不同，不能外推。
- **把多维误差压成一个总分**：严重冲突不能被文笔抵消。

---

## 10. 最小可执行清单

评测开始前：

- [ ] 选 12 个独立现场做管线试跑。
- [ ] 每现场冻结前文、任务、32 条母池和事实 ID。
- [ ] 标注 4 类事实、可观察后果、责任场景和禁止状态。
- [ ] 冻结 5 个剂量臂，保证真子集关系。
- [ ] 冻结模型、提示、输出长度与两个随机样本。
- [ ] 冻结硬门、共同主指标和唯一主对比。

生成后：

- [ ] 全量做原子主张拆分、事实证据对齐和硬冲突核验。
- [ ] 全量计算供给召回、供给精度、必须实现、约束违反、噪声采纳和复述。
- [ ] 候选臂做双顺序盲配对。
- [ ] 抽至少 60 对做三专家校准。
- [ ] 按故事现场汇总，报告 95% 置信区间。
- [ ] 选择通过硬门且与最佳安全臂非劣的最小 K。

---

## 11. 关键论文与资料链接

### 故事规划与大纲承接

- [Plan-And-Write: Towards Better Automatic Storytelling](https://arxiv.org/abs/1811.05701)
- [PlotMachines: Outline-Conditioned Generation with Dynamic Plot State Tracking](https://aclanthology.org/2020.emnlp-main.349/)
- [Re3: Generating Longer Stories With Recursive Reprompting and Revision](https://aclanthology.org/2022.emnlp-main.296/)
- [DOC: Improving Long Story Coherence With Detailed Outline Control](https://aclanthology.org/2023.acl-long.190/)
- [Advancing Precise Outline-Conditioned Text Generation with Task Duality and Explicit Outline Control](https://aclanthology.org/2024.eacl-long.145/)

### RAG、事实利用与贡献归因

- [RAGAS: Automated Evaluation of Retrieval Augmented Generation](https://aclanthology.org/2024.eacl-demo.16/)
- [RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract-Datasets_and_Benchmarks_Track.html)
- [ContextCite: Attributing Model Generation to Context](https://arxiv.org/abs/2409.00729)
- [ALCE: Enabling Large Language Models to Generate Text with Citations](https://aclanthology.org/2023.emnlp-main.398/)
- [FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation](https://aclanthology.org/2023.emnlp-main.741/)

### 长上下文退化

- [Lost in the Middle: How Language Models Use Long Contexts](https://aclanthology.org/2024.tacl-1.9/)
- [Same Task, More Tokens: the Impact of Input Length on the Reasoning Performance of Large Language Models](https://aclanthology.org/2024.acl-long.818/)
- [Context Length Alone Hurts LLM Performance Despite Perfect Retrieval](https://aclanthology.org/2025.findings-emnlp.1264/)
- [Context Rot 技术报告](https://www.trychroma.com/research/context-rot)

### 故事质量与 LLM-as-judge

- [OpenMEVA: A Benchmark for Evaluating Open-ended Story Generation Metrics](https://aclanthology.org/2021.acl-long.500/)
- [HANNA: A Benchmark for Human-aligned Automatic Evaluation of Narrative Generation](https://aclanthology.org/2022.coling-1.509/)
- [Do Language Models Enjoy Their Own Stories?](https://aclanthology.org/2024.tacl-1.62/)
- [LongStoryEval: A Comprehensive Benchmark for Long Story Evaluation](https://aclanthology.org/2025.acl-long.799/)
- [Large Language Models are not Fair Evaluators](https://aclanthology.org/2024.acl-long.511/)
- [CheckEval: Robust Evaluation of Large Language Model Outputs through Checklist](https://aclanthology.org/2025.emnlp-main.796/)

---

## 12. 最简建议

若团队现在只做一件事，就做这套：

> 12 个现场跑通管线 → 40 个现场筛 K 和选法 → 新 120 个现场比较现行策略与角色感知最小包 → 自动裁判全量双顺序盲评 → 60 对三专家校准 → 硬冲突单独设门 → 在安全候选里选最小 K。

这样能同时回答三件不同的事：选料是否漏了、模型是否承接了、承接后故事是否更好；也不会把“复述更多素材”错当成“创作更成功”。
