# PR 标题草稿

feat: CCZ-142 #270 人话结果卡离线打开入口

# PR 正文草稿

Refs #270

状态：`CONSTRUCTION_DRAFT__NOT_MERGED`。这里只提供文字草稿，没有创建 PR。

从新增目录的 README 点“打开人话结果卡”，或双击同名 HTML，即可看已有样张，不需要 Python、数据库或服务器。页面只负责打开文件，不运行候选读取逻辑。

三张卡逐字节复用 main@9c2fb958 中已合入的预览样张。离线副本都留在唯一写集内，来源版本和校验值见 `SOURCE_SAMPLES.json`。保留夹具身份、缺口标记和覆盖未接线说明，不增加修补建议。

唯一写集：新增 `work/ccz142_current_candidate_read_entry_r01/**`。没有修改已有源文件、writer、机读合同或产品代码。

检查命令和实际回执见本目录 README 与 `TEST_RECEIPT.json`。33 项静态测试、4 项内存渲染测试通过；4 项本地文件打开测试被浏览器管理策略拦截，Ruff 未安装。本地仍须补做双击验收、锁定环境检查和合入前禁区检查；内存渲染或 SKIP 都不能顶替文件打开验收。不转 Ready、不合并；不触碰另一份 authority 草稿。

来源：ChatGPT
