# T03 握手与 C9/M11 runtime OPEN

审查身份：ADVISORY_ONLY  
判决：T03_SEMANTIC_NO_VERDICT__C9_DECLARED_DIRECTION_ONLY__RUNTIME_AND_RECALL_OPEN

## 1. T03 证据账

### 旧八次能力批次

| 项 | 当前值 |
|---|---|
| calls | 8 |
| raw responses | 8 |
| sealed candidates | 0 |
| semantic verdict | NO_VERDICT |
| Recall / Precision | 未产生 |
| ranking | 未产生 |
| C3/C4 qualification | 未产生 |
| retries | 0 |

原因有两类：豆包输出的 identity 与 validator 的未公开固定常量不一致；Flash 输出 Markdown JSON fence，冻结 runner 不直接解析。诊断性去 fence 或检查可解析形状，不得补 seal 或能力成绩。评分表中的 0 只代表没有合格评分对象，不是语义值为 0。

证据：

- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/STAGE_RESULT.md
- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json

### 新两次合成输出握手

| 路线 | observed transport | route policy | shared validator | 正确判定 |
|---|---|---|---|---|
| Flash | 精确单层小写 json fence | 允许 Flash fence adapter | reached / PASS | HANDSHAKE_PASS |
| 豆包 | 精确单层小写 json fence | 不允许豆包 fence adapter | not reached | HANDSHAKE_FAIL |

两边观察到的外层格式相同，结果差异来自冻结运输策略，不来自语义内容裁决。Flash 的 PASS 也不证明它原生遵守裸 JSON；豆包的 FAIL 也不证明它不能完成语义任务。

证据：

- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/STAGE_RESULT.md
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json

### 当前禁止结论

- 不得产生 Recall、Precision、F1 或能力总分；
- 不得排列豆包与 Flash；
- 不得宣布 C3/C4 资格；
- 不得宣布生产可用；
- 不得把 Flash 写成 native naked JSON compliant；
- 不得把豆包写成 semantic failure；
- 不得从旧 raw 事后修格式后补录预注册成绩；
- 不得自动发第三次调用或开启新能力批次。

当前治理回执明确 third_call_authorized=false、ability_batch_started=false。

证据：

- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json
- 01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md

## 2. 格式修理不能掩盖能力问题

格式 adapter 的安全用途是：在调用前冻结、供应商范围明确、转换逐字可审计，并且 adapter 只改变运输外壳。它不能：

1. 在看到 raw 后临时改变允许供应商；
2. 让未到 shared validator 的路线获得 validator PASS；
3. 把 adapter PASS 当语义 PASS；
4. 把旧能力 raw 重新命名为新实验；
5. 把身份披露缺口归咎于模型。

若未来 CZ 决定统一 fence policy，必须使用新实验 identity、预先冻结的 prompt/validator/adapter 与新调用帽；本轮 raw 只能保留诊断身份。

证据：

- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/STAGE_RESULT.md
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/STAGE_RESULT.md

## 3. C owner closure 到底关闭了什么

### 已关闭

| 领域 | 当前结论 |
|---|---|
| C4 source owner | M4/M5 作者确认与 factstore |
| plan source owner | planstore |
| C9 声明 producer | M11 候选 |
| 声明 consumer | M8 |
| 反写权限 | C9/M11 不得改 C4、planstore 或作者真值 |
| 缺输入处理 | M11 候选输入门 fail closed，不接管上游 owner |

证据：

- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/final_validation_receipt_v2.json

### 仍 OPEN

| 字段／接缝 | 当前 owner/runtime | 影响 |
|---|---|---|
| task_id / task_actuality_scope | 正式唯一 owner 未分配；runtime producer 无 | M11 不能推断任务边界 |
| budget_tokens | O1/config owner 未冻结 | M11 只能守 cap，不能自定 cap |
| token_estimator_ref / per-item estimate | owner/runtime 无 | 预算总数不可复算 |
| actuality_class mapping | 统一 mapping owner 无 | C4 与 plan 语义不能由 M11 重写 |
| obligation_tier / selection_rank | owner 无 | 不得把相关性偷偷升 HARD，也不能用输入顺序当排名 |
| unresolved policy | OPEN_NO_DEFAULT | 不能把 unknown/未检索/未发生混为一类 |
| evidence recall | OPEN_NO_DEFAULT | 不能声称缺料可正式回捞 |
| runtime assembler | mvp/packer.py 不存在 | 没有 C9 producer |
| runtime consumer | mvp/plan.py 直接读 facts | M8 没走 C9 lineage |
| C9→C7 lineage | 未实现 | 无法证明规划题卡使用了哪一包、遗漏了什么 |

证据：

- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/STAGE_FINAL_CAPSULE.txt

## 4. 为什么 M8 不能自称已有正式上下文包

PLAN_LEDGER 的接线表把 C9 写成“尚未冻结”的候选，并承认 M11/runtime 尚未建立。C owner closure 又证明现役 plan.py 直接读 facts，绕过 C9。因此当前 M8 的诚实状态是：

- 可以按现役路径读取 facts/planstore；
- 不能声称经过正式 C9 的 actuality 过滤；
- 不能声称预算 HARD/SHOULD/MAY 已由正式 owner 计算；
- 不能声称携带 chapter revision waterline；
- 不能声称有 omission/coverage receipt；
- 不能声称 evidence recall 可用；
- 不能声称 M8 输出可回到 C9→C7 lineage。

证据：

- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md

R13 的“共同前提必须加载、执行包最小充分＋可扩张、缺料回捞”仍是有效产品钢线；它描述目标，不是当前能力证明。

证据：

- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/07_GLOSSARY.md

## 5. T03 与 C9 的相邻关系

T03 负责判断输出合同/未来候选发现实验是否形成合格对象；C9/M11 负责把已经有正式身份的材料装进任务包。两者不能互相补洞：

- transport adapter 不能定义 unresolved 对象；
- M11 不能从原文缺失推断“未发生”；
- budget PASS 不能补 evidence recall；
- C9 包装不能把 T03 NO_VERDICT 变成正式 C3/C4；
- M8 直接读 facts 不能冒充 C9 consumer。

证据：

- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json

## 6. 当前建议

T03：INTENTIONAL_IDLE。没有第三次调用授权，也没有新能力批次授权。  
C：INTENTIONAL_IDLE。runtime 施工和 recall owner 都需要正式合同/产品权限与 CZ 明字；重复 owner closure 没有新增价值。

若以后重启，触发条件至少是：

1. CZ 冻结 transport adapter policy 与新调用帽；
2. C9 输入 owner、unresolved 与 evidence recall owner 明确；
3. chapter revision waterline 与 planstore 落盘版本明确；
4. producer、consumer、lineage 与 fail-closed 验收合同先于模型调用。

来源：本审查包内 T03、C owner closure、PLAN_LEDGER 与 R13。
