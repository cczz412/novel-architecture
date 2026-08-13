# 独立验真器评测与数据回流预注册 R01

日期：2026-08-11  
适用对象：小说事实抽取的“候选生成＋独立补漏＋逐条证据验真＋程序合并”  
状态：研究与实验设计建议；不授权新增模型调用、训练、生产或数据回流

## 一句话结论

✅ **证明验真器有效，不能看“它有多自信”，也不能只看“它和人工有多一致”。唯一够硬的证明是：在小说来源隔离的未见确认集上，把机械失败一并计入后，整条管线的最终 Precision、Recall、F1 变好，误杀、漏放、拒答和每章最差表现都没有越过预注册红线。**

同模型自检不算独立；同家族换尺寸只算弱独立；不同厂商／不同家族是更好的默认候选，但仍要实测共错；专用判别式小模型最容易做概率校准，适合当便宜第一道门；人工盲审仍是判断“两个模型一起错”的最终锚点。

当前四块和 1,132 条匿名队列可以完成 DEV 盲审、错误分型和验真器初筛，**不能单独证明产品改善**。反复查看同一开发卷并按成绩改模型、Prompt 或阈值，会让这张卷逐渐失去终验资格；这是典型的自适应复用问题。[Dwork 等关于 holdout 复用的研究](https://arxiv.org/abs/1506.02629)明确说明，反复依据同一留出集结果修改方案会过拟合留出集。

---

## 1. 公开证据真正支持什么

### 1.1 “验证器单体更准”不等于“接入后更好”

最直接的反例来自 SCORE。对 LLaMA-2-13B 的 GSM8K 实验，GPT-3.5 验证器的 F1 为 59.7，高于自训练验证器的 47.3，但接入纠错后，最终准确率反而从 42.7 降到 31.5，下降 11.2 个百分点；GPT-4 验证器 F1 达 89.2 时，最终准确率才提高到 46.3。[SCORE 全文](https://arxiv.org/abs/2404.17140)

这条证据虽然来自推理题而非小说抽取，却直接证明了本项目最关心的机制：**验证器的错误会通过“错误放行、错误拦截、错误触发修正”传到最终系统，judge F1 高一点也可能让系统更差。**

### 1.2 同模型与同家族更容易共享错误

2025 年的跨模型验证研究比较了 37 个模型、9 类任务，以及自检、同家族验证、跨家族验证。总体上跨家族收益最大，同家族次之，自检最弱；模型的解题分布越相似，验证器越容易把错误答案判为正确。[When Does Verification Pay Off? 全文](https://arxiv.org/abs/2512.02304)

这项研究主要是数学、逻辑、知识和结构化题，不能直接替小说抽取定量背书；它能支持的是实验方向：**厂商或家族不同只是降低共错的先验，不是独立性的证明。最终仍要在本地候选上测 `P(验证器放行 | 提议模型已错)`。**

LLM-as-a-judge 研究还发现了自偏好、家族偏好、熟悉度偏好、位置偏差和对无关 Prompt 改写敏感等问题：[Play Favorites](https://arxiv.org/abs/2508.06709)、[Large Language Models are Inconsistent and Biased Evaluators](https://arxiv.org/abs/2405.01724)、[Large Language Models are not Fair Evaluators](https://aclanthology.org/2024.acl-long.511/)。所以隐藏模型身份是必要条件，但隐藏身份本身还不够。

### 1.3 专用小模型值得测，但不能照搬论文成绩

MiniCheck 把文档与候选主张当成判别任务。其 770M Flan-T5 版本在由 10 个数据集组成的 LLM-AGGREFACT 上达到接近 GPT-4 的整体表现，论文估算成本低约 400 倍；作者还用人工标注的真实模型输出做测试，而不只在教师模型生成数据上自测。[MiniCheck 全文](https://aclanthology.org/2024.emnlp-main.499/)

这说明“判别式小模型做窄验真”有可靠先例，但它主要做 supported / unsupported 二分类。中文小说里的说话人、时间、否定、计划／已发生、目标区边界和“真实但不该抽”都超出了原论文任务，因此必须重新做域内校准和未见小说确认。

### 1.4 三态事实核查仍不够，灰区必须显式保留

FEVER 把主张分成 `SUPPORTED / REFUTED / NOT ENOUGH INFO`，并要求支持／反驳标签同时给证据。[FEVER 全文](https://aclanthology.org/N18-1074/)

VeriScore 的 320 条人工核查中，55% 被支持、2.8% 被反驳，42.2% 因主张过泛、部分成分没有直接证据或关系无法确认而处于 inconclusive；50 条三人重复标注的 Fleiss κ 为 0.7316。[VeriScore 全文](https://arxiv.org/abs/2406.19276)

所以本项目不能把“找不到反证”当成 `SUPPORTED`，也不能把所有不确定都塞进一个 `NOT_STATED`。不过要把两个概念分开：

- `AMBIGUOUS`：正文或责任边界本身允许多个合理读法，是**语义真值标签**；
- `ABSTAIN/DEFER`：验证器没有把握，是**系统动作**。

两者不是一回事。

### 1.5 Groundedness 只管精度，不管漏抽

FActScore 把长输出拆成原子事实，计算被可靠来源支持的比例，主要衡量 factual precision；它不直接回答漏掉多少必抽事实。[FActScore 全文](https://aclanthology.org/2023.emnlp-main.741/)

微软当前的 RAG 评测说明也把 Groundedness 视为精度侧指标，把 Response Completeness 视为召回侧指标，明确分开报告。[Microsoft RAG evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators)

因此，只报告验真后“留下的事实更可信”不够；必须同时报告它杀掉了多少必抽事实，以及补漏器是否把召回补回来。

---

## 2. 验真标签必须是“两条轴＋一个动作层”

最容易犯的错是把 `SUPPORTED` 直接等同于“应该进入最终事实表”。小说里存在大量“正文确实说了，但按产品合同仍不该抽”的句子，例如气氛、重复信息、背景区事实、无后续价值细节或目标责任区外事件。

推荐 Schema：

| 层 | 字段 | 枚举／内容 | 用途 |
|---|---|---|---|
| 证据真值 | `evidence_verdict` | `SUPPORTED / CONTRADICTED / NOT_STATED / AMBIGUOUS` | 判断给定证据是否托住候选主张 |
| 抽取职责 | `extraction_duty` | `REQUIRED / OPTIONAL_NEUTRAL / FORBIDDEN` | 判断即便是真的，是否应进入最终表 |
| 系统动作 | `decision` | `AUTO_PASS / AUTO_REJECT / DEFER` | 由校准阈值和两条语义轴共同决定 |
| 机械状态 | `mechanical_status` | `OK / HTTP_FAIL / HTTP_OK_NO_FINAL_BODY / INVALID_JSON / SCHEMA_FAIL / INVALID_EVIDENCE / TIMEOUT` | 机械失败不能伪装成语义标签 |
| 证据 | `evidence_ids`、`evidence_spans`、`scope` | 逐字片段、位置、目标区／只读背景区 | 程序回验来源与边界 |
| 分数 | `raw_scores`、`calibrated_scores` | 四类分数或至少 `P(SUPPORTED)` | 阈值与校准审计 |
| 审计 | `error_type`、`rubric_version`、`run_id` | 固定错误码与版本 | 分层监控和回流 |

四个证据标签的操作定义：

- `SUPPORTED`：主张每个必要组成部分都被允许证据直接支持，没有冲突；只读背景可以帮助解指代，但不能替目标责任区提供新增事实证据。
- `CONTRADICTED`：允许证据直接否定主张中的至少一个必要组成部分，如人物、动作、状态、时间、数量、否定或情态相反。
- `NOT_STATED`：证据既不支持也不直接否定；只出现相似词、常识上可能、因果上可猜或只支持一半，都归这里。
- `AMBIGUOUS`：证据文本、说话人、指代、时间或范围本身无法唯一确定，且两个以上读法都成立。验证器自己“没想明白”不能借用这个标签，应返回 `DEFER`。

推荐采用**分层判定**，而不是强迫一个模型一次做好四分类：

1. 主门只判 `SUPPORTED` 对 `NON_SUPPORTED`，用来决定能否自动放行；
2. 对非支持项再分 `CONTRADICTED / NOT_STATED / AMBIGUOUS`，服务于自动拒绝、人工路由和错误分析；
3. 另判 `REQUIRED / OPTIONAL_NEUTRAL / FORBIDDEN`。证据支持但职责禁止的候选仍不得放行。

---

## 3. 最小数据切分：不需要立刻造大 Gold，但三套身份不能混

| 集合 | 起步规模建议 | 可以做什么 | 绝对不能做什么 |
|---|---|---|---|
| DEV | 现有四块＋1,132 条匿名候选 | 完成人工盲审、错误分型；选候选模型、Prompt、Schema、合并规则；比较多种验真器 | 宣称生产改善；把置信区间当未见泛化证据 |
| CAL | 约 12 个新责任块，来自至少 4 本未见小说；来源与 DEV 隔离 | 只拟合概率校准、双阈值、拒答区和风险上限；最好只接收 DEV 冻结后的一个方案 | 再改 Prompt、模型或标签定义；若改了，该集降级为 DEV |
| CONFIRM | 再约 12 个新责任块，来自另外至少 4 本未见小说；与 DEV/CAL 小说级隔离 | 冻结后一次性比较基线与新管线；做最终置信区间和逐章检查 | 看完结果再改阈值并继续称它为未见确认 |

上表的 12＋12 是**低成本启动数，不是统计学保证**。真正需要多少候选，由预注册的误放上限决定。若随机抽检 `n` 个自动放行项恰好零错误，95% 单侧上界近似为 `3/n`：

- 约 60 个零错误，只能说明误放率大致低于 5%；
- 约 150 个零错误，才接近低于 2%；
- 约 300 个零错误，才接近低于 1%。

这些近似还假设样本独立。小说内候选高度相关，所以样本必须跨小说／章节抽，最终用小说或章节成组的区间；不能把同一章里几十条事实当几十次独立试验。

自然流里 `CONTRADICTED` 和 `AMBIGUOUS` 可能太少。可以另建一个**挑战切片**，从真实失败中为稀有标签各补到至少能看混淆矩阵的数量；但挑战切片只能报告分层能力，不能冒充线上自然分布总成绩。所有派生记录跟随原小说的 split，不能拆到不同集合。

---

## 4. 最小盲审与交叉验证流程

1. **先分小说，再产输出。** 冻结小说／章节／责任块清单、正文 SHA、Gold 版本、DEV/CAL/CONFIRM 身份。
2. **冻结三臂。** A＝当前最佳单模型；B＝主抽取＋验真；C＝主抽取＋补漏＋验真＋程序合并。Prompt、模型版本、思考档、输出预算、阈值、重试和 fallback 全部入清单。
3. **先记机械账。** HTTP、stop reason、是否有最终结构化正文、JSON、Schema、evidence、去重和合并各自判定。语义评分不得只在成功行上算。
4. **形成统一候选池。** 对 A/B/C 的最终候选做确定性去重，隐藏模型名、厂商、臂、置信度、验证器理由和候选顺序；保留原始文字，不让另一个模型改写候选含义。
5. **双人独立标。** 人工只看候选、允许证据和抽取合同，分别标 `evidence_verdict`、`extraction_duty`、逐字证据和错误类型；分歧交第三人裁决。身份揭盲前锁定标签。
6. **交叉矩阵回放。** 同一批已有人类标签的候选，分别交给自检、同家族、跨家族、判别式小模型；每个验证器都看完全相同的 claim＋证据，不看提议者身份与原推理。
7. **CAL 只做校准。** 选定一个配置后，拟合概率映射和 PASS／REJECT 双阈值；阈值冻结。
8. **CONFIRM 一次确认。** 揭盲并重算单体验真指标、端到端指标、逐章最差、机械完成率、成本和延迟。

⚠️ 当前 `BLIND_SEMANTIC_QUEUE` 可以做 DEV 匿名语义裁决，但其中的 `candidate_gold_facts` 绝不能传给验真模型。验真模型只能看冻结正文、合法证据区和候选主张。

---

## 5. 五类验真方式怎么选

| 方式 | 优点 | 主要风险 | 在本项目中的位置 |
|---|---|---|---|
| 同模型自检 | 最便宜、接入简单；可发现 JSON、漏字段等显眼问题 | 共享知识盲区、表达习惯和推理路径；自偏好 | 只作辅助信号或机械修复，不能叫“独立验真” |
| 同家族不同模型 | 能力和成本可分层；比完全自检多一点差异 | 共享预训练、后训练和家族偏好；尺寸变大不等于共错消失 | 只有 CAL/CONFIRM 的同家族误放不劣于跨家族时才可自动放行 |
| 不同厂商／家族 LLM | 默认最有希望降低错误相关性；长文本理解较强 | 仍可能共享网络语料、偏好数据和评测套路；成本与版本漂移 | 推荐作为首个强验真候选和灰区升级，但必须盲输入＋人工抽检 |
| 判别式小模型 | 便宜、输出稳定、可拿 logits 做校准；不容易延续提议者生成风格 | 中文小说指代、状态和边界能力可能不足；训练教师也会带偏 | 推荐做第一道窄门；先以跨家族强 API＋人工作为上限对照 |
| 人工抽检 | 能发现两个模型共同遗漏的规则和语义错误 | 贵、慢、也会不一致；风险抽样不能估总体发生率 | 随机抽样估残余误放＋高风险全审；双人盲标与第三人裁决 |

不同厂商是“更可能独立”，不是“已经独立”。真正的独立性指标是下面的共错结果。

---

## 6. 怎样直接测“两个模型一起错”

在同一批人类定标候选上，对每个 `提议模型 g × 验真器 v` 计算：

1. **条件误放率**

   `CFP(g,v) = 人工判为错误但被 v 放行的 g 候选 / 人工判为错误的 g 候选`

   这是最关键的共错指标。它直接回答：“提议模型已经错时，验真器还会不会点头？”

2. **双错率**

   `DoubleFault(g,v) = 提议错误且验真器放行的候选数 / g 的全部候选数`

3. **错误集合重合**

   对固定候选池，报告验证器之间错误集合的 Jaccard、pairwise double-fault 和错误类型重合。总体一致率会被大量简单样本冲高，不能代替错误重合。

4. **同家族超额风险**

   `ExcessSameFamily = CFP(同家族) - CFP(跨家族)`，按小说／章节做配对成组 bootstrap 区间；还要分别看人物、说话人、时间、否定、状态、证据越界、可选／禁止等切片。

硬条件：

- 自检永远不以“独立验真器”名义自动签绿票。
- 若同家族 `CFP` 相比跨家族的差值超过预注册容忍值，或某个错误家族明显集中共错，该切片必须换跨家族验真或转人工。
- “差异不显著”不等于“证明独立”；小样本没检出差异时仍保留随机人工抽检。
- 跨家族也要审计，因为公开研究只证明平均趋势，不证明你这组中文小说模型。

---

## 7. 验真器单体必须报告的指标

### 7.1 语义分类

- 四分类混淆矩阵；每类 Precision、Recall、F1；macro-F1。
- `SUPPORTED precision`：自动支持项中人工真正支持的比例，直接对应误放。
- `SUPPORTED recall`：人工支持项被保留的比例，直接对应误杀。
- `CONTRADICTED / NOT_STATED / AMBIGUOUS` 各自召回，不能只合成一个 unsupported。
- 抽取职责三分类混淆矩阵，另报 `FORBIDDEN pass rate`。
- 逐字证据合法率、证据覆盖完整率、只读背景越界率。

### 7.2 选择性预测与拒答

- `auto-pass coverage`、`auto-reject coverage`、`defer rate`。
- `pass risk = 错误自动放行 / 全部自动放行`。
- `reject risk = 本应保留却自动拒绝 / 全部自动拒绝`。
- risk–coverage 曲线：阈值收紧后错误是否稳定下降，还是模型只是随机少答。
- 灰区的标签构成和最终人工工作量。

### 7.3 校准

神经网络原始概率通常不等于真实正确概率；温度缩放等后处理必须在独立校准集上拟合。[Guo 等校准研究](https://arxiv.org/abs/1706.04599)

至少报告：

- Brier score、NLL；
- classwise ECE 与等频 reliability diagram；
- 预测 0.8～0.9 的 `SUPPORTED` 中，人工实际支持率是多少；
- 各小说／错误切片上的校准误差；
- 阈值变化时 coverage 与 pass risk。

推荐双阈值：高于 `τ_pass` 且职责允许才自动放行；低于 `τ_reject` 且有明确非支持证据才自动拒绝；中间全部 `DEFER`。阈值按允许误放率选，不按验证器 F1 最大点选。选择性分类研究的核心也是用覆盖率换可控风险，而不是强迫模型回答所有样本。[Selective Classification](https://papers.nips.cc/paper/7073-selective-classification-for-deep-neural-networks)

若以后 CAL 数据足够，可试 split conformal prediction，把多标签集合交给系统：只有集合恰为 `{SUPPORTED}` 才自动通过；包含多个标签就拒答。它的保证依赖校准集与线上数据可交换，分布漂移时不能照搬。[Conformal Prediction 教程](https://arxiv.org/abs/2107.07511)

---

## 8. 端到端指标与误差传导

设每章必抽集合为 `M`、可选集合为 `O`、最终去重输出为 `P`：

- `TP = |P ∩ M|`
- `OPTIONAL = |P ∩ O|`
- `FP = |P \ (M ∪ O)|`
- `FN = |M \ P|`

主分建议让可选事实真正中性：把命中 `O` 的预测从主 Precision 分子和分母都移除，不奖励也不惩罚；另报可选输出量。于是：

- `P_neutral = TP / (TP + FP)`
- `R_required = TP / (TP + FN)`
- `F1_neutral = harmonic(P_neutral, R_required)`

同时保留当前严格／宽松带作敏感性分析，但晋级必须预先冻结一个主口径。明确不该抽的事实和未匹配预测全部算 FP，并单报 `FORBIDDEN leakage`。

验真器的传导关系可以直接写成：

- `最终必抽召回 ≈ 候选阶段必抽召回 × 验真器对必抽的保留率 × 合并保留率`
- `最终误抽数 ≈ 候选错误数 × 验真器错误放行率 × 合并保留率`

因此，没有补漏器时，验真器理论上只能维持或降低召回；它是否值得接入，取决于 Precision 增益能否覆盖误杀。加入补漏器后，要重新测整条 C 臂，不能把补漏器召回和验真器精度从不同实验相乘冒充结果。

端到端必须报告：

- micro P/R/F1 与相对基线差值；
- 每章 TP/FP/FN、F1、最差章、10% 分位和塌陷章数量；
- 必抽误杀率、错误候选漏放率、可选输出量、明确不该抽泄漏率；
- 完整结构化结果率、HTTP 成功率、Schema 率、evidence 率、merge 失败率；
- 每章调用数、token、费用、端到端时延、人工升级比例。

### 机械失败的硬口径

`HTTP 200` 但思考耗尽预算、没有最终 JSON，必须记为 `HTTP_OK_NO_FINAL_BODY`：

- 不得标成“零事实”或 `NOT_STATED`；
- 不进入验真器语义混淆矩阵；
- 若没有 fallback，该章最终输出不完整，所有未交付的必抽事实在无条件端到端评分里计 FN；
- 若有 fallback，就把 fallback 的质量、成本和延迟一起计入该臂；
- 验真单条调用出现同类问题时，动作是 `DEFER/MECHANICAL_FAIL`，不得静默通过。

这样可以避免只在成功返回的调用上计算漂亮的“条件 F1”。

---

## 9. 统计检验怎么做

### 9.1 重采样单位

1,132 条候选来自少量共同小说块、重复模型输出和共享 Gold，互相不独立。主单位优先用**小说**；小说数太少时退到**章节／责任块**，但必须说明外推只到该层。不能逐候选 bootstrap。

### 9.2 主分析

- 对基线 A 与冻结管线 B/C 做 10,000 次 paired cluster bootstrap；每次成组重采样小说／章节，并同时带走该组两臂全部 TP/FP/FN、机械失败和成本，再重算 micro P/R/F1。
- 报 `ΔP、ΔR、ΔF1` 的 95% CI、`P(Δ>0)` 和 `P(Δ≥最小有用提升 δ)`。
- 用 paired approximate randomization 作为主要差值的补充检验：在同一小说／章节内交换两臂标签，再重算 micro-F1。F1 非正态，非参数重采样更合适；NLP 统计检验综述也把 paired bootstrap 和 randomization 列为这类指标的常用方法。[Dror 等全文](https://aclanthology.org/P18-1128/)
- 对固定候选上的二元放行差异，可用 McNemar；四分类用成组 bootstrap 的混淆矩阵差值。

### 9.3 多重选择

DEV 可以筛很多方案；CONFIRM 只保留一个预注册主比较，例如 `C 对 A`。若确认集仍同时检验多种验真器、阈值和管线，必须标为探索性，或对主假设做 Holm 等多重比较控制。不能挑出最好看的一个 p 值再补写假设。

---

## 10. 可复制的预注册模板

```yaml
experiment_id: VERIFIER_PIPELINE_Rxx
claim_scope: "只允许称 DEV 晋级 / CAL 通过 / 未见确认通过 三者之一"

data:
  dev_manifest_sha: ...
  cal_manifest_sha: ...
  confirm_manifest_sha: ...
  split_unit: novel
  leakage_rule: "同小说、作者、来源及其所有派生样本只能在一个 split"

arms:
  A_baseline: {generator, prompt_sha, model_version, decoding, max_output, fallback}
  B_verify: {A_plus, verifier, verifier_prompt_sha, thresholds, fallback}
  C_full: {generator, supplementer, verifier, merge_code_sha, thresholds, fallback}

labels:
  evidence: [SUPPORTED, CONTRADICTED, NOT_STATED, AMBIGUOUS]
  duty: [REQUIRED, OPTIONAL_NEUTRAL, FORBIDDEN]
  action: [AUTO_PASS, AUTO_REJECT, DEFER]
  rubric_version: ...

mechanical_policy:
  http_200_without_final_body: HTTP_OK_NO_FINAL_BODY
  invalid_or_truncated: fail_closed_or_named_fallback
  unconditional_scoring: true

calibration:
  method: temperature_scaling_or_isotonic
  tau_pass: ...
  tau_reject: ...
  max_pass_risk_upper_95: alpha_pass
  minimum_auto_coverage: c_min

primary_metrics:
  - delta_micro_precision_neutral
  - delta_required_recall
  - delta_micro_f1_neutral
  - mechanical_completion_delta
  - worst_chapter_delta

margins:
  minimum_useful_precision_gain: delta_p
  minimum_useful_recall_gain: delta_r
  minimum_useful_f1_gain: delta_f1
  maximum_chapter_drop: m_chapter
  maximum_mechanical_failure_rate: m_mech

correlated_error_gate:
  metric: CFP_same_family_minus_CFP_cross_family
  tolerance: m_cfp
  failure_action: "换家族或该切片转人工"

statistics:
  cluster_unit: novel_or_chapter
  bootstrap_runs: 10000
  confidence: 0.95
  randomization_runs: 20000
  primary_comparison: C_vs_A

decision:
  dev_promote: "仅有资格进入 CAL，不产生产品结论"
  retain_only: "点估计方向好但 CI 跨 0、稀有类不足或逐章不稳"
  confirm_pass: "阈值冻结；未见集 delta_P、delta_R、delta_F1 的 95% CI 下界均大于 0，并达到预注册最小有用提升；机械与最差章过门"
  reject: "误放上界超标、Recall 越界、机械失败变多、同家族共错超标或逐章塌陷"
```

### 三道晋级门

**DEV 晋级 CAL：** 只看是否值得继续。要求点估计方向合理、机械完成率不低于基线、没有明显逐章塌陷，且盲审和标签流程可执行。过门只能写“DEV 晋级”。

**CAL 冻结：** 只校准一个已选配置；PASS 风险的单侧 95% 上界低于预设 `alpha_pass`，自动覆盖率不低于 `c_min`；阈值、Prompt、模型和 merge 全冻结。若改任何一项，重新建 CAL 身份。

**CONFIRM 产品改善：** 按本项目已经给出的采用条件，要求 `ΔP、ΔR、ΔF1` 的 95% CI 下界都大于 0，并达到各自预注册的最小有用提升。机械完成率不得退、最差章不得越过 `m_chapter`，且同家族共错门通过。任何一项区间跨 0，都只能保留候选或写“证据不足”，不能称产品改善。

若未见题方向一致但 CI 跨 0，只能写“保留候选／证据不足”；若只在 DEV 或训练回放上变好，不得写“产品改善”。

---

## 11. 可审计的数据回流链

所有记录只追加版本，不覆盖旧答案：

| 层 | 必存内容 | 谁能定真值 |
|---|---|---|
| `source_snapshot` | 小说／章／责任区 ID、正文与边界 SHA、权利与来源、split | 数据治理规则 |
| `run_record_v0` | 完整请求、Prompt SHA、厂商／模型／版本／参数、HTTP、stop reason、token、时延、费用、原始响应字节 | 只记录，不改写 |
| `adapter_record_v1` | 从原始响应提取出的最终正文、JSON/Schema/evidence/截断结果、所有修复操作 | 确定性程序 |
| `candidate_record` | 原始候选、去重键、提议模型、证据 ID、候选进入哪一臂 | 只记录来源 |
| `verifier_record` | 原始判定、四类分数、职责判定、证据、机械状态、阈值动作、模型版本 | 不能单独升为 Gold |
| `human_annotation_v*` | 盲标人 ID、rubric 版本、两条语义轴、逐字证据、错误码、时间 | 独立标注人 |
| `adjudication_record` | 分歧、第三人裁决、最终修正、理由、父记录 ID | 人工终审 |
| `user_feedback` | 当时展示答案、投诉原文、上下文、证据、是否核实、隐私／授权状态 | 未核实前不是训练标签 |
| `training_example_manifest` | 所有父 ID、SFT/DPO 类型、chosen/rejected、split、权利、去重、质量级别 | 训练数据审核 |

### 哪些进 SFT，哪些进 DPO

| 失败 | SFT | DPO | 处理说明 |
|---|---|---|---|
| 没有可用 rejected，只知道标准正确答案 | ✅ | ❌ | 用规范完整答案教任务与格式 |
| JSON／Schema／字段顺序／证据 ID 形式错误 | ✅ | 通常不建议 | 这类容易让 DPO只学表面格式 |
| HTTP 200 但预算耗尽、没有最终正文 | 条件性 | ❌ | 先修预算、stop、adapter；只有在预算充足仍习惯性不交正文时，才把简洁正确答案做 SFT |
| 同一输入下，两份都完整合法，一份误抽／状态错／证据错，另一份经人工确认正确 | ✅ 可用 | ✅ | DPO 的 chosen/rejected 必须绑定同一输入与合同 |
| 同一输入下，一份漏必抽，另一份完整，且人工能稳定判优 | ✅ 可用 | ✅ | 控制长度偏差，不能让 chosen 永远更长 |
| 可选事实差异、人工意见分裂 | 暂停 | ❌ | 先修职责规则，不能强造偏好 |
| 模型与验真器一致、但无人审 | ❌ 作为 Gold | ❌ | 只能标 `SILVER_AGREEMENT`，抽检后再决定 |
| 用户投诉尚未核实 | ❌ | ❌ | 保留 incident，人工取证后才转教材 |

DPO 原论文使用相对质量偏好来训练模型；所以每一对必须保留完全相同的输入、精确的原始 rejected，以及经人工证据确认的 chosen。[DPO 论文](https://arxiv.org/abs/2305.18290)

### 防止教师与验真器共同犯错后被放大

- 模型＋模型一致只叫 silver，永远不自动升 Gold；强 API 也只是对照／教师，不是真值。
- 只有人工证据裁决或确定性机械检查能升 Gold；人工分歧保留，不强行二选一。
- 训练、DEV、CAL、CONFIRM 在小说来源层先分；同一记录的所有改写、候选、投诉和偏好对继承原 split。
- CAL/CONFIRM 永不回流当前训练；若决定回流，它们先退役并建立新的未见确认集。
- 把“提议者和验证器都同意、人工却判错”的案例单列 `DOUBLE_FAULT`。一部分进入下轮训练时，另一批同错误家族必须继续封存作未见挑战集。
- 报 silver/human 原创/用户核实三类数据比例，禁止训练集被单一教师批量淹没。
- 保存教师、验真器和学生的完整版本；任一模型升级都要重跑影子确认。

递归使用模型生成数据会损失长尾分布甚至出现模型退化，已有直接研究，但那篇 Nature 工作讨论的是多代递归训练，不是对本项目一次 SFT/DPO 的直接预测。这里应把它当作“保留真实人类／原始分布与数据血缘”的风险依据，而不是宣称一次回流必然崩坏。[Nature model collapse](https://www.nature.com/articles/s41586-024-07566-y)

---

## 12. 持续监控预注册

每个发布版本固定监控：

1. **未见小说确认卷**：至少保留一个永不训练的固定卷；另建按时间滚动的新鲜卷。没有未见复现，只能叫训练／DEV 改善。
2. **失败类型分层**：人物、说话人、指代、时间、否定、计划／推测／已发生、数字、跨句、目标区外、背景越界、必抽／可选／禁止、证据、重复／合并、机械失败。
3. **模型更新漂移**：厂商模型版本、Prompt、思考档、输出预算、温度、Schema、验证阈值、merge 代码任一变化，都生成新 `pipeline_version`，跑固定影子集和 CAL 校准检查。
4. **线上分布漂移**：输入长度、对话占比、指代密度、事实密度、候选数量、四类预测分布、置信度、拒答率、证据跨度、机械失败率、用户投诉类型。
5. **强 API 对照**：对随机样本保留一个冻结强 API 影子臂；它不是 Gold，只和同一人工确认结果比较，防止便宜管线悄悄退化。
6. **人工随机审计**：同时抽自动 PASS 和自动 REJECT。只抽 PASS 只能估 Precision，发现不了验真器误杀导致的 Recall 损失。

Google 的模型监控实践把服务输入／预测随时间变化单列为 drift；NIST AI RMF 也强调持续测量、记录和人类监督。它们支持的是持续监控框架，不替代本项目的语义 Gold。[Google Model Monitoring](https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/model-monitoring/overview)；[NIST GenAI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)

---

## 13. 适用条件与硬失败条件

### 适用

- 责任区和只读背景区已经冻结，证据能逐字回查；
- 候选能拆到一次可判断的核心主张；
- 人工能把证据真值与抽取职责分开标；
- 灰区可以拒答或转人工；
- 小说来源能做 DEV/CAL/CONFIRM 隔离；
- 管线保留完整原始响应和版本。

### 失败／不得采用

- 只报告 judge–human agreement、accuracy 或 macro-F1，不重算最终抽取 P/R/F1；
- 只在成功返回的调用上评分，忽略 HTTP 200 无最终正文、截断和 Schema 失败；
- 把 `SUPPORTED` 当“必然应该抽”，未测真实但禁止的过抽；
- 把 `AMBIGUOUS` 和模型 `DEFER` 混为一类；
- 同模型／同家族验证器看得到提议者身份、原推理、置信度或 Gold 候选；
- 阈值在当前四块或 CONFIRM 上反复调；
- 逐候选 bootstrap，把同章相关样本当独立；
- 验真后 Precision 上升，但 Recall、最差章或机械完成率塌陷；
- 模型与验真器一致就自动回流训练；
- 模型或线上分布更新后不重校准。

---

## 14. 本地证据锚点（4 条）

1. `.../all_api_scoring_r02/BLIND_SEMANTIC_QUEUE.jsonl`  
   SHA-256：`715ef7ec9b5111204b155dcdc854b5301d09cf85d3daa13fe42e821f28a7be37`  
   作用：1,132 条匿名候选；当前 1,132 条 `decision` 均未终审，身份只允许 DEV。

2. `.../all_api_scoring_r02/SCORING_RECEIPT.json`  
   SHA-256：`885d38ba669cd88c2f7de4bb4d0c314fc75042f24f2712c24e85865a7277a6dd`  
   作用：97 次调用、30 个条件；明确写明机器辅助暂分、待人工复核，未授权晋升。

3. `.../returns/03_extractor_independent_validator_pipeline.md`  
   SHA-256：`bbe90a927a00fb8fd6ef76c40d0c756e4b02c1dce872d1a98e85b995c930695e`  
   作用：已有通用“提名—证据—验证—门卫”调查；本报告补上共错、校准、端到端和回流。

4. `.../evidence/10_LING30_FLASH_R01_FAILURE_RESULT.json`  
   SHA-256：`ef90da8dca812e0f0e23794733e5b8653f171470335fe0ff46018e26c4b68b40`  
   作用：1 次 HTTP 成功、0 次 adapter 通过、无法进入四块内容评分；对应 `HTTP_OK_NO_FINAL_BODY` 机械失败面。

---

## 15. 主要资料与阅读范围

| 资料 | 阅读范围 | 对本项目的用途 | 不能直接外推 |
|---|---|---|---|
| [When Does Verification Pay Off?](https://arxiv.org/abs/2512.02304) | 全文 HTML | 自检／同家族／跨家族、相似解法与误放 | 任务以推理和知识题为主，不是中文小说抽取 |
| [Small Language Models Need Strong Verifiers](https://arxiv.org/abs/2404.17140) | 全文 HTML | 验真器单体 F1 与最终系统可能反向 | 纠错式推理管线，不是候选事实去重管线 |
| [MiniCheck](https://aclanthology.org/2024.emnlp-main.499/) | 全文 PDF | 判别式小验真器、人工测试、成本与阈值 | 二分类和英文文档，不含抽取职责轴 |
| [VeriScore](https://arxiv.org/abs/2406.19276) | 全文 HTML | inconclusive、人工一致性、复杂主张 | 开放网络检索，不是冻结小说正文 |
| [FEVER](https://aclanthology.org/N18-1074/) | 全文 PDF | 支持／反驳／证据不足与证据标注 | Wikipedia 事实核查，不含可选／禁止 |
| [FActScore](https://aclanthology.org/2023.emnlp-main.741/) | 论文页＋摘要，结合既有全文调查 | 原子事实与事实精度 | 不直接测遗漏和产品职责 |
| [Play Favorites](https://arxiv.org/abs/2508.06709) | 摘要＋方法概览 | 自偏好与家族偏好 | 自由回答打分，不是文档 entailment |
| [LLM Evaluators are Inconsistent and Biased](https://arxiv.org/abs/2405.01724) | 摘要＋HTML 要点 | 熟悉度、锚定和 Prompt 敏感 | 摘要评价任务，非本域 |
| [Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599) | 摘要＋论文方法要点 | 独立校准、温度缩放 | 不保证分布漂移下仍校准 |
| [Selective Classification](https://papers.nips.cc/paper/7073-selective-classification-for-deep-neural-networks) | 摘要＋方法结论 | risk–coverage 与拒答 | 图像分类实验，不给本域阈值 |
| [NLP Statistical Significance Guide](https://aclanthology.org/P18-1128/) | 全文 PDF | paired bootstrap、randomization、依赖样本 | 没有替本项目选 cluster 层级 |
| [Adaptive Holdout Reuse](https://arxiv.org/abs/1506.02629) | 摘要＋方法概览 | 当前四块降级 DEV 的理论依据 | 不要求本项目实现其隐私算法 |
| [DPO](https://arxiv.org/abs/2305.18290) | 摘要＋方法定义 | chosen/rejected 偏好数据边界 | 不证明任意模型裁判生成偏好都正确 |
| [AI models collapse on recursive generated data](https://www.nature.com/articles/s41586-024-07566-y) | 全文网页要点 | 防止无审计模型数据循环放大 | 多代递归训练，不是一次微调的直接预测 |

来源：Codex
