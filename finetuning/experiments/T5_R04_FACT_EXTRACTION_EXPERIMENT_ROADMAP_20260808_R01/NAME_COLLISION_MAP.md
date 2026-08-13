# 名称撞车说明

很多名字长得像，但测的不是一件事。以后结果票必须写完整实验臂 ID，不能只写“A、C2、D、E、F”。

| 容易混淆的名字 | 在哪里 | 真正含义 | 以后怎么叫 |
|---|---|---|---|
| `C2_FULL` | MICRO24 M1 | 正式四格式训练臂之一；输出事实对象和 `evidence_ids` | `LORA-FMT-C2-FULL` |
| P3 的 `C2` | P3 输入合同 | 在同一个 C2_FULL update72 上增加 1～2 句任务目的，不是新格式，也不是新 LoRA | `INPUT-P3-PURPOSE` |
| `C2_CORE`／Z01 | Semantic Core 零训练诊断 | 正文插入 B/T 编号，但输出只抽事实，用来测 marker burden | `INPUT-MARKER-Z01-C2-CORE` |
| 报告里的 `C2` | 外部研究材料 | 研究作者对某种编号／单元表示的简称，必须回到具体报告段落判断 | 只作研究别名，不得直接登记结果 |
| `D_RANGE` | MICRO24 M1 | 输出证据 ID 范围的本地格式训练臂 | `LORA-FMT-D-RANGE` |
| 报告里的 D | Deep Research 或旧讨论 | 可能指诊断层、阶段 D、文档分段或另一套比较，不自动等于 D_RANGE | 按来源重新命名 |
| `E_UNIT_QUOTE` | MICRO24 M1 | 输出单元 ID 加原文短引文的本地格式训练臂 | `LORA-FMT-E-UNIT-QUOTE` |
| 报告里的 E | Deep Research 或旧讨论 | 可能指 evidence-first、等 token 对照或章节方案 | 按来源重新命名 |
| `F_STAGE1_FACTS`／`F_STAGE2_CITATION` | MICRO24 渲染件 | 先抽 fact／status／speaker，再为已确认事实绑定 citation；这是 facts-first | `LORA-FS-STAGE1-FACTS`／`LORA-FS-STAGE2-CITATION` |
| evidence-first 两阶段 | 后续路线 | Stage A 先提 evidence，Stage B 再从已选 evidence 抽 fact；和上面的 facts-first 顺序相反 | `INPUT-EF-*` 与 `LORA-EF-STAGE-*` |
| 报告里的 F | 外部研究材料 | 不保证与本地 F 两阶段相同 | 只作研究别名 |
| 固定 contrastive pair | examples 第一轮 | 每题固定加入同一组安全最小对比例子 | `INPUT-EX-CONTRASTIVE` |
| 按边界检索 0～2 例 | examples 后续候选 | 按预先冻结的可观察边界检索 0～2 例；不是固定 pair 的别名 | `INPUT-EX-RETRIEVED-BOUNDARY-0TO2` |
| `A_CORE` | Semantic Core 零训练诊断 | 无 B/T 编号，只输出事实的输入表示 | `INPUT-MARKER-Z00-A-CORE` |
| `A_FULL` | MICRO24 M1 | 全文 evidence 字符串格式的独立 LoRA | `LORA-FMT-A-FULL` |
| `C0` | P3 | 当前极简输入对照 | `INPUT-P3-C0` |
| `C0` | Semantic Core 训练线 | 0% Semantic Core 的完整正式任务训练条件 | `LORA-SEMCORE-0` |
| `P4-GRAN-10/20/30` | P4 splitter | 每章约 10／20／30 个责任区 | 只用于完整章专项，不能写成旧 G10 |
| `FULL-META-M0/M1/C-Nonce` | 完整章位置专项 | 只改变位置 metadata；三臂必须先共同绑定一个相同的 WRNW read mode 与粒度 | 共同绑定 `META_WRNW_FIXED_CONDITION_R01` |

🔥 一个简单判断：名字相同不代表材料、输出合同、checkpoint 或问题相同。任何结果回写前，至少同时核对 `arm_id`、模型 SHA、数据池 SHA、Prompt／renderer SHA 和结果票 SHA。

来源：Codex
