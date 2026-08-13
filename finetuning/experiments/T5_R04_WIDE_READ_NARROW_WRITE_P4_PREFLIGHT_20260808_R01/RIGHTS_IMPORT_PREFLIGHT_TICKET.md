# P4 A 线｜权利裁决导入预检票

✅ 结论：权利导入器的离线预检已通过。真实 dry-run 读到 74 个来源组、314 行、2783 条事实；74 组全部仍是权利未知，放行候选为 0，可训练组为 0。

这张票只证明“导入机械闸能失败关闭”，不是权利批准，也不会让任何材料进入训练。

## 本次 dry-run 绑定

- 74 组来源真源：`finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/sealed_inputs_r01/track_a/RIGHTS_SOURCE_GROUPS_314.jsonl`
  - SHA-256：`08c576787d1d3153d95ed52dd4c5a0462ee7d08f66bca2be21df9fa66171db95`
- 74 组裁决模板：`finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/sealed_inputs_r01/track_a/RIGHTS_DECISION_TEMPLATE.jsonl`
  - SHA-256：`e8b870daedf4161f670f5dd73ee67814343115af2966353cfc50cfc0fc15b945`
- 导入 Schema：`RIGHTS_DECISION_IMPORT_SCHEMA.json`
  - SHA-256：`25b8434b8ae1e396a8b679bb60b2e91abd03c9dfd13745543a804705aafc8b6d`
- 派生候选：`dry_run/RIGHTS_DECISION_DERIVED_CANDIDATE.jsonl`
  - 74 行全部为 `RIGHTS_UNKNOWN`
  - 74 行全部为 `CANDIDATE_PENDING_CZ_CONFIRMATION`
  - 每行都绑定整份 74 组来源快照 SHA-256：`08c576787d1d3153d95ed52dd4c5a0462ee7d08f66bca2be21df9fa66171db95`
  - 每行保留本组的 record SHA 和本裁决行 SHA；两类 SHA 各有 74 个唯一值
  - 每行都显式含 `allowed_use` 和 `validity`；本次全部为空，不作推断
  - SHA-256：`32d0e8c65e107dc448509db79a2a2379e56fee579febbb54c9354c7f4e904560`
- 机器回执：`RIGHTS_IMPORT_DRY_RUN_RECEIPT.json`
  - 状态：`PASS_DRY_RUN_ALL_RIGHTS_UNKNOWN_NO_PROMOTION`

⚠️ `CZ_DECISION_REQUIRED` 只能在 `--mode DRY_RUN` 中当作“仍未裁决”读入。dry-run 只要混入放行或拒绝就硬停；普通候选导入只要还有未裁决值也硬停。

冻结来源路径、来源 SHA、74／314／2783 计数、Schema 路径和 Schema SHA 全部写死在公开导入入口内，CLI 不提供替换参数。

## 任何放行候选都必须同时满足

- 权利主体不能为空，并写入 `rights_holder`。
- 用途只接受精确的 `INTERNAL_MODEL_TRAINING`，不接受近义改写或模糊范围。
- 授权文档必须是存在、非空、绝对且已解析的真实文件；文件字节的 SHA-256 必须与裁决行一致。
- 有效期必须同时写明开始日和结束日，且覆盖系统 UTC 转 Asia/Shanghai 后的真实导入当天。普通入口不接受调用者回填日期。
- 行范围要精确列出全部 `row_ids`；行数、事实数和顺序都要与 P3 来源组完全一致。
- 来源、书、作者、源文 SHA、行数、事实数、权利主体、用途、有效期和授权文档 SHA，必须同时写入一份独立的 authority snapshot JSON。
- 裁决行还要绑定这份 authority snapshot 的真实路径和 SHA-256；快照内容不完全相等也会硬停。

真的要导入放行候选时，需要在 P3 模板行上补齐 `author_id`、`author_name`、`source_sha256`、`row_scope`、`authority_snapshot_path` 和 `authority_snapshot_sha256`。authority snapshot 只接受 `t5-r04-p4-rights-authority-snapshot-v1` JSON，且它的整个对象必须与导入器重建出的绑定对象逐字段相等。

即使上面全部通过，输出也只会写成 `RIGHTS_ALLOW_CANDIDATE`，并强制保持：

- `training_eligible = false`
- `cz_confirmation_required = true`
- `production_promoted = false`
- `p2_sealed_modified = false`

历史日期只能走 `--mode REPLAY_ONLY`。Replay 就算读到历史 approve，也只输出 `RIGHTS_REPLAY_OBSERVATION_ONLY`，不产生 allow candidate，`allowed_use = null`，且永远不可训练、不可晋级。

玩具测试的伪时钟只存在私有测试 core，公开入口不接受。伪时钟与冻结 baseline 同时出现会在写文件前硬停；测试产物只写 `RIGHTS_TEST_ONLY_OBSERVATION`，不写正式权利状态。

## 会硬停的情况

重复组、漏组、陌生组、跨组重用行 ID、未知裁决值、来源或计数漂移、只填一部分放行字段、授权证据不存在、文档 SHA 漂移、快照 SHA 漂移、快照内容漂移、行范围不精确、授权过期、候选输出路径覆盖授权证据，都会在写出候选和回执之前失败。

## 中途纠偏记录

- 经过只读审查，dry-run 混入 allow，Schema 未锁 SHA，调用者日期掩盖过期授权三个失败面被硬停修正。
- 回归新增断言曾误插到错的测试作用域，现场为 `1 failed / 18 passed`；已移回弱化 Schema 专项测试。
- Replay observation-only 收紧期间先后出现 `2 failed / 17 passed`、`3 failed / 17 passed`和 `1 failed / 19 passed`；原因都是旧断言还在期待正式 allow／reject／replay PASS。现已统一改成 TEST_ONLY／observation-only，并补上冻结 baseline 禁用伪时钟的硬停测试。
- 上述历史与修正也以 `P4-RIGHTS-CORR-01`～`P4-RIGHTS-CORR-09` 写入机器回执，没有删掉中途失败。

## 本次验证

```bash
uv run --locked pytest finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01/tests/test_rights_decision_import.py -q
```

结果：`21 passed`。测试材料全部是玩具数据，没有把真实小说正文或真实授权文件当测试样本。

P4 全目录测试：

```bash
uv run --locked pytest finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01/tests -q
```

结果：`33 passed`。

同时通过：

```bash
uv run --locked ruff check finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01/tools/rights_decision_import.py finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01/tests/test_rights_decision_import.py
```

本轮没有训练、没有模型或 API 调用、没有 Notion 写入、没有 Git 操作，也没有修改 P3／P2 sealed 上游。

来源：Codex
