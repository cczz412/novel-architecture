# 四份外部顾问回包 · 只读入库索引（2026-08-20）

四份 ChatGPT 侧回包一次性入库，供后续工单按格取用；以后干活窗口直接读本目录，不再传 ZIP。

- **身份**：全部 `ADVISORY_ONLY` 候选。没有执行权、施工权或拍板权；与现行代码、正式合同或 CZ 拍板冲突时，一律以后者为准（「当前代码优先」）。
- **归位条件**：每张工单消费完自己那格后，把吸收结论登进对应正式件；七张工单收线时，本目录按工单 6 的证据纪律整体归档退役。
- **入库口径**：只收解出的 md＋json 正文（8 件），ZIP 原件不进 Git，由 CZ 保管，SHA 见下表。

## 包目录与消费排期

| 包 | 内容一句话 | 给哪张工单用 | 什么时候用 | ZIP SHA256 |
|---|---|---|---|---|
| 测试设计增补（原文已迁走） | 新增 15 条×6＝90 例。现行包装件在 [ATOMIC_TEST_DESIGN_R03_ADDENDUM_20260821_R01](../../references/atomic-expectations/ATOMIC_TEST_DESIGN_R03_ADDENDUM_20260821_R01/)；顾问原文在同包 [source/](../../references/atomic-expectations/ATOMIC_TEST_DESIGN_R03_ADDENDUM_20260821_R01/source/) | 工单 3（已吸收） | 不要再从 work 读 | `f0de2eb114aa5191358ff424778425961d82b0e9c15f9e59e3b41d84d7c9303e` |
| 运行缺口登记（已迁走） | 142 条需求的代码证据分层。现行在 [capability_traceability_sources_r01/](../../governance/capability_traceability_sources_r01/) | 工单 4／5（已吸收进追踪表） | 不要再从 work 读 | `b19c09bc7367683e8d034d7dbf8be4c374155cebff145df1ae101dab06598f6b` |
| [dual_lane_ledger_handover_r01/](dual_lane_ledger_handover_r01/) | 双车道、章事实稿、十本账与交棒设计；含确认粒度候选方案「整包提交＋逐条状态：普通批量、高影响单签」 | 工单 5 的 PR-C 参考；PR-E5 施工依据 | PR-C 前读；PR-E5 必须等 CZ 冻结确认粒度后才能按它施工 | `7e080ba243b12c01d5b75e0dd8b688cedd5b7f032a6b1e3a0988e99fd9eec933` |
| [multi_form_creative_intake_r01/](multi_form_creative_intake_r01/) | 新功能设计：剧本／灵感／产品原生大纲三条导入适配器 | 暂不施工 | 冻结到七张工单收线；之后作为第一批走「想法→需求条目→照表施工」小门的输入 | `d5dba654994e406beacb553dc6384c03136f35b805d3160636ceb6846aeee017` |

## 两条特别注记

1. **确认粒度**：dual_lane 包里的「整包提交＋逐条状态」正是决策书里待 CZ 拍的第 1 件的候选答案；CZ 拍板前它只是候选，PR-E5 不得据此开工。
2. **四包引用的代码基线**：`01efc50`（运行差量止点）与 `79bd2e2`（外审打包基线），均为模块分支上的 commit；消费时先核对目标分支是否仍与该基线一致，漂了就先对账再用。

来源：Cursor 云端 Agent 入库，2026-08-20；原件为 ChatGPT 侧四份回包
