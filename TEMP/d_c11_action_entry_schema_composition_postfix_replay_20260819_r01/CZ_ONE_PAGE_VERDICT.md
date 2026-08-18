# C11 action 入口修后独立重放判决

✅ 判决：`PASS_INDEPENDENT_POSTFIX_REPLAY`。

D 没有拿 A 新增的五条正式夹具当答案，而是重新使用上一轮 fail-first 的构造方式：从同一个合法 REPLACE action 深拷贝，分别改成 INITIAL、BOGUS、缺 `contract`、缺 `version`，再独立对照正式 Schema 和公开 `validate_action`。

## 五例结果

| 子例 | Schema | 公开入口 | 失败路径写入 | 结果 |
|---|---|---|---:|---:|
| 合法 REPLACE | 接受 | `PRECHECK_ALLOWED` | 不适用 | PASS |
| INITIAL | `SCHEMA_REJECT` | `REJECTED_ACTION_SCHEMA` | 0 | PASS |
| BOGUS | `SCHEMA_REJECT` | `REJECTED_ACTION_SCHEMA` | 0 | PASS |
| 缺 `contract` | `SCHEMA_REJECT` | `REJECTED_ACTION_SCHEMA` | 0 | PASS |
| 缺 `version` | `SCHEMA_REJECT` | `REJECTED_ACTION_SCHEMA` | 0 | PASS |

四个非法例的 ledger、C10 records 和写入向量在调用前后 SHA 全等。上一轮发现的“Schema 拒绝但入口放行”没有复现。

## 旧语义有没有被修坏

- 合法 RESTORE 仍返回 `PRECHECK_ALLOWED`。
- 当前正式 validator：旧题 75/75、新入口题 5/5，总计 80/80。
- RESTORE reactivation 仍为 5/5。
- 精确 Ruff 通过。
- Schema JSON 可解析；fixtures JSONL 80 行全部可解析。

这证明 A 的修复不仅是把新增正式夹具写绿：D 的独立 action 构造也通过了公开入口。

## 身份与权限

五份正式输入的开工 SHA 全部等于总控给定值，运行前后也完全一致。A 的两份支持回执同样未变化。

API／模型／自动重试为 0／0／0；正式写入、产品、小说、Gold、R13、Notion、Git、上传、越权路径和缓存污染均为 0。

这个 PASS 只关闭 action Schema 与 `validate_action` 的窄入口缺口，不自动晋升产品能力，也不覆盖其他 C11 接缝。

阶段短回执已经在本目录生成，但向总控任务投递时，Codex 线程工具两次返回“目标任务没有可接收的 active turn id”。第二次已带只读探针确认的 `hostId=local`，仍未送达；本窗按停止规则不再重试。传输失败不改变上述机械判决，详情见 `results/capsule_delivery_receipt.json`。

机器账：`results/postfix_replay_ledger.json`  
当前 validator 输出：`results/current_validator_output.json`  
输入账：`results/input_manifest.json`  
未触碰回执：`results/no_touch_receipt.json`

来源：Codex
