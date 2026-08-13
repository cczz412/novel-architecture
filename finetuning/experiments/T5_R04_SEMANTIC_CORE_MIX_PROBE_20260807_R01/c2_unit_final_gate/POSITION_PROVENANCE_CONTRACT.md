# canonical A evidence 位置来源合同 R01

## 结论

canonical A gold 以后不能只保存 evidence 文字，还必须保存它在本窗连续原文中的明确位置。C2 renderer 只认该位置，不能再用 evidence 文字搜索后默认取第一次。

## 推荐字段

每条 canonical fact 应有稳定 `fact_id`，并带：

```json
{
  "evidence": "逐字证据",
  "evidence_span": {
    "coordinate_space": "c2_source_text_bridge_plus_target",
    "indexing": "unicode_codepoint_0_based_half_open",
    "start": 123,
    "end": 145,
    "source_text_sha256": "..."
  }
}
```

字段含义：

- `start` 包含，`end` 不包含；
- 坐标按 Python Unicode 字符计数；
- `source_text` 是 C2 机械解析后的 `bridge_text + target_text`；
- 必须满足 `source_text[start:end] == evidence`；
- `source_text_sha256` 防止正文变化后旧坐标悄悄漂移。

如果 canonical schema 已有等价的稳定范围字段，可以沿用，不必重复造字段，但必须具备同样的字符范围、坐标口径与源文本指纹。

## 当前 legacy 迁移

当前原型 A 没有稳定 `fact_id` 和位置字段。本轮只建立迁移 sidecar：

- 唯一逐字匹配的 396 条，登记为 `LEGACY_UNIQUE_TEXT_MATCH_BACKFILL`；
- 多次匹配且没有独立位置来源的 1 条，登记为 `LEGACY_POSITION_AMBIGUOUS`；
- sidecar 用 `canonical_sample_id + fact_index + fact_fingerprint` 防止行内顺序或事实内容变化后误绑；
- sidecar 只是旧材料迁移票，不替代未来 canonical gold 内建位置。

## 隔离纪律

`LEGACY_POSITION_AMBIGUOUS`：

- 不猜第一次；
- 不进入需要唯一映射的 C2 训练／评分事实分母；
- 保留全部候选范围和独立审计记录；
- 将来拿到真实位置后，新建修订票再恢复；
- 若所在整行用于 SFT，必须整行隔离或先恢复位置，不能从答案中静默删一条后继续训练，避免教模型漏抽。

来源：Codex
