# Deep Research 3-3｜章节与块位置 metadata 会提高事实抽取吗？

## 结论

截至 2026 年 8 月，没有直接研究证明：

> 在中文小说事实抽取前加入 `chapter_index=23`、`chunk=6/10` 或 `chapter_middle`，会稳定改善事实、说话人、状态变化或指代抽取。

现有研究支持的强弱顺序更接近：

1. **与正文单位精确对应的责任区／只读区标记**：最有希望，也最接近“精确指针”类实证。
2. **真实的层级边界、句子／段落在 section 内的位置**：在长文 QA、证据选择、科学文献摘要中有收益，但多为专门训练的结构 embedding 或 token，不是直接写一句 `6/10`。
3. **章节相对位置**：可检验，但没有小说 IE 直接证据。
4. **`chapter_middle`、`chapter_end` 等语义标签**：锚定风险更高。
5. **绝对章节号**：目前更适合作为审计 provenance，不应默认让模型看到。

所以推荐：

- 保留并强化真实的 responsibility/read-only 区域指针。
- 在 Qwen 上测试 `chunk_index/count` 和机械派生的中性位置桶。
- 暂不把 `chapter_index` 或 `section_role=chapter_end` 固定进生产合同。
- 任何收益必须显著超过等位置、等 token 的无意义标签控制。
- Qwen、Ling Tiny、Doubao Mini/Lite 分别复验，不能按 dense、MoE、参数规模外推。

------

## A、B：研究证据与适用边界

| 研究                                                         | 直接发现                                                     | 能支持什么                                               | 不能支持什么                                               |
| ------------------------------------------------------------ | ------------------------------------------------------------ | -------------------------------------------------------- | ---------------------------------------------------------- |
| [Document Structure in Long Document Transformers](https://aclanthology.org/2024.eacl-long.64/) | LED、LongT5 在 QASPER、Evidence Inference 上有时受益于 node type、depth、结构 token/embedding。一个 LED 证据选择条件中，单纯 separator 已把 F1 从 61.55 提到 66.81，丰富结构最高 67.07 | 结构边界可能有用；separator 控制不可缺少；模型反应不同   | 不能证明小说中的 `6/10` 有语义收益                         |
| [HiStruct+](https://aclanthology.org/2022.findings-acl.102/) | 把 section index、section 内句子位置和标题编码进抽取式摘要模型；消融显示层级位置是主要贡献者 | 层级位置可成为有效的训练信号                             | 它不是 decoder prompt，也不是小说事实抽取                  |
| [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) | 同一证据放在长上下文的不同物理位置，模型表现显著变化，常呈首尾高、中部低 | 必须按证据物理位置和章节位置分桶                         | 写一个 `middle` 标签不等于修复位置偏差                     |
| [Can We Instruct LLMs to Compensate for Position Bias?](https://aclanthology.org/2024.findings-emnlp.732/) | `beginning/midsection/tail` 等相对词不能稳定引导模型；精确文档 ID 在部分条件下有帮助；错误 ID 会降低表现 | 责任区 ID 比模糊位置词更有希望；错误 metadata 会主动误导 | 不能把相对位置词当成已验证方案                             |
| [Structural Scaffolds](https://aclanthology.org/N19-1361/)   | 用预测规范化 section title／discourse role 作为辅助目标，改善科学论文引文意图分类 | discourse role 可在结构高度规范的文档中帮助训练          | 不等于把原始标题或 `chapter_end` 写进 prompt 就会改善      |
| [MC-indexing](https://aclanthology.org/2024.findings-emnlp.150/) 与 [PDFTriage](https://aclanthology.org/2024.emnlp-industry.13/) | 内容感知 chunk、层级文档树、section/page/table 节点改善检索或文档问答流程 | RAG 应保留真实文档结构；结构化索引有工程价值             | 收益混合了切块、检索和工具流程，不能归因给 ordinal token   |
| [LAMBERT](https://arxiv.org/abs/2002.08087)                  | OCR bounding box 等布局坐标改善视觉文档 IE                   | 真实布局对表单、扫描件 IE 有价值                         | “第 38 页”这个绝对数字本身未被证明有用；纯文本小说不应照搬 |
| [MeCo](https://arxiv.org/abs/2501.01956)                     | 训练时 prepend metadata 可加速预训练并用于 steering；一直带 metadata 训练的模型在无 metadata 评测时会退化；伪造 metadata 也能改变行为 | metadata 会被学成控制条件；训练—推理分布必须一致         | 研究对象是英文预训练，不是小说 SFT                         |
| [Chiang & Lee 2024](https://aclanthology.org/2024.blackboxnlp-1.24/) | 保持内容不变、交换网页时间和来源 metadata，会改变多个模型的答案 | metadata 不是无害注释；必须做交换审计                    | 不能给出小说位置 metadata 的净收益                         |
| [Sclar et al., ICLR 2024](https://arxiv.org/abs/2310.11324)  | 语义等价的 prompt 格式变化可造成很大性能差异，格式排名跨模型不稳定 | JSON/XML/NL 的选择必须冻结并逐模型复验                   | 不存在可直接宣称的通用最佳格式                             |

证据分级如下：

- **已有较强实证**：层级边界、section 内句子位置、精确 unit ID、视觉布局、结构化切块。
- **近邻但领域依赖明显**：section title、discourse role、文档 outline。
- **目前主要靠直觉**：绝对章节号、字面 `6/10`、`0.60`、`chapter_middle` 对小说事实抽取的帮助。
- **尚无直接证据**：`chapter_end` 一定诱发总结或预测；dense/MoE、小/大模型存在统一 metadata 规律。

## `6/10` 到底有没有语义？

它不是纯粹无意义，但语义非常有限：

- 它只说明这是确定切分流程中的第六块，共十块。
- 它不能直接告诉模型“她”指谁，也不提供缺失的状态事实。
- 只有切分器固定、块顺序真实、完整章节已经冻结时，`6/10` 才可复现。
- 若块长不同或存在重叠，`6/10` 不等于正文字符位置的 60%。

更准确的相对位置应从责任区中心计算：

[
r=\frac{\text{责任区起始字符偏移}+\text{责任区结束字符偏移}}
{2\times\text{完整章节字符数}}
]

字符规范化和切分器版本必须冻结。模型输入中不建议同时出现 `6/10`、`0.60` 和 `middle`：三者高度共线、浪费 token，也让归因失效。

工程上可保留：

- 模型可见：`chunk_index`、`chunk_count`；
- 实验 M3 可见：`first_third / middle_third / last_third`；
- 日志可见：精确 `r`；
- 审计日志可见：`chapter_index`。

`chapter_index=23` 跨小说并不具有统一语义，还可能成为作品、篇幅或情节阶段的捷径。若 M1 获胜，应追加 `M1-chunk-only` 与 `M1-chapter-only`，否则不知道是谁带来的收益。

## 章节结尾风险

没有论文直接证明 `chapter_end` 会让模型补写转折、总结整章或预测未来。但 metadata 和位置指令能 steering 模型，错误位置又会误导，因此这是合理且必须预注册的失败假设。

M3 应使用中性标签：

```text
relative_position_bucket = last_third
```

不要使用：

```text
section_role = chapter_climax
section_role = resolution
section_role = chapter_end
```

所有实验臂共用一条规则：

> 位置字段只描述当前窗口在冻结章节中的机械位置，不授权总结整章、补写转折或预测未见内容。窗口边界不等于章节边界；只能输出责任区内有逐字证据的事实。

------

## C：最小实验

这里有一个重要的因果设计修正：

**responsibility/read-only zone 定义了哪些事实允许输出，它是任务合同，不是普通可选 metadata。**

如果 M0/M1 完全没有责任区，而 M2 才加入，`M2-M1` 同时改变了抽取目标，不能解释为“结构 metadata 收益”。

建议把“无 metadata”定义为“无章节位置 metadata”，所有臂保留相同的正文局部区域标记：

| 臂      | 输入                                                         |
| ------- | ------------------------------------------------------------ |
| M0      | 当前局部窗口合同；正文内有相同的 responsibility/read-only 边界；无章节位置 header |
| M1      | M0 + 真实 `chapter_index`、`chunk_index`、`chunk_count`      |
| M2      | M1 + header 中明确列出真实 responsibility/read-only ID 范围；正文边界与 M0 完全相同 |
| M3      | M2 + 机械派生的 `relative_position_bucket`                   |
| C-Nonce | 与 M3 相同 wrapper、字段数、位置和 token 预算，但位置字段换成无意义标签 |

若一定要运行“正文完全无区域指示 → 加区域指示”的原始阶梯，应把它命名为**合同完整度实验**，不要用它判断位置 metadata 的因果收益。

### D：结构标记控制臂

示例：

```text
<context_metadata>
meta_a = K7
meta_b = Q2
meta_c = V9
meta_d = J4-J8
</context_metadata>
```

控制要求：

- 固定随机种子并写入实验 manifest；
- nonce 与作品、章节、位置、人物、gold 完全独立；
- 使用小型平衡词表，避免每个样本一个唯一 ID，后者可能成为记忆键；
- wrapper、标点、字段数、header 位置保持一致；
- 按各模型 tokenizer 匹配 token 长度分布；
- 最好使用三套 nonce 映射；
- 真实 responsibility/read-only 边界不得随机化。

结果解释：

- `真实 > M0`，但 `真实 ≈ nonce`：只证明 header／separator 有帮助。
- `真实 > nonce > M0`：结构和 metadata 语义可能都有贡献。
- `nonce > 真实`：真实位置字段很可能产生锚定。
- `真实 > nonce` 且换错位置后性能下降：说明模型确实使用了位置，但仍要检查它是否使用正确。

另做一个仅评测的反事实审计：保持正文不动，在同一 `chunk_count` 分层内交换 `chunk_index` 或首尾位置桶，记录事实 flip、无证据新增、speaker/status 改写。伪 metadata 只用于这个负面对照，不能混入主要训练材料。

------

## E、F：预注册指标与受益样本

### 主指标

- semantic fact micro Precision、Recall、F1；
- 章节级 macro F1；
- 同一事实的一对一匹配，语义等价由盲审处理；
- paired difference：`真实-M0`；
- metadata 语义贡献：`真实-C-Nonce`。

### 次指标与风险指标

- speaker accuracy／macro-F1；
- 状态标签 macro-F1、状态变化子集 F1；
- 跨块指代／代词样本 semantic F1；
- evidence ID F1、逐字证据 span accuracy；
- 过抽率：无支持预测数 ÷ 全部预测数；
- 只读区泄漏率；
- 未见未来事实／结尾补写率；
- schema 合法率、重复事实率；
- 输入 token、被 header 挤掉的正文 token、截断数、延迟和费用。

### 必须分桶

- `first_third / middle_third / last_third`；
- 真实证据在 prompt 中的物理首／中／尾；
- 章首第一块、章尾最后一块；
- 跨块指代；
- 状态延续与状态改变；
- 多人物对话、说话人省略；
- 前后都有只读上下文；
- 简单显式单人物事实，作为低预期收益对照。

最可能受益的是“窗口边界与章节边界容易混淆”的样本；最可能受害的是章尾、强叙事节奏和多义位置标签样本。

统计单位应按作品／章节聚类，不能把同章多个 chunk 当成完全独立。训练、DEV、测试必须按作品或至少按章节隔离；使用章节级 paired bootstrap 95% CI。

TRAIN24/DEV24 适合淘汰明显失败臂，但 24 个窗口不足以把小幅收益锁进生产。晋级还需要独立冻结、权利清楚的考卷。P2 可作特殊教材诊断，但不能代表普通小说；A v2.7 在训练权利明确前不得进入训练。

真实元数据必须来自冻结的章节 manifest 和确定性切分器。合成章节可以使用其生成时真实存在的章节结构，不能在实验后随手编一个章节号。

------

## G：什么结果足以写入生产合同

以下数值是建议的项目准入线，不是论文定律；应在查看结果前登记。若已有业务最小实用差异，用业务阈值替换。

- 在两个独立冻结测试集上，semantic F1 相对 M0 至少提高 **1.5 个绝对点**；
- 章节级 paired bootstrap 95% CI 下界大于 0；
- 相对 C-Nonce 至少提高 **1.0 点**，且 CI 下界大于 0；
- 过抽、只读泄漏、未来补写任一项不得恶化超过 **0.5 个百分点**；
- speaker、状态、指代及任一位置桶不得出现超过 **1.0 点**的实质退化；
- 三个 Qwen 训练种子方向一致；
- 不得造成正文截断；
- 在 Ling Tiny 和 Doubao Mini 上分别得到直接同向复验。

判定细则：

- 若 M2 胜、M3 不胜：固定区域合同，不加入位置桶。
- 若 M1 胜：拆开 chapter-only 与 chunk-only；没有独立收益的字段删除。
- 若真实≈nonce：只保留分隔结构，不保留章节语义字段。
- 若 M3 提高召回但同时提高章尾过抽或未来补写：拒绝 M3。
- Lite 只在复杂升级样本上验收，不能继承 Mini 的结论。

## H：训练加入 metadata 后，推理是否必须存在？

保守答案是：**必须。**

如果 SFT 样本 100% 带 metadata，模型可能把它学成输入条件或捷径。推理时删除属于分布变化。[MeCo](https://arxiv.org/abs/2501.01956) 已在预训练场景观察到无 metadata 退化，但它的 cooldown 比例不能照搬到你们的 SFT。

若生产无法永远提供 metadata：

- 训练中加入明确的 metadata-absent 路径或 metadata dropout；
- 单独验收 `full / absent / invalid-reject`；
- 缺失时回退到经过测试的 M0 合同或 M0 checkpoint；
- 不得临时填 `0`、`unknown chapter` 或猜一个 `middle`。

错误字段应 hard-fail；不可靠时宁可不提供。`null` 或 `unknown` 也只有在训练中见过并通过独立验收后才能使用。

------

## I：三层复验路线

### 1. Dense Qwen3-4B 代理

完整运行：

```text
M0 / M1 / M2 / M3 / C-Nonce
```

- 同一基础 checkpoint、样本顺序、训练步数、解码参数；
- 三个训练随机种子；
- 先用普通 JSON/key-value token，不改 tokenizer；
- 加入真实 metadata 删除／交换的推理审计；
- Qwen 结果只负责筛选，不能成为生产证据。

### 2. Sparse Ling 3.0 Tiny

只复验：

```text
L0 = M0
L* = Qwen 胜出方案
LP = 等 token nonce
```

建议 2～3 个训练种子。若能读取 router 数据，可记录真实、nonce、错误 metadata 是否改变专家路由，但路由变化只能作为解释性结果，不能替代事实 F1。

一个 Qwen 和一个 Ling 的差异只能描述这两个 checkpoint，不能命名为 dense/MoE 架构规律。

### 3. Doubao-Seed-2.0 Mini / Lite

成本压缩顺序：

1. 在未见冻结考卷上做 Mini 的 `M0 / M* / nonce` 推理筛查；
2. 只有 Qwen、Ling 都出现 `真实 > nonce` 的同向结果，才开云端训练；
3. 从同一 Mini 基础 checkpoint 分别训练 `D0` 与 `D*`；
4. 在 `D*` 上测真实、删除、nonce、首尾交换；
5. 若结果接近准入线，或 nonce 也明显改善，再增加 placebo 训练臂；
6. Lite 只在复杂升级集上单独做相同的推理 A/B。

Mini 没有直接过门槛前，不应把 Qwen/Ling 胜出的字段写入生产 Input Contract。

------

## J：最小、稳定、无内容泄漏 schema

建议采用“正文前一次 JSON header + 正文局部区域标签”。动态 metadata 不放 system；system 只放稳定抽取规则。

离线处理已经完成并冻结的章节：

```text
<context_metadata>
{
  "contract_version": "icc-v1",
  "scope": "chapter_local_window",
  "chunk": {
    "index": 6,
    "count": 10
  },
  "zones": {
    "responsibility": {"from": "T04", "to": "T11"},
    "read_only": [
      {"from": "T01", "to": "T03"},
      {"from": "T12", "to": "T14"}
    ]
  }
}
</context_metadata>

<source_text>
<read_only ids="T01-T03">...</read_only>
<responsibility ids="T04-T11">...</responsibility>
<read_only ids="T12-T14">...</read_only>
</source_text>
```

字段政策：

- `chapter_index`：先留在审计 manifest；M1 实验时加入，只有 chapter-only 消融证明独立收益才进入模型输入。
- `relative_position_bucket`：只有 M3 过门槛才加入。
- 精确 `relative_position=0.60`：保留在分析日志，不与 bucket 同时喂模型。
- section title、outline、摘要、未来事件、全书总章数：不进入最小 schema。
- metadata 只控制输入解释，不得写回事实库或成为事实证据。
- `contract_version`、章节文本 hash、切分器版本、字符偏移和推导公式写入实验 manifest。

若是边写边抽取的流式场景，完整章节长度尚不可知，`chunk_count`、相对位置和 section role 都构成未来结构泄漏。此时改为：

```json
{
  "contract_version": "icc-stream-v1",
  "scope": "chapter_local_window",
  "chunk_index_so_far": 6,
  "zones": {
    "responsibility": {"from": "T04", "to": "T11"},
    "read_only": [{"from": "T01", "to": "T03"}]
  }
}
```

一句话决策：**先证明“真实位置语义”胜过“相同分隔结构”，再谈把 metadata 固定进生产；当前最该押注的是精确责任区指针，不是绝对章节号或 `chapter_end`。**

来源：ChatGPT