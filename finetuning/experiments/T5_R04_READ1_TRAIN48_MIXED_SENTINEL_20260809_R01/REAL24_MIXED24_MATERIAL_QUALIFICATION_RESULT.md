# mixed24 教材版本资格补测

结论：`FAIL_TRAIN48_MATERIAL_CANDIDATE`。

这次只复用现成 mixed iter24 adapter。已有 REAL8 原样保留，只补了缺少的16题；没有训练，也没有重跑已有8题。

## REAL24 结果

- 可恢复事实语义：P=0.393013，R=0.321429，F1=0.353635。
- TP/FP/FN：90/139/190。
- 严格 JSON：23/24题。
- 完整 Schema：0/24题。
- 在90条语义命中事实中：status正确0条，speaker正确47条，evidence正确44条。
- 复读题0，触顶题0，重复事实0，空答题0，越界事实0。
- 24/24均正常停止。

## 对照

- 相对 BASE_READ1 F1=0.409639：下降0.056004。
- 相对 TRAIN36 dense-only iter24 F1=0.428000：下降0.074365。
- TRAIN36 iter24 的完整 Schema 为0/24；本次仍为0/24，没有格式改善。

## 判定

预注册要求同时满足“完整 Schema 明显改善”和“事实 F1 不低于 BASE”。本次两项都没有满足，因此36+12教材版本候选不合格。

L6结果只保留诊断，不参与本次硬门。没有继续 mixed48、S-M、READ2/READ4 或 OUT。

边界：新增本地推理16次；训练0、API调用0、自动重试0。未改 adapter、TRAIN48、REAL24 Gold、scorer、Notion、Git、默认或生产指针。

来源：Codex
