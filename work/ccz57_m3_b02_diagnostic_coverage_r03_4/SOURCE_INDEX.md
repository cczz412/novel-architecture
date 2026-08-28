# B-02 来源索引

## 工程真值

- GitHub 仓库：`cczz412/novel-architecture`
- GitHub Issue：[#191](https://github.com/cczz412/novel-architecture/issues/191)
- Linear：`CCZ-130`
- 开工基线：`main@905346f56cd51259c15a9517ead1517227c1719a`

## A 与 B-01 准入

- A 精确受审 head：`9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26`
- A merge：`019df751641533c7de4d56aa38f50747fb564036`
- GLOBAL-A record hash：`91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af`
- GLOBAL-A 准入原始文件 SHA-256：`5d326296d2028f87772f1f24836b4885bfe395909a7e74aa331870d5023aa7c0`
- B-01 精确受审 head：`24a89a4a705138308f2db5a9f94dc09e74bb4c28`
- B-01 merge：`905346f56cd51259c15a9517ead1517227c1719a`
- B-01 merge/readback 文件 SHA-256：`98ab63f1b8ff34844ba346839cb7471aeb784d400282f12c3d4fb686a5183138`
- B-01 merge/readback 内部 hash：`81544ef084908480acd3466bbd167f577cdd700de7e70967e782204fc67974a6`
- B-01 合并对象目录：`../ccz57_m3_b01_candidate_version_r03_4/OBJECT_SHAPES.json`
- B-01 对象目录文件 SHA-256：`90ea6b165f4e509ff3e267f494afc83ddad408c54abb6a006be0c15decad1ccd`
- 本目录的 `A_INTERFACE_ADMISSION_RECEIPT.fixture.json` 与 `B01_MERGE_READBACK_RECEIPT.fixture.json` 是上述两份仓库外回执的 byte-identical 固定副本，只用于离线准入夹具，不是新产品对象。

## 蓝图与合同

- R03.4 蓝图 SHA-256：`8db5f9acb8ada30e929af4e710790bb36c6058023928de513757465a0fa43cd2`
- R03.4 文档自校验 hash：`c3203ef73c9d0fc23f843673df0325b95d4d6c52cb752e8c9b543c80dc1151b0`
- B-02 合同候选 R02 SHA-256：`189a225fc2484309696cbf4cd81c596548b8b815c33a803c644279ea756a62c7`
- B-02 文档身份：`CCZ57-M3-B02-R02-CANDIDATE`
- 四种对象的 `contract_version` 与 `record_contract_version`：`r03.3-candidate`

## 身份边界

R03.4 和 B-02 R02 是获准施工所依据的候选合同，不是产品运行证明。B-01 merge/readback 是仓库外施工证据，不是 M3 产品不可变对象或 `RecordRef`。两份 `.fixture.json` 只是原始 bytes 的离线证据副本，不增加对象、writer 或依赖边。本目录只使用合成固定夹具，不读取小说正文。

来源：Codex
