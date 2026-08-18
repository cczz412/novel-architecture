# T-03 统一精确 JSON 围栏离线重放｜阶段结果

✅ 阶段判决：`OFFLINE_UNIFIED_TRANSPORT_REPLAY_PASS`

在这个全新的离线身份下，豆包和 DeepSeek Flash 两份既有合成握手 raw 都通过了同一条运输规则和同一个 Validator。

统一候选规则是：两路都允许完整裸 JSON；两路也都允许整个 `content` 恰好是一层小写 `json` Markdown 围栏、围栏外 0 字符。围栏适配只删除开头和结尾包装，内部 payload 字节、字段、值、数组顺序、身份和证据内容均未修改。

- 豆包：raw、content、剥离后 payload SHA 已分账，重包后与原 content 完全一致，同一 Validator 通过。
- Flash：同样通过，处理路径没有模型分叉。
- 合成夹具：13/13。合法围栏和裸 JSON 通过；围栏外文字、大写或无语言标签、双层围栏、坏 JSON、身份错误、字段增删全部拒绝。

这不会改写上一轮 `HANDSHAKE_FAIL`：旧结论仍准确描述当时冻结的“只允许 Flash 围栏适配”合同。本轮只证明新的统一候选运输规则能离线覆盖两份既有合成 raw。

本轮 API、模型调用、重试均为 0，不产生能力评分、模型排名、C3/C4 资格或生产结论，也不会自动申请第三次调用或新能力批次。旧 8 次能力批次继续保持 `NO_VERDICT`。

来源：Codex
