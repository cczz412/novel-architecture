# 结论

**现阶段不应把固定 few-shot examples 设为生产 Prompt 的常驻组成。** 保留 `EX0` 作为默认合同；把 examples 做成可开关、可检索、可回退的实验变量。

最值得验证的两个候选是：

- **1 组安全的 contrastive minimal pair**：两句话只改一个决定性算子，两个成员都只展示正确语义，不展示裸错误 JSON。
- **按错误边界检索的 0～2 个短例**：严格过滤、相似度不足时回退 `EX0`。

`EX-FIXED` 适合做低方差基线和调试工具，但不是当前最有依据的生产方案。原因不是 few-shot 无效，而是 demonstrations 同时充当了规则提示、输出模板和浅层统计信号；收益、顺序偏差、复制倾向都高度依赖模型、checkpoint、任务和示例集合。

直接相关的三个证据尤其关键：

- C-ICL 在 NER/RE 上发现“正确例＋明确标错并纠正的 hard negative”通常胜过 positive-only，但负例过多会先升后降，复杂 nested NER 还会因上下文变长而退化。[C-ICL](https://aclanthology.org/2024.findings-emnlp.590/)
- 中文 Qwen-1.5-7B 的 RA-IT 显示：训练时加入检索上下文可小幅提升，但论文主结果反而采用**无 examples 推理**，因为推理时 examples 经常因 schema/domain 不匹配而伤害性能。[RA-IT](https://aclanthology.org/2025.coling-main.196/)
- GPT-3 2.7B 的 4-shot 生成实验中，50.2% 的预测重复某个 demo 答案，而正确情况下应重复的比例仅 24.7%；0→1-shot 也可能因复制唯一示例而降分。[Zhao et al.](https://proceedings.mlr.press/v139/zhao21c.html)

因此，Qwen3-4B 上筛出的好方案只能视为假设；Ling Tiny、Doubao Mini、Doubao Lite 都必须独立复验。

------

## A. 相关度最高的 15 项研究

| 研究                                                         | 直接证据                                                     | 对本项目的边界                                               |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 1. [Calibrate Before Use](https://proceedings.mlr.press/v139/zhao21c.html) | 顺序、示例集合和格式可令准确率从 54% 到 93%；存在 majority、recency、common-token bias；生成答案会过度复用 demo。 | 强力支持顺序、空答案率和措辞复制审计；其分类校准方法不能直接照搬到开放抽取。 |
| 2. [Fantastically Ordered Prompts](https://aclanthology.org/2022.acl-long.556/) | 相同示例不同排列可从接近随机到接近 SOTA；一个模型的好排列不能迁移到另一个模型。 | Qwen 的最佳顺序不能外推给 Ling 或 Doubao。                   |
| 3. [Rethinking the Role of Demonstrations](https://aclanthology.org/2022.emnlp-main.759/) | 在分类/多选中，随机替换标签有时仅轻微伤害；示例常主要提供标签空间、输入分布和格式。 | DEV 提升可能只是 task recognition 或格式学习，不代表学会“计划≠已发生”。 |
| 4. [What ICL “Learns” In-Context](https://aclanthology.org/2023.findings-acl.527/) | 区分 task recognition 与 task learning；真正现场学习新映射随模型规模和示例数增强。 | 4B 模型的两例收益更可能是提醒已有能力，而非学会新规则。      |
| 5. [LLMs Can Be Lazy Learners](https://aclanthology.org/2023.findings-acl.284/) | 分类和 extraction 中，模型利用词、符号、位置、文风等伪相关 shortcut；大模型也不能免疫。 | 必须做反模板、位置和 fact-count 干预。                       |
| 6. [C-ICL](https://aclanthology.org/2024.findings-emnlp.590/) | NER/RE 中 positive＋明确标错及纠正的 negative 总体胜 positive-only；负例过多、复杂错误和长上下文会变差。 | 最直接支持 `EX-CONTRASTIVE`，也直接反对堆叠负例。最小模型为 CodeLlama-7B，不能外推 4B。 |
| 7. [Comparable Demonstrations Are Important](https://arxiv.org/abs/2312.07476) | 用最小编辑翻转标签的 comparable examples 在情感/NLI、尤其 OOD 中常有帮助，但部分条件下降。 | 支持 minimal pair 是候选，不证明固定 pair 可常驻小说抽取。   |
| 8. [LLM Is Not a Good Few-shot Information Extractor](https://aclanthology.org/2023.findings-emnlp.710/) | 九数据集、四种 IE 任务中，LLM 通常较微调小模型成本高、延迟高；增加 demos 时，NER/事件检测会持平或退化。 | 直接反驳“更多 examples 必然更好”。                           |
| 9. [What Makes Good In-Context Examples](https://aclanthology.org/2022.deelio-1.10/) | 多项 NLU/NLG 任务中，语义检索通常优于随机；任务相关 retriever 更好。 | 支持 retrieval 作为候选，但不是小说 IE，也未解决近重复泄漏。 |
| 10. [Learning To Retrieve Prompts](https://aclanthology.org/2022.naacl-main.191/) | 结构化语义生成中，GPT-Neo-2.7B 的 random/BM25/EPR 差距很大；例如 BREAK 为 1.7/26.0/31.9。 | 强证据表明小模型高度依赖示例选择；同时论文也观察到 prompt-pattern copying。 |
| 11. [GPT-RE](https://aclanthology.org/2023.emnlp-main.214/)  | 任务感知关系检索优于通用句子相似度；5 个高质量例可胜 30 个通用近邻，NULL 召回仍困难。 | 应检索“状态/关系结构相似”，不只是文本相似；质量比数量重要。  |
| 12. [Dr.ICL](https://arxiv.org/abs/2305.14128)               | 检索 demos 对 instruction-tuned Flan-PaLM 仍有价值，说明微调后 examples 不一定无用；但 NQ 检索中存在大量语义等价问题。 | 回答“微调后仍可能有效”，同时给出近重复泄漏警告；模型为 540B，不能量化本项目收益。 |
| 13. [RA-IT for Open NER](https://aclanthology.org/2025.coling-main.196/) | 中文 Qwen-1.5-7B 训练时检索增强：5K 平均 F1 46.44→47.04，10K 为 46.87→47.51；推理 examples 却经常因 schema 不匹配伤害性能。 | 训练时 examples 与推理常驻 examples 必须分开实验。           |
| 14. [Where to Show Demos](https://aclanthology.org/2025.emnlp-main.1503/) | 十个开源模型上，demo 块位置本身会改变结果；放 user message 末尾可翻转超过 30% 的 QA 预测，小模型更敏感。 | 若试 examples，应放规则后、正文前；不要放正文后充当 checklist。 |
| 15. [Evaluating Local Decision Boundaries via Contrast Sets](https://aclanthology.org/2020.findings-emnlp.117/) | 只作小而有意义的输入修改，模型在 contrast sets 上最多跌约 25%。 | 应另建绝不进入训练、Prompt 或 retrieval 的 hidden minimal-pair 考卷。 |

补充成熟对比工作：

- [LLM-R](https://aclanthology.org/2024.eacl-long.105/) 的 retrieval 平均优于 random，但 SQuAD 会因同 passage、低多样性检索而劣于 random，NQ 结果受到 train/test paraphrase overlap 影响。
- [MDR](https://aclanthology.org/2024.naacl-long.235/) 明确发现不同推理模型偏好不同 demos；同一个 retriever 换模型可能退化。
- [How Many Demonstrations](https://aclanthology.org/2023.findings-emnlp.745/) 中，一个真正有帮助的 demo 可胜多个互相干扰的 demos，说明数量曲线并不单调。

------

## B–C. 支持证据与反证的综合判断

| 问题                       | 支持 examples 的证据                                     | 反证或风险                                                  | 本项目判断                                     |
| -------------------------- | -------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------- |
| Few-shot 是否改善 IE       | C-ICL、GPT-RE、EPR 都观察到明显收益。                    | Ma et al. 发现 NER/ED 随 demos 增加可持平或退化。           | 值得实验，不足以常驻。                         |
| 正反例是否优于正例         | C-ICL 总体支持 positive＋corrected negative。            | 负例过多、错误复杂或 prompt 过长会下降。                    | 每次最多先试一组 pair；禁止 negative-only。    |
| Minimal pair 是否更好      | 可隔离单个语义算子，Comparable Demos 在部分 OOD 中有效。 | 固定 pair 可能成为最强 surface shortcut；部分 ID 条件下降。 | 是最佳候选之一，但必须换人名、语序和顺序复验。 |
| Retrieval 是否更稳         | KATE、EPR、GPT-RE、Dr.ICL 通常胜 random。                | 同 passage、近重复、schema mismatch、低多样性均会反转收益。 | 先硬过滤，再检索；允许返回 0 个例子。          |
| 微调后 examples 是否仍有用 | Dr.ICL 表明 instruction-tuned 模型仍可能获益。           | RA-IT 表明训练检索增强有效，但推理 examples 经常伤害。      | 必须在实际 post-SFT checkpoint 上重新测试。    |
| 负例是否必然压 recall      | 没有找到生成式事实抽取上的直接定律。                     | Recency/label-frequency bias 使“空答案/拒抽偏置”风险可信。  | 当成预注册风险，不写成已证实事实。             |
| 1/2/4/8 是否单调           | C-ICL 的两个选定任务在 1～5-shot 上上升。                | Zhao、Ma、Chen 均给出不单调或增加示例变差的案例。           | 逐模型测成本曲线；不设先验赢家。               |

### 不同例子形式的优先级

| 形式                            | 优点                                       | 风险                                                 | 建议                                                      |
| ------------------------------- | ------------------------------------------ | ---------------------------------------------------- | --------------------------------------------------------- |
| Positive-only                   | 安全展示目标语义和格式。                   | 诱导固定事实数、措辞和结构；不明确决策边界。         | 可作 `EX-FIXED` 基线。                                    |
| 空答案／只读区例                | 能抑制过抽。                               | 若总在末尾或比例过高，可能抬高 false-empty。         | 必须与词汇、长度相近的非空例平衡。                        |
| 裸错误答案                      | 展示常见错误。                             | 模型可能直接模仿错误字段或关系。                     | **不使用。**                                              |
| 错误＋明确纠正                  | 边界信息强，C-ICL 有直接支持。             | 同一上下文同时出现错误和正确结构，增加冲突与 token。 | 只作为二级实验；格式必须是“错误→明确禁止→正确→一句规则”。 |
| 两个均为正确输出的 minimal pair | 不把非法输出放入上下文，又能显示局部边界。 | 仍可能锚定表面算子。                                 | **优先作为 `EX-CONTRASTIVE`。**                           |

建议把用户示例改成更安全的形式：

```text
以下只说明语义边界，不是当前正文证据。

例 A：“赵青说明天去城里。”
应抽：赵青计划去城里；不得记为已经到达。

例 B：“赵青昨天去了城里。”
应抽：赵青已经去过城里。
```

计划、否定、误信、梦境、推测本身不应被统一教成“空答案”。它们是否产生 `planned`、`believed`、`denied`、`imagined` 等事实，必须由 Canonical ontology 决定；hard negative 针对的是把它们错误投射为客观已发生事实。

------

## 训练时重复 examples 的判断

目前没有一篇成熟论文直接证明“中文小说 SFT 每条样本重复同两个例子”必然形成 shortcut；这里应明确承认证据空白。

工程机制取决于 loss mask：

- **Assistant-only loss**：system/user 中的 examples 通常被 `-100` mask，不会直接占答案 loss 的分母。但它们仍消耗上下文、显存和训练 token，可能挤掉正文、减少每批可容纳的独立样本，并让模型形成 demo dependency。
- **Full-sequence loss**：重复 boilerplate 会直接成为大量低信息 loss token，可能支配优化目标。相关对比可参见 [Instruction Tuning With Loss Over Instructions](https://proceedings.neurips.cc/paper_files/paper/2024/hash/7ffb43adf37b3eeaba559098bc084cc6-Abstract-Conference.html)。

若训练阶段要测试 examples，建议拆成三个训练臂：

- `T0`：全部无 demos。
- `T-FIX`：每条重复固定两例，用来直接测 shortcut 风险。
- `T-VAR`：例如 50% 无 demos、25% 一组 pair、25% 两个分层随机例；每 epoch 改选择、姓名和顺序。

百分比只是待冻结的工程起点，不是文献定律。[In-context Tuning](https://aclanthology.org/2022.acl-long.53/) 表明，训练时暴露于不同选择和顺序可显著降低顺序/选择方差；[PromptIntern](https://aclanthology.org/2024.findings-emnlp.602/) 则说明反复 prompt 信息可能被微调吸收，推理时未必还需携带。

随机 examples 不会让 gold target 本身不稳定，只要：

- 当前题正确答案不变；
- 所有示例通过同一 Rulebook 版本校验；
- 选择 seed、bank 版本和顺序可复现；
- 保留足够 `EX0` 训练行，避免模型只会“有例才做”。

------

# D. 最小实验矩阵

所有臂固定同一 Rulebook、正文窗口、输出 schema、evidence 模式、解码参数和当前题顺序，只改变 demonstration policy。

| 实验臂           | 精确定义                                                     | 必做反偏置控制                                              |
| ---------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| `EX0`            | 无 examples。                                                | 默认基线。                                                  |
| `EX-FIXED`       | 冻结的两个独立正确 minimal examples，每题相同。              | AB/BA 顺序；两例不能同句法、同事实数、同人物结构。          |
| `EX-RANDOM`      | 从冻结 bank 分层随机取两个；按 boundary、empty/non-empty、fact-count 平衡。 | 至少 4 个冻结 selection seeds；不能把多次 seed 当独立样本。 |
| `EX-RETRIEVED`   | 硬过滤后，按可观察错误边界＋语义相似度选最多两个；不足阈值可返回 0/1。 | 记录候选、分数、过滤原因；加 diversity constraint。         |
| `EX-CONTRASTIVE` | 一组 minimal pair，即两个近乎相同文本，只改一个算子，两个都展示正确语义。 | 正反顺序 AB/BA；换人名、语序、谓词各一版。                  |

`EX-RETRIEVED` 应区分：

- `ORACLE-TYPE`：用 gold 错误类型选例，只用于测上限。
- `PROD-ROUTER`：只能用正文可观察特征、Mini 首轮预测或独立 router；这是唯一可迁移生产的版本。

若使用 gold status 或 DEV 错误标签检索例子，结果属于泄漏，不是有效 retrieval。

### 示例数量 1/2/4/8

| 数量 | 主要价值                                      | 主要风险                                        | 实验定位                          |
| ---- | --------------------------------------------- | ----------------------------------------------- | --------------------------------- |
| 1    | 最低 token；可快速判断模型是否响应 examples。 | 无法形成对比，锚定和唯一标签复制最强。          | 高风险诊断臂，不是默认候选。      |
| 2    | 可组成一组 pair，或覆盖两个独立边界。         | 仍可能暗示固定事实数。                          | **主矩阵起点。**                  |
| 4    | 增加表面和边界多样性。                        | 干扰、顺序组合、上下文成本明显增加。            | 仅对 k=2 胜出策略继续测。         |
| 8    | 可检验更多样性是否稀释单例偏差。              | shortcut、lost-in-context、延迟和污染风险最大。 | 压力测试；若 k=4 无增益，不继续。 |

不要在云端跑完整的 `5 strategies × 4 counts`。建议流程是：

1. Qwen 上全部策略统一按两个逻辑例子比较；
2. 只对胜出的一到两个策略做 `0/1/2/4/8`；
3. Ling、Doubao 只复验筛出的结论。

`DEV24` 可用于筛方向和发现机制，但 24 个窗口不足以承担生产晋级。多跑八个 prompt seeds 仍然只有 24 个独立 query；统计时必须按窗口或书聚类。

------

# E. Token 控制

不要给 `EX0` 塞随机 filler。无关上下文本身可能伤害结果，也会把“无例子”变成另一个污染条件。

建议同时报告两套比较：

### 真实成本比较

- `EX0` 保持真正最短；
- 各 examples 臂使用实际 token 数；
- 报告 `ΔF1 / 每增加 1K input tokens`、prefill latency、总 latency 和实际调用成本。

### Token-matched 辅助比较

增加一个非主臂：

- `EX-RULE-MATCHED`：用等 token 的抽象 Rulebook 边界说明替代 examples。

这样可以区分“例子有用”与“只是多给了规则／更多 token”。

示例臂之间应：

- 用目标模型各自 tokenizer 计数，控制在同一 token envelope，例如目标值 ±5%；
- 超预算时删整例，不能截半个例子；
- 不允许通过缩短 Rulebook 或小说正文给 examples 腾空间；
- 按最坏示例臂预先确定窗口上限，保证所有臂看到完全相同正文；
- 固定例子可能命中 prefix cache，而 retrieved 例子不能；生产延迟应分别报告 cold/warm cache。

数量曲线 `1/2/4/8` 不应硬做 token 等长：把八个例子压成极短文本会同时改变信息密度。它应作为真实成本—收益曲线单独报告。

------

# F. 防止答案泄漏

检索前执行硬过滤，过滤后才计算相似度：

1. Example bank 只能来自合成材料或训练权利明确材料；A v2.7 未取得训练权利前不得进入 bank 或训练。
2. 检索语料仅使用 TRAIN bank；当前 query、DEV、test 不进入索引。
3. 小说数据最低按 `book_id` 隔离；严格泛化考卷再按 `author_id` 隔离。[BOOKSUM](https://aclanthology.org/2022.findings-emnlp.488/) 也采用同书整体分 split 的思路。
4. 合成数据按 `template_family + generator_seed + scenario_family` 隔离，避免同一模板换名字造成伪泛化。
5. 排除相同人物名、稀有短语、实体 tuple、规范化 gold fact、evidence 字符串。
6. 同时做 exact hash、字符 n-gram/MinHash 和 embedding near-duplicate 检查。NER/RE 中的 train/test overlap 会显著夸大泛化结果。[数据泄漏研究](https://aclanthology.org/2021.eacl-main.113/)
7. 禁止从当前书的后续章节、梗概、人物设定中检索，避免未来信息泄漏。
8. 语义近邻需加 diversity：相同 surface template 或高度近似 pair 最多取一个。
9. 在 DEV 解锁前冻结 bank manifest、索引、retriever、阈值、renderer、seed 和文件 hash。
10. DEV 错题不能回填当前 bank；只能形成下一版本，并配套新 holdout。
11. 每题保存 retrieval candidate IDs、分数、淘汰原因和最终示例 ID，保证可审计。

P2 的特殊教材可以作为一个专项考卷，但不能成为唯一的生产近似评价集。

------

# G. 预注册指标

以 semantic fact-set F1 为主指标，其他均为安全门槛，不应被平均 F1 掩盖。

| 指标组   | 预注册内容                                                   |
| -------- | ------------------------------------------------------------ |
| 语义事实 | micro P/R/F1；按窗口 macro-F1；按错误类型分层 P/R/F1。       |
| 事实数量 | `pred_count-gold_count` 有符号偏差、MAE；固定 query 下，预测事实数对 demo 平均事实数的回归系数。 |
| 空答案   | gold 非空题的 false-empty rate；gold 空题的 false-nonempty rate；非空题 recall。 |
| Status   | macro-F1；actual/planned/believed/speculated/denied/imagined 等完整 confusion matrix。 |
| Speaker  | 在已匹配事实上的 speaker accuracy；unknown-speaker rate；转述层级错误率。 |
| 过抽     | unsupported facts / predicted facts；只读区泄漏率；未来信息泄漏率；把计划/误信实际化的比例。 |
| Evidence | evidence ID exact accuracy、evidence 覆盖率、证据是否来自允许区。输出表示必须在各臂固定。 |
| 示例复制 | 输出中出现“只存在于 demo、不存在于当前正文”的专名比例；最长公共子串、4-gram overlap、示例谓词/纠错句复用率。 |
| 输出行为 | 输出 token/字符数、事实条数、schema valid rate、截断率。     |
| 稳定性   | AB/BA 差异、selection-seed 均值/标准差/range、worst-order F1、同题 fact-set consistency。 |
| 成本     | input/output tokens；prefill/total latency p50/p95；真实调用成本。 |

统计建议：

- 主结果使用确定性解码；若 API 仍有非确定性，冻结请求参数并重复记录。
- 使用同一批 query 的 paired comparison。
- 95% CI 按窗口／书做 paired clustered bootstrap，不能按 632 个 facts 假装独立。
- 预先指定一个 primary contrast；其余 arm 为探索性，避免看到 DEV 后挑赢家。
- 报告平均值与 worst-order/worst-seed，不能只报最佳排列。

------

# H. 判断学会规则还是复制模板

建立独立的 `CONTRAST_EVAL_HIDDEN`；它不得进入训练、Prompt、retrieval、错误分析回填。

| 干预                                             | 如果学会规则，应观察到                                   |
| ------------------------------------------------ | -------------------------------------------------------- |
| 更换 demo 的全部人名、地点、动词和语序           | 当前 query 的事实、status、speaker 不变。                |
| pair 顺序 AB↔BA                                  | 结果基本稳定。                                           |
| demo 事实数改成 0/1/3，query 不变                | query 预测事实数不随 demo 移动。                         |
| demo 输出改成短/长两种等价表达                   | query 输出长度和事实数基本不变。                         |
| query 与 demo 无词面重合，但规则相同             | 增益仍然存在。                                           |
| query 与 demo 高词面重合，但关系方向/status 不同 | 模型跟随 query 语义，不跟随表面模板。                    |
| 只改变 query 中“已/将、看见/猜测、承认/否认”     | 输出按 gold 方向正确变化。                               |
| 实体姓名互换                                     | 主体、客体和 speaker 随正文正确互换。                    |
| post-SFT 模型移除 demos                          | 不应出现能力崩溃；否则是 demo dependency。               |
| 离线故意破坏 demo 映射                           | 若预测跟随错误映射，说明主要在复制；该测试不得进入生产。 |

核心判据不是单题 F1，而是：

- 对 demo 的非语义变化具有 **invariance**；
- 对当前正文的语义算子变化具有正确 **sensitivity**；
- hidden contrast 的两个成员必须都答对，才能记为 pairwise contrast correct。

若普通 DEV 提升而 hidden contrast、无词面重合或 anti-shortcut 集合不提升，应判为“学模板”，不得迁移生产。

------

# I. 是否应成为生产 Prompt 固定组成

当前答案是：**不应。**

较合理的使用层级是：

- 训练前期：用 examples 做错误诊断、Rulebook 可理解性检查和小模型筛选。
- 训练阶段：可试受控随机 context augmentation，但保留大量 EX0，并验证推理可删除。
- 生产推理：默认 EX0；只在可观察的歧义 router 触发时加入一组相关 pair，且有零例回退。
- Lite 升级：可在复杂案例上测试动态 examples，但必须与 Lite 自身 EX0 独立比较。

### Prompt 位置与优先级

建议逻辑结构：

```text
SYSTEM
[权威 Rulebook、状态定义、证据权限、输出合同]
[冲突声明：Rulebook 高于示例；示例仅说明语义，不是证据]
[固定示例块——若该实验臂需要]

USER
[动态检索示例块——若该实验臂需要]
[当前可写区／只读区元数据]
[当前小说窗口：唯一事实与 evidence 来源]
[输出要求或纯规则 checklist]
```

固定例子测试 `end-of-system` 与 `start-of-user` 两个位置；动态例子通常只能放正文前。不要在正文后放 examples：既有 recency 风险，也容易把 demo 当成当前证据。正文后如果需要 checklist，应只重复抽象规则，不放人物化案例。

“Rulebook 优先”只是规范，不保证模型真的服从。因此：

- 每个 example 必须由同版本 Rulebook 的自动 linter 和人工复核共同通过；
- 任何示例—规则冲突都视为构建失败，不能依赖一句“规则优先”让模型现场消歧。

### 建议冻结的停用条件

以下是工程门槛建议，不是论文给出的普适阈值：

- 任一顺序或主要 seed 的 semantic F1 比 EX0 低超过 2pp：不常驻。
- 平均 F1 增益不足 1pp，或 paired 95% CI 不能排除无收益：不常驻。
- 非空题 recall 下降超过 0.5pp，或 false-empty、过抽、只读泄漏增加超过 1pp：停用。
- AB/BA 的 F1、recall 或空答案率差异超过 2pp：该 pair 不常驻。
- 普通 DEV 有增益但 hidden contrast 增益≤0：判为 shortcut。
- 示例专名或仅示例短语出现在超过 1% 的 query 输出中：停用该 bank/renderer。
- 预测事实数随 demo 事实数显著移动，或平均移动超过 0.25 条：停用。
- 增加的 token/latency 超预算，且增益不足以覆盖成本：仅保留为调试工具。

------

# J. 小型 example bank 设计合同

建议 v1 建成 **24～32 组 minimal pairs**，每种边界至少两个完全不同的 surface families；单次 Prompt 最多使用一组 pair 或两个独立 cards。

### 单个 pair 约束

- 每个 source 成员 15～50 个汉字，1～2 句。
- 每个成员只有一个目标语义边界；通常为 0 或 1 个 eligible fact。
- 最多两个命名实体，不依赖外部世界知识。
- 两成员尽量只改一个算子，`changed_span` 建议不超过 8 个汉字。
- 用各目标模型 tokenizer 计算；完整渲染后每个成员建议≤80 tokens，每组 pair≤180 tokens。
- 默认 renderer 只展示正确语义，不展示非法完整 JSON。
- `plausible_wrong` 存在 bank 元数据中；只有专门的 error-correction 实验臂才允许渲染，并必须紧接纠正。
- 当前语义实验统一使用轻量 semantic-card renderer，避免把字段顺序和输出格式一起变成实验变量。

### 必须覆盖的边界

| 边界                     | minimal change 示例方向                    |
| ------------------------ | ------------------------------------------ |
| 已发生 vs 未来计划       | “昨天去了” / “明天准备去”                  |
| 完成 vs 未遂             | “推开门” / “想推却没推开”                  |
| 现实 vs 梦境/幻觉        | narrator-confirmed / “梦见、仿佛看见”      |
| 事实 vs 条件/假设        | “已经发生” / “如果发生”                    |
| 肯定 vs 否定/否认        | “承认做过” / “否认做过”                    |
| 确知 vs 推测             | “亲眼看见” / “猜测也许”                    |
| 世界事实 vs 角色误信     | narrator-confirmed / “他误以为”            |
| 直接陈述 vs 转述/传闻    | narrator / “听甲说”，保留 speaker/source   |
| 可写区 vs 只读区         | 相同事实只改变 provenance/region           |
| 同词不同关系             | 主客体、施受者、所有者或关系方向互换       |
| 行动 vs 愿望/能力/许可   | “做了” / “想做、能做、获准做”              |
| 当前状态 vs 已失效旧状态 | 只改变时间锚点                             |
| 空答案 vs 一条事实       | 只改变现实性或可写区开关                   |
| Fact-count 控制          | 独立的 0/1/2/4 facts cards，防固定输出数量 |

### Bank 元数据

```text
example_id, pair_id, bank_version, rulebook_version,
boundary_type, source_text, eligible_region,
correct_semantics, plausible_wrong, one_line_rule,
changed_span, gold_fact_count, gold_status, speaker_case,
surface_family, template_family, source_group,
book_id, author_id, generator_seed,
rights_status, provenance_hash,
token_counts_by_model, renderer_version, reviewer
```

### 版本与隔离

- Major：ontology、status 或 Rulebook 语义变化。
- Minor：增加新 pair 或 surface family。
- Patch：不改变 gold 的文字修正。
- 任何 gold 语义变化都创建新 `example_id`，不能覆盖旧项。
- 冻结 manifest SHA-256、bank、renderer、retrieval index、embedding model、阈值和 seed。
- Prompt bank 与 `CONTRAST_EVAL_HIDDEN` 必须是两个不重叠集合。
- 有明确作者来源的材料按书、作者隔离；合成材料按生成模板和 seed 隔离。
- A v2.7 未获训练权利前不得进入 bank、retriever 训练或 SFT。

------

# K. 三层复验建议

| 层级             | 应运行什么                                                   | 可以得出什么                                              | 绝不能迁移什么                                               |
| ---------------- | ------------------------------------------------------------ | --------------------------------------------------------- | ------------------------------------------------------------ |
| Dense Qwen3-4B   | 完整五臂；两个顺序；4～8 个 bank seeds；hidden contrast；胜出臂再跑 1/2/4/8；必要时比较两个 placement。 | 哪些假设值得花云成本复验；哪些 shortcut 测试有效。        | 不能推断 Doubao 会同方向，也不能把最佳顺序、例子或 shot 数视为通则。 |
| Sparse Ling Tiny | 只复验 2～3 个 Qwen 筛选结论：EX0 vs 最佳 k=2、AB/BA 稳定性、无词面重合/anti-shortcut；若 placement 是关键结论，再测两个位置。 | 结论是否能在另一种本地代理架构上复现。                    | Dense→sparse 不保证 ICL 行为一致；token 预算、retriever 阈值和例子排名必须重算。 |
| Doubao Mini/Lite | 在真实 post-SFT checkpoint 上测 EX0、最佳候选、EX-CONTRASTIVE；使用冻结、权利明确、生产近似考卷；记录真实 token、cache、latency、成本。Lite 只在复杂升级集上另测。 | 是否可进入生产 feature flag；Mini/Lite 各自的无伤害边界。 | 不能沿用 Qwen/Ling 的最佳顺序、固定例子、retriever 或 shot 数；Mini 结果也不能自动外推 Lite。 |

云成本控制上：

- Qwen 承担多臂探索；
- Ling 只复验机制；
- Mini 运行 2～3 个冻结候选；
- Lite 仅运行升级难例上的 EX0 与最佳动态策略；
- 每次 model/checkpoint、Rulebook、chat template 或 renderer 变化，都视为新 Prompt 系统，需要重新做最小回归。

最终建议仍是：**examples 暂时用于研究、训练增强和定向升级，不进入生产基础 Prompt 常驻。** 如果后续 target-model 证据支持，优先晋级“短 contrastive pair／按需检索＋零例回退”，而不是固定两例覆盖所有小说窗口。

来源：ChatGPT