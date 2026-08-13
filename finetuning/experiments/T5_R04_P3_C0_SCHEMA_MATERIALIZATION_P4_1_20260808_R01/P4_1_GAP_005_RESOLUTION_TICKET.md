# P4.1｜P4-GAP-005 定点修补票

状态：`PASS_P3_C0_STRUCTURAL_SCHEMA_MATERIALIZED_NO_RUN_AUTHORITY`

✅ P3 C0 现役结构检查已经物化为独立 Draft 2020-12 JSON Schema。

这次修掉的是：未来工具不必再靠手读 renderer 或 24 条请求，去猜 `check_schema(value, "c2_full")` 的结构接受边界。

## 证明范围

- 冻结 M1 runner 整文件 SHA 已核为 `f2199b8f911894d8347878a97244ca3b41e8e19fc5297408fd6e8d18a2f81be7`；
- 冻结源码 AST 中恰有一个 `check_schema`；
- 函数原始源码位于 462–488 行，源码片段 SHA 为 `d640d941642bc80567a01dfd1595d2e4be44ac588a80f0214be67c0edfeba8b5`；
- `ALLOWED_STATUS` 和 `ARMS["c2_full"]["required"]` 从同一 AST 赋值节点机械读取；
- 全局依赖只含这两个登记值、类型名和 Python 内置项；
- 44 个定向变异、24 条冻结 assistant gold、24 条 P3 C0 历史输出的接受语言均无差异；
- `evidence_ids=[""]` 明确保留为合法宽松例；
- `status=[]` 与 `status={}` 明确保留为 oracle 异常例，Schema 均拒绝；
- 24 gold 与 24 历史输出的 `case_id` 各自唯一、逐项同序一致，顺序 SHA 写入机器回执；
- 目标化 corpus 连续构建两遍，稳定内容逐字一致。

## 施工中间态保留

- 直接导入完整 runner 的旧方案：`3 failed / 1 passed`。原因是 runner 顶层依赖 `yaml`，仓库锁定环境没有该依赖。此方案已失效，没有安装新依赖；
- AST 方案第一次：`2 failed / 2 passed`。原因是非字符串 status 用了不可哈希的 list，冻结函数抛出 `TypeError`；
- 当时曾把这个变异值换成数值 `7`。后续审查判定难例不能移出 corpus，因此最终版本恢复 `status=[]/{}`，并改用“接受语言一致、异常单列”的口径。没有改 Schema 或 runner。

## P4-GAP-005 的收口边界

独立结构 Schema 的缺口已修补。P4 原来的真实完整章不足、权利未知和不允许运行等硬停继续有效。

⚠️ 这张票不证明 Prompt 语义等价，不检查 ID 合法映射，也不判断事实语义。它也不证明旧 runner 与 Schema 对非法输入的失败方式相同。

## 权限

- 模型运行：未授权；
- 训练：未授权；
- synthetic 生成：未授权；
- 真实六臂：未授权；
- 74 组权利放行：未授权；
- Production Canonical：未授权；
- 修改 C0 Prompt、默认或 P4 状态：未授权。

来源：Codex
