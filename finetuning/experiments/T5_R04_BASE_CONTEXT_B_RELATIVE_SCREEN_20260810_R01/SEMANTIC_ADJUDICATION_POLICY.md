# Base context Demo｜语义裁决合同

这份合同只判断预测事实与同题 Gold 是否表达同一个可独立追踪的核心事实，不判断它来自哪种正文范围。

- `SEMANTIC_EQUIVALENT`：预测句必须与且只与一条 Gold 核心事实完整等价。允许不改变核心命题的同义改写。
- `NOT_MATCH`：只覆盖 Gold 的一部分；把多条 Gold 混成一条；人物、来源主体、时间或状态变化不一致；否定与确定性不一致；或者增加了会改变结论的内容。
- `OUT_OF_SCOPE`：只用于预测内容明显属于本题编号负责区之外的事实。拿不准时记 `NOT_MATCH`。

`SEMANTIC_EQUIVALENT` 必须绑定一条现有 Gold fact_id；另两类必须把 matched_gold_fact_id 写成 null。

冻结的 READ2 R02 裁决按同一 case_id＋预测事实 SHA 直接复用，不重新判。READ1／READ4 新出现且没有冻结裁决的事实才进入新盲审队列。队列不得出现 arm、variant 或其他臂身份。

来源：Codex
