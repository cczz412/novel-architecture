# 样本扩充 R01：六本前三章收件回执

已收到并独立核对六本新书原书完整前三章，共681条候选：161条单段可用候选、518条跨段暂缓、2条内容不支持。681条引文均在对应本机原章精确命中一次；段数标签、E-ID、章号、Markdown引文及四类计数一致。这里的“单段可用”仍是候选分类，不代表已完成全量语义审定或进入C4。

依据 [GitHub #324](https://github.com/cczz412/novel-architecture/issues/324)／[CCZ-178](https://linear.app/ccz/issue/CCZ-178) 的2026-09-08授权，工程基线 `main@45d0eb61a89cb843bbce6a2b1f0aa471c4e110c5`。全部取自本机新书池；没有重复已有登记书目，没有读第4章。新书池是备料身份，不证明模型训练未见。

## 书目和分母

| 书号 | 书名 | 题材／测试情况 | 总数 | 单段候选 | 跨段暂缓 | 内容不支持 |
|---|---|---|---:|---:|---:|---:|
| NB01 | 明末第一驿卒 | 历史／群像多势力与驿站权力 | 116 | 29 | 87 | 0 |
| NB02 | 全民地仙：开局紫金葫芦辟福地 | 体系／福地规则与物品选择 | 113 | 28 | 85 | 0 |
| NB03 | 公安局长之扫黑风暴 | 现代都市／刑侦与政商多方 | 91 | 28 | 62 | 1 |
| NB04 | 七罪副本：她靠怠惰封神 | 无限规则副本／群体博弈 | 127 | 25 | 102 | 0 |
| NB05 | 异常病理科 | 现代异常悬疑／判断与误信 | 103 | 22 | 80 | 1 |
| NB06 | 绝非赛博 | 赛博科幻／组织与身份权限 | 131 | 29 | 102 | 0 |
| 合计 | 6本／18章 | 含多势力、体系型和现代都市 | 681 | 161 | 518 | 2 |

逐书和总计满足：总数＝单段候选＋跨段暂缓＋内容不支持，后三类互斥。总数是本轮候选行数，不代表原文所有可抽事实数量，也不证明召回完整。书号＋E-ID共同唯一；各书逐章计数与回包来源摘要一致。

## 来源与原章哈希

来源池：`local/newbook_unseen_by_models/_newbook_rank_20260804/books/<书名>/chapters_cache/`。每本第1—3章分别对应原文件0001—0003，具体原文件名和网站来源在本地 `SELECTION_R01.json` 及回包 `BOOK_SOURCES.json`。18个文件共154095字节，外发拷贝保留原字节；收件时再次从原文件核验以下SHA-256。

| 书号 | 原书章号 | SHA-256 |
|---|---:|---|
| NB01 | 1 | `5ba330ddab195ab92e3e7149fb500b8ac4807b894f1cb47210777a8865cb9a1a` |
| NB01 | 2 | `50adbe5b6779e1f03ef2e103deb47a8edf3eec7cbb22a760eb6c37b46de61bc5` |
| NB01 | 3 | `2407c4cdddfef40ce2ec6894193469946ef5e10872d97010db779f59332ce898` |
| NB02 | 1 | `b428e3bea590c8dcfdec1dc1c943a2781da4d79ef194685b484d6375282a246a` |
| NB02 | 2 | `3265185a5d62abec5f52f49c4ca1ae63043610cd6c6724ed42b58cd6c923cb7c` |
| NB02 | 3 | `bcca23ee65ae8567f3e17ef512dff1a5396a416b2b81611149d357a53cbca9ba` |
| NB03 | 1 | `a1ba4fd686ef6d554d42d65e7e72902535872851f0e1b86d27a8f61791a0becd` |
| NB03 | 2 | `e60ac9c13d78f04b5f4ccb82d148ccfcd2cea2071446d49a50b7476c6d57c3ec` |
| NB03 | 3 | `6632f722ece6986fadd7f2e4bb733b221b0ef800dc00ae9a7ac1d7528f456a31` |
| NB04 | 1 | `7f7c5ceb8ee9dd39633f8ebb014bcc9d8b6e18a9081e1870456ade9a960ee861` |
| NB04 | 2 | `fdfa2a7e30eff0f9c6545a57991b3cc9d81bfcabe0b3b8ed5aed9b0aa094941b` |
| NB04 | 3 | `a9d3691948eeddf1d43f48ed3c4215d0a683cf0fde4603f12af62b88be497815` |
| NB05 | 1 | `bd670c6e8eadf740abef942268fcb7074f70a55837d6e77cd11287bb28d68a25` |
| NB05 | 2 | `474e34286e0655aeb3f5a7b3fd1f10059b404a874c60c348dc8ecefee6bfe091` |
| NB05 | 3 | `3336d9823f7f1a160195d7cbbc3a64f8ee2795bdb5990c256f90d7de1c5d5b0f` |
| NB06 | 1 | `2101be900acc09e4a400d905e858432c92a3ff3bd2a61063781e6660bf83efe6` |
| NB06 | 2 | `eb4d83e720cb12cb6a4d8cb53c74ad8a65d47fa050c58568d1bea5a8bb7251c0` |
| NB06 | 3 | `b449dc389cfc50a0e78b8bbf9fd0f03a50a67028702e81e88cbf6c56ab179d8d` |

## 交件、独立核查与保留项

精确 [Pro 对话](https://chatgpt.com/g/g-p-6a8d805c26e48191ace954cf0c1fb3c0-xiao-shuo-jia-gou-zhu-kong-wai-zhi-da-nao/c/6a9f3f3d-8074-83ea-aa48-236e97c4e27a) 只发送一次、最终ZIP只下载一次。最终文件为 `SAMPLE_EXPANSION_R01_RESULTS.zip`，339542字节，SHA-256 `552353490671ced4d4bdf861c3ab7b617c974886ca36e371fc45cac795e1cf4f`。安全解包通过，23份文件；六本各有独立Markdown、JSONL和来源摘要。

主窗口另写本地只读校验器，未执行回包脚本。681行字段、非空事实与类型、书章范围、联合编号唯一、逐字引文唯一命中、单段／跨段标签和Markdown引文一致性全部通过；18份原文件哈希和27项来源疑点引文均可回取。逐书分母与来源摘要精确一致。

可复跑命令（从本机小说架构v2容器根目录运行；只读取本批18章及回包，生成本地核验结果，不重新登记材料）：

```sh
python3 local/sample_expansion_r01/validate_local_return.py local/sample_expansion_r01/return_r01/unpacked > local/sample_expansion_r01/VALIDATION_STDOUT_R01.json
```

本次补充复跑退出码0。完整标准输出与 `LOCAL_VALIDATION_R01.json` 逐字节相同，顶层结果为 `total=681, errors=[], passed=true`；六本逐章数量见原输出。它只证明上文声明的机械核查范围。

| 本机证据 | SHA-256 |
|---|---|
| `local/sample_expansion_r01/validate_local_return.py`（Codex独立校验器） | `87930eb13c5e0101b7dcfe8ecc12a765989459a131e063a9a49794a9f0875584` |
| `local/sample_expansion_r01/VALIDATION_STDOUT_R01.json`（完整命令输出） | `1a877f04d8da7d4d4af20ef6349de9993d62c907dcc0440e9ed86a9cd93b8b21` |
| `local/sample_expansion_r01/LOCAL_VALIDATION_R01.json`（核验结果） | `1a877f04d8da7d4d4af20ef6349de9993d62c907dcc0440e9ed86a9cd93b8b21` |
| `local/sample_expansion_r01/QUOTE_ANCHORS_R01.jsonl`（681条精确定位） | `0da24bfc32bfd9f29d9365addf00c76fb72cd52fa764bc5cafd886741669263b` |

这些证据依赖本机材料存在；仓库只保存脱敏回执，不能仅靠clone复算正文核查。保留本批local目录及原包是后续复核前提。

两条内容不足项保留原编号和原候选：NB03 E-02-001 的代词指向未明确；NB05 E-02-017 为被动句补了施动者。没有删出分母或悄悄改成通过。27项来源疑点中含6处疑似评论／抓取残留，不能把“疑似”当已证来源身份；NB05 E-02-009连续引文中夹有一处疑似评论，原样保留以免拼接，该疑似评论行不作为事实支持，E-02-009仍归为跨段暂缓。

Pro报告的完整阅读和语义自查属于外部自报；主窗口本轮独立完成的是逐条引文、身份、段数和分母核查，并读取上述疑点及内容不足说明，未宣称681条已完成独立全量语义审定。来源矛盾、人物说法与事实的区分仍随候选保留。生成期间出现的625条是中间预览，不是本次登记版本；本回执只认最终ZIP中的681条。

## 本地登记与交付边界

原包、解包结果在 `local/sample_expansion_r01/return_r01/`；选书身份、独立逐条核查、精确引文坐标和登记回读在同目录上级的 `SELECTION_R01.json`、`LOCAL_VALIDATION_R01.json`、`QUOTE_ANCHORS_R01.jsonl`、`REGISTRY_RECEIPT_R01.json`。

本机 `local/fact_ledger_material_registry/BOOK_REGISTRY.jsonl` 新增6条 `ccz178-r01-nb01-ch01-03` 至 `ccz178-r01-nb06-ch01-03`；登记前16条、登记后22条，原有字节保留，六条新增逐项回读一致。每条包含来源文件／哈希、候选路径、四类分母、精确Chat URL、回包哈希与未入Gold／未正式入账身份。

仓内只有本回执。正文、引文、逐条候选、绑定和本地登记不入GitHub；本轮不调产品API、不建绑定、不投影、不确认事实。518条跨段和2条内容不足继续暂缓；其余为可供后续独立语义评测使用的候选。PR送审不合并，不用回包或机械核查替代产品验收。

归位条件：本回执当前按#324批准写集暂存work。CCZ-178验收完成且后续明确批准报告归位时，目标为 `reports/sample_expansion_r01/RECEIPT_R01.md`，迁移时保留本PR固定版本回链；在该条件满足前保留本文件，不把work当长期正式样本库，也不自行移动、删除或复制正文。候选材料的正式采用仍另行验收。

来源：Codex
