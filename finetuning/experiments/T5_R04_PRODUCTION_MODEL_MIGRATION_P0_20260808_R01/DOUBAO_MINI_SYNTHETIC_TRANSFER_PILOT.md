# Doubao Mini Synthetic Transfer Pilot

状态：**只设计，未训练，未调用 API**。

## 这轮只查一件事

✅ 用同一个 Doubao-Seed-2.0 Mini 基座，检查本地 Qwen 风洞里的 A／C2 格式排名能不能迁移。

这仍是 24 条合成训练＋24 条合成 DEV 的冒烟测试，不是生产性能验收。

## 模型身份

- Doubao-Seed-2.0 Mini：`primary_production_candidate`。
- 必须在执行锁中写死当时的确切 model ID／version，不用会滚动更新的模糊别名。
- 当前官方产品页已列出 Mini／Lite，但是否可精调、支持哪种训练方式和结构化输出，要以开工时的方舟官方列表和当前账号能力为准。

执行前必须出一张平台能力票：

- 精确 Mini 版本；
- 当前账号／区域是否可精调；
- 精调方式、数据格式、参数范围、计费和配额；
- 精调产物与评测端点的版本绑定；
- 结构化输出是否真正支持这个 Mini 版本。

任一项说不清就硬停，不从 Qwen 的做法猜豆包。

公开核对入口（只证明功能／模型入口存在，不授权施工）：

- [火山引擎豆包大模型产品页](https://www.volcengine.com/product/doubao/)；
- [火山方舟结构化输出（beta）](https://www.volcengine.com/docs/82379/1958523?lang=zh)；
- [火山方舟模型精调数据集格式说明](https://www.volcengine.com/docs/82379/1099461?lang=zh)。

## 推理基线

`MINI_BASE`

同一个未精调 Mini 基座分别读：

- TRAIN24／DEV24 的 A_FULL 题面；
- TRAIN24／DEV24 的 C2_FULL 题面。

这是一个模型的两种表示基线，不是两个训练臂。必须保存原始输出，后续 SFT 改善要相对它报告。

## 训练臂

只允许：

- `MINI_A_FULL`；
- `MINI_C2_FULL`。

两臂必须都从同一份 Mini 原始基座独立起训。禁止 A checkpoint 继续训成 C2，也禁止反过来做。

可选推理臂：

- `MINI_C2_CONSTRAINED`。

它只能复用 `MINI_C2_FULL` 的同一 checkpoint，在方舟真实支持稳定 structured output 时做 Free／Constrained 推理对照。它不是第三个训练臂。

若平台只有 JSON object，不能实现冻结的 Minimal Structural Schema，则按真实能力减项，不用 prompt 冒充 runtime constraint。

## 数据

TRAIN：

- Synthetic TRAIN24；
- 24 cases／43 facts／2 个自然空答案。

DEV：

- Synthetic DEV24 Set B R03；
- 24 cases／48 facts／2 个自然空答案；
- 身份继续是 `DEV24_SET_B_R03_DO_NOT_TRAIN`。

A／C2 必须从同一 canonical 机械渲染。两臂之间只允许 evidence representation 不同：

- A 输出逐字 evidence；
- C2 输出 evidence IDs，程序回填原文。

fact／status／speaker、负责区、窗口和分母必须完全一致。

## 不能从 Qwen 搬过来的参数

禁止默认携带：

- LR `3e-5`；
- 72 optimizer updates；
- LoRA rank 32；
- scale 0.125；
- micro batch；
- gradient accumulation；
- effective batch；
- target layers 16。

豆包训练参数必须以平台实际允许值、计费和小冒烟为依据另立合同。本文不预设一组豆包超参。

## 公平线

两臂必须保持：

- 同一 Mini 基座版本；
- 同一训练方式与超参；
- 同一 seed 口径；
- 同一数据顺序和分母；
- 同一训练预算；
- 同一推理参数、最大输出、retry 和 parser；
- 同一 evaluator 和人工语义尺子。

A 和 C2 的 assistant target token 长度天然不同，所以要单列实际目标 token 暴露量。但不得因 C2 更短就额外给它训练更新。

## 必须报告

- fact 语义 Precision／Recall／F1；
- status／speaker；
- Schema／required key／空数组逃避；
- repetition／max-token／正常结束；
- A 逐字 evidence 支持；
- C2 ID 合法性、绑定、缺失和额外 ID；
- 输入／输出 token；
- 延迟和调用费用；
- BASE→SFT 的变化；
- TRAIN24→DEV24 差距。

不制作一个能用 token 节省抵消语义退化的综合总分。

## 结论边界

这一层最多能说：

- A／C2 的本地排名在 Mini 上是否复现；
- 哪种格式值得进入真实小说 pilot；
- Mini 的结构化输出是否能作为 C2 推理优化候选。

不得说：

- C2 已成为生产格式；
- Mini 已通过真实网文验收；
- Synthetic DEV24 等于生产 blind。

来源：Codex
