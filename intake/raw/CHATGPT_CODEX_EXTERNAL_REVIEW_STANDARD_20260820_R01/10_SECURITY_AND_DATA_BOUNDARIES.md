# 安全、隐私与数据边界

## 1. Project-only 的真实边界

Project-only 是上下文隔离，不是独立账号或物理租户：

- 项目外 saved memories / conversations 不参与；
- 项目内容不用于项目外聊天记忆；
- 同一 Project chats 仍可作为上下文；
- Library、Web、Apps、账号设置和模型权限仍存在。

所以严格外审仍要在 Prompt 禁止未授权来源。

## 2. 密钥

MUST NOT 把以下内容放进 ZIP / Project Sources：

- API key；
- OAuth refresh token；
- SSH private key；
- `.npmrc` / `.pypirc` 凭据；
- 云账号 credentials；
- 长期 cookie；
- 数据库生产密码。

原因不只是“本次沙箱没网”。能力和工具会变化，密钥暴露面不应依赖当前网络阻断。

## 3. Archive 安全

处理外部 ZIP 前 MUST 检查：

- 绝对路径；
- `..`；
- Windows 盘符 / 反斜杠歧义；
- symlink；
- 重复/大小写冲突路径；
- 文件数；
- 单成员和总解压大小；
- 压缩比 / zip bomb；
- CRC；
- 嵌套深度；
- 隐藏 `.env`；
- 可执行文件。

使用 `15_TOOLS/safe_extract_zip.py`，先 staging，再原子切换。

Python 官方也提醒，处理不可信 archive 时必须验证路径，防止 path traversal。

## 4. 权限和真实作者数据

外审包只包含当前任务需要的最小材料。对真实小说、作者私有 Canon、未公开稿件：

- 先确认外发许可；
- 不把别的作者数据混入；
- 不用真实材料做默认 fixture；
- 不把结果用于训练，除非有独立许可；
- 导出时保留来源、版本和可见范围。

## 5. 数据保留

官方说明 Project 文件通常保留到 Project 被删除；Library 文件有自己的管理入口。但本地工程仍 MUST 保存正式原件和结果：

- ChatGPT 不是唯一备份；
- Project 删除不应销毁本地真源；
- RESULT.zip 当场下载；
- 本地按正式保留/删除政策处理。

## 6. 连接外部 App

需要 Drive/GitHub/其他 App 时另立任务，记录：

- 授权范围；
- 读取主体；
- 文件版本；
- 是否同步；
- 是否允许写入；
- 结果如何回本地。

不允许因为 App 可用就绕过本地 current 和权限边界。
