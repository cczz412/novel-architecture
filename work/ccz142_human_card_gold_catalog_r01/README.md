# 人话卡对照书目登记

GitHub 施工入口：[Issue #281](https://github.com/cczz412/novel-architecture/issues/281)（第一批书名）、[Issue #284](https://github.com/cczz412/novel-architecture/issues/284)（第二批新书）、[Issue #289](https://github.com/cczz412/novel-architecture/issues/289)（候选窗口／密度口径／金标命名）。模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)。

✅ 对照可以有两批。第一批仍是 **全职高手、道诡异仙、十日终焉**。第二批用试拆已锁的新书：**炼气士不死于无限、我在美恐科普都市传说、请勿高考时渡劫**。两批都已登记候选章号，都还没读正文，更没有金标。

你可以直接理解成：老书目一批、未见过的新书再一批。知否／凡人仍不用。不自动换入庆余年。第二批不抢第一批那 8–10／上限 12 章。

## 第一批：优先三本

| 书 | 仓内书目指针 | 这批用不用 | 候选章号 |
|---|---|---|---|
| 全职高手 | [corpus-pointers.md](../../references/corpus-pointers.md)、[book-meta INDEX](../../references/book-meta/INDEX.md) | 用 | 1–2、9–10 |
| 道诡异仙 | [corpus-pointers.md](../../references/corpus-pointers.md)、[book-meta INDEX](../../references/book-meta/INDEX.md) | 用 | 1–4 |
| 十日终焉 | [corpus-pointers.md](../../references/corpus-pointers.md)（[book-meta INDEX](../../references/book-meta/INDEX.md) 目前没有这一行） | 用 | 1–2 |

试拆七本书单写过：十日终焉仍只有因果大纲，不当事实句。优书样本库有 1–2 的分章文件。用途未放行，正文未读。

## 第二批：新书三本

这三本在试拆七本里，但和拿掉知否／凡人不是同一回事。那两本是旧书撞车；这三本是故意留的「模型没读过」对照。

仓内 [corpus-pointers.md](../../references/corpus-pointers.md)／[book-meta INDEX](../../references/book-meta/INDEX.md) 目前没有这三行。本包只登记书名、软链路径和候选章号，不把正文拷进 Git。

| 书 | 打算用的路径 | 试拆序号 | 候选章号 |
|---|---|---|---|
| 炼气士不死于无限 | `corpus-downloads/_newbook_rank_20260804/books/炼气士不死于无限/` | 5 | 1–2、15–16 |
| 我在美恐科普都市传说 | `corpus-downloads/_newbook_rank_20260804/books/我在美恐科普都市传说/` | 6 | 1–2、29–30 |
| 请勿高考时渡劫 | `corpus-downloads/_newbook_rank_20260804/books/请勿高考时渡劫/` | 7 | 10–11 |

磁场少女、系统上交国家、末日庇护所仍是备选，这批不启用。

## 这批不用

- 庶女明兰传（知否）、凡人修仙传：旧书和试拆七本重叠，第一批优先拿掉；第二批也不用。
- 庆余年：没有另拍换入，不自动补位。

权利空模板仍在 [golden-three-chapters/v0.2/](../../references/golden-three-chapters/v0.2/)，那是空模板，不是这些书的正文。

## 窗口和金标

- 两批状态都是：`WINDOWS_CANDIDATE_REGISTERED`
- 每一批登记 10 章，上限仍是 12；第二批不消耗第一批额度
- 本机分章文件看过文件名：**在**。这次评测用途：**未放行**。正文：**未读**
- 当前名称：人话卡金标候选｜未独立人工复核。施工只交候选，默认由 CZ 独立复核后再按版本签认
- 审过、尚未采纳：人话卡金标候选｜独立人工复核通过，待采纳
- 复核通过且具名采纳后：人话卡对照金标｜已独立人工复核并采纳。升格后也只是限定范围的评测参照，不是正式事实或十本账
- 只做人话结果卡的金标候选，不拆全书，不加章结构／钩子／爽点／修补建议

## 密度

作者看见的这一栏叫：**密度（仅说明本次已返回的候选）**。

现在继续写：**密度尚未提供：还没有可核对的候选信息分布说明。** 覆盖没接到 B02，就写尚未提供。不写百分数、分数、星级。

## 没做什么

- 不把小说正文放进写集
- 不调真实小说 API
- 不处理真章产品身份，不往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写

机读对照见同目录 `CATALOG.json`。
