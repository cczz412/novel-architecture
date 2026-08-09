# 仓库基础设施、寻路和日常执行提速｜STATUS

## Identity

- 生命周期：ACTIVE
- 角色：仓库级长期主线
- 机器状态入口：[`../../CURRENT_STATE.json`](../../CURRENT_STATE.json)

## Current state

W05 仓库卫生和 W06 根入口已收口；当前只对齐 Progress Storage、全局 Progress Skill 与语义提醒 Hooks，不扩建新的进度系统。

## Last reliable checkpoint

- [`../../CURRENT_STATE.json`](../../CURRENT_STATE.json)
- [共同背景板 R04 入口](../../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260808_R04/00_READ_ME_FIRST.md)
- [Storage／Skill／Hooks 写前预检](../../../TEMP/progress-storage-skill-alignment-r01/PROGRESS_ALIGNMENT_CLOSEOUT_RECEIPT.json)

## Next action

先完成 Router → STATUS 存储合同迁移；验收并独立提交后，停下等 CZ 单独决定是否替换全局 Progress Skill。

## Blockers

- `progress/` 中的旧专题页与特殊 lock／ledger 本轮不移动。
- 全局 Skill 与语义 Hooks 不属于本张合同迁移票。

## Recovery guardrails

- Must not repeat: 不重新盘点 W05/W06 历史，也不重新设计已经封存的四文件 Storage 结构。
- Must not skip: 先验证 router、选定 STATUS 与唯一测试消费者形成同一份恢复合同，再独立提交；任一新耦合都要停下校准。

## Recent CZ decisions

- `update_plan` 只管当前窗口；progress 只管跨窗口长期接力。
- 新窗口从 router 进入一个选定 STATUS，不再从 `current-progress.md` 读取恢复细节。

updated_at: 2026-08-09

来源：Codex
