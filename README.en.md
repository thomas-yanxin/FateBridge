# FateBridge

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
  <a href="https://www.modelscope.cn/mcp/servers/thomas/FateBridge"><img src="https://img.shields.io/badge/ModelScope-MCP%20Server-624AFF.svg" alt="ModelScope MCP Server"></a>
  <a href="https://www.modelscope.cn/collections/thomas/Onda-Skills"><img src="https://img.shields.io/badge/ModelScope-Onda%20Skills-624AFF.svg" alt="ModelScope Onda Skills Collection"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#mcp-deployment">MCP deployment</a> ·
  <a href="#rest-api">REST API</a> ·
  <a href="docs/README.md">Documentation</a> ·
  <a href="#contributing">Contributing</a>
</p>

FateBridge is a local calculation toolkit for developers and AI agents. It exposes BaZi, Zi Wei Dou Shu, Western astrology, Chinese divination, and Feng Shui rules through **MCP, REST API, and CLI**. Shared domain calculations return structured data, rule coverage, and execution receipts for integration and inspection.

The calculation service requires no LLM API key. Natural-language conversations use your chosen agent client and model. This repository provides the backend and Onda consultation skills; applications supply their own frontend.

## Contents

- [Why FateBridge](#why-fatebridge)
- [Capabilities](#capabilities)
- [Technology and prerequisites](#technology-and-prerequisites)
- [Quick start](#quick-start)
- [Architecture and project structure](#architecture-and-project-structure)
- [MCP deployment and Onda skills](#mcp-deployment)
- [REST API](#rest-api)
- [Configuration, results, and precision](#configuration-results-and-precision)
- [Development and testing](#development-and-testing)
- [Deployment and upgrades](#deployment-and-upgrades)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Scope and license](#scope-and-license)

## Why FateBridge

- **One integration across methods**: Shared input validation, tool catalog, error formats, and execution receipts reduce integration work across calculation systems.
- **Inspectable results**: Responses retain timing assumptions, precision, rule sources, and coverage limits, with field projection and paged access to the same calculation result.
- **Run in your own environment**: Use one-shot CLI commands, client-managed MCP processes, or an independent REST service. Installing dependencies and downloading ephemeris data require network access; local calculations do not depend on an online fortune-telling service.
- **Organize agent work around questions**: Repository-distributed [Onda skills](skills/README.md) guide evidence selection and interpretation for career, finances, relationships, learning, and other topics, separating calculations, traditional interpretation, and practical advice.

## Capabilities

| Domain | Coverage |
| --- | --- |
| BaZi and relationships | Four Pillars charts, nine topic analyses including career and finances, two-person compatibility, lunar-mansion compatibility |
| Timing and calendars | Luck periods, yearly/monthly/daily/hourly layers, solar terms, lunar calendar |
| Chinese systems and divination | Zi Wei, Qi Men, Liu Ren, Tai Yi, Jin Kou Jue, Mei Hua, Six Yao, and local techniques |
| Western astrology | Natal and tradition-specific charts, relationship charts, returns, transits, primary directions, and time-lord techniques |
| Feng Shui | Eight Mansions, basic Jin Suo sand/water, annual stars, historical Xuan Kong natal charts, layered layout and object review |

Current source exposes **86 business REST routes** and **87 FastMCP tools** across **13 families / 87 tools**. The central catalog contains 88 records; the CLI can execute 87. Names and exposed surfaces differ: see [interface boundaries](docs/api-reference.md#24-三端能力边界) and the per-tool [algorithm coverage matrix](docs/algorithm-coverage.md).

## Technology and prerequisites

| Component | Technology and purpose |
| --- | --- |
| Language and packaging | Python 3.10+; uv manages environments, dependency locking, and builds; source defaults to Python 3.12 |
| Services and protocols | FastAPI / Uvicorn for REST; FastMCP for MCP; argparse for CLI |
| Request and response contracts | Pydantic 2 and a central `ToolSpec` catalog for validation, discovery, and execution |
| Calendars and astrology | pyswisseph / Swiss Ephemeris, Kerykeion 5, lunardate, pytz, and related libraries |
| Rules and knowledge | Bundled JSON data; Onda skill files distributed separately through Git |
| Development checks | pytest, pytest-asyncio, Black, isort, mypy, and documentation / contract scripts |

See [pyproject.toml](pyproject.toml) for dependency constraints and [uv.lock](uv.lock) for resolved source-development versions.

Initial dependency installation and external ephemeris downloads require network access. Source installation also requires Git. No database, Redis, frontend build, or LLM API key setup is required. Large-result delivery can write private temporary files locally; see [results and precision](#inputs-results-and-precision).

## Quick start

### 0. Prepare uv

If uv is not installed, choose a method from the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/). On macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new terminal and run `uv --version`. The package requires Python 3.10+; CI covers 3.10–3.13. Tool installation below selects Python 3.12 explicitly, while source uses 3.12 through `.python-version`. uv can download this interpreter if needed.

### 1. Install

For the released CLI, REST, or MCP service, install an isolated tool environment from PyPI:

```bash
uv tool install --python 3.12 fatebridge
fatebridge doctor
```

This installs `fatebridge`, `fatebridge-api`, and `fatebridge-mcp`. If your terminal cannot find them, run `uv tool update-shell` and open a new terminal.

**For current branch features, Onda skills, or development, install from source:**

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor
```

Prefix source-environment commands with `uv run --locked --extra dev`. Bare `fatebridge` commands below refer to the isolated tool installation. Choose one installation; you do not need both. This page describes the development branch. For released packages, use the documentation at the [matching Git tag](https://github.com/thomas-yanxin/FateBridge/tags); see [CHANGELOG](CHANGELOG.md#unreleased) for unreleased changes. **The wheel does not include Onda skill files**, and an MCP connection does not install them.

### 2. Run your first calculation

No service is needed for CLI calls. This fictional example runs in macOS / Linux shells; see the [deployment guide](docs/mcp-deployment.md#windows-powershell) for PowerShell line continuation:

```bash
fatebridge bazi_birth \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem \
    bazi_birth.day_master.element bazi_birth.day_master.polarity \
  --strict-fields --no-include-snapshot-text
```

On success, exit code `0` accompanies the following business data and a `run_metadata` receipt:

```json
{
  "bazi_birth": {
    "day_master": {"stem": "庚", "element": "金", "polarity": "阳"}
  }
}
```

The values mean Geng, Metal, and Yang. Responses retain the domain's Chinese terminology.

### 3. Choose an interface

| Goal | Runtime | Next step |
| --- | --- | --- |
| Use Codex, Claude Desktop, or Cursor | Local MCP / stdio, managed by the client | [MCP deployment](#mcp-deployment) |
| Serve an MCP client that accepts a URL | FastMCP / Streamable HTTP, independent process | [HTTP MCP](#http-mcp) |
| Integrate a web, mobile, or backend application | REST API, independent HTTP process | [REST API](#rest-api) |
| Batch jobs, scripts, or terminal use | CLI, exits after execution | `fatebridge discover --family bazi`, `fatebridge describe bazi_birth --detail input` |

### 4. Discover tools and request formats

Use the installed environment's actual schema to check parameters before copying fields from another interface or older example:

```bash
fatebridge discover --family bazi
fatebridge describe bazi_birth --detail input
fatebridge scenarios --scenario onda-shiye
```

For source installations, prefix each command with `uv run --locked --extra dev`. `describe` returns input definitions and examples; omit `--detail input` to include the output contract. REST exposes discovery at `GET /api/tools`; MCP provides discovery resources. See the [API reference](docs/api-reference.md).

## Architecture and project structure

All three interfaces bind domain services through the central catalog and share execution, output validation, and receipts. Each transport then handles its protocol and result delivery:

```mermaid
flowchart LR
    REST[REST / FastAPI] --> Execution[Shared execution and output validation]
    MCP[MCP / FastMCP] --> Execution
    CLI[CLI / argparse] --> Execution
    Execution --> Services[Domain services and topic analysis]
    Services --> Core[Calendar and domain calculations]
    Core --> Data[Rule JSON / local ephemeris]
    Catalog[Central ToolSpec catalog] -.-> REST
    Catalog -.-> MCP
    Catalog -.-> CLI
```

```text
FateBridge/
├── src/fatebridge/
│   ├── api.py / mcp_server.py / cli.py  # Three interface entry points
│   ├── application/                   # Discovery, binding, execution, projection, delivery
│   ├── transports/                    # REST / MCP protocol registration
│   ├── services/catalog/              # Domain tool declarations
│   ├── services/                      # Domain orchestration and execution receipts
│   ├── analysis/                      # Topic and composite analysis
│   ├── core/                          # Algorithms, request and output models
│   ├── data/                          # Bundled rule and knowledge JSON
│   └── utils/                         # Shared places, timezones, solar time, files
├── skills/                            # Onda consultation workflows and references
├── .agents/skills/                     # Project skill discovery entry points
├── tests/                             # Domain, interface-contract, regression tests
├── scripts/                           # Documentation, generated contracts, audits
├── docs/                              # Usage, deployment, methods, development guides
├── .env.example                       # Optional runtime configuration template
├── pyproject.toml / uv.lock            # Package definition and development lockfile
└── .github/workflows/                  # CI and PyPI publishing
```

For `bazi_birth`, a request model validates parameters, `ToolSpec` binds the domain service, and shared execution validates business output and attaches `run_metadata`. The transport then applies field projection, snapshot options, and response budgets. Calculations are shared; routes, parameter shapes, and exposed tools still follow each interface's schema. See [Architecture](docs/architecture.md) for responsibilities, replay, and extension procedures.

## MCP deployment

### Local MCP: client-managed stdio

Use this for desktop agents. **You do not need REST, an open port, or a separately started `fatebridge-mcp` process.** The client launches the configured process and communicates over stdin/stdout. A manually started stdio process waiting for input is normal.

Verify MCP in your chosen installation:

```bash
# PyPI tool installation
fatebridge doctor --mcp

# Source installation: run from the repository root
uv run --locked --extra dev fatebridge doctor --mcp
```

Run the appropriate command. `ok=true` means dependency checks, independent process initialization, tool discovery, resource reading, and one fictional calculation passed. Copy the returned **`executable` absolute path** into `command` below. This is the Python interpreter with FateBridge installed, independent of a desktop client's PATH or working directory.

#### Codex

Merge this into `~/.codex/config.toml`, replacing the interpreter path. Edit an existing `fatebridge` entry instead of adding a duplicate:

```toml
[mcp_servers.fatebridge]
command = "/absolute/path/to/python"
args = ["-m", "fatebridge.mcp_server"]
startup_timeout_sec = 30
tool_timeout_sec = 60

[mcp_servers.fatebridge.env]
FATEBRIDGE_MCP_FAMILIES = ""
FATEBRIDGE_MCP_SCENARIOS = ""
PYTHONUTF8 = "1"
```

Alternatively, run the `codex.add_command` returned by doctor to register absolute paths automatically. Desktop and terminal installations may use different Codex CLIs; prefer the path doctor identifies. Choose one registration method. See the [Codex guide](docs/codex-guide.md#2-注册到-codex) and [official Codex configuration](https://developers.openai.com/codex/mcp).

#### Claude Desktop / Cursor

Merge this entry into the client's `mcpServers`, preserving other servers and replacing the interpreter path:

```json
{
  "mcpServers": {
    "fatebridge": {
      "command": "/absolute/path/to/python",
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

[Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers) uses `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows. [Cursor](https://cursor.com/docs/context/mcp) uses project-level `.cursor/mcp.json` or user-level `~/.cursor/mcp.json`; also add `"type": "stdio"` inside Cursor's server entry.

A Windows source interpreter might be `C:\path\to\FateBridge\.venv\Scripts\python.exe`; escape backslashes as `\\` in JSON. See [Windows deployment](docs/mcp-deployment.md#windows-powershell) for full PowerShell and configuration examples.

#### Verify the client connection

Reload the MCP connection after saving. If needed, restart the client and open a new chat. Confirm FateBridge tools are available, then try this fictional prompt:

> Use FateBridge to calculate the BaZi chart for a male born in Beijing on May 15, 1990 at 10:30 a.m., Gregorian calendar, local clock time. Explain only the traditional meaning of the day master.

A successful actual tool call completes client setup. A saved configuration or passing doctor check alone does not verify the active chat.

All tools are exposed by default. To narrow the tool scope, set `FATEBRIDGE_MCP_SCENARIOS=onda-shiye` for career consultations, or `FATEBRIDGE_MCP_FAMILIES=fengshui` for the Feng Shui family. Filters intersect; empty values impose no restriction. Restart MCP after changes. Run `fatebridge scenarios` to list scenarios.

### HTTP MCP

URL-capable clients can connect to the same `app` through the FastMCP runner. **This example uses the source installation.** Run from the repository root and keep the process running:

```bash
uv run --locked --extra dev fastmcp run src/fatebridge/mcp_server.py:app \
  --transport http --host 127.0.0.1 --port 8011 --path /mcp
```

The MCP URL is `http://127.0.0.1:8011/mcp`. The `fatebridge-mcp` entry point still uses stdio; these HTTP options belong to the [FastMCP runner](https://gofastmcp.com/deployment/running-server). REST on port `8010` and MCP on port `8011` are separate services.

A remote machine can keep its loopback binding and accept connections through an SSH tunnel. See the [MCP deployment guide](docs/mcp-deployment.md#http-与远程部署) for URL configurations, protocol verification, and a persistent-service template. **REST's `FATEBRIDGE_API_KEYS` does not protect MCP.** Public deployment requires separate TLS, MCP authentication, and access controls; this example does not provide tenant isolation.

### Onda consultation skills

MCP supplies calculation tools; Onda supplies consultation workflows. When you use the source repository as a Codex project, `AGENTS.md` and `.agents/skills/` provide project guidance and skill entry points. Confirm discovery in a new chat. Other clients must load `skills/` through their own skill mechanisms; MCP does not transfer these files. See the [Onda skill index](skills/README.md).

ModelScope entries: [FateBridge MCP Server](https://www.modelscope.cn/mcp/servers/thomas/FateBridge) · [Onda Skills collection](https://www.modelscope.cn/collections/thomas/Onda-Skills). Follow those pages for platform-specific setup, or this README for local installation and configuration.

## REST API

Start a local service after installation. On macOS / Linux:

```bash
API_HOST=127.0.0.1 fatebridge-api
# Source: API_HOST=127.0.0.1 uv run --locked --extra dev fatebridge-api
```

On Windows PowerShell:

```powershell
$env:API_HOST = "127.0.0.1"
fatebridge-api
```

In another terminal, check the service and run the same fictional calculation:

```bash
curl --fail http://127.0.0.1:8010/health
curl --fail http://127.0.0.1:8010/ready
curl --fail 'http://127.0.0.1:8010/api/cn/bazi/birth?fields=bazi_birth.day_master&strict_fields=true&include_snapshot_text=false' \
  -H 'Content-Type: application/json' \
  -d '{
    "birth_year": 1990, "birth_month": 5, "birth_day": 15,
    "birth_hour": 10, "birth_minute": 30, "gender": "男",
    "birth_place": "北京", "birth_timezone": "Asia/Shanghai"
  }'
```

`/health` returns `{"status":"healthy"}`. The calculation returns `bazi_birth.day_master` and `run_metadata`. `/ready` reports required readiness checks, not verification of every algorithm or ephemeris file. Inspect schemas and try requests in [Swagger UI](http://127.0.0.1:8010/docs).

The default binding is `0.0.0.0:8010`; the examples explicitly restrict it to the local machine. Before shared deployment, set `FATEBRIDGE_API_KEYS=client:replace-with-a-secret`, send `X-API-Key: replace-with-a-secret` on business requests, and provide TLS, access controls, and rate limits at a gateway. Keys do not create user accounts or result ownership boundaries. Operational routes including `/health`, `/ready`, `/metrics`, and API documentation are exempt from authentication; see the [security policy](SECURITY.md#scope-notes).

## Configuration, results, and precision

### Environment variables

Basic CLI calculations need no `.env`. For source API / MCP configuration, optionally copy the template (macOS / Linux; preserves an existing file):

```bash
cp -n .env.example .env
```

| Setting | Default | Purpose |
| --- | --- | --- |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8010` | REST bind address and port; use `127.0.0.1` for local access |
| `FATEBRIDGE_API_KEYS` | Empty; authentication off | REST shared keys such as `client:secret`; comma-separated for multiple keys |
| `API_KEY_HEADER_NAME` | `X-API-Key` | REST key header; send only `secret`, without `client:` |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated browser CORS origins |
| `FATEBRIDGE_MCP_FAMILIES` / `FATEBRIDGE_MCP_SCENARIOS` | Empty; no filtering | MCP family / scenario intersection; does not change REST / CLI |
| `SE_EPHE_PATH` | Unset; tries local `ephe/` | Custom ephemeris directory; not included in `.env.example` |
| `FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY` | `min(4, max(1, CPU count))` | Heavy-calculation concurrency per REST process, at least 1; not a request rate limit |
| `LOG_LEVEL` | `INFO` | Logging level |

Source API / MCP processes load the repository-root `.env`; existing process variables take precedence. Parsing supports simple `KEY=value`, wrapping quotes, and whole-line comments, without shell expansion. CLI does not automatically load `.env`. For isolated tool installations, inject settings through the launcher or client's `env`. Restart the relevant service after configuration changes. See [Getting started](docs/getting-started.md#配置环境变量) for loading rules and authentication examples.

### Ephemeris data

To obtain external Swiss Ephemeris data for a source installation, run from the repository root:

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe
```

By default, this downloads three `.se1` files into the repository's `ephe/` directory. Other eras or bodies may need additional files; the data license is separate from the code license. Tool-installation users should follow the [custom-directory download procedure](docs/getting-started.md#星历数据与精度) and set `SE_EPHE_PATH` in the service environment. Restart the service after preparing data and check the actual ephemeris model in its output.

### Inputs, results, and precision

- **Inputs**: Birth interfaces use Gregorian dates. Supply hours, timezone, and location according to each tool's schema; do not replace an unknown birth time with midnight. Chinese birth calculations default to true solar time; core Western charts default to civil time. Retain resolution and precision warnings.
- **Results**: Check MCP `isError`, REST status codes, or CLI exit codes before reading business data. `fields` accepts dotted paths; `strict_fields=true` rejects invalid paths. REST projection options belong in query parameters, not the JSON body.
- **Complete exports**: Set `fields=null` on the first call for complete JSON. MCP's default budget is 8192 characters; follow `result_delivery` to read the same run. Fields omitted by the initial projection cannot be recovered later. See [same-run exports](docs/agent-guide.md#完整结果交付与同次导出).
- **Precision and reproduction**: Keep original inputs and `run_metadata`. External `.se1` ephemeris files are not bundled in the wheel. Inspect `chart_profile.ephemeris_model` and `run_metadata.engine_is_approximate`; an importable dependency alone does not establish that data files were loaded. Reproduction also requires matching implementation, data, and environment; see [ephemeris guidance](docs/getting-started.md#星历数据与精度).

Large-result delivery writes files on demand to the current OS user's private temporary directory, without a database. The current implementation expires results after one hour and caps total directory storage at 64 MiB; capacity pressure can evict older results sooner. Export results you need to retain. This temporary delivery mechanism does not provide encryption or application-user isolation. File formats, pagination, and hash verification are described in [complete-result delivery](docs/agent-guide.md#完整结果交付与同次导出).

## Development and testing

Complete [source installation](#1-install) first. Run these commands from the repository root; no environment activation is needed:

| Task | Command |
| --- | --- |
| Sync locked development environment | `uv sync --locked --extra dev` |
| Check lockfile | `uv lock --check` |
| Inspect version, interpreter, dependencies | `uv run --locked --extra dev fatebridge doctor` |
| Verify independent stdio MCP | `uv run --locked --extra dev fatebridge doctor --mcp --scenario onda-shiye` |
| Start local REST (macOS / Linux) | `API_HOST=127.0.0.1 uv run --locked --extra dev fatebridge-api` |
| Run all tests | `uv run --locked --extra dev python -m pytest -q` |
| Run interface alignment tests | `uv run --locked --extra dev python -m pytest -q tests/test_api_alignment.py` |
| Check formatting | `uv run --locked --extra dev black --check src/fatebridge scripts tests` |
| Check import order | `uv run --locked --extra dev isort --check-only src/fatebridge scripts tests` |
| Check types | `uv run --locked --extra dev mypy src/fatebridge/` |
| Build sdist / wheel | `uv build` |

`tests/` contains domain regressions, input / output contracts, interface alignment, result delivery, documentation, and skill checks. `tests/golden/` contains numerical baselines. Start with files relevant to your change; select relationship-chart cases with `uv run --locked --extra dev python -m pytest -q tests/test_api_alignment.py -k relative_chart`.

For **documentation-only changes**, start with the following checks. Update generated sections through their scripts:

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python scripts/build_scenario_manifest.py --check
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
uv run --locked --extra dev python -m pytest -q \
  tests/test_documentation_integrity.py tests/test_doc_tool_counts.py \
  tests/test_scenario_routing_coverage.py tests/test_skills_interface_contract.py \
  tests/test_skills_engine_contract.py tests/test_codex_call_contracts.py \
  tests/test_ci_scope.py
git diff --check
```

CI separates locked-environment checks, the Python 3.10–3.13 latest-dependency matrix, and lowest-direct-dependency tests. A Windows / Python 3.12 job checks startup and storage. PRs changing only ordinary documentation use documentation checks; main-branch pushes run the full suite. Golden byte comparisons require the Linux x86_64 / Python 3.12 reference environment; skips on other platforms do not establish that check passed. See [CI scope](docs/development-guide.md#ci-运行范围).

## Deployment and upgrades

### Choose a runtime

Clients manage local stdio MCP processes. REST and HTTP MCP require independently managed services. The repository currently provides no Dockerfile or Compose file. For containers, follow the [official uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) to build your image: copy source, package metadata, and lockfile; install runtime dependencies with `uv sync --locked --no-dev`; run the selected entry point as a non-root user. Container HTTP services must bind to `0.0.0.0`; host port mappings and the gateway determine external access. Prepare ephemeris separately during builds or mount it as a data volume, and provide a writable temporary result directory.

For Linux host deployment, create a source environment at a stable path, then use systemd or another process manager to run `.venv/bin/fatebridge-api` or the FastMCP HTTP runner. An MCP unit template is provided in [persistent deployment](docs/mcp-deployment.md#常驻与公网边界). The service user needs access to the actual Python interpreter, source, ephemeris, and private temporary directory. Inject environment settings explicitly through service configuration. See the [security policy](SECURITY.md#scope-notes) for REST keys, network access, and operational endpoints.

### Verify and operate

- REST: check `/health` and `/ready`, then execute the fictional request above. `/metrics` provides Prometheus metrics for the current process.
- HTTP MCP: initialize, discover, and call a tool through an MCP client. A browser GET to `/mcp` does not replace protocol verification; see the [HTTP verification example](docs/mcp-deployment.md#http-与远程部署).
- Diagnostics: record doctor's version, interpreter, and package path, and inspect process-manager logs. Redact receipts and logs before sharing.

### Upgrade and roll back

Save the version / commit, service configuration, and any exports you need before upgrading. For isolated tools, use `uv tool upgrade fatebridge`. For source, preserve local changes, then run `git pull --ff-only` and `uv sync --locked --extra dev`. Repeat doctor and protocol verification, restart services or client connections, and check the version actually loaded.

To roll back, choose a confirmed release or Git tag / commit, install it in a separate environment, and switch the service path. See [upgrades and removal](docs/mcp-deployment.md#升级回退与停用) for version pinning and shutdown commands. A successful CI run publishes to PyPI only when its package version is not already published; source updates do not necessarily produce new PyPI releases. See [packaging and publishing](docs/development-guide.md#ci打包与发布).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Command not found / GUI launch failure | Run `uv tool update-shell` for tool installs; use doctor's absolute `executable` path in GUI clients |
| `fatebridge-mcp` waits without output | stdio is waiting for client messages; register it with a client, or use the HTTP runner above |
| Missing tools or new parameters | Check family / scenario intersection and package path; restart the connection and open a new chat |
| MCP connection fails at `http://localhost:8010` | This is REST; use `command/args` for stdio or the HTTP MCP `/mcp` URL |
| `partial`, approximation, or dependency errors | Check actual coverage, precision, inputs, backend dependencies, and ephemeris files |
| REST returns `401` | Check service key configuration and request header; send only the secret, without its name prefix |
| `strict_fields` rejects a path or parameters fail validation | Check requests with the installed `describe <tool> --detail input`; use full `describe` for output paths; REST projection belongs in query parameters |
| Ephemeris download or directory access fails | Check network access, write permissions, and service user; set the correct data path in the startup environment |
| Large-result reference becomes unavailable | Check expiry and capacity eviction; export temporary results promptly, and do not treat a new calculation as the original run |

See [Troubleshooting](docs/troubleshooting.md) for further recovery steps and the [deployment guide](docs/mcp-deployment.md) for MCP verification, upgrades, and removal.

## Documentation

Detailed guides are currently maintained in Chinese; commands and configuration keys are shared across languages.

| Goal | Guide |
| --- | --- |
| Install, configure, download ephemeris | [Getting started](docs/getting-started.md) |
| Deploy local or remote MCP | [MCP deployment](docs/mcp-deployment.md) |
| Consult through Codex | [Codex guide](docs/codex-guide.md) · [Onda skills](skills/README.md) |
| Build an application or agent integration | [Integration guide](docs/agent-guide.md) · [API reference](docs/api-reference.md) |
| Check implementation, methods, precision | [Algorithm coverage](docs/algorithm-coverage.md) · [Core concepts](docs/concepts.md) |
| Find topic routes, rules, examples | [Scenario routing](docs/scenario-routing.md) · [Examples](docs/examples/README.md) · [Rule documentation](docs/README.md#理解计算与结果) |
| Develop, migrate, troubleshoot | [Architecture](docs/architecture.md) · [Development](docs/development-guide.md) · [Migration](docs/migration.md) · [Troubleshooting](docs/troubleshooting.md) |

See the full [documentation index](docs/README.md) and [CHANGELOG](CHANGELOG.md).

## Contributing

Algorithm fixes, interface improvements, tests, documentation, and skills are welcome. Set up your environment and choose checks under [Development and testing](#development-and-testing). Code changes also need relevant domain tests and interface-contract validation. Use `uv add` / `uv remove` for dependency changes and commit both `pyproject.toml` and `uv.lock`.

See [CONTRIBUTING](CONTRIBUTING.md) for development and PR procedures. Report defects through [Issues](https://github.com/thomas-yanxin/FateBridge/issues) with version, OS, minimal fictional input, and actual error. Report security issues privately under [SECURITY.md](SECURITY.md).

## Scope and license

Traditional interpretations and scores are cultural references, not real-world success probabilities. Calculation tests check calendar, numerical, and selected-rule consistency; they do not establish predictive validity. Consultations exclude lifespan/death prediction, assertions of disasters, clinical diagnosis/treatment, and medical timing; see [consultation boundaries](skills/_shared/safety-boundaries.md).

Local execution still requires consideration of how agent clients, model providers, chat histories, and exported files handle personal data. Do not commit real birth records or include them in public Issues.

Project code is licensed under [Apache-2.0](LICENSE). Third-party components and sources are listed in [NOTICE](NOTICE). Dependencies and ephemeris data retain their own licenses; review these separately before redistribution or commercial integration.

[Back to top ↑](#fatebridge)
