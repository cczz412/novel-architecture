# 故障恢复与 Checkpoint

## 1. 沙箱重置

症状：旧 `/mnt/data/work` 不见、SQLite 不见、工具目录不见。

处理：

1. 不凭聊天回忆继续；
2. 找 Project Source current ZIP 或重新上传 Bootstrap；
3. 校验 package SHA；
4. 安全解压；
5. 恢复最近 checkpoint；
6. 重跑必要测试；
7. 记录 `SANDBOX_RESET_RECOVERY`。

## 2. Project Source raw 文件没挂载

1. 按文件名搜索；
2. 按预期 SHA 搜索；
3. 检查 Project Source UI；
4. 新开 Chat 复测；
5. 仍失败则把资产 ZIP作为当前聊天附件；
6. 不把 Source 不可见解释成内容不存在。

## 3. MD 语义检索失败

1. 精确提文件名 / heading / ID；
2. 检查 Source 版本；
3. 检查是否 Project-only 切换尚未生效；
4. 拆成主题文件；
5. 把 current 入口缩短；
6. 用代码层读取 raw MD 作机械对照，但不得冒充语义检索成功。

## 4. ZIP 太大或解压失败

- 拆模块；
- 冷材料另包；
- 去缓存/构建物；
- 用 delta；
- 记录丢弃清单；
- 不静默截断。

## 5. 依赖失败

- 输出缺失包、版本、ABI；
- 检查 wheelhouse；
- 不尝试无限联网；
- 使用 vendor fallback；
- 无 fallback 就 `BLOCKED_DEPENDENCY`。

## 6. Chat 太长

在旧 Chat：

1. 生成 `CHAT_CHECKPOINT.md`；
2. 生成 workspace manifest；
3. 打 `CHECKPOINT.zip`；
4. 下载；
5. 把稳定 handoff 保存为 Project Source；
6. 新 Chat 从 current Source + checkpoint 恢复。

## 7. 下载链接失败

- 确认结果 ZIP 已生成；
- 在沙箱 `testzip`；
- 输出绝对路径和 SHA；
- 重建更小 ZIP；
- 仍失败则拆成少量结果包；
- 不只在聊天里粘完整报告替代机器结果。

## 8. Model switch 异常

若切模型后 workspace 不见：

- 记 `MODEL_SWITCH_RESET`；
- 不重新解压后伪报“切换保持”；
- 从切换前 checkpoint 恢复；
- 继续任务，但把模型切换持久性标为 FAIL。
