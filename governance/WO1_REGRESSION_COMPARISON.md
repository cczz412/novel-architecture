# WO1 回归说明

- `check_current_freshness --check`：PASS；0 errors。
- 定向测试：58 passed、7 skipped；Ruff PASS。
- `main` 全套测试仍受两份 TEMP 夹具收集依赖与若干本机路径依赖阻断；这不是本工单引入。
- 工单 1 没有修改产品语义、需求、设计、合同或 runtime。
- `governance/tool_registry.json` 是约 190 KiB 的单体登记册；本云端连接器没有安全的小补丁写入接口。本票先由 README 与 `current_pointers.json` 提供正式入口，单体登记合并显式挂到工单 7，不伪装成已登记。
