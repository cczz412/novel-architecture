# Schema 两份文件

- [`v0_skeleton_contract.schema.json`](v0_skeleton_contract.schema.json)：只强制 #167 已冻的关系（三种对照回执、`READ_ONLY`、原件不可变、修复副本不能进主评测、64 位哈希、禁止 `GOLD`）。**不**用穷举 `enum` 把未冻结取值判成产品非法。
- [`v0_synthetic_fixture_profile.schema.json`](v0_synthetic_fixture_profile.schema.json)：只约束本目录合成夹具长什么样。不是产品合同。

[`CANDIDATE.md`](CANDIDATE.md) 列的名字仍然不能升成正式枚举。
