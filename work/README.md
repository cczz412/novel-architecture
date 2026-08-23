# work／施工与设计稿工作区

正在施工或只读引用的设计稿、执行单、提示词、Z 批运行配套件。

## 现状分区（按文件夹名认）

| 路径 | 大概放什么 |
|---|---|
| 根上散落 `*.md` | R10／W 批／对撞／Z 批执行单等设计与方案稿 |
| `zbatch_prompts/` | 各阶段 prompt 版本与 candidates |
| `zbatch_decisions/` | 主控决定单 JSON |
| `zbatch_contracts/` | 合同／施工钉子 |
| `zbatch_ab/` · `zbatch_t4/` · `zbatch_nonthinking/` | 预演／permits／gates／seals |
| `zbatch_audits/` | 语义审计 JSON |
| `advisory_returns_20260820_r01/` | 顾问回包。测试设计原文和运行缺口登记已迁走；这里只剩未吸收的双车道／导入设计 |
| `clean_baseline_decision_20260820_r01/` | 干净基线决策书。追踪种子已迁到 governance；这里留决策书和归档候选 |

跑批配置在 `config/`，运行原件在 `runs/`，给人看的判词在 `reports/`——本目录不替代这三者。

来源：第69道步一草稿（待审后落盘）
