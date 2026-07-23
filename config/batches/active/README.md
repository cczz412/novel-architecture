# batches/active

第84道分档规则 `batches_active_vs_archive_v1_conservative`：

- 默认链（`config/defaults/zbatch_v1.2_full_chain.json`）是现役，**不是**某个 batch JSON。
- 登记无 `active_batch_path` 字段 → **active 名单为空**。
- ⚠️ 本轮**不物理挪** JSON（团队 R2：`Path.resolve()` 写回会打穿 archive）。真身仍在 `config/batches/*.json`。
- 物理迁档须另拍：先加写回闸（禁 resolve 后写 archive）再 mv＋软链。
