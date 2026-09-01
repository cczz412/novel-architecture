# 设计冲突与边界

- Pro 建议给 B-07 新增状态和发布字段；current main 已有 `ACTIVE + FINALIZING` 和 `last_component_observation`，本目录直接复用，避免扩出第二套发布状态。
- Pro 把 reopen 解释成同 run 增加 epoch；current B-07 的真实语义是新建 run id 并增加 logical run generation。本目录按 current main 执行，resume 才增加同 run epoch。
- Pro 建议绑定 pointer snapshot；B-01 的现行产品状态是 mutable pointer，B-06 MergeReceipt 已冻结提交前后代次。本目录绑定 live pointer＋current CandidateVersion＋可选 MergeReceipt，不创造没人写、没人消费的新 snapshot。
- CCZ-105 仍是产品合同候选。本目录采用六类 B-08 产品结果和四类交付形状，只管终态原件；全产品重跑、人工复核和作者界面继续留在 CCZ-105。
- CCZ-142 目前没有本票可直接修改的产品级分类／覆盖 reader。当前 `TerminalAuthorityReader` 是严格接缝，fixture 从共享 SQLite 原件读取；真实 runtime 接线必须回 CCZ-142 自己的写集，不能在本票偷改。
- B-08 工件定位是写集内稳定逻辑定位，实际字节由唯一 SQLite writer 保存并可通过 `read_artifact_bytes` 读取；不另存第二份 JSON 原件。
- 当前只证明机械终态和适配门，不证明抽取准确率、速度或 Token 改善。

来源：Codex
