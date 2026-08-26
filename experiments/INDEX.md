# 试验专区索引

新专项试验只写 `experiments/<experiment_id>/`。历史 `runs/`、`reports/` 原件不搬、不回写。

## 当前登记

| 试验 | 状态 | 位置 | 说明 |
|---|---|---|---|
| Z76_phase2_semantic_inspector_pilot_20260721 | complete | `experiments/Z76_phase2_semantic_inspector_pilot_20260721` | 规则先验＋DeepSeek 只分流＋通过桶固定抽样；不产正式真值。 |
| CCZ57_ZERO_API_EXTRACTION_CONTROL_SKELETON_20260827_R01 | planned | `experiments/ccz57_zero_api_extraction_control_skeleton_20260827_r01` | 只读重放现有真实 API 回件，设计 M3 候选进入 M4 前的不可变保存、机械检查、局部 Patch、版本和停损骨架；本轮不含运行代码或模型调用。 |

未登记的本地候选与证据目录不写进生成页，避免干净副本和当前机器得到两张不同路牌。
本机只读盘点方式见 `experiments/README.md`。

来源：Codex
