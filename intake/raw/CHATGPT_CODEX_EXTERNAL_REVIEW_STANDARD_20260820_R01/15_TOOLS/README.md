# 工具

- `build_manifest.py`：为目录生成 MANIFEST.json 与 SHA256SUMS.txt。
- `deterministic_zip.py`：排序、固定时间戳生成可重现 ZIP。
- `validate_review_package.py`：检查路径、大小、Manifest、Secret 风险和 ZIP 完整性。
- `safe_extract_zip.py`：先检查再 staging 解压，阻断 path traversal / symlink / zip bomb。
- `compare_environment_receipts.py`：比较两个环境 JSON。

全部只用 Python 标准库。
