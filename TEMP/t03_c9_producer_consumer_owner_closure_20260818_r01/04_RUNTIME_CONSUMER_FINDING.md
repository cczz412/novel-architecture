# 真实 consumer 核对

## 文件声明

- `PLAN_LEDGER_STORAGE.md` 接线表：C9 前提包候选由 M11 写、M8 读，来源变化即重编，只读且不能回写。
- `ARCHITECTURE.md`：M11 输入 C4＋规划账＋任务描述，输出 C9；当前唯一直接消费者写为 M8。
- `CONTEXT_PACKER_DESIGN_R01.md`：同样画 M11→C9→M8，但文头明确它是设计稿，不是合同或 Schema。
- `M8_PLANNING_DESIGN_R04.md`：C9 増补仍标“落地时／挂账”。

## 运行时观察

- `novel-mvp/mvp/packer.py` 不存在；
- `mvp/plan.py` 没有 C9、premise pack、load IDs、why-loaded 或 budget 输入；
- 它直接调用 `store.facts(project)`，只筛 `status == confirmed`；
- 正式 C7 v1 没有 `premise_pack_ref`、`why_loaded` 或 C9 lineage 字段。

因此：

- 声明 consumer：M8；
- 实际 runtime C9 consumer：未找到；
- 现役旁路：M8 v0 `plan.py` 直接读 C4 风格事实列表；
- 这条旁路不等于 C9 已接通，也不能被本 TEMP 任务修改。

这不是本轮新失败，而是“候选尚未施工”的现行事实。正式接线必须另开产品／合同施工票。

来源：Codex
