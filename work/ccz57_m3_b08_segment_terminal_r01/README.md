# M3 B-08｜责任段候选终态与后续适配门

这个目录主要解决一件事：一个事实抽取责任段结束以后，系统要留下可信的候选终态封条，后面的模块才能分清“这段真的处理完了”“合法没有候选”“只完成了一部分”还是“运行失败了”。

你可以直接理解成：B-07 管这次运行有没有停稳，B-08 管这一段结束时交出了什么。B-08 不抽正文、不让模型更聪明，也不把候选写成正式事实。

## 只保留一个持久对象

- `M3_SEGMENT_CANDIDATE_TERMINAL_RECEIPT`：不可变的责任段候选终态原件；
- `B08SegmentTerminalStore`：唯一 writer；
- `B08TerminalReadService`：只读服务；
- `ExactCurrentTerminalView`：读取时判断旧封条今天是否仍然有效；
- `AdapterReadySegmentView`：读取时判断后续适配器能不能消费。

两个视图都不落库。没有 view writer、Checkpoint、CommitIntent、pointer snapshot 或第二套 current 真源。

## 调用方不能自己填结果

writer 的公开参数只有项目、run、操作号和预期的 epoch／state revision。产品结果、覆盖、来源 revision、current pointer、current CandidateVersion 和可选 B-06 MergeReceipt，都必须由构造 writer 时绑定的权威 reader 从同一 SQLite 事务里读取。

这样可以挡住一种很危险的假成功：调用方随手说“这一段完整了”，B-08 就照单全收。

## B-07 怎样发布 B-08

1. B-07 进入现有 `ACTIVE + FINALIZING`；
2. B-08 在共享 SQLite 事务域里写一份终态原件；
3. B-08 返回原件引用和可机械读取的工件定位；
4. B-07 用现有 `advance` 把 `last_component_observation` 绑定到同一定位和 SHA；
5. 完整结果进入 `SUCCEEDED`，部分／阻断结果进入 `STOPPED`。

B-08 已写但 B-07 还没绑定时，这份原件只是历史写入，两个视图都不会把它当成已发布结果。同操作号重放会回到同一份原件，不会生成第二份。

## 两层结果不能混

产品结果说明“发生了什么”：

- 有候选；
- 没有变化；
- 合法零条；
- 不适用；
- 证据不足；
- 抽取失败。

交付形状说明“交付完整到哪”：完整、合法空、部分完成、被阻断。

比如“合法零条”可以是完整结果；“抽取失败”不能冒充合法空结果。`reason_code` 只解释原因，不能替代这两层判断。

## 旧 run 为什么不能回来覆盖

原件同时绑定：

- 责任段来源 revision 和 segment scope；
- current pointer、pointer generation 和 CandidateVersion；
- B-07 的 logical run generation、run epoch 和发布观察；
- child 路线上的 exact B-06 MergeReceipt。

resume 增加 epoch，reopen 新建 run 并增加 logical run generation。旧原件不修改，读取服务会把它现算成过期或被新运行替代。`STALE` 不落盘。

## 当前证明到哪

当前使用合成引用和临时 SQLite：

- 0 小说正文读取；
- 0 模型／API／网络调用；
- 0 CandidateVersion、pointer、MergeReceipt、正式事实和十本账写入；
- 证明幂等、并发单赢家、事务失败回滚、resume、reopen、来源／pointer 漂移、B-06 child 精确绑定，以及派生视图不落库。

CCZ-142 的产品级分类／覆盖 reader 仍是接线边界。本目录只冻结接口和机械拒绝规则，不修改 CCZ-142 runtime，也不把实验 JSON 冒充产品权威。

## 运行

在仓库根目录执行：

```bash
uv run --locked pytest -q work/ccz57_m3_b08_segment_terminal_r01/test_b08_segment_terminal.py
uv run --locked pytest -q work/ccz57_m3_b07_local_recovery_stop_r01/test_b07_local_recovery.py work/ccz57_m3_b06_commit_core_r01/test_b06_commit_core.py work/ccz57_m3_b01_candidate_version_r03_5/test_b01_contract.py
uv run --locked python work/ccz57_m3_b08_segment_terminal_r01/self_check.py
uv run --locked ruff check work/ccz57_m3_b08_segment_terminal_r01
```

来源：Codex
