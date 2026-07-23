# ChatGPT／外审 · 审仓打包

定期把「结构 + 流程 + 近停证据」打成 zip，上传 ChatGPT（或同类）审仓库乱不乱、测试流程、近几轮效果差在哪。

## 一键

```bash
cd /Users/a1234/挣钱/小说架构
python3 tools/chatgpt_review_pack.py              # 默认 standard ≈ 常审
python3 tools/chatgpt_review_pack.py --profile deep
python3 tools/chatgpt_review_pack.py --dry-run
```

产出目录：`TEMP/chatgpt_review_packs/<profile>_<时间戳>/`  
主文件：`chatgpt_review_*.zip`＋包内 `00_READ_ME_FOR_REVIEWER.md`

## 三档

| profile | 干什么 |
|---|---|
| `surface` | 只要活面（结构／治理／代码／测试） |
| `standard`（默认） | 活面 + Z94 runs/reports + Z83 关键 retry + **全林票据摘要** |
| `deep` | 再加整棵 Z83／Z91／Z93 runs 等（更大） |

## 纪律

- 不带 `TEMP/`、密钥、正文语料
- zip 默认 ≤25MB；超限须 `--allow-large`
- 外发读盘 ≠ 把 `runs/`／`reports/` 重新进 Git
