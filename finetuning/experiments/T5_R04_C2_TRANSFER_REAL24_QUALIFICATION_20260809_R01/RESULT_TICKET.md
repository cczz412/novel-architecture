# 旧 M1 C2_FULL update72｜REAL24 READ1 转移资格

结论：`FAIL_STOP_C2_TRANSFER`。

本轮只让冻结 C2 update72 回答8道原始 READ1 题面；没有追加格式合同，没有训练，也没有复制或改写 adapter。

- adapter SHA：`321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9`。
- 事实：TP=37，FP=59，FN=48，P=0.385417，R=0.435294，F1=0.408840。
- 格式：严格 JSON=8/8，完整 Schema=2/8，非法证据=0，复读题=0，触顶题=0，重复事实=0。
- 命中字段：status=14/37，speaker=23/37，evidence=18/37。
- 资格门：稳定性=True；事实不低于当前最佳 low-dose A=False；Schema 8/8=False。

若结论为 `FAIL_STOP_C2_TRANSFER`，旧 C2 转移路线在8题淘汰：不跑格式 B，不追 D/E/SMALL_HALO，也不扩完整24题。

来源：Codex
