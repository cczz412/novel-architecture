# 🎯 T5 R04｜生产数据本地定版与云费用最小化

## 当前结论

P1 合同和实物盘点已完成，停在真实 Production Canonical 入口，没有开训练。

## 为什么停

- 正向 314 行缺逐行训练权利账和稳定 evidence 位置；
- 特殊 84 行缺作者身份，旧 69 行缺稳定书号；
- 作者级 TRAIN／DEV split 不能机械证明；
- 五本冻结书的 4 个历史特殊行必须从新 P1 分母排除。

## 当前产物

`finetuning/experiments/T5_R04_LOCAL_FIRST_PRODUCTION_GATE_P1_20260808_R01/`

## 唯一下一动作

补齐权利、evidence 位置和作者／书籍身份账，再生成 `PRODUCTION_CANONICAL_V1_CANDIDATE_R01`。三项未齐时不训练 REAL_A/C2，不进入豆包。

## 不要重复

- 不改 P0 历史文件；
- 不用历史 350/48 冒充新的作者级 split；
- 不拿特殊 84 单独当生产主教材；
- 不消费五本冻结书；
- 不恢复 Mini A/C2 双云训练。

来源：Codex
