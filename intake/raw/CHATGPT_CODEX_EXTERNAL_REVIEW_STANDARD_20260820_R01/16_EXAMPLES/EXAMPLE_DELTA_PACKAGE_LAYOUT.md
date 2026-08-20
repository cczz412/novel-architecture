# 示例：Delta ZIP

```text
M8_M11_DELTA_R03/
├─ 00_DELTA_READ_ME.md
├─ DELTA_MANIFEST.json
├─ changed/
│  ├─ mvp/file_a.py
│  └─ tests/test_a.py
├─ added/
├─ deleted_paths.txt
├─ receipts/
└─ SHA256SUMS.txt
```

必须绑定 Bootstrap / 前一 Delta 的 package ID 和 SHA。
