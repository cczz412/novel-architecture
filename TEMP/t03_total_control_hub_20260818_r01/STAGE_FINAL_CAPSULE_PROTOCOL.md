# 五窗阶段回执与不停机续跑协议

窗口完成阶段时采用“两层回传”，不要只发一句 PASS，也不要把全量报告塞进聊天。**阶段完成不等于必须停车。**

## 第一层：立即发给总控的短回执

控制在约 1500 个中文字以内，固定包含：

```text
STAGE_FINAL_CAPSULE
WINDOW=
TASK_ID=
STATUS=COMPLETE|HARD_STOP|BLOCKED
STOP_CLASS=CONTINUE_SAFE|INTENTIONAL_IDLE|DECISION_STOP|HARD_STOP
VERDICT=
DELIVERABLE_ROOT=
PRIMARY_RESULT=
MACHINE_RECEIPT=
API_MODEL_RETRY=
FORMAL_WRITES=
NEW_FAILURE=
DEPENDENCY_OR_WRITE_CONFLICT=
CZ_DECISION_REQUIRED=
NEXT_SAFE_TASK=
CONTINUATION_STARTED=NONE|TASK_ID
ONE_PARAGRAPH_SUMMARY=
END_STAGE_FINAL_CAPSULE
```

完成后除在本窗口正常给最终回答外，还要把这张短回执只发送一次到总控线程：

`01a00bb7-88f8-7092-9b55-34ca4127a4a1`

不要把全量报告重复粘贴给总控，不要操作共享 ChatGPT 页面。

## 第二层：本地完整证据

完整报告、逐项结果、机器账、SHA 和 no-touch 回执继续留在本任务唯一写集。短回执必须给出精确目录和主回执。

总控收到短回执后默认只做：

- 核验目录、主结果和机器回执存在；
- 解析 JSON／JSONL；
- 核对关键 SHA、API／retry、正式写集和权限；
- 原样排入共享 ChatGPT 队列；
- `STOP_CLASS=CONTINUE_SAFE` 且下一单前置齐、写集互斥、没有红线时，**先派下一张长阶段票，再异步等共享审查**；
- 收到 ChatGPT 的判断后，只检查红线、写集冲突和明显事实错误，再回传原窗口。普通共享审查不再成为续跑前置。

## 三种停法

- `CONTINUE_SAFE`：阶段完成，但已有明确、安全、能产生新信息的后续；`CONTINUATION_STARTED` 必须给精确任务号，不能写 YES。
- `INTENTIONAL_IDLE`：阶段完成，没有安全且能产生新信息的后续，也没有待 CZ 选择的政策问题；保持有意空闲，不制造假任务。
- `DECISION_STOP`：出现会改变合同语义、owner、正式方向或不可逆路线的真实选择；只停这一窗，其他窗继续。
- `HARD_STOP`：新失败、权限冲突、写集冲突、API/global_stop、身份不清或回执矛盾；只停受影响分支。

不得把“发了阶段回执”“共享页面还没批”“总控还没读完整正文”写成 `DECISION_STOP`。`NEXT_SAFE_TASK=IDLE` 时也不得写 `CONTINUE_SAFE` 或 `CONTINUATION_STARTED=YES`；应写 `INTENTIONAL_IDLE` 与 `NONE`。

只有遇到下面情况才读全量正文或最近线程：

- 新失败面或硬停；
- 正式合同／产品／Gold／R13 等红线变化；
- 写集冲突或 owner 不清；
- 机器回执与人读结论矛盾；
- ChatGPT／Notion 建议与本地证据矛盾。

## 共享 ChatGPT 固定介入但不阻塞

所有阶段完成回执和新阻断仍进入共享 ChatGPT。工作窗不判断“值不值得发”，总控也不先替 ChatGPT 写完整判断。纯粹的心跳、无变化等待和“收到规则”不发送。

普通完成回执可以在队列里等；新失败、真实阻断和 CZ 决策项插到普通回执前。共享页面一次只处理一窗，但这个串行队列不得把本来解耦的 Codex 工作也变成串行。

共享 ChatGPT 输出视为“思考草稿”。总控只有在下面情况才改写或暂停自动回传：红线越权、写集冲突、身份/轮次错误、本地机器票矛盾、明显引用旧结果。其余情况直接转回对应窗口。

窗口等待共享批复期间，可以继续总控已明确派发的 TEMP-only 长阶段；不能提前实施方向性正式修改。阶段票尽量覆盖一个完整、能产生新信息的对象，避免三五分钟一个微票。

来源：Codex
