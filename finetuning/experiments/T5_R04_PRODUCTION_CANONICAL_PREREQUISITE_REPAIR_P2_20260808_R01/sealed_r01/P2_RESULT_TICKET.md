# P2 结果票｜Production Canonical 前置资格修复

⚠️ **P2 已完成账目修复，但在 Production Canonical 候选构造前硬停。**

## 真实漏斗

| 阶段 | 行 | 事实 |
|---|---:|---:|
| 冻结输入 | 398 | 3,537 |
| 权利不明排除 | 314 | 2783 |
| 身份不明排除 | 6 | 69 |
| 位置歧义排除 | 1 | 29 |
| 五本冻结书排除 | 4 | 24 |
| 最终 eligible pool | 73 | 632 |

## 修好的部分

- A v2.7：314 行、2,783 条 evidence 全部在冻结窗口内唯一回填；位置账完成。
- 特殊 84：本地可确认的作者和稳定书号已补；未确认的保持 `IDENTITY_UNKNOWN`。
- 已知重复案 `FS02B-006-S01` 沿用正式隔离票，没有擅取第一次 occurrence。
- 五本冻结书共 4 行、24 条事实全部挡在 eligible pool 外。
- author split 的作者、作品、source 交集均为 0。

## 为什么不能生成 Canonical V1 候选

A v2.7 的本地票只允许生成候选，明确禁止直接训练；没有逐来源训练权利材料。按 P2 纪律只能登记 `RIGHTS_UNKNOWN`，不能因为历史训练过就放行。结果池只剩特殊教材，分布也不具备生产训练资格。

没有生成 `PRODUCTION_CANONICAL_V1_CANDIDATE_R01.jsonl`，没有训练、API、Notion、Git 或现役微调指针变更。

来源：Codex
