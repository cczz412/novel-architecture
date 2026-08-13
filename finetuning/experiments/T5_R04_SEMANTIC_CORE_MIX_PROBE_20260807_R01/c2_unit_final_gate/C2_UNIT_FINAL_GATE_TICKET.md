# C2_UNIT 最终机械闸门票

✅ **判词：C2_UNIT 机械闸门通过，可以进入 DEV_CORE／CORE gold 构造。atomizer R02 正式证明可用；剩余 1 条已改判为旧 A 位置来源缺失，并完成隔离。**

这次没有设计 atomizer R03，也没有改 R02 切分结果。只增加了一层明确位置合同：C2 renderer 必须读取 start/end，再机械映射成 B/T IDs；不能搜索 evidence 文字后挑第一次。

## 最终分母

| 项目 | 数量 | 处置 |
|---|---:|---|
| 旧 A facts | 397 | 审计总盘子 |
| 唯一位置可机械补回 | 396 | 纳入 C2 唯一映射机械分母 |
| `LEGACY_POSITION_AMBIGUOUS` | 1 | 不猜位置、不进唯一映射训练／评分事实分母 |
| 最终机械映射 | 396/396 | ✅ 100% |

唯一隔离项仍是：

```text
FS02B-006-S01 / 第 15 条
候选范围 565:576、643:654
没有权威位置来源
```

两个候选范围完整保留，但没有指定哪一个是真的。将来只有 canonical gold 补回权威 start/end，才能重新纳入。

## canonical A 新合同

以后每条 A fact 除了逐字 evidence，还必须保存：

- 稳定 fact_id；
- start/end；
- 0 起算、end 不包含的字符口径；
- source_text SHA；
- `source_text[start:end] == evidence` 验证。

当前旧数据没有 fact_id，本轮 sidecar 暂时使用 `canonical_sample_id + fact_index + fact fingerprint` 防止错绑。这是迁移办法，不是未来长期格式。

## R02 指标保持不变

- 平均 evidence_ids：1.7323；
- 3 个编号以内：377/396＝95.20%；
- 5 个编号以内：396/396＝100%；
- extra chars p50/p90/p95：10/32/35；
- 最大 extra chars：55；
- 跨单元 evidence：207/396＝52.3%；
- 每窗平均可见编号：21.875。

这些值与 atomizer R02 一致。题面编号密度和跨单元比例继续作为 Z00/Z01 的诊断项，暂不判失败。

## 训练与评分隔离

- 机械评分分母只排除 1 条歧义 fact，得到 396/396；
- 真实 SFT 不能把该 fact 从答案里静默删掉后继续训练，否则会教模型漏抽；
- 因此它所在的 `FS02B-006-S01` 整行暂时标为 C2 训练隔离，直到权威位置恢复；
- 当前原型中可完整形成单列表 C2 target 的是 39/40 行。

## 复验

- 位置 sidecar、隔离票、位置派生 facts、行隔离、指标和回执连续构建两遍；
- 9 份稳定产物全部逐字节一致；
- 396 条 renderer 全部只按 start/end 生成 IDs；
- 没有默认第一次、没有人工猜位置；
- atomizer R02、EVALUATOR_R02、旧成绩全部未改；
- 没有进入 DEV_CORE、Z00、Z01，没有推理或训练。

👉 **下一步已获准：开始构造 DEV_CORE／CORE gold。进入后仍要把每窗 21.875 个可见编号和 52.3% 跨单元率作为零训练诊断项单列。**

来源：Codex
