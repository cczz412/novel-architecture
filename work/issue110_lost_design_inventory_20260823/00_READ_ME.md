# #110 弄丢的最初设计 · 工作页

给 CZ 看的活页。只搜集登记，不施工。

- 工单：[issue #110](https://github.com/cczz412/novel-architecture/issues/110)
- 清单正文：[CANDIDATE_LIST.md](CANDIDATE_LIST.md)
- 续跑备忘（对照表 v0.1＋报告背景板已摘）：[CHECKPOINT_20260823.md](CHECKPOINT_20260823.md)
- 调查包：[SURVEY_PACK/](SURVEY_PACK/)
- 回包（候选，待拍）：[returns/00_LANDING.md](returns/00_LANDING.md)（外调现役＝ChatGPT Pro＋网搜那份；拍板外审＝[chatgpt_pro_board_review_20260824.md](returns/chatgpt_pro_board_review_20260824.md)）
- 本页只搜集登记，不改 `novel-mvp/contracts/`，不施工。
- 正式 Git 路径就是本目录 `work/issue110_lost_design_inventory_20260823/`。TEMP 那份只是起草现场，以这里为准。
- 归位条件：#110 过目、对照表开写，或并入正式评测材料之后，本目录退出 `work/`。不冒充 contracts。

## 来源怎么读（顺着去看原页）

清单里每条都标了来源身份。别把「本仓没进 contracts」理解成「Git 里没有」。

| 身份 | 什么意思 | 怎么打开原页 |
|---|---|---|
| **本仓 Git** | 小说架构仓库已经追踪 | 相对仓根的路径。纯 ASCII 的可点链接；路径里有中文时 Cursor 常点不开，复制反引号里的相对路径 |
| **本仓 TEMP** | 磁盘上有，被 `.gitignore` 挡住 | 不能 `git show`。Git 里往往只剩 `intake/manifests/` 登记卡，先开登记卡再按它写的磁盘路径找正文 |
| **NVM 仓 Git** | 另一份仓库，不在小说架构的 git 树里 | 复制 `` `/Users/a1234/NVM/active/requirements/…` ``。那边自己有 git，本仓搜「困境实体」会是零命中 |
| **旁仓磁盘、无 Git** | 小说101、外置仓 | 没有 commit 可追，只能打开磁盘文件 |

## 现在这页是什么程度

2026-08-23 下午后半：六组关键词**没找全**。又从已找到的真身页里扒了一批当时一起设计、用词已经忘掉的邻近概念（组7）。**还不是终稿。** Notion 原页 CZ 已拍不搜（2026-08-23）。

## 还要补（按急）

1. ✅ 已销｜Notion 页面：CZ 拍不搜（2026-08-23），理由＝旧内容废案＋防上下文污染
2. git 里「知情边从方向拍板变成合同禁止」对到哪次 commit
3. NVM `requirements_examples/` 填表示例
4. `小说架构_隔离实验/` 细扫（目录大）
5. ✅ 已补：丢掉困境／动机的那一刀＝2026-08-22 十本账内容合同草案
6. ✅ 已补：同页邻概念组7（关系实体、离屏、待唤回、一句话暗稿、规划里程、切线包、不可逆、情境签名、`must_carry` 近亲）
7. ✅ 已补：每条写清来源身份（本仓 Git／本仓 TEMP／NVM 仓 Git／旁仓无 Git），方便顺着打开原页

## 别搞混的三句话

- 「弄丢」多半不是文件删了，是设计还在、现行台账没收。
- [CHAPTER_SLOT_SNAPSHOT.md](../../novel-mvp/contracts/CHAPTER_SLOT_SNAPSHOT.md) 不是章末人物状态快照。
- NVM 的 hook ≠ 规划账 `hook` 三态 ≠ 四件套 C 读者承诺。规划账里已经有个近亲叫 `must_carry`（必写承接）。
- 现行故事线三件套不是当初那整本故事线（缺节点／里程／关联困境）。
