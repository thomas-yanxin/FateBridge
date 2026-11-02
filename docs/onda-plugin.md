# Onda 可安装插件

本仓库根的 `plugin.json` 与 `mcp.json` 按当前 OpenAI 支持的 Agent Plugins 格式声明 Onda 技能与本地 stdio MCP。插件同时携带本次源码的计算后端、数据和锁定依赖清单，插件版本独立于 Python 包版本。

## 构建与验证

在源码的锁定环境中执行：

```bash
uv run --locked --extra dev python scripts/build_onda_plugin.py --output dist/fatebridge-onda-0.2.0.zip
uv run --locked --extra dev python -m pytest -q tests/test_onda_plugin.py
```

输出路径须尚不存在，避免覆盖旧包。构建器保留 `skills/`、兄弟 `_shared/`、分支参考及本地文档依赖，并加入 `src/fatebridge/`、包数据、`pyproject.toml` 与 `uv.lock`。运行时依赖由 `uv export --locked --no-dev --no-emit-project` 导出至 `backend-requirements.txt`，保留版本、平台标记和散列。`backend-source.json` 记录后端文件与依赖清单的 SHA-256，可核对安装内容。

构建器拒绝包外或不存在的引用；不复制虚拟环境、运行时私密配置或缓存。不把单一技能文件夹单独拷贝后当作完整包。

## 本地安装

先安装 uv，并确认客户端启动环境能找到 `uvx`。解压到用户选择的插件目录。按客户端的本地插件或 marketplace 机制指向该目录；操作方式见 [OpenAI 插件包装文档](https://developers.openai.com/plugins/build/plugins)。仓库作者不需要代用户修改个人配置。

本插件通过 `uvx --python 3.12 --isolated --with-requirements "${PLUGIN_ROOT}/backend-requirements.txt" --from "${PLUGIN_ROOT}" fatebridge-mcp` 运行包内后端，工作目录也指向 `${PLUGIN_ROOT}`。这是官方支持的插件根目录占位符。启动不依赖本机仓库路径、已有 FateBridge 安装或旧版 PyPI 后端；首次仍需联网下载 Python 和目标平台的锁定依赖，不是离线安装包。

从源码目录手动注册开发服务仍使用 doctor 输出，详见 [MCP 部署](mcp-deployment.md)。根 `mcp.json` 中的依赖导出文件在插件构建时产生，因此安装应选择构建并解压后的插件包。可分发包内不放私有 Hosted URL、令牌或本机绝对路径。

在源码项目已发现同名技能、或已注册同名 MCP 时，选择使用项目入口或插件入口，避免重复安装。安装后新开聊天，确认技能及 MCP 工具存在，再用 [Codex 指南](codex-guide.md)的虚构资料实际调用。包结构、引用和 stdio 计算通过，不等于所有宿主、操作系统或公网部署都已验收。

当前没有发布到公共插件目录，也没有远程 HTTPS MCP 端点；本地插件不冒充 ChatGPT 网页端可连接的公网服务。公开分发的要求见官方[桌面插件说明](https://developers.openai.com/plugins/deploy/desktop-only)。
