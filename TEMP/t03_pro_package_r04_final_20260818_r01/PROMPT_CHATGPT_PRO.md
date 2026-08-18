# ChatGPT Pro 任务｜R13 六身份当前正式字节大审 R04

请读取随附的唯一 review ZIP。你是外部高级审查员，不是项目执行者；你的结论全部是 `ADVISORY_ONLY`，不会自动修改正式合同、R13、产品、Gold、模型配置或作者真值。

## 阅读顺序

按包内四层阅读：

1. `01_current_truth/`：本轮权限、当前事实和 R13 产品语义；
2. `02_current_route/`：当前直接相关正式合同、Schema、fixtures 与合同 validator；
3. `03_upstream_evidence/`：T03、A、B、C、D 的新停点和机器回执；
4. `04_external_reviews/`：上一轮 ChatGPT Pro 的 8 个主报告、接收票和本地分诊材料。

每个重要判断都请引用包内相对路径。不要把旧顾问建议、TEMP 机械 PASS 或候选补丁冒充当前正式能力。

## 当前事实，不能读反

- A 的 C11 四件已正式落地；D 对它完成 `5/5 PASS` 窄重放。
- C10 的 C1／C2 双 SHA 已正式刷新，现役 validator 不再是旧候选状态。
- C owner closure 保留，但 C9 runtime consumer／producer 和 evidence recall 仍 OPEN。
- T03 旧 8 次能力批次仍是 `NO_VERDICT`。
- T03 新两次合成握手：Flash `HANDSHAKE_PASS`；豆包因同样返回单层小写 `json` 围栏，在当前“只允许 Flash 围栏适配”的运输门下 `HANDSHAKE_FAIL`。这不是语义能力失败，不产生 Recall、Precision、模型排名或 C3／C4 资格。
- 不授权第三次调用或新能力批次。

## 请完成五项审查

### 1. 身份分层

逐项找出并纠正这些混淆：

- 已落正式件 vs 未应用候选；
- 机械测试通过 vs 产品能力完成；
- 模型运输格式失败 vs 语义能力失败；
- 外部顾问建议 vs CZ 执行授权；
- 计划、书稿、facts、actual 各自的写权。

### 2. 跨缝兼容

重点审查：

- C10 eligibility 与 C11 INITIAL／REPLACE／RESTORE 是否还有绕门路径；
- C11 revision 向 C1／C2、C3／C4／C6、planstore 和事实准入传播时，stale、幂等、回退和双重真源是否清楚；
- C9／M11 的 owner、runtime producer／consumer、evidence recall OPEN 是否会让 M8 或规划链误以为已有正式上下文包；
- 当前正式合同之间有没有字段同名但含义不同、未声明消费者、旧 SHA 锁或隐含默认。

### 3. R13 新旧差分

列出 R13 中：

- 仍然有效的产品钢线；
- 已被现行正式合同或新停点取代的说法；
- 仍需 CZ 拍板的产品语义；
- 只应更新人读说明、不应改合同的内容。

不要直接重写 R13，请只给证据和建议。

### 4. 下一批五窗任务

分别给 T03、A、B、C、D 一个明确姿态：

- `RUN_ONE_NARROW_TASK`：只给一个最小任务、输入、写集、验收门和停点；或
- `INTENTIONAL_IDLE`：说明为什么现在不该施工。

不要重复已经完成的 C11 formalization、D 窄重放、C10 双 SHA 刷新，也不要自动开启 T03 第三次调用。

### 5. 反方审查

主动寻找至少五个“表面全绿、实际仍危险”的反例，优先关注权限升级、stale 传播、并发写、旧候选复活、顾问建议越权和格式修理掩盖能力问题。

## 回传要求

请在聊天里给一段不超过 500 字的摘要，并提供一个可下载 ZIP。ZIP 根目录直接放：

- `00_EXECUTIVE_JUDGMENT.md`
- `01_IDENTITY_LAYER_AUDIT.md`
- `02_CROSS_SEAM_COMPATIBILITY.md`
- `03_R13_STALENESS_MAP.md`
- `04_T03_HANDSHAKE_AND_C_RUNTIME_OPEN.md`
- `05_NEXT_TASK_PORTFOLIO.md`
- `06_RISKS_AND_COUNTERARGUMENTS.md`
- `MACHINE_RECOMMENDATION.json`

Markdown 要能独立阅读；机器文件至少给出总判决、主要 blocker、每窗建议姿态和对应证据路径。不要返回代码补丁、修改后的正式文件、原始推理过程或第二个 ZIP。

来源：Codex
