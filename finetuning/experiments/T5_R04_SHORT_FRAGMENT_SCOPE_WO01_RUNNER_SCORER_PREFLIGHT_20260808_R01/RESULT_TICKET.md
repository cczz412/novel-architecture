# WO-01 Runner／Scorer 预检结果票

当前候选状态：`PASS_READY_FOR_INDEPENDENT_READONLY_REVIEW_NO_RUN_AUTHORITY`

✅ R01 的 72 份输入没有改字节，仍只认 `PASS_INPUT_PREFLIGHT_ONLY`。新 revision 已把未来运行和评分入口补齐，但没有给出模型运行权。

已机械证明：

- 每份请求的 system＋user 两条消息都会完整进入 chat template；
- `stream_generate` 只接收 model、tokenizer 两个位置参数，prompt 只传一次；
- 基础模型 receipt、revision 及未来正式运行前的 13 件逐文件核验已经写死；
- 运行只能写到固定 `runs/` 根下，同一 run ID／授权票不能换目录或重复使用；
- 运行前及每题前保留空闲内存硬停，MLX 上限、清缓存、峰值内存与耗时进入回执；
- scorer 先核 raw、运行票和 72 行逐题身份，再允许评分；
- 同题同 fact 的语义裁决跨三臂共用，给审查者的队列不显示 arm；
- pre-adjudication 与 final scoring 是两套不可覆盖工件，只有 final 且 pending 为 0 才能称最终语义分并生成 bootstrap；
- bootstrap 固定按 case 成对抽样 10,000 次，seed 为 `2026080801`，使用双侧 percentile Type-7 95% CI。

定向测试 21/21 通过，Ruff 通过；TEST_ONLY 派生物连续构建两次，5 件逐字一致。新增负测试证明：claim 抢占后即使起始票失败也保留 abort；pre 指标或隐藏 occurrence sidecar 任一漂移，final 都会硬停。所有夹具都明确不是模型输出或实验成绩。

⚠️ 仍未做：模型加载、72 次推理、API、训练、正式语义盲审、最终评分、任何 synthetic 生成、Notion、Git、CURRENT 或生产默认修改。

下一动作只能是独立只读审查；审查通过后封最终预检票，然后硬停等待 CZ 单独开运行授权。

来源：Codex
