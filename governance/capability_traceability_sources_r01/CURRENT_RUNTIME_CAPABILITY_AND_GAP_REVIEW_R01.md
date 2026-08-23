# 当前运行能力与真实缺口总审 R01

- 审查日期：2026-08-21
- 权限：`ADVISORY_ONLY`；只读审查，不改代码、合同、Gold、训练、API 或生产
- 当前代码：`01efc50d863bf01ac048dc6c50284fcebc7e51f4`
- 对照参考点：`a7b3ecb`
- 外审打包基线：`79bd2e2d6d0eb28610d5ed4608288251c6ffa424`（只增加外审路线／Prompt，不当运行能力）
- 产品背景：`R14`；外部报告：`R01`；原子需求：`R03`，142 条

## ✅ 结论

外来道的机械写链、事实审查、证据查询、体检报告、规划账和若干只读投影已经能独立跑；R14 自产道、十本账内容体系和完整作者主循环仍未闭合。

- 双车道只在“新章事实稿原型／pending 请求”边缘开始分开；正式 C11／章节账／事实账没有接上。
- 旧 work draft INITIAL 路径仍是可运行写路径，并且直接 C10→C11→C1→M2；它是当前最明确的 R14 路由冲突。
- 十本账已有固定目录登记和 UNKNOWN 覆盖读，但不是十个内容账。当前可复用内容入口主要只有 chapters、facts、plan。
- M4 外来章修订只做到证据迁移预演；M7 灯色和报告保存可跑；M8 长线只读 plan storylines/hooks；M11 只拼 current confirmed facts＋future planning。
- T14 unknown overlay 的存储护栏是好的，但没有直接作者 reader／closeout consumer，不能写成裁决已生效。
- 142 条原子需求：直接代码证据 61，局部证据 43，仅背景目标 36，当前路径直接相冲突 2。

说白了，当前产品已经有一批很扎实的“机械模块”：能安全写、能重启、能判旧、失败不留半份。最麻烦的地方不在这些底座，而在 **R14 新自产道还没穿过正式 C11／章节账／事实账**。新章事实稿侧目前只到原型和 pending；旧工作稿侧却已经能一路回到 M2。

## 1. 身份核对

| 项目 | 核对结果 | 关键身份 |
|---|---|---|
| Project Sources release | PASS | `PROJECT_SOURCE_RELEASE_8e66fe30e71fdfed` |
| 产品／报告／原子需求 | PASS | `R14`／`R01`／`R03`，142 条 |
| 工作区基线 | PASS | `WORKSPACE_BASELINE_79bd2e2d6d0e_1ea1f200` → `79bd2e2d6d0eb28610d5ed4608288251c6ffa424` |
| 任务 ZIP | PASS | SHA `e0ca298e61bbb2b0682eabae308026003371cec2d7a00bed84b7c841630facca`；内部 239 个成员 SHA 全通过 |
| 当前代码 | PASS | `codex/module-runtime-foundation-20260819-r01` @ `01efc50d863bf01ac048dc6c50284fcebc7e51f4` |
| 差量范围 | PASS | `a7b3ecb` → `01efc50` |

发布清单的 `remote_presence_status` 本来就写 `UNKNOWN`。这里能确认的是：**当前 Project 的 Sources 检索到了同一 release 的 router、R14、R01、R03 和基线索引，SHA 全匹配**；不把这句话扩大成别的 Project 也已安装。

### 关键 SHA

| 文件 | SHA-256 |
|---|---|
| `00_PROJECT_SOURCE_ROUTER_PROJECT_SOURCE_RELEASE_8e66fe30e71fdfed.md` | `6ba4e811d7005ff422140481fc1858d7d3e8fff2f486fe412e134456cef7ae30` |
| `PRODUCT_R14__SEMANTIC.md` | `a9f89274e42f056d4a040d23deabdb4e4ce2ab8051fce47af4d88af1a8560487` |
| `REPORT_R01__SEMANTIC.md` | `783f31566bcaf36083700243369d0acf35d812cc4cc33f5cb949d4d4b8f32a47` |
| `ATOMIC_R03__142_EXPECTATIONS.csv` | `11749551b55f13dd4ae63e90a85a20a7492959c16eb219385ac152d36fe41937` |
| `WORKSPACE_BASELINE_79bd2e2d6d0e_1ea1f200__INDEX.json` | `5e87679fe2a0c3b6bae0bf012d97fd1a743cb36449d323e7c3e9c26352d2bb21` |
| `PROJECT_SOURCE_RELEASE.json` | `ab2155e19a8a33fea573896f22e97ac3ea6ecd5a46cf41940267cc9163318ac6` |
| `CHATGPT_FLAT_BACKGROUND_BOARDS_PRODUCT_R14_REPORT_R01_ATOMIC_R03.zip` | `cf22978d966401ebd0ca26b5df67de287a00ebd52f93fad232549cbbe3304010` |
| `CHATGPT_WORKSPACE_BASELINE_79bd2e2d6d0e_1ea1f200.zip` | `27c8b12c73ec14541c049117685a0c5f788d38355c0a54d533f298d7f807c93b` |

## 2. 这六档怎样读

- **`RUNNABLE_WRITE_PATH`**：真实输入能进入受控写口，保存、重启读回、失败不留半份，并有直接使用方。只对该窄能力成立，不自动代表整条产品链完成。
- **`RUNNABLE_READ_PATH`**：能从有权的当前数据安全读取、编译或展示；读取失败会停，不负责把结果写进真值。
- **`PROTOTYPE_FILE_ONLY`**：只能生成或读取本地原型文件。文件形状、稳定 SHA 或作者可读性可以被证明，但没有正式工作区写入和直接下游。
- **`PREFLIGHT_ONLY`**：只计算如果提交会发生什么，所有正式写集仍为 none。预演通过不等于已经提交。
- **`BLOCKED_BY_PRODUCT_DECISION`**：产品语义还没冻结，继续接线会替 CZ 做决定。
- **`BROKEN_OR_UNPROVEN`**：代码与目标语义打架，或只有机械壳／局部测试，缺少证明该用户结果成立的直接证据。

🔥 同一模块可能同时有两种身份。例如 M3 的运行回执和候选保存是可运行写路径，但“真实小说语义抽取质量”仍是 `BROKEN_OR_UNPROVEN`。这不是矛盾，是把机械行为和模型能力分开。

## 3. 当前 M1～M11 与工作区能力图

| 能力 | 归类 | 现在真的交出什么 | 主要缺口 |
|---|---|---|---|
| `MOD-M1-EXTERNAL-INTAKE` M1 外来材料入料与章节身份 | `RUNNABLE_WRITE_PATH` | TXT、MD、DOCX、ZIP 和显式 CSV 能进入受控入料；原始 bytes、C10 身份、C11 版本和 C1 当前章视图有真实工作区落点。Excel 不会被当普通 ZIP 偷拆，而是明确停在转换门。 | 能跑的是受控入料和身份链，不是“自动看懂所有混合材料”。CSV 不拆表头语义；XLS/XLSX/XLSM 当前只给转换办法。 |
| `MOD-M2-SEGMENT` M2 责任段切分与持久化 | `RUNNABLE_WRITE_PATH` | 当前 C1 章可以被切成带版本门牌、正文责任区和只读 halo 的 C2 段，并保存、重启和判旧。 | 机械切分可靠，但它现在不会判断“这是不是自产章事实稿”。双车道未接好前，M2 本身无法阻止错误车道。 |
| `MOD-M3-RUN-LEDGER` M3 运行回执与候选文件持久化 | `RUNNABLE_WRITE_PATH` | M3 的 transport、timeout、截断、坏回包和候选快照能留下结构化回执；完整候选批次可以保存，失败批次不会替换当前完整 C3。 | 这只证明 transport／parser／持久化。包内没有真实模型语义胜负，冻结响应通过不能证明“计划、梦境、传闻都识别正确”。 |
| `MOD-M3-SEMANTIC` M3 真实小说语义抽取 | `BROKEN_OR_UNPROVEN` | 当前代码可以承接模型回包，却没有在本包内证明真实小说上的漏抽、错抽、事实粒度和旁挂推断质量。 | 没有真实小说、Gold 或模型调用证据，不能写成生产抽取能力已过。 |
| `MOD-M4-EXTERNAL-FACTS` M4 外来章候选与事实状态账 | `RUNNABLE_WRITE_PATH` | 外来道 C3 候选可以进入有作者／项目隔离、证据锚、状态和版本的事实工作区；candidate、confirmed、rejected、needs_recheck 不会静默混成一态。 | 自产章作者签字入事实账仍未接；核心句＋qualifiers、覆盖账和相似组也没有完整落地。 |
| `MOD-M5-REVIEW` M5 作者确认／驳回写口 | `RUNNABLE_WRITE_PATH` | 作者能按事实条目执行确认、驳回或受控改写；动作有版本、幂等和冲突保护，沉默不会变确认。 | “每千字确认负担”、完整故事概览优先页、死亡复活单签全语义还没有直接完成证据。 |
| `MOD-M6-ASK` M6 证据查询 | `RUNNABLE_READ_PATH` | M6 能从当前已确认、符合范围的事实中返回证据、排除范围和弃权；不会因为没命中就编故事。 | 现有能力偏字面／结构化检索，不能证明大白话问题、别名和多跳关系都能稳定找对。 |
| `MOD-M7-HEALTH` M7 一致性体检报告 | `RUNNABLE_WRITE_PATH` | M7 可以从 current facts 编译 C6 体检报告，保存、重启读回、判 stale。confirmed 硬冲突才允许红灯，候选或混合证据最多黄灯。 | 当前不是 R14 所说的完整优化工作台：还没有“位置＋原因＋最小回改＋后文圆回”的完整作者方案。 |
| `MOD-M8-PLANSTORE` M8 规划账机械写口 | `RUNNABLE_WRITE_PATH` | 规划对象、选择动作、章槽和交棒状态有单一 planstore 写口，能保存、重启、幂等和处理并发；规划轴与实际发生轴分开。 | 机械账可跑不等于 M8 已能稳定把作者一句话变成完整章计划。选择卡全文留底、正式选中写回和完整长线内容仍是缺口。 |
| `MOD-M8-AUTHOR-PLANNING` M8 作者下一章规划语义 | `BROKEN_OR_UNPROVEN` | 代码里有规划对象和局部动作，但没有直接证据证明三档规划、跨层约束、插件冲突、卷纲摊章和灵感时机能组成作者可用主路径。 | 不能宣称 M8 主路径完成。 |
| `MOD-M9-OVERVIEW` M9 概览投影 | `RUNNABLE_READ_PATH` | M9 有按当前有权来源编译、保存和读回的概览切片，能保留事实／计划分区并在源变化后标旧。 | 完整“梗概＋概览＋战报”首屏、全书／卷缩放和 R14 驾驶舱指标还没有直接代码证据。 |
| `MOD-M10-SCENE-EXPORT` M10 场景卡和导出投影 | `RUNNABLE_READ_PATH` | 当前 C7／章槽切片可以生成场景卡和 JSON、Markdown、ZIP 等确定性投影，顺序、来源版本和 stale 可以机械检查。 | 人物在第 N 章的故事时间状态仍缺可信 owner；当前不能保证跨场人物外观／伤势完全一致。 |
| `MOD-M11-PACKER` M11 当前事实打包与回取 | `RUNNABLE_READ_PATH` | M11 可以只读 current confirmed facts，执行硬预算、记录遗漏，并用受控回取 handle 取回被明确省略的内容；读侧不写 facts。 | 它不是从十本账统一取件的完整 M11，也没有远近压缩、宽窗路由和全部 handle owner。 |
| `MOD-AUTHOR-WORKSPACE` AuthorWorkspace 存储与隔离底座 | `RUNNABLE_WRITE_PATH` | 作者／项目绑定、白名单键、原子多键提交、恢复扫描、原始 bytes 和版本链是当前最扎实的运行底座。 | 项目列表／上次光标、云对象服务替换、十本账内容升级仍没有全部证据。 |
| `MOD-SELF-LANE-FORMAL` R14 自产章正式主路径 | `BLOCKED_BY_PRODUCT_DECISION` | 章事实稿怎样逐条或整包进入事实账、高影响项怎样单签、INITIAL 章号／revision 怎样正式分配，仍没有冻结。现有代码只能做到原型文件和 pending 请求。 | 这是专项窗口的核心，不在本窗口出重复施工卡。 |
| `MOD-OLD-WORKDRAFT-LANE` 旧工作稿 INITIAL 交棒路径 | `BROKEN_OR_UNPROVEN` | 这条旧路径机械上很完整：作者工作稿会进入 C10、C11、C1，重启后继续到 M2。也正因为如此，它直接证明 R14 纠偏尚未切流：产品自产内容仍有一条可被送回抽取链的运行路径。 | 不能把机械 PASS 写成产品主路径 PASS；这是一条需要切流或封门的旧运行能力。 |

### MOD-M1-EXTERNAL-INTAKE｜M1 外来材料入料与章节身份｜`RUNNABLE_WRITE_PATH`

TXT、MD、DOCX、ZIP 和显式 CSV 能进入受控入料；原始 bytes、C10 身份、C11 版本和 C1 当前章视图有真实工作区落点。Excel 不会被当普通 ZIP 偷拆，而是明确停在转换门。

- **输入**：上传文件名、原始 bytes、作者明确或路由得到的材料身份。
- **输出**：不可变上传源、C10 材料身份、C11 章节修订、C1 当前章视图，以及导入回执。
- **保存位置**：AuthorWorkspace 的 upload_sources、intake_materials、chapter_revisions、chapters 等登记键。
- **怎样接过去**：外来章节可交给 M2；非章节材料留在自己的材料身份，不会自动生成 C1。
- **实际使用方**：M2、后续外来道模块、作者导入结果页。
- **成功主路径**：输入先校验和分流，再以 guarded commit 写入；重放同一 operation 可幂等读回。
- **失败不变式**：任一成员非法、Excel 未转换、版本冲突或源内容变化时整批不写；原始 bytes 不被后续模块覆盖。
- **重启／过期**：C10／C11／C1 可重启读回；新修订会让旧 current 和下游派生物过期。
- **相邻兼容**：外来章身份可被 external_chapter_route_tool 机械证明；CSV 只按严格文本进入，尚不是表格语义解析。
- ⚠️ **仍不能宣称**：能跑的是受控入料和身份链，不是“自动看懂所有混合材料”。CSV 不拆表头语义；XLS/XLSX/XLSM 当前只给转换办法。
- **代码／合同**：`02_current_route/novel-mvp/mvp/input_router.py`<br>`02_current_route/novel-mvp/mvp/upload_source.py`<br>`02_current_route/novel-mvp/mvp/ingest_workspace.py`<br>`02_current_route/novel-mvp/mvp/intake_identity.py`<br>`02_current_route/novel-mvp/mvp/admission.py`<br>`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`<br>`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`<br>`02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py`<br>`02_current_route/tests/test_novel_mvp_c10_first_entrypoints.py`<br>`02_current_route/tests/test_novel_mvp_ingest_workspace.py`<br>`02_current_route/tests/test_novel_mvp_upload_source.py`

### MOD-M2-SEGMENT｜M2 责任段切分与持久化｜`RUNNABLE_WRITE_PATH`

当前 C1 章可以被切成带版本门牌、正文责任区和只读 halo 的 C2 段，并保存、重启和判旧。

- **输入**：同一作者项目里的当前 C1 章节集合和切段参数。
- **输出**：C2 responsibility segments，包含章／修订／位置／责任文本／前后文 halo。
- **保存位置**：AuthorWorkspace 的 segments 当前版本。
- **怎样接过去**：交给 M3 候选抽取；旧段在上游章修订变化后标 stale。
- **实际使用方**：M3 机械抽取入口和作者／调试切段小票。
- **成功主路径**：先把整批章节身份和覆盖校验完，再一次性提交段集合。
- **失败不变式**：任何章版本不对、覆盖失败、源变化或版本冲突时整批零写入，不能留下前几章的半套段。
- **重启／过期**：保存后可重启读回；上游 C1 revision 或 SHA 变化会使段过期。
- **相邻兼容**：与外来章 C1 相邻兼容已证；代码没有 lane marker，因此也会吃到旧“产品内工作稿→C1”路径。
- ⚠️ **仍不能宣称**：机械切分可靠，但它现在不会判断“这是不是自产章事实稿”。双车道未接好前，M2 本身无法阻止错误车道。
- **代码／合同**：`02_current_route/novel-mvp/mvp/segment_tool.py`<br>`02_current_route/novel-mvp/mvp/segment_workspace.py`<br>`02_current_route/novel-mvp/contracts/C2_SEGMENT.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_segment_workspace.py`

### MOD-M3-RUN-LEDGER｜M3 运行回执与候选文件持久化｜`RUNNABLE_WRITE_PATH`

M3 的 transport、timeout、截断、坏回包和候选快照能留下结构化回执；完整候选批次可以保存，失败批次不会替换当前完整 C3。

- **输入**：当前 C2 段、冻结的响应映射或 provider 调用结果、运行身份。
- **输出**：fact_candidate_runs 运行账和 fact_candidates 当前候选快照。
- **保存位置**：AuthorWorkspace 的 fact_candidate_runs、fact_candidates。
- **怎样接过去**：完整 current C3 可交给 M4；失败回执只用于诊断和重跑。
- **实际使用方**：M4 的完整候选门、调试与运行审计。
- **成功主路径**：候选先逐条验证来源、段身份和 Schema，运行回执与候选快照一起 guarded commit。
- **失败不变式**：timeout、截断、transport error、旧版本、缺响应或坏候选会结构化失败；当前完整候选不被半份结果覆盖。
- **重启／过期**：运行账和 current candidates 可重启读回；C2 变化后旧候选不可冒充 current complete。
- **相邻兼容**：M4 只读 current complete C3 的机械门存在。
- ⚠️ **仍不能宣称**：这只证明 transport／parser／持久化。包内没有真实模型语义胜负，冻结响应通过不能证明“计划、梦境、传闻都识别正确”。
- **代码／合同**：`02_current_route/novel-mvp/mvp/extract.py`<br>`02_current_route/novel-mvp/mvp/extract_tool.py`<br>`02_current_route/novel-mvp/mvp/extract_workspace.py`<br>`02_current_route/novel-mvp/mvp/extract_run_receipt.py`<br>`02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_extract_transport_receipts.py`<br>`02_current_route/tests/test_novel_mvp_extract_run_receipt.py`<br>`02_current_route/tests/test_novel_mvp_extract_workspace.py`

### MOD-M3-SEMANTIC｜M3 真实小说语义抽取｜`BROKEN_OR_UNPROVEN`

当前代码可以承接模型回包，却没有在本包内证明真实小说上的漏抽、错抽、事实粒度和旁挂推断质量。

- **输入**：真实责任段和真实模型。
- **输出**：语义正确、证据承托完整的 C3 候选。
- **保存位置**：理想状态仍会落 fact_candidates；本审查没有新建任何数据。
- **怎样接过去**：M4。
- **实际使用方**：M4 和后续作者确认。
- **成功主路径**：机械壳能运行。
- **失败不变式**：语义错也可能是合法 JSON；代码校验无法替代小说语义判断。
- **重启／过期**：不适用；质量需要真实材料和现行评测。
- **相邻兼容**：与 transport 相邻兼容不等于语义完成。
- ⚠️ **仍不能宣称**：没有真实小说、Gold 或模型调用证据，不能写成生产抽取能力已过。
- **代码／合同**：`02_current_route/novel-mvp/mvp/extract.py`<br>`02_current_route/novel-mvp/mvp/extract_tool.py`<br>`02_current_route/novel-mvp/mvp/extract_workspace.py`<br>`02_current_route/novel-mvp/mvp/extract_run_receipt.py`<br>`02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_extract_transport_receipts.py`<br>`02_current_route/tests/test_novel_mvp_extract_run_receipt.py`<br>`02_current_route/tests/test_novel_mvp_extract_workspace.py`

### MOD-M4-EXTERNAL-FACTS｜M4 外来章候选与事实状态账｜`RUNNABLE_WRITE_PATH`

外来道 C3 候选可以进入有作者／项目隔离、证据锚、状态和版本的事实工作区；candidate、confirmed、rejected、needs_recheck 不会静默混成一态。

- **输入**：current complete C3、外来章身份、作者动作或事实批次。
- **输出**：候选／事实条目、状态历史、来源和锚点。
- **保存位置**：AuthorWorkspace facts 与相关 review state。
- **怎样接过去**：M5 审查、M6 查询、M7 体检、M9／M11 读取。
- **实际使用方**：M5～M11 的读侧。
- **成功主路径**：批次校验后原子提交，跨作者／跨项目隔离。
- **失败不变式**：一条坏事实会挡住整批；证据断裂或修订迁移不唯一时不得继续当 current confirmed。
- **重启／过期**：可重启读回；证据或章版本变化触发 stale／needs_recheck。
- **相邻兼容**：与 M5、M6、M7 的直接测试相邻。
- ⚠️ **仍不能宣称**：自产章作者签字入事实账仍未接；核心句＋qualifiers、覆盖账和相似组也没有完整落地。
- **代码／合同**：`02_current_route/novel-mvp/mvp/fact_tool.py`<br>`02_current_route/novel-mvp/mvp/fact_workspace.py`<br>`02_current_route/novel-mvp/mvp/factstore.py`<br>`02_current_route/novel-mvp/mvp/fact_revision_preflight_tool.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_fact_workspace.py`<br>`02_current_route/tests/test_novel_mvp_fact_revision_preflight_tool.py`

### MOD-M5-REVIEW｜M5 作者确认／驳回写口｜`RUNNABLE_WRITE_PATH`

作者能按事实条目执行确认、驳回或受控改写；动作有版本、幂等和冲突保护，沉默不会变确认。

- **输入**：当前事实候选、明确作者动作、expected version。
- **输出**：新的事实状态和审查动作历史。
- **保存位置**：AuthorWorkspace facts／review action 相关键。
- **怎样接过去**：confirmed 可被 M6／M7／M9／M11 使用；rejected 不进入这些 current truth 读取面。
- **实际使用方**：事实账读侧和作者审查页。
- **成功主路径**：作者动作先验证目标、来源和版本，再 guarded commit。
- **失败不变式**：并发或旧页操作失败不覆盖 current；高影响专用语义不允许靠默认值偷填。
- **重启／过期**：动作可重启读回，旧决定保留；源事实变化会使旧页过期。
- **相邻兼容**：与 factstore、review queue 相邻兼容。
- ⚠️ **仍不能宣称**：“每千字确认负担”、完整故事概览优先页、死亡复活单签全语义还没有直接完成证据。
- **代码／合同**：`02_current_route/novel-mvp/mvp/review_decision_tool.py`<br>`02_current_route/novel-mvp/mvp/review_workspace.py`<br>`02_current_route/novel-mvp/mvp/review_queue_workspace.py`<br>`02_current_route/novel-mvp/contracts/FACT_REVIEW_ACTION.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_fact_review_transaction.py`<br>`02_current_route/tests/test_novel_mvp_review_queue_workspace.py`

### MOD-M6-ASK｜M6 证据查询｜`RUNNABLE_READ_PATH`

M6 能从当前已确认、符合范围的事实中返回证据、排除范围和弃权；不会因为没命中就编故事。

- **输入**：作者／项目绑定、查询条件、截止章或可见范围。
- **输出**：命中事实、证据锚、读取范围、未命中／材料不足回执。
- **保存位置**：默认不写真值；查询结果是临时读结果。
- **怎样接过去**：作者问答页；必要时只能另行提名候选。
- **实际使用方**：作者查询与 M7 转交。
- **成功主路径**：先构造安全 scope，再只读 facts／chapter index。
- **失败不变式**：跨作者、路径伪造、无权范围、证据不全都 fail closed；无命中写“当前范围未找到”。
- **重启／过期**：读面会随 facts／chapter index 变化；不会自己保留成第二真源。
- **相邻兼容**：与 M4 current confirmed facts 相邻兼容。
- ⚠️ **仍不能宣称**：现有能力偏字面／结构化检索，不能证明大白话问题、别名和多跳关系都能稳定找对。
- **代码／合同**：`02_current_route/novel-mvp/mvp/ask_tool.py`<br>`02_current_route/novel-mvp/mvp/ask_workspace.py`<br>`02_current_route/novel-mvp/mvp/ask_context_workspace.py`<br>`02_current_route/novel-mvp/mvp/ask_reader_scope_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_ask_workspace.py`<br>`02_current_route/tests/test_novel_mvp_ask_reader_scope_workspace.py`

### MOD-M7-HEALTH｜M7 一致性体检报告｜`RUNNABLE_WRITE_PATH`

M7 可以从 current facts 编译 C6 体检报告，保存、重启读回、判 stale。confirmed 硬冲突才允许红灯，候选或混合证据最多黄灯。

- **输入**：current facts、chapter index、受控 provider finding。
- **输出**：C6 health report、证据和覆盖信息。
- **保存位置**：AuthorWorkspace health_report 投影。
- **怎样接过去**：作者体检页；只报告，不改书稿、事实或规划。
- **实际使用方**：作者和后续修复提案入口。
- **成功主路径**：读取源双检，provider 输出再按本地规则重算 severity，再保存投影。
- **失败不变式**：源在运行中变化时丢弃结果；坏 provider、跨项目、旧版本不会覆盖已保存报告。
- **重启／过期**：报告可重启读回；facts／index 前进后显示 stale。
- **相邻兼容**：与 M4 facts 相邻；没有自动修订写口。
- ⚠️ **仍不能宣称**：当前不是 R14 所说的完整优化工作台：还没有“位置＋原因＋最小回改＋后文圆回”的完整作者方案。
- **代码／合同**：`02_current_route/novel-mvp/mvp/check_tool.py`<br>`02_current_route/novel-mvp/mvp/check_workspace.py`<br>`02_current_route/novel-mvp/mvp/check_reader_workspace.py`<br>`02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_check_workspace.py`

### MOD-M8-PLANSTORE｜M8 规划账机械写口｜`RUNNABLE_WRITE_PATH`

规划对象、选择动作、章槽和交棒状态有单一 planstore 写口，能保存、重启、幂等和处理并发；规划轴与实际发生轴分开。

- **输入**：合法 plan-v2、C7 selection action、expected version。
- **输出**：current planning ledger、操作历史、章槽状态。
- **保存位置**：AuthorWorkspace plan。
- **怎样接过去**：M8 读侧、M10／M11 规划读取、章事实稿供料。
- **实际使用方**：规划模块和派生投影。
- **成功主路径**：所有计划状态变化经 planstore 校验和 guarded commit。
- **失败不变式**：旧版本、重复 operation 不同 payload、并发和非法状态不会半写。
- **重启／过期**：可重启；旧候选和旧槽位可判 stale。
- **相邻兼容**：M10／M11 可读 current plan；章事实稿 pending 会绑定 current plan snapshot。
- ⚠️ **仍不能宣称**：机械账可跑不等于 M8 已能稳定把作者一句话变成完整章计划。选择卡全文留底、正式选中写回和完整长线内容仍是缺口。
- **代码／合同**：`02_current_route/novel-mvp/mvp/plan_tool.py`<br>`02_current_route/novel-mvp/mvp/plan_workspace.py`<br>`02_current_route/novel-mvp/mvp/planstore.py`<br>`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`<br>`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`<br>`02_current_route/novel-mvp/contracts/C7_SELECTION_ACTION.md`<br>`02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_plan_workspace.py`<br>`02_current_route/tests/test_novel_mvp_planstore_handover.py`

### MOD-M8-AUTHOR-PLANNING｜M8 作者下一章规划语义｜`BROKEN_OR_UNPROVEN`

代码里有规划对象和局部动作，但没有直接证据证明三档规划、跨层约束、插件冲突、卷纲摊章和灵感时机能组成作者可用主路径。

- **输入**：作者目标、全书／卷／章约束、长线和 confirmed facts。
- **输出**：完整可选章计划、全部选择卡历史、正式 current plan。
- **保存位置**：理想落 planstore；当前只证明部分对象。
- **怎样接过去**：章事实稿供料、M10、M11。
- **实际使用方**：作者规划工作台。
- **成功主路径**：局部机械写口可运行。
- **失败不变式**：语义问题可能被省略、默认或错误归位，测试数量不能替代真实规划质量。
- **重启／过期**：局部 planstore 可重启。
- **相邻兼容**：下游能读 plan，但完整 producer 未证。
- ⚠️ **仍不能宣称**：不能宣称 M8 主路径完成。
- **代码／合同**：`02_current_route/novel-mvp/mvp/plan_tool.py`<br>`02_current_route/novel-mvp/mvp/plan_workspace.py`<br>`02_current_route/novel-mvp/mvp/planstore.py`<br>`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`<br>`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`<br>`02_current_route/novel-mvp/contracts/C7_SELECTION_ACTION.md`<br>`02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_plan_workspace.py`<br>`02_current_route/tests/test_novel_mvp_planstore_handover.py`

### MOD-M9-OVERVIEW｜M9 概览投影｜`RUNNABLE_READ_PATH`

M9 有按当前有权来源编译、保存和读回的概览切片，能保留事实／计划分区并在源变化后标旧。

- **输入**：current confirmed facts、chapter index、可选 current plan。
- **输出**：只读 overview／book overview 投影。
- **保存位置**：AuthorWorkspace overview 派生物；写的是可重建投影，不是真值。
- **怎样接过去**：作者概览页、返回项目后的阅读面。
- **实际使用方**：作者读侧。
- **成功主路径**：读取源身份，编译投影，保存前重验。
- **失败不变式**：源变化、坏引用或跨项目会拒绝；投影不反写 facts／plan。
- **重启／过期**：可重启读回并判 stale。
- **相邻兼容**：与 M4、planstore 相邻读取。
- ⚠️ **仍不能宣称**：完整“梗概＋概览＋战报”首屏、全书／卷缩放和 R14 驾驶舱指标还没有直接代码证据。
- **代码／合同**：`02_current_route/novel-mvp/mvp/overview_workspace.py`<br>`02_current_route/novel-mvp/mvp/overview_book_workspace.py`<br>`02_current_route/novel-mvp/mvp/overview_reader_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_overview_workspace.py`<br>`02_current_route/tests/test_novel_mvp_overview_book_workspace.py`

### MOD-M10-SCENE-EXPORT｜M10 场景卡和导出投影｜`RUNNABLE_READ_PATH`

当前 C7／章槽切片可以生成场景卡和 JSON、Markdown、ZIP 等确定性投影，顺序、来源版本和 stale 可以机械检查。

- **输入**：current plan／chapter slot、场景列表和导出模板。
- **输出**：场景卡、Markdown／JSON／ZIP 派生文件。
- **保存位置**：AuthorWorkspace 的派生投影或调用方指定的安全输出文件。
- **怎样接过去**：外部视频／分镜工具和作者导出。
- **实际使用方**：M10 作者页、外部工具。
- **成功主路径**：只读 current plan，按确定性顺序生成派生物。
- **失败不变式**：源变、场景串号、非法输出路径、部分写失败都不能留下半个正式包。
- **重启／过期**：输出可复现；plan 变化后旧卡 stale。
- **相邻兼容**：能消费现有 C7 机械结构。
- ⚠️ **仍不能宣称**：人物在第 N 章的故事时间状态仍缺可信 owner；当前不能保证跨场人物外观／伤势完全一致。
- **代码／合同**：`02_current_route/novel-mvp/mvp/scene_export.py`<br>`02_current_route/novel-mvp/mvp/scene_export_workspace.py`<br>`02_current_route/novel-mvp/mvp/scene_export_bundle_workspace.py`<br>`02_current_route/novel-mvp/mvp/scene_card_workspace.py`<br>`02_current_route/novel-mvp/mvp/scene_state_interval_resolver.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_scene_export_workspace.py`<br>`02_current_route/tests/test_novel_mvp_scene_export_bundle_workspace.py`<br>`02_current_route/tests/test_novel_mvp_scene_card_workspace.py`

### MOD-M11-PACKER｜M11 当前事实打包与回取｜`RUNNABLE_READ_PATH`

M11 可以只读 current confirmed facts，执行硬预算、记录遗漏，并用受控回取 handle 取回被明确省略的内容；读侧不写 facts。

- **输入**：任务、current facts／chapter index、预算和可选 recall handle。
- **输出**：事实前提包、遗漏清单、预算回执、回取内容。
- **保存位置**：默认是短命派生结果；不建立第二真源。
- **怎样接过去**：M8／M7／章事实稿材料编译等调用方。
- **实际使用方**：需要当前事实的下游。
- **成功主路径**：先按身份与重要性选材，再硬预算；源在最终检查前必须不变。
- **失败不变式**：非 confirmed、旧锚、危险 handle、源变化或预算 unresolved 会停，不泄漏半包。
- **重启／过期**：同源可复现；源变化后旧 handle／包失效。
- **相邻兼容**：与 facts、chapter index 相邻；与 planning bundle 有局部拼装。
- ⚠️ **仍不能宣称**：它不是从十本账统一取件的完整 M11，也没有远近压缩、宽窗路由和全部 handle owner。
- **代码／合同**：`02_current_route/novel-mvp/mvp/packer_tool.py`<br>`02_current_route/novel-mvp/mvp/packer_workspace.py`<br>`02_current_route/novel-mvp/mvp/packer_fact_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_material_bundle_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`<br>`02_current_route/tests/test_novel_mvp_packer_fact_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_material_bundle_workspace.py`

### MOD-AUTHOR-WORKSPACE｜AuthorWorkspace 存储与隔离底座｜`RUNNABLE_WRITE_PATH`

作者／项目绑定、白名单键、原子多键提交、恢复扫描、原始 bytes 和版本链是当前最扎实的运行底座。

- **输入**：author_id、project_id、登记逻辑键、expected versions。
- **输出**：版本化 JSON／bytes、commit manifest 和恢复结果。
- **保存位置**：项目专属工作区。
- **怎样接过去**：所有当前模块的统一读写接口。
- **实际使用方**：M1～M11 及作者工作区各切片。
- **成功主路径**：读写必须走登记键和 workspace handle；多键写通过事务护栏。
- **失败不变式**：绝对路径、..、软链接、跨作者猜号、未知键、版本冲突均拒绝；读操作不建目录。
- **重启／过期**：崩溃后能回滚或补全 commit；重开保留 current pointer。
- **相邻兼容**：多数模块已经改用该接口。
- ⚠️ **仍不能宣称**：项目列表／上次光标、云对象服务替换、十本账内容升级仍没有全部证据。
- **代码／合同**：`02_current_route/novel-mvp/mvp/workspace.py`<br>`02_current_route/novel-mvp/mvp/store.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_workspace.py`

### MOD-SELF-LANE-FORMAL｜R14 自产章正式主路径｜`BLOCKED_BY_PRODUCT_DECISION`

章事实稿怎样逐条或整包进入事实账、高影响项怎样单签、INITIAL 章号／revision 怎样正式分配，仍没有冻结。现有代码只能做到原型文件和 pending 请求。

- **输入**：current plan、章事实稿、作者明确交棒。
- **输出**：目标应是 C11／章节账 current 版、事实准入结果、下一章 plan 起点，且 M2／M3 调用为 0。
- **保存位置**：目标存储应是 chapter revisions／chapter ledger、facts、plan；当前没有这次正式提交。
- **怎样接过去**：下一章规划、M9、M10、M11。
- **实际使用方**：自产章后续全部功能。
- **成功主路径**：当前 pending 保存可运行。
- **失败不变式**：现在接写会替 CZ决定确认粒度和高影响规则。
- **重启／过期**：pending 可重启；正式提交不存在。
- **相邻兼容**：没有与 C11／facts／plan 的正式相邻提交。
- ⚠️ **仍不能宣称**：这是专项窗口的核心，不在本窗口出重复施工卡。
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_reader_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_initial_admission_workspace.py`<br>`02_current_route/novel-mvp/mvp/work_draft_workspace.py`<br>`02_current_route/novel-mvp/mvp/segment_workspace.py`<br>`02_current_route/novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_draft_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_reader_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_initial_admission_workspace.py`<br>`02_current_route/tests/test_novel_mvp_segment_workspace.py`

### MOD-OLD-WORKDRAFT-LANE｜旧工作稿 INITIAL 交棒路径｜`BROKEN_OR_UNPROVEN`

这条旧路径机械上很完整：作者工作稿会进入 C10、C11、C1，重启后继续到 M2。也正因为如此，它直接证明 R14 纠偏尚未切流：产品自产内容仍有一条可被送回抽取链的运行路径。

- **输入**：作者 work draft、INITIAL handover action、current plan slot。
- **输出**：C10 source、C11 revision、C1 current chapter，随后 C2 segments。
- **保存位置**：AuthorWorkspace intake_materials、chapter_revisions、chapters、segments。
- **怎样接过去**：旧 M2／M3 外来式抽取链。
- **实际使用方**：M2。
- **成功主路径**：guarded commit、重启和故障恢复都被直接测试。
- **失败不变式**：写失败零半份；但成功本身与 R14 自产道语义冲突。
- **重启／过期**：可重启进入 M2。
- **相邻兼容**：与 M2 机械兼容，和 R14 自产章“零 M2／M3”不兼容。
- ⚠️ **仍不能宣称**：不能把机械 PASS 写成产品主路径 PASS；这是一条需要切流或封门的旧运行能力。
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_initial_admission_workspace.py`<br>`02_current_route/novel-mvp/mvp/work_draft_workspace.py`<br>`02_current_route/novel-mvp/mvp/segment_workspace.py`<br>`02_current_route/novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_initial_admission_workspace.py`<br>`02_current_route/tests/test_novel_mvp_segment_workspace.py`

## 4. `a7b3ecb` 之后每组新增能力归类

| 增量 | 提交 | 归类 | 大白话结论 |
|---|---|---|---|
| `DELTA-01-LEDGER-PROTOTYPE-FILE` 十本账目录原型文件 | `3f69b3b` | `PROTOTYPE_FILE_ONLY` | 能生成一份固定十本账名称、顺序和说明的本地 JSON 原型；它不创建任何一本真实内容账。 |
| `DELTA-02-LEDGER-REGISTRATION` 十本账固定身份登记 | `3f69b3b` | `RUNNABLE_WRITE_PATH` | 作者工作区里能保存十本账的固定名称、顺序和职责目录。保存的是“户口本”，不是十个内容文件。 |
| `DELTA-03-LEDGER-OVERLAY` 十本账当前能力覆盖读 | `3f69b3b` | `RUNNABLE_READ_PATH` | 目录页能把固定户口和调用方提供的当前能力快照拼起来；没有可用内容的七本账必须显示 UNKNOWN，不能伪装 ready。 |
| `DELTA-04-CHAPTER-FACT-DRAFT-FILE` 章事实稿原型与作者可读版 | `3f69b3b` | `PROTOTYPE_FILE_ONLY` | 能把作者编排的事实句和独立写法批注按顺序做成稳定 SHA 的章事实稿原型文件，并渲染成人能读的文本。 |
| `DELTA-05-CHAPTER-FACT-HANDOVER-ACTION-FILE` 章事实稿明确交棒动作原型 | `3f69b3b` | `PROTOTYPE_FILE_ONLY` | 能记录作者明确交棒意图、标题和章事实稿 SHA，并明确标出 facts／C10／C11／plan 都没有被写。 |
| `DELTA-06-PENDING-HANDOVER-INBOX` 章事实稿 pending 请求保存 | `a376acc` | `RUNNABLE_WRITE_PATH` | 作者的章事实稿交棒请求可以写入工作区、重启读回、追加多条，并且不影响 current chapter、facts 或 plan。 |
| `DELTA-07-PENDING-HANDOVER-PREFLIGHT` pending 请求消费预演 | `aeac47a` | `PREFLIGHT_ONLY` | 能判断某条 pending 请求在当前 plan 下是否仍可消费，并返回 current 请求；所有正式写集都是 none。 |
| `DELTA-08-PENDING-AUTHOR-VIEW` pending 请求作者读回 | `9d8c667` | `RUNNABLE_READ_PATH` | 作者能重开项目后看到 pending 标题、章事实稿条目和当前状态，页面只读。 |
| `DELTA-09-CSV-INTAKE` 显式 CSV 入料 | `3f526f5` | `RUNNABLE_WRITE_PATH` | CSV 会按严格文本保留原始 bytes 和解码文本，作者明确材料身份后可进入 C10；它不会擅自解析成章节或设定表。 |
| `DELTA-10-EXCEL-GATE` Excel 安全转换门 | `3f526f5` | `PREFLIGHT_ONLY` | XLS／XLSX／XLSM 被识别为工作簿并明确阻断，提示按 sheet 转 CSV；不会把内部 XML 或压缩成员当成小说材料。 |
| `DELTA-11-PLANNING-LONGLINE-VIEW` 当前规划中的长线视图 | `66f545d`, `11acbee` | `RUNNABLE_READ_PATH` | 能从 current plan 只读展示故事线和伏笔，并把 paid／revealed 保持在“规划状态”，不冒充已发生或读者已知。 |
| `DELTA-12-CHAPTER-FACT-SUPPLY` 章事实稿规划供料 | `3f7314a` | `RUNNABLE_READ_PATH` | 能从 current plan 取出已经落位的 future events、写法提示、故事线和伏笔；未选、pending、blocked、discarded 不会混进来。 |
| `DELTA-13-M11-FACT-PLAN-BUNDLE` M11 当前事实＋未来规划材料包 | `3f7314a` | `RUNNABLE_READ_PATH` | 能把 current confirmed already-occurred facts 和 future planning 分成两个区块装包，非 confirmed facts 不会混入。 |
| `DELTA-14-M11-AUTHOR-FILE` M11 材料包作者可读文件 | `c6d90a7` | `PROTOTYPE_FILE_ONLY` | 能把已分区材料包渲染成作者可读本地文件，保留 facts／planning 身份。 |
| `DELTA-15-M7-RED-RULE` M7 红灯证据门 | `5bcc1e7` | `RUNNABLE_WRITE_PATH` | M7 保存报告时会把候选层、混合层或非 confirmed 证据降到黄灯；只有 current confirmed 的硬／高影响冲突才能红。 |
| `DELTA-16-EXTERNAL-ROUTE-PROOF` 外来章身份只读证明 | `5707ec8` | `RUNNABLE_READ_PATH` | 能证明同一外来章从 confirmed C10 到 current C11 再到 current C1，且拒绝旧 work plan 和伪造 chapter fact draft。 |
| `DELTA-17-M4-REVISION-PREFLIGHT` M4 外来章修订证据迁移预演 | `5707ec8` | `PREFLIGHT_ONLY` | 旧章改稿后，能按逐字锚判断事实证据是否唯一迁到新 revision；删除或歧义会变 needs_recheck。所有写集仍为 none。 |
| `DELTA-18-T14-UNKNOWN-OVERLAY` T14 unknown 作者裁决保存 | `6186fe0` | `BROKEN_OR_UNPROVEN` | 作者可以把自己对 unknown finding 的处置存成 overlay，原模型 unknown 不被改写，存储层的幂等、版本和隔离是好的；但当前正式结果读取和 closeout 都没有消费 overlay，所以作者动作没有进入直接使用方。 |
| `DELTA-19-FUTURE-CREATIVE-IMPORTS` 剧本／灵感／产品原生大纲导入 | `01efc50` | `BLOCKED_BY_PRODUCT_DECISION` | 01efc50 只把这些材料登记为未来缺口，没有当前入口、身份合同、保存位置或使用方。 |

### DELTA-01-LEDGER-PROTOTYPE-FILE｜十本账目录原型文件｜`PROTOTYPE_FILE_ONLY`

能生成一份固定十本账名称、顺序和说明的本地 JSON 原型；它不创建任何一本真实内容账。

- **输入**：固定目录定义和调用参数。
- **输出**：AUTHOR_LEDGER_DIRECTORY_PROTOTYPE_R01 JSON。
- **保存位置**：调用方指定的安全本地输出文件。
- **怎样接过去**：没有正式工作区下游。
- **实际使用方**：设计审查和人工查看。
- **成功主路径**：固定数据经严格校验后原子替换输出文件。
- **失败不变式**：坏输入或输出失败不破坏旧文件。
- **重启／过期**：文件可重复生成、SHA 稳定。
- **相邻兼容**：与 workspace 目录登记是两件不同能力。
- ⚠️ **仍不能宣称**：只证明文件形状，不能说十本账已经建好。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/ledger_directory_tool.py`<br>`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`<br>`02_current_route/novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_ledger_directory_tool.py`<br>`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

### DELTA-02-LEDGER-REGISTRATION｜十本账固定身份登记｜`RUNNABLE_WRITE_PATH`

作者工作区里能保存十本账的固定名称、顺序和职责目录。保存的是“户口本”，不是十个内容文件。

- **输入**：作者项目和未初始化目录。
- **输出**：ledger_directory registration。
- **保存位置**：AuthorWorkspace logical key `ledger_directory`。
- **怎样接过去**：读目录接口。
- **实际使用方**：目录页／调试读取。
- **成功主路径**：显式 initialize，一次写入；重复相同初始化幂等。
- **失败不变式**：冲突、坏目录、跨项目和路径伪造零写。
- **重启／过期**：重启可读同一 registration。
- **相邻兼容**：可叠加运行 capability snapshot。
- ⚠️ **仍不能宣称**：没有创建 character／location／item／faction／system／world_rule／longline 的内容入口。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/ledger_directory_tool.py`<br>`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`<br>`02_current_route/novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_ledger_directory_tool.py`<br>`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

### DELTA-03-LEDGER-OVERLAY｜十本账当前能力覆盖读｜`RUNNABLE_READ_PATH`

目录页能把固定户口和调用方提供的当前能力快照拼起来；没有可用内容的七本账必须显示 UNKNOWN，不能伪装 ready。

- **输入**：已登记目录和受控 capability snapshot。
- **输出**：当前目录视图。
- **保存位置**：不写 capability snapshot；只读 registration。
- **怎样接过去**：作者目录页。
- **实际使用方**：作者／审查者。
- **成功主路径**：双读目录，校验固定身份，再叠加当前状态。
- **失败不变式**：源变化、伪造 handle 或未知账状态 fail closed。
- **重启／过期**：重启读回；live snapshot 不写进 registration。
- **相邻兼容**：与目录登记相邻。
- ⚠️ **仍不能宣称**：调用方快照不是统一取件能力，也不证明账里有内容。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/ledger_directory_tool.py`<br>`02_current_route/novel-mvp/mvp/ledger_directory_workspace.py`<br>`02_current_route/novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_ledger_directory_tool.py`<br>`02_current_route/tests/test_novel_mvp_ledger_directory_workspace.py`

### DELTA-04-CHAPTER-FACT-DRAFT-FILE｜章事实稿原型与作者可读版｜`PROTOTYPE_FILE_ONLY`

能把作者编排的事实句和独立写法批注按顺序做成稳定 SHA 的章事实稿原型文件，并渲染成人能读的文本。

- **输入**：作者身份、章槽／规划快照、按序 entries、写法批注。
- **输出**：CHAPTER_FACT_DRAFT_PROTOTYPE_R01 JSON 和作者可读文本。
- **保存位置**：调用方安全输出文件；不写 AuthorWorkspace。
- **怎样接过去**：章事实稿交棒动作原型。
- **实际使用方**：人工查看和后续原型工具。
- **成功主路径**：严格验证条目顺序、身份、水印和 SHA，原子写文件。
- **失败不变式**：坏形状、篡改、输出别名或写失败不破坏旧文件。
- **重启／过期**：文件字节稳定。
- **相邻兼容**：能被 handover_tool 引用 SHA。
- ⚠️ **仍不能宣称**：它不是 C11、章节账或事实账；也没有从 M8／M11 正式生成的 owner。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_reader_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_draft_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_reader_workspace.py`

### DELTA-05-CHAPTER-FACT-HANDOVER-ACTION-FILE｜章事实稿明确交棒动作原型｜`PROTOTYPE_FILE_ONLY`

能记录作者明确交棒意图、标题和章事实稿 SHA，并明确标出 facts／C10／C11／plan 都没有被写。

- **输入**：章事实稿原型、作者明确标题和意图。
- **输出**：CHAPTER_FACT_HANDOVER_ACTION_PROTOTYPE_R01。
- **保存位置**：本地文件。
- **怎样接过去**：pending request 保存。
- **实际使用方**：pending 请求写口。
- **成功主路径**：动作只绑定整包身份，不复制事实句。
- **失败不变式**：篡改或错误 SHA 拒绝，旧输出不被破坏。
- **重启／过期**：字节稳定。
- **相邻兼容**：可与 pending workspace 配对校验。
- ⚠️ **仍不能宣称**：状态是 REQUEST_RECORDED_NOT_APPLIED，不是正式交棒。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_reader_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_draft_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_reader_workspace.py`

### DELTA-06-PENDING-HANDOVER-INBOX｜章事实稿 pending 请求保存｜`RUNNABLE_WRITE_PATH`

作者的章事实稿交棒请求可以写入工作区、重启读回、追加多条，并且不影响 current chapter、facts 或 plan。

- **输入**：有效 draft＋action 对、current plan snapshot、expected request-store version。
- **输出**：pending handover request entry。
- **保存位置**：AuthorWorkspace logical key `chapter_fact_handover_requests`。
- **怎样接过去**：pending reader 和消费预演。
- **实际使用方**：作者 pending 页／未来正式 consumer。
- **成功主路径**：两次读取 current plan，配对校验后 guarded commit。
- **失败不变式**：plan 变化、并发、坏配对、旧版本或跨项目都不写；无半份请求。
- **重启／过期**：重启 exact readback；plan 前进后请求不再 current。
- **相邻兼容**：与 pending reader、preflight 相邻。
- ⚠️ **仍不能宣称**：真实写入只到 pending inbox，没有 C11／章节账／事实账／下一章。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_reader_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_draft_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_reader_workspace.py`

### DELTA-07-PENDING-HANDOVER-PREFLIGHT｜pending 请求消费预演｜`PREFLIGHT_ONLY`

能判断某条 pending 请求在当前 plan 下是否仍可消费，并返回 current 请求；所有正式写集都是 none。

- **输入**：pending operation_id、current plan 和 request store。
- **输出**：preflight result。
- **保存位置**：不写。
- **怎样接过去**：未来正式 C11／facts／plan consumer。
- **实际使用方**：当前只有审查和 pending 页。
- **成功主路径**：双读 request store 和 plan，验证水印。
- **失败不变式**：任何源变化或过期都拒绝，不能边预演边写。
- **重启／过期**：重启可重新预演。
- **相邻兼容**：与 pending inbox 相邻。
- ⚠️ **仍不能宣称**：通过只代表“现在看起来可消费”，不代表已提交。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_reader_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_draft_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_reader_workspace.py`

### DELTA-08-PENDING-AUTHOR-VIEW｜pending 请求作者读回｜`RUNNABLE_READ_PATH`

作者能重开项目后看到 pending 标题、章事实稿条目和当前状态，页面只读。

- **输入**：pending operation_id 和当前 plan。
- **输出**：作者安全 pending view。
- **保存位置**：不写。
- **怎样接过去**：作者交棒收件箱。
- **实际使用方**：作者。
- **成功主路径**：读取 preflight 结果并验证 plan 身份。
- **失败不变式**：过期 plan、伪造页面字段、跨项目或坏 preflight 都拒绝。
- **重启／过期**：重启可读，plan 前进后停止展示为 current。
- **相邻兼容**：与 pending preflight 相邻。
- ⚠️ **仍不能宣称**：能看见 pending 不等于 pending 被消费。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_fact_draft_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_tool.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_handover_reader_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_draft_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_tool.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_handover_reader_workspace.py`

### DELTA-09-CSV-INTAKE｜显式 CSV 入料｜`RUNNABLE_WRITE_PATH`

CSV 会按严格文本保留原始 bytes 和解码文本，作者明确材料身份后可进入 C10；它不会擅自解析成章节或设定表。

- **输入**：CSV 文件名、bytes、显式 role／intent。
- **输出**：upload source、decoded text、C10 identity。
- **保存位置**：AuthorWorkspace upload_sources／intake_materials。
- **怎样接过去**：后续按材料身份读取。
- **实际使用方**：M1 作者入料页。
- **成功主路径**：严格解码并保留原始 bytes。
- **失败不变式**：解码失败或同批 Excel 阻断时整批不改变项目。
- **重启／过期**：可重启读回 SHA。
- **相邻兼容**：与 C10 相邻。
- ⚠️ **仍不能宣称**：“CSV 能进来”不等于读懂列、sheet 或自动分流。
- **专项归属**：多形态导入专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/input_router.py`<br>`02_current_route/novel-mvp/mvp/upload_source.py`<br>`02_current_route/novel-mvp/mvp/ingest_workspace.py`<br>`02_current_route/novel-mvp/mvp/intake_identity.py`<br>`02_current_route/novel-mvp/mvp/admission.py`<br>`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`<br>`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`<br>`02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py`<br>`02_current_route/tests/test_novel_mvp_c10_first_entrypoints.py`<br>`02_current_route/tests/test_novel_mvp_ingest_workspace.py`<br>`02_current_route/tests/test_novel_mvp_upload_source.py`

### DELTA-10-EXCEL-GATE｜Excel 安全转换门｜`PREFLIGHT_ONLY`

XLS／XLSX／XLSM 被识别为工作簿并明确阻断，提示按 sheet 转 CSV；不会把内部 XML 或压缩成员当成小说材料。

- **输入**：Excel 工作簿 bytes。
- **输出**：blocking receipt 和转换说明。
- **保存位置**：正式项目状态不变。
- **怎样接过去**：作者手动转换后重新入料。
- **实际使用方**：M1 作者入料页。
- **成功主路径**：识别扩展名／工作簿身份，生成单个阻断。
- **失败不变式**：与其他文件同批时不得留下半批写入。
- **重启／过期**：不适用。
- **相邻兼容**：转换后回到 CSV 入口。
- ⚠️ **仍不能宣称**：这不是 Excel 支持；没有读取 sheet 内容。
- **专项归属**：多形态导入专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/input_router.py`<br>`02_current_route/novel-mvp/mvp/upload_source.py`<br>`02_current_route/novel-mvp/mvp/ingest_workspace.py`<br>`02_current_route/novel-mvp/mvp/intake_identity.py`<br>`02_current_route/novel-mvp/mvp/admission.py`<br>`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`<br>`02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`<br>`02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py`<br>`02_current_route/tests/test_novel_mvp_c10_first_entrypoints.py`<br>`02_current_route/tests/test_novel_mvp_ingest_workspace.py`<br>`02_current_route/tests/test_novel_mvp_upload_source.py`

### DELTA-11-PLANNING-LONGLINE-VIEW｜当前规划中的长线视图｜`RUNNABLE_READ_PATH`

能从 current plan 只读展示故事线和伏笔，并把 paid／revealed 保持在“规划状态”，不冒充已发生或读者已知。

- **输入**：current plan。
- **输出**：PLANNING_NOT_FACT 的长线作者视图。
- **保存位置**：不写。
- **怎样接过去**：作者长线只读页、章事实稿供料。
- **实际使用方**：M8／作者。
- **成功主路径**：双读 current plan，按 plan 顺序编译。
- **失败不变式**：源变化、坏 plan、跨项目都拒绝。
- **重启／过期**：重启字节稳定；plan 变化后旧视图自然失效。
- **相邻兼容**：与 planstore 相邻。
- ⚠️ **仍不能宣称**：只覆盖 plan 里的 storylines／hooks。卷纲、人物命运、灵感和预计时机明确显示 unavailable，不是十本账里的完整长线账。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/planning_longline_view_tool.py`<br>`02_current_route/novel-mvp/mvp/planning_longline_view_workspace.py`<br>`02_current_route/novel-mvp/mvp/planning_longline_reader_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_planning_longline_view_tool.py`<br>`02_current_route/tests/test_novel_mvp_planning_longline_view_workspace.py`<br>`02_current_route/tests/test_novel_mvp_planning_longline_reader_workspace.py`

### DELTA-12-CHAPTER-FACT-SUPPLY｜章事实稿规划供料｜`RUNNABLE_READ_PATH`

能从 current plan 取出已经落位的 future events、写法提示、故事线和伏笔；未选、pending、blocked、discarded 不会混进来。

- **输入**：current plan／chapter slot。
- **输出**：短命 planning supply。
- **保存位置**：不写。
- **怎样接过去**：章事实稿或材料包编译器。
- **实际使用方**：M11／章事实稿原型。
- **成功主路径**：双读 plan，按落位顺序过滤。
- **失败不变式**：源变化、坏槽位、缺 checkpoint 或非法落位记录拒绝。
- **重启／过期**：同源可复现。
- **相邻兼容**：与 material bundle 相邻。
- ⚠️ **仍不能宣称**：只取规划账局部内容，不是 M8 全文选择卡历史，也不是十本账统一取件。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/plan_tool.py`<br>`02_current_route/novel-mvp/mvp/plan_workspace.py`<br>`02_current_route/novel-mvp/mvp/planstore.py`<br>`02_current_route/novel-mvp/mvp/plan_selection_target_tool.py`<br>`02_current_route/novel-mvp/contracts/C7_PLOT_LAYER.md`<br>`02_current_route/novel-mvp/contracts/C7_SELECTION_ACTION.md`<br>`02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md`<br>`02_current_route/novel-mvp/mvp/chapter_fact_supply_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_supply_workspace.py`

### DELTA-13-M11-FACT-PLAN-BUNDLE｜M11 当前事实＋未来规划材料包｜`RUNNABLE_READ_PATH`

能把 current confirmed already-occurred facts 和 future planning 分成两个区块装包，非 confirmed facts 不会混入。

- **输入**：M11 current fact pack、planning supply、源水印。
- **输出**：in-memory chapter fact material bundle。
- **保存位置**：不写真值；调用返回短命对象。
- **怎样接过去**：章事实稿／章事实稿检查调用方。
- **实际使用方**：当前只在模块和测试层使用。
- **成功主路径**：读取 facts 与 plan，最终再次验证两个源没有变化。
- **失败不变式**：任何一侧非 READY、源变化、篡改或跨项目都不返回半包。
- **重启／过期**：同源可重建，源变化失效。
- **相邻兼容**：与 packer_fact、chapter_fact_supply 相邻。
- ⚠️ **仍不能宣称**：只有事实账＋规划账，不是十本账全量材料包；也不是正式 C9。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/packer_tool.py`<br>`02_current_route/novel-mvp/mvp/packer_workspace.py`<br>`02_current_route/novel-mvp/mvp/packer_fact_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_material_bundle_workspace.py`<br>`02_current_route/novel-mvp/mvp/chapter_fact_supply_workspace.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_recall_handle_workspace.py`<br>`02_current_route/tests/test_novel_mvp_packer_fact_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_material_bundle_workspace.py`<br>`02_current_route/tests/test_novel_mvp_chapter_fact_supply_workspace.py`

### DELTA-14-M11-AUTHOR-FILE｜M11 材料包作者可读文件｜`PROTOTYPE_FILE_ONLY`

能把已分区材料包渲染成作者可读本地文件，保留 facts／planning 身份。

- **输入**：已生成的材料包对象。
- **输出**：CHAPTER_FACT_MATERIAL_BUNDLE_PROTOTYPE 文件／文本。
- **保存位置**：本地安全输出文件。
- **怎样接过去**：人工阅读。
- **实际使用方**：作者／审查者。
- **成功主路径**：严格验证 bundle 和 SHA 后确定性渲染。
- **失败不变式**：篡改或写失败不破坏旧文件。
- **重启／过期**：字节稳定。
- **相邻兼容**：可读取 DELTA-13 输出。
- ⚠️ **仍不能宣称**：文件打开时不会自动重验 facts／plan current；不是新的真源或长期 M11 工件。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/chapter_fact_material_bundle_tool.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_chapter_fact_material_bundle_tool.py`

### DELTA-15-M7-RED-RULE｜M7 红灯证据门｜`RUNNABLE_WRITE_PATH`

M7 保存报告时会把候选层、混合层或非 confirmed 证据降到黄灯；只有 current confirmed 的硬／高影响冲突才能红。

- **输入**：provider findings、current fact layer。
- **输出**：受本地规则重算 severity 的 C6 report。
- **保存位置**：health_report 投影。
- **怎样接过去**：作者体检页。
- **实际使用方**：作者。
- **成功主路径**：provider 输出进入本地 `_expected_severity` 重算。
- **失败不变式**：provider 伪报红灯不能越过本地证据门。
- **重启／过期**：报告可重启、判 stale。
- **相邻兼容**：与 M4 facts 相邻。
- ⚠️ **仍不能宣称**：证明的是灯色权限，不是冲突发现率或完整优化方案。
- **代码／合同**：`02_current_route/novel-mvp/mvp/check_tool.py`<br>`02_current_route/novel-mvp/mvp/check_workspace.py`<br>`02_current_route/novel-mvp/mvp/check_reader_workspace.py`<br>`02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_check_workspace.py`

### DELTA-16-EXTERNAL-ROUTE-PROOF｜外来章身份只读证明｜`RUNNABLE_READ_PATH`

能证明同一外来章从 confirmed C10 到 current C11 再到 current C1，且拒绝旧 work plan 和伪造 chapter fact draft。

- **输入**：C10／C11／C1 三份对象。
- **输出**：external route proof。
- **保存位置**：不写。
- **怎样接过去**：M4 修订迁移预演。
- **实际使用方**：fact_revision_preflight_tool。
- **成功主路径**：逐层核对 source span、revision、SHA 和 current 指针。
- **失败不变式**：任一漂移或调用方自报身份都不被信任。
- **重启／过期**：对当前对象即时证明。
- **相邻兼容**：与 M4 revision preflight 相邻。
- ⚠️ **仍不能宣称**：M2 入口没有强制调用它，所以它不能单独解决双车道切流。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_external_chapter_route_tool.py`

### DELTA-17-M4-REVISION-PREFLIGHT｜M4 外来章修订证据迁移预演｜`PREFLIGHT_ONLY`

旧章改稿后，能按逐字锚判断事实证据是否唯一迁到新 revision；删除或歧义会变 needs_recheck。所有写集仍为 none。

- **输入**：机械证明的外来章 route、旧 facts、新章文本。
- **输出**：migration preflight：preserve／move／needs_recheck。
- **保存位置**：本地输出文件或返回对象，不写 facts／C11／C1。
- **怎样接过去**：未来正式 facts revision consumer。
- **实际使用方**：当前只供审查。
- **成功主路径**：整批验证、逐字匹配、唯一性判断。
- **失败不变式**：一条坏事实整批拒绝；歧义不猜。
- **重启／过期**：可重跑；不是长期状态。
- **相邻兼容**：与 external route proof 相邻。
- ⚠️ **仍不能宣称**：没有正式提交、锚迁移历史和下游 stale 传播。
- **专项归属**：双车道与十本账专项窗口
- **代码／合同**：`02_current_route/novel-mvp/mvp/fact_revision_preflight_tool.py`<br>`02_current_route/novel-mvp/mvp/external_chapter_route_tool.py`
- **直接测试**：`02_current_route/tests/test_novel_mvp_fact_revision_preflight_tool.py`

### DELTA-18-T14-UNKNOWN-OVERLAY｜T14 unknown 作者裁决保存｜`BROKEN_OR_UNPROVEN`

作者可以把自己对 unknown finding 的处置存成 overlay，原模型 unknown 不被改写，存储层的幂等、版本和隔离是好的；但当前正式结果读取和 closeout 都没有消费 overlay，所以作者动作没有进入直接使用方。

- **输入**：completed writing check result、unknown finding、作者 self-reported action、current draft／slot。
- **输出**：unknown overlay receipt。
- **保存位置**：AuthorWorkspace writing_check_results 条目内。
- **怎样接过去**：目标应是作者结果页和 closeout；当前没有接上。
- **实际使用方**：目前只有 overlay 自己的读回测试。
- **成功主路径**：验证 parent result、finding、draft／slot current 后 guarded commit。
- **失败不变式**：stale、第二次不同裁决、跨项目和并发都零写。
- **重启／过期**：可重启读回 overlay。
- **相邻兼容**：与 writing_check_result_workspace 的存储相邻，但 `resolve_writing_check_result` 返回值剥掉 overlays；closeout 只看原 result。
- ⚠️ **仍不能宣称**：机械保存不能写成“作者裁决已经生效”。
- **代码／合同**：`02_current_route/novel-mvp/mvp/writing_check_unknown_adjudication_workspace.py`<br>`02_current_route/novel-mvp/mvp/writing_check_result_workspace.py`<br>`02_current_route/novel-mvp/mvp/writing_closeout_workspace.py`<br>`02_current_route/novel-mvp/contracts/WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION.md`
- **直接测试**：`02_current_route/tests/test_novel_mvp_writing_check_unknown_adjudication_workspace.py`<br>`02_current_route/tests/test_novel_mvp_writing_closeout_workspace.py`

### DELTA-19-FUTURE-CREATIVE-IMPORTS｜剧本／灵感／产品原生大纲导入｜`BLOCKED_BY_PRODUCT_DECISION`

01efc50 只把这些材料登记为未来缺口，没有当前入口、身份合同、保存位置或使用方。

- **输入**：剧本、灵感、产品原生大纲等未来材料。
- **输出**：尚未定义。
- **保存位置**：尚未定义。
- **怎样接过去**：尚未定义。
- **实际使用方**：尚未定义。
- **成功主路径**：无当前成功路径。
- **失败不变式**：贸然接入会把安排、定义、变化混账。
- **重启／过期**：不适用。
- **相邻兼容**：不适用。
- ⚠️ **仍不能宣称**：需先决定每种材料进哪本账、何时只是候选、谁能确认。
- **专项归属**：多形态导入专项窗口
- **代码／合同**：`02_current_route/novel-mvp/ARCHITECTURE.md`
- **直接测试**：无。

## 5. 重点复核结果

### 双车道到底分开没有

**分开了一小段，但还没有形成正式分流。** 新路径已经有章事实稿原型、明确交棒动作、pending 保存、pending 预演和作者读回，这一段不会写 C10／C11／C1／facts／plan。可问题也在这里：它停在 pending。

旧路径 `chapter_initial_admission_workspace` 则是完整可运行写路径：work draft → C10 → C11 → C1，重开后直接交 M2。`segment_workspace` 不识别 lane，`external_chapter_route_tool` 也没有成为 M2 的强制入口门。

所以当前准确说法是：

- 新自产道**开始有自己的原型和 pending 收件箱**；
- 正式 current chapter／fact admission 尚未接；
- 旧自产 work draft 仍能走回抽取链；
- `AE-X-N01`、`AE-X-N02` 不是普通“未完成”，而是 **当前运行路径和目标直接打架**。

### 章事实稿、交棒、pending、作者读回

| 环节 | 当前做到哪 | 不能写成什么 |
|---|---|---|
| 章事实稿 | 稳定 SHA 的本地原型＋作者可读文本 | 正式工作区 current 章事实稿 |
| 明确交棒动作 | 本地 action 原型，绑定整包 SHA 和标题 | C11／章节账提交 |
| pending 保存 | 真实 AuthorWorkspace 写路径，重启、幂等、并发保护齐全 | 已消费／已入事实账 |
| pending 预演 | current plan 下的只读消费检查 | 正式提交 |
| 作者读回 | current pending 页面可读、零写 | 章已经完成交棒 |

### 十本账

当前有两件真能力：固定十个名字能写进 `ledger_directory`；目录能叠加当前能力快照并把不可用账诚实标 `UNKNOWN`。

当前没有的东西也很明确：目录初始化不会建 concrete ledgers；七本账在直接测试里被要求保持 unavailable。能复用的内容 owner 主要是章节、事实、规划，长线只有 plan 中 storylines/hooks 的只读切片。统一“按账取件”、轻文件升精装和接口不变都没完成。

### M4、M7、M8、M11、T14

- **M4 外来章修订**：证据迁移规则能预演；不会猜歧义；但没有正式 facts 提交和下游过期传播。
- **M7 灯色**：confirmed 硬冲突才能红，候选／混合层不能红；报告能保存、重启、判旧。缺的是完整两路修法。
- **M8 长线视图**：只读 current plan 的故事线和伏笔；paid／revealed 保持 planning 身份。卷纲、人物命运、灵感与预计时机仍 unavailable。
- **M11 材料包**：current confirmed facts 和 future planning 分区、硬预算、遗漏回取可跑；不是十本账统一取件，也不是正式 C9。
- **T14 unknown**：作者 overlay 能安全保存；正式 reader 和 closeout 没消费，所以当前属于 `BROKEN_OR_UNPROVEN`，不是“作者裁决已生效”。

## 6. 作者现在最早会卡住的断点

| 排名 | 断点 | 当前直接证据 | 归属 |
|---:|---|---|---|
| 1 | `GAP-SELF-01` 章事实稿没有正式 producer／contract／workspace owner | chapter_fact_draft_tool.py 明确使用 PROTOTYPE_R01 身份并只写本地文件。；R14 背景本身也把正式章事实稿合同列为未完成。 | 双车道与十本账专项窗口 |
| 2 | `GAP-SELF-02` 明确交棒停在 pending，C11／章节账／事实账／下一章都没发生 | chapter_fact_handover_workspace.py 顶部和返回结构都明确 no C10／C11／C1／facts／plan。；直接测试只证明 pending 保存、重启和零副作用。 | 双车道与十本账专项窗口 |
| 3 | `GAP-SELF-03` 旧 work draft 路径仍把产品自产内容送回 M2 | test_initial_handover_commits_c10_c11_c1_and_restarts_into_m2 直接通过。；segment_workspace 只认 current C1，不分外来／自产。 | 双车道与十本账专项窗口 |
| 4 | `GAP-SELF-04` 自产章进入事实账的确认粒度未冻结 | R14 明确把这一点写成开放口。；当前 pending consumer 不写 facts。 | 双车道与十本账专项窗口 |
| 5 | `GAP-LEDGER-01` 十本账只有固定目录，七本内容能力仍是 UNKNOWN | ledger_directory_workspace.py 明确只持久化 identity/order，不创建 concrete ledgers。；直接测试要求七本 unavailable 必须保持 UNKNOWN。 | 双车道与十本账专项窗口 |
| 6 | `GAP-M8-01` M8 长线页只读 plan 中的故事线／伏笔，不是完整长线账 | planning_longline_view_tool.py 的 UNAVAILABLE 常量。；R14 当前缺口表。 | 双车道与十本账专项窗口 |
| 7 | `GAP-T14-01` unknown 作者裁决能保存，但页面与 closeout 不使用 | writing_check_result_workspace.resolve_writing_check_result 不返回 unknown_overlays。；writing_closeout_workspace 只校验 parent result status。 | 本窗口可拆窄卡 |
| 8 | `GAP-M7-01` M7 有安全灯色和可保存报告，但没有完整两路修法 | check_tool／check_workspace 只覆盖 finding/report。；ARCHITECTURE.md 把 full optimizer 列为当前缺口。 | 本窗口可拆窄卡 |
| 9 | `GAP-M9-01` M9 有概览切片，没有完整可靠驾驶舱／项目首屏 | overview_* 只覆盖局部投影。；R14 把 M9 定位为只读驾驶舱，当前缺口仍列 M9 指标。 | 本窗口可拆窄卡 |
| 10 | `GAP-IMPORT-01` CSV 只保留文本，Excel／未来创作材料仍未真正读懂 | input_router.py 的 CSV strict text 和 Excel blocking receipt。；01efc50 只有 docs 提交。 | 多形态导入专项窗口 |

### GAP-SELF-01｜章事实稿没有正式 producer／contract／workspace owner

- **作者会遇到什么**：作者完成下一章规划后，当前系统只能手工或工具生成原型文件；没有正式工作区对象把 M8／M11 材料编译成可持续编辑的章事实稿。
- **证明它在 01efc50 仍存在**：chapter_fact_draft_tool.py 明确使用 PROTOTYPE_R01 身份并只写本地文件。；R14 背景本身也把正式章事实稿合同列为未完成。
- **结果**：作者不能在产品内稳定保存、继续编辑并交棒自产章核心工件。
- **处理位置**：双车道与十本账专项窗口

### GAP-SELF-02｜明确交棒停在 pending，C11／章节账／事实账／下一章都没发生

- **作者会遇到什么**：点击明确交棒后，当前最远只写 `chapter_fact_handover_requests`；preflight 的 effects 全是 none。
- **证明它在 01efc50 仍存在**：chapter_fact_handover_workspace.py 顶部和返回结构都明确 no C10／C11／C1／facts／plan。；直接测试只证明 pending 保存、重启和零副作用。
- **结果**：作者看得到请求，却不能把当前章登记成 current，也不能用它继续规划下一章。
- **处理位置**：双车道与十本账专项窗口

### GAP-SELF-03｜旧 work draft 路径仍把产品自产内容送回 M2

- **作者会遇到什么**：旧 INITIAL handover 会写 C10→C11→C1，重启后直接调用 M2。C1 没有 lane marker，M2 也不验证 external route proof。
- **证明它在 01efc50 仍存在**：test_initial_handover_commits_c10_c11_c1_and_restarts_into_m2 直接通过。；segment_workspace 只认 current C1，不分外来／自产。
- **结果**：双车道只在新原型边缘分开，旧可运行主路仍违反 R14 的自产章零 M2／M3。
- **处理位置**：双车道与十本账专项窗口

### GAP-SELF-04｜自产章进入事实账的确认粒度未冻结

- **作者会遇到什么**：交棒绑定整包身份，但逐条还是整包确认、低影响默认与高影响单签怎样组合没有正式规则。
- **证明它在 01efc50 仍存在**：R14 明确把这一点写成开放口。；当前 pending consumer 不写 facts。
- **结果**：开发继续接线会替 CZ 决定作者确认权。
- **处理位置**：双车道与十本账专项窗口

### GAP-LEDGER-01｜十本账只有固定目录，七本内容能力仍是 UNKNOWN

- **作者会遇到什么**：目录可以显示十个名字，但 character、location、item、faction、system、world_rule、longline 没有统一内容入口；只有 chapters、facts、plan 有较可复用的当前存储。
- **证明它在 01efc50 仍存在**：ledger_directory_workspace.py 明确只持久化 identity/order，不创建 concrete ledgers。；直接测试要求七本 unavailable 必须保持 UNKNOWN。
- **结果**：M8、M9、M10、M11 无法从同一目录取全量当前材料。
- **处理位置**：双车道与十本账专项窗口

### GAP-M8-01｜M8 长线页只读 plan 中的故事线／伏笔，不是完整长线账

- **作者会遇到什么**：卷纲、人物命运、灵感与预计使用时机在当前视图中明确 unavailable；选择卡全文和正式 current selection 也未形成完整作者路径。
- **证明它在 01efc50 仍存在**：planning_longline_view_tool.py 的 UNAVAILABLE 常量。；R14 当前缺口表。
- **结果**：作者无法把跨章方向完整保存并可靠供给下一章。
- **处理位置**：双车道与十本账专项窗口

### GAP-T14-01｜unknown 作者裁决能保存，但页面与 closeout 不使用

- **作者会遇到什么**：作者对 unknown 做了处置后，重开可以从底层读到 overlay；正式 result resolver 和 closeout 仍只看原始 unknown。
- **证明它在 01efc50 仍存在**：writing_check_result_workspace.resolve_writing_check_result 不返回 unknown_overlays。；writing_closeout_workspace 只校验 parent result status。
- **结果**：作者动作像“保存了但没生效”，会卡在收工判断。
- **处理位置**：本报告任务卡

### GAP-M7-01｜M7 有安全灯色和可保存报告，但没有完整两路修法

- **作者会遇到什么**：作者能看到 finding，却拿不到 R14 要求的定位、原因、最小回改、后文圆回、触碰范围和代价。
- **证明它在 01efc50 仍存在**：check_tool／check_workspace 只覆盖 finding/report。；ARCHITECTURE.md 把 full optimizer 列为当前缺口。
- **结果**：体检能报错，不能直接帮作者做下一步决定。
- **处理位置**：本报告任务卡

### GAP-M9-01｜M9 有概览切片，没有完整可靠驾驶舱／项目首屏

- **作者会遇到什么**：已有概要和过期机制，但“梗概＋概览＋战报”、卷级缩放、人物／阵营／故事线／抉择／钩子指标没有同一条直接代码证据。
- **证明它在 01efc50 仍存在**：overview_* 只覆盖局部投影。；R14 把 M9 定位为只读驾驶舱，当前缺口仍列 M9 指标。
- **结果**：作者重开项目后仍不能只靠一个可信页面看清写到哪、哪里卡、接下来做什么。
- **处理位置**：本报告任务卡

### GAP-IMPORT-01｜CSV 只保留文本，Excel／未来创作材料仍未真正读懂

- **作者会遇到什么**：CSV 可以进 C10，但列语义不解析；Excel 只阻断；剧本／灵感／产品原生大纲只有文档登记。
- **证明它在 01efc50 仍存在**：input_router.py 的 CSV strict text 和 Excel blocking receipt。；01efc50 只有 docs 提交。
- **结果**：作者必须手工转换和指定身份，不能把多形态材料直接变成对应账内容。
- **处理位置**：多形态导入专项窗口

## 7. R03 142 条：直接证据、局部证据、背景目标与当前冲突

| 证据档 | 数量 | 含义 |
|---|---:|---|
| `DIRECT_CODE_EVIDENCE` | 61 | 当前代码和直接测试覆盖这条需求的机械核心。这里不把机械通过扩大成真实小说内容质量通过。 |
| `PARTIAL_DIRECT_CODE_EVIDENCE` | 43 | 当前已有一个或多个直接切片，但需求中的作者结果、语义质量、统一入口或完整下游还缺。 |
| `BACKGROUND_TARGET_ONLY` | 36 | R14／R03 对目标说得清楚，但当前代码和直接测试没有覆盖核心用户结果。 |
| `CURRENT_CODE_CONTRADICTS_TARGET` | 2 | 当前存在可运行路径与这条 R14 目标直接冲突；不是简单“还没做”。 |

🔥 这里的“直接证据”只认当前代码和直接测试的机械核心。真实小说内容质量、模型判断和作者体验没有因为一条 pytest 变成已证明。

### 分组统计

| 归组 | 直接 | 局部 | 仅背景 | 当前冲突 | 合计 |
|---|---:|---:|---:|---:|---:|
| M1 | 5 | 4 | 2 | 0 | 11 |
| M2 | 7 | 2 | 0 | 0 | 9 |
| M3 | 4 | 3 | 5 | 0 | 12 |
| M4 | 5 | 2 | 3 | 0 | 10 |
| M5 | 4 | 4 | 1 | 0 | 9 |
| M6 | 7 | 1 | 1 | 0 | 9 |
| M7 | 5 | 3 | 2 | 0 | 10 |
| M8 | 0 | 6 | 9 | 0 | 15 |
| M9 | 5 | 2 | 4 | 0 | 11 |
| M10 | 6 | 3 | 2 | 0 | 11 |
| M11 | 4 | 4 | 2 | 0 | 10 |
| 作者工作区 | 7 | 3 | 3 | 0 | 13 |
| 跨模块 | 2 | 6 | 2 | 2 | 12 |

### M1

- **`DIRECT_CODE_EVIDENCE`**：`M1-E01`、`M1-E04`、`M1-E05`、`M1-E06`、`M1-N01`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M1-B02`、`M1-B03`、`M1-E02`、`M1-E03`
- **`BACKGROUND_TARGET_ONLY`**：`M1-B01`、`M1-N02`

### M2

- **`DIRECT_CODE_EVIDENCE`**：`M2-B02`、`M2-E01`、`M2-E02`、`M2-E03`、`M2-E04`、`M2-E05`、`M2-E06`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M2-B01`、`M2-B03`

### M3

- **`DIRECT_CODE_EVIDENCE`**：`M3-E01`、`M3-E03`、`M3-E04`、`M3-E06`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M3-E02`、`M3-E05`、`M3-N03`
- **`BACKGROUND_TARGET_ONLY`**：`M3-B01`、`M3-B02`、`M3-B03`、`M3-N01`、`M3-N02`

### M4

- **`DIRECT_CODE_EVIDENCE`**：`M4-C01`、`M4-C02`、`M4-C03`、`M4-C05`、`M4-C06`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M4-B03`、`M4-C04`
- **`BACKGROUND_TARGET_ONLY`**：`M4-B01`、`M4-B02`、`M4-N01`

### M5

- **`DIRECT_CODE_EVIDENCE`**：`M5-C01`、`M5-C02`、`M5-C03`、`M5-C06`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M5-B01`、`M5-B02`、`M5-C04`、`M5-C05`
- **`BACKGROUND_TARGET_ONLY`**：`M5-B03`

### M6

- **`DIRECT_CODE_EVIDENCE`**：`M6-B01`、`M6-B02`、`M6-C01`、`M6-C02`、`M6-C03`、`M6-C04`、`M6-C05`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M6-B03`
- **`BACKGROUND_TARGET_ONLY`**：`M6-C06`

### M7

- **`DIRECT_CODE_EVIDENCE`**：`M7-E01`、`M7-E04`、`M7-E05`、`M7-E06`、`M7-E07`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M7-E02`、`M7-E03`、`M7-E08`
- **`BACKGROUND_TARGET_ONLY`**：`M7-E09`、`M7-N01`

### M8

- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M8-E01`、`M8-E02`、`M8-E07`、`M8-E09`、`M8-N05`、`M8-N06`
- **`BACKGROUND_TARGET_ONLY`**：`M8-E03`、`M8-E04`、`M8-E05`、`M8-E06`、`M8-E08`、`M8-N01`、`M8-N02`、`M8-N03`、`M8-N04`

### M9

- **`DIRECT_CODE_EVIDENCE`**：`M9-E01`、`M9-E02`、`M9-E03`、`M9-E04`、`M9-E07`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`M9-E06`、`M9-E09`
- **`BACKGROUND_TARGET_ONLY`**：`M9-E05`、`M9-E08`、`M9-N01`、`M9-N02`

### M10

- **`DIRECT_CODE_EVIDENCE`**：`AE-M10-B01`、`AE-M10-B02`、`AE-M10-C01`、`AE-M10-C03`、`AE-M10-C05`、`AE-M10-C06`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`AE-M10-B03`、`AE-M10-C02`、`AE-M10-C04`
- **`BACKGROUND_TARGET_ONLY`**：`AE-M10-N01`、`AE-M10-N02`

### M11

- **`DIRECT_CODE_EVIDENCE`**：`AE-M11-C02`、`AE-M11-C03`、`AE-M11-C04`、`AE-M11-C05`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`AE-M11-B02`、`AE-M11-C01`、`AE-M11-C06`、`AE-M11-N01`
- **`BACKGROUND_TARGET_ONLY`**：`AE-M11-B01`、`AE-M11-B03`

### 作者工作区

- **`DIRECT_CODE_EVIDENCE`**：`AE-AW-B02`、`AE-AW-C01`、`AE-AW-C02`、`AE-AW-C03`、`AE-AW-C04`、`AE-AW-C05`、`AE-AW-C06`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`AE-AW-B01`、`AE-AW-B03`、`AE-AW-N01`
- **`BACKGROUND_TARGET_ONLY`**：`AE-AW-N02`、`AE-AW-N03`、`AE-AW-N04`

### 跨模块

- **`DIRECT_CODE_EVIDENCE`**：`AE-X-C02`、`AE-X-C05`
- **`PARTIAL_DIRECT_CODE_EVIDENCE`**：`AE-X-B02`、`AE-X-C01`、`AE-X-C03`、`AE-X-C04`、`AE-X-C06`、`AE-X-N03`
- **`BACKGROUND_TARGET_ONLY`**：`AE-X-B01`、`AE-X-B03`
- **`CURRENT_CODE_CONTRADICTS_TARGET`**：`AE-X-N01`、`AE-X-N02`

逐条需求原文、状态、代码路径、测试路径和具体限制全部保存在同包 JSON 的 `atomic_expectations` 数组，142 条恰好一条一记录。

## 8. 测试与证据完整性

- 包内当前基线：排除两份依赖未版本化 TEMP 夹具的旧测试后，**1542 passed in 48.41s**；Ruff 通过。
- 两份不可复跑旧测试：`test_novel_mvp_m3_admission.py`、`test_novel_mvp_chapterization.py`。这是夹具缺件，不是断言失败。
- 本次外审另跑 31 个明确 test node，参数化后 **40 passed in 8.72s**，覆盖章事实稿、pending、十本账目录、长线读、M11 bundle、M7、M4 预演、T14 overlay、旧 work draft→M2 和 M2 持久化。
- 本次容器只有 Python 3.13.5；项目锁定环境是 Python 3.12.12。因此 40 项只作补充烟测，1542 项包内基线仍是主证据。
- 新发现的外审包可移植性缺口：包里有 `test_novel_mvp_c10_first_entrypoints.py`，却没有它 import 的 `novel-mvp/cli.py`。这应交 R03 测试补齐专项处理，不能冒充产品运行失败。

❌ 不允许从这些数字推出：真实小说语义质量好、作者体验好、全链完成、模型可生产。

## 9. 不与三个专项窗口重叠的任务卡

本报告只开 4 张。没有凑第 5 张，因为剩余最高优先级断点都属于“双车道与十本账、R03 测试补齐、多形态导入”。

### TASK-RUNTIME-R01-T14-UNKNOWN-CONSUMER｜让 T14 unknown 作者裁决真正进入作者读页与收工判断

- **唯一用户问题**：作者已经对 unknown finding 作出明确处置，但当前页面和 closeout 仍像没处理过。
- **输入**：
  - current WRITING_DESK_CHECK_RESULT（保留原模型 unknown）
  - 同一 result 内已保存的 unknown_overlays
  - current work draft 和 chapter slot 水印
- **输出**：
  - 作者可读 resolved view：并列显示“模型=unknown”和“作者处置=…”，不能把二者合成模型已确定
  - closeout preflight 对 overlay 的消费结果和明确阻断原因
- **保存位置**：不新开真值；继续读取现有 `writing_check_results`，必要的派生页只作可重建投影。
- **实际使用方**：章事实稿检查／历史 T14 作者结果页；writing_closeout_workspace
- **建议最小写集**：
  - novel-mvp/mvp/writing_check_result_workspace.py 的作者安全 resolver
  - novel-mvp/mvp/writing_check_change_reader.py 或对应作者 reader
  - novel-mvp/mvp/writing_closeout_workspace.py
  - 对应直接测试与最小合同说明
- **禁改范围**：
  - 不得修改原始 model finding 或把 unknown 改成模型 covered／missing
  - 不得写 facts、plan、C10、C11、C1
  - 不得顺手重做双车道、十本账或章事实稿正式合同
- 💡 **正常例**：模型因证据不足报 unknown；作者选择“我确认这项已交代”。结果页同时显示两层身份，closeout 按已冻结规则决定是否放行。
- ⚠️ **危险反例**：
  - 作者裁决后又改了 work draft：旧 overlay 必须 stale，不能继续放行。
  - 另一个作者／项目伪造 result_id：必须零泄漏、零写入。
- **最小测试**：
  - overlay 被作者 reader 消费且原 finding 仍为 unknown
  - closeout 对每个冻结 disposition 给出确定结果
  - stale draft／slot 拒绝
  - 重复同动作幂等、不同动作冲突
  - 跨作者／路径伪造零泄漏
- **停下问 CZ 的条件**：如果“作者说 covered／missing／mismatch”分别是否解除 closeout 阻断还没有正式拍板，只接作者读页；closeout 消费停下问 CZ，不能用默认值。
- **做完仍不能宣称**：不能宣称章事实稿检查全链完成，也不能宣称作者裁决等于事实确认。
- **与专项窗口关系**：无；只消费现有 T14 overlay。

### TASK-RUNTIME-R01-M7-OPTIMIZER｜把 M7 finding 补成作者可决定的两路修法报告

- **唯一用户问题**：作者知道哪里可能有问题，却不知道应该回改旧章，还是保留旧章用后文圆回来。
- **输入**：
  - current C6 finding 和其证据范围
  - current confirmed facts／world rules／chapter index
  - 作者选中的问题范围和可选“这是故意的”豁免
- **输出**：
  - 问题位置与证据
  - 原因说明
  - 最小回改方案：要动哪些旧位置、代价和风险
  - 后文圆回方案：要新增哪些未来安排、代价和风险
  - 材料不足时明确停止，不硬给两条假方案
- **保存位置**：建议新增窄投影 `m7_optimization_reports`，引用 C6 report/version/SHA；不写书稿或真值。
- **实际使用方**：M7 优化工作台作者页；后续“采纳为提案”动作，而不是自动执行
- **建议最小写集**：
  - M7 optimizer 纯编译模块
  - 窄 workspace 保存／读回／stale 处理
  - 作者 reader
  - 直接测试
- **禁改范围**：
  - 不得自动改书稿、facts、plan、C11
  - 不得生成成文段落
  - 不得把推断型问题升红灯
  - 不得引入全局工单平台或事件总线
- 💡 **正常例**：confirmed facts 显示人物第 20 章死亡、第 50 章同本人再次出现。报告给“回改死亡表述”与“后文揭示假死”两路，并列出各自触碰范围。
- ⚠️ **危险反例**：
  - 证据只来自 extracted candidate：不能给确定修法，更不能红灯；应写待复核。
  - 后文圆回会新增人物复活或秘密替身等高影响 Canon：只能形成待作者签字提案。
- **最小测试**：
  - confirmed hard conflict 生成两路且都引用证据
  - candidate／mixed 证据不生成确定性修法
  - 材料不足返回 stop
  - 报告保存、重启、源变化 stale
  - 零 facts／plan／prose writes
- **停下问 CZ 的条件**：如果某类“后文圆回”是否允许自动形成 plan candidate、还是只能停在报告层没有正式规则，保持报告层并问 CZ。
- **做完仍不能宣称**：不能宣称系统已经修稿、已经解决冲突或真实小说修法质量已验证。
- **与专项窗口关系**：无；不改双车道、账本 owner、R03 测试设计或导入。

### TASK-RUNTIME-R01-M9-DASHBOARD-PROVENANCE｜把 M9 现有概览拼成有出处、会判旧的最小项目驾驶舱

- **唯一用户问题**：作者重开项目时，不能在一个可信页面看清写到哪、当前人物／故事线和下一步，而又不被未确认候选或未来计划冒充已发生。
- **输入**：
  - current confirmed facts 和 chapter index
  - current plan／planning longline read view
  - 现有 overview／book overview 投影
- **输出**：
  - 最小首屏：故事梗概、已完成／current 章进度、当前 pending／stale 项、当前故事线与下一步
  - 每个数字和状态都带来源 ID、版本、SHA；无法机械定义的指标显示 unavailable
- **保存位置**：复用或新增 `overview_dashboard` 可重建投影；不写 facts、plan 或章节账。
- **实际使用方**：打开小说项目的第一屏；隔几天回来续写的作者
- **建议最小写集**：
  - M9 dashboard compiler
  - projection workspace／reader
  - 来源与 stale 测试
- **禁改范围**：
  - 不得让未确认候选进入已发生指标
  - 不得把 plan paid／revealed 当 actual／reader-known
  - 不得编“重大人物”“重大抉择”等没有冻结算法的数字
  - 不得改真值
- 💡 **正常例**：项目有 12 个 current 章节、一个 pending 章事实稿请求、两条 current storylines。首屏分别显示，并能点回来源。
- ⚠️ **危险反例**：
  - facts 在编译中前进：丢弃整张 dashboard，不留下事实新、计划旧的混合页。
  - 只有 extracted 候选提到某人物阵营：人物／阵营计数不得加一。
- **最小测试**：
  - facts／plan／pending 分区
  - 每项 provenance 完整
  - 源变化全页丢弃
  - 重启读回与 stale
  - 零真值写入
- **停下问 CZ 的条件**：“重大抉择、爽点、目标进度、人物主次”等指标若没有机械定义，只交付已经冻结的子集；其余列 unavailable 并问 CZ，不自行定阈值。
- **做完仍不能宣称**：不能宣称完整产品首页 UX、作者留存或叙事质量得到验证。
- **与专项窗口关系**：无；只拼现有有权读面。

### TASK-RUNTIME-R01-M5-CONFIRMATION-BURDEN｜给 M5 增加不改事实的确认负担回执

- **唯一用户问题**：作者能确认事实，但产品不知道每千字打扰了作者多少次，也无法识别重复提示和确认疲劳。
- **输入**：
  - 不可变 review action 历史
  - 对应章节 current 字数／source identity
  - 有正式身份的普通动作、高影响单签和系统停点事件；没有身份的事件只能记 unknown
- **输出**：
  - 每章和每千字确认动作数
  - 重复展示／重复动作数
  - 高影响单签数、普通批量动作数、unknown 事件数
  - 来源与计算公式
- **保存位置**：窄投影 `review_burden_report`；不改 review action、facts 或原文。
- **实际使用方**：M5 审查页轻量统计；M9 可选指标；产品评测而非真值模块
- **建议最小写集**：
  - 纯函数 burden compiler
  - 可重建投影 workspace／reader
  - 直接测试
- **禁改范围**：
  - 不得把“点击少”直接等同于质量更好
  - 不得补造高影响分类
  - 不得改变任何确认／驳回动作
  - 不得设计训练或 Gold
- 💡 **正常例**：一章 3000 字，作者批量确认 8 条普通候选、单签 1 条死亡事实、驳回 2 条；回执按有权动作身份计算并可追到 action IDs。
- ⚠️ **危险反例**：
  - 同一 idempotent operation 重放：不得重复计数。
  - 章节字数或事件身份缺失：输出 unknown／不可计算，不能用 0 填空。
- **最小测试**：
  - 幂等 replay 去重
  - 普通批量与高影响单签分开
  - 缺 source／字数返回 unknown
  - 源变化 stale
  - 零事实写入
- **停下问 CZ 的条件**：如果 review action 事件分类里没有冻结“高影响单签／普通批量／系统停点”的机器字段，先只交付总动作数和 unknown 分类；更细统计停下问 CZ。
- **做完仍不能宣称**：不能宣称确认体验已好、作者负担已低或事实质量提高。
- **与专项窗口关系**：无；不补 R03 测试题，只做运行投影。

## 10. 专项窗口只登记，不重复设计

### 双车道与十本账专项窗口

- **登记项**：`GAP-SELF-01`；`GAP-SELF-02`；`GAP-SELF-03`；`GAP-SELF-04`；`GAP-LEDGER-01`；`GAP-M8-01`
- **不在本窗口重复开卡的原因**：这些问题共享章事实稿正式身份、C11／章节账／事实准入和十本账 owner。拆成第二套施工卡会产生互相打架的合同。

### R03 测试补齐专项窗口

- **登记项**：两份旧测试依赖未版本化 TEMP 夹具；任务 ZIP 省略 novel-mvp/cli.py，部分 c10 entrypoint 测试在包内不可收集；142 条中 PARTIAL／BACKGROUND／CONTRADICTS 项的新增原子测试
- **不在本窗口重复开卡的原因**：本报告只给证据分类和可移植性缺口，不重复设计 142×测试。

### 多形态导入专项窗口

- **登记项**：`GAP-IMPORT-01`；CSV 列语义；Excel sheet 读取；剧本／灵感／产品原生大纲身份与落账
- **不在本窗口重复开卡的原因**：当前只有 CSV strict text、Excel gate 和未来文档；入口语义应在同一专项冻结。

## 11. 最终边界

- 没有写代码补丁。
- 没有调用 API 或模型。
- 没有设计训练或 Gold。
- 没有把测试数量当成产品质量。
- 没有用新的统一工作流平台、全局事件总线或治理层替代局部能力。
- 所有结论只在 01efc50 和本任务包证据范围内成立。

当前最准确的收口句是：**外来道和多项底层模块已经有可独立运行的机械能力；R14 自产章主路径还停在“原型＋pending＋只读供料”，十本账还停在“目录＋少数现有 owner”，不能写成小说辅助产品主循环已经闭合。**

来源：ChatGPT（只读审查包内代码、合同、直接测试与 Project Sources R14／R01／R03）
