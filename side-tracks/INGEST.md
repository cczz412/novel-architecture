# 回包怎么扔｜别乱

你以后基本两步循环：**扔报告 → 要下一窗 Prompt**。  
Agent 按下面分流；你也可以自己丢进对应 `returns/`。

## 一张表：报告属于哪条支线

| 支线 | 工作夹（Prompt／书单） | **回包只进这里** | TRACK |
|---|---|---|---|
| ST-001 语料重标 | [dr_corpus_relabel_20260718/](../TEMP/dr_corpus_relabel_20260718/) | [returns/](../TEMP/dr_corpus_relabel_20260718/returns/) | [ST-001](tracks/ST-001_corpus_relabel/TRACK.md) |
| ST-002 原型书 | [dr_prototype_borrow_20260718/](../TEMP/dr_prototype_borrow_20260718/) | [returns/](../TEMP/dr_prototype_borrow_20260718/returns/) | [ST-002](tracks/ST-002_prototype_borrow/TRACK.md) |
| ST-003 世界观纸面 | [dr_worldview_paper_20260718/](../TEMP/dr_worldview_paper_20260718/) | [returns/](../TEMP/dr_worldview_paper_20260718/returns/) | [ST-003](tracks/ST-003_worldview_paper/TRACK.md) |

看不清是哪条？先丢 [inbox/](inbox/)，并说一句「这是 ST-00X」或「语料／原型／世界观」。

## Agent 接到报告后必须做的

1. **落盘**：拷进上表对应 `returns/`，文件名带窗号，例：`w01_trial50.md`、`p1_batch01.md`  
2. **记进度**：改该支线 `TRACK.md` 窗进度表＋往 `LOG.md` 追加一行  
3. **更新** [BOARD.md](BOARD.md) 那一行的「进度一句话／下一手」  
4. **可选沉淀**：锚点／值得留的介绍 → [book-meta/](../references/book-meta/)（仍不进正文）  
5. **结构化大表**：ST-002 用 CSV 追加（见 [tables/](tracks/ST-002_prototype_borrow/tables/)）；ST-001 语料重标回包稳定后再建同款 CSV  
6. **交下一窗**：切好下一份 Prompt（仍 ASCII 路径），在回复里给可点链接  

❌ 不要：写进 `current.md`／`decisions.md`／`reports/`；不要把正文拷进仓。

💡 三表产品字段（浅表／深拆／试验）与新 Prompt 口径：[团队裁决](../TEMP/cursor_team_three_tables_20260718/团队裁决_三表与Prompt优化.md)。入站时按新硬字段核：浅表有无 `reader_synopsis`；深潜有无 `arch_slot_candidate`／`mountability`；试验有无 `demo_usage`＋`paper_only`。

## 你怎么跟我说就行

- 「这是语料第1窗回包」＋贴路径或丢 Downloads  
- 「下一窗」→ 我按 TRACK 切下一批 50 本 Prompt  
- 「这是原型清单回包」→ 进 ST-002 returns，再问你要不要勾 30 本开深潜  
