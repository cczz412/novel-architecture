# 生产模型路线总路牌

## 大白话总线

```text
本地 C2 runtime constraint 收口
→ 本地 Qwen 风洞封口
→ Mini BASE / A / C2 synthetic transfer
→ REAL_TRAIN48 / REAL_DEV48
→ Mini one-stage C2 / Oracle evidence / Predicted evidence
→ 冻结生产接口
→ Lite 困难切片验证
→ 扩大真实教材
→ Mini 主路由 / Lite escalation
→ 最终 REAL Blind C96+
```

本地 Qwen 只在最前面做风洞、排错、renderer／evaluator 验证和低成本消融。生产接口的真正判定模型是 Mini，复杂升级候选是 Lite。

## P0-A｜本地 C2 runtime constraint 收口

当前状态：**HARD STOP 于前置能力审计**。

已核清：

- M1 C2 update72 使用 MLX-LM 0.30.7；
- 当前环境没有已安装、已冻结的 JSON Grammar／Minimal Schema 后端；
- MLX 有通用 logits processor 插口，但这不等于已有 constraint backend；
- 换成 HF／vLLM／llama.cpp 会同时改变推理引擎，不能作为主实验。

处置：

- 不跑一份没有对照臂的新 Free；
- 不建大型本地 constraint 基础设施；
- 记录能力缺口；
- 本地 constraint 的实际复验后移到 Doubao Mini 平台能力门。

如 CZ 以后仍需本地三臂，必须独立批准小型 MLX backend 试作，不能把本票当成自动授权。

## P0-B｜本地 Qwen 风洞封口

冻结：

- C2_FULL：本地第一候选；
- A_FULL：跨模型迁移基线；
- D_RANGE：工程消融／备选；
- E_UNIT_QUOTE：暂停；
- `LR=3e-5 + 72 updates`：只属于本地 Qwen／MLX；
- TRAIN24／DEV24：只是 synthetic 工程冒烟。

不将 C2 写成豆包生产格式，也不扩大本地 Qwen 的线上职责。

## P1｜Mini BASE／A／C2 synthetic transfer

运行：

- `MINI_BASE`；
- `MINI_A_FULL`；
- `MINI_C2_FULL`；
- `MINI_C2_CONSTRAINED` 只在锁定 Mini 真实支持时存在。

进场门：

- Mini 确切版本／可训资格／结构化输出能力已有当时官方票；
- 豆包训练超参另立合同；
- A／C2 同 canonical、同分母、同预算；
- 有费用帽、API 和上传授权。

结论只限格式迁移，不评生产性能。

## P2｜REAL_TRAIN48／REAL_DEV48

进场门：

- 真实中文小说表达；
- TRAIN／DEV 作者和作品完全隔离；
- canonical gold 统一；
- A／C2 机械派生；
- evidence start/end 明确；
- 双人独立语义审查；
- provenance 和权利状态通过；
- 普通和困难案例分层。

当前五本新书全部不进 TRAIN；CZ 亲选 2 本 DEV，其余 3 本继续 blind 封存。

## P3｜Mini One-stage／Oracle／Predicted Evidence

三个比较：

- One-stage C2；
- Gold Evidence Oracle；
- Predicted Evidence Pipeline。

重点看 evidence recall／fact semantic F1／unsupported／omission／status／speaker／duplication／延迟／token／Mini 费用。

Oracle 没有收益就不扩 evidence-first；Predicted Evidence 吃不到 Oracle 收益就先查 Stage A，不宣布主架构。

## P4｜冻结生产接口

冻结物至少包含：

- 单阶段或 evidence-first 选择；
- Mini 精确模型／精调版本；
- 模型输入／输出合同；
- deterministic program 责任边界；
- ID／start-end／speaker／去重／排序／JSON／Schema；
- evaluator 和人工尺子；
- 失败与升级信号。

冻结接口不等于已上线。

## P5｜Lite 困难切片验证

Lite 只跑 Mini 最终胜出接口；如 evidence-first 已通过，才加 evidence-first。

不在 Lite 上重跑 A／C2／D／E 格式锦标赛。

## P6｜扩大真实教材

只有 Mini 在真实 pilot 上证明 synthetic→real 不崩，生产接口已冻结，才扩真实教材。

一直保持：

- 作者／作品分散；
- 近年真实网文为主；
- 正常／困难案例分层；
- 一份 canonical，多格式机械派生；
- provenance 和权利门。

## P7｜Mini 主路由／Lite escalation

在线角色只能是：

- Mini：主体流量；
- Lite：预注册困难／低信心切片升级；
- deterministic program：最终结果质检和组装。

切流规则需要另一张 CZ 拍板，不由本路牌自动生效。

## P8｜最终 REAL Blind C96+

只有下列内容全部冻结后才打开：

- 生产接口；
- Mini／Lite 精确版本；
- 训练产物；
- evaluator／人工裁决规则；
- 生产判定门槛；
- 数据隔离和权利票。

Blind 打开后，不得为了提分改 prompt、换 checkpoint、修 renderer／Schema 或重选书。

## 当前明确不做

- 不启动 M2；
- 不启动 SEMANTIC_CORE；
- 不生成第三批 synthetic；
- 不训练豆包；
- 不调用豆包 API；
- 不选当前五本书；
- 不切五本书；
- 不修 gold 或 renderer；
- 不改 `finetuning/CURRENT.json`。

来源：Codex
