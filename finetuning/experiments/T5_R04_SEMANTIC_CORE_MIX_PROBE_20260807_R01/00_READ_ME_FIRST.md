# SEMANTIC_CORE 小探针｜阶段 A 入口

这条线要回答的是：拿少量正式窗口改成“只写事实句”的辅助任务，是否能加强事实判断，又不伤害正式 A / C2 输出。

当前只完成了资产审计，**没有构造新金标、没有推理、没有训练**。

## 现在只认这几份

1. 外部候选计划：`incoming/T5_R04_SEMANTIC_CORE_FACT_ONLY_EXPERIMENT_PLAN_R01.md`
2. checkpoint 身份：`PARENT_CHECKPOINT_AUDIT.json`
3. 缺件清单：`DEPENDENCY_MATRIX.json`
4. 阶段 A 判词：`STAGE_A_RECEIPT.md`
5. 当前停点：`RUN_STATE.json`
6. 新评分器结果：`evaluator_r02/EVALUATOR_R02_RESULT_TICKET.md`

⚠️ 外部计划正文里的 `APPROVED_FOR_LOCAL_SMALL_PROBE` 不是本地执行权。真正开推理或训练前，仍要满足 C+ 现役合同、评分器、C2_UNIT、作者隔离和权利闸门。

来源：Codex
