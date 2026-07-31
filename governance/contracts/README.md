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

S-06-A 新增三份仓库瘦身合同：

- `external_archive_registry_v1.schema.json`：约束主仓、同级外置仓、隔离实验区、测试工作区
  的定位方式，对象身份、消费者收口、清单 SHA、已知矛盾和 10MB 体积政策。
- `repo_slim_inventory_report_v1.schema.json`：约束只读扫描报告。报告必须明确写出是否达到
  10MB，并把“库存可信”“可恢复”“已迁移”分开，不能拿一个 PASS 全包。
- `repository_size_migration_receipt_v1.schema.json`：只供以后切换 10MB 硬上限。票据不仅
  要有固定 SHA，还必须证明迁移发生、消费者已收口、指针能解析、外置快照已验，并列出
  登记过的迁移对象。

登记实例只认 `../external_archive_registry.json`。结构约束本身不授权移动、删除、恢复、
联网、读密钥、调用模型或写 Notion。迁移完成票只是必要条件，不是充分条件；S-06-A
明确拒绝启用硬上限，必须等另行获批的外置 payload 逐文件验证器。

S-06-B 新增两份逐文件验证合同：

- `external_payload_validation_policy_v1.schema.json`：约束单件读取白名单、旧对象排除原因、
  payload 相对根和清单大小字段；不能自动发现对象，也不授权迁移或硬门。
- `external_payload_verification_report_v1.schema.json`：约束不含逐文件列表的轻量 PASS
  报告。报告只证明 payload 文件集合、大小和 SHA 与清单一致，其余能力一律固定为否。

政策实例只认 `../external_payload_validation_policy.json`。旧三批缺逐文件 SHA、旧 TEMP
外置根缺清单，都必须保持排除；不能用抽样、绝对路径或目录存在冒充完整验证。

纯规则检查点登记在 `../rule_check_registry.json`。它把材料、锚、格式、参数、调用账、密钥、保护件、金标、泄题、重放、交付和受影响测试 18 类检查逐项钉到程序入口，检查员 API 不重复裁这些机械事实。

来源：Codex
