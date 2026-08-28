# B-01 来源与输出索引

## 工程准入

| 依据 | 精确身份 | 这份依据在这里证明什么 |
| --- | --- | --- |
| GitHub PR #186 | reviewed/merge head `9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26` | A 机械外壳的精确受审版本 |
| GitHub current main | merge commit `019df751641533c7de4d56aa38f50747fb564036` | A 已进入 current main |
| `A_INTERFACE_ADMISSION_RECEIPT` | record hash `91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af` | B 的 GLOBAL-A 准入成立 |
| A interface manifest | payload hash `50c5c74c67678565693dd86c27dab20319a0d107bb9d196b21d23643843ca860` | A 接口文件集没有漂移 |

## B 设计与施工范围

| 依据 | SHA-256 | 用途 |
| --- | --- | --- |
| `ccz57_m3_b_stage_candidate_blueprint_20260828_r03_4.md` | `8db5f9acb8ada30e929af4e710790bb36c6058023928de513757465a0fa43cd2` | B-01～B-12 共用候选协议和依赖真源 |
| R03.4 文档自校验 | `c3203ef73c9d0fc23f843673df0325b95d4d6c52cb752e8c9b543c80dc1151b0` | 蓝图内部固定向量身份 |
| `ccz57_m3_b01_construction_contract_candidate_20260828_r01.md` | `c6f41e6116ae8d87289ad0a7d9541d59750566eee3b63a50b873845e808c3b33` | B-01 唯一写集、对象、writer、夹具和失败码 |
| GitHub Issue #189 | `施工｜CCZ-57 M3 B-01 CandidateVersion、责任段索引与 current pointer 基础` | 本次施工授权和 Draft PR 停点 |

## 文件分别负责什么

| 文件 | 用途 |
| --- | --- |
| `b01_contract.py` | 不可变外壳、固定哈希、三种 writer、派生 diff 和原子 fixture store |
| `OBJECT_SHAPES.json` | 五类输出、固定字段和唯一 writer 的机器目录 |
| `fixtures.py` | 8 个正常夹具族和 20 个失败夹具族，只含合成内容 |
| `test_b01_contract.py` | 定向测试、崩溃点和 0 半成品断言 |
| `self_check.py` | 离线重放、引用检查、静态禁用路径检查和报告生成 |
| `OFFLINE_REPLAY_REPORT.json` | 当前机械复验结果，不承载语义验收 |
| `DESIGN_CONFLICTS_AND_LIMITS.md` | 当前能力边界和后续票的归属 |
| `MANIFEST.sha256` | 除自身外 9 个交付文件的完整性清单 |

## 写入归属

唯一允许写集是：

```text
work/ccz57_m3_b01_candidate_version_r03_4/**
```

B-01 不读取 `local/`，不读取小说正文，不调用 B-02 或其他后续票的 writer。

来源：Codex
