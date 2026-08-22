# PLAN_DESTINY_CONTENT · 人物命运条目内容合同

**正式版本：`destiny-plan-content-v1`**

一句话用途：给人物账 `destiny_ref` 一个真实存在的目标对象——人物命运条目住规划账（题 1 已拍），本合同把 L2 占位示例里的 `DESTINY-` 正式冻结为官方前缀，并随本票补齐人物账的存在性校验（复核注记 3 收口）。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 提出 | 作者、M8 候选 | 模糊未来内容经 M8 放置路由落到这里（M8-N01） |
| 唯一落盘 | planstore | 复用 `id_counters` 统一发号（`DESTINY` 计数器）；本票不实现写动作 |
| 读取 | M8、长线读取面、人物账存在性校验 | 只读已提交版本 |
| 跨账只读 | 人物账 | 人物账只保存 `destiny_ref` 稳定 ID，不复制命运正文 |

真值来源：拍板页 §5.7／题 1，复核页注记 3，`CHARACTER_LEDGER_CONTENT.md`。冲突时复核注记优先。

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `DESTINY-` 官方前缀＋十进制数字；L2 示例 `DESTINY-0001` 自本票起为正式形状 |
| `ch_ref` | str | 指向哪个人物，`CH-` ID |
| `destiny_text` | str | 命运正文，非空、去首尾空白 |
| `expected_at` | obj/null | 预计时机，三种锚之一，见 §3 |

另带规划账公共字段与 `confirm_status`＋`evidence_refs`（规则同 PLAN_VOLUME_CONTENT §2）。
`confirmed→retired` 后条目保留历史身份；取件码旧码仍可取旧版并标注（见 LEDGER_RECALL_CODE）。

## 3. 预计时机 `expected_at` 三种锚（题 1 已拍）

tagged union，`kind` 三选一；条目永远住账不动窝，写章取料带走的是引用：

1. `slot_anchor`：挂计划章槽 `{"kind":"slot_anchor","slot_ref":"S-0003"}`——写快写慢改槽位映射，条目不动窝；
2. `story_time_anchor`：挂故事内时间 `{"kind":"story_time_anchor","anchor":{"chapter_revision_ref":{…},"story_order":120}}`——锚坐标复用 L2 已冻的章 revision 三元组＋可选故事序；缺记录答 `NOT_RECORDED`，不可比答 `STORY_TIME_NOT_COMPARABLE`；禁止 `story_sequence`、禁止扁平 `text_sha256`；
3. `fuzzy_anchor`：只说「本卷内」「三卷内」`{"kind":"fuzzy_anchor","scope":"本卷内"}`——对账只提醒、不报警（`expected_at_alarm_policy` 恒答 `REMIND_ONLY`）。

配套语义（合同层声明，机器实现挂对账票）：写完由对账边标兑现／未兑现／改挂新落点；「先加两章铺垫再挂后面」＝插新槽＋改挂，必要时登记承接。

## 4. 与人物账的存在性闭环（复核注记 3，本票收口）

- 人物账 `destiny_ref` 非空时必须匹配 `^DESTINY-[0-9]+$`；
- 统一 writer／校验方提供命运目录时，`destiny_ref` 必须命中一个已登记的命运条目 `id`；
- L2 时代「只做形状校验」的开口自本票关闭，人物账合同、校验器与测试同票更新。

## 5. 真实示例

```json
{
  "contract": "PLAN_DESTINY_CONTENT",
  "version": "destiny-plan-content-v1",
  "id": "DESTINY-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "created_at": "2026-08-22T10:00:00+08:00",
  "updated_at": "2026-08-22T10:00:00+08:00",
  "rev": 1,
  "note": "",
  "ch_ref": "CH-0001",
  "destiny_text": "他最终会为守住北城而死。",
  "expected_at": {"kind": "fuzzy_anchor", "scope": "三卷内"}
}
```

## 6. 明确禁止

1. 禁止另发明 `DY-` 等第二套命运前缀。
2. 禁止 `expected_at` 三种锚平铺混写或发明第四种 `kind`。
3. 禁止模糊锚触发报警（只提醒）。
4. 禁止在故事时间锚里使用 `story_sequence` 或扁平 `text_sha256`。
5. 禁止本票实现 planstore 写动作、对账推进或 M8 路由 runtime。
6. 禁止把命运条目写进 C4 冒充已发生事实。

## 7. 机器件与状态

- `PLAN_DESTINY_CONTENT.schema.json`
- `validate_plan_destiny_content.py`
- `PLAN_DESTINY_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_plan_destiny_content_contract.py`

实现状态：`CONTRACT_ONLY__PLANSTORE_DESTINY_WRITE_PENDING`。
