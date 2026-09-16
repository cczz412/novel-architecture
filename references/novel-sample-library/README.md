# 小说样本目录

云端 Agent 在这里选书和用途，本地 Agent 按编号取样。**仓库只放目录；书稿、抽取句、引文、预期答案和测试对照内容都留本地。**

[按题材与梯队选书](BOOKS.md) · [按能力选用例](CAPABILITIES.md) · [机器目录](catalog.json)

## 先怎么用

1. 到能力页选择本次要测的用途，再挑不同题材的用例。起步可用标出的基础六例。
2. 记下 `catalog.json` 的 `catalog_revision` 和所选 `case_id`，交给本地 Agent。需要题材覆盖时，把选择理由一起交回。
3. 本地核对同一目录版本、原文件与局部修订版本，再按独立获准的 API 任务做对照。原始回包和旧成绩保留。

云端没有样本文件是正常边界，不是仓库损坏。不得凭熟悉小说补内容，或把目录里未列出的能力当作作品没有。

## 三档是什么意思

|档位|可怎么用|不能据此推出什么|
|---|---|---|
|A 优先用|只取已经点名、具有局部核对记录的用例|整本、全部字段、整种题材已审完；答案是人工Gold|
|B 补充用|材料已收，先核一个具体例子再用于对照|仅因文件齐全就能当标准答案|
|C 待准备|先补来源或等待抽取；此时可用于选材安排|样本已可用、书目即测试通过|

本次快照含106本书目：46本原登记、60本追加选材候选；38本已收样本。57组具体用例分布于34本A档书，4本为B档，其余68本为C档。数量与快照时间均可从机器目录重算。书目不是完整小说内容，也不是全部通过语义审查的书数。

13类标签描述用例用途，不给产品增设题材必填字段。历史榜单和新书池只表示选材来源；今日榜位、模型训练未见均未验证。未收书目也没有继承旧加工结果的核准身份。

## 云端怎么查

下面命令只读仓内目录，不访问网络或本地样本：

```bash
# 查基础六例的编号、所属书、章材料、能力标签
jq '.cases[] | select(.starter) | {case_id,book_id,chapter_materials,capability_tags}' references/novel-sample-library/catalog.json

# 查“人物知情”用例；再用 book_id 对照 books 中的题材
jq '.cases[] | select(.capability_tags | index("KNOW"))' references/novel-sample-library/catalog.json

# 查科幻题材且有优先用例的书
jq '.books[] | select(.genre_family=="科幻" and .tier=="A") | {book_id,title,case_ids}' references/novel-sample-library/catalog.json
```

交回本地的选样单可以从当前目录生成：

```bash
jq '{catalog_id,catalog_revision,case_ids:[.cases[] | select(.starter) | .case_id]}' references/novel-sample-library/catalog.json > sample_selection.json
```

这是一张取样请求，不是产品接口或 API 运行授权。未携带目录版本、编号不属于该版、原件缺失或内容变动时，本地应说明差异，不静默换成最新版、旧版或其他小说。

## 本地如何承接

本机材料根目录由执行者配置，不提交机器绝对路径。对应的本地库名是 `novel_extraction_library_r01`，库内 `cloud_catalog_r01/resolve_local.py` 接收上述选样单和本地输出路径。它只解析编号、核对文件内容并给出路径，不调用模型，不评价产品效果。

目录版本 `catalog_revision` 是本目录数据的摘要；它不是结构合同的受信版本或书稿事实顺序。绑定表按目录版本保存在本地，实际样本各自保留文件摘要。不要拿目录摘要、样本摘要和产品对象摘要互相替代。

未来规划、工作卡许可、版本保存与读取、改动传播和创作体验需要额外任务输入，见能力页的待补表。已写小说不能提供作者尚未写出的安排，也不能证明程序入口已接通。

## 谁维护、怎样更新

编制源是本地库的样本总表、局部核对选例和来源登记。本地导出器 `cloud_catalog_r01/export_catalog.py` 只挑允许入仓的字段，生成 `catalog.json`、`BOOKS.md`、`CAPABILITIES.md`，另存本地绑定。书目、用例或资格变化时从编制源更新，再通过同一仓库正常审阅流程发布目录新版本；不要手改派生表制造第二份当前清单。

本目录不记录实时 Pro 进度或任务分配。云端选样只认所读 Git 提交和目录版本；实时任务状态仍回原活动任务。仅本地可访问的选择器 HTML 含内容，不得代替本目录上传。

准许入仓的是：书名、题材、梯队、材料范围、能力标签、用例编号、数量、快照和使用边界。不得入仓的是：书稿、抽取句、引文、具体预期答案、逐条评审、原回包、私有聊天地址和机器绝对路径。

来源：Codex。依据：CZ 2026-09-15 授权“库进Git、样本内容留本地”，见[本次目录交付 #368](https://github.com/cczz412/novel-architecture/issues/368)。本目录是选样参考，不改产品合同、评测评分或样本核准身份。
