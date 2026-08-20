# ZERO API Fixture Manifest Rebase

- 报告身份：`ADVISORY_ONLY`
- 任务身份：`PILOT-R01_ZERO_API_FIXTURE_MANIFEST_REBASE`
- 日期：`2026-08-20`
- 本地执行前置：必须重新核对现役代码、合同和直接测试；本报告不产生施工、合同、API、模型、Gold、训练、生产、Git、Notion 或真实材料权限。

## ✅ 结论

旧蓝图的 **51 个家族**被展开为 **89 个单变量变体**。本轮真正需要执行 **20 次 0 API 运行**；其余 **69 行**只登记现有证据、复用案例、记录语义阻断或保留未来 API 卡。

| 口径 | 数量 |
|---|---:|
| 评测卡 | 15 |
| fixture 家族 | 51 |
| 展开变体 | 89 |
| 实际 0 API 运行 | 20 |
| 非运行行 | 69 |
| 复用现有测试变体 | 36 |
| 复用现有案例变体 | 5 |
| 复用合计 | 41 |
| 新正常 fixture 变体 | 12 |
| 预期失败：本轮要跑 | 8 |
| 预期失败：现有案例已复现 | 1 |
| 预期失败合计 | 9 |
| 语义合同阻断 | 24 |
| 未来 API、不执行 | 4 |
| 需要新备料的变体 | 20 |
| 可并行备料组 | 5 |

### 数量怎样读

- **复用数量有两层**：卡级纯复用为 2 张；变体级复用为 41 行，其中测试 36 行、案例 5 行。
- **需要新备料 20 行**：12 行目标正常通过，8 行目标保存当前预期失败。成对材料可以共用底稿，但基线和处理组仍是两行、两个 `variant_id`。
- **预计失败 9 行**：8 行本轮实际运行，另有 M9 rejected 污染案例已在现有 13 组合成案例中复现，不重复运行。
- **语义阻断 24 行**：没有唯一当前预期，不得用临时字段、枚举或 adapter 补齐。
- **M9 正常对照单列**：confirmed-only 正常回包与 extracted／零 confirmed 危险回包没有挤在同一行。

## 边界与来源审计

- 输入 ZIP：`chatgpt_review_route_r13-six-return-component-design-and-content-pilot-pro-two-window-20260819-r01_20260820_000334.zip`
- ZIP SHA256：`8ca1e3f021fc3077ed2be4088dd02c269156301c4870a1a226f1ac6fa2a74092`
- 解包文件：231；顶层 manifest 登记业务成员：229。
- `SHA256SUMS`：230/230 匹配，失败 0。
- 当前代码身份按本地分诊记录：`codex/module-runtime-foundation-20260819-r01@1daed37`。
- 本报告没有运行产品测试；现有测试只作为附件中的直接证据登记。本地 Agent 执行前必须在现役仓库重跑。
- 真实小说：0；Gold：0；API：0；模型调用：0；重试：0；seed registry：未创建。

技术事实优先顺序：
1. user current prompt
2. current code and direct tests in 02_current_route
3. formal contracts in 02_current_route
4. current truth and direct synthetic outputs
5. local triage
6. old Pro plans and external reports

## 15 张卡当前事实对账

| 卡 | 主题 | 卡级结论 | 家族 | 变体 | 实跑 | 测试复用 | 案例复用 | 新 fixture | 预计失败 | 阻断 | API later |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CCE-A-M1-03` | 多格式、脏包、章数与静默丢失 | `NEW_ZERO_API_FIXTURE` | 4 | 11 | 4 | 7 | 0 | 3 | 1 | 0 | 0 |
| `CCE-A-M1-04` | current／已发布／工作稿身份与 owner | `BLOCKED_SEMANTIC_CONTRACT` | 3 | 7 | 0 | 5 | 0 | 0 | 0 | 2 | 0 |
| `CCE-A-M2-03` | 否定、条件、时间限定的切段差分 | `NEW_ZERO_API_FIXTURE` | 3 | 6 | 6 | 0 | 0 | 6 | 0 | 0 | 0 |
| `CCE-A-M4-01` | confirmed／extracted／rejected／planned 与来源权力分账 | `BLOCKED_SEMANTIC_CONTRACT` | 3 | 6 | 0 | 3 | 0 | 0 | 0 | 3 | 0 |
| `CCE-A-M4-04` | r1→r2 证据迁锚、消失与歧义 | `REUSE_EXISTING_TEST` | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| `CCE-A-M5-04` | 分页、固定水位、原子批次与隐藏高影响项 | `BLOCKED_SEMANTIC_CONTRACT` | 3 | 6 | 0 | 5 | 0 | 0 | 0 | 1 | 0 |
| `CCE-A-M6-02` | 截至章防剧透、上下文窗口与未读范围 | `REUSE_EXISTING_CASE` | 3 | 6 | 0 | 5 | 1 | 0 | 0 | 0 | 0 |
| `CCE-B-M10-01` | 故事时间与人物阶段锚 | `BLOCKED_SEMANTIC_CONTRACT` | 3 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 0 |
| `CCE-B-M11-01` | HARD 预算、未来隔离、handle 与作者页脱敏 | `EXPECTED_FAIL_MISSING_COMPONENT` | 3 | 10 | 3 | 4 | 3 | 0 | 3 | 0 | 0 |
| `CCE-A-M3-02` | 表述事件与世界命题 | `BLOCKED_SEMANTIC_CONTRACT` | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| `CCE-A-M3-04` | 冻结回包的结构失败、传输失败与解析失败 | `NEW_ZERO_API_FIXTURE` | 3 | 8 | 4 | 4 | 0 | 2 | 2 | 0 | 0 |
| `CCE-A-M7-03` | 冲突强度、对象身份与来源强度 | `BLOCKED_SEMANTIC_CONTRACT` | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| `CCE-B-T14-02` | must_not 与覆盖结果 | `BLOCKED_SEMANTIC_CONTRACT` | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| `CCE-B-M8-02` | 三个可选择计划与硬约束 | `API_LATER` | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| `CCE-B-M9-01` | confirmed-only 梗概主文准入 | `EXPECTED_FAIL_MISSING_COMPONENT` | 4 | 5 | 3 | 0 | 1 | 1 | 3 | 1 | 0 |

### CCE-A-M1-03｜多格式、脏包、章数与静默丢失

- **结论**：`NEW_ZERO_API_FIXTURE`
- **为什么**：四格式、CRC／DOCX 失败关闭和来源链已有直接测试；仍缺嵌套深度边界的成对材料，以及重复水印只提示不删除的差分材料。当前入口能直接跑这些合成输入，水印处理预计失败。
- **已经覆盖**：TXT／MD／DOCX／ZIP 统一内存对象入口；系统垃圾显式丢弃；CRC 损坏和 DOCX 未覆盖区域整批失败关闭
- **还缺**：zip_depth=LIMIT 与 LIMIT+1 的单变量对照；重复水印候选的保留、提示与零静默删除
- **最少读取**：`02_current_route/novel-mvp/mvp/input_router.py`；`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py`；`02_current_route/tests/test_novel_mvp_c10_intake_entrypoints.py`；`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`
- **以后何时重跑**：水印候选检测／损失小票组件落地后，重跑水印处理组；已有格式测试只登记。

### CCE-A-M1-04｜current／已发布／工作稿身份与 owner

- **结论**：`BLOCKED_SEMANTIC_CONTRACT`
- **为什么**：current revision 与 AuthorWorkspace owner 隔离已有测试，但现行 C10／工作稿合同没有一套共享的 CURRENT_WORKING 与 PUBLISHED_FROZEN 生命周期角色。无法唯一冻结两者应走的 writer、consumer 和证据权。
- **已经覆盖**：C11 current 指针与旧 revision 阻断；author／project owner 错配失败关闭
- **还缺**：工作稿与已发表冻结书稿的共同生命周期 owner；角色到证据权、可覆盖性和 consumer allowlist 的正式映射
- **最少读取**：`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`；`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`；`02_current_route/tests/test_novel_mvp_author_workspace.py`；`02_current_route/tests/test_novel_mvp_c11_chapter_revision_ledger.py`
- **以后何时重跑**：共享生命周期合同冻结后，再生成 working／published 双身份材料；本轮不造 TEMP adapter。

### CCE-A-M2-03｜否定、条件、时间限定的切段差分

- **结论**：`NEW_ZERO_API_FIXTURE`
- **为什么**：逐字覆盖、责任段、halo 和稳定坐标已有能力；旧题真正缺的是否定、条件、时间限定在边界附近的差异文本。六个基线／处理组可直接交给现行 M2，模型调用为 0。
- **已经覆盖**：core 全文逐字闭合；halo 只读且不授予责任区；revision ref 与坐标稳定
- **还缺**：否定转折的边界前后对照；条件前件／后件的边界前后对照；时间有效区间切换的边界前后对照
- **最少读取**：`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/novel-mvp/contracts/C2_SEGMENT.md`；`02_current_route/tests/test_novel_mvp_segment_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`
- **以后何时重跑**：无组件阻断；本轮直接运行六个差分变体。

### CCE-A-M4-01｜confirmed／extracted／rejected／planned 与来源权力分账

- **结论**：`BLOCKED_SEMANTIC_CONTRACT`
- **为什么**：C4 已直接覆盖 extracted、confirmed、rejected 和 needs_recheck；planned 不是 C4 状态，AUTHOR_ATTESTATION／inference 的来源权力也没有进入当前 C4 合同。若照旧题造对象，会把未来合同字段冒充当前能力。
- **已经覆盖**：extracted 不自动晋升 confirmed；confirmed／rejected 的作者动作和历史留痕；current consumer 可按现有状态过滤
- **还缺**：planned 的正式 owner 与投影入口；作者签字来源与 AI inference 的机器合同
- **最少读取**：`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`；`02_current_route/novel-mvp/mvp/fact_tool.py`；`02_current_route/novel-mvp/mvp/review_decision_tool.py`；`02_current_route/tests/test_novel_mvp_fact_tool.py`；`02_current_route/tests/test_novel_mvp_review_decision_tool.py`
- **以后何时重跑**：planned owner 与 AUTHOR_ATTESTATION 来源合同冻结后再解封对应三行；现有三状态只登记。

### CCE-A-M4-04｜r1→r2 证据迁锚、消失与歧义

- **结论**：`REUSE_EXISTING_TEST`
- **为什么**：C11 validator 已有唯一迁锚、证据消失和多重命中三条直接反例，恰好覆盖旧家族；不再造 r1／r2 材料。
- **已经覆盖**：CR-16 唯一迁锚；CR-17 证据消失；CR-18 多次命中歧义
- **还缺**：—
- **最少读取**：`02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py`；`02_current_route/tests/test_novel_mvp_c11_chapter_revision_ledger.py`
- **以后何时重跑**：本轮只登记测试；C11 合同变更时才回归。

### CCE-A-M5-04｜分页、固定水位、原子批次与隐藏高影响项

- **结论**：`BLOCKED_SEMANTIC_CONTRACT`
- **为什么**：分页、固定水位、cursor 失效、operation_id 幂等与整批原子性已有直接测试；但 review item 没有正式 high-impact 分类和单签 owner，隐藏高影响项的预期输出不能唯一冻结。
- **已经覆盖**：普通分页与 visible IDs；水位变化后的旧 cursor 失效；中断批次不留下半套决定
- **还缺**：高影响事项的正式分类来源；隐藏页高影响项强制单签的 owner 与状态
- **最少读取**：`02_current_route/novel-mvp/mvp/review_tool.py`；`02_current_route/novel-mvp/mvp/review_decision_tool.py`；`02_current_route/tests/test_novel_mvp_review_tool.py`；`02_current_route/tests/test_novel_mvp_review_decision_tool.py`
- **以后何时重跑**：高影响单签合同冻结后，只补隐藏页反例；普通分页不重做。

### CCE-A-M6-02｜截至章防剧透、上下文窗口与未读范围

- **结论**：`REUSE_EXISTING_CASE`
- **为什么**：13 组合成案例已有 as_of 防剧透样例，当前专用 scope 出口和 renderer 已关闭旧缺口；窗口展开与缺 cutoff 也有直接测试。只登记，不设计第二个 renderer。
- **已经覆盖**：as_of_chapter 截止范围；未来事实排除与作者可读说明；同 revision 上下文展开；缺 cutoff 失败关闭
- **还缺**：—
- **最少读取**：`02_current_route/novel-mvp/mvp/ask_reader_scope_tool.py`；`02_current_route/novel-mvp/mvp/ask_reader_context_tool.py`；`02_current_route/tests/test_novel_mvp_ask_reader_scope_tool.py`；`02_current_route/tests/test_novel_mvp_ask_reader_context_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/CASE_NOTE.md`
- **以后何时重跑**：只在专用出口或 cutoff 合同变化时回归。

### CCE-B-M10-01｜故事时间与人物阶段锚

- **结论**：`BLOCKED_SEMANTIC_CONTRACT`
- **为什么**：当前 M10 能做显式场景卡、锚绑定和确定性导出，但没有正式人物阶段区间 owner，也没有 resolver 可判断一个故事时点落在哪一段。受伤前／后与 draft／missing 的预期无法唯一冻结。
- **已经覆盖**：显式 anchor ref 校验；scene card 与 deterministic export
- **还缺**：人物状态有效区间 owner；故事时点→唯一阶段 resolver；零匹配／多匹配失败语义
- **最少读取**：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`；`02_current_route/novel-mvp/mvp/scene_export_tool.py`；`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`；`02_current_route/tests/test_novel_mvp_scene_export_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- **以后何时重跑**：正式阶段区间 owner 与 resolver 接通 M10 后重跑全部五行；纯 resolver 原型不能冒充产品通过。

### CCE-B-M11-01｜HARD 预算、未来隔离、handle 与作者页脱敏

- **结论**：`EXPECTED_FAIL_MISSING_COMPONENT`
- **为什么**：HARD 预算门、未决停止、actuality 和稳定排序已有测试与案例；真实 handle 的存在性／新鲜度未验证，作者页还会暴露 ID、URI 或 recall handle。可造三条当前必失败反例。
- **已经覆盖**：HARD 超预算零半包；CURRENT_QUERY 与 FUTURE_PLANNING 身份隔离；稳定排序和可选项预算边界；unresolved 停止
- **还缺**：handle 存在性检查；handle 新鲜度／revision 绑定；作者安全 omission 投影
- **最少读取**：`02_current_route/novel-mvp/mvp/packer.py`；`02_current_route/novel-mvp/mvp/packer_tool.py`；`02_current_route/tests/test_novel_mvp_packer.py`；`02_current_route/tests/test_novel_mvp_packer_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/CASE_NOTE.md`
- **以后何时重跑**：M11 handle validator 和作者安全 renderer 落地后重跑三条预期失败；既有预算案例不重造。

### CCE-A-M3-02｜表述事件与世界命题

- **结论**：`BLOCKED_SEMANTIC_CONTRACT`
- **为什么**：旧 API 示例要求 source_mode、world_status、event_kind、candidate_only 等字段；当前 C3 只冻结 text／quote／seg／revision_ref 等现役字段。四种来源语义不能严格映射，不能偷偷加 TEMP schema。
- **已经覆盖**：冻结 provider 生成现行 C3 候选；候选不自动写 C4 confirmed
- **还缺**：表述事件与世界命题的正式字段；DIRECT／HEARSAY／DREAM／LIE 的枚举与 consumer
- **最少读取**：`02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATES.md`；`02_current_route/novel-mvp/mvp/extract_tool.py`；`02_current_route/tests/test_novel_mvp_extract_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- **以后何时重跑**：C3 或相邻正式合同冻结来源／命题语义后，再生成正常与危险冻结回包。

### CCE-A-M3-04｜冻结回包的结构失败、传输失败与解析失败

- **结论**：`NEW_ZERO_API_FIXTURE`
- **为什么**：现有 frozen response validator 已覆盖合法空答、合法候选、缺字段和 extra field；仍可补 facts 非数组、顶层非对象两个结构失败。timeout 与截断属于传输／完成原因，不是当前离线 provider 入口的合法返回，因此登记为预期失败，不伪造 adapter。
- **已经覆盖**：合法空数组与单候选；缺字段与额外字段整批拒绝；坏 item 不应形成部分 C3
- **还缺**：facts 非数组；顶层非对象；timeout 与 finish_reason=length 的独立失败身份
- **最少读取**：`02_current_route/novel-mvp/mvp/extract_tool.py`；`02_current_route/novel-mvp/mvp/extract.py`；`02_current_route/tests/test_novel_mvp_extract_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- **以后何时重跑**：live parser／transport adapter 严格化后重跑 timeout 和截断；结构坏回包本轮直接跑。

### CCE-A-M7-03｜冲突强度、对象身份与来源强度

- **结论**：`BLOCKED_SEMANTIC_CONTRACT`
- **为什么**：当前 C6 finding 能表达一般冲突，但没有正式 proposition identity、source strength 和 object identity 合同，无法可靠区分声称、硬证据、同名异物与传闻。关键词补丁被明确禁止。
- **已经覆盖**：C6 finding 的基本生成、保存与 stale 判断；两端 evidence refs 的通用结构
- **还缺**：命题类型与来源强度；同一对象的稳定身份；HARD_CONFLICT／MIXED_EVIDENCE 的正式判定边界
- **最少读取**：`02_current_route/novel-mvp/contracts/C6_CHECK_FINDINGS.md`；`02_current_route/novel-mvp/mvp/check_tool.py`；`02_current_route/tests/test_novel_mvp_check_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- **以后何时重跑**：正式命题类型与证据强度合同落地后再做四个冻结变体；本轮不执行。

### CCE-B-T14-02｜must_not 与覆盖结果

- **结论**：`BLOCKED_SEMANTIC_CONTRACT`
- **为什么**：当前 T14 使用 covered／mismatch／missing／unknown／unplanned 等通用结果，旧示例要求 VIOLATED、NOT_FOUND_WITHIN_COVERAGE、INCOMPLETE 等 must_not 专属语义。字段与 owner 不同，不能映射。
- **已经覆盖**：工作稿检测的通用覆盖／错写／未写结果；工作稿不被检测器自动改写
- **还缺**：must_not 专属结果合同；coverage completeness 与 no-pass 声明；跨重启结果 owner／resolver／full_check
- **最少读取**：`02_current_route/novel-mvp/contracts/T14_IN_PLACE_WRITING_CHECK_RESULT.md`；`02_current_route/novel-mvp/mvp/writing_check_tool.py`；`02_current_route/tests/test_novel_mvp_writing_check_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- **以后何时重跑**：T14 must_not 结果合同与 owner 落地后再生成四个冻结变体；本轮不执行。

### CCE-B-M8-02｜三个可选择计划与硬约束

- **结论**：`API_LATER`
- **为什么**：旧 API JSON 的 route_signature、steps、tradeoffs、blocking_reasons 等不是当前 C7／plan_tool 可直接消费的合同；当前也缺完整长期 option record owner。此题只在真实模型产生多路线语义时有区分力，本轮保留未来卡。
- **已经覆盖**：C7 v1 离线规划卡；稳定 planning card ref 与选择动作
- **还缺**：完整长期 option record owner；三路线差异的正式输出合同；硬约束覆盖与不可行停止的语义评测
- **最少读取**：`02_current_route/novel-mvp/contracts/C7_CHAPTER_PLAN.md`；`02_current_route/novel-mvp/mvp/plan_tool.py`；`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`；`02_current_route/tests/test_novel_mvp_plan_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- **以后何时重跑**：先完成 owner 只读审计与正式 option contract；之后另开 API 实验，本 manifest 不选模型。

### CCE-B-M9-01｜confirmed-only 梗概主文准入

- **结论**：`EXPECTED_FAIL_MISSING_COMPONENT`
- **为什么**：当前 overview 输入合法接受 extracted／confirmed／rejected，existing 恶意案例已证明 rejected 可污染 synopsis；planned 不属于 C4。可以用当前 Schema 做 confirmed-only 正常对照，以及 extracted／rejected／无 confirmed 的危险变体，但修复前危险组只能记预期失败。
- **已经覆盖**：M9 投影、fact_refs、coverage 与 deterministic render；恶意 rejected synopsis 已被当前机械门接受的现成案例
- **还缺**：confirmed-only synopsis admission gate；无 confirmed 时的材料不足／空主文行为；planned 独立投影 owner
- **最少读取**：`02_current_route/novel-mvp/mvp/overview.py`；`02_current_route/novel-mvp/mvp/overview_tool.py`；`02_current_route/tests/test_novel_mvp_overview_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/CASE_NOTE.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- **以后何时重跑**：confirmed-only 主梗概准入门落地后重跑正常／危险组；planned 等正式 owner。

## 五张未来 API 卡的本轮处理

| 卡 | 处理 | 冻结正常回包 | 冻结危险回包 | 原因 |
|---|---|---|---|---|
| `CCE-A-M3-02` | `BLOCKED_SEMANTIC_CONTRACT` | 否 | 否 | source_mode/world_status/event_kind/candidate_only are not current C3 fields. |
| `CCE-A-M7-03` | `BLOCKED_SEMANTIC_CONTRACT` | 否 | 否 | formal proposition identity, source strength, and object identity are absent. |
| `CCE-B-T14-02` | `BLOCKED_SEMANTIC_CONTRACT` | 否 | 否 | must_not-specific outcomes do not map to the current T14 result contract. |
| `CCE-B-M8-02` | `API_LATER` | 否 | 否 | route_signature/steps/tradeoffs/blocking fields do not map to current C7 and the content distinction only matters with a real model later. |
| `CCE-B-M9-01` | `EXPECTED_FAIL_MISSING_COMPONENT` | 是 | 是 | confirmed/extracted/rejected are current legal C4 statuses and overview accepts a frozen provider; planned remains separately blocked. |

- M3、M7、T14 的示例字段不属于当前正式合同，不能生成“看起来能跑”的 TEMP 对象。
- M8 的三路线语义只有真实模型调用才有意义，保留未来卡，不指定模型、供应商、价格或 evaluator。
- M9 的 current C4 状态可以严格映射，所以保留 frozen normal／dangerous 组；`planned` 仍单独阻断。

## 51 个家族展开摘要

| fixture_family_id | 卡 | 模块 | 旧单变量名 | 变体 | 实跑 | 新备料 | execution_class 计数 |
|---|---|---|---|---:|---:|---:|---|
| `P01-M1-03-F01` | `CCE-A-M1-03` | `M1` | 容器格式 | 4 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=4 |
| `P01-M1-03-F02` | `CCE-A-M1-03` | `M1` | 成员完整性 | 3 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=3 |
| `P01-M1-03-F03` | `CCE-A-M1-03` | `M1` | 嵌套深度 | 2 | 2 | 2 | RUN_NEW_ZERO_API_FIXTURE=2 |
| `P01-M1-03-F04` | `CCE-A-M1-03` | `M1` | 水印候选 | 2 | 2 | 2 | RUN_NEW_ZERO_API_FIXTURE=1；RUN_EXPECTED_FAIL=1 |
| `P01-M1-04-F01` | `CCE-A-M1-04` | `M1/C10/C11` | 材料生命周期 | 2 | 0 | 0 | BLOCKED_NO_RUN=2 |
| `P01-M1-04-F02` | `CCE-A-M1-04` | `M1/C1/C11` | current 指针 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M1-04-F03` | `CCE-A-M1-04` | `AuthorWorkspace/M1` | owner | 3 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=3 |
| `P01-M2-03-F01` | `CCE-A-M2-03` | `M2` | 否定范围 | 2 | 2 | 2 | RUN_NEW_ZERO_API_FIXTURE=2 |
| `P01-M2-03-F02` | `CCE-A-M2-03` | `M2` | 条件前件 | 2 | 2 | 2 | RUN_NEW_ZERO_API_FIXTURE=2 |
| `P01-M2-03-F03` | `CCE-A-M2-03` | `M2` | 时间限定 | 2 | 2 | 2 | RUN_NEW_ZERO_API_FIXTURE=2 |
| `P01-M4-01-F01` | `CCE-A-M4-01` | `M4/M6` | confirmed vs extracted | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M4-01-F02` | `CCE-A-M4-01` | `M4/M6` | rejected vs planned | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=1；BLOCKED_NO_RUN=1 |
| `P01-M4-01-F03` | `CCE-A-M4-01` | `M4/Author Canon` | AUTHOR_ATTESTATION vs inference | 2 | 0 | 0 | BLOCKED_NO_RUN=2 |
| `P01-M4-04-F01` | `CCE-A-M4-04` | `C11/M4` | 唯一迁锚 | 1 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=1 |
| `P01-M4-04-F02` | `CCE-A-M4-04` | `C11/M4` | 证据消失 | 1 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=1 |
| `P01-M4-04-F03` | `CCE-A-M4-04` | `C11/M4` | 多次命中 | 1 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=1 |
| `P01-M5-04-F01` | `CCE-A-M5-04` | `M5` | 隐藏高影响项 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=1；BLOCKED_NO_RUN=1 |
| `P01-M5-04-F02` | `CCE-A-M5-04` | `M5` | 分页水位变化 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M5-04-F03` | `CCE-A-M5-04` | `M5` | 计数闭合 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M6-02-F01` | `CCE-A-M6-02` | `M6` | as_of 截点 | 2 | 0 | 0 | REUSE_EXISTING_CASE_NO_RERUN=1；REGISTER_ONLY_EXISTING_TEST=1 |
| `P01-M6-02-F02` | `CCE-A-M6-02` | `M6` | 人读展开窗口 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M6-02-F03` | `CCE-A-M6-02` | `M6` | 未读范围 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M10-01-F01` | `CCE-B-M10-01` | `M10` | 受伤前阶段 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M10-01-F02` | `CCE-B-M10-01` | `M10` | 受伤后阶段 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M10-01-F03` | `CCE-B-M10-01` | `M10` | 锚缺失状态 | 3 | 0 | 0 | BLOCKED_NO_RUN=3 |
| `P01-M11-01-F01` | `CCE-B-M11-01` | `M11` | HARD 超预算 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M11-01-F02` | `CCE-B-M11-01` | `M11` | 未来隔离 | 2 | 0 | 0 | REUSE_EXISTING_CASE_NO_RERUN=1；REGISTER_ONLY_EXISTING_TEST=1 |
| `P01-M11-01-F03` | `CCE-B-M11-01` | `M11` | 可选项边界 | 6 | 3 | 3 | REGISTER_ONLY_EXISTING_TEST=1；REUSE_EXISTING_CASE_NO_RERUN=2；RUN_EXPECTED_FAIL=3 |
| `P01-M3-02-F01` | `CCE-A-M3-02` | `M3` | 直接叙述 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M3-02-F02` | `CCE-A-M3-02` | `M3` | 传闻 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M3-02-F03` | `CCE-A-M3-02` | `M3` | 梦境 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M3-02-F04` | `CCE-A-M3-02` | `M3` | 明确谎言 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M3-04-F01` | `CCE-A-M3-04` | `M3` | 合法响应形状 | 2 | 0 | 0 | REGISTER_ONLY_EXISTING_TEST=2 |
| `P01-M3-04-F02` | `CCE-A-M3-04` | `M3` | schema 畸形 | 4 | 2 | 2 | REGISTER_ONLY_EXISTING_TEST=2；RUN_NEW_ZERO_API_FIXTURE=2 |
| `P01-M3-04-F03` | `CCE-A-M3-04` | `M3` | 超时／截断 | 2 | 2 | 2 | RUN_EXPECTED_FAIL=2 |
| `P01-M7-03-F01` | `CCE-A-M7-03` | `M7` | 一端仅声称 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M7-03-F02` | `CCE-A-M7-03` | `M7` | 两端硬证据 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M7-03-F03` | `CCE-A-M7-03` | `M7` | 对象不同 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M7-03-F04` | `CCE-A-M7-03` | `M7` | 后端仅传闻 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-T14-02-F01` | `CCE-B-T14-02` | `T14/AuthorWorkspace` | 明确泄露 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-T14-02-F02` | `CCE-B-T14-02` | `T14/AuthorWorkspace` | 确认别名后的改写泄露 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-T14-02-F03` | `CCE-B-T14-02` | `T14/AuthorWorkspace` | 完整扫描未找到 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-T14-02-F04` | `CCE-B-T14-02` | `T14/AuthorWorkspace` | 扫描不完整 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M8-02-F01` | `CCE-B-M8-02` | `M8` | 基础硬约束 | 1 | 0 | 0 | API_LATER_NO_RUN=1 |
| `P01-M8-02-F02` | `CCE-B-M8-02` | `M8` | 新增时间硬门 | 1 | 0 | 0 | API_LATER_NO_RUN=1 |
| `P01-M8-02-F03` | `CCE-B-M8-02` | `M8` | 新增人物限制 | 1 | 0 | 0 | API_LATER_NO_RUN=1 |
| `P01-M8-02-F04` | `CCE-B-M8-02` | `M8` | 可行方案不足 | 1 | 0 | 0 | API_LATER_NO_RUN=1 |
| `P01-M9-01-F01` | `CCE-B-M9-01` | `M9` | extracted 高显著性 | 2 | 2 | 2 | RUN_NEW_ZERO_API_FIXTURE=1；RUN_EXPECTED_FAIL=1 |
| `P01-M9-01-F02` | `CCE-B-M9-01` | `M9` | rejected 高显著性 | 1 | 0 | 0 | REUSE_EXISTING_CASE_NO_RERUN=1 |
| `P01-M9-01-F03` | `CCE-B-M9-01` | `M9/C7` | planned 未来事件 | 1 | 0 | 0 | BLOCKED_NO_RUN=1 |
| `P01-M9-01-F04` | `CCE-B-M9-01` | `M9` | 无 confirmed 材料 | 1 | 1 | 1 | RUN_EXPECTED_FAIL=1 |

## 可并行准备的材料组

### MAT-GRP-01-M1-DIRTY-INPUT｜M1 嵌套深度与水印差分

- 运行数：4
- `variant_id`：`ZAFV-P01-M1-03-F03-DEPTH-LIMIT`；`ZAFV-P01-M1-03-F03-DEPTH-OVER`；`ZAFV-P01-M1-03-F04-NO-REPEAT`；`ZAFV-P01-M1-03-F04-REPEAT-12`
- `run_id`：`ZAFR-0008`；`ZAFR-0009`；`ZAFR-0010`；`ZAFR-0011`
- 配料：同一组三章占位文本；一对只改 ZIP 嵌套深度，一对只改重复页眉/水印次数。记录每层成员 SHA、终端文本 SHA、边界标记与预期损失小票。
- 最少读取：`02_current_route/novel-mvp/mvp/input_router.py`；`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py`；`02_current_route/tests/test_novel_mvp_c10_intake_entrypoints.py`；`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`

### MAT-GRP-02-M2-SCOPE-DIFFERENTIAL｜M2 否定／条件／时间限定差分

- 运行数：6
- `variant_id`：`ZAFV-P01-M2-03-F01-NEG-CONTROL`；`ZAFV-P01-M2-03-F01-NEG-BOUNDARY`；`ZAFV-P01-M2-03-F02-COND-CONTROL`；`ZAFV-P01-M2-03-F02-COND-BOUNDARY`；`ZAFV-P01-M2-03-F03-TIME-CONTROL`；`ZAFV-P01-M2-03-F03-TIME-BOUNDARY`
- `run_id`：`ZAFR-0019`；`ZAFR-0020`；`ZAFR-0021`；`ZAFR-0022`；`ZAFR-0023`；`ZAFR-0024`
- 配料：三段短合成文本，各自生成 control 与 boundary 两版；正文逐字相同，只调切段目标长度/邻段结构，使语义限定词是否跨 core 边界成为唯一变量。
- 最少读取：`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/novel-mvp/contracts/C2_SEGMENT.md`；`02_current_route/tests/test_novel_mvp_segment_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`

### MAT-GRP-03-M3-STRICT-FAILURES｜M3 结构／传输／截断失败分账

- 运行数：4
- `variant_id`：`ZAFV-P01-M3-04-F02-FACTS-NONARRAY`；`ZAFV-P01-M3-04-F02-ROOT-NONOBJECT`；`ZAFV-P01-M3-04-F03-TIMEOUT`；`ZAFV-P01-M3-04-F03-TRUNCATED`
- `run_id`：`ZAFR-0069`；`ZAFR-0070`；`ZAFR-0071`；`ZAFR-0072`
- 配料：复用同一合法 C2 请求；两份冻结 JSON 只改变 root/facts 类型；两份失败记录只改变 transport timeout 或未闭合 JSON+length。不得构造 TEMP adapter。
- 最少读取：`02_current_route/novel-mvp/mvp/extract_tool.py`；`02_current_route/novel-mvp/mvp/extract.py`；`02_current_route/tests/test_novel_mvp_extract_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`

### MAT-GRP-04-M11-HANDLE-REDACTION｜M11 handle 存在性／新鲜度与作者页脱敏

- 运行数：3
- `variant_id`：`ZAFV-P01-M11-01-F03-HANDLE-MISSING`；`ZAFV-P01-M11-01-F03-HANDLE-STALE`；`ZAFV-P01-M11-01-F03-RENDER-AUTHOR`
- `run_id`：`ZAFR-0058`；`ZAFR-0059`；`ZAFR-0060`
- 配料：同一 pack 结果骨架：一份 handle 指向不存在对象，一份指向旧 revision，一份含未来 ID/URI/handle 并调用当前作者渲染出口。三项均应保存当前失败证据。
- 最少读取：`02_current_route/novel-mvp/mvp/packer.py`；`02_current_route/novel-mvp/mvp/packer_tool.py`；`02_current_route/tests/test_novel_mvp_packer.py`；`02_current_route/tests/test_novel_mvp_packer_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/CASE_NOTE.md`

### MAT-GRP-05-M9-CONFIRMED-GATE｜M9 confirmed-only 正常／危险冻结组

- 运行数：3
- `variant_id`：`ZAFV-P01-M9-01-F01-CONFIRMED-CONTROL`；`ZAFV-P01-M9-01-F01-EXTRACTED`；`ZAFV-P01-M9-01-F04-NO-CONFIRMED`
- `run_id`：`ZAFR-0085`；`ZAFR-0086`；`ZAFR-0089`
- 配料：同一 C4 当前 revision：正常组只含 confirmed；危险组一加入高显著性 extracted；危险组二 confirmed=0。每组配独立冻结 provider 回包，不能把三个状态挤进同一行。
- 最少读取：`02_current_route/novel-mvp/mvp/overview.py`；`02_current_route/novel-mvp/mvp/overview_tool.py`；`02_current_route/tests/test_novel_mvp_overview_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/CASE_NOTE.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`

## 本地执行顺序（24 行）

01｜核对输入 ZIP：230 条 SHA256 全部匹配；只把当前代码、合同和直接测试当技术真值。
02｜锁定本 manifest 的 15 张卡、51 个家族、89 个 variant_id／run_id；本地不得自行改 ID。
03｜本地执行前重新确认现役分支与附件快照没有漂移；漂移时停在对账，不静默套用。
04｜登记 36 行 REUSE_EXISTING_TEST；引用现有测试，不复制同一 fixture，不把“已读测试”写成“本轮已跑”。
05｜登记 5 行 REUSE_EXISTING_CASE；其中 M9 rejected 行标记 EXPECTED_FAIL_ALREADY_REPRODUCED。
06｜把 24 行 BLOCKED_NO_RUN 加入阻断清单；不得生成缺失字段、枚举、owner 或 TEMP adapter。
07｜把 4 行 API_LATER_NO_RUN 留在未来卡；本轮不选模型、不申请费用、不调用 provider API。
08｜并行备料 MAT-GRP-01：M1 嵌套 ZIP 与水印差分。
09｜并行备料 MAT-GRP-02：M2 否定／条件／时间限定六个差分文本。
10｜并行备料 MAT-GRP-03：M3 两个结构坏回包与两个 transport/parse 失败记录。
11｜并行备料 MAT-GRP-04：M11 missing/stale handle 与作者页泄露反例。
12｜并行备料 MAT-GRP-05：M9 confirmed-only 正常对照、extracted 危险组、零 confirmed 危险组。
13｜对 20 个新材料变体计算输入 SHA；确认全部为合成材料、真实小说=0、Gold=0、seed registry=0。
14｜运行 ZAFR-0008～0011；保留水印处理组的预期失败，不修代码。
15｜运行 ZAFR-0019～0024；逐字检查 core 拼接、限定词坐标、halo 只读与 revision ref。
16｜运行 ZAFR-0069～0072；结构失败、transport 失败、parse 失败分开记，retry 始终为 0。
17｜运行 ZAFR-0058～0060；missing/stale handle 和作者页泄露均按预期失败保存当前输出。
18｜运行 ZAFR-0085、0086、0089；正常对照应通过，两个危险组修复前不得写 PASS。
19｜逐运行核对 provider_mode 仅为 none／frozen_synthetic_response，model_calls=0，retry=0。
20｜逐运行核对无正式合同、产品文件、Gold、真实小说、训练、Git、Notion 或 API 写入。
21｜保存每行 expected_artifacts；失败行同时保存 current_failure_reason 与 future_rerun_trigger。
22｜按 core_scoring_dimensions 计硬门；bonus 只附加展示，不得抵消红线。
23｜汇总卡级、家族级、变体级计数；确认 15／51／89／20 与本 JSON 一致。
24｜产出本地执行回执并停线；是否修组件、何时重跑由后续独立施工票决定。

## 全量单变量 manifest

下列每个 `variant_id` 都对应 JSON 中一行。`run_required=false` 的行也保留唯一 `run_id`，但不计入 20 次实际运行。

### CCE-A-M1-03｜多格式、脏包、章数与静默丢失｜`NEW_ZERO_API_FIXTURE`

#### ZAFV-P01-M1-03-F01-TXT

- `fixture_family_id`：`P01-M1-03-F01`
- `variant_id`：`ZAFV-P01-M1-03-F01-TXT`
- `run_id`：`ZAFR-0001`
- `module`：`M1`
- `scenario_cn`：同一三章合成文本使用 TXT 容器进入上传对象入口
- `single_variable`：`container_format=TXT`
- `input_recipe`：复用现有参数化测试中的同文档格式样本；终端文本、章序、声明与边界标记保持不变，只改变容器。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：登记既有测试证据：格式可读、来源链可追、无静默丢字；ZIP/DOCX 仍服从整批失败关闭。
- `redline`：不得为本 manifest 再造四套等价材料；不得把文件可读误写成材料身份已确认。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py::test_four_supported_formats_return_safe_inspection_without_truth_writes`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：格式入口覆盖；逐字与 SHA 保真；失败关闭
- `bonus_scoring_dimensions`：作者可读损失小票
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F01-MD

- `fixture_family_id`：`P01-M1-03-F01`
- `variant_id`：`ZAFV-P01-M1-03-F01-MD`
- `run_id`：`ZAFR-0002`
- `module`：`M1`
- `scenario_cn`：同一三章合成文本使用 MD 容器进入上传对象入口
- `single_variable`：`container_format=MD`
- `input_recipe`：复用现有参数化测试中的同文档格式样本；终端文本、章序、声明与边界标记保持不变，只改变容器。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：登记既有测试证据：格式可读、来源链可追、无静默丢字；ZIP/DOCX 仍服从整批失败关闭。
- `redline`：不得为本 manifest 再造四套等价材料；不得把文件可读误写成材料身份已确认。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py::test_four_supported_formats_return_safe_inspection_without_truth_writes`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：格式入口覆盖；逐字与 SHA 保真；失败关闭
- `bonus_scoring_dimensions`：作者可读损失小票
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F01-DOCX

- `fixture_family_id`：`P01-M1-03-F01`
- `variant_id`：`ZAFV-P01-M1-03-F01-DOCX`
- `run_id`：`ZAFR-0003`
- `module`：`M1`
- `scenario_cn`：同一三章合成文本使用 DOCX 容器进入上传对象入口
- `single_variable`：`container_format=DOCX`
- `input_recipe`：复用现有参数化测试中的同文档格式样本；终端文本、章序、声明与边界标记保持不变，只改变容器。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：登记既有测试证据：格式可读、来源链可追、无静默丢字；ZIP/DOCX 仍服从整批失败关闭。
- `redline`：不得为本 manifest 再造四套等价材料；不得把文件可读误写成材料身份已确认。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py::test_four_supported_formats_return_safe_inspection_without_truth_writes`；`02_current_route/tests/test_novel_mvp_c10_first_entrypoints.py::test_entry_07_docx_main_flow_becomes_derived_c10_source`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：格式入口覆盖；逐字与 SHA 保真；失败关闭
- `bonus_scoring_dimensions`：作者可读损失小票
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F01-ZIP

- `fixture_family_id`：`P01-M1-03-F01`
- `variant_id`：`ZAFV-P01-M1-03-F01-ZIP`
- `run_id`：`ZAFR-0004`
- `module`：`M1`
- `scenario_cn`：同一三章合成文本使用 ZIP 容器进入上传对象入口
- `single_variable`：`container_format=ZIP`
- `input_recipe`：复用现有参数化测试中的同文档格式样本；终端文本、章序、声明与边界标记保持不变，只改变容器。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：登记既有测试证据：格式可读、来源链可追、无静默丢字；ZIP/DOCX 仍服从整批失败关闭。
- `redline`：不得为本 manifest 再造四套等价材料；不得把文件可读误写成材料身份已确认。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py::test_four_supported_formats_return_safe_inspection_without_truth_writes`；`02_current_route/tests/test_novel_mvp_c10_first_entrypoints.py::test_entry_09_zip_txt_md_docx_chapters_are_atomic_and_ordered`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：格式入口覆盖；逐字与 SHA 保真；失败关闭
- `bonus_scoring_dimensions`：作者可读损失小票
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F02-CLEAN

- `fixture_family_id`：`P01-M1-03-F02`
- `variant_id`：`ZAFV-P01-M1-03-F02-CLEAN`
- `run_id`：`ZAFR-0005`
- `module`：`M1`
- `scenario_cn`：四成员均合法的完整批次
- `single_variable`：`member_integrity=clean`
- `input_recipe`：引用现有成对 fixture；其他三个成员、声明章数、顺序和 SHA 均固定。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：完整批次按输入顺序产生全部合法终端材料，零部分遗漏。
- `redline`：不完整批次不得冒充完成；失败不得留下半套 C10/C1 或覆盖旧结果。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_c10_first_entrypoints.py::test_entry_09_zip_txt_md_docx_chapters_are_atomic_and_ordered`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：成员完整性；批次原子性；损失透明
- `bonus_scoring_dimensions`：错误码可读性
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F02-CRC-BAD

- `fixture_family_id`：`P01-M1-03-F02`
- `variant_id`：`ZAFV-P01-M1-03-F02-CRC-BAD`
- `run_id`：`ZAFR-0006`
- `module`：`M1`
- `scenario_cn`：第三个 ZIP 成员 CRC/读取失败
- `single_variable`：`member_integrity=zip_crc_error`
- `input_recipe`：引用现有成对 fixture；其他三个成员、声明章数、顺序和 SHA 均固定。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：整批失败关闭；坏成员原因可见；正式状态零部分写入。
- `redline`：不完整批次不得冒充完成；失败不得留下半套 C10/C1 或覆盖旧结果。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py::test_zip_and_unknown_format_failures_use_current_router_blocks`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：成员完整性；批次原子性；损失透明
- `bonus_scoring_dimensions`：错误码可读性
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F02-DOCX-UNCOVERED

- `fixture_family_id`：`P01-M1-03-F02`
- `variant_id`：`ZAFV-P01-M1-03-F02-DOCX-UNCOVERED`
- `run_id`：`ZAFR-0007`
- `module`：`M1`
- `scenario_cn`：第三个 DOCX 含未覆盖主文档外区域
- `single_variable`：`member_integrity=docx_unparsed_area`
- `input_recipe`：引用现有成对 fixture；其他三个成员、声明章数、顺序和 SHA 均固定。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：整批阻断并列出未覆盖区域，不能只取主文档可读部分冒充完整。
- `redline`：不完整批次不得冒充完成；失败不得留下半套 C10/C1 或覆盖旧结果。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_c10_first_entrypoints.py::test_entry_08_docx_unparsed_area_blocks_without_partial_write`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：成员完整性；批次原子性；损失透明
- `bonus_scoring_dimensions`：错误码可读性
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F03-DEPTH-LIMIT

- `fixture_family_id`：`P01-M1-03-F03`
- `variant_id`：`ZAFV-P01-M1-03-F03-DEPTH-LIMIT`
- `run_id`：`ZAFR-0008`
- `module`：`M1`
- `scenario_cn`：相同终端成员封装为 ZIP 嵌套深度 2
- `single_variable`：`zip_depth=2`
- `input_recipe`：新建两套 ZIP，终端成员字节、文件名、顺序和声明完全相同；只改变嵌套层数。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M1_NESTED_ZIP_DEPTH_PAIR`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：两层嵌套在当前 max_archive_layers=2 内完整展开，所有终端成员和来源链闭合。
- `redline`：越界包不得静默截层、不得把只读出外层解释为成功。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/input_router.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md#M1`
- `blocked_by`：—
- `expected_artifacts`：`request.json`；`input_zip.sha256`；`result.json`；`run_receipt.json`
- `core_scoring_dimensions`：嵌套深度门；来源链闭合；零部分写入
- `bonus_scoring_dimensions`：错误说明包含当前限值
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F03-DEPTH-OVER

- `fixture_family_id`：`P01-M1-03-F03`
- `variant_id`：`ZAFV-P01-M1-03-F03-DEPTH-OVER`
- `run_id`：`ZAFR-0009`
- `module`：`M1`
- `scenario_cn`：相同终端成员封装为 ZIP 嵌套深度 3
- `single_variable`：`zip_depth=3`
- `input_recipe`：新建两套 ZIP，终端成员字节、文件名、顺序和声明完全相同；只改变嵌套层数。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M1_NESTED_ZIP_DEPTH_PAIR`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：三层嵌套触发 nested_archive_too_deep；不得只读外层或产生任何 current 章节。
- `redline`：越界包不得静默截层、不得把只读出外层解释为成功。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/input_router.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md#M1`
- `blocked_by`：—
- `expected_artifacts`：`request.json`；`input_zip.sha256`；`result.json`；`run_receipt.json`
- `core_scoring_dimensions`：嵌套深度门；来源链闭合；零部分写入
- `bonus_scoring_dimensions`：错误说明包含当前限值
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F04-NO-REPEAT

- `fixture_family_id`：`P01-M1-03-F04`
- `variant_id`：`ZAFV-P01-M1-03-F04-NO-REPEAT`
- `run_id`：`ZAFR-0010`
- `module`：`M1`
- `scenario_cn`：三章文本中不含跨章重复中性行
- `single_variable`：`repeated_line_count=0`
- `input_recipe`：生成三章短文本，除唯一章标和普通句外不含重复行；与处理组保持字数级别和容器一致。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M1_WATERMARK_DIFFERENTIAL_CONTROL`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：当前入口完整保留文本，warnings 为空；作为重复行处理组的字节保真对照。
- `redline`：控制组不得被误报为水印，也不得改变章节边界。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/input_router.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md#M1`
- `blocked_by`：—
- `expected_artifacts`：`request.json`；`result.json`；`coverage_receipt.json`
- `core_scoring_dimensions`：逐字覆盖；误报为零
- `bonus_scoring_dimensions`：检测小票稳定
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-03-F04-REPEAT-12

- `fixture_family_id`：`P01-M1-03-F04`
- `variant_id`：`ZAFV-P01-M1-03-F04-REPEAT-12`
- `run_id`：`ZAFR-0011`
- `module`：`M1`
- `scenario_cn`：同一条中性句跨章重复 12 次，像站点水印但也可能属于正文
- `single_variable`：`repeated_line_count=12`
- `input_recipe`：在控制组固定坐标插入同一中性句 12 次；所有新增字符计入 source/decoded SHA，不改变其他内容。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M1_WATERMARK_DIFFERENTIAL_TREATMENT`
- `current_entrypoint`：`mvp.input_router.collect_uploads`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：目标行为应保留原文并给 watermark_candidate 警告；现行 input_router 没有该组件，预计只保留文本而不提示，按预期失败登记。
- `redline`：不得为了让测试通过而自动删重复行；不得把 known_archive_junk 规则扩写成正文水印规则。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/input_router.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md#M1 水印候选仍是新缺口`
- `blocked_by`：M1 watermark candidate detector/receipt component absent
- `expected_artifacts`：`request.json`；`result.json`；`expected_fail_receipt.json`；`coverage_receipt.json`
- `core_scoring_dimensions`：零静默删除；候选提示存在
- `bonus_scoring_dimensions`：重复坐标可回看
- `future_rerun_trigger`：M1 水印候选检测与损失小票组件落地后重跑。

### CCE-A-M1-04｜current／已发布／工作稿身份与 owner｜`BLOCKED_SEMANTIC_CONTRACT`

#### ZAFV-P01-M1-04-F01-WORKING

- `fixture_family_id`：`P01-M1-04-F01`
- `variant_id`：`ZAFV-P01-M1-04-F01-WORKING`
- `run_id`：`ZAFR-0012`
- `module`：`M1/C10/C11`
- `scenario_cn`：同一章字节声明为 CURRENT_WORKING
- `single_variable`：`material_lifecycle=CURRENT_WORKING`
- `input_recipe`：旧蓝图要求同一 C10/C11 对象切换 working/published；现行 C10 role 枚举与 WRITING_DESK_WORK_DRAFT 是两套对象，禁止拼成临时字段。
- `material_source`：`NO_MATERIAL_UNTIL_CONTRACT`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__NO_SHARED_LIFECYCLE_OWNER`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结预期输出；只登记 working 与 published/frozen 权力角色尚无共同正式 owner。
- `redline`：不得把 C10 Chapter role、C11 revision 或工作稿 state 解释成已冻结的 published/current_working 二选一字段。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`；`02_current_route/tests/test_novel_mvp_work_draft_workspace.py::test_first_save_edit_restart_and_exact_text_round_trip`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：working/published lifecycle field and owner not frozen
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：权力来源不混；工作稿不获得证据权
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-04-F01-PUBLISHED

- `fixture_family_id`：`P01-M1-04-F01`
- `variant_id`：`ZAFV-P01-M1-04-F01-PUBLISHED`
- `run_id`：`ZAFR-0013`
- `module`：`M1/C10/C11`
- `scenario_cn`：同一章字节声明为 PUBLISHED_FROZEN
- `single_variable`：`material_lifecycle=PUBLISHED_FROZEN`
- `input_recipe`：旧蓝图要求同一 C10/C11 对象切换 working/published；现行 C10 role 枚举与 WRITING_DESK_WORK_DRAFT 是两套对象，禁止拼成临时字段。
- `material_source`：`NO_MATERIAL_UNTIL_CONTRACT`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__NO_SHARED_LIFECYCLE_OWNER`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结预期输出；只登记 working 与 published/frozen 权力角色尚无共同正式 owner。
- `redline`：不得把 C10 Chapter role、C11 revision 或工作稿 state 解释成已冻结的 published/current_working 二选一字段。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`；`02_current_route/tests/test_novel_mvp_work_draft_workspace.py::test_first_save_edit_restart_and_exact_text_round_trip`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：working/published lifecycle field and owner not frozen
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：权力来源不混；工作稿不获得证据权
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-04-F02-R1-STALE

- `fixture_family_id`：`P01-M1-04-F02`
- `variant_id`：`ZAFV-P01-M1-04-F02-R1-STALE`
- `run_id`：`ZAFR-0014`
- `module`：`M1/C1/C11`
- `scenario_cn`：C11 存 r1/r2，current=r2，请求 r1 while current=r2
- `single_variable`：`requested_revision=r1 while current=r2`
- `input_recipe`：复用现有同章两版 fixture；只改变被请求 revision_ref。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`EXISTING_TEST_ONLY__cited direct test is the current evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：旧 r1 不得进入 M2/current 路径。
- `redline`：旧 revision 不得冒充 current，也不得覆盖 r2。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_c1_c2_v1_pipeline.py::test_c2_v1_rejects_current_ref_text_drift`；`02_current_route/tests/test_novel_mvp_c1_c2_v1_pipeline.py::test_c1_v1_writer_rejects_revision_ref_drift_before_write`；`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：current ref 一致；旧版阻断
- `bonus_scoring_dimensions`：跨重启字节一致
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-04-F02-R2-CURRENT

- `fixture_family_id`：`P01-M1-04-F02`
- `variant_id`：`ZAFV-P01-M1-04-F02-R2-CURRENT`
- `run_id`：`ZAFR-0015`
- `module`：`M1/C1/C11`
- `scenario_cn`：C11 存 r1/r2，current=r2，请求 r2 while current=r2
- `single_variable`：`requested_revision=r2 while current=r2`
- `input_recipe`：复用现有同章两版 fixture；只改变被请求 revision_ref。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`EXISTING_TEST_ONLY__cited direct test is the current evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：r2 的 chapter_id、revision_no 和 text SHA 原样传给 C2。
- `redline`：旧 revision 不得冒充 current，也不得覆盖 r2。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_c1_c2_v1_pipeline.py::test_c1_v1_writer_to_c2_v1_inherits_current_revision_ref`；`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：current ref 一致；旧版阻断
- `bonus_scoring_dimensions`：跨重启字节一致
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-04-F03-OWNER-MATCH

- `fixture_family_id`：`P01-M1-04-F03`
- `variant_id`：`ZAFV-P01-M1-04-F03-OWNER-MATCH`
- `run_id`：`ZAFR-0016`
- `module`：`AuthorWorkspace/M1`
- `scenario_cn`：同一内容地址对象，owner_binding=matching_author_project
- `single_variable`：`owner_binding=matching_author_project`
- `input_recipe`：复用 AuthorWorkspace 隔离 fixture；内容 SHA 与逻辑键不变，只切换绑定主体。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`EXISTING_TEST_ONLY__cited direct test is the current evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：绑定 author/project 的当前 workspace 正常读取。
- `redline`：不得靠 chapter_id、显示名或路径猜 owner。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_workspace.py::test_referenced_raw_upload_roundtrip_is_read_only_and_project_bound`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：作者隔离；项目隔离；路径不可冒名
- `bonus_scoring_dimensions`：拒绝不产生目录
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-04-F03-WRONG-AUTHOR

- `fixture_family_id`：`P01-M1-04-F03`
- `variant_id`：`ZAFV-P01-M1-04-F03-WRONG-AUTHOR`
- `run_id`：`ZAFR-0017`
- `module`：`AuthorWorkspace/M1`
- `scenario_cn`：同一内容地址对象，owner_binding=wrong_author
- `single_variable`：`owner_binding=wrong_author`
- `input_recipe`：复用 AuthorWorkspace 隔离 fixture；内容 SHA 与逻辑键不变，只切换绑定主体。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`EXISTING_TEST_ONLY__cited direct test is the current evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：跨作者猜测在业务读取前失败关闭。
- `redline`：不得靠 chapter_id、显示名或路径猜 owner。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_workspace.py::test_same_display_name_isolated_by_authenticated_principal_and_guess_is_hidden`；`02_current_route/tests/test_novel_mvp_workspace.py::test_raw_upload_reader_rejects_cross_author_other_kind_and_path_impostor`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：作者隔离；项目隔离；路径不可冒名
- `bonus_scoring_dimensions`：拒绝不产生目录
- `future_rerun_trigger`：—

#### ZAFV-P01-M1-04-F03-WRONG-PROJECT

- `fixture_family_id`：`P01-M1-04-F03`
- `variant_id`：`ZAFV-P01-M1-04-F03-WRONG-PROJECT`
- `run_id`：`ZAFR-0018`
- `module`：`AuthorWorkspace/M1`
- `scenario_cn`：同一内容地址对象，owner_binding=wrong_project
- `single_variable`：`owner_binding=wrong_project`
- `input_recipe`：复用 AuthorWorkspace 隔离 fixture；内容 SHA 与逻辑键不变，只切换绑定主体。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`EXISTING_TEST_ONLY__cited direct test is the current evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：跨项目或路径冒名失败关闭。
- `redline`：不得靠 chapter_id、显示名或路径猜 owner。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_workspace.py::test_referenced_raw_upload_roundtrip_is_read_only_and_project_bound`；`02_current_route/tests/test_novel_mvp_workspace.py::test_logical_key_rejects_paths_and_non_whitelisted_names`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：作者隔离；项目隔离；路径不可冒名
- `bonus_scoring_dimensions`：拒绝不产生目录
- `future_rerun_trigger`：—

### CCE-A-M2-03｜否定、条件、时间限定的切段差分｜`NEW_ZERO_API_FIXTURE`

#### ZAFV-P01-M2-03-F01-NEG-CONTROL

- `fixture_family_id`：`P01-M2-03-F01`
- `variant_id`：`ZAFV-P01-M2-03-F01-NEG-CONTROL`
- `run_id`：`ZAFR-0019`
- `module`：`M2`
- `scenario_cn`：否定范围控制组
- `single_variable`：`scope_position=inside_one_core`
- `input_recipe`：把“不是没去码头，而是去了却没见到周宁”及前后语义段放入同一 core；填充段固定。 使用合法 C1 v1 current revision；lo/hi/halo 对同一对照组冻结。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M2_DIFFERENTIAL_NEG-CONTROL`
- `current_entrypoint`：`mvp.segment_tool.execute + mvp.segment_tool.render_segment_map`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：C2 core 按序逐字闭合规范化全文；责任段与只读 halo 身份不变；本轮不评价模型是否理解语义。
- `redline`：任何“不/只有/否则/日落前/日落后”字符消失、重复进两个 core、跨 revision 拼接都失败。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/segment.py`；`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_render_map_shows_exact_responsibility_spans_and_read_only_halo`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_coverage_corruption_rejects_the_whole_batch`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`
- `blocked_by`：—
- `expected_artifacts`：`c1_input.json`；`segment_options.json`；`c2_output.json`；`segment_map.md`；`coverage_receipt.json`
- `core_scoring_dimensions`：逐字覆盖；责任段唯一归属；halo 只读；revision ref 继承
- `bonus_scoring_dimensions`：同对照组段数变化可解释
- `future_rerun_trigger`：—

#### ZAFV-P01-M2-03-F01-NEG-BOUNDARY

- `fixture_family_id`：`P01-M2-03-F01`
- `variant_id`：`ZAFV-P01-M2-03-F01-NEG-BOUNDARY`
- `run_id`：`ZAFR-0020`
- `module`：`M2`
- `scenario_cn`：否定范围边界组
- `single_variable`：`scope_position=core_halo_boundary`
- `input_recipe`：保持否定句字节不变，只增加前置填充，使转折前后两个自然段落在相邻 core/halo。 使用合法 C1 v1 current revision；lo/hi/halo 对同一对照组冻结。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M2_DIFFERENTIAL_NEG-BOUNDARY`
- `current_entrypoint`：`mvp.segment_tool.execute + mvp.segment_tool.render_segment_map`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：C2 core 按序逐字闭合规范化全文；责任段与只读 halo 身份不变；本轮不评价模型是否理解语义。
- `redline`：任何“不/只有/否则/日落前/日落后”字符消失、重复进两个 core、跨 revision 拼接都失败。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/segment.py`；`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_render_map_shows_exact_responsibility_spans_and_read_only_halo`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_coverage_corruption_rejects_the_whole_batch`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`
- `blocked_by`：—
- `expected_artifacts`：`c1_input.json`；`segment_options.json`；`c2_output.json`；`segment_map.md`；`coverage_receipt.json`
- `core_scoring_dimensions`：逐字覆盖；责任段唯一归属；halo 只读；revision ref 继承
- `bonus_scoring_dimensions`：同对照组段数变化可解释
- `future_rerun_trigger`：—

#### ZAFV-P01-M2-03-F02-COND-CONTROL

- `fixture_family_id`：`P01-M2-03-F02`
- `variant_id`：`ZAFV-P01-M2-03-F02-COND-CONTROL`
- `run_id`：`ZAFR-0021`
- `module`：`M2`
- `scenario_cn`：条件前件控制组
- `single_variable`：`condition_position=inside_one_core`
- `input_recipe`：把“只有门铃响三次，守卫才开门；否则继续封锁”置于同一 core。 使用合法 C1 v1 current revision；lo/hi/halo 对同一对照组冻结。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M2_DIFFERENTIAL_COND-CONTROL`
- `current_entrypoint`：`mvp.segment_tool.execute + mvp.segment_tool.render_segment_map`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：C2 core 按序逐字闭合规范化全文；责任段与只读 halo 身份不变；本轮不评价模型是否理解语义。
- `redline`：任何“不/只有/否则/日落前/日落后”字符消失、重复进两个 core、跨 revision 拼接都失败。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/segment.py`；`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_render_map_shows_exact_responsibility_spans_and_read_only_halo`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_coverage_corruption_rejects_the_whole_batch`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`
- `blocked_by`：—
- `expected_artifacts`：`c1_input.json`；`segment_options.json`；`c2_output.json`；`segment_map.md`；`coverage_receipt.json`
- `core_scoring_dimensions`：逐字覆盖；责任段唯一归属；halo 只读；revision ref 继承
- `bonus_scoring_dimensions`：同对照组段数变化可解释
- `future_rerun_trigger`：—

#### ZAFV-P01-M2-03-F02-COND-BOUNDARY

- `fixture_family_id`：`P01-M2-03-F02`
- `variant_id`：`ZAFV-P01-M2-03-F02-COND-BOUNDARY`
- `run_id`：`ZAFR-0022`
- `module`：`M2`
- `scenario_cn`：条件前件边界组
- `single_variable`：`condition_position=core_halo_boundary`
- `input_recipe`：保持条件文本不变，只调整前置填充，使前件与后件位于相邻责任段并由 halo 可读。 使用合法 C1 v1 current revision；lo/hi/halo 对同一对照组冻结。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M2_DIFFERENTIAL_COND-BOUNDARY`
- `current_entrypoint`：`mvp.segment_tool.execute + mvp.segment_tool.render_segment_map`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：C2 core 按序逐字闭合规范化全文；责任段与只读 halo 身份不变；本轮不评价模型是否理解语义。
- `redline`：任何“不/只有/否则/日落前/日落后”字符消失、重复进两个 core、跨 revision 拼接都失败。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/segment.py`；`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_render_map_shows_exact_responsibility_spans_and_read_only_halo`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_coverage_corruption_rejects_the_whole_batch`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`
- `blocked_by`：—
- `expected_artifacts`：`c1_input.json`；`segment_options.json`；`c2_output.json`；`segment_map.md`；`coverage_receipt.json`
- `core_scoring_dimensions`：逐字覆盖；责任段唯一归属；halo 只读；revision ref 继承
- `bonus_scoring_dimensions`：同对照组段数变化可解释
- `future_rerun_trigger`：—

#### ZAFV-P01-M2-03-F03-TIME-CONTROL

- `fixture_family_id`：`P01-M2-03-F03`
- `variant_id`：`ZAFV-P01-M2-03-F03-TIME-CONTROL`
- `run_id`：`ZAFR-0023`
- `module`：`M2`
- `scenario_cn`：时间限定控制组
- `single_variable`：`time_switch_position=inside_one_core`
- `input_recipe`：把“日落前不得离岛；日落后收到白旗方可启航”置于同一 core。 使用合法 C1 v1 current revision；lo/hi/halo 对同一对照组冻结。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M2_DIFFERENTIAL_TIME-CONTROL`
- `current_entrypoint`：`mvp.segment_tool.execute + mvp.segment_tool.render_segment_map`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：C2 core 按序逐字闭合规范化全文；责任段与只读 halo 身份不变；本轮不评价模型是否理解语义。
- `redline`：任何“不/只有/否则/日落前/日落后”字符消失、重复进两个 core、跨 revision 拼接都失败。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/segment.py`；`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_render_map_shows_exact_responsibility_spans_and_read_only_halo`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_coverage_corruption_rejects_the_whole_batch`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`
- `blocked_by`：—
- `expected_artifacts`：`c1_input.json`；`segment_options.json`；`c2_output.json`；`segment_map.md`；`coverage_receipt.json`
- `core_scoring_dimensions`：逐字覆盖；责任段唯一归属；halo 只读；revision ref 继承
- `bonus_scoring_dimensions`：同对照组段数变化可解释
- `future_rerun_trigger`：—

#### ZAFV-P01-M2-03-F03-TIME-BOUNDARY

- `fixture_family_id`：`P01-M2-03-F03`
- `variant_id`：`ZAFV-P01-M2-03-F03-TIME-BOUNDARY`
- `run_id`：`ZAFR-0024`
- `module`：`M2`
- `scenario_cn`：时间限定边界组
- `single_variable`：`time_switch_position=core_halo_boundary`
- `input_recipe`：保持时间限定文本不变，只调整填充，使日落前/后两个自然段跨责任边界。 使用合法 C1 v1 current revision；lo/hi/halo 对同一对照组冻结。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M2_DIFFERENTIAL_TIME-BOUNDARY`
- `current_entrypoint`：`mvp.segment_tool.execute + mvp.segment_tool.render_segment_map`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：C2 core 按序逐字闭合规范化全文；责任段与只读 halo 身份不变；本轮不评价模型是否理解语义。
- `redline`：任何“不/只有/否则/日落前/日落后”字符消失、重复进两个 core、跨 revision 拼接都失败。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/segment.py`；`02_current_route/novel-mvp/mvp/segment_tool.py`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_render_map_shows_exact_responsibility_spans_and_read_only_halo`；`02_current_route/tests/test_novel_mvp_segment_tool.py::test_coverage_corruption_rejects_the_whole_batch`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`
- `blocked_by`：—
- `expected_artifacts`：`c1_input.json`；`segment_options.json`；`c2_output.json`；`segment_map.md`；`coverage_receipt.json`
- `core_scoring_dimensions`：逐字覆盖；责任段唯一归属；halo 只读；revision ref 继承
- `bonus_scoring_dimensions`：同对照组段数变化可解释
- `future_rerun_trigger`：—

### CCE-A-M4-01｜confirmed／extracted／rejected／planned 与来源权力分账｜`BLOCKED_SEMANTIC_CONTRACT`

#### ZAFV-P01-M4-01-F01-CONFIRMED

- `fixture_family_id`：`P01-M4-01-F01`
- `variant_id`：`ZAFV-P01-M4-01-F01-CONFIRMED`
- `run_id`：`ZAFR-0025`
- `module`：`M4/M6`
- `scenario_cn`：同一 C4 命题只切换 status=confirmed
- `single_variable`：`c4_status=confirmed`
- `input_recipe`：复用现有 C4 状态过滤 fixture；文字、quote、anchor、revision 均固定。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.ask_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：current、confirmed、VERIFIED 的 C4 可被 M6/current consumer 读取。
- `redline`：extracted 不得漂白为 confirmed；confirmed 仍须 current+VERIFIED。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_workspace.py::test_current_confirmed_verified_hits_and_other_states_stay_excluded`；`02_current_route/tests/test_novel_mvp_ask_tool.py::test_keyword_query_only_returns_current_confirmed_verified_c4`；`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：状态隔离；current evidence 门
- `bonus_scoring_dimensions`：排除计数
- `future_rerun_trigger`：—

#### ZAFV-P01-M4-01-F01-EXTRACTED

- `fixture_family_id`：`P01-M4-01-F01`
- `variant_id`：`ZAFV-P01-M4-01-F01-EXTRACTED`
- `run_id`：`ZAFR-0026`
- `module`：`M4/M6`
- `scenario_cn`：同一 C4 命题只切换 status=extracted
- `single_variable`：`c4_status=extracted`
- `input_recipe`：复用现有 C4 状态过滤 fixture；文字、quote、anchor、revision 均固定。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.ask_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：extracted 留在候选/排除统计，不进入 current truth。
- `redline`：extracted 不得漂白为 confirmed；confirmed 仍须 current+VERIFIED。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_workspace.py::test_current_confirmed_verified_hits_and_other_states_stay_excluded`；`02_current_route/tests/test_novel_mvp_ask_tool.py::test_keyword_query_only_returns_current_confirmed_verified_c4`；`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：状态隔离；current evidence 门
- `bonus_scoring_dimensions`：排除计数
- `future_rerun_trigger`：—

#### ZAFV-P01-M4-01-F02-REJECTED

- `fixture_family_id`：`P01-M4-01-F02`
- `variant_id`：`ZAFV-P01-M4-01-F02-REJECTED`
- `run_id`：`ZAFR-0027`
- `module`：`M4/M6`
- `scenario_cn`：同一命题 status=rejected
- `single_variable`：`c4_status=rejected`
- `input_recipe`：复用现有 rejected 状态过滤 fixture。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.ask_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：rejected 保留审查历史但不进入 current truth、查询或规划事实输入。
- `redline`：rejected 不得被恢复成已发生。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_workspace.py::test_current_confirmed_verified_hits_and_other_states_stay_excluded`；`02_current_route/tests/test_novel_mvp_review_workspace.py::test_reject_is_saved_but_remains_excluded_from_m6`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：驳回历史保留；current 排除
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M4-01-F02-PLANNED

- `fixture_family_id`：`P01-M4-01-F02`
- `variant_id`：`ZAFV-P01-M4-01-F02-PLANNED`
- `run_id`：`ZAFR-0028`
- `module`：`M4/C7`
- `scenario_cn`：旧蓝图把 planned 与 rejected 放在同一状态字段比较
- `single_variable`：`identity=planned`
- `input_recipe`：不造 C4 status=planned；现行 C4 枚举不含 planned，计划属于 C7/planstore 另一对象。
- `material_source`：`NO_MATERIAL_UNTIL_CROSS_LAYER_MAPPING`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__PLANNED_IS_NOT_C4_STATUS`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结同构输出；只登记计划与事实必须分账。
- `redline`：不得给 C4 添加 TEMP planned 枚举，也不得用字符串字段把 C7 计划塞进 facts。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`；`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md#API JSON 不直接映射`
- `blocked_by`：planned object owner/schema differs from C4
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：计划事实分账
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M4-01-F03-AUTHOR-ATTESTATION

- `fixture_family_id`：`P01-M4-01-F03`
- `variant_id`：`ZAFV-P01-M4-01-F03-AUTHOR-ATTESTATION`
- `run_id`：`ZAFR-0029`
- `module`：`M4/Author Canon`
- `scenario_cn`：未见书稿命题的来源切换为 AUTHOR_ATTESTATION
- `single_variable`：`authority_source=AUTHOR_ATTESTATION`
- `input_recipe`：不向 C4 v1 追加 authority/visibility 字段；当前 C4 只有 source 字符串，不能表达作者签字五件套或 AUTHOR 可见范围。
- `material_source`：`NO_MATERIAL_UNTIL_CONTRACT`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__AUTHOR_ATTESTATION_OWNER_NOT_IN_C4`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结通过答案；作者签字与 AI 推断不能借 source 字符串获得相同权力。
- `redline`：不得把 inference 当 AUTHOR Canon；不得伪造签字人、范围、生效时间或可见范围。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`；`02_current_route/tests/test_novel_mvp_reconciliation_facts_admission.py::test_author_admission_writes_confirmed_facts_and_only_exact_variant_support_actual`
- `blocked_by`：formal author-attestation/visibility fields absent from current C4
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：权力来源；可见范围
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M4-01-F03-INFERENCE

- `fixture_family_id`：`P01-M4-01-F03`
- `variant_id`：`ZAFV-P01-M4-01-F03-INFERENCE`
- `run_id`：`ZAFR-0030`
- `module`：`M4/Author Canon`
- `scenario_cn`：未见书稿命题的来源切换为 AI_INFERENCE
- `single_variable`：`authority_source=AI_INFERENCE`
- `input_recipe`：不向 C4 v1 追加 authority/visibility 字段；当前 C4 只有 source 字符串，不能表达作者签字五件套或 AUTHOR 可见范围。
- `material_source`：`NO_MATERIAL_UNTIL_CONTRACT`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__AUTHOR_ATTESTATION_OWNER_NOT_IN_C4`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结通过答案；作者签字与 AI 推断不能借 source 字符串获得相同权力。
- `redline`：不得把 inference 当 AUTHOR Canon；不得伪造签字人、范围、生效时间或可见范围。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`；`02_current_route/tests/test_novel_mvp_reconciliation_facts_admission.py::test_author_admission_writes_confirmed_facts_and_only_exact_variant_support_actual`
- `blocked_by`：formal author-attestation/visibility fields absent from current C4
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：权力来源；可见范围
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

### CCE-A-M4-04｜r1→r2 证据迁锚、消失与歧义｜`REUSE_EXISTING_TEST`

#### ZAFV-P01-M4-04-F01-UNIQUE

- `fixture_family_id`：`P01-M4-04-F01`
- `variant_id`：`ZAFV-P01-M4-04-F01-UNIQUE`
- `run_id`：`ZAFR-0031`
- `module`：`C11/M4`
- `scenario_cn`：r1→r2 后，旧 quote 在新版命中数为 1
- `single_variable`：`new_revision_match_count=1`
- `input_recipe`：复用 C11 机器门 CR-16；old/new text 其余字节按现有 fixture 固定。
- `material_source`：`EXISTING_CONTRACT_VALIDATOR_FIXTURE`
- `current_entrypoint`：`contracts.validate_c11_chapter_revision_ledger.migrate_fact`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：保持 status，迁移 revision_ref/anchor 到 r2。
- `redline`：旧 revision 不得继续冒 current；零/多命中不得自动保持 confirmed。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py::CR-16`；`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`；`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：锚迁移唯一性；needs_recheck 传播；current consumer 过滤
- `bonus_scoring_dimensions`：旧状态历史可追
- `future_rerun_trigger`：—

#### ZAFV-P01-M4-04-F02-GONE

- `fixture_family_id`：`P01-M4-04-F02`
- `variant_id`：`ZAFV-P01-M4-04-F02-GONE`
- `run_id`：`ZAFR-0032`
- `module`：`C11/M4`
- `scenario_cn`：r1→r2 后，旧 quote 在新版命中数为 0
- `single_variable`：`new_revision_match_count=0`
- `input_recipe`：复用 C11 机器门 CR-17；old/new text 其余字节按现有 fixture 固定。
- `material_source`：`EXISTING_CONTRACT_VALIDATOR_FIXTURE`
- `current_entrypoint`：`contracts.validate_c11_chapter_revision_ledger.migrate_fact`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：转 needs_recheck/evidence_gone，退出 M6/M7/M8/M11 current consumer。
- `redline`：旧 revision 不得继续冒 current；零/多命中不得自动保持 confirmed。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py::CR-17`；`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`；`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：锚迁移唯一性；needs_recheck 传播；current consumer 过滤
- `bonus_scoring_dimensions`：旧状态历史可追
- `future_rerun_trigger`：—

#### ZAFV-P01-M4-04-F03-AMBIGUOUS

- `fixture_family_id`：`P01-M4-04-F03`
- `variant_id`：`ZAFV-P01-M4-04-F03-AMBIGUOUS`
- `run_id`：`ZAFR-0033`
- `module`：`C11/M4`
- `scenario_cn`：r1→r2 后，旧 quote 在新版命中数为 2
- `single_variable`：`new_revision_match_count=2`
- `input_recipe`：复用 C11 机器门 CR-18；old/new text 其余字节按现有 fixture 固定。
- `material_source`：`EXISTING_CONTRACT_VALIDATOR_FIXTURE`
- `current_entrypoint`：`contracts.validate_c11_chapter_revision_ledger.migrate_fact`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：转 needs_recheck/anchor_ambiguous；程序不猜锚。
- `redline`：旧 revision 不得继续冒 current；零/多命中不得自动保持 confirmed。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py::CR-18`；`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`；`02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：锚迁移唯一性；needs_recheck 传播；current consumer 过滤
- `bonus_scoring_dimensions`：旧状态历史可追
- `future_rerun_trigger`：—

### CCE-A-M5-04｜分页、固定水位、原子批次与隐藏高影响项｜`BLOCKED_SEMANTIC_CONTRACT`

#### ZAFV-P01-M5-04-F01-VISIBLE-LOW

- `fixture_family_id`：`P01-M5-04-F01`
- `variant_id`：`ZAFV-P01-M5-04-F01-VISIBLE-LOW`
- `run_id`：`ZAFR-0034`
- `module`：`M5`
- `scenario_cn`：当前页只选择可见普通候选，其余页保持 pending
- `single_variable`：`selected_scope=current_visible_page`
- `input_recipe`：复用现有一页选择 fixture。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.review_decision_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：只处理显式选中 ID；其他页和本页未选项保持 pending。
- `redline`：不得把当前页动作扩成整批动作。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_review_decision_tool.py::test_selecting_only_one_page_item_leaves_other_items_pending`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：显式动作范围；未选项保留
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M5-04-F01-HIDDEN-HIGH-IMPACT

- `fixture_family_id`：`P01-M5-04-F01`
- `variant_id`：`ZAFV-P01-M5-04-F01-HIDDEN-HIGH-IMPACT`
- `run_id`：`ZAFR-0035`
- `module`：`M5`
- `scenario_cn`：250 项的第 4 页含死亡/秘密揭示项，第一页执行普通批量动作
- `single_variable`：`high_impact_item_page=4`
- `input_recipe`：不造 high_impact 临时字段；当前 M5 action/page 合同没有高影响 owner 或单签分类。
- `material_source`：`NO_MATERIAL_UNTIL_CONTRACT`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__HIGH_IMPACT_SINGLE_SIGN`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结批量/单签输出；只登记普通分页不能替代高影响单签合同。
- `redline`：不得用文本关键词“死亡/秘密”临时判高影响，也不得宣称普通分页已覆盖单签。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_review_queue_workspace.py`；`02_current_route/tests/test_novel_mvp_review_decision_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md#M5 普通分页已有`
- `blocked_by`：high-impact classification and single-sign owner absent
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：高影响作者决定权
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M5-04-F02-SAME-WATERMARK

- `fixture_family_id`：`P01-M5-04-F02`
- `variant_id`：`ZAFV-P01-M5-04-F02-SAME-WATERMARK`
- `run_id`：`ZAFR-0036`
- `module`：`M5`
- `scenario_cn`：分页继续时 snapshot_watermark=unchanged
- `single_variable`：`snapshot_watermark=unchanged`
- `input_recipe`：复用固定 cursor/watermark fixture；只改变 facts snapshot 水位。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`MISSING_FROM_ROUTE_SNAPSHOT__review_queue_workspace; cited direct tests are registration evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：旧 cursor/页在同一固定水位下可继续，动作幂等。
- `redline`：旧分页视图不得覆盖新 facts；重复动作不得重复提交。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_review_queue_workspace.py::test_processed_last_item_remains_a_valid_resume_anchor`；`02_current_route/tests/test_novel_mvp_review_queue_workspace.py::test_page_tail_and_empty_page_are_stable_and_read_only`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：固定水位；幂等；零陈旧写入
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M5-04-F02-CHANGED-WATERMARK

- `fixture_family_id`：`P01-M5-04-F02`
- `variant_id`：`ZAFV-P01-M5-04-F02-CHANGED-WATERMARK`
- `run_id`：`ZAFR-0037`
- `module`：`M5`
- `scenario_cn`：分页继续时 snapshot_watermark=changed
- `single_variable`：`snapshot_watermark=changed`
- `input_recipe`：复用固定 cursor/watermark fixture；只改变 facts snapshot 水位。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`MISSING_FROM_ROUTE_SNAPSHOT__review_queue_workspace; cited direct tests are registration evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：facts 水位变化后旧页/批次拒绝，零写入。
- `redline`：旧分页视图不得覆盖新 facts；重复动作不得重复提交。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_review_queue_workspace.py::test_facts_change_after_open_is_rejected_by_existing_batch_watermark`；`02_current_route/tests/test_novel_mvp_review_decision_tool.py::test_facts_change_after_page_is_rejected_by_existing_watermark_without_write`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：固定水位；幂等；零陈旧写入
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M5-04-F03-COMPLETE-250

- `fixture_family_id`：`P01-M5-04-F03`
- `variant_id`：`ZAFV-P01-M5-04-F03-COMPLETE-250`
- `run_id`：`ZAFR-0038`
- `module`：`M5`
- `scenario_cn`：固定 250 项批次，completion_state=all_250_seen
- `single_variable`：`completion_state=all_250_seen`
- `input_recipe`：复用 250 项和 resume/atomic batch 现有测试，不再生成普通分页材料。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`MISSING_FROM_ROUTE_SNAPSHOT__review_queue_workspace; cited direct tests are registration evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：250 条分页无缺口、无重复，尾页和空页稳定。
- `redline`：未读 15 条不得冒充完成；失败批次不得留下前半提交。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_review_queue_workspace.py::test_two_hundred_fifty_candidates_page_without_gap_duplicate_or_write`；`02_current_route/tests/test_novel_mvp_review_queue_workspace.py::test_page_tail_and_empty_page_are_stable_and_read_only`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：计数闭合；恢复锚；批次原子性
- `bonus_scoring_dimensions`：尾页可读
- `future_rerun_trigger`：—

#### ZAFV-P01-M5-04-F03-INTERRUPTED-235

- `fixture_family_id`：`P01-M5-04-F03`
- `variant_id`：`ZAFV-P01-M5-04-F03-INTERRUPTED-235`
- `run_id`：`ZAFR-0039`
- `module`：`M5`
- `scenario_cn`：固定 250 项批次，completion_state=235_of_250
- `single_variable`：`completion_state=235_of_250`
- `input_recipe`：复用 250 项和 resume/atomic batch 现有测试，不再生成普通分页材料。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`MISSING_FROM_ROUTE_SNAPSHOT__review_queue_workspace; cited direct tests are registration evidence`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：中断后 remaining=15；不得标 completed；恢复锚合法。
- `redline`：未读 15 条不得冒充完成；失败批次不得留下前半提交。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_review_queue_workspace.py::test_processed_last_item_remains_a_valid_resume_anchor`；`02_current_route/tests/test_novel_mvp_review_decision_tool.py::test_selecting_only_one_page_item_leaves_other_items_pending`；`02_current_route/tests/test_novel_mvp_review_workspace.py::test_bad_second_action_keeps_first_action_out_of_workspace`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：计数闭合；恢复锚；批次原子性
- `bonus_scoring_dimensions`：尾页可读
- `future_rerun_trigger`：—

### CCE-A-M6-02｜截至章防剧透、上下文窗口与未读范围｜`REUSE_EXISTING_CASE`

#### ZAFV-P01-M6-02-F01-ASOF-EARLY

- `fixture_family_id`：`P01-M6-02-F01`
- `variant_id`：`ZAFV-P01-M6-02-F01-ASOF-EARLY`
- `run_id`：`ZAFR-0040`
- `module`：`M6`
- `scenario_cn`：同一谜底查询，as_of_chapter=c01
- `single_variable`：`as_of_chapter=c01`
- `input_recipe`：复用现有合成事实/章节顺序；只切换 as_of_chapter_id。
- `material_source`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence`
- `current_entrypoint`：`mvp.ask_reader_scope_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：只返回 c01 可见事实，c02 真相和身份不泄露。
- `redline`：截点后事实、事实号、章节号或证据不得进入结果。
- `execution_class`：`REUSE_EXISTING_CASE_NO_RERUN`
- `reuse_or_new`：`REUSE_EXISTING_CASE`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REUSE_CASE`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/input.json`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.json`；`02_current_route/tests/test_novel_mvp_ask_reader_scope_tool.py::test_as_of_early_chapter_blocks_later_reveal_without_identity_leak`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：截至章过滤；未来身份不泄露
- `bonus_scoring_dimensions`：reader_scope 人读可见
- `future_rerun_trigger`：—

#### ZAFV-P01-M6-02-F01-ASOF-LATE

- `fixture_family_id`：`P01-M6-02-F01`
- `variant_id`：`ZAFV-P01-M6-02-F01-ASOF-LATE`
- `run_id`：`ZAFR-0041`
- `module`：`M6`
- `scenario_cn`：同一谜底查询，as_of_chapter=later
- `single_variable`：`as_of_chapter=later`
- `input_recipe`：复用现有合成事实/章节顺序；只切换 as_of_chapter_id。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.ask_reader_scope_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：晚截点可读取截点前两条合法 current evidence。
- `redline`：截点后事实、事实号、章节号或证据不得进入结果。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_reader_scope_tool.py::test_as_of_later_chapter_can_see_both_matching_facts`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：截至章过滤；未来身份不泄露
- `bonus_scoring_dimensions`：reader_scope 人读可见
- `future_rerun_trigger`：—

#### ZAFV-P01-M6-02-F02-WINDOW-SHORT

- `fixture_family_id`：`P01-M6-02-F02`
- `variant_id`：`ZAFV-P01-M6-02-F02-WINDOW-SHORT`
- `run_id`：`ZAFR-0042`
- `module`：`M6`
- `scenario_cn`：同一证据 context_window=short
- `single_variable`：`context_window=short`
- `input_recipe`：复用窗口起/中/尾与多证据现有测试；不创建第二个 renderer。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`MISSING_FROM_ROUTE_SNAPSHOT__mvp.ask_context_tool.execute; reader renderer exists as mvp.ask_reader_context_tool.render_result`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：短窗保持同 revision、精确 quote 与最小上下文。
- `redline`：不得跨 revision 拼接；扩大窗口不得改变 confirmed/claim 身份。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_context_tool.py::test_chapter_start_middle_end_windows_and_multiple_evidence`；`02_current_route/tests/test_novel_mvp_ask_reader_context_tool.py::test_previous_workspace_result_renders_c04_without_c06_secret`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：同版上下文；quote 高亮；防剧透
- `bonus_scoring_dimensions`：窗口长度可解释
- `future_rerun_trigger`：—

#### ZAFV-P01-M6-02-F02-WINDOW-EXPANDED

- `fixture_family_id`：`P01-M6-02-F02`
- `variant_id`：`ZAFV-P01-M6-02-F02-WINDOW-EXPANDED`
- `run_id`：`ZAFR-0043`
- `module`：`M6`
- `scenario_cn`：同一证据 context_window=expanded
- `single_variable`：`context_window=expanded`
- `input_recipe`：复用窗口起/中/尾与多证据现有测试；不创建第二个 renderer。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`MISSING_FROM_ROUTE_SNAPSHOT__mvp.ask_context_tool.execute; reader renderer exists as mvp.ask_reader_context_tool.render_result`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：扩窗只扩大同 revision 的前后文，不改变事实状态。
- `redline`：不得跨 revision 拼接；扩大窗口不得改变 confirmed/claim 身份。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_context_tool.py::test_chapter_start_middle_end_windows_and_multiple_evidence`；`02_current_route/tests/test_novel_mvp_ask_reader_context_tool.py::test_previous_workspace_result_renders_c04_without_c06_secret`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：同版上下文；quote 高亮；防剧透
- `bonus_scoring_dimensions`：窗口长度可解释
- `future_rerun_trigger`：—

#### ZAFV-P01-M6-02-F03-CUTOFF-PRESENT

- `fixture_family_id`：`P01-M6-02-F03`
- `variant_id`：`ZAFV-P01-M6-02-F03-CUTOFF-PRESENT`
- `run_id`：`ZAFR-0044`
- `module`：`M6`
- `scenario_cn`：调用方声明截至章时，coverage_index=contains_requested_cutoff
- `single_variable`：`coverage_index=contains_requested_cutoff`
- `input_recipe`：复用 current_revision_refs 顺序测试；缺截点时直接验证现有 fail-closed 规则。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.ask_reader_scope_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：请求截点存在于 current chapter index，按现行专用出口执行。
- `redline`：不得把未纳入 current index 的章节说成已扫描或不存在。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_reader_scope_tool.py::test_non_contiguous_chapter_ids_follow_supplied_array_order`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：覆盖范围诚实；截点身份
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M6-02-F03-CUTOFF-MISSING

- `fixture_family_id`：`P01-M6-02-F03`
- `variant_id`：`ZAFV-P01-M6-02-F03-CUTOFF-MISSING`
- `run_id`：`ZAFR-0045`
- `module`：`M6`
- `scenario_cn`：调用方声明截至章时，coverage_index=missing_requested_cutoff
- `single_variable`：`coverage_index=missing_requested_cutoff`
- `input_recipe`：复用 current_revision_refs 顺序测试；缺截点时直接验证现有 fail-closed 规则。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.ask_reader_scope_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：as_of 不在当前章节索引时失败关闭；不另造“扫到 ch10”声明或第二 renderer。
- `redline`：不得把未纳入 current index 的章节说成已扫描或不存在。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_ask_reader_scope_tool.py::test_bad_cutoff_index_fact_membership_and_shapes_fail_closed`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：覆盖范围诚实；截点身份
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

### CCE-B-M10-01｜故事时间与人物阶段锚｜`BLOCKED_SEMANTIC_CONTRACT`

#### ZAFV-P01-M10-01-F01-PRE-INJURY

- `fixture_family_id`：`P01-M10-01-F01`
- `variant_id`：`ZAFV-P01-M10-01-F01-PRE-INJURY`
- `run_id`：`ZAFR-0046`
- `module`：`M10`
- `scenario_cn`：受伤前场景选择人物外观阶段
- `single_variable`：`scene_story_stage=pre_injury`
- `input_recipe`：保留旧蓝图反例和现有阶段错装案例作为证据；不创建 TEMP stage_interval、draft/confirmed 枚举或 resolver adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__STORY_STAGE_INTERVAL_RESOLVER`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结产品 PASS；当前只能证明显式 anchor binding/歧义门，不能证明按故事时间选阶段。
- `redline`：不得把显式区间原型冒充人物阶段 owner 已接通；不得默认取最新锚。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`；`02_current_route/novel-mvp/mvp/scene_export_tool.py`；`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py::test_missing_or_ambiguous_explicit_bindings_reject_whole_batch`；`02_current_route/tests/test_novel_mvp_scene_export_tool.py::test_anchor_selection_keeps_character_and_location_identity`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal character stage interval owner absent；M10 stage resolver not connected
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：故事时间阶段；锚来源
- `bonus_scoring_dimensions`：缺锚人读警告
- `future_rerun_trigger`：—

#### ZAFV-P01-M10-01-F02-POST-INJURY

- `fixture_family_id`：`P01-M10-01-F02`
- `variant_id`：`ZAFV-P01-M10-01-F02-POST-INJURY`
- `run_id`：`ZAFR-0047`
- `module`：`M10`
- `scenario_cn`：受伤后场景选择人物外观阶段
- `single_variable`：`scene_story_stage=post_injury`
- `input_recipe`：保留旧蓝图反例和现有阶段错装案例作为证据；不创建 TEMP stage_interval、draft/confirmed 枚举或 resolver adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__STORY_STAGE_INTERVAL_RESOLVER`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结产品 PASS；当前只能证明显式 anchor binding/歧义门，不能证明按故事时间选阶段。
- `redline`：不得把显式区间原型冒充人物阶段 owner 已接通；不得默认取最新锚。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`；`02_current_route/novel-mvp/mvp/scene_export_tool.py`；`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py::test_missing_or_ambiguous_explicit_bindings_reject_whole_batch`；`02_current_route/tests/test_novel_mvp_scene_export_tool.py::test_anchor_selection_keeps_character_and_location_identity`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal character stage interval owner absent；M10 stage resolver not connected
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：故事时间阶段；锚来源
- `bonus_scoring_dimensions`：缺锚人读警告
- `future_rerun_trigger`：—

#### ZAFV-P01-M10-01-F03-ANCHOR-CONFIRMED

- `fixture_family_id`：`P01-M10-01-F03`
- `variant_id`：`ZAFV-P01-M10-01-F03-ANCHOR-CONFIRMED`
- `run_id`：`ZAFR-0048`
- `module`：`M10`
- `scenario_cn`：阶段锚已确认
- `single_variable`：`stage_anchor_state=confirmed`
- `input_recipe`：保留旧蓝图反例和现有阶段错装案例作为证据；不创建 TEMP stage_interval、draft/confirmed 枚举或 resolver adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__STORY_STAGE_INTERVAL_RESOLVER`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结产品 PASS；当前只能证明显式 anchor binding/歧义门，不能证明按故事时间选阶段。
- `redline`：不得把显式区间原型冒充人物阶段 owner 已接通；不得默认取最新锚。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`；`02_current_route/novel-mvp/mvp/scene_export_tool.py`；`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py::test_missing_or_ambiguous_explicit_bindings_reject_whole_batch`；`02_current_route/tests/test_novel_mvp_scene_export_tool.py::test_anchor_selection_keeps_character_and_location_identity`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal character stage interval owner absent；M10 stage resolver not connected
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：故事时间阶段；锚来源
- `bonus_scoring_dimensions`：缺锚人读警告
- `future_rerun_trigger`：—

#### ZAFV-P01-M10-01-F03-ANCHOR-DRAFT

- `fixture_family_id`：`P01-M10-01-F03`
- `variant_id`：`ZAFV-P01-M10-01-F03-ANCHOR-DRAFT`
- `run_id`：`ZAFR-0049`
- `module`：`M10`
- `scenario_cn`：阶段锚仍是草稿
- `single_variable`：`stage_anchor_state=draft`
- `input_recipe`：保留旧蓝图反例和现有阶段错装案例作为证据；不创建 TEMP stage_interval、draft/confirmed 枚举或 resolver adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__STORY_STAGE_INTERVAL_RESOLVER`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结产品 PASS；当前只能证明显式 anchor binding/歧义门，不能证明按故事时间选阶段。
- `redline`：不得把显式区间原型冒充人物阶段 owner 已接通；不得默认取最新锚。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`；`02_current_route/novel-mvp/mvp/scene_export_tool.py`；`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py::test_missing_or_ambiguous_explicit_bindings_reject_whole_batch`；`02_current_route/tests/test_novel_mvp_scene_export_tool.py::test_anchor_selection_keeps_character_and_location_identity`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal character stage interval owner absent；M10 stage resolver not connected
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：故事时间阶段；锚来源
- `bonus_scoring_dimensions`：缺锚人读警告
- `future_rerun_trigger`：—

#### ZAFV-P01-M10-01-F03-ANCHOR-MISSING

- `fixture_family_id`：`P01-M10-01-F03`
- `variant_id`：`ZAFV-P01-M10-01-F03-ANCHOR-MISSING`
- `run_id`：`ZAFR-0050`
- `module`：`M10`
- `scenario_cn`：阶段锚缺失
- `single_variable`：`stage_anchor_state=missing`
- `input_recipe`：保留旧蓝图反例和现有阶段错装案例作为证据；不创建 TEMP stage_interval、draft/confirmed 枚举或 resolver adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__STORY_STAGE_INTERVAL_RESOLVER`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结产品 PASS；当前只能证明显式 anchor binding/歧义门，不能证明按故事时间选阶段。
- `redline`：不得把显式区间原型冒充人物阶段 owner 已接通；不得默认取最新锚。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`；`02_current_route/novel-mvp/mvp/scene_export_tool.py`；`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py::test_missing_or_ambiguous_explicit_bindings_reject_whole_batch`；`02_current_route/tests/test_novel_mvp_scene_export_tool.py::test_anchor_selection_keeps_character_and_location_identity`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal character stage interval owner absent；M10 stage resolver not connected
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：故事时间阶段；锚来源
- `bonus_scoring_dimensions`：缺锚人读警告
- `future_rerun_trigger`：—

### CCE-B-M11-01｜HARD 预算、未来隔离、handle 与作者页脱敏｜`EXPECTED_FAIL_MISSING_COMPONENT`

#### ZAFV-P01-M11-01-F01-B-MINUS-1

- `fixture_family_id`：`P01-M11-01-F01`
- `variant_id`：`ZAFV-P01-M11-01-F01-B-MINUS-1`
- `run_id`：`ZAFR-0051`
- `module`：`M11`
- `scenario_cn`：固定 HARD 总量 B，只切换 budget_tokens=B-1
- `single_variable`：`budget_tokens=B-1`
- `input_recipe`：复用现有 HARD 预算边界测试；不再造六条普通 HARD 材料。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.packer.pack_context / mvp.packer_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：STOP_HARD_OVER_BUDGET，loaded 为空，不丢 HARD 凑预算。
- `redline`：不得截断或省略一条 HARD；STOP 不得带半包。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_packer.py::test_hard_set_over_budget_stops_without_returning_a_partial_package`；`02_current_route/tests/test_novel_mvp_packer_tool.py::test_hard_over_budget_stops_without_partial_package`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：HARD 零丢失；硬预算；无半包
- `bonus_scoring_dimensions`：错误说明可读
- `future_rerun_trigger`：—

#### ZAFV-P01-M11-01-F01-B-EXACT

- `fixture_family_id`：`P01-M11-01-F01`
- `variant_id`：`ZAFV-P01-M11-01-F01-B-EXACT`
- `run_id`：`ZAFR-0052`
- `module`：`M11`
- `scenario_cn`：固定 HARD 总量 B，只切换 budget_tokens=B
- `single_variable`：`budget_tokens=B`
- `input_recipe`：复用现有 HARD 预算边界测试；不再造六条普通 HARD 材料。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.packer.pack_context / mvp.packer_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：全部 HARD 恰好装入，used=B。
- `redline`：不得截断或省略一条 HARD；STOP 不得带半包。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_packer.py::test_legal_pack_keeps_hard_first_and_explains_every_loaded_id`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：HARD 零丢失；硬预算；无半包
- `bonus_scoring_dimensions`：错误说明可读
- `future_rerun_trigger`：—

#### ZAFV-P01-M11-01-F02-CURRENT-QUERY

- `fixture_family_id`：`P01-M11-01-F02`
- `variant_id`：`ZAFV-P01-M11-01-F02-CURRENT-QUERY`
- `run_id`：`ZAFR-0053`
- `module`：`M11`
- `scenario_cn`：同一候选材料集，task_actuality_scope=CURRENT_TRUTH_REQUIRED
- `single_variable`：`task_actuality_scope=CURRENT_TRUTH_REQUIRED`
- `input_recipe`：复用现有 actuality/未决材料；只改变 task scope。
- `material_source`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection`
- `current_entrypoint`：`mvp.packer_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：future plan 进入 omission，不作为当前事实装入；机器结果可追溯。
- `redline`：future 不得冒 current；UNRESOLVED 不得自动代填。
- `execution_class`：`REUSE_EXISTING_CASE_NO_RERUN`
- `reuse_or_new`：`REUSE_EXISTING_CASE`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REUSE_CASE`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.json`；`02_current_route/tests/test_novel_mvp_packer_tool.py::test_future_hard_current_scope_is_an_explicit_obligation_conflict`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：actuality 隔离；未决停止
- `bonus_scoring_dimensions`：omission 原因
- `future_rerun_trigger`：—

#### ZAFV-P01-M11-01-F02-FUTURE-PLANNING

- `fixture_family_id`：`P01-M11-01-F02`
- `variant_id`：`ZAFV-P01-M11-01-F02-FUTURE-PLANNING`
- `run_id`：`ZAFR-0054`
- `module`：`M11`
- `scenario_cn`：同一候选材料集，task_actuality_scope=FUTURE_PLANNING_ALLOWED
- `single_variable`：`task_actuality_scope=FUTURE_PLANNING_ALLOWED`
- `input_recipe`：复用现有 actuality/未决材料；只改变 task scope。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.packer_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：未来计划可按计划身份装入，不改写成 current fact；未决仍停止。
- `redline`：future 不得冒 current；UNRESOLVED 不得自动代填。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_packer.py::test_explicit_unresolved_material_stops_and_is_listed_for_caller`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：actuality 隔离；未决停止
- `bonus_scoring_dimensions`：omission 原因
- `future_rerun_trigger`：—

#### ZAFV-P01-M11-01-F03-CAPACITY-0

- `fixture_family_id`：`P01-M11-01-F03`
- `variant_id`：`ZAFV-P01-M11-01-F03-CAPACITY-0`
- `run_id`：`ZAFR-0055`
- `module`：`M11`
- `scenario_cn`：固定 HARD 与可选排序，optional_capacity=0
- `single_variable`：`optional_capacity=0`
- `input_recipe`：复用预算选择案例；只改变可选容量或输出受众。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.packer_tool.execute / render`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：全部 HARD 装入；所有 SHOULD/MAY 进入可见 omission，稳定排序不变。
- `redline`：稳定排序不得随机；omission 不得消失。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_packer.py::test_budget_is_hard_cap_and_optional_material_becomes_visible_omission`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：稳定排序；omission 可见
- `bonus_scoring_dimensions`：机器追溯完整
- `future_rerun_trigger`：—

#### ZAFV-P01-M11-01-F03-CAPACITY-1

- `fixture_family_id`：`P01-M11-01-F03`
- `variant_id`：`ZAFV-P01-M11-01-F03-CAPACITY-1`
- `run_id`：`ZAFR-0056`
- `module`：`M11`
- `scenario_cn`：固定 HARD 与可选排序，optional_capacity=1
- `single_variable`：`optional_capacity=1`
- `input_recipe`：复用预算选择案例；只改变可选容量或输出受众。
- `material_source`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection`
- `current_entrypoint`：`mvp.packer_tool.execute / render`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：装入稳定排序第一条 SHOULD，其余 omission；该现象已有合成案例。
- `redline`：稳定排序不得随机；omission 不得消失。
- `execution_class`：`REUSE_EXISTING_CASE_NO_RERUN`
- `reuse_or_new`：`REUSE_EXISTING_CASE`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REUSE_CASE`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.json`；`02_current_route/tests/test_novel_mvp_packer_tool.py::test_normal_budget_keeps_hard_first_and_exposes_recallable_omission`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：稳定排序；omission 可见
- `bonus_scoring_dimensions`：机器追溯完整
- `future_rerun_trigger`：—

#### ZAFV-P01-M11-01-F03-RENDER-MACHINE

- `fixture_family_id`：`P01-M11-01-F03`
- `variant_id`：`ZAFV-P01-M11-01-F03-RENDER-MACHINE`
- `run_id`：`ZAFR-0057`
- `module`：`M11`
- `scenario_cn`：固定 HARD 与可选排序，render_audience=machine_internal
- `single_variable`：`render_audience=machine_internal`
- `input_recipe`：复用预算选择案例；只改变可选容量或输出受众。
- `material_source`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection`
- `current_entrypoint`：`mvp.packer_tool.execute / render`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：机器 JSON 可保留材料 ID、recall disposition 和 handle，用于内部追溯。
- `redline`：稳定排序不得随机；omission 不得消失。
- `execution_class`：`REUSE_EXISTING_CASE_NO_RERUN`
- `reuse_or_new`：`REUSE_EXISTING_CASE`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REUSE_CASE`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.json`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：稳定排序；omission 可见
- `bonus_scoring_dimensions`：机器追溯完整
- `future_rerun_trigger`：—

#### ZAFV-P01-M11-01-F03-HANDLE-MISSING

- `fixture_family_id`：`P01-M11-01-F03`
- `variant_id`：`ZAFV-P01-M11-01-F03-HANDLE-MISSING`
- `run_id`：`ZAFR-0058`
- `module`：`M11`
- `scenario_cn`：M11 可选项与回捞出口，recall_handle_state=missing
- `single_variable`：`recall_handle_state=missing`
- `input_recipe`：在 CAPACITY-1 控制材料旁建立 handle registry sidecar，并让被装入/省略项的 handle 指向不存在对象；现行 packer 不读取 sidecar。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M11_HANDLE-MISSING`
- `current_entrypoint`：`mvp.packer_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：目标应拒绝或降为 NOT_RETRIEVABLE；现行工具预计仍接受任意非空 handle，登记预期失败。
- `redline`：不得把虚构/过期 handle 当可回捞；作者页不得泄露未来材料身份或内部 URI。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/packer.py`；`02_current_route/novel-mvp/mvp/packer_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：recall handle existence resolver absent
- `expected_artifacts`：`request.json`；`handle_sidecar.json`；`current_result.json`；`expected_fail_receipt.json`
- `core_scoring_dimensions`：handle 可用性；不静默遗漏
- `bonus_scoring_dimensions`：失败理由可回查
- `future_rerun_trigger`：recall handle existence resolver absent 落地后重跑。

#### ZAFV-P01-M11-01-F03-HANDLE-STALE

- `fixture_family_id`：`P01-M11-01-F03`
- `variant_id`：`ZAFV-P01-M11-01-F03-HANDLE-STALE`
- `run_id`：`ZAFR-0059`
- `module`：`M11`
- `scenario_cn`：M11 可选项与回捞出口，recall_handle_state=stale
- `single_variable`：`recall_handle_state=stale`
- `input_recipe`：在 CAPACITY-1 控制材料旁建立 sidecar：handle 存在但 source revision/sha 落后 current；现行 packer 不校验新鲜度。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M11_HANDLE-STALE`
- `current_entrypoint`：`mvp.packer_tool.execute`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：目标应标 stale/要求重编或阻断回捞；现行工具预计仍接受，登记预期失败。
- `redline`：不得把虚构/过期 handle 当可回捞；作者页不得泄露未来材料身份或内部 URI。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/packer.py`；`02_current_route/novel-mvp/mvp/packer_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：recall handle freshness resolver absent
- `expected_artifacts`：`request.json`；`handle_sidecar.json`；`current_result.json`；`expected_fail_receipt.json`
- `core_scoring_dimensions`：handle 可用性；不静默遗漏
- `bonus_scoring_dimensions`：失败理由可回查
- `future_rerun_trigger`：recall handle freshness resolver absent 落地后重跑。

#### ZAFV-P01-M11-01-F03-RENDER-AUTHOR

- `fixture_family_id`：`P01-M11-01-F03`
- `variant_id`：`ZAFV-P01-M11-01-F03-RENDER-AUTHOR`
- `run_id`：`ZAFR-0060`
- `module`：`M11`
- `scenario_cn`：M11 可选项与回捞出口，render_audience=author_safe
- `single_variable`：`render_audience=author_safe`
- `input_recipe`：复用 CAPACITY-1 机器结果，只把输出受众改为 author_safe；不得改机器 JSON。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M11_RENDER-AUTHOR`
- `current_entrypoint`：`mvp.packer_tool.render`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：作者页只显示省略数量、通用原因和可执行下一步，不展示未来材料 ID、名称、URI 或 recall handle；现行 render 预计泄露，登记预期失败。
- `redline`：不得把虚构/过期 handle 当可回捞；作者页不得泄露未来材料身份或内部 URI。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/packer.py`；`02_current_route/novel-mvp/mvp/packer_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.json`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：author-safe omission projection/redaction absent
- `expected_artifacts`：`request.json`；`machine_result.json`；`current_result.json`；`expected_fail_receipt.json`
- `core_scoring_dimensions`：作者安全脱敏；不静默遗漏
- `bonus_scoring_dimensions`：失败理由可回查
- `future_rerun_trigger`：author-safe omission projection/redaction absent 落地后重跑。

### CCE-A-M3-02｜表述事件与世界命题｜`BLOCKED_SEMANTIC_CONTRACT`

#### ZAFV-P01-M3-02-F01-DIRECT

- `fixture_family_id`：`P01-M3-02-F01`
- `variant_id`：`ZAFV-P01-M3-02-F01-DIRECT`
- `run_id`：`ZAFR-0061`
- `module`：`M3`
- `scenario_cn`：同一命题的表达来源为 DIRECT_NARRATION
- `single_variable`：`source_mode=DIRECT_NARRATION`
- `input_recipe`：旧 API 示例要求 event_kind/world_support/modality/source_actor；现行 C3 v1 只有 text/quote/seg/revision_ref，不创建 TEMP adapter。
- `material_source`：`FUTURE_PROTOCOL_ONLY_NO_CURRENT_FIXTURE`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__EXPRESSION_WORLD_PROPOSITION_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结正常/危险 product response；本轮只保留未来语义卡。
- `redline`：不得把 source_mode 塞进 C3 extra field，也不得靠事实句文本约定替代正式命题类型。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/CASE_NOTE.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：current C3 has no expression-event/world-proposition fields or enums
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：表述事件与世界命题分离
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-02-F02-HEARSAY

- `fixture_family_id`：`P01-M3-02-F02`
- `variant_id`：`ZAFV-P01-M3-02-F02-HEARSAY`
- `run_id`：`ZAFR-0062`
- `module`：`M3`
- `scenario_cn`：同一命题的表达来源为 HEARSAY
- `single_variable`：`source_mode=HEARSAY`
- `input_recipe`：旧 API 示例要求 event_kind/world_support/modality/source_actor；现行 C3 v1 只有 text/quote/seg/revision_ref，不创建 TEMP adapter。
- `material_source`：`FUTURE_PROTOCOL_ONLY_NO_CURRENT_FIXTURE`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__EXPRESSION_WORLD_PROPOSITION_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结正常/危险 product response；本轮只保留未来语义卡。
- `redline`：不得把 source_mode 塞进 C3 extra field，也不得靠事实句文本约定替代正式命题类型。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/CASE_NOTE.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：current C3 has no expression-event/world-proposition fields or enums
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：表述事件与世界命题分离
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-02-F03-DREAM

- `fixture_family_id`：`P01-M3-02-F03`
- `variant_id`：`ZAFV-P01-M3-02-F03-DREAM`
- `run_id`：`ZAFR-0063`
- `module`：`M3`
- `scenario_cn`：同一命题的表达来源为 DREAM
- `single_variable`：`source_mode=DREAM`
- `input_recipe`：旧 API 示例要求 event_kind/world_support/modality/source_actor；现行 C3 v1 只有 text/quote/seg/revision_ref，不创建 TEMP adapter。
- `material_source`：`FUTURE_PROTOCOL_ONLY_NO_CURRENT_FIXTURE`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__EXPRESSION_WORLD_PROPOSITION_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结正常/危险 product response；本轮只保留未来语义卡。
- `redline`：不得把 source_mode 塞进 C3 extra field，也不得靠事实句文本约定替代正式命题类型。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/CASE_NOTE.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：current C3 has no expression-event/world-proposition fields or enums
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：表述事件与世界命题分离
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-02-F04-LIE

- `fixture_family_id`：`P01-M3-02-F04`
- `variant_id`：`ZAFV-P01-M3-02-F04-LIE`
- `run_id`：`ZAFR-0064`
- `module`：`M3`
- `scenario_cn`：同一命题的表达来源为 DELIBERATE_LIE
- `single_variable`：`source_mode=DELIBERATE_LIE`
- `input_recipe`：旧 API 示例要求 event_kind/world_support/modality/source_actor；现行 C3 v1 只有 text/quote/seg/revision_ref，不创建 TEMP adapter。
- `material_source`：`FUTURE_PROTOCOL_ONLY_NO_CURRENT_FIXTURE`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__EXPRESSION_WORLD_PROPOSITION_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结正常/危险 product response；本轮只保留未来语义卡。
- `redline`：不得把 source_mode 塞进 C3 extra field，也不得靠事实句文本约定替代正式命题类型。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/CASE_NOTE.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：current C3 has no expression-event/world-proposition fields or enums
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：表述事件与世界命题分离
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

### CCE-A-M3-04｜冻结回包的结构失败、传输失败与解析失败｜`NEW_ZERO_API_FIXTURE`

#### ZAFV-P01-M3-04-F01-LEGAL-EMPTY

- `fixture_family_id`：`P01-M3-04-F01`
- `variant_id`：`ZAFV-P01-M3-04-F01-LEGAL-EMPTY`
- `run_id`：`ZAFR-0065`
- `module`：`M3`
- `scenario_cn`：冻结 provider 回包：provider_facts_count=0
- `single_variable`：`provider_facts_count=0`
- `input_recipe`：复用现有 strict frozen response fixture；同一 C2 item 与 current revision 不变。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.extract_tool.execute + offline_response_provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：合法空 facts 接受并稳定产生零候选。
- `redline`：不得补字段、丢 extra、接纳部分 item 或覆盖旧输出。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_extract_workspace.py::test_exact_response_keys_allow_every_item_to_return_zero_candidates`；`02_current_route/novel-mvp/mvp/extract_tool.py`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：严格 schema；整批原子性
- `bonus_scoring_dimensions`：错误码稳定
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-04-F01-LEGAL-ONE

- `fixture_family_id`：`P01-M3-04-F01`
- `variant_id`：`ZAFV-P01-M3-04-F01-LEGAL-ONE`
- `run_id`：`ZAFR-0066`
- `module`：`M3`
- `scenario_cn`：冻结 provider 回包：provider_facts_count=1
- `single_variable`：`provider_facts_count=1`
- `input_recipe`：复用现有 strict frozen response fixture；同一 C2 item 与 current revision 不变。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.extract_tool.execute + offline_response_provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：合法单候选按现行 C3 v1 生成。
- `redline`：不得补字段、丢 extra、接纳部分 item 或覆盖旧输出。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_extract_tool.py::test_local_files_turn_c2_batch_into_parseable_c3_batch_without_api`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/current_output.json`；`02_current_route/novel-mvp/mvp/extract_tool.py`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：严格 schema；整批原子性
- `bonus_scoring_dimensions`：错误码稳定
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-04-F02-MISSING-FIELD

- `fixture_family_id`：`P01-M3-04-F02`
- `variant_id`：`ZAFV-P01-M3-04-F02-MISSING-FIELD`
- `run_id`：`ZAFR-0067`
- `module`：`M3`
- `scenario_cn`：冻结 provider 回包：schema_mutation=missing_quote
- `single_variable`：`schema_mutation=missing_quote`
- `input_recipe`：复用现有 strict frozen response fixture；同一 C2 item 与 current revision 不变。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.extract_tool.execute + offline_response_provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：严格拒绝，整批无 C3，旧输出不覆盖。
- `redline`：不得补字段、丢 extra、接纳部分 item 或覆盖旧输出。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_extract_tool.py::test_provider_fields_are_not_repaired_or_silently_dropped`；`02_current_route/novel-mvp/mvp/extract_tool.py`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：严格 schema；整批原子性
- `bonus_scoring_dimensions`：错误码稳定
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-04-F02-EXTRA-FIELD

- `fixture_family_id`：`P01-M3-04-F02`
- `variant_id`：`ZAFV-P01-M3-04-F02-EXTRA-FIELD`
- `run_id`：`ZAFR-0068`
- `module`：`M3`
- `scenario_cn`：冻结 provider 回包：schema_mutation=extra_field
- `single_variable`：`schema_mutation=extra_field`
- `input_recipe`：复用现有 strict frozen response fixture；同一 C2 item 与 current revision 不变。
- `material_source`：`EXISTING_TEST_FIXTURE`
- `current_entrypoint`：`mvp.extract_tool.execute + offline_response_provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：严格拒绝，extra 不被静默丢弃。
- `redline`：不得补字段、丢 extra、接纳部分 item 或覆盖旧输出。
- `execution_class`：`REGISTER_ONLY_EXISTING_TEST`
- `reuse_or_new`：`REUSE_EXISTING_TEST`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_PASS_REGISTER_ONLY`
- `existing_evidence`：`02_current_route/tests/test_novel_mvp_extract_tool.py::test_provider_fields_are_not_repaired_or_silently_dropped`；`02_current_route/novel-mvp/mvp/extract_tool.py`
- `blocked_by`：—
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：严格 schema；整批原子性
- `bonus_scoring_dimensions`：错误码稳定
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-04-F02-FACTS-NONARRAY

- `fixture_family_id`：`P01-M3-04-F02`
- `variant_id`：`ZAFV-P01-M3-04-F02-FACTS-NONARRAY`
- `run_id`：`ZAFR-0069`
- `module`：`M3`
- `scenario_cn`：冻结 provider 结构坏回包：schema_mutation=facts_non_array
- `single_variable`：`schema_mutation=facts_non_array`
- `input_recipe`：复制合法 frozen response，仅把 data.facts 从数组改为对象；其余字节与键固定。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M3_FACTS-NONARRAY`
- `current_entrypoint`：`mvp.extract_tool.execute + offline_response_provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：现行 _validate_provider_result 应报 PROVIDER_FACTS_NOT_LIST，零 C3。
- `redline`：坏结构不得进入 live parser 清洗，也不得留下部分 C3。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/extract_tool.py`；`02_current_route/tests/test_novel_mvp_extract_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：—
- `expected_artifacts`：`c2_request.json`；`frozen_response.json`；`error_receipt.json`；`output_inventory.json`
- `core_scoring_dimensions`：schema failure；零写入
- `bonus_scoring_dimensions`：错误层级明确
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-04-F02-ROOT-NONOBJECT

- `fixture_family_id`：`P01-M3-04-F02`
- `variant_id`：`ZAFV-P01-M3-04-F02-ROOT-NONOBJECT`
- `run_id`：`ZAFR-0070`
- `module`：`M3`
- `scenario_cn`：冻结 provider 结构坏回包：schema_mutation=top_level_non_object
- `single_variable`：`schema_mutation=top_level_non_object`
- `input_recipe`：复制合法 frozen response，仅把 provider result 顶层改为数组。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M3_ROOT-NONOBJECT`
- `current_entrypoint`：`mvp.extract_tool.execute + offline_response_provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：现行 _validate_provider_result 应报 PROVIDER_RESULT_NOT_OBJECT，零 C3。
- `redline`：坏结构不得进入 live parser 清洗，也不得留下部分 C3。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/extract_tool.py`；`02_current_route/tests/test_novel_mvp_extract_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：—
- `expected_artifacts`：`c2_request.json`；`frozen_response.json`；`error_receipt.json`；`output_inventory.json`
- `core_scoring_dimensions`：schema failure；零写入
- `bonus_scoring_dimensions`：错误层级明确
- `future_rerun_trigger`：—

#### ZAFV-P01-M3-04-F03-TIMEOUT

- `fixture_family_id`：`P01-M3-04-F03`
- `variant_id`：`ZAFV-P01-M3-04-F03-TIMEOUT`
- `run_id`：`ZAFR-0071`
- `module`：`M3`
- `scenario_cn`：M3 失败层：failure_layer=transport_timeout
- `single_variable`：`failure_layer=transport_timeout`
- `input_recipe`：provider callable 仅抛 TimeoutError；不返回 JSON，不重试。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M3_TIMEOUT`
- `current_entrypoint`：`mvp.extract_tool.execute (current boundary; missing structured transport adapter)`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：目标应产结构化 FAILED_TRANSPORT_NO_RETRY/attempts=1；现行 extract_tool 没有该 transport receipt，预计异常外抛，按预期失败。
- `redline`：不得自动重试；不得从截断字节恢复部分事实；不得覆盖已有 C3。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/extract_tool.py`；`02_current_route/novel-mvp/mvp/extract.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：M3 transport failure receipt/owner absent
- `expected_artifacts`：`c2_request.json`；`raw_failure.bin`；`failure_sidecar.json`；`expected_fail_receipt.json`；`output_inventory.json`
- `core_scoring_dimensions`：transport/parse 分账；retry=0；零部分写入
- `bonus_scoring_dimensions`：raw SHA 留存
- `future_rerun_trigger`：M3 transport failure receipt/owner absent 落地后重跑。

#### ZAFV-P01-M3-04-F03-TRUNCATED

- `fixture_family_id`：`P01-M3-04-F03`
- `variant_id`：`ZAFV-P01-M3-04-F03-TRUNCATED`
- `run_id`：`ZAFR-0072`
- `module`：`M3`
- `scenario_cn`：M3 失败层：failure_layer=parse_truncated_finish_length
- `single_variable`：`failure_layer=parse_truncated_finish_length`
- `input_recipe`：保存未闭合 JSON 原始字节与 finish_reason=length sidecar；不先修复成 Python 对象。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M3_TRUNCATED`
- `current_entrypoint`：`mvp.extract_tool.execute (current boundary; missing structured transport adapter)`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：目标应分账 FAILED_PARSE_NO_RETRY 并保留 raw SHA；现行 frozen provider 入口只接已解析对象，不能表达该形状，按预期失败。
- `redline`：不得自动重试；不得从截断字节恢复部分事实；不得覆盖已有 C3。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/extract_tool.py`；`02_current_route/novel-mvp/mvp/extract.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：raw transport/finish_reason adapter absent
- `expected_artifacts`：`c2_request.json`；`raw_failure.bin`；`failure_sidecar.json`；`expected_fail_receipt.json`；`output_inventory.json`
- `core_scoring_dimensions`：transport/parse 分账；retry=0；零部分写入
- `bonus_scoring_dimensions`：raw SHA 留存
- `future_rerun_trigger`：raw transport/finish_reason adapter absent 落地后重跑。

### CCE-A-M7-03｜冲突强度、对象身份与来源强度｜`BLOCKED_SEMANTIC_CONTRACT`

#### ZAFV-P01-M7-03-F01-ONE-SIDE-CLAIM

- `fixture_family_id`：`P01-M7-03-F01`
- `variant_id`：`ZAFV-P01-M7-03-F01-ONE-SIDE-CLAIM`
- `run_id`：`ZAFR-0073`
- `module`：`M7`
- `scenario_cn`：钥匙烧毁/再出现冲突对，side_a_source_strength=claim
- `single_variable`：`side_a_source_strength=claim`
- `input_recipe`：现有 C4/C6 只有事实 text/status/anchor 与 finding；没有表述事件、source strength、stable object_id/effective_range。保留现有红灯案例作为反证，不造关键词 adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__FORMAL_PROPOSITION_EVIDENCE_STRENGTH`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结 HARD_CONFLICT/MIXED_EVIDENCE 产品答案；未来合同完成后才运行。
- `redline`：不得按“声称/传闻”关键词修补，也不得把冻结 provider finding 当语义正确。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.json`；`02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal proposition/source-strength/object-identity types absent
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：证据强度；对象身份；冲突等级
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M7-03-F02-BOTH-HARD

- `fixture_family_id`：`P01-M7-03-F02`
- `variant_id`：`ZAFV-P01-M7-03-F02-BOTH-HARD`
- `run_id`：`ZAFR-0074`
- `module`：`M7`
- `scenario_cn`：钥匙烧毁/再出现冲突对，side_a_source_strength=confirmed_verified
- `single_variable`：`side_a_source_strength=confirmed_verified`
- `input_recipe`：现有 C4/C6 只有事实 text/status/anchor 与 finding；没有表述事件、source strength、stable object_id/effective_range。保留现有红灯案例作为反证，不造关键词 adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__FORMAL_PROPOSITION_EVIDENCE_STRENGTH`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结 HARD_CONFLICT/MIXED_EVIDENCE 产品答案；未来合同完成后才运行。
- `redline`：不得按“声称/传闻”关键词修补，也不得把冻结 provider finding 当语义正确。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.json`；`02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal proposition/source-strength/object-identity types absent
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：证据强度；对象身份；冲突等级
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M7-03-F03-DIFFERENT-OBJECT

- `fixture_family_id`：`P01-M7-03-F03`
- `variant_id`：`ZAFV-P01-M7-03-F03-DIFFERENT-OBJECT`
- `run_id`：`ZAFR-0075`
- `module`：`M7`
- `scenario_cn`：钥匙烧毁/再出现冲突对，object_identity=different
- `single_variable`：`object_identity=different`
- `input_recipe`：现有 C4/C6 只有事实 text/status/anchor 与 finding；没有表述事件、source strength、stable object_id/effective_range。保留现有红灯案例作为反证，不造关键词 adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__FORMAL_PROPOSITION_EVIDENCE_STRENGTH`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结 HARD_CONFLICT/MIXED_EVIDENCE 产品答案；未来合同完成后才运行。
- `redline`：不得按“声称/传闻”关键词修补，也不得把冻结 provider finding 当语义正确。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.json`；`02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal proposition/source-strength/object-identity types absent
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：证据强度；对象身份；冲突等级
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M7-03-F04-SIDE-B-HEARSAY

- `fixture_family_id`：`P01-M7-03-F04`
- `variant_id`：`ZAFV-P01-M7-03-F04-SIDE-B-HEARSAY`
- `run_id`：`ZAFR-0076`
- `module`：`M7`
- `scenario_cn`：钥匙烧毁/再出现冲突对，side_b_source_strength=hearsay
- `single_variable`：`side_b_source_strength=hearsay`
- `input_recipe`：现有 C4/C6 只有事实 text/status/anchor 与 finding；没有表述事件、source strength、stable object_id/effective_range。保留现有红灯案例作为反证，不造关键词 adapter。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__FORMAL_PROPOSITION_EVIDENCE_STRENGTH`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结 HARD_CONFLICT/MIXED_EVIDENCE 产品答案；未来合同完成后才运行。
- `redline`：不得按“声称/传闻”关键词修补，也不得把冻结 provider finding 当语义正确。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.json`；`02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：formal proposition/source-strength/object-identity types absent
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：证据强度；对象身份；冲突等级
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

### CCE-B-T14-02｜must_not 与覆盖结果｜`BLOCKED_SEMANTIC_CONTRACT`

#### ZAFV-P01-T14-02-F01-DIRECT-REVEAL

- `fixture_family_id`：`P01-T14-02-F01`
- `variant_id`：`ZAFV-P01-T14-02-F01-DIRECT-REVEAL`
- `run_id`：`ZAFR-0077`
- `module`：`T14/AuthorWorkspace`
- `scenario_cn`：must_not 检测，draft_signal=explicit_reveal
- `single_variable`：`draft_signal=explicit_reveal`
- `input_recipe`：旧示例 outcome=VIOLATED/NOT_FOUND_WITHIN_COVERAGE/UNVERIFIED_INCOMPLETE 与 overall 不属于现行 WRITING_DESK_CHECK_RESULT；现行结果只有 covered/mismatch/missing/unknown/unplanned 且 status=completed。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__MUST_NOT_COVERAGE_RESULT_CONTRACT`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不生成 normal/dangerous 临时回包；当前案例只证明通用 package/result 接收器可跑，不证明 must_not 覆盖语义。
- `redline`：不得把 unknown/missing 随意映射成未找到或通过；不得新增 TEMP enum/adapter。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.json`；`02_current_route/novel-mvp/mvp/writing_check_package_tool.py`；`02_current_route/novel-mvp/mvp/writing_check_result_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：must_not-specific outcome and coverage completeness not frozen；T14 persisted owner/resolver/full_check still open
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：未找到不等于通过；覆盖完整性；逐字证据
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-T14-02-F02-ALIAS-REVEAL

- `fixture_family_id`：`P01-T14-02-F02`
- `variant_id`：`ZAFV-P01-T14-02-F02-ALIAS-REVEAL`
- `run_id`：`ZAFR-0078`
- `module`：`T14/AuthorWorkspace`
- `scenario_cn`：must_not 检测，draft_signal=confirmed_alias_rewrite
- `single_variable`：`draft_signal=confirmed_alias_rewrite`
- `input_recipe`：旧示例 outcome=VIOLATED/NOT_FOUND_WITHIN_COVERAGE/UNVERIFIED_INCOMPLETE 与 overall 不属于现行 WRITING_DESK_CHECK_RESULT；现行结果只有 covered/mismatch/missing/unknown/unplanned 且 status=completed。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__MUST_NOT_COVERAGE_RESULT_CONTRACT`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不生成 normal/dangerous 临时回包；当前案例只证明通用 package/result 接收器可跑，不证明 must_not 覆盖语义。
- `redline`：不得把 unknown/missing 随意映射成未找到或通过；不得新增 TEMP enum/adapter。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.json`；`02_current_route/novel-mvp/mvp/writing_check_package_tool.py`；`02_current_route/novel-mvp/mvp/writing_check_result_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：must_not-specific outcome and coverage completeness not frozen；T14 persisted owner/resolver/full_check still open
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：未找到不等于通过；覆盖完整性；逐字证据
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-T14-02-F03-FULL-NOT-FOUND

- `fixture_family_id`：`P01-T14-02-F03`
- `variant_id`：`ZAFV-P01-T14-02-F03-FULL-NOT-FOUND`
- `run_id`：`ZAFR-0079`
- `module`：`T14/AuthorWorkspace`
- `scenario_cn`：must_not 检测，coverage=complete_no_match
- `single_variable`：`coverage=complete_no_match`
- `input_recipe`：旧示例 outcome=VIOLATED/NOT_FOUND_WITHIN_COVERAGE/UNVERIFIED_INCOMPLETE 与 overall 不属于现行 WRITING_DESK_CHECK_RESULT；现行结果只有 covered/mismatch/missing/unknown/unplanned 且 status=completed。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__MUST_NOT_COVERAGE_RESULT_CONTRACT`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不生成 normal/dangerous 临时回包；当前案例只证明通用 package/result 接收器可跑，不证明 must_not 覆盖语义。
- `redline`：不得把 unknown/missing 随意映射成未找到或通过；不得新增 TEMP enum/adapter。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.json`；`02_current_route/novel-mvp/mvp/writing_check_package_tool.py`；`02_current_route/novel-mvp/mvp/writing_check_result_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：must_not-specific outcome and coverage completeness not frozen；T14 persisted owner/resolver/full_check still open
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：未找到不等于通过；覆盖完整性；逐字证据
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-T14-02-F04-INCOMPLETE

- `fixture_family_id`：`P01-T14-02-F04`
- `variant_id`：`ZAFV-P01-T14-02-F04-INCOMPLETE`
- `run_id`：`ZAFR-0080`
- `module`：`T14/AuthorWorkspace`
- `scenario_cn`：must_not 检测，coverage=incomplete_no_match
- `single_variable`：`coverage=incomplete_no_match`
- `input_recipe`：旧示例 outcome=VIOLATED/NOT_FOUND_WITHIN_COVERAGE/UNVERIFIED_INCOMPLETE 与 overall 不属于现行 WRITING_DESK_CHECK_RESULT；现行结果只有 covered/mismatch/missing/unknown/unplanned 且 status=completed。
- `material_source`：`EXISTING_CASE_EVIDENCE_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__MUST_NOT_COVERAGE_RESULT_CONTRACT`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不生成 normal/dangerous 临时回包；当前案例只证明通用 package/result 接收器可跑，不证明 must_not 覆盖语义。
- `redline`：不得把 unknown/missing 随意映射成未找到或通过；不得新增 TEMP enum/adapter。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.json`；`02_current_route/novel-mvp/mvp/writing_check_package_tool.py`；`02_current_route/novel-mvp/mvp/writing_check_result_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：must_not-specific outcome and coverage completeness not frozen；T14 persisted owner/resolver/full_check still open
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：未找到不等于通过；覆盖完整性；逐字证据
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

### CCE-B-M8-02｜三个可选择计划与硬约束｜`API_LATER`

#### ZAFV-P01-M8-02-F01-BASE

- `fixture_family_id`：`P01-M8-02-F01`
- `variant_id`：`ZAFV-P01-M8-02-F01-BASE`
- `run_id`：`ZAFR-0081`
- `module`：`M8`
- `scenario_cn`：三路线规划探针，constraint_delta=base_hard_constraints
- `single_variable`：`constraint_delta=base_hard_constraints`
- `input_recipe`：旧示例 route_signature/plan_steps/prerequisites/tradeoffs/blocking_constraints 不严格映射 C7 cards/options/guidance；不造 adapter。现有 M8 案例只作 C7 能跑的旁证。
- `material_source`：`FUTURE_API_PROTOCOL_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card`
- `current_entrypoint`：`NO_ZERO_API_CURRENT_ENTRYPOINT_FOR_THIS_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：本轮不执行；保留未来 API 卡，待正式 action/option owner 与调用授权后另行冻结。
- `redline`：不得把 C7 局部 options 冒充完整长期 option record；不得指定模型/供应商/价格。
- `execution_class`：`API_LATER_NO_RUN`
- `reuse_or_new`：`API_LATER`
- `run_required`：`false`
- `expectation_status`：`FUTURE_NOT_EXECUTED`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.json`；`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：old API response does not strictly map current C7；M8 formal action/consumer owner insufficient
- `expected_artifacts`：`future_card_record.json`
- `core_scoring_dimensions`：HARD 约束保留；路线差异；不可行时不凑数
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M8-02-F02-TIME-GATE

- `fixture_family_id`：`P01-M8-02-F02`
- `variant_id`：`ZAFV-P01-M8-02-F02-TIME-GATE`
- `run_id`：`ZAFR-0082`
- `module`：`M8`
- `scenario_cn`：三路线规划探针，constraint_delta=add_time_gate
- `single_variable`：`constraint_delta=add_time_gate`
- `input_recipe`：旧示例 route_signature/plan_steps/prerequisites/tradeoffs/blocking_constraints 不严格映射 C7 cards/options/guidance；不造 adapter。现有 M8 案例只作 C7 能跑的旁证。
- `material_source`：`FUTURE_API_PROTOCOL_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card`
- `current_entrypoint`：`NO_ZERO_API_CURRENT_ENTRYPOINT_FOR_THIS_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：本轮不执行；保留未来 API 卡，待正式 action/option owner 与调用授权后另行冻结。
- `redline`：不得把 C7 局部 options 冒充完整长期 option record；不得指定模型/供应商/价格。
- `execution_class`：`API_LATER_NO_RUN`
- `reuse_or_new`：`API_LATER`
- `run_required`：`false`
- `expectation_status`：`FUTURE_NOT_EXECUTED`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.json`；`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：old API response does not strictly map current C7；M8 formal action/consumer owner insufficient
- `expected_artifacts`：`future_card_record.json`
- `core_scoring_dimensions`：HARD 约束保留；路线差异；不可行时不凑数
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M8-02-F03-PROTECTED-ACTOR

- `fixture_family_id`：`P01-M8-02-F03`
- `variant_id`：`ZAFV-P01-M8-02-F03-PROTECTED-ACTOR`
- `run_id`：`ZAFR-0083`
- `module`：`M8`
- `scenario_cn`：三路线规划探针，constraint_delta=add_protected_actor
- `single_variable`：`constraint_delta=add_protected_actor`
- `input_recipe`：旧示例 route_signature/plan_steps/prerequisites/tradeoffs/blocking_constraints 不严格映射 C7 cards/options/guidance；不造 adapter。现有 M8 案例只作 C7 能跑的旁证。
- `material_source`：`FUTURE_API_PROTOCOL_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card`
- `current_entrypoint`：`NO_ZERO_API_CURRENT_ENTRYPOINT_FOR_THIS_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：本轮不执行；保留未来 API 卡，待正式 action/option owner 与调用授权后另行冻结。
- `redline`：不得把 C7 局部 options 冒充完整长期 option record；不得指定模型/供应商/价格。
- `execution_class`：`API_LATER_NO_RUN`
- `reuse_or_new`：`API_LATER`
- `run_required`：`false`
- `expectation_status`：`FUTURE_NOT_EXECUTED`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.json`；`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：old API response does not strictly map current C7；M8 formal action/consumer owner insufficient
- `expected_artifacts`：`future_card_record.json`
- `core_scoring_dimensions`：HARD 约束保留；路线差异；不可行时不凑数
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M8-02-F04-INSUFFICIENT

- `fixture_family_id`：`P01-M8-02-F04`
- `variant_id`：`ZAFV-P01-M8-02-F04-INSUFFICIENT`
- `run_id`：`ZAFR-0084`
- `module`：`M8`
- `scenario_cn`：三路线规划探针，feasible_option_count<3
- `single_variable`：`feasible_option_count<3`
- `input_recipe`：旧示例 route_signature/plan_steps/prerequisites/tradeoffs/blocking_constraints 不严格映射 C7 cards/options/guidance；不造 adapter。现有 M8 案例只作 C7 能跑的旁证。
- `material_source`：`FUTURE_API_PROTOCOL_ONLY:03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card`
- `current_entrypoint`：`NO_ZERO_API_CURRENT_ENTRYPOINT_FOR_THIS_SCHEMA`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：本轮不执行；保留未来 API 卡，待正式 action/option owner 与调用授权后另行冻结。
- `redline`：不得把 C7 局部 options 冒充完整长期 option record；不得指定模型/供应商/价格。
- `execution_class`：`API_LATER_NO_RUN`
- `reuse_or_new`：`API_LATER`
- `run_required`：`false`
- `expectation_status`：`FUTURE_NOT_EXECUTED`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.json`；`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：old API response does not strictly map current C7；M8 formal action/consumer owner insufficient
- `expected_artifacts`：`future_card_record.json`
- `core_scoring_dimensions`：HARD 约束保留；路线差异；不可行时不凑数
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

### CCE-B-M9-01｜confirmed-only 梗概主文准入｜`EXPECTED_FAIL_MISSING_COMPONENT`

#### ZAFV-P01-M9-01-F01-CONFIRMED-CONTROL

- `fixture_family_id`：`P01-M9-01-F01`
- `variant_id`：`ZAFV-P01-M9-01-F01-CONFIRMED-CONTROL`
- `run_id`：`ZAFR-0085`
- `module`：`M9`
- `scenario_cn`：合法当前 M9 输入只含 confirmed 事实，冻结 provider 只引用 confirmed 生成主梗概
- `single_variable`：`input_status_set=confirmed_only`
- `input_recipe`：使用与 extracted 处理组相同的两条普通 confirmed 事实，移除额外高显著性候选；冻结 provider 的 synopsis、beats、fact_refs 只引用 confirmed。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M9_CONFIRMED_ONLY_CONTROL`
- `current_entrypoint`：`mvp.overview.execute + frozen synthetic provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：现行代码应生成合法投影；未来 confirmed-only 准入门落地后仍应通过，作为正常对照。
- `redline`：正常对照不得混入 extracted、rejected、planned，也不得把 provider 结果写回真值。
- `execution_class`：`RUN_NEW_ZERO_API_FIXTURE`
- `reuse_or_new`：`NEW_ZERO_API_FIXTURE`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_PASS_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/overview.py`；`02_current_route/novel-mvp/mvp/overview_tool.py`；`02_current_route/tests/test_novel_mvp_overview_tool.py`
- `blocked_by`：—
- `expected_artifacts`：`request.json`；`frozen_provider_response.json`；`overview_card.json`；`run_receipt.json`
- `core_scoring_dimensions`：confirmed-only 主文准入；fact_refs 全部指向 confirmed current；投影不写真值
- `bonus_scoring_dimensions`：排除计数可读性
- `future_rerun_trigger`：—
- `notes`：五张未来 API 卡中的可映射正常冻结回包；本轮 provider 为冻结合成函数，真实模型调用为 0。

#### ZAFV-P01-M9-01-F01-EXTRACTED

- `fixture_family_id`：`P01-M9-01-F01`
- `variant_id`：`ZAFV-P01-M9-01-F01-EXTRACTED`
- `run_id`：`ZAFR-0086`
- `module`：`M9`
- `scenario_cn`：两条 confirmed 普通事实外增加一条高显著性 extracted 候选，并让冻结 provider 在 synopsis 引用它
- `single_variable`：`extra_record_status=extracted`
- `input_recipe`：从现有 M9 案例复制 request/provider fixture，只把恶意额外记录设为 extracted；其余 confirmed、anchor、provider 文本固定。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M9_EXTRACTED_SYNOPSIS_GATE`
- `current_entrypoint`：`mvp.overview.execute + frozen synthetic provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：目标门应在 provider 前/后阻断 extracted 进入主梗概；现行 CURRENT_FACT_STATUSES 包含 extracted，预计接受恶意主文，按预期失败。
- `redline`：extracted 不得进入 synopsis/beats；不能靠页脚状态提示补救主文污染。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/overview.py`；`02_current_route/novel-mvp/mvp/overview_tool.py`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/CASE_NOTE.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：M9 confirmed-only synopsis admission gate absent
- `expected_artifacts`：`request.json`；`frozen_provider_response.json`；`current_output.json`；`expected_fail_receipt.json`
- `core_scoring_dimensions`：confirmed-only 主文；fact_refs 状态门
- `bonus_scoring_dimensions`：排除计数
- `future_rerun_trigger`：M9 confirmed-only 主梗概准入门落地后作为回归重跑。

#### ZAFV-P01-M9-01-F02-REJECTED

- `fixture_family_id`：`P01-M9-01-F02`
- `variant_id`：`ZAFV-P01-M9-01-F02-REJECTED`
- `run_id`：`ZAFR-0087`
- `module`：`M9`
- `scenario_cn`：现有恶意案例把 rejected 的“店主是寄件人”写入 synopsis
- `single_variable`：`extra_record_status=rejected`
- `input_recipe`：直接复用现有案例 input/current_output，不再生成材料或重跑。
- `material_source`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview`
- `current_entrypoint`：`mvp.overview.execute + frozen synthetic provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：既有输出已证明当前机械门会接受 rejected 污染；登记为已复现预期失败证据，修复后回归。
- `redline`：不得把现有危险输出登记成 PASS。
- `execution_class`：`REUSE_EXISTING_CASE_NO_RERUN`
- `reuse_or_new`：`REUSE_EXISTING_CASE`
- `run_required`：`false`
- `expectation_status`：`EXPECTED_FAIL_ALREADY_REPRODUCED`
- `existing_evidence`：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/CASE_NOTE.md`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/input.json`；`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/current_output.json`
- `blocked_by`：M9 confirmed-only synopsis admission gate absent
- `expected_artifacts`：`evidence_registration.json`
- `core_scoring_dimensions`：rejected 不进主文
- `bonus_scoring_dimensions`：人读状态醒目
- `future_rerun_trigger`：M9 confirmed-only 主梗概准入门落地后回归。

#### ZAFV-P01-M9-01-F03-PLANNED

- `fixture_family_id`：`P01-M9-01-F03`
- `variant_id`：`ZAFV-P01-M9-01-F03-PLANNED`
- `run_id`：`ZAFR-0088`
- `module`：`M9/C7`
- `scenario_cn`：额外记录是未来 planned death，同时 current confirmed 仍存活
- `single_variable`：`extra_record_identity=planned`
- `input_recipe`：不造 C4 status=planned；现行 M9 request 只接 C4 extracted/confirmed/rejected，旧 API records schema 不映射。
- `material_source`：`NO_MATERIAL_UNTIL_M9_PLAN_INPUT_CONTRACT`
- `current_entrypoint`：`MISSING_CURRENT_ENTRYPOINT__M9_PLAN_PROJECTION_INPUT`
- `provider_mode`：`none`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：不冻结产品输出；只登记计划不得进入当前历史梗概。
- `redline`：不得给 C4/M9 临时增加 planned 枚举或把 C7 文本当事实。
- `execution_class`：`BLOCKED_NO_RUN`
- `reuse_or_new`：`BLOCKED_SEMANTIC_CONTRACT`
- `run_required`：`false`
- `expectation_status`：`NO_UNIQUE_EXPECTATION`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/overview.py`；`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：planned input/owner not part of current M9 request contract
- `expected_artifacts`：`blocked_record.json`
- `core_scoring_dimensions`：未来计划隔离
- `bonus_scoring_dimensions`：—
- `future_rerun_trigger`：—

#### ZAFV-P01-M9-01-F04-NO-CONFIRMED

- `fixture_family_id`：`P01-M9-01-F04`
- `variant_id`：`ZAFV-P01-M9-01-F04-NO-CONFIRMED`
- `run_id`：`ZAFR-0089`
- `module`：`M9`
- `scenario_cn`：合法当前 M9 输入只含 extracted/rejected，confirmed 集为空，冻结 provider仍返回肯定 synopsis
- `single_variable`：`confirmed_record_count=0`
- `input_recipe`：使用当前合法 C4 状态，只放 extracted/rejected（不塞 planned）；冻结 provider 返回引用两者的 synopsis。
- `material_source`：`NEW_SYNTHETIC_TO_PREPARE:M9_NO_CONFIRMED_GATE`
- `current_entrypoint`：`mvp.overview.execute + frozen synthetic provider`
- `provider_mode`：`frozen_synthetic_response`
- `model_calls`：0
- `retry`：0
- `expected_behavior`：目标应返回材料不足/空主文；现行 overview 预计接受并生成，按预期失败。
- `redline`：无 confirmed 时不得用候选/驳回凑梗概。
- `execution_class`：`RUN_EXPECTED_FAIL`
- `reuse_or_new`：`EXPECTED_FAIL_MISSING_COMPONENT`
- `run_required`：`true`
- `expectation_status`：`EXPECTED_FAIL_TO_RUN`
- `existing_evidence`：`02_current_route/novel-mvp/mvp/overview.py`；`02_current_route/novel-mvp/mvp/overview_tool.py`；`02_current_route/tests/test_novel_mvp_overview_tool.py`；`04_external_reviews/pro_component_pilot_followup_bundle/LOCAL_TRIAGE_R01.md`
- `blocked_by`：M9 confirmed-only synopsis admission gate absent
- `expected_artifacts`：`request.json`；`frozen_provider_response.json`；`current_output.json`；`expected_fail_receipt.json`
- `core_scoring_dimensions`：空 confirmed fail closed；主文零候选污染
- `bonus_scoring_dimensions`：材料不足人读说明
- `future_rerun_trigger`：M9 confirmed-only 主梗概准入门落地后重跑。

## 机械自检

- `variant_id` 全局唯一：true
- `run_id` 全局唯一：true
- 家族数：51
- provider allowlist：`frozen_synthetic_response`；`none`
- 全部 `model_calls=0`：true
- 全部 `retry=0`：true
- 本地执行顺序：24 行，≤30：true
- Markdown 与 JSON 由同一内存对象生成；数量、card_id、fixture_family_id、variant_id、run_id 同源。

来源：当前 Prompt＋附件中的当前代码／合同／直接测试／13 组合成案例＋本地分诊；旧 Pro 报告仅作背景。
