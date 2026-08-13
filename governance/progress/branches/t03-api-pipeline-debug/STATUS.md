# T-03 多形态输入抽取管线隔离调试｜STATUS

## Identity

- 生命周期：ACTIVE
- 当前状态：D0_D1_D2_COMPLETE__D3_ROLE_CONFIG_SPLIT_COMPLETE__FOUR_PARALLEL_TEMP_SLOTS_READY
- 工作方式：固定输入合同和输出合同，在本仓 TEMP 的 MVP 副本里调中间管线
- 当前计划：[T03_API_PIPELINE_DEBUG_MASTER_PLAN_R01.md](../../../../TEMP/t03_api_pipeline_debug_plan_20260813_r01/T03_API_PIPELINE_DEBUG_MASTER_PLAN_R01.md)
- 隔离副本：[t03_mvp_isolated_debug_20260813_r01](../../../../TEMP/t03_mvp_isolated_debug_20260813_r01/README.md)

## Long-term objective

让小说、大纲、小说＋大纲、书名＋简介＋金手指＋黄金三章、前 100 章大纲都能按自己的材料身份进入系统，并输出来源、状态、证据和用途都正确的统一候选。

两端合同固定；中间的导入、分流、切分、上下文、人物解析、主抽、补漏、验真、去噪、去重和冲突整理可以单变量调试。每一刀必须保留改前、改后、退化、调用、Token、时延、费用和 MVP 修改建议证据。

这里的调试不表示训练。产品上架前只用 API，T-05 训练与 T-09 旧外调保持暂停。

## Current state

- T-03 已由 `/root` 领取并恢复执行。
- 输入合同、输出合同、总计划、调试样本 Schema 和外调问题账已经落盘。
- 已把 `novel-mvp` 2026-08-13 20:40 的当前施工现场复制成双层隔离副本：59 个入选文件，源提交 `190a099ea5c18ccf3a55eb4f9b951711295ab1cc`，成员清单总锁 `6797ac934efe8c0411009cb54c174e2a58f90fe597912f6501741706f49df7eb`。
- `upstream_snapshot/` 保存原样基线；`sandbox/` 可供后续调试；源仓未写入。
- `.git`、用户 `data/`、`temp/`、`emp/`、缓存和环境文件没有进入副本。
- D0 已用五类原创合成材料完成零 API 合同冒烟，证实材料身份、导入损失和入账证据字段三个缺口。
- D1 已在新小说批次精确 5 本、错开第 1～5 章、16 个责任段完成三个主抽臂：豆包对 V4 Flash 32 次，Seed OSS 36B 16 次；48/48 成功、0 重试。豆包暂留主抽默认，V4 留作速度／资源挑战者，Seed OSS 不扩大主抽测试。
- D2 已在每本书豆包引文覆盖代理最低的一个责任段测试补漏位。正式 R02 10 次、0 重试：GLM 5/5 成功并返回 16 条候选；DeepSeek V3 4/5 成功、1 格格式失败并返回 1 条。无 Gold，不把返回条数当 TP；GLM 暂留补漏位且产出必须继续验真。
- D2 R01 另有 1 次身份门停线：请求 GLM `260601` 固定回显服务器版本 `260617`，后 9 格未发；失败账保留，不计成绩。
- D3 已在 TEMP 主副本完成岗位模型配置拆分：主抽、补漏、验主抽、验补漏、去噪可以分别指定模型；旧配置字段缺失时仍按改前规则回退。零 API 内存冒烟证明旧行为不变、四岗位互不串位；见 [`D3_ROLE_MODEL_CONFIG_SPLIT_RESULT_R01.md`](../../../../TEMP/t03_mvp_isolated_debug_20260813_r01/evidence/D3_ROLE_MODEL_CONFIG_SPLIT_RESULT_R01.md)。
- 本轮累计实际 API 59 次：D1 48、D2 R01 1、D2 R02 10；自动／手动重试均为 0。仅精确读取获准的 5 章正文；训练、Gold／sealed／未见卷、Git、Notion、生产默认修改均为 0。
- 四个互斥 TEMP 实验位已经建立：验真、去噪、主抽第二批泛化、五类输入装配；每份都有只读 `baseline` 和可改 `sandbox`，见 [`T03_PARALLEL_WORK_SLOTS_R01.md`](../../../../TEMP/t03_mvp_isolated_debug_20260813_r01/evidence/T03_PARALLEL_WORK_SLOTS_R01.md)。
- 两份外部回传已经完成原文保存和本地采纳判读，见 [`RETURN_INTAKE_SUMMARY_R01.md`](../../../../TEMP/t03_external_returns_intake_20260813_r01/RETURN_INTAKE_SUMMARY_R01.md)。
- 24 小时复盘支持暂停广泛模型／Prompt 扩测，转为具体失败驱动的 T-03 调试；不产生 API 权限，也不把 T-03 缩成四章考试。
- R10 外审支持“修订后转正”路线，但与 T-03 合同无关，也不是 R10 转正票。

## Last reliable checkpoint

T-03 已从规划进入实测。D0 找到三个合同承载缺口；D1 得到主抽岗位的初步模型分工；D2 得到补漏岗位的初步分工；D3 让 TEMP 主副本具备按岗位单独换模型的能力。上述都是候选证据，不改正式 MVP 默认。当前岗位总览见 [`T03_CURRENT_PIPELINE_ROLE_BOARD_R01.md`](../../../../TEMP/t03_mvp_isolated_debug_20260813_r01/evidence/T03_CURRENT_PIPELINE_ROLE_BOARD_R01.md)；四个互斥实验位已经就绪，等待 CZ 分给其他 Agent 并行推进。

## Next action

由 CZ 把四个 READY 实验位分别交给窗口：

1. T-03V 只做验真岗位 GLM 5.2 对 V4 Flash；
2. T-03N 只做去噪岗位 GLM 5.2 对 DeepSeek V3；
3. T-03G 只做第二批 5 本小说的豆包对 V4 主抽泛化；
4. T-03M 先做五类输入装配、切分和身份错误地图，API 为 0 起步；
5. 各窗完成后只把结论、证据路径和 MVP 修改建议回填本 STATUS；不要互读私密 raw，不自动改正式产品仓。

## Blockers

- 无当前阻断；四个实验位等待 CZ 分派给其他 Agent。
- `governance/CURRENT_STATE.json` 仍是 2026-08-08 快照，不能授权未来真实 API。
- 超出各实验位 README 初始范围的真实样本或 API 调用，需要该窗口另写精确小票。

## Recovery guardrails

### Must not repeat

- 不把 T-03 缩成小说正文切窗调试。
- 不重新设计 MVP 已定产品流程；这里只调试与提建议。
- 不把小说、大纲、简介、作者设定拼成一个无来源文本。
- 不把“大纲计划”写成“正文已经发生”。
- 不恢复 T-09 的 API／微调二选一，不启动 T-05 训练。
- 不修改 `/Users/a1234/挣钱/novel-mvp/`；只改隔离 `sandbox/`。
- 不把每个问题先外调，不做全模型×全 Prompt×全环节大网格。
- 不碰另一个 Agent 正在施工的产品仓写集。
- 不让多个 Agent 共写同一个 `sandbox`、`runs` 或 `evidence`。
- 不重跑 D1 的 Seed OSS 主抽臂；没有新证据时不把 DeepSeek V3 改回主抽或默认补漏。

### Must not skip

- 输入材料类型、生命周期、权威、允许用途、来源版本和导入损失。
- 输出候选的来源、状态、证据能力、实体解析和未知／冲突。
- 每轮唯一主要变量、基线、逐站输出和跨输入退化。
- 运输、机械、语义、来源与资源分账。
- 没有显式姓名时允许未知，不能从书名、简介或常识补名。
- 真实 API 前冻结精确输入、模型／endpoint、Prompt、思考模式、调用上限、停止条件和输出根。
- MVP 修改建议必须附前后证据；建议不能直接回写产品仓。
- 并行实验位必须保留只读 `baseline`；试坏后从它重新复制，不在坏代码上补回去。
- D2 GLM 请求名与固定回显名必须分别登记；不能再把 `260601` 与 `260617` 的正常映射误判成未知漂移。

## Recent CZ decisions

- 2026-08-13：T-03 的最终目标覆盖小说、大纲、小说＋大纲、项目种子材料和前 100 章大纲；两端是合同，中间可以逐步调整，每步必须带证据。
- 2026-08-13：允许把当前 `novel-mvp` 现场复制到本仓 TEMP，在副本里试改调试，再给出附证据的 MVP 修改建议；不污染原仓。
- 2026-08-13：T-03 规划完成后停点；24 小时模型／Prompt 复盘与 R10 转正两份外部回传已经受控接收，前者不授权扩测，后者不替 R10 转正。
- 2026-08-13：产品上架前不训练，只用 API；T-05、T-09 暂停。
- 2026-08-14：允许在新小说批次精确选择 5 本不同题材、错开第 1～5 章，按岗位分轮做小规模 API 调试；拿多轮证据后再决定组合。
- 2026-08-14：允许在 TEMP 建多个互斥 MVP 副本，分别交给其他 Agent 并行试验；各 Agent 只在自己目录折腾，试坏则从只读起点重新复制。

updated_at: 2026-08-14T01:55:00+08:00

来源：Codex
