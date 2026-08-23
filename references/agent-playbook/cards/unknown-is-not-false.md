# 不知道，不等于没有发生

身份：已拍加固

## 遇到什么

某个状态没有值，或检查器没找到证据。后续 Agent 能不能统一写成 `false`、未发生或不存在？

## 对的做法

**已拍：**`unknown` 至少要分清：尚未检索、覆盖内未找到、证据冲突、作者未决定、对读者隐藏、尚未发生。它们的下一步完全不同，不能用一个空值吞掉。检测器也要允许“模型不知道”，不能被迫二选一。

**加固：**外部时间与记忆证据同向提醒，模糊、无界、分支和未知都可能真实存在；`unknown` 不能自动补成 `false`。[CLM-DR-MEM-03-K11]

## 错的做法

没检索就写不存在。覆盖内没找到就写绝对没有。对读者隐藏就写尚未发生。作者没决定就写冲突或默认值。把本卡升级成执行票；把外部 unknown 经验写成已拍存储枚举、界面文案或迁移合同。

## 出处

- [R14 真值分层页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md)（N17：unknown 六分）
- [R14 创作与记忆管线页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/03_CREATION_AND_MEMORY_PIPELINES.md)（检测器增加“模型不知道”档）
- [EKB 记忆页](../../external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/04_MEMORY_TRUTH_TIME_AND_RULES.md)（K11）

来源：#115；批次 A；2026-08-24
