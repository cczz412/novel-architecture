# C1 · 章节文档（CHAPTER_DOC）

**版本：v1**（正式增加 stable chapter revision 引用；v0-r01 保留为迁移前旧读法）

读法：v1 只表示章节书稿，是 [C11_CHAPTER_REVISION_LEDGER.md](C11_CHAPTER_REVISION_LEDGER.md) current revision 的物化视图。`chapters.json` 不保存第二份 revision history；大纲继续留在材料架／规划侧。现役产品仍输出 v0-r01，必须经过正式迁移后才可声称写出 v1。

一句话用途：给 M2 与 current chapter 消费者提供某个 stable chapter 的当前标题和逐字正文。

| 方向 | 模块 |
|---|---|
| 发 | 首次合法 M1 接收或章节 revision commit 协调器；写作区工作稿只在作者显式 handover 后进入接收边界 |
| 收 | M4 事实账（落盘 `data/<项目>/chapters.json`）；M2 切窗器（只吃 `text`）；M0 展示（status） |

## 字段表

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C1_CHAPTER_DOC` | 是 |
| version | str | 固定 `v1` | 是 |
| id | str | stable chapter id，`c01` 格式；正文修订时保持不变 | 是 |
| title | str | 章节标题（导入时指定，默认取文件名） | 是 |
| kind | str | 固定 `draft`；Outline 不进入 v1 C1 | 是 |
| text | str | 原文全文，原样保存、未清洗 | 是 |
| added_at | str | 导入时间，`YYYY-MM-DD HH:MM:SS` 本地时间 | 是 |
| chapter_revision_ref | obj | `{chapter_id, revision_no, revision_text_sha256}`；必须等于 C11 current revision | 是 |

章节顺序仍由 `chapters.json` 数组顺序表达。修订只替换同一 id 的 current 视图，不新增第二条 current chapter，也不改变数组位置。

## v1 形状示例

```json
{
  "contract": "C1_CHAPTER_DOC",
  "version": "v1",
  "id": "c01",
  "title": "第一章 雨夜",
  "kind": "draft",
  "text": "沈砚放下铜钥匙。",
  "added_at": "2026-08-18 04:30:00",
  "chapter_revision_ref": {
    "chapter_id": "c01",
    "revision_no": 2,
    "revision_text_sha256": "0aeb78621f82e724f19a56e01f2dc9bfcdec630b1748e2fb2c78edb0b0e47cfc"
  }
}
```

## v0-r01 真实示例（legacy）

取自 `data/万鬼伏藏/chapters.json` 第 1 条（`text` 截断展示，实际 3928 字）：

```json
{
  "id": "c01",
  "title": "第1章 李星燃",
  "kind": "draft",
  "text": "“你叫李星燃对吧，说说看吧，你都有什么症状。”\n　　市医院精神科的陈医生，四十岁出头，戴着眼镜，穿着干净整洁的白大褂，脸…",
  "added_at": "2026-08-13 00:53:41"
}
```

## 附：导入损失报告（M1 返回值，v0 最小版，不落盘）

`ingest.ingest_files(...)` 每批导入返回一份：

| 字段 | 类型 | 含义 |
|---|---|---|
| count | int | 本次导入章数 |
| total_chars | int | 本次导入总字数 |
| warnings | list[str] | 空章警告（正文全空白时一条） |
| chapters | list | 本次导入的 C1 章节文档 |

## 写作区工作稿的接收边界（v0-r01）

[WRITING_DESK_WORK_DRAFT.md](WRITING_DESK_WORK_DRAFT.md) 中的工作稿不是 C1。自动保存、修改、检测、收工或文件存在，都不能创建章节书稿。

只有作者显式发出 [WORK_DRAFT_HANDOVER_ACTION.md](WORK_DRAFT_HANDOVER_ACTION.md)，且动作仍指向 current work revision 时，C1 接收端才可以：

1. 用 `work_ref + work_rev` 从写作区工作稿 owner 取得作者原文；
2. 复核动作中的 `slot_ref`、`source_outline_ref` 与 current 工作稿一致；
3. 只接受 `WORK_DRAFT_HANDOVER_ACTION v2` 中作者明确确认的 `chapter_title`，不用文件名或 `slot.title_hint` 猜标题；
4. 首次入库经 C11 建 r1，标题从此由 C11 current revision 长期持有，再生成带 `chapter_revision_ref` 的 C1 v1 current view；
5. 原文逐字进入 `text`，不得由接收端润色、补写或改标点；
6. 成功返回合法 C1 `chapter_id` 与 current revision ref，供后续 planstore 交棒使用。

动作处于 `AWAITING_C1_ACCEPTANCE`、C1 校验失败或章节身份尚未产生时，planstore 不得先写 `handover_parts`。这段只增加接收顺序，不给 C1 增加 planstore、facts、actual、对账或关章权力，也不改变上面的 v0 字段表。

## Backward compatibility

- v0-r01 `id/title/kind/text/added_at` 可以迁移为 C11 r1；正文 bytes 不得改变。
- 旧只读展示可以在明确声明 legacy-display-only 时读取 v1 `title/text`；抽取、重导、问答、事实确认和 stale 判断必须升级后才可消费。
- 未知版本、缺 `chapter_revision_ref`、ref 与 `id/text` 不一致时 fail closed。
- Outline 不迁。

## 仍未解决

- 无来源文件名、无清洗损失明细；章序校验、缺章检测、水印剥离未做（台账 I-001／I-002／I-003／I-006）。
