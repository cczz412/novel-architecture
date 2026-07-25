# 回包怎么接｜归档后的恢复规则

⚠️ 下面三条旧工作夹已经外置，仓内只剩 `ARCHIVED.md` stub。**现在不能把新回包直接丢进旧 `returns/`，也不能照旧“下一窗”文字直接续跑。**

## 旧工作夹从哪找

| 支线 | 仓内 stub | 真身入口 | TRACK |
|---|---|---|---|
| ST-001 语料重标 | [dr_corpus_relabel_20260718/](../TEMP/dr_corpus_relabel_20260718/) | 读 stub 内的外置绝对路径与 manifest | [ST-001](tracks/ST-001_corpus_relabel/TRACK.md) |
| ST-002 原型书 | [dr_prototype_borrow_20260718/](../TEMP/dr_prototype_borrow_20260718/) | 读 stub 内的外置绝对路径与 manifest | [ST-002](tracks/ST-002_prototype_borrow/TRACK.md) |
| ST-003 世界观纸面 | [dr_worldview_paper_20260718/](../TEMP/dr_worldview_paper_20260718/) | 读 stub 内的外置绝对路径与 manifest | [ST-003](tracks/ST-003_worldview_paper/TRACK.md) |

看不清是哪条时，可以先放 [inbox/](inbox/) 并写明「这是 ST-00X」或「语料／原型／世界观」；不要猜一个旧 returns 路径硬塞。

## Agent 接到新回包后必须做的

1. **先核身份**：确认属于哪条 TRACK、旧真身是否仍需回读、当前是否有继续授权。
2. **另建工作夹**：使用新的 ASCII 路径；旧 `ARCHIVED.md` stub 一字不动。
3. **登记来源**：写原路径、目标路径、文件身份和 SHA，再拷入新工作夹。
4. **记进度**：更新 TRACK／LOG／BOARD，明确旧窗已归档、新窗从哪里接。
5. **可选沉淀**：锚点或介绍可进 [book-meta/](../references/book-meta/)；外部意见仍不替代正文真值。
6. **交下一窗**：只从新工作夹生成 Prompt，回复里给可点路径。

❌ 不要：写进 `governance/CURRENT_STATE.json`、`decisions.md` 或主线 `reports/`；不要把正文拷进仓；**禁止往 stub 里续写**。

💡 旧三表产品字段和 Prompt 口径在外置归档里。恢复时先按 stub 指针回读真身，不能把仓内缺失文件当作仍可直接打开的现役合同。

## 你怎么跟我说就行

- 「这是语料第1窗回包」＋贴路径或丢 Downloads  
- 「下一窗」→ 先核该 TRACK 是否已经恢复并登记新工作夹，再切 Prompt
- 「这是原型清单回包」→ 先恢复 ST-002 身份并登记新工作夹，再决定是否勾 30 本开深潜
