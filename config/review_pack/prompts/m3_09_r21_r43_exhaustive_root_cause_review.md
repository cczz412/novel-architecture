# ChatGPT Pro 外审 Prompt｜M3-09 R21～R43 全历史共同根因与一次收口

你是独立工程审查人。请先完整解压并阅读 ZIP。这个包不是只让你修 R43 的三个
字段，而是要求你审清 R21～R43 为什么持续出现“修一处、下一阶段再爆一处”。

ZIP 包含：

- R21～R43 每一轮完整公开胶囊；
- R21～R43 全部现存公开事故票、回归回执、fresh gate 和施工证据；
- R35 与 R7～R41 两次 ChatGPT Pro 原始审查及补丁账单；
- R42 施工后的完整公开胶囊；
- R43 当前胶囊、seal builder、AS 成功证据和 C0 挡停机械归因；
- 六个 SHA 绑定的 A5／QEC 程序和 Python 3.12.12 环境锁。

终验题、金标、正文、密钥和正式控制目录没有入包，也不需要它们才能完成本次
公开工程审查。

## 你必须完成的工作

### 1. 复盘两次旧外审

分别核对：

- R35 外审建议解决了什么，后续是否正确落地；
- R7～R41 外审列出的六个挡跑家族，R42 是否逐项正确施工；
- 哪些建议本身正确，但施工时仍因新的 producer／consumer 错位失效；
- 哪些内容旧外审明确没覆盖，却被后续误当成“全链已经验证”。

不要把旧报告复述一遍。请用 R42／R43 实物逐条判：
`已正确落地 / 部分落地 / 未落地 / 新证据推翻`。

### 2. 对 R21～R43 做版本间差分审查

沿 revision 顺序比较每轮公开胶囊。把所有挡停归到尽可能少的共同根因家族，
每个家族至少写清：

- 最早出现在哪一轮；
- 后续在哪些轮次以不同症状复发；
- 哪个字段、路径、schema 或状态有多个作者；
- 哪个 producer 生成，哪些 consumer 使用；
- 为什么当轮检查没有发现；
- 属于安全 fail-closed 正常挡停，还是可避免的工程错位。

请特别审查这些重复真源：

```text
ticket / revision / root paths
seal state fields and counters
runner output fields
contract required fields
sandbox actual reads and allowlists
canonical JSON and SHA rules
review route / review round / retired seal chain
stage outputs and downstream artifact sets
P2/P3 scoring and closeout inputs
```

### 3. 解释 R43，不要停在 R43

R43 当前直接问题已经机械确定：seal producer 漏了 C0 要求的
`formal_cycle_created=false`、`formal_run_created=false`、
`formal_authorization_issued=false`，而只写了复数计数。

请回答：

- 为什么 R42 的端到端公开彩排、R43 的读集对平和 Sol 审查都没发现；
- 这是不是“seal producer schema 与 C0 consumer schema 没有共同生成源”的直接证据；
- C0 之后的 FR／Terra／PF／P2／P3 是否还有同类 producer／consumer 漏项；
- 能否从包内公开材料在下一张票之前一次列全。

### 4. 给一张且只有一张 R44 收口账单

不要输出 R44、R45、R46 多轮建议。请给一个 R44：

- 直接挡正式跑的问题一次补齐；
- 明确唯一作者输入是什么；
- 哪些 JSON、合同、runner 字段、seal 和 allowlist 必须从它自动派生；
- 哪些旧手写副本应删除或退化为生成物；
- 哪一个真实 consumer 集成入口必须在封签前执行；
- 哪些文件明确不动；
- 新 seal、新公开证据链、新 AS、新 C0 的恢复规则；
- 完成定义和 fail-closed 退出条件。

R44 可以做必要的局部结构调整，但不要把整个 T3 大重构塞进来。请把不挡正式跑的
架构债单列，延后处理。

### 5. 设计“最终消费者覆盖表”

请给一张机器可实现的表：

```text
producer fact
→ generated artifact
→ consuming function
→ executable pre-seal test
→ expected evidence
```

至少覆盖：

- seal producer → C0 `current_seal()`；
- AS profile producer → AS/C0/FR 实际读取；
- formal output producer → Terra/PF；
- PF producer → P2；
- P2 score producer → P3；
- unique commands → 每个实际 launcher。

目标不是再增加几十个字符串检查，而是让最终 consumer 使用公开假件真实执行。

### 6. 回答 CZ 最关心的问题

请用明确数字或条件回答：

- R21～R43 一共有多少个共同根因家族；
- 哪些已经关闭，哪些仍未关闭；
- 做完 R44 和一个真实消费者端到端公开彩排后，公开工程面还有多少类已知挡点；
- 下一次正式 live run 能否合理收敛为 0～1 次；
- 哪些风险只能由真实供应商、密钥、文件系统故障或私有评分材料暴露；
- 如果不能保证一次成功，诚实给出剩余风险上界，不要只写“视情况而定”。

## 钢线

- Agent Plan＋MiniMax M3；
- 30 题 × A5／QEC 两路线，最多 60 次；
- 温度 0、thinking 关闭、自动重试 0；
- 最多 12 个证据编号；
- 一票一个 run，首个网络尝试前原子消耗授权；
- 不改终验题、金标、正文、评分判据和路线；
- 不提高上限，不截断超量结果冒充合规；
- 不要求 ZIP 外文件；
- 不要求密钥、正式控制目录或私有材料；
- ChatGPT 只给建议，不替 CZ 拍板。

## 输出要求

对话正文先给不超过 20 行的结论，同时生成一个可以直接点击下载的 ZIP。
ZIP 内至少包含：

- `M3_09_R21_R43_ROOT_CAUSE_REVIEW.md`
- `R21_R43_FAILURE_FAMILY_REGISTER.md`
- `R44_SINGLE_CLOSEOUT_PATCH_BILL.md`
- `FINAL_CONSUMER_COVERAGE_MATRIX.md`
- `REMAINING_LIVE_ONLY_RISKS.md`
- `REVIEW_RECEIPT.json`

所有结论都要引用 ZIP 内准确相对路径、文件和函数。请把 ZIP 下载链接直接发在
对话里，不要只贴正文，也不要只生成需要预览后另存的单个 MD。

来源：Codex
