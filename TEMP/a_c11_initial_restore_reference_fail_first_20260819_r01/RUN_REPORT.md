# INITIAL／RESTORE 引用门 fail-first 运行回执

## 结论

`CONTRACT_MACHINE_GAP_FOUND`

六个要求的反例全部为错误成功，详细结果见 `CASE_RESULTS.jsonl`。

## 运行范围

- 使用当前正式 C10/C11 字节；
- 外部 R04 只作线索；
- 直接调用正式 Schema、`validate_ledger`、eligibility helper 与 `validate_action`；
- 正式写入 0；API／模型／小说／Gold／Notion／Git mutation 0。

## 数字

- 固定反例：6；
- 错误成功：6；
- Ruff：PASS；
- 自动重试：0；
- TEMP runner 首次只发现一个 unused import，删除后重放；没有改题、预期或正式行为。

## 当前能说和不能说的

可以说：C11 正式机器门存在 INITIAL 组合入口缺口、revision kind 位置缺口和 RESTORE 历史 identity revision 存在性缺口。

不能说：产品已经发生错误写入、C11 整体方向无效、现有 65 项历史结果失效，或本票已经授权修复。

来源：Codex
