# 人话卡对照书目登记

GitHub 施工入口：[Issue #281](https://github.com/cczz412/novel-architecture/issues/281)（第一批）、[Issue #284](https://github.com/cczz412/novel-architecture/issues/284)（第二批新书）。模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)。

✅ 对照可以有两批。第一批仍是 **全职高手、道诡异仙、十日终焉**。第二批用试拆已锁的新书：**炼气士不死于无限、我在美恐科普都市传说、请勿高考时渡劫**。两批都还没选具体章节，更没有金标正文。

你可以直接理解成：老书目一批、未见过的新书再一批。知否／凡人仍不用。不自动换入庆余年。第二批不抢第一批那 8–10／上限 12 章。

## 第一批：优先三本

| 书 | 仓内书目指针 | 这批用不用 |
|---|---|---|
| 全职高手 | [corpus-pointers.md](../../references/corpus-pointers.md)、[book-meta INDEX](../../references/book-meta/INDEX.md) | 用 |
| 道诡异仙 | [corpus-pointers.md](../../references/corpus-pointers.md)、[book-meta INDEX](../../references/book-meta/INDEX.md) | 用 |
| 十日终焉 | [corpus-pointers.md](../../references/corpus-pointers.md)（[book-meta INDEX](../../references/book-meta/INDEX.md) 目前没有这一行） | 用，但选窗前要核本地材料 |

试拆七本书单写过：十日终焉仍只有因果大纲，不当事实句。CZ 仍拍了它进第一批优先。选窗时先看本地到底有没有可对照章节，没有就停，不要硬编窗口。

## 第二批：新书三本

这三本在试拆七本里，但和拿掉知否／凡人不是同一回事。那两本是旧书撞车；这三本是故意留的「模型没读过」对照。

仓内 [corpus-pointers.md](../../references/corpus-pointers.md)／[book-meta INDEX](../../references/book-meta/INDEX.md) 目前没有这三行。本包只登记书名和打算用的软链路径，不把正文拷进 Git。

| 书 | 打算用的路径 | 试拆序号 |
|---|---|---|
| 炼气士不死于无限 | `corpus-downloads/_newbook_rank_20260804/books/炼气士不死于无限/` | 5 |
| 我在美恐科普都市传说 | `corpus-downloads/_newbook_rank_20260804/books/我在美恐科普都市传说/` | 6 |
| 请勿高考时渡劫 | `corpus-downloads/_newbook_rank_20260804/books/请勿高考时渡劫/` | 7 |

磁场少女、系统上交国家、末日庇护所仍是备选，这批不启用。

## 这批不用

- 庶女明兰传（知否）、凡人修仙传：旧书和试拆七本重叠，第一批优先拿掉；第二批也不用。
- 庆余年：没有另拍换入，不自动补位。

权利空模板仍在 [golden-three-chapters/v0.2/](../../references/golden-three-chapters/v0.2/)，那是空模板，不是这些书的正文。

## 窗口和金标

- 两批状态都是：`BOOKS_SELECTED_WINDOWS_NOT_YET`
- 每一批各自上限 12 章、常态 8–10 章；第二批不消耗第一批额度
- 只做人话结果卡的金标候选，不拆全书，不加章结构／钩子／爽点／修补建议
- 本机有没有正文：**未核**。本包不读、不提交、不外发小说正文

## 没做什么

- 不把小说正文放进写集
- 不调真实小说 API
- 不处理真章产品身份，不往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写

机读对照见同目录 `CATALOG.json`。
