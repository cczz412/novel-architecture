# 风险与反方审查

审查身份：ADVISORY_ONLY  
判决：GREEN_SURFACE_CAN_HIDE_AUTHORITY_STALE_AND_IDENTITY_FAILURES

## 风险排序

| Risk ID | 严重度 | 表面全绿 | 实际危险 |
|---|---:|---|---|
| R-01 | P0 | C11 EG-01 与 D INITIAL 票 PASS | INITIAL 没有包内完整 command/writer C10 交叉门，坏 r1 可能从 ledger/migration 入口绕过 |
| R-02 | P0 | RESTORE reactivation 5/5 PASS | historical identity_revision_no 可不存在，helper 仍可能只看 material id/current role/source |
| R-03 | P0 | C1/C4/C6 schema examples 9/9 | 各对象自己合形，不等于 ref、SHA、anchor 和 current pointer 彼此相等 |
| R-04 | P0 | facts/RE 都有 stale 文字 | basis pin 不在 C11 atomic write group；旧 pin 仍可向 M8 提供“ok”依据 |
| R-05 | P0 | 同一 lock/transaction 设计完整 | revision commit 与 fact admission 的 revision-aware runtime 尚未施工，并发串行只是合同要求 |
| R-06 | P0 | C9 owner closure PASS 21/21 | formal C9=false、packer/consumer 无、evidence recall OPEN；M8 仍直读 facts |
| R-07 | P1 | planstore r07 正式冻结 | 落盘仍 plan-v2，old reader 无明确 r07 判别，可能忽略 revision ref |
| R-08 | P1 | fact admission 有 current gates | quote 只要求存在而非唯一；C3 可空 quote；candidate key owner 未声明 |
| R-09 | P1 | C6 source_revision_state 有 CURRENT/STALE | enum 可被写入自报，current route 没有证明 reader 与 C11 current 比较 |
| R-10 | P1 | C10 validator 总体 PASS | Title 机器标签仍 NOT_IMPLEMENTED，自动路由可错误降级正式 adoption；Tags 则相反，合同存在但产品未实现 |
| R-11 | P0 | R03 route consistency 25/25 | 它冻结的是旧“C10 双锁未应用”身份；作为 current route 使用会复活旧候选 |
| R-12 | P0 | 外审报告写 RUN/PASS | 顾问文本无 CZ 权限；执行会形成权限升级 |
| R-13 | P0 | 去 fence 后 JSON 可解析 | 事后格式修理会改变实验身份，并可能掩盖真正语义尚未评测 |
| R-14 | P1 | D 最终 34/34 | 首轮 33/34 曾因 harness 静态检查范围不足产生假阴性；绿灯证明指定断言，不证明覆盖完整 |

## 反例 1｜INITIAL 设置材料直接成为 r1

### 表面理由

A 回执与 D 票都写 INITIAL/REPLACE current C10 gate PASS。

### 反例

构造一条 schema 合形的 C11 ledger r1：

- change_kind=INITIAL；
- content_ref 指某 C10 span；
- origin_material_ref 指 Setting 或 Candidate material；
- 不经过 CHAPTER_REVISION_COMMIT_ACTION，因为 action 只允许 REPLACE/RESTORE。

validate_ledger 不接 material_records，schema 也无法跨文件判 current role。包内 EG-01 只验合法 Chapter 正例，不能证明这个入口被拒。

### 风险

材料身份权被 ledger creation/migration writer 越权，非 Chapter 进入 C1/current chapter。

### 最小防线

A 的 fail-first 任务必须找到唯一 initial writer，并让坏 r1 在首次持久化前拒绝；找不到唯一入口就保留 OPEN。

证据：

- 02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/narrow_replay_ledger.json

## 反例 2｜RESTORE 复制了不存在的历史 identity revision

### 表面理由

RESTORE lineage 与 current reactivation 两道门都通过窄重放。

### 反例

历史 revision 的 origin_material_ref 写 material_unit_id=MU-R1、identity_revision_no=999；当前 C10 record 只有 identity revision 1/2，最后一条仍 CONFIRMED+CHAPTER，source ref 未变。validate_restore_gates 读取 material id 并以 require_referenced_revision_is_current=false 调 helper，没有证明 999 存在。

### 风险

历史来源链伪造仍能被 current gate“洗白”，审计无法回到当时的 authority。

### 最小防线

同时验证 historical revision 存在和 current reactivation；不能二选一。

证据：

- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md

## 反例 3｜C4 confirmed 的 ref 与 anchor 指向不同章

### 表面理由

C4 v1 有 chapter_revision_ref、VERIFIED anchor 和 strict schema。

### 反例

让 top chapter_id=c01，chapter_revision_ref=c01/r2，anchor_ref=c02/r7；三个对象分别都满足形状。C11 schema 没有跨字段 equality。consumer_allows 的机械 probe 只看 status=confirmed，不检查 anchor_state/current ref。

### 风险

M6/M8/M11 将一条形式上 confirmed 的事实当 current truth，而实际证据属于另一章或旧版。

### 最小防线

current truth reader 必须联合校验 top id、revision ref、anchor ref、ledger current、C1 text SHA 与 slice SHA。

证据：

- 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py

## 反例 4｜事实已 needs_recheck，规划 pin 仍为 ok

### 表面理由

C11 revision commit 会让事实 needs_recheck、RE stale，actual 不再支持。

### 反例

planstore basis_pin 只存 fact id 和 pin_status；C11 原子组与 receipt writes 没列 pin。若 f001 转 needs_recheck，但 pin 未同事务转 needs_recheck，M8 的 planning constraint 仍可能展示为有效依据。

### 风险

旧证据通过另一种引用对象继续驱动规划，形成 stale 传播漏口。

### 最小防线

CZ 明确 pin 是 read-time 派生还是 revision commit write effect；两者择一并提供验收，不能依赖“RE 已 stale”旁推。

证据：

- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md

## 反例 5｜revision commit 与 facts admission 并发

### 表面理由

两个合同都要求 current refs、同一 .planstore.lock 和 all-before/all-after。

### 反例

事务 A 与 B 都读 c01/r1：

- A 准备 commit r2，并把旧 fact/RE stale；
- B 准备用 r1 reconciliation candidate 接纳新 confirmed fact；
- 若 B 的现役 v1 路径或 revision product writer 没真正复用同一 lock，B 可在 A 后写入 r1 confirmed fact/active RE。

### 风险

每个事务单独 PASS，组合后产生 stale confirmed 与第二 actual support。

### 最小防线

D 单场景必须做受控并发，证明后提交者在持锁后重读 current，而不是只校验进入函数前的 snapshot。

证据：

- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md

## 反例 6｜旧 plan reader 静默忽略 r07

### 表面理由

PLAN_LEDGER r07 写 old reader 应 fail closed。

### 反例

落盘 schema 字符串仍是 plan-v2；没有独立 r07 version marker/schema 随包提供。一个宽松 r06 reader 可能忽略新增 chapter_revision_ref，继续按 chapter_text_sha256 或 fact refs 计算 actual。

### 风险

旧 RE 在新章 revision 后仍支持 actual，或 reader 无法判断需要迁移。

### 最小防线

升明确的序列化版本或提供可机械判别的 feature/version marker 与 strict reader negative fixture。

证据：

- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md

## 反例 7｜重复 quote 被任意锚定

### 表面理由

事实准入要求 quote 逐字存在，成功后生成 VERIFIED anchor。

### 反例

同一句在 C1 r2 出现两次；action 只有 fact_candidate_refs，没有显式 anchor。RECONCILIATION_FACT_ADMISSION_ACTION 的硬门只写“逐字存在”，而 C4 说明要求唯一命中。弱实现可能使用第一次 index。

更差的情况是 C3 quote 为空串：C3 人读合同允许空，空串“存在”于任何文本，但无法形成合法非空 anchor。

### 风险

confirmed fact 获得表面 VERIFIED、实际不可唯一复现的证据。

### 最小防线

准入必须要求 nonempty unique match，或 action 携带受验证的 exact anchor candidate；candidate stable key 也必须有明确 owner。

证据：

- 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md
- 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md

## 反例 8｜C6 自报 CURRENT

### 表面理由

C6 v1 有 chapter_revision_refs 和 source_revision_state。

### 反例

旧 r1 报告携带 source_revision_state=CURRENT；schema 只检查 enum，不比较 C11 r2 current。check.py 又明确尚未施工 v1。

### 风险

UI 或高影响 consumer 只看存储字段，旧报告仍显示绿色。

### 最小防线

source_revision_state 必须由读取端派生并覆盖/拒绝自报值；无 reader receipt 时只能显示 historical/unknown。

证据：

- 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json

## 反例 9｜旧候选 route 复活

### 表面理由

R03 route consistency 25/25，47/47 SHA 匹配。

### 反例

它明确冻结 validator f27008…、C10_DUAL_LOCK_NOT_APPLIED，并标 DRAFT_NOT_EXECUTABLE。R04 current truth 已确认 aeac1c…为正式。若自动化只按 consistency PASS 选 route，会回退现役正式身份。

### 风险

旧 SHA 锁、旧 blocker 与旧窗口姿态被重新当 current，后续包继续错误传播。

### 最小防线

route consumer 先验证 identity/current epoch，不以内部一致性替代时效性。

证据：

- 03_upstream_evidence/TEMP/t03_pro_review_route_final_snapshot_20260818_r01/PRO_ROUTE_CANDIDATE_R03.json
- 03_upstream_evidence/TEMP/t03_pro_review_route_final_snapshot_20260818_r01/ROUTE_CONSISTENCY_CHECK_R03.json
- 01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md

## 反例 10｜顾问建议越权

### 表面理由

上一轮外审给出 SHOULD_RUN、writeset 和 WINDOW_INSTRUCTIONS，看起来像可执行任务。

### 反例

RETURN_INTAKE_RECEIPT 和 LOCAL_TRIAGE 都明确：外审是 advice only，没有正式合同、产品、API、Gold、R13、Notion、Git 或作者真值权限；本地停点可覆盖旧建议。

### 风险

一个窗口用外审 RUN 当成 CZ approval，开始正式施工或调用模型。

### 最小防线

路由层必须分开 recommendation 与 authorization；没有当前 CZ token/指令，RUN 只能保持建议。

证据：

- 04_external_reviews/prior_r13_six_window_review/RETURN_INTAKE_RECEIPT.json
- 04_external_reviews/prior_r13_six_window_review/LOCAL_TRIAGE_R01.md
- 04_external_reviews/prior_r13_six_window_review/extracted/04_NEXT_LONG_STAGE_PORTFOLIO.md

## 反例 11｜格式修理掩盖能力问题

### 表面理由

豆包/Flash 围栏去掉后都可能解析，似乎只差一行 normalizer。

### 反例

本轮 frozen route 只允许 Flash adapter。事后给豆包同样处理会改变注册规则；即使 shared validator 通过，也只证明 shape，不产生 span Recall、bundle Recall、precision 或 model ranking。

### 风险

团队把运输修复写成模型能力完成，随后错误启动 C3/C4 或生产。

### 最小防线

保持本轮 HANDSHAKE_FAIL/NO_VERDICT；未来 adapter 政策只能在新 identity 调用前冻结。

证据：

- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json
- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json

## 反例 12｜绿 harness 的覆盖盲区

### 表面理由

D 最终 5/5、34/34、83/83。

### 反例

首跑 33/34 是 harness 只检查外层函数源码，漏掉 helper 中的委托；修正静态检查范围后才变 34/34。这个处理合规并有留痕，但它说明断言通过依赖 harness 观察面。

### 风险

未来把 34/34 写成“无其他绕门”，忽略未被断言枚举的 INITIAL/migration/cross-object 问题。

### 最小防线

每次 PASS 都附测试覆盖声明和非结论；新增反例用新票，不改旧 fixture 追绿。

证据：

- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/CZ_ONE_PAGE_VERDICT.md
- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/SHA_RECEIPT.json

## 最强反对意见与回应

### “正式文字已经写全，机器门以后实现即可”

回应：可以把正式语义视为已冻结，但不能把它当 current product capability。当前 C1/C6/reconciliation/planstore 都明确产品待升级；对外状态必须分开写“合同已冻”与“runtime 未证明”。

### “D 5/5 足以接受全部 C10/C11 兼容”

回应：D 自己限定为五组指定机械验，并明确不是产品可用或合同冻结。INITIAL 唯一入口、historical revision existence、cross-object equality 与 pin/C6 propagation 不在同一证明范围。

### “C9 先做 runtime，缺 owner 以后补”

回应：task scope、budget、actuality、obligation 与 evidence recall 决定哪些材料被装入；先写 runtime 会把输入顺序、缺省值或 M11 推断固化成隐藏产品语义。

### “旧报告保留 CURRENT 只是展示问题”

回应：C6、RE、pin 和 C9 都会影响规划/actual/高影响判断。没有 current gate 的展示字段会成为事实上的授权信号，不能只按 UI bug 处理。

## 风险底线

三条不能为速度牺牲：

1. 非 Chapter、计划、投影、模型意见和旧证据不能获得 current truth 权力；
2. current/stale 必须由唯一真源和可回验等式派生，不能由投影自报；
3. 顾问 PASS、机械 PASS、运输 adapter 和 owner matrix 都不能自生执行权限或语义能力。

来源：本审查包内四层材料。
