# TRAIN48 长度校准教材构建说明

这批只是本地 Demo 长度校准材料。S6/M6来自6篇项目原创章；L6来自另3篇原创章，只作READ1未见密度小考且永不进训练。真实 LOCAL_REAL_SCREEN24 没有进入训练文件。

- 完整原创章：9篇
- 新增题：12题（S6+M6）
- 新增事实：48条；合并后 TRAIN48 共762条事实
- L6 READ1未见密度小考：6题、18条Gold，事实数0、0、2、3、5、8；只生成READ1无答案请求
- L6只判断低事实密度时是否少输出，禁止据此下READ1/READ2/READ4上下文长度结论
- S6事实数：0、0、1、2、2、3
- M6事实数：4、5、6、7、8、10
- 18个新目标段汉字粗计范围：551–734
- 每篇两段不重叠，中间至少隔一个完整自然段
- 新旧材料及9个新故事之间的28字连续文本复用命中：0
- 原TRAIN36三份文件SHA未变；TRAIN48前36行逐字复用旧文件
- 审收问题与修复：独立审收后，控制窗定点补正2条S6事实和3条事实表述；冻结正文未修改。

## 完整序列 token 范围

只为确认不超过4608训练上限而读取本地冻结 tokenizer；没有加载模型或做推理。

| arm | min | median | max | mean |
|---|---:|---:|---:|---:|
| READ-1-TARGET | 1339 | 2066.0 | 2772 | 2072.167 |
| READ-2-HALO180 | 1616 | 2245.5 | 2962 | 2279.771 |
| READ-4-FULL-CHAPTER | 2705 | 3402.0 | 4161 | 3374.042 |
| L6_READ1_PROMPT_ONLY | 1226 | 1421.5 | 1666 | 1431.5 |
| TRAIN36_READ1_PROMPT_ONLY_REFERENCE | 1186 | 1483.5 | 1829 | 1489.472 |

## 三份 TRAIN48 SHA-256

- `READ_1_TARGET_TRAIN48.jsonl`：`87d241eee1d37569682b82d858b8fb7848c2e45b91092c7fc2bc99dec9297a98`
- `READ_2_HALO180_TRAIN48.jsonl`：`7862d4528415f50e1c60836104ecf3c38d2ecb8b81c145468e1beb4321dc8d03`
- `READ_4_FULL_CHAPTER_TRAIN48.jsonl`：`2e03521faf8d0c0828bae564433b7cbc117ece0da7983f7b4880ce262c9b601e`

## L6 READ1 未见密度小考 SHA-256

- `READ_1_TARGET_L6_EVAL.jsonl`：`e96b8b5abb565f63e9bd3c2354c3a2a7366a4a646fb262379844c3fc32fb2503`

本轮没有训练、推理或API调用，也没有修改TRAIN36、REAL24、Notion、Git或现役指针。

来源：Codex
