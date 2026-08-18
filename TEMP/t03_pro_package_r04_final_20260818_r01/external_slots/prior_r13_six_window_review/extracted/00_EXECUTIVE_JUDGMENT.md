# R13 六身份阶段性全局深审｜执行判决

- 审查身份：外部总设计审查，只读顾问
- 审查对象：`CONTROLLER / T03 / A / B / C / D` 六个独立身份
- 证据冻结点：回包所附材料截至 2026-08-18 05:44（Asia/Shanghai）
- 总判决：`GLOBAL_REVIEW_COMPLETE__B_ACCEPTED_NARROW__A_T03_BLOCKERS_LIVE__C_FROZEN_CANDIDATE__D_CURRENT_BYTE_REPLAY_REQUIRED`
- 权限：本回包只提供建议；没有执行、训练、生产、正式合同修改、R13 修改、Gold 修改、上传或作者真值写入权限。

## ✅ 一句话结论

当前不是“六窗一起继续冲”的时点。**B 的 M5 唯一事务 writer 可以窄收口；A 的章节 revision 与 T03 的未决发现仍是结构性阻断；C 的 R19＋R21 只够冻结为实验规则族；D 的 4 项机械 PASS 必须在 B 最新正式字节上重放；总控应先补共享页面协议。** B、C 有意空闲，比制造重叠施工更安全。

## 本轮最重要的八个判断

### 1. B 是当前唯一拿到“正式字节＋强机械回归”的工作窗，但 PASS 范围很窄

B 已把旧 M5 确认、驳回、改判与改写后采纳统一到 `factstore → planstore transaction coordinator`；新 writer 20/20、定向 83/83、相邻 178/178、故障注入 8 点、旁路 writer 0。这个证据足以接受 `M5_UNIFIED_FACT_WRITER_PASS`。它只证明 facts 写入口、RE stale 与并发／恢复纪律，不证明暗稿签字、自动开下一章、关章、整个 M8 或产品主循环完成。

包内证据：
- `03_upstream_evidence/TEMP/t03_parallel_r13_m8_planstore_20260815_r01/outputs/m5_unified_fact_writer_r01/M5_UNIFIED_FACT_WRITER_RESULT_20260818_R01.md`
- `03_upstream_evidence/TEMP/t03_parallel_r13_m8_planstore_20260815_r01/outputs/m5_unified_fact_writer_r01/RESULT.json`

### 2. D 的 4/4 仍是有效历史证据，但不再是“当前字节已验证”

D 的 READY-01～04 在运行时使用了旧 `C4_FACT_QUERY.md` SHA `5c190819…` 和旧 `store.py` SHA `1e914557…`；本包当前正式字节分别是 `0e8f282e…` 与 `a2d944a7…`。四张夹具都读取了 `store.py`，READY-03／04 还直接依赖 C4。B 的变更不等于 D 已失败，但使 D 的状态必须收窄为：

`HISTORICAL_MECHANICAL_PASS__CURRENT_BYTES_UNVERIFIED`

因此 D 下一步不是扩新接缝，而是做一次零 API、同夹具、同断言、带差分说明的当前字节重放。

包内证据：
- `03_upstream_evidence/TEMP/t03_m1_m11_ready_seam_batch_20260818_r01/results/fixture_manifest.json`
- `03_upstream_evidence/TEMP/t03_m1_m11_ready_seam_batch_20260818_r01/SEAM_TEST_SUMMARY.md`
- `02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`
- `02_current_route/novel-mvp/mvp/store.py`

### 3. A 的 blocker 成立，而且是产品语义／合同 blocker，不是普通实现 bug

A 复现了两个 WRONG_SUCCESS：修改后的同章重导被当成 `c01 + c02` 两章；旧 quote 已从新版消失，旧 confirmed fact 仍被 M6 查询。当前 C1、C4、store、factstore、ask、check、planstore 都没有 stable chapter lineage、current revision、stale confirmed fact 或 revision waterline。B 改动后应重放这两个反例，但 blocker 本身仍存在。

推荐 A 只做 TEMP 合同设计和当前字节重基线，不直接往 `store.py` 加万能 `rev` 字段。章节 revision 的权威 owner、正式枚举和迁移属于 `CZ_EXPLICIT_APPROVAL_REQUIRED`。

包内证据：
- `03_upstream_evidence/TEMP/m1_m4_chapter_revision_audit_20260818_r01/RUN_REPORT.md`
- `03_upstream_evidence/TEMP/m1_m4_chapter_revision_audit_20260818_r01/MECHANICAL_PROBE_RESULTS.json`
- `03_upstream_evidence/TEMP/m1_m4_chapter_revision_audit_20260818_r01/CONTRACT_GAP_MATRIX.md`

### 4. T03 的“逐字安全”与“发现精度失败”完全兼容

T03 已把模型权力压到只选段号，程序逐字回捞，实体／actuality 改写 0、真值写入 0。这证明运输与权限更安全。它没有证明 C3 发现可用：未见完整送达只有 `6/11`，另 `5/11` 只是部分；普通负控误触 `19/55`。`24/24` 只是 DEV 项进入待看范围，不是语义 Recall。

所以正确表述是：**C4 可以逐字接住被选材料，但 C3 尚不能稳定决定哪些非连续段落合成一个未决，也不能稳定识别已闭合反证。** 不冻结 C3/C4，不进接口施工。

包内证据：
- `03_upstream_evidence/TEMP/v0_c3_unresolved_discovery_stage_20260818_r01/STAGE_RESULT.md`
- `03_upstream_evidence/TEMP/v0_c3_unresolved_discovery_stage_20260818_r01/FINAL_RECEIPT.json`
- `03_upstream_evidence/TEMP/v0_c3_unresolved_discovery_stage_20260818_r01/UNSEEN_SEMANTIC_EVALUATION_R01.json`

### 5. C 的 R19＋R21 可以并成实验规则族，REAL-03 必须保持独立

可保留的共同候选只有：

- R19 actuality：未来计划／投影不得冒充当前已发生；
- R21 budget：先保硬义务，再按剩余预算取舍 SHOULD／MAY，不让支持材料挤爆硬上限。

R21 豆包 7/7、DeepSeek 6/7；两模型预算失败 0。DeepSeek REAL-03 “邀请尚未接受”遗漏是独立 unresolved-state 失败，不能被预算 PASS 吞掉。R20 DeepSeek 只有 2/7 完成，也不能回填成整卷结论。正式 C9 仍不存在。

包内证据：
- `03_upstream_evidence/TEMP/t03_parallel_r13_m11_context_packer_20260818_budget_discipline_long_stage/03_COMPARISON_AND_DIAGNOSIS.md`
- `03_upstream_evidence/TEMP/t03_parallel_r13_m11_context_packer_20260818_budget_discipline_long_stage/04_RULE_FAMILY_CLOSEOUT.md`
- `03_upstream_evidence/TEMP/t03_parallel_r13_m11_context_packer_20260818_budget_discipline_long_stage/02_EXECUTION_LEDGER.md`

### 6. M9、M10、M11 不能都写成“等待上游”

- M9：C5 未落、产品未建，主要是模块本体缺口；需要稳定的 C4／planstore 读取身份后再施工。
- M10：C8 未落、产品未建，主要是模块本体缺口；V0 场景卡投影并不必然等待 A/T03 全部完成。
- M11：C9 未落、产品未建，同时真实等待 A 的 revision 水位线、T03 的 unresolved 对象身份和现行 planstore 读取合同。它才是集中接缝。

把 M9/M10 都写成“被 A/T03 阻塞”，会隐藏真正欠的是模块自身设计、合同与实现。

包内证据：
- `02_current_route/novel-mvp/ARCHITECTURE.md`
- `02_current_route/novel-mvp/design/REVIEW_OVERVIEW_DESIGN_R03.md`
- `02_current_route/novel-mvp/design/SCENE_CARD_EXPORT_DESIGN_R01.md`
- `02_current_route/novel-mvp/design/CONTEXT_PACKER_DESIGN_R01.md`

### 7. “一个共享 ChatGPT 页面”只能做不可信顾问通道，不能当身份隔离或授权系统

现协议有 `PAGE_LEASE_ID`、`DISPATCH_SEQ` 和 SHA 校验，方向正确，但仍有四个高风险缺口：

- 包外原件 SHA 与脱敏运输 SHA 是两套字节，单 SHA 规则会误隔离合法材料；
- 状态机缺 `EXPIRED / ABORTED / SUPERSEDED / QUARANTINED`，人工发送或回复丢失会死锁；
- 同一页面的旧上下文可污染新窗口，页面本身不是真正隔离边界；
- 顾问文字里的“通过／建议执行”容易被误读成授权。

必须加双 SHA＋转换回执、租约 TTL、严格 instruction epoch、能力矩阵、exactly-once 路由回执与冷启动规则。最强反对意见仍成立：**同一持久页面无法证明六身份无串线，只能降低概率。**

包内证据：
- `01_current_truth/TEMP/external_review_handoffs_20260818_r01/chatgpt_pro/05_SHARED_PAGE_DISPATCH_PROTOCOL.md`
- `_route/LOCAL_PATH_REDACTION.json`
- `01_current_truth/TEMP/external_review_handoffs_20260818_r01/chatgpt_pro/WINDOW_EVIDENCE_INDEX.json`

### 8. 下一阶段只开四条，B 与 C 有意空闲

| 身份 | 建议 | 原因 |
|---|---|---|
| CONTROLLER | RUN | 补共享页面协议与路由模拟，TEMP 独占写集 |
| T03 | RUN | 离线做非连续证据束＋已闭合反证；新 Gold/API 前硬停 |
| A | RUN | 当前字节重放＋章节 revision 最小合同候选，TEMP 独占写集 |
| B | IDLE | M5 writer 已窄收口；下一步触及暗稿／关章开放语义 |
| C | IDLE | 冻结 R19＋R21；正式 C9 需要 A/T03/D 先到新停点 |
| D | RUN | 在 B 最新字节上重放四接缝并增加 writer 接缝回归 |

## 需要 CZ 明字的事项

以下全部标记为 `CZ_EXPLICIT_APPROVAL_REQUIRED`：

- Gold、盲参考、阈值或评测集正式身份变化；
- 正式 C1/C3/C4/C6/C9、PLAN_LEDGER 或其他正式合同修改；
- R13 正文、产品代码、生产配置、训练、模型供应商、费用、上传；
- 暗稿签字、自动开下一章、关章、章节 revision 权威 owner 与迁移；
- 作者真值写入或任何跨窗口写集合并。

## 明确不成立的结论

- ❌ T03 未见 `6/11` 完整送达不是通过。
- ❌ C 的 `7/7 + 6/7` 不是正式 C9，也不是“两模型全通过”。
- ❌ D 的 `4/4` 不是合同冻结，更不是当前字节已验证。
- ❌ B writer 统一不等于暗稿、关章或自动下一章获授权。
- ❌ M1～M11 “都有方向”不等于都能施工或都已完成。

来源：本审查包内四份硬边界、`WINDOW_EVIDENCE_INDEX.json`、当前正式字节与六身份回执。
