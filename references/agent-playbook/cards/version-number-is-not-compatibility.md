# 版本号不是兼容证明

身份：外部先验

## 遇到什么

某个 JSON、合同或模块接口加了字段，也递增了版本号。后续 Agent 准备直接宣布“向后兼容”，或者只测新代码能读新样例。

## 对的做法

把版本号只当定位标记，兼容性要按实际风险分别证明：字段缺失、空值、默认值、未知值怎样处理；旧写入能否被新读取，新写入能否被旧读取；真实消费者是否仍按预期解析和产生投影；唯一写口、重复动作、过期基线和部分失败是否会留下副作用。只声明已经测过的范围，范围外保持“未证明”。

这是一条外部工程先验，不要求现在引入重型注册中心，也不冻结旁车文件、哈希字段、适配器或测试工具。具体合同仍由现行正式入口和合同所有者决定。

## 错的做法

只要 `version` 加一就写兼容。只跑 Schema 校验，不跑旧写新读、新写旧读和真实消费者。把“新增字段可选”推成所有旧消费者安全。用候选适配层长期掩盖语义冲突。把本卡升级成执行票，或把研究里的文件名、字段和停点写成已拍合同。

## 出处

- [DR05 执行摘要](../../../work/issue115_playbook_compile_pack_20260824/sources/TEMP_leftovers/deep_research_returns/DEEP_RESEARCH_R13_BATCH01_FULL_20260817_R01/DR05/extracted/00_EXECUTIVE_SUMMARY.md)（版本号只定位；字段、方向、消费者、写入分别证明）
- [六份研究完整价值映射](../../../work/issue115_playbook_compile_pack_20260824/sources/TEMP_leftovers/deep_research_returns/DEEP_RESEARCH_R13_BATCH01_FULL_20260817_R01/FULL_VALUE_INTEGRATION_MAP_R02.md)（“兼容不是一个布尔值”）

来源：#115；批次 E；CZ 2026-08-24
