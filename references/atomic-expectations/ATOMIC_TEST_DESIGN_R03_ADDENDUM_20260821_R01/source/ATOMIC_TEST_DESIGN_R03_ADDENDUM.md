# ATOMIC TEST DESIGN R03 ADDENDUM

状态：**TEST_DESIGN_ONLY / ADVISORY_ONLY / SELF_CHECK_PASS**

这份补充件把旧 R02 的 127×6 测试设计对账到 R03 的 142 条原子需求。它不修改 R03，不调用 API，不选择模型，不生成 Gold，也不读取或夹带真实小说正文。

## 结论

- Project Source release：`PROJECT_SOURCE_RELEASE_8e66fe30e71fdfed`，本轮所需发布文件 SHA 均匹配。
- R03 CSV：142 行、142 个唯一 `预期ID`；新增 15 条与任务清单逐项一致。
- 旧四份设计：127 条需求、762 个唯一小测试；每条恰好 6 例、权重合计 100。旧题面按原 SHA 和 test_id 保留，只应用本文件的差量登记。
- 新增设计：15 条×6＝90 例，全部使用 `AT5-` 前缀，90 个 test_id 和 90 个独立红线 ID 均唯一。
- 执行分层：60 个零 API 机械例、13 个未来模型语义例、17 个合同/产品决定未闭合而暂不可执行例。
- R14 适用范围修正：7 条旧需求的 42 个旧测试只适用于外来道，不能证明自产章要回 M2/M3 重抽。

## 1. 发布、CSV 与窗口身份

| 项目 | 结果 |
|---|---|
| release ID | `PROJECT_SOURCE_RELEASE_8e66fe30e71fdfed` |
| R03 CSV | `142` 行 / `142` 唯一 ID / SHA `11749551b55f13dd4ae63e90a85a20a7492959c16eb219385ac152d36fe41937` |
| 窗口 ZIP | SHA `b2c50aa6a53bed52e6eb55bd74a715ce29726cc58b0365a3a42a28d5726c1199`；成员 SHA `251/251 PASS` |
| 运行代码 | `01efc50d863bf01ac048dc6c50284fcebc7e51f4` |
| 打包定义 | `79bd2e2` |
| 差量参考 | `a7b3ecb` |

包内测试基线写的是：除两份依赖未版本化 TEMP fixture 的测试文件外，`1542 passed / 0 failed`，ruff PASS。这个数字只作为包内身份回执；不能证明真实内容能力。

### 本轮直接零 API 窄组

| 组 | 结果 | 只允许得出的结论 |
|---|---:|---|
| 章事实稿、外来道与相关身份/持久化测试组 | 98 passed, 16 deselected | 证明选中的零 API 局部合同/持久化断言通过；不证明正式自产 C11、事实入账或真实语义。 |
| 章节 INITIAL 准入与 reconciliation 相关测试组 | 31 passed, 8 deselected | 证明局部准入/版本机械门；不等于自产章正式交棒已完成。 |
| M8 planning、selection target、planstore 相关测试组 | 108 passed, 23 deselected | 证明 C7/target/planstore 的局部切片；selection target 仍是 transport-only，不能冒充 plan write。 |
| M10/M11/context packer/recall 相关测试组 | 120 passed, 5 deselected | 证明 resolver、handle、budget/identity 等局部机械行为；不证明人物账/三账回取/真实材料充分性。 |
| ledger directory 与 intent router 相关测试组 | 50 passed, 8 deselected | 证明固定目录和 advisory router 的局部行为；不证明十个具体账本、设定唯一路由或写账 consumer。 |
| M9 overview 与 M7 check 相关测试组 | 136 passed, 14 deselected | 证明 current/confirmed、只读投影/报告等机械门；不证明完整驾驶舱指标或圈段语义诊断。 |
| 章事实稿纯函数/工具窄组 | 30 passed, 6 deselected | 证明 prototype object、reader/validator 等机械行为；effects 仍明确为 no formal C11/facts/plan write。 |

说明：各组有重叠，结果不可相加。一次超大组合运行因执行超时中止，未观察到断言失败；因此本报告不把超时写成代码 FAIL，也不把被排除的 CLI 子进程例写成 PASS。

## 2. 旧 R02 设计完整性与保留方式

| Part | 需求 | 小测试 | JSON SHA-256 |
|---:|---:|---:|---|
| 1 | 32 | 192 | `8b19e8edc048df2d28edc813c38bd1cc174134e877aec69bb73c949266c6be2b` |
| 2 | 36 | 216 | `0666499afeee626e5f87085583ddfce4bdfceaa5fe68a7da28fbbc46af566614` |
| 3 | 41 | 246 | `006bfbf5129f18f00059faca13623818f713f1dd6dac13ae7e40440099aa8012` |
| 4 | 18 | 108 | `bd88ca496b02c004a0a60890c627db520bbbd477926faf4cf5c13842799d3153` |
| **合计** | **127** | **762** | — |

机械自查结果：

- 127 个 requirement ID 全局唯一，且恰好等于 R03 去掉新增 15 条后的 ID 集合。
- 762 个旧 test_id 全局唯一。
- 每条旧需求恰好 6 个小测试；每条权重合计 100。
- 旧 762 例不复制改写；以四份 JSON 的 SHA、完整 127-suite/test-ID/weight 清单和下方差量表共同保留。完整清单在同名 JSON 的 `legacy_audit.requirement_inventory`。

## 3. 旧测试需要改口径的项目

以下只改适用范围、当前状态或证据边界，不重写 762 例。JSON 里给出了每项精确受影响 test_id。

| Delta | 旧 requirement | 影响例数 | 新口径 |
|---|---|---:|---|
| `R03-D01` | `M2-E01、M3-E01、M3-E03、M4-C02、M4-C04、M6-C01、AE-X-C01` | 42 | 适用范围：外来道。只证明外来书稿/外部手写书稿进入 M2/M3/M4/M6 的取证与消费；不得用于证明产品自产章需要回 M2/M3 重抽。 |
| `R03-D02` | `M1-N01` | 6 | 不要继续写成 CSV/XLSX 完全缺能力；当前代码已有目标格式/局部输入支持证据，但仍需逐例按真实 parser、混合单元分流和覆盖回执重判。 |
| `R03-D03` | `M4-C05` | 6 | 保留来源身份体系测试，并新增对 M4-N01 的明确分工：外来事实可由书稿证据承托；自产事实目标来源是 AUTHOR_ATTESTATION，但机器字段、确认粒度和 owner 尚未冻结。 |
| `R03-D04` | `AE-X-C03` | 6 | 把旧修订测试拆成两种口径：外来冻结书稿修订继续做版本/证据迁移；自产渲染书稿新增信息只做局部 diff→candidate→作者确认，对齐 AE-X-N03，不整章重抽。 |
| `R03-D05` | `AE-X-C05` | 6 | 旧“工作稿冻结→C10→C11→C1→planstore”只保留为外写/历史路线；自产主路改为章事实稿→pending/preflight→正式 C11/章节账（未完成）→事实确认（未冻结）→下一章。 |
| `R03-D06` | `M7-E01、M7-E02、M7-E03` | 18 | 保留一致性/体检语义题，但输入门统一写成 current+confirmed；extracted、rejected、planned 和 stale 投影不得作为主判断事实。 |
| `R03-D07` | `M8-N01` | 6 | 旧六例继续测模糊未来内容放置语义；current_code_status 改为“部分覆盖：advisory placement router”，不可写成已持久化进长线/规划账。 |
| `R03-D08` | `M8-E07` | 6 | 局部选择目标只证明 transport/identity/完整 option record 绑定；不得证明选择卡全文已由稳定 owner 保存，也不得证明选中方案已写回 planstore。分别交由 M8-N05、M8-N06。 |
| `R03-D09` | `AE-M10-C04` | 6 | 把 current status 更新为部分覆盖：显式 story interval 唯一命中、gap/overlap 拒绝已有；人物账 owner、章/场景到故事时间 binding 和已确认来源未完成。 |
| `R03-D10` | `AE-M11-B02、AE-M11-C04` | 12 | 更新为部分覆盖：opaque handle 能绑定 current source ref、拒 stale/cross-workspace；三账正式 owner、历史版本 pin、显式 expiry 和用途授权仍缺。 |
| `R03-D11` | `AE-M11-C01、AE-M11-C02、AE-M11-C03、AE-M11-C06` | 24 | 保留材料选择、预算、缺料和回取说明题；current status 更新为部分覆盖的只读 supply/bundle 候选，禁止写成正式 C11/facts/plan 写入或真实语义充分性。 |
| `R03-D12` | `AE-AW-C06` | 6 | 把十账户籍登记作为目录能力测试；明确目录模块不创建具体账本、不决定每账内容，也不证明简装/精装升级或题材包。 |
| `R03-D13` | `AE-X-C01` | 6 | 本条明确为外来道：confirmed external C10→C11 current→C1 current→M2。当前可写局部机械接线已覆盖；不得用于自产章，也不得证明 M3/M4/M5 真实语义。 |

🔥 其中最硬的一条：`M2-E01`、`M3-E01`、`M3-E03`、`M4-C02`、`M4-C04`、`M6-C01`、`AE-X-C01` 的 42 例统一补标签 **“适用范围：外来道”**。

## 4. 执行分层

| 类别 | 数量 | 当前怎么处理 |
|---|---:|---|
| `ZERO_API_MECHANICAL` | 60 | 用函数/存储/身份/版本/权限/调用计数/恢复断言；缺代码的例先作为可执行测试合同。 |
| `FUTURE_MODEL_SEMANTIC` | 13 | 只给脱敏配方和人工评分尺；本轮不调用 API、不选模型、不生成 Gold。 |
| `BLOCKED_CONTRACT_OR_PRODUCT_DECISION` | 17 | blocker 解除前标 `BLOCKED_NOT_SCORED`；不得用 fixture 默认值偷偷拍板。 |

冻结回包、Schema PASS、测试文件存在、局部函数 PASS 都只能证明相应机械链，不能写成真实内容能力。

## 5. 新增 15 条总览

| Requirement | 模块 | 当前代码状态 | 机械 | 语义 | 决定阻断 |
|---|---|---|---:|---:|---:|
| `AE-X-N01` | 跨模块 | 缺产品决定 | 4 | 0 | 2 |
| `AE-X-N02` | 跨模块 | 部分覆盖 | 5 | 1 | 0 |
| `M4-N01` | M4 | 缺产品决定 | 1 | 1 | 4 |
| `AE-X-N03` | 跨模块 | 缺代码 | 4 | 2 | 0 |
| `M8-N05` | M8 | 缺产品决定 | 4 | 0 | 2 |
| `M8-N06` | M8 | 缺代码 | 5 | 1 | 0 |
| `AE-M10-N01` | M10 | 部分覆盖 | 5 | 0 | 1 |
| `AE-M10-N02` | M10 | 缺代码 | 6 | 0 | 0 |
| `AE-M11-N01` | M11 | 部分覆盖 | 6 | 0 | 0 |
| `AE-AW-N01` | 作者工作区 | 部分覆盖 | 5 | 0 | 1 |
| `AE-AW-N02` | 作者工作区 | 缺代码 | 1 | 4 | 1 |
| `AE-AW-N03` | 作者工作区 | 缺产品决定 | 0 | 0 | 6 |
| `AE-AW-N04` | 作者工作区 | 缺代码 | 6 | 0 | 0 |
| `M9-N02` | M9 | 部分覆盖 | 6 | 0 | 0 |
| `M7-N01` | M7 | 部分覆盖 | 2 | 4 | 0 |

## 6. 90 个新增小测试

统一权重顺序：`22 / 18 / 18 / 14 / 16 / 12`，对应常见干净、常见脏输入、次常见结构变体、缺失/歧义/冲突、危险少见输入、失败恢复。每条合计 100。

### AE-X-N01｜用产品写完一章、章事实稿交棒后，不经过任何重新抽取，立刻就能规划下一章，事实一条不丢

- 模块：跨模块
- R03 来源：CZ 2026-08-20 口述拍板（双车道回流）。
- 当前代码状态：**缺产品决定**
- 当前边界：章事实稿原型、pending handover 与 plan preflight 已有；正式 C11／章节账落地、事实确认粒度和 planstore 完成交接仍未冻结。
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`

#### AT5-AE-X-N01-S01｜单章章事实稿交棒后零回抽开下一章

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE__FINAL_ACCEPTANCE_BLOCKED`；代码状态：`缺产品决定`
- 主变量：自产章单章交棒、登记与下一章 preflight 的身份链
- 输入合同 / 必需输入：
  - current C7/plan snapshot
  - chapter_fact_draft bundle
  - author handover action
  - M2/M3 call counter
- 输入合同 / 前置条件：
  - 章事实稿事实句与写法批注分栏
  - 所有输入仅为合成结构数据
- 输入合同 / 禁止假设：
  - pending 文件存在等于正式 C11
  - preflight PASS 等于事实已经入账
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造 1 个当前规划、1 份含 5 条有序事实句和 2 条独立写法批注的合成章事实稿；记录所有对象 ID、版本、SHA 和调用计数。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 正式确认规则闭合后，输入事实句一条不丢地登记到目标章节/事实 current；事实 ID、顺序、内容摘要与来源身份可逐条对账
  - M2_calls=0 且 M3_calls=0
  - 下一章规划入口读取刚完成章的 current 事实与章节身份
- 预期禁止：
  - 不得把写法批注写成事实
  - 不得声称正式事实账已完成，除非正式 owner 已接入
- 失败/恢复：任一步失败应返回可恢复 pending/blocked 状态；不得留下半个 current chapter 或虚假 handover complete。
- 机械断言：
  - formal_fact_count == input_fact_count
  - input_fact_id/source_identity/payload_sha256 与登记结果逐条一致
  - 调用日志没有 M2/M3
  - 下一章 preflight/consumer 的 source version 指向本次正式 current
  - 输出明确区分 pending/preflight/formal complete
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 自产章单章交棒、登记与下一章 preflight 的身份链的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；自产章单章交棒、登记与下一章 preflight 的身份链所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 自产章单章交棒、登记与下一章 preflight 的身份链的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 自产章单章交棒、登记与下一章 preflight 的身份链的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 自产章单章交棒、登记与下一章 preflight 的身份链的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N01-S01-01` — 任何自产章对象进入 M2 或 M3，或事实句条数/SHA 与交棒输入不一致
- 当前代码说明：当前只能执行 prototype/pending/preflight 子断言；正式 C11、事实确认和 planstore consumer 子断言暂不可通过。
- 暂不可执行 blocker：
  - 章事实稿正式 C11/章节账 owner 未冻结
  - 逐条或整包进入事实账的确认规则未冻结
- 版本对比字段：`chapter_fact_id`、`chapter_fact_version`、`payload_sha256`、`handover_state`、`m2_call_count`、`m3_call_count`、`next_plan_preflight_source`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`

#### AT5-AE-X-N01-S02｜连续两章自产交棒不串章

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE__FINAL_ACCEPTANCE_BLOCKED`；代码状态：`缺产品决定`
- 主变量：连续自产章节的顺序、current 指针与零回抽
- 输入合同 / 必需输入：
  - chapter 9 fact bundle
  - chapter 10 fact bundle
  - two plan snapshots
  - operation ledger
- 输入合同 / 前置条件：
  - 第二章引用第一章交棒回执作为前态
  - 每章对象 ID 唯一
- 输入合同 / 禁止假设：
  - 按显示章号猜 current
  - 用最新文件 mtime 代替版本链
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造第 9、10 章两份不同事实数、不同版本和不同 SHA 的章事实稿；按交棒→下一章规划→交棒顺序执行。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 第 9、10 章各自形成唯一正式 current 与历史链
  - 两章事实句逐章守恒且不串版
  - 两章 M2/M3 均为 0，下一章只读取直接前章的 current
- 预期禁止：
  - 不得让第 10 章覆盖第 9 章历史
  - 不得把两章事实数组拼接或重排
- 失败/恢复：第二章失败时第一章 current 仍可读；重试只补第二章，不重放第一章。
- 机械断言：
  - per-chapter formal_fact_count == per-chapter input count
  - chapter sequence/current pointer 单调且历史可读
  - 两章 operation_id、payload SHA、source identity 独立
  - 两章 M2/M3 调用计数均为 0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 连续自产章节的顺序、current 指针与零回抽的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；连续自产章节的顺序、current 指针与零回抽所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 连续自产章节的顺序、current 指针与零回抽的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 连续自产章节的顺序、current 指针与零回抽的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 连续自产章节的顺序、current 指针与零回抽的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N01-S02-01` — 任一章事实被另一章覆盖、串版，或重试导致第一章重复登记
- 当前代码说明：连续 pending/preflight 可测；两章正式 C11/事实/planstore 全链仍受 owner 和确认规则阻断。
- 暂不可执行 blocker：
  - 正式章节账/current owner 未冻结
- 版本对比字段：`chapter_id`、`chapter_fact_id`、`version`、`payload_sha256`、`current_pointer`、`history_count`、`operation_id`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`

#### AT5-AE-X-N01-S03｜逐条确认与整包确认未冻结时必须停

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：章事实稿进入事实账的确认粒度与高影响单签
- 输入合同 / 必需输入：
  - fact item metadata
  - impact class
  - handover bundle identity
- 输入合同 / 前置条件：
  - R14 只确认交棒绑定整包身份
  - 正式确认粒度明确标为开放
- 输入合同 / 禁止假设：
  - 沉默=整包确认
  - 低影响规则自动延伸到所有事实
  - 用测试作者代替 CZ 拍板
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：只构造包含普通事实和高影响事实标记的章事实稿元数据；不提供正文，不选择逐条或整包默认值。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 测试状态为 BLOCKED_NOT_SCORED
  - 输出列明缺失决定
  - 不创建正式事实记录
- 预期禁止：
  - 不得自行选择逐条/整包
  - 不得用 prototype 默认行为固化产品语义
- 失败/恢复：决定缺失时稳定失败关闭；重跑仍返回同一 blocker，不产生副作用。
- 机械断言：
  - blocked_by 非空且可定位
  - facts_write_count=0
  - c11_write_count=0
  - decision_version 为空而非伪造
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 章事实稿进入事实账的确认粒度与高影响单签的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；章事实稿进入事实账的确认粒度与高影响单签所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 章事实稿进入事实账的确认粒度与高影响单签的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 章事实稿进入事实账的确认粒度与高影响单签的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 章事实稿进入事实账的确认粒度与高影响单签的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N01-S03-01` — 在未冻结确认规则时产生任何 confirmed fact 或 handover complete
- 当前代码说明：这是合同/产品决定阻断，不是缺 fixture 或缺实现可绕过。
- 暂不可执行 blocker：
  - 章事实稿逐条/整包确认规则
  - 高影响事实与普通事实的签字组合规则
- 版本对比字段：`confirmation_granularity`、`high_impact_signoff_policy`、`decision_version`、`write_count`、`blocker_code`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`

#### AT5-AE-X-N01-S04｜自产章伪装外来 C10 身份必须拒绝

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：双车道身份防伪与错误路由拒绝
- 输入合同 / 必需输入：
  - chapter fact bundle
  - spoofed C10 envelope
  - source identity chain
- 输入合同 / 前置条件：
  - 真实来源是产品自产章事实稿
  - 没有冻结外来书稿证据
- 输入合同 / 禁止假设：
  - 字段名像 C10 就授予外来道权限
  - 把缺原文锚解释为可忽略
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造一份章事实稿对象并篡改 source_kind 为 external_frozen_prose/C10；同时保留原始作者工作区来源链供比对。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 身份校验拒绝 fake C10
  - 不调用 external route 的 M2
  - 不改写原始 lane identity
- 预期禁止：
  - 不得把自产章送回抽取
  - 不得静默修正成外来章继续跑
- 失败/恢复：拒绝后原始章事实稿和 pending 状态完整；修正身份后可从自产道重新提交。
- 机械断言：
  - rejection_code 稳定
  - m2_call_count=0
  - source_kind 未被覆盖
  - 原对象 SHA 不变
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 双车道身份防伪与错误路由拒绝的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；双车道身份防伪与错误路由拒绝所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 双车道身份防伪与错误路由拒绝的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 双车道身份防伪与错误路由拒绝的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 双车道身份防伪与错误路由拒绝的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N01-S04-01` — 伪造外来身份后被接受、触发 M2/M3，或生成外来书稿证据锚
- 当前代码说明：外来道有身份门；需要把自产来源身份接入同一防伪规则。
- 版本对比字段：`source_kind`、`c10_identity`、`lane`、`m2_call_count`、`rejection_code`、`payload_sha256`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

#### AT5-AE-X-N01-S05｜作者签字来源身份未冻结时不准自动补

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：AUTHOR_ATTESTATION 最小来源合同
- 输入合同 / 必需输入：
  - handover metadata
  - fact item IDs
  - missing attestation fields
- 输入合同 / 前置条件：
  - 来源不是外来书稿
  - 事实准备进入自产确认路径
- 输入合同 / 禁止假设：
  - 系统当前登录用户可自动补齐全部签字字段
  - 交棒时间等于故事生效时间
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造章事实稿交棒元数据，故意缺 signer/version/scope/effective story time；不附任何正文。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 返回缺字段清单
  - 不生成作者签字记录
  - 不降级成 AI 推断
- 预期禁止：
  - 不得伪造签字人/范围/时间
  - 不得因无原文证据走外来候选抽取
- 失败/恢复：补齐正式字段后允许重新校验；此前重试没有任何真值副作用。
- 机械断言：
  - attestation_write_count=0
  - missing_fields 精确
  - fact_status 保持未确认
  - source_identity 不变
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | AUTHOR_ATTESTATION 最小来源合同的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；AUTHOR_ATTESTATION 最小来源合同所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | AUTHOR_ATTESTATION 最小来源合同的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | AUTHOR_ATTESTATION 最小来源合同的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | AUTHOR_ATTESTATION 最小来源合同的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N01-S05-01` — 缺签字合同字段时仍写入 AUTHOR_ATTESTATION 或 confirmed fact
- 当前代码说明：R14 方向已定，但机器字段与 owner 未冻结。
- 暂不可执行 blocker：
  - AUTHOR_ATTESTATION 正式字段/owner
  - 故事时间、系统时间与可见范围的必填规则
- 版本对比字段：`signer_id`、`attestation_version`、`scope`、`story_effective_time`、`system_time`、`visibility`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`

#### AT5-AE-X-N01-S06｜交棒 pending 后崩溃可重启恢复且幂等

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：章事实稿交棒的持久化、恢复和重复提交
- 输入合同 / 必需输入：
  - chapter fact bundle
  - operation_id
  - failure injection point
  - fresh workspace instance
- 输入合同 / 前置条件：
  - pending receipt 已 fsync/原子替换
  - 正式下游写入在当前实现中为 0
- 输入合同 / 禁止假设：
  - 目录 mtime 决定恢复对象
  - 相同 operation_id 生成新 handover
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：在章事实稿 pending 已持久化、正式 downstream 尚未执行时注入崩溃；重建全新 workspace，使用同一 operation_id 重试两次。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 重启读回同一 pending
  - 重复提交返回同一结果或明确 replay
  - 不产生第二份对象
- 预期禁止：
  - 不得把 pending 冒充 handover complete
  - 不得留下半写 JSON 或临时文件
- 失败/恢复：恢复扫描能区分可重试与冲突；payload 变化但 operation_id 相同必须拒绝。
- 机械断言：
  - pending SHA 一致
  - operation replay 稳定
  - temp file count=0
  - conflicting payload rejected
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 章事实稿交棒的持久化、恢复和重复提交的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；章事实稿交棒的持久化、恢复和重复提交所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 章事实稿交棒的持久化、恢复和重复提交的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 章事实稿交棒的持久化、恢复和重复提交的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 章事实稿交棒的持久化、恢复和重复提交的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N01-S06-01` — 崩溃后丢 pending、重复写两份，或同 operation_id 不同 payload 被接受
- 当前代码说明：pending workspace 的重启/读回/冲突可测；跨 C11/事实账恢复尚不在当前能力内。
- 版本对比字段：`operation_id`、`payload_sha256`、`pending_state`、`generation_id`、`replay_count`、`temp_member_count`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`

---

### AE-X-N02｜同一本书里外来旧章和自产新章并存时，系统知道每一章走哪条道，不把自产章误送回抽取

- 模块：跨模块
- R03 来源：CZ 2026-08-20 口述拍板（双车道回流）。
- 当前代码状态：**部分覆盖**
- 当前边界：外来道 current C10→C11→C1→M2 已有身份门；自产章只有 prototype/pending，混合同书全链未完成。
- 证据路径：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

#### AT5-AE-X-N02-S01｜同书外来旧章与自产新章正确分道

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：混合同书逐章 lane identity 与路由
- 输入合同 / 必需输入：
  - 3 external frozen chapter identities
  - 2 product chapter fact identities
  - shared project ledger
- 输入合同 / 前置条件：
  - 外来样本有合法冻结来源与可回取位置
  - 自产样本无书稿证据
- 输入合同 / 禁止假设：
  - 按章号早晚推断车道
  - 同项目只允许一种车道
- 材料分类：`REAL_NOVEL_REQUIRED`
- 材料配方：抽取一部获授权脱敏小说的 3 个外来章样本，仅保留 source ID、SHA、章边界和定位；另造 2 个合成自产章事实稿。不得把正文写入设计文件。
- 抽样要求：
  - 至少 2 个题材频率层级
  - 每个外来章只记录脱敏定位与 SHA
  - 不生成 Gold
- 正文边界：只登记脱敏材料配方、抽样层级、定位与 SHA；本设计不夹带正文、不生成 Gold。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 外来章进入 M2/M3
  - 自产章 M2/M3=0
  - 每章事实来源身份可区分
- 预期禁止：
  - 不得把外来章直接当 confirmed fact
  - 不得把自产章误送回抽取
- 失败/恢复：某一章失败只阻断该章与依赖项；其他章的 lane/current 身份不被改写。
- 机械断言：
  - lane_by_chapter 精确
  - external call counters >0 only where expected
  - product call counters=0
  - source identities distinct
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 混合同书逐章 lane identity 与路由的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；混合同书逐章 lane identity 与路由所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 混合同书逐章 lane identity 与路由的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 混合同书逐章 lane identity 与路由的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 混合同书逐章 lane identity 与路由的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N02-S01-01` — 任一自产章触发 M2/M3，或任一外来章绕过外来确认门成为事实
- 当前代码说明：外来道身份路由可直接测；自产正式直登仍只能测到 pending/preflight。
- 版本对比字段：`chapter_id`、`lane`、`source_kind`、`source_version`、`m2_calls`、`m3_calls`、`fact_source_identity`
- 证据路径：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

#### AT5-AE-X-N02-S02｜脏 ZIP、重复显示章号和混合顺序不串道

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：车道判定不依赖文件名、显示章号或 ZIP 顺序
- 输入合同 / 必需输入：
  - dirty external ZIP manifest
  - product chapter identities
  - internal chapter registry
- 输入合同 / 前置条件：
  - 内部 ID 唯一
  - 外来材料与自产对象都有明确 source_kind
- 输入合同 / 禁止假设：
  - 按文件名后缀/显示号判 lane
  - 隐藏文件自动当章节
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 ZIP：外来章文件名乱序、重复显示章号、隐藏文件；自产章使用内部 chapter_id 且显示号重叠。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 只按受控身份分道
  - 重复显示号不碰撞
  - 非章成员进入隔离回执
- 预期禁止：
  - 不得覆盖同显示号的不同内部章
  - 不得静默丢成员
- 失败/恢复：解析失败返回成员级错误和可重试清单；已登记的自产对象不受 ZIP 失败影响。
- 机械断言：
  - member coverage receipt 完整
  - chapter_id uniqueness
  - lane count exact
  - no overwrite
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 车道判定不依赖文件名、显示章号或 ZIP 顺序的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；车道判定不依赖文件名、显示章号或 ZIP 顺序所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 车道判定不依赖文件名、显示章号或 ZIP 顺序的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 车道判定不依赖文件名、显示章号或 ZIP 顺序的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 车道判定不依赖文件名、显示章号或 ZIP 顺序的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N02-S02-01` — 因文件名/排序把自产章判成外来章，或重复显示号造成覆盖
- 当前代码说明：M1/外来道已有部分输入与身份机械能力；混合 lane registry 需补齐。
- 版本对比字段：`archive_member_id`、`chapter_id`、`display_number`、`source_kind`、`lane`、`coverage_status`
- 证据路径：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

#### AT5-AE-X-N02-S03｜混合事实来源在人读查询中不混淆

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺产品决定`
- 主变量：外来书稿证据与自产作者签字事实的等权使用和身份可见
- 输入合同 / 必需输入：
  - confirmed external fact cards
  - synthetic author-attested fact cards
  - query set
- 输入合同 / 前置条件：
  - 所有输入均已确认
  - 事实内容不要求模型复述原文
- 输入合同 / 禁止假设：
  - 有原文的事实更高权
  - 作者签字事实自动降级为推断
- 材料分类：`REAL_NOVEL_REQUIRED`
- 材料配方：从获授权脱敏外来章抽取 8—12 个已确认事实身份卡，只保留事实卡、证据定位和来源标签；混入 8—12 个合成作者签字事实。人工构造查询，不写 Gold 答案。
- 抽样要求：
  - 至少 2 种题材频率
  - 外来事实只保留脱敏卡和证据定位
  - 不生成 Gold，人工按评分尺判断
- 正文边界：只登记脱敏材料配方、抽样层级、定位与 SHA；本设计不夹带正文、不生成 Gold。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 回答使用两类事实时语义一致
  - 每条引用保留来源身份
  - 无法支持时明确 unknown
- 预期禁止：
  - 不得隐藏来源差异
  - 不得把计划/候选混入答案
- 失败/恢复：模型失败或不确定时返回可复核引用清单，不写新事实。
- 机械断言：
  - 机械层检查引用 ID 均来自输入
  - 来源标签不丢
  - 未确认 ID 命中数=0
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 两类已确认事实同等可用于回答
  - 身份标签逐条可见
  - 不把计划/候选当事实
  - 未知时不编造
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 外来书稿证据与自产作者签字事实的等权使用和身份可见未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：两类已确认事实同等可用于回答；身份标签逐条可见；不把计划/候选当事实；未知时不编造。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：两类已确认事实同等可用于回答；身份标签逐条可见；不把计划/候选当事实；未知时不编造；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-AE-X-N02-S03-01` — 把作者签字事实说成 AI 推断，或把外来证据型事实与自产事实混成无来源结论
- 当前代码说明：语义评分可先设计；AUTHOR_ATTESTATION 正式合同和混合同书全链未闭合。
- 版本对比字段：`query_id`、`used_fact_ids`、`source_identity_set`、`unsupported_claim_count`、`unknown_count`
- 证据路径：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

#### AT5-AE-X-N02-S04｜外来旧章修订不改自产章车道

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：单车道版本变化的影响半径
- 输入合同 / 必需输入：
  - external chapter v1/v2
  - product chapter fact v1
  - dependency map
- 输入合同 / 前置条件：
  - 只有外来章内容变化
  - 自产章身份和 SHA 固定
- 输入合同 / 禁止假设：
  - 项目内任一章变化就重判全部车道
  - 最新更新时间决定所有 current
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：同一项目含外来章 v1/v2 和自产章 fact-v1；更新外来章并触发旧证据 stale。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 外来章证据/候选按版本更新
  - 自产章 lane/SHA/M2/M3 计数不变
- 预期禁止：
  - 不得重抽自产章
  - 不得把外来 v1 继续冒充 current
- 失败/恢复：外来修订失败时保持 v1 current 或明确 pending；自产章始终不受影响。
- 机械断言：
  - external current version
  - external stale markers
  - product lane
  - product SHA
  - product call counters
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 单车道版本变化的影响半径的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；单车道版本变化的影响半径所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 单车道版本变化的影响半径的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 单车道版本变化的影响半径的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 单车道版本变化的影响半径的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N02-S04-01` — 外来章修订导致自产章进入 M2/M3 或自产来源身份变化
- 当前代码说明：外来 current/version 门已有；跨 lane 影响半径需新增集成验证。
- 版本对比字段：`external_version`、`external_current`、`product_version`、`product_lane`、`product_sha256`、`affected_scope`
- 证据路径：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

#### AT5-AE-X-N02-S05｜双向身份伪造与跨项目猜号均拒绝

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：lane identity、项目隔离和路径安全
- 输入合同 / 必需输入：
  - spoofed envelopes
  - two project registries
  - invalid source refs
- 输入合同 / 前置条件：
  - 作者 A/B 项目隔离
  - 所有合法对象有不可猜内部 ID
- 输入合同 / 禁止假设：
  - 显示名或路径可授予权限
  - source_kind 字符串无需来源链
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造四种攻击：外来章伪装自产、自产章伪装外来、项目 A 复用项目 B 的 chapter_id、绝对路径/../source ref。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 四类攻击全部稳定拒绝
  - 合法控制组可继续
  - 错误不泄露别的项目细节
- 预期禁止：
  - 不得读取或改写他人项目
  - 不得自动转换 lane 以求继续
- 失败/恢复：攻击失败不创建目录、候选、current 或审计外的业务对象。
- 机械断言：
  - rejection codes stable
  - cross-project read/write count=0
  - tree digest unchanged
  - valid control passes
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | lane identity、项目隔离和路径安全的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；lane identity、项目隔离和路径安全所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | lane identity、项目隔离和路径安全的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | lane identity、项目隔离和路径安全的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | lane identity、项目隔离和路径安全的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N02-S05-01` — 任一伪造身份或跨项目引用被接受并触发业务读取/写入
- 当前代码说明：现有 workspace 与 external route 有隔离/身份门；需覆盖双车道联合攻击面。
- 版本对比字段：`author_id`、`project_id`、`chapter_id`、`lane_claim`、`source_ref`、`result_code`、`tree_digest`
- 证据路径：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

#### AT5-AE-X-N02-S06｜混合项目中断恢复不重复抽取或直登

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：混合车道 operation ledger、恢复点和幂等
- 输入合同 / 必需输入：
  - ordered route operations
  - failure injection points
  - operation IDs
  - fresh process instances
- 输入合同 / 前置条件：
  - 每章 operation_id 独立
  - 外来与自产恢复状态分开
- 输入合同 / 禁止假设：
  - 全项目从头重放
  - 恢复时按目录最新文件猜位置
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：按外来章→自产章→外来章顺序执行；在第二个外来章 M2 前和自产 pending 后分别注入崩溃，重启两次。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 外来章只补未完成步骤
  - 自产章保持零 M2/M3
  - 已完成章不重复登记
- 预期禁止：
  - 不得因恢复把自产 pending 送入外来抽取
  - 不得丢失失败原因
- 失败/恢复：相同 payload 重放幂等；相同 operation_id 不同 payload 作为冲突拒绝。
- 机械断言：
  - per-chapter state machine exact
  - call counters no duplicate
  - history count stable
  - conflict replay rejected
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 混合车道 operation ledger、恢复点和幂等的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；混合车道 operation ledger、恢复点和幂等所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 混合车道 operation ledger、恢复点和幂等的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 混合车道 operation ledger、恢复点和幂等的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 混合车道 operation ledger、恢复点和幂等的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N02-S06-01` — 恢复后重复抽取外来章、重复登记自产章，或任一 lane 被切换
- 当前代码说明：各局部 workspace 有恢复切片；混合路线统一 operation owner 尚未完成。
- 版本对比字段：`operation_id`、`chapter_id`、`lane`、`step_state`、`call_count`、`payload_sha256`、`replay_result`
- 证据路径：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`、`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

---

### M4-N01｜自产章的事实带「作者签字」身份入账，不需要原文证据；查询和体检同等对待、身份始终可见

- 模块：M4
- R03 来源：CZ 2026-08-20 口述拍板（真源口径）。
- 当前代码状态：**缺产品决定**
- 当前边界：R14 已拍作者签字身份方向，但章事实稿逐条或整包确认规则、AUTHOR_ATTESTATION 正式写入合同和 M6/M7 同等消费门未冻结。
- 证据路径：`02_current_route/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`

#### AT5-M4-N01-S01｜无原文证据的作者签字事实按正式合同入账

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：AUTHOR_ATTESTATION 写入最小合同与无原文证据合法性
- 输入合同 / 必需输入：
  - fact item
  - author identity
  - attestation metadata
- 输入合同 / 前置条件：
  - 事实来自自产章事实稿
  - 作者明确签字
- 输入合同 / 禁止假设：
  - 缺原文证据必拒绝
  - 登录态自动等于签字
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造 1 条自产事实元数据、签字主体、作用范围、故事生效时间与可见范围；不附正文。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 决定冻结前 BLOCKED_NOT_SCORED
  - 冻结后应生成可回源 attestation source
- 预期禁止：
  - 不得降级为 AI inference
  - 不得伪造 evidence anchor
- 失败/恢复：合同未冻结时零真值写入；字段补齐并有 owner 后才允许重试。
- 机械断言：
  - no prose/evidence field fabricated
  - source kind reserved
  - write_count=0 while blocked
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | AUTHOR_ATTESTATION 写入最小合同与无原文证据合法性的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；AUTHOR_ATTESTATION 写入最小合同与无原文证据合法性所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | AUTHOR_ATTESTATION 写入最小合同与无原文证据合法性的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | AUTHOR_ATTESTATION 写入最小合同与无原文证据合法性的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | AUTHOR_ATTESTATION 写入最小合同与无原文证据合法性的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M4-N01-S01-01` — 无正式签字合同仍写入 confirmed fact，或伪造原文 evidence
- 当前代码说明：方向已拍，但字段、确认动作和 owner 未冻结。
- 暂不可执行 blocker：
  - AUTHOR_ATTESTATION schema/owner
  - 章事实稿确认粒度
- 版本对比字段：`fact_id`、`source_kind`、`signer_id`、`scope`、`story_effective_time`、`visibility`、`write_count`
- 证据路径：`02_current_route/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`

#### AT5-M4-N01-S02｜同一命题同时有书稿证据与作者签字时保留多来源

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：多来源合并、身份展示和不重复发事实
- 输入合同 / 必需输入：
  - fact identity
  - external evidence ref
  - author attestation ref
- 输入合同 / 前置条件：
  - 两个来源都合法
  - 命题内容同一
- 输入合同 / 禁止假设：
  - 后来的来源覆盖并删除旧来源
  - 重复来源发两个 fact_id
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造同一 fact_id 的外来书稿 evidence source 与后续 author attestation source 元数据；不带正文，只带受控 source ref。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 合同冻结前明确 blocker
  - 冻结后同一 fact 保留来源集合与历史
- 预期禁止：
  - 不得把两个来源折成无身份的 confirmed
  - 不得静默改变可见范围
- 失败/恢复：任一来源写失败不留下半来源集合；重试幂等。
- 机械断言：
  - single fact_id
  - source count exact
  - history preserved
  - no duplicate fact
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 多来源合并、身份展示和不重复发事实的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；多来源合并、身份展示和不重复发事实所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 多来源合并、身份展示和不重复发事实的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 多来源合并、身份展示和不重复发事实的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 多来源合并、身份展示和不重复发事实的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M4-N01-S02-01` — 删除任一合法来源、重复发事实，或来源身份在查询投影中消失
- 当前代码说明：多来源事实的权威/显示/修订合同未在当前代码冻结。
- 暂不可执行 blocker：
  - 多来源事实 source set 合同
  - 来源冲突/优先级规则
- 版本对比字段：`fact_id`、`source_ids`、`source_kinds`、`source_versions`、`visibility`、`history_count`
- 证据路径：`02_current_route/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`

#### AT5-M4-N01-S03｜作者私有真相与读者已释放可见范围

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：AUTHOR_ATTESTATION 可见范围与释放迁移
- 输入合同 / 必需输入：
  - private attestation
  - release event metadata
  - consumer scopes
- 输入合同 / 前置条件：
  - 初态只对作者可见
  - 后续释放应挂同一事实
- 输入合同 / 禁止假设：
  - 新建第二条事实代替可见范围迁移
  - 私有内容默认给 M9/读者视图
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造同一作者签字事实的 AUTHOR 私有初态和后续读者释放事件元数据，不含正文。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 合同冻结前 blocked
  - 冻结后同一 fact 补释放来源/可见范围
- 预期禁止：
  - 不得向无权消费者泄露
  - 不得抹掉私有历史
- 失败/恢复：释放写失败时保留私有 current；不出现半公开状态。
- 机械断言：
  - fact identity stable
  - visibility transitions explicit
  - unauthorized read count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | AUTHOR_ATTESTATION 可见范围与释放迁移的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；AUTHOR_ATTESTATION 可见范围与释放迁移所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | AUTHOR_ATTESTATION 可见范围与释放迁移的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | AUTHOR_ATTESTATION 可见范围与释放迁移的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | AUTHOR_ATTESTATION 可见范围与释放迁移的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M4-N01-S03-01` — 私有作者 Canon 在未释放前进入读者视图，或释放后新建重复事实
- 当前代码说明：可见范围字段方向存在，但章事实稿作者签字接线未冻结。
- 暂不可执行 blocker：
  - 作者签字事实可见范围/释放迁移合同
- 版本对比字段：`fact_id`、`visibility`、`release_source_id`、`authorized_consumers`、`history`
- 证据路径：`02_current_route/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`

#### AT5-M4-N01-S04｜签字元数据缺失、冲突或作用域不唯一时失败关闭

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：作者签字来源的完整性、冲突和失败关闭
- 输入合同 / 必需输入：
  - attestation variants
  - operation IDs
  - existing fact state
- 输入合同 / 前置条件：
  - 已有真值只读快照可比对
- 输入合同 / 禁止假设：
  - 用系统时间补故事时间
  - 用 project owner 自动补 signer
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：生成缺 signer、缺 scope、故事时间冲突、同 operation_id 不同签字内容四组元数据。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 每组返回精确 blocker
  - 真值写计数为 0
  - 已有 fact 不变
- 预期禁止：
  - 不得模糊报成功
  - 不得将冲突降为普通警告
- 失败/恢复：修正字段后可重试；原冲突 operation 留审计但不生效。
- 机械断言：
  - missing/conflict codes exact
  - existing digest unchanged
  - no partial source
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 作者签字来源的完整性、冲突和失败关闭的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；作者签字来源的完整性、冲突和失败关闭所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 作者签字来源的完整性、冲突和失败关闭的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 作者签字来源的完整性、冲突和失败关闭的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 作者签字来源的完整性、冲突和失败关闭的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M4-N01-S04-01` — 任一缺失/冲突签字被接受，或已有事实被半覆盖
- 当前代码说明：必填字段与冲突政策未冻结，所以当前不可执行。
- 暂不可执行 blocker：
  - AUTHOR_ATTESTATION required fields
  - operation conflict policy
- 版本对比字段：`signer_id`、`scope`、`story_time`、`operation_id`、`payload_sha256`、`result_code`、`fact_digest`
- 证据路径：`02_current_route/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`

#### AT5-M4-N01-S05｜伪造 source_kind=AUTHOR_ATTESTATION 不授予权力

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE__FINAL_ACCEPTANCE_BLOCKED`；代码状态：`缺产品决定`
- 主变量：作者签字来源身份防伪
- 输入合同 / 必需输入：
  - fake source envelope
  - valid signed receipt control
  - fact candidate
- 输入合同 / 前置条件：
  - 来源身份必须由受控 receipt 证明
- 输入合同 / 禁止假设：
  - 字段名即可授权
  - 测试 fixture 白名单自动可信
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造只有 source_kind 字符串、没有受控签字 receipt/主体/版本的事实候选；附合法控制组。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 伪造对象被拒
  - 合法控制组通过身份层
  - 均不自动 confirmed
- 预期禁止：
  - 不得把 fake source 降为 AI 推断继续
  - 不得泄露内部签字 token
- 失败/恢复：拒绝不改候选/事实存储；合法控制组仍等待正式确认 owner。
- 机械断言：
  - receipt verification outcome
  - write_count=0
  - candidate digest unchanged
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 作者签字来源身份防伪的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；作者签字来源身份防伪所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 作者签字来源身份防伪的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 作者签字来源身份防伪的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 作者签字来源身份防伪的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M4-N01-S05-01` — 仅凭 source_kind 字符串获得 AUTHOR_ATTESTATION 权限或进入 confirmed
- 当前代码说明：防伪测试可零 API 设计；正式 receipt issuer/validator 仍未冻结。
- 暂不可执行 blocker：
  - 签字 receipt issuer/validator 正式合同
- 版本对比字段：`source_kind`、`receipt_id`、`signer_id`、`verification_result`、`fact_status`
- 证据路径：`02_current_route/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`

#### AT5-M4-N01-S06｜M6 查询与 M7 体检对两类已确认事实同等消费

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺产品决定`
- 主变量：已确认事实的下游等权消费与来源身份可见
- 输入合同 / 必需输入：
  - paired confirmed facts
  - M6 queries
  - M7 check tasks
- 输入合同 / 前置条件：
  - 两类事实均通过正式确认
  - 测试只比较身份偏差，不比较模型排名
- 输入合同 / 禁止假设：
  - 有原文锚的事实自动更可信
  - 作者签字事实可忽略
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 12 条书稿证据型事实和 12 条作者签字型事实，内容难度与影响等级配对；构造 M6 查询和 M7 冲突检查任务，不生成 Gold。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 语义判断不因来源类别偏置
  - 引用保留 source kind
  - 冲突规则同等适用
- 预期禁止：
  - 不得把 author-attested 当 inference
  - 不得隐藏身份以伪装一致
- 失败/恢复：模型无法判断时返回待复核，不产生新事实或修改旧账。
- 机械断言：
  - used fact IDs are input-confirmed
  - source labels preserved
  - rejected/planned usage=0
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 配对事实在查询和体检中同等可用
  - 来源身份始终可见
  - 冲突与 unknown 规则不因来源改变
  - 不混入未确认内容
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 已确认事实的下游等权消费与来源身份可见未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：配对事实在查询和体检中同等可用；来源身份始终可见；冲突与 unknown 规则不因来源改变；不混入未确认内容。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：配对事实在查询和体检中同等可用；来源身份始终可见；冲突与 unknown 规则不因来源改变；不混入未确认内容；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-M4-N01-S06-01` — 系统性忽略作者签字事实，或无理由优待书稿证据型事实
- 当前代码说明：语义评测可设计；正式作者签字写入与 M6/M7 consumer gate 未完成。
- 版本对比字段：`task_id`、`input_source_kind`、`used_fact_ids`、`decision`、`reason`、`source_label_visible`
- 证据路径：`02_current_route/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/02_ATOMIC_EXPECTATIONS.json`、`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`

---

### AE-X-N03｜渲染出的正文每段都能指回它来自哪几条事实句；作者手改正文改出新信息时，只报差异并升级成候选，不整章重抽

- 模块：跨模块
- R03 来源：CZ 2026-08-20 口述拍板（双车道唯一例外）。
- 当前代码状态：**缺代码**
- 当前边界：当前包未见章事实稿→渲染段落 source map、局部 diff→candidate 和失败恢复 owner；不得用整章抽取路线替代。
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`

#### AT5-AE-X-N03-S01｜渲染段落到事实句的一对多 source map

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：段落→事实句 source map 的完整性和可回源性
- 输入合同 / 必需输入：
  - chapter fact items
  - rendered paragraph identities
  - source map
- 输入合同 / 前置条件：
  - 事实句与写法批注分开
  - 段落 ID 稳定
- 输入合同 / 禁止假设：
  - 按文本相似度临时猜来源
  - 只存第一条来源
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造 5 条事实句、3 个渲染段落；其中一个段落引用 3 条事实，两个段落各引用 1—2 条。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 每段来源集合完整
  - 每个引用 fact_id 存在且版本匹配
  - 无孤儿映射
- 预期禁止：
  - 不得把写法批注作为事实来源
  - 不得声称渲染文是新真值
- 失败/恢复：映射生成失败时渲染输出标不可交付；不得留下可导出但不可回源的段落。
- 机械断言：
  - foreign key closure
  - source set cardinality exact
  - version/SHA bound
  - orphan count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 段落→事实句 source map 的完整性和可回源性的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；段落→事实句 source map 的完整性和可回源性所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 段落→事实句 source map 的完整性和可回源性的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 段落→事实句 source map 的完整性和可回源性的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 段落→事实句 source map 的完整性和可回源性的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N03-S01-01` — 任一渲染段落无法回到完整来源事实集合，或映射引用不存在版本
- 当前代码说明：当前包未见 renderer/source-map owner；这是未来零 API 机械合同。
- 版本对比字段：`paragraph_id`、`fact_ids`、`fact_versions`、`source_map_version`、`payload_sha256`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`

#### AT5-AE-X-N03-S02｜事实句拆分/合并造成多对多映射仍可追

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：多对多 source map、顺序与重排稳定性
- 输入合同 / 必需输入：
  - fact bundle
  - paragraph render plan
  - reorder operation
- 输入合同 / 前置条件：
  - 映射身份独立于段落序号
- 输入合同 / 禁止假设：
  - 数组位置即身份
  - 重排后重建新事实 ID
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造两条事实被合并进一段、同一事实跨两段呈现、段落重排三种结构。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 重排前后来源集合不变
  - 段落 ID 或迁移映射明确
  - 事实 ID 不变
- 预期禁止：
  - 不得因一事实跨段而重复发事实
  - 不得静默丢掉合并来源
- 失败/恢复：重排中断可回到旧 map；成功提交后 old→new mapping 可审计。
- 机械断言：
  - source set equality
  - fact uniqueness
  - order field changes only
  - migration map complete
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 多对多 source map、顺序与重排稳定性的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；多对多 source map、顺序与重排稳定性所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 多对多 source map、顺序与重排稳定性的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 多对多 source map、顺序与重排稳定性的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 多对多 source map、顺序与重排稳定性的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N03-S02-01` — 段落重排导致事实来源丢失、重复或不可回到旧段落
- 当前代码说明：无现成 source-map runtime。
- 版本对比字段：`paragraph_id`、`order`、`fact_ids`、`old_to_new_map`、`map_generation`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`

#### AT5-AE-X-N03-S03｜只改写法不新增信息时不报事实候选

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：写法变化与新事实变化的语义区分
- 输入合同 / 必需输入：
  - source paragraph pairs
  - source map
  - existing fact items
- 输入合同 / 前置条件：
  - 每组只允许一个写法变量变化
- 输入合同 / 禁止假设：
  - 任何字面 diff 都生成候选
  - 用字符串相等代替语义判断
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 12 组原段/改段 minimal pairs：语序、修辞、视角、节奏变化，但命题、限定和状态不变；不生成 Gold，只预注册变化维度。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 写法-only 组候选数为 0 或明确 non-truth diff
  - 来源映射保持
- 预期禁止：
  - 不得整章重抽
  - 不得把修辞变化写进事实账
- 失败/恢复：不确定样本进入待复核，不自动入账；失败不改变原 source map。
- 机械断言：
  - candidate IDs belong only to reviewed diffs
  - full-chapter extraction call=0
  - truth write=0
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 识别命题是否变化
  - 保留否定/条件/时间限定
  - 纯写法变化不产事实候选
  - 不确定时进入待复核而非自动确认
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 写法变化与新事实变化的语义区分未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：识别命题是否变化；保留否定/条件/时间限定；纯写法变化不产事实候选；不确定时进入待复核而非自动确认。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：识别命题是否变化；保留否定/条件/时间限定；纯写法变化不产事实候选；不确定时进入待复核而非自动确认；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-AE-X-N03-S03-01` — 把纯写法改动升级成 confirmed/extracted fact，或触发整章 M2/M3
- 当前代码说明：需要未来语义判断和局部 diff runtime。
- 版本对比字段：`pair_id`、`diff_type`、`candidate_count`、`review_state`、`m2_calls`、`m3_calls`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`

#### AT5-AE-X-N03-S04｜局部新增信息只生成局部候选并附差异证据

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：新信息识别、候选粒度与局部证据
- 输入合同 / 必需输入：
  - before/after paragraphs
  - source map
  - diff coordinates
- 输入合同 / 前置条件：
  - 改动范围明确
  - 原章事实稿已交棒
- 输入合同 / 禁止假设：
  - 整段全部当新事实
  - 新信息自动 confirmed
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 12 组局部改动：新增状态、规则、关系、知情或物品转手；每组只改一个段落，保留前后版本和 diff 坐标，不生成 Gold。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 只产与新信息对应的候选
  - 候选附 before/after/diff/source facts
  - 其他段不处理
- 预期禁止：
  - 不得重抽整章
  - 不得丢否定/条件/时间限定
- 失败/恢复：语义不确定时只产待复核线索；任何候选写失败不影响原事实与书稿版本。
- 机械断言：
  - candidate scope within changed paragraph
  - unchanged paragraph call count=0
  - truth write=0
  - diff refs complete
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 只识别真正新增/改变的命题
  - 候选粒度不吞并未改内容
  - 保留限定和不确定性
  - 候选不自动确认
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 新信息识别、候选粒度与局部证据未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：只识别真正新增/改变的命题；候选粒度不吞并未改内容；保留限定和不确定性；候选不自动确认。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：只识别真正新增/改变的命题；候选粒度不吞并未改内容；保留限定和不确定性；候选不自动确认；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-AE-X-N03-S04-01` — 差异自动入事实账、候选跨出修改范围，或整章重新切段抽取
- 当前代码说明：未来模型语义例；当前没有局部 diff candidate runtime。
- 版本对比字段：`paragraph_id`、`diff_span`、`candidate_ids`、`candidate_status`、`source_fact_ids`、`m2_calls`、`m3_calls`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`

#### AT5-AE-X-N03-S05｜复制、删除、重排与新信息混合时映射不误报

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：复杂 diff 的机械分类与影响范围
- 输入合同 / 必需输入：
  - old/new paragraph manifests
  - operation log
  - source map
- 输入合同 / 前置条件：
  - 段落有稳定内部 ID/指纹
  - 新信息以结构占位符表达
- 输入合同 / 禁止假设：
  - 复制=新事实
  - 删除=自动撤销事实
  - 重排=内容变化
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造一个版本变更：复制一段、删除一段、重排两段、在另一段新增结构化占位事实；预先给出操作日志。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 复制/重排只更新位置映射
  - 删除进入影响清单不自动改史
  - 新增段进入候选入口
- 预期禁止：
  - 不得静默撤销 confirmed fact
  - 不得对未变段生成候选
- 失败/恢复：操作日志与文本 manifest 冲突时失败关闭并列明差异；不自动选一边。
- 机械断言：
  - operation classification exact
  - candidate scope exact
  - truth mutation count=0
  - conflict reported
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 复杂 diff 的机械分类与影响范围的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；复杂 diff 的机械分类与影响范围所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 复杂 diff 的机械分类与影响范围的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 复杂 diff 的机械分类与影响范围的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 复杂 diff 的机械分类与影响范围的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N03-S05-01` — 复制或重排导致新候选，删除直接撤销真值，或未变段被处理
- 当前代码说明：可以作为纯机械 diff contract；无当前实现。
- 版本对比字段：`paragraph_id`、`operation_kind`、`old_position`、`new_position`、`candidate_flag`、`impact_flag`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`

#### AT5-AE-X-N03-S06｜source map 与候选提交中断后的原子恢复

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：局部 diff 流程的跨工件恢复和幂等
- 输入合同 / 必需输入：
  - old map
  - new map draft
  - candidate manifest
  - operation_id
  - failure point
- 输入合同 / 前置条件：
  - 旧版本完整可读
  - 提交需有 manifest/generation
- 输入合同 / 禁止假设：
  - 仅凭文件存在判断成功
  - 不同 payload 可复用 operation_id
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：在新 map 写入后、candidate manifest 提交前注入崩溃；重启恢复，同 operation_id 同/不同 payload 各重试。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 恢复到旧完整版本或新完整版本
  - 不出现 map/candidate 半配对
  - 冲突重放拒绝
- 预期禁止：
  - 不得把预演文件说成正式交棒
  - 不得丢旧版本
- 失败/恢复：恢复扫描明确 READY_TO_RETRY/COMMITTED/CONFLICT；任何状态都可解释。
- 机械断言：
  - commit manifest closure
  - generation consistency
  - temp files cleaned
  - replay semantics exact
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 局部 diff 流程的跨工件恢复和幂等的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；局部 diff 流程的跨工件恢复和幂等所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 局部 diff 流程的跨工件恢复和幂等的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 局部 diff 流程的跨工件恢复和幂等的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 局部 diff 流程的跨工件恢复和幂等的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-X-N03-S06-01` — 出现新 map 但无 candidate 状态且被当成功，或崩溃后旧版不可读
- 当前代码说明：当前无 owner；设计要求未来实现跨工件护栏。
- 版本对比字段：`operation_id`、`generation_id`、`map_sha256`、`candidate_manifest_sha256`、`commit_state`、`recovery_action`
- 证据路径：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`、`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`

---

### M8-N05｜发给作者的每张选择卡全文入账、带编号和版本；隔几天再选，系统仍知道每个选项当时的完整含义

- 模块：M8
- R03 来源：CZ 2026-08-20 口述拍板（M8 缺口：没人保存）。
- 当前代码状态：**缺产品决定**
- 当前边界：局部选择目标可绑定 C7 snapshot 与完整 option record，但身份是 transport_only_no_plan_write；稳定选择卡 owner 与持久化位置未冻结。
- 证据路径：`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`

#### AT5-M8-N05-S01｜选择卡全文、编号、版本的稳定 owner

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：选择卡全文持久化对象的 owner 与权威身份
- 输入合同 / 必需输入：
  - C7 snapshot
  - full option records
  - card metadata proposal
- 输入合同 / 前置条件：
  - 局部 target 仅 transport-only
  - 正式 owner 未冻结
- 输入合同 / 禁止假设：
  - 把 UI 缓存当 owner
  - 用 planstore 候选文件名临时顶替正式卡
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造 A/B/C 三个完整 option record 元数据（理由、代价、影响、来源计划版本），但不指定正式选择卡存储 owner。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 返回 BLOCKED_NOT_SCORED
  - 列明 owner/identity/version 需要决定
  - 不写正式选择卡
- 预期禁止：
  - 不得把局部 target PASS 冒充全文已持久化
  - 不得只存短标签
- 失败/恢复：重复执行保持零正式写入；决定冻结前不建立私有默认 owner。
- 机械断言：
  - formal_card_write_count=0
  - blocked_by exact
  - option bodies unchanged
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 选择卡全文持久化对象的 owner 与权威身份的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；选择卡全文持久化对象的 owner 与权威身份所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 选择卡全文持久化对象的 owner 与权威身份的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 选择卡全文持久化对象的 owner 与权威身份的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 选择卡全文持久化对象的 owner 与权威身份的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N05-S01-01` — 未冻结 owner 时创建正式选择卡，或只保留标签却声称全文已入账
- 当前代码说明：局部 target 有原型，正式 card owner/consumer 仍阻断。
- 暂不可执行 blocker：
  - 稳定选择卡 owner
  - 正式 card identity/schema
  - stop point 来源
- 版本对比字段：`card_id`、`card_version`、`owner`、`option_body_hashes`、`source_plan_version`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`

#### AT5-M8-N05-S02｜隔天选择旧卡 B 仍按当时全文解析

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：延迟选择的卡版本、选项全文与目标绑定
- 输入合同 / 必需输入：
  - card-v1
  - card-v2
  - selection target(card-v1,B)
- 输入合同 / 前置条件：
  - 两张卡均可读
  - B 在两版内容不同
- 输入合同 / 禁止假设：
  - 按当前最新卡解释旧选择
  - 只根据 option_label=B
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成周一 card-v1 的 A/B/C 全文，周三生成 card-v2；周四提交明确引用 card-v1/B 的 selection target。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - target 精确指向 card-v1/B
  - 返回 v1 B 的完整 body/hash
  - v2 不参与
- 预期禁止：
  - 不得把旧卡选择按新卡兑现
  - 不得丢理由/代价/影响字段
- 失败/恢复：card-v1 缺失或 SHA 不符时失败关闭，不退回 v2 猜测。
- 机械断言：
  - card_id/version exact
  - option_key exact
  - option_body_sha exact
  - source_plan_version exact
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 延迟选择的卡版本、选项全文与目标绑定的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；延迟选择的卡版本、选项全文与目标绑定所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 延迟选择的卡版本、选项全文与目标绑定的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 延迟选择的卡版本、选项全文与目标绑定的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 延迟选择的卡版本、选项全文与目标绑定的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N05-S02-01` — 作者引用旧卡 B，却返回新卡 B 或仅短标签
- 当前代码说明：局部 target 可绑定完整 option record；持久化 owner 仍缺。
- 版本对比字段：`card_id`、`card_version`、`option_key`、`option_body_sha256`、`source_plan_version`、`selection_time`
- 证据路径：`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`

#### AT5-M8-N05-S03｜多张卡复用 option_key 不串卡

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：复用短选项键下的复合身份解析
- 输入合同 / 必需输入：
  - 20 card snapshots
  - selection references
  - option hashes
- 输入合同 / 前置条件：
  - card_id+version+option_key 构成复合定位
- 输入合同 / 禁止假设：
  - 全局用 option_key 唯一定位
  - 按生成时间最近匹配
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 20 张选择卡，每张均有 A/B/C，但 B 的正文、版本和来源计划各不相同；随机引用 10 张旧卡。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 10 次都解析到指定卡的 B
  - 无跨卡正文串用
  - 每次返回完整 option record
- 预期禁止：
  - 不得只验证 option_key 存在
  - 不得用显示顺序代替身份
- 失败/恢复：任一引用不唯一时稳定报 AMBIGUOUS/NOT_FOUND，不猜。
- 机械断言：
  - composite key resolution
  - returned body hashes
  - ambiguity count
  - wrong-card count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 复用短选项键下的复合身份解析的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；复用短选项键下的复合身份解析所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 复用短选项键下的复合身份解析的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 复用短选项键下的复合身份解析的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 复用短选项键下的复合身份解析的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N05-S03-01` — 任一选择解析到另一张卡同名选项，或歧义时自动选一张
- 当前代码说明：原型支持局部身份绑定；需要扩大并持久化验证。
- 版本对比字段：`card_id`、`card_version`、`option_key`、`resolved_option_id`、`body_sha256`、`result_code`
- 证据路径：`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`

#### AT5-M8-N05-S04｜选项正文缺失、SHA 不符或来源计划过期时拒绝

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：选择卡完整性与来源计划新鲜度门
- 输入合同 / 必需输入：
  - bad card variants
  - plan history
  - valid control
- 输入合同 / 前置条件：
  - 旧卡可被选择不等于损坏卡可被选择
- 输入合同 / 禁止假设：
  - 缺正文时从日志/新卡补
  - SHA 错只警告
  - 过期计划照常兑现
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造三组坏卡：只剩标签、body SHA 被改、source plan version 已被明确废弃；附合法控制组。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 三组坏卡精确拒绝
  - 合法控制组可解析
  - 不写 plan
- 预期禁止：
  - 不得自动拼出缺失正文
  - 不得把损坏卡降级为短标签选择
- 失败/恢复：修复原卡或恢复历史后可重试；拒绝不改 current plan。
- 机械断言：
  - validation errors exact
  - plan write count=0
  - card digest unchanged
  - control passes
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 选择卡完整性与来源计划新鲜度门的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；选择卡完整性与来源计划新鲜度门所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 选择卡完整性与来源计划新鲜度门的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 选择卡完整性与来源计划新鲜度门的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 选择卡完整性与来源计划新鲜度门的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N05-S04-01` — 缺正文/SHA 冲突/来源计划不可用时仍产生可兑现 selection
- 当前代码说明：当前 validator/target 可覆盖部分完整性；正式新鲜度 owner 未闭合。
- 版本对比字段：`card_id`、`body_present`、`body_sha256`、`source_plan_status`、`result_code`、`plan_write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`

#### AT5-M8-N05-S05｜旧卡引用已废弃项目或跨作者时拒绝

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：选择卡的作者域、项目域与生命周期
- 输入合同 / 必需输入：
  - two author workspaces
  - archived/deleted project refs
  - historical card control
- 输入合同 / 前置条件：
  - 卡身份包含 author/project
  - 读取不创建缺失项目
- 输入合同 / 禁止假设：
  - 只要 card_id 存在即可跨项目用
  - 缺项目时自动重建
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造作者 A 的旧卡指向已删除/归档项目，并尝试在作者 B 项目提交；另造合法同作者历史卡控制组。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 跨作者/已删除拒绝
  - 归档策略明确
  - 合法历史卡按规则可读
- 预期禁止：
  - 不得泄露另一作者 option body
  - 不得读操作建目录
- 失败/恢复：拒绝后目录树和当前计划不变；错误只给安全序号/通用原因。
- 机械断言：
  - cross-author read=0
  - tree digest unchanged
  - plan digest unchanged
  - safe error
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 选择卡的作者域、项目域与生命周期的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；选择卡的作者域、项目域与生命周期所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 选择卡的作者域、项目域与生命周期的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 选择卡的作者域、项目域与生命周期的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 选择卡的作者域、项目域与生命周期的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N05-S05-01` — 跨作者读出卡全文、已删除项目被重建，或旧卡写入当前计划
- 当前代码说明：workspace 隔离已有；选择卡 owner 未完成。
- 版本对比字段：`author_id`、`project_id`、`card_id`、`lifecycle`、`result_code`、`tree_digest`
- 证据路径：`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`

#### AT5-M8-N05-S06｜选择卡持久化崩溃恢复不丢全文

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：选择卡全文的原子提交与恢复边界
- 输入合同 / 必需输入：
  - proposed card object
  - option body hashes
  - operation_id
  - failure points
- 输入合同 / 前置条件：
  - 正式 owner/storage 未决定
- 输入合同 / 禁止假设：
  - 用临时文件存在判成功
  - 把 planstore 写入当 card commit
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：在 card manifest 与 option bodies 之间设计崩溃点；因正式 owner/存储边界未冻结，只登记恢复测试合同，不实际执行。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 状态 BLOCKED_NOT_SCORED
  - 列明需要原子边界与 owner
  - 不制造测试专用正式格式
- 预期禁止：
  - 不得以私有 fixture 格式拍板
  - 不得声明恢复 PASS
- 失败/恢复：owner 冻结后必须验证 old-or-new 完整可见、重复 operation 幂等、冲突 payload 拒绝。
- 机械断言：
  - current formal write count=0
  - future recovery invariants registered
  - blocker visible
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 选择卡全文的原子提交与恢复边界的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；选择卡全文的原子提交与恢复边界所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 选择卡全文的原子提交与恢复边界的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 选择卡全文的原子提交与恢复边界的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 选择卡全文的原子提交与恢复边界的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N05-S06-01` — 未冻结存储 owner 时用测试格式写正式卡，或半份卡被读成可选
- 当前代码说明：恢复机制依赖正式 owner/对象边界，当前不可执行。
- 暂不可执行 blocker：
  - 选择卡正式 owner/storage
  - 跨文件原子提交边界
- 版本对比字段：`owner`、`storage_path`、`operation_id`、`manifest_state`、`body_count`、`commit_state`
- 证据路径：`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_plan_selection_target_tool.py`

---

### M8-N06｜作者点选后，选中方案正式写进规划账并成为当前版，旧候选标过期；下游只认写回后的规划

- 模块：M8
- R03 来源：CZ 2026-08-20 口述拍板（M8 缺口：选完没人写回）。
- 当前代码状态：**缺代码**
- 当前边界：planstore 有 current/history/versioning；正式 selection action builder、consumer、过期候选标记和跨存储恢复没有完成。
- 证据路径：`02_current_route/novel-mvp/mvp/planstore.py`、`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_planstore.py`

#### AT5-M8-N06-S01｜选中 B 写入规划账成为 current

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：selection action→planstore current 的正式写回
- 输入合同 / 必需输入：
  - current plan
  - selected full option B
  - selection action metadata
- 输入合同 / 前置条件：
  - B 与 plan-v3 版本匹配
  - author action 明确
- 输入合同 / 禁止假设：
  - 界面 selected 状态等于 plan write
  - 直接改 plan-v3 原文件
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 current plan-v3、card-v3 的 A/B/C 和明确 selection B；预期产生 plan-v4。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 生成新不可变 plan-v4
  - current 指向 v4
  - B 的完整变化被应用
- 预期禁止：
  - 不得把 A/C 写入 current
  - 不得删除 plan-v3
- 失败/恢复：写入失败时 plan-v3 仍 current；重试同 operation 幂等。
- 机械断言：
  - new version monotonic
  - current pointer exact
  - history preserved
  - payload hash matches B application
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | selection action→planstore current 的正式写回的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；selection action→planstore current 的正式写回所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | selection action→planstore current 的正式写回的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | selection action→planstore current 的正式写回的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | selection action→planstore current 的正式写回的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N06-S01-01` — 只更新 UI 不写 planstore，或原地覆盖 plan-v3
- 当前代码说明：planstore 有基础能力，selection consumer 未实现。
- 版本对比字段：`selection_action_id`、`source_plan_version`、`new_plan_version`、`current_version`、`history_versions`、`payload_sha256`
- 证据路径：`02_current_route/novel-mvp/mvp/planstore.py`、`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_planstore.py`

#### AT5-M8-N06-S02｜A/C 标过期留档且旧卡仍可审计

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：未选候选的过期标记、保留与审计
- 输入合同 / 必需输入：
  - card A/B/C
  - selection result
  - plan history
- 输入合同 / 前置条件：
  - 旧候选不是事实
  - 保留用于回看
- 输入合同 / 禁止假设：
  - 直接删除 A/C
  - 让 A/C 继续被下游当 current
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：选择 B 后读取 card、candidate history 和 planstore；检查 A/C 生命周期。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - A/C status=expired/superseded
  - 正文与版本留存
  - 下游 current query 只返回 B
- 预期禁止：
  - 不得抹掉未选方案
  - 不得把未选方案写成 rejected fact
- 失败/恢复：标记失败则整个 selection commit 不完成或进入明确恢复态。
- 机械断言：
  - candidate count preserved
  - lifecycle exact
  - downstream visible set=B only
  - history hashes stable
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 未选候选的过期标记、保留与审计的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；未选候选的过期标记、保留与审计所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 未选候选的过期标记、保留与审计的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 未选候选的过期标记、保留与审计的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 未选候选的过期标记、保留与审计的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N06-S02-01` — A/C 被删除、仍被下游当现行，或被误写成事实驳回
- 当前代码说明：候选过期 owner/consumer 未接。
- 版本对比字段：`option_id`、`lifecycle`、`selected_flag`、`downstream_visibility`、`body_sha256`
- 证据路径：`02_current_route/novel-mvp/mvp/planstore.py`、`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_planstore.py`

#### AT5-M8-N06-S03｜作者补充一句后重新判断是否仍选 B

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：选择动作与作者补充信息的语义冲突检测
- 输入合同 / 必需输入：
  - selected option B
  - new author note
  - current constraints
- 输入合同 / 前置条件：
  - 补充发生在正式 plan commit 前或明确修订入口
- 输入合同 / 禁止假设：
  - 所有补充都自动取消 B
  - 忽略补充按旧 B 写回
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 12 组：作者已点 B 后追加一个新限制/偏好；其中部分不影响 B，部分使 B 冲突。只预注册变量，不生成 Gold。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 判断补充是否改变 B 适用性
  - 冲突时停并说明
  - 不冲突时保留 B 且记录理由
- 预期禁止：
  - 不得悄悄改写 B
  - 不得把讨论当真改
- 失败/恢复：不确定时进入待决定，不写 plan current。
- 机械断言：
  - mechanical layer verifies no write before decision
  - note identity preserved
  - decision state explicit
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 区分补充是否改变方案可行性
  - 说明冲突来源
  - 不把讨论自动变更规划
  - 不确定时停而不猜
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 选择动作与作者补充信息的语义冲突检测未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：区分补充是否改变方案可行性；说明冲突来源；不把讨论自动变更规划；不确定时停而不猜。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：区分补充是否改变方案可行性；说明冲突来源；不把讨论自动变更规划；不确定时停而不猜；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-M8-N06-S03-01` — 补充与 B 明确冲突仍写回，或把仅讨论内容当正式修改
- 当前代码说明：需要意图/约束语义与 selection consumer 集成。
- 版本对比字段：`case_id`、`selection_id`、`note_id`、`conflict_state`、`decision_state`、`plan_write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/planstore.py`、`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_planstore.py`

#### AT5-M8-N06-S04｜规划版本冲突时拒绝旧选择

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：乐观并发控制与旧选择拒绝
- 输入合同 / 必需输入：
  - card source plan-v3
  - current plan-v4
  - selection B
- 输入合同 / 前置条件：
  - v4 与 v3 内容不同
  - 选择带 expected_version
- 输入合同 / 禁止假设：
  - 自动把 B 套到 v4
  - last write wins
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：card 来自 plan-v3，但作者在另一窗口把 current 更新到 plan-v4；再提交基于 v3 的 B。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 返回 VERSION_CONFLICT
  - plan-v4 保持 current
  - 旧卡/选择留审计
- 预期禁止：
  - 不得生成 plan-v5 猜测合并
  - 不得覆盖 v4
- 失败/恢复：作者显式刷新/重选后可新提交；旧 operation 不自动重放。
- 机械断言：
  - expected vs actual version
  - write count=0
  - current digest unchanged
  - conflict receipt
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 乐观并发控制与旧选择拒绝的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；乐观并发控制与旧选择拒绝所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 乐观并发控制与旧选择拒绝的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 乐观并发控制与旧选择拒绝的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 乐观并发控制与旧选择拒绝的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N06-S04-01` — 旧卡选择覆盖新规划，或系统无提示自动合并
- 当前代码说明：planstore 版本冲突基础可测；selection consumer 尚缺。
- 版本对比字段：`expected_plan_version`、`actual_plan_version`、`selection_id`、`result_code`、`current_sha256`
- 证据路径：`02_current_route/novel-mvp/mvp/planstore.py`、`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_planstore.py`

#### AT5-M8-N06-S05｜重复操作与 payload 篡改攻击

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：selection write 幂等与 operation conflict
- 输入合同 / 必需输入：
  - operation_id
  - B payload
  - tampered C payload
  - planstore
- 输入合同 / 前置条件：
  - 第一次提交成功的未来实现假设
  - payload hash 受控
- 输入合同 / 禁止假设：
  - 每次重放都增版本
  - operation_id 相同就无条件成功
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：同一 operation_id 重放相同 B 两次；第三次保持 ID 但把选项改成 C。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 相同 B 返回 replay/同一 plan version
  - 篡改 C 返回冲突
  - current 不变
- 预期禁止：
  - 不得生成重复 plan history
  - 不得让篡改 payload 生效
- 失败/恢复：冲突可审计且不暴露内部路径；后续新 operation 可正常使用。
- 机械断言：
  - history increment once
  - replay version same
  - tampered write count=0
  - current SHA stable
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | selection write 幂等与 operation conflict的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；selection write 幂等与 operation conflict所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | selection write 幂等与 operation conflict的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | selection write 幂等与 operation conflict的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | selection write 幂等与 operation conflict的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N06-S05-01` — 相同操作重复增版本，或同 operation_id 不同 payload 被接受
- 当前代码说明：需要未来 selection consumer 与 operation ledger。
- 版本对比字段：`operation_id`、`payload_sha256`、`result_code`、`plan_version`、`history_count`
- 证据路径：`02_current_route/novel-mvp/mvp/planstore.py`、`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_planstore.py`

#### AT5-M8-N06-S06｜selection commit 与 planstore commit 之间崩溃恢复

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：跨对象两步恢复而非伪装原子
- 输入合同 / 必需输入：
  - selection action receipt
  - plan commit intent
  - operation_id
  - failure point
- 输入合同 / 前置条件：
  - 承认跨存储可能两步
  - 恢复状态可枚举
- 输入合同 / 禁止假设：
  - 没有 plan current 仍标 HANDOVER_COMPLETE
  - 恢复时重写/丢失 selection
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：设计两步状态：selection action 已持久化、plan-v4 未 current；在中间注入崩溃并重启。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 返回 PLANSTORE_PENDING/可恢复等明确状态
  - 重启完成或回滚
  - 最终仅一个 current
- 预期禁止：
  - 不得把中间态冒充完成
  - 不得重复选择或丢历史
- 失败/恢复：恢复扫描依据 operation manifest，不按文件 mtime 猜。
- 机械断言：
  - state transition valid
  - selection receipt preserved
  - plan current exactly once
  - replay idempotent
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 跨对象两步恢复而非伪装原子的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；跨对象两步恢复而非伪装原子所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 跨对象两步恢复而非伪装原子的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 跨对象两步恢复而非伪装原子的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 跨对象两步恢复而非伪装原子的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M8-N06-S06-01` — 崩溃中间态被当完整、恢复后双写，或 selection receipt 丢失
- 当前代码说明：需实现明确两步恢复，不要求伪跨存储原子。
- 版本对比字段：`operation_id`、`selection_state`、`planstore_state`、`current_version`、`history_count`、`recovery_action`
- 证据路径：`02_current_route/novel-mvp/mvp/planstore.py`、`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`、`02_current_route/tests/test_novel_mvp_planstore.py`

---

### AE-M10-N01｜人物账能按故事时间回答「第 N 章时这个人受没受伤、穿什么、和谁什么关系」，答案全部来自已确认事实，没有记录就明说

- 模块：M10
- R03 来源：CZ 2026-08-20 口述拍板（M10 缺口：没人生产）。
- 当前代码状态：**部分覆盖**
- 当前边界：interval resolver 能按显式故事区间唯一命中并拒绝重叠/缺口；人物账 owner、章号→故事时间绑定和已确认事实来源仍缺。
- 证据路径：`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`、`02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`

#### AT5-AE-M10-N01-S01｜受伤与痊愈按故事时间回答历史状态

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：人物状态区间唯一命中与历史时点回答
- 输入合同 / 必需输入：
  - character_id
  - confirmed state intervals
  - story-time queries
- 输入合同 / 前置条件：
  - 区间有明确闭开边界
  - 来源 fact IDs 已确认
- 输入合同 / 禁止假设：
  - 拿最新状态回答所有历史时点
  - 按系统登记时间排序
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成同一人物两个不重叠状态区间：受伤、痊愈；查询三个故事时点。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 每个时点命中唯一正确区间
  - 返回来源 fact IDs
  - 边界点规则一致
- 预期禁止：
  - 不得使用 planned/rejected 状态
  - 不得无记录时猜
- 失败/恢复：区间无命中返回 NO_RECORD；不自动延长前一状态。
- 机械断言：
  - unique interval resolution
  - source IDs confirmed
  - boundary semantics exact
  - no fallback
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 人物状态区间唯一命中与历史时点回答的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；人物状态区间唯一命中与历史时点回答所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 人物状态区间唯一命中与历史时点回答的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 人物状态区间唯一命中与历史时点回答的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 人物状态区间唯一命中与历史时点回答的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N01-S01-01` — 历史时点被最新状态覆盖，或无记录时继承/编造状态
- 当前代码说明：显式 interval resolver 已有；人物账与章号映射未接。
- 版本对比字段：`character_id`、`query_story_time`、`state_key`、`resolved_value`、`source_fact_ids`、`resolution_status`
- 证据路径：`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`、`02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`

#### AT5-AE-M10-N01-S02｜衣着多次变化与同日边界

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：离散事件到衣着状态区间的稳定解析
- 输入合同 / 必需输入：
  - confirmed clothing events
  - story event order
  - queries
- 输入合同 / 前置条件：
  - 事件有故事序 tie-breaker
  - 不同状态键独立
- 输入合同 / 禁止假设：
  - 按章号/系统时间猜同日先后
  - 衣着缺失时继承未来值
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 4 次换装事实，含同一故事日内先后事件；查询事件前后和区间边界。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 事件前后值正确
  - 同日 tie-breaker 明确
  - 来源可回溯
- 预期禁止：
  - 不得把写法批注中的外观当状态
  - 不得使用未确认事件
- 失败/恢复：同日顺序不唯一时返回 AMBIGUOUS，不自动选一条。
- 机械断言：
  - event ordering exact
  - interval derivation deterministic
  - ambiguity surfaced
  - source closure
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 离散事件到衣着状态区间的稳定解析的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；离散事件到衣着状态区间的稳定解析所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 离散事件到衣着状态区间的稳定解析的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 离散事件到衣着状态区间的稳定解析的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 离散事件到衣着状态区间的稳定解析的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N01-S02-01` — 同日冲突被静默消解，或未来衣着泄露到更早时点
- 当前代码说明：resolver 支持显式整数区间；事件→区间 owner 仍缺。
- 版本对比字段：`event_id`、`story_time`、`story_order`、`state_value`、`resolution_status`、`source_fact_id`
- 证据路径：`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`、`02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`

#### AT5-AE-M10-N01-S03｜伤势、衣着、关系三个状态键互不污染

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：多状态键独立解析与部分答案
- 输入合同 / 必需输入：
  - character_id
  - three state-key interval sets
  - multi-key query
- 输入合同 / 前置条件：
  - 每键有独立 owner/来源
  - 允许部分 NO_RECORD
- 输入合同 / 禁止假设：
  - 一个键的 current 覆盖另一个键
  - 任一缺口使全部失败
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：同一人物并行构造 injury、clothing、relationship 三组区间，各自有不同覆盖范围和缺口。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 每键独立给值或 NO_RECORD
  - 来源按键列出
  - 无交叉串值
- 预期禁止：
  - 不得把关系标签当行为硬约束
  - 不得补默认衣着
- 失败/恢复：单键冲突只标该键 ambiguous，其余键照常返回。
- 机械断言：
  - per-key result statuses
  - no cross-key source IDs
  - partial response shape stable
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 多状态键独立解析与部分答案的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；多状态键独立解析与部分答案所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 多状态键独立解析与部分答案的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 多状态键独立解析与部分答案的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 多状态键独立解析与部分答案的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N01-S03-01` — 任一状态键读取到另一键的数据，或缺一键时编默认值
- 当前代码说明：interval resolver 可独立命中；人物账多键 owner 未完成。
- 版本对比字段：`state_key`、`value`、`status`、`source_fact_ids`、`query_story_time`
- 证据路径：`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`、`02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`

#### AT5-AE-M10-N01-S04｜倒叙场景的章号不能直接等于故事时间

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：章节/叙述位置到故事时间区间的绑定 owner
- 输入合同 / 必需输入：
  - chapter_id
  - scene_id
  - narrative position
  - story-time candidate
- 输入合同 / 前置条件：
  - R14 要区分故事序、叙述序
  - 当前绑定 owner 未冻结
- 输入合同 / 禁止假设：
  - chapter_number 直接作为 story time
  - 调用方任意提供一个整数即可信
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造叙述第 12 章实际回忆故事第 3 日的场景元数据；不提供正文。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 列明缺 scene/event binding owner
  - 不返回人物状态
- 预期禁止：
  - 不得拿最新或第 12 章状态冒充回忆时点
  - 不得用测试私有字段拍板
- 失败/恢复：正式绑定缺失时稳定停；不创建人物状态或场景卡。
- 机械断言：
  - resolution not attempted
  - state read count=0
  - blocker exact
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 章节/叙述位置到故事时间区间的绑定 owner的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；章节/叙述位置到故事时间区间的绑定 owner所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 章节/叙述位置到故事时间区间的绑定 owner的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 章节/叙述位置到故事时间区间的绑定 owner的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 章节/叙述位置到故事时间区间的绑定 owner的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N01-S04-01` — 未有权威 story-time binding 仍给出确定人物状态
- 当前代码说明：章号→故事时间和 scene/event binding owner 尚未冻结。
- 暂不可执行 blocker：
  - scene/event binding owner
  - 故事时间字段与章节/叙述位置映射合同
- 版本对比字段：`chapter_id`、`scene_id`、`story_time_owner`、`binding_version`、`result_code`
- 证据路径：`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`、`02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`

#### AT5-AE-M10-N01-S05｜没有状态记录时明确 NO_RECORD

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：状态缺失的 unknown/NO_RECORD 表达
- 输入合同 / 必需输入：
  - character_id
  - query time
  - confirmed non-clothing facts
- 输入合同 / 前置条件：
  - 未检索与覆盖内未找到可区分
- 输入合同 / 禁止假设：
  - 根据题材/常识编外观
  - 复用最近另一个人物衣着
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：查询人物在指定时点的衣着，输入只有伤势和关系事实，明确没有衣着记录。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 返回 NO_RECORD/覆盖状态
  - 列出已查范围
  - 衣着值为空
- 预期禁止：
  - 不得生成合理默认
  - 不得把空字符串当已知
- 失败/恢复：读取失败与覆盖内未找到必须用不同 code；都不写账。
- 机械断言：
  - value absent
  - status exact
  - searched sources listed
  - write count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 状态缺失的 unknown/NO_RECORD 表达的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；状态缺失的 unknown/NO_RECORD 表达所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 状态缺失的 unknown/NO_RECORD 表达的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 状态缺失的 unknown/NO_RECORD 表达的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 状态缺失的 unknown/NO_RECORD 表达的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N01-S05-01` — 无记录时给出具体衣着/状态，或把未检索说成覆盖内未找到
- 当前代码说明：resolver 对 gap 可拒绝；完整 unknown 六分和人物账读取未接。
- 版本对比字段：`query_id`、`state_key`、`value`、`unknown_kind`、`coverage`、`source_fact_ids`
- 证据路径：`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`、`02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`

#### AT5-AE-M10-N01-S06｜重叠区间与修订后恢复

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：状态区间冲突、版本修订和重启读回
- 输入合同 / 必需输入：
  - overlapping intervals v1
  - corrected intervals v2
  - version history
- 输入合同 / 前置条件：
  - v1/v2 都可审计
  - current 指针明确
- 输入合同 / 禁止假设：
  - 冲突时任选最新/最长区间
  - 修订原地覆盖
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造两个重叠伤势区间和一个合法修订版本；先读冲突，再提交修复并重启读取。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - v1 返回 AMBIGUOUS
  - v2 唯一命中
  - 重启仍读 v2 且 v1 历史保留
- 预期禁止：
  - 不得静默选一条
  - 不得丢冲突证据
- 失败/恢复：v2 写失败则 v1 仍 current conflict；重试幂等。
- 机械断言：
  - overlap rejected
  - version chain preserved
  - restart digest stable
  - single current
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 状态区间冲突、版本修订和重启读回的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；状态区间冲突、版本修订和重启读回所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 状态区间冲突、版本修订和重启读回的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 状态区间冲突、版本修订和重启读回的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 状态区间冲突、版本修订和重启读回的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N01-S06-01` — 重叠区间被静默解析为一个值，或修订后历史被删除/重启回旧版
- 当前代码说明：resolver 拒绝 overlap；持久人物账/version owner 未完成。
- 版本对比字段：`interval_set_version`、`current_version`、`overlap_count`、`resolution_status`、`history_versions`
- 证据路径：`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`、`02_current_route/tests/test_novel_mvp_scene_state_interval_resolver.py`

---

### AE-M10-N02｜场景卡只从人物账取人物状态，取不到就把缺口摆给作者，不自己编外观

- 模块：M10
- R03 来源：CZ 2026-08-20 口述拍板（M10 唯一可信来源）。
- 当前代码状态：**缺代码**
- 当前边界：M10 adapter 接受调用方 supplied bindings；没有只从人物账读取、缺口显式化和拒绝调用方伪造状态的正式接线。
- 证据路径：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`、`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`

#### AT5-AE-M10-N02-S01｜单人物场景卡只从人物账取状态

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：M10 人物状态唯一来源与 provenance
- 输入合同 / 必需输入：
  - scene story-time binding
  - character ledger snapshot
  - scene card request
- 输入合同 / 前置条件：
  - 人物账条目均来自已确认事实
  - 调用方不附状态值
- 输入合同 / 禁止假设：
  - M10 自己从旧章/默认模板补状态
  - caller supplied state 优先
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成人物账 current snapshot，含指定故事时点的伤势/衣着；调用 M10 场景卡构建。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 场景卡状态与人物账一致
  - 每字段带 ledger/source fact ref
  - 无额外外观
- 预期禁止：
  - 不得从书稿文本临时抓状态
  - 不得写回人物账
- 失败/恢复：人物账读取失败时卡进入缺料状态，不生成猜测版。
- 机械断言：
  - read source=character ledger only
  - field equality
  - provenance complete
  - ledger write=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | M10 人物状态唯一来源与 provenance的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；M10 人物状态唯一来源与 provenance所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | M10 人物状态唯一来源与 provenance的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | M10 人物状态唯一来源与 provenance的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | M10 人物状态唯一来源与 provenance的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N02-S01-01` — 场景卡出现人物账中没有的具体状态，或来源不是人物账
- 当前代码说明：当前 adapter 接受 caller binding，没有 ledger-only connector。
- 版本对比字段：`scene_id`、`character_id`、`story_time`、`state_fields`、`ledger_version`、`source_fact_ids`
- 证据路径：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`、`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`

#### AT5-AE-M10-N02-S02｜多人物场景不串人物或串时点

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：批量人物账读取的身份隔离
- 输入合同 / 必需输入：
  - five character ledger records
  - one scene time
  - scene participants
- 输入合同 / 前置条件：
  - character IDs 唯一
  - 同名显示名至少一组
- 输入合同 / 禁止假设：
  - 按名字关联
  - 缓存上一人物状态
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造 5 个人物、各自不同状态与有效区间；同一场景卡同时请求。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 每个人只拿自己的该时点状态
  - 同名不串
  - 来源 refs 对应本人
- 预期禁止：
  - 不得把缺项人物继承他人状态
  - 不得按数组位置错配
- 失败/恢复：单人物读取失败只标该人物缺口，其他人物保持可用。
- 机械断言：
  - character ID joins exact
  - no cross-character refs
  - partial error isolated
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 批量人物账读取的身份隔离的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；批量人物账读取的身份隔离所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 批量人物账读取的身份隔离的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 批量人物账读取的身份隔离的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 批量人物账读取的身份隔离的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N02-S02-01` — 任一人物读取到他人状态/来源，或一人失败导致系统编造全组默认值
- 当前代码说明：需正式 ledger connector 与批量 join。
- 版本对比字段：`scene_id`、`character_id`、`state_digest`、`ledger_ref`、`result_status`
- 证据路径：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`、`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`

#### AT5-AE-M10-N02-S03｜人物账部分缺项时卡上逐字段摆缺口

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：缺项字段的显式 author gap 与已知字段保留
- 输入合同 / 必需输入：
  - partial character state
  - requested field list
  - scene time
- 输入合同 / 前置条件：
  - 缺项不是空字符串已知值
- 输入合同 / 禁止假设：
  - 一项缺失时整卡失败
  - 用默认模板填缺项
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：人物账有伤势无衣着、有关系无携带物；场景卡请求四类字段。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 已知字段正常显示并带来源
  - 未知字段逐项标缺口
  - 缺口可定位回 owner
- 预期禁止：
  - 不得编造外观/物品
  - 不得隐藏缺口
- 失败/恢复：重试在账补齐后只刷新缺项，不改变既有来源字段。
- 机械断言：
  - per-field status exact
  - known refs stable
  - unknown fields have owner/request
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 缺项字段的显式 author gap 与已知字段保留的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；缺项字段的显式 author gap 与已知字段保留所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 缺项字段的显式 author gap 与已知字段保留的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 缺项字段的显式 author gap 与已知字段保留的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 缺项字段的显式 author gap 与已知字段保留的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N02-S03-01` — 缺项被静默填值、已知字段被丢弃，或缺口没有字段级定位
- 当前代码说明：当前 M10 没有人物账字段级缺口协议。
- 版本对比字段：`field_name`、`value`、`status`、`source_ref`、`gap_owner`、`ledger_version`
- 证据路径：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`、`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`

#### AT5-AE-M10-N02-S04｜人物账 stale 或场景故事时间缺失时停

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：新鲜度和故事时间前置门
- 输入合同 / 必需输入：
  - stale ledger snapshot
  - current fact version
  - scene request without story time
- 输入合同 / 前置条件：
  - current/version 可比对
- 输入合同 / 禁止假设：
  - 用 latest system time 代替 story time
  - stale 只做提示仍生成卡
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：两组输入：人物账 snapshot 基于旧事实版本；场景请求没有权威 story time。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 两组均停止人物状态装载
  - 返回 stale/missing-time 原因
  - 不生成具体状态
- 预期禁止：
  - 不得拿 current 最新状态冒充目标时点
  - 不得忽略 stale
- 失败/恢复：更新 snapshot 或补 binding 后可重试；失败前后卡/账无写入。
- 机械断言：
  - preflight failure exact
  - state field count=0
  - write count=0
  - versions reported
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 新鲜度和故事时间前置门的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；新鲜度和故事时间前置门所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 新鲜度和故事时间前置门的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 新鲜度和故事时间前置门的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 新鲜度和故事时间前置门的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N02-S04-01` — stale 或无故事时间仍生成具体人物状态
- 当前代码说明：需 connector preflight；story-time owner另有产品边界。
- 版本对比字段：`ledger_version`、`current_fact_version`、`story_time`、`preflight_status`、`state_field_count`
- 证据路径：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`、`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`

#### AT5-AE-M10-N02-S05｜调用方伪造状态覆盖人物账必须拒绝

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：caller supplied binding 的权限防线
- 输入合同 / 必需输入：
  - character ledger state
  - malicious supplied bindings
  - scene request
- 输入合同 / 前置条件：
  - 人物账是唯一可信来源
  - 调用方只能声明所需字段
- 输入合同 / 禁止假设：
  - 方便起见接受 caller 值
  - 冲突时以 caller 最新为准
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：调用方在 request 中附与人物账冲突的 injury/clothing binding；附合法仅请求字段控制组。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 恶意 binding 被拒或忽略并审计
  - 场景卡仍只用 ledger 值
  - 控制组通过
- 预期禁止：
  - 不得把 supplied binding 写回账
  - 不得把冲突降为无来源状态
- 失败/恢复：拒绝不泄露其他人物/项目数据；同一攻击重放幂等。
- 机械断言：
  - ledger value wins/attack rejected
  - ledger write=0
  - audit event exists
  - control passes
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | caller supplied binding 的权限防线的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；caller supplied binding 的权限防线所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | caller supplied binding 的权限防线的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | caller supplied binding 的权限防线的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | caller supplied binding 的权限防线的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N02-S05-01` — 调用方提供的状态覆盖人物账或进入场景卡
- 当前代码说明：当前 adapter 正是 caller supplied bindings，需要收权。
- 版本对比字段：`request_id`、`supplied_binding`、`ledger_value`、`effective_value`、`result_code`、`audit_id`
- 证据路径：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`、`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`

#### AT5-AE-M10-N02-S06｜构建过程中人物账升级时重试同一快照

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：多人物读取的一致快照与并发恢复
- 输入合同 / 必需输入：
  - ledger v5/v6
  - multi-character request
  - failure/update hook
- 输入合同 / 前置条件：
  - 读取应绑定单一 story_commit_seq/ledger version
- 输入合同 / 禁止假设：
  - 前 3 人用 v5、后 2 人用 v6 混卡
  - 失败后补写剩余字段
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：场景卡读取 3 人后人物账 current 从 v5 升 v6；注入中断并重试。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 整卡全用 v5 或检测变化后全量重试 v6
  - 不出现混版本
  - operation 幂等
- 预期禁止：
  - 不得静默混用版本
  - 不得改账以适配卡
- 失败/恢复：检测版本变化时丢弃未提交卡草稿；重试只产生一个正式卡版本。
- 机械断言：
  - single ledger version across card
  - draft cleaned
  - one committed card
  - history stable
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 多人物读取的一致快照与并发恢复的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；多人物读取的一致快照与并发恢复所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 多人物读取的一致快照与并发恢复的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 多人物读取的一致快照与并发恢复的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 多人物读取的一致快照与并发恢复的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M10-N02-S06-01` — 同一卡人物状态来自不同账版本，或重试生成双卡
- 当前代码说明：需一致性快照与重试 owner。
- 版本对比字段：`scene_card_id`、`ledger_version_set`、`operation_id`、`commit_state`、`card_count`
- 证据路径：`02_current_route/novel-mvp/mvp/m10_scene_slice_adapter.py`、`02_current_route/tests/test_novel_mvp_m10_scene_slice_adapter.py`

---

### AE-M11-N01｜拿着有效取件码能从事实账、规划账、章节账取回那份内容的正确版本；过期或无权的码被拒并说明原因

- 模块：M11
- R03 来源：CZ 2026-08-20 口述拍板（M11 缺口：没接线）。
- 当前代码状态：**部分覆盖**
- 当前边界：opaque recall handle 可绑定 current source ref，并拒绝 stale/cross-workspace；尚无事实/规划/章节三账正式 owner、历史版本 pin 与到期合同。
- 证据路径：`02_current_route/novel-mvp/mvp/recall_handle_workspace.py`、`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`

#### AT5-AE-M11-N01-S01｜事实账有效取件码取回正确版本

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：事实账 handle 解析与发码版本精确性
- 输入合同 / 必需输入：
  - fact ledger v3/v4
  - opaque handle
  - workspace identity
- 输入合同 / 前置条件：
  - handle 绑定发码时版本或明确 current 语义
  - 无明文路径泄露
- 输入合同 / 禁止假设：
  - 解析时总取最新 v4
  - handle 只验存在不取件
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造事实账 current v3、handle 绑定其 source ref；随后保留 v3 并产生 v4。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 按合同取回 v3 或明确 current-only 拒 stale
  - payload/SHA 与绑定版本一致
  - 来源域正确
- 预期禁止：
  - 不得把 v4 冒充 v3
  - 不得返回底层路径
- 失败/恢复：handle 过时按稳定 code 拒绝，不自动重发码或升级版本。
- 机械断言：
  - resolved source ref exact
  - payload hash exact
  - stale behavior deterministic
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 事实账 handle 解析与发码版本精确性的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；事实账 handle 解析与发码版本精确性所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 事实账 handle 解析与发码版本精确性的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 事实账 handle 解析与发码版本精确性的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 事实账 handle 解析与发码版本精确性的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M11-N01-S01-01` — 取回版本与发码绑定不一致，或只验码成功却无法取件
- 当前代码说明：当前 handle 可绑定 current ref 并拒 stale；历史 pin/事实账 owner 未接。
- 版本对比字段：`handle_id`、`ledger_kind`、`bound_version`、`resolved_version`、`payload_sha256`、`result_code`
- 证据路径：`02_current_route/novel-mvp/mvp/recall_handle_workspace.py`、`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`

#### AT5-AE-M11-N01-S02｜规划账取件码只回取指定 current/版本

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：规划账 handle 的版本与 current 身份
- 输入合同 / 必需输入：
  - planstore history
  - two handles
  - workspace
- 输入合同 / 前置条件：
  - 历史版本保留
  - handle 不暴露文件路径
- 输入合同 / 禁止假设：
  - 两个 handle 都取最新
  - 过期 candidate 当 current
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造 planstore v7/v8、两个 handle 分别绑定 v7 历史和 v8 current；测试取回。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 两个 handle 按各自语义取回
  - current/history 标签正确
  - 选项候选不混入
- 预期禁止：
  - 不得把过期候选当规划 current
  - 不得跨 project 解析
- 失败/恢复：历史版本不支持时必须明确拒绝 v7 handle，而不是返 v8。
- 机械断言：
  - handle-to-version mapping
  - plan identity exact
  - candidate exclusion
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 规划账 handle 的版本与 current 身份的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；规划账 handle 的版本与 current 身份所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 规划账 handle 的版本与 current 身份的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 规划账 handle 的版本与 current 身份的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 规划账 handle 的版本与 current 身份的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M11-N01-S02-01` — v7 handle 返回 v8，或 candidate/preview 被当正式规划取回
- 当前代码说明：opaque handle 通用原型与 planstore 存在，三账专用 owner未接。
- 版本对比字段：`handle_id`、`plan_version`、`plan_status`、`payload_sha256`、`result_code`
- 证据路径：`02_current_route/novel-mvp/mvp/recall_handle_workspace.py`、`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`

#### AT5-AE-M11-N01-S03｜章节账取件码取回章节正确版本和来源身份

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：章节账 handle 的准入与双车道来源身份
- 输入合同 / 必需输入：
  - external C11 current
  - product pending handover
  - chapter handles
- 输入合同 / 前置条件：
  - pending 不是正式 chapter ledger current
- 输入合同 / 禁止假设：
  - 给 pending 发正式章节码
  - 取件时丢 lane/source kind
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造外来章节 C11 current 与自产章事实稿 pending 两类对象；只对合法章节账 current 发码。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 只有正式 current 可发码/取回
  - 来源车道与版本可见
  - pending 被拒
- 预期禁止：
  - 不得把预演/pending 冒充正式交棒
  - 不得触发 M2/M3
- 失败/恢复：章节 current 变化后按新鲜度/历史规则处理，不能静默升级。
- 机械断言：
  - eligibility exact
  - lane label preserved
  - payload hash exact
  - pending rejected
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 章节账 handle 的准入与双车道来源身份的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；章节账 handle 的准入与双车道来源身份所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 章节账 handle 的准入与双车道来源身份的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 章节账 handle 的准入与双车道来源身份的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 章节账 handle 的准入与双车道来源身份的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M11-N01-S03-01` — pending/preflight 对象获得正式章节取件码，或取回后来源身份丢失
- 当前代码说明：外来 current eligibility 和 handle 原型存在；自产正式章节账未闭合。
- 版本对比字段：`handle_id`、`chapter_id`、`chapter_version`、`lane`、`eligibility`、`result_code`
- 证据路径：`02_current_route/novel-mvp/mvp/recall_handle_workspace.py`、`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`

#### AT5-AE-M11-N01-S04｜源版本升级后旧 current-only handle 变 stale

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：handle 新鲜度 owner 与统一 stale 行为
- 输入合同 / 必需输入：
  - fact/plan/chapter current refs
  - source upgrades
  - handles
- 输入合同 / 前置条件：
  - 每类账 current generation 可比对
- 输入合同 / 禁止假设：
  - 只看 handle 存在
  - 自动重定向最新版本
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：对三类账各发 current-only handle，随后升级 source generation；再逐一解析。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 三类旧 handle 均稳定 stale
  - 原因指出源版本变化
  - 新 handle 可用
- 预期禁止：
  - 不得取回新版本冒充旧码
  - 不得各账给不兼容错误形状
- 失败/恢复：stale 拒绝不删除 handle 审计；重发新码是独立动作。
- 机械断言：
  - stale codes consistent
  - old handles audit-preserved
  - new handles resolve
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | handle 新鲜度 owner 与统一 stale 行为的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；handle 新鲜度 owner 与统一 stale 行为所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | handle 新鲜度 owner 与统一 stale 行为的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | handle 新鲜度 owner 与统一 stale 行为的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | handle 新鲜度 owner 与统一 stale 行为的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M11-N01-S04-01` — 源升级后旧码仍取回新内容且不告知版本变化
- 当前代码说明：当前 workspace 已能拒 stale source ref；三账正式 adapter仍缺。
- 版本对比字段：`ledger_kind`、`handle_id`、`bound_generation`、`current_generation`、`result_code`
- 证据路径：`02_current_route/novel-mvp/mvp/recall_handle_workspace.py`、`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`

#### AT5-AE-M11-N01-S05｜过期、越权、跨项目和猜码攻击全部拒绝

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：handle 生命周期、权限和不可猜性
- 输入合同 / 必需输入：
  - valid handles
  - expiry metadata proposal
  - two authors/projects
  - attack values
- 输入合同 / 前置条件：
  - 授权按主体/项目/用途
  - 错误不泄露是否存在
- 输入合同 / 禁止假设：
  - 码可跨项目复用
  - 随机 handle 返回可区分存在性
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造显式过期码、作者 B 使用作者 A 码、项目跨用、随机猜码、篡改 handle 字节五组攻击。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 五组攻击拒绝
  - 合法控制组可取
  - 错误安全且可审计
- 预期禁止：
  - 不得返回任何 payload/路径
  - 不得读操作创建目录
- 失败/恢复：拒绝不消耗/改写合法 handle；连续攻击不影响控制组。
- 机械断言：
  - unauthorized payload bytes=0
  - tree digest unchanged
  - safe error uniformity
  - audit count exact
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | handle 生命周期、权限和不可猜性的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；handle 生命周期、权限和不可猜性所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | handle 生命周期、权限和不可猜性的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | handle 生命周期、权限和不可猜性的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | handle 生命周期、权限和不可猜性的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M11-N01-S05-01` — 任一无权/过期/猜测 handle 取到内容或泄露底层 source ref
- 当前代码说明：跨 workspace/stale 拒绝已有；显式 expiry/用途授权未冻结。
- 版本对比字段：`requester`、`project_id`、`handle_id`、`expiry`、`result_code`、`payload_length`、`tree_digest`
- 证据路径：`02_current_route/novel-mvp/mvp/recall_handle_workspace.py`、`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`

#### AT5-AE-M11-N01-S06｜批量发码与回取中断后恢复、operation 冲突

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：批量 handle 注册/取回的原子性、恢复和幂等
- 输入合同 / 必需输入：
  - nine source refs
  - operation_id
  - failure point
  - tampered retry
- 输入合同 / 前置条件：
  - source refs 均合法且版本固定
- 输入合同 / 禁止假设：
  - 崩溃后重复前 5 个
  - 同 operation 不校 payload
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：三账各 3 个 source ref 批量发码；第 5 个后崩溃。重启同 operation 重放，再用同 ID 篡改第 2 个 source。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 恢复后每 source 恰一 handle 或整批回滚
  - 相同重放幂等
  - 篡改重放冲突拒绝
- 预期禁止：
  - 不得留孤儿 handle
  - 不得把部分成功说成整批成功
- 失败/恢复：恢复回执列出 committed/pending/rolled_back；所有 handle 可审计。
- 机械断言：
  - unique handle per source
  - batch manifest closure
  - replay stable
  - conflict rejected
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 批量 handle 注册/取回的原子性、恢复和幂等的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；批量 handle 注册/取回的原子性、恢复和幂等所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 批量 handle 注册/取回的原子性、恢复和幂等的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 批量 handle 注册/取回的原子性、恢复和幂等的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 批量 handle 注册/取回的原子性、恢复和幂等的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-M11-N01-S06-01` — 崩溃留下不可取孤儿码、重复码，或同 operation 不同 source 集被接受
- 当前代码说明：单 handle workspace 有持久/冲突基础；三账批量 adapter 未接。
- 版本对比字段：`operation_id`、`source_set_sha256`、`handle_count`、`batch_state`、`replay_result`、`orphan_count`
- 证据路径：`02_current_route/novel-mvp/mvp/recall_handle_workspace.py`、`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`

---

### AE-AW-N01｜新项目一进来，10 本固定账自动建好（空着也建），每本在目录上登记：存什么、谁写、谁读

- 模块：作者工作区
- R03 来源：CZ 2026-08-20 口述拍板（账本目录／户籍处）。
- 当前代码状态：**部分覆盖**
- 当前边界：固定十账目录可登记、显式初始化和重启读回；当前模块明确不创建具体账本，也未冻结每账 producer/consumer。
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`、`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

#### AT5-AE-AW-N01-S01｜空项目初始化十本固定账目录

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：十本固定账的目录登记、唯一命名和空态可见
- 输入合同 / 必需输入：
  - author_id
  - project_id
  - empty workspace root
- 输入合同 / 前置条件：
  - 初始化是显式创建动作
  - 读操作不允许建目录
- 输入合同 / 禁止假设：
  - 内容来了再临时找家
  - 目录条目=具体账本已经创建
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：创建全新空作者项目，只传项目身份；不提供正文、设定或默认内容。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 章节、事实、人物、地点、物品、势力、体系、世界规则、长线、规划十本具体账均创建为空态 current
  - 目录恰有十个稳定 ledger kind，并逐项登记存什么、谁写、谁读的正式合同版本
  - 目录项与具体账本 generation/owner 可逐一对上
- 预期禁止：
  - 不得声称 10 个具体账本已创建，除非各 owner 实际落盘
  - 不得加入 M12
- 失败/恢复：初始化失败时旧空项目保持一致；可重试且不重复登记。
- 机械断言：
  - ledger_kind set exact and entry count=10
  - ten concrete stores exist with empty current receipts
  - directory-to-store owner/generation refs close
  - duplicate count=0
  - read-only verification creates no extra store
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 十本固定账的目录登记、唯一命名和空态可见的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；十本固定账的目录登记、唯一命名和空态可见所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 十本固定账的目录登记、唯一命名和空态可见的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 十本固定账的目录登记、唯一命名和空态可见的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 十本固定账的目录登记、唯一命名和空态可见的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N01-S01-01` — 目录少/多于十项、重复命名，或仅凭目录条目冒充具体账本已建
- 当前代码说明：当前只覆盖固定十账目录登记；模块明确不创建具体账本，producer/consumer 也未冻结。
- 版本对比字段：`project_id`、`ledger_kinds`、`entry_count`、`directory_version`、`concrete_store_state`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`、`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

#### AT5-AE-AW-N01-S02｜重启读回和重复初始化幂等

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：目录持久化、current 版本和幂等
- 输入合同 / 必需输入：
  - initialized directory
  - fresh process
  - same operation replay
- 输入合同 / 前置条件：
  - 目录 manifest 已提交
- 输入合同 / 禁止假设：
  - 每次启动追加十条
  - 按 mtime 选 current
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：初始化十账目录后销毁进程、重建 workspace；再执行相同初始化两次。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 重启后十本具体账与目录全部读回同一 generation/version/SHA
  - 重复初始化不产生第二套账、不重置已有空态/内容
  - 目录和具体账本 owner refs 仍一致
- 预期禁止：
  - 不得自动重写 owner 占位
  - 不得读回时创建具体账
- 失败/恢复：payload 相同幂等；同 operation_id 不同目录 schema 作为冲突拒绝。
- 机械断言：
  - directory and ten store identities stable after restart
  - same initialization is replay/idempotent
  - no duplicate directories/stores
  - payload/history digests unchanged
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 目录持久化、current 版本和幂等的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；目录持久化、current 版本和幂等所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 目录持久化、current 版本和幂等的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 目录持久化、current 版本和幂等的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 目录持久化、current 版本和幂等的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N01-S02-01` — 重启丢目录、重复初始化产生 20/30 条，或冲突 payload 被接受
- 当前代码说明：目录重启/幂等可测；十个具体账本的创建与联合读回未实现。
- 版本对比字段：`operation_id`、`directory_version`、`entry_count`、`payload_sha256`、`history_count`、`result_code`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`、`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

#### AT5-AE-AW-N01-S03｜每本账存什么、谁写、谁读的正式登记合同

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：十账 producer、consumer、内容边界与 owner
- 输入合同 / 必需输入：
  - ten ledger kinds
  - R14 semantic responsibilities
- 输入合同 / 前置条件：
  - 目录不夺每本账 owner
  - 当前代码只有目录
- 输入合同 / 禁止假设：
  - 由测试设计者补全所有 owner
  - 用当前模块名猜谁写谁读
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：只给十本账名称和 R14 产品职责；不自填 producer/consumer/action 权限矩阵。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 逐账列出缺失 owner/consumer/内容 schema
  - 不产正式目录权限
- 预期禁止：
  - 不得把建议当合同
  - 不得用空字段冒充 action
- 失败/恢复：决定冻结前重复执行不写正式权限；冻结后再启用机械校验。
- 机械断言：
  - formal owner matrix absent
  - blocker list covers 10 ledgers
  - write_count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 十账 producer、consumer、内容边界与 owner的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；十账 producer、consumer、内容边界与 owner所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 十账 producer、consumer、内容边界与 owner的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 十账 producer、consumer、内容边界与 owner的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 十账 producer、consumer、内容边界与 owner的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N01-S03-01` — 未经产品/合同决定就发布十账完整写读权限，或空字段被当已闭合
- 当前代码说明：十账户籍语义已拍，但每账 owner/consumer 仍需正式冻结。
- 暂不可执行 blocker：
  - 十账逐账 producer/consumer/owner 合同
  - 具体账本创建责任
- 版本对比字段：`ledger_kind`、`content_owner`、`writer_actions`、`reader_actions`、`contract_version`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`、`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

#### AT5-AE-AW-N01-S04｜某本账不可用时目录显示 UNKNOWN/UNAVAILABLE

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：目录与具体账本可用性不一致的诚实展示
- 输入合同 / 必需输入：
  - directory entries
  - per-ledger health receipts
- 输入合同 / 前置条件：
  - 目录身份与运行状态分开
- 输入合同 / 禁止假设：
  - 目录有条目就报 READY
  - 自动创建缺失人物账修复
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：目录有十项，其中人物账 owner 未安装/存储损坏，其他九项正常；只读目录和健康状态。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 人物账标 UNAVAILABLE/UNKNOWN 并说明 owner
  - 其余九项不受影响
  - 不创建目录/账
- 预期禁止：
  - 不得把目录登记冒充运行能力
  - 不得读操作修复或建账
- 失败/恢复：健康读取失败返回 UNKNOWN，不把 unknown 说成 empty。
- 机械断言：
  - 10 entries preserved
  - one health status unavailable
  - tree digest unchanged
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 目录与具体账本可用性不一致的诚实展示的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；目录与具体账本可用性不一致的诚实展示所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 目录与具体账本可用性不一致的诚实展示的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 目录与具体账本可用性不一致的诚实展示的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 目录与具体账本可用性不一致的诚实展示的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N01-S04-01` — 不可用账被报成 READY/EMPTY，或只读健康检查创建/修改任何账
- 当前代码说明：目录可读；具体账健康接线需要各 owner 提供 receipt。
- 版本对比字段：`ledger_kind`、`directory_registered`、`health_status`、`reason`、`tree_digest`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`、`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

#### AT5-AE-AW-N01-S05｜缺项、重名、改名和顺序攻击被 validator 拒绝

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：固定十账目录 schema 与显示顺序非身份
- 输入合同 / 必需输入：
  - invalid directory payloads
  - canonical kind registry
- 输入合同 / 前置条件：
  - 内部 ledger_kind 稳定
  - 显示名可本地化但不改身份
- 输入合同 / 禁止假设：
  - 数组顺序决定 kind
  - 改显示名等于新账
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造缺一账、加第十一账、重复人物账、把势力账改名、随机排序五种目录 payload。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 缺/多/重名/非法 kind 拒绝
  - 合法乱序可规范化但身份不变
- 预期禁止：
  - 不得静默丢未知项
  - 不得把建议新账混入固定十账
- 失败/恢复：验证失败不覆盖 current；错误列出精确差异。
- 机械断言：
  - canonical set comparison
  - duplicate detection
  - current digest unchanged
  - error details exact
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 固定十账目录 schema 与显示顺序非身份的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；固定十账目录 schema 与显示顺序非身份所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 固定十账目录 schema 与显示顺序非身份的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 固定十账目录 schema 与显示顺序非身份的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 固定十账目录 schema 与显示顺序非身份的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N01-S05-01` — 非法目录被接受为 current，或未知第十一账被静默吞掉
- 当前代码说明：固定十名可验证；扩展账提议另属产品决定。
- 版本对比字段：`input_kinds`、`canonical_kinds`、`result_code`、`difference_set`、`current_sha256`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`、`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

#### AT5-AE-AW-N01-S06｜初始化中断只见旧或新完整目录

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：目录初始化原子性、恢复和临时文件清理
- 输入合同 / 必需输入：
  - empty/old directory state
  - new directory payload
  - failure points
  - operation_id
- 输入合同 / 前置条件：
  - 提交应有 generation/manifest
- 输入合同 / 禁止假设：
  - 部分 3—7 项可作为 current
  - 按残留 temp 文件恢复
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：在目录 payload、manifest、current pointer 三个提交点注入崩溃并重启。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 初始化成功时目录与十个具体账本同时形成完整可读的一代
  - 任意崩溃点重启后只见旧完整状态或新完整状态，不能见半套
  - 同 operation 重试幂等，不同 payload 冲突
- 预期禁止：
  - 不得把半份目录说成已初始化
  - 不得丢旧 current
- 失败/恢复：恢复回执明确 COMMITTED/ROLLED_BACK/READY_TO_RETRY。
- 机械断言：
  - visible concrete store count only 0 or 10
  - directory and per-store commit manifests close to one generation
  - temp/partial objects isolated and cleaned
  - single current generation after recovery
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 目录初始化原子性、恢复和临时文件清理的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；目录初始化原子性、恢复和临时文件清理所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 目录初始化原子性、恢复和临时文件清理的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 目录初始化原子性、恢复和临时文件清理的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 目录初始化原子性、恢复和临时文件清理的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N01-S06-01` — 重启读到 1—9 项半目录、旧 current 丢失或重试生成重复版本
- 当前代码说明：目录自身恢复可测；跨十个具体账本的 bootstrap operation owner 未实现。
- 版本对比字段：`operation_id`、`generation_id`、`manifest_state`、`entry_count`、`current_version`、`temp_count`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`、`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

---

### AE-AW-N02｜作者随手加一个设定类新内容（新忍术、新国家），系统建议唯一去处并说明理由；没有合适账本就提议开新账，不丢在聊天里

- 模块：作者工作区
- R03 来源：CZ 2026-08-20 口述拍板（账本目录／进账路由）。
- 当前代码状态：**缺代码**
- 当前边界：现有 intent router 只做未来剧情放置建议，不负责设定类内容在十账中的唯一去处、理由、作者改判和提议新账。
- 证据路径：`02_current_route/novel-mvp/mvp/intent_router.py`、`02_current_route/tests/test_novel_mvp_intent_router.py`

#### AT5-AE-AW-N02-S01｜人物定义类新内容建议进人物账

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：设定类内容的唯一主去处、理由与可改判
- 输入合同 / 必需输入：
  - setting utterance
  - ten-ledger directory
  - current focus
- 输入合同 / 前置条件：
  - 本条只管设定，不管未来剧情安排
- 输入合同 / 禁止假设：
  - 关键词匹配到多个账就复制
  - 只留聊天气泡
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 20 条设定类输入：人物身份、别名、固有特征、长期背景；每条仅一个路由变量，不含正文。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 建议唯一 primary ledger
  - 给出一条可理解理由
  - 保留 author override 入口
- 预期禁止：
  - 不得自动入账
  - 不得复制进多账作为多真源
- 失败/恢复：不确定时给 primary candidate+冲突理由，等待作者决定。
- 机械断言：
  - mechanical result has one primary or explicit undecided
  - truth write=0
  - chat-only loss=0 after accepted action
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 识别这是人物定义而非未来事件
  - 给唯一主去处
  - 理由对应内容语义
  - 不确定时允许作者改判而不自动写入
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 设定类内容的唯一主去处、理由与可改判未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：识别这是人物定义而非未来事件；给唯一主去处；理由对应内容语义；不确定时允许作者改判而不自动写入。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：识别这是人物定义而非未来事件；给唯一主去处；理由对应内容语义；不确定时允许作者改判而不自动写入；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-AE-AW-N02-S01-01` — 同一设定被复制进两本账、无理由硬塞，或在作者未确认前直接写账
- 当前代码说明：现有 intent router 不管十账设定路由。
- 版本对比字段：`input_id`、`route_primary`、`route_references`、`reason`、`decision_state`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/intent_router.py`、`02_current_route/tests/test_novel_mvp_intent_router.py`

#### AT5-AE-AW-N02-S02｜体系、世界规则、势力/国家设定的边界区分

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：体系账、世界规则账、势力账的语义路由
- 输入合同 / 必需输入：
  - setting items
  - ledger definitions
  - minimal pairs
- 输入合同 / 前置条件：
  - 每条只考一个主归属
  - 允许稳定 ID 引用其他账
- 输入合同 / 禁止假设：
  - 国家一律地点账
  - 技能约束一律世界规则账
  - 多归属直接复制全文
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 30 条自创设定，覆盖技能/等级/克制、硬世界规则、国家/门派组织；加入 6 组最小对。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 主账分类正确
  - 必要关联只用引用
  - 理由说明安排/定义/变化边界
- 预期禁止：
  - 不得把未来使用某技能的安排当技能定义
  - 不得创建第二真源
- 失败/恢复：歧义项返回候选+提问点，不擅自拍板。
- 机械断言：
  - one primary route
  - reference IDs only for secondary links
  - write_count=0 before confirmation
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 区分体系定义、世界硬规则和势力实体
  - 区分定义与未来安排
  - 一条内容只有一个主家
  - 歧义时说明而非硬塞
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 体系账、世界规则账、势力账的语义路由未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：区分体系定义、世界硬规则和势力实体；区分定义与未来安排；一条内容只有一个主家；歧义时说明而非硬塞。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：区分体系定义、世界硬规则和势力实体；区分定义与未来安排；一条内容只有一个主家；歧义时说明而非硬塞；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-AE-AW-N02-S02-01` — 体系/规则/势力边界大面积混淆，或同一内容全文复制到多账
- 当前代码说明：需新语义路由器和目录 action builder。
- 版本对比字段：`item_id`、`primary_ledger`、`reference_ledgers`、`reason`、`ambiguity`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/intent_router.py`、`02_current_route/tests/test_novel_mvp_intent_router.py`

#### AT5-AE-AW-N02-S03｜未来相遇/剧情安排转交 M8 放置路由

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`部分覆盖`
- 主变量：设定路由与 M8 未来内容路由的职责分界
- 输入合同 / 必需输入：
  - ambiguous user inputs
  - ten-ledger directory
  - M8 placement categories
- 输入合同 / 前置条件：
  - AE-AW-N02 管设定类，M8-N01 管未来剧情类
- 输入合同 / 禁止假设：
  - 所有含人物名都进人物账
  - 所有含未来词都进规划账而不判断
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 18 条含未来动作、相遇、伏笔、人物走向的模糊输入；混入 6 条纯设定控制组。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 未来剧情移交 M8 placement
  - 纯设定留十账路由
  - 混合输入拆最小语义单元
- 预期禁止：
  - 不得把未来计划写进事实/人物定义
  - 不得把设定丢在聊天
- 失败/恢复：无法拆分时明确询问作者意图，不自动落账。
- 机械断言：
  - handoff target exact
  - semantic unit count
  - truth write=0
  - unresolved intent explicit
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 区分定义与未来安排
  - 混合内容按最小语义单元分流
  - M8 与目录 owner 边界清楚
  - 未确认不写真值
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 设定路由与 M8 未来内容路由的职责分界未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：区分定义与未来安排；混合内容按最小语义单元分流；M8 与目录 owner 边界清楚；未确认不写真值。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：区分定义与未来安排；混合内容按最小语义单元分流；M8 与目录 owner 边界清楚；未确认不写真值；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-AE-AW-N02-S03-01` — 未来剧情被当已发生/人物定义入账，或纯设定被无理由送去 M8
- 当前代码说明：现有 intent router 有未来放置建议；与十账设定路由的接缝缺代码。
- 版本对比字段：`input_id`、`unit_id`、`content_kind`、`route_owner`、`decision_state`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/intent_router.py`、`02_current_route/tests/test_novel_mvp_intent_router.py`

#### AT5-AE-AW-N02-S04｜一条内容看似可进两账时给唯一主家＋引用

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：多账候选下的唯一主存储与引用策略
- 输入合同 / 必需输入：
  - dual-fit setting items
  - ledger definitions
  - existing entity IDs
- 输入合同 / 前置条件：
  - 一条只存一处，别处稳定 ID 引用
- 输入合同 / 禁止假设：
  - 复制全文最保险
  - 任意选一个不解释
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 16 个双适用样本：国家地理与势力、物品与体系能力、人物与关系变化；不预填答案，只预注册判断维度。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 提出唯一主家
  - 说明为什么
  - 列出可选引用但不复制
- 预期禁止：
  - 不得产生双 current
  - 不得把变化塞进定义账
- 失败/恢复：置信不足时停在 proposed route，不创建多份草稿。
- 机械断言：
  - one primary route in output
  - reference count allowed
  - write count=0 pre-confirmation
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 唯一主存储合理
  - 引用而非复制
  - 理由对应内容职责
  - 安排/定义/变化不混
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 多账候选下的唯一主存储与引用策略未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：唯一主存储合理；引用而非复制；理由对应内容职责；安排/定义/变化不混。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：唯一主存储合理；引用而非复制；理由对应内容职责；安排/定义/变化不混；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-AE-AW-N02-S04-01` — 同一内容被建议全文写入两账，或变化/安排与定义混家
- 当前代码说明：需未来语义路由；不生成 Gold。
- 版本对比字段：`item_id`、`primary_ledger`、`reference_targets`、`reason`、`confidence_state`
- 证据路径：`02_current_route/novel-mvp/mvp/intent_router.py`、`02_current_route/tests/test_novel_mvp_intent_router.py`

#### AT5-AE-AW-N02-S05｜十本账都装不下时提议新账但不擅自创建

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：扩展账提议门、模板与批准权
- 输入合同 / 必需输入：
  - unroutable content metadata
  - fixed ten-ledger directory
  - extension proposal shell
- 输入合同 / 前置条件：
  - R03 允许提议开新账
  - 具体扩展字段合同仍需 owner/消费者
- 输入合同 / 禁止假设：
  - 自动创建第十一账
  - 硬塞进最相近固定账
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造一个超出十账职责的抽象扩展类型，只提供类型元数据；不指定应否开第十一账。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 列出扩展账需回答七问/字段合同
  - 不建账
- 预期禁止：
  - 不得让测试设计替产品决定扩展类型
  - 不得污染固定十账 registry
- 失败/恢复：决定前提案可保存为非真值草案；重放不产生目录变化。
- 机械断言：
  - fixed directory unchanged
  - proposal status only
  - write count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 扩展账提议门、模板与批准权的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；扩展账提议门、模板与批准权所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 扩展账提议门、模板与批准权的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 扩展账提议门、模板与批准权的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 扩展账提议门、模板与批准权的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N02-S05-01` — 未获确认自动创建新账，或硬塞导致固定账职责被改写
- 当前代码说明：新账模板、批准权和消费者未冻结。
- 暂不可执行 blocker：
  - 扩展账创建权限/模板
  - 扩展字段 owner/consumer/迁移合同
- 版本对比字段：`proposal_id`、`proposed_namespace`、`owner`、`consumer`、`approval_state`、`directory_entry_count`
- 证据路径：`02_current_route/novel-mvp/mvp/intent_router.py`、`02_current_route/tests/test_novel_mvp_intent_router.py`

#### AT5-AE-AW-N02-S06｜作者改判路由的保存、重启与幂等

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：作者 override action 的持久化与不重复落位
- 输入合同 / 必需输入：
  - route proposal
  - author override action
  - operation_id
  - failure point
- 输入合同 / 前置条件：
  - proposal 本身不写账
  - override 明确引用 item/proposal
- 输入合同 / 禁止假设：
  - 系统建议优先于作者改判
  - 崩溃后建议和改判各写一份
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：路由器建议体系账，作者明确改判世界规则账；在 override 提交中间崩溃，重启同 operation 重试。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 最终只有作者选定主家
  - 建议留审计但不生效
  - 重启幂等
- 预期禁止：
  - 不得同时写两账
  - 不得丢作者理由/动作身份
- 失败/恢复：相同 operation 同 payload replay；不同 payload conflict。
- 机械断言：
  - one effective route
  - proposal history preserved
  - replay stable
  - conflict rejected
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 作者 override action 的持久化与不重复落位的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；作者 override action 的持久化与不重复落位所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 作者 override action 的持久化与不重复落位的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 作者 override action 的持久化与不重复落位的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 作者 override action 的持久化与不重复落位的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N02-S06-01` — 作者改判后仍按系统建议落账，或崩溃导致双写
- 当前代码说明：可先设计 action/恢复机械合同；当前无十账路由写入 owner。
- 版本对比字段：`proposal_id`、`action_id`、`author_choice`、`effective_route`、`operation_id`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/intent_router.py`、`02_current_route/tests/test_novel_mvp_intent_router.py`

---

### AE-AW-N03｜一本账内容少时是轻文件，条数或引用过阈值自动升格成正式结构；升格前后模块和插件的取法完全不变

- 模块：作者工作区
- R03 来源：CZ 2026-08-20 口述拍板（简装／精装两档）。
- 当前代码状态：**缺产品决定**
- 当前边界：简装/精装阈值、引用计数口径、迁移 owner、稳定读取接口和降级政策均未冻结，当前代码无对应运行 owner。
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N03-S01｜少量条目保持简装的阈值决定

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：简装适用条件与形态定义
- 输入合同 / 必需输入：
  - small ledger metadata
  - consumer interface requirement
- 输入合同 / 前置条件：
  - R03 只拍简装/精装方向
  - 阈值未冻结
- 输入合同 / 禁止假设：
  - 随意用 10/50/60 条作为正式阈值
  - 简装等于无版本/无身份
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造 2 条物品登记和 1 个读取消费者；不预设条数阈值。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 列出待决定阈值与最低护栏
  - 不创建正式迁移规则
- 预期禁止：
  - 不得把示例 60 件当合同阈值
  - 不得牺牲版本/来源/隔离
- 失败/恢复：决定前保持现有存储不变；测试只登记未来验收。
- 机械断言：
  - threshold unset
  - migration write=0
  - minimum invariants listed
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 简装适用条件与形态定义的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；简装适用条件与形态定义所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 简装适用条件与形态定义的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 简装适用条件与形态定义的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 简装适用条件与形态定义的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N03-S01-01` — 测试设计自行拍定阈值或把简装定义成无护栏文件
- 当前代码说明：条数/引用阈值和简装最低合同未冻结。
- 暂不可执行 blocker：
  - 简装/精装阈值
  - 简装最低 schema/version/原子性合同
- 版本对比字段：`entry_count`、`reference_count`、`threshold_version`、`storage_mode`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N03-S02｜条数达到阈值触发升格的决定

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：条数触发器、计数口径和边界包含性
- 输入合同 / 必需输入：
  - symbolic threshold N
  - entry mutations
  - deleted/archived entries
- 输入合同 / 前置条件：
  - 计数是否含历史/删除项未冻结
- 输入合同 / 禁止假设：
  - 把示例值写死
  - 达到 N 自动迁移且无预演
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造条数从 N-1 到 N 的增长脚本，但 N 只作符号变量。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 列明 active/history/reference 的计数口径决定
  - 不执行迁移
- 预期禁止：
  - 不得用 fixture N 替正式产品决定
  - 不得静默升格
- 失败/恢复：阈值冻结后需测 N-1/N/N+1 与回滚；当前零写。
- 机械断言：
  - threshold symbolic
  - counter policy unresolved
  - migration_count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 条数触发器、计数口径和边界包含性的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；条数触发器、计数口径和边界包含性所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 条数触发器、计数口径和边界包含性的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 条数触发器、计数口径和边界包含性的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 条数触发器、计数口径和边界包含性的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N03-S02-01` — 未冻结计数口径就触发正式迁移或修改 current
- 当前代码说明：阈值与计数口径阻断。
- 暂不可执行 blocker：
  - 条数阈值
  - active/history/deleted 计数口径
- 版本对比字段：`active_count`、`history_count`、`reference_count`、`threshold`、`migration_state`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N03-S03｜引用次数达到阈值触发升格的决定

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：引用阈值、去重和消费者计数
- 输入合同 / 必需输入：
  - ledger entries
  - reference graph
  - consumer identities
- 输入合同 / 前置条件：
  - 条数少但引用多可升格
  - 何谓一次引用未冻结
- 输入合同 / 禁止假设：
  - 重复读取都算新引用
  - 插件缓存引用等于业务引用
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造 2 个条目被不同模块/插件引用多次的引用图，只存 ref IDs。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 列明 reference identity/dedup/window 决定
  - 不迁移
- 预期禁止：
  - 不得用请求次数冒充稳定引用
  - 不得泄露私有消费者
- 失败/恢复：合同冻结后需测重复 ref、撤销 ref、跨版本 ref；当前不执行。
- 机械断言：
  - reference threshold unset
  - unique ref policy unresolved
  - migration_count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 引用阈值、去重和消费者计数的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；引用阈值、去重和消费者计数所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 引用阈值、去重和消费者计数的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 引用阈值、去重和消费者计数的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 引用阈值、去重和消费者计数的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N03-S03-01` — 凭临时调用计数自动升格，或未定义消费者身份就累加阈值
- 当前代码说明：引用计数 owner/阈值未冻结。
- 暂不可执行 blocker：
  - 引用计数 owner/去重口径
  - 引用升格阈值
- 版本对比字段：`entry_id`、`reference_ids`、`consumer_ids`、`reference_count`、`threshold_version`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N03-S04｜升格期间并发写入如何处理

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：升格锁、双写/停写策略与一致性窗口
- 输入合同 / 必需输入：
  - migration intent
  - concurrent writes/reads
  - old/new storage proposals
- 输入合同 / 前置条件：
  - 不能假装跨存储天然原子
- 输入合同 / 禁止假设：
  - 无锁双写
  - 丢弃并发写
  - 读取随机选旧/新
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造迁移开始后作者新增条目、插件读取、另一个窗口更新旧条目三类并发动作。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 列明锁/队列/版本门需要决定
  - 不执行迁移
- 预期禁止：
  - 不得以测试实现拍板并发策略
  - 不得允许读到混合代际
- 失败/恢复：正式策略冻结后验收 old-or-new 一致快照和可恢复写队列。
- 机械断言：
  - no formal migration side effect
  - concurrency policy blocker exact
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 升格锁、双写/停写策略与一致性窗口的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；升格锁、双写/停写策略与一致性窗口所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 升格锁、双写/停写策略与一致性窗口的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 升格锁、双写/停写策略与一致性窗口的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 升格锁、双写/停写策略与一致性窗口的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N03-S04-01` — 未冻结并发策略仍启动迁移，导致丢写或混版本读取
- 当前代码说明：并发和迁移 owner 未冻结。
- 暂不可执行 blocker：
  - 迁移锁/队列/并发策略
  - 一致性读取版本
- 版本对比字段：`migration_id`、`old_version`、`new_version`、`concurrent_operation_ids`、`policy_version`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N03-S05｜升格中断的回滚与恢复边界

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：简装→精装迁移状态机、commit manifest 与恢复
- 输入合同 / 必需输入：
  - old store metadata
  - new store proposal
  - migration operation_id
  - failure points
- 输入合同 / 前置条件：
  - old store 必须可回读
  - 迁移 owner 未冻结
- 输入合同 / 禁止假设：
  - 新文件存在即成功
  - 失败后删除旧库
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：列出 copy、validate、switch current、cleanup 四个崩溃点，只用对象元数据。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 登记 future recovery invariants
  - 当前零迁移写
- 预期禁止：
  - 不得用临时迁移脚本冒充正式能力
  - 不得提前清理旧存储
- 失败/恢复：未来必须保证 old/new 一套完整 current、幂等重试和冲突拒绝。
- 机械断言：
  - migration_count=0
  - recovery invariants complete
  - owner blocker visible
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 简装→精装迁移状态机、commit manifest 与恢复的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；简装→精装迁移状态机、commit manifest 与恢复所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 简装→精装迁移状态机、commit manifest 与恢复的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 简装→精装迁移状态机、commit manifest 与恢复的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 简装→精装迁移状态机、commit manifest 与恢复的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N03-S05-01` — 未冻结 owner 时执行正式迁移，或允许半迁移被 current 读取
- 当前代码说明：恢复实现依赖正式迁移对象与 owner。
- 暂不可执行 blocker：
  - 迁移状态机/owner
  - 旧存储保留与清理政策
- 版本对比字段：`migration_state`、`old_store_sha`、`new_store_sha`、`current_pointer`、`operation_id`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N03-S06｜升格前后消费者接口完全一致与不自动降级

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`BLOCKED_CONTRACT_OR_PRODUCT_DECISION`；当前就绪度：`BLOCKED_NOT_SCORED`；代码状态：`缺产品决定`
- 主变量：稳定消费者接口、能力差异和降级政策
- 输入合同 / 必需输入：
  - consumer action inventory
  - light/formal storage capabilities
  - versioned contract shell
- 输入合同 / 前置条件：
  - R03 要求取法不变
  - 扩展字段/性能能力可能不同
- 输入合同 / 禁止假设：
  - 把两个实现的内部路径暴露给消费者
  - 条数下降就自动降回简装
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：构造模块和插件的抽象 read/list/query/write-proposal 调用清单，不指定具体 API 名称。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - BLOCKED_NOT_SCORED
  - 列明稳定接口与迁移兼容决定
  - 不发布 API
- 预期禁止：
  - 不得用本窗命名冻结正式接口
  - 不得自动降级导致引用失效
- 失败/恢复：接口冻结后需同一测试向量对两形态比对；当前只登记。
- 机械断言：
  - formal API version absent
  - consumer compatibility matrix pending
  - downgrade disabled pending decision
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 稳定消费者接口、能力差异和降级政策的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；稳定消费者接口、能力差异和降级政策所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 稳定消费者接口、能力差异和降级政策的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 稳定消费者接口、能力差异和降级政策的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 稳定消费者接口、能力差异和降级政策的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N03-S06-01` — 测试设计擅自发布接口或默认自动降级
- 当前代码说明：接口命名、能力范围和降级策略都未闭合。
- 暂不可执行 blocker：
  - 稳定账本读取/提案接口
  - 自动降级政策
- 版本对比字段：`contract_version`、`actions`、`light_result_shape`、`formal_result_shape`、`downgrade_policy`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

---

### AE-AW-N04｜选一个题材包能把种类、技能、克制关系一键铺进对应账本，身份标「包预填」，作者可改可删；不选包一切照常

- 模块：作者工作区
- R03 来源：CZ 2026-08-20 口述拍板（题材包选装）。
- 当前代码状态：**缺代码**
- 当前边界：当前包未见题材包预填、包身份、作者修改保留、卸载和跨账原子恢复 owner。
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N04-S01｜选装题材包按账铺入并标包预填

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：题材包安装、跨账路由与 package-prefill 身份
- 输入合同 / 必需输入：
  - package manifest
  - ten-ledger directory
  - empty project
- 输入合同 / 前置条件：
  - 所有内容为合成结构数据
  - 包不含代码/网络能力
- 输入合同 / 禁止假设：
  - 按文本自动猜目标账
  - 包项当作者自创
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成一个无版权依赖题材包：种类、技能、克制、派系各 3 条，带 package_id/version/item_id/目标账。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 体系/势力等目标账准确
  - 每条 source_kind=PACKAGE_PREFILL
  - 包版本可追
- 预期禁止：
  - 不得自动 confirmed 为已发生事实
  - 不得污染未选目标账
- 失败/恢复：任一目标账写失败时整包回滚或进入明确可恢复状态。
- 机械断言：
  - item count exact
  - target ledger exact
  - source identity exact
  - manifest closure
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 题材包安装、跨账路由与 package-prefill 身份的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；题材包安装、跨账路由与 package-prefill 身份所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 题材包安装、跨账路由与 package-prefill 身份的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 题材包安装、跨账路由与 package-prefill 身份的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 题材包安装、跨账路由与 package-prefill 身份的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N04-S01-01` — 包项身份丢失、写错账，或半包装入却报成功
- 当前代码说明：当前无题材包 runtime；可零 API 设计。
- 版本对比字段：`package_id`、`package_version`、`item_id`、`target_ledger`、`source_kind`、`install_state`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N04-S02｜不选包的项目结构与内容保持原样

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：题材包 opt-in 与零副作用
- 输入合同 / 必需输入：
  - project snapshot
  - package offer
  - skip/cancel actions
- 输入合同 / 前置条件：
  - 默认不安装
  - 目录十账独立存在
- 输入合同 / 禁止假设：
  - 展示包即预创建内容
  - cancel 后残留空包命名空间
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：同一空项目分别执行 skip/no-selection/cancel 三种路径；记录目录和各账摘要。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 三种不选路径账内容均不变
  - 无 package metadata/缓存业务对象
- 预期禁止：
  - 不得强迫包结构
  - 不得改变调用方式
- 失败/恢复：取消中断或重启后仍保持未安装。
- 机械断言：
  - tree/ledger digests unchanged
  - package item count=0
  - install status=NOT_INSTALLED
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 题材包 opt-in 与零副作用的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；题材包 opt-in 与零副作用所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 题材包 opt-in 与零副作用的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 题材包 opt-in 与零副作用的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 题材包 opt-in 与零副作用的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N04-S02-01` — 未选/取消仍写入任何包项或改变账本 schema
- 当前代码说明：未来 opt-in 机械护栏。
- 版本对比字段：`project_id`、`action`、`install_status`、`ledger_digests`、`package_item_count`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N04-S03｜作者修改包预填项后卸载不删作者版本

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：包项派生身份、作者修改和卸载保留
- 输入合同 / 必需输入：
  - installed package items
  - author edit/delete/create actions
  - uninstall
- 输入合同 / 前置条件：
  - 作者动作有独立版本/来源
  - 包原件与作者派生可区分
- 输入合同 / 禁止假设：
  - 卸载按 package_id 删除所有相关/相似项
  - 作者修改仍标纯包项
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：安装包后作者修改 2 项、删除 1 项、另新建 1 个自创项；执行卸载。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 未改包项可卸载
  - 作者修改项转为/保留作者派生身份
  - 自创项不受影响
  - 作者删除项不复活
- 预期禁止：
  - 不得删除作者修改/自创内容
  - 不得恢复作者已删项
- 失败/恢复：卸载失败保持安装前完整状态或明确 pending；重试幂等。
- 机械断言：
  - per-item provenance transition exact
  - author item count preserved
  - deleted tombstone honored
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 包项派生身份、作者修改和卸载保留的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；包项派生身份、作者修改和卸载保留所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 包项派生身份、作者修改和卸载保留的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 包项派生身份、作者修改和卸载保留的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 包项派生身份、作者修改和卸载保留的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N04-S03-01` — 卸载删除作者修改/自创项，或让作者已删除的包项复活
- 当前代码说明：需 provenance 与卸载 owner。
- 版本对比字段：`item_id`、`origin_chain`、`author_modified`、`deleted`、`post_uninstall_status`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N04-S04｜包升级与作者改动冲突时停给作者

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：包升级三方合并、冲突显式化和不自动覆盖
- 输入合同 / 必需输入：
  - package v1/v2
  - installed base
  - author derived changes
- 输入合同 / 前置条件：
  - 作者改动优先权需保留
  - 包版本不可静默升级
- 输入合同 / 禁止假设：
  - v2 全量覆盖
  - 忽略作者改动
  - 冲突自动选最新版
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：包 v1 安装后作者修改一条；包 v2 同时修改/删除该条并新增另一条。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 无冲突项可预演更新
  - 冲突项停止并列差异
  - 作者决定前 current 不变
- 预期禁止：
  - 不得把预演当已安装
  - 不得删除作者版本
- 失败/恢复：崩溃/取消升级后仍是 v1 current；重试依据 operation manifest。
- 机械断言：
  - conflict set exact
  - current package version unchanged before approval
  - preview has no truth effect
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 包升级三方合并、冲突显式化和不自动覆盖的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；包升级三方合并、冲突显式化和不自动覆盖所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 包升级三方合并、冲突显式化和不自动覆盖的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 包升级三方合并、冲突显式化和不自动覆盖的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 包升级三方合并、冲突显式化和不自动覆盖的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N04-S04-01` — 包升级静默覆盖作者改动或删除作者版本
- 当前代码说明：需 package upgrade/diff owner。
- 版本对比字段：`package_id`、`from_version`、`to_version`、`conflict_items`、`approval_state`、`current_version`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N04-S05｜恶意包目标账、重复 ID、代码/网络能力被拒绝

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：题材包 schema、能力声明和项目隔离
- 输入合同 / 必需输入：
  - malicious package manifests
  - valid control package
- 输入合同 / 前置条件：
  - 内容包应纯声明式
  - writes_truth/network/code 均无权
- 输入合同 / 禁止假设：
  - 未知字段忽略后继续
  - 路径/代码当普通文本写入
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：构造包 manifest 攻击：未知账、跨项目 source ref、重复 item_id、绝对路径、代码 payload、network=true。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 所有攻击拒绝
  - 合法控制组通过预检
  - 项目树不变
- 预期禁止：
  - 不得执行代码/联网
  - 不得读写跨项目
  - 不得自动写真值
- 失败/恢复：拒绝后无部分安装、无新目录、无秘密泄露。
- 机械断言：
  - preflight rejection exact
  - network/code execution count=0
  - tree digest unchanged
  - control passes
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 题材包 schema、能力声明和项目隔离的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；题材包 schema、能力声明和项目隔离所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 题材包 schema、能力声明和项目隔离的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 题材包 schema、能力声明和项目隔离的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 题材包 schema、能力声明和项目隔离的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N04-S05-01` — 任一恶意包执行代码/网络、跨项目写入或部分安装
- 当前代码说明：未来题材包必须复用插件内容包防线。
- 版本对比字段：`package_id`、`capabilities`、`target_ledgers`、`result_code`、`tree_digest`、`installed_count`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

#### AT5-AE-AW-N04-S06｜跨体系账/势力账安装中断可恢复且不留半包

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`DESIGNED__AWAITING_CODE`；代码状态：`缺代码`
- 主变量：跨账安装 commit manifest、恢复和 operation 冲突
- 输入合同 / 必需输入：
  - package manifest
  - two target ledgers
  - operation_id
  - failure point
- 输入合同 / 前置条件：
  - 承认跨账不天然原子
  - 旧账版本可回读
- 输入合同 / 禁止假设：
  - 第一账成功就报整体完成
  - 重启重复第一账
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：包需写体系账与势力账；在第一账提交后注入崩溃，重启同 operation 重试和篡改 payload。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 整包回滚或进入明确 pending 后补齐
  - 最终两账版本一致
  - 同 payload 幂等/篡改冲突
- 预期禁止：
  - 不得留下可见半包
  - 不得伪装跨存储原子
- 失败/恢复：恢复回执逐账列 committed/pending/rolled_back，且只有完成后 package current 生效。
- 机械断言：
  - install manifest closure
  - target generations consistent
  - replay stable
  - tampered retry rejected
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 跨账安装 commit manifest、恢复和 operation 冲突的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；跨账安装 commit manifest、恢复和 operation 冲突所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 跨账安装 commit manifest、恢复和 operation 冲突的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 跨账安装 commit manifest、恢复和 operation 冲突的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 跨账安装 commit manifest、恢复和 operation 冲突的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-AE-AW-N04-S06-01` — 半包被当已安装、重试重复项，或跨账版本不一致
- 当前代码说明：需跨账 operation manifest 和恢复 owner。
- 版本对比字段：`operation_id`、`package_sha256`、`per_ledger_state`、`install_state`、`item_counts`、`replay_result`
- 证据路径：`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`

---

### M9-N02｜驾驶舱指标（目标进度、人物与阵营计数、故事线、重大抉择、爽点计数、每章钩子）全部从已确认账算出，不产新事实、不编数

- 模块：M9
- R03 来源：CZ 2026-08-20 口述拍板（M9 驾驶舱定位）。
- 当前代码状态：**部分覆盖**
- 当前边界：M9 overview prototype 可投影 current/confirmed refs；目标进度、阵营、抉择、爽点、钩子等完整指标及逐数回源尚未齐。
- 证据路径：`02_current_route/novel-mvp/mvp/overview_tool.py`、`02_current_route/tests/test_novel_mvp_overview_tool.py`

#### AT5-M9-N02-S01｜已写章数与目标进度只从章节账/current 事实算

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：驾驶舱章节进度的 owner、current 去重和 pending 排除
- 输入合同 / 必需输入：
  - chapter ledger versions
  - closeout statuses
  - goal definition
- 输入合同 / 前置条件：
  - 每章内部 ID 唯一
  - 历史版可读但不重复计数
- 输入合同 / 禁止假设：
  - 数目录文件/版本
  - pending 算已写
  - 显示章号去重
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成章节账：8 个 current 已关章、2 个 pending/preflight、1 个历史替换版；另给目标等级定义。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 已写章数=8
  - pending/history 排除
  - 每个数字可点回 current chapter IDs
- 预期禁止：
  - 不得编一个完成百分比
  - 不得改章节账
- 失败/恢复：章节账 unavailable 时显示 UNKNOWN，不沿用旧缓存冒充 current。
- 机械断言：
  - count exact
  - source IDs exact
  - pending excluded
  - read-only digest unchanged
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 驾驶舱章节进度的 owner、current 去重和 pending 排除的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；驾驶舱章节进度的 owner、current 去重和 pending 排除所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 驾驶舱章节进度的 owner、current 去重和 pending 排除的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 驾驶舱章节进度的 owner、current 去重和 pending 排除的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 驾驶舱章节进度的 owner、current 去重和 pending 排除的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M9-N02-S01-01` — 把 pending/历史算进已写章数，或数字无法回到章节账
- 当前代码说明：overview 可投影 refs；完整指标 owner/逐数来源需补。
- 版本对比字段：`metric_id`、`value`、`source_chapter_ids`、`excluded_ids`、`ledger_version`、`freshness`
- 证据路径：`02_current_route/novel-mvp/mvp/overview_tool.py`、`02_current_route/tests/test_novel_mvp_overview_tool.py`

#### AT5-M9-N02-S02｜人物、阵营和故事线计数从各已确认账去重

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：实体计数的内部 ID、生命周期和去重
- 输入合同 / 必需输入：
  - character ledger
  - faction ledger
  - longline ledger
- 输入合同 / 前置条件：
  - current/active 规则明确
  - 显示名不是身份
- 输入合同 / 禁止假设：
  - 按名称或卡片数计数
  - 历史/合并候选重复算
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成人物/势力/长线账，含别名、合并历史、inactive 线、重复显示名；预注册 expected entity IDs。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 主要人物/朋友/反派/战友、势力和故事线按 current IDs 算
  - 分类来源可追
- 预期禁止：
  - 不得用未确认候选
  - 不得从梗概文本猜计数
- 失败/恢复：任何 owner 缺失时只将对应指标标 UNKNOWN，其余保持。
- 机械断言：
  - entity ID set exact
  - alias/merged history excluded
  - per-metric source list complete
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 实体计数的内部 ID、生命周期和去重的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；实体计数的内部 ID、生命周期和去重所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 实体计数的内部 ID、生命周期和去重的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 实体计数的内部 ID、生命周期和去重的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 实体计数的内部 ID、生命周期和去重的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M9-N02-S02-01` — 按显示名/文件数编计数，或未确认/历史对象混入
- 当前代码说明：需要多账投影接线；可零 API 验证。
- 版本对比字段：`metric_id`、`value`、`source_entity_ids`、`excluded_entity_ids`、`ledger_versions`
- 证据路径：`02_current_route/novel-mvp/mvp/overview_tool.py`、`02_current_route/tests/test_novel_mvp_overview_tool.py`

#### AT5-M9-N02-S03｜重大抉择、爽点、钩子只统计已确认登记

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：指标准入状态、类型边界和来源追溯
- 输入合同 / 必需输入：
  - typed ledger entries with statuses
  - chapter IDs
  - metric definitions
- 输入合同 / 前置条件：
  - 计划不等于已发生
  - 技巧/爽点可能是旁挂而非事实
- 输入合同 / 禁止假设：
  - 所有候选都计入
  - 从章节标题猜钩子
  - 计划选择即兑现
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 confirmed、extracted、rejected、planned 四态的决策/读者效果/章钩子条目；每类数目已知。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 只按指标合同纳入 confirmed/current
  - excluded reasons 可见
  - 每项回源
- 预期禁止：
  - 不得把 rejected/planned 写成已发生
  - 不得因统计反写真源
- 失败/恢复：指标合同未支持某类时显示 NOT_AVAILABLE/UNKNOWN，不编数。
- 机械断言：
  - status filter exact
  - excluded counts by reason
  - read-only write count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 指标准入状态、类型边界和来源追溯的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；指标准入状态、类型边界和来源追溯所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 指标准入状态、类型边界和来源追溯的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 指标准入状态、类型边界和来源追溯的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 指标准入状态、类型边界和来源追溯的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M9-N02-S03-01` — 未确认/驳回/计划内容进入已发生指标，或统计过程写账
- 当前代码说明：M9 confirmed/current 门有原型；完整指标定义未齐。
- 版本对比字段：`metric_id`、`included_entry_ids`、`excluded_entry_ids`、`status_filter`、`value`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/overview_tool.py`、`02_current_route/tests/test_novel_mvp_overview_tool.py`

#### AT5-M9-N02-S04｜某指标 owner/定义缺失时显示未知而非猜数

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：指标不可用、未知和覆盖回执
- 输入合同 / 必需输入：
  - partial ledger availability
  - metric registry
  - dashboard request
- 输入合同 / 前置条件：
  - 无 owner 不等于 0
  - 缓存可能 stale
- 输入合同 / 禁止假设：
  - 默认值 0
  - 用模型从其他文本估计
- 材料分类：`PROSE_MUST_NOT_BE_USED`
- 材料配方：移除爽点账/指标定义 owner，保留其他账；加载驾驶舱。
- 正文边界：本例验证身份、合同、存储、权限或恢复；正文会增加无关变量，禁止使用。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 爽点指标=UNKNOWN/NOT_AVAILABLE 并解释
  - 其他指标正常
  - 无新事实/估算
- 预期禁止：
  - 不得把 unknown 显示为零
  - 不得调用正文/模型补数
- 失败/恢复：owner 恢复后重新计算；旧 UNKNOWN 不被保存成真值。
- 机械断言：
  - per-metric status exact
  - model/API calls=0
  - other metrics stable
  - write count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 指标不可用、未知和覆盖回执的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；指标不可用、未知和覆盖回执所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 指标不可用、未知和覆盖回执的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 指标不可用、未知和覆盖回执的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 指标不可用、未知和覆盖回执的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M9-N02-S04-01` — 缺 owner 时编出具体数字或显示 0 误导作者
- 当前代码说明：可通过零 API fallback 合同约束；指标 registry 未完成。
- 版本对比字段：`metric_id`、`status`、`value`、`reason`、`source_owner`、`api_call_count`
- 证据路径：`02_current_route/novel-mvp/mvp/overview_tool.py`、`02_current_route/tests/test_novel_mvp_overview_tool.py`

#### AT5-M9-N02-S05｜来源账更新后驾驶舱旧投影必须 stale

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：多账投影新鲜度、source refs 和局部重算
- 输入合同 / 必需输入：
  - dashboard d1
  - source ledger versions
  - source update
  - recompute
- 输入合同 / 前置条件：
  - 投影非真值
  - source refs 完整
- 输入合同 / 禁止假设：
  - 旧快照继续标 CURRENT
  - 按 mtime 猜新鲜度
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：生成 dashboard snapshot d1，随后章节/人物/长线任一账升级 generation；读取旧 d1，再重算 d2。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - d1 标 STALE 并指出变更账
  - d2 引用新版本
  - 未变指标可证明复用
- 预期禁止：
  - 不得让旧数字冒充 current
  - 不得投影写回源账
- 失败/恢复：重算失败时 d1 保持 STALE 可读，不回标 CURRENT。
- 机械断言：
  - source version vector compare
  - stale reason exact
  - d2 current only after complete commit
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 多账投影新鲜度、source refs 和局部重算的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；多账投影新鲜度、source refs 和局部重算所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 多账投影新鲜度、source refs 和局部重算的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 多账投影新鲜度、source refs 和局部重算的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 多账投影新鲜度、source refs 和局部重算的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M9-N02-S05-01` — 源账变化后旧指标仍标 current，或失败重算把旧快照回标 current
- 当前代码说明：overview/current refs 与 stale 模式有局部能力；完整多账 vector 未接。
- 版本对比字段：`dashboard_version`、`source_version_vector`、`freshness`、`changed_ledgers`、`recompute_state`
- 证据路径：`02_current_route/novel-mvp/mvp/overview_tool.py`、`02_current_route/tests/test_novel_mvp_overview_tool.py`

#### AT5-M9-N02-S06｜统计候选、计划和投影自身不得自我计数

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：驾驶舱只读准入白名单与防自引用
- 输入合同 / 必需输入：
  - confirmed ledgers
  - candidate/projection/plan objects
  - dashboard computation
- 输入合同 / 前置条件：
  - 投影可重建
  - 计划与候选非已发生
- 输入合同 / 禁止假设：
  - 全文搜索数字
  - 上次 dashboard 作为下次输入
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：把 dashboard projection、候选指标解释、未来计划中出现的数字混入搜索范围；重启重复计算。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 只读取批准 owner/current 数据
  - 候选/计划/投影命中数=0
  - 重复计算确定性
- 预期禁止：
  - 不得统计自己产生的摘要/指标
  - 不得因显示而入账
- 失败/恢复：重启结果与同版本首算一致；无递增漂移。
- 机械断言：
  - input owner allowlist exact
  - self-reference count=0
  - deterministic digest
  - write count=0
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 驾驶舱只读准入白名单与防自引用的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；驾驶舱只读准入白名单与防自引用所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | 驾驶舱只读准入白名单与防自引用的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | 驾驶舱只读准入白名单与防自引用的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | 驾驶舱只读准入白名单与防自引用的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M9-N02-S06-01` — dashboard 把自身/候选/计划计入，导致每次重算数字增长或混账
- 当前代码说明：需要正式指标编译器 allowlist；当前 overview 仅原型。
- 版本对比字段：`metric_id`、`input_object_kinds`、`excluded_kinds`、`value`、`result_digest`、`run_number`
- 证据路径：`02_current_route/novel-mvp/mvp/overview_tool.py`、`02_current_route/tests/test_novel_mvp_overview_tool.py`

---

### M7-N01｜作者圈一段说「我觉得不好」，系统给出问题定位、原因和两种修法（最小回改／后文圆回），只出方案不动稿

- 模块：M7
- R03 来源：CZ 2026-08-20 口述拍板（M7 优化工作台定位，扩展自 M7-E09）。
- 当前代码状态：**部分覆盖**
- 当前边界：check tool 有 current/confirmed 机械门、报告不直改书稿；没有圈段语义诊断、原因和两种修法的完整运行能力。
- 证据路径：`02_current_route/novel-mvp/mvp/check_tool.py`、`02_current_route/tests/test_novel_mvp_check_tool.py`

#### AT5-M7-N01-S01｜常见圈段：定位问题、解释原因、给两种修法

- 常见程度：`common`；角色：`clean_common`；权重：`22`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`部分覆盖`
- 主变量：圈段诊断的具体性与双修法可操作性
- 输入合同 / 必需输入：
  - selected passage locator
  - bounded context recipe
  - author concern
- 输入合同 / 前置条件：
  - 只读 current confirmed chapter version
  - 语义评分由盲审完成
- 输入合同 / 禁止假设：
  - 泛泛夸赞
  - 直接重写书稿
  - 把作者不满当唯一真相
- 材料分类：`REAL_NOVEL_REQUIRED`
- 材料配方：从获授权脱敏小说抽样 12 个作者真实不满意段落，覆盖节奏/逻辑/人物/获得感；只保存 BOOK 代号、章内定位、作者标注类型和上下文窗口，不夹正文、不生成 Gold。
- 抽样要求：
  - 至少 2 个题材频率层级
  - 至少 4 类不满原因
  - 仅记录脱敏定位/标注/窗口配方
  - 不生成 Gold
- 正文边界：只登记脱敏材料配方、抽样层级、定位与 SHA；本设计不夹带正文、不生成 Gold。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 指出具体问题位置/现象
  - 解释原因
  - 最小回改和后文圆回两案均含动作/代价
- 预期禁止：
  - 不得替作者改稿
  - 不得承诺唯一正确
  - 不得泄露未来内容超范围
- 失败/恢复：材料不足时进入待补料，不生成伪诊断或修改。
- 机械断言：
  - mechanical layer verifies selected scope/current version
  - proposed edits count=0
  - two proposal slots present
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 问题定位具体且贴合圈段
  - 原因可由上下文承托
  - 最小回改说明动哪里和影响
  - 后文圆回说明不动旧章的代价与风险
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 圈段诊断的具体性与双修法可操作性未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：问题定位具体且贴合圈段；原因可由上下文承托；最小回改说明动哪里和影响；后文圆回说明不动旧章的代价与风险。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：问题定位具体且贴合圈段；原因可由上下文承托；最小回改说明动哪里和影响；后文圆回说明不动旧章的代价与风险；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-M7-N01-S01-01` — 直接输出改写后的书稿，或只给一种修法且不说明动静/代价
- 当前代码说明：check 工具只读/不直改可测；语义诊断和双方案缺代码。
- 版本对比字段：`case_id`、`passage_locator`、`diagnosis_categories`、`reason_refs`、`minimal_repair`、`forward_repair`、`write_count`
- 证据路径：`02_current_route/novel-mvp/mvp/check_tool.py`、`02_current_route/tests/test_novel_mvp_check_tool.py`

#### AT5-M7-N01-S02｜人物动机或关系推进的隐性问题

- 常见程度：`common`；角色：`dirty_common`；权重：`18`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：隐性动机/关系问题的证据边界和修法差异
- 输入合同 / 必需输入：
  - passage locator
  - confirmed fact refs
  - bounded before/after context
  - author concern
- 输入合同 / 前置条件：
  - 不使用心理标签作硬约束
  - 不读取超防剧透范围
- 输入合同 / 禁止假设：
  - 凭刻板标签判 OOC
  - 无证据说人物降智
  - 两方案只是同一句换说法
- 材料分类：`REAL_NOVEL_REQUIRED`
- 材料配方：抽样 10 个需要跨圈段前后文才能判断的人物动机/关系推进案例；仅保留脱敏定位、相关已确认事实 ID、作者不满描述。
- 抽样要求：
  - 至少 common/medium 两类题材
  - 不使用人物原名
  - 不写正文、不生成 Gold
- 正文边界：只登记脱敏材料配方、抽样层级、定位与 SHA；本设计不夹带正文、不生成 Gold。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 定位动机/关系断点
  - 引用相关事实/未知
  - 两方案在修改位置与代价上明显不同
- 预期禁止：
  - 不得把推断说成硬冲突
  - 不得直接改稿
- 失败/恢复：证据不足时标待复核并指出缺哪类材料。
- 机械断言：
  - used refs within allowed scope
  - confirmed-only refs
  - proposal differentiation field present
  - write count=0
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 动机/关系判断有事实依据
  - 区分硬冲突与软建议
  - 两种修法真正不同
  - 证据不足时明确不确定
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 隐性动机/关系问题的证据边界和修法差异未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：动机/关系判断有事实依据；区分硬冲突与软建议；两种修法真正不同；证据不足时明确不确定。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：动机/关系判断有事实依据；区分硬冲突与软建议；两种修法真正不同；证据不足时明确不确定；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-M7-N01-S02-01` — 无证据断言人物 OOC/降智，或两种修法实际相同
- 当前代码说明：未来语义能力；当前可守住只读/confirmed 输入门。
- 版本对比字段：`case_id`、`diagnosis`、`evidence_refs`、`uncertainty`、`minimal_repair_scope`、`forward_repair_scope`
- 证据路径：`02_current_route/novel-mvp/mvp/check_tool.py`、`02_current_route/tests/test_novel_mvp_check_tool.py`

#### AT5-M7-N01-S03｜少见倒叙、多视角或误导结构不被误判

- 常见程度：`medium`；角色：`structural_variant`；权重：`18`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：复杂叙事结构下的诊断准确性
- 输入合同 / 必需输入：
  - passage locator
  - narrative structure tags
  - truth/knowledge refs
- 输入合同 / 前置条件：
  - 表述事件不等于世界命题
  - 故事序与叙述序分开
- 输入合同 / 禁止假设：
  - 把倒叙当时间错误
  - 把谎言当事实冲突
  - 自动消除有意误导
- 材料分类：`REAL_NOVEL_REQUIRED`
- 材料配方：抽样 8 个倒叙、梦境、谎言、视角限制或读者误导案例；只记录结构标签、定位和已确认状态/知情 refs。
- 抽样要求：
  - 至少 3 种少见结构
  - 只保留脱敏结构标签与定位
  - 不生成 Gold
- 正文边界：只登记脱敏材料配方、抽样层级、定位与 SHA；本设计不夹带正文、不生成 Gold。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 先判断结构身份
  - 只在真实问题时诊断
  - 方案保留作者意图
- 预期禁止：
  - 不得把有意手法一律当 bug
  - 不得越过可见范围剧透
- 失败/恢复：结构不确定时要求更宽受控上下文，不作确定结论。
- 机械断言：
  - structure classification recorded
  - fact/knowledge refs legal
  - no prose write
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 识别叙事结构身份
  - 表述/事实/知情不混
  - 不消灭作者有意效果
  - 修法尊重防剧透与叙述序
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 复杂叙事结构下的诊断准确性未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：识别叙事结构身份；表述/事实/知情不混；不消灭作者有意效果；修法尊重防剧透与叙述序。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：识别叙事结构身份；表述/事实/知情不混；不消灭作者有意效果；修法尊重防剧透与叙述序；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-M7-N01-S03-01` — 把合法倒叙/谎言/误导当硬冲突并要求改掉，或泄露未释放真相
- 当前代码说明：需要真实小说语义盲测。
- 版本对比字段：`case_id`、`structure_kind`、`diagnosis_strength`、`evidence_refs`、`spoiler_scope`、`proposal_types`
- 证据路径：`02_current_route/novel-mvp/mvp/check_tool.py`、`02_current_route/tests/test_novel_mvp_check_tool.py`

#### AT5-M7-N01-S04｜圈段上下文不足时明确缺料而不是泛化诊断

- 常见程度：`medium`；角色：`missing_ambiguous_conflict`；权重：`14`
- 执行：`FUTURE_MODEL_SEMANTIC`；当前就绪度：`DESIGNED__NO_API_OR_GOLD_RUN_THIS_ROUND`；代码状态：`缺代码`
- 主变量：材料不足识别、回取请求和诊断强度
- 输入合同 / 必需输入：
  - selected passage locator
  - narrow context refs
  - optional expanded refs
- 输入合同 / 前置条件：
  - 第一阶段故意缺关键前因/人物状态
- 输入合同 / 禁止假设：
  - 无材料仍给确定原因
  - 直接扩大到全书越权读取
- 材料分类：`REAL_NOVEL_REQUIRED`
- 材料配方：从真实材料抽样 8 个仅看圈段无法判断的案例，准备窄窗口和授权扩展窗口两阶段配方；不写正文。
- 抽样要求：
  - 8 个真实脱敏案例
  - 窄/扩窗口只记录定位与 SHA
  - 不生成 Gold
- 正文边界：只登记脱敏材料配方、抽样层级、定位与 SHA；本设计不夹带正文、不生成 Gold。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 第一阶段标材料不足
  - 说明需要哪类/哪段材料
  - 授权后再诊断
- 预期禁止：
  - 不得用常识补故事
  - 不得越权读取未授权范围
- 失败/恢复：回取失败保持 UNSCORED/NEEDS_CONTEXT，不出伪方案。
- 机械断言：
  - first-stage certainty limited
  - requested refs scoped
  - no unauthorized read
  - write count=0
- 语义评分：独立人工语义评分；不得用同一生成模型自评替代。
  - 能识别关键材料缺失
  - 回取请求具体且最小
  - 未授权不扩大范围
  - 补料后才提高结论强度
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | 材料不足识别、回取请求和诊断强度未完成、方向相反、编造材料，或命中独立红线。 |
| 25 | 能识别题目大类，但只给泛化判断；在这些评分点上大多缺失：能识别关键材料缺失；回取请求具体且最小；未授权不扩大范围；补料后才提高结论强度。 |
| 50 | 主要判断基本正确，但至少一个核心评分点缺失、理由不承托或不确定性被说成事实。 |
| 75 | 核心判断、理由和边界均正确，无红线；仅有一个不影响作者决定的次要遗漏。 |
| 100 | 完整满足全部评分点：能识别关键材料缺失；回取请求具体且最小；未授权不扩大范围；补料后才提高结论强度；能明确区分事实、计划、候选和未知，不生成 Gold、不借机械 PASS 冒充语义能力。 |

- 独立红线：`RL-AT5-M7-N01-S04-01` — 缺关键上下文仍给确定诊断/修法，或未经授权读取全书
- 当前代码说明：语义缺料判断和回取协作未实现。
- 版本对比字段：`case_id`、`context_status`、`requested_scope`、`diagnosis_strength`、`authorized_refs`、`read_scope`
- 证据路径：`02_current_route/novel-mvp/mvp/check_tool.py`、`02_current_route/tests/test_novel_mvp_check_tool.py`

#### AT5-M7-N01-S05｜任何诊断和方案都不修改书稿或真值

- 常见程度：`rare`；角色：`dangerous_rare`；权重：`16`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：M7 只报告不改书的副作用边界
- 输入合同 / 必需输入：
  - current chapter identity
  - selected span
  - confirmed fact refs
  - check request
- 输入合同 / 前置条件：
  - 报告可以保存为派生资产
  - 书稿/事实账只读
- 输入合同 / 禁止假设：
  - 为了给方案先改临时正文并覆盖
  - 把建议写入真值
- 材料分类：`SYNTHETIC_SUFFICIENT`
- 材料配方：合成 current chapter、selected span、confirmed facts 和检查请求；执行报告生成前后全树 digest。
- 正文边界：仅使用合成结构化材料；不得引入真实小说正文。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 报告/建议对象可生成
  - chapter/fact/plan digests 全不变
  - 无 C11/C1/事实写入
- 预期禁止：
  - 不得生成书稿成文补丁并自动应用
  - 不得把检查结果当改史
- 失败/恢复：报告保存失败不影响任何真值对象；重试幂等。
- 机械断言：
  - truth write count=0
  - source digests unchanged
  - report identity separate
  - temp cleanup
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | M7 只报告不改书的副作用边界的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；M7 只报告不改书的副作用边界所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | M7 只报告不改书的副作用边界的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | M7 只报告不改书的副作用边界的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | M7 只报告不改书的副作用边界的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M7-N01-S05-01` — 圈段检查导致书稿、事实、规划或章节 current 任一变化
- 当前代码说明：check tool 已有只读/不直改机械边界。
- 版本对比字段：`report_id`、`source_versions`、`source_digests_before`、`source_digests_after`、`write_sets`
- 证据路径：`02_current_route/novel-mvp/mvp/check_tool.py`、`02_current_route/tests/test_novel_mvp_check_tool.py`

#### AT5-M7-N01-S06｜报告保存、重启读回与源章修改后标 stale

- 常见程度：`rare`；角色：`failure_recovery`；权重：`12`
- 执行：`ZERO_API_MECHANICAL`；当前就绪度：`PARTIAL_ZERO_API_PROBE_AVAILABLE`；代码状态：`部分覆盖`
- 主变量：M7 圈段报告持久化、新鲜度和失败恢复
- 输入合同 / 必需输入：
  - source chapter version/SHA
  - selected span locator
  - report output
  - source revision
- 输入合同 / 前置条件：
  - 报告是派生只读资产
  - 源章版本不可变历史保留
- 输入合同 / 禁止假设：
  - 源章变化后报告仍标 current
  - 按文件 mtime 判断新鲜度
- 材料分类：`REAL_NOVEL_REQUIRED`
- 材料配方：用一条真实脱敏圈段定位生成报告元数据；保存后重启读回，再将源章 current 升版。只保存定位/SHA/评分，不存正文。
- 抽样要求：
  - 真实材料只记录 BOOK 代号、定位、SHA 和作者标注类型
  - 不夹正文、不生成 Gold
- 正文边界：只登记脱敏材料配方、抽样层级、定位与 SHA；本设计不夹带正文、不生成 Gold。
- Gold 边界：不生成 Gold；机械例用确定性断言，语义例由独立人工按本例评分尺判定。
- 预期必须：
  - 重启报告内容/来源 refs 一致
  - 源章升级后报告 stale
  - 旧报告仍可审计
- 预期禁止：
  - 不得自动重写报告或书稿
  - 不得丢原来源定位
- 失败/恢复：报告 commit 中断 old-or-new 完整；失败后不影响源章。
- 机械断言：
  - report SHA stable on restart
  - source version vector compare
  - stale reason exact
  - source digest unchanged
- 语义评分：不做小说语义评分；只按机械合同、身份、版本、权限、原子性和副作用判定。
- 机械证据边界：冻结回包、Schema PASS、fixture 存在或测试文件存在，只能证明对应机械链；不能证明真实内容能力。
- 五档锚点：

| 分数 | 锚点 |
|---:|---|
| 0 | M7 圈段报告持久化、新鲜度和失败恢复的核心结果缺失、对象不可执行，或命中本例任一独立红线。 |
| 25 | 只出现表面对象或成功码；M7 圈段报告持久化、新鲜度和失败恢复所需的身份、版本、来源、负例或恢复断言多数没有证明。 |
| 50 | M7 圈段报告持久化、新鲜度和失败恢复的主路径可见，但至少一个关键断言失败，或失败关闭／历史留存／版本精确性不完整。 |
| 75 | M7 圈段报告持久化、新鲜度和失败恢复的关键机械断言全部通过且无红线；只剩不改变结果的说明、可读性或非关键覆盖缺口。 |
| 100 | M7 圈段报告持久化、新鲜度和失败恢复的正向、负向、版本对比和恢复断言全部通过；无红线、无静默降级，也没有把局部 PASS 外推成内容能力。 |

- 独立红线：`RL-AT5-M7-N01-S06-01` — 源章升级后旧报告仍冒充 CURRENT，或报告失败影响源章
- 当前代码说明：报告保存/新鲜度有相关切片；N01 语义输出本身未覆盖。
- 版本对比字段：`report_id`、`report_version`、`source_chapter_version`、`source_span_ref`、`freshness`、`commit_state`
- 证据路径：`02_current_route/novel-mvp/mvp/check_tool.py`、`02_current_route/tests/test_novel_mvp_check_tool.py`

---

## 7. 自查回执

| 检查 | 结果 |
|---|---:|
| release 文件 SHA | PASS |
| CSV 行数 / 唯一 ID | 142 / 142 |
| 旧需求 / 旧小测试 | 127 / 762 |
| 旧例每条 6 个、权重 100 | PASS |
| 新需求 / 新小测试 | 15 / 90 |
| 新 `AT5-` test_id 唯一 | 90 / 90 |
| 独立红线 ID 唯一 | 90 / 90 |
| 新例每条 6 个、权重 100 | PASS |
| 执行分类 | 60 / 13 / 17 |
| 外来道标签 | 7 条需求 / 42 个旧测试 |
| API / 模型选择 / Gold / 真实正文 | 0 / 0 / 0 / 0 |

自查只证明设计文件结构和计数正确，不证明新增能力已经实现，也不证明真实内容语义。
