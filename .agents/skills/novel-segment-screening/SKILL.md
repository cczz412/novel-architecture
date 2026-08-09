---
name: novel-segment-screening
description: 对当前任务明确点名且权利边界已声明的小说正文批次做机械切窗、语义初筛和二次密筛。Use when 用户或上层微调任务明确要求这项筛选能力，并提供当前批次、来源身份、输出根和筛选口径。Do not use for普通微调问答、训练授权、权利判定、整库审计、未点名语料，或仅因任务提到“片段/筛选”。
---

# 网文素材批次筛选

只对当前任务明确点名、来源身份和权利边界已经声明的小说正文批次做机械切窗、初筛、密筛和候选输出。本 Skill 不负责发现语料、裁定权利、批准训练、构建 Production Canonical 或审计整库。

## 执行合同

- Required inputs: current batch manifest; source identities; rights boundary; output root; filter contract.
- Allowed reads: only the named batch and direct estimator or config dependencies.
- Allowed writes: candidate outputs and receipt under the authorized output root.
- SIDE EFFECTS: local candidate writes. No API, training, Git, Notion, or source modification.
- May call: the current task's estimator only when its identity is supplied.
- Must not call: training, model APIs, Notion, Git, another team SOP, external review, or unrelated corpus discovery.
- Default scope: `COUPLED`.
- Validation: `V2` member and source SHA, counts, rights labels, output schema, and named-batch closure.
- Expand only if: `TARGET_NOT_UNIQUE`, `GENERATED_VIEW_DEPENDENCY`, or `IDENTITY_MISMATCH`.
- Hard stop: rights missing, source identity drift, output collision, undeclared batch, or any required input missing.

缺少批次、来源身份、权利边界、输出根或筛选口径时，返回 `SCREENING_INPUT_INCOMPLETE` 并停止。不得从旧票据猜当前批次，也不得搜索整库补输入。

## 触发边界

以下条件同时成立才启用：

1. 用户或上层微调任务明确要求使用这项筛选能力；
2. 当前批次已点名；
3. 五项输入合同齐全。

“按这份批次清单切窗并密筛”可以启用；普通微调问答、训练资格判断、权利审计、模型表现分析、整库素材发现，或只说“从几本书找点好片段”都不启用。

批次很大不会自动启动团队；用户明确启用团队且当前主任务也满足本 Skill 输入合同时，两者才可由上层组合。团队模式本身也不会自动启用本 Skill。

## 工作流程

1. **锁定输入**：读取当前批次清单，核对来源路径、成员身份、权利标签、输出根和筛选合同；输出根已有未知内容时硬停。
2. **机械切窗**：只按当前筛选合同和已给定身份的估算器／配置切窗；记录合同要求的位置、来源和片段身份，不临时安装依赖。
3. **初筛与密筛**：初筛类别、密筛阈值、去重规则和作品上限全部来自当前 `filter contract`，不得沿用历史批次数字。
4. **候选写盘**：只在授权输出根写当前合同规定的候选工件和回执；不修改来源正文或权利记录。
5. **定向验收**：按 `V2` 核对成员集合、来源／输出 SHA、数量、权利标签、输出 Schema 和批次闭合；合同没有要求时，不跑全仓测试或整库 QA。

## 回执最小字段

回执至少记录：

- 当前批次身份与 manifest SHA；
- 来源对象和成员 SHA；
- 权利边界原值；
- 输出根和筛选合同身份；
- 使用的估算器／配置身份；
- 输入、初筛、保留、丢弃的机械计数；
- 输出成员和 SHA；
- API、训练、Git、Notion、来源修改均为 false；
- 验证结果与任何硬停原因。

字段和值从当前任务输入和实际输出取得，不保留历史波次、书数、章节数、日期、固定 SHA 或旧回执统计。

## 权利与身份边界

- Skill 只消费已声明的权利边界，不自行推断权利。
- 权利缺失是硬停，不是扩大搜索范围的理由。
- `screened candidate != training authorized`：筛中只表示进入候选输出，不代表可训练、可晋升 Production Canonical 或权利已放行。
- 来源、批次或输出身份漂移时停止，不刷新旧 SHA 追绿。

来源：Codex
