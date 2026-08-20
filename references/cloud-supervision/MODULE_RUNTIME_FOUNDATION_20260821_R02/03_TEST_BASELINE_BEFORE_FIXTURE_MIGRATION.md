# 当前代码测试基线

## 能诚实确认的结果

在分支 `codex/module-runtime-foundation-20260819-r01`、提交 `01efc50` 上，排除两份依赖未版本化 TEMP 夹具的旧测试后，其余小说辅助产品模块测试结果是：

```text
1542 passed in 48.41s
```

Ruff 对 `novel-mvp/mvp` 和全部 `tests/test_novel_mvp_*.py` 检查通过。

## 为什么不是写“全套通过”

直接收集全部 `test_novel_mvp_*.py` 时，测试在下面这份文件停住：

`tests/test_novel_mvp_m3_admission.py`

它要读取未进入 Git 的文件：

`TEMP/t03_parallel_r13_m1_m2_20260815_r01/rm06_m3_admission_gate_20260816_r01/REGRESSION_FIXTURE_LOCK.json`

同类依赖还存在于：

`tests/test_novel_mvp_chapterization.py`

所以当前只能写：

- 其余 90 份模块测试文件合计 1542 项通过；
- 这两份旧测试在干净分支不具备完整复跑材料；
- 不能把“收集失败”说成代码断言失败，也不能把缺失夹具临时伪造出来追绿；
- 不能把 1542 个机械测试写成真实小说内容质量已经证明。

## 本轮外审怎样使用

ChatGPT Pro 应把这项缺件列入测试可移植性问题，但不要因此否定所有当前模块测试。判断局部能力时，仍需阅读它自己的直接测试、成功路径和失败反例。

来源：Codex
