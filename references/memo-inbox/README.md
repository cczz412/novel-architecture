# memo-inbox｜便签收件箱

这里长期保存 CZ 随手记下的产品想法、技术备选、观察和提醒。它主要解决两个问题：换电脑或换 Agent 后仍能找到旧便签；准备做一件事时，能先发现以前写过的相近、重复或互相冲突的想法。

🔥 便签永远不是施工票。登记表中的 `construction_authority` 固定为 `NONE`；即使 CZ 已接受某个方向，也要由当前任务 Issue 或 CZ 的明确指令另行授权写集。

## 和外部调查收件箱怎么分

| 入口 | 放什么 | 编号 |
|---|---|---|
| 本夹 | CZ 口述便签、内部观察、暂存技术选择题 | `MN-*` |
| [survey-inbox](../survey-inbox/README.md) | GitHub、文章、视频和 Deep Research 等外部调查材料 | `SI-*` |

两个入口不各玩各的。本夹的机器登记表会声明外部目录 `references/survey-inbox/catalog.csv`，关系可以直接指向 `SI-*`。准备做决定时，要一起查相关 `MN-*` 和 `SI-*`，但只查当前主题和模块，不把两个箱子全部读一遍。

## 一条便签怎么流转

```text
CZ 丢进一条便签
    ↓
分配稳定 MN 编号，正文进 Git
    ↓
在 registry.json 登记主题、模块、选择题和当前身份
    ↓
按相关标签与选择题找旧材料，登记关系候选
    ↓
没有行动需求：继续留在便签箱
需要裁决：开 Issue 交 CZ
CZ 决定且另有施工授权：任务 PR 才能动代码或正式产品文档
```

旧便签不因新便签出现而删除。只有 CZ 已作决定，并留下 `decision_ref`，才能把旧便签标成 `SUPERSEDED` 并填写 `superseded_by`。

## 三个身份分开看

每条便签都要分开登记：

- 材料情况 `material_state`：`UNVERIFIED`、`PARTIALLY_VERIFIED`、`VERIFIED`、`POSSIBLY_STALE`；
- 决策情况 `decision_state`：`UNDECIDED`、`NEEDS_CZ`、`ACCEPTED`、`REJECTED`、`SUPERSEDED`；
- 施工权限 `construction_authority`：只能是 `NONE`。

材料已经核验，不等于 CZ 已选择；CZ 已接受一个方向，也不等于这次任务获准施工。

## 关系怎么记

机器登记表只允许五种关系：

| 关系 | 人话 |
|---|---|
| `OVERLAPS` | 有交集，适合一起读 |
| `DUPLICATES` | 可能在说同一件事 |
| `CONFLICTS_WITH` | 不能直接同时指导同一个选择 |
| `CONSOLIDATES` | 新便签汇总了旧材料，但不会自动让旧件失效 |
| `NOT_RELATED` | 人工确认只是误报或无需联读 |

`review_status=AGENT_CANDIDATE` 只表示 Agent 提醒 CZ 看一眼。只有 `CZ_CONFIRMED` 才是已确认关系；`DISMISSED` 表示候选已排除。

准备采用某条便签时，如果相关小簇里存在 `resolution_status=OPEN` 的 `DUPLICATES` 或 `CONFLICTS_WITH`，就停下对应写集交 CZ。已经 `SUPERSEDED` 的便签也不能继续作为当前依据。其他模块不受牵连。

关系状态不能随意拼：未排除的 `DUPLICATES`／`CONFLICTS_WITH` 只能保持 `OPEN`，或由 CZ 留下 `decision_ref` 后进入 `RESOLVED`；`DISMISSED` 必须搭配 `NOT_APPLICABLE`；任何 `RESOLVED` 都必须由 `CZ_CONFIRMED` 和决定依据支撑。

## 怎样查，避免每次全读

1. 从当前任务提取它在回答的选择题、主题和模块；
2. 在 [registry.json](registry.json) 中按 `decision_keys`、`topic_tags`、`area_tags` 找候选；
3. 只沿命中条目的关系读取这一小簇正文；
4. 再按 `external_catalog` 查询相关 `SI-*`；
5. 发现未裁决重复、冲突或已被替代的依据，再停对应写集交 CZ。

`decision_keys` 表示“这条便签在回答哪个选择题”。两条便签用词不同，只要在争同一个决定，也应该放到一起比较。

新便签落盘后运行这条定向检查：

```bash
uv run --locked pytest -q -p no:cacheprovider \
  tests/test_repository_navigation.py -k memo_inbox
```

检查会核对编号、正文 SHA、外部关系目标、替代环和施工权限；同一个选择题或高相似便签若还没有登记关系，会列出两边编号并失败。Agent 要先联读并登记 `OVERLAPS`、`DUPLICATES`、`CONFLICTS_WITH`、`CONSOLIDATES` 或 `NOT_RELATED`，不能为了追绿随便填一种关系。

## 自动提示只能做到哪一步

当前候选发现口径是 `memo-overlap-hint-v1`：

- `产品架构`、`作者工作台`、`技术`、`候选`属于宽标签，不能单独触发相似；
- 至少共享 2 个更具体的标签，才进入文字相似比较；
- 文字 Jaccard 阈值是 0.2；
- 规则最多输出 `EXACT_DUPLICATE_CANDIDATE`、`POSSIBLE_OVERLAP` 或 `SAME_DECISION_REVIEW`。

它不能自动断言两条便签重复、冲突或谁替代谁，也不能替 CZ 作产品决定。没有提示也不证明不存在冲突。

## 文件入口

| 用途 | 文件 |
|---|---|
| 人读总览 | [INDEX.md](INDEX.md) |
| 唯一机器清单 | [registry.json](registry.json) |
| 单条正文 | [items/](items/) |
| 新便签模板 | [_template/ITEM.md](_template/ITEM.md) |

这里不再维护 CSV 副本，避免两个机器清单内容漂移。

来源：Codex
