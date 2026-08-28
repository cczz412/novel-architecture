# CCZ-57｜M3 B-04 来源索引

## 工程真值

- 仓库：`cczz412/novel-architecture`
- GitHub Issue：`#193`
- 施工 base／current main：`2307831d7b62eb57992d3be368a3a635ebb8b7b7`
- A merge：`019df751641533c7de4d56aa38f50747fb564036`
- B-01 merge：`905346f56cd51259c15a9517ead1517227c1719a`
- B-02 merge：`2307831d7b62eb57992d3be368a3a635ebb8b7b7`
- B-02 tree：`1a8d5100602dfdbeb5f8bfe811b7377172a62c42`

## 施工合同

- R03.4 蓝图文件 SHA-256：`8db5f9acb8ada30e929af4e710790bb36c6058023928de513757465a0fa43cd2`
- R03.4 文档自校验 SHA：`c3203ef73c9d0fc23f843673df0325b95d4d6c52cb752e8c9b543c80dc1151b0`
- B-04 R02 合同文件 SHA-256：`f4517034cadf97465e2cdc7e59c19bb5ec738633f782154587b0f018a63c7bf5`
- B-03 R02 合同文件 SHA-256：`06104630259b00b3b090fa490acbe3ff465628ff6da924d6fa8d1a230a61f50c`
- B-03 R02 7-ref catalog SHA：`955bad28eb36ec70eb827b400640e00c5825041042e0d879960101d992761b93`

## 合并回执 fixture

- `A_INTERFACE_ADMISSION_RECEIPT.fixture.json`：从已合并 A 准入原件固化；文件 SHA 由 self-check 重算；
- `B01_MERGE_READBACK_RECEIPT.fixture.json`：B-01 合并回读原件；内部 receipt hash `81544ef084908480acd3466bbd167f577cdd700de7e70967e782204fc67974a6`；
- `B02_MERGE_READBACK_RECEIPT.fixture.json`：B-02 合并回读原件；文件 SHA `8244b608b412c2dbb4f31c5ea4a926a4c9cd4cff47fda87786dd79efb2adbdb2`，内部 receipt hash `e19e8b40d529fa62ae0f6f43bb5ad10fcaa1ddc1211fe711f5290c91c44993c4`。

这些回执只证明施工准入，不是新的 M3 产品对象。

## 合成 fixture

`OBJECT_SHAPES.json` 收录：

- B-03 R02 的 7 个完整 RecordRef；
- B-04 两条合法路线的三个原件和 PatchPreview 固定向量；
- F-25～F-29 的 SourceSlice 专用负例。

全部 fixture 都是合成数据，不含真实小说正文，不证明模型准确率或作者验收。

来源：Codex
