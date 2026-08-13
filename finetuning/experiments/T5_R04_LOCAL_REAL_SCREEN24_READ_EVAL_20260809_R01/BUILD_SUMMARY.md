# LOCAL_REAL_SCREEN24｜READ 三臂构建说明

这24题来自24本不同的真实小说，只作本机 Demo 筛选考试。当前权利状态仍是 **LOCAL_EVAL_ONLY_RIGHTS_PENDING**：不进入 TRAIN36，不上传，不发布。

- 题目：24题／24本
- 共同候选事实：280条
- 独立姓名诊断：2题（仅 C06、C18）
- READ-1、READ-2、READ-4 每行都只有 system+user，没有 assistant 或 gold
- 三臂逐题共用同一 system、编号目标和证据允许表，只改变前部只读范围
- READ-2 每侧最多180个 Unicode 字符；READ-4 不额外重复 halo
- 长度只按模型可见 Unicode 字符粗计，没有加载 tokenizer

## 模型可见字符粗计

| arm | min | median | max | mean |
|---|---:|---:|---:|---:|
| READ-1-TARGET | 1603 | 1923.5 | 2299 | 1944.833 |
| READ-2-HALO180 | 1854 | 2264.5 | 2659 | 2255.792 |
| READ-4-FULL-CHAPTER | 3113 | 3938.0 | 5774 | 4234.958 |

## 已登记题源异常

- C03：目标尾部有疑似站点数字；保留原文但不计为事实。
- C06：春婵/春蝉按同一人物异体处理；共同答案仍用目标可见称呼。
- C07：缓存编号为0003，文件标题写第二章；只记录，不改路径或坐标。
- C09：目标尾部有疑似站点注释符号；保留原文但不计为事实。
- C13：目标内夹有明显站外/读者插话；保留原文但不计为事实。
- C18：目标尾部有晋江数字/注释噪声；保留原文但不计为事实。
- C22：目标尾部有晋江数字/注释噪声；保留原文但不计为事实。
- C24：目标内有晋江注释符号噪声；保留原文但不计为事实。

## 输出 SHA-256

- `REAL24_SOURCE_INDEX.jsonl`：`0fe7ecb1649b93e4faab3d253d8904bee7f1a7a3e6f7f0fbb8b8e722c405de97`
- `REAL24_TXX_MAP.jsonl`：`9a52d321981b7c9c32b8b422ef6b96a4c89b5581b04a1385513c5403f75f915a`
- `REAL24_GOLD_24.jsonl`：`234963eee8c1024ccbdf7d0866e73d89e963ba7eaf21a0fbd1e3126c817641b4`
- `REAL24_ENTITY_DIAGNOSTIC.jsonl`：`7501d382ec3a21692ef1e9672fe4cdf89a490fd5e7e0d86e56b2d940b1ba5b4f`
- `READ_1_TARGET_EVAL24.jsonl`：`73423ace73ce60e497db6f0acf25d39bba3bfdccfc6d7a82abf9d8510d6157c0`
- `READ_2_HALO180_EVAL24.jsonl`：`a12f1f5cb1adfed4958418bfa8373af52b6305fdef64122c9bf02e3338c77e85`
- `READ_4_FULL_CHAPTER_EVAL24.jsonl`：`350799084dbc15791bc3b46a669552aec2da7920bfa39c8a3a110e1cbe431d4f`

这批结果只供本地 Demo 对比，不是最终盲考或生产泛化证明。

来源：Codex
