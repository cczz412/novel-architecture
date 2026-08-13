# READ1 iter24 零训练格式合同 A/B｜8题结果

结论：`FAIL_STOP_AT_8`。

本轮只在 B 臂 system 末尾追加一行结构合同；checkpoint、8道 READ1 题面正文、Gold、解码、停止条件和评分口径均不变。没有训练，也没有调用 API。

- A 臂旧提示：TP=37，预测=79，Gold=85，F1=0.451220，完整 Schema=0/8。
- B 臂结构合同：TP=33，FP=41，FN=52，P=0.445946，R=0.388235，F1=0.415094。
- B 臂格式：严格 JSON=8/8，完整 Schema=8/8，非法证据=0，复读题=0，触顶题=0，重复事实=0。
- B 臂字段类型：74/74 条预测使用合法 status，74/74 的 speaker 类型合法，74/74 的 evidence_ids 类型合法。
- B 臂命中事实字段：status=20/33，speaker=25/33，evidence=16/33。
- 三道门：格式稳定=True；事实保留=False；status 过半=True。

若结论为 `FAIL_STOP_AT_8`，本轮在8题硬停，不补完整24题，不改 Prompt，不加第三臂，不训练。

来源：Codex
