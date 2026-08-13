# 调查任务：API 先筛模型并积累数据，什么时候再接 Mini/Lite 的 SFT／DPO

触发原因：方向性决策；产品正在“API多步管线”和“回到可微调小模型”之间分岔，答案不应由一次本地试跑或厂商宣传决定。

## 本地背景

当前单API四块估分均未到产品线，多个模型却呈现互补的精度/召回。旧4B LoRA的两种损失路线已分别过抽崩坏和全空塌缩，训练READ三臂也没有赢家。火山方舟控制面在2026-08-11只读确认 Doubao Seed 2.0 Mini/Lite 260428 均支持 SFT、全参 DPO 和 DPO-LoRA；所以“能训练”不是问题，问题是何时训练才比多步API划算、该训练整套抽取还是其中一个窄步骤。

## 新增的分阶段路线与数据问题

Ling 3.0 Flash 还暴露了明确成本变量：2048 上限时思考正文挤掉最终 JSON，8192 才四题稳定，四题共用 27,597 token 和 88.4 秒。请把思考预算、截断与结构化完成率纳入 API 初筛。

火山方舟控制面已于 2026-08-11 确认 Mini/Lite 260428 均支持 SFT、全参 DPO 和 DPO-LoRA。只读核验见包内 `evidence/11_ARK_MINI_LITE_FINETUNE_CAPABILITY_CHECK.md`。请不要再把问题写成 API 与微调二选一，而要比较五段路线：API 初筛淘汰明显差档；留下三到四个互补候选；用多步管线生产和校正真实样本；把正确答案用于 SFT、把同一输入的失败答案／修正答案组成 DPO 偏好对；让强 API 继续做教师、灰区升级和质量上限。

请给出训练数据达到什么数量、来源多样性、失败类型覆盖和人工复核强度后，Mini/Lite 才值得开 SFT 或 DPO；怎样按小说来源隔离训练、DEV 和未见确认集；用户失败、API 幻觉、开发卷输出、隐私内容和低置信裁决分别怎样过滤。还要回答：什么证据才足以支持“微调 Mini/Lite 在本项目超过当前 GLM 5.2”，以及 SFT→DPO、只 DPO、DPO-LoRA 三条顺序各自的适用条件。

本地证据锚点最多 5 条：

- `TEMP/t5_r04_fresh_novel_four_chapter_model_screen_20260811_r01/all_api_scoring_r02/ALL_API_MODEL_SCOREBOARD.md`｜SHA：`5fe2445a94e5b9e7f41f48f718719fdc172f296a146ad4f19de53f35c6eccb30`｜说明：当前API质量、Token和时延估算
- `finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R05/TRAINED_READ_NO_WINNER_RESULT_TICKET.json`｜SHA：`b0840724f0712550dae084535d406d126ea829320c6056e79603810e5a379d7a`｜说明：旧训练READ没有承接臂
- `runs/T5_R04_READ1_TRAIN96_TOKEN_WEIGHTED_QUALIFICATION_R01/L6_MECHANICAL_FAIL_TICKET.json`｜SHA：`b09f3d952c3ca7668236d1fa21dc4957d0225cf152f5849b5362986e5b527a77`｜说明：token-weighted路线过抽、复读和触顶
- `runs/T5_R04_READ1_TRAIN96_SAMPLE_MEAN_QUALIFICATION_R01/L6_MECHANICAL_FAIL_TICKET.json`｜SHA：`90e461e52735193e75a56c59ed7544cf6ab187aa1941ffcf69c5473990061066`｜说明：sample-mean路线六题全空

## 请你深度调查

请给出一个可计算的决策框架，比较三条路线：

1. 全程使用通用API的多步级联；
2. 通用API负责主抽取，微调Mini/Lite只做验真、筛选、路由或补漏中的一个窄步骤；
3. 微调Mini/Lite承担主抽取，强API只处理灰区和高风险事实。

重点回答：在什么质量、请求量、上下文长度、Token价格、延迟、并发、人工复核率、数据维护成本和模型漂移条件下，各路线更合算；项目专有判定边界要稳定到什么程度、训练数据要达到什么覆盖与独立验证水平，才适合微调；窄验真器是否通常比完整生成式抽取器更适合作为第一个微调目标。

## 期望产出

- 论文、官方文档或真实工业案例，不要只复述“微调更便宜/大模型更强”
- 一套代入本地数据即可算的成本与延迟公式，包含缓存、批处理、失败重试和人工灰区成本
- 一棵决策树：质量未过门、质量过门但太贵、错误稳定可教学、数据/Gold不稳时分别怎么走
- “微调整体抽取器”与“微调窄验真器/路由器”的风险对比
- 适用条件、失败条件和出处链接

## 采用／否决判据

- 若API管线先达到质量线且在目标业务量下成本可接受，保留API，不为了训练而训练
- 若质量过门但成本、时延或并发成为明确瓶颈，且某一步有稳定标签与独立验证，再考虑只微调该步
- 若错误仍被上下文切分、Gold、评分或流程变量解释，不得归因成“缺教材”并启动SFT
- 外部案例不能直接证明当前Mini/Lite一定可迁移；厂商基准和营销数字只能作先验

## 本地并行与禁止事项

等待回包时可整理每章调用量、Token、时延、灰区比例和现有训练失败类型；不得创建SFT任务、数据集、接入点或新的API调用，不得调整旧训练教材、损失或超参。

来源：Codex
