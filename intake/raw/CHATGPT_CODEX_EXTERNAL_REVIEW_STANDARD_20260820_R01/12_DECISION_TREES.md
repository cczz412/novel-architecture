# 决策树

## A. 要不要建 Project？

```text
是否是长期、会反复外审的同一工程？
├─ 否 → 普通新 Chat + 自包含 Bootstrap ZIP
└─ 是 → Project
       └─ 是否要避免账号其他聊天串线？
          ├─ 是 → Project-only（默认）
          └─ 否 → Default memory，明确接受外部上下文
```

## B. 资料放 Project Source 还是聊天附件？

```text
新 Chat 是否要长期直接语义检索？
├─ 是 → 平铺 MD/JSON/CSV Project Source
└─ 否
   └─ 是否要跨 Chat 保留完整目录/代码资产？
      ├─ 是 → ZIP Project Source
      └─ 否 → 当前 Chat 附件
```

通常答案是：**核心 MD + 完整 ZIP 同时放。**

## C. 很多报告能不能压成一份？

```text
只是归档/运输/全文批处理？
├─ 是 → 可以一个或多个 ZIP
└─ 否，未来要经常问内容
   → Router + 主题 Digest + Ledger 平铺
   → 原报告另放 ZIP
```

## D. 继续旧 Chat 还是开新 Chat？

```text
是否同一阶段、同一 baseline、需要旧 workspace？
├─ 是 → 继续旧 Chat，发 Delta
└─ 否
   └─ 是否做独立复核或大版本切换？
      ├─ 是 → 新 Chat，冻结 Bootstrap
      └─ 否 → 先 checkpoint，再决定
```

## E. 能不能靠 Project memory 交接？

```text
信息是“项目大概在做什么”吗？
├─ 是 → memory 可以辅助
└─ 否，是 RUN_ID/SHA/current/状态/JSON？
   → 必须文件化，禁止只靠 memory
```

## F. 能不能临时安装依赖？

```text
依赖已经在包内 / wheelhouse / vendor？
├─ 是 → 离线安装
└─ 否
   └─ 需要公网下载？
      → 不合格包；回本地补依赖后重打
```

## G. 模型切换要不要新 Chat？

```text
只是换推理模型，仍是同一阶段？
├─ 是 → 同 Chat 切，先 checkpoint
└─ 否，任务/阶段也变了 → 新 Chat
```

## H. 外部 API 怎么办？

```text
是否必须真实调用 API？
├─ 否 → 普通 Chat 离线执行
└─ 是 → 本地 Codex / Codex Cloud / 专用环境
       → 不把 API key 塞普通 Chat ZIP
```
