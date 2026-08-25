---
name: external-handoff
description: >
  Prepares this repo's ChatGPT Pro review ZIP/prompt or Deep Research prompt after a
  stay-local vs Pro vs Deep Research gate. Use when a Cursor window considers 外发,
  ChatGPT Pro, Deep Research, Deep Search, review pack, chatgpt_review_pack, or
  handing CZ a ZIP/prompt. Do not use for ordinary repo edits, Codex browser send,
  NVM investigation packets, or treating Parallel/Firecrawl auto-research as ChatGPT
  Deep Research.
---

# Cursor 外发交接

给 **Cursor 窗口**用。说白了：先判断要不要出门、出门走哪条；真要出门就按本仓打包器打 ZIP、写 Prompt，交到 CZ 手上就停。

这不是 Codex 用户 Skill `$chatgpt-review-cycle` / `$deep-research-handoff` 的副本。Codex 继续用那两份。这里不写进 `.agents/skills/`。

Cursor 要以 **本仓库根**（GitHub clone 的 `novel-architecture/`）为工作区才会自动吃到这份 Skill。外壳镜像目录不会加载它。

## 什么时候用 / 不用

**用**：本仓任务要外发 ChatGPT Pro／普通 ChatGPT 独立外审，或 ChatGPT Deep Research／Deep Search；或你已经在准备 ZIP／Prompt。

**不用**：普通改仓库；本地读文件就能核清；CZ 没要外发；NVM 调查包；让浏览器代发；把 Parallel／Firecrawl 自动研究当成 ChatGPT Deep Research。

本 Skill **不能**扩大授权：不上传、不发送、不改正式合同、不把回包当项目真源。

## 1. 先过闸门

本地已经能核清 → 继续在 Cursor 干，不为显得谨慎而外发。

候选方向后果差不多、改了也回得来 → 不要升级成昂贵外援。

| 真正缺什么 | 走哪条 | 别误会成 |
|---|---|---|
| 本地材料已经齐，缺独立高推理：复杂关系、批量结果、样本、表单、反例 | **ChatGPT Pro**（独立外审） | 不是去网上找论文 |
| 本地再读也补不上：论文、官方文档、大厂做法、竞品、反例，而且答案会改路线 | **Deep Research／Deep Search** | 不是把本地包再审一遍 |
| 两条都缺 | **拆成两批** | 两套问题、两套材料，不能混成一次外发 |

能用脚本做完的计数、格式、一致性检查，先在本地做。

机械工作先问自己：便宜助手／Read／grep／普通网页搜索能不能核清。能核清就标 `继续本地`。CZ 点名 ChatGPT Deep Research 时，仍准备那条 Prompt，不要偷偷改成 Parallel 自动研究。

闸门结论只能是：`继续本地` / `ChatGPT Pro` / `Deep Research` / `两边拆批` / `先问 CZ`。

## 2. 外发前写判断卡

```text
必须决定什么：
候选方向（至少两个真正不同的）：
各方向已有证据 / 最可能错在哪：
已经核对过的本地材料：
为什么 Cursor 继续读解决不了：
外部需要回答什么，什么证据才够排除或保留某个方向：
回来之前必须暂停的施工／改票／改合同：
路线：继续本地 / ChatGPT Pro / Deep Research / 两边拆批
```

缺判断卡不准打包。

## 3. ChatGPT Pro：ZIP + Prompt

禁止手搓压缩包、禁止复用旧 zip。只走本仓打包器。

先读：

- [外审打包说明](../../../config/review_pack/README.md)
- [项目适配页](../../../config/review_pack/CHATGPT_REVIEW_SOP.md)（差量页，不是总控）
- [路线表](../../../config/review_pack/routes.json)

命令在仓库根执行：

```bash
uv run --locked python tools/chatgpt_review_pack.py --list-routes

uv run --locked python tools/chatgpt_review_pack.py \
  --route <route-id> \
  --layers current_truth,current_route,upstream_evidence \
  --dry-run
```

`--dry-run` 零写入。正式打包还要本轮明确的打包授权，然后再跑不带 `--dry-run` 的同一条（接续轮才加 `--external 槽名=/回包路径`）。

没有合格 route 就先补最小 route，不准拿 `surface`／`standard`／`deep` profile 包冒充正式外审。

**不准进包**：密钥、正式金标原文、答案锁箱、未授权作者正文、本机绝对路径。缺 required 材料就停，不准用摘要顶原件。

25 MB 只是提醒线。闭集确实更大时，获准再用 `--allow-large` 并写原因。

Prompt 可以要求：可下载 ZIP，根目录放完整 Markdown；约定时用 CSV／JSONL。推荐模型档位写给人看，不要替 CZ 点发送。

同一只读 ZIP 可给 1～5 个独立侧面，每个侧面独立 Prompt 和回包身份；1～5 是本流程范围，不是平台并发保证。

## 4. Deep Research／Deep Search：只写研究问题

发给 Deep Research／Deep Search 的那份正文，**只能是研究问题本身**。

每窗一个主问题。只写：背景、真正要回答的问题、范围、截止日期、来源优先级、要核对的冲突、不能越过的结论边界。可以要求重要结论带来源、区分直接证据和类比、说明适用范围和反例。

🔥 **那份要粘贴出去的正文里，不要出现任何回件形态。** 连「不要按某某方式交回」也不要写。研究质量可以写，交回来长什么样一句都不要写。

本地怎么保存、和 ChatGPT Pro 那条线怎么分开，只写在你给 CZ 的说明里，不要写进 Deep Research 正文。

现成稿在 `config/review_pack/prompts/`。沿用前先通读：凡是在规定交回长什么样的句子，删掉再交。

## 5. 交到 CZ 手上就停

按路线分开交：

- ChatGPT Pro：交本仓打包器产出的材料、Prompt、回执路径，加上判断卡和推荐档位。
- Deep Research／Deep Search：只交判断卡 + 一份可直接粘贴的研究问题正文。不要把打包说明写进那份正文。

到此停止：不打开 ChatGPT，不上传，不点击发送，不轮询回复。CZ 说「你来发」也一样停，说明这份 Skill 不代发。

`TEMP/` 产物默认不进 Git。

## 6. 回包只是顾问材料

只收 CZ 明确给的路径或附件。原样放 `TEMP/`，不改原文。

回来后对判断卡：哪些候选被排除、哪些仍成立、来源能不能打开、和当前真源／合同冲不冲突。证据仍分不出高下就继续停，交 CZ，不因为「已经外发过」就拍板。

没有本地跟进授权就保存原件后停止。
