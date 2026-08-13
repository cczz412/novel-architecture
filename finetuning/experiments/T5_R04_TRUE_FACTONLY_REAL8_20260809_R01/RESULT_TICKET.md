# TRUE-FACTONLY REAL8｜零训练结果

结论：`FAIL_TRUE_FACTONLY_NOT_TRANSFER_QUALIFIED`。

本格只把现成 READ1 TRAIN36 iter24 的输出要求改为每项仅含 `fact`。同一8题、READ1正文、Gold、checkpoint、解码和事实语义评分口径均未改变；旧全字段 A 臂没有重跑。

- 旧全字段 A：TP=37，FP=42，FN=48，F1=0.451220。
- TRUE-FACTONLY：TP=32，FP=97，FN=53，P=0.248062，R=0.376471，F1=0.299065。
- 输出形状：严格 JSON=8/8，fact-only Schema=7/8；C02 把 `facts` 写成字符串数组，Schema 判失败，但字符串内容仍只进入可恢复语义审查，没有补字段或改写输出。
- 稳定性：复读题=0，触顶题=0，重复事实=0。
- 晋级门：F1达标=False，TP达标=False，0复读=True，0触顶=True。

本轮已硬停：没有扩到 REAL24，没有训练 Stage1，没有制作或运行 Stage2，也没有调用 API。

来源：Codex
