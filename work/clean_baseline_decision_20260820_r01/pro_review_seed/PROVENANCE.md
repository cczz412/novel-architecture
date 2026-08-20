# 种子文件来历

这三份 JSON 摘自 ChatGPT Pro 总审包 `NOVEL_ARCH_CLEAN_BASELINE_AND_TRACEABILITY_REVIEW_20260820_R01.zip`（整包 SHA256 `d357f41e0f978bdea8581bf8374a9074baed417c3b632cb01996344f5343047c`，原件由 CZ 保管，未整包入仓——完整包里的 markdown 分析属于一次性外审证据，不进现役树）。

只收后续工单要直接消费的三件机器文件：

| 文件 | 给哪张工单用 | SHA256 |
|---|---|---|
| `07_REQUIREMENT_SCHEMA_CANDIDATE.json` | 工单 3（需求五轴 schema 候选） | `0f9bfdc6aac62598ab9c310cb7c6e15641a7a14e4b9e6642658b3726ef2dcf7a` |
| `08_CAPABILITY_TRACEABILITY.json` | 工单 3（142 条候选追踪表） | `cd790743f63604fea6085ba45fe65dfb0980511ee1f6f5f2e2945c54750ec71a` |
| `15_ARCHIVE_CANDIDATES.json` | 工单 6（归档候选清单） | `10fa69858b12c813cf9a4587b8b0ae858571c3a1b1563bd793c847370a062813` |

真值边界：三件全部是 **ADVISORY_ONLY 候选**。追踪表里的 owner／maturity 是 Pro 推断，未经逐条复核不得当正式；归档候选不构成移动或删除授权。转正式的动作分别归工单 3 和工单 6。

来源：Cursor 云端 Agent 摘录，2026-08-20
