# T5 R04｜SEMANTIC_CORE / FACT_ONLY 辅助训练对照实验施工合同

- 文档版本：`R01`
- 日期：`2026-08-07`
- 状态：`APPROVED_FOR_LOCAL_SMALL_PROBE`
- 授权范围：只允许执行本文列出的本地小探针、重评分、渲染和有限续训
- 禁止范围：不启动 500 本抽数，不扩到 1000～1500 窗口，不改冻结教材，不调用外部 API，不写 Notion，不提交 Git，不宣布 A 或 C2 胜出
- 目标：验证少量 `SEMANTIC_CORE / FACT_ONLY` 辅助任务，能否提高模型“判断该抽哪些事实、怎样写成准确事实句”的能力，同时不破坏正式 JSON、status、speaker 和证据输出

---

## 0. 大白话总原则

本实验要测的是：

> 在正式 A 或 C2_FULL 教材中，拿出少量窗口，只让模型练“抽出事实句”，是否能加强抽取内核，而不把正式输出格式教乱。

不允许直接混入自由文本答案。阶段 1 已经说明，Qwen3-4B 会受到局部字段顺序和输出模板影响。辅助任务必须有明确模式标记，并使用一个与正式任务不同、但稳定且极简的容器。

本轮只测两档：

```text
0% SEMANTIC_CORE
5% SEMANTIC_CORE
```

`10%` 只在 5% 通过闸门后运行。

A 与 C2 必须使用：

- 同一批小说窗口；
- 同一批事实语义；
- 同一批被切换成 SEMANTIC_CORE 的 `sample_id`；
- 同一训练顺序、配方、seed 和更新步数；
- 同一作者隔离 dev；
- 同一评分器。

A/C2 的正式比较仍然要求两臂同时存在。旧 A/C checkpoint 可以节省筛查时间，但不能把不同训练历史的 checkpoint 直接拿来判 A/C2 胜负。

---

# 1. 三种任务身份

## 1.1 `FULL_A`

正式 A 任务。模型输出逐字 evidence。

固定对象顺序：

```json
{
  "facts": [
    {
      "fact": "……",
      "status": "已发生",
      "evidence": ["逐字连续原文"],
      "speaker": null
    }
  ]
}
```

## 1.2 `FULL_C2_UNIT`

正式 C2 任务。模型只输出局部 `Bxx/Txx` 单元，不输出字符坐标和锚字。

```json
{
  "facts": [
    {
      "fact": "……",
      "status": "已发生",
      "evidence_ids": ["B01", "T01"],
      "speaker": null
    }
  ]
}
```

固定约束：

- `B` 是可作为证据开头的桥接单元；
- `T` 是本段负责单元；
- `evidence_ids` 最后一个 ID 必须为 `T`；
- ID 按正文顺序排列并去重；
- 不输出全局编号、字符偏移或锚字；
- `sample_id + local_id` 由程序映射回全局原文。

## 1.3 `SEMANTIC_CORE`

辅助任务，只练“抽什么、怎样写成事实句”。

用户题面必须明确标记：

```text
【任务模式】SEMANTIC_CORE
```

输出固定为：

```json
{
  "fact_sentences": [
    "陈川计划明早出发。",
    "赵明误以为钥匙在抽屉里。"
  ]
}
```

零事实时：

```json
{
  "fact_sentences": []
}
```

禁止输出：

- `status`；
- `speaker`；
- `evidence`；
- `evidence_ids`；
- 编号；
- 分析过程；
- Markdown；
- JSON 之外的解释。

### 为什么不用 `{"facts":["……"]}`

正式任务的 `facts` 是对象数组。辅助任务若把同一个 `facts` 改成字符串数组，容易让 4B 模型混淆正式 schema。

因此辅助任务使用独立顶层键：

```text
fact_sentences
```

这能明确告诉模型：这是另一种任务模式，不是正式对象缺字段。

---

# 2. `fact_sentences` 的语义合同

不能直接把 FULL 里的 `fact` 字段盲目抄过来。删除 `status` 和 `speaker` 后，事实句仍必须保留原来的语义限定。

## 2.1 必须保留的内容

每条 `fact_sentence` 必须保留：

- 主体；
- 核心动作或状态；
- 否定；
- 时间关系；
- 计划、承诺、条件、推测、误信等模态；
- 信息来源或说话人归属，若删除后会把“某人声称”误写成客观事实；
- 原子性，一句只表达一个核心断言。

示例：

| FULL 语义 | 合格的 `fact_sentence` | 不合格写法 |
|---|---|---|
| `status=计划` | `陈川计划明早出发。` | `陈川明早出发。` |
| `status=误信` | `赵明误以为钥匙在抽屉里。` | `钥匙在抽屉里。` |
| 某人声称 | `陈川称李四已经离开。` | `李四已经离开。` |
| 否定 | `陈川没有答应同行。` | `陈川答应同行。` |
| 条件 | `如果雨停，陈川才会出发。` | `陈川会出发。` |

## 2.2 生成方式

`fact_sentences` 可以从 A 的人工语义真源派生，但必须经过独立复核。

每条至少保存：

```text
fact_sentence_id
source_fact_id
source_sample_id
semantic_sentence
review_status
reviewer_id
```

不得让大模型自动改写后直接作为金标。

---

# 3. A 与 C2 的 SEMANTIC_CORE 输入必须怎样对应

A_CORE 与 C2_CORE 的输出完全相同。输入内容也必须完全相同，唯一差别是 C2 带局部编号。

## 3.1 A_CORE

```text
【任务模式】SEMANTIC_CORE
【窗口位置】MIDDLE

【只读上文】
……

【证据桥接区】
他此前曾答应同行。

【本段负责区】
陈川终于点了点头。
“明早出发。”他说。

【只读下文】
……
```

## 3.2 C2_CORE

```text
【任务模式】SEMANTIC_CORE
【窗口位置】MIDDLE

【只读上文】
……

【证据桥接区】
[B01] 他此前曾答应同行。

【本段负责区】
[T01] 陈川终于点了点头。
[T02] “明早出发。”他说。

【只读下文】
……
```

C2_CORE 的 instruction 必须明确：

```text
编号只是正文位置标记。本任务不要输出任何编号。
```

这样，A_CORE 与 C2_CORE 的差异只剩：

```text
正文前是否存在 B/T 局部编号
```

这能单独观察编号是否干扰模型阅读和事实形成。

---

# 4. 数据构造锁

## 4.1 以窗口计比例

`5%` 和 `10%` 全部按训练窗口计算，不按 fact 数，也不按 token 数计算。

同时必须报告：

- SEMANTIC_CORE 窗口占比；
- 对应事实句占比；
- assistant supervised token 占比。

## 4.2 替换，不追加

假设 continuation batch 有 200 个窗口：

```text
0%：200 个窗口全部使用 FULL
5%：同样 200 个窗口，其中 10 个切换为 SEMANTIC_CORE
10%：同样 200 个窗口，其中 20 个切换为 SEMANTIC_CORE
```

不能写成：

```text
200 个 FULL
＋额外增加 10 个 SEMANTIC_CORE
```

否则 5% 组训练步数更多，因果关系失效。

## 4.3 同一 source pool

0%、5%、10% 使用完全相同的 source window 清单。

区别只能是：

```text
指定 sample_id 使用 FULL renderer
或
指定 sample_id 使用 SEMANTIC_CORE renderer
```

同一个 run 内，一个窗口只能出现一次。

## 4.4 5% 必须是 10% 的子集

```text
SEMANTIC_CORE_05 ⊂ SEMANTIC_CORE_10
```

这样才能观察从 0% → 5% → 10% 的剂量变化。

## 4.5 数量建议

优先使用已有、已清权、已作者隔离的窗口，不为本探针开新一轮大规模抽数。

推荐 continuation batch：

```text
默认：200 个窗口
可接受：160～300 个窗口
低于 160：不建议做比例结论
```

对应数量：

| 总窗口 | 5% | 10% |
|---:|---:|---:|
| 160 | 8 | 16 |
| 200 | 10 | 20 |
| 240 | 12 | 24 |
| 300 | 15 | 30 |

## 4.6 SEMANTIC_CORE 子集结构

不能只选简单的“某人做了某事”。

5% 子集按下列五类尽量均衡：

| 类型 | 目标作用 |
|---|---|
| 零事实／近零事实 | 教模型不要过抽 |
| 原子性 | 教模型拆开两个核心断言，不把动作和结果乱合并 |
| 否定／条件／推测 | 教模型保留限定，不写成客观已发生 |
| 计划／承诺／误信／来源归属 | 教模型在自然事实句里保留模态和来源 |
| 对话指代／噪声文本／特殊形态 | 教模型穿过拟声词、聊天、系统面板等噪声抓核心事实 |

约束：

- 同一本书原则上只进 1 个 SEMANTIC_CORE 窗口；
- 同一作者尽量只进 1 个；
- 不让某一题材或状态占满子集；
- 零事实窗口建议占 SEMANTIC_CORE 子集的 15%～25%。

---

# 5. checkpoint 分级：哪些可以省时间，哪些不能

## 5.1 `READ_ONLY_BASELINE`

只读取旧 raw outputs 和指标，不继续训练。

当前历史资产：

| 资产 | SHA-256 | 身份 |
|---|---|---|
| A stage1 | `1e2f5e736f9d913819b835b21533626915a0e569f23242a7a15b8c1655fb3cdf` | 旧 A 正向阶段 checkpoint |
| A final | `e1217ec79657cd12cce2d273154db2da1c118a034dceca7a23975cddb27d9b74` | 旧 A 特殊阶段后 checkpoint |
| C stage1 | `206886963a2de9553a6c7a8824db2bb12cbb0509834d695d6a8a54807fc28f3e` | 旧坐标 C 正向阶段 checkpoint |
| C final | `35595e49156cbe8c39ca5f90729f06deea16ca6bd12456cca7edabed43cd7175` | 旧坐标 C 最终 checkpoint |

这些结果可以用新评分器重算，作为历史锚点。

它们不能直接回答：

```text
SEMANTIC_CORE 是否帮助新 C2_UNIT
```

## 5.2 `ELIGIBLE_PARENT`

可以作为正式续训父 checkpoint，必须同时满足：

- 输出合同与当前 arm 相同；
- 使用同一 tokenizer 和 chat template；
- parent 的训练数据、字段顺序和 renderer 有完整锁；
- parent 未经过另一个不兼容证据格式训练；
- 两个分支从完全相同的 checkpoint SHA 起步；
- optimizer/scheduler 是否恢复，两分支做法完全一致。

理想 parent 是：

```text
由同一 Qwen3-4B 基座
＋同一 canonical pilot
＋同一 recipe
训练出来的 A_FULL_0 和 C2_FULL_0 checkpoint
```

## 5.3 `ENGINEERING_ONLY_PARENT`

可以做省时筛查，但结果不能用于 A/C2 胜负。

### 旧 A stage1

可以做 A 内部的续训探针：

```text
旧 A stage1 → A_CONT_0
旧 A stage1 → A_CONT_5
```

它只能回答：

> 在旧 A stage1 这条训练历史上，把 5% 新增窗口改成 SEMANTIC_CORE，有没有局部收益。

不能与新 C2 直接比较。

### 旧 A final

只能作为“已发生格式污染的 checkpoint 是否容易被修回”的附加探针。

它回答的是 repairability，不是 SEMANTIC_CORE 主效果。除非本地成本极低，否则不优先跑。

### 旧 C stage1 / final

❌ 不允许作为正式 C2 parent。

旧 C 学的是：

```text
字符坐标＋锚字
```

新 C2 学的是：

```text
局部 B/T 单元 ID
```

从旧 C 续训到 C2，同时改变证据合同和 SEMANTIC_CORE 比例，无法解释结果。

如以后专门研究“旧 C 能否迁移到 C2”，必须另开实验，不得混入本轮。

---

# 6. resume 与 warm start 必须区分

## 6.1 真正 resume

同时恢复：

- adapter 权重；
- optimizer state；
- scheduler state；
- global step；
- RNG state；
- dataloader continuation 状态。

## 6.2 warm start

只加载 adapter 权重，重新初始化 optimizer 和 scheduler。

两种都可以，但同一对照中的两个分支必须完全一致。

禁止：

```text
0% 分支恢复 optimizer
5% 分支重置 optimizer
```

每个 run lock 必须记录：

```text
parent_checkpoint_sha
parent_adapter_sha
optimizer_state_sha 或 null
scheduler_state_sha 或 null
resume_mode
global_step_start
rng_state_sha
```

---

# 7. 对照组总表

## 7.1 零训练输入编号诊断

这组最便宜，先跑。

| Group ID | 模型 | 输入 | 输出合同 | 训练 |
|---|---|---|---|---|
| `Z00_BASE_A_CORE` | 原始 Qwen3-4B | A_CORE | SEMANTIC_CORE | 无 |
| `Z01_BASE_C2_CORE` | 同一原始 Qwen3-4B | C2_CORE | SEMANTIC_CORE | 无 |

只回答：

> 在没有 LoRA 的情况下，B/T 编号是否已经明显干扰事实抽取。

这组必须用同一批 `DEV_CORE`，同一解码参数。

## 7.2 历史只读对照

| Group ID | 数据来源 | 动作 |
|---|---|---|
| `H00_A_STAGE1_OLD41` | 旧 A stage1 raw outputs | 用 EVALUATOR_R02 重算 |
| `H01_A_FINAL_OLD41` | 旧 A final raw outputs | 用 EVALUATOR_R02 重算 |
| `H02_C_STAGE1_OLD41` | 旧 C stage1 raw outputs | 用 EVALUATOR_R02 重算 |
| `H03_C_FINAL_OLD41` | 旧 C final raw outputs | 用 EVALUATOR_R02 重算 |

这组只作为历史锚点，不参与新 A/C2 胜负。

## 7.3 干净的 0% A/C2 parent

若本地已有完全符合当前 C2_UNIT 合同的成对 checkpoint，先验收后复用。

否则创建：

| Group ID | 起点 | 训练集 | SEMANTIC_CORE |
|---|---|---|---:|
| `P00_A_FULL0` | 同一 Qwen3-4B base | canonical pilot 的 A_FULL | 0% |
| `P01_C2_FULL0` | 同一 Qwen3-4B base | 同一 canonical pilot 的 C2_FULL | 0% |

两者必须：

- 使用同一 canonical sample；
- 事实、status、speaker 完全相同；
- 训练顺序相同；
- recipe 相同；
- 唯一差异是 A evidence 与 C2 evidence_ids。

这两个 checkpoint 是后续最理想的续训 parent。

## 7.4 5% 主筛查组

从各自的 0% parent 分叉。

### A

| Group ID | Parent | 新增 continuation batch |
|---|---|---|
| `S00_A_CONT0` | `P00_A_FULL0` | 100% A_FULL |
| `S01_A_CONT5` | 同一个 `P00_A_FULL0` | 95% A_FULL＋5% A_CORE |

### C2

| Group ID | Parent | 新增 continuation batch |
|---|---|---|
| `S02_C2_CONT0` | `P01_C2_FULL0` | 100% C2_FULL |
| `S03_C2_CONT5` | 同一个 `P01_C2_FULL0` | 95% C2_FULL＋5% C2_CORE |

四组必须保持：

- continuation source windows 相同；
- 5% 的 sample_id 相同；
- 总窗口数相同；
- optimizer updates 相同；
- batch、gradient accumulation、LR、warmup、rank、alpha、dropout 相同；
- max sequence length 相同；
- seed 和样本顺序相同；
- 解码相同。

### 能做的比较

```text
S01 - S00
= SEMANTIC_CORE 对 A 的增量效果

S03 - S02
= SEMANTIC_CORE 对 C2 的增量效果
```

只有当 `P00/P01` 本身来自干净成对实验时，才允许进一步比较：

```text
S02 - S00
= 0% 配方下的 A/C2 格式差异

S03 - S01
= 5% 配方下的 A/C2 格式差异
```

## 7.5 10% 条件组

只有对应 5% 组通过闸门后才运行。

| Group ID | Parent | continuation batch |
|---|---|---|
| `S04_A_CONT10` | 原始 `P00_A_FULL0` | 90% A_FULL＋10% A_CORE |
| `S05_C2_CONT10` | 原始 `P01_C2_FULL0` | 90% C2_FULL＋10% C2_CORE |

🔥 10% 必须重新从原始 parent 分叉。

禁止：

```text
A_CONT5 → 再追加 5% → 当作 A_CONT10
```

否则 10% 组比 5% 组多训练了一段，无法比较。

## 7.6 旧 A checkpoint 的省时附加组

仅当新 A parent 暂时不存在、而本地希望先看有没有信号时运行：

| Group ID | Parent | continuation |
|---|---|---|
| `X00_A_S1_CONT0` | 旧 A stage1 | 100% A_FULL |
| `X01_A_S1_CONT5` | 同一个旧 A stage1 | 95% A_FULL＋5% A_CORE |

身份必须写：

```text
ENGINEERING_SCREEN_ONLY
```

不能拿它与新 C2 结果直接判胜负。

旧 A final 的同类 pair 默认不跑。只有 CZ 另行要求研究“污染 checkpoint 能否修回”时才运行。

## 7.7 正式采用前的干净确认组

只有 5% 或 10% 在筛查中显示净收益，才需要跑。

假设胜出比例是 `R`：

| Group ID | 起点 | 配方 |
|---|---|---|
| `C00_A_CLEAN0` | 原始 Qwen3-4B base | A，0% |
| `C01_A_CLEANR` | 同一 base | A，R% |
| `C02_C2_CLEAN0` | 同一 base | C2，0% |
| `C03_C2_CLEANR` | 同一 base | C2，R% |

这四组从第一步就按锁定比例分层打散，才可用于主线 recipe 决定。

若结果落在灰区，只允许增加第二个 seed；不靠继续扩数据绕过不确定性。

---

# 8. 训练配方锁

同一对照中，以下项目不能变化：

```text
base model
tokenizer
chat template
system prompt
字段顺序
EOS token
loss mask
LoRA target modules
rank
alpha
dropout
learning rate
warmup
batch size
gradient accumulation
max sequence length
max steps
weight decay
seed
decode strategy
max_new_tokens
```

辅助任务输出更短，因此 5% 组的 supervised assistant token 会略少，这是 treatment 自带结果。

必须报告：

```text
总训练窗口
总 input tokens
总 assistant supervised tokens
optimizer updates
tokens per update
```

如果 5% 组与 0% 组的 supervised assistant token 相差超过 8%，必须暂停解释，先检查是不是 renderer 或采样比例错误。

---

# 9. dev 与考试隔离

## 9.1 新 dev

至少建立：

```text
DEV_FULL
DEV_CORE
```

两者使用同一批 source windows，只是输出合同不同。

建议：

```text
40～60 个窗口
至少来自 30 个作者
零事实窗口 10%～20%
```

作者不得出现在：

- 当前 continuation train；
- 新 A/C2 parent train；
- 旧 350 条训练来源；
- 当前 41 题；
- 旧 48 题。

## 9.2 旧 41 和旧 48

仍是历史回归卷：

- 不用于选择 5% 子集；
- 不用于调 prompt；
- 不用于调 atomizer；
- 不用于选择 5% 还是 10%；
- 可以在实验完成后做一次只读回归。

---

# 10. 评分合同

必须使用修正后的 `EVALUATOR_R02` 或等价实现。

## 10.1 SEMANTIC_CORE 指标

主指标：

- `core_fact_semantic_precision`
- `core_fact_semantic_recall`
- `core_fact_semantic_f1`
- `zero_fact_false_positive_rate`
- `fact_count_mae`
- `atomicity_error_count`
- `unsupported_fact_count`

匹配方式：

1. case 内生成候选配对；
2. 机械归一只用于候选；
3. 人工盲审 `same / partial / different`；
4. 不知道输出来自 A、C2、0%、5% 或 10%；
5. 不使用大模型改写后自评。

## 10.2 FULL 指标

格式层：

- JSON valid；
- schema valid；
- 缺字段；
- 非法额外字段；
- 截断；
- 严重复。

语义层：

- fact semantic precision / recall / F1；
- normalized exact fact F1；
- status accuracy，只在 fact 匹配后计算；
- speaker accuracy，只在 fact 匹配后计算。

证据层：

A：

- evidence 是否逐字存在；
- exact span 命中；
- 最小证据覆盖；
- 额外抄入字符。

C2：

- ID schema 合法；
- ID 是否存在于本题；
- 最后一个 ID 是否为 T；
- local→global 映射成功率；
- A exact span 覆盖率；
- 额外带入字符；
- 使用 ID 数量。

效率层：

- output token p50 / p90；
- 每条正确 fact 的平均输出 token。

---

# 11. 事前判定阈值

## 11.1 5% 通过条件

对某一个格式，`CONT5` 相对 `CONT0` 同时满足：

### 语义收益

至少满足一项：

- `core_fact_semantic_f1` 提高 ≥3 个百分点；
- 固定 DEV_CORE 上净增加 ≥5 条 `same` 事实；
- 配对 bootstrap 中 `P(ΔF1 > 0) ≥ 0.90`。

### FULL 不受伤

- FULL fact semantic F1 不下降超过 1 个百分点；
- JSON/schema 合法率不下降超过 2 个百分点，且新增无效案例不超过 1 案；
- 严重复或截断合计不得增加超过 1 案；
- status、speaker、evidence 条件准确率各自不下降超过 3 个百分点；
- 零事实窗口的误抽案例不得增加超过 1 案。

只提高 CORE、却伤害 FULL 的，判为：

```text
CORE_GAIN_WITH_PRODUCTION_REGRESSION
```

不得进入主配方。

## 11.2 10% 启动条件

某格式的 5% 必须已经通过。

A 通过但 C2 不通过时，只允许给 A 跑 10%；不能为了“对称”强行给 C2 跑。

## 11.3 10% 胜过 5%

10% 相对 5%：

- CORE fact semantic F1 再提高 ≥2 个百分点，或净增加 ≥3 条 `same`；
- 所有 FULL guardrail 继续通过。

没有额外收益时保留 5%。

## 11.4 直接淘汰条件

出现任一项即停止该比例：

- 正式 JSON 漏字段明显增加；
- 模型在 FULL 模式输出 `fact_sentences`；
- 模型在 CORE 模式输出 `facts` 对象；
- 严重复或截断明显增加；
- zero-fact 过抽增加；
- status、speaker 或证据定位明显下降；
- A/C2 两臂使用了不同 source pool、不同 sample order 或不同训练步数。

---

# 12. 结果该怎样解释

## 可以下的结论

### `S01 > S00`

可以说：

> 在该 A parent 和该 continuation batch 上，5% SEMANTIC_CORE 显示正向增量。

### `S03 > S02`

可以说：

> 在该 C2 parent 和该 continuation batch 上，5% SEMANTIC_CORE 显示正向增量。

### `Z00 ≈ Z01`

可以说：

> 在未训练的 FACT_ONLY 任务里，局部 B/T 编号没有造成明显语义损失。

### `Z01 << Z00`

可以说：

> C2 输入编号或分段形式可能干扰基础阅读，需要先检查输入设计。

## 不能下的结论

- 旧 A stage1 的 5% 有效，不等于新 A 主线一定有效；
- 旧 A 的结果不能与新 C2 直接判胜负；
- 旧 C checkpoint 续训后变好，不等于 C2 本身更好；
- 5% continuation 有效，不等于“整个训练生命周期 5%”已经被验证；
- CORE 得分高，不等于 FULL 生产任务合格；
- 输出更短，不等于事实更准；
- 单 seed 小样本胜出，不等于可以直接扩到 1500 窗口。

---

# 13. 执行顺序

## 阶段 A｜零训练与资产验收

1. 建 `PARENT_CHECKPOINT_AUDIT.json`；
2. 将旧 checkpoint 分类为 `READ_ONLY_BASELINE / ELIGIBLE_PARENT / ENGINEERING_ONLY_PARENT`；
3. 跑 `Z00/Z01`；
4. 用 EVALUATOR_R02 重算 `H00～H03`；
5. 回 `STAGE_A_RECEIPT.md`。

此阶段不训练。

## 阶段 B｜确认或建立干净 0% parent

1. 检查本地是否已有符合当前 FULL_A / FULL_C2_UNIT 合同的成对 checkpoint；
2. 有则校验 SHA、dataset、recipe 后复用；
3. 没有则只运行 `P00/P01`；
4. 不运行 5% 前，先冻结 parent SHA。

## 阶段 C｜5% 主筛查

运行：

```text
S00
S01
S02
S03
```

完成后必须先评分和回执，不自动进入 10%。

## 阶段 D｜条件性 10%

只有对应格式通过 5% 闸门时才运行：

```text
S04 和／或 S05
```

全部从原始 parent 分叉。

## 阶段 E｜干净确认

只有筛查存在净收益时，才运行 `C00～C03`。

通过后仍只形成：

```text
CANDIDATE_RECIPE
```

不自动扩到 500 本。

---

# 14. Codex 必须生成的文件

建议实验根目录：

```text
finetuning/experiments/T5_R04_SEMANTIC_CORE_MIX_PROBE_20260807_R01/
```

至少包含：

```text
00_READ_ME_FIRST.md
PARENT_CHECKPOINT_AUDIT.json
CANONICAL_SAMPLE_MANIFEST.jsonl
SEMANTIC_CORE_GOLD.jsonl
SEMANTIC_CORE_SUBSET_05.json
SEMANTIC_CORE_SUBSET_10.json
RENDER_LOCK.json
GROUP_MATRIX.json
DECISION_THRESHOLDS.md
runs/<group_id>/RUN_LOCK.json
runs/<group_id>/RAW_OUTPUTS.jsonl
runs/<group_id>/METRICS.json
PAIRWISE_COMPARISON.md
DECISION_CANDIDATE.md
RUN_STATE.json
RETURN_MANIFEST.json
SELF_CHECK.md
```

每个 run 的 `RUN_LOCK.json` 至少记录：

```text
group_id
parent checkpoint SHA
base model SHA
adapter SHA
optimizer/scheduler恢复方式
dataset manifest SHA
renderer SHA
subset SHA
sample order SHA
recipe SHA
decode SHA
实际训练窗口数
实际 supervised tokens
实际 optimizer updates
```

---

# 15. 停工条件

遇到以下任一情况，Codex 必须停在当前阶段并回报，不得自行补实验：

- parent checkpoint 身份不明；
- A/C2 parent 不是同一 base 或同一 canonical pilot；
- 旧 C 被误当成 C2 parent；
- 5% 组是额外加数据而不是替换；
- 5% A 与 5% C2 使用了不同 sample_id；
- SEMANTIC_CORE 金标丢失否定、计划、误信或来源限定；
- dev 作者泄漏；
- EVALUATOR_R02 尚未完成；
- 同一对照的 optimizer resume 方式不同；
- 结果出来后才修改阈值；
- 需要新开大规模抽数才能凑样本；
- 计划同时修改 LoRA 参数、解码或 max_new_tokens。

---

# 16. 本轮唯一允许的最终判断

Codex 最终只能输出以下状态之一：

```text
SEMANTIC_CORE_5_SUPPORTED_FOR_A
SEMANTIC_CORE_5_SUPPORTED_FOR_C2
SEMANTIC_CORE_5_SUPPORTED_FOR_BOTH
SEMANTIC_CORE_5_NO_MATERIAL_GAIN
SEMANTIC_CORE_5_CAUSES_FORMAT_REGRESSION
SEMANTIC_CORE_RESULT_MIXED
INSUFFICIENT_CLEAN_COMPARISON
```

10% 运行后可追加：

```text
SEMANTIC_CORE_10_OUTPERFORMS_5
SEMANTIC_CORE_10_NO_ADDITIONAL_GAIN
SEMANTIC_CORE_10_CAUSES_REGRESSION
```

不得输出：

```text
A_WINS
C2_WINS
READY_FOR_1500_WINDOWS
READY_FOR_PRODUCTION
```

除非另有独立、正式授权的 A/C2 主线胜负实验。

---

# 17. 给 Codex 的唯一下一动作

收到本文件后，先执行阶段 A：

```text
建立 checkpoint 身份审计
→ 列出现有可复用 parent
→ 列出缺失的干净 A/C2 0% parent
→ 回传 STAGE_A_RECEIPT.md
```

若干净 A/C2 parent 已存在，可以继续进入阶段 C；若不存在，只补建 `P00/P01`，不得直接拿旧坐标 C checkpoint 代替 C2。

本文件授权的是小规模本地探针，不授权新增大规模训练集。
