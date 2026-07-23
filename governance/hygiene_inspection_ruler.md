# 常检尺子定标（磁盘观感主刀）

来源：支线瘦身批件③；云端代拍常检口径；**文档级**，不改任何 check 逻辑与 `.py`。

## 主刀

✅ **磁盘观感**（打开工作树不觉得拖）为主。  
Git 跟踪与 `.git` 历史为辅读数，不拿「整仓 `du -sh .` 一个数」判胖瘦。

## 常检三行读数（自此固定）

在仓库根执行：

```bash
# 1) 除 TEMP 的工作树磁盘（主观感）
du -sh --exclude=TEMP . 2>/dev/null || du -sh $(ls -A | grep -v '^TEMP$' | grep -v '^\.git$') 

# 更稳（macOS）：
python3 - <<'PY'
from pathlib import Path
import os
root=Path('.')
skip={'.git','TEMP'}
n=0
for p in root.iterdir():
    if p.name in skip: continue
    for r,_,fs in os.walk(p):
        for f in fs:
            try: n+=(Path(r)/f).stat().st_size
            except: pass
print(f'except_TEMP_MB={n/1024/1024:.1f}')
PY

# 2) Git tracked 体量
git ls-files -z | xargs -0 ls -l 2>/dev/null | awk '{s+=$5} END{printf "tracked_MB=%.1f files=%d\n", s/1024/1024, NR}'

# 3) 外置旁仓另算（不计入主仓胖瘦）
du -sh ../小说架构_外置仓/archive_batch_* 2>/dev/null
```

| 读数 | 含义 | 判胖时 |
|---|---|---|
| **除 TEMP 磁盘** | 主仓「看得见的业务树」 | 主刀 |
| **Git tracked** | 克隆／协作相关 | 辅 |
| **外置旁仓** | `小说架构_外置仓/…` | **另算，不并进主仓单数字** |

❌ 废弃：只用 `du -sh .`（含 TEMP＋有时心理上还想塞旁仓）当唯一胖瘦判决。

## 与 Phase0／1 关系

- TEMP 已 ignore：清 TEMP＝观感，不等于 tracked 下降。  
- 冷 runs stub：除 TEMP 读数下降；tracked 仅当原文件曾入库才会变。  
- `.git` 历史瘦身＝P3，另拍。

## 入口

本说明挂在治理区常驻文档；刷新 `INDEX.md` 时不覆盖本文件。
