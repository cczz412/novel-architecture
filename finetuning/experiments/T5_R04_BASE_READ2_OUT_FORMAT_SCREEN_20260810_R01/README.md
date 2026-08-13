# Base＋READ2 输出形式 Demo｜只准备

✅ 这个包只固定两个未来推理格：OUT3-IDRANGE 和 OUT4-IDQUOTE，共 48 题。当前状态是 `PREPARED_NOT_AUTHORIZED_NOT_RUN`，没有创建执行票或 run 目录。

这不是 R02 里的训练版 OUT Round2。这里固定使用未微调本地 4B、READ2 和 REAL24，只看输出形式的差别。

## 三格怎么对比

- OUT2-IDLIST 是现成共同格，直接绑定旧 BASE_READ2 的 24 行结果，不重跑。
- OUT3-IDRANGE 的 `evidence_ranges` 每条事实必须恰好只有一个字符串：连续证据写成 `T01-T03`，单个证据写 `T01`。把连续证据拆成多个字符串也算违约。
- OUT4-IDQUOTE 输出最小充分的 Txx 集合和一段逐字原文。引文只检查真实性，不伪造“唯一标准引文”。

runner 里的确定性 builder 从已冻结 READ2 题面生成两套请求。每题的 user 文字逐字不变，只整体替换 system 里的输出合同；新 system 不保留旧 `evidence_ids` 合同，避免两种规则打架。

## 已知缺口

- 两个新合同还没有跑模型，所以格式和事实表现都是未知。
- 未来即使机械门通过，新事实表述仍要进同题匿名盲审。
- 本包只能产生当前本机 Demo 选择，不会自动授权训练、OUT 下游、Mini 或生产。
- OUT2 始终是已冻结的现任形式；两个新格不合格或事实 F1 没有超过 OUT2，就继续保留 OUT2。这个相对选择不等于 4B 绝对可用，也不等于 Mini 或生产合格。

具体冻结身份和门槛看 [SPEC.json](SPEC.json)。

来源：Codex
