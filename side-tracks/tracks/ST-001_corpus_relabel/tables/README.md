# ST-001 tables｜浅表产品账

## 你要干什么

**逛书库**：看梗概＋分类。真源是 [product_shallow.csv](product_shallow.csv)（350 本）。

| 文件 | 用途 |
|---|---|
| [product_shallow.csv](product_shallow.csv) | 产品浅表（给人逛） |
| [ST001_COMPATIBILITY_MAP.json](../ST001_COMPATIBILITY_MAP.json) | `corpus_relabel.csv` 的历史行号兼容键、外置对象和恢复身份 |
| [identity_resolve.csv](identity_resolve.csv) | 认亲裁决结果 |
| [pending_identity_queue.csv](pending_identity_queue.csv) | 认亲队列（仍开看 `still_open`） |

`corpus_relabel.csv` 是冻结历史调查表；Git 只保留稳定兼容映射，完整原字节按映射登记的 archive object 恢复。本机可保留同路径副本，但它不是 Git 真源。

整理入口（按用途）：[dr_three_tables_tidy_20260719/](../../../../TEMP/dr_three_tables_tidy_20260719/)

⚠️ w01 五十本梗概是「旧窗缺字段」占位，见同包 `w01_synopsis_gap.csv`。  
主账用 CSV；Excel 只作浏览副本。
