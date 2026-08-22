# LEDGER_RECALL_CODE · 取件码扩十本合同

**正式版本：`ledger-recall-code-v1`**

一句话用途：拿一枚钉死版本的取件码，从十本账中的任何一本取回「那条条目的那个版本」；过期或无权被拒并说明原因；条目改判／退役后旧码仍取旧版，回执标明身份（题 7 已拍，AE-M11-N01）。

## 1. 码的形状（C11 revision ref 同族）

```json
{
  "contract": "LEDGER_RECALL_CODE",
  "version": "ledger-recall-code-v1",
  "ledger_name": "事实账",
  "entry_id": "f0007",
  "rev": 1,
  "sha": "aaaaaaaa…（64 位十六进制）",
  "expires_at": null
}
```

| 字段 | 类型 | 规则 |
|---|---|---|
| `ledger_name` | enum | 只允许户籍十本中文名：章节账／事实账／人物账／地点账／物品账／势力账／体系账／世界规则账／长线账／规划账 |
| `entry_id` | str | 该账内的稳定条目 ID（`f0007`、`PE-0412`、`CH-0001`、`DESTINY-0001`……） |
| `rev` | int | 钉死的条目修订号，≥1 |
| `sha` | str | 该版本内容 SHA-256，64 位十六进制 |
| `expires_at` | str/null | 可选过期时刻；非空时解析必须提供当前时刻，否则拒绝判定 |

长线账没有自己的落盘文件：`ledger_name=长线账` 的码解析到规划账里的长线对象（卷／命运／灵感／故事线／伏笔）。不存在第十一本物理账。

## 2. 解析语义

| 情形 | 回执 |
|---|---|
| 有效码 | `{"status":"OK", …, "rev":钉死的那版}` |
| 码过期 | `{"status":"REJECTED","reason":"CODE_EXPIRED"}` |
| 无权 | `{"status":"REJECTED","reason":"UNAUTHORIZED"}` |
| 条目不存在 | `{"status":"REJECTED","reason":"ENTRY_NOT_FOUND"}` |
| 版本不存在 | `{"status":"REJECTED","reason":"REVISION_NOT_FOUND"}` |
| SHA 对不上 | `{"status":"REJECTED","reason":"SHA_MISMATCH"}` |

**题 7 条款**：条目 `confirmed→retired`（改判／退役）后，旧码仍取回旧版本；回执必须带
`"retired_notice": true` 与 `"notice": "此条已改判／退役"`。历史可回是全仓一贯纪律，标明身份就不误导。

## 3. 两种形状并存的边界（复核注记 4，本票不迁移）

**本票选择：不迁移现役行为，两种形状并存。**

| | 形状 A（现役） | 形状 B（本合同） |
|---|---|---|
| 载体 | `rh_` 不透明 handle（`recall_handle_workspace.py`） | `{ledger_name, entry_id, rev, sha}` 明码 |
| 覆盖 | 事实／规划／章节三账 | 户籍十本 |
| 源版本前进 | **STALE 拒收**（`RecallHandleStaleError`） | 不受影响——码钉死那一版，照常取回 |
| 条目退役 | 不适用 | 旧码仍取旧版＋回执标注 |
| 测试 | `tests/test_novel_mvp_recall_handle_workspace.py`，本票一字不改 | `tests/test_novel_mvp_ledger_recall_code_contract.py` |

- 形状 A 的「源一前进就 STALE」语义继续锁死，不迁移到 rev-pinned；
- 题 7 的「旧码仍取旧版」只适用于形状 B；
- 未来若要迁移形状 A，必须另开票、同票改其测试并显式声明，禁止静默改现役行为。

## 4. 明确禁止

1. 禁止发明十本之外的 `ledger_name` 或用英文名。
2. 禁止有效码返回「当前版」代替钉死的那版。
3. 禁止无理由拒绝：REJECTED 必须带 reason。
4. 禁止退役条目的旧码被拒收，或回执不带改判／退役标注。
5. 禁止本票改动 `recall_handle_workspace.py`、packer 一族或其测试。
6. 禁止本票实现十本账取件 runtime 接线（M11 接线另开票）。

## 5. 机器件与状态

- `LEDGER_RECALL_CODE.schema.json`
- `validate_ledger_recall_code.py`
- `LEDGER_RECALL_CODE.fixtures.jsonl`
- `tests/test_novel_mvp_ledger_recall_code_contract.py`

实现状态：`CONTRACT_ONLY__M11_TEN_LEDGER_WIRING_PENDING`。
