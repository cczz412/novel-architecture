# TRAIN72 token-weighted reducer 诊断准备包

✅ 这个包已经把通过预检的新梯度累计方式接到旧 `density-paired` 单臂诊断上，但**没有训练、没有推理，也没有执行票**。当前状态只认 `PREPARED_NOT_AUTHORIZED_NOT_RUN`。

其实核心就一件事：旧实验与未来诊断使用完全相同的 72 行教材、相邻配对、模型、LoRA 参数、36 步训练、L6 请求、解码、评分和门槛；唯一变化是梯度累计怎么算权重。

- 旧做法：每个微批先各自求平均，再把 4 个微批等权合并。
- 新做法：每个微批的平均梯度先乘该批 assistant 监督 token 数，整个 optimizer 窗口只除一次总监督 token 数。

未来只能使用 `run_token_weighted_diagnostic.py` 的 `train` 和 `infer-l6` 两个受票命令。票不存在、身份或 SHA 不符时，runner 会在创建 run 目录和加载模型前停止。未来唯一 run 目录是：

`/Users/a1234/挣钱/小说架构/runs/T5_R04_READ1_TRAIN72_TOKEN_WEIGHTED_REDUCER_DIAGNOSTIC_R01/`

当前静态检查只验证：72 行／830 条事实／7 个空答案不变，旧 density 配方逐字段一致，新 trainer 与整棵派生 vendor 的 SHA 闭合，L6 Base 六行机械投影不变，评分逻辑与旧 scorer 等价，以及缺票时确实不会创建 run 目录。

机械门仍是原门：JSON 和完整 Schema 都要 6/6；两道空题必须输出 0；四道非空题每题至少 1 条；非法证据、复读、触顶和重复事实都必须为 0。机械不过就停，不生成盲审、不碰 REAL24；机械通过后才允许做 L6 盲审，语义 F1 不得低于同合同 Base。

这个包不提供运行权，也不包含 READ2／READ4、REAL24 路径、训练数据副本、模型或 adapter。

来源：Codex
