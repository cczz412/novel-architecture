# 黄金三章是独立工作台，不是三章上限

身份：已拍加固

## 遇到什么

实现黄金三章体验时，后续 Agent 准备加 `chapter_limit=3`、免费三章、C1 的特殊章节类型，或把前三章自动整包塞进小说项目。

## 对的做法

**已拍：**R14 把黄金三章定义为独立工作台：只处理前三章，作者改到满意后再移交进小说项目。它是上层工作区与体验门牌，不由章节文档的类型、项目章数上限或收费字段定义；进入项目后仍服从同一套真值、确认和账本纪律。

**加固：**SI-016 指出，当时候选材料只写了“黄金三章工作台”方向，却没有正式接线，开发很容易把它误做成 C1 章数限制或另一套项目。这个审查支持把工作台身份与存储合同分开，但没有拍定移交包、落盘位置、迁移流程或界面步骤。

## 错的做法

把黄金三章写成数据库常量、付费额度或导入硬上限。另建一套前三章真源。作者一保存就自动移交全部材料。把“独立工作台”理解成 C1 新枚举。照搬 SI-016 的候选补句当已落合同。把本卡升级成执行票。

## 出处

- [R14 入口页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)（黄金三章是独立工作台，满意后移交）
- [R14 创作与记忆管线](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/03_CREATION_AND_MEMORY_PIPELINES.md)（打开项目与黄金三章工作台的边界）
- [R14 术语表](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/07_GLOSSARY.md)（黄金三章工作台的易混边界）
- [SI-016 消化稿](../../survey-inbox/packages/PLAN_CONTRACT_REVIEW_RETURNS_20260815_R01/02_RETURNS_DIGEST.md)（A7；B4）

来源：#115；批次 D；2026-08-24
