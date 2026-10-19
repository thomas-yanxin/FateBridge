# FateBridge

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![CI](https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml)

FateBridge 是一个可在本地运行的 Python 后端能力库，把八字、紫微、传统占术、西方占星与风水规则组织成可调用、可复算、带来源的计算接口。应用通过 REST 接入，Agent 通过 MCP 调用，脚本通过 CLI 运行；当前版本为 **0.1.0**。

当前提供 **86 个业务 REST 路由**、**87 个 FastMCP 工具**；中央目录含 88 条记录，CLI 可执行其中87条。三端共用领域计算，名称和请求形态见 [三端能力边界](docs/api-reference.md#24-三端能力边界)。完整 **13 family / 87 工具** 清单见 [算法覆盖矩阵](docs/algorithm-coverage.md)。

## 从这里开始

| 你的目标 | 入口 |
| --- | --- |
| 在 Codex 中直接咨询 | [Codex 使用指南](docs/codex-guide.md) |
| 安装并发起第一次调用 | [快速入门](docs/getting-started.md) |
| 接入应用或 Agent | [接入指南](docs/agent-guide.md) · [API 参考](docs/api-reference.md) |
| 按问题选择工具或场景技能 | [场景路由](docs/scenario-routing.md) · [9 个 Onda 技能](skills/README.md) |
| 修改代码、规则或文档 | [开发指南](docs/development-guide.md) · [贡献指南](CONTRIBUTING.md) |
| 升级旧版调用或排查故障 | [迁移指南](docs/migration.md) · [故障排除](docs/troubleshooting.md) |

完整导航和各文档职责见 [文档中心](docs/README.md)。

## 能力概览

| 领域 | 计算内容 |
| --- | --- |
| 八字与双人关系 | 命盘，事业、财运、婚姻等九项专题，双人配合、宿曜相性 |
| 时运与历法 | 大运、流年、流月、流日、流时、节气与农历 |
| 中国术数与占卜 | 紫微、奇门、六壬、太乙、金口诀、梅花、六爻及本地技法 |
| 西方占星 | 本命与流派盘、关系盘、返照、行运、主限及时主等推运 |
| 风水空间 | 八宅、金锁基础砂水、年星、玄空历史宅盘，以及按事实分层的布局与物件审查 |

风水的输入、来源与适用范围见 [家居风水](docs/fengshui.md)；各工具精度、依赖与未覆盖项目见 [算法覆盖](docs/algorithm-coverage.md)。

## 快速开始

需要 Python 3.10+，当前 CI 覆盖 3.10–3.13。通过 PyPI 安装：

```bash
python -m pip install fatebridge==0.1.0
```

源码开发安装需要 Git，以下为 macOS / Linux 示例；Windows 和全部配置见 [快速入门](docs/getting-started.md#安装)。

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

### CLI：安装后直接调用

CLI 不需要启动服务。以下命令使用虚构体验资料：

```bash
fatebridge describe bazi_birth --detail input
fatebridge bazi_birth --birth-year 1990 --birth-month 5 --birth-day 15   --birth-hour 10 --birth-minute 30 --gender 男 --birth-place 北京   --birth-timezone Asia/Shanghai --fields bazi_birth.day_master --strict-fields
```

### REST：启动后发起请求

```bash
API_HOST=127.0.0.1 fatebridge-api
```

另开一个终端执行：

```bash
curl http://localhost:8010/health
curl -X POST http://localhost:8010/api/cn/bazi/birth   -H 'Content-Type: application/json'   -d '{"birth_year":1990,"birth_month":5,"birth_day":15,"birth_hour":10,
       "birth_minute":30,"gender":"男","birth_place":"北京",
       "birth_timezone":"Asia/Shanghai","use_true_solar_time":true}'
```

交互文档位于 `http://localhost:8010/docs`。独立命盘数据位于 `bazi_birth`；配置了 `FATEBRIDGE_API_KEYS` 时，业务请求还需密钥头。监听地址默认 `0.0.0.0`，本机使用以上命令限制到 `127.0.0.1`；配置与部署说明见 [快速入门](docs/getting-started.md#配置环境变量) 和 [安全策略](SECURITY.md)。

### MCP：交给 host 启动

MCP 使用 stdio。先运行 `fatebridge doctor --mcp --scenario onda-shiye`，再按返回的绝对路径命令注册。完整 Codex 配置、虚构对话和连接检查见 [Codex 使用指南](docs/codex-guide.md)。

## 调用与结果

- 用 `fatebridge discover --family bazi` 或 REST `/api/tools?detail=summary&family=bazi` 筛选能力，再读取所选工具契约。已知 Schema 时可直接调用。
- 成功结果默认带 `run_metadata`，记录工具、时间和计算口径；复现还需保存原输入与运行环境。
- 用 `fields` 控制响应体积，`strict_fields=true` 拒绝无效路径。MCP 默认预算 8192 字符，超限后通过 `result_delivery` 读取同一次结果。
- **需要完整 JSON 或全部时间线时，首次调用 `fields=null`**，再按 [完整结果交付](docs/agent-guide.md#完整结果交付与同次导出) 保存与校验；摘要投影无法恢复未选字段。

字段、错误与端口差异见 [API 参考](docs/api-reference.md)，Python / JavaScript 客户端例子见 [接入指南](docs/agent-guide.md)。

## 开发与验证

源码位于 `src/fatebridge/`；中央目录装配领域声明，REST / MCP / CLI 共用服务与算法。[架构说明](docs/architecture.md) 介绍调用链与模块职责。

安装开发依赖后运行：

```bash
uv pip install -e ".[dev]"
python scripts/check_docs.py
python -m pytest -q tests/test_doc_tool_counts.py tests/test_scenario_routing_coverage.py
```

代码变更还需运行领域测试与 CI 对应检查，命令见 [开发指南](docs/development-guide.md)。提交方式见 [贡献指南](CONTRIBUTING.md)，版本变化见 [CHANGELOG](CHANGELOG.md)。

## 使用范围与许可

计算验证关注历法、规则与数值的一致性；传统解释及分数是文化参考，分数不代表现实成功概率。规则来源、三端一致、黄金快照和真实模型对话分别提供不同证据。

核心星盘支持本地星历与近似路径，应检查实际返回的 `chart_profile.ephemeris_model` 和 `run_metadata.engine_is_approximate`；西占推运、事件与生命周期工具缺少后端依赖时明确报错。项目包含后端、CLI 与技能资料，前端与部署控制由接入方提供。

代码采用 [Apache-2.0](LICENSE)，第三方组件见 [NOTICE](NOTICE)；星历数据单独获取，见 [星历数据与精度](docs/getting-started.md#星历数据与精度)。
