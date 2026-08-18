# C11 action Schema／公开机器入口独立审查

🔥 判决：`CONTRACT_MACHINE_ENTRY_GAP_FOUND`。

这次找到了一个真实入口不一致，而且正好命中工单规定的立即停点：同一份 action，正式 Schema 判非法，公开 `validate_action` 却返回 `PRECHECK_ALLOWED`。

## 实际执行结果

| 子例 | action Schema | `validate_action` | 结论 |
|---|---|---|---|
| 合法 REPLACE | 通过 | `PRECHECK_ALLOWED` | 通过 |
| `change_kind=INITIAL` | 拒绝；错误码 `SCHEMA_REJECT` | `PRECHECK_ALLOWED` | 机器入口缺口 |
| `change_kind=BOGUS` | 未运行 | 未运行 | 首个缺口后按 fail-first 停止 |
| 缺 `contract` | 未运行 | 未运行 | 首个缺口后按 fail-first 停止 |
| 缺 `version` | 未运行 | 未运行 | 首个缺口后按 fail-first 停止 |

精确证据在 `results/gate_ledger.json`。`INITIAL` 子例只改了 `items[0].change_kind`，其他字节与合法 REPLACE 相同。Schema 返回：

```text
SCHEMA_REJECT::... is not valid under any of the given schemas
```

公开机器入口返回：

```text
PRECHECK_ALLOWED
```

## 最小影响

- `validate_action` 没有在公开入口调用正式 action Schema。
- 当前分支只特别识别 `RESTORE`；其他值全部进入 REPLACE 路径，所以非法 `INITIAL` 被当成 REPLACE 继续预检。
- A 的 75/75 证明它点名的正式夹具通过，但不能覆盖“Schema 与公开入口组合是否一致”这条独立问题。
- 本票没有扫描外部调用者，也没有扩大到 C1—C10；因此这里只判入口缺口，不推断生产影响范围。

## 候选差分（未施工）

最窄修法候选只有三步：公开入口先用正式 action Schema 校验完整 action；Schema 非法时在任何 eligibility 检查前返回稳定拒绝；Schema 通过后只允许精确的 REPLACE／RESTORE 分支。

这只是交给 owner 的候选，不是正式补丁。本窗没有改合同、Schema、validator、fixtures 或产品。

## 边界回执

8 份只读输入前后 SHA 全部一致。API／模型／自动重试为 0／0／0；正式写入、产品、小说、Gold、R13、Notion、Git、越权路径和缓存污染均为 0。

机器账：`results/gate_ledger.json`  
输入账：`results/input_manifest.json`  
未触碰回执：`results/no_touch_receipt.json`

来源：Codex
