# side-tracks｜支线台账（不是主线路牌）

⚠️ **这不是主线。** 主线进度只认 [current.md](../current.md) 与 `reports/Z00*`。  
本目录只记 Cursor／旁路调查：做到哪、下一窗开什么、回包放哪。

状态默认：`欠回传·非消账·非已拍·非开工`

## 和主线怎么隔离（缺一条就不要往这边加活）

| ✅ 可以写 | ❌ 绝对不要写／跑 |
|---|---|
| `side-tracks/` 本台账 | [current.md](../current.md) |
| `TEMP/dr_*` 等 **ASCII** 工作夹 | [decisions.md](../decisions.md)（支线结论禁止往这儿钉） |
| [references/book-meta/](../references/book-meta/) 介绍／DR 沉淀 | `reports/` `runs/` `config/` `tools/` `work/` `outbox/` |
| [references/survey-inbox/](../references/survey-inbox/) 调查角度／GitHub／短视频讲法（攒批） | `foundation/` 大改、zbatch run／重算／分类规则 |

## 进度以谁为准

- **做到哪了** → 只看本目录 [BOARD.md](BOARD.md) ＋各条 `TRACK.md`
- **Prompt／回包原件** → `TEMP/dr_*` 或各 TRACK 里写的工作夹
- TEMP 不是第二本进度账；换窗先打开 BOARD，再按 TRACK 去 TEMP 拿文件
- **扔报告／要下一窗** → [INGEST.md](INGEST.md)（每条支线对应哪个 `TEMP/dr_*/returns/`）

## 怎么新开支线

1. 复制 [_template/TRACK.md](_template/TRACK.md) → `tracks/ST-00X_short_ascii_name/TRACK.md`
2. 在 [BOARD.md](BOARD.md) 加一行
3. 文件夹名 **必须 ASCII**（中文写在正文里；路径含中文 → 链接乱码点不开）

## 三调查并行时

一调查一条 TRACK，不要合并成一章三个小节。BOARD 只做总览。
