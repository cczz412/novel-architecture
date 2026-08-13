# P3 C0 运行时校验分层

这份说明只把四种校验拆开，避免把“结构合法”误写成“答案正确”。P4.1 只新增第二层的独立 Schema。

## 1. 原始输出能否完整解析

冻结 M1 runner 先对整段输出执行严格 JSON 解析。只有 `json.loads(raw.strip())` 成功，且整段没有 JSON 前后的解释文字，才进入结构检查。

- 真源：`TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/tools/m1_runner.py`
- 现场 SHA：`f2199b8f911894d8347878a97244ca3b41e8e19fc5297408fd6e8d18a2f81be7`
- 位置：`analyze_output` 中的整段解析
- P4.1 没有另做 parser，也没有改变这一层。

## 2. JSON 结构是否符合现役宽松边界

本轮新增的 `P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json` 只检查根容器、字段集合、字段类型和八态枚举。

它刻意保留现役宽松行为：

- `facts` 可以是空数组；
- `speaker` 可以是 `null`、普通字符串或空字符串；
- `evidence_ids` 可以为空、重复，也可以包含任意字符串；
- 不检查 ID 是否存在，不检查证据是否最小充分。

等价 oracle 没有成功导入完整 M1 runner。它先核整个 runner 的 SHA，再从同一冻结源码 AST 中机械提取唯一的 `check_schema` 函数、`ALLOWED_STATUS` 和 `ARMS["c2_full"]["required"]`，编译执行原函数节点。这个方法名为 `FROZEN_SOURCE_AST_ORACLE`。

本轮只声明：

> standalone Schema 与已核 SHA 的 frozen `check_schema` 接受语言，在固定目标 corpus、24 gold、24 历史输出上等价。

这里的“接受语言”是：旧 oracle 只有正常返回 `True` 才算接受；正常返回 `False` 或抛异常都算不接受。

冻结函数对 `status=[]` 和 `status={}` 会抛 `TypeError`，而 JSON Schema 会正常拒绝。这两条难例仍在 corpus 中，不能把两种失败方式说成一样。P4.1 单列异常类型和样本 ID，不宣称所有 JSON 输入都能得到相同布尔返回。

## 3. evidence ID 是否属于当前责任区

这一层以后应检查 ID 是否存在、是否属于当前允许表、顺序、连续、最小充分和可回填映射。P4.1 没有物化新的 source-aware validator，也没有新增任何 evidence 规则。

现有相关诊断仍绑定冻结 M1 runner 和 P3 scorer；它们不是本轮 standalone Schema 的一部分。

## 4. 事实语义是否正确

P3 scorer 负责事实、状态、说话人和证据是否正确的评估：

- 真源：`finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/tools/score_p3_context_probe.py`
- 现场 SHA：`c7df1d96d785122d7af818c39c168be646298aa158cfa698102f24e4094e6674`

结构 Schema 通过，不代表事实正确、证据充分，也不代表答案来自负责区。P4.1 没有改 scorer、gold 或语义合同。

## 明确不作的声明

- 不宣称完整 M1 runner 已在当前锁定环境成功导入；
- 不宣称 standalone Schema 与训练运行时所有行为完全等价；
- 不宣称它与 Prompt 语义或 24 条请求字节等价；
- 不宣称非法输入的异常或错误行为等价；
- 不宣称 standalone Schema 可无差别替换旧 runtime runner；
- 不产生模型运行、训练、Production Canonical 或 P4 六臂授权。

来源：Codex
