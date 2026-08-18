# D-C11 r1→r2 单场景探针总判决

⚠️ 停点：`RUNTIME_OR_CONTRACT_GAP_FOUND`。

这不是说合同方向错了。相反，正式合同和 C11 validator 对这个场景的规则基本一致：c01 从 r1 变成 r2 后，唯一支持 f001 的原文引用消失，f001 应进入“需要重查／证据消失”，M6、M8、M11 不再消费；相关 RE 应过期，旧 actual 支持应失效，旧 admission 也应因仍引用 r1 而在写前拒绝。

真正卡住的是现役产品还没有把这条链做出来。十道门中，合同或正式 validator 层面的检查 10/10 成立，但产品运行时可执行证明是 0/10，所以不能写 `PASS_ONE_SCENARIO`。

## 十道门怎么记

| 门 | 可核到什么 | 运行时结论 |
|---|---|---|
| 1 | r2 ledger 与合成 C1 v1 夹具的 id、revision ref、正文 SHA 全等 | C1 v1 current-view writer 不可测 |
| 2 | 正式 validator 得到 `needs_recheck/evidence_gone`，M6/M8/M11 全部禁用 | C4 revision-aware 产品迁移未实现 |
| 3 | 合同要求 basis pin 重查、RE stale；validator 只有局部 RE 夹具 | planstore r07 writer 未实现 |
| 4 | 合同和局部夹具都指向无 actual 支持 | r07 actual 派生运行时未实现 |
| 5 | revision ref 比较能识别旧报告 | C6 v1 current reader 不可测，不能证明它会覆盖输入自报 |
| 6 | r1 action 与 r2 current 明确不一致，合同要求写前拒绝 | 现役 `reconcile.py` 仍是 v1，v2 admission 未实现 |
| 7 | 合同要求共用 `.planstore.lock` 并让后提交者重读 current | 跨 owner revision commit 协调器未实现 |
| 8 | C11 validator 的同 operation 同载荷回放、异载荷冲突成立 | 跨 owner 组合运行时不可测 |
| 9 | 形式化 SHA 恢复分类能区分 all-before／all-after／人工恢复 | 没有可故障注入的整链事务运行时 |
| 10 | 上述缺口被明确识别，没有包装成 PASS | 通过缺口识别门 |

## 这张票真正证明了什么

- 合同方向没有出现新的互相打架：证据消失、消费禁用、RE 过期、actual 失效、旧 action 写前拒绝、共锁与原子恢复的口径能对上。
- C11 正式 validator 能机械跑 r1→r2、证据消失、消费禁用、局部 RE/actual、幂等冲突和恢复分类。
- 它不能代替产品 writer、reader 或跨 owner 事务协调器。这里没有用自造实现冒充现役能力。
- 没发现新的语义错误成功；发现的是已由正式合同明说的产品实现缺口。

## 权限与停点

正式输入前后 SHA 全部一致。API、模型、小说、Gold、Notion、Git、R13、产品和正式写入均为 0；自动重试 0，缓存污染 0。

若 CZ 以后要继续，所需的是新的正式产品施工票，至少要包含 C1 v1 current-view writer、C4 revision-aware writer、planstore r07 stale/actual、C6 v1 current reader、reconciliation admission v2 和共用事务协调器。本 D 窗不能自行补这些能力。

机器总账：`results/gate_ledger.json`  
运行能力盘点：`results/runtime_capability_inventory.json`  
输入 SHA：`results/input_manifest.json`  
未触碰回执：`results/no_touch_receipt.json`

来源：Codex
