# 本地真实数据 A/C2 对照计划

状态：**设计完成，未到开训门**。

## 只比较两个格式

- `REAL_A`：逐字 evidence；
- `REAL_C2`：局部 evidence IDs，由程序回填原文。

D_RANGE 和 E_UNIT_QUOTE 不进入这一轮。

## 开训前必须齐

- Production Canonical V1 已封版；
- 训练行全为 `TRAINING_CLEARED`；
- 作者级 split lock 通过；
- A/C2 两次机械派生字节一致；
- evaluator、人工语义尺子、解码和停止口径已冻结；
- 两臂的 base、训练配方、数据顺序、tokenizer 和更新预算完全相同。

## 多 seed

默认至少 3 个相同 seed 对。seed 清单必须在看见结果前写入执行锁。每个 seed 都从同一原始 base 独立训练：

```text
base → REAL_A_seed_n
base → REAL_C2_seed_n
```

禁止 A checkpoint 继续生成 C2，或只给较弱臂增加更新量。

## 分开报告

- Semantic Fact Precision／Recall／F1；
- strict Fact F1；
- status、speaker；
- evidence grounding；
- Schema、required keys；
- clean termination、复读、触顶和 tail waste；
- TRAIN→DEV 差距；
- 逐题 A 好／C2 好／相同；
- seed 均值、方差和方向一致性；
- 按题材、八态、证据跨度、编号密度和普通／困难层切片。

不制造一个让 token 节省抵消语义退化的总分。

## C2 晋级线

C2 只有同时满足下面条件才成为生产格式候选：

- 多 seed 的语义事实质量不劣于 A；
- evidence 绑定不退化；
- 没有新增系统性失败；
- 优势不是由某一个 seed 或少数 case 单独撑起；
- 节省的输出 token 是附加收益，不是掩盖语义差距的理由。

真实数据若反转，就按真实结果处理，不用 MICRO24 的旧排名强保 C2。

来源：Codex
