# Production Canonical V1 建设计划

## 要解决什么

当前 A v2.7 和特殊 84 都是“可以直接喂给模型的消息卷”。生产 canonical 要比消息卷更靠上：人工只维护一次事实语义和证据位置，A/C2 都由程序生成。

本轮没有生成实体 canonical，因为权利和身份信息还没齐。

## 每个 case 必须保存

```json
{
  "case_id": "PCV1-000001",
  "source_id": "SRC-...",
  "book_id": "BK-...",
  "author_id": "AU-...",
  "chapter_id": "CH-...",
  "source_family_id": "SF-...",
  "source_sha256": "...",
  "window": {
    "context_start": 0,
    "responsibility_start": 120,
    "responsibility_end": 860,
    "context_end": 980
  },
  "rights": {
    "status": "TRAINING_CLEARED",
    "use_scope": "INTERNAL_TRAINING_AND_EVALUATION_ONLY",
    "authority_id": "..."
  },
  "facts": [
    {
      "fact_id": "PCV1-000001-F01",
      "fact": "...",
      "status": "已发生",
      "speaker": null,
      "evidence_text": "...",
      "evidence_start": 200,
      "evidence_end": 230
    }
  ]
}
```

位置统一相对冻结的 source window 计算，左闭右开。必须满足：

```text
source_window[evidence_start:evidence_end] == evidence_text
```

同一 evidence 文本出现多次时，只认 canonical 明确保存的位置，禁止搜索后默认取第一次。

## 权利分层

- `TRAINING_CLEARED`：可进入训练候选；
- `RIGHTS_PENDING`：只读盘点和审查；
- `REFERENCE_ONLY`：只作参考；
- `REJECTED`：不得继续使用。

任何 case 只要 book、author、source、位置或权利有一项缺失，就进隔离账，不进训练分母。

## A 与 C2 怎么生成

- A：程序从明确位置回填逐字 `evidence`；
- C2：冻结 atomizer 只读正文，生成 B/T 单元，再从明确位置取最小覆盖的 `evidence_ids`；
- 两边的 fact、status、speaker、case 顺序和分母必须逐条一致；
- C2 派生失败就隔离，不允许在 C2 一侧手改答案。

## 迁移顺序

1. 给书、作者、章节和来源族补稳定 ID；
2. 把逐书权利票绑定到 case；
3. 从旧 A 消息卷恢复正文窗口和事实；
4. 从已核验来源映射恢复 evidence 明确位置；
5. 两次独立构建，要求 canonical SHA 一致；
6. 做语义双审和分歧裁决；
7. 通过 split 闸后才生成训练视图。

## 当前不能直接迁入的材料

- 正向 314 行：权利账和稳定 evidence 位置未齐；
- 特殊 84 行：作者身份未齐，旧 69 行稳定书号未齐；
- 当前五本冻结书：全部不进新 canonical 的训练分母；
- 现有 DEV、旧 41/48、MICRO24：只能保留各自历史身份。

来源：Codex
