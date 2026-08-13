# WO-01 三臂 Demo 结果票

状态：`HARD_STOP_SMOKE_RUNTIME_MLX_UNAVAILABLE`

静态部分通过：8 项测试全绿，三臂各 24 题，共同 48 条 gold；runner 明确把 system+user 两条消息完整送入。

实际运行停在 2 题 smoke 的模型加载前：项目锁定环境无法导入 `mlx`。因此：

- 模型加载：0 次成功；
- 模型输出：0 条；
- API 调用：0；
- 训练：0；
- 自动重试：0；
- 完整 72 题：未启动；
- 三臂评分和语义盲审：未产生。

这不是模型或三种上下文范围的失败，只是当前命令所用的 Python 环境没有本地 MLX 运行库。按 CZ 的 Demo 覆盖令，本轮不继续查环境、不换解释器，等待下一张定点运行环境工单。

烟雾失败原件：`runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_DEMO_R01/smoke_2/ABORT_RECEIPT.json`，SHA-256 为 `74bcee93270d3a1e8630a894e2a8bee031fb366d89f001660a74edf111f843e5`。

来源：Codex
