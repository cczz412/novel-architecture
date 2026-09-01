# 设计冲突与边界

- Pro R01 唯一阻断是没读到 B-06 exact-head 字节；W0 已补读并确认三件套单事务，随后 B-06 run fence 已随 PR #215 合并，因此该阻断已关闭。
- Pro 建议的持久对象最多三种，本目录保持三种，没有新增 Checkpoint、CommitIntent、provider checkpoint 或持久 ResumePlan。
- CCZ-142 exact adapter 字段仍在并行校准。本目录只冻结 locator／ref／hash 的零 API 交接壳，不把实验字段当产品真源。
- `InternalDebugRecord` 只供维护者，默认 7 天、没有新政策不超过 30 天；本目录没有实现跨项目聚合、导出支持包或 raw payload 存储。
- B-08、B-10、B-11 只保留接口边界，不在本票写它们的对象或作者文案。
- 当前结果只证明机械恢复与停损语义，不证明语义准确率、速度或 Token 改善。

来源：Codex
