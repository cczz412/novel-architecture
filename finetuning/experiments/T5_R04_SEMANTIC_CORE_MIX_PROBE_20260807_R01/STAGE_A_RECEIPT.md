# SEMANTIC_CORE｜阶段 A 资产审计回执

✅ checkpoint 身份审计完成，但现在还不能跑 Z00 / Z01，也不能训练。

## 查到的现状

- 四个旧 A/C adapter 都在，SHA、大小和计划一致。
- 旧 A stage1 只能做 A 内部省时筛查；旧 A final 只适合研究污染后能否修回。
- 两个旧 C 学的是全局编号、字符坐标和锚字，不能冒充新的局部 `Bxx/Txx` C2_UNIT parent。
- 本地 Qwen3-4B 基座完整可读。
- 当前没有一对满足新合同的干净 A/C2 parent。

## 为什么连“零训练探针”也没马上跑

零训练不是零准备。Z00 / Z01 还需要同一批作者隔离的 DEV_CORE、人工复核过的 `fact_sentences` 金标，以及 A_CORE / C2_CORE 两个冻结渲染器。C2_CORE 又依赖尚未完成的局部 B/T 切分与映射。

现有旧 41 题和旧 48 题不能拿来凑：它们已经属于历史评测，且不满足新计划要求的作者隔离。

## 与当前 C+ 主线的关系

当前 C+ 首轮只允许 A 与 C2 的证据格式不同，其他内容相同。SEMANTIC_CORE 会把 5% 窗口换成第三种 `fact_sentences` 输出合同，所以它是**独立实验**，不能偷偷并进原 C+ Stage 6。

## 下一步建议

1. 先做 EVALUATOR_R02，只重算现有答卷，不覆盖旧成绩。
2. 按原 P0 先完成 C2_UNIT atomizer / renderer 的机械闸门。
3. 再建 DEV_CORE 与 CORE 金标，才运行 Z00 / Z01。
4. 只有零训练探针通过，才讨论是否建立干净 parent；不直接拿旧 C 接着训。

本阶段没有推理、没有训练、没有 API、没有改教材和考卷。

来源：Codex
