# Doubao Mini Evidence-First Oracle 计划

状态：**候选实验设计，未训练，不代表生产架构已决定**。

## 要搞清的事

一阶段 C2 让模型一次完成证据选择、事实写作、status、speaker 和对象结构。

evidence-first 把它拆成：

```text
先找证据
→ 程序验真并回填
→ 再写事实、status、speaker
→ 程序组装最终 JSON
```

这可能降低一次生成的负担，也可能因 Stage A 漏证据而出现级联错误。只能通过成对实验判断，不先把它写成主架构。

## 三个正式比较条件

### 1｜One-stage C2

模型一次输出：

- fact；
- status；
- speaker；
- evidence_ids。

程序负责：

- evidence 原文回填；
- ID 校验；
- 去重；
- 稳定排序；
- 最终 JSON 与 Schema。

这是强基线，不能为了突出两阶段而给它更差的 prompt、更少的训练或更严的解码。

### 2｜Gold Evidence Oracle

直接给 Stage B 正确的 gold evidence，让它输出：

- fact；
- status；
- speaker。

它回答：

> 如果证据搜索完全正确，Mini 后半段能力的上限是多少？

这是 oracle 诊断，不是可上线方案。成本表中必须把它标为“没有 Stage A 调用的上限探针”，不得拿它冒充生产成本。

### 3｜Predicted Evidence Pipeline

Stage A：

```text
正文
→ evidence IDs
```

程序：

```text
ID 校验
→ 去重和顺序固定
→ 原文逐字取回
```

Stage B：

```text
已选 evidence
+ 必要 context-only
+ speaker candidates
→ fact
→ status
→ speaker ID
```

程序：

```text
canonicalize
→ speaker ID 回填
→ evidence 回填
→ 去重
→ 排序
→ 最终 JSON
→ Schema validation
```

这个条件才是可部署的 evidence-first 候选。

## Stage A 合同

目标：**高召回、输出短、不抄原文。**

模型只输出 evidence IDs，不输出 fact／status／speaker／evidence text。

程序必须拒绝：

- 题面中不存在的 ID；
- 只属于 context-only 的 ID；
- 重复 ID；
- 不符合冻结顺序的 ID。

程序可以校验和排序，不能帮模型补上漏掉的 evidence。

## Stage B 合同

Stage B 只看：

- Stage A 选出的 evidence；
- 早已冻结的必要 context-only；
- 机械生成的 speaker candidates。

Stage B 不得偷看整个负责区来补 Stage A 漏选，否则无法测到级联错误。

speaker candidates 需要稳定 ID，程序负责回填人名或 `null`。模型不负责临时生成一个候选表里不存在的 speaker。

## 确定性程序负责到哪里

程序负责：

- evidence ID 和 start/end 校验；
- evidence 原文逐字回填；
- speaker ID 回填；
- canonicalization；
- 去重；
- 稳定排序；
- 最终 JSON 组装；
- Schema validation。

程序不负责：

- 修改 fact 语义；
- 把错 status 猜成对 status；
- 为漏抽事实自动补写；
- 把一个非法结果洗成正确结果。

## 必须预注册的读数

### Evidence

- recall；
- precision；
- exact-set；
- missing ID；
- extra ID；
- nonexistent ID；
- context-only ID；
- 每个 fact 平均 ID 数。

### Fact 与字段

- semantic fact Precision／Recall／F1；
- unsupported fact rate；
- omission；
- status 合法率和正确率；
- speaker ID 合法率和正确率；
- duplication。

### 工程代价

- 端到端 latency；
- 每阶段 input／output tokens；
- Mini 调用次数；
- Mini 调用费用；
- 程序校验失败率；
- 整条请求成功率。

不使用可互相抵消的总分。

## 怎么判断这条路值不值得

✅ 只有出现这组证据才值得继续：

- Gold Evidence Oracle 相比 One-stage C2 有稳定语义收益；
- Predicted Evidence 能保住大部分 Oracle 收益；
- Stage A evidence recall 不构成明显天花板；
- unsupported fact／omission／duplication 没有退化；
- 多一次 Mini 调用的延迟和费用与质量收益匹配。

❌ 如果 Oracle 都不优于 One-stage C2，说明当前瓶颈不主要在 evidence 搜索，应停止两阶段扩张。

❌ 如果 Oracle 很好、Predicted Evidence 很差，说明 Stage A 召回是主要堵点，不得跳过它宣布 evidence-first 可上线。

来源：Codex
