# Sample-mean loss 预检

✅ 这个包只证明一件事：“每道题先算自己的平均 loss，再让 batch 内每道题各算一票”的数学和真实 MLX 接线是对的。它不是 Qwen 训练权，也不证明 L6 一定会过。

派生 vendor 从原冻结 vendor 重新复制，没有叠加上一版 token-weighted reducer。163个非缓存文件一一对应，只有 `mlx_lm/tuner/trainer.py` 不同；该文件也只改了 `default_loss`。训练循环、GA4、optimizer、数据迭代和日志都没有改。

NumPy 证明用1～8个监督 token 的8道假样本：两种 pair 和8样本一次性参考的梯度、SGD、Adam状态一致，每道题贡献精确是1/8。旧 microbatch-token-mean 负控会随pair变化；global-token-mean不随pair变，但和sample-mean的结果明确不同。

真实 MLX 烟测用 Homebrew Python 3.12 和 MLX 0.30.6，走过派生 `default_loss → value_and_grad → GA4 → Adam.update`；两种pair和参考更新一致，GA1两样本等于两份样本loss平均，连续两个optimizer窗口都正确清空累计状态。这只是 tiny FP32 单元验证，没有加载 Qwen。

项目锁定 `uv` 环境不含 NumPy 和 MLX，所以它只跑源码／树／TRAIN96静态测试。NumPy与MLX部分明确由本机历史已成功的 Homebrew Python 执行，回执分开记录，不冒充锁定环境 MLX PASS。

本轮加载 Qwen、训练、推理、API、Notion、Git、指针和运行目录动作均为0。状态只到 `PASS_PREFLIGHT_NOT_RUN_AUTHORITY`。

来源：Codex
