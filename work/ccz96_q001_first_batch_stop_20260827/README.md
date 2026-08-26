# CCZ-96 第一小批停下回执（2026-08-27）

这是 [CCZ-96](https://linear.app/ccz/issue/CCZ-96) 完整第一小批的停下证据。拍板见 [DR-20260827-01](../../governance/decision_records/DR-20260827-01.md)。

说白了：四对正式 J1×J2 都跑完了，没有一对能继续做 Q001 同章复测。CZ 原话「整票停在这」。

## 归位条件

合并进 `main` 之后，本目录就是这张票的可回读停下回执。它不是正式评测合同，不是 Gold，也不是 CCZ-84 的开工许可。

## 这里有什么

| 文件 | 干什么 |
|---|---|
| [result_card.json](result_card.json) | 机器摘要：停下、不解锁 84、四对回执字段 |
| [ticket_continue_or_stop.json](ticket_continue_or_stop.json) | 票级继续／停下 |
| [pairs/](pairs/) | 四对各自的继续／停下回执 |
| [independent_spot_check.json](independent_spot_check.json) | 独立抽查 PASS |
| [MANIFEST.sha256.json](MANIFEST.sha256.json) | 本目录文件哈希 |

## 明确没进 Git 的

128 份信封、原字节裁决、章节／候选正文、模型原始回包、供应商钥匙。那些还在本机 TEMP，丢了不能靠这份 work 目录复原现场。

## 边界

- 不评分
- 不把对照次数写成准确率
- 不改 GitHub 正式合同或产品代码
- CCZ-84 仍不得扩另外五个样本

来源：Cursor（Grok 4.6）；CZ 2026-08-27
