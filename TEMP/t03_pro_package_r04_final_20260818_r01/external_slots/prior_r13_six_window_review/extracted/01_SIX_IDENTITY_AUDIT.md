# 六身份独立审查

## 审查方法

身份按 `WINDOW_EVIDENCE_INDEX.json` 的 `WINDOW_ID` 与绑定回执判定，不按目录前缀、旧线程标题或历史窗口名猜测。每个判决分开看五层：

1. 身份和写集是否对；
2. 机械证据是否成立；
3. 语义结论是否越界；
4. 是否仍对应当前正式字节；
5. 是否被写成了授权、产品能力或正式合同。

包内依据：`01_current_truth/TEMP/external_review_handoffs_20260818_r01/chatgpt_pro/WINDOW_EVIDENCE_INDEX.json`。

---

## CONTROLLER｜总控

### 判决

`ACCEPT_WITH_PROTOCOL_NARROWING`

总控保持“协调与验收，不是产品施工线”的身份是正确的。它已经纠正过 A/B 写集冲突，也把普通 CLI 失败从治理停线降回普通实现问题，说明其职责边界基本健康。

### 证据支持什么

- 总控只写 handoff 与 route 配置；
- 早期 D 审计因 B 的 planstore SHA 漂移而等待，没有强行把不稳定材料写成 PASS；
- 本轮外审包明确保留六身份独立，不把总控当第六条产品线。

包内依据：
- `01_current_truth/TEMP/external_review_handoffs_20260818_r01/chatgpt_pro/02_SIX_IDENTITY_SNAPSHOT.md`
- `03_upstream_evidence/TEMP/t03_m1_m11_cross_pipeline_seam_audit_20260818_r01/VALIDATION_RECEIPT.json`

### 必须收窄的地方

1. 当前协议把单一 ChatGPT 页面当作可排队通道，但没有证明它能隔离六个身份的历史。
2. `WINDOW_EVIDENCE_INDEX.json` 记录本地原件 SHA；外发包有 25 个文件经过路径脱敏，包内 SHA 改变。协议若只认一个 `SOURCE_SNAPSHOT_SHA`，会把合法运输字节误判为旧 SHA 或篡改。
3. `governance/module_registry.json` 的 M00～M16 是另一套治理／研究编号，不能与产品 M1～M11 裸名互认。共享页面必须带 `MODULE_NAMESPACE`。
4. 总控不应把“ChatGPT 建议 RUN”转成执行票；只能路由给本地验收，再由当前权限决定。

包内依据：
- `_route/LOCAL_PATH_REDACTION.json`
- `02_current_route/governance/module_registry.json`
- `02_current_route/novel-mvp/ARCHITECTURE.md`

### 推荐姿态

运行一段完整的协议硬化阶段，只写 TEMP 候选和模拟回执，不修改正式协议／产品。正式采用标 `CZ_EXPLICIT_APPROVAL_REQUIRED`。

---

## T03｜C3 未决发现与 C4 送达

### 判决

`ACCEPT_FAILURE_VERDICT__NARROW_SAFETY_CLAIMS`

接受 `C3_C4_NOT_READY__UNRESOLVED_DISCOVERY`。不接受任何把“逐字回源 0 改写”扩成“精度已解决”或“11/11 已送达”的表述。

### 证据支持什么

- DEV：9/9 语义参考保留；普通负控误触 4/45；逐字改写 0；真值写入 0。
- 未见：完整 6/11、部分 5/11、缺失 0/11；普通负控误触 19/55；逐字改写 0；真值写入 0。
- 模型不再直接产命题、实体 ID 或 actuality 答案，程序从原书逐字回捞。
- 失败集中在跨段聚合、限定词完整性、缺失动作／状态、备选方案上下文和已闭合事项识别。

包内依据：
- `03_upstream_evidence/TEMP/v0_c3_unresolved_discovery_stage_20260818_r01/STAGE_RESULT.md`
- `03_upstream_evidence/TEMP/v0_c3_unresolved_discovery_stage_20260818_r01/FINAL_RECEIPT.json`
- `03_upstream_evidence/TEMP/v0_c3_unresolved_discovery_stage_20260818_r01/UNSEEN_REFERENCE_FREEZE_RECEIPT_R01.json`

### 分母与命名审查

- `24/24 program_wait_range` 只表示程序把 24 条已见项送进待看范围，不能写成语义 Recall。
- `6/11 semantic_full` 的分母是 11 条未见语义参考；另 5 条只是 partial。不能把“至少部分覆盖 11/11”偷换成完整通过。
- 回执字段名是 `negative_false_proposition_paragraphs=19`、`negative_controls=55`。当前包没有给出全部 55 条逐项人工判词，外审能核对汇总与冻结身份，不能独立重判每个负控。建议下一阶段把“负控段落数、负控命题数、被触发对象数”拆开登记，防未来分母含义漂移。

### 未证明的否定事实

T03 最危险的新错误不是模型改写，而是把“没有看到签字／接受动作”推成“未签／未接受”。安全合同只能在原文明确正向登记“尚未签、尚未接受、仍在考虑”时加载当前未决；若只是没看到完成动作，应标 `未检索／覆盖内未找到`，不能制造否定事实。这与 C 的 REAL-03 正向状态登记问题要分开：REAL-03 有明确当前状态支持，T03 某些缺失动作案例则需要区分 absence inference。

### 推荐姿态

停止同 Prompt 微调与模型扩榜，转做离线的“未决证据束＋闭合反证”表示／算法研究。新 Gold、未见集身份或 API 调用均标 `CZ_EXPLICIT_APPROVAL_REQUIRED`。

---

## A｜章节 revision、anchor 与 stale

### 判决

`ACCEPT_BLOCKER__REBASELINE_CURRENT_BYTES_REQUIRED`

接受 `BLOCKED_BY_CONTRACT_OR_DECISION`。机械反例强，且命中正式合同／产品语义红线。A 不能直接施工 revision。

### 证据支持什么

- 修改后的同章重导产生 `c01 + c02`；两条 admission 都 READY；
- 旧 quote 不在新版文字，旧 fact 仍 confirmed，M6 查询仍返回 1；
- identical reimport 安全停止、0 半写，但没有幂等 no-op 回执；
- C1/C4 没有 revision／stale 表达，revision API 不存在。

包内依据：
- `03_upstream_evidence/TEMP/m1_m4_chapter_revision_audit_20260818_r01/MECHANICAL_PROBE_RESULTS.json`
- `03_upstream_evidence/TEMP/m1_m4_chapter_revision_audit_20260818_r01/CURRENT_PATH_AUDIT.md`
- `03_upstream_evidence/TEMP/m1_m4_chapter_revision_audit_20260818_r01/CONTRACT_GAP_MATRIX.md`

### 需要收窄的地方

A 的探针早于 B 最终 writer 字节。B 改了 `store.py`、`factstore.py`、C4 与事务协调；所以“当前仍能精确复现两个 WRONG_SUCCESS”需要在最新字节上重跑。但当前 C1/C4 与运行时代码仍没有 `chapter_revision / lineage / needs_recheck / restore` 语义，结构性 blocker 并未被 B 隐式解决。

### owner 审查

- M1 拥有导入与 material identity；
- M4 拥有 confirmed facts 写域；
- planstore 拥有规划持久化事务；
- **跨模块 chapter revision 的权威 owner 尚未冻结。**

推荐不要把 owner 简化成“M1 全包”或“M4 全包”。较安全的候选是：章节 lineage／revision 由章节证据域 owner 持有，M1 只提出显式目标 chapter 的 revision action，M4/planstore/M6/M7/M9/M10/M11 作为带水位的消费者。正式选择仍是 `CZ_EXPLICIT_APPROVAL_REQUIRED`。

### 推荐姿态

先做当前字节重放，再做 TEMP 最小合同候选：显式 `target_chapter_id`、append-only revision、restore-as-new、stale fact 身份方案、锚点基准、消费者水位和多文件事务边界。不改正式件。

---

## B｜M5 facts 唯一事务 writer

### 判决

`ACCEPT_NARROW_PASS__INTENTIONAL_IDLE_AT_SEMANTIC_BOUNDARY`

B 的 M5 writer PASS 可以收口，不需要再补普通工程尾巴。下一步正好撞上暗稿／关章开放语义，应有意空闲。

### 证据支持什么

- 唯一 writer：`factstore.py::commit_facts_transaction_locked`；
- 兼容入口不再裸写 facts；
- confirmed→rejected 或被作者改写时，active RE 同事务 stale；
- rejected→confirmed 不静默复活旧 RE；
- stale action 写前拒绝；并发只允许一个提交；
- 20/20、83/83、178/178，8 点故障注入；无新增 M5/novel-mvp 回归。

包内依据：
- `03_upstream_evidence/TEMP/t03_parallel_r13_m8_planstore_20260815_r01/outputs/m5_unified_fact_writer_r01/M5_UNIFIED_FACT_WRITER_RESULT_20260818_R01.md`
- `03_upstream_evidence/TEMP/t03_parallel_r13_m8_planstore_20260815_r01/outputs/m5_unified_fact_writer_r01/RESULT.json`
- `02_current_route/novel-mvp/contracts/FACT_REVIEW_ACTION.md`

### 不能推出什么

- 不能推出暗稿算作者签字；
- 不能推出收工可自动开下一章；
- 不能推出关章合同已完成；
- 不能推出 M8 全部完成；
- 不能推出 revision stale 已解决；
- 不能推出 M5 UX、确认负担与批量审查已经可用。

### 旧窗口名／写集审查

B 的目录仍带 `m8_planstore` 历史前缀，但 `WINDOW_ID=B` 和最终回执明确它是 M5 facts writer 窄工程阶段。按硬规则应以 B 当前身份为准，不把目录名读成“M8 writer 统一”。

### 推荐姿态

`SHOULD_RUN=NO`。等待 A 的 revision owner／合同候选，以及 CZ 对暗稿／关章语义的明确决定。B 不应抢写 A、C 或 D 的 TEMP 写集。

---

## C｜M11 R21 预算规则

### 判决

`ACCEPT_EXPERIMENTAL_RULE_FAMILY__NO_FORMAL_C9`

接受 R21 预算变量的候选 PASS；收窄“跨模型通过”为“预算目标跨模型成立，但 DeepSeek 全卷仍有 1 个非预算硬失败”。

### 证据支持什么

- 同一 7 题真实卷，豆包 7/7，DeepSeek 6/7；
- 两模型预算失败 0；DeepSeek REAL-06 从 1950/1500 降到 1230/1500，硬组完整；
- 未来投影误载 0；无新增硬回归；
- REAL-03 当前未决状态遗漏继续存在，与预算变量无关；
- 14 次调用、重试 0。

包内依据：
- `03_upstream_evidence/TEMP/t03_parallel_r13_m11_context_packer_20260818_budget_discipline_long_stage/03_COMPARISON_AND_DIAGNOSIS.md`
- `03_upstream_evidence/TEMP/t03_parallel_r13_m11_context_packer_20260818_budget_discipline_long_stage/results/final_validation_receipt.json`

### 结构运输审查

Track A 原始输出仍有模型差异：豆包 7/7 是 Markdown fence，裸 JSON 0/7；DeepSeek 裸 JSON＋Schema 有效 7/7。Track B 使用冻结的 TEST_ONLY normalizer。这个结果说明规则语义候选可保留，但**产品解析器与正式 C9 的原始结构兼容尚未验证**。

包内依据：`03_upstream_evidence/TEMP/t03_parallel_r13_m11_context_packer_20260818_budget_discipline_long_stage/02_EXECUTION_LEDGER.md`。

### 推荐姿态

冻结 R19＋R21，不再追加预算 Prompt 或扩模型。C 有意空闲，等 A 给 revision waterline、T03 给 unresolved bundle 候选、D 完成当前字节重放，再进入正式 C9 设计入口。正式 C9、Gold、API、产品均为 `CZ_EXPLICIT_APPROVAL_REQUIRED`。

---

## D｜跨模块审计与四项机械验

### 判决

`ACCEPT_HISTORICAL_PASS__OVERTURN_CURRENT_BYTE_STATUS`

不推翻 D 当时的 4/4 机械结果；推翻“这些 PASS 已覆盖 B 最新正式字节”的隐含读法。

### 证据支持什么

- READY-01：C10→C1 原文无损、C2 可回拼、坐标分家、source 篡改失败关闭；
- READY-02：Intro/Setting/Title/Tags/Unknown 0 C1、0 M2；
- READY-03：C3→M4 extracted-only，M4 发号，上游不能抬权；
- READY-04：M4→M7 只读，rejected 排除，facts SHA 不变；
- 42/42 断言，外部 API 0。

包内依据：
- `03_upstream_evidence/TEMP/t03_m1_m11_ready_seam_batch_20260818_r01/SEAM_TEST_SUMMARY.md`
- `03_upstream_evidence/TEMP/t03_m1_m11_ready_seam_batch_20260818_r01/results/seam_test_ledger.json`

### 旧 SHA 审查

D 夹具：
- C4：`5c190819…`
- store：`1e914557…`

当前正式包：
- C4：`0e8f282e…`
- store：`a2d944a7…`

四张票都纳入了旧 store 字节，因此都要重放；READY-03／04 还必须核对 C4 差异。历史 PASS 不能抹掉，当前身份改成 `CURRENT_BYTES_UNVERIFIED` 即可。

### 机械／语义混读审查

D 自己明确把 5 个 actuality/unresolved/entity-scope 夹具标成 `SEMANTIC_UNJUDGED`。因此 READY-03 只能证明“无权限升级”，不能证明 T03 的语义发现正确。D 4/4 与 T03 未见失败并不冲突。

### 推荐姿态

运行一个完整重基线阶段：冻结当前 SHA→原四票重放→差分归因→增加 B writer 的 facts+RE 原子性与 M7 只读断言→全回归→收口。仍只写 TEMP。

---

## 六身份之间的兼容结论

| 组合 | 判断 |
|---|---|
| T03 × D | 兼容：D 证明机械不抬权，T03 证明语义选择不成熟 |
| A × D | 兼容：D 的非 Chapter 隔离不解决同章 revision；READY-01/04 正好暴露 revision 水位缺口 |
| A × B | 兼容但需排序：B 先稳定事实事务 writer；A 再设计 revision 触发的 stale／recheck，不应绕过 B writer |
| B × C | 兼容：B 管真值写；C 只管执行包候选。C9 未来只能读现行 facts/planstore，不得另开写口 |
| B × D | 需重放：B 改了 D 夹具所用正式字节 |
| T03 × C | 相邻但不同：T03 决定 unresolved 对象如何被发现／送达；C 决定已登记对象怎样进最小包 |
| A × C | 有真实等待：C9 必须携带 revision 水位或过期回执，否则会把旧章事实装进新包 |

来源：包内六身份回执、当前正式合同与实现。
