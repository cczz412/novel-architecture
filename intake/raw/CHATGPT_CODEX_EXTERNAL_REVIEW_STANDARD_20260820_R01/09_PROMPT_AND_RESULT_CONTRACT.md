# Prompt 与结果回包合同

## 1. Prompt 必须包含的九段

1. **唯一任务**：本轮只做什么。
2. **输入身份**：current / 历史 / 候选 / 外部报告 / fixture。
3. **权力边界**：只读、候选补丁、不得调用 API 等。
4. **读包顺序**：入口、current、合同、证据、历史。
5. **来源边界**：是否允许 Web、Library、Apps、项目外 memory。
6. **执行步骤**：解压、校验、运行、补写、finalize。
7. **失败规则**：FAIL/BLOCKED/UNAVAILABLE，不猜。
8. **结果目录合同**：必须生成哪些文件。
9. **聊天最终格式**：只留 ID、状态、ZIP、SHA、链接。

模板：`14_TEMPLATES/EXTERNAL_REVIEW_PROMPT_TEMPLATE.md`。

## 2. 外审材料身份优先级

```text
CZ 当前明确指令
> 正式合同 / 当前结果票
> CURRENT / 运行指针
> 有边界实验结果
> 共同背景板
> 外部研究
> 旧聊天回忆
```

Prompt 必须把当前任务适用的优先级写清，不能让模型自己猜。

## 3. 结果 ZIP 合同

### `SUMMARY.md`

人读结论：

- 一句话结论；
- 已验证；
- 未验证；
- 阻断；
- 下一步；
- 不能外推什么。

### `MACHINE_RESULT.json`

机器字段：

- run_id；
- package_id / parent SHA；
- environment；
- checks；
- status；
- output members；
- errors；
- model label；
- API/network count。

### `FINDINGS.md`

每个 finding：

- ID；
- 严重级；
- 证据路径；
- 影响；
- 建议；
- 是否可施工；
- 不确定性。

### `COVERAGE_RECEIPT.json`

- 实际读了哪些文件；
- 未读文件及原因；
- 扫描范围；
- current 版本；
- 旧版本；
- 解析失败；
- 是否过期。

### `FINALIZE_RECEIPT.json`

- 结果成员 SHA；
- ZIP `testzip`；
- 生成时间；
- 工具/模型标签；
- 失败计数。

## 4. Chat 最终消息

```text
RUN_ID=<...>
STATUS=<PASS/PARTIAL/FAIL/BLOCKED>
RESULT_ZIP=<filename>
SHA256=<...>
[下载结果 ZIP]
```

最多再加 1～3 条必须立刻知道的阻断。详细报告不要淹没下载链接。

## 5. Codex 回收

本地 Codex 收到 RESULT.zip 后 MUST：

1. 验证 ZIP 和 SHA；
2. 读 `FINALIZE_RECEIPT.json`；
3. 对比输入 package_id / parent SHA；
4. 把 advisory 与正式改动分开；
5. 本地复跑测试；
6. 只有获授权才合并或写 Git；
7. 将最终接受/拒绝结果写本地结果票。
