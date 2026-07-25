# side-tracks｜支线台账（不是主线路牌）

⚠️ **这不是主线。** 当前任务只认 [治理索引](../governance/INDEX.md)；根 `current.md` 与旧 `reports/Z00*` 只作历史回放。
本目录保存旁路调查的历史台账，不得覆盖主线状态。

## 当前归档状态

`BOARD.md`、`INGEST.md` 和各条 TRACK 记录的是 2026-07-19 的历史快照。它们原先指向的 `TEMP/dr_*` 工作夹已经外置，仓内目录只剩 `ARCHIVED.md` stub。

- stub 可以告诉你真身在哪，但**不能直接接收新文件**；
- 想恢复一条支线时，先核对外置真身与 manifest，再新建当轮 ASCII 工作夹；
- 新工作夹、授权和下一动作必须重新登记到 TRACK／BOARD，不能沿用旧“下一窗”文字直接开工。

状态默认仍是：`欠回传·非消账·非已拍·非开工`。

## 和主线怎么隔离（缺一条就不要往这边加活）

| ✅ 可以写 | ❌ 绝对不要写／跑 |
|---|---|
| `side-tracks/` 本台账 | `governance/CURRENT_STATE.json` 与生成路牌 |
| 当轮新建且已登记的 **ASCII** 工作夹 | [decisions.md](../decisions.md)（支线结论禁止往这儿钉） |
| [references/book-meta/](../references/book-meta/) 介绍／DR 沉淀 | `reports/` `runs/` `config/` `tools/` `work/` `outbox/` |
| [references/survey-inbox/](../references/survey-inbox/) 调查角度／GitHub／短视频讲法（攒批） | `foundation/` 大改、zbatch run／重算／分类规则 |

## 进度以谁为准

- **做到哪了** → 只看本目录 [BOARD.md](BOARD.md) ＋各条 `TRACK.md`
- **Prompt／回包原件** → 只认本轮重新登记的新工作夹；旧 TRACK 里的 `TEMP/dr_*` 路径只负责指向归档 stub
- TEMP 不是第二本进度账；换窗先打开 BOARD，再按 TRACK 核实新工作夹是否已经登记
- **扔报告／要下一窗** → [INGEST.md](INGEST.md)（先恢复身份，再决定新回包落点）

## 怎么新开支线

1. 复制 [_template/TRACK.md](_template/TRACK.md) → `tracks/ST-00X_short_ascii_name/TRACK.md`
2. 在 [BOARD.md](BOARD.md) 加一行
3. 文件夹名 **必须 ASCII**（中文写在正文里；路径含中文 → 链接乱码点不开）
4. 如果旧工作夹已是 `ARCHIVED.md` stub，必须另建新目录，禁止往 stub 里续写

## 三调查并行时

一调查一条 TRACK，不要合并成一章三个小节。BOARD 只做总览。
