# Z57 默认合同热修测试夹具

这个目录只给 `tests/test_z57_default_contract_hotfix.py` 回放 2026-07-23 的旧版分类
合同。它不是现役 `tools/` 程序，也不参与默认链。

`neutral_extract.py` 保留来源文件的原始字节：

- 来源提交：`0550e45c9c4cafbda905e8d436f883d04c5e818b`
- 来源路径：`experiments/model_benchmarks/MB_X01_C0003_longcat_LongCat-2.0_thinking_t02_r01_20260723/inputs/runtime_dependencies/tools/zbatch_modules/neutral_extract.py`
- 文件大小：8,465 字节
- SHA-256：`f567ebef481dc33775ba7974c09744d185d6b8fa2b7b5e947e0be89f145dd7a7`
- 完整历史包：`model-benchmark-longcat-r01-interrupted-s07ea-v1`

测试会先核对 SHA，再把这份旧程序复制进自己的临时工作区。不要原地更新这份夹具；以后
若必须测试另一版，应新增明确命名的新夹具和新 SHA。

定向复验：

```bash
.venv/bin/python -m pytest -q tests/test_z57_default_contract_hotfix.py
```

来源：Codex
