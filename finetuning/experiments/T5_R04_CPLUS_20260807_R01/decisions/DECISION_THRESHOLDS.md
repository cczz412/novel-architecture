# T5 R04 C+｜冻结判定阈值与阶段执行闸门

- **状态**：`CZ_APPROVED_PENDING_REPOSITORY_REGISTRATION`
- **配套决定**：`01_T5_R04_CPLUS_P0_DECISION_AND_ROUTE_AUTHORIZATION.md`
- **适用日期**：2026-08-07
- **原则**：阈值必须在看新结果前冻结；不得跑完再换主指标

---

# 一、共同计分纪律

## 1. 原始一次生成永远保留

每案必须同时保存：

- 原始 prompt；
- 原始模型文本；
- token 数；
- finish reason；
- 是否触顶；
- 首次复读位置；
- 解析结果；
- 恢复解析结果；
- evaluator 版本和 SHA；
- adapter、基座、解码和运行配置 SHA。

修复 JSON、重试或受限解码可以另报，但不能覆盖第一次原始输出。

## 2. 分层指标

至少报告：

1. `raw_completion_rate`：是否产生输出；
2. `raw_json_valid_rate`：原始文本是否可直接解析；
3. `schema_valid_rate`：字段、类型、枚举是否完整；
4. `truncation_rate`：是否触及输出上限；
5. `severe_repeat_case_rate`：同一完整对象或核心 fact 连续出现至少 3 次；
6. `fact_exact_f1`：原始严格文本；
7. `fact_normalized_f1`：只做固定机械归一化；
8. `fact_precision / fact_recall`；
9. `status_accuracy_on_matched_fact`；
10. `speaker_accuracy_on_matched_fact`；
11. A 的逐字 evidence 合法率；
12. C-2 的 ID 结构合法率；
13. 映射后的证据字符覆盖率、额外带入字符数；
14. 输出 token 的 p50／p90／最大值；
15. 按来源、文本形态、status、speaker、证据跨度和窗口位置分层结果。

## 3. 固定机械归一化

`fact_normalized_f1` 只能做这些变换：

- Unicode NFKC；
- 去首尾空白；
- 合并连续空白；
- 统一全角／半角常见标点；
- 去掉句末单个 `。！？!?`；
- speaker 的 `null / 缺省` 按同一合同处理。

不得删除否定词、主体名、数字、时间、状态词或因果词；不得用大模型自动改写事实后再评分。

严格文本 F1 继续保留，但名称必须写成 `STRICT_TEXT_TRIPLE_F1`，不能继续简称“语义 F1”。

---

# 二、阶段 1：三个根因证伪的冻结判定

阶段 1 只作病因分类，不决定 A/C-2 最终胜负。

## 1A｜只换 checkpoint

### 固定条件

- 同一 Qwen3-4B 基座；
- 同一 41 题；
- 同一题面；
- 同一 greedy、temperature 0、2048；
- 同一 evaluator；
- 唯一变量是 stage1 adapter 与 final adapter。

### 分类阈值

#### `STAGE2_FORMAT_POLLUTION_SUPPORTED`

满足两项：

- final 相比 stage1，漏 `fact`、evidence-first 或字段容器异常的案例数增加至少 **5 案**，或增加至少 **10 个百分点**；
- final 的 `fact_normalized_f1` 没有同步提升至少 **3 个百分点**。

#### `STAGE2_BROAD_FORGETTING_SUPPORTED`

同时满足：

- final 的总体 `fact_normalized_f1` 比 stage1 下降至少 **5 个百分点**；
- 在“正向／特殊／新未见”三层中至少两层下降至少 **5 个百分点**；
- 下降不能主要由 JSON 解析失败单独解释；
- 若特殊层反而提升至少 **5 个百分点**，作为更强支持。

#### `NO_MATERIAL_STAGE_EFFECT`

- 所有主指标差异均小于 **3 个百分点**；
- 主要病理案例数差异不超过 **2 案**。

允许同时支持“格式污染”和“部分遗忘”；不得强迫只选一个标签。

---

## 1B｜A 输出上限 2048 → 4096

### 固定条件

只跑当前 22 个 A 触顶案。除 `max_output_tokens` 外不改任何变量。

### 分类阈值

#### `OUTPUT_LIMIT_ROOT_CAUSE_SUPPORTED`

同时满足：

- 至少 **14/22** 案在 4096 内自然闭合为有效 JSON；
- token 2048 之后新增对象中，至少 **75%** 是未出现过的独立对象；
- 新增内容使 `fact_normalized_recall` 提升至少 **10 个百分点**；
- 严重复没有继续主导输出。

#### `OUTPUT_LIMIT_IS_TERMINATOR_SUPPORTED`

满足任一：

- 至少 **18/22** 案在 4096 仍继续重复或再次触顶；
- 至少 **18/22** 案的首次完整对象复读发生在 token 2048 之前，且 2048 后新增对象中至少 **75%** 为重复。

其余标记 `MIXED_OUTPUT_LIMIT_EFFECT`。

---

## 1C｜只改旧 C 题面范围写法

### 固定条件

adapter、输出合同、金标、41 题、解码均不变。只把标题中的 `@start:end` 改成与输出不同形的自然语言。

### 分类阈值

#### `HEADER_RANGE_COPY_IMPORTANT_CAUSE`

同时满足：

- 复制标题范围的指针比例下降至少 **20 个百分点**；
- 严格合法指针比例上升至少 **5 个百分点**。

#### `HEADER_RANGE_COPY_PRESENT_NOT_MAIN`

- 标题范围复制下降至少 **20 个百分点**；
- 合法指针提升不足 **5 个百分点**。

#### `NO_MATERIAL_HEADER_EFFECT`

- 标题复制下降不足 **10 个百分点**；
- 合法指针提升不足 **2 个百分点**。

其余标记 `MIXED_HEADER_EFFECT`。

### 阶段 1 完成闸门

三个实验全部满足：

- 每个实验只有一个差异变量；
- 82 案和子集原始输出完整保存；
- 旧读数与新诊断读数并列；
- 没有改写历史成绩；
- 报告使用上述固定标签。

通过后自动进入阶段 2，无需 CZ 再确认。

---

# 三、阶段 2：C2_UNIT 与切段器硬闸门

阶段 2 只用 30～50 个原型窗口。切段器不得读取 fact 或 evidence 金标。

## 1. 机械硬闸门

必须全部满足：

| 指标 | 阈值 |
|---|---:|
| 同一原文连跑两次 unit map 完全一致 | 100% |
| 单元可反向逐字还原 | 100% |
| `sample_id + local_id` 唯一映射 | 100% |
| A exact evidence 字符被 C gold units 覆盖 | 100% |
| C 的 `fact/status/speaker` 与 A 一致 | 100% |
| C gold 全部由程序生成 | 100% |
| 可见 ID、顺序、去重、B/T 终点合法 | 100% |
| 只读上下文无编号 | 100% |

任何一项低于 100%，不得训练。

## 2. 证据粒度闸门

对原型集中所有 fact 统计：

- 至少 **95%** 的 fact 使用不超过 **3 个** evidence IDs；
- **100%** 的 fact 使用不超过 **5 个** evidence IDs；
- 额外带入字符数 `p50 ≤ 20`；
- 额外带入字符数 `p90 ≤ 60`；
- 额外带入字符数 `p95 ≤ 80`；
- 任一 fact 额外带入超过 100 字，必须列为 atomizer 失败样本，不得静默接受。

额外带入字符数定义：

```text
selected_unit_union_chars - exact_gold_evidence_chars
```

按原始 Unicode 字符计数，保留原标点和空白；编号标签不计入。

## 3. atomizer 调整纪律

若粒度闸门不通过：

- 允许在看模型结果前调整 atomizer；
- 每次调整新建版本和 SHA；
- 必须重新生成全部 unit map 与 C-2 view；
- 不得只为失败 fact 人工特切；
- 通过机械闸门后冻结 atomizer，之后训练期不能再改。

---

# 四、阶段 3：C-1／C-2／C-3 小探针

## 1. 固定探针规模

建议固定为 **50 个 canonical windows**：

- 40 个 micro-train；
- 10 个 held-out probe；
- 来自当前权利状态合规材料；
- 不使用当前 41、旧 48 或其来源作者；
- 三个版本共享完全相同的 A 真值、unit map、窗口和样本顺序。

若仓库已有更合适的 30～50 固定集，可用现有数量，但必须在运行前锁定，不能看结果后增删。

## 2. 探针训练纪律

- 允许三套极小格式探针，但不得把它们称为正式 LoRA；
- 三臂 recipe、seed、步数、batch、基座和解码完全相同；
- `PROBE_RECIPE.json` 在输出前冻结；
- C-1 对 C-2 只改变 ID 外观；
- C-2 对 C-3 只增加固定两字锚；
- 锚字由明确机械规则定义，不允许任选。

## 3. 选择阈值

### C-2 对 C-1

C-2 是结构默认候选。只有 C-1 同时满足下面条件，才可推翻 C-2：

- C-1 的 ID 结构合法率比 C-2高至少 **5 个百分点**；
- C-1 的 `fact_normalized_f1` 比 C-2高至少 **5 个百分点**；
- C-1 的桥接区错误、证据终点落 B 错误不高于 C-2；
- 输出 token 优势至少 **5%**。

否则选择 C-2。结果相近也选择 C-2，因为 B/T 显式表达证据权限，代价仅一个字母。

### C-3 对 C-2

C-3 只有同时满足下面条件才能晋级：

- 错选 evidence ID 率相对下降至少 **20%**，且绝对下降至少 **5 个百分点**；
- 原始 JSON／schema 有效率下降不超过 **2 个百分点**；
- `fact_normalized_f1` 下降不超过 **2 个百分点**；
- 中位输出 token 增加不超过 **10%**；
- 锚字本身合法率至少 **98%**。

任何一项不满足，淘汰 C-3。锚字只改善“显示可读性”而不改善 ID 选择，也判淘汰。

### 灰区默认

样本过小导致差异不稳定时，不扩探针、不临时调阈值，默认冻结 C-2。

---

# 五、阶段 4～5：新数据池的执行闸门

## 1. 先锁作者和 split，再选段

顺序必须是：

```text
作者归一
→ 作品与首发日期核实
→ 权利状态
→ 作者级 train/dev/test lock
→ 排除当前 41／旧 48 作者
→ 再选窗口
```

同一作者不能跨 split。同一作品的已接收训练窗口必须来自不同章节。

## 2. 首批规模

首轮正式 A/C-2 pilot 推荐使用：

```text
200 个 train canonical windows
40 个 dev canonical windows
```

约等于 100 本训练作品 × 每本 2 窗口，再加作者独立的 dev。实际作品数可以因作者归并而调整，但 canonical window 数在训练前锁定。

本阶段不动最终 sealed test。

## 3. 来源比例

每次真实 LoRA 前：

- 近年目标窗口累计占比 75%～85%；
- 中心目标 80%；
- 单一题材达到 35% 预警，达到 40% 阻断并要求书面例外；
- 同一作者全部作品合计默认不超过 4 个训练窗口；
- 每个窗口通常 2～6 个 facts，通常不超过 8；
- 特殊与低密度样本合计不得超过总训练窗口的 1/3，保证普通自然样本至少 2:1。

## 4. 训练 manifest 闸门

进入真实训练的每行必须：

- `TRAINING_CLEARED`；
- author split 合法；
- 原文 SHA 和 unit map SHA 存在；
- A 已独立复审；
- C-2 可机械重建；
- schema 与字段顺序统一；
- 无当前 41、旧 48 或其来源作者；
- 无近重复窗口；
- 无同章第二窗口。

---

# 六、阶段 6：A／C-2 首轮格式胜负阈值

## 1. 训练设计先冻结

首轮对照只允许 evidence 表示不同：

| 项目 | A | C-2 |
|---|---|---|
| canonical windows | 相同 | 相同 |
| fact/status/speaker | 相同 | 相同 |
| evidence | 逐字原文 | B/T 局部 ID |
| 基座、LoRA、seed | 相同 | 相同 |
| 样本顺序 | 相同 canonical 顺序 | 相同 canonical 顺序 |
| 正常／特殊 | 单一混合 manifest | 单一混合 manifest |
| evaluator／解码 | 相同 | 相同 |

首轮不再采用“正向阶段→特殊阶段覆盖”。所有样本使用同一 JSON 容器、字段顺序和 EOS，并按固定 seed 分层打散。

## 2. 胜负分成两个概念

- `FORMAT_WINNER`：哪种 evidence 表示更适合继续扩数；
- `PRODUCTION_READY`：模型是否达到产品可用标准。

本轮只决定 `FORMAT_WINNER`。格式胜出不等于模型可上线。

## 3. C-2 胜出条件

只有下列条件全部满足，才能写 `C2_FORMAT_WIN`：

### 语义不劣

- `C2 fact_normalized_f1 ≥ A - 0.02`；
- `C2 fact_precision ≥ A - 0.03`；
- `C2 fact_recall ≥ A - 0.03`；
- `C2 status_accuracy_on_matched_fact ≥ A - 0.03`；
- `C2 speaker_accuracy_on_matched_fact ≥ A - 0.03`。

### C2_UNIT 证据合格

- C-2 ID 结构合法率 ≥ **98%**；
- 在已匹配 fact 上，所选 units 对 A exact evidence 的字符覆盖 recall ≥ **95%**；
- 预测 evidence 的额外带入字符 `p90 ≤ 80`；
- 证据不支持 fact 的比例不高于 A 超过 **2 个百分点**。

### 生成可靠性合格

- C-2 原始 JSON 有效率 ≥ **95%**；
- C-2 truncation rate ≤ **1%**；
- C-2 severe repeat case rate ≤ **3%**；
- C-2 的“非法 JSON＋触顶＋严重复读”案例率比 A 至少低 **5 个百分点**，或相对下降至少 **25%**。

### 确实获得短输出收益

- C-2 完成 token 中位数比 A 至少减少 **25%**；
- p90 完成 token 不高于 A。

### 无明显结构性退化

对 gold fact 数不少于 20 的关键分层：

- 任一层 `fact_normalized_f1` 不得比 A 低超过 **8 个百分点**；
- 不得在 speaker、稀有 status 或跨单元证据中出现系统性失效。

### 配对不劣性检查

对案例做 paired bootstrap：

- C2-A 的 fact F1 差异 95% CI 下界不得低于 `-0.03`。

若样本不足导致区间过宽，进入一次预授权复跑，而不是直接宣布 C-2 胜出。

## 4. A 胜出条件

满足任一核心条件，可写 `A_FORMAT_WIN`：

- C-2 `fact_normalized_f1` 比 A 低至少 **5 个百分点**；
- C-2 fact recall 或 precision 任一低至少 **7 个百分点**；
- C-2 status 或 speaker 在两个以上关键分层低至少 **5 个百分点**；
- C-2 ID 结构合法率低于 **95%**；
- C-2 对 exact evidence 的字符覆盖 recall 低于 **90%**；
- C-2 关键分层退化超过 **10 个百分点**；
- C-2 输出 token 只减少不足 **15%**，同时生成可靠性没有至少 5 个百分点的改善。

## 5. 灰区

下面情况写 `NO_FORMAT_WINNER_YET`：

- 语义差距落在 -2 至 -5 个百分点；
- 一个版本语义更好，另一个可靠性明显更好；
- 置信区间跨过不劣界；
- 关键分层相互冲突；
- 两臂绝对语义能力都太低，无法区分格式问题和教材问题。

灰区只允许一次预先授权的复跑：

- 同一数据；
- 同一 recipe；
- 只换第二个固定 seed；
- 不增删样本、不改 evaluator、不改解码。

两次仍灰区，则停止扩数，状态为：

```text
NO_FORMAT_WINNER_DO_NOT_SCALE
```

不得用“再加很多数据看看”绕过格式未决。

---

# 七、当前 41 与旧 48 的后续身份

- 当前 41：只用于阶段 1 根因证伪和历史回归，不再决定新 A/C-2 胜负；
- 旧 48：继续保持旧冻结隔离卷身份，不进入当前成绩分母；
- 新 A/C-2 胜负必须使用作者独立的新 dev；
- 最终 sealed test 在格式胜出、教材冻结后只运行一次；
- sealed test 的作者和作品在建池之初就锁定，不能看到结果后换题。

---

# 八、每阶段固定交付物

每阶段至少输出：

```text
STAGE_N_RECEIPT.md
RUN_STATE.json
MANIFEST.json
RAW_OUTPUTS.jsonl（有模型运行时）
METRICS.json
CASE_DIAGNOSIS.jsonl
OPEN_ISSUES.md
DECISION.md
```

回执必须写：

- 输入与输出 SHA；
- 唯一变量；
- 是否通过阶段闸门；
- 是否自动进入下一阶段；
- 唯一下一动作；
- 没有做什么。

---

# 九、容易踩坑的固定提醒

- A/C-2 两个视图不能当成两倍数据量；
- “最近更新于 2026”不能把 2012 首发小说变成近年小说；
- `DATE_UNKNOWN` 不得偷偷计入近年配额；
- C-2 不生成锚字，展示用前两字和省略号由程序补；
- B 区只能机械取紧邻前文，不能为金标专挑；
- atomizer 一旦冻结，改动就必须全量重建 unit map 与 C-2；
- 特殊样本不能使用另一种字段顺序；
- 评分器修复后的高分不能覆盖旧成绩；
- 格式胜出不等于训练集够广，也不等于模型可用；
- 权利未清可以继续候选施工，但不能进入训练；
- 当前 41 已被反复分析，不再适合充当新路线的最终选型卷。

来源：ChatGPT
