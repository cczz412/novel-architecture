# 重复证据文本下，Gold 与 Provenance 应该怎样定义

## 结论摘要

✅ **你们目前的处理方向是对的，而且比“默认取第一次出现”可靠得多。** 但长期合同还应再拆清一层：

> **完整 gold 不应只是一个 canonical span；完整 gold 应是“语义事实 + 可接受的证据集合 + canonical 代表位置 + 标注确定性”。**

换句话说，三个概念不能混在一起：

| 概念 | 回答的问题 | 推荐定义 |
|---|---|---|
| 事实 gold | 事实内容是什么 | 规范化后的事实或答案 |
| provenance gold | 哪些原文位置足以支持该事实 | 一个或多个合法 evidence set |
| canonical provenance | 当格式、渲染器或旧模型只能接收一个位置时，用哪一个 | 从已确认合法的位置中按固定规则选出的代表 |
| ambiguous candidates | 旧数据只知道可能是这些位置，但不知道哪个是真的 | 候选集合，不属于 gold alternatives |

🔥 **同一句 evidence 出现两次，并不自动意味着有两个合法 gold span。**

可能出现三种完全不同的情况：

1. 两个位置都能独立、充分地证明事实：这是**多个等价 gold provenance**。
2. 两个位置文字相同，但只有一个位置结合上下文后真正支持事实：这是**多个候选位置、一个潜在真位置**。
3. 旧数据已经丢失位置，无法判断属于上面哪一种：这是**位置不确定的部分标签**，不能伪装成 gold。

SQuAD、Natural Questions 等问答数据通常会保留某个具体 span 作为单次标注的位置，同时在开发集和测试集中接纳多个参考答案；FEVER 更进一步，直接把 gold 定义成多个可替代的完整证据集合；HotpotQA 则把答案和 supporting facts 分开评估。它们共同说明：**用于序列化的单一位置，与评估时允许的正确答案集合，不必是同一个东西。** citeturn2view0turn2view1turn2view3turn2view4turn2view5

对用户提出的 A—G，可以压缩成下面这组结论：

| 问题 | 结论 |
|---|---|
| A | 主流 benchmark 常见做法是“每次标注给出具体位置，多参考答案评估取任一合法答案”；证据型任务则常用 evidence sets |
| B | 完整数据层应保留全部经确认合法的位置；canonical span 只是兼容单位置格式的投影 |
| C | 任一**已登记为等价 gold**的位置命中应算正确；任一同字符串位置命中不能自动算正确 |
| D | 只能容纳一个位置时，从已确认合法集合中按固定规则选 canonical；位置未知时应屏蔽 span loss，而不是猜第一个 |
| E | 当前格式把一行视为穷举标签时，隔离整行是合理的保守策略；长期应改成事实级和损失级 mask |
| F | 有。更稳健的是“不可变源版本 + 结构位置 + start/end + exact quote + 前后文”的多锚点设计 |
| G | 小说事实库应把 outer OR 的替代 evidence sets、inner AND 的多段证据、版本信息、标注状态和训练资格一起写入合同 |

## 先把三种“多位置”分开

最容易出问题的地方，不是 offset 怎么存，而是把三种标签语义都装进了一个数组。

### 多个位置都是真的

设事实为 \(f\)，它有两个位置 \(s_1\) 和 \(s_2\)。如果读者只查看 \(s_1\) 或只查看 \(s_2\)，都能独立确认事实，那么 gold 可以写成：

\[
G_f=\{\{s_1\},\{s_2\}\}
\]

外层集合表示 **OR**：命中任意一个 evidence set 即可。

FEVER 的证据设计与此最接近。一个 claim 可以拥有多个相互替代的 evidence sets；每个 set 都必须完整支持或反驳 claim，系统只要找回其中一套完整集合，就可以满足证据要求。citeturn1view3turn2view5turn3view4

你们的重复句子如果两次出现都具有相同、完整的证明能力，应该保存为两个 singleton evidence sets，而不是把其中一个删除。

### 一个事实需要多段证据共同成立

有些事实不能靠单个句子证明，例如：

- 第一段说明“甲就是匿名作家”；
- 第二段说明“匿名作家写了某书”；
- 合起来才能推出“甲写了某书”。

这时应表示为：

\[
G_f=\{\{s_1,s_2\}\}
\]

集合内部表示 **AND**：只有同时命中 \(s_1\) 和 \(s_2\) 才算完整 provenance。

HotpotQA 把 supporting facts 定义成支持答案的一组句子，并单独计算 supporting-fact EM/F1；它还提供 joint 指标，要求答案和 supporting facts 同时正确。FEVER 对多句证据也要求找回一套完整 evidence set，而不是命中其中任意一句就给满分。citeturn1view2turn2view4turn2view5

因此，长期 schema 要同时支持：

- evidence sets 之间为 OR；
- 一个 evidence set 内的 members 为 AND。

单纯的 `valid_spans: [...]` 无法表达这个区别。

### 多个位置只是候选，不知道哪个是真的

假设某字符串在窗口里出现五次，但真正回答问题的只有第四次。弱监督问答研究明确指出，答案字符串的多次匹配会产生伪 span：字符串相同不代表每个出现位置都具有正确语义。早期系统常使用“第一次出现”等启发式规则，但这会把错误位置当成训练标签；后续工作把正确位置视为潜变量，在候选中做消歧。citeturn11view3turn12view0

这一情形更接近 partial-label learning，也就是“候选标签集合中至少有一个真标签，但不知道是哪一个”。它和 multi-label 不同：multi-label 表示多个标签都可接受；partial label 表示候选中只有未知的一部分是真实标签。citeturn11view5turn12view2

因此必须区分：

```text
gold_evidence_alternatives
```

和：

```text
unresolved_candidate_anchors
```

❌ 不能因为 `evidence_text` 在两个位置匹配，就把两个位置都塞进 gold alternatives。

这会把“我们不知道”错误转换成“两个都正确”。

## 主流 benchmark 的处理方式

### SQuAD：单次标注明确位置，评估接纳多个参考答案

SQuAD 的答案是文章中的连续 span。原始采集时，标注者直接在文章中高亮一个能够回答问题的最短文本范围；开发集和测试集又为每个问题补充了至少两个独立答案。citeturn1view0turn2view0turn3view0

评估时，Exact Match 和 token-level F1 都不会只对照一个参考答案，而是对所有人工参考答案计算，并取最高分。也就是说，**训练或单次标注可以有一个具体 span，评估 gold 却可以是一个答案集合。** citeturn2view1turn3view1

SQuAD 并没有把“文章里所有相同字符串的位置”自动列为合法 gold。合法性来自人工答案标注，而不是字符串搜索。因此它支持的是：

```text
任一人工认可答案
```

而不是：

```text
任一与 answer_text 相同的 occurrence
```

### Natural Questions：canonical 标注规则与多标注评估并存

Natural Questions 允许 short answer 是单个 span、一组 spans、yes/no 或空答案。训练集主要使用单个标注，开发集和测试集则为样本收集五个独立标注。citeturn1view1turn13view0

它的标注规范要求标注者选择最早出现、且包含充分信息的 HTML bounding box。这是一种 canonical policy：当页面里可能存在多个可用区域时，用稳定规则减少标注漂移。citeturn1view1turn2view2

但 NQ 没有假设这个 canonical 位置就是唯一真理。论文明确讨论了多个 long answer 都可能合理的情形；开发集和测试集通过五人标注形成参考集合，系统答案只要满足共识条件，并与至少一个被接受的人工答案对应，就可以获得正确判定。citeturn2view2turn2view3turn3view2

NQ 给出的经验很重要：

> 可以规定一个 canonical 选择规则来提高数据一致性，但评估层仍应承认其他人工确认的有效答案。

NQ 数据还明确写入 byte/token start 和 end，并规定 offset 的坐标体系；这也说明 span 数字脱离 source version、编码和边界约定后没有完整含义。citeturn13view0

### HotpotQA：答案正确与证据正确分开

HotpotQA 不只要求生成答案，还要求预测 supporting facts，也就是能够支撑答案的一组句子。数据提供 sentence-level supporting-fact supervision，并分别计算答案指标、supporting-fact 指标和 joint 指标。citeturn1view2turn2view4turn3view3

这种设计说明：

- 答案文本正确，不代表 provenance 正确；
- 找到相关句子，不代表答案正确；
- 真正严格的 grounding，应单独报告 provenance，再报告 joint correctness。

对于小说事实库，这比“只看 evidence_text 是否一致”更合适。一个模型可能生成了正确事实，却引用了另一个恰好包含同样句子的错误场景；事实分可以正确，provenance 分仍应判错。

### FEVER：直接把 gold 定义成 evidence-set alternatives

FEVER 的 claim 可以有多个 gold evidence sets。每个 set 是一套足以支持或反驳 claim 的最小证据；如果存在多套合法证据，系统找回任意一套完整集合即可。只找回集合的一部分，不满足严格 FEVER score 的证据条件。citeturn1view3turn2view5turn3view4

这几乎就是长期小说事实库最适合借鉴的结构：

```text
事实
  ├─ evidence set A：句子 A1
  ├─ evidence set B：句子 B1
  └─ evidence set C：句子 C1 + 句子 C2
```

A、B、C 之间是 OR；C1、C2 之间是 AND。

FEVER 还暴露了另一个现实问题：证据标注可能不完备。共享任务为测试数据补充证据，就是因为早期 evidence recall 并非天然完整。citeturn1view3

这意味着数据库必须明确写出：

```text
annotation_completeness = COMPLETE | PARTIAL | UNKNOWN
```

否则“数据里没有这个位置”会被错误理解成“这个位置不是合法证据”。

### Citation 与 attribution benchmark：出处正确性是独立维度

ALCE 等带引用的长文本生成评测，会分别检查答案质量和 citation quality，而不是把引用看成答案文本的附属字符串。AIS 的定义同样强调，输出应当能由一个可识别、独立的外部来源验证。citeturn11view0turn11view1

这类 benchmark 支持一个关键设计：

```text
fact correctness
provenance correctness
joint correctness
```

三项指标应分开保存和计算。

不能因为模型抽出了正确事实，就自动认为它引用的任意同文句子都正确；也不能因为 provenance 位置正确，就忽略事实值是否抽错。

## 训练与评估应怎样签合同

### 完整 gold 应保留所有经确认的合法位置

对于真正等价的位置，推荐保存：

\[
G_f=\{E_1,E_2,\ldots,E_k\}
\]

其中每个 \(E_i\) 是一套完整、充分的 evidence set。

canonical 只是函数：

\[
C_f=\operatorname{canonicalize}(G_f)
\]

它是为了满足：

- 单 span 模型；
- 确定性序列化；
- renderer 编号；
- 标注工具展示；
- 数据 diff 稳定。

它不应覆盖或删除 \(G_f\)。

这与 SQuAD 的多参考答案评估、NQ 的多标注答案集合，以及 FEVER 的替代 evidence sets 是一致的。citeturn2view1turn2view3turn2view5

### 多个合法 span 的训练方式

模型能够处理多位置监督时，推荐在所有合法位置上计算边际似然：

\[
\mathcal{L}_{span}
=
-\log \sum_{s\in V_f}P(s\mid x)
\]

其中 \(V_f\) 只包含**经过确认、每一个都合法**的 span。

这样模型把概率分配给任一合法位置都不会被惩罚。

也可以每轮从合法集合中稳定采样一个位置，但不建议把每个位置无权重地复制成独立样本。一个事实拥有五个等价位置时，如果复制五次，它会比只有一个位置的事实获得五倍训练权重。

⚠️ 边际化不能直接套在所有字符串匹配结果上。弱监督 QA 的研究表明，相同 answer string 的多个 occurrence 中可能只有一个真正回答问题；把全部字符串匹配都当 gold 会引入伪监督。citeturn11view3turn12view0

所以训练集合应区分：

```text
verified_valid_spans
```

和：

```text
string_match_candidates
```

只有前者能进入普通多答案 loss。

### 单位置格式怎样选 canonical

当现有训练格式只能放一个位置，推荐按以下条件选取，但候选范围只能是**已确认合法的 evidence sets**：

1. 证据必须完整、充分；
2. 多套证据都充分时，优先最小 evidence set；
3. 同为单 span 时，优先范围更精确的 span；
4. 仍然相同，再按稳定的文档阅读顺序；
5. 再相同时，用稳定的 `span_id` 做最终 tie-break。

“阅读顺序最早”可以作为**已验证等价答案之间的 canonical tie-break**。Natural Questions 也采用了“最早充分区域”的标注规则。citeturn1view1turn2view2

但它不能写成：

```text
在所有 evidence_text 匹配中默认取第一次
```

两句话表面相似，含义完全不同：

```text
✅ 在全部已验证合法位置中选择最早者
❌ 在全部字符串匹配位置中假设最早者合法
```

如果位置根本不可恢复，就不存在可合法选择的 canonical span。此时应：

```text
span_loss = MASK
```

而不是制造一个位置。

### 评估时任一等价位置是否算正确

答案是：**是，但必须是 gold 中明确登记的等价位置。**

推荐拆成三层：

| 指标 | 判定 |
|---|---|
| Fact / Answer correctness | 事实值或答案语义是否正确 |
| Provenance correctness | 是否命中任一完整 gold evidence set |
| Joint correctness | 前两项是否同时正确 |

对两个独立充分的重复位置：

```text
gold = {{span_1}, {span_2}}
```

预测任意一个都应获得完整 provenance 分。

对需要两段共同证明的事实：

```text
gold = {{span_1, span_2}}
```

只预测 `span_1` 可以获得诊断性的 evidence recall，但不应得到严格 provenance 满分。这与 FEVER 要求完整 evidence set、HotpotQA 单独提供 supporting-fact 与 joint 指标的方向一致。citeturn2view4turn2view5

如果模型只返回 evidence text，而无法返回 occurrence：

- 可以计算 evidence-text matching 的辅助分；
- 不能据此确认 provenance position；
- 两个相同 occurrence 存在时，严格 provenance 应视为 unresolved。

否则 provenance 指标最终又退化成了字符串指标。

## 对你们当前处置的判断

### `evidence_text + start/end` 方向正确，但还缺 source identity

你们将 canonical gold 改成：

```text
evidence_text + start/end
```

比只保存 evidence text 明显更可靠。brat 等 span 标注工具也采用 standoff annotation：标注与正文分离，用 start/end 指向具体文本范围，同时保存对应文本，便于校验。它使用 start inclusive、end exclusive 的半开区间。citeturn13view2

但严格说，canonical locator 至少应是：

```text
document_version_id
+ text_view_id
+ start
+ end
+ evidence_text
```

因为 `start=128` 只在某个确定的文本版本、某种文本表示里有意义。Natural Questions 使用 UTF-8 byte offset，W3C TextPositionSelector 使用 Unicode code-point position；两套系统的数字即使相同，也未必指向同一字符。citeturn13view0turn11view2

所以 `start/end` 字段必须同时声明：

```text
offset_unit
offset_base
end_convention
normalization
source_version
```

### Renderer 根据 offset 机械生成编号是正确的

“第一次出现”“第二次出现”这种编号属于展示层派生信息，不应成为 gold 的定位主键。

同一版本中，renderer 可以按照：

```text
(document_order, start, end, span_id)
```

排序后生成 occurrence 编号。

这样：

- 编号不需要人工维护；
- 插入新标注时不会污染 canonical gold；
- 不同 renderer 可以有不同显示方式；
- 数据层仍然保留实际位置。

因此，编号应是 derived field，不应写回 provenance 主记录。

### `LEGACY_POSITION_AMBIGUOUS` 是合适的状态

旧数据只有 evidence text，并且出现两个以上匹配时，标记：

```text
LEGACY_POSITION_AMBIGUOUS
```

是正确方向。

更完整的语义应是：

```text
事实内容可能仍然可信
证据文本可能仍然可信
具体 provenance position 未经确认
字符串匹配结果只是 candidates
```

不要把候选位置放入 `gold_evidence_sets`。可以单独保存：

```text
legacy_candidate_anchors
```

这既保留了未来人工修复的线索，又不会让训练程序误以为所有位置都合法。

如果能用规则、上下文或模型恢复位置，这个结果应被标为 weak / proposed provenance，而不是直接升级成 adjudicated gold。Snorkel 一类弱监督方法的核心思路也是把启发式标签视为有噪声信号，再进行聚合或校准，而不是把启发式输出直接当无误的人工标签。citeturn6search3

### 不默认取第一次是正确决定

默认第一次出现，相当于暗中加入了一条未经验证的标签规则：

```text
first_match == true_provenance
```

这在 NQ 中只有一个前提：标注者先判断该区域已经充分回答问题，然后才使用“最早充分区域”作为规范。它不是纯字符串 first-match。citeturn1view1turn2view2

弱监督 QA 中，相同答案实体多次出现而只有一个位置真正相关，是已知的噪声来源；直接采用第一次匹配会教模型学习位置偏差，而不是证据充分性。citeturn11view3turn12view0

### 临时隔离整行是合理的，但应说明适用条件

如果你们的训练格式把一行输出视为该窗口内的**完整事实清单**，那么删除其中一条歧义事实，会产生新的伪监督：

```text
该事实没有出现在 gold 输出
→ 训练程序把它理解成“不应该抽取”
```

部分标注 NER 研究明确讨论了这个问题：真实实体没有被标注时，如果训练程序默认把未标注 token 当作非实体，就会制造 false negatives。citeturn11view4turn12view1

因此，在当前系统无法做事实级 mask、又把缺失事实视为负标签的前提下：

✅ **隔离整个含歧义事实的样本，比删掉单条事实继续训练更安全。**

不过这应当是暂时的训练策略，而不是永久数据语义。长期应支持三类独立资格：

```text
eligible_for_fact_value_loss
eligible_for_provenance_loss
eligible_for_exhaustive_extraction_loss
```

例如一条 legacy 记录可以是：

```json
{
  "eligible_for_fact_value_loss": true,
  "eligible_for_provenance_loss": false,
  "eligible_for_exhaustive_extraction_loss": false
}
```

这样仍可利用可信的事实内容，又不会把未知位置或不完整清单变成负监督。

推荐规则是：

| 当前训练能力 | 处理 |
|---|---|
| 只能做整行穷举生成，无法 mask 单条事实 | 隔离整行 |
| 支持事实级 loss mask | 只屏蔽歧义事实的 provenance/span loss |
| 其他事实清单已确认完整 | 可继续训练其他事实，但不能删除歧义事实后假装清单仍完整 |
| 训练是 positive-only，不把未标注事实当负例 | 可保留已知正事实 |
| 能把位置当潜变量并正确建模候选 | 可作为 weak-supervision 样本单独训练，不并入 clean gold |

## 比 start/end 更稳健的 provenance 设计

不存在一个单独字段能同时兼顾精确定位、文本更新、跨格式和可审计性。更稳健的办法是保存多个互相校验的 anchor。

W3C Web Annotation Data Model 同时定义了 TextPositionSelector 和 TextQuoteSelector。前者使用 start/end；后者保存 exact quote，并可保存 prefix、suffix 来区分相同文本的多次出现。W3C 还允许同一目标携带多个 selector，以提高未来重新定位的成功率，并可记录资源的特定版本或时间状态。citeturn11view2turn14view3turn14view1

### 各种定位方式的优缺点

| 方式 | 优点 | 主要风险 |
|---|---|---|
| 只有 `evidence_text` | 人可读；文本小幅移动后仍可能重新搜索 | 重复文本无法区分；空格、标点、Unicode 归一化会影响匹配 |
| 只有 `start/end` | 精确指向 occurrence；提取和验证成本低 | 文本插入一个字符后，后续 offset 全部漂移；坐标单位不明会跨系统错位 |
| `start/end + exact` | 能定位，也能验证 slice 是否正确 | 文本版本变化后仍会失效；同样需要声明坐标体系 |
| `exact + prefix + suffix` | 可在轻微文本变更后重新锚定，也能消除重复句歧义 | 大规模改写、章节重排后仍可能失效 |
| 结构 ID + container-local offset | 章节或段落移动时仍较稳定 | 结构重新切分后需要迁移 |
| 不可变版本 + 内容 hash | 最强审计能力，可准确复现原标注 | 不能自动跟随新版文本 |
| 多锚点组合 | 可以交叉校验，并在一个 anchor 失效时尝试修复 | schema 和迁移程序更复杂 |

brat 的 offset 加 reference text、W3C 的 position 加 quote selector，都采用了“定位信息 + 文本断言”而不是二选一。citeturn13view2turn11view2

### 推荐的多锚点组合

对长期小说库，一条 span 推荐同时保存五类信息。

**源版本锚点**

```text
work_id
edition_id
document_version_id
text_view_id
content_sha256
```

这解决“offset 是相对哪一份文本”的问题。

**结构锚点**

```text
chapter_id
scene_id
paragraph_id
sentence_id
```

这些 ID 最好是不透明稳定 ID，而不是直接把“第 12 段”当 ID。序号可以派生，稳定 ID 用来引用。

EPUB CFI 一类规范也会把结构路径、范围位置和文本断言组合起来，用于在可重排文档中指向具体位置，并在部分文档变化后尝试恢复。citeturn13view3

**位置锚点**

```text
global_start
global_end
container_start
container_end
```

建议规范为：

```text
offset_base = 0
end_convention = exclusive
offset_unit = unicode_code_point
```

如果现有系统更适合 UTF-8 byte，也可以使用 byte，但必须固定写入 schema。NQ 使用 UTF-8 byte offset，而 W3C 文本位置使用 Unicode code points，正好说明“character offset”这个说法本身不够明确。citeturn13view0turn11view2

**文本断言锚点**

```text
exact
prefix
suffix
exact_sha256
```

`exact` 用来验证：

```text
text[start:end] == exact
```

`prefix` 和 `suffix` 用来区分相同 exact quote 的多个 occurrence。W3C TextQuoteSelector 就提供了这三个字段。citeturn5search6turn11view2

**标注与迁移状态**

```text
ADJUDICATED
EQUIVALENT_ALTERNATIVES
LEGACY_POSITION_AMBIGUOUS
SOURCE_VERSION_MISSING
ANCHOR_CONFLICT
MIGRATION_REQUIRED
```

其中 `ANCHOR_CONFLICT` 表示 offset 指向的 slice 与 exact 不一致，不能继续静默使用。

### `evidence_text` 应是断言，不是唯一 locator

推荐把字段角色写进合同：

```text
start/end：定位具体 occurrence
exact：验证定位结果和供人阅读
prefix/suffix：解决重复文本并辅助迁移
structure：缩小搜索范围
source version/hash：保证可复现
```

因此，更准确的 canonical key 不是：

```text
evidence_text + start/end
```

而是：

```text
source_version
+ text_view
+ structural_container
+ start/end
+ exact quote assertion
```

## 面向长期小说事实库的 schema

下面的结构兼容：

- 单句直接证据；
- 相同句子的多个合法 occurrence；
- 多句联合证据；
- legacy 位置歧义；
- 单位置 renderer；
- 多答案训练与评估；
- 文本版本迁移。

```json
{
  "schema_version": "evidence-provenance/1.0",

  "fact_id": "fact_01JXYZ...",
  "fact": {
    "subject": "人物甲",
    "predicate": "真实身份",
    "object": "匿名作家乙",
    "normalized_value": "匿名作家乙",
    "fact_status": "ADJUDICATED"
  },

  "source": {
    "work_id": "work_001",
    "edition_id": "edition_zh_001",
    "document_version_id": "docv_2026_08_07_001",
    "text_view_id": "plain_nfc_v1",
    "content_sha256": "sha256:...",
    "encoding": "UTF-8",
    "unicode_normalization": "NFC",
    "offset_unit": "UNICODE_CODE_POINT",
    "offset_base": 0,
    "end_convention": "EXCLUSIVE"
  },

  "gold_provenance": {
    "between_evidence_sets": "OR",
    "within_evidence_set": "AND",
    "canonical_evidence_set_id": "es_001",

    "evidence_sets": [
      {
        "evidence_set_id": "es_001",
        "sufficiency": "COMPLETE",
        "minimality": "MINIMAL",
        "status": "ADJUDICATED",
        "members": [
          {
            "span_id": "span_001",
            "role": "DIRECT_QUOTE",

            "structure": {
              "chapter_id": "ch_007",
              "scene_id": "scene_007_03",
              "paragraph_id": "para_007_03_014",
              "sentence_id": "sent_007_03_014_02"
            },

            "position": {
              "global_start": 182341,
              "global_end": 182368,
              "container_start": 19,
              "container_end": 46
            },

            "quote": {
              "exact": "他终于承认，自己就是匿名作家乙。",
              "prefix": "房间里沉默了很久。",
              "suffix": "她没有立刻回答。",
              "exact_sha256": "sha256:..."
            }
          }
        ]
      },

      {
        "evidence_set_id": "es_002",
        "sufficiency": "COMPLETE",
        "minimality": "MINIMAL",
        "status": "ADJUDICATED",
        "members": [
          {
            "span_id": "span_002",
            "role": "DIRECT_QUOTE",

            "structure": {
              "chapter_id": "ch_019",
              "scene_id": "scene_019_01",
              "paragraph_id": "para_019_01_006",
              "sentence_id": "sent_019_01_006_01"
            },

            "position": {
              "global_start": 491820,
              "global_end": 491847,
              "container_start": 0,
              "container_end": 27
            },

            "quote": {
              "exact": "他终于承认，自己就是匿名作家乙。",
              "prefix": "多年后，旧事再次被提起。",
              "suffix": "这一次，没有人感到意外。",
              "exact_sha256": "sha256:..."
            }
          }
        ]
      }
    ]
  },

  "annotation": {
    "provenance_status": "EQUIVALENT_ALTERNATIVES",
    "position_certainty": "EXACT",
    "label_completeness": "COMPLETE",
    "annotator_ids": [
      "ann_014",
      "ann_027"
    ],
    "adjudicator_id": "adj_003",
    "annotation_revision": 4,
    "created_at": "2026-08-07T09:00:00+09:00",
    "updated_at": "2026-08-07T11:30:00+09:00"
  },

  "training_disposition": {
    "eligible_for_fact_value_loss": true,
    "eligible_for_provenance_loss": true,
    "eligible_for_exhaustive_extraction_loss": true
  },

  "audit": {
    "supersedes_record_id": null,
    "migration_history": [],
    "notes": "两个位置均可独立、完整地证明该事实。"
  }
}
```

这里的两个 `evidence_sets` 都只含一个 member，表示两个 occurrence 各自都能独立证明事实。评估命中 `es_001` 或 `es_002` 都正确。

如果事实需要两段共同证明，应写成一个 set 中包含两个 members：

```json
{
  "evidence_set_id": "es_003",
  "sufficiency": "COMPLETE",
  "members": [
    {
      "span_id": "span_003"
    },
    {
      "span_id": "span_004"
    }
  ]
}
```

这时只命中其中一个 span 不算完整 provenance。

### Legacy 歧义记录应怎样写

无法恢复旧位置时，不应伪造 `gold_provenance.evidence_sets`。推荐结构是：

```json
{
  "fact_id": "fact_legacy_001",

  "unresolved_provenance": {
    "evidence_text": "他终于承认，自己就是匿名作家乙。",
    "reason_code": "LEGACY_POSITION_AMBIGUOUS",

    "candidate_anchors": [
      {
        "candidate_id": "candidate_001",
        "global_start": 182341,
        "global_end": 182368,
        "candidate_status": "STRING_MATCH_ONLY"
      },
      {
        "candidate_id": "candidate_002",
        "global_start": 491820,
        "global_end": 491847,
        "candidate_status": "STRING_MATCH_ONLY"
      }
    ]
  },

  "annotation": {
    "provenance_status": "LEGACY_POSITION_AMBIGUOUS",
    "position_certainty": "AMBIGUOUS",
    "label_completeness": "UNKNOWN"
  },

  "training_disposition": {
    "eligible_for_fact_value_loss": true,
    "eligible_for_provenance_loss": false,
    "eligible_for_exhaustive_extraction_loss": false
  }
}
```

🔥 `candidate_anchors` 不能进入正常 gold 评估。

它们表达的是：

```text
答案可能在这里
```

而 `evidence_sets` 表达的是：

```text
这里已经被确认是正确、充分的证据
```

### canonical 应落在哪一层

`canonical_evidence_set_id` 是操作性字段，用于：

- 单位置模型导出；
- C2 renderer；
- 人工界面默认定位；
- 稳定 snapshot；
- 数据版本 diff。

它不表示其他 evidence sets 比较“不正确”。

如果 canonical set 含多个 members，而旧模型只能容纳一个 span，应直接标记该样本与模型格式不兼容，不建议任取一个 member 冒充完整证据。

## 验收、迁移与数据治理规则

为了让未来几万条数据不再重复踩坑，建议把以下规则做成写入时的硬校验，而不是依赖人工记忆。

### 写入校验

每个已确认 span 必须满足：

```text
source version 存在
content hash 可验证
start < end
text[start:end] == quote.exact
span 位于声明的 paragraph/sentence container 内
canonical_evidence_set_id 存在于 evidence_sets
每个 COMPLETE evidence set 至少有一个 member
```

如果 `text[start:end] != exact`，记录应进入：

```text
ANCHOR_CONFLICT
```

不能由程序静默重新搜索第一个 exact match。

### 重复文本校验

当 `exact` 在 source version 中出现多次：

```text
允许写入
但必须有明确 start/end
并要求结构锚点或 prefix/suffix 可以区分
```

重复 evidence text 本身不是错误；缺少可区分的 provenance 才是错误。

### 文本版本变更

编辑、校对或重新分段产生新文本时：

```text
旧 document_version 不修改
创建新 document_version
运行 anchor migration
记录 old_span_id → new_span_id
重新验证 exact、prefix、suffix 和结构位置
```

W3C 的 selector/state 设计同样把“定位方式”和“目标资源的具体状态”分开，以便在资源发生变化时保留可追溯性。citeturn14view0turn14view1turn14view3

迁移程序找到一个唯一高置信位置时，也不应无痕覆盖旧记录。推荐状态流转为：

```text
LEGACY_POSITION_AMBIGUOUS
→ MACHINE_PROPOSED
→ HUMAN_VERIFIED
→ ADJUDICATED
```

### 训练资格应由状态派生

建议不要让训练脚本自行猜测哪些数据能用。由数据合同统一映射：

| 状态 | fact loss | provenance loss | exhaustive row loss |
|---|---:|---:|---:|
| `ADJUDICATED` + `COMPLETE` | 开 | 开 | 开 |
| `EQUIVALENT_ALTERNATIVES` + `COMPLETE` | 开 | 开，多 gold | 开 |
| `LEGACY_POSITION_AMBIGUOUS` | 视事实可信度 | 关 | 关 |
| `PARTIAL_LABEL` | 可做 positive-only | 关或专用 weak loss | 关 |
| `ANCHOR_CONFLICT` | 暂停 | 关 | 关 |
| `SOURCE_VERSION_MISSING` | 视情况 | 关 | 关 |

这样，“隔离整行”不再是人工临时操作，而是状态驱动的稳定行为。

### 推荐写入合同

可以把最终原则压缩成这段规范：

> 每条事实的 gold provenance 由一个或多个完整 evidence sets 构成。evidence sets 之间为 OR，set 内 spans 之间为 AND。每个 span 必须指向一个不可变 source version，并同时保存结构锚点、明确坐标体系下的 start/end、exact quote 及必要的 prefix/suffix。canonical provenance 仅用于单位置格式和确定性渲染，不会删除其他合法 alternatives。字符串匹配产生的位置只属于 candidates，未经确认不得进入 gold。位置不可恢复的 legacy 数据标记为 `LEGACY_POSITION_AMBIGUOUS`，不得默认选择第一次出现；训练系统无法屏蔽单条歧义标签且把一行视为穷举事实时，应隔离整行，直到支持事实级、provenance 级和完整性级 loss mask。

这套合同下，gold 不再被迫在“唯一位置、等价答案、provenance”三者中三选一：

- **事实 gold** 定义语义；
- **evidence sets** 定义哪些 provenance 可接受；
- **canonical span** 提供工程上的唯一表示；
- **annotation status** 诚实表达哪些地方仍然未知。