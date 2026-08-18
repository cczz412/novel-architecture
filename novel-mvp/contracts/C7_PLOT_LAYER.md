# C7 · 剧情层（PLOT_LAYER）

**版本：v1**（M8 单次出题快照；v0 只少本版新增的三个稳定引用）

一句话用途：作者给一句「我要达成的目的」，系统吐出**计划**——卡片选项、卡上目的注解、写作指导三层、跟已确认事实打架的冲突。这是计划，不是事实；不回写 `facts.json`。

| 方向 | 模块 |
|---|---|
| 发 | M8 续写规划；现有 [plan.py](../mvp/plan.py) 仍是未升级的 v0 试跑代码，不属于本轮施工 |
| 收 | M0 展示、选择／停点动作层；未来 M9／M10／网页画布（本切片不接线） |

语义规则（ADD-037／A9、ADD-036／G5）：

- 目的挂到卡上（附着或单独开卡），人加的注解影响选项，**不改底层事实账**。
- 跟已确认事实或本章原意图打架时，冲突必须爆出来，问改哪边。
- 反向模式先生成「前面得先达成什么」的前置卡。
- 写作指导是出题副产品，不另开 API。三层＝卡片要解决什么／对白透露什么／插件写法（没有插件就空串）。
- J1：给要求给信息点，**不给示范成文**。
- C7 是可覆盖、可过期的只读快照。它没有规划账、事实账或 actual 写权，也不是完整章计划。

## 顶层结构

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `"C7_PLOT_LAYER v1"` | 是 |
| project / generated_at / model | str | 哪本书、何时出题、用什么模型（`--stub` 时为 `stub`） | 是 |
| purpose | str | 作者要达成的目的 | 是 |
| purpose_note | str | 卡上注解／额外限制（可空） | 是 |
| mode | str | `forward` 正向出题／`reverse` 先拆前置卡 | 是 |
| purpose_placement | str | `standalone` 单独开卡／`attach` 附着在剧情卡上（有注解时） | 是 |
| chapter_intent | str | 本章原意图（可空）；用来对拍冲突 | 是 |
| confirmed_fact_ids | list | 本次吃进的已确认事实号 | 是 |
| cards | list | 出题卡（含前置卡） | 是 |
| conflicts | list | 跟真值或本章原意图打架的条目；可空，但字段必须在 | 是 |

## 卡片（cards 一条）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| id | str | 本份产出内唯一，如 `card01` | 是 |
| role | str | `purpose` 目的卡／`prerequisite` 前置卡／`attach` 附着卡 | 是 |
| title | str | 卡标题（人话） | 是 |
| purpose_note | str | 本卡要达成的效果／作者注解 | 是 |
| options | list | 至少 1 条；每条 `{id, label, reveal_intent}` | 是 |
| recommended_option_ref | str | 主推荐的稳定引用 | 是；必须指向本卡一个真实 `options[].id` |
| planning_card_ref | str | 这道题所属的稳定主架卡／规划对象引用 | 是；正式 AC 号或完整沙箱卡引用 |
| planning_card_rev | int | 出题时看到的规划对象修订号 | 是；从 1 起，写前必须仍与当前对象一致 |
| guidance | obj | 写作指导三层，见下 | 是 |

`options[].id`：`A`／`B`／`C`。`label`＝选项方向（不是成文）。`reveal_intent`＝对白该透露的信息点。

`recommended_option_ref` 只保存选项 ID，不复制选项正文。选项重排后，推荐对象身份不能变化；引用不存在时必须拒绝，不能退回 `options[0]`。

`planning_card_ref` 优先引用已有稳定 AC 号；沙箱期使用章工作台规定的完整引用，例如 `SB-0001#d-ac-1`。C7 的局部 `cards[].id` 只用于在本快照内找卡，不得进入长期规划账。`planning_card_ref` 不存在、不可选择，或 `planning_card_rev` 已过期时，选择动作必须在 planstore 写入前停止。

`guidance`：

| 字段 | 含义 |
|---|---|
| card_problem | 这张卡要解决什么 |
| dialogue_reveal | 对白该透露什么 |
| plugin_craft | 插件自带写法；没有插件就 `""` |

## 冲突（conflicts 一条）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| kind | str | `fact` 顶撞已确认事实／`intent` 顶撞本章原意图 | 是 |
| fact_id | str | 涉事事实号；`intent` 类可空串 | 是 |
| fact_text | str | 涉事事实句或原意图原文 | 是 |
| why | str | 为什么打架 | 是 |
| ask | str | 固定问法：改目的，还是改已确认事实／本章原意图？ | 是 |

## 真实示例（stub 形状）

```json
{
  "contract": "C7_PLOT_LAYER v1",
  "project": "_m8_v0_selftest",
  "generated_at": "2026-08-13 19:00:00",
  "model": "stub",
  "purpose": "让陈平在这一章活着走出来，并告诉九棺真相",
  "purpose_note": "",
  "mode": "reverse",
  "purpose_placement": "standalone",
  "chapter_intent": "继续瞒住棺中有人",
  "confirmed_fact_ids": ["f001", "f002"],
  "cards": [
    {
      "id": "card01",
      "role": "prerequisite",
      "title": "前置：让关键人物处于能被改变的状态",
      "purpose_note": "后面那张目的卡要成立，这里必须先成立",
      "options": [
        {"id": "A", "label": "先把「已死」从公开认知里拆开一条缝", "reveal_intent": "只透露有人在查，不透露结论"},
        {"id": "B", "label": "先安排一次无法用「已死」解释的现场痕迹", "reveal_intent": "痕迹本身，不解释来源"},
        {"id": "C", "label": "先让知情者自己动摇", "reveal_intent": "动摇，不给新设定"}
      ],
      "recommended_option_ref": "B",
      "planning_card_ref": "SB-0001#d-ac-1",
      "planning_card_rev": 1,
      "guidance": {
        "card_problem": "后面要让人活着出现，先处理「已经死了」这笔账",
        "dialogue_reveal": "只能透露「这件事没结」",
        "plugin_craft": ""
      }
    }
  ],
  "conflicts": [
    {
      "kind": "fact",
      "fact_id": "f001",
      "fact_text": "陈平已经死了，埋在后山。",
      "why": "已确认事实写「死」，目的要「活着走出来」",
      "ask": "改目的，还是改已确认事实？"
    }
  ]
}
```

## 接缝边界与未施工部分

- C7 自己不改账、不重出变更清单。选定、整组驳回或自动放行必须另走 [C7_SELECTION_ACTION.md](C7_SELECTION_ACTION.md)，再由 planstore 校验和落盘。
- C7 不落规划账 `plan.json`；现有 v0 试跑代码仍只覆盖写 `plan_latest.json`，正式 v1 发送端与 planstore 尚未施工。
- 本版只绑定稳定规划卡，不把 `arc_card`、槽、场、PE、事实或 actual 塞进 C7。
- 插件写法位恒空，不接插件系统。
