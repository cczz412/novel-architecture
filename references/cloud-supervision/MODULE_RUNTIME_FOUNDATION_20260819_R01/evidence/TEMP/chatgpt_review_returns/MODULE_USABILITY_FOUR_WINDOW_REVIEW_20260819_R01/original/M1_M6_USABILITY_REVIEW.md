# M1～M6 独立可用性与交接审查

- 审查身份：`ADVISORY_ONLY`
- 审查对象：共用 review ZIP 内的当前代码、正式合同、直接测试、当前总控简报、R13 与原子需求背景
- 结论口径：**代码与直接测试证明“已经做到什么”；R13 与原子需求只说明“应该做到什么”；旧顾问意见只作先验。**
- 不产生：代码修改、正式合同修改、R13 修改、Gold／训练／生产结论、模型调用或上传权限

---

## 1. 一页结论

### 总判决

| 模块 | 判定 | 现在能独立做什么 | 不能外推成什么 |
|---|---|---|---|
| M1 | **存在安全断点** | 上传对象与上传前检查可独立使用；TXT／MD／DOCX／ZIP 的格式、解码、容器安全和损失小票有清楚结果；原始上传可进 `AuthorWorkspace` 不可变存储并重启读回 | 不能说“上传材料已经进入章节主线”。当前没有一条由 M1 自己拥有的安全路径，把持久化上传变成 C11 current revision，再物化为合法 C1 v1 current view |
| M2 | **机械可用** | 给定合法、current 的 C1 v1 批次，可确定性生成 C2 v1、完整覆盖回执、人读责任段地图；可保存、重启读回、过期拒绝、整批失败不写 | 不能说切段对真实稀疏章、超长段、跨边界事件已经“语义够用” |
| M3 | **只有切片** | 给定 current C2 v1 和一份与责任段键完全闭合的冻结 provider response，可生成 C3 v1；坏形状、旧 revision、未知 item key、责任段外非空 quote 会失败关闭；可保存和重启 | 不能说真实模型抽取质量已证明。现役工作区测试证明的是**离线响应运输、校验和版本绑定**，不是事实召回、精度或证据承托 |
| M4 | **只有切片** | 给定同版 C1＋C2＋C3，可把候选机械变成带 raw chapter anchor 的 C4 v1 `extracted`；多章可全批预检，失败不留半套；对象／文件入口可保留既有 confirmed | 不能说事实账可连续日常使用。工作区入口只会创建第一份 `facts` 快照，第二批无法增量并入；章节改稿后的 `current / needs_recheck / evidence_gone` 生命周期还没接通 |
| M5 | **可试用** | 在“当前章、current revision、VERIFIED、extracted 候选”的窄范围内，作者可分页查看证据，只对点名项执行 `confirm / reject / edit / edit_and_confirm`；批次原子提交、重放、stale 绑定、250 条分页和作者隔离已有直接测试 | 不能说完整作者审查体验已完成；高影响单签、显式历史查看、跨页固定会话、下游 RE stale 同事务传播仍有缺口 |
| M6 | **机械可用** | 只读 current revision 上 `confirmed + VERIFIED + recheck=null` 的事实；无命中不编答案；返回 quote、anchor、revision、来源和排除计数；“截至某章”按 `chapter_index` 数组顺序防剧透，正文上下文也只从可见前缀取 | 不能说自然语言问答已成立。当前是所有查询词都必须字面命中的检索器，不理解别名、关系问法或大白话，也不生成综合答案 |

### 哪些东西现在可以拿来试

- **M1 上传前检查器**可以作为独立小工具试用：作者给文件，它返回“读到了什么、丢了什么、为什么阻断”，不碰真值。
- **M5 当前章事实审查**可以做窄试用：候选已经在 C4 里时，作者按章分页看证据并明确处置；未选项保持原状。
- **M2 和 M6**可以作为开发者／Agent 的机械工具试用：一个切责任段，一个查当前已确认事实与证据。它们都不是面向普通作者的完整功能面。

### 当前真实成立的最长交接

下面这条链，在**调用方已经手工提供合法 C1 current**、M3 使用**冻结离线响应**、M4 只做**第一批 facts 快照**的前提下，机械上已经成立：

`C1 current → M2/C2 → M3/C3 → M4/C4 EXTRACTED → M5 作者动作 → C4 CONFIRMED → M6 关键词查询＋证据`

它证明的是：版本门牌、文件运输、AuthorWorkspace 原子提交、重启读回、作者隔离和多数 stale 防护可以拼起来。它**没有证明**：上传自动变章节、真实模型抽取正确、事实账能持续接第二批、改稿后旧事实能正确迁移、自然语言查询能回答作者问题。

### 普通作者最早卡在哪里

普通作者最早卡在 M1 内部，而不是 M2：

> 文件检查和原始上传保存完成后，系统没有一个当前 owner 把“这几个 span 是作者确认的章节”变成 C11 初始 revision 与 C1 v1 current view。

`chapter_workspace.py` 明写自己只保存“上游已经确认好的 current view”，不创建 C11、不判断 current。当前总控简报也把缺口列成四件：C10 origin、唯一章节号 owner、C11 runtime writer、跨存储协调器。旧 `ingest.py / intake_identity.py` 虽能写 C10 和旧 C1 投影，但它走 legacy project store，不是同一条 AuthorWorkspace＋C11 current 主线。〔证据：`02_current_route/novel-mvp/mvp/chapter_workspace.py:1-5,108-143`；`01_current_truth/TEMP/t03_total_control_hub_20260818_r01/CURRENT_CONTROLLER_BRIEF.md:27-30`；`02_current_route/novel-mvp/mvp/ingest.py:230-314`；`02_current_route/novel-mvp/mvp/intake_identity.py:327-411`〕

### 最该做的三件事

1. **补 M1 的“首次章节准入”窄路径**：输入必须是作者已经明确确认的 Chapter spans 和外部已分配的稳定 chapter IDs；程序只生成 C10 origin、C11 r1 和 C1 current，并在一次 AuthorWorkspace 事务里提交，不能顺便做自动分类或元数据推断。
2. **把 M3 从“冻结 response 搬运”推进到“真实语义可评”**：先统一真实 provider 与离线 provider 的严格解析边界，堵住空 quote、坏 fact 被静默丢弃和高密度截断“其余舍弃”；再用少量权利清楚的真实责任段做语义验收。
3. **让 M4 能接第二批，并补 revision 生命周期**：增量并入时保留旧 fact ID、confirmed/rejected 和作者决定；章节改稿后先做只读 anchor effect 预览，再决定 unique move、`needs_recheck`、`evidence_gone` 的正式 writer。不要把两件事做成一个大重构。

---

## 2. 审查方法、证据等级与复跑限制

### 证据等级

| 等级 | 本报告怎样使用 |
|---|---|
| A｜当前代码＋直接测试 | 用来判断对象入口、字段门、原子性、重启、stale、隔离和失败行为 |
| B｜当前总控简报／模块结果票 | 只使用明确写出的测试数量、停点和 owner 缺口 |
| C｜正式合同 | 用来判断代码是否只覆盖合同的一部分，不能反向证明实现完成 |
| D｜R13／原子需求 | 用来判断用户目标和差距，不当作代码事实 |
| E｜旧外审 | 只作反方提示；本报告不靠旧顾问结论定当前完成度 |

### 包体与辅助复跑

- ZIP 清单与 SHA 已逐项核对通过；路线图登记 223 个业务成员，并明确“当前代码与直接测试证明机械现状”。〔`00_ROUTE_MAP.md:16-31`〕
- 包锁定 Python `3.12.12`。当前离线审查容器只有 Python `3.13.5`，无法联网下载 3.12.12；因此不能把本容器复跑冒充正式锁定环境结果。
- 包里若干测试会 import 未随 ZIP 提供的 `cli.py`，全量收集会受阻。定向辅助复跑在 Python 3.13 下连续跑过约 190 个 M1～M6 用例后达到容器时限，期间没有新增断言失败；这只作补充信号。
- M6 有一条旧测试写死 workspace read 次数，当前总控明确标成既有断言漂移，不是新功能失败。〔`01_current_truth/TEMP/t03_total_control_hub_20260818_r01/CURRENT_CONTROLLER_BRIEF.md:12-15`〕
- 所以，本报告对“通过”的正式用词只来自包内直接测试源码、当前总控明确结果和代码行为；无法复跑或缺直接样例的地方写“材料不足”。
- 路径缩写：下文 `mvp/...`＝`02_current_route/novel-mvp/mvp/...`；`contracts/...`＝`02_current_route/novel-mvp/contracts/...`；`tests/...`＝`02_current_route/tests/...`。

---

## 3. M1～M6 能力表

| 模块 | 真实输入 | 明确输出 | 核心对象入口 | 本地文件入口 | AuthorWorkspace | 持久化／重启 | 失败保旧 | 可安全交给谁 | 不可外推边界 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|
| M1 | `UploadSource(source_name, raw_bytes, declarations?, encoding_hint?)`；本地适配器可读文件后构造对象 | 格式路由 items、损失／阻断 receipt、人读上传检查；另有 raw upload immutable receipt 和当前 M1 state | **有**。`UploadSource` 拒绝绝对路径、`..`、斜杠和 Windows drive；`collect_uploads()` 不接项目路径 | **有**。`from_local_path`、`collect_paths`、`upload_inspect_tool`；输出做同路径／硬链接／软链接别名防护和原子替换 | **部分有**。`persist_m1_result()` 保存 raw uploads＋manifest＋module_state；但不产 C10/C11/C1 | M1 state 和 raw bytes 可重启复验、重新构造 UploadSource | 可见 state 一次 commit；写输出失败保留旧文件。immutable blob 可能先写后成为孤儿，但不会被 current manifest 看见 | 上传检查／后续显式材料准入器 | 本地输入适配器会跟随受信任根文件软链接；Excel/CSV 仅落 generic unsupported；没有 raw upload→C11/C1 current owner | **存在安全断点** |
| M2 | 合法 C1 v1 current view 批次＋显式 `seg_min_chars / seg_max_chars / halo_chars` | C2 v1 items、逐章 coverage receipt、人读责任段／halo 地图 | **有**。`segment_tool.execute()` 只接对象 | **有**。JSON file/stdin→JSON file/stdout；输入输出别名关闭；原子写 | **有**。只从绑定句柄读 `chapters + chapter_index`，一次写 `segments` | 保存 source identity；重启时重算并核对；上游改变返回 STALE | 全批先验 C1；任一章失败不写；source race 不提交 | M3 | 坐标是规范化书稿，不是 raw file；超长单段会原样成为 oversize 段；固定档位的真实语义收益未证明 | **机械可用** |
| M3 | C2 v1 items＋current revision refs＋response provider；当前工作区入口要求完整冻结 response mapping | C3 v1 candidates；工作区保存 candidates＋source identity＋responses hash/item keys | **有**。`extract_tool.execute()` 只有一个 provider 替换缝 | **有**。冻结 responses JSON＋C2 JSON→C3 JSON；原子输出 | **有**，但目前**只走离线 response**，零模型调用 | 可重启读回；C2/index 或 response identity 变化即 stale／拒绝 | 完整 response key 集、所有 provider shapes、所有 candidates 先过才 commit | M4 | 非空 quote 仅证明字面属于责任段，不证明语义托住；空 quote 可过 M3、到 M4 才失败；真实 `extract.py` parser 会静默丢坏 fact；真实抽取质量材料不足 | **只有切片** |
| M4 | 同 revision 的 C1、C2、C3；可选既有 C4（仅对象／文件入口） | C4 v1 `extracted` snapshot、new fact refs、VERIFIED raw anchor | **有**。`fact_tool.execute/execute_batch` 只接对象 | **有**。JSON→JSON；原子输出；可带 `existing_c4` | **有**，但 `materialize_current_extracted_snapshot()` 固定 `expected_version=0` | 初始 snapshot 可重启；current view 会排除旧 revision 并返回 stale IDs | 多章第二章失败不返回／不覆盖半批；source race 不 commit | M5、M6 | 工作区不能接第二批；没有 duplicate/similar/conflict grouping；没有 revision anchor migration writer；source 只是字符串 | **只有切片** |
| M5 | 当前 facts snapshot／review page＋作者显式动作；动作带 expected status、fact SHA、revision ref、operation id | 新 C4 snapshot、每项 receipt、facts version/SHA；人读审查页和动作 JSON | **有**。单条和同 revision 批量对象入口 | **有**。C4＋actions JSON→新 C4；review page→Markdown；decision rows→actions | **有**。只接绑定 workspace；一次 commit 替换 facts | 重启读回；operation replay；facts version/SHA stale 拒绝 | 批次全部内存计算后一次 commit；第二条坏则第一条不落盘 | M6；未来 revision/RE 协调器 | `edit` 仍绑定旧 quote/anchor，语义承托不重判；open session 首次读不是稳定双读；没有高影响单签分类；AuthorWorkspace 路线不做 RE stale | **可试用** |
| M6 | query＋C4 facts＋current revision refs；工作区版本只接绑定 workspace；可选 current C1 做证据上下文和 as-of chapter | matches、evidence、excluded_counts；可选 reader_scope 和 before/quote/after context | **有**。`ask_tool`／reader scope／context 都是对象核心 | **有**。JSON file/stdin→JSON file/stdout；原子写；失败保旧 | **有**。只读 `facts/chapter_index/chapters`，不写查询结果 | 重启返回同一水位；查询前后水位改变则丢弃结果 | 无输出落盘半状态；本地输出替换失败保旧 | 作者证据查看、M7/M8/M11 的受控读侧 | 只是 `query.split()` 后所有词的 substring AND；不懂别名、关系、大白话；context/reader workspace 遇到任何 stale fact 会整次拒绝 | **机械可用** |

### 能力表主要证据

- M1：`02_current_route/novel-mvp/mvp/upload_source.py:_validate_source_name, UploadSource, from_local_path`；`mvp/input_router.py:_decode_text,_safe_zip_name,_docx_main_flow,_Collector,collect_uploads,collect_paths`；`mvp/upload_inspect_tool.py:execute,render_inspection,_validate_output_path,_write_bytes_atomic`；`mvp/ingest_workspace.py:persist_m1_result,read_persisted_m1_state,load_persisted_upload_sources`；直接测试 `test_novel_mvp_upload_source.py`、`test_novel_mvp_upload_inspect_tool.py`、`test_novel_mvp_ingest_workspace.py`。
- M2：`mvp/segment.py:build_segments,segment_chapter`；`mvp/segment_tool.py:_chapter_coverage_receipt,execute`；`mvp/segment_workspace.py:persist_current_segments,read_current_segments`；直接测试 `test_novel_mvp_segment_tool.py`、`test_novel_mvp_segment_workspace.py`。
- M3：`mvp/extract.py:INSTRUCTIONS,parse_fact_call_result,extract_segment`；`mvp/extract_tool.py:_validate_provider_result,_validate_c3_candidate,execute,offline_response_provider`；`mvp/extract_workspace.py:persist_current_fact_candidates,read_current_fact_candidates`；直接测试 `test_novel_mvp_extract_tool.py`、`test_novel_mvp_extract_workspace.py`、`test_novel_mvp_m3_c2v1_c3v1.py`。
- M4：`mvp/factstore.py:build_extracted_c4_snapshot,validate_c4_v1_snapshot`；`mvp/fact_tool.py:execute,execute_batch`；`mvp/fact_workspace.py:materialize_current_extracted_snapshot,read_current_snapshot`；直接测试 `test_novel_mvp_fact_tool.py`、`test_novel_mvp_fact_workspace.py`。
- M5：`mvp/factstore.py:_validate_review_action,apply_review_action_to_c4_snapshot`；`mvp/review_tool.py:execute,execute_batch`；`mvp/review_workspace.py:apply_review,apply_review_batch`；`mvp/review_queue_workspace.py:open_chapter_review_session,read_chapter_review_page`；直接测试 `test_novel_mvp_review_*.py`。
- M6：`mvp/ask_tool.py:execute`；`mvp/ask_workspace.py:execute`；`mvp/ask_context_workspace.py:execute`；`mvp/ask_reader_scope_tool.py:execute`；`mvp/ask_reader_scope_workspace.py:execute`；`mvp/ask_reader_context_workspace.py:execute`；直接测试 `test_novel_mvp_ask_*.py`。

---

## 4. 当前真实交接图

```text
上传材料
  │  已证明：UploadSource → 格式/安全检查 → raw upload + M1 state 持久化
  ▼
C10 材料身份 / C11 初始 revision / C1 current
  │  断裂：当前调用方需手拼；缺 C10 origin、chapter ID/number owner、C11 writer、跨存储协调
  ▼
M2 / C2
  │  已证明：同 AuthorWorkspace current C1 → C2；持久化、重启、stale、整批原子
  ▼
M3 / C3
  │  只有运输：冻结 provider response → C3；字段和 quote 字面门已证明，真实语义缺失
  ▼
M4 / C4 EXTRACTED
  │  已证明：第一批 current C1+C2+C3 → VERIFIED-anchor EXTRACTED
  │  断裂：第二批 workspace 增量；缺 revision migration owner
  ▼
M5 作者动作
  │  已证明：显式 confirm/reject/edit/edit_and_confirm；分页、原子批次、重放、stale
  │  缺 owner：被改判事实引用的 RE/actual support 不在 AuthorWorkspace 同事务失效
  ▼
C4 CONFIRMED
  │  已证明：M6 基础读只收 current + confirmed + VERIFIED + recheck=null
  ▼
M6 查询与证据
     机械成立：关键词、证据、排除计数、截至章、同 revision 上下文
     缺语义：别名/关系/大白话/综合回答
     安全断点：reader/context workspace 遇到任一 stale fact 会整次拒绝
```

### 每条边的诚实状态

| 边 | 状态标签 | 当前证据 | 还缺什么 |
|---|---|---|---|
| 上传对象 → 格式路由／检查 | **已证明** | 四格式对象入口、严格解码、ZIP 安全、DOCX 未覆盖区强停、损失小票、路径别名保护 | 本地输入根软链接是否也要拒绝；CSV/XLSX 专门说明 |
| 格式路由 → raw upload AuthorWorkspace | **已证明** | immutable raw upload、manifest/module_state 一次可见提交、重启复验、作者隔离 | 与 C10/C11/C1 没有 owner 接口 |
| raw upload／C10 → C11 r1 → C1 current | **断裂＋调用方手拼＋缺 owner** | `chapter_workspace` 明确不创建 C11；总控列四个缺口 | 首次准入对象、稳定 ID/章序 owner、C11 logical key/writer、单事务提交 |
| 合法 C1 current → M2/C2 | **已证明** | `chapter_workspace` 与 `segment_workspace` 直接测试 | 真实语义切段数据；oversize 策略 |
| M2/C2 → M3/C3 | **只有文件运输＋缺语义** | response key、revision、shape、非空 quote 所属段、原子 commit | 真实 provider 严格同构；语义精度/召回/承托；空 quote 门；截断覆盖 |
| M3/C3 → M4/C4 EXTRACTED | **已证明（首批）** | raw anchor 回拼、quote 唯一命中、IDs、全批原子 | workspace 第二批 merge；去重/冲突组；高密度策略 |
| 后续 C3 batch → 既有 C4 | **断裂** | 对象／文件 `existing_c4` 可行；workspace 固定 `expected_version=0` | current facts 读入、expected version/SHA、幂等增量提交 |
| C4 EXTRACTED → M5 作者动作 | **已证明** | 当前章队列、250 条分页、显式选择、单条/批量原子、stale、重放 | 固定跨页 session；高影响单签；edit 后语义证据门 |
| M5 改判 → 下游 RE stale | **缺 owner** | C4 合同要求同事务；AuthorWorkspace adapter 明确“不做 reconcile” | 由谁持有 RE、怎样跨 logical key 同事务、失败恢复 |
| C4 CONFIRMED → M6 基础查询 | **已证明（机械）** | current/confirmed/VERIFIED/recheck 门、证据、无命中、排除计数 | 自然语言语义、别名、关系回答 |
| C4/C1 current → M6 上下文 | **已证明但过严** | quote raw slice 和三水位闭合 | stale history 应排除并计数，不应让整次 current 查询死亡 |
| chapter_index → as-of 防剧透 | **已证明（机械）** | 非连续 ID 按数组顺序、未来 facts/refs/body 不进入查询和 context | 普通用户问题理解；是否展示更完整 coverage receipt |

---
## 5. 从代码里额外发现的高风险真实场景

这些不是把原子需求重复一遍，而是当前实现组合后会真实出现、且旧摘要容易漏掉的失败面。

### HR-01｜M1 本地输入根文件若本身是软链接，会被跟随读取

`UploadSource` 的核心对象入口不接路径，逻辑名也严格拒绝斜杠、`..` 和 Windows drive；这部分是安全的。但 `from_local_path()` 只做 `Path.is_file()` 后 `read_bytes()`，会跟随调用方提供的文件软链接。`collect_paths()` 对 ZIP 成员有路径与链接防护，`upload_inspect_tool` 对**输出**别名也防得很严，却没有直接测试“根输入文件是软链接时必须拒绝”。这不等于已发生跨作者泄漏，因为该入口明确写成 `LOCAL_FILESYSTEM_ONLY`、假定受信任本地 CLI；但一旦前端或 Agent 把不可信路径暴露给它，边界会被读反。〔`mvp/upload_source.py:90-95`；`mvp/input_router.py:1-4`；`tests/test_novel_mvp_upload_source.py:test_local_path_adapter_matches_memory_core`；材料不足：没有 root-input-symlink 反例测试〕

### HR-02｜M1 的可见状态原子，但 immutable blob 可能在提交失败后成为不可见孤儿

`persist_m1_result()` 先逐个写不可变 raw upload，再用一次 `workspace.commit()` 切换 `input_manifest + module_state`。这能保证作者看到的是全套或旧套，不会看到半套；但如果 immutable 写完、最终 commit 失败，新的 blob 可能留在底层而没有 current manifest 引用。当前读取面不会泄漏或误用它，属于垃圾回收／配额问题，不是业务半写。施工时不能为了消灭孤儿反过来放弃不可变写入。〔`mvp/ingest_workspace.py:persist_m1_result`；`mvp/workspace.py:write_immutable,commit`；`tests/test_novel_mvp_ingest_workspace.py:test_version_conflict_leaves_both_visible_keys_unchanged`〕

### HR-03｜M1 当前 C10 角色集合与“六材料架”并不完全同构

现行 C10 明确覆盖 `INTRO / CHAPTER / SETTING / TITLE / TAGS` 等身份；包内 C10 说明同时写着 OUTLINE 迁移没有完成。旧 ingest 路线还能产 legacy `C1 kind=outline`。因此“简介、标签、设定、章节、大纲混在一起”时，不能把“六架产品语义”直接写成当前正式 C10 全覆盖。M1 上传检查只显示声明／Unknown，不自动补这个缺口。〔`02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`；`mvp/intake_identity.py`；`tests/test_novel_mvp_c10_first_entrypoints.py`；R13 `03_CREATION_AND_MEMORY_PIPELINES.md` 的六架是产品方向，不是现状证明〕

### HR-04｜M2 对超长单段的行为是“保完整、记 oversize”，不是阻断或拆开

`build_segments()` 明确把单段超 `hi` 保持完整；coverage receipt 只统计 `oversize_segment_count`。这避免把自然段硬切坏，但一段数万字会完整交给 M3，可能超过模型输入、让抽取截断或成本失控。当前没有 `allow/block` 策略，也没有超限停止门。〔`mvp/segment.py:35-63`；`mvp/segment_tool.py:199-212`；`tests/test_novel_mvp_segment_tool.py:test_execute_emits_only_c2_v1_items_with_revision_ref_and_stable_receipt`〕

### HR-05｜M3 的正式实时 parser 与离线工具不是同一把严格尺子

`extract_tool._validate_provider_result()` 对顶层、`data`、`facts`、每条 `text/quote` 都做 exact-shape 校验；坏字段不能修复或静默丢弃。可 `extract.parse_fact_call_result()` 会用列表推导式忽略非对象、没有 text 或 text 为空的 fact，并把缺 quote 变成空字符串；`data` 的额外字段也不拒绝。当前 AuthorWorkspace 走冻结离线 response，所以严格门有效；一旦换回真实 `call_model()` 路径，就可能出现“模型回了坏条目，但系统悄悄少了几条”。〔`mvp/extract_tool.py:101-128`；`mvp/extract.py:208-225`；`tests/test_novel_mvp_extract_tool.py:test_provider_fields_are_not_repaired_or_silently_dropped`〕

### HR-06｜M3 空 quote 可成为合法 C3，到 M4 才失败

严格 provider 门只要求 quote 是 trim 后字符串，不要求非空；C3 校验也只在 `quote` truthy 时检查它是否属于责任段。于是 `{"text":"…","quote":""}` 可通过 M3。M4 的 anchor 构造要求非空、唯一且能回 raw revision，才会拒绝。这会把“抽取运输成功”与“可交给下一模块”拆开，违反核心判定句里的安全交接。〔`mvp/extract_tool.py:119-142`；`mvp/factstore.py:build_extracted_c4_snapshot`；材料不足：现有 M3 测试没有空 quote→M4 handoff 反例〕

### HR-07｜M3 截断重试明确写着“其余舍弃”

`RETRY_DENSITY_NOTE` 在疑似截断时要求只留前 25 条最重要事实并“其余舍弃”。这可以换到合法 JSON，却把高密度章的覆盖损失藏成成功结果；原子需求 M3-E05 正好要求两三百条候选时不能照单全收，也不能静默丢。当前 C3 没有 `incomplete/truncated/coverage` 回执承接这一事实。〔`mvp/extract.py:35-40,197-204`；`01_current_truth/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260819_R02/01_ATOMIC_EXPECTATIONS.md` 的 `M3-E05`〕

### HR-08｜M4 工作区物化路径天然是“第一次建账”，不是增量写入器

`materialize_current_extracted_snapshot()` 从空 `snapshot=[]` 开始，把本次各章依次追加，然后调用 `save_snapshot(... expected_version=0)`。如果 facts 已存在，工作区测试期望它冲突并保留旧批次。这是安全的，但意味着第二次正常抽取不能进入事实账。对象／文件工具支持 `existing_c4`，工作区没有把它接进来。〔`mvp/fact_workspace.py:305-375`；`tests/test_novel_mvp_fact_workspace.py:test_existing_facts_version_conflict_never_replaces_prior_batch`；`tests/test_novel_mvp_fact_tool.py:test_existing_c4_snapshot_is_preserved_and_only_new_record_is_extracted`〕

### HR-09｜M4 没有候选去重、相似合并、冲突分组或密度门

M4 只验证 revision、quote 和 raw anchor，然后为每条候选发 fact ID。相同／近似／互相冲突的候选只要机械合法，就会全部进入 `extracted`。两三百条候选也会照单全收；M5 虽能分页，但确认负担会被上游噪音直接转嫁给作者。〔`mvp/factstore.py:build_extracted_c4_snapshot`；`mvp/fact_tool.py:execute_batch`；原子需求 `M4-B03`、`M4-C03`〕

### HR-10｜M5 的 `edit`／`edit_and_confirm` 改主张文本，但沿用旧证据

作者编辑事实文本时，C4 的 quote、anchor 和 revision 身份不变。机械上这是可追溯的作者动作；语义上，新文本可能已经超出旧 quote 能托住的范围。当前没有独立 support check，也没有强制把编辑后的事实送回 `needs_recheck`。这不是说作者不能改，而是“作者改写主张”与“旧证据仍能证明它”现在被合在一次动作里。正式改合同前必须问 CZ：作者签字本身是否可成为新来源，还是仍要求书稿证据逐字托住。〔`mvp/factstore.py:_validate_review_action,apply_review_action_to_c4_snapshot`；`tests/test_novel_mvp_review_decision_tool.py:test_explicit_edit_and_edit_confirm_reuse_formal_semantics_in_one_commit`；R13 真源按问题分权〕

### HR-11｜M5 开启会话不是稳定双读，跨页也没有固定同一 facts 水位

`open_chapter_review_session()` 依次读一次 facts、一次 chapter_index；`read_chapter_review_page()` 才使用稳定双读。打开会话时若两个 logical key 在读取间改变，可能得到混合快照；后续翻页只靠 `after_fact_ref` 在**当时最新** facts 中续读，没有 session token 固定最初水位。已有测试证明“作者根据旧页提交动作”会被 page watermark 拒绝，也证明处理后的最后项仍可当游标；但没有证明任意外部变更后翻页会显式要求重开。〔`mvp/review_queue_workspace.py:176-283`；`tests/test_novel_mvp_review_queue_workspace.py:test_facts_change_after_open_is_rejected_by_existing_batch_watermark`、`test_processed_last_item_remains_a_valid_resume_anchor`〕

### HR-12｜M5 AuthorWorkspace 写事实时明确不处理 RE／actual support

legacy `fact_review_transaction` 有跨文件恢复与旧 actual support 失效测试；当前 AuthorWorkspace `review_workspace` 只原子改 `facts`。C4 合同要求章节 revision 迁移与相关 RE stale 同事务，但当前工作区注释明确把 reconcile 排除在适配器外。不能用 legacy transaction 的通过证明新 AuthorWorkspace 链已经闭合。〔`tests/test_novel_mvp_fact_review_transaction.py:test_rejudge_invalidates_old_actual_support_and_does_not_revive_it`；`mvp/review_workspace.py`；`contracts/C4_FACT_QUERY.md`〕

### HR-13｜M6 基础查询能安全排除 stale，正文上下文／截至章工作区却会被任一 stale fact 整体拖死

`ask_tool.execute()` 对旧 revision 只增加 `stale_revision` 排除计数并继续查 current facts，这是正确的读侧姿势。可 `ask_context_workspace._validate_closed_snapshots()` 和 `ask_reader_scope_workspace._validate_pair()` 遍历整份 facts，只要有一条旧 revision 就拒绝整次请求。M4 又有意保留 stale history，因此项目改过一章后，基础查询仍能用，带上下文或防剧透查询反而全部失效。〔`mvp/ask_tool.py:179-246`；`mvp/ask_context_workspace.py:59-98`；`mvp/ask_reader_scope_workspace.py:100-125`；`tests/test_novel_mvp_fact_workspace.py:test_read_current_snapshot_excludes_only_advanced_chapter_and_keeps_history`〕

### HR-14｜M6 的“大白话查询”其实是所有空格分词都必须字面出现

`keywords = query.split()`，匹配条件是 `all(keyword in fact_text)`。中文不带空格时整句作为一个关键词；“他俩后来闹翻了吗”只有事实文本恰好含整句才会命中。带空格时又是 AND，不支持同义词、别名、关系方向、否定或综合。这个工具的可靠身份应是“受控关键词检索＋证据展示”，不能在界面上叫自然语言回答。〔`mvp/ask_tool.py:152-170,220-246`；原子需求 `M6-C06`〕

---
## 6. M1～M6 原子需求差距

读法：

- **核心已满足**＝当前代码和直接测试已经覆盖用户目标的核心机械结果；若只证明运输，会在“边界”列收窄。
- **部分满足**＝有可复用切片，但用户目标仍缺一段关键行为、真实材料或 owner。
- **未满足**＝当前代码明确没有，或存在与目标相反的行为。
- **附加可暂缓**＝不挡下一批模块可用性的增强；不等于取消原子预期。

原子需求来源：`01_current_truth/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260819_R02/01_ATOMIC_EXPECTATIONS.md` 与机器版 `02_ATOMIC_EXPECTATIONS.json`。共同家规 GR-01～GR-10 见同目录 `04_GLOBAL_ACCEPTANCE_RULES.md`。

### M1

| 分类 | 原子 ID | 当前判断 | 依据与边界 |
|---|---|---|---|
| 核心已满足 | `M1-E05` | **满足** | 对象核心只收逻辑名＋bytes，不接 Path／author／project；危险逻辑名与 ZIP 穿越拒绝；本地适配器与对象核心结果一致。〔`upload_source.py`；`test_novel_mvp_upload_source.py`〕 |
| 部分满足 | `M1-E01` | **四格式读取与失败关闭成立；“一个字不偷偷丢”只在受支持主流区域成立** | TXT/MD 严格解码、DOCX 主文档流、ZIP 终端材料与未覆盖区强停已测；批注、文本框、修订删除等 DOCX 未覆盖区会整批拒绝而不是静默丢。原始字节与 SHA 可追。〔`input_router.py:_decode_text,_docx_main_flow`；`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py:test_four_supported_formats_return_safe_inspection_without_truth_writes`〕 |
| 部分满足 | `M1-E02` | **章数识别有局部能力，1/3/10/20 的完整产品路线未证明** | 显式 Chapter declarations 与文件名章序有机械处理；没有直接材料证明单文件 20 章会先给规模／分批／整本工程选择，也没有静默截断证据。结论只能写“材料不足”。 |
| 部分满足 | `M1-E03` | **明确声明的分流可运输；自动六架不成立** | C10 明确身份与 Unknown 可保留；只有 Chapter 能安全进入章节候选方向。OUTLINE 正式迁移仍开，未声明混合内容不会自动语义拆分。 |
| 部分满足 | `M1-E04` | **当前批次的缺章／重复／乱序／标题冲突有检查；跨已有项目追加不完整** | 路由能发现 declared chapter 序列问题、文件名与正文标题冲突；短非空材料保留，空终端阻断。缺章判断主要看本批，不能证明“先有 c01 后追加 c03”按整个项目强停。 |
| 未满足 | `M1-E06` | **断裂** | raw upload 可持久化，C1 current 也可被上游直接持久化，但中间没有 C11 r1 writer/current owner；旧版不能冒充 current 的责任落在调用方。〔`chapter_workspace.py:1-5`；总控简报 27-30〕 |
| 附加部分满足 | `M1-B03` | **大部分满足** | 垃圾文件、嵌套层数、文件数、单件/总解压上限、CRC/容器损坏、编码严格和损失小票都有；水印只标候选的专门能力材料不足。 |
| 附加可暂缓 | `M1-B01` | **未满足，可后置于首次 1～20 章准入** | 没有 20/80 章预估、分层快启和覆盖回执产品路线。 |
| 附加可暂缓 | `M1-B02` | **未满足** | 当前能展示声明和 Unknown，但没有“为什么分到这个架子”的语义解释、作者改判历史。 |
| 附加可暂缓 | `M1-N01` | **明确不支持但说明太泛** | CSV/XLSX 落 `unsupported_format`，不会静默接收；没有表格读取，也没有格式专属转换指引。先补明确拒绝即可，不必立刻实现 Excel parser。 |
| 附加可暂缓 | `M1-N02` | **未满足** | 三章裸书稿不会自动推书名、类型、主角、金手指候选；无声明时保持 Unknown，符合不硬猜，但没做到少填表。 |

### M2

| 分类 | 原子 ID | 当前判断 | 依据与边界 |
|---|---|---|---|
| 核心已满足 | `M2-E01` | **机械满足** | 合法 C1 v1 current → 同 revision ref C2 v1；工作区直接测试和重启读回通过。 |
| 核心已满足 | `M2-E02` | **满足** | 规范化书稿逐字闭合、无重叠／空洞／乱序，coverage SHA 与重组验证齐全。注意坐标不是原始文件坐标。 |
| 部分满足 | `M2-E03` | **短章、碎尾明确；超长单段只记录不处置** | 短章可单段，碎尾并回；超长单段完整保留并计 oversize，不阻断也不拆分。 |
| 核心已满足 | `M2-E04` | **机械满足** | halo 由责任段外邻接字符机械计算，人读图明确“只读”；C3 quote 门限制非空证据在责任段。但真实模型会不会偷用 halo 是 M3 语义问题。 |
| 核心已满足 | `M2-E05` | **满足** | 全批先验 C1 与 duplicate/current ref；第二章 coverage 失败不写第一章；1/3/10/20 的具体性能只对 80 章回执有直接测试。 |
| 核心已满足 | `M2-E06` | **满足** | 对象、文件、stdin/stdout，原子替换和跨进程字节稳定已测。 |
| 附加部分满足 | `M2-B03` | **回执满足，性能目标材料不足** | 80 章每章 receipt、顺序与稳定测试存在；没有正式机器、三次耗时和内存峰值结果。 |
| 附加可暂缓 | `M2-B01` | **未满足** | 参数由调用方固定传入，没有密／稀自适应和收益对照。 |
| 附加可暂缓 | `M2-B02` | **机械边界满足，语义收益未证明** | halo 能让下游看邻文，责任段证据纪律存在；没有 12 个跨边界事件的真实理解／重复率对照。 |

### M3

| 分类 | 原子 ID | 当前判断 | 依据与边界 |
|---|---|---|---|
| 核心已满足 | `M3-E01` | **运输满足** | C3 原样继承 chapter revision ref 与 seg；item key 全闭合；重启与 stale 检查齐全。 |
| 未满足 | `M3-E02` | **真实语义未证明** | Prompt 写了已发生／非计划／非猜测，但现役直接测试全是人工冻结 response；不能由 prompt 文字推出模型会遵守。 |
| 部分满足 | `M3-E03` | **字面门不完整** | 非空 quote 必须属于自己的责任段；空 quote 可通过，且“字面在段内”不证明语义托住主张。 |
| 部分满足 | `M3-E04` | **离线严格，实时路径有缺口** | frozen provider 的少/多字段、旧 revision、未知 key、坏 quote、整批原子都测了；实时 parser 会静默丢坏 fact，截断重试会舍弃其余，超时重试次数的端到端材料不足。 |
| 未满足 | `M3-E05` | **未满足，且存在反向风险** | 没有密度诊断／灌水门；截断重试只留前 25 条。 |
| 核心已满足 | `M3-E06` | **离线运输满足** | response keys 必须与 current C2 完全相等；缺一段、混旧版、source race 整批不提交；真实 API 调用的可恢复停点未证明。 |
| 附加可暂缓 | `M3-B01/B02/B03` | **未满足** | 质量精炼链、跨模型同卷基准、fact_core＋qualifiers 都不是当前 M3 合同能力。 |
| 附加可暂缓 | `M3-N01/N02` | **未满足，应旁挂而非进事实主线** | 爽点和章末钩子是推断旁挂，当前 C3 只有事实候选。不要塞进同一 parser。 |
| 附加可暂缓 | `M3-N03` | **零候选运输成立，低密度解释未实现** | 一段零候选和整章全零都合法；没有“低密度／材料不足”原因回执。 |

### M4

| 分类 | 原子 ID | 当前判断 | 依据与边界 |
|---|---|---|---|
| 核心已满足 | `M4-C01` | **满足** | M4 新记录固定 `status=extracted`，不会自动确认；M6 排除 extracted。 |
| 核心已满足 | `M4-C02` | **满足当前 revision 的机械锚** | C2 规范化坐标会映回 raw C1，quote 必须唯一连续命中，anchor 记录 revision、start/end、slice SHA。 |
| 部分满足 | `M4-C03` | **全批原子满足；高密度可用性未满足** | 多章任一坏候选整批不写；但 200～300 条没有噪音门和人工负担控制，机械合法就全入 extracted。 |
| 未满足 | `M4-C04` | **未满足** | 读取 current view 能排除旧版并列 stale IDs，但没有 unique move / needs_recheck / evidence_gone 的写入迁移链，也没有与 C11 同事务。 |
| 部分满足 | `M4-C05` | **C4 来源字段存在，来源身份体系未闭合** | 当前 `source` 是非空字符串；书稿证据 anchor 有，AUTHOR_ATTESTATION、AI inference、future plan 的不同机器身份不在这条 M4 里。 |
| 核心已满足 | `M4-C06` | **满足工作区隔离** | 只接绑定 `AuthorWorkspace`，跨作者项目猜测和 path 句柄被拒绝。 |
| 附加可暂缓 | `M4-B01/B02/B03` | **未满足** | 反向覆盖账、core＋qualifiers、重复／相似／冲突分组都未实现。B03 虽可后置，但在真实高密度审查前必须补至少分组回执。 |

### M5

| 分类 | 原子 ID | 当前判断 | 依据与边界 |
|---|---|---|---|
| 核心已满足 | `M5-C01` | **满足窄范围** | 按章只列 current revision、VERIFIED、extracted 候选；页上有 fact text、quote、anchor、revision 和状态。 |
| 核心已满足 | `M5-C02` | **满足** | formal action 要求 actor=AUTHOR；模型不能伪造；同 revision 批次全成全不成，一次 commit。 |
| 部分满足 | `M5-C03` | **决定历史在 legacy 路线较强；AuthorWorkspace 下游 stale 不闭合** | operation receipts、版本、重放和改判留痕有；C4 旧状态不被静默覆盖。但 RE／actual support 同事务失效只在 legacy transaction 有直接证据。 |
| 未满足 | `M5-C04` | **未满足** | 没有死亡／复活风险分类、高影响单签或两个时间点专门验证；普通事实动作可批量。 |
| 部分满足 | `M5-C05` | **读侧排除有，迁移写入没有** | M6 排除 unverified／needs_recheck；M4 未把断锚事实写成 needs_recheck/evidence_gone，也没有自动恢复门。 |
| 核心已满足 | `M5-C06` | **满足当前章分页，不存在全书一键确认** | 250 条无漏无重分页；batch 禁止跨 revision；只选两条时其他保持 pending。 |
| 附加可暂缓 | `M5-B01` | **未满足，可由 M9 概览承接** | M5 自己没有“先故事概览再点事实”的界面编排；不要为补这个票把 M9 复制进 M5。 |
| 附加部分满足 | `M5-B02` | **自由文本/原因字段材料不足** | reject 动作成立，但可选原因 taxonomy、存储和改进消费链没有当前直接证据。 |
| 附加可暂缓 | `M5-B03` | **未满足** | 没有每千字确认次数／有效时间／批量操作负担计量。可后置于分页会话一致性。 |

### M6

| 分类 | 原子 ID | 当前判断 | 依据与边界 |
|---|---|---|---|
| 核心已满足 | `M6-C01` | **机械满足** | 基础查询只返回 current revision、confirmed、VERIFIED、recheck=null；旧版和其他状态分项排除。 |
| 核心已满足 | `M6-C02` | **满足** | 每个 match 与 evidence 以 fact_id 一一闭合，带 source、quote、revision、anchor。 |
| 核心已满足 | `M6-C03` | **部分到满足之间** | `excluded_counts` 清楚列状态、旧版、坏证据、关键词未命中；as-of 返回可见 refs。尚无完整“未读材料及原因”覆盖小票。 |
| 核心已满足 | `M6-C04` | **满足** | 空结果可解析，人读文案只说证据门内未命中，不写故事结论。 |
| 核心已满足 | `M6-C05` | **满足工作区边界** | 公开函数不接作者／项目／path；绑定 handle；跨作者 guess 被拒；as-of 隐藏未来事实、ref 和正文。 |
| 未满足 | `M6-C06` | **未满足** | 字面 substring AND，不做实体解析、别名、关系方向或自然语言回答。 |
| 附加已满足 | `M6-B01` | **机械满足** | 截止章按 `chapter_index` 顺序；非连续 chapter IDs 直接测试；未来证据和正文不泄漏。 |
| 附加已满足 | `M6-B02` | **机械满足，但 stale 历史会拖死工作区** | before/quote/after 与 raw current C1 逐字闭合、三水位一致；需要修 stale 过滤策略。 |
| 附加部分满足 | `M6-B03` | **临时结果成立，转候选再确认未实现** | M6 全程只读，不持久化查询结果；没有“提名事实候选”的窄动作。该动作应另走 M4/M5，不给 M6 真值写权。 |

### 跨模块共同家规结论

| 家规 | M1～M6 当前状态 |
|---|---|
| `GR-01` 不静默丢 | M1/M2/M4/M5/M6 较强；M3 实时 parser 静默丢坏 fact、截断“其余舍弃”是最大反例 |
| `GR-02` 不知道就说不知道 | M1 Unknown、M6 no-hit 较好；M3 低密度和截断覆盖不足没有显式回执 |
| `GR-03` 回到来源 | C1→C6 revision/quote/anchor 链较强；M5 edit 后主张与旧证据语义承托仍开放 |
| `GR-04` 计划／事实／投影不混 | M4 extracted≠confirmed 守住；M3 真实语义未证明，不能保证计划不被抽成事实 |
| `GR-05` 作者关键决定权 | M5 AUTHOR-only 守住；高影响单签分类还没落实 |
| `GR-06` 批次失败无半套 | M2～M5 工作区较强；M1 可见状态原子，immutable orphan 只属清理问题 |
| `GR-07` 旧版不冒充 current | M2/M3/M5/M6 基础读较强；M1 首次 C11 owner 断裂，M4 revision migration 未完成 |
| `GR-08` 作者隔离 | AuthorWorkspace 路线较强；本地文件适配器仍依赖受信任 CLI 假设 |
| `GR-09` 改判可追溯 | M5 operation/version/receipt 较强；下游 RE stale 在新工作区未闭合 |
| `GR-10` 覆盖透明 | M1 loss receipt、M2 coverage、M6 excluded counts 有基础；M3 语义覆盖、M4 source coverage ledger 未建 |

---
## 7. 真实异常场景清单

“当前可能行为”只写代码与直接测试能支持的最窄判断；没有对应 fixture 的地方标“材料不足”，不靠想象补齐。

### M1｜上传、识别、分流、材料进入系统

| # | 用户输入 | 预期行为 | 当前可能行为 | 怎样判定进步 | 所需最小材料 |
|---:|---|---|---|---|---|
| 1 | 同一批上传 UTF-8 TXT、GB18030 MD、DOCX、含三种成员的 ZIP | 四种格式走同一对象核心；每份原始 bytes/SHA/来源链可追；任一终端失败整批强停 | **大体符合**。四格式对象入口、严格解码、DOCX 主文档流、ZIP 终端展开和检查小票有直接测试；不写 C10/C1/真值。〔`02_current_route/tests/test_novel_mvp_upload_inspect_tool.py:test_four_supported_formats_return_safe_inspection_without_truth_writes`〕 | 同一内容四封装得到逐字等价终端文本；坏 DOCX/ZIP 前后 workspace visible state 不变 | 一份三章结构文本的四种封装；每段唯一首尾标记；一份带 DOCX 未覆盖区反例 |
| 2 | 空文件、坏编码、`__MACOSX`、`.DS_Store`、两/三层 ZIP、CRC 损坏、单成员超 8MB、总解压超 32MB | 明确区分保留、显式丢弃、警告、阻断；无静默损失 | **大部分符合**。known junk 可见但不遮住有效终端；嵌套>2、文件数>200、单件/总量超限、坏容器、空终端会阻断；水印候选识别材料不足 | 每类脏点都有固定 receipt code；混合包中所有成员处置数与预标注一致；阻断后零可见提交 | 每个脏点一包＋一个混合包；预标 expected keep/drop/warn/block |
| 3 | 一个文件分别含 1／3／10／20 章；另一个 ZIP 每章一文件 | 系统识别真实章数和顺序；20 章先说明规模与普通分批/整本路线；不静默只取前几章 | **局部有、产品路线未证明**。声明式 Chapter spans 可逐项处理；文件名可辅助跨文件章序；没有直接 20 章路线测试，也没有 `20+` 预估/选择输出 | 四规模版本章数、顺序、每章字符覆盖 100%；20 章必须先返回路线选择或明确“本工具只做检查、未进入章节主线” | 模板生成 1/3/10/20 章单 TXT＋20 文件 ZIP；每章唯一标记、期望 SHA |
| 4 | 缺第 2 章、重复章号、乱序、同标题两章、文件名“第2章”而正文标题“第五章”、一句话短章、只有标题空章 | 写入前说清异常；重复显示名不覆盖稳定 ID；短章保留，空章阻断；不自动补章或重排 | **当前批次有较多机械检查**。章号连续/重复/顺序与文件名-正文单候选冲突可阻断；短非空终端保留；空终端阻断。跨“项目已有章＋本次追加”全局缺章材料不足 | 每个异常单变量；阻断前后 M1 visible keys SHA 不变；短章逐字保留并给 warning | 七个单异常包＋先存 c01 后追加 c03 的项目态 fixture |
| 5 | 简介、标签、设定、章节、大纲混在一个 ZIP；另有一段身份模糊 | 明确材料进入各自架；拿不准保持 Unknown；只有 Chapter 可进入 C11/C1；其他不能冒充已发生事实 | **显式声明可运输，自动六架不成立**。C10 current roles 不完全覆盖六架，OUTLINE 迁移仍开；无声明材料保持 Unknown 是安全的 | 显式声明版 100% 分流；无声明疑难件不硬猜；只有作者确认的 Chapter spans 能进入首次准入 bundle | 六类短材料＋一个模糊件；声明版/无声明版各一套；人工期望表 |
| 6 | 只有三章裸书稿，没有书名、类型、主角、金手指 | 正文不得丢；可产生“推断待确认”的元数据候选，最多问 1～3 个必要问题；推断不进事实 | **正文可保留，自动元数据未实现**。当前会是 Unknown/Chapter 声明运输，不会推书名/类型/主角 | 真实三题材前 3 章上，候选命中与“推断身份”分开评分；提问≤3；任何候选不得自动写正式身份 | 权利清楚的 3 本前三章，剥离元数据；人工候选答案与可接受 unknown |
| 7 | CSV 每行一章、XLSX 人物设定表、章节与设定混合表 | 支持就逐字读并分流；不支持就明确格式、原因和转换办法，不静默丢 | **generic unsupported**。`.csv/.xlsx` 不在 `_format()` 支持集合，阻断文案只说支持 TXT/MD/DOCX/ZIP；没有格式专属转换指引 | 近期最小进步不是实现 parser，而是返回 `UNSUPPORTED_CSV/XLSX`＋“导出 UTF-8 CSV/TXT 或 DOCX”的确定说明；原文件保持 | 一个小 CSV、一个 XLSX、一个混合表；预期只验拒绝码/人话，不验表格解析 |
| 8 | 本地输入和输出同一路径、硬链接/软链接别名；输入文件自身是指向根外文件的软链接 | 输出绝不能覆盖输入；不可信路径不能越界读取 | **输出别名防护强；根输入软链接会跟随**。核心对象不接路径；本地适配器受信任假设下 `is_file/read_bytes`。〔`upload_inspect_tool` 别名测试；HR-01〕 | 为根输入软链接补明示策略：拒绝，或在 README/CLI 边界写死“只接受信任路径”并有测试；输出别名继续全拒 | 根内普通文件、根内→根外软链接、硬链接输出、相对/绝对同文件四例 |
| 9 | 第一次已保存一批 raw uploads；第二次写入时发生版本冲突、替换失败或进程中断；随后重启 | 旧 visible state 完整可读；新批不得半可见；重放同 operation 不重复 | **符合可见原子性**。manifest/module_state 同版本；version conflict 保旧；operation replay；read watermark drift 强停。immutable orphan 可能存在但不可见 | 故障注入点覆盖 immutable 前/后与 final commit；重启只看到旧套或新套；另给 orphan 扫描回执但不影响业务 | 两批 2 文件上传；每个阶段故障注入；提交前后 visible SHA 与 blob 列表 |
| 10 | 作者 A 与 B 使用同名项目；A 改了章节 r2，旧 r1 上传/投影再次出现 | A/B 完全隔离；旧 r1 不能冒充 current；M1 能把首次章版本交给 M2 | **隔离成立，版本交接断裂**。raw M1 state 绑定 AuthorWorkspace；C1 workspace 也隔离；但 raw→C11/C1 owner 缺失，调用方可手拼旧 current view | 只有 M1 首次准入 writer 能生成 C11 r1/current；后续更新必须 expected current ref；跨作者句柄全部拒绝 | 两 author handles、同 project slug、同一章 r1/r2；C11/C1 预期 bundle 与 stale 反例 |

### M2｜章节切成责任段

| # | 用户输入 | 预期行为 | 当前可能行为 | 怎样判定进步 | 所需最小材料 |
|---:|---|---|---|---|---|
| 1 | 80～200 字极短章 | 至少一个非空责任段；正文与 revision ref 完整；不硬凑多个段 | **符合**。合法短章可单段，空白章拒绝。〔`02_current_route/tests/test_novel_mvp_segment_tool.py:test_render_accepts_legal_one_segment_short_chapter_and_rejects_empty_c2`、`02_current_route/tests/test_novel_mvp_segment_tool.py:test_blank_chapter_cannot_become_a_legal_zero_segment_batch`〕 | C2 仅 1 段，coverage 100%，halo 合法，重跑字节一致 | 80/120/200 字三章，包含换行与无换行版 |
| 2 | 5000～20000 字且只有一个自然段 | 不切断自然段；但必须明确 oversize，必要时按调用策略阻断，不让 M3 无感吞超限 | **整段保留并计 oversize，不阻断** | 增加显式 `oversize_policy` 或独立 preflight：allow 时 receipt 显眼，block 时零 C2；默认不做语义拆句 | 5k、20k 单段；固定 max=923；预期 allow/block 两例 |
| 3 | 多段章最后只剩 20～100 字碎尾 | 不产生莫名空段；尾部要么独立保留，要么完整并回上一段；覆盖不变 | **符合**。短于 `lo//2` 的尾段并回上一段；逐字重组门会抓丢失/重复 | 不同 lo 下行为固定并在 receipt 说明“尾段并回”；无语义文本也可验 | 3 组段长恰好落在阈值两侧的合成章 |
| 4 | 同字数的对白密集、设定条目密集、长描写稀疏章 | 先保证机械覆盖；是否换档必须有收益证据和参数回执 | **固定参数机械可用；不自适应** | 三类材料在同一 provider/冻结响应下比较漏抽、重复与成本；只有预注册收益过门才保留自适应 | 三个同字数合成章＋不可拆段/跨段依赖标注 |
| 5 | 一件事跨切段边界：主语在前段、动作在责任段、结果在后段 | halo 帮理解；新事实证据只能在责任段；不能因重复 halo 双抽 | **M2 halo 机械正确；语义结果材料不足**。人读图明确只读，M3 非空 quote 门只看责任段 | 12 个跨界骨架上比较无 halo/窄 halo/宽 halo；零 halo-only 事实、重复率不升 | 12 个跨边界合成事件，标合法归属段和允许事实 |
| 6 | 1/3/10/20 章批次里第二章 revision SHA 错或同 chapter 两个 revision | 整批拒绝，第一章不得留下 C2；不替调用方选择哪版 current | **符合**。全批先验；duplicate ref、same chapter two revisions、第二章 coverage failure 均不提交 | workspace `segments` version/SHA 前后不变；错误必须在 provider/M3 之前暴露 | 20 章合法批＋第 2 章 SHA 错／重复 revision 两个反例 |
| 7 | halo 包含邻段的重要句，责任段本身没有这句 | 人读出口必须清楚区分；下游不得把 halo 当责任正文 | **符合机械展示**。C2 item 字段分开；render 写明只读；M3 prompt/quote 门也写了边界 | 构造 provider 故意引用 halo，M3 必须整批拒绝；空 quote 同时要拒绝 | 两段短文，halo 特有标记；一个坏 frozen response |
| 8 | 80 章批量切段并在读取过程中更新 chapter_index | 每章 receipt 完整有序、零模型调用；上游变化整批不提交；耗时可复测 | **receipt/source-race 成立，性能数字未提供**。80 章直接测试只验完整有序稳定 | 固定机器连续 3 次，登记耗时、峰值内存、每章段数、oversize；水位变化必须零写 | 80 章结构化 C1；其中短章/超长单段/普通章各若干；故障钩子 |

### M3｜责任段到事实候选

| # | 用户输入 | 预期行为 | 当前可能行为 | 怎样判定进步 | 所需最小材料 |
|---:|---|---|---|---|---|
| 1 | provider 少一段响应、额外返回未知 item key、同一 key 重复 | response key 集必须与 current C2 完全一致；整批停；不消费旧/未知响应 | **工作区符合**。missing/extra/tampered key 在 provider 前拒绝；对象工具 missing item 整批拒绝。额外 mapping 在 standalone offline provider 是否被显式拒绝需与工作区统一 | 对象、文件、workspace 三入口对同一 extra/missing key 得到同一错误码和零 C3 写 | 3 个 C2 item，少一、多一、重复三套 response mapping |
| 2 | provider 返回旧 revision、未知 chapter、malformed revision ref | provider 不应被调用或结果整批拒绝；旧 C3 保留 | **符合**。C2/current ref mismatch 在 provider 前拒绝；stored response identity 也复验 | mock provider 调用计数必须 0；workspace 旧 version/SHA 不变 | 同章 r1/r2 两套 C2，current 指向 r2；一个坏 ref |
| 3 | 顶层坏 JSON、`data` 缺失、`facts` 非列表、fact 少字段/多字段/额外字段 | 不修复、不静默丢；最多按明确规则重试；失败停在可重跑位置 | **冻结工具严格；实时 parser 不严格** | 所有入口共享一个 exact validator；每种损坏固定错误码；任何坏 fact 使本段/整批失败，不被 filter 掉 | 8 种单字段 mutation；实时 provider stub 与 frozen provider 各跑一遍 |
| 4 | 模型输出因 token 上限截断 | 明确标 `incomplete` 或整段失败；允许一次重试但不能把剩余事实静默舍弃 | **会触发重试，并指令“前25条，其余舍弃”** | 去掉“舍弃成功”；retry 后若仍不完整则 C3 不提交，并返回 segment-level incomplete receipt | 人工 stub 第一次抛 `TruncatedOutput`，第二次 25 条合法 JSON；期望仍标不完整/失败 |
| 5 | 一个责任段零候选；整章所有段都零候选 | 合法返回空，不编事实；最好区分“确实无可抽”与“低密度/材料不足” | **零候选运输成立**，工作区 exact key 全零可保存；没有原因分类 | C3 receipt 增加每段 candidate_count 与 provider completion identity；语义原因先不拍，只允许 `zero_candidates` | 一段纯氛围负控＋一章 3 段全零 frozen response |
| 6 | 一个段突然 250 条候选 | 先诊断真密/重复/灌水；不能照单全收，也不能只留前25条不说明 | **当前可能全收；若截断则可能舍弃其余** | 先做纯机械密度回执：count、平均 quote 长度、重复 text/quote 计数、truncated 标志；不自动删 | 250 条中含 80 exact duplicate、40 near duplicate、130 unique 的合成 response |
| 7 | fact 的 quote 在 halo、不在责任段；或 quote 为空 | 必须拒绝；每条候选都要有非空责任段逐字证据 | **halo quote 拒绝；空 quote 可过 M3** | 把 provider quote 条件改为非空；对象/文件/workspace 全部加空 quote 反例；M3→M4 正例必须可直接交接 | 一个 halo-only quote、一个 empty quote、一个责任段内 quote |
| 8 | quote 在责任段里，但 fact text 把“他打算去”写成“他已经去了” | 机械字面门不能冒充语义正确；要单独评计划/猜测/比喻/表述事件 | **材料不足**。Prompt 有规则，冻结 response 测试无法证明模型遵守 | 权利清楚的真实责任段建立事实性、限定、来源支持标签；报告 precision/recall/危险错误，不压单分 | 30～50 个真实责任段，含计划、梦境、传闻、比喻、对话谎言、客观变化 |
| 9 | 多章抽取过程中 C2 或 chapter_index 水位改变 | 整批结果丢弃；旧 C3 不隐藏；重跑可恢复 | **符合离线工作区**。source change during extraction 零 commit，失败 rerun 不覆盖 prior state | 同一故障在未来 live provider 路径也必须成立；调用费用发生与否单独回执，不影响业务原子性 | 3 章 C2＋在第二段 provider 返回后改变 index 的故障钩子 |
| 10 | 一章只有十几句可抽，另一章设定密集且 100+ 条 | 不按统一密度硬凑或硬砍；说明覆盖和不确定性 | **只有 candidate count，没有低/高密度解释** | 先做客观 receipt，不急着拍阈值：段数、零段数、候选数、截断、重复、未处理段；阈值由真实评测后决定 | 一稀一密两章真实/合成材料；人工标应保事实数与允许 unknown |

### M4｜候选进入事实快照

| # | 用户输入 | 预期行为 | 当前可能行为 | 怎样判定进步 | 所需最小材料 |
|---:|---|---|---|---|---|
| 1 | 两章 C3，带 chapter/revision/seg/quote；quote 中含规范化换行差异 | 多章编号、revision、raw anchor、quote SHA 全保真；C2 坐标正确映回 C1 raw text | **符合机械链**。直接测试覆盖多章顺序/ID/ref/anchor 与规范化→raw 映射 | 每条 `raw_text[start:end]==quote`，slice SHA 一致；重启字节稳定 | 两章含空行/缩进/重复短语；每条 quote 唯一的正例 |
| 2 | 第二章一条 quote 不存在或多次出现，第一章全合法 | 整批不入 facts，旧输出保留 | **符合**。对象/文件与工作区都有第二章失败不留第一章 | workspace facts version/SHA、文件旧字节、tmp 清理全部对平 | 两章 batch，第二章 missing/ambiguous quote 两个反例 |
| 3 | 既有 confirmed/rejected facts，再加入新 C3 | 旧 ID、状态、作者决定、证据不变；只追加 extracted | **对象/文件符合；工作区不支持第二批** | AuthorWorkspace 增量 writer 读 current facts＋expected watermark，一次 commit；重复 operation replay | 一份含 confirmed/rejected 的 C4＋一章新 C3；同 operation 重跑 |
| 4 | 两条 exact duplicate、三条相似、两条互相冲突的候选 | 不能静默删；应分组并让作者看见关系；事实身份仍 extracted | **全部独立入账，无 grouping** | 最小进步只产 `candidate_group_receipt` 或旁挂 group IDs，不改 fact text/status；exact/near/conflict 分开 | 人工构造 7 条候选及期望 group；不要求模型判冲突 |
| 5 | 一章 250 条机械合法候选 | 每条证据核验，全批原子；同时避免把噪音直接变 250 个审查动作 | **会全入 extracted**，M5 能分页但负担转嫁 | 在 M4 前/旁增加纯机械重复与密度小票；是否拦截、合并或抽样须 CZ/实测后决定 | 250 条合成 C3，含重复比例、quote 覆盖与 unique anchors |
| 6 | 当前章从 r1 改成 r2：quote 原样唯一存在、位置移动；另有 quote 消失/多义 | unique move 可迁移；消失进入 needs_recheck/evidence_gone；多义待人工；旧历史保留 | **读 current view 只把 r1 fact 列 stale，不做迁移写入** | 先实现只读 effect preview，输出 `unique/missing/ambiguous`，零事实写；正式 writer另票 | r1/r2 三组：位置移动、删除、重复出现；预期 effect 表 |
| 7 | facts 已有 version 1，第二次执行 `materialize_current_extracted_snapshot()` | 正常增量，不应把“已有账”当冲突异常；失败保留 version 1 | **固定 expected_version=0，第二次必冲突** | 新增单用途 `append_current_extracted_batch`，要求 expected facts version/SHA；旧首建函数不改语义 | 初始 C4＋第二批 C3；stale expected version 反例 |
| 8 | 来源分别是书稿证据、作者签字、AI 推断、未来计划 | 身份分开；只有书稿 C3 可走本 M4；其他不能靠 source 字符串冒充 | **source 只是非空字符串，当前路线实质只承接书稿候选** | 输入 schema/adapter 明确限制本票 `source_kind=PROSE_EVIDENCE`，或保持现合同并在边界文档强停；不要顺手发明四类总表 | 四种来源声明的最小对象；只允许书稿例通过 |
| 9 | 作者 A/B 同名章；物化期间上游 C3 改变 | 不串作者；source race 零 facts write | **符合**。绑定 handle、跨作者 guess 拒绝、前后 upstream identity 复验 | 保持现有测试，并把第二批增量 writer纳入相同隔离/水位门 | 两 author workspace＋同 project slug；物化中改 candidate state |

### M5｜作者查看证据并确认、驳回或改写

| # | 用户输入 | 预期行为 | 当前可能行为 | 怎样判定进步 | 所需最小材料 |
|---:|---|---|---|---|---|
| 1 | 当前章 250 条 extracted 候选，page_size=25 | 10 页无漏无重，顺序稳定；不保存 UI 游标；每页只读 | **符合**。直接测试 250 条分页、尾页/空页与零写 | 再加跨进程重开第 6 页和页面摘要；总 fact IDs 与原序完全一致 | 250 条同 revision facts，唯一 IDs/quotes |
| 2 | 作者看完第 1 页后，另一个动作改变 facts version，再请求第 2 页 | 明确提示“审查内容已变化，请重开”，不能静默混新旧页 | **动作提交会因旧 page watermark 拒绝；翻页本身会读最新 snapshot** | page API 接收 expected session watermark；任意非本会话变化均拒绝翻页；自己上一页成功动作则返回新 session token | 50 条 facts；外部改第 30 条/插入新条；旧 cursor 请求 |
| 3 | 作者只勾选两条 confirm，其余 248 条不处理 | 只改两条；其余状态、顺序、文本、证据完全不变 | **符合**。`test_selecting_only_one_page_item_leaves_other_items_pending` 与 batch tests | 扩到两条跨页选择仍必须显式，不能“全选本章”默认带走隐藏项 | 250 条 facts＋两条 decision rows；前后逐 ID diff |
| 4 | confirm/reject/edit/edit_and_confirm，动作带 stale fact SHA 或 revision ref | 每个动作绑定作者看到的证据与版本；stale 整批拒绝 | **机械符合**。expected status/ref/fact binding/facts watermark 齐全 | 人读 page 上显示与 action 中复用的 hash/ref 可回验；错误码区分哪一水位 stale | 四种动作各一正例；fact SHA/ref/version 三类 stale |
| 5 | 批次第二条动作不合法或指向重复 fact_ref | 第一条不得落盘；重复目标不允许 | **符合**。第二条 stale/shape error、重复 target 在单次 execute 前阻断 | workspace commit 调用计数 0；旧 facts version/SHA 不变 | 两动作 batch，第二条坏；duplicate fact_ref batch |
| 6 | 相同 operation_id 重放；同 operation_id 改 payload；竞争进程同时改同一事实 | 完全相同重放不加版本；改 payload 冲突；竞争不能都提交 | **符合工作区单 logical key**。legacy 跨文件事务也有竞争/恢复测试 | 新的跨页 session/增量链仍复用同一 operation receipt 语义 | 相同与改变 payload 两组；两个并发 process |
| 7 | 作者先 confirm，后改口 reject 或改写，再回看历史 | 新决定生效，旧决定可追；靠旧决定的下游标 stale | **事实版本/receipt 可追；下游 stale 在 AuthorWorkspace 未闭合** | 查询一个 fact 的 decision history 能看每次 operation；RE/actual support 同事务失效另有 owner 票 | 单 fact 三次动作；一个引用它的 RE fixture；故障注入 |
| 8 | 本章含“死亡”“复活”“秘密揭示”等高影响项，另有普通项；作者尝试批量确认 | 高影响项必须单独签；普通项可批量；不存在危险全书一键确认 | **没有高影响分类；但 batch 只允许同 revision，当前也没有全书一键入口** | 先做只读风险标注/fixture，正式哪些类型强单签需 CZ；不能由关键词偷偷决定真值 | 10 条事实含 4 类高影响语义；人工 risk 标签；批量动作反例 |
| 9 | 作者把“张三拿起钥匙”编辑成“张三偷走了钥匙并嫁祸李四”并 `edit_and_confirm` | 必须明确旧 quote 是否仍托住新主张；不能只因作者点确认就假装书稿证据没变 | **当前会沿用旧 quote/anchor 并确认新文本** | 在 CZ 决定来源语义前，只能增加 warning/preview，不改真值规则；若要求书稿托住，则 edit_and_confirm 进入 needs_recheck 或要求新 AUTHOR_ATTESTATION | 一条短 quote＋三种改写：同义、轻扩展、完全新增主张；人工支持等级 |

### M6｜查询当前已确认事实与证据

| # | 用户输入 | 预期行为 | 当前可能行为 | 怎样判定进步 | 所需最小材料 |
|---:|---|---|---|---|---|
| 1 | facts 同时含 current confirmed、current extracted、rejected、needs_recheck、旧 revision confirmed、坏 anchor | 只返回 current confirmed+VERIFIED+recheck=null；其余逐类计数 | **符合基础查询**。直接测试覆盖主要状态与旧版 | 加一份统一 7 类门禁 fixture，确保对象/文件/workspace/as-of 同口径 | 7～10 条 C4，每类一条，统一关键词 |
| 2 | 查询词无命中，或只有 extracted/rejected 中含关键词 | 返回空 matches/evidence；说明证据门内未命中，不编答案 | **符合**。`keyword_miss` 与各排除原因可见；人读 render 不下故事结论 | 文案固定包含“当前证据范围内”；不把排除项数量写成“事实不存在” | 一份 eligible keyword miss＋一份 only-rejected hit |
| 3 | 命中两条事实 | 展示 fact text、quote、anchor start/end、revision、source，并说明排除计数/范围 | **符合证据闭合**。缺更完整“未读材料”receipt | 增加可展开 coverage：chapter_index 水位、as-of cutoff、未读未来章数；不复制正文 | 两条 current facts＋三条被排除 facts |
| 4 | 截至 c05 查询；c06 有秘密事实、证据 quote 和正文；事实文本与 c04 相同关键词 | c06 fact/ref/body/quote 均不可见，连身份也不泄漏 | **符合对象与工作区 as-of/context 测试** | 对输出 JSON 做 key/value leak scan；未来 fact ID/chapter ID/quote 均不出现 | c04/c05/c06 三章；c04 与 c06 都命中同词；秘密标记 |
| 5 | chapter IDs 为 `c01,c04,c09`，截至 c04 | 按 `chapter_index` 顺序而非数字连续性判断 | **符合**。对象和工作区均有非连续 ID 测试 | 追加显示 cutoff 的 ordinal index，避免用户误以为按数字大小 | 非连续三章 index＋对应 facts |
| 6 | 需要展开命中 quote 前后 80 字；facts 中还保留另章旧 revision 历史 | 当前命中上下文必须来自同 revision C1；旧事实应排除并计数，不应拖死全部查询 | **raw context closure 符合；存在 stale 全局拒绝断点** | 修改 context/reader workspace：只验证 eligible current facts anchor；旧版历史交给 ask 门排除，仍计 `stale_revision` | 一章 current fact＋另一章 stale fact＋current C1；上下文正例 |
| 7 | “霍野跟沈星挽现在什么关系”“他俩后来闹翻了吗”“小挽知道钥匙在哪吗” | 理解别名、指代、关系方向和当前/as-of 范围；答案仍带证据，不补故事 | **未实现**。整句/空格词必须字面全出现；返回匹配事实列表，不综合回答 | 先做只读 entity/alias query plan，输出 resolved terms＋候选 facts；语义回答另过 evidence support；无实体时明确澄清/unknown | 30 个中文大白话问题，带角色别名表和人工期望事实集合 |
| 8 | 作者 A/B 同名项目和人物；调用方传 path 或猜 project ID | 只能读绑定 handle；不跨作者/项目；path 不能冒充 workspace | **符合**。所有工作区入口公开签名无 identity/path，跨作者 guess 测试齐全 | 后续语义层只能消费 M6 已过滤结果，不得自己接数据库/path 绕过 | 两 author handles，同项目名/人物名；非法 path/handle |
| 9 | 查询期间 facts、chapter_index 或 chapters 任一水位改变 | 丢弃整次结果；不返回混合快照；查询不写任何业务状态 | **符合**。基础两水位、context 三水位、reader combined source change 都有测试 | stale-compatible 修复后继续保持水位门；不能为了容忍历史旧 fact 放松 source race | 查询中变更 facts/index/chapters 三个独立故障钩子 |

---
## 8. 下一批最小候选施工票（按优先顺序）

这些票都只增加一个可独立验收的能力。它们不要求统一平台、不改 R13、不决定开放语义，也不把局部 PASS 写成模块完成。

### T01｜M1｜首次章节准入 bundle 编译器（只读、不落盘）

- **所属模块**：M1
- **用户问题**：作者已经明确说“这几个 span 是章节”，但当前只能手拼 C10/C11/C1，容易错 revision、SHA 或章序。
- **输入**：一批已持久化 `UploadSource` 的 terminal text refs；作者确认的 `role=CHAPTER` spans；调用方显式提供的 stable `chapter_id`、显示章号和顺序；不接受自动推断。
- **输出**：一个纯对象 `initial_chapter_admission_bundle`，内含 C10 origin、C11 r1 candidates、C1 v1 current views、chapter_index 和全套 SHA/坐标；**只预览，不写 AuthorWorkspace**。
- **缺口依据**：`chapter_workspace.py:1-5` 明确不创建 C11；总控简报列 C10 origin、chapter number owner、C11 writer、协调器四缺口。
- **建议最小写集**：新增一个 M1 纯对象模块及测试；复用现有 C10/C11/C1 validators，不改它们；不碰 M2～M6。
- **正常例**：三章 TXT，作者确认三个 span，调用方给 `c01/c02/c03`；输出三条 C11 r1 与同 ref C1 current，逐字 SHA 对齐。
- **失败例**：两个 span 共用同一 `chapter_id`，或 span SHA 与 terminal text 不符；整个 bundle 拒绝，零文件写入。
- **完成后多出的真实能力**：M1 能把“作者已确认的章节边界”机械编译成下一站可校验的正式对象，不再要求普通调用方逐字段手拼。
- **停下来问 CZ 的条件**：调用方没有唯一 chapter ID/显示章号；希望程序自动判断章节、补缺章或决定文件名/正文标题谁赢；希望顺便推书名/类型/主角。
- **依赖关系**：无；T02 依赖本票输出。

### T02｜M1｜C11 r1＋C1 current 的首次原子提交器

- **所属模块**：M1
- **用户问题**：T01 即使能产合法 bundle，当前 AuthorWorkspace 没有 C11 runtime writer；首次入章仍不能重启后确认 current。
- **输入**：T01 已验证 bundle、`operation_id`、C11/C1 相关 logical keys 的 expected versions（首次均为 0）。
- **输出**：一次 AuthorWorkspace commit 的 receipt；重启后可读 C11 r1 ledger、C1 current views 与 chapter_index，三者水位闭合。
- **缺口依据**：当前 `workspace.py` logical key 集没有明确 C11 runtime owner；`chapter_workspace.persist_c1_current_views()` 只写 `chapters + chapter_index`，不写 revision ledger。
- **建议最小写集**：AuthorWorkspace logical key allowlist 的一个 C11 键；一个 M1 初始 writer；对应恢复/重放/作者隔离测试。不要改现有 C11 Schema 语义。
- **正常例**：空项目首次提交三章；一次 commit 后所有 visible keys 同一 generation，重启 byte-equivalent。
- **失败例**：C11 写前已存在 version 1，或第 2 章 C1 SHA 错；整批零 visible write，旧项目不变。
- **完成后多出的真实能力**：`上传材料 → C11 r1/current → C1 v1 current → M2` 的首次机械边真正接上。
- **停下来问 CZ 的条件**：C11 是独立 logical key 还是嵌入 chapters 尚未冻结；stable chapter ID/显示章号 owner 未明确；需要同时改旧 legacy store；要求支持 replace/restore 而不只是 INITIAL。
- **依赖关系**：依赖 T01；不依赖 M2 改动。

### T03｜M4｜既有 facts 上追加一批 EXTRACTED 的工作区入口

- **所属模块**：M4
- **用户问题**：第一批事实候选能入账，第二章/下一批正常抽取却因 `expected_version=0` 冲突，事实账不能连续使用。
- **输入**：current C1/C2/C3、本次 `operation_id`、调用方看到的 facts `expected_version + expected_sha256`。
- **输出**：保留既有 facts 原顺序、ID、status、decision/evidence，只追加本批新 `extracted` 的新 C4 snapshot 与 receipt。
- **缺口依据**：`fact_workspace.materialize_current_extracted_snapshot()` 从空 snapshot 开始并固定 `expected_version=0`；对象 `fact_tool` 已证明 `existing_c4` 可保留 confirmed/rejected。
- **建议最小写集**：在 `fact_workspace.py` 新增单用途 append 函数；复用 `fact_tool.execute_batch(existing_c4=...)` 与 `save_snapshot()`；加 version/SHA、重放、第二章坏候选、source race 测试。
- **正常例**：facts v1 有一条 confirmed、一条 rejected；追加两章三条 C3，得到 v2，旧两条逐字不变、新三条 extracted。
- **失败例**：expected SHA stale 或第二章 quote 无法锚定；facts 仍保持 v1，一个新 fact 都不可见。
- **完成后多出的真实能力**：M4 从“一次性建第一份快照”升级为可连续接批的独立小工具。
- **停下来问 CZ 的条件**：要求本票同时做去重、冲突分组、revision migration 或改旧 fact IDs；这些必须拆票。
- **依赖关系**：无；可与 T01/T02 并行。

### T04｜M3｜真实 provider 与冻结 provider 共用 exact 解析边界

- **所属模块**：M3
- **用户问题**：冻结工具会拒绝坏字段，真实 `extract.py` 却可能静默过滤坏 fact；同一模型响应在两条入口身份不同。
- **输入**：`call_json()` 返回对象或 frozen response，统一要求 exact `{data:{facts:[{text,quote}]},usage,model}`；quote 非空。
- **输出**：合法时同字节 C3 candidates；任一缺/多字段、空 quote、非对象 fact、空 text 都给明确错误并使整批失败。
- **缺口依据**：`extract_tool._validate_provider_result()` 严格；`extract.parse_fact_call_result()` 在 220～224 行静默 filter，且把缺 quote 变空；`_validate_c3_candidate()` 对空 quote 不检查。
- **建议最小写集**：抽出一个共享 validator/parser，令 `extract.py` 与 `extract_tool.py` 调同一函数；补空 quote 和 extra field 反例；不改 prompt、不换模型。
- **正常例**：两个 C2 item 的 live stub 与 frozen mapping 返回同一合法 response，输出 C3 字节等价。
- **失败例**：第二条 fact 多 `confidence` 字段或 quote 为空；整个 batch 拒绝，旧 C3 保留。
- **完成后多出的真实能力**：M3 的“运输成功”在离线和未来真实 provider 上含义一致，输出可直接交给 M4。
- **停下来问 CZ 的条件**：希望允许 provider extra metadata、自动 trim/修复或部分接收坏 batch；这会改变合同边界。
- **依赖关系**：无；T05 建议在本票之后。

### T05｜M3｜截断与高密度段的显式 incomplete 回执

- **所属模块**：M3
- **用户问题**：高密度段被截断后，当前重试指令会“只留前25条、其余舍弃”，作者和下游看不见覆盖损失。
- **输入**：单个 C2 item、provider 第一次 `TruncatedOutput`、按现有规则最多一次重试的第二响应。
- **输出**：成功完整则正常 C3；任何曾截断且无法证明完整时，返回/保存 `segment_incomplete` 失败回执，**不提交本段或整批 C3**；不保存前25条当完整结果。
- **缺口依据**：`extract.py:35-40` 明写“其余舍弃”；C3 当前没有 coverage/incomplete 身份。
- **建议最小写集**：M3 运行 receipt/错误类型与测试；删除“舍弃后算成功”的控制流。不要在此票设计 200 条如何筛选。
- **正常例**：第一次截断，第二次在更高 token 上返回完整合法 JSON；receipt 记录 `retry_count=1`，C3 正常提交。
- **失败例**：第二次只返回25条或再次截断；整批停在可重跑位置，旧 C3 不变，并列出受影响 item key。
- **完成后多出的真实能力**：M3 不再静默牺牲覆盖来换合法 JSON；高密度失败对作者和后续评测可观测。
- **停下来问 CZ 的条件**：要不要允许部分候选进入临时区、是否提高 token/增加费用、何时拆段；这些涉及额度与产品策略。
- **依赖关系**：建议依赖 T04 的统一 parser。

### T06｜M6｜带旧版本历史时仍可查询 current 的上下文与防剧透入口

- **所属模块**：M6
- **用户问题**：改过任一章后，facts 会保留旧 revision 历史；基础查询能排除它，但 context/as-of workspace 会因一条 stale fact 整体拒绝。
- **输入**：混合 current＋stale C4、current chapter_index/C1、query、可选 cutoff/context window。
- **输出**：只对 eligible current facts 做 anchor/context/as-of；旧 facts 进入 `stale_revision` 排除计数，不出现在 matches/evidence/body；三水位仍严格闭合。
- **缺口依据**：`ask_tool.execute()` 已按条排除 stale；`ask_context_workspace._validate_closed_snapshots()` 与 `ask_reader_scope_workspace._validate_pair()` 当前全局拒绝。
- **建议最小写集**：只改 M6 两个 workspace validator/组合入口与相关测试；复用 `ask_tool` eligibility；不改 C4 writer。
- **正常例**：c01 r1 stale history＋c01 r2 current confirmed，查询 r2 命中并展开上下文，excluded_counts.stale_revision=1。
- **失败例**：current eligible fact 的 anchor 在 current C1 中损坏，或查询期间水位改变；整次仍失败关闭。
- **完成后多出的真实能力**：作者改过章节后，M6 的证据上下文和截至章读取仍能作为独立工具使用，而不丢历史也不泄漏旧版。
- **停下来问 CZ 的条件**：要求自动迁移旧 fact、隐藏排除计数、或允许旧事实作为历史回答；这些不是 M6 current query 的职责。
- **依赖关系**：无；与 T09 revision preview 可并行。

### T07｜M5｜固定水位的跨页审查会话

- **所属模块**：M5
- **用户问题**：作者审 250 条时，翻页期间 facts/index 变化可能让后页来自新快照；旧页动作虽会 stale 拒绝，但作者已读内容混了。
- **输入**：`open_session(chapter_id,page_size)` 返回 session token（facts/index watermarks＋current ref）；后续 `read_page(session,after_fact_ref)`。
- **输出**：同 session 所有页固定同一水位；任意外部变更返回 `SESSION_STALE_REOPEN_REQUIRED`；作者成功提交本页动作后明确返回新 session token/next cursor。
- **缺口依据**：open session 单读 facts/index；page 双读但不接 expected session watermark；现有测试只证明旧页动作 stale 和 processed cursor 可续。
- **建议最小写集**：`review_queue_workspace.py` 的 session/page 对象与测试；不改 review action 合同，不保存 UI cursor。
- **正常例**：250 条按 25 条翻完；作者确认第25条后，用返回的新 token 从该 fact_ref 继续，零漏零重。
- **失败例**：外部插入一条候选后仍用旧 token 请求第2页；拒绝并不返回任何新页内容。
- **完成后多出的真实能力**：M5 真正支持长列表连续审查，而不是每页都悄悄追随最新账。
- **停下来问 CZ 的条件**：希望自动把新候选插入正在审的 session、持久化 UI 游标或跨设备自动合并；这些是体验策略。
- **依赖关系**：无。

### T08｜M2｜超长单段的显式允许／阻断策略

- **所属模块**：M2
- **用户问题**：超长自然段被完整保留是对的，但它可能直接把 M3 输入推到不可用；当前只有 receipt 计数，调用方容易漏看。
- **输入**：现有 C1＋切段 options，新增最小 `oversize_policy=allow|block`，不做语义切句。
- **输出**：allow 时保留完整段并在顶层 receipt 标明 affected chapters/lengths；block 时整批零 C2，返回明确超限列表。
- **缺口依据**：`segment.build_segments()` 保持超长段；`_chapter_coverage_receipt()` 只给 count。
- **建议最小写集**：`segment_tool` option/receipt 与 workspace 参数透传、直接测试；不改 `segment.py` 的自然段保真算法。
- **正常例**：5000 字单段＋allow，得到一段且 `oversize_segment_count=1`、exact length 可见。
- **失败例**：同输入＋block，整批拒绝；已有 `segments` 旧版本不变。
- **完成后多出的真实能力**：M2 的超限行为从“开发者读 receipt 才知道”变成可选择、可失败关闭的独立工具行为。
- **停下来问 CZ 的条件**：默认策略要从 allow 改 block、要自动语义拆句、或要按模型上下文动态阈值；这些需产品/模型预算决定。
- **依赖关系**：无。

### T09｜M4｜章节改稿后的 anchor effect 只读预览

- **所属模块**：M4
- **用户问题**：r1→r2 后，当前只能把旧 fact 全列 stale；不知道证据是唯一移动、消失还是变成多义，无法安全施工正式迁移。
- **输入**：一个旧 C4 fact、old revision ref、新 C1 current text/ref；不接 workspace writer。
- **输出**：`UNIQUE_MOVE / MISSING / AMBIGUOUS / UNCHANGED` effect，列新候选 anchor（若唯一）、旧/new SHA；零 status/真值写入。
- **缺口依据**：C4 合同要求 evidence effect；当前 `read_current_snapshot()` 只分 current/stale；没有迁移分类工具。
- **建议最小写集**：M4 纯函数工具＋文件适配器＋四类 fixture；不改 C11/C4，不自动设 needs_recheck。
- **正常例**：quote 在 r2 唯一出现、位置后移，输出 UNIQUE_MOVE 与新 anchor。
- **失败例**：quote 消失或出现两次，分别输出 MISSING/AMBIGUOUS；绝不猜最近位置。
- **完成后多出的真实能力**：改稿影响从“整条旧版”细化为可审查的机械效果，为正式 migration writer 准备证据。
- **停下来问 CZ 的条件**：要求 UNIQUE_MOVE 自动更新 fact、MISSING 自动选 `needs_recheck` 还是 `evidence_gone`、或跨 C11/RE 同事务；这些需正式语义与 owner。
- **依赖关系**：无；后续正式 writer 依赖本票和 C11 owner。

### T10｜M4｜候选密度与 exact duplicate 的只读小票

- **所属模块**：M4
- **用户问题**：两三百条候选机械合法就全部入 extracted，作者审查负担不可见；但贸然自动删又会丢事实。
- **输入**：本批 C3 candidates（物化前或物化结果），只做机械统计。
- **输出**：每章 candidate count、exact duplicate text/quote groups、重复占比、唯一 anchor count、超阈值标记；不删、不合并、不改 status。
- **缺口依据**：M4-B03 要求相似/重复/冲突分组不静默删；当前完全无 grouping。先做 exact 机械层最安全。
- **建议最小写集**：M4 sidecar receipt 纯函数与 render；只覆盖 exact duplicate，不做 embedding/LLM near duplicate/conflict。
- **正常例**：250 条里 80 条 exact 重复，receipt 列出组与成员 IDs，C4 仍保留全部候选。
- **失败例**：同 fact/candidate ID 重复或输入 shape 损坏；receipt 失败，不影响 facts 现状。
- **完成后多出的真实能力**：作者/施工者能看见高密度到底是“真多”还是机械重复，且没有自动删事实风险。
- **停下来问 CZ 的条件**：要求自动合并、相似度阈值、冲突语义判断或章级阻断线；这些需真实数据和作者负担实验。
- **依赖关系**：可与 T03 并行；不依赖其写入。

### T11｜M1｜CSV/XLSX 的格式专属明确拒绝

- **所属模块**：M1
- **用户问题**：作者上传表格时只得到“只支持四格式”的泛化错误，不知道内容有没有被读、该怎样转换。
- **输入**：`.csv/.xlsx/.xls` UploadSource 或本地适配器对象。
- **输出**：格式专属 block code、`bytes_read=false/content_not_parsed`、明确转换建议；原 raw upload 是否保存由现有 M1 state 规则决定，不生成 terminal text。
- **缺口依据**：`input_router._format()` 没有表格类型，统一 `unsupported_format`；原子 `M1-N01` 允许“读不了就明说并给转换办法”。
- **建议最小写集**：只改格式识别与人读 receipt/render 测试；不引入 pandas/openpyxl、不做表格解析。
- **正常例**：`chapters.xlsx` 返回 `UNSUPPORTED_XLSX`，说明可导出为 TXT/MD/DOCX，零 C10/C1。
- **失败例**：把 ZIP 改扩展名为 `.xlsx`；按 magic/container 策略仍不得伪装成表格成功，必须给一致的容器/格式判断。
- **完成后多出的真实能力**：M1 对 CZ 点名的 Excel/CSV 给出诚实、可操作的当前边界，不再让作者猜“是不是偷偷丢了”。
- **停下来问 CZ 的条件**：要求直接支持每行一章、公式、合并单元格或混合 sheet 分流；那是独立新能力票。
- **依赖关系**：无。

### T12｜M3｜真实责任段最小语义验收切片

- **所属模块**：M3
- **用户问题**：当前所有强通过都可能只是“冻结 response 搬运正确”，无法判断真实抽取是否把计划、传闻、比喻或 halo 当事实。
- **输入**：30～50 个权利清楚的真实 C2 责任段，覆盖零/稀/密、对话谎言、计划、梦境、传闻、限定词、跨边界指代；同一 provider 配置另行获准后运行。
- **输出**：固定 Gold/评审表不在本票自动生成；本票只提供可重复 harness 与分层结果：结构失败、事实 precision/recall、危险错误、quote containment、evidence support、截断/零候选、速度。机械分与人工语义分分开。
- **缺口依据**：R13 明确机械正确与语义正确分开；现役 M3 workspace 测试零模型调用；原子 M3-E02/E03/E05 尚无真实证明。
- **建议最小写集**：独立 M3 evaluation harness、fixture manifest、结果 schema；不改生产 prompt、provider、C3/C4 合同，不污染现有 Gold。
- **正常例**：一个明确客观变化段命中 fact+quote；结构和语义两层都过。
- **失败例**：把“他打算离开”抽成“他已离开”，即使 quote 在段内也记危险语义错误，不能被机械 pass 覆盖。
- **完成后多出的真实能力**：项目终于能回答“这个 M3 不只是能跑，它对真实责任段是否有可用语义能力”，但仍不宣称模型/生产合格。
- **停下来问 CZ 的条件**：需要调用付费 API、修改 Gold、改变模型顺位、扩大真实书稿外发或冻结正式阈值。
- **依赖关系**：建议依赖 T04/T05；执行真实 provider 另需现有权限链。

### 票间并行关系

```text
T01 → T02                         （M1 首次准入）
T04 → T05 → T12                  （M3 解析安全 → 覆盖透明 → 真实语义评）
T03                              （M4 第二批增量，可独立）
T09                              （M4 改稿 effect 预览，可独立）
T10                              （M4 密度小票，可独立）
T06                              （M6 stale-compatible 读侧，可独立）
T07                              （M5 固定分页会话，可独立）
T08                              （M2 oversize 策略，可独立）
T11                              （M1 表格明确拒绝，可独立）
```

建议实际开窗时，优先保证 **T01/T02、T03、T04/T05、T06** 四条线；其余不需要阻塞它们。

---
## 9. 现在不要做的高级但浪费额度的事

1. **不要先造一个“统一 M1～M6 全链编排器”。** 当前最长链的断点不是少一层 orchestrator，而是 M1 没有首次 C11 owner、M4 不能增量、M3 语义未验。大编排只会把手拼字段藏起来。
2. **不要新增 M12／M13，也不要给现有 M1～M6改名重排。** 这轮目标是让独立模块变得可用，不是扩能力图。
3. **不要现在迁 PostgreSQL、Schema registry、消息总线或分布式事务。** AuthorWorkspace 的 JSON＋generation/commit 机制已足够验证局部原子性；先把 owner 和单模块语义接对。
4. **不要把 legacy project store 与 AuthorWorkspace 一次性大合并。** 先用 T01/T02 建一条窄首次准入，旧路线继续只作历史兼容；大迁移会把 C10/C11/C1 的语义问题和存储重构混在一起。
5. **不要在 M1 立即实现完整 Excel/XLSX 解析。** 先做格式专属明确拒绝。表格每行一章、人物设定、混合 sheet 是独立输入产品，需要自己的身份与损失合同。
6. **不要在 M1 顺便自动猜书名、类型、主角、金手指并直接入正式材料。** 这是 `M1-N02` 的推断候选能力，不应卡住首次章节准入，更不能用元数据推断补 C11 owner。
7. **不要为了“智能切段”引入模型语义切窗。** M2 当前机械覆盖很稳；先做 oversize 策略和真实跨边界对照，确认固定自然段策略哪里真失败，再考虑自适应。
8. **不要给 M3 继续堆 prompt 规则来假装解决质量。** 当前最急的是统一 parser、非空 quote、截断不静默丢和真实责任段评测。Prompt 更长不能证明语义更好。
9. **不要做全书级 200～300 条候选的 LLM 自动去重／冲突裁决。** 先做 exact duplicate 与密度小票；相似和冲突的阈值没有真实作者负担证据，自动删更危险。
10. **不要让 M4 在改稿后自动把旧事实“挪到新 anchor”或自动确认。** 先只读 effect preview。`UNIQUE_MOVE` 是否足以迁移、`MISSING` 应写 `needs_recheck` 还是 `evidence_gone`，都涉及正式语义与跨模块事务。
11. **不要在 M5 增加全书一键确认。** 当前按章分页和同 revision batch 是正确安全边界；高密度问题应从上游密度/重复回执和作者负担测量解决，不靠扩大确认半径。
12. **不要用关键词命中把高影响事实自动分类并强签。** 死亡、复活、关系破裂等方向已拍，但机器分类规则和误判代价未冻结；先用人工标 fixture 验证，再问 CZ。
13. **不要把 M5 的作者 `edit_and_confirm` 语义偷偷改成“旧证据自动托住新文本”或“作者签字自动取代书稿”。** 这需要 CZ 决定来源权力；施工前只能暴露风险和做测试。
14. **不要直接给 M6 接一个开放式大模型回答器。** 当前证据过滤和防剧透是有价值的；开放生成若先于实体/别名解析、coverage receipt 和 evidence support，会把“查不到”重新变成“编一个”。
15. **不要现在跑全书大规模 Gold、训练或模型排名。** 本轮没有这类权限；M3 只需要 30～50 个真实责任段的最小语义切片，且机械分与人工语义分分开。
16. **不要先做完整作者前端、故事概览大屏或统一治理仪表。** M5/M6 现阶段用人读 Markdown 和明确 receipt 已能验局部能力；页面美化不能修 owner、stale 和语义断点。

---

## 10. 最终判定

### 逐模块回答核心判定句

> 给它明确输入，它能独立运行并交出明确输出；输出可保存、重启读回并安全交给下一模块；失败不留半套结果；不同作者不串数据；旧版本不冒充当前版本。

| 模块 | 对核心判定句的回答 | 最短解释 |
|---|---|---|
| M1 | **否，只有前半句成立** | 上传对象、检查、raw 持久化都成立；但输出不能由 M1 安全交给 M2，因为 C10→C11→C1 current 断裂 |
| M2 | **是，机械意义成立** | 明确 C1 current 可独立切 C2、保存/重启/失败保旧/隔离/stale 都成立；语义是否好用另算 |
| M3 | **否，只有冻结运输切片成立** | 离线 response→C3 可保存交 M4；真实 provider parser 与语义质量未过，空 quote 还会让交接晚失败 |
| M4 | **否，只能创建第一批** | 首批 C3→C4 EXTRACTED 成立；第二批无法进工作区，改稿生命周期缺 writer |
| M5 | **是，窄事实审查工具成立** | 当前章分页、显式动作、原子批次、重放、隔离、stale 都成立；跨页固定水位和下游 stale 仍需补 |
| M6 | **是，受控关键词读工具成立** | current confirmed evidence-only、no-hit、as-of、防剧透、上下文/水位成立；不能叫自然语言理解 |

### 当前可对外/对内使用口径

- 可说：**M1 上传前检查可试用；M2 责任段工具机械可用；M3 冻结响应运输切片可用；M4 首批 extracted 物化切片可用；M5 当前章作者审查可试用；M6 受控关键词证据查询机械可用。**
- 不可说：**M1～M6 已打通给普通作者；真实抽取质量已合格；事实账支持持续增量与改稿迁移；自然语言查询已成立；全链生产可用。**
- 最诚实的阶段状态：`M1_M6_HAVE_A_REAL_MECHANICAL_SPINE__AUTHOR_ENTRY_AND_SEMANTIC_USABILITY_STILL_BLOCKED`。

### 材料不足，不能下结论的事项

- M1：单文件 1/3/10/20 章的完整真实 fixture；20 章产品路线；跨已有项目追加缺章；根输入软链接的正式安全政策；CSV/XLSX 是否最终支持。
- M2：真实稀疏／高密章节的切段收益；跨边界事件理解与重复；80 章正式性能基线。
- M3：真实模型的 precision/recall、危险错误、限定词、证据语义承托、零/稀/高密度行为；不能用冻结 response 替代。
- M4：相似／冲突分组的真实收益；改稿迁移状态词与跨 C11/RE 事务 owner。
- M5：高影响单签机器分类；作者 edit 后证据或 AUTHOR_ATTESTATION 的正式权力；真实作者审 250 条的时间与疲劳。
- M6：中文大白话、别名、关系查询的真实理解；查询结果如何提名回候选但不让 M6 获得真值写权。

### 证据索引

| 主题 | 主要包内路径 |
|---|---|
| 当前总控与正式停点 | `01_current_truth/TEMP/t03_total_control_hub_20260818_r01/CURRENT_CONTROLLER_BRIEF.md` |
| R13 产品语义 | `01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md`、`02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md`、`03_CREATION_AND_MEMORY_PIPELINES.md` |
| M1～M6 原子预期 | `01_current_truth/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260819_R02/01_ATOMIC_EXPECTATIONS.md`、`02_ATOMIC_EXPECTATIONS.json`、`04_GLOBAL_ACCEPTANCE_RULES.md` |
| AuthorWorkspace 安全与原子性 | `02_current_route/novel-mvp/mvp/workspace.py`、`02_current_route/tests/test_novel_mvp_workspace.py` |
| M1 | `mvp/upload_source.py`、`input_router.py`、`upload_inspect_tool.py`、`ingest_workspace.py`、`chapter_workspace.py`；对应 `test_novel_mvp_upload_*`、`ingest_workspace`、`chapter_workspace` |
| M2 | `mvp/segment.py`、`segment_tool.py`、`segment_workspace.py`；对应两份 segment tests |
| M3 | `mvp/extract.py`、`extract_tool.py`、`extract_workspace.py`；对应 extract tests 与 `test_novel_mvp_m3_c2v1_c3v1.py` |
| M4 | `mvp/factstore.py`、`fact_tool.py`、`fact_workspace.py`；对应 fact tests；合同 `contracts/C4_FACT_QUERY.md` |
| M5 | `mvp/review_*`、`factstore.py`；对应 review tests 与 legacy `test_novel_mvp_fact_review_transaction.py` |
| M6 | `mvp/ask_*`；对应 ask tool/workspace/context/reader tests |

来源：共用 review ZIP 内当前代码、直接测试、正式合同、当前总控简报、R13 与原子需求背景；ChatGPT Pro 独立审查
