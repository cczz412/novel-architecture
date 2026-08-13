# DEV_CORE／CORE gold 阶段合同 R02

这阶段只准备一把能测“事实有没有读懂”的尺子，不推理、不训练，也不改已经封住的机械件。

## 冻结件

- C2 atomizer R02；
- position provenance contract；
- C2 renderer；
- EVALUATOR_R02。

看到具体题目后，不允许回头改切分、位置来源、渲染或评分规则。

## 同源与独立

- DEV_CORE 先按书目、作者隔离、正文质量和稳定哈希冻结正文窗口，再制作 gold；
- 不能读取旧模型输出或旧得分选题；
- A_CORE 与 C2_CORE 必须使用同一批 bridge、负责区和下文；
- 两臂共用同一份 canonical `fact_sentences`；
- Bxx／Txx 只是输入位置标记，不参与 CORE 正误定义；
- 不允许为了 A 或 C2 单独增删题目、改正文或改 gold。

`FS02B-006-S01` 的位置歧义继续隔离于 C2 训练和唯一 provenance 评分。它的事实语义若明确，不因此从纯事实 CORE 删除。本轮新 DEV_CORE 不把这条旧案例当作新选题来源。

## 三类读数分开

1. 事实能力：fact precision、recall，以及人工盲审的 raw／recoverable semantic；
2. 生成故障：structured semantic、end-to-end usable、schema、复读、截断、是否正常完成；
3. 表示负担：题面／输出 token、可见编号数量、跨单元比例。

这三类不得合成一个可以互相补偿的总分。21.875 个可见编号／窗和 52.3% 跨单元只是历史诊断值，不预先判 C2 失败。

## Z00／Z01 与子臂

现有 `Z00_BASE_A_CORE` 对 `Z01_BASE_C2_CORE` 只隔离了 **marker burden**：同一正文，无编号对插入 R02 编号，两边都只输出 `fact_sentences`。

它没有单独隔离另外两件事，所以只补零训练子臂，不改 Z00／Z01 的名字和主问题：

- `Z01M_C2_CORE_FACT_ONLY`：带编号，只输出事实；与 Z00 构成 marker burden 对照；
- `Z02C_C2_CORE_WITH_CITATION`：同样带编号，同时要求事实和 `evidence_ids`；与 Z01M 构成 citation burden 对照；
- `Z03U_C2_SINGLE_UNIT` 与 `Z03X_C2_CROSS_UNIT`：同样正文规模和近似编号密度，按冻结映射自然分层为单单元／跨单元；不为配平改切点，回答 cross-unit burden。

如果自然分层后两组规模或编号密度不可比，只报告缺口，不人工修题。

## 后续训练前的独立硬门

任何新 SFT 前必须另验：EOT/EOS 与 Qwen chat template 对齐、EOS 进入 labels、未被截断或 mask、packing 样本边界、训练／推理 `eos_token_id` 一致，以及既有输出的最早有效前缀、tail waste、正常停止率。

该门未通过，不训练。

后续 SEMANTIC_CORE 最小候选改为：

- C0：完整正式任务；
- J5：5% 独立 `fact_sentences` 容器；
- S5：完整正式 schema 不变，只加强 fact 字段 loss，降低或 mask 其他复杂字段 loss。

J5 或 S5 有稳定收益后才允许测试对应 10%。普通／特殊教材默认使用统一 schema 的分层混训，按 assistant target tokens 对账；“普通训完再用特殊教材覆盖”只保留为风险对照。

本阶段不执行上述训练，只登记门槛和缺口。

来源：Codex
