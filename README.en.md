<p align="center">
  <img src="asserts/fatebridge-banner.png" alt="FateBridge banner with a silver Möbius loop and star trails" width="100%">
</p>

<p align="center">
  <strong>Traditional Chinese metaphysics and astrology calculations for applications and AI agents</strong>
</p>

<p align="center">
  <a href="README.md">简体中文</a> · English
</p>

<p align="center">
  <a href="https://pypi.org/project/fatebridge/"><img src="https://img.shields.io/pypi/v/fatebridge.svg" alt="PyPI"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python"></a>
  <a href="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml"><img src="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#connect-an-agent">Connect an agent</a> ·
  <a href="#connect-an-application">Connect an application</a> ·
  <a href="docs/README.md">Documentation</a> ·
  <a href="#contributing">Contributing</a>
</p>

FateBridge organizes BaZi, Zi Wei Dou Shu, Chinese divination, Western astrology, and Feng Shui rules into Python calculation tools that run locally. It provides calculation evidence to agents through **MCP**, serves applications through **REST**, and supports direct terminal use through the **CLI**.

---

## Key features

- **Chinese and Western systems through a shared interface**: BaZi, Zi Wei Dou Shu, Chinese divination, Western astrology, and Feng Shui calculations are organized into structured tools for applications and AI agents.
- **Consultation organized around the question**: Onda selects relevant methods and timing layers for topics such as career, finances, relationships, and education, connects results to the question, and reuses relevant evidence in follow-ups.
- **Open source, local execution, and flexible integration**: Connect agents through MCP, applications through REST, or use the CLI directly, with field selection and complete-result delivery from the same calculation.

## Supported capabilities

| Area | Main capabilities |
| --- | --- |
| BaZi and two-person relationships | Four Pillars charts, nine topic analyses including career and wealth, two-person compatibility, and Sukuyō compatibility |
| Timing and calendars | Major luck periods, annual, monthly, daily, and hourly timing layers, solar terms, and the lunar calendar |
| Chinese metaphysics and divination | Zi Wei Dou Shu, Qi Men Dun Jia, Liu Ren, Tai Yi, Jin Kou Jue, Mei Hua, Six Yao, and local techniques |
| Western astrology | Natal and tradition-specific charts, relationship charts, returns, transits, primary directions, and time-lord techniques |
| Feng Shui | Eight Mansions, basic Jin Suo landform rules, annual stars, historical Xuan Kong house charts, and layered layout/object reviews |

The current development branch provides **86 business REST routes** and **87 FastMCP tools**, covering **13 families / 87 tools**. The central catalog contains 88 records, of which 87 are executable through the CLI. Names and request shapes vary by interface; see [interface boundaries](docs/api-reference.md#24-三端能力边界). For each tool's implementation, precision, and limitations, see the [algorithm coverage matrix](docs/algorithm-coverage.md).

## Quick start

Requires **Python 3.10+** and [uv](https://docs.astral.sh/uv/getting-started/installation/). CI currently covers Python 3.10–3.13.

### Installation

Install the latest release of the standalone command-line tools from PyPI:

This page describes the current development branch; see [CHANGELOG](CHANGELOG.md#unreleased) for unpublished changes. To try the latest skills and interfaces, use the [source installation](#contributing).

```bash
uv tool install fatebridge
```

Installation provides three commands: `fatebridge`, `fatebridge-api`, and `fatebridge-mcp`. To run the current checkout or modify the code, use the [source installation](#contributing). Onda skills are distributed with the Git repository; the current wheel does not include the skills directory.

### Run your first calculation

The CLI does not require a running service. This fictional example returns only three fields describing the BaZi Day Master:

```bash
fatebridge bazi_birth \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem \
    bazi_birth.day_master.element bazi_birth.day_master.polarity \
  --strict-fields
```

Here, `男` means male and `北京` means Beijing. The business data is shown below; the response also includes a `run_metadata` execution receipt:

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

The returned values mean Geng, Metal, and Yang. Continue exploring tools and input contracts:

```bash
fatebridge discover --family bazi
fatebridge describe bazi_birth --detail input
```

See [Getting started](docs/getting-started.md) for installation and Windows instructions, environment variables, and ephemeris configuration. Detailed guides and tool output currently use Chinese terminology.

## Connect an agent

MCP uses **stdio**, with hosts such as Codex, Claude, or Cursor launching a local subprocess. First check the installation and connection, for example with the career scenario:

```bash
fatebridge doctor --mcp --scenario onda-shiye
```

The diagnostic checks dependencies, an independent MCP process, tool discovery, resource reading, and a fictional calculation. Codex users can run the returned `codex.add_command` to register the connection; it uses absolute paths for the current installation. Other hosts can adapt `command`, `args`, and `env` from the returned `codex.config` to their own configuration format.

After registration, confirm that tools are visible in a new chat, then ask in everyday language. For example:

> Use FateBridge to explore my career. I am considering changing jobs and would like to understand which responsibilities might suit me. Use these fictional details: male, born May 15, 1990 at 10:30 a.m. in Beijing, recorded in local clock time using the Gregorian calendar. Analyze 2026 and explain the evidence in plain language.

`--scenario onda-shiye` limits the connection to the career scenario's tool scope. To support other topics, change the scenario or clear the filter and restart the connection. [Onda skills](skills/README.md) organize consultations by life topic, task, and time range; a topic may draw on multiple perspectives, and follow-ups retain relevant results.

See the [Codex guide](docs/codex-guide.md) for registration steps, configuration formats, and conversation examples. For other hosts, see the [Agent integration guide](docs/agent-guide.md#fastmcpagent-host).

## Connect an application

Start a local REST service. The following command is for macOS / Linux; for Windows configuration, see [Getting started](docs/getting-started.md#配置环境变量):

```bash
API_HOST=127.0.0.1 fatebridge-api
```

In another terminal, send a request:

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

`/health` returns `{"status":"healthy"}`. The chart request returns business data under `bazi_birth`, alongside an execution receipt. Open [Swagger UI](http://localhost:8010/docs) in your browser to inspect request schemas and try the API.

The default bind address is `0.0.0.0`; the command above restricts access to the local machine. When `FATEBRIDGE_API_KEYS` is enabled, business requests must also send `X-API-Key` (the default header name). Configuration and deployment boundaries are covered in [Getting started](docs/getting-started.md#配置环境变量) and the [security policy](SECURITY.md). Python and JavaScript examples are available in the [integration guide](docs/agent-guide.md).

## Results and reproducibility

Keep the original input and `run_metadata`, and check the timezone, solar-time policy, analysis time, and engine version. The receipt records calculation assumptions; reproduction also requires matching implementation, data, and runtime environment.

- **Request only what you need**: Use `fields` to project results and `strict_fields=true` to reject invalid field paths.
- **Plan complete exports from the first call**: For complete JSON or a full timeline, set `fields=null` on the first call and keep the default response budget. MCP's default budget is 8192 characters; when exceeded, follow `result_delivery` to read the result from the same run. A summary projection cannot recover fields that were not selected. See [complete-result delivery and same-run export](docs/agent-guide.md#完整结果交付与同次导出).
- **Judge precision from the actual response**: Core charts support local ephemeris and approximation paths; inspect `chart_profile.ephemeris_model` and `run_metadata.engine_is_approximate`. Western predictive, event, and lifecycle tools report errors when required backend dependencies are missing. Ephemeris data is obtained separately; see [ephemeris data and precision](docs/getting-started.md#星历数据与精度).

## Documentation

| Your goal | Read |
| --- | --- |
| Install, configure, or troubleshoot | [Getting started](docs/getting-started.md) · [Troubleshooting](docs/troubleshooting.md) |
| Consult through Codex or connect an agent | [Codex guide](docs/codex-guide.md) · [Agent integration guide](docs/agent-guide.md) |
| Look up tools, fields, and interface differences | [API reference](docs/api-reference.md) · [Algorithm coverage](docs/algorithm-coverage.md) |
| Choose tools and skills by question | [Scenario routing](docs/scenario-routing.md) · [Onda skills](skills/README.md) |
| Understand tools, receipts, and result states | [Core concepts](docs/concepts.md) |
| Understand domain rules and sources | [BaZi assessment](docs/bazi-assessment.md) · [Feng Shui](docs/fengshui.md) · [Compatibility scoring](docs/compatibility-scoring.md) |
| Understand architecture, development, or upgrades | [Architecture](docs/architecture.md) · [Development guide](docs/development-guide.md) · [Migration](docs/migration.md) |

See the [documentation index](docs/README.md) for all guides and maintenance responsibilities, and [CHANGELOG](CHANGELOG.md) for version changes.

## Contributing

Contributions to algorithms, interfaces, tests, documentation, and consultation skills are welcome. Source development uses the locked uv environment; no manual virtual-environment activation is required:

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge list
```

For documentation-only changes, start with:

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q \
  tests/test_doc_tool_counts.py tests/test_scenario_routing_coverage.py
```

Code changes also require domain tests and the applicable CI checks; see the [development guide](docs/development-guide.md). For the contribution and PR workflow, see [CONTRIBUTING.md](CONTRIBUTING.md). Report bugs and feature requests through [Issues](https://github.com/thomas-yanxin/FateBridge/issues); report security issues privately as described in [SECURITY.md](SECURITY.md).

## Scope and license

FateBridge's calculation validation concerns calendar, numerical, and selected-rule consistency. Traditional interpretations and scores are cultural references: scores are not probabilities of real-world success, and passing software tests does not establish predictive validity. Consultations exclude lifespan/death prediction, assertions of disasters, clinical diagnosis or treatment, and medical timing. Traditional health content is not a medical conclusion; see the [consultation boundaries](skills/_shared/safety-boundaries.md).

The project provides a backend, CLI, and skill materials; integrating applications manage their own frontend and deployment. Code is licensed under [Apache-2.0](LICENSE). Third-party components and sources are listed in [NOTICE](NOTICE); dependencies and ephemeris data retain their own licensing terms.

---

<p align="center">
  <img src="asserts/fatebridge-logo-square.png" alt="FateBridge Möbius loop logo" width="72" height="72">
</p>

<p align="center">
  <a href="#fatebridge">Back to top ↑</a>
</p>
