# MCP 部署指南

通过 MCP，可以让 AI 助手调用 FateBridge 的本地计算。完成接入需要选择传输方式、安装服务并配置客户端，最后确认一次实际调用；后续升级和停用也沿用同一套部署方式。客户端与模型负责理解问题和解释结果，Onda 技能提供按主题组织咨询的指引。

先按下表选择部署方式，再完成对应的安装与连接验证。人物示例均为虚构资料；项目能力见[项目首页](../README.md)，接口集成见 [Agent 接入指南](agent-guide.md)。

## 选择部署方式

| 场景 | 方式 | 进程由谁管理 | 客户端填写什么 |
| --- | --- | --- | --- |
| Codex、Claude Desktop、Cursor 本机使用 | stdio | 客户端启动与关闭 | Python 绝对路径和 `-m fatebridge.mcp_server` |
| 支持 URL 的客户端、远程机器 | Streamable HTTP | 你或服务管理器 | `http://127.0.0.1:8011/mcp`，远程可通过 SSH 隧道 |
| 普通应用 HTTP 调用 | REST，见[快速入门](getting-started.md) | 你或服务管理器 | `http://127.0.0.1:8010/api/...` |

`fatebridge-mcp` 默认运行 stdio；HTTP 模式由 FastMCP runner 加载同一个应用。两者共享计算与 MCP 资源，REST 是另一套协议。无需同时启动三个入口。

## 安装与本地验证

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/)。选择一种安装方式，不混用解释器。

### 已发布的独立工具

```bash
uv tool install --python 3.12 fatebridge
fatebridge doctor --mcp
```

命令找不到时，执行 `uv tool update-shell` 并重开终端。doctor 的 `version` 是实际安装版本，`executable` 是该工具环境的 Python 绝对路径。wheel 包含工具与场景数据，不包含 Onda 技能文件。已发布包的文档以[对应 Git 标签](https://github.com/thomas-yanxin/FateBridge/tags)为准。

### 当前源码与 Onda 技能

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor --mcp
```

源码环境由 `uv.lock` 锁定，默认 Python 3.12。接入配置使用 doctor 返回的 `executable`，例如 `/absolute/path/to/FateBridge/.venv/bin/python`。无需先激活环境，也无需在另一个终端启动 stdio 服务。

两种方式均应检查 `ok=true` 和 `mcp.ok=true`。诊断从无关临时工作目录启动独立进程，执行初始化、工具发现、资源读取与一条虚构计算。失败时查看 `mcp.stage`、`error_type` 和 `server_stderr`，修复后在同一环境重试。该诊断不修改客户端配置，也不验证 HTTP 连接或当前聊天加载状态。

## 注册本地 stdio

[README](../README.md#本地-mcp由客户端启动-stdio-进程)提供可合并的 Codex TOML 和通用 `mcpServers` JSON。替换 `command` 为本次 doctor 的 `executable`，不要使用系统 Python、未展开的 `~` 或依赖激活的相对路径。

- Codex：编辑 `~/.codex/config.toml` 的 `[mcp_servers.fatebridge]`；也可执行 doctor 的 `codex.add_command`，二选一。详见 [Codex 指南](codex-guide.md#2-注册到-codex)。
- Claude Desktop：通过客户端的开发者设置打开 MCP 配置，合并 `mcpServers.fatebridge`；配置位置见 [MCP 官方本地接入说明](https://modelcontextprotocol.io/docs/develop/connect-local-servers)。
- Cursor：项目 `.cursor/mcp.json` 或用户 `~/.cursor/mcp.json`，条目使用 `"type": "stdio"`、`command`、`args` 和 `env`，见 [Cursor 官方说明](https://cursor.com/docs/context/mcp)。

不要将 TOML 粘进 JSON，或把整个 shell 命令塞进 `command`；参数分别放在 `args`。已有同名条目时修改该条目，保留其他 MCP 服务。

### Windows PowerShell

源码安装与诊断：

```powershell
git clone https://github.com/thomas-yanxin/FateBridge.git
Set-Location FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor --mcp
```

独立工具安装仍使用 `uv tool install --python 3.12 fatebridge`，然后运行 `fatebridge doctor --mcp`。doctor 的注册命令使用 POSIX shell 引号；PowerShell 用户应使用下方配置，或按 PowerShell 语法分别传参。

Codex TOML 可使用单引号保留 Windows 路径，不需要双写反斜杠：

```toml
[mcp_servers.fatebridge]
command = 'C:\path\to\FateBridge\.venv\Scripts\python.exe'
args = ["-m", "fatebridge.mcp_server"]
startup_timeout_sec = 30
tool_timeout_sec = 60

[mcp_servers.fatebridge.env]
FATEBRIDGE_MCP_FAMILIES = ""
FATEBRIDGE_MCP_SCENARIOS = ""
PYTHONUTF8 = "1"
```

Claude Desktop 的 JSON 要双写反斜杠；Cursor 使用同样结构并在条目内加入 `"type": "stdio"`：

```json
{
  "mcpServers": {
    "fatebridge": {
      "command": "C:\\path\\to\\FateBridge\\.venv\\Scripts\\python.exe",
      "args": ["-m", "fatebridge.mcp_server"],
      "env": {
        "FATEBRIDGE_MCP_FAMILIES": "",
        "FATEBRIDGE_MCP_SCENARIOS": "",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

CLI 虚构计算可用 PowerShell 续行符执行，反引号后不要留空格：

```powershell
uv run --locked --extra dev fatebridge bazi_birth `
  --birth-year 1990 --birth-month 5 --birth-day 15 `
  --birth-hour 10 --birth-minute 30 --gender 男 `
  --birth-place 北京 --birth-timezone Asia/Shanghai `
  --fields bazi_birth.day_master --strict-fields --no-include-snapshot-text
```

路径必须替换为本次安装的真实路径；`PYTHONUTF8=1` 使子进程使用 UTF-8。

## 工具范围、环境与技能

默认不筛选工具。可在客户端的 `env` 中明确设置：

| 目标 | `FATEBRIDGE_MCP_FAMILIES` | `FATEBRIDGE_MCP_SCENARIOS` |
| --- | --- | --- |
| 全部工具 | `""` | `""` |
| 事业咨询所需工具 | `""` | `"onda-shiye"` |
| 仅风水工具族 | `"fengshui"` | `""` |

筛选是服务端实际公开范围，两个变量取交集，错误名称或空交集会导致启动失败。可先执行 `fatebridge doctor --mcp --family fengshui --scenario ""` 验证该范围；源码用户加 `uv run --locked --extra dev`。`fatebridge scenarios` 和 `fatebridge discover --surface mcp` 可查场景与工具。限制工具只影响 MCP，不提供用户权限管理。

源码 MCP 启动时读取仓库根目录 `.env`，已有进程环境优先。GUI 客户端应通过 `env` 注入设置，独立工具安装不要依赖当前工作目录的 `.env`。自定义星历目录可加 `SE_EPHE_PATH`，下载步骤与精度检查见[星历说明](getting-started.md#星历数据与精度)。日志写 stderr，stdout 留给 stdio 协议；启动包装脚本也应遵守此约定。

[Onda 技能](../skills/README.md)与 MCP 进程分开加载。Codex 使用该源码仓库作为项目时，从 `AGENTS.md` 和 `.agents/skills/` 获取项目指导及技能入口；其他客户端需按自身机制加载 `skills/`。只安装 Python 包或连接远程 MCP，不会向客户端复制技能文件。

## HTTP 与远程部署

以下使用**当前源码的锁定环境**。在服务器安装仓库后，从仓库根目录运行：

```bash
uv run --locked --extra dev fastmcp run src/fatebridge/mcp_server.py:app \
  --transport http --host 127.0.0.1 --port 8011 --path /mcp
```

保持进程运行，MCP URL 为 `http://127.0.0.1:8011/mcp`。这是 FastMCP 的 Streamable HTTP transport，不是 REST。`fatebridge-mcp --transport http` 不是本项目入口支持的写法。runner 参数见 [FastMCP 官方文档](https://gofastmcp.com/deployment/running-server)。PowerShell 用户将命令写成一行，或将续行 `\` 改为反引号。

### 验证协议与计算

在同机另一个终端、仓库根目录运行以下脚本；它同时验证初始化、工具发现、资源读取与计算：

```bash
uv run --locked --extra dev python - <<'PY'
import asyncio
import json
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8011/mcp", timeout=30) as client:
        tools = await client.list_tools()
        await client.read_resource("fatebridge://catalog/summary")
        result = await client.call_tool(
            "bazi_birth",
            {
                "birth_year": 1990, "birth_month": 5, "birth_day": 15,
                "birth_hour": 10, "birth_minute": 30, "gender": "男",
                "birth_place": "北京", "birth_timezone": "Asia/Shanghai",
                "fields": ["bazi_birth.day_master"],
                "strict_fields": True, "include_snapshot_text": False,
            },
            raise_on_error=False,
        )
        if result.is_error:
            raise RuntimeError(result.structured_content)
        print("tools:", len(tools))
        print(json.dumps(result.structured_content, ensure_ascii=False, indent=2))

asyncio.run(main())
PY
```

成功时退出码 `0`，输出日主 `庚 / 金 / 阳` 与回执。Windows 将 `import asyncio` 到 `asyncio.run(main())` 的 Python 内容保存为 `verify_mcp.py`，执行 `uv run --locked --extra dev python verify_mcp.py`。该脚本要求公开 `bazi_birth`；筛选其他工具族时换成其可用工具。浏览器 GET `/mcp` 或普通 `curl` 的响应不能替代 MCP 协议验证。

### 远程接入

受信任用户可通过 SSH 转发访问服务器的回环监听。在**客户端机器**运行，替换登录名与服务器地址并保持终端打开：

```bash
ssh -N -L 8011:127.0.0.1:8011 user@server.example.com
```

此时客户端仍填写 `http://127.0.0.1:8011/mcp`。Codex 的 URL 条目如下，与 stdio 配置二选一；用单独名称可保留现有本地连接：

```toml
[mcp_servers.fatebridge_remote]
url = "http://127.0.0.1:8011/mcp"
startup_timeout_sec = 30
tool_timeout_sec = 60
```

也可执行 `codex mcp add fatebridge_remote --url http://127.0.0.1:8011/mcp`。支持 URL 的 JSON 客户端使用如下结构；以客户端当前格式为准：

```json
{
  "mcpServers": {
    "fatebridge_remote": {
      "url": "http://127.0.0.1:8011/mcp"
    }
  }
}
```

服务器端的进程环境决定公开工具与星历；客户端 URL 条目的 `env` 不会设置远程服务环境。云端客户端无法通过自己的 `127.0.0.1` 访问你电脑的隧道，需部署其可达且经过鉴权的 HTTPS MCP 服务。

### 常驻与公网边界

需要常驻时，由 systemd 等服务管理器运行安装环境的 `fastmcp` 绝对路径。例如 Linux 安装于 `/opt/FateBridge` 时，以下为 unit 模板，需先创建有权读取仓库、写入私有临时目录的 `fatebridge` 运行用户：

```ini
[Unit]
Description=FateBridge HTTP MCP
After=network.target

[Service]
Type=simple
User=fatebridge
WorkingDirectory=/opt/FateBridge
Environment=PYTHONUTF8=1
Environment=FATEBRIDGE_MCP_FAMILIES=
Environment=FATEBRIDGE_MCP_SCENARIOS=
ExecStart=/opt/FateBridge/.venv/bin/fastmcp run /opt/FateBridge/src/fatebridge/mcp_server.py:app --transport http --host 127.0.0.1 --port 8011 --path /mcp
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

将审查并调整后的 unit 保存为 `/etc/systemd/system/fatebridge-mcp.service`，运行 `sudo systemctl daemon-reload`、`sudo systemctl enable --now fatebridge-mcp`。用 `systemctl status fatebridge-mcp` 与 `journalctl -u fatebridge-mcp` 查看状态及日志。源码环境需在部署前创建，运行用户必须能访问该环境的实际 Python 路径；不要让 uv 管理的解释器仅能被部署管理员读取。macOS / Windows 可使用本机服务管理器运行同等命令。

上述服务没有 MCP 网络鉴权，保持回环监听并通过 SSH 使用。若要开放公网，需在 FastMCP 或前置网关实现客户端兼容的鉴权、TLS 与访问限制，并验证 MCP POST / GET / DELETE 和流式响应可通过；不能只转发普通 REST POST。**`FATEBRIDGE_API_KEYS` 只保护 REST，不保护此 MCP 服务。** 当前共享结果存储不提供多租户结果所有权隔离；不同信任边界应隔离运行用户与实例，详见[安全策略](../SECURITY.md)。

## 客户端验收与排错

1. 本地 stdio 运行 doctor；HTTP 使用上面的协议脚本，确认服务本身可用。
2. 保存客户端配置，重新加载连接；必要时重启客户端并打开新聊天。
3. 确认实际工具可见，使用 [README 的虚构提示](../README.md#确认客户端可用)完成一次真实调用。

| 失败现象 | 检查 |
| --- | --- |
| 找不到命令、模块或数据 | `command` 是否为 doctor 的实际 Python；安装目录是否移动；GUI 日志中的启动路径 |
| 初始化失败 | doctor 的失败阶段与子进程 stderr；JSON / TOML 格式；family / scenario 配置 |
| stdio 协议解析失败 | 包装脚本是否把普通日志打印到 stdout |
| 工具数量不符 | 服务启动环境的筛选、运行版本、是否重启了旧进程 |
| HTTP 连接拒绝 | HTTP 进程、监听端口、SSH 隧道与客户端所在机器 |
| HTTP 404 | 是否使用完整 `/mcp` 路径，是否误连 REST 的 `8010` |
| CLI 成功、聊天仍失败 | 当前聊天是否实际加载新连接；客户端工具调用错误与超时日志 |

日志与回执可能含个人资料，分享前脱敏。更多领域或输入错误见[故障排除](troubleshooting.md)。

## 升级、回退与停用

升级前记录 doctor 的版本、包路径、当前 Git 提交和客户端配置，保存仍需要的结果交付文件。

- PyPI 独立工具：执行 `uv tool upgrade fatebridge`；如需固定或回退到某个已发布版本，使用 `uv tool install --force fatebridge==<version>`，将占位符替换为确认过的版本。
- 源码：先确认 `git status` 并保留本地修改；跟踪主分支时执行 `git pull --ff-only`，再执行 `uv sync --locked --extra dev`。回退优先在独立目录检出已确认 tag / commit，并为该目录创建锁定环境，保留当前工作区。
- 重新运行对应协议检查，重启 stdio 连接或 HTTP 服务，再在新聊天验证工具。若解释器或目录改变，更新配置中的绝对路径。

停用 stdio 时删除或禁用客户端内对应服务条目并重载；手动 HTTP 服务用 Ctrl-C 结束，systemd 使用 `sudo systemctl disable --now fatebridge-mcp`，SSH 隧道用 Ctrl-C 结束。独立工具不再需要时可执行 `uv tool uninstall fatebridge`。停用和卸载不会代替你管理已导出的文件与客户端聊天记录。
