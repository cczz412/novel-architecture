# 故事时间、叙述位置、系统时间别混成一个字段

身份：已拍加固

## 遇到什么

Agent 要判断人物在某一场景的状态，手上只有章节顺序或最后修改时间。能不能把“最新一条”当时的当前状态？

## 对的做法

**已拍：**至少分开故事内有效区间、读者何时看到的叙述位置、系统何时登记或修订。故事序、叙述序和创作痕迹也不能让一个数组位置同时承担。查询人物状态要按目标故事时间取对应版本，不能让未来状态污染过去场景。

**加固：**外部记忆材料同向支持“有效时间”和“系统知道时间”分开，并保留版本谱系而不只留最后修改时间。[CLM-DR-MEM-03-K02] [CLM-DR-MEM-03-K03] [CLM-DR-MEM-03-K04] SI-004 的竞品拆解只加固“状态应能随时间演进查看”，不证明任何竞品条目就是故事正史。

## 错的做法

用章节号替代故事时间。用 `updated_at` 之类最后修改时间判断故事当时状态。新状态直接覆盖旧状态，不留适用区间和修订史。把本卡升级成执行票；把竞品形状、具体字段名或外部先验写成已拍数据库合同。

## 出处

- [R14 真值分层页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md)（“三序”；N17“三种时间”）
- [R14 风险页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/08_VALIDATION_MARKET_AND_RISK_REGISTER.md)（人物时间账缺失风险）
- [EKB 记忆页](../../external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/04_MEMORY_TRUTH_TIME_AND_RULES.md)（K02／K03／K04）
- [SI-004 竞品回包](../../survey-inbox/packages/MANUS_R06_CLOUD_RESEARCH_20260812_R01/returns/RETURN_02_AI_WRITING_AGENT_LANDSCAPE_20260812_R01.md)（状态演进可借鉴，条目不能冒充正史）

来源：#115；批次 A；2026-08-24
