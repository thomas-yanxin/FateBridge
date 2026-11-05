# FateBridge

<p align="center">
  <img src="asserts/fatebridge-banner.png" alt="FateBridge banner with a silver Möbius loop and star trails" width="100%">
</p>

<p align="center">
  <strong>Inspectable Chinese metaphysics and astrology calculations for AI applications</strong>
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
  <a href="https://www.modelscope.cn/collections/thomas/Onda-Skills"><img src="https://img.shields.io/badge/ModelScope-Onda%20Skills-624AFF.svg" alt="ModelScope Onda Skills Collection"></a>
</p>

FateBridge provides local metaphysics and astrology calculations for AI applications through **MCP, REST API, and CLI**. Results include structured data, time conventions, and execution receipts. [Onda consultation skills](skills/README.md) guide an agent in selecting evidence and explaining traditional interpretations. Your application supplies the model conversation and interface.

The calculation service requires no LLM API key. It serves application developers, MCP clients, and researchers checking calendar calculations and selected traditional rules. Reproducibility, source conformity, and predictive validity are evaluated separately.

## Capabilities

| Domain | Implemented scope | Details and limits |
| --- | --- | --- |
| BaZi and relationships | Four pillars, nine topics, pairwise rule scores, luck periods through hourly timing | [Assessment](docs/bazi-assessment.md) · [Timing](docs/bazi-timing.md) · [Scores](docs/compatibility-scoring.md) |
| Chinese systems and divination | Zi Wei, Qi Men, Liu Ren, Jin Kou, Tai Yi, Mei Hua, Liu Yao, He Luo, and Canping | [Topic index](docs/README.md#计算原理与专题) |
| Astrology | Western natal, relationship, timing, and event charts; Jyotish, Guolao, Sukuyo, and other schools | [Western](docs/western-astrology.md) · [Jyotish](docs/jyotish.md) · [Coverage](docs/algorithm-coverage.md) |
| Human Design | Dual moments separated by 88° solar longitude, gates and lines, channels, type, and authority | [Calculation and acceptance](docs/human-design.md) |
| Feng Shui | Eight Mansions, basic sand/water rules, annual/monthly stars, historical Xuan Kong charts, layouts, and measured workstations | [Home assessment](docs/fengshui.md) · [Workstations](docs/fengshui-workstation-layout.md) |

The current source exposes **91 business REST routes** and **92 FastMCP tools** across **13 families**. The central catalog contains 93 entries; 92 are executable through the CLI. The interfaces share domain calculations but differ in names and input shapes; see [interface boundaries](docs/api-reference.md#24-三端能力边界). [Algorithm status](docs/algorithm-status.md) records method versions, source disagreements, and outstanding acceptance work. Detailed guides are currently in Chinese; commands, field names, and schemas retain their API spelling.

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first. Python 3.10+ is required; the source checkout defaults to 3.12, and CI tests 3.10–3.13. Choose one installation method.

### Released package

```bash
uv tool install --python 3.12 fatebridge
fatebridge doctor
```

This provides `fatebridge`, `fatebridge-api`, and `fatebridge-mcp`. If they are not on your PATH, run `uv tool update-shell` and reopen the terminal.

### Current source

For current branch features, Onda skills, or development:

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor
```

This README describes the development branch. For a released package, use the documentation at its [Git tag](https://github.com/thomas-yanxin/FateBridge/tags); pending changes appear in the [Changelog](CHANGELOG.md#unreleased). The Python wheel contains calculation code and rule data. Onda skills are distributed separately through the repository or a [plugin bundle](docs/mcp-deployment.md#onda-插件的构建与安装).

### Run a calculation

The fictional example below runs in a macOS / Linux terminal without starting a service. Source users should prefix `fatebridge` with `uv run --locked --extra dev`. See the [Windows example](docs/mcp-deployment.md#windows-powershell) for PowerShell.

```bash
fatebridge bazi_birth \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem bazi_birth.day_master.element \
    bazi_birth.day_master.polarity --strict-fields --no-include-snapshot-text \
  --response-char-limit 8192
```

On success, the command exits with `0` and returns the day master `庚 / 金 / 阳` (Geng / Metal / Yang) plus `run_metadata`. Large execution evidence is deferred through `result_delivery`; see [reading results](#read-and-verify-results). This verifies this calculation in the installed environment. Discover other tools and their inputs with:

```bash
fatebridge discover --family bazi
fatebridge describe bazi_birth --detail input
```

## Connect an assistant or application

| Goal | Connection | Guide |
| --- | --- | --- |
| Local Codex, Claude Desktop, or Cursor | Client-managed MCP stdio process | [MCP setup](docs/mcp-deployment.md#注册本地-stdio) · [First Codex conversation](docs/codex-guide.md) |
| MCP client accepting a URL | Independent Streamable HTTP service | [HTTP and remote deployment](docs/mcp-deployment.md#http-与远程部署) |
| Web, mobile, or backend application | Independent REST service | [Start REST](docs/getting-started.md#启动-rest-并检查状态) · [Integration guide](docs/agent-guide.md) |
| Scripts and batch jobs | One-shot CLI execution | [Getting started](docs/getting-started.md) · [Requests](docs/examples/README.md) |

For local MCP, run `fatebridge doctor --mcp` and register the absolute Python path returned as `executable`. The client manages the stdio process. After saving the configuration, verify tool visibility and a real call in a new chat. MCP and Onda skills load separately.

Start REST locally with `API_HOST=127.0.0.1 fatebridge-api`. The default port is `8010`, with interactive API documentation at `/docs`. The default bind address listens on all interfaces; review [configuration](docs/getting-started.md#配置环境变量) and [security](SECURITY.md). REST API keys do not protect MCP.

## Read and verify results

- **Inputs and time:** use confirmed information, including time zone, location, and analysis time. Do not fill an unknown birth hour with a default or example. Read the actual time convention returned by each method.
- **Summary and full output:** project task-specific `fields` for a summary. For complete JSON, retain all fields on the first call and follow `result_delivery` to read the same run. See [full-result delivery](docs/agent-guide.md#完整结果交付与同次导出).
- **Ephemeris and precision:** an installed Python library does not establish that external data files were used. Check the actual model, source, and approximation flag. See [ephemeris setup](docs/ephemeris.md) and [solar backends](docs/solar-backends.md).
- **Evidence and limits:** software regression, independent numerical references, classical sources, model explanations, and real-world validity have separate acceptance criteria. A `partial` status limits its own layer. See [core concepts](docs/concepts.md).

## Development and contributions

The package uses a Python `src` layout. FastAPI, FastMCP, and CLI adapters call shared execution and domain services through a central `ToolSpec` catalog. See [architecture](docs/architecture.md). Dependencies are declared in [pyproject.toml](pyproject.toml), with development resolutions pinned in [uv.lock](uv.lock).

Contributions to documentation, algorithms, interfaces, tests, and Onda skills are welcome. Follow [CONTRIBUTING](CONTRIBUTING.md) and select checks from the [development guide](docs/development-guide.md). Start documentation-only validation with:

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q tests/quality/test_documentation_integrity.py tests/quality/test_doc_tool_counts.py
```

[Documentation maintenance](docs/development-guide.md#文档维护与验证) covers interface, skill, and generated-source synchronization. Include the version, a minimal fictional reproduction, and the actual error in bug reports. Report vulnerabilities privately under [SECURITY.md](SECURITY.md).

## Documentation and scope

The [documentation index](docs/README.md) organizes installation, integration, domain references, and development. [Troubleshooting](docs/troubleshooting.md) starts from symptoms. Platform listings: [ModelScope MCP Server](https://www.modelscope.cn/mcp/servers/thomas/FateBridge) · [Onda Skills](https://www.modelscope.cn/collections/thomas/Onda-Skills).

Traditional interpretations and rule scores are cultural references. Scores are not real-world success probabilities. Consultations exclude lifespan/death prediction, assertions of disasters, clinical diagnosis/treatment, and medical timing; see [consultation boundaries](skills/_shared/safety-boundaries.md). Agent clients, model providers, chat histories, and exports have their own personal-data handling boundaries beyond local calculation.

Project code is licensed under [Apache-2.0](LICENSE). Third-party components and materials appear in [NOTICE](NOTICE). Check the separate licenses of dependencies, downloaded ephemerides, and source materials before redistribution or commercial integration.
