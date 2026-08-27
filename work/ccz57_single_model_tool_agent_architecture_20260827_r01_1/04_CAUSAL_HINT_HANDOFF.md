# 因果提示与现役事实账的交接

## 当前事实

GitHub `main@fa287f5...` 已有正式写入器：

- 候选入口：`factstore.add_fact_causal_edge_candidates`
- 正式对象：`FACT_CAUSAL_EDGE fact-causal-edge-v1`
- 正式编号：`CE-...`
- 机器建议只能写成 `candidate`
- 作者才能确认或退役
- 端点必须是 M4 已分配的 `f...`

因此不再讨论新建 writer，也不再创建持久 `RelationCandidate`。

## M3 可以留下什么

M3 只能留下 `causal_review_hint`，身份写死为：

> 有期限、可审计、不是正式事实账的内部侧车 artifact。

```json
{
  "contract": "M3_CAUSAL_REVIEW_HINT",
  "version": "r01.1",
  "hint_id": "hint_...",
  "chapter_revision_ref": {},
  "from_candidate_lineage_id": "cand_...",
  "to_candidate_lineage_id": "cand_...",
  "evidence_artifact_refs": [],
  "suggested_span": "直接|长程|UNDECIDED",
  "status": "PENDING_M4_MAPPING|MAPPED_TO_CANDIDATE|STALE|REJECTED|EXPIRED",
  "expires_at_chapter_run_close": true
}
```

它不进入 C3 条目，不影响事实候选内容 hash，不自动写事实账，也不能冒充作者确认。

## 交接顺序

```text
M3 接受两个事实候选
→ hint 只引用 M3 lineage ID
→ M3 发出 C3 handoff、独立 hint manifest 和有序 handoff manifest
→ M4 按冻结顺序写事实候选
→ 接线层读取同一事务的 new_f_ids 回执
→ bridge 按 ordinal 核对 C3 item SHA、章节 revision、数量和端点 current
→ 把 hint 转成 FACT_CAUSAL_EDGE candidate 请求
→ 调用现役 factstore writer，actor=machine，source_identity=model_suggested
→ 保存 CE 候选回执
→ 等作者确认、退役或稍后处理
```

### 为什么不能写 `client_item_key → f-ID`

当前 `C3_FACT_CANDIDATE v1` 没有 `client_item_key`。现役底层 `factstore.add_fact_candidates` 会在事务回执中返回 `new_f_ids`，顺序与通过校验的输入候选一致；但上层 `store.add_fact_candidates` 目前只把 `candidate_count` 返回给调用方，丢掉了编号列表。

R01.1 不能假装稳定映射已经存在。候选方案是另建不扩写 C3 的批次回执：

```json
{
  "contract": "M3_M4_FACT_ID_MAPPING_RECEIPT",
  "version": "r01.1",
  "handoff_id": "handoff_...",
  "m4_operation_id": "op-m4-candidates-...",
  "chapter_revision_ref": {},
  "items": [
    {
      "ordinal": 0,
      "candidate_lineage_id": "cand_...",
      "c3_item_sha256": "64位小写hex",
      "f_id": "f001"
    }
  ]
}
```

接线层必须先证明：输入 C3 均已通过非空检查，M4 没有过滤或重排，`new_f_ids` 数量与 manifest 相同。同一事务回执缺失时立即停止，不能事后按事实文本模糊匹配。

## 必须停止的情况

- 任一端点没有 f-ID；
- M3 候选被拒绝、改写或换 revision；
- 两端相同；
- hint 没有可追源证据；
- 规划依赖、知情关系或人物动机冒充事实因果；
- bridge 试图自己分配 `CE-...`；
- 只能读到 candidate count，读不到同一事务的 `new_f_ids`；
- C3 输入顺序、数量或条目 SHA 与 handoff manifest 不同；
- 机器把候选直接写成 confirmed；
- 章节 run 已结束但 hint 仍未映射。

## 保存期限

- hint 在章节 run 内保留完整 artifact 和 SHA；
- 成功映射后保留 hint→CE 回执，正文可按归档策略收起；
- 端点失效时标 `STALE`，不自动重连新事实；
- run 结束仍未映射时标 `EXPIRED`，不能跨 revision 偷用；
- 是否长期保留过期正文由后续数据保留票决定，R01.1 不自拍。

## 仍需产品票明确的传递能力

当前 M3 读取 C2 并输出 C3，现役 M4 能给事实分配 `f...`，现役底层 factstore 回执含 `new_f_ids`，现役因果 writer 能保存因果边候选。小说辅助产品还缺少一条正式传递接口，把有序 C3 handoff、M4 同一事务的 `new_f_ids` 和 M3 hint 组成可复核映射；当前上层 store 只返回数量。这个缺失会卡住作者从“看见两条事实”进入“查看并确认两条事实之间因果关系”的操作。

来源：Codex
