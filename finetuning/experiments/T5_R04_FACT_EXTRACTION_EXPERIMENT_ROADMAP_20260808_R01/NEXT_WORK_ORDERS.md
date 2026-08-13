# 下一批小工单

这里是可以直接施工的工单草案。本轮一个都不执行。

## WO-01｜短片段责任范围三臂预检

**目的：**确认 `target-only`、小 halo、当前窗口哪个更适合事实抽取。

**只做：**材料资格、三臂 renderer、同源校验、token 统计、执行锁和评分合同预注册。

**固定：**C2_FULL update72、DEV24、输出合同、解码、评分器。

**唯一变化：**负责区外只读上下文范围。

**硬停：**三臂不是同一 target／gold；halo 看 gold 选取；题面重复次数不同；DEV24 被修改；任何模型运行未获单独授权。

## WO-02｜1～2 条原子规则候选冻结

**目的：**避开已经失败的八规则写法，只检查一条或两条真正决定边界的规则有没有净收益。

**只做：**从错误家族选择两条原子规则，冻结 C0／+1／+2 的逐字 Prompt，做等来源、等数据、等解码预注册。

**固定：**不用 R5／R10／R15 名字重跑；不引入 examples、背景或目的。

**硬停：**规则同时改变字段说明和输出合同；从 DEV24 逐题错误反向写专用规则；未冻结 CONFIRM24 隔离方案。

## WO-03｜安全 contrastive pair 候选包

**目的：**检查一个最小对比例子能否帮助模型认清计划、误信、否定等边界，而不是复制答案。

**只做：**制作候选合同、anti-copy 检查、EX0 与单 pair 的同源预注册；不运行。

**固定：**两个示例成员都必须是正确输出；示例人物名、谓词和事实数不能泄漏当前题；一次只放一组 pair。

**硬停：**示例和 query 有词面泄漏；示例改变当前 evidence allowlist；示例进入训练；示例位置和数量同时变化。

“按可观察边界检索 0～2 例”已单列为后续臂 `INPUT-EX-RETRIEVED-BOUNDARY-0TO2`。它不属于本工单；只有固定 pair 先过门，且检索规则、0 例退路、故事／人物／模板隔离和泄漏禁令都封版后，才允许另开工单。

## 后续排队

4. 背景四臂预检：无背景／确认相关／等 token 中性／冲突；
5. marker、citation、cross-unit 三个单变量工单；
6. CONFIRM24 设计与独立审收；
7. Semantic Core 0%／5% 训练前审计；
8. `FACTS_FIRST_METRIC_CONTRACT_PREFLIGHT`：只冻结 scorer、共享分母、citation 失败归因和阈值，不运行模型；
9. facts-first 与 evidence-first 各自的 One-stage／Oracle／Predicted 零训练门；
10. P4-SYNTH-PILOT6 原创完整章材料合同；
11. 完整章六臂与 metadata M0／M1／C-Nonce 运行票。

来源：Codex
