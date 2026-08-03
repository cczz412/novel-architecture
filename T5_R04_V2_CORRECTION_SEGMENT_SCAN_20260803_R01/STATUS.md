# STATUS — T5_R04_V2_CORRECTION_SEGMENT_SCAN_20260803_R01

> 本批状态页。机器读 `governance/CURRENT_STATE.json`；本批局部状态看这里。

## 本批信息

- 批次：dense_screen_batch08_cnweb_sparse
- 开工/完成：2026-08-03
- 目标：凑空样本配额（总目标 45 条，当前可信约 21～25，差 20～24）；本轮尽力交 15～20 条 PASS_SPARSE
- 产出目录：`T5_R04_V2_CORRECTION_SEGMENT_SCAN_20260803_R01/work/dense_screen_batch08_cnweb_sparse/`
- 口径：`work/EMPTY_SPARSE_POLICY.md`、`work/SOURCE_TEXT_LOCAL_POLICY.md`

## 状态：已完成

- [x] 读策略（原文件不存在，已落地 work/EMPTY_SPARSE_POLICY.md + work/SOURCE_TEXT_LOCAL_POLICY.md）
- [x] 建工作目录（raw/ + segments/）
- [x] 挑书 + 抓整章（本地库 10 本书，15 章整章落盘 raw/）
- [x] 手读切窗 + 判断（15 PASS_SPARSE + 5 BORDER_SPARSE + 8 REJECT）
- [x] 写 CANDIDATES.jsonl / RECEIPT.json / BATCH_REPORT.md / REJECTS.md / FETCH_META.json
- [x] 自检验收（文件数、jsonl、sha256、segment==raw切片 全通过）

## 交付摘要

- **PASS_SPARSE：15 条**（主交付）
- **BORDER_SPARSE：5 条**（单独记账，未混报"已满"）
- **REJECT：8 条**（REJECTS.md 记原因）
- 类型摊开 9 类，玄幻占比 13.3% ≤25%
- 全部来自本地正文库（/Users/a1234/挣钱/小说101-downloads/），无网页抓取
- rights_state 全标 RIGHTS_PENDING_FOR_TRAINING（较新网文）

## 边界遵守

- 未写 facts 金标
- 未调训练 API
- 未写 Notion
- 未 git commit/push
- 未碰旧 226 金标包、未改 R03 源包
- 未把关键词机筛当金标

## 备注

- token 估计器不存在（仓内无 segment_token_estimator_v1.py），按中文 700-900 字 ≈ 850-1000 tokens 手估
- 4 条 PASS 字数略超 1050（1097-1311），原因：切窗需保段落完整，未在句中截断
- 建议下批补女频现言/古言、纯科幻
