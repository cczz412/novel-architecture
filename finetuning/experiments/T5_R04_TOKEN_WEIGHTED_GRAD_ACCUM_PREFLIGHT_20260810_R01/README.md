# TOKEN-WEIGHTED-GA-PREFLIGHT-R01

✅ 结论：这份派生训练器通过了“小型分组不变性”预检，但没有训练权，状态仅为 `PASS_PREFLIGHT_NOT_RUN_AUTHORITY`。

这个主要解决固定相邻 pair 对梯度权重的干扰。旧训练器先把每个微批各自求平均，再把四个微批等权平均；短答案微批和长答案微批因此可能被当成同样重。派生版改成：先把每个微批的平均梯度乘回该批监督 assistant token 数，在一个 optimizer 窗口内累计分子和 token 总数，只在更新时除一次窗口 token 总数。

旧 vendor 没有修改。派生 vendor 完整保留 163 个非缓存文件，只有 `mlx_lm/tuner/trainer.py` 不同；`default_loss`、`iterate_batches`、`evaluate` 和训练日志字段保持原语义。派生训练器只接受 `world_size=1`，多进程会在编译和更新前硬停。

8 个 FP32 样本的监督 token 数为 1～8，总数 36。两种固定配对 A/B 和一次性 8 样本 reference 的新归一化梯度在 `rtol=1e-5、atol=1e-6` 内一致；SGD 参数变化、Adam 参数与 m/v/step 同样一致。旧 reducer 的 A/B 最大差异为 10，负对照成立。连续两个窗口都会归零，GA=1 与旧单微批路径一致，`world_size=2` 会硬停。

验证分两层。项目锁定环境用 Python 3.12.12 跑标准库 FP32 数值、AST 接线和树差异测试；这个环境没有 MLX，所以不把它写成“锁定环境 MLX PASS”。真实 MLX 接线烟测使用仓库历史训练所用的 Homebrew Python 3.12.12 与 MLX 0.30.6，tiny 模型直接走 `default_loss → nn.value_and_grad → mx.compile → token_weighted_optimizer_step → Adam.update`，A/B/reference 各只更新一次，结果同样在门内一致。这个 smoke 只是单元验证，不是 Qwen 训练。

这只证明“同一个 optimizer 窗口换 pair 后，归一化结果不再变化”，不证明教材有效、训练会变好，也不授权创建 density runner、执行票或训练 run。没有加载 Qwen，没有训练、推理、API、Notion、Git 或现役指针动作。

来源：Codex
