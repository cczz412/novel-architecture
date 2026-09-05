# 打开人话结果卡

**入口：[打开人话结果卡](打开人话结果卡.html)**

把 ZIP 完整解压后，双击同名 HTML，或用浏览器打开。不需要 Python、服务器、数据库或联网。看完一张，点浏览器“返回”即可换另一张。

GitHub 网页通常显示 HTML 源码，不等于本地网页预览。请在解压后的文件夹里打开，别只从压缩软件里释放一个 HTML。入口与旁边的 `samples/` 要一起保留。

三张卡分别是：没有活库时的缺口页；带传闻／怀疑、误信、未证实的夹具样张；两条已发生条目的夹具样张。

## 这版做了什么

只加一页打开入口。三张卡逐字节复制自 `main@9c2fb958` 的 `work/ccz142_current_candidate_read_preview_r01/samples/`，没有重算、改写或增加事实条目。副本放在本目录，是为了让只有这个 ZIP 的人也能打开，避免链接指向包外缺失的文件。

这是一份固定版本的离线副本，不随活库或未来的 main 自动更新。`SOURCE_SAMPLES.json` 记来源版本、原路径、Git blob SHA-1 和 SHA-256；检查脚本只验证网页文件，不读取候选库。以后来源样张变化时，要重新核对版本与副本，不能把新旧卡混用。

卡上保留 `FIXTURE_ONLY`、`GAP_NO_LIVE_STORE` 和覆盖未接到 B02 的说明，不编密度／覆盖数字，也不加修补建议。入口不会判断现场有没有活库，更不会在缺库时拿夹具顶替一次真实读取。

状态：`CONSTRUCTION_DRAFT__NOT_MERGED`。唯一写集是新增本目录；没有改 proof／display／preview 源文件、writer、机读合同或产品代码。

## 已跑检查与未完成项

| 检查 | 本次结果 |
| --- | --- |
| 定向静态 pytest | 33 通过 |
| 自带副本 self_check | 通过，3 张副本校验一致 |
| 对照来源切片 self_check | 通过；切片已用在线 main 的 Git blob 值核对 |
| 浏览器内存渲染 | 4 通过，桌面／窄屏 × 启用／禁用脚本；页面资源请求为 0 |
| 浏览器本地文件打开与往返 | 4 失败，均在首次打开时收到 `ERR_BLOCKED_BY_ADMINISTRATOR`；本环境管理策略禁止导航，尚未验收 |
| Ruff | 未运行成功：本环境没有 Ruff，未下载或安装 |
| Python 语法编译检查 | 3 个文件通过，不生成字节码 |

**内存渲染不是双击验收。** 渲染测试把 HTML 放入空白页面，只验证内容与布局，没有打开 `file://` 或点完链接。`evidence/` 中的两张截图也只属于这类证据。没有修改浏览器管理策略，也没有把被拦的四项改成通过或跳过。

实际环境是 Python 3.13.5／pytest 9.0.2。仓库锁定 Python 3.12.12／pytest 9.0.2／Ruff 0.15.22，本次未跑锁定环境；完整回执见 `TEST_RECEIPT.json`。

## 给本地验收者的命令

以下命令只给开发验收用。普通看卡的人不用执行。

在仓库根目录，用已备好的锁定环境运行。`--offline` 会阻止临时下载依赖；缺依赖就停，不会自动联网补齐。

检查静态入口：

```bash
uv run --locked --offline python -B -m pytest -p no:cacheprovider -q work/ccz142_current_candidate_read_entry_r01/test_current_read_entry.py
```

检查副本，并与仓库里三张源样张逐字节比较：

```bash
uv run --locked --offline python -B work/ccz142_current_candidate_read_entry_r01/self_check.py --source-root .
```

检查 Python 代码格式和常见错误：

```bash
uv run --locked --offline ruff check --no-cache work/ccz142_current_candidate_read_entry_r01
```

本机已有 Playwright 和 Chromium 时，跑真实本地文件打开检查：

```bash
uv run --locked --offline python -B -m pytest -p no:cacheprovider -q work/ccz142_current_candidate_read_entry_r01/test_entry_browser.py::test_offline_file_links_without_repo_or_store
```

只检查内存渲染，不能拿它顶替上一项：

```bash
uv run --locked --offline python -B -m pytest -p no:cacheprovider -q work/ccz142_current_candidate_read_entry_r01/test_entry_browser.py::test_memory_render_only
```

浏览器依赖不在这次写集里；测试不会安装依赖或下载浏览器。缺依赖时显示 SKIP，不能记成验收通过。

## 人工打开验收

将本目录单独复制到带中文与空格的文件夹，不放仓库和数据库。断网后双击入口，依次打开三张卡并返回。缺口页应有 `GAP_NO_LIVE_STORE` 且没有事实条目；两张夹具卡应保留 `FIXTURE_ONLY`，类型样张应有传闻／怀疑、误信、未证实。所有卡仍说明覆盖未接 B02。

没有改仓库首页或全局导航，因为不在写集里。包根目录说明和本 README 都给了直达入口；不能把这项描述成“仓库首页已接入口”。

来源：ChatGPT
