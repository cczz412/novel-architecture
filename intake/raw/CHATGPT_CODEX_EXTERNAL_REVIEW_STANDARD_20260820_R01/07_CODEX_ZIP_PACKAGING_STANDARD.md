# 本地 Codex ZIP 打包合同

## 1. 包类型

| Profile | 用途 | 是否自包含 | 典型载体 |
|---|---|---:|---|
| `PROJECT_SOURCE_SEMANTIC` | 跨 Chat 语义检索 | 是 | MD/JSON/CSV 平铺 |
| `PROJECT_SOURCE_ASSET` | 跨 Chat 完整资产 | 是 | ZIP |
| `CHAT_BOOTSTRAP` | 新 Chat 开工 | 是 | ZIP |
| `CHAT_DELTA` | 同 Chat 增量更新 | 否，绑定父 SHA | ZIP |
| `INDEPENDENT_REVIEW` | 冻结输入独立复核 | 是 | ZIP |
| `RESULT` | ChatGPT 回本地 | 是 | ZIP |

## 2. Bootstrap 包

推荐结构：

```text
PACKAGE_ID/
├─ 00_READ_ME_FIRST.md
├─ 01_TASK.md
├─ 02_SCOPE_AND_AUTHORITY.md
├─ 03_CURRENT_BASELINE.json
├─ MANIFEST.json
├─ SHA256SUMS.txt
├─ source/
├─ contracts/
├─ tests/
├─ fixtures/
├─ expected/
├─ tools/
├─ vendor/
├─ wheelhouse/
└─ receipts/
```

`00_READ_ME_FIRST.md` 必须写：

- 唯一任务；
- 输入身份；
- 读包顺序；
- 可执行/不可执行权限；
- 结果目录和回包格式；
- 失败如何记录；
- 预计解压大小和内存。

## 3. Delta 包

```text
DELTA_ID/
├─ 00_DELTA_READ_ME.md
├─ DELTA_MANIFEST.json
├─ changed/
├─ added/
├─ deleted_paths.txt
├─ receipts/
└─ SHA256SUMS.txt
```

Delta MUST：

- 声明 `parent_package_id` 和 `parent_package_sha256`；
- 只对 staging 应用；
- 应用后重算完整工作区 manifest；
- mismatch 时强停，不猜父版本；
- 不直接覆盖 Project Source current。

## 4. Independent review 包

独立外审必须：

- 冻结输入；
- 不携带前一审查聊天结论，除非它本身是审查对象；
- 把正式事实、候选建议、历史报告分目录；
- 说明证据优先级；
- 不要求 ChatGPT 通过 Project memory 补缺文件。

## 5. 结果包

见 `09_PROMPT_AND_RESULT_CONTRACT.md`。

## 6. Manifest 合同

`MANIFEST.json` 每项至少：

```json
{
  "path": "contracts/C7.md",
  "bytes": 12345,
  "sha256": "...",
  "role": "FORMAL_CONTRACT",
  "status": "CURRENT"
}
```

包级至少：

```json
{
  "package_id": "...",
  "profile": "CHAT_BOOTSTRAP",
  "version": "R01",
  "parent_package_id": null,
  "created_at": "...",
  "authority": "ADVISORY_ONLY",
  "estimated_extracted_bytes": 0,
  "estimated_peak_ram_bytes": 0,
  "files": []
}
```

## 7. 大小和拆包

### MUST 拆包

- 单 ZIP 接近 512 MB；
- 解压后预计超过常规 8 GiB；
- 峰值 RAM 预计超过 2.5 GiB；
- 文件超过 10,000 个；
- 一个包混了多个无关任务；
- 需要不同权限或不同审查者。

### 拆包方式

按：

- 模块；
- 权力身份；
- 热/冷材料；
- 语义层/资产层；
- baseline/delta；
- 真实数据/合成 fixture。

## 8. 可重现 ZIP

SHOULD：

- 路径排序；
- 固定时间戳；
- 标准化权限；
- UTF-8 文件名；
- 不携带 `__MACOSX`、`.DS_Store`、缓存、`.git` 对象（除非审查 Git 历史）；
- 生成 `BUILD_RECEIPT.json`。

工具：`15_TOOLS/deterministic_zip.py`。

## 9. 禁止内容

- 真实 API key / token / 私钥；
- 未经授权的作者数据；
- 本地绝对路径作为唯一引用；
- Mac `.venv`；
- Mac native `node_modules`；
- Docker image 作为普通 Chat 必需依赖；
- 需要公网才能完成的安装步骤；
- 旧 current 与新 current 混在同一路径且无身份。
