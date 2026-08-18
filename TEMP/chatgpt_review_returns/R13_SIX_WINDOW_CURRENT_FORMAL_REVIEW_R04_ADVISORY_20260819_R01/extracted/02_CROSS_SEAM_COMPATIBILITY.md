# 跨缝兼容审计

审查身份：ADVISORY_ONLY  
判决：FORMAL_SEMANTICS_IMPROVED__MACHINE_AND_RUNTIME_SEAMS_NOT_CLOSED

## 1. C10 eligibility × C11 INITIAL／REPLACE／RESTORE

### 总表

| 路径 | 已有门 | 尚存绕门／证明缺口 | 判定 |
|---|---|---|---|
| INITIAL | 正式文字要求唯一 C10 material、current identity、CONFIRMED+CHAPTER、source ref 全等 | action schema 没有 INITIAL；ledger schema/validate_ledger 不加载 C10；EG-01 只测合法正例，没有非 Chapter initial ledger 负例 | OPEN_MACHINE_ENTRY |
| REPLACE | action 强制 C10_SOURCE_SPAN＋origin ref；helper 要求 origin identity revision=current、C10 record 合法、current 可发 C1、source ref 全等；batch 坏项 0 写 | 产品 revision commit 尚未施工；schema 本身不能跨文件验证，必须保证所有 writer 都调用同一 precheck | CONTRACT_LOCAL_CLOSED__RUNTIME_PENDING |
| RESTORE_LINEAGE | target 必须同 stable chapter、真实旧 revision；title/text SHA/content ref 精确复制；新 origin ref 必须 null | ledger 初建/迁移若已带坏 origin，lineage 只会复制坏值；当前包没有 migration validator 的外部 C10 交叉证明 | PARTIAL |
| REACTIVATE_CURRENT | 由历史 material_unit_id 重读当前 C10 record；当前必须 CONFIRMED+CHAPTER；source ref 必须仍全等；legacy snapshot fail closed | helper 不检查历史 origin identity_revision_no 是否真实存在于 C10 chain；只要 material id 与 current source/role 合法，虚构历史 revision number 可能被忽略 | OPEN_HISTORICAL_REF_EXISTENCE |
| NO_CHANGE | candidate SHA 等于 current 时 0 写；同 operation id 同载荷回放、异载荷冲突 | NO_CHANGE 只比较正文 SHA；同正文、不同标题的 RESTORE/REPLACE 是否应产生 revision 没有单独语义说明 | CZ_SEMANTIC_CHOICE |

主要证据：

- 02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md
- 02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl

### INITIAL 的具体证明缺口

正式回执写“INITIAL／REPLACE 当前 C10 门 15 个正反例通过”，D 也把第二票命名为 INITIAL_REPLACE_CURRENT_C10_GATE。可是包内 validator 的接口关系是：

- validate_ledger(ledger, previous) 不接 material_records；
- validate_action(action, ledger, material_records) 只处理已有 ledger 的 REPLACE/RESTORE；
- EG-01 直接调用 validate_current_c10_eligibility 验一个合法 initial revision；
- EG-03～EG-08 的非 Chapter 负例都经 base_action，也就是 REPLACE 路径；
- schema 允许一条 ledger 自带任意合形 content_ref/origin_material_ref，无法证明 origin current eligibility。

所以当前可以接受“正式规则已写”，不能接受“INITIAL 所有 writer 已无法绕门”。这个结论不会推翻 A 或 D 的窄 PASS，只收窄其覆盖边界。

证据：

- 03_upstream_evidence/TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/RUN_REPORT.md
- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/narrow_replay_ledger.json
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py

### RESTORE 的 identity revision 语义

允许 historical identity revision 不等于 current 是合理的：C10 identity chain 可从 r1 到 r2，RESTORE 只需重读 material 的当前资格。但这不等于可以忽略 historical revision 的存在。建议的最小不变量是：

1. historical origin identity_revision_no 必须存在于同一 C10 record；
2. 该 revision 在历史提交时必须可证明为当时合法 Chapter origin；
3. reactivation 再独立检查当前最后 revision 仍为 CONFIRMED+CHAPTER；
4. 两者不能合并成“只看 current”或“只看 history”。

当前包只完整表达第 3 条和 source ref 全等，第 1/2 条没有可审计的机器门。

证据：

- 02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py

## 2. C11 revision 传播

### 传播表

| 消费对象 | 正式目标 | 当前清楚处 | 当前缺口／冲突 | 判定 |
|---|---|---|---|---|
| C1 | current revision 的唯一物化视图；id/ref/text/title 与 ledger current 一致 | 人读合同明确，C11 schema 有 v1 形状 | schema 不验证 id=ref.chapter_id、SHA(text)=ref SHA、ref=current；产品仍输出 v0-r01 | RUNTIME_OPEN |
| C2 | 从 current C1 切分并逐字段复制 revision ref | ref 字段与 C2 normalized offset/正式 anchor 分家 | schema 不验证 ref 等于 C1、end=start+len(text)；v1 产品升级状态未给结果票 | RUNTIME_OPEN |
| C3 | 继承 C2/C1 revision ref，只是 candidate | 权限边界清楚 | 人读表称 quote/seg 非必填，后文又要求 external v1 携带 seg；C11 schema 两者均 required；无跨对象 ref 校验 | CONTRACT_CONFLICT |
| C4 | confirmed 只有在 current revision 且证据可回验时才属 current truth；失败转 needs_recheck | status/recheck/anchor 形状与迁移规则已写 | schema 不强制 top chapter_id、chapter_revision_ref、anchor_ref 三者相等；consumer probe 只按 status 排除 needs_recheck，未检查 current/VERIFIED | MACHINE_GAP |
| C6 | 保存消费 refs，读取端与 C11 current 比较后派生 CURRENT/STALE | enum 与 legacy unknown 已写 | source_revision_state 可由输入直接声称；包内无 read validator。PLAN_LEDGER 接线表又用不存在于 C6 v1 的 source_commit_seq 说明过期 | CONSUMER_UNDECLARED |
| slot_mapping | 只绑 stable chapter_id，revision 变化保持 active | 语义清楚 | 无新增缺口；不得复制 revision truth | COMPATIBLE |
| RE | 必绑 current chapter_revision_ref/C1 SHA/fact basis/planned rev；revision commit 同事务 stale | r07 人读规则完整 | r07 产品待施工；落盘仍 plan-v2，旧 reader 无明确版本判别；旧 nonempty RE 迁移机制没有机器件 | RUNTIME_AND_VERSION_OPEN |
| basis_pin | 引用 fact，fact/revision 改变后 needs_recheck | PLAN_LEDGER 末尾边界提到 pin/recheck | C11 原子组与 writes receipt 只点 RE，不点 pin；pin 无 chapter revision ref，可能继续显示 ok | STALE_PROPAGATION_OPEN |
| facts admission | action/C1/candidate/RE/mapping 同 revision，失败 0 写 | v2 人读门清楚 | 产品仍 v1；quote 唯一性、C3 candidate key owner、receipt/schema 未在 current route 闭合 | RUNTIME_OPEN |

证据：

- 02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md
- 02_current_route/novel-mvp/contracts/C2_SEGMENT.md
- 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md
- 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md
- 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md

### 双重真源风险

C11 已正确声明章节历史唯一真源，C1 只存 current projection；危险来自实现阶段同时保存可独立改变的重复字段：

- ledger revision 保存 title、text SHA、content ref；
- C1 再保存 title、text、chapter_revision_ref；
- C4 再保存 chapter_id、chapter_revision_ref、anchor_ref；
- RE 再保存 chapter_ref、chapter_revision_ref、chapter_text_sha256；
- C6 再保存 chapter_revision_refs 与 source_revision_state。

这些重复是必要投影，不应删掉；安全条件是每次写入都由同一事务计算，读取时逐字段比 current，不允许某个投影自己的 CURRENT 布尔或 enum 成为第二 current pointer。C11 §7 给出正确方向，但 current route 没有一个联合 validator 或现役 product receipt 证明上述等式全部受控。

证据：

- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 03_upstream_evidence/TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/VALIDATION_RESULTS.json

## 3. stale、幂等、回退和并发

### stale

清楚的部分：

- stale expected current revision 拒绝；
- verified slice 唯一命中则 anchor 前进；
- 0 次/多次/legacy 无法双边唯一则 needs_recheck；
- needs_recheck 不供 M6/M8/M11；
- C6 旧 refs 应派生 STALE；
- RE 旧 revision/C1 SHA/fact basis/planned rev/mapping 任一旧就不得支持 actual。

证据：

- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md
- 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md

未闭合的部分：

- C4 confirmed 的 current/VERIFIED 判断没有统一 reader gate；
- basis_pin 没有明确进入 C11 atomic effects；
- C6 CURRENT 是可序列化字段，但读取端未落；
- C1/C2/C3 旧 projection 的失效处理没有 product receipt；
- C9 不存在，无法携带 revision waterline/omission/recall。

### 幂等

C11 action 对 operation ID 的同载荷回放、异载荷冲突和 NO_CHANGE 0 写规定清楚。planstore 也有 request SHA、commit log、rolled_back 后禁复用的规则。问题是：

- C11 receipt 的人读链接 CHAPTER_REVISION_COMMIT_RECEIPT.md 未包含在 current route，只有 schema 内的 receipt 形状；
- receipt 并未序列化每个跨 owner target SHA，只保存 write counts；
- reconciliation v2 的 operation receipt/schema 未包含在 current route；
- 跨 action family 是否共享同一 operation-id namespace 与 canonicalization 没有明确登记。

证据：

- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md
- MANIFEST.json

### 回退／恢复

语义层是清楚的：

- committed revision 不做物理 rollback；
- 内容恢复使用 RESTORE-as-new；
- 事务故障只恢复 all-before 或 all-after；
- 未知 SHA 进入 NEEDS_MANUAL_RECOVERY。

证据：

- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md

产品层仍未证明 C11 append、C1 view、facts、pin/RE、history/blob/receipt 均由同一个现役 coordinator 串行化。尤其 revision commit 与 reconciliation fact admission 若同时读 r1，必须由同一 lock 让后提交者重新检查 current；人读合同要求复用 .planstore.lock，但对应 revision-aware product 尚未施工。

证据：

- 02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md

## 4. 字段同名、含义漂移与隐含默认

| ID | 冲突／漂移 | 风险 | 证据 |
|---|---|---|---|
| F-01 | C10 identity_revisions、C11 revision_no、work_rev、plan object rev、outline_rev | 同名 rev 被错误互认，造成越权 current | 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md；02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| F-02 | C3 quote/seg 在人读表非必填，schema required | producer 与 validator 对字段形状分叉 | 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md；C11_CHAPTER_REVISION_LEDGER.schema.json |
| F-03 | C4 chapter_id、chapter_revision_ref.chapter_id、anchor_ref.chapter_id 可分别成形 | confirmed fact 可绑定不同章/版的证据 | 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md；C11_CHAPTER_REVISION_LEDGER.schema.json |
| F-04 | C6 source_revision_state 与 PLAN_LEDGER 所述 source_commit_seq | 一个合同按 chapter revision 过期，接线表又引用未声明字段 | 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md；02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| F-05 | plan-v2-candidate-r07 与落盘 plan-v2 | reader 无可靠语义版本水位，旧 RE 可能静默继续 | 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| F-06 | C10 Title adoption 已实现，但 validator 机器标签 NOT_IMPLEMENTED | 自动分诊可能把已落正式能力降级 | 02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md；validate_c10_intake_material_identity.py |
| F-07 | reconciliation fact_candidate_refs 无 C3 item ID owner | 弱实现可能用数组位置/局部字符串，重排后错绑 | 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md；02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md |
| F-08 | quote “存在”与“唯一命中” | 重复文本可能被任取一处生成 VERIFIED anchor | 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md；02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md |
| F-09 | C6 CURRENT 可写 enum，但语义上应由 reader 派生 | stale 报告可自报 CURRENT | 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md；C11_CHAPTER_REVISION_LEDGER.schema.json |
| F-10 | C11 writes 只有计数，未声明 projection receipt 内容 | 计数正确仍可能写错对象/错 revision | 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json；02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md |

## 5. C9/M11 对 M8 的兼容判定

当前没有可供 M8 正式消费的 C9 runtime：

- formal_c9=false；
- 没有 mvp/packer.py；
- mvp/plan.py 直接读取 facts；
- 真实 runtime consumer=NONE；
- task scope、budget、estimator、actuality class、obligation/rank 的 owner 不全；
- unresolved policy 与 evidence recall 均 OPEN_NO_DEFAULT。

因此 M8/规划链只能声称“直接读取现役 facts/planstore 的旧路径”，不能声称“经正式 C9 前提包选择、预算、遗漏回执和 evidence recall”。R13 对共同前提包的描述是产品钢线与设计目标，不是现役 C9 能力。

证据：

- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md

## 6. 建议

不直接修改任何正式文件。建议先用 A/D 两个 TEMP-only 负例阶段收证：

- A 证明 INITIAL 与 RESTORE historical identity revision 是否真正 fail closed；
- D 用一个 revision 变更场景验证跨对象 current 等式、pin/RE/C6 stale、并发与幂等。

若反例成立，再由 CZ 指定正式合同 owner、写集与版本策略。不要由 validator PASS、外审建议或当前文档链接自动产生修改权限。

来源：本审查包内当前 route 与上游回执。
