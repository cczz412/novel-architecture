结论：你们观察到的“能发现真错，但约 1/3 修正建议会误改”并不反常。文献显示，LLM 更适合充当“提出可疑点的高召回检测器”，还不足以单独承担“确定错误并生成正确补丁”。建议保留“只挂建议、不自动改”，再把诊断、修复和置信路由彻底拆开。

截至 2026 年 8 月，也没有可信证据表明“跨家族评审固定强 X%”。模型家族只是错误多样性的粗代理；真正该测的是每个审计员在你们错误类型上的 precision/recall、边际增益和错误相关性。

## 1. LLM-as-judge 的可靠性

| 问题                 | 2024–2026 实证                                               | 对你们的含义                                                 |
| -------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 自我偏好             | NeurIPS 2024 中，GPT-4 对自己的生成有 73.5% 识别率；识别能力和自我偏好显著相关。但这主要来自开放式摘要偏好，不能直接外推到有原文证据的事实核验。[Panickssery et al., 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/7f1f0218e45f5414c79c0679633e47bc-Abstract-Conference.html) | 隐藏“由 A/B 生成”、模型名和原始推理链，仍是低成本防偏措施。  |
| 位置偏差             | 15 个 judge、超过 10 万次评审中，Claude 3.5、GPT-4、GPT-4o 的 pairwise 位置一致率约 76%–83%，即调换顺序后约 17%–24% 的判断不一致；listwise 更差。[Shi et al., IJCNLP 2025](https://aclanthology.org/2025.ijcnlp-long.18/) | 若还在比较“原项 vs 修正项”，必须双向换序；更好的做法是避免比较，改成逐项 `SUPPORTED / CONTRADICTED / INSUFFICIENT`。 |
| 长度/风格偏差        | 仅改变“简洁/详细”提示，GPT-4 judge 的原始胜率可从 22.9% 变到 64.3%；长度校正后收窄至 41.9%–51.6%。[Length-Controlled AlpacaEval, COLM 2024](https://arxiv.org/html/2404.04475v2) | 不要让 judge 把“更详细的修正说明”当成“更正确”。核验输入应只保留原子事实、必要上下文和证据。 |
| 困难事实判断上限     | JudgeBench 的刻意困难客观题对中，Claude 3.5 准确率约 64.3%，GPT-4o judge 约 56.6%，多 agent ChatEval 仅 34.0%。[JudgeBench, ICLR 2025](https://openreview.net/forum?id=G0dksFayVq) | “多一个 judge”不等于可靠金标，尤其在双方答案都很像、仅一个条件或时间点不同的时候。 |
| 事实场景中的家族效应 | 2026 年 source-grounded RAG 配对实验固定同一候选答案后，匹配生成器身份的 judge recall 效应仅 −0.5pp，95% CI [−2.7,+1.7]；没有发现显著同模型宽松。[Eval-Pair Matrix，预印本](https://arxiv.org/html/2607.10626v1) | 有明确原文证据时，来源模型身份可能远不如证据质量、错误类型和判据重要。 |

### 跨家族到底强多少

目前最诚实的答案是：没有可迁移的固定增益。

- 最接近直接对照的 TMLR 2026 实验中，同模型三次投票与名义上的“跨模型面板”在 MT-Bench 都是 65.25%，即 **+0.0pp**；后者还包含两款 Gemini，不能算纯三家族对照。[Soumik, TMLR 2026](https://openreview.net/forum?id=QF4lAmG4zc)
- 上述 Eval-Pair Matrix 在更接近你们的原文事实核验场景中，严格配对效应也接近零。[Selvam & Ghosh, 2026](https://arxiv.org/html/2607.10626v1)
- 正面证据来自 PoLL：Command-R、Claude Haiku、GPT-3.5 三模型 jury 相对单一 GPT-4，与人工的一致性 κ 在 NQ/TQA/HotpotQA 分别提高 13.6、6.5、3.7pp。但实验没有“同家族三模型 jury”消融，因此增益混合了模型数、能力、聚合方式和家族差异。[PoLL, 2024](https://arxiv.org/html/2404.18796v2)
- 跨家族也可能高度共错：2026 九 judge 研究中，同家族错误相关约 .435–.437，跨家族平均 .389，但最高跨家族组合达到 .603。[Nine Judges, Two Effective Votes，预印本](https://arxiv.org/html/2605.29800v1)

所以，A/B 跨家族值得保留，但选择 B 时应依据“它能否补 A 的具体错误”，而不是只看供应商不同。

## 2. 多模型协作：增益、成本和补漏

| 方法                        | 实测结果                                                     | 成本和局限                                                   |
| --------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Self-consistency / 多数投票 | 2025 年等预算复核发现，在 5 种 debate、9 个 benchmark、4 个模型上，self-consistency 通常比开放式 debate 更稳；多种 debate 相对普通 CoT 仅约 15% 的设置显著更好。[Stop Overvaluing Multi-Agent Debate，预印本](https://arxiv.org/pdf/2502.08788) | (N) 个独立样本约为 (N) 倍生成成本；多数票会强化各模型共享的稳定错误。 |
| Debate                      | ICML 2024 的 3 agents × 2 rounds，在 biography 一致性上 66.0→73.8、MMLU 63.9→71.1。[Du et al., ICML 2024](https://proceedings.mlr.press/v235/du24e.html) | Biography 指标不会惩罚 gold 之外的额外幻觉；后续等预算研究未复现普遍优势。辩论还会传播错误并把原本正确答案翻错。 |
| 多样本细粒度互证            | N=10 的 self-endorsement 在 biography factual accuracy 上提高 7.8–14.5pp；N=2 已取得不少收益。[Self-Endorsement, Findings ACL 2024](https://aclanthology.org/2024.findings-acl.499/) | 完整方法需要把每个样本的每个事实与其余样本互比，成本随样本和事实数快速增长；共同幻觉仍会获高一致性。 |
| Chain-of-Verification       | MultiSpanQA 的 F1/P/R 从 .39/.40/.38 提高到 .48/.50/.46。[CoVe, Findings ACL 2024](https://aclanthology.org/2024.findings-acl.212) | Biography 的 FactScore 55.9→71.4，但平均事实数 16.6→12.3；Wikidata 正确项也从 .59 降至 .38。它可能靠删内容换精度，不是 recall-safe。 |
| 专门化证据 verifier         | FLAN-T5-11B 在 FEVER/FM2 上达到 93.8/82.0，超过 GPT-3.5 的 91.7/77.5；说明最好生成器不一定是最好验证器。[Guan et al., NAACL 2024](https://aclanthology.org/2024.naacl-long.62.pdf) | 错误证据会严重破坏验证：ChatGPT 的 FEVER 分数在随机证据下从 82.0 降到 61.5。证据选择比再加一层模型更重要。 |

### “补漏”有系统方法

最适合你们的是 omission-only gleaning：

1. 冻结首轮结果；
2. 第二遍只能返回 `new_candidates[]`，禁止删除或改写已有项；
3. 每个新增项必须附 `source_id + exact_span`；
4. 并集、去重后，再逐新增项核验。

临床实体抽取实验中，一次 gleaning 把 recall 提高 2.3–7.5pp，约增加一次抽取调用；最差配置 precision 下降 6.2pp，因此必须把新增项留在候选层。[HPO Extraction，2024 预印本](https://arxiv.org/html/2412.15256v1)

更接近完整性审计的 VeriFact 先程序化找未覆盖原文区间，再用三个家族模型判断遗漏。单 judge 与人工的平均 κ 仅约 .33，但并集对“不完整”和“缺失事实”的 recall 分别达到 .89 和 .85——再次说明 union 适合候选召回，不适合直接修改真值。[VeriFact，2025 预印本](https://arxiv.org/html/2505.09701v2)

实践侧，Microsoft GraphRAG 也把 gleaning 做成 `max_gleanings`，配置示例通常只做一轮；官方没有隔离增益实验。[GraphRAG 配置](https://microsoft.github.io/graphrag/config/yaml/)

## 3. 审计员为什么误改，怎样降低

建议把“一条错误修正建议”拆成两个事件：

# [ P(\text{错误建议})

P(\text{误报})
+
P(\text{真有错误且修复失败})
]

这两类不能混着统计：

- **诊断误报**：原事实其实有充分证据；
- **错误定位**：确有问题，但 judge 指错字段或条件；
- **修复失败**：诊断正确，替换文本仍不受证据支持；
- **无必要重写**：新旧都成立，只是表达不同；
- **有效修复**：原项被证据反驳，补丁被证据蕴含。

学术界较有效的处理不是“让模型更谨慎”一句提示，而是结构约束：

- **诊断与修复分离**：第一模型只能判定和引用反证，第二阶段才生成补丁。自纠综述发现，纯提示式 intrinsic self-correction 缺乏稳定收益；可靠的外部反馈明显更有效。[TACL 2024 综述](https://aclanthology.org/2024.tacl-1.78/)
- **允许 abstain**：强制二选一会制造假阳性；使用 `SUPPORTED / CONTRADICTED / INSUFFICIENT`，只有 `CONTRADICTED` 才能进入修复阶段。[Trust or Escalate, ICLR 2025](https://openreview.net/forum?id=UHPnqSTBPO)
- **双重证据义务**：必须同时证明“原项不成立”和“补丁成立”。只有后者不够，因为一个更具体、听起来合理的文本仍可能是误改。
- **隐藏原模型及其解释**：factored CoVe 会让各验证问题独立回答；2026 MARCH 的 checker 只看问题和检索文档，不看 solver 原答案，以减少确认偏差。[CoVe](https://aclanthology.org/2024.findings-acl.212)、[MARCH, 2026](https://arxiv.org/pdf/2603.24579)
- **把原文证据放在提示末尾重申**：ACL 2025 的 BoolQ 自纠中，GPT-4o 正确→错误翻转率由 11.3% 降至 6.0%，净准确率损失由 4.9pp 降到 0.5pp。不过其他提示配置并非都改善，应该视为便宜的 A/B 变量，不是保证。[Zhang et al., ACL 2025](https://aclanthology.org/2025.acl-long.1314/)

补丁应当被视为一条全新的待核验事实，不能继承诊断阶段的置信度。

## 4. 哪种置信度真的有效

原始口头置信度不适合作为人审路由主信号。

- 八任务实验中，原始 verbal confidence 用于错误检测时，GPT-4 平均 AUROC 仅 62.7%，GPT-3.5 为 55.1%，后者接近随机。[Can LLMs Express Their Uncertainty?, ICLR 2024](https://openreview.net/forum?id=gjeQKFxFpZ)
- claim-level 实验中，直接询问 `P(True)` 的 ROC-AUC 多在 .53–.64；使用 token 概率构造的 CCP 约 .61–.74。经过 isotonic calibration 后，概率误差通常优于线性或分位数校准。[LM-Polygraph, TACL 2025](https://aclanthology.org/2025.tacl-1.11/)
- Trust or Escalate 中，GPT-4 在 AlpacaEval 的 verbal confidence 为 ECE .215、AUROC .550；用多次模拟标注者信号后改善到 .095/.723。目标人类一致率 80% 时，级联达到 80.2% 一致、77.6% coverage、相对 API 成本 .215。[Jung et al., ICLR 2025](https://arxiv.org/html/2407.18370v1)
  但该保证是“与多数人类偏好一致”，不是事实真值；还依赖校准集与部署数据近似同分布。

对你们，建议分别校准两个概率：

- `p_diagnosis`：人工是否同意原项确实有错误；
- `p_patch`：在诊断成立的条件下，人工是否接受这个具体补丁。

置信模型可使用 A/B 独立判断、换序稳定性、证据跨度、错误类型、来源阶段、补丁改动长度、token 概率和模型自报置信度；后两项只作为特征。按书/章节分组切分校准集，模型、提示或文本类型变化后重校准。

路由方式：

- `p_diagnosis` 高、`p_patch` 高：人审队列展示诊断＋补丁；
- `p_diagnosis` 高、`p_patch` 低：只展示反证，让人自行改；
- 中置信或高严重度：第二 verifier 或人工；
- 两者都低：抑制建议，仅留日志和抽样审计。

评估应以 risk–coverage/AURC、固定人审预算下的真错误召回、队列 precision、Brier/ECE 为主，而不是只看 AUROC。

## 5. 三个可以立即试的改进

| 实验                                 | 改法                                                         | 文献锚点                                                     | 保守预期                                                     |
| ------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **A. 诊断—修复解耦**                 | 审计员只输出三分类、错误类型和最小反证 span；隐藏 A/B 身份及解释。仅确定矛盾项进入独立修复器，补丁再核验。提示末尾重放原子事实与原文。 | [ACL 2025 自纠误翻](https://aclanthology.org/2025.acl-long.1314/)、[CoVe](https://aclanthology.org/2024.findings-acl.212)、[MARCH](https://arxiv.org/pdf/2603.24579) | 建议把试验目标定为误建议率相对下降 20%–40%，即约从 33% 降到 20%–26%。这是产品假设，不是可直接迁移的论文保证。新增成本主要发生在被 flag 的项目。 |
| **B. 一轮 coverage-guided gleaning** | 冻结首轮；按未覆盖原文语义单元补漏；只能新增，每项强制 exact span/source ID；并集后逐新增项核验。 | [HPO gleaning](https://arxiv.org/html/2412.15256v1)、[VeriFact](https://arxiv.org/html/2505.09701v2)、[GraphRAG](https://microsoft.github.io/graphrag/config/yaml/) | 原始候选 recall 可期待 +2–8pp；试验成功门槛可设为最终 recall +2–5pp、验证后 precision 损失不超过 1pp。成本约增加一次抽取调用，而非整条管线翻倍。 |
| **C. 人审标签校准＋选择性路由**      | 用历史人工裁决训练 `p_diagnosis` 和 `p_patch`；按文档分组留出，采用 isotonic calibration；按风险、严重度和审核时长排序。保留少量随机样本监测漂移。 | [LM-Polygraph](https://aclanthology.org/2025.tacl-1.11/)、[Trust or Escalate](https://openreview.net/forum?id=UHPnqSTBPO) | 论文结果不能直接外推事实抽取。合理的首轮验收目标是人审量下降 25%–40%，同时保留至少 90% 的人工确认真错误；进入队列的建议 precision 从当前约 67% 提高到至少 80%。 |

统一 scorecard 至少同时报告：

- 审计 flag precision/recall；
- 正确项→错误项 flip rate；
- 修正建议人工接受率；
- 新增候选 precision 与 recall@固定最终 precision；
- 重要原文事实 coverage；
- 每发现一个真错误的调用成本和人审分钟数。

只看“审计后 factuality”会奖励删事实和少说话：CoVe 已出现事实数量下降，MARCH 也观察到严格 factuality 奖励诱发 “less said, less leaked”。因此 coverage 必须与 precision 并列。[CoVe](https://aclanthology.org/2024.findings-acl.212)、[Beyond Precision, 2026 预印本](https://arxiv.org/html/2604.03141v1)

来源：ChatGPT