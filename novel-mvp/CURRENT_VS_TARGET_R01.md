# novel-mvp 当前与目标差距 R01

> 身份：`CURRENT_VS_TARGET`。本页防止把 [ARCHITECTURE.md](ARCHITECTURE.md) 的产品目标图误读成当前完成态；不替代合同、代码、测试结果或 CZ 拍板。
> 种子：[`CURRENT_RUNTIME_GAP_REGISTER_R01.json`](../governance/capability_traceability_sources_r01/CURRENT_RUNTIME_GAP_REGISTER_R01.json) 仍是 2026-08-20 的分层快照（`BACKGROUND_TARGET_ONLY=36／CURRENT_CODE_CONTRADICTS_TARGET=2／DIRECT_CODE_EVIDENCE=61／PARTIAL_DIRECT_CODE_EVIDENCE=43`）。它不是工单 5 收线后的新审计。

## 工单 5 小票落地（main）

PR-C～G 已经按小票合进 `main`，不是「还在候选分支等接入」：

| 票 | PR | main 上的身份 |
|---|---|---|
| PR-C 产品架构＋账本目录＋耦合合同 | #15 | 已落地。合同目标仍不等于作者可用。 |
| PR-D 共享 runtime 底座 | #16 | 已落地。 |
| PR-E1 外来道 M1–M3 | #17 | 已落地。 |
| PR-E2 M4 事实入账与外来章修订预演 | #18 | 已落地。 |
| PR-E3 M7 检查与 T14 写作检查域 | #19 | 已落地。只读原型仍不是完整驾驶舱。 |
| PR-E4 M8／M10／M11 规划与取料 | #20 | 已落地。十本账取件合同后来又经 L1～L5 加厚，统一设定账 writer 还没做。 |
| PR-E5 章事实稿交棒竖切 | #21 | 已落地。 |
| PR-F 测试基线回执 | #22 | 已落地。测试全绿 ≠ 852 条语义测试已跑。 |
| PR-G 外审证据登记 | #23 | 已登记。大件外置仍归工单 6，未获许可不得搬。 |

超级候选分支 `codex/module-runtime-foundation-20260819-r01@cc793c4719fb6470946c70e744f463147989547b` 禁止整支再合。

## 目标与现在还差什么

| 目标／超前面 | main 当前事实 | 还差什么 |
|---|---|---|
| 双车道：外来正文走 M1→M2→M3；产品自产章事实稿不回 M2／M3 | PR-E1／E5 已把对应 runtime 切片送上 main | 机械在仓 ≠ 作者可以当完整产品用；旧接缝是否清干净要看代码和测试，不看本页口号 |
| M1～M3 外来材料导入、责任段、事实提名 | PR-E1 已在 main | 不把模块切片写成「外来材料管线已交付给作者」 |
| M4～M6 事实入账、作者确认、带证据查询 | PR-E2 已在 main | 合同与查询面仍有未收口的作者体验缺口 |
| M7 优化工作台、M9 只读驾驶舱 | PR-E3 已在 main | 不把只读原型写成完整产品 |
| M8／M10／M11 规划、场景出口、统一取料 | PR-D／E4 已在 main；十本账内容合同 L1～L5 已在 main | 六本设定账还缺统一落盘方（拍板题 3） |
| 章事实稿、检查、C11 明确交棒、两步恢复 | PR-E5 已在 main | 强耦合链已按竖切进仓；不外推成写作闭环完成 |
| 测试与合成夹具基线 | PR-F 已在 main | 基线回执不是 852 语义测试执行证明 |

## PR-C 当时带上的三个耦合合同

这些合同已随 PR-C 进 main；对齐 runtime 的是后面已合并的 E1／E5，不是「还没做的未来票」。

| 合同／校验器 | 直接消费者 | 为什么当时先上 | runtime 对齐票（现已合并） |
|---|---|---|---|
| `contracts/C1_CHAPTER_DOC.md` | M2 责任段、M3 抽取、章节工作区、C11 登记读取侧 | 产品架构需要明确章节对象和来源身份边界 | PR-E1＋PR-E5 |
| `contracts/WORK_DRAFT_HANDOVER_ACTION.md` | 作者工作区交棒、C10/C11 适配、planstore 恢复链 | 交棒动作是章事实稿竖切的耦合边界 | PR-E5 |
| `contracts/validate_c11_chapter_revision_ledger.py` | C11 fixture／合同 CI、章节登记和交棒验收 | 与冻结合同增量成套 | PR-E5 |

## 读取纪律

- `ARCHITECTURE.md` 回答「目标怎样工作」；本页回答「小票到了哪、还差什么」。
- runtime 小票进 main，只表示那张票的代码在默认分支上；不证明 M1～M11 已具备完整作者能力，也不证明 852 条语义测试已执行。
- 后续产品票仍要回写追踪表并引用需求 ID；不能用本页替代测试与直接代码证据。

来源：Issue #27 路牌刷新；原 PR-C 页按工单 5 已合并事实改写，差距语义保留。
