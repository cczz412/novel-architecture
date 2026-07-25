# 包B｜判分法改法调查

## 1. 结论先行

- ✅ 保留现有“严格”尺；把“有效召回”改成“严格命中＋关键语义完整、锚全部过闸的可用部分命中”，不要再让所有“有效影子”按完整一条计数。
- ✅ 判分拆成三条独立轴：**语义完整度、锚支持度、对齐与去重质量**；语义相似不能抵消锚无效。
- ✅ 一条金标可以由多条预测合并补齐；一条预测默认只能给一条金标计分，除非先拆成真正独立的子主张。
- ✅ 部分分应来自“若干可检查单元分别命中”，不建议让 LLM 直接拍一个不透明的 0.7 分。
- ✅ 嵌入只做候选召回；NLI／专用对齐模型检查最小证据；数字、否定、角色、时间走硬规则；模糊项人工终审。
- ✅ LLM judge 只能当辅助标注员：固定 rubric、盲化来源、交换顺序、异构法官复核，并用人工裁决集校准。
- ✅ 双尺回答“整体成绩如何”，不劣化闸回答“历史完整条有没有退步”；两者并列展示，不合成一个总分。
- ⚠️ 评分合同一旦变化，旧分与新分不可直接横比，必须全量重跑基线并冻结版本。

------

## 2. 可操作建议清单

### 1）把“有效影子”改成两档可审计的部分命中

**动作**

建议保留四个读数，但重新定义中间档：

| 读数               | 建议定义                                                     | 是否用于过闸 |
| ------------------ | ------------------------------------------------------------ | ------------ |
| **严格召回**       | 语义完整；全部必需单元有锚支持；所有挂出锚都能支持至少一个主张单元；无冲突 | 主尺         |
| **可用召回**       | 严格命中＋“核心事件和全部关键单元均正确且有锚，仅缺非关键单元” | 第二主尺     |
| **支持型加权召回** | 按已正确且有锚支持的判分单元累计部分分                       | 诊断／排序尺 |
| **表面触达率**     | 句子碰到了相关语义，但不要求锚成立                           | 只作诊断     |

这里的“判分单元”可以直接理解成：把一条金标拆成几个最小、能单独回答“对不对”的部分，例如核心事件、主体、客体、极性、时间、数量、限定条件。v1 建议单元内采用 0／1 判定，部分分来自“命中了几个单元”，而不是让法官自由输出任意小数。只有分类层级、范围重叠等已经写进合同的情况，才允许固定折扣。

**依据／来源链接**

MUC 评测把结构拆成原子填充值，再记录正确、错误、部分正确、遗漏和多报；SemEval DDI 同时报严格边界、部分边界和类型匹配；统一结构化评测框架也把这类指标归纳为“相似度＋有约束的最优对齐”。BenchIE 则用同一事实的可接受表达簇处理语义等价。CaRB 还显示，匹配代码本身的差异就可能改变系统排名，因此“影子怎么认定”必须写进合同，不能藏在人工经验里。([ACL文摘](https://aclanthology.org/S13-2056.pdf))

**对我方双尺的对照判词**

- **严格**：方向正确，建议保留，但补足“语义完整”和“所有锚有效”的可执行定义。
- **有效召回**：概念可留，名称建议改成“可用召回”；现有“有效影子”过宽，应拆成“可用部分”和“普通部分”。
- **表面覆盖**：建议改名“表面触达率”，避免管理报表把它误解成有效能力。
- **部分分**：可以进入分析和模型排序，但不能抵消严格尺或锚闸。

------

### 2）用全局对齐处理“一对多、多对一”，禁止重复领分

**动作**

建立章节级全局对齐图，不要按输出顺序逐条贪心匹配：

1. 每条预测先拆成“虚拟子主张”。已经足够原子的，保持一条；包含两个独立事实的，拆成两条并记录 `atomicity_violation=true`。
2. 每个虚拟子主张最多给一条金标分配语义分，防止一个模糊长句同时命中多条金标。
3. 一条金标可以接收多条预测。最终取这些预测覆盖到的**不同判分单元的并集**，重复表达同一单元不增加分数。
4. 多个锚只是同一主张的证据，锚数量本身不增加命中数。
5. 同一金标收到互相矛盾的预测时，不允许只挑有利句子；必须记冲突并送人工裁决。
6. 对齐目标应是全章总支持分最高，同时满足上述容量限制，而不是“谁先出现谁先占位”。

CEAF 类指标使用最大二分匹配控制预测与参考对象的对应关系；CEAF-RME 又展示了在特定任务中放宽单侧约束、允许多条预测指向同一参考对象的做法。统一结构化评测论文也明确区分双侧约束和单侧约束。你们的场景适合“预测侧限一、金标侧可多”的做法。([ACL文摘](https://aclanthology.org/2023.eacl-main.136.pdf))

**常见坑**

- 一个宽泛句子给多条金标重复领分。
- 把完整事实拆成很多碎片，靠碎片数量刷部分分。
- 重复输出同一事实，被误算成多次覆盖。
- 贪心对齐受输出顺序影响。
- 跨句拼接时偷偷补入原文没有明确表达的桥接关系。
- 只合并支持性句子，忽略另一条预测中的否定或冲突。
- 为了召回给一句话挂很多锚，增加“至少有一个锚能托住”的概率。

**对我方双尺的对照判词**

严格和可用召回都应在**全局去重对齐完成后**计算。否则分母虽然固定，分子仍可通过重复、拆句和模糊长句被放大。

------

### 3）把“锚有效”从事实级布尔值改成主张单元与锚的支持关系表

**动作**

对每个“主张单元—锚”关系记录以下状态：

- `SUPPORT`：锚直接支持该单元。
- `IRRELEVANT`：锚合法，但与该单元无关或证据不足。
- `CONTRADICT`：锚与该单元直接冲突。
- `UNCLEAR`：涉及省略、跨句指代、隐含推理，自动系统无法稳定判断。

同时拆开三个概念：

| 字段                     | 说明                                   |
| ------------------------ | -------------------------------------- |
| `anchor_id_valid`        | 锚 ID 是否存在、格式是否合法           |
| `claim_support_coverage` | 有多少主张单元至少得到一个锚支持       |
| `anchor_link_precision`  | 挂出的锚中，有多少至少支持一个主张单元 |

推荐判法：

- **严格命中**：所有必需单元均被支持，`anchor_link_precision=1`，且无冲突。
- **可用命中**：核心和全部关键单元均被支持，所有挂出锚均有效，仅缺非关键单元。
- 某个额外锚无关时，已经被其他锚支持的单元可以保留原始部分分，但该事实不能通过严格／可用锚闸。
- 锚出现直接冲突时，核心或关键单元应判 0，并进入冲突计数。
- 多锚联合支持只允许覆盖各自明确表达的单元；需要复杂指代或隐含桥接时，必须人工终审。

MUC 的原子填充值思路说明，结构对象内部各部分应分别对齐和计分，而不是给整条对象一个不可解释的布尔标签。([ACL文摘](https://aclanthology.org/M98-1030.pdf))

**对我方双尺的对照判词**

现有“语义锚无效”计数建议拆成：

- `非法锚 ID`
- `合法但不支持`
- `直接冲突`
- `自动系统无法判定`

其中“合法但不支持”才对应你们当前最关心的“锚 ID 合法但原文托不住主张”。这样能看出问题出在 ID、证据不足，还是事实反转。

------

### 4）中文长文本自动判定采用“召回—核验—硬规则—人工”四段式

**动作**

| 环节              | 推荐职责                                             | 不应承担的职责           |
| ----------------- | ---------------------------------------------------- | ------------------------ |
| 中文嵌入模型      | 从整章中找出最可能对应的金标、预测和证据片段         | 直接决定语义等价或锚有效 |
| NLI／专用对齐模型 | 判断最小证据片段是否支持、冲突或无法推出某个原子主张 | 单独决定最终严格命中     |
| 硬规则            | 检查数字、日期、范围、否定、可能性、角色方向、时序   | 处理复杂同义改写         |
| 人工终审          | 处理跨句指代、隐含主语、联合证据、模型分歧和高风险项 | 全量重复做机械检查       |

推荐流程：

1. 嵌入模型召回 top-k 候选对齐关系，阈值偏向高召回。
2. 把长章切成最小可解释证据片段，再送 NLI／AlignScore 类模型判断。
3. 对人物角色、施事与受事、否定词、可能／确定、前后时间、数值和单位做独立硬校验。
4. 自动模型给出 `SUPPORT / CONTRADICT / UNCLEAR`，不要直接给最终 S／E 档。
5. 在本地病例域人工裁决集上校准阈值，按否定、数字、角色互换、跨句证据等切片分别看误放行率。

C-MTEB 覆盖六类中文嵌入任务和 35 个数据集，BGE-M3 可处理最多 8192 token 的长文档；这些结果主要说明它们适合语义检索，并不能证明某条主张被原文蕴含。OCNLI 提供约 5.6 万对中文 NLI 数据，其论文当时报告的最佳基线仍比人工低约 12 个百分点。SummaC 还表明，句级 NLI 直接套到长文档会出现粒度错配，切句后聚合更有效。([ACL文摘](https://aclanthology.org/2020.findings-emnlp.314/))

专用对齐模型如 AlignScore 可以覆盖蕴含、复述、事实核验等多类一致性判断，但仍须做中文病例域校准。HANS 显示 NLI 模型可能过度依赖词面重叠、子序列等捷径；EQUATE 显示数量推理也是明显弱点。因此数字、否定、角色互换和时序不能只交给语义模型。([ACL文摘](https://aclanthology.org/2023.acl-long.634/))

**对我方双尺的对照判词**

- 嵌入相似度只能帮助“找候选”，不能直接把条目送进严格或有效召回。
- NLI／对齐模型的高分也不能抵消无效锚。
- 中文病例中的否定、病程时间、数量变化、主体错位，应设独立硬闸。
- `UNCLEAR` 不能自动按命中处理。

------

### 5）LLM-as-judge 采用固定 rubric、顺序互换和人工校准

**动作**

推荐按以下方式使用：

1. **绝对判档用逐项评审**：让法官按固定字段判断语义单元、锚支持和冲突，不让它自由写总评。
2. **系统比较才用成对评审**：候选 A/B 各评一次，再交换为 B/A；结论变化就标记为不稳定。
3. **先给证据映射，再给标签**：要求输出支持的主张单元、对应证据片段和原因代码，而不是只给分。
4. **盲化生成来源**：不展示模型名、厂商名、历史成绩；尽量不用与抽取模型同系列的单一法官。
5. **困难项使用异构法官**：选择不同模型家族，而不是同一模型换三个提示词；分歧项交人工。
6. **建立人工裁决校准集**：按章节、命中档、锚状态、否定、数字、角色、长距离证据等分层抽样。
7. **报告误放行率**：除总体一致率外，至少看 S／E 档混淆情况、冲突漏检率、锚无效漏检率。
8. **冻结法官版本**：记录模型版本、rubric 版本、温度、输入格式和调用日期；升级后重新校准。

MT-Bench 论文归纳了位置、冗长、自我偏好和推理能力不足等问题；FairEval 显示只改变候选顺序就可能明显改变排名，并提出多证据、平衡顺序和人工介入校准；Length-Controlled AlpacaEval 进一步证明自动法官会偏爱更长回答。([arXiv](https://arxiv.org/abs/2306.05685))

另有研究显示，LLM 可能识别并偏爱自身生成风格；G-Eval 说明明确评测步骤和表单式输出有帮助，但也观察到对 LLM 文本的偏好。PoLL 在其研究设置下用不同模型家族组成法官组，减少了单一模型内部偏差；JUDGE-BENCH 则发现法官可靠性随任务、属性和文本来源大幅变化，因此任何法官都必须先与人工判断对齐。([arXiv](https://arxiv.org/abs/2404.13076))

**对我方双尺的对照判词**

- LLM judge 可以给出候选标签，**不能单独决定严格命中、不劣化放行或锚冲突终判**。
- 金标、病例证据和锚信息只能进入隔离的离线评测环境；不得进入生产抽取 Prompt。
- 若“禁止进入模型窗”也覆盖所有外部评测模型，则 LLM judge 应换成本地隔离模型，或只让规则系统与人工完成终判。

------

### 6）双尺、预测质量和不劣化闸分成三个报表区

**动作**

#### A. 召回区：回答“固定金标被覆盖了多少”

- `strict_recall`
- `usable_recall`
- `supported_weighted_recall`
- `surface_touch_rate`，明确标注“诊断，不参与过闸”

#### B. 预测质量区：回答“输出有没有靠多报刷召回”

- `supported_prediction_precision`
- `unmatched_prediction_rate`
- `invalid_anchor_link_rate`
- `contradictory_anchor_link_rate`
- `duplicate_prediction_rate`
- `atomicity_violation_rate`

固定金标分母只看召回，天然可能被“多输出、长输出、多挂锚”钻空子，因此至少要有一组预测侧指标。若金标并非穷尽式，未对齐预测不能直接算错，应先由人工判断它是合法新增事实还是多报。

#### C. 不劣化区：回答“历史完整条有没有退步”

建议默认闸规则：

```text
历史冻结完整条中：
S → 非 S 的数量必须为 0；
不得新增核心/关键单元冲突；
不得新增锚直接冲突。
```

整体成绩可以上升，但只要出现一条冻结完整项回退，成绩卡仍显示上升，**不劣化闸单独判失败**。二者没有冲突，因为回答的不是同一个问题。

上线判断可以写成：

```text
可放行 =
  召回主尺达到约定门槛
  AND 预测质量指标达到约定门槛
  AND 不劣化闸通过
```

不要把三者加权成一个总分。整体均值容易掩盖关键行为退化；评测预处理、输出空间或打分实现的差异也会破坏历史可比性。SeqScore 和事件抽取评测研究都显示，未记录的打分与预处理差异会产生显著分数变化；CheckList 则说明单一总体分数可能漏掉关键行为缺陷。([ACL文摘](https://aclanthology.org/2023.findings-acl.586.pdf))

**对我方双尺的对照判词**

现有“严格／有效召回＋旧固定子集闸”的整体方向可以保留。要改的是：

- 不把不劣化塞进双尺计算。
- 给不劣化闸单独的转移表和失败明细。
- 补预测侧质量指标，防止召回刷分。
- 合同变化后，对旧基线与候选版本使用同一新合同重跑。

------

### 7）最该先改的三处

#### 🔥 改动 1：停止把所有“有效影子”按完整命中计数

**动作：** 拆成 `E 可用部分命中` 和 `P 普通支持型部分命中`。只有核心与全部关键单元正确、锚全部过闸的 E 才进入可用召回；P 只进入加权分。

**依据／来源：** MUC、SemEval 和统一结构化评测都采用可解释的原子或部分匹配，而不是一个不设边界的宽松命中桶。([ACL文摘](https://aclanthology.org/S13-2056.pdf))

**对照判词：** 这是最直接降低“分数好看但信息不完整”风险的改动。

#### 🔥 改动 2：加入全局去重对齐和主张—锚支持关系表

**动作：** 统一处理多句合一、一句多事实、重复预测和多锚联合支持。

**依据／来源：** CEAF 和统一结构化评测框架说明，对齐约束会直接决定最终得分；CaRB 也展示了匹配实现对系统排名的影响。([ACL文摘](https://aclanthology.org/2023.eacl-main.136.pdf))

**对照判词：** 这会让严格和可用两尺真正具备可复现性。

#### 🔥 改动 3：增加预测侧质量区，并把不劣化保持为独立硬闸

**动作：** 报告支持型精确率、多报率、锚无效率、冲突率；不劣化另列通过／失败，不进入平均分。

**依据／来源：** 行为测试和可复现评测研究都说明，总体分数不能代替对关键子集和评分实现的单独检查。([ACL文摘](https://aclanthology.org/2020.acl-main.442/))

**对照判词：** 只改评测合同和报表，不要求同步修改抽取 Prompt。

------

### 8）“分数变好看但产品变差”的风险清单

**动作：** 把下列反作弊项写进评分合同和回归验收。

| 风险                             | 分数为什么会变好看         | 产品为什么会变差                 | 建议防线                               |
| -------------------------------- | -------------------------- | -------------------------------- | -------------------------------------- |
| 语义相似掩盖否定、数字或角色反转 | 关键词和主题高度相似       | 事实方向错误                     | 否定、数字、角色、时间硬规则           |
| 一个宽泛长句命中多条金标         | 一条预测被重复对齐         | 下游拿不到原子事实               | 先拆虚拟子主张，每个子主张限配一条金标 |
| 把完整事实拆成大量碎片           | 每个碎片都获得部分分       | 输出零散、不可直接使用           | 重复单元只计一次；E 档必须关键单元齐全 |
| 大量多报提高召回                 | 固定金标分母只奖励命中     | 下游噪声和人工审核量上升         | 增加预测侧精确率和未对齐率             |
| 给每句挂很多锚                   | 更容易碰到一个能支持的锚   | 用户看到大量无关证据             | 每个挂出锚都必须支持至少一个主张单元   |
| 语义分补偿锚无效                 | 总分仍可能较高             | 事实不可追溯                     | 语义轴与锚轴分开，锚闸不可被加权抵消   |
| LLM judge 偏爱长文本或自身风格   | 文风更像法官偏好的答案     | 信息未必更准确                   | 固定结构、盲化来源、顺序互换、异构法官 |
| 调参时反复看正式测试集           | 阈值越来越贴合现有样本     | 新章节泛化变差                   | 分开校准集、冻结测试集、记录阈值版本   |
| 法官或预处理静默升级             | 同一输出得到更高分         | 能力没有真实变化                 | 冻结版本，升级后全量重跑               |
| 平均分掩盖历史关键项回退         | 新增命中覆盖了旧项损失     | 老用户场景出现回归               | 独立不劣化闸和逐项转移表               |
| 金标等价表达覆盖不全             | 某类系统表达更贴近已有写法 | 合法表达被误判或模型被迫迎合措辞 | 维护评测侧等价表达簇＋人工裁决         |
| 修改单元划分却沿用旧版本号       | 部分分自然提高             | 报表伪装成模型进步               | 单元、权重、关键标记变化均升级合同版本 |

CaRB 和 BenchIE 都表明，匹配器与金标可接受表达覆盖会显著影响评价；LLM judge 研究则确认了顺序、长度和自我偏好等风险。([ACL文摘](https://aclanthology.org/D19-1651/))

**对我方双尺的对照判词**

严格尺防止“残缺也算完整”，预测质量区防止“多报刷召回”，不劣化闸防止“总分提升掩盖旧能力丢失”。三者缺一都会出现好看但不可用的分数。

------

## 3. 推荐评分合同草案

下面是建议稿，不是某篇论文的原样字段。

### 3.1 运行级字段

| 字段                         | 类型        | 规则                                                |
| ---------------------------- | ----------- | --------------------------------------------------- |
| `run_id`                     | string      | 本次评测唯一标识                                    |
| `scoring_contract_version`   | string      | 单元划分、命中档、公式或阈值变化都必须升级          |
| `gold_version`               | string      | 章节级正式金标版本                                  |
| `frozen_subset_version`      | string      | 历史完整条冻结集版本                                |
| `baseline_run_id`            | string      | 本次候选所对比的重跑基线                            |
| `extractor_version`          | object      | 模型、抽取 Prompt、参数版本；只记录，不要求本包修改 |
| `preprocess_version`         | string      | 分句、虚拟子主张拆分、字段标准化规则                |
| `alignment_version`          | string      | 候选召回与全局对齐算法版本                          |
| `semantic_evaluator_version` | object      | 嵌入、NLI、专用对齐模型及阈值                       |
| `llm_judge_version`          | object/null | 法官模型、rubric、温度、顺序策略；未使用则为空      |
| `evaluation_boundary`        | enum        | `PROGRAM_ONLY / LOCAL_MODEL / EXTERNAL_OFFLINE`     |
| `created_at`                 | datetime    | 评测生成时间                                        |

### 3.2 金标项级字段

| 字段                       | 类型／枚举  | 判定规则                                                     | 人工终审                 |
| -------------------------- | ----------- | ------------------------------------------------------------ | ------------------------ |
| `chapter_id`               | string      | 章节 ID                                                      | 否                       |
| `gold_item_id`             | string      | 只在评测侧使用；导出报表可脱敏                               | 否                       |
| `gold_units[]`             | array       | 每个单元含 `unit_id / field_type / critical / weight`；原文不进入生产窗口 | **划分与变更必须**       |
| `core_unit_id`             | string      | 核心事件单元                                                 | **必须**                 |
| `candidate_fact_ids[]`     | array       | 检索召回的候选预测                                           | 否                       |
| `virtual_claim_units[]`    | array       | 从预测句中拆出的独立子主张                                   | 多事实句必须             |
| `alignment_edges[]`        | array       | 子主张与金标单元的候选对应关系                               | 模糊对应必须             |
| `semantic_status_by_unit`  | enum        | `EQUIVALENT / PARTIAL / ABSENT / CONTRADICTED / UNCLEAR`     | 后三类中的高风险项必须   |
| `anchor_relations[]`       | array       | 每个主张单元与每个锚记录 `SUPPORT / IRRELEVANT / CONTRADICT / UNCLEAR` | 冲突、联合证据必须       |
| `anchor_status`            | enum        | `FULL / PARTIAL / NONE / CONTRADICTED / UNCLEAR`             | 非 FULL 且影响过闸时必须 |
| `alignment_status`         | enum        | `CLEAN / AGGREGATED / SPLIT / DUPLICATE / AMBIGUOUS`         | SPLIT、AMBIGUOUS 必须    |
| `raw_supported_credit`     | number 0–1  | 判分单元正确且有锚支持的权重和                               | 否                       |
| `critical_complete`        | boolean     | 核心和全部关键单元是否均正确且有锚                           | 否                       |
| `hit_tier`                 | enum        | `S / E / P / A / X / N`，见下方定义                          | 边界项必须               |
| `strict_hit`               | boolean     | `hit_tier=S`                                                 | 否                       |
| `effective_hit`            | boolean     | `hit_tier∈{S,E}`                                             | 否                       |
| `surface_hit`              | boolean     | 存在相关语义触达，不要求锚过闸                               | 否                       |
| `atomicity_violation`      | boolean     | 原输出是否含多个独立事实                                     | 分拆不明确时必须         |
| `duplicate_credit_blocked` | integer     | 被去重而未重复计分的单元数量                                 | 否                       |
| `prediction_side_status`   | enum        | `SUPPORTED / UNMATCHED / UNSUPPORTED / CONTRADICTORY`        | 未对齐合法性不明时必须   |
| `judge_labels[]`           | array       | 各自动法官原始结构化标签                                     | 否                       |
| `judge_disagreement`       | boolean     | 法官分歧或 A/B、B/A 结果不同                                 | **必须**                 |
| `human_review_required`    | boolean     | 是否进入人工队列                                             | 否                       |
| `review_reason_codes[]`    | array       | 冲突、跨句指代、回归、法官分歧等                             | 否                       |
| `final_label_source`       | enum        | `RULE / MODEL / HUMAN / HUMAN_AUDITED_MODEL`                 | 否                       |
| `baseline_transition`      | string/null | 如 `S→S`、`S→P`、`E→S`                                       | 所有回退必须             |
| `adjudication_note_ref`    | string/null | 只存内部裁决记录引用，不在成绩表暴露金标原文                 | 否                       |

### 3.3 命中档定义

| 档位               | 定义                                                         | 进入哪个读数     |
| ------------------ | ------------------------------------------------------------ | ---------------- |
| `S` 严格命中       | 全部必需单元正确且有锚；所有挂出锚有效；无冲突；无阻断性对齐问题 | 严格、可用、加权 |
| `E` 可用部分命中   | 核心和全部关键单元正确且有锚；所有挂出锚有效；仅缺非关键单元 | 可用、加权       |
| `P` 支持型部分命中 | 至少一个单元正确且有锚，但关键单元不齐，或存在非冲突型锚缺陷 | 只进加权         |
| `A` 表面触达       | 语义碰到相关事实，但没有任何可计分的锚支持单元               | 只进表面诊断     |
| `X` 冲突           | 核心或关键单元被原文／锚直接否定或反转                       | 0 分＋风险计数   |
| `N` 未命中         | 无可对齐语义                                                 | 0 分             |

### 3.4 计算公式

设本章正式金标数为 (N)，第 (i) 条金标包含单元集合 (U_i)，单元权重之和为 1。

v1 建议各单元等权；“关键”只决定 E／P 分档。业务损失已经明确时，再引入不同权重。

```text
unit_credit(u) =
  1，语义等价且至少一个锚 SUPPORT 该单元
  q，合同预先声明该字段允许固定部分分
  0，其他情况
```

其中 `q` 默认不启用，不能用自动法官置信度直接代替。

```text
item_supported_credit(i)
  = Σ weight(u) × unit_credit(u)
```

核心或关键单元发生直接冲突时：

```text
hit_tier = X
final_supported_credit = 0
```

章节级读数：

```text
strict_recall
  = Σ strict_hit(i) / N

usable_recall
  = Σ effective_hit(i) / N

supported_weighted_recall
  = Σ final_supported_credit(i) / N

surface_touch_rate
  = Σ surface_hit(i) / N
```

预测侧读数：

```text
supported_prediction_precision
  = 获得有效对齐且锚支持的虚拟子主张数
    / 全部输出虚拟子主张数

invalid_anchor_link_rate
  = IRRELEVANT 锚关系数
    / 全部挂出锚关系数

contradictory_anchor_link_rate
  = CONTRADICT 锚关系数
    / 全部挂出锚关系数
```

不劣化默认规则：

```text
regression_count
  = 冻结集中 baseline_tier=S 且 candidate_tier≠S 的条数

non_regression_pass
  = regression_count=0
    AND 新增核心/关键冲突数=0
    AND 新增锚直接冲突数=0
```

### 3.5 🔒 必须人工终审的情况

- 金标判分单元的初次拆分、关键标记和权重变更。
- 一条预测准备拆给多条金标计分。
- 多条预测需要跨句指代或联合推理才能拼成一条金标。
- 核心／关键单元出现 `CONTRADICTED` 或 `UNCLEAR`。
- 自动法官分歧，或交换候选顺序后结论变化。
- 冻结子集出现任何 `S→非S`。
- 未对齐预测可能是合法新增事实，且要进入预测精确率统计。
- 对自动判为 S／E 的样本做持续分层抽检，不能只抽失败样本。

------

## 4. 示例报表表头

以下只给列名，不填任何假成绩。

### 4.1 章节／整体成绩表

| run_id | scoring_contract_version | gold_version | chapter_id | gold_denominator | strict_hits | strict_recall | usable_partial_hits | usable_recall | supported_weighted_recall | surface_touch_rate_诊断 | supported_prediction_precision | unmatched_prediction_rate | invalid_anchor_link_rate | contradictory_anchor_link_rate | duplicate_credit_blocked | atomicity_violation_rate | human_review_rate |
| ------ | ------------------------ | ------------ | ---------- | ---------------- | ----------- | ------------- | ------------------- | ------------- | ------------------------- | ----------------------- | ------------------------------ | ------------------------- | ------------------------ | ------------------------------ | ------------------------ | ------------------------ | ----------------- |
|        |                          |              |            |                  |             |               |                     |               |                           |                         |                                |                           |                          |                                |                          |                          |                   |

### 4.2 不劣化闸表

| run_id | frozen_subset_version | frozen_subset_size | baseline_strict_hits | candidate_strict_hits | S_to_S | S_to_E | S_to_P | S_to_A_X_N | new_invalid_anchor_items | new_contradiction_items | critical_regressions | gate_rule_version | gate_result |
| ------ | --------------------- | ------------------ | -------------------- | --------------------- | ------ | ------ | ------ | ---------- | ------------------------ | ----------------------- | -------------------- | ----------------- | ----------- |
|        |                       |                    |                      |                       |        |        |        |            |                          |                         |                      |                   |             |

### 4.3 条目级审计表

| chapter_id | gold_item_id | baseline_tier | candidate_tier | supported_credit | critical_complete | anchor_status | alignment_status | aligned_fact_ids | atomicity_violation | judge_disagreement | human_final_label | regression_flag | review_reason_codes |
| ---------- | ------------ | ------------- | -------------- | ---------------- | ----------------- | ------------- | ---------------- | ---------------- | ------------------- | ------------------ | ----------------- | --------------- | ------------------- |
|            |              |               |                |                  |                   |               |                  |                  |                     |                    |                   |                 |                     |

### 4.4 档位转移表

| 旧档位＼新档位 | S    | E    | P    | A    | X    | N    |
| -------------- | ---- | ---- | ---- | ---- | ---- | ---- |
|                |      |      |      |      |      |      |

------

## 5. 开放问题

1. **哪些单元算“关键”**：缺失后事实仍可用于产品，还是会改变临床／业务含义？这决定 E 与 P 的边界。
2. **正式金标是否穷尽结构层事实**：若不穷尽，未对齐预测不能直接计为多报，需要设置“合法新增事实”人工档。
3. **多挂一个无关锚的处理强度**：建议严格和可用两尺都不过闸，但保留已支持单元的加权分；是否符合现行业务风险判断？
4. **冻结闸保护范围**：只保护历史 S 条目，还是还要保护原有锚数量、锚位置和输出原子性？
5. **“模型窗禁入”适用边界**：若金标和病例证据也不能进入隔离的外部评测模型，则 LLM judge 只能换成本地模型或退出终判流程。

------

## 6. 参考来源列表

### 结构化抽取、严格匹配与部分得分

1. [A Unified View of Evaluation Metrics for Structured Prediction，EMNLP 2023](https://aclanthology.org/2023.emnlp-main.795/)
2. [MUC Scoring Software User’s Manual，1998](https://aclanthology.org/M98-1030/)
3. [SemEval-2013 Task 9: DDIExtraction](https://aclanthology.org/S13-2056/)
4. [CaRB: A Crowdsourced Benchmark for Open IE，EMNLP 2019](https://aclanthology.org/D19-1651/)
5. [BenchIE: Multi-Faceted Fact-Based Open IE Evaluation，ACL 2022](https://aclanthology.org/2022.acl-long.307/)
6. [Iterative Document-level Information Extraction via Imitation Learning；含 CEAF-RME，EACL 2023](https://aclanthology.org/2023.eacl-main.136/)
7. [The Devil is in the Details: Pitfalls of Event Extraction Evaluation，Findings ACL 2023](https://aclanthology.org/2023.findings-acl.586/)
8. [SeqScore: Reproducible Named Entity Recognition Evaluation，Eval4NLP 2021](https://aclanthology.org/2021.eval4nlp-1.5/)
9. [Beyond Accuracy: Behavioral Testing with CheckList，ACL 2020](https://aclanthology.org/2020.acl-main.442/)

### 中文语义等价、长文本与一致性判断

1. [OCNLI: Original Chinese Natural Language Inference，Findings EMNLP 2020](https://aclanthology.org/2020.findings-emnlp.314/)
2. [C-Pack / C-MTEB: General Chinese Embeddings](https://arxiv.org/abs/2309.07597)
3. [M3-Embedding / BGE-M3](https://arxiv.org/abs/2402.03216)
4. [SummaC: NLI-based Inconsistency Detection，TACL 2022](https://aclanthology.org/2022.tacl-1.10/)
5. [AlignScore: A Unified Alignment Function，ACL 2023](https://aclanthology.org/2023.acl-long.634/)
6. [HANS: Diagnosing Syntactic Heuristics in NLI，ACL 2019](https://aclanthology.org/P19-1334/)
7. [EQUATE: Quantitative Reasoning in NLI，CoNLL 2019](https://aclanthology.org/K19-1033/)

### LLM-as-judge 偏差与校准

1. [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)
2. [Large Language Models are not Fair Evaluators / FairEval](https://arxiv.org/abs/2305.17926)
3. [Length-Controlled AlpacaEval](https://arxiv.org/abs/2404.04475)
4. [LLM Evaluators Recognize and Favor Their Own Generations](https://arxiv.org/abs/2404.13076)
5. [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634)
6. [Replacing Judges with Juries / PoLL](https://arxiv.org/abs/2404.18796)
7. [JUDGE-BENCH: LLM Judges across 20 NLP Evaluation Tasks](https://arxiv.org/abs/2406.18403)

来源：ChatGPT