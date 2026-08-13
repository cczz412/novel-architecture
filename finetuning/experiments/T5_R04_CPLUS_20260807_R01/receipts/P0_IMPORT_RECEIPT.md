# T5 R04 C+｜P0 决定导入回执

✅ P0 两份决定已经登记，新 C+ 实验已经成为微调域当前入口；这次切换只影响微调导航，没有改全仓当前状态，也没有启动训练或 500 本抽数。

- 实验：`T5_R04_CPLUS_20260807_R01`
- 证据合同：`C2_UNIT`
- 实验 MANIFEST SHA-256：`7f5818391b9988be2ddeb0d5ac89fe49363c0d0e245a7d02660cf649cab08216`
- P0 决定 SHA-256：`8ebc866dcbc83ef0ebc06ff5662f975dae133803963a66c245e12cd8793f60a0`
- 阈值与闸门 SHA-256：`fc428b8c8c299a166fc3d90a0be4c33ab9e1169ee33fdf8890a036d06425e580`
- 预检回执 SHA-256：`5a2529258dfe4b6244880c21b007f8accef6831b925e021e88f85e0ac09dddcd`

机械核对：

- 每臂母集 398 行；
- 每臂实际训练 350 行；
- 当前历史回归卷每臂 41 题、355 条金标；
- 旧冻结隔离卷每臂 48 题；
- 历史原始答卷共 82 份；
- stage1 与 final 四份 adapter 均在，并已绑定进 MANIFEST；
- `finetuning_control verify-current`：PASS；
- `finetuning_domain check`：PASS（v2 通用检查）；
- 微调域控制测试：7/7 PASS。

边界：不授权训练、转正、API、Notion、Git、500 本抽数或修改旧冻结证据。下一动作只允许执行阶段 1 的三个零训练根因证伪。

来源：Codex
