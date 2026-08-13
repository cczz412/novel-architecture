# P1 本地优先生产门｜入口

状态：**HARD STOP｜只完成盘点与合同，不训练、不调用豆包、不切换现役指针**。

## 大白话结论

现成的 398 行 A/C 教材可以当历史实验资产，但还不能直接升级成 `PRODUCTION_CANONICAL_V1_CANDIDATE`：

- 正向 314 行缺逐行训练权利账，也没有冻结的 evidence 明确位置；
- 特殊 84 行虽有内部训练权，但 84 行都缺作者身份，旧 69 行还缺稳定书号；
- 当前五本冻结书有 4 行存在于历史特殊卷，新 P1 数据必须排除，历史文件不回写；
- 当前 TRAIN／DEV 不是按作者隔离形成的新生产 split。

因此本轮只建立 P1 路线、盘点票和缺口账。任何本地真实数据训练都要等权利、canonical 和 split 三道门同时通过。

## 这轮新增什么

- 云训练成本覆盖条款；
- 生产 canonical、真实 split、本地 A/C2、evidence-first、数据规模实验合同；
- Mini 单任务与 Cloud Entry Gate；
- Lite 先跑 BASE 的成本纪律；
- P1 实物盘点、硬停锁和缺口账。

## 没有改什么

- P0 八个历史文件；
- A v2.7、特殊 84、历史 A/C 训练卷与成绩；
- `finetuning/CURRENT.json`；
- `governance/CURRENT_STATE.json`；
- 模型、权重、考卷、金标和外部平台。

来源：Codex
