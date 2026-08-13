# Doubao Mini 真实小说 Pilot 计划

状态：**只设计，未选书，未切片，未建 gold，未训练**。

## 为什么必须走到真实小说

MICRO24 能证明一种格式能不能教会，但 synthetic→synthetic 的迁移不等于 synthetic→真实网文。

✅ 这一层要回答的是：

> Mini 在真实中文网文的句式、节奏、人物指代和信息密度下，能不能保住 A／C2 小实验里的能力。

## 两个数据身份

### REAL_TRAIN48

- 48 个真实小说训练 case；
- 只从获得内部训练权利门的来源进入；
- 作者和作品均不得出现在 REAL_DEV48；
- 不使用当前五本候选新书。

### REAL_DEV48

- 48 个真实小说未见 case；
- 不参与训练、超参搜索、renderer 修补或数据挑选；
- 作者、作品与 REAL_TRAIN48 完全隔离；
- 它是 pilot DEV，不是最终 blind。

## 数据隔离

机械验收必须同时检查：

- TRAIN 与 DEV 作者集合交集为 0；
- TRAIN 与 DEV 作品集合交集为 0；
- 窗口原文 SHA 交集为 0；
- 近重复文本候选进人工复核；
- DEV 没有出现在任何训练、few-shot 或调参文件里。

同一作者的不同书也算作者重叠，不能分到 TRAIN／DEV 两侧。

## 文本与 provenance

每个 case 至少登记：

- 作者和作品稳定 ID；
- 平台、章节、章内位置；
- 原始文本 SHA；
- 负责区和 context-only 范围；
- 每条 evidence 的明确 `start/end`；
- 权利状态和允许用途；
- 切段器／atomizer 版本和 SHA；
- canonical 版本和 SHA。

同一逐字 evidence 在窗口出现多次时，不能只搜文字后默认取第一次；位置必须来自 canonical 的明确 provenance。

## canonical 和 A／C2 派生

人工只维护一份 canonical 语义：

- fact；
- status；
- speaker；
- evidence 明确位置；
- 负责区与 context-only 边界。

A／C2 都从这份 canonical 机械生成：

- A 回填逐字 evidence；
- C2 生成最小覆盖 evidence IDs；
- fact／status／speaker 必须逐条一致；
- 派生失败就硬停，不在 C2 侧手工修语义。

## 双人语义复审

每个 case 需要两位审查者独立逐段读原文，审查前不看对方结论。

两人均需检查：

- fact 是否完整由负责区支持；
- 主体、时间、数字、否定和模态；
- 八态；
- speaker；
- evidence 是否过长、过短或跨越不必要文本；
- 只读上下文是否被误抽；
- 应抽热事实是否漏失；
- 冷动作、氛围句和重复面板是否过抽。

分歧不能用多数自动合并，必须进单独裁决票。

## 普通与困难案例

REAL_TRAIN48／REAL_DEV48 都需要分层登记，不把两类混成一个总分。

普通层可包含：

- 单一主体／单一明确事实；
- 直接对话；
- 单证据；
- 明确已发生或计划。

困难层可包含：

- 多证据／跨句／跨单元；
- 指代、别名、隐含因果；
- 推测／误信／否定／条件并存；
- 叙述和对话的 speaker 边界；
- 高信息密度和章节出口。

分层比例要在切片前冻结，不按 Mini 已知对错反向挑题。

## 当前五本新书

候选书：

- 《领袖》；
- 《重生78，从知青返城开始》；
- 《末日来袭，我能无限升级庇护所》；
- 《有道行》；
- 《颠婆勇者太多了》。

当前统一处置：

- 五本全部不进 REAL_TRAIN48；
- Codex 不自动选书；
- 不提前切片；
- 不提前建 gold；
- CZ 未来亲选 2 本作为 REAL_DEV48 来源；
- 剩余 3 本继续封存，作为后续真实 blind 候选。

旧裸模探针用的是本地 Qwen3.5-2B，20 问命中 0。它只能说该 Qwen 未显示知道这五本书，不能当成 Mini 的污染票或能力票。

## 执行前硬门

- CZ 已选 2 本 DEV 来源；
- 权利状态允许内部训练／评测；
- author／book split lock 已冻结；
- canonical schema 和 evidence position provenance 已冻结；
- 双人语义复审已通过；
- A／C2 两次机械渲染结果字节一致；
- DEV 没有进入训练路径；
- 费用、API、上传和精调任务已有另行 CZ 授权。

任一项未过就不建 REAL pilot。

来源：Codex
