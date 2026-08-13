# 生产模型路线总路牌 V2

```text
M1 本地 synthetic 风洞
        ↓
真实 Production Canonical 定版
        ↓
本地 REAL_A / REAL_C2 多 seed
        ↓
本地 One-stage / Evidence-first
        ↓
本地数据量收益验证
        ↓
冻结唯一生产候选
        ↓
Mini BASE 低成本兼容性检查
        ↓
一次 Mini 正式微调
        ↓
Mini 真实 DEV
        ↓
建立 Mini 困难集
        ↓
Lite BASE
        ↓
有充分理由时才提 Lite 微调
        ↓
扩大真实教材
        ↓
最终真实 Blind
```

## 当前所在位置

停在“真实 Production Canonical 定版”的入口。

当前不是模型训练问题，而是数据资格问题：正向卷缺训练权利账和稳定 evidence 位置，特殊卷缺作者身份，作者级 split 还没法锁。

## 唯一下一动作

补齐正向 314 行的逐行权利登记和 evidence 明确位置；补齐特殊 84 行的作者／稳定书籍身份；排除五本冻结书后，再生成 `PRODUCTION_CANONICAL_V1_CANDIDATE_R01`。

这三项未齐时，不训练本地 REAL_A/C2，更不进入豆包。

来源：Codex
