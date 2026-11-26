# FateBridge

<p align="center">
  <img src="asserts/fatebridge-banner.png" alt="FateBridge banner with a silver Möbius loop and star trails" width="100%">
</p>

<p align="center">
  <strong>Inspectable Chinese metaphysics, astrology, and psychometrics calculations for AI applications</strong>
</p>

<p align="center">
  <a href="README.md">简体中文</a> · English
</p>

<p align="center">
  <a href="https://pypi.org/project/fatebridge/"><img src="https://img.shields.io/pypi/v/fatebridge.svg" alt="PyPI"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python"></a>
  <a href="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml"><img src="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
  <a href="https://www.modelscope.cn/mcp/servers/thomas/FateBridge"><img src="https://img.shields.io/badge/ModelScope-MCP%20Server-624AFF.svg" alt="ModelScope MCP Server"></a>
</p>

FateBridge provides local Chinese metaphysics, astrology, and psychometrics calculations for AI applications through **MCP, REST API, and CLI**. Results include structured facts, time conventions, and execution receipts. [Method references](docs/interpretation/README.md) document result reading, sources, and scope. Your application supplies the model conversation and interface; no LLM API key is required by the calculation service.

## Capabilities

| Domain | Implemented scope | Details and limits |
| --- | --- | --- |
| BaZi and relationships | Four pillars, nine topics, cross-chart contacts, luck periods through hourly timing | [Coverage](docs/algorithm-coverage.md) · [Method reference](docs/interpretation/README.md) |
| Chinese systems and divination | Zi Wei, Qi Men, Liu Ren, Jin Kou, Tai Yi, Mei Hua, Liu Yao, He Luo, and Canping | [Zi Wei](docs/ziwei.md) · [Coverage](docs/algorithm-coverage.md) |
| Astrology | Western natal, relationship, timing, and event charts; Jyotish, Guolao, Sukuyo, and other schools | [Sukuyo](docs/sukuyo.md) · [Astrodice](docs/astrodice.md) · [Coverage](docs/algorithm-coverage.md) |
| Human Design | Dual moments separated by 88° solar longitude, gates and lines, channels, type, and authority | [Human Design reference](docs/human-design.md) |
| Feng Shui | Eight Mansions, basic sand/water rules, annual/monthly stars, historical Xuan Kong charts, layouts, and measured workstations | [Home assessment](docs/fengshui.md) · [Consultation guide](docs/interpretation/fengshui/consultation.md) |
| Psychometrics | IPIP 50-item Big Five factor markers (Goldberg 1992 public domain) | [Coverage](docs/algorithm-coverage.md#212-psychometrics--心理测量量表implemented) |

The current source exposes **91 business REST routes**. Two MCP tools (`discover_tools` and `run_calculation`) provide access to **91 capabilities** across **12 families**. The central catalog contains 91 entries, with 91 available through the CLI. All three interfaces share the same domain calculations; see [interface boundaries](docs/api-reference.md#22-三端能力边界) and the [algorithm coverage matrix](docs/algorithm-coverage.md).

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first. Python 3.10+ is required; the source checkout defaults to 3.12, and CI tests 3.10–3.13. Choose one installation method.

### Released package

```bash
uv tool install --python 3.12 fatebridge
fatebridge doctor
```

This provides `fatebridge`, `fatebridge-api`, and `fatebridge-mcp`. If they are not on your PATH, run `uv tool update-shell` and reopen the terminal.

### Current source

For current branch features or development:

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor
```

This README describes the development branch. For a released package, use the documentation at its [Git tag](https://github.com/thomas-yanxin/FateBridge/tags); pending changes appear in the [Changelog](CHANGELOG.md#unreleased). The Python wheel contains calculation code and rule data. Method scope and result-reading guidance are in the [method references](docs/interpretation/README.md).

### Run a calculation

The fictional example below runs in a macOS / Linux terminal without starting a service. Source users should prefix `fatebridge` with `uv run --locked --extra dev`. See the [Windows example](docs/mcp-deployment.md#windows-powershell) for PowerShell.

```bash
fatebridge bazi_birth_chart \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem bazi_birth.day_master.element \
    bazi_birth.day_master.polarity
```

On success, the command exits with `0` and returns the day master `庚 / 金 / 阳` (Geng / Metal / Yang) plus `run_metadata`. `--detail compact` is the default across all interfaces; pass `--detail audit` for complete payloads and method evidence. Discover other tools and their inputs with:

```bash
fatebridge discover --family bazi
fatebridge discover bazi_birth_chart
```

## Connect an assistant or application

| Goal | Connection | Guide |
| --- | --- | --- |
| Local Codex, Claude Desktop, or Cursor | Client-managed MCP stdio process | [MCP setup](docs/mcp-deployment.md#注册本地-stdio) |
| MCP client accepting a URL | Independent Streamable HTTP service | [HTTP and remote deployment](docs/mcp-deployment.md#http-与远程部署) |
| Web, mobile, or backend application | Independent REST service | [Start REST](docs/getting-started.md#启动-rest-并检查状态) · [Integration guide](docs/agent-guide.md) |
| Scripts and batch jobs | One-shot CLI execution | [Getting started](docs/getting-started.md) · [Requests](docs/examples/README.md) |

For local MCP, run `fatebridge doctor --mcp` and register the absolute Python path returned as `executable`. The client manages the stdio process. After saving the configuration, verify tool visibility and a real call in a new chat. Reload the MCP connection after upgrading.

Start REST locally with `API_HOST=127.0.0.1 fatebridge-api`. The default port is `8010`, with interactive API documentation at `/docs`. The default bind address listens on all interfaces; review [configuration](docs/configuration.md) and [security](SECURITY.md). REST API keys do not protect MCP.

## Read and verify results

- **Inputs and time:** use confirmed information, including time zone, location, and analysis time. Do not fill an unknown birth hour with a default or example. Read the actual time convention returned by each method.
- **Summary and full output:** `detail=compact` is the default on all three surfaces; project task-specific `fields` (strictly validated) for targeted views, or pass `detail=audit` with `fields=null` for complete JSON and method evidence. See [output controls and result reading](docs/agent-guide.md#输出控制与结果读取).
- **Ephemeris and precision:** an installed Python library does not establish that external data files were used. Check the actual model, source, and approximation flag. See [ephemeris setup](docs/ephemeris.md).
- **Evidence and limits:** software regression, classical sources, and runtime dependencies are reported separately. A `partial` status limits its own layer. See [core concepts](docs/concepts.md).

## Development and contributions

The package uses a Python `src` layout. FastAPI, FastMCP, and CLI adapters call shared execution and domain services through a central `ToolSpec` catalog. See [architecture](docs/architecture.md). Dependencies are declared in [pyproject.toml](pyproject.toml), with development resolutions pinned in [uv.lock](uv.lock).

Contributions to documentation, algorithms, interfaces, and tests are welcome. Follow [CONTRIBUTING](CONTRIBUTING.md) and select checks from the [development guide](docs/development-guide.md). See the [documentation writing guide (Chinese)](docs/development-guide.md#文档写作). Start documentation-only validation with:

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q tests/quality/test_documentation_integrity.py tests/quality/test_doc_tool_counts.py
```

[Documentation maintenance](docs/development-guide.md#文档维护与验证) covers interface and generated-contract synchronization. Include the version, a minimal fictional reproduction, and the actual error in bug reports. Report vulnerabilities privately under [SECURITY.md](SECURITY.md).

## Documentation and licensing

The [documentation index](docs/README.md) organizes installation, integration, domain references, and development. [Troubleshooting](docs/troubleshooting.md) starts from symptoms. Platform listings: [ModelScope MCP Server](https://www.modelscope.cn/mcp/servers/thomas/FateBridge). Consultation scope boundaries are defined in [safety boundaries](docs/interpretation/shared/safety-boundaries.md).

Project code is licensed under [Apache-2.0](LICENSE). Third-party components and materials appear in [NOTICE](NOTICE). Check the separate licenses of dependencies, downloaded ephemerides, and source materials before redistribution or commercial integration.
