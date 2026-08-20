# Chat 生命周期与模型切换

## 1. 一个阶段一个 Chat

推荐：

```text
Chat 1：M1～M3 本轮总审
Chat 2：M4～M7 本轮总审
Chat 3：M8～M11 本轮总审
Chat 4：作者工作区＋跨模块
Chat 5：完全独立终审
```

不推荐：每个小步骤开一个 Chat；也不推荐整个项目一年只用一个 Chat。

## 2. 同 Chat 的效率优势

同一 Chat 已实测可以跨独立代码调用保留文件；模型切换也保留 workspace。可复用：

- 完整解压目录；
- SQLite 索引；
- Git repo；
- 测试缓存；
- 当前轮日志；
- 已安装的离线依赖；
- 生成中的结果目录。

因此：首次给 `BOOTSTRAP.zip`，同 Chat 后续优先给 `DELTA.zip`。

## 3. Checkpoint 纪律

以下时点 MUST checkpoint：

- 模型切换前；
- 大批测试前；
- 预计中断/离开前；
- 应用 Delta 前；
- 打结果 ZIP 前；
- current 版本发生变化时。

Checkpoint 至少包含：

```text
CHAT_CHECKPOINT.md
WORKSPACE_MANIFEST.json
CURRENT_BASELINE.json
PENDING_WORK.md
SHA256SUMS.txt
```

## 4. 什么时候继续旧 Chat

- 仍是同一个阶段；
- baseline 没变；
- 需要复用当前 workspace；
- 只是追加 Codex 回执、Patch 或 fixture；
- 当前对话没有严重旧结论污染。

## 5. 什么时候开新 Chat

- 做 independent review；
- 进入新阶段或新模块；
- baseline 大版本切换；
- current/旧状态混乱；
- 沙箱丢失或无法验证；
- Chat 已积累太多互相冲突的历史；
- 需要测试 Project Sources 在新 Chat 的可恢复性。

## 6. 模型切换

本次同 Chat `Pro → Extra High`：

- marker SHA PASS；
- 16 MiB blob SHA PASS；
- SQLite token / previous phase PASS；
- Git HEAD PASS；
- MD/ZIP Project Source SHA PASS；
- hostname 前后一致；
- CPU/RAM/运行时一致。

因此可以在一个 Chat 中按任务切模型，不必重传工程。规范仍要求切换前 checkpoint，因为：

- 平台没有给沙箱持续性 SLA；
- 模型和工具实现会变化；
- 某次异常可能触发 reset。

## 7. 长 Chat 的防污染

聊天变长后，MUST 用文件压住 current：

- `CURRENT.md/json`：当前版本和正式状态；
- `DECISIONS.md`：本阶段已经接受的决定；
- `SUPERSEDED.md`：明确作废项；
- `PENDING.md`：未决；
- `WORKSPACE_MANIFEST.json`：文件状态。

Prompt 写明：文件 current 高于早期聊天文字。
