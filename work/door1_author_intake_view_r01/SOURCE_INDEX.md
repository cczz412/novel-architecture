# 门 1 第一刀｜来源与判断边界

本包的产品画面以本轮 Prompt、施工授权与拍板人口述为依据。外部资料只用于核对浏览器文件权限，不拿它改产品范围。

## 按指定顺序读取的材料

这些文件位于输入 ZIP 的 `01_current_truth/TEMP/chatgpt_review_cycles/door1_author_intake_view_20260906_r01/`。

| 文件 | 本包采用了什么 |
|---|---|
| `AUTHORITY_AND_SCOPE.md` | #309 的写集、只读边界、夹具范围、正常路径与两条失败路径 |
| `CZ_DICTATION_RAW.md` | 原文／候选双向悬停；默认摆出候选后打标记；“＋”连虚线、“重新抽”保留关系；主键、标签、标签组；18:13 明确不用叉或减号 |
| `PRODUCT_PICTURE_DOOR1.md` | 只做第一刀静态画面；分镜占位；动画、多章并列与飞回家不接 |
| `LEDGER_DIRECTORY_DESIGN_R01.md` | 10 本账的原名、顺序与用途；计划不等于已发生；每条只放一个候选展示组 |
| `REPO_CONVENTIONS.md` | work 包文件纪律、CLI、只读库、独立边车、实际测试回执与哈希 |

其他包内卡片只作背景，不替代本轮 Prompt。旧目录里“已确认事实才进正式事实账”，与这次“默认摆出候选＋打标记”并不自动等义：本页明确只显示候选归类，没有登记正式事实。本刀不新增逐条确认，也不把标记改成认可。

## 在线核对

2026-09-06 通过 GitHub 连接只读打开 #309 与 main 分支信息。#309 的范围、写集、禁区和三条验收与包内授权一致；读取当时状态为 OPEN。main 返回：

`908fbbfef6fa3a6b1d92e9a3fc35b1c35570ef66`

地址用于复核，不是已经创建的回件 PR：

- `https://github.com/cczz412/novel-architecture/issues/309`
- `https://github.com/cczz412/novel-architecture/tree/908fbbfef6fa3a6b1d92e9a3fc35b1c35570ef66`
- Linear 只沿用宿主引用 `https://linear.app/ccz/issue/CCZ-142`，本次未打开或修改 Linear。

本次没有线上写操作，没有改票、创建分支、提交或合并。没有读 Slack、Notion 或真实小说。

因切片缺依赖，还读取了该基线下 B06 目录元数据及 `b06_store.py` 的开头 105 行，确认它继续依赖 B05。这不等于拿到了 B05～B08 的完整源码，也不等于已经补齐运行环境。交回 ZIP 不附这些旧文件。

## 代码怎么复用

| 仓库文件／函数 | 用途 | 是否运行时调用 |
|---|---|---|
| `work/ccz142_named_chapter_txt_card_r01/named_chapter.py`：`drop_named_chapter` | 理解既有“丢一章”入口，以及它负责调用旧 writer | 新页面不调用；完整库集成测试的准备步骤调用 |
| 同目录 `ALLOWLIST.json` | 检查只放行北塔夹具第 1 章、固定路径与两种正文指纹 | 是，只读固定条目 |
| `work/ccz142_human_card_vertical_wire_r01/vertical_wire.py`：`wire_synthetic_chapter_to_card`、`FROZEN_HANDOFF_ITEMS` | 理解夹具候选如何进旧库；投影单测从冻结常量取五条 | 新页面不调用写入；单测只用 AST 读冻结常量 |
| 同目录 `synthetic_chapter.txt` | 唯一允许读取的正文 | 是，先核文件指纹 |
| `work/ccz142_current_candidate_read_preview_r01/html_render.py`：`show_current_html` | 参考现有单文件 HTML、身份与缺口展示 | 否；新四栏由 `view_render.render_page` 画，不改旧样张 |
| `work/ccz142_current_candidate_read_display_r01/card_render.py`：`render_markdown`、`render_scope_section` | 沿用事实、状态、证据与未知范围的显示含义 | 否；不从 Markdown 反解析候选 |
| `work/ccz142_current_candidate_read_proof_r01/current_read_proof.py`：`prove_current_read` | 新页面唯一的候选读取入口 | 是；只调用这条现有读路 |
| 同文件 `project_human_card`、`project_item_source`、`format_source_locations` | 提供 fact、status、evidence、kind、speaker、stable_item_id、match_locations、source_location | 经原读路调用；新页不重写这些上游函数 |
| 同文件 `project_result_scope`、`apply_named_card_identity` | 检查项目、章号、修订指纹、责任段；兼容旧命名边车把章号写成 `1` | 经原读路调用；新页只核对结果 |
| `work/ccz142_candidate_authority_r01/candidate_authority.py`：`CandidateAuthorityStore` | 原有候选库；继承的 `read_pointer`、`read_candidate` 读 current | 经 `prove_current_read` 使用；没有第二套库 |
| `work/ccz57_m3_b01_candidate_version_r03_5/fixtures.py`：`chapter_revision_ref`、`segment_inputs` | 同一章修订与责任段的全章字节位置 | 是，只读夹具构造值 |
| `pyproject.toml` | Python 3.12.12、pytest 9.0.2 与仓库工具约定 | 读取，不修改 |

旧 `project_human_card` 会略过本来就缺事实／状态／证据的原始坏条目。新页面没有拿到那些被上游略过的原始记录，不能宣称本页显示了库内每一种坏形状。这里完整展示的是该现有读路返回的候选集合；本页收到的合法条目若缺来源位置，则局部提示而不消失。没有因此另开原始库读取路线。

## 夹具字节口径

固定正文去掉文件尾换行后是 4 句。第 1、3 句内容相同，第 2 句证据不同，第 4 句在旧冻结五条候选中没有对应。

| 范围 | 全章 UTF-8 半开区间 |
|---|---|
| 责任段 1 | `[0, 57)` |
| 责任段 2 | `[57, 75)` |
| 原文第 1 句 | `[0, 18)` |
| 原文第 2 句 | `[18, 39)` |
| 原文第 3 句 | `[39, 57)` |
| 原文第 4 句 | `[57, 75)` |

候选位置是责任段内的区间；页面加责任段起点后才去碰原文句。相同文字不增加新的来源关系。

文件指纹含尾换行：
`e217cbdba708352584c26ef1404e99e24075da88d07b32624fecc7c436c3ffa4`

章正文指纹不含尾换行：
`9209f22416dfff31d931f9f8f02ce12f4b99ff735754afbb1a4abcaa4899910b`

`OBJECT_SHAPES.json` 还保存了切片重建后 71 个已有仓库文件的指纹。它们用于核对本次没有动旧文件，不是从在线完整仓库重新生成的 71 份核验结论。

## 本刀自己的判断

1. 按已给出的状态做保守分账；计划／承诺进长线候选，其余进事实候选且保留原状态。没有实体 ID，不靠关键词猜七种专门账。
2. 标签组只用有依据的“只读”；不把示例里的“不可回退”等组名一股脑贴到每条候选。
3. 句末标点与换行切句；现有字节区间加严格证据核对负责连线，不用模糊文本匹配。
4. `view_id` 随正文、范围、指针和投影变化。异版本边车不自动迁移，更不会清空后假装兼容。
5. 本页新增空候选只是标记的显示结果，没有新 writer，也没有伪造的事实正文或正式账条。
6. 纯离线 HTML 的磁盘权限需要用户一次明确授权；故加了顶部目录连接控制。它不是删除／确认操作，也不接服务。
7. 同一原文可以对应多个位置或多个候选；对方在屏幕外时只滚动对方栏到第一处，保留全部高亮，不做动画。

以上是本次施工选择，不冒充 CZ 对字段算法逐条拍过板。

## 浏览器文件权限的外部依据

只核对了 WICG 的 File System Access 草案，2026-09-06 读取：

`https://wicg.github.io/file-system-access/`

对应章节是 Introduction、Permissions、`queryPermission`、`requestPermission` 和 `showDirectoryPicker`。它支持两条判断：文件系统访问要经过用户授权；保存过句柄不保证重开后仍有权限，可能需要重新请求。

这里没有引用浏览器支持率来承诺“任何浏览器都行”。实际代码检查接口，失败时留明确提示。规范描述不能代替本机原生授权验收；本次受控浏览器只测了页面交互和文件接口接线，详情在测试回执。

来源：ChatGPT
