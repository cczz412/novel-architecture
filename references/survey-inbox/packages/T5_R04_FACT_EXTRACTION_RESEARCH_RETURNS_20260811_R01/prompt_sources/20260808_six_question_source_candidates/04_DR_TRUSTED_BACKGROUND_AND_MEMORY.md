# Deep Research 3-4｜作者确认背景卡、正文确认背景和模型猜测背景，怎样安全地帮助小说事实抽取？


## 项目背景与不可误解的边界

我们正在做中文长篇小说事实抽取系统。模型读取一个局部小说窗口，输出事实、状态、说话人和逐字证据／证据 ID。事实会进入长期状态库，供后续检索、连续性检查和章节写作使用。

当前已知：

- 本地 Qwen3-4B 只是低成本代理实验台，不是生产模型；
- 本地 MICRO24/M1 中，C2（输出 evidence IDs）在未见合成 DEV24 上的语义事实 F1 高于逐字 evidence，但这个排名不能直接外推到生产模型；
- 未来生产候选是 Doubao-Seed-2.0 Mini，Lite 用于复杂案例升级；云微调成本高，不能用来做大规模多臂探索；
- 等 Ling 3.0 Tiny 可本地下载和微调后，它会作为稀疏架构代理模型，只复验已经筛出的 2～3 个关键结论；
- 当前真实 Production Canonical 尚未构造：P2 只剩 73 行／632 facts 机械合格，而且全部是特殊教材；A v2.7 的 314 行仍缺训练权利；
- 因此近期实验应优先使用合成 TRAIN24/DEV24、已有冻结考卷或权利明确的材料，不得把权利不明数据拿来训练。

我们现在要研究的不是输出格式，而是 **Input Context Contract**：模型在正文之前到底应该收到哪些信息、多少信息、以什么顺序收到，才能提高事实抽取准确率而不产生锚定、过抽、未来信息泄漏或背景污染。

请把结论分成三层：

1. 对本地 Dense Qwen 代理模型的可验证建议；
2. 对未来 Sparse Ling Tiny 的复验建议；
3. 对 Doubao Mini/Lite 的生产迁移建议。

不得把任何一家模型或某个参数规模的结果自动外推为通用规律。


## 当前问题

很多信息很难只读当前 5～10 章就百分百确定，例如：主角、别名、金手指、系统类型、稳定人物关系、当前持有物、隐含 speaker。

我们考虑做一个可选的作者增强流程：

```text
模型读前 5～10 章
→ 生成背景卡草稿＋逐字证据＋unknown
→ 作者确认／修改／保持未知
→ 后续抽取把已确认背景作为辅助上下文
```

背景分级：

- `AUTHOR_CONFIRMED`：作者明确确认；
- `TEXT_CONFIRMED`：正文有明确证据；
- `MODEL_SUGGESTED`：模型推测，只能展示，默认不能作为抽取真值。

背景只能帮助消歧，不能单独制造当前正文事实；必须带 `as_of_chapter`，防止未来信息偷渡到过去。

## 请系统调查

1. Agent memory、entity memory、user profile、knowledge card、world model、long-term memory 在 LLM 系统中的成熟经验。
2. Trusted memory、uncertain memory、model-generated memory 如何分级；是否有 provenance-aware memory schema。
3. 错误背景／记忆污染／context poisoning 对下游抽取和推理的影响。
4. 人类确认一小张背景卡，能否显著提高实体消歧、别名、speaker、状态连续性；有什么 HCI 或 human-in-the-loop 证据。
5. 模型先提议、作者只确认／修订，与让作者从零填写相比，成本和错误率如何。
6. `unknown`、`not yet revealed`、`author secret` 是否应该是正式状态。
7. 背景卡应保存哪些字段：人物 ID、别名、稳定关系、能力、系统类型、状态、来源、置信度、时间有效范围。
8. 背景如何版本化：`as_of_chapter`、valid_from、valid_to、superseded_by。
9. 当前正文与背景冲突时，谁优先；如何避免背景覆盖新的明确事实。
10. 背景是否应该直接进入 extractor Prompt，还是先经过检索，只取与当前窗口相关的 5～20 条。
11. 背景越全是否越好；minimal character/alias card 与 full world bible 的 trade-off。
12. 是否应该把 prior confirmed state 与 stable background 分成两种 channel。
13. 作者确认背景是否可以当产品世界设定真值，但不能当正文 evidence；这类双层真值有没有成熟设计。
14. 如何检测模型因背景产生 unsupported extraction。
15. 如何设计 noisy-background stress test，验证模型是否会盲信背景。

## 最终必须给出

A. 10～15 项最相关研究／工业实践；
B. `AUTHOR_CONFIRMED / TEXT_CONFIRMED / MODEL_SUGGESTED` 分级是否合理；
C. 推荐的背景卡 schema，必须包含 provenance、certainty、as-of 时间和训练／推理资格；
D. 一个本地对照矩阵：

```text
B0：无背景
B1：最小 confirmed 人物＋别名
B2：B1 + confirmed stable background
B3：B2 + confirmed previous state
B4：Noisy background stress test（只做安全测试）
```

E. 如何保证背景不能单独贡献 evidence；
F. 预注册指标：semantic P/R/F1、speaker、alias resolution、状态变化、background-only unsupported fact、冲突处理、过抽；
G. 作者交互原型：确认／修改／未知／尚未揭晓，怎样降低工作量；
H. 哪些背景字段值得给 extractor，哪些只供作者界面使用；
I. 什么时候自动更新背景，什么时候必须作者确认；
J. Dense Qwen、Ling Tiny、Doubao Mini/Lite 上的复验顺序；
K. 明确列出不能做的事：未来剧情、大纲、模型低置信猜测不得当作当前事实真值。

不要把“更多记忆”默认当成更好；请重点调查错误记忆和锚定风险。
