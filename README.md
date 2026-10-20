<p align="center">
  <img src="asserts/fatebridge-banner.png" alt="FateBridge：银色莫比乌斯环与星轨横幅" width="100%">
</p>

<h1 align="center">FateBridge</h1>

<p align="center">
  <strong>面向应用与 AI Agent 的传统术数与占星计算引擎</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/fatebridge/"><img src="https://img.shields.io/pypi/v/fatebridge.svg" alt="PyPI"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python"></a>
  <a href="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml"><img src="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#接入-agent">接入 Agent</a> ·
  <a href="#接入应用">接入应用</a> ·
  <a href="docs/README.md">文档中心</a> ·
  <a href="#参与贡献">参与贡献</a>
</p>

FateBridge 将八字、紫微、中国占术、西方占星与风水规则组织成可在本地运行的 Python 计算工具。通过 **MCP** 为 Agent 提供计算依据，通过 **REST** 接入应用，也可以用 **CLI** 在终端直接调用。

---

## 核心特性

- **一套计算支持三种入口**：REST、MCP 与 CLI 共用领域服务和工具目录，提供结构化输入、输出与错误信息。
- **按问题组织 Agent 能力**：Onda 技能覆盖事业、财务、关系、学习等主题，按本轮问题选择依据、时间范围与解读方式，追问复用已有结果。
- **保留计算口径**：成功结果附带 `run_metadata`，记录版本、有效时间及输入与结果摘要；结合原输入和相同运行环境复算。
- **适配模型上下文**：用 `fields` 选择需要的字段，用 `strict_fields` 检查路径；超出 MCP 响应预算时，通过 `result_delivery` 读取同一次计算结果。

## 支持的能力

| 领域 | 主要内容 |
| --- | --- |
| 八字与双人关系 | 四柱命盘、事业与财务等九项专题、双人配合、宿曜相性 |
| 时运与历法 | 大运、流年、流月、流日、流时、节气与农历 |
| 中国术数与占卜 | 紫微、奇门、六壬、太乙、金口诀、梅花、六爻及本地技法 |
| 西方占星 | 本命与流派盘、关系盘、返照、行运、主限与时主等推运 |
| 风水空间 | 八宅、金锁基础砂水、年星、玄空历史宅盘，以及分层的布局与物件审查 |

当前提供 **86 个业务 REST 路由**、**87 个 FastMCP 工具**，覆盖 **13 family / 87 工具**。中央目录含 88 条记录，CLI 可执行其中 87 条；各端的名称与请求形态有差异，见[三端能力边界](docs/api-reference.md#24-三端能力边界)。逐工具的实现、精度与限制见[算法覆盖矩阵](docs/algorithm-coverage.md)。

## 快速开始

需要 **Python 3.10+** 与 [uv](https://docs.astral.sh/uv/getting-started/installation/)，当前 CI 覆盖 Python 3.10–3.13。

### 安装

从 PyPI 安装独立命令工具，当前版本为 **0.1.0**：

本页描述当前开发分支。PyPI `0.1.0` 是已发布版本，尚未发布的变更见 [CHANGELOG](CHANGELOG.md#unreleased)；体验最新技能与接口范围时，请使用[源码安装](#参与贡献)。

```bash
uv tool install fatebridge==0.1.0
```

安装后可使用 `fatebridge`、`fatebridge-api` 和 `fatebridge-mcp` 三个命令。需要运行当前仓库或修改源码时，使用[源码安装](#参与贡献)；Onda 技能随 Git 仓库分发，当前 wheel 不包含技能目录。

### 完成第一次计算

CLI 不需要启动服务。以下使用虚构资料，只返回日主的三个字段：

```bash
fatebridge bazi_birth \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem \
    bazi_birth.day_master.element bazi_birth.day_master.polarity \
  --strict-fields
```

响应中的业务数据如下，另附 `run_metadata` 计算回执：

```json
{
  "bazi_birth": {
    "day_master": {
      "stem": "庚",
      "element": "金",
      "polarity": "阳"
    }
  }
}
```

继续探索工具与输入契约：

```bash
fatebridge discover --family bazi
fatebridge describe bazi_birth --detail input
```

安装与 Windows 说明、环境变量和星历配置见[快速入门](docs/getting-started.md)。

## 接入 Agent

MCP 使用 **stdio**，由 Codex、Claude 或 Cursor 等 host 启动本地子进程。先诊断安装与连接，例如从事业场景开始：

```bash
fatebridge doctor --mcp --scenario onda-shiye
```

诊断会验证依赖、独立 MCP 进程、工具发现、资源读取和一条虚构计算。Codex 用户可执行输出中的 `codex.add_command` 注册连接；它使用当前安装环境的绝对路径。其他 host 可按其配置格式填写返回的 `codex.config` 中的 `command`、`args` 与 `env`。

注册后在新聊天中确认工具可见，即可用日常语言提问，例如：

> 请用 FateBridge 看看我的事业。我正在考虑换工作，也想了解自己适合承担哪类职责。以下是虚构体验资料：男，公历 1990 年 5 月 15 日上午 10:30，北京出生，按当地钟表时间记录。请分析 2026 年，用普通人能懂的话讲清依据。

`--scenario onda-shiye` 将连接限制在事业场景的工具范围；需要其他主题时调整场景或清空筛选并重启连接。[Onda 技能](skills/README.md)按生活主题、问题任务与时间范围组织咨询，专题综合可使用多视角，追问保留已有相关结果。

完整注册步骤、配置格式与对话示例见 [Codex 使用指南](docs/codex-guide.md)；其他 host 的配置见 [Agent 接入指南](docs/agent-guide.md#fastmcpagent-host)。

## 接入应用

启动本机 REST 服务。以下为 macOS / Linux 命令，Windows 配置见[快速入门](docs/getting-started.md#配置环境变量)：

```bash
API_HOST=127.0.0.1 fatebridge-api
```

在另一个终端发起请求：

```bash
curl http://localhost:8010/health

curl -X POST http://localhost:8010/api/cn/bazi/birth \
  -H 'Content-Type: application/json' \
  -d '{
    "birth_year": 1990, "birth_month": 5, "birth_day": 15,
    "birth_hour": 10, "birth_minute": 30, "gender": "男",
    "birth_place": "北京", "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": true
  }'
```

`/health` 返回 `{"status":"healthy"}`，命盘请求的业务数据位于 `bazi_birth`，另附计算回执。浏览器打开 [Swagger UI](http://localhost:8010/docs) 查看请求 Schema 并试调接口。

监听地址默认 `0.0.0.0`，上述命令将其限制为本机。启用 `FATEBRIDGE_API_KEYS` 后，业务请求还需发送 `X-API-Key`（默认头名）；配置与部署边界见[快速入门](docs/getting-started.md#配置环境变量)和[安全策略](SECURITY.md)。Python 与 JavaScript 调用示例见[接入指南](docs/agent-guide.md)。

## 结果与复现

保留原输入与 `run_metadata`，并核对时区、太阳时策略、分析时间和引擎版本。回执描述的是计算口径，复现还需要相同的实现、数据与运行环境。

- **只取需要的内容**：使用 `fields` 投影结果，设置 `strict_fields=true` 拒绝无效字段路径。
- **完整导出从首次调用开始**：需要完整 JSON 或全部时间线时，首次调用设置 `fields=null`，保留默认响应预算。MCP 默认预算为 8192 字符，超限后通过 `result_delivery` 读取同一 run；摘要投影不能恢复未选字段。详见[完整结果交付与同次导出](docs/agent-guide.md#完整结果交付与同次导出)。
- **按实际返回判断精度**：核心星盘支持本地星历与近似路径，核对 `chart_profile.ephemeris_model` 和 `run_metadata.engine_is_approximate`。西占推运、事件与生命周期工具缺少所需后端依赖时明确报错。星历数据单独获取，见[星历数据与精度](docs/getting-started.md#星历数据与精度)。

## 文档导航

| 你想做什么 | 阅读入口 |
| --- | --- |
| 安装、配置与排错 | [快速入门](docs/getting-started.md) · [故障排除](docs/troubleshooting.md) |
| 在 Codex 中咨询或接入 Agent | [Codex 指南](docs/codex-guide.md) · [Agent 接入指南](docs/agent-guide.md) |
| 查工具、字段与三端差异 | [API 参考](docs/api-reference.md) · [算法覆盖矩阵](docs/algorithm-coverage.md) |
| 按问题选择工具和技能 | [场景路由](docs/scenario-routing.md) · [Onda 技能](skills/README.md) |
| 理解工具、回执与结果状态 | [核心概念](docs/concepts.md) |
| 理解专题规则与来源 | [八字判定说明](docs/bazi-assessment.md) · [家居风水](docs/fengshui.md) · [双人评分](docs/compatibility-scoring.md) |
| 理解架构、开发或升级 | [架构说明](docs/architecture.md) · [开发指南](docs/development-guide.md) · [迁移指南](docs/migration.md) |

全部文档及维护职责见[文档中心](docs/README.md)，版本变化见 [CHANGELOG](CHANGELOG.md)。

## 参与贡献

欢迎改进算法、接口、测试、文档和场景技能。源码开发使用锁定的 uv 环境，无需手动激活虚拟环境：

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge list
```

纯文档改动可先运行：

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q \
  tests/test_doc_tool_counts.py tests/test_scenario_routing_coverage.py
```

代码改动还需运行领域测试及 CI 对应检查，详见[开发指南](docs/development-guide.md)。提交与 PR 流程见[贡献指南](CONTRIBUTING.md)。报告问题或提出功能建议请到 [Issues](https://github.com/thomas-yanxin/FateBridge/issues)；安全问题按 [SECURITY.md](SECURITY.md) 私下报告。

## 使用范围与许可

FateBridge 的计算验证关注历法、数值与所选规则的一致性。传统解释与分数用于文化参考，分数不代表现实成功概率，软件测试通过也不证明预测有效性。咨询不提供生死寿命、灾祸断言、临床诊断治疗与医疗择时，传统健康内容不作为医学结论；详见[咨询硬边界](skills/_shared/safety-boundaries.md)。

项目提供后端、CLI 与技能资料，前端和部署由接入方负责。代码采用 [Apache-2.0](LICENSE)，第三方组件与来源见 [NOTICE](NOTICE)，依赖和星历数据遵循各自许可。

---

<p align="center">
  <img src="asserts/fatebridge-logo-square.png" alt="FateBridge 莫比乌斯环 Logo" width="72" height="72">
</p>

<p align="center">
  <a href="#fatebridge">返回顶部 ↑</a>
</p>
