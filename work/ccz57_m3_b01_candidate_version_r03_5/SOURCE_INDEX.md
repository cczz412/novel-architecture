# B-01 r03.5 来源与输出索引

## 工程准入

| 依据 | 精确身份 | 在这里证明什么 |
| --- | --- | --- |
| A 阶段 PR #186 | reviewed/merge head `9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26` | A 机械外壳的精确受审版本 |
| A merge commit | `019df751641533c7de4d56aa38f50747fb564036` | GLOBAL-A 已成立，且后续 main 必须仍可达 |
| A 准入原件 | ID `a_admission_pr186_019df751_20260828`；record hash `91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af` | B 阶段使用的准入原件 |
| 旧 B-01 merge | `905346f56cd51259c15a9517ead1517227c1719a` | r03.3 历史对象的来源；只读保留 |
| 开工时 current main | `189fb4a28a036aa5126baf32950f0fef2b359fa5` | Issue #195 分支的精确起点 |

## 产品语义与施工范围

| 依据 | SHA-256 | 用途 |
| --- | --- | --- |
| B-01 r03.5 合同候选 | `34c695b81d1e06730eba71d75fa8176c98ca086c3aea6c29c289c4bde07b4772` | 新旧兼容、输入绑定、对象、writer 和验收范围 |
| CZ 语义决定回执 | `54dcd1e6bb6ddd7b3d166c568995f6d78bb544f213044e316f6ef1d24c660058` | 固定“按事实条目找证据，不按任意字符范围读取正文” |
| GitHub Issue #195 | `施工｜CCZ-57 M3 B-01 r03.5 v2.1 候选版本与证据定位兼容修复` | 已合并的 r03.5 基线来源 |
| Linear CCZ-144 | `修复｜CCZ-57 M3 B-01 r03.5 v2.1 候选版本输入绑定与证据定位` | 已完成的基线需求及本票关联对象 |
| GitHub Issue #203 | `施工｜CCZ-57 M3 B-01 正文抽取来源准入与 raw_items 封装` | 本次来源准入窄修、唯一写集和 GitHub 停点 |
| Linear CCZ-148 | `修复｜CCZ-57 M3 B-01 正文抽取来源准入与 raw_items 封装` | CCZ-142 与 B-01 的来源交接归属 |
| GitHub Issue #212 | `修复｜CCZ-57 M3 B-01 真实输入减法：来源代次映射与可选写作上下文` | 本次独立写集、分支、测试和 PR 入口 |
| Linear CCZ-151 | 同名修复票 | 正式采用“章节修订＋来源代次必需，写作上下文可选” |

## 正文抽取来源准入

| 临时交接字段 | 固定要求 | 是否持久化 |
| --- | --- | --- |
| 来源路线 | `CCZ142_TEXT_EXTRACTION_CANDIDATES` | 否 |
| 来源模块 | `CCZ-142` | 否 |
| 交接合同 | `CCZ142_B01_EXTRACTION_HANDOFF_V1_CANDIDATE` | 否 |
| 请求绑定 | 工作区、章节修订、来源代次、写作资料、责任段、尝试引用和候选条目逐项一致 | 否 |
| 准入凭证 | 仅绑定的 `B01Service` 实例可以打开；签发能力只交给组装层另一侧的 CCZ-142 适配端，不挂在服务公开面上 | 否 |

画布计划事实、章节内核、旧 C3 预览和通用 JSON 都不是这条路线的合法来源。公开 root baseline 入口没有名为 `raw_items` 的参数，也没有来源凭证签发方法；直接传入会在任何状态发布前失败。

## 合成输入接口

| 记录 | 用途 | writer 边界 |
| --- | --- | --- |
| `M1_ACCEPTED_SOURCE_GENERATION` | 绑定作者工作区来源代次、章节接纳身份和精确章节版本 | B-01 只读适配，不创建真实 M1 记录 |
| `M1_WRITING_MATERIAL` | 绑定同代资料的角色、合同、版本和内容 SHA | B-01 只读适配，不创建真实 M1 记录 |
| `A_RAW_ATTEMPT_RECEIPT` 等 A 记录 | 保留机械尝试和准入来源 | 继续使用旧合同身份，不由 B-01 改写 |

写作资料现在是可选上下文，允许整组为空。可用类型是题材、核心人物、平台、简介和规划；提供后仍要满足同代、唯一类型和规范排序。

## AuthorWorkspace 只读来源代次

| 读取项 | 用途 |
| --- | --- |
| `chapter_index` | 锁定 current 章节修订 |
| `chapter_revisions` | 验 C11 修订序列和 current 指针 |
| `chapter_materials` | 验 current 修订仍绑定可用的 C10 章节材料身份 |
| `chapter_admission_operations` | 验初始接纳操作与首版修订一致 |

适配器连续读取两遍并比较完整水位。`chapters`、`chapter_sources`、`draft` 不在读取范围，因为它们会带入正文或工作稿。输出只是一份内存来源代次记录，产品写入、模型调用和正文读取都是 0。

## 文件分别负责什么

| 文件 | 用途 |
| --- | --- |
| `b01_contract.py` | 不可变外壳、输入绑定、UTF-8 byte 段索引、三种持久 writer、两个 Locator、版本差异和原子 fixture store |
| `OBJECT_SHAPES.json` | 参考输入、三份完整不可变对象、新旧候选、Locator、pointer、VersionDiff 和 writer 的机器样例 |
| `fixtures.py` | 13 个正常夹具族和 33 个失败夹具族，只含合成内容；每个失败夹具都带 0 写入尝试探针 |
| `product_source_adapter.py` | 把四项 AuthorWorkspace 元数据映射成 B-01 来源代次；不读正文、不写产品状态 |
| `test_b01_contract.py` | 定向测试、幂等、旧版只读、失败前 0 写入和重启回放断言 |
| `self_check.py` | 离线重放、引用与哈希检查、固定向量、writer 静态检查、运行期 audit hook 和报告生成 |
| `OFFLINE_REPLAY_REPORT.json` | 当前机械复验结果，不承载语义验收 |
| `README.md` | 人能读懂的范围、对象和复验说明 |
| `DESIGN_CONFLICTS_AND_LIMITS.md` | 产品语义冲突、兼容策略和后续能力边界 |
| `MANIFEST.sha256` | 除自身外 10 个交付文件的完整性清单 |

唯一允许写集是：

```text
work/ccz57_m3_b01_candidate_version_r03_5/**
```

旧 r03.4 目录、B-02、B-03、B-04 和 `local/` 都不在本票写集。

来源：Codex
