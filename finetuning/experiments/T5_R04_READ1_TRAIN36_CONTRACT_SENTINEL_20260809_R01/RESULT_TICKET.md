# TRAIN36＋共同输出合同｜READ1 24步哨兵

结论：`FAIL_STOP_AT_8`。

本轮从冻结 TRAIN36 READ1 派生36条训练行，user、assistant、metadata和顺序不变；训练与8道考试题都只在 system 末尾追加同一行完整输出合同。

- 派生训练数据 SHA：`74ec989941db110c15d1d183dbc12f37aecf1922e68c8b73d52e074aee8a4504`。
- 24步 adapter SHA：`6a58425559c66f9c0c1f10f97ca8be90e9eb1ebe2b2efe932980511c8c9d03ae`；训练耗时 371.471 秒。
- 8题事实：TP=32，FP=44，FN=53，P=0.421053，R=0.376471，F1=0.397516。
- 8题格式：严格 JSON=8/8，完整 Schema=8/8，非法证据=0，复读题=0，触顶题=0，重复事实=0。
- 命中字段：status=19/32，speaker=25/32，evidence=15/32。
- 三道门：格式稳定=True；事实保留=False；status过半=True。

若结论为 `FAIL_STOP_AT_8`，本轮不补完整24题、不增加训练步数，也不触碰 TRAIN48、READ2/4 或 OUT。

来源：Codex
