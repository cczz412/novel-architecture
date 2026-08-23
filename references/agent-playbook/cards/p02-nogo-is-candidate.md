# P02 的 No-Go 不是现行产品否决

身份：设计审查风险

## 遇到什么

读到 SI-007 P02 开头「按当前设计直接施工：No-Go」，或读到拆状态轴、换库、移交协议，准备按「产品已经否决／合同已经改了」往下写。

## 对的做法

No-Go 针对的是当时 `pack2_ledger_system.zip` 那包**候选设计稿**。审查效力是「一旦按那包施工会有结构风险」，不是现行产品已经炸了，也不是字段已经定稿。

方向上仍可对照：计划与事实分号、事实账集中、旧计划保留、展示层只读。建议本身还是审查意见。现行语义回 [R14](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)。

## 错的做法

写成「现行产品 No-Go」。把 P02 里的 SQLite／PostgreSQL、`story_commit_seq`、移交状态机当成已拍合同。用包内旧字段覆盖共同背景板。把当时稿里的 PE／H／MC 名字当成现行数据合同。

## 出处

- [SI-007 包入口](../../survey-inbox/packages/DESIGN_REVIEW_AND_TECH_RESEARCH_RETURNS_20260813_R01/00_READ_ME_FIRST.md)（P02 开头结论、审查效力边界）

来源：#115
