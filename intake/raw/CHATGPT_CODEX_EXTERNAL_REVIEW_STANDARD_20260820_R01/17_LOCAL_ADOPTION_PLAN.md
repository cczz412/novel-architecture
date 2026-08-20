# 本地采用计划

## 建议落点

```text
docs/standards/chatgpt-external-review/
  CURRENT.md
  R01/
```

根 `AGENTS.md` 只挂一个入口，不复制全文。

## 本地 Codex 最小施工

1. 接纳/修订本规格；
2. 建 `pack_chatgpt_review.py`，支持 Bootstrap / Delta / Result profiles；
3. 接入本包四个标准库工具；
4. 给每个外审包生成 Manifest、SHA、Build Receipt；
5. 给本地任务系统增加字段：`chat_mode`、`project_memory_mode`、`source_strategy`、`package_profile`；
6. 建 Project Source 发布清单；
7. 建结果回收校验；
8. 用 1～2 个真实长期外审周期试跑后升 R02。

## 建议新增本地字段

```json
{
  "external_review": {
    "project_id": "...",
    "memory_mode": "PROJECT_ONLY",
    "chat_strategy": "REUSE_STAGE_CHAT",
    "semantic_source_version": "...",
    "asset_source_version": "...",
    "bootstrap_package_id": "...",
    "last_checkpoint_sha256": "...",
    "model_label": "...",
    "result_zip_sha256": "..."
  }
}
```

## 不应改动

接纳本规格不自动修改：

- 产品 R13；
- 正式合同；
- 模块完成度；
- API/训练权限；
- Notion；
- Git current；
- 作者数据政策。

## R02 触发

- 本地 Packager 完成并跑 3 次；
- Project Source 版本更新流程实跑；
- 同 Chat Bootstrap→Delta→Result 走通；
- 一次 sandbox reset 恢复演练；
- 发现官方能力变化。
