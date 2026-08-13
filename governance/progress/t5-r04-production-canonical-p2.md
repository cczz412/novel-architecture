# 🎯 T5 R04｜Production Canonical 前置资格修复 P2

## 当前结论

P2 已完成两遍一致性构建和机械复验，但在 Production Canonical V1 候选构造前硬停，没有训练。

## 真实漏斗

- 冻结输入：398 行／3,537 条事实；
- A 权利不明：314 行／2,783 条事实；
- 特殊卷作者身份不明：6 行／69 条事实；
- 重复证据位置歧义：1 行／29 条事实；
- 五本冻结来源排除：4 行／24 条事实；
- 通过机械资格门：73 行／632 条事实，而且全部是特殊教材。

## 已经修好的部分

- A 的 2,783 条 evidence 全部获得唯一 start/end，逐字回填通过；
- 特殊卷本地可确认的作者和书号已补；
- `FS02B-006-S01` 保持位置歧义隔离，没有默认第一次 occurrence；
- 五本冻结书在 eligible pool 中为 0；
- 当前 pool 的 TRAIN／DEV 作者、作品、来源交集均为 0。

## 当前产物

`finetuning/experiments/T5_R04_PRODUCTION_CANONICAL_PREREQUISITE_REPAIR_P2_20260808_R01/sealed_r01/`

## 唯一下一动作

补 A 314 行逐来源训练权利；如仍要回收特殊卷缺件，再只补 6 行作者身份和 1 行权威 evidence 位置。补证后新建 P2 revision，不能覆盖 R01。

## 不要重复

- 不从历史训练倒推权利；
- 不把特殊 73 行当生产主教材；
- 不消费五本冻结书；
- 不生成 A/C2 renderer；
- 不训练本地 Qwen 或豆包；
- 不覆盖 P2 R01。

来源：Codex
