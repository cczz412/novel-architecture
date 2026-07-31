# S-05-B 历史测试回放 v2｜轻量结论卡

> 本页由同目录 `result_card.json`、`external_pointer.json` 和
> `retrieval_profile.json` 确定性生成；这张卡自身的机器真源只认这三份 JSON，请勿手改本页。

## 一眼看懂

- 实验编号：`S-05-B-HISTORICAL-REPLAY-V2`
- 当前停点：已完成
- 质量裁决：通过
- 仓外对象：`historical-test-replay-s05b-v2`
- 固定清单 SHA：`1e1c003ec5fe1adb9c045584d7dc33415623607baef63c3e6e1060166ec4cca4`

## 这次想验证什么

在 v1 失败原因已经定位后，只补齐登记过的 Z01d 固定夹具，再验证 40 个历史测试能否在独立副本中完整回放。

## 怎么组装

- 程序固定在 Git 提交 d8371ea36ca2fc9b98300df6699f2e4bdb0468dc。
- 材料使用仓外对象 historical-test-replay-s05b-v2。
- 材料复制到新测试工作区后再运行，主仓和仓外原件都不回写。

## 结论

- 真实回放得到 40 项通过、3 个子测试通过，pytest 退出码为 0。
- v2 只补了登记过的 Z01d 旧运行取件单位，没有改写 v1。
- 这证明 40 个历史节点目前可按固定提交和冻结材料复验，不代表它们应重新进入日常测试。

## 这张结论不能说明什么

S-06-B 已证明 v2 当前 payload 与固定清单逐文件一致；通过只覆盖已登记的 40 个历史节点，不代表语义质量、独立灾备、源材料永久可恢复或 10MB 目标已经达成。

## 以后怎么取件

日常只读本页。确实要复现时，先核卡片和仓外清单：

```bash
.venv/bin/python tools/experiment_artifact_retrieval.py check --card-id s05b-historical-replay-v2
```

再按已登记组合生成复制计划。这个命令只输出 JSON，不会创建目录或复制文件：

```bash
.venv/bin/python tools/experiment_artifact_retrieval.py resolve --card-id s05b-historical-replay-v2 --selection-id full-replay-payload
```

- `full-replay-payload`：在全新测试工作区复现 v2 的 40 项通过、3 个子测试通过现场，不引用主仓可变工作树。

真正复制仍要等后续单独施工；当前没有复制子命令。

## 使用边界

本卡只记录 v2 的历史结论和取件入口；不授权重新加入日常测试、移动、删除、恢复、迁移或启用 10MB 硬门。

来源：Codex
