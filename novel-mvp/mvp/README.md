# mvp/ 模块地图

业务逻辑都在这里，`cli.py`（M0 编排器）只做参数解析和调用。跨模块数据格式认 `contracts/` 里的合同，模块内部随便改。

| 模块 | 做什么 | 对外函数 | 下游是谁 |
|---|---|---|---|
| `ingest.py`（M1） | draft 文件／粘贴统一走 C10-first；无显式身份时保存 Unknown、0 C1；`outline` 是不进 M3 的兼容口 | `ingest_files` / `ingest_text` / `ingest_explicit_materials` | input router / intake identity / chapterize → store |
| `input_router.py`（M1 格式层） | TXT／MD 原字节严格解码；DOCX 主文档流生成带容器 SHA 的派生 source；ZIP 安全解包且任一成员失败、无有效材料或超过保守上限时整批强停 | `collect_paths` | ingest；不猜 role、不写 C1 |
| `intake_identity.py`（C10 producer / projection gate） | 保存冻结 source 与 source-span 身份；显式 Tags／Title／Setting 批次分别写 C10 v4／v3／v2；整批先验证再落盘；只让当前 Confirmed Chapter 进入 C1 writer | `ingest_explicit_materials` / `ingest_explicit_material_batch` / `append_identity_revision` / `project_material_units_to_c1` | store → chapterize → C1；正式 validator 负责合同校验 |
| `chapterize.py`（M1 内部） | 识别明确“章／Chapter／节”和 Markdown 围栏外标题；稳定双门牌可折叠，歧义、章序冲突和来源缺口在落盘前强停 | `chapterize_text` | ingest |
| `segment.py`（M2） | 章节正文切责任段（带前后 halo 背景） | `segment_chapter` | extract / refine 按段调用 |
| `admission.py`（Pre-M3） | 不改 C1 原文；阻断 C1 已明确标为 outline 的材料，隔离明确作者提示，身份不明时整章不下发；不按正文关键词猜材料类型 | `apply_pre_m3_admission` | CLI 的 extract／refine／外部 candidates 都只能消费放行章 |
| `extract.py`（M3a） | 主抽：责任段→事实句候选；arkcli 调用的共用底层通道 `call_json` 也在这里。截断判据：JSON 解析失败且 output≥上限 95% 判 `TruncatedOutput`，`extract_segment` 自动降密度重试一次（I-009） | `extract_segment` / `call_json` / `load_config` | store 入账；refine、check 借 `call_json` 调模型 |
| `refine.py`（M3b） | 抽取质检管线：引文回填→补漏→验真→去噪→去重。质检用另一家模型（双 API 纪律）。分账规则：needs_review 待审条去噪不得剔，意见挂 `denoise_flag`（I-020）；去重带数值句守门，属性词不同不判重（I-021） | `run_pipeline` / `format_receipt` / `dedup` | cli 存 refine 报告；候选回 store |
| `store.py`（M4 兼容面） | 项目/材料/C1/事实读取；旧事实写调用保持原名字，但不得裸写 facts | `facts` / `add_fact_candidates` / `set_status` / `edit_fact_text` / `review_fact` / `repair_ids` | facts 写动作全部转给 factstore；其他模块继续读它 |
| `factstore.py`（M4/M5 writer） | C3 候选、作者确认／驳回／改判、改写后采纳、修号与事实因果边共用一把文件锁；被改事实的旧 RE 同事务 stale | `add_fact_candidates` / `review_fact` / `repair_duplicate_fact_ids` / `add_fact_causal_edge_candidates` / `review_fact_causal_edge` / `read_confirmed_fact_causal_edges` | 唯一允许替换 `facts.json` 与 `fact_causal_edges.json` 的运行时入口；底层交 planstore 恢复事务；机器只能写因果候选，确认只认作者 |
| `workspace.py`（作者项目底座） | 原子提交之外，提供不暴露物理路径的同代多键只读快照和 current 重核 | `AuthorWorkspace.read_current_snapshot` / `AuthorWorkspace.is_current_snapshot` | 真实 reader 一次只打开一个 generation；不改变任何 writer |
| `ledger_read_runtime.py`（CCZ-126 current reader） | 读取十账目录、current 章节证据切片和章节／事实稳定 ID；六本设定账、规划、长线、知情边与 pinned 如实保持关闭 | `open_current_reader_session` / `execute_read` | 输出冻结的 `LEDGER_READ_RESPONSE v1`，零 workspace 写入 |
| `c9_ledger_read_adapter.py`（C9 adapter） | 把规范账本对象引用变成公共读取请求，并把完整回执、材料投影和来源绑定交给 C9 | `directory_object_ref` / `chapter_evidence_object_ref` / `ledger_entries_object_ref` | 只适配现有 C9 v2，不复制取件或预算逻辑 |
| `unified_retrieval_composition.py`（M11 受信组装入口） | 从 AuthorWorkspace 能力句柄取得作用域，单会话运行 reader → adapter → C9，末尾重核 current | `run_current_retrieval` | 当前只接章节账和事实账；故事线、自动备料、假设、返工与产品入口仍在边界外 |
| `check.py`（M7） | 一致性体检：机械分组＋打包调模型扫矛盾，含账本完整性预检（重复号只认首条、单独报） | `run_check` / `format_plan` / `format_report` / `save_report` | cli 存 health_report |
| `ask.py` | 取证问答：关键词查已确认事实（带原文依据） | `search_confirmed` | cli 打印 |
| `plan.py`（M8） | 续写规划最小出题：目的挂卡＋选项／前置卡＋冲突爆出＋写作指导副产品；计划不入事实账 | `run_plan` / `format_plan` / `save_plan` | cli 存 plan_latest.json |
| `planstore.py`（M8 planstore） | 正式 `plan-v2` 的跨文件提交护栏＋最小工作稿 handover writer；文件锁、prepare/commit、对象 blob、启动恢复扫描与跨进程幂等 | `accept_work_draft_handover` / `recover` / `operation_status` / `verify_storage` | C1／facts／plan.json／流水共用的提交协调器；跨账权限由 factstore／reconcile 等接缝校验 |
| `reconcile.py`（M8×M4/M5） | current C1＋C3 对计划做六态观察；先落无 actual 权的 RE，再由作者动作把 confirmed facts 与 RE 引用同事务接上 | `record_reconciliation_candidate` / `admit_reconciled_facts` / `reconciliation_edge_states` / `mark_stale_reconciliation_edges` | M4 facts＋planstore RE；不改 C1／原计划文字，不写裸 actual |

模型配置在根目录 `config.json`：主抽 `model_id`（豆包）、质检 `checker_model_id`（GLM），传输走 arkcli 托管凭证。
