# 流水线合同说明

目标模块从 M00 到 M11。每份新制中间工件应带共同外壳：

```json
{
  "contract_version": "...",
  "artifact_type": "...",
  "artifact_id": "...",
  "book_id": "...",
  "chapter_range": {"start": 1, "end": 20},
  "run_id": "...",
  "producer": {
    "module_id": "M05",
    "module_version": "v1.0.0",
    "code_sha256": "..."
  },
  "inputs": [{"artifact_id": "...", "sha256": "..."}],
  "status": "complete",
  "payload": {},
  "validation": {
    "validator_version": "...",
    "passed": true,
    "receipt_sha256": "..."
  }
}
```

旧工件仍按原合同读取；新模块只有在输入输出主版本、SHA、定向测试、真实样本、直接下游和回退条件都过闸后，才能标成“可用”。

第二期新增两份正式机器合同：

- `semantic_inspector_v1.json`：只管低成本语义检查分流。疑义、否定、跨章因果先由程序送强审；DeepSeek 不能产真值，也不能修改输入。
- `../test_policy.json`：只管该跑哪些测试。状态为“可用”且现役合同没变的模块，局部验票后免全链；现役合同、大版本、总入口、运输或无法判断影响范围的变化触发全链。

纯规则检查点登记在 `../rule_check_registry.json`。它把材料、锚、格式、参数、调用账、密钥、保护件、金标、泄题、重放、交付和受影响测试 18 类检查逐项钉到程序入口，检查员 API 不重复裁这些机械事实。

来源：Codex
