# M3 B-07｜本地恢复与停损核心

这个目录主要解决一件事：事实抽取或局部修补中途停下、崩溃或失去权限以后，系统仍能只靠本地原件判断“还能不能继续、该不该开新 run”，并且旧进程不能在停止后偷偷把结果写进去。

你可以直接理解成：B-01～B-06 负责事实候选和安全修改，B-07 负责这次运行的刹车、接管和恢复。它不让模型变聪明，也不再加一轮 API。

## 只保留三种持久内容

- `CurrentRunState`：每个 run 一份受控可变的当前状态，是恢复真源；
- `StopReceipt`：说明为什么停止，并且和 `STOPPED` 状态在同一个 SQLite 事务里出现；
- `InternalDebugRecord`：短期维护记录，只存引用、哈希和计数，写失败不影响停止。

`ResumePlan` 每次从当前本地权威重新计算，不落盘。独立 Checkpoint、CommitIntent、provider checkpoint、持久 ResumePlan 和失败提交回执都没有新增。

## 为什么能挡住旧 run

`CurrentRunState` 带两把锁：run 的代次 `run_epoch`，以及状态版本 `state_revision`。

- 同一个非终态 run 被新进程接管时，epoch 加一；
- 每次更新都用 epoch＋revision 做 compare-and-swap；
- B-06 真正提交 child、pointer 和 MergeReceipt 前，会在自己已经打开的同一个 `BEGIN IMMEDIATE` 事务里只读这两把锁；
- Stop 先成功时，旧 B-06 写入三件套的数量必须为 0；
- B-06 先成功时，Stop 只能排在它后面，回包丢失也能从本地三件套识别成已提交。

B-06 仍然不写 RunState 或 StopReceipt，B-07 也不写 CandidateVersion、pointer 或 MergeReceipt。双方只共用同一个 SQLite 事务域和一次只读围栏。

## 恢复和重开不是一回事

- 非终态 run 因进程崩溃，可以 `resume`：同一行的 epoch 加一，旧进程失效；
- `STOPPED` 是终态，不能改回 `ACTIVE`；想继续必须 `reopen` 一个新 run，并重新读取当前章节版本、pointer、预算、权限和路线。

provider session 或 cache 即使全部丢失，也不能改变恢复判断。

## 与 CCZ-142 怎么接

B-07 只读取 CCZ-142 已经保存的本地结果，用 locator、record ref 和 SHA-256 做机械核对，不复制模型原始回包，不调用模型，也不读取新正文。

当前适配器已经证明“本地结果可按哈希交接”，但 CCZ-142 的 exact 字段映射仍等真实保存结果反馈，所以 `ccz142_exact_adapter_complete=false`。这不阻塞 RunState／StopReceipt 核心施工，也不能被写成产品已接线。

## 作者看见什么

B-07 只给 B-10 一个现算的五字段白名单状态，例如正在运行、等待、停止、是否需要重新启动。内部错误码、Token、费用、Prompt、模型 ID、record ID 和 debug 字段全部禁止进入作者 payload。

## 当前证明到哪

当前只使用合成引用和临时 SQLite：

- 0 小说正文读取；
- 0 模型/API/网络调用；
- 0 正式事实和十本账写入；
- 证明原子 Stop、幂等、CAS、resume、reopen、B-06 ack-lost 对账、Stop 与 B-06 的两种合法总顺序，以及 debug 失败不影响 Stop。

它没有证明抽取更准、更快或更省 Token，这三项继续是 `null`。

## 运行

在仓库根目录执行：

```bash
uv run --locked pytest -q work/ccz57_m3_b07_local_recovery_stop_r01/test_b07_local_recovery.py
uv run --locked pytest -q work/ccz57_m3_b06_commit_core_r01/test_b06_commit_core.py
uv run --locked python work/ccz57_m3_b07_local_recovery_stop_r01/self_check.py
uv run --locked ruff check work/ccz57_m3_b07_local_recovery_stop_r01
```

来源：Codex
