# novel-mvp 当前与目标差距 R01

> 身份：`CURRENT_VS_TARGET`。本页防止把 [ARCHITECTURE.md](ARCHITECTURE.md) 的产品目标图误读成当前完成态；不替代合同、代码、测试结果或 CZ 拍板。
> 种子：`work/advisory_returns_20260820_r01/current_runtime_gap_review_r01/CURRENT_RUNTIME_GAP_REGISTER_R01.json`。该登记册本票只读；解析到 `142` 条原子证据行，原始分层为 `BACKGROUND_TARGET_ONLY=36／CURRENT_CODE_CONTRADICTS_TARGET=2／DIRECT_CODE_EVIDENCE=61／PARTIAL_DIRECT_CODE_EVIDENCE=43`。

## 目标与 runtime 到票表

| 目标／超前面 | main 当前事实 | runtime 随哪票到 | 本票边界 |
|---|---|---|---|
| 双车道：外来正文走 M1→M2→M3；产品自产章事实稿不回 M2／M3 | 当前 runtime 仍有按 C1 current 统一切段的旧接缝 | `PR-E1` 补外来道；`PR-E5` 补自产章事实稿竖切 | 本票只上目标架构，不改 runtime |
| M1～M3 外来材料导入、责任段、事实提名 | 分支已有候选实现，main 尚未按小票接入 | `PR-E1` | 不带 `novel-mvp/mvp/` |
| M4～M6 事实入账、作者确认、带证据查询 | main 仍缺模块分支的完整切片 | `PR-E2` | 合同目标不等于运行能力 |
| M7 优化工作台、M9 只读驾驶舱 | 当前主要是健康报告／概览投影切片 | `PR-E3` | 不把只读原型写成完整产品 |
| M8／M10／M11 规划、场景出口、统一取料 | 选择卡全文、人物阶段、10 本账取件仍未完整接好 | `PR-D` 先上共享底座，`PR-E4` 上模块 runtime | 账本目录本票只上设计 |
| 章事实稿、检查、C11 明确交棒、两步恢复 | 当前仍有旧 `WORK_DRAFT` 机器名和未闭合接缝 | `PR-E5` | 强耦合链不在 PR-C 拆开 |
| 测试与合成夹具基线 | runtime 小票完成前不能把测试镜像混进架构票 | `PR-F` | 本票不带 tests／fixtures |

## 本票三个耦合合同的消费者说明

| 合同／校验器 | 直接消费者 | 为什么在 PR-C 先上 | runtime 对齐票 |
|---|---|---|---|
| `contracts/C1_CHAPTER_DOC.md` | M2 责任段、M3 抽取、章节工作区、C11 登记读取侧 | 产品架构需要明确章节对象和来源身份边界；只是合同目标 | `PR-E1`＋`PR-E5` |
| `contracts/WORK_DRAFT_HANDOVER_ACTION.md` | 作者工作区交棒、C10/C11 适配、planstore 恢复链 | 交棒动作是章事实稿竖切的耦合边界；旧机器名暂留兼容 | `PR-E5` |
| `contracts/validate_c11_chapter_revision_ledger.py` | C11 fixture／合同 CI、章节登记和交棒验收 | 与冻结合同增量成套，先保证合同字节和机械校验一致 | `PR-E5`；若 main 测试变红则本票撤回并延期 |

## 读取纪律

- `ARCHITECTURE.md` 回答“目标怎样工作”；本页回答“现在还差什么”。
- 本票的合同增量若测试全绿，只表示机械兼容；不证明 PR-E1～E5 runtime 已存在。
- 后续每张 runtime PR 必回写追踪表并引用需求 ID；不能用本页替代测试与直接代码证据。

来源：ChatGPT（工单 5 PR-C；按仓内冻结分支与运行缺口登记册整理）
