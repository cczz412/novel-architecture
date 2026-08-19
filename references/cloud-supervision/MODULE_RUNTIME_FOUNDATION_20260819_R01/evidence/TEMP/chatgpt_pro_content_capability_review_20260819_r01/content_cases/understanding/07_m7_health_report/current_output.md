# 小说体检报告

报告身份：C6_HEALTH_REPORT v1
项目：纸灯巷·合成体检
生成时间：2026-08-19 19:20:00
Provider：FROZEN_SYNTHETIC_ZERO_MODEL_HEALTH_MAP（原报告记录 API 调用 0 次；本次渲染未调用 provider）
来源状态：CURRENT

## 覆盖范围与来源水位

事实水位：纳入 2 条；已确认 2 条；候选 0 条。
检查分组：1 组。
来源 revisions：
- c03 / revision 1 / SHA 60c7ade1164019200769ddbec99be059acbf02a7511da2e4fbbe7355f53f60c0

## Findings

### h001 · 矛盾

- 严重度：red
- 类别：setting
- 事实层：confirmed
- 说明：同一把铜钥匙先被声称已经烧毁，随后又以完整实物出现。
- 事实号：f201, f202
- 证据：
  - 事实 f201（confirmed）
    引文：苏晚说铜钥匙已经烧毁
    锚点：c03 / revision 1 / [0, 10)
    revision SHA：60c7ade1164019200769ddbec99be059acbf02a7511da2e4fbbe7355f53f60c0
    quote SHA：fe38399599222057031e8ab2b3a22fa3cc53580cb3ae80f56259e3be25681cd3
  - 事实 f202（confirmed）
    引文：林乔在桌上看见了同一把铜钥匙
    锚点：c03 / revision 1 / [15, 29)
    revision SHA：60c7ade1164019200769ddbec99be059acbf02a7511da2e4fbbe7355f53f60c0
    quote SHA：9da93a43794766ed27cc4c36bca7a23bea9b34454a1957a825551026e142d71e
- 判读边界：以上类别按原报告展示，没有给出整体结论。

## 排除、弃权与未知项

- invalid_c4_v1：0
- rejected：0
- needs_recheck：0
- current_revision_missing：0
- stale_revision：0
- unverified_evidence：0
- invalid_evidence：0
- duplicate_dropped：0
- 材料不足 findings：0
- 别名提示：0
- 账本重复事实号：0

这些项目只按原报告列出；未进入 finding 的内容不等于已经完成检查。
