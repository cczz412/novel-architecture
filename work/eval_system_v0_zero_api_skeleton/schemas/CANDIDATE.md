# 本骨架不冻结的候选

这些出现在顾问稿或夹具里，**不是**正式产品合同。检查器最多做结构检查，不会拿它们当已批准枚举。

- 正式 verdict 全集（夹具只用到 `SUPPORTED` / `REJECTED` 举例）
- 正式原因码全集、主原因优先级、多原因排序
- 通过时 `reason_code` 最终空值写法
- 生产 ID 格式
- API grader、模型排名、总分
- HMAC、近重复阈值、真实作品权利
- `CONTRACT_GAP` / `UNKNOWN` 若出现，只是 v0 候选

夹具里的 `SYN_*` 原因码是自编短句标签，状态是 `CANDIDATE`。不得强制 `single_primary_reason`。

更严的夹具形状只放在 [`v0_synthetic_fixture_profile.schema.json`](v0_synthetic_fixture_profile.schema.json)，不能倒过来改 `V0_SKELETON_CONTRACT`。

来源：GitHub #167
