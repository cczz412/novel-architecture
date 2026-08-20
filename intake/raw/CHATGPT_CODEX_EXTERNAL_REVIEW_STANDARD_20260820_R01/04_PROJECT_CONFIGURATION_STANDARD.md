# Project 配置标准

## 1. 一个 Project 管一个长期领域

推荐拆分：

```text
Project A：小说产品架构
Project B：某一本真实小说
Project C：模型/评测实验
Project D：市场与外部调查
```

不要把完全不同的工程塞进同一个 Project，只靠聊天标题区分。

## 2. Memory 默认值

长期外审 Project 默认：`Project-only memory`。

适用原因：

- 防止账号其他普通聊天、其他 Project 和生活话题进入工程回答；
- 项目内容不会被项目外聊天作为记忆上下文使用；
- 同一 Project 的聊天仍可作为软连续性。

注意：

- Project-only 不是独立账号；
- Library、Web、Apps、模型权限和账号数据控制仍存在；
- 官方说明现有 Project 可切换 memory，但变更可能需要几小时生效；严格实验或高敏任务应新建干净 Project，或等待后再验证。

## 3. Project Instructions 推荐模板

见 `14_TEMPLATES/PROJECT_INSTRUCTIONS_TEMPLATE.md`。最低必须表达：

1. 当前本地真源高于 Project memory；
2. Current / Manifest / Result 文件高于聊天回忆；
3. 默认只使用 Project Sources 和当前附件；
4. 未授权不使用 Web、Library、Apps 或项目外上下文；
5. 不把背景板当施工权；
6. 不猜缺失 ID；
7. 详细结果进 ZIP。

## 4. Project Source 文件预算

官方 Pro Project 当前列 40 files/project。本规格推荐：

- 目标常驻 ≤ 30；
- 至少留 10 个空槽给临时 current、迁移和新版本验证；
- 语义核心 5～15 个文件；
- 资产 ZIP 1～5 个；
- 不把 40 个槽全部占满。

## 5. Source 更新

推荐版本化文件名：

```text
00_PROJECT_ROUTER_R07.md
01_CURRENT_20260820_R03.json
PRODUCT_CONTEXT_R13.md
ATOMIC_EXPECTATIONS_R02.json
CODEBASE_20260820_R41.zip
REPORT_ARCHIVE_20260815_R01.zip
```

更新流程：

1. 本地构建新版本并计算 SHA；
2. 上传新文件，不覆盖旧文件名；
3. 开干净 Project Chat 验证语义与 raw mount；
4. 更新 Router 的 current 指针；
5. 下载/保存验证回执；
6. 再删除旧 Source 或标 archived。

## 6. Save to Project 的使用

聊天产出重要的 decision note / current handoff / summary 时，可以保存为 Project Source。但保存前必须：

- 去掉临时猜测；
- 标记版本和来源；
- 写清它是背景、候选还是 current；
- 不把聊天总结冒充正式结果票。

## 7. Connected Apps / Web

Project-only 不禁止 Apps 或 Web。严格外审 Prompt 必须显式禁止；需要外部刷新时另开“外部研究任务”，并把来源和日期写进结果。

## 8. Library

Library 的定位：账号级人工文件仓库。

- 可以人工 Add from Library；
- 不会因为在 Library 中就自动成为 Project Source；
- 本次 assistant-side 自动寻找前轮 result ZIP 没有成功；
- 所以 RESULT.zip 必须当场下载，本地保存，Library 只作额外便利。
