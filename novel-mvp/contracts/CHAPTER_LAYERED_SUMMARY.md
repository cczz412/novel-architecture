# CHAPTER_LAYERED_SUMMARY · 章节封存后的分层摘要

**版本：v1**

一句话用途：把多张章节结算封存记录压成阶段或长跨度读取投影，同时保留全部叶子章节、未决项和重算依据。

实现状态：`CONTRACT_ONLY__SUMMARY_GENERATION_AND_PERSISTENCE_NOT_AUTHORIZED`。

## 1. 摘要不是新真值

本合同固定：

```text
projection_only=true
writes_truth=false
```

摘要不能写回章节、事实、十本账、工作卡、沙箱、来源封条或 current 指针，也不能充当 owner commit receipt。

上一章默认读取完整 `CHAPTER_SETTLEMENT_SEAL v1`。更老内容才先读分层摘要；命中具体人物、规则、秘密、状态或因果时，再沿叶子 `settlement_sha256` 下钻。

## 2. 两种摘要层

| `summary_kind` | 输入 | 用途 |
| --- | --- | --- |
| `PHASE` | 按精确顺序固定的一组章节结算记录 | 提供一个阶段、故事范围、卷或作者钉选集合的薄读取面 |
| `LONG_RANGE` | 阶段摘要和／或少量章节结算记录 | 提供更长跨度入口，但仍保存扁平化叶子清单 |

`PHASE` 不能直接吃另一张摘要，避免第一层就丢掉原章边界。`LONG_RANGE` 可以组合下层摘要，但必须能回到全部叶子章节。

## 3. 不固定章数或永久层数

`scope` 与 `policy` 必须明确：

- 分组依据是 `STORY_PHASE`、`STORYLINE_SCOPE`、`VOLUME_SCOPE`、`AUTHOR_PINNED_SET` 或其他已登记策略；
- 精确范围引用；
- 策略 ID、版本、分组依据和 `policy_sha256`；
- 输入业务顺序。

合同没有 `chapter_count`、固定 10／20／50 章或永久三层字段。策略、输入集合或生成器版本改变时，生成新摘要；不能拿旧摘要继续冒充 current。

## 4. 输入清单和叶子清单

`inputs` 保存当前层直接读取的结算对象或下层摘要。`leaf_settlement_refs` 保存穿透所有下层后的完整章节结算清单。

规则固定：

- 输入和叶子的 `order` 从 1 连续递增；
- 同一输入不能重复；
- 同一叶子不能从两条输入路径重复进入；
- 每个叶子必须写明章槽、`settlement_sha256` 和结算声明水位；
- 清单必须与实际传入的精确源对象逐项相同。

## 5. 每段摘要都要有回指

每个 `sections[]` 都必须列出 `source_leaf_settlement_refs`。所有叶子至少被一个摘要段覆盖；未知叶子、空来源和漏叶子都拒绝。

机械校验只能证明引用覆盖，不能判断自由文字是否语义忠实。摘要内容的取准、漏项和噪音要由后续真实题集评测，不能用结构 PASS 冒充语义质量。

## 6. 未决项不能被压没

validator 会从全部叶子结算记录重建 `(settlement_sha256, item_id)` 清单。`unresolved_item_refs` 必须逐项完全相同：

- 不能因为摘要变薄就删除 Hook、义务、疑问、冲突或风险；
- 同名未决项位于不同章节时仍是两条精确引用；
- 未决项后来结清、延期或改线时，源结算对象或后续结算输入变化，摘要必须重算。

## 7. owner 未解析向上层传播

摘要声明水位只有：

| `claim_kind` | 条件 |
| --- | --- |
| `RESOLVED_PROJECTION` | 所有叶子都是 `OWNER_RESOLVED_SEALED` |
| `OWNER_UNRESOLVED_PROJECTION` | 任一叶子或下层摘要仍有 owner 未解析 |

未解析不能在上层压缩时消失。补齐 owner 后形成的是新结算对象和新摘要；旧未解析摘要保留历史身份。

## 8. 摘要身份和重算

`summary_sha256` 对删除自身后的完整规范 JSON 计算。下面任一项变化，摘要值必须变化：

- 直接输入或业务顺序；
- 叶子结算对象；
- 作用域和分组依据；
- 策略 ID／版本／摘要；
- 任一摘要段或来源；
- 未决项清单；
- 生成器身份／版本。

旧摘要不能覆盖，也不能只改一个 current 指针就假装内容没变。

## 9. validator 能证明什么

调用方把精确 settlement 文档和适用的下层 summary 文档作为内存对象传入。validator 只做：

1. Schema、投影身份、策略摘要和 `summary_sha256`；
2. 递归输入存在、类型、作用域和声明水位；
3. PHASE／LONG_RANGE 输入边界；
4. 扁平化叶子顺序、去重和完整覆盖；
5. 每段摘要的叶子来源；
6. 全部未决故事项覆盖；
7. owner 未解析逐层传播；
8. 循环引用和受保护内容拒绝。

它不读取路径、数据库、AuthorWorkspace、current、网络或模型，不生成自然语言摘要，也不判断摘要语义正确。

## 10. 合成夹具

`CHAPTER_LAYERED_SUMMARY.fixtures.jsonl` 是 16 条紧凑合成配方：

- 4 个结构正例；
- 3 个 owner 未解析传播例；
- 9 个结构反例。

夹具覆盖阶段摘要、长跨度摘要、作者钉选集合、策略换版、漏叶子、重复叶子、顺序漂移、无来源段落、未决项丢失、跨项目和旧摘要复用。

来源：Codex
