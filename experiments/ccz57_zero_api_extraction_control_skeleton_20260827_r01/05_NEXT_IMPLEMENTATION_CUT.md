# 05｜下一轮实现切片

## 推荐只开一张实现票

下一张票先做“只读导入与机械门”，不要同时做完整 Patch 控制器。

建议票名：

> 施工｜CCZ-57 0 API 骨架 A：不可变 Attempt＋两层 JSON／Schema／evidence 重放

## 写集

```text
experiments/ccz57_zero_api_extraction_control_skeleton_20260827_r01/program/
experiments/ccz57_zero_api_extraction_control_skeleton_20260827_r01/tests/
experiments/ccz57_zero_api_extraction_control_skeleton_20260827_r01/replay/
```

`tests/` 只保留这项实验的最小机械测试，并纳入本实验 MANIFEST；不进入根 `tests/`，也不冒充跨场景工具。

## A 票只实现什么

1. 只读导入仓内真实请求、stdout／stderr、meta 和冻结题面；
2. 生成不可变 Attempt；
3. 校验来源 SHA、运输状态和模型身份；
4. 分开解析供应商外壳与 content；
5. 在普通 JSON 解析前检测重复键；
6. 运行冻结 v2.1 Schema；
7. 定位 evidence 的连续字符区间和命中次数；
8. 只处理 BOM、首尾空白和单层完整代码围栏；
9. 跑 R01～R09，生成符合 Schema 的 ReplayReport；
10. 证明网络请求、模型调用和 Token 消耗都是 0。

## A 票不实现什么

- 自动删除空 `speaker`；
- 通用坏 JSON 转录；
- 稳定事实 ID 的实际 Patch 合并；
- 自动说话人、因果、时间、指代和补漏；
- 独立模型验证器；
- M3/M4 runtime 接线；
- result_card 或产品完成声明。

## A 票验收后再开的 B 票

B 票才实现：

- 旁路稳定事实 ID；
- 人工冻结 Patch 测试件；
- 基线 SHA、允许字段和未触碰字段门；
- 父子 ResultVersion；
- 错误指纹、A→B→A、无进展和回归停损；
- RelationCandidate 的旁路保存。

B 票仍然是 0 API。A、B 都通过以后，才向 CZ申请 6～8 例的新 API 小实验。

## 为什么分成 A、B

A 票只读，没有修改候选内容，最容易证明没有污染证据。B 票开始应用 Patch 和生成版本，错误代价更高。分开以后，出现问题时能明确判断是“看错了回件”，还是“改错了结果”。

来源：Codex
