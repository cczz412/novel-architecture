# S-05-B 历史测试回放 v1｜轻量结论卡

> 本页由同目录 `result_card.json`、`external_pointer.json` 和
> `retrieval_profile.json` 确定性生成；这张卡自身的机器真源只认这三份 JSON，请勿手改本页。

## 一眼看懂

- 实验编号：`S-05-B-HISTORICAL-REPLAY-V1`
- 当前停点：已被后续版本替代
- 质量裁决：失败
- 仓外对象：`historical-test-replay-s05b-v1`
- 固定清单 SHA：`f2f2b3b612ac4b18f98abbabdd0bf500337fde9cfe62be8dacf1ab03f6a5503a`

## 这次想验证什么

验证退出日常验收的 40 个历史测试，能否从固定 Git 提交和仓外冻结材料复制到独立工作区后真实回放。

## 怎么组装

- 程序固定在 Git 提交 ed0dddcd2428fae8daf726ca2985571843df263d。
- 材料使用仓外对象 historical-test-replay-s05b-v1。
- 运行只读复制后的新测试工作区，不引用主仓可变工作树。

## 结论

- 真实回放得到 38 项通过、2 项失败。
- 两项失败都因为 v1 少收 Z01d 覆盖诊断文件，不是业务断言失败。
- v1 原字节继续保留为失败证据，不能被 v2 的通过结果覆盖。

## 这张结论不能说明什么

S-06-B 已证明 v1 当前 payload 与固定清单逐文件一致；这只保住失败现场的字节身份，不把 38 过 2 败改写成通过，也不证明独立备份或永久可恢复。

## 以后怎么取件

日常只读本页。确实要复现时，先核卡片和仓外清单：

```bash
.venv/bin/python tools/experiment_artifact_retrieval.py check --card-id s05b-historical-replay-v1
```

再按已登记组合生成复制计划。这个命令只输出 JSON，不会创建目录或复制文件：

```bash
.venv/bin/python tools/experiment_artifact_retrieval.py resolve --card-id s05b-historical-replay-v1 --selection-id full-replay-payload
```

- `full-replay-payload`：在全新测试工作区复现 v1 的 38 项通过、2 项失败现场，不覆盖或改写旧失败证据。

真正复制仍要等后续单独施工；当前没有复制子命令。

## 使用边界

本卡只记录 v1 的历史结论和取件入口；不授权续跑、补包、移动、删除、恢复、迁移或启用 10MB 硬门。

来源：Codex
