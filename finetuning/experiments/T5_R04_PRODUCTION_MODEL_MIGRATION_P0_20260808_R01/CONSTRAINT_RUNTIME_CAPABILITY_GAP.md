# C2 结构约束运行时能力缺口

状态：**HARD STOP，未运行 C2_FREE／C2_JSON_GRAMMAR／C2_MINIMAL_STRUCTURAL_SCHEMA 新实验**。

## 为什么停

当前 M1 C2 update72 的真实回放链是：

```text
Qwen3-4B-Instruct-2507 同一基座
+ C2 update72 adapter
+ MLX-LM 0.30.7
+ tokenizer.apply_chat_template(...)
+ stream_generate(...)
+ greedy temperature=0
```

这条链有通用 `logits_processors` 插口，但“有一个可以改 logits 的钩子”不等于“已经有可用的 JSON Grammar／JSON Schema 约束后端”。

本地 Python 3.12 环境审计结果：

| 能力 | 结果 |
|---|---|
| Outlines | 未安装 |
| XGrammar | 未安装 |
| llguidance | 未安装 |
| LM Format Enforcer | 未安装 |
| Guidance | 未安装 |
| MLX-LM 自带 JSON Grammar／Schema compiler | 未发现 |
| MLX-LM 自带的 logits processor | 只有 logit bias 和 repetition penalty |

还缺的不只是一个包：

- 没有被冻结的 Grammar／Schema 后端及版本；
- 没有 MLX token ID 与该后端之间的适配层；
- 没有证明 JSON Grammar 与 Minimal Schema 能使用同一个后端；
- 没有冷编译、暖延迟、accept 停止原因和首个分叉 token 的计量实现；
- 没有同 prompt 字节、同权重、同精度的后端等价票。

所以，现在如果继续，只有三种做法：

1. 临时安装一个新后端并自己写适配层；
2. 换成 HF／vLLM／llama.cpp 等整套推理引擎；
3. 用 prompt 或生成后修补假装是 constrained decoding。

这三种都超出本工单冻结的单变量范围。因此按工单硬停。

## 为什么没有先重跑 Free

工单要求先审计同一运行时能否接入约束。前置能力已经失败，再跑 Free 不会让 Grammar／Schema 臂变得可运行，只会产生一份没有对照臂的重复输出。

旧 M1 C2 update72 DEV24 的 24 条 Free 原始输出和回执原样保留，但本票不把它冒充成新三臂实验里的新 Free 运行。

## 什么条件下可以重开

只有 CZ 另行批准运行时能力试作，并且以下材料先齐全，才能重开：

- 选定的约束后端、固定版本和本地安装回执；
- MLX-LM 适配层的源码、SHA 和最小测试；
- 同一权重、tokenizer、chat template、prompt 字节、精度、加载路径和解码参数的机器票；
- Grammar 与 Schema 确认共用同一约束后端；
- 无后处理修补、无 retry；
- 能把 `model EOS`、`grammar accept`、`max token`、`error` 四种停止原因分开。

在此之前，本地 C2 只保留为本地 Qwen 格式候选，不修训练器，不重训 C2，不换引擎。

来源：Codex
