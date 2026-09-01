# B-06 已知限制与停点

## 已解决

- B-05 trial apply 与 B-06 commit 已共用同一 CandidateMutationKernel；
- child、current pointer、MergeReceipt 使用单一 SQLite 事务；
- B-07 run fence 只能通过同一事务 connection 的只读视图核对；B-06 不写 RunState；
- 同 operation 幂等重放、不同输入冲突、并发抢 pointer、数据库 reopen 和四个失败注入点都有定向反例；
- 没有 CommitIntent 表和 pointer snapshot 表；
- B-06 不读取正文、不调用模型、不写十本账。

## 仍未解决

- 现行 pointer namespace 仍是 fixture 身份；生产 pointer 的存储位置、租约和 reader 尚未接入；
- B-02 current scope、政策选择和非内容门当前由合成 authority reader 提供哈希，真实产品 reader 尚未接入；
- CCZ-142 真实保存结果还没有通过 exact adapter 进入本目录；
- 本目录证明的是版本安全和失败语义，不证明抽取准确率、速度、Token 或模块净减少已经达到产品目标；
- B-07～B-12 不在本票范围。

如果真实接线要求新增正式对象类型、writer、第三个写集或改变 B-05 路线语义，必须停下另行决定。

来源：Codex
