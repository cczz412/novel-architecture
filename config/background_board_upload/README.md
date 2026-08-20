# 三块背景板一键打包 SOP

✅ 这套工具会把“当前产品共同背景板＋当前外部报告背景板＋当前原子需求与验收背景板”编译成一个单层 ZIP，放到仓库的 `TEMP/background-board-upload/`。你只要运行一条命令，再自己解压或上传。

## 一键制作

在仓库根目录运行：

```bash
uv run --locked python tools/build_background_board_upload_zip.py
```

它会自动做这些事：

- 产品文件统一加 `PRODUCT_R版本__` 前缀。
- 报告文件统一加 `REPORT_R版本__` 前缀；报告的日常背景页使用 `REPORT_R版本__BG__` 前缀。
- 原子需求文件统一加 `ATOMIC_R版本__` 前缀。
- 所有材料放在 ZIP 同一层，不依赖上传平台保留文件夹结构。
- 同一背景板内的 Markdown 链接会改指向平铺后的文件名。
- 图片和其他附件只改文件名，原始字节不改。
- `.DS_Store`、`__MACOSX`、`._*`、`Thumbs.db`、`__pycache__`、工具缓存和编辑器临时文件不会进入 ZIP；原背景板里的文件不会被删除。
- 自动生成总导航、逐文件清单和 SHA-256 校验表。
- 同样的输入会得到字节完全一致的 ZIP。

## 成品怎么用

成品名会带三块背景板的真实版本，例如：

```text
TEMP/background-board-upload/CHATGPT_FLAT_BACKGROUND_BOARDS_PRODUCT_R14_REPORT_R01_ATOMIC_R03.zip
```

解压后先读 `00_CHATGPT_MASTER_ROUTER.md`。它会告诉 ChatGPT：

- 哪些文件是产品共同背景；
- 哪些文件是外部报告证据；
- 哪些文件是原子需求与验收参考；
- 平时该读哪些短主题页；
- 需要核证据时怎样追 claim、source 和报告登记。

你也可以不解压，直接把 ZIP 交给支持 ZIP 的读取工具。若平台会把附件平铺显示，前缀已经能防止三个 `00_READ_ME_FIRST.md` 撞名。

## 怎么核对现有 ZIP

```bash
uv run --locked python tools/build_background_board_upload_zip.py check
```

看到 `PASS_BYTE_IDENTICAL`，表示现有 ZIP 与当前三块背景板重新编译出的字节完全一致。

看到报错就停下，不要手工覆盖同名 ZIP。最常见的原因是：背景板内容变了，但版本号或当前入口还没一起升。

## 背景板升级后怎么接

外部报告背景板会自动读取 `references/external-knowledge-base/CURRENT.json`，所以 R02 转正后不用改打包工具。

原子需求与验收背景板会自动读取 `references/atomic-expectations/CURRENT.json`，所以后续 R04 转正后也不用改打包工具。当前指针缺版本、包身份、入口、清单或清单 SHA 漂移时，打包会直接停止。

产品共同背景板也不用手改版本。工具会扫描 `references/shared-context/`，只认名字以 `NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_` 开头、并且以 `_R数字` 收尾的目录，再从入口和清单都齐全的目录里选择版本数字最大的一个。

例如 R14 完整落盘后，下一次会自动使用 R14。`R14_DRAFT`、缺入口、缺清单或清单身份不匹配的半成品不会被选中。若同一个最高版本出现两个完整目录，工具会停下让人处理，不会猜一个。

三块背景板都只运输清单登记的文件。多出来的普通文件不会被悄悄带走；清单自身和产品板按自校验规则排除的构建回执属于机器身份文件，不算漏登记的正文材料。

## 这套工具不会做什么

- 不改 R14、R01、R03 或以后版本的正式原件。
- 不删除正式目录里的缓存文件，只在运输包里排除。
- 不把报告意见升级成产品决定。
- 不上传 ChatGPT，不写 Notion，不提交 Git，也不调用模型。
- 不覆盖同名但字节不同的旧 ZIP；背景板正式升版后会自然生成新文件名。

配置入口是 `config/background_board_upload/sources.json`。除背景板正式升版外，不要为一次上传临时改它。

来源：Codex
