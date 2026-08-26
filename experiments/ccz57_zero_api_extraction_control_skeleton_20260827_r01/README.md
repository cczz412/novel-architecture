# CCZ-57 0 API 抽取纠错控制骨架｜设计 R01

✅ 这份设计只解决一个问题：模型回包进入 M4 事实账候选区以前，小说辅助产品怎样保存原件、看出具体错在哪、只允许安全的小修改、保存新版本，并在没有新信息时停下来。

对应设计票：[GitHub Issue #165](https://github.com/cczz412/novel-architecture/issues/165)。

## 它处在产品哪里

当前 M3 读取责任段和模型回包，能够输出带原文引文的事实候选；M4 保存候选和作者确认后的事实。这个候选骨架放在两者之间：

```text
M3 模型原始回包
        ↓
0 API 控制骨架
  保存原件／机械检查／错误路由／版本与停损
        ↓
仍是候选的可读版本
        ↓
M4 候选区／M5 作者确认
```

它不替作者判断小说语义，也不把模型建议直接写成已确认事实。

## 本轮交付到什么程度

| 文件 | 说明 |
|---|---|
| [`01_MODULE_DESIGN.md`](01_MODULE_DESIGN.md) | 模块顺序、每步输入输出、允许与禁止动作 |
| [`02_DATA_CONTRACTS.md`](02_DATA_CONTRACTS.md) | Attempt、Diagnostic、Patch、Version 等对象怎样关联 |
| [`03_ERROR_ROUTING_AND_STATE_MACHINE.md`](03_ERROR_ROUTING_AND_STATE_MACHINE.md) | 每类错误走哪里、什么时候必须停 |
| [`04_REPLAY_ACCEPTANCE.md`](04_REPLAY_ACCEPTANCE.md) | 用现有真实 API 回件怎样验收下一轮实现 |
| [`05_NEXT_IMPLEMENTATION_CUT.md`](05_NEXT_IMPLEMENTATION_CUT.md) | 下一张施工票做什么、暂时不做什么 |
| [`schemas/`](schemas/) | 设计期 Draft 2020-12 Schema，不是现行产品合同 |
| [`fixtures/replay_cases.json`](fixtures/replay_cases.json) | 冻结的离线重放案例和预期路由，不包含新模型结果 |
| [`fixtures/contract_examples.json`](fixtures/contract_examples.json) | 8 类对象的最小可解析样例；路径和 SHA 是形状占位，不是运行证据 |
| `MANIFEST.sha256` | 本设计目录的文件清单；不把自己算进去 |

## 这轮不会发生什么

- API 调用、模型调用和网络发送都是 0。
- 不写运行代码，不碰现行 `novel-mvp`。
- 不覆盖已经入库的 505 文件证据包。
- 不把坏 JSON 猜修成“看起来合理”。
- 不自动补说话人、因果边或漏项。
- 不生成 `result_card.json`，因为实验还没有运行。

## 当前身份

状态是 `planned`。这份 PR 通过，只表示设计可以进入下一张 0 API 实现票，不表示控制骨架已经可运行，更不表示模型抽取质量已经提高。

来源：Codex
