# WO-01 Runner／Scorer 安全适配预检

✅ 这张工单只修“以后怎么安全运行、怎么正确计分”，没有运行模型，也没有训练。

R01 的 72 份输入材料继续原样保留，身份收窄为：

```text
PASS_INPUT_PREFLIGHT_ONLY
```

它不能直接交给 P3 旧 runner。旧 runner 会把三条消息中的最后一条 assistant gold 去掉；WO-01 只有 system＋user 两条，照搬 `messages[:-1]` 会把 user 正文一起删掉。

本 revision 新增专用 runner，明确把两条消息完整交给 chat template。专用 scorer 也只认 `TARGET_ONLY / SMALL_HALO / CURRENT_WINDOW`，固定每臂 24 题、共同 48 条 gold，不接受历史臂名或历史 checkpoint 分母。

当前只完成 TEST_ONLY 静态演练：72 份请求的 system 和 user 均进入同一个序列化函数；8 个评分夹具覆盖正常、空答案、容器损坏但事实可恢复、非法 evidence、只读泄漏、复读、触顶和非法 status。另有一组跨三臂夹具，证明同题同 fact 只产生一条不显示 arm 的盲审候选，并共用同一语义裁决。它们不是模型输出，也不是实验成绩。

运行权仍是关闭的。未来即使有人调用 `run`，也必须另外提供一张绑定当前 runner SHA、R01 manifest、checkpoint、基础模型 13 件、Schema、chat template、固定解码参数、唯一 run ID 和唯一输出目录的 CZ 授权票。同一张票只能用一次，运行中断也不能重试。

运行工件只能写进固定的 `runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_R01/`。本预检目录封票后只读，不能被正式运行写入 claim、缓存、原始输出或评分文件。

评分也拆成两道不可覆盖的目录：先生成盲审队列，再在裁决齐全后生成最终分。第一道不是最终 semantic F1，第二道才允许生成配对 bootstrap。

来源：Codex
