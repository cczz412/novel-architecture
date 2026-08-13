# 2026-08-12｜DISCRIM17 部分盲审试选方法审查一问一回包

这批共有 1 个逐字 Prompt 和 1 份完整 ChatGPT 回包。Prompt 来自本地外审路线，回包由 CZ 从 Downloads 交回；两份归档副本都与源文件逐字节一致，原件没有移动或覆盖。

## 身份边界

- 这份报告是 `METHOD_ADVISORY_EVIDENCE`：只帮助修订 DISCRIM17 的部分盲审上下界、停审判据、角色前沿、资源比较和匿名补审方法。
- 报告结论是 `CONDITIONAL PASS`：继续停止 Wave06～21 的默认机械续审，但不能据此发布 3～5 个候选、排名或赢家。
- 报告看见的是打包时的进度快照。它写“累计 R05 尚不存在”，但本地随后已经生成 225 行累计 R05；当前事实只认本地累计账和接收票，不能让旧快照覆盖新证据。
- 外部公式和阈值建议要进入新的合同、代码与执行票后才可运行。本报告不授权真实解盲派生、评分、模型调用、A／B／C、训练、Git、Notion、确认卷开封或生产晋级。

## Prompt 与回包

| 问题 | 逐字 Prompt | 完整回包 | 大小 | SHA-256 |
|---|---|---|---:|---|
| 225／916 条已审时，怎样用确定性可达边界判断能否停审；若不能，怎样只审有决策价值的匿名行 | [Prompt](prompts/01_discrim17_partial_blind_review_method_audit.md) | [回包](returns/01_discrim17_partial_blind_review_method_audit.md) | 36,511 | `def26adb2b64e9c73a6c254b015083ed232923d1cc0d1d7cb7bba38d3058a000` |

## 外发证据包追源

- 路线：`t5-r04-discrim17-partial-shortlist-decision`
- ZIP：74,098 bytes，26 个成员，其中 24 个为路线清单载荷。
- ZIP SHA-256：`10bc73f7ac8af98c4a8d96d672c08b97156f03ad7b91a3664cb2b88d591cd788`
- 包内 `MANIFEST.json` SHA-256：`d0de99d2145cd0c1e5ed42d81d392627499e495508deb550a6aeb03ca437bcca`
- 包内 `SHA256SUMS` SHA-256：`7ee751cfdec1610b333922ace35468d001bc058dae6e3b668850994e808549f6`
- 本地打包回执 SHA-256：`941af2f095c4d77642a97d65b567e304c6db2a13b7a88a5035bfb2c44afddd79`
- 打包回执只证明本地包已生成并通过检查，没有独立平台发送回执；不补写 `sent=true`。

## 当前吸收的办法

- 未审预测必须同时记录出现次数和不同预测容量，避免重复预测虚抬最好成绩。
- 三个主单元要按同一个可达世界联合汇总，不能把不同世界里的 Precision、Recall、F1 最好端点拼起来。
- 费用、时延或角色阈值缺失时，应标成非语义阻塞；继续审语义行不能修好这类问题。
- 若要定向补审，只能选择反事实上可能改变候选关系的匿名行，并用新的不透明编号交给没看过聚合结果的审者。

来源：Codex
