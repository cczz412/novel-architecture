# 实验轻量结论卡

这个目录主要解决一个问题：**平时只看短结论，需要复现时再按仓外对象编号取固定零件。**

每张卡放在自己的目录里，固定只有四份文件：

| 文件 | 只负责什么 |
|---|---|
| `result_card.json` | 实验目的、组装方式、短结论、质量裁决和证据边界；这是结论真源 |
| `external_pointer.json` | 仓外对象编号和固定清单 SHA；不保存本机绝对路径 |
| `retrieval_profile.json` | 已登记的取件组合和未来复制安全规则 |
| `README.md` | 给人读的短报告；由前三份 JSON 确定性生成，禁止单独手改 |

仓外对象实际放在哪里，只认
[`governance/external_archive_registry.json`](../../../governance/external_archive_registry.json)。
哪些卡允许解析，只认
[`governance/artifact_retrieval_policy.json`](../../../governance/artifact_retrieval_policy.json)。
这样结论、位置和取件规则各管一件事，不会互相抄出三份真源。

当前首批两张卡分别保留 S-05-B v1 的失败现场和 v2 的通过现场。v2 不覆盖 v1。
正在运行的 R02 不在允许卡片中，取件器也没有自动发现、任意路径或扫描 `TEMP/` 的入口。

```bash
.venv/bin/python tools/experiment_artifact_retrieval.py check \
  --card-id s05b-historical-replay-v2

.venv/bin/python tools/experiment_artifact_retrieval.py resolve \
  --card-id s05b-historical-replay-v2 \
  --selection-id full-replay-payload
```

`check` 只核卡片、指针和固定仓外清单；`resolve` 只把清单翻成未来复制计划并写到标准
输出。当前没有复制、移动、删除或恢复命令。

以后普通模型实验仍把轻量卡放在自己的 `experiments/<实验编号>/` 里；只有共用的历史
测试回放卡放在本目录，避免给 S-05-B 硬造一个假的模型实验身份。

来源：Codex
