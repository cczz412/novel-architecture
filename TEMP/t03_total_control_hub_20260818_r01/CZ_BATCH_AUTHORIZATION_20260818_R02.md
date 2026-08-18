# CZ 批量明字授权｜2026-08-18 R02

## CZ 原话

> 同意 C10 只正式刷新 C1/C2 两条 SHA；同意 T03 执行 2 次合成握手（豆包 1 次、Flash 1 次，Agent Plan、0 重试、0 元、新书 0、Gold 0、能力评分 0）；同意两项完成后更新 route 并在本地生成下一次 Pro Prompt/ZIP，不自动上传。

## 执行解释

1. A 可在 `validate_c10_intake_material_identity.py` 中只正式替换 C1/C2 两条 expected SHA，并按已冻结说明验收；不得修改第三处正式字节。
2. T03 可按已冻结候选票执行豆包与 DeepSeek Flash 各一次 Agent Plan 合成握手；总调用 2、0 重试、增量按量费 0 元、小说与 Gold 读取 0、能力评分 0。
3. A 与 T03 完成后，B 可更新最终 route，并在本地生成 ChatGPT Pro Prompt、ZIP 与包回执；不得自动上传或发送。
4. CZ 要求总控做到本地包完成后再通知其手工上传，不在中间正常阶段反复要求确认。

来源：CZ 明字；本地登记：Codex
