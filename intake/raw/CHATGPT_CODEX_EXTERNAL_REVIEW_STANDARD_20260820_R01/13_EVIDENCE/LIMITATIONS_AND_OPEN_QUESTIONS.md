# 限制与需要复测的条件

## 已足够指导工程，但不是平台 SLA

- CPU/RAM/磁盘规格；
- Project Source raw mount 路径；
- 同 Chat 模型切换不重置；
- ZIP 当前不做语义展开。

平台版本变化后，按本页触发复测。

## Project memory

当前证据足以规定“不当状态库”，但不足以精确量化“能记住多少”。若未来要依赖 Project chat handoff，需做正确传入 BPRIME_RUN_ID 的 exact recall 复测。

## Library

官方支持人工 Library；assistant-side 自动寻找结果 ZIP失败。未来如果产品新增 Library 自动引用，需要重新测试。

## 存储上限

官方页面对不同存储层的数字存在并列表述。不要把 25 GB / 100 GB 任何一个写成跨全部能力的固定总量。

## 触发重新探针

- ChatGPT 模型大版本更换；
- Data Analysis 后端更新；
- Project Sources UI/索引变化；
- ZIP 被官方列为可语义解析类型；
- Project file limit 或 Library 规则变化；
- 本地包需要超过 450 MiB / 8 GiB extracted / 2.5 GiB RAM；
- 真实任务开始依赖联网、Docker、GPU 或 daemon。
