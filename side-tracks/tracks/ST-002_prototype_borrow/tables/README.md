# ST-002 tables｜深拆／试验产品账

## CSV 还是 Excel？

✅ **主账用 CSV**（本目录）  
💡 要透视／筛选：Excel／Numbers 另存浏览副本；真源仍以 CSV 为准。

## 你要干什么 → 打开哪张

| 你想… | 打开 |
|---|---|
| **借结构零件** | [product_deep_parts.csv](product_deep_parts.csv)（零件）＋ [product_deep_book.csv](product_deep_book.csv)（书头） |
| **看纸面示范** | [product_trial.csv](product_trial.csv)（一律 `paper_only`） |
| 找还没深拆的火书候选 | [prototype_candidates.csv](prototype_candidates.csv) |

整理入口（按用途）：[dr_three_tables_tidy_20260719/](../../../../TEMP/dr_three_tables_tidy_20260719/)

## 其他表

| 文件 | 内容 |
|---|---|
| `prototype_deep.csv` | 旧模具深潜 w01（A～F）；完整原件见外置对象 `side-track-st002-prototype-borrow-legacy-tables-20260718-v1` |
| `borrow_downstream.csv` | 下游借用谱系（早期窗）；完整原件见同一外置对象 |
| `exclude_fingerprints_batch01.txt` | 清单排除区素材；完整原件见同一外置对象 |
| [ingest_meta.json](ingest_meta.json) | 入站机器摘要 |

弱兼容：`survey_not_ledger`；零件槽＝候选，不是真账。
