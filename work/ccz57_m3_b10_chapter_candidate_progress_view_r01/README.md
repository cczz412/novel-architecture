# CCZ-57 M3 B-10｜当前章节候选处理进度纯派生视图

这个目录落实 GitHub #228／Linear CCZ-165 已采纳的 R03 设计。它只按需读取当前权威对象，回答“这一章的候选处理走到哪”；读取结束后，两张视图都丢弃。

## 两张视图

- `M3_CURRENT_CHAPTER_CANDIDATE_PROGRESS_VIEW` 是内部机械视图。它保留 B-01 分母、B-06 指针与候选、B-07 current run、B-08 exact-current terminal 的核验结果。
- `M3_AUTHOR_VISIBLE_CHAPTER_CANDIDATE_PROGRESS` 是作者白名单投影。它只给出可用性、处理状态、段数和作者下一动作，不暴露内部引用、哈希、run、指针、模型或调试信息。

`availability` 与 `candidate_processing_state` 是两条轴。权威读取失败、身份映射不唯一、镜像列或哈希错误、请求已不是 current、读前读后发生变化时，视图只返回 `UNAVAILABLE`；处理状态和段数全部为空，不能拿旧成功结果兜底。

## 权威路径

固定读取顺序是：

1. B-01 exact SegmentIndex 给出当前章节修订和完整责任段集合；
2. B-07 的 `candidate_pointer_key` 读取 B-06 live pointer，再读取 current CandidateVersion；
3. CandidateVersion 自带 `segment_index_ref` 与 `seg`，据此回到 B-01 exact segment，不解析指针字符串；
4. B-08 terminal 只通过 exact-current 复验后才计入完成；
5. 每个 B-01 预期段都必须有一个解析结果。没有 current run 也要留下 `AUTHORITATIVE_NO_CURRENT_RUN`；已终结但没有 terminal 要留下 `TERMINAL_PENDING`；
6. 完整身份集合必须相等，并对同一范围读两遍。正向引用或负结果见证发生变化，整张视图都不可用。

## 边界

这里没有 B-10 record、writer、数据库表、Manifest、生命周期、保留期或清理任务。它不读正文，不调用模型或网络，不依赖 B-09／B-11／B-12，也不写 CCZ-142 runtime、C11、M4、M5、M9 或十本账。

`COMPLETE` 只代表当前 M3 责任段的候选处理完整，不代表事实正确、章节完成、作者确认、质检通过、关章或账本入账。

定向验证：

```bash
uv run --locked pytest -q work/ccz57_m3_b10_chapter_candidate_progress_view_r01/test_current_chapter_progress_view.py
uv run --locked python work/ccz57_m3_b10_chapter_candidate_progress_view_r01/self_check.py
```

来源：Codex
