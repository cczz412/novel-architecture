# CCZ-142 点名身份写入库目录 R01｜来源索引

## 施工入口

- GitHub Issue：[点名身份入库 #301](https://github.com/cczz412/novel-architecture/issues/301)
- 开工基线：`main@4856209bdb2817c875474e3ae5baecae66f43f96`
- Linear 模块：[CCZ-142](https://linear.app/ccz/issue/CCZ-142)

## 直接读取的现行模块

- `work/ccz142_named_chapter_card_identity_r01/` 的 `drop_named_chapter_with_card_identity`
- `work/ccz142_named_chapter_txt_card_r01/` 的放行闸
- `work/ccz142_current_candidate_read_preview_r01/` 的 `show_current_html`

## 明确排除

- [PR #235](https://github.com/cczz412/novel-architecture/pull/235)
- sqlite schema、B01～B09 writer、金标正文、覆盖数字

来源：Cursor
