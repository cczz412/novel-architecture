✅ 结论：当前应继续用 C2_FULL 做主方案。D_RANGE 暂时不值得替换 C2。

你们现在用 4.2 个 token、约 5.9% 的输出缩短，换来了：

- Schema +4.17 个点；
- Semantic F1 −8.93 个点；
- 语义命中事实从 42 个降到 37 个。

而且两边一旦语义命中，证据位置都完全正确。这说明当前 D 的主要问题不是“端点写错”，而是它让模型更容易在前面的事实选择、答案组织阶段少选或错选。

说白了就是：range 是一种压缩编码。压缩会减少输出，但不会自动降低任务本身的不确定性；对小模型，显式列出每个 ID 反而可能提供更清楚、更冗余的监督。

## A. 最相关研究和 GitHub

| 研究                                                         | 和你们最相关的发现                                           | 实现                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| [Adapting Pre-trained Generative Models for Extractive QA](https://aclanthology.org/2023.gem-1.11/) | 直接比较完整索引 FI 和起止索引 SI。MultiSpanQA 上 BART-large：Exact F1 都是 0.68，Partial F1 是 FI 0.82、SI 0.81；其他数据集也基本持平或 FI 略高。SI 还多出奇数端点、start>end、重叠、越界等非法状态。 | [GenAI4EQA](https://github.com/prabirmallick/GenAI4EQA)，但目前基本只有 README，不算可直接跑的实现 |
| [Learning Recurrent Span Representations](https://arxiv.org/abs/1611.01436) | 显式给整个 span 打分，优于把 start/end 或单词分别预测。说明“两个端点更短”不等于“两个端点独立预测更准”。 | 论文为主                                                     |
| [Rethinking the Objectives of Extractive QA](https://aclanthology.org/2021.mrqa-1.2/) | 独立 start/end 会把两个候选答案的开头和结尾交叉拼接；联合 span 目标能修掉这类错误。 | [JointSpanExtraction](https://github.com/KNOT-FIT-BUT/JointSpanExtraction) |
| [BERT](https://aclanthology.org/N19-1423/)                   | 经典做法：分别给每个输入位置算 start/end 分数，再选合法组合。强编码器、大数据下很有效，但仍不是联合 span 评分。 | 常见 QA 实现都采用这类 head                                  |
| [A Simple and Effective Model for Answering Multi-span Questions](https://aclanthology.org/2020.emnlp-main.248/) | 把多段答案改成逐 token 的 BIO/IO 标注，在 DROP、Quoref 分别提升 9.9、5.5 EM。 | [tag-based-multi-span-extraction](https://github.com/eladsegal/tag-based-multi-span-extraction) |
| [MultiSpanQA](https://aclanthology.org/2022.naacl-main.90/)  | 多段场景里，序列标注比单 span 模型高 30 多个 Exact F1 点；用一个大范围包住多个离散 span，通常表现为召回高、精度低。 | [MultiSpanQA](https://github.com/haonan-li/multispanqa)      |
| [Pointer Networks](https://papers.nips.cc/paper/5866-pointer-networks) | 直接指向输入位置，特别适合位置选择；但它是专门的网络结构，不等于让普通 LLM 输出字符串 `"T03"`。 | 论文与社区实现较多                                           |
| [Locate and Label](https://aclanthology.org/2021.acl-long.216/) | boundary regression 是从候选 span 出发，学习左右偏移量来修正边界；不是简单输出 start/end 字段。 | [locate-and-label](https://github.com/tricktreat/locate-and-label) |
| [LongCite](https://aclanthology.org/2025.findings-acl.264/)  | 同时使用单句 `[k]` 和连续范围 `[a-b]`，不是纯 range；依赖 LongCite-45k 微调、few-shot 示例和非法 range 后处理，没有做 list-vs-range 消融。 | [THUDM/LongCite](https://github.com/THUDM/LongCite)          |

### label entropy 为什么没有想象中低

“标签熵”可以直接理解成：模型要在多少种正确含义之间做选择。

设一共有 (n) 个 unit：

| 目标约束               | 可能的语义答案数  | ID list  | range             |
| ---------------------- | ----------------- | -------- | ----------------- |
| 固定长度 (k) 的连续段  | (n-k+1)           | 一一对应 | 一一对应          |
| 任意长度的一段连续区间 | (n(n+1)/2)        | 一一对应 | 一一对应          |
| 任意 (k) 个离散 ID     | (\binom nk)       | 可表达   | 单 range 无法表达 |
| 恰好 (r) 段连续区间    | (\binom{n+1}{2r}) | 可表达   | 需要 (r) 个 range |

🔥 如果 gold evidence 已经限定为“一段连续区间”，list 和 range 表达的是同一批答案，它们的语义熵完全相同。range 只缩短了字符串。

对连续的 `T03,T04,T05`，模型生成 `T03` 后，后面两个几乎是“下一个、再下一个”，并不是三个互相独立的高难选择。range 则把同样的信息压进两个高信息量端点；任何端点错误都会改变整段覆盖。

如果 C2 允许 ID 任意排序，同一个集合会有 (k!) 种字符串，这会平白增加难度。建议强制：

- 升序；
- 去重；
- 固定 ID 宽度；
- evaluator 按集合比较。

### 1、2、3 个连续 unit 的实际难度

| 连续长度 | C2 ID list            | start/end            | 判断                                         |
| -------- | --------------------- | -------------------- | -------------------------------------------- |
| 1        | `["T03"]`             | `start=T03, end=T03` | C2 更简单；range 不但没省 ID，还多了相等约束 |
| 2        | `["T03","T04"]`       | `start=T03, end=T04` | 都输出两个 ID；range 没有压缩收益            |
| 3        | `["T03","T04","T05"]` | `start=T03, end=T05` | range 只少一个 ID，未必抵得过端点学习难度    |
| 4+       | ID 数继续增长         | 始终两个端点         | range 才开始有明显 token 优势                |

离散证据可以拆成 (r) 个连续 run，总共有 (k) 个 ID。普通多 range 需要 (2r) 个端点，因此只有：

[
2r < k
]

也就是平均每段长度超过 2 时，range 才真正少输出 ID。大量 singleton 或长度 2 的 run，会让 multi-range 与 list 一样长，甚至更长。

### 四类常见方法怎么选

| 方法                | 优点                                         | 麻烦点                                                       |
| ------------------- | -------------------------------------------- | ------------------------------------------------------------ |
| Pointer network     | 直接指向输入位置；end 可以依赖 start         | 需要专门结构和训练；普通生成式 LLM 没有这个能力保证          |
| BIO/IO tagging      | 每个 unit 都有显式监督；天然支持多段         | 要对全部 unit 分类，负标签很多；嵌套、重叠实体需要扩展       |
| Span classification | 直接联合判断整个 `(start,end)`；避免交叉边界 | 候选数通常是 (O(n^2))，需要限长或剪枝                        |
| Boundary regression | 能利用“偏了一格、两格”这样的距离关系修正候选 | 依赖候选 span、回归损失和取整；你们的 D_RANGE 不属于这种方法 |

## B. C2 和 D 最可能的错误机制

| C2_FULL                                        | D_RANGE                                              |
| ---------------------------------------------- | ---------------------------------------------------- |
| 要判断输出多少个 ID，容易漏 ID、重复、提前结束 | 固定两个字段，结构更稳定                             |
| 变长数组带来逗号、引号、顺序等 Schema 错误     | 要学会“哪里开始、哪里结束”的额外抽象                 |
| ID 越多，串行生成错误机会越多                  | 一个端点错，可能整段多覆盖或少覆盖                   |
| 但每个 evidence unit 都显式出现，监督清楚      | 中间 unit 不再显式出现在目标中，监督被压缩           |
| 离散证据天然可表达                             | 单 range 无法精确表达中间有空洞的证据                |
| 排序后的连续 ID 有很强的局部规律               | singleton 必须学会 `start=end`，还要维持跨字段一致性 |

经典独立边界错误是这样的：

- 合理答案 A：`T03–T04`
- 合理答案 B：`T08–T09`
- start 对 `T03`、`T08` 都很有信心；
- end 对 `T04`、`T09` 都很有信心；
- 独立组合可能产出从没存在过的 `T03–T09`。

你们的 D 是自回归生成，end 会看到已经生成的 start，所以不算严格独立。但它仍然没有“对整个 span 联合评分”的保证。

更关键的是：D 在语义命中后的 37/37 都机械正确。因此这次 DEV 中，经典 boundary error 看起来不是主因。D 少掉的命中更可能发生在事实选择和答案生成阶段。

⚠️ 如果 D 的 evaluator 只检查“完整覆盖 gold”，还要补一个“展开后的证据精度”。`T03–T09` 可能完整覆盖 gold，却把大量无关 unit 一起圈进来。

## C. 为什么 C2 语义更好，D 看起来稍稳定

C2 更好，可能是几个因素叠加：

- 每个 evidence unit 都进入训练目标，相当于额外的逐 unit 监督；
- 它不要求证据连续，更符合多事实、多段支持；
- 连续 ID 的后续项很容易通过局部规律生成；
- 模型不用同时完成“选证据”和“把集合压缩成边界”两件事。

D 的 Schema 更高，则很好解释：

- 始终两个字段；
- 不用判断数组长度；
- 分隔符更少；
- 输出更短，提前截断或格式漂移的机会更少。

不过，75.00% 和 79.17% 很像 18/24 与 19/24。如果 DEV 确实是 24 条，这个 Schema 优势其实只有 1 条样本，暂时不能叫稳定结论。

现代生成式 LLM 也没有普遍表现出“更擅长两个边界”。最接近的 FI/SI 对照研究显示两者接近、FI 还经常略高。一个 [2025 年多标签 LLM 研究](https://arxiv.org/abs/2505.17510)发现，自回归 LLM 更像是在连续做多次单标签判断，而不是一次性形成完整标签集合；这会带来漏项和顺序问题，但并不能推出 start/end 更容易。

## D. D 是否值得保留

✅ 值得保留，但定位应降为：

- 长连续 evidence 的专项备选；
- token 成本实验；
- 显示、存储或传输时的压缩格式；
- C2 的对照组。

❌ 目前不适合继续作为替换 C2 的主候选。语义差 8.93 点，远大于 5.9% 的 token 节省。

更划算的做法是：模型继续输出 C2，程序自动把连续 ID 压成 range。这样保住模型的语义表现，同时得到下游的紧凑表示，只是不能节省模型生成阶段的 token。

## E. 不训练或极少训练的最小实验

建议先做一个 100 条左右的成对实验，同一条数据同时跑 C2 和 D。

### 先直接重算现有结果

给每条 gold evidence 增加三个统计量：

```text
k = gold ID 总数
r = 最大连续段数量
gap = 从最小 ID 到最大 ID 之间的非证据 unit 数
```

分成五桶：

1. `k=1, r=1`
2. `k=2, r=1`
3. `k=2, r=2`
4. `k>=3, r=1`
5. `k>=3, r>1`

这一步不需要重新推理。把 C2 list 和 D range 都展开成 ID set，然后比较：

- Semantic F1；
- expanded-set Exact Match；
- unit Precision / Recall / F1；
- Schema；
- start/end 偏移；
- range 多覆盖了多少无关 unit；
- 输出 token。

错误曲线以 (k) 为横轴，同时把 `r=1` 和 `r>1` 分开画。只按 ID 数分桶会把“数量难度”和“不连续难度”混在一起。

### 再做两层 prompt-only 测试

- Oracle 格式测试：直接告诉模型正确 ID set，只让它转换成 C2 或 D。这个主要检查序列化和边界压缩。
- End-to-end 测试：同一个 checkpoint、同一个输入，唯一差异是目标 Schema。这个检查格式是否反过来干扰语义选择。

每桶先取 20 条，temperature 设为 0，最大输出长度设得足够大，避免 C2 因截断吃亏。如果差距很接近，再换 3 组 few-shot 示例顺序重复。

如果现有 C2/D 是分别训练的模型，这个 prompt-only 对照很重要，否则当前差异可能混有训练随机性、样本顺序或 checkpoint 差异。

只有 prompt-only 已经接近时，才值得补一个很小的 LoRA/SFT：

- 约 200 条；
- 五桶均衡采样；
- C2/D 使用完全相同样本、步数和超参数；
- 最好跑 3 个随机种子。

## F. 什么结果才值得改成 range

我建议用下面的门槛，而不是只看平均分：

- D 的整体 Semantic F1 不劣于 C2 超过 1 个点；
- 通过“成对 bootstrap”置信区间确认差异不是几条样本造成；
- 每个主要桶都不能回退超过 2 个点；
- `k>=3、r=1` 桶里，D 至少明显优于 C2，或者在语义持平时节省 15% 以上总输出 token；
- 展开后的 evidence set F1 与 Exact Match 不低于 C2；
- 不连续证据有明确的 multi-range 方案；
- Schema 至少不退步；
- 多个 prompt/checkpoint 重复后方向一致。

按这个门槛，当前结果离切换还很远：token 只省 5.9%，语义却掉了 8.93 点。

## G. 更合适的 hybrid representation

不建议让模型在“单 ID / 单 range / 多 range”三种 JSON 类型之间自行选择。那会增加一个新的格式决策。

更简单的是始终使用同一种 Schema：

```json
{
  "evidence_spans": [
    {
      "start_id": "T03",
      "end_id": "T05"
    },
    {
      "start_id": "T09",
      "end_id": "T09"
    }
  ]
}
```

它的含义固定：

- 单 ID：`start_id == end_id`
- 一段连续证据：数组只有一个元素
- 多段证据：数组里有多个元素
- evaluator 按闭区间自动展开为 ID set

Evaluator 再统一做这些检查：

- ID 必须存在；
- `start <= end`；
- ranges 升序且不重叠；
- 相邻 ranges 自动合并，或判为非 canonical；
- singleton 必须写成相同 start/end；
- 最终一律展开为 set 后评分。

不过，结合当前结果，我更推荐的生产路径仍是：

```text
小模型输出排序后的 C2 ID list
            ↓
evaluator 转成 canonical ID set
            ↓
程序按连续 run 自动压成 single/range/multi-range
```

🔥 这样把“语义选择”留给模型，把“压缩编码”交给确定性程序。对现在的 MICRO24 M1，这是风险最低、也最符合你们数据的方案。

来源：ChatGPT