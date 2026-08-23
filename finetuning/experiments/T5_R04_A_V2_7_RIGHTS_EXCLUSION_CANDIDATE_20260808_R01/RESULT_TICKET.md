# A v2.7｜74 组退出当前训练路线候选结果票

状态：`CANDIDATE_PENDING_CZ_CONFIRMATION`

✅ 74 个来源组已经全部生成“当前版本不用于内部模型训练”的派生候选。

## 结果

| 项目 | 数量 |
|---|---:|
| 来源组 | 74 |
| 教材行 | 314 |
| 事实 | 2,783 |
| `RIGHTS_REJECT_CANDIDATE` | 74 |
| `RIGHTS_ALLOW_CANDIDATE` | 0 |
| 可训练组 | 0 |
| 生产晋级 | 0 |

74 行同时满足：

- 项目使用决定为 `REJECT_FOR_TRAINING`；
- 允许用途为 `FORBIDDEN`；
- 候选状态为 `CANDIDATE_PENDING_CZ_CONFIRMATION`；
- 仍需 CZ 确认；
- 不可训练、没有生产晋级。

## 边界怎么读

原 P3/P4 证据里的权利状态仍然是 `RIGHTS_UNKNOWN`，没有被覆盖。这次登记的是项目使用决定：当前版本退出内部训练路线。它不是版权法律结论，也不妨碍某组将来凭真实证据在新 revision 中单独重审。

## 机械身份

- 74 行决定输入 SHA：`761c74ad71bab07e38951998130283da0bc3238b8c5add54e9440c5a8346006a`
- 74 行派生候选 SHA：`6baa0ace33d96505d04e046a80ca087bd9011b635410b986a1b706c55d1dce5b`
- P4 实时候选导入回执 SHA：`5a013eaa4a96aa00cad1dc04688d509e3f79a7860220d5178b5198a867ace796`
- 来源绑定 SHA：`9998274454782230496849b393b1777f2cf05c17503d7e450b83bf0a4c407257`
- 两次决定构建：逐字一致；
- 两次 `REALTIME_CANDIDATE` 导入：候选逐字一致；
- 实时时钟只在导入回执 sidecar 中登记，没有写入稳定决定输入。

## 未做事项

- 没有改变 P3/P4 既有文件或 sealed；
- 没有把 `RIGHTS_UNKNOWN` 改写成已获权利或法律否定；
- 没有生成训练资格或 Production Canonical；
- 没有训练、调用模型/API、生成 synthetic；
- 没有写 Notion、操作 Git或切换现役指针；
- 没有自行晋升这份候选。

👉 下一步只等 CZ 按最终候选 SHA 确认。

来源：Codex
