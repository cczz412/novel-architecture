# 输入合同跨模型复验计划

- 本地 Qwen 只筛候选，不替生产模型定版。
- Ling Tiny 工具链成熟后，只复验 C0 与本轮最多两个候选，不迁移 Qwen 的训练参数。
- 如果 Dense 与 Sparse 对同一输入变量结论一致，Doubao Mini 默认只验证一个最终合同。
- 如果两者在具体变量上冲突，Mini 最多做两臂仲裁；三臂必须另获 CZ 批准。
- 本阶段不调用 Ling、Mini 或 Lite。

来源：Codex
