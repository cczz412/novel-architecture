# <TASK TITLE>

本文件是唯一任务。请完整读取附件，但只按本任务范围工作。

## 输入
- `<BOOTSTRAP_OR_DELTA.zip>`
- Project Sources：`<LIST>`

## 身份
- 正式 current：`<...>`
- 历史材料：`<...>`
- 外部报告：`<...>`
- 候选补丁：`<...>`

## 来源边界
只使用当前 Project Sources 和当前聊天附件。不得使用项目外 memory、Web、Library 或 Connected Apps；资料不足就明确写不足。

## 权限
- 允许：只读分析 / 运行本地测试 / 生成候选补丁（按实际选择）
- 禁止：API、训练、Git push、Notion、生产写入、真实密钥

## 执行
1. 校验 ZIP 与 Manifest。
2. 安全解压到 staging。
3. 读取 `00_READ_ME_FIRST.md`。
4. 按 current → 合同 → 结果 → 背景顺序。
5. 运行明确允许的测试。
6. 把详细结果写结果目录。
7. 运行 finalize，生成 RESULT.zip。

## 失败
失败写 FAIL/BLOCKED/UNAVAILABLE；不得猜，不留下半套正式结果。

## 结果必须包含
SUMMARY.md / MACHINE_RESULT.json / FINDINGS.md / COVERAGE_RECEIPT.json / FINALIZE_RECEIPT.json / MANIFEST.json / SHA256SUMS.txt。

## 最终聊天
RUN_ID=...
STATUS=...
RESULT_ZIP=...
SHA256=...
[下载结果 ZIP]
