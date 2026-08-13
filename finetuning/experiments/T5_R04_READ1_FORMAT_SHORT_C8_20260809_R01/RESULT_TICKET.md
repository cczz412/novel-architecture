# READ1 iter24 短格式 Prompt C｜8题结果

结论：`FAIL_STOP_PROMPT_ONLY_ROUTE`。

C 只在原 system 末尾追加一行短格式说明；checkpoint、8道 READ1 正文、Gold、解码、停止条件和评分口径都没有改变。没有训练，也没有调用 API。

- A 旧提示：F1=0.451220，完整 Schema=0/8。
- B 完整合同：F1=0.415094，完整 Schema=8/8。
- C 短格式：TP=26，FP=40，FN=59，P=0.393939，R=0.305882，F1=0.344371。
- C 格式：严格 JSON=8/8，完整 Schema=8/8，非法证据=0，复读题=0，触顶题=0，重复事实=0。
- C 字段：合法 status=66/66；命中事实 status=17/26，speaker=16/26，evidence=11/26。
- 三道门：格式稳定=True；事实保留=False；status 过半=True。

若结论为 `FAIL_STOP_PROMPT_ONLY_ROUTE`，本轮在8题硬停，不补完整24题；Prompt-only 路线停止，不再造 D/E 措辞。

来源：Codex
