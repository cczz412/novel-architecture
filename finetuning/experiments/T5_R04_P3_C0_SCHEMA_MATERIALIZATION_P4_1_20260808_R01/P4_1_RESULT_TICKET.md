# P4.1 结果票｜P3 C0 结构 Schema 物化

状态：`PASS_P3_C0_STRUCTURAL_SCHEMA_MATERIALIZED_NO_RUN_AUTHORITY`

✅ 结构 Schema 已独立物化，接受语言差分为 0。

## 机械结果

| 检查面 | 结果 |
|---|---:|
| 目标化 mutation corpus | 44 条 |
| mutation 接受 / 拒绝 | 17 / 27 |
| mutation 接受语言不一致 | 0 |
| oracle 正常返回样本布尔不一致 | 0 |
| oracle 异常 | 2 条，均为 TypeError |
| 冻结 assistant gold | 24/24 两边接受 |
| gold 接受语言不一致 | 0 |
| P3 C0 历史输出 | 24 条 |
| 历史输出结构合法 / 不合法 | 18 / 6 |
| 历史回放接受语言不一致 | 0 |
| gold / 历史 case_id 配对 | 24 条唯一且逐项同序 |
| 确定性构建 | 2 遍逐字一致 |

## Oracle 身份

使用 `FROZEN_SOURCE_AST_ORACLE`。它核完整 runner SHA 后，从同一冻结 AST 机械取出：

- 唯一的 `check_schema` 原函数节点；
- `ALLOWED_STATUS`；
- `ARMS["c2_full"]["required"]`。

它没有手写等价函数，也没有复制一份状态或字段常量充当真源。函数原始片段和依赖清单已写入 `P3_C0_SCHEMA_SOURCE_BINDING.json` 与回执。

## 施工中间失败

- 完整模块直接导入：`3 failed / 1 passed`，根因是锁定环境缺 `yaml`；
- AST 初版：`2 failed / 2 passed`，根因是 list 类型 status 让冻结函数抛 `TypeError`；
- 临时把 list 换成数值 7 的方案已失效；最终恢复 `status=[]/{}`，异常单列；
- 现役修订测试和 Ruff 结果只认最终回执。

这两次失败都留在回执，没有被改写成从未发生。

## 结论怎么读

这份 Schema 只回答：“JSON 已经解析成功后，它是否落在现役 C2 `check_schema` 的接受集合中？”

旧 oracle 对两条不可哈希 status 会抛异常，而 Schema 会正常拒绝。两者都不接受，但失败方式不同。它不回答事实对不对、证据 ID 是否存在、证据是否最小充分，也不授权任何模型运行。

## 未做事项

- 没跑模型或 API；
- 没训练；
- 没改 Prompt、renderer、runner、gold、P3/P4 sealed；
- 没生成 synthetic 文本；
- 没写 Notion、没改 Git；
- 没切现役指针或默认；
- 没放行 74 组权利；
- 没生成 Production Canonical。

来源：Codex
