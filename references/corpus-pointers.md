# 样本指针（优书 · 正文不进仓）

正文真源：[corpus-downloads/](../corpus-downloads/)。

仓库只跟踪这一层相对指针：

```text
corpus-downloads -> .local/corpus-downloads
```

`.local/` 不进 Git。每台机器第一次使用时，把第二层指向自己的正文库：

```bash
cd /Users/a1234/挣钱/小说架构
mkdir -p .local
ln -s /你的/小说101-downloads .local/corpus-downloads
```

检查有没有接好：

```bash
test -d corpus-downloads && echo "正文库可读" || echo "请重建 .local/corpus-downloads"
```

这套二级指针保留所有既有 `corpus-downloads/...` 路径，同时避免 Git 记住某台机器的用户名和绝对路径。干净克隆后正文仍不会自动出现，这是“正文不进仓”的既定边界，不是仓库损坏。

名单出处：小说101 `structure/SAMPLE_REGISTRY.md`（FIT-24）。外发时选 1～3 本 × 几章即可。

| 主类 | 书 | 正文文件夹（可点） |
|---|---|---|
| 单主角升级 | 玄鉴仙族 | [玄鉴仙族/](../corpus-downloads/01_单主角升级线/玄鉴仙族/) |
| 群像多线 | 庆余年 | [庆余年/](../corpus-downloads/02_群像多线/庆余年/) |
| 多视角 | 道诡异仙 | [道诡异仙/](../corpus-downloads/03_多视角/道诡异仙/) |
| 悬疑信息差 | 十日终焉 | [十日终焉/](../corpus-downloads/04_悬疑信息差/十日终焉/) |
| 感情关系 | 庶女明兰传（知否） | [庶女明兰传…/](../corpus-downloads/05_感情关系/庶女明兰传（知否？知否？应是绿肥红瘦）/) |
| 系统关卡 | 全职高手 | [全职高手/](../corpus-downloads/06_系统关卡/全职高手/) |
| 世界规则 | 凡人修仙传 | [凡人修仙传/](../corpus-downloads/07_历史世界规则/凡人修仙传/) |
| 长伏笔 | 诡秘之主 | [诡秘之主/](../corpus-downloads/08_连载长伏笔/诡秘之主/) |

一般书／批量例子：需要时再从 [小说目录表.md](../corpus-downloads/小说目录表.md) 加，不进默认表。

---

## 书目介绍／调研材料

→ [book-meta/](book-meta/)  
正文仍只指针到 `corpus-downloads/`；不要把原文拷进 book-meta。

聊天里请用相对仓库根：`references/book-meta/`  
复制用（不当链接）：`/Users/a1234/挣钱/小说架构/references/book-meta/`
