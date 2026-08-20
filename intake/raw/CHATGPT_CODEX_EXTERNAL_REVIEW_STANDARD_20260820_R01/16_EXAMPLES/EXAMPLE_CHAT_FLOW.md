# 示例：一个阶段的 Chat 流程

```text
Project-only Project
  ├─ Sources: Router + Current + Codebase.zip
  └─ Chat: M8-M11 Review Cycle R03
       1. 发现 Source ZIP，校验 SHA
       2. 安全解压到 /work/base
       3. 建 SQLite index
       4. 跑基线
       5. Pro 做高难审查
       6. checkpoint
       7. 同 Chat 切 Extra High 继续整理
       8. 上传 Delta_R02.zip
       9. staging 应用 + 回归
      10. 生成 RESULT.zip，立即下载
      11. 本地 Codex 验收
      12. 阶段结束后新开 Chat
```
