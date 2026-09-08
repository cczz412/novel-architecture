# C3 · 事实候选（FACT_CANDIDATE）

**版本：v1**（增加来源章节 revision 身份；quote 仍只是未核定位线索）

一句话用途：抽取器（或外部 JSON 文件）产出的候选事实句，投给事实账之前的传输形态；入账后由 M4 补齐记录字段变成 C4。

| 方向 | 模块 |
|---|---|
| 发 | M3 抽取器（[extract.py](../mvp/extract.py) 的 `extract_segment`；备用入口 `load_candidates_file`） |
| 收 | M4 事实账（[store.py](../mvp/store.py) 的 `add_fact_candidates`） |

## 字段表（传输条目，`items` 数组里的一条）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C3_FACT_CANDIDATE` | 是 |
| version | str | 固定 `v1` | 是 |
| chapter_revision_ref | obj | 必须等于产生本候选的 C2/C1 revision ref | 是 |
| text | str | 事实句，独立完整、主语明确 | 是（空白条目入账时被丢弃） |
| quote | str | 责任段内的原文依据片段（模型转抄，未做一致性校验） | 否（可空串） |
| seg | int | 来源责任段序号（对应 C2 的 `seg`） | 否（extract 路径必带；外部候选文件通常没有） |

批次级参数（不在条目里，随调用传）：

| 参数 | 类型 | 含义 |
|---|---|---|
| chapter_id | str | 兼容调用参数；必须等于每条 `chapter_revision_ref.chapter_id` |
| source | str | 候选来源：模型 ID（extract 路径）或候选文件名（candidates 路径），入库时打在每条上 |

## 真实示例

《万鬼伏藏》c01 第 1 段抽出的一条（入账后成为 f001）：

```json
{
  "contract": "C3_FACT_CANDIDATE",
  "version": "v1",
  "chapter_revision_ref": {
    "chapter_id": "c01",
    "revision_no": 2,
    "revision_text_sha256": "0aeb78621f82e724f19a56e01f2dc9bfcdec630b1748e2fb2c78edb0b0e47cfc"
  },
  "text": "市医院精神科的陈医生询问李星燃有什么症状。",
  "quote": "“你叫李星燃对吧，说说看吧，你都有什么症状。”",
  "seg": 1
}
```

外部候选文件进入 v1 时也必须携带 revision ref 与 seg；旧 v0 无 revision 的候选只能走显式 legacy migration，不能直接进入 C4 v1。

## 可选扩展：保留候选原文与映射证据

来源 C2 含 `text_map` 时，每条 C3 必须带 `text_map_evidence`，形状严格遵守 [C2_C1_TEXT_MAP v1](C2_C1_TEXT_MAP.md)。`quote` 保持模型原样并等于证据的 `quote_original`；映射由 M3 从可信 C2 构造，模型不能提交或改写映射。证据失败使该批候选写入失败，不能丢掉扩展再按旧规则接纳。

原始 C3 v1 入口保持原规则。扩展没有增加置信分；证据校验通过不说明事实语义正确，更不表示作者确认。

## 显式恢复证据 v2

调用方显式启用 [C2/C1恢复v2](C2_C1_TEXT_MAP_V2.md) 时，text_map_evidence.version为v2；C3 quote仍是模型原引文，恢复后的原章片段和点名字段适配原件另存于证据内。只有源LF缺失或被单普通空格替代可以受控恢复；旧默认及v1校验不放宽。M3工作区新增独立入口 `persist_current_recovered_fact_candidates`，仍按原始响应身份、完整来源批次与事务保存。
