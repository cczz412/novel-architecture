# 跨窗口任务队列

这页解决一件事：**一个窗口把手头任务收口后，不用等 CZ 现场派活，来这里领下一单。**

## 权威边界

- 队列只做接力，不是真值源。与 CZ 当前指令、Notion 账序、`../CURRENT_STATE.json`、正式结果票冲突时，停下校准，以它们为准。
- 领到任务不等于领到权限：每单标注的授权边界照旧生效；训练、Notion 写入、Git、外发、生产晋升等仍按各自的票和 CZ 指令走。
- CZ 可随时插单、重排、砍单；改动本页无需任何窗口同意。
- 公告（2026-08-13）：产品 MVP 主办仓已建在同级 `/Users/a1234/挣钱/novel-mvp/`（CZ 拍板、Cursor 直营、轻档治理、已接真 API）。Codex 窗口**不接管、不巡检、不顺手优化**该仓，除非 CZ 点名派单；研究结论照旧只在本仓沉淀。
- 公告（2026-08-13 20:48 更新）：`novel-mvp` 已由另一个 Agent 独立复工。T-03 不接管其写集，只使用 20:40 的 TEMP 隔离快照做调试；成熟结果只形成附证据的修改建议，不直接回写产品仓。
- 公告（2026-08-13）：背景板 R07 之后的小批语义新增走**增补案挂账**，不逐次改版：[挂账本](../../TEMP/bgboard-audit-20260809-r01/18_R07_ADDENDUM_LEDGER_20260813_R01.md)已有 ADD-001（SI-006 采信条目＋CZ 教程双路拍板）。R08 组装时逐条吸收，见 T-12。

## 领单协议

1. 窗口收口当前任务（交付＋回执＋progress 更新齐）后，从上往下找第一条 `QUEUED`、主办匹配、前置门全部满足的任务。领单先按根 `AGENTS.md` 4b 节给任务定治理档（轻／中／重），按档配流程，不默认升重档。
2. 领单＝把状态改成 `CLAIMED`，写上会话 ID 和时间。先改先得；改之前先看本页最新版和 Git 状态，别抢别人已领的单。
3. 领单窗口如果发现 `../CURRENT_STATE.json` 的快照时间（`snapshot_at`）距现在超过 48 小时，先把过期情况报给 CZ，再开工；这里只要求报告，不自动刷新机器真源。
4. 一个窗口同时只持有一单。完成后改 `DONE` 并附回执指针；被门卡住改 `BLOCKED` 并写清缺什么。
5. 队列里没有可领的单时，登记「空闲待派」并停下，不自开新支线。

## 队列

| ID | 任务 | 主办 | 前置门 | 状态 |
|---|---|---|---|---|
| T-01 | DISCRIM17 收窗四件套：916 行精确/边界账、17 臂主分+费用双账表、候选提案（含已授权的 A/B/C）、交接包+progress 更新 | 总控窗 | R08 合成修复过独立验收 → 一次性真实试选 | DONE（2026-08-13 13:23；[候选提案](../../TEMP/t01_discrim17_candidate_proposal_20260813_r01/CANDIDATE_PROPOSAL_R01.md)；[真实边界接受票](../../TEMP/t01_old17_real_boundary_run_acceptance_r01/REAL_BOUNDARY_RUN_INDEPENDENT_ACCEPTANCE_R01.json)；[非思考补测接受票](../../TEMP/t01_nonthinking_bounds_real_run_acceptance_r01/REAL_BOUNDS_RUN_INDEPENDENT_ACCEPTANCE_R01.json)；3 候选不变） |
| T-02 | PROMPT A/B/C 三臂对照（36~60 次硬顶，套餐内） | 总控窗或继任实验窗 | T-01 候选提案通过总控验收（CZ 2026-08-12 16:18 已预授权） | DONE（2026-08-13 17:50；36 个逻辑格／33 次实际尝试；3 个完整臂均为 Prompt A，6 个 B／C 臂不可比；未产生 Prompt 胜者；[最终计分结果](../../TEMP/t02_prompt_abc_bounds_scoring_result_r01/PUBLIC_BOUNDS_SCORE.json)；[独立接受票](../../TEMP/t02_prompt_abc_bounds_scoring_run_acceptance_r01/INDEPENDENT_RESULT_ACCEPTANCE_R01.json)） |
| T-03 | 多形态输入抽取管线隔离调试：小说、大纲、混合材料、书名＋简介＋金手指＋黄金三章、前 100 章大纲走固定输入／输出合同；中间管线在 MVP 副本里单变量调整，每步附质量、退化与资源证据 | 当前总控窗 `/root` | T-02 已收口；真实 API 前留精确小票；只改 TEMP `sandbox/`，不写原 `novel-mvp` | IN_PROGRESS_PARALLEL_SLOTS_READY（2026-08-14 01:40；D0／D1／D2 已完成；[证据账](../../TEMP/t03_mvp_isolated_debug_20260813_r01/evidence/RUN_EVIDENCE_LEDGER_R01.md)；[四个互斥实验位](../../TEMP/t03_mvp_isolated_debug_20260813_r01/evidence/T03_PARALLEL_WORK_SLOTS_R01.md)已就绪，等待 CZ 分给其他 Agent） |
| T-03V | 验真岗位对照：固定主抽和补漏候选，比较 GLM 5.2 与 V4 Flash 的误放／误杀 | 待 CZ 分派 | 只写自己的 TEMP 实验位；建议 10 次、0 重试 | READY（[实验位](../../TEMP/t03_parallel_verify_20260814_r01/README.md)） |
| T-03N | 去噪岗位对照：验证 DeepSeek V3 的克制是否能减少流水账而不误杀关键事实 | 待 CZ 分派 | 只写自己的 TEMP 实验位；先冻结 40～60 条候选 | READY（[实验位](../../TEMP/t03_parallel_denoise_20260814_r01/README.md)） |
| T-03G | 主抽第二批泛化：另选 5 本不同题材小说，复验豆包对 V4 Flash | 待 CZ 分派 | 不与 D1 书目重合；建议 24～40 次、0 重试 | READY（[实验位](../../TEMP/t03_parallel_main_generalization_20260814_r01/README.md)） |
| T-03M | 五类输入装配与切分：先画错误地图，再对具体故障开窄 API | 待 CZ 分派 | 先 0 API；只写自己的 TEMP 实验位 | READY（[实验位](../../TEMP/t03_parallel_multi_input_20260814_r01/README.md)） |
| T-04 | 未见确认卷（CONFIRM4）一次性开封终审 | 实验窗 | T-03 胜者确定＋开封协议＋模型/Prompt 合同冻结；同版本只准开一次 | BLOCKED（门未齐） |
| T-05 | Mini 候选训练执行票启动 | 实验窗 | 产品上架后或 CZ 另行改令；现阶段产品只用 API | PAUSED_BY_CZ（2026-08-13 20:17；产品上架前不微调，旧预备票不执行） |
| T-06 | 背景板 R07 收尾核验：成员/核心/整包 SHA 复算回报、Notion MANIFEST 回填核对、AGENTS 与总库入口牌指向核对 | 任意 Codex 窗 | 无 | DONE（2026-08-13 00:38；[成员清单](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260812_R07/CORE_MATERIALS_MANIFEST.json)；[构建回执](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260812_R07/BUILD_RECEIPT.json)；AGENTS 仍指 R06，留给 T-11 D；本地回执记载 Notion 总库入口已指 R07） |
| T-07 | 四份需求调查回包按 SI 登记进 survey-inbox（TEMP/bgboard-audit-20260809-r01/returns_demand_discovery_20260812/） | 任意 Codex 窗 | 无；只登记证据，不产生产品结论 | DONE（2026-08-13 00:47；[SI-005 卡片](../../references/survey-inbox/items/SI-005_demand_discovery_research_returns.md)；[四份回包知识包](../../references/survey-inbox/packages/DEMAND_DISCOVERY_RESEARCH_RETURNS_20260812_R01/00_READ_ME_FIRST.md)） |
| T-08 | T3 前语义合同起草：把 R07 已批方向 N15（真源分权）/N16（表述-命题拆分）/N17（签字来源、三种时间、unknown 六分）翻成可验收的语义合同草案 | 产品/架构窗 | R07 现行（已满足）；只出草案，不建表、不施工 | DONE（2026-08-13 00:55；[T3 前语义合同草案 R01](../../TEMP/t08_semantic_contract_draft_20260813_r01/T3_PRE_SEMANTIC_CONTRACT_DRAFT_R01.md)；轻档草案，不产生执行权） |
| T-09 | 外调 ZIP 外发：API 管线 vs 微调三题（TEMP/T5_R04_EXTERNAL_RESEARCH_API_PIPELINE_FORK_20260811_R01.zip） | CZ 手动 | 产品路线再次需要比较 API 与微调时再恢复 | PAUSED_BY_CZ（2026-08-13 20:17；产品上架前只用 API，旧外调不发送；T-03 只对具体调试故障开窄调查） |
| T-11 | 仓库结构收尾四件：隔离区外置毕业（A）、根目录僵尸手术（B）、CURRENT_STATE 刷新节奏（C）、AGENTS 入口切 R07（D）。工单全文在 TEMP/_quarantine_repo_cleanup_20260812/WORKORDER_FOR_CODEX.md | Codex 治理窗 | A 项等 2026-08-19 观察期满＋CZ 点头；B/C 可先做；D 等 AGENTS.md 当前写集收口 | BLOCKED（B/C 已完成；[阶段回执](../../TEMP/t11_repo_cleanup_20260813/T11_BC_CLOSEOUT_RECEIPT.json)；A/D 门未齐） |
| T-12 | 背景板 R08 组装：吸收[增补案挂账本](../../TEMP/bgboard-audit-20260809-r01/18_R07_ADDENDUM_LEDGER_20260813_R01.md)全部挂账条目（ADD-001~017），按 06 变更协议出新版＋SHA；Notion 同步另行安排 | Cursor 主窗（CZ 点名 Fable 5 Max 组装） | CZ 已触发 | DONE（2026-08-13 07:54；[R08 包](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260813_R08/00_READ_ME_FIRST.md)；17/17 ADD 吸收、机械自查 11 项＋主窗独立复核全绿、R07 原包 SHA 对平未动；整包 SHA `5bfc856c…aded`；Notion 按 ADD-020 N4 不单独推 R08，随 T-13 一次性同步 R09） |
| T-13 | 背景板 R09 组装＋Notion 一次性同步：吸收[第二册挂账本](../../TEMP/bgboard-audit-20260809-r01/24_R08_ADDENDUM_LEDGER_20260813_R01.md) ADD-018~020＋写作区附录；按 N4 由 Cursor 直推 Notion（R08 不单独推） | Cursor 主窗（Fable 5 Max 组装＋主窗直推） | CZ 已触发（"应该要去制作 R9 了"＋N4 拍板） | DONE（2026-08-13 11:20；[R09 包](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260813_R09/00_READ_ME_FIRST.md)；20/20 ADD＋1 附录批次吸收零驳回、组装员自查＋主窗独立复核全绿、R08 原包分毫未动；整包 SHA `3fc9b7ca…ba05`；Notion 同步完成：包页＋14 成员页已建、总库入口牌已从 R07 切 R09、R07 页面保留未动，页面 ID 清单回填 [BUILD_RECEIPT](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260813_R09/BUILD_RECEIPT.json)；03/04/05/07＋两 JSON 页后由收尾员升级逐字全文；账序补登记完成（11:30 条插页首）；⚠️ 遗留：重复 R09 半成品页已标记待删等 CZ） |
| T-14 | 第三轮外调回包消化→R10：15 份回包、第三册 ADD-021~037、产品稿与 R10 草稿／正式版 | Cursor 主窗＋Codex 收口 | CZ 防阻塞替拍授权＋2026-08-13 当前“按清单补齐并快速转正”指令 | DONE（2026-08-13 23:49；[R10 本地正式包](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260813_R10/00_READ_ME_FIRST.md)已由草稿独立派生；021／029／030／035 原文接受，022／023／025／026／027／028／031／032／033／034 修订接受，024 降施工附录，036／037 保持亲拍；题 16 字段继续开放但不阻塞；[第三册](../../TEMP/bgboard-audit-20260809-r01/26_R09_ADDENDUM_LEDGER_VOL3_20260813_R01.md)已回填；Notion 本轮未授权、镜像仍 R09） |
| T-15 | 背景板 R11 组装：吸收第四册 ADD-038～042、049～056；043／044 开口带着走；045～048 不吸收；独立目录、不改 R10 冻包、不传 Notion | Cursor 主窗（自检模式） | CZ 2026-08-14「开自检、组 11」 | DONE（2026-08-14；[R11 入口](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R11/00_READ_ME_FIRST.md)；核心 SHA `420e883a…29f3`；整包 SHA `848eca8b…98c6`；父版 R10 SHA 对平未动；Notion 仍 R09） |
| T-16 | 背景板 R12：扫 SI-013 已拍组装残留；独立目录、不改 R11 冻包、不替拍 5 问、不传 Notion | Cursor 主窗（自检模式） | CZ 2026-08-14「开始修复吧」 | DONE（2026-08-14；[R12 入口](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R12/00_READ_ME_FIRST.md)；核心 SHA `370fbbe0…6849`；整包 SHA `2ebc7eee…b7a9`；父版 R11 SHA 对平未动；Notion 仍 R09） |
| T-17 | 背景板 R13：吸收 SI-013 五问 ADD-057～061；独立目录、不改 R12 冻包、不传 Notion | Cursor 主窗（自检模式） | CZ 2026-08-14「进入下一版」 | DONE（2026-08-14；[R13 入口](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md)；核心 SHA `d5629b88…55de`；整包 SHA `502a98af…8a7b`；父版 R12 SHA 对平未动；Notion 仍 R09） |

## 已完成

- T-02｜2026-08-13 17:50 完成。三候选×Prompt A／B／C 共 36 个逻辑格、33 次实际尝试；只有三个 Prompt A 臂四章完整，且最有利上界均低于筛选线，六个 B／C 臂不可比。本轮不产生 Prompt 胜者，不改旧三候选，也不重排旧前三／前五。
- T-01｜2026-08-13 13:23 完成。916 行部分盲审真实边界分出 3 个 `POSSIBLE`、0 个 `ROBUST`候选：Seed OSS 36B Instruct 与 DeepSeek V4 Flash 过产品线可能前沿，DeepSeek V3 仅过筛选线可能前沿；14 臂本周期永久出局。后续追加的 5 模型关闭思考补测中，4 个可比模型的上界仍低于 B 线，1 个主章交付失败不可比，因此 0 新候选，原 3 候选直接交给 T-02。
- T-08｜2026-08-13 00:55 完成。R07 已批 N15／N16／N17 已翻成 T3 建表前可读、可机械检查的语义合同草案，覆盖真源分权、表述／命题拆分、作者签字、三种时间、unknown 六分、正反例与开放题。轻档草案，不产生数据库 Schema、迁移、API、训练、生产或 Notion 拍板等执行权。
- T-07｜2026-08-13 00:47 完成。四份 ChatGPT 需求调查以一个 SI-005 批次卡和一个知识包登记；包内正文与 TEMP 原件逐字节一致，原文件名、原始归因、SHA、字节数和换行数均已保存。只作为历史调查证据与候选先验，不产生产品结论、执行权、训练权或 Notion 拍板。
- T-06｜2026-08-13 00:38 完成。目录精确 14 个文件，其中 12 个 Markdown 成员、8 个核心成员；成员 SHA、核心 SHA、manifest SHA 与整包 SHA 均已复算对平。本地 MANIFEST／构建回执已保存 14 个 Notion 成员页 ID、全成员回读和总库入口指向 R07 的证据。根 `AGENTS.md` 当前仍指 R06，按写集边界只报告，切换留给 T-11 D；`current-progress.md` 的队列入口已存在，未改。
- T-10｜2026-08-12 23:48 完成。逐条核对后以 `PASS_WITH_BOUNDARY_CORRECTIONS` 归位到 [`references/engineering-ledger/00_READ_ME_FIRST.md`](../../references/engineering-ledger/00_READ_ME_FIRST.md)；原 `work/` 草稿保留，未修改实验票、Gold、CURRENT 或生产身份。

updated_at: 2026-08-13T23:49:00+08:00

来源：Cursor（经 CZ 2026-08-12 授权搭建）
