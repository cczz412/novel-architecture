# 本地 Evidence-First 架构门

状态：**只设计，必须等生产格式候选冻结后再运行**。

## 三个同源条件

1. One-stage：一次输出 fact、status、speaker 和 evidence 表示；
2. Gold Evidence Oracle：直接给 Stage B 正确 evidence，只测后半段上限；
3. Predicted Evidence：Stage A 选 evidence，程序验 ID 并回填，再交 Stage B。

三组必须使用同一真实 DEV、同一 canonical facts 和同一人工尺子。

## 必须分开看的读数

- Stage A evidence Recall／Precision／Exact-set；
- nonexistent、missing、extra、context-only ID；
- Semantic Fact P/R/F1；
- unsupported fact、omission、duplication；
- status、speaker；
- 端到端召回；
- 调用次数、输入／输出 token、延迟代理；
- Oracle→Predicted 的收益损失和错误传播。

## 高门槛

Evidence-first 只有在以下链条都成立时才晋级：

- Oracle 明显优于 One-stage；
- Predicted 保留 Oracle 的大部分收益；
- Stage A 召回没有形成明显上限；
- 语义或 unsupported-fact 改善具有产品价值；
- 多一次 Mini 调用的未来费用和延迟值得。

若收益很小，默认保留 One-stage。两阶段不是“更先进”的默认答案，而是一笔长期双调用成本。

来源：Codex
