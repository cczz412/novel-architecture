# 微调实验夹｜正线已删，留下两类痕迹

正线（CPLUS、MIX、P2／P3／P4、路线图、资格账、金标／训练消费者）已经退出本 Git。这里只剩两类东西，别混。

## 1. 试过不行的结果票（要留）

说白了就是：同一套本机小模型，Prompt／剂量／格式这样改好还是那样改好。结论写在各包的 `RESULT_TICKET.md` 里。

🔥 考官是本机 **Qwen 3 4B（MLX）**。不是 Deepseek，也不是豆包。豆包只在 P0 写过「生产模型以后怎么迁」的路牌，没来判这些题。

留下的票大致是：

- [READ1 格式合同 A/B 8题](T5_R04_READ1_FORMAT_CONTRACT_AB8_20260809_R01/RESULT_TICKET.md)
- [READ1 短格式 C 8题](T5_R04_READ1_FORMAT_SHORT_C8_20260809_R01/RESULT_TICKET.md)
- [READ1 低剂量哨兵](T5_R04_READ1_LOW_DOSE_SENTINEL_20260809_R01/RESULT_TICKET.md)
- [READ1 TRAIN36／TRAIN48 混合哨兵](T5_R04_READ1_TRAIN36_CONTRACT_SENTINEL_20260809_R01/RESULT_TICKET.md)
- [AC 格式对照](T5_R04_AC_FORMAT_COMPARE_20260807_R01/)
- [TRUE_FACTONLY REAL8](T5_R04_TRUE_FACTONLY_REAL8_20260809_R01/RESULT_TICKET.md)
- 以及 READ4 探针、C2 迁移资格、WO01 Demo 跑票等

## 2. 中间桥工具包（暂时留，后期整顿）

这些不是「还能接着训练」的正线。它们是当时互相借用的初筛、预飞、认分脚本，别的包会 import 这里的程序。

⚠️ 相当于临时桥。以后要收成真正的共用工具，不要再在实验夹里复制来复制去。

包括名字里带 `SCREEN`、`PREFLIGHT`、认分／fair scoring 的包，以及 WO01 的 runner／scorer 预飞。P4 那份宽读窄写预飞也先放着，性质一样。

## 3. 豆包路牌（不是这批对照实验）

[PRODUCTION_MODEL_MIGRATION_P0](T5_R04_PRODUCTION_MODEL_MIGRATION_P0_20260808_R01/) 讲豆包 Mini／Lite 以后怎么迁。它停在「还没开跑」的路牌，不能拿来回答「Prompt 这样好还是那样好」。

## 当前指针

机器只认上一级的 [CURRENT.json](../CURRENT.json)，现在落到 [T5_R04_LINE_ABANDONED_20260823_R01](T5_R04_LINE_ABANDONED_20260823_R01/)。那是空落点，不授权训练。

来源：CZ 2026-08-23 拍板；#99
