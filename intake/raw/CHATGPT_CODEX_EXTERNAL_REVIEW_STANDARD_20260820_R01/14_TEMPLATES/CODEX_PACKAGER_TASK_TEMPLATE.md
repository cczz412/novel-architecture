# 给本地 Codex 的外审打包任务

读取本规格包 `00_READ_ME_FIRST.md` 与 `02_MACHINE_POLICY.json`。

任务：把 `<LOCAL_SCOPE>` 打成 `<PROFILE>` 外审包。

必须：
- 识别 current、正式合同、结果票、背景和历史；
- 只装当前任务需要的最小充分材料；
- 生成 00_READ_ME_FIRST、Manifest、SHA、Build Receipt；
- 清除缓存和本地绝对路径；
- 检查 secrets、路径穿越、symlink、大小和峰值内存；
- Python 依赖准备 wheelhouse；Node 依赖准备 local tarball/vendor；
- 运行 `validate_review_package.py`；
- 给出 PACKAGE_ID、ZIP、SHA、解压大小、峰值 RAM 估算。

禁止：
- 不调用真实 API；
- 不把未授权真实作者数据塞包；
- 不把旧 current 冒充 current；
- 不依赖 Project memory 补状态。
